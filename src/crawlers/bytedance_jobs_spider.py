#!/usr/bin/env python3
"""抓取字节跳动社招网站中的全部研发职位。"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.async_api import Browser, Error as PlaywrightError, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright


START_URL = "https://jobs.bytedance.com/experienced/position"
FIELDS = [
    "position_id",
    "job_id",
    "title",
    "locations",
    "employment_type",
    "category",
    "publish_time",
    "description",
    "requirement",
    "url",
]

PUBLISH_TIME_KEYS = ("publish_time", "publishTime")
CHINA_TIMEZONE = timezone(timedelta(hours=8))


def parse_publish_time(source: str, position_id: str = "") -> str:
    """从页面或接口源数据中提取发布时间，并转换为北京时间。"""
    candidates: list[tuple[int, str]] = []
    position_at = source.find(position_id) if position_id else -1
    for key in PUBLISH_TIME_KEYS:
        pattern = re.compile(
            rf'["\']{key}["\']\s*:\s*["\']?'
            r"(\d{10,13}|\d{4}-\d{2}-\d{2}(?:[T ][^\"']+)?)",
            re.I,
        )
        for match in pattern.finditer(source):
            distance = abs(match.start() - position_at) if position_at >= 0 else 0
            if position_id and (position_at < 0 or distance > 100_000):
                continue
            candidates.append((distance, match.group(1)))

    if not candidates:
        return ""
    raw = min(candidates, key=lambda item: item[0])[1]
    if raw.isdigit():
        timestamp = int(raw)
        if len(raw) == 13:
            timestamp /= 1000
        utc_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    else:
        try:
            utc_time = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw
        if utc_time.tzinfo is None:
            utc_time = utc_time.replace(tzinfo=timezone.utc)
    return utc_time.astimezone(CHINA_TIMEZONE).isoformat(sep=" ", timespec="seconds")


def replace_query(url: str, **changes: Any) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({key: str(value) for key, value in changes.items()})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def parse_detail_text(text: str, url: str, publish_time: str = "") -> dict[str, str]:
    """把详情页 main 元素的纯文本转换为结构化字段。"""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    desc_at = lines.index("职位描述") if "职位描述" in lines else -1
    req_at = lines.index("职位要求") if "职位要求" in lines else -1
    end_markers = {"投递", "相关职位", "分享"}

    def section(start: int, fallback_end: int) -> str:
        if start < 0:
            return ""
        end = fallback_end
        for index in range(start + 1, len(lines)):
            if lines[index] in end_markers:
                end = min(end, index)
                break
        return "\n".join(lines[start + 1 : end]).strip()

    meta = lines[1:desc_at] if desc_at > 0 else lines[1:5]
    job_id = ""
    for line in meta:
        match = re.search(r"职位\s*ID[：:]\s*(\S+)", line, re.I)
        if match:
            job_id = match.group(1)
            break

    position_match = re.search(r"/position/(\d+)/detail", url)
    return {
        "position_id": position_match.group(1) if position_match else "",
        "job_id": job_id,
        "title": lines[0] if lines else "",
        "locations": meta[0] if len(meta) > 0 else "",
        "employment_type": meta[1] if len(meta) > 1 else "",
        "category": meta[2] if len(meta) > 2 else "",
        "publish_time": publish_time,
        "description": section(desc_at, req_at if req_at > desc_at else len(lines)),
        "requirement": section(req_at, len(lines)),
        "url": url,
    }


async def wait_for_jobs(page: Page, timeout_ms: int) -> None:
    await page.locator('main a[href*="/position/"][href*="/detail"]').first.wait_for(
        state="attached", timeout=timeout_ms
    )


async def read_job_total(page: Page) -> int | None:
    main_text = await page.locator("main").inner_text()
    match = re.search(r"开启新的工作[（(]([\d,]+)[）)]", main_text)
    return int(match.group(1).replace(",", "")) if match else None


async def select_development(page: Page, timeout_ms: int) -> tuple[str, int | None]:
    await page.goto(START_URL, wait_until="domcontentloaded", timeout=timeout_ms)
    await page.locator("main").wait_for(state="attached", timeout=timeout_ms)
    await wait_for_jobs(page, timeout_ms)
    development = page.locator('li[role="treeitem"]').filter(has_text="研发")
    try:
        await development.first.wait_for(state="visible", timeout=timeout_ms)
    except PlaywrightTimeoutError as exc:
        raise RuntimeError("等待“研发”筛选项超时，网站页面结构可能已变化") from exc
    if await development.count() != 1:
        raise RuntimeError("无法唯一定位“研发”筛选项，网站页面结构可能已变化")
    checkbox = development.locator(".atsx-tree-checkbox")
    if await checkbox.count() != 1:
        raise RuntimeError("无法定位“研发”复选框，网站页面结构可能已变化")
    checkbox_class = await checkbox.get_attribute("class") or ""
    if "atsx-tree-checkbox-checked" in checkbox_class:
        return page.url, await read_job_total(page)
    initial_total = await read_job_total(page)
    await checkbox.click()
    deadline = asyncio.get_running_loop().time() + timeout_ms / 1000
    total = initial_total
    while asyncio.get_running_loop().time() < deadline:
        total = await read_job_total(page)
        checkbox_class = await checkbox.get_attribute("class") or ""
        if (
            "atsx-tree-checkbox-checked" in checkbox_class
            and total is not None
            and total != initial_total
        ):
            break
        await asyncio.sleep(0.25)
    else:
        raise RuntimeError("点击“研发”后职位总数未变化，筛选可能未生效")
    await wait_for_jobs(page, timeout_ms)
    return page.url, total


async def collect_job_urls(
    page: Page,
    filtered_url: str,
    total: int | None,
    page_size: int,
    max_pages: int | None,
    timeout_ms: int,
    delay: float,
) -> list[str]:
    found: dict[str, None] = {}
    page_number = 1
    while max_pages is None or page_number <= max_pages:
        url = replace_query(filtered_url, current=page_number, limit=page_size)
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            await wait_for_jobs(page, timeout_ms)
        except PlaywrightTimeoutError:
            break

        links = await page.locator('main a[href*="/position/"][href*="/detail"]').evaluate_all(
            "els => els.map(a => a.href.split('?')[0])"
        )
        unique_links = list(dict.fromkeys(links))
        before = len(found)
        found.update(dict.fromkeys(unique_links))
        print(f"[列表] 第 {page_number} 页，本页 {len(unique_links)} 条，累计 {len(found)} 条")

        if not unique_links or len(found) == before or (total is not None and len(found) >= total):
            break
        page_number += 1
        await asyncio.sleep(delay + random.uniform(0, min(delay, 0.5)))
    return list(found)


def load_completed(path: Path) -> dict[str, dict[str, str]]:
    completed: dict[str, dict[str, str]] = {}
    if not path.exists():
        return completed
    with path.open(encoding="utf-8") as file:
        for line in file:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("position_id"):
                completed[str(row["position_id"])] = row
    return completed


async def scrape_details(
    browser: Browser,
    urls: list[str],
    output_jsonl: Path,
    workers: int,
    timeout_ms: int,
    delay: float,
) -> dict[str, dict[str, str]]:
    completed = load_completed(output_jsonl)
    pending = [
        url
        for url in urls
        if (position_id := (re.search(r"/position/(\d+)/", url) or [""])[1])
        not in completed
        or not completed[position_id].get("publish_time")
    ]
    print(f"[详情] 已完成 {len(completed)} 条，待抓取 {len(pending)} 条")
    queue: asyncio.Queue[str] = asyncio.Queue()
    for url in pending:
        queue.put_nowait(url)
    write_lock = asyncio.Lock()
    scraped_count = 0

    async def worker(number: int) -> None:
        nonlocal scraped_count
        page = await browser.new_page()
        try:
            while not queue.empty():
                url = await queue.get()
                try:
                    source_responses: list[str] = []

                    async def capture_source(response: Any) -> None:
                        content_type = (await response.header_value("content-type") or "").lower()
                        if "json" not in content_type:
                            return
                        if not re.search(r"position|job|recruit", response.url, re.I):
                            return
                        try:
                            source_responses.append(await response.text())
                        except PlaywrightError:
                            pass

                    page.on("response", capture_source)
                    await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                    main = page.locator("main")
                    await main.get_by_text("职位要求", exact=True).wait_for(
                        state="visible", timeout=timeout_ms
                    )
                    position_match = re.search(r"/position/(\d+)/detail", page.url)
                    position_id = position_match.group(1) if position_match else ""
                    page_source = await page.content()
                    publish_time = parse_publish_time(page_source, position_id)
                    if not publish_time:
                        publish_time = parse_publish_time("\n".join(source_responses), position_id)
                    row = parse_detail_text(await main.inner_text(), page.url, publish_time)
                    async with write_lock:
                        completed[row["position_id"]] = row
                        with output_jsonl.open("a", encoding="utf-8") as file:
                            file.write(json.dumps(row, ensure_ascii=False) + "\n")
                        scraped_count += 1
                        if scraped_count == 1 or scraped_count % 25 == 0:
                            write_csv(output_jsonl.with_suffix(".csv"), completed)
                        print(f"[详情] {len(completed)} | {row['job_id']} | {row['title']}")
                except Exception as exc:  # 单个失效职位不应中断整个任务
                    print(f"[警告] worker-{number} 抓取失败：{url} ({exc})")
                finally:
                    page.remove_listener("response", capture_source)
                    queue.task_done()
                await asyncio.sleep(delay + random.uniform(0, min(delay, 0.5)))
        finally:
            await page.close()

    await asyncio.gather(*(worker(index + 1) for index in range(workers)))
    return completed


def write_csv(path: Path, rows: dict[str, dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted(rows.values(), key=lambda row: row.get("position_id", "")))


async def run(args: argparse.Namespace) -> None:
    output = Path(args.output)
    jsonl_path = output.with_suffix(".jsonl")
    csv_path = output.with_suffix(".csv")
    output.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(headless=not args.show_browser)
        except PlaywrightError as exc:
            if "Executable doesn't exist" not in str(exc):
                raise
            print("[提示] 未找到 Playwright Chromium，尝试使用本机 Chrome")
            browser = await playwright.chromium.launch(
                channel="chrome", headless=not args.show_browser
            )
        list_page = await browser.new_page()
        try:
            filtered_url, total = await select_development(list_page, args.timeout)
            print(f"[筛选] 研发职位总数：{total if total is not None else '未知'}")
            urls = await collect_job_urls(
                list_page,
                filtered_url,
                total,
                args.page_size,
                args.max_pages,
                args.timeout,
                args.delay,
            )
            rows = await scrape_details(
                browser, urls, jsonl_path, args.workers, args.timeout, args.delay
            )
            write_csv(csv_path, rows)
        finally:
            await list_page.close()
            await browser.close()
    print(f"完成：{len(rows)} 条职位")
    print(f"CSV: {csv_path}")
    print(f"JSONL: {jsonl_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="抓取字节跳动社招研发职位")
    parser.add_argument(
        "--output",
        default="data/raw/bytedance_dev_jobs",
        help="原始数据输出路径（无需扩展名）",
    )
    parser.add_argument("--workers", type=int, default=4, help="详情页并发数")
    parser.add_argument("--page-size", type=int, default=50, help="列表页请求条数")
    parser.add_argument("--delay", type=float, default=0.8, help="每次请求后的基础间隔（秒）")
    parser.add_argument("--timeout", type=int, default=30000, help="页面超时（毫秒）")
    parser.add_argument("--max-pages", type=int, help="只抓前 N 个列表页，便于测试")
    parser.add_argument("--show-browser", action="store_true", help="显示浏览器窗口")
    return parser


if __name__ == "__main__":
    asyncio.run(run(build_parser().parse_args()))

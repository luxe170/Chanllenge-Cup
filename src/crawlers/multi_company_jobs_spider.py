#!/usr/bin/env python3
"""抓取腾讯、阿里、美团和华为公开招聘职位。"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import urlencode

from playwright.async_api import Browser, BrowserContext, Error as PlaywrightError
from playwright.async_api import Page, async_playwright


CHINA_TIMEZONE = timezone(timedelta(hours=8))
FIELDS = [
    "source_platform",
    "company",
    "recruit_type",
    "source_job_id",
    "job_id",
    "title",
    "locations",
    "employment_type",
    "category",
    "publish_time",
    "description",
    "requirement",
    "url",
    "scraped_at",
]
COMPANIES = ("tencent", "alibaba", "meituan", "huawei")


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "、".join(text(item) for item in value if text(item))
    return re.sub(r"[ \t]+", " ", str(value)).strip()


def timestamp(value: Any) -> str:
    """把毫秒时间戳或 ISO 时间转成北京时间字符串。"""
    if value in (None, ""):
        return ""
    raw = str(value)
    if raw.isdigit():
        seconds = int(raw) / (1000 if len(raw) >= 13 else 1)
        parsed = datetime.fromtimestamp(seconds, tz=timezone.utc)
    else:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=CHINA_TIMEZONE)
    return parsed.astimezone(CHINA_TIMEZONE).isoformat(sep=" ", timespec="seconds")


def scraped_at() -> str:
    return datetime.now(CHINA_TIMEZONE).isoformat(sep=" ", timespec="seconds")


def city_names(items: Any) -> str:
    if not isinstance(items, list):
        return text(items)
    return "、".join(text(item.get("name") if isinstance(item, dict) else item) for item in items)


def parse_tencent(item: dict[str, Any]) -> dict[str, str]:
    post_id = text(item.get("PostId"))
    return {
        "source_platform": "tencent_careers",
        "company": "腾讯",
        "recruit_type": "社会招聘",
        "source_job_id": post_id,
        "job_id": text(item.get("RecruitPostId")),
        "title": text(item.get("RecruitPostName")),
        "locations": text(item.get("LocationName")),
        "employment_type": "全职",
        "category": text(item.get("CategoryName")),
        "publish_time": text(item.get("LastUpdateTime")),
        "description": text(item.get("Responsibility")),
        "requirement": text(item.get("Requirement")),
        "url": f"https://careers.tencent.com/jobdesc.html?postId={post_id}",
        "scraped_at": scraped_at(),
    }


def parse_alibaba(item: dict[str, Any]) -> dict[str, str]:
    job_id = text(item.get("id"))
    return {
        "source_platform": "alibaba_campus",
        "company": "阿里巴巴",
        "recruit_type": text(item.get("batchName")) or "校园招聘",
        "source_job_id": job_id,
        "job_id": text(item.get("code")),
        "title": text(item.get("name")),
        "locations": city_names(item.get("workLocations")),
        "employment_type": "实习" if "实习" in text(item.get("batchName")) else "全职",
        "category": text(item.get("categoryName")),
        "publish_time": timestamp(item.get("publishTime") or item.get("modifyTime")),
        "description": text(item.get("description")),
        "requirement": text(item.get("requirement")),
        "url": f"https://campus-talent.alibaba.com/campus/position-detail?positionId={job_id}",
        "scraped_at": scraped_at(),
    }


def parse_meituan(item: dict[str, Any]) -> dict[str, str]:
    job_id = text(item.get("jobUnionId"))
    return {
        "source_platform": "meituan_careers",
        "company": "美团",
        "recruit_type": "校园招聘" if text(item.get("jobType")) == "1" else "社会招聘",
        "source_job_id": job_id,
        "job_id": job_id,
        "title": text(item.get("name")),
        "locations": city_names(item.get("cityList")),
        "employment_type": "全职",
        "category": " - ".join(filter(None, (text(item.get("jobFamily")), text(item.get("jobFamilyGroup"))))),
        "publish_time": timestamp(item.get("refreshTime") or item.get("firstPostTime")),
        "description": text(item.get("jobDuty")),
        "requirement": text(item.get("jobRequirement")),
        "url": f"https://zhaopin.meituan.com/web/position/detail?jobUnionId={job_id}",
        "scraped_at": scraped_at(),
    }


def parse_huawei(item: dict[str, Any]) -> dict[str, str]:
    source_job_id = text(item.get("advertisementsIntegrationId") or item.get("jobId"))
    detail_job_id = text(item.get("jobId") or source_job_id)
    data_source = text(item.get("dataSource") or "1")
    return {
        "source_platform": "huawei_careers",
        "company": "华为",
        "recruit_type": text(item.get("jobType")) or "社会招聘",
        "source_job_id": source_job_id,
        "job_id": text(item.get("advertisementCode") or item.get("positionReqCode")),
        "title": text(item.get("jobname") or item.get("nameCn")),
        "locations": text(item.get("jobArea") or item.get("jobAddress")),
        "employment_type": "全职",
        "category": text(item.get("jobFamilyName")),
        "publish_time": timestamp(item.get("releaseDate") or item.get("creationDate")),
        "description": text(item.get("mainBusiness")),
        "requirement": text(item.get("jobRequire")),
        "url": (
            "https://career.huawei.com/reccampportal/portal5/social-recruitment-detail.html"
            f"?jobId={detail_job_id}&dataSource={data_source}"
        ),
        "scraped_at": scraped_at(),
    }


def valid(row: dict[str, str]) -> bool:
    return all(row.get(key) for key in ("source_job_id", "title", "description", "requirement", "url"))


def load_rows(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as source:
        for line in source:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("source_job_id"):
                rows[str(row["source_job_id"])] = row
    return rows


def write_outputs(base: Path, rows: dict[str, dict[str, str]]) -> None:
    base.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows.values(), key=lambda row: row["source_job_id"])
    with base.with_suffix(".jsonl").open("w", encoding="utf-8") as target:
        for row in ordered:
            target.write(json.dumps(row, ensure_ascii=False) + "\n")
    with base.with_suffix(".csv").open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(ordered)


async def get_json(response: Any) -> dict[str, Any]:
    if not response.ok:
        raise RuntimeError(f"HTTP {response.status}: {response.url}")
    payload = await response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"接口返回的不是 JSON 对象: {response.url}")
    return payload


async def scrape_tencent(context: BrowserContext, max_pages: int | None, page_size: int, delay: float) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    page_no = 1
    while max_pages is None or page_no <= max_pages:
        query = urlencode({"pageIndex": page_no, "pageSize": page_size, "language": "zh-cn", "area": "cn"})
        payload = await get_json(await context.request.get(f"https://careers.tencent.com/tencentcareer/api/post/Query?{query}"))
        data = payload.get("Data") or {}
        items = data.get("Posts") or []
        if not items:
            break
        for item in items:
            post_id = text(item.get("PostId"))
            if post_id and not item.get("Requirement"):
                detail_query = urlencode({"postId": post_id, "language": "zh-cn"})
                detail = await get_json(await context.request.get(
                    f"https://careers.tencent.com/tencentcareer/api/post/ByPostId?{detail_query}"
                ))
                item = detail.get("Data") or item
            rows.append(parse_tencent(item))
        if len(rows) >= int(data.get("Count") or 0):
            break
        page_no += 1
        await asyncio.sleep(delay + random.uniform(0, min(delay, 0.5)))
    return rows


async def bootstrap_csrf(page: Page, url: str) -> str:
    await page.goto(url, wait_until="domcontentloaded")
    meta = page.locator('meta[name="csrf-token"]')
    csrf = await meta.get_attribute("content") if await meta.count() else ""
    if not csrf:
        cookies = await page.context.cookies()
        csrf = next((
            cookie["value"]
            for cookie in cookies
            if "csrf" in cookie["name"].lower() or "xsrf" in cookie["name"].lower()
        ), "")
    if not csrf:
        raise RuntimeError("未能从阿里招聘页获取 CSRF token")
    return csrf


async def scrape_alibaba(page: Page, max_pages: int | None, page_size: int, delay: float) -> list[dict[str, str]]:
    csrf = await bootstrap_csrf(page, "https://campus-talent.alibaba.com/campus/position-list")
    batch_payload = await get_json(await page.request.post(
        f"https://campus-talent.alibaba.com/searchCondition/listBatch?_csrf={csrf}"
    ))
    content = batch_payload.get("content") or []
    batches = content if isinstance(content, list) else content.get("datas", [])
    active = next((item for item in batches if item.get("id")), None)
    batch_id = (active or {}).get("id") or 100000560002
    rows: list[dict[str, str]] = []
    page_no = 1
    while max_pages is None or page_no <= max_pages:
        body = {"batchId": batch_id, "pageIndex": page_no, "pageSize": page_size, "customDeptCode": "", "channel": "campus_group_official_site", "language": "zh"}
        payload = await get_json(await page.request.post(
            f"https://campus-talent.alibaba.com/position/search?_csrf={csrf}", data=body
        ))
        content = payload.get("content") or {}
        items = content.get("datas") or []
        if not items:
            break
        rows.extend(parse_alibaba(item) for item in items)
        total = int(content.get("total") or content.get("totalCount") or 0)
        if total and len(rows) >= total:
            break
        page_no += 1
        await asyncio.sleep(delay + random.uniform(0, min(delay, 0.5)))
    return rows


async def scrape_meituan(page: Page, max_pages: int | None, page_size: int, delay: float) -> list[dict[str, str]]:
    await page.goto("https://zhaopin.meituan.com/web/position?hiringType=1", wait_until="domcontentloaded")
    rows: list[dict[str, str]] = []
    page_no = 1
    while max_pages is None or page_no <= max_pages:
        body = {"page": {"pageNo": page_no, "pageSize": page_size}, "jobShareType": "1", "keywords": "", "cityList": [], "department": [], "jfJgList": [], "jobType": [{"code": "1", "subCode": []}], "typeCode": [], "specialCode": []}
        payload = await get_json(await page.request.post(
            "https://zhaopin.meituan.com/api/official/job/getJobList", data=body
        ))
        data = payload.get("data") or {}
        items = data.get("list") or []
        if not items:
            break
        rows.extend(parse_meituan(item) for item in items)
        pagination = data.get("page") or {}
        total = int(data.get("total") or data.get("totalCount") or pagination.get("totalCount") or 0)
        if total and len(rows) >= total:
            break
        page_no += 1
        await asyncio.sleep(delay + random.uniform(0, min(delay, 0.5)))
    return rows


async def scrape_huawei(context: BrowserContext, max_pages: int | None, page_size: int, delay: float) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    page_no = 1
    while max_pages is None or page_no <= max_pages:
        params = {
            "curPage": page_no,
            "pageSize": page_size,
            "jobFamilyCode": "",
            "deptCode": "",
            "keywords": "",
            "searchType": 1,
            "orderBy": "P_COUNT_DESC",
            "jobType": 1,
        }
        query = urlencode(params)
        url = (
            "https://career.huawei.com/reccampportal/services/portal/portalpub/getJob/newHr/page/"
            f"{page_size}/{page_no}?{query}"
        )
        headers = {
            "Referer": "https://career.huawei.com/reccampportal/portal5/social-recruitment.html",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }
        payload = await get_json(await context.request.get(url, headers=headers))
        items = payload.get("result") or []
        if not items:
            break
        rows.extend(parse_huawei(item) for item in items)
        total_pages = int((payload.get("pageVO") or {}).get("totalPages") or 0)
        if total_pages and page_no >= total_pages:
            break
        page_no += 1
        await asyncio.sleep(delay + random.uniform(0, min(delay, 0.5)))
    return rows


SCRAPERS: dict[str, Callable[..., Awaitable[list[dict[str, str]]]]] = {}


async def run(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir)
    async with async_playwright() as playwright:
        try:
            browser: Browser = await playwright.chromium.launch(headless=not args.show_browser)
        except PlaywrightError:
            browser = await playwright.chromium.launch(channel="chrome", headless=not args.show_browser)
        context = await browser.new_context(locale="zh-CN")
        page = await context.new_page()
        try:
            for company in args.companies:
                print(f"[{company}] 开始抓取")
                if company == "tencent":
                    fresh = await scrape_tencent(context, args.max_pages, args.page_size, args.delay)
                elif company == "alibaba":
                    fresh = await scrape_alibaba(page, args.max_pages, args.page_size, args.delay)
                elif company == "meituan":
                    fresh = await scrape_meituan(page, args.max_pages, args.page_size, args.delay)
                else:
                    fresh = await scrape_huawei(context, args.max_pages, args.page_size, args.delay)
                base = output_dir / f"{company}_jobs"
                rows = load_rows(base.with_suffix(".jsonl"))
                accepted = [row for row in fresh if valid(row)]
                rows.update((row["source_job_id"], row) for row in accepted)
                write_outputs(base, rows)
                print(f"[{company}] 本次有效 {len(accepted)} 条，累计 {len(rows)} 条")
        finally:
            await context.close()
            await browser.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--companies", nargs="+", choices=COMPANIES, default=list(COMPANIES), help="要抓取的公司")
    parser.add_argument("--output-dir", default="data/raw", help="输出目录")
    parser.add_argument("--page-size", type=int, default=10, help="每页职位数")
    parser.add_argument("--max-pages", type=int, help="每家公司最多抓取页数")
    parser.add_argument("--delay", type=float, default=1.0, help="翻页间隔秒数")
    parser.add_argument("--show-browser", action="store_true", help="显示浏览器")
    return parser


if __name__ == "__main__":
    asyncio.run(run(build_parser().parse_args()))

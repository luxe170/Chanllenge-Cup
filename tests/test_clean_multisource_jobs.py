import unittest

from src.processing.clean_multisource_jobs import classify_records, normalize_record


def make_record(**changes: str) -> dict[str, str]:
    record = {
        "source_platform": "tencent_careers",
        "company": "腾讯",
        "recruit_type": "社会招聘",
        "source_job_id": "1554352375597113344",
        "job_id": "92143",
        "title": "操作系统高级研发工程师",
        "locations": "深圳",
        "employment_type": "全职",
        "category": "技术",
        "publish_time": "2026年07月08日",
        "description": "负责操作系统基础软件研发",
        "requirement": "精通 C/C++、Python",
        "url": "https://careers.tencent.com/jobdesc.html?postId=1554352375597113344",
        "scraped_at": "2026-08-01 15:23:18+08:00",
    }
    record.update(changes)
    return record


class CleanMultisourceJobsTest(unittest.TestCase):
    def test_normalizes_source_id_and_time(self) -> None:
        cleaned = normalize_record(make_record())

        self.assertEqual(cleaned["source_id"], "tencent_careers:1554352375597113344")
        self.assertEqual(cleaned["publish_time"], "2026-07-08 00:00:00+08:00")
        self.assertEqual(cleaned["url"], "https://careers.tencent.com/jobdesc.html")

    def test_keeps_technical_roles_as_relevant(self) -> None:
        relevant, review, rejected, report = classify_records([(1, "tencent_jobs.jsonl", make_record())])

        self.assertEqual(len(relevant), 1)
        self.assertEqual(review, [])
        self.assertEqual(rejected, [])
        self.assertEqual(report["status_relevant_records"], 1)

    def test_marks_product_manager_as_review(self) -> None:
        record = make_record(
            title="AI产品经理",
            category="产品类 - 产品,硬件产品",
            description="负责AI产品规划",
            requirement="有AI产品实践",
        )

        relevant, review, rejected, _ = classify_records([(1, "meituan_jobs.jsonl", record)])

        self.assertEqual(relevant, [])
        self.assertEqual(len(review), 1)
        self.assertEqual(rejected, [])
        self.assertEqual(review[0]["source_status"], "review")

    def test_keeps_mixed_chinese_jd_with_english_terms(self) -> None:
        record = make_record(
            title="AI Agent算法工程师",
            description="负责 Agent 系统研发和大模型后训练",
            requirement="熟悉 Python、LLM、RLHF",
        )

        relevant, review, rejected, _ = classify_records([(1, "alibaba_jobs.jsonl", record)])

        self.assertEqual(len(relevant), 1)
        self.assertEqual(review, [])
        self.assertEqual(rejected, [])

    def test_rejects_jd_without_chinese_text(self) -> None:
        record = make_record(
            title="AI Agent Engineer",
            description="Build agent workflows and LLM applications.",
            requirement="Python, LangChain, RLHF experience.",
        )

        relevant, review, rejected, report = classify_records([(1, "english_jobs.jsonl", record)])

        self.assertEqual(relevant, [])
        self.assertEqual(review, [])
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["reason"], "rejected:non_chinese_jd")
        self.assertEqual(report["status_rejected_records"], 1)

    def test_rejects_sales_and_legal_roles(self) -> None:
        sales = make_record(
            title="腾讯云汽车行业高级大客户销售经理",
            category="销售、服务与支持",
            description="负责销售/客户管理工作",
            requirement="3年及以上KA销售经验",
            source_job_id="1610171352088584192",
        )
        legal = make_record(
            source_platform="huawei_careers",
            company="华为",
            source_job_id="205629",
            title="法务综合专员",
            category="法务与合规族",
            description="负责合同法律审核",
            requirement="法律专业本科以上学历",
            url="https://career.huawei.com/reccampportal/portal5/social-recruitment-detail.html?jobId=30236&dataSource=1",
        )

        relevant, review, rejected, report = classify_records(
            [
                (1, "tencent_jobs.jsonl", sales),
                (2, "huawei_jobs.jsonl", legal),
            ]
        )

        self.assertEqual(relevant, [])
        self.assertEqual(review, [])
        self.assertEqual(len(rejected), 2)
        self.assertEqual(report["status_rejected_records"], 2)


if __name__ == "__main__":
    unittest.main()

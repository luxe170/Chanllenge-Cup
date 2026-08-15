import unittest

from src.crawlers.multi_company_jobs_spider import (
    parse_alibaba,
    parse_huawei,
    parse_meituan,
    parse_tencent,
    timestamp,
    valid,
)


class MultiCompanyParserTest(unittest.TestCase):
    def test_timestamp_converts_milliseconds(self) -> None:
        self.assertEqual(timestamp(1717041600000), "2024-05-30 12:00:00+08:00")

    def test_parses_tencent(self) -> None:
        row = parse_tencent({"PostId": "1", "RecruitPostName": "后端工程师", "LocationName": "深圳", "Responsibility": "职责", "Requirement": "要求"})
        self.assertEqual(row["company"], "腾讯")
        self.assertEqual(row["source_job_id"], "1")
        self.assertTrue(valid(row))

    def test_parses_alibaba(self) -> None:
        row = parse_alibaba({"id": 2, "name": "算法实习生", "batchName": "日常实习", "workLocations": ["杭州"], "description": "职责", "requirement": "要求"})
        self.assertEqual(row["employment_type"], "实习")
        self.assertEqual(row["locations"], "杭州")

    def test_parses_meituan(self) -> None:
        row = parse_meituan({"jobUnionId": "3", "name": "研发工程师", "cityList": [{"name": "北京"}], "jobDuty": "职责", "jobRequirement": "要求"})
        self.assertEqual(row["locations"], "北京")

    def test_parses_huawei(self) -> None:
        row = parse_huawei({"advertisementsIntegrationId": 4, "jobname": "AI工程师", "jobArea": "中国/上海", "mainBusiness": "职责", "jobRequire": "要求"})
        self.assertEqual(row["company"], "华为")
        self.assertIn("jobId=4", row["url"])
        self.assertIn("dataSource=1", row["url"])


if __name__ == "__main__":
    unittest.main()

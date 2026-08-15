import unittest

from src.processing.clean_job_postings import clean_record, clean_records


def make_record(**changes: str) -> dict[str, str]:
    record = {
        "position_id": "123",
        "job_id": "A123",
        "title": " 后端\t开发工程师 ",
        "locations": "北京",
        "employment_type": "正式",
        "category": "研发 - 后端",
        "publish_time": "2026-07-01T12:30:00+08:00",
        "description": "职责一  \r\n\r\n职责二",
        "requirement": "要求一\n要求二",
        "url": "https://jobs.example/position/123?tracking=1#top",
    }
    record.update(changes)
    return record


class CleanRecordTest(unittest.TestCase):
    def test_normalizes_fields_and_builds_stable_source_id(self) -> None:
        cleaned = clean_record(make_record())

        self.assertEqual(cleaned["source_id"], "bytedance:123")
        self.assertEqual(cleaned["title"], "后端 开发工程师")
        self.assertEqual(cleaned["description"], "职责一\n职责二")
        self.assertEqual(cleaned["publish_time"], "2026-07-01 12:30:00+08:00")
        self.assertEqual(cleaned["url"], "https://jobs.example/position/123")

    def test_rejects_record_missing_core_text(self) -> None:
        accepted, rejected, report = clean_records(
            [(1, make_record(description="", requirement=""))]
        )

        self.assertEqual(accepted, [])
        self.assertEqual(report["rejected_records"], 1)
        self.assertIn("description", rejected[0]["reason"])
        self.assertIn("requirement", rejected[0]["reason"])

    def test_keeps_cross_postings_and_marks_duplicate_content(self) -> None:
        records = [
            (1, make_record()),
            (2, make_record(position_id="456", locations="上海")),
        ]

        accepted, _, report = clean_records(records)

        self.assertEqual(len(accepted), 2)
        self.assertEqual(report["duplicate_content_records_retained"], 2)
        self.assertTrue(all(row["duplicate_group_id"] for row in accepted))
        self.assertTrue(all("duplicate_content" in row["quality_flags"] for row in accepted))

    def test_removes_duplicate_source_id_and_keeps_better_record(self) -> None:
        records = [
            (1, make_record(publish_time="", description="短")),
            (2, make_record(description="更完整的岗位职责")),
        ]

        accepted, _, report = clean_records(records)

        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0]["description"], "更完整的岗位职责")
        self.assertEqual(report["duplicate_source_records_removed"], 1)


if __name__ == "__main__":
    unittest.main()

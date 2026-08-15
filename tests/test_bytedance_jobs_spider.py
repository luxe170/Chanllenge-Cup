import unittest

from src.crawlers.bytedance_jobs_spider import parse_publish_time


class ParsePublishTimeTest(unittest.TestCase):
    def test_extracts_millisecond_timestamp_near_position(self) -> None:
        source = (
            '{"id":"other","publishTime":1783081546229}'
            '{"id":"6704247954808506628","publish_time":1717041600000}'
        )

        self.assertEqual(
            parse_publish_time(source, "6704247954808506628"),
            "2024-05-30 12:00:00+08:00",
        )

    def test_returns_empty_when_source_has_no_publish_time(self) -> None:
        self.assertEqual(parse_publish_time('{"id":"123"}', "123"), "")

    def test_ignores_publish_time_from_unrelated_source(self) -> None:
        self.assertEqual(parse_publish_time('{"publishTime":1783081546229}', "123"), "")


if __name__ == "__main__":
    unittest.main()

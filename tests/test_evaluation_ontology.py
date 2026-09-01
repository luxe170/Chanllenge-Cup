from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "data" / "evaluation" / "ontology"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class EvaluationOntologyTest(unittest.TestCase):
    def test_registry_ids_names_and_aliases_are_unique(self) -> None:
        for entity in ("position", "skill"):
            registry = read_jsonl(ONTOLOGY / f"{entity}_registry_v1.jsonl")
            aliases = read_jsonl(ONTOLOGY / f"{entity}_aliases_v1.jsonl")
            self.assertEqual(len(registry), len({row["id"] for row in registry}))
            self.assertEqual(len(registry), len({row["normalized_name"] for row in registry}))
            self.assertEqual(len(aliases), len({row["normalized_alias"] for row in aliases}))
            valid_ids = {row["id"] for row in registry}
            self.assertTrue(all(row[f"{entity}_id"] in valid_ids for row in aliases))

    def test_skill_parents_exist(self) -> None:
        skills = read_jsonl(ONTOLOGY / "skill_registry_v1.jsonl")
        ids = {row["id"] for row in skills}
        self.assertTrue(all(not row["parent_skill_id"] or row["parent_skill_id"] in ids for row in skills))

    def test_all_ground_truth_entities_reference_registries(self) -> None:
        positions = {row["id"] for row in read_jsonl(ONTOLOGY / "position_registry_v1.jsonl")}
        skills = {row["id"] for row in read_jsonl(ONTOLOGY / "skill_registry_v1.jsonl")}
        ground_truth = read_jsonl(ROOT / "data" / "evaluation" / "jd_ground_truth_normalized_120_v1.jsonl")
        self.assertEqual(len(ground_truth), 120)
        self.assertTrue(all(row["annotation"]["position_id"] in positions for row in ground_truth))
        self.assertTrue(
            all(skill["skill_id"] in skills for row in ground_truth for skill in row["annotation"]["skills"])
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from backend.app.services.match_service import _align_resume_skills, _build_match_report, _llm_fit_guidance


class FakeAlignmentClient:
    model = "fake-aligner"

    def complete_json(self, system_prompt: str, payload: dict) -> dict:
        return {"alignments": [
            {"rawName": "Spring Boot", "standardSkillId": "skill_spring", "confidence": .96, "reason": "框架同类"},
            {"rawName": "Java", "standardSkillId": "skill_java", "confidence": .99, "reason": "完全一致"},
            {"rawName": "不存在", "standardSkillId": "skill_java", "confidence": 1, "reason": "应被过滤"},
        ]}


class FakeGuidanceClient:
    model = "fake-adviser"

    def complete_json(self, system_prompt: str, payload: dict) -> dict:
        self.payload = payload
        return {"summary": "Java基础匹配，需补齐工程证据。", "suggestions": ["补充可量化的并发项目结果"], "learningPath": [{"stage": 1, "title": "补齐后端工程证据", "duration": "2周", "skills": ["Spring 框架"], "goal": "完成压测报告"}]}


class MatchLlmPipelineTest(unittest.TestCase):
    def test_alignment_then_formula_then_guidance(self) -> None:
        profile = {"candidateName": "测试者", "skills": [{"name": "Spring Boot", "level": "掌握"}, {"name": "Java", "level": "掌握"}], "experiences": []}
        alignment = _align_resume_skills(profile, FakeAlignmentClient())
        self.assertEqual({item["standardSkillId"] for item in alignment}, {"skill_spring", "skill_java"})
        report = _build_match_report("test", profile, "pos_java_engineer", persist=False, aligned_skills=alignment)
        self.assertGreaterEqual(report["overallScore"], 0)
        self.assertEqual(report["skillAlignment"], alignment)
        client = FakeGuidanceClient()
        guidance = _llm_fit_guidance(profile, report, client)
        self.assertEqual(guidance["summary"], "Java基础匹配，需补齐工程证据。")
        self.assertEqual(guidance["learningPath"][0]["goal"], "完成压测报告")
        self.assertEqual(guidance["guidanceSource"], "llm")
        self.assertEqual(guidance["suggestions"][0], "补充可量化的并发项目结果")


if __name__ == "__main__":
    unittest.main()

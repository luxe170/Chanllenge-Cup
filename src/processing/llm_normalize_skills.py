from __future__ import annotations

from src.processing.llm_offline_boundary import run_boundary_script


if __name__ == "__main__":
    run_boundary_script("Skill normalization", "skill_normalization.jsonl")

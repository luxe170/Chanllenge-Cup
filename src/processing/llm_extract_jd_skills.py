from __future__ import annotations

from src.processing.llm_offline_boundary import run_boundary_script


if __name__ == "__main__":
    run_boundary_script("JD skill extraction", "llm_skill_mentions.jsonl")

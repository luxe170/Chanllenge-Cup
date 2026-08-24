from __future__ import annotations

import argparse
from pathlib import Path

from backend.app.services.data_sources import write_jsonl


def run_boundary_script(name: str, output_filename: str) -> None:
    parser = argparse.ArgumentParser(description=f"{name} offline enhancement placeholder.")
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument(
        "--write-empty",
        action="store_true",
        help="Write an empty JSONL output file so downstream readers can be wired without online LLM calls.",
    )
    args = parser.parse_args()

    if args.write_empty:
        write_jsonl(args.output_dir / output_filename, [])
        print(f"{name}: wrote empty {output_filename}; no online LLM was called")
        return
    print(f"{name}: offline LLM enhancement is not enabled; no online LLM was called")

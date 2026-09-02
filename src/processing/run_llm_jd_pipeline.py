from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.services.data_sources import project_root, read_jsonl, write_jsonl
from src.evaluation.evaluate_jd_parser import evaluate_jd_parser
from src.llm_client import ChatCompletionsClient, llm_config_status
from src.processing.build_graph_seed import build_graph_seed
from src.processing.llm_extract_jd_skills import (
    DEFAULT_OUTPUT,
    DEFAULT_TEST_OUTPUT,
    extract_default_splits_with_llm,
)


RUN_LABEL = "LLM runs"
DEFAULT_RUN_DIR = project_root() / "data" / "processed" / "llm_runs"


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_graph_from_predictions(predictions: list[dict[str, Any]], output_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    train_predictions = [item for item in predictions if item.get("split") == "graph_train"]
    nodes, edges = build_graph_seed(predictions=train_predictions, split="graph_train")
    write_jsonl(output_dir / "graph_nodes.jsonl", nodes)
    write_jsonl(output_dir / "graph_edges.jsonl", edges)
    return nodes, edges


def run_llm_jd_pipeline(
    *,
    output_dir: Path = DEFAULT_RUN_DIR,
    extraction_output: Path = DEFAULT_OUTPUT,
    test_prediction_output: Path = DEFAULT_TEST_OUTPUT,
    report_output: Path | None = None,
    batch_size: int = 5,
    limit_per_split: int | None = None,
    timeout: int = 90,
    retries: int = 2,
    verbose: bool = True,
    splits: list[str] | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_output = report_output or output_dir / "llm_jd_evaluation_report.json"
    client = ChatCompletionsClient.from_env(timeout=timeout, retries=retries)
    predictions = extract_default_splits_with_llm(
        extraction_output,
        client,
        test_output_path=test_prediction_output,
        batch_size=batch_size,
        limit_per_split=limit_per_split,
        verbose=verbose,
        splits=splits,
        resume=True,
    )
    nodes, edges = _write_graph_from_predictions(predictions, output_dir)
    report = evaluate_jd_parser(
        project_root() / "data" / "processed" / "splits" / "jd_test_set_100.jsonl",
        project_root() / "data" / "processed" / "evaluation" / "jd_gold_labels.jsonl",
        report_output,
        test_prediction_output,
        predictions_input_path=test_prediction_output,
        run_label=RUN_LABEL,
    )
    manifest = {
        "runLabel": RUN_LABEL,
        "generatedAt": _generated_at(),
        "llmConfig": llm_config_status(),
        "outputs": {
            "extractionPredictions": str(extraction_output),
            "testPredictions": str(test_prediction_output),
            "graphNodes": str(output_dir / "graph_nodes.jsonl"),
            "graphEdges": str(output_dir / "graph_edges.jsonl"),
            "evaluationReport": str(report_output),
        },
        "counts": {
            "predictionCount": len(predictions),
            "graphNodeCount": len(nodes),
            "graphEdgeCount": len(edges),
            "evaluatedCount": report["sampleCount"],
        },
        "metrics": {
            "overallAccuracy": report["overallAccuracy"],
            "positionAccuracy": report["positionAccuracy"],
            "skillF1": report["skillF1"],
        },
    }
    (output_dir / "LLM_RUN_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LLM JD extraction, graph, and evaluation pipeline.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--extraction-output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--test-output", type=Path, default=DEFAULT_TEST_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=None)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--limit-per-split", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--splits", default="", help="Comma-separated split names: graph_train,jd_test,holdout.")
    args = parser.parse_args()
    manifest = run_llm_jd_pipeline(
        output_dir=args.output_dir,
        extraction_output=args.extraction_output,
        test_prediction_output=args.test_output,
        report_output=args.report_output,
        batch_size=args.batch_size,
        limit_per_split=args.limit_per_split,
        timeout=args.timeout,
        retries=args.retries,
        verbose=not args.quiet,
        splits=[item.strip() for item in args.splits.split(",") if item.strip()] or None,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

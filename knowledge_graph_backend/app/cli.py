from __future__ import annotations

import argparse
import json

import uvicorn

from .config import get_settings
from .database import SessionLocal, create_schema
from .models import PipelineRun
from .pipeline import PipelineService
from .runtime import get_graph_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="career-prism-kg", description="Career Prism knowledge graph operations")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db", help="create SQL schema and Neo4j constraints")

    import_command = commands.add_parser("import", help="run the complete CSV-to-graph pipeline")
    import_command.add_argument("--source", default="relevant_jobs.csv", help="CSV path relative to IMPORT_ROOT")
    import_command.add_argument("--window-days", type=int)
    import_command.add_argument("--window-end", help="YYYY-MM-DD")
    import_command.add_argument("--min-sample-count", type=int)

    show = commands.add_parser("show-run", help="print a pipeline run")
    show.add_argument("run_id")

    worker = commands.add_parser("worker", help="process durable queued pipeline runs")
    worker.add_argument("--poll-seconds", type=float, default=2.0)
    worker.add_argument("--once", action="store_true")

    serve = commands.add_parser("serve", help="run the API server")
    serve.add_argument("--reload", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()
    if args.command == "init-db":
        create_schema()
        graph = get_graph_repository()
        graph.ensure_schema()
        print(json.dumps({"database": "initialized", "graph": graph.health()}, ensure_ascii=False, indent=2))
        return
    if args.command == "import":
        create_schema()
        parameters = {
            key: value
            for key, value in {
                "windowDays": args.window_days,
                "windowEnd": args.window_end,
                "minSampleCount": args.min_sample_count,
            }.items()
            if value is not None
        }
        service = PipelineService(SessionLocal, get_graph_repository(), settings)
        run = service.run_now(args.source, parameters)
        print(json.dumps({"id": run.id, "status": run.status, "statistics": run.statistics, "error": run.error}, ensure_ascii=False, indent=2, default=str))
        return
    if args.command == "show-run":
        with SessionLocal() as session:
            run = session.get(PipelineRun, args.run_id)
            if run is None:
                raise SystemExit(f"run not found: {args.run_id}")
            print(json.dumps({"id": run.id, "status": run.status, "statistics": run.statistics, "error": run.error}, ensure_ascii=False, indent=2, default=str))
        return
    if args.command == "worker":
        create_schema()
        service = PipelineService(SessionLocal, get_graph_repository(), settings)
        service.worker(args.poll_seconds, args.once)
        return
    if args.command == "serve":
        uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=args.reload)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a local SQLite validation database")
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    connection = sqlite3.connect(args.database)
    names = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    output = {
        "tables": {
            name: connection.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
            for name in names
        },
        "reviewTypes": dict(
            connection.execute("SELECT review_type, count(*) FROM review_items GROUP BY review_type")
        ),
        "graphVersions": list(
            connection.execute("SELECT id, node_count, edge_count, status FROM graph_versions")
        ),
        "positionMentionStatus": dict(
            connection.execute("SELECT status, count(*) FROM position_mentions GROUP BY status")
        ),
    }
    candidates = []
    for title, payload, confidence in connection.execute(
        "SELECT title, payload, confidence FROM review_items WHERE review_type='new_position'"
    ):
        parsed = json.loads(payload)
        candidates.append(
            {
                "title": title,
                "sampleCount": parsed.get("sampleCount", 0),
                "sourceCount": parsed.get("sourceCount", 0),
                "confidence": confidence,
            }
        )
    output["topNewPositionCandidates"] = sorted(
        candidates,
        key=lambda item: (item["sampleCount"], item["sourceCount"], item["confidence"]),
        reverse=True,
    )[:10]
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

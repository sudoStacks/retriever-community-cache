#!/usr/bin/env python3
"""Generate or verify stats/dataset.json from repository dataset files."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schema" / "schema.json"
STATS_PATH = ROOT / "stats" / "dataset.json"
DATA_ROOTS = (
    ROOT / "youtube" / "recording",
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_schema_version() -> int:
    schema = _load_json(SCHEMA_PATH)
    value = (
        schema.get("properties", {})
        .get("schema_version", {})
        .get("const")
    )
    if not isinstance(value, int):
        raise ValueError("Unable to determine schema_version const from schema/schema.json")
    return value


def compute_stats() -> dict:
    unique_recordings: set[str] = set()
    youtube_sources = 0

    for data_root in DATA_ROOTS:
        if not data_root.exists():
            continue

        for path in data_root.rglob("*.json"):
            record = _load_json(path)
            mbid = record.get("recording_mbid")
            if isinstance(mbid, str):
                unique_recordings.add(mbid)

            for source in record.get("sources", []):
                if isinstance(source, dict) and source.get("type") == "youtube":
                    youtube_sources += 1

    return {
        "schema_version": _resolve_schema_version(),
        "total_recordings": len(unique_recordings),
        "youtube_sources": youtube_sources,
        "last_updated": datetime.now(timezone.utc).date().isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or validate stats/dataset.json against repository data."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write computed stats to stats/dataset.json.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if stats/dataset.json does not match computed values.",
    )
    args = parser.parse_args()

    if args.write and args.check:
        parser.error("Use only one of --write or --check.")

    computed = compute_stats()

    if args.write:
        STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATS_PATH.write_text(json.dumps(computed, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {STATS_PATH.relative_to(ROOT)}")
        return 0

    if args.check:
        if not STATS_PATH.exists():
            print(f"Missing {STATS_PATH.relative_to(ROOT)}")
            print("Run: python scripts/generate_stats.py --write")
            return 1

        current = _load_json(STATS_PATH)
        if current != computed:
            print("stats/dataset.json is stale.")
            print("Current:")
            print(json.dumps(current, indent=2))
            print("Expected:")
            print(json.dumps(computed, indent=2))
            print("Run: python scripts/generate_stats.py --write")
            return 1

        print("stats/dataset.json matches computed dataset stats.")
        return 0

    print(json.dumps(computed, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Promote proposal JSONL records into sharded dataset files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
YOUTUBE_ROOT = ROOT / "youtube" / "recording"
YOUTUBE_VIDEO_ROOT = ROOT / "youtube" / "video"
SCHEMA_PATH = ROOT / "schema" / "schema.json"

MBID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CHANNEL_TYPES = {"official", "label", "vevo", "topic", "unknown"}
CHANNEL_RANK = {
    "official": 5,
    "label": 4,
    "vevo": 3,
    "topic": 2,
    "unknown": 1,
}


@dataclass
class ProposalResult:
    status: str
    reason: str | None = None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema_version() -> int:
    try:
        schema = _load_json(SCHEMA_PATH)
    except Exception:
        return 1
    value = schema.get("properties", {}).get("schema_version", {}).get("const")
    return value if isinstance(value, int) else 1


def _is_valid_date(value: str) -> bool:
    if not DATE_RE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _validate_proposal(record: Any) -> tuple[bool, str | None]:
    if not isinstance(record, dict):
        return False, "not_object"

    mbid = record.get("recording_mbid")
    if not isinstance(mbid, str) or not MBID_RE.fullmatch(mbid):
        return False, "invalid_recording_mbid"

    if record.get("type") != "youtube":
        return False, "invalid_type"

    video_id = record.get("video_id")
    if not isinstance(video_id, str) or not VIDEO_ID_RE.fullmatch(video_id):
        return False, "invalid_video_id"

    duration_ms = record.get("duration_ms")
    if not isinstance(duration_ms, int) or not (1 <= duration_ms <= 7_200_000):
        return False, "invalid_duration_ms"

    confidence = record.get("confidence")
    if not isinstance(confidence, (int, float)) or not (0 <= float(confidence) <= 1):
        return False, "invalid_confidence"

    verified_at = record.get("verified_at")
    if not isinstance(verified_at, str) or not _is_valid_date(verified_at):
        return False, "invalid_verified_at"

    channel_type = record.get("channel_type")
    if not isinstance(channel_type, str) or channel_type not in CHANNEL_TYPES:
        return False, "invalid_channel_type"

    return True, None


def _source_sort_key(source: dict[str, Any]) -> tuple[float, str]:
    return (-float(source["confidence"]), source["video_id"])


def _merge_source(existing: dict[str, Any], incoming: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    merged = dict(existing)
    changed = False

    # Deterministic merges:
    # confidence -> max, verified_at -> max (ISO date), duration -> latest verified_at wins,
    # channel_type -> highest trust rank.
    max_conf = max(float(existing["confidence"]), float(incoming["confidence"]))
    if float(merged["confidence"]) != max_conf:
        merged["confidence"] = max_conf
        changed = True

    max_verified = max(str(existing["verified_at"]), str(incoming["verified_at"]))
    if merged["verified_at"] != max_verified:
        merged["verified_at"] = max_verified
        changed = True

    incoming_is_newer = str(incoming["verified_at"]) > str(existing["verified_at"])
    if incoming_is_newer and merged["duration_ms"] != incoming["duration_ms"]:
        merged["duration_ms"] = incoming["duration_ms"]
        changed = True

    existing_rank = CHANNEL_RANK.get(str(existing["channel_type"]), 0)
    incoming_rank = CHANNEL_RANK.get(str(incoming["channel_type"]), 0)
    if incoming_rank > existing_rank and merged["channel_type"] != incoming["channel_type"]:
        merged["channel_type"] = incoming["channel_type"]
        changed = True

    return merged, changed


def _target_path(recording_mbid: str) -> Path:
    mbid = recording_mbid.lower()
    return YOUTUBE_ROOT / mbid[:2] / f"{mbid}.json"


def _reverse_target_path(video_id: str) -> Path:
    prefix = video_id[:2].lower()
    return YOUTUBE_VIDEO_ROOT / prefix / f"{video_id}.json"


def _normalize_new_source(proposal: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "youtube",
        "video_id": proposal["video_id"],
        "duration_ms": int(proposal["duration_ms"]),
        "confidence": float(proposal["confidence"]),
        "verified_at": proposal["verified_at"],
        "channel_type": proposal["channel_type"],
    }


def _load_or_init_record(path: Path, recording_mbid: str) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {
            "schema_version": _schema_version(),
            "recording_mbid": recording_mbid,
            "sources": [],
        }, None

    try:
        record = _load_json(path)
    except Exception:
        return {}, "invalid_existing_json"

    if not isinstance(record, dict):
        return {}, "invalid_existing_record"
    if record.get("recording_mbid") != recording_mbid:
        return {}, "existing_mbid_mismatch"

    sources = record.get("sources")
    if not isinstance(sources, list):
        return {}, "invalid_existing_sources"

    return record, None


def _validate_reverse_record(record: Any, video_id: str) -> tuple[dict[str, Any], str | None]:
    if not isinstance(record, dict):
        return {}, "invalid_existing_reverse_index"

    required_keys = {"video_id", "recording_mbid", "confidence", "verified_at"}
    if set(record.keys()) != required_keys:
        return {}, "invalid_existing_reverse_index"

    existing_video_id = record.get("video_id")
    if not isinstance(existing_video_id, str) or existing_video_id != video_id:
        return {}, "invalid_existing_reverse_index"

    mbid = record.get("recording_mbid")
    if not isinstance(mbid, str) or not MBID_RE.fullmatch(mbid):
        return {}, "invalid_existing_reverse_index"

    confidence = record.get("confidence")
    if not isinstance(confidence, (int, float)) or not (0 <= float(confidence) <= 1):
        return {}, "invalid_existing_reverse_index"

    verified_at = record.get("verified_at")
    if not isinstance(verified_at, str) or not _is_valid_date(verified_at):
        return {}, "invalid_existing_reverse_index"

    normalized = {
        "video_id": existing_video_id,
        "recording_mbid": mbid.lower(),
        "confidence": float(confidence),
        "verified_at": verified_at,
    }
    return normalized, None


def _load_existing_reverse(path: Path, video_id: str) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, None

    try:
        record = _load_json(path)
    except Exception:
        return None, "invalid_existing_reverse_index"

    normalized, err = _validate_reverse_record(record, video_id)
    if err is not None:
        return None, err
    return normalized, None


def _merge_reverse_record(
    existing: dict[str, Any] | None,
    recording_mbid: str,
    source: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    if existing is None:
        return {
            "video_id": source["video_id"],
            "recording_mbid": recording_mbid,
            "confidence": float(source["confidence"]),
            "verified_at": source["verified_at"],
        }, True

    merged = dict(existing)
    changed = False

    max_conf = max(float(existing["confidence"]), float(source["confidence"]))
    if float(merged["confidence"]) != max_conf:
        merged["confidence"] = max_conf
        changed = True

    max_verified = max(str(existing["verified_at"]), str(source["verified_at"]))
    if merged["verified_at"] != max_verified:
        merged["verified_at"] = max_verified
        changed = True

    return merged, changed


def _promote_one(proposal: dict[str, Any], dry_run: bool) -> ProposalResult:
    valid, reason = _validate_proposal(proposal)
    if not valid:
        return ProposalResult("skipped", reason=reason)

    recording_mbid = proposal["recording_mbid"].lower()
    source = _normalize_new_source(proposal)
    recording_path = _target_path(recording_mbid)
    reverse_path = _reverse_target_path(source["video_id"])

    existing_reverse, reverse_err = _load_existing_reverse(reverse_path, source["video_id"])
    if reverse_err is not None:
        return ProposalResult("skipped", reason=reverse_err)
    if existing_reverse is not None and existing_reverse["recording_mbid"] != recording_mbid:
        return ProposalResult("skipped", reason="reverse_index_conflict")

    record, load_err = _load_or_init_record(recording_path, recording_mbid)
    if load_err is not None:
        return ProposalResult("skipped", reason=load_err)

    sources: list[dict[str, Any]] = record.get("sources", [])
    existing_idx = None
    for idx, item in enumerate(sources):
        if not isinstance(item, dict):
            return ProposalResult("skipped", reason="invalid_existing_source_entry")
        if item.get("type") == "youtube" and item.get("video_id") == source["video_id"]:
            existing_idx = idx
            break

    record_changed = False
    status = "added"
    if existing_idx is None:
        sources.append(source)
        record_changed = True
    else:
        merged, updated = _merge_source(sources[existing_idx], source)
        if updated:
            sources[existing_idx] = merged
            record_changed = True
            status = "updated"

    sources.sort(key=_source_sort_key)
    record["recording_mbid"] = recording_mbid
    record["schema_version"] = _schema_version()
    record["sources"] = sources

    reverse_record, reverse_changed = _merge_reverse_record(existing_reverse, recording_mbid, source)

    if not record_changed and not reverse_changed:
        return ProposalResult("skipped", reason="no_change")

    if existing_idx is not None and (record_changed or reverse_changed):
        status = "updated"

    if not dry_run:
        if record_changed:
            recording_path.parent.mkdir(parents=True, exist_ok=True)
            recording_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        if reverse_changed:
            reverse_path.parent.mkdir(parents=True, exist_ok=True)
            reverse_path.write_text(json.dumps(reverse_record, indent=2) + "\n", encoding="utf-8")

    return ProposalResult(status=status)


def _iter_jsonl(path: Path) -> tuple[int, dict[str, Any] | None, str | None]:
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except Exception as exc:
            yield line_no, None, f"invalid_jsonl_line: {exc}"
            continue
        if not isinstance(value, dict):
            yield line_no, None, "invalid_jsonl_record_type"
            continue
        yield line_no, value, None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Promote proposal JSONL records into sharded dataset records."
    )
    parser.add_argument(
        "proposal_files",
        nargs="+",
        help="One or more proposal JSONL files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate proposals and print summary without writing files.",
    )
    args = parser.parse_args()

    added = 0
    updated = 0
    skipped = 0
    skipped_reasons: Counter[str] = Counter()

    for proposal_file in args.proposal_files:
        path = Path(proposal_file)
        if not path.exists() or not path.is_file():
            skipped += 1
            skipped_reasons["missing_input_file"] += 1
            print(f"[skip] {proposal_file}: missing input file")
            continue
        if path.suffix != ".jsonl":
            skipped += 1
            skipped_reasons["unsupported_input_format"] += 1
            print(f"[skip] {proposal_file}: expected .jsonl input")
            continue

        for line_no, proposal, parse_error in _iter_jsonl(path):
            if parse_error is not None:
                skipped += 1
                skipped_reasons[parse_error.split(":")[0]] += 1
                print(f"[skip] {proposal_file}:{line_no}: {parse_error}")
                continue

            assert proposal is not None
            result = _promote_one(proposal, dry_run=args.dry_run)
            if result.status == "added":
                added += 1
            elif result.status == "updated":
                updated += 1
            else:
                skipped += 1
                skipped_reasons[result.reason or "unknown"] += 1
                print(f"[skip] {proposal_file}:{line_no}: {result.reason}")

    print("")
    print("Promotion summary")
    print(f"- added: {added}")
    print(f"- updated: {updated}")
    print(f"- skipped: {skipped}")
    if skipped_reasons:
        print("- skipped_reasons:")
        for reason in sorted(skipped_reasons):
            print(f"  - {reason}: {skipped_reasons[reason]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

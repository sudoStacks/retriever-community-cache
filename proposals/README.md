# Proposal Workflow (Human-Gated)

This directory is for candidate mappings produced from verified acquisition outcomes before any dataset inclusion.

No files in `proposals/` are treated as canonical dataset records, and no automation in this repository writes directly to `main` outside pull requests.

## Directory Layout

Use date-based batches:

- `proposals/YYYY-MM-DD/<batch>.jsonl`
- `proposals/YYYY-MM-DD/<batch>.json`

Examples:

- `proposals/2026-03-04/acq-batch-001.jsonl`
- `proposals/2026-03-04/acq-batch-002.json`

## Minimal Proposal Record Contract

Each proposal record should include:

- `recording_mbid`: MusicBrainz recording MBID (UUID)
- `type`: transport type (currently expected: `youtube`)
- `video_id`: provider identifier (YouTube ID for `youtube`)
- `duration_ms`: observed duration in milliseconds
- `confidence`: 0..1 confidence score
- `verified_at`: verification date (`YYYY-MM-DD`)
- `provenance`: object describing where the proposal came from

Recommended `provenance` fields:

- `producer`: tool/system that generated the proposal (for example, `retreivr`)
- `producer_version`: producer version string
- `run_id`: job/run identifier
- `evidence`: short list of matching signals used during verification

## Issue Submission Format (for Trusted Batch Promotion)

Trusted batch automation reads proposals from open GitHub Issues labeled `proposal`.

- Only publishers listed in `.github/trusted_publishers.txt` are processed.
- Use exactly one proposal record per issue.
- Add the `proposal` label to the issue so it is eligible for batch processing.
- Put proposal JSON inside markers:

```md
<!-- proposal:start -->
{
  "recording_mbid": "4b9d0f41-3d5e-4649-8137-9a071f7e9667",
  "type": "youtube",
  "video_id": "dQw4w9WgXcQ",
  "duration_ms": 242000,
  "confidence": 0.97,
  "verified_at": "2026-03-04",
  "channel_type": "official",
  "provenance": {
    "producer": "retreivr",
    "producer_version": "1.2.3",
    "run_id": "acq-20260304-001",
    "evidence": [
      "exact_title_match",
      "artist_match",
      "duration_within_tolerance"
    ]
  }
}
<!-- proposal:end -->
```

If markers are missing, automation falls back to the first fenced `json` code block.

## Review and Promotion Rules

- Proposals are candidate records only.
- Proposal files are syntax-validated in CI, but not schema-validated as canonical dataset entries.
- Maintainers must manually review and promote accepted entries into:
  - `youtube/recording/<prefix>/<recording_mbid>.json`
- Reverse index files under `youtube/video/<prefix>/<video_id>.json` are generated automatically by `scripts/promote_proposals.py`.
- Reverse index files must not be edited manually.
- Promotion must happen via pull request.
- No scheduled or bot-driven auto-write to `main`.

## CI Guardrails

- Dataset files: full schema + path + duplicate checks.
- Dataset stats file is enforced to match computed output.
- Promotion automation runs via `.github/workflows/batch_promote.yml`.

## Maintainer Promotion Tool

Use the local maintainer-side script to consume proposal JSONL files and write dataset records:

```bash
python scripts/promote_proposals.py proposals/2026-03-04/acq-batch-001.jsonl
```

Dry-run mode:

```bash
python scripts/promote_proposals.py --dry-run proposals/2026-03-04/acq-batch-001.jsonl
```

The tool performs basic proposal validation, writes/updates sharded files under `youtube/recording/`, merges existing source entries deterministically, and prints added/updated/skipped counts with skip reasons.

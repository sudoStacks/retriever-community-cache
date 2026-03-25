# Proposal Workflow (Legacy / Optional)

This directory is for candidate mappings produced from verified acquisition outcomes before any dataset inclusion.
It is now a legacy or optional path. The primary Retreivr publisher path is direct dataset branch publication plus trusted-PR validation and auto-merge.

No files in `proposals/` are treated as canonical dataset records.

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
- Maintainers may still review and promote accepted entries into dataset files via pull request.
- The primary automated path is now direct trusted publisher PRs that modify dataset files and pass CI.

## Deterministic Safety Guarantees

Promotion tooling applies deterministic, full-file rewrites:

- Read current record JSON.
- Apply deterministic merge rules.
- Rewrite complete JSON atomically (temporary file + rename), never partial appends.

Deterministic source ordering in each recording file:

- `confidence` descending
- `video_id` ascending

Reverse index constraints:

- One-to-one mapping is enforced for `video_id -> recording_mbid`.
- If a proposal maps an existing `video_id` to a different `recording_mbid`, it is skipped with `reverse_index_conflict`.

Batch size guard:

- Automation enforces a configurable max unique recording writes per run (`MAX_RECORD_WRITES` / `--max-record-writes`).
- Promotion summary always reports `added`, `updated`, `skipped`, and skip reasons.

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

## Automated Proposal Submission

Retreivr can write proposal JSONL files locally, and contributors can automate submission using helper scripts in `scripts/`.

### Prerequisites

1. Install GitHub CLI:

```bash
brew install gh
```

or

```bash
sudo apt install gh
```

2. Authenticate once:

```bash
gh auth login
```

### Outbox location

Default proposal outbox:

- `~/.retreivr/community_outbox`

Override with environment variable:

- `RETREIVR_OUTBOX`

### Scripts

Submit proposals once:

```bash
/bin/sh ./scripts/submit_proposals.sh
```

Install cron automation:

```bash
/bin/sh ./scripts/install_submit_cron.sh
```

Behavior:

- Local proposal `.jsonl` files are submitted as GitHub Issues labeled `proposal`.
- GitHub Actions batch-promotes accepted proposals into the dataset.
- Successfully submitted files are moved to `<outbox>/submitted/`.

Preferred path for automated publishers:

- Retreivr writes canonical dataset files to a trusted branch directly.
- CI validates the dataset contract.
- Trusted same-repo PRs can be auto-merged once checks pass.

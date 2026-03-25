# Retreivr Community Cache

This repository is a transport index dataset for Retreivr.

It stores mappings from canonical MusicBrainz recording MBIDs to known-good transport identifiers.

## Scope

Canonical mapping model:

`recording_mbid -> transport sources`

Examples of transport identifiers:

- YouTube video IDs
- SoundCloud track IDs (future)
- Other supported transport IDs (future)

MusicBrainz remains the authoritative source of metadata. This repository does not replicate MusicBrainz entity metadata.

## Data Layout

Current dataset namespace:

- `youtube/recording/<prefix>/<recording_mbid>.json`

Where:

- `prefix` is the first two characters of `recording_mbid`
- filename stem equals `recording_mbid`

## Record Model

Each record contains:

- `recording_mbid`
- `schema_version`
- `updated_at`
- `sources[]` with transport candidate identifiers and verification fields

See [schema/schema.json](schema/schema.json) for the strict record contract.

## Non-Goals

This repository must not contain:

- scraped metadata dumps
- platform search result dumps
- thumbnails
- ranking heuristics
- MusicBrainz entity metadata copies
- media files or download URLs

## CI Guarantees

Validation in `.github/workflows/validate.yml` enforces:

- JSON parse validity for dataset files
- JSON Schema compliance
- shard-path and filename/MBID consistency
- duplicate MBID prevention in namespace
- duplicate `video_id` prevention within a recording file
- stats integrity via `scripts/generate_stats.py --check`

Trusted PR automation in `.github/workflows/trusted_pr_automerge.yml` enables auto-merge for same-repo pull requests opened by publishers listed in `.github/trusted_publishers.txt`, once required checks pass.
Additional publish policy lives in `.github/publish_policy.json`, including the minimum source confidence floor enforced by CI.

## Purpose

The dataset accelerates transport resolution for Retreivr clients while keeping output deterministic, lightweight, and Git-native.

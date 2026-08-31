# Tender Tracking System

A tender/bid tracking tool — rebuilt as a generalized, open-source system.

Originally built as an internal work tool; this repo is a from-scratch rebuild using
generic, sanitized logic only. No employer-specific data, workflows, or branding.

## Status

🚧 Early development. DB models, config loading, and CLI skeleton are in place.
Scraper implementations, the daily pipeline, and CRM sync are not built yet —
see [open issues](https://github.com/codeapplied/tender-tracking-system/issues)
and the [project board](https://github.com/users/codeapplied/projects/4).

## Architecture

Daily scheduled run → per-source scraper/API client → normalize into a common
`Tender` record → dedupe against the DB → export to Excel → sync to Pipedrive
as deals. Every run is logged to `SyncLog`, which the ops CLI reads for pipeline
health (last run per source, error counts).

## Setup

```
uv venv
uv pip install -e .
cp config/.env.example .env
cp config/portals.example.yaml config/portals.yaml
tendertracker init
```

## CLI

- `tendertracker init` — create the database
- `tendertracker status` — recent sync runs per source
- `tendertracker sources` — list configured portal sources
- `tendertracker run` — run the daily fetch pipeline (not yet implemented)

## License

MIT — see [LICENSE](LICENSE).

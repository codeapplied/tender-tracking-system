# Tender Tracking System

A tender/bid tracking tool — rebuilt as a generalized, open-source system.

Originally built as an internal work tool; this repo is a from-scratch rebuild using
generic, sanitized logic only. No employer-specific data, workflows, or branding.

## Status

🚧 Early development. Core pipeline is complete: DB models, config loading,
CLI, scraper interface, the daily pipeline (normalize/filter/dedupe/store),
Excel export, optional cloud sync (OneDrive/SharePoint), and Pipedrive deal
sync are all in place. Remaining work is calendar sync, cross-system
reconciliation checks, and polish (health CLI, docs, tests) — see
[open issues](https://github.com/codeapplied/tender-tracking-system/issues)
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
- `tendertracker run` — run the daily fetch pipeline. **Plan-only by default**
  (fetches, normalizes, filters, computes what would change, logs the run —
  no DB writes). Pass `--apply` to actually write; on `--apply`, also
  re-syncs the Excel tracker from the DB. This default-safe direction was
  a deliberate choice, not an oversight — see the pipeline module for why.
- `tendertracker export` — regenerate the Excel tracker from current DB
  state without running the full pipeline. Two sheets (Active/Archived,
  split by status), formatted headers, a status dropdown per row, DB is
  always the source of truth — re-running fully regenerates the file. Also
  syncs to OneDrive/SharePoint if configured (see below).
- `tendertracker sync-cloud` — upload the current Excel tracker to
  OneDrive/SharePoint via Microsoft Graph. Optional — skip entirely and the
  tracker stays a local file only. Setup: [docs/CLOUD_SYNC_SETUP.md](docs/CLOUD_SYNC_SETUP.md).
- `tendertracker sync-pipedrive` — create/update Pipedrive deals for tracked
  tenders (org find-or-create, deal, a note with source metadata). **Plan-only
  by default**, `--apply` to write for real. Also runs automatically as part
  of `run --apply` if `PIPEDRIVE_API_TOKEN`/`PIPEDRIVE_DOMAIN` are set —
  silently skipped otherwise, same pattern as cloud sync.

## License

MIT — see [LICENSE](LICENSE).

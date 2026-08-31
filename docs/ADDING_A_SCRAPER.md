# Adding a new tender source

## 1. Decide: public feed, scraped portal, or private aggregator?

Prefer an official API or open-data feed over scraping HTML — see
`scrapers/canadabuys_feed.py` for a real example (a government open-data
CSV). If you must scrape a portal directly, **check its `robots.txt` first**
and treat a blanket `Disallow: /` as a real answer, not an obstacle to route
around — see that same file's docstring for a documented case where the
project deliberately shipped a source disabled-by-default over exactly this
ambiguity, rather than silently deciding either way.

For a private/paid aggregator, copy `scrapers/private_portal_template.py` —
nothing generic can be shipped for these since they're all different, but
the template shows the shape.

## 2. Implement the `Scraper` interface

```python
# src/tendertracker/scrapers/my_portal.py
from typing import Iterator
from .base import RawTender, Scraper

class MyPortalScraper(Scraper):
    name = "my-portal"

    def fetch(self) -> Iterator[RawTender]:
        for raw_record in self._get_records():
            try:
                yield RawTender(
                    source=self.name,
                    external_id=raw_record["id"],       # stable, unique per record
                    title=raw_record["title"],
                    raw=raw_record,                       # full record — normalize() reads from this
                )
            except Exception:
                # log and skip — one bad record must never abort the whole run
                continue
```

Key rules, all covered by existing tests you can pattern-match against
(`tests/test_pipedrive_client.py` for the mocked-HTTP pattern):

- `external_id` must be **stable** across runs for the same record — it's
  the dedup key (`source` + `external_id` is a unique constraint on
  `Tender`). Don't use something that changes on every fetch.
- Never raise out of `fetch()` for a single bad record — catch, log, `continue`.
  The one exception is a genuinely fatal error (e.g. can't reach the source
  at all) — let that propagate, `run_daily.py` isolates it per-source.
- `raw` should keep the *original* record, not a partial extraction —
  `normalize()` is where field mapping happens, not the scraper.

## 3. Add a normalizer

Each source's `raw` dict has its own shape. Add a function in
`pipeline/normalize.py` and register it:

```python
def _normalize_my_portal(raw: RawTender) -> dict:
    data = raw.raw
    return {
        "title": raw.title,
        "description": data.get("description"),
        "category": data.get("category"),
        "organization": data.get("issuing_org"),
        "published_date": parse_date(data.get("published")),
        "closing_date": parse_date(data.get("deadline")),
        "estimated_value": data.get("value"),
        "currency": data.get("currency"),
        "url": data.get("link"),
    }

NORMALIZERS["my-portal"] = _normalize_my_portal
```

If you skip this step, `normalize()` falls back to `_normalize_generic`,
which assumes the sandbox fixture's flat English field names — fine for a
quick test, wrong for anything with a different raw shape.

## 4. Register it in `portals.yaml`

```yaml
portals:
  - name: my-portal
    scraper_class: tendertracker.scrapers.my_portal.MyPortalScraper
    enabled: true
    relevance: # optional — omit entirely for no filtering
      must_match: ["keyword1", "keyword2"]
      boost: ["nice-to-have-keyword"]
      exclude: ["false-positive-keyword"]
```

## 5. Test it

```
tendertracker run          # plan-only — see what it would fetch/store, no writes
tendertracker run --apply  # for real
tendertracker sources      # confirm it's listed and enabled
```

Write a unit test for your normalizer following `tests/test_normalize.py`'s
pattern — a normalizer is pure data mapping, easy to test without touching
the network or the DB.

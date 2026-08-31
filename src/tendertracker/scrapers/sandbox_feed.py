import json
from importlib import resources
from typing import Iterator

from .base import RawTender, Scraper


class SandboxFeedScraper(Scraper):
    """Default example source: a bundled synthetic dataset, not a real portal.

    Zero network calls, zero external site, so there's no robots.txt/ToS
    question at all — the cleanest possible way to prove the scraper
    interface and pipeline work end-to-end. Swap in a real source (see
    canadabuys_feed.py or private_portal_template.py) once you've settled
    your own compliance judgment for whatever you point this at.
    """

    name = "sandbox"

    def fetch(self) -> Iterator[RawTender]:
        data = resources.files("tendertracker.scrapers.fixtures").joinpath("sample_tenders.json")
        records = json.loads(data.read_text(encoding="utf-8"))

        for record in records:
            yield RawTender(
                source=self.name,
                external_id=record["external_id"],
                title=record["title"],
                raw=record,
            )

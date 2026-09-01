import csv
import io
import logging
from typing import Iterator

from ..http_client import get_session
from .base import RawTender, Scraper

logger = logging.getLogger(__name__)

FEED_URL = "https://canadabuys.canada.ca/opendata/pub/newTenderNotice-nouvelAvisAppelOffres.csv"


class CanadaBuysFeedScraper(Scraper):
    """Optional real-data source: the Government of Canada's published
    open-data tender notices feed (CSV, updated roughly every 2 hours, under
    the Open Government Licence - Canada).

    NOT enabled by default. canadabuys.canada.ca's robots.txt has a blanket
    `Disallow: /` for all user-agents other than Googlebot/Bingbot, with no
    specific carve-out for the /opendata/ path this feed lives under — even
    though the file is served from separate Azure Blob Storage infrastructure
    and is explicitly catalogued for reuse on Canada's open-data portal under
    a permissive license. That's a genuine ambiguity between the license's
    intent and the site's robots.txt, not a clear-cut allow. Decide your own
    compliance judgment before enabling this — see `sandbox_feed.py` for the
    zero-ambiguity default this project ships with instead.

    Note on headers: this server 403s a plainly-identifying User-Agent (the
    default below) and only responds to a browser-like one. This class does
    NOT spoof a browser UA by default — pass your own `headers` if you decide
    that's a step you're willing to take; that choice is left to you, not
    made silently by this code.
    """

    name = "canadabuys-open-data"
    DEFAULT_USER_AGENT = (
        "tender-tracking-system/0.1 (open-data fetch; "
        "github.com/codeapplied/tender-tracking-system)"
    )

    def __init__(self, feed_url: str = FEED_URL, timeout: int = 30, headers: dict | None = None) -> None:
        self.feed_url = feed_url
        self.timeout = timeout
        self.headers = headers or {"User-Agent": self.DEFAULT_USER_AGENT}

    def fetch(self) -> Iterator[RawTender]:
        response = get_session().get(self.feed_url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        # utf-8-sig strips the BOM this feed is published with.
        reader = csv.DictReader(io.StringIO(response.content.decode("utf-8-sig")))

        for row in reader:
            try:
                yield self._parse_row(row)
            except Exception:
                logger.warning("Skipping unparseable row from %s", self.name, exc_info=True)
                continue

    def _parse_row(self, row: dict) -> RawTender:
        external_id = (row.get("referenceNumber-numeroReference") or "").strip()
        title = (row.get("title-titre-eng") or "").strip()
        if not external_id or not title:
            raise ValueError("missing required field (reference number or title)")
        return RawTender(source=self.name, external_id=external_id, title=title, raw=row)

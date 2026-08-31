"""Template for a scraper against a private/paid aggregator.

No real vendor is implemented here. Many tender-tracking setups also pull
from paid aggregator services (in addition to public open-data feeds) — but
those integrations are specific to whatever commercial agreement and API/export
format your aggregator provides, so there's nothing generic to ship here.

Copy this file, rename the class, and implement `fetch()` against your own
aggregator's API. Keep credentials in `.env` (see `config/.env.example`),
never hardcoded.
"""

from typing import Iterator

from .base import RawTender, Scraper


class PrivatePortalTemplate(Scraper):
    name = "your-private-portal-name"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def fetch(self) -> Iterator[RawTender]:
        raise NotImplementedError(
            "Implement authentication and parsing against your aggregator's "
            "API or export format here."
        )

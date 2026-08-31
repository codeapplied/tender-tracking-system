from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class RawTender:
    """Unprocessed record as produced by a scraper.

    `normalize.py` (Phase 3) maps this to a `Tender`. `raw` keeps the full
    original record so normalize can pull additional fields it needs without
    every scraper having to promote everything up front.
    """

    source: str
    external_id: str
    title: str
    raw: dict = field(default_factory=dict)


class Scraper(ABC):
    """Interface every portal/feed source implements."""

    name: str

    @abstractmethod
    def fetch(self) -> Iterator[RawTender]:
        """Yield raw tender records from the source.

        Must not raise on a single malformed record — log a warning and skip
        it instead, so one bad row doesn't abort the whole run. Treat a
        source's structure changing as an expected failure mode, not a crash.
        """
        raise NotImplementedError

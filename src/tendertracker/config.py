import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()


@dataclass
class PortalConfig:
    name: str
    scraper_class: str
    enabled: bool = True


@dataclass
class Settings:
    db_path: str
    excel_export_path: str
    pipedrive_api_token: str | None
    pipedrive_domain: str | None


def load_settings() -> Settings:
    return Settings(
        db_path=os.getenv("TENDERTRACKER_DB_PATH", "data/tenders.db"),
        excel_export_path=os.getenv("TENDERTRACKER_EXCEL_PATH", "data/tenders.xlsx"),
        pipedrive_api_token=os.getenv("PIPEDRIVE_API_TOKEN"),
        pipedrive_domain=os.getenv("PIPEDRIVE_DOMAIN"),
    )


def load_portals(config_path: str = "config/portals.yaml") -> list[PortalConfig]:
    path = Path(config_path)
    if not path.exists():
        return []
    with path.open() as f:
        raw = yaml.safe_load(f) or {}
    return [PortalConfig(**p) for p in raw.get("portals", [])]


settings = load_settings()

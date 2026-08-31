import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .pipeline.relevance import RelevanceRules

load_dotenv()


@dataclass
class PortalConfig:
    name: str
    scraper_class: str
    enabled: bool = True
    relevance: RelevanceRules = field(default_factory=RelevanceRules)


@dataclass
class Settings:
    db_path: str
    excel_export_path: str
    pipedrive_api_token: str | None
    pipedrive_domain: str | None
    ms_graph_tenant_id: str | None
    ms_graph_client_id: str | None
    ms_graph_client_secret: str | None
    ms_graph_drive_id: str | None
    ms_graph_upload_path: str
    ms_graph_calendar_user_id: str | None


def load_settings() -> Settings:
    return Settings(
        db_path=os.getenv("TENDERTRACKER_DB_PATH", "data/tenders.db"),
        excel_export_path=os.getenv("TENDERTRACKER_EXCEL_PATH", "data/tenders.xlsx"),
        pipedrive_api_token=os.getenv("PIPEDRIVE_API_TOKEN"),
        pipedrive_domain=os.getenv("PIPEDRIVE_DOMAIN"),
        ms_graph_tenant_id=os.getenv("MS_GRAPH_TENANT_ID"),
        ms_graph_client_id=os.getenv("MS_GRAPH_CLIENT_ID"),
        ms_graph_client_secret=os.getenv("MS_GRAPH_CLIENT_SECRET"),
        ms_graph_drive_id=os.getenv("MS_GRAPH_DRIVE_ID"),
        ms_graph_upload_path=os.getenv("MS_GRAPH_UPLOAD_PATH", "TenderTracker/tenders.xlsx"),
        ms_graph_calendar_user_id=os.getenv("MS_GRAPH_CALENDAR_USER_ID"),
    )


def load_portals(config_path: str = "config/portals.yaml") -> list[PortalConfig]:
    path = Path(config_path)
    if not path.exists():
        return []
    with path.open() as f:
        raw = yaml.safe_load(f) or {}

    portals = []
    for entry in raw.get("portals", []):
        relevance_data = entry.pop("relevance", None) or {}
        portals.append(PortalConfig(relevance=RelevanceRules(**relevance_data), **entry))
    return portals


settings = load_settings()

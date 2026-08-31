from pathlib import Path
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from ..config import Settings

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Simple (single-request) upload only supports files under 4MB — plenty for
# an Excel tracker. A resumable upload session would be needed above that;
# out of scope until something actually needs it.
MAX_SIMPLE_UPLOAD_BYTES = 4 * 1024 * 1024


class OneDriveSyncError(Exception):
    pass


def _get_access_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    """App-only (client credentials) OAuth flow — no signed-in user needed,
    suitable for an unattended daily job. Requires an Azure AD app
    registration with an application (not delegated) Graph permission such
    as Files.ReadWrite.All or Sites.ReadWrite.All, admin-consented. See
    docs/CLOUD_SYNC_SETUP.md."""
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    response = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def sync_file_to_onedrive(
    local_path: str,
    drive_id: str,
    remote_path: str,
    tenant_id: str,
    client_id: str,
    client_secret: str,
) -> dict:
    """Upload local_path to the given drive at remote_path via Graph API
    simple upload. Returns the Graph API response JSON (includes webUrl)."""
    size = Path(local_path).stat().st_size
    if size > MAX_SIMPLE_UPLOAD_BYTES:
        raise OneDriveSyncError(
            f"{local_path} is {size} bytes, over the {MAX_SIMPLE_UPLOAD_BYTES}-byte simple-upload "
            "limit — a resumable upload session would be needed, not implemented."
        )

    token = _get_access_token(tenant_id, client_id, client_secret)
    content = Path(local_path).read_bytes()

    url = f"{GRAPH_BASE}/drives/{drive_id}/root:/{remote_path}:/content"
    response = requests.put(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
        data=content,
        timeout=60,
    )
    if response.status_code not in (200, 201):
        raise OneDriveSyncError(f"Upload failed: {response.status_code} {response.text}")
    return response.json()


def is_configured(settings: "Settings") -> bool:
    return bool(
        settings.ms_graph_tenant_id
        and settings.ms_graph_client_id
        and settings.ms_graph_client_secret
        and settings.ms_graph_drive_id
    )


def sync_excel_if_configured(settings: "Settings") -> dict | None:
    """Returns the Graph API response if a sync happened, or None if cloud
    sync isn't configured — cloud sync is optional, not every user of this
    project wants or needs it."""
    if not is_configured(settings):
        return None
    return sync_file_to_onedrive(
        settings.excel_export_path,
        settings.ms_graph_drive_id,
        settings.ms_graph_upload_path,
        settings.ms_graph_tenant_id,
        settings.ms_graph_client_id,
        settings.ms_graph_client_secret,
    )

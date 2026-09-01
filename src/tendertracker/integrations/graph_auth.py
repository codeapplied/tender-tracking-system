from ..http_client import get_session

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def get_access_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    """App-only (client credentials) OAuth flow — no signed-in user needed,
    suitable for an unattended daily job. Requires an Azure AD app
    registration with the relevant application (not delegated) Graph
    permission, admin-consented. Shared by every Graph-backed integration
    (OneDrive/SharePoint sync, calendar sync) — see docs/CLOUD_SYNC_SETUP.md.

    This is a POST request, so it does not get the automatic retry
    http_client.get_session() gives GET/PUT calls (see that module's
    docstring) — safe to retry in principle (no side effects), but left
    consistent with the rest of the project's POST-is-not-retried policy
    rather than special-cased."""
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    response = get_session().post(
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

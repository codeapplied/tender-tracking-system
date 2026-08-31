from datetime import datetime, timedelta

import requests

from .graph_auth import GRAPH_BASE, get_access_token

EVENT_DURATION = timedelta(hours=1)


class CalendarSyncError(Exception):
    pass


class CalendarClient:
    """Outlook Calendar via Microsoft Graph (app-only auth). Targets a
    specific mailbox by user ID/UPN — app-only auth has no signed-in user,
    so there's no /me/calendar. See docs/CLOUD_SYNC_SETUP.md."""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str, user_id: str, timeout: int = 30) -> None:
        self.token = get_access_token(tenant_id, client_id, client_secret)
        self.user_id = user_id
        self.timeout = timeout

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _event_payload(self, subject: str, start: datetime, body: str) -> dict:
        end = start + EVENT_DURATION
        return {
            "subject": subject,
            "body": {"contentType": "text", "content": body},
            "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
        }

    def create_event(self, subject: str, start: datetime, body: str) -> dict:
        response = requests.post(
            f"{GRAPH_BASE}/users/{self.user_id}/events",
            headers=self._headers(),
            json=self._event_payload(subject, start, body),
            timeout=self.timeout,
        )
        if response.status_code not in (200, 201):
            raise CalendarSyncError(f"Create event failed: {response.status_code} {response.text}")
        return response.json()

    def update_event(self, event_id: str, subject: str, start: datetime, body: str) -> dict:
        response = requests.patch(
            f"{GRAPH_BASE}/users/{self.user_id}/events/{event_id}",
            headers=self._headers(),
            json=self._event_payload(subject, start, body),
            timeout=self.timeout,
        )
        if response.status_code not in (200, 201):
            raise CalendarSyncError(f"Update event failed: {response.status_code} {response.text}")
        return response.json()

    def delete_event(self, event_id: str) -> None:
        response = requests.delete(
            f"{GRAPH_BASE}/users/{self.user_id}/events/{event_id}", headers=self._headers(), timeout=self.timeout
        )
        # 404 is fine here — the event is already gone, which is the desired end state.
        if response.status_code not in (200, 202, 204, 404):
            raise CalendarSyncError(f"Delete event failed: {response.status_code} {response.text}")

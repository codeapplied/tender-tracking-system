from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from tendertracker.integrations.calendar_sync import CalendarClient, CalendarSyncError


@pytest.fixture
def client():
    with patch("tendertracker.integrations.calendar_sync.get_access_token", return_value="FAKE_TOKEN"):
        return CalendarClient("T", "C", "S", "someone@example.com")


def test_create_event_request_shape(client):
    with patch("requests.Session.request") as mock_req:
        mock_req.return_value = MagicMock(status_code=201, json=lambda: {"id": "EVT1"})
        event = client.create_event("Tender closing: X", datetime(2026, 9, 15, 14, 0, 0), "body text")

    assert event["id"] == "EVT1"
    call = mock_req.call_args
    assert call.args[0] == "POST"
    assert call.args[1] == "https://graph.microsoft.com/v1.0/users/someone@example.com/events"
    assert call.kwargs["headers"]["Authorization"] == "Bearer FAKE_TOKEN"
    payload = call.kwargs["json"]
    assert payload["subject"] == "Tender closing: X"
    assert payload["start"]["dateTime"] == "2026-09-15T14:00:00"
    assert payload["end"]["dateTime"] == "2026-09-15T15:00:00"  # +1hr duration


def test_update_event_request_shape(client):
    with patch("requests.Session.request") as mock_req:
        mock_req.return_value = MagicMock(status_code=200, json=lambda: {"id": "EVT1"})
        client.update_event("EVT1", "Updated", datetime(2026, 9, 16, 10, 0, 0), "body")

    call = mock_req.call_args
    assert call.args[0] == "PATCH"
    assert call.args[1] == "https://graph.microsoft.com/v1.0/users/someone@example.com/events/EVT1"


def test_delete_event_request_shape(client):
    with patch("requests.Session.request") as mock_req:
        mock_req.return_value = MagicMock(status_code=204)
        client.delete_event("EVT1")

    call = mock_req.call_args
    assert call.args[0] == "DELETE"
    assert call.args[1] == "https://graph.microsoft.com/v1.0/users/someone@example.com/events/EVT1"


def test_delete_event_tolerates_404():
    """404 on delete means the event is already gone — the desired end
    state — so this must not raise."""
    with patch("tendertracker.integrations.calendar_sync.get_access_token", return_value="TOK"):
        client = CalendarClient("T", "C", "S", "someone@example.com")
    with patch("requests.Session.request") as mock_req:
        mock_req.return_value = MagicMock(status_code=404)
        client.delete_event("EVT1")  # must not raise


def test_create_event_raises_on_failure(client):
    with patch("requests.Session.request") as mock_req:
        mock_req.return_value = MagicMock(status_code=500, text="Server Error")
        with pytest.raises(CalendarSyncError, match="500"):
            client.create_event("X", datetime(2026, 1, 1), "b")

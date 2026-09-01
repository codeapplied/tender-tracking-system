from unittest.mock import MagicMock, patch

import pytest

from tendertracker.integrations.pipedrive import PipedriveClient, PipedriveError


@pytest.fixture
def client():
    return PipedriveClient(api_token="TOK123", domain="mycompany")


def test_find_or_create_organization_returns_existing_match(client):
    with patch("requests.Session.request") as mock_req:
        mock_req.return_value = MagicMock(
            ok=True,
            json=lambda: {"success": True, "data": {"items": [{"item": {"id": 42, "name": "Acme Co"}}]}},
        )
        org_id = client.find_or_create_organization("Acme Co")

    assert org_id == 42
    call = mock_req.call_args
    assert call.args[0] == "GET"
    assert call.args[1] == "https://mycompany.pipedrive.com/api/v1/organizations/search"
    assert call.kwargs["params"]["term"] == "Acme Co"
    assert call.kwargs["params"]["api_token"] == "TOK123"


def test_find_or_create_organization_creates_when_not_found(client):
    def side_effect(method, url, **kwargs):
        if method == "GET":
            return MagicMock(ok=True, json=lambda: {"success": True, "data": {"items": []}})
        return MagicMock(ok=True, json=lambda: {"success": True, "data": {"id": 99}})

    with patch("requests.Session.request", side_effect=side_effect):
        org_id = client.find_or_create_organization("New Org")

    assert org_id == 99


def test_create_deal_request_shape(client):
    with patch("requests.Session.request") as mock_req:
        mock_req.return_value = MagicMock(ok=True, json=lambda: {"success": True, "data": {"id": 7}})
        deal = client.create_deal("Test Deal", org_id=99, value=1000.0, currency="CAD")

    assert deal["id"] == 7
    call = mock_req.call_args
    assert call.args[0] == "POST"
    assert call.args[1] == "https://mycompany.pipedrive.com/api/v1/deals"
    assert call.kwargs["json"] == {"title": "Test Deal", "org_id": 99, "value": 1000.0, "currency": "CAD"}


def test_update_deal_request_shape(client):
    with patch("requests.Session.request") as mock_req:
        mock_req.return_value = MagicMock(ok=True, json=lambda: {"success": True, "data": {"id": 7}})
        client.update_deal(7, "Updated Title", 2000.0, "CAD")

    call = mock_req.call_args
    assert call.args[0] == "PUT"
    assert call.args[1] == "https://mycompany.pipedrive.com/api/v1/deals/7"


def test_add_note_request_shape(client):
    with patch("requests.Session.request") as mock_req:
        mock_req.return_value = MagicMock(ok=True, json=lambda: {"success": True, "data": {}})
        client.add_note(7, "some note")

    call = mock_req.call_args
    assert call.args[0] == "POST"
    assert call.args[1] == "https://mycompany.pipedrive.com/api/v1/notes"
    assert call.kwargs["json"] == {"deal_id": 7, "content": "some note"}


def test_get_deal_request_shape(client):
    with patch("requests.Session.request") as mock_req:
        mock_req.return_value = MagicMock(ok=True, json=lambda: {"success": True, "data": {"id": 7, "title": "X"}})
        deal = client.get_deal(7)

    assert deal["title"] == "X"
    call = mock_req.call_args
    assert call.args[0] == "GET"
    assert call.args[1] == "https://mycompany.pipedrive.com/api/v1/deals/7"


def test_non_ok_response_raises_pipedrive_error(client):
    with patch("requests.Session.request") as mock_req:
        mock_req.return_value = MagicMock(ok=False, status_code=401, text="Unauthorized")
        with pytest.raises(PipedriveError, match="401"):
            client.create_deal("X", None, None, None)


def test_success_false_raises_pipedrive_error(client):
    with patch("requests.Session.request") as mock_req:
        mock_req.return_value = MagicMock(ok=True, json=lambda: {"success": False, "error": "bad request"})
        with pytest.raises(PipedriveError, match="success=false"):
            client.create_deal("X", None, None, None)

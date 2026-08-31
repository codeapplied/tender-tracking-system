from unittest.mock import MagicMock, patch

import pytest

from tendertracker.integrations.onedrive_sync import (
    OneDriveSyncError,
    is_configured,
    sync_excel_if_configured,
    sync_file_to_onedrive,
)


def test_is_configured_false_when_missing_any_var(tmp_settings):
    assert is_configured(tmp_settings) is False


def test_is_configured_true_when_all_set(tmp_settings):
    tmp_settings.ms_graph_tenant_id = "t"
    tmp_settings.ms_graph_client_id = "c"
    tmp_settings.ms_graph_client_secret = "s"
    tmp_settings.ms_graph_drive_id = "d"
    assert is_configured(tmp_settings) is True


def test_sync_excel_if_configured_returns_none_when_not_configured(tmp_settings):
    assert sync_excel_if_configured(tmp_settings) is None


def test_sync_file_to_onedrive_request_shape(tmp_path):
    local_file = tmp_path / "tenders.xlsx"
    local_file.write_bytes(b"fake-excel-bytes")

    with patch("tendertracker.integrations.onedrive_sync.get_access_token", return_value="FAKE_TOKEN"), patch(
        "tendertracker.integrations.onedrive_sync.requests.put"
    ) as mock_put:
        mock_put.return_value = MagicMock(
            status_code=201, json=lambda: {"webUrl": "https://example.sharepoint.com/fake"}
        )
        result = sync_file_to_onedrive(
            str(local_file),
            drive_id="DRIVE123",
            remote_path="TenderTracker/tenders.xlsx",
            tenant_id="T",
            client_id="C",
            client_secret="S",
        )

    assert result == {"webUrl": "https://example.sharepoint.com/fake"}
    call = mock_put.call_args
    assert call.args[0] == "https://graph.microsoft.com/v1.0/drives/DRIVE123/root:/TenderTracker/tenders.xlsx:/content"
    assert call.kwargs["headers"]["Authorization"] == "Bearer FAKE_TOKEN"
    assert call.kwargs["data"] == b"fake-excel-bytes"


def test_sync_file_to_onedrive_raises_over_size_limit(tmp_path):
    local_file = tmp_path / "big.xlsx"
    local_file.write_bytes(b"x" * (5 * 1024 * 1024))  # 5MB, over the 4MB simple-upload limit

    with pytest.raises(OneDriveSyncError, match="simple-upload"):
        sync_file_to_onedrive(str(local_file), "D", "p", "T", "C", "S")


def test_sync_file_to_onedrive_raises_on_failed_upload(tmp_path):
    local_file = tmp_path / "tenders.xlsx"
    local_file.write_bytes(b"data")

    with patch("tendertracker.integrations.onedrive_sync.get_access_token", return_value="TOK"), patch(
        "tendertracker.integrations.onedrive_sync.requests.put"
    ) as mock_put:
        mock_put.return_value = MagicMock(status_code=403, text="Forbidden")
        with pytest.raises(OneDriveSyncError, match="403"):
            sync_file_to_onedrive(str(local_file), "D", "p", "T", "C", "S")

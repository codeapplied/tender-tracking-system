from tendertracker.http_client import get_session


def test_session_has_retry_adapter_mounted_for_both_schemes():
    session = get_session()
    https_adapter = session.get_adapter("https://example.com")
    http_adapter = session.get_adapter("http://example.com")
    assert https_adapter.max_retries.total == 3
    assert http_adapter.max_retries.total == 3


def test_retry_config_matches_documented_policy():
    session = get_session(total_retries=5, backoff_factor=1.0)
    retry = session.get_adapter("https://example.com").max_retries
    assert retry.total == 5
    assert retry.backoff_factor == 1.0
    assert set(retry.status_forcelist) == {502, 503, 504}


def test_post_is_not_in_the_retried_methods():
    """The whole point: POST must not auto-retry, since retrying a create
    call that actually reached the server risks a duplicate record."""
    session = get_session()
    retry = session.get_adapter("https://example.com").max_retries
    assert "POST" not in retry.allowed_methods
    assert "GET" in retry.allowed_methods
    assert "PUT" in retry.allowed_methods

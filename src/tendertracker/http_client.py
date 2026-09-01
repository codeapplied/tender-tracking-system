import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def get_session(total_retries: int = 3, backoff_factor: float = 0.5) -> requests.Session:
    """A requests.Session with automatic retry + exponential backoff for
    transient failures — pulled from a pattern validated in a prior, related
    system's own design (retry-with-backoff on outbound HTTP calls).

    Deliberately relies on urllib3's default allowed-methods policy: GET,
    HEAD, PUT, DELETE, OPTIONS are retried; POST is not. Retrying a failed
    POST blindly risks creating a duplicate record (e.g. a duplicate
    Pipedrive deal) if the request actually reached the server but the
    response was lost in transit — every POST in this project (create_deal,
    create_event, add_note, organization creation, Graph token requests)
    intentionally does NOT get automatic retries for this reason. GET/PUT
    calls (data feeds, deal/event lookups and updates, file uploads) are
    idempotent and safe to retry.
    """
    session = requests.Session()
    retry = Retry(
        total=total_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[502, 503, 504],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

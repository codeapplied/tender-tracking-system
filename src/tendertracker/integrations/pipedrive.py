import requests


class PipedriveError(Exception):
    pass


class PipedriveClient:
    """Thin wrapper over the Pipedrive REST API (v1) — no DB/business logic
    here, see pipeline/sync_pipedrive.py for what gets synced and when."""

    def __init__(self, api_token: str, domain: str, timeout: int = 30) -> None:
        self.api_token = api_token
        self.base_url = f"https://{domain}.pipedrive.com/api/v1"
        self.timeout = timeout

    def _request(self, method: str, path: str, *, params: dict | None = None, json: dict | None = None) -> dict:
        params = dict(params or {})
        params["api_token"] = self.api_token
        response = requests.request(method, f"{self.base_url}{path}", params=params, json=json, timeout=self.timeout)
        if not response.ok:
            raise PipedriveError(f"{method} {path} failed: {response.status_code} {response.text}")
        data = response.json()
        if not data.get("success", True):
            raise PipedriveError(f"{method} {path} returned success=false: {data}")
        return data.get("data")

    def get_deal(self, deal_id: int) -> dict:
        return self._request("GET", f"/deals/{deal_id}")

    def find_or_create_organization(self, name: str) -> int:
        results = self._request("GET", "/organizations/search", params={"term": name, "fields": "name"})
        for item in (results or {}).get("items", []):
            org = item.get("item", {})
            if org.get("name", "").strip().lower() == name.strip().lower():
                return org["id"]
        created = self._request("POST", "/organizations", json={"name": name})
        return created["id"]

    def create_deal(self, title: str, org_id: int | None, value: float | None, currency: str | None) -> dict:
        payload: dict = {"title": title}
        if org_id is not None:
            payload["org_id"] = org_id
        if value is not None:
            payload["value"] = value
        if currency:
            payload["currency"] = currency
        return self._request("POST", "/deals", json=payload)

    def update_deal(self, deal_id: int, title: str, value: float | None, currency: str | None) -> dict:
        payload: dict = {"title": title}
        if value is not None:
            payload["value"] = value
        if currency:
            payload["currency"] = currency
        return self._request("PUT", f"/deals/{deal_id}", json=payload)

    def add_note(self, deal_id: int, content: str) -> dict:
        return self._request("POST", "/notes", json={"deal_id": deal_id, "content": content})

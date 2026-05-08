"""
Power BI datasource connector.

Connection string:
  Data Source=powerbi://api.powerbi.com/v1.0/myorg/Sell%20Analytics;
  Initial Catalog=C2B GROWTH - REFERRAL;

Uses the Power BI REST API (XMLA endpoint) with Azure AD service-principal auth.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Connection config
# ---------------------------------------------------------------------------
XMLA_ENDPOINT = os.getenv(
    "POWERBI_XMLA_ENDPOINT",
    "powerbi://api.powerbi.com/v1.0/myorg/Sell%20Analytics",
)
DATASET_NAME = os.getenv("POWERBI_DATASET_NAME", "C2B GROWTH - REFERRAL")
WORKSPACE_NAME = os.getenv("POWERBI_WORKSPACE_NAME", "Sell Analytics")

TENANT_ID = os.getenv("POWERBI_TENANT_ID")
CLIENT_ID = os.getenv("POWERBI_CLIENT_ID")
CLIENT_SECRET = os.getenv("POWERBI_CLIENT_SECRET")

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = ["https://analysis.windows.net/powerbi/api/.default"]

POWERBI_API_BASE = "https://api.powerbi.com/v1.0/myorg"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def get_access_token() -> str:
    """Acquire an OAuth2 bearer token via client-credentials flow."""
    import msal

    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(scopes=SCOPE)
    if "access_token" not in result:
        raise RuntimeError(f"Auth failed: {result.get('error_description', result)}")
    return result["access_token"]


# ---------------------------------------------------------------------------
# REST API helpers
# ---------------------------------------------------------------------------
def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def get_workspace_id(token: str) -> str:
    """Resolve workspace name → group ID."""
    resp = requests.get(f"{POWERBI_API_BASE}/groups", headers=_headers(token))
    resp.raise_for_status()
    groups = resp.json().get("value", [])
    for g in groups:
        if g["name"] == WORKSPACE_NAME:
            return g["id"]
    available = [g["name"] for g in groups]
    raise ValueError(
        f"Workspace '{WORKSPACE_NAME}' not found. Available: {available}"
    )


def get_dataset_id(token: str, workspace_id: str) -> str:
    """Resolve dataset name → dataset ID within the workspace."""
    url = f"{POWERBI_API_BASE}/groups/{workspace_id}/datasets"
    resp = requests.get(url, headers=_headers(token))
    resp.raise_for_status()
    datasets = resp.json().get("value", [])
    for ds in datasets:
        if ds["name"] == DATASET_NAME:
            return ds["id"]
    available = [ds["name"] for ds in datasets]
    raise ValueError(
        f"Dataset '{DATASET_NAME}' not found in workspace. Available: {available}"
    )


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------
class PowerBIConnection:
    """
    Thin wrapper around the Power BI REST API for the
    'C2B GROWTH - REFERRAL' dataset in the 'Sell Analytics' workspace.

    Connection string equivalent:
      Data Source=powerbi://api.powerbi.com/v1.0/myorg/Sell%20Analytics;
      Initial Catalog=C2B GROWTH - REFERRAL;
    """

    def __init__(self):
        self._token: str | None = None
        self._workspace_id: str | None = None
        self._dataset_id: str | None = None

    def connect(self) -> "PowerBIConnection":
        self._token = get_access_token()
        self._workspace_id = get_workspace_id(self._token)
        self._dataset_id = get_dataset_id(self._token, self._workspace_id)
        print(
            f"Connected  workspace={self._workspace_id}  dataset={self._dataset_id}"
        )
        return self

    def execute_dax(self, query: str) -> list[dict]:
        """Run a DAX query against the dataset; returns rows as list of dicts."""
        if not self._token:
            raise RuntimeError("Call connect() first.")
        url = (
            f"{POWERBI_API_BASE}/groups/{self._workspace_id}"
            f"/datasets/{self._dataset_id}/executeQueries"
        )
        body = {"queries": [{"query": query}], "serializerSettings": {"includeNulls": True}}
        resp = requests.post(url, json=body, headers=_headers(self._token))
        resp.raise_for_status()
        results = resp.json()
        rows = (
            results.get("results", [{}])[0]
            .get("tables", [{}])[0]
            .get("rows", [])
        )
        return rows

    def get_dataset_info(self) -> dict:
        """Return metadata for the connected dataset."""
        if not self._token:
            raise RuntimeError("Call connect() first.")
        url = (
            f"{POWERBI_API_BASE}/groups/{self._workspace_id}"
            f"/datasets/{self._dataset_id}"
        )
        resp = requests.get(url, headers=_headers(self._token))
        resp.raise_for_status()
        return resp.json()

    def refresh_dataset(self) -> None:
        """Trigger an on-demand dataset refresh."""
        if not self._token:
            raise RuntimeError("Call connect() first.")
        url = (
            f"{POWERBI_API_BASE}/groups/{self._workspace_id}"
            f"/datasets/{self._dataset_id}/refreshes"
        )
        resp = requests.post(url, headers=_headers(self._token))
        resp.raise_for_status()
        print("Dataset refresh triggered.")


# ---------------------------------------------------------------------------
# Quick smoke-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    conn = PowerBIConnection().connect()
    info = conn.get_dataset_info()
    print("Dataset name :", info.get("name"))
    print("Configured by:", info.get("configuredBy"))
    print("Is refreshable:", info.get("isRefreshable"))

    # Example DAX query
    rows = conn.execute_dax("EVALUATE TOPN(5, 'YourTableName')")
    for row in rows:
        print(row)

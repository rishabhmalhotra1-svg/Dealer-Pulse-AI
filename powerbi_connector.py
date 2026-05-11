"""
DealerPulse AI — Power BI Live Data Connector
Connects to: powerbi://api.powerbi.com/v1.0/myorg/Sell%20Analytics
Dataset: C2B GROWTH - REFERRAL
"""

import os, json, requests, pandas as pd
from datetime import datetime

# ─── CONFIG (fill these in or set as env vars) ─────────────────────────────
TENANT_ID     = os.getenv("PBI_TENANT_ID",     "YOUR_TENANT_ID")
CLIENT_ID     = os.getenv("PBI_CLIENT_ID",     "YOUR_CLIENT_ID")      # Azure App ID
CLIENT_SECRET = os.getenv("PBI_CLIENT_SECRET", "YOUR_CLIENT_SECRET")  # Azure App Secret
WORKSPACE_NAME = "Sell Analytics"
DATASET_NAME   = "C2B GROWTH - REFERRAL"
TARGET_TM      = "rishabh.malhotra1@cars24.com"

PBI_RESOURCE  = "https://analysis.windows.net/powerbi/api"
PBI_API_BASE  = "https://api.powerbi.com/v1.0/myorg"
AUTH_URL      = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"

# ─── STEP 1: GET ACCESS TOKEN ──────────────────────────────────────────────
def get_access_token():
    resp = requests.post(AUTH_URL, data={
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope":         f"{PBI_RESOURCE}/.default"
    })
    resp.raise_for_status()
    token = resp.json()["access_token"]
    print("✅ Power BI authentication successful")
    return token

# ─── STEP 2: FIND WORKSPACE + DATASET IDs ─────────────────────────────────
def get_dataset_id(token):
    headers = {"Authorization": f"Bearer {token}"}

    # Get workspaces
    ws_resp = requests.get(f"{PBI_API_BASE}/groups", headers=headers)
    ws_resp.raise_for_status()
    workspaces = ws_resp.json()["value"]
    workspace  = next((w for w in workspaces if w["name"] == WORKSPACE_NAME), None)
    if not workspace:
        raise ValueError(f"Workspace '{WORKSPACE_NAME}' not found. Available: {[w['name'] for w in workspaces]}")
    ws_id = workspace["id"]
    print(f"✅ Workspace found: {WORKSPACE_NAME} (ID: {ws_id})")

    # Get datasets in workspace
    ds_resp = requests.get(f"{PBI_API_BASE}/groups/{ws_id}/datasets", headers=headers)
    ds_resp.raise_for_status()
    datasets = ds_resp.json()["value"]
    dataset  = next((d for d in datasets if d["name"] == DATASET_NAME), None)
    if not dataset:
        raise ValueError(f"Dataset '{DATASET_NAME}' not found. Available: {[d['name'] for d in datasets]}")
    ds_id = dataset["id"]
    print(f"✅ Dataset found: {DATASET_NAME} (ID: {ds_id})")
    return ws_id, ds_id

# ─── STEP 3: EXECUTE DAX QUERY ────────────────────────────────────────────
def run_dax(token, ws_id, ds_id, dax_query):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json"
    }
    payload = {"queries": [{"query": dax_query}], "serializerSettings": {"includeNulls": True}}
    resp = requests.post(
        f"{PBI_API_BASE}/groups/{ws_id}/datasets/{ds_id}/executeQueries",
        headers=headers, json=payload
    )
    resp.raise_for_status()
    rows = resp.json()["results"][0]["tables"][0].get("rows", [])
    return pd.DataFrame(rows)

# ─── STEP 4: PULL DEALER DATA ──────────────────────────────────────────────
# *** Adjust column names below to match your actual Power BI table/column names ***
DEALER_DAX = """
EVALUATE
FILTER(
    SELECTCOLUMNS(
        'Dealer Master',
        "DealerCode",    [Dealer Code],
        "DealerName",    [Dealer Name],
        "Region",        [Region],
        "Zone",          [Zone],
        "KAM",           [KAM Name],
        "TL",            [TL Email],
        "TM",            [TM Email],
        "OnboardDate",   [Onboarding Date],
        "L3M_Leads",     [L3M Leads],
        "L3M_Insp",      [L3M Inspections],
        "L3M_SI",        [L3M Stock Ins],
        "L6M_Leads",     [L6M Leads],
        "TotalLeads",    [Total Leads],
        "TotalInsp",     [Total Inspections],
        "TotalSI",       [Total Stock Ins]
    ),
    OR(
        'Dealer Master'[TL Email] = "rishabh.malhotra1@cars24.com",
        'Dealer Master'[TM Email] = "rishabh.malhotra1@cars24.com"
    )
)
ORDER BY [L3M_SI] DESC
"""

def fetch_dealer_data():
    token       = get_access_token()
    ws_id, ds_id = get_dataset_id(token)
    print("📊 Running DAX query for dealer data...")
    df = run_dax(token, ws_id, ds_id, DEALER_DAX)
    print(f"✅ Fetched {len(df)} dealer records from Power BI")
    return df

# ─── STEP 5: LIST AVAILABLE TABLES (for discovery) ────────────────────────
def list_tables(token, ws_id, ds_id):
    """Run this first to discover your table/column names in the dataset."""
    dax = "EVALUATE INFO.TABLES()"
    try:
        df = run_dax(token, ws_id, ds_id, dax)
        print("\n📋 Tables in dataset:")
        for t in df.get("[Name]", df.columns[:1]).tolist():
            print(f"   • {t}")
        return df
    except Exception as e:
        print(f"Could not list tables via DAX: {e}")
        # Fallback: get schema via metadata API
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(
            f"{PBI_API_BASE}/groups/{ws_id}/datasets/{ds_id}/tables",
            headers=headers
        )
        if resp.ok:
            tables = resp.json().get("value", [])
            print("\n📋 Tables in dataset:")
            for t in tables:
                print(f"   • {t['name']}")
                for col in t.get("columns", []):
                    print(f"       - {col['name']} ({col['dataType']})")
        return None

# ─── MAIN ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("DealerPulse AI — Power BI Connector")
    print(f"Workspace : {WORKSPACE_NAME}")
    print(f"Dataset   : {DATASET_NAME}")
    print("=" * 60)

    if TENANT_ID == "YOUR_TENANT_ID":
        print("""
⚠️  CREDENTIALS NOT SET

You need to set 3 environment variables (or edit this file):

  export PBI_TENANT_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  export PBI_CLIENT_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  export PBI_CLIENT_SECRET="your-secret-value"

How to get these:
  1. Go to portal.azure.com → Azure Active Directory → App registrations
  2. Click "New registration" → name it "DealerPulse-AI"
  3. After creating: copy the "Application (client) ID" = CLIENT_ID
  4. Copy "Directory (tenant) ID" = TENANT_ID
  5. Go to Certificates & secrets → New client secret → copy value = CLIENT_SECRET
  6. In Power BI admin portal: enable "Allow service principals to use Power BI APIs"
  7. In your workspace settings: add the service principal as a Member/Contributor

Then re-run this script.
""")
        sys.exit(1)

    try:
        token = get_access_token()
        ws_id, ds_id = get_dataset_id(token)

        # First run: discover table structure
        if "--discover" in sys.argv:
            list_tables(token, ws_id, ds_id)
        else:
            df = fetch_dealer_data()
            print(df.head())
            # Save to CSV for DealerPulse analysis pipeline
            out = f"/home/user/Dealer-Pulse-AI/live_dealer_data_{datetime.now().strftime('%Y%m%d')}.csv"
            df.to_csv(out, index=False)
            print(f"\n💾 Saved to: {out}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise

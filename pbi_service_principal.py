"""
DealerPulse AI — Power BI Service Principal Connector
Auth: Azure AD App (Service Principal) — no user credentials, no MFA bypass
Flow: Client Credentials → Bearer Token → Power BI REST API

Setup:
  1. Azure Portal → App registrations → New → name: "DealerPulse-AI-SP"
  2. Copy: Application (client) ID  →  PBI_CLIENT_ID
  3. Copy: Directory (tenant) ID    →  PBI_TENANT_ID
  4. Certificates & secrets → New client secret → copy value  →  PBI_CLIENT_SECRET
  5. Power BI Admin Portal → Tenant settings → Developer settings
       → "Allow service principals to use Power BI APIs" → ENABLE
  6. Power BI Workspace "Sell Analytics" → Access → add SP as Viewer

Usage:
  export PBI_TENANT_ID=xxx PBI_CLIENT_ID=xxx PBI_CLIENT_SECRET=xxx
  python3 pbi_service_principal.py --test
  python3 pbi_service_principal.py --discover
  python3 pbi_service_principal.py --pull
"""

import os, sys, json, requests
from datetime import datetime

WORKSPACE_NAME = "Sell Analytics"
DATASET_NAME   = "C2B GROWTH - REFERRAL"
PBI_API_BASE   = "https://api.powerbi.com/v1.0/myorg"
TARGET_TM      = "rishabh.malhotra1@cars24.com"

# ── Credentials (from env vars or Azure Key Vault) ─────────────────────────
TENANT_ID     = os.getenv("PBI_TENANT_ID")
CLIENT_ID     = os.getenv("PBI_CLIENT_ID")
CLIENT_SECRET = os.getenv("PBI_CLIENT_SECRET")

def check_creds():
    missing = [k for k, v in {"PBI_TENANT_ID": TENANT_ID,
                               "PBI_CLIENT_ID": CLIENT_ID,
                               "PBI_CLIENT_SECRET": CLIENT_SECRET}.items() if not v]
    if missing:
        print(f"❌ Missing env vars: {', '.join(missing)}")
        print("\nSet them with:")
        for k in missing:
            print(f"  export {k}=<value>")
        sys.exit(1)

# ── Step 1: Get token via client credentials (Service Principal) ───────────
def get_token():
    check_creds()
    url  = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope":         "https://analysis.windows.net/powerbi/api/.default"
    }
    r = requests.post(url, data=data, timeout=30)
    if r.status_code != 200:
        print(f"❌ Auth failed ({r.status_code}): {r.json().get('error_description', r.text)}")
        sys.exit(1)
    print("✅ Service Principal authenticated")
    return r.json()["access_token"]

# ── Step 2: Find workspace + dataset ──────────────────────────────────────
def find_ids(token):
    h = {"Authorization": f"Bearer {token}"}

    # Workspace
    r = requests.get(f"{PBI_API_BASE}/groups", headers=h, timeout=30)
    if r.status_code == 403:
        print("❌ 403 on /groups — ensure 'Allow service principals to use Power BI APIs' is ON")
        print("   And that the Service Principal is added to the workspace as Viewer")
        sys.exit(1)
    r.raise_for_status()
    groups = r.json()["value"]
    ws = next((g for g in groups if g["name"] == WORKSPACE_NAME), None)
    if not ws:
        print(f"❌ Workspace '{WORKSPACE_NAME}' not found.")
        print(f"   Available: {[g['name'] for g in groups]}")
        sys.exit(1)
    ws_id = ws["id"]
    print(f"✅ Workspace : {WORKSPACE_NAME}  ({ws_id})")

    # Dataset
    r = requests.get(f"{PBI_API_BASE}/groups/{ws_id}/datasets", headers=h, timeout=30)
    r.raise_for_status()
    datasets = r.json()["value"]
    ds = next((d for d in datasets if d["name"] == DATASET_NAME), None)
    if not ds:
        print(f"❌ Dataset '{DATASET_NAME}' not found.")
        print(f"   Available: {[d['name'] for d in datasets]}")
        sys.exit(1)
    ds_id = ds["id"]
    print(f"✅ Dataset   : {DATASET_NAME}  ({ds_id})")
    return ws_id, ds_id

# ── Step 3: Discover schema ────────────────────────────────────────────────
def discover(token, ws_id, ds_id):
    h = {"Authorization": f"Bearer {token}"}
    print("\n📋 Schema for dataset:", DATASET_NAME)

    # REST metadata
    r = requests.get(f"{PBI_API_BASE}/groups/{ws_id}/datasets/{ds_id}/tables", headers=h, timeout=30)
    if r.ok:
        for t in r.json().get("value", []):
            print(f"\n  TABLE: {t['name']}")
            for col in t.get("columns", []):
                print(f"    ├─ {col['name']}  ({col['dataType']})")
    else:
        # Fallback: DAX INFO
        run_dax(token, ws_id, ds_id,
                "EVALUATE SELECTCOLUMNS(INFO.TABLES(), \"Table\", [Name], \"Rows\", [RowsCount])")

# ── Step 4: Execute DAX ───────────────────────────────────────────────────
def run_dax(token, ws_id, ds_id, dax):
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"queries": [{"query": dax}], "serializerSettings": {"includeNulls": True}}
    r = requests.post(
        f"{PBI_API_BASE}/groups/{ws_id}/datasets/{ds_id}/executeQueries",
        headers=h, json=body, timeout=60
    )
    if not r.ok:
        print(f"❌ DAX failed ({r.status_code}): {r.text[:500]}")
        return []
    rows = r.json()["results"][0]["tables"][0].get("rows", [])
    return rows

# ── Step 5: Pull dealer data ───────────────────────────────────────────────
# *** Update table/column names after running --discover ***
DEALER_DAX = """
EVALUATE
FILTER(
    SELECTCOLUMNS(
        'Dealer Master',
        "DealerCode",   'Dealer Master'[Dealer Code],
        "DealerName",   'Dealer Master'[Dealer Name],
        "Region",       'Dealer Master'[Region],
        "Zone",         'Dealer Master'[Zone],
        "KAM",          'Dealer Master'[KAM Name],
        "TM",           'Dealer Master'[TM Email],
        "TL",           'Dealer Master'[TL Email],
        "OnboardDate",  'Dealer Master'[Onboarding Date],
        "L3M_Leads",    'Dealer Master'[L3M Leads],
        "L3M_Insp",     'Dealer Master'[L3M Inspections],
        "L3M_SI",       'Dealer Master'[L3M Stock Ins],
        "L6M_Leads",    'Dealer Master'[L6M Leads],
        "TotalLeads",   'Dealer Master'[Total Leads],
        "TotalInsp",    'Dealer Master'[Total Inspections],
        "TotalSI",      'Dealer Master'[Total Stock Ins]
    ),
    OR(
        'Dealer Master'[TM Email] = "rishabh.malhotra1@cars24.com",
        'Dealer Master'[TL Email] = "rishabh.malhotra1@cars24.com"
    )
)
ORDER BY 'Dealer Master'[L3M Stock Ins] DESC
"""

def pull_data(token, ws_id, ds_id):
    import pandas as pd
    print("\n📊 Pulling dealer data via DAX...")
    rows = run_dax(token, ws_id, ds_id, DEALER_DAX)
    if not rows:
        return None
    df = pd.DataFrame(rows)
    # Strip PBI column prefix "[ColName]" → "ColName"
    df.columns = [c.strip("[]").split("]")[-1].strip() for c in df.columns]
    print(f"✅ {len(df)} dealers fetched")

    out = f"/home/user/Dealer-Pulse-AI/live_dealer_data_{datetime.now().strftime('%Y%m%d')}.csv"
    df.to_csv(out, index=False)
    print(f"💾 Saved → {out}")

    # Run through DealerPulse agent
    print("\n🔄 Running DealerPulse analysis on live data...")
    os.system(f"python3 /home/user/Dealer-Pulse-AI/dealerpulse_agent.py {out} --excel")
    return df

# ── Export API (Option 2 — report snapshot) ───────────────────────────────
def export_report_snapshot(token, ws_id, report_id, fmt="PDF"):
    """Export a Power BI report as PDF/XLSX snapshot."""
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"format": fmt}
    r = requests.post(
        f"{PBI_API_BASE}/groups/{ws_id}/reports/{report_id}/ExportTo",
        headers=h, json=body, timeout=30
    )
    if not r.ok:
        print(f"❌ Export failed: {r.text[:300]}")
        return None
    export_id = r.json()["id"]
    print(f"⏳ Export started (ID: {export_id}) — polling...")
    import time
    for _ in range(12):
        time.sleep(5)
        status = requests.get(
            f"{PBI_API_BASE}/groups/{ws_id}/reports/{report_id}/exports/{export_id}",
            headers=h
        ).json()
        print(f"   Status: {status.get('status')}")
        if status.get("status") == "Succeeded":
            file_r = requests.get(
                f"{PBI_API_BASE}/groups/{ws_id}/reports/{report_id}/exports/{export_id}/file",
                headers=h
            )
            path = f"/home/user/Dealer-Pulse-AI/pbi_export_{datetime.now().strftime('%Y%m%d')}.{fmt.lower()}"
            with open(path, "wb") as f:
                f.write(file_r.content)
            print(f"✅ Exported → {path}")
            return path
    print("❌ Export timed out")
    return None

# ── MAIN ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--test"
    print(f"\n{'='*60}")
    print(f"  DealerPulse AI — Service Principal Auth")
    print(f"  {datetime.now().strftime('%d %b %Y %H:%M')}")
    print(f"{'='*60}\n")

    token = get_token()
    ws_id, ds_id = find_ids(token)

    if mode == "--test":
        print("\n✅ Connection successful — Service Principal is working.")
        print(f"   Workspace ID : {ws_id}")
        print(f"   Dataset  ID  : {ds_id}")
        print("\nNext:")
        print("  --discover  →  map table/column names")
        print("  --pull      →  fetch live dealer data + regenerate Excel & Slack")

    elif mode == "--discover":
        discover(token, ws_id, ds_id)

    elif mode == "--pull":
        pull_data(token, ws_id, ds_id)

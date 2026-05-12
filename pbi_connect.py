"""
DealerPulse AI — Power BI XMLA / REST Connector
Connection: powerbi://api.powerbi.com/v1.0/myorg/Sell%20Analytics
Dataset:    C2B GROWTH - REFERRAL

Auth: Device Code Flow (sign in with your Microsoft account — no app setup needed)
"""

import json, requests, sys, os
from msal import PublicClientApplication

# ── Power BI connection details from your XMLA string ─────────────────────
# Dataset is in "My Workspace" — accessed directly, no group/workspace ID needed
DATASET_NAME        = "C2B GROWTH - REFERRAL"
WORKSPACE_NAME      = None   # My Workspace has no group ID in the API

# Power BI / AAS public client (well-known, no app registration needed)
PBI_PUBLIC_CLIENT_ID = "7f67af8a-fedc-4b08-8b4e-37c4d127b6cf"
AUTHORITY            = "https://login.microsoftonline.com/organizations"
SCOPES               = ["https://analysis.windows.net/powerbi/api/.default"]
PBI_API_BASE         = "https://api.powerbi.com/v1.0/myorg"

TOKEN_CACHE_FILE = "/home/user/Dealer-Pulse-AI/.pbi_token_cache.json"

# ── Auth: Device Code Flow ─────────────────────────────────────────────────
def get_token():
    cache = msal_token_cache()
    app   = PublicClientApplication(
        PBI_PUBLIC_CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache
    )

    # Try silent first (reuse cached token)
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            print(f"✅ Using cached token for: {accounts[0]['username']}")
            save_cache(cache)
            return result["access_token"]

    # Interactive device code flow
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise ValueError("Could not initiate device flow: " + json.dumps(flow, indent=2))

    print("\n" + "═"*60)
    print("🔐  SIGN IN TO POWER BI")
    print("═"*60)
    print(f"\n  1. Open this URL in your browser:")
    print(f"     https://microsoft.com/devicelogin")
    print(f"\n  2. Enter this code: {flow['user_code']}")
    print(f"\n  3. Sign in with your Cars24 Microsoft account")
    print(f"     (rishabh.malhotra1@cars24.com)")
    print("\n" + "═"*60)
    print("Waiting for you to sign in", end="", flush=True)

    result = app.acquire_token_by_device_flow(flow)

    if "access_token" not in result:
        raise ValueError("Authentication failed: " + result.get("error_description", str(result)))

    save_cache(cache)
    print(f"\n✅ Signed in successfully!")
    return result["access_token"]

def msal_token_cache():
    from msal import SerializableTokenCache
    cache = SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE_FILE):
        with open(TOKEN_CACHE_FILE, "r") as f:
            cache.deserialize(f.read())
    return cache

def save_cache(cache):
    from msal import SerializableTokenCache
    if cache.has_state_changed:
        with open(TOKEN_CACHE_FILE, "w") as f:
            f.write(cache.serialize())

# ── REST API helpers ───────────────────────────────────────────────────────
def api_get(token, url):
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    return r.json()

def api_post(token, url, body):
    r = requests.post(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                      json=body, timeout=60)
    r.raise_for_status()
    return r.json()

def dataset_url(ws_id, ds_id, path=""):
    # My Workspace: /myorg/datasets/{id}/...
    # Shared workspace: /myorg/groups/{ws_id}/datasets/{id}/...
    if ws_id:
        return f"{PBI_API_BASE}/groups/{ws_id}/datasets/{ds_id}{path}"
    return f"{PBI_API_BASE}/datasets/{ds_id}{path}"

# ── Find dataset in My Workspace ───────────────────────────────────────────
def find_ids(token):
    # My Workspace datasets are at /myorg/datasets — no group ID needed
    try:
        all_datasets = api_get(token, f"{PBI_API_BASE}/datasets")["value"]
    except Exception as e:
        print(f"❌ Cannot list datasets: {e}")
        print("   Ensure Power BI Admin → Tenant settings → Developer settings")
        print("   → 'Users can access Power BI service features using REST APIs' is ON")
        sys.exit(1)

    ds = next((d for d in all_datasets if d["name"] == DATASET_NAME), None)
    if not ds:
        names = [d["name"] for d in all_datasets]
        print(f"❌ Dataset '{DATASET_NAME}' not found in My Workspace.")
        print(f"   Found: {names}")
        sys.exit(1)

    ds_id = ds["id"]
    print(f"✅ Dataset : {DATASET_NAME}  (ID: {ds_id})")
    print(f"   Location : My Workspace")
    # My Workspace has no group — use None, calls go to /myorg/datasets/{id}/...
    return None, ds_id

# ── Discover schema ────────────────────────────────────────────────────────
def discover_schema(token, ws_id, ds_id):
    print("\n📋 Discovering tables and columns in your dataset...\n")
    try:
        resp = api_get(token, dataset_url(ws_id, ds_id, "/tables"))
        tables = resp.get("value", [])
        for t in tables:
            print(f"  TABLE: {t['name']}")
            for col in t.get("columns", []):
                print(f"    ├─ {col['name']}  ({col['dataType']})")
            print()
    except Exception as e:
        print(f"  Metadata API not available ({e}), trying DAX INFO...")
        try:
            rows = run_dax(token, ws_id, ds_id,
                           "EVALUATE SELECTCOLUMNS(INFO.TABLES(), \"Table\", [Name])")
            print("  Tables found:")
            for r in rows:
                print(f"    • {list(r.values())[0]}")
        except Exception as e2:
            print(f"  Could not enumerate tables: {e2}")

# ── Run DAX query ──────────────────────────────────────────────────────────
def run_dax(token, ws_id, ds_id, dax):
    result = api_post(token, dataset_url(ws_id, ds_id, "/executeQueries"),
                      {"queries": [{"query": dax}], "serializerSettings": {"includeNulls": True}})
    rows = result["results"][0]["tables"][0].get("rows", [])
    return rows

# ── Pull dealer data (update DAX once you know your column names) ──────────
def pull_dealer_data(token, ws_id, ds_id):
    import pandas as pd

    print("\n📊 Pulling dealer data...")
    print("   (If DAX column names mismatch, run --discover first to find exact names)\n")

    # ── EDIT the table/column names below to match your schema ──
    dax = """
EVALUATE
TOPN(
    5000,
    SELECTCOLUMNS(
        'Dealer Master',
        "DealerCode",  'Dealer Master'[Dealer Code],
        "DealerName",  'Dealer Master'[Dealer Name],
        "Region",      'Dealer Master'[Region],
        "Zone",        'Dealer Master'[Zone],
        "KAM",         'Dealer Master'[KAM Name],
        "TM",          'Dealer Master'[TM Email],
        "TL",          'Dealer Master'[TL Email],
        "L3M_Leads",   'Dealer Master'[L3M Leads],
        "L3M_Insp",    'Dealer Master'[L3M Inspections],
        "L3M_SI",      'Dealer Master'[L3M Stock Ins],
        "L6M_Leads",   'Dealer Master'[L6M Leads]
    ),
    'Dealer Master'[L3M Leads],
    DESC
)
"""
    try:
        rows = run_dax(token, ws_id, ds_id, dax)
        df = pd.DataFrame(rows)
        # Strip Power BI column name prefix (e.g. "[DealerCode]" -> "DealerCode")
        df.columns = [c.split("]")[-1].strip("[").strip() if "]" in c else c for c in df.columns]
        print(f"✅ Fetched {len(df)} rows")
        print(df.head(3).to_string())
        out = f"/home/user/Dealer-Pulse-AI/live_dealer_data.csv"
        df.to_csv(out, index=False)
        print(f"\n💾 Saved → {out}")
        return df
    except Exception as e:
        print(f"\n❌ DAX query failed: {e}")
        print("   Run  python3 pbi_connect.py --discover  to find exact table/column names")
        return None

# ── MAIN ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════╗")
    print("║   DealerPulse AI  ←→  Power BI Live Connection          ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  Workspace : Sell Analytics                              ║")
    print(f"║  Dataset   : C2B GROWTH - REFERRAL                      ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    mode = sys.argv[1] if len(sys.argv) > 1 else "--pull"

    token = get_token()
    ws_id, ds_id = find_ids(token)

    if mode == "--discover":
        discover_schema(token, ws_id, ds_id)

    elif mode == "--pull":
        pull_dealer_data(token, ws_id, ds_id)

    elif mode == "--test":
        print("\n🔌 Connection test passed! Power BI is reachable.")
        print(f"   Workspace ID : {ws_id}")
        print(f"   Dataset  ID  : {ds_id}")
        print("\nNext steps:")
        print("  python3 pbi_connect.py --discover   ← see all table/column names")
        print("  python3 pbi_connect.py --pull       ← fetch live dealer data")

"""
Local test: confirm the EVS app registration can reach the Urban Soil Co-Lab
SharePoint library via Microsoft Graph (app-only / client-credentials flow).

Run locally (never commit the secret):
    export SP_TENANT_ID='<tenant-uuid>'
    export SP_CLIENT_ID='448531da-6d44-4729-8761-3f518ad44bfa'
    export SP_CLIENT_SECRET='<paste-from-box-note>'
    python3 test_sharepoint.py

Requires: pip install msal requests
"""
import os
import sys
import requests
import msal

# ---- Config from environment (no secrets in code) ----
TENANT_ID = os.environ.get("SP_TENANT_ID")
CLIENT_ID = os.environ.get("SP_CLIENT_ID", "448531da-6d44-4729-8761-3f518ad44bfa")
CLIENT_SECRET = os.environ.get("SP_CLIENT_SECRET")

# ---- SharePoint target (decoded from the library URL) ----
SP_HOST = "ubuffalo.sharepoint.com"
SP_SITE_PATH = "/teams/CASSoilCo-Lab"          # the team site
TARGET_FOLDER = "Urban Soil Co-Lab"             # folder inside the default drive

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = ["https://graph.microsoft.com/.default"]
GRAPH = "https://graph.microsoft.com/v1.0"


def fail(msg):
    print(f"\n❌ {msg}")
    sys.exit(1)


def main():
    if not TENANT_ID:
        fail("SP_TENANT_ID not set. Run the curl command to get UB's tenant ID first.")
    if not CLIENT_SECRET:
        fail("SP_CLIENT_SECRET not set. export it from the Box note (don't paste it in chat).")

    # 1. Authenticate (client credentials)
    print("1. Authenticating with Microsoft Graph...")
    app = msal.ConfidentialClientApplication(
        CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
    )
    result = app.acquire_token_for_client(scopes=SCOPE)
    if "access_token" not in result:
        fail(f"Auth failed: {result.get('error')} - {result.get('error_description')}")
    token = result["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   ✅ Got an access token. (Secret is valid, tenant is correct.)")

    # 2. Resolve the site
    print(f"2. Resolving site {SP_HOST}:{SP_SITE_PATH} ...")
    r = requests.get(f"{GRAPH}/sites/{SP_HOST}:{SP_SITE_PATH}", headers=headers)
    if r.status_code == 403:
        fail("403 Forbidden resolving site. The app authenticated but lacks permission "
             "to this site. UBIT likely needs to grant Sites.Selected (read/write) to "
             "THIS site. Share the output below with them.")
    if r.status_code != 200:
        fail(f"Site lookup returned {r.status_code}: {r.text[:400]}")
    site = r.json()
    site_id = site["id"]
    print(f"   ✅ Site resolved. site_id = {site_id}")

    # 3. List the default document library (drive) root
    print("3. Listing the default drive root...")
    r = requests.get(f"{GRAPH}/sites/{site_id}/drive/root/children", headers=headers)
    if r.status_code == 403:
        fail("403 listing drive. App can see the site but not read files. "
             "Permission scope is too narrow.")
    if r.status_code != 200:
        fail(f"Drive listing returned {r.status_code}: {r.text[:400]}")
    items = r.json().get("value", [])
    print(f"   ✅ Drive readable. {len(items)} item(s) at root:")
    for it in items[:25]:
        kind = "DIR " if "folder" in it else "file"
        print(f"      [{kind}] {it['name']}")

    # 4. Look into the target folder
    print(f"4. Listing target folder '{TARGET_FOLDER}'...")
    r = requests.get(
        f"{GRAPH}/sites/{site_id}/drive/root:/{TARGET_FOLDER}:/children",
        headers=headers,
    )
    if r.status_code == 200:
        sub = r.json().get("value", [])
        print(f"   ✅ Found '{TARGET_FOLDER}' with {len(sub)} item(s):")
        for it in sub[:25]:
            kind = "DIR " if "folder" in it else "file"
            print(f"      [{kind}] {it['name']}")
    else:
        print(f"   ⚠️  Could not list '{TARGET_FOLDER}' ({r.status_code}). "
              f"Folder name may differ; check the root listing above.")

    print("\n🎉 SUCCESS: the app registration can reach your SharePoint library.")
    print("   We can build the real sync against this exact path.")


if __name__ == "__main__":
    main()
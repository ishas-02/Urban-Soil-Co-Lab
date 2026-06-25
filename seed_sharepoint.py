"""
STAGE A — ONE-TIME SEED: upload local ./data  ->  SharePoint 'Urban Soil Co-Lab'.

This is upload-only. It creates folders and uploads files. It NEVER deletes
anything on SharePoint or locally. Safe to run while the SharePoint folder is empty.

Run locally (secret from env, never hardcoded):
    export SP_TENANT_ID='96464a8a-f8ed-40b1-99e2-5f6b50a20250'
    export SP_CLIENT_ID='448531da-6d44-4729-8761-3f518ad44bfa'
    export SP_CLIENT_SECRET='<paste-from-box-note>'
    python3 seed_sharepoint.py            # dry run first (lists what WOULD upload)
    python3 seed_sharepoint.py --go       # actually upload

Requires: pip install msal requests
"""
import os
import sys
import requests
import msal

TENANT_ID = os.environ.get("SP_TENANT_ID")
CLIENT_ID = os.environ.get("SP_CLIENT_ID", "448531da-6d44-4729-8761-3f518ad44bfa")
CLIENT_SECRET = os.environ.get("SP_CLIENT_SECRET")

# Resolved earlier by test_sharepoint.py — hardcoded so we don't re-resolve.
SITE_ID = ("ubuffalo.sharepoint.com,5f018493-39ef-46af-a3cd-7ac32fed4007,"
           "7d18843c-7584-4fd4-885f-9ebd21322727")
SP_ROOT_FOLDER = "Urban Soil Co-Lab"          # destination folder in the default drive
LOCAL_DIR = "./data"                          # source on your Mac

# Skip junk that rode along in earlier copies.
SKIP_NAMES = {".DS_Store"}
SKIP_SUFFIXES = ()                            # add e.g. (".pdf",) to skip the Jenkins PDF

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPE = ["https://graph.microsoft.com/.default"]
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"

DRY_RUN = "--go" not in sys.argv


def fail(msg):
    print(f"\n❌ {msg}")
    sys.exit(1)


def get_token():
    if not TENANT_ID or not CLIENT_SECRET:
        fail("SP_TENANT_ID and SP_CLIENT_SECRET must be set in the environment.")
    app = msal.ConfidentialClientApplication(
        CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
    )
    res = app.acquire_token_for_client(scopes=SCOPE)
    if "access_token" not in res:
        fail(f"Auth failed: {res.get('error_description')}")
    return res["access_token"]


def should_skip(name):
    if name in SKIP_NAMES:
        return True
    return any(name.endswith(suf) for suf in SKIP_SUFFIXES)


def upload_file(headers, local_path, sp_rel_path):
    """Upload one file to {SP_ROOT_FOLDER}/{sp_rel_path} via simple PUT (<4MB files)."""
    size = os.path.getsize(local_path)
    target = f"{SP_ROOT_FOLDER}/{sp_rel_path}".replace("\\", "/")
    if DRY_RUN:
        print(f"   [DRY] would upload {sp_rel_path}  ({size} bytes)")
        return True
    # Files <4MB: single PUT to the content endpoint, path-addressed.
    url = f"{GRAPH}/sites/{SITE_ID}/drive/root:/{target}:/content"
    with open(local_path, "rb") as f:
        r = requests.put(url, headers=headers, data=f.read())
    if r.status_code in (200, 201):
        print(f"   ✅ uploaded {sp_rel_path}")
        return True
    print(f"   ❌ FAILED {sp_rel_path}: {r.status_code} {r.text[:200]}")
    return False


def main():
    if not os.path.isdir(LOCAL_DIR):
        fail(f"Local dir {LOCAL_DIR} not found. Run from your project root.")

    mode = "DRY RUN (nothing uploaded)" if DRY_RUN else "LIVE UPLOAD"
    print(f"=== Seed SharePoint :: {mode} ===")
    print(f"    Source: {LOCAL_DIR}")
    print(f"    Dest:   SharePoint /{SP_ROOT_FOLDER}/\n")

    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    uploaded = skipped = failed = 0
    for root, _dirs, files in os.walk(LOCAL_DIR):
        for name in sorted(files):
            if should_skip(name):
                skipped += 1
                continue
            local_path = os.path.join(root, name)
            rel = os.path.relpath(local_path, LOCAL_DIR)
            ok = upload_file(headers, local_path, rel)
            uploaded += 1 if ok else 0
            failed += 0 if ok else 1

    print(f"\n--- Summary ---")
    print(f"   {'would upload' if DRY_RUN else 'uploaded'}: {uploaded}")
    print(f"   skipped (junk): {skipped}")
    if not DRY_RUN:
        print(f"   failed: {failed}")
    if DRY_RUN:
        print("\nDry run only. Re-run with  --go  to actually upload.")
    else:
        print("\n🎉 Seed complete. Verify in the SharePoint web UI, then we build Stage B.")


if __name__ == "__main__":
    main()
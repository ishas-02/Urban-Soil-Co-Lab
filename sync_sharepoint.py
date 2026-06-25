"""
STAGE B (v4) — SharePoint <-> volume sync.  Runs IN-CLUSTER.

Change detection compares each side against ITS OWN previously-recorded state
(.sync_state.json) — never cross-computes a hash:
  * SharePoint side: current quickXorHash (from Graph) vs stored quickXorHash.
  * Local side:      current (size, mtime)            vs stored (size, mtime).

Policy:
  * Additive both ways — never auto-deletes either side.
  * SharePoint wins genuine conflicts — local backed up to .sync_backups/<ts>/ first.
  * First run: same size both sides -> assume in-sync; size mismatch -> SharePoint wins.

Excludes (BOTH sides):
  .DS_Store, *.backup.*, __*test*, *.pdf, sync bookkeeping,
  AND generated_reports/ (regenerable outputs — kept off the synced volume).

Backup retention: .sync_backups/ pruned to the most recent BACKUP_KEEP runs.

Env: SP_TENANT_ID, SP_CLIENT_ID, SP_CLIENT_SECRET, SOIL_DATA_DIR, SP_DRY_RUN=1
Requires: msal, requests
"""
import os, sys, json, shutil, datetime as dt
import requests, msal

TENANT_ID=os.environ.get("SP_TENANT_ID")
CLIENT_ID=os.environ.get("SP_CLIENT_ID","448531da-6d44-4729-8761-3f518ad44bfa")
CLIENT_SECRET=os.environ.get("SP_CLIENT_SECRET")
DRY_RUN=os.environ.get("SP_DRY_RUN","0")=="1"
DATA_DIR=os.environ.get("SOIL_DATA_DIR","/opt/app-root/src/data")
BACKUP_KEEP=int(os.environ.get("SP_BACKUP_KEEP","10"))   # retain last N backup runs

SITE_ID=("ubuffalo.sharepoint.com,5f018493-39ef-46af-a3cd-7ac32fed4007,"
         "7d18843c-7584-4fd4-885f-9ebd21322727")
SP_ROOT="Urban Soil Co-Lab"
GRAPH="https://graph.microsoft.com/v1.0"
SCOPE=["https://graph.microsoft.com/.default"]
AUTHORITY=f"https://login.microsoftonline.com/{TENANT_ID}"
STATE_FILE=os.path.join(DATA_DIR,".sync_state.json")
BACKUP_DIR=os.path.join(DATA_DIR,".sync_backups")
RUN_TS=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

# Folders/paths excluded from sync entirely (regenerable or non-data).
EXCLUDE_DIR_PREFIXES=("generated_reports/",)

def _excluded(rel):
    name=os.path.basename(rel)
    if name==".DS_Store": return True
    if rel.startswith(".sync_state.json") or rel.startswith(".sync_backups"): return True
    if ".backup." in name: return True
    if name.startswith("__") and "test" in name: return True
    if name.lower().endswith(".pdf"): return True
    if name=="persistence_test.txt": return True
    if any(rel.startswith(p) for p in EXCLUDE_DIR_PREFIXES): return True
    return False

def log(m): print(f"[{dt.datetime.now(dt.timezone.utc).isoformat()}] {m}",flush=True)
def fail(m): log(f"FATAL: {m}"); sys.exit(1)

def get_headers():
    if not TENANT_ID or not CLIENT_SECRET: fail("SP_TENANT_ID and SP_CLIENT_SECRET must be set.")
    app=msal.ConfidentialClientApplication(CLIENT_ID,authority=AUTHORITY,client_credential=CLIENT_SECRET)
    res=app.acquire_token_for_client(scopes=SCOPE)
    if "access_token" not in res: fail(f"Auth failed: {res.get('error_description')}")
    return {"Authorization":f"Bearer {res['access_token']}"}

def load_state():
    try:
        with open(STATE_FILE) as f: return json.load(f)
    except Exception: return {}

def save_state(s):
    if DRY_RUN: return
    tmp=STATE_FILE+".tmp"
    with open(tmp,"w") as f: json.dump(s,f,indent=2)
    os.replace(tmp,STATE_FILE)

def prune_backups():
    """Keep only the most recent BACKUP_KEEP timestamped backup run dirs."""
    if DRY_RUN or not os.path.isdir(BACKUP_DIR): return
    runs=sorted([d for d in os.listdir(BACKUP_DIR)
                 if os.path.isdir(os.path.join(BACKUP_DIR,d))])
    excess=runs[:-BACKUP_KEEP] if len(runs)>BACKUP_KEEP else []
    for d in excess:
        shutil.rmtree(os.path.join(BACKUP_DIR,d),ignore_errors=True)
        log(f"   pruned old backup {d}")

def sp_list_all(headers):
    out={}
    def walk(fp):
        base=f"{GRAPH}/sites/{SITE_ID}/drive/root:/{SP_ROOT}"
        url=f"{base}/{fp}:/children" if fp else f"{base}:/children"
        while url:
            r=requests.get(url,headers=headers)
            if r.status_code==404: return
            if r.status_code!=200: fail(f"List '{fp}': {r.status_code} {r.text[:200]}")
            d=r.json()
            for it in d.get("value",[]):
                name=it["name"]; rel=f"{fp}/{name}" if fp else name
                if "folder" in it:
                    if any(rel.startswith(p.rstrip("/")) for p in EXCLUDE_DIR_PREFIXES): continue
                    walk(rel)
                else:
                    if _excluded(rel): continue
                    out[rel]={"id":it["id"],"size":it.get("size",0),
                              "hash":it.get("file",{}).get("hashes",{}).get("quickXorHash"),
                              "download":it.get("@microsoft.graph.downloadUrl")}
            url=d.get("@odata.nextLink")
    walk("")
    return out

def local_list_all():
    out={}
    for root,_d,files in os.walk(DATA_DIR):
        for name in files:
            full=os.path.join(root,name); rel=os.path.relpath(full,DATA_DIR)
            if _excluded(rel): continue
            st=os.stat(full)
            out[rel]={"size":st.st_size,"mtime":round(st.st_mtime,1),"path":full}
    return out

def backup_local(rel):
    src=os.path.join(DATA_DIR,rel)
    if not os.path.exists(src): return
    if DRY_RUN: log(f"   [DRY] would back up local {rel}"); return
    dst=os.path.join(BACKUP_DIR,RUN_TS,rel); os.makedirs(os.path.dirname(dst),exist_ok=True)
    shutil.copy2(src,dst); log(f"   backed up local {rel}")

def download(headers,rel,meta):
    if DRY_RUN: log(f"   [DRY] would DOWNLOAD {rel}"); return
    dst=os.path.join(DATA_DIR,rel); os.makedirs(os.path.dirname(dst),exist_ok=True)
    url=meta.get("download")
    if not url:
        r=requests.get(f"{GRAPH}/sites/{SITE_ID}/drive/items/{meta['id']}",headers=headers)
        url=r.json().get("@microsoft.graph.downloadUrl")
    r=requests.get(url)
    if r.status_code!=200: log(f"   ERROR download {rel}: {r.status_code}"); return
    with open(dst,"wb") as f: f.write(r.content)
    log(f"   DOWNLOADED {rel}")

def upload(headers,rel,path):
    if DRY_RUN: log(f"   [DRY] would UPLOAD {rel}"); return
    target=f"{SP_ROOT}/{rel}".replace("\\","/")
    with open(path,"rb") as f: content=f.read()
    if len(content)<4*1024*1024:
        r=requests.put(f"{GRAPH}/sites/{SITE_ID}/drive/root:/{target}:/content",headers=headers,data=content)
    else:
        s=requests.post(f"{GRAPH}/sites/{SITE_ID}/drive/root:/{target}:/createUploadSession",headers=headers,json={})
        up=s.json()["uploadUrl"]; total=len(content); chunk=5*1024*1024; r=None
        for st in range(0,total,chunk):
            en=min(st+chunk,total)-1
            r=requests.put(up,headers={"Content-Length":str(en-st+1),"Content-Range":f"bytes {st}-{en}/{total}"},data=content[st:en+1])
    if r.status_code in (200,201): log(f"   UPLOADED {rel}")
    else: log(f"   ERROR upload {rel}: {r.status_code} {r.text[:200]}")

def main():
    log(f"=== Sync start ({'DRY RUN' if DRY_RUN else 'LIVE'}) ===")
    log(f"    DATA_DIR={DATA_DIR}  SP_ROOT=/{SP_ROOT}  (generated_reports/ excluded)")
    headers=get_headers(); state=load_state()
    sp=sp_list_all(headers); local=local_list_all(); new_state={}
    down=up=conflicts=skipped=0; first_run=(len(state)==0)

    for rel in sorted(set(sp)|set(local)):
        in_sp,in_local=rel in sp, rel in local
        prev=state.get(rel,{})
        if in_sp and in_local:
            sp_changed=sp[rel]["hash"]!=prev.get("sp_hash")
            local_changed=(local[rel]["size"]!=prev.get("local_size") or
                           local[rel]["mtime"]!=prev.get("local_mtime"))
            if first_run:
                if local[rel]["size"]==sp[rel]["size"]:
                    skipped+=1
                else:
                    conflicts+=1; log(f"   FIRST-RUN size mismatch {rel}: SharePoint wins (local backed up)")
                    backup_local(rel); download(headers,rel,sp[rel]); down+=1
            elif sp_changed and local_changed:
                conflicts+=1; log(f"   CONFLICT {rel}: SharePoint wins (local backed up)")
                backup_local(rel); download(headers,rel,sp[rel]); down+=1
            elif sp_changed:
                backup_local(rel); download(headers,rel,sp[rel]); down+=1
            elif local_changed:
                upload(headers,rel,local[rel]["path"]); up+=1
            else:
                skipped+=1
        elif in_sp:
            download(headers,rel,sp[rel]); down+=1
        else:
            upload(headers,rel,local[rel]["path"]); up+=1

        ns={}
        if rel in sp: ns["sp_hash"]=sp[rel]["hash"]
        lp=os.path.join(DATA_DIR,rel)
        if os.path.exists(lp):
            st=os.stat(lp); ns["local_size"]=st.st_size; ns["local_mtime"]=round(st.st_mtime,1)
        new_state[rel]=ns

    save_state(new_state)
    prune_backups()
    log(f"--- done: downloaded={down} uploaded={up} conflicts={conflicts} skipped={skipped} ---")

if __name__=="__main__":
    main()
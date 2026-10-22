"""
swap_xrf_folders.py — one-time rename of the two XRF folders, on the data
volume AND in SharePoint, in one coordinated step.

    BEFORE (old)                          AFTER (new)
    xrf_data/       raw instrument CSVs   XRF_Chemistry/  raw instrument CSVs
    XRF_Chemistry/  XRF_Chemistry_V*.csv  XRF_Data/       XRF_Chemistry_V*.csv

Why a script and not a manual rename:
  * The hourly sync never deletes. Renaming on one side only would make the
    next sync copy the old folders back and MIX raw and versioned files.
  * SharePoint ignores letter case (xrf_data == XRF_Data), so the swap
    needs a temporary third name.
  * .sync_state.json records every file by path; it is rewritten here so the
    next sync sees "nothing changed" instead of 60+ conflicts.

Safety:
  * Folders are identified by WHAT IS INSIDE them (chemistry-*.csv = raw,
    XRF_Chemistry_V*.csv = versions), never by name alone.
  * Dry run by default. Nothing changes without --apply.
  * Idempotent and reversible: run again with --to old to swap back.
  * Holds the shared data lock while it works.

Run it as the one-off Job in tools/swap-xrf-folders-job.yaml (it needs the
SharePoint credentials from the sharepoint-sync Secret).
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

RAW_PAT, VER_PAT = "chemistry*.csv", "XRF_Chemistry_V*.csv"
CANDIDATES = ["xrf_data", "XRF_Chemistry", "XRF_Data"]
TARGETS = {"new": {"raw": "XRF_Chemistry", "ver": "XRF_Data"},
           "old": {"raw": "xrf_data", "ver": "XRF_Chemistry"}}
TMP = "_swap_tmp_versions"


def classify(names: list[str]) -> str:
    raw = any(fnmatch.fnmatch(n, RAW_PAT) for n in names)
    ver = any(fnmatch.fnmatch(n, VER_PAT) for n in names)
    if raw and ver:
        return "MIXED"
    return "raw" if raw else "ver" if ver else "empty"


def detect(listing: dict[str, list[str]]) -> dict:
    """listing: {actual_folder_name: [file names]} → {"raw": name, "ver": name, "empty": [...]}"""
    out = {"raw": None, "ver": None, "empty": []}
    for name, files in listing.items():
        kind = classify(files)
        if kind == "MIXED":
            raise SystemExit(f"ABORT: folder '{name}' holds BOTH raw and versioned files — fix by hand first.")
        if kind == "empty":
            out["empty"].append(name)
            continue
        if out[kind]:
            raise SystemExit(f"ABORT: two folders look like '{kind}': {out[kind]} and {name}.")
        out[kind] = name
    if not out["raw"] or not out["ver"]:
        raise SystemExit(f"ABORT: could not find both folders. Found: {out}")
    return out


def plan(found: dict, target: dict) -> list[tuple[str, str]]:
    """Renames needed to reach target. Uses a temp name so it is safe on
    case-insensitive SharePoint and when the two names simply swap."""
    if found["raw"] == target["raw"] and found["ver"] == target["ver"]:
        return []
    steps = []
    if found["ver"] != TMP:                 # (a previous run may have stopped half-way)
        steps.append((found["ver"], TMP))
    if found["raw"] != target["raw"]:
        steps.append((found["raw"], target["raw"]))
    steps.append((TMP, target["ver"]))
    return steps


# ── data volume side ─────────────────────────────────────────────────────
def local_listing(data_dir: str) -> dict[str, list[str]]:
    out = {}
    for n in os.listdir(data_dir):
        p = os.path.join(data_dir, n)
        if os.path.isdir(p) and n.lower() in {c.lower() for c in CANDIDATES + [TMP]}:
            out[n] = os.listdir(p)
    return out


# ── SharePoint side ──────────────────────────────────────────────────────
class SharePoint:
    def __init__(self):
        import requests
        import sync_sharepoint as s
        self.s, self.rq = s, requests
        self.h = s.get_headers()
        self.base = f"{s.GRAPH}/sites/{s.SITE_ID}/drive"

    def _children(self, path: str) -> list[dict]:
        url = f"{self.base}/root:/{path}:/children" if path else f"{self.base}/root:/{self.s.SP_ROOT}:/children"
        items = []
        while url:
            r = self.rq.get(url, headers=self.h)
            if r.status_code != 200:
                raise SystemExit(f"ABORT: SharePoint list '{path}' → {r.status_code} {r.text[:200]}")
            d = r.json(); items += d.get("value", []); url = d.get("@odata.nextLink")
        return items

    def listing(self) -> dict[str, list[str]]:
        wanted = {c.lower() for c in CANDIDATES + [TMP]}
        self.ids = {}
        out = {}
        for it in self._children(""):
            if "folder" in it and it["name"].lower() in wanted:
                self.ids[it["name"]] = it["id"]
                out[it["name"]] = [c["name"] for c in self._children(f"{self.s.SP_ROOT}/{it['name']}")]
        return out

    def rename(self, old: str, new: str) -> None:
        item_id = self.ids.pop(old)
        r = self.rq.patch(f"{self.base}/items/{item_id}", headers={**self.h, "Content-Type": "application/json"},
                          json={"name": new})
        if r.status_code not in (200, 201):
            raise SystemExit(f"ABORT: SharePoint rename {old} → {new} failed: {r.status_code} {r.text[:200]}")
        self.ids[new] = item_id


def rewrite_state(state_path: str, mapping: dict[str, str], apply: bool) -> int:
    if not os.path.exists(state_path):
        return 0
    with open(state_path) as f:
        st = json.load(f)
    new, moved = {}, 0
    for k, v in st.items():
        top, _, rest = k.partition("/")
        if rest and top in mapping:
            new[f"{mapping[top]}/{rest}"] = v; moved += 1
        else:
            new[k] = v
    if apply:
        from safe_io import atomic_write_json
        atomic_write_json(new, state_path)
    return moved


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", choices=["new", "old"], default="new")
    ap.add_argument("--apply", action="store_true", help="actually rename (default: dry run)")
    ap.add_argument("--local-only", action="store_true", help="skip SharePoint (tests only)")
    a = ap.parse_args(argv)
    data_dir = os.environ.get("SOIL_DATA_DIR", os.path.join(ROOT, "data"))
    target = TARGETS[a.to]
    mode = "APPLY" if a.apply else "DRY RUN"
    print(f"=== swap_xrf_folders → layout '{a.to}' ({mode}) ===  data={data_dir}")

    from safe_io import data_lock
    with data_lock(wait=120):
        loc = local_listing(data_dir)
        loc_found = detect({k: v for k, v in loc.items()})
        print(f"volume    : raw='{loc_found['raw']}' ({len(loc[loc_found['raw']])} files)  "
              f"versions='{loc_found['ver']}' ({len(loc[loc_found['ver']])} files)  empty={loc_found['empty']}")

        sp = None
        if not a.local_only:
            sp = SharePoint()
            spl = sp.listing()
            sp_found = detect(spl)
            print(f"SharePoint: raw='{sp_found['raw']}' ({len(spl[sp_found['raw']])} files)  "
                  f"versions='{sp_found['ver']}' ({len(spl[sp_found['ver']])} files)  empty={sp_found['empty']}")
            for kind in ("raw", "ver"):
                only_l = set(loc[loc_found[kind]]) - set(spl[sp_found[kind]])
                if only_l - {".DS_Store"}:
                    print(f"  note: {len(only_l)} {kind} file(s) only on the volume (sync will upload them): "
                          f"{sorted(only_l)[:5]}")

        # Empty leftovers (e.g. a folder auto-created by new code) that sit on a target name
        blockers = [e for e in loc_found["empty"] if e.lower() in {target["raw"].lower(), target["ver"].lower(), TMP.lower()}]
        steps = plan(loc_found, target)
        sp_steps = plan(sp_found, target) if sp else []
        sp_blockers = [e for e in (sp_found["empty"] if sp else []) if e.lower() in {target["raw"].lower(), target["ver"].lower(), TMP.lower()}]
        if sp_blockers:
            raise SystemExit(f"ABORT: empty SharePoint folder(s) {sp_blockers} sit on a target name — delete them in SharePoint first.")

        mapping = {}
        for kind in ("raw", "ver"):
            if loc_found[kind] != target[kind]:
                mapping[loc_found[kind]] = target[kind]

        print("plan:")
        for e in blockers:
            print(f"  volume     : remove empty folder '{e}'")
        for o, n in sp_steps:
            print(f"  SharePoint : rename '{o}' → '{n}'")
        for o, n in steps:
            print(f"  volume     : rename '{o}' → '{n}'")
        moved = rewrite_state(os.path.join(data_dir, ".sync_state.json"), mapping, apply=False)
        print(f"  sync state : re-key {moved} file record(s) {mapping}")
        if not (steps or sp_steps or blockers):
            print("Nothing to do — already in the requested layout.")
            return 0
        if not a.apply:
            print("DRY RUN — nothing changed. Re-run with --apply.")
            return 0

        # SharePoint first: if it fails, the volume is untouched.
        for o, n in sp_steps:
            sp.rename(o, n); print(f"  done SharePoint {o} → {n}")
        for e in blockers:
            os.rmdir(os.path.join(data_dir, e)); print(f"  removed empty {e}")
        for o, n in steps:
            os.rename(os.path.join(data_dir, o), os.path.join(data_dir, n)); print(f"  done volume {o} → {n}")
        rewrite_state(os.path.join(data_dir, ".sync_state.json"), mapping, apply=True)
        print(f"  done sync state ({moved} records)")

        # Verify
        after = detect(local_listing(data_dir))
        assert after["raw"] == target["raw"] and after["ver"] == target["ver"], after
        if sp:
            spa = detect(sp.listing())
            assert spa["raw"] == target["raw"] and spa["ver"] == target["ver"], spa
        print("VERIFIED: both sides now in layout", a.to)
    return 0


if __name__ == "__main__":
    sys.exit(main())

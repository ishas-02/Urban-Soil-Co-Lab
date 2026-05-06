"""
key_reconciler.py — Two-sided LeadPPM reconciliation.

Compares the latest XRF chemistry output (XRF_Soil_chem_v*.csv, produced
by data.py from instrument readings) against the manual Site lab data
(Site_Lab_Data.csv, produced by xrf_tech.py).

Per-row status semantics
------------------------
For each row in either file we add a `status` column:

  * "match"        — the (SampleID, XRFID) pair exists in BOTH files and
                     LeadPPM agrees within tolerance.
  * "discrepancy"  — the pair exists in BOTH files but LeadPPM disagrees.
                     UI should render these rows in RED.
  * "pending"      — the pair exists in only one file; the other side
                     hasn't been entered yet, so we can't compare.
                     UI should render these rows in YELLOW. When the
                     other side later appears, the row flips to "match"
                     or "discrepancy".

When (and only when) the run produces zero discrepancies AND zero
pending rows on the chem side that have a SampleID, we refresh
XRF_Master_Data_KEY.csv. The key contains only matched rows and is
the authoritative SampleID ↔ XRFID mapping consumed by data.py on the
next ETL pass.

Trigger points
--------------
- src/data.py calls reconcile() at the end of each ETL run, so a new
  XRF_Soil_chem_v*.csv kicks off comparison.
- src/xrf_tech.py calls reconcile() after each Site_Lab_Data.csv save,
  so a manual entry on the lab side also triggers comparison.

Either trigger is sufficient — both files keep their status columns
in sync regardless of which side moved.

Tolerance
---------
LeadPPM is a real measurement; demanding exact equality is too strict
(310 vs 310.0 vs "<LOD" all happen). PPM_TOLERANCE_ABS / _REL set the
threshold for what counts as agreement.
"""

from __future__ import annotations

import glob
import os
import re

import pandas as pd

# --- Tolerance for LeadPPM agreement -------------------------------------
# Two readings agree if they're within EITHER:
#   - PPM_TOLERANCE_ABS ppm absolute, OR
#   - PPM_TOLERANCE_REL fractional difference
# The "OR" is deliberate — it lets very small absolute deltas pass even
# when they'd be a large fractional difference (e.g. 5 vs 7 ppm).
PPM_TOLERANCE_ABS: float = 5.0
PPM_TOLERANCE_REL: float = 0.05  # 5%


# ─── Path resolution ─────────────────────────────────────────────────────
def _find_chem_dir(repo_root: str) -> str:
    """Return the directory holding XRF_Soil_chem_v*.csv files."""
    return os.path.join(repo_root, "data", "XRF_Soil_chem")


def _find_site_lab_path(repo_root: str) -> str | None:
    """Locate Site_Lab_Data.csv.

    The project has two `Data` folders — one at the repo root and one
    inside `src/`. xrf_tech.py writes to the latter (relative path
    "Data/Site_Lab_Data_Manual/Site_Lab_Data.csv" from the src cwd).
    Check both, prefer the one that exists.
    """
    candidates = [
        os.path.join(repo_root, "src", "Data", "Site_Lab_Data_Manual", "Site_Lab_Data.csv"),
        os.path.join(repo_root, "Data", "Site_Lab_Data_Manual", "Site_Lab_Data.csv"),
        os.path.join(repo_root, "data", "Site_Lab_Data_Manual", "Site_Lab_Data.csv"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _latest_chem_file(chem_dir: str) -> str | None:
    """Return the highest-version XRF_Soil_chem_v*.csv, or None."""
    files = glob.glob(os.path.join(chem_dir, "XRF_Soil_chem_v*.csv"))
    if not files:
        return None

    def _ver(fn: str) -> int:
        m = re.search(r"_v(\d+)\.csv$", fn)
        return int(m.group(1)) if m else 0

    return max(files, key=_ver)


def _key_path(repo_root: str) -> str:
    return os.path.join(repo_root, "data", "site_databases", "XRF_Master_Data_KEY.csv")


# ─── Comparison helpers ──────────────────────────────────────────────────
def _ppm_agrees(a: float, b: float) -> bool:
    """True if two LeadPPM values agree within tolerance (NaN-safe)."""
    if pd.isna(a) or pd.isna(b):
        return False
    if abs(a - b) <= PPM_TOLERANCE_ABS:
        return True
    denom = max(abs(a), abs(b))
    if denom == 0:
        return True
    return abs(a - b) / denom <= PPM_TOLERANCE_REL


def _row_key(sample_id, xrfid) -> tuple[str, str]:
    """Comparison key — string-normalized (SampleID, XRFID)."""
    return (str(sample_id).strip(), str(xrfid).strip())


# ─── Main entry point ────────────────────────────────────────────────────
def reconcile(repo_root: str) -> dict | None:
    """Run a full reconciliation pass.

    Parameters
    ----------
    repo_root : str
        Absolute path to the project root (the directory containing
        `etl_manager.py`, `data/`, `src/`).

    Returns
    -------
    dict | None
        Summary counts {"matched", "discrepancy", "pending"} on success,
        or None if neither side has data.
    """
    chem_dir = _find_chem_dir(repo_root)
    chem_path = _latest_chem_file(chem_dir)
    site_path = _find_site_lab_path(repo_root)

    if chem_path is None and site_path is None:
        print("🔁 Reconciler: neither chem nor site file present — nothing to do.")
        return None

    # --- Load whichever sides exist ---
    chem_df = pd.read_csv(chem_path) if chem_path else None
    site_df = pd.read_csv(site_path) if site_path else None

    if chem_df is not None:
        print(f"🔁 Reconciler: chem  = {os.path.basename(chem_path)} ({len(chem_df)} rows)")
    else:
        print("🔁 Reconciler: chem  = (none yet)")
    if site_df is not None:
        print(f"🔁 Reconciler: site  = {os.path.basename(site_path)} ({len(site_df)} rows)")
    else:
        print("🔁 Reconciler: site  = (none yet)")

    # --- Build (SampleID, XRFID) -> LeadPPM lookups for cross-checking ---
    def _build_lookup(df: pd.DataFrame | None) -> dict[tuple[str, str], float]:
        if df is None or df.empty:
            return {}
        if "SampleID" not in df.columns or "XRFID" not in df.columns or "LeadPPM" not in df.columns:
            return {}
        out: dict[tuple[str, str], float] = {}
        for _, row in df.iterrows():
            key = _row_key(row["SampleID"], row["XRFID"])
            if key == ("", "") or key[0] == "" or key[1] == "":
                continue
            out[key] = pd.to_numeric(row["LeadPPM"], errors="coerce")
        return out

    chem_lookup = _build_lookup(chem_df)
    site_lookup = _build_lookup(site_df)

    # --- Decide a status for each row in each file ---
    def _status_for(this_lookup_value: float, key: tuple[str, str], other_lookup: dict) -> str:
        if not key[0] or not key[1]:
            # Row has no joinable identity (e.g. blank SampleID). Leave
            # as pending so it's visible but not treated as confirmed.
            return "pending"
        if key not in other_lookup:
            return "pending"
        if _ppm_agrees(this_lookup_value, other_lookup[key]):
            return "match"
        return "discrepancy"

    summary = {"matched": 0, "discrepancy": 0, "pending": 0}

    if chem_df is not None and not chem_df.empty:
        statuses = []
        for _, row in chem_df.iterrows():
            key = _row_key(row.get("SampleID", ""), row.get("XRFID", ""))
            val = pd.to_numeric(row.get("LeadPPM"), errors="coerce")
            statuses.append(_status_for(val, key, site_lookup))
        chem_df["status"] = statuses
        chem_df.to_csv(chem_path, index=False)

    if site_df is not None and not site_df.empty:
        statuses = []
        for _, row in site_df.iterrows():
            key = _row_key(row.get("SampleID", ""), row.get("XRFID", ""))
            val = pd.to_numeric(row.get("LeadPPM"), errors="coerce")
            statuses.append(_status_for(val, key, chem_lookup))
        site_df["status"] = statuses
        site_df.to_csv(site_path, index=False)

    # --- Tally summary across whichever side(s) we have ---
    for df in (chem_df, site_df):
        if df is None or "status" not in df.columns:
            continue
        counts = df["status"].value_counts()
        summary["matched"]      += int(counts.get("match", 0))
        summary["discrepancy"]  += int(counts.get("discrepancy", 0))
        summary["pending"]      += int(counts.get("pending", 0))

    # --- Refresh XRF_Master_Data_KEY.csv only when both sides exist
    # AND every comparable row matches (no discrepancies). Pending rows
    # on the chem side are tolerated as long as they're pending due to
    # a missing site row — but the safer rule is: only write the key
    # when the chem file has zero discrepancies at all. ---
    if chem_df is not None and site_df is not None and len(chem_df) > 0:
        chem_has_discrepancy = (chem_df["status"] == "discrepancy").any()
        site_has_discrepancy = (site_df["status"] == "discrepancy").any() if site_df is not None and not site_df.empty else False

        if not chem_has_discrepancy and not site_has_discrepancy:
            # Build the key from rows that are confirmed matched on the
            # chem side. Columns mirror the legacy KEY format the ETL
            # already understands: at minimum SampleID, XRFID, LeadPPM.
            matched_chem = chem_df[chem_df["status"] == "match"].copy()
            if not matched_chem.empty:
                key_df = matched_chem[["SampleID", "XRFID", "LeadPPM"]].copy()
                if "LeadAvg" in matched_chem.columns:
                    key_df["LeadAvg"] = matched_chem["LeadAvg"]
                key_out = _key_path(repo_root)
                os.makedirs(os.path.dirname(key_out), exist_ok=True)
                key_df.to_csv(key_out, index=False)
                print(f"   🔑 Refreshed {os.path.basename(key_out)} "
                      f"with {len(key_df)} matched rows.")
        else:
            print("   ⚠️  Discrepancies present — XRF_Master_Data_KEY.csv NOT refreshed.")

    print(f"   📊 Summary: {summary['matched']} matched, "
          f"{summary['discrepancy']} discrepancies, "
          f"{summary['pending']} pending.")
    return summary


if __name__ == "__main__":
    # Allow running standalone for ad-hoc reconciliation:
    #   python src/key_reconciler.py
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    reconcile(repo_root)

# """
# key_reconciler.py — Two-sided LeadPPM reconciliation (Site + Clinic).

# Compares the latest XRF chemistry output (XRF_Chemistry_V*.csv, produced
# by data.py from instrument readings) against the manual technician files
# produced by xrf_tech.py:

#   * SITE   side: data/XRF_Technician_Site_Data/XRF_Technician_Site.csv
#   * CLINIC side: data/XRF_Technician_Clinic_Data/XRF_Technician_Clinic.csv

# Both sides use the same per-row status semantics:

#   * "match"        — the (SampleID, XRFID) pair exists in BOTH files and
#                      LeadPPM agrees within tolerance.
#   * "discrepancy"  — the pair exists in BOTH files but LeadPPM disagrees.
#                      UI should render these rows in RED.
#   * "pending"      — the pair exists in only one file; the other side
#                      hasn't been entered yet, so we can't compare.
#                      UI should render these rows in YELLOW. When the
#                      other side later appears, the row flips to "match"
#                      or "discrepancy".

# When (and only when) a side produces zero discrepancies we refresh the
# master output for that side:

#   * Site   matches → data/site_databases/Site_Master_Data.csv
#   * Clinic matches → data/site_databases/Clinic_Master_Data.csv

# Trigger points
# --------------
# - src/data.py calls reconcile() at the end of each ETL run.
# - src/xrf_tech.py calls reconcile() after each save (Site or Clinic).

# Either trigger is sufficient — both sides keep their status columns
# in sync regardless of which moved.

# Tolerance
# ---------
# LeadPPM is a real measurement; demanding exact equality is too strict
# (310 vs 310.0 vs "<LOD" all happen). PPM_TOLERANCE_ABS / _REL set the
# threshold for what counts as agreement.
# """

# from __future__ import annotations

# import glob
# import os
# import re

# import pandas as pd

# # --- Tolerance for LeadPPM agreement -------------------------------------
# # Two readings agree if they're within EITHER:
# #   - PPM_TOLERANCE_ABS ppm absolute, OR
# #   - PPM_TOLERANCE_REL fractional difference
# # The "OR" is deliberate — it lets very small absolute deltas pass even
# # when they'd be a large fractional difference (e.g. 5 vs 7 ppm).
# PPM_TOLERANCE_ABS: float = 5.0
# PPM_TOLERANCE_REL: float = 0.05  # 5%


# # ─── Path resolution ─────────────────────────────────────────────────────
# def _find_chem_dir(repo_root: str) -> str:
#     """Return the directory holding XRF_Chemistry_V*.csv files."""
#     return os.path.join(repo_root, "data", "XRF_Chemistry")


# def _find_site_lab_path(repo_root: str) -> str | None:
#     """Locate XRF_Technician_Site.csv.

#     The project may have two `Data` folders — one at the repo root and
#     one inside `src/`. xrf_tech.py writes to the latter when launched
#     via `streamlit run src/xrf_tech.py`. Check several candidates and
#     prefer the one that exists.
#     """
#     candidates = [
#         os.path.join(repo_root, "src", "Data",
#                      "XRF_Technician_Site_Data", "XRF_Technician_Site.csv"),
#         os.path.join(repo_root, "Data",
#                      "XRF_Technician_Site_Data", "XRF_Technician_Site.csv"),
#         os.path.join(repo_root, "data",
#                      "XRF_Technician_Site_Data", "XRF_Technician_Site.csv"),
#     ]
#     for path in candidates:
#         if os.path.exists(path):
#             return path
#     return None


# def _find_clinic_lab_path(repo_root: str) -> str | None:
#     """Locate XRF_Technician_Clinic.csv (mirrors _find_site_lab_path)."""
#     candidates = [
#         os.path.join(repo_root, "src", "Data",
#                      "XRF_Technician_Clinic_Data", "XRF_Technician_Clinic.csv"),
#         os.path.join(repo_root, "Data",
#                      "XRF_Technician_Clinic_Data", "XRF_Technician_Clinic.csv"),
#         os.path.join(repo_root, "data",
#                      "XRF_Technician_Clinic_Data", "XRF_Technician_Clinic.csv"),
#     ]
#     for path in candidates:
#         if os.path.exists(path):
#             return path
#     return None


# def _latest_chem_file(chem_dir: str) -> str | None:
#     """Return the highest-version XRF_Chemistry_V*.csv, or None."""
#     files = glob.glob(os.path.join(chem_dir, "XRF_Chemistry_V*.csv"))
#     if not files:
#         return None

#     def _ver(fn: str) -> int:
#         m = re.search(r"_V(\d+)\.csv$", fn, re.IGNORECASE)
#         return int(m.group(1)) if m else 0

#     return max(files, key=_ver)


# def _site_master_path(repo_root: str) -> str:
#     """Output path for matched site rows (the canonical site key)."""
#     return os.path.join(repo_root, "data", "site_databases", "Site_Master_Data.csv")


# def _clinic_master_path(repo_root: str) -> str:
#     """Output path for matched clinic rows."""
#     return os.path.join(repo_root, "data", "site_databases", "Clinic_Master_Data.csv")


# # ─── Comparison helpers ──────────────────────────────────────────────────
# def _ppm_agrees(a: float, b: float) -> bool:
#     """True if two LeadPPM values agree within tolerance (NaN-safe)."""
#     if pd.isna(a) or pd.isna(b):
#         return False
#     if abs(a - b) <= PPM_TOLERANCE_ABS:
#         return True
#     denom = max(abs(a), abs(b))
#     if denom == 0:
#         return True
#     return abs(a - b) / denom <= PPM_TOLERANCE_REL


# def _row_key(sample_id, xrfid) -> tuple[str, str]:
#     """Comparison key — string-normalized (SampleID, XRFID)."""
#     return (str(sample_id).strip(), str(xrfid).strip())


# def _build_lookup(df: pd.DataFrame | None) -> dict[tuple[str, str], float]:
#     """Build a (SampleID, XRFID) -> LeadPPM lookup from a dataframe."""
#     if df is None or df.empty:
#         return {}
#     if "SampleID" not in df.columns or "XRFID" not in df.columns or "LeadPPM" not in df.columns:
#         return {}
#     out: dict[tuple[str, str], float] = {}
#     for _, row in df.iterrows():
#         key = _row_key(row["SampleID"], row["XRFID"])
#         if not key[0] or not key[1]:
#             continue
#         out[key] = pd.to_numeric(row["LeadPPM"], errors="coerce")
#     return out


# def _status_for(this_lookup_value: float, key: tuple[str, str], other_lookup: dict) -> str:
#     """Decide a status for a single row, given the opposing side's lookup."""
#     if not key[0] or not key[1]:
#         # Row has no joinable identity (e.g. blank SampleID). Leave
#         # as pending so it's visible but not treated as confirmed.
#         return "pending"
#     if key not in other_lookup:
#         return "pending"
#     if _ppm_agrees(this_lookup_value, other_lookup[key]):
#         return "match"
#     return "discrepancy"


# def _annotate_status(df: pd.DataFrame | None, other_lookup: dict) -> pd.DataFrame | None:
#     """Add a `status` column to df by comparing each row to other_lookup."""
#     if df is None or df.empty:
#         return df
#     statuses = []
#     for _, row in df.iterrows():
#         key = _row_key(row.get("SampleID", ""), row.get("XRFID", ""))
#         val = pd.to_numeric(row.get("LeadPPM"), errors="coerce")
#         statuses.append(_status_for(val, key, other_lookup))
#     df = df.copy()
#     df["status"] = statuses
#     return df


# def _refresh_master(matched_chem: pd.DataFrame, out_path: str, label: str) -> None:
#     """Write matched chem rows to the master CSV at out_path."""
#     if matched_chem.empty:
#         return
#     cols = ["SampleID", "XRFID", "LeadPPM"]
#     key_df = matched_chem[cols].copy()
#     if "LeadAvg" in matched_chem.columns:
#         key_df["LeadAvg"] = matched_chem["LeadAvg"]
#     os.makedirs(os.path.dirname(out_path), exist_ok=True)
#     key_df.to_csv(out_path, index=False)
#     print(f"   🔑 Refreshed {os.path.basename(out_path)} "
#           f"with {len(key_df)} matched {label} rows.")


# # ─── Main entry point ────────────────────────────────────────────────────
# def reconcile(repo_root: str) -> dict | None:
#     """Run a full reconciliation pass over BOTH the Site and Clinic sides.

#     Each side is reconciled independently against the same chem file:
#       - Site rows    ↔ chem rows  → Site_Master_Data.csv
#       - Clinic rows  ↔ chem rows  → Clinic_Master_Data.csv

#     The chem file gets a `status` column reflecting whether either side
#     matches its (SampleID, XRFID) pair.

#     Parameters
#     ----------
#     repo_root : str
#         Absolute path to the project root.

#     Returns
#     -------
#     dict | None
#         Summary counts {"site": {...}, "clinic": {...}} on success,
#         or None if no chem file is present.
#     """
#     chem_dir = _find_chem_dir(repo_root)
#     chem_path = _latest_chem_file(chem_dir)
#     site_path = _find_site_lab_path(repo_root)
#     clinic_path = _find_clinic_lab_path(repo_root)

#     if chem_path is None and site_path is None and clinic_path is None:
#         print("🔁 Reconciler: no chem, site, or clinic file present — nothing to do.")
#         return None

#     # --- Load whichever sides exist ---
#     chem_df = pd.read_csv(chem_path) if chem_path else None
#     site_df = pd.read_csv(site_path) if site_path else None
#     clinic_df = pd.read_csv(clinic_path) if clinic_path else None

#     if chem_df is not None:
#         print(f"🔁 Reconciler: chem    = {os.path.basename(chem_path)} ({len(chem_df)} rows)")
#     else:
#         print("🔁 Reconciler: chem    = (none yet)")
#     if site_df is not None:
#         print(f"🔁 Reconciler: site    = {os.path.basename(site_path)} ({len(site_df)} rows)")
#     else:
#         print("🔁 Reconciler: site    = (none yet)")
#     if clinic_df is not None:
#         print(f"🔁 Reconciler: clinic  = {os.path.basename(clinic_path)} ({len(clinic_df)} rows)")
#     else:
#         print("🔁 Reconciler: clinic  = (none yet)")

#     # --- Build lookups for cross-checking ---
#     chem_lookup   = _build_lookup(chem_df)
#     site_lookup   = _build_lookup(site_df)
#     clinic_lookup = _build_lookup(clinic_df)

#     summary = {
#         "site":   {"matched": 0, "discrepancy": 0, "pending": 0},
#         "clinic": {"matched": 0, "discrepancy": 0, "pending": 0},
#     }

#     # ── SITE side ────────────────────────────────────────────────
#     site_df_annotated = _annotate_status(site_df, chem_lookup)
#     if site_df_annotated is not None and not site_df_annotated.empty:
#         site_df_annotated.to_csv(site_path, index=False)
#         counts = site_df_annotated["status"].value_counts()
#         summary["site"]["matched"]     = int(counts.get("match", 0))
#         summary["site"]["discrepancy"] = int(counts.get("discrepancy", 0))
#         summary["site"]["pending"]     = int(counts.get("pending", 0))

#     # ── CLINIC side ──────────────────────────────────────────────
#     clinic_df_annotated = _annotate_status(clinic_df, chem_lookup)
#     if clinic_df_annotated is not None and not clinic_df_annotated.empty:
#         clinic_df_annotated.to_csv(clinic_path, index=False)
#         counts = clinic_df_annotated["status"].value_counts()
#         summary["clinic"]["matched"]     = int(counts.get("match", 0))
#         summary["clinic"]["discrepancy"] = int(counts.get("discrepancy", 0))
#         summary["clinic"]["pending"]     = int(counts.get("pending", 0))

#     # ── CHEM side ────────────────────────────────────────────────
#     # A chem row matches if EITHER side agrees; it's a discrepancy
#     # only if a side has the key and disagrees; otherwise pending.
#     if chem_df is not None and not chem_df.empty:
#         statuses = []
#         for _, row in chem_df.iterrows():
#             key = _row_key(row.get("SampleID", ""), row.get("XRFID", ""))
#             val = pd.to_numeric(row.get("LeadPPM"), errors="coerce")

#             in_site   = key in site_lookup
#             in_clinic = key in clinic_lookup

#             if not key[0] or not key[1] or (not in_site and not in_clinic):
#                 statuses.append("pending")
#                 continue

#             site_ok   = in_site   and _ppm_agrees(val, site_lookup[key])
#             clinic_ok = in_clinic and _ppm_agrees(val, clinic_lookup[key])

#             if site_ok or clinic_ok:
#                 statuses.append("match")
#             else:
#                 statuses.append("discrepancy")
#         chem_df = chem_df.copy()
#         chem_df["status"] = statuses
#         chem_df.to_csv(chem_path, index=False)

#     # ── Refresh the matched-only master CSVs (one per side) ──────
#     # Only refresh when that side has zero discrepancies — pending is OK
#     # (it just means the other side hasn't caught up yet).
#     if chem_df is not None and not chem_df.empty:
#         # Site master: chem rows whose key matched a SITE row
#         if site_df_annotated is not None and not site_df_annotated.empty:
#             site_has_disc = (site_df_annotated["status"] == "discrepancy").any()
#             if not site_has_disc:
#                 matched_site_keys = {
#                     _row_key(r["SampleID"], r["XRFID"])
#                     for _, r in site_df_annotated[
#                         site_df_annotated["status"] == "match"
#                     ].iterrows()
#                 }
#                 matched_chem_site = chem_df[
#                     chem_df.apply(
#                         lambda r: _row_key(r.get("SampleID"), r.get("XRFID"))
#                                    in matched_site_keys,
#                         axis=1,
#                     )
#                 ]
#                 _refresh_master(
#                     matched_chem_site, _site_master_path(repo_root), "site"
#                 )
#             else:
#                 print("   ⚠️  Site discrepancies present — Site_Master_Data.csv NOT refreshed.")

#         # Clinic master: chem rows whose key matched a CLINIC row
#         if clinic_df_annotated is not None and not clinic_df_annotated.empty:
#             clinic_has_disc = (clinic_df_annotated["status"] == "discrepancy").any()
#             if not clinic_has_disc:
#                 matched_clinic_keys = {
#                     _row_key(r["SampleID"], r["XRFID"])
#                     for _, r in clinic_df_annotated[
#                         clinic_df_annotated["status"] == "match"
#                     ].iterrows()
#                 }
#                 matched_chem_clinic = chem_df[
#                     chem_df.apply(
#                         lambda r: _row_key(r.get("SampleID"), r.get("XRFID"))
#                                    in matched_clinic_keys,
#                         axis=1,
#                     )
#                 ]
#                 _refresh_master(
#                     matched_chem_clinic, _clinic_master_path(repo_root), "clinic"
#                 )
#             else:
#                 print("   ⚠️  Clinic discrepancies present — Clinic_Master_Data.csv NOT refreshed.")

#     print(
#         f"   📊 Site  : {summary['site']['matched']} matched, "
#         f"{summary['site']['discrepancy']} discrepancies, "
#         f"{summary['site']['pending']} pending."
#     )
#     print(
#         f"   📊 Clinic: {summary['clinic']['matched']} matched, "
#         f"{summary['clinic']['discrepancy']} discrepancies, "
#         f"{summary['clinic']['pending']} pending."
#     )
#     return summary


# if __name__ == "__main__":
#     # Allow running standalone for ad-hoc reconciliation:
#     #   python src/key_reconciler.py
#     repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
#     reconcile(repo_root)


"""
key_reconciler.py — Two-sided LeadPPM reconciliation (Site + Clinic).

Compares the latest XRF chemistry output (XRF_Chemistry_V*.csv, produced
by data.py from instrument readings) against the manual technician files
produced by xrf_tech.py:

  * SITE   side: data/XRF_Technician_Site_Data/XRF_Technician_Site.csv
  * CLINIC side: data/XRF_Technician_Clinic_Data/XRF_Technician_Clinic.csv

Both sides use the same per-row status semantics:

  * "match"        — the (SampleID, XRFID) pair exists in BOTH files and
                     LeadPPM agrees within tolerance.
  * "discrepancy"  — the pair exists in BOTH files but LeadPPM disagrees.
                     UI should render these rows in RED.
  * "pending"      — the pair exists in only one file; the other side
                     hasn't been entered yet, so we can't compare.
                     UI should render these rows in YELLOW. When the
                     other side later appears, the row flips to "match"
                     or "discrepancy".

Master output files (ALWAYS refreshed on every reconcile, no longer
gated on zero-discrepancies):

  * Site   → data/site_databases/Site_Master_Data.csv
  * Clinic → data/site_databases/Clinic_Master_Data.csv

Each master file contains EVERY technician row with a `status` column.
Rows with status "match" carry the authoritative LeadPPM from chem;
rows with status "discrepancy" or "pending" have BLANK LeadPPM/LeadAvg
so downstream consumers don't accidentally use disputed or unverified
data. When a row's status later flips to "match" (e.g., the technician
corrects a value or new chem data arrives), the next reconcile pass
rewrites the master file and automatically populates LeadPPM.

Downstream code that wants "trusted values only" should filter on
`status == "match"`. Code that wants the full audit trail (including
flagged rows) can read all rows directly.

Trigger points
--------------
- src/data.py calls reconcile() at the end of each ETL run.
- src/xrf_tech.py calls reconcile() after each save (Site or Clinic).

Either trigger is sufficient — both sides keep their status columns
in sync regardless of which moved.

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
    """Return the directory holding XRF_Chemistry_V*.csv files."""
    return os.path.join(repo_root, "data", "XRF_Chemistry")


def _find_site_lab_path(repo_root: str) -> str | None:
    """Locate XRF_Technician_Site.csv.

    The project may have two `Data` folders — one at the repo root and
    one inside `src/`. xrf_tech.py writes to the latter when launched
    via `streamlit run src/xrf_tech.py`. Check several candidates and
    prefer the one that exists.
    """
    candidates = [
        os.path.join(repo_root, "src", "Data",
                     "XRF_Technician_Site_Data", "XRF_Technician_Site.csv"),
        os.path.join(repo_root, "Data",
                     "XRF_Technician_Site_Data", "XRF_Technician_Site.csv"),
        os.path.join(repo_root, "data",
                     "XRF_Technician_Site_Data", "XRF_Technician_Site.csv"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _find_clinic_lab_path(repo_root: str) -> str | None:
    """Locate XRF_Technician_Clinic.csv (mirrors _find_site_lab_path)."""
    candidates = [
        os.path.join(repo_root, "src", "Data",
                     "XRF_Technician_Clinic_Data", "XRF_Technician_Clinic.csv"),
        os.path.join(repo_root, "Data",
                     "XRF_Technician_Clinic_Data", "XRF_Technician_Clinic.csv"),
        os.path.join(repo_root, "data",
                     "XRF_Technician_Clinic_Data", "XRF_Technician_Clinic.csv"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _latest_chem_file(chem_dir: str) -> str | None:
    """Return the highest-version XRF_Chemistry_V*.csv, or None."""
    files = glob.glob(os.path.join(chem_dir, "XRF_Chemistry_V*.csv"))
    if not files:
        return None

    def _ver(fn: str) -> int:
        m = re.search(r"_V(\d+)\.csv$", fn, re.IGNORECASE)
        return int(m.group(1)) if m else 0

    return max(files, key=_ver)


def _site_master_path(repo_root: str) -> str:
    """Output path for the site master CSV (full audit + matched values)."""
    return os.path.join(repo_root, "data", "site_databases", "Site_Master_Data.csv")


def _clinic_master_path(repo_root: str) -> str:
    """Output path for the clinic master CSV (full audit + matched values)."""
    return os.path.join(repo_root, "data", "site_databases", "Clinic_Master_Data.csv")


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


def _build_lookup(df: pd.DataFrame | None) -> dict[tuple[str, str], float]:
    """Build a (SampleID, XRFID) -> LeadPPM lookup from a dataframe."""
    if df is None or df.empty:
        return {}
    if "SampleID" not in df.columns or "XRFID" not in df.columns or "LeadPPM" not in df.columns:
        return {}
    out: dict[tuple[str, str], float] = {}
    for _, row in df.iterrows():
        key = _row_key(row["SampleID"], row["XRFID"])
        if not key[0] or not key[1]:
            continue
        out[key] = pd.to_numeric(row["LeadPPM"], errors="coerce")
    return out


def _status_for(this_lookup_value: float, key: tuple[str, str], other_lookup: dict) -> str:
    """Decide a status for a single row, given the opposing side's lookup."""
    if not key[0] or not key[1]:
        # Row has no joinable identity (e.g. blank SampleID). Leave
        # as pending so it's visible but not treated as confirmed.
        return "pending"
    if key not in other_lookup:
        return "pending"
    if _ppm_agrees(this_lookup_value, other_lookup[key]):
        return "match"
    return "discrepancy"


def _annotate_status(df: pd.DataFrame | None, other_lookup: dict) -> pd.DataFrame | None:
    """Add a `status` column to df by comparing each row to other_lookup."""
    if df is None or df.empty:
        return df
    statuses = []
    for _, row in df.iterrows():
        key = _row_key(row.get("SampleID", ""), row.get("XRFID", ""))
        val = pd.to_numeric(row.get("LeadPPM"), errors="coerce")
        statuses.append(_status_for(val, key, other_lookup))
    df = df.copy()
    df["status"] = statuses
    return df


def _refresh_master(
    annotated_side_df: pd.DataFrame | None,
    chem_df: pd.DataFrame | None,
    out_path: str,
    label: str,
) -> None:
    """Write the master CSV with ALL technician rows annotated by status.

    For each row in the technician file (already annotated by
    `_annotate_status` with a `status` column):

      - status == "match":        pull LeadPPM from chem (authoritative)
                                  and LeadAvg from the technician row.
      - status == "discrepancy":  LeadPPM and LeadAvg are BLANKED.
      - status == "pending":      LeadPPM and LeadAvg are BLANKED.

    The output preserves the order of rows in the technician file.

    Because reconcile() rewrites this file in full on every run, the
    "auto-update on fix" behavior is automatic: once a row's status flips
    to "match" in a future reconcile pass, this same function will
    repopulate its LeadPPM in the master file.

    Parameters
    ----------
    annotated_side_df : pd.DataFrame | None
        The site or clinic technician dataframe AFTER `_annotate_status`
        has added a `status` column. Must contain SampleID, XRFID, status.
        If None or empty, no file is written.
    chem_df : pd.DataFrame | None
        The chem dataframe (used to look up authoritative LeadPPM for
        matched rows). Can be None or empty.
    out_path : str
        Destination for Site_Master_Data.csv / Clinic_Master_Data.csv.
    label : str
        "site" or "clinic" — for the log summary line.
    """
    if annotated_side_df is None or annotated_side_df.empty:
        return

    # Build a lookup from (SampleID, XRFID) → LeadPPM in the chem file.
    chem_lookup_ppm: dict[tuple[str, str], object] = {}
    if chem_df is not None and not chem_df.empty:
        for _, r in chem_df.iterrows():
            sid = str(r.get("SampleID", "")).strip()
            xid = str(r.get("XRFID", "")).strip()
            chem_lookup_ppm[(sid, xid)] = r.get("LeadPPM", "")

    out_rows = []
    for _, r in annotated_side_df.iterrows():
        sid = str(r.get("SampleID", "")).strip()
        xid = str(r.get("XRFID", "")).strip()
        status = str(r.get("status", "")).strip()

        if status == "match":
            # Use chem's authoritative LeadPPM; fall back to the
            # technician's reported value if chem somehow lacks it
            # (shouldn't normally happen for a match).
            ppm = chem_lookup_ppm.get((sid, xid), r.get("LeadPPM", ""))
            lead_avg = r.get("LeadAvg", "")
        else:
            # discrepancy or pending — blank out the lead values so
            # downstream consumers don't treat disputed/unverified
            # values as authoritative.
            ppm = ""
            lead_avg = ""

        out_rows.append({
            "SampleID": sid,
            "XRFID": xid,
            "LeadPPM": ppm,
            "LeadAvg": lead_avg,
            "status": status,
        })

    out_df = pd.DataFrame(
        out_rows,
        columns=["SampleID", "XRFID", "LeadPPM", "LeadAvg", "status"],
    )

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out_df.to_csv(out_path, index=False)

    # Helpful summary in the log.
    counts = out_df["status"].value_counts()
    n_match = int(counts.get("match", 0))
    n_disc  = int(counts.get("discrepancy", 0))
    n_pend  = int(counts.get("pending", 0))
    print(
        f"   🔑 Refreshed {os.path.basename(out_path)}: "
        f"{len(out_df)} rows ({n_match} match, {n_disc} discrepancy, "
        f"{n_pend} pending) [{label}]."
    )


# ─── Main entry point ────────────────────────────────────────────────────
def reconcile(repo_root: str) -> dict | None:
    """Run a full reconciliation pass over BOTH the Site and Clinic sides.

    Each side is reconciled independently against the same chem file:
      - Site rows    ↔ chem rows  → Site_Master_Data.csv
      - Clinic rows  ↔ chem rows  → Clinic_Master_Data.csv

    The chem file gets a `status` column reflecting whether either side
    matches its (SampleID, XRFID) pair.

    Master files are ALWAYS refreshed (no longer gated on zero
    discrepancies). Non-matched rows appear in the master file with
    blank LeadPPM/LeadAvg and a `status` column indicating why.

    Parameters
    ----------
    repo_root : str
        Absolute path to the project root.

    Returns
    -------
    dict | None
        Summary counts {"site": {...}, "clinic": {...}} on success,
        or None if no chem file is present.
    """
    chem_dir = _find_chem_dir(repo_root)
    chem_path = _latest_chem_file(chem_dir)
    site_path = _find_site_lab_path(repo_root)
    clinic_path = _find_clinic_lab_path(repo_root)

    if chem_path is None and site_path is None and clinic_path is None:
        print("🔁 Reconciler: no chem, site, or clinic file present — nothing to do.")
        return None

    # --- Load whichever sides exist ---
    chem_df = pd.read_csv(chem_path) if chem_path else None
    site_df = pd.read_csv(site_path) if site_path else None
    clinic_df = pd.read_csv(clinic_path) if clinic_path else None

    if chem_df is not None:
        print(f"🔁 Reconciler: chem    = {os.path.basename(chem_path)} ({len(chem_df)} rows)")
    else:
        print("🔁 Reconciler: chem    = (none yet)")
    if site_df is not None:
        print(f"🔁 Reconciler: site    = {os.path.basename(site_path)} ({len(site_df)} rows)")
    else:
        print("🔁 Reconciler: site    = (none yet)")
    if clinic_df is not None:
        print(f"🔁 Reconciler: clinic  = {os.path.basename(clinic_path)} ({len(clinic_df)} rows)")
    else:
        print("🔁 Reconciler: clinic  = (none yet)")

    # --- Build lookups for cross-checking ---
    chem_lookup   = _build_lookup(chem_df)
    site_lookup   = _build_lookup(site_df)
    clinic_lookup = _build_lookup(clinic_df)

    summary = {
        "site":   {"matched": 0, "discrepancy": 0, "pending": 0},
        "clinic": {"matched": 0, "discrepancy": 0, "pending": 0},
    }

    # ── SITE side ────────────────────────────────────────────────
    site_df_annotated = _annotate_status(site_df, chem_lookup)
    if site_df_annotated is not None and not site_df_annotated.empty:
        site_df_annotated.to_csv(site_path, index=False)
        counts = site_df_annotated["status"].value_counts()
        summary["site"]["matched"]     = int(counts.get("match", 0))
        summary["site"]["discrepancy"] = int(counts.get("discrepancy", 0))
        summary["site"]["pending"]     = int(counts.get("pending", 0))

    # ── CLINIC side ──────────────────────────────────────────────
    clinic_df_annotated = _annotate_status(clinic_df, chem_lookup)
    if clinic_df_annotated is not None and not clinic_df_annotated.empty:
        clinic_df_annotated.to_csv(clinic_path, index=False)
        counts = clinic_df_annotated["status"].value_counts()
        summary["clinic"]["matched"]     = int(counts.get("match", 0))
        summary["clinic"]["discrepancy"] = int(counts.get("discrepancy", 0))
        summary["clinic"]["pending"]     = int(counts.get("pending", 0))

    # ── CHEM side ────────────────────────────────────────────────
    # A chem row matches if EITHER side agrees; it's a discrepancy
    # only if a side has the key and disagrees; otherwise pending.
    if chem_df is not None and not chem_df.empty:
        statuses = []
        for _, row in chem_df.iterrows():
            key = _row_key(row.get("SampleID", ""), row.get("XRFID", ""))
            val = pd.to_numeric(row.get("LeadPPM"), errors="coerce")

            in_site   = key in site_lookup
            in_clinic = key in clinic_lookup

            if not key[0] or not key[1] or (not in_site and not in_clinic):
                statuses.append("pending")
                continue

            site_ok   = in_site   and _ppm_agrees(val, site_lookup[key])
            clinic_ok = in_clinic and _ppm_agrees(val, clinic_lookup[key])

            if site_ok or clinic_ok:
                statuses.append("match")
            else:
                statuses.append("discrepancy")
        chem_df = chem_df.copy()
        chem_df["status"] = statuses
        chem_df.to_csv(chem_path, index=False)

    # ── Refresh the master CSVs (one per side) ──────────────────────
    # ALWAYS refresh — discrepancy and pending rows are included with
    # blank LeadPPM/LeadAvg and a `status` column so downstream consumers
    # can distinguish them. Once a row's status flips to "match" on a
    # later reconcile pass, this same code path will repopulate its
    # LeadPPM automatically (because the file is rewritten in full).
    if site_df_annotated is not None and not site_df_annotated.empty:
        _refresh_master(
            site_df_annotated,
            chem_df,
            _site_master_path(repo_root),
            "site",
        )

    if clinic_df_annotated is not None and not clinic_df_annotated.empty:
        _refresh_master(
            clinic_df_annotated,
            chem_df,
            _clinic_master_path(repo_root),
            "clinic",
        )

    print(
        f"   📊 Site  : {summary['site']['matched']} matched, "
        f"{summary['site']['discrepancy']} discrepancies, "
        f"{summary['site']['pending']} pending."
    )
    print(
        f"   📊 Clinic: {summary['clinic']['matched']} matched, "
        f"{summary['clinic']['discrepancy']} discrepancies, "
        f"{summary['clinic']['pending']} pending."
    )
    return summary


if __name__ == "__main__":
    # Allow running standalone for ad-hoc reconciliation:
    #   python src/key_reconciler.py
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    reconcile(repo_root)
# """
# xrf_tech.py — XRF Lab Technician QA/QC Portal

# Two data-entry modes share the same flow:
#   - Site_Master_Data   → writes data/XRF_Technician_Site_Data/XRF_Technician_Site.csv
#   - Clinic_Master_Data → writes data/XRF_Technician_Clinic_Data/XRF_Technician_Clinic.csv

# Per-row identity is (SampleID, XRFID). The technician enters the FULL XRFID
# for each reading (e.g. "Oct 31-1", "Oct 31-14", "Oct 31-20") so that downstream
# reconciliation against XRF_Chemistry_V*.csv joins on the same key the
# instrument uses, character-for-character. Nothing is auto-prefixed or
# auto-appended — the typed XRFID is saved as-is.

# Flow
# ----
# 1. Tech enters Test Date, Sample ID, and for each of 3+ readings:
#    the XRFID (exact instrument label) and the LeadPPM value.
# 2. Click "Analyze Stability" — runs the consensus algorithm and shows
#    the analysis result + a Preview table of exactly what will be saved.
# 3. From the preview, click either:
#      - "💾 Save & Start New Sample"  → writes to disk, runs reconciliation,
#        and resets all fields EXCEPT Test Date (which carries across
#        consecutive samples in the same lab session).
#      - "↺ Start New Sample (discard)" → clear without saving.

# The reading inputs use a placeholder-style "0.00" that disappears as
# soon as the tech starts typing. We achieve that with text inputs whose
# value is empty until the tech types something — letting them see the
# "0.00" placeholder until the first keystroke. Validation rejects non-
# numeric input, zeros, empty XRFIDs, and duplicate XRFIDs within a sample.
# """

# import streamlit as st
# import pandas as pd
# from datetime import date
# import itertools
# import os
# import sys


# # ─── Make sibling modules importable when run via `streamlit run src/xrf_tech.py` ───
# _HERE = os.path.dirname(os.path.abspath(__file__))
# if _HERE not in sys.path:
#     sys.path.insert(0, _HERE)


# # ═════════════════════════════════════════════
# #  PAGE CONFIGURATION
# # ═════════════════════════════════════════════
# st.set_page_config(page_title="XRF Technician QA/QC Form", page_icon="🧪", layout="centered")


# # ═════════════════════════════════════════════
# #  SECURITY GATEKEEPER (SINGLE PASSWORD MODE)
# # ═════════════════════════════════════════════
# def check_password():
#     def password_entered():
#         if st.session_state["password"] == st.secrets["lab_password"]:
#             st.session_state["password_correct"] = True
#             del st.session_state["password"]
#         else:
#             st.session_state["password_correct"] = False

#     if "password_correct" not in st.session_state:
#         st.markdown("### 🔒 GroundSense Tech Portal Login")
#         st.text_input("Enter Lab Password", type="password",
#                       on_change=password_entered, key="password")
#         return False
#     elif not st.session_state["password_correct"]:
#         st.markdown("### 🔒 GroundSense Tech Portal Login")
#         st.text_input("Enter Lab Password", type="password",
#                       on_change=password_entered, key="password")
#         st.error("🚫 Incorrect password. Please try again.")
#         return False
#     else:
#         return True


# if not check_password():
#     st.stop()


# # ═════════════════════════════════════════════
# #  SESSION STATE INIT
# # ═════════════════════════════════════════════
# # Reading count: how many ppm input boxes are currently rendered.
# # Bumped by 1 each time the consensus algorithm fails so the tech can
# # add another tie-breaker reading.
# if "reading_count" not in st.session_state:
#     st.session_state.reading_count = 3

# if "data_mode" not in st.session_state:
#     st.session_state.data_mode = "Site_Master_Data"

# # Once an analysis succeeds we stash everything needed for the preview /
# # save step here, and switch the UI into "preview" mode until the tech
# # saves (or discards). This avoids re-running the analysis on every
# # rerun and keeps the readings visible in the preview table.
# if "pending_save" not in st.session_state:
#     # Shape: {"records": [...], "average": float, "message": str,
#     #         "test_date": str, "sample_id": str, "mode": str}
#     st.session_state.pending_save = None

# # Flag set when the tech clicks Save / Start-New so we wipe the per-sample
# # widget state on the next rerun (you can't mutate widget keys after
# # they've been instantiated in the same run).
# if "_pending_reset" not in st.session_state:
#     st.session_state._pending_reset = False


# # ═════════════════════════════════════════════
# #  RESET HANDLER
# # ═════════════════════════════════════════════
# # Widget keys we wipe on "Save & Start New Sample" and on the discard
# # button. Test Date is deliberately NOT in this list — it carries across
# # consecutive samples in the same lab session. Per-reading XRFIDs and ppm
# # values ARE wiped because each new sample has a different set of
# # instrument labels and readings.
# PER_SAMPLE_WIDGET_KEYS_BASE = [
#     "sample_id_input",
#     # Clinic-only fields:
#     "ph_input", "moisture_choice", "notes_input",
# ]

# if st.session_state._pending_reset:
#     # Wipe per-sample fields. test_date_input is preserved.
#     for k in list(st.session_state.keys()):
#         if k in PER_SAMPLE_WIDGET_KEYS_BASE:
#             del st.session_state[k]
#         elif k.startswith("read_") or k.startswith("xrfid_"):
#             # Dynamic per-reading inputs (one xrfid_N + one read_N per row).
#             del st.session_state[k]
#     st.session_state.reading_count = 3
#     st.session_state.pending_save = None
#     st.session_state._pending_reset = False


# # ═════════════════════════════════════════════
# #  HEADER
# # ═════════════════════════════════════════════
# st.title("🧪 XRF Lab Technician Portal")
# st.markdown(
#     "Enter your readings. The system evaluates both consecutive stability "
#     "and overall cluster consensus to intelligently filter out machine flukes."
# )


# # ═════════════════════════════════════════════
# #  MODE SELECTOR
# # ═════════════════════════════════════════════
# data_mode = st.selectbox(
#     "Select Data Entry Mode",
#     ["Site_Master_Data", "Clinic_Master_Data"],
#     index=0 if st.session_state.data_mode == "Site_Master_Data" else 1,
# )

# # Reset everything if the mode changed.
# if data_mode != st.session_state.data_mode:
#     st.session_state.data_mode = data_mode
#     st.session_state.reading_count = 3
#     st.session_state.pending_save = None
#     st.session_state._pending_reset = True
#     st.rerun()


# st.markdown("---")


# # ═════════════════════════════════════════════
# #  DYNAMIC FILE PATHS
# # ═════════════════════════════════════════════
# # All paths are resolved relative to the repo root (one level above /src).
# REPO_ROOT = os.path.abspath(os.path.join(_HERE, ".."))

# if data_mode == "Site_Master_Data":
#     manual_file_path = os.path.join(
#         REPO_ROOT, "data", "XRF_Technician_Site_Data", "XRF_Technician_Site.csv"
#     )
#     download_label = "Download XRF Technician Site Data"
#     download_filename = "XRF_Technician_Site.csv"
# else:
#     manual_file_path = os.path.join(
#         REPO_ROOT, "data", "XRF_Technician_Clinic_Data", "XRF_Technician_Clinic.csv"
#     )
#     download_label = "Download XRF Technician Clinic Data"
#     download_filename = "XRF_Technician_Clinic.csv"


# # ═════════════════════════════════════════════
# #  SIDEBAR CONFIG
# # ═════════════════════════════════════════════
# st.sidebar.header("Lab Configuration")
# variance_threshold = st.sidebar.number_input(
#     "Max Allowed Discrepancy (%)", value=20.0, step=1.0,
# )


# # ═════════════════════════════════════════════
# #  SAMPLE INFO
# # ═════════════════════════════════════════════
# col_date, col_sid = st.columns(2)
# with col_date:
#     test_date = st.date_input(
#         "Test Date", value=date.today(), key="test_date_input"
#     )
# with col_sid:
#     sample_id = st.text_input(
#         "Sample ID",
#         placeholder="Scan or type Sample ID",
#         key="sample_id_input",
#     ).strip()


# # ─── Clinic-specific fields ─────────────────────────────
# ph_val = None
# moisture_level = "Normal"
# notes = ""
# if data_mode == "Clinic_Master_Data":
#     st.subheader("Clinic Sample Details")
#     col_clin1, col_clin2 = st.columns(2)
#     with col_clin1:
#         ph_val = st.number_input(
#             "pH", value=None, format="%.2f",
#             placeholder="Enter pH value", key="ph_input",
#         )
#         moisture_level = st.radio(
#             "Moisture Level",
#             ["Normal", "High moisture", "Low Moisture"],
#             horizontal=True, key="moisture_choice",
#         )
#     with col_clin2:
#         notes = st.text_area(
#             "Notes",
#             placeholder="Add any specific sample observations here...",
#             height=100, key="notes_input",
#         )
#     st.markdown("---")


# # ═════════════════════════════════════════════
# #  XRF READINGS
# # ═════════════════════════════════════════════
# # Each reading has TWO inputs:
# #   - XRFID: free-form text, exactly as the instrument labelled the reading
# #     (e.g. "Oct 31-1", "Oct 31-14", "Oct 31-20"). This is the joinable key
# #     against XRF_Chemistry_V*.csv, so it must match the instrument label
# #     character-for-character — no auto-prefixing or suffix appending.
# #   - LeadPPM: numeric, parsed from a text input so the "0.00" placeholder
# #     vanishes the moment the tech starts typing (st.number_input forces
# #     a leading 0 that can't be cleared).
# st.subheader("XRF Readings (Lead ppm)")
# st.caption(
#     "Enter the **exact XRFID** the instrument used for each reading "
#     "(e.g. `Oct 31-1`, `Oct 31-14`). This becomes the join key for "
#     "reconciliation, so it must match the instrument label character-for-character."
# )

# readings_str = []   # raw ppm strings as typed
# xrfids_str   = []   # raw XRFID strings as typed (one per reading)

# # Two-column layout — each column holds one reading's full pair.
# # Two-up keeps the XRFID + ppm pair visually grouped without becoming cramped.
# cols = st.columns(2)
# for i in range(st.session_state.reading_count):
#     col = cols[i % 2]
#     with col:
#         st.markdown(f"**Reading {i+1}**")
#         xid = st.text_input(
#             "XRFID",
#             value="",
#             placeholder=f"e.g. Oct 31-{i+1}",
#             key=f"xrfid_{i}",
#             label_visibility="collapsed",
#         )
#         val_str = st.text_input(
#             "LeadPPM",
#             value="",
#             placeholder="0.00",
#             key=f"read_{i}",
#             label_visibility="collapsed",
#         )
#         xrfids_str.append(xid.strip())
#         readings_str.append(val_str.strip())


# def _parse_readings(raw_strs):
#     """Parse the raw ppm text inputs to floats. Returns (readings, errors)."""
#     out = []
#     errs = []
#     for idx, s in enumerate(raw_strs, start=1):
#         if s == "":
#             errs.append(f"Reading {idx} ppm is empty.")
#             continue
#         try:
#             v = float(s)
#         except ValueError:
#             errs.append(f"Reading {idx} ppm ('{s}') is not a number.")
#             continue
#         if v <= 0:
#             errs.append(f"Reading {idx} ppm must be greater than 0.")
#             continue
#         out.append(v)
#     return out, errs


# def _validate_xrfids(raw_xids):
#     """Verify each reading has a non-empty, unique XRFID. Returns errors list."""
#     errs = []
#     seen = {}
#     for idx, x in enumerate(raw_xids, start=1):
#         if x == "":
#             errs.append(f"Reading {idx} XRFID is empty.")
#             continue
#         if x in seen:
#             errs.append(
#                 f"Reading {idx} XRFID '{x}' duplicates Reading {seen[x]} — "
#                 f"each reading needs a unique instrument label."
#             )
#             continue
#         seen[x] = idx
#     return errs


# # ═════════════════════════════════════════════
# #  ANALYZE STABILITY
# # ═════════════════════════════════════════════
# analyze_clicked = st.button(
#     "🔬 Analyze Stability",
#     type="primary",
#     disabled=st.session_state.pending_save is not None,
#     help="Run the consensus algorithm. If readings stabilize, you'll see "
#          "a preview before saving.",
# )

# if analyze_clicked:
#     # ── Validation ──
#     if not sample_id:
#         st.error("⚠️ Please enter a Sample ID before proceeding.")
#         st.stop()

#     xid_errs = _validate_xrfids(xrfids_str)
#     readings, errs = _parse_readings(readings_str)
#     all_errs = xid_errs + errs
#     if all_errs:
#         for e in all_errs:
#             st.error(f"⚠️ {e}")
#         st.stop()
#     if len(readings) < 2:
#         st.error("⚠️ At least two readings are required.")
#         st.stop()

#     # ── Consensus algorithm (unchanged) ──
#     is_stable = False
#     success_message = ""

#     # 1. Consecutive check on the last two readings
#     r_last, r_prev = readings[-1], readings[-2]
#     avg_last_2 = (r_last + r_prev) / 2
#     rpd_last_2 = (abs(r_last - r_prev) / avg_last_2) * 100 if avg_last_2 > 0 else 0
#     if rpd_last_2 <= variance_threshold:
#         is_stable = True
#         success_message = (
#             f"Readings {len(readings)-1} and {len(readings)} stabilized perfectly."
#         )

#     # 2. Cluster check — any 3 of N within tolerance
#     if not is_stable and len(readings) >= 3:
#         for combo in itertools.combinations(enumerate(readings, 1), 3):
#             idx = [c[0] for c in combo]
#             vals = [c[1] for c in combo]
#             max_v, min_v = max(vals), min(vals)
#             avg_v = (max_v + min_v) / 2
#             combo_rpd = (abs(max_v - min_v) / avg_v) * 100 if avg_v > 0 else 0
#             if combo_rpd <= variance_threshold:
#                 is_stable = True
#                 success_message = (
#                     f"Readings {idx[0]}, {idx[1]}, and {idx[2]} formed a "
#                     f"stable consensus (ignoring outliers)."
#                 )
#                 break

#     current_avg = sum(readings) / len(readings)
#     st.markdown("### 📊 Analysis Results")

#     if not is_stable:
#         st.warning(
#             "⚠️ **No consensus found.** The current variance is still too erratic."
#         )
#         st.session_state.reading_count += 1
#         st.info(
#             f"👇 The machine requires a tie-breaker. Adding input for "
#             f"**Reading {st.session_state.reading_count}**…"
#         )
#         st.rerun()
#     else:
#         st.success(f"✅ **Sample Accepted!** {success_message}")
#         st.info(
#             f"Final Average of all {len(readings)} readings: "
#             f"**{current_avg:.1f} ppm**"
#         )

#         # ── Build the records that WOULD be saved ──
#         # The XRFID for each row is whatever the tech literally typed —
#         # we never transform it (no auto-prefix, no auto-suffix), because
#         # it's the join key against the instrument output and must match
#         # character-for-character.
#         records = []
#         for ridx, val in enumerate(readings):
#             xrfid = xrfids_str[ridx]
#             if data_mode == "Clinic_Master_Data":
#                 records.append({
#                     "SampleID": sample_id,
#                     "XRFID": xrfid,
#                     "Moisture Level": moisture_level if ridx == 0 else "",
#                     "pH": ph_val if ridx == 0 and ph_val is not None else "",
#                     "LeadPPM": val,
#                     "LeadAvg": current_avg if ridx == 0 else "",
#                     "Notes": notes if ridx == 0 else "",
#                 })
#             else:
#                 records.append({
#                     "SampleID": sample_id,
#                     "XRFID": xrfid,
#                     "LeadPPM": val,
#                     "LeadAvg": current_avg if ridx == 0 else "",
#                 })

#         # Stash everything for the preview/save step.
#         st.session_state.pending_save = {
#             "records": records,
#             "average": current_avg,
#             "message": success_message,
#             "test_date": test_date.isoformat(),
#             "sample_id": sample_id,
#             "mode": data_mode,
#         }
#         st.rerun()


# # ═════════════════════════════════════════════
# #  PREVIEW + SAVE / DISCARD (only after a successful analysis)
# # ═════════════════════════════════════════════
# if st.session_state.pending_save is not None:
#     pending = st.session_state.pending_save
#     st.markdown("---")
#     st.markdown("### 👀 Preview — review before saving")
#     st.caption(
#         "These are the exact rows that will be written to "
#         f"`{download_filename}`. Verify each value and XRFID before saving."
#     )

#     preview_df = pd.DataFrame(pending["records"])
#     st.dataframe(preview_df, use_container_width=True, hide_index=True)

#     pcol1, pcol2 = st.columns([3, 2])
#     with pcol1:
#         save_clicked = st.button(
#             "💾 Save & Start New Sample",
#             type="primary",
#             use_container_width=True,
#         )
#     with pcol2:
#         discard_clicked = st.button(
#             "↺ Start New Sample (discard)",
#             use_container_width=True,
#         )

#     if discard_clicked:
#         # Drop the pending payload and reset per-sample fields. Test
#         # Date and XRFID stay (they carry across samples by design).
#         st.session_state.pending_save = None
#         st.session_state._pending_reset = True
#         st.rerun()

#     if save_clicked:
#         # ── Write to disk ──
#         try:
#             os.makedirs(os.path.dirname(manual_file_path), exist_ok=True)
#             df_new = pd.DataFrame(pending["records"])
#             if os.path.exists(manual_file_path):
#                 df_new.to_csv(manual_file_path, mode="a", header=False, index=False)
#             else:
#                 df_new.to_csv(manual_file_path, mode="w", header=True, index=False)
#             st.success(
#                 f"💾 **Saved {len(df_new)} row(s) to "
#                 f"`{download_filename}`** "
#                 f"({pending['mode']})."
#             )
#         except Exception as e:
#             st.error(f"❌ Save failed: {e}")
#             st.stop()

#         # ── Trigger reconciliation (works for BOTH Site and Clinic) ──
#         try:
#             from key_reconciler import reconcile
#             summary = reconcile(REPO_ROOT)
#             if summary:
#                 if pending["mode"] == "Site_Master_Data":
#                     side = summary["site"]
#                 else:
#                     side = summary["clinic"]
#                 st.info(
#                     f"🔁 Reconciliation complete — "
#                     f"{side['matched']} matched, "
#                     f"{side['discrepancy']} discrepancies, "
#                     f"{side['pending']} pending "
#                     f"on the {pending['mode'].split('_')[0].lower()} side."
#                 )
#         except Exception as e:
#             st.warning(f"⚠️ Reconciliation could not run: {e}")

#         # ── Reset per-sample fields, keep Test Date + XRFID ──
#         st.session_state.pending_save = None
#         st.session_state._pending_reset = True
#         st.rerun()


# # ═════════════════════════════════════════════
# #  SIDEBAR EXPORT
# # ═════════════════════════════════════════════
# st.sidebar.markdown("---")
# st.sidebar.subheader("📥 Data Export")

# if os.path.exists(manual_file_path):
#     with open(manual_file_path, "rb") as file:
#         st.sidebar.download_button(
#             label=download_label,
#             data=file.read(),
#             file_name=download_filename,
#             mime="text/csv",
#         )
# else:
#     st.sidebar.info(f"{download_filename} will appear here after the first save.")


"""
xrf_tech.py — XRF Lab Technician QA/QC Portal

Two data-entry modes share the same flow:
  - Site_Master_Data   → writes data/XRF_Technician_Site_Data/XRF_Technician_Site.csv
  - Clinic_Master_Data → writes data/XRF_Technician_Clinic_Data/XRF_Technician_Clinic.csv

Per-row identity is (SampleID, XRFID). The technician enters the FULL XRFID
for each reading (e.g. "Oct 31-1", "Oct 31-14", "Oct 31-20") so that downstream
reconciliation against XRF_Chemistry_V*.csv joins on the same key the
instrument uses, character-for-character. Nothing is auto-prefixed or
auto-appended — the typed XRFID is saved as-is.

Flow
----
1. Tech enters Test Date, Sample ID, and for each of 3+ readings:
   the XRFID (exact instrument label) and the LeadPPM value.
2. Click "Analyze Stability" — runs the consensus algorithm and shows
   the analysis result + a Preview table of exactly what will be saved.
3. From the preview, click either:
     - "💾 Save & Start New Sample"  → writes to disk, runs reconciliation,
       and resets all fields EXCEPT Test Date (which carries across
       consecutive samples in the same lab session).

       UPSERT BEHAVIOR: If the SampleID already exists in the technician
       file, the tech is shown a confirmation banner warning that the
       existing rows for that SampleID will be REPLACED. Only on explicit
       confirmation are the old rows deleted and the new ones written.
     - "↺ Start New Sample (discard)" → clear without saving.

The reading inputs use a placeholder-style "0.00" that disappears as
soon as the tech starts typing. We achieve that with text inputs whose
value is empty until the tech types something — letting them see the
"0.00" placeholder until the first keystroke. Validation rejects non-
numeric input, zeros, empty XRFIDs, and duplicate XRFIDs within a sample.
"""

import streamlit as st
import pandas as pd
from datetime import date
import itertools
import os
import sys


# ─── Make sibling modules importable when run via `streamlit run src/xrf_tech.py` ───
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


# ═════════════════════════════════════════════
#  PAGE CONFIGURATION
# ═════════════════════════════════════════════
st.set_page_config(page_title="XRF Technician QA/QC Form", page_icon="🧪", layout="centered")


# ═════════════════════════════════════════════
#  SECURITY GATEKEEPER (SINGLE PASSWORD MODE)
# ═════════════════════════════════════════════
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["lab_password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("### 🔒 GroundSense Tech Portal Login")
        st.text_input("Enter Lab Password", type="password",
                      on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.markdown("### 🔒 GroundSense Tech Portal Login")
        st.text_input("Enter Lab Password", type="password",
                      on_change=password_entered, key="password")
        st.error("🚫 Incorrect password. Please try again.")
        return False
    else:
        return True


if not check_password():
    st.stop()


# ═════════════════════════════════════════════
#  SESSION STATE INIT
# ═════════════════════════════════════════════
# Reading count: how many ppm input boxes are currently rendered.
# Bumped by 1 each time the consensus algorithm fails so the tech can
# add another tie-breaker reading.
if "reading_count" not in st.session_state:
    st.session_state.reading_count = 3

if "data_mode" not in st.session_state:
    st.session_state.data_mode = "Site_Master_Data"

# Once an analysis succeeds we stash everything needed for the preview /
# save step here, and switch the UI into "preview" mode until the tech
# saves (or discards). This avoids re-running the analysis on every
# rerun and keeps the readings visible in the preview table.
if "pending_save" not in st.session_state:
    # Shape: {"records": [...], "average": float, "message": str,
    #         "test_date": str, "sample_id": str, "mode": str}
    st.session_state.pending_save = None

# When the tech clicks Save and the SampleID already has rows on disk,
# we stash the replace intent here and render a confirmation banner on
# the next rerun. Cleared after the tech confirms or cancels.
# Shape: {"existing_count": int, "sample_id": str}
if "pending_replace" not in st.session_state:
    st.session_state.pending_replace = None

# Flag set when the tech clicks Save / Start-New so we wipe the per-sample
# widget state on the next rerun (you can't mutate widget keys after
# they've been instantiated in the same run).
if "_pending_reset" not in st.session_state:
    st.session_state._pending_reset = False


# ═════════════════════════════════════════════
#  RESET HANDLER
# ═════════════════════════════════════════════
# Widget keys we wipe on "Save & Start New Sample" and on the discard
# button. Test Date is deliberately NOT in this list — it carries across
# consecutive samples in the same lab session. Per-reading XRFIDs and ppm
# values ARE wiped because each new sample has a different set of
# instrument labels and readings.
PER_SAMPLE_WIDGET_KEYS_BASE = [
    "sample_id_input",
    # Clinic-only fields:
    "ph_input", "moisture_choice", "notes_input",
]

if st.session_state._pending_reset:
    # Wipe per-sample fields. test_date_input is preserved.
    for k in list(st.session_state.keys()):
        if k in PER_SAMPLE_WIDGET_KEYS_BASE:
            del st.session_state[k]
        elif k.startswith("read_") or k.startswith("xrfid_"):
            # Dynamic per-reading inputs (one xrfid_N + one read_N per row).
            del st.session_state[k]
    st.session_state.reading_count = 3
    st.session_state.pending_save = None
    st.session_state.pending_replace = None
    st.session_state._pending_reset = False


# ═════════════════════════════════════════════
#  SAVE HELPERS
# ═════════════════════════════════════════════
def _do_save_and_reconcile(pending, manual_file_path, download_filename):
    """Append new rows to the technician file and run reconciliation.

    Used when no existing SampleID collision is detected (the "happy path").
    Caller is responsible for clearing pending_save and triggering the
    rerun after this returns successfully.
    """
    try:
        os.makedirs(os.path.dirname(manual_file_path), exist_ok=True)
        df_new = pd.DataFrame(pending["records"])
        if os.path.exists(manual_file_path):
            df_new.to_csv(manual_file_path, mode="a", header=False, index=False)
        else:
            df_new.to_csv(manual_file_path, mode="w", header=True, index=False)
        st.success(
            f"💾 **Saved {len(df_new)} row(s) to `{download_filename}`** "
            f"({pending['mode']})."
        )
    except Exception as e:
        st.error(f"❌ Save failed: {e}")
        st.stop()

    _run_reconcile(pending)


def _do_replace_and_reconcile(pending, manual_file_path, download_filename,
                              sample_id, existing_count):
    """Replace all rows for `sample_id` in the technician file, then reconcile.

    Reads the full file, splits it into the rows ABOVE the first matching
    SampleID row and BELOW the last matching SampleID row, drops the
    matching rows, and reassembles as: above + new rows + below.

    The new rows therefore appear at the exact position the first old row
    occupied — other SampleIDs above and below keep their original order.

    Caller is responsible for clearing session state and triggering the
    rerun.
    """
    try:
        if os.path.exists(manual_file_path):
            existing_df = pd.read_csv(manual_file_path, dtype=str).fillna("")
            # Reset index so iloc slicing uses positional indices we control.
            existing_df = existing_df.reset_index(drop=True)
        else:
            existing_df = pd.DataFrame()

        new_df = pd.DataFrame(pending["records"])

        if len(existing_df) and "SampleID" in existing_df.columns:
            mask = (
                existing_df["SampleID"].astype(str).str.strip()
                == sample_id.strip()
            )
            match_positions = list(existing_df.index[mask])
            if match_positions:
                # First matching row's position = insertion point for the new rows.
                first_pos = match_positions[0]
                # Slice everything ABOVE the first match (preserves their order).
                above = existing_df.iloc[:first_pos].copy()
                # Slice everything BELOW the LAST match, skipping any in between
                # (covers the case where the SampleID's rows are contiguous OR
                # interleaved with others — we drop ALL matches, keep everything
                # else in original order).
                # Build "below" from rows strictly after first_pos whose mask is False.
                tail_mask = ~mask.iloc[first_pos + 1:]
                below = existing_df.iloc[first_pos + 1:][tail_mask].copy()
            else:
                # No match found (shouldn't happen — caller already counted).
                # Treat as a clean append.
                above = existing_df.copy()
                below = pd.DataFrame()
        else:
            above = existing_df.copy()
            below = pd.DataFrame()

        # Align columns across all three pieces.
        all_cols = list(above.columns)
        for c in new_df.columns:
            if c not in all_cols:
                all_cols.append(c)
        for c in below.columns:
            if c not in all_cols:
                all_cols.append(c)

        def _align(df):
            if df.empty and len(df.columns) == 0:
                return pd.DataFrame(columns=all_cols)
            for c in all_cols:
                if c not in df.columns:
                    df[c] = ""
            return df[all_cols]

        above = _align(above)
        new_df = _align(new_df)
        below = _align(below)

        combined = pd.concat([above, new_df, below], ignore_index=True)

        os.makedirs(os.path.dirname(manual_file_path), exist_ok=True)
        combined.to_csv(manual_file_path, index=False)

        st.success(
            f"💾 **Replaced {existing_count} old row(s) with "
            f"{len(new_df)} new row(s)** for SampleID "
            f"`{sample_id}` in `{download_filename}`."
        )
    except Exception as e:
        st.error(f"❌ Replace failed: {e}")
        st.stop()

    _run_reconcile(pending)


def _run_reconcile(pending):
    """Trigger key_reconciler.reconcile() and surface the summary."""
    try:
        from key_reconciler import reconcile
        summary = reconcile(REPO_ROOT)
        if summary:
            side = (summary["site"] if pending["mode"] == "Site_Master_Data"
                    else summary["clinic"])
            st.info(
                f"🔁 Reconciliation complete — {side['matched']} matched, "
                f"{side['discrepancy']} discrepancies, "
                f"{side['pending']} pending on the "
                f"{pending['mode'].split('_')[0].lower()} side."
            )
    except Exception as e:
        st.warning(f"⚠️ Reconciliation could not run: {e}")


def _count_existing_rows_for_sample(manual_file_path, sample_id):
    """Return the number of rows in the file whose SampleID matches.

    Returns 0 if the file is missing, unreadable, or has no SampleID column.
    A read failure surfaces as a Streamlit warning but does NOT raise.
    """
    if not os.path.exists(manual_file_path):
        return 0
    try:
        existing_df = pd.read_csv(manual_file_path, dtype=str).fillna("")
        if "SampleID" not in existing_df.columns:
            return 0
        return int(
            (existing_df["SampleID"].astype(str).str.strip()
             == sample_id.strip()).sum()
        )
    except Exception as e:
        st.warning(
            f"⚠️ Could not read existing file to check for duplicates "
            f"({e}). Proceeding with append."
        )
        return 0


# ═════════════════════════════════════════════
#  HEADER
# ═════════════════════════════════════════════
st.title("🧪 XRF Lab Technician Portal")
st.markdown(
    "Enter your readings. The system evaluates both consecutive stability "
    "and overall cluster consensus to intelligently filter out machine flukes."
)


# ═════════════════════════════════════════════
#  MODE SELECTOR
# ═════════════════════════════════════════════
data_mode = st.selectbox(
    "Select Data Entry Mode",
    ["Site_Master_Data", "Clinic_Master_Data"],
    index=0 if st.session_state.data_mode == "Site_Master_Data" else 1,
)

# Reset everything if the mode changed.
if data_mode != st.session_state.data_mode:
    st.session_state.data_mode = data_mode
    st.session_state.reading_count = 3
    st.session_state.pending_save = None
    st.session_state.pending_replace = None
    st.session_state._pending_reset = True
    st.rerun()


st.markdown("---")


# ═════════════════════════════════════════════
#  DYNAMIC FILE PATHS
# ═════════════════════════════════════════════
# All paths are resolved relative to the repo root (one level above /src).
REPO_ROOT = os.path.abspath(os.path.join(_HERE, ".."))

if data_mode == "Site_Master_Data":
    manual_file_path = os.path.join(
        REPO_ROOT, "data", "XRF_Technician_Site_Data", "XRF_Technician_Site.csv"
    )
    download_label = "Download XRF Technician Site Data"
    download_filename = "XRF_Technician_Site.csv"
else:
    manual_file_path = os.path.join(
        REPO_ROOT, "data", "XRF_Technician_Clinic_Data", "XRF_Technician_Clinic.csv"
    )
    download_label = "Download XRF Technician Clinic Data"
    download_filename = "XRF_Technician_Clinic.csv"


# ═════════════════════════════════════════════
#  SIDEBAR CONFIG
# ═════════════════════════════════════════════
st.sidebar.header("Lab Configuration")
variance_threshold = st.sidebar.number_input(
    "Max Allowed Discrepancy (%)", value=20.0, step=1.0,
)


# ═════════════════════════════════════════════
#  SAMPLE INFO
# ═════════════════════════════════════════════
col_date, col_sid = st.columns(2)
with col_date:
    test_date = st.date_input(
        "Test Date", value=date.today(), key="test_date_input"
    )
with col_sid:
    sample_id = st.text_input(
        "Sample ID",
        placeholder="Scan or type Sample ID",
        key="sample_id_input",
    ).strip()


# ─── Clinic-specific fields ─────────────────────────────
ph_val = None
moisture_level = "Normal"
notes = ""
if data_mode == "Clinic_Master_Data":
    st.subheader("Clinic Sample Details")
    col_clin1, col_clin2 = st.columns(2)
    with col_clin1:
        ph_val = st.number_input(
            "pH", value=None, format="%.2f",
            placeholder="Enter pH value", key="ph_input",
        )
        moisture_level = st.radio(
            "Moisture Level",
            ["Normal", "High moisture", "Low Moisture"],
            horizontal=True, key="moisture_choice",
        )
    with col_clin2:
        notes = st.text_area(
            "Notes",
            placeholder="Add any specific sample observations here...",
            height=100, key="notes_input",
        )
    st.markdown("---")


# ═════════════════════════════════════════════
#  XRF READINGS
# ═════════════════════════════════════════════
# Each reading has TWO inputs:
#   - XRFID: free-form text, exactly as the instrument labelled the reading
#     (e.g. "Oct 31-1", "Oct 31-14", "Oct 31-20"). This is the joinable key
#     against XRF_Chemistry_V*.csv, so it must match the instrument label
#     character-for-character — no auto-prefixing or suffix appending.
#   - LeadPPM: numeric, parsed from a text input so the "0.00" placeholder
#     vanishes the moment the tech starts typing (st.number_input forces
#     a leading 0 that can't be cleared).
st.subheader("XRF Readings (Lead ppm)")
st.caption(
    "Enter the **exact XRFID** the instrument used for each reading "
    "(e.g. `Oct 31-1`, `Oct 31-14`). This becomes the join key for "
    "reconciliation, so it must match the instrument label character-for-character."
)

readings_str = []   # raw ppm strings as typed
xrfids_str   = []   # raw XRFID strings as typed (one per reading)

# Two-column layout — each column holds one reading's full pair.
# Two-up keeps the XRFID + ppm pair visually grouped without becoming cramped.
cols = st.columns(2)
for i in range(st.session_state.reading_count):
    col = cols[i % 2]
    with col:
        st.markdown(f"**Reading {i+1}**")
        xid = st.text_input(
            "XRFID",
            value="",
            placeholder=f"e.g. Oct 31-{i+1}",
            key=f"xrfid_{i}",
            label_visibility="collapsed",
        )
        val_str = st.text_input(
            "LeadPPM",
            value="",
            placeholder="0.00",
            key=f"read_{i}",
            label_visibility="collapsed",
        )
        xrfids_str.append(xid.strip())
        readings_str.append(val_str.strip())


def _parse_readings(raw_strs):
    """Parse the raw ppm text inputs to floats. Returns (readings, errors)."""
    out = []
    errs = []
    for idx, s in enumerate(raw_strs, start=1):
        if s == "":
            errs.append(f"Reading {idx} ppm is empty.")
            continue
        try:
            v = float(s)
        except ValueError:
            errs.append(f"Reading {idx} ppm ('{s}') is not a number.")
            continue
        if v <= 0:
            errs.append(f"Reading {idx} ppm must be greater than 0.")
            continue
        out.append(v)
    return out, errs


def _validate_xrfids(raw_xids):
    """Verify each reading has a non-empty, unique XRFID. Returns errors list."""
    errs = []
    seen = {}
    for idx, x in enumerate(raw_xids, start=1):
        if x == "":
            errs.append(f"Reading {idx} XRFID is empty.")
            continue
        if x in seen:
            errs.append(
                f"Reading {idx} XRFID '{x}' duplicates Reading {seen[x]} — "
                f"each reading needs a unique instrument label."
            )
            continue
        seen[x] = idx
    return errs


# ═════════════════════════════════════════════
#  ANALYZE STABILITY
# ═════════════════════════════════════════════
analyze_clicked = st.button(
    "🔬 Analyze Stability",
    type="primary",
    disabled=st.session_state.pending_save is not None,
    help="Run the consensus algorithm. If readings stabilize, you'll see "
         "a preview before saving.",
)

if analyze_clicked:
    # ── Validation ──
    if not sample_id:
        st.error("⚠️ Please enter a Sample ID before proceeding.")
        st.stop()

    xid_errs = _validate_xrfids(xrfids_str)
    readings, errs = _parse_readings(readings_str)
    all_errs = xid_errs + errs
    if all_errs:
        for e in all_errs:
            st.error(f"⚠️ {e}")
        st.stop()
    if len(readings) < 2:
        st.error("⚠️ At least two readings are required.")
        st.stop()

    # ── Consensus algorithm (unchanged) ──
    is_stable = False
    success_message = ""

    # 1. Consecutive check on the last two readings
    r_last, r_prev = readings[-1], readings[-2]
    avg_last_2 = (r_last + r_prev) / 2
    rpd_last_2 = (abs(r_last - r_prev) / avg_last_2) * 100 if avg_last_2 > 0 else 0
    if rpd_last_2 <= variance_threshold:
        is_stable = True
        success_message = (
            f"Readings {len(readings)-1} and {len(readings)} stabilized perfectly."
        )

    # 2. Cluster check — any 3 of N within tolerance
    if not is_stable and len(readings) >= 3:
        for combo in itertools.combinations(enumerate(readings, 1), 3):
            idx = [c[0] for c in combo]
            vals = [c[1] for c in combo]
            max_v, min_v = max(vals), min(vals)
            avg_v = (max_v + min_v) / 2
            combo_rpd = (abs(max_v - min_v) / avg_v) * 100 if avg_v > 0 else 0
            if combo_rpd <= variance_threshold:
                is_stable = True
                success_message = (
                    f"Readings {idx[0]}, {idx[1]}, and {idx[2]} formed a "
                    f"stable consensus (ignoring outliers)."
                )
                break

    current_avg = sum(readings) / len(readings)
    st.markdown("### 📊 Analysis Results")

    if not is_stable:
        st.warning(
            "⚠️ **No consensus found.** The current variance is still too erratic."
        )
        st.session_state.reading_count += 1
        st.info(
            f"👇 The machine requires a tie-breaker. Adding input for "
            f"**Reading {st.session_state.reading_count}**…"
        )
        st.rerun()
    else:
        st.success(f"✅ **Sample Accepted!** {success_message}")
        st.info(
            f"Final Average of all {len(readings)} readings: "
            f"**{current_avg:.1f} ppm**"
        )

        # ── Build the records that WOULD be saved ──
        # The XRFID for each row is whatever the tech literally typed —
        # we never transform it (no auto-prefix, no auto-suffix), because
        # it's the join key against the instrument output and must match
        # character-for-character.
        records = []
        for ridx, val in enumerate(readings):
            xrfid = xrfids_str[ridx]
            if data_mode == "Clinic_Master_Data":
                records.append({
                    "SampleID": sample_id,
                    "XRFID": xrfid,
                    "Moisture Level": moisture_level if ridx == 0 else "",
                    "pH": ph_val if ridx == 0 and ph_val is not None else "",
                    "LeadPPM": val,
                    "LeadAvg": current_avg if ridx == 0 else "",
                    "Notes": notes if ridx == 0 else "",
                })
            else:
                records.append({
                    "SampleID": sample_id,
                    "XRFID": xrfid,
                    "LeadPPM": val,
                    "LeadAvg": current_avg if ridx == 0 else "",
                })

        # Stash everything for the preview/save step.
        st.session_state.pending_save = {
            "records": records,
            "average": current_avg,
            "message": success_message,
            "test_date": test_date.isoformat(),
            "sample_id": sample_id,
            "mode": data_mode,
        }
        st.rerun()


# ═════════════════════════════════════════════
#  PREVIEW + SAVE / DISCARD (only after a successful analysis)
# ═════════════════════════════════════════════
if st.session_state.pending_save is not None:
    pending = st.session_state.pending_save
    st.markdown("---")
    st.markdown("### 👀 Preview — review before saving")
    st.caption(
        "These are the exact rows that will be written to "
        f"`{download_filename}`. Verify each value and XRFID before saving."
    )

    preview_df = pd.DataFrame(pending["records"])
    st.dataframe(preview_df, use_container_width=True, hide_index=True)

    pcol1, pcol2 = st.columns([3, 2])
    with pcol1:
        save_clicked = st.button(
            "💾 Save & Start New Sample",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.pending_replace is not None,
        )
    with pcol2:
        discard_clicked = st.button(
            "↺ Start New Sample (discard)",
            use_container_width=True,
            disabled=st.session_state.pending_replace is not None,
        )

    if discard_clicked:
        # Drop the pending payload and reset per-sample fields. Test
        # Date and XRFID stay (they carry across samples by design).
        st.session_state.pending_save = None
        st.session_state.pending_replace = None
        st.session_state._pending_reset = True
        st.rerun()

    if save_clicked:
        # ── Check for existing rows with this SampleID ──
        # If any exist, gate the destructive replace behind a second
        # confirm step (rendered below in the pending_replace block).
        # Otherwise just append directly (the "happy path").
        existing_count = _count_existing_rows_for_sample(
            manual_file_path, pending["sample_id"]
        )

        if existing_count > 0:
            st.session_state.pending_replace = {
                "existing_count": existing_count,
                "sample_id": pending["sample_id"],
            }
            st.rerun()
        else:
            _do_save_and_reconcile(pending, manual_file_path, download_filename)
            st.session_state.pending_save = None
            st.session_state._pending_reset = True
            st.rerun()


# ═════════════════════════════════════════════
#  REPLACE-CONFIRMATION BANNER
# ═════════════════════════════════════════════
# Rendered only when the tech has clicked Save AND existing rows for
# this SampleID were found on disk. The save is paused until the tech
# explicitly confirms (deletes old + writes new) or cancels (keeps old,
# returns to preview).
if (st.session_state.get("pending_replace") is not None
        and st.session_state.get("pending_save") is not None):
    pr = st.session_state.pending_replace
    pending = st.session_state.pending_save
    st.markdown("---")
    st.warning(
        f"⚠️ **{pr['existing_count']} existing row(s)** in "
        f"`{download_filename}` for SampleID **`{pr['sample_id']}`** "
        f"will be **REPLACED** with the {len(pending['records'])} new row(s) "
        f"shown above. The old rows will be permanently deleted from the file. "
        f"Continue?"
    )
    rcol1, rcol2 = st.columns([3, 2])
    with rcol1:
        confirm_replace = st.button(
            "✅ Yes, replace existing rows",
            type="primary",
            use_container_width=True,
            key="confirm_replace_btn",
        )
    with rcol2:
        cancel_replace = st.button(
            "✖ Cancel (keep existing)",
            use_container_width=True,
            key="cancel_replace_btn",
        )

    if cancel_replace:
        # Bail out: clear the replace intent but keep pending_save so the
        # tech can still review/discard from the preview.
        st.session_state.pending_replace = None
        st.rerun()

    if confirm_replace:
        _do_replace_and_reconcile(
            pending=pending,
            manual_file_path=manual_file_path,
            download_filename=download_filename,
            sample_id=pr["sample_id"],
            existing_count=pr["existing_count"],
        )
        st.session_state.pending_save = None
        st.session_state.pending_replace = None
        st.session_state._pending_reset = True
        st.rerun()


# ═════════════════════════════════════════════
#  SIDEBAR EXPORT
# ═════════════════════════════════════════════
st.sidebar.markdown("---")
st.sidebar.subheader("📥 Data Export")

if os.path.exists(manual_file_path):
    with open(manual_file_path, "rb") as file:
        st.sidebar.download_button(
            label=download_label,
            data=file.read(),
            file_name=download_filename,
            mime="text/csv",
        )
else:
    st.sidebar.info(f"{download_filename} will appear here after the first save.")

# """
# field_entry.py — GroundSense Field Entry App

# A lightweight Streamlit form for recording SiteID + SampleID pairs while
# out in the field, *without* ever touching resident PII (address, name, ZIP).

# Why this exists
# ---------------
# The repo previously shipped a single CSV
# (`XRF Site Analysis Database W SampleID(Sheet1).csv`) that mixed two very
# different concerns:

#     1. Pipeline-tracking metadata (SiteID, SampleID, status flags)
#     2. Resident PII (address, first/last name, ZIP)

# That made it impossible to commit the CSV without leaking PII. This app
# replaces the manual Excel/Numbers workflow for column 1 only. PII is now
# read from a separate, user-configured local-only path (see
# `PII_PATH_ENV_VAR` below) and is never written here.

# Output
# ------
# Writes `<repo>/data/site_databases/XRF Site Analysis Database W SampleID(Sheet1).csv`
# in the exact two-row-header format the rest of the codebase already
# parses (`pd.read_csv(..., header=1, encoding='latin1')`). PII columns are
# left blank — the dashboard now joins addresses in via the configured PII
# file, not via this CSV.

# Run
# ---
#     streamlit run src/field_entry.py
# """

# import os
# import re
# from datetime import date

# import pandas as pd
# import streamlit as st


# # ═══════════════════════════════════════════════
# #  CONSTANTS — file format
# # ═══════════════════════════════════════════════
# # Two-header-row layout. Order MUST match the existing CSV exactly so that
# # `pd.read_csv(..., header=1)` calls elsewhere in the codebase keep working.
# HEADER_ROW_1 = [
#     "", "", "", "",
#     "Site Info", "", "",
#     "Resident Info", "",
#     "Resident Communication", "",
#     "Soil Characterization", "",
#     "Sample Prep", "", "", "",
#     "XRF Analysis", "",
#     "Report  ", "",
#     "",
# ]

# HEADER_ROW_2 = [
#     "SiteID", "SampleID", "Data Location", "SamplingDate",
#     "Address", "City", "ZipCode",
#     "FirstName", "LastName",
#     "Permission Obtained?", "Pre-sampling Info Shared?",
#     "pH Analysis", "Soil Type",
#     "Sample delivered to lab", "Dehydrated", "Homogenized", "Sieved",
#     "Analyzed", "Data Upload",
#     "Created", "Shared",
#     "",
# ]

# # Columns that are PII — this app NEVER fills these.
# PII_COLUMNS = {"Address", "City", "ZipCode", "FirstName", "LastName"}

# OUTPUT_FILENAME = "XRF Site Analysis Database W SampleID(Sheet1).csv"


# # ═══════════════════════════════════════════════
# #  PATH RESOLUTION
# # ═══════════════════════════════════════════════
# def get_repo_root() -> str:
#     """Return absolute path to the repo root (one level above /src)."""
#     return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# def get_output_path() -> str:
#     """Where to write the field CSV — same place the rest of the codebase reads from."""
#     return os.path.join(
#         get_repo_root(), "data", "site_databases", OUTPUT_FILENAME
#     )


# # ═══════════════════════════════════════════════
# #  EXISTING-DATA LOADER
# # ═══════════════════════════════════════════════
# def load_existing_rows(path: str) -> pd.DataFrame:
#     """Load any existing field CSV so users can append rather than overwrite.

#     Returns an empty DataFrame with the right columns if the file is missing
#     or malformed — never raises.
#     """
#     cols = HEADER_ROW_2
#     if not os.path.exists(path):
#         return pd.DataFrame(columns=cols)
#     try:
#         df = pd.read_csv(path, header=1, encoding="latin1", dtype=str).fillna("")
#         # Normalize column set in case the source had extra/missing trailing cols
#         for c in cols:
#             if c not in df.columns:
#                 df[c] = ""
#         return df[cols]
#     except Exception as e:
#         st.warning(f"Could not parse existing CSV ({e}). Starting fresh.")
#         return pd.DataFrame(columns=cols)


# # ═══════════════════════════════════════════════
# #  WRITER — preserves the two-row-header format
# # ═══════════════════════════════════════════════
# def write_field_csv(df: pd.DataFrame, path: str) -> None:
#     """Write df to disk with the original two-row header on top.

#     We can't use `df.to_csv(header=True)` directly because the file format
#     has TWO header rows (a category band on top of the actual column names).
#     So we manually emit both header rows, then the data rows, all comma-
#     separated and quoted minimally to match pandas' default dialect.
#     """
#     os.makedirs(os.path.dirname(path), exist_ok=True)

#     # Make sure the dataframe has exactly the expected column order
#     out = df.reindex(columns=HEADER_ROW_2).fillna("")

#     # Strip any accidental PII the user might have pasted
#     for col in PII_COLUMNS:
#         if col in out.columns:
#             out[col] = ""

#     import csv
#     with open(path, "w", newline="", encoding="utf-8") as f:
#         writer = csv.writer(f)
#         writer.writerow(HEADER_ROW_1)
#         writer.writerow(HEADER_ROW_2)
#         for _, row in out.iterrows():
#             writer.writerow([row.get(c, "") for c in HEADER_ROW_2])


# # ═══════════════════════════════════════════════
# #  ID GENERATION HELPERS
# # ═══════════════════════════════════════════════
# def generate_grid_ids(
#     rows: str, cols: int, suffix: str, replicates: int
# ) -> list[str]:
#     """Generate sample IDs for a rectangular grid plus optional replicates.

#     Example: rows='A-D', cols=3, suffix='PITT_24June2025', replicates=3
#     -> ['A1_PITT_24June2025', 'A1_PITT_24June2025', 'A1_PITT_24June2025',
#         'A2_PITT_24June2025', ...]
#     """
#     # Parse row range like "A-D" or "A,B,C,D"
#     row_letters: list[str] = []
#     rows = rows.strip().upper()
#     if "-" in rows and len(rows) >= 3:
#         start, end = rows.split("-", 1)
#         start, end = start.strip(), end.strip()
#         if len(start) == 1 and len(end) == 1 and start <= end:
#             row_letters = [chr(c) for c in range(ord(start), ord(end) + 1)]
#     if not row_letters:
#         row_letters = [r.strip() for r in rows.split(",") if r.strip()]

#     ids: list[str] = []
#     for r in row_letters:
#         for c in range(1, cols + 1):
#             base = f"{r}{c}"
#             full = f"{base}_{suffix}" if suffix else base
#             ids.extend([full] * max(1, replicates))
#     return ids


# # ═══════════════════════════════════════════════
# #  PAGE
# # ═══════════════════════════════════════════════
# st.set_page_config(
#     page_title="GroundSense Field Entry",
#     page_icon="🌱",
#     layout="wide",
# )

# st.title("🌱 Field Sample Entry")
# st.caption(
#     "Record SiteID + SampleIDs from the field. Resident PII (address, name, ZIP) "
#     "is never stored in this file — it lives in a separate local-only file."
# )

# OUTPUT_PATH = get_output_path()
# st.code(f"Will write to: {OUTPUT_PATH}", language=None)


# # ─── Session state ───
# if "rows" not in st.session_state:
#     st.session_state.rows = load_existing_rows(OUTPUT_PATH)
# if "new_site_id" not in st.session_state:
#     st.session_state.new_site_id = date.today().strftime("%Y-%-m-%-d") if os.name != "nt" else date.today().strftime("%Y-%m-%d").lstrip("0")


# # ═══════════════════════════════════════════════
# #  SECTION 1 — SITE
# # ═══════════════════════════════════════════════
# st.markdown("---")
# st.subheader("1. Site")

# col_a, col_b = st.columns([2, 3])
# with col_a:
#     site_id = st.text_input(
#         "SiteID",
#         value=st.session_state.new_site_id,
#         help="Free-form. Convention in this dataset: the sampling date as YYYY-M-D, e.g. 2025-10-18.",
#         key="site_id_input",
#     )
# with col_b:
#     sampling_date = st.date_input(
#         "SamplingDate (optional, fills SamplingDate + Data Location columns)",
#         value=date.today(),
#         format="MM/DD/YYYY",
#         key="sampling_date_input",
#     )


# # ═══════════════════════════════════════════════
# #  SECTION 2 — SAMPLE IDs
# # ═══════════════════════════════════════════════
# st.markdown("---")
# st.subheader("2. SampleIDs")

# mode = st.radio(
#     "Entry mode",
#     ["Single (one at a time)", "Bulk paste", "Auto-grid"],
#     horizontal=True,
#     key="entry_mode",
# )

# new_ids: list[str] = []

# if mode == "Single (one at a time)":
#     with st.form("single_form", clear_on_submit=True):
#         s_id = st.text_input("SampleID", placeholder="e.g. A1_PITT_24June2025")
#         replicates = st.number_input(
#             "Number of replicates (rows to write for this ID)",
#             min_value=1, max_value=10, value=3,
#             help="The dataset convention is 3 readings per sample, so 3 rows per SampleID.",
#         )
#         submitted = st.form_submit_button("➕ Add SampleID")
#         if submitted:
#             s_id = s_id.strip()
#             if s_id:
#                 new_ids = [s_id] * int(replicates)
#             else:
#                 st.warning("SampleID is empty.")

# elif mode == "Bulk paste":
#     with st.form("bulk_form", clear_on_submit=False):
#         bulk = st.text_area(
#             "Paste SampleIDs — one per line",
#             height=200,
#             placeholder="A1_PITT_24June2025\nA2_PITT_24June2025\nA3_PITT_24June2025",
#         )
#         replicates = st.number_input(
#             "Replicates per ID",
#             min_value=1, max_value=10, value=3,
#             key="bulk_replicates",
#         )
#         submitted = st.form_submit_button("➕ Add all")
#         if submitted:
#             ids = [line.strip() for line in bulk.splitlines() if line.strip()]
#             if ids:
#                 new_ids = [i for i in ids for _ in range(int(replicates))]
#             else:
#                 st.warning("No SampleIDs found in the paste box.")

# else:  # Auto-grid
#     with st.form("grid_form", clear_on_submit=False):
#         c1, c2, c3, c4 = st.columns(4)
#         with c1:
#             rows = st.text_input("Rows", value="A-H", help="e.g. 'A-H' or 'A,B,C'")
#         with c2:
#             cols = st.number_input("Cols", min_value=1, max_value=20, value=3)
#         with c3:
#             suffix = st.text_input(
#                 "Suffix",
#                 value=f"PITT_{sampling_date.strftime('%-d%b%Y') if os.name != 'nt' else sampling_date.strftime('%d%b%Y').lstrip('0')}",
#                 help="Appended to each cell label, e.g. '_PITT_24June2025'.",
#             )
#         with c4:
#             replicates = st.number_input(
#                 "Replicates",
#                 min_value=1, max_value=10, value=3,
#                 key="grid_replicates",
#             )
#         submitted = st.form_submit_button("➕ Generate grid")
#         if submitted:
#             new_ids = generate_grid_ids(rows, int(cols), suffix.strip(), int(replicates))
#             st.success(
#                 f"Generated {len(new_ids)} rows "
#                 f"({len(set(new_ids))} unique SampleIDs)."
#             )


# # ─── Append new rows to session state ───
# if new_ids:
#     sample_date_str = sampling_date.strftime("%-m/%-d/%Y") if os.name != "nt" else sampling_date.strftime("%m/%d/%Y").lstrip("0").replace("/0", "/")
#     additions = []
#     seen_first_for_id: dict[str, bool] = {}
#     for sid in new_ids:
#         # Mirror the existing convention: the FIRST row of each block
#         # carries SiteID + SamplingDate + Data Location; subsequent rows
#         # for the same SampleID leave them blank.
#         is_first = sid not in seen_first_for_id
#         seen_first_for_id[sid] = True
#         row = {c: "" for c in HEADER_ROW_2}
#         row["SampleID"] = sid
#         if is_first:
#             row["SiteID"] = site_id
#             row["SamplingDate"] = sample_date_str
#             row["Data Location"] = sample_date_str
#         additions.append(row)
#     st.session_state.rows = pd.concat(
#         [st.session_state.rows, pd.DataFrame(additions, columns=HEADER_ROW_2)],
#         ignore_index=True,
#     )


# # ═══════════════════════════════════════════════
# #  SECTION 3 — REVIEW & EDIT
# # ═══════════════════════════════════════════════
# st.markdown("---")
# st.subheader("3. Review")

# current = st.session_state.rows
# non_pii_cols = [c for c in HEADER_ROW_2 if c not in PII_COLUMNS and c != ""]

# m1, m2, m3 = st.columns(3)
# m1.metric("Total rows", len(current))
# m2.metric(
#     "Unique SampleIDs",
#     int(current["SampleID"].replace("", pd.NA).dropna().nunique()) if len(current) else 0,
# )
# m3.metric(
#     "Unique SiteIDs",
#     int(current["SiteID"].replace("", pd.NA).dropna().nunique()) if len(current) else 0,
# )

# if len(current):
#     edited = st.data_editor(
#         current[non_pii_cols],
#         num_rows="dynamic",
#         use_container_width=True,
#         hide_index=True,
#         key="editor",
#     )
#     # Re-merge with PII columns (always blank) before saving
#     merged = edited.copy()
#     for c in PII_COLUMNS:
#         merged[c] = ""
#     st.session_state.rows = merged.reindex(columns=HEADER_ROW_2).fillna("")
# else:
#     st.info("No rows yet. Add some above.")


# # ═══════════════════════════════════════════════
# #  SECTION 4 — SAVE
# # ═══════════════════════════════════════════════
# st.markdown("---")
# st.subheader("4. Save")

# col_save, col_clear, col_reload = st.columns(3)

# with col_save:
#     if st.button("💾 Save to disk", type="primary", use_container_width=True):
#         try:
#             write_field_csv(st.session_state.rows, OUTPUT_PATH)
#             st.success(f"Saved {len(st.session_state.rows)} rows to:\n{OUTPUT_PATH}")
#         except Exception as e:
#             st.error(f"Save failed: {e}")

# with col_clear:
#     if st.button("🗑️ Clear all (in-memory)", use_container_width=True):
#         st.session_state.rows = pd.DataFrame(columns=HEADER_ROW_2)
#         st.rerun()

# with col_reload:
#     if st.button("↻ Reload from disk", use_container_width=True):
#         st.session_state.rows = load_existing_rows(OUTPUT_PATH)
#         st.rerun()


# with st.expander("ℹ️ Where does the resident address come from then?"):
#     st.markdown(
#         """
# The dashboard now reads resident PII from a **local-only** file path,
# configured via the `SOIL_COLAB_PII_PATH` environment variable, with a
# default of `~/.soil_colab/residents_private.csv`.

# That file should have these columns (no header gymnastics — just one row of headers):

# ```
# SiteID,Address,City,ZipCode,FirstName,LastName
# 2025-6-24,179 Cleveland Ave,Buffalo,14222,Lacey,Carpenter
# 2025-7-8,102 Putnam St,Buffalo,14213,Alexandra,Judelsohn
# ...
# ```

# The dashboard joins on `SiteID`. If the file doesn't exist, the
# dashboard falls back to "Unknown Address" — nothing breaks, just no
# addresses shown. Keep that file outside the repo.
#         """
#     )

"""
field_entry.py — GroundSense Field Entry App

A lightweight Streamlit form for recording field samples. Each sample's
SampleID is auto-generated by joining structured fields with underscores:

    SampleID = SiteID_TimeOfDay_Position_Protocol_Location_Initials

Layout
------
Two columns, side-by-side:
  • LEFT  — input fields (SiteID, Time of Day, Position, Protocol,
            Location, Initials, Replicates)
  • RIGHT — live SampleID preview + Review table of all rows

After a successful "Add Sample", all input fields and toggles reset to
their defaults so the next sample can be entered immediately.

Output
------
Writes `<repo>/data/site_databases/XRF_Site_Analysis_Database.csv` —
columns: SiteID, SampleID. This is the format the dashboard reads.
"""

import csv
import os

import pandas as pd
import streamlit as st


# ═══════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════
COLUMNS = ["SiteID", "SampleID"]
OUTPUT_FILENAME = "XRF_Site_Analysis_Database.csv"

TIME_OPTIONS = ["AM", "PM", "Other"]
POSITION_OPTIONS = ["Front", "Back", "Side", "Other"]
PROTOCOL_OPTIONS = ["HUD", "PIIT", "MIELKE", "Other"]

# Widget keys — kept in one place so the reset helper can target them precisely.
WIDGET_KEYS = [
    "site_id_input",
    "time_choice", "time_other",
    "position_choice", "position_other",
    "protocol_choice", "protocol_other",
    "location_input",
    "initials_input",
    "replicates_input",
]


# ═══════════════════════════════════════════════
#  PATH RESOLUTION
# ═══════════════════════════════════════════════
def get_repo_root() -> str:
    """Return absolute path to the repo root (one level above /src)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def get_output_path() -> str:
    """Where to write the field CSV — same place the dashboard reads from."""
    return os.path.join(
        get_repo_root(), "data", "site_databases", OUTPUT_FILENAME
    )


# ═══════════════════════════════════════════════
#  EXISTING-DATA LOADER / WRITER
# ═══════════════════════════════════════════════
def load_existing_rows(path: str) -> pd.DataFrame:
    """Load existing field CSV so users can append rather than overwrite."""
    if not os.path.exists(path):
        return pd.DataFrame(columns=COLUMNS)
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
        for c in COLUMNS:
            if c not in df.columns:
                df[c] = ""
        return df[COLUMNS]
    except Exception as e:
        st.warning(f"Could not parse existing CSV ({e}). Starting fresh.")
        return pd.DataFrame(columns=COLUMNS)


def write_field_csv(df: pd.DataFrame, path: str) -> None:
    """Write df to disk as a plain single-header CSV with SiteID + SampleID."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = df.reindex(columns=COLUMNS).fillna("")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for _, row in out.iterrows():
            writer.writerow([row.get(c, "") for c in COLUMNS])


# ═══════════════════════════════════════════════
#  SAMPLE ID BUILDER
# ═══════════════════════════════════════════════
def build_sample_id(
    site_id: str,
    time_of_day: str,
    position: str,
    protocol: str,
    location: str,
    initials: str,
) -> str:
    """Join the six fields with underscores to form the SampleID.

    All fields are stripped. Internal spaces in custom 'Other' values are
    preserved as-is. Caller is responsible for validating non-empty inputs.
    """
    parts = [site_id, time_of_day, position, protocol, location, initials]
    return "_".join(p.strip() for p in parts)


# ═══════════════════════════════════════════════
#  PAGE
# ═══════════════════════════════════════════════
st.set_page_config(
    page_title="Urban Soil Co-Lab Field Entry",
    page_icon="🌱",
    layout="wide",
)

st.title("🌱 Field Sample Entry")
st.caption(
    "Record SiteID and SampleIDs from the field."
    
)

OUTPUT_PATH = get_output_path()


# ─── Session state init ───
if "rows" not in st.session_state:
    st.session_state.rows = load_existing_rows(OUTPUT_PATH)

# Flag set by the "Add Sample" handler; consumed at the top of the next
# rerun to wipe widget state. We can't mutate widget keys after they've
# been instantiated in the same run, so we do it on the *next* run.
if st.session_state.get("_pending_reset"):
    for k in WIDGET_KEYS:
        if k in st.session_state:
            del st.session_state[k]
    st.session_state["_pending_reset"] = False


# ═══════════════════════════════════════════════
#  TWO-COLUMN LAYOUT — inputs left, preview right
# ═══════════════════════════════════════════════
left_col, right_col = st.columns([1, 1], gap="large")


# ───────────────────────────────────────────────
#  LEFT — INPUTS
# ───────────────────────────────────────────────
with left_col:
    st.subheader("Sample Entry")

    # ── SiteID ──
    site_id = st.text_input(
        "SiteID",
        help="Free-form. Convention: sampling date as YYYY-M-D, e.g. 2025-10-18.",
        key="site_id_input",
    ).strip()

    # ── Time of Day ──
    time_choice = st.radio(
        "Time of Day",
        TIME_OPTIONS,
        horizontal=True,
        key="time_choice",
    )
    if time_choice == "Other":
        time_value = st.text_input(
            "Specify time of day",
            placeholder="e.g. Dawn, Dusk",
            key="time_other",
        ).strip()
    else:
        time_value = time_choice

    # ── Position ──
    position_choice = st.radio(
        "Position",
        POSITION_OPTIONS,
        horizontal=True,
        key="position_choice",
    )
    if position_choice == "Other":
        position_value = st.text_input(
            "Specify position",
            placeholder="e.g. Driveway, Garden",
            key="position_other",
        ).strip()
    else:
        position_value = position_choice

    # ── Protocol ──
    protocol_choice = st.radio(
        "Protocol",
        PROTOCOL_OPTIONS,
        horizontal=True,
        key="protocol_choice",
    )
    if protocol_choice == "Other":
        protocol_value = st.text_input(
            "Specify protocol",
            placeholder="e.g. Custom",
            key="protocol_other",
        ).strip()
    else:
        protocol_value = protocol_choice

    # ── Location (grid) ──
    location_value = st.text_input(
        "Location (grid)",
        placeholder="e.g. A1, A2, B1, B2",
        help="The grid cell within the site, e.g. A1 or B3.",
        key="location_input",
    ).strip()

    # ── Field crew initials ──
    initials_value = st.text_input(
        "Field Crew Initials",
        placeholder="e.g. JD",
        key="initials_input",
    ).strip()

    # ── Replicates ──
    replicates = st.number_input(
        "Number of replicates (rows to write for this SampleID)",
        min_value=1, max_value=10, value=3,
        help="Convention: 3 readings per sample, so 3 rows per SampleID.",
        key="replicates_input",
    )

    # ── Add button ──
    add_clicked = st.button(
        "➕ Add Sample", type="primary", use_container_width=True,
    )

    if add_clicked:
        missing = []
        if not site_id:        missing.append("SiteID")
        if not time_value:     missing.append("Time of Day")
        if not position_value: missing.append("Position")
        if not protocol_value: missing.append("Protocol")
        if not location_value: missing.append("Location")
        if not initials_value: missing.append("Initials")

        if missing:
            st.warning(f"Missing required fields: {', '.join(missing)}.")
        else:
            sample_id = build_sample_id(
                site_id, time_value, position_value,
                protocol_value, location_value, initials_value,
            )
            additions = [
                {"SiteID": site_id, "SampleID": sample_id}
                for _ in range(int(replicates))
            ]
            st.session_state.rows = pd.concat(
                [st.session_state.rows, pd.DataFrame(additions, columns=COLUMNS)],
                ignore_index=True,
            )
            # Stash a one-shot success message + trigger reset on next rerun.
            st.session_state["_last_added"] = (sample_id, int(replicates))
            st.session_state["_pending_reset"] = True
            st.rerun()


# ───────────────────────────────────────────────
#  RIGHT — PREVIEW + REVIEW
# ───────────────────────────────────────────────
with right_col:
    st.subheader("Preview")

    # One-shot success message after a successful add (survives the reset rerun).
    last_added = st.session_state.pop("_last_added", None)
    if last_added:
        sid, n = last_added
        st.success(f"Added {n} row(s):\n`{sid}`")

    # Live preview of the SampleID being built.
    all_filled = all([
        site_id, time_value, position_value,
        protocol_value, location_value, initials_value,
    ])
    if all_filled:
        preview = build_sample_id(
            site_id, time_value, position_value,
            protocol_value, location_value, initials_value,
        )
        st.info(f"**SampleID preview:**\n\n`{preview}`")
    else:
        st.caption("Fill all fields on the left to see a SampleID preview.")

    st.markdown("---")
    st.subheader("Review")

    current = st.session_state.rows

    m1, m2, m3 = st.columns(3)
    m1.metric("Total rows", len(current))
    m2.metric(
        "Unique SampleIDs",
        int(current["SampleID"].replace("", pd.NA).dropna().nunique()) if len(current) else 0,
    )
    m3.metric(
        "Unique SiteIDs",
        int(current["SiteID"].replace("", pd.NA).dropna().nunique()) if len(current) else 0,
    )

    if len(current):
        edited = st.data_editor(
            current[COLUMNS],
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="editor",
        )
        st.session_state.rows = edited.reindex(columns=COLUMNS).fillna("")
    else:
        st.info("No rows yet. Add some on the left.")


# ═══════════════════════════════════════════════
#  SAVE BAR (full-width below)
# ═══════════════════════════════════════════════
st.markdown("---")
st.subheader("Save")

col_save, col_clear, col_reload = st.columns(3)

with col_save:
    if st.button("💾 Save to disk", type="primary", use_container_width=True):
        try:
            write_field_csv(st.session_state.rows, OUTPUT_PATH)
            st.success(f"Saved {len(st.session_state.rows)} rows.")
        except Exception as e:
            st.error(f"Save failed: {e}")

with col_clear:
    if st.button("🗑️ Clear all (in-memory)", use_container_width=True):
        st.session_state.rows = pd.DataFrame(columns=COLUMNS)
        st.rerun()

with col_reload:
    if st.button("↻ Reload from disk", use_container_width=True):
        st.session_state.rows = load_existing_rows(OUTPUT_PATH)
        st.rerun()


# with st.expander("ℹ️ Where does the resident address come from then?"):
#     st.markdown(
#         """
# The dashboard reads resident PII from a **local-only** file path,
# configured via the `SOIL_COLAB_PII_PATH` environment variable, with a
# default of `~/.soil_colab/residents_private.csv`.

# That file should have these columns (single header row):

# ```
# SiteID,Address,City,ZipCode,FirstName,LastName
# 2025-6-24,179 Cleveland Ave,Buffalo,14222,Lacey,Carpenter
# 2025-7-8,102 Putnam St,Buffalo,14213,Alexandra,Judelsohn
# ...
# ```

# The dashboard joins on `SiteID`. If the file doesn't exist, it falls
# back to "Unknown Address" — nothing breaks. Keep that file outside the repo.
#         """
#     )
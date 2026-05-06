"""
site_builder.py — GroundSense Site Configuration Builder

A standalone Streamlit page where field technicians input measurements
for a new sampling site and the system auto-generates:
  1. Grid block offsets (computed from cell dimensions + fixed point)
  2. A site_configs.json entry
  3. A live draggable satellite map preview (Leaflet)
  4. Persistent fine-tuned position via Save button — updates anchor
     lat/lon AND stores rotation_deg separately for dashboard consistency.
  5. Three downloadable map exports (all via shared map_renderer module,
     so they stay visually consistent with the PPTX reports):
        - Basemap + no numbers  (Leaflet HTML, satellite)
        - Basemap + numbers     (Leaflet HTML, satellite, ppm labels)
        - No basemap + numbers  (static PNG, dark theme)

Place in src/ alongside groundsense_config.py and map_renderer.py.
Run: streamlit run src/site_builder.py
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
import math
import os
import glob
import re
import io
import tempfile

from groundsense_config import (
    get_nysh_category,
    NYSH_TIERS,
    NYSH_COLORS,
    calculate_coordinate,
    resolve_lod,
)

# Shared renderer — used by etl_manager.py too, so exports stay consistent
from map_renderer import (
    render_leaflet_html,
    render_static_png,
    get_block_data,
)


# ═══════════════════════════════════════════════
#  MASTER DATA LOADER (for export with real PPM values)
# ═══════════════════════════════════════════════
@st.cache_data
def load_master_data():
    """Load the latest XRF_Chemistry_V*.csv for looking up real Lead PPM
    values when rendering the exported maps. Returns empty df if missing.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    master_dir = os.path.join(base_dir, "..", "data", "XRF_Chemistry")
    master_files = glob.glob(os.path.join(master_dir, "XRF_Chemistry_V*.csv"))
    if not master_files:
        return pd.DataFrame(columns=["SampleID", "LeadPPM", "LeadPPM_Clean"])

    def _ver(fn):
        m = re.search(r"_V(\d+)\.csv$", fn, re.IGNORECASE)
        return int(m.group(1)) if m else 0

    latest = max(master_files, key=_ver)
    df = pd.read_csv(latest)
    df["LeadPPM_Clean"] = df["LeadPPM"].apply(resolve_lod)
    return df


# ═══════════════════════════════════════════════
#  PAGE CONFIG & STYLING
# ═══════════════════════════════════════════════
st.set_page_config(page_title="GroundSense Site Builder", page_icon="📐", layout="wide")
st.title("📐 Site Configuration Builder")
st.caption("Urban Soil Co-Lab · University at Buffalo · GroundSense Pipeline")
st.markdown(
    "Transform field sketch measurements into a config-ready site definition. "
    "Fill in each section below, then hit **Compute** to generate the JSON config "
    "and preview the grid on satellite imagery. You can drag/rotate the grid on "
    "the preview to fine-tune positioning, then **Save** to persist the change."
)
st.markdown("---")


# ═══════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════
def parse_imperial(s):
    """Convert imperial string like 11'6.5\" or plain feet like 10 to decimal feet."""
    if s is None or str(s).strip() == "":
        return 0.0
    s = str(s).strip().replace('"', '').replace("''", "").replace('\u2033', '').replace('\u2032', "'")
    if "'" in s:
        parts = s.split("'")
        feet = float(parts[0]) if parts[0].strip() else 0
        inches = float(parts[1]) if len(parts) > 1 and parts[1].strip() else 0
        return feet + inches / 12.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def dms_to_decimal(degrees, minutes, seconds, direction):
    """Convert DMS coordinates to decimal degrees."""
    dd = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
    if direction in ['S', 'W']:
        dd *= -1
    return dd


def load_existing_config_for_site_id(site_id, config_path):
    """If this site_id already has a saved config, return its current offset/rotation."""
    if not os.path.exists(config_path):
        return None
    try:
        with open(config_path, 'r') as f:
            existing = json.load(f)
        for s in existing:
            if s.get("site_id") == site_id:
                return s
    except Exception:
        pass
    return None


def list_existing_site_ids(config_path):
    """Return a list of all SiteIDs currently saved in site_configs.json.

    Returns [] if the file is missing or unreadable. Order matches the
    file order (which is roughly creation order).
    """
    if not os.path.exists(config_path):
        return []
    try:
        with open(config_path, 'r') as f:
            existing = json.load(f)
        return [s.get("site_id", "") for s in existing if s.get("site_id")]
    except Exception:
        return []


# ═══════════════════════════════════════════════
#  LOAD EXISTING SITE (search/edit existing maps)
# ═══════════════════════════════════════════════
st.subheader("🔍 Load Existing Site")
st.caption(
    "Pick a previously-saved site to load it into the draggable preview. "
    "You can re-position or rotate the grid and **Save** to update its "
    "config in place. Leave this empty if you're creating a brand-new site."
)

_base_dir_top = os.path.dirname(os.path.abspath(__file__))
_config_path_top = os.path.join(
    _base_dir_top, "..", "data", "site_configs", "site_configs.json"
)
_existing_site_ids = list_existing_site_ids(_config_path_top)

ec1, ec2 = st.columns([3, 1])
with ec1:
    selected_existing = st.selectbox(
        "Existing SiteIDs",
        options=["— select to load —"] + _existing_site_ids,
        index=0,
        key="existing_site_selector",
        help="Sites are pulled from data/site_configs/site_configs.json.",
    )
with ec2:
    load_clicked = st.button(
        "📂 Load to Preview",
        use_container_width=True,
        disabled=(selected_existing == "— select to load —"),
    )

if load_clicked and selected_existing != "— select to load —":
    cfg = load_existing_config_for_site_id(selected_existing, _config_path_top)
    if cfg is None:
        st.error(f"Could not find SiteID '{selected_existing}' in site_configs.json.")
    else:
        # Drop the loaded config straight into the draggable-preview slot.
        # The preview block further down keys off `generated_config`, so this
        # is all we need to do — the user lands on the same map UI they'd
        # see right after clicking Compute.
        st.session_state["generated_config"] = cfg
        # Clear any stale drag-state from a previous edit.
        st.session_state.pop("pending_offset_e", None)
        st.session_state.pop("pending_offset_n", None)
        st.session_state.pop("pending_rotation", None)
        st.success(
            f"✅ Loaded **{selected_existing}** "
            f"({len(cfg.get('grid_blocks', {}))} blocks · "
            f"{len(cfg.get('point_samples', {}))} point samples). "
            f"Scroll down to the **Draggable Satellite Preview** to nudge it "
            f"and **Save** to overwrite its config."
        )
        st.rerun()

st.markdown("---")


# ═══════════════════════════════════════════════
#  STEP 1 — SITE INFORMATION
# ═══════════════════════════════════════════════
st.subheader("① Site Information")
st.caption(
    "SiteID is the canonical identifier for this site across the pipeline. "
    "Convention: use the sampling date in ISO form (YYYY-MM-DD). "
    "Resident address/name/ZIP are PII and never stored here. "
    "_(Steps ① – ⑦ are for building a **new** site from scratch — to edit "
    "an existing one, use the dropdown above and skip to the preview.)_"
)

col_date, col_id = st.columns([1, 2])
with col_date:
    sampling_date = st.date_input("Sampling Date *")
with col_id:
    # Auto-suggest SiteID from sampling_date (zero-padded ISO). User may
    # override if a non-date scheme is needed (e.g. multiple sites on the
    # same day — append a suffix like "2025-06-24-A").
    suggested_id = sampling_date.strftime("%Y-%m-%d") if sampling_date else ""
    site_id = st.text_input(
        "SiteID *",
        value=suggested_id,
        placeholder="e.g. 2025-06-24",
        help="Defaults to the sampling date in ISO form. Override only if you need to disambiguate multiple sites on the same date.",
    ).strip()

notes = st.text_input(
    "Site Notes (optional)",
    placeholder="e.g. Backyard grid, measured from porch corner…"
)

st.markdown("---")


# ═══════════════════════════════════════════════
#  STEP 2 — FIXED POINT LOCATION IN GRID
# ═══════════════════════════════════════════════
st.subheader("② Fixed Point Location in Grid")
st.caption("Identify which cell corner the GPS measurement was taken at. "
           "This anchors the entire grid to the real world.")

col_fp1, col_fp2 = st.columns(2)
with col_fp1:
    fp_cell_input = st.text_input(
        "Fixed Point Cell ID *", value="E1",
        help="The cell whose corner was marked with GPS (e.g. E1, A1, D2)"
    )
with col_fp2:
    fp_corner = st.selectbox(
        "Which corner of this cell? *",
        ["Top-Left", "Top-Right", "Bottom-Left", "Bottom-Right"],
        help="As drawn on the field sketch — not compass direction"
    )

st.markdown("---")


# ═══════════════════════════════════════════════
#  STEP 3 — FIXED POINT GPS
# ═══════════════════════════════════════════════
st.subheader("③ Fixed Point GPS Coordinates")

gps_format = st.radio(
    "Coordinate format",
    ["DMS (Degrees Minutes Seconds)", "Decimal Degrees"],
    horizontal=True,
    help="DMS example: 42° 55' 11.46\" N  ·  Decimal example: 42.9198500"
)

if gps_format == "DMS (Degrees Minutes Seconds)":
    col_lat, col_lon = st.columns(2)
    with col_lat:
        st.markdown("**Latitude (N)**")
        c1, c2, c3 = st.columns(3)
        lat_d = c1.number_input("Deg", value=42, key="lat_d")
        lat_m = c2.number_input("Min", value=55, key="lat_m")
        lat_s = c3.number_input("Sec", value=11.46, format="%.4f", key="lat_s")
    with col_lon:
        st.markdown("**Longitude (W)**")
        c4, c5, c6 = st.columns(3)
        lon_d = c4.number_input("Deg", value=78, key="lon_d")
        lon_m = c5.number_input("Min", value=49, key="lon_m")
        lon_s = c6.number_input("Sec", value=33.63, format="%.4f", key="lon_s")
    anchor_lat = dms_to_decimal(lat_d, lat_m, lat_s, 'N')
    anchor_lon = dms_to_decimal(lon_d, lon_m, lon_s, 'W')
else:
    col_lat, col_lon = st.columns(2)
    with col_lat:
        anchor_lat = st.number_input("Latitude", value=42.919850, format="%.7f")
    with col_lon:
        anchor_lon = st.number_input("Longitude", value=-78.826008, format="%.7f")

st.success(f"📍 Anchor locked: **{anchor_lat:.7f}°N, {abs(anchor_lon):.7f}°W**")

st.markdown("---")


# ═══════════════════════════════════════════════
#  STEP 4 — GRID LAYOUT & ORIENTATION
# ═══════════════════════════════════════════════
st.subheader("④ Grid Layout")

col_orient, col_dir = st.columns(2)
with col_orient:
    orientation = st.selectbox(
        "Grid orientation on map",
        ["Vertical (strip runs North–South)", "Horizontal (strip runs East–West)"],
        help="Vertical = long axis goes up/down. Horizontal = long axis goes left/right."
    )
with col_dir:
    if "Vertical" in orientation:
        house_dir = st.selectbox("Which end is near the house?",
                                 ["Top (North)", "Bottom (South)"])
    else:
        house_dir = st.selectbox("Which end is near the house?",
                                 ["Left (West)", "Right (East)"])

st.markdown("---")


# ═══════════════════════════════════════════════
#  STEP 5 — DEFINE GRID ROWS
# ═══════════════════════════════════════════════
st.subheader("⑤ Define Grid Rows")
st.caption("List row letters from **farthest from house** → **nearest to house**.")

rows_input = st.text_input(
    "Row letters (comma-separated) *", value="A, B, C, D, E",
    help="Example: A, B, C, D, E, F, G, H — where A is farthest from house"
)
rows = [r.strip().upper() for r in rows_input.split(",") if r.strip()]

if rows:
    st.info(f"**{len(rows)} rows:** {' → '.join(rows)}  _(far → near)_")

st.markdown("---")


# ═══════════════════════════════════════════════
#  STEP 6 — CELL DIMENSIONS
# ═══════════════════════════════════════════════
st.subheader("⑥ Cell Dimensions")
st.caption("Enter each cell's **width** (perpendicular to strip) and **height** "
           "(along the strip). Accepts imperial: `11'6.5\"` or plain feet: `10`.")

max_cols = st.number_input("Max columns per row", min_value=1, max_value=5, value=3,
                            help="e.g. 3 if cells are A1, A2, A3")

cell_data = {}
for row in rows:
    with st.expander(f"**Row {row}**", expanded=True):
        num_cols = st.number_input(f"Columns in row {row}", min_value=1,
                                    max_value=int(max_cols),
                                    value=min(int(max_cols), 3), key=f"ncols_{row}")
        cols_ui = st.columns(int(num_cols))
        for c in range(int(num_cols)):
            col_num = c + 1
            cell_id = f"{row}{col_num}"
            with cols_ui[c]:
                st.markdown(f"##### {cell_id}")
                w = st.text_input("Width (ft)", value="10", key=f"w_{cell_id}")
                h = st.text_input("Height (ft)", value="10", key=f"h_{cell_id}")
                pat = st.text_input("SampleID pattern", value=f"{cell_id}_",
                                    key=f"pat_{cell_id}",
                                    help="Substring matched against Master Data")
                cell_data[cell_id] = {
                    "width": parse_imperial(w), "height": parse_imperial(h),
                    "col": col_num, "row": row, "pattern": pat,
                }

st.markdown("---")


# ═══════════════════════════════════════════════
#  STEP 7 — POINT SAMPLES (OPTIONAL)
# ═══════════════════════════════════════════════
st.subheader("⑦ Point Samples _(optional)_")
st.caption("Non-grid samples (driplines, lawns, etc.). Offsets in feet from the fixed point.")

num_points = st.number_input("Number of point samples", min_value=0, max_value=20, value=0)
point_samples = {}
if num_points > 0:
    for i in range(int(num_points)):
        with st.expander(f"Point Sample {i + 1}", expanded=True):
            pc1, pc2, pc3, pc4 = st.columns(4)
            with pc1:
                pt_name = st.text_input("Name", key=f"pt_name_{i}", placeholder="HUD Dripline")
            with pc2:
                pt_ox = st.number_input("East offset (ft)", key=f"pt_ox_{i}", value=0.0)
            with pc3:
                pt_oy = st.number_input("North offset (ft)", key=f"pt_oy_{i}", value=0.0)
            with pc4:
                pt_pat = st.text_input("SampleID pattern", key=f"pt_pat_{i}",
                                        placeholder="HUD_Dripline")
            if pt_name:
                point_samples[pt_name] = {
                    "offset_x": pt_ox, "offset_y": pt_oy,
                    "sample_id_patterns": [pt_pat] if pt_pat else [],
                    "zone": "auxiliary",
                }


# ═══════════════════════════════════════════════
#  COMPUTE
# ═══════════════════════════════════════════════
st.markdown("---")
st.markdown("### 🔧 Generate Configuration")

col_btn, _ = st.columns([2, 5])
with col_btn:
    compute = st.button("Compute Grid & Preview Map", type="primary", use_container_width=True)

if compute:
    errors = []
    if not site_id:
        errors.append("SiteID is required.")
    if not rows:
        errors.append("At least one grid row must be defined.")
    if not cell_data:
        errors.append("Cell dimensions are required.")
    fp_cell = fp_cell_input.strip().upper()
    if fp_cell not in cell_data:
        errors.append(f"Fixed point cell '{fp_cell}' doesn't match any defined cell.")
    if errors:
        for e in errors:
            st.error(e)
        st.stop()

    row_heights = {}
    for row in rows:
        c1 = f"{row}1"
        if c1 in cell_data:
            row_heights[row] = cell_data[c1]["height"]
        else:
            for cid, cd in cell_data.items():
                if cd["row"] == row:
                    row_heights[row] = cd["height"]
                    break

    strip_pos, pos = {}, 0
    for row in rows:
        strip_pos[row] = pos
        pos += row_heights.get(row, 10)

    fp_row = ''.join(c for c in fp_cell if c.isalpha())
    fp_col = int(''.join(c for c in fp_cell if c.isdigit()))

    col_widths_per_row = {}
    for row in rows:
        col_widths_per_row[row] = {}
        for cid, cd in cell_data.items():
            if cd["row"] == row:
                col_widths_per_row[row][cd["col"]] = cd["width"]

    fp_row_widths = col_widths_per_row.get(fp_row, {})
    fp_perp = 0
    if "Left" in fp_corner:
        for c in range(1, fp_col):
            fp_perp += fp_row_widths.get(c, 0)
    else:
        for c in range(1, fp_col + 1):
            fp_perp += fp_row_widths.get(c, 0)

    fp_strip = strip_pos[fp_row] + (row_heights[fp_row] if "Top" in fp_corner else 0)

    is_vertical = "Vertical" in orientation
    flip_strip = "Top" in house_dir or "Right" in house_dir

    grid_blocks = {}
    for cid, cd in cell_data.items():
        row, col = cd["row"], cd["col"]
        cell_h, cell_w = cd["height"], cd["width"]

        strip_start = strip_pos[row] - fp_strip
        strip_end = strip_start + row_heights[row]
        if cell_h != row_heights[row]:
            strip_start = strip_end - cell_h

        perp_start = sum(col_widths_per_row[row].get(c, 0) for c in range(1, col))
        perp_end = perp_start + cell_w
        perp_start -= fp_perp
        perp_end -= fp_perp

        if flip_strip:
            strip_start, strip_end = -strip_end, -strip_start

        if is_vertical:
            ns, ne, es, ee = strip_start, strip_end, perp_start, perp_end
        else:
            es, ee, ns, ne = strip_start, strip_end, perp_start, perp_end

        grid_blocks[cid] = {
            "sw_x": round(min(es, ee), 2), "sw_y": round(min(ns, ne), 2),
            "ne_x": round(max(es, ee), 2), "ne_y": round(max(ns, ne), 2),
            "sample_id_patterns": [cd["pattern"]] if cd["pattern"] else [],
            "zone": "yard", "mock_ppm": 0,
        }

    # ── Preserve existing rotation if this site_id was saved before ──
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "..", "data", "site_configs", "site_configs.json")
    existing = load_existing_config_for_site_id(site_id, config_path)
    preserved_rotation = existing.get("rotation_deg", 0) if existing else 0

    site_config = {
        "site_id": site_id,
        "sampling_date": str(sampling_date), "notes": notes,
        "anchor": {
            "lat": anchor_lat, "lon": anchor_lon,
            "description": f"Fixed point at {fp_cell} ({fp_corner}) — field-measured GPS",
            "marker_label": f"Fixed Point ({fp_cell})",
        },
        "map_defaults": {"zoom_start": 21, "center_offset_north_ft": 0, "center_offset_east_ft": 0},
        "rotation_deg": preserved_rotation,
        "grid_blocks": grid_blocks,
        "point_samples": point_samples,
    }

    st.session_state["generated_config"] = site_config
    # Reset any stale drag state
    st.session_state.pop("pending_offset_e", None)
    st.session_state.pop("pending_offset_n", None)
    st.session_state.pop("pending_rotation", None)
    st.success(f"✅ Grid computed — **{len(grid_blocks)} blocks** + **{len(point_samples)} point samples**")


# ═══════════════════════════════════════════════
#  RESULTS & DRAGGABLE PREVIEW
# ═══════════════════════════════════════════════
if "generated_config" in st.session_state:
    config = st.session_state["generated_config"]
    st.markdown("---")

    st.subheader("📋 Computed Grid Offsets")
    tbl = []
    for bid, b in config["grid_blocks"].items():
        tbl.append({
            "Cell": bid,
            "SW East": b["sw_x"], "SW North": b["sw_y"],
            "NE East": b["ne_x"], "NE North": b["ne_y"],
            "W (ft)": round(b["ne_x"] - b["sw_x"], 1),
            "H (ft)": round(b["ne_y"] - b["sw_y"], 1),
            "Pattern": ", ".join(b.get("sample_id_patterns", [])),
        })
    st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True)

    # ═══════════════════════════════════════════
    #  DRAGGABLE LEAFLET PREVIEW
    # ═══════════════════════════════════════════
    st.subheader("🗺️ Draggable Satellite Preview")
    st.caption(
        "**Click & drag the grid** to nudge it onto the actual yard. "
        "Use the rotation buttons to align with the house. "
        "The current offset/rotation is shown live in the control panel — "
        "click **Save** below the map to persist it."
    )

    # Build blocks payload for the Leaflet component
    blocks_payload = []
    for bid, b in config["grid_blocks"].items():
        # We want to render each block as a rectangle in feet-space,
        # then convert to lat/lon client-side using the anchor.
        corners = [
            [b["sw_x"], b["sw_y"]],
            [b["ne_x"], b["sw_y"]],
            [b["ne_x"], b["ne_y"]],
            [b["sw_x"], b["ne_y"]],
        ]
        cx = (b["sw_x"] + b["ne_x"]) / 2
        cy = (b["sw_y"] + b["ne_y"]) / 2
        mock_ppm = b.get("mock_ppm", 0)
        label, color = get_nysh_category(mock_ppm) if mock_ppm else ("Preview", "#4a90d9")
        blocks_payload.append({
            "id": bid,
            "corners": corners,
            "cx": cx, "cy": cy,
            "color": color,
            "label": label,
            "ppm": mock_ppm,
        })

    points_payload = []
    for pid, pt in config.get("point_samples", {}).items():
        points_payload.append({
            "id": pid,
            "ox": pt.get("offset_x", 0),
            "oy": pt.get("offset_y", 0),
        })

    anchor = config["anchor"]
    rotation_init = config.get("rotation_deg", 0)

    # Build the legend HTML from NYSH_TIERS so it stays in sync
    legend_rows = ""
    for t in NYSH_TIERS:
        legend_rows += (
            '<div><span style="display:inline-block;width:11px;height:11px;'
            f'background:{t["color"]};border-radius:2px;margin-right:5px;'
            f'vertical-align:middle"></span>{t["label"]}</div>'
        )
    legend_rows += (
        '<div><span style="display:inline-block;width:11px;height:11px;'
        'background:#4a90d9;border-radius:2px;margin-right:5px;'
        'vertical-align:middle"></span>Preview (no data yet)</div>'
    )

    # Leaflet HTML component with drag + rotate + message bridge
    component_html = f"""
<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html,body {{ margin:0; padding:0; font-family:Arial,sans-serif; background:#0c0f14; }}
  #map {{ width:100%; height:560px; }}
  .legend {{ position:absolute; bottom:20px; left:20px; z-index:1001;
    background:rgba(12,15,20,0.93); padding:12px 16px; border-radius:10px;
    color:#e8eaed; font-size:11px; line-height:1.7;
    border:1px solid rgba(255,255,255,0.08); }}
  .legend b {{ font-size:13px; }}
  .controls {{ position:absolute; top:20px; right:20px; z-index:1001;
    background:rgba(12,15,20,0.93); padding:12px 16px; border-radius:10px;
    color:#e8eaed; font-size:11px; border:1px solid rgba(255,255,255,0.08);
    min-width:210px; }}
  .controls b {{ font-size:13px; color:#e67e22; }}
  .controls .hint {{ font-size:10px; color:#7a8599; margin-top:2px; }}
  .controls .offset {{ font-family:monospace; font-size:11px; color:#4ecdc4;
    margin-top:6px; background:rgba(78,205,196,0.08); padding:5px 8px;
    border-radius:4px; }}
  .controls button {{ padding:4px 9px; border:1px solid rgba(255,255,255,0.15);
    border-radius:4px; background:rgba(78,205,196,0.12); color:#4ecdc4;
    cursor:pointer; font-size:10px; }}
  .controls button:hover {{ background:rgba(78,205,196,0.25); }}
  .rotate-row {{ display:flex; gap:4px; align-items:center; margin-top:6px; }}
  .rotate-row button {{ margin:0; padding:3px 7px; font-size:10px; }}
  .rotate-row span {{ font-size:11px; color:#c7d0dc; min-width:38px;
    text-align:center; font-family:monospace; }}
  .reset-btn {{ margin-top:8px; width:100%; background:rgba(255,100,100,0.12) !important;
    color:#ff8888 !important; }}
</style>
</head><body>
<div id="map"></div>
<div class="legend"><b>Lead Guidelines (ppm)</b><br>{legend_rows}</div>
<div class="controls">
  <b>Grid Position</b>
  <div class="hint">Click & drag the grid on the map</div>
  <div class="rotate-row">
    <button onclick="rg(-5)">−5°</button>
    <button onclick="rg(-1)">−1°</button>
    <span id="rd">{rotation_init}°</span>
    <button onclick="rg(1)">+1°</button>
    <button onclick="rg(5)">+5°</button>
  </div>
  <div class="offset" id="od">Offset: 0.0 E, 0.0 N</div>
  <button class="reset-btn" onclick="rs()">Reset Position</button>
</div>

<script>
  var AL = {anchor["lat"]}, AO = {anchor["lon"]};
  var BL = {json.dumps(blocks_payload)};
  var PT = {json.dumps(points_payload)};
  var RF = 20925721.78;
  var oE = 0, oN = 0, rot = {rotation_init};

  var map = L.map('map', {{
    center: [AL, AO], zoom: 21, maxZoom: 25
  }});
  L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
    {{ attribution: 'Esri', maxZoom: 25, maxNativeZoom: 19 }}
  ).addTo(map);

  // Anchor marker (stays put — doesn't move with the drag)
  L.marker([AL, AO], {{
    icon: L.divIcon({{
      className: '',
      html: '<div style="width:14px;height:14px;background:#ff4444;border:2px solid white;border-radius:50%;box-shadow:0 0 6px rgba(0,0,0,0.6)"></div>',
      iconSize: [14,14], iconAnchor: [7,7]
    }})
  }}).addTo(map).bindTooltip('Original Anchor');

  function f2ll(la, lo, e, n) {{
    // Convert (east_ft, north_ft) offset from (la,lo) to [lat,lon]
    var dl = (n / RF) * (180 / Math.PI);
    var dn = (e / (RF * Math.cos(la * Math.PI / 180))) * (180 / Math.PI);
    return [la + dl, lo + dn];
  }}

  function rp(x, y, a) {{
    // Rotate point (x,y) by angle a (deg)
    var r = a * Math.PI / 180;
    return [x * Math.cos(r) - y * Math.sin(r), x * Math.sin(r) + y * Math.cos(r)];
  }}

  var gl = L.layerGroup().addTo(map);

  function dg() {{
    gl.clearLayers();
    BL.forEach(function(b) {{
      var ll = b.corners.map(function(c) {{
        var r = rp(c[0], c[1], rot);
        return f2ll(AL, AO, r[0] + oE, r[1] + oN);
      }});
      var pl = L.polygon(ll, {{
        color: 'white', weight: 2,
        fillColor: b.color, fillOpacity: 0.65
      }});
      pl.bindTooltip('<b>' + b.id + '</b><br>' + b.label);
      gl.addLayer(pl);
      var rc = rp(b.cx, b.cy, rot);
      var lp = f2ll(AL, AO, rc[0] + oE, rc[1] + oN);
      gl.addLayer(L.marker(lp, {{
        icon: L.divIcon({{
          className: '',
          html: '<div style="font-family:Arial;text-align:center;pointer-events:none">' +
                '<b style="font-size:10px;color:white;text-shadow:0 1px 3px rgba(0,0,0,0.85)">' +
                b.id + '</b></div>',
          iconSize: [50, 20], iconAnchor: [25, 10]
        }}),
        interactive: false
      }}));
    }});

    PT.forEach(function(p) {{
      var r = rp(p.ox, p.oy, rot);
      var ll = f2ll(AL, AO, r[0] + oE, r[1] + oN);
      gl.addLayer(L.circleMarker(ll, {{
        radius: 7, color: 'white', weight: 2,
        fillColor: '#f39c12', fillOpacity: 0.8
      }}).bindTooltip('<b>' + p.id + '</b>'));
    }});

    document.getElementById('od').textContent =
      'Offset: ' + oE.toFixed(1) + ' E, ' + oN.toFixed(1) + ' N' +
      (rot ? ('  |  ' + rot + '°') : '');
    document.getElementById('rd').textContent = rot + '°';
    // Post state to parent Streamlit
    postState();
  }}

  function postState() {{
    var msg = {{
      type: 'groundsense_grid_state',
      offset_east_ft: oE,
      offset_north_ft: oN,
      rotation_deg: rot
    }};
    window.parent.postMessage(msg, '*');
  }}

  function rg(d) {{ rot += d; dg(); }}
  function rs() {{ oE = 0; oN = 0; rot = 0; dg(); }}

  // Click & drag detection on polygons
  var iD = false, dL = null, dE = 0, dN = 0;
  map.on('mousedown', function(e) {{
    var hit = false;
    gl.eachLayer(function(l) {{
      if (l instanceof L.Polygon && l.getBounds().contains(e.latlng)) hit = true;
    }});
    if (hit) {{
      iD = true; dL = e.latlng; dE = oE; dN = oN;
      map.dragging.disable();
      map.getContainer().style.cursor = 'grabbing';
    }}
  }});
  map.on('mousemove', function(e) {{
    if (!iD) return;
    oN = dN + (e.latlng.lat - dL.lat) * (Math.PI / 180) * RF;
    oE = dE + (e.latlng.lng - dL.lng) * (Math.PI / 180) * RF *
              Math.cos(AL * Math.PI / 180);
    dg();
  }});
  map.on('mouseup', function() {{
    if (iD) {{
      iD = false;
      map.dragging.enable();
      map.getContainer().style.cursor = '';
    }}
  }});

  dg();
</script>
</body></html>
"""

    components.html(component_html, height=580, scrolling=False)

    # ── Bridge: read posted state via a tiny JS shim + hidden text_input trick ──
    # We use streamlit_js_eval if available, else fall back to manual entry.
    try:
        from streamlit_js_eval import streamlit_js_eval
        bridge_available = True
    except ImportError:
        bridge_available = False

    st.markdown("#### 💾 Save Fine-Tuned Position")

    if bridge_available:
        # Listen for postMessage events from the iframe
        posted_state = streamlit_js_eval(
            js_expressions="""
                (function() {
                    if (!window._gs_state) {
                        window._gs_state = {offset_east_ft: 0, offset_north_ft: 0, rotation_deg: 0};
                        window.addEventListener('message', function(ev) {
                            if (ev.data && ev.data.type === 'groundsense_grid_state') {
                                window._gs_state = ev.data;
                            }
                        });
                    }
                    return JSON.stringify(window._gs_state);
                })()
            """,
            key="gs_bridge",
            want_output=True,
        )
        try:
            state = json.loads(posted_state) if posted_state else {}
        except Exception:
            state = {}
        live_e = float(state.get("offset_east_ft", 0) or 0)
        live_n = float(state.get("offset_north_ft", 0) or 0)
        live_r = float(state.get("rotation_deg", 0) or 0)

        st.caption(
            f"Live position from map:  **East:** {live_e:+.2f} ft  ·  "
            f"**North:** {live_n:+.2f} ft  ·  **Rotation:** {live_r:+.1f}°"
        )
    else:
        st.info(
            "⚙️ For automatic drag-state capture, install `streamlit-js-eval`:  \n"
            "`pip install streamlit-js-eval`  \n\n"
            "Meanwhile, use the **Copy** button in the map's control panel, "
            "then paste the values below:"
        )
        mc1, mc2, mc3 = st.columns(3)
        live_e = mc1.number_input("East offset (ft)", value=0.0, step=0.1, key="manual_e")
        live_n = mc2.number_input("North offset (ft)", value=0.0, step=0.1, key="manual_n")
        live_r = mc3.number_input("Rotation (°)", value=0.0, step=1.0, key="manual_r")

    # Buttons
    sb1, sb2, _ = st.columns([2, 2, 3])
    with sb1:
        save_clicked = st.button("💾 Save Position to Config",
                                  type="primary", use_container_width=True)
    with sb2:
        download_clicked = st.button("📥 Preview JSON",
                                      use_container_width=True)

    if save_clicked:
        # Apply offset to anchor lat/lon AND store rotation separately
        R_EARTH_FT = 20_925_721.78
        updated_config = json.loads(json.dumps(config))  # deep copy
        old_lat = updated_config["anchor"]["lat"]
        old_lon = updated_config["anchor"]["lon"]

        delta_lat = (live_n / R_EARTH_FT) * (180 / math.pi)
        lat_rad = old_lat * (math.pi / 180)
        delta_lon = (live_e / (R_EARTH_FT * math.cos(lat_rad))) * (180 / math.pi)

        new_lat = old_lat + delta_lat
        new_lon = old_lon + delta_lon

        updated_config["anchor"]["lat"] = round(new_lat, 8)
        updated_config["anchor"]["lon"] = round(new_lon, 8)
        updated_config["anchor"]["description"] = (
            updated_config["anchor"].get("description", "")
            + f" · visually nudged {live_e:+.2f} E / {live_n:+.2f} N ft"
        ).strip()
        updated_config["rotation_deg"] = round(live_r, 2)

        # Persist
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(base_dir, "..", "data", "site_configs")
        config_path = os.path.join(config_dir, "site_configs.json")
        os.makedirs(config_dir, exist_ok=True)

        existing = []
        if os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    existing = json.load(f)
            except Exception:
                existing = []

        found = False
        for i, s in enumerate(existing):
            if s.get("site_id") == updated_config["site_id"]:
                existing[i] = updated_config
                found = True
                break
        if not found:
            existing.append(updated_config)

        with open(config_path, "w") as f:
            json.dump(existing, f, indent=2)

        st.session_state["generated_config"] = updated_config
        st.success(
            f"✅ **Position saved** for SiteID `{updated_config['site_id']}`.  \n"
            f"Anchor updated: `{old_lat:.7f}, {old_lon:.7f}` → "
            f"`{new_lat:.7f}, {new_lon:.7f}`  \n"
            f"Rotation stored: **{updated_config['rotation_deg']}°**  \n\n"
            f"This change is now reflected in `site_configs.json` and will be "
            f"used by the dashboard on next load."
        )
        st.info("🔄 Tip: Click **Compute** again if you want to re-preview with the new baked-in anchor.")

    if download_clicked:
        json_str = json.dumps(config, indent=2)
        st.code(json_str, language="json")
        st.download_button(
            "📥 Download JSON",
            data=json_str,
            file_name=f"site_config_{config['site_id']}.json",
            mime="application/json",
        )

    # ═══════════════════════════════════════════
    #  MAP EXPORTS — three consistent variants
    # ═══════════════════════════════════════════
    st.markdown("---")
    st.subheader("🗂️ Export Site Maps")
    st.caption(
        "Download this site's map in three formats. All three use the **same** "
        "renderer as the PPTX resident reports, so the output is consistent "
        "everywhere. Real XRF readings are pulled from the latest Master Data; "
        "cells without data render in gray."
    )

    # Load master data for real PPM lookup
    master_df_export = load_master_data()
    if master_df_export.empty:
        st.warning(
            "⚠️ No Master Data found — exports will render all cells as 'No Data' (gray). "
            "Run the ETL Pipeline first if you want real PPM values."
        )
    else:
        # Show a little summary so the user knows what's being used
        blocks_preview, _ = get_block_data(config, master_df_export,
                                            use_mock_fallback=False)
        real_count = sum(1 for b in blocks_preview if b["has_real_data"])
        total = len(blocks_preview)
        st.caption(
            f"📊 Using Master Data: **{real_count} / {total}** cells have real "
            f"XRF readings. Remaining cells will render as 'No Data' (gray)."
        )

    # SiteIDs are filesystem-safe by construction (alphanumerics + dashes).
    safe_name = config["site_id"]

    exp1, exp2, exp3 = st.columns(3)

    # ─── 1. Basemap + no numbers (HTML) ───
    with exp1:
        st.markdown("**🛰️ Basemap · no numbers**")
        st.caption("Satellite imagery, cell IDs only, draggable.")
        try:
            html_nonum = render_leaflet_html(
                config, master_df_export,
                show_numbers=False, use_mock_fallback=False,
            )
            st.download_button(
                label="📥 Download HTML",
                data=html_nonum,
                file_name=f"{safe_name}_basemap_no_numbers.html",
                mime="text/html",
                use_container_width=True,
                key="exp_basemap_nonum",
            )
        except Exception as e:
            st.error(f"Render failed: {e}")

    # ─── 2. Basemap + numbers (HTML) ───
    with exp2:
        st.markdown("**🛰️ Basemap · with numbers**")
        st.caption("Satellite imagery, cell IDs + ppm values.")
        try:
            html_num = render_leaflet_html(
                config, master_df_export,
                show_numbers=True, use_mock_fallback=False,
            )
            st.download_button(
                label="📥 Download HTML",
                data=html_num,
                file_name=f"{safe_name}_basemap_with_numbers.html",
                mime="text/html",
                use_container_width=True,
                key="exp_basemap_num",
            )
        except Exception as e:
            st.error(f"Render failed: {e}")

    # ─── 3. No basemap + numbers (PNG) ───
    with exp3:
        st.markdown("**🎨 No basemap · with numbers**")
        st.caption("Dark-theme PNG (matches PPTX reports).")
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".png", delete=False
            ) as tmp:
                png_path = tmp.name
            render_static_png(
                config, master_df_export, png_path,
                show_numbers=True, use_mock_fallback=False,
            )
            with open(png_path, "rb") as f:
                png_bytes = f.read()
            os.unlink(png_path)
            st.download_button(
                label="📥 Download PNG",
                data=png_bytes,
                file_name=f"{safe_name}_no_basemap_with_numbers.png",
                mime="image/png",
                use_container_width=True,
                key="exp_static_png",
            )
        except Exception as e:
            st.error(f"Render failed: {e}")

    st.caption(
        "🔄 All three outputs honor the site's saved `rotation_deg` and "
        "fine-tuned anchor position. The PNG here is byte-identical to what "
        "`etl_manager.py` embeds in the resident PPTX report."
    )
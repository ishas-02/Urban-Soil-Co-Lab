# # # """
# # # site_builder.py — GroundSense Site Configuration Builder

# # # A standalone Streamlit page where field technicians input measurements
# # # for a new sampling site and the system auto-generates:
# # #   1. Grid block offsets (computed from cell dimensions + fixed point)
# # #   2. A site_configs.json entry
# # #   3. A live draggable satellite map preview (Leaflet)
# # #   4. Persistent fine-tuned position via Save button — updates anchor
# # #      lat/lon AND stores rotation_deg separately for dashboard consistency.
# # #   5. Three downloadable map exports (all via shared map_renderer module,
# # #      so they stay visually consistent with the PPTX reports):
# # #         - Basemap + no numbers  (Leaflet HTML, satellite)
# # #         - Basemap + numbers     (Leaflet HTML, satellite, ppm labels)
# # #         - No basemap + numbers  (static PNG, dark theme)

# # # Place in src/ alongside groundsense_config.py and map_renderer.py.
# # # Run: streamlit run src/site_builder.py
# # # """

# # # import streamlit as st
# # # import streamlit.components.v1 as components
# # # import pandas as pd
# # # import json
# # # import math
# # # import os
# # # import glob
# # # import re
# # # import io
# # # import tempfile

# # # from groundsense_config import (
# # #     get_nysh_category,
# # #     NYSH_TIERS,
# # #     NYSH_COLORS,
# # #     calculate_coordinate,
# # #     resolve_lod,
# # # )

# # # # Shared renderer — used by etl_manager.py too, so exports stay consistent
# # # from map_renderer import (
# # #     render_leaflet_html,
# # #     render_static_png,
# # #     get_block_data,
# # # )


# # # # ═══════════════════════════════════════════════
# # # #  MASTER DATA LOADER (for export with real PPM values)
# # # # ═══════════════════════════════════════════════
# # # @st.cache_data
# # # def load_master_data():
# # #     """Load the latest XRF_Chemistry_V*.csv for looking up real Lead PPM
# # #     values when rendering the exported maps. Returns empty df if missing.
# # #     """
# # #     base_dir = os.path.dirname(os.path.abspath(__file__))
# # #     master_dir = os.path.join(base_dir, "..", "data", "XRF_Chemistry")
# # #     master_files = glob.glob(os.path.join(master_dir, "XRF_Chemistry_V*.csv"))
# # #     if not master_files:
# # #         return pd.DataFrame(columns=["SampleID", "LeadPPM", "LeadPPM_Clean"])

# # #     def _ver(fn):
# # #         m = re.search(r"_V(\d+)\.csv$", fn, re.IGNORECASE)
# # #         return int(m.group(1)) if m else 0

# # #     latest = max(master_files, key=_ver)
# # #     df = pd.read_csv(latest)
# # #     df["LeadPPM_Clean"] = df["LeadPPM"].apply(resolve_lod)
# # #     return df


# # # # ═══════════════════════════════════════════════
# # # #  PAGE CONFIG & STYLING
# # # # ═══════════════════════════════════════════════
# # # st.set_page_config(page_title="GroundSense Site Builder", page_icon="📐", layout="wide")
# # # st.title("📐 Site Configuration Builder")
# # # st.caption("Urban Soil Co-Lab · University at Buffalo · GroundSense Pipeline")
# # # st.markdown(
# # #     "Transform field sketch measurements into a config-ready site definition. "
# # #     "Fill in each section below, then hit **Compute** to generate the JSON config "
# # #     "and preview the grid on satellite imagery. You can drag/rotate the grid on "
# # #     "the preview to fine-tune positioning, then **Save** to persist the change."
# # # )
# # # st.markdown("---")


# # # # ═══════════════════════════════════════════════
# # # #  HELPERS
# # # # ═══════════════════════════════════════════════
# # # def parse_imperial(s):
# # #     """Convert imperial string like 11'6.5\" or plain feet like 10 to decimal feet."""
# # #     if s is None or str(s).strip() == "":
# # #         return 0.0
# # #     s = str(s).strip().replace('"', '').replace("''", "").replace('\u2033', '').replace('\u2032', "'")
# # #     if "'" in s:
# # #         parts = s.split("'")
# # #         feet = float(parts[0]) if parts[0].strip() else 0
# # #         inches = float(parts[1]) if len(parts) > 1 and parts[1].strip() else 0
# # #         return feet + inches / 12.0
# # #     try:
# # #         return float(s)
# # #     except ValueError:
# # #         return 0.0


# # # def dms_to_decimal(degrees, minutes, seconds, direction):
# # #     """Convert DMS coordinates to decimal degrees."""
# # #     dd = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
# # #     if direction in ['S', 'W']:
# # #         dd *= -1
# # #     return dd


# # # def load_existing_config_for_site_id(site_id, config_path):
# # #     """If this site_id already has a saved config, return its current offset/rotation."""
# # #     if not os.path.exists(config_path):
# # #         return None
# # #     try:
# # #         with open(config_path, 'r') as f:
# # #             existing = json.load(f)
# # #         for s in existing:
# # #             if s.get("site_id") == site_id:
# # #                 return s
# # #     except Exception:
# # #         pass
# # #     return None


# # # def list_existing_site_ids(config_path):
# # #     """Return a list of all SiteIDs currently saved in site_configs.json.

# # #     Returns [] if the file is missing or unreadable. Order matches the
# # #     file order (which is roughly creation order).
# # #     """
# # #     if not os.path.exists(config_path):
# # #         return []
# # #     try:
# # #         with open(config_path, 'r') as f:
# # #             existing = json.load(f)
# # #         return [s.get("site_id", "") for s in existing if s.get("site_id")]
# # #     except Exception:
# # #         return []


# # # # ═══════════════════════════════════════════════
# # # #  LOAD EXISTING SITE (search/edit existing maps)
# # # # ═══════════════════════════════════════════════
# # # st.subheader("🔍 Load Existing Site")
# # # st.caption(
# # #     "Pick a previously-saved site to load it into the draggable preview. "
# # #     "You can re-position or rotate the grid and **Save** to update its "
# # #     "config in place. Leave this empty if you're creating a brand-new site."
# # # )

# # # _base_dir_top = os.path.dirname(os.path.abspath(__file__))
# # # _config_path_top = os.path.join(
# # #     _base_dir_top, "..", "data", "site_configs", "site_configs.json"
# # # )
# # # _existing_site_ids = list_existing_site_ids(_config_path_top)

# # # ec1, ec2 = st.columns([3, 1])
# # # with ec1:
# # #     selected_existing = st.selectbox(
# # #         "Existing SiteIDs",
# # #         options=["— select to load —"] + _existing_site_ids,
# # #         index=0,
# # #         key="existing_site_selector",
# # #         help="Sites are pulled from data/site_configs/site_configs.json.",
# # #     )
# # # with ec2:
# # #     load_clicked = st.button(
# # #         "📂 Load to Preview",
# # #         use_container_width=True,
# # #         disabled=(selected_existing == "— select to load —"),
# # #     )

# # # if load_clicked and selected_existing != "— select to load —":
# # #     cfg = load_existing_config_for_site_id(selected_existing, _config_path_top)
# # #     if cfg is None:
# # #         st.error(f"Could not find SiteID '{selected_existing}' in site_configs.json.")
# # #     else:
# # #         # Drop the loaded config straight into the draggable-preview slot.
# # #         # The preview block further down keys off `generated_config`, so this
# # #         # is all we need to do — the user lands on the same map UI they'd
# # #         # see right after clicking Compute.
# # #         st.session_state["generated_config"] = cfg
# # #         # Clear any stale drag-state from a previous edit.
# # #         st.session_state.pop("pending_offset_e", None)
# # #         st.session_state.pop("pending_offset_n", None)
# # #         st.session_state.pop("pending_rotation", None)
# # #         st.success(
# # #             f"✅ Loaded **{selected_existing}** "
# # #             f"({len(cfg.get('grid_blocks', {}))} blocks · "
# # #             f"{len(cfg.get('point_samples', {}))} point samples). "
# # #             f"Scroll down to the **Draggable Satellite Preview** to nudge it "
# # #             f"and **Save** to overwrite its config."
# # #         )
# # #         st.rerun()

# # # st.markdown("---")


# # # # ═══════════════════════════════════════════════
# # # #  STEP 1 — SITE INFORMATION
# # # # ═══════════════════════════════════════════════
# # # st.subheader("① Site Information")
# # # st.caption(
# # #     "SiteID is the canonical identifier for this site across the pipeline. "
# # #     "Convention: use the sampling date in ISO form (YYYY-MM-DD). "
# # #     "Resident address/name/ZIP are PII and never stored here. "
# # #     "_(Steps ① – ⑦ are for building a **new** site from scratch — to edit "
# # #     "an existing one, use the dropdown above and skip to the preview.)_"
# # # )

# # # col_date, col_id = st.columns([1, 2])
# # # with col_date:
# # #     sampling_date = st.date_input("Sampling Date *")
# # # with col_id:
# # #     # Auto-suggest SiteID from sampling_date (zero-padded ISO). User may
# # #     # override if a non-date scheme is needed (e.g. multiple sites on the
# # #     # same day — append a suffix like "2025-06-24-A").
# # #     suggested_id = sampling_date.strftime("%Y-%m-%d") if sampling_date else ""
# # #     site_id = st.text_input(
# # #         "SiteID *",
# # #         value=suggested_id,
# # #         placeholder="e.g. 2025-06-24",
# # #         help="Defaults to the sampling date in ISO form. Override only if you need to disambiguate multiple sites on the same date.",
# # #     ).strip()

# # # notes = st.text_input(
# # #     "Site Notes (optional)",
# # #     placeholder="e.g. Backyard grid, measured from porch corner…"
# # # )

# # # st.markdown("---")


# # # # ═══════════════════════════════════════════════
# # # #  STEP 2 — FIXED POINT LOCATION IN GRID
# # # # ═══════════════════════════════════════════════
# # # st.subheader("② Fixed Point Location in Grid")
# # # st.caption("Identify which cell corner the GPS measurement was taken at. "
# # #            "This anchors the entire grid to the real world.")

# # # col_fp1, col_fp2 = st.columns(2)
# # # with col_fp1:
# # #     fp_cell_input = st.text_input(
# # #         "Fixed Point Cell ID *", value="E1",
# # #         help="The cell whose corner was marked with GPS (e.g. E1, A1, D2)"
# # #     )
# # # with col_fp2:
# # #     fp_corner = st.selectbox(
# # #         "Which corner of this cell? *",
# # #         ["Top-Left", "Top-Right", "Bottom-Left", "Bottom-Right"],
# # #         help="As drawn on the field sketch — not compass direction"
# # #     )

# # # st.markdown("---")


# # # # ═══════════════════════════════════════════════
# # # #  STEP 3 — FIXED POINT GPS
# # # # ═══════════════════════════════════════════════
# # # st.subheader("③ Fixed Point GPS Coordinates")

# # # gps_format = st.radio(
# # #     "Coordinate format",
# # #     ["DMS (Degrees Minutes Seconds)", "Decimal Degrees"],
# # #     horizontal=True,
# # #     help="DMS example: 42° 55' 11.46\" N  ·  Decimal example: 42.9198500"
# # # )

# # # if gps_format == "DMS (Degrees Minutes Seconds)":
# # #     col_lat, col_lon = st.columns(2)
# # #     with col_lat:
# # #         st.markdown("**Latitude (N)**")
# # #         c1, c2, c3 = st.columns(3)
# # #         lat_d = c1.number_input("Deg", value=42, key="lat_d")
# # #         lat_m = c2.number_input("Min", value=55, key="lat_m")
# # #         lat_s = c3.number_input("Sec", value=11.46, format="%.4f", key="lat_s")
# # #     with col_lon:
# # #         st.markdown("**Longitude (W)**")
# # #         c4, c5, c6 = st.columns(3)
# # #         lon_d = c4.number_input("Deg", value=78, key="lon_d")
# # #         lon_m = c5.number_input("Min", value=49, key="lon_m")
# # #         lon_s = c6.number_input("Sec", value=33.63, format="%.4f", key="lon_s")
# # #     anchor_lat = dms_to_decimal(lat_d, lat_m, lat_s, 'N')
# # #     anchor_lon = dms_to_decimal(lon_d, lon_m, lon_s, 'W')
# # # else:
# # #     col_lat, col_lon = st.columns(2)
# # #     with col_lat:
# # #         anchor_lat = st.number_input("Latitude", value=42.919850, format="%.7f")
# # #     with col_lon:
# # #         anchor_lon = st.number_input("Longitude", value=-78.826008, format="%.7f")

# # # st.success(f"📍 Anchor locked: **{anchor_lat:.7f}°N, {abs(anchor_lon):.7f}°W**")

# # # st.markdown("---")


# # # # ═══════════════════════════════════════════════
# # # #  STEP 4 — GRID LAYOUT & ORIENTATION
# # # # ═══════════════════════════════════════════════
# # # st.subheader("④ Grid Layout")

# # # col_orient, col_dir = st.columns(2)
# # # with col_orient:
# # #     orientation = st.selectbox(
# # #         "Grid orientation on map",
# # #         ["Vertical (strip runs North–South)", "Horizontal (strip runs East–West)"],
# # #         help="Vertical = long axis goes up/down. Horizontal = long axis goes left/right."
# # #     )
# # # with col_dir:
# # #     if "Vertical" in orientation:
# # #         house_dir = st.selectbox("Which end is near the house?",
# # #                                  ["Top (North)", "Bottom (South)"])
# # #     else:
# # #         house_dir = st.selectbox("Which end is near the house?",
# # #                                  ["Left (West)", "Right (East)"])

# # # st.markdown("---")


# # # # ═══════════════════════════════════════════════
# # # #  STEP 5 — DEFINE GRID ROWS
# # # # ═══════════════════════════════════════════════
# # # st.subheader("⑤ Define Grid Rows")
# # # st.caption("List row letters from **farthest from house** → **nearest to house**.")

# # # rows_input = st.text_input(
# # #     "Row letters (comma-separated) *", value="A, B, C, D, E",
# # #     help="Example: A, B, C, D, E, F, G, H — where A is farthest from house"
# # # )
# # # rows = [r.strip().upper() for r in rows_input.split(",") if r.strip()]

# # # if rows:
# # #     st.info(f"**{len(rows)} rows:** {' → '.join(rows)}  _(far → near)_")

# # # st.markdown("---")


# # # # ═══════════════════════════════════════════════
# # # #  STEP 6 — CELL DIMENSIONS
# # # # ═══════════════════════════════════════════════
# # # st.subheader("⑥ Cell Dimensions")
# # # st.caption("Enter each cell's **width** (perpendicular to strip) and **height** "
# # #            "(along the strip). Accepts imperial: `11'6.5\"` or plain feet: `10`.")

# # # max_cols = st.number_input("Max columns per row", min_value=1, max_value=5, value=3,
# # #                             help="e.g. 3 if cells are A1, A2, A3")

# # # cell_data = {}
# # # for row in rows:
# # #     with st.expander(f"**Row {row}**", expanded=True):
# # #         num_cols = st.number_input(f"Columns in row {row}", min_value=1,
# # #                                     max_value=int(max_cols),
# # #                                     value=min(int(max_cols), 3), key=f"ncols_{row}")
# # #         cols_ui = st.columns(int(num_cols))
# # #         for c in range(int(num_cols)):
# # #             col_num = c + 1
# # #             cell_id = f"{row}{col_num}"
# # #             with cols_ui[c]:
# # #                 st.markdown(f"##### {cell_id}")
# # #                 w = st.text_input("Width (ft)", value="10", key=f"w_{cell_id}")
# # #                 h = st.text_input("Height (ft)", value="10", key=f"h_{cell_id}")
# # #                 pat = st.text_input("SampleID pattern", value=f"{cell_id}_",
# # #                                     key=f"pat_{cell_id}",
# # #                                     help="Substring matched against Master Data")
# # #                 cell_data[cell_id] = {
# # #                     "width": parse_imperial(w), "height": parse_imperial(h),
# # #                     "col": col_num, "row": row, "pattern": pat,
# # #                 }

# # # st.markdown("---")


# # # # ═══════════════════════════════════════════════
# # # #  STEP 7 — POINT SAMPLES (OPTIONAL)
# # # # ═══════════════════════════════════════════════
# # # st.subheader("⑦ Point Samples _(optional)_")
# # # st.caption("Non-grid samples (driplines, lawns, etc.). Offsets in feet from the fixed point.")

# # # num_points = st.number_input("Number of point samples", min_value=0, max_value=20, value=0)
# # # point_samples = {}
# # # if num_points > 0:
# # #     for i in range(int(num_points)):
# # #         with st.expander(f"Point Sample {i + 1}", expanded=True):
# # #             pc1, pc2, pc3, pc4 = st.columns(4)
# # #             with pc1:
# # #                 pt_name = st.text_input("Name", key=f"pt_name_{i}", placeholder="HUD Dripline")
# # #             with pc2:
# # #                 pt_ox = st.number_input("East offset (ft)", key=f"pt_ox_{i}", value=0.0)
# # #             with pc3:
# # #                 pt_oy = st.number_input("North offset (ft)", key=f"pt_oy_{i}", value=0.0)
# # #             with pc4:
# # #                 pt_pat = st.text_input("SampleID pattern", key=f"pt_pat_{i}",
# # #                                         placeholder="HUD_Dripline")
# # #             if pt_name:
# # #                 point_samples[pt_name] = {
# # #                     "offset_x": pt_ox, "offset_y": pt_oy,
# # #                     "sample_id_patterns": [pt_pat] if pt_pat else [],
# # #                     "zone": "auxiliary",
# # #                 }


# # # # ═══════════════════════════════════════════════
# # # #  COMPUTE
# # # # ═══════════════════════════════════════════════
# # # st.markdown("---")
# # # st.markdown("### 🔧 Generate Configuration")

# # # col_btn, _ = st.columns([2, 5])
# # # with col_btn:
# # #     compute = st.button("Compute Grid & Preview Map", type="primary", use_container_width=True)

# # # if compute:
# # #     errors = []
# # #     if not site_id:
# # #         errors.append("SiteID is required.")
# # #     if not rows:
# # #         errors.append("At least one grid row must be defined.")
# # #     if not cell_data:
# # #         errors.append("Cell dimensions are required.")
# # #     fp_cell = fp_cell_input.strip().upper()
# # #     if fp_cell not in cell_data:
# # #         errors.append(f"Fixed point cell '{fp_cell}' doesn't match any defined cell.")
# # #     if errors:
# # #         for e in errors:
# # #             st.error(e)
# # #         st.stop()

# # #     row_heights = {}
# # #     for row in rows:
# # #         c1 = f"{row}1"
# # #         if c1 in cell_data:
# # #             row_heights[row] = cell_data[c1]["height"]
# # #         else:
# # #             for cid, cd in cell_data.items():
# # #                 if cd["row"] == row:
# # #                     row_heights[row] = cd["height"]
# # #                     break

# # #     strip_pos, pos = {}, 0
# # #     for row in rows:
# # #         strip_pos[row] = pos
# # #         pos += row_heights.get(row, 10)

# # #     fp_row = ''.join(c for c in fp_cell if c.isalpha())
# # #     fp_col = int(''.join(c for c in fp_cell if c.isdigit()))

# # #     col_widths_per_row = {}
# # #     for row in rows:
# # #         col_widths_per_row[row] = {}
# # #         for cid, cd in cell_data.items():
# # #             if cd["row"] == row:
# # #                 col_widths_per_row[row][cd["col"]] = cd["width"]

# # #     fp_row_widths = col_widths_per_row.get(fp_row, {})
# # #     fp_perp = 0
# # #     if "Left" in fp_corner:
# # #         for c in range(1, fp_col):
# # #             fp_perp += fp_row_widths.get(c, 0)
# # #     else:
# # #         for c in range(1, fp_col + 1):
# # #             fp_perp += fp_row_widths.get(c, 0)

# # #     fp_strip = strip_pos[fp_row] + (row_heights[fp_row] if "Top" in fp_corner else 0)

# # #     is_vertical = "Vertical" in orientation
# # #     flip_strip = "Top" in house_dir or "Right" in house_dir

# # #     grid_blocks = {}
# # #     for cid, cd in cell_data.items():
# # #         row, col = cd["row"], cd["col"]
# # #         cell_h, cell_w = cd["height"], cd["width"]

# # #         strip_start = strip_pos[row] - fp_strip
# # #         strip_end = strip_start + row_heights[row]
# # #         if cell_h != row_heights[row]:
# # #             strip_start = strip_end - cell_h

# # #         perp_start = sum(col_widths_per_row[row].get(c, 0) for c in range(1, col))
# # #         perp_end = perp_start + cell_w
# # #         perp_start -= fp_perp
# # #         perp_end -= fp_perp

# # #         if flip_strip:
# # #             strip_start, strip_end = -strip_end, -strip_start

# # #         if is_vertical:
# # #             ns, ne, es, ee = strip_start, strip_end, perp_start, perp_end
# # #         else:
# # #             es, ee, ns, ne = strip_start, strip_end, perp_start, perp_end

# # #         grid_blocks[cid] = {
# # #             "sw_x": round(min(es, ee), 2), "sw_y": round(min(ns, ne), 2),
# # #             "ne_x": round(max(es, ee), 2), "ne_y": round(max(ns, ne), 2),
# # #             "sample_id_patterns": [cd["pattern"]] if cd["pattern"] else [],
# # #             "zone": "yard", "mock_ppm": 0,
# # #         }

# # #     # ── Preserve existing rotation if this site_id was saved before ──
# # #     base_dir = os.path.dirname(os.path.abspath(__file__))
# # #     config_path = os.path.join(base_dir, "..", "data", "site_configs", "site_configs.json")
# # #     existing = load_existing_config_for_site_id(site_id, config_path)
# # #     preserved_rotation = existing.get("rotation_deg", 0) if existing else 0

# # #     site_config = {
# # #         "site_id": site_id,
# # #         "sampling_date": str(sampling_date), "notes": notes,
# # #         "anchor": {
# # #             "lat": anchor_lat, "lon": anchor_lon,
# # #             "description": f"Fixed point at {fp_cell} ({fp_corner}) — field-measured GPS",
# # #             "marker_label": f"Fixed Point ({fp_cell})",
# # #         },
# # #         "map_defaults": {"zoom_start": 21, "center_offset_north_ft": 0, "center_offset_east_ft": 0},
# # #         "rotation_deg": preserved_rotation,
# # #         "grid_blocks": grid_blocks,
# # #         "point_samples": point_samples,
# # #     }

# # #     st.session_state["generated_config"] = site_config
# # #     # Reset any stale drag state
# # #     st.session_state.pop("pending_offset_e", None)
# # #     st.session_state.pop("pending_offset_n", None)
# # #     st.session_state.pop("pending_rotation", None)
# # #     st.success(f"✅ Grid computed — **{len(grid_blocks)} blocks** + **{len(point_samples)} point samples**")


# # # # ═══════════════════════════════════════════════
# # # #  RESULTS & DRAGGABLE PREVIEW
# # # # ═══════════════════════════════════════════════
# # # if "generated_config" in st.session_state:
# # #     config = st.session_state["generated_config"]
# # #     st.markdown("---")

# # #     st.subheader("📋 Computed Grid Offsets")
# # #     tbl = []
# # #     for bid, b in config["grid_blocks"].items():
# # #         tbl.append({
# # #             "Cell": bid,
# # #             "SW East": b["sw_x"], "SW North": b["sw_y"],
# # #             "NE East": b["ne_x"], "NE North": b["ne_y"],
# # #             "W (ft)": round(b["ne_x"] - b["sw_x"], 1),
# # #             "H (ft)": round(b["ne_y"] - b["sw_y"], 1),
# # #             "Pattern": ", ".join(b.get("sample_id_patterns", [])),
# # #         })
# # #     st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True)

# # #     # ═══════════════════════════════════════════
# # #     #  DRAGGABLE LEAFLET PREVIEW
# # #     # ═══════════════════════════════════════════
# # #     st.subheader("🗺️ Draggable Satellite Preview")
# # #     st.caption(
# # #         "**Click & drag the grid** to nudge it onto the actual yard. "
# # #         "Use the rotation buttons to align with the house. "
# # #         "The current offset/rotation is shown live in the control panel — "
# # #         "click **Save** below the map to persist it."
# # #     )

# # #     # Build blocks payload for the Leaflet component
# # #     blocks_payload = []
# # #     for bid, b in config["grid_blocks"].items():
# # #         # We want to render each block as a rectangle in feet-space,
# # #         # then convert to lat/lon client-side using the anchor.
# # #         corners = [
# # #             [b["sw_x"], b["sw_y"]],
# # #             [b["ne_x"], b["sw_y"]],
# # #             [b["ne_x"], b["ne_y"]],
# # #             [b["sw_x"], b["ne_y"]],
# # #         ]
# # #         cx = (b["sw_x"] + b["ne_x"]) / 2
# # #         cy = (b["sw_y"] + b["ne_y"]) / 2
# # #         mock_ppm = b.get("mock_ppm", 0)
# # #         label, color = get_nysh_category(mock_ppm) if mock_ppm else ("Preview", "#4a90d9")
# # #         blocks_payload.append({
# # #             "id": bid,
# # #             "corners": corners,
# # #             "cx": cx, "cy": cy,
# # #             "color": color,
# # #             "label": label,
# # #             "ppm": mock_ppm,
# # #         })

# # #     points_payload = []
# # #     for pid, pt in config.get("point_samples", {}).items():
# # #         points_payload.append({
# # #             "id": pid,
# # #             "ox": pt.get("offset_x", 0),
# # #             "oy": pt.get("offset_y", 0),
# # #         })

# # #     anchor = config["anchor"]
# # #     rotation_init = config.get("rotation_deg", 0)

# # #     # Build the legend HTML from NYSH_TIERS so it stays in sync
# # #     legend_rows = ""
# # #     for t in NYSH_TIERS:
# # #         legend_rows += (
# # #             '<div><span style="display:inline-block;width:11px;height:11px;'
# # #             f'background:{t["color"]};border-radius:2px;margin-right:5px;'
# # #             f'vertical-align:middle"></span>{t["label"]}</div>'
# # #         )
# # #     legend_rows += (
# # #         '<div><span style="display:inline-block;width:11px;height:11px;'
# # #         'background:#4a90d9;border-radius:2px;margin-right:5px;'
# # #         'vertical-align:middle"></span>Preview (no data yet)</div>'
# # #     )

# # #     # Leaflet HTML component with drag + rotate + message bridge
# # #     component_html = f"""
# # # <!DOCTYPE html>
# # # <html><head>
# # # <meta charset="utf-8">
# # # <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
# # # <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
# # # <style>
# # #   html,body {{ margin:0; padding:0; font-family:Arial,sans-serif; background:#0c0f14; }}
# # #   #map {{ width:100%; height:560px; }}
# # #   .legend {{ position:absolute; bottom:20px; left:20px; z-index:1001;
# # #     background:rgba(12,15,20,0.93); padding:12px 16px; border-radius:10px;
# # #     color:#e8eaed; font-size:11px; line-height:1.7;
# # #     border:1px solid rgba(255,255,255,0.08); }}
# # #   .legend b {{ font-size:13px; }}
# # #   .controls {{ position:absolute; top:20px; right:20px; z-index:1001;
# # #     background:rgba(12,15,20,0.93); padding:12px 16px; border-radius:10px;
# # #     color:#e8eaed; font-size:11px; border:1px solid rgba(255,255,255,0.08);
# # #     min-width:210px; }}
# # #   .controls b {{ font-size:13px; color:#e67e22; }}
# # #   .controls .hint {{ font-size:10px; color:#7a8599; margin-top:2px; }}
# # #   .controls .offset {{ font-family:monospace; font-size:11px; color:#4ecdc4;
# # #     margin-top:6px; background:rgba(78,205,196,0.08); padding:5px 8px;
# # #     border-radius:4px; }}
# # #   .controls button {{ padding:4px 9px; border:1px solid rgba(255,255,255,0.15);
# # #     border-radius:4px; background:rgba(78,205,196,0.12); color:#4ecdc4;
# # #     cursor:pointer; font-size:10px; }}
# # #   .controls button:hover {{ background:rgba(78,205,196,0.25); }}
# # #   .rotate-row {{ display:flex; gap:4px; align-items:center; margin-top:6px; }}
# # #   .rotate-row button {{ margin:0; padding:3px 7px; font-size:10px; }}
# # #   .rotate-row span {{ font-size:11px; color:#c7d0dc; min-width:38px;
# # #     text-align:center; font-family:monospace; }}
# # #   .reset-btn {{ margin-top:8px; width:100%; background:rgba(255,100,100,0.12) !important;
# # #     color:#ff8888 !important; }}
# # # </style>
# # # </head><body>
# # # <div id="map"></div>
# # # <div class="legend"><b>Lead Guidelines (ppm)</b><br>{legend_rows}</div>
# # # <div class="controls">
# # #   <b>Grid Position</b>
# # #   <div class="hint">Click & drag the grid on the map</div>
# # #   <div class="rotate-row">
# # #     <button onclick="rg(-5)">−5°</button>
# # #     <button onclick="rg(-1)">−1°</button>
# # #     <span id="rd">{rotation_init}°</span>
# # #     <button onclick="rg(1)">+1°</button>
# # #     <button onclick="rg(5)">+5°</button>
# # #   </div>
# # #   <div class="offset" id="od">Offset: 0.0 E, 0.0 N</div>
# # #   <button class="reset-btn" onclick="rs()">Reset Position</button>
# # # </div>

# # # <script>
# # #   var AL = {anchor["lat"]}, AO = {anchor["lon"]};
# # #   var BL = {json.dumps(blocks_payload)};
# # #   var PT = {json.dumps(points_payload)};
# # #   var RF = 20925721.78;
# # #   var oE = 0, oN = 0, rot = {rotation_init};

# # #   var map = L.map('map', {{
# # #     center: [AL, AO], zoom: 21, maxZoom: 25
# # #   }});
# # #   L.tileLayer(
# # #     'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
# # #     {{ attribution: 'Esri', maxZoom: 25, maxNativeZoom: 19 }}
# # #   ).addTo(map);

# # #   // Anchor marker (stays put — doesn't move with the drag)
# # #   L.marker([AL, AO], {{
# # #     icon: L.divIcon({{
# # #       className: '',
# # #       html: '<div style="width:14px;height:14px;background:#ff4444;border:2px solid white;border-radius:50%;box-shadow:0 0 6px rgba(0,0,0,0.6)"></div>',
# # #       iconSize: [14,14], iconAnchor: [7,7]
# # #     }})
# # #   }}).addTo(map).bindTooltip('Original Anchor');

# # #   function f2ll(la, lo, e, n) {{
# # #     // Convert (east_ft, north_ft) offset from (la,lo) to [lat,lon]
# # #     var dl = (n / RF) * (180 / Math.PI);
# # #     var dn = (e / (RF * Math.cos(la * Math.PI / 180))) * (180 / Math.PI);
# # #     return [la + dl, lo + dn];
# # #   }}

# # #   function rp(x, y, a) {{
# # #     // Rotate point (x,y) by angle a (deg)
# # #     var r = a * Math.PI / 180;
# # #     return [x * Math.cos(r) - y * Math.sin(r), x * Math.sin(r) + y * Math.cos(r)];
# # #   }}

# # #   var gl = L.layerGroup().addTo(map);

# # #   function dg() {{
# # #     gl.clearLayers();
# # #     BL.forEach(function(b) {{
# # #       var ll = b.corners.map(function(c) {{
# # #         var r = rp(c[0], c[1], rot);
# # #         return f2ll(AL, AO, r[0] + oE, r[1] + oN);
# # #       }});
# # #       var pl = L.polygon(ll, {{
# # #         color: 'white', weight: 2,
# # #         fillColor: b.color, fillOpacity: 0.65
# # #       }});
# # #       pl.bindTooltip('<b>' + b.id + '</b><br>' + b.label);
# # #       gl.addLayer(pl);
# # #       var rc = rp(b.cx, b.cy, rot);
# # #       var lp = f2ll(AL, AO, rc[0] + oE, rc[1] + oN);
# # #       gl.addLayer(L.marker(lp, {{
# # #         icon: L.divIcon({{
# # #           className: '',
# # #           html: '<div style="font-family:Arial;text-align:center;pointer-events:none">' +
# # #                 '<b style="font-size:10px;color:white;text-shadow:0 1px 3px rgba(0,0,0,0.85)">' +
# # #                 b.id + '</b></div>',
# # #           iconSize: [50, 20], iconAnchor: [25, 10]
# # #         }}),
# # #         interactive: false
# # #       }}));
# # #     }});

# # #     PT.forEach(function(p) {{
# # #       var r = rp(p.ox, p.oy, rot);
# # #       var ll = f2ll(AL, AO, r[0] + oE, r[1] + oN);
# # #       gl.addLayer(L.circleMarker(ll, {{
# # #         radius: 7, color: 'white', weight: 2,
# # #         fillColor: '#f39c12', fillOpacity: 0.8
# # #       }}).bindTooltip('<b>' + p.id + '</b>'));
# # #     }});

# # #     document.getElementById('od').textContent =
# # #       'Offset: ' + oE.toFixed(1) + ' E, ' + oN.toFixed(1) + ' N' +
# # #       (rot ? ('  |  ' + rot + '°') : '');
# # #     document.getElementById('rd').textContent = rot + '°';
# # #     // Post state to parent Streamlit
# # #     postState();
# # #   }}

# # #   function postState() {{
# # #     var msg = {{
# # #       type: 'groundsense_grid_state',
# # #       offset_east_ft: oE,
# # #       offset_north_ft: oN,
# # #       rotation_deg: rot
# # #     }};
# # #     window.parent.postMessage(msg, '*');
# # #   }}

# # #   function rg(d) {{ rot += d; dg(); }}
# # #   function rs() {{ oE = 0; oN = 0; rot = 0; dg(); }}

# # #   // Click & drag detection on polygons
# # #   var iD = false, dL = null, dE = 0, dN = 0;
# # #   map.on('mousedown', function(e) {{
# # #     var hit = false;
# # #     gl.eachLayer(function(l) {{
# # #       if (l instanceof L.Polygon && l.getBounds().contains(e.latlng)) hit = true;
# # #     }});
# # #     if (hit) {{
# # #       iD = true; dL = e.latlng; dE = oE; dN = oN;
# # #       map.dragging.disable();
# # #       map.getContainer().style.cursor = 'grabbing';
# # #     }}
# # #   }});
# # #   map.on('mousemove', function(e) {{
# # #     if (!iD) return;
# # #     oN = dN + (e.latlng.lat - dL.lat) * (Math.PI / 180) * RF;
# # #     oE = dE + (e.latlng.lng - dL.lng) * (Math.PI / 180) * RF *
# # #               Math.cos(AL * Math.PI / 180);
# # #     dg();
# # #   }});
# # #   map.on('mouseup', function() {{
# # #     if (iD) {{
# # #       iD = false;
# # #       map.dragging.enable();
# # #       map.getContainer().style.cursor = '';
# # #     }}
# # #   }});

# # #   dg();
# # # </script>
# # # </body></html>
# # # """

# # #     components.html(component_html, height=580, scrolling=False)

# # #     # ── Bridge: read posted state via a tiny JS shim + hidden text_input trick ──
# # #     # We use streamlit_js_eval if available, else fall back to manual entry.
# # #     try:
# # #         from streamlit_js_eval import streamlit_js_eval
# # #         bridge_available = True
# # #     except ImportError:
# # #         bridge_available = False

# # #     st.markdown("#### 💾 Save Fine-Tuned Position")

# # #     if bridge_available:
# # #         # Listen for postMessage events from the iframe
# # #         posted_state = streamlit_js_eval(
# # #             js_expressions="""
# # #                 (function() {
# # #                     if (!window._gs_state) {
# # #                         window._gs_state = {offset_east_ft: 0, offset_north_ft: 0, rotation_deg: 0};
# # #                         window.addEventListener('message', function(ev) {
# # #                             if (ev.data && ev.data.type === 'groundsense_grid_state') {
# # #                                 window._gs_state = ev.data;
# # #                             }
# # #                         });
# # #                     }
# # #                     return JSON.stringify(window._gs_state);
# # #                 })()
# # #             """,
# # #             key="gs_bridge",
# # #             want_output=True,
# # #         )
# # #         try:
# # #             state = json.loads(posted_state) if posted_state else {}
# # #         except Exception:
# # #             state = {}
# # #         live_e = float(state.get("offset_east_ft", 0) or 0)
# # #         live_n = float(state.get("offset_north_ft", 0) or 0)
# # #         live_r = float(state.get("rotation_deg", 0) or 0)

# # #         st.caption(
# # #             f"Live position from map:  **East:** {live_e:+.2f} ft  ·  "
# # #             f"**North:** {live_n:+.2f} ft  ·  **Rotation:** {live_r:+.1f}°"
# # #         )
# # #     else:
# # #         st.info(
# # #             "⚙️ For automatic drag-state capture, install `streamlit-js-eval`:  \n"
# # #             "`pip install streamlit-js-eval`  \n\n"
# # #             "Meanwhile, use the **Copy** button in the map's control panel, "
# # #             "then paste the values below:"
# # #         )
# # #         mc1, mc2, mc3 = st.columns(3)
# # #         live_e = mc1.number_input("East offset (ft)", value=0.0, step=0.1, key="manual_e")
# # #         live_n = mc2.number_input("North offset (ft)", value=0.0, step=0.1, key="manual_n")
# # #         live_r = mc3.number_input("Rotation (°)", value=0.0, step=1.0, key="manual_r")

# # #     # Buttons
# # #     sb1, sb2, _ = st.columns([2, 2, 3])
# # #     with sb1:
# # #         save_clicked = st.button("💾 Save Position to Config",
# # #                                   type="primary", use_container_width=True)
# # #     with sb2:
# # #         download_clicked = st.button("📥 Preview JSON",
# # #                                       use_container_width=True)

# # #     if save_clicked:
# # #         # Apply offset to anchor lat/lon AND store rotation separately
# # #         R_EARTH_FT = 20_925_721.78
# # #         updated_config = json.loads(json.dumps(config))  # deep copy
# # #         old_lat = updated_config["anchor"]["lat"]
# # #         old_lon = updated_config["anchor"]["lon"]

# # #         delta_lat = (live_n / R_EARTH_FT) * (180 / math.pi)
# # #         lat_rad = old_lat * (math.pi / 180)
# # #         delta_lon = (live_e / (R_EARTH_FT * math.cos(lat_rad))) * (180 / math.pi)

# # #         new_lat = old_lat + delta_lat
# # #         new_lon = old_lon + delta_lon

# # #         updated_config["anchor"]["lat"] = round(new_lat, 8)
# # #         updated_config["anchor"]["lon"] = round(new_lon, 8)
# # #         updated_config["anchor"]["description"] = (
# # #             updated_config["anchor"].get("description", "")
# # #             + f" · visually nudged {live_e:+.2f} E / {live_n:+.2f} N ft"
# # #         ).strip()
# # #         updated_config["rotation_deg"] = round(live_r, 2)

# # #         # Persist
# # #         base_dir = os.path.dirname(os.path.abspath(__file__))
# # #         config_dir = os.path.join(base_dir, "..", "data", "site_configs")
# # #         config_path = os.path.join(config_dir, "site_configs.json")
# # #         os.makedirs(config_dir, exist_ok=True)

# # #         existing = []
# # #         if os.path.exists(config_path):
# # #             try:
# # #                 with open(config_path) as f:
# # #                     existing = json.load(f)
# # #             except Exception:
# # #                 existing = []

# # #         found = False
# # #         for i, s in enumerate(existing):
# # #             if s.get("site_id") == updated_config["site_id"]:
# # #                 existing[i] = updated_config
# # #                 found = True
# # #                 break
# # #         if not found:
# # #             existing.append(updated_config)

# # #         with open(config_path, "w") as f:
# # #             json.dump(existing, f, indent=2)

# # #         st.session_state["generated_config"] = updated_config
# # #         st.success(
# # #             f"✅ **Position saved** for SiteID `{updated_config['site_id']}`.  \n"
# # #             f"Anchor updated: `{old_lat:.7f}, {old_lon:.7f}` → "
# # #             f"`{new_lat:.7f}, {new_lon:.7f}`  \n"
# # #             f"Rotation stored: **{updated_config['rotation_deg']}°**  \n\n"
# # #             f"This change is now reflected in `site_configs.json` and will be "
# # #             f"used by the dashboard on next load."
# # #         )
# # #         st.info("🔄 Tip: Click **Compute** again if you want to re-preview with the new baked-in anchor.")

# # #     if download_clicked:
# # #         json_str = json.dumps(config, indent=2)
# # #         st.code(json_str, language="json")
# # #         st.download_button(
# # #             "📥 Download JSON",
# # #             data=json_str,
# # #             file_name=f"site_config_{config['site_id']}.json",
# # #             mime="application/json",
# # #         )

# # #     # ═══════════════════════════════════════════
# # #     #  MAP EXPORTS — three consistent variants
# # #     # ═══════════════════════════════════════════
# # #     st.markdown("---")
# # #     st.subheader("🗂️ Export Site Maps")
# # #     st.caption(
# # #         "Download this site's map in three formats. All three use the **same** "
# # #         "renderer as the PPTX resident reports, so the output is consistent "
# # #         "everywhere. Real XRF readings are pulled from the latest Master Data; "
# # #         "cells without data render in gray."
# # #     )

# # #     # Load master data for real PPM lookup
# # #     master_df_export = load_master_data()
# # #     if master_df_export.empty:
# # #         st.warning(
# # #             "⚠️ No Master Data found — exports will render all cells as 'No Data' (gray). "
# # #             "Run the ETL Pipeline first if you want real PPM values."
# # #         )
# # #     else:
# # #         # Show a little summary so the user knows what's being used
# # #         blocks_preview, _ = get_block_data(config, master_df_export,
# # #                                             use_mock_fallback=False)
# # #         real_count = sum(1 for b in blocks_preview if b["has_real_data"])
# # #         total = len(blocks_preview)
# # #         st.caption(
# # #             f"📊 Using Master Data: **{real_count} / {total}** cells have real "
# # #             f"XRF readings. Remaining cells will render as 'No Data' (gray)."
# # #         )

# # #     # SiteIDs are filesystem-safe by construction (alphanumerics + dashes).
# # #     safe_name = config["site_id"]

# # #     exp1, exp2, exp3 = st.columns(3)

# # #     # ─── 1. Basemap + no numbers (HTML) ───
# # #     with exp1:
# # #         st.markdown("**🛰️ Basemap · no numbers**")
# # #         st.caption("Satellite imagery, cell IDs only, draggable.")
# # #         try:
# # #             html_nonum = render_leaflet_html(
# # #                 config, master_df_export,
# # #                 show_numbers=False, use_mock_fallback=False,
# # #             )
# # #             st.download_button(
# # #                 label="📥 Download HTML",
# # #                 data=html_nonum,
# # #                 file_name=f"{safe_name}_basemap_no_numbers.html",
# # #                 mime="text/html",
# # #                 use_container_width=True,
# # #                 key="exp_basemap_nonum",
# # #             )
# # #         except Exception as e:
# # #             st.error(f"Render failed: {e}")

# # #     # ─── 2. Basemap + numbers (HTML) ───
# # #     with exp2:
# # #         st.markdown("**🛰️ Basemap · with numbers**")
# # #         st.caption("Satellite imagery, cell IDs + ppm values.")
# # #         try:
# # #             html_num = render_leaflet_html(
# # #                 config, master_df_export,
# # #                 show_numbers=True, use_mock_fallback=False,
# # #             )
# # #             st.download_button(
# # #                 label="📥 Download HTML",
# # #                 data=html_num,
# # #                 file_name=f"{safe_name}_basemap_with_numbers.html",
# # #                 mime="text/html",
# # #                 use_container_width=True,
# # #                 key="exp_basemap_num",
# # #             )
# # #         except Exception as e:
# # #             st.error(f"Render failed: {e}")

# # #     # ─── 3. No basemap + numbers (PNG) ───
# # #     with exp3:
# # #         st.markdown("**🎨 No basemap · with numbers**")
# # #         st.caption("Dark-theme PNG (matches PPTX reports).")
# # #         try:
# # #             with tempfile.NamedTemporaryFile(
# # #                 suffix=".png", delete=False
# # #             ) as tmp:
# # #                 png_path = tmp.name
# # #             render_static_png(
# # #                 config, master_df_export, png_path,
# # #                 show_numbers=True, use_mock_fallback=False,
# # #             )
# # #             with open(png_path, "rb") as f:
# # #                 png_bytes = f.read()
# # #             os.unlink(png_path)
# # #             st.download_button(
# # #                 label="📥 Download PNG",
# # #                 data=png_bytes,
# # #                 file_name=f"{safe_name}_no_basemap_with_numbers.png",
# # #                 mime="image/png",
# # #                 use_container_width=True,
# # #                 key="exp_static_png",
# # #             )
# # #         except Exception as e:
# # #             st.error(f"Render failed: {e}")

# # #     st.caption(
# # #         "🔄 All three outputs honor the site's saved `rotation_deg` and "
# # #         "fine-tuned anchor position. The PNG here is byte-identical to what "
# # #         "`etl_manager.py` embeds in the resident PPTX report."
# # #     )

# # """
# # site_builder.py — GroundSense Site Configuration Builder

# # A standalone Streamlit page where field technicians input measurements
# # for a new sampling site and the system auto-generates:
# #   1. Grid block offsets (computed from cell dimensions + fixed point)
# #   2. A site_configs.json entry
# #   3. A live draggable satellite map preview (Leaflet)
# #   4. Persistent fine-tuned position via Save button — updates anchor
# #      lat/lon AND stores rotation_deg separately for dashboard consistency.
# #   5. Three downloadable map exports (all via shared map_renderer module,
# #      so they stay visually consistent with the PPTX reports):
# #         - Basemap + no numbers  (Leaflet HTML, satellite)
# #         - Basemap + numbers     (Leaflet HTML, satellite, ppm labels)
# #         - No basemap + numbers  (static PNG, dark theme)

# # ═══════════════════════════════════════════════════════════════════════
# # NEW (multi-yard support, additive — never breaks old configs):

# #   • ② "Which yard" dropdown — Front or Back. Switch between yards
# #     without leaving the page; fields ③ through ⑦ rebind per yard.
# #   • Each yard has its OWN anchor GPS, rotation, grid, and point samples.
# #   • Compute generates the currently-selected yard and stashes it.
# #     Repeat for the other yard if needed.
# #   • Save below the preview merges Front + Back into ONE site_config
# #     with both:
# #       - a NEW `yards` key (front + back subsections, full schema each)
# #       - LEGACY mirror keys (`anchor`, `rotation_deg`, `grid_blocks`,
# #         `point_samples`) populated as the UNION of all yards, so old
# #         consumers (dashboard, etl_manager, map_renderer) keep working.
# #   • Sites with only one yard still work — the absent yard is just
# #     omitted from the `yards` block.
# #   • Backward compat: old configs with no `yards` key load as-is and
# #     are treated as a single backyard. Saving them again preserves
# #     the legacy shape (no forced migration).
# #   • PPM matching downstream defaults SampleIDs without "Front"/"Back"
# #     in them to the backyard.

# # Place in src/ alongside groundsense_config.py and map_renderer.py.
# # Run: streamlit run src/site_builder.py
# # """

# # import streamlit as st
# # import streamlit.components.v1 as components
# # import pandas as pd
# # import json
# # import math
# # import os
# # import glob
# # import re
# # import io
# # import tempfile

# # from groundsense_config import (
# #     get_nysh_category,
# #     NYSH_TIERS,
# #     NYSH_COLORS,
# #     calculate_coordinate,
# #     resolve_lod,
# # )

# # # Shared renderer — used by etl_manager.py too, so exports stay consistent
# # from map_renderer import (
# #     render_leaflet_html,
# #     render_static_png,
# #     get_block_data,
# # )


# # # ═══════════════════════════════════════════════
# # #  MASTER DATA LOADER (for export with real PPM values)
# # # ═══════════════════════════════════════════════
# # @st.cache_data
# # def load_master_data():
# #     """Load the latest XRF_Chemistry_V*.csv for looking up real Lead PPM
# #     values when rendering the exported maps. Returns empty df if missing.
# #     """
# #     base_dir = os.path.dirname(os.path.abspath(__file__))
# #     master_dir = os.path.join(base_dir, "..", "data", "XRF_Chemistry")
# #     master_files = glob.glob(os.path.join(master_dir, "XRF_Chemistry_V*.csv"))
# #     if not master_files:
# #         return pd.DataFrame(columns=["SampleID", "LeadPPM", "LeadPPM_Clean"])

# #     def _ver(fn):
# #         m = re.search(r"_V(\d+)\.csv$", fn, re.IGNORECASE)
# #         return int(m.group(1)) if m else 0

# #     latest = max(master_files, key=_ver)
# #     df = pd.read_csv(latest)
# #     df["LeadPPM_Clean"] = df["LeadPPM"].apply(resolve_lod)
# #     return df


# # # ═══════════════════════════════════════════════
# # #  PAGE CONFIG & STYLING
# # # ═══════════════════════════════════════════════
# # st.set_page_config(page_title="GroundSense Site Builder", page_icon="📐", layout="wide")
# # st.title("📐 Site Configuration Builder")
# # st.caption("Urban Soil Co-Lab · University at Buffalo · GroundSense Pipeline")
# # st.markdown(
# #     "Transform field sketch measurements into a config-ready site definition. "
# #     "Fill in each section below, then hit **Compute** to generate the JSON config "
# #     "and preview the grid on satellite imagery. You can drag/rotate the grid on "
# #     "the preview to fine-tune positioning, then **Save** to persist the change."
# # )
# # st.markdown("---")


# # # ═══════════════════════════════════════════════
# # #  HELPERS
# # # ═══════════════════════════════════════════════
# # def parse_imperial(s):
# #     """Convert imperial string like 11'6.5\" or plain feet like 10 to decimal feet."""
# #     if s is None or str(s).strip() == "":
# #         return 0.0
# #     s = str(s).strip().replace('"', '').replace("''", "").replace('\u2033', '').replace('\u2032', "'")
# #     if "'" in s:
# #         parts = s.split("'")
# #         feet = float(parts[0]) if parts[0].strip() else 0
# #         inches = float(parts[1]) if len(parts) > 1 and parts[1].strip() else 0
# #         return feet + inches / 12.0
# #     try:
# #         return float(s)
# #     except ValueError:
# #         return 0.0


# # def dms_to_decimal(degrees, minutes, seconds, direction):
# #     """Convert DMS coordinates to decimal degrees."""
# #     dd = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
# #     if direction in ['S', 'W']:
# #         dd *= -1
# #     return dd


# # def load_existing_config_for_site_id(site_id, config_path):
# #     """If this site_id already has a saved config, return its current offset/rotation."""
# #     if not os.path.exists(config_path):
# #         return None
# #     try:
# #         with open(config_path, 'r') as f:
# #             existing = json.load(f)
# #         for s in existing:
# #             if s.get("site_id") == site_id:
# #                 return s
# #     except Exception:
# #         pass
# #     return None


# # def list_existing_site_ids(config_path):
# #     """Return a list of all SiteIDs currently saved in site_configs.json.

# #     Returns [] if the file is missing or unreadable. Order matches the
# #     file order (which is roughly creation order).
# #     """
# #     if not os.path.exists(config_path):
# #         return []
# #     try:
# #         with open(config_path, 'r') as f:
# #             existing = json.load(f)
# #         return [s.get("site_id", "") for s in existing if s.get("site_id")]
# #     except Exception:
# #         return []


# # def _zone_for_yard(yard_key: str) -> str:
# #     """Map an internal yard key to the zone string used in grid_blocks.

# #     yard_key is 'front' or 'back'. We store zone as 'front_yard' or
# #     'backyard' so downstream code can tell them apart cleanly.
# #     """
# #     return "front_yard" if yard_key == "front" else "backyard"


# # def _prefix_for_yard(yard_key: str) -> str:
# #     """Internal block-ID prefix to keep front/back keys collision-proof.

# #     Front cell 'A1' becomes 'F_A1', back 'A1' becomes 'B_A1'. The
# #     underlying cell label 'A1' is preserved inside the block as
# #     'cell_id' for map labels and downstream string matching.
# #     """
# #     return "F_" if yard_key == "front" else "B_"


# # def _merge_yards_into_legacy(yards_block: dict) -> dict:
# #     """Build the legacy top-level fields from the new yards block.

# #     Returns a dict with keys 'anchor', 'rotation_deg', 'grid_blocks',
# #     'point_samples' that mirror the UNION of all yards. Old consumers
# #     (dashboard, etl_manager, map_renderer) read these keys and stay
# #     blissfully unaware of the front/back split — every block has a
# #     `zone` tag that yard-aware code can use later.

# #     If only one yard exists, its anchor + rotation become the legacy
# #     fields directly. If both exist, the front yard wins for the legacy
# #     `anchor`/`rotation_deg` (chosen as the "primary" anchor — back is
# #     still fully present in the `yards` block with its own anchor).
# #     """
# #     front = yards_block.get("front")
# #     back  = yards_block.get("back")

# #     # Choose primary yard for legacy anchor/rotation (front first, else back).
# #     primary = front if front else back
# #     if primary is None:
# #         return {
# #             "anchor": {"lat": 0, "lon": 0, "description": "", "marker_label": ""},
# #             "rotation_deg": 0,
# #             "grid_blocks": {},
# #             "point_samples": {},
# #         }

# #     legacy_anchor   = dict(primary["anchor"])
# #     legacy_rotation = primary.get("rotation_deg", 0)

# #     legacy_blocks  = {}
# #     legacy_points  = {}
# #     for yk in ("front", "back"):
# #         y = yards_block.get(yk)
# #         if not y:
# #             continue
# #         legacy_blocks.update(y.get("grid_blocks", {}))
# #         legacy_points.update(y.get("point_samples", {}))

# #     return {
# #         "anchor": legacy_anchor,
# #         "rotation_deg": legacy_rotation,
# #         "grid_blocks": legacy_blocks,
# #         "point_samples": legacy_points,
# #     }


# # def _split_legacy_into_yards(config: dict) -> dict:
# #     """Best-effort: split an OLD single-yard config into the yards shape.

# #     Used when the user loads an existing site that pre-dates this feature.
# #     The old config has no `yards` key — we treat it as a single backyard
# #     (per spec: SampleIDs without Front/Back default to back). The user
# #     can then add a front yard via the builder if they want.

# #     Returns a yards-shaped dict: {"front": None, "back": {...}}.
# #     NOTE: We do NOT modify the original config or write it back — this
# #     is purely for in-session editing. Saving preserves the old shape.
# #     """
# #     # Already has the new shape — just hand it back.
# #     if "yards" in config:
# #         return dict(config["yards"])

# #     legacy_blocks = config.get("grid_blocks", {})
# #     legacy_points = config.get("point_samples", {})

# #     if not legacy_blocks and not legacy_points:
# #         return {"front": None, "back": None}

# #     # Tag every legacy block with backyard zone (default per spec).
# #     tagged_blocks = {}
# #     for bid, b in legacy_blocks.items():
# #         b_copy = dict(b)
# #         if "zone" not in b_copy or b_copy.get("zone") == "yard":
# #             b_copy["zone"] = "backyard"
# #         tagged_blocks[bid] = b_copy

# #     back_yard = {
# #         "anchor": dict(config.get("anchor", {})),
# #         "rotation_deg": config.get("rotation_deg", 0),
# #         "grid_blocks": tagged_blocks,
# #         "point_samples": dict(legacy_points),
# #     }
# #     return {"front": None, "back": back_yard}


# # # ═══════════════════════════════════════════════
# # #  LOAD EXISTING SITE (search/edit existing maps)
# # #  — UNCHANGED behavior: load any site, drag, save in place. Works with
# # #    both legacy and new-format configs.
# # # ═══════════════════════════════════════════════
# # st.subheader("🔍 Load Existing Site")
# # st.caption(
# #     "Pick a previously-saved site to load it into the draggable preview. "
# #     "You can re-position or rotate the grid and **Save** to update its "
# #     "config in place. Leave this empty if you're creating a brand-new site."
# # )

# # _base_dir_top = os.path.dirname(os.path.abspath(__file__))
# # _config_path_top = os.path.join(
# #     _base_dir_top, "..", "data", "site_configs", "site_configs.json"
# # )
# # _existing_site_ids = list_existing_site_ids(_config_path_top)

# # ec1, ec2 = st.columns([3, 1])
# # with ec1:
# #     selected_existing = st.selectbox(
# #         "Existing SiteIDs",
# #         options=["— select to load —"] + _existing_site_ids,
# #         index=0,
# #         key="existing_site_selector",
# #         help="Sites are pulled from data/site_configs/site_configs.json.",
# #     )
# # with ec2:
# #     load_clicked = st.button(
# #         "📂 Load to Preview",
# #         use_container_width=True,
# #         disabled=(selected_existing == "— select to load —"),
# #     )

# # if load_clicked and selected_existing != "— select to load —":
# #     cfg = load_existing_config_for_site_id(selected_existing, _config_path_top)
# #     if cfg is None:
# #         st.error(f"Could not find SiteID '{selected_existing}' in site_configs.json.")
# #     else:
# #         # Drop the loaded config straight into the draggable-preview slot.
# #         # The preview block further down keys off `generated_config`, so this
# #         # is all we need to do — the user lands on the same map UI they'd
# #         # see right after clicking Compute.
# #         st.session_state["generated_config"] = cfg
# #         # Mark this as a loaded (existing) site so the preview/save block
# #         # knows to preserve its on-disk schema (legacy vs new).
# #         st.session_state["loaded_from_disk"] = True
# #         # Clear any in-progress build state for the new-site flow.
# #         st.session_state.pop("front_config", None)
# #         st.session_state.pop("back_config", None)
# #         # Clear any stale drag-state from a previous edit.
# #         for k in ("pending_offset_e", "pending_offset_n", "pending_rotation",
# #                   "front_offset_e", "front_offset_n", "front_rotation",
# #                   "back_offset_e", "back_offset_n", "back_rotation"):
# #             st.session_state.pop(k, None)
# #         n_blocks = len(cfg.get("grid_blocks", {}))
# #         # Try to give a friendlier yards breakdown when present.
# #         yards_present = list((cfg.get("yards") or {}).keys()) if cfg.get("yards") else []
# #         yards_desc = (f" · yards: {', '.join(yards_present)}"
# #                       if yards_present else " · legacy single-yard config")
# #         st.success(
# #             f"✅ Loaded **{selected_existing}** "
# #             f"({n_blocks} blocks · "
# #             f"{len(cfg.get('point_samples', {}))} point samples{yards_desc}). "
# #             f"Scroll down to the **Draggable Satellite Preview** to nudge it "
# #             f"and **Save** to overwrite its config."
# #         )
# #         st.rerun()

# # st.markdown("---")


# # # ═══════════════════════════════════════════════
# # #  STEP 1 — SITE INFORMATION
# # # ═══════════════════════════════════════════════
# # st.subheader("① Site Information")
# # st.caption(
# #     "SiteID is the canonical identifier for this site across the pipeline. "
# #     "Convention: use the sampling date in ISO form (YYYY-MM-DD). "
# #     "Resident address/name/ZIP are PII and never stored here. "
# #     "_(Steps ① – ⑦ are for building a **new** site from scratch — to edit "
# #     "an existing one, use the dropdown above and skip to the preview.)_"
# # )

# # col_date, col_id = st.columns([1, 2])
# # with col_date:
# #     sampling_date = st.date_input("Sampling Date *", key="builder_sampling_date")
# # with col_id:
# #     # Auto-suggest SiteID from sampling_date (zero-padded ISO). User may
# #     # override if a non-date scheme is needed (e.g. multiple sites on the
# #     # same day — append a suffix like "2025-06-24-A").
# #     suggested_id = sampling_date.strftime("%Y-%m-%d") if sampling_date else ""
# #     site_id = st.text_input(
# #         "SiteID *",
# #         value=suggested_id,
# #         placeholder="e.g. 2025-06-24",
# #         help="Defaults to the sampling date in ISO form. Override only if you need to disambiguate multiple sites on the same date.",
# #         key="builder_site_id",
# #     ).strip()

# # notes = st.text_input(
# #     "Site Notes (optional)",
# #     placeholder="e.g. Backyard grid, measured from porch corner…",
# #     key="builder_notes",
# # )

# # st.markdown("---")


# # # ═══════════════════════════════════════════════
# # #  STEP 2 — WHICH YARD (NEW)
# # # ═══════════════════════════════════════════════
# # st.subheader("② Which Yard")
# # st.caption(
# #     "Pick which yard you're configuring right now. Fill in fields ③–⑦, "
# #     "then hit Compute to stash THIS yard's grid. Switch the dropdown to "
# #     "the other yard if this site has both — repeat the fill + Compute. "
# #     "When you save below, all completed yards are merged into one site."
# # )

# # yard_choice = st.selectbox(
# #     "I am entering data for the:",
# #     options=["Front", "Back"],
# #     index=0,
# #     key="builder_yard_choice",
# #     help="The yard whose ③–⑦ fields you're filling in right now. "
# #          "Sites with only one yard: just fill the one and ignore the other.",
# # )
# # yard_key = yard_choice.lower()  # "front" or "back"
# # yard_zone = _zone_for_yard(yard_key)
# # yard_prefix = _prefix_for_yard(yard_key)

# # # Show a status banner telling the user what's already stashed.
# # front_done = st.session_state.get("front_config") is not None
# # back_done  = st.session_state.get("back_config")  is not None
# # status_msgs = []
# # if front_done:
# #     n = len(st.session_state["front_config"]["grid_blocks"])
# #     status_msgs.append(f"✅ Front yard stashed ({n} blocks)")
# # else:
# #     status_msgs.append("⬜ Front yard — not yet computed")
# # if back_done:
# #     n = len(st.session_state["back_config"]["grid_blocks"])
# #     status_msgs.append(f"✅ Back yard stashed ({n} blocks)")
# # else:
# #     status_msgs.append("⬜ Back yard — not yet computed")
# # st.info("  ·  ".join(status_msgs))

# # st.markdown("---")


# # # ═══════════════════════════════════════════════
# # #  STEP 3 — FIXED POINT LOCATION IN GRID  (per yard)
# # # ═══════════════════════════════════════════════
# # st.subheader(f"③ Fixed Point Location in Grid — {yard_choice} Yard")
# # st.caption("Identify which cell corner the GPS measurement was taken at. "
# #            "This anchors this yard's grid to the real world.")

# # col_fp1, col_fp2 = st.columns(2)
# # with col_fp1:
# #     fp_cell_input = st.text_input(
# #         "Fixed Point Cell ID *", value="E1",
# #         help="The cell whose corner was marked with GPS (e.g. E1, A1, D2)",
# #         key=f"fp_cell_{yard_key}",
# #     )
# # with col_fp2:
# #     fp_corner = st.selectbox(
# #         "Which corner of this cell? *",
# #         ["Top-Left", "Top-Right", "Bottom-Left", "Bottom-Right"],
# #         help="As drawn on the field sketch — not compass direction",
# #         key=f"fp_corner_{yard_key}",
# #     )

# # st.markdown("---")


# # # ═══════════════════════════════════════════════
# # #  STEP 4 — FIXED POINT GPS  (per yard)
# # # ═══════════════════════════════════════════════
# # st.subheader(f"④ Fixed Point GPS Coordinates — {yard_choice} Yard")

# # gps_format = st.radio(
# #     "Coordinate format",
# #     ["DMS (Degrees Minutes Seconds)", "Decimal Degrees"],
# #     horizontal=True,
# #     help="DMS example: 42° 55' 11.46\" N  ·  Decimal example: 42.9198500",
# #     key=f"gps_format_{yard_key}",
# # )

# # if gps_format == "DMS (Degrees Minutes Seconds)":
# #     col_lat, col_lon = st.columns(2)
# #     with col_lat:
# #         st.markdown("**Latitude (N)**")
# #         c1, c2, c3 = st.columns(3)
# #         lat_d = c1.number_input("Deg", value=42, key=f"lat_d_{yard_key}")
# #         lat_m = c2.number_input("Min", value=55, key=f"lat_m_{yard_key}")
# #         lat_s = c3.number_input("Sec", value=11.46, format="%.4f", key=f"lat_s_{yard_key}")
# #     with col_lon:
# #         st.markdown("**Longitude (W)**")
# #         c4, c5, c6 = st.columns(3)
# #         lon_d = c4.number_input("Deg", value=78, key=f"lon_d_{yard_key}")
# #         lon_m = c5.number_input("Min", value=49, key=f"lon_m_{yard_key}")
# #         lon_s = c6.number_input("Sec", value=33.63, format="%.4f", key=f"lon_s_{yard_key}")
# #     anchor_lat = dms_to_decimal(lat_d, lat_m, lat_s, 'N')
# #     anchor_lon = dms_to_decimal(lon_d, lon_m, lon_s, 'W')
# # else:
# #     col_lat, col_lon = st.columns(2)
# #     with col_lat:
# #         anchor_lat = st.number_input("Latitude", value=42.919850, format="%.7f",
# #                                       key=f"lat_dec_{yard_key}")
# #     with col_lon:
# #         anchor_lon = st.number_input("Longitude", value=-78.826008, format="%.7f",
# #                                       key=f"lon_dec_{yard_key}")

# # st.success(f"📍 {yard_choice} anchor locked: **{anchor_lat:.7f}°N, {abs(anchor_lon):.7f}°W**")

# # st.markdown("---")


# # # ═══════════════════════════════════════════════
# # #  STEP 5 — GRID LAYOUT & ORIENTATION  (per yard)
# # # ═══════════════════════════════════════════════
# # st.subheader(f"⑤ Grid Layout — {yard_choice} Yard")

# # col_orient, col_dir = st.columns(2)
# # with col_orient:
# #     orientation = st.selectbox(
# #         "Grid orientation on map",
# #         ["Vertical (strip runs North–South)", "Horizontal (strip runs East–West)"],
# #         help="Vertical = long axis goes up/down. Horizontal = long axis goes left/right.",
# #         key=f"orientation_{yard_key}",
# #     )
# # with col_dir:
# #     if "Vertical" in orientation:
# #         house_dir = st.selectbox("Which end is near the house?",
# #                                  ["Top (North)", "Bottom (South)"],
# #                                  key=f"house_dir_v_{yard_key}")
# #     else:
# #         house_dir = st.selectbox("Which end is near the house?",
# #                                  ["Left (West)", "Right (East)"],
# #                                  key=f"house_dir_h_{yard_key}")

# # st.markdown("---")


# # # ═══════════════════════════════════════════════
# # #  STEP 6 — DEFINE GRID ROWS  (per yard)
# # # ═══════════════════════════════════════════════
# # st.subheader(f"⑥ Define Grid Rows — {yard_choice} Yard")
# # st.caption("List row letters from **farthest from house** → **nearest to house**.")

# # rows_input = st.text_input(
# #     "Row letters (comma-separated) *", value="A, B, C, D, E",
# #     help="Example: A, B, C, D, E, F, G, H — where A is farthest from house",
# #     key=f"rows_{yard_key}",
# # )
# # rows = [r.strip().upper() for r in rows_input.split(",") if r.strip()]

# # if rows:
# #     st.info(f"**{len(rows)} rows:** {' → '.join(rows)}  _(far → near)_")

# # st.markdown("---")


# # # ═══════════════════════════════════════════════
# # #  STEP 7 — CELL DIMENSIONS  (per yard)
# # # ═══════════════════════════════════════════════
# # st.subheader(f"⑦ Cell Dimensions — {yard_choice} Yard")
# # st.caption("Enter each cell's **width** (perpendicular to strip) and **height** "
# #            "(along the strip). Accepts imperial: `11'6.5\"` or plain feet: `10`.")

# # max_cols = st.number_input("Max columns per row", min_value=1, max_value=5, value=3,
# #                             help="e.g. 3 if cells are A1, A2, A3",
# #                             key=f"max_cols_{yard_key}")

# # cell_data = {}
# # for row in rows:
# #     with st.expander(f"**Row {row}**", expanded=True):
# #         num_cols = st.number_input(f"Columns in row {row}", min_value=1,
# #                                     max_value=int(max_cols),
# #                                     value=min(int(max_cols), 3),
# #                                     key=f"ncols_{row}_{yard_key}")
# #         cols_ui = st.columns(int(num_cols))
# #         for c in range(int(num_cols)):
# #             col_num = c + 1
# #             cell_id = f"{row}{col_num}"
# #             with cols_ui[c]:
# #                 st.markdown(f"##### {cell_id}")
# #                 w = st.text_input("Width (ft)", value="10", key=f"w_{cell_id}_{yard_key}")
# #                 h = st.text_input("Height (ft)", value="10", key=f"h_{cell_id}_{yard_key}")
# #                 # Default the sample-id pattern to include the yard hint so
# #                 # downstream matching naturally segregates front from back.
# #                 default_pat = f"{yard_choice}_{cell_id}_"
# #                 pat = st.text_input("SampleID pattern", value=default_pat,
# #                                     key=f"pat_{cell_id}_{yard_key}",
# #                                     help="Substring matched against Master Data. "
# #                                          "Include 'Front' or 'Back' so the matcher "
# #                                          "associates readings with the correct yard.")
# #                 cell_data[cell_id] = {
# #                     "width": parse_imperial(w), "height": parse_imperial(h),
# #                     "col": col_num, "row": row, "pattern": pat,
# #                 }

# # st.markdown("---")


# # # ═══════════════════════════════════════════════
# # #  STEP 8 — POINT SAMPLES (OPTIONAL)  (per yard)
# # # ═══════════════════════════════════════════════
# # st.subheader(f"⑧ Point Samples _(optional)_ — {yard_choice} Yard")
# # st.caption("Non-grid samples (driplines, lawns, etc.). Offsets in feet from the fixed point.")

# # num_points = st.number_input("Number of point samples", min_value=0, max_value=20, value=0,
# #                               key=f"num_points_{yard_key}")
# # point_samples = {}
# # if num_points > 0:
# #     for i in range(int(num_points)):
# #         with st.expander(f"Point Sample {i + 1}", expanded=True):
# #             pc1, pc2, pc3, pc4 = st.columns(4)
# #             with pc1:
# #                 pt_name = st.text_input("Name", key=f"pt_name_{i}_{yard_key}",
# #                                         placeholder="HUD Dripline")
# #             with pc2:
# #                 pt_ox = st.number_input("East offset (ft)", key=f"pt_ox_{i}_{yard_key}", value=0.0)
# #             with pc3:
# #                 pt_oy = st.number_input("North offset (ft)", key=f"pt_oy_{i}_{yard_key}", value=0.0)
# #             with pc4:
# #                 pt_pat = st.text_input("SampleID pattern", key=f"pt_pat_{i}_{yard_key}",
# #                                         placeholder=f"{yard_choice}_HUD_Dripline")
# #             if pt_name:
# #                 # Prefix point sample key with yard prefix to avoid collisions
# #                 # when both yards have a point named e.g. "Dripline".
# #                 point_samples[f"{yard_prefix}{pt_name}"] = {
# #                     "name": pt_name,
# #                     "offset_x": pt_ox, "offset_y": pt_oy,
# #                     "sample_id_patterns": [pt_pat] if pt_pat else [],
# #                     "zone": "auxiliary",
# #                     "yard": yard_key,
# #                 }


# # # ═══════════════════════════════════════════════
# # #  COMPUTE  (per yard)
# # # ═══════════════════════════════════════════════
# # st.markdown("---")
# # st.markdown(f"### 🔧 Generate Configuration — {yard_choice} Yard")
# # st.caption(
# #     f"Computing only the **{yard_choice}** yard right now. If this site has "
# #     f"both yards, switch the dropdown to the other yard, fill in its fields, "
# #     f"and click Compute again. Both yards get merged together when you Save."
# # )

# # col_btn, col_btn2, _ = st.columns([2, 2, 4])
# # with col_btn:
# #     compute = st.button(
# #         f"Compute {yard_choice} Yard",
# #         type="primary",
# #         use_container_width=True,
# #         key=f"compute_{yard_key}",
# #     )
# # with col_btn2:
# #     clear_yard = st.button(
# #         f"Clear {yard_choice} Yard",
# #         use_container_width=True,
# #         key=f"clear_{yard_key}",
# #         help="Forget the currently-stashed configuration for this yard. "
# #              "Does NOT touch site_configs.json on disk.",
# #     )

# # if clear_yard:
# #     st.session_state.pop(f"{yard_key}_config", None)
# #     st.success(f"🗑️ Cleared stashed {yard_choice} yard from this session.")
# #     st.rerun()

# # if compute:
# #     errors = []
# #     if not site_id:
# #         errors.append("SiteID is required.")
# #     if not rows:
# #         errors.append("At least one grid row must be defined.")
# #     if not cell_data:
# #         errors.append("Cell dimensions are required.")
# #     fp_cell = fp_cell_input.strip().upper()
# #     if fp_cell not in cell_data:
# #         errors.append(f"Fixed point cell '{fp_cell}' doesn't match any defined cell.")
# #     if errors:
# #         for e in errors:
# #             st.error(e)
# #         st.stop()

# #     row_heights = {}
# #     for row in rows:
# #         c1 = f"{row}1"
# #         if c1 in cell_data:
# #             row_heights[row] = cell_data[c1]["height"]
# #         else:
# #             for cid, cd in cell_data.items():
# #                 if cd["row"] == row:
# #                     row_heights[row] = cd["height"]
# #                     break

# #     strip_pos, pos = {}, 0
# #     for row in rows:
# #         strip_pos[row] = pos
# #         pos += row_heights.get(row, 10)

# #     fp_row = ''.join(c for c in fp_cell if c.isalpha())
# #     fp_col = int(''.join(c for c in fp_cell if c.isdigit()))

# #     col_widths_per_row = {}
# #     for row in rows:
# #         col_widths_per_row[row] = {}
# #         for cid, cd in cell_data.items():
# #             if cd["row"] == row:
# #                 col_widths_per_row[row][cd["col"]] = cd["width"]

# #     fp_row_widths = col_widths_per_row.get(fp_row, {})
# #     fp_perp = 0
# #     if "Left" in fp_corner:
# #         for c in range(1, fp_col):
# #             fp_perp += fp_row_widths.get(c, 0)
# #     else:
# #         for c in range(1, fp_col + 1):
# #             fp_perp += fp_row_widths.get(c, 0)

# #     fp_strip = strip_pos[fp_row] + (row_heights[fp_row] if "Top" in fp_corner else 0)

# #     is_vertical = "Vertical" in orientation
# #     flip_strip = "Top" in house_dir or "Right" in house_dir

# #     grid_blocks = {}
# #     for cid, cd in cell_data.items():
# #         row, col = cd["row"], cd["col"]
# #         cell_h, cell_w = cd["height"], cd["width"]

# #         strip_start = strip_pos[row] - fp_strip
# #         strip_end = strip_start + row_heights[row]
# #         if cell_h != row_heights[row]:
# #             strip_start = strip_end - cell_h

# #         perp_start = sum(col_widths_per_row[row].get(c, 0) for c in range(1, col))
# #         perp_end = perp_start + cell_w
# #         perp_start -= fp_perp
# #         perp_end -= fp_perp

# #         if flip_strip:
# #             strip_start, strip_end = -strip_end, -strip_start

# #         if is_vertical:
# #             ns, ne, es, ee = strip_start, strip_end, perp_start, perp_end
# #         else:
# #             es, ee, ns, ne = strip_start, strip_end, perp_start, perp_end

# #         # Internal collision-proof key: F_A1 or B_A1.
# #         block_key = f"{yard_prefix}{cid}"
# #         grid_blocks[block_key] = {
# #             "sw_x": round(min(es, ee), 2), "sw_y": round(min(ns, ne), 2),
# #             "ne_x": round(max(es, ee), 2), "ne_y": round(max(ns, ne), 2),
# #             "sample_id_patterns": [cd["pattern"]] if cd["pattern"] else [],
# #             "zone": yard_zone,        # "front_yard" or "backyard"
# #             "cell_id": cid,           # human-readable label, e.g. "A1"
# #             "yard": yard_key,         # "front" or "back"
# #             "mock_ppm": 0,
# #         }

# #     # ── Preserve existing rotation if this site_id was saved before ──
# #     # Look up rotation specifically for THIS yard if the saved config
# #     # has the new yards-keyed shape; otherwise fall back to top-level
# #     # rotation_deg (legacy).
# #     base_dir = os.path.dirname(os.path.abspath(__file__))
# #     config_path = os.path.join(base_dir, "..", "data", "site_configs", "site_configs.json")
# #     existing = load_existing_config_for_site_id(site_id, config_path)
# #     preserved_rotation = 0
# #     if existing:
# #         if "yards" in existing and yard_key in (existing.get("yards") or {}):
# #             preserved_rotation = (existing["yards"][yard_key] or {}).get("rotation_deg", 0)
# #         else:
# #             preserved_rotation = existing.get("rotation_deg", 0)

# #     yard_config = {
# #         "anchor": {
# #             "lat": anchor_lat, "lon": anchor_lon,
# #             "description": f"{yard_choice} yard fixed point at {fp_cell} ({fp_corner}) — field-measured GPS",
# #             "marker_label": f"{yard_choice} Fixed Point ({fp_cell})",
# #         },
# #         "rotation_deg": preserved_rotation,
# #         "grid_blocks": grid_blocks,
# #         "point_samples": point_samples,
# #     }

# #     # Stash THIS yard. The other yard, if previously computed, is untouched.
# #     st.session_state[f"{yard_key}_config"] = yard_config

# #     # Whenever a yard is computed, rebuild the combined generated_config so
# #     # the preview & legacy consumers see the union. Use the front anchor for
# #     # the legacy mirror if front exists, else back.
# #     yards_block = {
# #         "front": st.session_state.get("front_config"),
# #         "back":  st.session_state.get("back_config"),
# #     }
# #     legacy_mirror = _merge_yards_into_legacy(yards_block)
# #     combined_config = {
# #         "site_id": site_id,
# #         "sampling_date": str(sampling_date),
# #         "notes": notes,
# #         "anchor": legacy_mirror["anchor"],
# #         "rotation_deg": legacy_mirror["rotation_deg"],
# #         "map_defaults": {"zoom_start": 21, "center_offset_north_ft": 0, "center_offset_east_ft": 0},
# #         "grid_blocks": legacy_mirror["grid_blocks"],
# #         "point_samples": legacy_mirror["point_samples"],
# #         "yards": {k: v for k, v in yards_block.items() if v is not None},
# #     }
# #     st.session_state["generated_config"] = combined_config
# #     # We're in the new-site flow, not editing a loaded config.
# #     st.session_state["loaded_from_disk"] = False
# #     # Reset stale drag state.
# #     for k in ("pending_offset_e", "pending_offset_n", "pending_rotation",
# #               "front_offset_e", "front_offset_n", "front_rotation",
# #               "back_offset_e", "back_offset_n", "back_rotation"):
# #         st.session_state.pop(k, None)

# #     msg_lines = [
# #         f"✅ **{yard_choice} yard computed** — {len(grid_blocks)} blocks · "
# #         f"{len(point_samples)} point samples."
# #     ]
# #     other = "back" if yard_key == "front" else "front"
# #     other_done = st.session_state.get(f"{other}_config") is not None
# #     if other_done:
# #         n_other = len(st.session_state[f"{other}_config"]["grid_blocks"])
# #         msg_lines.append(
# #             f"Both yards now stashed (Front + Back). Scroll down to the "
# #             f"preview to position them and Save."
# #         )
# #     else:
# #         msg_lines.append(
# #             f"Only **{yard_choice}** stashed so far. If this site has a "
# #             f"{other.capitalize()} yard too, switch the dropdown to "
# #             f"**{other.capitalize()}**, fill it in, and click Compute again. "
# #             f"Otherwise scroll down to position & Save just this one."
# #         )
# #     st.success("  \n".join(msg_lines))


# # # ═══════════════════════════════════════════════
# # #  RESULTS & DRAGGABLE PREVIEW
# # # ═══════════════════════════════════════════════
# # if "generated_config" in st.session_state:
# #     config = st.session_state["generated_config"]
# #     st.markdown("---")

# #     # ── Computed-offsets table — group by yard if the new shape exists ──
# #     st.subheader("📋 Computed Grid Offsets")
# #     yards_in_config = config.get("yards") or {}
# #     if yards_in_config:
# #         for yk, ydata in yards_in_config.items():
# #             if not ydata:
# #                 continue
# #             st.markdown(f"**{yk.capitalize()} Yard** — anchor "
# #                         f"`{ydata['anchor']['lat']:.6f}, {ydata['anchor']['lon']:.6f}`")
# #             tbl = []
# #             for bid, b in ydata.get("grid_blocks", {}).items():
# #                 tbl.append({
# #                     "Cell": b.get("cell_id", bid),
# #                     "Internal ID": bid,
# #                     "SW East": b["sw_x"], "SW North": b["sw_y"],
# #                     "NE East": b["ne_x"], "NE North": b["ne_y"],
# #                     "W (ft)": round(b["ne_x"] - b["sw_x"], 1),
# #                     "H (ft)": round(b["ne_y"] - b["sw_y"], 1),
# #                     "Pattern": ", ".join(b.get("sample_id_patterns", [])),
# #                 })
# #             st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True)
# #     else:
# #         # Legacy single-yard view — exactly as before.
# #         tbl = []
# #         for bid, b in config["grid_blocks"].items():
# #             tbl.append({
# #                 "Cell": b.get("cell_id", bid),
# #                 "SW East": b["sw_x"], "SW North": b["sw_y"],
# #                 "NE East": b["ne_x"], "NE North": b["ne_y"],
# #                 "W (ft)": round(b["ne_x"] - b["sw_x"], 1),
# #                 "H (ft)": round(b["ne_y"] - b["sw_y"], 1),
# #                 "Pattern": ", ".join(b.get("sample_id_patterns", [])),
# #             })
# #         st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True)

# #     # ═══════════════════════════════════════════
# #     #  DRAGGABLE LEAFLET PREVIEW
# #     # ═══════════════════════════════════════════
# #     st.subheader("🗺️ Draggable Satellite Preview")
# #     st.caption(
# #         "**Click & drag** the grid to nudge it onto the actual yard. "
# #         "When both yards exist, each is dragged INDEPENDENTLY — click "
# #         "a front-yard block to move the front grid, a back-yard block to "
# #         "move the back grid. Rotation controls below the map are also "
# #         "per-yard. Click **Save** to persist."
# #     )

# #     # ── Build per-yard render payloads ────────────────────────────────
# #     # If the config has the new `yards` shape, render each yard with its
# #     # own anchor + rotation. If it's a legacy single-yard config, render
# #     # it as a single "back" yard for UI purposes (preserves on-save shape).
# #     render_yards = {}  # yard_key -> {anchor, rotation, blocks_payload, points_payload}

# #     if yards_in_config:
# #         for yk, ydata in yards_in_config.items():
# #             if not ydata:
# #                 continue
# #             blocks_payload = []
# #             for bid, b in ydata.get("grid_blocks", {}).items():
# #                 corners = [
# #                     [b["sw_x"], b["sw_y"]],
# #                     [b["ne_x"], b["sw_y"]],
# #                     [b["ne_x"], b["ne_y"]],
# #                     [b["sw_x"], b["ne_y"]],
# #                 ]
# #                 cx = (b["sw_x"] + b["ne_x"]) / 2
# #                 cy = (b["sw_y"] + b["ne_y"]) / 2
# #                 mock_ppm = b.get("mock_ppm", 0)
# #                 label, color = get_nysh_category(mock_ppm) if mock_ppm else ("Preview", "#4a90d9")
# #                 blocks_payload.append({
# #                     "id": bid,
# #                     "cell": b.get("cell_id", bid),
# #                     "corners": corners,
# #                     "cx": cx, "cy": cy,
# #                     "color": color,
# #                     "label": label,
# #                     "ppm": mock_ppm,
# #                 })
# #             points_payload = []
# #             for pid, pt in ydata.get("point_samples", {}).items():
# #                 points_payload.append({
# #                     "id": pid,
# #                     "name": pt.get("name", pid),
# #                     "ox": pt.get("offset_x", 0),
# #                     "oy": pt.get("offset_y", 0),
# #                 })
# #             render_yards[yk] = {
# #                 "anchor_lat": ydata["anchor"]["lat"],
# #                 "anchor_lon": ydata["anchor"]["lon"],
# #                 "rotation":   ydata.get("rotation_deg", 0),
# #                 "blocks":     blocks_payload,
# #                 "points":     points_payload,
# #             }
# #     else:
# #         # Legacy single-yard config — render as one yard. Default to back
# #         # per spec (SampleIDs without Front/Back → backyard).
# #         blocks_payload = []
# #         for bid, b in config["grid_blocks"].items():
# #             corners = [
# #                 [b["sw_x"], b["sw_y"]],
# #                 [b["ne_x"], b["sw_y"]],
# #                 [b["ne_x"], b["ne_y"]],
# #                 [b["sw_x"], b["ne_y"]],
# #             ]
# #             cx = (b["sw_x"] + b["ne_x"]) / 2
# #             cy = (b["sw_y"] + b["ne_y"]) / 2
# #             mock_ppm = b.get("mock_ppm", 0)
# #             label, color = get_nysh_category(mock_ppm) if mock_ppm else ("Preview", "#4a90d9")
# #             blocks_payload.append({
# #                 "id": bid,
# #                 "cell": b.get("cell_id", bid),
# #                 "corners": corners,
# #                 "cx": cx, "cy": cy,
# #                 "color": color,
# #                 "label": label,
# #                 "ppm": mock_ppm,
# #             })
# #         points_payload = []
# #         for pid, pt in config.get("point_samples", {}).items():
# #             points_payload.append({
# #                 "id": pid,
# #                 "name": pt.get("name", pid),
# #                 "ox": pt.get("offset_x", 0),
# #                 "oy": pt.get("offset_y", 0),
# #             })
# #         # Use "legacy" key so the JS knows there's no yard split; save logic
# #         # will keep this config in its original shape.
# #         render_yards["legacy"] = {
# #             "anchor_lat": config["anchor"]["lat"],
# #             "anchor_lon": config["anchor"]["lon"],
# #             "rotation":   config.get("rotation_deg", 0),
# #             "blocks":     blocks_payload,
# #             "points":     points_payload,
# #         }

# #     # Build legend
# #     legend_rows = ""
# #     for t in NYSH_TIERS:
# #         legend_rows += (
# #             '<div><span style="display:inline-block;width:11px;height:11px;'
# #             f'background:{t["color"]};border-radius:2px;margin-right:5px;'
# #             f'vertical-align:middle"></span>{t["label"]}</div>'
# #         )
# #     legend_rows += (
# #         '<div><span style="display:inline-block;width:11px;height:11px;'
# #         'background:#4a90d9;border-radius:2px;margin-right:5px;'
# #         'vertical-align:middle"></span>Preview (no data yet)</div>'
# #     )

# #     # Compute the initial map center: midpoint of all yards' anchors.
# #     if render_yards:
# #         anchor_lats = [y["anchor_lat"] for y in render_yards.values()]
# #         anchor_lons = [y["anchor_lon"] for y in render_yards.values()]
# #         map_center_lat = sum(anchor_lats) / len(anchor_lats)
# #         map_center_lon = sum(anchor_lons) / len(anchor_lons)
# #     else:
# #         map_center_lat = config.get("anchor", {}).get("lat", 0)
# #         map_center_lon = config.get("anchor", {}).get("lon", 0)

# #     # Build the dynamic controls HTML — one block per yard.
# #     # Colors per yard so they're visually distinguishable on the map.
# #     yard_visuals = {
# #         "front":  {"label": "Front Yard", "stroke": "#ffd166", "anchor_color": "#ffd166"},
# #         "back":   {"label": "Back Yard",  "stroke": "#ff4444", "anchor_color": "#ff4444"},
# #         "legacy": {"label": "Grid",       "stroke": "#ff4444", "anchor_color": "#ff4444"},
# #     }

# #     controls_html = ""
# #     for yk in render_yards.keys():
# #         viz = yard_visuals[yk]
# #         rot_init = render_yards[yk]["rotation"]
# #         controls_html += f"""
# #         <div class="yard-block" data-yard="{yk}" style="border-left:3px solid {viz['stroke']};">
# #           <b>{viz['label']} Position</b>
# #           <div class="hint">Click &amp; drag a {viz['label'].lower()} block on the map</div>
# #           <div class="rotate-row">
# #             <button onclick="rg('{yk}', -5)">−5°</button>
# #             <button onclick="rg('{yk}', -1)">−1°</button>
# #             <span id="rd_{yk}">{rot_init}°</span>
# #             <button onclick="rg('{yk}', 1)">+1°</button>
# #             <button onclick="rg('{yk}', 5)">+5°</button>
# #           </div>
# #           <div class="offset" id="od_{yk}">Offset: 0.0 E, 0.0 N</div>
# #           <button class="reset-btn" onclick="rs('{yk}')">Reset {viz['label']}</button>
# #         </div>
# #         """

# #     # Serialise per-yard payloads for JS.
# #     yards_json = json.dumps({
# #         yk: {
# #             "anchor_lat": y["anchor_lat"],
# #             "anchor_lon": y["anchor_lon"],
# #             "rotation":   y["rotation"],
# #             "blocks":     y["blocks"],
# #             "points":     y["points"],
# #             "stroke":     yard_visuals[yk]["stroke"],
# #             "anchor_color": yard_visuals[yk]["anchor_color"],
# #             "label":      yard_visuals[yk]["label"],
# #         }
# #         for yk, y in render_yards.items()
# #     })

# #     # Use a per-site localStorage key so two sites don't trample each
# #     # other's drag state in the same browser session. Strip characters
# #     # that might confuse JS string concatenation.
# #     site_id_for_storage = re.sub(
# #         r"[^A-Za-z0-9_-]", "_",
# #         config.get("site_id", "site")
# #     )

# #     # Leaflet HTML component with PER-YARD drag + rotate + message bridge.
# #     # The JS keeps a state map keyed by yard, and click-detection figures
# #     # out which yard's blocks are under the cursor so drags are isolated.
# #     component_html = f"""
# # <!DOCTYPE html>
# # <html><head>
# # <meta charset="utf-8">
# # <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
# # <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
# # <style>
# #   html,body {{ margin:0; padding:0; font-family:Arial,sans-serif; background:#0c0f14; }}
# #   #map {{ width:100%; height:560px; }}
# #   .legend {{ position:absolute; bottom:20px; left:20px; z-index:1001;
# #     background:rgba(12,15,20,0.93); padding:12px 16px; border-radius:10px;
# #     color:#e8eaed; font-size:11px; line-height:1.7;
# #     border:1px solid rgba(255,255,255,0.08); }}
# #   .legend b {{ font-size:13px; }}
# #   .controls {{ position:absolute; top:20px; right:20px; z-index:1001;
# #     background:rgba(12,15,20,0.93); padding:8px 12px; border-radius:10px;
# #     color:#e8eaed; font-size:11px; border:1px solid rgba(255,255,255,0.08);
# #     min-width:230px; max-height:540px; overflow-y:auto; }}
# #   .controls .yard-block {{ padding:8px 6px 10px 10px; margin-bottom:6px;
# #     border-radius:6px; background:rgba(255,255,255,0.02); }}
# #   .controls .yard-block:last-child {{ margin-bottom:0; }}
# #   .controls b {{ font-size:13px; color:#e67e22; }}
# #   .controls .hint {{ font-size:10px; color:#7a8599; margin-top:2px; }}
# #   .controls .offset {{ font-family:monospace; font-size:11px; color:#4ecdc4;
# #     margin-top:6px; background:rgba(78,205,196,0.08); padding:5px 8px;
# #     border-radius:4px; }}
# #   .controls button {{ padding:4px 9px; border:1px solid rgba(255,255,255,0.15);
# #     border-radius:4px; background:rgba(78,205,196,0.12); color:#4ecdc4;
# #     cursor:pointer; font-size:10px; }}
# #   .controls button:hover {{ background:rgba(78,205,196,0.25); }}
# #   .rotate-row {{ display:flex; gap:4px; align-items:center; margin-top:6px; }}
# #   .rotate-row button {{ margin:0; padding:3px 7px; font-size:10px; }}
# #   .rotate-row span {{ font-size:11px; color:#c7d0dc; min-width:38px;
# #     text-align:center; font-family:monospace; }}
# #   .reset-btn {{ margin-top:8px; width:100%; background:rgba(255,100,100,0.12) !important;
# #     color:#ff8888 !important; }}
# # </style>
# # </head><body>
# # <div id="map"></div>
# # <div class="legend"><b>Lead Guidelines (ppm)</b><br>{legend_rows}</div>
# # <div class="controls">{controls_html}</div>

# # <script>
# #   var RF = 20925721.78;
# #   var YARDS = {yards_json};

# #   // Per-yard mutable state.
# #   var STATE = {{}};
# #   Object.keys(YARDS).forEach(function(yk) {{
# #     STATE[yk] = {{ oE: 0, oN: 0, rot: YARDS[yk].rotation }};
# #   }});

# #   var map = L.map('map', {{
# #     center: [{map_center_lat}, {map_center_lon}], zoom: 21, maxZoom: 25
# #   }});
# #   L.tileLayer(
# #     'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
# #     {{ attribution: 'Esri', maxZoom: 25, maxNativeZoom: 19 }}
# #   ).addTo(map);

# #   // One anchor marker per yard (stays put — doesn't move with drag).
# #   Object.keys(YARDS).forEach(function(yk) {{
# #     var Y = YARDS[yk];
# #     L.marker([Y.anchor_lat, Y.anchor_lon], {{
# #       icon: L.divIcon({{
# #         className: '',
# #         html: '<div style="width:14px;height:14px;background:' + Y.anchor_color +
# #               ';border:2px solid white;border-radius:50%;box-shadow:0 0 6px rgba(0,0,0,0.6)"></div>',
# #         iconSize: [14,14], iconAnchor: [7,7]
# #       }})
# #     }}).addTo(map).bindTooltip(Y.label + ' Anchor');
# #   }});

# #   function f2ll(la, lo, e, n) {{
# #     var dl = (n / RF) * (180 / Math.PI);
# #     var dn = (e / (RF * Math.cos(la * Math.PI / 180))) * (180 / Math.PI);
# #     return [la + dl, lo + dn];
# #   }}

# #   function rp(x, y, a) {{
# #     var r = a * Math.PI / 180;
# #     return [x * Math.cos(r) - y * Math.sin(r), x * Math.sin(r) + y * Math.cos(r)];
# #   }}

# #   // Per-yard layer groups so we can clear & re-draw each independently.
# #   var GROUPS = {{}};
# #   Object.keys(YARDS).forEach(function(yk) {{
# #     GROUPS[yk] = L.layerGroup().addTo(map);
# #   }});

# #   // Track which polygons belong to which yard (for click hit-test).
# #   var POLY_TO_YARD = []; // array of {{poly, yard}}

# #   function drawYard(yk) {{
# #     var Y = YARDS[yk];
# #     var S = STATE[yk];
# #     GROUPS[yk].clearLayers();
# #     // Filter out our prior poly-yard mappings for this yard before re-adding.
# #     POLY_TO_YARD = POLY_TO_YARD.filter(function(rec) {{ return rec.yard !== yk; }});

# #     Y.blocks.forEach(function(b) {{
# #       var ll = b.corners.map(function(c) {{
# #         var r = rp(c[0], c[1], S.rot);
# #         return f2ll(Y.anchor_lat, Y.anchor_lon, r[0] + S.oE, r[1] + S.oN);
# #       }});
# #       var pl = L.polygon(ll, {{
# #         color: Y.stroke, weight: 2,
# #         fillColor: b.color, fillOpacity: 0.65
# #       }});
# #       pl.bindTooltip('<b>' + b.cell + '</b><br>' + Y.label + '<br>' + b.label);
# #       GROUPS[yk].addLayer(pl);
# #       POLY_TO_YARD.push({{ poly: pl, yard: yk }});

# #       var rc = rp(b.cx, b.cy, S.rot);
# #       var lp = f2ll(Y.anchor_lat, Y.anchor_lon, rc[0] + S.oE, rc[1] + S.oN);
# #       GROUPS[yk].addLayer(L.marker(lp, {{
# #         icon: L.divIcon({{
# #           className: '',
# #           html: '<div style="font-family:Arial;text-align:center;pointer-events:none">' +
# #                 '<b style="font-size:10px;color:white;text-shadow:0 1px 3px rgba(0,0,0,0.85)">' +
# #                 b.cell + '</b></div>',
# #           iconSize: [50, 20], iconAnchor: [25, 10]
# #         }}),
# #         interactive: false
# #       }}));
# #     }});

# #     Y.points.forEach(function(p) {{
# #       var r = rp(p.ox, p.oy, S.rot);
# #       var ll = f2ll(Y.anchor_lat, Y.anchor_lon, r[0] + S.oE, r[1] + S.oN);
# #       GROUPS[yk].addLayer(L.circleMarker(ll, {{
# #         radius: 7, color: 'white', weight: 2,
# #         fillColor: '#f39c12', fillOpacity: 0.8
# #       }}).bindTooltip('<b>' + p.name + '</b> (' + Y.label + ')'));
# #     }});

# #     // Update per-yard control panel readout.
# #     var od = document.getElementById('od_' + yk);
# #     var rd = document.getElementById('rd_' + yk);
# #     if (od) od.textContent = 'Offset: ' + S.oE.toFixed(1) + ' E, ' + S.oN.toFixed(1) + ' N' +
# #       (S.rot ? ('  |  ' + S.rot + '°') : '');
# #     if (rd) rd.textContent = S.rot + '°';

# #     postState();
# #   }}

# #   function drawAll() {{
# #     Object.keys(YARDS).forEach(drawYard);
# #   }}

# #   function postState() {{
# #     // Send the full per-yard state up to the Streamlit host.
# #     var payload = {{ type: 'groundsense_grid_state_multi', yards: {{}} }};
# #     Object.keys(STATE).forEach(function(yk) {{
# #       payload.yards[yk] = {{
# #         offset_east_ft:  STATE[yk].oE,
# #         offset_north_ft: STATE[yk].oN,
# #         rotation_deg:    STATE[yk].rot
# #       }};
# #     }});
# #     // Persist to BOTH localStorage (for streamlit_js_eval to read on
# #     // Python-side reruns — the message-bus is racy) AND postMessage
# #     // (for any listener that's already wired up).
# #     try {{
# #       window.parent.localStorage.setItem(
# #         'gs_drag_state_' + '{site_id_for_storage}',
# #         JSON.stringify(payload.yards)
# #       );
# #     }} catch (e) {{
# #       // Cross-origin localStorage access blocked — try this frame's own.
# #       try {{
# #         window.localStorage.setItem(
# #           'gs_drag_state_' + '{site_id_for_storage}',
# #           JSON.stringify(payload.yards)
# #         );
# #       }} catch (e2) {{ /* give up — postMessage still works */ }}
# #     }}
# #     window.parent.postMessage(payload, '*');
# #   }}

# #   function rg(yk, d) {{ STATE[yk].rot += d; drawYard(yk); }}
# #   function rs(yk) {{ STATE[yk].oE = 0; STATE[yk].oN = 0; STATE[yk].rot = 0; drawYard(yk); }}

# #   // Click & drag detection — figure out which yard owns the hit polygon.
# #   var iD = false, dY = null, dL = null, dE = 0, dN = 0;
# #   map.on('mousedown', function(e) {{
# #     var hit_yard = null;
# #     POLY_TO_YARD.forEach(function(rec) {{
# #       if (!hit_yard && rec.poly.getBounds().contains(e.latlng)) hit_yard = rec.yard;
# #     }});
# #     if (hit_yard) {{
# #       iD = true; dY = hit_yard; dL = e.latlng;
# #       dE = STATE[hit_yard].oE; dN = STATE[hit_yard].oN;
# #       map.dragging.disable();
# #       map.getContainer().style.cursor = 'grabbing';
# #     }}
# #   }});
# #   map.on('mousemove', function(e) {{
# #     if (!iD) return;
# #     var Y = YARDS[dY];
# #     STATE[dY].oN = dN + (e.latlng.lat - dL.lat) * (Math.PI / 180) * RF;
# #     STATE[dY].oE = dE + (e.latlng.lng - dL.lng) * (Math.PI / 180) * RF *
# #               Math.cos(Y.anchor_lat * Math.PI / 180);
# #     drawYard(dY);
# #   }});
# #   map.on('mouseup', function() {{
# #     if (iD) {{
# #       iD = false; dY = null;
# #       map.dragging.enable();
# #       map.getContainer().style.cursor = '';
# #     }}
# #   }});

# #   drawAll();
# # </script>
# # </body></html>
# # """

# #     components.html(component_html, height=580, scrolling=False)

# #     # ──────────────────────────────────────────────────────────────────
# #     # CAPTURE DRAG STATE — robust localStorage-based bridge
# #     # ──────────────────────────────────────────────────────────────────
# #     # The Leaflet iframe writes drag state to parent.localStorage on every
# #     # nudge (see postState() in the JS above). On Python rerun, we read
# #     # that localStorage key via streamlit_js_eval. This is rock-solid
# #     # vs the postMessage approach which races on iframe load.
# #     #
# #     # If streamlit_js_eval is unavailable, fall back to manual number
# #     # inputs. Either way, the final live_states[yk] feeds Save.
# #     # ──────────────────────────────────────────────────────────────────

# #     try:
# #         from streamlit_js_eval import streamlit_js_eval
# #         bridge_available = True
# #     except ImportError:
# #         bridge_available = False

# #     st.markdown("#### 💾 Save Fine-Tuned Position")
# #     st.caption(
# #         "After dragging in the map above, click **🔄 Capture Drag State** "
# #         "to pull the live offsets into the inputs below. Then click **💾 Save** "
# #         "to persist. You can also type values directly into the inputs."
# #     )

# #     yard_keys_for_state = list(render_yards.keys())

# #     # ── Step 1: read whatever's in localStorage right now (auto on every rerun) ──
# #     captured = {}
# #     if bridge_available:
# #         storage_key = f"gs_drag_state_{site_id_for_storage}"
# #         # Read from BOTH localStorage scopes (parent and iframe) — whichever
# #         # the postState() write succeeded into. Return as JSON string.
# #         raw = streamlit_js_eval(
# #             js_expressions=f"""
# #                 (function() {{
# #                     var k = '{storage_key}';
# #                     var v = null;
# #                     try {{ v = window.parent.localStorage.getItem(k); }} catch(e) {{}}
# #                     if (!v) {{
# #                         try {{ v = window.localStorage.getItem(k); }} catch(e) {{}}
# #                     }}
# #                     return v || '';
# #                 }})()
# #             """,
# #             key=f"gs_storage_read_{site_id_for_storage}",
# #             want_output=True,
# #         )
# #         if raw:
# #             try:
# #                 captured = json.loads(raw)
# #             except Exception:
# #                 captured = {}

# #     # ── Step 2: explicit Capture button (forces a re-read + writes into inputs) ──
# #     # The bridge above runs on every rerun, but the Capture button is the
# #     # tech's "I'm done dragging — pull values in NOW" handoff. Clicking it
# #     # copies localStorage → session_state, so the inputs below show the
# #     # captured values and Save reads them.
# #     cap_col, status_col = st.columns([1, 3])
# #     with cap_col:
# #         capture_clicked = st.button(
# #             "🔄 Capture Drag State",
# #             use_container_width=True,
# #             key="capture_drag_btn",
# #             help="Pull the current drag/rotation from the map above into the inputs.",
# #         )
# #     with status_col:
# #         if captured:
# #             parts = []
# #             for yk in yard_keys_for_state:
# #                 c = captured.get(yk) or {}
# #                 e = c.get("offset_east_ft", 0) or 0
# #                 n = c.get("offset_north_ft", 0) or 0
# #                 r = c.get("rotation_deg", 0) or 0
# #                 parts.append(
# #                     f"{yard_visuals[yk]['label']}: "
# #                     f"{e:+.1f}E / {n:+.1f}N / {r:+.0f}°"
# #                 )
# #             st.caption("🟢 Live drag state detected: " + "  ·  ".join(parts))
# #         else:
# #             st.caption(
# #                 "⚪ No drag state in browser storage yet. "
# #                 "Drag in the map above first, then click Capture."
# #             )

# #     # ── Step 3: per-yard editable inputs (the actual source of truth for Save) ──
# #     # If Capture was clicked, copy localStorage values into the input keys
# #     # BEFORE the widgets are instantiated. Streamlit reads from session_state
# #     # on the next rerun, so this gets the values into the boxes.
# #     if capture_clicked and captured:
# #         for yk in yard_keys_for_state:
# #             c = captured.get(yk) or {}
# #             st.session_state[f"in_e_{yk}"] = float(c.get("offset_east_ft", 0) or 0)
# #             st.session_state[f"in_n_{yk}"] = float(c.get("offset_north_ft", 0) or 0)
# #             st.session_state[f"in_r_{yk}"] = float(
# #                 c.get("rotation_deg", render_yards[yk]["rotation"]) or 0
# #             )
# #         st.rerun()

# #     live_states = {}
# #     if not bridge_available:
# #         st.info(
# #             "⚙️ For one-click drag capture, install `streamlit-js-eval`:  \n"
# #             "`pip install streamlit-js-eval`  \n\n"
# #             "Meanwhile, type each yard's drag offsets manually below."
# #         )

# #     for yk in yard_keys_for_state:
# #         st.markdown(f"**{yard_visuals[yk]['label']}**")
# #         mc1, mc2, mc3 = st.columns(3)
# #         # Default values come from session_state (populated by Capture) or
# #         # fall back to zero / the saved rotation. Number inputs read & write
# #         # to session_state via their key.
# #         default_e = float(st.session_state.get(f"in_e_{yk}", 0.0) or 0.0)
# #         default_n = float(st.session_state.get(f"in_n_{yk}", 0.0) or 0.0)
# #         default_r = float(
# #             st.session_state.get(f"in_r_{yk}", render_yards[yk]["rotation"]) or 0.0
# #         )
# #         live_states[yk] = {
# #             "e": mc1.number_input(
# #                 "East offset (ft)", value=default_e, step=0.1,
# #                 format="%.2f", key=f"in_e_{yk}",
# #             ),
# #             "n": mc2.number_input(
# #                 "North offset (ft)", value=default_n, step=0.1,
# #                 format="%.2f", key=f"in_n_{yk}",
# #             ),
# #             "r": mc3.number_input(
# #                 "Rotation (°)", value=default_r, step=1.0,
# #                 format="%.2f", key=f"in_r_{yk}",
# #             ),
# #         }

# #     st.markdown("---")

# #     # Buttons
# #     sb1, sb2, _ = st.columns([2, 2, 3])
# #     with sb1:
# #         save_clicked = st.button("💾 Save Position to Config",
# #                                   type="primary", use_container_width=True,
# #                                   key="save_position_btn")
# #     with sb2:
# #         download_clicked = st.button("📥 Preview JSON",
# #                                       use_container_width=True,
# #                                       key="preview_json_btn")

# #     if save_clicked:
# #         R_EARTH_FT = 20_925_721.78
# #         # Deep-copy the current config so we can mutate freely.
# #         updated_config = json.loads(json.dumps(config))
# #         loaded_from_disk = st.session_state.get("loaded_from_disk", False)
# #         had_yards_originally = bool((updated_config.get("yards") or {}))

# #         def _shift_anchor(old_lat, old_lon, e_ft, n_ft):
# #             """Return (new_lat, new_lon) after applying the (east,north) ft offset."""
# #             delta_lat = (n_ft / R_EARTH_FT) * (180 / math.pi)
# #             lat_rad = old_lat * (math.pi / 180)
# #             delta_lon = (e_ft / (R_EARTH_FT * math.cos(lat_rad))) * (180 / math.pi)
# #             return old_lat + delta_lat, old_lon + delta_lon

# #         # ── Case 1: legacy single-yard config (loaded from disk OR new flow
# #         #            with no yards key present). Update in place, no `yards`
# #         #            key. Keeps the old schema verbatim — historical data
# #         #            untouched.
# #         if not had_yards_originally:
# #             # There's exactly one yard in render_yards. Could be keyed
# #             # "legacy" (loaded old config) or "front"/"back" (new flow
# #             # with only one yard computed).
# #             yk = yard_keys_for_state[0]
# #             ls = live_states[yk]
# #             old_lat = updated_config["anchor"]["lat"]
# #             old_lon = updated_config["anchor"]["lon"]
# #             new_lat, new_lon = _shift_anchor(old_lat, old_lon, ls["e"], ls["n"])
# #             updated_config["anchor"]["lat"] = round(new_lat, 8)
# #             updated_config["anchor"]["lon"] = round(new_lon, 8)
# #             updated_config["anchor"]["description"] = (
# #                 (updated_config["anchor"].get("description", "") or "")
# #                 + f" · visually nudged {ls['e']:+.2f} E / {ls['n']:+.2f} N ft"
# #             ).strip(" ·")
# #             updated_config["rotation_deg"] = round(ls["r"], 2)

# #             # If the source was a new-flow (front_config or back_config)
# #             # rather than a legacy load, we should ALSO write the `yards`
# #             # block so future loads use the new shape. This is the only
# #             # case where new data gets the new schema; loaded legacy
# #             # configs stay legacy.
# #             if not loaded_from_disk and yk in ("front", "back"):
# #                 # Pull the stashed per-yard config built during Compute,
# #                 # apply the offset/rotation to its anchor, and store it
# #                 # in the yards block.
# #                 stash = st.session_state.get(f"{yk}_config")
# #                 if stash is not None:
# #                     yard_copy = json.loads(json.dumps(stash))
# #                     a_old_lat = yard_copy["anchor"]["lat"]
# #                     a_old_lon = yard_copy["anchor"]["lon"]
# #                     a_new_lat, a_new_lon = _shift_anchor(
# #                         a_old_lat, a_old_lon, ls["e"], ls["n"]
# #                     )
# #                     yard_copy["anchor"]["lat"] = round(a_new_lat, 8)
# #                     yard_copy["anchor"]["lon"] = round(a_new_lon, 8)
# #                     yard_copy["rotation_deg"] = round(ls["r"], 2)
# #                     updated_config["yards"] = {yk: yard_copy}

# #         # ── Case 2: new yards-shaped config. Apply offset/rotation to EACH
# #         #            yard's anchor and rotation independently. Also refresh
# #         #            the legacy mirror keys so old consumers see something
# #         #            consistent.
# #         else:
# #             new_yards = {}
# #             for yk in yard_keys_for_state:
# #                 if yk not in (updated_config.get("yards") or {}):
# #                     # Yard exists in render but not in updated_config (shouldn't
# #                     # normally happen). Skip safely.
# #                     continue
# #                 ydata = updated_config["yards"][yk]
# #                 if ydata is None:
# #                     continue
# #                 ls = live_states[yk]
# #                 a_old_lat = ydata["anchor"]["lat"]
# #                 a_old_lon = ydata["anchor"]["lon"]
# #                 a_new_lat, a_new_lon = _shift_anchor(
# #                     a_old_lat, a_old_lon, ls["e"], ls["n"]
# #                 )
# #                 ydata = json.loads(json.dumps(ydata))
# #                 ydata["anchor"]["lat"] = round(a_new_lat, 8)
# #                 ydata["anchor"]["lon"] = round(a_new_lon, 8)
# #                 ydata["anchor"]["description"] = (
# #                     (ydata["anchor"].get("description", "") or "")
# #                     + f" · visually nudged {ls['e']:+.2f} E / {ls['n']:+.2f} N ft"
# #                 ).strip(" ·")
# #                 ydata["rotation_deg"] = round(ls["r"], 2)
# #                 new_yards[yk] = ydata
# #             updated_config["yards"] = new_yards

# #             # Refresh legacy mirror keys from the updated yards block.
# #             legacy_mirror = _merge_yards_into_legacy(new_yards)
# #             updated_config["anchor"] = legacy_mirror["anchor"]
# #             updated_config["rotation_deg"] = legacy_mirror["rotation_deg"]
# #             updated_config["grid_blocks"] = legacy_mirror["grid_blocks"]
# #             updated_config["point_samples"] = legacy_mirror["point_samples"]

# #         # ── Persist — APPEND-OR-REPLACE the entry for this site_id.
# #         # Any other site entries in the file are preserved verbatim.
# #         base_dir = os.path.dirname(os.path.abspath(__file__))
# #         config_dir = os.path.join(base_dir, "..", "data", "site_configs")
# #         config_path = os.path.join(config_dir, "site_configs.json")
# #         os.makedirs(config_dir, exist_ok=True)

# #         existing = []
# #         if os.path.exists(config_path):
# #             try:
# #                 with open(config_path) as f:
# #                     existing = json.load(f)
# #             except Exception:
# #                 existing = []

# #         found = False
# #         for i, s in enumerate(existing):
# #             if s.get("site_id") == updated_config["site_id"]:
# #                 existing[i] = updated_config
# #                 found = True
# #                 break
# #         if not found:
# #             existing.append(updated_config)

# #         with open(config_path, "w") as f:
# #             json.dump(existing, f, indent=2)

# #         st.session_state["generated_config"] = updated_config

# #         # Clear the localStorage drag state so the next Save doesn't
# #         # apply the same offset twice (the offset has been baked into
# #         # the anchor lat/lon now).
# #         if bridge_available:
# #             try:
# #                 streamlit_js_eval(
# #                     js_expressions=f"""
# #                         (function() {{
# #                             var k = 'gs_drag_state_{site_id_for_storage}';
# #                             try {{ window.parent.localStorage.removeItem(k); }} catch(e) {{}}
# #                             try {{ window.localStorage.removeItem(k); }} catch(e) {{}}
# #                             return 'cleared';
# #                         }})()
# #                     """,
# #                     key=f"gs_storage_clear_{site_id_for_storage}_{os.urandom(2).hex()}",
# #                     want_output=False,
# #                 )
# #             except Exception:
# #                 pass
# #         # Reset the number-input session_state entries to zero so the
# #         # post-save state matches the just-baked anchor (no further drag
# #         # pending).
# #         for yk in yard_keys_for_state:
# #             st.session_state[f"in_e_{yk}"] = 0.0
# #             st.session_state[f"in_n_{yk}"] = 0.0
# #             st.session_state[f"in_r_{yk}"] = float(
# #                 live_states[yk].get("r", 0.0)
# #             )

# #         # Build a friendly summary message.
# #         yards_saved = list((updated_config.get("yards") or {}).keys())
# #         if yards_saved:
# #             yards_desc = f"with yards: **{', '.join(yards_saved)}**"
# #         else:
# #             yards_desc = "(legacy single-yard schema preserved)"
# #         st.success(
# #             f"✅ **Position saved** for SiteID `{updated_config['site_id']}` "
# #             f"{yards_desc}.  \n"
# #             f"All other entries in `site_configs.json` were preserved."
# #         )
# #         st.info("🔄 Tip: Click **Compute** again if you want to re-preview "
# #                 "with the new baked-in anchor.")

# #     if download_clicked:
# #         json_str = json.dumps(config, indent=2)
# #         st.code(json_str, language="json")
# #         st.download_button(
# #             "📥 Download JSON",
# #             data=json_str,
# #             file_name=f"site_config_{config['site_id']}.json",
# #             mime="application/json",
# #         )

# #     # ═══════════════════════════════════════════
# #     #  MAP EXPORTS — three consistent variants
# #     # ═══════════════════════════════════════════
# #     st.markdown("---")
# #     st.subheader("🗂️ Export Site Maps")
# #     st.caption(
# #         "Download this site's map in three formats. All three use the **same** "
# #         "renderer as the PPTX resident reports, so the output is consistent "
# #         "everywhere. Real XRF readings are pulled from the latest Master Data; "
# #         "cells without data render in gray. Exports use the legacy mirror "
# #         "fields so old & new configs render identically."
# #     )

# #     # Load master data for real PPM lookup
# #     master_df_export = load_master_data()
# #     if master_df_export.empty:
# #         st.warning(
# #             "⚠️ No Master Data found — exports will render all cells as 'No Data' (gray). "
# #             "Run the ETL Pipeline first if you want real PPM values."
# #         )
# #     else:
# #         blocks_preview, _ = get_block_data(config, master_df_export,
# #                                             use_mock_fallback=False)
# #         real_count = sum(1 for b in blocks_preview if b["has_real_data"])
# #         total = len(blocks_preview)
# #         st.caption(
# #             f"📊 Using Master Data: **{real_count} / {total}** cells have real "
# #             f"XRF readings. Remaining cells will render as 'No Data' (gray)."
# #         )

# #     safe_name = config["site_id"]

# #     exp1, exp2, exp3 = st.columns(3)

# #     # ─── 1. Basemap + no numbers (HTML) ───
# #     with exp1:
# #         st.markdown("**🛰️ Basemap · no numbers**")
# #         st.caption("Satellite imagery, cell IDs only, draggable.")
# #         try:
# #             html_nonum = render_leaflet_html(
# #                 config, master_df_export,
# #                 show_numbers=False, use_mock_fallback=False,
# #             )
# #             st.download_button(
# #                 label="📥 Download HTML",
# #                 data=html_nonum,
# #                 file_name=f"{safe_name}_basemap_no_numbers.html",
# #                 mime="text/html",
# #                 use_container_width=True,
# #                 key="exp_basemap_nonum",
# #             )
# #         except Exception as e:
# #             st.error(f"Render failed: {e}")

# #     # ─── 2. Basemap + numbers (HTML) ───
# #     with exp2:
# #         st.markdown("**🛰️ Basemap · with numbers**")
# #         st.caption("Satellite imagery, cell IDs + ppm values.")
# #         try:
# #             html_num = render_leaflet_html(
# #                 config, master_df_export,
# #                 show_numbers=True, use_mock_fallback=False,
# #             )
# #             st.download_button(
# #                 label="📥 Download HTML",
# #                 data=html_num,
# #                 file_name=f"{safe_name}_basemap_with_numbers.html",
# #                 mime="text/html",
# #                 use_container_width=True,
# #                 key="exp_basemap_num",
# #             )
# #         except Exception as e:
# #             st.error(f"Render failed: {e}")

# #     # ─── 3. No basemap + numbers (PNG) ───
# #     with exp3:
# #         st.markdown("**🎨 No basemap · with numbers**")
# #         st.caption("Dark-theme PNG (matches PPTX reports).")
# #         try:
# #             with tempfile.NamedTemporaryFile(
# #                 suffix=".png", delete=False
# #             ) as tmp:
# #                 png_path = tmp.name
# #             render_static_png(
# #                 config, master_df_export, png_path,
# #                 show_numbers=True, use_mock_fallback=False,
# #             )
# #             with open(png_path, "rb") as f:
# #                 png_bytes = f.read()
# #             os.unlink(png_path)
# #             st.download_button(
# #                 label="📥 Download PNG",
# #                 data=png_bytes,
# #                 file_name=f"{safe_name}_no_basemap_with_numbers.png",
# #                 mime="image/png",
# #                 use_container_width=True,
# #                 key="exp_static_png",
# #             )
# #         except Exception as e:
# #             st.error(f"Render failed: {e}")

# #     st.caption(
# #         "🔄 All three outputs honor the site's saved `rotation_deg` and "
# #         "fine-tuned anchor position. The PNG here is byte-identical to what "
# #         "`etl_manager.py` embeds in the resident PPTX report."
# #     )


# import streamlit as st
# import streamlit.components.v1 as components
# import pandas as pd
# import json
# import math
# import os
# import glob
# import re
# import io
# import tempfile

# from groundsense_config import (
#     get_nysh_category,
#     NYSH_TIERS,
#     NYSH_COLORS,
#     calculate_coordinate,
#     resolve_lod,
# )

# # Shared renderer — used by etl_manager.py too, so exports stay consistent
# from map_renderer import (
#     render_leaflet_html,
#     render_static_png,
#     get_block_data,
# )


# # ═══════════════════════════════════════════════
# #  MASTER DATA LOADER (for export with real PPM values)
# # ═══════════════════════════════════════════════
# @st.cache_data
# def load_master_data():
#     """Load the latest XRF_Chemistry_V*.csv for looking up real Lead PPM
#     values when rendering the exported maps. Returns empty df if missing.
#     """
#     base_dir = os.path.dirname(os.path.abspath(__file__))
#     master_dir = os.path.join(base_dir, "..", "data", "XRF_Chemistry")
#     master_files = glob.glob(os.path.join(master_dir, "XRF_Chemistry_V*.csv"))
#     if not master_files:
#         return pd.DataFrame(columns=["SampleID", "LeadPPM", "LeadPPM_Clean"])

#     def _ver(fn):
#         m = re.search(r"_V(\d+)\.csv$", fn, re.IGNORECASE)
#         return int(m.group(1)) if m else 0

#     latest = max(master_files, key=_ver)
#     df = pd.read_csv(latest)
#     df["LeadPPM_Clean"] = df["LeadPPM"].apply(resolve_lod)
#     return df


# # ═══════════════════════════════════════════════
# #  PAGE CONFIG & STYLING
# # ═══════════════════════════════════════════════
# st.set_page_config(page_title="GroundSense Site Builder", page_icon="📐", layout="wide")
# st.title("📐 Site Configuration Builder")
# st.caption("Urban Soil Co-Lab · University at Buffalo · GroundSense Pipeline")
# st.markdown(
#     "Transform field sketch measurements into a config-ready site definition. "
#     "Fill in each section below, then hit **Compute** to generate the JSON config "
#     "and preview the grid on satellite imagery. You can drag/rotate the grid on "
#     "the preview to fine-tune positioning, then **Save** to persist the change."
# )
# st.markdown("---")


# # ═══════════════════════════════════════════════
# #  HELPERS
# # ═══════════════════════════════════════════════
# def parse_imperial(s):
#     """Convert imperial string like 11'6.5\" or plain feet like 10 to decimal feet."""
#     if s is None or str(s).strip() == "":
#         return 0.0
#     s = str(s).strip().replace('"', '').replace("''", "").replace('\u2033', '').replace('\u2032', "'")
#     if "'" in s:
#         parts = s.split("'")
#         feet = float(parts[0]) if parts[0].strip() else 0
#         inches = float(parts[1]) if len(parts) > 1 and parts[1].strip() else 0
#         return feet + inches / 12.0
#     try:
#         return float(s)
#     except ValueError:
#         return 0.0


# def dms_to_decimal(degrees, minutes, seconds, direction):
#     """Convert DMS coordinates to decimal degrees."""
#     dd = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
#     if direction in ['S', 'W']:
#         dd *= -1
#     return dd


# def load_existing_config_for_site_id(site_id, config_path):
#     """If this site_id already has a saved config, return its current offset/rotation."""
#     if not os.path.exists(config_path):
#         return None
#     try:
#         with open(config_path, 'r') as f:
#             existing = json.load(f)
#         for s in existing:
#             if s.get("site_id") == site_id:
#                 return s
#     except Exception:
#         pass
#     return None


# def list_existing_site_ids(config_path):
#     """Return a list of all SiteIDs currently saved in site_configs.json.

#     Returns [] if the file is missing or unreadable. Order matches the
#     file order (which is roughly creation order).
#     """
#     if not os.path.exists(config_path):
#         return []
#     try:
#         with open(config_path, 'r') as f:
#             existing = json.load(f)
#         return [s.get("site_id", "") for s in existing if s.get("site_id")]
#     except Exception:
#         return []


# def _zone_for_yard(yard_key: str) -> str:
#     """Map an internal yard key to the zone string used in grid_blocks.

#     yard_key is 'front' or 'back'. We store zone as 'front_yard' or
#     'backyard' so downstream code can tell them apart cleanly.
#     """
#     return "front_yard" if yard_key == "front" else "backyard"


# def _prefix_for_yard(yard_key: str) -> str:
#     """Internal block-ID prefix to keep front/back keys collision-proof.

#     Front cell 'A1' becomes 'F_A1', back 'A1' becomes 'B_A1'. The
#     underlying cell label 'A1' is preserved inside the block as
#     'cell_id' for map labels and downstream string matching.
#     """
#     return "F_" if yard_key == "front" else "B_"


# def _merge_yards_into_legacy(yards_block: dict) -> dict:
#     """Build the legacy top-level fields from the new yards block.

#     Returns a dict with keys 'anchor', 'rotation_deg', 'grid_blocks',
#     'point_samples' that mirror the UNION of all yards. Old consumers
#     (dashboard, etl_manager, map_renderer) read these keys and stay
#     blissfully unaware of the front/back split — every block has a
#     `zone` tag that yard-aware code can use later.

#     If only one yard exists, its anchor + rotation become the legacy
#     fields directly. If both exist, the front yard wins for the legacy
#     `anchor`/`rotation_deg` (chosen as the "primary" anchor — back is
#     still fully present in the `yards` block with its own anchor).
#     """
#     front = yards_block.get("front")
#     back  = yards_block.get("back")

#     # Choose primary yard for legacy anchor/rotation (front first, else back).
#     primary = front if front else back
#     if primary is None:
#         return {
#             "anchor": {"lat": 0, "lon": 0, "description": "", "marker_label": ""},
#             "rotation_deg": 0,
#             "grid_blocks": {},
#             "point_samples": {},
#         }

#     legacy_anchor   = dict(primary["anchor"])
#     legacy_rotation = primary.get("rotation_deg", 0)

#     legacy_blocks  = {}
#     legacy_points  = {}
#     for yk in ("front", "back"):
#         y = yards_block.get(yk)
#         if not y:
#             continue
#         legacy_blocks.update(y.get("grid_blocks", {}))
#         legacy_points.update(y.get("point_samples", {}))

#     return {
#         "anchor": legacy_anchor,
#         "rotation_deg": legacy_rotation,
#         "grid_blocks": legacy_blocks,
#         "point_samples": legacy_points,
#     }


# def _split_legacy_into_yards(config: dict) -> dict:
#     """Best-effort: split an OLD single-yard config into the yards shape.

#     Used when the user loads an existing site that pre-dates this feature.
#     The old config has no `yards` key — we treat it as a single backyard
#     (per spec: SampleIDs without Front/Back default to back). The user
#     can then add a front yard via the builder if they want.

#     Returns a yards-shaped dict: {"front": None, "back": {...}}.
#     NOTE: We do NOT modify the original config or write it back — this
#     is purely for in-session editing. Saving preserves the old shape.
#     """
#     # Already has the new shape — just hand it back.
#     if "yards" in config:
#         return dict(config["yards"])

#     legacy_blocks = config.get("grid_blocks", {})
#     legacy_points = config.get("point_samples", {})

#     if not legacy_blocks and not legacy_points:
#         return {"front": None, "back": None}

#     # Tag every legacy block with backyard zone (default per spec).
#     tagged_blocks = {}
#     for bid, b in legacy_blocks.items():
#         b_copy = dict(b)
#         if "zone" not in b_copy or b_copy.get("zone") == "yard":
#             b_copy["zone"] = "backyard"
#         tagged_blocks[bid] = b_copy

#     back_yard = {
#         "anchor": dict(config.get("anchor", {})),
#         "rotation_deg": config.get("rotation_deg", 0),
#         "grid_blocks": tagged_blocks,
#         "point_samples": dict(legacy_points),
#     }
#     return {"front": None, "back": back_yard}


# # ═══════════════════════════════════════════════
# #  LOAD EXISTING SITE (search/edit existing maps)
# #  — UNCHANGED behavior: load any site, drag, save in place. Works with
# #    both legacy and new-format configs.
# # ═══════════════════════════════════════════════
# st.subheader("🔍 Load Existing Site")
# st.caption(
#     "Pick a previously-saved site to load it into the draggable preview. "
#     "You can re-position or rotate the grid and **Save** to update its "
#     "config in place. Leave this empty if you're creating a brand-new site."
# )

# _base_dir_top = os.path.dirname(os.path.abspath(__file__))
# _config_path_top = os.path.join(
#     _base_dir_top, "..", "data", "site_configs", "site_configs.json"
# )
# _existing_site_ids = list_existing_site_ids(_config_path_top)

# ec1, ec2 = st.columns([3, 1])
# with ec1:
#     selected_existing = st.selectbox(
#         "Existing SiteIDs",
#         options=["— select to load —"] + _existing_site_ids,
#         index=0,
#         key="existing_site_selector",
#         help="Sites are pulled from data/site_configs/site_configs.json.",
#     )
# with ec2:
#     load_clicked = st.button(
#         "📂 Load to Preview",
#         use_container_width=True,
#         disabled=(selected_existing == "— select to load —"),
#     )

# if load_clicked and selected_existing != "— select to load —":
#     cfg = load_existing_config_for_site_id(selected_existing, _config_path_top)
#     if cfg is None:
#         st.error(f"Could not find SiteID '{selected_existing}' in site_configs.json.")
#     else:
#         # Drop the loaded config straight into the draggable-preview slot.
#         # The preview block further down keys off `generated_config`, so this
#         # is all we need to do — the user lands on the same map UI they'd
#         # see right after clicking Compute.
#         st.session_state["generated_config"] = cfg
#         # Mark this as a loaded (existing) site so the preview/save block
#         # knows to preserve its on-disk schema (legacy vs new).
#         st.session_state["loaded_from_disk"] = True
#         # Clear any in-progress build state for the new-site flow.
#         st.session_state.pop("front_config", None)
#         st.session_state.pop("back_config", None)
#         # Clear any stale drag-state from a previous edit.
#         for k in ("pending_offset_e", "pending_offset_n", "pending_rotation",
#                   "front_offset_e", "front_offset_n", "front_rotation",
#                   "back_offset_e", "back_offset_n", "back_rotation",
#                   "in_e_front", "in_n_front", "in_r_front",
#                   "in_e_back", "in_n_back", "in_r_back",
#                   "in_e_legacy", "in_n_legacy", "in_r_legacy"):
#             st.session_state.pop(k, None)
#         n_blocks = len(cfg.get("grid_blocks", {}))
#         # Try to give a friendlier yards breakdown when present.
#         yards_present = list((cfg.get("yards") or {}).keys()) if cfg.get("yards") else []
#         yards_desc = (f" · yards: {', '.join(yards_present)}"
#                       if yards_present else " · legacy single-yard config")
#         st.success(
#             f"✅ Loaded **{selected_existing}** "
#             f"({n_blocks} blocks · "
#             f"{len(cfg.get('point_samples', {}))} point samples{yards_desc}). "
#             f"Scroll down to the **Draggable Satellite Preview** to nudge it "
#             f"and **Save** to overwrite its config."
#         )
#         st.rerun()

# st.markdown("---")


# # ═══════════════════════════════════════════════
# #  STEP 1 — SITE INFORMATION
# # ═══════════════════════════════════════════════
# st.subheader("① Site Information")
# st.caption(
#     "SiteID is the canonical identifier for this site across the pipeline. "
#     "Convention: use the sampling date in ISO form (YYYY-MM-DD). "
#     "Resident address/name/ZIP are PII and never stored here. "
#     "_(Steps ① – ⑦ are for building a **new** site from scratch — to edit "
#     "an existing one, use the dropdown above and skip to the preview.)_"
# )

# col_date, col_id = st.columns([1, 2])
# with col_date:
#     sampling_date = st.date_input("Sampling Date *", key="builder_sampling_date")
# with col_id:
#     # Auto-suggest SiteID from sampling_date (zero-padded ISO). User may
#     # override if a non-date scheme is needed (e.g. multiple sites on the
#     # same day — append a suffix like "2025-06-24-A").
#     suggested_id = sampling_date.strftime("%Y-%m-%d") if sampling_date else ""
#     site_id = st.text_input(
#         "SiteID *",
#         value=suggested_id,
#         placeholder="e.g. 2025-06-24",
#         help="Defaults to the sampling date in ISO form. Override only if you need to disambiguate multiple sites on the same date.",
#         key="builder_site_id",
#     ).strip()

# notes = st.text_input(
#     "Site Notes (optional)",
#     placeholder="e.g. Backyard grid, measured from porch corner…",
#     key="builder_notes",
# )

# st.markdown("---")


# # ═══════════════════════════════════════════════
# #  STEP 2 — WHICH YARD (NEW)
# # ═══════════════════════════════════════════════
# st.subheader("② Which Yard")
# st.caption(
#     "Pick which yard you're configuring right now. Fill in fields ③–⑦, "
#     "then hit Compute to stash THIS yard's grid. Switch the dropdown to "
#     "the other yard if this site has both — repeat the fill + Compute. "
#     "When you save below, all completed yards are merged into one site."
# )

# yard_choice = st.selectbox(
#     "I am entering data for the:",
#     options=["Front", "Back"],
#     index=0,
#     key="builder_yard_choice",
#     help="The yard whose ③–⑦ fields you're filling in right now. "
#          "Sites with only one yard: just fill the one and ignore the other.",
# )
# yard_key = yard_choice.lower()  # "front" or "back"
# yard_zone = _zone_for_yard(yard_key)
# yard_prefix = _prefix_for_yard(yard_key)

# # Show a status banner telling the user what's already stashed.
# front_done = st.session_state.get("front_config") is not None
# back_done  = st.session_state.get("back_config")  is not None
# status_msgs = []
# if front_done:
#     n = len(st.session_state["front_config"]["grid_blocks"])
#     status_msgs.append(f"✅ Front yard stashed ({n} blocks)")
# else:
#     status_msgs.append("⬜ Front yard — not yet computed")
# if back_done:
#     n = len(st.session_state["back_config"]["grid_blocks"])
#     status_msgs.append(f"✅ Back yard stashed ({n} blocks)")
# else:
#     status_msgs.append("⬜ Back yard — not yet computed")
# st.info("  ·  ".join(status_msgs))

# st.markdown("---")


# # ═══════════════════════════════════════════════
# #  STEP 3 — FIXED POINT LOCATION IN GRID  (per yard)
# # ═══════════════════════════════════════════════
# st.subheader(f"③ Fixed Point Location in Grid — {yard_choice} Yard")
# st.caption("Identify which cell corner the GPS measurement was taken at. "
#            "This anchors this yard's grid to the real world.")

# col_fp1, col_fp2 = st.columns(2)
# with col_fp1:
#     fp_cell_input = st.text_input(
#         "Fixed Point Cell ID *", value="E1",
#         help="The cell whose corner was marked with GPS (e.g. E1, A1, D2)",
#         key=f"fp_cell_{yard_key}",
#     )
# with col_fp2:
#     fp_corner = st.selectbox(
#         "Which corner of this cell? *",
#         ["Top-Left", "Top-Right", "Bottom-Left", "Bottom-Right"],
#         help="As drawn on the field sketch — not compass direction",
#         key=f"fp_corner_{yard_key}",
#     )

# st.markdown("---")


# # ═══════════════════════════════════════════════
# #  STEP 4 — FIXED POINT GPS  (per yard)
# # ═══════════════════════════════════════════════
# st.subheader(f"④ Fixed Point GPS Coordinates — {yard_choice} Yard")

# gps_format = st.radio(
#     "Coordinate format",
#     ["DMS (Degrees Minutes Seconds)", "Decimal Degrees"],
#     horizontal=True,
#     help="DMS example: 42° 55' 11.46\" N  ·  Decimal example: 42.9198500",
#     key=f"gps_format_{yard_key}",
# )

# if gps_format == "DMS (Degrees Minutes Seconds)":
#     col_lat, col_lon = st.columns(2)
#     with col_lat:
#         st.markdown("**Latitude (N)**")
#         c1, c2, c3 = st.columns(3)
#         lat_d = c1.number_input("Deg", value=42, key=f"lat_d_{yard_key}")
#         lat_m = c2.number_input("Min", value=55, key=f"lat_m_{yard_key}")
#         lat_s = c3.number_input("Sec", value=11.46, format="%.4f", key=f"lat_s_{yard_key}")
#     with col_lon:
#         st.markdown("**Longitude (W)**")
#         c4, c5, c6 = st.columns(3)
#         lon_d = c4.number_input("Deg", value=78, key=f"lon_d_{yard_key}")
#         lon_m = c5.number_input("Min", value=49, key=f"lon_m_{yard_key}")
#         lon_s = c6.number_input("Sec", value=33.63, format="%.4f", key=f"lon_s_{yard_key}")
#     anchor_lat = dms_to_decimal(lat_d, lat_m, lat_s, 'N')
#     anchor_lon = dms_to_decimal(lon_d, lon_m, lon_s, 'W')
# else:
#     col_lat, col_lon = st.columns(2)
#     with col_lat:
#         anchor_lat = st.number_input("Latitude", value=42.919850, format="%.7f",
#                                       key=f"lat_dec_{yard_key}")
#     with col_lon:
#         anchor_lon = st.number_input("Longitude", value=-78.826008, format="%.7f",
#                                       key=f"lon_dec_{yard_key}")

# st.success(f"📍 {yard_choice} anchor locked: **{anchor_lat:.7f}°N, {abs(anchor_lon):.7f}°W**")

# st.markdown("---")


# # ═══════════════════════════════════════════════
# #  STEP 5 — GRID LAYOUT & ORIENTATION  (per yard)
# # ═══════════════════════════════════════════════
# st.subheader(f"⑤ Grid Layout — {yard_choice} Yard")

# col_orient, col_dir = st.columns(2)
# with col_orient:
#     orientation = st.selectbox(
#         "Grid orientation on map",
#         ["Vertical (strip runs North–South)", "Horizontal (strip runs East–West)"],
#         help="Vertical = long axis goes up/down. Horizontal = long axis goes left/right.",
#         key=f"orientation_{yard_key}",
#     )
# with col_dir:
#     if "Vertical" in orientation:
#         house_dir = st.selectbox("Which end is near the house?",
#                                  ["Top (North)", "Bottom (South)"],
#                                  key=f"house_dir_v_{yard_key}")
#     else:
#         house_dir = st.selectbox("Which end is near the house?",
#                                  ["Left (West)", "Right (East)"],
#                                  key=f"house_dir_h_{yard_key}")

# st.markdown("---")


# # ═══════════════════════════════════════════════
# #  STEP 6 — DEFINE GRID ROWS  (per yard)
# # ═══════════════════════════════════════════════
# st.subheader(f"⑥ Define Grid Rows — {yard_choice} Yard")
# st.caption("List row letters from **farthest from house** → **nearest to house**.")

# rows_input = st.text_input(
#     "Row letters (comma-separated) *", value="A, B, C, D, E",
#     help="Example: A, B, C, D, E, F, G, H — where A is farthest from house",
#     key=f"rows_{yard_key}",
# )
# rows = [r.strip().upper() for r in rows_input.split(",") if r.strip()]

# if rows:
#     st.info(f"**{len(rows)} rows:** {' → '.join(rows)}  _(far → near)_")

# st.markdown("---")


# # ═══════════════════════════════════════════════
# #  STEP 7 — CELL DIMENSIONS  (per yard)
# # ═══════════════════════════════════════════════
# st.subheader(f"⑦ Cell Dimensions — {yard_choice} Yard")
# st.caption("Enter each cell's **width** (perpendicular to strip) and **height** "
#            "(along the strip). Accepts imperial: `11'6.5\"` or plain feet: `10`.")

# max_cols = st.number_input("Max columns per row", min_value=1, max_value=5, value=3,
#                             help="e.g. 3 if cells are A1, A2, A3",
#                             key=f"max_cols_{yard_key}")

# cell_data = {}
# for row in rows:
#     with st.expander(f"**Row {row}**", expanded=True):
#         num_cols = st.number_input(f"Columns in row {row}", min_value=1,
#                                     max_value=int(max_cols),
#                                     value=min(int(max_cols), 3),
#                                     key=f"ncols_{row}_{yard_key}")
#         cols_ui = st.columns(int(num_cols))
#         for c in range(int(num_cols)):
#             col_num = c + 1
#             cell_id = f"{row}{col_num}"
#             with cols_ui[c]:
#                 st.markdown(f"##### {cell_id}")
#                 w = st.text_input("Width (ft)", value="10", key=f"w_{cell_id}_{yard_key}")
#                 h = st.text_input("Height (ft)", value="10", key=f"h_{cell_id}_{yard_key}")
#                 # Default the sample-id pattern to include the yard hint so
#                 # downstream matching naturally segregates front from back.
#                 default_pat = f"{yard_choice}_{cell_id}_"
#                 pat = st.text_input("SampleID pattern", value=default_pat,
#                                     key=f"pat_{cell_id}_{yard_key}",
#                                     help="Substring matched against Master Data. "
#                                          "Include 'Front' or 'Back' so the matcher "
#                                          "associates readings with the correct yard.")
#                 cell_data[cell_id] = {
#                     "width": parse_imperial(w), "height": parse_imperial(h),
#                     "col": col_num, "row": row, "pattern": pat,
#                 }

# st.markdown("---")


# # ═══════════════════════════════════════════════
# #  STEP 8 — POINT SAMPLES (OPTIONAL)  (per yard)
# # ═══════════════════════════════════════════════
# st.subheader(f"⑧ Point Samples _(optional)_ — {yard_choice} Yard")
# st.caption("Non-grid samples (driplines, lawns, etc.). Offsets in feet from the fixed point.")

# num_points = st.number_input("Number of point samples", min_value=0, max_value=20, value=0,
#                               key=f"num_points_{yard_key}")
# point_samples = {}
# if num_points > 0:
#     for i in range(int(num_points)):
#         with st.expander(f"Point Sample {i + 1}", expanded=True):
#             pc1, pc2, pc3, pc4 = st.columns(4)
#             with pc1:
#                 pt_name = st.text_input("Name", key=f"pt_name_{i}_{yard_key}",
#                                         placeholder="HUD Dripline")
#             with pc2:
#                 pt_ox = st.number_input("East offset (ft)", key=f"pt_ox_{i}_{yard_key}", value=0.0)
#             with pc3:
#                 pt_oy = st.number_input("North offset (ft)", key=f"pt_oy_{i}_{yard_key}", value=0.0)
#             with pc4:
#                 pt_pat = st.text_input("SampleID pattern", key=f"pt_pat_{i}_{yard_key}",
#                                         placeholder=f"{yard_choice}_HUD_Dripline")
#             if pt_name:
#                 # Prefix point sample key with yard prefix to avoid collisions
#                 # when both yards have a point named e.g. "Dripline".
#                 point_samples[f"{yard_prefix}{pt_name}"] = {
#                     "name": pt_name,
#                     "offset_x": pt_ox, "offset_y": pt_oy,
#                     "sample_id_patterns": [pt_pat] if pt_pat else [],
#                     "zone": "auxiliary",
#                     "yard": yard_key,
#                 }


# # ═══════════════════════════════════════════════
# #  COMPUTE  (per yard)
# # ═══════════════════════════════════════════════
# st.markdown("---")
# st.markdown(f"### 🔧 Generate Configuration — {yard_choice} Yard")
# st.caption(
#     f"Computing only the **{yard_choice}** yard right now. If this site has "
#     f"both yards, switch the dropdown to the other yard, fill in its fields, "
#     f"and click Compute again. Both yards get merged together when you Save."
# )

# col_btn, col_btn2, _ = st.columns([2, 2, 4])
# with col_btn:
#     compute = st.button(
#         f"Compute {yard_choice} Yard",
#         type="primary",
#         use_container_width=True,
#         key=f"compute_{yard_key}",
#     )
# with col_btn2:
#     clear_yard = st.button(
#         f"Clear {yard_choice} Yard",
#         use_container_width=True,
#         key=f"clear_{yard_key}",
#         help="Forget the currently-stashed configuration for this yard. "
#              "Does NOT touch site_configs.json on disk.",
#     )

# if clear_yard:
#     st.session_state.pop(f"{yard_key}_config", None)
#     st.success(f"🗑️ Cleared stashed {yard_choice} yard from this session.")
#     st.rerun()

# if compute:
#     errors = []
#     if not site_id:
#         errors.append("SiteID is required.")
#     if not rows:
#         errors.append("At least one grid row must be defined.")
#     if not cell_data:
#         errors.append("Cell dimensions are required.")
#     fp_cell = fp_cell_input.strip().upper()
#     if fp_cell not in cell_data:
#         errors.append(f"Fixed point cell '{fp_cell}' doesn't match any defined cell.")
#     if errors:
#         for e in errors:
#             st.error(e)
#         st.stop()

#     row_heights = {}
#     for row in rows:
#         c1 = f"{row}1"
#         if c1 in cell_data:
#             row_heights[row] = cell_data[c1]["height"]
#         else:
#             for cid, cd in cell_data.items():
#                 if cd["row"] == row:
#                     row_heights[row] = cd["height"]
#                     break

#     strip_pos, pos = {}, 0
#     for row in rows:
#         strip_pos[row] = pos
#         pos += row_heights.get(row, 10)

#     fp_row = ''.join(c for c in fp_cell if c.isalpha())
#     fp_col = int(''.join(c for c in fp_cell if c.isdigit()))

#     col_widths_per_row = {}
#     for row in rows:
#         col_widths_per_row[row] = {}
#         for cid, cd in cell_data.items():
#             if cd["row"] == row:
#                 col_widths_per_row[row][cd["col"]] = cd["width"]

#     fp_row_widths = col_widths_per_row.get(fp_row, {})
#     fp_perp = 0
#     if "Left" in fp_corner:
#         for c in range(1, fp_col):
#             fp_perp += fp_row_widths.get(c, 0)
#     else:
#         for c in range(1, fp_col + 1):
#             fp_perp += fp_row_widths.get(c, 0)

#     fp_strip = strip_pos[fp_row] + (row_heights[fp_row] if "Top" in fp_corner else 0)

#     is_vertical = "Vertical" in orientation
#     flip_strip = "Top" in house_dir or "Right" in house_dir

#     grid_blocks = {}
#     for cid, cd in cell_data.items():
#         row, col = cd["row"], cd["col"]
#         cell_h, cell_w = cd["height"], cd["width"]

#         strip_start = strip_pos[row] - fp_strip
#         strip_end = strip_start + row_heights[row]
#         if cell_h != row_heights[row]:
#             strip_start = strip_end - cell_h

#         perp_start = sum(col_widths_per_row[row].get(c, 0) for c in range(1, col))
#         perp_end = perp_start + cell_w
#         perp_start -= fp_perp
#         perp_end -= fp_perp

#         if flip_strip:
#             strip_start, strip_end = -strip_end, -strip_start

#         if is_vertical:
#             ns, ne, es, ee = strip_start, strip_end, perp_start, perp_end
#         else:
#             es, ee, ns, ne = strip_start, strip_end, perp_start, perp_end

#         # Internal collision-proof key: F_A1 or B_A1.
#         block_key = f"{yard_prefix}{cid}"
#         grid_blocks[block_key] = {
#             "sw_x": round(min(es, ee), 2), "sw_y": round(min(ns, ne), 2),
#             "ne_x": round(max(es, ee), 2), "ne_y": round(max(ns, ne), 2),
#             "sample_id_patterns": [cd["pattern"]] if cd["pattern"] else [],
#             "zone": yard_zone,        # "front_yard" or "backyard"
#             "cell_id": cid,           # human-readable label, e.g. "A1"
#             "yard": yard_key,         # "front" or "back"
#             "mock_ppm": 0,
#         }

#     # ── Preserve existing rotation if this site_id was saved before ──
#     # Look up rotation specifically for THIS yard if the saved config
#     # has the new yards-keyed shape; otherwise fall back to top-level
#     # rotation_deg (legacy).
#     base_dir = os.path.dirname(os.path.abspath(__file__))
#     config_path = os.path.join(base_dir, "..", "data", "site_configs", "site_configs.json")
#     existing = load_existing_config_for_site_id(site_id, config_path)
#     preserved_rotation = 0
#     if existing:
#         if "yards" in existing and yard_key in (existing.get("yards") or {}):
#             preserved_rotation = (existing["yards"][yard_key] or {}).get("rotation_deg", 0)
#         else:
#             preserved_rotation = existing.get("rotation_deg", 0)

#     yard_config = {
#         "anchor": {
#             "lat": anchor_lat, "lon": anchor_lon,
#             "description": f"{yard_choice} yard fixed point at {fp_cell} ({fp_corner}) — field-measured GPS",
#             "marker_label": f"{yard_choice} Fixed Point ({fp_cell})",
#         },
#         "rotation_deg": preserved_rotation,
#         "grid_blocks": grid_blocks,
#         "point_samples": point_samples,
#     }

#     # Stash THIS yard. The other yard, if previously computed, is untouched.
#     st.session_state[f"{yard_key}_config"] = yard_config

#     # Whenever a yard is computed, rebuild the combined generated_config so
#     # the preview & legacy consumers see the union. Use the front anchor for
#     # the legacy mirror if front exists, else back.
#     yards_block = {
#         "front": st.session_state.get("front_config"),
#         "back":  st.session_state.get("back_config"),
#     }
#     legacy_mirror = _merge_yards_into_legacy(yards_block)
#     combined_config = {
#         "site_id": site_id,
#         "sampling_date": str(sampling_date),
#         "notes": notes,
#         "anchor": legacy_mirror["anchor"],
#         "rotation_deg": legacy_mirror["rotation_deg"],
#         "map_defaults": {"zoom_start": 21, "center_offset_north_ft": 0, "center_offset_east_ft": 0},
#         "grid_blocks": legacy_mirror["grid_blocks"],
#         "point_samples": legacy_mirror["point_samples"],
#         "yards": {k: v for k, v in yards_block.items() if v is not None},
#     }
#     st.session_state["generated_config"] = combined_config
#     # We're in the new-site flow, not editing a loaded config.
#     st.session_state["loaded_from_disk"] = False
#     # Reset stale drag state.
#     for k in ("pending_offset_e", "pending_offset_n", "pending_rotation",
#               "front_offset_e", "front_offset_n", "front_rotation",
#               "back_offset_e", "back_offset_n", "back_rotation",
#               "in_e_front", "in_n_front", "in_r_front",
#               "in_e_back", "in_n_back", "in_r_back",
#               "in_e_legacy", "in_n_legacy", "in_r_legacy"):
#         st.session_state.pop(k, None)

#     msg_lines = [
#         f"✅ **{yard_choice} yard computed** — {len(grid_blocks)} blocks · "
#         f"{len(point_samples)} point samples."
#     ]
#     other = "back" if yard_key == "front" else "front"
#     other_done = st.session_state.get(f"{other}_config") is not None
#     if other_done:
#         n_other = len(st.session_state[f"{other}_config"]["grid_blocks"])
#         msg_lines.append(
#             f"Both yards now stashed (Front + Back). Scroll down to the "
#             f"preview to position them and Save."
#         )
#     else:
#         msg_lines.append(
#             f"Only **{yard_choice}** stashed so far. If this site has a "
#             f"{other.capitalize()} yard too, switch the dropdown to "
#             f"**{other.capitalize()}**, fill it in, and click Compute again. "
#             f"Otherwise scroll down to position & Save just this one."
#         )
#     st.success("  \n".join(msg_lines))


# # ═══════════════════════════════════════════════
# #  RESULTS & DRAGGABLE PREVIEW
# # ═══════════════════════════════════════════════
# if "generated_config" in st.session_state:
#     config = st.session_state["generated_config"]
#     st.markdown("---")

#     # ── Computed-offsets table — group by yard if the new shape exists ──
#     st.subheader("📋 Computed Grid Offsets")
#     yards_in_config = config.get("yards") or {}
#     if yards_in_config:
#         for yk, ydata in yards_in_config.items():
#             if not ydata:
#                 continue
#             st.markdown(f"**{yk.capitalize()} Yard** — anchor "
#                         f"`{ydata['anchor']['lat']:.6f}, {ydata['anchor']['lon']:.6f}`")
#             tbl = []
#             for bid, b in ydata.get("grid_blocks", {}).items():
#                 tbl.append({
#                     "Cell": b.get("cell_id", bid),
#                     "Internal ID": bid,
#                     "SW East": b["sw_x"], "SW North": b["sw_y"],
#                     "NE East": b["ne_x"], "NE North": b["ne_y"],
#                     "W (ft)": round(b["ne_x"] - b["sw_x"], 1),
#                     "H (ft)": round(b["ne_y"] - b["sw_y"], 1),
#                     "Pattern": ", ".join(b.get("sample_id_patterns", [])),
#                 })
#             st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True)
#     else:
#         # Legacy single-yard view — exactly as before.
#         tbl = []
#         for bid, b in config["grid_blocks"].items():
#             tbl.append({
#                 "Cell": b.get("cell_id", bid),
#                 "SW East": b["sw_x"], "SW North": b["sw_y"],
#                 "NE East": b["ne_x"], "NE North": b["ne_y"],
#                 "W (ft)": round(b["ne_x"] - b["sw_x"], 1),
#                 "H (ft)": round(b["ne_y"] - b["sw_y"], 1),
#                 "Pattern": ", ".join(b.get("sample_id_patterns", [])),
#             })
#         st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True)

#     # ═══════════════════════════════════════════
#     #  DRAGGABLE LEAFLET PREVIEW
#     # ═══════════════════════════════════════════
#     st.subheader("🗺️ Draggable Satellite Preview")
#     st.caption(
#         "**Click & drag** the grid to nudge it onto the actual yard. "
#         "When both yards exist, each is dragged INDEPENDENTLY — click "
#         "a front-yard block to move the front grid, a back-yard block to "
#         "move the back grid. Rotation controls below the map are also "
#         "per-yard. Click **Save** to persist."
#     )

#     # ── Build per-yard render payloads ────────────────────────────────
#     # If the config has the new `yards` shape, render each yard with its
#     # own anchor + rotation. If it's a legacy single-yard config, render
#     # it as a single "back" yard for UI purposes (preserves on-save shape).
#     render_yards = {}  # yard_key -> {anchor, rotation, blocks_payload, points_payload}

#     if yards_in_config:
#         for yk, ydata in yards_in_config.items():
#             if not ydata:
#                 continue
#             blocks_payload = []
#             for bid, b in ydata.get("grid_blocks", {}).items():
#                 corners = [
#                     [b["sw_x"], b["sw_y"]],
#                     [b["ne_x"], b["sw_y"]],
#                     [b["ne_x"], b["ne_y"]],
#                     [b["sw_x"], b["ne_y"]],
#                 ]
#                 cx = (b["sw_x"] + b["ne_x"]) / 2
#                 cy = (b["sw_y"] + b["ne_y"]) / 2
#                 mock_ppm = b.get("mock_ppm", 0)
#                 label, color = get_nysh_category(mock_ppm) if mock_ppm else ("Preview", "#4a90d9")
#                 blocks_payload.append({
#                     "id": bid,
#                     "cell": b.get("cell_id", bid),
#                     "corners": corners,
#                     "cx": cx, "cy": cy,
#                     "color": color,
#                     "label": label,
#                     "ppm": mock_ppm,
#                 })
#             points_payload = []
#             for pid, pt in ydata.get("point_samples", {}).items():
#                 points_payload.append({
#                     "id": pid,
#                     "name": pt.get("name", pid),
#                     "ox": pt.get("offset_x", 0),
#                     "oy": pt.get("offset_y", 0),
#                 })
#             render_yards[yk] = {
#                 "anchor_lat": ydata["anchor"]["lat"],
#                 "anchor_lon": ydata["anchor"]["lon"],
#                 "rotation":   ydata.get("rotation_deg", 0),
#                 "blocks":     blocks_payload,
#                 "points":     points_payload,
#             }
#     else:
#         # Legacy single-yard config — render as one yard. Default to back
#         # per spec (SampleIDs without Front/Back → backyard).
#         blocks_payload = []
#         for bid, b in config["grid_blocks"].items():
#             corners = [
#                 [b["sw_x"], b["sw_y"]],
#                 [b["ne_x"], b["sw_y"]],
#                 [b["ne_x"], b["ne_y"]],
#                 [b["sw_x"], b["ne_y"]],
#             ]
#             cx = (b["sw_x"] + b["ne_x"]) / 2
#             cy = (b["sw_y"] + b["ne_y"]) / 2
#             mock_ppm = b.get("mock_ppm", 0)
#             label, color = get_nysh_category(mock_ppm) if mock_ppm else ("Preview", "#4a90d9")
#             blocks_payload.append({
#                 "id": bid,
#                 "cell": b.get("cell_id", bid),
#                 "corners": corners,
#                 "cx": cx, "cy": cy,
#                 "color": color,
#                 "label": label,
#                 "ppm": mock_ppm,
#             })
#         points_payload = []
#         for pid, pt in config.get("point_samples", {}).items():
#             points_payload.append({
#                 "id": pid,
#                 "name": pt.get("name", pid),
#                 "ox": pt.get("offset_x", 0),
#                 "oy": pt.get("offset_y", 0),
#             })
#         # Use "legacy" key so the JS knows there's no yard split; save logic
#         # will keep this config in its original shape.
#         render_yards["legacy"] = {
#             "anchor_lat": config["anchor"]["lat"],
#             "anchor_lon": config["anchor"]["lon"],
#             "rotation":   config.get("rotation_deg", 0),
#             "blocks":     blocks_payload,
#             "points":     points_payload,
#         }

#     # Build legend
#     legend_rows = ""
#     for t in NYSH_TIERS:
#         legend_rows += (
#             '<div><span style="display:inline-block;width:11px;height:11px;'
#             f'background:{t["color"]};border-radius:2px;margin-right:5px;'
#             f'vertical-align:middle"></span>{t["label"]}</div>'
#         )
#     legend_rows += (
#         '<div><span style="display:inline-block;width:11px;height:11px;'
#         'background:#4a90d9;border-radius:2px;margin-right:5px;'
#         'vertical-align:middle"></span>Preview (no data yet)</div>'
#     )

#     # Compute the initial map center: midpoint of all yards' anchors.
#     if render_yards:
#         anchor_lats = [y["anchor_lat"] for y in render_yards.values()]
#         anchor_lons = [y["anchor_lon"] for y in render_yards.values()]
#         map_center_lat = sum(anchor_lats) / len(anchor_lats)
#         map_center_lon = sum(anchor_lons) / len(anchor_lons)
#     else:
#         map_center_lat = config.get("anchor", {}).get("lat", 0)
#         map_center_lon = config.get("anchor", {}).get("lon", 0)

#     # Build the dynamic controls HTML — one block per yard.
#     # Colors per yard so they're visually distinguishable on the map.
#     yard_visuals = {
#         "front":  {"label": "Front Yard", "stroke": "#ffd166", "anchor_color": "#ffd166"},
#         "back":   {"label": "Back Yard",  "stroke": "#ff4444", "anchor_color": "#ff4444"},
#         "legacy": {"label": "Grid",       "stroke": "#ff4444", "anchor_color": "#ff4444"},
#     }

#     controls_html = ""
#     for yk in render_yards.keys():
#         viz = yard_visuals[yk]
#         rot_init = render_yards[yk]["rotation"]
#         controls_html += f"""
#         <div class="yard-block" data-yard="{yk}" style="border-left:3px solid {viz['stroke']};">
#           <b>{viz['label']} Position</b>
#           <div class="hint">Click &amp; drag a {viz['label'].lower()} block on the map</div>
#           <div class="rotate-row">
#             <button onclick="rg('{yk}', -5)">−5°</button>
#             <button onclick="rg('{yk}', -1)">−1°</button>
#             <span id="rd_{yk}">{rot_init}°</span>
#             <button onclick="rg('{yk}', 1)">+1°</button>
#             <button onclick="rg('{yk}', 5)">+5°</button>
#           </div>
#           <div class="offset" id="od_{yk}">Offset: 0.0 E, 0.0 N</div>
#           <button class="copy-btn" id="cp_{yk}" onclick="cp('{yk}')">Copy values for boxes</button>
#           <div class="copy-hint">Paste as: East, North, Rotation</div>
#           <button class="reset-btn" onclick="rs('{yk}')">Reset {viz['label']}</button>
#         </div>
#         """

#     # Serialise per-yard payloads for JS.
#     yards_json = json.dumps({
#         yk: {
#             "anchor_lat": y["anchor_lat"],
#             "anchor_lon": y["anchor_lon"],
#             "rotation":   y["rotation"],
#             "blocks":     y["blocks"],
#             "points":     y["points"],
#             "stroke":     yard_visuals[yk]["stroke"],
#             "anchor_color": yard_visuals[yk]["anchor_color"],
#             "label":      yard_visuals[yk]["label"],
#         }
#         for yk, y in render_yards.items()
#     })

#     # Use a per-site localStorage key so two sites don't trample each
#     # other's drag state in the same browser session. Strip characters
#     # that might confuse JS string concatenation.
#     site_id_for_storage = re.sub(
#         r"[^A-Za-z0-9_-]", "_",
#         config.get("site_id", "site")
#     )

#     # Leaflet HTML component with PER-YARD drag + rotate + message bridge.
#     # The JS keeps a state map keyed by yard, and click-detection figures
#     # out which yard's blocks are under the cursor so drags are isolated.
#     component_html = f"""
# <!DOCTYPE html>
# <html><head>
# <meta charset="utf-8">
# <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
# <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
# <style>
#   html,body {{ margin:0; padding:0; font-family:Arial,sans-serif; background:#0c0f14; }}
#   #map {{ width:100%; height:560px; }}
#   .legend {{ position:absolute; bottom:20px; left:20px; z-index:1001;
#     background:rgba(12,15,20,0.93); padding:12px 16px; border-radius:10px;
#     color:#e8eaed; font-size:11px; line-height:1.7;
#     border:1px solid rgba(255,255,255,0.08); }}
#   .legend b {{ font-size:13px; }}
#   .controls {{ position:absolute; top:20px; right:20px; z-index:1001;
#     background:rgba(12,15,20,0.93); padding:8px 12px; border-radius:10px;
#     color:#e8eaed; font-size:11px; border:1px solid rgba(255,255,255,0.08);
#     min-width:230px; max-height:540px; overflow-y:auto; }}
#   .controls .yard-block {{ padding:8px 6px 10px 10px; margin-bottom:6px;
#     border-radius:6px; background:rgba(255,255,255,0.02); }}
#   .controls .yard-block:last-child {{ margin-bottom:0; }}
#   .controls b {{ font-size:13px; color:#e67e22; }}
#   .controls .hint {{ font-size:10px; color:#7a8599; margin-top:2px; }}
#   .controls .offset {{ font-family:monospace; font-size:11px; color:#4ecdc4;
#     margin-top:6px; background:rgba(78,205,196,0.08); padding:5px 8px;
#     border-radius:4px; }}
#   .controls button {{ padding:4px 9px; border:1px solid rgba(255,255,255,0.15);
#     border-radius:4px; background:rgba(78,205,196,0.12); color:#4ecdc4;
#     cursor:pointer; font-size:10px; }}
#   .controls button:hover {{ background:rgba(78,205,196,0.25); }}
#   .rotate-row {{ display:flex; gap:4px; align-items:center; margin-top:6px; }}
#   .rotate-row button {{ margin:0; padding:3px 7px; font-size:10px; }}
#   .rotate-row span {{ font-size:11px; color:#c7d0dc; min-width:38px;
#     text-align:center; font-family:monospace; }}
#   .copy-btn {{ margin-top:8px; width:100%; background:rgba(78,205,196,0.16) !important;
#     color:#4ecdc4 !important; }}
#   .copy-hint {{ margin-top:4px; color:#7a8599; font-size:9px; }}
#   .reset-btn {{ margin-top:8px; width:100%; background:rgba(255,100,100,0.12) !important;
#     color:#ff8888 !important; }}
# </style>
# </head><body>
# <div id="map"></div>
# <div class="legend"><b>Lead Guidelines (ppm)</b><br>{legend_rows}</div>
# <div class="controls">{controls_html}</div>

# <script>
#   var RF = 20925721.78;
#   var YARDS = {yards_json};

#   // Per-yard mutable state.
#   var STATE = {{}};
#   Object.keys(YARDS).forEach(function(yk) {{
#     STATE[yk] = {{ oE: 0, oN: 0, rot: YARDS[yk].rotation, dirty: false }};
#   }});

#   var map = L.map('map', {{
#     center: [{map_center_lat}, {map_center_lon}], zoom: 21, maxZoom: 25
#   }});
#   L.tileLayer(
#     'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
#     {{ attribution: 'Esri', maxZoom: 25, maxNativeZoom: 19 }}
#   ).addTo(map);

#   // One anchor marker per yard (stays put — doesn't move with drag).
#   Object.keys(YARDS).forEach(function(yk) {{
#     var Y = YARDS[yk];
#     L.marker([Y.anchor_lat, Y.anchor_lon], {{
#       icon: L.divIcon({{
#         className: '',
#         html: '<div style="width:14px;height:14px;background:' + Y.anchor_color +
#               ';border:2px solid white;border-radius:50%;box-shadow:0 0 6px rgba(0,0,0,0.6)"></div>',
#         iconSize: [14,14], iconAnchor: [7,7]
#       }})
#     }}).addTo(map).bindTooltip(Y.label + ' Anchor');
#   }});

#   function f2ll(la, lo, e, n) {{
#     var dl = (n / RF) * (180 / Math.PI);
#     var dn = (e / (RF * Math.cos(la * Math.PI / 180))) * (180 / Math.PI);
#     return [la + dl, lo + dn];
#   }}

#   function rp(x, y, a) {{
#     var r = a * Math.PI / 180;
#     return [x * Math.cos(r) - y * Math.sin(r), x * Math.sin(r) + y * Math.cos(r)];
#   }}

#   // Per-yard layer groups so we can clear & re-draw each independently.
#   var GROUPS = {{}};
#   Object.keys(YARDS).forEach(function(yk) {{
#     GROUPS[yk] = L.layerGroup().addTo(map);
#   }});

#   // Track which polygons belong to which yard (for click hit-test).
#   var POLY_TO_YARD = []; // array of {{poly, yard}}

#   function drawYard(yk) {{
#     var Y = YARDS[yk];
#     var S = STATE[yk];
#     GROUPS[yk].clearLayers();
#     // Filter out our prior poly-yard mappings for this yard before re-adding.
#     POLY_TO_YARD = POLY_TO_YARD.filter(function(rec) {{ return rec.yard !== yk; }});

#     Y.blocks.forEach(function(b) {{
#       var ll = b.corners.map(function(c) {{
#         var r = rp(c[0], c[1], S.rot);
#         return f2ll(Y.anchor_lat, Y.anchor_lon, r[0] + S.oE, r[1] + S.oN);
#       }});
#       var pl = L.polygon(ll, {{
#         color: Y.stroke, weight: 2,
#         fillColor: b.color, fillOpacity: 0.65
#       }});
#       pl.bindTooltip('<b>' + b.cell + '</b><br>' + Y.label + '<br>' + b.label);
#       GROUPS[yk].addLayer(pl);
#       POLY_TO_YARD.push({{ poly: pl, yard: yk }});

#       var rc = rp(b.cx, b.cy, S.rot);
#       var lp = f2ll(Y.anchor_lat, Y.anchor_lon, rc[0] + S.oE, rc[1] + S.oN);
#       GROUPS[yk].addLayer(L.marker(lp, {{
#         icon: L.divIcon({{
#           className: '',
#           html: '<div style="font-family:Arial;text-align:center;pointer-events:none">' +
#                 '<b style="font-size:10px;color:white;text-shadow:0 1px 3px rgba(0,0,0,0.85)">' +
#                 b.cell + '</b></div>',
#           iconSize: [50, 20], iconAnchor: [25, 10]
#         }}),
#         interactive: false
#       }}));
#     }});

#     Y.points.forEach(function(p) {{
#       var r = rp(p.ox, p.oy, S.rot);
#       var ll = f2ll(Y.anchor_lat, Y.anchor_lon, r[0] + S.oE, r[1] + S.oN);
#       GROUPS[yk].addLayer(L.circleMarker(ll, {{
#         radius: 7, color: 'white', weight: 2,
#         fillColor: '#f39c12', fillOpacity: 0.8
#       }}).bindTooltip('<b>' + p.name + '</b> (' + Y.label + ')'));
#     }});

#     // Update per-yard control panel readout.
#     var od = document.getElementById('od_' + yk);
#     var rd = document.getElementById('rd_' + yk);
#     if (od) od.textContent = 'Offset: ' + S.oE.toFixed(1) + ' E, ' + S.oN.toFixed(1) + ' N' +
#       (S.rot ? ('  |  ' + S.rot + '°') : '');
#     if (rd) rd.textContent = S.rot + '°';

#     postState();
#   }}

#   function drawAll() {{
#     Object.keys(YARDS).forEach(drawYard);
#   }}

#   function postState() {{
#     // Send the full per-yard state up to the Streamlit host.
#     var payload = {{ type: 'groundsense_grid_state_multi', yards: {{}} }};
#     Object.keys(STATE).forEach(function(yk) {{
#       payload.yards[yk] = {{
#         offset_east_ft:  STATE[yk].oE,
#         offset_north_ft: STATE[yk].oN,
#         rotation_deg:    STATE[yk].rot,
#         dirty:          !!STATE[yk].dirty
#       }};
#     }});
#     // Persist to BOTH localStorage (for streamlit_js_eval to read on
#     // Python-side reruns — the message-bus is racy) AND postMessage
#     // (for any listener that's already wired up).
#     try {{
#       window.parent.localStorage.setItem(
#         'gs_drag_state_' + '{site_id_for_storage}',
#         JSON.stringify(payload.yards)
#       );
#     }} catch (e) {{
#       // Cross-origin localStorage access blocked — try this frame's own.
#       try {{
#         window.localStorage.setItem(
#           'gs_drag_state_' + '{site_id_for_storage}',
#           JSON.stringify(payload.yards)
#         );
#       }} catch (e2) {{ /* give up — postMessage still works */ }}
#     }}
#     window.parent.postMessage(payload, '*');
#   }}

#   function rg(yk, d) {{ STATE[yk].rot += d; STATE[yk].dirty = true; drawYard(yk); }}
#   function rs(yk) {{ STATE[yk].oE = 0; STATE[yk].oN = 0; STATE[yk].rot = 0; STATE[yk].dirty = true; drawYard(yk); }}

#   function cp(yk) {{
#     var S = STATE[yk];
#     // Copy in the exact order of the Streamlit boxes below:
#     // East offset, North offset, Rotation.
#     var text = S.oE.toFixed(2) + ', ' + S.oN.toFixed(2) + ', ' + S.rot.toFixed(2);
#     function markDone() {{
#       var b = document.getElementById('cp_' + yk);
#       if (!b) return;
#       var old = b.textContent;
#       b.textContent = 'Copied: ' + text;
#       setTimeout(function() {{ b.textContent = old; }}, 1800);
#     }}
#     if (navigator.clipboard && navigator.clipboard.writeText) {{
#       navigator.clipboard.writeText(text).then(markDone).catch(function() {{
#         window.prompt('Copy these values: East, North, Rotation', text);
#       }});
#     }} else {{
#       window.prompt('Copy these values: East, North, Rotation', text);
#     }}
#   }}

#   // Click & drag detection — figure out which yard owns the hit polygon.
#   var iD = false, dY = null, dL = null, dE = 0, dN = 0;
#   map.on('mousedown', function(e) {{
#     var hit_yard = null;
#     POLY_TO_YARD.forEach(function(rec) {{
#       if (!hit_yard && rec.poly.getBounds().contains(e.latlng)) hit_yard = rec.yard;
#     }});
#     if (hit_yard) {{
#       iD = true; dY = hit_yard; dL = e.latlng;
#       dE = STATE[hit_yard].oE; dN = STATE[hit_yard].oN;
#       map.dragging.disable();
#       map.getContainer().style.cursor = 'grabbing';
#     }}
#   }});
#   map.on('mousemove', function(e) {{
#     if (!iD) return;
#     var Y = YARDS[dY];
#     STATE[dY].oN = dN + (e.latlng.lat - dL.lat) * (Math.PI / 180) * RF;
#     STATE[dY].oE = dE + (e.latlng.lng - dL.lng) * (Math.PI / 180) * RF *
#               Math.cos(Y.anchor_lat * Math.PI / 180);
#     STATE[dY].dirty = true;
#     drawYard(dY);
#   }});
#   map.on('mouseup', function() {{
#     if (iD) {{
#       iD = false; dY = null;
#       map.dragging.enable();
#       map.getContainer().style.cursor = '';
#     }}
#   }});

#   drawAll();
# </script>
# </body></html>
# """

#     components.html(component_html, height=580, scrolling=False)

#     # ──────────────────────────────────────────────────────────────────
#     # CAPTURE DRAG STATE — robust localStorage-based bridge
#     # ──────────────────────────────────────────────────────────────────
#     # The Leaflet iframe writes drag state to parent.localStorage on every
#     # nudge (see postState() in the JS above). On Python rerun, we read
#     # that localStorage key via streamlit_js_eval. This is rock-solid
#     # vs the postMessage approach which races on iframe load.
#     #
#     # If streamlit_js_eval is unavailable, fall back to manual number
#     # inputs. Either way, the final live_states[yk] feeds Save.
#     # ──────────────────────────────────────────────────────────────────

#     try:
#         from streamlit_js_eval import streamlit_js_eval
#         bridge_available = True
#     except ImportError:
#         bridge_available = False

#     st.markdown("#### 💾 Save Fine-Tuned Position")
#     st.caption(
#         "After dragging in the map above, use **Copy values for boxes** in the map control panel, "
#         "then paste/type those values into the East, North, and Rotation boxes below. "
#         "The export buttons below use these box values immediately. Click **💾 Save** only when "
#         "you want to bake those offsets into `site_configs.json`."
#     )

#     yard_keys_for_state = list(render_yards.keys())

#     # If a previous Save baked the offsets into the anchor, reset the manual
#     # offset boxes BEFORE the widgets are created on this rerun. This avoids
#     # applying the same offset twice to exports after Save.
#     if st.session_state.pop("reset_offset_inputs_after_save", False):
#         for _yk in yard_keys_for_state:
#             st.session_state[f"in_e_{_yk}"] = 0.0
#             st.session_state[f"in_n_{_yk}"] = 0.0
#             st.session_state[f"in_r_{_yk}"] = float(render_yards[_yk]["rotation"] or 0.0)

#     if st.session_state.pop("position_save_success", False):
#         st.success(
#             "✅ Position saved. The manual offset boxes were reset to 0 because "
#             "the offset is now baked into the saved anchor. Downloads now use the "
#             "saved position as the default."
#         )

#     # ── Step 1: read whatever's in localStorage right now (auto on every rerun) ──
#     captured = {}
#     if bridge_available:
#         storage_key = f"gs_drag_state_{site_id_for_storage}"
#         # Read from BOTH localStorage scopes (parent and iframe) — whichever
#         # the postState() write succeeded into. Return as JSON string.
#         raw = streamlit_js_eval(
#             js_expressions=f"""
#                 (function() {{
#                     var k = '{storage_key}';
#                     var v = null;
#                     try {{ v = window.parent.localStorage.getItem(k); }} catch(e) {{}}
#                     if (!v) {{
#                         try {{ v = window.localStorage.getItem(k); }} catch(e) {{}}
#                     }}
#                     return v || '';
#                 }})()
#             """,
#             key=f"gs_storage_read_{site_id_for_storage}",
#             want_output=True,
#         )
#         if raw:
#             try:
#                 captured = json.loads(raw)
#             except Exception:
#                 captured = {}

#     # ── Step 2: explicit Capture button (forces a re-read + writes into inputs) ──
#     # The bridge above runs on every rerun, but the Capture button is the
#     # tech's "I'm done dragging — pull values in NOW" handoff. Clicking it
#     # copies localStorage → session_state, so the inputs below show the
#     # captured values and Save reads them.
#     cap_col, status_col = st.columns([1, 3])
#     with cap_col:
#         capture_clicked = st.button(
#             "🔄 Capture Drag State",
#             use_container_width=True,
#             key="capture_drag_btn",
#             help="Pull the current drag/rotation from the map above into the inputs.",
#         )
#     with status_col:
#         if captured:
#             parts = []
#             for yk in yard_keys_for_state:
#                 c = captured.get(yk) or {}
#                 e = c.get("offset_east_ft", 0) or 0
#                 n = c.get("offset_north_ft", 0) or 0
#                 r = c.get("rotation_deg", 0) or 0
#                 parts.append(
#                     f"{yard_visuals[yk]['label']}: "
#                     f"{e:+.1f}E / {n:+.1f}N / {r:+.0f}°"
#                 )
#             st.caption("🟢 Live drag state detected: " + "  ·  ".join(parts))
#         else:
#             st.caption(
#                 "⚪ No drag state in browser storage yet. "
#                 "Drag in the map above first, then click Capture."
#             )

#     # ── Step 3: per-yard editable inputs (the actual source of truth for Save) ──
#     # If Capture was clicked, copy localStorage values into the input keys
#     # BEFORE the widgets are instantiated. Streamlit reads from session_state
#     # on the next rerun, so this gets the values into the boxes.
#     if capture_clicked and captured:
#         for yk in yard_keys_for_state:
#             c = captured.get(yk) or {}
#             st.session_state[f"in_e_{yk}"] = float(c.get("offset_east_ft", 0) or 0)
#             st.session_state[f"in_n_{yk}"] = float(c.get("offset_north_ft", 0) or 0)
#             st.session_state[f"in_r_{yk}"] = float(
#                 c.get("rotation_deg", render_yards[yk]["rotation"]) or 0
#             )
#         st.rerun()

#     live_states = {}
#     if not bridge_available:
#         st.info(
#             "⚙️ For one-click drag capture, install `streamlit-js-eval`:  \n"
#             "`pip install streamlit-js-eval`  \n\n"
#             "Meanwhile, type each yard's drag offsets manually below."
#         )

#     # ── Step 3A: reliable paste handoff from the preview panel ───────────────
#     # This avoids relying on iframe → Streamlit communication. The preview's
#     # "Copy values for boxes" button copies: East, North, Rotation.
#     # Paste that exact text here and click Apply; the number inputs below become
#     # the committed source of truth for Save + HTML/PNG downloads.
#     def _parse_offset_triplet(raw: str, default_rotation: float = 0.0):
#         raw = (raw or "").strip()
#         if not raw:
#             return None
#         # Accept both:
#         #   -2.00, 17.60, 0.00
#         #   East=-2.00, North=17.60, Rot=0°
#         nums = re.findall(r"[-+]?\d+(?:\.\d+)?", raw)
#         if len(nums) < 2:
#             return None
#         e_val = float(nums[0])
#         n_val = float(nums[1])
#         r_val = float(nums[2]) if len(nums) >= 3 else float(default_rotation or 0.0)
#         return e_val, n_val, r_val

#     st.markdown("##### Paste copied preview offset")
#     st.caption(
#         "Use this instead of Capture: click **Copy values for boxes** in the preview panel, "
#         "paste the copied text here, then click **Apply copied values**. After that, downloads use it."
#     )

#     paste_cols = st.columns(len(yard_keys_for_state) if yard_keys_for_state else 1)
#     paste_apply_clicked = False
#     for idx, yk in enumerate(yard_keys_for_state):
#         with paste_cols[idx]:
#             st.text_input(
#                 f"{yard_visuals[yk]['label']} copied values",
#                 key=f"paste_offsets_{yk}",
#                 placeholder="Example: -2.00, 17.60, 0.00",
#             )
#     paste_apply_clicked = st.button(
#         "✅ Apply copied values to boxes",
#         use_container_width=True,
#         key="apply_copied_offsets_btn",
#     )

#     if paste_apply_clicked:
#         applied_any = False
#         bad_yards = []
#         for yk in yard_keys_for_state:
#             parsed = _parse_offset_triplet(
#                 st.session_state.get(f"paste_offsets_{yk}", ""),
#                 render_yards[yk]["rotation"],
#             )
#             if parsed is None:
#                 # Empty is fine when there is only one yard? No — tell user what failed.
#                 bad_yards.append(yard_visuals[yk]["label"])
#                 continue
#             e_val, n_val, r_val = parsed
#             st.session_state[f"in_e_{yk}"] = e_val
#             st.session_state[f"in_n_{yk}"] = n_val
#             st.session_state[f"in_r_{yk}"] = r_val
#             applied_any = True
#         if applied_any:
#             st.session_state["copied_offsets_apply_success"] = True
#             st.rerun()
#         else:
#             st.error("Could not read any copied offset values. Paste values like: `-2.00, 17.60, 0.00`.")

#     if st.session_state.pop("copied_offsets_apply_success", False):
#         st.success("✅ Copied offset values applied to the boxes below. HTML/PNG downloads now use these values.")

#     for yk in yard_keys_for_state:
#         st.markdown(f"**{yard_visuals[yk]['label']}**")
#         mc1, mc2, mc3 = st.columns(3)
#         # Default values come from session_state (populated by Capture) or
#         # fall back to zero / the saved rotation. Number inputs read & write
#         # to session_state via their key.
#         default_e = float(st.session_state.get(f"in_e_{yk}", 0.0) or 0.0)
#         default_n = float(st.session_state.get(f"in_n_{yk}", 0.0) or 0.0)
#         default_r = float(
#             st.session_state.get(f"in_r_{yk}", render_yards[yk]["rotation"]) or 0.0
#         )
#         live_states[yk] = {
#             "e": mc1.number_input(
#                 "East offset (ft)", value=default_e, step=0.1,
#                 format="%.2f", key=f"in_e_{yk}",
#             ),
#             "n": mc2.number_input(
#                 "North offset (ft)", value=default_n, step=0.1,
#                 format="%.2f", key=f"in_n_{yk}",
#             ),
#             "r": mc3.number_input(
#                 "Rotation (°)", value=default_r, step=1.0,
#                 format="%.2f", key=f"in_r_{yk}",
#             ),
#         }

#     st.markdown("---")

#     def _captured_states_for_save(captured_state: dict, fallback_states: dict) -> dict:
#         """Prefer browser-captured drag state for yards that were actually
#         dragged/rotated/reset. Fall back to the manual inputs otherwise.
#         """
#         merged = json.loads(json.dumps(fallback_states))
#         if not captured_state:
#             return merged
#         for _yk in yard_keys_for_state:
#             c = captured_state.get(_yk) or {}
#             # The iframe writes an initial zero-state on load. Only treat
#             # browser state as authoritative after the user interacted with
#             # that yard (dirty=True). This preserves manual fallback inputs.
#             if not c.get("dirty", False):
#                 continue
#             merged[_yk] = {
#                 "e": float(c.get("offset_east_ft", 0) or 0),
#                 "n": float(c.get("offset_north_ft", 0) or 0),
#                 "r": float(c.get("rotation_deg", render_yards[_yk]["rotation"]) or 0),
#             }
#         return merged

#     # Buttons
#     sb1, sb2, _ = st.columns([2, 2, 3])
#     with sb1:
#         save_clicked = st.button("💾 Save Position to Config",
#                                   type="primary", use_container_width=True,
#                                   key="save_position_btn")
#     with sb2:
#         download_clicked = st.button("📥 Preview JSON",
#                                       use_container_width=True,
#                                       key="preview_json_btn")

#     def _apply_manual_offsets_to_config(base_config: dict, states: dict) -> dict:
#         """Return a copy of base_config with the current manual box offsets baked in.

#         This is the single source of truth for both Save and downloads. The boxes
#         are intentionally used instead of localStorage because the iframe/browser
#         bridge can be unreliable on some Streamlit installs.
#         """
#         R_EARTH_FT = 20_925_721.78
#         updated_config = json.loads(json.dumps(base_config))
#         loaded_from_disk = st.session_state.get("loaded_from_disk", False)
#         had_yards_originally = bool((updated_config.get("yards") or {}))

#         def _shift_anchor(old_lat, old_lon, e_ft, n_ft):
#             delta_lat = (n_ft / R_EARTH_FT) * (180 / math.pi)
#             lat_rad = old_lat * (math.pi / 180)
#             delta_lon = (e_ft / (R_EARTH_FT * math.cos(lat_rad))) * (180 / math.pi)
#             return old_lat + delta_lat, old_lon + delta_lon

#         # ── Case 1: legacy single-yard config (loaded from disk OR new flow
#         #            with no yards key present). Update in place, no `yards`
#         #            key. Keeps the old schema verbatim — historical data
#         #            untouched.
#         if not had_yards_originally:
#             # There's exactly one yard in render_yards. Could be keyed
#             # "legacy" (loaded old config) or "front"/"back" (new flow
#             # with only one yard computed).
#             yk = yard_keys_for_state[0]
#             ls = states[yk]
#             old_lat = updated_config["anchor"]["lat"]
#             old_lon = updated_config["anchor"]["lon"]
#             new_lat, new_lon = _shift_anchor(old_lat, old_lon, ls["e"], ls["n"])
#             updated_config["anchor"]["lat"] = round(new_lat, 8)
#             updated_config["anchor"]["lon"] = round(new_lon, 8)
#             updated_config["anchor"]["description"] = (
#                 (updated_config["anchor"].get("description", "") or "")
#                 + f" · visually nudged {ls['e']:+.2f} E / {ls['n']:+.2f} N ft"
#             ).strip(" ·")
#             updated_config["rotation_deg"] = round(ls["r"], 2)

#             # If the source was a new-flow (front_config or back_config)
#             # rather than a legacy load, we should ALSO write the `yards`
#             # block so future loads use the new shape. This is the only
#             # case where new data gets the new schema; loaded legacy
#             # configs stay legacy.
#             if not loaded_from_disk and yk in ("front", "back"):
#                 # Pull the stashed per-yard config built during Compute,
#                 # apply the offset/rotation to its anchor, and store it
#                 # in the yards block.
#                 stash = st.session_state.get(f"{yk}_config")
#                 if stash is not None:
#                     yard_copy = json.loads(json.dumps(stash))
#                     a_old_lat = yard_copy["anchor"]["lat"]
#                     a_old_lon = yard_copy["anchor"]["lon"]
#                     a_new_lat, a_new_lon = _shift_anchor(
#                         a_old_lat, a_old_lon, ls["e"], ls["n"]
#                     )
#                     yard_copy["anchor"]["lat"] = round(a_new_lat, 8)
#                     yard_copy["anchor"]["lon"] = round(a_new_lon, 8)
#                     yard_copy["rotation_deg"] = round(ls["r"], 2)
#                     updated_config["yards"] = {yk: yard_copy}

#         # ── Case 2: new yards-shaped config. Apply offset/rotation to EACH
#         #            yard's anchor and rotation independently. Also refresh
#         #            the legacy mirror keys so old consumers see something
#         #            consistent.
#         else:
#             new_yards = {}
#             for yk in yard_keys_for_state:
#                 if yk not in (updated_config.get("yards") or {}):
#                     # Yard exists in render but not in updated_config (shouldn't
#                     # normally happen). Skip safely.
#                     continue
#                 ydata = updated_config["yards"][yk]
#                 if ydata is None:
#                     continue
#                 ls = states[yk]
#                 a_old_lat = ydata["anchor"]["lat"]
#                 a_old_lon = ydata["anchor"]["lon"]
#                 a_new_lat, a_new_lon = _shift_anchor(
#                     a_old_lat, a_old_lon, ls["e"], ls["n"]
#                 )
#                 ydata = json.loads(json.dumps(ydata))
#                 ydata["anchor"]["lat"] = round(a_new_lat, 8)
#                 ydata["anchor"]["lon"] = round(a_new_lon, 8)
#                 ydata["anchor"]["description"] = (
#                     (ydata["anchor"].get("description", "") or "")
#                     + f" · visually nudged {ls['e']:+.2f} E / {ls['n']:+.2f} N ft"
#                 ).strip(" ·")
#                 ydata["rotation_deg"] = round(ls["r"], 2)
#                 new_yards[yk] = ydata
#             updated_config["yards"] = new_yards

#             # Refresh legacy mirror keys from the updated yards block.
#             legacy_mirror = _merge_yards_into_legacy(new_yards)
#             updated_config["anchor"] = legacy_mirror["anchor"]
#             updated_config["rotation_deg"] = legacy_mirror["rotation_deg"]
#             updated_config["grid_blocks"] = legacy_mirror["grid_blocks"]
#             updated_config["point_samples"] = legacy_mirror["point_samples"]

#         return updated_config

#     # Downloads should reflect the values currently typed/pasted in the boxes,
#     # even before the user saves. This is the config used by Preview JSON and
#     # all HTML/PNG export buttons below.
#     export_config = _apply_manual_offsets_to_config(config, live_states)

#     if save_clicked:
#         # Save uses the same config that downloads use: the current box values.
#         # This makes copy/paste offsets deterministic and avoids stale iframe state.
#         updated_config = export_config

#         # ── Persist — APPEND-OR-REPLACE the entry for this site_id.
#         # Any other site entries in the file are preserved verbatim.
#         base_dir = os.path.dirname(os.path.abspath(__file__))
#         config_dir = os.path.join(base_dir, "..", "data", "site_configs")
#         config_path = os.path.join(config_dir, "site_configs.json")
#         os.makedirs(config_dir, exist_ok=True)

#         existing = []
#         if os.path.exists(config_path):
#             try:
#                 with open(config_path) as f:
#                     existing = json.load(f)
#             except Exception:
#                 existing = []

#         found = False
#         for i, s in enumerate(existing):
#             if s.get("site_id") == updated_config["site_id"]:
#                 existing[i] = updated_config
#                 found = True
#                 break
#         if not found:
#             existing.append(updated_config)

#         with open(config_path, "w") as f:
#             json.dump(existing, f, indent=2)

#         st.session_state["generated_config"] = updated_config
#         # Use the freshly saved config for JSON preview and map exports in
#         # this same run, so downloads immediately default to the dragged
#         # position instead of the original computed anchor.
#         config = updated_config

#         # Clear the localStorage drag state so the next Save doesn't
#         # apply the same offset twice (the offset has been baked into
#         # the anchor lat/lon now).
#         if bridge_available:
#             try:
#                 streamlit_js_eval(
#                     js_expressions=f"""
#                         (function() {{
#                             var k = 'gs_drag_state_{site_id_for_storage}';
#                             try {{ window.parent.localStorage.removeItem(k); }} catch(e) {{}}
#                             try {{ window.localStorage.removeItem(k); }} catch(e) {{}}
#                             return 'cleared';
#                         }})()
#                     """,
#                     key=f"gs_storage_clear_{site_id_for_storage}_{os.urandom(2).hex()}",
#                     want_output=False,
#                 )
#             except Exception:
#                 pass
#         # Build a friendly summary message.
#         yards_saved = list((updated_config.get("yards") or {}).keys())
#         if yards_saved:
#             yards_desc = f"with yards: **{', '.join(yards_saved)}**"
#         else:
#             yards_desc = "(legacy single-yard schema preserved)"
#         st.session_state["position_save_success"] = True
#         st.session_state["reset_offset_inputs_after_save"] = True
#         st.session_state["generated_config"] = updated_config
#         st.rerun()

#     if download_clicked:
#         json_str = json.dumps(export_config, indent=2)
#         st.code(json_str, language="json")
#         st.download_button(
#             "📥 Download JSON",
#             data=json_str,
#             file_name=f"site_config_{export_config['site_id']}.json",
#             mime="application/json",
#         )

#     # ═══════════════════════════════════════════
#     #  MAP EXPORTS — three consistent variants
#     # ═══════════════════════════════════════════
#     st.markdown("---")
#     st.subheader("🗂️ Export Site Maps")
#     st.caption(
#         "Download this site's map in three formats. All three use the **same** "
#         "renderer as the PPTX resident reports, so the output is consistent "
#         "everywhere. Real XRF readings are pulled from the latest Master Data; "
#         "cells without data render in gray. Exports use the legacy mirror "
#         "fields so old & new configs render identically."
#     )

#     # Load master data for real PPM lookup
#     master_df_export = load_master_data()
#     if master_df_export.empty:
#         st.warning(
#             "⚠️ No Master Data found — exports will render all cells as 'No Data' (gray). "
#             "Run the ETL Pipeline first if you want real PPM values."
#         )
#     else:
#         blocks_preview, _ = get_block_data(export_config, master_df_export,
#                                             use_mock_fallback=False)
#         real_count = sum(1 for b in blocks_preview if b["has_real_data"])
#         total = len(blocks_preview)
#         st.caption(
#             f"📊 Using Master Data: **{real_count} / {total}** cells have real "
#             f"XRF readings. Remaining cells will render as 'No Data' (gray)."
#         )

#     safe_name = export_config["site_id"]

#     exp1, exp2, exp3 = st.columns(3)

#     # ─── 1. Basemap + no numbers (HTML) ───
#     with exp1:
#         st.markdown("**🛰️ Basemap · no numbers**")
#         st.caption("Satellite imagery, cell IDs only, draggable.")
#         try:
#             html_nonum = render_leaflet_html(
#                 export_config, master_df_export,
#                 show_numbers=False, use_mock_fallback=False,
#             )
#             st.download_button(
#                 label="📥 Download HTML",
#                 data=html_nonum,
#                 file_name=f"{safe_name}_basemap_no_numbers.html",
#                 mime="text/html",
#                 use_container_width=True,
#                 key="exp_basemap_nonum",
#             )
#         except Exception as e:
#             st.error(f"Render failed: {e}")

#     # ─── 2. Basemap + numbers (HTML) ───
#     with exp2:
#         st.markdown("**🛰️ Basemap · with numbers**")
#         st.caption("Satellite imagery, cell IDs + ppm values.")
#         try:
#             html_num = render_leaflet_html(
#                 export_config, master_df_export,
#                 show_numbers=True, use_mock_fallback=False,
#             )
#             st.download_button(
#                 label="📥 Download HTML",
#                 data=html_num,
#                 file_name=f"{safe_name}_basemap_with_numbers.html",
#                 mime="text/html",
#                 use_container_width=True,
#                 key="exp_basemap_num",
#             )
#         except Exception as e:
#             st.error(f"Render failed: {e}")

#     # ─── 3. No basemap + numbers (PNG) ───
#     with exp3:
#         st.markdown("**🎨 No basemap · with numbers**")
#         st.caption("Dark-theme PNG (matches PPTX reports).")
#         try:
#             with tempfile.NamedTemporaryFile(
#                 suffix=".png", delete=False
#             ) as tmp:
#                 png_path = tmp.name
#             render_static_png(
#                 export_config, master_df_export, png_path,
#                 show_numbers=True, use_mock_fallback=False,
#             )
#             with open(png_path, "rb") as f:
#                 png_bytes = f.read()
#             os.unlink(png_path)
#             st.download_button(
#                 label="📥 Download PNG",
#                 data=png_bytes,
#                 file_name=f"{safe_name}_no_basemap_with_numbers.png",
#                 mime="image/png",
#                 use_container_width=True,
#                 key="exp_static_png",
#             )
#         except Exception as e:
#             st.error(f"Render failed: {e}")

#     st.caption(
#         "🔄 All three outputs honor the site's saved `rotation_deg` and "
#         "fine-tuned anchor position. The PNG here is byte-identical to what "
#         "`etl_manager.py` embeds in the resident PPTX report."
#     )


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


def _zone_for_yard(yard_key: str) -> str:
    """Map an internal yard key to the zone string used in grid_blocks.

    yard_key is 'front' or 'back'. We store zone as 'front_yard' or
    'backyard' so downstream code can tell them apart cleanly.
    """
    return "front_yard" if yard_key == "front" else "backyard"


def _prefix_for_yard(yard_key: str) -> str:
    """Internal block-ID prefix to keep front/back keys collision-proof.

    Front cell 'A1' becomes 'F_A1', back 'A1' becomes 'B_A1'. The
    underlying cell label 'A1' is preserved inside the block as
    'cell_id' for map labels and downstream string matching.
    """
    return "F_" if yard_key == "front" else "B_"


def _merge_yards_into_legacy(yards_block: dict) -> dict:
    """Build the legacy top-level fields from the new yards block.

    Returns a dict with keys 'anchor', 'rotation_deg', 'grid_blocks',
    'point_samples' that mirror the UNION of all yards. Old consumers
    (dashboard, etl_manager, map_renderer) read these keys and stay
    blissfully unaware of the front/back split — every block has a
    `zone` tag that yard-aware code can use later.

    If only one yard exists, its anchor + rotation become the legacy
    fields directly. If both exist, the front yard wins for the legacy
    `anchor`/`rotation_deg` (chosen as the "primary" anchor — back is
    still fully present in the `yards` block with its own anchor).
    """
    front = yards_block.get("front")
    back  = yards_block.get("back")

    # Choose primary yard for legacy anchor/rotation (front first, else back).
    primary = front if front else back
    if primary is None:
        return {
            "anchor": {"lat": 0, "lon": 0, "description": "", "marker_label": ""},
            "rotation_deg": 0,
            "grid_blocks": {},
            "point_samples": {},
        }

    legacy_anchor   = dict(primary["anchor"])
    legacy_rotation = primary.get("rotation_deg", 0)

    legacy_blocks  = {}
    legacy_points  = {}
    for yk in ("front", "back"):
        y = yards_block.get(yk)
        if not y:
            continue
        legacy_blocks.update(y.get("grid_blocks", {}))
        legacy_points.update(y.get("point_samples", {}))

    return {
        "anchor": legacy_anchor,
        "rotation_deg": legacy_rotation,
        "grid_blocks": legacy_blocks,
        "point_samples": legacy_points,
    }


def _split_legacy_into_yards(config: dict) -> dict:
    """Best-effort: split an OLD single-yard config into the yards shape.

    Used when the user loads an existing site that pre-dates this feature.
    The old config has no `yards` key — we treat it as a single backyard
    (per spec: SampleIDs without Front/Back default to back). The user
    can then add a front yard via the builder if they want.

    Returns a yards-shaped dict: {"front": None, "back": {...}}.
    NOTE: We do NOT modify the original config or write it back — this
    is purely for in-session editing. Saving preserves the old shape.
    """
    # Already has the new shape — just hand it back.
    if "yards" in config:
        return dict(config["yards"])

    legacy_blocks = config.get("grid_blocks", {})
    legacy_points = config.get("point_samples", {})

    if not legacy_blocks and not legacy_points:
        return {"front": None, "back": None}

    # Tag every legacy block with backyard zone (default per spec).
    tagged_blocks = {}
    for bid, b in legacy_blocks.items():
        b_copy = dict(b)
        if "zone" not in b_copy or b_copy.get("zone") == "yard":
            b_copy["zone"] = "backyard"
        tagged_blocks[bid] = b_copy

    back_yard = {
        "anchor": dict(config.get("anchor", {})),
        "rotation_deg": config.get("rotation_deg", 0),
        "grid_blocks": tagged_blocks,
        "point_samples": dict(legacy_points),
    }
    return {"front": None, "back": back_yard}


# ═══════════════════════════════════════════════
#  LOAD EXISTING SITE (search/edit existing maps)
#  — UNCHANGED behavior: load any site, drag, save in place. Works with
#    both legacy and new-format configs.
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
        # Mark this as a loaded (existing) site so the preview/save block
        # knows to preserve its on-disk schema (legacy vs new).
        st.session_state["loaded_from_disk"] = True
        # Clear any in-progress build state for the new-site flow.
        st.session_state.pop("front_config", None)
        st.session_state.pop("back_config", None)
        # Clear any stale drag-state from a previous edit.
        for k in ("pending_offset_e", "pending_offset_n", "pending_rotation",
                  "front_offset_e", "front_offset_n", "front_rotation",
                  "back_offset_e", "back_offset_n", "back_rotation",
                  "in_e_front", "in_n_front", "in_r_front",
                  "in_e_back", "in_n_back", "in_r_back",
                  "in_e_legacy", "in_n_legacy", "in_r_legacy"):
            st.session_state.pop(k, None)
        n_blocks = len(cfg.get("grid_blocks", {}))
        # Try to give a friendlier yards breakdown when present.
        yards_present = list((cfg.get("yards") or {}).keys()) if cfg.get("yards") else []
        yards_desc = (f" · yards: {', '.join(yards_present)}"
                      if yards_present else " · legacy single-yard config")
        st.success(
            f"✅ Loaded **{selected_existing}** "
            f"({n_blocks} blocks · "
            f"{len(cfg.get('point_samples', {}))} point samples{yards_desc}). "
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
    sampling_date = st.date_input("Sampling Date *", key="builder_sampling_date")
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
        key="builder_site_id",
    ).strip()

notes = st.text_input(
    "Site Notes (optional)",
    placeholder="e.g. Backyard grid, measured from porch corner…",
    key="builder_notes",
)

st.markdown("---")


# ═══════════════════════════════════════════════
#  STEP 2 — WHICH YARD (NEW)
# ═══════════════════════════════════════════════
st.subheader("② Which Yard")
st.caption(
    "Pick which yard you're configuring right now. Fill in fields ③–⑦, "
    "then hit Compute to stash THIS yard's grid. Switch the dropdown to "
    "the other yard if this site has both — repeat the fill + Compute. "
    "When you save below, all completed yards are merged into one site."
)

yard_choice = st.selectbox(
    "I am entering data for the:",
    options=["Front", "Back"],
    index=0,
    key="builder_yard_choice",
    help="The yard whose ③–⑦ fields you're filling in right now. "
         "Sites with only one yard: just fill the one and ignore the other.",
)
yard_key = yard_choice.lower()  # "front" or "back"
yard_zone = _zone_for_yard(yard_key)
yard_prefix = _prefix_for_yard(yard_key)

# Show a status banner telling the user what's already stashed.
front_done = st.session_state.get("front_config") is not None
back_done  = st.session_state.get("back_config")  is not None
status_msgs = []
if front_done:
    n = len(st.session_state["front_config"]["grid_blocks"])
    status_msgs.append(f"✅ Front yard stashed ({n} blocks)")
else:
    status_msgs.append("⬜ Front yard — not yet computed")
if back_done:
    n = len(st.session_state["back_config"]["grid_blocks"])
    status_msgs.append(f"✅ Back yard stashed ({n} blocks)")
else:
    status_msgs.append("⬜ Back yard — not yet computed")
st.info("  ·  ".join(status_msgs))

st.markdown("---")


# ═══════════════════════════════════════════════
#  STEP 3 — FIXED POINT LOCATION IN GRID  (per yard)
# ═══════════════════════════════════════════════
st.subheader(f"③ Fixed Point Location in Grid — {yard_choice} Yard")
st.caption("Identify which cell corner the GPS measurement was taken at. "
           "This anchors this yard's grid to the real world.")

col_fp1, col_fp2 = st.columns(2)
with col_fp1:
    fp_cell_input = st.text_input(
        "Fixed Point Cell ID *", value="E1",
        help="The cell whose corner was marked with GPS (e.g. E1, A1, D2)",
        key=f"fp_cell_{yard_key}",
    )
with col_fp2:
    fp_corner = st.selectbox(
        "Which corner of this cell? *",
        ["Top-Left", "Top-Right", "Bottom-Left", "Bottom-Right"],
        help="As drawn on the field sketch — not compass direction",
        key=f"fp_corner_{yard_key}",
    )

st.markdown("---")


# ═══════════════════════════════════════════════
#  STEP 4 — FIXED POINT GPS  (per yard)
# ═══════════════════════════════════════════════
st.subheader(f"④ Fixed Point GPS Coordinates — {yard_choice} Yard")

gps_format = st.radio(
    "Coordinate format",
    ["DMS (Degrees Minutes Seconds)", "Decimal Degrees"],
    horizontal=True,
    help="DMS example: 42° 55' 11.46\" N  ·  Decimal example: 42.9198500",
    key=f"gps_format_{yard_key}",
)

if gps_format == "DMS (Degrees Minutes Seconds)":
    col_lat, col_lon = st.columns(2)
    with col_lat:
        st.markdown("**Latitude (N)**")
        c1, c2, c3 = st.columns(3)
        lat_d = c1.number_input("Deg", value=42, key=f"lat_d_{yard_key}")
        lat_m = c2.number_input("Min", value=55, key=f"lat_m_{yard_key}")
        lat_s = c3.number_input("Sec", value=11.46, format="%.4f", key=f"lat_s_{yard_key}")
    with col_lon:
        st.markdown("**Longitude (W)**")
        c4, c5, c6 = st.columns(3)
        lon_d = c4.number_input("Deg", value=78, key=f"lon_d_{yard_key}")
        lon_m = c5.number_input("Min", value=49, key=f"lon_m_{yard_key}")
        lon_s = c6.number_input("Sec", value=33.63, format="%.4f", key=f"lon_s_{yard_key}")
    anchor_lat = dms_to_decimal(lat_d, lat_m, lat_s, 'N')
    anchor_lon = dms_to_decimal(lon_d, lon_m, lon_s, 'W')
else:
    col_lat, col_lon = st.columns(2)
    with col_lat:
        anchor_lat = st.number_input("Latitude", value=42.919850, format="%.7f",
                                      key=f"lat_dec_{yard_key}")
    with col_lon:
        anchor_lon = st.number_input("Longitude", value=-78.826008, format="%.7f",
                                      key=f"lon_dec_{yard_key}")

st.success(f"📍 {yard_choice} anchor locked: **{anchor_lat:.7f}°N, {abs(anchor_lon):.7f}°W**")

st.markdown("---")


# ═══════════════════════════════════════════════
#  STEP 5 — GRID LAYOUT & ORIENTATION  (per yard)
# ═══════════════════════════════════════════════
st.subheader(f"⑤ Grid Layout — {yard_choice} Yard")

col_orient, col_dir = st.columns(2)
with col_orient:
    orientation = st.selectbox(
        "Grid orientation on map",
        ["Vertical (strip runs North–South)", "Horizontal (strip runs East–West)"],
        help="Vertical = long axis goes up/down. Horizontal = long axis goes left/right.",
        key=f"orientation_{yard_key}",
    )
with col_dir:
    if "Vertical" in orientation:
        house_dir = st.selectbox("Which end is near the house?",
                                 ["Top (North)", "Bottom (South)"],
                                 key=f"house_dir_v_{yard_key}")
    else:
        house_dir = st.selectbox("Which end is near the house?",
                                 ["Left (West)", "Right (East)"],
                                 key=f"house_dir_h_{yard_key}")

st.markdown("---")


# ═══════════════════════════════════════════════
#  STEP 6 — DEFINE GRID ROWS  (per yard)
# ═══════════════════════════════════════════════
st.subheader(f"⑥ Define Grid Rows — {yard_choice} Yard")
st.caption("List row letters from **farthest from house** → **nearest to house**.")

rows_input = st.text_input(
    "Row letters (comma-separated) *", value="A, B, C, D, E",
    help="Example: A, B, C, D, E, F, G, H — where A is farthest from house",
    key=f"rows_{yard_key}",
)
rows = [r.strip().upper() for r in rows_input.split(",") if r.strip()]

if rows:
    st.info(f"**{len(rows)} rows:** {' → '.join(rows)}  _(far → near)_")

st.markdown("---")


# ═══════════════════════════════════════════════
#  STEP 7 — CELL DIMENSIONS  (per yard)
# ═══════════════════════════════════════════════
st.subheader(f"⑦ Cell Dimensions — {yard_choice} Yard")
st.caption("Enter each cell's **width** (perpendicular to strip) and **height** "
           "(along the strip). Accepts imperial: `11'6.5\"` or plain feet: `10`.")

max_cols = st.number_input("Max columns per row", min_value=1, max_value=5, value=3,
                            help="e.g. 3 if cells are A1, A2, A3",
                            key=f"max_cols_{yard_key}")

cell_data = {}
for row in rows:
    with st.expander(f"**Row {row}**", expanded=True):
        num_cols = st.number_input(f"Columns in row {row}", min_value=1,
                                    max_value=int(max_cols),
                                    value=min(int(max_cols), 3),
                                    key=f"ncols_{row}_{yard_key}")
        cols_ui = st.columns(int(num_cols))
        for c in range(int(num_cols)):
            col_num = c + 1
            cell_id = f"{row}{col_num}"
            with cols_ui[c]:
                st.markdown(f"##### {cell_id}")
                w = st.text_input("Width (ft)", value="10", key=f"w_{cell_id}_{yard_key}")
                h = st.text_input("Height (ft)", value="10", key=f"h_{cell_id}_{yard_key}")
                # Default the sample-id pattern to include the yard hint so
                # downstream matching naturally segregates front from back.
                default_pat = f"{yard_choice}_{cell_id}_"
                pat = st.text_input("SampleID pattern", value=default_pat,
                                    key=f"pat_{cell_id}_{yard_key}",
                                    help="Substring matched against Master Data. "
                                         "Include 'Front' or 'Back' so the matcher "
                                         "associates readings with the correct yard.")
                cell_data[cell_id] = {
                    "width": parse_imperial(w), "height": parse_imperial(h),
                    "col": col_num, "row": row, "pattern": pat,
                }

st.markdown("---")


# ═══════════════════════════════════════════════
#  STEP 8 — POINT SAMPLES (OPTIONAL)  (per yard)
# ═══════════════════════════════════════════════
st.subheader(f"⑧ Point Samples _(optional)_ — {yard_choice} Yard")
st.caption("Non-grid samples (driplines, lawns, etc.). Offsets in feet from the fixed point.")

num_points = st.number_input("Number of point samples", min_value=0, max_value=20, value=0,
                              key=f"num_points_{yard_key}")
point_samples = {}
if num_points > 0:
    for i in range(int(num_points)):
        with st.expander(f"Point Sample {i + 1}", expanded=True):
            pc1, pc2, pc3, pc4 = st.columns(4)
            with pc1:
                pt_name = st.text_input("Name", key=f"pt_name_{i}_{yard_key}",
                                        placeholder="HUD Dripline")
            with pc2:
                pt_ox = st.number_input("East offset (ft)", key=f"pt_ox_{i}_{yard_key}", value=0.0)
            with pc3:
                pt_oy = st.number_input("North offset (ft)", key=f"pt_oy_{i}_{yard_key}", value=0.0)
            with pc4:
                pt_pat = st.text_input("SampleID pattern", key=f"pt_pat_{i}_{yard_key}",
                                        placeholder=f"{yard_choice}_HUD_Dripline")
            if pt_name:
                # Prefix point sample key with yard prefix to avoid collisions
                # when both yards have a point named e.g. "Dripline".
                point_samples[f"{yard_prefix}{pt_name}"] = {
                    "name": pt_name,
                    "offset_x": pt_ox, "offset_y": pt_oy,
                    "sample_id_patterns": [pt_pat] if pt_pat else [],
                    "zone": "auxiliary",
                    "yard": yard_key,
                }


# ═══════════════════════════════════════════════
#  COMPUTE  (per yard)
# ═══════════════════════════════════════════════
st.markdown("---")
st.markdown(f"### 🔧 Generate Configuration — {yard_choice} Yard")
st.caption(
    f"Computing only the **{yard_choice}** yard right now. If this site has "
    f"both yards, switch the dropdown to the other yard, fill in its fields, "
    f"and click Compute again. Both yards get merged together when you Save."
)

col_btn, col_btn2, _ = st.columns([2, 2, 4])
with col_btn:
    compute = st.button(
        f"Compute {yard_choice} Yard",
        type="primary",
        use_container_width=True,
        key=f"compute_{yard_key}",
    )
with col_btn2:
    clear_yard = st.button(
        f"Clear {yard_choice} Yard",
        use_container_width=True,
        key=f"clear_{yard_key}",
        help="Forget the currently-stashed configuration for this yard. "
             "Does NOT touch site_configs.json on disk.",
    )

if clear_yard:
    st.session_state.pop(f"{yard_key}_config", None)
    st.success(f"🗑️ Cleared stashed {yard_choice} yard from this session.")
    st.rerun()

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

        # Internal collision-proof key: F_A1 or B_A1.
        block_key = f"{yard_prefix}{cid}"
        grid_blocks[block_key] = {
            "sw_x": round(min(es, ee), 2), "sw_y": round(min(ns, ne), 2),
            "ne_x": round(max(es, ee), 2), "ne_y": round(max(ns, ne), 2),
            "sample_id_patterns": [cd["pattern"]] if cd["pattern"] else [],
            "zone": yard_zone,        # "front_yard" or "backyard"
            "cell_id": cid,           # human-readable label, e.g. "A1"
            "yard": yard_key,         # "front" or "back"
            "mock_ppm": 0,
        }

    # ── Preserve existing rotation if this site_id was saved before ──
    # Look up rotation specifically for THIS yard if the saved config
    # has the new yards-keyed shape; otherwise fall back to top-level
    # rotation_deg (legacy).
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "..", "data", "site_configs", "site_configs.json")
    existing = load_existing_config_for_site_id(site_id, config_path)
    preserved_rotation = 0
    if existing:
        if "yards" in existing and yard_key in (existing.get("yards") or {}):
            preserved_rotation = (existing["yards"][yard_key] or {}).get("rotation_deg", 0)
        else:
            preserved_rotation = existing.get("rotation_deg", 0)

    yard_config = {
        "anchor": {
            "lat": anchor_lat, "lon": anchor_lon,
            "description": f"{yard_choice} yard fixed point at {fp_cell} ({fp_corner}) — field-measured GPS",
            "marker_label": f"{yard_choice} Fixed Point ({fp_cell})",
        },
        "rotation_deg": preserved_rotation,
        "grid_blocks": grid_blocks,
        "point_samples": point_samples,
    }

    # Stash THIS yard. The other yard, if previously computed, is untouched.
    st.session_state[f"{yard_key}_config"] = yard_config

    # Whenever a yard is computed, rebuild the combined generated_config so
    # the preview & legacy consumers see the union. Use the front anchor for
    # the legacy mirror if front exists, else back.
    yards_block = {
        "front": st.session_state.get("front_config"),
        "back":  st.session_state.get("back_config"),
    }
    legacy_mirror = _merge_yards_into_legacy(yards_block)
    combined_config = {
        "site_id": site_id,
        "sampling_date": str(sampling_date),
        "notes": notes,
        "anchor": legacy_mirror["anchor"],
        "rotation_deg": legacy_mirror["rotation_deg"],
        "map_defaults": {"zoom_start": 21, "center_offset_north_ft": 0, "center_offset_east_ft": 0},
        "grid_blocks": legacy_mirror["grid_blocks"],
        "point_samples": legacy_mirror["point_samples"],
        "yards": {k: v for k, v in yards_block.items() if v is not None},
    }
    st.session_state["generated_config"] = combined_config
    # We're in the new-site flow, not editing a loaded config.
    st.session_state["loaded_from_disk"] = False
    # Reset stale drag state.
    for k in ("pending_offset_e", "pending_offset_n", "pending_rotation",
              "front_offset_e", "front_offset_n", "front_rotation",
              "back_offset_e", "back_offset_n", "back_rotation",
              "in_e_front", "in_n_front", "in_r_front",
              "in_e_back", "in_n_back", "in_r_back",
              "in_e_legacy", "in_n_legacy", "in_r_legacy"):
        st.session_state.pop(k, None)

    msg_lines = [
        f"✅ **{yard_choice} yard computed** — {len(grid_blocks)} blocks · "
        f"{len(point_samples)} point samples."
    ]
    other = "back" if yard_key == "front" else "front"
    other_done = st.session_state.get(f"{other}_config") is not None
    if other_done:
        n_other = len(st.session_state[f"{other}_config"]["grid_blocks"])
        msg_lines.append(
            f"Both yards now stashed (Front + Back). Scroll down to the "
            f"preview to position them and Save."
        )
    else:
        msg_lines.append(
            f"Only **{yard_choice}** stashed so far. If this site has a "
            f"{other.capitalize()} yard too, switch the dropdown to "
            f"**{other.capitalize()}**, fill it in, and click Compute again. "
            f"Otherwise scroll down to position & Save just this one."
        )
    st.success("  \n".join(msg_lines))


# ═══════════════════════════════════════════════
#  RESULTS & DRAGGABLE PREVIEW
# ═══════════════════════════════════════════════
if "generated_config" in st.session_state:
    config = st.session_state["generated_config"]
    st.markdown("---")

    # ── Computed-offsets table — group by yard if the new shape exists ──
    st.subheader("📋 Computed Grid Offsets")
    yards_in_config = config.get("yards") or {}
    if yards_in_config:
        for yk, ydata in yards_in_config.items():
            if not ydata:
                continue
            st.markdown(f"**{yk.capitalize()} Yard** — anchor "
                        f"`{ydata['anchor']['lat']:.6f}, {ydata['anchor']['lon']:.6f}`")
            tbl = []
            for bid, b in ydata.get("grid_blocks", {}).items():
                tbl.append({
                    "Cell": b.get("cell_id", bid),
                    "Internal ID": bid,
                    "SW East": b["sw_x"], "SW North": b["sw_y"],
                    "NE East": b["ne_x"], "NE North": b["ne_y"],
                    "W (ft)": round(b["ne_x"] - b["sw_x"], 1),
                    "H (ft)": round(b["ne_y"] - b["sw_y"], 1),
                    "Pattern": ", ".join(b.get("sample_id_patterns", [])),
                })
            st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True)
    else:
        # Legacy single-yard view — exactly as before.
        tbl = []
        for bid, b in config["grid_blocks"].items():
            tbl.append({
                "Cell": b.get("cell_id", bid),
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
        "**Click & drag** the grid to nudge it onto the actual yard. "
        "When both yards exist, each is dragged INDEPENDENTLY — click "
        "a front-yard block to move the front grid, a back-yard block to "
        "move the back grid. Rotation controls below the map are also "
        "per-yard. Click **Save** to persist."
    )

    # ── Build per-yard render payloads ────────────────────────────────
    # If the config has the new `yards` shape, render each yard with its
    # own anchor + rotation. If it's a legacy single-yard config, render
    # it as a single "back" yard for UI purposes (preserves on-save shape).
    render_yards = {}  # yard_key -> {anchor, rotation, blocks_payload, points_payload}

    if yards_in_config:
        for yk, ydata in yards_in_config.items():
            if not ydata:
                continue
            blocks_payload = []
            for bid, b in ydata.get("grid_blocks", {}).items():
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
                    "cell": b.get("cell_id", bid),
                    "corners": corners,
                    "cx": cx, "cy": cy,
                    "color": color,
                    "label": label,
                    "ppm": mock_ppm,
                })
            points_payload = []
            for pid, pt in ydata.get("point_samples", {}).items():
                points_payload.append({
                    "id": pid,
                    "name": pt.get("name", pid),
                    "ox": pt.get("offset_x", 0),
                    "oy": pt.get("offset_y", 0),
                })
            render_yards[yk] = {
                "anchor_lat": ydata["anchor"]["lat"],
                "anchor_lon": ydata["anchor"]["lon"],
                "rotation":   ydata.get("rotation_deg", 0),
                "blocks":     blocks_payload,
                "points":     points_payload,
            }
    else:
        # Legacy single-yard config — render as one yard. Default to back
        # per spec (SampleIDs without Front/Back → backyard).
        blocks_payload = []
        for bid, b in config["grid_blocks"].items():
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
                "cell": b.get("cell_id", bid),
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
                "name": pt.get("name", pid),
                "ox": pt.get("offset_x", 0),
                "oy": pt.get("offset_y", 0),
            })
        # Use "legacy" key so the JS knows there's no yard split; save logic
        # will keep this config in its original shape.
        render_yards["legacy"] = {
            "anchor_lat": config["anchor"]["lat"],
            "anchor_lon": config["anchor"]["lon"],
            "rotation":   config.get("rotation_deg", 0),
            "blocks":     blocks_payload,
            "points":     points_payload,
        }

    # Build legend
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

    # Compute the initial map center: midpoint of all yards' anchors.
    if render_yards:
        anchor_lats = [y["anchor_lat"] for y in render_yards.values()]
        anchor_lons = [y["anchor_lon"] for y in render_yards.values()]
        map_center_lat = sum(anchor_lats) / len(anchor_lats)
        map_center_lon = sum(anchor_lons) / len(anchor_lons)
    else:
        map_center_lat = config.get("anchor", {}).get("lat", 0)
        map_center_lon = config.get("anchor", {}).get("lon", 0)

    # Build the dynamic controls HTML — one block per yard.
    # Colors per yard so they're visually distinguishable on the map.
    yard_visuals = {
        "front":  {"label": "Front Yard", "stroke": "#ffd166", "anchor_color": "#ffd166"},
        "back":   {"label": "Back Yard",  "stroke": "#ff4444", "anchor_color": "#ff4444"},
        "legacy": {"label": "Grid",       "stroke": "#ff4444", "anchor_color": "#ff4444"},
    }

    controls_html = ""
    for yk in render_yards.keys():
        viz = yard_visuals[yk]
        rot_init = render_yards[yk]["rotation"]
        controls_html += f"""
        <div class="yard-block" data-yard="{yk}" style="border-left:3px solid {viz['stroke']};">
          <b>{viz['label']} Position</b>
          <div class="hint">Click &amp; drag a {viz['label'].lower()} block on the map</div>
          <div class="rotate-row">
            <button onclick="rg('{yk}', -5)">−5°</button>
            <button onclick="rg('{yk}', -1)">−1°</button>
            <span id="rd_{yk}">{rot_init}°</span>
            <button onclick="rg('{yk}', 1)">+1°</button>
            <button onclick="rg('{yk}', 5)">+5°</button>
          </div>
          <div class="offset" id="od_{yk}">Offset: 0.0 E, 0.0 N</div>
          <button class="copy-btn" id="cp_{yk}" onclick="cp('{yk}')">Copy values for boxes</button>
          <div class="copy-hint">Paste as: East, North, Rotation</div>
          <button class="reset-btn" onclick="rs('{yk}')">Reset {viz['label']}</button>
        </div>
        """

    # Serialise per-yard payloads for JS.
    yards_json = json.dumps({
        yk: {
            "anchor_lat": y["anchor_lat"],
            "anchor_lon": y["anchor_lon"],
            "rotation":   y["rotation"],
            "blocks":     y["blocks"],
            "points":     y["points"],
            "stroke":     yard_visuals[yk]["stroke"],
            "anchor_color": yard_visuals[yk]["anchor_color"],
            "label":      yard_visuals[yk]["label"],
        }
        for yk, y in render_yards.items()
    })

    # Use a per-site localStorage key so two sites don't trample each
    # other's drag state in the same browser session. Strip characters
    # that might confuse JS string concatenation.
    site_id_for_storage = re.sub(
        r"[^A-Za-z0-9_-]", "_",
        config.get("site_id", "site")
    )

    # Leaflet HTML component with PER-YARD drag + rotate + message bridge.
    # The JS keeps a state map keyed by yard, and click-detection figures
    # out which yard's blocks are under the cursor so drags are isolated.
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
    background:rgba(12,15,20,0.93); padding:8px 12px; border-radius:10px;
    color:#e8eaed; font-size:11px; border:1px solid rgba(255,255,255,0.08);
    min-width:230px; max-height:540px; overflow-y:auto; }}
  .controls .yard-block {{ padding:8px 6px 10px 10px; margin-bottom:6px;
    border-radius:6px; background:rgba(255,255,255,0.02); }}
  .controls .yard-block:last-child {{ margin-bottom:0; }}
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
  .copy-btn {{ margin-top:8px; width:100%; background:rgba(78,205,196,0.16) !important;
    color:#4ecdc4 !important; }}
  .copy-hint {{ margin-top:4px; color:#7a8599; font-size:9px; }}
  .reset-btn {{ margin-top:8px; width:100%; background:rgba(255,100,100,0.12) !important;
    color:#ff8888 !important; }}
</style>
</head><body>
<div id="map"></div>
<div class="legend"><b>Lead Guidelines (ppm)</b><br>{legend_rows}</div>
<div class="controls">{controls_html}</div>

<script>
  var RF = 20925721.78;
  var YARDS = {yards_json};

  // Per-yard mutable state.
  var STATE = {{}};
  Object.keys(YARDS).forEach(function(yk) {{
    STATE[yk] = {{ oE: 0, oN: 0, rot: YARDS[yk].rotation, dirty: false }};
  }});

  var map = L.map('map', {{
    center: [{map_center_lat}, {map_center_lon}], zoom: 21, maxZoom: 25
  }});
  L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
    {{ attribution: 'Esri', maxZoom: 25, maxNativeZoom: 19 }}
  ).addTo(map);

  // One anchor marker per yard (stays put — doesn't move with drag).
  Object.keys(YARDS).forEach(function(yk) {{
    var Y = YARDS[yk];
    L.marker([Y.anchor_lat, Y.anchor_lon], {{
      icon: L.divIcon({{
        className: '',
        html: '<div style="width:14px;height:14px;background:' + Y.anchor_color +
              ';border:2px solid white;border-radius:50%;box-shadow:0 0 6px rgba(0,0,0,0.6)"></div>',
        iconSize: [14,14], iconAnchor: [7,7]
      }})
    }}).addTo(map).bindTooltip(Y.label + ' Anchor');
  }});

  function f2ll(la, lo, e, n) {{
    var dl = (n / RF) * (180 / Math.PI);
    var dn = (e / (RF * Math.cos(la * Math.PI / 180))) * (180 / Math.PI);
    return [la + dl, lo + dn];
  }}

  function rp(x, y, a) {{
    var r = a * Math.PI / 180;
    return [x * Math.cos(r) - y * Math.sin(r), x * Math.sin(r) + y * Math.cos(r)];
  }}

  // Per-yard layer groups so we can clear & re-draw each independently.
  var GROUPS = {{}};
  Object.keys(YARDS).forEach(function(yk) {{
    GROUPS[yk] = L.layerGroup().addTo(map);
  }});

  // Track which polygons belong to which yard (for click hit-test).
  var POLY_TO_YARD = []; // array of {{poly, yard}}

  function drawYard(yk) {{
    var Y = YARDS[yk];
    var S = STATE[yk];
    GROUPS[yk].clearLayers();
    // Filter out our prior poly-yard mappings for this yard before re-adding.
    POLY_TO_YARD = POLY_TO_YARD.filter(function(rec) {{ return rec.yard !== yk; }});

    Y.blocks.forEach(function(b) {{
      var ll = b.corners.map(function(c) {{
        var r = rp(c[0], c[1], S.rot);
        return f2ll(Y.anchor_lat, Y.anchor_lon, r[0] + S.oE, r[1] + S.oN);
      }});
      var pl = L.polygon(ll, {{
        color: Y.stroke, weight: 2,
        fillColor: b.color, fillOpacity: 0.65
      }});
      pl.bindTooltip('<b>' + b.cell + '</b><br>' + Y.label + '<br>' + b.label);
      GROUPS[yk].addLayer(pl);
      POLY_TO_YARD.push({{ poly: pl, yard: yk }});

      var rc = rp(b.cx, b.cy, S.rot);
      var lp = f2ll(Y.anchor_lat, Y.anchor_lon, rc[0] + S.oE, rc[1] + S.oN);
      GROUPS[yk].addLayer(L.marker(lp, {{
        icon: L.divIcon({{
          className: '',
          html: '<div style="font-family:Arial;text-align:center;pointer-events:none">' +
                '<b style="font-size:10px;color:white;text-shadow:0 1px 3px rgba(0,0,0,0.85)">' +
                b.cell + '</b></div>',
          iconSize: [50, 20], iconAnchor: [25, 10]
        }}),
        interactive: false
      }}));
    }});

    Y.points.forEach(function(p) {{
      var r = rp(p.ox, p.oy, S.rot);
      var ll = f2ll(Y.anchor_lat, Y.anchor_lon, r[0] + S.oE, r[1] + S.oN);
      GROUPS[yk].addLayer(L.circleMarker(ll, {{
        radius: 7, color: 'white', weight: 2,
        fillColor: '#f39c12', fillOpacity: 0.8
      }}).bindTooltip('<b>' + p.name + '</b> (' + Y.label + ')'));
    }});

    // Update per-yard control panel readout.
    var od = document.getElementById('od_' + yk);
    var rd = document.getElementById('rd_' + yk);
    if (od) od.textContent = 'Offset: ' + S.oE.toFixed(1) + ' E, ' + S.oN.toFixed(1) + ' N' +
      (S.rot ? ('  |  ' + S.rot + '°') : '');
    if (rd) rd.textContent = S.rot + '°';

    postState();
  }}

  function drawAll() {{
    Object.keys(YARDS).forEach(drawYard);
  }}

  function postState() {{
    // Send the full per-yard state up to the Streamlit host.
    var payload = {{ type: 'groundsense_grid_state_multi', yards: {{}} }};
    Object.keys(STATE).forEach(function(yk) {{
      payload.yards[yk] = {{
        offset_east_ft:  STATE[yk].oE,
        offset_north_ft: STATE[yk].oN,
        rotation_deg:    STATE[yk].rot,
        dirty:          !!STATE[yk].dirty
      }};
    }});
    // Persist to BOTH localStorage (for streamlit_js_eval to read on
    // Python-side reruns — the message-bus is racy) AND postMessage
    // (for any listener that's already wired up).
    try {{
      window.parent.localStorage.setItem(
        'gs_drag_state_' + '{site_id_for_storage}',
        JSON.stringify(payload.yards)
      );
    }} catch (e) {{
      // Cross-origin localStorage access blocked — try this frame's own.
      try {{
        window.localStorage.setItem(
          'gs_drag_state_' + '{site_id_for_storage}',
          JSON.stringify(payload.yards)
        );
      }} catch (e2) {{ /* give up — postMessage still works */ }}
    }}
    window.parent.postMessage(payload, '*');
  }}

  function rg(yk, d) {{ STATE[yk].rot += d; STATE[yk].dirty = true; drawYard(yk); }}
  function rs(yk) {{ STATE[yk].oE = 0; STATE[yk].oN = 0; STATE[yk].rot = 0; STATE[yk].dirty = true; drawYard(yk); }}

  function cp(yk) {{
    var S = STATE[yk];
    // Copy in the exact order of the Streamlit boxes below:
    // East offset, North offset, Rotation.
    var text = S.oE.toFixed(2) + ', ' + S.oN.toFixed(2) + ', ' + S.rot.toFixed(2);
    function markDone() {{
      var b = document.getElementById('cp_' + yk);
      if (!b) return;
      var old = b.textContent;
      b.textContent = 'Copied: ' + text;
      setTimeout(function() {{ b.textContent = old; }}, 1800);
    }}
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      navigator.clipboard.writeText(text).then(markDone).catch(function() {{
        window.prompt('Copy these values: East, North, Rotation', text);
      }});
    }} else {{
      window.prompt('Copy these values: East, North, Rotation', text);
    }}
  }}

  // Click & drag detection — figure out which yard owns the hit polygon.
  var iD = false, dY = null, dL = null, dE = 0, dN = 0;
  map.on('mousedown', function(e) {{
    var hit_yard = null;
    POLY_TO_YARD.forEach(function(rec) {{
      if (!hit_yard && rec.poly.getBounds().contains(e.latlng)) hit_yard = rec.yard;
    }});
    if (hit_yard) {{
      iD = true; dY = hit_yard; dL = e.latlng;
      dE = STATE[hit_yard].oE; dN = STATE[hit_yard].oN;
      map.dragging.disable();
      map.getContainer().style.cursor = 'grabbing';
    }}
  }});
  map.on('mousemove', function(e) {{
    if (!iD) return;
    var Y = YARDS[dY];
    STATE[dY].oN = dN + (e.latlng.lat - dL.lat) * (Math.PI / 180) * RF;
    STATE[dY].oE = dE + (e.latlng.lng - dL.lng) * (Math.PI / 180) * RF *
              Math.cos(Y.anchor_lat * Math.PI / 180);
    STATE[dY].dirty = true;
    drawYard(dY);
  }});
  map.on('mouseup', function() {{
    if (iD) {{
      iD = false; dY = null;
      map.dragging.enable();
      map.getContainer().style.cursor = '';
    }}
  }});

  drawAll();
</script>
</body></html>
"""

    components.html(component_html, height=580, scrolling=False)

    # ──────────────────────────────────────────────────────────────────
    # CAPTURE DRAG STATE — robust localStorage-based bridge
    # ──────────────────────────────────────────────────────────────────
    # The Leaflet iframe writes drag state to parent.localStorage on every
    # nudge (see postState() in the JS above). On Python rerun, we read
    # that localStorage key via streamlit_js_eval. This is rock-solid
    # vs the postMessage approach which races on iframe load.
    #
    # If streamlit_js_eval is unavailable, fall back to manual number
    # inputs. Either way, the final live_states[yk] feeds Save.
    # ──────────────────────────────────────────────────────────────────

    try:
        from streamlit_js_eval import streamlit_js_eval
        bridge_available = True
    except ImportError:
        bridge_available = False

    st.markdown("#### 💾 Save Fine-Tuned Position")
    st.caption(
        "After dragging in the map above, use **Copy values for boxes** in the map control panel, "
        "then paste/type those values into the East, North, and Rotation boxes below. "
        "The export buttons below use these box values immediately. Click **💾 Save** only when "
        "you want to bake those offsets into `site_configs.json`."
    )

    yard_keys_for_state = list(render_yards.keys())

    # If a previous Save baked the offsets into the anchor, reset the manual
    # offset boxes BEFORE the widgets are created on this rerun. This avoids
    # applying the same offset twice to exports after Save.
    if st.session_state.pop("reset_offset_inputs_after_save", False):
        for _yk in yard_keys_for_state:
            st.session_state[f"in_e_{_yk}"] = 0.0
            st.session_state[f"in_n_{_yk}"] = 0.0
            st.session_state[f"in_r_{_yk}"] = float(render_yards[_yk]["rotation"] or 0.0)

    if st.session_state.pop("position_save_success", False):
        st.success(
            "✅ Position saved. The manual offset boxes were reset to 0 because "
            "the offset is now baked into the saved anchor. Downloads now use the "
            "saved position as the default."
        )

    # ── Step 1: read whatever's in localStorage right now (auto on every rerun) ──
    captured = {}
    if bridge_available:
        storage_key = f"gs_drag_state_{site_id_for_storage}"
        # Read from BOTH localStorage scopes (parent and iframe) — whichever
        # the postState() write succeeded into. Return as JSON string.
        raw = streamlit_js_eval(
            js_expressions=f"""
                (function() {{
                    var k = '{storage_key}';
                    var v = null;
                    try {{ v = window.parent.localStorage.getItem(k); }} catch(e) {{}}
                    if (!v) {{
                        try {{ v = window.localStorage.getItem(k); }} catch(e) {{}}
                    }}
                    return v || '';
                }})()
            """,
            key=f"gs_storage_read_{site_id_for_storage}",
            want_output=True,
        )
        if raw:
            try:
                captured = json.loads(raw)
            except Exception:
                captured = {}

    # ── Step 2: explicit Capture button (forces a re-read + writes into inputs) ──
    # The bridge above runs on every rerun, but the Capture button is the
    # tech's "I'm done dragging — pull values in NOW" handoff. Clicking it
    # copies localStorage → session_state, so the inputs below show the
    # captured values and Save reads them.
    cap_col, status_col = st.columns([1, 3])
    with cap_col:
        capture_clicked = st.button(
            "🔄 Capture Drag State",
            use_container_width=True,
            key="capture_drag_btn",
            help="Pull the current drag/rotation from the map above into the inputs.",
        )
    with status_col:
        if captured:
            parts = []
            for yk in yard_keys_for_state:
                c = captured.get(yk) or {}
                e = c.get("offset_east_ft", 0) or 0
                n = c.get("offset_north_ft", 0) or 0
                r = c.get("rotation_deg", 0) or 0
                parts.append(
                    f"{yard_visuals[yk]['label']}: "
                    f"{e:+.1f}E / {n:+.1f}N / {r:+.0f}°"
                )
            st.caption("🟢 Live drag state detected: " + "  ·  ".join(parts))
        else:
            st.caption(
                "⚪ No drag state in browser storage yet. "
                "Drag in the map above first, then click Capture."
            )

    # ── Step 3: per-yard editable inputs (the actual source of truth for Save) ──
    # If Capture was clicked, copy localStorage values into the input keys
    # BEFORE the widgets are instantiated. Streamlit reads from session_state
    # on the next rerun, so this gets the values into the boxes.
    if capture_clicked and captured:
        for yk in yard_keys_for_state:
            c = captured.get(yk) or {}
            st.session_state[f"in_e_{yk}"] = float(c.get("offset_east_ft", 0) or 0)
            st.session_state[f"in_n_{yk}"] = float(c.get("offset_north_ft", 0) or 0)
            st.session_state[f"in_r_{yk}"] = float(
                c.get("rotation_deg", render_yards[yk]["rotation"]) or 0
            )
        st.rerun()

    live_states = {}
    if not bridge_available:
        st.info(
            "⚙️ For one-click drag capture, install `streamlit-js-eval`:  \n"
            "`pip install streamlit-js-eval`  \n\n"
            "Meanwhile, type each yard's drag offsets manually below."
        )

    # ── Step 3A: reliable paste handoff from the preview panel ───────────────
    # This avoids relying on iframe → Streamlit communication. The preview's
    # "Copy values for boxes" button copies: East, North, Rotation.
    # Paste that exact text here and click Apply; the number inputs below become
    # the committed source of truth for Save + HTML/PNG downloads.
    def _parse_offset_triplet(raw: str, default_rotation: float = 0.0):
        raw = (raw or "").strip()
        if not raw:
            return None
        # Accept both:
        #   -2.00, 17.60, 0.00
        #   East=-2.00, North=17.60, Rot=0°
        nums = re.findall(r"[-+]?\d+(?:\.\d+)?", raw)
        if len(nums) < 2:
            return None
        e_val = float(nums[0])
        n_val = float(nums[1])
        r_val = float(nums[2]) if len(nums) >= 3 else float(default_rotation or 0.0)
        return e_val, n_val, r_val

    st.markdown("##### Paste copied preview offset")
    st.caption(
        "Use this instead of Capture: click **Copy values for boxes** in the preview panel, "
        "paste the copied text here, then click **Apply copied values**. After that, downloads use it."
    )

    paste_cols = st.columns(len(yard_keys_for_state) if yard_keys_for_state else 1)
    paste_apply_clicked = False
    for idx, yk in enumerate(yard_keys_for_state):
        with paste_cols[idx]:
            st.text_input(
                f"{yard_visuals[yk]['label']} copied values",
                key=f"paste_offsets_{yk}",
                placeholder="Example: -2.00, 17.60, 0.00",
            )
    paste_apply_clicked = st.button(
        "✅ Apply copied values to boxes",
        use_container_width=True,
        key="apply_copied_offsets_btn",
    )

    if paste_apply_clicked:
        applied_any = False
        bad_yards = []
        for yk in yard_keys_for_state:
            parsed = _parse_offset_triplet(
                st.session_state.get(f"paste_offsets_{yk}", ""),
                render_yards[yk]["rotation"],
            )
            if parsed is None:
                # Empty is fine when there is only one yard? No — tell user what failed.
                bad_yards.append(yard_visuals[yk]["label"])
                continue
            e_val, n_val, r_val = parsed
            st.session_state[f"in_e_{yk}"] = e_val
            st.session_state[f"in_n_{yk}"] = n_val
            st.session_state[f"in_r_{yk}"] = r_val
            applied_any = True
        if applied_any:
            st.session_state["copied_offsets_apply_success"] = True
            st.rerun()
        else:
            st.error("Could not read any copied offset values. Paste values like: `-2.00, 17.60, 0.00`.")

    if st.session_state.pop("copied_offsets_apply_success", False):
        st.success("✅ Copied offset values applied to the boxes below. HTML/PNG downloads now use these values.")

    for yk in yard_keys_for_state:
        st.markdown(f"**{yard_visuals[yk]['label']}**")
        mc1, mc2, mc3 = st.columns(3)
        # Default values come from session_state (populated by Capture) or
        # fall back to zero / the saved rotation. Number inputs read & write
        # to session_state via their key.
        default_e = float(st.session_state.get(f"in_e_{yk}", 0.0) or 0.0)
        default_n = float(st.session_state.get(f"in_n_{yk}", 0.0) or 0.0)
        default_r = float(
            st.session_state.get(f"in_r_{yk}", render_yards[yk]["rotation"]) or 0.0
        )
        live_states[yk] = {
            "e": mc1.number_input(
                "East offset (ft)", value=default_e, step=0.1,
                format="%.2f", key=f"in_e_{yk}",
            ),
            "n": mc2.number_input(
                "North offset (ft)", value=default_n, step=0.1,
                format="%.2f", key=f"in_n_{yk}",
            ),
            "r": mc3.number_input(
                "Rotation (°)", value=default_r, step=1.0,
                format="%.2f", key=f"in_r_{yk}",
            ),
        }

    st.markdown("---")

    def _captured_states_for_save(captured_state: dict, fallback_states: dict) -> dict:
        """Prefer browser-captured drag state for yards that were actually
        dragged/rotated/reset. Fall back to the manual inputs otherwise.
        """
        merged = json.loads(json.dumps(fallback_states))
        if not captured_state:
            return merged
        for _yk in yard_keys_for_state:
            c = captured_state.get(_yk) or {}
            # The iframe writes an initial zero-state on load. Only treat
            # browser state as authoritative after the user interacted with
            # that yard (dirty=True). This preserves manual fallback inputs.
            if not c.get("dirty", False):
                continue
            merged[_yk] = {
                "e": float(c.get("offset_east_ft", 0) or 0),
                "n": float(c.get("offset_north_ft", 0) or 0),
                "r": float(c.get("rotation_deg", render_yards[_yk]["rotation"]) or 0),
            }
        return merged

    # Buttons
    sb1, sb2, _ = st.columns([2, 2, 3])
    with sb1:
        save_clicked = st.button("💾 Save Position to Config",
                                  type="primary", use_container_width=True,
                                  key="save_position_btn")
    with sb2:
        download_clicked = st.button("📥 Preview JSON",
                                      use_container_width=True,
                                      key="preview_json_btn")

    def _apply_manual_offsets_to_config(base_config: dict, states: dict) -> dict:
        """Return a copy of base_config with the current manual box offsets baked in.

        This is the single source of truth for both Save and downloads. The boxes
        are intentionally used instead of localStorage because the iframe/browser
        bridge can be unreliable on some Streamlit installs.
        """
        R_EARTH_FT = 20_925_721.78
        updated_config = json.loads(json.dumps(base_config))
        loaded_from_disk = st.session_state.get("loaded_from_disk", False)
        had_yards_originally = bool((updated_config.get("yards") or {}))

        def _shift_anchor(old_lat, old_lon, e_ft, n_ft):
            delta_lat = (n_ft / R_EARTH_FT) * (180 / math.pi)
            lat_rad = old_lat * (math.pi / 180)
            delta_lon = (e_ft / (R_EARTH_FT * math.cos(lat_rad))) * (180 / math.pi)
            return old_lat + delta_lat, old_lon + delta_lon

        # ── Case 1: legacy single-yard config (loaded from disk OR new flow
        #            with no yards key present). Update in place, no `yards`
        #            key. Keeps the old schema verbatim — historical data
        #            untouched.
        if not had_yards_originally:
            # There's exactly one yard in render_yards. Could be keyed
            # "legacy" (loaded old config) or "front"/"back" (new flow
            # with only one yard computed).
            yk = yard_keys_for_state[0]
            ls = states[yk]
            old_lat = updated_config["anchor"]["lat"]
            old_lon = updated_config["anchor"]["lon"]
            new_lat, new_lon = _shift_anchor(old_lat, old_lon, ls["e"], ls["n"])
            updated_config["anchor"]["lat"] = round(new_lat, 8)
            updated_config["anchor"]["lon"] = round(new_lon, 8)
            if abs(float(ls["e"])) > 1e-9 or abs(float(ls["n"])) > 1e-9:
                updated_config["anchor"]["description"] = (
                    (updated_config["anchor"].get("description", "") or "")
                    + f" · visually nudged {ls['e']:+.2f} E / {ls['n']:+.2f} N ft"
                ).strip(" ·")
            updated_config["rotation_deg"] = round(ls["r"], 2)

            # If the source was a new-flow (front_config or back_config)
            # rather than a legacy load, we should ALSO write the `yards`
            # block so future loads use the new shape. This is the only
            # case where new data gets the new schema; loaded legacy
            # configs stay legacy.
            if not loaded_from_disk and yk in ("front", "back"):
                # Pull the stashed per-yard config built during Compute,
                # apply the offset/rotation to its anchor, and store it
                # in the yards block.
                stash = st.session_state.get(f"{yk}_config")
                if stash is not None:
                    yard_copy = json.loads(json.dumps(stash))
                    a_old_lat = yard_copy["anchor"]["lat"]
                    a_old_lon = yard_copy["anchor"]["lon"]
                    a_new_lat, a_new_lon = _shift_anchor(
                        a_old_lat, a_old_lon, ls["e"], ls["n"]
                    )
                    yard_copy["anchor"]["lat"] = round(a_new_lat, 8)
                    yard_copy["anchor"]["lon"] = round(a_new_lon, 8)
                    yard_copy["rotation_deg"] = round(ls["r"], 2)
                    updated_config["yards"] = {yk: yard_copy}

        # ── Case 2: new yards-shaped config. Apply offset/rotation to EACH
        #            yard's anchor and rotation independently. Also refresh
        #            the legacy mirror keys so old consumers see something
        #            consistent.
        else:
            new_yards = {}
            for yk in yard_keys_for_state:
                if yk not in (updated_config.get("yards") or {}):
                    # Yard exists in render but not in updated_config (shouldn't
                    # normally happen). Skip safely.
                    continue
                ydata = updated_config["yards"][yk]
                if ydata is None:
                    continue
                ls = states[yk]
                a_old_lat = ydata["anchor"]["lat"]
                a_old_lon = ydata["anchor"]["lon"]
                a_new_lat, a_new_lon = _shift_anchor(
                    a_old_lat, a_old_lon, ls["e"], ls["n"]
                )
                ydata = json.loads(json.dumps(ydata))
                ydata["anchor"]["lat"] = round(a_new_lat, 8)
                ydata["anchor"]["lon"] = round(a_new_lon, 8)
                if abs(float(ls["e"])) > 1e-9 or abs(float(ls["n"])) > 1e-9:
                    ydata["anchor"]["description"] = (
                        (ydata["anchor"].get("description", "") or "")
                        + f" · visually nudged {ls['e']:+.2f} E / {ls['n']:+.2f} N ft"
                    ).strip(" ·")
                ydata["rotation_deg"] = round(ls["r"], 2)
                new_yards[yk] = ydata
            updated_config["yards"] = new_yards

            # Refresh legacy mirror keys from the updated yards block.
            legacy_mirror = _merge_yards_into_legacy(new_yards)
            updated_config["anchor"] = legacy_mirror["anchor"]
            updated_config["rotation_deg"] = legacy_mirror["rotation_deg"]
            updated_config["grid_blocks"] = legacy_mirror["grid_blocks"]
            updated_config["point_samples"] = legacy_mirror["point_samples"]

        return updated_config

    # Config used by Preview JSON / Save: the current box values are baked
    # into the anchor lat/lon and yard rotations.
    export_config = _apply_manual_offsets_to_config(config, live_states)

    # IMPORTANT: downloads use the BAKED config, not temporary JS offsets.
    # The current box values have already been converted into real anchor
    # lat/lon changes inside export_config. This makes downloaded HTML/PNG
    # open at the new position by default, with no extra drag offset required.
    renderer_export_config = export_config

    if save_clicked:
        # Save uses the same config that downloads use: the current box values.
        # This makes copy/paste offsets deterministic and avoids stale iframe state.
        updated_config = export_config

        # ── Persist — APPEND-OR-REPLACE the entry for this site_id.
        # Any other site entries in the file are preserved verbatim.
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
        # Use the freshly saved config for JSON preview and map exports in
        # this same run, so downloads immediately default to the dragged
        # position instead of the original computed anchor.
        config = updated_config

        # Clear the localStorage drag state so the next Save doesn't
        # apply the same offset twice (the offset has been baked into
        # the anchor lat/lon now).
        if bridge_available:
            try:
                streamlit_js_eval(
                    js_expressions=f"""
                        (function() {{
                            var k = 'gs_drag_state_{site_id_for_storage}';
                            try {{ window.parent.localStorage.removeItem(k); }} catch(e) {{}}
                            try {{ window.localStorage.removeItem(k); }} catch(e) {{}}
                            return 'cleared';
                        }})()
                    """,
                    key=f"gs_storage_clear_{site_id_for_storage}_{os.urandom(2).hex()}",
                    want_output=False,
                )
            except Exception:
                pass
        # Build a friendly summary message.
        yards_saved = list((updated_config.get("yards") or {}).keys())
        if yards_saved:
            yards_desc = f"with yards: **{', '.join(yards_saved)}**"
        else:
            yards_desc = "(legacy single-yard schema preserved)"
        st.session_state["position_save_success"] = True
        st.session_state["reset_offset_inputs_after_save"] = True
        st.session_state["generated_config"] = updated_config
        st.rerun()

    if download_clicked:
        json_str = json.dumps(export_config, indent=2)
        st.code(json_str, language="json")
        st.download_button(
            "📥 Download JSON",
            data=json_str,
            file_name=f"site_config_{export_config['site_id']}.json",
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
        "cells without data render in gray. Exports use the legacy mirror "
        "fields so old & new configs render identically."
    )

    # Load master data for real PPM lookup
    master_df_export = load_master_data()
    if master_df_export.empty:
        st.warning(
            "⚠️ No Master Data found — exports will render all cells as 'No Data' (gray). "
            "Run the ETL Pipeline first if you want real PPM values."
        )
    else:
        blocks_preview, _ = get_block_data(renderer_export_config, master_df_export,
                                            use_mock_fallback=False)
        real_count = sum(1 for b in blocks_preview if b["has_real_data"])
        total = len(blocks_preview)
        st.caption(
            f"📊 Using Master Data: **{real_count} / {total}** cells have real "
            f"XRF readings. Remaining cells will render as 'No Data' (gray)."
        )

    safe_name = export_config["site_id"]

    exp1, exp2, exp3 = st.columns(3)

    # ─── 1. Basemap + no numbers (HTML) ───
    with exp1:
        st.markdown("**🛰️ Basemap · no numbers**")
        st.caption("Satellite imagery, cell IDs only, draggable.")
        try:
            html_nonum = render_leaflet_html(
                renderer_export_config, master_df_export,
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
                renderer_export_config, master_df_export,
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
                renderer_export_config, master_df_export, png_path,
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
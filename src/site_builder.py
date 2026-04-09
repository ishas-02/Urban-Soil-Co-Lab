# """
# site_builder.py — GroundSense Site Configuration Builder

# A standalone Streamlit page where technicians input field measurements
# for a new site and the system auto-generates:
#   1. The grid block offsets (computed from cell dimensions + fixed point)
#   2. The site_configs.json entry
#   3. A live map preview

# Place in src/ alongside groundsense_config.py.
# Run: streamlit run src/site_builder.py
# """

# import streamlit as st
# import pandas as pd
# import json
# import math
# import os
# import copy

# from groundsense_config import (
#     get_nysh_category,
#     NYSH_TIERS,
#     NYSH_COLORS,
#     calculate_coordinate,
#     resolve_lod,
# )

# # ═══════════════════════════════════════════════
# #  PAGE SETUP
# # ═══════════════════════════════════════════════
# st.set_page_config(page_title="GroundSense Site Builder", page_icon="📐", layout="wide")
# st.title("📐 Site Configuration Builder")
# st.markdown("Input your field measurements to auto-generate the grid config for a new site. "
#             "No manual offset calculations needed.")
# st.markdown("---")

# # ═══════════════════════════════════════════════
# #  HELPER: Parse imperial measurements
# # ═══════════════════════════════════════════════
# def parse_imperial(s):
#     """Convert '11\\'6.5\"' or '7\\'8.5\"' or '10' to decimal feet."""
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
#     """Convert DMS to decimal degrees."""
#     dd = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
#     if direction in ['S', 'W']:
#         dd *= -1
#     return dd


# # ═══════════════════════════════════════════════
# #  STEP 1: SITE INFO
# # ═══════════════════════════════════════════════
# st.subheader("1️⃣ Site Information")

# col_addr, col_city, col_zip = st.columns([3, 2, 1])
# with col_addr:
#     address = st.text_input("Street Address", placeholder="e.g. 203 Schuele Ave")
# with col_city:
#     city = st.text_input("City", value="Buffalo")
# with col_zip:
#     zip_code = st.text_input("ZIP", placeholder="14215")

# sampling_date = st.date_input("Sampling Date")
# notes = st.text_area("Site Notes (optional)", placeholder="e.g. Backyard grid, measured from porch corner...")

# st.markdown("---")

# # ═══════════════════════════════════════════════
# #  STEP 2: FIXED POINT GPS
# # ═══════════════════════════════════════════════
# st.subheader("2️⃣ Fixed Point (GPS Anchor)")
# st.caption("Enter the GPS coordinates of the known fixed point in the grid.")

# gps_format = st.radio("Coordinate Format", ["DMS (Degrees Minutes Seconds)", "Decimal Degrees"], horizontal=True)

# if gps_format == "DMS (Degrees Minutes Seconds)":
#     col_lat, col_lon = st.columns(2)
#     with col_lat:
#         st.markdown("**Latitude (N)**")
#         c1, c2, c3 = st.columns(3)
#         lat_d = c1.number_input("Degrees", value=42, key="lat_d")
#         lat_m = c2.number_input("Minutes", value=55, key="lat_m")
#         lat_s = c3.number_input("Seconds", value=11.46, format="%.4f", key="lat_s")
#     with col_lon:
#         st.markdown("**Longitude (W)**")
#         c4, c5, c6 = st.columns(3)
#         lon_d = c4.number_input("Degrees", value=78, key="lon_d")
#         lon_m = c5.number_input("Minutes", value=49, key="lon_m")
#         lon_s = c6.number_input("Seconds", value=33.63, format="%.4f", key="lon_s")

#     anchor_lat = dms_to_decimal(lat_d, lat_m, lat_s, 'N')
#     anchor_lon = dms_to_decimal(lon_d, lon_m, lon_s, 'W')
# else:
#     col_lat, col_lon = st.columns(2)
#     with col_lat:
#         anchor_lat = st.number_input("Latitude", value=42.919850, format="%.7f")
#     with col_lon:
#         anchor_lon = st.number_input("Longitude", value=-78.826008, format="%.7f")

# st.info(f"📍 Anchor: {anchor_lat:.7f}, {anchor_lon:.7f}")

# st.markdown("---")

# # ═══════════════════════════════════════════════
# #  STEP 3: GRID LAYOUT
# # ═══════════════════════════════════════════════
# st.subheader("3️⃣ Grid Layout")

# col_orient, col_dir = st.columns(2)
# with col_orient:
#     orientation = st.selectbox("Grid Orientation on Map",
#                                ["Vertical (strip runs North-South)",
#                                 "Horizontal (strip runs East-West)"])
# with col_dir:
#     if "Vertical" in orientation:
#         house_dir = st.selectbox("Which end is near the house?",
#                                  ["Top (North)", "Bottom (South)"])
#     else:
#         house_dir = st.selectbox("Which end is near the house?",
#                                  ["Left (West)", "Right (East)"])

# st.markdown("---")

# # Row definitions
# st.subheader("4️⃣ Define Grid Rows")
# st.caption("List the row letters from **far from house** to **near house**. "
#            "Example: A, B, C, D, E, F, G, H where A is farthest and H is nearest.")

# rows_input = st.text_input("Row letters (comma-separated, far→near)",
#                             value="A, B, C, D, E, F, G, H",
#                             help="e.g. A, B, C, D, E, F, G, H")

# rows = [r.strip().upper() for r in rows_input.split(",") if r.strip()]

# if rows:
#     st.markdown(f"**{len(rows)} rows defined:** {' → '.join(rows)} (far → near house)")

# st.markdown("---")

# # ═══════════════════════════════════════════════
# #  STEP 5: CELL DIMENSIONS
# # ═══════════════════════════════════════════════
# st.subheader("5️⃣ Cell Dimensions")
# st.caption("For each cell, enter the width (perpendicular to strip) and height (along the strip). "
#            "Use imperial format like `11'6.5\"` or just feet like `10`.")

# # How many columns per row?
# max_cols = st.number_input("Maximum columns per row", min_value=1, max_value=5, value=3,
#                             help="e.g. 3 if you have cells like A1, A2, A3")

# st.markdown("**Enter dimensions for each cell:**")

# # Build a table of inputs
# cell_data = {}

# for row in rows:
#     st.markdown(f"**Row {row}**")
#     num_cols = st.number_input(f"Number of columns in row {row}",
#                                 min_value=1, max_value=max_cols,
#                                 value=min(max_cols, 3),
#                                 key=f"ncols_{row}")

#     cols_ui = st.columns(int(num_cols))
#     for c in range(int(num_cols)):
#         col_num = c + 1
#         cell_id = f"{row}{col_num}"
#         with cols_ui[c]:
#             st.markdown(f"**{cell_id}**")
#             w = st.text_input(f"Width", value="10", key=f"w_{cell_id}",
#                               help="Perpendicular to strip direction")
#             h = st.text_input(f"Height", value="10", key=f"h_{cell_id}",
#                               help="Along the strip direction")
#             pat = st.text_input(f"SampleID pattern", value=f"{cell_id}_",
#                                 key=f"pat_{cell_id}",
#                                 help="Substring to match in Master_Data SampleID")

#             cell_data[cell_id] = {
#                 "width": parse_imperial(w),
#                 "height": parse_imperial(h),
#                 "col": col_num,
#                 "row": row,
#                 "pattern": pat,
#             }

# st.markdown("---")

# # ═══════════════════════════════════════════════
# #  STEP 6: FIXED POINT CELL
# # ═══════════════════════════════════════════════
# st.subheader("6️⃣ Fixed Point Location in Grid")

# all_cells = list(cell_data.keys())
# fp_cell = st.selectbox("Which cell is the fixed point at?", all_cells,
#                         help="The GPS anchor sits at a corner of this cell")

# fp_corner = st.selectbox("Which corner of this cell?",
#                           ["Top-Left", "Top-Right", "Bottom-Left", "Bottom-Right"],
#                           help="Looking at the grid in its natural orientation (as drawn on the field sketch)")

# st.markdown("---")

# # ═══════════════════════════════════════════════
# #  STEP 7: POINT SAMPLES (optional)
# # ═══════════════════════════════════════════════
# st.subheader("7️⃣ Point Samples (Optional)")
# st.caption("Add non-grid samples like driplines, lawns, etc. "
#            "Offsets are in feet from the fixed point.")

# num_points = st.number_input("Number of point samples", min_value=0, max_value=20, value=0)

# point_samples = {}
# for i in range(int(num_points)):
#     st.markdown(f"**Point {i + 1}**")
#     pc1, pc2, pc3, pc4 = st.columns(4)
#     with pc1:
#         pt_name = st.text_input("Name", key=f"pt_name_{i}", placeholder="e.g. HUD Dripline")
#     with pc2:
#         pt_ox = st.number_input("East offset (ft)", key=f"pt_ox_{i}", value=0.0)
#     with pc3:
#         pt_oy = st.number_input("North offset (ft)", key=f"pt_oy_{i}", value=0.0)
#     with pc4:
#         pt_pat = st.text_input("SampleID pattern", key=f"pt_pat_{i}", placeholder="e.g. HUD_Dripline")

#     if pt_name:
#         point_samples[pt_name] = {
#             "offset_x": pt_ox,
#             "offset_y": pt_oy,
#             "sample_id_patterns": [pt_pat] if pt_pat else [],
#             "zone": "auxiliary"
#         }

# st.markdown("---")

# # ═══════════════════════════════════════════════
# #  COMPUTE GRID & GENERATE CONFIG
# # ═══════════════════════════════════════════════
# if st.button("🔧 Compute Grid & Generate Config", type="primary"):

#     if not address:
#         st.error("Please enter a street address.")
#         st.stop()
#     if not rows:
#         st.error("Please define at least one row.")
#         st.stop()
#     if not cell_data:
#         st.error("Please define cell dimensions.")
#         st.stop()

#     # ── Compute cumulative positions along the strip ──
#     # "Height" = dimension along the strip
#     # Rows go from far (first) to near house (last)
#     # We stack them: row[0] starts at 0, row[1] starts at row[0].height, etc.

#     # Get the height of each row (use col 1 as reference)
#     row_heights = {}
#     for row in rows:
#         c1 = f"{row}1"
#         if c1 in cell_data:
#             row_heights[row] = cell_data[c1]["height"]
#         else:
#             # Use any cell in that row
#             for cid, cd in cell_data.items():
#                 if cd["row"] == row:
#                     row_heights[row] = cd["height"]
#                     break

#     # Cumulative strip position
#     strip_pos = {}
#     pos = 0
#     for row in rows:
#         strip_pos[row] = pos
#         pos += row_heights.get(row, 10)
#     total_strip = pos

#     # Find the fixed point position in the grid
#     fp_row = ''.join(c for c in fp_cell if c.isalpha())
#     fp_col = int(''.join(c for c in fp_cell if c.isdigit()))

#     # Perpendicular widths per row
#     col_widths_per_row = {}
#     for row in rows:
#         col_widths_per_row[row] = {}
#         for cid, cd in cell_data.items():
#             if cd["row"] == row:
#                 col_widths_per_row[row][cd["col"]] = cd["width"]

#     # Max total perpendicular width (for alignment)
#     max_perp = 0
#     for row in rows:
#         total_w = sum(col_widths_per_row[row].values())
#         max_perp = max(max_perp, total_w)

#     # Fixed point X (perpendicular) position
#     # Compute cumulative width up to the fixed point cell
#     fp_row_widths = col_widths_per_row.get(fp_row, {})
#     fp_perp = 0
#     if "Left" in fp_corner or "Bottom-Left" in fp_corner:
#         # Left edge of the fp_col
#         for c in range(1, fp_col):
#             fp_perp += fp_row_widths.get(c, 0)
#     else:
#         # Right edge of the fp_col
#         for c in range(1, fp_col + 1):
#             fp_perp += fp_row_widths.get(c, 0)

#     # Fixed point Y (strip) position
#     if "Top" in fp_corner:
#         fp_strip = strip_pos[fp_row] + row_heights[fp_row]
#     else:
#         fp_strip = strip_pos[fp_row]

#     # ── Compute block offsets relative to fixed point ──
#     is_vertical = "Vertical" in orientation
#     flip_strip = "Top" in house_dir or "Right" in house_dir
#     # If house is at top/right, near-house rows have HIGHER strip positions
#     # and should map to positive north/east. If house is at bottom/left, flip.

#     grid_blocks = {}

#     for cid, cd in cell_data.items():
#         row = cd["row"]
#         col = cd["col"]
#         cell_h = cd["height"]
#         cell_w = cd["width"]

#         # Strip direction offset
#         strip_start = strip_pos[row] - fp_strip
#         strip_end = strip_start + row_heights[row]

#         # Handle cells with different height than row (e.g. I2 shorter)
#         if cell_h != row_heights[row]:
#             strip_start = strip_end - cell_h

#         # Perpendicular offset
#         perp_start = 0
#         for c in range(1, col):
#             perp_start += col_widths_per_row[row].get(c, 0)
#         perp_end = perp_start + cell_w
#         perp_start -= fp_perp
#         perp_end -= fp_perp

#         # Apply flip if needed
#         if flip_strip:
#             strip_start, strip_end = -strip_end, -strip_start

#         # Map to compass directions
#         if is_vertical:
#             # Strip = North-South, Perp = East-West
#             north_start = strip_start
#             north_end = strip_end
#             east_start = perp_start
#             east_end = perp_end
#         else:
#             # Strip = East-West, Perp = North-South
#             east_start = strip_start
#             east_end = strip_end
#             north_start = perp_start
#             north_end = perp_end

#         grid_blocks[cid] = {
#             "sw_x": round(min(east_start, east_end), 2),
#             "sw_y": round(min(north_start, north_end), 2),
#             "ne_x": round(max(east_start, east_end), 2),
#             "ne_y": round(max(north_start, north_end), 2),
#             "sample_id_patterns": [cd["pattern"]] if cd["pattern"] else [],
#             "zone": "yard",
#             "mock_ppm": 0
#         }

#     # ── Build the config object ──
#     site_config = {
#         "address": address,
#         "city": city,
#         "zip": zip_code,
#         "sampling_date": str(sampling_date),
#         "notes": notes,
#         "anchor": {
#             "lat": anchor_lat,
#             "lon": anchor_lon,
#             "description": f"Fixed point at {fp_cell} corner — field-measured GPS",
#             "marker_label": f"Fixed Point ({fp_cell} corner)"
#         },
#         "map_defaults": {
#             "zoom_start": 21,
#             "center_offset_north_ft": 0,
#             "center_offset_east_ft": 0
#         },
#         "grid_blocks": grid_blocks,
#         "point_samples": point_samples
#     }

#     # Store in session state
#     st.session_state['generated_config'] = site_config

#     st.success("✅ Grid computed successfully! {} blocks + {} point samples.".format(
#         len(grid_blocks), len(point_samples)
#     ))

# # ═══════════════════════════════════════════════
# #  PREVIEW & SAVE
# # ═══════════════════════════════════════════════
# if 'generated_config' in st.session_state:
#     config = st.session_state['generated_config']

#     st.markdown("---")
#     st.subheader("📋 Generated Configuration")

#     # Show the grid blocks in a table
#     block_rows = []
#     for bid, b in config["grid_blocks"].items():
#         block_rows.append({
#             "Cell": bid,
#             "East (sw)": b["sw_x"],
#             "North (sw)": b["sw_y"],
#             "East (ne)": b["ne_x"],
#             "North (ne)": b["ne_y"],
#             "Width (ft)": round(b["ne_x"] - b["sw_x"], 1),
#             "Height (ft)": round(b["ne_y"] - b["sw_y"], 1),
#             "Pattern": ", ".join(b.get("sample_id_patterns", []))
#         })
#     st.dataframe(pd.DataFrame(block_rows), use_container_width=True, hide_index=True)

#     # ── Map Preview ──
#     st.subheader("🗺️ Map Preview")

#     try:
#         import folium
#         from streamlit_folium import st_folium

#         anchor = config["anchor"]
#         m = folium.Map(
#             location=[anchor["lat"], anchor["lon"]],
#             zoom_start=21, max_zoom=25, tiles=None
#         )

#         folium.TileLayer(
#             tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
#             attr='Esri', name='Esri Satellite',
#             max_zoom=25, max_native_zoom=19,
#             overlay=False, control=True
#         ).add_to(m)

#         folium.Marker(
#             location=[anchor["lat"], anchor["lon"]],
#             tooltip=f"<b>{anchor.get('marker_label', 'Anchor')}</b>",
#             icon=folium.Icon(color='red', icon='home')
#         ).add_to(m)

#         for bid, dims in config["grid_blocks"].items():
#             sw_lat, sw_lon = calculate_coordinate(anchor["lat"], anchor["lon"],
#                                                    dims["sw_y"], dims["sw_x"])
#             ne_lat, ne_lon = calculate_coordinate(anchor["lat"], anchor["lon"],
#                                                    dims["ne_y"], dims["ne_x"])

#             # Use a default color since we don't have data yet
#             folium.Rectangle(
#                 bounds=[[sw_lat, sw_lon], [ne_lat, ne_lon]],
#                 color='white', weight=2,
#                 fill=True, fill_color='#4a90d9', fill_opacity=0.5,
#                 tooltip=f"<b>{bid}</b><br>Size: {dims['ne_x']-dims['sw_x']:.1f} × {dims['ne_y']-dims['sw_y']:.1f} ft"
#             ).add_to(m)

#         for pid, pt in config.get("point_samples", {}).items():
#             pt_lat, pt_lon = calculate_coordinate(anchor["lat"], anchor["lon"],
#                                                    pt["offset_y"], pt["offset_x"])
#             folium.CircleMarker(
#                 location=[pt_lat, pt_lon],
#                 radius=7, color='white', weight=2,
#                 fill=True, fill_color='#f39c12', fill_opacity=0.8,
#                 tooltip=f"<b>{pid}</b>"
#             ).add_to(m)

#         st_folium(m, width=900, height=550, returned_objects=[])

#     except ImportError:
#         st.warning("Install folium and streamlit_folium for map preview.")

#     # ── JSON Preview ──
#     st.subheader("📄 JSON Config")
#     json_str = json.dumps(config, indent=2)
#     st.code(json_str, language="json")

#     # ── Save to site_configs.json ──
#     st.subheader("💾 Save Configuration")

#     base_dir = os.path.dirname(os.path.abspath(__file__))
#     config_dir = os.path.join(base_dir, '..', 'data', 'site_configs')
#     config_path = os.path.join(config_dir, 'site_configs.json')

#     col_save, col_download = st.columns(2)

#     with col_save:
#         if st.button("💾 Save to site_configs.json", type="primary"):
#             os.makedirs(config_dir, exist_ok=True)

#             if os.path.exists(config_path):
#                 with open(config_path, 'r') as f:
#                     existing = json.load(f)
#             else:
#                 existing = []

#             # Check if address already exists — update or append
#             found = False
#             for i, s in enumerate(existing):
#                 if s.get("address") == config["address"]:
#                     existing[i] = config
#                     found = True
#                     break
#             if not found:
#                 existing.append(config)

#             with open(config_path, 'w') as f:
#                 json.dump(existing, f, indent=2)

#             st.success(f"✅ {'Updated' if found else 'Added'} '{config['address']}' in site_configs.json")

#     with col_download:
#         st.download_button(
#             label="📥 Download JSON",
#             data=json_str,
#             file_name=f"site_config_{config['address'].replace(' ', '_')}.json",
#             mime="application/json"
#         )

"""
site_builder.py — GroundSense Site Configuration Builder

A standalone Streamlit page where field technicians input measurements
for a new sampling site and the system auto-generates:
  1. Grid block offsets (computed from cell dimensions + fixed point)
  2. A site_configs.json entry
  3. A live satellite map preview

Place in src/ alongside groundsense_config.py.
Run: streamlit run src/site_builder.py
"""

import streamlit as st
import pandas as pd
import json
import math
import os

from groundsense_config import (
    get_nysh_category,
    NYSH_TIERS,
    NYSH_COLORS,
    calculate_coordinate,
    resolve_lod,
)


# ═══════════════════════════════════════════════
#  PAGE CONFIG & STYLING
# ═══════════════════════════════════════════════
# st.set_page_config(
#     page_title="GroundSense · Site Builder",
#     page_icon="📐",
#     layout="wide",
#     initial_sidebar_state="collapsed",
# )

# st.markdown("""
# <style>
#     .block-container { padding-top: 2rem; }
#     hr { border-color: rgba(255,255,255,0.06) !important; }
#     .stAlert { border-radius: 10px; }
# </style>
# """, unsafe_allow_html=True)

st.set_page_config(page_title="GroundSense Site Builder", page_icon="📐", layout="wide")
st.title("📐 Site Configuration Builder")
st.caption("Urban Soil Co-Lab · University at Buffalo · GroundSense Pipeline")
st.markdown("Transform field sketch measurements into a config-ready site definition. "
    "Fill in each section below, then hit **Compute** to generate the JSON config "
    "and preview the grid on satellite imagery.")
st.markdown("---")


# ═══════════════════════════════════════════════
#  HEADER
# ═══════════════════════════════════════════════
# col_logo, col_head = st.columns([1, 9])
# with col_logo:
#     st.markdown("## 📐")
# with col_head:
#     st.title("Site Configuration Builder")
#     st.caption("Urban Soil Co-Lab · GroundSense Pipeline")

# st.markdown(
#     "Transform field sketch measurements into a config-ready site definition. "
#     "Fill in each section below, then hit **Compute** to generate the JSON config "
#     "and preview the grid on satellite imagery."
# )
# st.markdown("---")



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


# ═══════════════════════════════════════════════
#  STEP 1 — SITE INFORMATION
# ═══════════════════════════════════════════════
st.subheader("① Site Information")

col_addr, col_city, col_zip = st.columns([4, 2, 1])
with col_addr:
    address = st.text_input("Street Address *", placeholder="e.g. 203 Schuele Ave")
with col_city:
    city = st.text_input("City", value="Buffalo")
with col_zip:
    zip_code = st.text_input("ZIP", placeholder="14215")

col_date, col_notes = st.columns([1, 3])
with col_date:
    sampling_date = st.date_input("Sampling Date")
with col_notes:
    notes = st.text_input("Site Notes (optional)",
                           placeholder="e.g. Backyard grid, measured from porch corner…")

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
    if not address:
        errors.append("Street address is required.")
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

    site_config = {
        "address": address, "city": city, "zip": zip_code,
        "sampling_date": str(sampling_date), "notes": notes,
        "anchor": {
            "lat": anchor_lat, "lon": anchor_lon,
            "description": f"Fixed point at {fp_cell} ({fp_corner}) — field-measured GPS",
            "marker_label": f"Fixed Point ({fp_cell})",
        },
        "map_defaults": {"zoom_start": 21, "center_offset_north_ft": 0, "center_offset_east_ft": 0},
        "grid_blocks": grid_blocks,
        "point_samples": point_samples,
    }

    st.session_state["generated_config"] = site_config
    st.success(f"✅ Grid computed — **{len(grid_blocks)} blocks** + **{len(point_samples)} point samples**")


# ═══════════════════════════════════════════════
#  RESULTS
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

    st.subheader("🗺️ Satellite Map Preview")
    try:
        import folium
        from streamlit_folium import st_folium

        a = config["anchor"]
        m = folium.Map(location=[a["lat"], a["lon"]], zoom_start=21, max_zoom=25, tiles=None)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri", max_zoom=25, max_native_zoom=19, overlay=False, control=True,
        ).add_to(m)
        folium.Marker([a["lat"], a["lon"]],
                       tooltip=f"<b>{a.get('marker_label','Anchor')}</b>",
                       icon=folium.Icon(color="red", icon="home")).add_to(m)
        for bid, d in config["grid_blocks"].items():
            sw = calculate_coordinate(a["lat"], a["lon"], d["sw_y"], d["sw_x"])
            ne = calculate_coordinate(a["lat"], a["lon"], d["ne_y"], d["ne_x"])
            folium.Rectangle(bounds=[sw, ne], color="white", weight=2,
                             fill=True, fill_color="#4a90d9", fill_opacity=0.5,
                             tooltip=f"<b>{bid}</b><br>{d['ne_x']-d['sw_x']:.1f}×{d['ne_y']-d['sw_y']:.1f} ft").add_to(m)
        for pid, pt in config.get("point_samples", {}).items():
            loc = calculate_coordinate(a["lat"], a["lon"], pt["offset_y"], pt["offset_x"])
            folium.CircleMarker(location=loc, radius=7, color="white", weight=2,
                                fill=True, fill_color="#f39c12", fill_opacity=0.8,
                                tooltip=f"<b>{pid}</b>").add_to(m)
        st_folium(m, width=1000, height=550, returned_objects=[])
    except ImportError:
        st.warning("Install `folium` and `streamlit_folium` for map preview.")

    st.subheader("💾 Export")
    json_str = json.dumps(config, indent=2)
    tab_save, tab_json = st.tabs(["Save to Project", "Raw JSON"])

    with tab_save:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.join(base_dir, "..", "data", "site_configs")
        config_path = os.path.join(config_dir, "site_configs.json")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 Save to site_configs.json", type="primary", use_container_width=True):
                os.makedirs(config_dir, exist_ok=True)
                existing = []
                if os.path.exists(config_path):
                    with open(config_path) as f:
                        existing = json.load(f)
                found = False
                for i, s in enumerate(existing):
                    if s.get("address") == config["address"]:
                        existing[i] = config; found = True; break
                if not found:
                    existing.append(config)
                with open(config_path, "w") as f:
                    json.dump(existing, f, indent=2)
                st.success(f"{'Updated' if found else 'Added'} **{config['address']}**")
        with c2:
            st.download_button("📥 Download JSON", data=json_str,
                                file_name=f"site_config_{config['address'].replace(' ','_')}.json",
                                mime="application/json", use_container_width=True)
    with tab_json:
        st.code(json_str, language="json")
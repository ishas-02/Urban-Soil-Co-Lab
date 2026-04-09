# # # # """
# # # # etl_manager.py — GroundSense Data Pipeline Manager

# # # # Updates from original:
# # # #   1. Imports NYSH colors from groundsense_config.py
# # # #   2. Generates static map images (matplotlib) for each site using site_configs.json
# # # #   3. Inserts map images into Slide 5 of the Resident Report PPTX template
# # # #   4. Builds NYSH-colored results table on Slide 4
# # # # """


# # # import streamlit as st
# # # import os
# # # import sys
# # # import glob
# # # import re
# # # import subprocess
# # # import shutil
# # # import json
# # # import math
# # # import pandas as pd
# # # import numpy as np
# # # import matplotlib
# # # matplotlib.use('Agg')
# # # import matplotlib.pyplot as plt
# # # import matplotlib.patches as mpatches
# # # from matplotlib.patches import FancyBboxPatch
# # # from pptx import Presentation
# # # from pptx.util import Inches

# # # # Inject src to path so groundsense_config can be imported
# # # sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

# # # from groundsense_config import (
# # #     get_nysh_category,
# # #     NYSH_TIERS,
# # #     NYSH_COLORS,
# # #     calculate_coordinate,
# # #     resolve_lod,
# # # )

# # # # ═══════════════════════════════════════════════
# # # #  PAGE CONFIGURATION
# # # # ═══════════════════════════════════════════════
# # # st.set_page_config(page_title="GroundSense Pipeline", page_icon="⚙️", layout="wide")

# # # # Initialize Session State
# # # if 'pipeline_success' not in st.session_state:
# # #     st.session_state.pipeline_success = False
# # # if 'latest_master_file' not in st.session_state:
# # #     st.session_state.latest_master_file = None
# # # if 'reports_generated' not in st.session_state:
# # #     st.session_state.reports_generated = 0

# # # # ═══════════════════════════════════════════════
# # # #  MAP IMAGE GENERATOR (matplotlib)
# # # # ═══════════════════════════════════════════════
# # # def generate_map_image(site_config, master_df, output_path, style="dark"):
# # #     """Generates a static PNG map image of a site's grid with NYSH coloring."""
# # #     anchor = site_config["anchor"]
# # #     grid = site_config.get("grid_blocks", {})
# # #     points = site_config.get("point_samples", {})

# # #     if 'LeadPPM_Clean' not in master_df.columns:
# # #         master_df['LeadPPM_Clean'] = master_df['LeadPPM'].apply(resolve_lod)

# # #     def match_ppm(patterns):
# # #         for pat in patterns:
# # #             matches = master_df[master_df['SampleID'].str.contains(pat, case=False, na=False)]
# # #             if not matches.empty:
# # #                 avg = matches['LeadPPM_Clean'].mean()
# # #                 if pd.notna(avg):
# # #                     return avg
# # #         return None

# # #     if style == "light":
# # #         bg, text_c, label_c, edge_c = '#ffffff', '#333333', '#555555', '#333333'
# # #         tick_c, spine_c = '#888888', '#cccccc'
# # #         leg_bg, leg_edge, leg_text = '#f0f0f0', '#cccccc', '#333333'
# # #         pt_label_c, pt_val_c = '#555555', '#333333'
# # #     else:
# # #         bg, text_c, label_c, edge_c = '#1a1c24', 'white', '#888888', 'white'
# # #         tick_c, spine_c = '#666666', '#333333'
# # #         leg_bg, leg_edge, leg_text = '#2a2d38', '#444444', 'white'
# # #         pt_label_c, pt_val_c = '#cccccc', 'white'

# # #     fig, ax = plt.subplots(1, 1, figsize=(8, 7), facecolor=bg)
# # #     ax.set_facecolor(bg)

# # #     all_x, all_y = [], []

# # #     for block_id, dims in grid.items():
# # #         if block_id.startswith("_"): continue
# # #         sx, sy = dims["sw_x"], dims["sw_y"]
# # #         w = dims["ne_x"] - dims["sw_x"]
# # #         h = dims["ne_y"] - dims["sw_y"]

# # #         patterns = dims.get("sample_id_patterns", [])
# # #         ppm = match_ppm(patterns)
# # #         if ppm is None: ppm = dims.get("mock_ppm", 0)

# # #         label, color = get_nysh_category(ppm)

# # #         rect = FancyBboxPatch((sx, sy), w, h, boxstyle="round,pad=0.3",
# # #                               facecolor=color, edgecolor=edge_c, linewidth=1.5, alpha=0.8)
# # #         ax.add_patch(rect)

# # #         cx, cy = sx + w / 2, sy + h / 2
# # #         ax.text(cx, cy, block_id, ha='center', va='center', fontsize=8, fontweight='bold', color='white',
# # #                 bbox=dict(boxstyle='round,pad=0.15', facecolor='black', alpha=0.4))
# # #         ax.text(cx, cy - h * 0.25, "{:.0f}".format(ppm), ha='center', va='center', fontsize=7, color='white', alpha=0.9)

# # #         all_x.extend([sx, sx + w])
# # #         all_y.extend([sy, sy + h])

# # #     for pt_id, pt in points.items():
# # #         if pt_id.startswith("_"): continue
# # #         ox, oy = pt.get("offset_x", 0), pt.get("offset_y", 0)
# # #         patterns = pt.get("sample_id_patterns", [])
# # #         ppm = match_ppm(patterns)

# # #         if ppm is not None:
# # #             label, color = get_nysh_category(ppm)
# # #             ppm_str = "{:.0f}".format(ppm)
# # #         else:
# # #             color, ppm_str = "#808080", "?"

# # #         ax.plot(ox, oy, 'o', markersize=10, color=color, markeredgecolor=edge_c, markeredgewidth=1.5)
# # #         ax.text(ox, oy + 2.5, pt_id, ha='center', va='bottom', fontsize=6, color=pt_label_c, fontstyle='italic')
# # #         ax.text(ox, oy - 2.5, ppm_str, ha='center', va='top', fontsize=6, color='white', fontweight='bold')
# # #         all_x.append(ox); all_y.append(oy)

# # #     ax.plot(0, 0, marker='^', markersize=12, color='red', markeredgecolor=edge_c, markeredgewidth=1.5, zorder=10)
# # #     ax.text(0, -3, "Anchor", ha='center', va='top', fontsize=7, color='red', fontweight='bold')

# # #     if all_x and all_y:
# # #         pad = 10
# # #         ax.set_xlim(min(all_x) - pad, max(all_x) + pad)
# # #         ax.set_ylim(min(all_y) - pad, max(all_y) + pad)

# # #     ax.set_aspect('equal')
# # #     ax.set_xlabel('East (ft)', color='#888888', fontsize=9)
# # #     ax.set_ylabel('North (ft)', color='#888888', fontsize=9)
# # #     ax.tick_params(colors='#666666', labelsize=7)
# # #     for spine in ax.spines.values(): spine.set_color('#333333')

# # #     site_name = site_config.get("address", "Site")
# # #     ax.set_title(site_name + " — Lead Contamination Map", color=text_c, fontsize=12, fontweight='bold', pad=12)

# # #     legend_patches = [mpatches.Patch(color=t["color"], label=t["label"]) for t in NYSH_TIERS]
# # #     legend_patches.append(mpatches.Patch(color="#808080", label="No Data"))
# # #     ax.legend(handles=legend_patches, loc='lower right', fontsize=6, framealpha=0.8,
# # #               facecolor='#2a2d38', edgecolor='#444444', labelcolor='white')

# # #     plt.tight_layout()
# # #     plt.savefig(output_path, dpi=200, bbox_inches='tight', facecolor=bg, edgecolor='none')
# # #     plt.close()
# # #     return output_path

# # # # ═══════════════════════════════════════════════
# # # #  REPORT GENERATION (PPTX)
# # # # ═══════════════════════════════════════════════
# # # def generate_pptx_reports(master_csv_path, template_path, output_dir, site_db_path, site_configs_path):
# # #     """Generates PPTX reports. Returns the number of reports generated."""
# # #     df = pd.read_csv(master_csv_path)
# # #     df = df[df['SampleID'].notna() & (df['SampleID'] != "")]
# # #     df['LeadPPM_Clean'] = df['LeadPPM'].apply(resolve_lod)

# # #     if os.path.exists(site_db_path):
# # #         site_db = pd.read_csv(site_db_path, header=1, encoding='latin1')
# # #         site_db['Address'] = site_db['Address'].ffill()
# # #         site_mapping = dict(zip(site_db['SampleID'].dropna(), site_db['Address'].dropna()))
# # #         df['SiteID'] = df['SampleID'].map(site_mapping).fillna(df['SampleID'])
# # #     else:
# # #         df['SiteID'] = df['SampleID']

# # #     site_configs = {}
# # #     if os.path.exists(site_configs_path):
# # #         with open(site_configs_path, 'r') as f:
# # #             raw = json.load(f)
# # #         site_configs = {s["address"]: s for s in raw}

# # #     site_averages = df.groupby('SiteID')['LeadPPM_Clean'].mean().reset_index()

# # #     os.makedirs(output_dir, exist_ok=True)
# # #     maps_dir = os.path.join(output_dir, "map_images")
# # #     os.makedirs(maps_dir, exist_ok=True)

# # #     report_count = 0

# # #     for _, row in site_averages.iterrows():
# # #         site_id = str(row['SiteID'])
# # #         site_avg = row['LeadPPM_Clean']
# # #         if pd.isna(site_avg): continue

# # #         map_image_path = None
# # #         if site_id in site_configs:
# # #             safe_name = "".join(c for c in site_id if c.isalnum() or c == ' ').rstrip()
# # #             map_image_path = os.path.join(maps_dir, f"map_{safe_name}.png")
# # #             try:
# # #                 generate_map_image(site_configs[site_id], df, map_image_path)
# # #             except Exception as e:
# # #                 st.warning(f"Could not generate map for {site_id}: {e}")
# # #                 map_image_path = None

# # #         try:
# # #             prs = Presentation(template_path)
# # #         except Exception as e:
# # #             raise Exception(f"Failed to load PPTX template: {e}")

# # #         for slide_idx, slide in enumerate(prs.slides):
# # #             for shape in slide.shapes:
# # #                 if not shape.has_text_frame: continue
# # #                 for paragraph in shape.text_frame.paragraphs:
# # #                     for run in paragraph.runs:
# # #                         if "Name of Resident" in run.text:
# # #                             run.text = run.text.replace("Name of Resident", f"Resident at {site_id}")
# # #                         if "Address of Resident" in run.text:
# # #                             run.text = run.text.replace("Address of Resident", site_id)
# # #                         if "Average Lead concentration (ppm)" in run.text:
# # #                             nysh_label, _ = get_nysh_category(site_avg)
# # #                             run.text = run.text.replace("Average Lead concentration (ppm)", f"Average Lead: {site_avg:.1f} ppm — {nysh_label}")
# # #                         if "Visual map of property with color-coded zones" in run.text or "Highlight hotspots" in run.text:
# # #                             run.text = "" 

# # #             if slide_idx == 0 and map_image_path:
# # #                 light_map_path = map_image_path.replace('.png', '_light.png')
# # #                 try:
# # #                     generate_map_image(site_configs[site_id], df, light_map_path, style="light")
# # #                     from PIL import Image as PILImage
# # #                     img = PILImage.open(light_map_path)
# # #                     img_aspect = img.width / img.height
# # #                     max_w, max_h = 7.5, 3.8
# # #                     w = max_h * img_aspect if max_w / img_aspect > max_h else max_w
# # #                     h = w / img_aspect
# # #                     slide.shapes.add_picture(light_map_path, Inches((8.5 - w) / 2), Inches(6.15), width=Inches(w), height=Inches(h))
# # #                 except Exception: pass

# # #             if slide_idx == 4 and map_image_path and os.path.exists(map_image_path):
# # #                 slide.shapes.add_picture(map_image_path, Inches(0.6), Inches(1.7), width=Inches(7.2))

# # #         safe_filename = "".join(c for c in site_id if c.isalnum() or c == ' ').rstrip()
# # #         output_file = os.path.join(output_dir, f"Resident_Report_{safe_filename}.pptx")
# # #         prs.save(output_file)
# # #         report_count += 1

# # #     return report_count

# # # # ═══════════════════════════════════════════════
# # # #  UI: HEADER & INSTRUCTIONS
# # # # ═══════════════════════════════════════════════
# # # col_header, col_info = st.columns([2, 1])
# # # with col_header:
# # #     st.title("⚙️ Data Pipeline Manager")
# # #     st.markdown("Automated ETL, spatial mapping, and resident report generation.")
# # # with col_info:
# # #     st.info("💡 **Instructions:** Drag and drop your raw XRF `.csv` files below. The backend will parse the readings, append them to the Master Database, and automatically generate updated site reports.")

# # # st.markdown("---")

# # # # ═══════════════════════════════════════════════
# # # #  UI: UPLOAD & PROCESS 
# # # # ═══════════════════════════════════════════════
# # # st.subheader("1. Ingest Data")
# # # uploaded_files = st.file_uploader("Upload Raw XRF Chemistry Files", type=['csv'], accept_multiple_files=True)

# # # if st.button("🚀 Execute Data Pipeline", type="primary", use_container_width=True):
# # #     if not uploaded_files:
# # #         st.warning("⚠️ Please upload at least one chemistry CSV file to begin.")
# # #     else:
# # #         # Keep it clean: no expanded details, just the top-level loading message
# # #         with st.status("Executing the Data Pipeline...", expanded=False) as status:
# # #             try:
# # #                 # 1. Save uploaded files
# # #                 xrf_dir = os.path.join("data", "xrf_data")
# # #                 os.makedirs(xrf_dir, exist_ok=True)
# # #                 for f in uploaded_files:
# # #                     with open(os.path.join(xrf_dir, f.name), "wb") as f_out:
# # #                         f_out.write(f.read())

# # #                 # 2. Run ETL script
# # #                 result = subprocess.run(["python", "src/data.py"], capture_output=True, text=True)
                
# # #                 if result.returncode != 0:
# # #                     status.update(label="Pipeline Failed during ETL process.", state="error")
# # #                     st.error(f"Backend Error Output:\n{result.stderr}")
# # #                     st.stop()

# # #                 # 3. Locate Master Data
# # #                 master_dir = os.path.join("data", "master_data")
# # #                 master_files = glob.glob(os.path.join(master_dir, 'Master_Data_v*.csv'))
                
# # #                 if not master_files:
# # #                     status.update(label="Failed to locate output Master Data.", state="error")
# # #                     st.stop()

# # #                 latest_master = max(master_files, key=lambda x: int(re.search(r'_v(\d+)\.csv', x).group(1) if re.search(r'_v(\d+)\.csv', x) else 0))
# # #                 st.session_state.latest_master_file = latest_master

# # #                 # 4. Generate Reports
# # #                 template_path = os.path.join("src", "Resident_Report_Template.pptx")
# # #                 site_db_path = os.path.join("data", "site_databases", "XRF Site Analysis Database W SampleID(Sheet1).csv")
# # #                 site_configs_path = os.path.join("data", "site_configs", "site_configs.json")
# # #                 reports_dir = os.path.join("data", "generated_reports")
# # #                 zip_path_base = os.path.join("data", "All_Resident_Reports")

# # #                 if os.path.exists(template_path):
# # #                     report_count = generate_pptx_reports(
# # #                         st.session_state.latest_master_file,
# # #                         template_path, reports_dir,
# # #                         site_db_path, site_configs_path
# # #                     )
# # #                     st.session_state.reports_generated = report_count
                    
# # #                     # Archive into ZIP
# # #                     shutil.make_archive(zip_path_base, 'zip', reports_dir)
# # #                 else:
# # #                     st.warning("⚠️ Template missing. Skipped report generation.")

# # #                 # Final Success Message
# # #                 status.update(label="Pipeline Execution Complete!", state="complete")
# # #                 st.session_state.pipeline_success = True

# # #             except Exception as e:
# # #                 status.update(label="Critical System Error", state="error")
# # #                 st.error(f"An unexpected error occurred: {str(e)}")
# # #                 st.session_state.pipeline_success = False

# # # # ═══════════════════════════════════════════════
# # # #  UI: RESULTS & EXPORT
# # # # ═══════════════════════════════════════════════
# # # if st.session_state.pipeline_success and st.session_state.latest_master_file:
# # #     st.markdown("---")
# # #     st.subheader("2. Deployment Artifacts")
    
# # #     # KPIs
# # #     df_result = pd.read_csv(st.session_state.latest_master_file)
# # #     kpi1, kpi2, kpi3 = st.columns(3)
# # #     kpi1.metric("Total Records Processed", len(df_result))
# # #     kpi2.metric("Sites Evaluated", df_result['SampleID'].nunique() if 'SampleID' in df_result else "N/A")
# # #     kpi3.metric("Resident Reports Generated", st.session_state.reports_generated)
    
# # #     st.write("")
    
# # #     # Download Buttons
# # #     col_dl1, col_dl2 = st.columns(2)
# # #     with col_dl1:
# # #         st.success("### 📊 Master Database")
# # #         st.caption(f"File: `{os.path.basename(st.session_state.latest_master_file)}`")
# # #         with open(st.session_state.latest_master_file, "rb") as file:
# # #             st.download_button(
# # #                 label="📥 Download Master Data (CSV)",
# # #                 data=file,
# # #                 file_name=os.path.basename(st.session_state.latest_master_file),
# # #                 mime="text/csv",
# # #                 use_container_width=True
# # #             )

# # #     with col_dl2:
# # #         zip_path_base = os.path.join("data", "All_Resident_Reports")
# # #         zip_file_full = zip_path_base + ".zip"
# # #         if os.path.exists(zip_file_full):
# # #             st.info("### 🗂️ Resident Reports")
# # #             st.caption(f"Includes {st.session_state.reports_generated} formatted PPTX presentations.")
# # #             with open(zip_file_full, "rb") as zip_file:
# # #                 st.download_button(
# # #                     label="📥 Download All Reports (ZIP)",
# # #                     data=zip_file,
# # #                     file_name="GroundSense_Resident_Reports.zip",
# # #                     mime="application/zip",
# # #                     use_container_width=True
# # #                 )

# """
# etl_manager.py — GroundSense Data Pipeline Manager

# Updates from original:
#   1. Imports NYSH colors from groundsense_config.py
#   2. Generates static map images (matplotlib, dark style only) for each site
#   3. Inserts map images into correct slides of the Resident Report PPTX template
#   4. Fills in zone-based average Lead PPM values (backyard / front yard)

# Template slide layout (6 pages, 0-indexed):
#   Slide 0: Cover letter — replace "Address of Resident", "Name of Resident", "Date"
#   Slide 1: Sample Collection Method — keep as-is
#   Slide 2: Soil Report Summary — insert dark map (no basemap)
#   Slide 3: Detailed Results — fill [###] with real PPM, insert map
#   Slide 4: NY Soil Health info — keep as-is
#   Slide 5: Lead level table & safety — keep as-is
# """


# import streamlit as st
# import os
# import sys
# import glob
# import re
# import subprocess
# import json
# import math
# import pandas as pd
# import numpy as np
# import matplotlib
# matplotlib.use('Agg')
# import matplotlib.pyplot as plt
# import matplotlib.patches as mpatches
# from matplotlib.patches import FancyBboxPatch
# from pptx import Presentation
# from pptx.util import Inches
# from datetime import date

# # Inject src to path so groundsense_config can be imported
# sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

# from groundsense_config import (
#     get_nysh_category,
#     NYSH_TIERS,
#     NYSH_COLORS,
#     calculate_coordinate,
#     resolve_lod,
# )

# # ═══════════════════════════════════════════════
# #  PAGE CONFIGURATION
# # ═══════════════════════════════════════════════
# st.set_page_config(page_title="GroundSense Pipeline", page_icon="⚙️", layout="wide")

# # Initialize Session State
# if 'pipeline_success' not in st.session_state:
#     st.session_state.pipeline_success = False
# if 'latest_master_file' not in st.session_state:
#     st.session_state.latest_master_file = None
# if 'reports_generated' not in st.session_state:
#     st.session_state.reports_generated = 0
# if 'generated_report_list' not in st.session_state:
#     st.session_state.generated_report_list = []

# # ═══════════════════════════════════════════════
# #  MAP IMAGE GENERATOR (matplotlib) — DARK ONLY
# # ═══════════════════════════════════════════════
# def generate_map_image(site_config, master_df, output_path):
#     """Generates a static dark-style PNG map image of a site's grid
#     with NYSH coloring.  No light/white variant is produced."""
#     anchor = site_config["anchor"]
#     grid = site_config.get("grid_blocks", {})
#     points = site_config.get("point_samples", {})

#     # Ensure LeadPPM_Clean column exists (work on a copy to avoid side-effects)
#     if 'LeadPPM_Clean' not in master_df.columns:
#         master_df = master_df.copy()
#         master_df['LeadPPM_Clean'] = master_df['LeadPPM'].apply(resolve_lod)

#     def match_ppm(patterns):
#         for pat in patterns:
#             if not pat:
#                 continue
#             matches = master_df[master_df['SampleID'].str.contains(pat, case=False, na=False)]
#             if not matches.empty:
#                 avg = matches['LeadPPM_Clean'].mean()
#                 if pd.notna(avg):
#                     return avg
#         return None

#     # Dark style constants
#     bg       = '#1a1c24'
#     text_c   = 'white'
#     edge_c   = 'white'

#     fig, ax = plt.subplots(1, 1, figsize=(8, 7), facecolor=bg)
#     ax.set_facecolor(bg)

#     all_x, all_y = [], []

#     for block_id, dims in grid.items():
#         if block_id.startswith("_"):
#             continue
#         sx, sy = dims["sw_x"], dims["sw_y"]
#         w = dims["ne_x"] - dims["sw_x"]
#         h = dims["ne_y"] - dims["sw_y"]

#         patterns = dims.get("sample_id_patterns", [])
#         ppm = match_ppm(patterns)
#         if ppm is None:
#             ppm = dims.get("mock_ppm", 0)

#         _label, color = get_nysh_category(ppm)

#         rect = FancyBboxPatch(
#             (sx, sy), w, h, boxstyle="round,pad=0.3",
#             facecolor=color, edgecolor=edge_c, linewidth=1.5, alpha=0.8,
#         )
#         ax.add_patch(rect)

#         cx, cy = sx + w / 2, sy + h / 2
#         ax.text(cx, cy, block_id, ha='center', va='center',
#                 fontsize=8, fontweight='bold', color='white',
#                 bbox=dict(boxstyle='round,pad=0.15', facecolor='black', alpha=0.4))
#         ax.text(cx, cy - h * 0.25, "{:.0f}".format(ppm),
#                 ha='center', va='center', fontsize=7, color='white', alpha=0.9)

#         all_x.extend([sx, sx + w])
#         all_y.extend([sy, sy + h])

#     # Point samples
#     for pt_id, pt in points.items():
#         if pt_id.startswith("_"):
#             continue
#         ox, oy = pt.get("offset_x", 0), pt.get("offset_y", 0)
#         patterns = pt.get("sample_id_patterns", [])
#         ppm = match_ppm(patterns)

#         if ppm is not None:
#             _label, color = get_nysh_category(ppm)
#             ppm_str = "{:.0f}".format(ppm)
#         else:
#             color, ppm_str = "#808080", "?"

#         ax.plot(ox, oy, 'o', markersize=10, color=color,
#                 markeredgecolor=edge_c, markeredgewidth=1.5)
#         ax.text(ox, oy + 2.5, pt_id, ha='center', va='bottom',
#                 fontsize=6, color='#cccccc', fontstyle='italic')
#         ax.text(ox, oy - 2.5, ppm_str, ha='center', va='top',
#                 fontsize=6, color='white', fontweight='bold')
#         all_x.append(ox)
#         all_y.append(oy)

#     # Anchor marker
#     ax.plot(0, 0, marker='^', markersize=12, color='red',
#             markeredgecolor=edge_c, markeredgewidth=1.5, zorder=10)
#     ax.text(0, -3, "Anchor", ha='center', va='top',
#             fontsize=7, color='red', fontweight='bold')

#     if all_x and all_y:
#         pad = 10
#         ax.set_xlim(min(all_x) - pad, max(all_x) + pad)
#         ax.set_ylim(min(all_y) - pad, max(all_y) + pad)

#     ax.set_aspect('equal')
#     ax.set_xlabel('East (ft)', color='#888888', fontsize=9)
#     ax.set_ylabel('North (ft)', color='#888888', fontsize=9)
#     ax.tick_params(colors='#666666', labelsize=7)
#     for spine in ax.spines.values():
#         spine.set_color('#333333')

#     site_name = site_config.get("address", "Site")
#     ax.set_title(f"{site_name} — Lead Contamination Map",
#                  color=text_c, fontsize=12, fontweight='bold', pad=12)

#     legend_patches = [mpatches.Patch(color=t["color"], label=t["label"])
#                       for t in NYSH_TIERS]
#     legend_patches.append(mpatches.Patch(color="#808080", label="No Data"))
#     ax.legend(handles=legend_patches, loc='lower right', fontsize=6,
#               framealpha=0.8, facecolor='#2a2d38', edgecolor='#444444',
#               labelcolor='white')

#     plt.tight_layout()
#     plt.savefig(output_path, dpi=200, bbox_inches='tight',
#                 facecolor=bg, edgecolor='none')
#     plt.close()
#     return output_path


# # ═══════════════════════════════════════════════
# #  ZONE-BASED PPM CALCULATOR
# # ═══════════════════════════════════════════════
# def compute_zone_averages(site_config, master_df):
#     """Compute average Lead PPM for each zone (back, front, yard, transect).

#     Returns dict, e.g. {"back": 542.3, "front": 718.1}
#     """
#     grid = site_config.get("grid_blocks", {})

#     if 'LeadPPM_Clean' not in master_df.columns:
#         master_df = master_df.copy()
#         master_df['LeadPPM_Clean'] = master_df['LeadPPM'].apply(resolve_lod)

#     zone_values = {}  # zone_name -> [ppm, ...]

#     for block_id, dims in grid.items():
#         if block_id.startswith("_"):
#             continue
#         zone = dims.get("zone", "yard")
#         patterns = dims.get("sample_id_patterns", [])

#         ppm = None
#         for pat in patterns:
#             if not pat:
#                 continue
#             matches = master_df[
#                 master_df['SampleID'].str.contains(pat, case=False, na=False)
#             ]
#             if not matches.empty:
#                 avg = matches['LeadPPM_Clean'].mean()
#                 if pd.notna(avg):
#                     ppm = avg
#                     break

#         if ppm is None:
#             ppm = dims.get("mock_ppm")

#         if ppm is not None and not (isinstance(ppm, float) and math.isnan(ppm)):
#             zone_values.setdefault(zone, []).append(ppm)

#     return {z: sum(v) / len(v) for z, v in zone_values.items() if v}


# def format_zone_ppm(zone_averages):
#     """Map zone averages to backyard_ppm / frontyard_ppm for template filling.

#     Single-zone sites (yard, transect) map to backyard only.
#     """
#     result = {"backyard_ppm": None, "frontyard_ppm": None}
#     for zone, avg in zone_averages.items():
#         z = zone.lower()
#         if z in ("back", "backyard"):
#             result["backyard_ppm"] = round(avg)
#         elif z in ("front", "frontyard", "front_yard"):
#             result["frontyard_ppm"] = round(avg)
#         elif z in ("yard", "transect"):
#             result["backyard_ppm"] = round(avg)
#     return result


# # ═══════════════════════════════════════════════
# #  REPORT GENERATION (PPTX)
# # ═══════════════════════════════════════════════
# def generate_pptx_reports(master_csv_path, template_path, output_dir,
#                           site_db_path, site_configs_path):
#     """Generate one PPTX resident report per site.

#     Returns (report_count, list_of_output_paths).
#     """
#     df = pd.read_csv(master_csv_path)
#     df = df[df['SampleID'].notna() & (df['SampleID'] != "")]
#     df['LeadPPM_Clean'] = df['LeadPPM'].apply(resolve_lod)

#     # Map SampleIDs → site addresses via the site database
#     if os.path.exists(site_db_path):
#         site_db = pd.read_csv(site_db_path, header=1, encoding='latin1')
#         site_db['Address'] = site_db['Address'].ffill()
#         site_mapping = dict(
#             zip(site_db['SampleID'].dropna(), site_db['Address'].dropna())
#         )
#         df['SiteID'] = df['SampleID'].map(site_mapping).fillna(df['SampleID'])
#     else:
#         df['SiteID'] = df['SampleID']

#     # Load site configs
#     site_configs = {}
#     if os.path.exists(site_configs_path):
#         with open(site_configs_path, 'r') as f:
#             raw = json.load(f)
#         site_configs = {s["address"]: s for s in raw}

#     site_averages = df.groupby('SiteID')['LeadPPM_Clean'].mean().reset_index()

#     os.makedirs(output_dir, exist_ok=True)
#     maps_dir = os.path.join(output_dir, "map_images")
#     os.makedirs(maps_dir, exist_ok=True)

#     report_count = 0
#     generated_reports = []  # list of (site_id, filepath) tuples
#     today_str = date.today().strftime("%m/%d/%Y")

#     for _, row in site_averages.iterrows():
#         site_id = str(row['SiteID'])
#         site_avg = row['LeadPPM_Clean']
#         if pd.isna(site_avg):
#             continue

#         # ── 1. Generate dark map image (only style) ──
#         map_image_path = None
#         if site_id in site_configs:
#             safe_name = "".join(
#                 c for c in site_id if c.isalnum() or c == ' '
#             ).rstrip()
#             map_image_path = os.path.join(maps_dir, f"map_{safe_name}.png")
#             try:
#                 generate_map_image(site_configs[site_id], df, map_image_path)
#             except Exception as e:
#                 st.warning(f"Could not generate map for {site_id}: {e}")
#                 map_image_path = None

#         # ── 2. Compute zone-based PPM ──
#         zone_ppm = {"backyard_ppm": None, "frontyard_ppm": None}
#         if site_id in site_configs:
#             zone_ppm = format_zone_ppm(
#                 compute_zone_averages(site_configs[site_id], df)
#             )
#         if zone_ppm["backyard_ppm"] is None:
#             zone_ppm["backyard_ppm"] = round(site_avg)

#         # ── 3. Open PPTX template ──
#         try:
#             prs = Presentation(template_path)
#         except Exception as e:
#             raise Exception(f"Failed to load PPTX template: {e}")

#         # ── 4. Walk every slide & do text replacements ──
#         for slide_idx, slide in enumerate(prs.slides):

#             # --- Text replacements ---
#             for shape in slide.shapes:
#                 if not shape.has_text_frame:
#                     continue
#                 for paragraph in shape.text_frame.paragraphs:
#                     for run in paragraph.runs:
#                         txt = run.text

#                         # Slide 0 — Cover letter
#                         if "Name of Resident" in txt:
#                             run.text = txt.replace(
#                                 "Name of Resident",
#                                 f"Resident at {site_id}",
#                             )
#                             txt = run.text
#                         if "Address of Resident" in txt:
#                             run.text = txt.replace("Address of Resident", site_id)
#                             txt = run.text
#                         # Replace standalone "Date" on the cover
#                         if txt.strip() == "Date":
#                             run.text = today_str
#                             txt = run.text

#                         # Slide 3 — Fill [###] PPM placeholders
#                         if "[###]" in txt:
#                             low = txt.lower()
#                             if "backyard" in low or "back" in low:
#                                 val = zone_ppm["backyard_ppm"]
#                                 run.text = txt.replace(
#                                     "[###]", str(val) if val else "N/A"
#                                 )
#                             elif "front" in low:
#                                 val = zone_ppm["frontyard_ppm"]
#                                 if val is not None:
#                                     run.text = txt.replace("[###]", str(val))
#                                 else:
#                                     # No front yard → blank line
#                                     run.text = ""
#                             else:
#                                 run.text = txt.replace(
#                                     "[###]", str(round(site_avg))
#                                 )
#                             txt = run.text

#                         # Legacy placeholder clean-up
#                         if "Average Lead concentration (ppm)" in txt:
#                             lbl, _ = get_nysh_category(site_avg)
#                             run.text = txt.replace(
#                                 "Average Lead concentration (ppm)",
#                                 f"Average Lead: {site_avg:.1f} ppm — {lbl}",
#                             )
#                         for old_ph in (
#                             "Visual map of property with color-coded zones",
#                             "Highlight hotspots",
#                             "Heat map of property (no basemap)",
#                             "Heat map of property with basemap",
#                         ):
#                             if old_ph in run.text:
#                                 run.text = run.text.replace(old_ph, "")

#             # --- Image insertions (map) ---
#             if map_image_path and os.path.exists(map_image_path):
#                 try:
#                     from PIL import Image as PILImage
#                     img = PILImage.open(map_image_path)
#                     img_aspect = img.width / img.height
#                 except Exception:
#                     img_aspect = 1.14  # fallback

#                 # Slide 2 — "Soil Report Summary" → dark map, no basemap
#                 # Banner "Map of Site" ends ~3.6", QR code starts ~6.2"
#                 # Available space: roughly 3.6" to 6.0" = 2.4" tall
#                 if slide_idx == 2:
#                     max_w, max_h = 6.0, 2.8
#                     if max_w / img_aspect > max_h:
#                         w, h = max_h * img_aspect, max_h
#                     else:
#                         w, h = max_w, max_w / img_aspect
#                     left = Inches((10.0 - w) / 2)
#                     top  = Inches(3.8)
#                     try:
#                         slide.shapes.add_picture(
#                             map_image_path, left, top,
#                             width=Inches(w), height=Inches(h),
#                         )
#                     except Exception as e:
#                         st.warning(
#                             f"Map insert failed (slide 3) for {site_id}: {e}"
#                         )

#                 # Slide 3 — "Detailed Results" → map below PPM text
#                 # Title + PPM lines end ~2.2", slide bottom ~7.0"
#                 # Available: roughly 2.2" to 7.0" = 4.8" tall
#                 if slide_idx == 3:
#                     max_w, max_h = 7.0, 4.2
#                     if max_w / img_aspect > max_h:
#                         w, h = max_h * img_aspect, max_h
#                     else:
#                         w, h = max_w, max_w / img_aspect
#                     left = Inches((10.0 - w) / 2)
#                     top  = Inches(2.6)
#                     try:
#                         slide.shapes.add_picture(
#                             map_image_path, left, top,
#                             width=Inches(w), height=Inches(h),
#                         )
#                     except Exception as e:
#                         st.warning(
#                             f"Map insert failed (slide 4) for {site_id}: {e}"
#                         )

#         # ── 5. Save the report ──
#         safe_filename = "".join(
#             c for c in site_id if c.isalnum() or c == ' '
#         ).rstrip()
#         output_file = os.path.join(
#             output_dir, f"Resident_Report_{safe_filename}.pptx"
#         )
#         prs.save(output_file)
#         generated_reports.append((site_id, output_file))
#         report_count += 1

#     return report_count, generated_reports


# # ═══════════════════════════════════════════════
# #  UI: HEADER & INSTRUCTIONS
# # ═══════════════════════════════════════════════
# col_header, col_info = st.columns([2, 1])
# with col_header:
#     st.title("⚙️ Data Pipeline Manager")
#     st.markdown("Automated ETL, spatial mapping, and resident report generation.")
# with col_info:
#     st.info(
#         "💡 **Instructions:** Drag and drop your raw XRF `.csv` files below. "
#         "The backend will parse the readings, append them to the Master Database, "
#         "and automatically generate updated site reports."
#     )

# st.markdown("---")

# # ═══════════════════════════════════════════════
# #  UI: UPLOAD & PROCESS
# # ═══════════════════════════════════════════════
# st.subheader("1. Ingest Data")
# uploaded_files = st.file_uploader(
#     "Upload Raw XRF Chemistry Files", type=['csv'], accept_multiple_files=True
# )

# if st.button("🚀 Execute Data Pipeline", type="primary", use_container_width=True):
#     if not uploaded_files:
#         st.warning("⚠️ Please upload at least one chemistry CSV file to begin.")
#     else:
#         with st.status("Executing the Data Pipeline...", expanded=False) as status:
#             try:
#                 # 1. Save uploaded files
#                 xrf_dir = os.path.join("data", "xrf_data")
#                 os.makedirs(xrf_dir, exist_ok=True)
#                 for f in uploaded_files:
#                     with open(os.path.join(xrf_dir, f.name), "wb") as f_out:
#                         f_out.write(f.read())

#                 # 2. Run ETL script
#                 result = subprocess.run(
#                     ["python", "src/data.py"], capture_output=True, text=True
#                 )
#                 if result.returncode != 0:
#                     status.update(
#                         label="Pipeline Failed during ETL process.", state="error"
#                     )
#                     st.error(f"Backend Error Output:\n{result.stderr}")
#                     st.stop()

#                 # 3. Locate Master Data
#                 master_dir = os.path.join("data", "master_data")
#                 master_files = glob.glob(
#                     os.path.join(master_dir, 'Master_Data_v*.csv')
#                 )
#                 if not master_files:
#                     status.update(
#                         label="Failed to locate output Master Data.", state="error"
#                     )
#                     st.stop()

#                 latest_master = max(
#                     master_files,
#                     key=lambda x: int(
#                         re.search(r'_v(\d+)\.csv', x).group(1)
#                         if re.search(r'_v(\d+)\.csv', x) else 0
#                     ),
#                 )
#                 st.session_state.latest_master_file = latest_master

#                 # 4. Generate Reports
#                 template_path    = os.path.join("src", "Resident_Report_Template.pptx")
#                 site_db_path     = os.path.join(
#                     "data", "site_databases",
#                     "XRF Site Analysis Database W SampleID(Sheet1).csv",
#                 )
#                 site_configs_path = os.path.join(
#                     "data", "site_configs", "site_configs.json"
#                 )
#                 reports_dir  = os.path.join("data", "generated_reports")

#                 if os.path.exists(template_path):
#                     report_count, report_list = generate_pptx_reports(
#                         st.session_state.latest_master_file,
#                         template_path, reports_dir,
#                         site_db_path, site_configs_path,
#                     )
#                     st.session_state.reports_generated = report_count
#                     st.session_state.generated_report_list = report_list
#                 else:
#                     st.warning("⚠️ Template missing. Skipped report generation.")

#                 status.update(
#                     label="Pipeline Execution Complete!", state="complete"
#                 )
#                 st.session_state.pipeline_success = True

#             except Exception as e:
#                 status.update(label="Critical System Error", state="error")
#                 st.error(f"An unexpected error occurred: {str(e)}")
#                 st.session_state.pipeline_success = False

# # ═══════════════════════════════════════════════
# #  UI: RESULTS & EXPORT
# # ═══════════════════════════════════════════════
# if st.session_state.pipeline_success and st.session_state.latest_master_file:
#     st.markdown("---")
#     st.subheader("2. Deployment Artifacts")

#     # KPIs
#     df_result = pd.read_csv(st.session_state.latest_master_file)
#     kpi1, kpi2, kpi3 = st.columns(3)
#     kpi1.metric("Total Records Processed", len(df_result))
#     kpi2.metric(
#         "Sites Evaluated",
#         df_result['SampleID'].nunique() if 'SampleID' in df_result else "N/A",
#     )
#     kpi3.metric("Resident Reports Generated", st.session_state.reports_generated)

#     st.write("")

#     # Download Buttons
#     col_dl1, col_dl2 = st.columns(2)
#     with col_dl1:
#         st.success("### 📊 Master Database")
#         st.caption(
#             f"File: `{os.path.basename(st.session_state.latest_master_file)}`"
#         )
#         with open(st.session_state.latest_master_file, "rb") as file:
#             st.download_button(
#                 label="📥 Download Master Data (CSV)",
#                 data=file,
#                 file_name=os.path.basename(st.session_state.latest_master_file),
#                 mime="text/csv",
#                 use_container_width=True,
#             )

#     with col_dl2:
#         st.info("### 🗂️ Generated Reports")
#         report_list = st.session_state.get("generated_report_list", [])
#         if report_list:
#             st.caption(
#                 f"{len(report_list)} report(s) generated in this run."
#             )
#             for idx, (site_name, report_path) in enumerate(report_list):
#                 if os.path.exists(report_path):
#                     with open(report_path, "rb") as rpt_file:
#                         st.download_button(
#                             label=f"📥 Download: {site_name}",
#                             data=rpt_file,
#                             file_name=os.path.basename(report_path),
#                             mime="application/vnd.openxmlformats-officedocument"
#                                  ".presentationml.presentation",
#                             use_container_width=True,
#                             key=f"dl_report_{idx}",
#                         )
#         else:
#             st.caption("No reports were generated in this run.")

# ###################
# """
# etl_manager.py — GroundSense Data Pipeline Manager

# Updates from original:
#   1. Imports NYSH colors from groundsense_config.py
#   2. Generates static map images (matplotlib, dark style only) for each site
#   3. Inserts map images into correct slides of the Resident Report PPTX template
#   4. Fills in zone-based average Lead PPM values (backyard / front yard)

# Template slide layout (6 pages, 0-indexed):
#   Slide 0: Cover letter — replace "Address of Resident", "Name of Resident", "Date"
#   Slide 1: Sample Collection Method — keep as-is
#   Slide 2: Soil Report Summary — insert dark map (no basemap)
#   Slide 3: Detailed Results — fill [###] with real PPM, insert map
#   Slide 4: NY Soil Health info — keep as-is
#   Slide 5: Lead level table & safety — keep as-is
# """


# import streamlit as st
# import os
# import sys
# import glob
# import re
# import subprocess
# import json
# import math
# import pandas as pd
# import numpy as np
# import matplotlib
# matplotlib.use('Agg')
# import matplotlib.pyplot as plt
# import matplotlib.patches as mpatches
# from matplotlib.patches import FancyBboxPatch
# from pptx import Presentation
# from pptx.util import Inches
# from datetime import date

# # Inject src to path so groundsense_config can be imported
# sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

# from groundsense_config import (
#     get_nysh_category,
#     NYSH_TIERS,
#     NYSH_COLORS,
#     calculate_coordinate,
#     resolve_lod,
# )

# # ═══════════════════════════════════════════════
# #  PAGE CONFIGURATION
# # ═══════════════════════════════════════════════
# st.set_page_config(page_title="GroundSense Pipeline", page_icon="⚙️", layout="wide")

# # Initialize Session State
# if 'pipeline_success' not in st.session_state:
#     st.session_state.pipeline_success = False
# if 'latest_master_file' not in st.session_state:
#     st.session_state.latest_master_file = None
# if 'reports_generated' not in st.session_state:
#     st.session_state.reports_generated = 0
# if 'generated_report_list' not in st.session_state:
#     st.session_state.generated_report_list = []

# # ═══════════════════════════════════════════════
# #  MAP IMAGE GENERATOR (matplotlib) — DARK ONLY
# # ═══════════════════════════════════════════════
# def generate_map_image(site_config, master_df, output_path):
#     """Generates a static dark-style PNG map image of a site's grid
#     with NYSH coloring.  No light/white variant is produced."""
#     anchor = site_config["anchor"]
#     grid = site_config.get("grid_blocks", {})
#     points = site_config.get("point_samples", {})

#     # Ensure LeadPPM_Clean column exists (work on a copy to avoid side-effects)
#     if 'LeadPPM_Clean' not in master_df.columns:
#         master_df = master_df.copy()
#         master_df['LeadPPM_Clean'] = master_df['LeadPPM'].apply(resolve_lod)

#     def match_ppm(patterns):
#         for pat in patterns:
#             if not pat:
#                 continue
#             matches = master_df[master_df['SampleID'].str.contains(pat, case=False, na=False)]
#             if not matches.empty:
#                 avg = matches['LeadPPM_Clean'].mean()
#                 if pd.notna(avg):
#                     return avg
#         return None

#     # Dark style constants
#     bg       = '#1a1c24'
#     text_c   = 'white'
#     edge_c   = 'white'

#     fig, ax = plt.subplots(1, 1, figsize=(8, 7), facecolor=bg)
#     ax.set_facecolor(bg)

#     all_x, all_y = [], []

#     for block_id, dims in grid.items():
#         if block_id.startswith("_"):
#             continue
#         sx, sy = dims["sw_x"], dims["sw_y"]
#         w = dims["ne_x"] - dims["sw_x"]
#         h = dims["ne_y"] - dims["sw_y"]

#         patterns = dims.get("sample_id_patterns", [])
#         ppm = match_ppm(patterns)
#         if ppm is None:
#             ppm = dims.get("mock_ppm", 0)

#         _label, color = get_nysh_category(ppm)

#         rect = FancyBboxPatch(
#             (sx, sy), w, h, boxstyle="round,pad=0.3",
#             facecolor=color, edgecolor=edge_c, linewidth=1.5, alpha=0.8,
#         )
#         ax.add_patch(rect)

#         cx, cy = sx + w / 2, sy + h / 2
#         ax.text(cx, cy, block_id, ha='center', va='center',
#                 fontsize=8, fontweight='bold', color='white',
#                 bbox=dict(boxstyle='round,pad=0.15', facecolor='black', alpha=0.4))
#         ax.text(cx, cy - h * 0.25, "{:.0f}".format(ppm),
#                 ha='center', va='center', fontsize=7, color='white', alpha=0.9)

#         all_x.extend([sx, sx + w])
#         all_y.extend([sy, sy + h])

#     # Point samples
#     for pt_id, pt in points.items():
#         if pt_id.startswith("_"):
#             continue
#         ox, oy = pt.get("offset_x", 0), pt.get("offset_y", 0)
#         patterns = pt.get("sample_id_patterns", [])
#         ppm = match_ppm(patterns)

#         if ppm is not None:
#             _label, color = get_nysh_category(ppm)
#             ppm_str = "{:.0f}".format(ppm)
#         else:
#             color, ppm_str = "#808080", "?"

#         ax.plot(ox, oy, 'o', markersize=10, color=color,
#                 markeredgecolor=edge_c, markeredgewidth=1.5)
#         ax.text(ox, oy + 2.5, pt_id, ha='center', va='bottom',
#                 fontsize=6, color='#cccccc', fontstyle='italic')
#         ax.text(ox, oy - 2.5, ppm_str, ha='center', va='top',
#                 fontsize=6, color='white', fontweight='bold')
#         all_x.append(ox)
#         all_y.append(oy)

#     # Anchor marker
#     ax.plot(0, 0, marker='^', markersize=12, color='red',
#             markeredgecolor=edge_c, markeredgewidth=1.5, zorder=10)
#     ax.text(0, -3, "Anchor", ha='center', va='top',
#             fontsize=7, color='red', fontweight='bold')

#     if all_x and all_y:
#         pad = 10
#         ax.set_xlim(min(all_x) - pad, max(all_x) + pad)
#         ax.set_ylim(min(all_y) - pad, max(all_y) + pad)

#     ax.set_aspect('equal')
#     ax.set_xlabel('East (ft)', color='#888888', fontsize=9)
#     ax.set_ylabel('North (ft)', color='#888888', fontsize=9)
#     ax.tick_params(colors='#666666', labelsize=7)
#     for spine in ax.spines.values():
#         spine.set_color('#333333')

#     site_name = site_config.get("address", "Site")
#     ax.set_title(f"{site_name} — Lead Contamination Map",
#                  color=text_c, fontsize=12, fontweight='bold', pad=12)

#     legend_patches = [mpatches.Patch(color=t["color"], label=t["label"])
#                       for t in NYSH_TIERS]
#     legend_patches.append(mpatches.Patch(color="#808080", label="No Data"))
#     ax.legend(handles=legend_patches, loc='lower right', fontsize=6,
#               framealpha=0.8, facecolor='#2a2d38', edgecolor='#444444',
#               labelcolor='white')

#     plt.tight_layout()
#     plt.savefig(output_path, dpi=200, bbox_inches='tight',
#                 facecolor=bg, edgecolor='none')
#     plt.close()
#     return output_path


# # ═══════════════════════════════════════════════
# #  ZONE-BASED PPM CALCULATOR
# # ═══════════════════════════════════════════════
# def compute_zone_averages(site_config, master_df):
#     """Compute average Lead PPM for each zone (back, front, yard, transect).

#     Returns dict, e.g. {"back": 542.3, "front": 718.1}
#     """
#     grid = site_config.get("grid_blocks", {})

#     if 'LeadPPM_Clean' not in master_df.columns:
#         master_df = master_df.copy()
#         master_df['LeadPPM_Clean'] = master_df['LeadPPM'].apply(resolve_lod)

#     zone_values = {}  # zone_name -> [ppm, ...]

#     for block_id, dims in grid.items():
#         if block_id.startswith("_"):
#             continue
#         zone = dims.get("zone", "yard")
#         patterns = dims.get("sample_id_patterns", [])

#         ppm = None
#         for pat in patterns:
#             if not pat:
#                 continue
#             matches = master_df[
#                 master_df['SampleID'].str.contains(pat, case=False, na=False)
#             ]
#             if not matches.empty:
#                 avg = matches['LeadPPM_Clean'].mean()
#                 if pd.notna(avg):
#                     ppm = avg
#                     break

#         if ppm is None:
#             ppm = dims.get("mock_ppm")

#         if ppm is not None and not (isinstance(ppm, float) and math.isnan(ppm)):
#             zone_values.setdefault(zone, []).append(ppm)

#     return {z: sum(v) / len(v) for z, v in zone_values.items() if v}


# def format_zone_ppm(zone_averages):
#     """Map zone averages to backyard_ppm / frontyard_ppm for template filling.

#     Single-zone sites (yard, transect) map to backyard only.
#     """
#     result = {"backyard_ppm": None, "frontyard_ppm": None}
#     for zone, avg in zone_averages.items():
#         z = zone.lower()
#         if z in ("back", "backyard"):
#             result["backyard_ppm"] = round(avg)
#         elif z in ("front", "frontyard", "front_yard"):
#             result["frontyard_ppm"] = round(avg)
#         elif z in ("yard", "transect"):
#             result["backyard_ppm"] = round(avg)
#     return result


# # ═══════════════════════════════════════════════
# #  REPORT GENERATION (PPTX)
# # ═══════════════════════════════════════════════
# def generate_pptx_reports(master_csv_path, template_path, output_dir,
#                           site_db_path, site_configs_path):
#     """Generate one PPTX resident report per site.

#     Returns (report_count, list_of_output_paths).
#     """
#     df = pd.read_csv(master_csv_path)
#     df = df[df['SampleID'].notna() & (df['SampleID'] != "")]
#     df['LeadPPM_Clean'] = df['LeadPPM'].apply(resolve_lod)

#     # Map SampleIDs → site addresses via the site database
#     if os.path.exists(site_db_path):
#         site_db = pd.read_csv(site_db_path, header=1, encoding='latin1')
#         site_db['Address'] = site_db['Address'].ffill()
#         site_mapping = dict(
#             zip(site_db['SampleID'].dropna(), site_db['Address'].dropna())
#         )
#         df['SiteID'] = df['SampleID'].map(site_mapping).fillna(df['SampleID'])
#     else:
#         df['SiteID'] = df['SampleID']

#     # Load site configs
#     site_configs = {}
#     if os.path.exists(site_configs_path):
#         with open(site_configs_path, 'r') as f:
#             raw = json.load(f)
#         site_configs = {s["address"]: s for s in raw}

#     site_averages = df.groupby('SiteID')['LeadPPM_Clean'].mean().reset_index()

#     os.makedirs(output_dir, exist_ok=True)
#     maps_dir = os.path.join(output_dir, "map_images")
#     os.makedirs(maps_dir, exist_ok=True)

#     report_count = 0
#     generated_reports = []  # list of (site_id, filepath) tuples
#     today_str = date.today().strftime("%m/%d/%Y")

#     for _, row in site_averages.iterrows():
#         site_id = str(row['SiteID'])
#         site_avg = row['LeadPPM_Clean']
#         if pd.isna(site_avg):
#             continue

#         # ── 1. Generate dark map image (only style) ──
#         map_image_path = None
#         if site_id in site_configs:
#             safe_name = "".join(
#                 c for c in site_id if c.isalnum() or c == ' '
#             ).rstrip()
#             map_image_path = os.path.join(maps_dir, f"map_{safe_name}.png")
#             try:
#                 generate_map_image(site_configs[site_id], df, map_image_path)
#             except Exception as e:
#                 st.warning(f"Could not generate map for {site_id}: {e}")
#                 map_image_path = None

#         # ── 2. Compute zone-based PPM ──
#         zone_ppm = {"backyard_ppm": None, "frontyard_ppm": None}
#         if site_id in site_configs:
#             zone_ppm = format_zone_ppm(
#                 compute_zone_averages(site_configs[site_id], df)
#             )
#         if zone_ppm["backyard_ppm"] is None:
#             zone_ppm["backyard_ppm"] = round(site_avg)

#         # ── 3. Open PPTX template ──
#         try:
#             prs = Presentation(template_path)
#         except Exception as e:
#             raise Exception(f"Failed to load PPTX template: {e}")

#         # ── 4. Walk every slide & do text replacements ──
#         for slide_idx, slide in enumerate(prs.slides):

#             # --- Text replacements ---
#             for shape in slide.shapes:
#                 if not shape.has_text_frame:
#                     continue
#                 for paragraph in shape.text_frame.paragraphs:
#                     for run in paragraph.runs:
#                         txt = run.text

#                         # Slide 0 — Cover letter
#                         if "Name of Resident" in txt:
#                             run.text = txt.replace(
#                                 "Name of Resident",
#                                 f"Resident at {site_id}",
#                             )
#                             txt = run.text
#                         if "Address of Resident" in txt:
#                             run.text = txt.replace("Address of Resident", site_id)
#                             txt = run.text
#                         # Replace standalone "Date" on the cover
#                         if txt.strip() == "Date":
#                             run.text = today_str
#                             txt = run.text

#                         # Slide 3 — Fill [###] PPM placeholders
#                         if "[###]" in txt:
#                             low = txt.lower()
#                             if "backyard" in low or "back" in low:
#                                 val = zone_ppm["backyard_ppm"]
#                                 run.text = txt.replace(
#                                     "[###]", str(val) if val else "N/A"
#                                 )
#                             elif "front" in low:
#                                 val = zone_ppm["frontyard_ppm"]
#                                 if val is not None:
#                                     run.text = txt.replace("[###]", str(val))
#                                 else:
#                                     # No front yard → blank line
#                                     run.text = ""
#                             else:
#                                 run.text = txt.replace(
#                                     "[###]", str(round(site_avg))
#                                 )
#                             txt = run.text

#                         # Legacy placeholder clean-up
#                         if "Average Lead concentration (ppm)" in txt:
#                             lbl, _ = get_nysh_category(site_avg)
#                             run.text = txt.replace(
#                                 "Average Lead concentration (ppm)",
#                                 f"Average Lead: {site_avg:.1f} ppm — {lbl}",
#                             )
#                         for old_ph in (
#                             "Visual map of property with color-coded zones",
#                             "Highlight hotspots",
#                             "Heat map of property (no basemap)",
#                             "Heat map of property with basemap",
#                         ):
#                             if old_ph in run.text:
#                                 run.text = run.text.replace(old_ph, "")

#             # --- Image insertions (map) ---
#             if map_image_path and os.path.exists(map_image_path):
#                 try:
#                     from PIL import Image as PILImage
#                     img = PILImage.open(map_image_path)
#                     img_aspect = img.width / img.height
#                 except Exception:
#                     img_aspect = 1.14  # fallback

#                 # Slide 2 — "Soil Report Summary" → dark map, no basemap
#                 # Banner "Map of Site" ends ~3.6", QR code starts ~6.2"
#                 # Available space: roughly 3.6" to 6.0" = 2.4" tall
#                 if slide_idx == 2:
#                     max_w, max_h = 6.0, 2.8
#                     if max_w / img_aspect > max_h:
#                         w, h = max_h * img_aspect, max_h
#                     else:
#                         w, h = max_w, max_w / img_aspect
#                     left = Inches((10.0 - w) / 2)
#                     top  = Inches(3.8)
#                     try:
#                         slide.shapes.add_picture(
#                             map_image_path, left, top,
#                             width=Inches(w), height=Inches(h),
#                         )
#                     except Exception as e:
#                         st.warning(
#                             f"Map insert failed (slide 3) for {site_id}: {e}"
#                         )

#                 # Slide 3 — "Detailed Results" → map below PPM text
#                 # Title + PPM lines end ~2.2", slide bottom ~7.0"
#                 # Available: roughly 2.2" to 7.0" = 4.8" tall
#                 if slide_idx == 3:
#                     max_w, max_h = 7.0, 4.2
#                     if max_w / img_aspect > max_h:
#                         w, h = max_h * img_aspect, max_h
#                     else:
#                         w, h = max_w, max_w / img_aspect
#                     left = Inches((10.0 - w) / 2)
#                     top  = Inches(2.6)
#                     try:
#                         slide.shapes.add_picture(
#                             map_image_path, left, top,
#                             width=Inches(w), height=Inches(h),
#                         )
#                     except Exception as e:
#                         st.warning(
#                             f"Map insert failed (slide 4) for {site_id}: {e}"
#                         )

#         # ── 5. Save the report ──
#         safe_filename = "".join(
#             c for c in site_id if c.isalnum() or c == ' '
#         ).rstrip()
#         output_file = os.path.join(
#             output_dir, f"Resident_Report_{safe_filename}.pptx"
#         )
#         prs.save(output_file)
#         generated_reports.append((site_id, output_file))
#         report_count += 1

#     return report_count, generated_reports


# # ═══════════════════════════════════════════════
# #  UI: HEADER & INSTRUCTIONS
# # ═══════════════════════════════════════════════
# col_header, col_info = st.columns([2, 1])
# with col_header:
#     st.title("⚙️ Data Pipeline Manager")
#     st.markdown("Automated ETL, spatial mapping, and resident report generation.")
# with col_info:
#     st.info(
#         "💡 **Instructions:** Drag and drop your raw XRF `.csv` files below. "
#         "The backend will parse the readings, append them to the Master Database, "
#         "and automatically generate updated site reports."
#     )

# st.markdown("---")

# # ═══════════════════════════════════════════════
# #  UI: UPLOAD & PROCESS
# # ═══════════════════════════════════════════════
# st.subheader("1. Ingest Data")
# uploaded_files = st.file_uploader(
#     "Upload Raw XRF Chemistry Files", type=['csv'], accept_multiple_files=True
# )

# if st.button("🚀 Execute Data Pipeline", type="primary", use_container_width=True):
#     if not uploaded_files:
#         st.warning("⚠️ Please upload at least one chemistry CSV file to begin.")
#     else:
#         with st.status("Executing the Data Pipeline...", expanded=False) as status:
#             try:
#                 # 1. Save uploaded files
#                 xrf_dir = os.path.join("data", "xrf_data")
#                 os.makedirs(xrf_dir, exist_ok=True)
#                 for f in uploaded_files:
#                     with open(os.path.join(xrf_dir, f.name), "wb") as f_out:
#                         f_out.write(f.read())

#                 # 2. Run ETL script
#                 result = subprocess.run(
#                     ["python", "src/data.py"], capture_output=True, text=True
#                 )
#                 if result.returncode != 0:
#                     status.update(
#                         label="Pipeline Failed during ETL process.", state="error"
#                     )
#                     st.error(f"Backend Error Output:\n{result.stderr}")
#                     st.stop()

#                 # 3. Locate Master Data
#                 master_dir = os.path.join("data", "master_data")
#                 master_files = glob.glob(
#                     os.path.join(master_dir, 'Master_Data_v*.csv')
#                 )
#                 if not master_files:
#                     status.update(
#                         label="Failed to locate output Master Data.", state="error"
#                     )
#                     st.stop()

#                 latest_master = max(
#                     master_files,
#                     key=lambda x: int(
#                         re.search(r'_v(\d+)\.csv', x).group(1)
#                         if re.search(r'_v(\d+)\.csv', x) else 0
#                     ),
#                 )
#                 st.session_state.latest_master_file = latest_master

#                 # 4. Generate Reports
#                 template_path    = os.path.join("src", "Resident_Report_Template.pptx")
#                 site_db_path     = os.path.join(
#                     "data", "site_databases",
#                     "XRF Site Analysis Database W SampleID(Sheet1).csv",
#                 )
#                 site_configs_path = os.path.join(
#                     "data", "site_configs", "site_configs.json"
#                 )
#                 reports_dir  = os.path.join("data", "generated_reports")

#                 if os.path.exists(template_path):
#                     report_count, report_list = generate_pptx_reports(
#                         st.session_state.latest_master_file,
#                         template_path, reports_dir,
#                         site_db_path, site_configs_path,
#                     )
#                     st.session_state.reports_generated = report_count
#                     st.session_state.generated_report_list = report_list
#                 else:
#                     st.warning("⚠️ Template missing. Skipped report generation.")

#                 status.update(
#                     label="Pipeline Execution Complete!", state="complete"
#                 )
#                 st.session_state.pipeline_success = True

#             except Exception as e:
#                 status.update(label="Critical System Error", state="error")
#                 st.error(f"An unexpected error occurred: {str(e)}")
#                 st.session_state.pipeline_success = False

# # ═══════════════════════════════════════════════
# #  UI: RESULTS & EXPORT
# # ═══════════════════════════════════════════════
# if st.session_state.pipeline_success and st.session_state.latest_master_file:
#     st.markdown("---")
#     st.subheader("2. Deployment Artifacts")

#     # KPIs
#     df_result = pd.read_csv(st.session_state.latest_master_file)
#     kpi1, kpi2, kpi3 = st.columns(3)
#     kpi1.metric("Total Records Processed", len(df_result))
#     kpi2.metric(
#         "Sites Evaluated",
#         df_result['SampleID'].nunique() if 'SampleID' in df_result else "N/A",
#     )
#     kpi3.metric("Resident Reports Generated", st.session_state.reports_generated)

#     st.write("")

#     # Download Buttons
#     col_dl1, col_dl2 = st.columns(2)
#     with col_dl1:
#         st.success("### 📊 Master Database")
#         st.caption(
#             f"File: `{os.path.basename(st.session_state.latest_master_file)}`"
#         )
#         with open(st.session_state.latest_master_file, "rb") as file:
#             st.download_button(
#                 label="📥 Download Master Data (CSV)",
#                 data=file,
#                 file_name=os.path.basename(st.session_state.latest_master_file),
#                 mime="text/csv",
#                 use_container_width=True,
#             )

#     with col_dl2:
#         st.info("### 🗂️ Generated Reports")
#         report_list = st.session_state.get("generated_report_list", [])
#         if report_list:
#             st.caption(
#                 f"{len(report_list)} report(s) generated in this run."
#             )
#             for idx, (site_name, report_path) in enumerate(report_list):
#                 if os.path.exists(report_path):
#                     with open(report_path, "rb") as rpt_file:
#                         st.download_button(
#                             label=f"📥 Download: {site_name}",
#                             data=rpt_file,
#                             file_name=os.path.basename(report_path),
#                             mime="application/vnd.openxmlformats-officedocument"
#                                  ".presentationml.presentation",
#                             use_container_width=True,
#                             key=f"dl_report_{idx}",
#                         )
#         else:
#             st.caption("No reports were generated in this run.")

"""
etl_manager.py — GroundSense Data Pipeline Manager

Updates from original:
  1. Imports NYSH colors from groundsense_config.py
  2. Generates static map images (matplotlib, dark style only) for each site
  3. Inserts map images into correct slides of the Resident Report PPTX template
  4. Fills in zone-based average Lead PPM values (backyard / front yard)

Template slide layout (6 pages, 0-indexed):
  Slide 0: Cover letter — replace "Address of Resident", "Name of Resident", "Date"
  Slide 1: Sample Collection Method — keep as-is
  Slide 2: Soil Report Summary — insert dark map (no basemap)
  Slide 3: Detailed Results — fill [###] with real PPM, insert map
  Slide 4: NY Soil Health info — keep as-is
  Slide 5: Lead level table & safety — keep as-is
"""


import streamlit as st
import os
import sys
import glob
import re
import subprocess
import json
import math
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from pptx import Presentation
from pptx.util import Inches
from datetime import date

# Inject src to path so groundsense_config can be imported
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from groundsense_config import (
    get_nysh_category,
    NYSH_TIERS,
    NYSH_COLORS,
    calculate_coordinate,
    resolve_lod,
)

# ═══════════════════════════════════════════════
#  PAGE CONFIGURATION
# ═══════════════════════════════════════════════
st.set_page_config(page_title="GroundSense Pipeline", page_icon="⚙️", layout="wide")

# Initialize Session State
if 'pipeline_success' not in st.session_state:
    st.session_state.pipeline_success = False
if 'latest_master_file' not in st.session_state:
    st.session_state.latest_master_file = None
if 'reports_generated' not in st.session_state:
    st.session_state.reports_generated = 0
if 'generated_report_list' not in st.session_state:
    st.session_state.generated_report_list = []

# ═══════════════════════════════════════════════
#  MAP IMAGE GENERATOR (matplotlib) — DARK ONLY
# ═══════════════════════════════════════════════
def generate_map_image(site_config, master_df, output_path):
    """Generates a static dark-style PNG map image of a site's grid
    with NYSH coloring.  No light/white variant is produced."""
    anchor = site_config["anchor"]
    grid = site_config.get("grid_blocks", {})
    points = site_config.get("point_samples", {})

    # Ensure LeadPPM_Clean column exists (work on a copy to avoid side-effects)
    if 'LeadPPM_Clean' not in master_df.columns:
        master_df = master_df.copy()
        master_df['LeadPPM_Clean'] = master_df['LeadPPM'].apply(resolve_lod)

    def match_ppm(patterns):
        for pat in patterns:
            if not pat:
                continue
            matches = master_df[master_df['SampleID'].str.contains(pat, case=False, na=False)]
            if not matches.empty:
                avg = matches['LeadPPM_Clean'].mean()
                if pd.notna(avg):
                    return avg
        return None

    # Dark style constants
    bg       = '#1a1c24'
    text_c   = 'white'
    edge_c   = 'white'

    fig, ax = plt.subplots(1, 1, figsize=(8, 7), facecolor=bg)
    ax.set_facecolor(bg)

    all_x, all_y = [], []

    for block_id, dims in grid.items():
        if block_id.startswith("_"):
            continue
        sx, sy = dims["sw_x"], dims["sw_y"]
        w = dims["ne_x"] - dims["sw_x"]
        h = dims["ne_y"] - dims["sw_y"]

        patterns = dims.get("sample_id_patterns", [])
        ppm = match_ppm(patterns)
        if ppm is None:
            ppm = dims.get("mock_ppm", 0)

        _label, color = get_nysh_category(ppm)

        rect = FancyBboxPatch(
            (sx, sy), w, h, boxstyle="round,pad=0.3",
            facecolor=color, edgecolor=edge_c, linewidth=1.5, alpha=0.8,
        )
        ax.add_patch(rect)

        cx, cy = sx + w / 2, sy + h / 2
        ax.text(cx, cy, block_id, ha='center', va='center',
                fontsize=8, fontweight='bold', color='white',
                bbox=dict(boxstyle='round,pad=0.15', facecolor='black', alpha=0.4))
        ax.text(cx, cy - h * 0.25, "{:.0f}".format(ppm),
                ha='center', va='center', fontsize=7, color='white', alpha=0.9)

        all_x.extend([sx, sx + w])
        all_y.extend([sy, sy + h])

    # Point samples
    for pt_id, pt in points.items():
        if pt_id.startswith("_"):
            continue
        ox, oy = pt.get("offset_x", 0), pt.get("offset_y", 0)
        patterns = pt.get("sample_id_patterns", [])
        ppm = match_ppm(patterns)

        if ppm is not None:
            _label, color = get_nysh_category(ppm)
            ppm_str = "{:.0f}".format(ppm)
        else:
            color, ppm_str = "#808080", "?"

        ax.plot(ox, oy, 'o', markersize=10, color=color,
                markeredgecolor=edge_c, markeredgewidth=1.5)
        ax.text(ox, oy + 2.5, pt_id, ha='center', va='bottom',
                fontsize=6, color='#cccccc', fontstyle='italic')
        ax.text(ox, oy - 2.5, ppm_str, ha='center', va='top',
                fontsize=6, color='white', fontweight='bold')
        all_x.append(ox)
        all_y.append(oy)

    # Anchor marker
    ax.plot(0, 0, marker='^', markersize=12, color='red',
            markeredgecolor=edge_c, markeredgewidth=1.5, zorder=10)
    ax.text(0, -3, "Anchor", ha='center', va='top',
            fontsize=7, color='red', fontweight='bold')

    if all_x and all_y:
        pad = 10
        ax.set_xlim(min(all_x) - pad, max(all_x) + pad)
        ax.set_ylim(min(all_y) - pad, max(all_y) + pad)

    ax.set_aspect('equal')
    ax.set_xlabel('East (ft)', color='#888888', fontsize=9)
    ax.set_ylabel('North (ft)', color='#888888', fontsize=9)
    ax.tick_params(colors='#666666', labelsize=7)
    for spine in ax.spines.values():
        spine.set_color('#333333')

    site_name = site_config.get("address", "Site")
    ax.set_title(f"{site_name} — Lead Contamination Map",
                 color=text_c, fontsize=12, fontweight='bold', pad=12)

    legend_patches = [mpatches.Patch(color=t["color"], label=t["label"])
                      for t in NYSH_TIERS]
    legend_patches.append(mpatches.Patch(color="#808080", label="No Data"))
    ax.legend(handles=legend_patches, loc='lower right', fontsize=6,
              framealpha=0.8, facecolor='#2a2d38', edgecolor='#444444',
              labelcolor='white')

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches='tight',
                facecolor=bg, edgecolor='none')
    plt.close()
    return output_path


# ═══════════════════════════════════════════════
#  ZONE-BASED PPM CALCULATOR
# ═══════════════════════════════════════════════
def compute_zone_averages(site_config, master_df):
    """Compute average Lead PPM for each zone (back, front, yard, transect).

    Returns dict, e.g. {"back": 542.3, "front": 718.1}
    """
    grid = site_config.get("grid_blocks", {})

    if 'LeadPPM_Clean' not in master_df.columns:
        master_df = master_df.copy()
        master_df['LeadPPM_Clean'] = master_df['LeadPPM'].apply(resolve_lod)

    zone_values = {}  # zone_name -> [ppm, ...]

    for block_id, dims in grid.items():
        if block_id.startswith("_"):
            continue
        zone = dims.get("zone", "yard")
        patterns = dims.get("sample_id_patterns", [])

        ppm = None
        for pat in patterns:
            if not pat:
                continue
            matches = master_df[
                master_df['SampleID'].str.contains(pat, case=False, na=False)
            ]
            if not matches.empty:
                avg = matches['LeadPPM_Clean'].mean()
                if pd.notna(avg):
                    ppm = avg
                    break

        if ppm is None:
            ppm = dims.get("mock_ppm")

        if ppm is not None and not (isinstance(ppm, float) and math.isnan(ppm)):
            zone_values.setdefault(zone, []).append(ppm)

    return {z: sum(v) / len(v) for z, v in zone_values.items() if v}


def format_zone_ppm(zone_averages):
    """Map zone averages to backyard_ppm / frontyard_ppm for template filling.

    Single-zone sites (yard, transect) map to backyard only.
    """
    result = {"backyard_ppm": None, "frontyard_ppm": None}
    for zone, avg in zone_averages.items():
        z = zone.lower()
        if z in ("back", "backyard"):
            result["backyard_ppm"] = round(avg)
        elif z in ("front", "frontyard", "front_yard"):
            result["frontyard_ppm"] = round(avg)
        elif z in ("yard", "transect"):
            result["backyard_ppm"] = round(avg)
    return result


# ═══════════════════════════════════════════════
#  REPORT GENERATION (PPTX)
# ═══════════════════════════════════════════════
def generate_pptx_reports(master_csv_path, template_path, output_dir,
                          site_db_path, site_configs_path):
    """Generate one PPTX resident report **per site address** from site_configs.json.

    Iterates over sites (addresses), NOT individual SampleIDs.
    Each site's grid_blocks contain sample_id_patterns that link to master data.

    Returns (report_count, list_of (site_address, filepath) tuples).
    """
    df = pd.read_csv(master_csv_path)
    df = df[df['SampleID'].notna() & (df['SampleID'] != "")]
    df['LeadPPM_Clean'] = df['LeadPPM'].apply(resolve_lod)

    # Load site configs — one report per site address
    site_configs = {}
    if os.path.exists(site_configs_path):
        with open(site_configs_path, 'r') as f:
            raw = json.load(f)
        site_configs = {s["address"]: s for s in raw}

    if not site_configs:
        st.warning("⚠️ No site configurations found. Cannot generate reports.")
        return 0, []

    os.makedirs(output_dir, exist_ok=True)
    maps_dir = os.path.join(output_dir, "map_images")
    os.makedirs(maps_dir, exist_ok=True)

    report_count = 0
    generated_reports = []
    today_str = date.today().strftime("%m/%d/%Y")

    for site_address, site_config in site_configs.items():

        # ── 1. Compute zone averages for this site ──
        zone_averages = compute_zone_averages(site_config, df)
        zone_ppm = format_zone_ppm(zone_averages)

        all_zone_vals = list(zone_averages.values())
        if all_zone_vals:
            site_avg = sum(all_zone_vals) / len(all_zone_vals)
        else:
            # No real data — use mock PPM for grid preview
            mock_vals = [
                b.get("mock_ppm", 0)
                for b in site_config.get("grid_blocks", {}).values()
                if b.get("mock_ppm") is not None
            ]
            site_avg = sum(mock_vals) / len(mock_vals) if mock_vals else None
            if site_avg is None:
                continue

        if zone_ppm["backyard_ppm"] is None:
            zone_ppm["backyard_ppm"] = round(site_avg)

        # ── 2. Generate dark map image ──
        safe_name = "".join(
            c for c in site_address if c.isalnum() or c == ' '
        ).rstrip()
        map_image_path = os.path.join(maps_dir, f"map_{safe_name}.png")
        try:
            generate_map_image(site_config, df, map_image_path)
        except Exception as e:
            st.warning(f"Could not generate map for {site_address}: {e}")
            map_image_path = None

        # ── 3. Open PPTX template ──
        try:
            prs = Presentation(template_path)
        except Exception as e:
            raise Exception(f"Failed to load PPTX template: {e}")

        # ── 4. Process each slide ──
        for slide_idx, slide in enumerate(prs.slides):

            for shape in slide.shapes:
                if not shape.has_text_frame:
                    continue
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        txt = run.text

                        # Slide 0 — Cover letter
                        if "Name of Resident" in txt:
                            run.text = txt.replace(
                                "Name of Resident",
                                f"Resident at {site_address}",
                            )
                            txt = run.text
                        if "Address of Resident" in txt:
                            run.text = txt.replace(
                                "Address of Resident", site_address
                            )
                            txt = run.text
                        if txt.strip() == "Date":
                            run.text = today_str
                            txt = run.text

                        # Slide 3 — Fill [###] PPM
                        if "[###]" in txt:
                            low = txt.lower()
                            if "backyard" in low or "back" in low:
                                val = zone_ppm["backyard_ppm"]
                                run.text = txt.replace(
                                    "[###]", str(val) if val else "N/A"
                                )
                            elif "front" in low:
                                val = zone_ppm["frontyard_ppm"]
                                if val is not None:
                                    run.text = txt.replace("[###]", str(val))
                                else:
                                    run.text = ""
                            else:
                                run.text = txt.replace(
                                    "[###]", str(round(site_avg))
                                )
                            txt = run.text

                        # Legacy placeholders
                        if "Average Lead concentration (ppm)" in txt:
                            lbl, _ = get_nysh_category(site_avg)
                            run.text = txt.replace(
                                "Average Lead concentration (ppm)",
                                f"Average Lead: {site_avg:.1f} ppm — {lbl}",
                            )
                        for old_ph in (
                            "Visual map of property with color-coded zones",
                            "Highlight hotspots",
                            "Heat map of property (no basemap)",
                            "Heat map of property with basemap",
                        ):
                            if old_ph in run.text:
                                run.text = run.text.replace(old_ph, "")

            # --- Map image insertions ---
            if map_image_path and os.path.exists(map_image_path):
                try:
                    from PIL import Image as PILImage
                    img = PILImage.open(map_image_path)
                    img_aspect = img.width / img.height
                except Exception:
                    img_aspect = 1.14

                if slide_idx == 2:
                    max_w, max_h = 6.0, 2.8
                    if max_w / img_aspect > max_h:
                        w, h = max_h * img_aspect, max_h
                    else:
                        w, h = max_w, max_w / img_aspect
                    left = Inches((10.0 - w) / 2)
                    top = Inches(3.8)
                    try:
                        slide.shapes.add_picture(
                            map_image_path, left, top,
                            width=Inches(w), height=Inches(h),
                        )
                    except Exception as e:
                        st.warning(f"Map insert failed (slide 3) for {site_address}: {e}")

                if slide_idx == 3:
                    max_w, max_h = 7.0, 4.2
                    if max_w / img_aspect > max_h:
                        w, h = max_h * img_aspect, max_h
                    else:
                        w, h = max_w, max_w / img_aspect
                    left = Inches((10.0 - w) / 2)
                    top = Inches(2.6)
                    try:
                        slide.shapes.add_picture(
                            map_image_path, left, top,
                            width=Inches(w), height=Inches(h),
                        )
                    except Exception as e:
                        st.warning(f"Map insert failed (slide 4) for {site_address}: {e}")

        # ── 5. Save ──
        output_file = os.path.join(
            output_dir, f"Resident_Report_{safe_name}.pptx"
        )
        prs.save(output_file)
        generated_reports.append((site_address, output_file))
        report_count += 1

    return report_count, generated_reports

# ═══════════════════════════════════════════════
#  UI: HEADER & INSTRUCTIONS
# ═══════════════════════════════════════════════
col_header, col_info = st.columns([2, 1])
with col_header:
    st.title("⚙️ Data Pipeline Manager")
    st.markdown("Automated ETL, spatial mapping, and resident report generation.")
with col_info:
    st.info(
        "💡 **Instructions:** Drag and drop your raw XRF `.csv` files below. "
        "The backend will parse the readings, append them to the Master Database, "
        "and automatically generate updated site reports."
    )

st.markdown("---")

# ═══════════════════════════════════════════════
#  UI: UPLOAD & PROCESS
# ═══════════════════════════════════════════════
st.subheader("1. Ingest Data")
uploaded_files = st.file_uploader(
    "Upload Raw XRF Chemistry Files", type=['csv'], accept_multiple_files=True
)

fresh_rebuild = st.checkbox(
    "🔄 Fresh rebuild (clear old Master Data and reprocess all files)",
    value=False,
    help="Check this if you've updated data.py or the XRF Master Data Key "
         "and need to regenerate everything from scratch.",
)

if st.button("🚀 Execute Data Pipeline", type="primary", use_container_width=True):
    if not uploaded_files:
        st.warning("⚠️ Please upload at least one chemistry CSV file to begin.")
    else:
        with st.status("Executing the Data Pipeline...", expanded=False) as status:
            try:
                # 1. Save uploaded files
                xrf_dir = os.path.join("data", "xrf_data")
                os.makedirs(xrf_dir, exist_ok=True)
                for f in uploaded_files:
                    with open(os.path.join(xrf_dir, f.name), "wb") as f_out:
                        f_out.write(f.read())

                # 1b. If fresh rebuild, clear old master data
                if fresh_rebuild:
                    master_dir = os.path.join("data", "master_data")
                    if os.path.exists(master_dir):
                        import shutil
                        shutil.rmtree(master_dir)
                    os.makedirs(master_dir, exist_ok=True)
                    st.info("🗑️ Cleared old Master Data. Rebuilding from scratch.")

                # 2. Run ETL script
                result = subprocess.run(
                    ["python", "src/data.py"], capture_output=True, text=True
                )

                # Show ETL output for transparency
                if result.stdout.strip():
                    st.code(result.stdout, language="text")

                if result.returncode != 0:
                    status.update(
                        label="Pipeline Failed during ETL process.", state="error"
                    )
                    st.error(f"Backend Error Output:\n{result.stderr}")
                    st.stop()

                # 3. Locate Master Data
                master_dir = os.path.join("data", "master_data")
                master_files = glob.glob(
                    os.path.join(master_dir, 'Master_Data_v*.csv')
                )
                if not master_files:
                    status.update(
                        label="Failed to locate output Master Data.", state="error"
                    )
                    st.stop()

                latest_master = max(
                    master_files,
                    key=lambda x: int(
                        re.search(r'_v(\d+)\.csv', x).group(1)
                        if re.search(r'_v(\d+)\.csv', x) else 0
                    ),
                )
                st.session_state.latest_master_file = latest_master

                # 4. Generate Reports
                template_path    = os.path.join("src", "Resident_Report_Template.pptx")
                site_db_path     = os.path.join(
                    "data", "site_databases",
                    "XRF Site Analysis Database W SampleID(Sheet1).csv",
                )
                site_configs_path = os.path.join(
                    "data", "site_configs", "site_configs.json"
                )
                reports_dir  = os.path.join("data", "generated_reports")

                if os.path.exists(template_path):
                    report_count, report_list = generate_pptx_reports(
                        st.session_state.latest_master_file,
                        template_path, reports_dir,
                        site_db_path, site_configs_path,
                    )
                    st.session_state.reports_generated = report_count
                    st.session_state.generated_report_list = report_list
                else:
                    st.warning("⚠️ Template missing. Skipped report generation.")

                status.update(
                    label="Pipeline Execution Complete!", state="complete"
                )
                st.session_state.pipeline_success = True

            except Exception as e:
                status.update(label="Critical System Error", state="error")
                st.error(f"An unexpected error occurred: {str(e)}")
                st.session_state.pipeline_success = False

# ═══════════════════════════════════════════════
#  UI: RESULTS & EXPORT
# ═══════════════════════════════════════════════
if st.session_state.pipeline_success and st.session_state.latest_master_file:
    st.markdown("---")
    st.subheader("2. Deployment Artifacts")

    # KPIs
    df_result = pd.read_csv(st.session_state.latest_master_file)
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Total Records Processed", len(df_result))
    filled_ids = df_result[
        df_result['SampleID'].notna() & (df_result['SampleID'] != "")
    ] if 'SampleID' in df_result.columns else pd.DataFrame()
    kpi2.metric("Sites Evaluated", filled_ids['SampleID'].nunique() if len(filled_ids) else 0)
    kpi3.metric("Resident Reports Generated", st.session_state.reports_generated)

    st.write("")

    # Download Buttons
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.success("### 📊 Master Database")
        st.caption(
            f"File: `{os.path.basename(st.session_state.latest_master_file)}`"
        )
        with open(st.session_state.latest_master_file, "rb") as file:
            st.download_button(
                label="📥 Download Master Data (CSV)",
                data=file,
                file_name=os.path.basename(st.session_state.latest_master_file),
                mime="text/csv",
                use_container_width=True,
            )

    with col_dl2:
        st.info("### 🗂️ Generated Reports")
        report_list = st.session_state.get("generated_report_list", [])
        if report_list:
            st.caption(
                f"{len(report_list)} report(s) generated in this run."
            )
            for idx, (site_name, report_path) in enumerate(report_list):
                if os.path.exists(report_path):
                    with open(report_path, "rb") as rpt_file:
                        st.download_button(
                            label=f"📥 Download: {site_name}",
                            data=rpt_file,
                            file_name=os.path.basename(report_path),
                            mime="application/vnd.openxmlformats-officedocument"
                                 ".presentationml.presentation",
                            use_container_width=True,
                            key=f"dl_report_{idx}",
                        )
        else:
            st.caption("No reports were generated in this run.")
"""
dashboard.py — GroundSense Streamlit Dashboard (Launch Edition)
 
Public-facing dashboard for Urban Soil Co-Lab.
Config-driven geospatial maps for all sites.
 
Place in src/ alongside groundsense_config.py.
Place site_configs.json in data/site_configs/.
 
UPDATED: Honours `rotation_deg` stored in site_configs.json by routing
all coordinate conversions through calculate_coordinate_rotated().
"""
 
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import glob
import os
import re
import json
import folium
from streamlit_folium import st_folium
 
from groundsense_config import (
    get_nysh_category,
    NYSH_COLORS,
    NYSH_TIERS,
    calculate_coordinate,
    calculate_coordinate_rotated,
    resolve_lod,
)
 
 
# ═══════════════════════════════════════════════
#  PAGE SETUP & CUSTOM STYLING
# ═══════════════════════════════════════════════
st.set_page_config(
    page_title="GroundSense — Urban Soil Health",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)
 
st.markdown("""
<style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    .gs-header {
        background: linear-gradient(135deg, #1a472a 0%, #2d6a4f 50%, #40916c 100%);
        padding: 1.8rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
    }
    .gs-header h1 { margin: 0; font-size: 1.9rem; font-weight: 700; letter-spacing: -0.5px; }
    .gs-header p { margin: 0.3rem 0 0 0; font-size: 0.95rem; opacity: 0.85; }
    div[data-testid="stMetric"] {
        background: var(--background-color);
        border: 1px solid rgba(128, 128, 128, 0.15);
        border-radius: 10px;
        padding: 0.9rem 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    div[data-testid="stMetric"] label {
        font-size: 0.78rem !important; text-transform: uppercase;
        letter-spacing: 0.5px; opacity: 0.65;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-size: 1.6rem !important; font-weight: 600;
    }
    .gs-section {
        margin-top: 2rem; margin-bottom: 0.5rem;
        padding-bottom: 0.4rem;
        border-bottom: 2px solid rgba(45, 106, 79, 0.2);
    }
    .gs-section h3 { margin: 0; font-size: 1.15rem; font-weight: 600; color: #2d6a4f; }
    .gs-map-container {
        border: 1px solid rgba(128, 128, 128, 0.12);
        border-radius: 10px; overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .gs-footer {
        margin-top: 3rem; padding: 1.2rem 0;
        border-top: 1px solid rgba(128,128,128,0.15);
        text-align: center; font-size: 0.78rem; opacity: 0.5;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    section[data-testid="stSidebar"] > div { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)
 
 
st.markdown("""
<div class="gs-header">
    <h1>🌱 GroundSense</h1>
    <p>Urban Soil Health Dashboard — XRF Lead (Pb) Analysis & Monitoring</p>
</div>
""", unsafe_allow_html=True)
 
 
# ═══════════════════════════════════════════════
#  DATA LOADING
# ═══════════════════════════════════════════════
@st.cache_data
def load_chemistry_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, '..', 'data', 'xrf_data')
    files = glob.glob(os.path.join(data_dir, 'chemistry*.csv'))
    if not files:
        return pd.DataFrame()
 
    all_data = []
    for f in files:
        try:
            df = pd.read_csv(f)
            if 'Date' not in df.columns or 'Time' not in df.columns:
                continue
            df['DateTime'] = pd.to_datetime(
                df['Date'].astype(str) + ' ' + df['Time'].astype(str),
                errors='coerce'
            )
            all_data.append(df)
        except Exception:
            continue
 
    if not all_data:
        return pd.DataFrame()
 
    final_df = pd.concat(all_data, ignore_index=True)
    final_df = final_df.dropna(subset=['DateTime'])
 
    elements = {'Pb': 'Lead', 'Zn': 'Zinc', 'As': 'Arsenic', 'Fe': 'Iron'}
    for sym, name in elements.items():
        col = f"{sym} Concentration"
        if col in final_df.columns:
            final_df[name] = pd.to_numeric(final_df[col], errors='coerce')
 
    return final_df
 
 
def _load_sample_to_site_mapping():
    """Build SampleID -> SiteID mapping from the field CSV.

    Reads `data/site_databases/XRF_Site_Analysis_Database.csv` (written by
    field_entry.py) which is a plain single-header CSV with just
    SiteID + SampleID columns — no PII.

    Returns {} if the file is missing or malformed; the caller falls back
    to "Unknown Site".
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    field_path = os.path.join(
        base_dir, '..', 'data', 'site_databases',
        'XRF_Site_Analysis_Database.csv'
    )
    if not os.path.exists(field_path):
        return {}

    try:
        field_df = pd.read_csv(field_path, dtype=str)
    except Exception:
        return {}

    if "SiteID" not in field_df.columns or "SampleID" not in field_df.columns:
        return {}

    # SiteID may be filled only on the first row of each block in older
    # files — forward-fill so every SampleID inherits its block's SiteID.
    field_df = field_df.copy()
    field_df["SiteID"] = field_df["SiteID"].ffill()
    field_df = field_df.dropna(subset=["SampleID"])
    field_df = field_df[field_df["SampleID"].astype(str).str.strip() != ""]

    sample_to_site: dict[str, str] = {}
    for _, row in field_df.iterrows():
        sid = str(row.get("SiteID", "")).strip()
        sample = str(row.get("SampleID", "")).strip()
        if sample and sid:
            sample_to_site[sample] = sid
    return sample_to_site
 
 
@st.cache_data
def load_master_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    master_dir = os.path.join(base_dir, '..', 'data', 'master_data')
    master_files = glob.glob(os.path.join(master_dir, 'Master_Data_v*.csv'))
    if not master_files:
        return pd.DataFrame()
 
    def get_version(fn):
        m = re.search(r'_v(\d+)\.csv', fn)
        return int(m.group(1)) if m else 0
 
    latest = max(master_files, key=get_version)
    df = pd.read_csv(latest)
    df['LeadPPM_Clean'] = df['LeadPPM'].apply(resolve_lod)

    mapping = _load_sample_to_site_mapping()
    if mapping:
        df['Site_ID'] = df['SampleID'].map(mapping).fillna("Unknown Site")
    else:
        df['Site_ID'] = "Unknown Site"

    return df


@st.cache_data
def load_site_configs():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(
        base_dir, '..', 'data', 'site_configs', 'site_configs.json'
    )
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, 'r') as f:
            raw = json.load(f)
        return {site["site_id"]: site for site in raw}
    except Exception:
        return {}
 
 
# ═══════════════════════════════════════════════
#  MAP GENERATION ENGINE
# ═══════════════════════════════════════════════
 
def match_sample_to_master(patterns, master_df):
    for pattern in patterns:
        matches = master_df[
            master_df['SampleID'].str.contains(pattern, case=False, na=False)
        ]
        if not matches.empty:
            avg = matches['LeadPPM_Clean'].mean()
            if pd.notna(avg):
                return avg
    return None
 
 
def generate_site_map(site_config, master_df):
    """Generate a Folium satellite map honouring saved rotation_deg."""
    anchor = site_config["anchor"]
    defaults = site_config.get("map_defaults", {})
    rotation_deg = site_config.get("rotation_deg", 0) or 0
 
    # Use rotation-aware centre offset so the map re-frames correctly
    center_lat, center_lon = calculate_coordinate_rotated(
        anchor["lat"], anchor["lon"],
        defaults.get("center_offset_north_ft", 10),
        defaults.get("center_offset_east_ft", 0),
        rotation_deg,
    )
 
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=defaults.get("zoom_start", 20),
        max_zoom=25, tiles=None
    )
 
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/'
              'World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri', name='Esri Satellite',
        max_zoom=25, max_native_zoom=19,
        overlay=False, control=True
    ).add_to(m)
 
    folium.Marker(
        location=[anchor["lat"], anchor["lon"]],
        tooltip="<b>{}</b>".format(anchor.get('marker_label', 'Anchor Point')),
        icon=folium.Icon(color='red', icon='home')
    ).add_to(m)
 
    site_df = master_df[
        master_df['Site_ID'] == site_config['site_id']
    ].copy()
    if site_df.empty:
        site_df = master_df.copy()
 
    stats = {
        "total_blocks": 0, "real_data": 0, "mock_data": 0,
        "blocks": [], "max_ppm": 0, "min_ppm": float('inf')
    }
 
    # ── GRID BLOCKS ──
    grid = site_config.get("grid_blocks", {})
    for block_id, dims in grid.items():
        if block_id.startswith("_"):
            continue
 
        stats["total_blocks"] += 1
 
        # Build full polygon (4 corners) so rotation looks correct in Folium.
        # We can't use folium.Rectangle anymore because a rotated rectangle
        # isn't axis-aligned — we use folium.Polygon with rotated corners.
        corners_ft = [
            (dims["sw_x"], dims["sw_y"]),
            (dims["ne_x"], dims["sw_y"]),
            (dims["ne_x"], dims["ne_y"]),
            (dims["sw_x"], dims["ne_y"]),
        ]
        corner_latlon = [
            calculate_coordinate_rotated(
                anchor["lat"], anchor["lon"], cy, cx, rotation_deg
            )
            for cx, cy in corners_ft
        ]
 
        patterns = dims.get("sample_id_patterns", [])
        real_ppm = match_sample_to_master(patterns, site_df)
 
        if real_ppm is not None:
            ppm = real_ppm
            data_source = "XRF Data"
            stats["real_data"] += 1
        else:
            ppm = dims.get("mock_ppm", 0)
            data_source = "Estimated"
            stats["mock_data"] += 1
 
        stats["max_ppm"] = max(stats["max_ppm"], ppm)
        stats["min_ppm"] = min(stats["min_ppm"], ppm)
 
        label, color_hex = get_nysh_category(ppm)
        width_ft = abs(dims["ne_x"] - dims["sw_x"])
        height_ft = abs(dims["ne_y"] - dims["sw_y"])
 
        tooltip_html = """
        <div style='font-family: -apple-system, sans-serif; font-size: 13px;
                    line-height: 1.6; min-width: 160px;'>
            <b style='font-size: 15px;'>{block_id}</b><br>
            <span style='font-size: 1.4em; color: {color};'>●</span>
            <b>{ppm:.0f} ppm</b> — {label}<br>
            <span style='opacity: 0.7;'>{w:.0f} × {h:.0f} ft · {src}</span>
        </div>
        """.format(
            block_id=block_id, color=color_hex, ppm=ppm,
            label=label, w=width_ft, h=height_ft, src=data_source
        )
 
        folium.Polygon(
            locations=corner_latlon,
            color='white', weight=2,
            fill=True, fill_color=color_hex, fill_opacity=0.75,
            tooltip=tooltip_html
        ).add_to(m)
 
        stats["blocks"].append({
            "id": block_id, "ppm": ppm, "label": label,
            "source": data_source, "zone": dims.get("zone", "")
        })
 
    # ── POINT SAMPLES ──
    points = site_config.get("point_samples", {})
    for pt_id, pt in points.items():
        if pt_id.startswith("_"):
            continue
 
        ox = pt.get("offset_x")
        oy = pt.get("offset_y")
        if ox is None or oy is None:
            continue
 
        pt_lat, pt_lon = calculate_coordinate_rotated(
            anchor["lat"], anchor["lon"], oy, ox, rotation_deg
        )
 
        patterns = pt.get("sample_id_patterns", [])
        real_ppm = match_sample_to_master(patterns, site_df)
 
        if real_ppm is not None:
            ppm = real_ppm
            data_source = "XRF Data"
            stats["real_data"] += 1
            label, color_hex = get_nysh_category(ppm)
            ppm_str = "{:.0f} ppm".format(ppm)
        else:
            ppm = None
            data_source = "No Data"
            label, color_hex = "Unknown", "#808080"
            ppm_str = "Pending"
 
        stats["total_blocks"] += 1
        stats["blocks"].append({
            "id": pt_id, "ppm": ppm or 0, "label": label,
            "source": data_source, "zone": pt.get("zone", "")
        })
 
        tooltip_html = """
        <div style='font-family: -apple-system, sans-serif; font-size: 13px;
                    line-height: 1.6; min-width: 140px;'>
            <b style='font-size: 15px;'>{pt_id}</b><br>
            <span style='font-size: 1.4em; color: {color};'>●</span>
            <b>{ppm_str}</b> — {label}<br>
            <span style='opacity: 0.7;'>Point sample · {src}</span>
        </div>
        """.format(
            pt_id=pt_id, color=color_hex, ppm_str=ppm_str,
            label=label, src=data_source
        )
 
        folium.CircleMarker(
            location=[pt_lat, pt_lon],
            radius=8, color='white', weight=2,
            fill=True, fill_color=color_hex, fill_opacity=0.85,
            tooltip=tooltip_html
        ).add_to(m)
 
    # ── LEGEND ──
    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
                background: rgba(20,24,32,0.92); padding: 16px 20px;
                border-radius: 12px; font-family: -apple-system, sans-serif;
                font-size: 12px; color: #e8eaed;
                box-shadow: 0 4px 24px rgba(0,0,0,0.4);
                border: 1px solid rgba(255,255,255,0.08);
                backdrop-filter: blur(8px);">
        <b style="font-size: 13px; letter-spacing: 0.3px;">
            NYSH Lead Guidelines
        </b><br>
        <div style="margin-top: 6px;">
    """
    for tier in NYSH_TIERS:
        legend_html += """
        <div style="margin: 3px 0;">
            <span style="display: inline-block; width: 12px; height: 12px;
                          background: {}; border-radius: 3px;
                          margin-right: 8px; vertical-align: middle;"></span>
            {}
        </div>
        """.format(tier['color'], tier['label'])
    legend_html += """
        <div style="margin: 3px 0;">
            <span style="display: inline-block; width: 12px; height: 12px;
                          background: #808080; border-radius: 3px;
                          margin-right: 8px; vertical-align: middle;"></span>
            No Data
        </div>
        </div>
        <hr style="border-color: rgba(255,255,255,0.1); margin: 8px 0 6px;">
        <span style="font-size: 11px; opacity: 0.7;">
            ■ Grid block &nbsp; ● Point sample
        </span>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
 
    # Stash rotation in stats for diagnostic display
    stats["rotation_deg"] = rotation_deg
 
    return m, stats
 
 
# ═══════════════════════════════════════════════
#  LOAD ALL DATA
# ═══════════════════════════════════════════════
chem_df = load_chemistry_data()
master_df = load_master_data()
site_configs = load_site_configs()
 
if chem_df.empty:
    st.error(
        "**No XRF data found.** Please ensure chemistry CSV files "
        "are in the `data/xrf_data/` directory."
    )
    st.stop()
 
 
# ═══════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════
with st.sidebar:
    st.markdown("### ⚙️ Filters")
    st.caption("Adjust parameters for the analytics below.")
 
    min_date = chem_df['DateTime'].min().date()
    max_date = chem_df['DateTime'].max().date()
 
    date_range = st.date_input(
        "Date Range",
        value=[min_date, max_date],
        min_value=min_date,
        max_value=max_date,
    )
 
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = date_range[0] if isinstance(date_range, (list, tuple)) else date_range
        end_date = max_date
 
    nysh_limit = st.number_input(
        "NYSH Hazard Threshold (ppm)",
        value=400, step=50,
        help="Readings above this level are classified as 'Hazard' "
             "per New York Soil Health guidelines."
    )
 
    st.markdown("---")
    st.markdown("### 📋 About")
    st.caption(
        "**GroundSense** is a project by the Urban Soil Co-Lab at the "
        "University at Buffalo. We use portable XRF technology to map "
        "lead contamination in residential soils across Buffalo, NY."
    )
 
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
 
 
mask = (
    (chem_df['DateTime'].dt.date >= start_date) &
    (chem_df['DateTime'].dt.date <= end_date)
)
filtered_chem_df = chem_df.loc[mask]
 
if filtered_chem_df.empty:
    st.warning("No readings in the selected date range.")
    st.stop()
 
 
# ═══════════════════════════════════════════════
#  KEY METRICS ROW
# ═══════════════════════════════════════════════
if 'Lead' in filtered_chem_df.columns:
    lead_data = filtered_chem_df['Lead'].dropna()
    avg_lead = lead_data.mean()
    max_lead = lead_data.max()
    total_readings = len(lead_data)
    high_risk = (lead_data > nysh_limit).sum()
    pct_below = ((lead_data <= nysh_limit).sum() / total_readings * 100) if total_readings > 0 else 100
 
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Avg Lead (Pb)", "{:.0f} ppm".format(avg_lead))
    col2.metric("Peak Detected", "{:.0f} ppm".format(max_lead))
    col3.metric("Total Readings", "{:,}".format(total_readings))
    col4.metric(
        "Below NYSH Hazard",
        "{:.1f}%".format(pct_below),
        help="Percentage of readings below {} ppm (NYSH Hazard threshold)".format(nysh_limit)
    )
else:
    st.warning("Lead concentration data not found in chemistry files.")
 
 
# ═══════════════════════════════════════════════
#  GEOSPATIAL MAPS
# ═══════════════════════════════════════════════
st.markdown(
    '<div class="gs-section"><h3>🗺️ Site Maps — Lead Contamination by Grid Block</h3></div>',
    unsafe_allow_html=True
)
 
if not master_df.empty and site_configs:
    configured_site_ids = list(site_configs.keys())
    master_site_ids = sorted(master_df['Site_ID'].unique().tolist())
    all_site_ids = configured_site_ids + [
        s for s in master_site_ids
        if s not in configured_site_ids and s != "Unknown Site"
    ]

    selected_site = st.selectbox(
        "Select site",
        all_site_ids,
        label_visibility="collapsed",
        help="Choose a site to view its lead contamination map on satellite imagery."
    )

    if selected_site in site_configs:
        config = site_configs[selected_site]

        info1, info2, info3 = st.columns(3)
        info1.markdown(
            "**🆔 SiteID:** {}".format(config['site_id'])
        )
        info2.markdown(
            "**📅 Sampled:** {}".format(
                config.get('sampling_date', 'Unknown')
            )
        )
        grid_count = len([
            k for k in config.get('grid_blocks', {})
            if not k.startswith('_')
        ])
        point_count = len([
            k for k in config.get('point_samples', {})
            if not k.startswith('_')
        ])
        info3.markdown(
            "**📐 Zones:** {} grid blocks, {} point samples".format(
                grid_count, point_count
            )
        )
 
        if config.get("notes"):
            st.caption("📝 {}".format(config["notes"]))
 
        rot = config.get("rotation_deg", 0) or 0
        if rot:
            st.caption(f"🧭 Grid rotation applied: **{rot:+.1f}°** (set in Site Builder)")
 
        with st.spinner("Rendering satellite map..."):
            site_map, stats = generate_site_map(config, master_df)
 
        st.markdown('<div class="gs-map-container">', unsafe_allow_html=True)
        st_folium(site_map, width=None, height=600, returned_objects=[])
        st.markdown('</div>', unsafe_allow_html=True)
 
        st.markdown("")
        scol1, scol2, scol3, scol4 = st.columns(4)
        scol1.metric("Zones Mapped", stats["total_blocks"])
        scol2.metric(
            "XRF Data",
            stats["real_data"],
            help="Zones with real lab-measured XRF readings"
        )
        scol3.metric(
            "Estimated",
            stats["mock_data"],
            help="Zones using placeholder values — awaiting XRF analysis"
        )
        if stats["real_data"] > 0 and stats["max_ppm"] > 0:
            scol4.metric(
                "Range",
                "{:.0f}–{:.0f} ppm".format(
                    stats["min_ppm"], stats["max_ppm"]
                )
            )
 
        if stats["blocks"]:
            block_df = pd.DataFrame(stats["blocks"])
            cat_counts = block_df['label'].value_counts()
 
            st.markdown("**NYSH Category Breakdown:**")
            cat_cols = st.columns(len(NYSH_TIERS))
            for i, tier in enumerate(NYSH_TIERS):
                count = cat_counts.get(tier["label"], 0)
                cat_cols[i].markdown(
                    "<div style='text-align:center; padding: 0.5rem 0;'>"
                    "<span style='color:{}; font-size: 1.8rem; "
                    "font-weight: 700;'>{}</span><br>"
                    "<span style='font-size: 0.7rem; opacity: 0.6;'>"
                    "{}</span></div>".format(
                        tier['color'], count,
                        tier['label'].split('(')[0].strip()
                    ),
                    unsafe_allow_html=True
                )
 
    else:
        st.info(
            "**No grid configuration for '{}'.**  \n"
            "Use the Site Builder tool to create a grid layout for this "
            "site, then it will appear here automatically.".format(
                selected_site
            )
        )
 
elif not site_configs:
    st.warning(
        "**Site configuration file not found.**  \n"
        "Place `site_configs.json` in `data/site_configs/` to enable "
        "satellite mapping."
    )
else:
    st.info(
        "**No processed data available.**  \n"
        "Run the ETL Pipeline to generate Master Data and enable maps."
    )
 
 
# ═══════════════════════════════════════════════
#  LEAD DISTRIBUTION
# ═══════════════════════════════════════════════
st.markdown(
    '<div class="gs-section"><h3>📊 Lead Distribution</h3></div>',
    unsafe_allow_html=True
)
 
if 'Lead' in filtered_chem_df.columns:
    fig_hist = go.Figure()
 
    fig_hist.add_trace(go.Histogram(
        x=filtered_chem_df['Lead'].dropna(),
        nbinsx=25,
        marker_color='#2d6a4f',
        marker_line_color='#1a472a',
        marker_line_width=0.5,
        opacity=0.85,
        hovertemplate="<b>%{x:.0f} ppm</b><br>Count: %{y}<extra></extra>",
    ))
 
    thresholds = [
        (63, "NYSH Elevated", "#f1c40f"),
        (100, "NYSH Contaminated", "#e67e22"),
        (200, "NYSH High", "#e74c3c"),
        (400, "NYSH Hazard", "#800000"),
    ]
    for val, name, color in thresholds:
        fig_hist.add_vline(
            x=val, line_dash="dot", line_color=color, line_width=1.5,
            annotation_text=name, annotation_font_size=10,
            annotation_font_color=color,
        )
 
    fig_hist.update_layout(
        title=None,
        xaxis_title="Lead Concentration (ppm)",
        yaxis_title="Number of Readings",
        template="plotly_white",
        height=380,
        margin=dict(t=30, b=60, l=60, r=30),
        bargap=0.05,
        font=dict(family="-apple-system, BlinkMacSystemFont, sans-serif"),
    )
 
    st.plotly_chart(fig_hist, use_container_width=True)
 
 
# ═══════════════════════════════════════════════
#  MULTI-ELEMENT CORRELATION
# ═══════════════════════════════════════════════
st.markdown(
    '<div class="gs-section">'
    '<h3>🔬 Multi-Element Soil Fingerprint</h3>'
    '</div>',
    unsafe_allow_html=True
)
 
if 'Zinc' in filtered_chem_df.columns and 'Arsenic' in filtered_chem_df.columns:
    plot_df = filtered_chem_df.copy()
    plot_df['Arsenic'] = plot_df['Arsenic'].fillna(1)
    if 'Iron' in plot_df.columns:
        plot_df['Iron'] = plot_df['Iron'].fillna(0)
 
    fig_corr = px.scatter(
        plot_df, x="Zinc", y="Lead",
        size="Arsenic", color="Iron",
        hover_data=['DateTime', 'Lead', 'Zinc', 'Arsenic'],
        color_continuous_scale="Viridis",
    )
 
    fig_corr.update_layout(
        title=None,
        xaxis_title="Zinc (ppm)",
        yaxis_title="Lead (ppm)",
        template="plotly_white",
        height=420,
        margin=dict(t=30, b=60, l=60, r=30),
        font=dict(family="-apple-system, BlinkMacSystemFont, sans-serif"),
        coloraxis_colorbar_title="Iron (ppm)",
    )
 
    st.plotly_chart(fig_corr, use_container_width=True)
 
    st.caption(
        "Each point represents one XRF reading. Point size indicates "
        "arsenic concentration. Color intensity shows iron levels. "
        "Strong Lead-Zinc correlation suggests shared contamination source "
        "(e.g. leaded paint or industrial fallout)."
    )
else:
    st.info(
        "Zinc and/or Arsenic data not available in the current dataset "
        "for correlation analysis."
    )
 
 
# ═══════════════════════════════════════════════
#  FOOTER
# ═══════════════════════════════════════════════
st.markdown(
    '<div class="gs-footer">'
    'GroundSense · Urban Soil Co-Lab · University at Buffalo<br>'
    'Data sourced from portable XRF analysis (Instrument #824222)'
    '</div>',
    unsafe_allow_html=True
)
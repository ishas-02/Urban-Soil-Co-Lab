# import streamlit as st
# import pandas as pd
# import plotly.express as px
# import plotly.graph_objects as go
# import glob
# import os

# # --- PAGE CONFIGURATION ---
# st.set_page_config(page_title="GroundSense Dashboard", page_icon="🌱", layout="wide")

# # --- TITLE & HEADER ---
# st.title("🌱 Urban Soil Health Dashboard")
# st.markdown("### Preliminary XRF Analysis & Lead (Pb) Monitoring")
# st.markdown("---")

# # --- DATA LOADING FUNCTION ---
# # @st.cache_data
# # def load_data():
# #     # 1. Find all chemistry files INSIDE the 'xrf_data' folder
# #     # We use os.path.join to ensure it works on both Windows and Mac
# #     search_path = os.path.join('xrf_data', 'chemistry*.csv')
# #     files = glob.glob(search_path)
    
# #     if not files:
# #         return pd.DataFrame()
    
# #     all_data = []
# #     for f in files:
# #         df = pd.read_csv(f)
# #         # Create a clean Timestamp
# #         df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
# #         all_data.append(df)
        
# #     final_df = pd.concat(all_data, ignore_index=True)

# # --- DATA LOADING FUNCTION ---
# @st.cache_data
# def load_data():
#     # 1. Get the absolute path of the 'src' directory where dashboard.py lives
#     base_dir = os.path.dirname(os.path.abspath(__file__))
    
#     # 2. Navigate up to the root, then into Data/xrf_data (Capital 'D' to match your folder!)
#     data_dir = os.path.join(base_dir, '..', 'data', 'xrf_data')
    
#     # 3. Create the search path
#     search_path = os.path.join(data_dir, 'chemistry*.csv')
#     files = glob.glob(search_path)
    
#     if not files:
#         # Prints to your terminal so we can see exactly where it searched if it fails
#         print(f"DEBUG: Looked for files in: {search_path}") 
#         return pd.DataFrame()
    
#     all_data = []
#     for f in files:
#         df = pd.read_csv(f)
#         # Create a clean Timestamp
#         df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
#         all_data.append(df)
        
#     final_df = pd.concat(all_data, ignore_index=True)
    
#     # Clean & Rename Key Columns
#     elements = {'Pb': 'Lead', 'Zn': 'Zinc', 'As': 'Arsenic', 'Fe': 'Iron'}
#     for sym, name in elements.items():
#         col_name = f"{sym} Concentration"
#         if col_name in final_df.columns:
#             final_df[name] = pd.to_numeric(final_df[col_name], errors='coerce')
    
#     return final_df
    
#     # 2. Clean & Rename Key Columns
#     # Ensure numeric conversion for key elements
#     elements = {'Pb': 'Lead', 'Zn': 'Zinc', 'As': 'Arsenic', 'Fe': 'Iron'}
#     for sym, name in elements.items():
#         col_name = f"{sym} Concentration"
#         if col_name in final_df.columns:
#             # Force numeric, turning '<LOD' into NaN (or 0 if you prefer)
#             final_df[name] = pd.to_numeric(final_df[col_name], errors='coerce')
    
#     return final_df

# # --- LOAD DATA ---
# df = load_data()

# if df.empty:
#     st.error("No data found! Please ensure your chemistry files are inside the 'xrf_data' folder.")
#     st.stop()

# # --- SIDEBAR FILTERS ---
# st.sidebar.header("Filter Options")
# date_range = st.sidebar.date_input("Select Date Range", [df['DateTime'].min(), df['DateTime'].max()])
# epa_limit = st.sidebar.number_input("EPA Safety Limit (ppm)", value=400, step=50)

# # Filter data based on selection
# mask = (df['DateTime'].dt.date >= date_range[0]) & (df['DateTime'].dt.date <= date_range[1])
# filtered_df = df.loc[mask]

# # --- KEY METRICS ROW ---
# col1, col2, col3, col4 = st.columns(4)

# avg_lead = filtered_df['Lead'].mean()
# max_lead = filtered_df['Lead'].max()
# high_risk_count = filtered_df[filtered_df['Lead'] > epa_limit].shape[0]
# percent_safe = 100 - (high_risk_count / len(filtered_df) * 100) if len(filtered_df) > 0 else 100

# # NEW METRIC: Calculate total sites/readings examined
# sites_examined = len(filtered_df)

# col1.metric("Avg Lead Level", f"{avg_lead:.1f} ppm", delta_color="inverse")
# col2.metric("Max Detected", f"{max_lead:.0f} ppm", delta="-High" if max_lead > epa_limit else "normal")
# col3.metric("Sites Examined", f"{sites_examined}")
# col4.metric("Safety Rate", f"{percent_safe:.1f}%")

# st.markdown("---")

# # --- VISUALIZATIONS ---

# # ROW 1: Distribution 
# st.subheader("📊 Lead Distribution Histogram")
# fig_hist = px.histogram(filtered_df, x="Lead", nbins=20, title="Frequency of Lead Concentrations",
#                         color_discrete_sequence=['#2E8B57'])
# fig_hist.add_vline(x=epa_limit, line_dash="dash", line_color="red", annotation_text="EPA Limit")
# # Displaying the chart in full width now since the other chart is removed
# st.plotly_chart(fig_hist, use_container_width=True)

# st.markdown("---")

# # ROW 2: Advanced Correlations (The "Creative" Part)
# st.subheader("🔬 Multi-Element Soil Fingerprint")
# st.markdown("Lead contamination often co-occurs with other heavy metals. This chart explores those relationships.")

# # Check if we have Zinc and Arsenic data
# if 'Zinc' in filtered_df.columns and 'Arsenic' in filtered_df.columns:
#     # --- FIX START: Handle Missing Values for Plotting ---
#     # Create a copy so we don't mess up the original data
#     plot_df = filtered_df.copy()
    
#     # Fill missing Arsenic values with 0 so the code doesn't crash
#     # (Visually, this means points with no Arsenic data will be very small dots)
#     plot_df['Arsenic'] = plot_df['Arsenic'].fillna(1) 
    
#     # Also fill Iron just in case
#     if 'Iron' in plot_df.columns:
#         plot_df['Iron'] = plot_df['Iron'].fillna(0)
#     # --- FIX END ---

#     fig_corr = px.scatter(plot_df, x="Zinc", y="Lead", 
#                           size="Arsenic", color="Iron",
#                           # Update hover data to use the filled dataframe
#                           hover_data=['DateTime', 'Lead', 'Zinc', 'Arsenic'],
#                           title="Lead vs. Zinc Correlation (Sized by Arsenic, Colored by Iron)",
#                           color_continuous_scale="Viridis")
#     st.plotly_chart(fig_corr, use_container_width=True)
# else:
#     st.info("Zinc or Arsenic data missing from current dataset.")

# import streamlit as st
# import pandas as pd
# import plotly.express as px
# import plotly.graph_objects as go
# import glob
# import os

# # --- PAGE CONFIGURATION ---
# st.set_page_config(page_title="GroundSense Dashboard", page_icon="🌱", layout="wide")

# # --- TITLE, HEADER & REFRESH BUTTON ---
# # We use columns to put the title on the left and a refresh button on the right
# col_title, col_btn = st.columns([8, 2])
# with col_title:
#     st.title("🌱 Urban Soil Health Dashboard")
#     st.markdown("### Preliminary XRF Analysis & Lead (Pb) Monitoring")

# with col_btn:
#     # This button forces Streamlit to clear its memory and pull fresh data from the folder
#     st.write("") # Spacing to align with title
#     if st.button("🔄 Refresh Data", type="primary", use_container_width=True):
#         st.cache_data.clear()
#         st.rerun()

# st.markdown("---")

# # --- DATA LOADING FUNCTION ---
# @st.cache_data
# def load_data():
#     # 1. Get the absolute path of the 'src' directory where dashboard.py lives
#     base_dir = os.path.dirname(os.path.abspath(__file__))
    
#     # 2. Navigate up to the root, then into Data/xrf_data (Capital 'D')
#     data_dir = os.path.join(base_dir, '..', 'Data', 'xrf_data')
    
#     # 3. Create the search path
#     search_path = os.path.join(data_dir, 'chemistry*.csv')
#     files = glob.glob(search_path)
    
#     if not files:
#         print(f"DEBUG: Looked for files in: {search_path}") 
#         return pd.DataFrame()
    
#     all_data = []
#     for f in files:
#         df = pd.read_csv(f)
#         # Create a clean Timestamp
#         df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
#         all_data.append(df)
        
#     final_df = pd.concat(all_data, ignore_index=True)
    
#     # 4. Clean & Rename Key Columns
#     elements = {'Pb': 'Lead', 'Zn': 'Zinc', 'As': 'Arsenic', 'Fe': 'Iron'}
#     for sym, name in elements.items():
#         col_name = f"{sym} Concentration"
#         if col_name in final_df.columns:
#             # Force numeric, turning '<LOD' into NaN
#             final_df[name] = pd.to_numeric(final_df[col_name], errors='coerce')
    
#     return final_df

# # --- LOAD DATA ---
# df = load_data()

# if df.empty:
#     st.error("No data found! Please ensure your chemistry files are inside the 'Data/xrf_data' folder.")
#     st.stop()

# # --- SIDEBAR FILTERS ---
# st.sidebar.header("Filter Options")
# date_range = st.sidebar.date_input("Select Date Range", [df['DateTime'].min(), df['DateTime'].max()])
# epa_limit = st.sidebar.number_input("EPA Safety Limit (ppm)", value=400, step=50)

# # Filter data based on selection
# mask = (df['DateTime'].dt.date >= date_range[0]) & (df['DateTime'].dt.date <= date_range[1])
# filtered_df = df.loc[mask]

# # --- KEY METRICS ROW ---
# col1, col2, col3, col4 = st.columns(4)

# avg_lead = filtered_df['Lead'].mean()
# max_lead = filtered_df['Lead'].max()
# high_risk_count = filtered_df[filtered_df['Lead'] > epa_limit].shape[0]
# percent_safe = 100 - (high_risk_count / len(filtered_df) * 100) if len(filtered_df) > 0 else 100

# sites_examined = len(filtered_df)

# col1.metric("Avg Lead Level", f"{avg_lead:.1f} ppm", delta_color="inverse")
# col2.metric("Max Detected", f"{max_lead:.0f} ppm", delta="-High" if max_lead > epa_limit else "normal")
# col3.metric("Sites Examined", f"{sites_examined}")
# col4.metric("Safety Rate", f"{percent_safe:.1f}%")

# st.markdown("---")

# # --- VISUALIZATIONS ---

# # ROW 1: Distribution 
# st.subheader("📊 Lead Distribution Histogram")
# fig_hist = px.histogram(filtered_df, x="Lead", nbins=20, title="Frequency of Lead Concentrations",
#                         color_discrete_sequence=['#2E8B57'])
# fig_hist.add_vline(x=epa_limit, line_dash="dash", line_color="red", annotation_text="EPA Limit")
# st.plotly_chart(fig_hist, use_container_width=True)

# st.markdown("---")

# # ROW 2: Advanced Correlations 
# st.subheader("🔬 Multi-Element Soil Fingerprint")
# st.markdown("Lead contamination often co-occurs with other heavy metals. This chart explores those relationships.")

# # Check if we have Zinc and Arsenic data
# if 'Zinc' in filtered_df.columns and 'Arsenic' in filtered_df.columns:
#     plot_df = filtered_df.copy()
    
#     # Handle Missing Values for Plotting
#     plot_df['Arsenic'] = plot_df['Arsenic'].fillna(1) 
#     if 'Iron' in plot_df.columns:
#         plot_df['Iron'] = plot_df['Iron'].fillna(0)

#     fig_corr = px.scatter(plot_df, x="Zinc", y="Lead", 
#                           size="Arsenic", color="Iron",
#                           hover_data=['DateTime', 'Lead', 'Zinc', 'Arsenic'],
#                           title="Lead vs. Zinc Correlation (Sized by Arsenic, Colored by Iron)",
#                           color_continuous_scale="Viridis")
#     st.plotly_chart(fig_corr, use_container_width=True)
# else:
#     st.info("Zinc or Arsenic data missing from current dataset.")

# import streamlit as st
# import pandas as pd
# import plotly.express as px
# import plotly.graph_objects as go
# import glob
# import os
# import re

# # --- PAGE CONFIGURATION ---
# st.set_page_config(page_title="GroundSense Dashboard", page_icon="🌱", layout="wide")

# # --- TITLE, HEADER & REFRESH BUTTON ---
# col_title, col_btn = st.columns([8, 2])
# with col_title:
#     st.title("🌱 Urban Soil Health Dashboard")
#     st.markdown("### Preliminary XRF Analysis & Lead (Pb) Monitoring")

# with col_btn:
#     st.write("") 
#     if st.button("🔄 Refresh Data", type="primary", use_container_width=True):
#         st.cache_data.clear()
#         st.rerun()

# st.markdown("---")

# # --- NYSH COLOR MAPPING FUNCTION ---
# def get_nysh_category(ppm):
#     if pd.isna(ppm): return 'Unknown'
#     if ppm < 63: return 'Safe (< 63 ppm)'
#     elif ppm < 100: return 'Elevated (63-99 ppm)'
#     elif ppm < 200: return 'Contaminated (100-199 ppm)'
#     elif ppm < 400: return 'High (200-399 ppm)'
#     else: return 'Hazard (400+ ppm)'

# nysh_colors = {
#     'Safe (< 63 ppm)': '#2ecc71',
#     'Elevated (63-99 ppm)': '#f1c40f',
#     'Contaminated (100-199 ppm)': '#e67e22',
#     'High (200-399 ppm)': '#e74c3c',
#     'Hazard (400+ ppm)': '#8e44ad',
#     'Unknown': '#808080'
# }

# # --- DATA LOADING FUNCTIONS ---
# @st.cache_data
# def load_chemistry_data():
#     """Loads raw chemistry files for overall metrics and correlations."""
#     base_dir = os.path.dirname(os.path.abspath(__file__))
#     data_dir = os.path.join(base_dir, '..', 'Data', 'xrf_data')
#     search_path = os.path.join(data_dir, 'chemistry*.csv')
#     files = glob.glob(search_path)
    
#     if not files:
#         return pd.DataFrame()
    
#     all_data = []
#     for f in files:
#         df = pd.read_csv(f)
#         df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
#         all_data.append(df)
        
#     final_df = pd.concat(all_data, ignore_index=True)
    
#     # Clean & Rename Key Columns
#     elements = {'Pb': 'Lead', 'Zn': 'Zinc', 'As': 'Arsenic', 'Fe': 'Iron'}
#     for sym, name in elements.items():
#         col_name = f"{sym} Concentration"
#         if col_name in final_df.columns:
#             final_df[name] = pd.to_numeric(final_df[col_name], errors='coerce')
            
#     return final_df

# @st.cache_data
# def load_master_data():
#     """Loads the latest Master Data file to get mapped SampleIDs and Addresses."""
#     base_dir = os.path.dirname(os.path.abspath(__file__))
#     master_dir = os.path.join(base_dir, '..', 'Data', 'master_data')
#     master_files = glob.glob(os.path.join(master_dir, 'Master_Data_v*.csv'))
    
#     if not master_files:
#         return pd.DataFrame()
        
#     def get_version(filename):
#         match = re.search(r'_v(\d+)\.csv', filename)
#         return int(match.group(1)) if match else 0
        
#     latest_file = max(master_files, key=get_version)
#     df = pd.read_csv(latest_file)
    
#     # MAP ADDRESSES FROM SITE DATABASE
#     site_db_path = os.path.join(base_dir, '..', 'Data', 'site_databases', 'XRF Site Analysis Database W SampleID(Sheet1).csv')
#     if os.path.exists(site_db_path):
#         site_db = pd.read_csv(site_db_path, header=1, encoding='latin1')
#         site_db['Address'] = site_db['Address'].ffill()
#         site_mapping = dict(zip(site_db['SampleID'].dropna(), site_db['Address'].dropna()))
#         df['Site_Address'] = df['SampleID'].map(site_mapping).fillna("Unknown Address")
#     else:
#         df['Site_Address'] = "Unknown Address"
        
#     return df

# # --- LOAD DATA ---
# chem_df = load_chemistry_data()
# master_df = load_master_data()

# if chem_df.empty:
#     st.error("No data found! Please ensure your chemistry files are inside the 'Data/xrf_data' folder.")
#     st.stop()

# # --- SIDEBAR FILTERS ---
# st.sidebar.header("Filter Options")
# date_range = st.sidebar.date_input("Select Date Range", [chem_df['DateTime'].min(), chem_df['DateTime'].max()])
# epa_limit = st.sidebar.number_input("EPA Safety Limit (ppm)", value=400, step=50)

# mask = (chem_df['DateTime'].dt.date >= date_range[0]) & (chem_df['DateTime'].dt.date <= date_range[1])
# filtered_chem_df = chem_df.loc[mask]

# # --- KEY METRICS ROW ---
# col1, col2, col3, col4 = st.columns(4)
# avg_lead = filtered_chem_df['Lead'].mean()
# max_lead = filtered_chem_df['Lead'].max()
# high_risk_count = filtered_chem_df[filtered_chem_df['Lead'] > epa_limit].shape[0]
# percent_safe = 100 - (high_risk_count / len(filtered_chem_df) * 100) if len(filtered_chem_df) > 0 else 100

# col1.metric("Avg Lead Level", f"{avg_lead:.1f} ppm", delta_color="inverse")
# col2.metric("Max Detected", f"{max_lead:.0f} ppm", delta="-High" if max_lead > epa_limit else "normal")
# col3.metric("Total Readings", f"{len(filtered_chem_df)}")
# col4.metric("Safety Rate", f"{percent_safe:.1f}%")

# st.markdown("---")

# # --- VISUALIZATIONS ---

# # ROW 1: NYSH CONCEPTUAL GRID HEATMAP
# st.subheader("🟩 Conceptual Site Heatmap (NYSH Guidelines)")
# st.markdown("Select a site address to view the lead concentration breakdown by specific sample regions (e.g., A1, B2).")

# if not master_df.empty and 'Site_Address' in master_df.columns:
#     # Get list of unique sites, filter out "Unknown" if possible, and create a dropdown
#     site_list = sorted(master_df['Site_Address'].unique().tolist())
#     selected_site = st.selectbox("Select Site:", site_list)

#     # Filter data for just the selected site
#     site_df = master_df[master_df['Site_Address'] == selected_site].copy()

#     if not site_df.empty and 'SampleID' in site_df.columns:
#         # Ensure Lead is numeric
#         site_df['Lead'] = pd.to_numeric(site_df['LeadPPM'], errors='coerce')
        
#         # Group by SampleID to get the average lead for each sector of the yard
#         grid_df = site_df.groupby('SampleID')['Lead'].mean().reset_index()
        
#         # Apply NYSH levels and a dummy 'Size' column so the blocks are drawn evenly
#         grid_df['NYSH_Level'] = grid_df['Lead'].apply(get_nysh_category)
#         grid_df['Block_Size'] = 1 
        
#         # Create the Treemap
#         fig_grid = px.treemap(
#             grid_df, 
#             path=['SampleID'], 
#             values='Block_Size',
#             color='NYSH_Level',
#             color_discrete_map=nysh_colors,
#             custom_data=['Lead']
#         )
        
#         # Format the text inside the blocks
#         fig_grid.update_traces(
#             hovertemplate="<b>Sample Sector:</b> %{label}<br><b>Avg Lead:</b> %{customdata[0]:.1f} ppm<extra></extra>",
#             textinfo="label",
#             textfont_size=18
#         )
#         fig_grid.update_layout(margin=dict(t=10, l=10, r=10, b=10))
#         st.plotly_chart(fig_grid, use_container_width=True)
#     else:
#         st.info("No valid Sample ID data available for this site.")
# else:
#     st.info("Please process data through the ETL Pipeline to generate Site Heatmaps.")

# st.markdown("---")

# # ROW 2: Distribution 
# st.subheader("📊 Lead Distribution Histogram")
# fig_hist = px.histogram(filtered_chem_df, x="Lead", nbins=20, title="Frequency of Lead Concentrations",
#                         color_discrete_sequence=['#2E8B57'])
# fig_hist.add_vline(x=epa_limit, line_dash="dash", line_color="red", annotation_text="EPA Limit")
# st.plotly_chart(fig_hist, use_container_width=True)

# st.markdown("---")

# # ROW 3: Advanced Correlations 
# st.subheader("🔬 Multi-Element Soil Fingerprint")
# if 'Zinc' in filtered_chem_df.columns and 'Arsenic' in filtered_chem_df.columns:
#     plot_df = filtered_chem_df.copy()
#     plot_df['Arsenic'] = plot_df['Arsenic'].fillna(1) 
#     if 'Iron' in plot_df.columns:
#         plot_df['Iron'] = plot_df['Iron'].fillna(0)

#     fig_corr = px.scatter(plot_df, x="Zinc", y="Lead", 
#                           size="Arsenic", color="Iron",
#                           hover_data=['DateTime', 'Lead', 'Zinc', 'Arsenic'],
#                           title="Lead vs. Zinc Correlation (Sized by Arsenic, Colored by Iron)",
#                           color_continuous_scale="Viridis")
#     st.plotly_chart(fig_corr, use_container_width=True)
# else:
#     st.info("Zinc or Arsenic data missing from current dataset.")

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import glob
import os
import re
import math
import folium
from streamlit_folium import st_folium

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="GroundSense Dashboard", page_icon="🌱", layout="wide")

# --- TITLE, HEADER & REFRESH BUTTON ---
col_title, col_btn = st.columns([8, 2])
with col_title:
    st.title("🌱 Urban Soil Health Dashboard")
    st.markdown("### Preliminary XRF Analysis & Lead (Pb) Monitoring")

with col_btn:
    st.write("") 
    if st.button("🔄 Refresh Data", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# --- 1. NYSH COLOR MAPPING FUNCTION ---
def get_nysh_category(ppm):
    # Action levels based on NYSH guidance 
    if pd.isna(ppm): return 'Unknown'
    if ppm < 63: return 'Safe (< 63 ppm)' 
    elif ppm < 100: return 'Elevated (63-99 ppm)' 
    elif ppm < 200: return 'Contaminated (100-199 ppm)' 
    elif ppm < 400: return 'High (200-399 ppm)' 
    else: return 'Hazard (400+ ppm)' 

nysh_colors = {
    'Safe (< 63 ppm)': '#2ecc71',
    'Elevated (63-99 ppm)': '#f1c40f',
    'Contaminated (100-199 ppm)': '#e67e22',
    'High (200-399 ppm)': '#e74c3c',
    'Hazard (400+ ppm)': '#800000', # Dark Red/Maroon
    'Unknown': '#808080'
}

# --- 2. GPS OFFSET CALCULATOR ---
def calculate_coordinate(start_lat, start_lon, offset_north_ft, offset_east_ft):
    """Calculates a GPS coordinate based on an offset in feet. Handles negatives (South/West) automatically."""
    R_EARTH_FT = 20925721.78 
    delta_lat = (offset_north_ft / R_EARTH_FT) * (180 / math.pi)
    lat_radians = start_lat * (math.pi / 180)
    delta_lon = (offset_east_ft / (R_EARTH_FT * math.cos(lat_radians))) * (180 / math.pi)
    return start_lat + delta_lat, start_lon + delta_lon

# --- DATA LOADING FUNCTIONS ---
@st.cache_data
def load_chemistry_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, '..', 'Data', 'xrf_data')
    search_path = os.path.join(data_dir, 'chemistry*.csv')
    files = glob.glob(search_path)
    
    if not files:
        return pd.DataFrame()
    
    all_data = []
    for f in files:
        df = pd.read_csv(f)
        df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
        all_data.append(df)
        
    final_df = pd.concat(all_data, ignore_index=True)
    
    elements = {'Pb': 'Lead', 'Zn': 'Zinc', 'As': 'Arsenic', 'Fe': 'Iron'}
    for sym, name in elements.items():
        col_name = f"{sym} Concentration"
        if col_name in final_df.columns:
            final_df[name] = pd.to_numeric(final_df[col_name], errors='coerce')
            
    return final_df

@st.cache_data
def load_master_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    master_dir = os.path.join(base_dir, '..', 'Data', 'master_data')
    master_files = glob.glob(os.path.join(master_dir, 'Master_Data_v*.csv'))
    
    if not master_files:
        return pd.DataFrame()
        
    def get_version(filename):
        match = re.search(r'_v(\d+)\.csv', filename)
        return int(match.group(1)) if match else 0
        
    latest_file = max(master_files, key=get_version)
    df = pd.read_csv(latest_file)
    
    site_db_path = os.path.join(base_dir, '..', 'Data', 'site_databases', 'XRF Site Analysis Database W SampleID(Sheet1).csv')
    if os.path.exists(site_db_path):
        site_db = pd.read_csv(site_db_path, header=1, encoding='latin1')
        site_db['Address'] = site_db['Address'].ffill()
        site_mapping = dict(zip(site_db['SampleID'].dropna(), site_db['Address'].dropna()))
        df['Site_Address'] = df['SampleID'].map(site_mapping).fillna("Unknown Address")
    else:
        df['Site_Address'] = "Unknown Address"
        
    return df

# --- LOAD DATA ---
chem_df = load_chemistry_data()
master_df = load_master_data()

if chem_df.empty:
    st.error("No data found! Please ensure your chemistry files are inside the 'Data/xrf_data' folder.")
    st.stop()

# --- SIDEBAR FILTERS ---
st.sidebar.header("Filter Options")
date_range = st.sidebar.date_input("Select Date Range", [chem_df['DateTime'].min(), chem_df['DateTime'].max()])
epa_limit = st.sidebar.number_input("EPA Safety Limit (ppm)", value=400, step=50)

mask = (chem_df['DateTime'].dt.date >= date_range[0]) & (chem_df['DateTime'].dt.date <= date_range[1])
filtered_chem_df = chem_df.loc[mask]

# --- KEY METRICS ROW ---
col1, col2, col3, col4 = st.columns(4)
avg_lead = filtered_chem_df['Lead'].mean()
max_lead = filtered_chem_df['Lead'].max()
high_risk_count = filtered_chem_df[filtered_chem_df['Lead'] > epa_limit].shape[0]
percent_safe = 100 - (high_risk_count / len(filtered_chem_df) * 100) if len(filtered_chem_df) > 0 else 100

col1.metric("Avg Lead Level", f"{avg_lead:.1f} ppm", delta_color="inverse")
col2.metric("Max Detected", f"{max_lead:.0f} ppm", delta="-High" if max_lead > epa_limit else "normal")
col3.metric("Total Readings", f"{len(filtered_chem_df)}")
col4.metric("Safety Rate", f"{percent_safe:.1f}%")

st.markdown("---")

# --- VISUALIZATIONS ---

# ROW 1: REAL GEOSPATIAL YARD GRID HEATMAP
st.subheader("🗺️ High-Resolution Geospatial Site Map (NYSH Guidelines)")
st.markdown("Select a site address to view the exact grid layouts overlaid on satellite imagery.")

if not master_df.empty and 'Site_Address' in master_df.columns:
    site_list = sorted(master_df['Site_Address'].unique().tolist())
    selected_site = st.selectbox("Select Site to Map:", site_list)

    if selected_site == "252 E Utica St" or "Utica" in selected_site:
        site_df = master_df[master_df['Site_Address'] == selected_site].copy()
        site_df['Lead'] = pd.to_numeric(site_df['LeadPPM'], errors='coerce')
        
        # Corner of Porch at 252 E Utica St
        ANCHOR_LAT = 42.9115083
        ANCHOR_LON = -78.8563833

        grid_layout = {
            "1A_Utica": {"sw_x": -17, "sw_y": 20, "ne_x": -10, "ne_y": 30, "mock_ppm": 45},  
            "1B_Utica": {"sw_x": -17, "sw_y": 10, "ne_x": -10, "ne_y": 20, "mock_ppm": 45},  
            "1C_Utica": {"sw_x": -17, "sw_y": 0,  "ne_x": -10, "ne_y": 10, "mock_ppm": 150}, 
            "2A_Utica": {"sw_x": -10, "sw_y": 20, "ne_x": 0,   "ne_y": 30, "mock_ppm": 85},  
            "2B_Utica": {"sw_x": -10, "sw_y": 10, "ne_x": 0,   "ne_y": 20, "mock_ppm": 150}, 
            "2C_Utica": {"sw_x": -10, "sw_y": 0,  "ne_x": 0,   "ne_y": 10, "mock_ppm": 250}, 
            "3A_Utica": {"sw_x": 0,   "sw_y": 20, "ne_x": 10,  "ne_y": 30, "mock_ppm": 150}, 
            "3B_Utica": {"sw_x": 0,   "sw_y": 10, "ne_x": 10,  "ne_y": 20, "mock_ppm": 250}, 
            "3C_Utica": {"sw_x": 0,   "sw_y": 0,  "ne_x": 10,  "ne_y": 10, "mock_ppm": 450}, 
            "3D_Utica": {"sw_x": 0,   "sw_y": -6, "ne_x": 10,  "ne_y": 0,  "mock_ppm": 450}, 
        }

        # Initialize map
        m = folium.Map(location=[ANCHOR_LAT + 0.00004, ANCHOR_LON - 0.00002], zoom_start=21, max_zoom=25, tiles=None)

        # High-Res Esri Satellite Layer (with zoom unlock)
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Esri Satellite',
            max_zoom=25,
            max_native_zoom=19,
            overlay=False,
            control=True
        ).add_to(m)

        # Draw the Anchor Point (Porch Corner)
        folium.Marker(
            location=[ANCHOR_LAT, ANCHOR_LON],
            tooltip="<b>Porch Corner (Anchor Point at 3D/3C/2C)</b>",
            icon=folium.Icon(color='red', icon='home')
        ).add_to(m)

        # Draw all colored Rectangles
        for sample_id, dims in grid_layout.items():
            sw_lat, sw_lon = calculate_coordinate(ANCHOR_LAT, ANCHOR_LON, dims["sw_y"], dims["sw_x"])
            ne_lat, ne_lon = calculate_coordinate(ANCHOR_LAT, ANCHOR_LON, dims["ne_y"], dims["ne_x"])
            
            # Use REAL dashboard data if available, otherwise use your mock_ppm
            real_data_match = site_df[site_df['SampleID'] == sample_id]
            if not real_data_match.empty and not pd.isna(real_data_match['Lead'].iloc[0]):
                ppm = real_data_match['Lead'].iloc[0]
            else:
                ppm = dims["mock_ppm"]
                
            # --- THE BUG FIX ---
            label = get_nysh_category(ppm)
            color_hex = nysh_colors.get(label, '#808080')
            
            width = dims["ne_x"] - dims["sw_x"]
            length = dims["ne_y"] - dims["sw_y"]
            
            tooltip_html = f"""
            <div style='font-family: Arial; font-size: 14px;'>
                <b>Sample:</b> {sample_id}<br>
                <b>Size:</b> {width}x{length} ft<br>
                <b>Lead Level:</b> {ppm:.1f} ppm<br>
                <b>NYSH Status:</b> {label}
            </div>
            """
            
            folium.Rectangle(
                bounds=[[sw_lat, sw_lon], [ne_lat, ne_lon]],
                color='white',
                weight=2,
                fill=True,
                fill_color=color_hex,
                fill_opacity=0.75, 
                tooltip=tooltip_html
            ).add_to(m)

        st_folium(m, width=1000, height=600, returned_objects=[])

    else:
        st.info(f"Custom spatial mapping is currently hardcoded and configured only for the Utica site. Please select '252 E Utica St'.")
else:
    st.info("Please process data through the ETL Pipeline to generate Site Heatmaps.")

st.markdown("---")

# ROW 2: Distribution 
st.subheader("📊 Lead Distribution Histogram")
fig_hist = px.histogram(filtered_chem_df, x="Lead", nbins=20, title="Frequency of Lead Concentrations",
                        color_discrete_sequence=['#2E8B57'])
fig_hist.add_vline(x=epa_limit, line_dash="dash", line_color="red", annotation_text="EPA Limit")
st.plotly_chart(fig_hist, use_container_width=True)

st.markdown("---")

# ROW 3: Advanced Correlations 
st.subheader("🔬 Multi-Element Soil Fingerprint")
if 'Zinc' in filtered_chem_df.columns and 'Arsenic' in filtered_chem_df.columns:
    plot_df = filtered_chem_df.copy()
    plot_df['Arsenic'] = plot_df['Arsenic'].fillna(1) 
    if 'Iron' in plot_df.columns:
        plot_df['Iron'] = plot_df['Iron'].fillna(0)

    fig_corr = px.scatter(plot_df, x="Zinc", y="Lead", 
                          size="Arsenic", color="Iron",
                          hover_data=['DateTime', 'Lead', 'Zinc', 'Arsenic'],
                          title="Lead vs. Zinc Correlation (Sized by Arsenic, Colored by Iron)",
                          color_continuous_scale="Viridis")
    st.plotly_chart(fig_corr, use_container_width=True)
else:
    st.info("Zinc or Arsenic data missing from current dataset.")
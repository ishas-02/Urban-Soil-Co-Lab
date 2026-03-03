# import streamlit as st
# import pandas as pd
# import plotly.express as px
# import plotly.graph_objects as go
# import glob

# # --- PAGE CONFIGURATION ---
# st.set_page_config(page_title="GroundSense Dashboard", page_icon="🌱", layout="wide")

# # --- TITLE & HEADER ---
# st.title("🌱 GroundSense: Urban Soil Health Dashboard")
# st.markdown("### Preliminary XRF Analysis & Lead (Pb) Monitoring")
# st.markdown("---")

# # --- DATA LOADING FUNCTION ---
# @st.cache_data
# def load_data():
#     # 1. Find all chemistry files
#     files = glob.glob('chemistry*.csv')
#     if not files:
#         return pd.DataFrame()
    
#     all_data = []
#     for f in files:
#         df = pd.read_csv(f)
#         # Create a clean Timestamp
#         df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
#         all_data.append(df)
        
#     final_df = pd.concat(all_data, ignore_index=True)
    
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
#     st.error("No data found! Please ensure 'chemistry-*.csv' files are in the folder.")
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
# percent_safe = 100 - (high_risk_count / len(filtered_df) * 100)

# col1.metric("Avg Lead Level", f"{avg_lead:.1f} ppm", delta_color="inverse")
# col2.metric("Max Detected", f"{max_lead:.0f} ppm", delta="-High" if max_lead > epa_limit else "normal")
# col3.metric(f"Samples > {epa_limit} ppm", f"{high_risk_count}", delta_color="inverse")
# col4.metric("Safety Rate", f"{percent_safe:.1f}%")

# st.markdown("---")

# # --- VISUALIZATIONS ---

# # ROW 1: Distribution & Trends
# c1, c2 = st.columns(2)

# with c1:
#     st.subheader("📊 Lead Distribution Histogram")
#     fig_hist = px.histogram(filtered_df, x="Lead", nbins=20, title="Frequency of Lead Concentrations",
#                             color_discrete_sequence=['#2E8B57'])
#     fig_hist.add_vline(x=epa_limit, line_dash="dash", line_color="red", annotation_text="EPA Limit")
#     st.plotly_chart(fig_hist, use_container_width=True)

# with c2:
#     st.subheader("📈 Temporal Trend (QC Check)")
#     # Sort by time to show sequence
#     filtered_df = filtered_df.sort_values('DateTime')
#     fig_line = px.line(filtered_df, x="DateTime", y="Lead", markers=True, title="Lead Readings Over Time")
#     fig_line.add_hline(y=epa_limit, line_dash="dash", line_color="red")
#     st.plotly_chart(fig_line, use_container_width=True)

# # --- GRID HEATMAP SECTION ---
# st.subheader("🔥 Site Grid Heatmap")
# st.markdown("Visualizing contamination across the physical sampling grid (A1, A2, B1...).")

# # Function to parse Row/Col from SampleID
# def parse_grid(sample_id):
#     if not isinstance(sample_id, str): return None, None
#     # Looking for patterns like "A1_..." or "B2_..."
#     parts = sample_id.split('_')
#     grid_part = parts[0] # "A1"
    
#     # Simple check: First char is letter, second is digit
#     if len(grid_part) >= 2 and grid_part[0].isalpha() and grid_part[1].isdigit():
#         return grid_part[0], grid_part[1] # Row "A", Col "1"
#     return None, None

# # 1. We need the Master Data logic (SampleIDs) for this
# # Since we are generating the draft master data in the ETL script, 
# # let's simulate it or check if 'SampleID' exists in your dataframe.
# if 'SampleID' in filtered_df.columns:
#     # Extract Grid Coordinates
#     heatmap_data = filtered_df.copy()
#     heatmap_data[['Grid_Row', 'Grid_Col']] = heatmap_data['SampleID'].apply(
#         lambda x: pd.Series(parse_grid(x))
#     )
    
#     # Filter for valid grid points only
#     heatmap_data = heatmap_data.dropna(subset=['Grid_Row', 'Grid_Col'])
    
#     if not heatmap_data.empty:
#         # Create Pivot Table: Rows vs Cols, Values = Lead
#         grid_matrix = heatmap_data.pivot_table(
#             index='Grid_Row', 
#             columns='Grid_Col', 
#             values='Lead', 
#             aggfunc='mean'
#         )
        
#         # Sort index to ensure A, B, C order
#         grid_matrix = grid_matrix.sort_index()
        
#         # Plot
#         fig_heat = px.imshow(grid_matrix, 
#                              labels=dict(x="Grid Column", y="Grid Row", color="Lead (ppm)"),
#                              color_continuous_scale="RdYlGn_r", # Red = High Lead, Green = Low
#                              title="Average Lead Concentration by Grid Location")
#         st.plotly_chart(fig_heat, use_container_width=True)
#     else:
#         st.warning("Could not extract grid coordinates (e.g., 'A1', 'B2') from Sample IDs.")
# else:
#     st.info("To generate a grid heatmap, you need to map Reading # to Sample IDs (A1, A2...) first.")

# # # ROW 2: Advanced Correlations (The "Creative" Part)
# # st.subheader("🔬 Multi-Element Soil Fingerprint")
# # st.markdown("Lead contamination often co-occurs with other heavy metals. This chart explores those relationships.")

# # # Check if we have Zinc and Arsenic data
# # if 'Zinc' in filtered_df.columns and 'Arsenic' in filtered_df.columns:
# #     fig_corr = px.scatter(filtered_df, x="Zinc", y="Lead", 
# #                           size="Arsenic", color="Iron",
# #                           hover_data=['DateTime', 'Lead', 'Zinc', 'Arsenic'],
# #                           title="Lead vs. Zinc Correlation (Sized by Arsenic, Colored by Iron)",
# #                           color_continuous_scale="Viridis")
# #     st.plotly_chart(fig_corr, use_container_width=True)
# # else:
# #     st.info("Zinc or Arsenic data missing from current dataset.")

# # # --- RAW DATA VIEW ---
# # with st.expander("📂 View Raw Processed Data"):
# #     st.dataframe(filtered_df)

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

# # --- PAGE CONFIGURATION ---
# st.set_page_config(page_title="GroundSense Dashboard", page_icon="🌱", layout="wide")

# # --- TITLE & HEADER ---
# st.title("🌱 Urban Soil Health Dashboard")
# st.markdown("### Preliminary XRF Analysis & Lead (Pb) Monitoring")
# st.markdown("---")

# # --- DATA LOADING FUNCTION ---
# @st.cache_data
# def load_data():
#     # 1. Find all chemistry files
#     files = glob.glob('chemistry*.csv')
#     if not files:
#         return pd.DataFrame()
    
#     all_data = []
#     for f in files:
#         df = pd.read_csv(f)
#         # Create a clean Timestamp
#         df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
#         all_data.append(df)
        
#     final_df = pd.concat(all_data, ignore_index=True)
    
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
#     st.error("No data found! Please ensure 'chemistry-*.csv' files are in the folder.")
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

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import glob
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="GroundSense Dashboard", page_icon="🌱", layout="wide")

# --- TITLE & HEADER ---
st.title("🌱 Urban Soil Health Dashboard")
st.markdown("### Preliminary XRF Analysis & Lead (Pb) Monitoring")
st.markdown("---")

# --- DATA LOADING FUNCTION ---
# @st.cache_data
# def load_data():
#     # 1. Find all chemistry files INSIDE the 'xrf_data' folder
#     # We use os.path.join to ensure it works on both Windows and Mac
#     search_path = os.path.join('xrf_data', 'chemistry*.csv')
#     files = glob.glob(search_path)
    
#     if not files:
#         return pd.DataFrame()
    
#     all_data = []
#     for f in files:
#         df = pd.read_csv(f)
#         # Create a clean Timestamp
#         df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
#         all_data.append(df)
        
#     final_df = pd.concat(all_data, ignore_index=True)

# --- DATA LOADING FUNCTION ---
@st.cache_data
def load_data():
    # 1. Get the absolute path of the 'src' directory where dashboard.py lives
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. Navigate up to the root, then into Data/xrf_data (Capital 'D' to match your folder!)
    data_dir = os.path.join(base_dir, '..', 'data', 'xrf_data')
    
    # 3. Create the search path
    search_path = os.path.join(data_dir, 'chemistry*.csv')
    files = glob.glob(search_path)
    
    if not files:
        # Prints to your terminal so we can see exactly where it searched if it fails
        print(f"DEBUG: Looked for files in: {search_path}") 
        return pd.DataFrame()
    
    all_data = []
    for f in files:
        df = pd.read_csv(f)
        # Create a clean Timestamp
        df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'])
        all_data.append(df)
        
    final_df = pd.concat(all_data, ignore_index=True)
    
    # Clean & Rename Key Columns
    elements = {'Pb': 'Lead', 'Zn': 'Zinc', 'As': 'Arsenic', 'Fe': 'Iron'}
    for sym, name in elements.items():
        col_name = f"{sym} Concentration"
        if col_name in final_df.columns:
            final_df[name] = pd.to_numeric(final_df[col_name], errors='coerce')
    
    return final_df
    
    # 2. Clean & Rename Key Columns
    # Ensure numeric conversion for key elements
    elements = {'Pb': 'Lead', 'Zn': 'Zinc', 'As': 'Arsenic', 'Fe': 'Iron'}
    for sym, name in elements.items():
        col_name = f"{sym} Concentration"
        if col_name in final_df.columns:
            # Force numeric, turning '<LOD' into NaN (or 0 if you prefer)
            final_df[name] = pd.to_numeric(final_df[col_name], errors='coerce')
    
    return final_df

# --- LOAD DATA ---
df = load_data()

if df.empty:
    st.error("No data found! Please ensure your chemistry files are inside the 'xrf_data' folder.")
    st.stop()

# --- SIDEBAR FILTERS ---
st.sidebar.header("Filter Options")
date_range = st.sidebar.date_input("Select Date Range", [df['DateTime'].min(), df['DateTime'].max()])
epa_limit = st.sidebar.number_input("EPA Safety Limit (ppm)", value=400, step=50)

# Filter data based on selection
mask = (df['DateTime'].dt.date >= date_range[0]) & (df['DateTime'].dt.date <= date_range[1])
filtered_df = df.loc[mask]

# --- KEY METRICS ROW ---
col1, col2, col3, col4 = st.columns(4)

avg_lead = filtered_df['Lead'].mean()
max_lead = filtered_df['Lead'].max()
high_risk_count = filtered_df[filtered_df['Lead'] > epa_limit].shape[0]
percent_safe = 100 - (high_risk_count / len(filtered_df) * 100) if len(filtered_df) > 0 else 100

# NEW METRIC: Calculate total sites/readings examined
sites_examined = len(filtered_df)

col1.metric("Avg Lead Level", f"{avg_lead:.1f} ppm", delta_color="inverse")
col2.metric("Max Detected", f"{max_lead:.0f} ppm", delta="-High" if max_lead > epa_limit else "normal")
col3.metric("Sites Examined", f"{sites_examined}")
col4.metric("Safety Rate", f"{percent_safe:.1f}%")

st.markdown("---")

# --- VISUALIZATIONS ---

# ROW 1: Distribution 
st.subheader("📊 Lead Distribution Histogram")
fig_hist = px.histogram(filtered_df, x="Lead", nbins=20, title="Frequency of Lead Concentrations",
                        color_discrete_sequence=['#2E8B57'])
fig_hist.add_vline(x=epa_limit, line_dash="dash", line_color="red", annotation_text="EPA Limit")
# Displaying the chart in full width now since the other chart is removed
st.plotly_chart(fig_hist, use_container_width=True)

st.markdown("---")

# ROW 2: Advanced Correlations (The "Creative" Part)
st.subheader("🔬 Multi-Element Soil Fingerprint")
st.markdown("Lead contamination often co-occurs with other heavy metals. This chart explores those relationships.")

# Check if we have Zinc and Arsenic data
if 'Zinc' in filtered_df.columns and 'Arsenic' in filtered_df.columns:
    # --- FIX START: Handle Missing Values for Plotting ---
    # Create a copy so we don't mess up the original data
    plot_df = filtered_df.copy()
    
    # Fill missing Arsenic values with 0 so the code doesn't crash
    # (Visually, this means points with no Arsenic data will be very small dots)
    plot_df['Arsenic'] = plot_df['Arsenic'].fillna(1) 
    
    # Also fill Iron just in case
    if 'Iron' in plot_df.columns:
        plot_df['Iron'] = plot_df['Iron'].fillna(0)
    # --- FIX END ---

    fig_corr = px.scatter(plot_df, x="Zinc", y="Lead", 
                          size="Arsenic", color="Iron",
                          # Update hover data to use the filled dataframe
                          hover_data=['DateTime', 'Lead', 'Zinc', 'Arsenic'],
                          title="Lead vs. Zinc Correlation (Sized by Arsenic, Colored by Iron)",
                          color_continuous_scale="Viridis")
    st.plotly_chart(fig_corr, use_container_width=True)
else:
    st.info("Zinc or Arsenic data missing from current dataset.")
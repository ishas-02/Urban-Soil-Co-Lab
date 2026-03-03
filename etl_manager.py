import streamlit as st
import os
import glob
import re
import subprocess

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="GroundSense Data Pipeline", page_icon="⚙️", layout="centered")

st.title("⚙️ Data Pipeline Manager")
st.markdown("Drag and drop your raw XRF analysis files here. The backend will automatically process the data, map the Sample IDs, and generate the newest version of the Master Data.")
st.markdown("---")

# --- 1. FILE UPLOADER ---
uploaded_files = st.file_uploader("Upload New XRF analysis CSVs", type=['csv'], accept_multiple_files=True)

if st.button("🚀 Process Data & Update Master", type="primary"):
    if uploaded_files:
        # Step A: Save the uploaded files to the correct folder
        xrf_dir = os.path.join("data", "xrf_data")
        os.makedirs(xrf_dir, exist_ok=True)
        
        for f in uploaded_files:
            file_path = os.path.join(xrf_dir, f.name)
            with open(file_path, "wb") as f_out:
                f_out.write(f.read())
                
        st.success(f"✅ Successfully saved {len(uploaded_files)} file(s) to `data/xrf_data/`")
        
        # Step B: Run the backend Python script automatically
        with st.spinner("Running background ETL pipeline..."):
            # This runs your src/data.py exactly as if you typed it in the terminal
            result = subprocess.run(["python", "src/data.py"], capture_output=True, text=True)
            
        # Show the terminal logs directly on the web page so you can see what happened!
        with st.expander("🔍 View Pipeline Logs", expanded=True):
            st.code(result.stdout)
            
        if result.returncode == 0:
            st.success("🎉 Pipeline executed successfully!")
        else:
            st.error("⚠️ Pipeline encountered an error. Check the logs above.")
            st.stop()
            
        # Step C: Find the newly created Master file for download
        master_dir = os.path.join("data", "master_data")
        master_files = glob.glob(os.path.join(master_dir, 'Master_Data_v*.csv'))
        
        if master_files:
            def get_version(filename):
                match = re.search(r'_v(\d+)\.csv', filename)
                return int(match.group(1)) if match else 0
                
            latest_file = max(master_files, key=get_version)
            
            st.markdown("### 📥 Download Ready")
            with open(latest_file, "rb") as file:
                st.download_button(
                    label=f"Download Latest Master Data ({os.path.basename(latest_file)})",
                    data=file,
                    file_name=os.path.basename(latest_file),
                    mime="text/csv"
                )
    else:
        st.warning("Please upload at least one chemistry file first.")

# import streamlit as st
# import os
# import glob
# import re
# import subprocess
# import pandas as pd
# from datetime import datetime
# from pptx import Presentation # The new library!
# import zipfile
# import io

# # --- PAGE CONFIGURATION ---
# st.set_page_config(page_title="GroundSense Data Pipeline", page_icon="⚙️", layout="centered")

# st.title("⚙️ GroundSense Data Pipeline Manager")
# st.markdown("Drag and drop your raw XRF chemistry files here to process data and generate resident reports automatically.")
# st.markdown("---")

# # --- 1. FILE UPLOADER & ETL PIPELINE ---
# uploaded_files = st.file_uploader("Upload New Chemistry CSVs", type=['csv'], accept_multiple_files=True)

# if st.button("🚀 Process Data & Update Master", type="primary"):
#     if uploaded_files:
#         xrf_dir = os.path.join("data", "xrf_data")
#         os.makedirs(xrf_dir, exist_ok=True)
        
#         for f in uploaded_files:
#             file_path = os.path.join(xrf_dir, f.name)
#             with open(file_path, "wb") as f_out:
#                 f_out.write(f.read())
                
#         st.success(f"✅ Successfully saved {len(uploaded_files)} file(s).")
        
#         with st.spinner("Running background ETL pipeline..."):
#             result = subprocess.run(["python", "src/data.py"], capture_output=True, text=True)
            
#         with st.expander("🔍 View Pipeline Logs", expanded=False):
#             st.code(result.stdout)
            
#         if result.returncode == 0:
#             st.success("🎉 Pipeline executed successfully!")
#         else:
#             st.error("⚠️ Pipeline encountered an error. Check the logs.")
#             st.stop()
#     else:
#         st.warning("Please upload at least one chemistry file first.")

# st.markdown("---")
# st.subheader("📄 Automated Resident Report Generation")

# # --- 2. REPORT GENERATOR LOGIC ---
# if st.button("Generate Reports for All Sites"):
#     with st.spinner("Generating custom reports..."):
#         # 1. Load the data
#         site_db_path = os.path.join("data", "site_databases", "XRF Site Analysis Database W SampleID(Sheet1).csv")
#         master_dir = os.path.join("data", "master_data")
        
#         # Get the latest master file
#         master_files = glob.glob(os.path.join(master_dir, 'Master_Data_v*.csv'))
#         if not master_files:
#             st.error("No Master Data found. Please run the pipeline first.")
#             st.stop()
            
#         latest_master = max(master_files, key=os.path.getctime)
        
#         df_site = pd.read_csv(site_db_path, header=1, encoding='latin1')
#         df_master = pd.read_csv(latest_master)
        
#         # 2. Merge Data: We need max lead level per resident
#         # Drop duplicates in site DB to get unique addresses/residents
#         df_residents = df_site[['SampleID', 'FirstName', 'LastName', 'Address', 'City', 'ZipCode']].dropna(subset=['FirstName'])
#         df_residents = df_residents.drop_duplicates(subset=['FirstName', 'LastName', 'Address'])
        
#         # Merge with master data to get Lead levels
#         merged_data = pd.merge(df_residents, df_master, on='SampleID', how='inner')
        
#         # Group by Address to find the max lead level for that specific property
#         property_summary = merged_data.groupby(['FirstName', 'LastName', 'Address', 'City', 'ZipCode'])['LeadPPM'].max().reset_index()

#         # 3. Create the Reports
#         template_path = os.path.join("src", "Report_Template.pptx")
#         reports_dir = os.path.join("data", "generated_reports")
#         os.makedirs(reports_dir, exist_ok=True)
        
#         generated_files = []
#         today_date = datetime.today().strftime('%B %d, %Y')
        
#         for index, row in property_summary.iterrows():
#             # Open the template fresh for each resident
#             prs = Presentation(template_path)
            
#             # Dictionary of what to replace
#             replacements = {
#                 "[FIRST_NAME]": str(row['FirstName']),
#                 "[LAST_NAME]": str(row['LastName']),
#                 "[ADDRESS]": f"{row['Address']}, {row['City']}, NY {int(row['ZipCode'])}",
#                 "[MAX_LEAD]": str(row['LeadPPM']),
#                 "[DATE]": today_date
#             }
            
#             # Loop through slides and replace text
#             for slide in prs.slides:
#                 for shape in slide.shapes:
#                     if hasattr(shape, "text"):
#                         for key, val in replacements.items():
#                             if key in shape.text:
#                                 shape.text = shape.text.replace(key, val)
            
#             # Save the customized report
#             safe_address = str(row['Address']).replace(" ", "_")
#             report_filename = f"GroundSense_Report_{row['FirstName']}_{row['LastName']}_{safe_address}.pptx"
#             report_path = os.path.join(reports_dir, report_filename)
#             prs.save(report_path)
#             generated_files.append(report_path)
            
#         # 4. ZIP them up for easy download
#         zip_buffer = io.BytesIO()
#         with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
#             for file in generated_files:
#                 zip_file.write(file, arcname=os.path.basename(file))
        
#         st.success(f"✅ Successfully generated {len(generated_files)} customized reports!")
        
#         st.download_button(
#             label="📦 Download All Reports (ZIP)",
#             data=zip_buffer.getvalue(),
#             file_name=f"GroundSense_Reports_{datetime.today().strftime('%Y%m%d')}.zip",
#             mime="application/zip"
#         )
# # import streamlit as st
# # import os
# # import glob
# # import re
# # import subprocess

# # # --- PAGE CONFIGURATION ---
# # st.set_page_config(page_title="GroundSense Data Pipeline", page_icon="⚙️", layout="centered")

# # st.title("⚙️ Data Pipeline Manager")
# # st.markdown("Drag and drop your raw XRF analysis files here. The backend will automatically process the data, map the Sample IDs, and generate the newest version of the Master Data.")
# # st.markdown("---")

# # # --- 1. FILE UPLOADER ---
# # uploaded_files = st.file_uploader("Upload New XRF analysis CSVs", type=['csv'], accept_multiple_files=True)

# # if st.button("🚀 Process Data & Update Master", type="primary"):
# #     if uploaded_files:
# #         # Step A: Save the uploaded files to the correct folder
# #         xrf_dir = os.path.join("data", "xrf_data")
# #         os.makedirs(xrf_dir, exist_ok=True)
        
# #         for f in uploaded_files:
# #             file_path = os.path.join(xrf_dir, f.name)
# #             with open(file_path, "wb") as f_out:
# #                 f_out.write(f.read())
                
# #         st.success(f"✅ Successfully saved {len(uploaded_files)} file(s) to `data/xrf_data/`")
        
# #         # Step B: Run the backend Python script automatically
# #         with st.spinner("Running background ETL pipeline..."):
# #             # This runs your src/data.py exactly as if you typed it in the terminal
# #             result = subprocess.run(["python", "src/data.py"], capture_output=True, text=True)
            
# #         # Show the terminal logs directly on the web page so you can see what happened!
# #         with st.expander("🔍 View Pipeline Logs", expanded=True):
# #             st.code(result.stdout)
            
# #         if result.returncode == 0:
# #             st.success("🎉 Pipeline executed successfully!")
# #         else:
# #             st.error("⚠️ Pipeline encountered an error. Check the logs above.")
# #             st.stop()
            
# #         # Step C: Find the newly created Master file for download
# #         master_dir = os.path.join("data", "master_data")
# #         master_files = glob.glob(os.path.join(master_dir, 'Master_Data_v*.csv'))
        
# #         if master_files:
# #             def get_version(filename):
# #                 match = re.search(r'_v(\d+)\.csv', filename)
# #                 return int(match.group(1)) if match else 0
                
# #             latest_file = max(master_files, key=get_version)
            
# #             st.markdown("### 📥 Download Ready")
# #             with open(latest_file, "rb") as file:
# #                 st.download_button(
# #                     label=f"Download Latest Master Data ({os.path.basename(latest_file)})",
# #                     data=file,
# #                     file_name=os.path.basename(latest_file),
# #                     mime="text/csv"
# #                 )
# #     else:
# #         st.warning("Please upload at least one chemistry file first.")


# import streamlit as st
# import os
# import glob
# import re
# import subprocess
# import shutil
# import pandas as pd
# from pptx import Presentation

# # --- PAGE CONFIGURATION ---
# st.set_page_config(page_title="GroundSense Data Pipeline", page_icon="⚙️", layout="centered")

# st.title("⚙️ Data Pipeline Manager")
# st.markdown("Drag and drop your raw XRF analysis files here. The backend will automatically process the data, map the Sample IDs, and generate the newest version of the Master Data and Resident Reports.")
# st.markdown("---")

# # --- REPORT GENERATION FUNCTION ---
# def generate_pptx_reports(master_csv_path, template_path, output_dir):
#     df = pd.read_csv(master_csv_path)
#     # Filter out rows where SampleID is blank or missing
#     df = df[df['SampleID'].notna() & (df['SampleID'] != "")]
    
#     # Get unique sites and their calculated average lead
#     sites = df[['SampleID', 'LeadAvg']].drop_duplicates()
    
#     os.makedirs(output_dir, exist_ok=True)
    
#     for _, row in sites.iterrows():
#         sample_id = str(row['SampleID'])
#         lead_avg = str(row['LeadAvg'])
        
#         # Load the presentation template
#         prs = Presentation(template_path)
        
#         # Loop through slides, shapes, and text to find placeholders
#         for slide in prs.slides:
#             for shape in slide.shapes:
#                 if not shape.has_text_frame:
#                     continue
#                 for paragraph in shape.text_frame.paragraphs:
#                     for run in paragraph.runs:
#                         # Replace specific text found in the template
#                         if "Name of Resident" in run.text:
#                             run.text = run.text.replace("Name of Resident", f"Resident ({sample_id})")
#                         if "Address of Resident" in run.text:
#                             run.text = run.text.replace("Address of Resident", f"Site: {sample_id}")
#                         if "Average Lead concentration (ppm)" in run.text:
#                             # Format to 1 decimal place
#                             try:
#                                 formatted_lead = f"Average Lead: {float(lead_avg):.1f} ppm"
#                                 run.text = run.text.replace("Average Lead concentration (ppm)", formatted_lead)
#                             except ValueError:
#                                 pass # Skip if LeadAvg isn't a clean number yet
                                
#         # Save the personalized report
#         output_file = os.path.join(output_dir, f"Resident_Report_{sample_id}.pptx")
#         prs.save(output_file)

# # --- 1. FILE UPLOADER ---
# uploaded_files = st.file_uploader("Upload New XRF analysis CSVs", type=['csv'], accept_multiple_files=True)

# if st.button("🚀 Process Data & Update Master", type="primary"):
#     if uploaded_files:
#         # Step A: Save the uploaded files to the correct folder (Capital 'D')
#         xrf_dir = os.path.join("Data", "xrf_data")
#         os.makedirs(xrf_dir, exist_ok=True)
        
#         for f in uploaded_files:
#             file_path = os.path.join(xrf_dir, f.name)
#             with open(file_path, "wb") as f_out:
#                 f_out.write(f.read())
                
#         # Step B: Run the backend Python script automatically
#         with st.spinner("Running background ETL pipeline..."):
#             result = subprocess.run(["python", "src/data.py"], capture_output=True, text=True)
            
#         if result.returncode == 0:
#             st.success("🎉 Pipeline executed successfully!")
#         else:
#             st.error("⚠️ Pipeline encountered an error. Please check your terminal for details.")
#             st.stop()
            
#         # Step C: Find the newly created Master file
#         master_dir = os.path.join("Data", "master_data")
#         master_files = glob.glob(os.path.join(master_dir, 'Master_Data_v*.csv'))
        
#         if master_files:
#             def get_version(filename):
#                 match = re.search(r'_v(\d+)\.csv', filename)
#                 return int(match.group(1)) if match else 0
                
#             latest_master_file = max(master_files, key=get_version)
            
#             # Step D: Generate the PPTX Reports
#             with st.spinner("Generating personalized resident reports..."):
#                 template_path = os.path.join("src", "Report_Template.pptx")
#                 reports_dir = os.path.join("Data", "generated_reports")
#                 zip_path_base = os.path.join("Data", "All_Resident_Reports")
                
#                 if os.path.exists(template_path):
#                     generate_pptx_reports(latest_master_file, template_path, reports_dir)
#                     # Zip the folder for easy downloading
#                     shutil.make_archive(zip_path_base, 'zip', reports_dir)
#                     st.success("📄 Resident Reports generated successfully!")
#                 else:
#                     st.warning(f"⚠️ Template not found at {template_path}. Skipping report generation.")

#             # --- DISPLAY DOWNLOAD BUTTONS ---
#             st.markdown("---")
#             col1, col2 = st.columns(2)
            
#             with col1:
#                 st.markdown("### 📊 Master Data")
#                 with open(latest_master_file, "rb") as file:
#                     st.download_button(
#                         label=f"Download Master Data ({os.path.basename(latest_master_file)})",
#                         data=file,
#                         file_name=os.path.basename(latest_master_file),
#                         mime="text/csv"
#                     )
            
#             with col2:
#                 zip_file_full = zip_path_base + ".zip"
#                 if os.path.exists(zip_file_full):
#                     st.markdown("### 🗂️ Resident Reports")
#                     with open(zip_file_full, "rb") as zip_file:
#                         st.download_button(
#                             label="Download All Reports (ZIP)",
#                             data=zip_file,
#                             file_name="GroundSense_Resident_Reports.zip",
#                             mime="application/zip",
#                             type="primary"
#                         )
#     else:
#         st.warning("Please upload at least one chemistry file first.")

import streamlit as st
import os
import glob
import re
import subprocess
import shutil
import pandas as pd
from pptx import Presentation

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="GroundSense Data Pipeline", page_icon="⚙️", layout="centered")

st.title("⚙️ Data Pipeline Manager")
st.markdown("Drag and drop your raw XRF analysis files here. The backend will automatically process the data, map the Sample IDs, and generate the newest version of the Master Data and Resident Reports.")
st.markdown("---")

# --- REPORT GENERATION FUNCTION ---
def generate_pptx_reports(master_csv_path, template_path, output_dir, site_db_path):
    df = pd.read_csv(master_csv_path)
    
    # Filter out rows where SampleID is blank or missing
    df = df[df['SampleID'].notna() & (df['SampleID'] != "")]
    
    # --- 1. EXTRACT REAL SITE ADDRESS FROM DATABASE ---
    if os.path.exists(site_db_path):
        # Using latin1 to prevent decode errors
        site_db = pd.read_csv(site_db_path, header=1, encoding='latin1') 
        
        # The database only lists the address on the first row of a site's block.
        # This forward-fills the address down so every single sample gets attached to a real address!
        site_db['Address'] = site_db['Address'].ffill()
        
        # Create a mapping dictionary: {SampleID: Address}
        site_mapping = dict(zip(site_db['SampleID'].dropna(), site_db['Address'].dropna()))
        
        # Map the addresses to our master dataframe. (If an address isn't found, fallback to the SampleID)
        df['SiteID'] = df['SampleID'].map(site_mapping).fillna(df['SampleID'])
    else:
        st.warning(f"⚠️ Could not find Site Database at {site_db_path}. Reports will not be grouped by address.")
        df['SiteID'] = df['SampleID']
    
    # --- 2. CALCULATE TRUE SITE AVERAGE ---
    df['LeadPPM_Numeric'] = pd.to_numeric(df['LeadPPM'], errors='coerce')
    
    # Group all samples (A1, A2, etc.) by their new Address and calculate the mean average
    site_averages = df.groupby('SiteID')['LeadPPM_Numeric'].mean().reset_index()
    
    os.makedirs(output_dir, exist_ok=True)
    
    # --- 3. GENERATE ONE REPORT PER SITE (ADDRESS) ---
    for _, row in site_averages.iterrows():
        site_id = str(row['SiteID'])
        site_avg = row['LeadPPM_Numeric']
        
        if pd.isna(site_avg):
            continue
            
        # Load the presentation template
        prs = Presentation(template_path)
        
        # Loop through slides, shapes, and text to find placeholders
        for slide in prs.slides:
            for shape in slide.shapes:
                if not shape.has_text_frame:
                    continue
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        # Replace specific text found in the template
                        if "Name of Resident" in run.text:
                            run.text = run.text.replace("Name of Resident", f"Resident at {site_id}")
                        if "Address of Resident" in run.text:
                            run.text = run.text.replace("Address of Resident", site_id)
                        if "Average Lead concentration (ppm)" in run.text:
                            # Format to 1 decimal place
                            formatted_lead = f"Average Lead: {site_avg:.1f} ppm"
                            run.text = run.text.replace("Average Lead concentration (ppm)", formatted_lead)
                                
        # Clean up filename to prevent errors with weird characters
        safe_filename = "".join([c for c in site_id if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        output_file = os.path.join(output_dir, f"Resident_Report_{safe_filename}.pptx")
        prs.save(output_file)

# --- 1. FILE UPLOADER ---
uploaded_files = st.file_uploader("Upload New XRF analysis CSVs", type=['csv'], accept_multiple_files=True)

if st.button("🚀 Process Data & Update Master", type="primary"):
    if uploaded_files:
        # Step A: Save the uploaded files to the correct folder
        xrf_dir = os.path.join("Data", "xrf_data")
        os.makedirs(xrf_dir, exist_ok=True)
        
        for f in uploaded_files:
            file_path = os.path.join(xrf_dir, f.name)
            with open(file_path, "wb") as f_out:
                f_out.write(f.read())
                
        # Step B: Run the backend Python script automatically
        with st.spinner("Running background ETL pipeline..."):
            result = subprocess.run(["python", "src/data.py"], capture_output=True, text=True)
            
        if result.returncode == 0:
            st.success("🎉 Pipeline executed successfully!")
        else:
            st.error("⚠️ Pipeline encountered an error. Please check your terminal for details.")
            st.stop()
            
        # Step C: Find the newly created Master file
        master_dir = os.path.join("Data", "master_data")
        master_files = glob.glob(os.path.join(master_dir, 'Master_Data_v*.csv'))
        
        if master_files:
            def get_version(filename):
                match = re.search(r'_v(\d+)\.csv', filename)
                return int(match.group(1)) if match else 0
                
            latest_master_file = max(master_files, key=get_version)
            
            # Step D: Generate the PPTX Reports
            with st.spinner("Grouping samples by address and generating reports..."):
                # Make sure your template is named exactly this and placed in the src folder!
                template_path = os.path.join("src", "Resident_Report_Template.pptx") 
                site_db_path = os.path.join("Data", "site_databases", "XRF Site Analysis Database W SampleID(Sheet1).csv")
                reports_dir = os.path.join("Data", "generated_reports")
                zip_path_base = os.path.join("Data", "All_Resident_Reports")
                
                if os.path.exists(template_path):
                    generate_pptx_reports(latest_master_file, template_path, reports_dir, site_db_path)
                    
                    # Zip the folder for easy downloading
                    shutil.make_archive(zip_path_base, 'zip', reports_dir)
                    st.success("📄 Resident Reports generated successfully!")
                else:
                    st.warning(f"⚠️ Template not found at {template_path}. Skipping report generation.")

            # --- DISPLAY DOWNLOAD BUTTONS ---
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📊 Master Data")
                with open(latest_master_file, "rb") as file:
                    st.download_button(
                        label=f"Download Master Data ({os.path.basename(latest_master_file)})",
                        data=file,
                        file_name=os.path.basename(latest_master_file),
                        mime="text/csv"
                    )
            
            with col2:
                zip_file_full = zip_path_base + ".zip"
                if os.path.exists(zip_file_full):
                    st.markdown("### 🗂️ Resident Reports")
                    with open(zip_file_full, "rb") as zip_file:
                        st.download_button(
                            label="Download All Reports (ZIP)",
                            data=zip_file,
                            file_name="GroundSense_Resident_Reports.zip",
                            mime="application/zip",
                            type="primary"
                        )
    else:
        st.warning("Please upload at least one chemistry file first.")
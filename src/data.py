# # import pandas as pd
# # import glob
# # import os

# # def process_chemistry_files():
# #     # 1. SMART LOADER: Automatically find all files starting with "chemistry" in the folder
# #     file_list = glob.glob('chemistry*.csv')
    
# #     if not file_list:
# #         print("No chemistry files found! Make sure they are in the same folder.")
# #         return

# #     print(f"Found {len(file_list)} files to process...")
    
# #     all_data = []

# #     for file_path in file_list:
# #         try:
# #             # Load the chemistry file
# #             df = pd.read_csv(file_path)
            
# #             # 2. Create XRFID: Format Date as "Mon DD" (e.g., Jan 08)
# #             # Ensure Date is datetime format
# #             df['Date_dt'] = pd.to_datetime(df['Date'])
# #             df['Date_Str'] = df['Date_dt'].dt.strftime('%b %d')
            
# #             # Combine to make ID: "Jan 08-1"
# #             df['XRFID'] = df['Date_Str'] + '-' + df['Reading #'].astype(str)
            
# #             # 3. Extract LeadPPM (Rename 'Pb Concentration')
# #             if 'Pb Concentration' in df.columns:
# #                 df['LeadPPM'] = df['Pb Concentration']
# #             else:
# #                 df['LeadPPM'] = pd.NA 
                
# #             # 4. Create Placeholders for the manual work later
# #             df['SampleID'] = "" 
# #             df['LeadAvg'] = "" 
            
# #             # 5. Select only the columns we need for the Master File
# #             master_df = df[['SampleID', 'XRFID', 'LeadPPM', 'LeadAvg']]
# #             all_data.append(master_df)
# #             print(f"Processed: {file_path}")
            
# #         except Exception as e:
# #             print(f"Error processing {file_path}: {e}")

# #     # Combine all processed files into one big table
# #     if all_data:
# #         final_master = pd.concat(all_data, ignore_index=True)
# #         return final_master
# #     else:
# #         return pd.DataFrame()

# # # --- EXECUTION ---
# # draft_master_data = process_chemistry_files()

# # if not draft_master_data.empty:
# #     # PREVIEW
# #     print("\nPreview of generated data:")
# #     print(draft_master_data.head())
# #     print(f"\nTotal rows processed: {len(draft_master_data)}")

# #     # SAVE TO CSV (This creates the file you will send to the Professor)
# #     output_filename = 'Draft_Master_Data_Output.csv'
# #     draft_master_data.to_csv(output_filename, index=False)
# #     print(f"\nSUCCESS! File saved as: {output_filename}")

# import pandas as pd
# import glob
# import os
# import re

# def generate_sequential_master_versions():
#     print("🔍 Scanning folder for chemistry files and existing Master Data...\n")
    
#     # 1. IDENTIFY THE LATEST MASTER VERSION (To pick up where we left off)
#     master_files = glob.glob('Master_Data_v*.csv')
    
#     existing_xrfids = set()
#     current_version = 0
    
#     if master_files:
#         # Find the highest version number
#         def get_version_number(filename):
#             match = re.search(r'_v(\d+)\.csv', filename)
#             return int(match.group(1)) if match else 0
            
#         latest_master_file = max(master_files, key=get_version_number)
#         current_version = get_version_number(latest_master_file)
        
#         # Load the latest master data to know what IDs we already have
#         master_df = pd.read_csv(latest_master_file)
#         existing_xrfids = set(master_df['XRFID'].astype(str))
#         print(f"📂 Resuming from '{latest_master_file}' (Contains {len(master_df)} records).")
#     else:
#         # Start completely fresh
#         master_df = pd.DataFrame(columns=['SampleID', 'XRFID', 'LeadPPM', 'LeadAvg'])
#         print("📂 No existing Master Data found. Starting fresh from Version 1.")

#     # 2. GET ALL CHEMISTRY FILES AND SORT THEM (Oldest to Newest)
#     # Sorting ensures we process them in the exact order they were created
#     chem_files = sorted(glob.glob('chemistry*.csv'))
    
#     files_processed_with_new_data = 0

#     # 3. PROCESS EACH FILE ONE BY ONE
#     for file_path in chem_files:
#         try:
#             df = pd.read_csv(file_path)
            
#             # Create the unique ID
#             df['Date_dt'] = pd.to_datetime(df['Date'])
#             df['Date_Str'] = df['Date_dt'].dt.strftime('%b %d')
#             df['XRFID'] = df['Date_Str'] + '-' + df['Reading #'].astype(str)
            
#             # Extract Lead
#             if 'Pb Concentration' in df.columns:
#                 df['LeadPPM'] = df['Pb Concentration']
#             else:
#                 df['LeadPPM'] = pd.NA 
                
#             df['SampleID'] = "" 
#             df['LeadAvg'] = "" 
            
#             clean_df = df[['SampleID', 'XRFID', 'LeadPPM', 'LeadAvg']]
            
#             # FILTER: Find rows from THIS chemistry file that aren't in the Master yet
#             new_rows = clean_df[~clean_df['XRFID'].isin(existing_xrfids)]
            
#             if not new_rows.empty:
#                 # --- THIS IS THE MAGIC PART ---
#                 # We found new data! Let's update the master and save a new version IMMEDIATELY.
                
#                 # 1. Add new IDs to our tracking list
#                 existing_xrfids.update(new_rows['XRFID'].tolist())
                
#                 # 2. Append new rows to the current Master DataFrame
#                 master_df = pd.concat([master_df, new_rows], ignore_index=True)
                
#                 # 3. Increment the version number
#                 current_version += 1
#                 output_filename = f'Master_Data_v{current_version}.csv'
                
#                 # 4. Save the new version
#                 master_df.to_csv(output_filename, index=False)
                
#                 print(f"✅ Processed {os.path.basename(file_path)}: Added {len(new_rows)} new readings.")
#                 print(f"   💾 Created {output_filename}")
                
#                 files_processed_with_new_data += 1
#             else:
#                 # If the file has no new data (we already processed it previously), skip it
#                 print(f"⏭️ Skipped {os.path.basename(file_path)}: Data already exists in Master.")
                
#         except Exception as e:
#             print(f"⚠️ Error reading {file_path}: {e}")

#     # 4. FINAL SUMMARY
#     if files_processed_with_new_data == 0:
#         print("\n✅ Check complete. No new chemistry files found. Everything is up to date.")
#     else:
#         print(f"\n🎉 Success! Created {files_processed_with_new_data} new Master Data version(s).")

# # --- RUN THE SCRIPT ---
# if __name__ == "__main__":
#     generate_sequential_master_versions()

# import pandas as pd
# import glob
# import os
# import re

# def generate_sequential_master_versions():
#     print("🔍 Scanning folder for chemistry files and existing Master Data...\n")
    
#     # --- FOLDER CONFIGURATION ---
#     input_dir = 'xrf_data'
#     output_dir = 'master_data'
    
#     # Ensure the output folder exists so the script doesn't crash on saving
#     os.makedirs(output_dir, exist_ok=True)
    
#     # 1. IDENTIFY THE LATEST MASTER VERSION in the 'master_data' folder
#     master_files = glob.glob(os.path.join(output_dir, 'Master_Data_v*.csv'))
    
#     existing_xrfids = set()
#     current_version = 0
    
#     if master_files:
#         # Find the highest version number
#         def get_version_number(filename):
#             match = re.search(r'_v(\d+)\.csv', filename)
#             return int(match.group(1)) if match else 0
            
#         latest_master_file = max(master_files, key=get_version_number)
#         current_version = get_version_number(latest_master_file)
        
#         # Load the latest master data to know what IDs we already have
#         master_df = pd.read_csv(latest_master_file)
#         existing_xrfids = set(master_df['XRFID'].astype(str))
#         print(f"📂 Resuming from '{latest_master_file}' (Contains {len(master_df)} records).")
#     else:
#         # Start completely fresh
#         master_df = pd.DataFrame(columns=['SampleID', 'XRFID', 'LeadPPM', 'LeadAvg'])
#         print(f"📂 No existing Master Data found in '{output_dir}'. Starting fresh from Version 1.")

#     # 2. GET ALL CHEMISTRY FILES FROM THE 'xrf_data' FOLDER AND SORT THEM
#     chem_files = sorted(glob.glob(os.path.join(input_dir, 'chemistry*.csv')))
    
#     if not chem_files:
#         print(f"⚠️ No chemistry files found in the '{input_dir}' folder. Please add some files.")
#         return

#     files_processed_with_new_data = 0

#     # 3. PROCESS EACH FILE ONE BY ONE
#     for file_path in chem_files:
#         try:
#             df = pd.read_csv(file_path)
            
#             # Create the unique ID
#             df['Date_dt'] = pd.to_datetime(df['Date'])
#             df['Date_Str'] = df['Date_dt'].dt.strftime('%b %d')
#             df['XRFID'] = df['Date_Str'] + '-' + df['Reading #'].astype(str)
            
#             # Extract Lead
#             if 'Pb Concentration' in df.columns:
#                 df['LeadPPM'] = df['Pb Concentration']
#             else:
#                 df['LeadPPM'] = pd.NA 
                
#             df['SampleID'] = "" 
#             df['LeadAvg'] = "" 
            
#             clean_df = df[['SampleID', 'XRFID', 'LeadPPM', 'LeadAvg']]
            
#             # FILTER: Find rows from THIS chemistry file that aren't in the Master yet
#             new_rows = clean_df[~clean_df['XRFID'].isin(existing_xrfids)]
            
#             if not new_rows.empty:
#                 # 1. Add new IDs to our tracking list
#                 existing_xrfids.update(new_rows['XRFID'].tolist())
                
#                 # 2. Append new rows to the current Master DataFrame
#                 master_df = pd.concat([master_df, new_rows], ignore_index=True)
                
#                 # 3. Increment the version number
#                 current_version += 1
#                 # Save into the 'master_data' folder
#                 output_filename = os.path.join(output_dir, f'Master_Data_v{current_version}.csv')
                
#                 # 4. Save the new version
#                 master_df.to_csv(output_filename, index=False)
                
#                 print(f"✅ Processed {os.path.basename(file_path)}: Added {len(new_rows)} new readings.")
#                 print(f"   💾 Created {output_filename}")
                
#                 files_processed_with_new_data += 1
#             else:
#                 # If the file has no new data, skip it
#                 print(f"⏭️ Skipped {os.path.basename(file_path)}: Data already exists in Master.")
                
#         except Exception as e:
#             print(f"⚠️ Error reading {file_path}: {e}")

#     # 4. FINAL SUMMARY
#     if files_processed_with_new_data == 0:
#         print("\n✅ Check complete. No new chemistry files found. Everything is up to date.")
#     else:
#         print(f"\n🎉 Success! Created {files_processed_with_new_data} new Master Data version(s) in the '{output_dir}' folder.")

# # --- RUN THE SCRIPT ---
# if __name__ == "__main__":
#     generate_sequential_master_versions()

# import pandas as pd
# import glob
# import os
# import re

# def generate_sequential_master_versions():
#     print("🔍 Scanning folder for chemistry files and existing Master Data...\n")
    
#     # --- FOLDER CONFIGURATION ---
#     input_dir = 'xrf_data'
#     output_dir = 'master_data'
#     site_db_file = 'XRF Site Analysis Database W SampleID(Sheet1).csv' # The file you just attached
    
#     # Ensure the output folder exists
#     os.makedirs(output_dir, exist_ok=True)
    
#     # --- 1. LOAD THE SITE DATABASE (To Fetch Sample IDs) ---
#     site_sample_ids = []
#     if os.path.exists(site_db_file):
#         # We use header=1 because the actual column names start on the second row
#         # df_site = pd.read_csv(site_db_file, header=1)
#         df_site = pd.read_csv(site_db_file, header=1, encoding='latin1')
#         # Drop empty rows and convert the SampleID column to a clean list
#         site_sample_ids = df_site['SampleID'].dropna().tolist()
#         print(f"📖 Loaded Site Database: Found {len(site_sample_ids)} sequential Sample IDs to map.")
#     else:
#         print(f"⚠️ Warning: '{site_db_file}' not found. Sample IDs will remain blank.")
        
#     # --- 2. IDENTIFY THE LATEST MASTER VERSION ---
#     master_files = glob.glob(os.path.join(output_dir, 'Master_Data_v*.csv'))
    
#     existing_xrfids = set()
#     current_version = 0
    
#     if master_files:
#         def get_version_number(filename):
#             match = re.search(r'_v(\d+)\.csv', filename)
#             return int(match.group(1)) if match else 0
            
#         latest_master_file = max(master_files, key=get_version_number)
#         current_version = get_version_number(latest_master_file)
        
#         master_df = pd.read_csv(latest_master_file)
#         existing_xrfids = set(master_df['XRFID'].astype(str))
#         print(f"📂 Resuming from '{latest_master_file}' (Contains {len(master_df)} records).")
#     else:
#         master_df = pd.DataFrame(columns=['SampleID', 'XRFID', 'LeadPPM', 'LeadAvg'])
#         print(f"📂 No existing Master Data found in '{output_dir}'. Starting fresh from Version 1.")

#     # --- 3. GET ALL CHEMISTRY FILES AND SORT THEM ---
#     chem_files = sorted(glob.glob(os.path.join(input_dir, 'chemistry*.csv')))
    
#     if not chem_files:
#         print(f"⚠️ No chemistry files found in the '{input_dir}' folder. Please add some files.")
#         return

#     files_processed_with_new_data = 0

#     # --- 4. PROCESS EACH FILE ---
#     for file_path in chem_files:
#         try:
#             df = pd.read_csv(file_path)
            
#             # Create the unique ID
#             df['Date_dt'] = pd.to_datetime(df['Date'])
#             df['Date_Str'] = df['Date_dt'].dt.strftime('%b %d')
#             df['XRFID'] = df['Date_Str'] + '-' + df['Reading #'].astype(str)
            
#             # Extract Lead
#             if 'Pb Concentration' in df.columns:
#                 df['LeadPPM'] = df['Pb Concentration']
#             else:
#                 df['LeadPPM'] = pd.NA 
                
#             # Placeholders
#             df['SampleID'] = "" 
#             df['LeadAvg'] = "" 
            
#             clean_df = df[['SampleID', 'XRFID', 'LeadPPM', 'LeadAvg']]
            
#             # FILTER: Find rows from THIS chemistry file that aren't in the Master yet
#             new_rows = clean_df[~clean_df['XRFID'].isin(existing_xrfids)]
            
#             if not new_rows.empty:
#                 existing_xrfids.update(new_rows['XRFID'].tolist())
#                 master_df = pd.concat([master_df, new_rows], ignore_index=True)
                
#                 # ==========================================
#                 # NEW LOGIC: MAP SAMPLE IDs & CALCULATE AVG
#                 # ==========================================
                
#                 # 1. Map the Sample IDs sequentially from the Site Database
#                 # We only map up to the number of rows currently in our master_df
#                 current_length = len(master_df)
#                 mapped_ids = site_sample_ids[:current_length] 
                
#                 # If we have more chemistry readings than Sample IDs in the database, pad with blanks
#                 if len(mapped_ids) < current_length:
#                     mapped_ids.extend([""] * (current_length - len(mapped_ids)))
                    
#                 master_df['SampleID'] = mapped_ids
                
#                 # 2. Calculate Average Lead for each Sample ID
#                 # Convert LeadPPM to numeric just in case there are strings/errors
#                 master_df['LeadPPM_Numeric'] = pd.to_numeric(master_df['LeadPPM'], errors='coerce')
                
#                 # Calculate the mean per SampleID
#                 master_df['LeadAvg'] = master_df.groupby('SampleID')['LeadPPM_Numeric'].transform('mean')
                
#                 # Only keep the average on the FIRST row of each SampleID (mimicking your Master Key file)
#                 # We ignore rows where SampleID is blank
#                 duplicates = master_df.duplicated('SampleID')
#                 master_df.loc[duplicates | (master_df['SampleID'] == ""), 'LeadAvg'] = ""
                
#                 # Drop the temporary numeric column we used for the math
#                 master_df = master_df.drop(columns=['LeadPPM_Numeric'])
#                 # ==========================================

#                 # Increment the version number and save
#                 current_version += 1
#                 output_filename = os.path.join(output_dir, f'Master_Data_v{current_version}.csv')
                
#                 master_df.to_csv(output_filename, index=False)
                
#                 print(f"✅ Processed {os.path.basename(file_path)}: Added {len(new_rows)} new readings.")
#                 print(f"   💾 Created {output_filename}")
                
#                 files_processed_with_new_data += 1
#             else:
#                 print(f"⏭️ Skipped {os.path.basename(file_path)}: Data already exists in Master.")
                
#         except Exception as e:
#             print(f"⚠️ Error reading {file_path}: {e}")

#     # --- 5. FINAL SUMMARY ---
#     if files_processed_with_new_data == 0:
#         print("\n✅ Check complete. No new chemistry files found. Everything is up to date.")
#     else:
#         print(f"\n🎉 Success! Created {files_processed_with_new_data} new Master Data version(s).")

# # --- RUN THE SCRIPT ---
# if __name__ == "__main__":
#     generate_sequential_master_versions()

import pandas as pd
import glob
import os
import re

def generate_sequential_master_versions():
    print("🔍 Scanning folder for chemistry files and existing Master Data...\n")
    
    # --- NEW FILE STRUCTURE CONFIGURATION ---
    # Since this script lives in /src, we use '..' to go up one level to the main folder
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    input_dir = os.path.join(base_dir, 'data', 'xrf_data')
    output_dir = os.path.join(base_dir, 'data', 'master_data')
    site_db_file = os.path.join(base_dir, 'data', 'site_databases', 'XRF Site Analysis Database W SampleID(Sheet1).csv')
    
    # Ensure the output folders exist
    os.makedirs(output_dir, exist_ok=True)
    
    # --- 1. LOAD THE SITE DATABASE ---
    site_sample_ids = []
    if os.path.exists(site_db_file):
        # Using latin1 encoding to prevent the UnicodeDecodeError we saw earlier
        df_site = pd.read_csv(site_db_file, header=1, encoding='latin1')
        site_sample_ids = df_site['SampleID'].dropna().tolist()
        print(f"📖 Loaded Site Database: Found {len(site_sample_ids)} sequential Sample IDs to map.")
    else:
        print(f"⚠️ Warning: '{site_db_file}' not found. Sample IDs will remain blank.")
        
    # --- 2. IDENTIFY THE LATEST MASTER VERSION ---
    master_files = glob.glob(os.path.join(output_dir, 'Master_Data_v*.csv'))
    
    existing_xrfids = set()
    current_version = 0
    
    if master_files:
        def get_version_number(filename):
            match = re.search(r'_v(\d+)\.csv', filename)
            return int(match.group(1)) if match else 0
            
        latest_master_file = max(master_files, key=get_version_number)
        current_version = get_version_number(latest_master_file)
        
        master_df = pd.read_csv(latest_master_file)
        existing_xrfids = set(master_df['XRFID'].astype(str))
        print(f"📂 Resuming from '{os.path.basename(latest_master_file)}' (Contains {len(master_df)} records).")
    else:
        master_df = pd.DataFrame(columns=['SampleID', 'XRFID', 'LeadPPM', 'LeadAvg'])
        print(f"📂 No existing Master Data found. Starting fresh from Version 1.")

    # --- 3. GET ALL CHEMISTRY FILES AND SORT THEM ---
    chem_files = sorted(glob.glob(os.path.join(input_dir, 'chemistry*.csv')))
    
    if not chem_files:
        print(f"⚠️ No chemistry files found in '{input_dir}'. Please add some files.")
        return

    files_processed_with_new_data = 0

    # --- 4. PROCESS EACH FILE ---
    for file_path in chem_files:
        try:
            df = pd.read_csv(file_path)
            
            df['Date_dt'] = pd.to_datetime(df['Date'])
            df['Date_Str'] = df['Date_dt'].dt.strftime('%b %d')
            df['XRFID'] = df['Date_Str'] + '-' + df['Reading #'].astype(str)
            
            if 'Pb Concentration' in df.columns:
                df['LeadPPM'] = df['Pb Concentration']
            else:
                df['LeadPPM'] = pd.NA 
                
            df['SampleID'] = "" 
            df['LeadAvg'] = "" 
            
            clean_df = df[['SampleID', 'XRFID', 'LeadPPM', 'LeadAvg']]
            new_rows = clean_df[~clean_df['XRFID'].isin(existing_xrfids)]
            
            if not new_rows.empty:
                existing_xrfids.update(new_rows['XRFID'].tolist())
                master_df = pd.concat([master_df, new_rows], ignore_index=True)
                
                # MAP SAMPLE IDs & CALCULATE AVG
                current_length = len(master_df)
                mapped_ids = site_sample_ids[:current_length] 
                
                if len(mapped_ids) < current_length:
                    mapped_ids.extend([""] * (current_length - len(mapped_ids)))
                    
                master_df['SampleID'] = mapped_ids
                
                master_df['LeadPPM_Numeric'] = pd.to_numeric(master_df['LeadPPM'], errors='coerce')
                master_df['LeadAvg'] = master_df.groupby('SampleID')['LeadPPM_Numeric'].transform('mean')
                
                duplicates = master_df.duplicated('SampleID')
                master_df.loc[duplicates | (master_df['SampleID'] == ""), 'LeadAvg'] = ""
                master_df = master_df.drop(columns=['LeadPPM_Numeric'])

                current_version += 1
                output_filename = os.path.join(output_dir, f'Master_Data_v{current_version}.csv')
                master_df.to_csv(output_filename, index=False)
                
                print(f"✅ Processed {os.path.basename(file_path)}: Added {len(new_rows)} new readings.")
                print(f"   💾 Created {os.path.basename(output_filename)} in data/master_data/")
                
                files_processed_with_new_data += 1
            else:
                print(f"⏭️ Skipped {os.path.basename(file_path)}: Data already exists in Master.")
                
        except Exception as e:
            print(f"⚠️ Error reading {os.path.basename(file_path)}: {e}")

    # --- 5. FINAL SUMMARY ---
    if files_processed_with_new_data == 0:
        print("\n✅ Check complete. No new chemistry files found. Everything is up to date.")
    else:
        print(f"\n🎉 Success! Created {files_processed_with_new_data} new Master Data version(s).")

# --- RUN THE SCRIPT ---
if __name__ == "__main__":
    generate_sequential_master_versions()
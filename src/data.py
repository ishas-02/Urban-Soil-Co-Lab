# # import pandas as pd
# # import glob
# # import os
# # import re

# # def generate_sequential_master_versions():
# #     print("🔍 Scanning folder for chemistry files and existing Master Data...\n")
    
# #     # --- NEW FILE STRUCTURE CONFIGURATION ---
# #     # Since this script lives in /src, we use '..' to go up one level to the main folder
# #     base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
# #     input_dir = os.path.join(base_dir, 'data', 'xrf_data')
# #     output_dir = os.path.join(base_dir, 'data', 'master_data')
# #     site_db_file = os.path.join(base_dir, 'data', 'site_databases', 'XRF Site Analysis Database W SampleID(Sheet1).csv')
    
# #     # Ensure the output folders exist
# #     os.makedirs(output_dir, exist_ok=True)
    
# #     # --- 1. LOAD THE SITE DATABASE ---
# #     site_sample_ids = []
# #     if os.path.exists(site_db_file):
# #         # Using latin1 encoding to prevent the UnicodeDecodeError we saw earlier
# #         df_site = pd.read_csv(site_db_file, header=1, encoding='latin1')
# #         site_sample_ids = df_site['SampleID'].dropna().tolist()
# #         print(f"📖 Loaded Site Database: Found {len(site_sample_ids)} sequential Sample IDs to map.")
# #     else:
# #         print(f"⚠️ Warning: '{site_db_file}' not found. Sample IDs will remain blank.")
        
# #     # --- 2. IDENTIFY THE LATEST MASTER VERSION ---
# #     master_files = glob.glob(os.path.join(output_dir, 'Master_Data_v*.csv'))
    
# #     existing_xrfids = set()
# #     current_version = 0
    
# #     if master_files:
# #         def get_version_number(filename):
# #             match = re.search(r'_v(\d+)\.csv', filename)
# #             return int(match.group(1)) if match else 0
            
# #         latest_master_file = max(master_files, key=get_version_number)
# #         current_version = get_version_number(latest_master_file)
        
# #         master_df = pd.read_csv(latest_master_file)
# #         existing_xrfids = set(master_df['XRFID'].astype(str))
# #         print(f"📂 Resuming from '{os.path.basename(latest_master_file)}' (Contains {len(master_df)} records).")
# #     else:
# #         master_df = pd.DataFrame(columns=['SampleID', 'XRFID', 'LeadPPM', 'LeadAvg'])
# #         print(f"📂 No existing Master Data found. Starting fresh from Version 1.")

# #     # --- 3. GET ALL CHEMISTRY FILES AND SORT THEM ---
# #     chem_files = sorted(glob.glob(os.path.join(input_dir, 'chemistry*.csv')))
    
# #     if not chem_files:
# #         print(f"⚠️ No chemistry files found in '{input_dir}'. Please add some files.")
# #         return

# #     files_processed_with_new_data = 0

# #     # --- 4. PROCESS EACH FILE ---
# #     for file_path in chem_files:
# #         try:
# #             df = pd.read_csv(file_path)
            
# #             df['Date_dt'] = pd.to_datetime(df['Date'])
# #             df['Date_Str'] = df['Date_dt'].dt.strftime('%b %d')
# #             df['XRFID'] = df['Date_Str'] + '-' + df['Reading #'].astype(str)
            
# #             if 'Pb Concentration' in df.columns:
# #                 df['LeadPPM'] = df['Pb Concentration']
# #             else:
# #                 df['LeadPPM'] = pd.NA 
                
# #             df['SampleID'] = "" 
# #             df['LeadAvg'] = "" 
            
# #             clean_df = df[['SampleID', 'XRFID', 'LeadPPM', 'LeadAvg']]
# #             new_rows = clean_df[~clean_df['XRFID'].isin(existing_xrfids)]
            
# #             if not new_rows.empty:
# #                 existing_xrfids.update(new_rows['XRFID'].tolist())
# #                 master_df = pd.concat([master_df, new_rows], ignore_index=True)
                
# #                 # MAP SAMPLE IDs & CALCULATE AVG
# #                 current_length = len(master_df)
# #                 mapped_ids = site_sample_ids[:current_length] 
                
# #                 if len(mapped_ids) < current_length:
# #                     mapped_ids.extend([""] * (current_length - len(mapped_ids)))
                    
# #                 master_df['SampleID'] = mapped_ids
                
# #                 master_df['LeadPPM_Numeric'] = pd.to_numeric(master_df['LeadPPM'], errors='coerce')
# #                 master_df['LeadAvg'] = master_df.groupby('SampleID')['LeadPPM_Numeric'].transform('mean')
                
# #                 duplicates = master_df.duplicated('SampleID')
# #                 master_df.loc[duplicates | (master_df['SampleID'] == ""), 'LeadAvg'] = ""
# #                 master_df = master_df.drop(columns=['LeadPPM_Numeric'])

# #                 current_version += 1
# #                 output_filename = os.path.join(output_dir, f'Master_Data_v{current_version}.csv')
# #                 master_df.to_csv(output_filename, index=False)
                
# #                 print(f"✅ Processed {os.path.basename(file_path)}: Added {len(new_rows)} new readings.")
# #                 print(f"   💾 Created {os.path.basename(output_filename)} in data/master_data/")
                
# #                 files_processed_with_new_data += 1
# #             else:
# #                 print(f"⏭️ Skipped {os.path.basename(file_path)}: Data already exists in Master.")
                
# #         except Exception as e:
# #             print(f"⚠️ Error reading {os.path.basename(file_path)}: {e}")

# #     # --- 5. FINAL SUMMARY ---
# #     if files_processed_with_new_data == 0:
# #         print("\n✅ Check complete. No new chemistry files found. Everything is up to date.")
# #     else:
# #         print(f"\n🎉 Success! Created {files_processed_with_new_data} new Master Data version(s).")

# # # --- RUN THE SCRIPT ---
# # if __name__ == "__main__":
# #     generate_sequential_master_versions()

# """
# data.py — GroundSense ETL Pipeline

# Processes raw chemistry CSV files from the XRF instrument and produces
# versioned Master Data files.

# KEY DESIGN:
#   The XRF Master Data Key (maintained manually) is the authoritative
#   mapping from XRFID → SampleID.  Only readings whose XRFID appears
#   in the key are included in the output.  This filters out:
#     - Readings from other projects that share the same instrument
#     - Calibration / test readings
#     - Duplicate chemistry file uploads (-1 / -2 copies)

# Directory layout (relative to repo root):
#   data/xrf_data/                ← raw chemistry CSVs
#   data/master_data/             ← versioned Master_Data_v*.csv output
#   data/site_databases/          ← XRF Master Data Key CSV
# """

# import pandas as pd
# import glob
# import os
# import re


# def generate_sequential_master_versions():
#     print("🔍 Scanning folder for chemistry files and existing Master Data...\n")

#     # ── Folder configuration ──
#     base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
#     input_dir    = os.path.join(base_dir, 'data', 'xrf_data')
#     output_dir   = os.path.join(base_dir, 'data', 'master_data')
#     key_file     = os.path.join(
#         base_dir, 'data', 'site_databases',
#         'XRF Master Data KEY (Experimental Formatting) 1-14-2025(Sheet1).csv'
#     )
#     # Fallback filename variants (in case the file is named differently)
#     key_file_alt = os.path.join(
#         base_dir, 'data', 'site_databases',
#         'XRF_Master_Data_KEY__Experimental_Formatting__1-14-2025_Sheet1_.csv'
#     )

#     os.makedirs(output_dir, exist_ok=True)

#     # ── 1. Load the XRF Master Data Key ──
#     # This file is the single source of truth for XRFID → SampleID mapping.
#     key_path = key_file if os.path.exists(key_file) else key_file_alt
#     if not os.path.exists(key_path):
#         # Try to find any key file in the directory
#         key_candidates = glob.glob(os.path.join(
#             base_dir, 'data', 'site_databases', 'XRF*Master*Data*KEY*.*csv'
#         ))
#         if key_candidates:
#             key_path = key_candidates[0]

#     if os.path.exists(key_path):
#         key_df = pd.read_csv(key_path, encoding='latin1')
#         # Normalise column names (strip whitespace)
#         key_df.columns = key_df.columns.str.strip()
#         print(f"📖 Loaded XRF Master Data Key: {len(key_df)} entries "
#               f"({key_df['SampleID'].nunique()} unique SampleIDs) "
#               f"from {os.path.basename(key_path)}")

#         # Build the XRFID → row mapping (keeps SampleID, LeadPPM from key
#         # but we'll overwrite LeadPPM with actual instrument data)
#         valid_xrfids = set(key_df['XRFID'].dropna().astype(str).unique())

#         # Build lookup: XRFID → SampleID
#         xrfid_to_sample = dict(zip(
#             key_df['XRFID'].dropna().astype(str),
#             key_df['SampleID'].dropna().astype(str),
#         ))
#     else:
#         print(f"⚠️  XRF Master Data Key not found. "
#               f"Looked in: {os.path.dirname(key_file)}")
#         print("   Without the key, no SampleID mapping or filtering is possible.")
#         print("   Place the key CSV in data/site_databases/")
#         valid_xrfids = None
#         xrfid_to_sample = {}

#     # ── 2. Find the latest existing Master Data version ──
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
#         print(f"📂 Resuming from '{os.path.basename(latest_master_file)}' "
#               f"({len(master_df)} records).")
#     else:
#         master_df = pd.DataFrame(
#             columns=['SampleID', 'XRFID', 'LeadPPM', 'LeadAvg']
#         )
#         print("📂 No existing Master Data found. Starting fresh from v1.")

#     # ── 3. Gather and sort chemistry files ──
#     chem_files = sorted(glob.glob(os.path.join(input_dir, 'chemistry*.csv')))
#     if not chem_files:
#         print(f"⚠️  No chemistry files found in '{input_dir}'.")
#         return

#     print(f"📄 Found {len(chem_files)} chemistry file(s) to process.\n")

#     files_processed_with_new_data = 0

#     # ── 4. Process each chemistry file ──
#     for file_path in chem_files:
#         try:
#             raw = pd.read_csv(file_path, encoding='latin1')

#             # Select only needed columns early to avoid fragmentation
#             # on 300+ column chemistry files
#             needed_cols = ['Date', 'Reading #']
#             if 'Pb Concentration' in raw.columns:
#                 needed_cols.append('Pb Concentration')
#             df = raw[needed_cols].copy()

#             # Build XRFID: "Mon DD-ReadingNum"  (e.g. "Oct 31-4")
#             df['Date_dt'] = pd.to_datetime(df['Date'])
#             df['XRFID'] = (df['Date_dt'].dt.strftime('%b %d')
#                            + '-' + df['Reading #'].astype(str))

#             # Extract Lead PPM
#             if 'Pb Concentration' in df.columns:
#                 df['LeadPPM'] = df['Pb Concentration']
#             else:
#                 df['LeadPPM'] = pd.NA

#             # ── Filter: only keep readings that exist in the key ──
#             if valid_xrfids is not None:
#                 before = len(df)
#                 df = df[df['XRFID'].isin(valid_xrfids)]
#                 filtered = before - len(df)
#                 if filtered > 0:
#                     print(f"   🔒 Filtered {filtered} non-project reading(s) "
#                           f"from {os.path.basename(file_path)}")

#             # ── Deduplicate: skip XRFIDs already in master ──
#             df = df[~df['XRFID'].isin(existing_xrfids)]

#             if df.empty:
#                 print(f"⏭️  Skipped {os.path.basename(file_path)}: "
#                       "no new project readings.")
#                 continue

#             # ── Map SampleID from the key (not positional!) ──
#             df['SampleID'] = df['XRFID'].astype(str).map(xrfid_to_sample)
#             df['SampleID'] = df['SampleID'].where(df['SampleID'].notna(), "")

#             # Select output columns
#             clean_df = df[['SampleID', 'XRFID', 'LeadPPM']].copy()
#             clean_df['LeadAvg'] = ""
#             # Ensure all columns are standard Python types
#             clean_df['SampleID'] = clean_df['SampleID'].astype(str)
#             clean_df['XRFID'] = clean_df['XRFID'].astype(str)

#             # Track processed XRFIDs
#             existing_xrfids.update(clean_df['XRFID'].tolist())

#             # Append to master
#             master_df = pd.concat([master_df, clean_df], ignore_index=True)

#             # ── Recalculate LeadAvg per SampleID ──
#             master_df['LeadPPM_Numeric'] = pd.to_numeric(
#                 master_df['LeadPPM'], errors='coerce'
#             )
#             avgs = master_df.groupby('SampleID')['LeadPPM_Numeric'].transform(
#                 'mean'
#             )
#             master_df['LeadAvg'] = ""
#             # Show average only on the first row of each SampleID group
#             first_mask = ~master_df.duplicated('SampleID')
#             has_id = master_df['SampleID'].notna() & (master_df['SampleID'] != "")
#             # Convert float averages to strings for assignment into str column
#             master_df.loc[first_mask & has_id, 'LeadAvg'] = (
#                 avgs[first_mask & has_id].round(1).astype(str)
#             )
#             master_df.drop(columns=['LeadPPM_Numeric'], inplace=True)

#             # ── Save new version ──
#             current_version += 1
#             output_filename = os.path.join(
#                 output_dir, f'Master_Data_v{current_version}.csv'
#             )
#             master_df.to_csv(output_filename, index=False)

#             print(f"✅ Processed {os.path.basename(file_path)}: "
#                   f"added {len(clean_df)} readings.")
#             print(f"   💾 Created {os.path.basename(output_filename)}")

#             files_processed_with_new_data += 1

#         except Exception as e:
#             print(f"⚠️  Error reading {os.path.basename(file_path)}: {e}")

#     # ── 5. Summary ──
#     if files_processed_with_new_data == 0:
#         print("\n✅ No new project readings found. Everything is up to date.")
#     else:
#         print(f"\n🎉 Success! Processed {files_processed_with_new_data} file(s). "
#               f"Master Data now at v{current_version} "
#               f"with {len(master_df)} total records.")


# # --- RUN THE SCRIPT ---
# if __name__ == "__main__":
#     generate_sequential_master_versions()

"""
data.py — GroundSense ETL Pipeline

Processes raw chemistry CSV files from the XRF instrument and produces
versioned Master Data files.

KEY DESIGN:
  The XRF Master Data Key (maintained manually) is the authoritative
  mapping from XRFID → SampleID.  Only readings whose XRFID appears
  in the key are included in the output.  This filters out:
    - Readings from other projects that share the same instrument
    - Calibration / test readings
    - Duplicate chemistry file uploads (-1 / -2 copies)

Directory layout (relative to repo root):
  data/xrf_data/                ← raw chemistry CSVs
  data/master_data/             ← versioned Master_Data_v*.csv output
  data/site_databases/          ← XRF Master Data Key CSV
"""

import pandas as pd
import glob
import os
import re


def generate_sequential_master_versions():
    print("🔍 Scanning folder for chemistry files and existing Master Data...\n")

    # ── Folder configuration ──
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    input_dir    = os.path.join(base_dir, 'data', 'xrf_data')
    output_dir   = os.path.join(base_dir, 'data', 'master_data')
    key_file     = os.path.join(
        base_dir, 'data', 'site_databases',
        'XRF Master Data KEY (Experimental Formatting) 1-14-2025(Sheet1).csv'
    )
    # Fallback filename variants (in case the file is named differently)
    key_file_alt = os.path.join(
        base_dir, 'data', 'site_databases',
        'XRF_Master_Data_KEY__Experimental_Formatting__1-14-2025_Sheet1_.csv'
    )

    os.makedirs(output_dir, exist_ok=True)

    # ── 1. Load the XRF Master Data Key ──
    # This file is the single source of truth for XRFID → SampleID mapping.
    key_path = key_file if os.path.exists(key_file) else key_file_alt
    if not os.path.exists(key_path):
        # Try to find any key file in the directory
        key_candidates = glob.glob(os.path.join(
            base_dir, 'data', 'site_databases', 'XRF*Master*Data*KEY*.*csv'
        ))
        if key_candidates:
            key_path = key_candidates[0]

    if os.path.exists(key_path):
        key_df = pd.read_csv(key_path, encoding='latin1')
        # Normalise column names (strip whitespace)
        key_df.columns = key_df.columns.str.strip()
        print(f"📖 Loaded XRF Master Data Key: {len(key_df)} entries "
              f"({key_df['SampleID'].nunique()} unique SampleIDs) "
              f"from {os.path.basename(key_path)}")

        # Build the XRFID → row mapping (keeps SampleID, LeadPPM from key
        # but we'll overwrite LeadPPM with actual instrument data)
        valid_xrfids = set(key_df['XRFID'].dropna().astype(str).unique())

        # Build lookup: XRFID → SampleID
        xrfid_to_sample = dict(zip(
            key_df['XRFID'].dropna().astype(str),
            key_df['SampleID'].dropna().astype(str),
        ))
    else:
        print(f"⚠️  XRF Master Data Key not found. "
              f"Looked in: {os.path.dirname(key_file)}")
        print("   Without the key, no SampleID mapping or filtering is possible.")
        print("   Place the key CSV in data/site_databases/")
        valid_xrfids = None
        xrfid_to_sample = {}

    # ── 2. Find the latest existing Master Data version ──
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
        print(f"📂 Resuming from '{os.path.basename(latest_master_file)}' "
              f"({len(master_df)} records).")
    else:
        master_df = pd.DataFrame(
            columns=['SampleID', 'XRFID', 'LeadPPM', 'LeadAvg']
        )
        print("📂 No existing Master Data found. Starting fresh from v1.")

    # ── 3. Gather and sort chemistry files ──
    chem_files = sorted(glob.glob(os.path.join(input_dir, 'chemistry*.csv')))
    if not chem_files:
        print(f"⚠️  No chemistry files found in '{input_dir}'.")
        return

    print(f"📄 Found {len(chem_files)} chemistry file(s) to process.\n")

    files_processed_with_new_data = 0

    # ── 4. Process each chemistry file ──
    for file_path in chem_files:
        try:
            raw = pd.read_csv(file_path, encoding='latin1')

            # Select only needed columns early to avoid fragmentation
            # on 300+ column chemistry files
            needed_cols = ['Date', 'Reading #']
            if 'Pb Concentration' in raw.columns:
                needed_cols.append('Pb Concentration')
            df = raw[needed_cols].copy()

            # Build XRFID: "Mon DD-ReadingNum"  (e.g. "Oct 31-4")
            df['Date_dt'] = pd.to_datetime(df['Date'])
            df['XRFID'] = (df['Date_dt'].dt.strftime('%b %d')
                           + '-' + df['Reading #'].astype(str))

            # Extract Lead PPM
            if 'Pb Concentration' in df.columns:
                df['LeadPPM'] = df['Pb Concentration']
            else:
                df['LeadPPM'] = pd.NA

            # ── Filter: only keep readings that exist in the key ──
            if valid_xrfids is not None:
                before = len(df)
                df = df[df['XRFID'].isin(valid_xrfids)]
                filtered = before - len(df)
                if filtered > 0:
                    print(f"   🔒 Filtered {filtered} non-project reading(s) "
                          f"from {os.path.basename(file_path)}")

            # ── Deduplicate: skip XRFIDs already in master ──
            df = df[~df['XRFID'].isin(existing_xrfids)]

            if df.empty:
                print(f"⏭️  Skipped {os.path.basename(file_path)}: "
                      "no new project readings.")
                continue

            # ── Map SampleID from the key (not positional!) ──
            df['SampleID'] = df['XRFID'].astype(str).map(xrfid_to_sample)
            df['SampleID'] = df['SampleID'].where(df['SampleID'].notna(), "")

            # Select output columns
            clean_df = df[['SampleID', 'XRFID', 'LeadPPM']].copy()
            clean_df['LeadAvg'] = ""
            # Ensure all columns are standard Python types
            clean_df['SampleID'] = clean_df['SampleID'].astype(str)
            clean_df['XRFID'] = clean_df['XRFID'].astype(str)

            # Track processed XRFIDs
            existing_xrfids.update(clean_df['XRFID'].tolist())

            # Append to master
            master_df = pd.concat([master_df, clean_df], ignore_index=True)

            # ── Recalculate LeadAvg per SampleID ──
            master_df['LeadPPM_Numeric'] = pd.to_numeric(
                master_df['LeadPPM'], errors='coerce'
            )
            avgs = master_df.groupby('SampleID')['LeadPPM_Numeric'].transform(
                'mean'
            )
            master_df['LeadAvg'] = ""
            # Show average only on the first row of each SampleID group
            first_mask = ~master_df.duplicated('SampleID')
            has_id = master_df['SampleID'].notna() & (master_df['SampleID'] != "")
            # Convert float averages to strings for assignment into str column
            master_df.loc[first_mask & has_id, 'LeadAvg'] = (
                avgs[first_mask & has_id].round(1).astype(str)
            )
            master_df.drop(columns=['LeadPPM_Numeric'], inplace=True)

            # ── Save new version ──
            current_version += 1
            output_filename = os.path.join(
                output_dir, f'Master_Data_v{current_version}.csv'
            )
            master_df.to_csv(output_filename, index=False)

            print(f"✅ Processed {os.path.basename(file_path)}: "
                  f"added {len(clean_df)} readings.")
            print(f"   💾 Created {os.path.basename(output_filename)}")

            files_processed_with_new_data += 1

        except Exception as e:
            print(f"⚠️  Error reading {os.path.basename(file_path)}: {e}")

    # ── 5. Summary ──
    if files_processed_with_new_data == 0:
        print("\n✅ No new project readings found. Everything is up to date.")
    else:
        print(f"\n🎉 Success! Processed {files_processed_with_new_data} file(s). "
              f"Master Data now at v{current_version} "
              f"with {len(master_df)} total records.")


# --- RUN THE SCRIPT ---
if __name__ == "__main__":
    generate_sequential_master_versions()
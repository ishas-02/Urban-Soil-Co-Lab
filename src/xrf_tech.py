# # import streamlit as st
# # import pandas as pd
# # from datetime import date

# # # --- PAGE CONFIGURATION ---
# # # (This must always be the first Streamlit command)
# # st.set_page_config(page_title="XRF Technician QA/QC Form", page_icon="🧪", layout="centered")

# # # --- SECURITY GATEKEEPER ---
# # def check_password():
# #     """Returns `True` if the user entered the correct password."""
    
# #     def password_entered():
# #         # Checks the entered password against the secret password
# #         if st.session_state["password"] == st.secrets["lab_password"]:
# #             st.session_state["password_correct"] = True
# #             del st.session_state["password"]  # Clear from memory
# #         else:
# #             st.session_state["password_correct"] = False

# #     if "password_correct" not in st.session_state:
# #         st.markdown("### 🔒 GroundSense Tech Portal Login")
# #         st.text_input("Enter Technician Password", type="password", on_change=password_entered, key="password")
# #         return False
        
# #     elif not st.session_state["password_correct"]:
# #         st.markdown("### 🔒 GroundSense Tech Portal Login")
# #         st.text_input("Enter Technician Password", type="password", on_change=password_entered, key="password")
# #         st.error("🚫 Incorrect password. Please try again.")
# #         return False
        
# #     else:
# #         return True

# # # --- STOP THE APP IF NOT LOGGED IN ---
# # if not check_password():
# #     st.stop()

# # # ==========================================
# # # MAIN DASHBOARD CODE (ONLY RUNS IF UNLOCKED)
# # # ==========================================

# # st.title("🧪 XRF Lab Technician Portal")
# # st.markdown("Enter your sample readings below. The system will automatically calculate variance and prompt for a third reading if the discrepancy is too high.")
# # st.markdown("---")

# # # --- SETTINGS ---
# # # Usually, environmental labs use a 20% Relative Percent Difference (RPD) as the threshold.
# # # You can hide this in a sidebar so only the admin can change it.
# # st.sidebar.header("Lab Configuration")
# # variance_threshold = st.sidebar.number_input("Max Allowed Discrepancy (%)", value=20.0, step=1.0)

# # # --- DATA ENTRY FORM ---
# # with st.form("xrf_entry_form"):
# #     st.subheader("Sample Information")
# #     col_date, col_id = st.columns(2)
# #     with col_date:
# #         test_date = st.date_input("Test Date", value=date.today())
# #     with col_id:
# #         sample_id = st.text_input("Sample ID (e.g., A1_PITT)", placeholder="Scan or type Sample ID")
        
# #     st.subheader("XRF Readings (Lead ppm)")
# #     col1, col2 = st.columns(2)
    
# #     with col1:
# #         test1 = st.number_input("Reading 1", min_value=0.0, step=1.0, format="%.1f")
# #     with col2:
# #         test2 = st.number_input("Reading 2", min_value=0.0, step=1.0, format="%.1f")
        
# #     # We use a submit button to process the logic
# #     submitted = st.form_submit_button("Analyze Variance", type="primary")

# # # --- LOGIC & ALERTS ---
# # if submitted:
# #     if sample_id.strip() == "":
# #         st.error("⚠️ Please enter a Sample ID before proceeding.")
# #     elif test1 > 0 and test2 > 0:
# #         # Calculate the Average and Relative Percent Difference (RPD)
# #         avg = (test1 + test2) / 2
# #         diff = abs(test1 - test2)
# #         rpd = (diff / avg) * 100 if avg > 0 else 0
        
# #         st.markdown("### 📊 Analysis Results")
        
# #         # Display the metrics nicely
# #         m1, m2, m3 = st.columns(3)
# #         m1.metric("Current Average", f"{avg:.1f} ppm")
# #         m2.metric("Difference", f"{diff:.1f} ppm")
# #         m3.metric("Variance (RPD)", f"{rpd:.1f}%", delta=f"Limit: {variance_threshold}%", delta_color="inverse")
        
# #         if rpd > variance_threshold:
# #             # 🚨 DISCREPANCY TOO HIGH - Trigger Test 3
# #             st.warning(f"⚠️ **High Variance Detected!** The discrepancy is {rpd:.1f}%, which exceeds the {variance_threshold}% limit.")
# #             st.info("👇 Please run a third test on this sample to stabilize the data.")
            
# #             # We use a second form specifically for the third reading
# #             with st.form("test3_form"):
# #                 test3 = st.number_input("Reading 3", min_value=0.0, step=1.0, format="%.1f")
# #                 submit_test3 = st.form_submit_button("Submit 3rd Reading & Save")
                
# #                 if submit_test3:
# #                     final_avg = (test1 + test2 + test3) / 3
# #                     st.success(f"✅ All 3 readings saved. Final Average: **{final_avg:.1f} ppm**")
# #                     # Here is where we would write the data to your CSV or database
# #         else:
# #             # ✅ DATA IS GOOD
# #             st.success("✅ Variance is within acceptable lab limits. Data is good to save!")
# #             # Here is where we would write the data to your CSV or database

# import streamlit as st
# import pandas as pd
# from datetime import date
# import itertools

# # --- PAGE CONFIGURATION ---
# st.set_page_config(page_title="XRF Technician QA/QC Form", page_icon="🧪", layout="centered")

# # --- SECURITY GATEKEEPER (SINGLE PASSWORD MODE) ---
# def check_password():
#     def password_entered():
#         if st.session_state["password"] == st.secrets["lab_password"]:
#             st.session_state["password_correct"] = True
#             del st.session_state["password"] 
#         else:
#             st.session_state["password_correct"] = False

#     if "password_correct" not in st.session_state:
#         st.markdown("### 🔒 GroundSense Tech Portal Login")
#         st.text_input("Enter Lab Password", type="password", on_change=password_entered, key="password")
#         return False
#     elif not st.session_state["password_correct"]:
#         st.markdown("### 🔒 GroundSense Tech Portal Login")
#         st.text_input("Enter Lab Password", type="password", on_change=password_entered, key="password")
#         st.error("🚫 Incorrect password. Please try again.")
#         return False
#     else:
#         return True

# if not check_password():
#     st.stop()

# # ==========================================
# # MAIN DASHBOARD CODE (SMART CONSENSUS QA/QC)
# # ==========================================

# if "reading_count" not in st.session_state:
#     st.session_state.reading_count = 3  
# if "current_sample" not in st.session_state:
#     st.session_state.current_sample = ""

# st.title("🧪 XRF Lab Technician Portal")
# st.markdown("Enter your readings. The system evaluates both consecutive stability and overall cluster consensus to intelligently filter out machine flukes.")
# st.markdown("---")

# st.sidebar.header("Lab Configuration")
# variance_threshold = st.sidebar.number_input("Max Allowed Discrepancy (%)", value=20.0, step=1.0)

# # --- SAMPLE INFO ---
# col_date, col_id = st.columns(2)
# with col_date:
#     test_date = st.date_input("Test Date", value=date.today())
# with col_id:
#     sample_id = st.text_input("Sample ID", value=st.session_state.current_sample, placeholder="Scan or type Sample ID")
#     if sample_id != st.session_state.current_sample:
#         st.session_state.current_sample = sample_id
#         st.session_state.reading_count = 3
#         st.rerun()

# st.subheader("XRF Readings (Lead ppm)")

# # --- DYNAMIC INPUT GENERATION ---
# readings = []
# cols = st.columns(3)
# for i in range(st.session_state.reading_count):
#     col = cols[i % 3]
#     val = col.number_input(f"Reading {i+1}", min_value=0.0, step=1.0, format="%.1f", key=f"read_{i}")
#     readings.append(val)

# # --- SMART LOGIC ALGORITHM ---
# if st.button("Analyze Stability & Save", type="primary"):
#     if sample_id.strip() == "":
#         st.error("⚠️ Please enter a Sample ID before proceeding.")
#     elif any(r == 0 for r in readings):
#         st.error("⚠️ Please enter a value greater than 0 for all generated reading fields.")
#     else:
#         is_stable = False
#         success_message = ""
        
#         # 1. THE CONSECUTIVE CHECK (Are the last 2 readings matching?)
#         r_last = readings[-1]
#         r_prev = readings[-2]
#         avg_last_2 = (r_last + r_prev) / 2
#         rpd_last_2 = (abs(r_last - r_prev) / avg_last_2) * 100 if avg_last_2 > 0 else 0
        
#         if rpd_last_2 <= variance_threshold:
#             is_stable = True
#             success_message = f"Readings {len(readings)-1} and {len(readings)} stabilized perfectly."
            
#         # 2. THE CLUSTER CHECK (Are ANY 3 readings matching, ignoring outliers?)
#         if not is_stable and len(readings) >= 3:
#             # Look at all possible combinations of 3 readings
#             for combo in itertools.combinations(enumerate(readings, 1), 3):
#                 idx = [c[0] for c in combo] # Reading numbers (e.g., 1, 3, 4)
#                 vals = [c[1] for c in combo] # The actual ppm values
                
#                 max_v, min_v = max(vals), min(vals)
#                 avg_v = (max_v + min_v) / 2
#                 combo_rpd = (abs(max_v - min_v) / avg_v) * 100 if avg_v > 0 else 0
                
#                 if combo_rpd <= variance_threshold:
#                     is_stable = True
#                     success_message = f"Readings {idx[0]}, {idx[1]}, and {idx[2]} formed a stable consensus (ignoring outliers)."
#                     break

#         # --- DISPLAY RESULTS ---
#         current_avg = sum(readings) / len(readings)
#         st.markdown("### 📊 Analysis Results")
        
#         if not is_stable:
#             st.warning(f"⚠️ **No consensus found.** The current variance is still too erratic.")
#             st.session_state.reading_count += 1
#             st.info(f"👇 The machine requires a tie-breaker. Adding input for **Reading {st.session_state.reading_count}**...")
#             st.rerun()
#         else:
#             st.success(f"✅ **Sample Accepted!** {success_message}")
#             st.info(f"Final Average of all {len(readings)} readings: **{current_avg:.1f} ppm**")
            
#             # --- INSERT DATABASE SAVE LOGIC HERE ---
            
#             if st.button("Start Next Sample"):
#                 st.session_state.current_sample = ""
#                 st.session_state.reading_count = 3
#                 st.rerun()

import streamlit as st
import pandas as pd
from datetime import date
import itertools
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="XRF Technician QA/QC Form", page_icon="🧪", layout="centered")

# --- SECURITY GATEKEEPER (SINGLE PASSWORD MODE) ---
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["lab_password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"] 
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("### 🔒 GroundSense Tech Portal Login")
        st.text_input("Enter Lab Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.markdown("### 🔒 GroundSense Tech Portal Login")
        st.text_input("Enter Lab Password", type="password", on_change=password_entered, key="password")
        st.error("🚫 Incorrect password. Please try again.")
        return False
    else:
        return True

if not check_password():
    st.stop()

# ==========================================
# MAIN DASHBOARD CODE (SMART CONSENSUS QA/QC)
# ==========================================

if "reading_count" not in st.session_state:
    st.session_state.reading_count = 3  
if "current_sample" not in st.session_state:
    st.session_state.current_sample = ""

st.title("🧪 XRF Lab Technician Portal")
st.markdown("Enter your readings. The system evaluates both consecutive stability and overall cluster consensus to intelligently filter out machine flukes.")
st.markdown("---")

# --- SIDEBAR & DOWNLOAD BUTTON ---
st.sidebar.header("Lab Configuration")
variance_threshold = st.sidebar.number_input("Max Allowed Discrepancy (%)", value=20.0, step=1.0)

st.sidebar.markdown("---")
st.sidebar.subheader("📥 Data Export")
manual_file_path = os.path.join("Data", "manual_xrf_data", "Manual_Master_Data.csv")

if os.path.exists(manual_file_path):
    with open(manual_file_path, "rb") as file:
        st.sidebar.download_button(
            label="Download Manual Master Data",
            data=file,
            file_name="Manual_Master_Data.csv",
            mime="text/csv"
        )
else:
    st.sidebar.info("Manual Master Data will appear here after the first save.")

# --- SAMPLE INFO ---
col_date, col_id = st.columns(2)
with col_date:
    test_date = st.date_input("Test Date", value=date.today())
with col_id:
    sample_id = st.text_input("Sample ID", value=st.session_state.current_sample, placeholder="Scan or type Sample ID")
    if sample_id != st.session_state.current_sample:
        st.session_state.current_sample = sample_id
        st.session_state.reading_count = 3
        st.rerun()

st.subheader("XRF Readings (Lead ppm)")

# --- DYNAMIC INPUT GENERATION ---
readings = []
cols = st.columns(3)
for i in range(st.session_state.reading_count):
    col = cols[i % 3]
    val = col.number_input(f"Reading {i+1}", min_value=0.0, step=1.0, format="%.1f", key=f"read_{i}")
    readings.append(val)

# --- SMART LOGIC ALGORITHM ---
if st.button("Analyze Stability & Save", type="primary"):
    if sample_id.strip() == "":
        st.error("⚠️ Please enter a Sample ID before proceeding.")
    elif any(r == 0 for r in readings):
        st.error("⚠️ Please enter a value greater than 0 for all generated reading fields.")
    else:
        is_stable = False
        success_message = ""
        
        # 1. THE CONSECUTIVE CHECK
        r_last = readings[-1]
        r_prev = readings[-2]
        avg_last_2 = (r_last + r_prev) / 2
        rpd_last_2 = (abs(r_last - r_prev) / avg_last_2) * 100 if avg_last_2 > 0 else 0
        
        if rpd_last_2 <= variance_threshold:
            is_stable = True
            success_message = f"Readings {len(readings)-1} and {len(readings)} stabilized perfectly."
            
        # 2. THE CLUSTER CHECK
        if not is_stable and len(readings) >= 3:
            for combo in itertools.combinations(enumerate(readings, 1), 3):
                idx = [c[0] for c in combo] 
                vals = [c[1] for c in combo] 
                
                max_v, min_v = max(vals), min(vals)
                avg_v = (max_v + min_v) / 2
                combo_rpd = (abs(max_v - min_v) / avg_v) * 100 if avg_v > 0 else 0
                
                if combo_rpd <= variance_threshold:
                    is_stable = True
                    success_message = f"Readings {idx[0]}, {idx[1]}, and {idx[2]} formed a stable consensus (ignoring outliers)."
                    break

        # --- DISPLAY RESULTS ---
        current_avg = sum(readings) / len(readings)
        st.markdown("### 📊 Analysis Results")
        
        if not is_stable:
            st.warning(f"⚠️ **No consensus found.** The current variance is still too erratic.")
            st.session_state.reading_count += 1
            st.info(f"👇 The machine requires a tie-breaker. Adding input for **Reading {st.session_state.reading_count}**...")
            st.rerun()
        else:
            st.success(f"✅ **Sample Accepted!** {success_message}")
            st.info(f"Final Average of all {len(readings)} readings: **{current_avg:.1f} ppm**")
            
            # --- DATABASE SAVE LOGIC ---
            manual_dir = os.path.join("Data", "manual_xrf_data")
            os.makedirs(manual_dir, exist_ok=True)
            
            # Format data to match the main Master_Data.csv columns
            new_records = []
            date_str = test_date.strftime('%b %d')
            
            for idx, val in enumerate(readings):
                new_records.append({
                    "SampleID": sample_id,
                    "XRFID": f"Manual_{date_str}-{idx+1}",  # e.g., Manual_Oct 31-1
                    "LeadPPM": val,
                    "LeadAvg": current_avg if idx == 0 else "" # Only place average on the first row
                })
                
            df_new = pd.DataFrame(new_records)
            
            # Append to file
            if os.path.exists(manual_file_path):
                df_new.to_csv(manual_file_path, mode='a', header=False, index=False)
            else:
                df_new.to_csv(manual_file_path, mode='w', header=True, index=False)
                
            st.success("💾 **Data automatically saved to the Manual Master Data file.**")
            
            if st.button("Start Next Sample"):
                st.session_state.current_sample = ""
                st.session_state.reading_count = 3
                st.rerun()
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
if "data_mode" not in st.session_state:
    st.session_state.data_mode = "Site_Master_Data"

st.title("🧪 XRF Lab Technician Portal")
st.markdown("Enter your readings. The system evaluates both consecutive stability and overall cluster consensus to intelligently filter out machine flukes.")

# --- MODE SELECTOR ---
data_mode = st.selectbox(
    "Select Data Entry Mode", 
    ["Site_Master_Data", "Clinic_Master_Data"],
    index=0 if st.session_state.data_mode == "Site_Master_Data" else 1
)

# Reset sample tracking if mode changes
if data_mode != st.session_state.data_mode:
    st.session_state.data_mode = data_mode
    st.session_state.current_sample = ""
    st.session_state.reading_count = 3
    st.rerun()

st.markdown("---")

# --- DYNAMIC FILE PATHS ---
if data_mode == "Site_Master_Data":
    manual_file_path = os.path.join("Data", "Site_Master_Data_manual", "Site_Master_Data.csv")
    download_label = "Download Site Master Data"
    download_filename = "Site_Master_Data.csv"
else:
    manual_file_path = os.path.join("Data", "Clinic_Master_Data_manual", "Clinic_Master_Data.csv")
    download_label = "Download Clinic Master Data"
    download_filename = "Clinic_Master_Data.csv"

# --- SIDEBAR CONFIG (Download moved to bottom) ---
st.sidebar.header("Lab Configuration")
variance_threshold = st.sidebar.number_input("Max Allowed Discrepancy (%)", value=20.0, step=1.0)


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

# --- CLINIC-SPECIFIC FIELDS ---
if data_mode == "Clinic_Master_Data":
    st.subheader("Clinic Sample Details")
    col_clin1, col_clin2 = st.columns(2)
    
    with col_clin1:
        ph_val = st.number_input("pH", value=None, format="%.2f", placeholder="Enter pH value")
        moisture_level = st.radio("Moisture Level", ["Normal", "High moisture", "Low Moisture"], horizontal=True)
    with col_clin2:
        notes = st.text_area("Notes", placeholder="Add any specific sample observations here...", height=100)
    st.markdown("---")

# --- XRF READINGS ---
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
            os.makedirs(os.path.dirname(manual_file_path), exist_ok=True)
            
            new_records = []
            date_str = test_date.strftime('%b %d')
            
            for idx, val in enumerate(readings):
                if data_mode == "Clinic_Master_Data":
                    # Clinic Format
                    new_records.append({
                        "SampleID": sample_id,
                        "XRFID": f"Manual_{date_str}-{idx+1}", 
                        "Moisture Level": moisture_level if idx == 0 else "",
                        "pH": ph_val if idx == 0 and ph_val is not None else "",
                        "LeadPPM": val,
                        "LeadAvg": current_avg if idx == 0 else "",
                        "Notes": notes if idx == 0 else ""
                    })
                else:
                    # Site Format
                    new_records.append({
                        "SampleID": sample_id,
                        "XRFID": f"Manual_{date_str}-{idx+1}", 
                        "LeadPPM": val,
                        "LeadAvg": current_avg if idx == 0 else "" 
                    })
                
            df_new = pd.DataFrame(new_records)
            
            # Append to file
            if os.path.exists(manual_file_path):
                df_new.to_csv(manual_file_path, mode='a', header=False, index=False)
            else:
                df_new.to_csv(manual_file_path, mode='w', header=True, index=False)
                
            st.success(f"💾 **Data automatically saved to {data_mode} file.**")
            
            if st.button("Start Next Sample"):
                st.session_state.current_sample = ""
                st.session_state.reading_count = 3
                st.rerun()

# ==========================================
# SIDEBAR EXPORT (Moved to bottom to catch newly created files)
# ==========================================
st.sidebar.markdown("---")
st.sidebar.subheader("📥 Data Export")

if os.path.exists(manual_file_path):
    with open(manual_file_path, "rb") as file:
        st.sidebar.download_button(
            label=download_label,
            data=file.read(),
            file_name=download_filename,
            mime="text/csv"
        )
else:
    st.sidebar.info(f"{download_filename} will appear here after the first save.")
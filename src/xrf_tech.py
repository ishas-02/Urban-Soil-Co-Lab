# import streamlit as st
# import pandas as pd
# from datetime import date

# # --- PAGE CONFIGURATION ---
# st.set_page_config(page_title="XRF Technician QA/QC Form", page_icon="🧪", layout="centered")

# st.title("🧪 XRF Lab Technician Portal")
# st.markdown("Enter your sample readings below. The system will automatically calculate variance and prompt for a third reading if the discrepancy is too high.")
# st.markdown("---")

# # --- SETTINGS ---
# # Usually, environmental labs use a 20% Relative Percent Difference (RPD) as the threshold.
# # You can hide this in a sidebar so only the admin can change it.
# st.sidebar.header("Lab Configuration")
# variance_threshold = st.sidebar.number_input("Max Allowed Discrepancy (%)", value=20.0, step=1.0)

# # --- DATA ENTRY FORM ---
# with st.form("xrf_entry_form"):
#     st.subheader("Sample Information")
#     col_date, col_id = st.columns(2)
#     with col_date:
#         test_date = st.date_input("Test Date", value=date.today())
#     with col_id:
#         sample_id = st.text_input("Sample ID (e.g., A1_PITT)", placeholder="Scan or type Sample ID")
        
#     st.subheader("XRF Readings (Lead ppm)")
#     col1, col2 = st.columns(2)
    
#     with col1:
#         test1 = st.number_input("Reading 1", min_value=0.0, step=1.0, format="%.1f")
#     with col2:
#         test2 = st.number_input("Reading 2", min_value=0.0, step=1.0, format="%.1f")
        
#     # We use a submit button to process the logic
#     submitted = st.form_submit_button("Analyze Variance", type="primary")

# # --- LOGIC & ALERTS ---
# if submitted:
#     if sample_id.strip() == "":
#         st.error("⚠️ Please enter a Sample ID before proceeding.")
#     elif test1 > 0 and test2 > 0:
#         # Calculate the Average and Relative Percent Difference (RPD)
#         avg = (test1 + test2) / 2
#         diff = abs(test1 - test2)
#         rpd = (diff / avg) * 100 if avg > 0 else 0
        
#         st.markdown("### 📊 Analysis Results")
        
#         # Display the metrics nicely
#         m1, m2, m3 = st.columns(3)
#         m1.metric("Current Average", f"{avg:.1f} ppm")
#         m2.metric("Difference", f"{diff:.1f} ppm")
#         m3.metric("Variance (RPD)", f"{rpd:.1f}%", delta=f"Limit: {variance_threshold}%", delta_color="inverse")
        
#         if rpd > variance_threshold:
#             # 🚨 DISCREPANCY TOO HIGH - Trigger Test 3
#             st.warning(f"⚠️ **High Variance Detected!** The discrepancy is {rpd:.1f}%, which exceeds the {variance_threshold}% limit.")
#             st.info("👇 Please run a third test on this sample to stabilize the data.")
            
#             # We use a second form specifically for the third reading
#             with st.form("test3_form"):
#                 test3 = st.number_input("Reading 3", min_value=0.0, step=1.0, format="%.1f")
#                 submit_test3 = st.form_submit_button("Submit 3rd Reading & Save")
                
#                 if submit_test3:
#                     final_avg = (test1 + test2 + test3) / 3
#                     st.success(f"✅ All 3 readings saved. Final Average: **{final_avg:.1f} ppm**")
#                     # Here is where we would write the data to your CSV or database
#         else:
#             # ✅ DATA IS GOOD
#             st.success("✅ Variance is within acceptable lab limits. Data is good to save!")
#             # Here is where we would write the data to your CSV or database

import streamlit as st
import pandas as pd
from datetime import date

# --- PAGE CONFIGURATION ---
# (This must always be the first Streamlit command)
st.set_page_config(page_title="XRF Technician QA/QC Form", page_icon="🧪", layout="centered")

# --- SECURITY GATEKEEPER ---
def check_password():
    """Returns `True` if the user entered the correct password."""
    
    def password_entered():
        # Checks the entered password against the secret password
        if st.session_state["password"] == st.secrets["lab_password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Clear from memory
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("### 🔒 GroundSense Tech Portal Login")
        st.text_input("Enter Technician Password", type="password", on_change=password_entered, key="password")
        return False
        
    elif not st.session_state["password_correct"]:
        st.markdown("### 🔒 GroundSense Tech Portal Login")
        st.text_input("Enter Technician Password", type="password", on_change=password_entered, key="password")
        st.error("🚫 Incorrect password. Please try again.")
        return False
        
    else:
        return True

# --- STOP THE APP IF NOT LOGGED IN ---
if not check_password():
    st.stop()

# ==========================================
# MAIN DASHBOARD CODE (ONLY RUNS IF UNLOCKED)
# ==========================================

st.title("🧪 XRF Lab Technician Portal")
st.markdown("Enter your sample readings below. The system will automatically calculate variance and prompt for a third reading if the discrepancy is too high.")
st.markdown("---")

# --- SETTINGS ---
# Usually, environmental labs use a 20% Relative Percent Difference (RPD) as the threshold.
# You can hide this in a sidebar so only the admin can change it.
st.sidebar.header("Lab Configuration")
variance_threshold = st.sidebar.number_input("Max Allowed Discrepancy (%)", value=20.0, step=1.0)

# --- DATA ENTRY FORM ---
with st.form("xrf_entry_form"):
    st.subheader("Sample Information")
    col_date, col_id = st.columns(2)
    with col_date:
        test_date = st.date_input("Test Date", value=date.today())
    with col_id:
        sample_id = st.text_input("Sample ID (e.g., A1_PITT)", placeholder="Scan or type Sample ID")
        
    st.subheader("XRF Readings (Lead ppm)")
    col1, col2 = st.columns(2)
    
    with col1:
        test1 = st.number_input("Reading 1", min_value=0.0, step=1.0, format="%.1f")
    with col2:
        test2 = st.number_input("Reading 2", min_value=0.0, step=1.0, format="%.1f")
        
    # We use a submit button to process the logic
    submitted = st.form_submit_button("Analyze Variance", type="primary")

# --- LOGIC & ALERTS ---
if submitted:
    if sample_id.strip() == "":
        st.error("⚠️ Please enter a Sample ID before proceeding.")
    elif test1 > 0 and test2 > 0:
        # Calculate the Average and Relative Percent Difference (RPD)
        avg = (test1 + test2) / 2
        diff = abs(test1 - test2)
        rpd = (diff / avg) * 100 if avg > 0 else 0
        
        st.markdown("### 📊 Analysis Results")
        
        # Display the metrics nicely
        m1, m2, m3 = st.columns(3)
        m1.metric("Current Average", f"{avg:.1f} ppm")
        m2.metric("Difference", f"{diff:.1f} ppm")
        m3.metric("Variance (RPD)", f"{rpd:.1f}%", delta=f"Limit: {variance_threshold}%", delta_color="inverse")
        
        if rpd > variance_threshold:
            # 🚨 DISCREPANCY TOO HIGH - Trigger Test 3
            st.warning(f"⚠️ **High Variance Detected!** The discrepancy is {rpd:.1f}%, which exceeds the {variance_threshold}% limit.")
            st.info("👇 Please run a third test on this sample to stabilize the data.")
            
            # We use a second form specifically for the third reading
            with st.form("test3_form"):
                test3 = st.number_input("Reading 3", min_value=0.0, step=1.0, format="%.1f")
                submit_test3 = st.form_submit_button("Submit 3rd Reading & Save")
                
                if submit_test3:
                    final_avg = (test1 + test2 + test3) / 3
                    st.success(f"✅ All 3 readings saved. Final Average: **{final_avg:.1f} ppm**")
                    # Here is where we would write the data to your CSV or database
        else:
            # ✅ DATA IS GOOD
            st.success("✅ Variance is within acceptable lab limits. Data is good to save!")
            # Here is where we would write the data to your CSV or database
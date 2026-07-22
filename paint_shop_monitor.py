# -*- coding: utf-8 -*-
"""
System Name: Paint Shop Motor Monitoring Condition using Vibration & BDU Analysis
Framework: Streamlit & Matplotlib (Fleet Overview + Single Asset Selection)
Database: Google Sheets (via gspread API & Streamlit Secrets)
Theme: High-Contrast Light Mode with Industrial Safety Alerts
"""

import os
import time
import random
import datetime
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt

# --- GOOGLE SHEETS INTEGRATION IMPORTS ---
import gspread
from google.oauth2.service_account import Credentials

# --- THRESHOLD CONFIGURATION BOUNDARIES ---
# Threshold Constraints (vRMS) - Standardized to 2 decimal places
VRMS_THRESHOLD = 4.50  # Critical Limit (Red)
VRMS_WARNING = 2.80    # Warning Limit (Yellow)

# Threshold Constraints (BDU) - Standardized to 2 decimal places
BDU_THRESHOLD = 100.00   # Critical Limit (Red)
BDU_WARNING = 70.00      # Warning Limit (Yellow)

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Paint Shop Motor Monitoring",
    page_icon="⚙️",
    layout="wide"
)

# --- SESSION STATE INITIALIZATION FOR DYNAMIC MOTORS ---
if "motor_options" not in st.session_state:
    st.session_state.motor_options = [
        # --- SHEET A: CDWP & CHWP (CHILLER SYSTEM) ---
        "Chiller - CDWP 1", "Chiller - CDWP 2", "Chiller - CDWP 3",
        "Chiller - CDWP EQPT 1", "Chiller - CDWP EQPT 2",
        "Chiller - CHWP 1", "Chiller - CHWP 2", "Chiller - CHWP 3",
        "Chiller - CHWP EQPT 1", "Chiller - CHWP EQPT 2",
        
        # --- SHEET B: EXHAUST FANS ---
        "Exhaust Fan - Dust removal B", "Exhaust Fan - Dust Removal A",
        "Exhaust Fan - Primer B1", "Exhaust Fan - Primer A1",
        "Exhaust Fan - Primer A2", "Exhaust Fan - Primer B2",
        "Exhaust Fan - Primer B Pre Heat", "Exhaust Fan - Primer A Pre Heat",
        "Exhaust Fan - Base B1", "Exhaust Fan - Base A1",
        "Exhaust Fan - Base B2", "Exhaust Fan - Base A2",
        "Exhaust Fan - Base A3", "Exhaust Fan - Base B3",
        "Exhaust Fan - Top Coat A Pre Heat", "Exhaust Fan - Top Coat B Pre Heat",
        "Exhaust Fan - Clear B1", "Exhaust Fan - Clear A1",
        "Exhaust Fan - Clear A2", "Exhaust Fan - Clear B2",
        "Exhaust Fan - Set. Zone Exh Fan",
        
        # --- SHEET C: ASH SYSTEM (PUMPS & FANS) ---
        "ASH - Pump Clear A", "ASH - Clear A Supply Fan",
        "ASH - Pump Clear B", "ASH - Clear B Supply Fan",
        "ASH - Pump BB", "ASH - BB Supply",
        "ASH - Pump BA", "ASH - BA Supply",
        "ASH - Pump Primer B", "ASH - Primer B supply",
        "ASH - Pump Primer A", "ASH - Primer A supply",
        "ASH - Pump d. remove A", "ASH - D. Remove A supply",
        "ASH - Pump D. remove B", "ASH - D. Remove B Supply",
        "ASH - Pump W. Area", "ASH - W. Area Supply fan",
        "ASH - Pump HVAC", "ASH - HVAC supply fan"
    ]

if "motor_colors" not in st.session_state:
    st.session_state.motor_colors = {
        motor: f"#{random.randint(0, 0x999999):06x}" for motor in st.session_state.motor_options
    }

if "active_fleet_filter" not in st.session_state:
    st.session_state.active_fleet_filter = "ALL"

def get_sheet_name(motor_fullname):
    clean_name = (
        motor_fullname
        .replace(":", "")
        .replace("\\", "")
        .replace("/", "")
        .replace("?", "")
        .replace("*", "")
        .replace("[", "")
        .replace("]", "")
    )
    return clean_name[:31]

# --- GLOBAL LIGHT MODE STYLING & TEXT SIZES (CSS) ---
st.markdown(
    """
    <style>
        .stApp { background-color: #ffffff !important; color: #1e293b !important; }
        h1, h2, h3, p, label, span { color: #1e293b !important; }
        h1 { font-size: 2.4rem !important; font-weight: 700 !important; }
        h2 { font-size: 1.6rem !important; font-weight: 600 !important; margin-bottom: 12px !important;}
        h3 { font-size: 1.3rem !important; margin-top: 18px !important; }
        
        span[data-baseweb="tag"] {
            background-color: #e2e8f0 !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 6px !important;
        }
        span[data-baseweb="tag"] span { color: #1e293b !important; font-weight: 500 !important; }
        .stSidebar { background-color: #f8fafc !important; border-right: 1px solid #e2e8f0 !important; }
        
        [data-testid="stMetricLabel"] { font-size: 1.05rem !important; font-weight: 600 !important; color: #475569 !important; }
        [data-testid="stMetricValue"] { font-size: 1.6rem !important; font-weight: 700 !important; color: #0f172a !important; }
        
        div[data-testid="stButton"] button.metric-btn {
            background-color: #f1f5f9 !important; border: 1px solid #cbd5e1 !important;
            border-radius: 8px !important; padding: 15px !important; text-align: left !important;
            width: 100% !important; display: block !important; height: auto !important; box-shadow: none !important;
        }
        div[data-testid="stButton"] button.metric-btn:hover {
            border-color: #3b82f6 !important; background-color: #eff6ff !important;
        }
        
        .st_caption { font-size: 1.05rem !important; color: #64748b !important; }
        
        /* OVERVIEW FLEET FILTER SHAPE STYLING */
        div.fleet-all-container [data-testid="stButton"] button {
            background-color: #f8fafc !important; border: 2px solid #64748b !important;
            border-radius: 10px !important; color: #0f172a !important;
        }
        div.fleet-all-container [data-testid="stButton"] button:hover { background-color: #e2e8f0 !important; }

        div.fleet-normal-container [data-testid="stButton"] button {
            background-color: #f0fdf4 !important; border: 2px solid #16a34a !important;
            border-radius: 10px !important; color: #14532d !important;
        }
        div.fleet-normal-container [data-testid="stButton"] button:hover { background-color: #dcfce7 !important; }

        div.fleet-warning-container [data-testid="stButton"] button {
            background-color: #fffbeb !important; border: 2px solid #eab308 !important;
            border-radius: 10px !important; color: #713f12 !important;
        }
        div.fleet-warning-container [data-testid="stButton"] button:hover { background-color: #fef3c7 !important; }

        div.fleet-critical-container [data-testid="stButton"] button {
            background-color: #fef2f2 !important; border: 2px solid #dc2626 !important;
            border-radius: 10px !important; color: #7f1d1d !important;
        }
        div.fleet-critical-container [data-testid="stButton"] button:hover { background-color: #fee2e2 !important; }

        /* GLOBAL ACTION BUTTON EXECUTE OVERRIDES */
        div.execute-green-container button {
            background-color: #22c55e !important; color: #000000 !important;
            border: 1px solid #16a34a !important; border-radius: 8px !important; font-weight: 700 !important;
        }
        div.execute-green-container button:hover {
            background-color: #16a34a !important; border: 1px solid #15803d !important;
        }

        div.execute-red-container button {
            background-color: #ef4444 !important; color: #ffffff !important;
            border: 1px solid #dc2626 !important; border-radius: 8px !important; font-weight: 700 !important;
        }
        div.execute-red-container button:hover {
            background-color: #dc2626 !important; border: 1px solid #b91c1c !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- GOOGLE SHEETS DATABASE ENGINE ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def get_gspread_client():
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    if "private_key" in creds_dict:
        pk = creds_dict["private_key"]
        pk = pk.replace("\\n", "\n").replace("\\\\n", "\n")
        creds_dict["private_key"] = pk

    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)

# Caching sheet data for 120 seconds prevents hitting 429 Quota Exceeded error on READS
@st.cache_data(ttl=120)
def load_all_data(motor_list):
    """Loads all worksheets from the Google Spreadsheet into memory using Batch Operations to avoid 429 errors."""
    data_dict = {}
    try:
        gc = get_gspread_client()
        sheet_id = st.secrets["SPREADSHEET_ID"]
        sh = gc.open_by_key(sheet_id)
        
        # 1 API request: Get all existing worksheets
        existing_worksheets = [ws.title for ws in sh.worksheets()]
        ranges_to_fetch = []
        
        for m_name in motor_list:
            s_name = get_sheet_name(m_name)
            if s_name not in existing_worksheets:
                # Create sheet automatically if it doesn't exist
                time.sleep(1)
                worksheet = sh.add_worksheet(title=s_name, rows="100", cols="5")
                worksheet.append_row(["Date", "Vibration", "BDU"])
                data_dict[m_name] = pd.DataFrame(columns=["Date", "Vibration", "BDU"])
            else:
                ranges_to_fetch.append(f"'{s_name}'!A:C")
        
        if ranges_to_fetch:
            # 1 API request: Batch read all sheets at once
            batch_data = sh.values_batch_get(ranges_to_fetch)
            value_ranges = batch_data.get('valueRanges', [])
            
            fetch_idx = 0
            for m_name in motor_list:
                s_name = get_sheet_name(m_name)
                if s_name in existing_worksheets:
                    rows = value_ranges[fetch_idx].get('values', [])
                    fetch_idx += 1
                    
                    if len(rows) > 1:
                        header = rows[0]
                        data = rows[1:]
                        df = pd.DataFrame(data, columns=header) if len(header) >= 3 else pd.DataFrame(data)
                        if len(df.columns) >= 3:
                            df.columns = ["Date", "Vibration", "BDU"][:len(df.columns)]
                            
                        if not df.empty and 'Date' in df.columns:
                            df['Date'] = pd.to_datetime(df['Date'], format='mixed', errors='coerce').dt.date
                            df['Vibration'] = pd.to_numeric(df['Vibration'], errors='coerce').round(2)
                            if 'BDU' not in df.columns:
                                df['BDU'] = np.nan
                            else:
                                df['BDU'] = pd.to_numeric(df['BDU'], errors='coerce').round(2)
                            data_dict[m_name] = df.dropna(subset=['Date'])
                        else:
                            data_dict[m_name] = pd.DataFrame(columns=["Date", "Vibration", "BDU"])
                    else:
                        data_dict[m_name] = pd.DataFrame(columns=["Date", "Vibration", "BDU"])

    except Exception as e:
        st.error(f"Error loading Google Sheets database: {e}")
        for m_name in motor_list:
            data_dict[m_name] = data_dict.get(m_name, pd.DataFrame(columns=["Date", "Vibration", "BDU"]))
            
    return data_dict

def save_single_motor_data(motor_name, df_to_save):
    """Saves/Overwrites ONLY a single modified motor record to Google Sheets to avoid 429 Write limits."""
    try:
        gc = get_gspread_client()
        sheet_id = st.secrets["SPREADSHEET_ID"]
        sh = gc.open_by_key(sheet_id)
        
        s_name = get_sheet_name(motor_name)
        
        try:
            worksheet = sh.worksheet(s_name)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=s_name, rows="100", cols="5")

        worksheet.clear()
        export_df = df_to_save.copy()
        
        if not export_df.empty:
            if 'Date' in export_df.columns:
                export_df['Date'] = export_df['Date'].astype(str)
            export_df = export_df[['Date', 'Vibration', 'BDU']].fillna("")
            worksheet.update([export_df.columns.values.tolist()] + export_df.values.tolist())
        else:
            worksheet.update([["Date", "Vibration", "BDU"]])
        
        # Invalidate cache on write operations so fresh data loads immediately
        st.cache_data.clear()
        
    except Exception as e:
        st.error(f"Failed to save changes to Google Sheets: {e}")

# --- FORECASTING ENGINE: LEAST SQUARES ---
def calculate_forecast(df, metric, threshold):
    """Calculates intercept and slope using np.polyfit to predict date reaching threshold."""
    valid_df = df.dropna(subset=[metric, 'Days'])
    if len(valid_df) < 2:
        return None, None, None, None
        
    x = valid_df['Days'].values
    y = valid_df[metric].values
    
    # m = slope, c = intercept
    m, c = np.polyfit(x, y, 1)
    
    if m <= 0:
        return "Stable / No Degradation", m, c, None
        
    target_days = (threshold - c) / m
    start_date = pd.to_datetime(valid_df['Date_Parsed'].min())
    predicted_date = start_date + pd.Timedelta(days=target_days)
    
    return predicted_date.date(), m, c, target_days

if "all_motor_data" not in st.session_state:
    st.session_state.all_motor_data = load_all_data(st.session_state.motor_options)

all_motor_data = st.session_state.all_motor_data

def process_data_days(df):
    if df.empty:
        return df
    df_sorted = df.sort_values(by='Date').copy()
    df_sorted['Date_Parsed'] = pd.to_datetime(df_sorted['Date'])
    start_date = df_sorted['Date_Parsed'].min()
    df_sorted['Days'] = (df_sorted['Date_Parsed'] - start_date).dt.days
    return df_sorted

# --- HEADER SECTION ---
st.title("⚙️ Paint Shop Motor Monitoring Condition using Vibration Analysis")
st.caption("Predictive Maintenance & Degradation Tracking System")

tab_overview, tab_display, tab_measurements, tab_structure = st.tabs([
    "🖥️ Fleet Condition Overview",
    "📊 Real-Time Analytics & Trends", 
    "📋 Add & Manage Measurement Readings", 
    "⚙️ Database Structure & Asset Inventory"
])

color_map = {
    "NORMAL": "#16a34a",   
    "WARNING": "#eab308",  
    "CRITICAL": "#dc2626"  
}

# ==========================================
# TAB 1: ALL SYSTEMS FLEET CONDITION OVERVIEW
# ==========================================
with tab_overview:
    st.write("### 🖥️ Overall System Fleet Diagnostic Overview")
    if not st.session_state.motor_options:
        st.info("💡 No assets registered. Please navigate to the 'Database Structure' tab.")
    else:
        fleet_summary = []
        normal_count, warning_count, critical_count = 0, 0, 0

        for m_name in st.session_state.motor_options:
            df = all_motor_data.get(m_name, pd.DataFrame(columns=["Date", "Vibration", "BDU"]))
            df_sorted = process_data_days(df)
            
            if not df_sorted.empty:
                valid_v = df_sorted['Vibration'].dropna()
                last_v = round(float(valid_v.iloc[-1]), 2) if not valid_v.empty else 0.00
                
                valid_b = df_sorted['BDU'].dropna()
                last_b = round(float(valid_b.iloc[-1]), 2) if not valid_b.empty else 0.00
                
                v_state = "CRITICAL" if last_v >= VRMS_THRESHOLD else "WARNING" if last_v >= VRMS_WARNING else "NORMAL"
                b_state = "CRITICAL" if last_b >= BDU_THRESHOLD else "WARNING" if last_b >= BDU_WARNING else "NORMAL"
                if "CRITICAL" in [v_state, b_state]:
                    sys_status = "CRITICAL"
                    critical_count += 1
                elif "WARNING" in [v_state, b_state]:
                    sys_status = "WARNING"
                    warning_count += 1
                else:
                    sys_status = "NORMAL"
                    normal_count += 1
            else:
                last_v, last_b = 0.00, 0.00
                v_state, b_state, sys_status = "UNKNOWN", "UNKNOWN", "NO DATA"

            fleet_summary.append({
                "motor_name": m_name, "sys_status": sys_status,
                "v_val": last_v, "v_state": v_state,
                "b_val": last_b, "b_state": b_state
            })

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown('<div class="fleet-all-container">', unsafe_allow_html=True)
            if st.button(f"Total Fleet Motors\n\n### {len(st.session_state.motor_options)}", key="btn_filter_all", use_container_width=True):
                st.session_state.active_fleet_filter = "ALL"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
                
        with c2:
            st.markdown('<div class="fleet-normal-container">', unsafe_allow_html=True)
            if st.button(f"Healthy (NORMAL)\n\n### {normal_count}", key="btn_filter_normal", use_container_width=True):
                st.session_state.active_fleet_filter = "NORMAL"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
                
        with c3:
            st.markdown('<div class="fleet-warning-container">', unsafe_allow_html=True)
            if st.button(f"Caution (WARNING)\n\n### {warning_count}", key="btn_filter_warning", use_container_width=True):
                st.session_state.active_fleet_filter = "WARNING"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
                
        with c4:
            st.markdown('<div class="fleet-critical-container">', unsafe_allow_html=True)
            if st.button(f"Action Required (CRITICAL)\n\n### {critical_count}", key="btn_filter_critical", use_container_width=True):
                st.session_state.active_fleet_filter = "CRITICAL"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("---")
        filter_scope = st.session_state.active_fleet_filter
        
        st.write(f"#### 📋 {'Diagnostic Cards for All Systems' if filter_scope == 'ALL' else f'Filtered Diagnostic Cards: Status = {filter_scope}'}")
        filtered_summary = [item for item in fleet_summary if filter_scope == "ALL" or item["sys_status"] == filter_scope]

        if not filtered_summary:
            st.info(f"There are currently no assets matching the condition state segment: **{filter_scope}**")
        else:
            cols = st.columns(2)
            for idx, item in enumerate(filtered_summary):
                col = cols[idx % 2]
                
                bg_color = "#fef2f2" if item["sys_status"] == "CRITICAL" else "#fffbeb" if item["sys_status"] == "WARNING" else "#f0fdf4" if item["sys_status"] == "NORMAL" else "#f8fafc"
                border_color = "#dc2626" if item["sys_status"] == "CRITICAL" else "#f59e0b" if item["sys_status"] == "WARNING" else "#22c55e" if item["sys_status"] == "NORMAL" else "#cbd5e1"
                
                sys_c = color_map.get(item["sys_status"], "#64748b")
                v_c = color_map.get(item["v_state"], "#64748b")
                b_c = color_map.get(item["b_state"], "#64748b")

                with col:
                    st.markdown(
                        f"""
                        <div style="background-color: {bg_color}; border: 2px solid {border_color}; padding: 18px; border-radius: 8px; margin-bottom: 18px; font-family: sans-serif; text-align: center;">
                            <div style="font-size: 1.3rem; font-weight: 800; color: #000000 !important; margin-bottom: 4px;">{item['motor_name'].upper()}</div>
                            <div style="font-size: 1.15rem; font-weight: 700; color: {sys_c}; margin-bottom: 10px;">SYSTEM STATUS : {item['sys_status']}</div>
                            <div style="display: inline-block; text-align: left;">
                                <ul style="margin: 0; padding-left: 20px; font-size: 1.05rem; font-weight: 700; color: #334155; line-height: 1.8;">
                                    <li>VRMS CONDITION : <span style="color: {v_c};">{item['v_state']}</span> ({item['v_val']:.2f} mm/s)</li>
                                    <li>BDU CONDITION : <span style="color: {b_c};">{item['b_state']}</span> ({item['b_val']:.2f} BDU)</li>
                                </ul>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

# ==========================================
# TAB 2: INDIVIDUAL ANALYTICS & TRENDS
# ==========================================
with tab_display:
    if not st.session_state.motor_options:
        st.info("💡 No assets registered.")
    else:
        st.write("### 🔍 Live Diagnostic & Predictive Forecasting")
        
        active_motor = st.selectbox(
            "Select Targeted Fleet Asset Tracking Group:",
            options=st.session_state.motor_options,
            key="sync_plot"
        )

        df_active = all_motor_data.get(active_motor, pd.DataFrame(columns=["Date", "Vibration", "BDU"]))
        df_sorted = process_data_days(df_active)

        if not df_sorted.empty:
            valid_v = df_sorted['Vibration'].dropna()
            last_v = round(float(valid_v.iloc[-1]), 2) if not valid_v.empty else 0.00
            
            valid_b = df_sorted['BDU'].dropna()
            last_b = round(float(valid_b.iloc[-1]), 2) if not valid_b.empty else 0.00
            
            v_state = "CRITICAL" if last_v >= VRMS_THRESHOLD else "WARNING" if last_v >= VRMS_WARNING else "NORMAL"
            b_state = "CRITICAL" if last_b >= BDU_THRESHOLD else "WARNING" if last_b >= BDU_WARNING else "NORMAL"

            if "CRITICAL" in [v_state, b_state]:
                sys_status, bg_color, border_color = "CRITICAL", "#fef2f2", "#dc2626"
            elif "WARNING" in [v_state, b_state]:
                sys_status, bg_color, border_color = "WARNING", "#fffbeb", "#f59e0b"
            else:
                sys_status, bg_color, border_color = "NORMAL", "#f0fdf4", "#22c55e"

            sys_color = color_map.get(sys_status, "#64748b")

            st.markdown(
                f"""
                <div style="background-color: {bg_color}; border: 2px solid {border_color}; padding: 20px; border-radius: 8px; margin-top: 10px; margin-bottom: 20px; font-family: sans-serif; text-align: center;">
                    <div style="font-size: 1.5rem; font-weight: 800; color: #000000 !important; margin-bottom: 6px;">{active_motor.upper()}</div>
                    <div style="font-size: 1.25rem; font-weight: 700; color: {sys_color}; margin-bottom: 12px;">SYSTEM STATUS : {sys_status}</div>
                </div>
                """, unsafe_allow_html=True
            )
            
            v_date_pred, v_m, v_c, v_target_days = calculate_forecast(df_sorted, "Vibration", VRMS_THRESHOLD)
            b_date_pred, b_m, b_c, b_target_days = calculate_forecast(df_sorted, "BDU", BDU_THRESHOLD)
            
            # OVERRIDE DATE DISPLAY IF CURRENT READING IS EQUAL OR GREATER THAN CRITICAL
            if last_v >= VRMS_THRESHOLD:
                v_date_display = "⚠️ Maintenance Required"
            else:
                v_date_display = str(v_date_pred) if v_date_pred else "No Data"

            if last_b >= BDU_THRESHOLD:
                b_date_display = "⚠️ Maintenance Required"
            else:
                b_date_display = str(b_date_pred) if b_date_pred else "No Data"

            st.write("#### 📊 Asset Live Metrics & Forecast Data")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Latest Velocity (vRMS)", f"{last_v:.2f} mm/s")
            m2.metric("Latest Bearing Value", f"{last_b:.2f} BDU")
            m3.metric("Date to Critical VRMS", v_date_display)
            m4.metric("Date to Critical BDU", b_date_display)
            
            st.markdown("---")
        else:
            last_v, last_b = 0.00, 0.00
            v_m, v_c, v_target_days = None, None, None
            b_m, b_c, b_target_days = None, None, None
            st.info("No recorded timeline updates found for this asset profile.")

        if len(df_sorted) >= 1:
            max_days_in_data = df_sorted['Days'].max()
            plt.style.use('default')

            # --- VRMS PLOT WITH DYNAMIC TRAJECTORY ---
            valid_v_df = df_sorted.dropna(subset=['Vibration'])
            if not valid_v_df.empty:
                st.write("#### 📈 Velocity Amplitude (vRMS) Forecasted Trend")
                fig1, ax1 = plt.subplots(figsize=(11, 4.5))
                fig1.patch.set_facecolor('#ffffff') 
                ax1.set_facecolor('#ffffff')        
                
                ax1.scatter(valid_v_df['Days'], valid_v_df['Vibration'], color='#0000ff', s=100, label='Historical Data', zorder=5)
                ax1.plot(valid_v_df['Days'], valid_v_df['Vibration'], color='#cbd5e1', linestyle='-', linewidth=1.5, zorder=4)
                
                plot_max_days_v = max_days_in_data + 30
                if v_m is not None and v_c is not None:
                    if v_m > 0 and v_target_days is not None:
                        plot_max_days_v = max(plot_max_days_v, v_target_days + 15)
                        x_trend = np.linspace(0, v_target_days, 100)
                        y_trend = v_m * x_trend + v_c
                        ax1.plot(x_trend, y_trend, color='#8b5cf6', linestyle='--', linewidth=2, label='Forecasted Trend', zorder=3)
                    else:
                        x_trend = np.linspace(0, plot_max_days_v, 100)
                        y_trend = v_m * x_trend + v_c
                        ax1.plot(x_trend, y_trend, color='#10b981', linestyle='--', linewidth=2, label='Stable Trend', zorder=3)

                for idx, row in valid_v_df.iterrows():
                    date_str = row['Date'].strftime('%d-%m-%Y') if isinstance(row['Date'], (datetime.date, datetime.datetime)) else str(row['Date'])
                    ax1.annotate(
                        f"{date_str}\n({row['Vibration']:.2f})", 
                        (row['Days'], row['Vibration']), textcoords="offset points", xytext=(0, 8), ha='center', 
                        fontsize=6, fontweight='bold', color='#1e293b',
                        bbox=dict(boxstyle="round,pad=0.15", fc="#f1f5f9", ec="#cbd5e1", alpha=0.85)
                    )
                
                ax1.axhline(y=VRMS_WARNING, color='#eab308', linestyle='-', linewidth=1.5, label=f'Warning Limit ({VRMS_WARNING:.2f} mm/s)')
                ax1.axhline(y=VRMS_THRESHOLD, color='#dc2626', linestyle='-', linewidth=1.5, label=f'Critical Limit ({VRMS_THRESHOLD:.2f} mm/s)')

                ax1.set_ylabel("Vibration (mm/s)", fontsize=12)
                ax1.set_xlabel("Days Since Start of Monitoring", fontsize=12)
                ax1.set_xlim(-1, plot_max_days_v)
                ax1.set_ylim(0, max(VRMS_THRESHOLD + 1.2, valid_v_df['Vibration'].max() + 0.8))
                ax1.grid(True, linestyle=':', alpha=0.6, color='#cbd5e1')
                ax1.legend(loc="upper left", frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1')
                fig1.tight_layout()
                st.pyplot(fig1)
                plt.close(fig1)

            # --- BDU PLOT WITH DYNAMIC TRAJECTORY ---
            valid_b_df = df_sorted.dropna(subset=['BDU'])
            if not valid_b_df.empty:
                st.write("#### 📈 Bearing Damage Unit (BDU) Forecasted Trend")
                fig2, ax2 = plt.subplots(figsize=(11, 4.5))
                fig2.patch.set_facecolor('#ffffff') 
                ax2.set_facecolor('#ffffff')        
                
                ax2.scatter(valid_b_df['Days'], valid_b_df['BDU'], color='#0000ff', s=100, label='Historical Data', zorder=5)
                ax2.plot(valid_b_df['Days'], valid_b_df['BDU'], color='#cbd5e1', linestyle='-', linewidth=1.5, zorder=4)
                
                plot_max_days_b = max_days_in_data + 30
                if b_m is not None and b_c is not None:
                    if b_m > 0 and b_target_days is not None:
                        plot_max_days_b = max(plot_max_days_b, b_target_days + 15)
                        x_trend_b = np.linspace(0, b_target_days, 100)
                        y_trend_b = b_m * x_trend_b + b_c
                        ax2.plot(x_trend_b, y_trend_b, color='#8b5cf6', linestyle='--', linewidth=2, label='Forecasted Trend', zorder=3)
                    else:
                        x_trend_b = np.linspace(0, plot_max_days_b, 100)
                        y_trend_b = b_m * x_trend_b + b_c
                        ax2.plot(x_trend_b, y_trend_b, color='#10b981', linestyle='--', linewidth=2, label='Stable Trend', zorder=3)
                
                for idx, row in valid_b_df.iterrows():
                    date_str = row['Date'].strftime('%d-%m-%Y') if isinstance(row['Date'], (datetime.date, datetime.datetime)) else str(row['Date'])
                    ax2.annotate(
                        f"{date_str}\n({row['BDU']:.2f})", 
                        (row['Days'], row['BDU']), textcoords="offset points", xytext=(0, 8), ha='center', 
                        fontsize=6, fontweight='bold', color='#1e293b',
                        bbox=dict(boxstyle="round,pad=0.15", fc="#f1f5f9", ec="#cbd5e1", alpha=0.85)
                    )
                
                ax2.axhline(y=BDU_WARNING, color='#eab308', linestyle='-', linewidth=1.5, label=f'Warning Limit ({BDU_WARNING:.2f} BDU)')
                ax2.axhline(y=BDU_THRESHOLD, color='#dc2626', linestyle='-', linewidth=1.5, label=f'Critical Limit ({BDU_THRESHOLD:.2f} BDU)')

                ax2.set_ylabel("Bearing Value (BDU)", fontsize=12)
                ax2.set_xlabel("Days Since Start of Monitoring", fontsize=12)
                ax2.set_xlim(-1, plot_max_days_b)
                ax2.set_ylim(0, max(BDU_THRESHOLD + 25.0, valid_b_df['BDU'].max() + 15.0))
                ax2.grid(True, linestyle=':', alpha=0.6, color='#cbd5e1')
                ax2.legend(loc="upper left", frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1')
                fig2.tight_layout()
                st.pyplot(fig2)
                plt.close(fig2)

# ==========================================
# TAB 3: MEASUREMENTS WORKSPACE
# ==========================================
with tab_measurements:
    st.write("### 📊 Continuous Variable Updates & Adjustments")
    
    if st.session_state.motor_options:
        selected_tab2_motor = st.selectbox(
            "Select Target Fleet Asset Profile for Operations:", 
            options=st.session_state.motor_options, 
            key="tab2_active_motor"
        )
        
        st.info(f"📍 **Active Target Motor:** Operations will strictly apply **ONLY to {selected_tab2_motor}** (Google Sheet: `{get_sheet_name(selected_tab2_motor)}`)")
        st.markdown("---")
        
        col_log, col_drop_row = st.columns(2)
        
        with col_log:
            st.caption(f"📋 **Append Log Entry to `{selected_tab2_motor}`**")
            
            with st.form(key="append_entry_form", clear_on_submit=True):
                measurement_date = st.date_input("Readout Timeline Timestamp Date", datetime.date.today(), format="DD/MM/YYYY")
                vibration_value = st.number_input("vRMS Amplitude Input (mm/s)", min_value=0.0, step=0.01, format="%.2f", value=None)
                bdu_value = st.number_input("Bearing Damage Unit (BDU) Value", min_value=0.0, step=0.01, format="%.2f", value=None)

                st.markdown('<div class="execute-green-container">', unsafe_allow_html=True)
                submit_btn = st.form_submit_button("Append Timeline Entry Row", use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

                if submit_btn:
                    if vibration_value is None and bdu_value is None:
                        st.error("⚠️ Failed to append data: Please enter at least one value.")
                    else:
                        current_df = st.session_state.all_motor_data.get(selected_tab2_motor, pd.DataFrame(columns=["Date", "Vibration", "BDU"]))
                        if not current_df.empty:
                            current_df['Date'] = pd.to_datetime(current_df['Date'], errors='coerce').dt.date

                        existing_row_idx = current_df[current_df['Date'] == measurement_date].index

                        if not existing_row_idx.empty:
                            idx = existing_row_idx[0]
                            if vibration_value is not None:
                                current_df.at[idx, 'Vibration'] = round(vibration_value, 2)
                            if bdu_value is not None:
                                current_df.at[idx, 'BDU'] = round(bdu_value, 2)
                            st.success(f"✅ Updated logs for **{selected_tab2_motor}** on date **{measurement_date.strftime('%d-%m-%Y')}**!")
                        else:
                            v_to_insert = round(vibration_value, 2) if vibration_value is not None else np.nan
                            b_to_insert = round(bdu_value, 2) if bdu_value is not None else np.nan
                            
                            new_row = pd.DataFrame([{"Date": measurement_date, "Vibration": v_to_insert, "BDU": b_to_insert}])
                            current_df = pd.concat([current_df, new_row], ignore_index=True)
                            st.success(f"✅ Appended new log for **{selected_tab2_motor}** on date **{measurement_date.strftime('%d-%m-%Y')}**!")

                        st.session_state.all_motor_data[selected_tab2_motor] = current_df
                        save_single_motor_data(selected_tab2_motor, current_df)
        
        with col_drop_row:
            st.caption(f"🗑️ **Remove Latest Entry from `{selected_tab2_motor}`**")
            with st.form(key="delete_entry_form", clear_on_submit=True):
                st.markdown('<div class="execute-red-container">', unsafe_allow_html=True)
                delete_btn = st.form_submit_button("Delete Latest Entry Row", use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

                if delete_btn:
                    current_df = st.session_state.all_motor_data.get(selected_tab2_motor, pd.DataFrame())
                    if not current_df.empty:
                        # Drop the last row
                        current_df = current_df.iloc[:-1]
                        st.session_state.all_motor_data[selected_tab2_motor] = current_df
                        save_single_motor_data(selected_tab2_motor, current_df)
                        st.success(f"✅ Deleted latest log entry for **{selected_tab2_motor}**!")
                    else:
                        st.warning("⚠️ No data to delete for this motor.")

# ==========================================
# TAB 4: DATABASE STRUCTURE & INVENTORY
# ==========================================
with tab_structure:
    st.write("### ⚙️ Database Structure & Asset Inventory")
    st.write("Current monitored assets grouped by Google Sheets mapping:")
    st.dataframe(pd.DataFrame(st.session_state.motor_options, columns=["Motor Asset Name"]), use_container_width=True)

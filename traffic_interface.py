import streamlit as st
import pandas as pd
import folium
from folium.plugins import PolyLineTextPath
from streamlit_folium import st_folium
import json
import os
import requests
import plotly.express as px
import random

from shapely.geometry import LineString
from pyproj import Transformer

# --- 1. Ρυθμίσεις σελίδας ---
icon_path = "upatras_logo.png" if os.path.exists("upatras_logo.png") else "🚦"
st.set_page_config(page_title="Patras Traffic Analytics", page_icon=icon_path, layout="wide")

# 🔥 CUSTOM CSS: DARK GLASSMORPHISM
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    /* 1. Νυχτερινή Εικόνα Φόντου σε όλη την εφαρμογή */
    .stApp { 
        background-image: url("https://images.unsplash.com/photo-1517685633466-403d6955aeab?ixlib=rb-4.0.3&auto=format&fit=crop&w=1920&q=80");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        font-family: 'Inter', sans-serif; 
    }
    
    /* 2. Κεντρικό Ημιδιάφανο Σκούρο Πλαίσιο (Dark Glass) */
    .block-container {
        background: rgba(11, 15, 25, 0.75); /* Σκούρο μπλε/μαύρο με 75% αδιαφάνεια */
        backdrop-filter: blur(12px); /* Θολώνει την εικόνα από πίσω */
        border-radius: 20px;
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        margin-top: 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.08); /* Πολύ αχνό λευκό περίγραμμα */
    }

    /* Χρώματα κειμένου (Λευκά/Ασημί για αντίθεση) */
    h1, h2, h3, h4, p, span, label { color: #F8FAFC !important; font-family: 'Inter', sans-serif; }
    
    /* Κάρτες Μετρήσεων (Metrics) - Πιο διαφανείς */
    div[data-testid="metric-container"] {
        background-color: rgba(15, 23, 42, 0.6) !important; /* Ημιδιάφανο σκούρο */
        backdrop-filter: blur(8px);
        border-radius: 12px; 
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3); 
        border: 1px solid rgba(255, 255, 255, 0.1);
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 20px rgba(0, 0, 0, 0.6);
        border-color: #00BFFF;
    }
    [data-testid="stMetricValue"] { font-size: 2.2rem !important; font-weight: 800; color: #00BFFF !important; text-shadow: 0 0 10px rgba(0,191,255,0.3); }
    [data-testid="stMetricLabel"] { font-size: 1rem !important; color: #94A3B8 !important; font-weight: 600 !important; }
    
    /* Sidebar (Σκούρο Γυαλί) */
    [data-testid="stSidebar"] { 
        background-color: rgba(11, 15, 25, 0.8) !important; 
        backdrop-filter: blur(15px);
        border-right: 1px solid rgba(255, 255, 255, 0.08); 
    }
    
    /* Tabs */
    button[data-baseweb="tab"] { font-size: 1.1rem; font-weight: 600; color: #94A3B8; transition: all 0.2s ease; background: transparent; }
    button[data-baseweb="tab"]:hover { color: #F8FAFC; }
    button[data-baseweb="tab"][aria-selected="true"] { 
        color: #00BFFF !important; 
        border-bottom: 3px solid #00BFFF !important; 
        background-color: rgba(0, 191, 255, 0.05); 
    }

    /* Inputs / Selectboxes */
    .stSelectbox > div > div { background-color: rgba(30, 41, 59, 0.7); color: white; border-radius: 8px; border: 1px solid rgba(255,255,255,0.2); }
    .stDataFrame { border-radius: 12px; overflow: hidden; border: 1px solid rgba(255, 255, 255, 0.1); }
</style>
""", unsafe_allow_html=True)

# --- Κεντρικός Τίτλος ---
col_logo, col_title = st.columns([1, 8]) 
with col_logo:
    if os.path.exists("upatras_logo.png"):
        st.image("upatras_logo.png", width=90)
    else:
        st.markdown("<h1 style='font-size: 3.5rem; text-align: center; margin-top: 0;'>🏛️</h1>", unsafe_allow_html=True)

with col_title:
    st.markdown("<h4 style='color: #94A3B8 !important; font-weight: 500; margin-bottom: -15px;'>ΠΑΝΕΠΙΣΤΗΜΙΟ ΠΑΤΡΩΝ</h4>", unsafe_allow_html=True)
    st.markdown("<h1 style='font-size: 2.8rem; font-weight: 800; text-shadow: 2px 2px 4px rgba(0,0,0,0.5);'>Patras Traffic Analytics <span style='color: #00BFFF;'>PRO</span></h1>", unsafe_allow_html=True)

st.markdown("<hr style='border: 1px solid rgba(255,255,255,0.1); margin-top: 10px; margin-bottom: 30px;'>", unsafe_allow_html=True)

if 'start_point' not in st.session_state: st.session_state.start_point = None
if 'end_point' not in st.session_state: st.session_state.end_point = None

# --- 2. Φόρτωση Στατικών & Τύπων από το EXCEL ---
static_data = {}
road_types = {}
if os.path.exists("traffic_patra.xlsx"):
    try:
        df_ex1 = pd.read_excel("traffic_patra.xlsx", sheet_name="Φύλλο1")
        for _, row in df_ex1.iterrows():
            r_name = row['Road_Segment']
            road_types[r_name] = str(row.get('Road type', row.get('Road_type', 'Άγνωστο'))).strip()
            static_data[r_name] = row.get('Static_Speed', 50)
            
        df_ex2 = pd.read_excel("traffic_patra.xlsx", sheet_name="Φύλλο2")
        for _, row in df_ex2.iterrows():
            r_name = row['Road_Segment']
            road_types[r_name] = str(row.get('Road type', row.get('Road_type', 'secondary'))).strip()
            static_data[r_name] = row.get('Static_Speed', 50)
    except Exception as e:
        st.error(f"Σφάλμα ανάγνωσης Excel: {e}")

# --- 3. Φόρτωση Γεωμετρίας & CSV ---
if not os.path.exists("road_geometry.json"):
    st.error("❌ Λείπει το αρχείο 'road_geometry.json'! Τρέξτε πρώτα το setupgeometry.py")
    st.stop()

with open("road_geometry.json", "r", encoding="utf-8") as f:
    geometry_data = json.load(f)

if not os.path.exists("live_traffic_data.csv"):
    st.warning("⏳ Αναμονή για δεδομένα από το Bot...")
    st.stop()

df_history = pd.read_csv("live_traffic_data.csv", sep=";")
df_history['Timestamp'] = pd.to_datetime(df_history['Timestamp'], format='mixed', errors='coerce')
df_history['Date'] = df_history['Timestamp'].dt.date
df_history['Time'] = df_history['Timestamp'].dt.strftime('%H:%M')

API_KEYS = [
    "UsA5r09FOSV6PmRd4NZFF3JCW3y6N2o1", 
    "Nz9zgm9uxG3Pd70dK2OYvEtdktn8PQSD",
    "IP2weRLSvXxstW414lUcWWSks3qwrGYR", 
    "V8V7MYwbnjA6y0YJj8V46mkxvXRM9Uz9"
]

# --- 4. SIDEBAR ---
with st.sidebar:
    st.markdown("<h2 style='text-align: center; text-shadow: 1px 1px 2px black;'>⚙️ Κέντρο Ελέγχου</h2>", unsafe_allow_html=True)
    st.markdown("<hr style='border: 1px solid rgba(255,255,255,0.1);'>", unsafe_allow_html
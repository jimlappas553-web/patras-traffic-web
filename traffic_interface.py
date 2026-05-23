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
st.set_page_config(page_title="Patras Traffic Analytics", layout="wide")

# --- 2. CSS για Professional Light Theme ---
st.markdown("""
<style>
    .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
    h1, h2, h3, h4, p, label, div, span { color: #0F172A !important; }
    .block-container { background: #FFFFFF; border-radius: 16px; padding: 2rem !important; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border: 1px solid #E2E8F0; }
    div[data-testid="metric-container"] { background-color: #F1F5F9 !important; border: 1px solid #E2E8F0; border-radius: 10px; padding: 20px; }
    [data-testid="stMetricValue"] { color: #0284C7 !important; font-weight: 800 !important; }
    [data-testid="stSidebar"] { background-color: #F1F5F9 !important; }
    button[data-baseweb="tab"][aria-selected="true"] { color: #0284C7 !important; border-bottom: 2px solid #0284C7 !important; }
</style>
""", unsafe_allow_html=True)

# --- 3. Header ---
col1, col2 = st.columns([1, 10])
if os.path.exists("upatras_logo.png"): col1.image("upatras_logo.png", width=80)
col2.markdown("## Πανεπιστήμιο Πατρών - Εργαστήριο Συστημάτων Μεταφορών\n# Patras Traffic Analytics <span style='color:#0284C7;'>PRO</span>", unsafe_allow_html=True)
st.divider()

# --- 4. Δεδομένα & Cache ---
@st.cache_data
def load_all():
    with open("road_geometry.json", "r", encoding="utf-8") as f: geom = json.load(f)
    df = pd.read_csv("live_traffic_data.csv", sep=";")
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='mixed')
    st_data, r_types = {}, {}
    if os.path.exists("traffic_patra.xlsx"):
        ex = pd.concat([pd.read_excel("traffic_patra.xlsx", sheet_name="Φύλλο1"), pd.read_excel("traffic_patra.xlsx", sheet_name="Φύλλο2")])
        for _, r in ex.iterrows():
            st_data[r['Road_Segment']] = r.get('Static_Speed', 50)
            r_types[r['Road_Segment']] = str(r.get('Road_type', 'secondary')).strip()
    return st_data, r_types, geom, df

static_data, road_types, geometry_data, df_history = load_all()

# --- 5. Sidebar ---
with st.sidebar:
    st.header("⚙️ Έλεγχος Παραμέτρων")
    sel_date = st.selectbox("📅 Ημερομηνία", sorted(df_history['Timestamp'].dt.date.unique()))
    df_day = df_history[df_history['Timestamp'].dt.date == sel_date]
    sel_time = st.selectbox("⏱️ Ώρα", sorted(df_day['Timestamp'].dt.strftime('%H:%M').unique()))
    sel_road = st.selectbox("📍 Οδός", ["Όλες οι Οδοί"] + sorted(geometry_data.keys()))

# --- 6. Helper Functions ---
def get_hybrid_color(speed, road_name):
    if pd.isna(speed) or speed < 5: return "#94A3B8"
    ratio = speed / static_data.get(road_name, 50)
    return "#DC2626" if ratio < 0.4 else "#F59E0B" if ratio < 0.75 else "#059669"

current = df_history[(df_history['Timestamp'].dt.date == sel_date) & (df_history['Timestamp'].dt.strftime('%H:%M') == sel_time)]
speeds = dict(zip(current['Road_Segment'], current['Speed_kmh']))

# --- 7. Tabs & Content ---
tab1, tab2, tab3 = st.tabs(["🗺️ Ανάλυση Δικτύου", "📍 Δρομολόγηση", "📅 Στατιστικά"])

with tab1:
    m = folium.Map(location=[38.2462, 21.7351], zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', attr='Google Maps')
    for r, coords in geometry_data.items():
        folium.PolyLine(locations=coords, color=get_hybrid_color(speeds.get(r, 50), r), weight=4, opacity=0.8, tooltip=f"{r}: {speeds.get(r, 50)} km/h").add_to(m)
    st_folium(m, width=1200, height=500)

with tab2:
    st.subheader("Έξυπνη Δρομολόγηση")
    if 'start' not in st.session_state: st.session_state.start = None
    if 'end' not in st.session_state: st.session_state.end = None
    if st.button("Καθαρισμός"): st.session_state.start = None; st.session_state.end = None; st.rerun()
    
    m_route = folium.Map(location=[38.2462, 21.7351], zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', attr='Google Maps')
    click_data = st_folium(m_route, width=1200, height=400)
    if click_data and click_data.get("last_clicked"):
        pt = [click_data["last_clicked"]["lat"], click_data["last_clicked"]["lng"]]
        if not st.session_state.start: st.session_state.start = pt
        elif not st.session_state.end: st.session_state.end = pt
        st.rerun()
    st.write(f"Αφετηρία: {st.session_state.start} | Προορισμός: {st.session_state.end}")

with tab3:
    st.subheader("Εβδομαδιαία Ανάλυση")
    df_heat = df_history.copy()
    df_heat['Day'] = df_heat['Timestamp'].dt.day_name()
    df_heat['Hour'] = df_heat['Timestamp'].dt.hour
    heatmap_data = df_heat.groupby(['Day', 'Hour'])['Speed_kmh'].mean().unstack()
    st.plotly_chart(px.imshow(heatmap_data, labels=dict(x="Ώρα", y="Ημέρα", color="Ταχύτητα"), color_continuous_scale='Viridis'), use_container_width=True)

st.divider()
st.caption("© 2026 Πανεπιστήμιο Πατρών - Εργαστήριο Συστημάτων Μεταφορών")
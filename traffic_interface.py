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

# 🔥 ΑΣΦΑΛΕΣ CSS: DARK GLASSMORPHISM
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    /* Νυχτερινή Εικόνα Φόντου (Σκοτεινός δρόμος πόλης) */
    .stApp { 
        background-image: url("https://images.unsplash.com/photo-1494522855154-9297ac14b55f?ixlib=rb-4.0.3&auto=format&fit=crop&w=1920&q=80");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        font-family: 'Inter', sans-serif; 
    }
    
    /* Διαφανές Header */
    [data-testid="stHeader"] { background-color: transparent !important; }

    /* Ασφαλής Στόχευση του Κεντρικού Πλαισίου (Dark Glass) */
    [data-testid="block-container"] {
        background: rgba(11, 15, 25, 0.85); /* Σκούρο μπλε/μαύρο με 85% αδιαφάνεια */
        backdrop-filter: blur(10px); 
        border-radius: 20px;
        padding: 2rem !important;
        margin-top: 1rem;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.08);
    }

    /* Χρώματα κειμένου */
    h1, h2, h3, h4, p, span, label { color: #F8FAFC !important; font-family: 'Inter', sans-serif; }
    
    /* Κάρτες Μετρήσεων */
    div[data-testid="metric-container"] {
        background-color: rgba(30, 41, 59, 0.6) !important; 
        backdrop-filter: blur(8px);
        border-radius: 12px; 
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3); 
        border: 1px solid rgba(255, 255, 255, 0.1);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 20px rgba(0, 0, 0, 0.6);
        border-color: #00BFFF;
    }
    [data-testid="stMetricValue"] { font-size: 2.2rem !important; font-weight: 800; color: #00BFFF !important; text-shadow: 0 0 10px rgba(0,191,255,0.3); }
    [data-testid="stMetricLabel"] { font-size: 1rem !important; color: #94A3B8 !important; font-weight: 600 !important; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { 
        background-color: rgba(11, 15, 25, 0.9) !important; 
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

    /* Inputs */
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
    st.markdown("<hr style='border: 1px solid rgba(255,255,255,0.1);'>", unsafe_allow_html=True)
    
    available_dates = sorted(df_history['Date'].dropna().unique())
    if not available_dates:
        st.error("Σφάλμα: Το CSV δεν έχει έγκυρες ημερομηνίες!")
        st.stop()

    selected_date = st.selectbox("📅 Επιλέξτε μέρα:", options=available_dates, index=len(available_dates)-1)
    df_day = df_history[df_history['Date'] == selected_date]
    available_times = sorted(df_day['Time'].dropna().unique())

    if not available_times:
        st.warning("Δεν βρέθηκαν καταγραφές.")
        st.stop()

    selected_time = st.selectbox("⏱️ Επιλέξτε ώρα:", options=available_times, index=len(available_times)-1)
    
    unique_types = ["Όλοι οι Τύποι"] + sorted(list(set(road_types.values()))) if road_types else ["Όλοι οι Τύποι"]
    selected_type = st.selectbox("🛤️ Επιλέξτε τύπο οδού:", options=unique_types, index=0)

    available_roads_for_step4 = [r for r in geometry_data.keys() if selected_type == "Όλοι οι Τύποι" or road_types.get(r) == selected_type]
    all_roads = ["Όλες οι Οδοί"] + sorted(available_roads_for_step4)
    selected_road = st.selectbox("📍 Επιλέξτε δρόμο:", options=all_roads, index=0)
    
    past_mask = (df_history['Date'] < selected_date) | ((df_history['Date'] == selected_date) & (df_history['Time'] <= selected_time))
    all_current_df = df_history[past_mask].drop_duplicates(subset=['Road_Segment'], keep='last')
    
    live_speeds = dict(zip(all_current_df['Road_Segment'], all_current_df['Speed_kmh']))
    
    roads_to_remove = []
    for road, speed in live_speeds.items():
        try: val = float(speed)
        except: val = 0.0
        if val <= 0.5: roads_to_remove.append(road)
    for road in roads_to_remove: del live_speeds[road]
        
    def get_center(coords):
        lats, lons = [c[0] for c in coords], [c[1] for c in coords]
        return (sum(lats)/len(lats), sum(lons)/len(lons))

    live_centers = {r: get_center(geometry_data[r]) for r in live_speeds.keys() if r in geometry_data}
    dynamic_secondary_speeds = {}
    
    for r_name in geometry_data.keys():
        if r_name not in live_speeds:
            static_speed = static_data.get(r_name, 50) 
            center_sec = get_center(geometry_data[r_name])
            distances = [((center_sec[0] - center_live[0])**2 + (center_sec[1] - center_live[1])**2, live_name) for live_name, center_live in live_centers.items()]
            distances.sort()
            
            closest_live = distances[:1] if "_rev" in str(r_name).lower() else distances[:3]
            if closest_live:
                local_ratios = [min(live_speeds[l_name] / static_data.get(l_name, 50), 1.0) for _, l_name in closest_live if static_data.get(l_name, 50) > 0]
                local_health_factor = sum(local_ratios) / len(local_ratios) if local_ratios else 1.0
            else:
                local_health_factor = 1.0 
            
            dynamic_secondary_speeds[r_name] = round(max(static_speed * local_health_factor, 5.0), 1)
            
    all_speeds_map = {**live_speeds, **dynamic_secondary_speeds}
    filtered_view_df = all_current_df.copy()
    if selected_type != "Όλοι οι Τύποι":
        filtered_view_df['Type'] = filtered_view_df['Road_Segment'].map(road_types)
        filtered_view_df = filtered_view_df[filtered_view_df['Type'] == selected_type]
        
    st.markdown("<br>", unsafe_allow_html=True)
    st.metric(label="📊 Ενεργές Μετρήσεις", value=len(filtered_view_df))

# --- ΚΟΙΝΕΣ ΣΥΝΑΡΤΗΣΕΙΣ ---
to_mercator = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
to_wgs84 = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

def get_parallel_line(coords, dist_meters=2.0): 
    try:
        xy_pairs = [(c[1], c[0]) for c in coords]
        if len(xy_pairs) < 2: return coords
        projected_xy = [to_mercator.transform(x, y) for x, y in xy_pairs]
        line = LineString(projected_xy).parallel_offset(dist_meters, side='right', join_style=1) 
        
        coords_out_xy = []
        if line.geom_type == 'MultiLineString':
            for sub_line in line.geoms: coords_out_xy.extend(list(sub_line.coords))
        else: coords_out_xy = list(line.coords)
        
        if len(coords_out_xy) < 2: return coords
        return [[y, x] for x, y in [to_wgs84.transform(x, y) for x, y in coords_out_xy]]
    except: return coords

def is_night_time(time_str):
    if not time_str: return False
    try: return int(time_str.split(':')[0]) >= 22 or int(time_str.split(':')[0]) <= 6
    except: return False

def get_hybrid_color(speed, road_name, current_time_str):
    if pd.isna(speed) or speed == 0: return "#64748B" 
    
    r_type = road_types.get(road_name, "").lower()
    night_mode = is_night_time(current_time_str)
    
    if "trunk" in r_type or "motorway" in r_type:
        limit = static_data.get(road_name, 90)
        ratio = speed / limit if limit > 0 else 1
        if ratio < 0.4: color_cat = "red"
        elif ratio < 0.75: color_cat = "yellow"
        else: color_cat = "green"
    else:
        if speed < 15: color_cat = "red"
        elif speed < 30: color_cat = "yellow"
        else: color_cat = "green"
        
    if night_mode:
        if color_cat == "red": color_cat = "yellow"
        elif color_cat == "yellow": color_cat = "green"
        
    if color_cat == "red": return "#EF4444"    
    if color_cat == "yellow": return "#F59E0B" 
    return "#10B981"                           

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["🗺️ Ανάλυση Δικτύου", "📍 Έξυπνη Δρομολόγηση", "📅 Στατιστικά & Heatmap"])

# ================= TAB 1 =================
with tab1:
    st.markdown(f"<h4>Αποτύπωση Κυκλοφορίας: <span style='color:#00BFFF;'>{selected_date}</span> στις <span style='color:#00BFFF;'>{selected_time}</span></h4>", unsafe_allow_html=True)
    
    # Ο ΧΑΡΤΗΣ ΕΙΝΑΙ ΣΙΓΟΥΡΑ Ο ΣΚΟΥΡΟΣ
    m = folium.Map(
        location=[38.2462, 21.7351], 
        zoom_start=14, 
        tiles='CartoDB dark_matter', 
        attr='CARTO'
    )

    for road_name, coords in geometry_data.items():
        speed = all_speeds_map.get(road_name, 0)
        current_coords = get_parallel_line(coords, dist_meters=3.5) if "_rev" in road_name.lower() else coords

        is_type_match = (selected_type == "Όλοι οι Τύποι" or road_types.get(road_name) == selected_type)
        if selected_road != "Όλες οι Οδοί":
            if road_name == selected_road: color, weight, opacity = get_hybrid_color(speed, road_name, selected_time), 8, 1.0
            else: color, weight, opacity = "#334155", 2, 0.4 
        else:
            if is_type_match: color, weight, opacity = get_hybrid_color(speed, road_name, selected_time), 5, 0.9
            else: color, weight, opacity = "#334155", 2, 0.4

        line = folium.PolyLine(locations=current_coords, color=color, weight=weight, opacity=opacity, tooltip=f"{road_name}: {speed} km/h").add_to(m)

        if selected_road != "Όλες οι Οδοί" and road_name == selected_road:
            PolyLineTextPath(line, f'  {road_name}  ', repeat=False, offset=8, attributes={'fill': '#FFFFFF', 'font-weight': 'bold', 'font-size': '16'}).add_to(m)

    st_folium(m, width=1300, height=550, key="network_map")
    st.markdown("<hr style='border: 1px solid rgba(255,255,255,0.1);'>", unsafe_allow_html=True)
    
    if selected_road == "Όλες οι Οδοί":
        if not filtered_view_df.empty:
            filtered_view_df['Type'] = filtered_view_df['Road_Segment'].map(road_types).fillna('Άγνωστο')
            filtered_view_df['Limit'] = filtered_view_df['Road_Segment'].apply(lambda x: static_data.get(x, 50))
            
            def is_congested(row):
                r_type, night_mode = str(row['Type']).lower(), is_night_time(selected_time)
                is_red = (row['Speed_kmh'] / row['Limit']) < 0.4 if "trunk" in r_type or "motorway" in r_type else row['Speed_kmh'] < 15
                return False if night_mode else is_red
                    
            filtered_view_df['Is_Congested'] = filtered_view_df.apply(is_congested, axis=1)
            filtered_view_df['Ratio'] = filtered_view_df.apply(lambda row: row['Speed_kmh'] / row['Limit'] if "trunk" in str(row['Type']).lower() else row['Speed_kmh'] / 50, axis=1)
            
            avg_speed = round(filtered_view_df['Speed_kmh'].mean(), 1)
            congested_count = filtered_view_df['Is_Congested'].sum()
            total_roads = len(filtered_view_df)
            worst_road_row = filtered_view_df.loc[filtered_view_df['Ratio'].idxmin()]
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🏎️ Μέση Ταχύτητα", f"{avg_speed} km/h")
            c2.metric("🚨 Συμφόρηση", f"{congested_count} / {total_roads} δρόμοι")
            c3.metric("📉 Ποσοστό", f"{round((congested_count/total_roads)*100, 1)}%")
            c4.metric("🤯 Χειρότερο Σημείο", f"{worst_road_row['Speed_kmh']} km/h", f"{worst_road_row['Road_Segment']}", delta_color="inverse")

            st.markdown("<br>", unsafe_allow_html=True)
            c_left, c_right = st.columns([1, 1])
            with c_left:
                st.markdown("#### 🚫 Top 5 Καθυστερήσεις")
                worst_5 = filtered_view_df.nsmallest(5, 'Ratio')[['Road_Segment', 'Speed_kmh', 'Type']].reset_index(drop=True)
                worst_5.columns = ["Όνομα Δρόμου", "Ταχύτητα (km/h)", "Τύπος"]
                st.dataframe(worst_5, use_container_width=True)
            with c_right:
                st.markdown("#### 🚦 Κατανομή Κυκλοφορίας")
                def categorize_hybrid(row):
                    speed, r_type = row['Speed_kmh'], str(row['Type']).lower()
                    night_mode = is_night_time(selected_time)
                    if "trunk" in r_type or "motorway" in r_type:
                        ratio = speed / row['Limit'] if row['Limit'] > 0 else 1
                        cat = 'Συμφόρηση' if ratio < 0.4 else 'Μέτρια' if ratio < 0.75 else 'Ελεύθερη'
                    else: cat = 'Συμφόρηση' if speed < 15 else 'Μέτρια' if speed < 30 else 'Ελεύθερη'
                    return ('Μέτρια' if cat == 'Συμφόρηση' else 'Ελεύθερη') if night_mode else cat
                        
                filtered_view_df['Traffic_Level'] = filtered_view_df.apply(categorize_hybrid, axis=1)
                pie_fig = px.pie(filtered_view_df, names='Traffic_Level', hole=0.6, color='Traffic_Level',
                                 color_discrete_map={'Συμφόρηση': '#EF4444', 'Μέτρια': '#F59E0B', 'Ελεύθερη': '#10B981'})
                pie_fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="#F8FAFC"), margin=dict(t=10, b=10, l=10, r=10), height=300)
                st.plotly_chart(pie_fig, use_container_width=True)

        st.markdown("<hr style='border: 1px solid rgba(255,255,255,0.1);'>", unsafe_allow_html=True)
        st.markdown("#### 📈 Ανάλυση ανά Τύπο Οδού")
        
        df_history['Type'] = df_history['Road_Segment'].map(road_types).fillna('Άγνωστο')
        df_types = df_history[df_history['Type'] != 'Άγνωστο'].copy()
        
        if not df_types.empty:
            df_types['Ώρα'] = df_types['Timestamp'].dt.strftime('%H:%M')
            type_grouped = df_types.groupby(['Ώρα', 'Type'])['Speed_kmh'].mean().reset_index().sort_values(by='Ώρα')
            
            fig_type = px.line(type_grouped, x="Ώρα", y="Speed_kmh", color="Type", markers=True)
            fig_type.update_traces(connectgaps=True)
            fig_type.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="#F8FAFC"),
                xaxis=dict(showgrid=False, tickangle=-45, nticks=24), yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
                hovermode="x unified", legend=dict(title="", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_type, use_container_width=True)
    else:
        df_road_day = df_day[df_day['Road_Segment'] == selected_road].sort_values('Time')
        if not df_road_day.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("⏱️ Ταχύτητα τώρα", f"{live_speeds.get(selected_road, 'N/A')} km/h")
            c2.metric("📈 Μέγιστη Σήμερα", f"{df_road_day['Speed_kmh'].max()} km/h")
            c3.metric("📉 Ελάχιστη Σήμερα", f"{df_road_day['Speed_kmh'].min()} km/h")
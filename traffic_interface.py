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

# 🔥 ΚΑΘΑΡΟ, ΕΠΑΓΓΕΛΜΑΤΙΚΟ LIGHT THEME (Google Style)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Καθαρό ανοιχτόχρωμο φόντο */
    .stApp { 
        background-color: #F8FAFC; 
        font-family: 'Inter', sans-serif; 
    }
    
    /* Μαύρα γράμματα παντού για τέλεια αναγνωσιμότητα */
    h1, h2, h3, h4, p, span, label, div { 
        color: #0F172A !important; 
        font-family: 'Inter', sans-serif; 
    }
    
    /* Κεντρικό Container (Λευκό με απαλή σκιά) */
    .block-container {
        background: #FFFFFF;
        border-radius: 16px;
        padding: 2rem !important;
        margin-top: 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border: 1px solid #E2E8F0;
    }

    /* Κάρτες Στατιστικών (Metrics) */
    div[data-testid="metric-container"] {
        background-color: #F1F5F9 !important; 
        border-radius: 12px; 
        padding: 20px;
        border: 1px solid #E2E8F0;
        box-shadow: none;
    }
    [data-testid="stMetricValue"] { font-size: 2.2rem !important; font-weight: 800; color: #0284C7 !important; }
    [data-testid="stMetricLabel"] { font-size: 1rem !important; color: #475569 !important; font-weight: 600 !important; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { 
        background-color: #FFFFFF !important; 
        border-right: 1px solid #E2E8F0; 
    }
    
    /* Tabs */
    button[data-baseweb="tab"] { font-size: 1.1rem; font-weight: 600; color: #64748B; background: transparent; }
    button[data-baseweb="tab"]:hover { color: #0F172A; }
    button[data-baseweb="tab"][aria-selected="true"] { 
        color: #0284C7 !important; 
        border-bottom: 3px solid #0284C7 !important; 
        background-color: #F0F9FF; 
    }

    /* Selectboxes */
    .stSelectbox > div > div { background-color: #FFFFFF; color: #0F172A; border-radius: 8px; border: 1px solid #CBD5E1; }
    .stSelectbox > div > div > div { color: #0F172A !important; }
    
    /* Dataframe */
    .stDataFrame { border-radius: 12px; border: 1px solid #E2E8F0; }
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
    st.markdown("<h4 style='color: #475569 !important; font-weight: 600; margin-bottom: -15px;'>ΠΑΝΕΠΙΣΤΗΜΙΟ ΠΑΤΡΩΝ</h4>", unsafe_allow_html=True)
    st.markdown("<h1 style='font-size: 2.8rem; font-weight: 800; color: #0F172A !important;'>Patras Traffic Analytics <span style='color: #0284C7 !important;'>PRO</span></h1>", unsafe_allow_html=True)

st.markdown("<hr style='border: 1px solid #E2E8F0; margin-top: 10px; margin-bottom: 30px;'>", unsafe_allow_html=True)

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
    st.markdown("<h3 style='text-align: center; color: #0F172A !important;'>⚙️ Κέντρο Ελέγχου</h3>", unsafe_allow_html=True)
    st.markdown("<hr style='border: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
    
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
    st.markdown(f"<h4>Αποτύπωση Κυκλοφορίας: <span style='color:#0284C7;'>{selected_date}</span> στις <span style='color:#0284C7;'>{selected_time}</span></h4>", unsafe_allow_html=True)
    
    # 🔥 ΕΠΙΣΤΡΟΦΗ ΣΤΟ ΚΛΑΣΙΚΟ GOOGLE MAPS
    m = folium.Map(
        location=[38.2462, 21.7351], 
        zoom_start=14, 
        tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', 
        attr='Google Maps'
    )

    for road_name, coords in geometry_data.items():
        speed = all_speeds_map.get(road_name, 0)
        current_coords = get_parallel_line(coords, dist_meters=3.5) if "_rev" in road_name.lower() else coords

        is_type_match = (selected_type == "Όλοι οι Τύποι" or road_types.get(road_name) == selected_type)
        if selected_road != "Όλες οι Οδοί":
            if road_name == selected_road: color, weight, opacity = get_hybrid_color(speed, road_name, selected_time), 8, 1.0
            else: color, weight, opacity = "#94A3B8", 3, 0.4 
        else:
            if is_type_match: color, weight, opacity = get_hybrid_color(speed, road_name, selected_time), 6, 0.9
            else: color, weight, opacity = "#94A3B8", 3, 0.4

        line = folium.PolyLine(locations=current_coords, color=color, weight=weight, opacity=opacity, tooltip=f"{road_name}: {speed} km/h").add_to(m)

        if selected_road != "Όλες οι Οδοί" and road_name == selected_road:
            # Μαύρα γράμματα πάνω στη γραμμή για να φαίνονται στο Google Maps
            PolyLineTextPath(line, f'  {road_name}  ', repeat=False, offset=8, attributes={'fill': '#000000', 'font-weight': 'bold', 'font-size': '16'}).add_to(m)

    st_folium(m, width=1300, height=550, key="network_map")
    st.markdown("<hr style='border: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
    
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
                pie_fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="#0F172A"), margin=dict(t=10, b=10, l=10, r=10), height=300)
                st.plotly_chart(pie_fig, use_container_width=True)

        st.markdown("<hr style='border: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
        st.markdown("#### 📈 Ανάλυση ανά Τύπο Οδού")
        
        df_history['Type'] = df_history['Road_Segment'].map(road_types).fillna('Άγνωστο')
        df_types = df_history[df_history['Type'] != 'Άγνωστο'].copy()
        
        if not df_types.empty:
            df_types['Ώρα'] = df_types['Timestamp'].dt.strftime('%H:%M')
            type_grouped = df_types.groupby(['Ώρα', 'Type'])['Speed_kmh'].mean().reset_index().sort_values(by='Ώρα')
            
            fig_type = px.line(type_grouped, x="Ώρα", y="Speed_kmh", color="Type", markers=True)
            fig_type.update_traces(connectgaps=True)
            fig_type.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="#0F172A"),
                xaxis=dict(showgrid=False, tickangle=-45, nticks=24), yaxis=dict(showgrid=True, gridcolor='#E2E8F0'),
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
            
            city_avg = df_day.groupby('Time')['Speed_kmh'].mean().reset_index().rename(columns={'Speed_kmh': 'Μέσος Όρος Πόλης'})
            plot_df = pd.merge(df_road_day[['Time', 'Speed_kmh']], city_avg, on='Time', how='outer').sort_values('Time').rename(columns={'Speed_kmh': f'Επιλεγμένη Οδός'})
            plot_df_melted = plot_df.melt(id_vars=['Time'], value_vars=[f'Επιλεγμένη Οδός', 'Μέσος Όρος Πόλης'], var_name='Δείκτης', value_name='Ταχύτητα (km/h)')
            
            fig_road_line = px.line(plot_df_melted, x='Time', y='Ταχύτητα (km/h)', color='Δείκτης', markers=True, color_discrete_map={f'Επιλεγμένη Οδός': '#0284C7', 'Μέσος Όρος Πόλης': '#94A3B8'})
            fig_road_line.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="#0F172A"), xaxis=dict(gridcolor="#E2E8F0"), yaxis=dict(gridcolor="#E2E8F0"), legend=dict(title="", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_road_line, use_container_width=True)

# ================= TAB 2 =================
with tab2:
    c_btn, c_inf = st.columns([1, 4])
    with c_btn:
        if st.button("🔄 Καθαρισμός Σημείων"):
            st.session_state.start_point, st.session_state.end_point = None, None
            st.rerun()
        
    # 🔥 GOOGLE MAPS
    m_click = folium.Map(
        location=[38.2462, 21.7351], 
        zoom_start=14, 
        tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', 
        attr='Google Maps'
    )
    for road_name, coords in geometry_data.items():
        folium.PolyLine(locations=coords, color="#0284C7", weight=4, opacity=0.4, tooltip=f"Άξονας: {road_name}").add_to(m_click)
    
    if st.session_state.start_point: folium.Marker(st.session_state.start_point, icon=folium.Icon(color="green", icon="play")).add_to(m_click)
    if st.session_state.end_point: folium.Marker(st.session_state.end_point, icon=folium.Icon(color="red", icon="stop")).add_to(m_click)
        
    map_data = st_folium(m_click, width=1300, height=500, key="click_selector_map")
    
    if map_data and map_data.get("last_clicked"):
        clicked_coords = [map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]]
        if st.session_state.start_point is None:
            st.session_state.start_point = clicked_coords
            st.rerun()
        elif st.session_state.end_point is None and clicked_coords != st.session_state.start_point:
            st.session_state.end_point = clicked_coords
            st.rerun()
            
    c_out1, c_out2 = st.columns(2)
    with c_out1: st.markdown(f"<div style='background-color:#F1F5F9; padding:15px; border-radius:8px; border: 1px solid #E2E8F0; border-left:4px solid #10B981;'>🟢 <b style='color:#0F172A;'>Αφετηρία:</b> <span style='color:#475569;'>{st.session_state.start_point if st.session_state.start_point else 'Εκκρεμεί...'}</span></div>", unsafe_allow_html=True)
    with c_out2: st.markdown(f"<div style='background-color:#F1F5F9; padding:15px; border-radius:8px; border: 1px solid #E2E8F0; border-left:4px solid #EF4444;'>🔴 <b style='color:#0F172A;'>Προορισμός:</b> <span style='color:#475569;'>{st.session_state.end_point if st.session_state.end_point else 'Εκκρεμεί...'}</span></div>", unsafe_allow_html=True)

    if st.session_state.start_point and st.session_state.end_point:
        s_str = f"{st.session_state.start_point[0]},{st.session_state.start_point[1]}"
        e_str = f"{st.session_state.end_point[0]},{st.session_state.end_point[1]}"
        url = f"https://api.tomtom.com/routing/1/calculateRoute/{s_str}:{e_str}/json"
        try:
            with st.spinner('Υπολογισμός βέλτιστης διαδρομής...'):
                res_data = requests.get(url, params={'key': random.choice(API_KEYS), 'traffic': 'true', 'routeType': 'fastest', 'travelMode': 'car', 'sectionType': 'traffic'}, timeout=10).json()
            if 'routes' in res_data:
                summary, points, sections = res_data['routes'][0]['summary'], res_data['routes'][0]['legs'][0]['points'], res_data['routes'][0].get('sections', [])
                time_min, distance_km = round(summary.get('travelTimeInSeconds', 0)/60, 1), round(summary.get('lengthInMeters', 0)/1000, 2)
                calc_speed = round((distance_km) / (summary.get('travelTimeInSeconds', 1)/3600), 1)
                
                st.markdown("---")
                res_col1, res_col2, res_col3 = st.columns(3)
                res_col1.metric("⏱️ Χρόνος", f"{time_min} λεπτά")
                res_col2.metric("🏎️ Ταχύτητα", f"{calc_speed} km/h")
                res_col3.metric("📏 Απόσταση", f"{distance_km} km")
                
                route_coords = [[p['latitude'], p['longitude']] for p in points]
                
                # 🔥 GOOGLE MAPS 
                m_res = folium.Map(
                    location=route_coords[0], 
                    zoom_start=14, 
                    tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', 
                    attr='Google Maps'
                )
                
                for road_name, coords in geometry_data.items():
                    speed = live_speeds.get(road_name, static_data.get(road_name, 0))
                    folium.PolyLine(locations=coords, color=get_hybrid_color(speed, road_name, selected_time), weight=3, opacity=0.4).add_to(m_res)

                folium.PolyLine(locations=route_coords, color="#0284C7", weight=8, opacity=0.9).add_to(m_res)
                for sec in sections:
                    if sec.get('sectionType') == 'TRAFFIC':
                        s_idx, e_idx, mag = sec.get('startPointIndex', 0), sec.get('endPointIndex', len(route_coords)-1), sec.get('magnitudeOfDelay', 0)
                        t_color = "#EF4444" if mag >= 3 else "#F59E0B" if mag > 0 else "#10B981"
                        folium.PolyLine(locations=route_coords[s_idx:e_idx+1], color=t_color, weight=8, opacity=1.0).add_to(m_res)

                folium.Marker(location=route_coords[0], icon=folium.Icon(color="green", icon="play")).add_to(m_res)
                folium.Marker(location=route_coords[-1], icon=folium.Icon(color="red", icon="stop")).add_to(m_res)
                st_folium(m_res, width=1300, height=450, key="result_route_map")
        except: st.error("Αποτυχία σύνδεσης API.")

# ================= TAB 3 =================
with tab3:
    st.markdown("#### 📅 Εβδομαδιαίος Χάρτης Συμφόρησης (Heatmap)")
    df_heat = df_history.copy()
    df_heat.loc[df_heat['Speed_kmh'] < 2, 'Speed_kmh'] = 25.0
    
    if selected_type != "Όλοι οι Τύποι": df_heat = df_heat[df_heat['Road_Segment'].map(road_types) == selected_type]
    if selected_road != "Όλες οι Οδοί": df_heat = df_heat[df_heat['Road_Segment'] == selected_road]
        
    if not df_heat.empty:
        df_heat['Limit'] = df_heat['Road_Segment'].apply(lambda r: static_data.get(r, 50))
        df_heat['Congestion'] = (((df_heat['Limit'] - df_heat['Speed_kmh']) / df_heat['Limit']) * 100).clip(lower=0)
        df_heat['Ημέρα'] = df_heat['Timestamp'].dt.dayofweek.map({0:'Δευτέρα', 1:'Τρίτη', 2:'Τετάρτη', 3:'Πέμπτη', 4:'Παρασκευή', 5:'Σάββατο', 6:'Κυριακή'})
        df_heat['Μισάωρο'] = df_heat['Timestamp'].dt.floor('30min').dt.strftime('%H:%M')
        
        heatmap_data = df_heat.groupby(['Ημέρα', 'Μισάωρο'])['Congestion'].mean().reset_index()
        pivot_df = heatmap_data.pivot(index='Μισάωρο', columns='Ημέρα', values='Congestion').reindex(columns=['Δευτέρα', 'Τρίτη', 'Τετάρτη', 'Πέμπτη', 'Παρασκευή', 'Σάββατο', 'Κυριακή']).reindex([f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]).dropna(how='all').interpolate(method='linear', limit=4, limit_area='inside')
        
        if not pivot_df.empty:
            c1, c2, c3 = st.columns(3)
            peak_row = heatmap_data.loc[heatmap_data['Congestion'].idxmax()]
            c1.metric("🔥 Απόλυτη Αιχμή", f"{peak_row['Congestion']:.1f}%", f"{peak_row['Ημέρα']} στις {peak_row['Μισάωρο']}", delta_color="inverse")
            day_avg = heatmap_data.groupby('Ημέρα')['Congestion'].mean()
            c2.metric("📅 Δυσκολότερη Μέρα", f"{day_avg.max():.1f}%", f"Μ.Ο: {day_avg.idxmax()}", delta_color="inverse")
            best_row = heatmap_data.loc[heatmap_data['Congestion'].idxmin()]
            c3.metric("✅ Πιο Ήσυχη Ώρα", f"{best_row['Congestion']:.1f}%", f"{best_row['Ημέρα']} στις {best_row['Μισάωρο']}", delta_color="normal")

            dramatic_scale = [[0.0, "#10B981"], [0.35, "#F59E0B"], [0.55, "#EF4444"], [0.8, "#991B1B"], [1.0, "#4C1D95"]]
            fig_heat = px.imshow(pivot_df, labels=dict(x="Ημέρα", y="Ώρα", color="Συμφόρηση (%)"), x=pivot_df.columns, y=pivot_df.index, color_continuous_scale=dramatic_scale, range_color=[20, 70], text_auto=".0f", aspect="auto", height=700)
            fig_heat.update_traces(xgap=4, ygap=4, texttemplate="%{z:.0f}%")
            fig_heat.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="#0F172A"), xaxis=dict(side="top"), yaxis=dict(autorange="reversed"), coloraxis_colorbar=dict(title="%"))
            st.plotly_chart(fig_heat, use_container_width=True)
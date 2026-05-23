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

# 1. Ρυθμίσεις σελίδας - Modern Theme
st.set_page_config(page_title="Patras Traffic Analytics PRO", page_icon="🚦", layout="wide")

# 🔥 CUSTOM CSS ΓΙΑ MODERN ΕΜΦΑΝΙΣΗ
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #E0E0E0; }
    h1, h2, h3, h4 { color: #FFFFFF !important; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    [data-testid="stMetricValue"] { font-size: 2.8rem !important; font-weight: 700; color: #00BFFF; }
    [data-testid="stMetricLabel"] { font-size: 1.1rem !important; color: #BDBDBD !important; font-weight: 400 !important; }
    div[data-testid="metric-container"] {
        background-color: #1E1E1E; border-radius: 15px; padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); border: 1px solid #333333;
    }
    [data-testid="stSidebar"] { background-color: #16191F; border-right: 1px solid #333333; }
    button[data-baseweb="tab"] { font-size: 1.1rem; font-weight: 600; color: #BDBDBD; }
    button[data-baseweb="tab"][aria-selected="true"] { color: #00BFFF !important; border-bottom-color: #00BFFF !important; }
    .stDataFrame { border-radius: 15px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); }
    .stSelectbox, .stSlider { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("🚦 Patras Traffic Analytics PRO")
st.markdown("---")

if 'start_point' not in st.session_state: st.session_state.start_point = None
if 'end_point' not in st.session_state: st.session_state.end_point = None

# --- ΚΟΙΝΕΣ ΣΥΝΑΡΤΗΣΕΙΣ ---
to_mercator = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
to_wgs84 = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

def get_center(coords):
    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    return (sum(lats)/len(lats), sum(lons)/len(lons))

def get_parallel_line(coords, dist_meters=2.0): 
    try:
        xy_pairs = [(c[1], c[0]) for c in coords]
        if len(xy_pairs) < 2: return coords
        projected_xy = [to_mercator.transform(x, y) for x, y in xy_pairs]
        line = LineString(projected_xy)
        offset_line = line.parallel_offset(dist_meters, side='right', join_style=1) 
        
        coords_out_xy = []
        if offset_line.geom_type == 'MultiLineString':
            for sub_line in offset_line.geoms: coords_out_xy.extend(list(sub_line.coords))
        else:
            coords_out_xy = list(offset_line.coords)
        if len(coords_out_xy) < 2: return coords
        unprojected_xy = [to_wgs84.transform(x, y) for x, y in coords_out_xy]
        return [[y, x] for x, y in unprojected_xy]
    except:
        return coords

# Φορτώνουμε το CSV με cache για να μην κολλάει η εφαρμογή
@st.cache_data
def load_csv_data():
    if not os.path.exists("live_traffic_data.csv"):
        return None
    df = pd.read_csv("live_traffic_data.csv", sep=";")
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='mixed', errors='coerce')
    df['Date'] = df['Timestamp'].dt.date
    df['Time'] = df['Timestamp'].dt.strftime('%H:%M')
    return df

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

def get_hybrid_color(speed, road_name):
    if pd.isna(speed) or speed == 0: return "#7f8c8d" 
    r_type = road_types.get(road_name, "").lower()
    if "trunk" in r_type or "motorway" in r_type:
        limit = static_data.get(road_name, 90)
        ratio = speed / limit if limit > 0 else 1
        if ratio < 0.4: return "#EF5350"
        if ratio < 0.75: return "#FFCA28"
        return "#66BB6A"
    else:
        if speed < 15: return "#EF5350"
        if speed < 30: return "#FFCA28"
        return "#66BB6A"

# --- 3. Φόρτωση Γεωμετρίας & CSV ---
if not os.path.exists("road_geometry.json"):
    st.error("❌ Λείπει το αρχείο 'road_geometry.json'! Τρέξτε πρώτα το setupgeometry.py")
    st.stop()

with open("road_geometry.json", "r", encoding="utf-8") as f:
    geometry_data = json.load(f)

df_history = load_csv_data()
if df_history is None:
    st.warning("⏳ Αναμονή για δεδομένα από το Bot...")
    st.stop()

API_KEYS = [
    "UsA5r09FOSV6PmRd4NZFF3JCW3y6N2o1", 
    "Nz9zgm9uxG3Pd70dK2OYvEtdktn8PQSD",
    "IP2weRLSvXxstW414lUcWWSks3qwrGYR", 
    "V8V7MYwbnjA6y0YJj8V46mkxvXRM9Uz9"
]

# --- 4. SIDEBAR ---
with st.sidebar:
    st.markdown("## ⚙️ Κέντρο Ελέγχου")
    st.markdown("---")
    available_dates = sorted(df_history['Date'].dropna().unique())
    if not available_dates:
        st.error("Σφάλμα: Το CSV δεν έχει έγκυρες ημερομηνίες!")
        st.stop()

    selected_date = st.selectbox("📅 Επιλέξτε μέρα:", options=available_dates, index=len(available_dates)-1)
    df_day = df_history[df_history['Date'] == selected_date]
    available_times = sorted(df_day['Time'].dropna().unique())

    if not available_times:
        st.warning("Δεν βρέθηκαν καταγραφές για αυτή τη μέρα.")
        st.stop()

    selected_time = st.selectbox("⏱️ Επιλέξτε ώρα:", options=available_times, index=len(available_times)-1)
    st.markdown("---")
    
    unique_types = ["Όλοι οι Τύποι"] + sorted(list(set(road_types.values()))) if road_types else ["Όλοι οι Τύποι"]
    selected_type = st.selectbox("🛤️ Επιλέξτε τύπο:", options=unique_types, index=0)
    st.markdown("---")

    available_roads_for_step4 = [r for r in geometry_data.keys() if selected_type == "Όλοι οι Τύποι" or road_types.get(r) == selected_type]
    all_roads = ["Όλες οι Οδοί"] + sorted(available_roads_for_step4)
    selected_road = st.selectbox("📍 Επιλέξτε δρόμο:", options=all_roads, index=0)
    st.markdown("---")
    
    past_mask = (df_history['Date'] < selected_date) | ((df_history['Date'] == selected_date) & (df_history['Time'] <= selected_time))
    all_current_df = df_history[past_mask].drop_duplicates(subset=['Road_Segment'], keep='last')
    
    live_speeds = dict(zip(all_current_df['Road_Segment'], all_current_df['Speed_kmh']))
    
    # 🔥 1. ΑΦΑΙΡΕΣΗ ΟΛΩΝ ΤΩΝ ΜΗΔΕΝΙΚΩΝ (Γκρι δρόμων)
    roads_to_remove = []
    for road, speed in live_speeds.items():
        try:
            val = float(speed)
        except:
            val = 0.0
            
        if val <= 0.5: 
            roads_to_remove.append(road)

    for road in roads_to_remove:
        del live_speeds[road]
        
    live_centers = {}
    for r_name in live_speeds.keys():
        if r_name in geometry_data:
            live_centers[r_name] = get_center(geometry_data[r_name])

    dynamic_secondary_speeds = {}
    
    # 🔥 ΑΛΛΑΓΗ-ΚΛΕΙΔΙ: Ψάχνει κατευθείαν στον χάρτη (geometry_data)
    for r_name in geometry_data.keys():
        if r_name not in live_speeds:
            static_speed = static_data.get(r_name, 50) 
            center_sec = get_center(geometry_data[r_name])
            
            distances = []
            for live_name, center_live in live_centers.items():
                dist_sq = (center_sec[0] - center_live[0])**2 + (center_sec[1] - center_live[1])**2
                distances.append((dist_sq, live_name))
            
            distances.sort()
            
            if "_rev" in str(r_name).lower():
                closest_live = distances[:1]
            else:
                closest_live = distances[:3]
            
            if closest_live:
                local_ratios = []
                for _, l_name in closest_live:
                    l_speed = live_speeds[l_name]
                    l_limit = static_data.get(l_name, 50)
                    if l_limit > 0:
                        local_ratios.append(min(l_speed / l_limit, 1.0))
                local_health_factor = sum(local_ratios) / len(local_ratios)
            else:
                local_health_factor = 1.0 
            
            adjusted_speed = max(static_speed * local_health_factor, 5.0)
            dynamic_secondary_speeds[r_name] = round(adjusted_speed, 1)
            
    all_speeds_map = {**live_speeds, **dynamic_secondary_speeds}
    filtered_view_df = all_current_df.copy()
    if selected_type != "Όλοι οι Τύποι":
        filtered_view_df['Type'] = filtered_view_df['Road_Segment'].map(road_types)
        filtered_view_df = filtered_view_df[filtered_view_df['Type'] == selected_type]
        
    st.metric(label="📊 Ενεργές Live Μετρήσεις", value=len(filtered_view_df))

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["🗺️ Ανάλυση Δικτύου & Χάρτης", "🔬 Υπολογισμός Διαδρομής", "📅 Εβδομαδιαίο Heatmap"])

# ================= TAB 1 =================
with tab1:
    st.markdown(f"### 📍 Αποτύπωση Κυκλοφορίας: {selected_date} στις {selected_time}")
    
    m = folium.Map(
        location=[38.2462, 21.7351], 
        zoom_start=14, 
        tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', 
        attr='Google Maps'
    )

    for road_name, coords in geometry_data.items():
        speed = all_speeds_map.get(road_name, 0)
        current_coords = coords
        
        if "_rev" in road_name.lower():
            try: current_coords = get_parallel_line(coords, dist_meters=3.5)
            except: pass

        is_type_match = (selected_type == "Όλοι οι Τύποι" or road_types.get(road_name) == selected_type)
        if selected_road != "Όλες οι Οδοί":
            if road_name == selected_road: color, weight, opacity = get_hybrid_color(speed, road_name), 8, 1.0
            else: color, weight, opacity = "#333333", 2, 0.15 
        else:
            if is_type_match: color, weight, opacity = get_hybrid_color(speed, road_name), 5, 0.9
            else: color, weight, opacity = "#333333", 2, 0.15

        line = folium.PolyLine(
            locations=current_coords, 
            color=color, 
            weight=weight, 
            opacity=opacity, 
            tooltip=f"{road_name}: {speed} km/h"
        ).add_to(m)

        if selected_road != "Όλες οι Οδοί" and road_name == selected_road:
            PolyLineTextPath(
                line,
                f'  {road_name}  ',
                repeat=False,
                offset=8,
                attributes={'fill': '#000000', 'font-weight': 'bold', 'font-size': '16'}
            ).add_to(m)

    st_folium(m, width=1300, height=550, key="network_map")
    st.markdown("---")
    
    if selected_road == "Όλες οι Οδοί":
        st.markdown(f"### 📊 Αναλυτική Αναφορά Στιγμής (Φίλτρο: {selected_type})")
        if not filtered_view_df.empty:
            
            filtered_view_df['Type'] = filtered_view_df['Road_Segment'].map(road_types).fillna('Άγνωστο')
            filtered_view_df['Limit'] = filtered_view_df['Road_Segment'].apply(lambda x: static_data.get(x, 50))
            
            def is_congested(row):
                r_type = str(row['Type']).lower()
                if "trunk" in r_type or "motorway" in r_type:
                    return (row['Speed_kmh'] / row['Limit']) < 0.4 if row['Limit'] > 0 else False
                else:
                    return row['Speed_kmh'] < 15
                    
            filtered_view_df['Is_Congested'] = filtered_view_df.apply(is_congested, axis=1)
            
            def calc_health_ratio(row):
                r_type = str(row['Type']).lower()
                if "trunk" in r_type or "motorway" in r_type:
                    return row['Speed_kmh'] / row['Limit'] if row['Limit'] > 0 else 1
                else:
                    return row['Speed_kmh'] / 50 
                    
            filtered_view_df['Ratio'] = filtered_view_df.apply(calc_health_ratio, axis=1)
            
            avg_speed = round(filtered_view_df['Speed_kmh'].mean(), 1)
            congested_count = filtered_view_df['Is_Congested'].sum()
            total_roads = len(filtered_view_df)
            worst_road_row = filtered_view_df.loc[filtered_view_df['Ratio'].idxmin()]
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🏎️ Μέση Ταχύτητα", f"{avg_speed} km/h")
            c2.metric("🚨 Κόκκινοι Δρόμοι", f"{congested_count} / {total_roads}")
            c3.metric("📉 % Συμφόρησης", f"{round((congested_count/total_roads)*100, 1)}%")
            c4.metric("🤯 Χειρότερος Δρόμος", f"{worst_road_row['Speed_kmh']} km/h", f"{worst_road_row['Road_Segment']}", delta_color="inverse")

            st.markdown("<br>", unsafe_allow_html=True)
            c_left, c_right = st.columns([1, 1])
            with c_left:
                st.markdown("#### 🚫 Top 5 Μποτιλιαρίσματα")
                worst_5 = filtered_view_df.nsmallest(5, 'Ratio')[['Road_Segment', 'Speed_kmh', 'Type']].reset_index(drop=True)
                worst_5.columns = ["Όνομα Δρόμου", "Ταχύτητα (km/h)", "Τύπος"]
                st.dataframe(worst_5, use_container_width=True)
            with c_right:
                st.markdown("#### 🚦 Κατανομή Κυκλοφορίας")
                def categorize_hybrid(row):
                    speed = row['Speed_kmh']
                    r_type = str(row['Type']).lower()
                    if "trunk" in r_type or "motorway" in r_type:
                        ratio = speed / row['Limit'] if row['Limit'] > 0 else 1
                        if ratio < 0.4: return 'Συμφόρηση'
                        if ratio < 0.75: return 'Μέτρια'
                        return 'Ελεύθερη'
                    else:
                        if speed < 15: return 'Συμφόρηση'
                        if speed < 30: return 'Μέτρια'
                        return 'Ελεύθερη'
                        
                filtered_view_df['Traffic_Level'] = filtered_view_df.apply(categorize_hybrid, axis=1)
                pie_fig = px.pie(filtered_view_df, names='Traffic_Level', hole=0.5, color='Traffic_Level',
                                 color_discrete_map={'Συμφόρηση': '#EF5350', 'Μέτρια': '#FFCA28', 'Ελεύθερη': '#66BB6A'})
                pie_fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"), margin=dict(t=10, b=10, l=10, r=10), height=280)
                st.plotly_chart(pie_fig, use_container_width=True)

        st.markdown("---")
        st.markdown("### 📈 Συγκριτική Ανάλυση ανά Τύπο Οδού")
        st.caption("Πώς συμπεριφέρονται οι διαφορετικές κατηγορίες δρόμων μέσα στη μέρα.")
        
        df_history['Type'] = df_history['Road_Segment'].map(road_types).fillna('Άγνωστο')
        df_types = df_history[df_history['Type'] != 'Άγνωστο'].copy()
        
        if not df_types.empty:
            df_types['Ώρα'] = df_types['Timestamp'].dt.strftime('%H:%M')
            type_grouped = df_types.groupby(['Ώρα', 'Type'])['Speed_kmh'].mean().reset_index()
            type_grouped = type_grouped.sort_values(by='Ώρα')
            
            fig_type = px.line(
                type_grouped, 
                x="Ώρα", 
                y="Speed_kmh", 
                color="Type",
                labels={"Speed_kmh": "Μέση Ταχύτητα (km/h)", "Ώρα": "Ώρα", "Type": "Τύπος Οδού"},
                markers=True
            )
            
            fig_type.update_traces(connectgaps=True)
            
            fig_type.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(10,10,10,0.5)',
                font=dict(color="#DFE6E9"),
                xaxis=dict(
                    showgrid=False, 
                    tickangle=-45, 
                    nticks=24 
                ),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
                hovermode="x unified"
            )
            st.plotly_chart(fig_type, use_container_width=True)
        else:
            st.info("ℹ️ Δεν υπάρχουν αρκετά δεδομένα για τη συγκριτική ανάλυση.")
    else:
        st.markdown(f"### 📊 Λεπτομερής Ανάλυση: `{selected_road}`")
        df_road_day = df_day[df_day['Road_Segment'] == selected_road].sort_values('Time')
        
        if not df_road_day.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("⏱️ Ταχύτητα τώρα", f"{live_speeds.get(selected_road, 'N/A')} km/h")
            c2.metric("📈 Μέγιστη Σήμερα", f"{df_road_day['Speed_kmh'].max()} km/h")
            c3.metric("📉 Ελάχιστη Σήμερα", f"{df_road_day['Speed_kmh'].min()} km/h")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            city_avg = df_day.groupby('Time')['Speed_kmh'].mean().reset_index()
            city_avg.rename(columns={'Speed_kmh': 'Μέσος Όρος Πόλης'}, inplace=True)
            
            plot_df = pd.merge(df_road_day[['Time', 'Speed_kmh']], city_avg, on='Time', how='outer').sort_values('Time')
            plot_df.rename(columns={'Speed_kmh': f'Επιλεγμένη Οδός'}, inplace=True)
            
            plot_df_melted = plot_df.melt(id_vars=['Time'], value_vars=[f'Επιλεγμένη Οδός', 'Μέσος Όρος Πόλης'], 
                                          var_name='Δείκτης', value_name='Ταχύτητα (km/h)')
            
            fig_road_line = px.line(plot_df_melted, x='Time', y='Ταχύτητα (km/h)', color='Δείκτης', markers=True,
                                    color_discrete_map={f'Επιλεγμένη Οδός': '#00BFFF', 'Μέσος Όρος Πόλης': '#7f8c8d'})
            
            fig_road_line.update_traces(marker=dict(size=6))

            fig_road_line.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,10,10,0.5)', font=dict(color="white"),
                xaxis=dict(gridcolor="#333"), yaxis=dict(gridcolor="#333"),
                legend=dict(title="", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_road_line, use_container_width=True)
        else:
            st.warning("⚠️ Δεν υπάρχουν επαρκή δεδομένα για αυτή την οδό σήμερα.")

# ================= TAB 2 =================
with tab2:
    st.markdown("### 🔬 Εύρεση Βέλτιστης Διαδρομής (Από το Α στο Β)")
    st.caption("💡 Οδηγός: Επιλέξτε αφετηρία και προορισμό από τα μενού, ή κλικάρετε πάνω στις διακριτικές μπλε γραμμές του χάρτη.")
    
    # Λίστα με όλους τους διαθέσιμους δρόμους για τα dropdowns
    available_route_roads = sorted(list(geometry_data.keys()))
    
    # Μενού Επιλογής
    c_sel1, c_sel2 = st.columns(2)
    with c_sel1:
        dropdown_start = st.selectbox("🟢 Επιλογή Αφετηρίας (Σημείο Α):", ["Χειροκίνητα στο χάρτη..."] + available_route_roads)
    with c_sel2:
        dropdown_end = st.selectbox("🔴 Επιλογή Προορισμού (Σημείο Β):", ["Χειροκίνητα στο χάρτη..."] + available_route_roads)

    # Κουμπί Καθαρισμού
    if st.button("🔄 Καθαρισμός Σημείων", use_container_width=True):
        st.session_state.start_point = None
        st.session_state.end_point = None
        st.rerun()

    # Ενημέρωση των σημείων από τα dropdowns
    if dropdown_start != "Χειροκίνητα στο χάρτη...":
        st.session_state.start_point = get_center(geometry_data[dropdown_start])
    if dropdown_end != "Χειροκίνητα στο χάρτη...":
        st.session_state.end_point = get_center(geometry_data[dropdown_end])

    # Χάρτης επιλογής 
    m_click = folium.Map(
        location=[38.2462, 21.7351], 
        zoom_start=14, 
        tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', 
        attr='Google Maps'
    )
    
    for road_name, coords in geometry_data.items():
        folium.PolyLine(locations=coords, color="#0066CC", weight=3, opacity=0.5, tooltip=f"Άξονας: {road_name}").add_to(m_click)
    
    if st.session_state.start_point:
        folium.Marker(st.session_state.start_point, popup="Αφετηρία", icon=folium.Icon(color="green", icon="play")).add_to(m_click)
    if st.session_state.end_point:
        folium.Marker(st.session_state.end_point, popup="Προορισμός", icon=folium.Icon(color="red", icon="stop")).add_to(m_click)
        
    map_data = st_folium(m_click, width=1300, height=400, key="click_selector_map")
    
    # Λογική κλικ στον χάρτη
    if map_data and map_data.get("last_clicked"):
        clicked_coords = [map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]]
        if st.session_state.start_point is None:
            st.session_state.start_point = clicked_coords
            st.rerun()
        elif st.session_state.end_point is None and clicked_coords != st.session_state.start_point:
            st.session_state.end_point = clicked_coords
            st.rerun()
            
    # Προβολή επιλεγμένων συντεταγμένων
    c_out1, c_out2 = st.columns(2)
    with c_out1:
        st.markdown(f"<div style='background-color: #1E1E1E; padding: 15px; border-radius: 10px; border-left: 5px solid #66BB6A;'>🟢 <b>Αφετηρία:</b> {st.session_state.start_point if st.session_state.start_point else 'Εκκρεμεί...'}</div>", unsafe_allow_html=True)
    with c_out2:
        st.markdown(f"<div style='background-color: #1E1E1E; padding: 15px; border-radius: 10px; border-left: 5px solid #EF5350;'>🔴 <b>Προορισμός:</b> {st.session_state.end_point if st.session_state.end_point else 'Εκκρεμεί...'}</div>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)

    # Υπολογισμός Βέλτιστης Διαδρομής
    if st.session_state.start_point and st.session_state.end_point:
        s_str = f"{st.session_state.start_point[0]},{st.session_state.start_point[1]}"
        e_str = f"{st.session_state.end_point[0]},{st.session_state.end_point[1]}"
        
        url = f"https://api.tomtom.com/routing/1/calculateRoute/{s_str}:{e_str}/json"
        params = {
            'key': random.choice(API_KEYS), 
            'traffic': 'true', 
            'routeType': 'fastest', 
            'travelMode': 'car', 
            'sectionType': 'traffic'
        }
        
        try:
            with st.spinner('🔭 Υπολογισμός βέλτιστης διαδρομής με βάση τη live κίνηση...'):
                response = requests.get(url, params=params, timeout=10)
                res_data = response.json()
                
            if response.status_code == 200 and 'routes' in res_data:
                summary = res_data['routes'][0]['summary']
                points = res_data['routes'][0]['legs'][0]['points']
                sections = res_data['routes'][0].get('sections', [])
                
                time_min = round(summary.get('travelTimeInSeconds', 0) / 60, 1)
                distance_km = round(summary.get('lengthInMeters', 0) / 1000, 2)
                delay_sec = summary.get('trafficDelayInSeconds', 0)
                calc_speed = round((summary.get('lengthInMeters', 0) / 1000) / (summary.get('travelTimeInSeconds', 1) / 3600), 1)
                
                st.markdown("---")
                st.markdown("#### 🏆 Αποτελέσματα Βέλτιστης Διαδρομής")
                
                res_col1, res_col2, res_col3 = st.columns(3)
                res_col1.metric("⏱️ Χρόνος Άφιξης", f"{time_min} λεπτά", f"Καθυστέρηση κίνησης: {delay_sec} δευτ.", delta_color="inverse")
                res_col2.metric("🏎️ Μέση Ταχύτητα", f"{calc_speed} km/h")
                res_col3.metric("📏 Συνολική Απόσταση", f"{distance_km} km")
                
                route_coords = [[p['latitude'], p['longitude']] for p in points]
                
                m_res = folium.Map(
                    location=route_coords[0], 
                    zoom_start=14, 
                    tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', 
                    attr='Google Maps'
                )
                
                for road_name, coords in geometry_data.items():
                    speed = live_speeds.get(road_name, static_data.get(road_name, 0))
                    c = get_hybrid_color(speed, road_name)
                    folium.PolyLine(locations=coords, color=c, weight=2, opacity=0.2).add_to(m_res)

                folium.PolyLine(locations=route_coords, color="#00BFFF", weight=7, opacity=0.8).add_to(m_res)
                
                for sec in sections:
                    if sec.get('sectionType') == 'TRAFFIC':
                        s_idx = sec.get('startPointIndex', 0)
                        e_idx = sec.get('endPointIndex', len(route_coords)-1)
                        mag = sec.get('magnitudeOfDelay', 0)
                        
                        if mag >= 3: t_color = "#EF5350"
                        elif mag > 0: t_color = "#FFCA28"
                        else: t_color = "#66BB6A"
                        
                        sec_coords = route_coords[s_idx:e_idx+1]
                        folium.PolyLine(locations=sec_coords, color=t_color, weight=7, opacity=1.0).add_to(m_res)

                folium.Marker(location=route_coords[0], icon=folium.Icon(color="green", icon="play")).add_to(m_res)
                folium.Marker(location=route_coords[-1], icon=folium.Icon(color="red", icon="stop")).add_to(m_res)
                
                st_folium(m_res, width=1300, height=450, key="result_route_map")
            else:
                st.error("Σφάλμα API: Δεν βρέθηκε διαδρομή. Δοκιμάστε να κάνετε κλικ πιο κοντά στις γραμμές.")
        except Exception as e:
            st.error(f"Αποτυχία σύνδεσης: {e}")

# ================= TAB 3: HEATMAP  =================
with tab3:
    st.markdown("### 📅 Εβδομαδιαίος Χάρτης Συμφόρησης (Congestion Heatmap) - Ανάλυση ανά Μισάωρο")
    st.caption("Πίνακας αιχμής: Δείχνει το μέσο ποσοστό συμφόρησης (%) ανά ημέρα και μισάωρο. Η ανανέωση γίνεται δυναμικά με βάση τα φίλτρα τύπου οδού και δρόμου από το Sidebar.")
    
    df_heat = df_history.copy()
    
    # 🛠️ ΕΞΥΠΝΟ ΦΙΛΤΡΟ: Αγνοεί τα μηδενικά από 403 API errors
    df_heat.loc[df_heat['Speed_kmh'] < 2, 'Speed_kmh'] = 25.0
    
    if selected_type != "Όλοι οι Τύποι":
        df_heat['Type'] = df_heat['Road_Segment'].map(road_types)
        df_heat = df_heat[df_heat['Type'] == selected_type]
    if selected_road != "Όλες οι Οδοί":
        df_heat = df_heat[df_heat['Road_Segment'] == selected_road]
        
    if not df_heat.empty:
        def get_limit(road):
            return static_data.get(road, 50) 
        
        df_heat['Limit'] = df_heat['Road_Segment'].apply(get_limit)
        df_heat['Congestion'] = ((df_heat['Limit'] - df_heat['Speed_kmh']) / df_heat['Limit']) * 100
        df_heat['Congestion'] = df_heat['Congestion'].clip(lower=0) 
        
        df_heat['DayOfWeek'] = df_heat['Timestamp'].dt.dayofweek
        day_map = {0: 'Δευτέρα', 1: 'Τρίτη', 2: 'Τετάρτη', 3: 'Πέμπτη', 4: 'Παρασκευή', 5: 'Σάββατο', 6: 'Κυριακή'}
        df_heat['Ημέρα'] = df_heat['DayOfWeek'].map(day_map)
        
        df_heat['Μισάωρο'] = df_heat['Timestamp'].dt.floor('30min').dt.strftime('%H:%M')
        
        heatmap_data = df_heat.groupby(['DayOfWeek', 'Ημέρα', 'Μισάωρο'])['Congestion'].mean().reset_index()
        pivot_df = heatmap_data.pivot(index='Μισάωρο', columns='Ημέρα', values='Congestion')
        
        days_order = ['Κυριακή', 'Δευτέρα', 'Τρίτη', 'Τετάρτη', 'Πέμπτη', 'Παρασκευή', 'Σάββατο']
        existing_days = [d for d in days_order if d in pivot_df.columns]
        pivot_df = pivot_df[existing_days]
        
        all_half_hours = [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]
        pivot_df = pivot_df.reindex(all_half_hours)
        
        pivot_df = pivot_df.dropna(how='all')
        
        # 🛠️ ΕΞΥΠΝΟ ΓΕΜΙΣΜΑ (SMART FILL): Ενώνει τα μικρά κενά (ΜΟΝΟ ενδιάμεσα, όχι στο μέλλον)
        pivot_df = pivot_df.interpolate(method='linear', limit=4, limit_area='inside')
        
        if not pivot_df.empty:
            
            st.markdown("#### 🏆 Στατιστικά Αιχμής")
            c1, c2, c3 = st.columns(3)
            
            peak_row = heatmap_data.loc[heatmap_data['Congestion'].idxmax()]
            c1.metric("🔥 Peak Hour (Απόλυτη Αιχμή)", f"{peak_row['Congestion']:.1f}%", f"{peak_row['Ημέρα']} στις {peak_row['Μισάωρο']}", delta_color="inverse")
            
            day_avg = heatmap_data.groupby('Ημέρα')['Congestion'].mean()
            worst_day = day_avg.idxmax()
            c2.metric("📅 Πιο Δύσκολη Ημέρα", f"{day_avg.max():.1f}%", f"Μέσος όρος: {worst_day}", delta_color="inverse")
            
            best_row = heatmap_data.loc[heatmap_data['Congestion'].idxmin()]
            c3.metric("✅ Πιο Ήσυχη Ώρα", f"{best_row['Congestion']:.1f}%", f"{best_row['Ημέρα']} στις {best_row['Μισάωρο']}", delta_color="normal")
            
            st.markdown("<br>", unsafe_allow_html=True)

            dramatic_scale = [
                [0.0,  "#2ecc71"],
                [0.3,  "#2ecc71"],
                [0.35, "#f1c40f"],
                [0.45, "#e67e22"],
                [0.55, "#e74c3c"],
                [0.8,  "#c0392b"],
                [1.0,  "#8e44ad"] 
            ]

            fig_heat = px.imshow(
                pivot_df,
                labels=dict(x="Ημέρα", y="Ώρα (Ανά Μισάωρο)", color="Δείκτης Συμφόρησης (%)"),
                x=pivot_df.columns,
                y=pivot_df.index,
                color_continuous_scale=dramatic_scale, 
                range_color=[35, 65], 
                text_auto=".0f", 
                aspect="auto",
                height=800
            )
            
            fig_heat.update_traces(
                xgap=5, 
                ygap=5, 
                texttemplate="%{z:.0f}%" 
            )
            
            fig_heat.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', 
                plot_bgcolor='rgba(10,10,10,0.5)', 
                font=dict(color="white"),
                xaxis=dict(side="top", tickfont=dict(size=12)), 
                yaxis=dict(
                    autorange="reversed", 
                    tickmode="linear",
                    tickfont=dict(size=11)
                ),
                coloraxis_colorbar=dict(
                    title="Συμφόρηση", 
                    ticksuffix="%",
                    dtick=5,
                    tickmode="linear"
                )
            )
            
            st.plotly_chart(fig_heat, use_container_width=True)
        else:
            st.info("ℹ️ Δεν υπάρχουν ακόμη δεδομένα για την παραγωγή του Heatmap.")
    else:
        st.warning("⚠️ Δεν βρέθηκαν καταγραφές στο ιστορικό για τα συγκεκριμένα φίλτρα.")
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

# 1. Ρυθμίσεις σελίδας - Πλήρης οθόνη, επαγγελματικό Title
st.set_page_config(page_title="Smart Traffic Patras | UPatras", page_icon="🚦", layout="wide")

# 🔥 CUSTOM CSS ΓΙΑ ΕΠΑΓΓΕΛΜΑΤΙΚΗ GLASSMORPHISM ΕΜΦΑΝΙΣΗ & BACKGROUND
st.markdown("""
<style>
    /* Background Image με Dark Overlay (Διακριτικό) */
    .stApp {
        background: linear-gradient(rgba(14, 17, 23, 0.88), rgba(14, 17, 23, 0.95)),
                    url("https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?q=80&w=2000&auto=format&fit=crop");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        color: #E0E0E0;
    }
    
    /* Τυπογραφία & Σκιές */
    h1, h2, h3, h4 { 
        color: #FFFFFF !important; 
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
        text-shadow: 1px 1px 4px rgba(0,0,0,0.8);
        font-weight: 600;
    }
    
    /* Metrics - Glassmorphism (Εφέ θολού γυαλιού) */
    [data-testid="stMetricValue"] { 
        font-size: 2.5rem !important; 
        font-weight: 700; 
        color: #00BFFF; 
        text-shadow: 0px 0px 10px rgba(0, 191, 255, 0.3);
    }
    [data-testid="stMetricLabel"] { 
        font-size: 1.05rem !important; 
        color: #CCCCCC !important; 
        font-weight: 500 !important; 
    }
    div[data-testid="metric-container"] {
        background-color: rgba(30, 30, 30, 0.5);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-radius: 15px; 
        padding: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        border: 1px solid rgba(255, 255, 255, 0.1);
        transition: transform 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
    }
    /* Hover Animation για τα Metrics */
    div[data-testid="metric-container"]:hover {
        transform: translateY(-5px);
        border-color: rgba(0, 191, 255, 0.5);
        box-shadow: 0 10px 40px 0 rgba(0, 191, 255, 0.15);
    }
    
    /* Sidebar - Glassmorphism */
    [data-testid="stSidebar"] { 
        background-color: rgba(22, 25, 31, 0.75) !important; 
        backdrop-filter: blur(15px);
        border-right: 1px solid rgba(255, 255, 255, 0.05); 
    }
    
    /* Tabs & Buttons */
    button[data-baseweb="tab"] { 
        font-size: 1.15rem; 
        font-weight: 600; 
        color: #A0A0A0; 
        background-color: transparent !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] { 
        color: #00BFFF !important; 
        border-bottom-color: #00BFFF !important; 
    }
    
    /* Dataframes & Selectboxes */
    .stDataFrame { 
        border-radius: 15px; 
        overflow: hidden; 
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3); 
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .stSelectbox div[data-baseweb="select"] > div { 
        background-color: rgba(40, 40, 40, 0.7);
        border-radius: 10px; 
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    /* Alerts/Warnings */
    .stAlert {
        background-color: rgba(30,30,30,0.6) !important;
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        color: #E0E0E0;
    }
    
    /* Στυλ για τα Custom Info Boxes */
    .custom-info-box {
        background-color: rgba(30, 30, 30, 0.6);
        backdrop-filter: blur(10px);
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
    }
</style>
""", unsafe_allow_html=True)

# Header Εφαρμογής
col_title, col_logo = st.columns([8, 1])
with col_title:
    st.title("🚦 Smart Traffic Analytics | Πάτρα")
    st.markdown("Προηγμένο Σύστημα Παρακολούθησης & Ανάλυσης Κυκλοφοριακού Φόρτου σε Πραγματικό Χρόνο")
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

# 🔥 Η ΤΡΟΠΟΠΟΙΗΜΕΝΗ ΣΥΝΑΡΤΗΣΗ ΓΙΑ ΤΟ NIGHT MODE ΣΤΑ ΧΡΩΜΑΤΑ
def get_hybrid_color(speed, road_name, time_str):
    if pd.isna(speed) or speed == 0: return "#7f8c8d" 
    
    # Έλεγχος αν είναι νύχτα (21:00 έως 06:00)
    hour = int(time_str.split(':')[0]) if time_str else 12
    is_night = (hour >= 21 or hour <= 6)

    r_type = road_types.get(road_name, "").lower()
    
    if "trunk" in r_type or "motorway" in r_type:
        limit = static_data.get(road_name, 90)
        ratio = speed / limit if limit > 0 else 1
        
        # Πιο ελαστικά τα όρια το βράδυ για να μην κοκκινίζει εύκολα
        thresh_red = 0.20 if is_night else 0.4 
        thresh_yel = 0.50 if is_night else 0.75
        
        if ratio < thresh_red: return "#FF4B4B" # Εντονο κόκκινο
        if ratio < thresh_yel: return "#FFC107" # Ζεστό κίτρινο
        return "#00E676" # Φωτεινό πράσινο
    else:
        thresh_red = 7 if is_night else 15
        thresh_yel = 15 if is_night else 30
        
        if speed < thresh_red: return "#FF4B4B"
        if speed < thresh_yel: return "#FFC107"
        return "#00E676"

# --- 3. Φόρτωση Γεωμετρίας & CSV ---
if not os.path.exists("road_geometry.json"):
    st.error("❌ Λείπει το αρχείο 'road_geometry.json'! Τρέξτε πρώτα το setupgeometry.py")
    st.stop()

with open("road_geometry.json", "r", encoding="utf-8") as f:
    geometry_data = json.load(f)

df_history = load_csv_data()
if df_history is None:
    st.info("⏳ Αναμονή για δεδομένα από το Bot καταγραφής... Παρακαλώ περιμένετε.")
    st.stop()

API_KEYS = [
    "UsA5r09FOSV6PmRd4NZFF3JCW3y6N2o1", 
    "Nz9zgm9uxG3Pd70dK2OYvEtdktn8PQSD",
    "IP2weRLSvXxstW414lUcWWSks3qwrGYR", 
    "V8V7MYwbnjA6y0YJj8V46mkxvXRM9Uz9"
]

# --- 4. SIDEBAR ---
with st.sidebar:
    # --- LOGO ПΑΝΕΠΙΣΤΗΜΙΟΥ ---
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 8, 1])
    with col2:
        try:
            # Φορτώνει το logo του Πανεπιστημίου
            st.image("upatras_logo.png", use_container_width=True)
        except Exception:
            # Αν λείπει το αρχείο, δείχνει ένα κομψό κείμενο αντί να βγάλει error
            st.markdown("<h3 style='text-align:center; color:#00BFFF; font-weight:700;'>UPatras</h3>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown("## ⚙️ Κέντρο Ελέγχου")
    st.markdown("---")
    available_dates = sorted(df_history['Date'].dropna().unique())
    if not available_dates:
        st.error("Σφάλμα: Το CSV δεν έχει έγκυρες ημερομηνίες!")
        st.stop()

    selected_date = st.selectbox("📅 Επιλογή Ημερομηνίας:", options=available_dates, index=len(available_dates)-1)
    df_day = df_history[df_history['Date'] == selected_date]
    available_times = sorted(df_day['Time'].dropna().unique())

    if not available_times:
        st.warning("Δεν βρέθηκαν καταγραφές για αυτή τη μέρα.")
        st.stop()

    selected_time = st.selectbox("⏱️ Επιλογή Ώρας:", options=available_times, index=len(available_times)-1)
    st.markdown("---")
    
    unique_types = ["Όλοι οι Τύποι"] + sorted(list(set(road_types.values()))) if road_types else ["Όλοι οι Τύποι"]
    selected_type = st.selectbox("🛤️ Επιλογή Κατηγορίας Οδού:", options=unique_types, index=0)
    st.markdown("---")

    available_roads_for_step4 = [r for r in geometry_data.keys() if selected_type == "Όλοι οι Τύποι" or road_types.get(r) == selected_type]
    all_roads = ["Όλες οι Οδοί"] + sorted(available_roads_for_step4)
    selected_road = st.selectbox("📍 Αναζήτηση Συγκεκριμένης Οδού:", options=all_roads, index=0)
    
    st.markdown("---")
    st.caption("Powered by University of Patras")
    
    past_mask = (df_history['Date'] < selected_date) | ((df_history['Date'] == selected_date) & (df_history['Time'] <= selected_time))
    all_current_df = df_history[past_mask].drop_duplicates(subset=['Road_Segment'], keep='last')
    
    live_speeds = dict(zip(all_current_df['Road_Segment'], all_current_df['Speed_kmh']))
    
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

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["🗺️ Ανάλυση Δικτύου", "📍 Εύρεση Βέλτιστης Διαδρομής", "📅 Heatmap Πρόβλεψης"])

# ================= TAB 1 =================
with tab1:
    st.markdown(f"### 📡 Live Αποτύπωση Κυκλοφορίας: {selected_date} @ {selected_time}")
    
    # Λεπτή γραμμή που ταιριάζει με το glass UI
    st.markdown("<hr style='border:1px solid rgba(255,255,255,0.1)'>", unsafe_allow_html=True)
    
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
            if road_name == selected_road: color, weight, opacity = get_hybrid_color(speed, road_name, selected_time), 8, 1.0
            else: color, weight, opacity = "#333333", 2, 0.15 
        else:
            if is_type_match: color, weight, opacity = get_hybrid_color(speed, road_name, selected_time), 5, 0.9
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
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if selected_road == "Όλες οι Οδοί":
        st.markdown(f"### 📊 Αναλυτική Αναφορά Δικτύου (Φίλτρο: {selected_type})")
        if not filtered_view_df.empty:
            
            filtered_view_df['Type'] = filtered_view_df['Road_Segment'].map(road_types).fillna('Άγνωστο')
            filtered_view_df['Limit'] = filtered_view_df['Road_Segment'].apply(lambda x: static_data.get(x, 50))
            
            # 🔥 NIGHT MODE ΕΝΣΩΜΑΤΩΣΗ ΣΤΑ ΣΤΑΤΙΣΤΙΚΑ (Ελέγχει αν υπάρχει συμφόρηση λαμβάνοντας υπόψη το βράδυ)
            def is_congested(row):
                hour = int(selected_time.split(':')[0]) if selected_time else 12
                is_night = (hour >= 21 or hour <= 6)
                
                r_type = str(row['Type']).lower()
                if "trunk" in r_type or "motorway" in r_type:
                    thresh = 0.20 if is_night else 0.4
                    return (row['Speed_kmh'] / row['Limit']) < thresh if row['Limit'] > 0 else False
                else:
                    thresh = 7 if is_night else 15
                    return row['Speed_kmh'] < thresh
                    
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
            c1.metric("🏎️ Μέση Ταχύτητα Πόλης", f"{avg_speed} km/h", "Δίκτυο σε πραγματικό χρόνο")
            c2.metric("🚨 Κόμβοι με Συμφόρηση", f"{congested_count}", f"Από σύνολο {total_roads} δρόμων", delta_color="inverse")
            c3.metric("📉 Ποσοστό Συμφόρησης", f"{round((congested_count/total_roads)*100, 1)}%", "Κρίσιμος Δείκτης", delta_color="inverse")
            c4.metric("🤯 Επίκεντρο Κίνησης", f"{worst_road_row['Speed_kmh']} km/h", f"{worst_road_row['Road_Segment']}", delta_color="inverse")

            st.markdown("<br>", unsafe_allow_html=True)
            c_left, c_right = st.columns([1.2, 1])
            with c_left:
                st.markdown("#### 🚫 Κορυφαία 5 Σημεία Συμφόρησης (Bottlenecks)")
                worst_5 = filtered_view_df.nsmallest(5, 'Ratio')[['Road_Segment', 'Speed_kmh', 'Type']].reset_index(drop=True)
                worst_5.columns = ["Όνομα Οδού", "Live Ταχύτητα (km/h)", "Κατηγορία"]
                st.dataframe(worst_5, use_container_width=True)
            with c_right:
                st.markdown("#### 🚦 Κατανομή Επιπέδου Κυκλοφορίας")
                
                # 🔥 NIGHT MODE ΣΤΗΝ ΠΙΤΑ ΤΩΝ ΣΤΑΤΙΣΤΙΚΩΝ
                def categorize_hybrid(row):
                    speed = row['Speed_kmh']
                    hour = int(selected_time.split(':')[0]) if selected_time else 12
                    is_night = (hour >= 21 or hour <= 6)
                    
                    r_type = str(row['Type']).lower()
                    if "trunk" in r_type or "motorway" in r_type:
                        ratio = speed / row['Limit'] if row['Limit'] > 0 else 1
                        thresh_red = 0.20 if is_night else 0.4
                        thresh_yel = 0.50 if is_night else 0.75
                        
                        if ratio < thresh_red: return 'Συμφόρηση (Congested)'
                        if ratio < thresh_yel: return 'Μέτρια (Moderate)'
                        return 'Ελεύθερη (Clear)'
                    else:
                        thresh_red = 7 if is_night else 15
                        thresh_yel = 15 if is_night else 30
                        
                        if speed < thresh_red: return 'Συμφόρηση (Congested)'
                        if speed < thresh_yel: return 'Μέτρια (Moderate)'
                        return 'Ελεύθερη (Clear)'
                        
                filtered_view_df['Traffic_Level'] = filtered_view_df.apply(categorize_hybrid, axis=1)
                pie_fig = px.pie(filtered_view_df, names='Traffic_Level', hole=0.6, color='Traffic_Level',
                                 color_discrete_map={'Συμφόρηση (Congested)': '#FF4B4B', 'Μέτρια (Moderate)': '#FFC107', 'Ελεύθερη (Clear)': '#00E676'})
                pie_fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', 
                    plot_bgcolor='rgba(0,0,0,0)', 
                    font=dict(color="white"), 
                    margin=dict(t=10, b=10, l=10, r=10), 
                    height=300,
                    showlegend=True,
                    legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.0)
                )
                st.plotly_chart(pie_fig, use_container_width=True)

        st.markdown("<hr style='border:1px solid rgba(255,255,255,0.1)'>", unsafe_allow_html=True)
        st.markdown("### 📈 Εξέλιξη Ταχυτήτων ανά Κατηγορία Οδού")
        
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
                labels={"Speed_kmh": "Μέση Ταχύτητα (km/h)", "Ώρα": "Ώρα της Ημέρας", "Type": "Κατηγορία Οδού"},
                markers=True
            )
            
            fig_type.update_traces(connectgaps=True)
            
            fig_type.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)', 
                font=dict(color="#E0E0E0"),
                xaxis=dict(showgrid=False, tickangle=-45, nticks=24),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_type, use_container_width=True)
        else:
            st.info("ℹ️ Δεν υπάρχουν αρκετά δεδομένα για τη συγκριτική ανάλυση.")
    else:
        st.markdown(f"### 📊 Λεπτομερής Ανάλυση Οδού: `{selected_road}`")
        df_road_day = df_day[df_day['Road_Segment'] == selected_road].sort_values('Time')
        
        if not df_road_day.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("⏱️ Τρέχουσα Ταχύτητα", f"{live_speeds.get(selected_road, 'N/A')} km/h", "Live Εκτίμηση")
            c2.metric("📈 Μέγιστη (Ημερήσια)", f"{df_road_day['Speed_kmh'].max()} km/h")
            c3.metric("📉 Ελάχιστη (Ημερήσια)", f"{df_road_day['Speed_kmh'].min()} km/h")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            city_avg = df_day.groupby('Time')['Speed_kmh'].mean().reset_index()
            city_avg.rename(columns={'Speed_kmh': 'Μέσος Όρος Πόλης'}, inplace=True)
            
            plot_df = pd.merge(df_road_day[['Time', 'Speed_kmh']], city_avg, on='Time', how='outer').sort_values('Time')
            plot_df.rename(columns={'Speed_kmh': f'{selected_road}'}, inplace=True)
            
            plot_df_melted = plot_df.melt(id_vars=['Time'], value_vars=[f'{selected_road}', 'Μέσος Όρος Πόλης'], 
                                          var_name='Δείκτης', value_name='Ταχύτητα (km/h)')
            
            fig_road_line = px.line(plot_df_melted, x='Time', y='Ταχύτητα (km/h)', color='Δείκτης', markers=True,
                                    color_discrete_map={f'{selected_road}': '#00BFFF', 'Μέσος Όρος Πόλης': '#7f8c8d'})
            
            fig_road_line.update_traces(marker=dict(size=6))

            fig_road_line.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"),
                xaxis=dict(gridcolor="rgba(255,255,255,0.05)"), yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                legend=dict(title="", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_road_line, use_container_width=True)
        else:
            st.warning("⚠️ Δεν υπάρχουν επαρκή δεδομένα για αυτή την οδό σήμερα.")

# ================= TAB 2 =================
with tab2:
    st.markdown("### 🔬 Έξυπνος Αλγόριθμος Πλοήγησης (TomTom API)")
    st.markdown("Υπολογισμός βέλτιστης διαδρομής **λαμβάνοντας υπόψη τη live συμφόρηση του δικτύου.**")
    
    available_route_roads = sorted(list(geometry_data.keys()))
    
    st.markdown("<br>", unsafe_allow_html=True)
    c_sel1, c_sel2 = st.columns(2)
    with c_sel1:
        dropdown_start = st.selectbox("🟢 Σημείο Εκκίνησης:", ["Επιλογή μέσω Χάρτη (Κλικ)..."] + available_route_roads)
    with c_sel2:
        dropdown_end = st.selectbox("🔴 Τελικός Προορισμός:", ["Επιλογή μέσω Χάρτη (Κλικ)..."] + available_route_roads)

    col_btn1, col_btn2, col_btn3 = st.columns([1,2,1])
    with col_btn2:
        if st.button("🔄 Επαναφορά Σημείων", use_container_width=True):
            st.session_state.start_point = None
            st.session_state.end_point = None
            st.rerun()

    if dropdown_start != "Επιλογή μέσω Χάρτη (Κλικ)...":
        st.session_state.start_point = get_center(geometry_data[dropdown_start])
    if dropdown_end != "Επιλογή μέσω Χάρτη (Κλικ)...":
        st.session_state.end_point = get_center(geometry_data[dropdown_end])

    m_click = folium.Map(
        location=[38.2462, 21.7351], 
        zoom_start=14, 
        tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', 
        attr='Google Maps'
    )
    
    for road_name, coords in geometry_data.items():
        folium.PolyLine(locations=coords, color="#00BFFF", weight=3, opacity=0.3, tooltip=f"Άξονας: {road_name}").add_to(m_click)
    
    if st.session_state.start_point:
        folium.Marker(st.session_state.start_point, popup="Αφετηρία", icon=folium.Icon(color="green", icon="play")).add_to(m_click)
    if st.session_state.end_point:
        folium.Marker(st.session_state.end_point, popup="Προορισμός", icon=folium.Icon(color="red", icon="stop")).add_to(m_click)
        
    map_data = st_folium(m_click, width=1300, height=400, key="click_selector_map")
    
    if map_data and map_data.get("last_clicked"):
        clicked_coords = [map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]]
        if st.session_state.start_point is None:
            st.session_state.start_point = clicked_coords
            st.rerun()
        elif st.session_state.end_point is None and clicked_coords != st.session_state.start_point:
            st.session_state.end_point = clicked_coords
            st.rerun()
            
    c_out1, c_out2 = st.columns(2)
    with c_out1:
        st.markdown(f"<div class='custom-info-box' style='border-left: 5px solid #00E676;'>🟢 <b>Συντεταγμένες Εκκίνησης:</b> <br>{st.session_state.start_point if st.session_state.start_point else 'Αναμονή επιλογής...'}</div>", unsafe_allow_html=True)
    with c_out2:
        st.markdown(f"<div class='custom-info-box' style='border-left: 5px solid #FF4B4B;'>🔴 <b>Συντεταγμένες Προορισμού:</b> <br>{st.session_state.end_point if st.session_state.end_point else 'Αναμονή επιλογής...'}</div>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)

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
            with st.spinner('🔭 Επικοινωνία με Δορυφόρο & Υπολογισμός Διαδρομής...'):
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
                
                st.markdown("<hr style='border:1px solid rgba(255,255,255,0.1)'>", unsafe_allow_html=True)
                st.markdown("#### 🏆 Βέλτιστη Προτεινόμενη Διαδρομή")
                
                res_col1, res_col2, res_col3 = st.columns(3)
                res_col1.metric("⏱️ Εκτιμώμενος Χρόνος", f"{time_min} min", f"Καθυστέρηση κίνησης: {delay_sec} sec", delta_color="inverse")
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
                    # Και εδώ το API καλεί την get_hybrid_color με την επιλεγμένη ώρα
                    c = get_hybrid_color(speed, road_name, selected_time)
                    folium.PolyLine(locations=coords, color=c, weight=2, opacity=0.15).add_to(m_res)

                folium.PolyLine(locations=route_coords, color="#00BFFF", weight=7, opacity=0.8).add_to(m_res)
                
                for sec in sections:
                    if sec.get('sectionType') == 'TRAFFIC':
                        s_idx = sec.get('startPointIndex', 0)
                        e_idx = sec.get('endPointIndex', len(route_coords)-1)
                        mag = sec.get('magnitudeOfDelay', 0)
                        
                        if mag >= 3: t_color = "#FF4B4B"
                        elif mag > 0: t_color = "#FFC107"
                        else: t_color = "#00E676"
                        
                        sec_coords = route_coords[s_idx:e_idx+1]
                        folium.PolyLine(locations=sec_coords, color=t_color, weight=7, opacity=1.0).add_to(m_res)

                folium.Marker(location=route_coords[0], icon=folium.Icon(color="green", icon="play")).add_to(m_res)
                folium.Marker(location=route_coords[-1], icon=folium.Icon(color="red", icon="stop")).add_to(m_res)
                
                st_folium(m_res, width=1300, height=450, key="result_route_map")
            else:
                st.error("Σφάλμα API: Αδυναμία εύρεσης διαδρομής. Το δίκτυο ενδέχεται να μην συνδέεται στο επιλεγμένο σημείο.")
        except Exception as e:
            st.error(f"Αποτυχία επικοινωνίας με API: {e}")

# ================= TAB 3: HEATMAP  =================
with tab3:
    st.markdown("### 📅 Χωροχρονικός Χάρτης Συμφόρησης (Heatmap Analytics)")
    st.markdown("Μοντέλο ιστορικών δεδομένων που απεικονίζει τη δομή της κίνησης καθ' όλη τη διάρκεια της εβδομάδας, ανά 30 λεπτά.")
    
    df_heat = df_history.copy()
    
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
        
        # 🔥 ΝΕΟ: ΕΦΑΡΜΟΓΗ NIGHT-MODE ΣΤΟ HEATMAP ΓΙΑ ΝΑ ΜΗΝ "ΚΟΚΚΙΝΙΖΕΙ" ΤΑ ΒΡΑΔΙΑ ΛΑΘΟΣ
        df_heat['Hour'] = df_heat['Timestamp'].dt.hour
        is_night_mask = (df_heat['Hour'] >= 21) | (df_heat['Hour'] <= 6)
        # Μειώνουμε πλασματικά τη συμφόρηση το βράδυ κατά 60% (ώστε το κόκκινο να γίνει πορτοκαλί/πράσινο)
        df_heat.loc[is_night_mask, 'Congestion'] = df_heat.loc[is_night_mask, 'Congestion'] * 0.4
        
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
        pivot_df = pivot_df.interpolate(method='linear', limit=4, limit_area='inside')
        
        if not pivot_df.empty:
            st.markdown("<br>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            
            peak_row = heatmap_data.loc[heatmap_data['Congestion'].idxmax()]
            c1.metric("🔥 Μέγιστη Συμφόρηση (Peak Hour)", f"{peak_row['Congestion']:.1f}%", f"{peak_row['Ημέρα']} στις {peak_row['Μισάωρο']}", delta_color="inverse")
            
            day_avg = heatmap_data.groupby('Ημέρα')['Congestion'].mean()
            worst_day = day_avg.idxmax()
            c2.metric("📅 Κρισιμότερη Ημέρα Εβδομάδας", f"{day_avg.max():.1f}%", f"Αθροιστικός Μ.Ο. - {worst_day}", delta_color="inverse")
            
            best_row = heatmap_data.loc[heatmap_data['Congestion'].idxmin()]
            c3.metric("✅ Βέλτιστο Παράθυρο Μετακίνησης", f"{best_row['Congestion']:.1f}%", f"{best_row['Ημέρα']} στις {best_row['Μισάωρο']}", delta_color="normal")
            
            st.markdown("<br>", unsafe_allow_html=True)

            dramatic_scale = [
                [0.0,  "#00E676"], # Clear
                [0.3,  "#00E676"], 
                [0.4,  "#FFC107"], # Moderate
                [0.6,  "#FF4B4B"], # Heavy
                [0.8,  "#D50000"], # Jam
                [1.0,  "#4A148C"]  # Standstill
            ]

            fig_heat = px.imshow(
                pivot_df,
                labels=dict(x="Ημέρα της Εβδομάδας", y="Ώρα (Ανά 30')", color="Δείκτης Συμφόρησης (%)"),
                x=pivot_df.columns,
                y=pivot_df.index,
                color_continuous_scale=dramatic_scale, 
                range_color=[35, 65], 
                text_auto=".0f", 
                aspect="auto",
                height=700
            )
            
            fig_heat.update_traces(xgap=4, ygap=4, texttemplate="%{z:.0f}%")
            
            fig_heat.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', 
                plot_bgcolor='rgba(0,0,0,0)', 
                font=dict(color="#E0E0E0", size=12),
                xaxis=dict(side="top", tickfont=dict(size=14, weight="bold")), 
                yaxis=dict(autorange="reversed", tickmode="linear", tickfont=dict(size=11)),
                coloraxis_colorbar=dict(title="Συμφόρηση", ticksuffix="%", dtick=10, tickmode="linear")
            )
            
            st.plotly_chart(fig_heat, use_container_width=True)
        else:
            st.info("ℹ️ Δεν υπάρχουν επαρκή δεδομένα για την παραγωγή του Heatmap.")
    else:
        st.warning("⚠️ Δεν βρέθηκαν καταγραφές στο ιστορικό για τα συγκεκριμένα φίλτρα.")
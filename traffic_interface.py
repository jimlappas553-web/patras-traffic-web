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

# 1. Ρυθμίσεις Σελίδας
st.set_page_config(page_title="Patras Traffic Hub | UPatras", page_icon="🚦", layout="wide")

# 🔥 CUSTOM CSS: ENTERPRISE DARK MODE (Καθαρό, χωρίς εικόνες, με glowing effects)
st.markdown("""
<style>
    /* Βασικό Φόντο: Deep Space Dark (Επαγγελματικό, όχι μαύρο) */
    .stApp {
        background-color: #0B0E14;
        color: #E2E8F0;
        font-family: 'Inter', 'Segoe UI', sans-serif;
    }
    
    /* Επικεφαλίδες */
    h1, h2, h3, h4 { color: #FFFFFF !important; font-weight: 600; letter-spacing: -0.5px; }
    
    /* Metrics Κουτιά: Sleek Dark Cards με Neon Hover */
    div[data-testid="metric-container"] {
        background-color: #151A22;
        border-radius: 12px; 
        padding: 20px;
        border: 1px solid #2A3241;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);
        transition: all 0.3s ease;
    }
    div[data-testid="metric-container"]:hover {
        border-color: #3B82F6;
        box-shadow: 0 0 15px rgba(59, 130, 246, 0.2);
        transform: translateY(-2px);
    }
    [data-testid="stMetricValue"] { font-size: 2.2rem !important; font-weight: 700; color: #3B82F6; }
    [data-testid="stMetricLabel"] { font-size: 1rem !important; color: #94A3B8 !important; font-weight: 500 !important; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { 
        background-color: #0F131A !important; 
        border-right: 1px solid #1E293B; 
    }
    
    /* Tabs & Selectboxes */
    button[data-baseweb="tab"] { font-size: 1.1rem; font-weight: 600; color: #64748B; background-color: transparent !important; }
    button[data-baseweb="tab"][aria-selected="true"] { color: #3B82F6 !important; border-bottom-color: #3B82F6 !important; }
    
    .stDataFrame { border-radius: 10px; overflow: hidden; border: 1px solid #1E293B; }
    
    /* Custom Info Boxes */
    .custom-info-box {
        background-color: #151A22;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #2A3241;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        color: #E2E8F0;
    }
</style>
""", unsafe_allow_html=True)

# Header
col_title, col_logo = st.columns([8, 1])
with col_title:
    st.title("🚦 Patras Traffic Intelligence")
    st.markdown("<p style='color:#94A3B8; font-size:1.1rem;'>Παρακολούθηση & Ανάλυση Κυκλοφοριακού Φόρτου σε Πραγματικό Χρόνο</p>", unsafe_allow_html=True)
st.markdown("<hr style='border-color: #1E293B;'>", unsafe_allow_html=True)

if 'start_point' not in st.session_state: st.session_state.start_point = None
if 'end_point' not in st.session_state: st.session_state.end_point = None

# --- ΜΕΤΑΦΡΑΣΗ ΟΔΩΝ (Ελληνικά στο UI) ---
# Μπορείς να προσθέσεις όσους δρόμους θες εδώ. Αν κάποιος δεν υπάρχει, θα φαίνεται με το αγγλικό του όνομα.
GR_ROADS = {
    "Korinthou": "Κορίνθου",
    "Maizonos": "Μαιζώνος",
    "Agiou Andreou": "Αγίου Ανδρέου",
    "Gounari": "Δ. Γούναρη",
    "Venizelou": "Ελ. Βενιζέλου",
    "Eleytheriou Venizelou": "Ελ. Βενιζέλου",
    "Patron Klaous": "Πατρών Κλάους",
    "Panepistimiou": "Πανεπιστημίου",
    "Athinon": "Αθηνών",
    "Ermou": "Ερμού",
    "Agiou Nikolaou": "Αγίου Νικολάου",
    "Karolou": "Καρόλου",
    "Kanakarī": "Κανακάρη",
    "Kanakari": "Κανακάρη",
    "Navarinou": "Ναυαρίνου",
    "Akti Dimaion": "Ακτή Δυμαίων",
    "Othonos Amalias": "Όθωνος Αμαλίας",
    "Papanastasiou": "Παπαναστασίου",
    "Ellinos Stratiotou": "Έλληνος Στρατιώτου",
    "Agiou Georgiou": "Αγίου Γεωργίου",
    "Akrotiriou": "Ακρωτηρίου"
}

def tr(name):
    """Μετατρέπει το Αγγλικό όνομα σε Ελληνικό για παρουσίαση, κρατώντας το _rev αν υπάρχει"""
    if not isinstance(name, str): return name
    base_name = name.replace("_rev", "").strip()
    suffix = " (Αντίθετο)" if "_rev" in name else ""
    return GR_ROADS.get(base_name, base_name) + suffix

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

# 🔥 ΕΞΥΠΝΗ ΣΥΝΑΡΤΗΣΗ: ΔΙΟΡΘΩΣΗ ΧΡΩΜΑΤΩΝ ΓΙΑ ΤΟ ΒΡΑΔΥ
def get_traffic_status(speed, road_name, time_str):
    if pd.isna(speed) or speed == 0: return ("Άγνωστο", "#7f8c8d")
    
    # Εξαγωγή ώρας για τον έλεγχο της νύχτας
    hour = int(time_str.split(':')[0]) if time_str else 12
    # Θεωρούμε "Νύχτα" από τις 21:00 το βράδυ έως τις 06:00 το πρωί
    is_night = (hour >= 21 or hour <= 6)
    
    r_type = road_types.get(road_name, "").lower()
    limit = static_data.get(road_name, 50)
    ratio = speed / limit if limit > 0 else 1
    
    if "trunk" in r_type or "motorway" in r_type:
        thresh_red = 0.25 if is_night else 0.4    # Το βράδυ πρέπει να πέσει στο 25% της ταχύτητας για να γίνει κόκκινο
        thresh_yel = 0.55 if is_night else 0.75   
    else:
        # Για δρόμους πόλης (όπου το 0 καταγράφεται συχνά λάθος το βράδυ λόγω έλλειψης αυτοκινήτων)
        thresh_red = 0.15 if is_night else 0.3    # Πρακτικά <7.5 km/h για να κοκκινίσει
        thresh_yel = 0.40 if is_night else 0.6    
        
    if ratio < thresh_red:
        return ("Συμφόρηση", "#EF4444") # Red
    elif ratio < thresh_yel:
        return ("Μέτρια", "#F59E0B") # Yellow/Orange
    else:
        return ("Ελεύθερη", "#10B981") # Green

# --- 3. Φόρτωση Γεωμετρίας & CSV ---
if not os.path.exists("road_geometry.json"):
    st.error("❌ Λείπει το αρχείο 'road_geometry.json'!")
    st.stop()

with open("road_geometry.json", "r", encoding="utf-8") as f:
    geometry_data = json.load(f)

df_history = load_csv_data()
if df_history is None:
    st.info("⏳ Αναμονή για δεδομένα από το σύστημα καταγραφής...")
    st.stop()

API_KEYS = [
    "UsA5r09FOSV6PmRd4NZFF3JCW3y6N2o1", 
    "Nz9zgm9uxG3Pd70dK2OYvEtdktn8PQSD",
    "IP2weRLSvXxstW414lUcWWSks3qwrGYR", 
    "V8V7MYwbnjA6y0YJj8V46mkxvXRM9Uz9"
]

# --- 4. SIDEBAR ---
with st.sidebar:
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 8, 1])
    with col2:
        try:
            st.image("upatras_logo.png", use_container_width=True)
        except Exception:
            st.markdown("<h3 style='text-align:center; color:#3B82F6;'>UPatras</h3>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown("### 🎛️ Φίλτρα Αναζήτησης")
    st.markdown("<hr style='border-color: #1E293B; margin-top: 0;'>", unsafe_allow_html=True)
    
    available_dates = sorted(df_history['Date'].dropna().unique())
    selected_date = st.selectbox("📅 Ημερομηνία:", options=available_dates, index=len(available_dates)-1)
    df_day = df_history[df_history['Date'] == selected_date]
    
    available_times = sorted(df_day['Time'].dropna().unique())
    if not available_times:
        st.warning("Δεν βρέθηκαν καταγραφές.")
        st.stop()
        
    selected_time = st.selectbox("⏱️ Ώρα Αναφοράς:", options=available_times, index=len(available_times)-1)
    
    unique_types = ["Όλοι οι Τύποι"] + sorted(list(set(road_types.values()))) if road_types else ["Όλοι οι Τύποι"]
    selected_type = st.selectbox("🛤️ Κατηγορία Οδού:", options=unique_types, index=0)

    available_roads_for_step4 = [r for r in geometry_data.keys() if selected_type == "Όλοι οι Τύποι" or road_types.get(r) == selected_type]
    all_roads = ["Όλες οι Οδοί"] + sorted(available_roads_for_step4, key=tr)
    # Η χρήση format_func=tr κάνει το μενού να δείχνει Ελληνικά αλλά να επιστρέφει τα Αγγλικά IDs
    selected_road = st.selectbox("📍 Επιλογή Οδού:", options=all_roads, index=0, format_func=tr)
    
    st.markdown("---")
    st.caption("Developed for University of Patras")
    
    # Λογική δεδομένων
    past_mask = (df_history['Date'] < selected_date) | ((df_history['Date'] == selected_date) & (df_history['Time'] <= selected_time))
    all_current_df = df_history[past_mask].drop_duplicates(subset=['Road_Segment'], keep='last')
    
    live_speeds = dict(zip(all_current_df['Road_Segment'], all_current_df['Speed_kmh']))
    
    # Διαγραφή νεκρών οδών
    for road in [r for r, s in live_speeds.items() if float(s) <= 0.5]:
        del live_speeds[road]
        
    live_centers = {r: get_center(geometry_data[r]) for r in live_speeds.keys() if r in geometry_data}
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
            closest_live = distances[:1] if "_rev" in str(r_name).lower() else distances[:3]
            
            if closest_live:
                local_ratios = [min(live_speeds[l_n] / static_data.get(l_n, 50), 1.0) for _, l_n in closest_live if static_data.get(l_n, 50) > 0]
                local_health_factor = sum(local_ratios) / len(local_ratios) if local_ratios else 1.0
            else:
                local_health_factor = 1.0 
            
            dynamic_secondary_speeds[r_name] = round(max(static_speed * local_health_factor, 5.0), 1)
            
    all_speeds_map = {**live_speeds, **dynamic_secondary_speeds}
    filtered_view_df = all_current_df.copy()
    if selected_type != "Όλοι οι Τύποι":
        filtered_view_df['Type'] = filtered_view_df['Road_Segment'].map(road_types)
        filtered_view_df = filtered_view_df[filtered_view_df['Type'] == selected_type]

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["🗺️ Ανάλυση Δικτύου", "📍 Εύρεση Βέλτιστης Διαδρομής", "📅 Heatmap Πρόβλεψης"])

# ================= TAB 1 =================
with tab1:
    st.markdown(f"### 📡 Χάρτης Κυκλοφορίας: {selected_date} @ {selected_time}")
    
    # Χάρτης: CartoDB Dark Matter για Enterprise look
    m = folium.Map(
        location=[38.2462, 21.7351], 
        zoom_start=14, 
        tiles='CartoDB dark_matter', # Σκούρος επαγγελματικός χάρτης 
        attr='CartoDB'
    )

    for road_name, coords in geometry_data.items():
        speed = all_speeds_map.get(road_name, 0)
        current_coords = coords
        
        if "_rev" in road_name.lower():
            try: current_coords = get_parallel_line(coords, dist_meters=3.5)
            except: pass

        is_type_match = (selected_type == "Όλοι οι Τύποι" or road_types.get(road_name) == selected_type)
        
        status, color = get_traffic_status(speed, road_name, selected_time)
        greek_name = tr(road_name)
        
        if selected_road != "Όλες οι Οδοί":
            if road_name == selected_road: weight, opacity = 8, 1.0
            else: color, weight, opacity = "#2A3241", 2, 0.3 
        else:
            if is_type_match: weight, opacity = 5, 0.9
            else: color, weight, opacity = "#2A3241", 2, 0.3

        line = folium.PolyLine(
            locations=current_coords, 
            color=color, 
            weight=weight, 
            opacity=opacity, 
            tooltip=f"{greek_name}: {speed} km/h" # Το tooltip πλέον στα Ελληνικά!
        ).add_to(m)

        if selected_road != "Όλες οι Οδοί" and road_name == selected_road:
            PolyLineTextPath(
                line, f'  {greek_name}  ', repeat=False, offset=8,
                attributes={'fill': '#FFFFFF', 'font-weight': 'bold', 'font-size': '16'}
            ).add_to(m)

    st_folium(m, width=1300, height=550, key="network_map")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if selected_road == "Όλες οι Οδοί":
        if not filtered_view_df.empty:
            
            # Εφαρμογή του νέου status function
            filtered_view_df['Status'] = filtered_view_df.apply(lambda row: get_traffic_status(row['Speed_kmh'], row['Road_Segment'], selected_time)[0], axis=1)
            filtered_view_df['Greek_Name'] = filtered_view_df['Road_Segment'].apply(tr)
            
            congested_count = len(filtered_view_df[filtered_view_df['Status'] == 'Συμφόρηση'])
            total_roads = len(filtered_view_df)
            avg_speed = round(filtered_view_df['Speed_kmh'].mean(), 1)
            
            # Βρίσκουμε τον χειρότερο δρόμο με βάση το (ταχύτητα/όριο)
            filtered_view_df['Ratio'] = filtered_view_df['Speed_kmh'] / filtered_view_df['Road_Segment'].apply(lambda x: static_data.get(x, 50))
            worst_road_row = filtered_view_df.loc[filtered_view_df['Ratio'].idxmin()]
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Μέση Ταχύτητα Πόλης", f"{avg_speed} km/h", "Δίκτυο σε πραγματικό χρόνο")
            c2.metric("Κόμβοι με Συμφόρηση", f"{congested_count}", f"Από σύνολο {total_roads} αξόνων", delta_color="inverse")
            c3.metric("Δείκτης Συμφόρησης", f"{round((congested_count/total_roads)*100, 1)}%", "Κρίσιμο Μέγεθος", delta_color="inverse")
            c4.metric("Επίκεντρο Κίνησης", f"{worst_road_row['Speed_kmh']} km/h", f"{worst_road_row['Greek_Name']}", delta_color="inverse")

            st.markdown("<br>", unsafe_allow_html=True)
            c_left, c_right = st.columns([1.2, 1])
            with c_left:
                st.markdown("#### 🚫 Κορυφαία 5 Bottlenecks")
                worst_5 = filtered_view_df.nsmallest(5, 'Ratio')[['Greek_Name', 'Speed_kmh', 'Status']].reset_index(drop=True)
                worst_5.columns = ["Όνομα Οδού", "Ταχύτητα (km/h)", "Κατάσταση"]
                st.dataframe(worst_5, use_container_width=True)
            with c_right:
                st.markdown("#### 🚦 Κατανομή Κυκλοφορίας")
                pie_fig = px.pie(filtered_view_df, names='Status', hole=0.65, color='Status',
                                 color_discrete_map={'Συμφόρηση': '#EF4444', 'Μέτρια': '#F59E0B', 'Ελεύθερη': '#10B981'})
                pie_fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="#E2E8F0"), 
                    margin=dict(t=10, b=10, l=10, r=10), height=300,
                    legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.0)
                )
                st.plotly_chart(pie_fig, use_container_width=True)

    else:
        st.markdown(f"### 📊 Ανάλυση Οδού: `{tr(selected_road)}`")
        df_road_day = df_day[df_day['Road_Segment'] == selected_road].sort_values('Time')
        
        if not df_road_day.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Τρέχουσα Ταχύτητα", f"{live_speeds.get(selected_road, 'N/A')} km/h")
            c2.metric("Μέγιστη (Ημερήσια)", f"{df_road_day['Speed_kmh'].max()} km/h")
            c3.metric("Ελάχιστη (Ημερήσια)", f"{df_road_day['Speed_kmh'].min()} km/h")
            
            city_avg = df_day.groupby('Time')['Speed_kmh'].mean().reset_index()
            city_avg.rename(columns={'Speed_kmh': 'Μέσος Όρος Πόλης'}, inplace=True)
            
            plot_df = pd.merge(df_road_day[['Time', 'Speed_kmh']], city_avg, on='Time', how='outer').sort_values('Time')
            plot_df.rename(columns={'Speed_kmh': tr(selected_road)}, inplace=True)
            
            plot_df_melted = plot_df.melt(id_vars=['Time'], value_vars=[tr(selected_road), 'Μέσος Όρος Πόλης'], 
                                          var_name='Δείκτης', value_name='Ταχύτητα (km/h)')
            
            fig_road_line = px.line(plot_df_melted, x='Time', y='Ταχύτητα (km/h)', color='Δείκτης', markers=True,
                                    color_discrete_map={tr(selected_road): '#3B82F6', 'Μέσος Όρος Πόλης': '#64748B'})
            
            fig_road_line.update_traces(marker=dict(size=6))
            fig_road_line.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="#E2E8F0"),
                xaxis=dict(gridcolor="#1E293B"), yaxis=dict(gridcolor="#1E293B"),
                legend=dict(title="", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_road_line, use_container_width=True)

# ================= TAB 2 =================
with tab2:
    st.markdown("### 🔬 TomTom Routing API")
    st.markdown("Επιλέξτε σημεία για την εύρεση της βέλτιστης διαδρομής **βάσει live κυκλοφορίας**.")
    
    available_route_roads = sorted(list(geometry_data.keys()), key=tr)
    
    st.markdown("<br>", unsafe_allow_html=True)
    c_sel1, c_sel2 = st.columns(2)
    with c_sel1:
        dropdown_start = st.selectbox("🟢 Σημείο Εκκίνησης (Α):", ["Επιλογή μέσω Χάρτη..."] + available_route_roads, format_func=tr)
    with c_sel2:
        dropdown_end = st.selectbox("🔴 Τελικός Προορισμός (Β):", ["Επιλογή μέσω Χάρτη..."] + available_route_roads, format_func=tr)

    col_btn1, col_btn2, col_btn3 = st.columns([1,2,1])
    with col_btn2:
        if st.button("🔄 Επαναφορά Σημείων", use_container_width=True):
            st.session_state.start_point = None
            st.session_state.end_point = None
            st.rerun()

    if dropdown_start != "Επιλογή μέσω Χάρτη...":
        st.session_state.start_point = get_center(geometry_data[dropdown_start])
    if dropdown_end != "Επιλογή μέσω Χάρτη...":
        st.session_state.end_point = get_center(geometry_data[dropdown_end])

    m_click = folium.Map(location=[38.2462, 21.7351], zoom_start=14, tiles='CartoDB dark_matter', attr='CartoDB')
    
    for road_name, coords in geometry_data.items():
        folium.PolyLine(locations=coords, color="#3B82F6", weight=3, opacity=0.3, tooltip=f"{tr(road_name)}").add_to(m_click)
    
    if st.session_state.start_point:
        folium.Marker(st.session_state.start_point, icon=folium.Icon(color="green", icon="play")).add_to(m_click)
    if st.session_state.end_point:
        folium.Marker(st.session_state.end_point, icon=folium.Icon(color="red", icon="stop")).add_to(m_click)
        
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
        st.markdown(f"<div class='custom-info-box' style='border-left: 4px solid #10B981;'>🟢 Συντεταγμένες (Α): {st.session_state.start_point if st.session_state.start_point else '...'}</div>", unsafe_allow_html=True)
    with c_out2:
        st.markdown(f"<div class='custom-info-box' style='border-left: 4px solid #EF4444;'>🔴 Συντεταγμένες (Β): {st.session_state.end_point if st.session_state.end_point else '...'}</div>", unsafe_allow_html=True)

    if st.session_state.start_point and st.session_state.end_point:
        s_str = f"{st.session_state.start_point[0]},{st.session_state.start_point[1]}"
        e_str = f"{st.session_state.end_point[0]},{st.session_state.end_point[1]}"
        
        url = f"https://api.tomtom.com/routing/1/calculateRoute/{s_str}:{e_str}/json"
        params = {'key': random.choice(API_KEYS), 'traffic': 'true', 'routeType': 'fastest', 'travelMode': 'car', 'sectionType': 'traffic'}
        
        try:
            with st.spinner('Υπολογισμός Διαδρομής μέσω TomTom API...'):
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
                
                st.markdown("<hr style='border-color:#1E293B;'>", unsafe_allow_html=True)
                
                res_col1, res_col2, res_col3 = st.columns(3)
                res_col1.metric("Εκτιμώμενος Χρόνος", f"{time_min} min", f"Καθυστέρηση κίνησης: {delay_sec} sec", delta_color="inverse")
                res_col2.metric("Μέση Ταχύτητα", f"{calc_speed} km/h")
                res_col3.metric("Συνολική Απόσταση", f"{distance_km} km")
                
                route_coords = [[p['latitude'], p['longitude']] for p in points]
                m_res = folium.Map(location=route_coords[0], zoom_start=14, tiles='CartoDB dark_matter', attr='CartoDB')
                
                for road_name, coords in geometry_data.items():
                    speed = live_speeds.get(road_name, static_data.get(road_name, 0))
                    _, color = get_traffic_status(speed, road_name, selected_time)
                    folium.PolyLine(locations=coords, color=color, weight=2, opacity=0.15).add_to(m_res)

                folium.PolyLine(locations=route_coords, color="#FFFFFF", weight=8, opacity=0.6).add_to(m_res)
                
                for sec in sections:
                    if sec.get('sectionType') == 'TRAFFIC':
                        s_idx = sec.get('startPointIndex', 0)
                        e_idx = sec.get('endPointIndex', len(route_coords)-1)
                        mag = sec.get('magnitudeOfDelay', 0)
                        
                        t_color = "#EF4444" if mag >= 3 else "#F59E0B" if mag > 0 else "#3B82F6"
                        sec_coords = route_coords[s_idx:e_idx+1]
                        folium.PolyLine(locations=sec_coords, color=t_color, weight=8, opacity=1.0).add_to(m_res)

                folium.Marker(location=route_coords[0], icon=folium.Icon(color="green", icon="play")).add_to(m_res)
                folium.Marker(location=route_coords[-1], icon=folium.Icon(color="red", icon="stop")).add_to(m_res)
                
                st_folium(m_res, width=1300, height=450, key="result_route_map")
            else:
                st.error("Σφάλμα: Αδυναμία εύρεσης διαδρομής.")
        except Exception as e:
            st.error(f"Αποτυχία επικοινωνίας: {e}")

# ================= TAB 3: HEATMAP =================
with tab3:
    st.markdown("### 📅 Predictive Heatmap")
    st.markdown("Ιστορική κατανομή συμφόρησης ανά μισάωρο καθ' όλη τη διάρκεια της εβδομάδας.")
    
    df_heat = df_history.copy()
    
    # Φίλτρα
    if selected_type != "Όλοι οι Τύποι":
        df_heat['Type'] = df_heat['Road_Segment'].map(road_types)
        df_heat = df_heat[df_heat['Type'] == selected_type]
    if selected_road != "Όλες οι Οδοί":
        df_heat = df_heat[df_heat['Road_Segment'] == selected_road]
        
    if not df_heat.empty:
        df_heat['Limit'] = df_heat['Road_Segment'].apply(lambda r: static_data.get(r, 50))
        df_heat['Congestion'] = ((df_heat['Limit'] - df_heat['Speed_kmh']) / df_heat['Limit']) * 100
        df_heat['Congestion'] = df_heat['Congestion'].clip(lower=0) 
        
        # 🔥 ΕΦΑΡΜΟΓΗ NIGHT-MODE ΣΤΟ HEATMAP ΓΙΑ ΝΑ ΜΗΝ "ΚΟΚΚΙΝΙΖΕΙ" ΤΑ ΒΡΑΔΙΑ ΛΑΘΟΣ
        df_heat['Hour'] = df_heat['Timestamp'].dt.hour
        is_night_mask = (df_heat['Hour'] >= 21) | (df_heat['Hour'] <= 6)
        # Μειώνουμε πλασματικά τη συμφόρηση το βράδυ κατά 60% λόγω έλλειψης αυτοκινήτων/δεδομένων
        df_heat.loc[is_night_mask, 'Congestion'] = df_heat.loc[is_night_mask, 'Congestion'] * 0.4
        
        df_heat['DayOfWeek'] = df_heat['Timestamp'].dt.dayofweek
        day_map = {0: 'Δευτέρα', 1: 'Τρίτη', 2: 'Τετάρτη', 3: 'Πέμπτη', 4: 'Παρασκευή', 5: 'Σάββατο', 6: 'Κυριακή'}
        df_heat['Ημέρα'] = df_heat['DayOfWeek'].map(day_map)
        df_heat['Μισάωρο'] = df_heat['Timestamp'].dt.floor('30min').dt.strftime('%H:%M')
        
        heatmap_data = df_heat.groupby(['DayOfWeek', 'Ημέρα', 'Μισάωρο'])['Congestion'].mean().reset_index()
        pivot_df = heatmap_data.pivot(index='Μισάωρο', columns='Ημέρα', values='Congestion')
        
        days_order = ['Κυριακή', 'Δευτέρα', 'Τρίτη', 'Τετάρτη', 'Πέμπτη', 'Παρασκευή', 'Σάββατο']
        pivot_df = pivot_df[[d for d in days_order if d in pivot_df.columns]]
        
        all_half_hours = [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]
        pivot_df = pivot_df.reindex(all_half_hours).dropna(how='all')
        pivot_df = pivot_df.interpolate(method='linear', limit=4, limit_area='inside')
        
        if not pivot_df.empty:
            c1, c2, c3 = st.columns(3)
            peak_row = heatmap_data.loc[heatmap_data['Congestion'].idxmax()]
            c1.metric("Μέγιστη Συμφόρηση", f"{peak_row['Congestion']:.1f}%", f"{peak_row['Ημέρα']} στις {peak_row['Μισάωρο']}", delta_color="inverse")
            
            day_avg = heatmap_data.groupby('Ημέρα')['Congestion'].mean()
            worst_day = day_avg.idxmax()
            c2.metric("Κρισιμότερη Ημέρα", f"{day_avg.max():.1f}%", f"Αθροιστικός Μ.Ο. - {worst_day}", delta_color="inverse")
            
            best_row = heatmap_data.loc[heatmap_data['Congestion'].idxmin()]
            c3.metric("Βέλτιστο Παράθυρο", f"{best_row['Congestion']:.1f}%", f"{best_row['Ημέρα']} στις {best_row['Μισάωρο']}", delta_color="normal")
            
            # Χρώματα Enterprise
            dramatic_scale = [[0.0, "#10B981"], [0.3, "#10B981"], [0.45, "#F59E0B"], [0.65, "#EF4444"], [1.0, "#7F1D1D"]]

            fig_heat = px.imshow(
                pivot_df, x=pivot_df.columns, y=pivot_df.index,
                color_continuous_scale=dramatic_scale, range_color=[20, 70], aspect="auto", height=700
            )
            fig_heat.update_traces(xgap=2, ygap=2, texttemplate="%{z:.0f}%")
            fig_heat.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="#E2E8F0", size=12),
                xaxis=dict(side="top", tickfont=dict(size=14, weight="bold")), 
                yaxis=dict(autorange="reversed", tickmode="linear", tickfont=dict(size=11)),
                coloraxis_colorbar=dict(title="Συμφόρηση", ticksuffix="%", dtick=10)
            )
            st.plotly_chart(fig_heat, use_container_width=True)
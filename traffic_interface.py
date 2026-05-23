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

# --- 1. ΡΥΘΜΙΣΕΙΣ & ΕΠΑΓΓΕΛΜΑΤΙΚΟ CSS ---
st.set_page_config(page_title="Patras Traffic Analytics", layout="wide")

st.markdown("""
<style>
    /* Καθαρό εταιρικό/ακαδημαϊκό στυλ */
    .stApp { background-color: #F8FAFC; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
    h1, h2, h3, h4, p, label, div, span { color: #0F172A !important; }
    
    /* Λευκές κάρτες για οργάνωση πληροφορίας */
    .block-container { background: #FFFFFF; border-radius: 12px; padding: 2rem !important; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid #E2E8F0; }
    div[data-testid="metric-container"] { background-color: #FFFFFF !important; border: 1px solid #CBD5E1; border-radius: 8px; padding: 15px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
    [data-testid="stMetricValue"] { color: #0369A1 !important; font-weight: 800 !important; }
    [data-testid="stMetricLabel"] { color: #475569 !important; font-weight: 600 !important; font-size: 1.1rem !important; }
    
    /* Μενού & Tabs */
    [data-testid="stSidebar"] { background-color: #F1F5F9 !important; border-right: 1px solid #E2E8F0; }
    button[data-baseweb="tab"] { font-weight: 600; color: #475569 !important; font-size: 1.1rem; }
    button[data-baseweb="tab"][aria-selected="true"] { color: #0369A1 !important; border-bottom: 3px solid #0369A1 !important; background-color: #F0F9FF; }
    
    /* Φίλτρα */
    .stSelectbox > div > div { background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 6px; }
</style>
""", unsafe_allow_html=True)

# --- 2. HEADER ---
c_logo, c_title = st.columns([1, 8])
if os.path.exists("upatras_logo.png"): c_logo.image("upatras_logo.png", width=90)
c_title.markdown("### Πανεπιστήμιο Πατρών - Εργαστήριο Συστημάτων Μεταφορών\n# Patras Traffic Analytics <span style='color:#0369A1;'>PRO</span>", unsafe_allow_html=True)
st.divider()

# --- 3. ΒΟΗΘΗΤΙΚΕΣ ΣΥΝΑΡΤΗΣΕΙΣ (ΕΛΛΗΝΙΚΑ & ΝΥΧΤΑ) ---
def format_road_name(raw_name):
    """Μετατρέπει τα Greeklish ονόματα από το dataset σε όμορφα Ελληνικά."""
    translations = {
        "25hs Martiou": "25ης Μαρτίου",
        "28hs_oktovriou_othonos_kanakari_roufou": "Καραϊσκάκη (28ης Οκτ) & Κανακάρη",
        "3ou_oreivat_goynari_papadiamantopoulou_mini_": "Γούναρη & Παπαδιαμαντοπούλου",
        "Mini_perimetriki_ag_sofias_telos": "Μίνι Περιμετρική (Αγ. Σοφίας)",
        "Mini_perimetriki_agrafwn_telos_rev": "Μίνι Περιμετρική (Αγράφων - Αντίθετο)",
        "ag_andreou_gerokostopoulou": "Αγίου Ανδρέου & Γεροκωστοπούλου",
        "ag_andreou_start_gerokostopoulou": "Αγίου Ανδρέου (Αρχή)"
    }
    if raw_name in translations: return translations[raw_name]
    
    # Γενικός κανόνας αν δεν υπάρχει στο λεξικό
    clean = str(raw_name).replace("_", " ").title()
    if "Rev" in clean: clean = clean.replace("Rev", "(Αντίθετο Ρεύμα)")
    return clean

def is_night_time(time_str):
    """Επιστρέφει True αν η ώρα είναι μεταξύ 22:00 και 06:00."""
    try:
        hour = int(time_str.split(':')[0])
        return hour >= 22 or hour <= 6
    except: return False

def get_hybrid_color(speed, limit, is_night):
    """Υπολογίζει το χρώμα. Το βράδυ κάνει downgrade τη συμφόρηση κατά 1 επίπεδο."""
    if pd.isna(speed) or speed < 5: return "#94A3B8" # Γκρι για έλλειψη δεδομένων
    ratio = speed / limit if limit > 0 else 1
    
    if ratio < 0.4: cat = "red"
    elif ratio < 0.75: cat = "orange"
    else: cat = "green"
    
    # Έξυπνη αλλαγή για το βράδυ
    if is_night:
        if cat == "red": cat = "orange"
        elif cat == "orange": cat = "green"
        
    if cat == "red": return "#E3000F"    # Standard Red
    if cat == "orange": return "#FF9900" # Standard Orange/Yellow
    return "#00B300"                     # Standard Green

# --- 4. ΦΟΡΤΩΣΗ ΔΕΔΟΜΕΝΩΝ ---
@st.cache_data
def load_all_data():
    with open("road_geometry.json", "r", encoding="utf-8") as f: geom = json.load(f)
    df = pd.read_csv("live_traffic_data.csv", sep=";")
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='mixed', errors='coerce')
    st_data, r_types = {}, {}
    if os.path.exists("traffic_patra.xlsx"):
        ex = pd.concat([pd.read_excel("traffic_patra.xlsx", sheet_name="Φύλλο1"), pd.read_excel("traffic_patra.xlsx", sheet_name="Φύλλο2")])
        for _, r in ex.iterrows():
            st_data[r['Road_Segment']] = r.get('Static_Speed', 50)
            r_types[r['Road_Segment']] = str(r.get('Road_type', 'secondary')).strip()
    return st_data, r_types, geom, df

static_data, road_types, geometry_data, df_history = load_all_data()
API_KEYS = ["UsA5r09FOSV6PmRd4NZFF3JCW3y6N2o1", "Nz9zgm9uxG3Pd70dK2OYvEtdktn8PQSD"]

# Γεωμετρικές μετατροπές
to_mercator = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
to_wgs84 = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
def get_parallel_line(coords, dist=3.5): 
    try:
        line = LineString([to_mercator.transform(c[1], c[0]) for c in coords]).parallel_offset(dist, side='right', join_style=1) 
        c_out = []
        if line.geom_type == 'MultiLineString':
            for sl in line.geoms: c_out.extend(list(sl.coords))
        else: c_out = list(line.coords)
        return [[y, x] for x, y in [to_wgs84.transform(x, y) for x, y in c_out]]
    except: return coords

# --- 5. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Φίλτρα Ανάλυσης")
    st.markdown("---")
    valid_dates = sorted(df_history['Timestamp'].dt.date.dropna().unique())
    sel_date = st.selectbox("📅 Ημερομηνία", valid_dates, index=len(valid_dates)-1)
    
    df_day = df_history[df_history['Timestamp'].dt.date == sel_date]
    valid_times = sorted(df_day['Timestamp'].dt.strftime('%H:%M').dropna().unique())
    sel_time = st.selectbox("⏱️ Ώρα", valid_times, index=len(valid_times)-1)
    st.markdown("---")
    
    types = ["Όλοι οι Τύποι"] + sorted(list(set(road_types.values())))
    sel_type = st.selectbox("🛤️ Κατηγορία Οδού", types)
    
    # Εφαρμογή Ελληνικών ονομάτων στο μενού επιλογής δρόμου
    available_roads = [r for r in geometry_data.keys() if sel_type == "Όλοι οι Τύποι" or road_types.get(r) == sel_type]
    road_display_dict = {r: format_road_name(r) for r in available_roads}
    
    display_to_raw = {v: k for k, v in road_display_dict.items()}
    display_names = ["Όλες οι Οδοί"] + sorted(list(road_display_dict.values()))
    sel_road_display = st.selectbox("📍 Συγκεκριμένη Οδός", display_names)
    sel_road_raw = display_to_raw.get(sel_road_display, "Όλες οι Οδοί")

# Εξαγωγή live ταχυτήτων
current_df = df_history[(df_history['Timestamp'].dt.date == sel_date) & (df_history['Timestamp'].dt.strftime('%H:%M') <= sel_time)].drop_duplicates(subset=['Road_Segment'], keep='last')
speeds = dict(zip(current_df['Road_Segment'], current_df['Speed_kmh']))
night_mode_active = is_night_time(sel_time)

# --- 6. TABS ---
tab1, tab2, tab3 = st.tabs(["🗺️ Ανάλυση Δικτύου", "📍 Έξυπνος Αλγόριθμος Πλοήγησης (TomTom)", "📅 Στατιστικά & Heatmap"])

with tab1:
    st.markdown(f"#### Αποτύπωση Κυκλοφορίας: <span style='color:#0369A1;'>{sel_date}</span> στις <span style='color:#0369A1;'>{sel_time}</span>", unsafe_allow_html=True)
    if night_mode_active:
        st.caption("🌙 Ενεργοποιήθηκε η νυχτερινή προσαρμογή χρωμάτων.")

    m = folium.Map(location=[38.2462, 21.7351], zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', attr='Google Maps')
    
    for r, coords in geometry_data.items():
        speed = speeds.get(r, static_data.get(r, 50))
        limit = static_data.get(r, 50)
        c_coords = get_parallel_line(coords) if "_rev" in r.lower() else coords
        
        is_match = (sel_type == "Όλοι οι Τύποι" or road_types.get(r) == sel_type)
        if sel_road_raw != "Όλες οι Οδοί":
            if r == sel_road_raw: color, weight, opacity = get_hybrid_color(speed, limit, night_mode_active), 8, 1.0
            else: color, weight, opacity = "#94A3B8", 3, 0.4
        else:
            if is_match: color, weight, opacity = get_hybrid_color(speed, limit, night_mode_active), 6, 0.9
            else: color, weight, opacity = "#94A3B8", 3, 0.4

        line = folium.PolyLine(locations=c_coords, color=color, weight=weight, opacity=opacity, tooltip=f"{format_road_name(r)}: {speed} km/h").add_to(m)

        # Εμφάνιση κειμένου ΠΑΝΤΟΥ με μαύρα γράμματα αν έχει επιλεγεί η οδός
        if sel_road_raw != "Όλες οι Οδοί" and r == sel_road_raw:
            PolyLineTextPath(line, f'  {format_road_name(r)}  ', repeat=False, offset=8, attributes={'fill': '#000000', 'font-weight': 'bold', 'font-size': '16'}).add_to(m)

    st_folium(m, width=1300, height=550)
    
    # --- Στατιστικά Κάτω από τον Χάρτη ---
    if sel_road_raw == "Όλες οι Οδοί":
        if not current_df.empty:
            st.markdown("---")
            st.markdown("### 📊 Συνοπτική Εικόνα Δικτύου")
            
            c1, c2, c3 = st.columns(3)
            avg_s = round(current_df['Speed_kmh'].mean(), 1)
            c1.metric("🏎️ Μέση Ταχύτητα Πόλης", f"{avg_s} km/h")
            c2.metric("🛣️ Ενεργά Σημεία", len(current_df))
            
            # Υπολογισμός χειρότερου δρόμου
            current_df['Limit'] = current_df['Road_Segment'].apply(lambda x: static_data.get(x, 50))
            current_df['Ratio'] = current_df['Speed_kmh'] / current_df['Limit']
            worst = current_df.loc[current_df['Ratio'].idxmin()]
            c3.metric("🤯 Πιο Αργό Σημείο", f"{worst['Speed_kmh']} km/h", format_road_name(worst['Road_Segment']), delta_color="inverse")
            
    else:
        st.markdown("---")
        st.markdown(f"### 📊 Στατιστικά Οδού: {format_road_name(sel_road_raw)}")
        r_day = df_day[df_day['Road_Segment'] == sel_road_raw]
        if not r_day.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Ταχύτητα Τώρα", f"{speeds.get(sel_road_raw, 'N/A')} km/h")
            c2.metric("Μέγιστη (24h)", f"{r_day['Speed_kmh'].max()} km/h")
            c3.metric("Ελάχιστη (24h)", f"{r_day['Speed_kmh'].min()} km/h")

with tab2:
    st.markdown("### 📍 Επιλογή Σημείων Διαδρομής")
    st.info("Κάντε κλικ σε 2 διαφορετικά σημεία πάνω στον χάρτη για να επιλέξετε Αφετηρία και Προορισμό.")
    
    if 'start' not in st.session_state: st.session_state.start = None
    if 'end' not in st.session_state: st.session_state.end = None
    if st.button("🔄 Καθαρισμός Σημείων"): st.session_state.start = None; st.session_state.end = None; st.rerun()
    
    col_s, col_e = st.columns(2)
    col_s.success(f"🟢 **Αφετηρία:** {st.session_state.start if st.session_state.start else 'Αναμονή...'}")
    col_e.error(f"🔴 **Προορισμός:** {st.session_state.end if st.session_state.end else 'Αναμονή...'}")

    m_route = folium.Map(location=[38.2462, 21.7351], zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', attr='Google Maps')
    for r, coords in geometry_data.items(): folium.PolyLine(locations=coords, color="#0369A1", weight=3, opacity=0.3).add_to(m_route)
    
    if st.session_state.start: folium.Marker(st.session_state.start, icon=folium.Icon(color="green")).add_to(m_route)
    if st.session_state.end: folium.Marker(st.session_state.end, icon=folium.Icon(color="red")).add_to(m_route)
    
    click_data = st_folium(m_route, width=1300, height=450, key="route_map")
    
    if click_data and click_data.get("last_clicked"):
        pt = [click_data["last_clicked"]["lat"], click_data["last_clicked"]["lng"]]
        if not st.session_state.start: st.session_state.start = pt
        elif not st.session_state.end and pt != st.session_state.start: st.session_state.end = pt
        st.rerun()
    
    if st.session_state.start and st.session_state.end:
        s_str = f"{st.session_state.start[0]},{st.session_state.start[1]}"
        e_str = f"{st.session_state.end[0]},{st.session_state.end[1]}"
        url = f"https://api.tomtom.com/routing/1/calculateRoute/{s_str}:{e_str}/json"
        
        try:
            with st.spinner('Υπολογισμός μέσω TomTom...'):
                res = requests.get(url, params={'key': random.choice(API_KEYS), 'traffic': 'true', 'routeType': 'fastest', 'sectionType': 'traffic'}, timeout=10)
            if res.status_code == 200:
                route = res.json()['routes'][0]
                summary = route['summary']
                
                st.markdown("---")
                st.markdown("#### Αποτελέσματα Δρομολόγησης")
                r1, r2, r3 = st.columns(3)
                r1.metric("⏱️ Χρόνος Ταξιδιού", f"{round(summary['travelTimeInSeconds']/60)} λεπτά")
                r2.metric("🏎️ Μέση Ταχύτητα", f"{round((summary['lengthInMeters']/1000) / (summary['travelTimeInSeconds']/3600), 1)} km/h")
                r3.metric("📏 Απόσταση", f"{round(summary['lengthInMeters']/1000, 2)} χλμ")
                
                m_res = folium.Map(location=[route['legs'][0]['points'][0]['latitude'], route['legs'][0]['points'][0]['longitude']], zoom_start=14, tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', attr='Google Maps')
                
                # Ζωγραφική της διαδρομής
                pts = [[p['latitude'], p['longitude']] for p in route['legs'][0]['points']]
                folium.PolyLine(locations=pts, color="#0369A1", weight=8, opacity=0.8).add_to(m_res)
                
                # Χρωματισμός κίνησης (TomTom)
                for sec in route.get('sections', []):
                    if sec.get('sectionType') == 'TRAFFIC':
                        s_idx, e_idx, mag = sec.get('startPointIndex', 0), sec.get('endPointIndex', len(pts)-1), sec.get('magnitudeOfDelay', 0)
                        tc = "#E3000F" if mag >= 3 else "#FF9900" if mag > 0 else "#00B300"
                        folium.PolyLine(locations=pts[s_idx:e_idx+1], color=tc, weight=8, opacity=1.0).add_to(m_res)
                        
                folium.Marker(st.session_state.start, icon=folium.Icon(color="green")).add_to(m_res)
                folium.Marker(st.session_state.end, icon=folium.Icon(color="red")).add_to(m_res)
                st_folium(m_res, width=1300, height=400, key="final_route")
            else:
                st.error("Αδυναμία εύρεσης διαδρομής μεταξύ αυτών των 2 σημείων. Δοκιμάστε πιο κοντά στον δρόμο.")
        except: st.error("Σφάλμα σύνδεσης με το TomTom API.")

with tab3:
    st.markdown("### 📅 Εβδομαδιαίος Χάρτης Συμφόρησης")
    st.markdown("Ανάλυση ιστορικών δεδομένων ανά ώρα και ημέρα της εβδομάδας.")
    
    df_heat = df_history.copy()
    df_heat.loc[df_heat['Speed_kmh'] < 2, 'Speed_kmh'] = 25.0
    
    if sel_type != "Όλοι οι Τύποι": df_heat = df_heat[df_heat['Road_Segment'].map(road_types) == sel_type]
    if sel_road_raw != "Όλες οι Οδοί": df_heat = df_heat[df_heat['Road_Segment'] == sel_road_raw]
        
    if not df_heat.empty:
        df_heat['Limit'] = df_heat['Road_Segment'].apply(lambda r: static_data.get(r, 50))
        df_heat['Congestion'] = (((df_heat['Limit'] - df_heat['Speed_kmh']) / df_heat['Limit']) * 100).clip(lower=0)
        df_heat['Ημέρα'] = df_heat['Timestamp'].dt.dayofweek.map({0:'Δευτέρα', 1:'Τρίτη', 2:'Τετάρτη', 3:'Πέμπτη', 4:'Παρασκευή', 5:'Σάββατο', 6:'Κυριακή'})
        df_heat['Μισάωρο'] = df_heat['Timestamp'].dt.floor('30min').dt.strftime('%H:%M')
        
        heatmap_data = df_heat.groupby(['Ημέρα', 'Μισάωρο'])['Congestion'].mean().reset_index()
        pivot_df = heatmap_data.pivot(index='Μισάωρο', columns='Ημέρα', values='Congestion').reindex(columns=['Δευτέρα', 'Τρίτη', 'Τετάρτη', 'Πέμπτη', 'Παρασκευή', 'Σάββατο', 'Κυριακή']).reindex([f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]).dropna(how='all').interpolate(method='linear', limit=4, limit_area='inside')
        
        if not pivot_df.empty:
            scale = [[0.0, "#00B300"], [0.35, "#FF9900"], [0.55, "#E3000F"], [0.8, "#990000"], [1.0, "#4A0000"]]
            fig_heat = px.imshow(pivot_df, labels=dict(x="Ημέρα", y="Ώρα", color="Συμφόρηση (%)"), x=pivot_df.columns, y=pivot_df.index, color_continuous_scale=scale, range_color=[20, 70], text_auto=".0f", aspect="auto", height=700)
            fig_heat.update_traces(xgap=4, ygap=4, texttemplate="%{z:.0f}%")
            fig_heat.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="#0F172A"), xaxis=dict(side="top"), yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig_heat, use_container_width=True)
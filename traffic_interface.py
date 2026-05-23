import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.express as px
import json

# ==========================================
# 1. ΒΑΣΙΚΕΣ ΡΥΘΜΙΣΕΙΣ (WIDE LAYOUT)
# ==========================================
st.set_page_config(page_title="Κέντρο Ελέγχου Κυκλοφορίας Πάτρας", layout="wide")

hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# ==========================================
# 2. ΦΟΡΤΩΣΗ ΔΕΔΟΜΕΝΩΝ (ΜΕ CACHE)
# ==========================================
@st.cache_data
def load_data():
    try:
        df = pd.read_csv('live_traffic_data.csv', sep=';')
    except:
        df = pd.read_csv('live_traffic_data.csv')
        
    with open('road_geometry.json', 'r', encoding='utf-8') as f:
        geojson_data = json.load(f)
    return df, geojson_data

df, geojson_data = load_data()

# ==========================================
# 3. ΠΛΑΪΝΟ ΜΕΝΟΥ (SIDEBAR) & ΛΟΓΟΤΥΠΟ
# ==========================================
# Λογότυπο Πανεπιστημίου Πατρών
st.sidebar.image("https://upload.wikimedia.org/wikipedia/el/8/87/University_of_Patras_Logo.png", use_container_width=True)

st.sidebar.title("⚙️ Πίνακας Ελέγχου")
st.sidebar.markdown("---")

dates = sorted(df['Date'].unique())
times = sorted(df['Time'].unique())
vehicle_types = ["Όλοι οι Τύποι"] + list(df['Vehicle_Type'].dropna().unique())
roads = ["Όλες οι Οδοί"] + list(df['Road'].unique())

selected_date = st.sidebar.selectbox("Επιλέξτε μέρα:", dates)
selected_time = st.sidebar.selectbox("Επιλέξτε ώρα:", times)
selected_type = st.sidebar.selectbox("Επιλέξτε τύπο οχήματος:", vehicle_types)
selected_road = st.sidebar.selectbox("Επιλέξτε δρόμο:", roads)

st.sidebar.markdown("---")
st.sidebar.info("Παρατηρητήριο Κυκλοφορίας | Πανεπιστήμιο Πατρών")

filtered_df = df[(df['Date'] == selected_date) & (df['Time'] == selected_time)]

if selected_road != "Όλες οι Οδοί":
    filtered_df = filtered_df[filtered_df['Road'] == selected_road]
if selected_type != "Όλοι οι Τύποι" and 'Vehicle_Type' in filtered_df.columns:
    filtered_df = filtered_df[filtered_df['Vehicle_Type'] == selected_type]

# ==========================================
# 4. ΒΑΣΙΚΟΙ ΔΕΙΚΤΕΣ (KPI CARDS)
# ==========================================
st.title(f"📍 Αποτύπωση Κυκλοφορίας: {selected_date} στις {selected_time}")

if not filtered_df.empty:
    avg_speed = round(filtered_df['Speed_kmh'].mean(), 1)
    worst_road_row = filtered_df.loc[filtered_df['Speed_kmh'].idxmin()]
    worst_road = worst_road_row['Road']
    worst_speed = worst_road_row['Speed_kmh']
    high_cong_count = len(filtered_df[filtered_df['Congestion_Level'] == 'High'])
    total_roads = len(filtered_df)
    cong_percentage = round((high_cong_count / total_roads) * 100) if total_roads > 0 else 0
else:
    avg_speed = 0; worst_road = "-"; worst_speed = 0; cong_percentage = 0

col1, col2, col3 = st.columns(3)
col1.metric(label="Μέση Ταχύτητα Δικτύου", value=f"{avg_speed} km/h")
col2.metric(label="Δρόμοι με Υψηλή Συμφόρηση", value=f"{cong_percentage}%", delta="Τρέχουσα Κατάσταση", delta_color="inverse")
col3.metric(label="Πιο Επιβαρυμένη Οδός", value=worst_road, delta=f"{worst_speed} km/h")

st.markdown("---")

# ==========================================
# 5. ΧΑΡΤΗΣ ΚΑΙ ΔΙΑΓΡΑΜΜΑΤΑ (ΕΠΑΓΓΕΛΜΑΤΙΚΑ)
# ==========================================
map_col, chart_col = st.columns([6, 4])

# Επαγγελματική Παλέτα Χρωμάτων
color_map_hex = {'High': '#E63946', 'Medium': '#F4A261', 'Low': '#2A9D8F'}
color_map_rgb = {'High': [230, 57, 70], 'Medium': [244, 162, 97], 'Low': [42, 157, 143]}

road_status = {}
for _, row in filtered_df.iterrows():
    # Δυναμικό Πάχος Δρόμου
    line_width = 15 if row['Congestion_Level'] == 'High' else (8 if row['Congestion_Level'] == 'Medium' else 4)
    road_status[row['Road']] = {
        'speed': row['Speed_kmh'],
        'color': color_map_rgb.get(row['Congestion_Level'], [128, 128, 128]),
        'width': line_width
    }

paths = []
for feature in geojson_data['features']:
    road_name = feature['properties'].get('name')
    if road_name in road_status:
        coords = feature['geometry']['coordinates']
        if feature['geometry']['type'] == 'MultiLineString': coords = coords[0]
        paths.append({
            "path": coords, "name": road_name, "color": road_status[road_name]['color'], 
            "speed": road_status[road_name]['speed'], "width": road_status[road_name]['width']
        })

with map_col:
    st.subheader("🗺️ Διαδραστικός Χάρτης Κυκλοφορίας")
    if paths:
        view_state = pdk.ViewState(latitude=38.2462, longitude=21.7351, zoom=14.5, pitch=50)
        path_layer = pdk.Layer(
            "PathLayer", paths, pickable=True, get_color="color", 
            width_scale=2, width_min_pixels=2, get_path="path", get_width="width"
        )
        r = pdk.Deck(layers=[path_layer], initial_view_state=view_state, tooltip={"html": "<b>Οδός:</b> {name} <br/> <b>Ταχύτητα:</b> {speed} km/h", "style": {"backgroundColor": "steelblue", "color": "white"}})
        st.pydeck_chart(r, use_container_width=True)
    else:
        st.warning("Δεν βρέθηκαν δεδομένα γεωμετρίας.")

with chart_col:
    st.subheader("📊 Αναλυτικά Στοιχεία")
    if not filtered_df.empty:
        # Μπαράκια (Bar Chart)
        top_worst = filtered_df.sort_values(by='Speed_kmh').head(7)
        fig_bar = px.bar(top_worst, x='Speed_kmh', y='Road', orientation='h', title="Οδοί με τη μεγαλύτερη καθυστέρηση", color='Congestion_Level', color_discrete_map=color_map_hex)
        fig_bar.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis=dict(showgrid=False, title=""), yaxis=dict(showgrid=False, title=""), showlegend=False, margin=dict(l=0, r=0, t=40, b=0))
        fig_bar.update_yaxes(categoryorder='total ascending')
        st.plotly_chart(fig_bar, use_container_width=True)
        
        st.write("") 
        
        # Πίτα (Donut Chart)
        fig_pie = px.pie(filtered_df, names='Congestion_Level', title="Κατανομή Κυκλοφοριακού Φόρτου", color='Congestion_Level', color_discrete_map=color_map_hex)
        fig_pie.update_traces(hole=.5, textinfo='percent+label', hoverinfo='label+percent')
        fig_pie.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=False, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Δεν υπάρχουν δεδομένα.")
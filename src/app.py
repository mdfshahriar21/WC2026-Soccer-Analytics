import streamlit as st
import psycopg2
import pandas as pd
import os
import plotly.express as px
from dotenv import load_dotenv

load_dotenv('/home/mystic31/WC2026-Soccer-Analytics/.env')
DATABASE_URL = st.secrets.get("DATABASE_URL") or os.getenv("DATABASE_URL")

# ------------------------------------------------------------
# Block 1: Database Connection (cached)
# ------------------------------------------------------------
@st.cache_resource
def get_connection():
    url = st.secrets.get("DATABASE_URL") or os.getenv("DATABASE_URL")
    return psycopg2.connect(url)

def run_query(query, params=None):
    conn = get_connection()
    return pd.read_sql(query, conn, params=params)

# ------------------------------------------------------------
# Block 2: Page Configuration & Header
# ------------------------------------------------------------
st.set_page_config(
    page_title="WC2026 Player Analytics",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ WC2026 Player Analytics")
st.markdown("### Match and player data from FIFA World Cup 2026 performance reports")
st.caption("⚠️ Stats reflect total in-match actions across available match reports. Defensive Score measures volume of defensive actions, not efficiency.")

def get_summary_stats():
    query = """
        SELECT 
            COUNT(DISTINCT match_code) as matches,
            COUNT(DISTINCT player_name) as players
        FROM player_stats
    """
    df = run_query(query)
    if df.empty:
        return {"matches": 0, "players": 0}
    return df.iloc[0].to_dict()

stats = get_summary_stats()
col1, col2 = st.columns(2)
with col1:
    st.metric(label="Total Matches", value=stats['matches'])
with col2:
    st.metric(label="Unique Players", value=stats['players'])

# ------------------------------------------------------------
# Block 3: Most Dangerous Player
# ------------------------------------------------------------
def get_dangerous_players(limit=10):
    query = """
        SELECT 
            player_name,
            team,
            SUM(attempts_at_goal) as total_chances,
            SUM(goals) as total_goals,
            SUM(attempts_at_goal + goals) as danger_score
        FROM player_stats
        GROUP BY player_name, team
        ORDER BY danger_score DESC
        LIMIT %s
    """
    return run_query(query, (limit,))

# ------------------------------------------------------------
# Block 4: Endurance King
# ------------------------------------------------------------
def get_endurance_players(limit=10):
    query = """
        SELECT 
            player_name,
            team,
            AVG(total_distance_m) / 1000.0 as avg_distance_per_match_km
        FROM player_stats
        GROUP BY player_name, team
        ORDER BY avg_distance_per_match_km DESC
        LIMIT %s
    """
    return run_query(query, (limit,))

# ------------------------------------------------------------
# Block 5: Speed Star
# ------------------------------------------------------------
def get_speed_stars(limit=10):
    query = """
        SELECT 
            player_name,
            team,
            MAX(top_speed_kmh) as top_speed_kmh
        FROM player_stats
        GROUP BY player_name, team
        ORDER BY top_speed_kmh DESC
        LIMIT %s
    """
    return run_query(query, (limit,))

# ------------------------------------------------------------
# Block 6: GK Saves (using blocks as proxy)
# ------------------------------------------------------------
#def get_gk_saves(limit=10):
    query = """
        SELECT 
            player_name,
            team,
            SUM(blocks) as total_blocks,
            SUM(interceptions) as total_interceptions,
            SUM(blocks + interceptions) as defensive_actions
        FROM player_stats
        GROUP BY player_name, team
        ORDER BY defensive_actions DESC
        LIMIT %s
    """
    return run_query(query, (limit,))

# ------------------------------------------------------------
# Block 7: Standout Passer
# ------------------------------------------------------------
def get_standout_passer(limit=10):
    query = """
        SELECT 
            player_name,
            team,
            ROUND(AVG(pass_completion_pct)::numeric, 1) as avg_completion_pct,
            SUM(passes_attempted) as total_passes_attempted,
            SUM(passes_completed) as total_passes_completed,
            COUNT(DISTINCT match_code) as matches_played
        FROM player_stats
        WHERE passes_attempted >= 20
        GROUP BY player_name, team
        HAVING SUM(passes_attempted) >= 200
        ORDER BY avg_completion_pct DESC
        LIMIT %s
    """
    return run_query(query, (limit,))

# ------------------------------------------------------------
# Block 8: Standout Defender
# ------------------------------------------------------------
def get_standout_defender(limit=10):
    query = """
        SELECT 
            player_name,
            team,
            SUM(tackles_won) as total_tackles_won,
            SUM(interceptions) as total_interceptions,
            SUM(blocks) as total_blocks,
            SUM(clearances) as total_clearances,
            SUM(tackles_won + interceptions + blocks + clearances) as defensive_score
        FROM player_stats
        GROUP BY player_name, team
        ORDER BY defensive_score DESC
        LIMIT %s
    """
    return run_query(query, (limit,))

# ------------------------------------------------------------
# Tabs
# ------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "⚡ Most Dangerous",
    "🏃 Endurance King", 
    "💨 Speed Star",
    #"🧤 GK Saves",
    "🎯 Standout Passer",
    "🛡️ Standout Defender"
])

# ---- Tab 1 ----
with tab1:
    st.subheader("Top 10 Most Dangerous Players")
    df = get_dangerous_players()
    if not df.empty:
        col_chart, col_metric = st.columns([3, 1])
        with col_metric:
            top = df.iloc[0]
            second = df.iloc[1] if len(df) > 1 else None
            delta = top['danger_score'] - second['danger_score'] if second is not None else 0.0
            st.metric(
                label="⚡ Most Dangerous",
                value=top['player_name'],
                delta=f"{delta:.0f} pts ahead of 2nd"
            )
        with col_chart:
            fig = px.bar(
                df,
                x='danger_score',
                y='player_name',
                color='team',
                orientation='h',
                title='Danger Score (Attempts + Goals)',
                labels={'danger_score': 'Score', 'player_name': 'Player'},
                height=500
            )
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, width='stretch')
        with st.expander("Show raw data"):
            st.dataframe(df, width='stretch')
    else:
        st.info("No data available.")

# ---- Tab 2 ----
with tab2:
    st.subheader("Top 10 Endurance Players")
    df = get_endurance_players()
    if not df.empty:
        col_chart, col_metric = st.columns([3, 1])
        with col_metric:
            top = df.iloc[0]
            second = df.iloc[1] if len(df) > 1 else None
            delta = top['avg_distance_per_match_km'] - second['avg_distance_per_match_km'] if second is not None else 0.0
            st.metric(
                label="🏃 Endurance King",
                value=top['player_name'],
                delta=f"{delta:.2f} km/match ahead of 2nd"
            )
        with col_chart:
            fig = px.bar(
                df,
                x='avg_distance_per_match_km',
                y='player_name',
                color='team',
                orientation='h',
                title='Average Distance Covered per Match (km)',
                labels={'avg_distance_per_match_km': 'Avg Distance (km)', 'player_name': 'Player'},
                height=500
            )
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, width='stretch')
        with st.expander("Show raw data"):
            st.dataframe(df, width='stretch')
    else:
        st.info("No data available.")

# ---- Tab 3 ----
with tab3:
    st.subheader("Top 10 Speed Stars")
    df = get_speed_stars()
    if not df.empty:
        col_chart, col_metric = st.columns([3, 1])
        with col_metric:
            top = df.iloc[0]
            second = df.iloc[1] if len(df) > 1 else None
            delta = top['top_speed_kmh'] - second['top_speed_kmh'] if second is not None else 0.0
            st.metric(
                label="💨 Speed Star",
                value=top['player_name'],
                delta=f"{delta:.1f} km/h ahead of 2nd"
            )
        with col_chart:
            fig = px.bar(
                df,
                x='top_speed_kmh',
                y='player_name',
                color='team',
                orientation='h',
                title='Top Speed Reached (km/h)',
                labels={'top_speed_kmh': 'Speed (km/h)', 'player_name': 'Player'},
                height=500
            )
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, width='stretch')
        with st.expander("Show raw data"):
            st.dataframe(df, width='stretch')
    else:
        st.info("No data available.")

# ---- Tab 4 ----
#with tab4:
    #st.subheader("Top 10 Goalkeeper/Defensive Actions")
    #df = get_gk_saves()
    #if not df.empty:
        #col_chart, col_metric = st.columns([3, 1])
        #with col_metric:
            #top = df.iloc[0]
            #second = df.iloc[1] if len(df) > 1 else None
            #delta = top['defensive_actions'] - second['defensive_actions'] if second is not None else 0.0
            #st.metric(
                #label="🧤 Most Defensive Actions",
                #value=top['player_name'],
                #delta=f"{delta:.0f} actions ahead of 2nd"
            #)
        #with col_chart:
            #fig = px.bar(
                #df,
                #x='defensive_actions',
                #y='player_name',
                #color='team',
                #orientation='h',
                #title='Blocks + Interceptions',
                #labels={'defensive_actions': 'Actions', 'player_name': 'Player'},
                #height=500
            #)
            #fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            #st.plotly_chart(fig, width='stretch')
        #with st.expander("Show raw data"):
            #st.dataframe(df, width='stretch')
    #else:
        #st.info("No data available.")

# ---- Tab 5 ----
with tab5:
    st.subheader("Top 10 Standout Passers")
    df = get_standout_passer()
    if not df.empty:
        col_chart, col_metric = st.columns([3, 1])
        with col_metric:
            top = df.iloc[0]
            second = df.iloc[1] if len(df) > 1 else None
            delta = top['avg_completion_pct'] - second['avg_completion_pct'] if second is not None else 0.0
            st.metric(
                label="🎯 Standout Passer",
                value=top['player_name'],
                delta=f"{delta:.1f}% ahead of 2nd"
            )
        with col_chart:
            fig = px.bar(
                df,
                x='avg_completion_pct',
                y='player_name',
                color='team',
                orientation='h',
                title='Average Pass Completion %',
                labels={'avg_completion_pct': 'Completion %', 'player_name': 'Player'},
                height=500
            )
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, width='stretch')
        with st.expander("Show raw data"):
            st.dataframe(df, width='stretch')
    else:
        st.info("No data available.")

# ---- Tab 6 ----
with tab6:
    st.subheader("Top 10 Standout Defenders")
    df = get_standout_defender()
    if not df.empty:
        col_chart, col_metric = st.columns([3, 1])
        with col_metric:
            top = df.iloc[0]
            second = df.iloc[1] if len(df) > 1 else None
            delta = top['defensive_score'] - second['defensive_score'] if second is not None else 0.0
            st.metric(
                label="🛡️ Standout Defender",
                value=top['player_name'],
                delta=f"{delta:.0f} pts ahead of 2nd"
            )
        with col_chart:
            fig = px.bar(
                df,
                x='defensive_score',
                y='player_name',
                color='team',
                orientation='h',
                title='Defensive Score (Tackles Won + Interceptions + Blocks + Clearances)',
                labels={'defensive_score': 'Score', 'player_name': 'Player'},
                height=500
            )
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, width='stretch')
        with st.expander("Show raw data"):
            st.dataframe(df, width='stretch')
    else:
        st.info("No data available.")
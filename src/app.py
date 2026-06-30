import streamlit as st
import psycopg2
import pandas as pd
import os
from dotenv import load_dotenv
import plotly.express as px

# Load environment variables
load_dotenv('/home/mystic31/WC2026-Soccer-Analytics/.env')

# ------------------------------------------------------------
# Block 1: Database Connection (cached)
# ------------------------------------------------------------
@st.cache_resource
def get_connection():
    """Return a cached psycopg2 connection using DATABASE_URL from .env"""
    return psycopg2.connect(os.getenv('DATABASE_URL'))

# Helper: Run a query and return a DataFrame
def run_query(query, params=None):
    """Execute a SQL query and return results as a pandas DataFrame"""
    conn = get_connection()
    # Do NOT close the connection – it's cached and reused
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

# Function to get summary counts
def get_summary_stats():
    """Return a dict with total matches and total unique players"""
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

def get_dangerous_players(limit=10):
    """Return top players by danger_score = attempts_at_goal + goals"""
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
    df = run_query(query, (limit,))
    return df

def get_endurance_players(limit=10):
    """Return top players by endurance (total distance covered in km)"""
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
    df = run_query(query, (limit,))
    return df

# Display summary stats as metrics
stats = get_summary_stats()
col1, col2 = st.columns(2)
with col1:
    st.metric(label="Total Matches", value=stats['matches'])
with col2:
    st.metric(label="Unique Players", value=stats['players'])
# Create 6 tabs (only first one implemented for now)
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "⚡ Most Dangerous",
    "🏃 Endurance King", 
    "💨 Speed Star",
    "🧤 GK Saves",
    "🎯 Standout Passer",
    "🛡️ Standout Defender"
])

with tab1:
    st.subheader("Top 10 Most Dangerous Players")
    df_danger = get_dangerous_players()
    if not df_danger.empty:
        fig = px.bar(
            df_danger,
            x='danger_score',
            y='player_name',
            color='team',
            orientation='h',
            title='Danger Score by Player',
            labels={'danger_score': 'Danger Score (Attempts + Goals)', 'player_name': 'Player'},
            height=500
        )
        fig.update_layout(yaxis={'categoryorder': 'total ascending'})  # top at top
        st.plotly_chart(fig, width='stretch')
        
        # Optional: show the raw data
        with st.expander("Show raw data"):
            st.dataframe(df_danger)
    else:
        st.info("No data available.")

with tab2:
    st.subheader("Top 10 Endurance Players")
    df_endurance = get_endurance_players()
    
    if not df_endurance.empty:
        # Split layout: 3/4 for chart, 1/4 for metric
        col1, col2 = st.columns([3, 1])
        
        with col2:
            top = df_endurance.iloc[0]
            second = df_endurance.iloc[1] if len(df_endurance) > 1 else None
            delta = top['avg_distance_per_match_km'] - second['avg_distance_per_match_km'] if second is not None else 0.0
            st.metric(
                label="🏃 Endurance King",
                value=top['player_name'],
                delta=f"{delta:.2f} km/match ahead of 2nd"
            )
        
        with col1:
            fig = px.bar(
                df_endurance,
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
            st.dataframe(df_endurance)
    else:
        st.info("No data available.")
#!/usr/bin/env python3
"""
WC26 Complete Attacker Index — Streamlit Dashboard

Reads data/leaderboard.csv (refreshed automatically by the GitHub Actions
workflow in .github/workflows/update.yml) and renders a live leaderboard.

Run locally: streamlit run dashboard.py
"""
import os
import pandas as pd
import streamlit as st

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "leaderboard.csv")

st.set_page_config(page_title="WC26 Complete Attacker Index", layout="wide")

st.title("World Cup 2026 — Complete Attacker Index")
st.caption(
    "Composite ranking across shooting, passing, dribbling, and defensive metrics. "
    "Auto-refreshed every 8 hours during the tournament."
)

if not os.path.exists(DATA_PATH):
    st.warning(
        "No leaderboard data found yet. Run `scripts/make_sample_data.py` "
        "then `scripts/compute_leaderboard.py` to generate a local test file, "
        "or wait for the next scheduled GitHub Actions run."
    )
    st.stop()

df = pd.read_csv(DATA_PATH)
mtime = os.path.getmtime(DATA_PATH)
st.caption(f"Data last updated: {pd.Timestamp(mtime, unit='s')}")

with st.expander("How the Complete Attacker Index (CAI) is calculated"):
    st.markdown(
        """
        **CAI = 2×z(Goals) + 1.7×z(Dribble%) + 1.4×z(SoT%\*) + 1.4×z(Shots) + 1.1×z(Recoveries/90) + 0.8×z(AT Actions/90) + 0.5×z(Aerial Won%)**

        | Weight | Metric | What it measures |
        |--------|--------|-----------------|
        | 2.0× | **Goals** | Total goals scored |
        | 1.7× | **Dribble%** | Take-on success rate |
        | 1.4× | **SoT%\*** | Shot accuracy — shots on target / shots taken |
        | 1.4× | **Shots** | Total shots taken — rewards getting into shooting positions |
        | 1.1× | **Recoveries/90** | Ball recoveries per 90 minutes |
        | 0.8× | **AT Actions/90** | Tackles won + interceptions in the attacking third per 90 min |
        | 0.5× | **Aerial Won%** | Aerial duel win rate |

        *\* SoT% is credibility-adjusted: players with few shots are shrunk toward the population mean so a single lucky shot doesn't dominate the ranking.*

        All components are z-scored before weighting. Players missing data for an optional metric (e.g. no aerial duels) receive a neutral score (0). Position-agnostic — all outfield players qualify.
        """
    )

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Leaderboard")
    _col_map = {
        "rank":               "rank",
        "Player":             "Player",
        "Squad":              "Squad",
        "CAI":                "CAI",
        "goals_total":        "Goals",
        "shots_total":        "Shots",
        "dribble_success_pct":"Dribble%",
        "SoT%":               "SoT%",
        "recoveries_p90":     "Recoveries/90",
        "at_actions_p90":     "AT Actions/90",
        "Aerial_Won%":        "Aerial Won%",
    }
    _avail = {k: v for k, v in _col_map.items() if k in df.columns}
    st.dataframe(
        df[list(_avail.keys())].rename(columns=_avail).round(1),
        use_container_width=True,
        hide_index=True,
    )

with col2:
    st.subheader("Top 5")
    top5 = df.head(5)
    for _, row in top5.iterrows():
        st.metric(f"#{row['rank']} {row['Player']}", f"CAI {row['CAI']:.2f}", row["Squad"])

st.divider()
st.caption("Data: WhoScored/Opta via nlbair/wc2026-events. Composite methodology and code: see README.md.")

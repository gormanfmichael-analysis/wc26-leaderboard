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
        **CAI = z(SoT%) + z(Goals/90) + z(Aerial Won%) + z(Prog Pass%) + z(Dribble%) + z(Recoveries/90) + z(AT Actions/90)**

        - **SoT%** — shot accuracy (shots on target / shots taken)
        - **Goals/90** — scoring volume per 90 minutes
        - **Aerial Won%** — aerial duel win rate
        - **Prog Pass%** — completion rate on passes advancing the ball ≥10 yards toward goal
        - **Dribble%** — take-on success rate
        - **Recoveries/90** — ball recoveries per 90 minutes
        - **AT Actions/90** — tackles won + interceptions in the attacking third per 90 minutes

        All components are z-scored before summing so no single metric dominates. Players missing data for an optional metric receive a neutral score (0). Position-agnostic — all outfield players qualify regardless of position.
        """
    )

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Leaderboard")
    st.dataframe(
        df[["rank", "Player", "Squad", "CAI",
            "SoT%", "goals_p90", "Aerial_Won%",
            "prog_pass_completion_pct", "dribble_success_pct",
            "recoveries_p90", "at_actions_p90"]]
        .rename(columns={
            "goals_p90":               "Goals/90",
            "Aerial_Won%":             "Aerial Won%",
            "prog_pass_completion_pct":"Prog Pass%",
            "dribble_success_pct":     "Dribble%",
            "recoveries_p90":          "Recoveries/90",
            "at_actions_p90":          "AT Actions/90",
        })
        .round(1),
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

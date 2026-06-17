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
    "Composite ranking from FBref's basic Shooting and Miscellaneous stats. "
    "Auto-refreshed during the tournament — see the data freshness note below."
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
        **CAI = z(SoT%) + z(G/Sh) + z(Aerial Won%) − z(Fouls per 90)**

        - **SoT%** — shot accuracy
        - **G/Sh** — finishing quality (goals per shot)
        - **Aerial Won%** — physical presence
        - **Fouls /90** — discipline (subtracted — fewer is better)

        Built without xG, since Opta withdrew that feed from FBref in
        January 2026 following a data-rights dispute tied to their
        exclusive FIFA World Cup 2026 deal.
        """
    )

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Leaderboard")
    st.dataframe(
        df[["rank", "Player", "Squad", "CAI", "SoT%", "G/Sh", "Aerial_Won%", "fouls_p90"]]
        .rename(columns={"fouls_p90": "Fouls/90"})
        .round(3),
        use_container_width=True,
        hide_index=True,
    )

with col2:
    st.subheader("Top 5")
    top5 = df.head(5)
    for _, row in top5.iterrows():
        st.metric(f"#{row['rank']} {row['Player']}", f"CAI {row['CAI']:.2f}", row["Squad"])

st.divider()
st.caption("Data: FBref (Sports Reference). Composite methodology and code: see README.md.")

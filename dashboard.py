#!/usr/bin/env python3
"""
WC26 Complete Attacker Index — Streamlit Dashboard

Reads data/leaderboard.csv (refreshed automatically by the GitHub Actions
workflow in .github/workflows/update.yml) and renders a live leaderboard.

Run locally: streamlit run dashboard.py
"""
import json
import os
import re
from datetime import datetime

import pandas as pd
import streamlit as st

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "leaderboard.csv")
META_PATH = os.path.join(os.path.dirname(__file__), "data", "meta.json")


def _parse_last_match(filename: str) -> str:
    """Turn 'wc2026_argentina_vs_france_2026-07-19_events.csv' into 'Argentina vs France (Jul 19)'."""
    m = re.match(r"wc2026_(.+?)_(\d{4}-\d{2}-\d{2})_events\.csv", filename)
    if not m:
        return filename.replace(".csv", "")
    teams = m.group(1).replace("_vs_", " vs ").replace("_", " ").title()
    date  = datetime.strptime(m.group(2), "%Y-%m-%d").strftime("%b %-d")
    return f"{teams} ({date})"

st.set_page_config(page_title="WC26 Complete Attacker Index", layout="wide")

st.title("World Cup 2026 — Complete Attacker Index")
if not os.path.exists(DATA_PATH):
    st.warning(
        "No leaderboard data found yet. Run `scripts/make_sample_data.py` "
        "then `scripts/compute_leaderboard.py` to generate a local test file, "
        "or wait for the next scheduled GitHub Actions run."
    )
    st.stop()

df = pd.read_csv(DATA_PATH)
mtime = pd.Timestamp(os.path.getmtime(DATA_PATH), unit="s").strftime("%Y-%m-%d %H:%M UTC")

_meta = {}
if os.path.exists(META_PATH):
    with open(META_PATH) as _f:
        _meta = json.load(_f)

_through = f" · Updated through: {_parse_last_match(_meta['last_match'])}" if _meta.get("last_match") else ""
st.caption(f"Composite ranking across shooting, passing, dribbling, and defensive metrics.{_through} · Data last updated: {mtime}")

with st.expander("How the Complete Attacker Index (CAI) is calculated"):
    st.markdown(
        """
        **CAI = 2×z(Goals) + 1.8×z(Assists) + 1.7×z(Dribble%) + 1.4×z(SoT%\*) + 1.4×z(Shots) + 1.1×z(Recoveries/90) + 0.8×z(AT Actions/90) + 0.5×z(Aerial Won%)**

        | Weight | Metric | What it measures |
        |--------|--------|-----------------|
        | 2.0× | **Goals** | Total goals scored |
        | 1.8× | **Assists** | Total goal assists |
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

with st.sidebar:
    st.header("Filters")
    all_squads = sorted(df["Squad"].dropna().unique().tolist())
    selected_squads = st.multiselect("Team", all_squads, placeholder="All teams")
    if selected_squads:
        df = df[df["Squad"].isin(selected_squads)].reset_index(drop=True)
        df["rank"] = range(1, len(df) + 1)

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Leaderboard")
    _col_map = {
        "rank":               "rank",
        "Player":             "Player",
        "Squad":              "Squad",
        "CAI":                "CAI",
        "goals_total":        "Goals",
        "assists":            "Assists",
        "shots_total":        "Shots",
        "dribble_success_pct":"Dribble%",
        "SoT%":               "SoT%",
        "recoveries_p90":     "Recoveries/90",
        "at_actions_p90":     "AT Actions/90",
        "Aerial_Won%":        "Aerial Won%",
    }
    _avail = {k: v for k, v in _col_map.items() if k in df.columns}
    _display = df[list(_avail.keys())].rename(columns=_avail).round(1)
    _color_cols = [c for c in ["CAI", "Goals", "Assists"] if c in _display.columns]
    _styled = _display.style.background_gradient(subset=_color_cols, cmap="RdYlGn")
    st.dataframe(
        _styled,
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

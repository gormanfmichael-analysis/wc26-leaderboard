#!/usr/bin/env python3
"""
WC26 Leaderboard — Composite Attacker Index (CAI)

Reads data/api_football_raw.csv and computes:

    CAI = z(SoT%) + z(Goals/90) + z(Aerial_Won%)
          + z(Prog_pass_completion%) + z(Dribble_success%)
          + z(Recoveries/90) + z(Key_passes/90) + z(AT_actions/90)

NaN z-scores (players missing data for an optional metric) → 0 (neutral).
Position-agnostic: defenders can rank via AT_actions, Aerial_Won%, etc.

Run: python scripts/compute_leaderboard.py
"""
import os
import sys

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
# Raise to 2 once matchday 2 is complete (~June 22-25 2026)
MIN_APPEARANCES = 1


def zscore(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std(ddof=0)


def main():
    raw_path = os.path.join(DATA_DIR, "api_football_raw.csv")
    if not os.path.exists(raw_path):
        sys.exit("Raw data not found. Run scripts/fetch_stats.py first.")

    df = pd.read_csv(raw_path)

    numeric_cols = [
        "minutes", "appearances",
        "shots_total", "shots_on", "goals_total", "fouls_committed",
        "duels_total", "duels_won",
        "pass_total", "pass_accurate", "prog_pass_total", "prog_pass_accurate", "key_passes",
        "takeons_total", "takeons_won",
        "ball_recoveries", "at_actions",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        else:
            df[col] = 0

    print(f"Total players in raw data: {len(df)}")

    df = df[df["appearances"] >= MIN_APPEARANCES].copy()
    print(f"After appearances >= {MIN_APPEARANCES}: {len(df)}")

    if len(df) < 2:
        sys.exit(f"Only {len(df)} qualifying players — cannot z-score. Check raw data.")

    df["90s"] = df["minutes"].clip(lower=1) / 90

    # ── Shot-based ───────────────────────────────────────────────────────────
    df["SoT%"]      = np.where(df["shots_total"] > 0, df["shots_on"] / df["shots_total"] * 100, np.nan)
    df["goals_p90"] = df["goals_total"] / df["90s"]

    # ── Aerial ───────────────────────────────────────────────────────────────
    df["Aerial_Won%"] = np.where(
        df["duels_total"] > 0,
        df["duels_won"] / df["duels_total"] * 100,
        np.nan,
    )

    # ── Passing ──────────────────────────────────────────────────────────────
    df["prog_pass_completion_pct"] = np.where(
        df["prog_pass_total"] > 0,
        df["prog_pass_accurate"] / df["prog_pass_total"] * 100,
        np.nan,
    )
    df["key_passes_p90"] = df["key_passes"] / df["90s"]

    # ── Dribbles ─────────────────────────────────────────────────────────────
    df["dribble_success_pct"] = np.where(
        df["takeons_total"] > 0,
        df["takeons_won"] / df["takeons_total"] * 100,
        np.nan,
    )

    # ── Defensive volume ─────────────────────────────────────────────────────
    df["recoveries_p90"] = df["ball_recoveries"] / df["90s"]
    df["at_actions_p90"] = df["at_actions"] / df["90s"]

    df = df.dropna(subset=["goals_p90"]).copy()
    print(f"After dropna on required metrics: {len(df)}")
    if len(df) < 2:
        sys.exit(f"Only {len(df)} players after dropna — cannot z-score. Check raw data.")

    # ── Z-scores (NaN → 0 for optional metrics) ──────────────────────────────
    df["z_sot_pct"]              = zscore(df["SoT%"]).fillna(0)
    df["z_goals_p90"]            = zscore(df["goals_p90"])
    df["z_aerial_won"]           = zscore(df["Aerial_Won%"]).fillna(0)
    df["z_prog_pass_completion"] = zscore(df["prog_pass_completion_pct"]).fillna(0)
    df["z_key_passes_p90"]       = zscore(df["key_passes_p90"]).fillna(0)
    df["z_dribble_success"]      = zscore(df["dribble_success_pct"]).fillna(0)
    df["z_recoveries_p90"]       = zscore(df["recoveries_p90"]).fillna(0)
    df["z_at_actions_p90"]       = zscore(df["at_actions_p90"]).fillna(0)

    df["CAI"] = (
        df["z_sot_pct"]
        + df["z_goals_p90"]
        + df["z_aerial_won"]
        + df["z_prog_pass_completion"]
        + df["z_dribble_success"]
        + df["z_recoveries_p90"]
        + df["z_key_passes_p90"]
        + df["z_at_actions_p90"]
    )

    df = df.sort_values("CAI", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))

    out_path = os.path.join(DATA_DIR, "leaderboard.csv")
    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} players → {out_path}")
    print(
        df[["rank", "Player", "Squad", "CAI", "SoT%", "goals_p90", "Aerial_Won%",
            "prog_pass_completion_pct", "recoveries_p90", "at_actions_p90"]]
        .head(10)
        .round(3)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()

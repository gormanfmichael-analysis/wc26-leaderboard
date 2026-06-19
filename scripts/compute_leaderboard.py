#!/usr/bin/env python3
"""
WC26 Leaderboard — Composite Attacker Index (CAI)

Reads data/api_football_raw.csv and computes:

    CAI = 3.0×z(Goals/90) + 2.5×z(Dribble%) + 2.0×z(SoT%†)
          + 1.5×z(Recoveries/90) + 1.0×z(AT_actions/90) + 0.5×z(Aerial_Won%)

    † SoT% uses Bayesian credibility adjustment (K=10 pseudo-shots) so players
      with small shot samples are shrunk toward the population mean rather than
      getting extreme z-scores from a handful of shots.

NaN z-scores (players missing data for an optional metric) → 0 (neutral).
Position-agnostic: defenders can rank via AT_actions, Aerial_Won%, Recoveries.

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

    # SoT% credibility adjustment: Bayesian shrinkage toward the population mean.
    # K_SOT pseudo-shots anchor every player's rate; after K_SOT real shots the
    # observed rate carries 50% weight. Eliminates extreme scores from 1-2 shots.
    K_SOT = 10
    _pop_mean_sot   = float(df["SoT%"].mean())
    _sot_obs        = df["SoT%"].fillna(_pop_mean_sot)  # no-shot players → mean
    df["SoT%_adj"]  = (K_SOT * _pop_mean_sot + df["shots_total"] * _sot_obs) / (K_SOT + df["shots_total"])

    # ── Aerial ───────────────────────────────────────────────────────────────
    df["Aerial_Won%"] = np.where(
        df["duels_total"] > 0,
        df["duels_won"] / df["duels_total"] * 100,
        np.nan,
    )

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

    # ── Weighted z-scores ────────────────────────────────────────────────────
    # Weights reflect priority order: Goals/90 > Dribble% > SoT% >
    # Recoveries/90 > AT Actions/90 > Aerial Won%.
    # NaN z-scores (no data for optional metric) → 0 (neutral contribution).
    df["z_goals_p90"]      = zscore(df["goals_p90"])
    df["z_dribble_success"]= zscore(df["dribble_success_pct"]).fillna(0)
    df["z_sot_adj"]        = zscore(df["SoT%_adj"])           # never NaN
    df["z_recoveries_p90"] = zscore(df["recoveries_p90"]).fillna(0)
    df["z_at_actions_p90"] = zscore(df["at_actions_p90"]).fillna(0)
    df["z_aerial_won"]     = zscore(df["Aerial_Won%"]).fillna(0)

    df["CAI"] = (
        3.0 * df["z_goals_p90"]
        + 2.5 * df["z_dribble_success"]
        + 2.0 * df["z_sot_adj"]
        + 1.5 * df["z_recoveries_p90"]
        + 1.0 * df["z_at_actions_p90"]
        + 0.5 * df["z_aerial_won"]
    )

    df = df.sort_values("CAI", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))

    out_path = os.path.join(DATA_DIR, "leaderboard.csv")
    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} players → {out_path}")
    print(
        df[["rank", "Player", "Squad", "CAI",
            "goals_p90", "dribble_success_pct", "SoT%", "SoT%_adj",
            "recoveries_p90", "at_actions_p90", "Aerial_Won%"]]
        .head(10)
        .round(3)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()

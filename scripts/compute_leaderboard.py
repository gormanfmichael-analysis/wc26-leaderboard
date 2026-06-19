#!/usr/bin/env python3
"""
WC26 Leaderboard — Composite Index

Reads data/api_football_raw.csv (produced by scripts/fetch_stats.py) and
computes the Complete Attacker Index (CAI):

    CAI = z(SoT%) + z(G/Sh) + z(Aerial Won%) − z(Fouls per 90)

  SoT%        — shot accuracy: shots on target / shots taken
  G/Sh        — finishing: goals / shots taken
  Aerial Won% — aerial duel win rate (WhoScored Aerial events)
  Fouls /90   — discipline: subtracted — fewer fouls is better

All four are z-scored before summing so no single metric dominates by range.

Run: python scripts/compute_leaderboard.py
"""
import os
import sys

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
# Minimum appearances to qualify. Event data gives unreliable minute counts
# (a quiet second half leaves no events), so we gate on matches played rather
# than accumulated 90s. Raise to 2 once matchday 2 is complete.
MIN_APPEARANCES = 1


def zscore(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std(ddof=0)


def main():
    raw_path = os.path.join(DATA_DIR, "api_football_raw.csv")
    if not os.path.exists(raw_path):
        sys.exit(
            "Raw data not found. Run scripts/fetch_stats.py first."
        )

    df = pd.read_csv(raw_path)

    numeric_cols = ["minutes", "appearances", "shots_total", "shots_on",
                    "goals_total", "fouls_committed", "duels_total", "duels_won"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    print(f"Total players in raw data: {len(df)}")

    # Gate on appearances (reliable) rather than minutes (underestimated from events)
    df = df[df["appearances"] >= MIN_APPEARANCES].copy()
    print(f"After appearances >= {MIN_APPEARANCES} filter: {len(df)}")

    # Need at least one shot to compute shot-based metrics
    df = df[df["shots_total"] > 0].copy()
    print(f"After shots_total > 0 filter: {len(df)}")

    if len(df) < 2:
        sys.exit(f"Only {len(df)} players have shots — cannot z-score. Check raw data.")

    # 90s used only for fouls/90 denominator; guard against 0 minutes
    df["90s"] = df["minutes"].clip(lower=1) / 90

    df["SoT%"] = (df["shots_on"] / df["shots_total"]) * 100
    df["G/Sh"] = df["goals_total"] / df["shots_total"]

    df["Aerial_Won%"] = np.where(
        df["duels_total"] > 0,
        df["duels_won"] / df["duels_total"] * 100,
        np.nan,
    )

    df["fouls_p90"] = df["fouls_committed"] / df["90s"]

    # Aerial_Won% intentionally excluded: players with no aerial duel data
    # get a neutral z-score (0) rather than being dropped entirely.
    df = df.dropna(subset=["SoT%", "G/Sh", "fouls_p90"]).copy()
    print(f"After dropna on required metrics: {len(df)}")
    print(f"  - players with aerial data: {df['Aerial_Won%'].notna().sum()}")

    if len(df) < 2:
        sys.exit(f"Only {len(df)} players after dropna — cannot z-score. Check raw data.")

    df["z_sot_pct"]    = zscore(df["SoT%"])
    df["z_g_per_sh"]   = zscore(df["G/Sh"])
    df["z_aerial_won"] = zscore(df["Aerial_Won%"]).fillna(0)  # no aerial data → neutral
    df["z_fouls_p90"]  = zscore(df["fouls_p90"])

    df["CAI"] = (
        df["z_sot_pct"]
        + df["z_g_per_sh"]
        + df["z_aerial_won"]
        - df["z_fouls_p90"]
    )

    df = df.sort_values("CAI", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))

    out_path = os.path.join(DATA_DIR, "leaderboard.csv")
    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} players → {out_path}")
    print(
        df[["rank", "Player", "Squad", "CAI", "SoT%", "G/Sh", "Aerial_Won%", "fouls_p90"]]
        .head(10)
        .round(3)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()

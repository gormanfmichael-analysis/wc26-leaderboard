#!/usr/bin/env python3
"""
WC26 Leaderboard — Composite Index

Combines FBref's basic Shooting and Miscellaneous tables into a single
"Complete Attacker Index" (CAI):

    CAI = z(SoT%) + z(G/Sh) + z(Aerial Won%) - z(Fouls per 90)

Built WITHOUT xG, since Opta pulled that feed from FBref in Jan 2026
(see scrape_fbref.py docstring). Each component:

  SoT%        — shot accuracy: of shots taken, what % hit the target?
  G/Sh        — finishing: goals scored per shot taken
  Aerial Won% — physical presence: % of aerial duels won
  Fouls /90   — discipline: fewer fouls is better, so it's subtracted

All four are z-scored (standardised) before summing so no single stat
with a wider raw range dominates the index.

Run: python3 scripts/compute_leaderboard.py
"""
import os
import sys
import pandas as pd
import numpy as np

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MIN_90S = 2.0  # minimum "90s played" (FBref's minutes-played proxy) to qualify


def zscore(s):
    return (s - s.mean()) / s.std(ddof=0)


def main():
    shooting_path = os.path.join(DATA_DIR, "fbref_shooting_raw.csv")
    misc_path     = os.path.join(DATA_DIR, "fbref_misc_raw.csv")

    if not (os.path.exists(shooting_path) and os.path.exists(misc_path)):
        sys.exit(
            "Raw data not found. Run scripts/scrape_fbref.py first "
            "(or scripts/make_sample_data.py for a local test run)."
        )

    shooting = pd.read_csv(shooting_path)
    misc     = pd.read_csv(misc_path)

    # Column names come straight from FBref's headers
    keep_shoot = ["Player", "Squad", "90s", "Sh", "SoT", "SoT%", "G/Sh"]
    keep_misc  = ["Player", "Squad", "Fls", "Won", "Lost", "Won%"]

    shooting = shooting[[c for c in keep_shoot if c in shooting.columns]].copy()
    misc     = misc[[c for c in keep_misc if c in misc.columns]].copy()
    misc     = misc.rename(columns={"Won%": "Aerial_Won%", "Fls": "Fouls"})

    df = shooting.merge(misc, on=["Player", "Squad"], how="inner")

    # Coerce numerics (FBref CSVs sometimes carry stray header rows)
    for col in ["90s", "Sh", "SoT", "SoT%", "G/Sh", "Fouls", "Aerial_Won%"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["90s"])
    df = df[df["90s"] >= MIN_90S].copy()

    df["fouls_p90"] = df["Fouls"] / df["90s"]

    df["z_sot_pct"]    = zscore(df["SoT%"])
    df["z_g_per_sh"]   = zscore(df["G/Sh"])
    df["z_aerial_won"] = zscore(df["Aerial_Won%"])
    df["z_fouls_p90"]  = zscore(df["fouls_p90"])

    df["CAI"] = df["z_sot_pct"] + df["z_g_per_sh"] + df["z_aerial_won"] - df["z_fouls_p90"]

    df = df.sort_values("CAI", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))

    out_path = os.path.join(DATA_DIR, "leaderboard.csv")
    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} players to {out_path}")
    print(df[["rank", "Player", "Squad", "CAI", "SoT%", "G/Sh", "Aerial_Won%", "fouls_p90"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()

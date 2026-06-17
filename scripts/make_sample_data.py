#!/usr/bin/env python3
"""
Generates realistic sample data shaped like FBref's Shooting + Misc tables,
so compute_leaderboard.py and the dashboard can be tested without depending
on the live Selenium scrape (which only works in a real browser environment
like GitHub Actions, not this sandboxed session).

Run: python3 scripts/make_sample_data.py
"""
import os
import numpy as np
import pandas as pd

np.random.seed(7)
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

players = [
    ("Kylian Mbappe", "France"), ("Erling Haaland", "Norway"),
    ("Vinicius Junior", "Brazil"), ("Jude Bellingham", "England"),
    ("Lautaro Martinez", "Argentina"), ("Harry Kane", "England"),
    ("Lamine Yamal", "Spain"), ("Florian Wirtz", "Germany"),
    ("Bukayo Saka", "England"), ("Rodrygo", "Brazil"),
    ("Ousmane Dembele", "France"), ("Julian Alvarez", "Argentina"),
    ("Cole Palmer", "England"), ("Jamal Musiala", "Germany"),
    ("Pedri", "Spain"), ("Victor Osimhen", "Nigeria"),
    ("Christopher Nkunku", "France"), ("Federico Valverde", "Uruguay"),
    ("Dusan Vlahovic", "Serbia"), ("Khvicha Kvaratskhelia", "Georgia"),
]

n = len(players)
df_players = pd.DataFrame(players, columns=["Player", "Squad"])

# --- Shooting table ---
ninety_s   = np.round(np.random.uniform(2.0, 6.5, n), 1)
shots      = np.random.randint(8, 30, n)
sot_pct    = np.round(np.random.uniform(28, 62, n), 1)
sot        = np.round(shots * sot_pct / 100).astype(int)
goals      = np.random.binomial(shots, p=np.random.uniform(0.08, 0.22, n))
g_per_sh   = np.round(goals / shots, 3)

shooting = df_players.copy()
shooting["90s"]   = ninety_s
shooting["Sh"]     = shots
shooting["SoT"]    = sot
shooting["SoT%"]   = sot_pct
shooting["G/Sh"]   = g_per_sh
shooting.to_csv(os.path.join(DATA_DIR, "fbref_shooting_raw.csv"), index=False)

# --- Misc table ---
fouls       = np.random.randint(2, 18, n)
aerial_won  = np.random.randint(3, 25, n)
aerial_lost = np.random.randint(3, 25, n)
aerial_pct  = np.round(aerial_won / (aerial_won + aerial_lost) * 100, 1)

misc = df_players.copy()
misc["Fls"]  = fouls
misc["Won"]  = aerial_won
misc["Lost"] = aerial_lost
misc["Won%"] = aerial_pct
misc.to_csv(os.path.join(DATA_DIR, "fbref_misc_raw.csv"), index=False)

print(f"Sample data written for {n} players to {DATA_DIR}/")
print("This is SYNTHETIC data for pipeline testing only — not real World Cup stats.")

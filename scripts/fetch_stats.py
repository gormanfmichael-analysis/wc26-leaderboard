#!/usr/bin/env python3
"""
WC26 Player Stats Fetcher — nlbair/wc2026-events (GitHub)

Downloads all match event CSVs from https://github.com/nlbair/wc2026-events,
aggregates them into per-player stats, and saves data/api_football_raw.csv
for use by compute_leaderboard.py. No API key required.

Optionally set GITHUB_TOKEN to raise the GitHub API rate limit from
60 to 5,000 requests/hour. In GitHub Actions this is injected automatically.

    python scripts/fetch_stats.py
"""
import os
import sys
from io import StringIO

import pandas as pd
import requests

EVENTS_REPO  = "nlbair/wc2026-events"
EVENTS_PATH  = "data/raw"
API_URL      = f"https://api.github.com/repos/{EVENTS_REPO}/contents/{EVENTS_PATH}"
RAW_BASE_URL = f"https://raw.githubusercontent.com/{EVENTS_REPO}/main/{EVENTS_PATH}"

OUT_DIR  = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_FILE = os.path.join(OUT_DIR, "api_football_raw.csv")


def _headers(token: str | None) -> dict:
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def list_event_files(token: str | None) -> list[str]:
    resp = requests.get(API_URL, headers=_headers(token), timeout=30)
    resp.raise_for_status()
    return sorted(item["name"] for item in resp.json() if item["name"].endswith(".csv"))


def fetch_match_events(filename: str, token: str | None) -> pd.DataFrame:
    url = f"{RAW_BASE_URL}/{filename}"
    resp = requests.get(url, headers=_headers(token), timeout=30)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))


def normalize_bools(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Coerce boolean columns that may arrive as True/False strings or 0/1."""
    for col in cols:
        if col in df.columns:
            df[col] = df[col].map(
                lambda v: str(v).strip().lower() in ("true", "1", "yes")
            )
    return df


def aggregate_to_players(events: pd.DataFrame) -> pd.DataFrame:
    df = events.copy()
    df = normalize_bools(df, ["isShot", "isGoal"])

    # Drop non-player rows (FormationSet, Start, End have no meaningful player)
    df = df[df["player"].notna() & df["playerId"].notna()]

    # Minutes played: sum of (max_minute + 1) per player per match.
    # Approximates time on pitch; understimates for late subs, solid for starters.
    minutes = (
        df.groupby(["playerId", "match_id"])["minute"]
        .max()
        .add(1)
        .groupby(level="playerId")
        .sum()
        .rename("minutes")
    )

    appearances = (
        df.groupby("playerId")["match_id"]
        .nunique()
        .rename("appearances")
    )

    # Player name and team — mode per playerId handles minor spelling variants
    names = (
        df.groupby("playerId")["player"]
        .agg(lambda s: s.mode().iloc[0])
        .rename("Player")
    )
    teams = (
        df.groupby("playerId")["team"]
        .agg(lambda s: s.mode().iloc[0])
        .rename("Squad")
    )

    shots       = df[df["isShot"]]
    shots_total = shots.groupby("playerId").size().rename("shots_total")
    shots_on    = (
        shots[shots["isGoal"] | (shots["event"] == "SavedShot")]
        .groupby("playerId")
        .size()
        .rename("shots_on")
    )
    goals_total = df[df["isGoal"]].groupby("playerId").size().rename("goals_total")

    # Fouls committed: event=Foul, outcome=Unsuccessful (the player who fouled)
    fouls_committed = (
        df[(df["event"] == "Foul") & (df["outcome"] == "Unsuccessful")]
        .groupby("playerId")
        .size()
        .rename("fouls_committed")
    )

    # Aerial duels: event=Aerial — WhoScored records both sides of each contest
    aerials    = df[df["event"] == "Aerial"]
    duels_total = aerials.groupby("playerId").size().rename("duels_total")
    duels_won   = (
        aerials[aerials["outcome"] == "Successful"]
        .groupby("playerId")
        .size()
        .rename("duels_won")
    )

    stats = (
        pd.DataFrame({"player_id": df["playerId"].unique()})
        .set_index("player_id")
        .join(names)
        .join(teams)
        .join(minutes)
        .join(appearances)
        .join(shots_total)
        .join(shots_on)
        .join(goals_total)
        .join(fouls_committed)
        .join(duels_total)
        .join(duels_won)
    )

    int_cols = [
        "minutes", "appearances", "shots_total", "shots_on",
        "goals_total", "fouls_committed", "duels_total", "duels_won",
    ]
    stats[int_cols] = stats[int_cols].fillna(0).astype(int)

    return stats.reset_index()


def main():
    token = os.environ.get("GITHUB_TOKEN")
    os.makedirs(OUT_DIR, exist_ok=True)

    print("Listing match event files from nlbair/wc2026-events...")
    files = list_event_files(token)
    print(f"Found {len(files)} match files")

    all_events = []
    for i, fname in enumerate(files, 1):
        print(f"  [{i}/{len(files)}] {fname}")
        all_events.append(fetch_match_events(fname, token))

    events = pd.concat(all_events, ignore_index=True)
    print(f"Total events loaded: {len(events):,}")

    stats = aggregate_to_players(events)
    stats.to_csv(OUT_FILE, index=False)
    print(f"Saved {len(stats)} players → {OUT_FILE}")


if __name__ == "__main__":
    main()

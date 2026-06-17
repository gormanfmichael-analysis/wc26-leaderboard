#!/usr/bin/env python3
"""
WC26 Player Stats Fetcher — API-Football (RapidAPI)

Fetches player statistics for the FIFA World Cup 2026 and saves raw data
to data/api_football_raw.csv for use by compute_leaderboard.py.

API provider: API-Football v3 via RapidAPI
  - Host: api-football-v1.p.rapidapi.com
  - Endpoint: /v3/players
  - League: FIFA World Cup (league_id=1, season=2026)

To verify the correct league ID for WC2026:
    curl -H "x-rapidapi-key: YOUR_KEY" \
         "https://api-football-v1.p.rapidapi.com/v3/leagues?name=FIFA%20World%20Cup&season=2026"

Set env var before running:
    export RAPIDAPI_KEY=your_key_here
    python scripts/fetch_stats.py
"""
import os
import sys
import time

import pandas as pd
import requests

API_HOST = "api-football-v1.p.rapidapi.com"
BASE_URL = f"https://{API_HOST}/v3"
LEAGUE_ID = 1     # FIFA World Cup in API-Football
SEASON = 2026

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_FILE = os.path.join(OUT_DIR, "api_football_raw.csv")


def fetch_all_players(api_key: str) -> list:
    headers = {
        "x-rapidapi-host": API_HOST,
        "x-rapidapi-key": api_key,
    }
    players = []
    page = 1
    while True:
        resp = requests.get(
            f"{BASE_URL}/players",
            headers=headers,
            params={"league": LEAGUE_ID, "season": SEASON, "page": page},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        batch = data.get("response", [])
        players.extend(batch)

        paging = data.get("paging", {})
        total_pages = paging.get("total", 1)
        print(f"  Page {page}/{total_pages} — {len(batch)} players fetched")

        if page >= total_pages:
            break
        page += 1
        time.sleep(0.4)  # stay within free-tier rate limits (100 req/day)

    return players


def flatten_players(players: list) -> pd.DataFrame:
    """Flatten nested API-Football player response into a flat DataFrame.

    Note on duels: API-Football's duels.total/won covers all physical contests
    (ground challenges + aerial duels combined), not aerial duels in isolation.
    compute_leaderboard.py uses this as the duel-contest proxy and outputs it
    as Aerial_Won% to keep leaderboard.csv schema stable.
    """
    rows = []
    for item in players:
        p = item.get("player", {})
        for stat in item.get("statistics", []):
            games = stat.get("games", {})
            shots = stat.get("shots", {})
            goals = stat.get("goals", {})
            fouls = stat.get("fouls", {})
            duels = stat.get("duels", {})

            rows.append({
                "player_id":       p.get("id"),
                "Player":          p.get("name"),
                "Squad":           (stat.get("team") or {}).get("name"),
                "minutes":         games.get("minutes") or 0,
                "appearances":     games.get("appearences") or 0,  # API has typo
                "shots_total":     shots.get("total") or 0,
                "shots_on":        shots.get("on") or 0,
                "goals_total":     goals.get("total") or 0,
                "fouls_committed": fouls.get("committed") or 0,
                "duels_total":     duels.get("total") or 0,
                "duels_won":       duels.get("won") or 0,
            })

    return pd.DataFrame(rows)


def main():
    api_key = os.environ.get("RAPIDAPI_KEY")
    if not api_key:
        sys.exit("Error: RAPIDAPI_KEY environment variable is not set.")

    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"Fetching WC2026 player stats (league={LEAGUE_ID}, season={SEASON})...")
    players = fetch_all_players(api_key)
    print(f"Total player records fetched: {len(players)}")

    df = flatten_players(players)
    df.to_csv(OUT_FILE, index=False)
    print(f"Saved {len(df)} rows → {OUT_FILE}")


if __name__ == "__main__":
    main()

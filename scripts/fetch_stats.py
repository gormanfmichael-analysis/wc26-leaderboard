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
from io import StringIO

import pandas as pd
import requests

EVENTS_REPO  = "nlbair/wc2026-events"
EVENTS_PATH  = "data/raw"
API_URL      = f"https://api.github.com/repos/{EVENTS_REPO}/contents/{EVENTS_PATH}"
RAW_BASE_URL = f"https://raw.githubusercontent.com/{EVENTS_REPO}/main/{EVENTS_PATH}"

OUT_DIR  = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_FILE = os.path.join(OUT_DIR, "api_football_raw.csv")

# Event names that identify a shot (fallback when isShot flag is unreliable)
SHOT_EVENTS      = {"MissedShots", "SavedShot", "BlockedShot", "ShotOnPost",
                    "Goal", "AttemptSaved", "OwnGoal"}
ON_TARGET_EVENTS = {"SavedShot", "Goal", "AttemptSaved"}


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
    df = pd.read_csv(StringIO(resp.text))
    # Tag each row with its source filename — reliable match identifier
    # regardless of whether match_id is populated in the data
    df["_match_file"] = filename
    return df


def coerce_bool(series: pd.Series) -> pd.Series:
    """Convert a bool-ish column to bool, handling all pandas storage types.

    pandas reads a column as float64 when it mixes integers with NaN, so
    True ends up as 1.0. str(1.0) == "1.0" which would not match "1" — this
    handles that case explicitly before falling back to string comparison.
    """
    def _cast(v) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, float):
            return not pd.isna(v) and bool(v)
        if isinstance(v, int):
            return bool(v)
        return str(v).strip().lower() in ("true", "1", "yes")
    return series.map(_cast)


def aggregate_to_players(events: pd.DataFrame) -> pd.DataFrame:
    df = events.copy()

    # Normalize boolean flags
    for col in ("isShot", "isGoal"):
        if col in df.columns:
            df[col] = coerce_bool(df[col])
        else:
            df[col] = False

    # Drop events with no player name (FormationSet, Start, End, etc.)
    df = df[df["player"].notna() & (df["player"] != "")].copy()

    # Use "Name|Team" as the groupby key. This avoids depending on playerId
    # or match_id, which are WhoScored numeric IDs that may be NaN in the CSV.
    df["_key"] = df["player"].str.strip() + "|" + df["team"].fillna("").str.strip()

    # Minutes played: sum of (last_event_minute + 1) per player per match file.
    # Approximates time on pitch; floored at 1 to avoid division-by-zero in fouls/90.
    minutes = (
        df.groupby(["_key", "_match_file"])["minute"]
        .max()
        .add(1)
        .groupby(level="_key")
        .sum()
        .rename("minutes")
    )

    appearances = (
        df.groupby("_key")["_match_file"]
        .nunique()
        .rename("appearances")
    )

    names = (
        df.groupby("_key")["player"]
        .agg(lambda s: s.mode().iloc[0])
        .rename("Player")
    )
    teams = (
        df.groupby("_key")["team"]
        .agg(lambda s: s.mode().iloc[0])
        .rename("Squad")
    )

    # Shots: accept either isShot flag OR known shot event names
    is_shot = df["isShot"] | df["event"].isin(SHOT_EVENTS)
    shots_df = df[is_shot]
    shots_total = shots_df.groupby("_key").size().rename("shots_total")

    # Shots on target: accepted by keeper or scored
    is_on_target = is_shot & (df["isGoal"] | df["event"].isin(ON_TARGET_EVENTS))
    shots_on = df[is_on_target].groupby("_key").size().rename("shots_on")

    # Goals: isGoal flag OR event name "Goal"
    goals_total = (
        df[df["isGoal"] | (df["event"] == "Goal")]
        .groupby("_key").size().rename("goals_total")
    )

    # Fouls committed: Foul event where the player is the one who fouled
    fouls_committed = (
        df[(df["event"] == "Foul") & (df["outcome"] == "Unsuccessful")]
        .groupby("_key").size().rename("fouls_committed")
    )

    # Aerial duels: WhoScored records both sides of each contest as separate rows
    aerials = df[df["event"] == "Aerial"]
    duels_total = aerials.groupby("_key").size().rename("duels_total")
    duels_won = (
        aerials[aerials["outcome"] == "Successful"]
        .groupby("_key").size().rename("duels_won")
    )

    stats = (
        pd.DataFrame({"player_id": df["_key"].unique()})
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

    # Diagnostic: show what event types were found before aggregating
    if "event" in events.columns:
        print(f"Unique event types in data: {sorted(events['event'].dropna().unique().tolist())}")
    if "isShot" in events.columns:
        print(f"isShot value counts: {events['isShot'].value_counts().to_dict()}")

    stats = aggregate_to_players(events)
    print(f"Total players found: {len(stats)}")
    print(f"Players with >= 1 appearance: {(stats['appearances'] >= 1).sum()}")
    print(f"Players with shots (shots_total > 0): {(stats['shots_total'] > 0).sum()}")
    print(f"Players with aerial data (duels_total > 0): {(stats['duels_total'] > 0).sum()}")

    stats.to_csv(OUT_FILE, index=False)
    print(f"Saved {len(stats)} players → {OUT_FILE}")


if __name__ == "__main__":
    main()

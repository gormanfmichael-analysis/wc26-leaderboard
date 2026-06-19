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

# Shot detection: isShot flag + event name fallback
SHOT_EVENTS      = {"MissedShots", "SavedShot", "BlockedShot", "ShotOnPost",
                    "Goal", "AttemptSaved", "OwnGoal"}
ON_TARGET_EVENTS = {"SavedShot", "Goal", "AttemptSaved"}

# Attacking third threshold: Opta x-coordinate is 0 (own goal) → 100 (opp goal),
# normalised per team so x >= 67 is always the player's own attacking third.
AT_X_THRESHOLD = 67.0


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
    df["_match_file"] = filename
    return df


def coerce_bool(series: pd.Series) -> pd.Series:
    """Convert bool-ish columns to bool, handling float64 (1.0), int, string."""
    def _cast(v) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, float):
            return not pd.isna(v) and bool(v)
        if isinstance(v, int):
            return bool(v)
        return str(v).strip().lower() in ("true", "1", "yes")
    return series.map(_cast)


def qual_flag(series: pd.Series) -> pd.Series:
    """Return True where a WhoScored qualifier column is set (non-null, truthy)."""
    numeric = pd.to_numeric(series, errors="coerce")
    return series.notna() & (numeric.fillna(0) != 0)


def aggregate_to_players(events: pd.DataFrame) -> pd.DataFrame:
    df = events.copy()

    for col in ("isShot", "isGoal"):
        df[col] = coerce_bool(df[col]) if col in df.columns else False

    df = df[df["player"].notna() & (df["player"] != "")].copy()
    df["_key"] = df["player"].str.strip() + "|" + df["team"].fillna("").str.strip()

    x_num = pd.to_numeric(df.get("x"), errors="coerce")
    in_at  = x_num >= AT_X_THRESHOLD   # attacking third mask

    # ── Time on pitch ────────────────────────────────────────────────────────
    minutes = (
        df.groupby(["_key", "_match_file"])["minute"]
        .max().add(1)
        .groupby(level="_key").sum()
        .rename("minutes")
    )
    appearances = df.groupby("_key")["_match_file"].nunique().rename("appearances")

    # ── Identity ─────────────────────────────────────────────────────────────
    names = df.groupby("_key")["player"].agg(lambda s: s.mode().iloc[0]).rename("Player")
    teams = df.groupby("_key")["team"].agg(lambda s: s.mode().iloc[0]).rename("Squad")

    # ── Shots & goals ────────────────────────────────────────────────────────
    is_shot      = df["isShot"] | df["event"].isin(SHOT_EVENTS)
    is_on_target = is_shot & (df["isGoal"] | df["event"].isin(ON_TARGET_EVENTS))

    shots_total  = df[is_shot].groupby("_key").size().rename("shots_total")
    shots_on     = df[is_on_target].groupby("_key").size().rename("shots_on")
    goals_total  = df[df["isGoal"] | (df["event"] == "Goal")].groupby("_key").size().rename("goals_total")

    # ── Discipline ───────────────────────────────────────────────────────────
    fouls_committed = (
        df[(df["event"] == "Foul") & (df["outcome"] == "Unsuccessful")]
        .groupby("_key").size().rename("fouls_committed")
    )

    # ── Aerial duels ─────────────────────────────────────────────────────────
    aerials     = df[df["event"] == "Aerial"]
    duels_total = aerials.groupby("_key").size().rename("duels_total")
    duels_won   = aerials[aerials["outcome"] == "Successful"].groupby("_key").size().rename("duels_won")

    # ── Passing ──────────────────────────────────────────────────────────────
    passes       = df[df["event"] == "Pass"]
    pass_total   = passes.groupby("_key").size().rename("pass_total")
    pass_accurate = (
        passes[passes["outcome"] == "Successful"]
        .groupby("_key").size().rename("pass_accurate")
    )

    # Key passes: qual_KeyPass qualifier present and truthy on a Pass event.
    # Note: goal assists typically carry qual_IntentionalGoalAssist instead,
    # so key_passes counts shot-creating passes excluding direct goal assists.
    if "qual_KeyPass" in df.columns:
        key_passes = (
            df[(df["event"] == "Pass") & qual_flag(df["qual_KeyPass"])]
            .groupby("_key").size().rename("key_passes")
        )
    else:
        key_passes = pd.Series(dtype=int, name="key_passes")

    # ── Dribbles (TakeOns) ───────────────────────────────────────────────────
    takeons       = df[df["event"] == "TakeOn"]
    takeons_total = takeons.groupby("_key").size().rename("takeons_total")
    takeons_won   = (
        takeons[takeons["outcome"] == "Successful"]
        .groupby("_key").size().rename("takeons_won")
    )

    # ── Ball recoveries ──────────────────────────────────────────────────────
    ball_recoveries = df[df["event"] == "BallRecovery"].groupby("_key").size().rename("ball_recoveries")

    # ── Attacking third defensive actions ────────────────────────────────────
    # Combined: ball recoveries + tackles won + interceptions, all in x >= 67.
    at_rec   = df[(df["event"] == "BallRecovery") & in_at].groupby("_key").size()
    at_tack  = df[(df["event"] == "Tackle") & (df["outcome"] == "Successful") & in_at].groupby("_key").size()
    at_inter = df[(df["event"] == "Interception") & in_at].groupby("_key").size()
    at_actions = (
        at_rec.add(at_tack, fill_value=0).add(at_inter, fill_value=0)
        .rename("at_actions")
    )

    # ── Assemble ─────────────────────────────────────────────────────────────
    stats = (
        pd.DataFrame({"player_id": df["_key"].unique()})
        .set_index("player_id")
        .join(names).join(teams).join(minutes).join(appearances)
        .join(shots_total).join(shots_on).join(goals_total)
        .join(fouls_committed)
        .join(duels_total).join(duels_won)
        .join(pass_total).join(pass_accurate).join(key_passes)
        .join(takeons_total).join(takeons_won)
        .join(ball_recoveries)
        .join(at_actions)
    )

    int_cols = [
        "minutes", "appearances",
        "shots_total", "shots_on", "goals_total", "fouls_committed",
        "duels_total", "duels_won",
        "pass_total", "pass_accurate", "key_passes",
        "takeons_total", "takeons_won",
        "ball_recoveries", "at_actions",
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
    if "event" in events.columns:
        print(f"Event types found: {sorted(events['event'].dropna().unique().tolist())}")

    stats = aggregate_to_players(events)
    print(f"Players found: {len(stats)}")
    print(f"  with >= 1 appearance:  {(stats['appearances'] >= 1).sum()}")
    print(f"  with shots:            {(stats['shots_total'] > 0).sum()}")
    print(f"  with passes:           {(stats['pass_total'] > 0).sum()}")
    print(f"  with key passes:       {(stats['key_passes'] > 0).sum()}")
    print(f"  with dribble attempts: {(stats['takeons_total'] > 0).sum()}")
    print(f"  with AT actions:       {(stats['at_actions'] > 0).sum()}")

    stats.to_csv(OUT_FILE, index=False)
    print(f"Saved {len(stats)} players → {OUT_FILE}")


if __name__ == "__main__":
    main()

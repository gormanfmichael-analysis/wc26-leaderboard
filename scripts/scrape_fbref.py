#!/usr/bin/env python3
"""
FBref World Cup 2026 Scraper — Shooting + Miscellaneous Stats

FBref sits behind Cloudflare bot protection that defeats requests,
cloudscraper, and curl_cffi TLS impersonation (all tested and confirmed
blocked). The only reliable bypass is a real browser — Cloudflare's JS
challenge requires actual JS execution, which only a genuine browser
engine provides. This script uses Selenium + headless Chrome.

NOTE: Since the January 2026 Opta/Stats Perform dispute, FBref no longer
serves xG, progressive passes, or shot-creating actions (Opta pulled that
feed). This scraper only targets stats Sports Reference explicitly kept:
basic Shooting (Goals, Shots, SoT, SoT%, G/Sh) and Miscellaneous
(Fouls, Cards, Aerial duels, Recoveries).

Rate limit: Sports Reference's own policy allows up to 10 requests/minute
(https://www.sports-reference.com/bot-traffic.html). This script makes 2
requests per run (one per stat page) — comfortably under that limit. Do
not increase scrape frequency without re-checking their current policy.

Run locally:  python3 scripts/scrape_fbref.py
Run in CI:    see .github/workflows/update.yml (headless Chrome via
              browser-actions/setup-chrome)
"""
import os
import sys
import time

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

COMP_SLUG = "World-Cup"
COMP_ID = 1  # FBref's internal id for the World Cup competition
BASE = f"https://fbref.com/en/comps/{COMP_ID}"

PAGES = {
    "shooting": f"{BASE}/shooting/{COMP_SLUG}-Stats",
    "misc":     f"{BASE}/misc/{COMP_SLUG}-Stats",
}

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
    # Selenium 4.6+ resolves the driver automatically (Selenium Manager) —
    # no webdriver-manager dependency needed.
    return webdriver.Chrome(options=opts)


def fetch_table(driver, url, table_keyword, wait_seconds=25):
    """Load a FBref stats page and return the player stats table as a DataFrame.

    FBref renders most tables server-side but wraps some in HTML comments
    to defeat naive scrapers — using a real browser sidesteps that since
    the DOM is already parsed. We search all <table> elements for one whose
    id contains `table_keyword` (e.g. 'shooting', 'misc').
    """
    driver.get(url)
    WebDriverWait(driver, wait_seconds).until(
        EC.presence_of_element_located((By.TAG_NAME, "table"))
    )
    # Let Cloudflare's challenge fully resolve and the table finish rendering
    time.sleep(3)

    tables = driver.find_elements(By.TAG_NAME, "table")
    target = None
    for t in tables:
        tid = t.get_attribute("id") or ""
        if table_keyword in tid:
            target = t
            break
    if target is None:
        raise RuntimeError(f"No table with id containing '{table_keyword}' found at {url}")

    html = target.get_attribute("outerHTML")
    df = pd.read_html(html)[0]

    # FBref player tables have a multi-row header — flatten it
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[-1] if "Unnamed" not in str(c[0]) else c[-1] for c in df.columns]

    # Drop FBref's repeated mid-table header rows
    if "Player" in df.columns:
        df = df[df["Player"].notna() & (df["Player"] != "Player")]

    return df.reset_index(drop=True)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    driver = make_driver()
    try:
        for name, url in PAGES.items():
            print(f"Fetching {name}: {url}")
            df = fetch_table(driver, url, table_keyword=name)
            out_path = os.path.join(OUT_DIR, f"fbref_{name}_raw.csv")
            df.to_csv(out_path, index=False)
            print(f"  Saved {len(df)} rows -> {out_path}")
            time.sleep(7)  # stay well under the 10 req/min limit
    finally:
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())

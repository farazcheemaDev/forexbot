"""ForexFactory's economic calendar, month by month, cached - the calendar a retail news trader watches.

Each event carries its release time to the second (`dateline`, epoch UTC), FF's impact rating, actual /
forecast / previous, and FF's own notes - including "Release time comes as a surprise from source" and
"added to the calendar after its release time" (unscheduled speeches, e.g. "President Trump Speaks").
Read from the page's embedded state (window.calendarComponentStates[1].days), which is plain JSON.

    python -m backtest.ff_calendar            # fetch dec.2025..sep.2026 into the cache
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "strategy_analysis" / "data" / "ff_calendar.csv"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
     "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-US,en;q=0.9"}
MONTHS = ["dec.2025", "jan.2026", "feb.2026", "mar.2026", "apr.2026", "may.2026", "jun.2026", "jul.2026",
          "aug.2026", "sep.2026"]


def fetch_month(m):
    t = urllib.request.urlopen(urllib.request.Request(f"https://www.forexfactory.com/calendar?month={m}", headers=H),
                               timeout=60).read().decode("utf-8", "replace")
    i = t.find("window.calendarComponentStates[1]")
    j = t.find("days:", i) + len("days:")
    days, _ = json.JSONDecoder().raw_decode(t[j:].lstrip())
    rows = []
    for d in days:
        for e in d.get("events", []):
            rows.append(dict(utc=pd.Timestamp(e["dateline"], unit="s"), currency=e["currency"], impact=e["impactName"],
                             name=e["name"], actual=e["actual"], forecast=e["forecast"], previous=e["previous"],
                             abw=e["actualBetterWorse"], time_label=e["timeLabel"], notice=e["notice"]))
    return rows


def load(refresh=False):
    if CACHE.exists() and not refresh:
        return pd.read_csv(CACHE, parse_dates=["utc"], keep_default_na=False)
    rows = []
    for m in MONTHS:
        rows += fetch_month(m)
        time.sleep(3)
    df = pd.DataFrame(rows).drop_duplicates().sort_values("utc", kind="stable").reset_index(drop=True)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CACHE, index=False)
    return df


if __name__ == "__main__":
    f = load(refresh=True)
    print(len(f), "events", f.utc.min(), "->", f.utc.max())
    print(f.groupby(["currency", "impact"]).size().unstack(fill_value=0).loc[["USD", "EUR", "CNY", "JPY"]])

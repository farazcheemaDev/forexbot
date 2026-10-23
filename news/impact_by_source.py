"""SENTIMENT ENGINE: the impact table SPLIT BY EXCHANGE - whose notices move coins? (2026-10-23)

THE USER (2026-10-23): "a better sentiment tool - add all the good stuff". news/impact.py pooled every exchange's
notices by event type; the live news book (news_books.py) acts on Binance's alone. This splits the same measurement
(news/impact.observe: the coin's EXCESS move vs BTC after the first full hour, against its own normal drift) by the
channel that posted the notice - Binance, Bybit, OKX, Bitget and the BWEnews wire - for the coin-event types, so a book
can be told which sources to act on.
REPORTED per source x type with >= 15 events: n, the mean excess at 24h / 72h / 7d (bp), t, tune / holdout at 72h and 7d,
and a USABLE flag (same rule as impact.py: |mean| >= 24bp, t >= 2, the same sign on both halves).

REGISTERED BEFORE THE RUN (2026-10-23)
  S1 list_spot carries its -300bp 7-day drift on at least two exchanges, not one (the pooled -310bp is not one venue).
  S2 delistings stay no signal on every exchange.
  S3 unlock notices (Bitget / Bybit, ~400) are small everywhere: |7d| < 100bp.
  S4 at most 4 source x type cells are USABLE beyond what impact.py already had.

RESULT (2026-10-23, logs/news_impact_by_source.txt; 1,446 notices with a coin and a perp bar) - other exchanges add little.
  Binance adds_products stays the strongest (-721bp at 72h t -3.3, -952bp at 7d, both halves) - already the news book.
  New SPOT listings drift down over 7 days on every source (BWEnews -539 t -2.5 usable; Bitget -348, Bybit -410, OKX -456,
  each t > -2 alone) - the pooled -310bp (impact.py) is real and spread across venues, but news_book.py already found it
  only covers the cost of thin coins as a trade (S1 WRONG on its t rule, right on the direction). BWEnews launchpool
  -1,530bp 7d (t -2.1, n 30). Delistings no signal anywhere (S2 RIGHT); unlocks -40..-170bp, small (S3 WRONG by BWEnews'
  -170 on 28); 4 usable cells (S4 RIGHT).

    python -m news.impact_by_source
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from news.impact import EV, observe  # noqa: E402

LOG = ROOT / "logs" / "news_impact_by_source.txt"
SOURCES = ["binance_announcements", "Bybit_Announcements", "OKXAnnouncements", "Bitget_Announcements", "BWEnews"]
TYPES = ["adds_products", "monitoring_tag", "seed_tag", "launchpool", "list_spot", "list_futures", "new_pairs", "delist",
         "delist_pairs", "delist_futures", "unlock"]
HZ = ("24h", "72h", "7d")


def tstat(v):
    return v.mean() / (v.std(ddof=1) / np.sqrt(len(v))) if len(v) > 2 and v.std(ddof=1) > 0 else 0.0


def main():
    E = pd.read_parquet(EV)
    E = E[E.channel.isin(SOURCES) & E.etype.isin(TYPES)]
    O = observe(E)
    ev = O.groupby(["eid", "etype", "channel", "t"])[["already"] + list(HZ)].mean().reset_index().sort_values("t", kind="stable")
    cut = ev.t.iloc[int(len(ev) * 0.6)]
    L = [f"news/impact_by_source.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(ev):,} exchange notices with a coin and a "
         f"perp bar; excess move vs BTC over the coin's own drift (bp); tune before {cut:%Y-%m-%d}", "",
         f"   {'source':<22}{'type':<15}{'n':>5}{'24h':>8}{'72h':>8}{'t':>6}{'7d':>8}{'t':>6}{'72h tune/hold':>16}{'7d tune/hold':>16}"]
    usable, cells = [], {}
    for (src, et), g in ev.groupby(["channel", "etype"]):
        if len(g) < 15:
            continue
        row = {}
        for k in HZ:
            v = g[k].dropna() * 1e4
            tu, ho = g[g.t < cut][k].dropna() * 1e4, g[g.t >= cut][k].dropna() * 1e4
            row[k] = (v.mean(), tstat(v), tu.mean() if len(tu) else np.nan, ho.mean() if len(ho) else np.nan)
            if abs(v.mean()) >= 24 and abs(tstat(v)) >= 2 and len(tu) and len(ho) and np.sign(tu.mean()) == np.sign(ho.mean()) == np.sign(v.mean()):
                usable.append((src, et, k, round(v.mean()), round(tstat(v), 1)))
        cells[(src, et)] = row
        L.append(f"   {src[:21]:<22}{et:<15}{len(g):>5}{row['24h'][0]:>+8.0f}{row['72h'][0]:>+8.0f}{row['72h'][1]:>+6.1f}"
                 f"{row['7d'][0]:>+8.0f}{row['7d'][1]:>+6.1f}{row['72h'][2]:>+8.0f}/{row['72h'][3]:<+7.0f}"
                 f"{row['7d'][2]:>+8.0f}/{row['7d'][3]:<+7.0f}")
    L += ["", "USABLE (|mean| >= 24bp, t >= 2, same sign on both halves):"] + [f"   {u}" for u in usable]
    ls = [s for (s, et), r in cells.items() if et == "list_spot" and r["7d"][0] <= -150 and r["7d"][1] <= -2]
    dl = [(s, et) for (s, et) in cells if et.startswith("delist") and (s, et, "7d") in [(u[0], u[1], u[2]) for u in usable]]
    un = [r["7d"][0] for (s, et), r in cells.items() if et == "unlock"]
    L += ["", "REGISTERED PREDICTIONS",
          f"  S1 list_spot <= -150bp at 7d with t <= -2 on >= 2 exchanges: {ls} -> {'RIGHT' if len(ls) >= 2 else 'WRONG'}",
          f"  S2 no delisting cell usable at 7d: {dl} -> {'RIGHT' if not dl else 'WRONG'}",
          f"  S3 unlock |7d| < 100bp everywhere: {[round(x) for x in un]} -> {'RIGHT' if all(abs(x) < 100 for x in un) else 'WRONG'}",
          f"  S4 <= 4 usable cells: {len(usable)} -> {'RIGHT' if len(usable) <= 4 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

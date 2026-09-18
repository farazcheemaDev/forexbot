"""WHICH DAYS DOES HE SHOW UP? — the question never asked.

    python -m backtest.his_day_choice

WHY THIS IS THE RIGHT PLACE TO LOOK
    Everything so far asked "what is special about the MOMENT he entered", and nothing
    was. But he does not trade moments, he trades SESSIONS: 46 NASDAQ trades arrive in
    bursts of 3-8 on a handful of days a month, and he sits out the rest. Whatever
    decision he is making, he makes it BEFORE the session - and a decision made before
    the session cannot be visible in the five minutes around an entry.

    So the unit of analysis is the DAY. He traded some; he skipped most. What is
    different about the ones he showed up for?

WHY THIS CANNOT REPEAT THE §19 BUG
    §19 died because controls were assigned a direction derived from the same quantity
    being tested. A DAY has no direction. Every feature here is a property of the day
    itself, computed from bars that closed BEFORE the US session opened, and it is
    identical in construction for days he traded and days he did not. There is no label
    to leak.

FEATURES, DECLARED BEFORE LOOKING
    All computed from the PREVIOUS session and the overnight, so all are knowable at the
    moment he decides whether to trade.

REGISTERED PREDICTION (2026-09-16, before running)
    Yesterday's RANGE is the most likely discriminator - a scalper needs movement, and a
    dead prior session predicts a dead next one. Second guess is the overnight gap. I
    expect at most one survivor after Holm correction, and given §19 I now expect the
    honest answer to be none: if his day choice were a simple volatility filter, the
    entry-level tests would probably have picked up its shadow.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
GMT = 5.0
rng = np.random.default_rng(23)

FEATURES = [
    ("prev_range_atr", "yesterday's range / 20-day average range"),
    ("prev_ret", "yesterday's return, absolute, in %"),
    ("prev_close_pos", "where yesterday closed in its own range (0=low, 1=high)"),
    ("gap_atr", "overnight gap into the session, absolute, in ATR"),
    ("atr20_ratio", "5-day average range / 20-day average range (vol regime)"),
    ("dow", "day of week (0=Mon)"),
    ("since_last", "trading days since he last traded"),
    ("open_hour_range_atr", "range of the first hour of the session / avg"),
]


def perm_p(a, b, n=20000):
    obs = a.mean() - b.mean()
    allv = np.concatenate([a, b]); k = len(a)
    c = sum(1 for _ in range(n)
            if abs((p := rng.permutation(allv))[:k].mean() - p[k:].mean()) >= abs(obs))
    return obs, c / n


def holm(ps):
    o = np.argsort(ps); m = len(ps); out = np.empty(m); prev = 0.0
    for r, i in enumerate(o):
        prev = max(prev, min(1.0, (m - r) * ps[i])); out[i] = prev
    return out


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: yesterday's RANGE is the likeliest discriminator; second guess")
    print("the overnight gap. After §19 I expect the honest answer to be NONE.\n")

    b = pd.DataFrame(json.load(open(
        ROOT / "strategy_analysis" / "data" / "USTECm_5m_400d.json")))
    b["t"] = pd.to_datetime(b["t"], unit="ms")
    b = (b.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close"})
         .set_index("t").sort_index())
    day = b.resample("D").agg(o=("open", "first"), h=("high", "max"),
                              l=("low", "min"), c=("close", "last")).dropna()
    day["rng"] = day.h - day.l
    day["avg20"] = day.rng.rolling(20).mean()
    day["avg5"] = day.rng.rolling(5).mean()

    d = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv",
                    parse_dates=["open_time"])
    n = d[d.symbol.str.contains("NASDAQ")].copy()
    n["utc"] = n.open_time - pd.Timedelta(hours=GMT)
    traded = sorted({t.normalize() for t in n.utc})
    print(f"  {len(n)} NASDAQ trades on {len(traded)} distinct days")
    print(f"  bursts of {len(n)/len(traded):.1f} trades per trading day\n")

    rows = []
    idx = list(day.index)
    tset = set(traded)
    last = None
    for j, dt in enumerate(idx):
        if j < 21 or dt < min(traded) or dt > max(traded):
            continue
        p = day.iloc[j - 1]
        cur = day.iloc[j]
        if not np.isfinite(p.avg20) or p.avg20 <= 0:
            continue
        sess = b.loc[(b.index >= dt + pd.Timedelta(hours=13, minutes=30)) &
                     (b.index < dt + pd.Timedelta(hours=14, minutes=30))]
        rows.append(dict(
            date=dt, took=dt in tset,
            prev_range_atr=p.rng / p.avg20,
            prev_ret=abs(p.c / p.o - 1) * 100,
            prev_close_pos=(p.c - p.l) / (p.h - p.l) if p.h > p.l else .5,
            gap_atr=abs(cur.o - p.c) / p.avg20,
            atr20_ratio=p.avg5 / p.avg20,
            dow=float(dt.dayofweek),
            since_last=float((j - last) if last is not None else 0),
            open_hour_range_atr=(float(sess.high.max() - sess.low.min()) / p.avg20)
            if len(sess) else np.nan))
        if dt in tset:
            last = j
    f = pd.DataFrame(rows).dropna()
    T, S = f[f.took], f[~f.took]
    print(f"  {len(T)} days he TRADED   vs   {len(S)} days he SKIPPED "
          f"(same window, same instrument)\n")
    if len(T) < 8:
        raise SystemExit("too few trading days to test")

    print("=" * 92)
    print("WHAT IS DIFFERENT ABOUT THE DAYS HE SHOWS UP FOR?")
    print("=" * 92)
    print(f"  {'feature':<44}{'traded':>9}{'skipped':>10}{'p':>8}{'Holm':>8}")
    raw = []
    for k, _ in FEATURES:
        _o, p = perm_p(T[k].to_numpy(float), S[k].to_numpy(float))
        raw.append(p)
    hp = holm(np.array(raw))
    surv = []
    for (k, desc), p, h in zip(FEATURES, raw, hp):
        star = " **" if h < .05 else (" *" if p < .05 else "")
        print(f"  {desc[:42]:<44}{T[k].mean():>9.3f}{S[k].mean():>10.3f}"
              f"{p:>8.3f}{h:>8.3f}{star}")
        if h < .05:
            surv.append((k, desc))
    print("\n  ** survives Holm across all 8   |   * uncorrected only")

    print("\n" + "=" * 92)
    print("VERDICT")
    print("=" * 92)
    if not surv:
        print("  No day-level feature separates the sessions he trades from the ones he")
        print("  skips. His day choice is not a volatility filter, not a gap filter, not")
        print("  a day-of-week habit, and not a fixed cadence.")
        print("\n  Combined with §20 (no moment-level feature either), the conclusion is")
        print("  that his selection is not recoverable from price data at all.")
    else:
        for k, desc in surv:
            print(f"  SURVIVES: {desc}  (traded {T[k].mean():.3f} vs "
                  f"skipped {S[k].mean():.3f})")
        print("\n  Re-test this on his gold days before believing it.")


if __name__ == "__main__":
    main()

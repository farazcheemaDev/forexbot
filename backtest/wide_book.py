"""DOES BREADTH STILL SCALE? - the deployed engine on a survivorship-free PIT universe.

WHY THIS IS THE BEST REMAINING LEVER
    cheap_wide.py measured that RETURN scales with BREADTH (3 coins +1.9%/mo, 9 coins
    +10.7%/mo) and then picked TWELVE coins - chosen for minimum-order affordability at $221,
    not because twelve is optimal. corr_alloc.py measured those twelve behave like ~1.5
    independent bets. The slots bind constantly (513 declines against 47 entries live).

    Since then perp_fetch.py downloaded every USDT-M perp that ever existed - 855 symbols,
    339 of them DEAD. That makes the honest version of "trade more coins" testable for the
    first time: with the SAME 12 slots, do signals drawn from 30/60/100 coins beat signals
    drawn from 12? More candidates means the slots go to whatever fires, from a far less
    concentrated pool.

HONEST CONSTRUCTION
    * Universe is POINT IN TIME: each month, the top N perps by the PRIOR month's quote
      volume, listed at least 30 days. Dead coins are in it while they lived, so nothing
      knows in advance which survive.
    * A trade only counts if its coin was eligible at ENTRY.
    * The BASELINE is the deployed 12 coins run through the SAME code and the SAME perp
      price data, so the comparison is not contaminated by a data-source change.
    * Deployed engine unchanged: bb_break(30,1.5), 2xATR stop, long 20xATR trail with the
      5-unit pyramid every 2R, short 5xATR one unit, breakeven at 3R, 12bp, 1000h BTC gate,
      compounded by close date, 3x hindsight haircut.
    * Seed-averaged over 5 orderings of simultaneous entries (that alone swings 3-5%/mo).

    WHAT THIS DOES NOT ANSWER: whether $221 can fund a wide book. Most of these coins are
    not on MEXC's cheap-minimum list, so a positive result here is a strategy result and a
    CAPITAL question, not a drop-in change.

    python -m backtest.wide_book
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bull_boost import evaluate, regimes  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "perps"
RULES = ["1h", "4h", "12h"]
SEEDS = (0, 1, 2, 3, 4)
MIN_AGE_D = 30


def eligibility(top_n):
    """{sym: set('YYYY-MM')} months where the coin was top-N by the PRIOR month's volume."""
    vols, first = {}, {}
    for p in DATA.glob("*_1d.csv.gz"):
        s = p.name.split("_")[0]
        try:
            d = pd.read_csv(p, parse_dates=["time"])
        except Exception:
            continue
        if len(d) < 5:
            continue
        first[s] = d.time.iloc[0]
        vols[s] = d.set_index("time")["qvol"].resample("ME").sum()
    V = pd.DataFrame(vols).fillna(0.0)
    elig = {s: set() for s in V.columns}
    for i in range(1, len(V.index)):
        cur = V.index[i]
        mstart = cur.to_period("M").start_time
        ok = [s for s in V.columns if (mstart - first[s]).days >= MIN_AGE_D]
        for s in V.loc[V.index[i - 1], ok].sort_values(ascending=False).index[:top_n]:
            elig[s].add(cur.strftime("%Y-%m"))
    return elig


def one_coin(args):
    """Deployed long pyramid + short sleeve for one coin, on its perp 1h bars."""
    sym, months = args
    import numpy as np
    import pandas as pd
    from backtest import blend
    from backtest.convex import run_uncapped
    from backtest.pyramid import run_pyramid
    from backtest.shortside import signals
    from backtest.timeframes import resample
    f = DATA / f"{sym}_1h.csv.gz"
    if not f.exists() or not months:
        return []
    d = pd.read_csv(f, parse_dates=["time"]).rename(columns={"qvol": "volume"})
    d = d[d.close > 0].reset_index(drop=True)
    gap = d.time.diff().dt.total_seconds().fillna(3600) / 3600
    if (gap > 48).any():                      # relisted symbol: first episode only
        d = d.iloc[:int(np.argmax(gap.values > 48))].reset_index(drop=True)
    if len(d) < 600:
        return []
    out = []
    for rule in RULES:
        df = resample(d, rule)
        if len(df) < 300:
            continue
        t = df["time"].to_numpy()
        a = (blend.atr_ind(df, 14) / df["close"]).replace([np.inf, -np.inf], np.nan).dropna() \
            if hasattr(blend, "atr_ind") else None
        R, idx, _u, held = run_pyramid(df, signals(df, "long", "all"),
                                      sl_mult=blend.SL_MULT, trail=blend.LONG_TRAIL,
                                      max_units=blend.MAX_UNITS, add_every=blend.ADD_EVERY,
                                      fee_bp=blend.FEE_BP, breakeven_at=blend.BE_AT)
        for r, i, h in zip(R, idx, held):
            t0 = t[max(int(i) - int(h), 0)]
            if pd.Timestamp(t0).strftime("%Y-%m") in months:
                out.append(dict(t0=t0, t1=t[int(i)], R=float(r), side="long", sf=0.05,
                                adds=[t0], coin=sym, rule=rule))
        R, idx, bars, _d = run_uncapped(df, signals(df, "short", "all"),
                                        sl_mult=blend.SL_MULT, fee_bp=blend.FEE_BP,
                                        mode="trail_atr", trail=blend.SHORT_TRAIL,
                                        be_at=blend.BE_AT)
        for r, i, b in zip(R, idx, bars):
            t0 = t[max(int(i) - int(b), 0)]
            if pd.Timestamp(t0).strftime("%Y-%m") in months:
                out.append(dict(t0=t0, t1=t[int(i)], R=float(r), side="short", sf=0.05,
                                adds=[t0], coin=sym, rule=rule))
    return out


def build(top_n, only=None):
    elig = eligibility(top_n)
    syms = [s for s, m in elig.items() if m and (DATA / f"{s}_1h.csv.gz").exists()]
    if only is not None:
        syms = [s for s in syms if s in only]
    print(f"  top-{top_n}: {len(syms)} coins ever eligible", flush=True)
    rows = []
    with ProcessPoolExecutor(7) as ex:
        for got in ex.map(one_coin, [(s, elig[s]) for s in syms], chunksize=4):
            rows += got
    return rows


def stat(rows, bear, cut, half, slots=12):
    hpm, dd, wm = [], [], []
    for sd in SEEDS:
        rng = np.random.default_rng(sd)
        tie = rng.random(len(rows))
        o = [rows[i] for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
        import backtest.bull_boost as BB
        old = BB.SLOTS
        BB.SLOTS = slots
        try:
            s = evaluate(o, bear, t_to=cut) if half == "tune" else evaluate(o, bear, t_from=cut)
        finally:
            BB.SLOTS = old
        hpm.append(s["hpm"]); dd.append(s["dd"]); wm.append(s["worst_mo"])
    return float(np.mean(hpm)), float(np.mean(dd)), float(np.mean(wm))


def main():
    bear = regimes()[1000]
    sets = {}
    sets["12 deployed coins"] = build(300, only=set(blend.BOOK))
    for n in (30, 60, 100):
        sets[f"PIT top-{n}"] = build(n)
    allt = pd.DatetimeIndex(sorted(r["t0"] for r in sets["12 deployed coins"]))
    cut = allt[int(len(allt) * 0.6)]
    print(f"\ntune < {cut:%Y-%m-%d} <= holdout | 5 orderings averaged | 12 slots unless noted")
    print(f"  {'universe':<22}{'trades':>8}{'coins':>6}{'TUNE/mo':>9}{'DD':>6}"
          f"{'HOLD/mo':>9}{'DD':>6}{'worst':>8}")
    for lab, rows in sets.items():
        t = stat(rows, bear, cut, "tune"); h = stat(rows, bear, cut, "hold")
        nc = len({r["coin"] for r in rows})
        print(f"  {lab:<22}{len(rows):>8}{nc:>6}{t[0]:>+8.2f}%{t[1]:>5.0f}%{h[0]:>+8.2f}%"
              f"{h[1]:>5.0f}%{h[2]:>+7.1f}%")
    print("\n  more slots on the widest book (breadth is useless if the slots still bind):")
    wide = sets["PIT top-100"]
    for sl in (12, 20, 30):
        t = stat(wide, bear, cut, "tune", sl); h = stat(wide, bear, cut, "hold", sl)
        print(f"  {'top-100, ' + str(sl) + ' slots':<22}{'':>8}{'':>6}{t[0]:>+8.2f}%{t[1]:>5.0f}%"
              f"{h[0]:>+8.2f}%{h[1]:>5.0f}%{h[2]:>+7.1f}%")


if __name__ == "__main__":
    main()

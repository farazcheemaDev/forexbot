"""CHOP AND LIQUIDATION - the two questions the new config has not been asked.

WHY THIS EXISTS
    Today's work produced one real improvement (MAX_UNITS 5 -> 7, stacking with the time stop) and
    the best backtest in the project: +10.76%/mo holdout for tight + time stop + 7 units. Two things
    were never measured for it, and they are the two that decide whether it is usable:

    1. HOW IT BEHAVES IN CHOP. The book is a trend follower. Its return is known to be bimodal by
       regime (doc 00), but that was measured for the DEPLOYED book on the old engine. The new
       config shortens holds (time stop) and adds size to runners (7 units), and both of those
       should interact with regime - the time stop should HELP in chop by cutting dead money, and
       the extra units should do nothing there because nothing runs.

    2. LIQUIDATION RISK. slots_sweep.py reported the triple book at 12 slots running gross leverage
       of 6.8x at p99 and 12.6x at MAXIMUM. lev_test.py put the liquidation line at 10x. A maximum
       above the line has to be quantified rather than noted: how often, for how long, and in what
       conditions.

THE LEVERAGE MEASUREMENT IS REBUILT HERE, because the old one was wrong in a way that matters
    kelly_corrected.simulate counts every position's FINAL unit count from the moment it opens, so
    a position that ends at 7 units is treated as 7 units on day one. That OVERSTATES leverage -
    conservative for a safety check, but useless for asking "how often are we really over 10x".
    Here each unit comes on at its own add time, which is what actually happens.

    Reported on the whole open book through time, hourly, not just at entry events.

REGISTERED PREDICTIONS (before running, 2026-09-24)
    1. Chop is the worst regime for every config, and the time stop narrows the gap most.
    2. The triple book beats the deployed book in chop by MORE than its overall margin, because
       chop is where dead money accumulates and the time stop is what removes it.
    3. With units timed properly, time over 10x gross is under 1% of hours for the triple book,
       and those hours cluster in the strongest bull stretches - when every position is deep in
       profit and its stop is already above entry, which is when high leverage is least dangerous.
    4. Liquidation never actually binds, because a position at 7 units has its stop far above entry.

    python -m backtest.regime_and_liq
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bar_phase import rows_for_phase  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.market_neutral import btc_regime  # noqa: E402

SEEDS = tuple(range(10))
CONFIGS = {
    "main (deployed)": {},
    "tight": dict(tight=True),
    "tight + time stop": dict(tight=True, time_stop=(100, 2.0)),
    "triple (+7 units)": dict(tight=True, time_stop=(100, 2.0), max_units=7),
}
SLOTS = 12


def walk_book(rows, bear, seed, t_from=None, t_to=None):
    """Entry-sized equity plus an HOURLY gross-leverage series with units timed correctly.

    Returns (daily returns, hourly leverage). A unit contributes notional only from the bar its
    add is known, which is the difference from kelly_corrected.simulate - that one applies the
    final unit count from the position's first moment and therefore overstates leverage."""
    rng = np.random.default_rng(seed)
    tie = rng.random(len(rows))
    o = [rows[i] for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
    eq, open_, pts, spans = 1.0, [], [], []

    def bank(upto):
        nonlocal eq, open_
        keep = []
        for p in sorted(open_, key=lambda q: q["t1"]):
            if p["t1"] <= upto:
                eq = max(eq + p["dpr"] * p["R"], 0.0)
                pts.append((p["t1"], eq))
            else:
                keep.append(p)
        open_ = keep

    for r in o:
        t0 = pd.Timestamp(r["t0"])
        if (t_from is not None and t0 < t_from) or (t_to is not None and t0 >= t_to):
            continue
        bank(t0)
        if len(open_) >= SLOTS:
            continue
        try:
            ib = bool(bear.asof(t0))
        except Exception:
            ib = False
        f = blend.RISK / 100.0 * (blend.REGIME_MULT if ib else 1.0)
        dpr = f * eq
        open_.append(dict(r, t1=pd.Timestamp(r["t1"]), dpr=dpr))
        # one span per UNIT, from its own add time to the position's exit
        per_unit = dpr / max(r["sf"], 1e-6)
        if eq > 0:
            for ta in (r.get("adds") or [r["t0"]]):
                spans.append((pd.Timestamp(ta), pd.Timestamp(r["t1"]), per_unit / eq))
    bank(pd.Timestamp("2100-01-01"))
    if len(pts) < 20:
        return None, None
    s = pd.Series([p[1] for p in pts], index=pd.DatetimeIndex([p[0] for p in pts]))
    cur = s.resample("D").last().ffill()
    # BOTH SIDES FORCED TO NANOSECONDS. The rows carry mixed datetime64 units - t0 came back as
    # [us] and t1 as [ms] - so date_range inherited [us] from its bounds while Timestamp.value
    # returned ns. searchsorted then put every span past the end of the grid and the whole
    # leverage series came out zero. This is trap 8 in CLAUDE.md and it cost a run.
    lo = pd.Timestamp(min(x[0] for x in spans)).as_unit("ns")
    hi = pd.Timestamp(max(x[1] for x in spans)).as_unit("ns")
    grid = pd.date_range(lo, hi, freq="h").as_unit("ns")
    lev = np.zeros(len(grid))
    gi = grid.asi8
    assert gi[0] > 1_000_000_000_000_000_000, "grid is not in nanoseconds"
    for a, b, v in spans:
        i = np.searchsorted(gi, pd.Timestamp(a).as_unit("ns").value)
        j = np.searchsorted(gi, pd.Timestamp(b).as_unit("ns").value)
        lev[i:j] += v
    assert lev.max() > 0, "leverage series is empty - a unit mismatch has returned"
    return cur.pct_change().fillna(0.0), pd.Series(lev, index=grid)


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    import backtest.blend as B
    reg = btc_regime(pd.DataFrame({"BTCUSDT": pd.Series(
        B.load("BTCUSDT")["close"].to_numpy(float),
        index=pd.DatetimeIndex(B.load("BTCUSDT")["time"])).resample("D").last().dropna()}))
    print(f"{len(SEEDS)} orderings | 0.30%/unit | 12 slots | holdout from {cut:%Y-%m-%d}")
    print(f"regime from BTC's 50-day trend: " + "  ".join(
        f"{k} {int(v)}d" for k, v in reg.value_counts().items()))

    print()
    print("1. RETURN BY REGIME - mean %/month within each regime, full history, 3x haircut")
    print(f"  {'config':<20}{'BULL':>10}{'BEAR':>10}{'CHOP':>10}{'all':>10}{'chop share':>12}")
    store = {}
    for name, kw in CONFIGS.items():
        rows = rows_for_phase(0, **kw)
        rets, levs = [], []
        for sd in SEEDS:
            r, lv = walk_book(rows, bear, sd)
            if r is not None:
                rets.append(r)
                levs.append(lv)
        store[name] = (rets, levs)
        cells = ""
        for k in ("bull", "bear", "chop", None):
            vals = []
            for r in rets:
                lab = pd.Series([reg.asof(t) if t >= reg.index[0] else "chop" for t in r.index],
                                index=r.index)
                x = r if k is None else r[(lab == k).to_numpy()]
                if len(x) > 20:
                    vals.append(((1 + x.mean()) ** 30 - 1) / blend.HINDSIGHT * 100)
            cells += f"{np.mean(vals):>+9.2f}%" if vals else f"{'-':>10}"
        r0 = rets[0]
        lab0 = pd.Series([reg.asof(t) if t >= reg.index[0] else "chop" for t in r0.index])
        print(f"  {name:<20}{cells}{(lab0 == 'chop').mean()*100:>11.0f}%")

    print()
    print("2. GROSS LEVERAGE THROUGH TIME - units timed at their own add bars")
    print(f"  {'config':<20}{'median':>9}{'p99':>8}{'max':>8}{'% hrs >10x':>12}"
          f"{'worst 24h':>11}{'hrs >10x':>10}")
    for name, (rets, levs) in store.items():
        med = float(np.mean([l.median() for l in levs]))
        p99 = float(np.mean([l.quantile(0.99) for l in levs]))
        mx = float(np.mean([l.max() for l in levs]))
        over = float(np.mean([(l > 10).mean() * 100 for l in levs]))
        hrs = float(np.mean([(l > 10).sum() for l in levs]))
        w24 = float(np.mean([l.rolling(24).mean().max() for l in levs]))
        print(f"  {name:<20}{med:>8.1f}x{p99:>7.1f}x{mx:>7.1f}x{over:>11.2f}%"
              f"{w24:>10.1f}x{hrs:>10.0f}")

    print()
    print("3. WHEN leverage is highest, what is the regime and is the book in profit?")
    rets, levs = store["triple (+7 units)"]
    l = levs[0]
    top = l.sort_values(ascending=False).head(max(int(len(l) * 0.01), 1))
    lab = pd.Series([reg.asof(t) if t >= reg.index[0] else "chop" for t in top.index])
    print(f"  the top 1% of leverage hours ({len(top)} hours, mean {top.mean():.1f}x):")
    for k in ("bull", "bear", "chop"):
        print(f"    {k:<6}{(lab == k).mean()*100:>6.0f}% of them")
    print(f"  their calendar span: {top.index.min():%Y-%m} .. {top.index.max():%Y-%m}")


if __name__ == "__main__":
    main()

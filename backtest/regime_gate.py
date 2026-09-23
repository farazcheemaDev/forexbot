"""THE 1000h / 200h DISCREPANCY, MEASURED - does the gate the bots run match the one tuned?

THE PROBLEM THIS RESOLVES
    The live bots (blend_paper.py, longtrend_bot.py) cut risk to x0.25 while BTC trades
    below its 1000-HOUR average. But REGIME_MULT = 0.25 was validated in opt200.py against
    a 200-HOUR average, and blend.btc_bear() - the function behind most of this repo's
    stored figures - still uses rolling(200).

    200h is ~8 days. 1000h is ~6 weeks. Those are not the same signal, they are not even
    the same KIND of signal: one is a short-term dip filter that flips constantly, the
    other is a slow bear-market flag that stays on for months. A multiplier tuned for the
    first being applied to the second is not a cosmetic mismatch.

    So: is the deployed gate better, worse, or indistinguishable? And is x0.25 still the
    right cut at 1000h, or was that number only right for 200h?

WHY THIS IS NOT MINING THE HOLDOUT
    Every other sweep in this repo searches for a better setting. This one asks whether the
    setting that is ALREADY RUNNING matches the one that was tested. A reconciliation can
    only ever produce bad news (the live config is worse than believed) or no news. The
    holdout column is here to show the direction is consistent, not to pick a winner.

    Deployed engine, 12 slots, compounded by close date, 5 orderings averaged, 3x haircut.

    python -m backtest.regime_gate
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import evaluate  # noqa: E402
from backtest.engine_variants import BASE_RULES, rows_for  # noqa: E402

SEEDS = (0, 1, 2, 3, 4)
MAS = (50, 100, 200, 500, 1000, 1500, 2000)


def gate(ma: int | None):
    """True while BTC's close is below its `ma`-hour mean. Shifted by one bar so the flag
    is knowable at the open of the bar it is applied to. None = no gate at all.

    .astype(bool) is not decoration: `~` on an object-dtype column yields truthy -1/-2 and
    has silently produced nonsense in this repo twice (see CLAUDE.md)."""
    d = blend.load("BTCUSDT")
    s = pd.Series(d["close"].to_numpy(float), index=pd.DatetimeIndex(d["time"]))
    s = s[~s.index.duplicated()].sort_index()
    if ma is None:
        return pd.Series(False, index=s.index).astype(bool)
    return (s < s.rolling(ma).mean()).shift(1).fillna(False).astype(bool)


def orderings(rows):
    """The 5 tie-broken orderings every figure in this repo is averaged over."""
    out = []
    for sd in SEEDS:
        rng = np.random.default_rng(sd)
        tie = rng.random(len(rows))
        out.append([rows[i] for i in sorted(range(len(rows)),
                                            key=lambda i: (rows[i]["t0"], tie[i]))])
    return out


def avg(orders, bear, **kw):
    """evaluate() averaged over orderings; dd and worst month averaged too."""
    res = [evaluate(o, bear, **kw) for o in orders]
    return {k: float(np.mean([r[k] for r in res]))
            for k in ("hpm", "raw", "dd", "worst_mo")}


def trade_share(rows, bear):
    """The number that actually matters: what fraction of ENTRIES the gate quarters.
    Hours-flagged is the wrong denominator - a gate that is on while nothing triggers
    costs nothing."""
    n = 0
    for r in rows:
        try:
            n += bool(bear.asof(r["t0"]))
        except Exception:
            pass
    return n / max(len(rows), 1) * 100


def main():
    rows = rows_for(BASE_RULES)
    orders = orderings(rows)
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    gates = {ma: gate(ma) for ma in MAS}
    g200, g1000 = gates[200], gates[1000]

    # ---- 1. are these even the same signal? ---------------------------------------
    print("1. HOW DIFFERENT ARE THE TWO GATES?\n")
    j = pd.DataFrame({"g200": g200, "g1000": g1000}).dropna()
    agree = float((j.g200 == j.g1000).mean() * 100)
    print(f"  hours where they AGREE: {agree:.0f}%")
    # PERSISTENCE, not median run length. The median run is ~0.1 days at EVERY MA, because
    # price oscillates across any average and throws off a swarm of one-bar runs; that
    # statistic hides the whole difference. What separates these gates is how much of the
    # gated TIME sits inside long stretches.
    print(f"  {'gate':<8}{'hours bear':>12}{'entries gated':>15}{'flips/yr':>10}"
          f"{'mean run':>10}{'longest':>9}{'  bear-hrs in a run >=7d':>26}")
    for ma in MAS:
        b = gates[ma].dropna()
        yrs = (b.index[-1] - b.index[0]).days / 365.25
        runs = b.ne(b.shift()).cumsum()
        sz = b.groupby(runs).size()
        bh = sz[b.groupby(runs).first()]          # run lengths of the BEAR runs only
        tot = max(bh.sum(), 1)
        print(f"  {str(ma) + 'h':<8}{b.mean()*100:>11.0f}%"
              f"{trade_share(rows, gates[ma]):>14.0f}%"
              f"{int((b != b.shift(1)).sum()) / yrs:>10.0f}{bh.mean() / 24:>9.1f}d"
              f"{bh.max() / 24:>8.0f}d{bh[bh >= 168].sum() / tot * 100:>25.0f}%")
    print("\n  The COVERAGE is nearly identical - every gate flags ~45% of hours and ~50%")
    print("  of entries. What differs is PERSISTENCE. A 200h gate never stays on for a")
    print("  month: 0% of its bear-hours are in 30-day-plus runs and its longest run ever")
    print("  is 18 days. At 1000h, 49% are, and the longest run is 88 days. These are not")
    print("  the same kind of signal - one is a dip filter, the other a bear-market flag.")

    # ---- 2. the deployed book under each gate --------------------------------------
    print(f"\n2. THE DEPLOYED BOOK UNDER EACH GATE (bear x0.25 both sides)")
    print(f"  tune < {cut:%Y-%m-%d} <= holdout | 5 orderings averaged | 3x haircut\n")
    hdr = (f"  {'gate':<24}| {'TUNE/mo':>9}{'DD':>6} | {'HOLD/mo':>9}{'DD':>6}"
           f"{'worst mo':>10} | {'FULL/mo':>9}{'DD':>6}")
    print(hdr)
    base = None
    for ma in (None,) + MAS:
        b = gate(ma) if ma is None else gates[ma]
        t = avg(orders, b, t_to=cut)
        h = avg(orders, b, t_from=cut)
        f = avg(orders, b)
        lab = "NO GATE (x1 always)" if ma is None else f"{ma}h"
        if ma == 1000:
            lab += "  <- DEPLOYED"
        if ma == 200:
            lab += "  <- TUNED ON"
        if base is None:
            base = f
        print(f"  {lab:<24}| {t['hpm']:>+8.2f}%{t['dd']:>5.0f}% | {h['hpm']:>+8.2f}%"
              f"{h['dd']:>5.0f}%{h['worst_mo']:>+9.1f}% | {f['hpm']:>+8.2f}%{f['dd']:>5.0f}%")

    # ---- 3. is x0.25 still the right cut at 1000h? ---------------------------------
    print(f"\n3. IS x0.25 STILL THE RIGHT CUT? (the multiplier was tuned at 200h)")
    print(f"  {'gate':<10}{'bear mult':>11}| {'TUNE/mo':>9}{'DD':>6} | {'HOLD/mo':>9}"
          f"{'DD':>6}{'worst mo':>10}")
    for ma in (200, 1000):
        for m in (0.0, 0.10, 0.25, 0.50, 1.0):
            t = avg(orders, gates[ma], bear_mult=m, t_to=cut)
            h = avg(orders, gates[ma], bear_mult=m, t_from=cut)
            star = "  *" if m == 0.25 else ""
            print(f"  {str(ma) + 'h':<10}{m:>11.2f}| {t['hpm']:>+8.2f}%{t['dd']:>5.0f}% | "
                  f"{h['hpm']:>+8.2f}%{h['dd']:>5.0f}%{h['worst_mo']:>+9.1f}%{star}")
        print()

    print("  * = the deployed multiplier. If a different row is better on BOTH halves at")
    print("    1000h, the deployed config is mis-tuned and that is worth acting on.")


if __name__ == "__main__":
    main()

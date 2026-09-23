"""THE SHORT BOOST READ THE BTC FLAG BEFORE IT EXISTED - measured, and the book re-scored.

WHAT WAS FOUND (2026-09-23, while adding funding costs to the engine)
    Every row in the engine carries t0 = the LABEL of its entry bar. For the 1h sleeve that
    is the bar's open time, which is the real entry time. For the resampled sleeves it is
    not: timeframes.resample() uses label='right', closed='right' on 1h OPEN times, so a
    4h bar labelled L aggregates the 1h bars opening at L-3h..L. signals() fire on the
    previous bar's close and enter at this bar's OPEN - real time L-3h. The 12h sleeve
    enters at L-11h. So t0 is 3h late on 4h rows and 11h late on 12h rows.

    btc_trail() flags are indexed by the BTC 4h label L and known at L+1h.
    vol_target.short_boost() and composite.rowset() tag a short as "boosted" with
    br.asof(t0). On 4h/12h rows that returns a BTC bar that closed AFTER the short was
    entered: the flag is on because BTC broke down during the trade.

    Trade-level check (scratch run before this file, reproduced below): of 224 shorts the
    backtest boosted, 118 were not boosted at their real entry time, and those 118 averaged
    +0.766R. For the 4h and 12h sleeves the as-measured and causal tags share ZERO trades.

WHAT ELSE t0 TOUCHES
    evaluate() also reads the regime gate at t0 (bear.asof(t0)) and orders the slot queue by
    t0. Both inherit the same 3h/11h lateness on resampled rows. The 1000h average rarely
    flips inside 11 hours, so that part should be small - it is measured, not assumed.

    The TIGHT exit's alignment (engine_variants.break_map) was checked and is causal: it
    reads a BTC bar known at or before the bar-end at which the trail is updated.

THE FIX
    t0 -> real entry time (t0 - rule + 1h) for every resampled row, for ordering, gating and
    the boost flag; the boost flag read from BTC bars indexed by the time they became known.

REGISTERED PREDICTION (before the portfolio run)
    The short boost's holdout gain (+1.3%/mo at x5, +2.3% at x8 over deployed on this path)
    roughly halves, since boosted-short mean R falls 0.481 -> 0.305 and the extra boosted
    trades are the weaker ones. The deployed book moves by under 1%/mo.

    python -m backtest.causal_t0
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.btc_exit import btc_trail  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.engine_variants import BASE_RULES, rows_for, run  # noqa: E402

LATE = {"1h": pd.Timedelta(0), "4h": pd.Timedelta(hours=3), "12h": pd.Timedelta(hours=11)}


def real_t0(rows):
    """Rows with t0 moved to the real entry time. Sorted again, since the order changes."""
    out = [dict(r, t0=(pd.Timestamp(r["t0"]) - LATE[r["rule"]]).to_datetime64())
           for r in rows]
    out.sort(key=lambda r: r["t0"])
    return out


def boost(rows, mult, causal):
    """Shorts x mult while BTC's 4h trail is broken. causal=False reproduces
    vol_target.short_boost exactly (br.asof on the row's t0)."""
    br = btc_trail(5)
    if causal:
        br = pd.Series(br.to_numpy(), index=br.index + pd.Timedelta(hours=1))  # known-at
    out = []
    for r in rows:
        f = 1.0
        if r["side"] == "short":
            t = pd.Timestamp(r["t0"])
            if t >= br.index[0] and bool(br.asof(t)):
                f = mult
        out.append(dict(r, R=r["R"] * f, boosted=f > 1))
    return out


def trade_level(rows):
    s = [r for r in rows if r["side"] == "short"]
    on = np.array([r["R"] for r in s if r.get("boosted")])
    off = np.array([r["R"] for r in s if not r.get("boosted")])
    return len(on), float(on.mean()) if len(on) else np.nan, float(off.mean())


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    print(f"tune < {cut:%Y-%m-%d} <= holdout | 5 orderings averaged, 3x haircut on %/mo\n")

    base = rows_for(BASE_RULES)
    tight = rows_for(BASE_RULES, tight=True)

    print("  TRADE LEVEL - shorts tagged 'boosted' (R per unit, before the multiplier)")
    for lab, rr, causal in (("as measured: br.asof(label t0)", base, False),
                            ("causal: flag known at real entry", real_t0(base), True)):
        # a multiplier a hair above 1 tags the trades without changing their R
        n, m_on, m_off = trade_level(boost(rr, 1.0 + 1e-9, causal))
        print(f"    {lab:<36} boosted n={n:>4}  mean {m_on:+.3f}R   others {m_off:+.3f}R")

    print(f"\n  {'book':<44}{'TUNE/mo':>9}{'DD':>5}{'HOLD/mo':>9}{'DD':>5}{'worst':>8}")

    def show(lab, rows):
        a = run(rows, bear, cut, "tune"); b = run(rows, bear, cut, "hold")
        print(f"  {lab:<44}{a[0]:>+8.2f}%{a[1]:>4.0f}%{b[0]:>+8.2f}%{b[1]:>4.0f}%{b[2]:>+7.1f}%")
        return a, b

    print("  -- as previously measured (t0 = bar label) --")
    show("deployed", base)
    show("short boost x5", boost(base, 5, False))
    show("short boost x8", boost(base, 8, False))
    show("tight", tight)
    show("tight + short boost x5 (the paper books)", boost(tight, 5, False))

    print("  -- causal (t0 = real entry; flag known at entry) --")
    show("deployed", real_t0(base))
    show("short boost x5", boost(real_t0(base), 5, True))
    show("short boost x8", boost(real_t0(base), 8, True))
    show("tight", real_t0(tight))
    show("tight + short boost x5 (the paper books)", boost(real_t0(tight), 5, True))


if __name__ == "__main__":
    main()

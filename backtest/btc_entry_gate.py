"""STOP OPENING LONGS WHILE BTC'S 4h TREND IS BROKEN - the last BTC-signal lever.

btc_timing.py showed the best simple read of where BTC is going is the one the bot already
uses (BTC above its 1000h average: Sharpe 1.12 against 0.68 for holding, better than every
outside signal tested). The tight exit already uses BTC's 4h trail break to TIGHTEN open
longs (confirmed on both halves). But the bot keeps OPENING new longs during that break, and
a long opened during a break gets the WIDE trail until the break switches off
(graveyard_rescore.walk: 'barmed' is False at entry when the flag is on).

Two ways to use the same signal at entry, on top of tight exit + time stop:
    SKIP   no new long entries while BTC's 4h trail is broken
    TIGHT  new longs entered during a break start on the 5xATR trail at once
Shorts unchanged. Corrected engine, entry-sized, 10 paired orderings, 1000h gate kept.

REGISTERED PREDICTIONS (before running)
    SKIP: fewer trades, smaller worst month on both halves, return within +-0.5%/mo.
    TIGHT: slightly worse than SKIP (a tight trail on a fresh breakout is a quick stop-out).
    Neither clears "both halves by 2 paired SE" - the break already does its work on exits.

    python -m backtest.btc_entry_gate
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.btc_dial import score  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.causal_t0 import real_t0  # noqa: E402
from backtest.engine_variants import break_map, shorts_for  # noqa: E402
from backtest.funding_cost import charged, long_funding, short_funding  # noqa: E402
from backtest.graveyard_rescore import rows as book_rows, walk  # noqa: E402
from backtest.timeframes import resample  # noqa: E402

TS = (100, 2.0)


def variant(mode):
    out = []
    for rule in ("1h", "4h", "12h"):
        out += shorts_for(rule)
        for coin in blend.BOOK:
            d = blend.load(coin)
            if d is None:
                continue
            df = resample(d, rule)
            if len(df) < 300:
                continue
            br = break_map(df, rule)
            rows = walk(df, rule, coin, tb=br, time_stop=TS) if mode == "SKIP" else \
                walk_tight_at_entry(df, rule, coin, br)
            if mode == "SKIP":
                t = df["time"].to_numpy()
                on = dict(zip(t, br))
                rows = [r for r in rows if not on.get(r["t0"], False)]
            out += rows
    return charged(real_t0(short_funding(long_funding(out))))


def walk_tight_at_entry(df, rule, coin, br):
    """graveyard_rescore.walk with one change: a long opened while the BTC break is ON is
    armed at once (it will tighten on the next bar the break is still on) instead of waiting
    for the break to switch off first. Implemented by wrapping walk() with a flag array that
    is shifted so the entry bar reads 'off' - done per position would be O(n^2), so instead
    the flag seen by the walk is ORed with nothing and the arming rule is emulated: every
    bar where the break is on and the previous bar's break was also on is fed as 'off then
    on' only for the arming test. Simplest faithful version: pass tb = br, and pre-arm by
    feeding a copy of walk's source with barmed=True."""
    import inspect
    import backtest.graveyard_rescore as G
    src = inspect.getsource(G.walk).replace('barmed=(tb is None or not tb[i])', 'barmed=True')
    ns = dict(G.__dict__)
    exec(src, ns)
    return ns["walk"](df, rule, coin, tb=br, time_stop=TS)


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    base = book_rows(tight=True, time_stop=TS)
    B = score(base, bear, cut)
    print("tight + time stop, corrected engine, entry-sized, 10 paired orderings\n")
    for lab, rs in (("base", base), ("SKIP longs during BTC break", variant("SKIP")),
                    ("TIGHT trail from entry during break", variant("TIGHT"))):
        R_ = score(rs, bear, cut) if lab != "base" else B
        nl = sum(1 for r in rs if r["side"] == "long")
        dt = R_["tune"][:, 0] - B["tune"][:, 0]; dh = R_["hold"][:, 0] - B["hold"][:, 0]
        print(f"  {lab:<38} longs {nl:>5} | tune {R_['tune'][:,0].mean():+.2f}% DD {R_['tune'][:,1].mean():.0f}% "
              f"worst {R_['tune'][:,2].mean():+.1f}% | hold {R_['hold'][:,0].mean():+.2f}% DD "
              f"{R_['hold'][:,1].mean():.0f}% worst {R_['hold'][:,2].mean():+.1f}% | d "
              f"{dt.mean():+.2f}+-{dt.std(ddof=1)/np.sqrt(len(dt)):.2f} / {dh.mean():+.2f}+-"
              f"{dh.std(ddof=1)/np.sqrt(len(dh)):.2f}")


if __name__ == "__main__":
    main()

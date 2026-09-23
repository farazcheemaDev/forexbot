"""FUNDING FARMING WITH A REALISTIC EXIT - the one settlement variant still alive.

settlement_check.py established, on 1-minute bars:
  - the price rise INTO a negative-funding settlement reverses almost entirely inside the
    FIRST MINUTE after it (POST-selected sample: long t-2h -> t +35.3bp, -> t+1m +1.6bp);
  - so the POST short is a sub-second race (enter t+0m +43bp gross, t+1m +10bp, t+3m -2bp).

What is left is the classic "funding farm": be LONG at the settlement instant of a coin with
negative funding (a long RECEIVES it), and get out right after. A retail bot cannot sell at
the settlement second, so the honest exit is t+1m or later. P&L = price(t-H -> exit) +
funding received - costs. The market's defence is exactly the first-minute dump.

This file measures it on a random sample of PRE-selected events (selected on the PREVIOUS
settlement's rate, so causal), with 1-minute prices for entry and exit and every settlement
held credited/charged.

REGISTERED PREDICTION (before running): with exit at t+1m the price leg is about minus the
funding, so the net at 12bp is within +-10bp of zero at both thresholds - the market prices
the farm. Dead unless the -0.30% bucket nets > +20bp in BOTH halves.

    python -m backtest.settlement_farm
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.listing_events import day_1m  # noqa: E402
from backtest.settlement_check import crossed, settle_book  # noqa: E402
from backtest.settlement_timing import VOL_FLOOR, load_all  # noqa: E402

HOUR = 3600 * 10**9
ENTRIES = (120, 60, 30)            # minutes before the settlement
EXITS = (0, 1, 2, 5, 15)           # minutes after it


def sample(E, thr, n, seed):
    g = E[(E.r_prev <= -thr) & (E.gap >= 4)].reset_index(drop=True)
    rng = np.random.default_rng(seed)
    return g.iloc[rng.choice(len(g), size=min(n, len(g)), replace=False)].reset_index(drop=True)


def measure(ev, book):
    t = pd.Timestamp(ev.t, unit="ns")
    days = sorted({(t - pd.Timedelta(hours=3)).strftime("%Y-%m-%d"),
                   (t + pd.Timedelta(hours=1)).strftime("%Y-%m-%d")})
    parts = [day_1m("um", ev.sym, d) for d in days]
    parts = [p for p in parts if p is not None]
    if not parts:
        return None
    d = pd.concat(parts).drop_duplicates("t").set_index("t").sort_index()["o"]
    tm = t.value // 10**6
    px = {k: d.get(tm + k * 60_000) for k in set(EXITS) | {-e for e in ENTRIES}}
    rec = dict(t=t, sym=ev.sym, r=ev.r, r_prev=ev.r_prev)
    for e in ENTRIES:
        for x in EXITS:
            a, b = px.get(-e), px.get(x)
            if a is None or b is None or not a or not np.isfinite(a) or not np.isfinite(b):
                continue
            # a long receives -rate at every settlement held (t-e min, t+x min]
            fund = -crossed(book, np.array([ev.sym]),
                            np.array([ev.t - e * 60 * 10**9], np.int64),
                            np.array([ev.t + x * 60 * 10**9], np.int64))[0]
            rec[f"px_{e}_{x}"] = b / a - 1
            rec[f"f_{e}_{x}"] = fund
    return rec


def main():
    E_all = load_all()
    book = settle_book(E_all)
    E = E_all[(E_all.vol24 >= VOL_FLOOR) & np.isfinite(E_all.p0)].copy()
    cut = pd.to_datetime(E.t, unit="ns").quantile(0.6)
    for thr, n in ((0.001, 400), (0.003, 300)):
        S = sample(E, thr, n, seed=11)
        R = pd.DataFrame([x for x in (measure(ev, book) for ev in S.itertuples()) if x])
        R["half"] = np.where(R.t < cut, "tune", "hold")
        print(f"\nPREVIOUS rate <= -{thr*100:.2f}%, 4h/8h coins, {len(R)} random events with 1m data "
              f"(tune {int((R.half=='tune').sum())} / holdout {int((R.half=='hold').sum())})")
        print("  net bp at 12bp cost = price leg + funding received - 12; (price, funding) below")
        print(f"  {'enter':<10}" + "".join(f"{'exit t+%dm' % x:>22}" for x in EXITS))
        for e in ENTRIES:
            line = f"  t-{e:<7}m"
            for x in EXITS:
                p = R.get(f"px_{e}_{x}"); f = R.get(f"f_{e}_{x}")
                if p is None:
                    line += f"{'-':>22}"; continue
                net = (p + f - 12 / 1e4) * 1e4
                line += f"{net.mean():>+8.1f} ({p.mean()*1e4:+5.0f},{f.mean()*1e4:+4.0f})"
            print(line)
        e, x = 60, 1
        net = (R[f"px_{e}_{x}"] + R[f"f_{e}_{x}"] - 12 / 1e4) * 1e4
        print(f"  enter t-60m / exit t+1m by half: " + "  ".join(
            f"{h}: {net[R.half == h].mean():+.1f}bp (n {int((R.half == h).sum())}, win "
            f"{(net[R.half == h] > 0).mean()*100:.0f}%)" for h in ("tune", "hold")))
        print("  by year: " + "  ".join(f"{y}: {v.mean():+.0f}" for y, v in
                                        net.groupby(R.t.dt.year)))


if __name__ == "__main__":
    main()

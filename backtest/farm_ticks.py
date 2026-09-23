"""EXIT SLIPPAGE FOR THE FUNDING FARM, ON THE EVENTS IT ACTUALLY TRADES - tick data.

settlement_ticks.py measured the post-settlement drop on POST-selected events (this settlement
paid <= -0.10%). funding_farm.py trades PRE-selected events (the PREVIOUS settlement paid
<= -0.10%) and assumes an 8.3bp exit slippage, the 0.74s figure from that other sample. This
measures it on the farm's own population: the price a market sell gets L seconds after the
settlement, against the first trade at/after t (the 1m open funding_farm.py exits at).

REGISTERED PREDICTION: within 3bp of the POST sample at every L (0.25s ~ -8bp, 1s ~ -17bp).

    python -m backtest.farm_ticks
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.settlement_ticks import LAT, ticks  # noqa: E402
from backtest.settlement_timing import VOL_FLOOR, load_all  # noqa: E402


def main():
    E = load_all()
    E = E[(E.vol24 >= VOL_FLOOR) & np.isfinite(E.p0)].copy()
    E["dt"] = pd.to_datetime(E.t, unit="ns")
    g = E[(E.r_prev <= -0.001) & (E.gap >= 4) & (E.dt >= "2024-01-01")].reset_index(drop=True)
    rng = np.random.default_rng(41)
    S = g.iloc[rng.choice(len(g), size=min(80, len(g)), replace=False)]
    rows = []
    for ev in S.itertuples():
        t = pd.Timestamp(ev.t, unit="ns")
        d = ticks(ev.sym, t)
        if d is None:
            continue
        t0 = t.value // 10**6
        T, P, M = d["T"].to_numpy(), d["p"].to_numpy(), d["m"].to_numpy(bool)
        first = np.nonzero(T >= t0)[0]
        if not len(first):
            continue
        rec = dict(first=P[first[0]], first_lag=(T[first[0]] - t0) / 1000, r=ev.r)
        for L in LAT:
            k = np.nonzero(M & (T >= t0 + int(L * 1000)))[0]     # a market SELL hits the bid
            rec[f"x{L}"] = P[k[0]] if len(k) else np.nan
        rows.append(rec)
    R = pd.DataFrame(rows)
    print(f"{len(R)} PRE-selected events with ticks (previous rate <= -0.10%, 4h/8h, 2024-2026)")
    print(f"  first trade after t arrives {R.first_lag.median():.3f}s after it (median)")
    print(f"  funding these longs received at t: {-R.r.mean()*1e4:+.1f}bp mean")
    print("  market SELL L seconds after t, vs the first trade at/after t (funding_farm.py's exit):")
    for L in LAT:
        x = (R[f"x{L}"] / R["first"] - 1) * 1e4
        print(f"    t+{L:<6}{x.mean():>+8.1f}bp mean {x.median():>+8.1f}bp median")


if __name__ == "__main__":
    main()

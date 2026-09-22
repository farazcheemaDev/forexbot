"""FUNDING SPIKES - collect extreme funding on small perps, hedged with spot.

WHY THIS AND NOT THE FUNDING TESTS THAT DIED
    cash_carry.py and funding_xs.py died on the AVERAGE: funding on liquid perps runs
    ~0.25bp per 8h (2.7%/yr), less than the fees to hold both legs. But the average hides
    a fat right tail. When a small coin pumps, longs pile into its perp and funding can
    run 0.1% to 2% PER SETTLEMENT for days. Short the perp, hold the same coin on spot,
    and price cancels; the payment does not.

    It is a payment, not a forecast - the one kind of edge that has held up in this
    project - and it is capacity-limited: a spike on a $5M/day coin absorbs a few
    thousand dollars before the funding itself collapses. Invisible to a fund, sized
    for $221.

THIS FILE IS THE CEILING CHECK, NOT THE STRATEGY
    Funding history for all 855 perps is already on disk (perp_fetch.py). Before
    building spot data, execution and basis modelling, measure the most this could pay:

      * an EVENT starts at a settlement whose rate, scaled to an 8h basis, is at least
        the entry threshold. Enter AFTER that settlement (you cannot collect the one
        that told you about the spike).
      * hold through following settlements, collecting each one, until a settlement
        comes in below the exit threshold, or 7 days pass.
      * cost 0.30% round trip for four taker legs (perp 0.05% x2, spot 0.10% x2).
      * the hedge needs a SPOT market: a coin is only counted while it had Binance spot
        (spot_first from perp_fetch.py).

    Not modelled here, and all of it could only LOWER the result: the basis moving
    against the position while it is open, the premium blowing out in a squeeze, and
    margin on the short leg. Positive basis convergence on exit would RAISE it.

    python -m backtest.funding_spikes
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DATA = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "perps"
COST = 0.0030
MAX_HOLD = pd.Timedelta(days=7)


def load():
    uni = {m["sym"]: m for m in json.load(open(DATA / "universe.json"))}
    out = {}
    for sym, m in uni.items():
        f = DATA / f"{sym}_funding.csv.gz"
        if not f.exists() or not m.get("spot_first"):
            continue                             # no Binance spot, no hedge
        fr = pd.read_csv(f, parse_dates=["time"]).sort_values("time")
        if len(fr) < 10:
            continue
        spot_from = pd.Timestamp(m["spot_first"] + "-01") + pd.Timedelta(days=31)
        fr = fr[fr.time >= spot_from]
        if len(fr) < 10:
            continue
        gap_h = fr.time.diff().dt.total_seconds().div(3600).fillna(8.0).clip(1, 8)
        fr["r8"] = fr.rate * 8.0 / gap_h          # rate on an 8h basis
        out[sym] = fr.reset_index(drop=True)
    return out


def events(frames, enter, leave):
    rows = []
    for sym, fr in frames.items():
        r, r8, t = fr.rate.to_numpy(), fr.r8.to_numpy(), fr.time.to_numpy()
        i = 0
        while i < len(fr) - 1:
            if r8[i] < enter:
                i += 1; continue
            t0 = t[i]
            got, j = 0.0, i + 1                   # first COLLECTED settlement is the next one
            while j < len(fr):
                got += r[j]
                if r8[j] < leave or (t[j] - t0) > MAX_HOLD:
                    break
                j += 1
            rows.append(dict(sym=sym, t0=pd.Timestamp(t0), t1=pd.Timestamp(t[min(j, len(fr) - 1)]),
                             trigger=r8[i], carry=got, n=j - i, net=got - COST))
            i = j + 1
    return pd.DataFrame(rows)


def main():
    frames = load()
    allr = pd.concat([f.r8 for f in frames.values()])
    print(f"{len(frames)} perps with a Binance spot hedge; {len(allr):,} settlements")
    print("settlement rate on an 8h basis - how fat is the tail?")
    for q in (0.5, 0.9, 0.99, 0.999):
        print(f"  {q*100:>5.1f}th percentile  {allr.quantile(q)*100:+.4f}%")
    print(f"  share of settlements >= +0.10%: {(allr >= 0.001).mean()*100:.2f}%   "
          f">= +0.50%: {(allr >= 0.005).mean()*100:.3f}%\n")

    print(f"{'enter >=':>9}{'leave <':>9}{'events':>8}{'/month':>8}{'mean carry':>12}"
          f"{'median':>9}{'net>0':>7}{'mean net':>10}{'hold (settl.)':>14}{'top 5% share':>13}")
    for enter in (0.001, 0.002, 0.005, 0.01):
        for leave in (0.0003, 0.001):
            if leave >= enter:
                continue
            E = events(frames, enter, leave)
            if not len(E):
                continue
            months = max((E.t0.max() - E.t0.min()).days / 30.4, 1)
            top = E.net.sort_values(ascending=False)
            share = top.iloc[:max(1, len(top) // 20)].sum() / top[top > 0].sum() * 100 \
                if (top > 0).any() else 0
            print(f"{enter*100:>8.2f}%{leave*100:>8.2f}%{len(E):>8}{len(E)/months:>8.1f}"
                  f"{E.carry.mean()*100:>+11.2f}%{E.carry.median()*100:>+8.2f}%"
                  f"{(E.net > 0).mean()*100:>6.0f}%{E.net.mean()*100:>+9.2f}%"
                  f"{E.n.median():>14.0f}{share:>12.0f}%")
    E = events(frames, 0.002, 0.0003)
    E["year"] = E.t0.dt.year
    print("\nby year, enter >= 0.20%/8h, leave < 0.03%/8h:")
    for y, g in E.groupby("year"):
        print(f"  {y}: {len(g):>4} events  mean net {g.net.mean()*100:+.2f}%  "
              f"median net {g.net.median()*100:+.2f}%  sum of net {g.net.sum()*100:+.0f}%")
    E.to_pickle(DATA.parent / "funding_spike_events.pkl")


if __name__ == "__main__":
    main()

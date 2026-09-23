"""THE FUNDING FARM WITH A TIMED EXIT - the one settlement variant the tick data leaves alive.

WHAT THE LAST THREE FILES ESTABLISHED
  settlement_timing.py  price rises INTO a negative-funding settlement and falls after it.
  settlement_check.py   the POST short needs the first minute; hourly/1m bots cannot have it.
  settlement_ticks.py   on tick data the post-settlement drop happens within ~0.2-1 SECOND.
                        A PRE long that sells 0.22s after the settlement gives up only 3.3bp
                        against the last print before it; 0.74s late, 8.3bp; 1.4s, 16.8bp.
  settlement_farm.py    with a t+1 MINUTE exit the farm nets ~0 (its registered test: dead).

So the question is no longer "can a poller get there" but "what does a bot that fires a
market sell on a CLOCK at the settlement second earn": be long through the settlement of a
coin whose previous funding was deeply negative (a long RECEIVES negative funding), ride the
pre-settlement short-covering, collect the payment, sell ~0.2-0.5s after.

THE TRADE, EXACTLY
    Select at t-H using ONLY the previous settlement's rate <= -thr (causal); 4h/8h coins;
    24h quote volume >= $10M. Enter long at the 1m open of t-H (H = 120 or 60 minutes).
    Exit at the 1m open of the settlement minute (= first trade at/after t), then charge the
    measured tick slippage for a real bot: 8.3bp (the 0.74s figure) - the pessimistic end
    of what a clock-fired order from a VM should see. 12bp fees. Funding: every settlement
    held (the one at t included).

    Samples are random but LARGER than settlement_farm.py (800 / 600 events) and reported by
    half, by year, and as a PORTFOLIO: at each settlement all qualifying coins equal-weighted,
    so correlated events at one timestamp count once. That portfolio series is what an
    account would see.

REGISTERED PREDICTIONS (before running)
    thr 0.10%: net (after 12bp and 8.3bp slippage) > +10bp per event in BOTH halves.
    thr 0.30%: > +30bp in both halves.
    Per-settlement portfolio positive in at least 5 of the 7 calendar years at 0.10%.
    If the 0.10% tune half is negative, the farm is dead regardless of the holdout.

    python -m backtest.funding_farm
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

TICK_SLIP = 8.3 / 1e4          # settlement_ticks.py: exit 0.74s after t costs 8.3bp
FEE = 12 / 1e4
ENTRIES = (120, 60)


def measure(ev, book):
    t = pd.Timestamp(ev.t, unit="ns")
    days = sorted({(t - pd.Timedelta(hours=3)).strftime("%Y-%m-%d"), t.strftime("%Y-%m-%d")})
    parts = [day_1m("um", ev.sym, d) for d in days]
    parts = [p for p in parts if p is not None]
    if not parts:
        return None
    d = pd.concat(parts).drop_duplicates("t").set_index("t").sort_index()["o"]
    tm = t.value // 10**6
    out = dict(t=t, sym=ev.sym)
    x = d.get(tm)
    if x is None or not np.isfinite(x):
        return None
    for e in ENTRIES:
        a = d.get(tm - e * 60_000)
        if a is None or not a or not np.isfinite(a):
            continue
        fund = -crossed(book, np.array([ev.sym]), np.array([ev.t - e * 60 * 10**9], np.int64),
                        np.array([ev.t], np.int64))[0]
        out[f"px{e}"] = x / a - 1
        out[f"f{e}"] = fund
        out[f"net{e}"] = x / a - 1 + fund - FEE - TICK_SLIP
    return out


def cluster_t(x, g, reps=3000, seed=4):
    x = np.asarray(x, float); g = np.asarray(g)
    ug, inv = np.unique(g, return_inverse=True)
    s = np.bincount(inv, weights=x); c = np.bincount(inv)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(ug), size=(reps, len(ug)))
    bs = s[pick].sum(1) / c[pick].sum(1)
    return float(x.mean() / bs.std()) if bs.std() > 0 else np.nan


def main():
    E_all = load_all()
    book = settle_book(E_all)
    E = E_all[(E_all.vol24 >= VOL_FLOOR) & np.isfinite(E_all.p0)].copy()
    cut = pd.to_datetime(E.t, unit="ns").quantile(0.6)
    for thr, n in ((0.001, 800), (0.003, 600)):
        g = E[(E.r_prev <= -thr) & (E.gap >= 4)].reset_index(drop=True)
        rng = np.random.default_rng(31)
        S = g.iloc[rng.choice(len(g), size=min(n, len(g)), replace=False)]
        R = pd.DataFrame([x for x in (measure(ev, book) for ev in S.itertuples()) if x])
        R["half"] = np.where(R.t < cut, "tune", "hold")
        print(f"\nPREVIOUS rate <= -{thr*100:.2f}% | {len(R)} events with 1m data of {len(g):,} "
              f"eligible | tune < {cut:%Y-%m-%d} <= holdout")
        print(f"  net = price + funding - 12bp fee - 8.3bp exit slippage (bp per event)")
        for e in ENTRIES:
            if f"net{e}" not in R:
                continue
            k = R.dropna(subset=[f"net{e}"])
            nb = k[f"net{e}"] * 1e4
            print(f"  enter t-{e}m: n {len(k)}  price {k[f'px{e}'].mean()*1e4:+.1f}  funding "
                  f"{k[f'f{e}'].mean()*1e4:+.1f}  NET {nb.mean():+.1f} (median {nb.median():+.1f}, "
                  f"sd {nb.std():.0f}, win {(nb > 0).mean()*100:.0f}%, t_clust "
                  f"{cluster_t(nb, k.t):+.2f})")
            for h in ("tune", "hold"):
                m = nb[k.half == h]
                print(f"      {h}: {m.mean():+7.1f}bp  n {len(m)}  t_clust "
                      f"{cluster_t(m, k.t[k.half == h]):+.2f}")
            print("      by year: " + "  ".join(f"{y}: {v.mean():+.0f} (n{len(v)})"
                                               for y, v in nb.groupby(k.t.dt.year)))
            # the account's view: one equal-weighted basket per settlement timestamp
            port = nb.groupby(k.t).mean()
            print(f"      per-settlement basket: {len(port)} settlements, mean {port.mean():+.1f}bp, "
                  f"win {(port > 0).mean()*100:.0f}%, by year: " + "  ".join(
                      f"{y}: {v.mean():+.0f}" for y, v in port.groupby(port.index.year)))


if __name__ == "__main__":
    main()

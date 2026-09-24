"""DO CRASH BIDS ON CROWDED-LONG COINS BOUNCE MORE? Funding as a filter for the wick book.

Mechanism: a long-liquidation cascade needs crowded longs, and crowded longs pay funding. A 10% hourly
wick on a coin whose longs were paying a lot is forced selling with no opinion behind it - it should
snap back. The same wick on a coin whose SHORTS were paying (negative funding: people betting on a
fall) is more likely informed selling - it should keep going. The funding rate settled BEFORE the
hour is known when the bid is placed, so a filter on it is causal.

Fills: the doc 16 rule (top-40, 10% under, no bids on BEAR days, sold at the fill hour's close, 38bp),
from wick_better.py. Funding: each coin's last settled rate before the hour, and its sum over the
prior 24h (strategy_analysis/data/perps/*_funding.csv.gz, dead coins included). Terciles are cut on
the TUNE half and applied unchanged to the holdout.

REGISTERED PREDICTION (2026-09-25, before running): per fill after costs rises with prior funding;
the top tercile beats the bottom by at least 1 point on BOTH halves; fills on negative funding are
the worst group. If that holds, skipping the bottom tercile is tested as a book against "just
smaller".

    python -m backtest.wick_funding
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.crash_buy import CUT  # noqa: E402
from backtest.wick_better import EXTRA, FEE, book, fills, load_all, stats  # noqa: E402
from backtest.wide_book import DATA  # noqa: E402


def funding(sym):
    p = DATA / f"{sym}_funding.csv.gz"
    if not p.exists():
        return None
    d = pd.read_csv(p)
    d["time"] = pd.to_datetime(d["time"], format="mixed").astype("datetime64[ns]")
    return d.drop_duplicates("time").sort_values("time").set_index("time")["rate"]


def main():
    X, _, bear = load_all()
    Y = fills(X[X.in40], skip_bear=bear).reset_index(drop=True)
    last, s24 = [], []
    cache = {}
    for r in Y.itertuples():
        if r.sym not in cache:
            cache[r.sym] = funding(r.sym)
        f = cache[r.sym]
        if f is None or not len(f):
            last.append(np.nan); s24.append(np.nan); continue
        prior = f[f.index < r.t]                       # settled BEFORE the hour starts
        last.append(float(prior.iloc[-1]) if len(prior) else np.nan)
        w24 = prior[prior.index >= r.t - pd.Timedelta(hours=24)]
        s24.append(float(w24.sum()) if len(w24) else np.nan)
    Y["f_last"], Y["f_24h"] = last, s24
    Y["net"] = Y.ret - FEE - EXTRA
    Y = Y.dropna(subset=["f_last"])
    tu = Y.t < CUT
    print(f"{len(Y)} fills with funding history (top-40, skip BEAR, 10%, fill-hour close, after 38bp)\n")
    for col in ("f_last", "f_24h"):
        q = Y.loc[tu, col].quantile([1 / 3, 2 / 3]).to_numpy()
        Y["grp"] = np.where(Y[col] <= q[0], "low", np.where(Y[col] <= q[1], "mid", "high"))
        print(f"BY {col} (tune terciles: <= {q[0]*1e4:.2f}bp / <= {q[1]*1e4:.2f}bp / above)")
        for g in ("low", "mid", "high"):
            a, b = Y[tu & (Y.grp == g)], Y[~tu & (Y.grp == g)]
            print(f"  {g:<5} tune {a.net.mean()*100:+.2f}% (n {len(a)}, losing {(a.net < 0).mean()*100:.0f}%)   "
                  f"holdout {b.net.mean()*100:+.2f}% (n {len(b)}, losing {(b.net < 0).mean()*100:.0f}%)")
        neg = Y[Y[col] < 0]
        print(f"  funding below zero: tune {neg[neg.t < CUT].net.mean()*100:+.2f}% (n {(neg.t < CUT).sum()})  "
              f"holdout {neg[neg.t >= CUT].net.mean()*100:+.2f}% (n {(neg.t >= CUT).sum()})\n")
    # the filter as a book, if the registered pattern holds: skip the bottom tercile of f_last
    q = Y.loc[tu, "f_last"].quantile(1 / 3)
    base = stats(book(Y, 40)[0])
    filt = stats(book(Y[Y.f_last > q], 40)[0])
    for lab, s in (("top-40 skip-BEAR, all fills", base), ("... skipping the bottom funding tercile", filt)):
        print(f"  {lab:<42} tune {s['tune']:+.1f}%/yr  worst mo {s['wm_t']:+.1f}%  |  holdout {s['hold']:+.1f}%/yr  "
              f"worst mo {s['wm_h']:+.1f}%  | fall {s['dd']:.0f}%")


if __name__ == "__main__":
    main()

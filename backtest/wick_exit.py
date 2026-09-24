"""WHEN TO SELL A CRASH-BID FILL - and what holding longer costs in risk. 1-minute bars, both venues.

wick_5m.py (5-minute bars, Binance, 2020-2026) found that selling 120 minutes after the fill beat
selling at the hour's close on both halves, but only after looking. wick_bitget.py replayed the
paper book on 1-minute bars 2022-2026 and read the same (Bitget +1.25% vs +1.08% a kept fill). What
neither measured is the price of holding longer: the book carries its fills through the minutes
after a cascade, when second legs happen. This takes the replay's own kept fills
(logs/wick_bitget_fills.csv.gz) and the same cached 1-minute bars, and for each exit rule reports the
return per fill AND the worst paper loss while held (every fill of a cohort at its lowest point
between fill and exit at once, as a share of the ledger, 1/40 per fill).

EXITS
  E0  the fill hour's close                                     (the rule)
  E1  120 minutes after the fill minute                          (recorded beside it)
  E2  the close 2 hours after the fill hour's close
  E3  E1, but only after an hour whose bids hit the cap (10 fills - a market-wide wave, which the bot
      knows at the hour's close because it cancelled the rest); otherwise E0.
  E4  E0, but after a capped wave, E1.  (the same as E3; kept as a check that the split is right)

REGISTERED PREDICTION (2026-09-25, before running): E1 beats E0 by about +0.2 a fill on both halves
and both venues; its worst paper loss while held is deeper, about -20% against -16%; E3 keeps most
of E1's gain because the post-cascade drift is where it comes from.

    python -m backtest.wick_exit
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wick_paper as w  # noqa: E402
from backtest.crash_buy import CUT  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
M1C = ROOT / "strategy_analysis" / "data" / "wick1m_cache.pkl"


def main():
    F = pd.read_csv(ROOT / "logs" / "wick_bitget_fills.csv.gz")
    F = F[F.kept == 1].copy()
    F["t"] = pd.to_datetime(F.hour)
    F["H"] = (F.t - pd.Timestamp("1970-01-01")) // pd.Timedelta(milliseconds=1)
    m1 = pickle.loads(M1C.read_bytes())
    listed = w.bitget_listed()
    wave = F.groupby(["venue", "hour"]).sym.transform("count") >= w.CAP_FILLS
    F["wave"] = wave.to_numpy()
    rows = []
    for r in F.itertuples():
        a = None
        if r.venue == "bitget":
            nm = w.bitget_name(r.sym, listed)
            a = m1.get(("bitget", nm, r.H)) if nm else None
        if a is None or len(a) < 186:
            a = m1.get(("binance", r.sym, r.H))
        if a is None or len(a) < 186:
            continue
        lo, cl = a[:, 3], a[:, 4]
        j = 1 + int(r.minute)                     # index of the fill minute (index 0 = H - 1 min)
        f = float(r.fill)
        ex = {"E0": 60, "E1": j + 120, "E2": 180}
        rec = dict(venue=r.venue, t=r.t, hour=r.hour, wave=r.wave)
        for k, i in ex.items():
            rec[k] = cl[i] / f - 1 - w.COST
            rec[k + "_low"] = lo[j:i + 1].min() / f - 1
        pick = "E1" if r.wave else "E0"
        rec["E3"], rec["E3_low"] = rec[pick], rec[pick + "_low"]
        rows.append(rec)
    R = pd.DataFrame(rows)
    print(f"{len(R)} kept fills with bars to +3h (of {len(F)}); waves (cap hit): {R.wave.mean()*100:.0f}% of fills\n")
    print(f"{'':<9}{'exit':<6}{'per fill: all':>14}{'tune':>8}{'hold':>8}{'waves':>8}{'others':>8}"
          f"{'  $300 ->':>10}{'worst mo':>10}{'worst paper loss while held':>30}")
    grid = pd.date_range("2022-01-01", "2026-09-21", freq="D")
    for v in w.VENUES:
        x = R[R.venue == v]
        for k in ("E0", "E1", "E2", "E3"):
            tu, ho = x[x.t < CUT], x[x.t >= CUT]
            eq, pts = 300.0, []
            for t, g in x.groupby("t", sort=True):
                eq += eq / w.TOP_N * g[k].sum()
                pts.append((t, eq))
            c = pd.Series([p[1] for p in pts], index=[p[0] for p in pts])
            c = c[~c.index.duplicated(keep="last")].resample("D").last().reindex(grid).ffill().fillna(300.0)
            me = c.resample("ME").last().pct_change().dropna()
            paper = x.groupby("hour")[k + "_low"].sum() / w.TOP_N
            print(f"{v.upper():<9}{k:<6}{x[k].mean()*100:>+13.2f}%{tu[k].mean()*100:>+7.2f}%{ho[k].mean()*100:>+7.2f}%"
                  f"{x[x.wave][k].mean()*100:>+7.2f}%{x[~x.wave][k].mean()*100:>+7.2f}%${c.iloc[-1]:>8,.0f}"
                  f"{me.min()*100:>+9.1f}%{paper.min()*100:>+17.1f}% ({paper.idxmin()})")
        print()
    d = R.E1 - R.E0
    print(f"E1 - E0 per fill: {d.mean()*100:+.2f} (se {d.std()/np.sqrt(len(d))*100:.2f}); by year: " +
          "  ".join(f"{y}: {g.mean()*100:+.2f}" for y, g in d.groupby(R.t.dt.year)))


if __name__ == "__main__":
    main()

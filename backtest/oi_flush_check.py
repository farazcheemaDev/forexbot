"""POST-HOC CHECKS on oi_flush.py's lead (2026-11-10) - is the flush more than 'a bigger drop'?

oi_flush.py: after an 8% day, coins whose open interest fell 10%+ bounced +1.05% / +2.85% a trade (tune / holdout),
+1.26% / +2.24% more than coins whose open interest rose.  Not a pass (t 1.4 / 2.0).  Before believing even the lead:
  C1  POOLED: all FLUSH trades, day-clustered t; trades a year.
  C2  SAME-SIZE DROPS: a flush comes with a bigger fall, and bigger falls bounce more (the capitulation book).  Within
      each third of the drop size, FLUSH against the rest.  Stated before the run: the flush premium survives inside
      drop thirds on both halves (50%).
  C3  PLATEAU: the flush line at -5 / -7.5 / -10 / -12.5 / -15% - the result should rise with the depth, not peak at one.
  C4  SAME DAY: on days with both a FLUSH and a non-FLUSH event, the within-day difference (the market's bounce that day
      is common to both).
  C5  WITHOUT THE BIGGEST DAYS: FLUSH without its 5 best days.
Everything here was chosen after looking at oi_flush.txt.

    python -m backtest.oi_flush_check
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import oi_flush as of  # noqa: E402

LOG = ROOT / "logs" / "oi_flush_check.txt"


def build():
    rows = []
    for f in sorted((of.DATA / "metrics").glob("*.csv.gz")):
        sym = f.name.split(".")[0]
        rows += of.events(of.load_hourly(f), sym, of.load_funding(sym))
    E = pd.DataFrame(rows).sort_values("t").reset_index(drop=True)
    E["g"] = E["doi"].map(of.group)
    cut = E["t"].iloc[int(len(E) * 0.6)]
    E["half"] = np.where(E["t"] < cut, "tune", "holdout")
    return E


def fmt(w):
    m, t, n, g = of.clustered(w["net"], w["day"])
    return f"n {n:>4} days {g:>3} net {m * 100:+.2f}% t {t:+.2f}" if n else "n    0"


def main():
    E = build()
    F = E[E.g == "FLUSH"]
    yrs = (E.t.max() - E.t.min()).days / 365.25
    L = [f"backtest/oi_flush_check.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC (post hoc)", "",
         f"C1 POOLED FLUSH: {fmt(F)}; {len(F) / yrs:.0f} trades a year on 13 coins; won {(F.net > 0).mean() * 100:.0f}%, "
         f"hit +5% {(F.why == 'target').mean() * 100:.0f}%, average loser {F[F.net <= 0].net.mean() * 100:+.1f}%, worst {F.net.min() * 100:+.1f}%, "
         f"median hold {F.hours.median():.0f} h",
         f"   median drop: FLUSH {F['drop'].median() * 100:.1f}%  MID {E[E.g == 'MID']['drop'].median() * 100:.1f}%  BUILD {E[E.g == 'BUILD']['drop'].median() * 100:.1f}%", "",
         "C2 SAME-SIZE DROPS (thirds of the drop over all events): FLUSH | the rest"]
    q = E["drop"].quantile([1 / 3, 2 / 3]).to_numpy()
    E["dq"] = np.where(E["drop"] <= q[0], "deep", np.where(E["drop"] <= q[1], "middle", "shallow"))
    for dq in ("shallow", "middle", "deep"):
        for half in ("tune", "holdout"):
            w = E[(E.dq == dq) & (E.half == half)]
            a, b = w[w.g == "FLUSH"], w[w.g != "FLUSH"]
            L.append(f"   {dq:<8}{half:>8}: {fmt(a)}  |  {fmt(b)}")
    L += ["", "C3 PLATEAU (open interest down at least ...):"]
    for th in (-0.05, -0.075, -0.10, -0.125, -0.15):
        L.append(f"   {th * 100:>6.1f}%  tune {fmt(E[(E.doi <= th) & (E.half == 'tune')])}   holdout {fmt(E[(E.doi <= th) & (E.half == 'holdout')])}")
    L += ["", "C4 SAME DAY (days with both kinds): mean of the day's FLUSH trades minus the day's others"]
    for half in ("tune", "holdout"):
        w = E[E.half == half]
        d = w.groupby(["day", w.g == "FLUSH"])["net"].mean().unstack()
        d = d.dropna()
        diff = d[True] - d[False]
        t = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if len(diff) > 2 else np.nan
        L.append(f"   {half:>8}: {len(diff)} days, {diff.mean() * 100:+.2f}% (t {t:+.2f}), FLUSH better on {(diff > 0).mean() * 100:.0f}% of them")
    L += ["", "C5 WITHOUT THE 5 BEST DAYS (by summed FLUSH result):"]
    for half in ("tune", "holdout"):
        w = F[F.half == half]
        best = w.groupby("day")["net"].sum().sort_values(ascending=False).index[:5]
        L.append(f"   {half:>8}: {fmt(w[~w.day.isin(best)])}")
    L += ["", "BY COIN (FLUSH, n, net): " + "  ".join(f"{s[:-4]} {len(g)} {g.net.mean() * 100:+.1f}%" for s, g in F.groupby("sym"))]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

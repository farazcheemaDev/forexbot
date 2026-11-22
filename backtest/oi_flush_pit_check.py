"""POST-HOC CHECKS on oi_flush_pit.py (2026-11-12) - the same checks oi_flush_check.py ran on the 13 coins, chosen before
looking at the PIT result, so a FLUSH number is not read alone:
  C1  POOLED FLUSH (both halves), trades a year, losers, hold.
  C2  SAME-SIZE DROPS: within each third of the drop size, FLUSH against the rest (a flush comes with a bigger fall,
      and bigger falls bounce more).
  C3  DOSE-RESPONSE: open interest down at least 5 / 7.5 / 10 / 12.5 / 15%.
  C4  SAME DAY: on days with both kinds, the day's FLUSH trades minus the day's others.
  C5  WITHOUT THE 5 BEST DAYS per half.
  C6  BY COIN SIZE: the 13 coins of oi_flush.py against the rest (is the 13-coin result a survivor effect?).

    python -m backtest.oi_flush_pit_check
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import oi_flush as of  # noqa: E402
from backtest import oi_flush_pit as op  # noqa: E402

LOG = ROOT / "logs" / "oi_flush_pit_check.txt"
THIRTEEN = {f.name.split(".")[0] for f in (ROOT / "strategy_analysis" / "data" / "metrics").glob("*.csv.gz")}


def fmt(w):
    m, t, n, g = of.clustered(w["net"], w["day"])
    return f"n {n:>4} days {g:>4} net {m * 100:+.2f}% t {t:+.2f}" if n > 2 else f"n {n:>4}"


def main():
    E = op.attach_oi(op.build_events())
    E, cut = op.split_halves(E)
    S = E[E.g != "NO_OI"].copy()
    F = S[S.g == "FLUSH"]
    yrs = (S.t_ev.max() - S.t_ev.min()).days / 365.25
    L = [f"backtest/oi_flush_pit_check.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC (post hoc)", "",
         f"C1 POOLED FLUSH: {fmt(F)}; {len(F) / yrs:.0f} trades a year; won {(F.net > 0).mean() * 100:.0f}%, hit +5% "
         f"{(F.why == 'target').mean() * 100:.0f}%, average loser {F[F.net <= 0].net.mean() * 100:+.1f}%, worst {F.net.min() * 100:+.1f}%, "
         f"median hold {F.hours.median():.0f} h",
         f"   median drop: FLUSH {F['drop'].median() * 100:.1f}%  MID {S[S.g == 'MID']['drop'].median() * 100:.1f}%  "
         f"BUILD {S[S.g == 'BUILD']['drop'].median() * 100:.1f}%", "",
         "C2 SAME-SIZE DROPS (thirds of the drop over the split events): FLUSH | the rest"]
    q = S["drop"].quantile([1 / 3, 2 / 3]).to_numpy()
    S["dq"] = np.where(S["drop"] <= q[0], "deep", np.where(S["drop"] <= q[1], "middle", "shallow"))
    for dq in ("shallow", "middle", "deep"):
        for half in ("tune", "holdout"):
            w = S[(S.dq == dq) & (S.half == half)]
            L.append(f"   {dq:<8}{half:>8}: {fmt(w[w.g == 'FLUSH'])}  |  {fmt(w[w.g != 'FLUSH'])}")
    L += ["", "C3 DOSE-RESPONSE (open interest down at least ...):"]
    for th in (-0.05, -0.075, -0.10, -0.125, -0.15):
        L.append(f"   {th * 100:>6.1f}%  tune {fmt(S[(S.doi <= th) & (S.half == 'tune')])}   holdout {fmt(S[(S.doi <= th) & (S.half == 'holdout')])}")
    L += ["", "C4 SAME DAY (days with both kinds): the day's FLUSH trades minus the day's others"]
    for half in ("tune", "holdout"):
        w = S[S.half == half]
        d = w.groupby(["day", w.g == "FLUSH"])["net"].mean().unstack().dropna()
        if True in d and False in d and len(d) > 2:
            diff = d[True] - d[False]
            t = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff)))
            L.append(f"   {half:>8}: {len(diff)} days, {diff.mean() * 100:+.2f}% (t {t:+.2f}), FLUSH better on {(diff > 0).mean() * 100:.0f}% of them")
    L += ["", "C5 WITHOUT THE 5 BEST DAYS (by summed FLUSH result):"]
    for half in ("tune", "holdout"):
        w = F[F.half == half]
        best = w.groupby("day")["net"].sum().sort_values(ascending=False).index[:5]
        L.append(f"   {half:>8}: {fmt(w[~w.day.isin(best)])}   (the 5 days: " + ", ".join(f"{d:%Y-%m-%d}" for d in best) + ")")
    L += ["", "C6 THE 13 COINS OF oi_flush.py AGAINST THE REST (FLUSH | BUILD):"]
    for lab, m in (("the 13 coins", S.sym.isin(THIRTEEN)), ("other coins", ~S.sym.isin(THIRTEEN))):
        for half in ("tune", "holdout"):
            w = S[m & (S.half == half)]
            L.append(f"   {lab:<13}{half:>8}: {fmt(w[w.g == 'FLUSH'])}  |  {fmt(w[w.g == 'BUILD'])}")
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

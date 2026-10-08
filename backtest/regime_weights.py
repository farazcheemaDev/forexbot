"""REGIME WEIGHTS ACROSS THE WHOLE MACHINE, without look-ahead (2026-10-08).

machine_combos.py's variant H (weights fixed in advance by the BTC 50-day-trend label: bull trend/daily 1, MN 0.5; chop
trend/daily 0.5, MN 1.5; bear trend/daily 0.5, MN 1, sleeve 1.5, capitulation 1.5) beat the line by +45% / +70%, then
+33% / +56% once MN and the capitulation book were weighted by the label at their ENTRY. It still had a leak: the trend
book (dd_fixes.sim) books each unit's P&L when it CLOSES, so weighting its daily series by the label of the close day is
sizing a position after its outcome is known. Here the trend book is re-simulated with the weight applied AT ENTRY
(size_fn = 21-day anchor x the trend weight of the label at the entry time), gains shrunk for hindsight as machine.py.
Everything else as machine_combos.py (rotating MN day with the +50% short exit, daily boundary, capitulation phase).

REGISTERED BEFORE RUNNING: with the trend book weighted at entry, H's edge over the line shrinks to under +10% on at
least one span (most of +33% / +56% was the leak), i.e. it fails or barely passes.

RESULT (2026-10-08, logs/regime_weights.txt): with the trend book weighted AT ENTRY, H typical $2,328 vs the line's
    $2,651 on 6 years (-12%: FAILS), +57% on the last 2 - most of machine_combos.py's +33% / +56% was the leak.
    Prediction (fails or barely passes) - right.

    python -m backtest.regime_weights
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.dd_fixes as D  # noqa: E402
import backtest.machine_combos as mc  # noqa: E402
from backtest import pair_lab as pl  # noqa: E402
from backtest.bar_phase import rows_for_phase  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.machine import CUT, summary  # noqa: E402
from backtest.worst_month import TCACHE  # noqa: E402

LOG = ROOT / "logs" / "regime_weights.txt"
TW = {"bull": 1.0, "chop": 0.5, "bear": 0.5}


def trend_at_entry():
    f = ROOT / "logs" / "daily_combos_cache" / "trend_regime_entry.pkl"
    if f.exists():
        return pickle.loads(f.read_bytes())
    cache = pickle.loads(TCACHE.read_bytes())
    bear = regimes()[1000]
    bn = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    bv = bear.to_numpy(bool)
    trows = D.decompose(rows_for_phase(0, tight=True, time_stop=(100, 2.0), max_units=7))
    reg = pl.btc_regime_daily()
    rn = pd.DatetimeIndex(reg.index).as_unit("ns").asi8
    rv = reg.to_numpy()
    anc = D.anchor(21)

    def size(t, eq, ctx):
        lab = rv[max(np.searchsorted(rn, pd.Timestamp(t).value, side="right") - 1, 0)]
        return anc(t, eq, ctx) * TW.get(lab, 1.0)

    out = {}
    for sd in mc.SEEDS:
        r = D.sim(trows, bn, bv, sd, lev=9.0, size_fn=size).pct_change().fillna(0.0)
        s = cache[("shrink", sd)]
        out[sd] = pd.Series(np.where(r > 0, s * r, r), index=r.index)
        print(f"  trend at entry, ordering {sd} done", flush=True)
    f.write_bytes(pickle.dumps(out))
    return out


def main():
    P = mc.parts()
    T = trend_at_entry()
    reg = pl.btc_regime_daily()
    RW = {"bull": dict(daily=1, mn_safe=0.5), "chop": dict(daily=0.5, mn_safe=1.5),
          "bear": dict(daily=0.5, mn_safe=1, sleeve=1.5, capit2=1.5)}
    base_w = dict(mn_safe=1, sleeve=1, bids=1, daily=1, capit2=1)
    lags = {"mn_safe": 7, "capit2": 2}

    def build(kind, k=1.0):
        xs = []
        for sd in mc.SEEDS:
            b = P[sd]
            if kind == "C":
                x = b.trend + b.mn_safe + b.sleeve + b.bids
            elif kind == "E":
                x = b.trend + b.mn_safe + b.sleeve + b.bids + b.daily + b.capit2
            else:
                lab0 = reg.reindex(b.index, method="ffill").fillna("chop")
                x = T[sd].reindex(b.index).fillna(0.0)
                for p_ in ("mn_safe", "sleeve", "bids", "daily", "capit2"):
                    lab = lab0.shift(lags.get(p_, 0)).fillna("chop").to_numpy()
                    wt = np.array([RW.get(l_, {}).get(p_, base_w[p_]) for l_ in lab])
                    x = x + wt * b[p_]
            xs.append(k * x)
        return xs

    spans = (("all 6 years", None), ("last 2 years", CUT))
    front = {sp: [] for sp, _ in spans}
    for k in np.round(np.arange(0.4, 1.81, 0.05), 2):
        xs = build("C", k)
        for sp, t0 in spans:
            s = summary(xs, t0)
            front[sp].append((s["wm"], s["typ"]))
    lines = [f"backtest/regime_weights.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; as machine_combos.py, the trend book weighted "
             f"AT ENTRY", ""]
    for sp, t0 in spans:
        f = sorted(front[sp])
        for nm, kind in (("C v2 safe", "C"), ("E (C + daily + capitulation improved)", "E"), ("H E with regime weights, no leak", "H")):
            s = summary(build(kind), t0)
            ref = float(np.interp(s["wm"], [a for a, _ in f], [b for _, b in f]))
            lines.append(f"  {sp:12} {nm:40} ${s['typ']:>6,.0f} / ${s['bad']:>6,.0f} / ${s['worst']:>5,.0f} | worst month "
                         f"{s['wm']:+.1f}% | fall {s['dd']:.0f}% | up {s['up']:.0f}% || line ${ref:,.0f} ({(s['typ'] / ref - 1) * 100:+.0f}%)")
            print(lines[-1], flush=True)
    LOG.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

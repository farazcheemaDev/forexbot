"""HOW BIG SHOULD THE TREND BOOK BE INSIDE THE 9-BOOK MACHINE? - the whole distribution, not only the typical year

chop_switch.py --control (2026-10-18) ran the trend book at a constant 0.6 / 0.7 / 0.8 / 0.9x inside the 9-book machine:
the TYPICAL 12 months on $300 barely moves (tune $3,575..$3,927, holdout $9,416..$9,666) while the biggest fall drops
45/49% -> 37/43%. The trend book is what makes the huge months, so a typical-year column cannot see what shrinking it
costs. This file reads the rest: the good (75th) and great (90th) years, the AVERAGE year, months by market type.
Reuses chop_switch.py's cached trend books (logs/chop_switch_const.pkl, chop_switch_trend.pkl), adds 0.5x.

REGISTERED BEFORE THE RUN (2026-10-18)
    Z1 at 0.7x the typical SIDEWAYS month is -0.5% or better (1.0x: -2.1%).
    Z2 at 0.7x the 75th-percentile year is at least 15% lower than at 1.0x on both halves.
    Z3 at 0.7x the AVERAGE year is at least 20% lower than at 1.0x on both halves.

RESULT (2026-10-18, logs/trend_size.txt) - Z1 RIGHT, Z2 / Z3 WRONG (the cost shows on ONE half). Shrinking the trend
book fills the sideways gap: typical sideways month -2.1% (1.0x) -> 0.0% (0.8x) -> +1.1% (0.7x) -> +3.6% (0.5x), bad
years better, falls 45/49% -> 38/45% (0.7x, chop_switch --control). The typical year barely moves (0.7x $3,701 / $9,666 vs
$3,927 / $9,416). The price is the TOP of the 2020-24 half, the one holding the 2021 bull: 0.7x good year -25%, great year
-37%, average -38%; on the 2024-26 half almost nothing (good +7%, great -16%, average -3%). A size choice between upside
in a 2021-type bull and steadier sideways months - the user's call (doc 22: a change to the bot).

    python -m backtest.trend_size
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "trend_size.txt"
CAP = 300.0


def years(daily: list, t0=None, t1=None) -> np.ndarray:
    """Every 12-month window's end / start (month-end equity), all orderings pooled - machine.summary's windows."""
    out = []
    for x in daily:
        y = x[(x.index >= t0) if t0 is not None else slice(None)]
        y = y[y.index < t1] if t1 is not None else y
        me = (1 + y).cumprod().resample("ME").last()
        if len(me) > 12:
            out.append((me.shift(-12) / me).dropna().to_numpy())
    return np.concatenate(out)


def main():
    from backtest import machine_combos as mc
    from backtest.all_books import machine_books, ndx_dip, news_book
    from backtest.chop_gap import NAMES, month_labels, monthly
    from backtest.chop_switch import btc_signals, machine_daily, trend_books
    from backtest.machine import CUT
    _, _, reg, _ = btc_signals()
    T = pickle.loads((ROOT / "logs" / "chop_switch_const.pkl").read_bytes())
    T["x1.0"] = pickle.loads((ROOT / "logs" / "chop_switch_trend.pkl").read_bytes())["G0"]
    T.update(trend_books({"x0.5": lambda r, t, ctx: 0.5}, ROOT / "logs" / "trend_size_x05.pkl"))
    M = machine_books()
    nw, nd = news_book(), ndx_dip()
    lab = month_labels(reg)
    lines = [f"backtest/trend_size.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the 9-book machine, the trend book at a "
             f"constant size; $300, 12-month windows, 10 orderings pooled; trend gains shrunk, the rest raw", "",
             f"   {'size':<6}{'half':>8}{'bad 25%':>9}{'typical':>9}{'good 75%':>10}{'great 90%':>11}{'AVERAGE':>9}"
             f"{'  typical month: bull':>22}{'chop':>7}{'bear':>7}"]
    R = {}
    for name in ("x0.5", "x0.6", "x0.7", "x0.8", "x0.9", "x1.0"):
        daily = machine_daily(T[name], M, nw, nd)
        P = []
        for sd, x in zip(mc.SEEDS, M):
            d = pd.DataFrame({nm: x[src] for src, nm in NAMES.items()})
            d["trend"] = T[name][sd].reindex(x.index).fillna(0.0)
            d["news"], d["ndx"] = nw.reindex(x.index).fillna(0.0), nd.reindex(x.index).fillna(0.0)
            m = monthly(d).iloc[1:-1]
            m["reg"] = lab.reindex(m.index).to_numpy()
            P.append(m)
        P = pd.concat(P).dropna(subset=["reg"])
        typ = {g: P[P.reg == g].account.median() for g in ("bull", "chop", "bear")}
        for half, w in (("tune", years(daily, None, CUT)), ("holdout", years(daily, CUT, None))):
            q = {p: CAP * np.percentile(w, p) for p in (25, 50, 75, 90)}
            R[(name, half)] = dict(q, mean=CAP * w.mean(), **{f"m_{g}": v for g, v in typ.items()})
            lines.append(f"   {name:<6}{half:>8} ${q[25]:>7,.0f} ${q[50]:>7,.0f} ${q[75]:>8,.0f} ${q[90]:>9,.0f} "
                         f"${CAP * w.mean():>7,.0f}{typ['bull'] * 100:>+19.1f}%{typ['chop'] * 100:>+6.1f}%{typ['bear'] * 100:>+6.1f}%")
    z1 = R[("x0.7", "tune")]["m_chop"] >= -0.005
    z2 = all(R[("x0.7", h)][75] <= 0.85 * R[("x1.0", h)][75] for h in ("tune", "holdout"))
    z3 = all(R[("x0.7", h)]["mean"] <= 0.80 * R[("x1.0", h)]["mean"] for h in ("tune", "holdout"))
    lines += ["", "REGISTERED PREDICTIONS",
              f"  Z1 0.7x typical sideways month {R[('x0.7', 'tune')]['m_chop'] * 100:+.1f}% (>= -0.5) -> {'RIGHT' if z1 else 'WRONG'}",
              f"  Z2 0.7x 75th-percentile year vs 1.0x: " + ", ".join(
                  f"{h} {R[('x0.7', h)][75] / R[('x1.0', h)][75] - 1:+.0%}" for h in ("tune", "holdout"))
              + f" (<= -15% both) -> {'RIGHT' if z2 else 'WRONG'}",
              f"  Z3 0.7x average year vs 1.0x: " + ", ".join(
                  f"{h} {R[('x0.7', h)]['mean'] / R[('x1.0', h)]['mean'] - 1:+.0%}" for h in ("tune", "holdout"))
              + f" (<= -20% both) -> {'RIGHT' if z3 else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

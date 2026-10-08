"""THE ONE REVIVAL FROM THE GRAVEYARD AUDIT, CHECKED THE WAY EVERYTHING ELSE WAS (2026-10-09).

moderate_retests.py --vwap: "VWAP reversion" (doc 02's first table, PF 0.46-0.85, early, no universe) re-tested on the
point-in-time top-40 - long when a DAILY close sits 2 ATR(14) under its 20-day volume-weighted average price, out at
the next open after a close back at or above it, or after 12 days; 12bp + funding - made +2.65% / +2.25% a trade on
the tune / holdout halves against -2.78% / -3.36% for a random bar of the same coin and month with the same exits
(excess t by day +3.6 / +3.9, 879 / 663 trades). On 4h bars it was dead on the holdout. A good result is a bug until
shown otherwise, so here it gets the checks the capitulation and daily books got:
    1. all 3 day boundaries (00 / 08 / 16 UTC) - bar phase;
    2. an ACCOUNT: 8 slots of an eighth, 1x, marked to market, 10 random same-day orders (daily_combos.py's machinery),
       tune / holdout CAGR, biggest fall, worst month;
    3. by year;
    4. overlap with the capitulation book (the same coins on the same days?) and the monthly correlation with it and
       with the daily trend book;
    5. entry thresholds 1.5 / 2.5 ATR (a plateau or a peak?).

REGISTERED BEFORE RUNNING: positive a trade on both halves at all 3 boundaries; the 1x account positive on both halves
but with a fall of 30-50% (it buys falling coins); 2022 the worst year; monthly correlation with the capitulation book
+0.3..+0.6 (the same washouts, slower); the 1.5 / 2.5 thresholds both positive (a plateau).

    python -m backtest.vwap_daily
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import capit_combos as cc  # noqa: E402
from backtest import daily_combos as dc  # noqa: E402

LOG = ROOT / "logs" / "vwap_daily.txt"
H = dc.HOLDOUT


def trades(off, z=2.0):
    PN = dc.panel(off)
    rows = []
    for s, P in PN.items():
        o, c, v, atr, fc, t = P["o"], P["c"], P["v"], P["atr"], P["fc"], P["t"]
        pv = pd.Series(c * v).rolling(20).sum().to_numpy()
        vv = pd.Series(v).rolling(20).sum().to_numpy()
        vw = pv / np.where(vv > 0, vv, np.nan)
        sig = np.nan_to_num((c - vw) / atr <= -z).astype(bool)
        ym, el = P["ym"], P["el"]
        n = len(c)
        free = 0
        for i in np.flatnonzero(sig):
            if i < 60 or i < free or i + 14 >= n or ym[i] not in el:
                continue
            e = o[i + 1]
            worst = 0.0
            for j in range(i + 1, i + 13):
                worst = max(worst, 1 - P["l"][j] / e)
                if c[j] >= vw[j] or j == i + 12:
                    x = o[j + 1]
                    net = x / e - 1 - dc.FEE - (fc[j + 1] - fc[i + 1]) / e
                    rows.append((s, t[i + 1], t[j + 1], net, worst, [(t[i + 1], e)], "vwap", 0.0))
                    free = j + 1
                    break
    T = pd.DataFrame(rows, columns=["coin", "t_in", "t_out", "net", "worst", "units", "why", "score"])
    return T


def acct(T, off):
    res = [dc.stats(dc.curve(T, dc.allocate(T, s), off)) for s in dc.SEEDS]
    return {k: np.mean([r[k] for r in res]) for k in res[0]}


def main():
    lines = [f"backtest/vwap_daily.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; PIT top-40 daily, long 2 ATR under VWAP(20), out at "
             f"VWAP or 12 days; 12bp + funding; account 8 slots 1x marked to market, 10 orders", ""]
    allT = {}
    lines.append("1-2. BY DAY BOUNDARY: trades, per trade tune / holdout, 1x account CAGR tune / holdout, fall, worst month")
    for off in dc.PHASES:
        T = trades(off)
        allT[off] = T
        a = acct(T, off)
        lines.append(f"  {off:02d} UTC: {len(T)} trades | {T.net[T.t_in < H].mean() * 100:+.2f}% / {T.net[T.t_in >= H].mean() * 100:+.2f}% "
                     f"a trade | account {a['tune'] * 100:+.0f}% / {a['hold'] * 100:+.0f}% a year, fall {a['fall'] * 100:.0f}%, "
                     f"worst month {a['wm'] * 100:+.1f}%")
        print(lines[-1], flush=True)
    lines.append("")
    T0 = allT[0]
    by = T0.groupby(pd.DatetimeIndex(T0.t_in).year).net.agg(["size", "mean"])
    lines.append("3. BY YEAR (00 UTC): " + "  ".join(f"{y}: {r['size']} trades {r['mean'] * 100:+.1f}%" for y, r in by.iterrows()))
    lines.append("")
    C = cc.gen(0, cc.BASE)
    cd = set(zip(C.coin, pd.DatetimeIndex(C.t_in).floor("D")))
    vd = set(zip(T0.coin, pd.DatetimeIndex(T0.t_in).floor("D")))
    near = sum(1 for k in vd if any((k[0], k[1] + pd.Timedelta(days=dd)) in cd for dd in (-2, -1, 0, 1, 2)))
    mo = lambda T, off: dc.curve(T, dc.allocate(T, 0), off).resample("ME").last().pct_change().dropna()  # noqa: E731
    vm = mo(T0, 0)
    dm = mo(dc.gen(0, dc.BASE), 0)
    cm = cc.curve(C, dc.allocate(C.assign(units=None), 0)).resample("ME").last().pct_change().dropna()
    lines.append(f"4. OVERLAP: {near} of {len(vd)} VWAP trades are within 2 days of a capitulation trade on the same coin; "
                 f"monthly correlation with the capitulation book {vm.corr(cm):+.2f}, with the daily trend book {vm.corr(dm):+.2f}")
    lines.append("")
    lines.append("5. THRESHOLD (00 UTC): per trade tune / holdout, account CAGR tune / holdout, fall")
    for z in (1.5, 2.5):
        T = trades(0, z)
        a = acct(T, 0)
        lines.append(f"  {z} ATR under: {len(T)} trades | {T.net[T.t_in < H].mean() * 100:+.2f}% / {T.net[T.t_in >= H].mean() * 100:+.2f}% "
                     f"| account {a['tune'] * 100:+.0f}% / {a['hold'] * 100:+.0f}%, fall {a['fall'] * 100:.0f}%")
        print(lines[-1], flush=True)
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")


if __name__ == "__main__":
    main()

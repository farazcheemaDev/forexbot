"""THE 1-HOUR CAPITULATION BUY x TODAY'S TWO FIXES - more frequency? (2026-10-08)

breadth_events.py killed the 1h version of the capitulation buy (RSI(14) cross under 20, volume > 2x, >= 5 top-40
coins in 24h): tune +1.1..+1.6% a trade, HOLDOUT -0.17..+0.34%. capit_combos.py / capit_stack.py then found two fixes
for the 4h book that pass in all 4 phases - only coins down >= 10% over 24h, bought with a limit 2% under the signal
close - and capit_volume.py showed the volume rule is redundant once the 10% drop is required. Never combined with
the 1h signal, which fires ~3x as often (the user asked for more frequency).
Same exits in clock time as the 4h book: +5% intrabar (not in a limit's fill bar), out at the next open once a close
24h or more after the signal is not above the entry, 7-day cap; 12bp + funding; PIT top-40, dead coins in. Limits live
4 hours (one 4h bar). Account: 8 slots of an eighth, 1x, 10 random same-hour orders; P&L at the close.

REGISTERED BEFORE RUNNING: the 1h base reproduces breadth_events' sign (holdout per trade within +-0.5%); the fixes lift
the 1h holdout per trade above +2% with 1.5-3x the 4h improved book's trades; the 1h improved book's 1x account beats
the 4h improved book's on the holdout but not on the tune half (it is the post-hoc book carried to a new timeframe).

RESULT (2026-10-08, logs/capit_1h.txt): the 1h base reproduces the kill (holdout -0.08% a trade). With the fixes:
    89 trades a year (~3x the 4h book), +2.83% / +1.24% a trade, 1x CAGR +21% / +5%, fall 15% - against the 4h
    improved book's ~30 a year, +3.6..+4.2% / +3.5..+4.8% a trade, +9..+11% / +13..+15%, falls 1-8%. More frequency
    again means less edge. Predictions: base sign - right; holdout above +2% a trade - WRONG (+1.24%); 1.5-3x the
    trades - right; beats the 4h book on the holdout - WRONG.

    python -m backtest.capit_1h

RE-RUN 2026-10-09 on the FIXED loader (capitulation_wide.halt_cut): until then a data-archive hole cut 51 coins (XRP, SOL,
    LTC ...) at 2022-02-25. Where a RESULT above differs from this file's log, THE LOG IS CURRENT - doc 02, "The archive-hole bug".
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
from backtest import pair_lab as pl  # noqa: E402
from backtest.capitulation_wide import funding_cum  # noqa: E402
from backtest.rsi_factors import rsi14  # noqa: E402

LOG = ROOT / "logs" / "capit_1h.txt"
H1 = np.timedelta64(1, "h")
_P: dict = {}


def panel1():
    if _P:
        return _P
    for s, h in pl.hourly_all().items():
        if len(h) < 1200:
            continue
        c = h.close.to_numpy(float)
        v = h.qvol.to_numpy(float)
        _P[s] = dict(o=h.open.to_numpy(np.float32).astype(float), h=h.high.to_numpy(float), l=h.low.to_numpy(float), c=c,
                     r=rsi14(c), v=v, vavg=pd.Series(v).rolling(20).mean().shift(1).to_numpy(),
                     t=h.time.to_numpy("datetime64[ns]"), fc=funding_cum(s, h.time.to_numpy(), h),
                     ym=h.time.dt.strftime("%Y-%m").to_numpy(), el=pl.universe()[s])
    return _P


def signals(vmin):
    PN = panel1()
    rows = []
    for s, P in PN.items():
        r, v, c = P["r"], P["v"], P["c"]
        sig = np.r_[False, (r[:-1] >= 20) & (r[1:] < 20)] & (v > vmin * P["vavg"])
        sig[:1000] = False
        for i in np.flatnonzero(sig):
            if i + 12 < len(r) and P["ym"][i] in P["el"]:
                rows.append((P["t"][i], s, i, c[i] / c[i - 24] - 1))
    S = pd.DataFrame(rows, columns=["t", "coin", "i", "drop24"]).sort_values("t", kind="stable").reset_index(drop=True)
    tt = S.t.to_numpy("datetime64[ns]").astype(np.int64)
    day, lo, br = 24 * 3600 * 10 ** 9, 0, []
    for k in range(len(S)):
        while tt[lo] < tt[k] - day:
            lo += 1
        br.append(S.coin.iloc[lo:np.searchsorted(tt, tt[k], side="right")].nunique())
    S["K"] = br
    return S


def gen(S, limit=None, drop=None):
    PN = panel1()
    S = S[S.K >= 5]
    if drop is not None:
        S = S[S.drop24 <= -drop]
    rows = []
    for s, g in S.groupby("coin"):
        P = PN[s]
        o, l, c, t = P["o"], P["l"], P["c"], P["t"]
        free = 0
        for i in g.i:
            if i < free:
                continue
            if limit is None:
                ib, e, lf = i + 1, o[i + 1], False
            else:
                lim = c[i] * (1 - limit)
                ib = next((j for j in range(i + 1, min(i + 5, len(c) - 3)) if l[j] <= lim), None)
                if ib is None:
                    free = i + 5
                    continue
                e, lf = min(o[ib], lim), o[ib] > lim
            j, net, worst, jx, after = cc.exit_tp(i, ib, e, P, P["fc"], nw=24, cap=168, limit_fill=lf)
            rows.append((s, t[ib], t[min(jx, len(t) - 1)] + (H1 if after else np.timedelta64(0, "h")), net, worst, 0.0))
            free = j + 1
    return pd.DataFrame(rows, columns=["coin", "t_in", "t_out", "net", "worst", "score"])


def account(T):
    out = [dc.stats(cc.curve(T, dc.allocate(T.assign(units=None), sd))) for sd in cc.SEEDS]
    return {k: np.mean([o[k] for o in out]) for k in out[0]}


def main():
    H = cc.HOLDOUT
    S2, S0 = signals(2.0), signals(0.0)
    lines = [f"backtest/capit_1h.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; 1h capitulation, PIT top-40, 8 slots 1x, 10 orders"]
    V = {"1h base (vol > 2x, open entry)": gen(S2), "1h + coin -10% + limit -2%": gen(S2, limit=0.02, drop=0.10),
         "1h + coin -10% + limit -2%, no volume rule": gen(S0, limit=0.02, drop=0.10)}
    for off in (0, 60, 120, 180):
        V[f"4h improved, phase +{off}m (reference)"] = cc.gen(off, dict(cc.BASE, filt=lambda S: S.drop24 <= -0.10,
                                                                         entry=("limit", 0.02, 1)))
    yrs = 6.5
    for nm, T in V.items():
        a = account(T)
        lines.append(f"  {nm:44} {len(T) / yrs:5.0f}/yr | per trade {T.net[T.t_in < H].mean() * 100:+.2f}% / "
                     f"{T.net[T.t_in >= H].mean() * 100:+.2f}% | 1x CAGR {a['tune'] * 100:+.1f}% / {a['hold'] * 100:+.1f}% | "
                     f"fall {a['fall'] * 100:.0f}% | worst month {a['wm'] * 100:+.1f}%")
        print(lines[-1], flush=True)
    LOG.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

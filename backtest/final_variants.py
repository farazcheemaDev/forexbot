"""THE LAST THREE DIMENSIONS - stop width, time stop, and a CAUSAL entry pullback.

  1. STOP WIDTH. Every test in this project uses a 2xATR stop = 1R. It was fixed early and
     never re-swept on the deployed pyramid + blend + gate. A wider stop survives noise but
     makes each unit smaller; a tighter one does the reverse.
  2. TIME STOP. Never tested here: close a position that has gone nowhere after N bars. The
     giveback work showed positions peaking at 5-50R close NEGATIVE on the median, so cutting
     the ones that never get going is at least arguable.
  3. ENTRY ON A PULLBACK, STRICTLY CAUSAL. The ADD version of this was retracted the same day
     it was found because it armed on a bar's high and filled at that bar's low. Here the
     ENTRY limit is placed from the SIGNAL bar's close and can only fill on a LATER bar, so
     no intrabar ordering is assumed. Better entry price, at the cost of missing the signals
     that never look back.

    Deployed engine otherwise unchanged. 12 slots, 1000h gate, compounded by close date,
    3x hindsight haircut, 5 orderings averaged, tune/holdout as bear_date.py.

    python -m backtest.final_variants
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.book_structure import stat  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.engine_variants import shorts_for  # noqa: E402
from backtest.pyramid import FEE_BP  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from backtest.timeframes import resample  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402
from bot.strategies.base import Action  # noqa: E402

RULES = ["1h", "4h", "12h"]
_C: dict = {}


def walk(df, rule, coin, sl_mult=2.0, time_stop=None, entry_pull=None, pull_expire=5):
    """Deployed long pyramid with three optional changes. One position at a time.

    entry_pull P: on a signal, rest a limit P x ATR below the SIGNAL bar's close; it may only
    fill on a LATER bar (no intrabar ordering assumed) and expires after pull_expire bars.
    time_stop (n, r): if the position is older than n bars and its mark is still below r R,
    close it at that bar's close."""
    s = signals(df, "long", "all").to_numpy()
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    a = atr_ind(df, 14).to_numpy(float)
    t = df["time"].to_numpy()
    fee = FEE_BP / 1e4
    out, pos, pend = [], None, None
    for i in range(1, len(df)):
        # ---- pending limit entry (placed on an earlier bar) ----
        if pos is None and pend is not None:
            lim, exp, risk = pend
            if i > exp:
                pend = None
            elif lo[i] <= lim:
                pos = dict(risk=risk, stop=lim - risk, best=lim, bar=i, ents=[lim], nxt=1)
                pend = None
        # ---- new signal ----
        if pos is None and pend is None and s[i] == Action.BUY \
                and np.isfinite(a[i - 1]) and a[i - 1] > 0:
            risk = sl_mult * a[i - 1]
            if entry_pull:
                # limit from the SIGNAL bar's close, fillable only from the NEXT bar on
                pend = (c[i - 1] - entry_pull * a[i - 1], i + pull_expire, risk)
            else:
                pos = dict(risk=risk, stop=o[i] - risk, best=o[i], bar=i, ents=[o[i]], nxt=1)
        if pos is None:
            continue
        r = pos["risk"]; e0 = pos["ents"][0]
        if lo[i] <= pos["stop"]:
            px = pos["stop"]
            R = (sum(px - e for e in pos["ents"]) - sum(fee * e for e in pos["ents"])) / r
            out.append(dict(t0=t[pos["bar"]], t1=t[i], R=float(R), side="long", sf=r / e0,
                            adds=[t[pos["bar"]]], coin=coin, rule=rule))
            pos = None
            continue
        if time_stop:
            nb, minr = time_stop
            if i - pos["bar"] >= nb and (c[i] - e0) / r < minr:
                R = (sum(c[i] - e for e in pos["ents"])
                     - sum(fee * e for e in pos["ents"])) / r
                out.append(dict(t0=t[pos["bar"]], t1=t[i], R=float(R), side="long",
                                sf=r / e0, adds=[t[pos["bar"]]], coin=coin, rule=rule))
                pos = None
                continue
        if len(pos["ents"]) < blend.MAX_UNITS and (h[i] - e0) / r >= pos["nxt"] * blend.ADD_EVERY:
            pos["ents"].append(e0 + pos["nxt"] * blend.ADD_EVERY * r); pos["nxt"] += 1
        pos["best"] = max(pos["best"], h[i])
        cand = pos["best"] - blend.LONG_TRAIL * a[i - 1]
        if (pos["best"] - e0) / r >= blend.BE_AT:
            cand = max(cand, e0)
        if cand > pos["stop"]:
            pos["stop"] = cand
    if pos is not None:
        R = (sum(c[-1] - e for e in pos["ents"]) - sum(fee * e for e in pos["ents"])) / pos["risk"]
        out.append(dict(t0=t[pos["bar"]], t1=t[-1], R=float(R), side="long",
                        sf=pos["risk"] / pos["ents"][0], adds=[t[pos["bar"]]],
                        coin=coin, rule=rule))
    return out


def rows_for(**kw):
    key = tuple(sorted((k, str(v)) for k, v in kw.items()))
    if key in _C:
        return _C[key]
    rows = []
    for rule in RULES:
        rows += shorts_for(rule)
        for coin in blend.BOOK:
            d = blend.load(coin)
            if d is None:
                continue
            df = resample(d, rule)
            if len(df) >= 300:
                rows += walk(df, rule, coin, **kw)
    _C[key] = rows
    return rows


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    hdr = f"  {'variant':<32}{'taken':>7}{'TUNE':>8}{'DD':>5}{'HOLD':>8}{'DD':>5}{'worst':>8}"

    def show(lab, **kw):
        rows = rows_for(**kw)
        t = stat(rows, bear, cut, "tune"); h = stat(rows, bear, cut, "hold")
        print(f"  {lab:<32}{h[3]:>7.0f}{t[0]:>+7.2f}%{t[1]:>4.0f}%{h[0]:>+7.2f}%{h[1]:>4.0f}%"
              f"{h[2]:>+7.1f}%")

    print(f"tune < {cut:%Y-%m-%d} <= holdout | 5 orderings averaged\n")
    print("BASELINE (2xATR stop, no time stop, market entry)"); print(hdr)
    show("deployed")

    print("\n1. STOP WIDTH (1R = this many ATR)"); print(hdr)
    for sl in (1.0, 1.5, 3.0, 4.0):
        show(f"stop {sl:g}xATR", sl_mult=sl)

    print("\n2. TIME STOP (close if below r R after n bars)"); print(hdr)
    for nb, mr in ((20, 0.0), (50, 0.0), (100, 0.0), (50, 1.0), (100, 2.0)):
        show(f"cut below {mr:g}R after {nb} bars", time_stop=(nb, mr))

    print("\n3. ENTRY ON A PULLBACK, CAUSAL (limit below the signal close, fills later)")
    print(hdr)
    for p in (0.25, 0.5, 1.0):
        show(f"entry limit {p:g}xATR below", entry_pull=p)
    print("\n  bar to clear: better than deployed on BOTH halves by >2%/mo")


if __name__ == "__main__":
    main()

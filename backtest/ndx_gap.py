"""OPENING-GAP TRADING ON NASDAQ, AS THE SKE-Labs gap-trading SKILL STATES IT (2026-10-27)

SKE-Labs/agent-trading-skills (skills/day-trading/gap-trading) is a framework more than a recipe, but it names three concrete
things worth testing exactly: (1) a NORMALISED gap, |open - previous close| / prior ATR, not a percentage cutoff; (2) FADE and
CONTINUATION tested separately; (3) the opening range's length chosen "in training data only", "retain a rule only when it
survives held-out costs". Never tested here as a gap rule (fx_intraday_pub.py tested the opening-range breakout without
conditioning on the gap; ndx_close_momo.py the last hour).

DATA   HistData NSXUSD 1-minute bars 2010-11 .. 2026-09, the cash session 09:30-16:00 New York (fx_intraday_pub.session);
       gap = the session's first open / the previous session's close - 1 (it contains the overnight move). ATR% = mean over
       the previous 14 sessions of (high - low) / previous close.
RULE   gap size z = |gap| / ATR% in three bins: [0.3, 0.6), [0.6, 1.0), >= 1.0 (fixed in advance; < 0.3 = no gap, skipped).
       Opening range = the first N minutes, N in {5, 15, 30}. After minute N the first CLOSED bar that closes beyond the range
       triggers; the order fills at the NEXT bar's open; the stop is the range's other end; exit = the stop or the session's
       last minute.   CONTINUATION = trigger in the gap's direction; FADE = trigger against the gap's direction.
COSTS  Exness NASDAQ: 0.77bp round trip + 0.5bp slippage (fx_intraday_pub), intraday so no swap.
SPLIT  tune = first 60% of days, holdout = the rest. 3 bins x 3 lengths x 2 modes = 18 cells, Holm over the 18.

REGISTERED BEFORE THE FIRST RUN (2026-10-27)
  G1  No cell passes both halves (net a trade > 0 with t >= 2 on each, Holm < 0.05): intraday NASDAQ was closed at every horizon
      (ndx_close_momo.py) and the unconditioned opening-range breakout was dead (fx_intraday_pub.py).
  G2  Continuation and fade are mirror images in gross terms: in every bin and length their gross means have opposite signs or
      are both within 1bp of zero; the bigger the gap bin, the larger the gross absolute move, but the net stays <= 0.
  G3  Fewer than 20% of days trigger in each cell (the rule is selective), so a cell has well under 2,000 trades.

    python -m backtest.ndx_gap
"""
from __future__ import annotations

import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.fx_intraday_pub import INSTR, SLIP, TUNE, session  # noqa: E402

LOG = ROOT / "logs" / "ndx_gap.txt"
BINS = ((0.3, 0.6), (0.6, 1.0), (1.0, 99.0))
LENS = (5, 15, 30)


def trade(O, H, L, C, i, n, s, against):
    """One day: the first closed bar after minute n that closes beyond the opening range; returns (gross return, entered)."""
    hi, lo = H[i, :n].max(), L[i, :n].min()
    want = -s if against else s                      # the break direction that triggers
    for m in range(n, C.shape[1] - 1):
        if (want > 0 and C[i, m] > hi) or (want < 0 and C[i, m] < lo):
            e = O[i, m + 1]
            stop = lo if want > 0 else hi
            x = C[i, -1]
            for k in range(m + 1, C.shape[1]):
                if (want > 0 and L[i, k] <= stop) or (want < 0 and H[i, k] >= stop):
                    x = min(stop, O[i, k]) if want > 0 else max(stop, O[i, k])
                    break
            return want * (x / e - 1), True
    return 0.0, False


def tstat(x):
    x = np.asarray(x, float)
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std(ddof=1) > 0 else np.nan


def main():
    A, dates, prev = session("NASDAQ")
    O, H, L, C = A["o"], A["h"], A["l"], A["c"]
    cost = (INSTR["NASDAQ"][4] + SLIP) / 1e4
    n = len(dates)
    gap = O[:, 0] / prev - 1
    rng = (H.max(1) - L.min(1)) / prev
    atr = pd.Series(rng, index=dates).rolling(14).mean().shift(1).to_numpy()
    z = np.abs(gap) / atr
    cut = int(n * TUNE)
    L_ = [f"backtest/ndx_gap.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; NASDAQ cash sessions {dates[0]:%Y-%m-%d} .. "
          f"{dates[-1]:%Y-%m-%d} ({n} days), tune = first {cut}; cost {cost * 1e4:.2f}bp a trade", "",
          f"  gap-size bins (z = |gap| / 14-day ATR%): " + "  ".join(f"[{a:g},{b:g}) {np.mean((z >= a) & (z < b)) * 100:.0f}% of days" for a, b in BINS), ""]
    L_.append(f"  {'cell':<28}{'trades':>7}{'trig %':>7} | {'gross bp':>9} {'net bp':>8} {'t':>6} | {'tune net bp (t)':>17} {'holdout net bp (t)':>20} | Holm p")
    cells = []
    for bi, (a, b) in enumerate(BINS):
        sel = np.isfinite(z) & (z >= a) & (z < b) & np.isfinite(gap) & (gap != 0)
        for nlen in LENS:
            for against, nm in ((False, "CONT"), (True, "FADE")):
                g, tr = np.zeros(n), np.zeros(n, bool)
                for i in np.flatnonzero(sel):
                    s = np.sign(gap[i])
                    g[i], tr[i] = trade(O, H, L, C, i, nlen, s, against)
                net = g - cost * tr
                k = tr & (np.arange(n) < cut)
                ho = tr & (np.arange(n) >= cut)
                cells.append(dict(name=f"{nm} bin{bi + 1} N={nlen}", n=int(tr.sum()), trig=tr.sum() / max(sel.sum(), 1), gross=g[tr].mean(),
                                  net=net[tr].mean(), t=tstat(net[tr]), tu=net[k].mean() if k.sum() else np.nan,
                                  t_tu=tstat(net[k]) if k.sum() > 2 else np.nan, ho=net[ho].mean() if ho.sum() else np.nan,
                                  t_ho=tstat(net[ho]) if ho.sum() > 2 else np.nan, bin=bi, nlen=nlen, mode=nm))
    ps = sorted((1 - 0.5 * (1 + erf(c["t"] / sqrt(2))), i) for i, c in enumerate(cells))     # one-sided: a positive mean
    run_max, holm = 0.0, {}
    for r_, (p, i) in enumerate(ps):
        run_max = max(run_max, min(1.0, p * (len(ps) - r_)))
        holm[i] = run_max
    passes = []
    for i, c in enumerate(cells):
        ok = c["tu"] > 0 and c["ho"] > 0 and c["t_tu"] >= 2 and c["t_ho"] >= 2 and holm[i] < 0.05
        if ok:
            passes.append(c["name"])
        L_.append(f"  {c['name']:<28}{c['n']:>7}{c['trig'] * 100:>6.0f}% | {c['gross'] * 1e4:>+9.1f} {c['net'] * 1e4:>+8.1f} {c['t']:>+6.1f} | "
                  f"{c['tu'] * 1e4:>+9.1f} ({c['t_tu']:+.1f}) {c['ho'] * 1e4:>+12.1f} ({c['t_ho']:+.1f}) | {holm[i]:.2f}")
    mirror = all((np.sign(cells[j]["gross"]) != np.sign(cells[j + 1]["gross"])) or max(abs(cells[j]["gross"]), abs(cells[j + 1]["gross"])) < 1e-4
                 for j in range(0, len(cells), 2))
    sel_ok = all(c["trig"] < 0.2 for c in cells)
    L_ += ["", f"  PASS (both halves t >= 2, Holm < 0.05): {passes or 'none'}", "", "REGISTERED PREDICTIONS",
           f"  G1 no cell passes -> {'RIGHT' if not passes else 'WRONG'}",
           f"  G2 continuation and fade have opposite gross signs (or ~0) in every bin and length -> {'RIGHT' if mirror else 'WRONG'}",
           f"  G3 fewer than 20% of the bin's days trigger in every cell -> {'RIGHT' if sel_ok else 'WRONG'} "
           f"(max {max(c['trig'] for c in cells) * 100:.0f}%)"]
    txt = "\n".join(L_)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

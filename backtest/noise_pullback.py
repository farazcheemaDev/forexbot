"""MENDING HIS PULLBACK HABIT FOR THE BOT: enter NASDAQ noise momentum on a small pullback after the signal instead of at once (2026-11-03)

The user, 2026-11-03: "keep them [his habits] in mind or mend them in ways beneficial to us". Of his ten habits (docs: his_strategy / CLAUDE.md), nine are either already in forex_bot.py (NASDAQ only, flat before the close,
no averaging down, acting seconds after a 1-minute bar closes), neutral (his +10% monthly stop changes the NOISE book by -0.5 points of CAGR, noise_book.py), or cannot be used without his entries (the exit shape: all
30 target x stop combinations lose from a random entry, his_exit_shape.py). ONE can be tried on the strategy we have: he enters on a small pullback against himself (his_strategy s34) - a better price AND a filter against
false breakouts. Here: when the NOISE rule says go long (short), do not buy at once; rest a limit `retr` basis points BELOW (above) the signal close and wait up to `wait` minutes for it to trade through by 0.5 bp. If it does not,
that checkpoint is skipped (the next one re-evaluates). Exits and flips stay at the market, as in the backtest. Same HistData NASDAQ minute bars (2010-2026), same costs (0.77 bp spread + 0.5 bp slippage per entered trade,
kept even for limit fills - conservative).

REGISTERED BEFORE THE FIRST RUN (2026-11-03)
    M1  No variant beats the baseline on BOTH halves with a paired t >= 2.5 (Holm over the 4 cells); the entry limit misses the strongest breakouts, which are the ones that run away (the same reason entry limits failed on
        the trend book, doc 02).
    M2  All four variants earn LESS per day than the baseline (+2.25 bp): the trades it skips are worth more than the price improvement.
    M3  At wait = 0 the function reproduces fx_intraday_pub.noise() exactly (a test).

RESULT (2026-11-03; logs/noise_pullback.txt; 3,686 sessions 2010-11..2026-09)
    The baseline reproduces +2.25 bp a day (Sharpe 0.74, 0.83 trades a day). EVERY pullback variant is worse, on both halves: wait 5 min / pull back 2 bp +1.22 (diff -1.03, paired t -4.7), 5 min / 5 bp +1.02 (-1.23, t -3.8),
    15 min / 2 bp +1.32 (-0.92, t -5.0), 15 min / 5 bp +1.26 (-0.99, t -3.8); Sharpe 0.74 -> 0.36-0.45; the entries skipped are the breakouts that run, so half the edge goes. M1, M2, M3 all RIGHT.
    Reading: his pullback habit cannot be bolted onto the noise rule; the pullback is part of whatever tells him the side, not a filter that improves a momentum breakout.

    python -m backtest.noise_pullback        writes logs/noise_pullback.txt          tests: python tests/test_noise_pullback.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.fx_intraday_pub import INSTR, SLIP, TUNE, session  # noqa: E402

THROUGH_BP = 0.5
GRID = [(w, r) for w in (5, 15) for r in (2.0, 5.0)]      # (minutes to wait, retracement in basis points)


def noise_pb(A, prev, wait=0, retr_bp=0.0, through_bp=THROUGH_BP, look=14):
    """fx_intraday_pub.noise() with an optional pullback entry. Returns (daily gross return, entered trades). wait = 0 (or retr_bp = 0) is the original rule, entry at the next minute's open."""
    O, H, Lo, C = A["o"], A["h"], A["l"], A["c"]
    n, L = C.shape
    op = O[:, :1]
    sig = pd.DataFrame(np.abs(C / op - 1)).rolling(look).mean().shift(1).to_numpy()
    out, trades = np.zeros(n), np.zeros(n)
    for i in range(n):
        if not np.isfinite(sig[i, 0]) or not np.isfinite(prev[i]):
            continue
        ub_base, lb_base = max(op[i, 0], prev[i]), min(op[i, 0], prev[i])
        pos, entry, r, nt = 0, np.nan, 0.0, 0
        for m in range(30, L - 1, 30):
            c = C[i, m]
            ub, lb = ub_base * (1 + sig[i, m]), lb_base * (1 - sig[i, m])
            want = 1 if c > ub else (-1 if c < lb else 0)
            if want == pos:
                continue
            px = O[i, m + 1]
            if pos != 0:
                r += pos * (px / entry - 1)
                pos = 0
            if want != 0:
                if wait == 0 or retr_bp <= 0:
                    pos, entry = want, px
                    nt += 1
                else:
                    limit = c * (1 - want * retr_bp / 1e4)
                    thr = limit * (1 - want * through_bp / 1e4)         # a long needs the low to trade BELOW the limit by through_bp; a short the high ABOVE it
                    for k in range(1, min(wait, 29) + 1):
                        j = m + k
                        if j >= L:
                            break
                        if (Lo[i, j] <= thr) if want > 0 else (H[i, j] >= thr):
                            pos, entry = want, limit
                            nt += 1
                            break
        if pos != 0:
            r += pos * (C[i, -1] / entry - 1)
        out[i], trades[i] = r, nt
    return out, trades


def tstat(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std() > 0 else 0.0


def main():
    S = session("NASDAQ")
    if S is None:
        raise SystemExit("HistData NASDAQ minute bars missing (strategy_analysis/data/histdata/NSXUSD.parquet)")
    A, dates, prev = S
    cost = (INSTR["NASDAQ"][4] + SLIP) / 1e4
    cut = int(len(dates) * TUNE)
    g0, n0 = noise_pb(A, prev)
    base = g0 - cost * n0
    out = [f"backtest/noise_pullback.py - NASDAQ noise momentum, {len(dates)} sessions {dates[0]:%Y-%m}..{dates[-1]:%Y-%m}, net of {INSTR['NASDAQ'][4] + SLIP:.2f} bp per entered trade; tune = first {cut} sessions",
           f"   {'variant':<26}{'net bp/day':>11}{'diff vs base':>13}{'paired t':>9}{'tune diff':>10}{'t':>6}{'hold diff':>10}{'t':>6}{'trades/day':>11}{'Sharpe':>7}",
           f"   {'baseline (enter at once)':<26}{base.mean() * 1e4:>+11.2f}{'':>13}{'':>9}{'':>10}{'':>6}{'':>10}{'':>6}{n0.mean():>11.2f}{base.mean() / base.std(ddof=1) * np.sqrt(252):>7.2f}"]
    pv = {}
    rows = []
    for w, r in GRID:
        g, nt = noise_pb(A, prev, w, r)
        net = g - cost * nt
        d = net - base
        a, b = d[:cut], d[cut:]
        rows.append(((w, r), d.mean() * 1e4, tstat(d), a.mean() * 1e4, tstat(a), b.mean() * 1e4, tstat(b), nt.mean(), net.mean() / net.std(ddof=1) * np.sqrt(252), net.mean() * 1e4))
        out.append(f"   {f'wait {w:>2} min, pull back {r:g} bp':<26}{net.mean() * 1e4:>+11.2f}{d.mean() * 1e4:>+13.2f}{tstat(d):>+9.2f}{a.mean() * 1e4:>+10.2f}{tstat(a):>+6.2f}{b.mean() * 1e4:>+10.2f}{tstat(b):>+6.2f}{nt.mean():>11.2f}{rows[-1][8]:>7.2f}")
    win = [k for k, dm, t, am, ta, bm, tb, _, _, _ in rows if dm > 0 and t >= 2.5 and am > 0 and bm > 0]
    out.append(f"\n   variants better than the baseline on BOTH halves with paired t >= 2.5: {len(win)} of {len(rows)}; variants that earn less than the baseline: {sum(1 for r_ in rows if r_[1] < 0)} of {len(rows)}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "noise_pullback.txt").write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

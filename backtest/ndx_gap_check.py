"""IS THE LARGE-GAP CONTINUATION REAL? CHECKS ON backtest/ndx_gap.py's TWO PASSING CELLS (2026-10-27)

ndx_gap.py (the SKE-Labs gap-trading skill's ideas, 18 registered cells, Holm over the 18) passed two cells against its own
prediction G1: NASDAQ gaps of at least one 14-day-ATR, a break of the opening range IN THE GAP'S DIRECTION after 15 / 30
minutes, out at the close: net +22.7 / +25.7bp a trade, t 3.1 / 3.5, tune t 2.2 / 2.1, holdout 2.2 / 2.8, ~9 trades a year
(144 / 132 trades in 16 years). It looks good, so the next move is the bug / duplicate hunt (CLAUDE.md s9):
  K1 CONSISTENCY   the rule is positive in at least 11 of the 15 calendar years that have a trade.
  K2 PLATEAU       the neighbours - gap size z >= 0.8 / 1.2 / 1.5 and opening ranges 10 / 20 / 45 / 60 minutes - are positive on
                   BOTH halves in at least 80% of the 12 neighbouring cells, and none of the 12 has a negative pooled mean.
  K3 OTHER INDICES the frozen rule (z >= 1, N = 15 and 30) is positive on both halves on S&P 500 (SPXUSD, same overnight
                   news) and not on DAX (GRXEUR, a different session: its "gap" is a different object) - registered as
                   S&P yes, DAX weaker.
  K4 DUPLICATE     it is mostly the NOISE book (noise_book.py's candidate): NOISE's own mean net on the same days is positive
                   and the daily P&L of the two correlate above +0.4 on the triggered days - so the gap rule adds less than
                   half of its standalone P&L on top of NOISE. (noise() gives P&L, not a side, so no side-overlap test.)
  K5 BOTH SIDES   gap-ups and gap-downs are each positive on the net (it is not a long-only drift).
  K6 PLACEBO      the same trade rule on RANDOM days with a random direction (same number of days, 500 draws) has a mean net
                   near zero: the real mean is above the 99th percentile of the placebo means, and the placebo's mean is
                   within +-3bp (no bias in the entry / exit mechanics).
  K7 COST STRESS  the net stays positive at 3x the cost (the open is wide on gap days): cost 3.8bp a trade.
VERDICT  a CANDIDATE only if K1-K3, K5, K6, K7 hold; if K4 also holds it is a subset of NOISE (nothing new, but a better
         way to size NOISE). Anything else: a chance cell among 18. Never a pass: found in one dataset after reading its grid.

    python -m backtest.ndx_gap_check
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.fx_intraday_pub import INSTR, SLIP, TUNE, noise, session  # noqa: E402
from backtest.ndx_gap import tstat, trade  # noqa: E402

LOG = ROOT / "logs" / "ndx_gap_check.txt"


def prep(name):
    A, dates, prev = session(name)
    O, H, L, C = A["o"], A["h"], A["l"], A["c"]
    gap = O[:, 0] / prev - 1
    rng = (H.max(1) - L.min(1)) / prev
    atr = pd.Series(rng, index=dates).rolling(14).mean().shift(1).to_numpy()
    return A, dates, prev, gap, np.abs(gap) / atr


def run(O, H, L, C, gap, z, lo, nlen, mask=None, against=False):
    g = np.zeros(len(z))
    tr = np.zeros(len(z), bool)
    sel = np.isfinite(z) & (z >= lo) & np.isfinite(gap) & (gap != 0)
    if mask is not None:
        sel &= mask
    for i in np.flatnonzero(sel):
        g[i], tr[i] = trade(O, H, L, C, i, nlen, np.sign(gap[i]), against)
    return g, tr


def halves(net, tr, cut):
    idx = np.arange(len(net))
    a, b = tr & (idx < cut), tr & (idx >= cut)
    return net[a].mean() if a.sum() else np.nan, net[b].mean() if b.sum() else np.nan, tstat(net[a]) if a.sum() > 2 else np.nan, tstat(net[b]) if b.sum() > 2 else np.nan


def main():
    A, dates, prev, gap, z = prep("NASDAQ")
    O, H, L, C = A["o"], A["h"], A["l"], A["c"]
    n = len(dates)
    cut = int(n * TUNE)
    cost = (INSTR["NASDAQ"][4] + SLIP) / 1e4
    Lg = [f"backtest/ndx_gap_check.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; NASDAQ {dates[0]:%Y-%m-%d} .. {dates[-1]:%Y-%m-%d}; "
          f"rule = gap z >= 1.0, opening range N, continuation; cost {cost * 1e4:.2f}bp", ""]
    base = {}
    for nlen in (15, 30):
        g, tr = run(O, H, L, C, gap, z, 1.0, nlen)
        base[nlen] = (g, tr)
        net = g - cost * tr
        Lg.append(f"  baseline N={nlen}: {int(tr.sum())} trades, net {net[tr].mean() * 1e4:+.1f}bp, t {tstat(net[tr]):+.1f}")
    g, tr = base[30]
    net = g - cost * tr
    # K1 yearly
    yrs = pd.Series(net[tr], index=dates[tr]).groupby(dates[tr].year).agg(["mean", "size"])
    k1_pos = int((yrs["mean"] > 0).sum())
    Lg += ["", "K1 BY YEAR (N=30): " + "  ".join(f"{y}:{r['mean'] * 1e4:+.0f}({int(r['size'])})" for y, r in yrs.iterrows()),
           f"   positive years {k1_pos} of {len(yrs)}"]
    k1 = k1_pos >= 11
    # K2 plateau
    nb = []
    Lg.append("K2 PLATEAU  (net bp per trade; tune / holdout; trades)")
    for lo in (0.8, 1.2, 1.5):
        for nlen in (15, 30):
            gg, tt = run(O, H, L, C, gap, z, lo, nlen)
            nn = gg - cost * tt
            a, b, ta, tb = halves(nn, tt, cut)
            nb.append((lo, nlen, nn[tt].mean(), a, b))
            Lg.append(f"   z >= {lo:<3} N={nlen:<3}: {nn[tt].mean() * 1e4:+7.1f}   {a * 1e4:+7.1f} / {b * 1e4:+7.1f}   {int(tt.sum())}")
    for nlen in (10, 20, 45, 60):
        gg, tt = run(O, H, L, C, gap, z, 1.0, nlen)
        nn = gg - cost * tt
        a, b, ta, tb = halves(nn, tt, cut)
        nb.append((1.0, nlen, nn[tt].mean(), a, b))
        Lg.append(f"   z >= 1.0 N={nlen:<3}: {nn[tt].mean() * 1e4:+7.1f}   {a * 1e4:+7.1f} / {b * 1e4:+7.1f}   {int(tt.sum())}")
    both = sum(1 for _, _, m, a, b in nb if a > 0 and b > 0)
    k2 = both / len(nb) >= 0.8 and all(m > 0 for _, _, m, _, _ in nb)
    Lg.append(f"   both halves positive in {both} of {len(nb)} neighbours")
    # K3 other indices
    Lg.append("K3 OTHER INDICES (frozen rule, z >= 1.0): net bp (tune / holdout) trades")
    k3 = {}
    for nm in ("S&P 500", "DAX"):
        A2, d2, p2, g2, z2 = prep(nm)
        O2, H2, L2, C2 = A2["o"], A2["h"], A2["l"], A2["c"]
        c2 = (INSTR[nm][4] + SLIP) / 1e4
        cu2 = int(len(d2) * TUNE)
        for nlen in (15, 30):
            gg, tt = run(O2, H2, L2, C2, g2, z2, 1.0, nlen)
            nn = gg - c2 * tt
            a, b, ta, tb = halves(nn, tt, cu2)
            k3[(nm, nlen)] = (a, b)
            Lg.append(f"   {nm:8} N={nlen}: {nn[tt].mean() * 1e4:+7.1f}  ({a * 1e4:+.1f} / {b * 1e4:+.1f})  {int(tt.sum())} trades, t {tstat(nn[tt]):+.1f}")
    k3ok = all(k3[("S&P 500", nl)][0] > 0 and k3[("S&P 500", nl)][1] > 0 for nl in (15, 30))
    # K4 overlap with NOISE
    gN, _, nN = noise(A, prev)
    rn = gN - cost * nN
    on = tr
    corr = np.corrcoef(rn[on], net[on])[0, 1]
    Lg += ["", f"K4 NOISE on the same {int(on.sum())} days: its mean net {rn[on].mean() * 1e4:+.1f}bp (all days {rn.mean() * 1e4:+.2f}bp); the gap rule's "
           f"{net[on].mean() * 1e4:+.1f}bp; daily correlation {corr:+.2f}"]
    k4 = rn[on].mean() > 0 and corr > 0.4
    # K5 both sides
    up = on & (gap > 0)
    dn = on & (gap < 0)
    Lg.append(f"K5 gap-ups: {int(up.sum())} trades, net {net[up].mean() * 1e4:+.1f}bp (t {tstat(net[up]):+.1f}); gap-downs: {int(dn.sum())} trades, "
              f"net {net[dn].mean() * 1e4:+.1f}bp (t {tstat(net[dn]):+.1f})")
    k5 = net[up].mean() > 0 and net[dn].mean() > 0
    # K6 placebo
    rng = np.random.default_rng(5)
    valid = np.flatnonzero(np.isfinite(z))
    k = int(on.sum())
    means = []
    for _ in range(500):
        days = rng.choice(valid, size=int(k / 0.7), replace=False)
        sgn = rng.choice([-1.0, 1.0], size=len(days))
        gg = np.zeros(n)
        tt = np.zeros(n, bool)
        for d, s in zip(days, sgn):
            gg[d], tt[d] = trade(O, H, L, C, d, 30, s, False)
        if tt.sum() > 20:
            means.append((gg - cost * tt)[tt].mean())
    means = np.array(means)
    real = net[on].mean()
    Lg.append(f"K6 PLACEBO (random days, random direction, N=30, 500 draws): mean {means.mean() * 1e4:+.1f}bp, 5th-95th "
              f"{np.percentile(means, 5) * 1e4:+.1f}..{np.percentile(means, 95) * 1e4:+.1f}; 99th pct {np.percentile(means, 99) * 1e4:+.1f}bp; real {real * 1e4:+.1f}bp")
    k6 = real > np.percentile(means, 99) and abs(means.mean()) < 3e-4
    # K7 cost stress
    stress = g - 3 * cost * tr
    Lg.append(f"K7 COST x3 ({3 * cost * 1e4:.1f}bp): net {stress[tr].mean() * 1e4:+.1f}bp, t {tstat(stress[tr]):+.1f}")
    k7 = stress[tr].mean() > 0
    Lg += ["", "REGISTERED CHECKS",
           f"  K1 >= 11 positive years ({k1_pos} of {len(yrs)}) -> {'HOLDS' if k1 else 'FAILS'}",
           f"  K2 plateau ({both} of {len(nb)} neighbours positive on both halves) -> {'HOLDS' if k2 else 'FAILS'}",
           f"  K3 S&P positive on both halves at N=15 and 30 -> {'HOLDS' if k3ok else 'FAILS'}",
           f"  K4 a duplicate of NOISE -> {'YES' if k4 else 'NO'}",
           f"  K5 both gap directions positive -> {'HOLDS' if k5 else 'FAILS'}",
           f"  K6 placebo -> {'HOLDS' if k6 else 'FAILS'}",
           f"  K7 cost x3 -> {'HOLDS' if k7 else 'FAILS'}"]
    cand = k1 and k2 and k3ok and k5 and k6 and k7
    Lg.append(f"  VERDICT: {'CANDIDATE' + (' (but a subset of NOISE)' if k4 else '') if cand else 'CHANCE CELL / NOT ROBUST'}")
    txt = "\n".join(Lg)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

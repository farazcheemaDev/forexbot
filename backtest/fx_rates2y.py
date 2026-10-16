"""THE DRIVER fx_drivers.py LACKED: 2-YEAR YIELD GAPS - and the way traders use them, "the currency catches up to rates"
(2026-10-12)

THE USER (2026-10-12): "I don't think you had all the correct information that drives forex." Right on the most important
piece: desks price a currency off the gap between its 2-YEAR government yield and the US one (the market's view of the
next two years of rates), and fx_drivers.py had only the US 2-year, central-bank policy rates and monthly 10-year rates.
backtest/fx_macro_data.py now holds daily 2-year yields from each issuer: US, Germany (for EUR), Japan, Canada,
Switzerland (to 2025-07). The UK, Australia and New Zealand could not be reached from this PC (Bank of England: no
connection; RBA / RBNZ: HTTP 403) and are left out here.

TESTS (weekly periods from the Monday noon fix, monthly from the first business day's; the gap is read at the close
BEFORE the period starts; fx_drivers' machinery and Exness costs)
    A  MOVES WITH   the same week's / month's change in the 2y gap (foreign - US) against the currency's move
    B  PREDICTS     last week's / month's gap change against the NEXT week's / month's move
    C  CATCH-UP     each week, beta = the currency's response to its gap over the trailing 104 weeks (causal); if last
                    week the currency moved less than its gap change implied (residual < -0.5 sd) buy it, if more sell it
                    - "the currency lags rates and catches up"
    D  FAIR VALUE   regress the currency's log level on its gap level over the trailing 52 weeks (causal); when it sits
                    more than 1 sd from that fair value, trade back toward it, re-decided weekly
    E  RATE TREND   monthly: follow the sign of the last 1 / 3 months' 2y-gap change
PASS     as fx_drivers: Exness net > 0 with t >= 2 on both halves, Holm p < 0.05 across these rules.

REGISTERED BEFORE THE RUN (2026-10-12)
    Y1  A: each currency's same-week correlation with its own 2y-gap change is >= +0.3 (EUR, JPY, CAD, CHF) - far above
        the policy gap's ~0 in fx_drivers.
    Y2  B: every next-week and next-month |correlation| is under 0.10.
    Y3  C and D: positive on at least one half, but neither passes on Exness.
    Y4  E does not pass.
    Y5  0 rules pass.

RESULT (2026-10-12 07:36 UTC, logs/fx_rates2y.txt; 1,605 weeks / 370 months)
    - A: the 2-year gap IS the rate driver the policy gap was not: same month EUR +0.40, JPY +0.41, CAD +0.31, CHF +0.27
      (the policy-rate gap: -0.05..+0.03 in fx_drivers). Same week +0.23..+0.34 - Y1 WRONG for EUR / CAD / CHF weekly,
      partly because the H.10 fix is at noon and the yields at the close, half a day apart.
    - B (Y2 RIGHT): last week's / month's gap change says almost nothing about the next: +0.01..+0.09.
    - Rules (Y3, Y4, Y5 RIGHT): 0 of 4 pass, every Holm p 1.00. The best is FAIR VALUE (trade a currency back toward the
      level its 52-week rate model implies): +1.28%/yr at Exness, but tune -0.016% (t -0.3) / holdout +0.086% (t +1.7)
      a week - holdout only. CATCH-UP (the currency lags its rate move) -1.07%/yr; RATE TREND 1m / 3m -0.76 / -0.15%/yr.
    Reading: with the right rate measure, rates explain about a sixth of a currency's monthly move (r ~0.4) - at the
    same time. The market keeps the currency in step with its 2-year gap within the week; there is no lag to trade.

    python -m backtest.fx_rates2y
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import fx_drivers as fd  # noqa: E402
from backtest import fx_macro_data as md  # noqa: E402

LOG = ROOT / "logs" / "fx_rates2y.txt"
C4 = ["EUR", "JPY", "CAD", "CHF"]


def main():
    y = md.load("yields_2y.csv")
    gap_d = pd.DataFrame({c: y[c] - y["USD"] for c in C4}).dropna(how="all")
    lines = [f"backtest/fx_rates2y.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; 2-year yield gaps (foreign - US): EUR "
             f"(Germany) 1997-, JPY 1996-, CAD 2001-, CHF 1996-2025-07; Fed H.10 noon FX; Exness costs", ""]
    out = {}
    for fq, name in (("W", "WEEK"), ("M", "MONTH")):
        starts, ret, nights = fd.grid(fq)
        g = fd.asof(gap_d, starts)                                  # the gap at the close before each period start
        dg_same = g.shift(-1) - g                                   # its change over the period
        dg_last = g - g.shift(1)                                    # its change over the previous period
        lines.append(f"{name}S ({len(starts)})")
        lines.append(f"  {'':34}" + "".join(f"{c:>8}" for c in C4))
        rs, rn = "", ""
        for c in C4:
            j = pd.concat([dg_same[c], ret[c]], axis=1).dropna()
            r1 = j.iloc[:, 0].corr(j.iloc[:, 1])
            j2 = pd.concat([dg_last[c], ret[c]], axis=1).dropna()
            r2 = j2.iloc[:, 0].corr(j2.iloc[:, 1])
            out[(fq, "same", c)], out[(fq, "next", c)] = r1, r2
            rs += f"{r1:+8.2f}"
            rn += f"{r2:+8.2f}"
        lines.append(f"  {'A  moves with (same ' + name.lower() + ')':34}" + rs)
        lines.append(f"  {'B  predicts (next ' + name.lower() + ')':34}" + rn)
        lines.append("")
        out[(fq, "grid")] = (starts, ret, nights, g, dg_last)
    # ----- trading rules -----
    starts, ret, nights, g, dg_last = out[("W", "grid")]
    rules = {}
    # C: catch-up
    pos_c = pd.DataFrame(0.0, index=starts, columns=fd.CCY)
    for c in C4:
        x, yv = dg_last[c], ret[c].shift(1)                         # last week's gap change and last week's move
        cov = (x * yv).rolling(104, min_periods=52).mean() - x.rolling(104, min_periods=52).mean() * yv.rolling(104, min_periods=52).mean()
        var = x.rolling(104, min_periods=52).var(ddof=0)
        beta = (cov / var).shift(1)                                 # estimated on weeks before last week
        resid = yv - beta * x
        sd = resid.rolling(104, min_periods=52).std().shift(1)
        pos_c[c] = np.where(resid < -0.5 * sd, 1.0, np.where(resid > 0.5 * sd, -1.0, 0.0))
    rules["C CATCH-UP (currency lags its 2y gap)"] = ("W", pos_c)
    # D: fair value on levels
    fx = md.load("fx_h10.csv")
    lvl = np.log(fd.asof(fx[C4], starts))                           # the currency's level at the close before the start
    pos_d = pd.DataFrame(0.0, index=starts, columns=fd.CCY)
    for c in C4:
        a, b = g[c], lvl[c]
        cov = (a * b).rolling(52, min_periods=40).mean() - a.rolling(52, min_periods=40).mean() * b.rolling(52, min_periods=40).mean()
        var = a.rolling(52, min_periods=40).var(ddof=0)
        beta = cov / var
        alpha = b.rolling(52, min_periods=40).mean() - beta * a.rolling(52, min_periods=40).mean()
        res = b - (alpha + beta * a)
        sd = res.rolling(52, min_periods=40).std()
        z = res / sd
        pos_d[c] = np.where(z < -1, 1.0, np.where(z > 1, -1.0, 0.0))
    rules["D FAIR VALUE (52-week level model)"] = ("W", pos_d)
    # E: rate trend, monthly
    ms, mret, mn, mg, _ = out[("M", "grid")]
    for k in (1, 3):
        d_ = mg - mg.shift(k)
        rules[f"E RATE TREND ({k}m 2y-gap change)"] = ("M", np.sign(d_).reindex(columns=fd.CCY).fillna(0.0))
    lines.append("TRADING RULES (% a period; EXNESS is the verdict; +CARRY earns the 2y gap)")
    lines.append(f"  {'rule':40} {'n':>5} | {'SPOT':>7} {'+CARRY':>7} {'EXNESS':>7} | EXNESS tune (t) / holdout (t) | ann. | worst")
    res = {}
    for nm, (fq, pos) in rules.items():
        st_, rt_, nt_, ppy = (starts, ret, nights, 52) if fq == "W" else (ms, mret, mn, 12)
        rates = fd.asof(y, st_).reindex(columns=["USD"] + fd.CCY)
        s_spot, s_carry, s_ex = fd.run(pos.reindex(columns=fd.CCY).fillna(0.0), rt_, nt_, rates)
        a_, b_, e_ = fd.stat(s_spot, ppy), fd.stat(s_carry, ppy), fd.stat(s_ex, ppy)
        res[nm] = (a_, b_, e_)
        lines.append(f"  {nm:40} {e_['n']:5} | {a_['mean'] * 100:+7.3f} {b_['mean'] * 100:+7.3f} {e_['mean'] * 100:+7.3f} | "
                     f"{e_['tu'] * 100:+.3f} ({e_['t_tu']:+.1f}) / {e_['ho'] * 100:+.3f} ({e_['t_ho']:+.1f}) | "
                     f"{e_['ann'] * 100:+.2f}%/yr | {e_['worst'] * 100:+.1f}%")
        lines.append(f"  {'':40}       SPOT: tune {a_['tu'] * 100:+.3f} ({a_['t_tu']:+.1f}) / holdout {a_['ho'] * 100:+.3f} ({a_['t_ho']:+.1f})")
    ps = sorted((res[n][2]["p"], n) for n in res)
    holm, run_max = {}, 0.0
    for r_, (p, n) in enumerate(ps):
        run_max = max(run_max, min(1.0, p * (len(ps) - r_)))
        holm[n] = run_max
    passes = [n for n in res if res[n][2]["tu"] > 0 and res[n][2]["ho"] > 0 and res[n][2]["t_tu"] >= 2
              and res[n][2]["t_ho"] >= 2 and holm[n] < 0.05]
    lines.append("  Holm p: " + ", ".join(f"{n.split(' (')[0]} {holm[n]:.2f}" for n in res) + f" | PASS: {passes or 'none'}")
    lines.append("")
    lines.append("REGISTERED PREDICTIONS")
    s1 = [out[("W", "same", c)] for c in C4]
    lines.append(f"  Y1 same-week correlation " + ", ".join(f"{c} {v:+.2f}" for c, v in zip(C4, s1)) +
                 f" -> {'RIGHT' if all(v >= 0.3 for v in s1) else 'WRONG'}")
    nx = [abs(out[(f, 'next', c)]) for f in ("W", "M") for c in C4]
    lines.append(f"  Y2 largest next-period |corr| {max(nx):.2f} -> {'RIGHT' if max(nx) < 0.10 else 'WRONG'}")
    cd = [res[k] for k in res if k.startswith(("C ", "D "))]
    y3 = all((r[2]["tu"] > 0 or r[2]["ho"] > 0) for r in cd) and not any(k.startswith(("C ", "D ")) for k in passes)
    lines.append(f"  Y3 catch-up / fair value positive on a half, neither passes -> {'RIGHT' if y3 else 'WRONG'}")
    lines.append(f"  Y4 rate trend passes: {[k for k in passes if k.startswith('E ')] or 'none'} -> "
                 f"{'RIGHT' if not any(k.startswith('E ') for k in passes) else 'WRONG'}")
    lines.append(f"  Y5 passes: {passes or 'none'} -> {'RIGHT' if not passes else 'WRONG'}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

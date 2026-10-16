"""WHO IS POSITIONED: HEDGE FUNDS, ASSET MANAGERS, DEALERS in the currency futures, 2006-2026 (2026-10-12)

The user (2026-10-12): "basically in the start we can do all freely" - the free sources not yet used. fx_drivers.py read
the CFTC's legacy report (all "non-commercial" traders in one number). The CFTC's Traders in Financial Futures report
(2006-) splits the futures market into LEVERAGED FUNDS (hedge funds, CTAs), ASSET MANAGERS (pensions, insurers, mutual
funds) and DEALERS (the banks on the other side). Each group's net position as a share of open interest, 7 currency
futures, weekly (as of Tuesday, published Friday, used from the next Monday's noon fix). backtest/fx_macro_data.py --
build_tff. Machinery and Exness costs as fx_drivers.py.

TESTS
    A  MOVES WITH   the change in each group's net position in the same week against the currency's move
    B  PREDICTS     last week's change against the next week's move
    RULES (weekly, each currency vs USD):
       LEV CROWD    fade leveraged funds when their net position's 156-week z-score is beyond +-1.5
       LEV FLOW     follow last week's change in leveraged funds' net position
       AM FLOW      follow last week's change in asset managers' net position (slow money, said to lead)
       AM LEVEL     follow asset managers' net position (long when they are net long)
       DEALER FADE  take the other side of the dealers' position change (dealers absorb what clients want)

REGISTERED BEFORE THE RUN (2026-10-12)
    T1  A: leveraged funds' same-week net change correlates >= +0.2 with the currency on most of the 7 (they chase
        moves); dealers' <= -0.2 (they take the other side).
    T2  B: every next-week |correlation| is under 0.10.
    T3  No rule passes on Exness (t >= 2 both halves, Holm across the five).

RESULT (2026-10-12 08:00 UTC, logs/fx_tff.txt; 1,059 weeks 2006-06 .. 2026-09)
    - T1 RIGHT - positioning moves WITH the currency, the textbook way: in the same Tuesday-to-Tuesday week leveraged
      funds add as it rises (EUR +0.30, JPY +0.32, AUD +0.24, GBP +0.23; NZD / CAD / CHF +0.09..+0.16), asset managers too
      (+0.12..+0.28), and the dealers take the other side (-0.27..-0.48). (The first run compared Tuesday positions with
      Monday-to-Monday moves - one day of overlap - and read ~0; the alignment was fixed before any conclusion.)
    - T2 RIGHT: none of it says where the currency goes the following week (|corr| <= 0.07).
    - T3 RIGHT: 0 of 5 rules pass, every Holm p 1.00, every one negative at Exness: fading crowded hedge funds -1.2%/yr,
      following hedge-fund flow -2.9%/yr, asset-manager flow -1.0%/yr, asset-manager side -1.3%/yr, against the
      dealers -2.2%/yr.
    Reading: the split by trader type shows who moves the price (hedge funds and asset managers buy, banks sell to them)
    but the report is three days old when it comes out, and by then the move is in the price.

    python -m backtest.fx_tff
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

LOG = ROOT / "logs" / "fx_tff.txt"
CCY = fd.CCY


def main():
    t = md.load("tff.csv")
    starts, ret, nights = fd.grid("W")
    keep = starts >= "2006-06-19"
    starts, ret, nights = starts[keep], ret[keep], nights[keep]
    pol = fd.policy_gap(starts)[1]
    nets = {}
    for g in ("lev", "am", "dealer"):
        p = t.assign(v=t[g] / t.oi).pivot_table(index="date", columns="ccy", values="v")
        p.index = p.index + pd.Timedelta(days=3)                   # published Friday
        nets[g] = fd.asof(p, starts)[CCY]
    lines = [f"backtest/fx_tff.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; CFTC Traders in Financial Futures, 7 currency "
             f"futures, {len(starts)} weeks {starts.min():%Y-%m-%d} .. {starts.max():%Y-%m-%d}; net position as a share of open "
             f"interest; Fed H.10 noon FX; Exness costs", ""]
    lines.append(f"  {'':40}" + "".join(f"{c:>7}" for c in CCY))
    corr = {}
    # A must compare like with like: positions are measured as of TUESDAY, so the same-week test uses the H.10 fix on
    # each report Tuesday (first run compared Tuesday-to-Tuesday positions with Monday-to-Monday moves - one day of
    # overlap - and read ~0; fixed before any conclusion). B keeps the trading alignment (published Friday -> Monday).
    fxd = md.load("fx_h10.csv")[CCY]
    for g, nm in (("lev", "leveraged funds"), ("am", "asset managers"), ("dealer", "dealers")):
        tue = t.assign(v=t[g] / t.oi).pivot_table(index="date", columns="ccy", values="v")[CCY]
        px_tue = fxd.reindex(fxd.index.union(tue.index)).ffill(limit=2).reindex(tue.index)
        same = tue - tue.shift(1)
        ret_tue = px_tue / px_tue.shift(1) - 1
        last = nets[g] - nets[g].shift(1)
        for kind, x, rr in (("A same week", same, ret_tue), ("B next week", last, ret)):
            row = f"  {kind + ' - ' + nm:40}"
            for c in CCY:
                j = pd.concat([x[c], rr[c]], axis=1).dropna()
                r = j.iloc[:, 0].corr(j.iloc[:, 1]) if len(j) > 50 else np.nan
                corr[(g, kind[0], c)] = r
                row += f"{r:+7.2f}"
            lines.append(row)
    lines.append("")
    lev, am, dl = nets["lev"], nets["am"], nets["dealer"]
    z = (lev - lev.rolling(156, min_periods=104).mean()) / lev.rolling(156, min_periods=104).std()
    rules = {
        "LEV CROWD (fade |z| > 1.5)": (-np.sign(z)).where(z.abs() > 1.5, 0.0),
        "LEV FLOW (follow last week)": np.sign(lev - lev.shift(1)),
        "AM FLOW (follow last week)": np.sign(am - am.shift(1)),
        "AM LEVEL (side of their position)": np.sign(am),
        "DEALER FADE (against last week's change)": -np.sign(dl - dl.shift(1)),
    }
    lines.append("RULES (% a week; EXNESS is the verdict)")
    res = {}
    for nm, pos in rules.items():
        s_spot, s_carry, s_ex = fd.run(pos.reindex(columns=CCY).fillna(0.0), ret, nights, pol)
        a, b, e = fd.stat(s_spot, 52), fd.stat(s_carry, 52), fd.stat(s_ex, 52)
        res[nm] = e
        lines.append(f"  {nm:42} n {e['n']:5} | spot {a['mean'] * 100:+.3f} | +carry {b['mean'] * 100:+.3f} | EXNESS {e['mean'] * 100:+.3f} "
                     f"(tune {e['tu'] * 100:+.3f} t {e['t_tu']:+.1f} / holdout {e['ho'] * 100:+.3f} t {e['t_ho']:+.1f}) | "
                     f"{e['ann'] * 100:+.2f}%/yr")
    ps = sorted((res[n]["p"], n) for n in res)
    holm, run_max = {}, 0.0
    for r_, (p, n) in enumerate(ps):
        run_max = max(run_max, min(1.0, p * (len(ps) - r_)))
        holm[n] = run_max
    passes = [n for n in res if res[n]["tu"] > 0 and res[n]["ho"] > 0 and res[n]["t_tu"] >= 2 and res[n]["t_ho"] >= 2
              and holm[n] < 0.05]
    lines.append("  Holm p: " + ", ".join(f"{n.split(' (')[0]} {holm[n]:.2f}" for n in res) + f" | PASS: {passes or 'none'}")
    lines.append("")
    lines.append("REGISTERED PREDICTIONS")
    lv = [corr[("lev", "A", c)] for c in CCY]
    dv = [corr[("dealer", "A", c)] for c in CCY]
    t1 = np.mean(np.array(lv) >= 0.2) > 0.5 and np.mean(np.array(dv) <= -0.2) > 0.5
    lines.append(f"  T1 same week: leveraged " + ", ".join(f"{c} {v:+.2f}" for c, v in zip(CCY, lv)) + "; dealers " +
                 ", ".join(f"{c} {v:+.2f}" for c, v in zip(CCY, dv)) + f" -> {'RIGHT' if t1 else 'WRONG'}")
    nx = max(abs(v) for (g, k, c), v in corr.items() if k == "B" and np.isfinite(v))
    lines.append(f"  T2 largest next-week |corr| {nx:.2f} -> {'RIGHT' if nx < 0.10 else 'WRONG'}")
    lines.append(f"  T3 passes: {passes or 'none'} -> {'RIGHT' if not passes else 'WRONG'}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

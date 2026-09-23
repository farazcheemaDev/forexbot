"""THE STATS SHEET - main vs tight vs tight + time stop, on the corrected engine, from $221.

Everything the corrected engine knows (doc 03 #12-14): real entry times, funding per unit,
ENTRY-SIZED compounding (a position's dollars fixed from closed equity at entry, as the bot
does). 12 slots, 1000h gate, 0.30% risk per unit. 10 random orderings of simultaneous
entries; every figure is the average (or the pooled distribution) across them.

Two windows: HOLDOUT (2024-08-29 on - the planning window) and FULL (2020-02 on). Upside
is shown RAW and with the 3x hindsight haircut (the 12 coins were picked knowing how they
turned out); downside (losing months, worst month, drawdown) is always RAW, because the
haircut must never shrink a loss (CLAUDE.md, "Haircutting a LOSS").

Caveat that travels with every number: the time stop's RETURN gain is holdout-only (the
mined-split signature); its worst-month and drawdown gains show on both halves
(graveyard_rescore.py). Trust the downside rows more than the upside rows.

    python -m backtest.book_stats
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.expectations import haircut, month_ends, windows  # noqa: E402
from backtest.graveyard_rescore import rows  # noqa: E402

CAP = 221.0
SEEDS = tuple(range(10))


def path(rs, bear, seed, t_from=None):
    """Entry-sized equity path from CAP, plus the taken trades (R, side, hold days, t1)."""
    rng = np.random.default_rng(seed)
    tie = rng.random(len(rs))
    o = [rs[i] for i in sorted(range(len(rs)), key=lambda i: (rs[i]["t0"], tie[i]))]
    eq, opens, pend, pts, tr = CAP, [], [], [], []
    for r in o:
        t0 = pd.Timestamp(r["t0"])
        if t_from is not None and t0 < t_from:
            continue
        pend.sort(key=lambda x: x[0])
        while pend and pend[0][0] <= t0:
            t1, dol = pend.pop(0); eq = max(eq + dol, 0.0); pts.append((t1, eq))
        opens = [u for u in opens if u > t0]
        if len(opens) >= 12:
            continue
        t1 = pd.Timestamp(r["t1"])
        opens.append(t1)
        f = blend.RISK / 100.0 * (blend.REGIME_MULT if bool(bear.asof(t0)) else 1.0)
        pend.append((t1, r["R"] * f * eq))
        tr.append(dict(R=r["R"], side=r["side"], rule=r["rule"], days=(t1 - t0).days + (t1 - t0).seconds / 86400,
                       t1=t1, dollars_frac=r["R"] * f))
    for t1, dol in sorted(pend, key=lambda x: x[0]):
        eq = max(eq + dol, 0.0); pts.append((t1, eq))
    s = pd.Series([p[1] for p in pts], index=pd.DatetimeIndex([p[0] for p in pts]))
    return s.resample("D").last().ffill(), pd.DataFrame(tr)


def sheet(name, rs, bear, cut):
    print(f"\n{'=' * 92}\n  {name}\n{'=' * 92}")
    for wlab, t_from in (("HOLDOUT (2024-08-29 -> 2026-09, never tuned on)", cut),
                         ("FULL HISTORY (2020-02 -> 2026-09)", None)):
        P = [path(rs, bear, sd, t_from) for sd in SEEDS]
        cs = [p[0] for p in P]; T = pd.concat([p[1] for p in P])
        me = [month_ends(c) for c in cs]
        m1 = np.concatenate([windows(m, 1) for m in me])
        m12 = np.concatenate([windows(m, 12) for m in me])
        yrs = np.mean([(c.index[-1] - c.index[0]).days / 365.25 for c in cs])
        fin = np.array([c.iloc[-1] / CAP for c in cs])
        cagr_raw = fin ** (1 / yrs) - 1
        mo_raw = (1 + cagr_raw) ** (1 / 12) - 1
        mo_hc = (1 + cagr_raw / blend.HINDSIGHT) ** (1 / 12) - 1
        dd = np.array([(1 - c / c.cummax()).max() for c in cs])
        uw = []
        for c in cs:
            under = (c < c.cummax()).astype(int)
            runs = (under.groupby((under != under.shift()).cumsum()).cumsum() * under).max()
            uw.append(runs / 30.4)
        print(f"\n  {wlab}")
        print(f"    average month (compounded)    raw {np.mean(mo_raw)*100:+6.2f}%   "
              f"after 3x haircut {np.mean(mo_hc)*100:+6.2f}%")
        print(f"    median month                   raw {(np.median(m1)-1)*100:+6.2f}%")
        print(f"    months that lose money        {(m1 < 1).mean()*100:5.0f}%     "
              f"best month {(m1.max()-1)*100:+.0f}%   worst month {(m1.min()-1)*100:+.1f}%")
        g12 = np.array([haircut(x, 12) for x in m12])
        print(f"    a random 12 months             median raw {(np.median(m12)-1)*100:+.0f}%  "
              f"(haircut {(np.median(g12)-1)*100:+.0f}%)   25th pct raw {(np.percentile(m12, 25)-1)*100:+.0f}%   "
              f"P(12 months at a loss) {(m12 < 1).mean()*100:.0f}%")
        print(f"    ${CAP:.0f} after a typical 12 months  ${CAP*np.median(g12):,.0f} (haircut)   "
              f"${CAP*np.median(m12):,.0f} (raw)")
        print(f"    max drawdown (raw)             {dd.mean()*100:.0f}%  (range {dd.min()*100:.0f}-{dd.max()*100:.0f}% "
              f"across orderings)   longest time under water ~{np.mean(uw):.0f} months")
        L = T[T.side == "long"]
        n_mo = yrs * 12 * len(SEEDS)
        print(f"    trades taken                   {len(T)/n_mo:.1f}/month ({len(L)/n_mo:.1f} long, "
              f"{(len(T)-len(L))/n_mo:.1f} short)   long win rate {(L.R > 0).mean()*100:.0f}%   "
              f"short win rate {(T[T.side=='short'].R > 0).mean()*100:.0f}%")
        top = L.sort_values("R", ascending=False)
        share = top.R.head(max(len(top) // 20, 1)).sum() / L.R.sum() * 100 if L.R.sum() > 0 else np.nan
        print(f"    long trades: median {L.R.median():+.2f}R, mean {L.R.mean():+.2f}R, best {L.R.max():+.0f}R, "
              f"worst {L.R.min():+.1f}R; top 5% of longs = {share:.0f}% of long profit; "
              f"median hold {L.days.median():.1f} days")
        if t_from is None:
            yr = pd.concat([c.resample("YE").last() for c in cs], axis=1)
            yr = pd.concat([pd.DataFrame([[CAP] * len(cs)], index=[yr.index[0] - pd.offsets.YearEnd()],
                                         columns=yr.columns), yr])
            chg = (yr / yr.shift(1) - 1).iloc[1:].mean(axis=1) * 100
            print("    by calendar year (raw)        " + "  ".join(f"{d.year}: {v:+.0f}%" for d, v in chg.items()))


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    print(f"${CAP:.0f} start, 0.30% risk/unit, 12 slots, corrected engine, {len(SEEDS)} orderings")
    sheet("MAIN - the deployed rules", rows(), bear, cut)
    sheet("TIGHT EXIT - on paper", rows(tight=True), bear, cut)
    sheet("TIGHT EXIT + TIME STOP (below +2R after 100 bars)", rows(tight=True, time_stop=(100, 2.0)),
          bear, cut)


if __name__ == "__main__":
    main()

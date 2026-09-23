"""CRAZY RETURNS ON TINY CAPITAL - the real odds, on the corrected engine.

THE QUESTION (the user's mandate, restated 2026-09-23)
    "Crazy returns with as low capital as possible." There is no hidden strategy for that
    (docs 02 and 11). What exists is the one validated edge - the trend book, now tight exit +
    time stop - run at MUCH higher risk on money the owner can afford to lose. The honest
    deliverable is the ODDS: from $10 / $50 / $221, what is the chance of 2x, 5x, 10x within
    3, 6, 12 months, and what is the chance of being wiped out, at each risk level.

WHY doc 07's ODDS ARE NOT GOOD ENOUGH
    microacct.py (doc 07: "29.7% chance of 5x from $10") bootstrapped trades ONE AT A TIME
    (the doc itself says real ruin is higher, "the gap is unmeasured"), used a synthetic
    deflation of the edge, and ran on the pre-2026-09-23 engine (no funding, label t0, a
    compounding convention that doubles returns). This re-does it on REAL paths.

THE SIMULATION
    Rows: tight exit + time stop (below +2R after 100 bars), longs pyramided, shorts on,
    funding charged per unit, real entry times (graveyard_rescore.py machinery).
    Two universes:
      BOOK12  the 12 deployed coins - picked WITH HINDSIGHT (3x premium on CAGR; there is no
              clean way to deflate a probability of 10x, so these odds are OPTIMISTIC)
      PIT12   the point-in-time top-12 perps by the PRIOR month's volume, dead coins included
              (wide_book.eligibility) - no hindsight, the honest one
    Account: entry-sized (a position's dollars fixed from closed equity at entry). A unit is
    skipped if its notional is under Bitget's $5 minimum; a new position is skipped if it
    would take gross notional past 10x equity (lev_test.py: liquidation bites above 10x). A
    path is RUINED when equity falls below 10% of the start (or below the $5 minimum).
    Starts: the first day of every month, 2020-07 .. 2025-09, each run 3 / 6 / 12 months,
    3 orderings each. Overlapping windows - these are historical frequencies, not
    independent draws.

REGISTERED PREDICTIONS (before running)
    1. BOOK12 at the deployed 0.30% from $221: P(2x in 12 months) ~40%, P(5x) ~10%, ruin ~0%.
    2. Raising risk raises P(5x) up to ~1-2% per unit, then ruin climbs steeply; at 4% per
       unit ruin exceeds 50%.
    3. PIT12 is far worse at every risk: P(5x in 12 months) under 5% anywhere.
    4. $10 is worse than $221 at low risk (the $5 minimum rejects units) and similar at high
       risk (big units clear the minimum).

    python -m backtest.lottery
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.causal_t0 import LATE, real_t0  # noqa: E402
from backtest.convex import run_uncapped  # noqa: E402
from backtest.engine_variants import break_map  # noqa: E402
from backtest.graveyard_rescore import rows as book_rows, walk  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from backtest.timeframes import resample  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402

PERPS = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "perps"
RULES = ("1h", "4h", "12h")
MIN_ORDER = 5.0
LEV_CAP = 10.0
RUIN = 0.10
TS = (100, 2.0)
RISKS = (0.003, 0.006, 0.01, 0.02, 0.04)
CAPS = (10.0, 50.0, 221.0)
HORIZONS = (3, 6, 12)
SEEDS = (0, 1, 2)


# ---------------------------------------------------------------- PIT rows -----------
def _pit_coin(sym, months):
    f = PERPS / f"{sym}_1h.csv.gz"
    if not f.exists():
        return []
    d = pd.read_csv(f, usecols=["time", "open", "high", "low", "close", "qvol"])
    d = d.rename(columns={"qvol": "volume"})
    d["time"] = pd.to_datetime(d["time"]).astype("datetime64[ns]")
    d = d[d.close > 0].drop_duplicates("time").sort_values("time").reset_index(drop=True)
    gap = d.time.diff().dt.total_seconds().fillna(3600) / 3600
    if (gap > 48).any():
        d = d.iloc[:int(np.argmax(gap.values > 48))].reset_index(drop=True)
    if len(d) < 600:
        return []
    fu = pd.read_csv(PERPS / f"{sym}_funding.csv.gz")
    fu["time"] = pd.to_datetime(fu["time"]).dt.floor("h").astype("datetime64[ns]")
    fu = fu.groupby("time", as_index=False)["rate"].sum()          # one row per settlement hour
    fts = fu["time"].astype("int64").to_numpy()
    px1 = pd.Series(d["open"].to_numpy(float), index=d["time"])
    fpx = px1.reindex(px1.index.union(pd.DatetimeIndex(fts))).ffill().reindex(pd.DatetimeIndex(fts)).to_numpy()
    rp = np.nan_to_num(fu["rate"].to_numpy(float) * fpx)
    cs = np.r_[0.0, np.cumsum(rp)]

    def paid(a, b):
        ia = np.searchsorted(fts, pd.Timestamp(a).value, side="right")
        ib = np.searchsorted(fts, pd.Timestamp(b).value, side="right")
        return cs[ib] - cs[ia]

    out = []
    for rule in RULES:
        df = resample(d, rule)
        if len(df) < 300:
            continue
        late = LATE[rule]
        mid = pd.Timedelta(hours=1) - pd.Timedelta(hours=int(rule[:-1])) / 2
        tb = break_map(df, rule)
        for r in walk(df, rule, sym, tb=tb, time_stop=TS):
            if pd.Timestamp(r["t0"]).strftime("%Y-%m") not in months:
                continue
            e0 = float(df["open"].to_numpy()[np.searchsorted(df["time"].to_numpy(), r["t0"])])
            risk = r["sf"] * e0
            t_exit = pd.Timestamp(r["t1"]) + mid
            tot = sum(paid(pd.Timestamp(ta) - late, t_exit) for ta in r["adds"]
                      if pd.Timestamp(ta) - late < t_exit)
            out.append(dict(r, R=r["R"] - tot / risk))
        a = atr_ind(df, 14).to_numpy(float); o = df["open"].to_numpy(float)
        t = df["time"].to_numpy()
        R, idx, bars, _d = run_uncapped(df, signals(df, "short", "all"), sl_mult=blend.SL_MULT,
                                        fee_bp=blend.FEE_BP, mode="trail_atr",
                                        trail=blend.SHORT_TRAIL, be_at=blend.BE_AT)
        for rr, i, b in zip(R, idx, bars):
            j = max(int(i) - int(b), 0)
            if pd.Timestamp(t[j]).strftime("%Y-%m") not in months or j < 1:
                continue
            risk = blend.SL_MULT * a[j - 1]
            if not np.isfinite(risk) or risk <= 0 or risk / o[j] < 0.001:   # frozen-price guard
                continue
            got = paid(pd.Timestamp(t[j]) - late, pd.Timestamp(t[int(i)]) + mid)
            out.append(dict(t0=t[j], t1=t[int(i)], R=float(rr) + got / risk, side="short",
                            sf=risk / o[j], adds=[t[j]], coin=sym, rule=rule))
    return out


def pit_rows(top_n=12):
    elig = eligibility(top_n)
    syms = [s for s, m in elig.items() if m and (PERPS / f"{s}_1h.csv.gz").exists()]
    rows = []
    for s in syms:
        rows += _pit_coin(s, elig[s])
    rows = [dict(r, R=float(np.clip(r["R"], -60, 5000))) for r in rows if np.isfinite(r["R"])]
    return real_t0(rows)


# ---------------------------------------------------------------- account ------------
def run(rows, bear, cap, risk, start, months, seed, slots=12):
    """Entry-sized account over [start, start+months). Returns (end multiple, max multiple,
    ruined, share of units rejected for size)."""
    end = start + pd.DateOffset(months=months)
    t0s = rows_t0(rows)
    a = np.searchsorted(t0s, start.value); b = np.searchsorted(t0s, end.value)
    sel = rows[a:b]
    rng = np.random.default_rng(seed)
    tie = rng.random(len(sel))
    o = [sel[i] for i in sorted(range(len(sel)), key=lambda i: (sel[i]["t0"], tie[i]))]
    eq, peak, opens, pend = cap, cap, [], []
    skipped = taken = 0
    ruined = False
    for r in o:
        t0 = pd.Timestamp(r["t0"])
        pend.sort(key=lambda x: x[0])
        while pend and pend[0][0] <= t0:
            _t1, dol, _n = pend.pop(0)
            eq = max(eq + dol, 0.0); peak = max(peak, eq)
            if eq < cap * RUIN or eq < MIN_ORDER:
                ruined = True
        if ruined:
            break
        opens = [x for x in opens if x[0] > t0]
        if len(opens) >= slots:
            continue
        f = risk * (blend.REGIME_MULT if bool(bear.asof(t0)) else 1.0)
        unit = eq * f / max(r["sf"], 1e-4)
        if unit < MIN_ORDER:
            skipped += 1; continue
        gross = sum(n_units(x, t0) * x[1] for x in opens)
        if gross + unit > LEV_CAP * eq:
            skipped += 1; continue
        taken += 1
        t1 = pd.Timestamp(r["t1"])
        opens.append((t1, unit, [pd.Timestamp(a) for a in r["adds"]]))
        pend.append((t1, r["R"] * f * eq, len(r["adds"])))
    if not ruined:
        for _t1, dol, _n in sorted(pend, key=lambda x: x[0]):
            eq = max(eq + dol, 0.0); peak = max(peak, eq)
            if eq < cap * RUIN:
                ruined = True; break
    return eq / cap, peak / cap, ruined, skipped / max(skipped + taken, 1)


_T0: dict = {}


def rows_t0(rows):
    """int64 ns entry times of rows that are already sorted by t0 (cached per list)."""
    k = id(rows)
    if k not in _T0:
        _T0[k] = np.array([pd.Timestamp(r["t0"]).value for r in rows], dtype=np.int64)
    return _T0[k]


def n_units(x, t):
    return sum(1 for a in x[2] if a <= t)


def main():
    bear = regimes()[1000]
    uni = {"BOOK12 (hindsight coins - optimistic)": book_rows(tight=True, time_stop=TS),
           "PIT12 (no hindsight - honest)": pit_rows(12)}
    uni = {k: sorted(v, key=lambda r: pd.Timestamp(r["t0"]).value) for k, v in uni.items()}
    starts = pd.date_range("2020-07-01", "2025-09-01", freq="MS")
    for lab, rows in uni.items():
        print(f"\n{'=' * 100}\n  {lab}: {len(rows):,} positions | tight exit + time stop | "
              f"entry-sized, $5 minimum, 10x gross cap, ruin = -90%\n{'=' * 100}")
        for H in HORIZONS:
            print(f"\n  horizon {H} months, {len(starts) if H == 12 else len(starts)} monthly starts x "
                  f"{len(SEEDS)} orderings")
            print(f"  {'capital':>8}{'risk/unit':>10}{'median x':>10}{'P(>=2x)':>9}{'P(>=5x)':>9}"
                  f"{'P(>=10x)':>10}{'touch 5x':>10}{'RUINED':>8}{'P(loss)':>9}{'rejected':>10}")
            for cap in CAPS:
                for risk in RISKS:
                    st = [s for s in starts if s + pd.DateOffset(months=H) <= pd.Timestamp("2026-09-15")]
                    res = np.array([run(rows, bear, cap, risk, s, H, sd) for s in st for sd in SEEDS],
                                   dtype=float)
                    endx, peakx, ru, rej = res[:, 0], res[:, 1], res[:, 2], res[:, 3]
                    print(f"  ${cap:>7.0f}{risk*100:>9.1f}%{np.median(endx):>9.2f}x"
                          f"{(endx >= 2).mean()*100:>8.0f}%{(endx >= 5).mean()*100:>8.0f}%"
                          f"{(endx >= 10).mean()*100:>9.0f}%{(peakx >= 5).mean()*100:>9.0f}%"
                          f"{ru.mean()*100:>7.0f}%{(endx < 1).mean()*100:>8.0f}%{rej.mean()*100:>9.0f}%")
                print()


if __name__ == "__main__":
    main()

"""THE TOKYO "GOTOBI" EFFECT ON USD/JPY - a forced dollar flow before the 9:55 JST fix, 19 years of minute bars (2026-11-04)

The user, 2026-11-04: "i said in forex, try some different strategy". Every forex family in this repo is dead (doc 02: calendar anomalies, carry, momentum, breakouts, news, ML lead-lag, scalping), so this picks one MECHANISM that is not in the graveyard
and belongs to the family that has worked here (forced flow, not prediction): on Japanese "gotobi" days - the 5th, 10th, 15th, 20th, 25th and the month-end - Japanese importers must settle payments in dollars, and corporate dollar demand is
concentrated in the Tokyo morning before the 9:55 JST fixing (00:55 UTC all year; Japan has no daylight saving). If the flow is real, USD/JPY should drift UP between the Tokyo open (09:00 JST = 00:00 UTC) and the fix on those days, and not on others.

DESIGN. HistData USD/JPY 1-minute bid bars, 2007-2026 (strategy_analysis/data/histdata/USDJPY.parquet, t = minute start in ms UTC). Per weekday, long from the OPEN of the entry minute to the OPEN of the exit minute (bars up to 3 minutes late are accepted, else the day is
skipped). Windows: W1 00:00 -> 00:55 UTC (Tokyo open to the fix; the primary), W2 23:00 the evening before -> 00:55, W3 00:00 -> 02:00. Gotobi definitions: D1 = day 5 / 10 / 15 / 20 / 25 when it is a weekday, plus the last weekday of the month; D2 = D1 with a gotobi on a weekend moved
to the PRECEDING Friday; D3 = moved to the FOLLOWING Monday (Japanese holidays are NOT modelled - a limitation that can only dilute the effect). Cost: 1.2 pips of price (0.012 yen) per round trip (Exness-like spread plus slippage), also 2.4 pips. Control: the other weekdays, same window; placebo: EUR/USD, same
days and windows. Halves: the first 60% of gotobi days (tune) and the last 40% (holdout). Holm over the 9 cells.

REGISTERED BEFORE THE FIRST RUN (2026-11-04)
    G1  In W1 the long drift on gotobi days is positive, +1 to +4 bp gross, and exceeds the other weekdays by a difference with t >= 2 over the full sample (prior 65%).
    G2  Net of 1.2 pips the primary cell (W1, D1) is positive but small (< +2 bp) and does NOT have t >= 2 on both halves; the holdout is weaker than the tune half (prior 75%).
    G3  The EUR/USD placebo shows nothing (no cell with |t| >= 2 on both halves).
    G4  Of the three windows W1 (ending at the fix) is the best, not W3.
    G5  PASS (primary cell net > 0 with t >= 2 on BOTH halves AND a significant excess over the other days) has prior 20%.

RESULT (2026-11-04, logs/fx_gotobi.txt; 5,151 weekdays 2007-01..2026-09, 1,076 gotobi days under D1)
    There is no gotobi drift in the fix window. W1, D1: +0.72 bp gross on gotobi days against +0.91 bp on the other weekdays (difference t -0.4); net of 1.2 pips -0.38 bp (t -0.9; tune -0.37, holdout -0.40). 2019 onwards +0.50 vs +0.32 (t +0.3); by year the two series differ by +-3 bp at random.
    The earlier window W2 (from 08:00 JST) is the best cell: D2 +1.87 gross vs +0.48 on other days (excess +1.4 bp, raw t +2.4, one of nine looks), net +0.76 bp (t +1.5; tune +0.87, holdout +0.61): Holm rejects nothing, and the net is under the standard error of a 14 bp trade. After the fix (W3) USD/JPY falls
    on gotobi days (-1.6 bp over 00:00-02:00 vs -0.2), a post-hoc observation. A side finding on EVERY day: the dollar rises in the 55 minutes after the Tokyo open (USD/JPY +0.9 bp, EUR/USD -0.8 bp), about the size of the cost. Scale: one standard lot nets -USD 3.79 a trade, 54 trades a year.
    Predictions: G1 wrong (the excess is -0.4 bp, t -0.4), G2 wrong on the sign (net is negative; the 'not t >= 2 on both halves' part right), G3 literally wrong (long EUR/USD loses cost plus its Tokyo-morning drift on every day; the gotobi-vs-other EXCESS on EUR/USD is null, |t| <= 0.9, which was the intent), G4 wrong (W2 is the best, W3 the worst), G5 right (no PASS).
    Tests: 10; 22 of 22 planted bugs caught. A time-unit trap (a DatetimeIndex whose asi8 is not nanoseconds emptied every window on the first run) was caught by the empty-result guard and now has a test.

    python -m backtest.fx_gotobi          writes logs/fx_gotobi.txt        tests: python tests/test_fx_gotobi.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

WINDOWS = {"W1 00:00-00:55": (0, 55), "W2 23:00(-1d)-00:55": (-60, 55), "W3 00:00-02:00": (0, 120)}
DEFS = ("D1", "D2", "D3")
PIP = 0.01                       # one USD/JPY pip, in yen
COST_PIPS = 1.2
MAX_LATE_MIN = 3
GOTOBI_DAYS = (5, 10, 15, 20, 25)


def gotobi_days(dates, definition):
    """Boolean per weekday date: is it a gotobi settlement day under D1 / D2 / D3?"""
    out = np.zeros(len(dates), bool)
    idx = {d: i for i, d in enumerate(pd.DatetimeIndex(dates).normalize())}
    ds = pd.DatetimeIndex(dates).normalize()
    months = sorted({(d.year, d.month) for d in ds})
    for y, mo in months:
        month_end = pd.Timestamp(year=y, month=mo, day=1) + pd.offsets.MonthEnd(0)
        targets = [pd.Timestamp(year=y, month=mo, day=d) for d in GOTOBI_DAYS] + [month_end]
        for tg in targets:
            if tg.dayofweek < 5:
                hit = tg
            elif definition == "D1":
                continue
            elif definition == "D2":
                hit = tg - pd.Timedelta(days=tg.dayofweek - 4)          # Saturday -> Friday, Sunday -> Friday
            else:
                hit = tg + pd.Timedelta(days=7 - tg.dayofweek)          # Saturday / Sunday -> Monday
            if hit in idx:
                out[idx[hit]] = True
        # the last weekday of the month is always month-end
        lw = month_end
        while lw.dayofweek >= 5:
            lw -= pd.Timedelta(days=1)
        if lw in idx:
            out[idx[lw]] = True
    return out


def window_returns(df, dates, entry_min, exit_min):
    """(long return in bp, entry price) per date, open of the entry minute to open of the exit minute, minutes counted from 00:00 UTC of the date (negative = the evening before). NaN where a bar is missing by more than MAX_LATE_MIN."""
    t = df["t"].to_numpy(dtype="int64")
    o = df["o"].to_numpy(dtype="float64")
    day0 = pd.DatetimeIndex(dates).normalize().as_unit("ns").asi8 // 10**6          # ms at 00:00 UTC (force ns: a [ms] or [us] index would silently empty every window)
    tgt_in, tgt_out = day0 + entry_min * 60_000, day0 + exit_min * 60_000
    out, px = np.full(len(day0), np.nan), np.full(len(day0), np.nan)
    for k, (a, b) in enumerate(zip(tgt_in, tgt_out)):
        i = int(np.searchsorted(t, a, side="left"))
        j = int(np.searchsorted(t, b, side="left"))
        if i >= len(t) or j >= len(t):
            continue
        if t[i] - a > MAX_LATE_MIN * 60_000 or t[j] - b > MAX_LATE_MIN * 60_000:
            continue
        out[k] = (o[j] / o[i] - 1) * 1e4
        px[k] = o[i]
    return out, px


def cost_bp(price, pips=COST_PIPS, pip=PIP):
    """Round-trip cost in bp of the price level: pips x the pip size (0.01 yen; 0.0001 for EUR/USD) / price."""
    return pips * pip / price * 1e4


def welch_t(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float((a.mean() - b.mean()) / se)


def one_sample_t(x):
    x = np.asarray(x, float)
    return float(x.mean() / (x.std(ddof=1) / math.sqrt(len(x)))) if len(x) > 2 else float("nan")


def p_one_sided(t):
    return 0.5 * math.erfc(t / math.sqrt(2))


def holm(ps, alpha=0.05):
    """Holm step-down: which of the p-values are rejected at alpha."""
    order = np.argsort(ps)
    rej = np.zeros(len(ps), bool)
    for rank, i in enumerate(order):
        if ps[i] <= alpha / (len(ps) - rank):
            rej[i] = True
        else:
            break
    return rej


def split_60_40(n):
    """Boolean mask of the first 60% (tune) of n date-ordered items."""
    m = np.zeros(n, bool)
    m[:int(n * 0.6)] = True
    return m


def cell(df, dates, gmask, entry_min, exit_min, pips=COST_PIPS, pip=PIP):
    """Summary of one (window, definition) cell: gotobi vs other days, gross and net, tune / holdout."""
    r, price = window_returns(df, dates, entry_min, exit_min)
    assert np.isfinite(r).mean() > 0.5, "most windows found no bar - check the time units"
    c = cost_bp(price, pips, pip)
    ok = np.isfinite(r)
    g, ng = ok & gmask, ok & ~gmask
    net = r - c
    gi = np.flatnonzero(g)
    tune = np.zeros(len(r), bool)
    tune[gi[split_60_40(len(gi))]] = True
    hold = g & ~tune
    return dict(n=int(g.sum()), gross=float(r[g].mean()), other=float(r[ng].mean()), diff_t=welch_t(r[g], r[ng]), net=float(net[g].mean()), net_t=one_sample_t(net[g]),
                tune=float(net[tune].mean()), tune_t=one_sample_t(net[tune]), hold=float(net[hold].mean()), hold_t=one_sample_t(net[hold]),
                dbl=float((r - cost_bp(price, 2 * pips, pip))[g].mean()), dbl_t=one_sample_t((r - cost_bp(price, 2 * pips, pip))[g]), r=r, cost=c, g=g, ng=ng)


def run_pair(df, dates, pip=PIP):
    res = {}
    for dn in DEFS:
        gm = gotobi_days(dates, dn)
        for wn, (a, b) in WINDOWS.items():
            res[(wn, dn)] = cell(df, dates, gm, a, b, pip=pip)
    return res


def table(res, title):
    out = [title, f"   {'window':<22}{'def':>4}{'gotobi n':>9}{'gross bp':>9}{'others bp':>10}{'diff t':>7}{'net bp':>8}{'t':>6}{'tune':>7}{'t':>6}{'hold':>7}{'t':>6}{'2x cost':>8}{'t':>6}"]
    for (wn, dn), v in res.items():
        out.append(f"   {wn:<22}{dn:>4}{v['n']:>9}{v['gross']:>+9.2f}{v['other']:>+10.2f}{v['diff_t']:>+7.1f}{v['net']:>+8.2f}{v['net_t']:>+6.1f}{v['tune']:>+7.2f}{v['tune_t']:>+6.1f}{v['hold']:>+7.2f}{v['hold_t']:>+6.1f}{v['dbl']:>+8.2f}{v['dbl_t']:>+6.1f}")
    return out


def main():
    from backtest.histdata_1m import load
    d = load("USDJPY")
    e = load("EURUSD")
    t0 = pd.to_datetime(d["t"].min(), unit="ms").normalize()
    dates = pd.bdate_range(t0 + pd.Timedelta(days=1), pd.to_datetime(d["t"].max(), unit="ms").normalize() - pd.Timedelta(days=1))
    out = [f"backtest/fx_gotobi.py - USD/JPY 1-minute bid bars {t0.date()}..{dates[-1].date()}, {len(dates)} weekdays; cost {COST_PIPS} pips a round trip", ""]
    res = run_pair(d, dates)
    out += table(res, "USD/JPY, LONG, gotobi days (net of cost; tune = first 60% of gotobi days, holdout = last 40%)")
    ps = np.array([p_one_sided(v["net_t"]) for v in res.values()])
    rej = holm(ps)
    keys = list(res.keys())
    out.append(f"\n   Holm over the 9 cells (one-sided, net > 0): rejected = {[k for k, r in zip(keys, rej) if r]}")
    k0 = ("W1 00:00-00:55", "D1")
    v = res[k0]
    out.append("\nPRIMARY CELL by year (W1, D1): mean gross bp on gotobi days vs other weekdays")
    yrs = pd.DatetimeIndex(dates).year.to_numpy()
    out.append(f"   {'year':>5}{'gotobi n':>9}{'gotobi bp':>10}{'others bp':>10}{'net bp':>8}")
    for y in sorted(set(yrs)):
        gy = v["g"] & (yrs == y)
        ny = v["ng"] & (yrs == y)
        if gy.sum() >= 3:
            out.append(f"   {y:>5}{int(gy.sum()):>9}{v['r'][gy].mean():>+10.2f}{v['r'][ny].mean():>+10.2f}{(v['r'][gy] - v['cost'][gy]).mean():>+8.2f}")
    last = yrs >= 2019
    gl, nl = v["g"] & last, v["ng"] & last
    out.append(f"   2019 onwards: gotobi {v['r'][gl].mean():+.2f} bp (n {int(gl.sum())}) vs others {v['r'][nl].mean():+.2f}; difference t {welch_t(v['r'][gl], v['r'][nl]):+.1f}")
    dow = pd.DatetimeIndex(dates).dayofweek.to_numpy()
    out.append("   by weekday of the gotobi day (gross bp): " + "  ".join(f"{n} {v['r'][v['g'] & (dow == i)].mean():+.2f} (n {int((v['g'] & (dow == i)).sum())})" for i, n in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri"])))
    pres = run_pair(e, dates, pip=0.0001)
    out += ["", ] + table(pres, "PLACEBO - EUR/USD, LONG, the same days and windows (no Japanese flow expected)")
    out.append("\nSCALE (descriptive): the primary cell's net edge on a position of 1 standard lot (USD 100,000):")
    n_year = v["n"] / (len(dates) / 260.0)
    out.append(f"   {v['n']} gotobi days in {len(dates) / 260.0:.1f} years = {n_year:.0f} trades a year; net {v['net']:+.2f} bp x USD 100,000 = USD {v['net'] / 1e4 * 100000:+.2f} a trade, USD {v['net'] / 1e4 * 100000 * n_year:+.0f} a year; the 55-minute standard deviation is {np.nanstd(v['r'][v['g']]):.1f} bp = USD {np.nanstd(v['r'][v['g']]) / 1e4 * 100000:.0f} a trade")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "fx_gotobi.txt").write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

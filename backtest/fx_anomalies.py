"""FOREX / METALS / INDICES: NINE DOCUMENTED CALENDAR AND SESSION EFFECTS, AT EXNESS COSTS.

Asked 2026-09-25: "go back to the roots... try different strategies for forex". Everything tried in
forex so far (doc 02, backtest/forex.py; strategy_analysis/his_strategy.md) was a TREND or FADE rule on
price bars: dead on FX majors, dead on indices, gold one-regime, silver a thin lead. This tests a
different family - effects documented in published research, each with a stated cause - none of
them tried here before. Costs are Exness's, measured in forex.py (spread round trip, swap per
night held); a result must be positive AFTER costs on BOTH halves (first 60% / last 40% by date),
and the family is Holm-corrected.

  T1  NDX OVERNIGHT      long the Nasdaq-100 from the cash close to the next cash open, daily.
                         Cause: returns accrue outside cash hours (Cooper-Cliff-Gulen 2008; Kelly-
                         Clark 2011 "Returns in trading versus non-trading hours").
  T2  SPX OVERNIGHT      the same on the S&P 500.
  T3  NDX TURN OF MONTH  long from the close two trading days before month end to the close of the
                         3rd trading day of the new month (days -1..+3). Cause: month-start flows
                         (Lakonishok-Smidt 1988; Ariel 1987).
  T4  SPX TURN OF MONTH  the same on the S&P 500.
  T5  GOLD OUTSIDE NY    long gold 22:00-13:00 UTC (Asia + London), flat in New York hours.
                         Cause: physical buying in Asian hours, futures selling in US hours (the
                         widely reported "gold is a night-time asset" pattern).
  T6  SILVER OUTSIDE NY  the same on silver.
  T7  FX HOME-HOURS      EURUSD & GBPUSD long 13-21 UTC and short 07-12 UTC; USDJPY long 00-07 UTC
                         and short 13-21 UTC. Cause: a currency weakens during its own country's
                         working hours as local investors buy foreign assets (Breedon-Ranaldo 2013,
                         "Intraday patterns in FX returns and order flow").
  T8  MONTH-END USD      on the last trading day, long EURUSD (short USD) from the prior close if US
                         equities beat European equities month-to-date, else short. Cause: foreign
                         holders re-hedge USD equity gains at the month-end fix (Melvin-Prins 2015).
  T9  NDX INTRADAY       long open-to-close, daily - the complement of T1, reported as the control.

DATA: ^NDX, ^GSPC, ^STOXX50E, EURUSD=X daily from Yahoo (1999/2003/2007-2026, cached to
strategy_analysis/data/yf_*.csv); gold, silver and FX majors H1 from MT5 (2020-02 to 2026-09, bar
hours are UTC - forex.py). The index CFDs have only a year on MT5, so the index tests use the cash
index and charge the CFD's costs.
COSTS: USTECm 0.77bp spread + 2.04bp/night; US500 taken as US30m's 0.38bp + 1.83bp/night; gold
1.22bp + 1.25bp/night; silver 9.52bp + 1.33bp/night; FX 1.29-1.48bp + 0.49bp/night. Swap on a
Friday-to-Monday hold is charged 3 nights.

REGISTERED PREDICTION (2026-09-25, before running):
  T1 T2  overnight gross > intraday gross; NET positive on both halves (the documented effect is ~2-4bp
         a night, costs ~2.8bp): borderline - I expect T1 to pass one half and fail the other.
  T3 T4  turn-of-month positive on both halves, net of ~9bp; the strongest candidate in the family.
  T5     gold outside NY positive both halves; NY-hours gold negative; passes net of 2.5bp.
  T6     silver dies on its 9.5bp spread.
  T7     the direction is right (positive gross) and it dies on costs (~2.8bp a day for ~1-2bp).
  T8     right sign in ~55-60% of months, too few months to pass Holm.
  T9     intraday gross near zero or negative.
  Expected survivors after Holm and both halves: T3 and/or T5 - at most two of nine.

    python -m backtest.fx_anomalies
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "strategy_analysis" / "data"
HOLD = 0.60
COST = {"NDX": (0.77, 2.04), "SPX": (0.38, 1.83), "XAU": (1.22, 1.25), "XAG": (9.52, 1.33),
        "EURUSD": (1.39, 0.49), "GBPUSD": (1.48, 0.49), "USDJPY": (1.29, 0.49)}   # bp, bp/night


def yf_daily(ticker, start="1999-01-01"):
    f = DATA / f"yf_{ticker.replace('^', '').replace('=', '_')}.csv"
    if f.exists():
        d = pd.read_csv(f, parse_dates=["Date"], index_col="Date")
    else:
        import yfinance as yf
        warnings.filterwarnings("ignore")
        d = yf.download(ticker, start=start, progress=False, auto_adjust=False)
        d.columns = d.columns.get_level_values(0)
        d = d[["Open", "High", "Low", "Close"]].dropna()
        d.index.name = "Date"
        d.to_csv(f)
    return d[(d.Open > 0) & (d.Close > 0)]


def mt5_h1(sym):
    d = pd.DataFrame(json.load(open(DATA / f"{sym}m_1h_2400d.json")))
    d["t"] = pd.to_datetime(d.t, unit="ms")
    return d.set_index("t")[["o", "h", "l", "c"]]


def nights(a, b):
    """Calendar nights between two timestamps (a Friday-to-Monday hold is 3)."""
    return max((pd.Timestamp(b).normalize() - pd.Timestamp(a).normalize()).days, 0)


def verdict(name, r, t, note=""):
    """r: net returns per trade (fraction), t: their dates. Both halves by date."""
    r, t = np.asarray(r, float), pd.DatetimeIndex(t)
    cut = t.sort_values()[int(len(t) * HOLD)]
    a, b = r[t < cut], r[t >= cut]
    se = r.std(ddof=1) / np.sqrt(len(r))
    return dict(name=name, n=len(r), mean=r.mean() * 1e4, t=r.mean() / se, tune=a.mean() * 1e4,
                hold=b.mean() * 1e4, win=(r > 0).mean() * 100, yr=r.sum() / ((t.max() - t.min()).days / 365.25) * 100,
                note=note, cut=cut)


def index_tests(tag, tk):
    d = yf_daily(tk)
    sp, sw = COST[tag]
    o, c = d.Open.to_numpy(), d.Close.to_numpy()
    idx = d.index
    out = []
    # overnight: close[i-1] -> open[i]; nights = calendar nights between the two dates
    on_g = o[1:] / c[:-1] - 1
    nn = np.array([nights(idx[i - 1], idx[i]) for i in range(1, len(idx))])
    on_n = on_g - sp / 1e4 - sw / 1e4 * nn
    out.append(verdict(f"{tag} overnight (close->open)", on_n, idx[1:],
                       f"gross {on_g.mean()*1e4:+.2f}bp/night"))
    intr_g = c / o - 1
    out.append(verdict(f"{tag} intraday (open->close)", intr_g - sp / 1e4, idx,
                       f"gross {intr_g.mean()*1e4:+.2f}bp/day"))
    # turn of month: enter at the close of trading day -2, exit at the close of day +3
    m = pd.Series(idx.to_period("M"), index=idx)
    last = m != m.shift(-1)
    pos_end = np.flatnonzero(last.to_numpy())
    rs, ts, others = [], [], []
    for k in pos_end:
        i0, i1 = k - 1, k + 3
        if i0 < 0 or i1 >= len(idx):
            continue
        g = c[i1] / c[i0] - 1
        rs.append(g - sp / 1e4 - sw / 1e4 * nights(idx[i0], idx[i1]))
        ts.append(idx[k])
    tom = verdict(f"{tag} turn of month (days -1..+3)", rs, ts)
    # the same 4-day hold at every other start, for the control
    ctrl = [c[i + 4] / c[i] - 1 for i in range(0, len(c) - 4)]
    tom["note"] = f"gross {np.mean(np.asarray(rs) + sp / 1e4)*1e4:+.1f}bp vs any 4-day hold {np.mean(ctrl)*1e4:+.1f}bp"
    out.append(tom)
    return out


def session(d, h0, h1):
    """Per UTC day: return from the open of the first bar at hour h0 to the close of the last bar
    before hour h1 (wrapping past midnight when h0 > h1). Returns (date, gross return, nights)."""
    rows = []
    hrs = d.index.hour
    days = d.index.normalize()
    if h0 < h1:
        m = (hrs >= h0) & (hrs < h1)
        g = d[m].groupby(days[m])
        for day, x in g:
            if len(x) >= (h1 - h0) - 1:
                rows.append((day, x.c.iloc[-1] / x.o.iloc[0] - 1, 0))
    else:                                       # e.g. 22 -> 13: starts on day D at h0, ends D+1 at h1
        start = d[hrs == h0]
        for t0, r0 in start.iterrows():
            end = t0 + pd.Timedelta(hours=(24 - h0) + h1 - 1)
            if end in d.index and (end - t0) < pd.Timedelta(hours=26):
                rows.append((t0.normalize(), d.loc[end, "c"] / r0.o - 1, 1 if t0.weekday() != 4 else 3))
    return rows


def main():
    res = []
    res += index_tests("NDX", "^NDX")
    res += index_tests("SPX", "^GSPC")

    for tag, sym in (("XAU", "XAU"), ("XAG", "XAG")):
        d = mt5_h1(sym + "USD")
        sp, sw = COST[tag]
        rows = session(d, 22, 13)
        r = [g - sp / 1e4 - sw / 1e4 * n for _, g, n in rows]
        ny = session(d, 13, 21)
        res.append(verdict(f"{tag} long 22-13 UTC (outside NY)", r, [x[0] for x in rows],
                           f"gross {np.mean([x[1] for x in rows])*1e4:+.2f}bp; NY hours gross "
                           f"{np.mean([x[1] for x in ny])*1e4:+.2f}bp"))

    # T7: home-hours depreciation, one daily book per pair
    fx_r, fx_t, notes = [], [], []
    for pair, (lo, lc, so, sc) in {"EURUSD": (13, 21, 7, 12), "GBPUSD": (13, 21, 7, 12),
                                  "USDJPY": (0, 7, 13, 21)}.items():
        d = mt5_h1(pair)
        sp, _ = COST[pair]
        L = {day: g for day, g, _ in session(d, lo, lc)}
        S = {day: g for day, g, _ in session(d, so, sc)}
        both = sorted(set(L) & set(S))
        for day in both:
            fx_r.append(L[day] - S[day] - 2 * sp / 1e4)
            fx_t.append(day)
        notes.append(f"{pair} long-leg {np.mean(list(L.values()))*1e4:+.2f}bp short-leg {np.mean(list(S.values()))*1e4:+.2f}bp")
    res.append(verdict("FX home-hours (3 pairs, 2 legs a day)", fx_r, fx_t, "; ".join(notes)))

    # T8: month-end USD rebalancing
    spx, sx5, eur = yf_daily("^GSPC"), yf_daily("^STOXX50E"), yf_daily("EURUSD=X")
    common = spx.index.intersection(sx5.index).intersection(eur.index)
    spx, sx5, eur = spx.loc[common], sx5.loc[common], eur.loc[common]
    per = pd.Series(common.to_period("M"), index=common)
    last = np.flatnonzero((per != per.shift(-1)).to_numpy())
    r8, t8, hits = [], [], 0
    for k in last:
        first = np.flatnonzero((per == per.iloc[k]).to_numpy())[0]
        if k < 2 or first == 0:
            continue
        mtd_us = spx.Close.iloc[k - 1] / spx.Close.iloc[first - 1] - 1
        mtd_eu = sx5.Close.iloc[k - 1] / sx5.Close.iloc[first - 1] - 1
        sgn = 1 if mtd_us > mtd_eu else -1                     # US outperformed -> USD sold -> EURUSD up
        g = eur.Close.iloc[k] / eur.Close.iloc[k - 1] - 1
        r8.append(sgn * g - COST["EURUSD"][0] / 1e4 - COST["EURUSD"][1] / 1e4 * nights(common[k - 1], common[k]))
        t8.append(common[k]); hits += int(sgn * g > 0)
    res.append(verdict("Month-end USD rebalancing (EURUSD)", r8, t8, f"right sign {hits}/{len(r8)} months"))

    # ------------------------------------------------------------ report + Holm
    from math import erf, sqrt
    for x in res:
        x["p"] = 1 - 0.5 * (1 + erf(x["t"] / sqrt(2)))          # one-sided: net mean > 0
    order = sorted(range(len(res)), key=lambda i: res[i]["p"])
    m = len(res)
    for rank, i in enumerate(order):
        res[i]["holm"] = min(1.0, max(res[j]["p"] * (m - r) for r, j in enumerate(order[:rank + 1])))
    print(f"NINE-EFFECT FAMILY, net of Exness costs. Per trade in bp; 'per yr' = sum of net returns a year (not compounded).")
    print(f"{'':<40}{'n':>6}{'net bp':>8}{'t':>7}{'Holm p':>8}{'TUNE':>8}{'HOLD':>8}{'win%':>6}{'per yr':>8}  PASS?")
    for x in res:
        ok = x["holm"] < 0.05 and x["tune"] > 0 and x["hold"] > 0
        print(f"{x['name']:<40}{x['n']:>6}{x['mean']:>+8.2f}{x['t']:>+7.2f}{x['holm']:>8.3f}{x['tune']:>+8.2f}"
              f"{x['hold']:>+8.2f}{x['win']:>6.0f}{x['yr']:>+7.1f}%  {'PASS' if ok else 'fail'}")
        print(f"{'':<40}  {x['note']}  (split {x['cut']:%Y-%m-%d})")


if __name__ == "__main__":
    main()

"""BITCOIN ETF FLOWS: DO BIG DAILY INFLOWS / OUTFLOWS INTO THE US SPOT ETFS PREDICT BTC'S NEXT DAYS? (2026-11-09)

THE USER (2026-11-09): "test both" (with backtest/options_expiry.py). Since 2024-01-11 the US spot bitcoin ETFs publish each trading
day's net creations / redemptions; an inflow means authorised participants had to BUY bitcoin, an outflow to sell it - forced flow, the
one kind of thing that has held up in this repo. Never tested here: the repo tested ETF HEADLINES (news/impact.py, dead) and the Coinbase
premium (doc 12, weak), not the flows.

DATA     Farside Investors' daily table (farside.co.uk/bitcoin-etf-flow-all-data, fetched 2026-11-09; kept as
         strategy_analysis/data/etf_flows/farside_btc_daily.csv: day, total US$m, IBIT, GBTC), 2024-01-11 .. 2026-11-06; a holiday row
         (every fund '-') is dropped. BTC: Binance BTCUSDT perp 1h opens (options_expiry.hourly_open: the archive + public klines).
TIMING   a day's flows are published in the US evening / overnight; the trade enters at 14:00 UTC the NEXT calendar day (after the
         slowest issuer has reported) and holds 24 or 72 hours.
SIGNAL   the day's total flow as a percentile of the previous 60 flow days (strictly earlier days only).
CELLS    LONG after a top-fifth day (percentile >= 0.8), SHORT after a bottom-fifth day (<= 0.2), x hold 24h / 72h = 4 cells.
         net = side x return - 12bp - funding at 1bp / 8h (charged whichever the side); EXCESS = the cell's side x return minus the same
         over ALL flow days' entries in the same half (the drift any day gives).
HALVES   the first 60% of signal days (tune) / the last 40% (holdout).
PASS     (per cell) on BOTH halves net > 0 with t >= 2 and excess > 0; Holm < 0.05 over the 4 cells (p from the weaker half's net t).
         72-hour entries overlap (a day's trade is still open when the next fires): their t is from non-overlapping entries, every 3rd.
ALSO     same-day correlation of the flow with BTC's UTC-day return; flows against the PREVIOUS 5 days' return; the percentile's rank
         correlation with the next 24 hours (IC) per half; MDE80 per cell.

REGISTERED BEFORE THE FIRST RUN (2026-11-09; my prior that any cell passes: under 10%)
  E1  No cell passes.
  E2  The flow and BTC's same UTC-day return correlate at +0.30 or more (the flow is mostly the day's price move).
  E3  Flows follow price: correlation with the previous 5 days' BTC return +0.20 or more.
  E4  The next-24-hour IC is small: |IC| < 0.08 on both halves.
  E5  The 24-hour cells' MDE80 is over 1% a trade (only a big next-day effect could be seen in ~2.8 years).

    python -m backtest.etf_flows
"""
from __future__ import annotations

import sys
import time
from math import sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import options_expiry as ox  # noqa: E402

LOG = ROOT / "logs" / "etf_flows.txt"
FLOWS = ROOT / "strategy_analysis" / "data" / "etf_flows" / "farside_btc_daily.csv"
H = ox.H
LOOKBACK = 60
TOP, BOTTOM = 0.8, 0.2
ENTRY_HOUR = 14
HOLDS = (24, 72)
TUNE = 0.6


def load_flows(path=FLOWS) -> pd.DataFrame:
    d = pd.read_csv(path)
    d = d[~(d.ibit.isna() & d.gbtc.isna())].copy()            # a holiday: every fund '-'
    d["day"] = pd.to_datetime(d.day)
    return d.sort_values("day", kind="stable").reset_index(drop=True)


def percentiles(x, lookback=LOOKBACK):
    """Each value's percentile among the previous `lookback` values (ties count half); NaN until there are `lookback` of them."""
    x = np.asarray(x, float)
    out = np.full(len(x), np.nan)
    for i in range(lookback, len(x)):
        prev = x[i - lookback:i]
        out[i] = (np.sum(prev < x[i]) + 0.5 * np.sum(prev == x[i])) / lookback
    return out


def entry_ms(day: pd.Timestamp) -> int:
    """14:00 UTC on the calendar day after the flow day."""
    d = day + pd.Timedelta(days=1)
    return int(pd.Timestamp(d.year, d.month, d.day, ENTRY_HOUR, tz="UTC").value // 10**6)


def day_return(px, day: pd.Timestamp, back_days=0):
    """BTC's return from 00:00 UTC `back_days` before `day` to 00:00 UTC of the day after `day` (back_days=0: that UTC day)."""
    a = int(pd.Timestamp(day.year, day.month, day.day, tz="UTC").value // 10**6) - back_days * 86_400_000
    b = int(pd.Timestamp(day.year, day.month, day.day, tz="UTC").value // 10**6) + 86_400_000
    p0, p1 = px.get(a), px.get(b)
    return p1 / p0 - 1 if p0 and p1 else np.nan


def prev_return(px, day: pd.Timestamp, days=5):
    """BTC's return over the `days` days BEFORE the flow day (00:00 UTC day-days -> 00:00 UTC day)."""
    b = int(pd.Timestamp(day.year, day.month, day.day, tz="UTC").value // 10**6)
    p0, p1 = px.get(b - days * 86_400_000), px.get(b)
    return p1 / p0 - 1 if p0 and p1 else np.nan


def build(fl: pd.DataFrame, px: dict) -> pd.DataFrame:
    D = fl.copy()
    D["pct"] = percentiles(D.total.to_numpy(float))
    D["entry"] = [entry_ms(d) for d in D.day]
    for h in HOLDS:
        D[f"r{h}"] = [ox.window_return(px, e, 0, h) for e in D.entry]
    D["same_day"] = [day_return(px, d) for d in D.day]
    D["prev5"] = [prev_return(px, d) for d in D.day]
    D = D[np.isfinite(D.pct)].reset_index(drop=True)
    D["half"] = np.where(np.arange(len(D)) < int(len(D) * TUNE), "tu", "ho")
    return D


def cell(D: pd.DataFrame, side: int, h: int) -> dict:
    sel = (D.pct >= TOP) if side > 0 else (D.pct <= BOTTOM)
    cst = ox.FEE + ox.FUND_PER_H * h
    out = {}
    for half in ("tu", "ho"):
        m = (D.half == half).to_numpy()
        x = side * D.loc[m & sel.to_numpy(), f"r{h}"].to_numpy(float)
        base = side * D.loc[m, f"r{h}"].to_numpy(float)
        x, base = x[np.isfinite(x)], base[np.isfinite(base)]
        net = x - cst
        # 72-hour trades overlap: t from every (h // 24)-th entry so no two share a day
        step = max(1, h // 24)
        t_net = ox.tstat(net[::step]) if step > 1 else ox.tstat(net)
        out[half] = dict(n=len(x), net=float(net.mean()) if len(net) else np.nan, net_t=t_net,
                         excess=float(x.mean() - base.mean()) if len(x) and len(base) else np.nan, ex_t=ox.welch(x, base),
                         mde=2.8 * net[::step].std(ddof=1) / sqrt(len(net[::step])) if len(net[::step]) > 1 else np.nan)
    return out


def passes(c, holm_p):
    return all(c[h]["net"] > 0 and c[h]["net_t"] >= 2 and c[h]["excess"] > 0 for h in ("tu", "ho")) and holm_p < 0.05


def spearman(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 10:
        return np.nan
    ra, rb = pd.Series(a[ok]).rank().to_numpy(), pd.Series(b[ok]).rank().to_numpy()
    return float(np.corrcoef(ra, rb)[0, 1])


def pearson(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    return float(np.corrcoef(a[ok], b[ok])[0, 1]) if ok.sum() > 10 else np.nan


def main():
    t0 = time.time()
    fl = load_flows()
    px = ox.hourly_open("BTCUSDT")
    D = build(fl, px)
    cells = {(s, h): cell(D, s, h) for s in (1, -1) for h in HOLDS}
    keys = list(cells)
    hp = dict(zip(keys, ox.holm([ox.p_one(min(cells[k]["tu"]["net_t"], cells[k]["ho"]["net_t"])) for k in keys])))
    cut = D.day[D.half == "ho"].min()
    L = [f"backtest/etf_flows.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; Farside US spot bitcoin ETF flows {fl.day.min():%Y-%m-%d} .. "
         f"{fl.day.max():%Y-%m-%d} ({len(fl)} flow days); signal days {len(D)} from {D.day.min():%Y-%m-%d}; holdout from {cut:%Y-%m-%d}; "
         f"entry 14:00 UTC the next day; 12bp + 1bp / 8h", ""]
    L.append(f"flow per day: median {fl.total.median():+.0f} US$m, mean {fl.total.mean():+.0f}, 10th / 90th percentile "
             f"{fl.total.quantile(0.1):+.0f} / {fl.total.quantile(0.9):+.0f}")
    sd, p5 = pearson(D.total, D.same_day), pearson(D.total, D.prev5)
    L.append(f"same UTC day: correlation of the flow with BTC's return {sd:+.3f}; with the PREVIOUS 5 days' return {p5:+.3f}")
    ics = {}
    for half in ("tu", "ho"):
        m = D.half == half
        ics[half] = (spearman(D.pct[m], D.r24[m]), spearman(D.pct[m], D.r72[m]), int(m.sum()))
        n = ics[half][2]
        t24 = ics[half][0] * sqrt(n - 2) / sqrt(max(1e-12, 1 - ics[half][0] ** 2))
        L.append(f"IC {half}: percentile vs next 24h {ics[half][0]:+.3f} (t {t24:+.2f}, n {n}); vs next 72h {ics[half][1]:+.3f} (overlapping)")
    L += ["", "CELLS (tune / holdout; a 72h cell's t and MDE use every 3rd entry, its mean all of them)"]
    for (s, h), c in cells.items():
        tu, ho = c["tu"], c["ho"]
        L.append(f"  {'LONG after a big inflow ' if s > 0 else 'SHORT after a big outflow'} hold {h}h  n {tu['n']:>3}/{ho['n']:>3}  "
                 f"NET {tu['net'] * 1e4:+7.1f} ({tu['net_t']:+.1f}) / {ho['net'] * 1e4:+7.1f}bp ({ho['net_t']:+.1f})  "
                 f"excess {tu['excess'] * 1e4:+7.1f} ({tu['ex_t']:+.1f}) / {ho['excess'] * 1e4:+7.1f}bp ({ho['ex_t']:+.1f})  "
                 f"MDE80 hold {ho['mde'] * 1e4:5.0f}bp  holm {hp[(s, h)]:.2f}{'  PASS' if passes(c, hp[(s, h)]) else ''}")
    npass = sum(passes(c, hp[k]) for k, c in cells.items())
    mde24 = [cells[(s, 24)]["ho"]["mde"] for s in (1, -1)]
    L += ["", f"PASSING: {npass} of 4", "REGISTERED PREDICTIONS",
          f"  E1 no cell passes -> {'RIGHT' if npass == 0 else 'WRONG'}",
          f"  E2 same-day correlation >= +0.30 -> {'RIGHT' if sd >= 0.30 else 'WRONG'} ({sd:+.3f})",
          f"  E3 flows follow price, previous 5 days >= +0.20 -> {'RIGHT' if p5 >= 0.20 else 'WRONG'} ({p5:+.3f})",
          f"  E4 |next-24h IC| < 0.08 on both halves -> {'RIGHT' if all(abs(ics[h][0]) < 0.08 for h in ics) else 'WRONG'} "
          f"({ics['tu'][0]:+.3f} / {ics['ho'][0]:+.3f})",
          f"  E5 24h cells' MDE80 over 1% -> {'RIGHT' if min(mde24) > 0.01 else 'WRONG'} ({min(mde24) * 100:.2f}% .. {max(mde24) * 100:.2f}%)",
          f"run time {time.time() - t0:.0f}s"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

"""THE OPEN-INTEREST FLUSH: after a coin drops hard, does it matter whether leveraged positions were WIPED OUT? (2026-11-10)

THE USER: "new strategy in crypto".  The one family that pays in this repo is buying forced selling (crash bids, the
capitulation book).  Both measure forced selling by PRICE (a wick, RSI, a 10% day).  Open interest measures it directly:
if a coin falls 8% in a day and its open interest falls with it, positions were closed or liquidated - the sellers are
done.  If open interest RISES into the fall, new shorts are piling in and nobody was forced.  cascade_redux.py tested
this at 5 minutes (real, under the fee).  It was never tested at the hours-to-days scale where the fee is small.

DATA  Binance's 5-minute futures metrics for the 13 coins on disk (strategy_analysis/data/metrics, metrics_fetch.py;
      BTC ETH XRP ADA LTC LINK DOT AVAX NEAR ARB SUI WLD ENA; 2020-09 / listing .. 2026-09).  Price = open-interest
      value / contracts at each stamp; sampled on the hour.  13 survivors picked earlier for liquidity: an event study
      of a SPLIT inside the same coins, not a universe claim.
EVENT a closed hour where price is down >= 8% on 24 hours ago; one event per coin per 24 hours (the first hour).
SPLIT BY OPEN INTEREST over the same 24 hours (contracts, so the price fall itself is not counted):
        FLUSH  down 10% or more        MID  between        BUILD  flat or up
TRADE long one hour AFTER the event hour; out at the first hourly close 5% above the entry, else after 96 hours.
      12bp round trip + funding (the coin's own where the file covers the hold, else 1bp per 8 hours).
STATS per-trade mean with errors clustered by entry DAY (a crash day is one bet).  Tune = the first 60% of events by
      time, holdout = the rest.
THE BAR FLUSH passes if its net is > 0 with day-clustered t >= 2 on BOTH halves, it beats BUILD on both halves, and the
      holdout has >= 30 trades from >= 15 days.  Fewer = 'cannot tell'.

REGISTERED BEFORE THE FIRST RUN (2026-11-10)
    F1  400-900 events from fewer than 150 distinct days.
    F2  FLUSH is 30-50% of events.
    F3  FLUSH bounces more than BUILD on both halves; the difference is not significant on the holdout (t < 2).
    F4  FLUSH is net positive on both halves; chance it passes the whole bar: 15%.
    F5  All drops together net between -0.3% and +1.0% a trade (the capitulation family without its filters).
    F6  Secondary: the bounce is better when the crowd's long share did NOT rise during the fall (nobody catching the
        knife) - the same direction on both halves.

RESULT (2026-11-10, logs/oi_flush.txt, logs/oi_flush_check.txt) - A WEAK LEAD, NOT A BOOK.
    2,044 events on 666 days; only 9% are a FLUSH (open interest moves far less than I assumed: median -1.1%).
    FLUSH net +1.05% a trade on the tune half (t 1.38, 137 trades, 92 days) and +2.85% on the holdout (t 1.97, 38 trades,
    26 days); BUILD -0.21% / +0.62%; FLUSH minus BUILD +1.26% / +2.24% (t 1.3 / 1.5).  Pooled +1.44%, t 2.07, 29 trades
    a year on 13 coins, 66% won, average loser -7.0%, worst -25.5%.  NO PASS: neither half reaches t 2 and the bar's
    FLUSH-over-BUILD difference is not significant.
    The checks (oi_flush_check.py, post hoc) do not strengthen it: the tune half does NOT rise with the depth of the
    flush (+1.17% at -7.5%, +0.46% at -12.5%); on days with both kinds FLUSH is better on 44% of tune days (74% of
    holdout days); without its 5 best days the holdout is -0.72%; 2026 is negative (-2.32%, 10 trades).  It is more than
    drop size (median drop -9.4% against -8.7%; better than the rest in 5 of 6 drop-third cells).  The strongest number
    in the table is the old one: the DEEPEST third of drops bounces whatever open interest did (+1.71% t 2.4 / +2.19%
    t 3.7) - the capitulation book again, and here on 13 SURVIVOR coins, so flattered.
    Secondary F6: better when the crowd's long share did not rise (+1.62% t 2.9 / +0.68% t 1.0) - same direction.
    F3-F6 right; F1, F2 wrong (five times the events, a quarter of the flush share).
    Limits: 13 survivor coins; hourly closes (no intrabar target fills); no stop.  The honest next test is the same split
    on the point-in-time top-40 with dead coins, which needs Binance's metrics archive for ~100 symbols (free, large).
    tests/test_oi_flush.py 8; no planted-bug round.

    python -m backtest.oi_flush
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "strategy_analysis" / "data"
LOG = ROOT / "logs" / "oi_flush.txt"
DROP, FLUSH, BUILD = -0.08, -0.10, 0.0
TP, MAX_H, COST, FLAT_FUND = 0.05, 96, 0.0012, 0.0001
H = pd.Timedelta(hours=1)


def load_hourly(path):
    """One coin's metrics on an hourly grid: price, open interest (contracts), crowd long share. NaN where the archive
    has no stamp within 10 minutes before the hour (a hole stays a hole)."""
    d = pd.read_csv(path, usecols=["create_time", "sum_open_interest", "sum_open_interest_value", "count_long_short_ratio"])
    t = pd.to_datetime(d["create_time"], utc=True).dt.as_unit("ns")
    d = d.assign(t=t).dropna(subset=["sum_open_interest", "sum_open_interest_value"])
    d = d[(d["sum_open_interest"] > 0) & (d["sum_open_interest_value"] > 0)].drop_duplicates("t").set_index("t").sort_index()
    px = d["sum_open_interest_value"] / d["sum_open_interest"]
    ls = d["count_long_short_ratio"]
    grid = pd.date_range(d.index[0].ceil("h"), d.index[-1].floor("h"), freq="h")
    tol = pd.Timedelta(minutes=10)
    out = pd.DataFrame({"p": px.reindex(grid, method="ffill", tolerance=tol),
                        "oi": d["sum_open_interest"].reindex(grid, method="ffill", tolerance=tol),
                        "long": (ls / (1 + ls)).reindex(grid, method="ffill", tolerance=tol)}, index=grid)
    return out


def load_funding(sym):
    f = DATA / f"funding_{sym}.csv"
    if not f.exists():
        return None
    d = pd.read_csv(f)
    return pd.Series(d["fundingRate"].to_numpy(float), index=pd.to_datetime(d["t"], utc=True).dt.as_unit("ns")).sort_index()


def funding_paid(F, t0, t1):
    """What a LONG pays over (t0, t1]: the coin's own settlements where the file covers the whole hold, else flat."""
    if F is not None and len(F) and F.index[0] <= t0 and F.index[-1] >= t1:
        return float(F[(F.index > t0) & (F.index <= t1)].sum())
    return FLAT_FUND * ((t1 - t0) / pd.Timedelta(hours=8))


def events(X, sym, F=None):
    """Every event of one coin with its trade.  X = load_hourly's frame."""
    p, oi, lg = X["p"].to_numpy(), X["oi"].to_numpy(), X["long"].to_numpy()
    idx, n, rows, last = X.index, len(X), [], -10 ** 9
    for i in range(24, n - 2):
        if i - last < 24:
            continue
        if not (np.isfinite(p[i]) and np.isfinite(p[i - 24]) and np.isfinite(oi[i]) and np.isfinite(oi[i - 24])):
            continue
        drop = p[i] / p[i - 24] - 1
        if drop > DROP:
            continue
        last = i
        e = i + 1                                              # entry one hour after the event hour
        if not np.isfinite(p[e]):
            continue
        entry, x, why = p[e], None, "time"
        for j in range(e + 1, min(e + MAX_H, n - 1) + 1):
            if np.isfinite(p[j]) and p[j] >= entry * (1 + TP):
                x, why = j, "target"
                break
        if x is None:
            x = min(e + MAX_H, n - 1)
            while x > e and not np.isfinite(p[x]):
                x -= 1
            if x == e:
                continue
        gross = p[x] / entry - 1
        fund = funding_paid(F, idx[e], idx[x])
        worst = np.nanmin(p[e:x + 1]) / entry - 1
        rows.append(dict(sym=sym, t=idx[i], day=idx[e].normalize(), drop=drop, doi=oi[i] / oi[i - 24] - 1,
                         dlong=lg[i] - lg[i - 24] if np.isfinite(lg[i]) and np.isfinite(lg[i - 24]) else np.nan,
                         gross=gross, net=gross - COST - fund, why=why, hours=x - e, worst=worst))
    return rows


def group(doi):
    return "FLUSH" if doi <= FLUSH else ("BUILD" if doi >= BUILD else "MID")


def clustered(r, day):
    """Per-trade mean and its t with errors clustered by day (sum of each day's deviations)."""
    r = np.asarray(r, float)
    n = len(r)
    if n < 3:
        return (float(r.mean()) if n else np.nan), np.nan, n, len(set(day))
    m = r.mean()
    s = pd.Series(r - m).groupby(np.asarray(day)).sum().to_numpy()
    g = len(s)
    if g < 3:
        return float(m), np.nan, n, g
    se = np.sqrt((s ** 2).sum() * g / (g - 1)) / n
    return float(m), float(m / se) if se > 0 else np.nan, n, g


def diff_clustered(a, b):
    """Mean(a.net) - mean(b.net) with a day-clustered t (the two groups share crash days)."""
    d = pd.concat([a.assign(w=1.0 / len(a)), b.assign(w=-1.0 / len(b))])
    diff = a["net"].mean() - b["net"].mean()
    contrib = pd.concat([(a["net"] - a["net"].mean()) / len(a), -(b["net"] - b["net"].mean()) / len(b)])
    s = contrib.groupby(d["day"].to_numpy()).sum().to_numpy()
    g = len(s)
    se = np.sqrt((s ** 2).sum() * g / (g - 1)) if g > 2 else np.nan
    return float(diff), float(diff / se) if se and np.isfinite(se) and se > 0 else np.nan


def line(lab, half, w):
    m, t, n, g = clustered(w["net"], w["day"])
    if not n:
        return f"   {lab:<22}{half:>8}    0"
    return (f"   {lab:<22}{half:>8}{n:>5}{g:>6}{w['gross'].mean() * 100:>+8.2f}%{m * 100:>+8.2f}%{t:>+7.2f}{(w['net'] > 0).mean() * 100:>5.0f}%"
            f"{(w['why'] == 'target').mean() * 100:>7.0f}%{w['net'].min() * 100:>+8.1f}%{w['worst'].median() * 100:>+8.1f}%")


def main():
    rows = []
    for f in sorted((DATA / "metrics").glob("*.csv.gz")):
        sym = f.name.split(".")[0]
        rows += events(load_hourly(f), sym, load_funding(sym))
    E = pd.DataFrame(rows).sort_values("t").reset_index(drop=True)
    E["g"] = E["doi"].map(group)
    cut = E["t"].iloc[int(len(E) * 0.6)]
    E["half"] = np.where(E["t"] < cut, "tune", "holdout")
    L = [f"backtest/oi_flush.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {E.sym.nunique()} coins, {len(E)} events on {E.day.nunique()} days, "
         f"{E.t.min():%Y-%m-%d} .. {E.t.max():%Y-%m-%d}; holdout from {cut:%Y-%m-%d}",
         "   events by coin: " + "  ".join(f"{s[:-4]} {n}" for s, n in E.sym.value_counts().items()),
         f"   open interest over the fall's 24 hours: median {E.doi.median() * 100:+.1f}%, 10th {E.doi.quantile(.1) * 100:+.1f}%, 90th {E.doi.quantile(.9) * 100:+.1f}%;  "
         + "  ".join(f"{g} {(E.g == g).mean() * 100:.0f}%" for g in ("FLUSH", "MID", "BUILD")), "",
         f"   {'group':<22}{'half':>8}{'n':>5}{'days':>6}{'gross':>9}{'net':>9}{'t(day)':>7}{'won':>6}{'target':>8}{'worst':>9}{'med dip':>9}"]
    for g in ("ALL", "FLUSH", "MID", "BUILD"):
        for half in ("tune", "holdout"):
            w = E[(E.half == half) & ((E.g == g) | (g == "ALL"))]
            L.append(line(g, half, w))
    L.append("")
    res = {}
    for half in ("tune", "holdout"):
        a, b = E[(E.half == half) & (E.g == "FLUSH")], E[(E.half == half) & (E.g == "BUILD")]
        d, t = diff_clustered(a, b) if len(a) > 2 and len(b) > 2 else (np.nan, np.nan)
        w = E[E.half == half]
        ic = w[["doi", "net"]].corr(method="spearman").iloc[0, 1]
        res[half] = (d, t)
        L.append(f"   FLUSH minus BUILD, {half}: {d * 100:+.2f}% a trade (day-clustered t {t:+.2f});  rank correlation of the open-interest change with the result: {ic:+.3f}")
    L += ["", "   SECONDARY - the crowd's long share over the fall (accounts long / all accounts):"]
    for lab, m in (("long share fell or flat", E.dlong <= 0), ("long share rose", E.dlong > 0)):
        for half in ("tune", "holdout"):
            L.append(line(lab, half, E[m & (E.half == half)]))
    L += ["", "   FLUSH by year (n, net): " + "  ".join(f"{y} {len(g)} {g.net.mean() * 100:+.2f}%" for y, g in E[E.g == 'FLUSH'].groupby(E.t.dt.year)),
          "   BUILD by year (n, net): " + "  ".join(f"{y} {len(g)} {g.net.mean() * 100:+.2f}%" for y, g in E[E.g == 'BUILD'].groupby(E.t.dt.year))]
    S = {(g, h): clustered(E[(E.g == g) & (E.half == h)]["net"], E[(E.g == g) & (E.half == h)]["day"]) for g in ("FLUSH", "BUILD") for h in ("tune", "holdout")}
    A = {h: clustered(E[E.half == h]["net"], E[E.half == h]["day"]) for h in ("tune", "holdout")}
    ft, fh = S[("FLUSH", "tune")], S[("FLUSH", "holdout")]
    passed = (ft[0] > 0 and fh[0] > 0 and ft[1] >= 2 and fh[1] >= 2 and res["tune"][0] > 0 and res["holdout"][0] > 0 and fh[2] >= 30 and fh[3] >= 15)
    verdict = "PASS" if passed else ("cannot tell" if (fh[2] < 30 or fh[3] < 15) else "no pass")
    share = (E.g == "FLUSH").mean()
    c = {h: (clustered(E[(E.dlong <= 0) & (E.half == h)]["net"], E[(E.dlong <= 0) & (E.half == h)]["day"])[0]
             - clustered(E[(E.dlong > 0) & (E.half == h)]["net"], E[(E.dlong > 0) & (E.half == h)]["day"])[0]) for h in ("tune", "holdout")}
    L += ["", f"VERDICT: {verdict}", "", "REGISTERED PREDICTIONS",
          f"  F1 400-900 events from < 150 days ({len(E)}, {E.day.nunique()}) -> {'RIGHT' if 400 <= len(E) <= 900 and E.day.nunique() < 150 else 'WRONG'}",
          f"  F2 FLUSH 30-50% of events ({share * 100:.0f}%) -> {'RIGHT' if 0.3 <= share <= 0.5 else 'WRONG'}",
          f"  F3 FLUSH > BUILD on both halves, holdout t < 2 ({res['tune'][0] * 100:+.2f}% / {res['holdout'][0] * 100:+.2f}%, t {res['holdout'][1]:+.2f}) -> "
          f"{'RIGHT' if res['tune'][0] > 0 and res['holdout'][0] > 0 and res['holdout'][1] < 2 else 'WRONG'}",
          f"  F4 FLUSH net positive on both halves ({ft[0] * 100:+.2f}% / {fh[0] * 100:+.2f}%), no pass expected -> "
          f"{'RIGHT' if ft[0] > 0 and fh[0] > 0 and not passed else 'WRONG'}",
          f"  F5 all drops net -0.3..+1.0% ({A['tune'][0] * 100:+.2f}% / {A['holdout'][0] * 100:+.2f}%) -> "
          f"{'RIGHT' if all(-0.003 <= A[h][0] <= 0.01 for h in A) else 'WRONG'}",
          f"  F6 better when the long share did not rise, both halves ({c['tune'] * 100:+.2f}% / {c['holdout'] * 100:+.2f}%) -> "
          f"{'RIGHT' if c['tune'] > 0 and c['holdout'] > 0 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)
    return E


if __name__ == "__main__":
    main()

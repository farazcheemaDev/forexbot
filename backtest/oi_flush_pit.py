"""THE OPEN-INTEREST FLUSH ON THE POINT-IN-TIME TOP-40, DEAD COINS INCLUDED (2026-11-10)

THE USER: "Yes, run it" - re-test oi_flush.py's rule where it can actually fail.  oi_flush.py found, on the 13
survivor coins with open interest on disk, that after an 8% day the coins whose open interest fell 10%+ bounced more
(FLUSH +1.05% / +2.85% a trade, t 1.4 / 2.0, BUILD -0.21% / +0.62%) - a weak lead, no pass, carried on the holdout by
five crash days.  Survivor coins flatter any dip-buy, so the honest test is the point-in-time universe.

THE RULE - FROZEN FROM oi_flush.py, nothing re-chosen
    universe  each month the 40 most-traded USDT perps by the PRIOR month's volume (wide_book.eligibility(40) via
              pair_lab.universe(); coins at least MIN_AGE_D old; delisted coins included - 339 of 864 perps are dead)
    prices    pair_lab.hourly(): Binance 1h perp bars, halt_cut applied; a bar's close is known at its END (time + 1 h)
    event     a closed hour whose close is down >= 8% on the close 24 bars earlier, in an eligible month; one event per
              coin per 24 hours (the first hour)
    split     open interest in CONTRACTS over the same 24 hours, read from Binance's 5-minute metrics archive at the
              event hour's end and 24 hours before (the last stamp at or before, at most 10 minutes old):
              FLUSH down 10% or more   MID between   BUILD flat or up
    trade     long at the close of the NEXT hour; out at the first hourly close 5% above the entry, else the close 96
              hours after the entry (or the last bar if the coin stops trading first)
    cost      12bp round trip + the coin's real funding over the hold (capitulation_wide.funding_cum)
    stats     per-trade mean, errors clustered by entry day (oi_flush.clustered); tune = the first 60% of the events
              that HAVE open interest, by time; holdout = the rest
    bar       FLUSH passes if its net is > 0 with day-clustered t >= 2 on BOTH halves, it beats BUILD on both halves,
              and the holdout has >= 30 FLUSH trades from >= 15 days; fewer = 'cannot tell'.  The minimum detectable
              edge (2.8 x the holdout standard error) is printed.
    Events before the archive covers a coin (the archive starts about 2021-12) cannot be split: they are counted and
    reported apart ("no OI"), and their all-drops result is printed for comparison.

DATA  strategy_analysis/data/metrics_days/<SYM>/<YYYY-MM-DD>.csv (gitignored): only the days the events need (the
      event day, and the day 24 hours earlier, plus the previous day when the hour is within 10 minutes of midnight),
      from data.binance.vision/data/futures/um/daily/metrics/; an EMPTY file marks a day Binance does not serve.
      Counted before writing this file: 15,470 events on 357 coins, 27,520 symbol-days, 19,328 from 2021-12 on.

REGISTERED BEFORE ANY OPEN INTEREST WAS FETCHED (2026-11-12; prior that FLUSH passes the whole bar: 20%)
    P1  55-75% of events can be split (open interest found at both ends).
    P2  FLUSH is 8-18% of the split events (13 coins: 9%; smaller coins carry more leverage).
    P3  All drops together net -0.5..+0.5% a trade on each half (dead coins in; the 13 survivors read +0.41 / +0.50).
    P4  FLUSH beats BUILD on both halves: 45%.  FLUSH passes the bar: 20%.
    P5  The deepest third of drops beats the shallowest third on both halves, whatever open interest did (the
        capitulation family), and the flush premium shrinks inside drop thirds.
    P6  Without its 5 best days the FLUSH holdout mean is under half its full mean.

RESULT (2026-11-12, logs/oi_flush_pit.txt, logs/oi_flush_pit_check.txt) - NO PASS; the 13-coin lead was a survivor effect.
    15,471 events on 357 coins (2020-02 .. 2026-09); open interest at both ends for 10,857 (70%) on 341 coins; FLUSH 14%.
    FLUSH +0.30% a trade on the tune half (t 0.74, 1,131 trades, 469 days), -1.01% on the holdout (t -1.03, 394 trades,
    239 days; minimum detectable edge 2.7%); BUILD -0.43% / -0.57%; FLUSH minus BUILD +0.74% (t 1.38) / -0.44% (t -0.44).
    All split drops +0.10% / -0.29%; the events before the archive (2020-21 mostly) +1.68% (t 4.1) - the 2021 bull.
    Checks (post hoc): pooled FLUSH -0.04% a trade (t -0.09), average loser -11.4%, worst -99.4%; no dose-response on
    either half; on days with both kinds FLUSH is worse (-0.24% / -1.73%); without its 5 best days the holdout is -2.23%
    (t -2.46); FLUSH is not better than the rest inside drop thirds on the holdout (deep -0.81% vs +0.30%).  THE 13 COINS
    OF oi_flush.py STILL SHOW IT (FLUSH +1.11% / +3.45%, holdout t 3.05) and every other coin does not (+0.20% / -1.52%):
    surviving, liquid coins bounce after a flush; the coins a point-in-time list actually holds keep falling.
    P1, P2, P3, P5 right; P4 wrong (FLUSH beats BUILD on the tune half only); P6 'right' only mechanically (the holdout
    mean is already negative).  tests/test_oi_flush_pit.py 11; planted bugs 28 of 29 caught (the survivor is equivalent:
    an empty cache file is skipped either way), the do-nothing control survived (judged by exit code).

    python -m backtest.oi_flush_pit --fetch      # download the needed days (threaded, resumable)
    python -m backtest.oi_flush_pit              # run the test (fetches anything still missing)
"""
from __future__ import annotations

import io
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import oi_flush as of  # noqa: E402

DAYS = ROOT / "strategy_analysis" / "data" / "metrics_days"
LOG = ROOT / "logs" / "oi_flush_pit.txt"
EV_CACHE = ROOT / "strategy_analysis" / "data" / "oi_flush_pit_events.pkl"
BASE = "https://data.binance.vision/data/futures/um/daily/metrics"
DROP, FLUSH, BUILD, TP, MAX_H, COST = of.DROP, of.FLUSH, of.BUILD, of.TP, of.MAX_H, of.COST
TOL = pd.Timedelta(minutes=10)
H = pd.Timedelta(hours=1)
NS_H = 3_600_000_000_000


# ---------------------------------------------------------------- events from prices (no open interest needed)

def coin_events(sym, t, c, fc, elig):
    """Every event of one coin.  t = bar OPEN times (datetime64[ns]); c = closes; fc = funding_cum at the bar starts,
    with one extra element for the hour after the last bar; elig = bool per bar (eligible month).
    A bar's close is known at t + 1 h.  Entry at the close of bar e = i + 1; exit at the close of bar x.
    Funding: settlements at or before the start of bar x + 1, minus those at or before the start of bar e + 1."""
    rows, n, last = [], len(c), -10 ** 9
    for i in range(24, n - 1):
        if i - last < 24 or not elig[i]:
            continue
        if t[i] - t[i - 24] != np.timedelta64(24 * NS_H, "ns"):
            continue                                          # a hole in the bars: no clean 24-hour change
        drop = c[i] / c[i - 24] - 1
        if not np.isfinite(drop) or drop > DROP:
            continue
        last = i
        e = i + 1
        if t[e] - t[i] != np.timedelta64(NS_H, "ns"):
            continue                                          # no bar the next hour: no entry
        entry, x, why = c[e], None, "time"
        end = min(e + MAX_H, n - 1)
        for j in range(e + 1, end + 1):
            if c[j] >= entry * (1 + TP):
                x, why = j, "target"
                break
        if x is None:
            x = end
            if x == e:
                continue
        gross = c[x] / entry - 1
        fund = (fc[x + 1] - fc[e + 1]) / entry
        rows.append(dict(sym=sym, t_ev=pd.Timestamp(t[i]) + H, t_entry=pd.Timestamp(t[e]) + H,
                         day=(pd.Timestamp(t[e]) + H).normalize(), drop=drop, gross=gross, fund=fund,
                         net=gross - COST - fund, why=why, hours=int(x - e), worst=float(np.min(c[e:x + 1]) / entry - 1),
                         cut=bool(x == n - 1 and why == "time" and x - e < MAX_H)))
    return rows


def build_events():
    """All events on the PIT top-40 (slow: loads every coin's hourly bars).  Cached."""
    if EV_CACHE.exists():
        return pd.read_pickle(EV_CACHE)
    from backtest import pair_lab as pl
    from backtest.capitulation_wide import funding_cum
    H_ = pl.hourly_all()
    el = pl.universe()
    rows = []
    for s, hh in H_.items():
        if not el.get(s):
            continue
        t = hh.time.to_numpy("datetime64[ns]")
        c = hh.close.to_numpy(float)
        t_ext = np.r_[t, t[-1] + np.timedelta64(NS_H, "ns")]
        fc = funding_cum(s, t_ext, hh)
        ym = pd.DatetimeIndex(t).strftime("%Y-%m").to_numpy()
        elig = np.array([m in el[s] for m in ym])
        rows += coin_events(s, t, c, fc, elig)
    E = pd.DataFrame(rows).sort_values(["t_ev", "sym"], kind="stable").reset_index(drop=True)
    E.to_pickle(EV_CACHE)
    return E


# ---------------------------------------------------------------- open interest from the daily archive

def days_for(T):
    """The archive days a lookup at T (the last stamp in (T - TOL, T]) can need."""
    d = {T.strftime("%Y-%m-%d")}
    d.add((T - TOL).strftime("%Y-%m-%d"))
    return d


def needed(E):
    out = set()
    for s, t in zip(E["sym"], E["t_ev"]):
        for T in (t, t - pd.Timedelta(hours=24)):
            for d in days_for(T):
                out.add((s, d))
    return sorted(out)


def parse_zip(blob):
    """(create_time ns int64, sum_open_interest) from one daily metrics zip; empty frame if unusable."""
    z = zipfile.ZipFile(io.BytesIO(blob))
    d = pd.read_csv(z.open(z.namelist()[0]))
    if "create_time" not in d or "sum_open_interest" not in d:
        return pd.DataFrame(columns=["create_time", "sum_open_interest"])
    return d[["create_time", "sum_open_interest"]]


def fetch_one(key, tries=4):
    s, d = key
    f = DAYS / s / f"{d}.csv"
    if f.exists():
        return "cached"
    url = f"{BASE}/{s}/{s}-metrics-{d}.zip"
    for a in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research"}), timeout=40) as r:
                blob = r.read()
            f.parent.mkdir(parents=True, exist_ok=True)
            parse_zip(blob).to_csv(f, index=False)
            return "ok"
        except urllib.error.HTTPError as ex:
            if ex.code == 404:
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text("")
                return "missing"
            err = ex
        except Exception as ex:                               # network: retry
            err = ex
        time.sleep(1.5 * (a + 1))
    return f"error {type(err).__name__}"


def fetch(keys, workers=16):
    todo = [k for k in keys if not (DAYS / k[0] / f"{k[1]}.csv").exists()]
    print(f"fetch: {len(keys)} symbol-days needed, {len(todo)} not cached", flush=True)
    stats = {}
    with ThreadPoolExecutor(workers) as ex:
        for k, r in enumerate(ex.map(fetch_one, todo)):
            key = r.split()[0]
            stats[key] = stats.get(key, 0) + 1
            if (k + 1) % 1000 == 0:
                print(f"  {k + 1}/{len(todo)} {stats}", flush=True)
    print(f"fetch done: {stats}", flush=True)
    return stats


def load_oi(sym, days):
    """One coin's open-interest stamps (ns since epoch, contracts) from the cached days, sorted."""
    parts = []
    for d in sorted(days):
        f = DAYS / sym / f"{d}.csv"
        if f.exists() and f.stat().st_size > 0:
            parts.append(pd.read_csv(f))
    if not parts:
        return np.array([], "int64"), np.array([], float)
    d = pd.concat(parts, ignore_index=True).dropna()
    d = d[d["sum_open_interest"] > 0]
    ct = d["create_time"]
    tt = pd.to_datetime(ct, unit="ms", utc=True) if pd.api.types.is_numeric_dtype(ct) else pd.to_datetime(ct, utc=True)
    ts = tt.dt.tz_localize(None).astype("datetime64[ns]").astype("int64").to_numpy()
    o = np.argsort(ts, kind="stable")
    ts, v = ts[o], d["sum_open_interest"].to_numpy(float)[o]
    keep = np.r_[True, ts[1:] != ts[:-1]]
    return ts[keep], v[keep]


def oi_at(ts, v, T):
    """The last stamp at or before T, no older than TOL; NaN otherwise."""
    k = np.searchsorted(ts, T.value, side="right") - 1
    if k < 0 or T.value - ts[k] > TOL.value:
        return np.nan
    return float(v[k])


def attach_oi(E):
    E = E.copy()
    E["doi"] = np.nan
    for s, g in E.groupby("sym"):
        days = set()
        for t in g["t_ev"]:
            days |= days_for(t) | days_for(t - pd.Timedelta(hours=24))
        ts, v = load_oi(s, days)
        if not len(ts):
            continue
        for k, t in zip(g.index, g["t_ev"]):
            a, b = oi_at(ts, v, t), oi_at(ts, v, t - pd.Timedelta(hours=24))
            if np.isfinite(a) and np.isfinite(b) and b > 0:
                E.at[k, "doi"] = a / b - 1
    E["g"] = np.where(E["doi"].isna(), "NO_OI", E["doi"].map(lambda x: of.group(x) if np.isfinite(x) else "NO_OI"))
    return E


# ---------------------------------------------------------------- the test

def split_halves(E):
    S = E[E.g != "NO_OI"].sort_values("t_ev", kind="stable")
    cut = S["t_ev"].iloc[int(len(S) * 0.6)]
    E = E.copy()
    E["half"] = np.where(E.g == "NO_OI", "none", np.where(E["t_ev"] < cut, "tune", "holdout"))
    return E, cut


def verdict(E):
    """The registered bar.  Returns (verdict, stats dict)."""
    S = {}
    for h in ("tune", "holdout"):
        a, b = E[(E.half == h) & (E.g == "FLUSH")], E[(E.half == h) & (E.g == "BUILD")]
        m, t, n, g = of.clustered(a["net"], a["day"])
        d, td = of.diff_clustered(a, b) if len(a) > 2 and len(b) > 2 else (np.nan, np.nan)
        S[h] = dict(m=m, t=t, n=n, days=g, diff=d, tdiff=td)
    ok = all(np.isfinite(S[h]["m"]) and S[h]["m"] > 0 and np.isfinite(S[h]["t"]) and S[h]["t"] >= 2
             and np.isfinite(S[h]["diff"]) and S[h]["diff"] > 0 for h in S)
    enough = S["holdout"]["n"] >= 30 and S["holdout"]["days"] >= 15
    return ("PASS" if ok and enough else ("cannot tell" if not enough else "no pass")), S


def line(lab, half, w):
    m, t, n, g = of.clustered(w["net"], w["day"])
    if not n:
        return f"   {lab:<24}{half:>8}    0"
    return (f"   {lab:<24}{half:>8}{n:>6}{g:>6}{w['gross'].mean() * 100:>+8.2f}%{m * 100:>+8.2f}%{t:>+7.2f}"
            f"{(w['net'] > 0).mean() * 100:>5.0f}%{(w['why'] == 'target').mean() * 100:>7.0f}%{w['net'].min() * 100:>+8.1f}%")


def report(E):
    E, cut = split_halves(E)
    split = E[E.g != "NO_OI"]
    L = [f"backtest/oi_flush_pit.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; PIT top-40 incl. dead coins; "
         f"{len(E)} events on {E.sym.nunique()} coins, {E.t_ev.min():%Y-%m-%d} .. {E.t_ev.max():%Y-%m-%d}",
         f"   open interest found at both ends for {len(split)} events ({len(split) / len(E) * 100:.0f}%) on {split.sym.nunique()} coins, "
         f"{split.t_ev.min():%Y-%m-%d} .. {split.t_ev.max():%Y-%m-%d}; holdout from {cut:%Y-%m-%d}",
         f"   open interest over the fall's 24 hours: median {split.doi.median() * 100:+.1f}%, 10th {split.doi.quantile(.1) * 100:+.1f}%, "
         f"90th {split.doi.quantile(.9) * 100:+.1f}%;  " + "  ".join(f"{g} {(split.g == g).mean() * 100:.0f}%" for g in ("FLUSH", "MID", "BUILD")),
         f"   exits cut short by a delisting / halt: {int(E.cut.sum())}", "",
         f"   {'group':<24}{'half':>8}{'n':>6}{'days':>6}{'gross':>9}{'net':>9}{'t(day)':>7}{'won':>6}{'target':>8}{'worst':>9}"]
    for g in ("ALL split", "FLUSH", "MID", "BUILD"):
        for half in ("tune", "holdout"):
            w = E[(E.half == half) & ((E.g == g) | ((g == "ALL split") & (E.g != "NO_OI")))]
            L.append(line(g, half, w))
    L.append(line("NO_OI (before archive)", "-", E[E.g == "NO_OI"]))
    v, S = verdict(E)
    L.append("")
    for h in ("tune", "holdout"):
        w = E[E.half == h]
        ic = w[["doi", "net"]].corr(method="spearman").iloc[0, 1]
        L.append(f"   FLUSH minus BUILD, {h}: {S[h]['diff'] * 100:+.2f}% a trade (day-clustered t {S[h]['tdiff']:+.2f});  "
                 f"rank correlation of the open-interest change with the result: {ic:+.3f}")
    hb = E[(E.half == "holdout") & (E.g == "FLUSH")]
    if len(hb) > 2:
        m, t, n, g = of.clustered(hb["net"], hb["day"])
        se = abs(m / t) if t else np.nan
        L.append(f"   minimum detectable edge for FLUSH on the holdout (2.8 x se): {2.8 * se * 100:.2f}% a trade")
    L += ["", "   FLUSH by year (n, net): " + "  ".join(f"{y} {len(g)} {g.net.mean() * 100:+.2f}%" for y, g in E[E.g == 'FLUSH'].groupby(E.t_ev.dt.year)),
          "   BUILD by year (n, net): " + "  ".join(f"{y} {len(g)} {g.net.mean() * 100:+.2f}%" for y, g in E[E.g == 'BUILD'].groupby(E.t_ev.dt.year)),
          "   ALL drops by year (n, net, incl. NO_OI): " + "  ".join(f"{y} {len(g)} {g.net.mean() * 100:+.2f}%" for y, g in E.groupby(E.t_ev.dt.year)),
          "", f"VERDICT: {v}"]
    return "\n".join(L), E, v, S


def predictions(E, S, v):
    split = E[E.g != "NO_OI"]
    share = len(split) / len(E)
    fl = (split.g == "FLUSH").mean()
    A = {h: of.clustered(E[E.half == h]["net"], E[E.half == h]["day"])[0] for h in ("tune", "holdout")}
    q = split["drop"].quantile([1 / 3, 2 / 3]).to_numpy()
    deep = {h: split[(split.half == h) & (split["drop"] <= q[0])]["net"].mean() for h in ("tune", "holdout")}
    shal = {h: split[(split.half == h) & (split["drop"] > q[1])]["net"].mean() for h in ("tune", "holdout")}
    hb = split[(split.half == "holdout") & (split.g == "FLUSH")]
    best = hb.groupby("day")["net"].sum().sort_values(ascending=False).index[:5]
    w5 = hb[~hb.day.isin(best)]["net"].mean() if len(hb) else np.nan
    return ["REGISTERED PREDICTIONS",
            f"  P1 55-75% of events split ({share * 100:.0f}%) -> {'RIGHT' if 0.55 <= share <= 0.75 else 'WRONG'}",
            f"  P2 FLUSH 8-18% of split events ({fl * 100:.0f}%) -> {'RIGHT' if 0.08 <= fl <= 0.18 else 'WRONG'}",
            f"  P3 all drops -0.5..+0.5% a trade each half ({A['tune'] * 100:+.2f}% / {A['holdout'] * 100:+.2f}%) -> "
            f"{'RIGHT' if all(-0.005 <= A[h] <= 0.005 for h in A) else 'WRONG'}",
            f"  P4 FLUSH > BUILD both halves ({S['tune']['diff'] * 100:+.2f}% / {S['holdout']['diff'] * 100:+.2f}%; stated 45%); "
            f"pass stated 20% -> verdict {v}",
            f"  P5 deepest third beats the shallowest on both halves ({deep['tune'] * 100:+.2f} vs {shal['tune'] * 100:+.2f} / "
            f"{deep['holdout'] * 100:+.2f} vs {shal['holdout'] * 100:+.2f}) -> {'RIGHT' if all(deep[h] > shal[h] for h in deep) else 'WRONG'} "
            "(the flush-inside-thirds half is in oi_flush_pit_check)",
            f"  P6 FLUSH holdout without its 5 best days under half its mean ({w5 * 100:+.2f}% vs {S['holdout']['m'] * 100:+.2f}%) -> "
            f"{'RIGHT' if np.isfinite(w5) and w5 < 0.5 * S['holdout']['m'] else 'WRONG'}"]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    E = build_events()
    print(f"events {len(E)} on {E.sym.nunique()} coins", flush=True)
    keys = needed(E)
    fetch(keys)
    if "--fetch" in argv:
        return
    E = attach_oi(E)
    txt, E2, v, S = report(E)
    txt += "\n\n" + "\n".join(predictions(E2, S, v))
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)
    return E2


if __name__ == "__main__":
    main()

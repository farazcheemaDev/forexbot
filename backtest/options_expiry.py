"""CRYPTO OPTIONS EXPIRY: DOES BTC / ETH MOVE DIFFERENTLY AROUND DERIBIT'S EXPIRY? (2026-11-09)

THE USER (2026-11-09): "test both" - after being told the repo's surviving books all have a FORCED trader behind them and that two
forced-flow ideas were never tested here: crypto options expiry and the bitcoin ETF flows (backtest/etf_flows.py). Deribit, where most
crypto options trade, expires its options at 08:00 UTC: every Friday (weeklies), the LAST Friday of each month (monthlies, much bigger)
and the last Friday of March / June / September / December (quarterlies, the biggest). Dealers who are short or long those options
hedge with the underlying, so the hours around expiry are when forced hedging flow should show: practitioners talk of 'pinning' (price
held near a strike into expiry, released after) and of a drift into or out of it.

DATA     Binance BTCUSDT / ETHUSDT perpetual 1h bars (the perp archive, 2020-01 .. 2026-09, plus Binance's public 1h klines after it,
         cached in strategy_analysis/data/fresh/). The price at time X = the open of the 1h bar that starts at X.
EVENTS   monthly = the last Friday of each month at 08:00 UTC (quarterlies = the months 3, 6, 9, 12 among them); CONTROL = every other
         Friday at 08:00 UTC (a weekly expiry, the same weekday and clock). Weekly question: every Friday 08:00 vs Monday-Thursday 08:00.
WINDOWS  into24 (T-24h -> T), into4 (T-4h -> T), after4 (T -> T+4h), after24 (T -> T+24h); the return over the window.
TRADE    one position per event in the direction the TUNE half's excess shows (the sign of mean(event) - mean(control) before
         2024-08-29); net = that signed return - 12bp - funding at 1bp / 8h whichever the side (conservative).
PASS     (per cell) on BOTH halves: net > 0 with t >= 2 and the excess over the control in the chosen direction > 0; and Holm < 0.05
         (p from the weaker half's net t) over its family: 16 cells (monthly / quarterly x 4 windows x BTC / ETH), 8 weekly cells.
DIAGNOSTIC 'pinning': mean |return| in the 4 hours into / out of a monthly expiry over the same on ordinary Fridays (a ratio, Welch t).
POWER    each cell prints its MDE80 (2.8 x the holdout net mean's standard error): below that a null means 'cannot tell', not 'dead'.

REGISTERED BEFORE THE FIRST RUN (2026-11-09; my prior that any cell passes: about 5%)
  X1  No directional cell passes, in either family.
  X2  Pinning shows on BOTH coins: |return| in the 4 hours into a monthly expiry is under 0.95 x ordinary Fridays', and in the 4
      hours after it over 1.05 x.
  X3  Weekly: no Friday-08:00 window differs from Monday-Thursday 08:00 with |t| >= 2 on both halves (8 of 8 cells).
  X4  The MDE80 of the monthly 24-hour cells is over 1% a trade (so the monthly null can only exclude big effects).

AMENDMENT (2026-11-09, after the first run; nothing registered above changed): the first run passed nothing, but the 4 hours INTO a
monthly expiry fell more than ordinary Fridays on both halves and both coins (BTC excess -49 / -42bp, t -2.5 / -2.7). A POST-HOC
section checks it for the usual artifacts before it is called anything: the per-event spread (median, share down, without the 3
worst), by year, which hour carries it (04-07 vs 07-08 UTC: Deribit's futures settle on a 07:30-08:00 average), and a placebo - the
Friday one week BEFORE each monthly expiry, also late in the month. Whatever it shows, it is a lead found after looking.

    python -m backtest.options_expiry
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from math import sqrt
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "options_expiry.txt"
FRESH = ROOT / "strategy_analysis" / "data" / "fresh"
H = 3_600_000
CUT_MS = int(pd.Timestamp("2024-08-29", tz="UTC").value // 10**6)
FEE = 12e-4
FUND_PER_H = 1e-4 / 8
WINDOWS = {"into24": (-24, 0), "into4": (-4, 0), "after4": (0, 4), "after24": (0, 24)}
COINS = ("BTCUSDT", "ETHUSDT")


# ---------------------------------------------------------------- prices

def fetch_fresh(sym, start_ms, end_ms):
    """Binance USD-M public 1h klines from start_ms (open times), [(open time ms, open)]."""
    out, t = [], start_ms
    while t < end_ms:
        u = f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}&interval=1h&startTime={int(t)}&limit=1500"
        rows = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "forexbot"}), timeout=30))
        if not rows:
            break
        out += [(int(r[0]), float(r[1])) for r in rows if int(r[6]) < end_ms]
        t = int(rows[-1][0]) + H
        time.sleep(0.3)
    return out


def hourly_open(sym):
    """{open time ms: open price}: the perp archive, then Binance's public klines after it (cached; only CLOSED bars)."""
    from backtest.capitulation_wide import hourly
    h = hourly(sym)
    t = h.time.to_numpy("datetime64[ms]").astype(np.int64)
    px = dict(zip(t.tolist(), h.open.to_numpy(float).tolist()))
    FRESH.mkdir(parents=True, exist_ok=True)
    f = FRESH / f"{sym}_1h_open.csv"
    have = pd.read_csv(f) if f.exists() else pd.DataFrame(columns=["t", "open"])
    last = max([int(t[-1])] + have.t.astype(np.int64).tolist())
    now = int(time.time() * 1000)
    if now - last > 2 * H:
        new = pd.DataFrame(fetch_fresh(sym, last + H, now), columns=["t", "open"])
        have = pd.concat([have, new]).drop_duplicates("t").sort_values("t")
        have.to_csv(f, index=False)
    for a, b in zip(have.t.astype(np.int64), have.open.astype(float)):
        px.setdefault(int(a), float(b))
    return px


def window_return(px, T, a, b):
    p0, p1 = px.get(T + a * H), px.get(T + b * H)
    return p1 / p0 - 1 if p0 and p1 else np.nan


# ---------------------------------------------------------------- the calendar

def last_friday(year, month):
    d = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)
    return d - pd.Timedelta(days=(d.dayofweek - 4) % 7)


def calendar(first: str, last: str):
    """(monthly, quarterly, ordinary Fridays, Monday-Thursday) 08:00 UTC times in ms, from `first` to `last` (days)."""
    days = pd.date_range(first, last, freq="D")
    lastf = {(d.year, d.month): last_friday(d.year, d.month) for d in days}
    ms = lambda d: int(pd.Timestamp(d.year, d.month, d.day, 8, tz="UTC").value // 10**6)  # noqa: E731
    monthly = sorted({ms(v) for v in lastf.values() if days[0] <= v <= days[-1]})
    quarterly = [t for t in monthly if pd.Timestamp(t, unit="ms").month in (3, 6, 9, 12)]
    mset = set(monthly)
    fridays = [ms(d) for d in days if d.dayofweek == 4 and ms(d) not in mset]
    other = [ms(d) for d in days if d.dayofweek < 4]
    return monthly, quarterly, fridays, other


# ---------------------------------------------------------------- statistics

def tstat(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) < 2 or x.std(ddof=1) == 0:
        return np.nan
    return float(x.mean() / (x.std(ddof=1) / sqrt(len(x))))


def welch(a, b):
    a, b = (np.asarray(v, float) for v in (a, b))
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < 2 or len(b) < 2:
        return np.nan
    se = sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float((a.mean() - b.mean()) / se) if se > 0 else np.nan


def p_one(t):
    return 1.0 if not np.isfinite(t) else 1 - NormalDist().cdf(t)


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    out, run = [1.0] * len(ps), 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - r) * ps[i]))
        out[i] = run
    return out


def cost(win):
    a, b = WINDOWS[win]
    return FEE + FUND_PER_H * (b - a)


def cell(ev_t, ev_r, ct_t, ct_r, win):
    """One directional cell. ev_t / ct_t event / control times (ms), ev_r / ct_r their window returns."""
    ev_t, ev_r, ct_t, ct_r = (np.asarray(x) for x in (ev_t, ev_r, ct_t, ct_r))
    ok_e, ok_c = np.isfinite(ev_r), np.isfinite(ct_r)
    halves = {}
    for h, m_e, m_c in (("tu", ev_t < CUT_MS, ct_t < CUT_MS), ("ho", ev_t >= CUT_MS, ct_t >= CUT_MS)):
        e, c = ev_r[m_e & ok_e], ct_r[m_c & ok_c]
        halves[h] = dict(e=e, c=c, n=len(e), excess=(e.mean() - c.mean()) if len(e) and len(c) else np.nan, ex_t=welch(e, c))
    d = 1.0 if not np.isfinite(halves["tu"]["excess"]) or halves["tu"]["excess"] >= 0 else -1.0
    for h in ("tu", "ho"):
        net = d * halves[h]["e"] - cost(win)
        halves[h].update(net=float(net.mean()) if len(net) else np.nan, net_t=tstat(net),
                         mde=2.8 * (net.std(ddof=1) / sqrt(len(net))) if len(net) > 1 else np.nan)
    return dict(dir=d, **halves)


def passes(c, holm_p):
    for h in ("tu", "ho"):
        r = c[h]
        if not (r["net"] > 0 and r["net_t"] >= 2 and c["dir"] * r["excess"] > 0):
            return False
    return holm_p < 0.05


def family(cells: dict) -> dict:
    keys = list(cells)
    ps = [p_one(min(cells[k]["tu"]["net_t"], cells[k]["ho"]["net_t"])) for k in keys]
    return dict(zip(keys, holm(ps)))


def abs_ratio(e, c):
    e, c = np.abs(np.asarray(e, float)), np.abs(np.asarray(c, float))
    e, c = e[np.isfinite(e)], c[np.isfinite(c)]
    return float(e.mean() / c.mean()) if len(e) and len(c) and c.mean() > 0 else np.nan, welch(e, c)


# ---------------------------------------------------------------- post hoc (added after the first run)

def posthoc(px, monthly, fridays):
    """The 4-hours-into-monthly-expiry dip, checked: spread, years, hours, placebo. Returns log lines."""
    L = ["", "POST-HOC (added after the first run): the 4 hours into a monthly expiry, checked (bp; excess = monthly minus ordinary Fridays)"]
    placebo = [t - 7 * 86_400_000 for t in monthly]
    for s in COINS:
        e = np.array([window_return(px[s], T, -4, 0) for T in monthly])
        c = np.array([window_return(px[s], T, -4, 0) for T in fridays])
        e, c = e[np.isfinite(e)], c[np.isfinite(c)]
        worst = np.sort(e)[3:]
        L.append(f"  {s[:3]} into4: monthly mean {e.mean() * 1e4:+.1f} median {np.median(e) * 1e4:+.1f}, down {np.mean(e < 0) * 100:.0f}% of {len(e)}; "
                 f"ordinary Fridays mean {c.mean() * 1e4:+.1f} median {np.median(c) * 1e4:+.1f}, down {np.mean(c < 0) * 100:.0f}%; "
                 f"without the 3 worst monthly events {worst.mean() * 1e4:+.1f} (excess {(worst.mean() - c.mean()) * 1e4:+.1f}, t {welch(worst, c):+.2f})")
        yrs = {}
        for T in monthly:
            r = window_return(px[s], T, -4, 0)
            if np.isfinite(r):
                yrs.setdefault(pd.Timestamp(T, unit="ms").year, []).append(r)
        L.append(f"      by year (mean bp, n): " + "  ".join(f"{y} {np.mean(v) * 1e4:+.0f} ({len(v)})" for y, v in sorted(yrs.items())))
        for lab, a, b in (("04-07 UTC", -4, -1), ("07-08 UTC", -1, 0)):
            e2 = np.array([window_return(px[s], T, a, b) for T in monthly])
            c2 = np.array([window_return(px[s], T, a, b) for T in fridays])
            L.append(f"      {lab}: excess {(np.nanmean(e2) - np.nanmean(c2)) * 1e4:+.1f}bp (t {welch(e2, c2):+.2f})")
        pl = np.array([window_return(px[s], T, -4, 0) for T in placebo])
        cpl = np.array([window_return(px[s], T, -4, 0) for T in fridays if T not in set(placebo)])
        L.append(f"      placebo, the Friday a week before: excess {(np.nanmean(pl) - np.nanmean(cpl)) * 1e4:+.1f}bp (t {welch(pl, cpl):+.2f})")
    return L


# ---------------------------------------------------------------- run

def fmt(name, c, hp):
    tu, ho = c["tu"], c["ho"]
    return (f"  {name:<26} dir {'long ' if c['dir'] > 0 else 'short'}  n {tu['n']:>3}/{ho['n']:>3}  "
            f"excess {tu['excess'] * 1e4:+7.1f} ({tu['ex_t']:+.1f}) / {ho['excess'] * 1e4:+7.1f}bp ({ho['ex_t']:+.1f})  "
            f"NET {tu['net'] * 1e4:+7.1f} ({tu['net_t']:+.1f}) / {ho['net'] * 1e4:+7.1f}bp ({ho['net_t']:+.1f})  "
            f"MDE80 hold {ho['mde'] * 1e4:6.0f}bp  holm {hp:.2f}{'  PASS' if passes(c, hp) else ''}")


def main():
    t0 = time.time()
    px = {s: hourly_open(s) for s in COINS}
    end = min(max(p) for p in px.values())
    last_day = (pd.Timestamp(end - 25 * H, unit="ms")).strftime("%Y-%m-%d")
    monthly, quarterly, fridays, other = calendar("2020-01-03", last_day)
    L = [f"backtest/options_expiry.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; Binance perp 1h opens to {pd.Timestamp(end, unit='ms')} UTC; "
         f"events 08:00 UTC: {len(monthly)} monthly ({len(quarterly)} quarterly), {len(fridays)} ordinary Fridays, {len(other)} Monday-Thursday days; "
         f"tune < 2024-08-29; 12bp + 1bp / 8h", ""]
    R = {s: {w: {k: [window_return(px[s], T, *WINDOWS[w]) for T in ts] for k, ts in
                 (("m", monthly), ("q", quarterly), ("f", fridays), ("o", other))} for w in WINDOWS} for s in COINS}
    fam1, fam2 = {}, {}
    for s in COINS:
        for w in WINDOWS:
            r = R[s][w]
            fam1[f"{s[:3]} monthly {w}"] = cell(monthly, r["m"], fridays, r["f"], w)
            fam1[f"{s[:3]} quarterly {w}"] = cell(quarterly, r["q"], fridays, r["f"], w)
            allf = sorted(monthly + fridays)
            rf = dict(zip(monthly + fridays, r["m"] + r["f"]))
            fam2[f"{s[:3]} every Friday {w}"] = cell(allf, [rf[t] for t in allf], other, r["o"], w)
    h1, h2 = family(fam1), family(fam2)
    L.append("MONTHLY / QUARTERLY EXPIRY vs ordinary Fridays at 08:00 UTC (direction = the tune half's excess; tune / holdout)")
    L += [fmt(k, c, h1[k]) for k, c in fam1.items()]
    L += ["", "EVERY FRIDAY 08:00 (weekly expiry) vs Monday-Thursday 08:00"]
    L += [fmt(k, c, h2[k]) for k, c in fam2.items()]
    L += ["", "PINNING: mean |return| around a monthly expiry over the same on ordinary Fridays (ratio, Welch t on |return|; all years)"]
    pin = {}
    for s in COINS:
        for w in ("into4", "after4", "into24", "after24"):
            ratio, t = abs_ratio(R[s][w]["m"], R[s][w]["f"])
            pin[(s, w)] = ratio
            L.append(f"  {s[:3]} {w:<8} ratio {ratio:.3f} (t {t:+.2f})")
    L += posthoc(px, monthly, fridays)
    n1 = sum(passes(c, h1[k]) for k, c in fam1.items())
    n2 = sum(passes(c, h2[k]) for k, c in fam2.items())
    x2 = all(pin[(s, "into4")] < 0.95 and pin[(s, "after4")] > 1.05 for s in COINS)
    x3 = sum(1 for c in fam2.values() if min(abs(c["tu"]["ex_t"]), abs(c["ho"]["ex_t"])) >= 2 and np.sign(c["tu"]["ex_t"]) == np.sign(c["ho"]["ex_t"]))
    mdes = [fam1[f"{s[:3]} monthly {w}"]["ho"]["mde"] for s in COINS for w in ("into24", "after24")]
    L += ["", f"PASSING: {n1} of {len(fam1)} monthly / quarterly cells, {n2} of {len(fam2)} weekly cells",
          "REGISTERED PREDICTIONS",
          f"  X1 no directional cell passes -> {'RIGHT' if n1 + n2 == 0 else 'WRONG'}",
          f"  X2 pinning on both coins (into4 < 0.95, after4 > 1.05) -> {'RIGHT' if x2 else 'WRONG'} "
          f"({', '.join(f'{s[:3]} {w} {pin[(s, w)]:.2f}' for s in COINS for w in ('into4', 'after4'))})",
          f"  X3 no weekly cell differs with |t| >= 2 on both halves (same sign) -> {'RIGHT' if x3 == 0 else 'WRONG'} ({x3} of 8)",
          f"  X4 the monthly 24h cells' MDE80 is over 1% -> {'RIGHT' if min(mdes) > 0.01 else 'WRONG'} "
          f"({min(mdes) * 100:.2f}% .. {max(mdes) * 100:.2f}%)",
          f"run time {time.time() - t0:.0f}s"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

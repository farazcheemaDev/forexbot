"""INSIDE THE WICK HOUR: 5-minute bars for every wick-bid fill (doc 15 follow-up).

Doc 15 and wick_better.py model a fill on 1-hour bars and sell at the fill hour's close, with a flat
30bp of extra exit slippage. Hourly bars cannot say WHEN in the hour the bid filled, how much lower the
price went after it, or whether a resting SELL order (maker, no slippage) placed above the fill would
have done better. This fetches Binance's 5-minute klines (public fapi/v1/klines, dead coins served too)
for the three hours from every fill of the top-20 / top-40 books at 10%, and measures:

  1. AGREEMENT  does a 5-minute bar actually go 0.1% through the bid, and at what price does it fill
                (min(bid, that 5-minute bar's open))?
  2. AFTER THE FILL  how far below the fill does the price go before the hour ends (what the margin
                has to carry), and how fast does it come back?
  3. EXITS      taker sells at the fill bar's close, +15 / +30 / +60 / +120 minutes after it, and the
                fill hour's close (the doc 15 rule); a resting take-profit at +2 / +3 / +5 / +8% over
                the fill (maker, 2bp, no slippage; live only from the bar AFTER the fill bar), else a
                taker sale at the fill hour's close; a stop 5% / 10% under the fill (taker, filled at
                min(stop, the bar's open), +50bp slippage), else the fill hour's close.
                Costs: 2bp maker in; taker exits 6bp + 30bp slippage, as doc 15.

REGISTERED PREDICTION (2026-09-24, before running):
  1. 5-minute bars confirm >90% of the hourly fills, at about the same price.
  2. median further fall after the fill ~2%, 1 fill in 20 goes 10%+ lower before the hour ends.
  3. +15 / +30 minutes about equal to the fill hour's close; +120 minutes worse; a resting
     take-profit at +3-5% BEATS the hour close by +0.3 to +0.5% per fill, because winners pay no
     slippage; stops LOSE (they sell the bottom of a wick).

    python -m backtest.wick_5m
"""
from __future__ import annotations

import json
import pickle
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.crash_buy import CUT, PEN  # noqa: E402
from backtest.wick_better import fills, load_all  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "strategy_analysis" / "data" / "wick5m_cache.pkl"
MAKER, TAKER, SLIP, STOP_SLIP = 2e-4, 6e-4, 0.003, 0.005


def fetch(sym, t):
    """Thirty-six 5-minute bars (3 hours) from hour t."""
    ms = int(pd.Timestamp(t).value // 10**6)
    u = f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}&interval=5m&startTime={ms}&limit=36"
    for _ in range(3):
        try:
            d = json.load(urllib.request.urlopen(u, timeout=20))
            return np.array([[float(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])] for r in d])
        except Exception:
            time.sleep(1.0)
    return None


def load_bars(keys):
    """Cached; fetched on 6 threads (weight 1 per request, far under Binance's 2,400 a minute)."""
    from concurrent.futures import ThreadPoolExecutor
    cache = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
    todo = [k for k in keys if k not in cache]
    for a in range(0, len(todo), 300):
        chunk = todo[a:a + 300]
        with ThreadPoolExecutor(6) as ex:
            for k, b in zip(chunk, ex.map(lambda k: fetch(*k), chunk)):
                cache[k] = b
        CACHE.write_bytes(pickle.dumps(cache))
        print(f"    fetched {a + len(chunk)} / {len(todo)}", flush=True)
    return cache


def per_fill(Y, bars):
    rows = []
    for r in Y.itertuples():
        b = bars.get((r.sym, r.t))
        bid = r.prev * 0.90
        rec = dict(sym=r.sym, t=r.t, h1=r.ret - FEE_H)
        if b is None or len(b) < 13 or b[0, 0] != pd.Timestamp(r.t).value // 10**6:
            rows.append(rec | dict(ok=False)); continue
        o, h, l, c = b[:, 1], b[:, 2], b[:, 3], b[:, 4]
        hit = np.flatnonzero(l[:12] < bid * (1 - PEN))
        if not len(hit):
            rows.append(rec | dict(ok=False, conf=False)); continue
        j = hit[0]
        f = min(bid, o[j])
        after = l[j:12].min() / f - 1                       # lowest low from the fill bar to the hour's end
        n = len(c)
        taker = lambda px: px / f - 1 - MAKER - TAKER - SLIP  # noqa: E731
        ex = {"fill bar close": taker(c[j]), "hour close": taker(c[11])}
        for mins in (15, 30, 60, 120):
            ex[f"+{mins} min"] = taker(c[min(j + mins // 5, n - 1)])
        for tp in (0.02, 0.03, 0.05, 0.08):
            lvl = f * (1 + tp)
            up = np.flatnonzero(h[j + 1:12] > lvl * (1 + PEN))
            ex[f"sell order +{tp*100:.0f}%"] = tp - 2 * MAKER if len(up) else taker(c[11])
        for sl in (0.05, 0.10):
            lvl = f * (1 - sl)
            dn = np.flatnonzero(l[j + 1:12] < lvl)
            if len(dn):
                k = j + 1 + dn[0]
                ex[f"stop -{sl*100:.0f}%"] = min(lvl, o[k]) / f - 1 - MAKER - TAKER - STOP_SLIP
            else:
                ex[f"stop -{sl*100:.0f}%"] = taker(c[11])
        # minutes until the price is back above the fill (bar closes after the fill bar)
        back = np.flatnonzero(c[j:] > f)
        rows.append(rec | dict(ok=True, conf=True, minute=int(j * 5), fill_vs_1h=f / min(bid, r.open) - 1,
                               after=after, back=int(back[0] * 5) if len(back) else 999, **ex))
    return pd.DataFrame(rows)


FEE_H = 8e-4 + SLIP


def book(P, col, n):
    eq, pts = 1.0, []
    for t, g in P.groupby("t", sort=True):
        eq *= 1 + g[col].sum() / n
        pts.append((t, eq))
    s = pd.Series([p[1] for p in pts], index=pd.DatetimeIndex([p[0] for p in pts]))
    c = s.resample("D").last().reindex(pd.date_range("2020-01-01", "2026-09-21", freq="D")).ffill().fillna(1.0)
    return c


def rate(c):
    y = (c.index[-1] - c.index[0]).days / 365.25
    return ((c.iloc[-1] / c.iloc[0]) ** (1 / y) - 1) * 100


def main():
    XA, _, bear_day = load_all()
    for label, n, kw in (("top-20", 20, {}), ("top-40", 40, {}), ("top-40, skip BEAR", 40, {"skip_bear": bear_day})):
        Y = fills(XA[XA[f"in{n}"]], k=0.10, **kw)
        keys = sorted({(r.sym, r.t) for r in Y.itertuples()})
        print(f"{label}, 10%: {len(Y)} hourly fills; fetching 5-minute bars for {len(keys)} fill hours", flush=True)
        bars = load_bars(keys)
        P = per_fill(Y, bars)
        ok = P[P.ok.astype(bool)].copy()
        got = P.conf.notna().sum() if "conf" in P else 0
        print(f"\n1. AGREEMENT ({label}): 5-minute bars served for {got} of {len(P)} fills; a 5-minute bar goes 0.1% "
              f"through the bid in {len(ok)} ({len(ok)/max(got,1)*100:.0f}%). Fill price vs the hourly model: "
              f"median {ok.fill_vs_1h.median()*100:+.2f}%, mean {ok.fill_vs_1h.mean()*100:+.2f}%")
        print(f"   when in the hour the bid fills: minute 0-9 {(ok.minute < 10).mean()*100:.0f}%, 10-29 "
              f"{((ok.minute >= 10) & (ok.minute < 30)).mean()*100:.0f}%, 30-59 {(ok.minute >= 30).mean()*100:.0f}%")
        print(f"\n2. AFTER THE FILL: further fall before the hour ends - median {ok.after.median()*100:+.1f}%, "
              f"1 in 4 {ok.after.quantile(0.25)*100:+.1f}%, 1 in 20 {ok.after.quantile(0.05)*100:+.1f}%, "
              f"worst {ok.after.min()*100:+.1f}%")
        hr = ok.groupby("t").after.sum() / n
        print(f"   the whole book's paper loss inside an hour (every fill at its lowest point at once, x1 size): worst "
              f"{hr.min()*100:+.1f}% of the account ({hr.idxmin():%Y-%m-%d %H:00}), 1 hour in 100 {hr.quantile(0.01)*100:+.1f}%")
        print(f"   back above the fill price (5-minute close): within 5 min {(ok.back <= 0).mean()*100:.0f}%, "
              f"15 min {(ok.back <= 10).mean()*100:.0f}%, 60 min {(ok.back <= 55).mean()*100:.0f}%, "
              f"not within 3 hours {(ok.back == 999).mean()*100:.0f}%")
        cols = ["hour close", "fill bar close", "+15 min", "+30 min", "+60 min", "+120 min", "sell order +2%",
                "sell order +3%", "sell order +5%", "sell order +8%", "stop -5%", "stop -10%"]
        print(f"\n3. EXITS (top-{n}, the {len(ok)} confirmed fills, after costs): per fill all / tune / hold, share "
              f"losing, and as a book (1/{n} each) CAGR / tune / hold / worst month")
        for col in cols:
            tu, ho = ok[ok.t < CUT], ok[ok.t >= CUT]
            c = book(ok, col, n)
            me = c.resample("ME").last().pct_change().dropna()
            print(f"   {col:<16} {ok[col].mean()*100:+6.2f}% / {tu[col].mean()*100:+6.2f}% / {ho[col].mean()*100:+6.2f}%"
                  f"  losing {(ok[col] < 0).mean()*100:3.0f}%  | book {rate(c):+6.1f}%/yr  {rate(c[c.index < CUT]):+6.1f}"
                  f" / {rate(c[c.index >= CUT]):+6.1f}  worst month {me.min()*100:+5.1f}%")
        print()


def caps():
    """4. A CAP ON HOW MANY BIDS MAY FILL IN ONE HOUR (added after 1-3 were read).

    Section 2 found the hourly model hides the real risk: after a fill the price keeps falling (median
    -3.8%, 1 in 20 -23%), and on 2025-10-10 21:00 every top-20 bid filled and sank together - the book's
    paper loss inside that hour, every fill at its low at once, was -50% of the account at x1. The fix
    a live bot can apply: once K bids have filled in the hour, cancel the rest. Fills are taken in
    the order of their 5-minute bar (ties in random order, 10 orderings); the kept fills are sold at
    the hour's close as before.

    REGISTERED before running: for top-40 skip-BEAR, K = 5 cuts the worst in-hour paper loss from
    ~-50% to under -10% and costs 20-35% of the growth (the 5+ coin waves carry most of the profit,
    wick_better.py H); K = 10 halves the paper loss and costs ~10-15%.
    """
    XA, _, bear_day = load_all()
    bars = pickle.loads(CACHE.read_bytes())
    for label, n, kw in (("top-20", 20, {}), ("top-40, skip BEAR", 40, {"skip_bear": bear_day})):
        P = per_fill(fills(XA[XA[f"in{n}"]], k=0.10, **kw), bars)
        ok = P[P.ok.astype(bool)].copy()
        print(f"\n4. CAP ON FILLS PER HOUR ({label}, 1/{n} each, sold at the hour's close; mean of 10 tie orderings)")
        print(f"  {'cap':<10}{'fills kept':>11}{'CAGR':>9}{'TUNE':>9}{'HOLD':>9}{'worst mo':>10}"
              f"{'worst in-hour paper loss':>26}{'1 hour in 100':>15}")
        for K in (3, 5, 10, 20, 999):
            if K > n and K != 999:
                continue
            res = []
            for sd in range(10):
                rng = np.random.default_rng(sd)
                x = ok.assign(tie=rng.random(len(ok))).sort_values(["t", "minute", "tie"])
                x = x[x.groupby("t").cumcount() < K]
                c = book(x, "hour close", n)
                hr = x.groupby("t").after.sum() / n
                me = c.resample("ME").last().pct_change().dropna()
                res.append((len(x), rate(c), rate(c[c.index < CUT]), rate(c[c.index >= CUT]), me.min() * 100,
                            hr.min() * 100, hr.quantile(0.01) * 100))
            r = np.mean(res, axis=0)
            print(f"  {'no cap' if K == 999 else f'first {K}':<10}{r[0]:>11.0f}{r[1]:>+8.1f}%{r[2]:>+8.1f}%{r[3]:>+8.1f}%"
                  f"{r[4]:>+9.1f}%{r[5]:>+25.1f}%{r[6]:>+14.1f}%")
        hr = ok.groupby("t").after.sum() / n
        print("  the five worst in-hour paper losses, no cap: " + ", ".join(
            f"{t:%Y-%m-%d %H:00} {v*100:+.0f}% ({(ok.t == t).sum()} fills)" for t, v in hr.nsmallest(5).items()))


def save_capped(out=ROOT / "logs" / "wick_capped.pkl"):
    """Daily returns of the top-40 skip-BEAR book with the first-K cap (K 10 / 20, and no cap), the mean
    over the 10 tie orderings, for worst_month.py. Fills without 5-minute bars (~3%) are left out."""
    XA, _, bear_day = load_all()
    bars = pickle.loads(CACHE.read_bytes())
    ok = per_fill(fills(XA[XA.in40], k=0.10, skip_bear=bear_day), bars)
    ok = ok[ok.ok.astype(bool)]
    res = {}
    for K in (10, 20, 999):
        rs = []
        for sd in range(10):
            rng = np.random.default_rng(sd)
            x = ok.assign(tie=rng.random(len(ok))).sort_values(["t", "minute", "tie"])
            rs.append(book(x[x.groupby("t").cumcount() < K], "hour close", 40).pct_change().fillna(0.0))
        res[K] = pd.concat(rs, axis=1).mean(axis=1)
        print(f"  cap {K}: {rate((1 + res[K]).cumprod()):+.1f}%/yr")
    pd.to_pickle(res, out)
    print(f"  saved {out}")


if __name__ == "__main__" and "--save" in sys.argv:
    save_capped()
elif __name__ == "__main__" and "--caps" in sys.argv:
    caps()
elif __name__ == "__main__":
    main()

"""THE GENERALS BEFORE HIS CLICK - did the big NASDAQ stocks, the dollar or bitcoin move his way first?

his_race_curve.py (2026-09-26) showed his moment's edge is real and is about DIRECTION over the next 1-5
minutes: at a 7-point race his entries beat the same-day nearby moments on 12 of 12 days (+37 points, t 7.0;
at 10 points 10 / 12, t 3.5), while at 4 points they are ordinary. Something leads NASDAQ by minutes and he
sees it. Tested so far: NASDAQ itself, the S&P, the Dow, gold, USDJPY, Binance's QQQ flow, news, posts.
Not tested: the stocks that ARE the index. The eight biggest NASDAQ names (NVDA, MSFT, AAPL, AMZN, GOOGL,
META, AVGO, TSLA - about half its weight) are on the Exness MT5 terminal as CFDs, with ticks; so are the
dollar index and bitcoin. A trader watching NVIDIA's chart next to NASDAQ's would see a "general" move first.

1-second mids from MT5 ticks (UTC-aware requests), 09:30-16:00 ET, cached in
strategy_analysis/data/generals_sec_cache.pkl. Returns in basis points over the prior w seconds, sign-aligned:
  lead_30 / lead_120 / lead_300   the eight stocks' average move minus NASDAQ's (the generals AHEAD of it)
  gmove_120                       the eight stocks' average move
  breadth_60                      how many of the eight moved his way in the last minute (0-8)
  nvda_lead_120                   NVIDIA alone minus NASDAQ
  dxy_120                         the dollar index, inverted (a falling dollar is "his way" for a buy)
  btc_120                         bitcoin
STAGE A: his clean entries (April on, 09:30-16:00 ET) vs ~80 moments of the same day within 20 minutes, same
direction. Ranks; Holm over 8.
STAGE B: all days, 40 random seconds a day x both directions: does the feature (top vs bottom third) move the
7-point NASDAQ race (mid, 600 s) - his scale, where his edge lives - on both halves? And the net race?

REGISTERED PREDICTION (2026-09-26, before running): the generals do not mark his entries - ranks 0.4-0.6,
nothing survives Holm - and in B the lead features move the 7-point race by at most +3 points, because the
index future leads its stocks, not the other way round.

    python -m backtest.his_generals
"""
from __future__ import annotations

import pickle
import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_predictors import race_net  # noqa: E402
from backtest.his_race_curve import race2  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
CACHE = ROOT / "strategy_analysis" / "data" / "generals_sec_cache.pkl"
GMT = 5.0
STOCKS = ("NVDAm", "MSFTm", "AAPLm", "AMZNm", "GOOGLm", "METAm", "AVGOm", "TSLAm")
OTHER = ("DXYm", "BTCUSDm")
N = 23400
FEATS = ("lead_30", "lead_120", "lead_300", "gmove_120", "breadth_60", "nvda_lead_120", "dxy_120", "btc_120")


def day_sec(mt5, sym, day):
    a = pd.Timestamp(day).tz_localize("America/New_York") + pd.Timedelta(hours=9, minutes=30)
    b = a + pd.Timedelta(seconds=N)
    t = mt5.copy_ticks_range(sym, a.tz_convert("UTC").to_pydatetime(), b.tz_convert("UTC").to_pydatetime(), mt5.COPY_TICKS_ALL)
    if t is None or len(t) < 200:
        return None
    d = pd.DataFrame(t)
    d = d[(d.bid > 0) & (d.ask > 0)]
    sec = ((pd.to_datetime(d.time_msc, unit="ms") - a.tz_convert("UTC").tz_localize(None)).dt.total_seconds()).astype(int)
    s = pd.Series(((d.bid + d.ask) / 2).to_numpy(), index=sec).groupby(level=0).last().reindex(range(N)).ffill().bfill()
    return s.to_numpy(np.float32)


def load(days):
    C = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
    need = [(s, d) for s in STOCKS + OTHER for d in days if d not in C.get(s, {})]
    if need:
        import MetaTrader5 as mt5
        mt5.initialize()
        for s in STOCKS + OTHER:
            mt5.symbol_select(s, True)
        for i, (s, d) in enumerate(need):
            C.setdefault(s, {})[d] = day_sec(mt5, s, d)
            if i % 100 == 0:
                print(f"  fetched {i}/{len(need)}", flush=True)
        mt5.shutdown()
        CACHE.write_bytes(pickle.dumps(C))
    return C


def ndx_sec(ts, mid):
    k = np.clip(np.searchsorted(ts, np.arange(N), side="right") - 1, 0, None)
    return mid[k].astype(np.float64)


def ret(a, t, w):
    t = int(t)
    return (np.log(a[t]) - np.log(a[t - w])) * 1e4


def feats(G, t, s):
    t = int(t)
    if t < 300 or t >= N:
        return None
    nd = G["ndx"]
    r = {w: np.array([ret(G[x], t, w) for x in STOCKS]) for w in (30, 60, 120, 300)}
    n = {w: ret(nd, t, w) for w in (30, 120, 300)}
    f = dict(lead_30=s * (r[30].mean() - n[30]), lead_120=s * (r[120].mean() - n[120]), lead_300=s * (r[300].mean() - n[300]),
             gmove_120=s * r[120].mean(), breadth_60=float((s * r[60] > 0).sum()),
             nvda_lead_120=s * (r[120][0] - n[120]),
             dxy_120=-s * ret(G["DXYm"], t, 120) if G.get("DXYm") is not None else np.nan,
             btc_120=s * ret(G["BTCUSDm"], t, 120) if G.get("BTCUSDm") is not None else np.nan)
    return f


def pz(z):
    return 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))


def main():
    cache = pickle.loads(TICKS.read_bytes())
    days = [d for d in sorted(cache) if cache[d] is not None]
    C = load(days)
    def G_of(d):
        if any(C[s].get(d) is None for s in STOCKS):
            return None
        g = {s: C[s][d].astype(np.float64) for s in STOCKS}
        for s in OTHER:
            g[s] = C[s][d].astype(np.float64) if C[s].get(d) is not None else None
        g["ndx"] = ndx_sec(*cache[d][:2])
        return g
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    x["et"] = (x.open_time - pd.Timedelta(hours=GMT)).dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    x = x[x.open_time - pd.Timedelta(hours=GMT) >= "2026-04-01"]
    rng = np.random.default_rng(20)
    ranks = []
    for r in x.itertuples():
        d = r.et.normalize()
        if d not in cache or cache[d] is None:
            continue
        G = G_of(d)
        if G is None:
            continue
        t0 = (r.et - d - pd.Timedelta(hours=9, minutes=30)).total_seconds()
        s = 1 if r.side == "BUY" else -1
        mine = feats(G, t0, s)
        if mine is None:
            continue
        near = [f for f in (feats(G, t0 + rng.uniform(30, 1200) * rng.choice((-1, 1)), s) for _ in range(120)) if f is not None][:80]
        Nn = pd.DataFrame(near)
        ranks.append({k: (Nn[k].dropna() < mine[k]).mean() + 0.5 * (Nn[k].dropna() == mine[k]).mean()
                      for k in FEATS if np.isfinite(mine[k])} | {"raw_" + k: mine[k] for k in FEATS})
    RA = pd.DataFrame(ranks)
    pA = {}
    for k in FEATS:
        v = RA[k].dropna() if k in RA else pd.Series(dtype=float)
        pA[k] = pz((v.mean() - 0.5) / (np.sqrt(1 / 12) / np.sqrt(len(v)))) if len(v) > 2 else 1.0
    order = sorted(pA, key=pA.get)
    holm = {k: min(1.0, max(pA[j] * (len(pA) - i) for i, j in enumerate(order[:order.index(k) + 1]))) for k in pA}
    have = sum(G_of(d) is not None for d in days)
    out = [f"stock ticks for {have} of {len(days)} NASDAQ tick days; DXY on {sum(C['DXYm'].get(d) is not None for d in days)}, "
           f"BTC on {sum(C['BTCUSDm'].get(d) is not None for d in days)}",
           f"\nSTAGE A - his {len(RA)} clean entries (09:30-16:00 ET) vs ~80 same-day moments within 20 min, same direction",
           f"  {'feature':<14}{'rank':>6}{'his median':>12}{'p':>7}{'Holm':>7}"]
    for k in FEATS:
        v = RA[k].dropna() if k in RA else pd.Series(dtype=float)
        out.append(f"  {k:<14}{v.mean():>6.2f}{RA['raw_' + k].median():>12.2f}{pA[k]:>7.3f}{holm[k]:>7.3f}")

    rows = []
    for d in days:
        G = G_of(d)
        if G is None:
            continue
        ts, mid, spr = cache[d]
        for t in rng.uniform(1800, 22800, 40):
            for s in (1, -1):
                f = feats(G, t, s)
                o = race2(ts, mid, t, s, 600, 7, 7)
                if f is None or o is None:
                    continue
                rows.append(f | {"o": o, "on": race_net(ts, mid, spr, t, s), "day": d})
    P = pd.DataFrame(rows)
    ds = sorted(P.day.unique())
    mid_day = ds[len(ds) // 2]
    w = lambda g, c="o": g[c].dropna().mean() * 100 if len(g) else np.nan  # noqa: E731
    out.append(f"\nSTAGE B - {len(P)} random moment x direction pairs on {len(ds)} days: 7-point NASDAQ race (mid, 600 s), "
               f"base {w(P):.1f}%; net race base {w(P, 'on'):.1f}% (break-even 50%)")
    out.append(f"  {'feature':<14}{'low 1/3':>9}{'high 1/3':>10}{'diff':>7}{'1st half':>9}{'2nd half':>9}{'net high':>10}")
    for k in FEATS:
        q = P.dropna(subset=[k])
        if not len(q):
            continue
        lo, hi = q[k].quantile(1 / 3), q[k].quantile(2 / 3)
        hm, lm = q[k] >= hi, q[k] <= lo
        if hi == lo:
            hm, lm = q[k] > hi, q[k] < lo
        h1, h2 = q.day < mid_day, q.day >= mid_day
        out.append(f"  {k:<14}{w(q[lm]):>8.1f}%{w(q[hm]):>9.1f}%{w(q[hm]) - w(q[lm]):>+7.1f}"
                   f"{w(q[hm & h1]) - w(q[lm & h1]):>+9.1f}{w(q[hm & h2]) - w(q[lm & h2]):>+9.1f}{w(q[hm], 'on'):>9.1f}%")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_generals.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()

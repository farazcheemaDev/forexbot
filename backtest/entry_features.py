"""SEVEN ENTRY-TIME FEATURES FROM THE LITERATURE, TESTED AS ONE PRE-REGISTERED FAMILY.

WHERE THEY CAME FROM (web research, 2026-09-23)
    A1 fund24    coin's own funding, mean of the 3 settlements before entry. BIS WP 1087
                 "Crypto carry": high carry predicts crash risk and short-side liquidations.
                 Practitioner form: a breakout on crowded, expensive longs is fragile.
    A2 fund_mkt  BTC's funding, mean of the 21 settlements (7 days) before entry - the
                 market-wide crowding version of A1.
    A3 oi24      the coin's open-interest VALUE change over the 24h before entry. The usual
                 claim: a breakout on rising OI is new money, on falling OI a covering pop.
                 Binance metrics archive, 2021-12 onward, 11 of 12 coins (no SHIB).
    A4 weekend   entry Saturday or Sunday (UTC) before 23:00 Sunday. Concretum Group,
                 "Seasonality in Bitcoin Intraday Trend Trading": US Sunday is mean-reverting.
    A5 asia_open entry from Sunday 23:00 to Monday 23:00 UTC - the same paper's strongest
                 trend window ("Monday Asia open effect"), stronger since mid-2020.
    A6 stable30  total stablecoin supply, 30-day growth, known the day before entry
                 (DefiLlama). Stablecoin growth as a crypto-native liquidity/regime signal.
    A7 fng       Fear & Greed index the day before entry (alternative.me), read contrarian.

    Short side, two features: B1 fund24 and B2 fund_mkt.

WHAT IS MEASURED
    Every position the deployed rules would open (all signals, before the slot cap), with
    t0 at the REAL entry time (causal_t0.py) and R charged the actual funding it paid
    (funding_cost.py). R is capped at [-25, +100] for the statistic so a single +1,800R
    runner cannot decide a feature - slot_priority.py's convention.

    Statistic: mean capped R of the top tercile of the feature minus the bottom tercile
    (for binary features: in minus out). Standard error from a MONTH-BLOCK bootstrap
    (whole calendar months of entries resampled), because trades inside a month are one
    market episode, not independent draws (doc 02: pooling fakes significance).

REGISTERED PREDICTIONS AND THE PASS RULE (written before the first run)
    Sign predicted for the LONG side:
        A1 fund24 -   A2 fund_mkt -   A3 oi24 +   A4 weekend -   A5 asia_open +
        A6 stable30 +   A7 fng -
    SHORT side: B1 fund24 +   B2 fund_mkt +
    A feature PASSES only if (i) the sign matches the prediction on the tune half AND the
    holdout separately, and (ii) the pooled Holm-corrected p < 0.05 across all nine.
    Anything that passes then has to hold on coins that took no part: the point-in-time
    wide universe (wide_book.py), before it is allowed near a portfolio run.
    My expectation: at most one passes, most likely A1 on longs, because funding is the
    one feature with a mechanism that costs the trade directly.

    python -m backtest.entry_features
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.causal_t0 import real_t0  # noqa: E402
from backtest.engine_variants import BASE_RULES, rows_for  # noqa: E402
from backtest.funding_cost import PERP_NAME, PERPS, charged, long_funding, short_funding  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data"
METRICS = DATA / "metrics"
CAP = (-25.0, 100.0)
PRED = {("long", "fund24"): -1, ("long", "fund_mkt"): -1, ("long", "oi24"): +1,
        ("long", "weekend"): -1, ("long", "asia_open"): +1, ("long", "stable30"): +1,
        ("long", "fng"): -1, ("short", "fund24"): +1, ("short", "fund_mkt"): +1}
BINARY = {"weekend", "asia_open"}


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=60))


def stablecoins():
    f = DATA / "stablecoins_total.csv"
    if not f.exists():
        js = _get_json("https://stablecoins.llama.fi/stablecoincharts/all")
        pd.DataFrame([dict(date=pd.to_datetime(int(x["date"]), unit="s"),
                           usd=x["totalCirculatingUSD"].get("peggedUSD", np.nan))
                      for x in js]).to_csv(f, index=False)
    s = pd.read_csv(f, parse_dates=["date"]).set_index("date")["usd"]
    g = s.pct_change(30)
    # a day's figure is known once the day is over: usable from the NEXT day on
    return pd.Series(g.to_numpy(), index=g.index + pd.Timedelta(days=1)).dropna()


def fear_greed():
    f = DATA / "fear_greed.csv"
    if not f.exists():
        js = _get_json("https://api.alternative.me/fng/?limit=0&format=json")
        pd.DataFrame([dict(date=pd.to_datetime(int(x["timestamp"]), unit="s"),
                           v=int(x["value"])) for x in js["data"]]).to_csv(f, index=False)
    s = pd.read_csv(f, parse_dates=["date"]).set_index("date")["v"].sort_index()
    return pd.Series(s.to_numpy(float), index=s.index + pd.Timedelta(days=1))


_FR: dict = {}


def fund_series(coin):
    if coin not in _FR:
        f = pd.read_csv(PERPS / f"{PERP_NAME.get(coin, coin)}_funding.csv.gz")
        _FR[coin] = pd.Series(f["rate"].to_numpy(float),
                              index=pd.to_datetime(f["time"]).dt.floor("h")).sort_index()
    return _FR[coin]


def fund_before(coin, t, n):
    s = fund_series(coin)
    s = s[s.index < t]                       # settled strictly before entry
    return float(s.iloc[-n:].mean()) if len(s) >= n else np.nan


_OI: dict = {}


def oi_series(coin):
    if coin not in _OI:
        f = METRICS / f"{coin}.csv.gz"
        if not f.exists():
            _OI[coin] = None
        else:
            m = pd.read_csv(f, usecols=["create_time", "sum_open_interest_value"])
            _OI[coin] = pd.Series(m["sum_open_interest_value"].to_numpy(float),
                                  index=pd.to_datetime(m["create_time"])).sort_index()
    return _OI[coin]


def oi_change(coin, t):
    s = oi_series(coin)
    if s is None or t < s.index[0] + pd.Timedelta(days=1):
        return np.nan
    now = s.asof(t - pd.Timedelta(minutes=5))       # last 5-min print before entry
    then = s.asof(t - pd.Timedelta(hours=24))
    return float(now / then - 1) if then and np.isfinite(then) and then > 0 else np.nan


def features(rows):
    st, fg = stablecoins(), fear_greed()
    out = []
    for r in rows:
        t = pd.Timestamp(r["t0"])
        wd, hr = t.dayofweek, t.hour
        out.append(dict(
            side=r["side"], rule=r["rule"], coin=r["coin"], t0=t, R=r["R"],
            fund24=fund_before(r["coin"], t, 3),
            fund_mkt=fund_before("BTCUSDT", t, 21),
            oi24=oi_change(r["coin"], t) if r["side"] == "long" else np.nan,
            weekend=float(wd == 5 or (wd == 6 and hr < 23)),
            asia_open=float((wd == 6 and hr >= 23) or (wd == 0 and hr < 23)),
            stable30=float(st.asof(t)) if t >= st.index[0] else np.nan,
            fng=float(fg.asof(t)) if t >= fg.index[0] else np.nan))
    return pd.DataFrame(out)


def spread(g, feat):
    """Top-minus-bottom tercile mean capped R (binary: in minus out)."""
    y = g["Rc"].to_numpy(); x = g[feat].to_numpy()
    if feat in BINARY:
        a, b = y[x == 1], y[x == 0]
    else:
        lo, hi = np.nanquantile(x, [1 / 3, 2 / 3])
        a, b = y[x >= hi], y[x <= lo]
    if len(a) < 20 or len(b) < 20:
        return np.nan
    return float(a.mean() - b.mean())


def boot_t(g, feat, reps=2000, seed=11):
    months = g["t0"].dt.to_period("M")
    groups = [idx for _, idx in g.groupby(months).groups.items()]
    rng = np.random.default_rng(seed)
    est = spread(g, feat)
    bs = []
    for _ in range(reps):
        pick = rng.integers(0, len(groups), len(groups))
        ii = np.concatenate([groups[k] for k in pick])
        v = spread(g.loc[ii], feat)
        if np.isfinite(v):
            bs.append(v)
    se = float(np.std(bs)) if len(bs) > 50 else np.nan
    return est, (est / se if se and se > 0 else np.nan)


def holm(ps):
    order = np.argsort(ps)
    m, adj, run = len(ps), np.ones(len(ps)), 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (m - k) * ps[i]))
        adj[i] = run
    return adj


def main():
    from scipy.stats import norm

    rows = charged(real_t0(short_funding(long_funding(rows_for(BASE_RULES)))))
    F = features(rows)
    F = F.dropna(subset=["fund24"]).copy()           # before a coin's perp existed: skip
    F["Rc"] = F["R"].clip(*CAP)
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    print(f"{len(F):,} positions with a live perp at entry | tune < {cut:%Y-%m-%d} <= holdout")
    print("R includes funding; capped at [-25, +100] for the statistic; t from month-block bootstrap\n")
    print(f"  {'side':<6}{'feature':<11}{'pred':>5}{'n':>7}{'TUNE':>9}{'t':>6}{'HOLD':>9}{'t':>6}"
          f"{'ALL':>9}{'t':>6}{'p':>8}{'Holm':>7}  verdict")
    res = []
    for (side, feat), sgn in PRED.items():
        g = F[(F.side == side)].dropna(subset=[feat]).reset_index(drop=True)
        tu = g[g.t0 < cut].reset_index(drop=True); ho = g[g.t0 >= cut].reset_index(drop=True)
        a, ta = boot_t(tu, feat); b, tb = boot_t(ho, feat); c, tc = boot_t(g, feat)
        p = float(2 * (1 - norm.cdf(abs(tc)))) if np.isfinite(tc) else 1.0
        res.append(dict(side=side, feat=feat, sgn=sgn, n=len(g), a=a, ta=ta, b=b, tb=tb,
                        c=c, tc=tc, p=p))
    adj = holm(np.array([r["p"] for r in res]))
    for r, h in zip(res, adj):
        ok_sign = np.sign(r["a"]) == r["sgn"] and np.sign(r["b"]) == r["sgn"]
        verdict = "PASS" if (ok_sign and h < 0.05) else ("sign holds, not sig" if ok_sign
                                                           else "fails")
        print(f"  {r['side']:<6}{r['feat']:<11}{r['sgn']:>+5d}{r['n']:>7}{r['a']:>+9.3f}"
              f"{r['ta']:>+6.2f}{r['b']:>+9.3f}{r['tb']:>+6.2f}{r['c']:>+9.3f}{r['tc']:>+6.2f}"
              f"{r['p']:>8.3f}{h:>7.3f}  {verdict}")

    print("\n  per-coin agreement with the predicted sign (pooled halves):")
    for (side, feat), sgn in PRED.items():
        g = F[F.side == side].dropna(subset=[feat])
        agree = tot = 0
        for _c, gc in g.groupby("coin"):
            v = spread(gc, feat)
            if np.isfinite(v):
                tot += 1; agree += int(np.sign(v) == sgn)
        print(f"    {side:<6}{feat:<11}{agree}/{tot}")


if __name__ == "__main__":
    main()

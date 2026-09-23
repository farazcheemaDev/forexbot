"""THE COIN-LEVEL KIMCHI PREMIUM - Korean retail mania as a cross-sectional signal.

THE IDEA
    Korean won cannot move freely in and out of crypto, so Upbit (KRW) prices can sit above
    Binance (USDT) prices for days. The market-wide part of that premium is FX and capital
    controls; the COIN-SPECIFIC part - one coin's premium over BTC's premium - is Korean
    retail piling into one name that the rest of the world is not buying. Folklore says
    Upbit manias mark local tops. It is a flow nobody abroad can arbitrage quickly, which is
    the kind of structural friction this project's surviving results came from.

    premium_coin(d) = (Upbit KRW close / Binance USDT close) / (same ratio for BTC) - 1
    measured at the daily close (Upbit day candles are 00:00-24:00 UTC, the same clock as
    Binance's), traded from the NEXT day's open.

THE TEST (weekly, market-neutral, all coins on both venues)
    Every 7 days rank eligible coins by premium. Long the bottom quintile, short the top
    quintile, equal dollars, on Binance perps; hold 7 days. 12bp on turnover measured from
    basket overlap, actual funding both legs. Also the event version: coins whose premium
    crosses +5%, short vs the equal-weight basket for 7 days.

REGISTERED PREDICTIONS (before any premium is computed)
    1. High-premium coins UNDERPERFORM: the long-low / short-high spread is positive,
       > +0.5%/week gross, in both halves.
    2. The event version (premium > +5%) shows a negative 7-day excess for the coin.
    3. Market-neutral by construction, so correlation with the trend book is near zero.
    If (1) fails in either half, the category is dead.

    python -m backtest.kimchi            # fetches Upbit daily candles once (cached)
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
PERPS = ROOT / "strategy_analysis" / "data" / "perps"
UP = ROOT / "strategy_analysis" / "data" / "upbit_daily"
FEE = 12 / 1e4


def _get(u):
    for a in range(5):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(
                u, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}), timeout=30))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(1 + a); continue
            return None
        except Exception:
            time.sleep(1 + a)
    return None


def upbit_daily(market):
    UP.mkdir(parents=True, exist_ok=True)
    f = UP / f"{market}.csv.gz"
    if f.exists():
        return pd.read_csv(f, parse_dates=["t"])
    rows, to = [], None
    while True:
        u = f"https://api.upbit.com/v1/candles/days?market={market}&count=200"
        if to:
            u += f"&to={to}"
        d = _get(u)
        if not d:
            break
        rows += [(x["candle_date_time_utc"], x["trade_price"], x["candle_acc_trade_price"]) for x in d]
        if len(d) < 200:
            break
        to = d[-1]["candle_date_time_utc"] + "Z"
        if d[-1]["candle_date_time_utc"] < "2020-01-01":
            break
        time.sleep(0.12)
    df = pd.DataFrame(rows, columns=["t", "krw", "krw_vol"])
    df["t"] = pd.to_datetime(df["t"])
    df = df.drop_duplicates("t").sort_values("t")
    df.to_csv(f, index=False, compression="gzip")
    return df


def binance_daily(base):
    for sym in (f"{base}USDT", f"1000{base}USDT"):
        f = PERPS / f"{sym}_1d.csv.gz"
        if f.exists():
            d = pd.read_csv(f, parse_dates=["time"])
            mult = 1000.0 if sym.startswith("1000") else 1.0
            fu = pd.read_csv(PERPS / f"{sym}_funding.csv.gz", parse_dates=["time"])
            fday = fu.groupby(fu.time.dt.floor("D"))["rate"].sum()
            return d.set_index("time"), fday, mult
    return None


def panel():
    mk = _get("https://api.upbit.com/v1/market/all") or []
    krw = sorted(m["market"] for m in mk if m["market"].startswith("KRW-"))
    C, O, K, F = {}, {}, {}, {}
    for m in krw:
        base = m[4:]
        b = binance_daily(base)
        if b is None:
            continue
        u = upbit_daily(m)
        if u is None or len(u) < 60:
            continue
        d, fday, mult = b
        s = u.set_index("t")["krw"]
        C[base] = d["close"] / mult; O[base] = d["open"] / mult
        K[base] = s; F[base] = fday
    C, O, K, F = (pd.DataFrame(x).sort_index() for x in (C, O, K, F))
    return C, O, K, F.fillna(0.0)


def main():
    C, O, K, F = panel()
    idx = C.index.intersection(K.index)
    C, O, K, F = C.loc[idx], O.loc[idx], K.loc[idx], F.reindex(idx).fillna(0.0)
    ratio = K / C
    prem = ratio.div(ratio["BTC"], axis=0) - 1            # coin premium over BTC's premium
    prem = prem.drop(columns=["BTC"])
    print(f"{prem.shape[1]} coins on both Upbit KRW and Binance perps, {idx[0]:%Y-%m} .. {idx[-1]:%Y-%m}")
    print(f"coin-specific premium: median {np.nanmedian(prem.values)*100:+.2f}%, "
          f"95th pct {np.nanpercentile(prem.values, 95)*100:+.2f}%")

    # weekly quintile spread, entering at the NEXT day's open, holding 7 days
    days = prem.index[::7]
    out, prev_l, prev_s = [], set(), set()
    for d0 in days:
        k = prem.index.get_loc(d0)
        if k + 8 >= len(prem.index):
            break
        p = prem.iloc[k].dropna()
        p = p[np.isfinite(p) & (p.abs() < 1.0)]                  # glitches out
        if len(p) < 20:
            continue
        q = max(len(p) // 5, 3)
        lo, hi = set(p.nsmallest(q).index), set(p.nlargest(q).index)
        a, b = prem.index[k + 1], prem.index[k + 8]
        r = O.loc[b] / O.loc[a] - 1
        f = F.loc[(F.index > a) & (F.index <= b)].sum()
        rl = (r[list(lo)] - f[list(lo)]).mean()                   # long pays funding
        rs = (-r[list(hi)] + f[list(hi)]).mean()                  # short receives it
        turn = (len(lo - prev_l) + len(hi - prev_s)) / (2 * q)
        out.append(dict(t=a, gross=0.5 * (rl + rs), net=0.5 * (rl + rs) - turn * FEE,
                        hi_ex=(r[list(hi)].mean() - r[p.index].mean())))
        prev_l, prev_s = lo, hi
    W = pd.DataFrame(out)
    cut = W.t.quantile(0.6)
    t = W.net.mean() / W.net.std() * np.sqrt(len(W))
    print(f"\nWEEKLY long-low / short-high premium quintiles: {len(W)} weeks")
    print(f"  gross {W.gross.mean()*100:+.3f}%/wk  net {W.net.mean()*100:+.3f}%/wk  t {t:+.2f}  "
          f"tune {W.net[W.t < cut].mean()*100:+.3f}  hold {W.net[W.t >= cut].mean()*100:+.3f}")
    print(f"  top-premium quintile excess return vs all eligible: {W.hi_ex.mean()*100:+.3f}%/wk")
    print("  by year (net %/wk): " + "  ".join(f"{y}: {v.mean()*100:+.2f}" for y, v in
                                               W.net.groupby(W.t.dt.year)))

    # event version: premium crosses +5%
    ev = []
    for c in prem.columns:
        s = prem[c]
        cross = (s > 0.05) & (s.shift(1) <= 0.05)
        for d0 in s.index[cross.fillna(False).to_numpy(bool)]:
            k = prem.index.get_loc(d0)
            if k + 8 >= len(prem.index):
                continue
            a, b = prem.index[k + 1], prem.index[k + 8]
            rc = O.at[b, c] / O.at[a, c] - 1
            rm = (O.loc[b] / O.loc[a] - 1).mean()
            ev.append(dict(t=a, coin=c, ex=rc - rm))
    E = pd.DataFrame(ev)
    if len(E):
        cut = E.t.quantile(0.6)
        print(f"\nEVENT: coin premium crosses +5%: {len(E)} events, 7-day excess return "
              f"{E.ex.mean()*100:+.2f}% (median {E.ex.median()*100:+.2f}%), "
              f"tune {E.ex[E.t < cut].mean()*100:+.2f}%  hold {E.ex[E.t >= cut].mean()*100:+.2f}%")


if __name__ == "__main__":
    main()


def event_costed(thr=0.05, seed=3):
    """The +5% event, costed: short the coin / long the equal-weight basket for 7 days,
    12bp per leg, the coin's actual funding (a short receives it), t clustered by WEEK, and a
    placebo on the same coins at random weeks. POST-HOC: this looks again at data that has
    already produced the event result, so it decides only whether a FORWARD test is worth
    running - it cannot confirm anything."""
    C, O, K, F = panel()
    idx = C.index.intersection(K.index)
    C, O, K, F = C.loc[idx], O.loc[idx], K.loc[idx], F.reindex(idx).fillna(0.0)
    ratio = K / C
    prem = (ratio.div(ratio["BTC"], axis=0) - 1).drop(columns=["BTC"])
    rng = np.random.default_rng(seed)
    ev, pl = [], []
    for c in prem.columns:
        s = prem[c]
        cross = ((s > thr) & (s.shift(1) <= thr)).fillna(False).to_numpy(bool)
        for k in np.nonzero(cross)[0]:
            for kk, store in ((k, ev), (int(rng.integers(30, len(s) - 9)), pl)):
                if kk + 8 >= len(s) or not np.isfinite(O[c].iloc[kk + 1]) or not np.isfinite(O[c].iloc[kk + 8]):
                    continue
                a, b = prem.index[kk + 1], prem.index[kk + 8]
                rc = O.at[b, c] / O.at[a, c] - 1
                rm = np.nanmean((O.loc[b] / O.loc[a] - 1).to_numpy())
                fund = F.loc[(F.index > a) & (F.index <= b), c].sum()
                store.append(dict(t=a, net=-(rc - rm) + fund - 2 * FEE))
    E, P = pd.DataFrame(ev), pd.DataFrame(pl)
    wk = E.groupby(E.t.dt.to_period("W")).net.mean()
    cut = E.t.quantile(0.6)
    print(f"\nEVENT, costed (post-hoc): {len(E)} events in {len(wk)} weeks | short coin vs basket 7d")
    print(f"  net {E.net.mean()*100:+.2f}%/event (median {E.net.median()*100:+.2f}%, win "
          f"{(E.net > 0).mean()*100:.0f}%)  t(week-clustered) {wk.mean() / wk.std() * np.sqrt(len(wk)):+.2f}")
    print(f"  tune {E.net[E.t < cut].mean()*100:+.2f}%  hold {E.net[E.t >= cut].mean()*100:+.2f}%  "
          f"| placebo (same coins, random weeks) {P.net.mean()*100:+.2f}%")
    print("  by year: " + "  ".join(f"{y}: {v.mean()*100:+.2f}% (n{len(v)})"
                                    for y, v in E.net.groupby(E.t.dt.year)))


if __name__ == "__main__" and "--event" in sys.argv:
    event_costed()

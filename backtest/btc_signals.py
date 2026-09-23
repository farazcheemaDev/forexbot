"""WHAT MOVES BTC, AND DOES KNOWING IT HELP THE BOT? - fourteen market-timing signals.

THE ASK (2026-09-23): "find the best signals that trigger BTC or where the market moves, and
a strategy we can apply to the current bot... because we know when to stop."

The bot already uses two BTC signals: a 1000h average as a risk gate, and BTC's 4h trend
break to tighten alt trails (btc_exit.py; confirmed on the corrected engine). doc 02 found
that BTC REVERSAL patterns predict nothing (btc_exit.py) and that coin funding, BTC funding,
stablecoin growth, Fear & Greed and open-interest change predict nothing about the bot's
trades (entry_features.py). What had never been tested are the classic MARKET-TIMING inputs
that are not price patterns:

    F1  cb_prem      Coinbase premium, 7d mean: CB BTC-USD / (Binance BTCUSDT x USDT-USD) - 1.
                     US spot demand (the "Coinbase Premium Index").                 pred +
    F2  cb_prem_chg  7d mean premium minus its 30d mean - demand turning.            pred +
    F3  oi_vs_px     BTC 7d open-interest change minus 7d price change - a rally built
                     on leverage rather than spot.                                   pred -
    F4  toptrader    BTC top traders' position long/short ratio, 7d change.          pred +
    F5  taker        BTC taker buy/sell volume ratio, 7d mean - aggressive buying.   pred +
    F6  alt_vs_btc   12-coin equal-weight 30d return minus BTC's - "alt season".      pred +
    F7  mvrv         MVRV (market cap / realised cap) - on-chain overvaluation.      pred -
    F8  netflow      exchange inflow - outflow (USD), 7d sum / market cap - coins moving
                     onto exchanges to be sold.                                      pred -
    F9  qqq_trend    QQQ close / its 50-day average - equities risk-on.               pred +
    F10 dxy_trend    DXY 20-day change - dollar strength.                            pred -
    F11 vix          VIX level - risk-off.                                           pred -
    F12 tsmom        sign(BTC 7d) + sign(28d) + sign(90d) - time-series momentum at the
                     1-12 week horizons Liu & Tsyvinski (RFS 2021) document.         pred +
    F13 btc_vol      BTC 30d realised vol, percentile of its trailing year - trends live
                     in high vol (vol_target.py).                                    pred +
    F14 adr_growth   active addresses, 30d growth - network adoption (Liu-Tsyvinski's
                     network factor).                                                pred +

    Every feature for day D uses data through the END of day D-1 (Yahoo equities: the last
    close before D). Sources: Coinbase Exchange API, Binance metrics archive, CoinMetrics
    community API, Yahoo Finance daily - all cached under strategy_analysis/data/signals/.

TWO TARGETS
    (a) BTC's next-7-day return, sampled every 7th day so windows never overlap.
    (b) The bot's own trades: every LONG position tight + time stop would open (corrected
        engine: real entry time, funding charged), R capped [-25, +100], feature taken on the
        entry day. Top tercile minus bottom tercile.
    t-statistics from a month-block bootstrap. Holm across the 14 features, per target.

PASS RULE (registered before any result): the predicted sign on BOTH halves of target (b) and
a Holm-corrected pooled p < 0.05. Only a pass goes on to an application test (a risk dial on
the book, against a uniform-risk control at the same drawdown).

REGISTERED EXPECTATION: at most two pass. The likeliest are tsmom (it is the 1000h gate's
cousin, so it may pass and still add nothing on top of the gate) and cb_prem.

    python -m backtest.btc_signals
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SIG = ROOT / "strategy_analysis" / "data" / "signals"
METRICS = ROOT / "strategy_analysis" / "data" / "metrics"
CAP = (-25.0, 100.0)
PRED = dict(cb_prem=+1, cb_prem_chg=+1, oi_vs_px=-1, toptrader=+1, taker=+1, alt_vs_btc=+1,
            mvrv=-1, netflow=-1, qqq_trend=+1, dxy_trend=-1, vix=-1, tsmom=+1, btc_vol=+1,
            adr_growth=+1)


def daily_btc():
    d = blend.load("BTCUSDT")
    s = pd.Series(d["close"].to_numpy(float), index=pd.DatetimeIndex(d["time"]))
    return s


def features():
    """DataFrame indexed by UTC day D; every column known before D starts."""
    btc_h = daily_btc()
    btc_close = btc_h.resample("D").last()                       # close of day D
    f = pd.DataFrame(index=btc_close.index)

    # F1/F2 Coinbase premium (hourly -> daily mean)
    cb = pd.read_csv(SIG / "coinbase_BTC-USD_1h.csv.gz", parse_dates=["t"]).set_index("t")["close"]
    ut = pd.read_csv(SIG / "coinbase_USDT-USD_1h.csv.gz", parse_dates=["t"]).set_index("t")["close"]
    bn = btc_h.copy(); bn.index = bn.index + pd.Timedelta(hours=1)   # 1h CLOSE time
    cb.index = cb.index + pd.Timedelta(hours=1)
    ut.index = ut.index + pd.Timedelta(hours=1)
    j = pd.concat([cb.rename("cb"), bn.rename("bn"), ut.rename("ut")], axis=1)
    j["ut"] = j["ut"].fillna(1.0)
    prem = (j.cb / (j.bn * j.ut) - 1).dropna()
    prem = prem[prem.abs() < 0.05]                                   # glitches out
    pd_ = prem.resample("D").mean()
    f["cb_prem"] = pd_.rolling(7).mean()
    f["cb_prem_chg"] = pd_.rolling(7).mean() - pd_.rolling(30).mean()

    # F3-F5 Binance metrics archive (BTC)
    m = pd.read_csv(METRICS / "BTCUSDT.csv.gz", parse_dates=["create_time"]).set_index("create_time").sort_index()
    oi = m["sum_open_interest_value"].resample("D").last()
    f["oi_vs_px"] = np.log(oi).diff(7) - np.log(btc_close).diff(7)
    f["toptrader"] = m["sum_toptrader_long_short_ratio"].resample("D").mean().diff(7)
    f["taker"] = m["sum_taker_long_short_vol_ratio"].resample("D").mean().rolling(7).mean()

    # F6 alt season
    rets = {}
    for c in blend.BOOK:
        d = blend.load(c)
        if d is None:
            continue
        s = pd.Series(d["close"].to_numpy(float), index=pd.DatetimeIndex(d["time"])).resample("D").last()
        rets[c] = s.pct_change(30)
    f["alt_vs_btc"] = pd.DataFrame(rets).mean(axis=1) - btc_close.pct_change(30)

    # F7/F8/F14 CoinMetrics
    def cm(name):
        x = pd.read_csv(SIG / f"cm_{name}.csv", parse_dates=["t"]).set_index("t")[name]
        return x.resample("D").last()
    f["mvrv"] = cm("CapMVRVCur")
    f["netflow"] = (cm("FlowInExUSD") - cm("FlowOutExUSD")).rolling(7).sum() / cm("CapMrktCurUSD")
    f["adr_growth"] = cm("AdrActCnt").rolling(7).mean().pct_change(30)

    # F9-F11 Yahoo (US close is ~21:00 UTC: known before the next UTC day starts)
    def yh(name):
        x = pd.read_csv(SIG / f"yahoo_{name}.csv", parse_dates=["t"]).set_index("t")["close"]
        x.index = x.index.normalize()
        return x.resample("D").last().ffill()
    q = yh("QQQ")
    f["qqq_trend"] = q / q.rolling(50).mean() - 1
    f["dxy_trend"] = yh("DX-Y_NYB").pct_change(20)
    f["vix"] = yh("VIX")

    # F12/F13 BTC itself
    f["tsmom"] = sum(np.sign(btc_close.pct_change(k)) for k in (7, 28, 90))
    rv = np.log(btc_close).diff().rolling(30).std()
    f["btc_vol"] = rv.rolling(365, min_periods=120).rank(pct=True)

    # everything above is "as of the end of day D"; the trading day that can use it is D+1
    f = f.shift(1)
    f["btc_open"] = btc_h.resample("D").first()                     # price at 00:00 of D
    return f


def boot_t(x, t, reps=2000, seed=7):
    """t of a mean with whole calendar months resampled."""
    x = np.asarray(x, float); m = pd.DatetimeIndex(t).to_period("M").astype(str)
    um, inv = np.unique(m, return_inverse=True)
    s = np.bincount(inv, weights=x); c = np.bincount(inv)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(um), size=(reps, len(um)))
    bs = s[pick].sum(1) / c[pick].sum(1)
    return float(x.mean() / bs.std()) if bs.std() > 0 else np.nan


def spread_t(v, y, t, reps=2000, seed=7):
    """Top-minus-bottom tercile mean of y by v, and its month-block bootstrap t."""
    v = np.asarray(v, float); y = np.asarray(y, float)
    lo, hi = np.nanquantile(v, [1 / 3, 2 / 3])
    if not (hi > lo):
        return np.nan, np.nan
    est = y[v >= hi].mean() - y[v <= lo].mean()
    m = pd.DatetimeIndex(t).to_period("M").astype(str)
    um, inv = np.unique(m, return_inverse=True)
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(reps):
        pick = rng.integers(0, len(um), len(um))
        idx = np.concatenate([np.nonzero(inv == k)[0] for k in pick])
        vv, yy = v[idx], y[idx]
        a, b = yy[vv >= hi], yy[vv <= lo]
        if len(a) > 5 and len(b) > 5:
            bs.append(a.mean() - b.mean())
    se = np.std(bs)
    return float(est), float(est / se) if se > 0 else np.nan


def holm(ps):
    order = np.argsort(ps); m = len(ps); adj = np.ones(m); run = 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (m - k) * ps[i])); adj[i] = run
    return adj


def main():
    from scipy.stats import norm
    from backtest.graveyard_rescore import rows as book_rows

    F = features()
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]

    # ---- target (a): BTC next 7 days, non-overlapping weekly samples ----
    W = F.iloc[::7].copy()
    W["fwd"] = F["btc_open"].shift(-7).iloc[::7] / W["btc_open"] - 1
    W = W.dropna(subset=["fwd"])
    print(f"TARGET (a): BTC next-7-day return, {len(W)} non-overlapping weeks "
          f"{W.index[0]:%Y-%m} .. {W.index[-1]:%Y-%m} | tune < {cut:%Y-%m-%d} <= holdout")
    print(f"  {'feature':<12}{'pred':>5}{'n':>5}{'top-bot tercile, %/wk':>24}{'t':>7}"
          f"{'TUNE':>8}{'HOLD':>8}")
    for k, sgn in PRED.items():
        g = W[[k, "fwd"]].dropna()
        if len(g) < 40:
            print(f"  {k:<12} too few"); continue
        est, t = spread_t(g[k], g.fwd, g.index)
        tu = g[g.index < cut]; ho = g[g.index >= cut]
        e1, _ = spread_t(tu[k], tu.fwd, tu.index, reps=10) if len(tu) > 30 else (np.nan, 0)
        e2, _ = spread_t(ho[k], ho.fwd, ho.index, reps=10) if len(ho) > 30 else (np.nan, 0)
        print(f"  {k:<12}{sgn:>+5d}{len(g):>5}{est*100:>+23.2f}%{t:>+7.2f}{e1*100:>+7.2f}%{e2*100:>+7.2f}%")

    # ---- target (b): the bot's own long trades ----
    rows = book_rows(tight=True, time_stop=(100, 2.0))
    L = pd.DataFrame([dict(t=pd.Timestamp(r["t0"]), R=float(np.clip(r["R"], *CAP)))
                      for r in rows if r["side"] == "long"])
    L["day"] = L.t.dt.normalize()
    L = L.join(F.drop(columns=["btc_open"]), on="day")
    print(f"\nTARGET (b): the bot's LONG positions (tight + time stop, corrected engine), "
          f"{len(L):,}; R capped {CAP}")
    print(f"  {'feature':<12}{'pred':>5}{'n':>6}{'TUNE':>8}{'HOLD':>8}{'ALL':>8}{'t':>7}{'p':>7}{'Holm':>7}  verdict")
    res = []
    for k, sgn in PRED.items():
        g = L[["t", "R", k]].dropna()
        if len(g) < 300:
            res.append((k, sgn, len(g), np.nan, np.nan, np.nan, np.nan, 1.0)); continue
        tu = g[g.t < cut]; ho = g[g.t >= cut]
        a, _ = spread_t(tu[k], tu.R, tu.t, reps=10)
        b, _ = spread_t(ho[k], ho.R, ho.t, reps=10)
        c, t = spread_t(g[k], g.R, g.t)
        p = float(2 * (1 - norm.cdf(abs(t)))) if np.isfinite(t) else 1.0
        res.append((k, sgn, len(g), a, b, c, t, p))
    adj = holm(np.array([r[7] for r in res]))
    for (k, sgn, n, a, b, c, t, p), h in zip(res, adj):
        ok = np.isfinite(a) and np.sign(a) == sgn and np.sign(b) == sgn
        v = "PASS" if ok and h < 0.05 else ("sign holds, not sig" if ok else "fails")
        print(f"  {k:<12}{sgn:>+5d}{n:>6}{a:>+8.2f}{b:>+8.2f}{c:>+8.2f}{t:>+7.2f}{p:>7.3f}{h:>7.3f}  {v}")
    F.to_csv(ROOT / "logs" / "btc_signals_features.csv.gz", compression="gzip")


if __name__ == "__main__":
    main()

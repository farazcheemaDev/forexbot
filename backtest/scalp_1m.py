"""SCALPING BTC AND DOGE ON 1-MINUTE BARS AT 30-40x - does a small edge plus leverage make money?

THE USER'S IDEA (2026-10-06)
    "more leverage like 30 40x ... stick with one or two like BTC and DOGE ... 1 minute graph and RSI and
    something, with even a small edge we can make money because of leverage."

THE ARITHMETIC THAT COMES FIRST
    Fees are charged on the POSITION, not the margin. Bitget perps: taker 0.06%, maker 0.02% a side.
      round trip    1x      10x     20x     30x     40x      (share of the ACCOUNT per trade)
      taker 12bp    0.12%   1.2%    2.4%    3.6%    4.8%
      maker  4bp    0.04%   0.4%    0.8%    1.2%    1.6%
    Leverage multiplies the edge AND the fee by the same number, so it can never turn a trade that loses after fees
    into one that wins. It only decides how fast the answer arrives. The question is whether any 1-minute rule is
    positive AFTER fees; leverage is the second question.

DATA
    Binance USDT-M perp 1m bars, BTCUSDT and DOGEUSDT, 2022-01 .. 2026-08 (data.binance.vision monthly archive,
    cached in strategy_analysis/data/min1/), funding from the perps archive (odds_now.fund_by_bar).
    Split 60/40 by time (rule 2).

RULES (signal at a closed bar, entry at the next bar's open, one trade at a time per coin)
    rsi_rev    RSI14 crosses up through 30 -> long; down through 70 -> short
    rsi_trend  close > EMA200 and RSI14 < 30 -> long; close < EMA200 and RSI14 > 70 -> short
    rsi_mom    RSI14 crosses 50 upward with close > EMA50 -> long; mirror short
    ema_cross  EMA9 crosses EMA21
    bb_rev     close under the lower Bollinger(20, 2) -> long; over the upper -> short
    bb_break   close over the upper -> long; under the lower -> short
    donchian   close above the prior 60-bar high -> long; below the 60-bar low -> short
    btc_lead   DOGE only: BTC's last 1m return beyond 2 sigma (60-bar) while DOGE has moved under half of
               beta x that (beta over 1440 bars) -> trade DOGE in BTC's direction
    cells      odds_now's 150 cells (RSI14 x 24-bar move in ATR x 50-bar range position x BTC above/below its
               60,000-minute = 1000h mean), on 1m bars
EXITS   stop 2 x ATR14(1m) = 1R; target 1R or 2R; timeout 60 bars; pessimistic fills (odds_now.races).
COSTS   gross, 4bp (maker both sides - an UPPER bound: every limit fills, no adverse selection), 12bp (taker, rule 1).
        Funding charged. DOGE's spread (1 tick, ~0.3-1.2bp) is NOT added - flatters DOGE slightly.
VERDICT per (coin, rule, side, target, fee): mean net > 0 on BOTH halves; EDGE if t > 4.0 (Bonferroni over every
        test run), WEAK if t > 2.4.

LEVERAGE  The rule or cell with the best TUNE-half mean net at each fee (n >= 200 tune trades) is replayed on the
        HOLDOUT from 4,000 PKR, the whole margin in every trade, at 1/10/20/30/40x: each trade multiplies equity by
        1 + lev x net%. A trade whose loss reaches 1/lev - 0.5% of the position (Bitget maintenance) liquidates the
        margin. Selected on tune, judged on holdout - a fair out-of-sample test of "small edge x leverage".

REGISTERED BEFORE THE RUN (2026-10-06)
    - Fee toll: a 1m 2xATR stop on BTC is ~0.10-0.15% of price, so 12bp is ~1R a trade; DOGE ~0.5-0.8R. Doc 02
      calls anything over ~0.15R hopeless.
    - 12bp: 0 tests net-positive on both halves with t > 2.4. 4bp: 0-2.
    - Gross edges of the named rules within about +-1bp a trade. Reversion rules may read slightly positive GROSS
      from bid-ask bounce in close prices - untradeable, the spread is that bounce.
    - btc_lead: positive gross on DOGE, smaller than the fee (DOGE follows BTC within seconds, not a minute).
    - Leverage: the tune-selected rule at 30-40x loses >= 90% of 4,000 PKR on the holdout at 12bp AND at 4bp.

RESULT (2026-10-06, logs/scalp_1m.txt, logs/scalp_1m_tests.csv, logs/scalp_1m_kelly.txt; holdout from 2024-10-19)
    - Fee toll as predicted: 1m stop median 0.122% (BTC) / 0.240% (DOGE) of price -> 12bp = 0.98R / 0.50R a trade.
    - 572 tests per fee level. Gross: 8 EDGE (t > 4, both halves) - ALL SHORTS, +0.5 to +1.9bp a trade (1m
      downside moves are faster than upside ones). Maker 4bp: 4 net-positive, 1 WEAK, 0 EDGE. Taker 12bp: 0 of 572.
      Every prediction right; btc_lead short +1.6bp gross was a little above the "+-1bp" guess.
    - The tune-best rule, replayed on the holdout from 4,000 PKR: 40x is under 10% after 22 trades (taker) / 42
      (maker); 30x after 42 / 53. Random BTC 1m trades at 40x: under 10% after 45 trades (taker).
    - --kelly, "a small edge plus leverage": growth per trade = lev x mean - lev^2 x variance / 2, so a small edge
      has a small best leverage. Tune-half Kelly on the three best gross edges at ZERO fees: 11.3x / 4.0x / 6.8x.
      At 30x and 40x ALL THREE lose the whole account on the holdout even with zero fees (prediction: >= 2 of 3).
      At the cheapest real cost (maker 0%, 2bp taker on stops) two of three lose at every leverage; the third
      (a cell chosen on the full sample) earns +0.56bp a trade at 1x and is ruined from 10x up.
    Reading: leverage cannot create an edge and does not rescue a small one - past the Kelly leverage it destroys
    it. A 1m edge of 1-2bp needs fees near zero AND leverage near 5x, and then it is ~1bp a trade on 4,000 PKR.

    python -m backtest.scalp_1m            # downloads once (~215 MB of zips), then runs
    python -m backtest.scalp_1m --kelly    # the leverage question on the three best gross edges
"""
from __future__ import annotations

import io
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import odds_now as on  # noqa: E402
from backtest.metrics_fetch import BASE, get  # noqa: E402

DIR = ROOT / "strategy_analysis" / "data" / "min1"
LOG = ROOT / "logs" / "scalp_1m.txt"
COINS = ("BTCUSDT", "DOGEUSDT")
MONTHS = [str(p) for p in pd.period_range("2022-01", "2026-08", freq="M")]
HOLD = 60
KS = (1, 2)
FEES = {"gross": 0.0, "maker 4bp": 0.0004, "taker 12bp": 0.0012}
T_EDGE, T_WEAK = 4.0, 2.4
LEVS = (1, 10, 20, 30, 40)
START_PKR = 4000.0
MAINT = 0.005
CHUNK = 250_000


# ---------------------------------------------------------------- data

def one_month(sym, m):
    raw = get(f"{BASE}/data/futures/um/monthly/klines/{sym}/1m/{sym}-1m-{m}.zip")
    z = zipfile.ZipFile(io.BytesIO(raw))
    d = pd.read_csv(z.open(z.namelist()[0]), header=None, usecols=[0, 1, 2, 3, 4])
    d = d[pd.to_numeric(d[0], errors="coerce").notna()].astype(float)        # newer files have a header
    d.columns = ["t", "o", "h", "l", "c"]
    t = d["t"].to_numpy(np.int64)
    d["t"] = np.where(t > 10 ** 14, t // 1000, t)                             # microseconds -> ms
    return d


def load(sym):
    DIR.mkdir(parents=True, exist_ok=True)
    f = DIR / f"{sym}_1m.parquet"
    if f.exists():
        return pd.read_parquet(f)
    t0 = time.time()
    with ThreadPoolExecutor(8) as ex:
        parts = list(ex.map(lambda m: one_month(sym, m), MONTHS))
    d = pd.concat(parts).drop_duplicates("t").sort_values("t", kind="stable").reset_index(drop=True)
    d.insert(0, "time", pd.to_datetime(d.pop("t"), unit="ms").astype("datetime64[ns]"))
    if len(d) < 0.9 * len(MONTHS) * 30 * 1440:
        raise SystemExit(f"{sym}: only {len(d):,} 1m bars - the download is incomplete")
    d.to_parquet(f)
    print(f"  {sym}: {len(d):,} bars {d.time.iloc[0]} .. {d.time.iloc[-1]} ({time.time() - t0:.0f}s)", flush=True)
    return d


# ---------------------------------------------------------------- outcomes and signals

def outcomes(d, sym, atr):
    """gross % (of position), gross R, code and bars held for every bar, both sides, both targets. Chunked."""
    o, h, l, c = (d[k].to_numpy(float) for k in "ohlc")
    fc = on.fund_by_bar(sym, d.time, o)
    n = len(d)
    out = {}
    for side_name, s in on.SIDES.items():
        for k in KS:
            out[(side_name, k)] = {x: np.full(n, np.nan) for x in ("code", "R", "pct", "held")}
        for a in range(0, n, CHUNK):
            b = min(a + CHUNK + HOLD, n)
            res = on.races(o[a:b], h[a:b], l[a:b], c[a:b], atr[a:b], s, fc[a:b], ks=KS, hold=HOLD, fee=0.0)
            m = min(CHUNK, b - a)
            for k in KS:
                for x, v in zip(("code", "R", "pct", "held"), res[k]):
                    out[(side_name, k)][x][a:a + m] = v[:m]
    return out


def ema(x, span):
    return pd.Series(x).ewm(span=span, adjust=False).mean().to_numpy()


def cross_up(a, b):
    return np.r_[False, (a[1:] > b[1:]) & (a[:-1] <= b[:-1])]


def rules(d, f, btc=None):
    """{rule: (long signal, short signal)} - every array reads bar i and earlier only."""
    c, h, l = (d[k].to_numpy(float) for k in "chl")
    rsi = f["rsi"]
    e9, e21, e50, e200 = ema(c, 9), ema(c, 21), ema(c, 50), ema(c, 200)
    mid = pd.Series(c).rolling(20).mean().to_numpy()
    sd = pd.Series(c).rolling(20).std(ddof=0).to_numpy()
    hi60 = pd.Series(h).rolling(60).max().shift(1).to_numpy()
    lo60 = pd.Series(l).rolling(60).min().shift(1).to_numpy()
    r30, r50, r70 = np.full_like(rsi, 30), np.full_like(rsi, 50), np.full_like(rsi, 70)
    out = {
        "rsi_rev": (cross_up(rsi, r30), cross_up(r70, rsi)),
        "rsi_trend": ((c > e200) & (rsi < 30), (c < e200) & (rsi > 70)),
        "rsi_mom": (cross_up(rsi, r50) & (c > e50), cross_up(r50, rsi) & (c < e50)),
        "ema_cross": (cross_up(e9, e21), cross_up(e21, e9)),
        "bb_rev": (c < mid - 2 * sd, c > mid + 2 * sd),
        "bb_break": (c > mid + 2 * sd, c < mid - 2 * sd),
        "donchian": (c > hi60, c < lo60),
    }
    if btc is not None:
        rb = np.r_[np.nan, np.diff(np.log(btc))]
        rd = np.r_[np.nan, np.diff(np.log(c))]
        sig = pd.Series(rb).rolling(60).std().to_numpy()
        cov = pd.Series(rb).rolling(1440).cov(pd.Series(rd)).to_numpy()
        beta = cov / pd.Series(rb).rolling(1440).var().to_numpy()
        lag = rd < 0.5 * beta * rb
        out["btc_lead"] = ((rb > 2 * sig) & lag, (rb < -2 * sig) & ~lag & (rd > 0.5 * beta * rb))
    return out


def valid_mask(d):
    """No window (features back to WARMUP, outcome forward to HOLD) may cross a missing minute or a >50% jump."""
    t = d.time.to_numpy("datetime64[ns]").astype(np.int64)
    o, c = d.o.to_numpy(float), d.c.to_numpy(float)
    bad = np.zeros(len(d), bool)
    bad[1:] = (np.diff(t) != 60_000_000_000) | (np.abs(np.log(o[1:] / c[:-1])) > np.log(1.5))
    cb = np.r_[0, np.cumsum(bad)]
    i = np.arange(len(d))
    lo, hi = np.maximum(i - on.WARMUP + 1, 0), np.minimum(i + HOLD + 1, len(d) - 1)
    return (cb[hi + 1] - cb[lo]) == 0


# ---------------------------------------------------------------- statistics

def take(times_min, sig, held):
    """Indices of non-overlapping trades among the signal bars."""
    idx = np.flatnonzero(sig)
    keep = on.no_overlap(np.zeros(len(idx), np.int64), times_min[idx], held[idx].astype(np.int64))
    return idx[keep]


def stats(pct, days):
    n = len(pct)
    if n < 2:
        return dict(n=n, mean=np.nan, se=np.nan, t=np.nan)
    mu = pct.mean()
    s = pd.Series(pct - mu).groupby(days).sum().to_numpy()
    g = len(s)
    se = np.sqrt((s ** 2).sum() * g / max(g - 1, 1)) / n
    return dict(n=n, mean=mu, se=se, t=mu / se if se > 0 else np.nan)


def evaluate(name, coin, side, k, idx, oc, times, days, split):
    """One test at every fee level. pct is in % of the position."""
    gp = oc["pct"][idx]
    tune = times[idx] < split
    rows = []
    for fee_name, fee in FEES.items():
        net = gp - fee * 100
        a, tu, ho = stats(net, days[idx]), stats(net[tune], days[idx][tune]), stats(net[~tune], days[idx][~tune])
        both = tu["n"] >= 30 and ho["n"] >= 30 and tu["mean"] > 0 and ho["mean"] > 0
        level = ("EDGE" if both and a["t"] > T_EDGE else "WEAK" if both and a["t"] > T_WEAK
                 else "pos" if both else "-")
        rows.append(dict(rule=name, coin=coin, side=side, k=k, fee=fee_name, n=a["n"], mean=a["mean"], t=a["t"],
                         tune=tu["mean"], hold=ho["mean"], n_tune=tu["n"], level=level,
                         p_tp=float((oc["code"][idx] == 1).mean()) if len(idx) else np.nan))
    return rows


def leverage_path(net_pct, lev):
    """Holdout replay, whole margin in every trade. Returns final PKR, worst PKR, trade at ruin (or None)."""
    eq, low, ruin = START_PKR, START_PKR, None
    liq = 100.0 / lev - MAINT * 100
    for i, x in enumerate(net_pct):
        eq = 0.0 if -x >= liq else eq * (1 + lev * x / 100)
        low = min(low, eq)
        if ruin is None and eq < 0.1 * START_PKR:
            ruin = i + 1
        if eq <= 0:
            break
    return eq, low, ruin


# ---------------------------------------------------------------- main

def main():
    t_start = time.time()
    data = {s: load(s) for s in COINS}
    btc = data["BTCUSDT"]
    split = np.sort(btc.time.to_numpy())[int(len(btc) * 0.6)]
    btc_ma = pd.Series(btc.c.to_numpy(float)).rolling(60_000).mean().to_numpy()
    btc_bull = pd.Series(np.where(np.isfinite(btc_ma), (btc.c.to_numpy() > btc_ma).astype(float), np.nan),
                         index=btc.time)
    btc_close = pd.Series(btc.c.to_numpy(float), index=btc.time)
    lines, results, trade_store = [], [], {}
    for coin in COINS:
        d = data[coin]
        f = on.features(d.o, d.h, d.l, d.c)
        oc = outcomes(d, coin, f["atr"])
        ok = valid_mask(d) & f["ok"]
        times = d.time.to_numpy("datetime64[ns]")
        tmin = times.astype("datetime64[m]").astype(np.int64)
        days = times.astype("datetime64[D]")
        stop_pct = on.STOP_ATR * f["atr"] / d.o.shift(-1).to_numpy(float) * 100
        lines.append(f"{coin}: {len(d):,} 1m bars {d.time.iloc[0]:%Y-%m-%d} .. {d.time.iloc[-1]:%Y-%m-%d}; "
                     f"stop (2xATR14) median {np.nanmedian(stop_pct[ok]):.3f}% of price -> 12bp = "
                     f"{0.12 / np.nanmedian(stop_pct[ok]):.2f}R, 4bp = {0.04 / np.nanmedian(stop_pct[ok]):.2f}R a trade")
        bull = btc_bull.reindex(d.time).to_numpy(float)
        rl = rules(d, f, btc_close.reindex(d.time).to_numpy(float) if coin != "BTCUSDT" else None)
        tests = [(nm, si, sig) for nm, (lg, sh) in rl.items() for si, sig in (("long", lg), ("short", sh))]
        tests.append(("any minute", "long", np.ones(len(d), bool)))
        tests.append(("any minute", "short", np.ones(len(d), bool)))
        cellkey = (f["rsi_b"].astype(np.int64) * 100 + f["mom_b"] * 10 + f["loc_b"]) * 2 \
            + np.nan_to_num(bull).astype(np.int64)
        cell_ok = ok & np.isfinite(bull)
        for key in np.unique(cellkey[cell_ok]):
            sig = cell_ok & (cellkey == key)
            if sig.sum() < 200:
                continue
            r_, m_, l_, b_ = key // 200, (key // 20) % 10, (key // 2) % 10, key % 2
            nm = f"cell RSI {on.RSI_NAMES[r_]}, {on.MOM_NAMES[m_]}, {on.LOC_NAMES[l_]}, BTC {'bull' if b_ else 'bear'}"
            tests += [(nm, "long", sig), (nm, "short", sig)]
        for nm, side, sig in tests:
            for k in KS:
                o_k = oc[(side, k)]
                idx = take(tmin, sig & ok & np.isfinite(o_k["pct"]), np.nan_to_num(o_k["held"], nan=1))
                if len(idx) < 60:
                    continue
                results += evaluate(nm, coin, side, k, idx, o_k, times, days, split)
                trade_store[(nm, coin, side, k)] = (times[idx], o_k["pct"][idx])
        print(f"  {coin} done, {len(results):,} rows ({time.time() - t_start:.0f}s)", flush=True)

    R = pd.DataFrame(results)
    real = R[R.rule != "any minute"]
    n_tests = real.groupby("fee").size().iloc[0]
    lines.append(f"\nholdout from {pd.Timestamp(split):%Y-%m-%d}; {n_tests} tests per fee level "
                 f"(EDGE t > {T_EDGE}, WEAK t > {T_WEAK}, both halves net-positive for either)")
    lines.append("\nANY MINUTE (the coin flip), mean % of position per trade:")
    for _, r in R[R.rule == "any minute"].iterrows():
        lines.append(f"  {r.coin:8} {r.side:5} {r.k}R {r.fee:10}: {r['mean']:+.4f}%  (TP first {r.p_tp:.1%}, n {r.n})")
    lines.append("\nNAMED RULES, mean % of position per trade (tune / holdout), gross and after fees:")
    named = real[~real.rule.str.startswith("cell")]
    for (rule, coin, side, k), g in named.groupby(["rule", "coin", "side", "k"], sort=False):
        cells = "  ".join(f"{r.fee}: {r['mean']:+.4f} ({r.tune:+.4f}/{r.hold:+.4f}){'*' if r.level != '-' else ''}"
                          for _, r in g.iterrows())
        lines.append(f"  {rule:9} {coin:8} {side:5} {k}R n {g.n.iloc[0]:>6}  {cells}")
    lines.append("\nCOUNTS (all named rules + cells):")
    for fee_name in FEES:
        g = real[real.fee == fee_name]
        lines.append(f"  {fee_name:10}: {(g.level != '-').sum():4} net-positive on both halves, "
                     f"{(g.level == 'WEAK').sum():3} WEAK, {(g.level == 'EDGE').sum():3} EDGE, of {len(g)}")
    for fee_name in ("maker 4bp", "taker 12bp"):
        for _, r in real[(real.fee == fee_name) & real.level.isin(["WEAK", "EDGE"])].iterrows():
            lines.append(f"    {r.level} at {fee_name}: {r.rule} {r.coin} {r.side} {r.k}R  mean {r['mean']:+.4f}% "
                         f"t {r.t:+.1f}  tune {r.tune:+.4f} hold {r.hold:+.4f}  n {r.n}")

    lines.append(f"\nLEVERAGE: best TUNE-half rule at each fee, replayed on the HOLDOUT from {START_PKR:,.0f} PKR, "
                 "whole margin every trade:")
    for fee_name, fee in FEES.items():
        if fee == 0.0:
            continue
        g = real[(real.fee == fee_name) & (real.n_tune >= 200)].sort_values("tune", ascending=False)
        for pick in (g.iloc[0], R[(R.rule == "any minute") & (R.fee == fee_name) & (R.coin == "BTCUSDT")
                                  & (R.side == "long") & (R.k == 1)].iloc[0]):
            tt, gp = trade_store[(pick.rule, pick.coin, pick.side, pick.k)]
            hold = gp[tt >= split] - fee * 100
            lines.append(f"  [{fee_name}] {pick.rule} {pick.coin} {pick.side} {pick.k}R: tune {pick.tune:+.4f}%/trade, "
                         f"holdout {hold.mean():+.4f}%/trade over {len(hold)} trades")
            for lev in LEVS:
                fin, low, ruin = leverage_path(hold, lev)
                lines.append(f"      {lev:>2}x: end {fin:>12,.0f} PKR, lowest {low:>10,.0f}"
                             + (f", below 10% after {ruin} trades" if ruin else ""))
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(f"backtest/scalp_1m.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}\n\n{txt}\n")
    R.to_csv(ROOT / "logs" / "scalp_1m_tests.csv", index=False)
    print(f"\n-> {LOG}  ({time.time() - t_start:.0f}s)")


KELLY_PICKS = [("rsi_mom", "DOGEUSDT", "short", 2), ("rsi_mom", "BTCUSDT", "short", 2),
               ("cell RSI 30-45, flat, near support, BTC bull", "DOGEUSDT", "short", 2)]
KELLY_COSTS = {"zero fees": lambda code: 0.0,
               "maker 0% + 2bp taker on stop/timeout": lambda code: np.where(code == 1, 0.0, 0.02)}


def kelly():
    """"Even a small edge makes money with leverage" - tested on the three best BEFORE-fee edges of main().

    Registered before running (2026-10-06): growth per trade is lev x mean - lev^2 x variance / 2, so a small edge
    has a SMALL best leverage. Prediction: the tune-half Kelly leverage is single-digit to low-teens even at zero
    fees, and 30-40x loses money on the holdout even at zero fees for at least two of the three.
    (The cell pick was chosen on the full sample in main(); the two rsi_mom picks are plain named rules.)"""
    data = {s: load(s) for s in COINS}
    btc = data["BTCUSDT"]
    split = np.sort(btc.time.to_numpy())[int(len(btc) * 0.6)]
    btc_ma = pd.Series(btc.c.to_numpy(float)).rolling(60_000).mean().to_numpy()
    bull_s = pd.Series(np.where(np.isfinite(btc_ma), (btc.c.to_numpy() > btc_ma).astype(float), np.nan),
                       index=btc.time)
    lines = [f"backtest/scalp_1m.py --kelly, {pd.Timestamp.now():%Y-%m-%d %H:%M}, holdout from "
             f"{pd.Timestamp(split):%Y-%m-%d}; whole margin every trade from {START_PKR:,.0f} PKR", ""]
    for coin in COINS:
        d = data[coin]
        f = on.features(d.o, d.h, d.l, d.c)
        ok = valid_mask(d) & f["ok"]
        oc = outcomes(d, coin, f["atr"])
        times = d.time.to_numpy("datetime64[ns]")
        tmin = times.astype("datetime64[m]").astype(np.int64)
        rl = rules(d, f)
        bull = bull_s.reindex(d.time).to_numpy(float)
        for nm, c_, side, k in KELLY_PICKS:
            if c_ != coin:
                continue
            if nm.startswith("cell"):
                sig = (f["rsi_b"] == 1) & (f["mom_b"] == 2) & (f["loc_b"] == 0) & (bull == 1)
            else:
                sig = rl[nm][0 if side == "long" else 1]
            o_k = oc[(side, k)]
            idx = take(tmin, sig & ok & np.isfinite(o_k["pct"]), np.nan_to_num(o_k["held"], nan=1))
            tune = times[idx] < split
            for cname, cost in KELLY_COSTS.items():
                x = (o_k["pct"][idx] - cost(o_k["code"][idx])) / 100          # fraction of the position
                xt, xh = x[tune], x[~tune]
                kel = xt.mean() / xt.var()
                lines.append(f"{nm} {coin} {side} {k}R [{cname}]: tune {xt.mean() * 1e4:+.2f}bp/trade "
                             f"(n {len(xt)}), holdout {xh.mean() * 1e4:+.2f}bp (n {len(xh)}); "
                             f"tune-half Kelly leverage {kel:.1f}x")
                for lev in sorted({1, max(1, int(round(kel))), 10, 20, 30, 40}):
                    g = np.log(np.clip(1 + lev * xh, 1e-12, None)).mean()
                    fin, low, ruin = leverage_path(xh * 100, lev)
                    lines.append(f"    {lev:>2}x: growth {g * 1e4:+8.2f}bp/trade, end {fin:>14,.0f} PKR"
                                 + (f", below 10% after {ruin} trades" if ruin else ""))
        print(f"  {coin} done", flush=True)
    txt = "\n".join(lines)
    print(txt)
    (ROOT / "logs" / "scalp_1m_kelly.txt").write_text(txt + "\n")


if __name__ == "__main__":
    kelly() if "--kelly" in sys.argv else main()

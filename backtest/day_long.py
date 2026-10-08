"""A ONE-DAY LONG ON 10,000 PKR, CHOSEN BY EVERY COMBINATION OF INDICATORS - how does it play out?

THE USER'S QUESTION (2026-10-08)
    "Keep the bot aside. On 10k PKR, if we open a futures trade LONG for a DAY, with all calculations and all types
    of combinations of indicators, how will it play out?"

THE TRADE
    Decide at the daily close (00:00 UTC = 05:00 PKT) from daily bars built from Binance USDT-M perp 1h bars; go long
    at that hour's open; close exactly 24 hours later at the open of the next 00:00 hour. Costs: 12bp round trip and
    every funding settlement held (08:00, 16:00 and the closing 00:00). Coins: BTC, ETH, SOL, DOGE, XRP, 2020 ..
    2026-09. Liquidation at leverage L: the lowest 1h low during the 24 hours falls 1/L - 0.5% (maintenance) - 0.06%
    (entry fee) under the entry. Split 60/40 by date (rule 2).

THE 20 CONDITIONS (read at the daily close; long-side meanings)
    rsi<30  rsi>70  rsi50-70  >ema20  >ema50  ema20>ema50  >sma200  macd>signal  macd_hist_up  <lower_bb  >upper_bb
    stoch<20  dip>3%  pop>3%  vol>1.5x  20d_high  20d_low  adx>25  btc>ema50  funding<0
    Every single condition, every pair and every triple: 20 + 190 + 1,140 = 1,350 filters per coin, 6,750 tests.
    A filter is judged on its own days' mean net return at 1x against zero AND against "long every day" on the
    same coin. EDGE: both halves positive and above the every-day baseline, t > 4.4 (Bonferroni over 6,750);
    WEAK: the same with t > 2.4. Then the honest version of "pick the best indicators": the 10 best filters by the
    TUNE half (n >= 30), judged only on the holdout.

10,000 PKR ($35.71 at 280)
    On the holdout, for "long every day" and for the tune-picked best filter per coin, at 1/3/5/10/20/50x:
      fixed    10,000 PKR margin on every signal day (refilled): average PKR a day traded, best / worst day,
               liquidations, total
      all-in   the whole account every signal day, compounding: where 10,000 ends, and the day it is under 1,000

REGISTERED BEFORE THE RUN (2026-10-08)
    - Long every day, 1x, net: -0.05% to +0.05% a day per coin.
    - 0-3 of 6,750 filters are EDGE; WEAK at about the chance rate.
    - The 10 tune-best filters: on the holdout no better than long-every-day on average (within +-0.10% a day), and
      most of them lose more than half of their tune-half edge.
    - All-in at 10x or more: 10,000 PKR under 1,000 within weeks to months, for every-day and for the picked filters.

RESULT (2026-10-08, logs/day_long.txt, logs/day_long_combos.csv, logs/day_long_followup.txt; holdout 2024-03-31 ..)
    - Long every day, net: tune +0.05..+0.56%/day, HOLDOUT -0.09..-0.13%/day on BTC/ETH/SOL/DOGE (XRP +0.05).
      Predicted -0.05..+0.05: wrong on the holdout side (fees + funding in a sideways-to-down 2024-26 for most).
    - 6,750 filters: 0 EDGE (right); 97 WEAK against a guessed chance rate of 4-17 (WRONG - the filters overlap
      heavily and 60% contain btc>ema50: one alt-momentum effect counted many times, 50 of them on SOL).
    - Pick by the TUNE MEAN (pre-registered): the 10 picks were DOGE dip/oversold filters made by a few 2021 monster
      days (+7..+14%/day on 30-60 days); holdout +0.40%/day vs every-day -0.13 (predicted "no better": WRONG), 10 of
      10 lost more than half their tune edge (right). Per coin the top pick lost on the holdout: BTC -173, DOGE -131,
      SOL -45 PKR a trade at 1x on 10,000.
    - Leverage, 10,000 PKR, holdout: long every day loses at every leverage; all-in at 10x is under 1,000 PKR after
      1-13 trades (right), at 20x+ after 1.
    - --followup (descriptive, after looking): '20d_high & btc>ema50' (a daily breakout while BTC trends up) - BTC
      0.00, ETH +0.02, SOL +0.58, DOGE +2.21, XRP +2.83 %/day on 65-117 holdout days; without the best 3 days SOL
      +0.14, DOGE +1.11, XRP +1.99; 46-61% of DOGE/XRP's gain is 2024-11. On 10,000 PKR at 1-3x it made money on
      the three alts (XRP 3x all-in 639,941 PKR) and NOTHING on BTC/ETH; at 10x+ every coin was wiped out by
      intraday liquidations. Picked by the tune t-statistic instead, the 10 best (all SOL) gave +0.13%/day on the
      holdout vs -0.11. This is the trend book's own momentum, seen daily - and it was FOUND by looking at the
      holdout, so it is not an out-of-sample result.

    python -m backtest.day_long
    python -m backtest.day_long --followup
"""
from __future__ import annotations

import itertools
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PERPS = ROOT / "strategy_analysis" / "data" / "perps"
LOG = ROOT / "logs" / "day_long.txt"
COINS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "XRPUSDT")
FEE = 0.0012
MAINT = 0.005
LEVS = (1, 3, 5, 10, 20, 50)
STAKE = 10_000.0
T_EDGE, T_WEAK = 4.4, 2.4


# ---------------------------------------------------------------- data

def hourly(sym):
    d = pd.read_csv(PERPS / f"{sym}_1h.csv.gz", parse_dates=["time"])
    d["time"] = d["time"].astype("datetime64[ns]")
    return d.drop_duplicates("time").sort_values("time", kind="stable").set_index("time")


def funding_by_hour(sym):
    f = pd.read_csv(PERPS / f"{sym}_funding.csv.gz")
    t = pd.to_datetime(f["time"]).dt.floor("h").astype("datetime64[ns]")
    return pd.Series(f["rate"].to_numpy(float), index=t).groupby(level=0).sum()


def daily_bars(h):
    """UTC days. Only days with all 24 hours."""
    g = h.resample("1D")
    d = pd.DataFrame({"o": g["open"].first(), "h": g["high"].max(), "l": g["low"].min(), "c": g["close"].last(),
                      "v": g["qvol"].sum(), "n": g["close"].count()})
    return d[d.n == 24].drop(columns="n")


# ---------------------------------------------------------------- the 20 conditions (causal: day d reads <= d)

def ema(x, n):
    return x.ewm(span=n, adjust=False).mean()


def conditions(d, btc_close, fund_day):
    c, h, l, v = d.c, d.h, d.l, d.v
    dl = c.diff()
    up = dl.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-dl).clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / dn)
    e20, e50, s200 = ema(c, 20), ema(c, 50), c.rolling(200).mean()
    macd = ema(c, 12) - ema(c, 26)
    sig = ema(macd, 9)
    hist = macd - sig
    mid, sd = c.rolling(20).mean(), c.rolling(20).std(ddof=0)
    lo14, hi14 = l.rolling(14).min(), h.rolling(14).max()
    stoch = 100 * (c - lo14) / (hi14 - lo14)
    ret = c.pct_change()
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    pdm = (h.diff()).where((h.diff() > -l.diff()) & (h.diff() > 0), 0.0)
    ndm = (-l.diff()).where((-l.diff() > h.diff()) & (-l.diff() > 0), 0.0)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    pdi = 100 * pdm.ewm(alpha=1 / 14, adjust=False).mean() / atr
    ndi = 100 * ndm.ewm(alpha=1 / 14, adjust=False).mean() / atr
    adx = (100 * (pdi - ndi).abs() / (pdi + ndi)).ewm(alpha=1 / 14, adjust=False).mean()
    b = btc_close.reindex(d.index)
    cond = {
        "rsi<30": rsi < 30, "rsi>70": rsi > 70, "rsi50-70": (rsi >= 50) & (rsi <= 70),
        ">ema20": c > e20, ">ema50": c > e50, "ema20>ema50": e20 > e50, ">sma200": c > s200,
        "macd>signal": macd > sig, "macd_hist_up": hist > hist.shift(1),
        "<lower_bb": c < mid - 2 * sd, ">upper_bb": c > mid + 2 * sd, "stoch<20": stoch < 20,
        "dip>3%": ret < -0.03, "pop>3%": ret > 0.03, "vol>1.5x": v > 1.5 * v.rolling(20).mean().shift(1),
        "20d_high": c >= c.rolling(20).max(), "20d_low": c <= c.rolling(20).min(), "adx>25": adx > 25,
        "btc>ema50": b > ema(b, 50), "funding<0": fund_day.reindex(d.index).fillna(0.0) < 0,
    }
    ok = s200.notna() & b.notna()
    return {k: (v_.fillna(False).astype(bool) & ok).to_numpy() for k, v_ in cond.items()}, ok.to_numpy()


# ---------------------------------------------------------------- the trade, from the hourly bars

def outcomes(d, h, fund_h):
    """For a signal at the close of day i: long from the open of day i+1's 00:00 hour to the open of day i+2's 00:00
    hour. Returns net return (1x, after fees and funding) and the worst drop (lowest low over the 24 hours)."""
    idx = d.index
    o_h = h["open"]
    net = np.full(len(idx), np.nan)
    worst = np.full(len(idx), np.nan)
    lows = h["low"]
    fcum = fund_h.reindex(h.index).fillna(0.0).cumsum()
    for i in range(len(idx) - 2):
        t_in, t_out = idx[i + 1], idx[i + 2]
        if t_in not in o_h.index or t_out not in o_h.index:
            continue
        e, x = o_h[t_in], o_h[t_out]
        win = lows.loc[t_in:t_out - pd.Timedelta(hours=1)]
        if len(win) != 24:
            continue
        fund = fcum.loc[t_out] - fcum.loc[t_in]                    # settlements in (t_in, t_out]
        net[i] = x / e - 1 - FEE - fund
        worst[i] = 1 - win.min() / e
    return net, worst


# ---------------------------------------------------------------- statistics

def stats(x):
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 2:
        return n, np.nan, np.nan
    return n, x.mean(), x.mean() / (x.std(ddof=1) / np.sqrt(n))


def play(net, worst, lev, mode):
    """10,000 PKR. fixed: 10k margin every trade. allin: the whole account, compounding. Liquidation when the day's
    worst drop reaches 1/lev - maintenance - the entry fee."""
    liq = 1 / lev - MAINT - FEE / 2
    pnl = np.where(worst >= liq, -1.0, np.maximum(lev * net, -1.0))
    if mode == "fixed":
        p = STAKE * pnl
        return dict(avg=p.mean(), best=p.max(), worst=p.min(), liqs=int((worst >= liq).sum()), total=p.sum(),
                    up=(p > 0).mean())
    eq, under = STAKE, None
    for k, r in enumerate(pnl):
        eq *= 1 + r
        if under is None and eq < 1000:
            under = k + 1
        if eq <= 0:
            eq = 0.0
            break
    return dict(end=eq, under=under, liqs=int((worst >= liq).sum()))


# ---------------------------------------------------------------- main

def main():
    t0 = time.time()
    btc_h = hourly("BTCUSDT")
    btc_close = daily_bars(btc_h).c
    lines = [f"backtest/day_long.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; long at the daily close (00:00 UTC), out 24h "
             f"later; {FEE * 1e4:.0f}bp + funding; liquidation from the 1h lows", ""]
    data, split = {}, None
    for sym in COINS:
        h = hourly(sym)
        d = daily_bars(h)
        fh = funding_by_hour(sym)
        fund_day = fh.groupby(fh.index.floor("D")).sum()
        cond, ok = conditions(d, btc_close, fund_day)
        net, worst = outcomes(d, h, fh)
        good = ok & np.isfinite(net)
        data[sym] = dict(d=d, cond=cond, net=net, worst=worst, good=good)
        if split is None:
            dates = d.index[good]
            split = dates[int(len(dates) * 0.6)]
        print(f"  {sym}: {good.sum()} trade days ({time.time() - t0:.0f}s)", flush=True)
    lines.append(f"tune < {split:%Y-%m-%d} <= holdout\n")

    lines.append("1. LONG EVERY DAY, 1x, net of costs:")
    base = {}
    for sym, D in data.items():
        tune = (D["d"].index < split)
        g = D["good"]
        n_t, m_t, _ = stats(D["net"][g & tune])
        n_h, m_h, _ = stats(D["net"][g & ~tune])
        base[sym] = (m_t, m_h)
        lines.append(f"  {sym:9} tune {m_t * 100:+.3f}%/day (n {n_t}, up days {np.mean(D['net'][g & tune] > 0):.0%}) | "
                     f"holdout {m_h * 100:+.3f}%/day (n {n_h}, up days {np.mean(D['net'][g & ~tune] > 0):.0%})")

    names = list(next(iter(data.values()))["cond"])
    combos = [c for k in (1, 2, 3) for c in itertools.combinations(names, k)]
    recs = []
    for sym, D in data.items():
        tune = (D["d"].index < split)
        for cb in combos:
            m = D["good"].copy()
            for c in cb:
                m &= D["cond"][c]
            x_t, x_h = D["net"][m & tune], D["net"][m & ~tune]
            n, mu, t = stats(D["net"][m])
            n_t, m_t, _ = stats(x_t)
            n_h, m_h, _ = stats(x_h)
            recs.append(dict(coin=sym, combo=" & ".join(cb), k=len(cb), n=n, mean=mu, t=t, n_t=n_t, m_t=m_t,
                             n_h=n_h, m_h=m_h, b_t=base[sym][0], b_h=base[sym][1]))
    R = pd.DataFrame(recs)
    both = (R.n_t >= 30) & (R.n_h >= 30) & (R.m_t > 0) & (R.m_h > 0) & (R.m_t > R.b_t) & (R.m_h > R.b_h)
    R["level"] = np.where(both & (R.t > T_EDGE), "EDGE", np.where(both & (R.t > T_WEAK), "WEAK", "-"))
    R.to_csv(ROOT / "logs" / "day_long_combos.csv", index=False)
    tested = int(((R.n_t >= 30) & (R.n_h >= 30)).sum())
    lines.append(f"\n2. EVERY FILTER: {len(R):,} coin x filter tests, {tested:,} with 30+ days in each half")
    lines.append(f"  EDGE (both halves above zero and above long-every-day, t > {T_EDGE}): {(R.level == 'EDGE').sum()}")
    lines.append(f"  WEAK (same, t > {T_WEAK}): {(R.level == 'WEAK').sum()}   "
                 f"(chance alone gives roughly {tested * 0.008 * 0.25:.0f}-{tested * 0.008:.0f})")
    for r in R[R.level != "-"].sort_values("t", ascending=False).head(12).itertuples():
        lines.append(f"    {r.level} {r.coin:9} {r.combo:40} n {r.n:>4}  {r.mean * 100:+.2f}%/day (t {r.t:+.1f})  "
                     f"tune {r.m_t * 100:+.2f} / holdout {r.m_h * 100:+.2f}  vs every day {r.b_t * 100:+.2f} / {r.b_h * 100:+.2f}")

    lines.append("\n3. PICK THE BEST INDICATORS ON 2020-23 (tune half, 30+ days), THEN TRADE THEM ON THE HOLDOUT:")
    pick = R[R.n_t >= 30].sort_values("m_t", ascending=False).head(10)
    for r in pick.itertuples():
        lines.append(f"    {r.coin:9} {r.combo:40} tune {r.m_t * 100:+.2f}%/day (n {r.n_t}) -> holdout "
                     f"{r.m_h * 100:+.2f}%/day (n {r.n_h})   every day: {r.b_h * 100:+.2f}")
    lines.append(f"  average of the 10 on the holdout: {pick.m_h.mean() * 100:+.3f}%/day against long-every-day "
                 f"{np.mean([base[c][1] for c in pick.coin]) * 100:+.3f}%; lost more than half their tune edge: "
                 f"{int(((pick.m_h - pick.b_h) < 0.5 * (pick.m_t - pick.b_t)).sum())} of 10")

    lines.append(f"\n4. 10,000 PKR ON THE HOLDOUT ({split:%Y-%m-%d} .. ), long every day vs the tune-picked filter:")
    best_per = R[R.n_t >= 30].sort_values("m_t", ascending=False).groupby("coin").head(1).set_index("coin")
    for sym in ("BTCUSDT", "DOGEUSDT", "SOLUSDT"):
        D = data[sym]
        hold = D["good"] & (D["d"].index >= split)
        cb = best_per.loc[sym, "combo"].split(" & ")
        m_pick = hold.copy()
        for c in cb:
            m_pick &= D["cond"][c]
        for lab, m in (("long every day", hold), (f"picked: {' & '.join(cb)}", m_pick)):
            net, worst = D["net"][m], D["worst"][m]
            lines.append(f"  {sym} - {lab}: {m.sum()} trade days")
            for lev in LEVS:
                f_ = play(net, worst, lev, "fixed")
                a_ = play(net, worst, lev, "allin")
                lines.append(f"    {lev:>2}x  fixed 10k: avg {f_['avg']:+7.0f} PKR/trade, up {f_['up']:.0%}, best {f_['best']:+7.0f}, "
                             f"worst {f_['worst']:+7.0f}, liquidated {f_['liqs']:>3}x, total {f_['total']:+10,.0f} | all-in: "
                             f"ends {a_['end']:>12,.0f} PKR" + (f", under 1,000 after {a_['under']} trades" if a_['under'] else ""))
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")
    print(f"\n-> {LOG} ({time.time() - t0:.0f}s)")


def followup():
    """AFTER the main run (so NOT pre-registered as a pass/fail test - read it as a description):
      a) is the breakout filter's holdout gain a few days? drop the best 3 days, report the median and the months
      b) pick the 10 filters by TUNE t-statistic (consistency) instead of the tune mean, judge on the holdout
      c) 10,000 PKR on '20d_high & btc>ema50' per coin, holdout, every leverage
    Registered before running it: (a) without its best 3 days the breakout filter's holdout mean is under +0.3%/day on
    every coin, and most of it sits in 2024-11; (b) the t-picked 10 beat long-every-day on the holdout by less than
    +0.3%/day on average; (c) all-in at 10x+ is under 1,000 PKR within 20 trades on every coin."""
    btc_h = hourly("BTCUSDT")
    btc_close = daily_bars(btc_h).c
    data, split = {}, None
    for sym in COINS:
        h = hourly(sym)
        d = daily_bars(h)
        fh = funding_by_hour(sym)
        cond, ok = conditions(d, btc_close, fh.groupby(fh.index.floor("D")).sum())
        net, worst = outcomes(d, h, fh)
        good = ok & np.isfinite(net)
        data[sym] = dict(d=d, cond=cond, net=net, worst=worst, good=good)
        if split is None:
            split = d.index[good][int(good.sum() * 0.6)]
    R = pd.read_csv(ROOT / "logs" / "day_long_combos.csv")
    lines = [f"backtest/day_long.py --followup, {pd.Timestamp.now():%Y-%m-%d %H:%M} (descriptive, after the main run)", ""]
    lines.append("a) '20d_high & btc>ema50' on the holdout: mean, without its best 3 days, median, share in 2024-11:")
    for sym, D in data.items():
        m = D["good"] & (D["d"].index >= split) & D["cond"]["20d_high"] & D["cond"]["btc>ema50"]
        x = pd.Series(D["net"][m], index=D["d"].index[m])
        if len(x) < 5:
            continue
        top3 = x.sort_values().iloc[:-3]
        nov = x[(x.index >= "2024-11-01") & (x.index < "2024-12-01")].sum() / max(x.sum(), 1e-12) if x.sum() > 0 else np.nan
        lines.append(f"  {sym:9} n {len(x):>3}: mean {x.mean() * 100:+.2f}%/day, without best 3 {top3.mean() * 100:+.2f}%, "
                     f"median {x.median() * 100:+.2f}%, up days {np.mean(x > 0):.0%}, share of the gain from 2024-11 "
                     f"{nov:.0%}" if np.isfinite(nov) else f"  {sym:9} n {len(x):>3}: mean {x.mean() * 100:+.2f}%/day "
                     f"(net loss), median {x.median() * 100:+.2f}%")
    lines.append("\nb) the 10 filters with the best TUNE t-statistic (30+ days each half), judged on the holdout:")
    R["t_t"] = R.m_t / R.m_t.abs().clip(lower=1e-9)          # placeholder, replaced below
    tt = []
    for r in R[(R.n_t >= 30) & (R.n_h >= 30)].itertuples():
        D = data[r.coin]
        m = D["good"] & (D["d"].index < split)
        for c in r.combo.split(" & "):
            m &= D["cond"][c]
        tt.append((r.Index, stats(D["net"][m])[2]))
    R.loc[[i for i, _ in tt], "t_t"] = [t for _, t in tt]
    pick = R.loc[[i for i, _ in tt]].sort_values("t_t", ascending=False).head(10)
    for r in pick.itertuples():
        lines.append(f"  {r.coin:9} {r.combo:40} tune {r.m_t * 100:+.2f}%/day (t {r.t_t:+.1f}, n {r.n_t}) -> holdout "
                     f"{r.m_h * 100:+.2f}%/day (n {r.n_h}), every day {r.b_h * 100:+.2f}")
    lines.append(f"  average holdout {pick.m_h.mean() * 100:+.3f}%/day vs long-every-day {pick.b_h.mean() * 100:+.3f}%")
    lines.append("\nc) 10,000 PKR on '20d_high & btc>ema50', holdout:")
    for sym, D in data.items():
        m = D["good"] & (D["d"].index >= split) & D["cond"]["20d_high"] & D["cond"]["btc>ema50"]
        net, worst = D["net"][m], D["worst"][m]
        cells = []
        for lev in LEVS:
            f_, a_ = play(net, worst, lev, "fixed"), play(net, worst, lev, "allin")
            cells.append(f"{lev}x: {f_['avg']:+.0f}/trade, {f_['liqs']} liq, all-in {a_['end']:,.0f}"
                         + (f" (<1k after {a_['under']})" if a_['under'] else ""))
        lines.append(f"  {sym:9} {m.sum():>3} days | " + " | ".join(cells))
    txt = "\n".join(lines)
    print(txt)
    (ROOT / "logs" / "day_long_followup.txt").write_text(txt + "\n")


if __name__ == "__main__":
    followup() if "--followup" in sys.argv else main()

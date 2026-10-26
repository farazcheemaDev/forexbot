"""IBD DISTRIBUTION DAYS AS AN EXPOSURE RULE: THE tradermonty ibd-distribution-day-monitor SKILL, EXACTLY (2026-10-27)

THE USER (2026-10-26/27): "check all of them [the Claude trading skills] and see if we can take something ... do not assume
that because we tested something already it is certified wrong". This skill is the one from tradermonty/claude-trading-skills
that turns an old William O'Neil heuristic into a rule with numbers. Never tested here. Implemented as its code reads:
  DISTRIBUTION DAY  close at least 0.2% under the previous close AND volume above the previous day's
  ACTIVE            until more than 25 sessions have passed, or the index's HIGH since has gained 5% from that day's close
  COUNTS            d5 / d15 / d25 = active distribution days aged <= 5 / 15 / 25 sessions (age 0 = the day itself)
  RISK              SEVERE: d25 >= 6 or d15 >= 4 or (close under BOTH its 21-day EMA and 50-day average and d25 >= 5)
                    HIGH: d25 >= 5 or d15 >= 3 or d5 >= 2;  CAUTION: d25 >= 3;  NORMAL otherwise
  EXPOSURE (QQQ map)   NORMAL 100%, CAUTION 100%, HIGH 75%, SEVERE 50%   (TQQQ map: 100 / 75 / 50 / 25, run as a variant)
The state read at a close sets the exposure for the NEXT day (no look-ahead). Cost 3bp a unit of exposure moved (ETF) / 6bp (BTC).
ASSETS  QQQ (1999-03 .. 2026-09, adjusted daily with volume, strategy_analysis/data/tradfi) and SPY; BTC (Binance perp 1h
        cached since 2020-02, rolled to UTC days) as the crypto analogue. tune = first 60% of days (QQQ: before 2015-08-01).
CONTROLS  (a) buy and hold; (b) the BET-SMALLER LINE: a constant exposure equal to the rule's average exposure; (c) 500
        circular shifts of the exposure series in time (same average and same clustering, no link to the market).
        A risk rule is worth having only if it beats (b) and (c), not just buy-and-hold.

REGISTERED BEFORE THE FIRST RUN (2026-10-27)
  Y1  Information: the next-20-day QQQ return in HIGH + SEVERE states is NOT lower than in NORMAL states by 1 point or more
      on BOTH halves (the old heuristic carries little return information), but the next-20-day realised volatility IS higher
      in HIGH + SEVERE on both halves (volatility clusters).
  Y2  On QQQ the QQQ-map rule has a smaller maximum drawdown than buy and hold on both halves, and a Sharpe ratio NOT higher on
      at least one half.
  Y3  Against (b) and (c): on at least one half, at least 10% of the shifted series do as well as the rule on drawdown AND
      Sharpe combined (i.e. the rule is not distinguishable from timing luck).
  Y4  BTC: the same as Y2.
PASS    on both halves of QQQ and of BTC the rule has Sharpe above buy-and-hold AND above its matched constant exposure, and
        fewer than 10% of shifted series do as well on Sharpe. LEAD: drawdown lower than the matched line on both halves of
        QQQ and Sharpe not lower than the matched line. Otherwise NO RULE.

    python -m backtest.dist_days
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "strategy_analysis" / "data"
LOG = ROOT / "logs" / "dist_days.txt"
MAPS = {"QQQ-map": {"NORMAL": 1.0, "CAUTION": 1.0, "HIGH": 0.75, "SEVERE": 0.5},
        "TQQQ-map": {"NORMAL": 1.0, "CAUTION": 0.75, "HIGH": 0.5, "SEVERE": 0.25}}
LEVELS = ("NORMAL", "CAUTION", "HIGH", "SEVERE")


def load_qqq(sym):
    d = pd.read_csv(DATA / "tradfi" / f"{sym}_1d.csv", parse_dates=["time"]).set_index("time")
    return d[["high", "close", "volume"]].dropna()


def load_btc():
    rows = json.load(open(DATA / "BTCUSDT_1h_2400d.json"))
    d = pd.DataFrame(rows)
    d["t"] = pd.to_datetime(d.t, unit="ms", utc=True).dt.tz_localize(None)
    g = d.groupby(d.t.dt.normalize())
    out = pd.DataFrame(dict(high=g.h.max(), close=g.c.last(), volume=g.v.sum()))
    return out.iloc[1:-1]                                           # drop the partial first and last UTC days


def states(df):
    c, h, v = df.close.to_numpy(float), df.high.to_numpy(float), df.volume.to_numpy(float)
    n = len(c)
    dd = np.zeros(n, bool)
    dd[1:] = (c[1:] <= c[:-1] * (1 - 0.002)) & (v[1:] > v[:-1])
    ema21 = df.close.ewm(span=21, adjust=False).mean().to_numpy()
    sma50 = df.close.rolling(50).mean().to_numpy()
    d5, d15, d25 = np.zeros(n, int), np.zeros(n, int), np.zeros(n, int)
    days = np.flatnonzero(dd)
    for i in range(n):
        for j in days[(days <= i) & (days >= i - 25)]:
            age = i - j
            if age > 0 and h[j + 1:i + 1].max() >= c[j] * 1.05:      # the high since has gained 5% from the DD close
                continue
            d25[i] += 1
            d15[i] += age <= 15
            d5[i] += age <= 5
    below = (c < ema21) & (c < sma50)
    st = np.full(n, "NORMAL", object)
    for i in range(n):
        if d25[i] >= 6 or d15[i] >= 4 or (below[i] and d25[i] >= 5):
            st[i] = "SEVERE"
        elif d25[i] >= 5 or d15[i] >= 3 or d5[i] >= 2:
            st[i] = "HIGH"
        elif d25[i] >= 3:
            st[i] = "CAUTION"
    return pd.Series(st, index=df.index)


def perf(r: pd.Series):
    r = r.dropna()
    if len(r) < 30:
        return dict(sharpe=np.nan, dd=np.nan, cagr=np.nan)
    eq = (1 + r).cumprod()
    yrs = (r.index[-1] - r.index[0]).days / 365.25
    return dict(sharpe=r.mean() / r.std() * np.sqrt(365 if yrs and len(r) / yrs > 300 else 252),
                dd=float((1 - eq / eq.cummax()).max()), cagr=float(eq.iloc[-1] ** (1 / yrs) - 1))


def apply(ret, expo, cost):
    e = expo.shift(1).reindex(ret.index).fillna(1.0)               # decided at the previous close
    return e * ret - cost * e.diff().abs().fillna(0)


def one_asset(name, df, cut, cost, L, draws=500, seed=3):
    ret = df.close.pct_change()
    st = states(df)
    halves = {"tune": ret.index < cut, "holdout": ret.index >= cut}
    out = {}
    L.append(f"== {name}: {df.index[0]:%Y-%m-%d} .. {df.index[-1]:%Y-%m-%d}, {len(df)} days; days in CAUTION/HIGH/SEVERE: "
             + " / ".join(f"{(st == k).mean() * 100:.0f}%" for k in LEVELS[1:]))
    # Y1 information
    fwd20 = df.close.shift(-20) / df.close - 1
    vol20 = ret[::-1].rolling(20).std()[::-1].shift(-1)             # realised vol of the next 20 days
    hi = st.isin(["HIGH", "SEVERE"])
    L.append(f"  Y1  next-20-day return by state (mean %; NORMAL | CAUTION | HIGH+SEVERE) and next-20-day daily vol (NORMAL | HIGH+SEVERE)")
    info = {}
    for hn, m in halves.items():
        a, b, c_ = fwd20[m & (st == "NORMAL")], fwd20[m & (st == "CAUTION")], fwd20[m & hi]
        va, vc = vol20[m & (st == "NORMAL")], vol20[m & hi]
        info[hn] = (a.mean(), c_.mean(), va.mean(), vc.mean())
        L.append(f"      {hn:8} {a.mean() * 100:+.2f}% | {b.mean() * 100:+.2f}% | {c_.mean() * 100:+.2f}% (n {int((m & hi).sum())}) | "
                 f"vol {va.mean() * 100:.2f}% | {vc.mean() * 100:.2f}%")
    y1 = not all(info[h][1] <= info[h][0] - 0.01 for h in halves) and all(info[h][3] > info[h][2] for h in halves)
    rng = np.random.default_rng(seed)
    res = {}
    for mapname, mp in MAPS.items():
        expo = st.map(mp).astype(float)
        rule = apply(ret, expo, cost)
        L.append(f"  {mapname}: average exposure {expo.mean() * 100:.0f}%")
        L.append(f"      {'':9} {'Sharpe':>7} {'maxDD':>6} {'CAGR':>7} | hold {'Sharpe':>7} {'maxDD':>6} {'CAGR':>7} | "
                 f"matched const {'Sharpe':>7} {'maxDD':>6} | shifted-timing share as good (Sharpe / DD / both)")
        for hn, m in halves.items():
            r, b = perf(rule[m]), perf(ret[m])
            const = perf(ret[m] * expo[m].mean())
            sh_s, sh_d, sh_b = [], [], []
            for _ in range(draws):
                k = int(rng.integers(40, len(expo) - 40))
                ex2 = pd.Series(np.roll(expo.to_numpy(), k), index=expo.index)
                p2 = perf(apply(ret, ex2, cost)[m])
                sh_s.append(p2["sharpe"] >= r["sharpe"])
                sh_d.append(p2["dd"] <= r["dd"])
                sh_b.append(p2["sharpe"] >= r["sharpe"] and p2["dd"] <= r["dd"])
            res[(mapname, hn)] = (r, b, const, float(np.mean(sh_s)), float(np.mean(sh_d)), float(np.mean(sh_b)))
            L.append(f"      {hn:9} {r['sharpe']:>7.2f} {r['dd'] * 100:>5.0f}% {r['cagr'] * 100:>+6.1f}% | "
                     f"      {b['sharpe']:>7.2f} {b['dd'] * 100:>5.0f}% {b['cagr'] * 100:>+6.1f}% | "
                     f"              {const['sharpe']:>7.2f} {const['dd'] * 100:>5.0f}% | {np.mean(sh_s) * 100:.0f}% / {np.mean(sh_d) * 100:.0f}% / {np.mean(sh_b) * 100:.0f}%")
    L.append("")
    out.update(y1=y1, res=res)
    return out


def main():
    L = [f"backtest/dist_days.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; IBD distribution days, rule exactly as the skill codes it", ""]
    q = load_qqq("QQQ")
    rq = one_asset("QQQ", q, pd.Timestamp("2015-08-01"), 3e-4, L)
    s = load_qqq("SPY")
    one_asset("SPY", s, pd.Timestamp("2015-08-01"), 3e-4, L)
    b = load_btc()
    rb = one_asset("BTC (UTC days, perp)", b, b.index[int(len(b) * 0.6)], 6e-4, L)
    # registered predictions
    y2 = all(rq["res"][("QQQ-map", h)][0]["dd"] < rq["res"][("QQQ-map", h)][1]["dd"] for h in ("tune", "holdout")) and \
        any(rq["res"][("QQQ-map", h)][0]["sharpe"] <= rq["res"][("QQQ-map", h)][1]["sharpe"] for h in ("tune", "holdout"))
    y3 = any(rq["res"][("QQQ-map", h)][5] >= 0.10 for h in ("tune", "holdout"))
    y4 = all(rb["res"][("QQQ-map", h)][0]["dd"] < rb["res"][("QQQ-map", h)][1]["dd"] for h in ("tune", "holdout")) and \
        any(rb["res"][("QQQ-map", h)][0]["sharpe"] <= rb["res"][("QQQ-map", h)][1]["sharpe"] for h in ("tune", "holdout"))

    def beats(res, mp):
        return all(res[(mp, h)][0]["sharpe"] > res[(mp, h)][1]["sharpe"] and res[(mp, h)][0]["sharpe"] > res[(mp, h)][2]["sharpe"]
                   and res[(mp, h)][3] < 0.10 for h in ("tune", "holdout"))

    def lead(res, mp):
        return all(res[(mp, h)][0]["dd"] < res[(mp, h)][2]["dd"] and res[(mp, h)][0]["sharpe"] >= res[(mp, h)][2]["sharpe"]
                   for h in ("tune", "holdout"))

    passed = beats(rq["res"], "QQQ-map") and beats(rb["res"], "QQQ-map")
    ld = lead(rq["res"], "QQQ-map") and not passed
    L += ["REGISTERED PREDICTIONS",
          f"  Y1 little return information, but higher volatility after HIGH/SEVERE on both halves (QQQ) -> {'RIGHT' if rq['y1'] else 'WRONG'}",
          f"  Y2 QQQ: smaller drawdown both halves, Sharpe not higher on at least one -> {'RIGHT' if y2 else 'WRONG'}",
          f"  Y3 QQQ: timing luck matches the rule on at least one half (share >= 10%) -> {'RIGHT' if y3 else 'WRONG'}",
          f"  Y4 BTC: as Y2 -> {'RIGHT' if y4 else 'WRONG'}",
          f"  VERDICT: {'PASS' if passed else ('LEAD' if ld else 'NO RULE')}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

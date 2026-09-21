"""BET MORE IN BULL MARKETS - a regime-conditional risk multiplier on the deployed blend.

THE QUESTION
    The blend already cuts risk to x0.25 while BTC is below its average. Nobody has tested
    the other half: raising risk ABOVE 1x while BTC is above it. The blend's returns are
    bimodal by regime, so the growth-optimal bet in a bull should be larger than the
    whole-sample optimum (ruin.py: 0.30% captures 92% of growth at the unconditional
    optimum of 0.50%).

    The control that decides it: raising risk UNIFORMLY. "Bet more" always raises return
    and drawdown together (escalate.py: flat x1.5 -> +10.79%/mo at 90% DD). A bull-only
    boost is only worth anything if it buys MORE return per point of drawdown than that.

A DISCREPANCY FIXED HERE
    The live bots gate on BTC's 1000h average (blend_paper.py, longtrend_bot.py: REGIME_MA
    = 1000 since 2026-09-14). backtest/blend.btc_bear() - used by escalate, bear_date,
    bear_side, tradfi and the "+9.07%/mo holdout" figure - still uses rolling(200) on 1h
    bars, i.e. 200h. So this file builds both gates, uses 1000h (what is deployed) as the
    primary, and shows 200h for continuity.

THE CONSTRAINT A BACKTEST WILL NOT SHOW BY ITSELF
    Bigger risk means bigger positions. Notional per unit = risk / stop distance, and the
    pyramid stacks up to 5 units per position across 12 slots. Exchanges cap leverage and
    liquidate beyond it; lev_test.py found liquidation is free up to 10x and destructive
    above. So every row reports the account's GROSS LEVERAGE through time (sum of open
    units' notional / equity, from each position's actual stop distance and the bar each
    unit was added). A row whose 99th-percentile gross leverage exceeds 10x is not
    tradable as simulated, however good its return.

    Compounded by CLOSE date (mistake #6). %/mo figures carry the 3x hindsight haircut on
    CAGR, as everywhere else. Tune/holdout split as bear_date.py.

    python -m backtest.bull_boost
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.pyramid import run_pyramid  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from backtest.timeframes import resample  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402

RULES, SLOTS, U = ["1h", "4h", "12h"], 12, blend.MAX_UNITS
LEV_CAP = 10.0


def pyramid_detail(df):
    """run_pyramid for the deployed long sleeve, also returning each position's stop
    distance as a fraction of entry and the time each unit was added. Guarded below."""
    sig = signals(df, "long", "all").to_numpy()
    o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    t = df["time"].to_numpy()
    a = atr_ind(df, 14).to_numpy(float)
    fee = blend.FEE_BP / 1e4
    out, pos = [], None

    def close(px, i):
        R = sum((px - e) / pos["risk"] - fee * e / pos["risk"] for e in pos["entries"])
        out.append(dict(t0=t[pos["bar"]], t1=t[i], R=R, sf=pos["risk"] / pos["entries"][0],
                        adds=list(pos["add_t"])))

    for i in range(1, len(df)):
        if pos is None and sig[i] == 1 and np.isfinite(a[i - 1]) and a[i - 1] > 0:
            r = blend.SL_MULT * a[i - 1]
            pos = dict(risk=r, stop=o[i] - r, best=o[i], bar=i, entries=[o[i]], nxt=1,
                       add_t=[t[i]])
        if pos is None:
            continue
        r = pos["risk"]
        if lo[i] <= pos["stop"]:
            close(pos["stop"], i); pos = None; continue
        if len(pos["entries"]) < U and (h[i] - pos["entries"][0]) / r >= pos["nxt"] * blend.ADD_EVERY:
            pos["entries"].append(pos["entries"][0] + pos["nxt"] * blend.ADD_EVERY * r)
            pos["add_t"].append(t[i]); pos["nxt"] += 1
        pos["best"] = max(pos["best"], h[i])
        cand = pos["best"] - blend.LONG_TRAIL * a[i - 1]
        if (pos["best"] - pos["entries"][0]) / r >= blend.BE_AT:
            cand = max(cand, pos["entries"][0])
        pos["stop"] = max(pos["stop"], cand)
    if pos is not None:
        close(c[-1], len(df) - 1)
    return out


def build():
    rows = []
    for rule in RULES:
        _tr, stops = sleeve_sided(rule)
        for coin in blend.BOOK:
            d = blend.load(coin)
            if d is None:
                continue
            df = resample(d, rule)
            if len(df) < 300:
                continue
            det = pyramid_detail(df)
            R0, *_ = run_pyramid(df, signals(df, "long", "all"), sl_mult=blend.SL_MULT,
                                 trail=blend.LONG_TRAIL, max_units=U,
                                 add_every=blend.ADD_EVERY, fee_bp=blend.FEE_BP,
                                 breakeven_at=blend.BE_AT)
            assert len(det) == len(R0) and np.allclose([x["R"] for x in det], R0), (rule, coin)
            rows += [dict(x, side="long") for x in det]
        for a_, b_, r, _rule, c_, side in _tr:
            if side == "short":
                rows.append(dict(t0=a_, t1=b_, R=r, sf=stops.get(c_, 0.05), adds=[a_],
                                 side="short"))
    rows.sort(key=lambda x: x["t0"])
    print(f"guard: long sleeve reproduces run_pyramid exactly; {len(rows):,} positions")
    return rows


def regimes():
    d = blend.load("BTCUSDT")
    s = pd.Series(d["close"].to_numpy(), index=pd.DatetimeIndex(d["time"]))
    return {ma: (s < s.rolling(ma).mean()).shift(1).fillna(False).astype(bool)
            for ma in (1000, 200)}


def evaluate(rows, bear, bull_long=1.0, bull_short=1.0, bear_mult=0.25, uniform=1.0,
             t_from=None, t_to=None, grid=None):
    f0 = blend.RISK / 100.0 * uniform
    opens, pnl, expo = [], [], []
    for r in rows:
        if t_from is not None and r["t0"] < t_from: continue
        if t_to is not None and r["t0"] >= t_to: continue
        opens = [u for u in opens if u > r["t0"]]
        if len(opens) >= SLOTS: continue
        opens.append(r["t1"])
        try: ib = bool(bear.asof(r["t0"]))
        except Exception: ib = False
        m = bear_mult if ib else (bull_long if r["side"] == "long" else bull_short)
        f = f0 * m
        pnl.append((pd.Timestamp(r["t1"]), r["R"] * f))
        if grid is not None:
            lev = f / max(r["sf"], 1e-4)              # notional per unit / equity
            for ta in r["adds"]:
                expo.append((ta, r["t1"], lev))
    s = pd.Series([x[1] for x in pnl], index=pd.DatetimeIndex([x[0] for x in pnl]))
    daily = s.resample("D").sum()
    cur = np.cumprod(np.maximum(1 + daily.values, 0))
    pk = np.maximum.accumulate(np.maximum(cur, 1e-12))
    dd = float((1 - cur / pk).max() * 100)
    yrs = max((daily.index[-1] - daily.index[0]).days / 365.25, 0.1)
    cagr = (max(cur[-1], 1e-12) ** (1 / yrs) - 1) * 100
    hc = cagr / blend.HINDSIGHT
    out = dict(hpm=((1 + hc / 100) ** (1 / 12) - 1) * 100 if hc > -100 else -100.0,
               raw=((max(cur[-1], 1e-12)) ** (1 / (yrs * 12)) - 1) * 100, dd=dd,
               worst_mo=float(daily.resample("ME").sum().min() * 100), daily=daily)
    if grid is not None and expo:
        g = np.zeros(len(grid))
        gi = grid.as_unit("ns").asi8          # the bar times are datetime64[ms]
        for ta, tb, lev in expo:
            a = np.searchsorted(gi, pd.Timestamp(ta).as_unit("ns").value)
            b = np.searchsorted(gi, pd.Timestamp(tb).as_unit("ns").value)
            g[a:b] += lev
        out["lev99"], out["levmax"] = float(np.percentile(g, 99)), float(g.max())
    return out


def by_year(daily):
    return {y: float(np.prod(1 + daily[daily.index.year == y].values) - 1) * 100
            for y in sorted(set(daily.index.year))}


def bootstrap_dd(daily, reps=4000, block=30, horizon=365 * 3):
    rng = np.random.default_rng(5)
    v = daily.values
    nb = int(np.ceil(horizon / block))
    st = rng.integers(0, len(v) - block, size=(reps, nb))
    idx = (st[:, :, None] + np.arange(block)[None, None, :]).reshape(reps, -1)[:, :horizon]
    cur = np.cumprod(np.maximum(1 + v[idx], 0), axis=1)
    dd = (1 - cur / np.maximum.accumulate(cur, axis=1)).max(1)
    return dict(p80=float((dd > 0.8).mean() * 100), p90=float((dd > 0.9).mean() * 100),
                med_x=float(np.median(cur[:, -1])))


def main():
    rows = build()
    regs = regimes()
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    grid = pd.date_range(pd.Timestamp(rows[0]["t0"]).floor("h"),
                         pd.Timestamp(rows[-1]["t1"]).ceil("h"), freq="h")
    bear = regs[1000]
    print(f"regime: share of hours in 'bull' (BTC above its 1000h average): "
          f"{(~bear).mean()*100:.0f}%   tune < {cut:%Y-%m-%d} <= holdout\n")

    def show(lab, **kw):
        a = evaluate(rows, bear, t_to=cut, **kw)
        b = evaluate(rows, bear, t_from=cut, **kw)
        full = evaluate(rows, bear, grid=grid, **kw)
        flag = "  OVER 10x" if full.get("lev99", 0) > LEV_CAP else ""
        print(f"  {lab:<34}| {a['hpm']:>+7.2f}%{a['dd']:>5.0f}% | {b['hpm']:>+7.2f}%"
              f"{b['dd']:>5.0f}%{b['worst_mo']:>+8.1f}% | {full['lev99']:>5.1f}x"
              f"{full['levmax']:>6.1f}x{flag}")
        return full

    hdr = (f"  {'':<34}| {'TUNE/mo':>8}{'DD':>6} | {'HOLD/mo':>8}{'DD':>6}{'worst mo':>9} |"
           f"{'lev p99':>7}{'max':>7}")
    print("1000h GATE (deployed). Bear: x0.25 both sides. Bull multiplier on LONGS:")
    print(hdr)
    res = {}
    for m in (1.0, 1.25, 1.5, 2.0, 2.5, 3.0):
        res[("bull", m)] = show(f"bull longs x{m:g}" + ("  (DEPLOYED)" if m == 1 else ""),
                                bull_long=m)
    print("\n  CONTROL - the same extra risk everywhere (uniform multiplier, gate kept):")
    for m in (1.25, 1.5, 2.0):
        res[("uni", m)] = show(f"uniform x{m:g}", uniform=m)
    print("\n  VARIANTS - flat in bears, and boosting bull shorts too:")
    show("bull x2, bear x0 (flat in bears)", bull_long=2.0, bear_mult=0.0)
    show("bull x2 longs AND shorts", bull_long=2.0, bull_short=2.0)

    print("\n200h GATE (what backtest/blend.py has used), same grid, for continuity:")
    print(hdr)
    bear200 = regs[200]
    for m in (1.0, 1.5, 2.0):
        a = evaluate(rows, bear200, t_to=cut, bull_long=m)
        b = evaluate(rows, bear200, t_from=cut, bull_long=m)
        print(f"  {'bull longs x' + format(m, 'g'):<34}| {a['hpm']:>+7.2f}%{a['dd']:>5.0f}% | "
              f"{b['hpm']:>+7.2f}%{b['dd']:>5.0f}%{b['worst_mo']:>+8.1f}% |")

    print("\nRISK OF A DEEP DRAWDOWN over 3 years (block bootstrap of daily P&L, 30-day blocks):")
    for key, lab in ((("bull", 1.0), "deployed"), (("bull", 1.5), "bull x1.5"),
                     (("bull", 2.0), "bull x2"), (("uni", 1.5), "uniform x1.5")):
        bs = bootstrap_dd(res[key]["daily"])
        print(f"  {lab:<14} P(drawdown > 80%) {bs['p80']:5.1f}%   P(> 90%) {bs['p90']:5.1f}%"
              f"   median 3-year multiple x{bs['med_x']:.1f} (raw, no haircut)")

    print("\nBY YEAR, compounded, raw (no haircut):")
    keys = [(("bull", 1.0), "deployed"), (("bull", 1.5), "bull x1.5"), (("bull", 2.0), "bull x2")]
    yrs = by_year(res[keys[0][0]]["daily"]).keys()
    print("  " + f"{'':<10}" + "".join(f"{y:>9}" for y in yrs))
    for key, lab in keys:
        yy = by_year(res[key]["daily"])
        print("  " + f"{lab:<10}" + "".join(f"{yy[y]:>+8.0f}%" for y in yrs))


if __name__ == "__main__":
    main()

"""ECONOMIC DATA SURPRISES AND FOREX, 2007-2026: the jump, and whether anything is left to trade after it (2026-10-12)

The user's first request in the /goal (2026-10-12): "run these economic data". ForexFactory's calendar (2007-01 ..
2026-09, backtest/fx_macro_data.py --ff) gives every release's ACTUAL and the market's FORECAST, and FF's own call on
whether the number was better or worse for the currency (abw: 1 better, 2 worse - computed from actual vs forecast, so
known the moment the number prints). Prices: the Fed's H.10 noon (New York) rates, daily.

EVENTS   high-impact releases with a forecast, for USD EUR GBP JPY AUD NZD CAD CHF. Each release's surprise is
         (actual - forecast) divided by the sd of that indicator's PAST surprises (>= 8 earlier ones; causal), capped at
         3, signed by abw. Releases of one currency at the same minute are summed into one SCORE (e.g. payrolls +
         unemployment + earnings at 08:30 ET).
WINDOWS  REACTION  from the last noon fix before the release to the first noon fix after it (includes the jump: it
                   shows that data DRIVES forex, but it cannot be traded - the number is not known before it prints)
         DRIFT k   from that first noon after the release, k = 1 / 3 / 5 business days on - TRADABLE: entered 3.5 h after an
                   08:30 ET release at the earliest, up to ~22 h after an afternoon one
         a USD release is read on the DOLLAR (minus the average of the 7 currencies); the others on their own currency
COSTS    Exness spread of the traded pair(s) + today's swap for the side held, each night (fx_drivers.COST)
PASS     DRIFT net > 0 with t >= 2 on both halves (60/40 by date), events with |score| >= 1.

REGISTERED BEFORE THE RUN (2026-10-12)
    E1  The REACTION has the surprise's sign in >= 60% of releases with |score| >= 1: data does drive forex on the day.
    E2  The DRIFT after the first noon is within 2 se of zero at 1, 3 and 5 days, for all releases and for USD alone:
        the information is priced within hours.
    E3  No drift rule passes after Exness costs.
    E4  For big USD surprises (|score| >= 2) the 1-day drift has the reaction's sign but is under 20% of its size.
    E5  (added before its run, after E1-E4 were seen) MINUTE RESOLUTION, 2026 only (Exness 1m bars from ticks,
        backtest/mt5_1m.py; the dollar = the average of -EURUSD, -GBPUSD, +USDJPY): for USD releases with |score| >= 1 the
        dollar's move from 1 minute before to 5 minutes after has the surprise's sign in >= 70%; the drift from +5 to
        +60 minutes, net of the spread, is within 2 se of zero.

RESULT (2026-10-12 01:20 UTC, logs/fx_surprises.txt; 6,810 currency-release groups 2007-08 .. 2026-09, holdout 2016-07)
    - DATA DOES MOVE FOREX ON THE DAY: after a surprise of |score| >= 1 the currency moves the surprise's way 59.9% of the
      time, +15.0bp (|score| >= 2: 62.3%, +17.4bp; non-USD releases 61.9%; CAD and AUD jobs 62-71%, core CPI 63%). E1
      WRONG by 0.1 point on noon-to-noon windows, which carry a day's other news; at MINUTE resolution (2026, Exness)
      the dollar jumps the surprise's way in 16 of 23 US releases, +6.1bp in 5 minutes (E5: 69.6% against a 70% line -
      WRONG by a hair).
    - NOTHING IS LEFT AFTER THE JUMP (E2, E3 RIGHT): the drift from the first noon after a release is -0.9 / -1.0 /
      -2.9bp at 1 / 3 / 5 days for all surprises (t -0.6 / -0.4 / -0.9), USD +1.6 / 0.0 / -2.2bp; after Exness costs
      every cell is negative except the biggest surprises (+1.7 / +5.0 / +1.4bp), which are positive on the tune half
      only (holdout +0.2 / +0.8 / -1.2bp). No rule passes. At minute resolution the +5 -> +60 min drift is -0.22bp (t -0.1).
    - E4 RIGHT: big US surprises keep only 9% of their jump the next day (+1.6bp of +18.8bp).
    Reading: economic data is one of the things that moves forex - for about five minutes. By the time a retail order
    can act on the number, the market has priced it, and the next hour, day or week holds nothing worth the spread.

    python -m backtest.fx_surprises
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import fx_macro_data as md  # noqa: E402
from backtest.fx_drivers import COST  # noqa: E402

LOG = ROOT / "logs" / "fx_surprises.txt"
CCY = md.CCY
ALL = ["USD"] + CCY
TUNE = 0.60
MULT = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}


def num(x):
    if not isinstance(x, str) or not x.strip():
        return np.nan
    s = x.strip().replace(",", "").replace("<", "").replace(">", "")
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*([KMBT%]?)", s)
    if not m:
        return np.nan
    v = float(m.group(1))
    return v * MULT.get(m.group(2), 1.0)


def events():
    ff = md.load("ff_2007_2026.csv")
    ff = ff[(ff.impact == "high") & ff.currency.isin(ALL)].copy()
    ff["a"], ff["f"] = ff.actual.map(num), ff.forecast.map(num)
    ff = ff.dropna(subset=["a", "f"])
    ff = ff[ff.abw.isin([1, 2])].sort_values("utc", kind="stable")
    ff["s"] = ff.a - ff.f
    sd = ff.groupby(["currency", "name"]).s.transform(lambda x: x.abs().shift(1).expanding(8).mean() * 1.2533)
    ff["z"] = (ff.s.abs() / sd).clip(upper=3) * np.where(ff.abw == 1, 1, -1)
    ff = ff.dropna(subset=["z"])
    g = ff.groupby(["currency", "utc"]).agg(score=("z", "sum"), n=("z", "size"), names=("name", lambda x: "; ".join(x)))
    return g.reset_index()


def main():
    fx = md.load("fx_h10.csv")[CCY]
    fx = fx[fx.index >= "2006-06-01"].dropna(how="all").ffill(limit=3)
    days = fx.index
    E = events()
    et = E.utc.dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    E["after_noon"] = et.dt.hour >= 12
    E["day"] = et.dt.normalize()
    rows = []
    for r in E.itertuples():
        i_day = days.searchsorted(r.day)                       # first fix on/after the release day
        if i_day >= len(days):
            continue
        same = days[i_day] == r.day
        if r.after_noon or not same:
            i_post = i_day + (1 if same else 0)               # the first noon AFTER the release
        else:
            i_post = i_day
        i_pre = i_post - 1
        if i_pre < 0 or i_post + 5 >= len(days):
            continue
        p = fx.iloc
        if r.currency == "USD":
            series = lambda a, b: -(p[b] / p[a] - 1).mean()      # noqa: E731  the dollar vs the 7
            cost_ccy = CCY
        else:
            series = lambda a, b, c=r.currency: p[b][c] / p[a][c] - 1  # noqa: E731
            cost_ccy = [r.currency]
        rec = dict(ccy=r.currency, utc=r.utc, score=r.score, names=r.names, react=series(i_pre, i_post))
        for k in (1, 3, 5):
            rec[f"d{k}"] = series(i_post, i_post + k)
            nights = (days[i_post + k] - days[i_post]).days
            side = np.sign(r.score)
            # long the currency that surprised well (for USD: long USD = short each foreign currency)
            sw = []
            for c in cost_ccy:
                long_foreign = (side > 0) if r.currency != "USD" else (side < 0)
                sw.append(COST[c][1] if long_foreign else COST[c][2])
            rec[f"c{k}"] = np.mean([COST[c][0] for c in cost_ccy]) / 1e4 - np.mean(sw) * nights / 1e4
        rows.append(rec)
    D = pd.DataFrame(rows).sort_values("utc", kind="stable").reset_index(drop=True)
    cut = D.utc.iloc[int(len(D) * TUNE)]
    lines = [f"backtest/fx_surprises.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; ForexFactory high-impact releases with a "
             f"forecast {D.utc.min():%Y-%m} .. {D.utc.max():%Y-%m}: {len(D)} currency-release groups; H.10 noon fixes; "
             f"holdout from {cut:%Y-%m-%d}", ""]
    lines.append("REACTION (last noon before -> first noon after; NOT tradable) - share with the surprise's sign, and the "
                 "average move in the surprise's direction")
    res = {}
    for nm, m in (("all, |score| >= 1", D.score.abs() >= 1), ("USD, |score| >= 1", (D.ccy == "USD") & (D.score.abs() >= 1)),
                  ("others, |score| >= 1", (D.ccy != "USD") & (D.score.abs() >= 1)),
                  ("all, |score| >= 2", D.score.abs() >= 2), ("USD, |score| >= 2", (D.ccy == "USD") & (D.score.abs() >= 2))):
        g = D[m]
        s = np.sign(g.score)
        hit = (np.sign(g.react) == s).mean()
        mv = (s * g.react).mean()
        line = f"  {nm:22} n {len(g):5} | reaction right {hit * 100:4.1f}%, {mv * 1e4:+6.1f}bp"
        for k in (1, 3, 5):
            x = s * g[f"d{k}"] - g[f"c{k}"]
            gross = s * g[f"d{k}"]
            tu, ho = x[g.utc < cut], x[g.utc >= cut]
            tt = lambda y: y.mean() / (y.std(ddof=1) / np.sqrt(len(y))) if len(y) > 2 else np.nan  # noqa: E731
            res[(nm, k)] = dict(gross=gross.mean(), net=x.mean(), t=tt(x), tu=tu.mean(), t_tu=tt(tu), ho=ho.mean(),
                                t_ho=tt(ho), gt=tt(gross))
            line += f" | drift {k}d gross {gross.mean() * 1e4:+5.1f}bp (t {tt(gross):+.1f}), net {x.mean() * 1e4:+5.1f}"
        res[(nm, "react")] = (hit, mv)
        lines.append(line)
    lines.append("")
    lines.append("DRIFT, Exness net, by half (tune / holdout, bp a trade, t)")
    for (nm, k), v in res.items():
        if k == "react":
            continue
        lines.append(f"  {nm:22} {k}d: {v['tu'] * 1e4:+6.1f} ({v['t_tu']:+.1f}) / {v['ho'] * 1e4:+6.1f} ({v['t_ho']:+.1f})")
    passes = [(nm, k) for (nm, k), v in res.items() if k != "react" and v["tu"] > 0 and v["ho"] > 0 and v["t_tu"] >= 2
              and v["t_ho"] >= 2]
    lines.append(f"  PASS: {passes or 'none'}")
    lines.append("")
    big = D[D.score.abs() >= 2].copy()
    big["s"] = np.sign(big.score)
    lines.append("THE BIGGEST SURPRISES' INDICATORS (|score| >= 2, count; reaction right %)")
    exp = big.assign(first=big.names.str.split("; ").str[0]).groupby(["ccy", "first"]).apply(
        lambda g: pd.Series({"n": len(g), "right": (np.sign(g.react) == g.s).mean()}), include_groups=False)
    for (c, nm_), v in exp.sort_values("n", ascending=False).head(12).iterrows():
        lines.append(f"  {c} {nm_:40} {int(v.n):4}  reaction right {v.right * 100:4.0f}%")
    lines.append("")
    lines.append("REGISTERED PREDICTIONS")
    h1 = res[("all, |score| >= 1", "react")][0]
    lines.append(f"  E1 reaction right {h1 * 100:.1f}% -> {'RIGHT' if h1 >= 0.60 else 'WRONG'}")
    e2 = all(abs(res[(nm, k)]["gt"]) < 2 for nm in ("all, |score| >= 1", "USD, |score| >= 1") for k in (1, 3, 5))
    lines.append(f"  E2 drift gross within 2 se of zero (all / USD, 1-5 d): " + ", ".join(
        f"{nm.split(',')[0]} {k}d t {res[(nm, k)]['gt']:+.1f}" for nm in ("all, |score| >= 1", "USD, |score| >= 1") for k in (1, 3, 5))
        + f" -> {'RIGHT' if e2 else 'WRONG'}")
    lines.append(f"  E3 no drift rule passes: {passes or 'none'} -> {'RIGHT' if not passes else 'WRONG'}")
    rv, d1 = res[("USD, |score| >= 2", "react")][1], res[("USD, |score| >= 2", 1)]["gross"]
    lines.append(f"  E4 big USD: reaction {rv * 1e4:+.1f}bp, 1-day drift {d1 * 1e4:+.1f}bp ({d1 / rv * 100 if rv else np.nan:.0f}% of it) -> "
                 f"{'RIGHT' if rv > 0 and 0 <= d1 < 0.2 * rv else 'WRONG'}")
    lines += intraday_2026(E.rename(columns={"currency": "ccy"}))
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


def intraday_2026(E: pd.DataFrame) -> list:
    """E5: USD releases in 2026 at minute resolution on Exness's own prices."""
    from backtest import mt5_1m
    MIN = 60_000
    bars = {}
    for sym in ("EURUSDm", "GBPUSDm", "USDJPYm"):
        b = mt5_1m.load(sym).set_index("t")
        bars[sym] = b
    sign = {"EURUSDm": -1, "GBPUSDm": -1, "USDJPYm": 1}           # the dollar's side of each quote
    u = E[(E.ccy == "USD") & (E.score.abs() >= 1) & (E.utc >= "2026-01-01")] if "ccy" in E.columns else         E[(E.currency == "USD") & (E.score.abs() >= 1) & (E.utc >= "2026-01-01")]
    rows = []
    for r in u.itertuples():
        t0 = int(pd.Timestamp(r.utc).timestamp() * 1000) // MIN * MIN
        moves, cost = {"jump": [], "drift": []}, []
        ok = True
        for sym, b in bars.items():
            need = [t0 - MIN, t0 + 5 * MIN, t0 + 60 * MIN]
            if not all(t in b.index for t in need):
                ok = False
                break
            p_pre, p5, p60 = b.at[t0 - MIN, "o"], b.at[t0 + 5 * MIN, "o"], b.at[t0 + 60 * MIN, "o"]
            moves["jump"].append(sign[sym] * (p5 / p_pre - 1))
            moves["drift"].append(sign[sym] * (p60 / p5 - 1))
            cost.append((b.at[t0 + 5 * MIN, "sp_o"] + b.at[t0 + 60 * MIN, "sp_o"]) / 2 / p5)
        if ok:
            rows.append(dict(score=r.score, jump=np.mean(moves["jump"]), drift=np.mean(moves["drift"]), cost=np.mean(cost)))
    out = ["", "MINUTE RESOLUTION, 2026 (Exness 1m; USD releases, |score| >= 1; the dollar vs EUR, GBP, JPY)"]
    if len(rows) < 10:
        return out + [f"  only {len(rows)} releases with bars - not decidable"]
    D = pd.DataFrame(rows)
    s_ = np.sign(D.score)
    hit = (np.sign(D.jump) == s_).mean()
    dr = s_ * D.drift
    net = dr - D.cost
    t = lambda y: y.mean() / (y.std(ddof=1) / np.sqrt(len(y)))   # noqa: E731
    out.append(f"  {len(D)} releases | -1 -> +5 min: the surprise's sign {hit * 100:.0f}%, {(s_ * D.jump).mean() * 1e4:+.1f}bp | "
               f"+5 -> +60 min drift: gross {dr.mean() * 1e4:+.2f}bp (t {t(dr):+.1f}), net of spread {net.mean() * 1e4:+.2f}bp "
               f"(t {t(net):+.1f}); spread {D.cost.mean() * 1e4:.2f}bp")
    out.append(f"  E5 jump right {hit * 100:.0f}% (>= 70%?), drift within 2 se of zero ({t(dr):+.1f}) -> "
               f"{'RIGHT' if hit >= 0.70 and abs(t(dr)) < 2 else 'WRONG'}")
    return out


if __name__ == "__main__":
    main()

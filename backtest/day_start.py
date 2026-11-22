"""DOES THE WAY A DAY STARTS PREDICT THE REST OF THAT DAY? - same-day crypto trades, flat by midnight (2026-11-21)

THE USER (2026-11-21), after the Analyst desk's ideas (held up to a day or two) were run over in the crash week: "that's where not
opening your trades for so long works - there should be a specific time period like a day ... we can predict how it will perform in a
day if a day starts like this or that". The idea is intraday momentum (or reversal): read the first hours of the UTC day, trade the rest
of the day with them (or against them), flat by 24:00 UTC, never held overnight. Published for Bitcoin (the first half-hour's return
predicts the last half-hour's); tested here on NASDAQ (ndx_close_momo.py: dead; the 'noise area' rule is NASDAQ's one candidate) and as
opening-range breakouts with brackets on DOGE (doge_adapt.py: dead) - never as 'the day's start predicts the rest of the day' on the
desk's crypto markets.
DATA   hourly bars of BTC, ETH, SOL, XRP, BNB (strategy_analysis/data/analyst_replay/*_1h.json, Binance USD-M, 2022-01-01 ..
       2026-10-26). A day = 00:00-24:00 UTC; only days with all 24 hourly bars.
START  the return over the day's first k hours, k = 1, 4, 8 and 13 (13:00 UTC ~ the US session's open).
TRADE  at hour k, WITH the start (momentum) or AGAINST it (reversal), out at 24:00 UTC; 12bp round trip; funding charged as a flat
       1bp per 8-hourly settlement held through (08:00 / 16:00 UTC; conservative - the real rate is sometimes received).
DAYS   all days, and STRONG starts only: |start| in the top 20% of that coin's own earlier starts (expanding quantile, 60-day warm-up,
       from days before - nothing later).
CELLS  4 starts x 2 directions x 2 day sets = 16, each pooled over the 5 coins; a BET = one day (the coins move together: the day's
       mean over the coins that traded).
GATE   PASS = mean net per bet > 0 with t >= 2 on BOTH halves (split ts[int(len * 0.6)] over the days) and Holm p < 0.05 over the 16
       (p from the weaker half's t). Also printed, for the user's question: after a strong up / down start, how often the rest of the
       day went the same way, and by how much.
REGISTERED BEFORE THE FIRST NUMBER (2026-11-21; my prior that any cell passes: about 7%)
  P1  No cell passes after costs.
  P2  Before costs, momentum after a STRONG start is positive at k = 1 and k = 4 on both halves (the published direction), but under
      12bp a day on average.
  P3  After a strong start, the rest of the day goes the same way on 48-55% of coin-days (close to a coin flip).

RESULT (2026-11-21, logs/day_start.txt): NO PASS (best Holm p 1.00), 1,759 days 2022-01 .. 2026-10, split 2024-11-21. After a strong start
  the rest of the day goes the same way on 45.3% (first hour), 50.1% (4h), 50.9% (8h), 51.3% (13h) of coin-days, against a 49% base
  rate: a coin flip. The first hour leans to REVERSAL (strong: gross +29 / +35bp, net +15 / +21bp, t 0.6 / 0.8); after 8 hours a strong
  start leans to continuation (net +12 / +29bp, t 0.6 / 1.2); at the US open (13h) +2 / +2bp. Two of 16 cells are positive after costs
  on both halves - what chance gives - and none near t 2. Every all-days cell loses the 12bp. P1 right; P2 wrong (the first hour
  reverses, it does not continue); P3 wrong at the first hour (45%). Crypto has no real 'start of the day'; NASDAQ does, and its
  version (the 'noise area' rule, forex_bot.py, built, demo-only, not started) is the one that held up.

    python -m backtest.day_start
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import candle_scan as cs  # noqa: E402

LOG = ROOT / "logs" / "day_start.txt"
DATA = ROOT / "strategy_analysis" / "data" / "analyst_replay"
COINS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT")
KS = (1, 4, 8, 13)
FEE = 0.0012
FUND = 0.0001                                   # per 8-hourly settlement held through (flat, conservative)


def day_table(sym: str) -> pd.DataFrame:
    """One row per complete UTC day: the price at 00:00 (bar 0's open), after each k hours (bar k-1's close) and at 24:00."""
    b = pd.DataFrame(json.loads((DATA / f"{sym}_1h.json").read_text()), columns=["t", "o", "h", "l", "c"])
    b["ts"] = pd.to_datetime(b.t, unit="ms")
    b["day"] = b.ts.dt.floor("D")
    b["hr"] = b.ts.dt.hour
    full = b.groupby("day").hr.count()
    b = b[b.day.isin(full[full == 24].index)]
    o0 = b[b.hr == 0].set_index("day").o
    out = pd.DataFrame({"p0": o0})
    for k in KS:
        out[f"p{k}"] = b[b.hr == k - 1].set_index("day").c
    out["p24"] = b[b.hr == 23].set_index("day").c
    return out.dropna()


def trades(sym: str) -> pd.DataFrame:
    d = day_table(sym)
    rows = {}
    for k in KS:
        start = d[f"p{k}"] / d.p0 - 1
        rest = d.p24 / d[f"p{k}"] - 1
        q = start.abs().expanding(min_periods=60).quantile(0.8).shift(1)
        n_fund = int(k < 8) + int(k < 16)
        rows[k] = pd.DataFrame({"start": start, "rest": rest, "strong": start.abs() > q,
                                "cost": FEE + FUND * n_fund})
    return pd.concat(rows, names=["k", "day"]).reset_index().assign(sym=sym)


def t_of(x: np.ndarray) -> float:
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 and x.std(ddof=1) > 0 else float("nan")


def main():
    T = pd.concat([trades(s) for s in COINS], ignore_index=True)
    T = T[T.start != 0]
    days = np.sort(T.day.unique())
    cut = pd.Timestamp(days[int(len(days) * 0.6)])
    L = [f"backtest/day_start.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {', '.join(s[:-4] for s in COINS)} hourly bars "
         f"{pd.Timestamp(days[0]):%Y-%m-%d} .. {pd.Timestamp(days[-1]):%Y-%m-%d} ({len(days)} days); split {cut:%Y-%m-%d}; trade from hour k to "
         f"24:00 UTC, {FEE * 1e4:.0f}bp + {FUND * 1e4:.0f}bp per settlement; a bet = one day (mean over the coins)", ""]
    L.append(f"   {'start':<10}{'way':<10}{'days':<8}{'half':>5}{'bets':>6}{'gross bp':>10}{'net bp':>8}{'t':>6}{'same way':>10}")
    res, pv = {}, {}
    for k in KS:
        for way in ("momentum", "reversal"):
            for ds in ("all", "strong"):
                sub = T[(T.k == k) & (T.strong if ds == "strong" else True)].copy()
                sgn = np.sign(sub.start) * (1 if way == "momentum" else -1)
                sub["gross"] = sgn * sub.rest
                sub["net"] = sub.gross - sub.cost
                sub["same"] = (np.sign(sub.rest) == np.sign(sub.start)).astype(float)
                cell = (k, way, ds)
                res[cell] = {}
                for h, m in (("tune", sub.day < cut), ("hold", sub.day >= cut)):
                    by = sub[m].groupby("day")[["gross", "net", "same"]].mean()
                    res[cell][h] = dict(bets=len(by), gross=float(by.gross.mean()), net=float(by.net.mean()), t=t_of(by.net.to_numpy()),
                                        same=float(sub[m].same.mean()))
                    r = res[cell][h]
                    L.append(f"   {('first ' + str(k) + 'h'):<10}{way:<10}{ds:<8}{h:>5}{r['bets']:>6}{r['gross'] * 1e4:>+10.1f}"
                             f"{r['net'] * 1e4:>+8.1f}{r['t']:>+6.1f}{r['same']:>10.1%}")
                pv[cell] = cs.p_one_sided(np.nan_to_num(min(res[cell]["tune"]["t"], res[cell]["hold"]["t"]), nan=-10.0))
    cells = list(pv)
    hp = dict(zip(cells, cs.holm([pv[c] for c in cells])))
    passed = [c for c in cells if all(res[c][h]["net"] > 0 and res[c][h]["t"] >= 2 for h in ("tune", "hold")) and hp[c] < 0.05]
    L += ["", "   PASS: " + (", ".join(f"first {c[0]}h {c[1]} {c[2]}" for c in passed) or "none")
          + f"   (best Holm p {min(hp.values()):.2f})", ""]

    # the user's question in plain numbers: after a strong up / a strong down start, what did the rest of the day do?
    L.append("AFTER A STRONG START (top 20% of starts), ALL COINS, BOTH HALVES - what the rest of the day did")
    L.append(f"   {'start':<10}{'the start':<14}{'coin-days':>10}{'rest went the same way':>24}{'average rest of day':>21}"
             f"{'baseline: any day, rest up':>28}")
    for k in KS:
        sub = T[T.k == k]
        base_up = float((sub.rest > 0).mean())
        for nm, m in (("strong UP", sub.strong & (sub.start > 0)), ("strong DOWN", sub.strong & (sub.start < 0))):
            x = sub[m]
            same = float((np.sign(x.rest) == np.sign(x.start)).mean())
            L.append(f"   {('first ' + str(k) + 'h'):<10}{nm:<14}{len(x):>10}{same:>24.1%}{x.rest.mean() * 100:>+20.2f}%"
                     f"{base_up:>27.1%}")
    p2 = all(res[(k, "momentum", "strong")][h]["gross"] > 0 for k in (1, 4) for h in ("tune", "hold")) and \
        all(res[(k, "momentum", "strong")][h]["gross"] < FEE for k in (1, 4) for h in ("tune", "hold"))
    same_strong = [float((np.sign(T[(T.k == k) & T.strong].rest) == np.sign(T[(T.k == k) & T.strong].start)).mean()) for k in KS]
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    L += ["", "REGISTERED PREDICTIONS",
          f"  P1 no cell passes after costs -> {ok(not passed)}",
          f"  P2 strong-start momentum gross > 0 at k = 1 and 4 on both halves, under 12bp -> {ok(p2)} ("
          + ", ".join(f"k {k} {h} {res[(k, 'momentum', 'strong')][h]['gross'] * 1e4:+.1f}bp" for k in (1, 4) for h in ("tune", "hold")) + ")",
          f"  P3 after a strong start the rest goes the same way on 48-55% of coin-days -> "
          f"{ok(all(0.48 <= s <= 0.55 for s in same_strong))} (" + ", ".join(f"k {k} {s:.1%}" for k, s in zip(KS, same_strong)) + ")"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

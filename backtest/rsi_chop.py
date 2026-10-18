"""DOES RSI WORK IN CHOPPY MARKETS? (2026-10-18)

The user, during the sideways-gap search: "in choppy markets using RSI should work I guess". The repo's RSI record
(rsi_only.py, doc 02): the retail RSI trade (buy the cross under 30, small target, no stop) wins 76-95% of trades in
EVERY year and makes money in 2020 / 2021 / 2023, loses it in 2022 and 2025-26. Never asked: are the winning stretches
the CHOPPY ones? Two tests:

PART 1 - rsi_only's own 115,312 trades (logs/rsi_only_trades.csv: BTC ETH SOL DOGE XRP perps, 15m / 1h / 4h, RSI(14)
    L 30 / 25, five exits, 12bp + funding), each tagged at its entry with
        CHOP-R   the BTC regime reads chop (market_neutral.btc_regime - BTC vs its 50-day mean, that mean's slope +-2%)
        CHOP-E   BTC's 30-day efficiency ratio < 0.25 (the day before; chop_switch.py's meter)
    and the average net trade, win rate and a day-clustered t (trades averaged by entry day) inside / outside chop, on
    rsi_only's own halves (before / after 2024-04-07).
PART 2 - RSI(14) 30/70 and RSI(2) 10/90 reversals on the PIT top-40 daily book (chop_revert.py's harness: next-close
    fill, out when RSI crosses 50 / 10 days / 10% stop, 10 slots, 12bp + funding), gated NONE / MARKET / COIN / BOTH.
REGISTERED BEFORE THE RUN (2026-10-18)
    Q1 the classic long (L 30, tp2, no stop) averages more per trade INSIDE chop than outside, on both halves (by CHOP-R).
    Q2 no RSI config (side x L x exit x timeframe) averages > 0 per trade inside chop on BOTH halves with a day-clustered
       t >= 2 on each half.
    Q3 PART 2: no gate makes either RSI book positive on both halves.

RESULT (2026-10-18, logs/rsi_chop.txt) - RSI IS A RISING-MARKET TRADE, NOT A SIDEWAYS ONE. Q1 WRONG the other way:
the classic long (L 30, +2%, no stop) LOSES inside BTC-chop on every timeframe and both halves (-0.27..-2.27% a trade,
66-84% won) and earns outside it (+0.23..+1.04%). 2 of 120 config x meter cells are positive in chop on both halves,
none with t >= 2 (Q2 RIGHT). The daily RSI books: none positive on both halves (Q3 RIGHT; rsi2 BOTH -30% / +17%).

    python -m backtest.rsi_chop
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "rsi_chop.txt"
SPLIT = pd.Timestamp("2024-04-07")                  # rsi_only's own split
CUT = pd.Timestamp("2024-08-29")


def tstat_by_day(x: pd.DataFrame) -> tuple:
    d = x.groupby(x.t.dt.normalize()).net.mean()
    if len(d) < 10 or d.std() == 0:
        return x.net.mean(), np.nan, len(x)
    return x.net.mean(), d.mean() / d.std() * np.sqrt(len(d)), len(x)


def part1(reg: pd.Series, er: pd.Series, lines: list):
    T = pd.read_csv(ROOT / "logs" / "rsi_only_trades.csv", parse_dates=["t"])
    day = T.t.dt.normalize()
    T["chopR"] = reg.reindex(day.unique()).reindex(day).to_numpy() == "chop"
    T["chopE"] = (er.reindex(day.unique()).reindex(day).to_numpy() < 0.25)
    T["half"] = np.where(T.t < SPLIT, "tune", "holdout")
    lines += [f"PART 1 - rsi_only's {len(T):,} trades; chop by BTC regime (CHOP-R) on {T.chopR.mean():.0%} of trades, "
              f"by efficiency ratio (CHOP-E) on {T.chopE.mean():.0%}", "",
              "   the CLASSIC long (L 30, +2% target, no stop), per trade net, by market at entry (avg / win rate / n):"]
    cl = T[(T.side == "long") & (T.L == 30) & (T.exit == "tp2")]
    for tf in ("15m", "1h", "4h"):
        for half in ("tune", "holdout"):
            x = cl[(cl.tf == tf) & (cl.half == half)]
            parts = []
            for lab, m in (("chop", x.chopR), ("not chop", ~x.chopR)):
                y = x[m.astype(bool)]
                parts.append(f"{lab} {y.net.mean() * 100:+.3f}% / {(y.net > 0).mean():.0%} / {len(y)}")
            lines.append(f"     {tf:>4} {half:<8} " + "   ".join(parts))
    q1 = all(cl[(cl.half == h) & cl.chopR.astype(bool)].net.mean() > cl[(cl.half == h) & ~cl.chopR.astype(bool)].net.mean()
             for h in ("tune", "holdout"))
    # every config, inside chop, both halves
    lines += ["", "   EVERY config inside chop (CHOP-R and CHOP-E): those positive on BOTH halves, with day-clustered t:"]
    hits = []
    for (side, L, ex, tf), x in T.groupby(["side", "L", "exit", "tf"]):
        for flag in ("chopR", "chopE"):
            r = {h: tstat_by_day(x[(x.half == h) & x[flag].astype(bool)]) for h in ("tune", "holdout")}
            if all(r[h][0] > 0 for h in r):
                ok = all(r[h][1] >= 2 for h in r)
                hits.append(ok)
                lines.append(f"     {side:<5} L{L} {ex:<7} {tf:>4} {flag}: tune {r['tune'][0] * 100:+.3f}% (t {r['tune'][1]:+.1f}, "
                             f"n {r['tune'][2]})  holdout {r['holdout'][0] * 100:+.3f}% (t {r['holdout'][1]:+.1f}, "
                             f"n {r['holdout'][2]}){'  <- t >= 2 both' if ok else ''}")
    n_cfg = T.groupby(["side", "L", "exit", "tf"]).ngroups * 2
    lines.append(f"     ({len(hits)} of {n_cfg} config x meter cells positive on both halves inside chop; "
                 f"{sum(hits)} with t >= 2 on both)")
    return q1, sum(hits)


def part2(lines: list):
    from backtest.chop_revert import data, run, stats
    C, F, elig, er_btc, er_coin, reg = data()
    lines += ["", "PART 2 - RSI reversals on the PIT top-40 DAILY book (chop_revert.py's harness)",
              f"   {'signal':<7}{'gate':<8}{'tune CAGR':>11}{'fall':>6}{'hold CAGR':>11}{'fall':>6}{'chop avg mo':>13}"]
    lab = reg.groupby(reg.index.to_period("M")).agg(lambda s: s.value_counts().idxmax())
    pos = []
    for sig in ("rsi14", "rsi2"):
        for gate in ("NONE", "MARKET", "COIN", "BOTH"):
            r = run(C, F, elig, er_btc, er_coin, gate, sig)
            tu, ho = stats(r[r.index < CUT]), stats(r[r.index >= CUT])
            m = (1 + r).groupby(r.index.to_period("M")).prod() - 1
            mr = pd.DataFrame({"m": m, "reg": lab.reindex(m.index)}).dropna()
            ch = mr[mr.reg == "chop"].m.mean()
            if tu[0] > 0 and ho[0] > 0:
                pos.append(f"{sig}/{gate}")
            lines.append(f"   {sig:<7}{gate:<8}{tu[0] * 100:>+10.1f}%{tu[1] * 100:>5.0f}%{ho[0] * 100:>+10.1f}%"
                         f"{ho[1] * 100:>5.0f}%{ch * 100:>+12.2f}%")
            print(lines[-1], flush=True)
    return pos


def main():
    from backtest.chop_revert import data
    C, _, _, er_btc, _, reg = data()
    lines = [f"backtest/rsi_chop.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC", ""]
    q1, n2 = part1(reg, er_btc, lines)
    pos = part2(lines)
    lines += ["", "REGISTERED PREDICTIONS",
              f"  Q1 classic long better inside chop than outside on both halves (all timeframes pooled) -> {'RIGHT' if q1 else 'WRONG'}",
              f"  Q2 no config positive inside chop on both halves with t >= 2 on each -> {'RIGHT' if n2 == 0 else 'WRONG'} ({n2})",
              f"  Q3 no gated daily RSI book positive on both halves -> {'RIGHT' if not pos else 'WRONG'} ({', '.join(pos) or 'none'})"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

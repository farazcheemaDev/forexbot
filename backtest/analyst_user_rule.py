"""The user's rule from the live Analyst desk: crypto only, liquidity sweeps only, wide stops, with risk management - 4.7 years (2026-11-13)

THE USER (after the live breakdown of 122 calls): "it's clear that this is not random, what's working with proper stops and risk management -
there's a profitable strategy". The live record's best groups were crypto (BNB / BTC), liquidity sweeps (SMC), stops of 0.8%+, shorts; the desk
wins 23% against 18% for random entries. The question here: written down as a rule BEFORE this run, and given risk management, does it make money
on the desk's 4.7-year replay, on both halves?

THE RULE (fixed before the run, from the live record of 2026-11-13)
  R0  crypto only (BTC ETH SOL XRP BNB; no gold / QQQ), SMC liquidity sweeps only, stop >= 0.8% of the entry       <- the PRIMARY
  R1  R0 + reward:risk <= 4 (the 2026-11-02 review's filter: calls with RR > 4 went 0 for 16 live)
  R2  R0 shorts only (shorts made the live book's money)
  R3  R0 + the 4h EMA50 slope with the call (trend filter)
RISK MANAGEMENT (each applied to every rule): risk 0.5% / 1% / 2% of booked equity a call, sized at entry, booked at exit;
  'capped' = skip a call that would push open notional past 3x equity (the desk's own cap); 'day stop' = no new call after the booked
  equity has fallen 2% since the start of the UTC day. Risk management cannot change a call's R; it changes which calls are taken and how big.

HOW: backtest/analyst_filters_oos.py's engine (every signal recorded, the filter applied BEFORE the one-call-per-symbol-and-rule cooldown, as a
filter inside analyst.py would), its random-entry odds (desk.baseline on the 500 bars before the call), 12bp, 1h bars (a bar touching both stop
and target = a loss). Split 2024-12-07. Bet = calls of one UTC day in one direction; t over bets.

REGISTERED BEFORE THE RUN (2026-11-13)
  U1  R0 is negative per call on the holdout.                                                                            (75%)
  U2  No rule passes the bar: R/bet > 0 with t >= 2 on BOTH halves and the hit rate above the random odds on both.          (90%)
  U3  R0's hit rate is below the random odds on both halves.                                                              (60%)
  U4  No rule x risk setting ends above $300 on BOTH halves.                                                              (70%)
  U5  The 2% day stop moves R0's holdout end at 1% risk by less than 10% either way.                                       (60%)

RESULT (2026-11-13, logs/analyst_user_rule.txt) - NO PASS; every rule loses on both halves at every risk setting. U1-U4 right, U5 wrong.
  R0 (crypto + SMC + stop >= 0.8%): 2,211 / 1,323 calls (~780 / ~700 a year), hit 13.1% vs random 14.1% (tune), 10.7% vs 13.3% (holdout);
  -0.132 / -0.136R a call, negative every year 2022-26. $300 at 0.5% risk -> $64 / $116; at 1% -> $12 / $41; at 2% -> $0 / $4.
  R1 (+ RR <= 4) -0.113 / -0.069R; R2 (shorts) -0.139 / -0.080R; R3 (+ 4h EMA50) -0.104 / -0.169R. Every hit rate is BELOW the random odds.
  Risk management only slows the loss: the 2% day stop and the 3x cap skip calls and lift the end (best: R1 at 2% capped + day stop, holdout
  $241, tune $110) - no rule x risk setting ends above $300 on either half's pair. The live record's wide-stop sweeps (122 calls, 17 days) are
  not what this rule does over 4.7 years.

    python -m backtest.analyst_user_rule
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import analyst as an  # noqa: E402
from backtest.analyst_filters_oos import CACHE, CAND, SPLIT, add_baseline, take  # noqa: E402

LOG = ROOT / "logs" / "analyst_user_rule.txt"
CRYPTO = {"BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"}
DAY = 86_400_000


def r0(r) -> bool:
    return r.symbol in CRYPTO and r.method == "SMC" and r.stop_pct >= 0.008


RULES = {
    "R0 crypto + SMC + stop>=0.8%": r0,
    "R1 R0 + RR<=4": lambda r: r0(r) and r.target_pct / r.stop_pct <= 4.0,
    "R2 R0 shorts only": lambda r: r0(r) and r.side == "short",
    "R3 R0 + 4h EMA50 with the call": lambda r: r0(r) and r.with_ema,
}


def book(x: pd.DataFrame, risk: float, cap: float | None = None, day_stop: float | None = None, start: float = 300.0) -> dict:
    """Sized at entry on the booked equity, booked at exit (exits before entries at the same instant).
    cap: skip a call that would push open notional past cap x equity. day_stop: no new call once booked equity is day_stop below the
    UTC day's opening booked equity."""
    ev = sorted([(e, 0, j) for j, e in enumerate(x.exit_ms)] + [(m, 1, j) for j, m in enumerate(x.made_ms)])
    r, sp = x.r_net.to_numpy(), x.stop_pct.to_numpy()
    eq, peak, dd, open_, taken, day, day_open = start, start, 0.0, {}, 0, None, start
    for t, kind, j in ev:
        d = t // DAY
        if d != day:
            day, day_open = d, eq
        if kind == 0:
            if j in open_:
                risk_usd, _n = open_.pop(j)
                eq += risk_usd * r[j]
                peak = max(peak, eq)
                dd = max(dd, 1 - eq / peak)
            continue
        if day_stop is not None and eq < day_open * (1 - day_stop):
            continue
        risk_usd = eq * risk
        notional = risk_usd / sp[j]
        if cap is not None and sum(n for _r, n in open_.values()) + notional > cap * eq:
            continue
        open_[j] = (risk_usd, notional)
        taken += 1
    return dict(end=eq, dd=dd, taken=taken)


def stats(x: pd.DataFrame) -> dict:
    t = pd.to_datetime(x.made_ms, unit="ms")
    b = x.assign(day=t.dt.floor("D")).groupby(["day", "side"]).r_net.mean()
    se = b.std(ddof=1) / np.sqrt(len(b)) if len(b) > 2 else np.nan
    return dict(n=len(x), bets=len(b), hit=(x.status == "WIN").mean(), rnd=x.base_p.mean(), rc=x.r_net.mean(), rb=b.mean(),
                t=b.mean() / se if se and se > 0 else np.nan, years=(x.made_ms.max() - x.made_ms.min()) / DAY / 365.25)


def main():
    bars = {s: json.loads((CACHE / f"{s}_1h.json").read_text()) for s in an.WATCH}
    C = pd.read_pickle(CAND)
    order = {s: k for k, s in enumerate(an.WATCH)}
    C = C.assign(o=C.symbol.map(order)).sort_values(["o", "made_ms"], kind="stable").drop(columns="o").reset_index(drop=True)
    L = [f"backtest/analyst_user_rule.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(C)} replay signals, split {SPLIT.date()}, 12bp, "
         "$300 start, booked equity", ""]
    memo, S, A = {}, {}, {}
    for lab, f in RULES.items():
        x = add_baseline(take(C, f), bars, memo).sort_values("made_ms", kind="stable").reset_index(drop=True)
        tt = pd.to_datetime(x.made_ms, unit="ms")
        L.append(lab)
        for half, m in (("tune", tt < SPLIT), ("hold", tt >= SPLIT)):
            h = x[m.to_numpy()].reset_index(drop=True)
            s = stats(h)
            S[(lab, half)] = s
            L.append(f"  [{half}] n {s['n']:>4} ({s['n'] / s['years']:.0f}/yr) bets {s['bets']:>4}  hit {s['hit'] * 100:4.1f}% vs random {s['rnd'] * 100:4.1f}%  "
                     f"R/call {s['rc']:+.3f}  R/bet {s['rb']:+.3f} (t {s['t']:+.1f})")
            for risk in (0.005, 0.01, 0.02):
                for rm, kw in (("plain", {}), ("capped 3x", dict(cap=3.0)), ("day stop 2%", dict(day_stop=0.02)),
                               ("capped + day stop", dict(cap=3.0, day_stop=0.02))):
                    a = book(h, risk, **kw)
                    A[(lab, half, risk, rm)] = a
                    L.append(f"      risk {risk * 100:.1f}% {rm:<18} took {a['taken']:>4}  $300 -> ${a['end']:>8,.0f}  fall {a['dd'] * 100:3.0f}%")
        yr = x.assign(y=tt.dt.year).groupby("y").r_net.agg(["size", "mean"])
        L.append("  by year: " + "  ".join(f"{y} n {int(a)} {b:+.2f}R" for y, (a, b) in yr.iterrows()))
        L.append("")
    k0 = "R0 crypto + SMC + stop>=0.8%"
    passes = [k for k in RULES if all(S[(k, h)]["rb"] > 0 and S[(k, h)]["t"] >= 2 and S[(k, h)]["hit"] > S[(k, h)]["rnd"] for h in ("tune", "hold"))]
    both_up = [(k, rk, rm) for (k, h, rk, rm), a in A.items() if h == "tune" and a["end"] > 300 and A[(k, "hold", rk, rm)]["end"] > 300]
    e1, e2 = A[(k0, "hold", 0.01, "plain")]["end"], A[(k0, "hold", 0.01, "day stop 2%")]["end"]
    L += ["PREDICTIONS",
          f"  U1 R0 negative per call on the holdout ({S[(k0, 'hold')]['rc']:+.3f}R) -> {'RIGHT' if S[(k0, 'hold')]['rc'] < 0 else 'WRONG'}",
          f"  U2 no rule passes the bar (passing: {passes or 'none'}) -> {'RIGHT' if not passes else 'WRONG'}",
          f"  U3 R0 hit below random on both halves ({S[(k0, 'tune')]['hit'] * 100:.1f} vs {S[(k0, 'tune')]['rnd'] * 100:.1f}; "
          f"{S[(k0, 'hold')]['hit'] * 100:.1f} vs {S[(k0, 'hold')]['rnd'] * 100:.1f}) -> "
          f"{'RIGHT' if all(S[(k0, h)]['hit'] < S[(k0, h)]['rnd'] for h in ('tune', 'hold')) else 'WRONG'}",
          f"  U4 no rule x risk setting ends above $300 on both halves ({len(both_up)} do: {both_up[:6]}) -> {'RIGHT' if not both_up else 'WRONG'}",
          f"  U5 day stop moves R0 holdout end at 1% by < 10% (${e1:,.0f} -> ${e2:,.0f}, {(e2 / e1 - 1) * 100:+.1f}%) -> "
          f"{'RIGHT' if abs(e2 / e1 - 1) < 0.10 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

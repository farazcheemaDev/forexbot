"""THE WORKS MAP'S MARKET STATES APPLIED TO THE ANALYST DESK'S CALLS (2026-11-15)

THE USER (2026-11-15): "add our findings to the analyst desk in any way that improves the signal from what we have found". The findings
(works_map.py): the books fall into a MOMENTUM family that earns when alts run (fuel HIGH, no alt bleed) and a FORCED-FLOW family that
earns in BTC bears and alt bleeds; the states are knowable at each day's open. The desk (analyst.py) makes three kinds of call on 7
markets: FIB (a pullback in a trend: momentum), SR (a bounce at a level) and SMC (a liquidity sweep reclaimed: a reversal). Its replay
(analyst_replay.py, 10,580 calls 2022-02 .. 2026-10) loses -0.20R a call and hits below a random entry with the same stop / target /
hours; earlier slices by stop, RR, rule, side, the coin's daily / 1000h trend and 24h momentum found nothing (analyst_replay_cuts.py).
The MARKET-WIDE states below were never tried on it.

DATA     calls: strategy_analysis/data/analyst_replay/calls.json (crypto only - BTC ETH SOL XRP BNB; gold and QQQ have no crypto state);
         states: works_map.py's cache, the day the call was made (closes through the day before - known at that day's open); calls
         after the state series ends (2026-09-13) are dropped. Halves split 2024-12-07 (the replay's own). Unit: a bet = the calls made
         the same UTC day in the same direction (the desk's amended unit); t over bets.
THE FOUR GATES (fixed here; each keeps a subset of calls)
  G1 FAMILY STATE   longs only when fuel is not LOW and the alts are not bleeding (median top-40 alt > -15% over 30 days); shorts only
                    in an alt bleed or a BTC bear (the momentum family's and the forced-flow family's states)
  G2 BTC LABEL      longs only when BTC is labelled bull, shorts only when it is labelled bear (market_neutral.btc_regime); chop: none
  G3 FORCED FLOW    in a deep bleed (median alt <= -25%) longs only (buy the forced selling, as capit2 and the sleeve do); else every call
  G4 METHOD STATE   FIB (momentum) calls only in the momentum state (fuel not LOW, no bleed); SR and SMC (reversal) calls only outside it
MEASURES per gate and half: kept vs dropped calls' hit rate minus their random odds (the desk's own skill measure) - the IMPROVEMENT is
         kept minus dropped, with t from the bet-level difference (kept bets vs dropped bets, Welch); and the kept calls' net R per bet.
VERDICT  IMPROVES = kept beat dropped on hit-minus-random on BOTH halves, Holm p < 0.05 over the 4 (p from the weaker half's t).
         PAYS = also kept net R per bet > 0 with t >= 2 on both halves. A gate that IMPROVES goes into the desk as a tag and into the
         dashboard's pick; one that PAYS would become the desk's rule (a dated amendment). Neither changes any trading bot.

REGISTERED BEFORE THE FIRST NUMBER (2026-11-15; my prior that any gate IMPROVES: about 25%; PAYS: about 3%)
  S1  No gate PAYS.
  S2  At most one gate IMPROVES.
  S3  G2 (the BTC label) does not improve: the coin's own trend did not (analyst_replay_cuts.py).
  S4  The share of calls kept: G1 40-60%, G2 30-50%, G3 85-100%, G4 40-60%.

RESULT (2026-11-15, logs/analyst_states.txt): NO GATE IMPROVES OR PAYS (Holm 0.63-1.00) on 9,830 crypto replay calls. FOLLOWING the market's
state made the calls WORSE: G1 -3.7 / -3.8 points of hit rate over random (tune / holdout, t -2.5 / -2.0), G2 (the BTC label) -3.8 / -3.0;
G4 (method by state) about 0; G3 (no shorts in a deep bleed) +3.6 / +7.3 (t 1.0 / 2.4) - the right sign on both halves, not significant on
the tune half. By state: deep-bleed longs hit 3.4 points over random (-0.06R a call), deep-bleed shorts 6.0 under. POST HOC (after the
registered gates failed): the inverse of G1 - calls AGAINST the state (a long while fuel is LOW or the alts bleed; a short while they do
not bleed and BTC is not bear) - beat the rest by +3.7 / +3.8 points (t 2.5 / 2.0), in every year 2022-26 (+1.5..+4.0), inside the sweet
spot +3.8 / +3.0 (t 2.3 / 1.4); those calls still lose -0.16 / -0.23R a call. It went into analyst.py as a recorded TAG with a registered
forward test (the desk's amendment of 2026-11-15), not as a filter. S1, S2, S3 right; S4 wrong (G2 kept 28%, under 30-50%). Tests 6.

    python -m backtest.analyst_states        (logs/analyst_states.txt)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import candle_scan as cs  # noqa: E402

LOG = ROOT / "logs" / "analyst_states.txt"
CALLS = ROOT / "strategy_analysis" / "data" / "analyst_replay" / "calls.json"
SPLIT = pd.Timestamp("2024-12-07")
CRYPTO = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT")
GATES = ("G1", "G2", "G3", "G4")


def momentum_state(fuel, alt30):
    return (fuel != "LOW") & (alt30 > -0.15)


def keep(g: str, d: pd.DataFrame) -> pd.Series:
    """The calls a gate keeps. d has side, method, btc, fuel, alt30."""
    lng, sht = d.side == "long", d.side == "short"
    mom = momentum_state(d.fuel, d.alt30)
    if g == "G1":
        return (lng & mom) | (sht & ((d.alt30 <= -0.15) | (d.btc == "bear")))
    if g == "G2":
        return (lng & (d.btc == "bull")) | (sht & (d.btc == "bear"))
    if g == "G3":
        return ~(sht & (d.alt30 <= -0.25))
    if g == "G4":
        return ((d.method == "FIB") & mom) | ((d.method != "FIB") & ~mom)
    raise ValueError(g)


def bets(d: pd.DataFrame) -> pd.DataFrame:
    """One row per (day, side): mean hit-minus-random and mean net R."""
    return d.assign(ex=d.win - d.base_p).groupby(["day", "side"]).agg(ex=("ex", "mean"), R=("r_net", "mean"), n=("ex", "size"))


def welch_t(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3 or len(b) < 3:
        return float("nan")
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float((a.mean() - b.mean()) / se) if se > 0 else float("nan")


def t_mean(a: np.ndarray) -> float:
    return float(a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))) if len(a) > 2 and a.std(ddof=1) > 0 else float("nan")


def score(d: pd.DataFrame, k: pd.Series) -> dict:
    a, b = d[k], d[~k]
    ba, bb = bets(a), bets(b)
    return dict(n=int(k.sum()), share=float(k.mean()), ex_k=float((a.win - a.base_p).mean()) if len(a) else np.nan,
                ex_d=float((b.win - b.base_p).mean()) if len(b) else np.nan,
                imp=float(ba.ex.mean() - bb.ex.mean()) if len(ba) and len(bb) else np.nan,
                imp_t=welch_t(ba.ex.to_numpy(), bb.ex.to_numpy()), R_k=float(a.r_net.mean()) if len(a) else np.nan,
                Rbet=float(ba.R.mean()) if len(ba) else np.nan, Rbet_t=t_mean(ba.R.to_numpy()), bets=len(ba))


def load():
    from backtest import works_map as wm
    r = pd.DataFrame(json.loads(CALLS.read_text()))
    r = r[r.symbol.isin(CRYPTO)].copy()
    r["t"] = pd.to_datetime(r.made_ms, unit="ms")
    r["day"] = r.t.dt.floor("D")
    r["win"] = (r.status == "WIN").astype(float)
    _, st, _ = wm.load()
    s = st[["btc", "fuel", "alt30"]].copy()
    s.index = pd.DatetimeIndex(s.index).as_unit("ns")
    r = r.merge(s, left_on=r.day.astype("datetime64[ns]"), right_index=True, how="left")
    r = r[r.day <= s.index[-1]]
    return r.dropna(subset=["btc", "fuel", "alt30"]).reset_index(drop=True)


def main():
    t0 = time.time()
    d = load()
    halves = {"tune": d.t < SPLIT, "hold": d.t >= SPLIT}
    L = [f"backtest/analyst_states.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the desk's replay calls (crypto) x the works map's market "
         f"states; {len(d)} calls {d.t.min():%Y-%m-%d} .. {d.t.max():%Y-%m-%d}; halves split {SPLIT.date()}; a bet = same day + side", ""]
    allb = {h: bets(d[m]) for h, m in halves.items()}
    L.append("ALL CALLS: " + "; ".join(f"{h} {int(m.sum())} calls, hit {d[m].win.mean() * 100:.1f}% vs random {d[m].base_p.mean() * 100:.1f}%, "
                                        f"R/call {d[m].r_net.mean():+.3f}, R/bet {allb[h].R.mean():+.3f}" for h, m in halves.items()))
    L.append("")
    L.append(f"   {'gate':<4}{'half':>6}{'kept':>7}{'share':>7}{'kept hit-rnd':>14}{'dropped':>10}{'improve':>9}{'t':>6}{'R/call':>8}{'R/bet':>8}{'t':>6}")
    res, p = {}, {}
    for g in GATES:
        res[g] = {}
        for h, m in halves.items():
            dd = d[m]
            res[g][h] = score(dd, keep(g, dd))
            s = res[g][h]
            L.append(f"   {g:<4}{h:>6}{s['n']:>7}{s['share'] * 100:>6.0f}%{s['ex_k'] * 100:>+13.1f}%{s['ex_d'] * 100:>+9.1f}%{s['imp'] * 100:>+8.1f}%"
                     f"{s['imp_t']:>+6.1f}{s['R_k']:>+8.3f}{s['Rbet']:>+8.3f}{s['Rbet_t']:>+6.1f}")
        p[g] = cs.p_one_sided(np.nan_to_num(min(res[g]["tune"]["imp_t"], res[g]["hold"]["imp_t"]), nan=-10.0))
    hp = dict(zip(GATES, cs.holm([p[g] for g in GATES])))
    imp = {g: all(res[g][h]["imp"] > 0 for h in halves) and hp[g] < 0.05 for g in GATES}
    pay = {g: imp[g] and all(res[g][h]["Rbet"] > 0 and res[g][h]["Rbet_t"] >= 2 for h in halves) for g in GATES}
    L += ["", "   Holm p (improvement, weaker half): " + ", ".join(f"{g} {hp[g]:.3f}" for g in GATES),
          "   IMPROVES: " + (", ".join(g for g in GATES if imp[g]) or "none") + "   PAYS: " + (", ".join(g for g in GATES if pay[g]) or "none")]
    # by state: the desk's record in each family state (context for the dashboard)
    L += ["", "THE DESK BY STATE (hit minus random, R per call; all halves)"]
    mom = momentum_state(d.fuel, d.alt30)
    for nm, m in (("momentum state", mom), ("not momentum", ~mom), ("deep bleed", d.alt30 <= -0.25)):
        for sd in ("long", "short"):
            x = d[m & (d.side == sd)]
            if len(x):
                L.append(f"   {nm:<15} {sd:<6} n {len(x):>5}  hit-rnd {(x.win - x.base_p).mean() * 100:+5.1f}%  R/call {x.r_net.mean():+.3f}")
    share = {g: float(keep(g, d).mean()) for g in GATES}
    s4 = 0.40 <= share["G1"] <= 0.60 and 0.30 <= share["G2"] <= 0.50 and 0.85 <= share["G3"] <= 1.0 and 0.40 <= share["G4"] <= 0.60
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    L += ["", "REGISTERED PREDICTIONS",
          f"  S1 no gate pays -> {ok(not any(pay.values()))}",
          f"  S2 at most one gate improves -> {ok(sum(imp.values()) <= 1)} ({sum(imp.values())})",
          f"  S3 G2 does not improve -> {ok(not imp['G2'])}",
          f"  S4 shares kept G1 40-60, G2 30-50, G3 85-100, G4 40-60 -> {ok(s4)} ("
          + ", ".join(f"{g} {share[g] * 100:.0f}%" for g in GATES) + ")",
          f"run time {time.time() - t0:.0f}s"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

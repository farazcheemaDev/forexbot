"""The four filters of an outside 'recommendations' document, run INSIDE the Analyst desk's replay engine, tune vs holdout (2026-11-12)

THE USER (with a 9-page PDF, 'Forexbot & Analyst Desk: Strategic Recommendations & Optimization Guide'): verify every claim, then "run or design a
clean replay test combining ONLY the verified improvements ... on the held-out split without overfitting. After 12 bps does the combined filter set
survive out of sample with positive expectancy and acceptable drawdown, or is it curve-fit noise?"

THE DOCUMENT'S FILTERS (its section 3), as testable rules
  F1  stop >= 0.8% of the entry                       (its 'Improvement 1')
  F2  4h EMA(50) slope with the call: long only if EMA50 of the last CLOSED 4h bar > the one before; short only if <   (its 'Improvement 2';
      the document says 'SMC sweeps must be filtered'; applied to every rule here, and to SMC alone in a separate line)
  F3  session gate: no XAU / QQQ call unless the market under it is open when the call is made and when its candle began - analyst.can_call, the
      DST-aware gate already LIVE since 2026-11-08 (f921ca8). The document's own hours (QQQ 14:30-20:00 UTC, gold shut 21:00-22:00 UTC) are wrong
      half of the year; the live gate is used instead.
  F4  'replace blind S/R bounces with break-and-retest': the document gives no exact rule (which level, how far, the 15m candle), so building one now
      would be a NEW rule designed after looking. Tested as the only honest proxy: DROP the SR rule.
  COMBINED = F1 + F2 + F3 + F4 (the registered primary).

HOW (this is the engine, not a slice of old calls)
  backtest/analyst_replay.py's loop, line for line (same cached 1h bars, same 4h / 1d aggregation, entry at the next bar's open, desk.resolve,
  12bp, one open call per symbol and rule, 6h cooldown after it ends) - but every signal is recorded with its features and resolved first, and
  each variant then applies its filter BEFORE the cooldown, as a filter inside analyst.py would. A post-hoc slice of the 10,580 calls is not the
  same thing: a call the filter rejects no longer blocks the next one. CHECK: the variant with no filter must reproduce the 10,580 calls exactly.
  Split 2024-12-07 (the replay's). Bet = calls made the same UTC day in the same direction; t over bets. Account = $300, 0.5% of the booked
  equity at risk per call (the desk's rule), sized at entry, booked at exit, no gross cap; deepest fall of the booked equity.

REGISTERED BEFORE THE RUN (2026-11-12)
  O1  COMBINED is negative per call on the holdout (R/call < 0).                                                          (70%)
  O2  COMBINED's holdout R/bet t is under 2 whichever sign - no pass.                                                     (90%)
  O3  F2 alone does not lift the hit rate above the random-entry odds on both halves.                                     (70%)
  O4  COMBINED keeps under 15% of the calls.                                                                               (60%)
  O5  The no-filter variant reproduces the replay's 10,580 calls and its -0.197R exactly (if not, nothing below is read).  (95%)
  THE BAR for 'survives': R/bet > 0 with t >= 2 on BOTH halves, hit above the random odds on both, and the holdout account above its start.

RESULT (2026-11-12, logs/analyst_filters_oos.txt) - DOES NOT SURVIVE. O1-O5 all right.
  Parity exact (10,580 calls, -0.1972R). COMBINED (F1+F2+F3+F4) keeps 1,355 calls (13%): -0.093R tune / -0.106R holdout a call, R/bet -0.055 /
  -0.024 (t -0.9 / -0.3), hit 15.7% / 11.6% against random entries' 19.3% / 17.3% - the filtered entries are WORSE than random by 4-6 points on both
  halves; it loses less than the base only because it trades less and wider stops shrink the fee in R. $300 at 0.5% a call ends $195 / $225 (falls
  41% / 34%). By year: negative in 4 of 5 (2024 +0.011R). F2 (4h EMA50 slope) alone makes things WORSE (-0.172 / -0.225R, t -3.1 / -2.9 per bet).
  F1 alone -0.122 / -0.138R. F4 (drop SR) -0.152 / -0.221R. F3 changes only the 2025-26 XAU / QQQ calls. SMC only + F1-F3 -0.104 / -0.164R.
  The one positive cell, FIB long +0.226R (90 calls), is one of ~12 cells read after the run: not a lead.
  Limits: the replay's 7 hand-picked symbols, 1h bars (a bar touching stop and target = loss), no break-and-retest rule (the document gives none).

    python -m backtest.analyst_filters_oos
"""
from __future__ import annotations

import bisect
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import analyst as an  # noqa: E402
import desk  # noqa: E402
from backtest.analyst_replay import aggregate  # noqa: E402

CACHE = ROOT / "strategy_analysis" / "data" / "analyst_replay"
LOG = ROOT / "logs" / "analyst_filters_oos.txt"
CAND = CACHE / "candidates_filters_oos.pkl"
H1, H4, D1 = an.H1, an.H4, an.D1
SPLIT = pd.Timestamp("2024-12-07")


def ema(x: np.ndarray, n: int = 50) -> np.ndarray:
    a, out = 2.0 / (n + 1), np.empty(len(x))
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def candidates(sym: str, bars: list) -> list:
    """Every signal the engine would see, in replay order, resolved, with its features. No cooldown here."""
    if len(bars) < 700:
        return []
    h4all, d1all = aggregate(bars, H4), aggregate(bars, D1)
    s4, sd = [b[0] for b in h4all], [b[0] for b in d1all]
    e4 = ema(np.array([b[4] for b in h4all], float))
    memo: dict = {}
    sr0, fib0 = an.sr_levels, an.fib_swing
    an.sr_levels = lambda h4c, d1c: memo.setdefault(("sr", h4c[-1][0], d1c[-1][0]), sr0(h4c, d1c))
    an.fib_swing = lambda h4c, look=60: memo.setdefault(("fib", h4c[-1][0]), fib0(h4c, look))
    out = []
    try:
        for i in range(500, len(bars) - 1):
            T = bars[i][0] + H1
            nxt = bars[i + 1]
            if nxt[0] != T:
                continue
            k4 = bisect.bisect_right(s4, T - H4)
            h1c = bars[i - 499:i + 1]
            h4c = h4all[max(0, k4 - 300):k4]
            d1c = d1all[max(0, bisect.bisect_right(sd, T - D1) - 200):bisect.bisect_right(sd, T - D1)]
            if len(h4c) < 80 or len(d1c) < 40:
                continue
            slope = e4[k4 - 1] - e4[k4 - 2]                       # the last two CLOSED 4h bars
            sess = an.can_call(sym, T, bars[i][0])
            for sig in an.signals(sym, h1c, h4c, d1c, nxt[1]):
                span = bars[i + 1:i + 1 + sig["hours"]]
                if len(span) < sig["hours"]:
                    continue
                call = dict(side=sig["side"], mode="market", entry=sig["entry"], stop=sig["stop"], target=sig["target"],
                            expires_ms=T + sig["hours"] * H1)
                res = desk.resolve(call, span, T + (sig["hours"] + 2) * H1)
                if res["status"] not in ("WIN", "LOSS", "EXPIRED"):
                    continue
                p = desk.plan_numbers(sig["side"], sig["entry"], sig["stop"], sig["target"], 300.0, an.RISK_PCT)
                out.append(dict(symbol=sym, i=i, method=sig["method"], side=sig["side"], made_ms=T, entry=sig["entry"], stop=sig["stop"],
                                target=sig["target"], status=res["status"], r_net=res["r_net"], exit_ms=res["exit_ms"] + H1,
                                stop_pct=p["stop_pct"], target_pct=p["target_pct"], hours=sig["hours"],
                                with_ema=(slope > 0) if sig["side"] == "long" else (slope < 0), session=sess))
    finally:
        an.sr_levels, an.fib_swing = sr0, fib0
    return out


def take(cands: pd.DataFrame, keep) -> pd.DataFrame:
    """The engine's cooldown applied after the filter: one open call per (symbol, rule), blocked until exit + 1h... as in replay_symbol."""
    rows, blocked = [], {}
    for r in cands.itertuples(index=False):
        if not keep(r):
            continue
        key = (r.symbol, r.method)
        if r.made_ms < blocked.get(key, 0):
            continue
        rows.append(r)
        blocked[key] = r.exit_ms + an.COOLDOWN_H * H1                 # exit_ms already carries the +1h of replay_symbol
    return pd.DataFrame(rows, columns=cands.columns)


def add_baseline(x: pd.DataFrame, bars: dict, memo: dict) -> pd.DataFrame:
    vals = []
    for r in x.itertuples(index=False):
        key = (r.symbol, r.i, r.side, round(r.stop_pct, 9), round(r.target_pct, 9), r.hours)
        if key not in memo:
            b = bars[r.symbol]
            memo[key] = desk.baseline(b[r.i - 499:r.i + 1], r.side, r.stop_pct, r.target_pct, r.hours)["p_tp"]
        vals.append(memo[key])
    return x.assign(base_p=vals)


def account(x: pd.DataFrame, start: float = 300.0, risk: float = 0.005) -> tuple:
    """Sized at entry on the booked equity, booked at exit; returns (end, deepest fall of the booked equity)."""
    ev = [(m, 1, j) for j, m in enumerate(x.made_ms)] + [(e, 0, j) for j, e in enumerate(x.exit_ms)]
    eq, peak, dd, sized = start, start, 0.0, {}
    r = x.r_net.to_numpy()
    for t, kind, j in sorted(ev):
        if kind == 1:
            sized[j] = eq * risk
        else:
            eq += sized.pop(j) * r[j]
            peak = max(peak, eq)
            dd = max(dd, 1 - eq / peak)
    return eq, dd


def line(lab: str, x: pd.DataFrame) -> tuple:
    if len(x) < 5:
        return f"  {lab:<36} n {len(x):>5}", None
    t = pd.to_datetime(x.made_ms, unit="ms")
    b = x.assign(day=t.dt.floor("D")).groupby(["day", "side"]).r_net.mean()
    se = b.std(ddof=1) / np.sqrt(len(b)) if len(b) > 2 else np.nan
    tt = b.mean() / se if se and se > 0 else np.nan
    end, dd = account(x)
    hit = (x.status == "WIN").mean()
    s = dict(n=len(x), bets=len(b), hit=hit, rnd=x.base_p.mean(), rc=x.r_net.mean(), rb=b.mean(), t=tt, mde=2.8 * se, end=end, dd=dd)
    return (f"  {lab:<36} n {len(x):>5} bets {len(b):>4}  hit {hit * 100:5.1f}% vs random {s['rnd'] * 100:5.1f}%  R/call {s['rc']:+.3f}  "
            f"R/bet {s['rb']:+.3f} (t {tt:+.1f}, MDE {s['mde']:.2f}R)  $300 at 0.5% -> ${end:,.0f}, fall {dd * 100:.0f}%"), s


def main():
    bars = {s: json.loads((CACHE / f"{s}_1h.json").read_text()) for s in an.WATCH}
    if CAND.exists():
        C = pd.read_pickle(CAND)
    else:
        rows = []
        for s in an.WATCH:
            rows += candidates(s, bars[s])
            print(s, len(rows), flush=True)
        C = pd.DataFrame(rows)
        C.to_pickle(CAND)
    order = {s: k for k, s in enumerate(an.WATCH)}
    C = C.assign(o=C.symbol.map(order)).sort_values(["o", "made_ms"], kind="stable").drop(columns="o").reset_index(drop=True)
    L = [f"backtest/analyst_filters_oos.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(C)} signals before any cooldown; split {SPLIT.date()}"]
    base = take(C, lambda r: True)
    old = pd.DataFrame(json.loads((CACHE / "calls.json").read_text()))
    same = len(base) == len(old) and np.allclose(np.sort(base.r_net.to_numpy()), np.sort(old.r_net.to_numpy()))
    L.append(f"CHECK (O5): no-filter variant {len(base)} calls, mean {base.r_net.mean():+.4f}R; replay calls.json {len(old)}, {old.r_net.mean():+.4f}R -> "
             f"{'IDENTICAL' if same else 'DIFFERENT'}")
    V = {
        "none (the replay)": lambda r: True,
        "F1 stop >= 0.8%": lambda r: r.stop_pct >= 0.008,
        "F2 4h EMA50 slope with the call": lambda r: r.with_ema,
        "F3 session gate (live)": lambda r: r.session,
        "F4 drop SR": lambda r: r.method != "SR",
        "COMBINED F1+F2+F3+F4": lambda r: r.stop_pct >= 0.008 and r.with_ema and r.session and r.method != "SR",
        "F1+F2+F3, SR kept": lambda r: r.stop_pct >= 0.008 and r.with_ema and r.session,
        "SMC only + F1+F2+F3": lambda r: r.method == "SMC" and r.stop_pct >= 0.008 and r.with_ema and r.session,
    }
    memo, S = {}, {}
    for lab, f in V.items():
        x = add_baseline(take(C, f), bars, memo)
        t = pd.to_datetime(x.made_ms, unit="ms")
        for half, m in (("tune", t < SPLIT), ("hold", t >= SPLIT)):
            txt, s = line(f"{lab} [{half}]", x[m.to_numpy()])
            L.append(txt)
            S[(lab, half)] = s
        if lab.startswith("COMBINED"):
            yr = x.assign(y=t.dt.year).groupby("y").r_net.agg(["size", "mean"])
            L.append("    by year: " + "  ".join(f"{y} n {int(a)} {b:+.3f}R" for y, (a, b) in yr.iterrows()))
            sym = x.groupby("symbol").r_net.agg(["size", "mean"])
            L.append("    by symbol: " + "  ".join(f"{s[:-4]} {int(a)} {b:+.3f}R" for s, (a, b) in sym.iterrows()))
            meth = x.groupby(["method", "side"]).r_net.agg(["size", "mean"])
            L.append("    by rule / side: " + "  ".join(f"{m} {sd} {int(a)} {b:+.3f}R" for (m, sd), (a, b) in meth.iterrows()))
            S["combined_n"] = len(x)
    c_t, c_h = S[("COMBINED F1+F2+F3+F4", "tune")], S[("COMBINED F1+F2+F3+F4", "hold")]
    f2_t, f2_h = S[("F2 4h EMA50 slope with the call", "tune")], S[("F2 4h EMA50 slope with the call", "hold")]
    passed = all(s["rb"] > 0 and s["t"] >= 2 and s["hit"] > s["rnd"] for s in (c_t, c_h)) and c_h["end"] > 300
    L += ["", f"VERDICT (the bar: R/bet > 0 at t >= 2 on both halves, hit above random on both, holdout account above $300): {'SURVIVES' if passed else 'DOES NOT SURVIVE'}",
          "", "REGISTERED PREDICTIONS",
          f"  O1 COMBINED holdout R/call < 0 ({c_h['rc']:+.3f}) -> {'RIGHT' if c_h['rc'] < 0 else 'WRONG'}",
          f"  O2 COMBINED holdout R/bet t < 2 ({c_h['t']:+.2f}) -> {'RIGHT' if c_h['t'] < 2 else 'WRONG'}",
          f"  O3 F2 does not lift hit above random on both halves ({f2_t['hit'] * 100:.1f} vs {f2_t['rnd'] * 100:.1f}; {f2_h['hit'] * 100:.1f} vs {f2_h['rnd'] * 100:.1f}) -> "
          f"{'RIGHT' if not (f2_t['hit'] > f2_t['rnd'] and f2_h['hit'] > f2_h['rnd']) else 'WRONG'}",
          f"  O4 COMBINED keeps < 15% of the calls ({S['combined_n']} of {len(base)} = {S['combined_n'] / len(base) * 100:.0f}%) -> "
          f"{'RIGHT' if S['combined_n'] < 0.15 * len(base) else 'WRONG'}",
          f"  O5 parity -> {'RIGHT' if same else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

"""CAN THE TREND BOOK'S FUEL BE READ? THE SHARE OF COINS ALREADY RUNNING, AS A SIZE GATE AT ENTRY (2026-10-27)

backtest/convexity.py (2026-10-27) found that the trend book's NEXT month depends on how many point-in-time top-40 coins were
already running: by the previous month-end's tercile of RUNNER SHARE (the share of the top-40, BTC out, up more than 20% over 30
days), the trend book's next month averaged -0.5% (median -5.2%, up 18% of months) in the lowest third, +3.0% in the middle and
+69.4% (median +25.1%, up 70%) in the highest; Spearman +0.35 / +0.46 on the two halves. Today's reading is 5.1%, the edge of the
lowest third. That is a persistent, readable state - but the repo's standard for a gate is the bet-smaller line through the REAL
trend engine, decided at ENTRY (CLAUDE.md s3: a label read the same day on a series booked at close is sizing after the outcome),
and 2025-07 (+143%) came right after a 5% reading, so a defensive gate can cut winners. This is that test, one setting each:
  STATE   runner share on entry day D = the share of the PIT top-40 (member on D-1, BTC out) whose close of D-1 is more than 20% above
          its close of D-31. Known at D 00:00 UTC. Point-in-time thresholds: the expanding 33rd / 67th percentile of the share's own
          past (at least 180 days of history, else the gate is off) - no threshold fitted to the whole sample.
  LOW     (below the expanding 33rd percentile): trend LONGS x0.5 (the defensive gate; shorts untouched - the live shorts are paying)
  HIGH    (above the expanding 67th percentile): trend LONGS x1.5 (the upside dial; the book's 6.25x/9x guards still apply)
MACHINERY  alt_bear.defence's: the triple, RAW, 4 bar phases x 10 orderings, the cached bet-smaller line (re-checked), holdout from 2024-04-07.

REGISTERED BEFORE THE FIRST RUN (2026-10-27)
  T1  The defensive gate (LOW x0.5) does not clear the bet-smaller line on both halves in all 4 phases: the explosive months also
      follow quiet ones (2025-07 +143% after a 5% reading), and the alt-bear gates failed this test twice.
  T2  The upside dial (HIGH x1.5) does not clear it either: it adds risk exactly in the months that already carry the book.
  T3  The LOW state is on 25-40% of days since 2020-09.
  T4  Today's runner share is inside the LOW state.
PASS    either variant clears the line on BOTH halves in ALL 4 phases (alt_bear.defence's own rule); then it is a CANDIDATE for a
        forward paper book, not a change to the machine (doc 22 freeze). Otherwise the fuel is something to READ, not to trade.

    python -m backtest.runner_gate
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel  # noqa: E402,F401
from backtest.regime_signals import member_mask  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

LOG = ROOT / "logs" / "runner_gate.txt"
CACHE = ROOT / "logs" / "daily_combos_cache" / "runner_gate.pkl"
MIN_HIST = 180


def runner_state():
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    X = C.to_numpy(float)
    mem = member_mask(C, first, drop_non_crypto(eligibility(40))) & np.isfinite(X)
    ib = list(C.columns).index("BTCUSDT")
    n = len(C)
    share = np.full(n, np.nan)
    for d in range(33, n):
        m = mem[d - 1].copy()
        m[ib] = False
        m &= np.isfinite(X[d - 1]) & np.isfinite(X[d - 31])
        if m.sum() >= 8:
            share[d] = np.mean(X[d - 1, m] / X[d - 31, m] - 1 > 0.20)          # closes through D-1 only
    s = pd.Series(share, index=C.index)
    lo = s.expanding(MIN_HIST).quantile(1 / 3).shift(1)                          # thresholds from strictly past values
    hi = s.expanding(MIN_HIST).quantile(2 / 3).shift(1)
    low = (s < lo).fillna(False)
    high = (s > hi).fillna(False)
    return s, low, high


def main():
    import backtest.dd_fixes as D
    from backtest import trend_combos as TC
    from backtest.bar_phase import rows_for_phase
    from backtest.bull_boost import regimes

    s, low, high = runner_state()
    valid = s.notna() & (s.index >= "2020-09-01")
    t3 = 0.25 <= low[valid].mean() <= 0.40
    an = pd.DatetimeIndex(s.index).as_unit("ns").asi8

    def gate(k_low, k_high):
        lv, hv = low.to_numpy(bool), high.to_numpy(bool)

        def fn(r, t, ctx):
            if r["side"] != "long":
                return 1.0
            tn = pd.Timestamp(t).value if not isinstance(t, (int, np.integer)) else int(t)
            i = np.searchsorted(an, tn, side="right") - 1
            if i < 0:
                return 1.0
            return k_low if lv[i] else (k_high if hv[i] else 1.0)
        return fn

    line = pickle.loads((ROOT / "logs" / "daily_combos_cache" / "trend_combos.pkl").read_bytes())
    res = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
    bear = regimes()[1000]
    bn, bv = pd.DatetimeIndex(bear.index).as_unit("ns").asi8, bear.to_numpy(bool)
    VARS = {"LOW05": (0.5, 1.0), "HIGH15": (1.0, 1.5)}
    for ph in TC.PHASES:
        if all((ph, k, sd) in res for k in VARS for sd in TC.SEEDS):
            continue
        trows = D.decompose(rows_for_phase(ph, tight=True, time_stop=(100, 2.0), max_units=7))
        if ph == 0 and "check" not in res:
            chk = TC.stats(D.sim(trows, bn, bv, 0, lev=9.0, size_fn=D.anchor(21), g=1.0))
            gap = max(abs(chk[k] - line[(0, "g1.0", 0)][k]) for k in chk)
            assert gap < 1e-9, f"trend_combos' cached line is stale (gap {gap})"
            res["check"] = gap
        for sd in TC.SEEDS:
            for k, (kl, kh) in VARS.items():
                res[(ph, k, sd)] = TC.stats(D.sim(trows, bn, bv, sd, lev=9.0, size_fn=D.anchor(21), gate_fn=gate(kl, kh)))
            print(f"  phase {ph} ordering {sd} done", flush=True)
        CACHE.write_bytes(pickle.dumps(res))

    def agg(src, ph, k, key):
        return np.mean([src[(ph, k, sd)][key] for sd in TC.SEEDS])

    L = [f"backtest/runner_gate.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the triple, RAW, 4 bar phases x 10 orderings; holdout from "
         f"{TC.HOLDOUT:%Y-%m-%d}; cached line re-checked (gap {res['check']:.1e})",
         f"   runner share (top-40 up > 20% in 30 days): median {s[valid].median():.2f}; LOW (below the expanding 33rd pct) on {low[valid].mean() * 100:.0f}% "
         f"of days since 2020-09, HIGH on {high[valid].mean() * 100:.0f}%; latest reading {s.dropna().iloc[-1]:.3f} on {s.dropna().index[-1]:%Y-%m-%d} "
         f"(LOW: {bool(low.iloc[-1])}, HIGH: {bool(high.iloc[-1])})", ""]
    passes = {}
    for k, nm in (("LOW05", "trend longs x0.5 when few coins are running"), ("HIGH15", "trend longs x1.5 when many coins are running")):
        cells, ok = [], True
        for ph in TC.PHASES:
            pts = sorted((agg(line, ph, f"g{g}", "fall"), agg(line, ph, f"g{g}", "tune"), agg(line, ph, f"g{g}", "hold")) for g in TC.GS)
            fa = agg(res, ph, k, "fall")
            dt = agg(res, ph, k, "tune") - np.interp(fa, [a for a, _, _ in pts], [b for _, b, _ in pts])
            dh = agg(res, ph, k, "hold") - np.interp(fa, [a for a, _, _ in pts], [c for _, _, c in pts])
            ok = ok and dt > 0 and dh > 0
            cells.append(f"{dt * 100:+.0f}/{dh * 100:+.0f}")
        passes[k] = ok
        L.append(f"  {nm:<46} tune {np.mean([agg(res, p, k, 'tune') for p in TC.PHASES]) * 100:+.0f}% hold "
                 f"{np.mean([agg(res, p, k, 'hold') for p in TC.PHASES]) * 100:+.0f}% fall "
                 f"{np.mean([agg(res, p, k, 'fall') for p in TC.PHASES]) * 100:.0f}% | vs line by phase {'  '.join(cells)} -> {'PASS' if ok else 'fail'}")
    base = [np.mean([agg(line, p, 'g1.0', key) for p in TC.PHASES]) for key in ('tune', 'hold', 'fall')]
    L.append(f"  {'base (x1.0)':<46} tune {base[0] * 100:+.0f}% hold {base[1] * 100:+.0f}% fall {base[2] * 100:.0f}%")
    L += ["", "REGISTERED PREDICTIONS",
          f"  T1 the defensive gate does not clear the line in all 4 phases -> {'RIGHT' if not passes['LOW05'] else 'WRONG'}",
          f"  T2 the upside dial does not clear it either -> {'RIGHT' if not passes['HIGH15'] else 'WRONG'}",
          f"  T3 LOW on 25-40% of days ({low[valid].mean() * 100:.0f}%) -> {'RIGHT' if t3 else 'WRONG'}",
          f"  T4 today is inside LOW -> {'RIGHT' if bool(low.iloc[-1]) else 'WRONG'} (panel ends {s.dropna().index[-1]:%Y-%m-%d})",
          f"  VERDICT: {'CANDIDATE: ' + ', '.join(k for k, v in passes.items() if v) if any(passes.values()) else 'NO GATE - the fuel is something to read, not to trade'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

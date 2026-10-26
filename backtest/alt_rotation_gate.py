"""THE ALTCOIN-ROTATION SKILL'S BREADTH GATE ON THE TREND BOOK'S LONGS (2026-10-27)

The user (2026-10-22/23): "can we do something about it when altcoins are crashing but BTC is still in bull, because it makes
us lose". backtest/alt_bear.py tested one definition of that state (the equal-weight alt index in a 50-day downtrend) and
found no gate that beats the bet-smaller line. SKE-Labs/agent-trading-skills' altcoin-rotation skill defines the state
differently: "BREADTH = share of eligible alts outperforming BTC" over a frozen lookback, "require broad participation", with a
BTC-stress de-risk. The user said not to treat an earlier negative as final, so this runs that definition through the SAME
machinery (alt_bear.defence: the triple trend book, RAW, 4 bar phases x 10 orderings, decided at ENTRY, against the cached
bet-smaller line) - one setting, no sweep:
  ELIGIBLE  the point-in-time top-40 by volume with dead coins in (breadth_trade.member_mask / eligibility), stables and
            non-crypto dropped - the skill's own rule: "never a present-day survivor list"
  BREADTH   share of eligible coins whose 30-day return beats BTC's 30-day return, read at the PREVIOUS close
  GATE      breadth < 0.35 ("alts are not participating"); the skill gives no number, so this is my one pre-declared choice:
            roughly the level where fewer than 1 alt in 3 is keeping up. 30 days = the window of the user's complaint.
  ACTION    trend LONGS x0.5 (and x0 as the harsher variant) on gate days; shorts untouched.

REGISTERED BEFORE THE FIRST RUN (2026-10-27)
  R1  The gate is on 20-45% of days since 2020-03.
  R2  Neither x0.5 nor x0 beats the bet-smaller line on the holdout in all 4 phases (the skill's signal is a cousin of the one
      that failed; the trend book's winners are the alts that break out when most alts lag).
  R3  Alt breadth is low on a larger share of days inside BTC-bull labels than inside BTC-bear labels (alts lag in BTC rallies).
PASS    x0.5 clears the line on BOTH halves in ALL 4 phases (alt_bear.defence's own rule). Otherwise no gate.

    python -m backtest.alt_rotation_gate
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import alt_bear as AB  # noqa: E402
from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel  # noqa: E402
from backtest.regime_signals import member_mask  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

LOOK, THR = 30, 0.35
LOG = ROOT / "logs" / "alt_rotation_gate.txt"
CACHE = ROOT / "logs" / "daily_combos_cache" / "alt_rotation_gate.pkl"


def breadth_series():
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    X = C.to_numpy(float)
    m = member_mask(C, first, drop_non_crypto(eligibility(40))) & np.isfinite(X)
    b = C["BTCUSDT"].to_numpy(float)
    out = np.full(len(C), np.nan)
    for d in range(LOOK + 2, len(C)):
        mem = m[d - 1].copy()
        r = X[d - 1] / X[d - 1 - LOOK] - 1                  # known at the previous close
        rb = b[d - 1] / b[d - 1 - LOOK] - 1
        mem &= np.isfinite(r)
        mem[list(C.columns).index("BTCUSDT")] = False
        if mem.sum() >= 8:
            out[d] = np.mean(r[mem] > rb)
    return pd.Series(out, index=C.index), C


def main():
    import backtest.dd_fixes as D
    from backtest import trend_combos as TC
    from backtest.bar_phase import rows_for_phase
    from backtest.bull_boost import regimes

    br, C = breadth_series()
    gate_s = (br < THR).fillna(False)
    valid = br.notna() & (br.index >= "2020-03-01")
    btc_reg = btc_regime(C).reindex(C.index)
    r1 = 0.20 <= gate_s[valid].mean() <= 0.45
    on_bull = gate_s[valid & (btc_reg == "bull")].mean()
    on_bear = gate_s[valid & (btc_reg == "bear")].mean()
    r3 = on_bull > on_bear
    an, av = pd.DatetimeIndex(gate_s.index).as_unit("ns").asi8, gate_s.to_numpy(bool)

    def gate(k):
        def fn(r, t, ctx):
            if r["side"] != "long":
                return 1.0
            tn = pd.Timestamp(t).value if not isinstance(t, (int, np.integer)) else int(t)
            i = np.searchsorted(an, tn, side="right") - 1
            return k if (i >= 0 and av[i]) else 1.0
        return fn

    line = pickle.loads((ROOT / "logs" / "daily_combos_cache" / "trend_combos.pkl").read_bytes())
    res = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
    bear = regimes()[1000]
    bn, bv = pd.DatetimeIndex(bear.index).as_unit("ns").asi8, bear.to_numpy(bool)
    KS = {"A05": 0.5, "A0": 0.0}
    for ph in TC.PHASES:
        if all((ph, k, sd) in res for k in KS for sd in TC.SEEDS):
            continue
        trows = D.decompose(rows_for_phase(ph, tight=True, time_stop=(100, 2.0), max_units=7))
        if ph == 0 and "check" not in res:
            chk = TC.stats(D.sim(trows, bn, bv, 0, lev=9.0, size_fn=D.anchor(21), g=1.0))
            gap = max(abs(chk[k] - line[(0, "g1.0", 0)][k]) for k in chk)
            assert gap < 1e-9, f"trend_combos' cached line is stale (gap {gap})"
            res["check"] = gap
        for sd in TC.SEEDS:
            for k, mult in KS.items():
                res[(ph, k, sd)] = TC.stats(D.sim(trows, bn, bv, sd, lev=9.0, size_fn=D.anchor(21), gate_fn=gate(mult)))
            print(f"  phase {ph} ordering {sd} done", flush=True)
        CACHE.write_bytes(pickle.dumps(res))

    def agg(src, ph, k, key):
        return np.mean([src[(ph, k, sd)][key] for sd in TC.SEEDS])

    L = [f"backtest/alt_rotation_gate.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the triple, RAW, 4 bar phases x 10 orderings; "
         f"holdout from {TC.HOLDOUT:%Y-%m-%d}; cached line re-checked (gap {res['check']:.1e})",
         f"   gate = breadth(PIT top-40 beating BTC over {LOOK}d) < {THR:g}: on {gate_s[valid].mean() * 100:.0f}% of days since 2020-03; "
         f"inside BTC-bull labels {on_bull * 100:.0f}%, inside BTC-bear {on_bear * 100:.0f}%", ""]
    passes = 0
    for k, nm in (("A05", "trend longs x0.5 on low-breadth days"), ("A0", "no trend longs on low-breadth days")):
        cells, ok = [], True
        for ph in TC.PHASES:
            pts = sorted((agg(line, ph, f"g{g}", "fall"), agg(line, ph, f"g{g}", "tune"), agg(line, ph, f"g{g}", "hold")) for g in TC.GS)
            fa = agg(res, ph, k, "fall")
            dt = agg(res, ph, k, "tune") - np.interp(fa, [a for a, _, _ in pts], [b for _, b, _ in pts])
            dh = agg(res, ph, k, "hold") - np.interp(fa, [a for a, _, _ in pts], [c for _, _, c in pts])
            ok = ok and dt > 0 and dh > 0
            cells.append(f"{dt * 100:+.0f}/{dh * 100:+.0f}")
        passes += ok and k == "A05"
        L.append(f"  {nm:<40} tune {np.mean([agg(res, p, k, 'tune') for p in TC.PHASES]) * 100:+.0f}% hold "
                 f"{np.mean([agg(res, p, k, 'hold') for p in TC.PHASES]) * 100:+.0f}% fall "
                 f"{np.mean([agg(res, p, k, 'fall') for p in TC.PHASES]) * 100:.0f}% | vs line by phase {'  '.join(cells)} -> "
                 f"{'PASS' if ok else 'fail'}")
    base = [np.mean([agg(line, p, 'g1.0', key) for p in TC.PHASES]) for key in ('tune', 'hold', 'fall')]
    L.append(f"  {'base (x1.0)':<40} tune {base[0] * 100:+.0f}% hold {base[1] * 100:+.0f}% fall {base[2] * 100:.0f}%")
    L += ["", "REGISTERED PREDICTIONS",
          f"  R1 gate on 20-45% of days ({gate_s[valid].mean() * 100:.0f}%) -> {'RIGHT' if r1 else 'WRONG'}",
          f"  R2 neither variant passes all 4 phases -> {'RIGHT' if passes == 0 else 'WRONG'}",
          f"  R3 low breadth more common in BTC-bull ({on_bull * 100:.0f}%) than BTC-bear ({on_bear * 100:.0f}%) -> {'RIGHT' if r3 else 'WRONG'}",
          f"  VERDICT: {'PASS (a gate to forward-test)' if passes else 'NO GATE'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

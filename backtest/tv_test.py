"""TESTING THE UNTESTED TRADINGVIEW FAMILIES — with today's corrected methodology.

Eight families never tried in this project (see tv_indicators.py for why these
eight and not the close-based oscillators). Each is run through the same engine and
the same gates that the rest of today's work used, so results are comparable:

    * UNCAPPED trailing exits, trail width swept. A fixed profit target was the
      error that produced a false "SURVIVORS: NONE" across 18 families; nothing
      here gets a target.
    * the capped rule as a CONTROL column, so the size of that effect stays visible
    * LONG and SHORT mean R reported separately. Crypto compounded ~40%/yr over
      this window, so a family earning only on the long side has found drift, not
      an edge. This column reclassified an apparent +174%/yr result as beta earlier.
    * the FEE TOLL in R, measured by differencing a zero-fee run. ~0.067R on 1h.
      A family whose gross edge does not clear it is dead regardless of how the
      signal looks.
    * position cap enforced in the portfolio pass, because pooling trades you could
      never have placed is what made new-listing momentum look real at +0.122R.

WHAT SURVIVES GOES TO THE POINT-IN-TIME GATE
    Anything positive here is only a hypothesis: this is the recent window on coins
    this project has examined all day. The gate that matters is pit_universe.py,
    which cut the best result of the day from +11.24%/month to +5.28% once coins
    were selected on information available at the time.

    python -m backtest.tv_test
    python -m backtest.tv_test --btc-only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.convex import describe, run_uncapped  # noqa: E402
from backtest.mass_search import fetch  # noqa: E402
from backtest.rtest import run_r  # noqa: E402
from backtest.tv_indicators import (aroon, chandelier, dmi, ichimoku,  # noqa: E402
                                    keltner, psar, supertrend, ttm_squeeze)
from bot.strategies.base import Action  # noqa: E402

FEE_BP = 12.0
RISK = 0.5
TRAILS = (5.0, 8.0, 12.0)
COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT",
         "DOGEUSDT", "AVAXUSDT", "LINKUSDT"]
_D: dict = {}


def load(c, days=2400):
    if c not in _D:
        try:
            _D[c] = fetch(c, "1h", days)
        except Exception:
            _D[c] = None
    return _D[c]


def _sig(cond_long: pd.Series, cond_short: pd.Series, idx) -> pd.Series:
    """Signals fire on the bar AFTER the condition, so a bar never sees itself."""
    s = pd.Series(Action.HOLD, index=idx)
    s[cond_long.shift(1).fillna(False).to_numpy(bool)] = Action.BUY
    s[cond_short.shift(1).fillna(False).to_numpy(bool)] = Action.SELL
    return s


# --- signal definitions. Each is the STANDARD reading of the indicator, not a
# --- variant I picked after seeing results.
def s_supertrend(df, period=10, mult=3.0):
    tr, _ = supertrend(df, period, mult)
    flip_up = (tr == 1) & (tr.shift(1) == -1)
    flip_dn = (tr == -1) & (tr.shift(1) == 1)
    return _sig(flip_up, flip_dn, df.index)


def s_keltner_break(df, period=20, mult=2.0):
    _m, u, l = keltner(df, period, mult)
    return _sig(df["close"] > u, df["close"] < l, df.index)


def s_squeeze_release(df, period=20):
    inside, mom = ttm_squeeze(df, period)
    rel = inside.shift(1).fillna(False) & ~inside.fillna(False)
    return _sig(rel & (mom > 0), rel & (mom < 0), df.index)


def s_psar(df):
    tr = psar(df)
    return _sig((tr == 1) & (tr.shift(1) == -1),
                (tr == -1) & (tr.shift(1) == 1), df.index)


def s_aroon(df, period=25):
    up, dn = aroon(df, period)
    return _sig((up > 70) & (dn < 30), (dn > 70) & (up < 30), df.index)


def s_adx_dmi(df, period=14, adx_min=25.0):
    p, m, a = dmi(df, period)
    cross_up = (p > m) & (p.shift(1) <= m.shift(1)) & (a > adx_min)
    cross_dn = (m > p) & (m.shift(1) <= p.shift(1)) & (a > adx_min)
    return _sig(cross_up, cross_dn, df.index)


def s_ichimoku(df):
    tk, kj, sa, sb = ichimoku(df)
    c = df["close"]
    above = (c > sa) & (c > sb) & (tk > kj)
    below = (c < sa) & (c < sb) & (tk < kj)
    return _sig(above & ~above.shift(1).fillna(False),
                below & ~below.shift(1).fillna(False), df.index)


def s_chandelier(df, period=22, mult=3.0):
    ls, ss = chandelier(df, period, mult)
    c = df["close"]
    return _sig((c > ss) & (c.shift(1) <= ss.shift(1)),
                (c < ls) & (c.shift(1) >= ls.shift(1)), df.index)


FAMS = {
    "supertrend": s_supertrend,
    "keltner_brk": s_keltner_break,
    "squeeze_rel": s_squeeze_release,
    "psar": s_psar,
    "aroon": s_aroon,
    "adx_dmi": s_adx_dmi,
    "ichimoku": s_ichimoku,
    "chandelier": s_chandelier,
}


def pool(coins, maker, mode, trail, fee=FEE_BP):
    Rs, Ts, Ds = [], [], []
    for c in coins:
        df = load(c)
        if df is None or len(df) < 3000:
            continue
        try:
            sig = maker(df)
        except Exception as e:
            print(f"    [{c}] {maker.__name__} raised "
                  f"{type(e).__name__}: {str(e)[:70]}", flush=True)
            continue
        if sig is None or int((sig != Action.HOLD).sum()) == 0:
            continue
        if mode == "capped":
            R, idx = run_r(df, sig, 2.0, 3.0, fee)
            D = np.zeros(len(R), dtype=int)
        else:
            R, idx, _b, D = run_uncapped(df, sig, sl_mult=2.0, fee_bp=fee,
                                         mode="trail_atr", trail=trail)
        if len(R):
            Rs.append(R); Ts.append(df["time"].iloc[idx]); Ds.append(D)
    if not Rs:
        return None
    o = np.argsort(np.concatenate([t.values for t in Ts]))
    R = np.concatenate(Rs)[o]
    D = np.concatenate(Ds)[o]
    T = pd.Series(np.concatenate([t.values for t in Ts])[o])
    return describe(R, T, RISK, dirs=(D if D.any() else None))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--btc-only", action="store_true")
    args = ap.parse_args()
    coins = ["BTCUSDT"] if args.btc_only else COINS

    print(f"UNTESTED TRADINGVIEW FAMILIES   {len(coins)} coin(s)  1h  "
          f"fee {FEE_BP}bp  risk {RISK}%")
    print("  8 families never tried here. Uncapped trailing exits, capped rule as "
          "control.")
    print("  RECENT window — generates hypotheses; pit_universe.py is the gate "
          "that matters.\n")
    print("=" * 118)
    print(f"{'family':<13} {'exit':<13} {'n':>6} {'meanR':>8} {'feeR':>7} "
          f"{'t':>7} {'PF':>5} {'maxR':>7} {'longR':>8} {'shortR':>8} "
          f"{'CAGR':>9} {'DD':>7}")
    results = {}
    for name, maker in FAMS.items():
        base = pool(coins, maker, "capped", 0.0)
        if base:
            print(f"{name:<13} {'capped 1.5R':<13} {base['n']:>6} "
                  f"{base['mean']:>+8.3f} {'':>7} {base['t']:>+7.2f} "
                  f"{base['pf']:>5.2f} {base['mx']:>7.1f} {'':>8} {'':>8} "
                  f"{base['cagr']:>+8.1f}% {base['dd']:>6.1f}%", flush=True)
        for tr in TRAILS:
            d = pool(coins, maker, "trail", tr)
            if not d:
                continue
            z = pool(coins, maker, "trail", tr, fee=0.0)
            ft = (z["mean"] - d["mean"]) if z else float("nan")
            ru = " RUIN" if d["ruined"] else ""
            print(f"{name:<13} {'trail '+str(int(tr))+'xATR':<13} {d['n']:>6} "
                  f"{d['mean']:>+8.3f} {ft:>7.3f} {d['t']:>+7.2f} {d['pf']:>5.2f} "
                  f"{d['mx']:>7.1f} {d['long_r']:>+8.3f} {d['short_r']:>+8.3f} "
                  f"{d['cagr']:>+8.1f}% {d['dd']:>6.1f}%{ru}", flush=True)
            results[(name, tr)] = (d, ft, base)
        print()

    if not results:
        print("nothing produced trades")
        return
    print("=" * 118)
    print("VERDICT — both tests must pass to be worth the point-in-time gate")
    print("=" * 118)
    print(f"{'family':<13} {'best meanR':>11} {'trail':>6} {'clears fee':>11} "
          f"{'symmetric':>10} {'verdict':>28}")
    keep = []
    for name in FAMS:
        sub = [(v[0]["mean"], tr, v) for (n, tr), v in results.items() if n == name]
        if not sub:
            continue
        m, tr, (d, ft, base) = max(sub)
        clears = m > 0 and np.isfinite(ft) and m > ft
        sym = (np.isfinite(d["short_r"]) and np.isfinite(d["long_r"])
               and d["short_r"] > 0.3 * abs(d["long_r"]))
        ok = clears and sym
        if ok:
            keep.append(name)
        print(f"{name:<13} {m:>+11.3f} {int(tr):>5}x "
              f"{('YES' if clears else 'NO'):>11} "
              f"{('YES' if sym else 'NO'):>10} "
              f"{('-> point-in-time gate' if ok else 'stop here'):>28}")
    print(f"\n{len(keep)}/{len(FAMS)} families worth the next gate: "
          f"{', '.join(keep) or 'none'}")
    print("\nclears fee = net mean R positive AND larger than the per-trade fee toll")
    print("symmetric  = short side >= 30% of long side. A near-zero short side in "
          "a market that\n             rose ~40%/yr means the result is drift, not "
          "an edge. Seven of seven\n             families tested earlier today "
          "failed exactly this test.")


if __name__ == "__main__":
    main()

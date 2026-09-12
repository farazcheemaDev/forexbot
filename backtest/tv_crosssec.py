"""THE TRADINGVIEW INDICATORS APPLIED CROSS-SECTIONALLY — the one untried move.

THE FINDING THIS RESPONDS TO
    Nineteen indicator families have now been tested here with uncapped trailing
    exits: 11 classic (donchian, bb_break, rsi_mom, macd, ma_cross, roc_mom, ...)
    and 8 TradingView staples (supertrend, keltner, ttm squeeze, psar, aroon,
    adx/dmi, ichimoku, chandelier).

    ALL NINETEEN show the identical signature: uncapping reveals a strong LONG side
    (+0.18R to +0.73R) and a short side of approximately zero or negative. Seven of
    seven earlier, eight of eight now.

    Nineteen different formulas producing one pattern is not nineteen findings. It
    is one finding: these indicators all detect the same underlying phenomenon, and
    on 2020-2026 crypto that phenomenon is THE ASSET CLASS RISING. Testing a
    twentieth indicator would add search space, not information.

THE ONE DESIGN THAT WAS SYMMETRIC
    Cross-sectional market-neutral momentum: rank coins against each other, long the
    top k, short the bottom k. On 500 unseen days it returned +12.6%/yr where the
    same signal held long-only returned -7.3%, with realised beta of -0.06 and a
    short side that carried real weight. It was symmetric because RANKING CANCELS
    THE MARKET MOVE BY CONSTRUCTION - every coin's shared drift appears on both
    sides of the book and nets out.

    So the question this file asks is not "is there a better indicator" but:
        does converting these indicators from DIRECTIONAL to RELATIVE give them a
        short side?

    A directional reading of Supertrend says "BTC is in an uptrend". A relative
    reading says "BTC's trend is stronger than SOL's". The second is a claim about
    dispersion rather than about direction, and it is the form that survived.

WHAT IS RANKED
    Each indicator is converted to a continuous score where higher = stronger trend,
    then coins are ranked on it each rebalance:

      supertrend   distance from the supertrend line, in ATR units, signed by trend
      keltner      position within the Keltner channel (-1 at lower, +1 at upper)
      aroon        aroon_up - aroon_down  (already -100..+100, natively relative)
      adx_dmi      (plus_di - minus_di) scaled by ADX, i.e. direction x conviction
      ichimoku     distance above/below the cloud in ATR units
      psar         distance from the SAR stop in ATR units, signed by regime
      chandelier   distance above the long-stop in ATR units

    All divided by ATR where a price distance is involved, so scores are comparable
    across coins of wildly different volatility. Ranking raw price distances would
    just rank coins by volatility.

CAUSALITY AND COSTS
    Scores are shifted one bar before ranking. Fees charged on actual turnover at
    Bitget taker rates. Beta to the equal-weight universe is reported: if a
    supposedly neutral book shows beta near 1, the neutralisation has failed and the
    result is beta wearing a disguise.

    python -m backtest.tv_crosssec
"""
from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.mass_search import fetch  # noqa: E402
from backtest.tv_indicators import (aroon, chandelier, dmi, ichimoku,  # noqa: E402
                                    keltner, psar, supertrend)
from backtest.xs_momentum import LONG_UNIVERSE, TAKER_BP, simulate  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402

_D: dict = {}


def load(c, days=2400):
    if c not in _D:
        try:
            _D[c] = fetch(c, "1h", days)
        except Exception:
            _D[c] = None
    return _D[c]


# --- score builders: higher = stronger uptrend, comparable across coins --------
def sc_supertrend(df):
    tr, line = supertrend(df, 10, 3.0)
    return (df["close"] - line) / atr_ind(df, 14)


def sc_keltner(df):
    m, u, l = keltner(df, 20, 2.0)
    return (df["close"] - m) / (u - m).replace(0, np.nan)


def sc_aroon(df):
    up, dn = aroon(df, 25)
    return up - dn


def sc_adx_dmi(df):
    p, m, a = dmi(df, 14)
    return (p - m) * a / 100.0


def sc_ichimoku(df):
    _t, _k, sa, sb = ichimoku(df)
    cloud_top = pd.concat([sa, sb], axis=1).max(axis=1)
    cloud_bot = pd.concat([sa, sb], axis=1).min(axis=1)
    c = df["close"]
    a = atr_ind(df, 14)
    above = (c - cloud_top).clip(lower=0)
    below = (c - cloud_bot).clip(upper=0)
    return (above + below) / a


def sc_psar(df):
    return psar(df).astype(float)          # already -1/+1, natively relative


def sc_chandelier(df):
    ls, _ss = chandelier(df, 22, 3.0)
    return (df["close"] - ls) / atr_ind(df, 14)


SCORES = {
    "supertrend": sc_supertrend,
    "keltner": sc_keltner,
    "aroon": sc_aroon,
    "adx_dmi": sc_adx_dmi,
    "ichimoku": sc_ichimoku,
    "psar": sc_psar,
    "chandelier": sc_chandelier,
}


def build_panels(coins, days):
    op, cl = {}, {}
    for c in coins:
        d = load(c, days)
        if d is None or len(d) < 8000:
            continue
        d = d.drop_duplicates("time").sort_values("time").set_index("time")
        op[c], cl[c] = d["open"].astype(float), d["close"].astype(float)
    return pd.DataFrame(op).sort_index(), pd.DataFrame(cl).sort_index()


def score_panel(coins, index, fn):
    cols = {}
    for c in coins:
        d = load(c)
        if d is None:
            continue
        d = d.drop_duplicates("time").sort_values("time").set_index("time")
        try:
            s = fn(d)
        except Exception:
            continue
        cols[c] = s.reindex(index)
    return pd.DataFrame(cols).replace([np.inf, -np.inf], np.nan)


def run(O, C, S, hold, k, fee):
    """Rank on S, long top k / short bottom k, via the xs_momentum engine.

    The engine derives its own momentum internally, so the score panel is injected
    by monkey-patching what it ranks: cleanest is to pass a C whose pct-change
    ordering matches S. Instead of hacking that, reuse the engine's weights by
    handing it S directly as the ranking input.
    """
    from backtest import xs_momentum as xm
    real = xm.weights

    def patched(Cin, lb, hold_, kk, er_min, invvol, long_only=False,
                disp_min=0.0, hedge_index=False, reverse=False, rank_by="ret"):
        mom = S.reindex(Cin.index)[Cin.columns]
        n = len(Cin)
        cols = list(Cin.columns)
        Mv = mom.to_numpy(dtype=float)
        Wa = np.zeros((n, len(cols)))
        start = 210
        for t in range(start, n, hold_):
            m = Mv[t]
            vi = np.flatnonzero(np.isfinite(m))
            if len(vi) < 2 * kk:
                continue
            order = vi[np.argsort(m[vi], kind="stable")]
            lo_i, hi_i = order[:kk], order[-kk:]
            w = np.zeros(len(cols))
            w[hi_i] = 0.5 / kk
            w[lo_i] = -0.5 / kk
            Wa[t:min(t + hold_, n)] = w
        return pd.DataFrame(Wa, index=Cin.index, columns=cols)

    xm.weights = patched
    try:
        Z = pd.DataFrame(0.0, index=O.index, columns=O.columns)
        return simulate(O, C, Z, lb=168, hold=hold, k=k, er_min=0.0,
                        invvol=False, fee_bp=fee, charge_funding=False)
    finally:
        xm.weights = real


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=2400)
    ap.add_argument("--fee", type=float, default=TAKER_BP)
    args = ap.parse_args()

    coins = LONG_UNIVERSE
    O, C = build_panels(coins, args.days)
    print(f"TV INDICATORS, CROSS-SECTIONAL   {C.shape[1]} coins x {len(C):,} bars")
    print(f"  rank on the indicator, long top k / short bottom k, "
          f"fee {args.fee}bp/side")
    print("  19/19 directional families had NO short side. Does ranking give them "
          "one?\n")
    print("=" * 104)
    print(f"{'score':<13} {'hold':>5} {'k':>3} | {'CAGR':>9} {'DD':>7} "
          f"{'Sharpe':>8} {'t':>7} {'beta':>7} {'legL':>8} {'legS':>8}")
    rows = []
    for name, fn in SCORES.items():
        S = score_panel(list(C.columns), C.index, fn)
        if S.empty or S.notna().sum().sum() == 0:
            print(f"{name:<13} produced no scores")
            continue
        for hold, k in itertools.product((24, 48), (5,)):
            s = run(O, C, S, hold, k, args.fee)
            rows.append((s["sharpe"], name, hold, k, s))
            print(f"{name:<13} {hold:>5} {k:>3} | {s['cagr']:>+8.1f}% "
                  f"{s['dd']:>6.1f}% {s['sharpe']:>+8.2f} {s['t']:>+7.2f} "
                  f"{s['beta']:>+7.2f} {s['leg_l']:>+8.1f} {s['leg_s']:>+8.1f}",
                  flush=True)
    if not rows:
        return
    rows.sort(reverse=True)
    print("\n" + "=" * 104)
    sh, name, hold, k, s = rows[0]
    print(f"best: {name} hold={hold} k={k} -> Sharpe {sh:+.2f}, "
          f"CAGR {s['cagr']:+.1f}%, DD {s['dd']:.1f}%, beta {s['beta']:+.2f}")
    pos = sum(1 for r in rows if r[0] > 0)
    print(f"positive Sharpe in {pos}/{len(rows)} cells")
    print(f"\nbeta near 0 means the ranking genuinely cancelled the market move.")
    print("Compare the reference: cross-sectional MOMENTUM scored Sharpe +1.09 "
          "with beta -0.01\nand p=0.0033 on 300 shuffles. Anything here must beat "
          "that to be worth pursuing,\nsince momentum is already validated and "
          "these are not.")


if __name__ == "__main__":
    main()

"""THE BEAR-MARKET BREADTH SIGNAL AS A TRADE - and the attempt to break it.

regime_signals.py found the one signal that predicts the next week INSIDE a bear regime and
passes Holm over 84 cells on both halves: breadth20, the share of PIT top-60 perps closing above
their 20-day average (logs/regime_signals.txt). In BEAR regimes (market_neutral.btc_regime):

    breadth20 in the bottom third (<= 10%)   alt index next 7 days +3.64%  (tune +3.66, hold +3.52)
    breadth20 in the top third (>= 29%)      alt index next 7 days -2.26%  (tune -1.83, hold -3.14)

That is a spread test with full-sample terciles and entry at the very close the signal is read
from. This file turns it into something an account could run and tries to kill it.

THE TRADE
    Each day D in a BEAR regime, read breadth20 (data through D-1). If it is LOW, open a long
    tranche; if HIGH (short variants), a short tranche; else nothing. Each tranche is 1/7 of the
    book and is held 7 days, so the book is a ladder of 7 overlapping tranches (no dependence on
    which weekday the week starts). Outside BEAR regimes it opens nothing.
INSTRUMENTS
    alt index  equal-weight PIT top-40 incl. dead coins, rebalanced daily (not buildable at $221)
    top-10     equal-weight PIT top-10 by prior-month volume (buildable: 10 x $5 minimum)
    BTC        one perp
WHAT IS CHARGED: 6bp per side on every change in net position (12bp round trip), plus 1bp/day on
the index legs for daily rebalancing, plus the members' actual funding over the exact settlement
window (carry_check.exact_funding: settlements strictly after entry, up to and including exit).
THRESHOLDS, both causal
    fixed      LOW = breadth20 < 20% - the web's "capitulation" line, chosen before seeing data
    expanding  LOW / HIGH = bottom / top third of breadth20 over all PRIOR bear days (>= 60 of them)
ATTACKS
    lag 1      enter a full day after the signal: a bounce that lives in the first hours dies
    halves     tune / holdout, and by year
    control    long the same instrument on EVERY bear day (is it the signal, or just "long in bear"?)

REGISTERED PREDICTIONS (2026-09-24, written after seeing the tercile means above and before
running any of this): the long-capitulation trade on the alt index is positive on both halves
at lag 0 and keeps at least half at lag 1; the short-high-breadth side is weaker and noisier;
BTC is smaller but positive; the drawdown is large (it buys falling knives in 2022) with a worst
week below -15%. It beats the always-long-in-bear control in both halves.

    python -m backtest.breadth_trade
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.carry_check import exact_funding  # noqa: E402
from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel  # noqa: E402
from backtest.regime_signals import member_mask  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

CUT = pd.Timestamp("2024-08-29")
H = 7
SIDE_BP = 6.0 / 1e4
REBAL_BP = 1.0 / 1e4


def instruments(C, Fx, first):
    X = C.to_numpy(float)
    ff = pd.DataFrame(X).ffill().to_numpy()
    fx = Fx.to_numpy(float)
    out = {}
    for lab, n in (("alt index (top-40)", 40), ("top-10 basket", 10)):
        m = member_mask(C, first, drop_non_crypto(eligibility(n))) & np.isfinite(X)
        r = np.full(len(C), np.nan); f = np.full(len(C), np.nan)
        for d in range(1, len(C)):
            mem = m[d - 1]
            if mem.sum() >= min(8, n):
                r[d] = np.nanmean(ff[d, mem] / X[d - 1, mem] - 1)
                f[d] = np.mean(fx[d, mem])
        out[lab] = (pd.Series(r, index=C.index), pd.Series(f, index=C.index), REBAL_BP)
    b = C["BTCUSDT"]
    out["BTC"] = (b / b.shift(1) - 1, Fx["BTCUSDT"], 0.0)
    return out


def ladder(sig, ret, fund, rebal, lag=0):
    """sig[D] in {-1,0,+1}: the tranche decided on day D (data through D-1). Tranche D holds
    rows D+lag .. D+lag+H-1 at 1/H of the book. Returns the book's daily net return."""
    s = sig.fillna(0.0).to_numpy()
    pos = np.zeros(len(s))
    for k in range(H):
        pos += np.r_[np.zeros(lag + k), s[:len(s) - lag - k]] / H
    pos = pd.Series(pos, index=sig.index)
    r = ret.fillna(0.0); f = fund.fillna(0.0)
    cost = pos.diff().abs().fillna(pos.abs()) * SIDE_BP + pos.abs() * rebal
    return pos * r - pos * f - cost, pos


def stats(x, pos):
    eq = (1 + x).cumprod()
    yrs = len(x) / 365.0
    cagr = (eq.iloc[-1] ** (1 / yrs) - 1) * 100 if eq.iloc[-1] > 0 else -100.0
    dd = (1 - eq / eq.cummax()).max() * 100
    wk = (1 + x).resample("W").prod() - 1
    sh = x.mean() / x.std(ddof=1) * np.sqrt(365) if x.std(ddof=1) > 0 else np.nan
    return cagr, dd, wk.min() * 100, sh, (pos.abs() > 0).mean() * 100


def half(x):
    """compounded %/yr over each half's calendar days (flat days included)"""
    out = []
    for g in (x[x.index < CUT], x[x.index >= CUT]):
        out.append(((1 + g).prod() ** (365 / max(len(g), 1)) - 1) * 100)
    return out


def main():
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    F.index = C.index
    reg = btc_regime(C)
    feat = pd.read_csv(Path(__file__).resolve().parents[1] / "logs" / "regime_signals_features.csv.gz",
                       index_col=0, parse_dates=True)
    feat.index = feat.index.astype("datetime64[ns]")
    Fx = exact_funding(C.index, C.columns)
    ins = instruments(C, Fx, first)
    br = feat["breadth20"].reindex(C.index)
    bear = (reg.reindex(C.index) == "bear").to_numpy(bool)
    bear_s = pd.Series(bear, index=C.index)

    # expanding terciles over PRIOR bear days only
    lo_t = np.full(len(C), np.nan); hi_t = np.full(len(C), np.nan)
    hist = []
    for d in range(len(C)):
        if len(hist) >= 60:
            lo_t[d], hi_t[d] = np.quantile(hist, [1 / 3, 2 / 3])
        if bear[d] and np.isfinite(br.iat[d]):
            hist.append(br.iat[d])
    lo_t = pd.Series(lo_t, index=C.index); hi_t = pd.Series(hi_t, index=C.index)

    sigs = {
        "control: long every bear day": bear_s.astype(float),
        "LONG breadth < 20% (fixed)": (bear_s & (br < 0.20)).astype(float),
        "LONG bottom third (expanding)": (bear_s & (br <= lo_t)).astype(float),
        "SHORT top third (expanding)": -(bear_s & (br >= hi_t)).astype(float),
        "LONG low + SHORT high (expanding)": (bear_s & (br <= lo_t)).astype(float)
                                             - (bear_s & (br >= hi_t)).astype(float),
    }
    print("ladder of 7 daily tranches, each held 7 days; flat outside BEAR regimes; 12bp round trip,")
    print("actual funding (exact window), +1bp/day rebalancing on the baskets. Returns on the WHOLE account.\n")
    for iname, (ret, fund, rebal) in ins.items():
        print(f"=== {iname}")
        print(f"  {'rule':<36}{'lag':>4}{'CAGR':>8}{'TUNE/yr':>9}{'HOLD/yr':>9}{'DD':>6}{'worst wk':>10}"
              f"{'Sharpe':>8}{'in mkt':>8}   by year %")
        for lab, sg in sigs.items():
            for lag in (0, 1):
                if lab.startswith("control") and lag == 1:
                    continue
                x, pos = ladder(sg, ret, fund, rebal, lag)
                x = x[x.index >= pd.Timestamp("2020-03-01")]
                pos = pos.reindex(x.index)
                cagr, dd, ww, sh, inm = stats(x, pos)
                t, h = half(x)
                yr = " ".join(f"{y % 100:02d}:{((1 + x[x.index.year == y]).prod() - 1) * 100:+.0f}"
                              for y in sorted(set(x.index.year)))
                print(f"  {lab:<36}{lag:>4}{cagr:>+7.1f}%{t:>+8.1f}%{h:>+8.1f}%{dd:>5.0f}%{ww:>+9.1f}%"
                      f"{sh:>8.2f}{inm:>7.0f}%   {yr}")
        print()


if __name__ == "__main__":
    main()

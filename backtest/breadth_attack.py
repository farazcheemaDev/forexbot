"""SECOND ROUND OF ATTACKS on the bear-market breadth trade (breadth_trade.py).

breadth_trade.py: in BEAR regimes, long the alt basket when breadth20 is in the bottom third of
prior bear days and short it in the top third - +25-27%/yr on the whole account at 1x, both
halves positive, survives a one-day entry delay, 20-21% drawdown, active ~25% of days, while
"long every bear day" makes ~0 with a 62-75% drawdown (logs/breadth_trade.txt). A result that
good is a bug until shown otherwise. Attacks:

  1. PLACEBO REGIMES   the identical rule in CHOP only and in BULL only. regime_signals.py saw no
                       breadth pattern there; if the rule earns there too, it is not a bear effect
                       and the "bear" story is decoration.
  2. THE BOT'S GATE    "bear" = BTC below its 42-day (~1000h) average - what the live bot
                       already computes - instead of btc_regime's 50d-MA-and-slope label.
  3. PLATEAU           hold 3 / 7 / 14 days x breadth on 10 / 20 / 50-day averages.
  4. SIGNIFICANCE      month-block bootstrap t of the daily mean (dependence inside months kept).
  5. WITHOUT 2022      the year that carries the most.
  6. THE TREND BOOK    daily correlation with the triple book (10x guard, entry-sized,
                       triple_capped.simulate) and what each earns in BEAR months.

REGISTERED PREDICTIONS (2026-09-24, before running): placebo regimes earn ~0 or lose; the
1000h gate keeps at least half; every plateau cell positive; t > 2.5; positive without 2022;
correlation with the trend book between -0.2 and +0.1.

    python -m backtest.breadth_attack
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.breadth_trade import CUT, half, instruments, stats  # noqa: E402
from backtest import breadth_trade as bt  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel  # noqa: E402
from backtest.regime_signals import member_mask  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

START = pd.Timestamp("2020-03-01")


def breadth(C, first, n):
    X = C.to_numpy(float)
    m60 = member_mask(C, first, drop_non_crypto(eligibility(60))) & np.isfinite(X)
    ma = C.rolling(n, min_periods=n).mean().to_numpy()
    ok = np.isfinite(ma) & m60
    cnt = ok.sum(1)
    b = ((X > ma) & ok).sum(1) / np.where(cnt > 0, cnt, np.nan)
    return pd.Series(b, index=C.index).shift(1)


def ls_signal(br, gate):
    """long bottom third / short top third of breadth over PRIOR gated days, on gated days."""
    g = gate.to_numpy(bool)
    b = br.to_numpy(float)
    s = np.zeros(len(b))
    hist = []
    for d in range(len(b)):
        if len(hist) >= 60 and g[d] and np.isfinite(b[d]):
            lo, hi = np.quantile(hist, [1 / 3, 2 / 3])
            s[d] = 1.0 if b[d] <= lo else (-1.0 if b[d] >= hi else 0.0)
        if g[d] and np.isfinite(b[d]):
            hist.append(b[d])
    return pd.Series(s, index=br.index)


def run(sig, inst, lag=1, h=7):
    ret, fund, rebal = inst
    old = bt.H
    bt.H = h
    try:
        x, pos = bt.ladder(sig, ret, fund, rebal, lag)
    finally:
        bt.H = old
    return x[x.index >= START], pos[pos.index >= START]


def boot_t(x, reps=2000, seed=7):
    m = x.index.to_period("M")
    g = x.groupby(m)
    s, c = g.sum().to_numpy(), g.count().to_numpy()
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(s), size=(reps, len(s)))
    bs = s[pick].sum(1) / c[pick].sum(1)
    return x.mean() / bs.std()


def line(lab, x, pos):
    cagr, dd, ww, sh, inm = stats(x, pos)
    t, h = half(x)
    print(f"  {lab:<46}{cagr:>+7.1f}%{t:>+8.1f}%{h:>+8.1f}%{dd:>5.0f}%{ww:>+8.1f}%{sh:>7.2f}"
          f"{inm:>6.0f}%{boot_t(x):>+7.2f}")


def main():
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    F.index = C.index
    reg = btc_regime(C).reindex(C.index)
    Fx = exact_funding(C.index, C.columns)
    ins = instruments(C, Fx, first)
    alt, top10, btc = ins["alt index (top-40)"], ins["top-10 basket"], ins["BTC"]
    br = {n: breadth(C, first, n) for n in (10, 20, 50)}
    b = C["BTCUSDT"]
    gate1000 = (b < b.rolling(42).mean()).shift(1, fill_value=False).astype(bool)
    gates = {g: (reg == g) for g in ("bear", "chop", "bull")}
    hdr = (f"  {'':<46}{'CAGR':>8}{'TUNE/yr':>9}{'HOLD/yr':>9}{'DD':>6}{'worst wk':>9}{'Sharpe':>7}"
           f"{'in mkt':>7}{'boot t':>7}")

    print("long bottom third / short top third of breadth over prior gated days; ladder of 7-day"
          " tranches; entered ONE DAY after the signal (lag 1); 12bp, funding, 1bp/day rebalancing\n")
    print("1. PLACEBO REGIMES - the same rule, gated to each regime (breadth20)")
    print(hdr)
    for inst_lab, inst in (("alt index", alt), ("top-10", top10)):
        for g, gate in gates.items():
            line(f"{inst_lab}, {g.upper()} only", *run(ls_signal(br[20], gate), inst))
    print("\n2. THE BOT'S OWN GATE: 'bear' = BTC below its 42-day (~1000h) average")
    print(hdr)
    for inst_lab, inst in (("alt index", alt), ("top-10", top10), ("BTC", btc)):
        line(f"{inst_lab}, BTC < 1000h average", *run(ls_signal(br[20], gate1000), inst))
    print("\n3. PLATEAU - top-10 basket, BEAR gate: breadth average x hold")
    print(hdr)
    for n in (10, 20, 50):
        s = ls_signal(br[n], gates["bear"])
        for h in (3, 7, 14):
            line(f"breadth{n}, hold {h}d", *run(s, top10, h=h))
    print("\n4/5. SIGNIFICANCE AND 2022 - breadth20, hold 7, BEAR gate (boot t is column 'boot t')")
    print(hdr)
    s = ls_signal(br[20], gates["bear"])
    for inst_lab, inst in (("alt index", alt), ("top-10", top10), ("BTC", btc)):
        x, pos = run(s, inst)
        line(f"{inst_lab}", x, pos)
        keep = x.index.year != 2022
        line(f"{inst_lab}, 2022 removed", x[keep], pos[keep])
    # 6. the trend book
    print("\n6. AGAINST THE TREND BOOK (triple, 10x guard, entry-sized, seed 0; RAW - no haircut)")
    from backtest.bull_boost import regimes
    from backtest.triple_capped import build, simulate
    bear = regimes()[1000]
    bear_ns = pd.DatetimeIndex(bear.index).as_unit("ns").asi8
    rows = build(max_units=7)
    curves = [simulate(rows, bear_ns, bear.to_numpy(bool), sd, 10.0)[0] for sd in range(5)]
    tr = pd.concat([c.pct_change() for c in curves], axis=1).mean(axis=1).fillna(0.0)
    tr.index = tr.index.normalize()
    x, _ = run(s, top10)
    j = pd.DataFrame({"trend": tr, "breadth": x}).dropna()
    j = j[j.index >= START]
    print(f"  daily correlation, trend vs breadth sleeve: {j.trend.corr(j.breadth):+.2f} over {len(j)} days")
    wk = (1 + j).resample("W").prod() - 1
    print(f"  weekly correlation: {wk.trend.corr(wk.breadth):+.2f}")
    mo = (1 + j).resample("ME").prod() - 1
    rg = reg.reindex(mo.index, method="ffill")
    # a month's regime = the regime most of its days carried
    dom = reg.groupby(reg.index.to_period("M")).agg(lambda v: v.value_counts().index[0])
    mo["regime"] = [dom.get(p, "chop") for p in mo.index.to_period("M")]
    print("  mean monthly return by the month's dominant regime (%, RAW):")
    for r_ in ("bull", "chop", "bear"):
        g = mo[mo.regime == r_]
        print(f"    {r_:<5} n {len(g):>3}   trend {g.trend.mean()*100:+7.2f}   breadth sleeve "
              f"{g.breadth.mean()*100:+6.2f}   trend + 1x sleeve {(g.trend + g.breadth).mean()*100:+7.2f}")
    for k in (0.0, 0.5, 1.0):
        comb = j.trend + k * j.breadth
        eq = (1 + comb).cumprod()
        yrs = len(comb) / 365
        m = (1 + comb).resample("ME").prod() - 1
        print(f"  trend + {k:.1f} x sleeve: CAGR {((eq.iloc[-1]) ** (1 / yrs) - 1) * 100:+.0f}%/yr RAW, "
              f"DD {(1 - eq / eq.cummax()).max()*100:.0f}%, months up {(m > 0).mean()*100:.0f}%, "
              f"worst month {m.min()*100:+.1f}%")


if __name__ == "__main__":
    main()

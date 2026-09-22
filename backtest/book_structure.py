"""FOUR UNTESTED STRUCTURAL CHOICES IN THE DEPLOYED BOOK.

  1. PER-COIN POSITION CAP. A coin can hold three positions at once, one per sleeve, and the
     live book shows it: NEAR, DOT and LINK each occupy two of the twelve slots. Earlier
     tests capped slots by correlation cluster (corr_alloc.py) and by side (slot_split.py);
     NOBODY capped positions per coin across sleeves. If duplicates crowd out other coins,
     capping them diversifies the same twelve slots for free.
  2. PER-SLEEVE TRAIL WIDTH. The 20xATR trail was swept GLOBALLY and applied to all three
     sleeves. A 1h bar's ATR and a 12h bar's ATR describe different noise, so one multiplier
     for all three has never been justified.
  3. PER-SLEEVE RISK WEIGHT. Same: one risk per unit regardless of which sleeve fired.
  4. THE ENTRY BAND. bb(30, 1.5) was chosen in a 9-coin sweep with an uncapped exit, never
     re-swept on the deployed pyramid + blend + gate.

METHOD
    Deployed engine otherwise unchanged; own allocator so the per-coin cap and per-sleeve
    weights can be applied where they belong. 12 slots, 1000h BTC gate, compounded by close
    date, 3x hindsight haircut, tune/holdout as bear_date.py, and every figure averaged over
    5 random orderings of simultaneous entries.

    python -m backtest.book_structure
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402

RULES = ["1h", "4h", "12h"]
SEEDS = (0, 1, 2, 3, 4)
SLOTS = 12


def allocate(rows, bear, cut, half, coin_cap=None, rule_w=None, mult=1.0, seed=0):
    """The deployed allocator, plus an optional per-coin cap and per-sleeve risk weights."""
    rng = np.random.default_rng(seed)
    tie = rng.random(len(rows))
    o = [rows[i] for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
    f0 = blend.RISK / 100.0 * mult
    opens, pnl = [], []
    for r in o:
        t0 = r["t0"]
        if half == "tune" and t0 >= cut:
            continue
        if half == "hold" and t0 < cut:
            continue
        opens = [(u, c) for (u, c) in opens if u > t0]
        if len(opens) >= SLOTS:
            continue
        if coin_cap and sum(1 for (_u, c) in opens if c == r["coin"]) >= coin_cap:
            continue
        opens.append((r["t1"], r["coin"]))
        try:
            ib = bool(bear.asof(t0))
        except Exception:
            ib = False
        f = f0 * (blend.REGIME_MULT if ib else 1.0)
        if rule_w:
            f *= rule_w.get(r["rule"], 1.0)
        pnl.append((pd.Timestamp(r["t1"]), r["R"] * f))
    if len(pnl) < 30:
        return float("nan"), float("nan"), float("nan"), 0
    s = pd.Series([x[1] for x in pnl], index=pd.DatetimeIndex([x[0] for x in pnl]))
    daily = s.resample("D").sum()
    cur = np.cumprod(np.maximum(1 + daily.values, 0))
    pk = np.maximum.accumulate(np.maximum(cur, 1e-12))
    dd = float((1 - cur / pk).max() * 100)
    yrs = max((daily.index[-1] - daily.index[0]).days / 365.25, 0.1)
    cagr = (max(cur[-1], 1e-12) ** (1 / yrs) - 1) * 100
    hpm = ((1 + (cagr / blend.HINDSIGHT) / 100) ** (1 / 12) - 1) * 100
    return hpm, dd, float(daily.resample("ME").sum().min() * 100), len(pnl)


def stat(rows, bear, cut, half, **kw):
    out = [allocate(rows, bear, cut, half, seed=sd, **kw) for sd in SEEDS]
    a = np.array([[x[0], x[1], x[2], x[3]] for x in out], dtype=float)
    return a[:, 0].mean(), a[:, 1].mean(), a[:, 2].mean(), a[:, 3].mean()


def main():
    from backtest.engine_variants import BASE_RULES, rows_for
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    base = rows_for(BASE_RULES)
    print(f"tune < {cut:%Y-%m-%d} <= holdout | 5 orderings averaged\n")
    hdr = (f"  {'variant':<32}{'taken':>7}{'TUNE':>8}{'DD':>5}{'HOLD':>8}{'DD':>5}{'worst':>8}")

    def show(lab, rows, **kw):
        t = stat(rows, bear, cut, "tune", **kw); h = stat(rows, bear, cut, "hold", **kw)
        print(f"  {lab:<32}{h[3]:>7.0f}{t[0]:>+7.2f}%{t[1]:>4.0f}%{h[0]:>+7.2f}%{h[1]:>4.0f}%"
              f"{h[2]:>+7.1f}%")

    print("BASELINE"); print(hdr); show("deployed (no per-coin cap)", base)

    print("\n1. PER-COIN POSITION CAP across sleeves"); print(hdr)
    for cap in (1, 2):
        show(f"max {cap} position(s) per coin", base, coin_cap=cap)

    print("\n2. PER-SLEEVE TRAIL WIDTH (1h / 4h / 12h)"); print(hdr)
    for tr in ((30, 20, 12), (12, 20, 30), (40, 20, 10), (30, 25, 20), (10, 20, 40)):
        rows = []
        for rule, mult in zip(RULES, tr):
            rows += [r for r in rows_for([rule], trail=float(mult))]
        show(f"trail {tr[0]}x / {tr[1]}x / {tr[2]}x", rows)

    print("\n3. PER-SLEEVE RISK WEIGHT (1h / 4h / 12h)"); print(hdr)
    for w in ((0.5, 1.0, 1.5), (1.5, 1.0, 0.5), (0.25, 1.0, 2.0), (2.0, 1.0, 0.25)):
        show(f"risk x{w[0]} / x{w[1]} / x{w[2]}", base,
             rule_w={"1h": w[0], "4h": w[1], "12h": w[2]})

    print("\n4. ENTRY BAND re-swept on the deployed engine"); print(hdr)
    import backtest.shortside as SS
    for per, sd_ in ((20, 2.0), (30, 2.0), (50, 1.5), (30, 1.25)):
        SS.BB_P, SS.BB_STD = per, sd_
        import backtest.engine_variants as EV
        EV._CACHE.clear()
        show(f"bb({per}, {sd_})", rows_for(BASE_RULES))
    SS.BB_P, SS.BB_STD = 30, 1.5
    import backtest.engine_variants as EV
    EV._CACHE.clear()
    print("\n  a variant counts only if it beats the baseline on BOTH halves by >2%/mo")


if __name__ == "__main__":
    main()

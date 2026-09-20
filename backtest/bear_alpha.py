"""CAN WE EARN IN FALLING MARKETS? — the regime detector, then a bear-specific trade.

    python -m backtest.bear_alpha

PART 1: HOW WOULD WE KNOW A TREND IS COMING?
    We would not. The 1000-hour BTC average is a DETECTOR, not a predictor - it tells you
    a trend has already started, late and with whipsaw. The honest question is not "can we
    forecast the regime" but "is the detector we already run actually separating the good
    months from the bad ones?" That is measurable: tag every month by the regime state at
    its start, then look at what each bucket earned. If the gate has no discriminating
    power, its only job is size control and we should stop expecting more from it.

PART 2: A TRADE THAT NEEDS THE MARKET TO FALL
    19 of 19 indicator families found a long edge and none found a short edge, and the
    short sleeve measures +0.081R in bears - a hedge, not an engine. Every one of those
    tests shorted a coin outright, which means fighting crypto's unconditional upward
    drift and paying funding to do it.

    The untested shape is RELATIVE. In a falling market, high-beta alt-coins fall further
    than BTC. So: long BTC, short the alts, dollar-neutral. That is not a directional bet
    - the market factor cancels - so it does not need the market to fall, only for alts to
    fall FURTHER than BTC when it does. And it earns precisely where the main book cannot.

    The mirror is tested too (long alts / short BTC in bulls), because if dispersion is
    real it should work in both directions and be a rotation rather than a bear trade.

WHAT WOULD MAKE IT A MIRAGE
    BTC has massively outperformed alts through 2025-2026 - "alt season" never arrived.
    So a long-BTC/short-alts book will look excellent in the recent window for a reason
    that has nothing to do with bear markets. That is why every result below is split by
    regime AND by year, and why the bull-regime mirror is run: if the trade only works in
    one direction, it is a bet on the last two years of BTC dominance rather than a
    dispersion edge.

COSTS
    Weekly rebalance, 12bp round trip charged on measured turnover. Weekly rather than
    daily because a dispersion trade has no reason to be fast and turnover is what kills
    small edges - the lesson from taker_ls.py, where a 4-hour book paid more in fees than
    it earned gross.

REGISTERED PREDICTION (2026-09-20, before running)
    The bear leg (long BTC / short alts) works, and the bull mirror does NOT. That
    asymmetry would mean it is not a dispersion edge at all but a bet on BTC dominance
    rising, which has been true since 2024 and is one regime. I expect the by-year table
    to show it earning in 2022, 2025 and 2026 and losing in 2021 - the mirror image of the
    main book, which is what makes it interesting and also what makes it unproven.

    On Part 1, I expect the gate to discriminate but weakly: bull-start months carrying
    most of the profit, and bear-start months roughly flat rather than negative, because
    the gate already quarter-sizes them.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.bear_side import all_trades, sleeve_sided, SLOTS  # noqa: E402

FEE_BP = 12.0
ALTS = [c for c in blend.BOOK if c != "BTCUSDT"]


def deployed_monthly():
    """The deployed book's monthly returns, compounded by close date."""
    tr, _ = all_trades()
    bear = blend.btc_bear()
    f0 = blend.RISK / 100.0
    opens, rows = [], []
    for a_, b_, r, _ru, _c, side in tr:
        opens = [u for u in opens if u > a_]
        if len(opens) >= SLOTS:
            continue
        try:
            ib = bool(bear.asof(a_))
        except Exception:
            ib = False
        opens.append(b_)
        rows.append((pd.Timestamp(b_), r * f0 * (0.25 if ib else 1.0)))
    s = pd.Series([x[1] for x in rows],
                  index=pd.DatetimeIndex([x[0] for x in rows]))
    return s.resample("D").sum().resample("ME").sum() * 100


def panel():
    px = {}
    for c in blend.BOOK + ["BTCUSDT"]:
        d = blend.load(c)
        if d is None:
            continue
        s = pd.Series(d["close"].to_numpy(float), index=pd.DatetimeIndex(d["time"]))
        px[c] = s[~s.index.duplicated()].sort_index()
    return pd.DataFrame(px).dropna(how="all")


def dispersion(PX, bear, direction, freq="W"):
    """direction='bear': long BTC, short alts, only while the gate says bear.
    direction='bull': long alts, short BTC, only while it says bull."""
    g = PX.resample(freq).last().dropna(how="all")
    ret = g.pct_change().shift(-1)
    one_way = FEE_BP / 2.0 / 1e4
    have = [c for c in ALTS if c in g.columns]
    w_prev = pd.Series(0.0, index=g.columns)
    rows, turns = [], []
    for t in g.index:
        try:
            ib = bool(bear.asof(t))
        except Exception:
            ib = False
        on = ib if direction == "bear" else (not ib)
        w = pd.Series(0.0, index=g.columns)
        if on:
            alive = [c for c in have if np.isfinite(g.loc[t, c])]
            if len(alive) >= 4 and np.isfinite(g.loc[t, "BTCUSDT"]):
                sgn = 1.0 if direction == "bear" else -1.0
                w["BTCUSDT"] = 0.5 * sgn
                for c in alive:
                    w[c] = -0.5 * sgn / len(alive)
        r = ret.loc[t]
        gross = float((w * r.fillna(0.0)).sum())
        turn = float((w - w_prev).abs().sum())
        rows.append((t, gross, gross - turn * one_way, turn))
        w_prev = w
    d = pd.DataFrame(rows, columns=["t", "gross", "net", "turn"]).set_index("t")
    return d


def summarise(net, label, width=34):
    m = net.resample("ME").sum() * 100
    m = m[m != 0]
    if len(m) < 6:
        return f"  {label:<{width}} too few active months"
    cur = np.cumprod(1 + m.values / 100)
    dd = (1 - cur / np.maximum.accumulate(np.maximum(cur, 1e-12))).max() * 100
    geo = (max(cur[-1], 1e-12) ** (1 / len(m)) - 1) * 100
    return (f"  {label:<{width}}{len(m):>6}{geo:>+9.2f}%{m.median():>+10.2f}%"
            f"{100*(m>0).mean():>7.0f}%{dd:>8.1f}%")


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: the bear leg works and the bull mirror does NOT, which would make")
    print("it a bet on BTC dominance rather than a dispersion edge. Expect it to earn in")
    print("2022/2025/2026 and lose in 2021. On Part 1, the gate discriminates weakly.\n")

    bear = blend.btc_bear()
    m = deployed_monthly()
    start_state = pd.Series(
        [("bear" if bool(bear.asof(d - pd.Timedelta(days=30))) else "bull")
         for d in m.index], index=m.index)

    print("=" * 96)
    print("PART 1 — DOES THE REGIME GATE ACTUALLY SEPARATE GOOD MONTHS FROM BAD?")
    print("=" * 96)
    print(f"  {'month started in':<20}{'n':>5}{'mean':>10}{'median':>10}"
          f"{'up%':>7}{'sum of returns':>16}")
    for st in ("bull", "bear"):
        g = m[start_state == st]
        if not len(g):
            continue
        print(f"  {st:<20}{len(g):>5}{g.mean():>+9.1f}%{g.median():>+9.2f}%"
              f"{100*(g>0).mean():>6.0f}%{g.sum():>+15.1f}%")
    flips = int((start_state != start_state.shift()).sum())
    print(f"\n  the gate flipped state {flips} times in {len(m)} months "
          f"(every {len(m)/max(flips,1):.1f} months)")
    print("  It is a DETECTOR. It tells you a trend has begun, not that one is coming.")

    print("\n" + "=" * 96)
    print("PART 2 — LONG BTC / SHORT ALTS IN BEARS, AND THE BULL MIRROR")
    print("=" * 96)
    PX = panel()
    print(f"  {len(PX.columns)} coins, weekly rebalance, {FEE_BP}bp round trip on turnover\n")
    print(f"  {'book':<34}{'mths':>6}{'geo/mo':>10}{'median':>10}{'up%':>7}{'maxDD':>8}")
    print(summarise(deployed_monthly() / 100, "deployed crypto book (reference)"))
    res = {}
    for d_ in ("bear", "bull"):
        dd_ = dispersion(PX, bear, d_)
        res[d_] = dd_
        print(summarise(dd_.gross, f"{d_}: dispersion GROSS"))
        print(summarise(dd_.net, f"{d_}: dispersion net of fees"))
        print(f"       mean weekly turnover {dd_.turn.mean():.3f}")

    print("\n" + "=" * 96)
    print("PART 3 — BY YEAR: does it mirror the main book?")
    print("=" * 96)
    dm = deployed_monthly()
    print(f"  {'year':<8}{'deployed':>12}{'bear disp':>12}{'bull disp':>12}")
    for y in sorted(set(dm.index.year)):
        a = dm[dm.index.year == y].sum()
        b = res["bear"].net[res["bear"].net.index.year == y].sum() * 100
        c = res["bull"].net[res["bull"].net.index.year == y].sum() * 100
        print(f"  {y:<8}{a:>+11.1f}%{b:>+11.1f}%{c:>+11.1f}%")

    print("\n" + "=" * 96)
    print("VERDICT")
    print("=" * 96)
    bn = res["bear"].net.resample("ME").sum()
    bn = bn[bn != 0] * 100
    bl = res["bull"].net.resample("ME").sum()
    bl = bl[bl != 0] * 100
    bear_ok = len(bn) > 6 and np.cumprod(1 + bn.values / 100)[-1] > 1
    bull_ok = len(bl) > 6 and np.cumprod(1 + bl.values / 100)[-1] > 1
    corr = float(pd.DataFrame({"a": dm, "b": res["bear"].net.resample("ME").sum() * 100})
                 .dropna().corr().iloc[0, 1])
    print(f"  bear leg profitable net: {bear_ok}   bull mirror profitable net: {bull_ok}")
    print(f"  monthly correlation of the bear leg with the deployed book: {corr:+.3f}")
    if bear_ok and bull_ok:
        print("\n  BOTH DIRECTIONS WORK — that is a dispersion edge, not a dominance bet.")
        print("  Check the by-year table for concentration before believing it.")
    elif bear_ok:
        print("\n  ONLY the bear leg works. That is consistent with a bet on BTC dominance")
        print("  rising since 2024 rather than a dispersion edge. Read Part 3: if the")
        print("  profit is 2025-2026, this is one regime wearing a market-neutral costume.")
    else:
        print("\n  The bear leg does not pay net of fees. Alts falling harder than BTC is")
        print("  real as a fact and not harvestable at these costs and this turnover.")


if __name__ == "__main__":
    main()

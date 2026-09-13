"""CUTTING THE DRAWDOWN — which is the same problem as cutting the capital needed.

WHY THESE TWO ARE ONE PROBLEM
    The capital a configuration needs is

        floor = min_order x stop_fraction / risk_fraction / (1 - maxDD)

    so drawdown enters as 1/(1 - maxDD) and dominates everything else once it goes
    past ~80%. The 12-coin cheap book earns +12.18%/month at a 94.3% drawdown and
    needs $438. Hold the return and cut the drawdown to 60% and the SAME book needs
    about $62. Cut it to 50% and it needs $50.

    So "reduce the drawdown" and "start with less capital" are not two goals. They
    are one number.

THE OBSERVATION THAT PROMPTED THIS, FROM THE LIVE BOT
    Three shorts open on the Bitget demo, 2026-09-13 11:00 UTC:

        BTC  entry 77,122  stop 77,334  open +1.78R   stopped out = -0.85R
        XRP  entry 1.3609  stop 1.3692  open +2.13R   stopped out = -0.87R
        ETH  entry 2,485   stop 2,504   open +0.70R   stopped out = -1.00R

    Every one winning, every one still guaranteed to close at a LOSS. A 5xATR trail
    gives back 2.5R, so nothing is protected until +2.5R; a 20xATR trail on the long
    side gives back 10R. The gap between open profit and LOCKED profit is where the
    drawdown lives, and it has never been tested against.

FOUR CONTROLS, ALL UNTESTED IN THIS PROJECT
    A  BREAKEVEN STOP. Move the stop to entry once the trade reaches +NR, then let
       the trail continue. Costs some runners - a trade that would have gone to
       +30R can now be stopped at 0 - which is exactly the profit-cap failure mode,
       so this is the one to distrust.
    B  DRAWDOWN THROTTLE. Halve (or zero) risk while equity is more than X% below
       its peak. Cannot cost anything in a rising market and mechanically shortens
       the bottom of a decline. The classic objection: it also delays the recovery,
       because recoveries start at the bottom.
    C  VOLATILITY TARGETING. Scale each trade's risk by target_vol / vol_at_entry,
       so quiet periods get more size and violent ones less. This is the standard
       institutional drawdown control and the single most likely of the four to
       work. Never tried here.
    D  A + B together.

    Each is measured against the SAME baseline on the SAME engine, and every row
    reports the CAPITAL FLOOR, because a control that cuts return by 20% and
    drawdown by half has made the strategy cheaper to run and is therefore a win,
    which a CAGR-only table would call a loss.

REGISTERED PREDICTION (2026-09-13, before running)
    C (vol targeting) helps most: maxDD down 10-20 points for a small return cost.
    B helps drawdown and costs little. A cuts drawdown AND cuts return hard enough
    to be roughly neutral, because it truncates the runners this strategy lives on
    - the same mechanism as the profit cap, which cost 8 of 11 trend families.
    I expect at least one row to beat the baseline on floor. If none do, the 94%
    drawdown is structural and the capital answer stays $438/$1,140.

    python -m backtest.ddcontrol
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.convex import run_uncapped  # noqa: E402
from backtest.mass_search import fetch  # noqa: E402
from backtest.pyramid import run_pyramid  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from backtest.small_book import LONG_TRAIL, SHORT_TRAIL, stop_fraction  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402

FEE_BP = 12.0
MAX_UNITS, ADD_EVERY = 5, 2.0
HINDSIGHT = 3.0
SLOTS = 8

# The 12 most liquid MEXC contracts with a minimum order under $2.50, from
# backtest/cheap_wide.py. Reputable alts, not microcaps - the cheapness is a
# contract-step property, not a quality one.
BOOK = ["XRPUSDT", "SUIUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT",
        "ENAUSDT", "SHIBUSDT", "WLDUSDT", "NEARUSDT", "DOTUSDT", "ARBUSDT"]
MIN_ORDER = {"XRPUSDT": 1.338, "SUIUSDT": 0.708, "ADAUSDT": 0.203,
             "LINKUSDT": 1.130, "AVAXUSDT": 0.729, "LTCUSDT": 0.535,
             "ENAUSDT": 1.388, "SHIBUSDT": 0.005, "WLDUSDT": 0.388,
             "NEARUSDT": 2.282, "DOTUSDT": 0.100, "ARBUSDT": 0.137}
_D: dict = {}


def load(c):
    if c not in _D:
        try:
            _D[c] = fetch(c, "1h", 2400)
        except Exception:
            _D[c] = None
    return _D[c]


def trades_for(df, breakeven_at=0.0):
    """(entry_time, exit_time, R, side, atr_pct_at_entry) per position.

    atr_pct at ENTRY is carried so volatility targeting can scale that trade's
    risk without look-ahead - it is ATR(14)/close at bar i-1, the same bar the stop
    is sized from.
    """
    t = df["time"].to_numpy()
    ap = (atr_ind(df, 14) / df["close"]).to_numpy(float)
    out = []
    R, idx, _u, held = run_pyramid(df, signals(df, "long", "all"), sl_mult=2.0,
                                   trail=LONG_TRAIL, max_units=MAX_UNITS,
                                   add_every=ADD_EVERY, fee_bp=FEE_BP,
                                   breakeven_at=breakeven_at)
    for r, i, h in zip(R, idx, held):
        e = max(int(i) - int(h), 0)
        out.append((t[e], t[int(i)], float(r), "L", ap[max(e - 1, 0)]))
    # mode stays trail_atr and the breakeven arrives as a FLOOR (be_at), matching
    # what run_pyramid does on the long sleeve. Using run_uncapped's mode=
    # "breakeven" here instead suspends the trail until the threshold is met, which
    # is a different rule - it made shorts hold far longer and dropped the trade
    # count BELOW baseline as the threshold rose, contaminating the first pass.
    R, idx, bars, _d = run_uncapped(
        df, signals(df, "short", "all"), sl_mult=2.0, fee_bp=FEE_BP,
        mode="trail_atr", trail=SHORT_TRAIL, be_at=breakeven_at)
    for r, i, b in zip(R, idx, bars):
        e = max(int(i) - int(b), 0)
        out.append((t[e], t[int(i)], float(r), "S", ap[max(e - 1, 0)]))
    return out


def portfolio(book, risk, *, breakeven_at=0.0, dd_throttle=0.0,
              throttle_factor=0.5, vol_target=0.0, vol_clip=(0.25, 2.0)):
    """One equity curve. Controls B and C act HERE, on position size; control A
    acts inside the exit engine and changes R itself.

    THE THROTTLE USES REALIZED EQUITY ONLY, and that distinction is the whole
    result. The first version of this function walked trades in ENTRY order and
    compounded each trade's R the moment it was reached, then read that running
    equity to decide whether to throttle. With 8 concurrent slots, a trade entered
    later was therefore sized using the OUTCOME of trades that had entered earlier
    but had not yet exited - information that did not exist at the time. The
    throttle could "know" a still-open position was going to lose and cut size just
    before the damage landed. It reported a 72.4% drawdown and a $90 capital floor.

    Correct treatment: keep trades pending until their EXIT time, and let the
    throttle see only equity from positions that have actually closed. That is what
    a live bot sees - unrealized P&L on open positions is not equity it can size
    from, because the trade is not finished.
    """
    tr = []
    for c in book:
        df = load(c)
        if df is None or len(df) < 3000:
            continue
        tr += trades_for(df, breakeven_at)
    if len(tr) < 30:
        return None
    tr.sort(key=lambda x: x[0])
    base_f = risk / 100.0
    r_eq, r_peak = 1.0, 1.0          # REALIZED equity and its peak
    pending: list[tuple] = []         # (exit_time, contribution) not yet settled
    settled: list[tuple] = []         # (exit_time, contribution) for the curve
    opens = []
    taken, throttled, ruined = 0, 0, False
    for a, b, r, side, apct in tr:
        # settle everything that closed before this entry, in exit order
        if pending:
            due = [p for p in pending if p[0] <= a]
            if due:
                pending = [p for p in pending if p[0] > a]
                for xt, contrib in sorted(due):
                    if not ruined:
                        r_eq *= (1 + contrib)
                        r_peak = max(r_peak, r_eq)
                        if r_eq <= 0.01:
                            r_eq, ruined = 0.0, True
                    settled.append((xt, r_eq))
        opens = [u for u in opens if u > a]
        if len(opens) >= SLOTS:
            continue
        opens.append(b)
        taken += 1
        f = base_f
        # C: volatility targeting. Quiet coin -> larger size, violent coin ->
        # smaller, so each trade carries comparable RISK rather than comparable
        # nominal exposure. Clipped, because an unclipped ratio on a near-zero ATR
        # would size a position to infinity.
        if vol_target > 0 and np.isfinite(apct) and apct > 0:
            f *= float(np.clip(vol_target / apct, *vol_clip))
        # B: drawdown throttle, decided on REALIZED equity against its realized
        # peak - both knowable at this instant.
        if dd_throttle > 0 and r_eq < r_peak * (1 - dd_throttle):
            f *= throttle_factor
            throttled += 1
        pending.append((b, r * f))
    for xt, contrib in sorted(pending):          # settle the tail
        if not ruined:
            r_eq *= (1 + contrib)
            r_peak = max(r_peak, r_eq)
            if r_eq <= 0.01:
                r_eq, ruined = 0.0, True
        settled.append((xt, r_eq))
    if taken < 30 or len(settled) < 30:
        return None
    settled.sort()
    times = [s[0] for s in settled]
    cur = np.asarray([s[1] for s in settled])
    pk = np.maximum.accumulate(np.maximum(cur, 1e-12))
    dd = float((1 - cur / pk).max() * 100)
    ts = pd.DatetimeIndex(times)
    yrs = max((ts[-1] - ts[0]).days / 365.25, 1e-9)
    cagr = (max(cur[-1], 0.0) ** (1 / yrs) - 1) * 100 if not ruined else -100.0
    hc = cagr / HINDSIGHT if cagr > -100 else -100.0
    return dict(n=taken, throttled=throttled, cagr=cagr, dd=dd, ruined=ruined,
                hpm=((1 + hc / 100) ** (1 / 12) - 1) * 100 if hc > -100 else -100.0,
                raw_pm=((1 + cagr / 100) ** (1 / 12) - 1) * 100 if cagr > -100 else -100.0)


def floor_for(book, dd, risk):
    worst, wc = 0.0, None
    for c in book:
        df = load(c)
        if df is None:
            continue
        need = MIN_ORDER[c] * stop_fraction(df) / (risk / 100.0)
        if need > worst:
            worst, wc = need, c
    if dd >= 99.0 or worst == 0:
        return float("nan"), wc
    return worst / (1 - dd / 100.0), wc


def main():
    ap = argparse.ArgumentParser()
    ap.parse_args()
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: vol targeting helps most; breakeven roughly")
    print("neutral because it truncates runners. If nothing beats the baseline on")
    print("FLOOR, the 94% drawdown is structural.\n")
    print(f"book: {len(BOOK)} cheap contracts, {SLOTS} slots, fee {FEE_BP}bp")
    print("every row reports the CAPITAL FLOOR - that is the scoreboard, not CAGR\n")

    variants = [
        ("baseline", dict()),
        ("A  breakeven @1.0R", dict(breakeven_at=1.0)),
        ("A  breakeven @2.0R", dict(breakeven_at=2.0)),
        ("A  breakeven @3.0R", dict(breakeven_at=3.0)),
        # Extended to 4/5/6R because the 1R->2R->3R results fell monotonically in
        # drawdown with NO return cost. A monotone response across many parameter
        # values is far stronger evidence than one good cell in a 24-cell grid, and
        # it also shows where the trend turns - if it never turns, the parameter is
        # doing something suspicious rather than something real.
        ("A  breakeven @4.0R", dict(breakeven_at=4.0)),
        ("A  breakeven @5.0R", dict(breakeven_at=5.0)),
        ("A  breakeven @6.0R", dict(breakeven_at=6.0)),
        ("B  throttle -25% x0.5", dict(dd_throttle=0.25)),
        ("B  throttle -40% x0.5", dict(dd_throttle=0.40)),
        ("B  throttle -25% STOP", dict(dd_throttle=0.25, throttle_factor=0.0)),
        ("C  vol target 2.0%", dict(vol_target=0.020)),
        ("C  vol target 2.5%", dict(vol_target=0.025)),
        ("C  vol target 3.0%", dict(vol_target=0.030)),
        ("D  BE@2R + throttle", dict(breakeven_at=2.0, dd_throttle=0.25)),
        ("D  vol 2.5% + throttle", dict(vol_target=0.025, dd_throttle=0.25)),
    ]
    print("=" * 116)
    print(f"{'variant':<24} {'risk%':>6} {'n':>6} {'raw /mo':>9} "
          f"{'HONEST /mo':>11} {'DD':>7} {'floor $':>9} {'vs base':>9}  note")
    print("=" * 116)
    rows = []
    for risk in (0.13, 0.30):
        base = None
        for tag, kw in variants:
            d = portfolio(BOOK, risk, **kw)
            if not d:
                print(f"{tag:<24} {risk:>6.2f} (no result)")
                continue
            fl, wc = floor_for(BOOK, d["dd"], risk)
            if tag == "baseline":
                base = (fl, d)
            delta = ""
            if base and tag != "baseline" and np.isfinite(fl) and np.isfinite(base[0]):
                delta = f"{fl / base[0] - 1:+.0%}"
            note = ""
            if d["hpm"] > 10.0 and not d["ruined"]:
                note = "** >10%/mo **"
            if d["ruined"]:
                note = "RUIN"
            rows.append((risk, tag, fl, d))
            print(f"{tag:<24} {risk:>6.2f} {d['n']:>6} {d['raw_pm']:>+8.2f}% "
                  f"{d['hpm']:>+10.2f}% {d['dd']:>6.1f}% {fl:>9,.0f} "
                  f"{delta:>9}  {note}", flush=True)
        print()

    print("=" * 116)
    print("CHEAPEST CONFIGURATIONS THAT STILL CLEAR +10%/MONTH")
    print("=" * 116)
    hits = [r for r in rows if r[3]["hpm"] > 10.0 and not r[3]["ruined"]
            and np.isfinite(r[2])]
    if not hits:
        print("  none. Every drawdown control that cut the drawdown enough to")
        print("  matter also cut the return below the target.")
    else:
        hits.sort(key=lambda r: r[2])
        for risk, tag, fl, d in hits:
            print(f"  ${fl:>8,.0f}  {tag:<24} {risk:.2f}%/unit  "
                  f"{d['hpm']:+.2f}%/month  DD {d['dd']:.1f}%")
        best = hits[0]
        print(f"\n  BEST: ${best[2]:,.0f} — {best[1]} at {best[0]:.2f}%/unit, "
              f"{best[3]['hpm']:+.2f}%/month, DD {best[3]['dd']:.1f}%")
    print("\nBEST DRAWDOWN AT ANY RETURN — for the record, since a lower floor is")
    print("worth more than a higher return to an account that cannot fund itself")
    print("=" * 116)
    for risk, tag, fl, d in sorted(rows, key=lambda r: r[3]["dd"])[:6]:
        print(f"  DD {d['dd']:>5.1f}%  floor ${fl:>8,.0f}  {tag:<24} "
              f"{risk:.2f}%/unit  {d['hpm']:+.2f}%/month")


if __name__ == "__main__":
    main()

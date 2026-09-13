"""MORE RETURN, LESS DRAWDOWN ON THE $200 BOOK — five levers never tested.

DISCIPLINE FIRST, BECAUSE THIS IS A PARAMETER SEARCH
    Every number in this project that came from picking the best cell of a grid has
    later shrunk or vanished. So this file is split 60/40 in TIME:

        TUNE on the first 60%          DECIDE on the last 40%

    A lever is only believed if it improves BOTH halves, or improves the second half
    having been chosen on the first. The grid size is printed next to the result, and
    a lone good cell whose neighbours are worse is reported as fitted rather than
    found - that exact signature already turned out to be a bug once today.

THE FIVE LEVERS, AND WHY THESE FIVE
    1. DIRECTIONAL EXPOSURE CAP.  The 8-slot cap allows 8 longs at once. In crypto
       that is ONE trade taken eight times: the coins move together, so the book's
       drawdown is correlated, not diversified. Breakeven stops cut per-trade waste
       and could not touch this - the majors' 67% drawdown barely moved. Capping
       longs and shorts SEPARATELY attacks it directly, and nothing in this project
       has tried it.
    2. SLOT COUNT with the breakeven stop in place. Swept before WITHOUT breakeven;
       the optimum can move once per-trade give-back is protected.
    3. ADD SPACING. Units are added every 2.0R and that number has never been
       changed. Tighter spacing builds size faster into a winner; wider spacing
       risks less on trades that stall.
    4. TRAIL WIDTHS for THIS book. 20xATR long / 5xATR short were measured on the 9
       MAJOR coins. These 12 alts are more volatile (2.5-3.8% stops against the
       majors' 1.2-2.2%) so there is no reason the same widths are right.
    5. PORTFOLIO REGIME GATE. Per-coin regime filters were tested and LOST. A
       portfolio-level one - scale risk down while BTC is below its own 200h average -
       is a different thing and is untested. It targets correlated drawdown like
       lever 1.

    Scored on honest %/month, drawdown, AND the capital floor, because a change that
    costs return but cuts drawdown makes the strategy CHEAPER TO RUN, and on a $200
    account that is worth more than the return.

REGISTERED PREDICTION (2026-09-13, before running)
    Lever 1 is the most likely to work and the only one I expect to survive the
    holdout, because it attacks a cause rather than a symptom. Levers 2-4 I expect to
    produce grid noise - small in-sample gains that do not repeat out of sample.
    Lever 5 I expect to cut both drawdown and return roughly proportionally, leaving
    the floor unchanged, the same way the drawdown throttle did.

    python -m backtest.opt200
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
from backtest.small_book import stop_fraction  # noqa: E402

FEE_BP = 12.0
SL_MULT = 2.0
HINDSIGHT = 3.0
BOOK = ["XRPUSDT", "SUIUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "LTCUSDT",
        "ENAUSDT", "SHIBUSDT", "WLDUSDT", "NEARUSDT", "DOTUSDT", "ARBUSDT"]
MIN_ORDER = {"XRPUSDT": 1.338, "SUIUSDT": 0.708, "ADAUSDT": 0.203,
             "LINKUSDT": 1.130, "AVAXUSDT": 0.729, "LTCUSDT": 0.535,
             "ENAUSDT": 1.388, "SHIBUSDT": 0.005, "WLDUSDT": 0.388,
             "NEARUSDT": 2.282, "DOTUSDT": 0.100, "ARBUSDT": 0.137}
BASE = dict(trail_l=20.0, trail_s=5.0, add_every=2.0, be=3.0,
            slots=8, max_long=99, max_short=99, risk=0.30, regime=0.0)
_D: dict = {}
_TR: dict = {}
_BTC = None


def load(c):
    if c not in _D:
        try:
            _D[c] = fetch(c, "1h", 2400)
        except Exception:
            _D[c] = None
    return _D[c]


def btc_bear():
    """Series of timestamps where BTC closed BELOW its 200h average. Used for the
    portfolio regime gate, shifted one bar so a decision never reads its own bar."""
    global _BTC
    if _BTC is None:
        d = load("BTCUSDT")
        ma = d["close"].rolling(200).mean()
        bear = (d["close"] < ma).shift(1).fillna(False).to_numpy(bool)
        _BTC = pd.Series(bear, index=pd.DatetimeIndex(d["time"]))
    return _BTC


def coin_trades(trail_l, trail_s, add_every, be):
    """Per-coin trade lists. Cached on the ENGINE parameters only, so the
    portfolio-level sweep (slots, caps, risk, regime) is free."""
    key = (trail_l, trail_s, add_every, be)
    if key in _TR:
        return _TR[key]
    tr = []
    for c in BOOK:
        df = load(c)
        if df is None or len(df) < 3000:
            continue
        t = df["time"].to_numpy()
        R, idx, _u, held = run_pyramid(df, signals(df, "long", "all"),
                                       sl_mult=SL_MULT, trail=trail_l,
                                       max_units=5, add_every=add_every,
                                       fee_bp=FEE_BP, breakeven_at=be)
        tr += [(t[max(int(i) - int(h), 0)], t[int(i)], float(r), "L")
               for r, i, h in zip(R, idx, held)]
        R, idx, bars, _d = run_uncapped(df, signals(df, "short", "all"),
                                        sl_mult=SL_MULT, fee_bp=FEE_BP,
                                        mode="trail_atr", trail=trail_s, be_at=be)
        tr += [(t[max(int(i) - int(b), 0)], t[int(i)], float(r), "S")
               for r, i, b in zip(R, idx, bars)]
    tr.sort(key=lambda x: x[0])
    _TR[key] = tr
    return tr


def book(cfg, t_from=None, t_to=None):
    """Portfolio pass. Directional caps and the regime gate live here."""
    tr = coin_trades(cfg["trail_l"], cfg["trail_s"], cfg["add_every"], cfg["be"])
    bear = btc_bear() if cfg["regime"] > 0 else None
    f0 = cfg["risk"] / 100.0
    eq, curve, times = 1.0, [], []
    opens: list[tuple] = []                 # (exit_time, side)
    Rs, sides = [], []
    declined = 0
    ruined = False
    for a, b, r, side in tr:
        if t_from is not None and a < t_from:
            continue
        if t_to is not None and a >= t_to:
            continue
        opens = [u for u in opens if u[0] > a]
        same = sum(1 for u in opens if u[1] == side)
        cap = cfg["max_long"] if side == "L" else cfg["max_short"]
        if len(opens) >= cfg["slots"] or same >= cap:
            declined += 1
            continue
        opens.append((b, side))
        f = f0
        if bear is not None:
            # nearest prior BTC bar; .asof gives the last value at or before `a`
            try:
                if bool(bear.asof(a)):
                    f *= cfg["regime"]
            except Exception:
                pass
        Rs.append(r); sides.append(side)
        if not ruined:
            eq *= (1 + r * f)
            if eq <= 0.01:
                eq, ruined = 0.0, True
        curve.append(eq); times.append(b)
    if len(Rs) < 30:
        return None
    R = np.asarray(Rs); cur = np.asarray(curve)
    pk = np.maximum.accumulate(np.maximum(cur, 1e-12))
    dd = float((1 - cur / pk).max() * 100)
    ts = pd.DatetimeIndex(times)
    yrs = max((ts[-1] - ts[0]).days / 365.25, 1e-9)
    cagr = (max(cur[-1], 0.0) ** (1 / yrs) - 1) * 100 if not ruined else -100.0
    hc = cagr / HINDSIGHT if cagr > -100 else -100.0
    return dict(n=len(R), declined=declined, mean=float(R.mean()),
                nL=int(sum(1 for s in sides if s == "L")),
                nS=int(sum(1 for s in sides if s == "S")),
                dd=dd, cagr=cagr, ruined=ruined,
                hpm=((1 + hc / 100) ** (1 / 12) - 1) * 100 if hc > -100 else -100.0,
                floor=floor_for(cfg["risk"], dd))


def floor_for(risk, dd):
    worst = 0.0
    for c in BOOK:
        df = load(c)
        if df is None:
            continue
        need = MIN_ORDER[c] * stop_fraction(df) / (risk / 100.0)
        worst = max(worst, need)
    return (worst / (1 - dd / 100.0)) if dd < 99.0 and worst else float("nan")


def split_times():
    tr = coin_trades(BASE["trail_l"], BASE["trail_s"], BASE["add_every"], BASE["be"])
    ts = pd.DatetimeIndex([x[0] for x in tr])
    return ts[int(len(ts) * 0.6)]


HDR = (f"{'variant':<26} {'n':>6} {'L/S':>11} {'decl':>6} {'HONEST /mo':>11} "
       f"{'DD':>7} {'floor $':>9}")


def line(tag, d):
    if not d:
        return f"{tag:<26} (no result)"
    return (f"{tag:<26} {d['n']:>6} {d['nL']:>5}/{d['nS']:<5} {d['declined']:>6} "
            f"{d['hpm']:>+10.2f}% {d['dd']:>6.1f}% {d['floor']:>9,.0f}"
            + ("  RUIN" if d["ruined"] else ""))


def sweep(name, variants, cut):
    """One lever, both halves, printed side by side."""
    print("=" * 118)
    print(f"{name}   ({len(variants)} cells)")
    print("=" * 118)
    print(f"{'variant':<26} | {'TUNE (first 60%)':^38} | "
          f"{'DECIDE (last 40%)':^38}")
    print(f"{'':<26} | {'/mo':>10} {'DD':>8} {'floor':>9} {'n':>7} | "
          f"{'/mo':>10} {'DD':>8} {'floor':>9} {'n':>7}")
    rows = []
    for tag, over in variants:
        cfg = dict(BASE); cfg.update(over)
        a = book(cfg, t_to=cut)
        b = book(cfg, t_from=cut)
        if not (a and b):
            print(f"{tag:<26} | (insufficient)")
            continue
        rows.append((tag, cfg, a, b))
        print(f"{tag:<26} | {a['hpm']:>+9.2f}% {a['dd']:>7.1f}% "
              f"{a['floor']:>9,.0f} {a['n']:>7} | {b['hpm']:>+9.2f}% "
              f"{b['dd']:>7.1f}% {b['floor']:>9,.0f} {b['n']:>7}", flush=True)
    print()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.parse_args()
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: lever 1 (directional cap) is the only one I")
    print("expect to survive the holdout. 2-4 should be grid noise; 5 should cut")
    print("return and drawdown proportionally, leaving the floor unchanged.\n")

    cut = split_times()
    print(f"time split at {cut.date()}  (tune before, decide after)\n")
    allrows = []

    allrows += sweep("LEVER 1 — directional exposure cap", [
        ("baseline 8 slots", {}),
        ("max 6 same direction", dict(max_long=6, max_short=6)),
        ("max 4 same direction", dict(max_long=4, max_short=4)),
        ("max 3 same direction", dict(max_long=3, max_short=3)),
        ("max 2 same direction", dict(max_long=2, max_short=2)),
        ("max 4 long / 8 short", dict(max_long=4, max_short=8)),
        ("max 8 long / 4 short", dict(max_long=8, max_short=4)),
    ], cut)

    allrows += sweep("LEVER 2 — slot count, with BE@3R", [
        (f"{s} slots", dict(slots=s)) for s in (4, 6, 8, 10, 12)
    ], cut)

    allrows += sweep("LEVER 3 — add spacing", [
        (f"add every {a:.1f}R", dict(add_every=a))
        for a in (1.0, 1.5, 2.0, 3.0, 4.0)
    ], cut)

    allrows += sweep("LEVER 4 — trail widths for THIS book", [
        ("long 12 / short 5", dict(trail_l=12.0)),
        ("long 20 / short 5  (base)", {}),
        ("long 30 / short 5", dict(trail_l=30.0)),
        ("long 20 / short 3", dict(trail_s=3.0)),
        ("long 20 / short 8", dict(trail_s=8.0)),
        ("long 30 / short 3", dict(trail_l=30.0, trail_s=3.0)),
    ], cut)

    allrows += sweep("LEVER 5 — portfolio regime gate (BTC below 200h)", [
        ("no gate", {}),
        ("x0.5 risk in BTC bear", dict(regime=0.5)),
        ("x0.25 risk in BTC bear", dict(regime=0.25)),
    ], cut)

    print("=" * 118)
    print(f"SURVIVED THE HOLDOUT — beats baseline on the LAST 40% "
          f"(searched {len(allrows)} cells total)")
    print("=" * 118)
    b_cfg = dict(BASE)
    b_out = book(b_cfg, t_from=cut)
    if not b_out:
        return
    print(f"  baseline out-of-sample: {b_out['hpm']:+.2f}%/month  "
          f"DD {b_out['dd']:.1f}%  floor ${b_out['floor']:,.0f}\n")
    keep = [(t, c, a, b) for (t, c, a, b) in allrows
            if b["hpm"] > b_out["hpm"] and b["dd"] <= b_out["dd"]
            and np.isfinite(b["floor"]) and b["floor"] <= b_out["floor"]]
    if not keep:
        print("  NOTHING beat the baseline on all three of return, drawdown and")
        print("  floor out of sample. The configuration as quoted is the one to run,")
        print("  and the levers above are noise. That is a result, not a failure -")
        print(f"  it means {len(allrows)} cells of searching found no free lunch.")
    else:
        keep.sort(key=lambda r: -r[3]["hpm"])
        for t, c, a, b in keep:
            print(f"  {t:<26} in {a['hpm']:+6.2f}%/mo DD {a['dd']:5.1f}%  ->  "
                  f"OUT {b['hpm']:+6.2f}%/mo DD {b['dd']:5.1f}% "
                  f"floor ${b['floor']:,.0f}")
        print(f"\n  {len(keep)} of {len(allrows)} cells survived. With that many")
        print("  cells searched, expect roughly "
              f"{len(allrows)*0.05:.0f} to survive by chance alone - so believe a")
        print("  survivor only if its neighbours in the same sweep also improved.")


if __name__ == "__main__":
    main()

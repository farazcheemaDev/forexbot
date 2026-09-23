"""WHAT DOES EACH STARTING CAPITAL ACTUALLY RETURN? - the minimum order simulated, not assumed.

THE GAP THIS FILLS
    blend.run reports an implied capital "floor" from the widest stop and the biggest minimum
    order, but no backtest here has ever SIMULATED the rejections. That matters because the
    effect compounds both ways: a small account skips the signals whose unit is below the
    venue minimum, which changes which trades it holds, which changes how fast it grows, which
    changes how many future signals it can afford. Only a simulation captures that loop.

HOW THE MINIMUM IS MADE HONEST
    MEXC's minimum is one contract, i.e. a FIXED number of coins - so its dollar value tracked
    the coin's price. Using today's dollar minimum across all of history would understate it
    badly in 2021, when these coins cost several times more. So the step is recovered in COIN
    units from today's minimum and today's price, and the dollar minimum at each trade is
    step x that coin's price at that moment.

    unit notional = equity x risk% / stop fraction. Below the minimum, the signal is skipped
    and counted. Everything else is the deployed engine: 12 slots, 1000h gate, compounded by
    close date, 3x hindsight haircut, 5 orderings averaged.

    python -m backtest.small_capital
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
from backtest.engine_variants import BASE_RULES, rows_for  # noqa: E402

SEEDS = (0, 1, 2, 3, 4)
# MEXC minimum order value in USDT measured 2026-09-13 (blend_paper.MIN_ORDER)
MIN_ORDER_TODAY = {"XRPUSDT": 1.338, "SUIUSDT": 0.708, "ADAUSDT": 0.203,
                   "LINKUSDT": 1.130, "AVAXUSDT": 0.729, "LTCUSDT": 0.535,
                   "ENAUSDT": 1.388, "SHIBUSDT": 0.005, "WLDUSDT": 0.388,
                   "NEARUSDT": 2.282, "DOTUSDT": 0.100, "ARBUSDT": 0.137}


def price_maps():
    """close series per coin, and the contract step in COIN units from today's minimum."""
    px, step = {}, {}
    for c in blend.BOOK:
        d = blend.load(c)
        if d is None:
            continue
        s = pd.Series(d["close"].to_numpy(float), index=pd.DatetimeIndex(d["time"]))
        s = s[~s.index.duplicated()].sort_index()
        px[c] = s
        step[c] = MIN_ORDER_TODAY[c] / float(s.iloc[-1])      # coins per contract
    return px, step


def simulate(rows, bear, px, step, capital, risk_pct, slots, seed, t_from=None, t_to=None):
    """Equity path with the venue minimum enforced at every entry.

    Equity advances ONLY from trades that have already CLOSED by the time of each new signal -
    which is both what a real account does and what mistake #6 in doc 03 demands (an earlier
    version of this file compounded in entry order and read 85% drawdowns where the same book
    measures 57%). The minimum-order test therefore sees the equity the account really had."""
    rng = np.random.default_rng(seed)
    tie = rng.random(len(rows))
    o = [rows[i] for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
    eq = capital
    opens, pending, curve = [], [], [(None, capital)]
    taken = skipped = 0

    def realize(upto):
        nonlocal eq
        pending.sort(key=lambda x: x[0])
        while pending and pending[0][0] <= upto:
            t1, dr = pending.pop(0)
            eq = max(eq * (1 + dr), 0.0)
            curve.append((pd.Timestamp(t1), eq))

    for r in o:
        t0 = r["t0"]
        if t_from is not None and t0 < t_from:
            continue
        if t_to is not None and t0 >= t_to:
            continue
        realize(t0)                                     # bank what has closed
        opens = [u for u in opens if u > t0]
        if len(opens) >= slots:
            continue
        f = risk_pct / 100.0
        try:
            ib = bool(bear.asof(t0))
        except Exception:
            ib = False
        if ib:
            f *= blend.REGIME_MULT
        sf = max(r["sf"], 1e-6)
        unit = eq * f / sf                              # notional of one unit
        coin = r["coin"]
        p = px[coin].asof(pd.Timestamp(t0)) if coin in px else np.nan
        floor = step.get(coin, 0.0) * (p if np.isfinite(p) else 0.0)
        if unit < floor:
            skipped += 1
            continue
        opens.append(r["t1"])
        taken += 1
        pending.append((r["t1"], r["R"] * f))
    realize(pd.Timestamp("2100-01-01"))
    pts = [(t, e) for t, e in curve if t is not None]
    if len(pts) < 20:
        return dict(hpm=float("nan"), dd=float("nan"), taken=taken, skipped=skipped,
                    final=eq, ruined=True)
    s_ = pd.Series([e for _t, e in pts], index=pd.DatetimeIndex([t for t, _e in pts]))
    cur = s_.resample("D").last().ffill()
    dd = float((1 - cur / cur.cummax()).max() * 100)
    yrs = max((cur.index[-1] - cur.index[0]).days / 365.25, 0.1)
    cagr = (max(cur.iloc[-1] / capital, 1e-12) ** (1 / yrs) - 1) * 100
    hpm = ((1 + (cagr / blend.HINDSIGHT) / 100) ** (1 / 12) - 1) * 100 if cagr > -100 else -100.0
    # an account down 90% is destroyed for this strategy whatever the arithmetic says
    return dict(hpm=hpm, dd=dd, taken=taken, skipped=skipped, final=float(eq),
                ruined=bool(dd >= 90.0), curve=cur)


def avg(rows, bear, px, step, capital, risk_pct, slots, **kw):
    out = [simulate(rows, bear, px, step, capital, risk_pct, slots, sd, **kw) for sd in SEEDS]
    g = lambda k: float(np.nanmean([o[k] for o in out]))
    return dict(hpm=g("hpm"), dd=g("dd"), taken=g("taken"), skipped=g("skipped"),
                final=g("final"), ruin=float(np.mean([o["ruined"] for o in out])) * 100)


def main():
    bear = regimes()[1000]
    px, step = price_maps()
    rows = rows_for(BASE_RULES)
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    print("MEXC minimum in COIN units (recovered), and its dollar value then vs now:")
    for c in ("NEARUSDT", "ENAUSDT", "XRPUSDT", "SHIBUSDT"):
        s = px[c]
        print(f"  {c:<10} step {step[c]:.6g} coins | ${step[c]*float(s.iloc[0]):.2f} at "
              f"{s.index[0]:%Y-%m} -> ${MIN_ORDER_TODAY[c]:.3f} now")

    print(f"\n1. THE DEPLOYED CONFIG (0.30%/unit, 12 slots) BY STARTING CAPITAL")
    print(f"  {'capital':>9}{'skipped':>9}{'taken':>7}{'TUNE/mo':>9}{'HOLD/mo':>9}"
          f"{'DD':>6}{'ruin':>6}")
    for cap in (25, 50, 100, 200, 500, 1000, 5000):
        t = avg(rows, bear, px, step, cap, 0.30, 12, t_to=cut)
        h = avg(rows, bear, px, step, cap, 0.30, 12, t_from=cut)
        pct = h["skipped"] / max(h["skipped"] + h["taken"], 1) * 100
        print(f"  ${cap:>8,}{pct:>8.0f}%{h['taken']:>7.0f}{t['hpm']:>+8.2f}%{h['hpm']:>+8.2f}%"
              f"{h['dd']:>5.0f}%{h['ruin']:>5.0f}%")

    print(f"\n2. BEST CONFIG FOR A SMALL ACCOUNT - risk and slots swept per capital")
    print("   (fewer slots and more risk both make each unit BIGGER, so fewer rejections)")
    print(f"  {'capital':>9}{'risk':>6}{'slots':>6}{'skipped':>9}{'TUNE/mo':>9}{'HOLD/mo':>9}"
          f"{'DD':>6}{'ruin':>6}")
    for cap in (25, 50, 100, 200):
        best = None
        for risk in (0.30, 0.50, 1.00, 2.00):
            for slots in (4, 6, 12):
                h = avg(rows, bear, px, step, cap, risk, slots, t_from=cut)
                t = avg(rows, bear, px, step, cap, risk, slots, t_to=cut)
                if not np.isfinite(h["hpm"]):
                    continue
                score = min(t["hpm"], h["hpm"])          # judged on the WORSE half
                if h["ruin"] > 20 or h["dd"] > 80 or t["dd"] > 80:
                    continue          # an 80%+ drawdown account is unusable, whatever it earns
                if best is None or score > best[0]:
                    best = (score, risk, slots, t, h)
        if best:
            _s, risk, slots, t, h = best
            pct = h["skipped"] / max(h["skipped"] + h["taken"], 1) * 100
            print(f"  ${cap:>8,}{risk:>6.2f}{slots:>6}{pct:>8.0f}%{t['hpm']:>+8.2f}%"
                  f"{h['hpm']:>+8.2f}%{h['dd']:>5.0f}%{h['ruin']:>5.0f}%")
        else:
            print(f"  ${cap:>8,}   no configuration stays under an 80% drawdown")


if __name__ == "__main__":
    main()

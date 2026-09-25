"""DOES BITGET'S ORDER MINIMUM BITE THE BOOK? - the venue the bot actually trades.

WHY THIS EXISTS
    `small_capital.py` settled that "at $221 the venue minimum is not the binding constraint",
    and CLAUDE.md section 6 repeats it. That measurement used **MEXC's** minimums, because
    blend_paper.py was written against MEXC. The bot trades **BITGET**, and the two venues
    express the minimum differently:

      MEXC     a minimum ORDER VALUE, per coin, all of them between $0.10 and $2.28.
      Bitget   a $5 cost floor AND a minimum AMOUNT in coins, which for LINK is 1 whole LINK.

    At LINK's price that second rule is a ~$14 floor, twelve times the $1.13 the book assumes,
    and it is also the amount STEP, so every LINK order is rounded to a whole coin.

    wick_live.py already found this for the crash desk ("$7.50 a bid is under Bitget's minimum
    size for BTC, ETH, SOL, LINK, UNI, NEAR, AAVE and LIT"). Nobody checked the TREND book,
    which is the one holding money.

WHAT THE LIVE CODE ASSUMES, and why that is the actual bug
    combo_bot.py: MIN_ORDER = 5.0 flat, for every coin.
    blend_paper.py: MIN_ORDER = the MEXC table.
    Neither knows about an amount minimum. So both SIZE a LINK order Bitget will REFUSE, and
    the refusal arrives as an order failure rather than as a skipped signal - the book believes
    it holds a unit it does not hold.

THE METHOD, following small_capital.py so the two are comparable
    Bitget's minimum is a fixed number of COINS, so its dollar value tracks the coin's price
    through history. Using today's price everywhere understates it early and overstates it late.
    So the floor at each trade is  max(amount_min * price_at_that_trade, cost_min).
    Unit notional = equity * risk% / stop_fraction, one order per unit (an add is an order).

REGISTERED PREDICTIONS (before running, 2026-09-26)
    1. LINK is the only coin that matters; every other coin's amount minimum is worth under $8.
    2. Book-wide rejection at $221 is under 5%, so small_capital.py's HEADLINE survives - the
       minimum is still not the binding constraint on the book as a whole.
    3. But LINK's own rejection rate is over 10% at $221, and LINK is 1/12 of the book, so the
       right fix is a per-coin Bitget table, not a change of capital.
    4. Rounding to a whole LINK costs more than the rejections do, because it applies to EVERY
       LINK order rather than the small ones.

    python -m backtest.bitget_minimums
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.graveyard_rescore import rows  # noqa: E402

TRIPLE = dict(tight=True, time_stop=(100, 2.0), max_units=7)
EQUITIES = (100.0, 221.0, 300.0, 500.0)
MINS = Path(__file__).resolve().parents[1] / "logs" / "bitget_book_mins.json"
# MEXC, what the live code believes (blend_paper.MIN_ORDER)
MEXC = {"XRPUSDT": 1.338, "SUIUSDT": 0.708, "ADAUSDT": 0.203, "LINKUSDT": 1.130,
        "AVAXUSDT": 0.729, "LTCUSDT": 0.535, "ENAUSDT": 1.388, "SHIBUSDT": 0.005,
        "WLDUSDT": 0.388, "NEARUSDT": 2.282, "DOTUSDT": 0.100, "ARBUSDT": 0.137}


def prices():
    out = {}
    for c in blend.BOOK:
        d = blend.load(c)
        if d is not None:
            out[c] = pd.Series(d["close"].to_numpy(float),
                               index=pd.DatetimeIndex(d["time"])).sort_index()
    return out


def main():
    mk = json.load(open(MINS))
    px = prices()
    r = rows(**TRIPLE)
    print(f"{len(r)} trades, triple book | Bitget swap minimums fetched live | "
          f"floor = max(amount_min x price_THEN, cost_min)")
    print("compare: what combo_bot.py assumes is $5.00 flat; what blend_paper.py assumes is MEXC\n")

    # per-unit records: (coin, t0, notional_at_1_dollar_equity)
    rec = {c: [] for c in blend.BOOK}
    for x in r:
        c = x["coin"]
        if c not in rec:
            continue
        for ta in (x["adds"] or [x["t0"]]):
            rec[c].append((pd.Timestamp(ta), blend.RISK / 100.0 / max(x["sf"], 1e-6)))

    print(f"  {'coin':<7}{'min':>12}{'today $':>9}{'MEXC $':>8}{'x':>6}   rejected at equity")
    print(f"  {'':<7}{'':>12}{'':>9}{'':>8}{'':>6}   " + "".join(f"{e:>8.0f}" for e in EQUITIES))
    tot = {e: [0, 0] for e in EQUITIES}
    rounding = {}
    for c in blend.BOOK:
        b = c[:-4]
        d = mk[b]
        if not rec[c]:
            continue
        ts = pd.DatetimeIndex([t for t, _ in rec[c]])
        per = np.array([v for _, v in rec[c]])
        p_then = px[c].reindex(ts, method="ffill").to_numpy(float)
        floor = np.maximum(d["amin"] * p_then, d["cmin"])
        step = d["prec"] * p_then                       # dollar value of one amount step
        cells = ""
        for e in EQUITIES:
            n = per * e
            bad = int((n < floor).sum())
            tot[e][0] += bad
            tot[e][1] += len(n)
            cells += f"{bad / len(n) * 100:>7.1f}%"
        ok = per * 221.0 >= floor
        err = np.where(step > 0, np.abs(np.round(per * 221.0 / np.maximum(step, 1e-12))
                                        * step - per * 221.0) / (per * 221.0) * 100, 0.0)
        rounding[b] = float(np.median(err[ok])) if ok.any() else float("nan")
        ratio = d["eff"] / MEXC[c]
        print(f"  {b:<7}{d['amin']:>10g}c{d['amin'] * d['px']:>9.2f}{MEXC[c]:>8.2f}"
              f"{ratio:>5.0f}x   {cells}")
    print(f"  {'BOOK':<7}{'':>12}{'':>9}{'':>8}{'':>6}   "
          + "".join(f"{tot[e][0] / tot[e][1] * 100:>7.1f}%" for e in EQUITIES))

    print()
    print("  ROUNDING - median size error on the orders that ARE accepted, at $221")
    for b, v in sorted(rounding.items(), key=lambda kv: -kv[1])[:5]:
        print(f"    {b:<7}{v:>6.1f}%")
    print()
    print("  A rejection is a signal not taken. A rounding error is a position the wrong size,")
    print("  on EVERY order, and the book has no idea either happened - it sizes from MEXC.")


if __name__ == "__main__":
    main()


# --------------------------------------------------------------------------- part 2
def walk(r, bear, px, mk, seed, cap, floor_on, t_from=None, t_to=None):
    """ENTRY-SIZED compounding (rule 12), with Bitget's floor enforced at the signal.

    Every unit of a position carries the SAME notional - risk_usd / stop_fraction, and the stop
    fraction belongs to the position - so if the first unit clears the floor every add clears it
    too. The rejection is therefore per POSITION, which is what this models."""
    rng = np.random.default_rng(seed)
    tie = rng.random(len(r))
    o = [r[i] for i in sorted(range(len(r)), key=lambda i: (r[i]["t0"], tie[i]))]
    eq, open_, pts, skip, take = cap, [], [], 0, 0

    def bank(upto):
        nonlocal eq, open_
        keep = []
        for p in sorted(open_, key=lambda q: q["t1"]):
            if p["t1"] <= upto:
                eq = max(eq + p["dpr"] * p["R"], 0.0)
                pts.append((p["t1"], eq))
            else:
                keep.append(p)
        open_ = keep

    for x in o:
        t0 = pd.Timestamp(x["t0"])
        if (t_from is not None and t0 < t_from) or (t_to is not None and t0 >= t_to):
            continue
        bank(t0)
        if len(open_) >= 12:
            continue
        try:
            ib = bool(bear.asof(t0))
        except Exception:
            ib = False
        f = blend.RISK / 100.0 * (blend.REGIME_MULT if ib else 1.0)
        sf = max(x["sf"], 1e-6)
        if floor_on:
            c = x["coin"]
            d = mk.get(c[:-4])
            p = px[c].asof(t0) if c in px else np.nan
            if d and np.isfinite(p):
                if eq * f / sf < max(d["amin"] * float(p), d["cmin"]):
                    skip += 1
                    continue
        take += 1
        open_.append(dict(x, t1=pd.Timestamp(x["t1"]), dpr=f * eq))
    bank(pd.Timestamp("2100-01-01"))
    if len(pts) < 20:
        return None
    s = pd.Series([p[1] for p in pts], index=pd.DatetimeIndex([p[0] for p in pts]))
    c = s.resample("D").last().ffill()
    yrs = max((c.index[-1] - c.index[0]).days / 365.25, 0.1)
    cagr = max(float(c.iloc[-1] / cap), 1e-12) ** (1 / yrs) - 1
    hc = cagr / blend.HINDSIGHT
    return dict(hpm=((1 + hc) ** (1 / 12) - 1) * 100 if hc > -1 else -100.0,
                dd=float((1 - c / c.cummax()).max() * 100), skip=skip, take=take)


def part2():
    mk = json.load(open(MINS))
    px = prices()
    r = rows(**TRIPLE)
    from backtest.bear_side import sleeve_sided
    from backtest.bull_boost import regimes
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    seeds = tuple(range(10))
    print()
    print("PART 2 - WHAT IT COSTS. Bitget's floor ON vs OFF, paired within ordering.")
    print(f"  entry-sized, 12 slots, 3x haircut, tune < {cut:%Y-%m-%d} <= holdout, 10 orderings")
    print(f"  {'capital':>8}{'skipped':>9}{'TUNE d':>9}{'t':>7}{'w':>6}{'HOLD d':>9}{'t':>7}{'w':>6}"
          f"{'DD off':>8}{'DD on':>7}")
    for cap in EQUITIES:
        line, sk = "", []
        for win, kw in (("tune", dict(t_to=cut)), ("hold", dict(t_from=cut))):
            a = [walk(r, bear, px, mk, s, cap, True, **kw) for s in seeds]
            b = [walk(r, bear, px, mk, s, cap, False, **kw) for s in seeds]
            d = np.array([x["hpm"] - y["hpm"] for x, y in zip(a, b) if x and y])
            se = d.std(ddof=1) / len(d) ** 0.5
            line += f"{d.mean():>+8.2f}%{d.mean() / se if se else np.nan:>+7.2f}{(d > 0).sum():>4}/{len(d)}"
            if win == "hold":
                sk = [x["skip"] / max(x["skip"] + x["take"], 1) * 100 for x in a if x]
                dof = float(np.mean([y["dd"] for y in b if y]))
                don = float(np.mean([x["dd"] for x in a if x]))
        print(f"  {cap:>7.0f}${np.mean(sk):>8.1f}%{line}{dof:>7.0f}%{don:>6.0f}%")
    print()
    print("  d = floor ON minus floor OFF, in %/month. Negative means the venue costs return.")


if __name__ == "__main__":
    main()
    part2()

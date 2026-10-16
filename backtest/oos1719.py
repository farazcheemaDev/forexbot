"""THE FROZEN MACHINE ON YEARS IT NEVER SAW - Binance spot 2017-08 .. 2019-12 (2026-10-16)

The user: "there must be a way that gives us a good confidence percentage - nobody can wait this much". Every book in
the final machine was built and tuned on Binance PERPS, 2019-09 on (most coins 2020+). This runs the SAME code, rules
and parameters - nothing re-tuned - on Binance SPOT 2017-08 .. 2019-12 (backtest/spot_fetch.py): the 2017 mania top and
the 2018 bear (-85%), a regime none of the books has seen. Point-in-time universes from spot volume, dead coins in.
HOW    the data folders the engines read (wide_book.DATA, capitulation_wide.PERPS, market_neutral.DATA,
       carry_check.DATA) and every cache folder are pointed at spot1719 / logs/oos1719_cache BEFORE anything loads, in this
       process (the trend engine is run in-process: wide_book.build's worker processes would re-import the perp paths).
BOOKS  (the final machine's weights)
    trend    the deployed MAIN trend book (bb_break 30/1.5, 3 sleeves, 5-unit pyramid, shorts) on the PIT top-12 by spot
             volume - wide_book.one_coin, sized at ENTRY (mtm_sizing.simulate 'realised', rule 12) with BTC's own 1000h
             gate. First run used bull_boost.evaluate (daily-sum compounding): 2019 read +575%, ~2x inflated. NOT the triple on the 12
             hand-picked coins: 8 of those 12 did not exist before 2020. PIT, so no hindsight haircut.            x1
    MN       market-neutral, half 30-day momentum / half RSI(14), +50% short exit (final_machine's mn_blend). Shorts
             on spot prices: a price-behaviour test (Binance had no perps then).                                  x1
    daily    Bollinger(30, 1.5) on daily bars, out under the 20-day mean (final_books DAILY), 8 slots           x0.5
    capit2   coin down >= 10% in 24h + limit 2% under, 8 slots at 2x (final_books CAPIT2 since 2026-10-16)      x1
    NOT TESTABLE on spot: funding carry (no funding before perps); funding is charged as ZERO on every book here
    (it cost the trend book ~21% of its long profit on perps - this flatters longs a little). Already tested out of
    sample elsewhere: the bear sleeve on 2018-19 (breadth_oos.py: +21.7%/yr vs -5.0% always-long). Crash bids: not run.
REPORTED  per book and combined: CAGR, the biggest fall, the worst month, months up, by year (2017 part / 2018 / 2019).

REGISTERED BEFORE ANY SPOT DATA WAS READ (2026-10-16)
    1. capit2 at 2x makes money over the period (2018 is full of capitulations).
    2. The daily book makes money over the period on late 2017, and loses in 2018.
    3. The MN blend makes money (momentum long / short worked in alt bears on perps).
    4. The trend book makes money over the period, and loses in 2018 (it is a bull amplifier).
    5. Combined: CAGR > 0, biggest fall under 60%, calendar 2018 no worse than -30%.
    PASS LINE (the edge exists outside the years it was built on): combined CAGR > 0 AND >= 3 of the 4 books positive.

RESULT (2026-10-16, logs/oos1719.txt) - PASS, with large coverage gaps. Median of 10 orderings, funding = 0:
    trend    +57%/yr, fall 38%, worst month -15% | 2017 +1%, 2018 +7%, 2019 +181%
    MN blend  +3%/yr, fall 24%                   | 2017 +0%, 2018 +0%, 2019 +8%   (needs 20 names: traded 2019 only)
    daily    +17%/yr, fall 40%, worst month -17% | 2017 +23%, 2018 -27%, 2019 +60%
    capit2 2x +1%/yr, fall 22%, worst month -17% | 2017 +0%, 2018 -17%, 2019 +17% (38-85 trades a phase)
    COMBINED +88%/yr, fall 48%, worst month -21% | 2017 +13%, 2018 -22%, 2019 +395%
    Predictions 1, 2, 3, 5 right; 4 wrong (the trend book made +7% in the 2018 bear: its SHORTS made +966R there - on
    perps they were a hedge that loses). WHAT IS AND IS NOT TESTED: 2017 hardly (USDT pairs were few: only BTC and ETH
    reached the top-12, Oct-Dec; MN and capit2 idle); MN only in 2019; capit2 weak (+1%/yr vs +20..+30% on perps - its
    2x upgrade is NOT supported out of sample); the trend book is the deployed MAIN book without the 10x guard, and its
    2019 is concentrated in low-volatility early-2019 BTC / BNB / BCH runs (one BTC 4h trade 505R). First run scored the
    trend book with bull_boost.evaluate (daily-sum compounding, rule 12): 2019 +575%, combined +181% - corrected.

    python -m backtest.oos1719
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPOT = ROOT / "strategy_analysis" / "data" / "spot1719"
OCACHE = ROOT / "logs" / "oos1719_cache"
LOG = ROOT / "logs" / "oos1719.txt"
START, END = pd.Timestamp("2017-08-17"), pd.Timestamp("2019-12-31")

import backtest.wide_book as wb  # noqa: E402
wb.DATA = SPOT
import backtest.capitulation_wide as cw  # noqa: E402
cw.PERPS = SPOT
import backtest.market_neutral as mnm  # noqa: E402
mnm.DATA = SPOT
import backtest.carry_check as ck  # noqa: E402
ck.DATA = SPOT
import backtest.pair_lab as pl  # noqa: E402
pl.CACHE = OCACHE
pl._EL.clear()
pl._H.clear()
import backtest.daily_combos as dc  # noqa: E402
dc.CACHE = OCACHE
dc._X.clear()
import backtest.capit_combos as cc  # noqa: E402
cc.CACHE = OCACHE
cc._S.clear()
import backtest.mn_combos as m  # noqa: E402
m._D.clear()
from backtest import bull_boost as BB  # noqa: E402,F401
from backtest import mtm_sizing as MS  # noqa: E402
from backtest import machine_combos as mc  # noqa: E402
from backtest.moderate_retests import scored_run  # noqa: E402


def close_curve(T, taken):
    """Equity booked at each trade's close, on this period's days (capit_combos.curve has the perp span built in)."""
    q = np.array([a for a, _, _ in taken], dtype=int)
    pnl = np.array([c for _, _, c in taken], dtype=float)
    days = pd.date_range(START, END)
    if not len(q):
        return pd.Series(1.0, index=days)
    tout = T.t_out.to_numpy("datetime64[ns]")[q]
    E = (days + pd.Timedelta(days=1)).to_numpy("datetime64[ns]")
    o = np.argsort(tout, kind="stable")
    cum = np.concatenate([[0.0], np.cumsum(pnl[o])])
    return pd.Series(1 + cum[np.searchsorted(tout[o], E, side="left")], index=days)


def stats(r):
    r = r[(r.index >= START) & (r.index <= END)].fillna(0.0)
    c = (1 + r).cumprod()
    yrs = (c.index[-1] - c.index[0]).days / 365.25
    cagr = c.iloc[-1] ** (1 / yrs) - 1 if c.iloc[-1] > 0 else -1.0
    me = c.resample("ME").last()
    mo = (me / me.shift(1).fillna(1.0)) - 1
    yr = c.resample("YE").last()
    yr = yr / yr.shift(1).fillna(1.0) - 1
    return dict(cagr=cagr, fall=float((1 - c / c.cummax()).max()), wm=float(mo.min()), up=float((mo > 0).mean()),
                yr={t.year: float(v) for t, v in yr.items()}, end=float(c.iloc[-1]))


def main():
    lines = [f"backtest/oos1719.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; Binance SPOT {START:%Y-%m-%d} .. {END:%Y-%m-%d}, "
             f"{len(list(SPOT.glob('*_1d.csv.gz')))} coins; frozen final-machine rules; funding = 0; 10 orderings", ""]
    el40 = pl.universe()
    lines.append(f"PIT top-40 coin-months: {sum(len(v) for v in el40.values())}; coins ever in it: {sum(1 for v in el40.values() if v)}")
    # ---- daily and capit2
    T20 = {off: dc.gen(off, dict(dc.BASE, mean_n=20)) for off in dc.PHASES}
    cT2 = {off: cc.gen(off, dict(cc.BASE, **mc.CAPIT_BETTER)) for off in cc.PHASES}
    lines.append(f"daily book trades per phase: {[len(T) for T in T20.values()]}; capit2 trades per phase: {[len(T) for T in cT2.values()]}")
    # ---- MN blend
    D = m.data()
    C = pd.DataFrame(D["X"])
    d = C.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()
    mom = D["X"] / np.r_[np.full((30, D["X"].shape[1]), np.nan), D["X"][:-30]] - 1
    # ---- trend: the main book on the PIT top-12, in-process
    el12 = wb.eligibility(12)
    syms = [s for s, mm in el12.items() if mm and (SPOT / f"{s}_1h.csv.gz").exists()]
    rows = [r for s in syms for r in wb.one_coin((s, el12[s]))]
    btc = cw.hourly("BTCUSDT").set_index("time").close
    bear = (btc < btc.rolling(1000).mean()).shift(1).fillna(False).astype(bool)
    lines.append(f"trend: {len(syms)} coins ever in the PIT top-12, {len(rows)} trades")
    days = pd.date_range(START, END)
    books = {k: [] for k in ("trend", "MN blend", "daily", "capit2 2x", "COMBINED")}
    for sd in mc.SEEDS:
        rng = np.random.default_rng(sd)
        tie = rng.random(len(rows))
        o_ = [rows[i] for i in sorted(range(len(rows)), key=lambda i: (rows[i]["t0"], tie[i]))]
        # entry-sized (rule 12): bull_boost.evaluate's daily-sum compounding read 2019 at +575% - ~2x what a bot earns
        tr = MS.simulate(rows, bear, sd, "realised", want_curve=True).reindex(days).ffill().fillna(1.0).pct_change().fillna(0.0)
        mn = 0.5 * scored_run(mom, start=sd % 7, stop="short_only", short_stop=0.5).reindex(days).fillna(0.0) \
            + 0.5 * scored_run(rsi, start=sd % 7, stop="short_only", short_stop=0.5).reindex(days).fillna(0.0)
        off = dc.PHASES[sd % 3]
        dl = dc.curve(T20[off], dc.allocate(T20[off], sd), off).pct_change().reindex(days).fillna(0.0)
        coff = cc.PHASES[sd % 4]
        cp = close_curve(cT2[coff], dc.allocate(cT2[coff].assign(units=None), sd, 2.0)).pct_change().reindex(days).fillna(0.0)
        books["trend"].append(tr)
        books["MN blend"].append(mn)
        books["daily"].append(dl)
        books["capit2 2x"].append(cp)
        books["COMBINED"].append(tr + mn + 0.5 * dl + cp)
    lines += ["", f"  {'book':<12}{'CAGR':>8}{'fall':>7}{'worst mo':>10}{'months up':>11}{'  by year':<10}   (median of 10 orderings)"]
    R = {}
    for nm, xs in books.items():
        S = [stats(x) for x in xs]
        med = lambda k: float(np.median([s[k] for s in S]))  # noqa: E731
        yrs = sorted(S[0]["yr"])
        R[nm] = dict(cagr=med("cagr"), fall=med("fall"), wm=med("wm"), up=med("up"),
                     yr={y: float(np.median([s["yr"].get(y, 0.0) for s in S])) for y in yrs})
        r = R[nm]
        lines.append(f"  {nm:<12}{r['cagr'] * 100:>+7.0f}%{r['fall'] * 100:>6.0f}%{r['wm'] * 100:>+9.0f}%{r['up'] * 100:>10.0f}%   "
                     + "  ".join(f"{y}: {v * 100:+.0f}%" for y, v in r["yr"].items()))
    pos = [nm for nm in ("trend", "MN blend", "daily", "capit2 2x") if R[nm]["cagr"] > 0]
    c = R["COMBINED"]
    lines += ["", "REGISTERED PREDICTIONS",
              f"  1 capit2 2x makes money: {R['capit2 2x']['cagr'] * 100:+.0f}%/yr -> {'RIGHT' if R['capit2 2x']['cagr'] > 0 else 'WRONG'}",
              f"  2 daily makes money, loses 2018: {R['daily']['cagr'] * 100:+.0f}%/yr, 2018 {R['daily']['yr'].get(2018, 0) * 100:+.0f}% -> "
              f"{'RIGHT' if R['daily']['cagr'] > 0 and R['daily']['yr'].get(2018, 0) < 0 else 'WRONG'}",
              f"  3 MN blend makes money: {R['MN blend']['cagr'] * 100:+.0f}%/yr -> {'RIGHT' if R['MN blend']['cagr'] > 0 else 'WRONG'}",
              f"  4 trend makes money, loses 2018: {R['trend']['cagr'] * 100:+.0f}%/yr, 2018 {R['trend']['yr'].get(2018, 0) * 100:+.0f}% -> "
              f"{'RIGHT' if R['trend']['cagr'] > 0 and R['trend']['yr'].get(2018, 0) < 0 else 'WRONG'}",
              f"  5 combined CAGR > 0, fall < 60%, 2018 >= -30%: {c['cagr'] * 100:+.0f}%, {c['fall'] * 100:.0f}%, {c['yr'].get(2018, 0) * 100:+.0f}% -> "
              f"{'RIGHT' if c['cagr'] > 0 and c['fall'] < 0.6 and c['yr'].get(2018, 0) >= -0.3 else 'WRONG'}",
              f"  PASS LINE (combined > 0 and >= 3 of 4 books positive: {pos}): "
              f"{'PASS' if c['cagr'] > 0 and len(pos) >= 3 else 'FAIL'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

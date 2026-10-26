"""STOCKBEE'S EXHAUSTION HAMMER AND MOMENTUM BURST, ON CRYPTO PERPS (2026-10-27)

tradermonty/claude-trading-skills has two Stockbee-style daily setups written as screeners with numeric defaults:
 A  EXHAUSTION HAMMER (stockbee-exhaustion-hammer-screener, screen_exhaustion_hammer.py's CLI defaults): a recent high formed
    within 40 days and 3-30 days ago; a pullback of 6-35% from it; a daily bar with a long lower wick (>= 40% of the range,
    >= 1.5x the body), a small body (<= 35% of the range), a small upper wick (<= 35%), a close in the upper part of the range
    (close location >= 60%) and a recovery of >= 2% off the low; the stop is the day's low less 0.10%, risk to the stop <= 12%.
    Variant A_U adds the skill's "undercut / reclaim": today's low is under the previous 5 days' lows and the close is back above.
    The skill's stock-quality gates (price, market cap, holders) are replaced by the point-in-time top-40 by volume.
    Pullback depth is measured from the recent high to TODAY'S LOW (the shake-out); the skill's text does not say which.
 B  MOMENTUM BURST (stockbee-momentum-burst-screener): close >= 1.04 x the previous close, volume above the previous day's,
    range expansion (today's range above each of the prior three ranges, prior day not itself extended: its range not above
    its own prior three), close location >= 70% (the skill says only "near the high"; 70% is my fixed choice), failure filters:
    no prior 3-day run-up over 10% and no -4% day in the previous 5. Stockbee holds 3-5 days: here 3, stop = the day's low.
    B_L = the long as designed; B_S = the mirror short (does the burst revert?).
UNIVERSE  point-in-time top-40 by volume with dead coins in (regime_signals.member_mask / wide_book.eligibility), stables and
          non-crypto dropped; Binance perp daily bars 2020-01 .. 2026-09 (strategy_analysis/data/perps).
ENTRY     at the signal day's close (the skills scan near the close); EXIT  the stop (the next days' low reaching it fills at the
          stop, or the open if it gaps through) or the time exit (A: day 5, B: day 3) at the close.  COSTS  12bp a round trip
          + funding 3bp a day on longs (1bp / 8h), charged on shorts as received 0 (conservative).
CONTROLS  C1 (A only): the same context WITHOUT the candle - pullback 6-35% from a 3-30-day-old 40-day high, close within the
          day's top 60% of the range, same exits - does the hammer shape add anything? C2: every PIT coin-day, same exits (the
          drift a holder gets). Edge = net per trade, and per day in the market against C2.
SPLIT     tune = signals before 2024-01-01, holdout after. t by ENTRY DATE (coins that signal the same day are averaged: crash
          days are one bet). Holm over the four variants.

REGISTERED BEFORE THE FIRST RUN (2026-10-27)
  H1  A and A_U do not pass (net > 0 with t >= 2 on both halves, Holm < 0.05): crypto's reversal edge sits in forced selling
      (capit2: a -10% day and a limit order), not in the candle shape, and the hammer needs the day to close to be known.
  H2  B_L (the burst long) has a negative holdout net, and B_S (the fade) is not positive on both halves either.
  H3  A beats its context control C1 by less than 0.3% a trade (the candle adds almost nothing to the context).
PASS    a variant passes both halves, Holm < 0.05, and beats C1 / C2 per day on both halves. Otherwise none.

    python -m backtest.stockbee_crypto
"""
from __future__ import annotations

import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.market_neutral import DATA, drop_non_crypto, load_panel  # noqa: E402
from backtest.regime_signals import member_mask  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

LOG = ROOT / "logs" / "stockbee_crypto.txt"
FEE, FUND = 12e-4, 3e-4
CUT = pd.Timestamp("2024-01-01")


def bars(sym):
    d = pd.read_csv(DATA / f"{sym}_1d.csv.gz", parse_dates=["time"]).drop_duplicates("time").set_index("time").sort_index()
    return d[["open", "high", "low", "close", "qvol"]]


def hammer_flags(d, undercut):
    o, h, l, c = (d[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    n = len(d)
    rng = h - l
    with np.errstate(all="ignore"):
        lw = (np.minimum(o, c) - l) / rng
        body = np.abs(c - o) / rng
        uw = (h - np.maximum(o, c)) / rng
        loc = (c - l) / rng
        rec = c / l - 1
    geo = (lw >= 0.40) & (body <= 0.35) & (uw <= 0.35) & (loc >= 0.60) & (rec >= 0.02) & (lw >= 1.5 * body)
    ctx = np.zeros(n, bool)
    und = np.zeros(n, bool)
    stop_ok = np.zeros(n, bool)
    for i in range(45, n):
        win = h[i - 40:i]
        k = int(np.argmax(win))
        days_since = 40 - k
        rh = win[k]
        pull = (rh - l[i]) / rh
        ctx[i] = 3 <= days_since <= 30 and 0.06 <= pull <= 0.35
        pl = l[i - 5:i].min()
        und[i] = l[i] < pl and c[i] > pl
        stop = l[i] * (1 - 0.001)
        stop_ok[i] = (c[i] - stop) / c[i] <= 0.12
    return geo & ctx & stop_ok & (und if undercut else True), ctx & (loc >= 0.60) & stop_ok, geo


def burst_flags(d):
    c, h, l, o = (d[k].to_numpy(float) for k in ("close", "high", "low", "open"))
    v = d["qvol"].to_numpy(float)
    n = len(d)
    rng = h - l
    f = np.zeros(n, bool)
    for i in range(8, n):
        if not (c[i] / c[i - 1] >= 1.04 and v[i] > v[i - 1]):
            continue
        if not (rng[i] > rng[i - 3:i].max()):
            continue
        if rng[i - 1] > rng[i - 4:i - 1].max():                  # the prior day was already extended
            continue
        if (c[i] - l[i]) / max(rng[i], 1e-12) < 0.70:
            continue
        if c[i - 1] / c[i - 4] - 1 > 0.10:                       # a 3-day run-up already
            continue
        if (c[i - 5:i] / c[i - 6:i - 1] - 1 <= -0.04).any():     # a recent -4% day
            continue
        f[i] = True
    return f


def simulate(d, flags, hold, side=1):
    """Entry at the signal day's close; exit at the stop (day low) or day `hold`'s close. Returns (entry_date, net, days)."""
    h, l, c, o = (d[k].to_numpy(float) for k in ("high", "low", "close", "open"))
    idx = d.index
    n = len(d)
    out = []
    i = 0
    while i < n - 1:
        if not flags[i]:
            i += 1
            continue
        e = c[i]
        stop = l[i] * (1 - 0.001) if side > 0 else h[i] * (1 + 0.001)
        x, j = None, i
        for j in range(i + 1, min(i + hold, n - 1) + 1):
            if side > 0 and l[j] <= stop:
                x = min(stop, o[j])
                break
            if side < 0 and h[j] >= stop:
                x = max(stop, o[j])
                break
            if j == i + hold:
                x = c[j]
                break
        if x is None:
            x = c[min(i + hold, n - 1)]
            j = min(i + hold, n - 1)
        days = j - i
        net = side * (x / e - 1) - FEE - (FUND * days if side > 0 else 0.0)
        out.append((idx[i], net, days))
        i = j + 1
    return out


def tstat(x):
    x = np.asarray(x, float)
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std(ddof=1) > 0 else np.nan


def stats(tr):
    if not len(tr):
        return None
    g = tr.groupby("t0")["net"].mean()
    return dict(n=len(tr), net=tr.net.mean(), t=tstat(g), win=(tr.net > 0).mean(), perday=tr.net.sum() / max(tr.days.sum(), 1))


def fmt(s):
    return "no trades" if s is None else f"n {s['n']:5d} net {s['net'] * 100:+6.2f}% win {s['win'] * 100:3.0f}% t {s['t']:+5.1f} per day {s['perday'] * 1e4:+6.1f}bp"


def main():
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    mem = member_mask(C, first, drop_non_crypto(eligibility(40))) & np.isfinite(C.to_numpy(float))
    coins = [c for j, c in enumerate(C.columns) if mem[:, j].any() and c.endswith("USDT")]
    rows = {k: [] for k in ("A", "A_U", "C1", "C2", "B_L", "B_S")}
    for sym in coins:
        try:
            d = bars(sym)
        except Exception:
            continue
        if len(d) < 120:
            continue
        j = list(C.columns).index(sym)
        member = pd.Series(mem[:, j], index=C.index).reindex(d.index).shift(1).fillna(False).to_numpy(bool)   # known the day before
        a, ctx, geo = hammer_flags(d, False)
        au, _, _ = hammer_flags(d, True)
        bf = burst_flags(d)
        allday = np.ones(len(d), bool)
        allday[:45] = False
        for k, fl, hold, side in (("A", a, 5, 1), ("A_U", au, 5, 1), ("C1", ctx, 5, 1), ("C2", allday, 5, 1), ("B_L", bf, 3, 1), ("B_S", bf, 3, -1)):
            for t0, net, days in simulate(d, fl & member, hold, side):
                rows[k].append((t0, net, days, sym))
    R = {k: pd.DataFrame(v, columns=["t0", "net", "days", "sym"]) for k, v in rows.items()}
    L = [f"backtest/stockbee_crypto.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(coins)} PIT-top-40 perps, daily 2020-01..2026-09; "
         f"tune < {CUT:%Y-%m-%d}; costs 12bp + 3bp/day on longs", ""]
    res = {}
    for k in ("A", "A_U", "C1", "C2", "B_L", "B_S"):
        tr = R[k]
        res[k] = {p: stats(m) for p, m in (("all", tr), ("tune", tr[tr.t0 < CUT]), ("hold", tr[tr.t0 >= CUT]))}
        L.append(f"  {k:4} all  {fmt(res[k]['all'])}")
        L.append(f"       tune {fmt(res[k]['tune'])}")
        L.append(f"       hold {fmt(res[k]['hold'])}")
    names = ["A", "A_U", "B_L", "B_S"]
    ps = sorted((1 - 0.5 * (1 + erf((res[k]["all"]["t"] if res[k]["all"] else -9) / sqrt(2))), k) for k in names)
    holm, run_max = {}, 0.0
    for r_, (p, k) in enumerate(ps):
        run_max = max(run_max, min(1.0, p * (len(ps) - r_)))
        holm[k] = run_max
    passes = []
    for k in names:
        t_, h_ = res[k]["tune"], res[k]["hold"]
        if t_ and h_ and t_["net"] > 0 and h_["net"] > 0 and t_["t"] >= 2 and h_["t"] >= 2 and holm[k] < 0.05:
            passes.append(k)
    h1 = "A" not in passes and "A_U" not in passes
    bl_h = res["B_L"]["hold"]
    bs = res["B_S"]
    h2 = (bl_h is not None and bl_h["net"] < 0) and not (bs["tune"] and bs["hold"] and bs["tune"]["net"] > 0 and bs["hold"]["net"] > 0)
    h3 = (res["A"]["all"] is not None) and (res["A"]["all"]["net"] - res["C1"]["all"]["net"] < 0.003)
    L += ["", "Holm p (4 variants): " + ", ".join(f"{k} {holm[k]:.2f}" for k in names) + f" | PASS: {passes or 'none'}", "",
          "REGISTERED PREDICTIONS",
          f"  H1 A and A_U do not pass -> {'RIGHT' if h1 else 'WRONG'}",
          f"  H2 B_L loses on the holdout and B_S is not positive on both halves -> {'RIGHT' if h2 else 'WRONG'}",
          f"  H3 A beats C1 by under 0.3% a trade ({(res['A']['all']['net'] - res['C1']['all']['net']) * 100 if res['A']['all'] else float('nan'):+.2f}%) -> {'RIGHT' if h3 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

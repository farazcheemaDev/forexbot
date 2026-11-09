"""THE 'MOTHER AND BABY' INSIDE BAR AT A NEW HIGH, 30-minute bars, on gold and ten other markets (2026-11-08)

THE USER'S RULE (2026-11-08, right after the 'I want a gold bot with bigger returns' request): "30 minute time frame, market swings, a new high will be made; if on that high there is an inside bar - a big
candle (the mother) and a baby candle - and the baby's low is broken, we enter with the mother's high as the stop loss."

MY READING (the user gave no numbers; these were FIXED BEFORE THE FIRST RUN and are one reading of 'new high', 'big' and 'baby', not the only one)
  bars        30-minute bars of the 1-minute data (slot = t // 30 min, UTC); a bar needs at least 10 minute bars; the mother and baby must be consecutive slots.
  mother      its high is above the highest high of the 20 bars before it (a NEW 20-bar high) and its range is at least 1.0 x ATR14 (mean true range of the 14 bars before it) = 'big'.
  baby        the next bar, INSIDE the mother (high <= mother high, low >= mother low) and at most 0.5 x the mother's range.
  entry       a SHORT when the baby's low breaks, within the next 4 bars (2 hours); cancelled if the mother's high trades first.
  stop        the mother's high.  target  k x R (k = 1, 2, 3, R = stop - entry).  time exit  24 hours after the entry, at the close.
  mirror      the same rule upside down (a new LOW, the baby's HIGH breaks, long, stop at the mother's low) is run by negating the prices; the user only described the short.
  fills       TOUCH = a sell-stop at the baby's low (a minute that opens below it fills at the open; +2bp stop-order slippage). CLOSE = a market order at the close of the first 30-minute bar that
              closes below the baby's low (cancelled if any bar up to and including it trades at the mother's high). Both are run, because a stop order at a level is exactly where this repo's
              last test (gold_news_breakout.py) found a fill artifact; a result is believed only if the CLOSE fill holds up.
  management  on the 1-MINUTE bars: stop and target in the same minute = the stop; a minute that gaps through the stop exits at its open (worse than the stop), through the target at its open (better).
  costs       round trip 2.94bp on gold (as gold_focus.py), 1.27bp on NASDAQ (as forex_bot.py), 1.5bp on everything else (ASSUMED, not measured, not Exness's published figures).
  control     the SAME bracket (the trade's own risk fraction, the same k, the same 24 hours) entered at the SAME minute-of-day on 5 random other days of the SAME half (tune = the first 60% of the
              signals by time), with the same costs: it asks whether the PATTERN adds anything to a short with that stop and target at that time of day (gold drifts up, so random shorts lose).
              Like the sell-stop fill, the control's management starts the minute AFTER its entry minute (the entry minute's own range is not used).
  PASS        net R > 0 AND excess over the control with Welch t >= 2, on BOTH halves.   Primary cell (named before the run): XAUUSD, short, TOUCH, 2R.

REGISTERED BEFORE THE RUN (written in the exploratory script before it was run; prior that any cell passes: about 5%)
  T1  no cell passes on gold.      T2  TOUCH looks better than CLOSE by more than 0.2R (the fill, as in the NFP test).
  T3  the mirror (long at new lows) is as null as the short.      T4  the random-short control loses on gold (the drift), so the excess is smaller than the net suggests.

RESULT (2026-11-08, logs/inside_bar_break.txt; 56 cells = 12 gold + 4 gold look-back checks + 10 markets x 4)
  GOLD, the rule as stated (short, new 20-bar high): TOUCH n 1,342, win 44.5% / 32.2% / 26.4% at 1R / 2R / 3R, net -0.245 / -0.233 / -0.261 R a trade; CLOSE n 910, win 48.0% / 36.4% / 32.0%,
  net -0.153 / -0.104 / -0.077 R. The random-short control loses about the same (-0.18 .. -0.28 R at 2R), so the excess is nil: t between -0.9 and +0.7 on both halves in all six cells. A 2R trade
  at a random entry wins one time in three, so a 32% win rate is the coin; the loss is the cost (about 0.2 R a trade, because the stop sits close). The look-back checks (10 and 50 bars) are the same.
  GOLD mirror (long at new lows): TOUCH -0.15 .. -0.19 R, CLOSE -0.006 .. -0.056 R; the best, CLOSE 1R, is net +0.032 on the holdout and +2.08 excess t there but -0.114 and t +0.03 on the tune half: no pass.
  OTHER MARKETS at 2R: every short loses (TOUCH -0.16 .. -0.29 R, CLOSE -0.04 .. -0.12 R). ONE cell passes: NASDAQ (NSXUSD), the MIRROR, TOUCH fill: n 889, win 40.5%, net +0.079 R (tune +0.031, holdout
  +0.149), excess t +2.34 / +3.01. Its CLOSE fill is better (net +0.130 R) but its excess t is +1.25 / +2.33, which fails the bar, so by the rule above it is a LEAD, not a result: 1 of 56 cells (about a 3%
  chance of one by luck if every cell were null, ignoring that the cells share trades), a NASDAQ dip-buy in the family of ndx_capit.py / the machine's QQQ book, long only, and it needs the 1.27bp cost to hold.
  Predictions: T1 right for gold (wrong across the table because of the NASDAQ lead), T2 WRONG (the stop-order fill is the WORSE one on gold: it is filled into whipsaws the close would have skipped),
  T3 right, T4 right.

LIMITS. Bid-only HistData bars (the spread is a constant, 1.5bp for forex is an assumption), 'new high' / 'big' / 'baby' are one reading each (only the look-back was varied), the controls share the signal's
half but not its regime, the cells share trades (so 56 is not 56 independent tests), 24-hour holds cross swap on a non-swap-free account (not charged), and nothing here is a bot or a forward record.
Nothing deployed.

TESTS. tests/test_inside_bar_break.py 42 (each signal condition and its boundary, the true-range ATR, the minute-bar management with ties and gaps and the 24-hour edge, both fills, the control's days / time of day / holes /
data end, Welch, the pass rule at t exactly 2, the printed line, and a planted five-pattern market run end to end, including the mirror and the 60/40 split). 100 of 100 planted bugs caught over two rounds (93 first; the
seven survivors were gaps in MY tests: the gap terms of the true range, a baby-high check hidden behind the size check, an exact touch of the level, the control's time of day and day pools, its data-end guard and its
entry-minute convention) and the do-nothing control survived; one more mutant is equivalent (the end-of-data guard in trade_close: manage() already returns None past the data). The module reproduces the exploratory
run's 62 result lines exactly.

    python -m backtest.inside_bar_break          # writes logs/inside_bar_break.txt (about 6-8 minutes)
    tests: python tests/test_inside_bar_break.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HD = ROOT / "strategy_analysis" / "data" / "histdata"
LOG = ROOT / "logs" / "inside_bar_break.txt"
COST = {"XAUUSD": 2.94, "NSXUSD": 1.27}
DEFAULT_COST = 1.5
STOP_SLIP = 2.0 / 1e4
SLOT = 30 * 60 * 1000
MIN = 60_000
LOOK, BIG, BABY, WAIT, HOLD_MIN, CTRL = 20, 1.0, 0.5, 4, 1440, 5
TUNE = 0.60
SEED = 11


# ----------------------------------------------------------------------------------------------- data and bars
def load(sym):
    d = pd.read_parquet(HD / f"{sym}.parquet").sort_values("t").drop_duplicates("t")
    return [d[k].to_numpy(float) if k != "t" else d[k].to_numpy(np.int64) for k in ("t", "o", "h", "l", "c")]


def mirror(t, o, h, l, c):  # noqa: E741
    """The same market upside down: a long becomes a short, a new low a new high."""
    return t, -o, -l, -h, -c


def bars30(t, o, h, l, c):  # noqa: E741
    s = t // SLOT
    idx = np.flatnonzero(np.r_[True, s[1:] != s[:-1]])
    end = np.r_[idx[1:], len(t)]
    cnt = end - idx
    bo, bh = o[idx], np.maximum.reduceat(h, idx)
    bl, bc = np.minimum.reduceat(l, idx), c[end - 1]
    ok = cnt >= 10
    return s[idx][ok], bo[ok], bh[ok], bl[ok], bc[ok]


def signals(bs, bo, bh, bl, bc, look=LOOK):
    """(baby index, stop = the mother's high, trigger = the baby's low) for every mother / baby pair."""
    n = len(bs)
    pc = np.r_[bc[0], bc[:-1]]
    tr = np.maximum(bh - bl, np.maximum(np.abs(bh - pc), np.abs(bl - pc)))
    cs = np.cumsum(np.r_[0.0, tr])
    i = np.arange(look + 15, n - 1)
    atr = (cs[i] - cs[i - 14]) / 14
    wmax = np.lib.stride_tricks.sliding_window_view(bh, look).max(axis=1)      # wmax[j] = max(bh[j:j+look])
    prevmax = wmax[i - look]
    rng_m, rng_b = bh[i] - bl[i], bh[i + 1] - bl[i + 1]
    ok = (bh[i] > prevmax) & (rng_m >= BIG * atr) & (bh[i + 1] <= bh[i]) & (bl[i + 1] >= bl[i]) & (rng_b <= BABY * rng_m) & (bs[i + 1] == bs[i] + 1) & (rng_m > 0)
    i = i[ok]
    return i + 1, bh[i], bl[i + 1]


# ----------------------------------------------------------------------------------------------- trades (always a short; the long side runs on mirrored prices)
def manage(t, o, h, l, c, a, entry, S, k, costf):  # noqa: E741
    """A short entered at `entry` just before minute index `a`: stop S, target k x R, 24 hours. Net R after the round-trip cost, or None."""
    D = S - entry
    if D <= 0:
        return None
    T = entry - k * D
    b = min(np.searchsorted(t, t[a - 1] + HOLD_MIN * MIN), len(t))
    if b <= a:
        return None
    hh, ll = h[a:b], l[a:b]
    si = np.argmax(hh >= S) if (hh >= S).any() else 10**9
    ti = np.argmax(ll <= T) if (ll <= T).any() else 10**9
    if si == 10**9 and ti == 10**9:
        ex = c[b - 1]
    elif si <= ti:
        ex = max(S, o[a + si])
    else:
        ex = min(T, o[a + ti])
    return (entry - ex) / D - costf * abs(entry) / D


def trade_touch(t, o, h, l, c, bs_j, S, L, k, costf):  # noqa: E741
    """Sell-stop at the baby's low L, live for WAIT bars after the baby, cancelled if the mother's high S trades first. (net R, risk fraction, entry minute) or None."""
    m0 = np.searchsorted(t, (bs_j + 1) * SLOT)
    m1 = np.searchsorted(t, (bs_j + 1 + WAIT) * SLOT)
    if m1 <= m0 + 1:
        return None
    hh, ll = h[m0:m1], l[m0:m1]
    trig = np.flatnonzero(ll <= L)
    if trig.size == 0:
        return None
    jt = trig[0]
    canc = np.flatnonzero(hh >= S)
    if canc.size and canc[0] < jt:
        return None
    mm = m0 + jt
    entry = min(L, o[mm]) - STOP_SLIP * abs(L)
    D = S - entry
    if D <= 0:
        return None
    if canc.size and canc[0] == jt:                      # the stop and the entry in the same minute: stopped
        return -1.0 - costf * abs(entry) / D, D / abs(entry), mm
    r = manage(t, o, h, l, c, mm + 1, entry, S, k, costf)
    return None if r is None else (r, D / abs(entry), mm)


def trade_close(t, o, h, l, c, bars, jb, S, L, k, costf):  # noqa: E741
    """Market order at the close of the first 30-minute bar (within WAIT bars of the baby) that closes below L; cancelled if a bar up to and including it trades at S."""
    bs, bo, bh, bl, bc = bars
    for q in range(jb + 1, min(jb + 1 + WAIT, len(bs))):
        if bs[q] != bs[jb] + (q - jb):
            return None
        if bh[q] >= S:
            return None
        if bc[q] < L:
            m = np.searchsorted(t, (bs[q] + 1) * SLOT)
            entry = bc[q]
            D = S - entry
            if D <= 0 or m >= len(t):
                return None
            r = manage(t, o, h, l, c, m, entry, S, k, costf)
            return None if r is None else (r, D / abs(entry), m - 1)
    return None


def control(t, o, h, l, c, day_pool, tod_ms, rf, k, costf, kind, rng):  # noqa: E741
    """CTRL net-R draws of the same bracket (risk fraction rf, k, 24 hours) at the same minute-of-day on random days of `day_pool`."""
    out = []
    tries = 0
    while len(out) < CTRL and tries < 60:
        tries += 1
        d = day_pool[rng.integers(len(day_pool))]
        m = np.searchsorted(t, d * 86400000 + tod_ms)
        if m >= len(t) - 2000 or abs(t[m] - (d * 86400000 + tod_ms)) > 2 * MIN:
            continue
        entry = o[m] - (STOP_SLIP * abs(o[m]) if kind == "touch" else 0.0)
        r = manage(t, o, h, l, c, m + 1, entry, entry + rf * abs(entry), k, costf)
        if r is not None:
            out.append(r)
    return out


# ----------------------------------------------------------------------------------------------- statistics and the pass rule
def welch(a, b):
    a, b = np.asarray(a), np.asarray(b)
    if len(a) < 5 or len(b) < 5:
        return float("nan")
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return (a.mean() - b.mean()) / se if se > 0 else float("nan")


def verdict(S_, C_):
    """S_, C_ = [tune list, holdout list] of net R. None with no trades; else the cell's numbers and PASS = net > 0 and excess t >= 2 on BOTH halves."""
    n = len(S_[0]) + len(S_[1])
    if n == 0:
        return None
    allr = np.array(S_[0] + S_[1])
    m0 = np.mean(S_[0]) if S_[0] else float("nan")
    m1 = np.mean(S_[1]) if S_[1] else float("nan")
    c0 = np.mean(C_[0]) if C_[0] else float("nan")
    c1 = np.mean(C_[1]) if C_[1] else float("nan")
    t0, t1 = welch(S_[0], C_[0]), welch(S_[1], C_[1])
    return dict(n=n, win=float((allr > 0).mean()), net=float(allr.mean()), m0=m0, m1=m1, c0=c0, c1=c1, t0=t0, t1=t1,
                passed=bool(m0 > 0 and m1 > 0 and t0 >= 2 and t1 >= 2))


def line(sym, side, kind, k, look, S_, C_):
    v = verdict(S_, C_)
    if v is None:
        return f"{sym:7s} {side:5s} {kind:5s} {k}R look{look}: no trades"
    return (f"{sym:7s} {side:5s} {kind:5s} {k}R look{look:>2}: n {v['n']:4d} ({len(S_[0])}/{len(S_[1])}) win {v['win']*100:4.1f}% net R {v['net']:+.3f} "
            f"[tune {v['m0']:+.3f} hold {v['m1']:+.3f}] | control [{v['c0']:+.3f} {v['c1']:+.3f}] | excess t [{v['t0']:+.2f} {v['t1']:+.2f}] {'PASS' if v['passed'] else ''}").rstrip()


# ----------------------------------------------------------------------------------------------- the study
def run_side(t, o, h, l, c, side, ks, kinds, look, costf, rng):  # noqa: E741
    """Every (fill, k) cell for one side (-1 = short at new highs, +1 = the mirror) on one market's minute arrays. [(side name, kind, k, look, [tune R], [hold R], controls...)]."""
    days = np.unique(t // 86400000)
    if side == -1:
        T_, O_, H_, L_, C_ = t, o, h, l, c
    else:
        T_, O_, H_, L_, C_ = mirror(t, o, h, l, c)
    bars = bars30(T_, O_, H_, L_, C_)
    bs = bars[0]
    jb, Sx, Lx = signals(*bars, look=look)
    cut_t = (bs[jb][int(len(jb) * TUNE)]) * SLOT if len(jb) else 0
    cut_day = cut_t // 86400000
    pool = {0: days[days < cut_day], 1: days[days >= cut_day]}
    res = []
    for kind in kinds:
        for k in ks:
            S_, C_r = [[], []], [[], []]
            for j, s_, l_ in zip(jb, Sx, Lx):
                tr = (trade_touch(T_, O_, H_, L_, C_, bs[j], s_, l_, k, costf) if kind == "touch"
                      else trade_close(T_, O_, H_, L_, C_, bars, j, s_, l_, k, costf))
                if tr is None:
                    continue
                r, rf, mm = tr
                hlf = 0 if bs[j] * SLOT < cut_t else 1
                S_[hlf].append(r)
                C_r[hlf].extend(control(T_, O_, H_, L_, C_, pool[hlf], int(T_[mm] % 86400000), rf, k, costf, kind, rng))
            res.append(("short" if side == -1 else "long", kind, k, look, S_, C_r))
    return res


def study(sym, ks, kinds=("touch", "close"), sides=(-1, 1), look=LOOK, rng=None):
    rng = rng if rng is not None else np.random.default_rng(SEED)
    t, o, h, l, c = load(sym)  # noqa: E741
    costf = COST.get(sym, DEFAULT_COST) / 1e4
    out = []
    for side in sides:
        out += [(sym,) + r for r in run_side(t, o, h, l, c, side, ks, kinds, look, costf, rng)]
    return out


def main():
    rng = np.random.default_rng(SEED)
    lines, passes, cells = [], [], 0

    def add(res):
        nonlocal cells
        for r in res:
            lines.append(line(*r))
            cells += 1
            v = verdict(r[5], r[6])
            if v and v["passed"]:
                passes.append(f"{r[0]} {r[1]} {r[2]} {r[3]}R")
        print("\n".join(lines[-len(res):]))
        sys.stdout.flush()

    lines.append("== GOLD, full grid ==")
    print(lines[-1])
    add(study("XAUUSD", ks=(1, 2, 3), rng=rng))
    lines += ["", "== GOLD, new-high lookback sensitivity (short, TOUCH and CLOSE, 2R) =="]
    print("\n" + lines[-1])
    for lk in (10, 50):
        add(study("XAUUSD", ks=(2,), sides=(-1,), look=lk, rng=rng))
    lines += ["", "== OTHER MARKETS, 2R =="]
    print("\n" + lines[-1])
    for sym in ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "NSXUSD", "SPXUSD", "GRXEUR"):
        add(study(sym, ks=(2,), rng=rng))
    lines += ["", f"cells {cells}; PASS {len(passes)}" + (": " + ", ".join(passes) if passes else "")]
    print(lines[-1])
    LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

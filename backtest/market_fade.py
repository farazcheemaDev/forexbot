"""THE MARKET-LEVEL FADE: SHORT THE CRYPTO MARKET AFTER A STRONG 4h UP-MOVE (2026-11-02)

The loose thread of candle_scan.py and candle_manage.py. Two different exit rules (a 20-hour hold; a 1 ATR stop with a +2R target)
found the same thing: of the 50 candle cells that were positive on both halves, 41 were SHORTS, with t of 3-4 and zero excess over
random entries at the same moment - being short after broad strong up-moves on 4h bars paid on every coin alike. That is a
statement about the MARKET, not about candles. This tests it as a market rule, once, with the choices fixed here.

SIGNAL   R(t) = the equal-weight mean 4h return (close / open - 1) of the point-in-time top-40 perps (by the prior month's volume, dead
         coins in; stables and non-crypto dropped) in the 4h bar ending at t, at least 10 coins. z(t) = R(t) divided by the standard
         deviation of R over the previous 180 bars (30 days, the bar itself excluded). SIGNAL: z >= thr.
TRADE    known at the bar's close; ENTER at the next bar's open, EXIT at the close H bars after the signal. SHORT the equal-weight basket
         of the same point-in-time coins (and, separately, BTCUSDT alone). One trade at a time: a signal inside an open trade is
         skipped. 12bp round trip on the notional; shorts receive no funding (conservative). No stop (the tail is reported).
GRID     thr in {1.5, 2.0, 2.5} x H in {1, 5, 12} bars (4h, 20h, 48h) x {basket, BTC} x {short after up-moves, and as a REFERENCE the
         mirror: long after z <= -thr, which pays 1bp / 8h funding} = 36 cells. The PRIMARY cell is basket, thr 2.0, H = 5, short.
SPLIT    tune before 2024-08-29, holdout after. Each entry DAY counts once in means and t (cs.day_mean_t).
NULL     circular shift: the whole signal series is moved by a random whole number of days (30 days or more, a multiple of 6 bars so
         the time of day is kept), the same one-at-a-time rule is applied and the mean net of the shifted trades is recorded; 1,500
         shifts. p = the share of shifts at least as good as the real series, per half. This keeps the drift of the period, the
         clustering of the signals and the time-of-day structure, and asks only whether the TIMING of the real signals matters.
PASS     all three: (1) the primary cell has net > 0 and t >= 2 on both halves; (2) its shift p < 0.05 on both halves; (3) a plateau: the
         basket-short cells (thr x H = 9) have net > 0 on both halves in at least 7 of 9.

REGISTERED BEFORE THE FIRST RUN (2026-11-02; the lead was found after looking, so the bar is three-fold; my prior that it passes: ~20%)
  T1  The primary cell does not pass: its shift p is above 0.05 on at least one half, or t < 2 on a half.
  T2  The plateau fails: fewer than 7 of the 9 basket-short cells are positive on both halves.
  T3  The mirror is the stronger side: long after strong down-moves (thr 2.0, H = 5) has a higher mean net than the short on both halves.
  T4  The tail is real: the worst single trade of the primary cell loses more than 8% of the basket's notional.

    python -m backtest.market_fade
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import candle_scan as cs  # noqa: E402

LOG = ROOT / "logs" / "market_fade.txt"
FEE, FUND_H = cs.FEE, cs.FUND_H
BAR_H = 4
THRS, HOLDS = (1.5, 2.0, 2.5), (1, 5, 12)
WIN, MIN_WIN, MIN_COINS = 180, 120, 10
PRIMARY = ("basket", 2.0, 5, "short")
SHIFT_STEP, MIN_SHIFT, N_SHIFTS, SEED = 6, 180, 1500, 11
T0 = np.datetime64("2019-09-01T00", "ns")
T_END = np.datetime64("2026-11-01T00", "ns")
STEP = np.timedelta64(BAR_H, "h")


# ---------------------------------------------------------------- panel

def build_panel():
    """Open / close / membership on one global 4h grid: arrays (bars x coins)."""
    from backtest.capitulation_wide import hourly
    from backtest.market_neutral import drop_non_crypto
    from backtest.wide_book import eligibility
    elig = drop_non_crypto(eligibility(40))
    coins = sorted(s for s in elig if elig[s] and s.endswith("USDT"))
    ng = int((T_END - T0) / STEP)
    grid = T0 + np.arange(ng) * STEP
    O, C = np.full((ng, len(coins)), np.nan), np.full((ng, len(coins)), np.nan)
    M = np.zeros((ng, len(coins)), bool)
    gm = grid.astype("datetime64[M]")
    used = []
    for j, sym in enumerate(coins):
        h = hourly(sym)
        if h is None:
            continue
        d = cs.to_tf(h, BAR_H)
        tt = d["time"].to_numpy("datetime64[ns]")
        k = ((tt - T0) / STEP).astype(int)
        ok = (k >= 0) & (k < ng)
        O[k[ok], j], C[k[ok], j] = d["o"].to_numpy(float)[ok], d["c"].to_numpy(float)[ok]
        M[:, j] = np.isin(gm, np.array(sorted(elig[sym]), dtype="datetime64[M]"))
        used.append(sym)
    return grid, coins, O, C, M


# ---------------------------------------------------------------- series

def bar_returns(O, C, M, min_coins=MIN_COINS):
    """R[t]: equal-weight mean of C/O - 1 over the point-in-time members with a bar at t."""
    ok = M & np.isfinite(O) & np.isfinite(C) & (O > 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.where(ok, C / O - 1, 0.0)
    n = ok.sum(1)
    return np.where(n >= min_coins, r.sum(1) / np.maximum(n, 1), np.nan)


def forward_returns(O, C, M, H, min_coins=MIN_COINS):
    """(F, per-coin matrix): F[i] = equal-weight mean over the members at bar i of C[i+H] / O[i+1] - 1 (enter at the next open)."""
    ng, nc = O.shape
    fwd = np.full((ng, nc), np.nan)
    if ng > H + 1:
        with np.errstate(invalid="ignore", divide="ignore"):
            fwd[:ng - H] = C[H:ng, :] / O[1:ng - H + 1, :] - 1
    ok = M & np.isfinite(fwd)
    n = ok.sum(1)
    F = np.where(n >= min_coins, np.where(ok, fwd, 0.0).sum(1) / np.maximum(n, 1), np.nan)
    return F, fwd


def zscore(R, win=WIN, min_periods=MIN_WIN):
    """R divided by the std of the PREVIOUS `win` bars (the bar itself is not in its own scale)."""
    sd = pd.Series(R).rolling(win, min_periods=min_periods).std().shift(1).to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        return R / sd


def pick_events(flag, H):
    """One trade at a time: a trade from bar i occupies bars i+1 .. i+H; the next signal may come on bar i+H."""
    out, last = [], -1
    for i in np.flatnonzero(np.asarray(flag, bool)).tolist():
        if i >= last:
            out.append(i)
            last = i + H
    return np.array(out, int)


def event_net(F, idx, side, H):
    """Net return of the basket trade per event, on the notional: short = -forward - fee; long = forward - fee - funding."""
    g = F[np.asarray(idx, int)]
    return -g - FEE if side == "short" else g - FEE - FUND_H * H * BAR_H


# ---------------------------------------------------------------- tests of one cell

def half_masks(days):
    return days < cs.CUT_DAY, days >= cs.CUT_DAY


def shift_null(flag, F, H, side, shifts, grid_days):
    """Mean net per trade, tune and holdout, of the signal series moved by each shift (whole days, time of day kept)."""
    fin = np.isfinite(F)
    out = np.full((len(shifts), 2), np.nan)
    for q, s in enumerate(shifts):
        idx = pick_events(np.roll(flag, int(s)) & fin, H)
        if not len(idx):
            continue
        net = event_net(F, idx, side, H)
        tu, ho = half_masks(grid_days[idx + 1])
        out[q, 0] = net[tu].mean() if tu.any() else np.nan
        out[q, 1] = net[ho].mean() if ho.any() else np.nan
    return out


def draw_shifts(ng, n=N_SHIFTS, seed=SEED):
    rng = np.random.default_rng(seed)
    lo, hi = MIN_SHIFT // SHIFT_STEP, (ng - MIN_SHIFT) // SHIFT_STEP
    return rng.integers(lo, hi, size=n) * SHIFT_STEP


def p_at_least(obs, null):
    null = null[np.isfinite(null)]
    return float((1 + (null >= obs).sum()) / (1 + len(null))) if np.isfinite(obs) and len(null) else np.nan


def cell(grid_days, F, z, thr, H, side, shifts):
    """One cell: events, per-half mean net / day-vote t / shift p, worst trade, 25bp stress."""
    flag = (z >= thr) if side == "short" else (z <= -thr)
    flag = flag & np.isfinite(F)
    idx = pick_events(flag, H)
    if not len(idx):
        return None
    net = event_net(F, idx, side, H)
    days = grid_days[idx + 1]
    null = shift_null(flag, F, H, side, shifts, grid_days)
    res = dict(idx=idx, net=net, days=days, worst=float(net.min()), n=len(idx))
    for h, m in zip(("tu", "ho"), half_masks(days)):
        k = 0 if h == "tu" else 1
        mean, t, nd = cs.day_mean_t(net[m], days[m]) if m.sum() > 2 else (float(net[m].mean()) if m.any() else np.nan, np.nan, 0)
        res[h] = dict(n=int(m.sum()), days=nd, net=mean, t=t, p=p_at_least(float(net[m].mean()) if m.any() else np.nan, null[:, k]),
                      stress=float(net[m].mean() - 0.0013) if m.any() else np.nan)
    return res


def positive_both(c):
    return c is not None and c["tu"]["n"] >= 5 and c["ho"]["n"] >= 5 and c["tu"]["net"] > 0 and c["ho"]["net"] > 0


def passes(primary, plateau_positive):
    """The three-fold bar: both halves positive with t >= 2, shift p < 0.05 on both halves, and a plateau of >= 7 of 9."""
    if primary is None:
        return False
    ok = all(primary[h]["net"] > 0 and primary[h]["t"] >= 2 and primary[h]["p"] < 0.05 for h in ("tu", "ho"))
    return bool(ok and plateau_positive >= 7)


# ---------------------------------------------------------------- report

def main():
    grid, coins, O, C, M = build_panel()
    ng = len(grid)
    grid_days = cs.day_index(grid)
    R = bar_returns(O, C, M)
    z = zscore(R)
    btc = coins.index("BTCUSDT")
    shifts = draw_shifts(ng)
    cells, L = {}, []
    L.append(f"backtest/market_fade.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(coins)} PIT coins, {np.isfinite(R).sum():,} 4h bars with >= {MIN_COINS} members; "
             f"tune < 2024-08-29; 12bp on notional, shorts receive no funding; {N_SHIFTS} day-shifts as the null")
    L.append(f"signal bars: z>=1.5 {int((z >= 1.5).sum())}, z>=2.0 {int((z >= 2.0).sum())}, z>=2.5 {int((z >= 2.5).sum())}; z<=-2.0 {int((z <= -2.0).sum())}")
    L.append("")
    L.append(f"{'cell':<34}{'TUNE n/ mean net / t / shift-p':<42}{'HOLDOUT n / mean net / t / shift-p':<42}worst trade   25bp stress (tune/hold)")
    for inst in ("basket", "BTC"):
        for side in ("short", "long"):
            for H in HOLDS:
                F, fwd = forward_returns(O, C, M, H)
                if inst == "BTC":
                    F = fwd[:, btc]
                for thr in THRS:
                    c = cell(grid_days, F, z, thr, H, side, shifts)
                    cells[(inst, thr, H, side)] = c
                    tag = "PRIMARY " if (inst, thr, H, side) == PRIMARY else ("ref " if side == "long" else "")
                    name = f"{tag}{inst} {side} z{'>=' if side == 'short' else '<=-'}{thr} H{H}"
                    if c is None:
                        L.append(f"{name:<34}no events")
                        continue
                    f = lambda s: f"n{s['n']:4d} {s['net'] * 100:+6.2f}% t{s['t']:+5.1f} p{s['p']:.3f}"
                    L.append(f"{name:<34}{f(c['tu']):<42}{f(c['ho']):<42}{c['worst'] * 100:+7.2f}%   {c['tu']['stress'] * 100:+.2f}% / {c['ho']['stress'] * 100:+.2f}%")
    prim = cells[PRIMARY]
    plateau = sum(1 for thr in THRS for H in HOLDS if positive_both(cells[("basket", thr, H, "short")]))
    ok = passes(prim, plateau)
    L += ["", f"PRIMARY: {'PASS' if ok else 'NO PASS'}   plateau (basket short, positive on both halves): {plateau} of 9"]
    if prim is not None:
        yrs = (cs.D0 + prim["days"].astype("timedelta64[D]")).astype("datetime64[Y]").astype(int) + 1970
        L.append("primary by year (events, mean net, sum of net on 1x notional): " + "  ".join(
            f"{y}: {int((yrs == y).sum())} / {prim['net'][yrs == y].mean() * 100:+.2f}% / {prim['net'][yrs == y].sum() * 100:+.1f}%" for y in sorted(set(yrs.tolist()))))
        q = np.quantile(prim["net"], [0.05, 0.5, 0.95])
        L.append(f"primary trade distribution: worst {prim['worst'] * 100:+.2f}%, 5th pct {q[0] * 100:+.2f}%, median {q[1] * 100:+.2f}%, 95th {q[2] * 100:+.2f}%; "
                 f"{prim['n']} trades")
        fb, _ = forward_returns(O, C, M, PRIMARY[2])
        fin = np.isfinite(fb)
        un = [(-fb[m & fin] - FEE).mean() for m in half_masks(grid_days)]
        L.append(f"unconditional basket short at EVERY bar, 20h (the drift of the period), tune / holdout: {un[0] * 100:+.3f}% / {un[1] * 100:+.3f}% a trade")
    mir = cells[("basket", 2.0, 5, "long")]
    t3 = bool(mir and prim and mir["tu"]["net"] > prim["tu"]["net"] and mir["ho"]["net"] > prim["ho"]["net"])
    t1 = not ok and prim is not None and (any(prim[h]["p"] >= 0.05 or prim[h]["t"] < 2 for h in ("tu", "ho")))
    L += ["", "REGISTERED PREDICTIONS",
          f"  T1 the primary cell does not pass (a half with shift p >= 0.05 or t < 2) -> {'RIGHT' if t1 else 'WRONG'}",
          f"  T2 fewer than 7 of 9 basket-short cells positive on both halves -> {'RIGHT' if plateau < 7 else 'WRONG'} ({plateau})",
          f"  T3 the mirror (long after z <= -2, H5) beats the short on both halves -> {'RIGHT' if t3 else 'WRONG'}",
          f"  T4 worst primary trade loses more than 8% -> {'RIGHT' if prim is not None and prim['worst'] < -0.08 else 'WRONG'} ({prim['worst'] * 100:+.2f}%)" if prim else "  T4 no events"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

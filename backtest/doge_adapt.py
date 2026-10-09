"""ANALYSE TODAY, TRADE TODAY - does DOGE's best RECENT scalping rule keep working for the next few hours? (2026-10-09)

THE USER (2026-10-09): "instead of trying finding a strategy wholeass backtested for years you will analyse the coin
today or some day before and then live ... predict yourself and then see in real time ... the end result will be a
strategy for scalping that is working today and worth a shot today."

The repo has already killed scalping DOGE over YEARS (scalp_1m.py, scalp_15m.py, btc_doge.py) and picking last MONTH's
winner (doge_focus.py). What was never tested is the user's actual method: read the last hours or days, pick what is
working, trade it for the next few hours. Its honest historical form is a ROLLING WALK-FORWARD on Bitget's own 1-minute
DOGE perp bars (backtest/bitget_1m.py), the last 90 days:
    every 6 hours (00/06/12/18 UTC), rank every rule in the menu by its net result over the trailing window - 6h, 12h,
    24h, 3 days or 7 days, counting only trades CLOSED before the block starts - and trade the winner for the next 6
    hours, only if it made money in its window (a trader would not pick a losing rule); then repeat.

THE MENU (signal on a closed 1m or 5m bar, filled at the next 1m bar's open; stop and target checked on every later 1m
bar, the STOP FIRST when one bar touches both; a time stop after 30 min (1m signals) / 120 min (5m); one position at a
time per rule; stops filled at the worse of the stop and the bar's open):
    vwap_fade k      close k x ATR beyond the session VWAP (from 00:00 UTC) with RSI(7) < 30 / > 70 -> fade (k 1.5, 3)
    bb_revert        a close back inside Bollinger(20, 2) after a close outside -> fade
    breakout N       close beyond the prior N-bar high / low on volume > 2x its 20-bar average -> follow (N 20, 60)
    ema_pullback     EMA 9 > 21 > 50 and the bar dips to EMA 21 and closes up -> long (mirror short)
    level_bounce     support / resistance = previous UTC day's high, low, close; today's open; the 4-hour high and low
                     (ending 15 min back); the bar wicks within 8bp of the nearest level and closes back on its side
                     with a candle that agrees -> bounce
    orb              the first 30 min of 00:00 / 08:00 / 13:30 UTC; the first 1m close beyond it in the next 3 hours ->
                     follow (1m only)
    rsi_fade lo/hi   RSI(14) crossing under lo / over hi -> fade (20/80, 30/70)
  x timeframe 1m / 5m, x side both / long only / short only, x stop 1 or 2 ATR(14) of the signal timeframe, x target
  1R or 2R = 228 rules. Costs per round trip: 12bp (Bitget taker both sides - the repo's standard), 8bp (maker entry),
  4bp (maker both). The maker rows assume the next-open fill at the maker rate, so they are OPTIMISTIC.
Read at 1x: returns are % of the position per trade; leverage multiplies them, and the losses with them.

REGISTERED BEFORE THE RUN (2026-10-09, before any result was seen)
    P1  Persistence is ~0: across rules, the trailing window's net and the next 6 hours' net are rank-correlated at
        |mean rho| < 0.05 for every window.
    P2  The walk-forward loses at 12bp for every window (mean net a trade < 0), and its edge over picking a RANDOM rule
        among those that also made money in the window is within 2 standard errors of zero.
    P3  At 4bp (maker both, optimistic) the best window is within 2 se of zero.
    P4  Fewer than 10% of the 228 rules are net positive over the whole 90 days at 12bp.
    P5  On the most recent 7 days alone the picture is the same (no "today is different" regime visible).

RESULT (2026-10-09 16:34 UTC, logs/doge_adapt.txt; 2026-07-11 .. 2026-10-09, 330 six-hour blocks, 0 data gaps)
    - P4 RIGHT: 0 of 228 rules are net positive over the 90 days at 12bp, 0 at 8bp, 1 at 4bp. The best at 12bp (5m RSI(14)
      under 20, long, 2 ATR stop, 2R) is -0.04% a trade on 41 trades.
    - P2 RIGHT: picking the recent winner LOSES at 12bp for every window - net a trade 6h -0.086%, 12h -0.144%, 24h -0.150%,
      3d -0.114%, 7d -0.121% (t by block -2.1 to -7.8; 15-34% of blocks up). That is about the fee: before costs the
      picked rule makes ~0 over the next 6 hours. Partly wrong on the edge over a random winner: the 6h window beats a
      random positive rule by +0.148% a block (t +2.92) - picking the best does select something at the shortest window
      - but not enough to pay the fee (still -0.086% a trade). Every other window is within 2 se of random.
    - P1 WRONG, and why it does not help: rankings DO persist (rho +0.45..+0.60 at 12bp) - but it is the fee: busy rules
      lose in every window, quiet ones sit near zero. At 4bp it falls to +0.20..+0.33, and the walk-forward still loses.
    - P3 RIGHT: at 4bp (maker both, optimistic) the best window (7d) is -0.002% a trade; every window <= 0.
    - P5 RIGHT at 12bp: last 7 days 6h -0.120%, 12h -0.193%, 24h -0.224%, 3d -0.041%, 7d -0.056% a trade. At 8bp the 3d
      window reads +0.077% a trade on 36 trades (t +0.60) - noise.
    Reading: on DOGE's last 90 days, "analyse the last hours or days and trade what is working" does not find a scalping
    rule that keeps working for the next 6 hours; the fee is the whole result. The live forward test (doge_live.py,
    logs/doge_live/) runs the procedure's own picks forward from 2026-10-09 16:35 UTC.

    python -m backtest.doge_adapt               (needs backtest/bitget_1m.py's cache: DOGE, 90 days)
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import bitget_1m as bg  # noqa: E402

LOG = ROOT / "logs" / "doge_adapt.txt"
MIN, H6, DAY = 60_000, 6 * 3_600_000, 86_400_000
COSTS = (12, 8, 4)
WINDOWS = {"6h": 6 * 3_600_000, "12h": 12 * 3_600_000, "24h": DAY, "3d": 3 * DAY, "7d": 7 * DAY}
TIME_STOP = {1: 30, 5: 120}                       # minutes
TOL = 0.0008                                      # level touch tolerance (8bp)


# ---------------------------------------------------------------- indicators (each value known at its bar's close)

def wilder(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).ewm(alpha=1 / n, adjust=False).mean().to_numpy()


def rsi(c: np.ndarray, n: int) -> np.ndarray:
    d = np.r_[0.0, np.diff(c)]
    up, dn = wilder(np.where(d > 0, d, 0.0), n), wilder(np.where(d < 0, -d, 0.0), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(dn > 0, 100 - 100 / (1 + up / dn), 100.0)


def atr(h, l, c, n=14):
    pc = np.r_[c[0], c[:-1]]
    return wilder(np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc))), n)


def ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().to_numpy()


def bars(d1: pd.DataFrame, tf: int) -> pd.DataFrame:
    """tf-minute bars from 1m bars, aligned to UTC; `t` is the bar's OPEN, `close_t` when it is known."""
    if tf == 1:
        b = d1.copy()
    else:
        g = d1.t // (tf * MIN) * (tf * MIN)
        b = d1.groupby(g).agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), v=("v", "sum"),
                              n=("t", "size")).reset_index().rename(columns={"index": "t"})
        b = b[b.n == tf].drop(columns="n").reset_index(drop=True)      # complete bars only
        b = b.rename(columns={b.columns[0]: "t"})
    b["close_t"] = b.t + tf * MIN
    return b


def signals(b: pd.DataFrame, d1: pd.DataFrame, tf: int) -> dict:
    """{entry name: (long bool array, short bool array)} on the tf bars."""
    o, h, l, c, v = (b[k].to_numpy(float) for k in "ohlcv")
    t = b.t.to_numpy()
    n = len(c)
    A = atr(h, l, c)
    out = {}
    # session VWAP from 00:00 UTC
    day = t // DAY
    tp = (h + l + c) / 3
    cv = pd.Series(tp * v).groupby(day).cumsum().to_numpy()
    vv = pd.Series(v).groupby(day).cumsum().to_numpy()
    vwap = np.where(vv > 0, cv / np.where(vv > 0, vv, 1), c)
    r7, r14 = rsi(c, 7), rsi(c, 14)
    for k in (1.5, 3.0):
        out[f"vwap_fade{k:g}"] = ((c < vwap - k * A) & (r7 < 30), (c > vwap + k * A) & (r7 > 70))
    # Bollinger(20, 2) re-entry
    m = pd.Series(c).rolling(20).mean().to_numpy()
    sd = pd.Series(c).rolling(20).std(ddof=0).to_numpy()
    lo_b, hi_b = m - 2 * sd, m + 2 * sd
    pc = np.r_[np.nan, c[:-1]]
    with np.errstate(invalid="ignore"):
        out["bb_revert"] = ((pc < np.r_[np.nan, lo_b[:-1]]) & (c > lo_b), (pc > np.r_[np.nan, hi_b[:-1]]) & (c < hi_b))
    # breakout on volume
    va = pd.Series(v).rolling(20).mean().shift(1).to_numpy()
    for N in (20, 60):
        hh = pd.Series(h).rolling(N).max().shift(1).to_numpy()
        ll = pd.Series(l).rolling(N).min().shift(1).to_numpy()
        with np.errstate(invalid="ignore"):
            out[f"breakout{N}"] = ((c > hh) & (v > 2 * va), (c < ll) & (v > 2 * va))
    # EMA pullback in trend
    e9, e21, e50 = ema(c, 9), ema(c, 21), ema(c, 50)
    out["ema_pullback"] = ((e9 > e21) & (e21 > e50) & (l <= e21) & (c > e21) & (c > o),
                           (e9 < e21) & (e21 < e50) & (h >= e21) & (c < e21) & (c < o))
    # support / resistance levels
    g = d1.assign(day=d1.t // DAY).groupby("day")
    dd = pd.DataFrame({"H": g.h.max(), "L": g.l.min(), "C": g.c.last(), "O": g.o.first()})
    prev = dd.shift(1)
    lv = [prev.H.reindex(day).to_numpy(), prev.L.reindex(day).to_numpy(), prev.C.reindex(day).to_numpy(),
          dd.O.reindex(day).to_numpy()]
    back, win = (15, 225) if tf == 1 else (3, 45)
    lv += [pd.Series(h).shift(back).rolling(win).max().to_numpy(), pd.Series(l).shift(back).rolling(win).min().to_numpy()]
    L = np.vstack(lv).T                                                   # n x 6
    with np.errstate(invalid="ignore"):
        below = np.where(L < c[:, None], L, -np.inf).max(axis=1)
        above = np.where(L > c[:, None], L, np.inf).min(axis=1)
        out["level_bounce"] = ((np.isfinite(below)) & (l <= below * (1 + TOL)) & (c > o),
                               (np.isfinite(above)) & (h >= above * (1 - TOL)) & (c < o))
    # opening-range breakout (1m only)
    if tf == 1:
        lo_s, sh_s = np.zeros(n, bool), np.zeros(n, bool)
        tod = t % DAY
        for start in (0, 8 * 60, 13 * 60 + 30):
            s0 = start * MIN
            for dy in np.unique(day):
                idx = np.flatnonzero((day == dy) & (tod >= s0) & (tod < s0 + 30 * MIN))
                if len(idx) < 30:
                    continue
                rh, rl = h[idx].max(), l[idx].min()
                after = np.flatnonzero((day == dy) & (tod >= s0 + 30 * MIN) & (tod < s0 + 210 * MIN))
                up = after[c[after] > rh]
                dn = after[c[after] < rl]
                if len(up):
                    lo_s[up[0]] = True
                if len(dn):
                    sh_s[dn[0]] = True
        out["orb"] = (lo_s, sh_s)
    # RSI(14) fades
    pr = np.r_[50.0, r14[:-1]]
    for lo, hi in ((20, 80), (30, 70)):
        out[f"rsi_fade{lo}"] = ((pr >= lo) & (r14 < lo), (pr <= hi) & (r14 > hi))
    warm = np.arange(n) < 240 // tf + 60                               # indicators warming up
    return {k: (np.nan_to_num(a, nan=0).astype(bool) & ~warm, np.nan_to_num(s, nan=0).astype(bool) & ~warm)
            for k, (a, s) in out.items()}, A


# ---------------------------------------------------------------- one rule, the whole period

def simulate(d1, b, tf, lo_sig, sh_sig, A, stop_k, tgt_r):
    """Trades of one rule: arrays (entry_t, exit_t, gross return at 1x)."""
    t1, o1, h1, l1, c1 = (d1[k].to_numpy() for k in ("t", "o", "h", "l", "c"))
    pos1 = {int(x): i for i, x in enumerate(t1)}
    H = TIME_STOP[tf]
    ev = sorted([(i, 1) for i in np.flatnonzero(lo_sig)] + [(i, -1) for i in np.flatnonzero(sh_sig)])
    ct = b.close_t.to_numpy()
    free_t, rows = -1, []
    for i, side in ev:
        if ct[i] <= free_t:
            continue
        j0 = pos1.get(int(ct[i]))                                     # the 1m bar that opens as the signal bar closes
        if j0 is None or j0 + H >= len(t1):
            continue
        e = o1[j0]
        dist = stop_k * A[i]
        if not np.isfinite(dist) or dist <= 0:
            continue
        stop = e - side * dist
        tgt = e + side * tgt_r * dist
        hh, ll = h1[j0:j0 + H], l1[j0:j0 + H]
        if side > 0:
            s_hit, t_hit = ll <= stop, hh >= tgt
        else:
            s_hit, t_hit = hh >= stop, ll <= tgt
        si = np.flatnonzero(s_hit)
        ti = np.flatnonzero(t_hit)
        s0 = si[0] if len(si) else H
        g0 = ti[0] if len(ti) else H
        if s0 <= g0 and s0 < H:                                        # stop first (also when the same bar)
            k = j0 + s0
            x = min(o1[k], stop) if side > 0 else max(o1[k], stop)
            if k == j0:
                x = stop
        elif g0 < H:
            k = j0 + g0
            x = tgt
        else:
            k = j0 + H - 1
            x = c1[k]
        ret = side * (x / e - 1)
        rows.append((t1[j0], t1[k] + MIN, ret))
        free_t = t1[k] + MIN
    if not rows:
        return np.zeros(0, np.int64), np.zeros(0, np.int64), np.zeros(0)
    r = np.array(rows)
    return r[:, 0].astype(np.int64), r[:, 1].astype(np.int64), r[:, 2]


def menu(d1):
    rules = {}
    for tf in (1, 5):
        b = bars(d1, tf)
        sig, A = signals(b, d1, tf)
        for name, (lo, sh) in sig.items():
            for side, stop_k, tgt_r in itertools.product(("both", "long", "short"), (1, 2), (1, 2)):
                L_ = lo if side in ("both", "long") else np.zeros_like(lo)
                S_ = sh if side in ("both", "short") else np.zeros_like(sh)
                rules[(f"{tf}m", name, side, stop_k, tgt_r)] = simulate(d1, b, tf, L_, S_, A, stop_k, tgt_r)
    return rules


# ---------------------------------------------------------------- the walk-forward

def window_sums(ent, ext, ret, starts, span, cost):
    """per block start s: (net sum, count) of trades CLOSED in [s - span, s), and (net sum, count) ENTERED in
    [s, s + 6h)."""
    net = ret - cost / 1e4
    o = np.argsort(ext, kind="stable")
    ex_s, cs = ext[o], np.r_[0.0, np.cumsum(net[o])]
    a, z = np.searchsorted(ex_s, starts - span, "left"), np.searchsorted(ex_s, starts, "left")
    o2 = np.argsort(ent, kind="stable")
    en_s, cs2 = ent[o2], np.r_[0.0, np.cumsum(net[o2])]
    a2, z2 = np.searchsorted(en_s, starts, "left"), np.searchsorted(en_s, starts + H6, "left")
    return cs[z] - cs[a], z - a, cs2[z2] - cs2[a2], z2 - a2


def spearman(x, y):
    rx, ry = pd.Series(x).rank().to_numpy(), pd.Series(y).rank().to_numpy()
    if rx.std() == 0 or ry.std() == 0:
        return np.nan
    return float(np.corrcoef(rx, ry)[0, 1])


def walk(rules, starts, cost, span):
    keys = list(rules)
    W = np.zeros((len(keys), len(starts)))
    Wn = np.zeros_like(W)
    R = np.zeros_like(W)
    Rn = np.zeros_like(W)
    for k, key in enumerate(keys):
        W[k], Wn[k], R[k], Rn[k] = window_sums(*rules[key], starts, span, cost)
    elig = (Wn >= 3) & (W > 0)
    pick_r, pick_n, base_r, rho, chosen = [], [], [], [], []
    for j in range(len(starts)):
        rho.append(spearman(W[:, j], R[:, j]))
        e = np.flatnonzero(elig[:, j])
        if not len(e):
            chosen.append(None)
            continue
        best = e[np.lexsort((-Wn[e, j], -W[e, j]))[0]]
        chosen.append(keys[best])
        pick_r.append(R[best, j]); pick_n.append(Rn[best, j])
        base_r.append(R[e, j].mean())
    return dict(pick_r=np.array(pick_r), pick_n=np.array(pick_n), base_r=np.array(base_r),
                rho=np.nanmean(rho), chosen=chosen, blocks=len(starts), W=W, R=R, Rn=Rn)


def fmt(res, label):
    p, n, bse = res["pick_r"], res["pick_n"], res["base_r"]
    if not len(p):
        return f"  {label:30} no block had an eligible rule"
    se = p.std(ddof=1) / np.sqrt(len(p)) if len(p) > 1 else np.nan
    dif = p - bse
    sed = dif.std(ddof=1) / np.sqrt(len(dif)) if len(dif) > 1 else np.nan
    per_trade = p.sum() / max(n.sum(), 1)
    return (f"  {label:30} traded {len(p):3}/{res['blocks']} blocks, {int(n.sum()):4} trades | net a trade {per_trade * 100:+.3f}% "
            f"| a block {p.mean() * 100:+.3f}% (t {p.mean() / se if se else np.nan:+.2f}), up {np.mean(p > 0) * 100:3.0f}% | "
            f"sum {p.sum() * 100:+7.1f}% | vs random winner {dif.mean() * 100:+.3f}% (t {dif.mean() / sed if sed else np.nan:+.2f}) "
            f"| persistence rho {res['rho']:+.3f}")


def main():
    d1 = bg.fetch("DOGE", 90, quiet=True)
    d1 = d1[d1.t >= d1.t.max() - 90 * DAY].reset_index(drop=True)
    rules = menu(d1)
    first = (int(d1.t.min()) // DAY + 8) * DAY                        # room for the 7-day window
    last = int(d1.t.max()) // H6 * H6 - H6                            # the last full 6h block
    starts = np.arange(first, last + 1, H6, dtype=np.int64)
    recent = starts >= starts.max() - 7 * DAY
    lines = [f"backtest/doge_adapt.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; Bitget DOGE perp 1m, "
             f"{pd.Timestamp(d1.t.min(), unit='ms'):%Y-%m-%d} .. {pd.Timestamp(d1.t.max(), unit='ms'):%Y-%m-%d %H:%M}; "
             f"{len(rules)} rules; {len(starts)} six-hour blocks; returns at 1x", ""]
    # whole-period rule stats
    lines.append("WHOLE PERIOD (every rule, 90 days): share net positive, and the best five at 12bp (hindsight)")
    for cost in COSTS:
        tot = {k: (r[2] - cost / 1e4).sum() for k, r in rules.items() if len(r[2])}
        lines.append(f"  {cost:2}bp: {sum(v > 0 for v in tot.values())} of {len(tot)} rules net positive "
                     f"({np.mean([v > 0 for v in tot.values()]) * 100:.0f}%)")
    tot12 = sorted(((r[2] - 0.0012).sum(), k, len(r[2]), (r[2] - 0.0012).mean()) for k, r in rules.items() if len(r[2]))
    for s, k, nn, mm in tot12[::-1][:5]:
        lines.append(f"     {str(k):45} {nn:5} trades, net {mm * 100:+.3f}% a trade, sum {s * 100:+.1f}%")
    lines.append("")
    for cost in COSTS:
        lines.append(f"WALK-FORWARD at {cost}bp a round trip (pick the best rule of the trailing window, trade it 6 hours)")
        for wn, span in WINDOWS.items():
            res = walk(rules, starts, cost, span)
            lines.append(fmt(res, f"window {wn}, all 90 days"))
            sub = walk(rules, starts[recent], cost, span)
            lines.append(fmt(sub, f"window {wn}, last 7 days"))
        lines.append("")
    # what the procedure picks NOW (for the live test)
    now_start = np.array([int(d1.t.max()) // MIN * MIN + MIN], dtype=np.int64)
    lines.append("WHAT EACH WINDOW PICKS NOW (12bp; trades closed before the last bar):")
    for wn, span in WINDOWS.items():
        keys = list(rules)
        best, bw = None, (0.0, 0)
        for key in keys:
            w, wn_, _, _ = window_sums(*rules[key], now_start, span, 12)
            if wn_[0] >= 3 and (w[0], wn_[0]) > bw:
                best, bw = key, (w[0], int(wn_[0]))
        lines.append(f"  {wn:4}: {best}  (window net {bw[0] * 100:+.2f}% on {bw[1]} trades)" if best else f"  {wn:4}: none made money")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

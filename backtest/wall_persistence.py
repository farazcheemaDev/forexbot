"""DOES A PERSISTENT ORDER-BOOK WALL PREDICT A BOUNCE? - Step 1 of the v2 '$20 order-book bot' spec, on the Bitget DOGE book days (2026-11-06).

THE USER (2026-11-06): "yes" - run v2's Step 1 (orderbook_bot_20usd_v2_remediation_spec.md) on the data we already hold, with the fixes the review asked for:
a wall tracker that attributes trades to the right side, a fill model from the tape instead of 'a simulated entry', a day split that keeps one unread day,
the project's own bar, one independent event per wall, and the pass rule written down before any result. No keys, no orders, nothing trades.

THE HYPOTHESIS (v2, untouched): a wall that has rested >= 20 s without being pulled, within 5 bp of the touch, with top-of-book imbalance pointing the
same way, is a place where price bounces. Long: a bid wall and I_L1 >= +0.60; short: an ask wall and I_L1 <= -0.60. I_L1 = (bid size - ask size) / (sum) at level 1.

THE TRADE (v2's, the same for signal and control): a post-only limit at min(wall price + 1 tick, best bid) (short: max(wall - 1 tick, best ask));
0.5 s latency; queue ahead = the displayed size at that price; filled only when the TAPE fills it (a taker through the price, or enough taker volume AT
the price to clear the queue: book_hist.maker_fill); cancelled after 30 s, when the wall is pulled, or when the mid is 10 bp away. After a fill: a maker
take-profit at +tp bp, a stop-market at -sl bp (a taker, executed 0.5 s after the trigger at the touch), at 90 s the take-profit becomes a maker limit at the
touch for 30 s (the scratch), at 120 s a forced taker exit. One position at a time, 15 s cooldown, one attempt per wall. Fees = Hyperliquid base: maker
1.5 bp (entry, target, scratch), taker 4.5 bp (stop, forced exit). Brackets tp = sl = 4, 6, 8, 12 bp; 8 is the primary (v2's config).

THE CONTROL: for every signal attempt, 5 random attempts the same day, a random second within +-15 minutes, the SAME side and the SAME distance behind the
touch in ticks, with no wall and no imbalance condition, through the same fill and exit code. Whatever the signal earns beyond them is the wall's and the
imbalance's information; the fill selection (a bid is filled when price falls into it) is in both.

DATA: Bitget DOGEUSDT perp, Tardis' first-of-month days, the book rebuilt from the update stream every second to its best 15 levels per side
(backtest/wall_levels.py, the validated book_hist.rebuild), and the complete tape. The wall tracker sees 15 levels (Hyperliquid's l2Book gives 20) and
one snapshot a second (Hyperliquid's is no faster than every 0.5).
    tune days     2025-03-01  2025-06-01  2025-09-01  2026-06-01   (2026-06-01 is here because the 20 s age came from its wall statistics)
    confirm days  2025-12-01  2026-03-01  2026-09-01               (2026-09-01 is the one real update-stream day nobody has read). READ ONCE, ONLY
                  IF THE TUNE HALF PASSES; `--confirm` is needed and is refused otherwise.

REGISTERED 2026-11-06, BEFORE ANY WALL STATISTIC OF ANY DAY WAS COMPUTED (the numbers in REGISTERED below are pinned by a digest in the tests)
    No parameter is tuned: the values are v2's. RULE for a half of the days, bracket 8/8 (the primary): at least 30 FILLED signal trades; mean gross
    >= +4.5 bp a filled trade; mean net of fees > 0; and the signal beats its matched random entries by a one-sided Welch t >= 2.0 on gross. The tune half
    must pass for the confirm half to be read; both must pass for a LEAD. A LEAD is not a profit: it earns the right to a 20+ day forward record on
    Hyperliquid's own feed (the project's registered K3 asks for 20 confirming days, which seven days cannot give). The other brackets are reported with
    a Holm correction over the four. Nothing here can say PASS.
    W1  Of the walls the tracker registers, fewer than 25% reach 20 s of age without being pulled or consumed.
    W2  The resting entry fills within 30 s in 25-60% of attempts.
    W3  The signal's gross edge per filled trade at 8/8 minus the matched random entries' is between -1 and +3 bp: the tune half FAILS the rule
        (my probability of that: 85%).
    W4  Filled signal attempts move less in the trade's direction over the next 30 s than unfilled ones (adverse selection), by >= 0.5 bp.
    W5  Mean NET per filled trade at 8/8 is negative, between -3 and -7 bp.

RESULT (2026-11-06, tune half, logs/wall_persistence.txt): KILLED at the first line of the rule. 247 signal attempts on the four tune days, ONE filled
    (0.4%; the matched random entries at the same distance filled 22%: 276-300 of 1,235 at every bracket); 8/8 gross -8.0 bp, net -14.0 bp on that one
    trade; the rule needs 30. The confirm days (2025-12-01, 2026-03-01, 2026-09-01) were NOT read. The 246 unfilled attempts moved +0.53 bp in the signal's
    direction over the next 30 s (filled: -6.99, n = 1): the one-tick lean exists, a resting entry cannot take it. Walls: 21,073 registered, 90 (0.4%)
    reached 20 s unpulled. Predictions: W1 right (0.4% against under 25%); W2 WRONG (fill rate 0.4%, not 25-60%); W3 right (the rule fails; no edge
    estimate is possible with one fill); W4 right in direction (+0.53 against -6.99), but the filled side is a single trade; W5 uninformative (n = 1).
    Tests tests/test_wall_persistence.py 31; planted-bug check 32 of 32 real mutants caught and the do-nothing control survived (run before the data).

    python -m backtest.wall_persistence              the tune half only
    python -m backtest.wall_persistence --confirm    the confirm half, once, only if the tune half passed
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import book_hist as bh  # noqa: E402
from backtest.wall_levels import K, levels_for  # noqa: E402

LOG = ROOT / "logs" / "wall_persistence.txt"
REGISTERED = dict(wall_z=2.5, wall_median_mult=3.5, wall_min_age_s=20.0, wall_max_cancel=0.35, wall_max_dist_bp=5.0, l1_imb=0.60, levels=15,
                  brackets_bp=[4.0, 6.0, 8.0, 12.0], primary_bp=8.0, ttl_s=30, cancel_away_bp=10.0, latency_ms=500, scratch_s=90, hard_s=120,
                  cooldown_s=15, maker_bp=1.5, taker_bp=4.5, controls=5, control_window_s=900, min_filled=30, min_gross_bp=4.5, min_excess_t=2.0,
                  tune=["2025-03-01", "2025-06-01", "2025-09-01", "2026-06-01"], confirm=["2025-12-01", "2026-03-01", "2026-09-01"])
REGISTRY_SHA256 = "2c7c283bdda3fbb8f0a2a27e6c11e4c5c836b0171dafc4d36c89aec050789553"

WALL_Z, WALL_MEDIAN_MULT = REGISTERED["wall_z"], REGISTERED["wall_median_mult"]
WALL_MIN_AGE_MS = int(REGISTERED["wall_min_age_s"] * 1000)
WALL_MAX_CANCEL, WALL_MAX_DIST_BP, L1_IMB = REGISTERED["wall_max_cancel"], REGISTERED["wall_max_dist_bp"], REGISTERED["l1_imb"]
TTL_MS, CANCEL_AWAY_BP, LAT_MS = REGISTERED["ttl_s"] * 1000, REGISTERED["cancel_away_bp"], REGISTERED["latency_ms"]
SCRATCH_MS, HARD_MS, COOLDOWN_MS = REGISTERED["scratch_s"] * 1000, REGISTERED["hard_s"] * 1000, REGISTERED["cooldown_s"] * 1000
MAKER_BP, TAKER_BP = REGISTERED["maker_bp"], REGISTERED["taker_bp"]
N_CONTROLS, CONTROL_WINDOW_S = REGISTERED["controls"], REGISTERED["control_window_s"]
BRACKETS, PRIMARY = REGISTERED["brackets_bp"], REGISTERED["primary_bp"]
TUNE, CONFIRM = REGISTERED["tune"], REGISTERED["confirm"]
EPS = 1e-9


def registry_digest() -> str:
    return hashlib.sha256(json.dumps(REGISTERED, sort_keys=True).encode()).hexdigest()


# ---------------------------------------------------------------- the wall tracker (side-specific trade attribution)
class Wall:
    __slots__ = ("px", "first", "max_q", "cur_q", "pulled", "invalid_at", "dead_at")

    def __init__(self, px: float, t: int, q: float):
        self.px, self.first, self.max_q, self.cur_q, self.pulled = px, t, q, q, 0.0
        self.invalid_at = None
        self.dead_at = None


class WallTracker:
    """Walls on ONE side of the book. A drop in a wall's size is a PULL unless taker volume explains it: taker volume at the wall's price, or any taker
    trade THROUGH the wall's price (then the level was swept). Each side gets its own trade totals, so one side's update cannot erase the other's."""

    def __init__(self, bid_side: bool):
        self.bid = bid_side
        self.walls: dict = {}
        self.history: list = []

    def update(self, t: int, prices: np.ndarray, qtys: np.ndarray, traded_at: dict, through_px) -> None:
        ok = ~np.isnan(prices) & (qtys > 0)
        if ok.sum() < 5:
            return
        p, q = prices[ok], qtys[ok]
        cutoff = max(q.mean() + WALL_Z * q.std(), WALL_MEDIAN_MULT * float(np.median(q)))
        lo, hi = float(p.min()), float(p.max())
        cur = dict(zip(p.tolist(), q.tolist()))
        for px in list(self.walls):
            w = self.walls[px]
            if px < lo - EPS or px > hi + EPS:                     # the level left the 15-level window: that is not a pull
                w.dead_at = t
                del self.walls[px]
                continue
            nq = cur.get(px, 0.0)
            drop = w.cur_q - nq
            if drop > 0:
                swept = through_px is not None and ((through_px < px - EPS) if self.bid else (through_px > px + EPS))
                explained = drop if swept else min(drop, traded_at.get(px, 0.0))
                w.pulled += drop - explained
            w.cur_q = nq
            if nq > w.max_q:
                w.max_q = nq
            if w.invalid_at is None and w.pulled / w.max_q >= WALL_MAX_CANCEL:
                w.invalid_at = t                                    # stays tracked (and invalid) while it is still big: no re-registration
            if nq < 0.5 * cutoff:
                w.dead_at = t
                del self.walls[px]
        for px, qq in cur.items():
            if qq >= cutoff and px not in self.walls:
                w = Wall(px, t, qq)
                self.walls[px] = w
                self.history.append(w)

    def valid(self, t: int, best_px: float):
        """(distance in price, wall) of the nearest wall that is old enough, not pulled, at or behind the touch and within WALL_MAX_DIST_BP; else None."""
        best = None
        for px, w in self.walls.items():
            if w.invalid_at is not None or t - w.first < WALL_MIN_AGE_MS:
                continue
            dist = (best_px - px) if self.bid else (px - best_px)
            if dist < -EPS or dist / best_px * 1e4 > WALL_MAX_DIST_BP:
                continue
            if best is None or dist < best[0]:
                best = (dist, w)
        return best


# ---------------------------------------------------------------- one day
def infer_tick(BP: np.ndarray, AP: np.ndarray) -> float:
    px = np.unique(np.concatenate([BP[:, 0], AP[:, 0]]))
    px = px[~np.isnan(px)]
    d = np.diff(px)
    return float(round(d[d > 1e-12].min(), 10))


def prep_day(day: str) -> dict:
    g, _ = levels_for(day)
    T = g.t.to_numpy("int64")
    BP = g[[f"bp{i}" for i in range(1, K + 1)]].to_numpy(float)
    BQ = g[[f"bq{i}" for i in range(1, K + 1)]].to_numpy(float)
    AP = g[[f"ap{i}" for i in range(1, K + 1)]].to_numpy(float)
    AQ = g[[f"aq{i}" for i in range(1, K + 1)]].to_numpy(float)
    tr = bh.load_trades(day)
    return make_ctx(T, BP, BQ, AP, AQ, tr.t.to_numpy(), tr.side.to_numpy(), tr.price.to_numpy(float), tr.qty.to_numpy(float))


def make_ctx(T, BP, BQ, AP, AQ, tt, ts, tp, tq, tick=None) -> dict:
    return dict(T=T, BP=BP, BQ=BQ, AP=AP, AQ=AQ, tt=tt, ts=ts, tp=tp, tq=tq, mid=(BP[:, 0] + AP[:, 0]) / 2.0,
                tick=tick if tick is not None else infer_tick(BP, AP))


def scan(ctx: dict):
    """Run both trackers second by second. Returns (signals, every wall ever registered)."""
    T, BP, BQ, AP, AQ = ctx["T"], ctx["BP"], ctx["BQ"], ctx["AP"], ctx["AQ"]
    tt, ts, tp, tq = ctx["tt"], ctx["ts"], ctx["tp"], ctx["tq"]
    idx = np.searchsorted(tt, T, "right")
    bids, asks = WallTracker(True), WallTracker(False)
    sigs = []
    for i in range(1, len(T)):
        sells, buys, lo_sell, hi_buy = {}, {}, None, None
        for j in range(int(idx[i - 1]), int(idx[i])):
            if ts[j] == "sell":
                sells[tp[j]] = sells.get(tp[j], 0.0) + tq[j]
                lo_sell = tp[j] if lo_sell is None else min(lo_sell, tp[j])
            else:
                buys[tp[j]] = buys.get(tp[j], 0.0) + tq[j]
                hi_buy = tp[j] if hi_buy is None else max(hi_buy, tp[j])
        t = int(T[i])
        bids.update(t, BP[i], BQ[i], sells, lo_sell)
        asks.update(t, AP[i], AQ[i], buys, hi_buy)
        bb, ba, bq1, aq1 = BP[i, 0], AP[i, 0], BQ[i, 0], AQ[i, 0]
        if not (bb == bb and ba == ba) or bb >= ba or bq1 + aq1 <= 0:
            continue
        imb = (bq1 - aq1) / (bq1 + aq1)
        if imb >= L1_IMB:
            hit = bids.valid(t, bb)
            if hit:
                sigs.append(dict(i=i, t=t, d=1, wall=hit[1]))
        elif imb <= -L1_IMB:
            hit = asks.valid(t, ba)
            if hit:
                sigs.append(dict(i=i, t=t, d=-1, wall=hit[1]))
    return sigs, bids.history + asks.history


# ---------------------------------------------------------------- one attempt: fill, then the bracket
def grid_index(T: np.ndarray, t: int):
    j = int(np.searchsorted(T, t, "left"))
    return j if j < len(T) else None


def level_qty(prices: np.ndarray, qtys: np.ndarray, px: float, tick: float) -> float:
    m = np.abs(prices - px) <= tick / 2.0
    return float(qtys[m][0]) if m.any() else 0.0


def away_cancel_ms(ctx: dict, i0: int, d: int, quote: float):
    """First grid time within the entry's 30 s at which the mid is CANCEL_AWAY_BP beyond the quote on the side the price runs away from."""
    T, mid = ctx["T"], ctx["mid"]
    j1 = int(np.searchsorted(T, T[i0] + LAT_MS + TTL_MS, "right"))
    seg = mid[i0 + 1:j1]
    dev = d * (seg - quote) / quote * 1e4                    # long: mid above the bid by CANCEL_AWAY_BP; short mirrored
    hit = np.nonzero(dev > CANCEL_AWAY_BP)[0]
    return int(T[i0 + 1 + hit[0]]) if len(hit) else None


def attempt(ctx: dict, i0: int, d: int, quote: float, q_ahead: float, cancel_ms, tp_bp: float, sl_bp: float):
    """One resting entry and, if it fills, the bracket. None = the day ended before the outcome was known (dropped)."""
    T, BP, AP, BQ, AQ = ctx["T"], ctx["BP"], ctx["AP"], ctx["BQ"], ctx["AQ"]
    tt, ts, tp, tq, mid, tick = ctx["tt"], ctx["ts"], ctx["tp"], ctx["tq"], ctx["mid"], ctx["tick"]
    long = d > 0
    t0 = int(T[i0])
    t_post = t0 + LAT_MS
    ttl = TTL_MS if cancel_ms is None else max(0, min(TTL_MS, int(cancel_ms) - t_post))
    j30 = grid_index(T, t0 + 30_000)
    if j30 is None:
        return None
    rec = dict(i=i0, t=t0, d=d, filled=False, kind="unfilled", gross=0.0, net=0.0, end_ms=t_post + ttl, fwd30=d * (mid[j30] / mid[i0] - 1.0) * 1e4)
    if ttl <= 0:
        return rec
    tf = bh.maker_fill(tt, ts, tp, tq, t_post, quote, q_ahead, rests_bid=long, ttl_ms=ttl)
    if tf is None:
        return rec
    pf = quote
    tp_px, sl_px = pf * (1 + d * tp_bp / 1e4), pf * (1 - d * sl_bp / 1e4)
    t_live, t_scr, t_hard = tf + LAT_MS, tf + SCRATCH_MS, tf + HARD_MS
    jl, js, jh = grid_index(T, t_live), grid_index(T, t_scr + LAT_MS), grid_index(T, t_hard + LAT_MS)
    if jl is None or js is None or jh is None:
        return None
    q_tp = level_qty(AP[jl], AQ[jl], tp_px, tick) if long else level_qty(BP[jl], BQ[jl], tp_px, tick)
    t_tp = bh.maker_fill(tt, ts, tp, tq, t_live, tp_px, q_tp, rests_bid=not long, ttl_ms=t_scr - t_live)
    a, b = int(np.searchsorted(tt, t_live, "right")), int(np.searchsorted(tt, t_hard, "right"))
    seg = tp[a:b]
    hit = (seg <= sl_px + EPS) if long else (seg >= sl_px - EPS)
    t_sl = int(tt[a + int(np.argmax(hit))]) if hit.any() else None
    sc_px = AP[js, 0] if long else BP[js, 0]
    q_sc = AQ[js, 0] if long else BQ[js, 0]
    t_sc = bh.maker_fill(tt, ts, tp, tq, t_scr + LAT_MS, sc_px, q_sc, rests_bid=not long, ttl_ms=t_hard - (t_scr + LAT_MS)) if sc_px == sc_px else None
    events = [(t, pr, kind) for t, pr, kind in ((t_sl, 0, "stop"), (t_tp, 1, "target"), (t_sc, 2, "scratch")) if t is not None]
    if events:
        t_x, _, kind = min(events)
    else:
        t_x, kind = t_hard, "timeout"
    if kind == "target":
        px, fee, end = tp_px, MAKER_BP, t_x
    elif kind == "scratch":
        px, fee, end = sc_px, MAKER_BP, t_x
    elif kind == "stop":
        jx = grid_index(T, t_x + LAT_MS)
        if jx is None:
            return None
        px = (BP[jx, 0] if long else AP[jx, 0])
        px = sl_px if px != px else px
        fee, end = TAKER_BP, t_x + LAT_MS
    else:
        px = BP[jh, 0] if long else AP[jh, 0]
        px = sl_px if px != px else px
        fee, end = TAKER_BP, t_hard + LAT_MS
    gross = d * (px / pf - 1.0) * 1e4
    rec.update(filled=True, kind=kind, gross=gross, net=gross - MAKER_BP - fee, end_ms=end, t_fill=tf)
    return rec


def quote_for(ctx: dict, i: int, d: int, wall_px=None, offset_ticks=None):
    """(quote price, queue ahead, distance behind the touch in ticks) for a long (d=1) or short (d=-1) at grid index i.
    With a wall: one tick in front of it, never beyond the touch. Without (a control): offset_ticks behind the touch."""
    BP, BQ, AP, AQ, tick = ctx["BP"], ctx["BQ"], ctx["AP"], ctx["AQ"], ctx["tick"]
    bb, ba = BP[i, 0], AP[i, 0]
    if d > 0:
        q = min(wall_px + tick, bb) if wall_px is not None else bb - offset_ticks * tick
        return q, level_qty(BP[i], BQ[i], q, tick), int(round((bb - q) / tick))
    q = max(wall_px - tick, ba) if wall_px is not None else ba + offset_ticks * tick
    return q, level_qty(AP[i], AQ[i], q, tick), int(round((q - ba) / tick))


def run_signals(ctx: dict, sigs: list, tp_bp: float, sl_bp: float) -> list:
    free, used, out = -1, set(), []
    for s in sigs:
        if s["t"] < free or id(s["wall"]) in used:
            continue
        used.add(id(s["wall"]))
        q, qa, off = quote_for(ctx, s["i"], s["d"], wall_px=s["wall"].px)
        w = s["wall"]
        c_away = away_cancel_ms(ctx, s["i"], s["d"], q)
        c_wall = w.invalid_at if (w.invalid_at is not None and w.invalid_at > s["t"]) else None
        cancels = [c for c in (c_away, c_wall) if c is not None]
        rec = attempt(ctx, s["i"], s["d"], q, qa, min(cancels) if cancels else None, tp_bp, sl_bp)
        if rec is None:
            continue
        rec.update(offset=off, wall_age_s=(s["t"] - w.first) / 1000.0)
        out.append(rec)
        free = rec["end_ms"] + COOLDOWN_MS
    return out


def run_controls(ctx: dict, signal_recs: list, tp_bp: float, sl_bp: float, rng) -> list:
    T = ctx["T"]
    out = []
    for r in signal_recs:
        for _ in range(N_CONTROLS):
            ic = r["i"]
            while ic == r["i"]:
                ic = int(np.clip(r["i"] + rng.integers(-CONTROL_WINDOW_S, CONTROL_WINDOW_S + 1), 60, len(T) - 300))
            if ctx["BP"][ic, 0] != ctx["BP"][ic, 0] or ctx["AP"][ic, 0] != ctx["AP"][ic, 0]:
                continue
            q, qa, _ = quote_for(ctx, ic, r["d"], offset_ticks=r["offset"])
            c = attempt(ctx, ic, r["d"], q, qa, away_cancel_ms(ctx, ic, r["d"], q), tp_bp, sl_bp)
            if c is not None:
                out.append(c)
    return out


# ---------------------------------------------------------------- statistics and the registered rule
def summarize(recs: list) -> dict:
    f = [r for r in recs if r["filled"]]
    g = np.array([r["gross"] for r in f])
    n = np.array([r["net"] for r in f])
    return dict(attempts=len(recs), filled=len(f), fill_rate=len(f) / len(recs) if recs else 0.0,
                gross=float(g.mean()) if len(f) else 0.0, net=float(n.mean()) if len(f) else 0.0,
                gross_sd=float(g.std(ddof=1)) if len(f) > 1 else 0.0, win=float((g > 0).mean()) if len(f) else 0.0,
                kinds=dict(Counter(r["kind"] for r in f)))


def excess_t(sig: dict, ctl: dict) -> float:
    """One-sided Welch t of the signal's filled gross minus the controls' filled gross. The 5 controls of an attempt share a time of day, so the control
    sample counts as filled / N_CONTROLS independent trades."""
    n1, n2 = sig["filled"], ctl["filled"] / N_CONTROLS
    if n1 < 2 or n2 < 2:
        return 0.0
    se = math.sqrt(sig["gross_sd"] ** 2 / n1 + ctl["gross_sd"] ** 2 / n2)
    return (sig["gross"] - ctl["gross"]) / se if se > 0 else 0.0


def passes(sig: dict, ctl: dict) -> bool:
    """The registered rule for one half of the days at the primary bracket."""
    return (sig["filled"] >= REGISTERED["min_filled"] and sig["gross"] >= REGISTERED["min_gross_bp"] and sig["net"] > 0
            and excess_t(sig, ctl) >= REGISTERED["min_excess_t"])


def holm(pvals: list) -> list:
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    adj, run = [0.0] * len(pvals), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(pvals) - rank) * pvals[i]))
        adj[i] = run
    return adj


def p_one_sided(t: float) -> float:
    return 0.5 * math.erfc(t / math.sqrt(2.0))


def study(days: list) -> dict:
    """{bracket: dict(sig=[records], ctl=[records], by_day={day: [records]})} plus per-day diagnostics."""
    res = {b: dict(sig=[], ctl=[], by_day={}) for b in BRACKETS}
    diag = {}
    for day in days:
        ctx = prep_day(day)
        sigs, walls = scan(ctx)
        age = [(w.dead_at if w.dead_at is not None else ctx["T"][-1]) - w.first for w in walls]
        reached = sum(1 for w, a in zip(walls, age) if a >= WALL_MIN_AGE_MS and w.invalid_at is None)
        diag[day] = dict(tick=ctx["tick"], walls=len(walls), reached_age_unpulled=reached, signal_seconds=len(sigs))
        rng = np.random.default_rng(int(day.replace("-", "")))
        for b in BRACKETS:
            s = run_signals(ctx, sigs, b, b)
            c = run_controls(ctx, s, b, b, rng)
            res[b]["sig"] += s
            res[b]["ctl"] += c
            res[b]["by_day"][day] = s
    return dict(res=res, diag=diag)


def report(title: str, out: dict) -> tuple:
    L = [title]
    for day, d in out["diag"].items():
        L.append(f"  {day}: tick {d['tick']:g}, walls registered {d['walls']}, reached 20 s unpulled {d['reached_age_unpulled']} "
                 f"({d['reached_age_unpulled'] / max(d['walls'], 1):.0%}), signal seconds {d['signal_seconds']}")
    L.append(f"  {'bracket':>8}{'attempts':>9}{'filled':>7}{'fill':>6}{'gross bp':>9}{'net bp':>8}{'win':>6}{'ctl filled':>11}{'ctl gross':>10}{'excess t':>9}{'Holm p':>8}")
    ts_, sums = [], {}
    for b in BRACKETS:
        s, c = summarize(out["res"][b]["sig"]), summarize(out["res"][b]["ctl"])
        sums[b] = (s, c)
        ts_.append(excess_t(s, c))
    hp = holm([p_one_sided(t) for t in ts_])
    for b, t, p in zip(BRACKETS, ts_, hp):
        s, c = sums[b]
        L.append(f"  {b:>5.0f}/{b:<2.0f}{s['attempts']:>9}{s['filled']:>7}{s['fill_rate']:>6.0%}{s['gross']:>9.2f}{s['net']:>8.2f}{s['win']:>6.0%}"
                 f"{c['filled']:>11}{c['gross']:>10.2f}{t:>9.2f}{p:>8.3f}")
    s, c = sums[PRIMARY]
    L.append(f"  primary {PRIMARY:.0f}/{PRIMARY:.0f} exits: {s['kinds']}; controls: {c['kinds']}")
    f = [r for r in out["res"][PRIMARY]["sig"] if r["filled"]]
    u = [r for r in out["res"][PRIMARY]["sig"] if not r["filled"]]
    if f and u:
        L.append(f"  next-30 s move in the trade's direction (bp): filled attempts {np.mean([r['fwd30'] for r in f]):+.2f}, unfilled {np.mean([r['fwd30'] for r in u]):+.2f}")
    L.append("  per day, signal gross at 8/8 (filled n, mean bp): " + ", ".join(
        f"{day} ({sum(r['filled'] for r in rs)}, {np.mean([r['gross'] for r in rs if r['filled']]):+.2f})" if any(r['filled'] for r in rs) else f"{day} (0, -)"
        for day, rs in out["res"][PRIMARY]["by_day"].items()))
    ok = passes(s, c)
    L.append(f"  REGISTERED RULE at {PRIMARY:.0f}/{PRIMARY:.0f}: filled {s['filled']} (>= {REGISTERED['min_filled']}), gross {s['gross']:+.2f} (>= +{REGISTERED['min_gross_bp']}), "
             f"net {s['net']:+.2f} (> 0), excess t {excess_t(s, c):+.2f} (>= {REGISTERED['min_excess_t']}) -> {'PASSES' if ok else 'FAILS'}")
    return "\n".join(L), ok


def main():
    assert registry_digest() == REGISTRY_SHA256, "the registered numbers were changed after they were pinned"
    confirm = "--confirm" in sys.argv
    lines = [f"backtest/wall_persistence.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; registry {REGISTRY_SHA256[:12]}"]
    if not confirm:
        txt, ok = report("TUNE HALF " + ", ".join(TUNE), study(TUNE))
        lines += [txt, "", ("The tune half PASSES the registered rule: the confirm half may now be read ONCE (--confirm)." if ok else
                           "The tune half FAILS the registered rule: KILL. The confirm days (2025-12-01, 2026-03-01, 2026-09-01) were NOT read.")]
        LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        prev = LOG.read_text(encoding="utf-8") if LOG.exists() else ""
        if "tune half PASSES" not in prev:
            raise SystemExit("refused: the tune half has not passed the registered rule (see logs/wall_persistence.txt); the confirm days stay unread")
        txt, ok = report("CONFIRM HALF " + ", ".join(CONFIRM), study(CONFIRM))
        lines = [prev.rstrip("\n"), "", f"--- confirm read, {pd.Timestamp.now():%Y-%m-%d %H:%M} ---", txt, "",
                 "LEAD: both halves pass the registered rule; worth a 20+ day forward record on Hyperliquid's feed, not money." if ok else
                 "NO PASS on the confirm half."]
        LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

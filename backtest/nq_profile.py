"""MARKET PROFILE / AUCTION MARKET THEORY ON NQ: value area, POC, value migration, initial balance, open drive (2026-11-09)

THE USER (2026-11-09): "heat map, time and sales, gamma exposure, volume profile, market profile, footprint, delta, order flow, VWAP, auction market theory - did we check all of them?" Most were (doc 02, his_volprofile.py, his_gex.py,
book_hist.py ...); the one NOT tested directly is market profile / auction market theory as a set of stand-alone rules. Then: "run the market profile test on NQ". This is that test, on the 16 years of NQ 1-minute bars WITH real volume already on
disk (nq_fetch.py, Databento, USD 19.93) - no new spend. his_volprofile.py used Exness tick counts as a volume stand-in on 181 days at one trader's clicks; this uses real volume, every session since 2010, as rules.

DATA     NQ.c.0 1-minute bars, cash session 09:30-16:00 New York (390 bars) via nq_noise.build_sessions: >= 90% of the minutes present, sessions with a contract change INSIDE them dropped, a session whose contract differs from the
         previous one's has no 'prior' (roll_gap). 4,016 sessions 2010-06..2026-10. Split: first 60% of sessions = tune, last 40% = holdout (the NQ studies' split, TUNE = 0.60).
PROFILE  of the PREVIOUS cash session only (known at its 16:00 close), two constructions, same value-area method:
           TPO  (primary - this is what 'Market Profile' means): 13 half-hour periods, one 'letter' per period in every price bin the period's range touched; POC = the bin with most letters.
           VOL  (the plateau check - 'volume profile' with real volume): each 1-minute bar's volume spread evenly over the bins its low-high range touches; POC = the bin with most volume.
         Bin = 2bp of the session's close, rounded to the 0.25 tick (floor lattice). POC ties -> the bin nearest the session close (then the lower). VALUE AREA = the standard CME method: from the POC, compare the two bins above with the two below,
         add the larger pair (ties up), until 70% of the total is inside; VAL = the lower edge of the lowest bin, VAH = the upper edge of the highest. A session is skipped when its previous session is not directly before it (contract change
         between them, or more than 4 calendar days).
RULES    (decision at the CLOSE of a bar, entry at the OPEN of the next; 30-minute checkpoints = the closes of bars 29, 59, ..., 359; last decision bar 359 = 15:30; exit at the 16:00 close unless a target is touched first; NO stop, as taught)
  R1  80% rule     the session OPENS outside the prior value area; the first time two consecutive 30-minute closes are both inside it, trade toward the far edge (opened above: short, target VAL; below: long, target VAH).
  R2  back to POC  at the 10:00 close, if price is >= 15bp from the prior POC, trade toward it (target = the POC).
  R3  fade the edge  the session opens INSIDE value; the first bar whose high reaches VAH (low reaches VAL) -> short (long) at the next open, target = the prior POC; a bar touching both edges = no trade.
  R4  acceptance   the first time two consecutive 30-minute closes are both above VAH (below VAL), go WITH it, to the close (no target).
  R5a value migration (POC)   |POC(yesterday) / POC(day before) - 1| >= 0.25 x the average daily range of the last 14 sessions: trade the migration's direction from the open to the close.
  R5b value migration (no overlap)   yesterday's whole value area above (below) the day before's: long (short) from the open to the close.
  R6a initial balance break   IB = the first 60 minutes' range; the first 1-minute CLOSE beyond it (bar 60 on, decision bars <= 359): go with the break to the close.
  R6b the same, only when the IB is narrow: IB / open < 0.6 x the median of the previous 20 sessions' IB / open.
  R7  open drive   at the 10:00 close, the first 30 minutes' range >= 0.25 x the average daily range, the close in the top (bottom) 10% of that range and the open in the bottom (top) 10%: go with the drive to the close.
  Every target must lie >= 5bp beyond the DECISION bar's close (what is known when the order is sent) or the day is skipped. Cells = 9 (R1, R2, R3, R4, R5a, R5b, R6a, R6b, R7); both sides are pooled in a cell, the side is whatever the rule says.
COSTS    1.27bp a trade (Exness NASDAQ 0.77 spread + 0.5 slippage, as nq_noise / fx_intraday_pub, kept for comparability); also shown at 0.25bp (futures-like) and at double. A touched target is assumed filled AT the target.
CONTROL  MATCHED DAYS. For every trade the same trade (same side, same entry bar, same target distance beyond the entry, same exit) is run on EVERY session of the same half, and the average is the expectation of that trade on a random day:
         it carries the market's drift, the side mix, the time of day and the target's shape (the average includes the trade's own day: 1 of ~2,400). excess = the trade's return minus that expectation (gross); t = mean / (sd / sqrt n); one-sided p from the normal; Holm over the 9 cells (TPO).
GATE     a cell PASSES when: net mean > 0 on BOTH halves at 1.27bp; excess > 0 on both halves; the holdout Holm-adjusted p < 0.05; >= 100 holdout trades (else UNDERPOWERED); AND the VOL construction also has net > 0 on both halves.
         LEAD (not a pass): net > 0 and excess t >= 2 on both halves with >= 100 trades each.

REGISTERED BEFORE THE FIRST RUN (2026-11-09; prior that at least one cell passes: 5%)
  M1  No cell passes the gate (TPO or VOL).
  M2  R1's target-touch share (the textbook '80%') is between 55% and 70% and within 6 points of its matched-day share: the rule hits the far edge about as often as a random day does.
  M3  R5a / R5b: positive gross on both halves (NQ's drift), excess over the matched days within +-2bp with |t| < 2 on both halves.
  M4  R3 (fade the edge from an inside open) has net < 0 on at least one half.
  M5  R6a: the first IB break exists on more than 85% of sessions (the textbook 'IB is nearly always broken'), and going with it has |excess t| < 2 on both halves; R6b is not better than R6a by more than 2bp on the holdout.
  M6  R7 fires on 2-10% of sessions, and its excess t is < 2 on both halves.
  M7  The VOL construction reaches the same verdict as TPO for every cell (no cell passes in either).

RESULT (2026-11-09; logs/nq_profile.txt; 4,016 NQ sessions 2010-06..2026-10: tune 2,409 sessions to 2020-04-14, holdout 1,607) - 0 of 9 cells pass, in either construction; no LEAD.
    Scale: long from the open to the close EVERY session earns +3.56bp (tune) / +2.85bp (holdout) gross; 65% of sessions open outside the previous session's value area (its median width is 58bp of the close); POC inside its value area on 100%.
    NET at 1.27bp, tune | holdout (matched-day excess t, tune | holdout), TPO:
      R1 80% rule +2.40 | -1.49 (1.9 | 0.2)    R2 back to POC -2.65 | -0.39 (-0.8 | 0.8)    R3 fade the value edge -2.33 | -3.93 (-0.2 | -0.5)    R4 acceptance +0.12 | +0.37 (0.7 | 0.6)
      R5a migration (POC) +0.34 | -2.33 (0.5 | -0.4)    R5b migration (no overlap) -0.75 | -5.71 (-0.1 | -1.2)    R6a IB break -3.62 | +1.21 (-1.6 | 1.0)    R6b narrow-IB break -6.58 | -8.43 (-1.4 | -1.0)
      R7 open drive +0.43 | +15.59 (0.2 | 1.8; holdout Holm p 0.34, n 141 | 120).
    The 80% rule: the far edge is touched 47.6% | 43.5% of the time (tune | holdout) against 43.4% | 44.2% for the same trade on random days; the textbook 80% is not in the data (VOL construction: 44.2% | 43.9%).
    VOL (real volume) reaches the same picture: R4 +0.96 | -1.02, R5a -0.71 | -0.25, R1 -0.07 | -3.76; no cell is positive on both halves with excess t >= 2. Shorts lose in R2 / R5a / R5b (-3.6 / -5.1 / -8.3bp over the whole period), the drift the matched days remove.
    At a futures-like 0.25bp, R4 (+1.1 | +1.4) and R7 (+1.5 | +16.6) are positive on both halves but their tune-half excess t is 0.7 and 0.2.
    The one number that stands out: R7 (open drive) +15.6bp on the holdout (t 1.7, 120 trades) with +0.4bp on the tune half; one of nine cells, holdout only, by year negative in 2010, 2011, 2015, 2019 and 2025 - not a lead by its own rule (needs t >= 2 on both halves).
    Predictions: M1 RIGHT. M2 HALF RIGHT (within 6 points of the matched days: yes; the registered 55-70% range: no, 44-48%). M3 WRONG (holdout gross is negative in both: R5a -1.06, R5b -4.44; the excess t < 2 part is right).
    M4 RIGHT (net < 0 on both halves). M5 RIGHT (the first IB break exists on 95.8% of sessions; excess t -1.6 | +1.0; R6b -8.4 against R6a +1.2 on the holdout). M6 RIGHT (6.6% of sessions; excess t 0.2 | 1.8). M7 RIGHT.
    Limits: the profile is of the cash session only (no Globex hours); the volume profile spreads each 1-minute bar's volume evenly over its range; a touched target is assumed filled at the target; no stops (as taught), so a trade held to the close can lose a lot;
    costs are the Exness CFD's 1.27bp, kept for comparability; 67 contract-change sessions have no prior; one market; one definition of each rule. NOT tested: full-session (Globex) profiles, single prints / poor highs / excess, composite or weekly profiles,
    a developing intraday profile as a stand-alone rule on real volume (his_volprofile.py did it on tick counts at one trader's clicks), open-type classification beyond the open drive, other markets (ES).
    Tests: 39 (tests/test_nq_profile.py). 98 planted bugs caught over three rounds: 88 of 96 first (eight survivors, every one a gap in MY tests), 96 of 97 second, the last survivor and one more after splitting verdicts_from out; the no-op control survived each time.

    python -m backtest.nq_profile        writes logs/nq_profile.txt          tests: python tests/test_nq_profile.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.nq_noise import build_sessions, load_nq  # noqa: E402

LOG = ROOT / "logs" / "nq_profile.txt"
L = 390
TUNE = 0.60
TICK = 0.25
BIN_BP = 2.0
VA_FRAC = 0.70
PERIOD = 30
COST_BP = 1.27
MIN_TARGET_BP = 5.0
POC_DIST_BP = 15.0
MIGR_ATR = 0.25
ATR_WIN = 14
IB_MIN = 60
IB_BASE_WIN = 20
IB_NARROW = 0.6
OD_EDGE = 0.10
OD_RANGE = 0.25
LAST = 359
MIN_HOLD_TRADES = 100
MAX_GAP_DAYS = 4
CELLS = ["R1 80% rule", "R2 back to POC", "R3 fade value edge", "R4 acceptance outside value", "R5a value migration (POC)",
         "R5b value migration (no overlap)", "R6a IB break", "R6b IB break, narrow IB", "R7 open drive"]
MODES = ("tpo", "vol")


# ------------------------------------------------------------------ the profile

def bin_width(ref: float) -> float:
    """2bp of the price, rounded to the 0.25 tick, never below one tick."""
    return max(TICK, round(ref * BIN_BP / 1e4 / TICK) * TICK)


def profile_counts(h, l, v, c_last: float, mode: str):
    """(k0, counts, w): the profile over bins k0, k0 + 1, ... of width w (bin k = [k w, (k + 1) w))."""
    w = bin_width(c_last)
    b0 = np.floor(np.asarray(l, float) / w).astype(int)
    b1 = np.floor(np.asarray(h, float) / w).astype(int)
    k0, k1 = int(b0.min()), int(b1.max())
    n = k1 - k0 + 1
    if mode == "vol":
        share = np.asarray(v, float) / (b1 - b0 + 1)
        diff = np.zeros(n + 1)
        np.add.at(diff, b0 - k0, share)
        np.add.at(diff, b1 - k0 + 1, -share)
        counts = np.maximum(np.cumsum(diff)[:n], 0.0)
    else:
        counts = np.zeros(n)
        for p in range(len(h) // PERIOD):
            sl = slice(p * PERIOD, (p + 1) * PERIOD)
            lo_b = int(np.floor(np.min(l[sl]) / w))
            hi_b = int(np.floor(np.max(h[sl]) / w))
            counts[lo_b - k0: hi_b - k0 + 1] += 1.0
    return k0, counts, w


def value_area(counts, close_bin: int):
    """(poc, lo, hi) as indices into counts: the CME method, two bins at a time, the larger pair wins, ties go up."""
    n = len(counts)
    mx = counts.max()
    cand = np.flatnonzero(counts >= mx - 1e-9 * max(abs(mx), 1.0))
    poc = int(cand[np.argmin(np.abs(cand - close_bin))])
    lo = hi = poc
    acc, goal = float(counts[poc]), VA_FRAC * float(counts.sum())
    while acc < goal and (lo > 0 or hi < n - 1):
        up = float(counts[hi + 1:hi + 3].sum()) if hi < n - 1 else None
        dn = float(counts[max(lo - 2, 0):lo].sum()) if lo > 0 else None
        if dn is None or (up is not None and up >= dn):
            acc += up
            hi = min(hi + 2, n - 1)
        else:
            acc += dn
            lo = max(lo - 2, 0)
    return poc, lo, hi


def session_profile(h, l, v, c_last: float, mode: str) -> dict:
    k0, counts, w = profile_counts(h, l, v, c_last, mode)
    close_bin = int(np.floor(c_last / w)) - k0
    poc, lo, hi = value_area(counts, close_bin)
    return dict(poc=(k0 + poc + 0.5) * w, val=(k0 + lo) * w, vah=(k0 + hi + 1) * w)


def profiles(A, mode: str) -> dict:
    n = A["c"].shape[0]
    P = {k: np.full(n, np.nan) for k in ("poc", "val", "vah")}
    for i in range(n):
        s = session_profile(A["h"][i], A["l"][i], A["v"][i], A["c"][i, -1], mode)
        for k in P:
            P[k][i] = s[k]
    return P


def prior_flags(dates, roll_gap):
    """ok[i]: session i-1 is the session directly before i (same contract, <= 4 calendar days). ok2[i]: that also holds for i-1 (the day before THAT)."""
    n = len(dates)
    ok = np.zeros(n, bool)
    for i in range(1, n):
        ok[i] = (not roll_gap[i]) and (dates[i] - dates[i - 1]).days <= MAX_GAP_DAYS
    ok2 = ok & np.r_[False, ok[:-1]]
    return ok, ok2


def day_features(A):
    """Everything known BEFORE the session: the average daily range (fraction of the close) of the last 14 sessions, and the IB range / open of the last 20 (median). ib[i] is today's (known at 10:30)."""
    rng = (A["h"].max(axis=1) - A["l"].min(axis=1)) / A["c"][:, -1]
    arf = pd.Series(rng).rolling(ATR_WIN).mean().shift(1).to_numpy()
    ib = (A["h"][:, :IB_MIN].max(axis=1) - A["l"][:, :IB_MIN].min(axis=1)) / A["o"][:, 0]
    ibmed = pd.Series(ib).rolling(IB_BASE_WIN).median().shift(1).to_numpy()
    return dict(arf=arf, ib=ib, ibmed=ibmed)


# ------------------------------------------------------------------ the rules; a spec = dict(i, side, m, target)

def _checkpoints():
    return list(range(PERIOD - 1, LAST + 1, PERIOD))


def _far_enough(side, target, entry):
    return side * (target / entry - 1) >= MIN_TARGET_BP / 1e4


def rule_r1(A, P, ok, ok2, F):
    out, C, O = [], A["c"], A["o"]
    cps = _checkpoints()
    for i in np.flatnonzero(ok):
        val, vah = P["val"][i - 1], P["vah"][i - 1]
        if not (np.isfinite(val) and np.isfinite(vah)):
            continue
        o = O[i, 0]
        if val <= o <= vah:
            continue
        side = -1 if o > vah else 1
        target = val if side < 0 else vah
        for a, b in zip(cps[:-1], cps[1:]):
            if val <= C[i, a] <= vah and val <= C[i, b] <= vah:
                if _far_enough(side, target, C[i, b]):
                    out.append(dict(i=int(i), side=side, m=b + 1, target=target))
                break
    return out


def rule_r2(A, P, ok, ok2, F):
    out, C, O = [], A["c"], A["o"]
    for i in np.flatnonzero(ok):
        poc = P["poc"][i - 1]
        if not np.isfinite(poc):
            continue
        dist = C[i, PERIOD - 1] / poc - 1
        if abs(dist) >= POC_DIST_BP / 1e4:
            side = -1 if dist > 0 else 1
            if _far_enough(side, poc, C[i, PERIOD - 1]):
                out.append(dict(i=int(i), side=side, m=PERIOD, target=poc))
    return out


def rule_r3(A, P, ok, ok2, F):
    out, H, Lw, O = [], A["h"], A["l"], A["o"]
    for i in np.flatnonzero(ok):
        val, vah, poc = P["val"][i - 1], P["vah"][i - 1], P["poc"][i - 1]
        if not (np.isfinite(val) and np.isfinite(vah) and np.isfinite(poc)):
            continue
        if not (val <= O[i, 0] <= vah):
            continue
        th, tl = H[i, :LAST + 1] >= vah, Lw[i, :LAST + 1] <= val
        any_t = th | tl
        if not any_t.any():
            continue
        b = int(np.argmax(any_t))
        if th[b] and tl[b]:
            continue
        side = -1 if th[b] else 1
        if _far_enough(side, poc, A["c"][i, b]):
            out.append(dict(i=int(i), side=side, m=b + 1, target=poc))
    return out


def rule_r4(A, P, ok, ok2, F):
    out, C = [], A["c"]
    cps = _checkpoints()
    for i in np.flatnonzero(ok):
        val, vah = P["val"][i - 1], P["vah"][i - 1]
        if not (np.isfinite(val) and np.isfinite(vah)):
            continue
        for a, b in zip(cps[:-1], cps[1:]):
            if C[i, a] > vah and C[i, b] > vah:
                out.append(dict(i=int(i), side=1, m=b + 1, target=None))
                break
            if C[i, a] < val and C[i, b] < val:
                out.append(dict(i=int(i), side=-1, m=b + 1, target=None))
                break
    return out


def rule_r5a(A, P, ok, ok2, F):
    out = []
    for i in np.flatnonzero(ok2):
        p1, p2, arf = P["poc"][i - 1], P["poc"][i - 2], F["arf"][i]
        if not (np.isfinite(p1) and np.isfinite(p2) and np.isfinite(arf)):
            continue
        d = p1 / p2 - 1
        if abs(d) >= MIGR_ATR * arf:
            out.append(dict(i=int(i), side=1 if d > 0 else -1, m=0, target=None))
    return out


def rule_r5b(A, P, ok, ok2, F):
    out = []
    for i in np.flatnonzero(ok2):
        v1, h1, v2, h2 = P["val"][i - 1], P["vah"][i - 1], P["val"][i - 2], P["vah"][i - 2]
        if not (np.isfinite(v1) and np.isfinite(h1) and np.isfinite(v2) and np.isfinite(h2)):
            continue
        if v1 > h2:
            out.append(dict(i=int(i), side=1, m=0, target=None))
        elif h1 < v2:
            out.append(dict(i=int(i), side=-1, m=0, target=None))
    return out


def _ib_break(A, i):
    hi, lo = A["h"][i, :IB_MIN].max(), A["l"][i, :IB_MIN].min()
    c = A["c"][i, IB_MIN:LAST + 1]
    up, dn = c > hi, c < lo
    br = up | dn
    if not br.any():
        return None
    k = int(np.argmax(br))
    return (1 if up[k] else -1), IB_MIN + k + 1


def rule_r6a(A, P, ok, ok2, F):
    out = []
    for i in range(A["c"].shape[0]):
        r = _ib_break(A, i)
        if r:
            out.append(dict(i=i, side=r[0], m=r[1], target=None))
    return out


def rule_r6b(A, P, ok, ok2, F):
    out = []
    for i in range(A["c"].shape[0]):
        med = F["ibmed"][i]
        if not np.isfinite(med) or not F["ib"][i] < IB_NARROW * med:
            continue
        r = _ib_break(A, i)
        if r:
            out.append(dict(i=i, side=r[0], m=r[1], target=None))
    return out


def rule_r7(A, P, ok, ok2, F):
    out = []
    for i in range(A["c"].shape[0]):
        arf = F["arf"][i]
        if not np.isfinite(arf):
            continue
        hi, lo = A["h"][i, :PERIOD].max(), A["l"][i, :PERIOD].min()
        rng = hi - lo
        if rng <= 0 or rng / A["o"][i, 0] < OD_RANGE * arf:
            continue
        pc, po = (A["c"][i, PERIOD - 1] - lo) / rng, (A["o"][i, 0] - lo) / rng
        if pc >= 1 - OD_EDGE and po <= OD_EDGE:
            out.append(dict(i=i, side=1, m=PERIOD, target=None))
        elif pc <= OD_EDGE and po >= 1 - OD_EDGE:
            out.append(dict(i=i, side=-1, m=PERIOD, target=None))
    return out


RULES = [rule_r1, rule_r2, rule_r3, rule_r4, rule_r5a, rule_r5b, rule_r6a, rule_r6b, rule_r7]


# ------------------------------------------------------------------ trades and the matched-day control

def trade_ret(A, i, side, m, target):
    """(gross return, touched target?). Entry at the open of bar m; a target is checked from the entry bar on and filled at the target; else out at the 16:00 close."""
    entry = A["o"][i, m]
    if target is not None:
        seg = A["h"][i, m:] if side > 0 else A["l"][i, m:]
        hit = (seg >= target) if side > 0 else (seg <= target)
        if hit.any():
            return side * (target / entry - 1), True
    return side * (A["c"][i, -1] / entry - 1), False


def expected(A, side, m, d, J):
    """(mean return, target-touch share) of the SAME trade on every session in J: side, entry bar m, a target d (a fraction, > 0) beyond the entry in the trade's direction (None = held to the close)."""
    entry = A["o"][J, m]
    close = A["c"][J, -1]
    if d is None:
        return float(np.mean(side * (close / entry - 1))), float("nan")
    tgt = entry * (1 + side * d)
    if side > 0:
        hit = (A["h"][J, m:] >= tgt[:, None]).any(axis=1)
    else:
        hit = (A["l"][J, m:] <= tgt[:, None]).any(axis=1)
    r = np.where(hit, d, side * (close / entry - 1))
    return float(r.mean()), float(hit.mean())


def evaluate(A, specs, cut):
    """One row per trade: day, half (0 tune / 1 holdout), side, gross return, touched, matched-day expectation, matched-day touch share."""
    n = A["c"].shape[0]
    Jh = {0: np.arange(cut), 1: np.arange(cut, n)}
    cache, rows = {}, []
    for s in specs:
        i, side, m, tg = s["i"], s["side"], s["m"], s["target"]
        half = 0 if i < cut else 1
        r, hit = trade_ret(A, i, side, m, tg)
        d = None if tg is None else side * (tg / A["o"][i, m] - 1)
        key = (half, side, m) if d is None else None
        if key is not None and key in cache:
            er, eh = cache[key]
        else:
            er, eh = expected(A, side, m, d, Jh[half])
            if key is not None:
                cache[key] = (er, eh)
        rows.append((i, half, side, r, hit, er, eh))
    return pd.DataFrame(rows, columns=["i", "half", "side", "r", "hit", "er", "eh"])


def tstat(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(x.mean() / (x.std(ddof=1) / math.sqrt(len(x)))) if len(x) > 2 and x.std() > 0 else 0.0


def p_one(t):
    return 0.5 * math.erfc(t / math.sqrt(2))


def holm(ps):
    ps = np.asarray(ps, float)
    order = np.argsort(ps)
    m = len(ps)
    adj, run = np.empty(m), 0.0
    for rank, k in enumerate(order):
        run = max(run, (m - rank) * ps[k])
        adj[k] = min(1.0, run)
    return adj


def half_stats(df, half, cost_bp=COST_BP):
    x = df[df.half == half]
    n = len(x)
    if n == 0:
        return dict(n=0, gross=float("nan"), net=float("nan"), tnet=0.0, ex=float("nan"), tex=0.0, p=1.0, hit=float("nan"), ehit=float("nan"))
    net = (x.r - cost_bp / 1e4).to_numpy()
    exc = (x.r - x.er).to_numpy()
    t = tstat(exc)
    return dict(n=n, gross=float(x.r.mean() * 1e4), net=float(net.mean() * 1e4), tnet=tstat(net), ex=float(exc.mean() * 1e4), tex=t, p=p_one(t),
                hit=float(x.hit.mean()), ehit=float(x.eh.mean()) if x.eh.notna().any() else float("nan"))


def plateau_ok(vol_tune, vol_hold):
    """The VOL construction agrees: its net mean is positive on BOTH halves."""
    return bool(vol_tune["net"] > 0 and vol_hold["net"] > 0)


def verdict(tu, ho, vol_ok):
    """tu / ho: half_stats of the primary (TPO) cell, the holdout one with its Holm-adjusted p in ho['padj']; vol_ok: the VOL construction has net > 0 on both halves."""
    if ho["n"] < MIN_HOLD_TRADES:
        return "UNDERPOWERED"
    passed = (tu["net"] > 0 and ho["net"] > 0 and tu["ex"] > 0 and ho["ex"] > 0 and ho["padj"] < 0.05 and vol_ok)
    if passed:
        return "PASS"
    lead = tu["n"] >= MIN_HOLD_TRADES and tu["net"] > 0 and ho["net"] > 0 and tu["tex"] >= 2 and ho["tex"] >= 2
    return "LEAD" if lead else "no"


# ------------------------------------------------------------------ the run

def run_block(A, dates, roll, mode, cut):
    P = profiles(A, mode)
    ok, ok2 = prior_flags(dates, roll)
    F = day_features(A)
    res = {}
    for name, rule in zip(CELLS, RULES):
        specs = rule(A, P, ok, ok2, F)
        res[name] = (specs, evaluate(A, specs, cut))
    return P, ok, res


def verdicts_from(stats):
    """The gate for every cell: the TPO numbers decide, the VOL construction must agree (plateau_ok)."""
    out = {}
    for name in CELLS:
        tu, ho = stats["tpo", name]
        sv = stats["vol", name]
        out[name] = verdict(tu, ho, plateau_ok(sv[0], sv[1]))
    return out


def analyze(A, dates, roll, cut):
    """(blocks, stats, verdicts): blocks[mode] = (profile, ok, {cell: (specs, trades)}); stats[mode, cell] = (tune, holdout) half_stats, the holdout one carrying its Holm-adjusted p ('padj') over the 9 cells of its construction;
    verdicts[cell] = the gate on the TPO construction, with the VOL construction as the plateau check."""
    blocks = {mode: run_block(A, dates, roll, mode, cut) for mode in MODES}
    stats = {}
    for mode in MODES:
        for name in CELLS:
            df = blocks[mode][2][name][1]
            stats[mode, name] = (half_stats(df, 0), half_stats(df, 1))
        adj = holm([stats[mode, c][1]["p"] for c in CELLS])
        for c, a in zip(CELLS, adj):
            stats[mode, c][1]["padj"] = float(a)
    return blocks, stats, verdicts_from(stats)


def fmt(x, w=7, d=2):
    return f"{x:{w}.{d}f}" if np.isfinite(x) else " " * (w - 3) + "nan"


def main():
    out = []

    def say(s=""):
        print(s, flush=True)
        out.append(s)

    d = load_nq()
    A, dates, prev, roll = build_sessions(d)
    n = len(dates)
    cut = int(TUNE * n)
    say(f"backtest/nq_profile.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; NQ.c.0 1-minute bars with volume, cash session 09:30-16:00 New York; prior-session profile; 1.27bp a trade; "
        f"matched-day control; tune = first {int(TUNE * 100)}% of sessions")
    say(f"sessions {n} ({dates[0]:%Y-%m-%d} .. {dates[-1]:%Y-%m-%d}); tune {cut} (to {dates[cut - 1]:%Y-%m-%d}), holdout {n - cut} (from {dates[cut]:%Y-%m-%d}); contract changes between kept sessions {int(roll.sum())}")
    blocks, stats, verdicts = analyze(A, dates, roll, cut)
    ok = blocks["tpo"][1]
    drift_t = np.mean(A["c"][:cut, -1] / A["o"][:cut, 0] - 1) * 1e4
    drift_h = np.mean(A["c"][cut:, -1] / A["o"][cut:, 0] - 1) * 1e4
    say(f"control for scale: long from the open to the close EVERY session = {drift_t:+.2f}bp (tune) / {drift_h:+.2f}bp (holdout) gross")
    for mode in MODES:
        P = blocks[mode][0]
        va_w = np.array([(P["vah"][i] - P["val"][i]) / A["c"][i, -1] * 1e4 for i in range(n)])
        inside = np.array([(P["val"][i] <= P["poc"][i] <= P["vah"][i]) for i in range(n)])
        o_out = [i for i in np.flatnonzero(ok) if not (P["val"][i - 1] <= A["o"][i, 0] <= P["vah"][i - 1])]
        say(f"[{mode.upper()}] profile checks: POC inside its value area on {inside.mean() * 100:.1f}% of sessions; median value-area width {np.median(va_w):.0f}bp of the close; "
            f"sessions opening outside the prior value area {len(o_out) / max(ok.sum(), 1) * 100:.1f}% ({len(o_out)} of {int(ok.sum())})")
    for mode in MODES:
        say()
        say(f"=== {mode.upper()} construction: every cell, tune | holdout (gross / net bp a trade at {COST_BP}bp, t of the net, EXCESS over matched days in bp and its t, Holm-adjusted holdout p) ===")
        for name in CELLS:
            tu, ho = stats[mode, name]
            fire = (tu["n"] + ho["n"]) / max(ok.sum(), 1) * 100
            say(f"  {name:32s} n {tu['n']:5d} | {ho['n']:5d}  fire {fire:5.1f}%  gross {fmt(tu['gross'])} | {fmt(ho['gross'])}  net {fmt(tu['net'])} | {fmt(ho['net'])}  "
                f"t {fmt(tu['tnet'], 5, 1)} | {fmt(ho['tnet'], 5, 1)}  excess {fmt(tu['ex'])} | {fmt(ho['ex'])}  t {fmt(tu['tex'], 5, 1)} | {fmt(ho['tex'], 5, 1)}  Holm p {ho.get('padj', float('nan')):.3f}")
    say()
    say("TARGET RULES: share of trades that touched the target vs the same trade on matched days (tune | holdout)")
    for mode in MODES:
        for name in CELLS[:3]:
            tu, ho = stats[mode, name]
            say(f"  [{mode}] {name:32s} touched {fmt(tu['hit'] * 100, 6, 1)}% | {fmt(ho['hit'] * 100, 6, 1)}%   matched days {fmt(tu['ehit'] * 100, 6, 1)}% | {fmt(ho['ehit'] * 100, 6, 1)}%   (R1's textbook claim: 80%)")
    say()
    say("SIDES AND YEARS (TPO): long / short counts and net bp by side over the whole period; net bp by calendar year")
    years = sorted(set(dates.year))
    for name in CELLS:
        df = blocks["tpo"][2][name][1]
        if not len(df):
            continue
        net = df.r.to_numpy() * 1e4 - COST_BP
        sd = df.side.to_numpy()
        yrs = np.asarray(dates[df.i.to_numpy()].year)
        if (sd < 0).any() and (sd > 0).any():
            ls = f"long {int((sd > 0).sum())} ({net[sd > 0].mean():+.2f}) short {int((sd < 0).sum())} ({net[sd < 0].mean():+.2f})"
        else:
            ls = f"one side only: {'long' if (sd > 0).any() else 'short'} {len(sd)} ({net.mean():+.2f})"
        yr = "  ".join(f"{str(y)[2:]}:{net[yrs == y].mean():+.1f}" for y in years if (yrs == y).sum() >= 5)
        say(f"  {name:32s} {ls}")
        say(f"      {yr}")
    say()
    say("COST SENSITIVITY (TPO): net bp a trade, tune | holdout, at 0.25 / 1.27 / 2.54 bp")
    for name in CELLS:
        df = blocks["tpo"][2][name][1]
        cells = []
        for cb in (0.25, COST_BP, 2 * COST_BP):
            a, b = half_stats(df, 0, cb), half_stats(df, 1, cb)
            cells.append(f"{fmt(a['net'])} | {fmt(b['net'])}")
        say(f"  {name:32s} " + "   ".join(cells))
    say()
    say("GATE (net > 0 on both halves at 1.27bp; excess > 0 on both halves; holdout Holm p < 0.05 over the 9 cells; >= 100 holdout trades; and the VOL construction also net > 0 on both halves)")
    passing = []
    for name in CELLS:
        tu, ho = stats["tpo", name]
        sv = stats["vol", name]
        v = verdicts[name]
        if v == "PASS":
            passing.append(name)
        say(f"  {name:32s} tune net {fmt(tu['net'])} (n {tu['n']}), holdout net {fmt(ho['net'])} (t {fmt(ho['tnet'], 5, 1)}, n {ho['n']}), excess {fmt(tu['ex'])} / {fmt(ho['ex'])} (t {fmt(tu['tex'], 5, 1)} / {fmt(ho['tex'], 5, 1)}), "
            f"Holm p {ho.get('padj', float('nan')):.3f}, VOL net {fmt(sv[0]['net'])} / {fmt(sv[1]['net'])}  ->  {v}")
    say(f"  cells passing: {len(passing)} of {len(CELLS)}  {passing}")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

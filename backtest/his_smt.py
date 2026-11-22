"""SMT DIVERGENCE AT THE FAKE BREAK - does a second index REFUSING to break its matching level pick the fake breaks that reverse? (2026-11-22)

THE USER (2026-11-22): "yes, test" - the first item of the study list: ICT's SMT divergence ('smart money technique'). The claim: when
NASDAQ sweeps a high or a low and a correlated index (the Dow, the S&P 500) does NOT sweep its matching one, the sweep is a stop hunt and
the price reverses; when both sweep, the break is real. It is the textbook answer to the question his_reclaim.py left open (he trades
fake breaks, 7 of 7 won; the setup itself is a coin flip) and it was never tested here: his_crossmarket.py only asked whether the S&P or
the Dow MOVED FIRST in the 10 s - 5 min before his clicks (ordinary).
DATA   NASDAQ: Exness USTECm ticks (ustec_tick_days.pkl, 181 days 2026-01-02 .. 09-14, mid). DOW (primary partner): Exness US30m 1-minute
       MID bars built from every tick by the same broker and code (mt5_1m.py; minute open in UTC -> minutes since 09:30 New York).
       S&P 500 (second partner): HistData SPXUSD bid minutes (stamps converted from New York time with daylight saving).
SETUP  his_reclaim.py's moments exactly (every 1-minute close + 14 s, 09:45-15:45 New York; the nearest swing level of the last 120
       minutes within 10 points, broken by more than 3 points since it formed), in two states:
         A  BEYOND - the price still on the broken side (his 7 reclaims; parity with his_reclaim.broken_level is checked on every moment)
         B  BACK   - the price already back on the level's original side (the ICT entry after the 'shift')
       the trade: the reversal side (a broken low -> buy, a broken high -> sell); the +-7 race on the mid (race2, 10 minutes).
SMT    the partner's MATCHING level = its lowest low (highest high) of the same 7 bars as NASDAQ's swing (j-3 .. j+3). The partner BROKE
       it if a closed bar since (j+4 .. the last closed bar) went beyond it by more than NASDAQ's 3-point rule scaled to the partner's
       price (primary) - or by any amount (strict). SMT = NASDAQ broke, the partner did not. Also continuous: the partner's depth beyond
       its level minus NASDAQ's, both in % of the level (terciles).
CANDLE SMT (every moment, all his entries) the last closed 1-minute candle against the one before: a lower low on exactly ONE of NASDAQ /
       the Dow -> bullish; a higher high on exactly one -> bearish (both flags -> none); the race in that direction.
REGISTERED BEFORE THE FIRST NUMBER (2026-11-22)
  S1  State A (his setup), Dow: SMT and no-SMT reclaims differ by at most 3 points on both halves; neither reaches 56%. (60%)
  S2  State B (after the shift), Dow: the same. (60%)
  S3  His 7 reclaims: at most 5 of 7 had the Dow holding (SMT). (55%)
  S4  Both partners holding (Dow AND S&P) lifts state A to at most 56% on either half. (70%)
  S5  Candle SMT as a rule wins 47-53% of races on both halves. (70%)
  S6  Where a candle SMT is active at his entries, his side matches it on 35-65%. (65%)
  S7  Clock check: the US30m builder's USTECm minute highs equal the tick cache's on >= 99% of minutes, and NASDAQ's minute returns
      correlate best at lag 0 with the Dow's and the S&P's (>= 0.7). (90%)
  Bar for a LEAD: SMT lifts state A or B by 5+ points on both halves. For a trade: 61% (the +-7 race after a ~1.5-point spread).

RESULT (2026-11-22, logs/his_smt.txt): SMT DOES NOT PICK THE FAKE BREAKS THAT REVERSE. The same 21,211 state-A moments as his_reclaim.py
  (0 mismatching moments). State A (his setup): with the Dow holding 51.4% / 52.0% of races (tune / holdout) against 49.6% / 52.5% when
  the Dow broke too (+1.8 / -0.5 points, day-bootstrap se 0.9); with the S&P holding 51.6% / 53.7% against 49.8% / 52.1% (+1.8 / +1.6,
  se 1.0) - small, and far under the 61% a trade needs; both holding 50.5% / 52.9%; the strict rule and the terciles flat. State B
  (after the shift): -1.0 / +0.2 points (Dow), -2.0 / -0.9 (S&P). Candle SMT as a rule 50.4% / 49.6%. His 7 reclaims: the Dow held on
  4, the S&P on 3, both on 3 of the 6 with a definite reading - more often than the average fake break (30% / 19% / 18% of moments;
  one-sided binomial p 0.13 / 0.13 / 0.07 on 7 trades: a lean, not a finding) - and he won the 3 where both indices broke too. No LEAD.
  S1-S6 right; S7 wrong on its threshold only: the Dow's minute correlation with NASDAQ is 0.58 (the S&P's 0.82), but lag 0 is the only
  non-zero lag for both and the minute builder reproduces the tick cache on 100% of 69,510 minutes - the clocks line up.

    python -m backtest.his_smt
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest.his_level_memory import BREAK, K, LOOK, NEAR, TICKS, minute_bars, swings  # noqa: E402
from backtest.his_reclaim import broken_level  # noqa: E402

LOG = ROOT / "logs" / "his_smt.txt"
DOW = ROOT / "strategy_analysis" / "data" / "mt5_1m" / "US30m.parquet"
NQX = ROOT / "strategy_analysis" / "data" / "mt5_1m" / "USTECm.parquet"
SPX = ROOT / "strategy_analysis" / "data" / "histdata" / "SPXUSD.parquet"
OPEN = 9 * 60 + 30                                                   # 09:30 New York, in minutes of the day
DAY_NS = 86_400 * 10**9


def by_day_minutes(path: Path, days, n_of: dict) -> dict:
    """{day: (high, low, close)} indexed by minute since 09:30 New York (NaN where a minute is missing)."""
    df = pd.read_parquet(path, columns=["t", "h", "l", "c"]).sort_values("t", kind="stable")
    lo_ms = pd.Timestamp(min(days)).value // 10**6 - 86_400_000
    hi_ms = pd.Timestamp(max(days)).value // 10**6 + 2 * 86_400_000
    df = df[(df.t >= lo_ms) & (df.t <= hi_ms)]
    loc = pd.DatetimeIndex(pd.to_datetime(df.t.to_numpy(), unit="ms", utc=True)).tz_convert("America/New_York").tz_localize(None)
    ns = loc.as_unit("ns").to_numpy().view("int64")
    dns = ns - ns % DAY_NS                                           # local midnight
    mn = (ns - dns) // (60 * 10**9) - OPEN
    h, l, c = df.h.to_numpy(float), df.l.to_numpy(float), df.c.to_numpy(float)
    out = {}
    for day in days:
        d = pd.Timestamp(day).value
        a, b = np.searchsorted(dns, d, "left"), np.searchsorted(dns, d, "right")
        if b <= a:
            continue
        n = n_of[day]
        m = mn[a:b]
        ok = (m >= 0) & (m < n)
        H, L, C = (np.full(n, np.nan) for _ in range(3))
        H[m[ok]], L[m[ok]], C[m[ok]] = h[a:b][ok], l[a:b][ok], c[a:b][ok]
        out[day] = (H, L, C)
    assert out, f"no minutes mapped from {path.name}"
    return out


def close_arr(ts: np.ndarray, mid: np.ndarray, n: int) -> np.ndarray:
    k = (ts // 60).astype(int)
    last = np.flatnonzero(np.r_[k[1:] != k[:-1], True])
    c = np.full(n, np.nan)
    c[k[last]] = mid[last]
    return c


def level_at(ts, mid, hi, lo, sh, sl, t: float):
    """The nearest swing level within NEAR points (as his_reclaim.broken_level), if BROKEN: its kind, bar, price, the reversal side,
    the state (A = the price still beyond it, B = back on its original side) and NASDAQ's deepest move beyond it (points)."""
    i = np.searchsorted(ts, t - 1.0, side="right") - 1
    if i < 0:
        return None
    p = float(mid[i])
    M = int(t // 60) - 1
    best = None
    for kind, idx, arr in (("hi", sh, hi), ("lo", sl, lo)):
        for j in idx[(idx <= M - K) & (idx >= M - LOOK)]:
            d = abs(arr[j] - p)
            if d <= NEAR and (best is None or d < best[0]):
                best = (d, kind, int(j), float(arr[j]))
    if best is None:
        return None
    _, kind, j, v = best
    seg_lo, seg_hi = lo[j + 1:M + 1], hi[j + 1:M + 1]
    if not len(seg_lo):
        return None
    if kind == "lo":
        if not (seg_lo < v - BREAK).any() or p == v:
            return None
        return dict(kind=kind, j=j, v=v, M=M, side=1, state="A" if p < v else "B", depth=float(v - np.nanmin(seg_lo)))
    if not (seg_hi > v + BREAK).any() or p == v:
        return None
    return dict(kind=kind, j=j, v=v, M=M, side=-1, state="A" if p > v else "B", depth=float(np.nanmax(seg_hi) - v))


def partner_break(ph, pl, kind: str, j: int, M: int, v: float):
    """The partner at NASDAQ's swing: (its depth beyond its matching level in % of it, broke by the scaled 3-point rule, broke at all),
    or None without data."""
    arr, ext = (pl, np.nanmin) if kind == "lo" else (ph, np.nanmax)
    w, a = arr[j - K:j + K + 1], arr[j + K + 1:M + 1]
    if not (np.isfinite(w).any() and np.isfinite(a).any()):
        return None
    pv = float(ext(w))
    dep = pv - float(np.nanmin(a)) if kind == "lo" else float(np.nanmax(a)) - pv
    return dep / pv, dep > BREAK * pv / v, dep > 0


def candle_smt(hi, lo, dh, dl, M: int) -> int:
    """+1 bullish / -1 bearish / 0: a lower low (higher high) on exactly one of NASDAQ and the Dow in the last closed candle."""
    if M < 1 or dh is None or M >= min(len(hi), len(dh)):             # a half-day: no candle there
        return 0
    v = (hi[M], hi[M - 1], lo[M], lo[M - 1], dh[M], dh[M - 1], dl[M], dl[M - 1])
    if not np.isfinite(v).all():
        return 0
    bull = (lo[M] < lo[M - 1]) != (dl[M] < dl[M - 1])
    bear = (hi[M] > hi[M - 1]) != (dh[M] > dh[M - 1])
    return 1 if bull and not bear else (-1 if bear and not bull else 0)


def boot_se(x: pd.DataFrame, col: str, reps: int = 500, seed: int = 7) -> float:
    """Day-block bootstrap standard error of win(col == 1) - win(col == 0) (moments in a day overlap)."""
    codes, uniq = pd.factorize(x.day)
    nd = len(uniq)
    win = x.win.to_numpy(float)
    m1, m0 = (x[col] == 1.0).to_numpy(float), (x[col] == 0.0).to_numpy(float)
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(reps):
        w = np.bincount(rng.integers(0, nd, nd), minlength=nd)[codes].astype(float)
        a, b = (w * m1).sum(), (w * m0).sum()
        if a > 0 and b > 0:
            out.append((w * m1 * win).sum() / a - (w * m0 * win).sum() / b)
    return float(np.std(out)) if out else np.nan


def main():
    from scipy.stats import binomtest
    import backtest.his_tape as TP
    from backtest.his_race_curve import race2
    cache = pickle.loads(TICKS.read_bytes())
    prep = {}
    for day, dd in cache.items():
        if dd is None:
            continue
        ts, mid = dd[0], dd[1]
        hi, lo = minute_bars(ts, mid)
        sh, sl = swings(hi, lo)
        prep[day] = (ts, mid, hi, lo, sh, sl)
    days = sorted(prep)
    cut = days[int(len(days) * 0.6)]
    n_of = {d: len(prep[d][2]) for d in days}
    dow, spx, nqx = by_day_minutes(DOW, days, n_of), by_day_minutes(SPX, days, n_of), by_day_minutes(NQX, days, n_of)

    # --- clock checks ---
    eq = tot = 0
    for d in days:
        if d in nqx:
            hx, ht = nqx[d][0][:390], prep[d][2][:390]
            ok = np.isfinite(hx) & np.isfinite(ht)
            tot += int(ok.sum())
            eq += int((np.abs(hx[ok] - ht[ok]) <= 0.05).sum())
    nq_close = {d: close_arr(prep[d][0], prep[d][1], n_of[d]) for d in days}
    lagc = {}
    for nm, P in (("Dow", dow), ("S&P", spx)):
        for L in (-2, -1, 0, 1, 2):
            xs, ys = [], []
            for d in days:
                if d not in P:
                    continue
                a, b = np.diff(nq_close[d][:391]), np.diff(P[d][2][:391])
                a2, b2 = (a[:-L], b[L:]) if L > 0 else ((a[-L:], b[:L]) if L < 0 else (a, b))
                ok = np.isfinite(a2) & np.isfinite(b2)
                xs.append(a2[ok])
                ys.append(b2[ok])
            lagc[(nm, L)] = float(np.corrcoef(np.concatenate(xs), np.concatenate(ys))[0, 1])

    # --- every moment ---
    rows, crow, mism = [], [], 0
    for day in days:
        ts, mid, hi, lo, sh, sl = prep[day]
        dh, dl, _ = dow.get(day, (None, None, None))
        sp = spx.get(day)
        for t in np.arange(15 * 60 + 14, 375 * 60 + 14, 60.0):
            lev = level_at(ts, mid, hi, lo, sh, sl, t)
            b = broken_level(ts, mid, hi, lo, sh, sl, t)
            in_a = lev is not None and lev["state"] == "A"
            if (b is not None) != in_a or (b is not None and b[0] != lev["side"]):
                mism += 1
            cs = candle_smt(hi, lo, dh, dl, int(t // 60) - 1)
            if cs:
                w = race2(ts, mid, t, cs, 600, 7, 7)
                if w is not None:
                    crow.append(dict(day=day, win=w))
            if lev is None:
                continue
            w = race2(ts, mid, t, lev["side"], 600, 7, 7)
            if w is None:
                continue
            r = dict(day=day, state=lev["state"], win=w)
            nq_pct = lev["depth"] / lev["v"]
            for nm, arrs in (("dow", (dh, dl) if dh is not None else None), ("spx", sp[:2] if sp is not None else None)):
                pb = partner_break(*arrs, lev["kind"], lev["j"], lev["M"], lev["v"]) if arrs is not None else None
                if pb is not None:
                    r[nm + "_rel"] = pb[0] - nq_pct
                    r[nm + "_smt"] = float(not pb[1])
                    r[nm + "_strict"] = float(not pb[2])
            rows.append(r)
    R = pd.DataFrame(rows)
    R["half"] = np.where(R.day < cut, "tune", "hold")
    both = R.dow_smt.notna() & R.spx_smt.notna()
    R["both_smt"] = np.where(both, np.where((R.dow_smt == 1.0) & (R.spx_smt == 1.0), 1.0,
                                            np.where((R.dow_smt == 0.0) & (R.spx_smt == 0.0), 0.0, np.nan)), np.nan)
    C = pd.DataFrame(crow)
    C["half"] = np.where(C.day < cut, "tune", "hold")

    out = [f"backtest/his_smt.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(days)} tick days, split {pd.Timestamp(cut):%Y-%m-%d}; "
           f"broken-level moments with a race: state A (still beyond) {int((R.state == 'A').sum()):,}, state B (back) {int((R.state == 'B').sum()):,}; "
           f"parity with his_reclaim.broken_level: {mism} mismatching moments", "",
           "  CLOCK CHECK",
           f"    the US30m builder's USTECm minute highs = the tick cache's on {eq:,} of {tot:,} minutes ({eq / max(tot, 1):.2%})"]
    for nm in ("Dow", "S&P"):
        out.append(f"    NASDAQ minute returns vs the {nm}'s, by lag (minutes; + = the {nm} later): "
                   + "  ".join(f"{L:+d} {lagc[(nm, L)]:+.3f}" for L in (-2, -1, 0, 1, 2)))
    res = {}

    def split(state, col, title):
        x = R[(R.state == state) & R[col].notna()]
        share = (x[col] == 1.0).mean()
        out.append(f"  {title}: SMT on {share:.0%} of {len(x):,} moments")
        out.append(f"    {'':<30}{'tune':>18}{'holdout':>18}")
        for val, nm in ((1.0, "SMT (partner held)"), (0.0, "no SMT (partner broke too)")):
            cells = []
            for h in ("tune", "hold"):
                y = x[(x[col] == val) & (x.half == h)]
                res[(state, col, val, h)] = y.win.mean() if len(y) else np.nan
                cells.append(f"{y.win.mean():.1%} of {len(y):,}" if len(y) else "-")
            out.append(f"    {nm:<30}{cells[0]:>18}{cells[1]:>18}")
        gaps = [res[(state, col, 1.0, h)] - res[(state, col, 0.0, h)] for h in ("tune", "hold")]
        out.append(f"    {'difference':<30}{gaps[0] * 100:>+17.1f}p{gaps[1] * 100:>+17.1f}p   (day-bootstrap se of the pooled difference "
                   f"{boot_se(x, col) * 100:.1f} points)")
        return gaps

    def terciles(state, col, title):
        x = R[(R.state == state) & R[col].notna()]
        q1, q2 = x[col].quantile([1 / 3, 2 / 3])
        tc = np.where(x[col] <= q1, 1, np.where(x[col] <= q2, 2, 3))
        cells = []
        for h in ("tune", "hold"):
            cells.append(" / ".join(f"{x[(tc == k) & (x.half == h)].win.mean():.1%}" for k in (1, 2, 3)))
        out.append(f"    {title} by tercile (partner broke LEAST relative to NASDAQ / middle / MOST): tune {cells[0]} | holdout {cells[1]}")

    gap = {}
    for state, nm in (("A", "STATE A - his setup: NASDAQ broke the level and is still beyond it (trade back through)"),
                      ("B", "STATE B - after the shift: NASDAQ broke the level and is already back (trade on)")):
        out += ["", f"  {nm}"]
        gap[(state, "dow")] = split(state, "dow_smt", "Dow, primary (scaled 3-point rule)")
        split(state, "dow_strict", "Dow, strict (never beyond its level at all)")
        terciles(state, "dow_rel", "Dow")
        gap[(state, "spx")] = split(state, "spx_smt", "S&P 500")
        terciles(state, "spx_rel", "S&P")
        split(state, "both_smt", "Dow AND S&P (both held vs both broke)")

    # --- his trades ---
    x = TP.entries()
    his, cand = [], []
    for r in x.itertuples():
        pr = prep.get(r.d)
        if pr is None:
            continue
        ts, mid, hi, lo, sh, sl = pr
        dh, dl, _ = dow.get(r.d, (None, None, None))
        sp = spx.get(r.d)
        cs = candle_smt(hi, lo, dh, dl, int(r.t // 60) - 1)
        won = race2(ts, mid, r.t, r.s, 600, 7, 7)
        if cs:
            cand.append(dict(match=cs == r.s, won=won))
        if r.t < 15 * 60:
            continue
        lev = level_at(ts, mid, hi, lo, sh, sl, float(r.t))
        if lev is None or lev["side"] != r.s:
            continue
        e = dict(d=r.d, s=r.s, state=lev["state"], won=won)
        nq_pct = lev["depth"] / lev["v"]
        for nm, arrs in (("dow", (dh, dl) if dh is not None else None), ("spx", sp[:2] if sp is not None else None)):
            pb = partner_break(*arrs, lev["kind"], lev["j"], lev["M"], lev["v"]) if arrs is not None else None
            e[nm] = None if pb is None else (not pb[1])
            e[nm + "_rel"] = None if pb is None else pb[0] - nq_pct
        his.append(e)
    Hh = pd.DataFrame(his)
    HA = Hh[Hh.state == "A"] if len(Hh) else Hh
    HB = Hh[Hh.state == "B"] if len(Hh) else Hh
    n_dow_a = int(sum(bool(v) for v in HA.dow if v is not None)) if len(HA) else 0
    out += ["", f"  HIS RECLAIMS (state A, his side = back through the level): {len(HA)}; the Dow held (SMT) on {n_dow_a}, the S&P on "
                f"{int(sum(bool(v) for v in HA.spx if v is not None)) if len(HA) else 0}; won {int((HA.won == 1).sum()) if len(HA) else 0}"]

    def yn(v):
        return "-" if v is None else ("HELD (SMT)" if v else "broke too")

    for r in HA.itertuples():
        out.append(f"    {r.d:%Y-%m-%d} {'BUY ' if r.s > 0 else 'SELL'}  Dow {yn(r.dow):<11} S&P {yn(r.spx):<11} "
                   f"{'won' if r.won == 1 else 'lost' if r.won == 0 else '-'}")
    out.append(f"  HIS TRADES in state B (already back, his side = the reversal side): {len(HB)}; the Dow held on "
               f"{int(sum(bool(v) for v in HB.dow if v is not None)) if len(HB) else 0}; won {int((HB.won == 1).sum()) if len(HB) else 0}")
    for r in HB.itertuples():
        out.append(f"    {r.d:%Y-%m-%d} {'BUY ' if r.s > 0 else 'SELL'}  Dow {yn(r.dow):<11} S&P {yn(r.spx):<11} "
                   f"{'won' if r.won == 1 else 'lost' if r.won == 0 else '-'}")

    # --- candle SMT ---
    cw = {h: C[C.half == h].win.mean() for h in ("tune", "hold")}
    Cd = pd.DataFrame(cand)
    k_m = int(Cd.match.sum()) if len(Cd) else 0
    p_m = binomtest(k_m, len(Cd), 0.5).pvalue if len(Cd) else np.nan
    out += ["", f"  CANDLE SMT (the last closed 1-minute candle: a new low / high on exactly one of NASDAQ and the Dow) as a rule: "
                f"{len(C):,} moments, race won {cw['tune']:.1%} (tune) / {cw['hold']:.1%} (holdout)",
            f"  at his entries: a candle SMT active on {len(Cd)}; his side = its direction on {k_m} ({k_m / max(len(Cd), 1):.0%}, binomial p "
            f"{p_m:.2f}); his race won {Cd[Cd.match].won.eq(1).mean() if k_m else float('nan'):.0%} when matching, "
            f"{Cd[~Cd.match.astype(bool)].won.eq(1).mean() if len(Cd) - k_m else float('nan'):.0%} when not"]

    # --- predictions ---
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731

    def s12(state):
        g = gap[(state, "dow")]
        top = max(res[(state, "dow_smt", v, h)] for v in (1.0, 0.0) for h in ("tune", "hold"))
        return all(abs(v) <= 0.03 for v in g) and top < 0.56, g

    s1, g1 = s12("A")
    s2, g2 = s12("B")
    both_a = [res[("A", "both_smt", 1.0, h)] for h in ("tune", "hold")]
    lead = [f"state {s} ({p})" for (s, p), g in gap.items() if all(v >= 0.05 for v in g)]
    lag_ok = all(max((-2, -1, 0, 1, 2), key=lambda L: lagc[(nm, L)]) == 0 and lagc[(nm, 0)] >= 0.7 for nm in ("Dow", "S&P"))
    out += ["", "REGISTERED PREDICTIONS",
            f"  S1 state A, Dow: SMT vs no SMT within 3 points on both halves, neither >= 56% -> {ok(s1)} (" + " | ".join(f"{v * 100:+.1f}" for v in g1) + " points)",
            f"  S2 state B, Dow: the same -> {ok(s2)} (" + " | ".join(f"{v * 100:+.1f}" for v in g2) + " points)",
            f"  S3 his 7 reclaims at most 5 with the Dow holding -> {ok(n_dow_a <= 5)} ({n_dow_a} of {len(HA)})",
            f"  S4 both partners holding, state A at most 56% on either half -> {ok(all(v < 0.56 for v in both_a))} ("
            + " / ".join(f"{v:.1%}" for v in both_a) + ")",
            f"  S5 candle SMT as a rule 47-53% on both halves -> {ok(all(0.47 <= v <= 0.53 for v in cw.values()))}",
            f"  S6 his side = the candle SMT on 35-65% -> {ok(0.35 <= k_m / max(len(Cd), 1) <= 0.65)}",
            f"  S7 clock: >= 99% equal minute highs and lag 0 best (>= 0.7) for both partners -> {ok(eq / max(tot, 1) >= 0.99 and lag_ok)}",
            f"  LEAD bar (5+ points on both halves): {', '.join(lead) if lead else 'none'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

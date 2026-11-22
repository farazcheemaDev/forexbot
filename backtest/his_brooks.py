"""AL BROOKS PRICE ACTION AT THE FAKE BREAK - the breakout bar, its follow-through, the signal bar and second entries (2026-11-22)

THE USER (2026-11-22): "run" - item 2 of the study list. Al Brooks (Reading Price Charts Bar by Bar, 2009; Trading Price Action, 2012)
scalps index futures with small targets and a high win rate, and much of his method is about FAILED BREAKOUTS. His tells that a
breakout will fail: a WEAK breakout bar (small body, closing away from its extreme, no bigger than the bars before it), NO FOLLOW-THROUGH
(the next bar does not close further beyond), a STRONG SIGNAL BAR for the reversal (closing near its extreme in the new direction), the
entry on a STOP one tick past the signal bar, and SECOND ENTRIES (the second attempt to reverse, 'H2' / 'L2', is more reliable than the
first). Single candles were already tested (his_candle_shape.py: every cell ~50%); this tests Brooks's SEQUENCE inside the fake-break
setup, and his second-entry scalp on every minute.
DATA   Exness USTECm ticks (ustec_tick_days.pkl, 181 days 2026-01-02 .. 09-14, mid), 1-minute open / high / low / close built from them.
SETUP  his_reclaim.py's state-A moments exactly (his_smt.level_at, parity-checked there: every 1-minute close + 14 s, 09:45-15:45 New York;
       the nearest swing level of the last 120 minutes within 10 points, broken by more than 3 points, the price still beyond it);
       the trade back through it; the +-7 race on the mid (race2, 10 minutes), by half.
BROOKS'S READINGS (closed bars only)
  breakout bar   the first bar beyond the level by > 3 points. STRONG = a body in the breakout direction of at least half its range, a close
                 in its outer third, and a range at least the average of the 10 bars before; else WEAK
  follow-through the bar after it closes further beyond AND has a body in the breakout direction; else NONE (needs that bar closed)
  signal bar     the last closed bar: a body in the reclaim direction and a close in its outer third = STRONG
  entries        his count since the deepest point: an ATTEMPT = a bar with a higher high (for a buy; a lower low for a sell) after a bar
                 without one. FIRST ENTRY = no attempt yet; SECOND ENTRY = one attempt so far and the last bar is not one (the pullback
                 after it). The entry: a stop past the signal bar valid for the next bar (filled at once if the price is already past
                 it); the race from the fill
  combination    WEAK breakout bar + NO follow-through + STRONG signal bar
GENERAL RULE (every minute, 09:45-15:45): Brooks's second-entry scalp - the lowest low (highest high) of the last 20 bars, one attempt
  since and the last bar not one -> a buy (sell) stop past the signal bar for the next bar; first entries for comparison; with and
  without his 20-bar EMA filter (buy only above it, sell only below).
HIS ENTRIES (all scored NASDAQ clicks): the signal bar in his direction and his count since the 20-bar extreme against him, against
  every minute's distribution.
REGISTERED BEFORE THE FIRST NUMBER (2026-11-22)
  R1  State A: WEAK and STRONG breakout bars differ by at most 3 points on both halves; neither reaches 56%. (60%)
  R2  State A: NO follow-through and follow-through - the same. (60%)
  R3  State A: a STRONG signal bar and the rest - the same. (60%)
  R4  State A: second entries and first entries (stop fills) - the same. (60%)
  R5  The combination stays under 56% on both halves, at the moment and with the stop entry. (70%)
  R6  No 'Brooks-good' reading (weak breakout bar, no follow-through, strong signal bar, second-entry setup) holds for more than 5 of
      his 7 reclaims. (55%)
  R7  The general second-entry scalp (with and without the EMA filter) wins 47-53% of races on both halves. (70%)
  R8  At his entries the signal bar is strong in his direction no more often than at every minute (binomial p > 0.05). (65%)
  Bar for a LEAD: a reading lifts the race by 5+ points on both halves. For a trade: 61% (the +-7 race after a ~1.5-point spread).

RESULT (2026-11-22, logs/his_brooks.txt): BROOKS'S READINGS DO NOT PICK THE FAKE BREAKS THAT REVERSE. The same 21,211 state-A moments as
  his_reclaim.py. Two readings point Brooks's way on both halves, by 1-2 points: WEAK breakout bars 51.2% / 52.8% (tune / holdout)
  against STRONG 48.9% / 51.8%; NO follow-through 50.5% / 53.2% against 49.7% / 51.5%. The signal bar (+0.4 / -1.2), second vs first
  entry on the stop (+1.9 / -2.8), and the combination (51.6% / 51.6%; with the stop entry 53.7% / 49.7%) flip or do nothing - all far
  under the 61% a trade needs. The general second-entry scalp on every minute: 53.8% tune / 48.5% holdout (a flip, R7 wrong on the tune
  half only); with the 20-bar EMA 49.8% / 45.6%. His 7 reclaims: weak breakout bar 5 (52% of moments; p 0.26), no follow-through 4 (49%),
  strong signal bar 2 (30%), second-entry setup 2 (8%; p 0.10). His 42 clicks: the signal bar strong in his direction 33% = every minute's
  33%; his count since the 20-bar extreme matches every minute's distribution (second-entry setup 12% vs 7%, p 0.17). R1-R6, R8 right;
  R7 wrong. No LEAD.

    python -m backtest.his_brooks
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest.his_level_memory import BREAK, TICKS, minute_bars, swings  # noqa: E402
from backtest.his_smt import level_at  # noqa: E402

LOG = ROOT / "logs" / "his_brooks.txt"
EXT = 20                                                             # the general rule's look-back for the extreme (bars)


def ohlc(ts: np.ndarray, mid: np.ndarray):
    k = (ts // 60).astype(int)
    n = int(k.max()) + 1
    first = np.flatnonzero(np.r_[True, k[1:] != k[:-1]])
    last = np.flatnonzero(np.r_[k[1:] != k[:-1], True])
    o, c = np.full(n, np.nan), np.full(n, np.nan)
    o[k[first]], c[k[last]] = mid[first], mid[last]
    h, l = minute_bars(ts, mid)
    return o, h, l, c


def strong(o, h, l, c, i: int, d: int, body_min: float = 0.0):
    """Bar i has a body in direction d (at least body_min of its range) and closes in its outer third in d; None without data."""
    if i < 0 or i >= len(h):
        return None
    r = h[i] - l[i]
    if not (np.isfinite(r) and r > 0 and np.isfinite(o[i]) and np.isfinite(c[i])):
        return None
    body = c[i] - o[i]
    cl = (c[i] - l[i]) / r if d > 0 else (h[i] - c[i]) / r
    return bool(d * body > 0 and abs(body) / r >= body_min and cl >= 2 / 3)


def edges(h, l, e: int, M: int, side: int):
    """Brooks's count after the extreme bar e up to bar M: (attempts in side's direction, bar M is one, bar M STARTS one)."""
    cnt, prev, fM, fresh = 0, False, False, False
    for i in range(e + 1, M + 1):
        a, b = (h[i], h[i - 1]) if side > 0 else (l[i - 1], l[i])
        f = bool(np.isfinite(a) and np.isfinite(b) and a > b)
        if f and not prev:
            cnt += 1
            fresh = i == M
        elif i == M:
            fresh = False
        if i == M:
            fM = f
        prev = f
    return cnt, fM, fresh


def stop_fill(ts, mid, t0: float, t1: float, side: int, px: float):
    """A stop past px in side's direction placed at t0, valid to t1: the fill time (t0 itself if the price is already past), else None."""
    i0 = np.searchsorted(ts, t0, side="right") - 1
    if i0 >= 0 and side * (mid[i0] - px) > 0:
        return float(t0)
    a, b = np.searchsorted(ts, t0, side="right"), np.searchsorted(ts, t1, side="right")
    hit = np.flatnonzero(side * (mid[a:b] - px) > 0)
    return float(ts[a + hit[0]]) if len(hit) else None


def brooks_a(o, h, l, c, lev: dict) -> dict:
    """Brooks's readings at a state-A moment (the price still beyond a broken level)."""
    kind, j, v, M, side = lev["kind"], lev["j"], lev["v"], lev["M"], lev["side"]
    seg = l[j + 1:M + 1] if kind == "lo" else h[j + 1:M + 1]
    brk = np.flatnonzero(seg < v - BREAK) if kind == "lo" else np.flatnonzero(seg > v + BREAK)
    bo = j + 1 + int(brk[0])
    e = j + 1 + (int(np.nanargmin(seg)) if kind == "lo" else int(np.nanargmax(seg)))
    d_bo = -side
    sb = strong(o, h, l, c, bo, d_bo, 0.5)
    prior = (h - l)[max(bo - 10, 0):bo]
    rel = (h[bo] - l[bo]) / np.nanmean(prior) if np.isfinite(prior).any() and np.nanmean(prior) > 0 else np.nan
    strong_bo = np.nan if sb is None or not np.isfinite(rel) else float(sb and rel >= 1.0)
    ft = np.nan
    if bo + 1 <= M and np.isfinite(c[bo + 1]) and np.isfinite(o[bo + 1]) and np.isfinite(c[bo]):
        ft = float(d_bo * (c[bo + 1] - c[bo]) > 0 and d_bo * (c[bo + 1] - o[bo + 1]) > 0)
    sg = strong(o, h, l, c, M, side)
    cnt, fM, _ = edges(h, l, e, M, side)
    entry = "first" if cnt == 0 else ("second" if cnt == 1 and not fM else "other")
    return dict(strong_bo=strong_bo, ft=ft, sig=np.nan if sg is None else float(sg), entry=entry)


def setup_gen(h, l, M: int, side: int):
    """The general rule's reading on bar M for side: 'second' / 'first' / None (since the 20-bar extreme against side)."""
    w = (l if side > 0 else h)[M - EXT + 1:M + 1]
    if M - EXT + 1 < 1 or not np.isfinite(w).any():
        return None
    e = M - EXT + 1 + (int(np.nanargmin(w)) if side > 0 else int(np.nanargmax(w)))
    cnt, fM, fresh = edges(h, l, e, M, side)
    if cnt == 0:
        return "first"
    if cnt == 1 and not fM:
        return "second"
    return None


def count_cat(h, l, M: int, side: int) -> str:
    """His count since the 20-bar extreme against him, as a category."""
    w = (l if side > 0 else h)[M - EXT + 1:M + 1]
    if M - EXT + 1 < 1 or not np.isfinite(w).any():
        return "n/a"
    e = M - EXT + 1 + (int(np.nanargmin(w)) if side > 0 else int(np.nanargmax(w)))
    cnt, fM, fresh = edges(h, l, e, M, side)
    if cnt == 0:
        return "no attempt yet (first-entry setup)"
    if cnt == 1:
        return "attempt 1 under way" if fM else "after attempt 1 (second-entry setup)"
    if cnt == 2:
        return "attempt 2 under way" if fM else "after attempt 2"
    return "3+ attempts"


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
        o, h, l, c = ohlc(ts, mid)
        sh, sl = swings(h, l)
        prep[day] = (ts, mid, o, h, l, c, sh, sl)
    days = sorted(prep)
    cut = days[int(len(days) * 0.6)]
    A, G = [], []
    base_sig, base_cat = {1: [], -1: []}, {}
    for day in days:
        ts, mid, o, h, l, c, sh, sl = prep[day]
        n = len(h)
        ema = pd.Series(c).ffill().ewm(span=20, adjust=False).mean().to_numpy()
        for t in np.arange(15 * 60 + 14, 375 * 60 + 14, 60.0):
            M = int(t // 60) - 1
            if M + 1 >= n:
                break
            # every minute: the base rates for his-entry readings
            for side in (1, -1):
                sg = strong(o, h, l, c, M, side)
                if sg is not None:
                    base_sig[side].append(sg)
                k = count_cat(h, l, M, side)
                base_cat[k] = base_cat.get(k, 0) + 1
            # the general second-entry scalp, decided at bar M's close
            st = {s: setup_gen(h, l, M, s) for s in (1, -1)}
            for kind in ("second", "first"):
                sides = [s for s in (1, -1) if st[s] == kind]
                if len(sides) != 1:
                    continue
                s = sides[0]
                px = h[M] if s > 0 else l[M]
                te = stop_fill(ts, mid, 60.0 * (M + 1), 60.0 * (M + 2), s, px) if np.isfinite(px) else None
                w = race2(ts, mid, te, s, 600, 7, 7) if te is not None else None
                if w is not None:
                    G.append(dict(day=day, kind=kind, ema_ok=float(s * (c[M] - ema[M]) > 0), win=w))
            # state A
            lev = level_at(ts, mid, h, l, sh, sl, t)
            if lev is None or lev["state"] != "A":
                continue
            w = race2(ts, mid, t, lev["side"], 600, 7, 7)
            if w is None:
                continue
            f = brooks_a(o, h, l, c, lev)
            px = h[M] if lev["side"] > 0 else l[M]
            te = stop_fill(ts, mid, t, 60.0 * (M + 2), lev["side"], px) if np.isfinite(px) else None
            ws = race2(ts, mid, te, lev["side"], 600, 7, 7) if te is not None else None
            A.append(dict(day=day, win=w, win_stop=np.nan if ws is None else float(ws), **f))
    R = pd.DataFrame(A)
    R["half"] = np.where(R.day < cut, "tune", "hold")
    R["combo"] = np.where(R.strong_bo.notna() & R.ft.notna() & R.sig.notna(),
                          ((R.strong_bo == 0.0) & (R.ft == 0.0) & (R.sig == 1.0)).astype(float), np.nan)
    Gd = pd.DataFrame(G)
    Gd["half"] = np.where(Gd.day < cut, "tune", "hold")

    out = [f"backtest/his_brooks.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(days)} tick days, split {pd.Timestamp(cut):%Y-%m-%d}; "
           f"state-A moments with a race: {len(R):,} (his_reclaim.py: 21,211); reclaim race won "
           f"{R[R.half == 'tune'].win.mean():.1%} / {R[R.half == 'hold'].win.mean():.1%} (tune / holdout)", ""]
    res = {}

    def rate(x, col="win"):
        y = x[col].dropna()
        return (y.mean() if len(y) else np.nan), len(y)

    def table(title, groups, col="win", key=None):
        out.append(f"  {title}")
        out.append(f"    {'':<44}{'tune':>18}{'holdout':>18}")
        for nm, m in groups:
            cells = []
            for h_ in ("tune", "hold"):
                r_, n_ = rate(R[m & (R.half == h_)] if isinstance(m, pd.Series) and len(m) == len(R) else m[m.half == h_], col)
                if key is not None:
                    res[(key, nm, h_)] = r_
                cells.append(f"{r_:.1%} of {n_:,}" if n_ else "-")
            out.append(f"    {nm:<44}{cells[0]:>18}{cells[1]:>18}")

    table("THE BREAKOUT BAR (the first bar more than 3 points beyond the level)",
          [("WEAK breakout bar", R.strong_bo == 0.0), ("STRONG breakout bar", R.strong_bo == 1.0)], key="bo")
    table("FOLLOW-THROUGH (the bar after the breakout bar)",
          [("NO follow-through", R.ft == 0.0), ("follow-through", R.ft == 1.0)], key="ft")
    table("THE SIGNAL BAR (the last closed bar, in the reclaim direction)",
          [("STRONG signal bar", R.sig == 1.0), ("not", R.sig == 0.0)], key="sig")
    table("FIRST vs SECOND ENTRY, stop past the signal bar, race from the fill",
          [("second entry (after one failed attempt)", R.entry == "second"), ("first entry (no attempt yet)", R.entry == "first"),
           ("other (attempt under way / later)", R.entry == "other")], col="win_stop", key="entry")
    table("THE COMBINATION (weak breakout bar + no follow-through + strong signal bar)",
          [("combination, at the moment", R.combo == 1.0), ("the rest, at the moment", R.combo == 0.0)], key="combo")
    table("THE COMBINATION with Brooks's stop entry",
          [("combination, stop entry", R.combo == 1.0), ("every state-A moment, stop entry", pd.Series(True, index=R.index))],
          col="win_stop", key="combo_stop")

    # the general second-entry scalp
    out += ["", "  THE GENERAL SECOND-ENTRY SCALP (every minute; the 20-bar extreme, a stop past the signal bar, race from the fill)",
            f"    {'':<44}{'tune':>18}{'holdout':>18}"]
    for nm, m in (("second entries", Gd.kind == "second"), ("second entries WITH the 20-bar EMA", (Gd.kind == "second") & (Gd.ema_ok == 1.0)),
                  ("first entries", Gd.kind == "first"), ("first entries WITH the 20-bar EMA", (Gd.kind == "first") & (Gd.ema_ok == 1.0))):
        cells = []
        for h_ in ("tune", "hold"):
            y = Gd[m & (Gd.half == h_)]
            res[("gen", nm, h_)] = y.win.mean() if len(y) else np.nan
            cells.append(f"{y.win.mean():.1%} of {len(y):,}" if len(y) else "-")
        out.append(f"    {nm:<44}{cells[0]:>18}{cells[1]:>18}")

    # his trades
    x = TP.entries()
    his7, hall = [], []
    for r in x.itertuples():
        pr = prep.get(r.d)
        if pr is None:
            continue
        ts, mid, o, h, l, c, sh, sl = pr
        M = int(r.t // 60) - 1
        if M < EXT or M + 1 >= len(h):
            continue
        won = race2(ts, mid, r.t, r.s, 600, 7, 7)
        hall.append(dict(sig=strong(o, h, l, c, M, r.s), cat=count_cat(h, l, M, r.s), won=won))
        if r.t < 15 * 60:
            continue
        lev = level_at(ts, mid, h, l, sh, sl, float(r.t))
        if lev is None or lev["state"] != "A" or lev["side"] != r.s:
            continue
        f = brooks_a(o, h, l, c, lev)
        his7.append(dict(d=r.d, s=r.s, won=won, **f))
    H7, HA = pd.DataFrame(his7), pd.DataFrame(hall)

    def lab(v, yes, no):
        return "-" if not np.isfinite(v) else (yes if v == 1.0 else no)

    out += ["", f"  HIS RECLAIMS (state A, his side = back through the level): {len(H7)}; won {int((H7.won == 1).sum())}"]
    for r in H7.itertuples():
        out.append(f"    {r.d:%Y-%m-%d} {'BUY ' if r.s > 0 else 'SELL'}  breakout bar {lab(r.strong_bo, 'STRONG', 'weak'):<7} "
                   f"follow-through {lab(r.ft, 'yes', 'NONE'):<5} signal bar {lab(r.sig, 'STRONG', 'weak'):<7} entry {r.entry:<7} "
                   f"{'won' if r.won == 1 else 'lost' if r.won == 0 else '-'}")
    good = {"weak breakout bar": int((H7.strong_bo == 0.0).sum()), "no follow-through": int((H7.ft == 0.0).sum()),
            "strong signal bar": int((H7.sig == 1.0).sum()), "second-entry setup": int((H7.entry == "second").sum())}
    base_good = {"weak breakout bar": (R.strong_bo == 0.0).sum() / R.strong_bo.notna().sum(),
                 "no follow-through": (R.ft == 0.0).sum() / R.ft.notna().sum(),
                 "strong signal bar": (R.sig == 1.0).sum() / R.sig.notna().sum(),
                 "second-entry setup": (R.entry == "second").mean()}
    out.append("    Brooks-good readings among his 7 (share at every state-A moment): "
               + ", ".join(f"{k} {v} ({base_good[k]:.0%})" for k, v in good.items()))

    hs = HA[HA.sig.notna()]
    k_sig = int(hs.sig.astype(bool).sum())
    p_base = float(np.mean(base_sig[1] + base_sig[-1]))
    p_sig = binomtest(k_sig, len(hs), p_base).pvalue if len(hs) else np.nan
    tot = sum(base_cat.values())
    out += ["", f"  HIS ENTRIES ({len(HA)} scored NASDAQ clicks): the signal bar strong in his direction on {k_sig} of {len(hs)} "
                f"({k_sig / max(len(hs), 1):.0%}; every minute {p_base:.0%}; binomial p {p_sig:.2f})",
            "    his count since the 20-bar extreme against him (every minute's share in brackets):"]
    for k in ("no attempt yet (first-entry setup)", "attempt 1 under way", "after attempt 1 (second-entry setup)", "attempt 2 under way",
              "after attempt 2", "3+ attempts"):
        m = HA.cat == k
        out.append(f"      {k:<40} {int(m.sum()):>3} ({m.mean():.0%})  [{base_cat.get(k, 0) / tot:.0%}]  his race won "
                   + (f"{HA[m].won.eq(1).mean():.0%}" if m.any() else "-"))

    # predictions
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731

    def pair(key, a, b):
        g = [res[(key, a, h_)] - res[(key, b, h_)] for h_ in ("tune", "hold")]
        top = max(res[(key, nm, h_)] for nm in (a, b) for h_ in ("tune", "hold"))
        return all(abs(v) <= 0.03 for v in g) and top < 0.56, g

    r1, g1 = pair("bo", "WEAK breakout bar", "STRONG breakout bar")
    r2, g2 = pair("ft", "NO follow-through", "follow-through")
    r3, g3 = pair("sig", "STRONG signal bar", "not")
    r4, g4 = pair("entry", "second entry (after one failed attempt)", "first entry (no attempt yet)")
    c5 = [res[("combo", "combination, at the moment", h_)] for h_ in ("tune", "hold")] + \
         [res[("combo_stop", "combination, stop entry", h_)] for h_ in ("tune", "hold")]
    g7 = [res[("gen", nm, h_)] for nm in ("second entries", "second entries WITH the 20-bar EMA") for h_ in ("tune", "hold")]
    lead = [k for k, g in (("breakout bar", g1), ("follow-through", g2), ("signal bar", g3), ("second entry", g4)) if all(v >= 0.05 for v in g)]
    fmt = lambda g: " | ".join(f"{v * 100:+.1f}" for v in g)  # noqa: E731
    out += ["", "REGISTERED PREDICTIONS",
            f"  R1 weak vs strong breakout bar within 3 points, neither >= 56% -> {ok(r1)} ({fmt(g1)} points)",
            f"  R2 no follow-through vs follow-through the same -> {ok(r2)} ({fmt(g2)} points)",
            f"  R3 strong signal bar vs the rest the same -> {ok(r3)} ({fmt(g3)} points)",
            f"  R4 second vs first entry the same -> {ok(r4)} ({fmt(g4)} points)",
            f"  R5 the combination under 56% at the moment and with the stop entry -> {ok(all(v < 0.56 for v in c5))} ("
            + " / ".join(f"{v:.1%}" for v in c5) + ")",
            f"  R6 no Brooks-good reading for more than 5 of his 7 -> {ok(max(good.values()) <= 5)} ({max(good.values())})",
            f"  R7 the general second-entry scalp 47-53% on both halves -> {ok(all(0.47 <= v <= 0.53 for v in g7))} ("
            + " / ".join(f"{v:.1%}" for v in g7) + ")",
            f"  R8 his strong signal bars no more often than every minute (p > 0.05) -> {ok(p_sig > 0.05)}",
            f"  LEAD bar (5+ points on both halves): {', '.join(lead) if lead else 'none'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

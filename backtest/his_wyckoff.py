"""WYCKOFF AT THE FAKE BREAK - the spring, its test, and the volume behind them (2026-11-22)

THE USER (2026-11-22): "run wyckoff" - item 3 of the study list. Richard Wyckoff's SPRING is the textbook fake break: the price breaks a
trading range's support, the selling dries up, and it comes back into the range (an UPTHRUST is the mirror at resistance). Wyckoff's
tells (as taught by Pruden, Villahermosa): the safest buy is the TEST - after the spring and the return, the price comes back DOWN
toward the spring low on LOWER VOLUME and NARROWER bars and holds above it; a shallow spring on light volume ('No. 3') can be bought
at once, a deep one on heavy volume ('No. 1') needs a test; a spring matters at the support of a TRADING RANGE; and heavy effort
(volume) for little result (depth) shows absorption. Volume is the core of the method, so this uses REAL CME volume.
DATA   Exness USTECm ticks (ustec_tick_days.pkl, 181 days 2026-01-02 .. 09-14, mid) for the levels, the bars and the race; CME NQ
       1-minute VOLUME (Databento, strategy_analysis/data/nq_1m/NQ_2026.parquet, the most-traded contract each minute, the bar's open
       time -> minutes since 09:30 New York).
SETUP  his_reclaim.py's state-A moments exactly (his_smt.level_at: every 1-minute close + 14 s, 09:45-15:45 New York; the nearest swing
       level of the last 120 minutes within 10 points, broken by more than 3 points, the price still beyond it); the trade back through
       it; the +-7 race on the mid (race2, 10 minutes), by half. State B (the price already back) for the tests that hold above it.
WYCKOFF'S READINGS (closed bars only; 'spring' below = spring or upthrust)
  the spring leg   from the first bar beyond the level (> 3 points) to the deepest bar (the spring low): its mean volume, mean bar range,
                   depth (points beyond the level), volume against the 20 bars before it, effort = its total volume per point of depth
  TEST             a bar has CLOSED back across the level after the spring low and the price is beyond it again (state A) - the
                   secondary test; FIRST = no close back across yet. In state B a test = a pullback of 3+ points from the high after the
                   return. Test volume / range = the mean over the bars since the post-return extreme; LOW-VOLUME test = below the
                   spring leg's, NARROW = bar ranges below the spring leg's
  spring type      No. 3 = depth and relative volume both below the tune half's medians; No. 1 = both above
  range support    the broken level was the lowest low (highest high) of the 60 bars before the break: the edge of the range
  the full entry   a TEST on lower volume and narrower bars than the spring, at a range-support level
REGISTERED BEFORE THE FIRST NUMBER (2026-11-22)
  W1  State A: TESTS and FIRST pushes differ by at most 3 points on both halves; neither reaches 56%. (60%)
  W2  Tests (state A and the state-B pullbacks): LOW-volume and higher-volume tests differ by at most 3 points on both halves; none
      reaches 56%. (60%)
  W3  No. 3 springs and No. 1 springs differ by at most 3 points on both halves; neither reaches 56%. (60%)
  W4  Range-support springs and interior-swing springs differ by at most 3 points on both halves; neither reaches 56%. (60%)
  W5  Effort vs result: the top and bottom terciles of volume per point of depth differ by at most 3 points on both halves. (60%)
  W6  The full Wyckoff entry stays under 56% on both halves. (70%)
  W7  His 7 reclaims: at most 5 of 7 are TESTS. (55%)
  W8  Alignment: CME minute returns and volume line up with the Exness ticks best at lag 0 (returns correlation >= 0.9). (90%)
  Bar for a LEAD: a reading lifts the race by 5+ points on both halves. For a trade: 61% (the +-7 race after a ~1.5-point spread).

RESULT (2026-11-22, logs/his_wyckoff.txt): WYCKOFF'S READINGS DO NOT PICK THE FAKE BREAKS THAT REVERSE. The same 21,211 state-A moments as
  his_reclaim.py; CME minute returns line up with the Exness ticks at +0.997 at lag 0. The test vs the first push -1.1 / +1.1 points
  (tune / holdout); low- vs higher-volume tests -1.5 / +0.8 (state A) and +0.4 / +1.8 (state-B pullbacks); range support +0.9 / +0.5;
  effort vs result -1.2 / +0.7; the full Wyckoff entry 50.1% / 55.6% (holdout only). One reading points Wyckoff's way on both halves:
  No. 3 springs (shallow, light volume) 50.8% / 53.5% against No. 1 (deep, heavy) 48.8% / 50.2% (+1.9 / +3.3 points - W3 wrong by 0.3)
  - the same 'weak breaks fail a little more' as Brooks's weak breakout bar (his_brooks.py), and as far from 61%. His 7 reclaims: 4 tests
  (56% of moments), 2 No. 3 springs (24%), 2 full Wyckoff entries (11%; p 0.18) - and 5 at a range-support level (31%; one-sided p
  0.033, among ~12 readings checked on these 7 trades across his_smt / his_brooks / this file: not significant after correction). W1,
  W2, W4-W7 right; W3 wrong (+3.3 on the holdout); W8 wrong on a near tie only (volume vs tick count +0.473 at lag -1 against +0.459 at
  lag 0 - both series are autocorrelated; the returns settle the clock). No LEAD.

    python -m backtest.his_wyckoff
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest.his_brooks import ohlc  # noqa: E402
from backtest.his_level_memory import BREAK, TICKS, swings  # noqa: E402
from backtest.his_smt import close_arr, level_at  # noqa: E402

LOG = ROOT / "logs" / "his_wyckoff.txt"
NQ = ROOT / "strategy_analysis" / "data" / "nq_1m" / "NQ_2026.parquet"
OPEN = 9 * 60 + 30
DAY_NS = 86_400 * 10**9
NEAR_SPRING, PULL = 5.0, 3.0


def cme_minutes(days, n_of: dict) -> dict:
    """{day: (volume, close, contract id)} of the CME NQ contract traded most in each minute, by minute since 09:30 New York."""
    d = pd.read_parquet(NQ, columns=["ts_event", "close", "volume", "instrument_id"])
    d = d.sort_values(["ts_event", "volume"], kind="stable").drop_duplicates("ts_event", keep="last")
    loc = d.ts_event.dt.tz_convert("America/New_York").dt.tz_localize(None)
    ns = loc.dt.as_unit("ns").to_numpy().view("int64")
    dns = ns - ns % DAY_NS
    mn = (ns - dns) // (60 * 10**9) - OPEN
    vol, cl, iid = d.volume.to_numpy(float), d.close.to_numpy(float), d.instrument_id.to_numpy(float)
    order = np.argsort(dns, kind="stable")
    dns, mn, vol, cl, iid = dns[order], mn[order], vol[order], cl[order], iid[order]
    out = {}
    for day in days:
        x = pd.Timestamp(day).value
        a, b = np.searchsorted(dns, x, "left"), np.searchsorted(dns, x, "right")
        if b <= a:
            continue
        n = n_of[day]
        m = mn[a:b]
        ok = (m >= 0) & (m < n)
        V, C, I = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
        V[m[ok]], C[m[ok]], I[m[ok]] = vol[a:b][ok], cl[a:b][ok], iid[a:b][ok]
        out[day] = (V, C, I)
    assert out, "no CME minutes mapped"
    return out


def argext(a: np.ndarray, lowest: bool) -> int:
    return int(np.nanargmin(a)) if lowest else int(np.nanargmax(a))


def nmean(a: np.ndarray) -> float:
    return float(np.nanmean(a)) if len(a) and np.isfinite(a).any() else np.nan


def features(h, l, c, vol, lev: dict, p: float) -> dict:
    """Wyckoff's readings for the broken level at this moment (both states)."""
    kind, j, v, M, side = lev["kind"], lev["j"], lev["v"], lev["M"], lev["side"]
    lo_k = kind == "lo"
    seg = l[j + 1:M + 1] if lo_k else h[j + 1:M + 1]
    brk = np.flatnonzero(seg < v - BREAK) if lo_k else np.flatnonzero(seg > v + BREAK)
    bo = j + 1 + int(brk[0])
    e = j + 1 + argext(seg, lo_k)
    sp = float(seg[e - j - 1])
    depth = (v - sp) if lo_k else (sp - v)
    rng = h - l
    sv = vol[bo:e + 1]
    f = dict(depth=depth, spring_vol=nmean(sv))
    pv = nmean(vol[max(bo - 20, 0):bo])
    f["relvol"] = f["spring_vol"] / pv if np.isfinite(pv) and pv > 0 else np.nan
    f["eff"] = float(np.nansum(sv)) / depth if np.isfinite(sv).any() and depth > 0 else np.nan
    spring_rng = nmean(rng[bo:e + 1])
    w60 = (l if lo_k else h)[max(bo - 60, 0):bo]
    f["rs"] = float(np.isfinite(w60).any() and (v <= np.nanmin(w60) + 1e-9 if lo_k else v >= np.nanmax(w60) - 1e-9))
    rec = np.flatnonzero(side * (c[e + 1:M + 1] - v) > 0)            # a CLOSE back across the level after the spring low
    f["reclaimed"] = float(len(rec) > 0)
    f["lvt"] = f["nar"] = f["near"] = f["pull"] = np.nan
    if len(rec):
        r0 = e + 1 + int(rec[0])
        seg2 = (h if side > 0 else l)[r0:M + 1]
        if np.isfinite(seg2).any():
            q = r0 + argext(seg2, side < 0)                            # the extreme after the return (a high, for a buy)
            idx = np.arange(q + 1, M + 1) if q < M else np.array([M])
            tv, tr = nmean(vol[idx]), nmean(rng[idx])
            if np.isfinite(tv) and np.isfinite(f["spring_vol"]):
                f["lvt"] = float(tv < f["spring_vol"])
            if np.isfinite(tr) and np.isfinite(spring_rng):
                f["nar"] = float(tr < spring_rng)
            f["near"] = float(abs(p - sp) <= NEAR_SPRING)
            qx = (h if side > 0 else l)[q]
            f["pull"] = float(side * (qx - p) >= PULL)
    return f


def lag_corr(pairs: list, lags=(-1, 0, 1)) -> dict:
    res = {}
    for L in lags:
        xs, ys = [], []
        for a, b in pairs:
            a2, b2 = (a[:-L], b[L:]) if L > 0 else ((a[-L:], b[:L]) if L < 0 else (a, b))
            ok = np.isfinite(a2) & np.isfinite(b2)
            xs.append(a2[ok])
            ys.append(b2[ok])
        res[L] = float(np.corrcoef(np.concatenate(xs), np.concatenate(ys))[0, 1])
    return res


def main():
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
        prep[day] = (ts, mid, h, l, c, sh, sl)
    days = sorted(prep)
    cut = days[int(len(days) * 0.6)]
    n_of = {d: len(prep[d][2]) for d in days}
    cme = cme_minutes(days, n_of)

    # alignment: CME vs the Exness ticks
    ret_pairs, vol_pairs = [], []
    for d in days:
        if d not in cme:
            continue
        ts, mid = prep[d][0], prep[d][1]
        ex_c = close_arr(ts, mid, n_of[d])
        ticks = np.bincount((ts // 60).astype(int), minlength=n_of[d]).astype(float)
        dc = np.diff(cme[d][1][:391])
        dc[np.diff(cme[d][2][:391]) != 0] = np.nan                      # a contract switch is not a return
        ret_pairs.append((np.diff(ex_c[:391]), dc))
        vol_pairs.append((ticks[:390], cme[d][0][:390]))
    rc, vc = lag_corr(ret_pairs), lag_corr(vol_pairs)

    A, B = [], []
    for day in days:
        ts, mid, h, l, c, sh, sl = prep[day]
        if day not in cme:
            continue
        vol = cme[day][0]
        for t in np.arange(15 * 60 + 14, 375 * 60 + 14, 60.0):
            lev = level_at(ts, mid, h, l, sh, sl, t)
            if lev is None:
                continue
            w = race2(ts, mid, t, lev["side"], 600, 7, 7)
            if w is None:
                continue
            p = float(mid[np.searchsorted(ts, t - 1.0, side="right") - 1])
            f = features(h, l, c, vol, lev, p)
            (A if lev["state"] == "A" else B).append(dict(day=day, win=w, **f))
    RA, RB = pd.DataFrame(A), pd.DataFrame(B)
    for R in (RA, RB):
        R["half"] = np.where(R.day < cut, "tune", "hold")
    tune = RA[RA.half == "tune"]
    md, mr = tune.depth.median(), tune.relvol.median()
    e1, e2 = tune.eff.quantile([1 / 3, 2 / 3])
    RA["type"] = np.where((RA.depth < md) & (RA.relvol < mr), "No. 3", np.where((RA.depth > md) & (RA.relvol > mr), "No. 1", "mixed"))
    RA.loc[RA.relvol.isna(), "type"] = "n/a"
    RA["eff_t"] = np.where(RA.eff.isna(), 0, np.where(RA.eff <= e1, 1, np.where(RA.eff <= e2, 2, 3)))
    RA["full"] = np.where(RA.lvt.notna() & RA.nar.notna(),
                          ((RA.reclaimed == 1.0) & (RA.lvt == 1.0) & (RA.nar == 1.0) & (RA.rs == 1.0)).astype(float), np.nan)

    out = [f"backtest/his_wyckoff.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(days)} tick days ({len(cme)} with CME volume), split "
           f"{pd.Timestamp(cut):%Y-%m-%d}; state-A moments {len(RA):,} (his_reclaim.py: 21,211), state-B {len(RB):,}; reclaim race "
           f"{RA[RA.half == 'tune'].win.mean():.1%} / {RA[RA.half == 'hold'].win.mean():.1%} (tune / holdout)", "",
           "  ALIGNMENT, CME NQ vs the Exness ticks (by lag in minutes; + = CME later)",
           "    minute returns: " + "  ".join(f"{L:+d} {rc[L]:+.3f}" for L in (-1, 0, 1)),
           "    minute volume vs tick count: " + "  ".join(f"{L:+d} {vc[L]:+.3f}" for L in (-1, 0, 1))]
    res = {}

    def table(R, title, groups, key):
        out.extend(["", f"  {title}", f"    {'':<48}{'tune':>18}{'holdout':>18}"])
        for nm, m in groups:
            cells = []
            for h_ in ("tune", "hold"):
                y = R[m & (R.half == h_)]
                res[(key, nm, h_)] = y.win.mean() if len(y) else np.nan
                cells.append(f"{y.win.mean():.1%} of {len(y):,}" if len(y) else "-")
            out.append(f"    {nm:<48}{cells[0]:>18}{cells[1]:>18}")

    table(RA, "STATE A: THE TEST vs THE FIRST PUSH (his setup: still beyond the broken level)",
          [("TEST (closed back across, now beyond again)", RA.reclaimed == 1.0), ("FIRST push (no close back across yet)", RA.reclaimed == 0.0),
           ("TEST within 5 points of the spring low", (RA.reclaimed == 1.0) & (RA.near == 1.0))], "test")
    table(RA, "STATE A TESTS: the volume and bar size of the test against the spring",
          [("LOW-volume test", RA.lvt == 1.0), ("higher-volume test", RA.lvt == 0.0),
           ("NARROW-bar test", RA.nar == 1.0), ("wider-bar test", RA.nar == 0.0)], "lvtA")
    table(RB, "STATE B TESTS: a pullback of 3+ points after the return, holding above the level",
          [("LOW-volume pullback", (RB.pull == 1.0) & (RB.lvt == 1.0)), ("higher-volume pullback", (RB.pull == 1.0) & (RB.lvt == 0.0)),
           ("every state-B moment", pd.Series(True, index=RB.index))], "lvtB")
    table(RA, f"STATE A: SPRING TYPE (depth median {md:.1f} points, volume vs the 20 bars before median {mr:.2f}x, both from the tune half)",
          [("No. 3 (shallow, light volume)", RA.type == "No. 3"), ("No. 1 (deep, heavy volume)", RA.type == "No. 1"),
           ("mixed", RA.type == "mixed")], "type")
    table(RA, "STATE A: RANGE SUPPORT (the level was the extreme of the 60 bars before the break)",
          [("range-support spring", RA.rs == 1.0), ("interior swing", RA.rs == 0.0)], "rs")
    table(RA, "STATE A: EFFORT vs RESULT (the spring leg's volume per point of depth, terciles from the tune half)",
          [("low effort per point", RA.eff_t == 1), ("middle", RA.eff_t == 2), ("HIGH effort per point (absorption)", RA.eff_t == 3)], "eff")
    table(RA, "STATE A: THE FULL WYCKOFF ENTRY (a test, lower volume and narrower bars than the spring, at range support)",
          [("full entry", RA.full == 1.0), ("other tests and pushes with a reading", RA.full == 0.0)], "full")

    # his trades
    x = TP.entries()
    his = []
    for r in x.itertuples():
        pr = prep.get(r.d)
        if pr is None or r.t < 15 * 60 or r.d not in cme:
            continue
        ts, mid, h, l, c, sh, sl = pr
        lev = level_at(ts, mid, h, l, sh, sl, float(r.t))
        if lev is None or lev["side"] != r.s:
            continue
        p = float(mid[np.searchsorted(ts, float(r.t) - 1.0, side="right") - 1])
        f = features(h, l, c, cme[r.d][0], lev, p)
        tp = "n/a" if not np.isfinite(f["relvol"]) else ("No. 3" if f["depth"] < md and f["relvol"] < mr else
                                                         ("No. 1" if f["depth"] > md and f["relvol"] > mr else "mixed"))
        his.append(dict(d=r.d, s=r.s, state=lev["state"], won=race2(ts, mid, r.t, r.s, 600, 7, 7), type=tp, **f))
    Hh = pd.DataFrame(his)
    H7 = Hh[Hh.state == "A"]
    HB = Hh[Hh.state == "B"]

    def yn(v, yes, no):
        return "-" if not np.isfinite(v) else (yes if v == 1.0 else no)

    out += ["", f"  HIS RECLAIMS (state A, his side = back through the level): {len(H7)}; won {int((H7.won == 1).sum())}"]
    for r in H7.itertuples():
        out.append(f"    {r.d:%Y-%m-%d} {'BUY ' if r.s > 0 else 'SELL'}  {'TEST ' if r.reclaimed == 1.0 else 'first'}  spring {r.type:<6} "
                   f"depth {r.depth:5.1f}  volume x{r.relvol:4.2f}  {'range support' if r.rs == 1.0 else 'interior     '}  "
                   f"test volume {yn(r.lvt, 'LOW', 'higher'):<6}  bars {yn(r.nar, 'NARROW', 'wider'):<6}  "
                   f"{'won' if r.won == 1 else 'lost' if r.won == 0 else '-'}")
    n_test = int((H7.reclaimed == 1.0).sum())
    base = {"tests": (RA.reclaimed == 1.0).mean(), "No. 3": (RA.type == "No. 3").mean(), "range support": (RA.rs == 1.0).mean()}
    out.append(f"    among his 7: tests {n_test} (every state-A moment {base['tests']:.0%}), No. 3 springs {int((H7.type == 'No. 3').sum())} "
               f"({base['No. 3']:.0%}), range support {int((H7.rs == 1.0).sum())} ({base['range support']:.0%})")
    out.append(f"  HIS STATE-B TRADES (already back, his side = the reversal side): {len(HB)}; pullbacks of 3+ points "
               f"{int((HB.pull == 1.0).sum())}; low-volume {int((HB.lvt == 1.0).sum())}; won {int((HB.won == 1).sum())}")

    # predictions
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731

    def pair(key, a, b):
        g = [res[(key, a, h_)] - res[(key, b, h_)] for h_ in ("tune", "hold")]
        top = max(res[(key, nm, h_)] for nm in (a, b) for h_ in ("tune", "hold"))
        return all(abs(v) <= 0.03 for v in g) and top < 0.56, g

    w1, g1 = pair("test", "TEST (closed back across, now beyond again)", "FIRST push (no close back across yet)")
    w2a, g2a = pair("lvtA", "LOW-volume test", "higher-volume test")
    w2b, g2b = pair("lvtB", "LOW-volume pullback", "higher-volume pullback")
    w3, g3 = pair("type", "No. 3 (shallow, light volume)", "No. 1 (deep, heavy volume)")
    w4, g4 = pair("rs", "range-support spring", "interior swing")
    g5 = [res[("eff", "HIGH effort per point (absorption)", h_)] - res[("eff", "low effort per point", h_)] for h_ in ("tune", "hold")]
    full = [res[("full", "full entry", h_)] for h_ in ("tune", "hold")]
    lead = [k for k, g in (("test", g1), ("low-volume test (A)", g2a), ("low-volume pullback (B)", g2b), ("spring type", g3),
                           ("range support", g4), ("effort vs result", g5)) if all(v >= 0.05 for v in g)]
    fmt = lambda g: " | ".join(f"{v * 100:+.1f}" for v in g)  # noqa: E731
    out += ["", "REGISTERED PREDICTIONS",
            f"  W1 tests vs first pushes within 3 points, neither >= 56% -> {ok(w1)} ({fmt(g1)} points)",
            f"  W2 low- vs higher-volume tests within 3 points, none >= 56% -> {ok(w2a and w2b)} (state A {fmt(g2a)}; state B {fmt(g2b)} points)",
            f"  W3 No. 3 vs No. 1 springs within 3 points, neither >= 56% -> {ok(w3)} ({fmt(g3)} points)",
            f"  W4 range support vs interior within 3 points, neither >= 56% -> {ok(w4)} ({fmt(g4)} points)",
            f"  W5 effort vs result top vs bottom tercile within 3 points -> {ok(all(abs(v) <= 0.03 for v in g5))} ({fmt(g5)} points)",
            f"  W6 the full Wyckoff entry under 56% on both halves -> {ok(all(v < 0.56 for v in full))} (" + " / ".join(f"{v:.1%}" for v in full) + ")",
            f"  W7 his 7 reclaims at most 5 tests -> {ok(n_test <= 5)} ({n_test} of {len(H7)})",
            f"  W8 alignment best at lag 0, returns >= 0.9 -> {ok(max(rc, key=rc.get) == 0 and max(vc, key=vc.get) == 0 and rc[0] >= 0.9)}",
            f"  LEAD bar (5+ points on both halves): {', '.join(lead) if lead else 'none'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

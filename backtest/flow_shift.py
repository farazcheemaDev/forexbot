"""SHIFTING WEIGHT FROM MOMENTUM TO FORCED FLOW WHEN THE ALTS BLEED (2026-11-15)

THE USER (2026-11-15): "Yes, test it" - after works_map.py found the books in three families, with the FORCED-FLOW family (bear sleeve,
capit2, news, crowd, crash bids) earning most in alt bleeds (+157%/yr annualised, deep bleeds +192%) and the daily breakout book
losing there (-14%). Already tested and NOT re-run here: cutting the TREND book in such states (runner_gate.py: trend longs x0.5 when
few coins run - fails the bet-smaller line on the tune half; alt_bear.py: trend x0.5 in alt bears - fails in all 4 phases). The trend
book stays at x1.0 in every variant below. What is new: raising the forced-flow books in a bleed, cutting the daily book there, and
running the crowd book only in a bleed.

STATE    bleed on day D = the median point-in-time top-40 alt's return over the 30 days to the close of D-1 is -15% or worse
         (works_map.alt_median_30; known at D 00:00 UTC).
WEIGHTS  (never read a label after the outcome - CLAUDE.md s3)
  per trade at ENTRY: capit2 (the slot allocator with each trade's leverage x its weight, liquidation at that leverage modelled as
         daily_combos.allocate does) and news (each trade's stake x its weight, news/combo.daily's booking) - the state on the
         entry day.
  per day on MARKED-TO-MARKET series: the bear sleeve, the crash bids (bought and sold inside the hour), the daily book (marked
         daily by daily_combos.curve) and the crowd book (marked daily) - the state known at the day's open; resizing a held book
         costs 6bp of the change in weight times its gross exposure (sleeve 1, daily 0.5, crowd 1) on each day the state flips.
VARIANTS (the base = the final machine's 9 books as deployed, the 10 orderings, trend gains shrunk 3x)
  V1 FLOW x2    sleeve, bids, capit2, news x2 in a bleed
  V2 SHIFT      V1 + the daily book x0.5 in a bleed
  V3 CROWD-B    the base + the crowd book x1 only in a bleed
  V4 ALL        V2 + V3
  REF           the base + the crowd book x1 always (the fresh account's set), for V3
  printed, not judged: V1 at x1.5; V2 with the bleed line at -10% and -20%.
PASS     a variant beats the bet-smaller line - the base x k at the SAME biggest fall (rsi80_overlap.line_gap: the typical 12 months
         on $300, mean over orderings' windows) - on BOTH halves (machine.CUT, 2024-08-29), with its fall inside the line's range.
         A pass is a candidate for the next code window (doc 22 freezes the bots to 2027-04-09), not a change to the machine.

REGISTERED BEFORE THE FIRST NUMBER (2026-11-15; my prior that V1 or V2 passes: about 30%)
  F1  V1 does NOT clear the line on both halves: doubling the forced-flow books doubles their crash tails too (capit2 at 4x).
  F2  V2's gap is larger than V1's on both halves (cutting the daily book where it loses helps).
  F3  V3 (crowd only in a bleed) has a smaller gap than REF (crowd always) on both halves: the crowd book earns in every state but bull.
  F4  The bleed state is on 25-35% of the days.
  F5  At x2, 1% or more of capit2's bleed-day trades are liquidated.

RESULT (2026-11-15, logs/flow_shift.txt): NO PASS. Parity exact (all weights 1 reproduce the cached machine, gap 0). Bleed on 28.8% of
days. Every judged variant LOSES to the bet-bigger line on the tune half: V1 FLOW x2 -$1,033 / -$547 (tune / holdout, typical $300 year
against the base x k at the same fall), V2 SHIFT -$796 / -$313, V3 CROWD-B -$579 / +$2,773, V4 ALL -$686 / +$3,348. The shift does earn
where it should (V2 minus the base: +103% of the account summed over the tune half's bleed days, +43% over the holdout's) but it deepens
the worst month from -19.2% / -31.3% to -26.4% / -38.5% and the fall by 6-5 points; scaling the whole machine up to the same fall earns
more. At x2 capit2 runs at 4x and 51 of its 878 bleed-day trades (5.8%) are liquidated; at x1.5 (printed, not judged) 1.9%, gap
-$220 / +$2,017. The bleed line moved to -10% / -20% (printed): worse on both halves / tune negative. The one row that clears the line
on BOTH halves is the reference: the crowd book held ALWAYS (+$535 / +$4,101) - crowd_combo.py's 2026-10-23 finding again, and a lead
on paper (verdict 2027-04-09), not a pass of this test. F1-F5 all right. Tests 7; planted bugs 11 of 11 (three first survivors were gaps
in my tests: tied entries, the loss floor, a news trade spanning a weight change); control survived.

    python -m backtest.flow_shift      (needs works_map.py's series cache; ~10 minutes: capit2 is regenerated for its 4 phases)
"""
from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "flow_shift.txt"
BLEED = -0.15
FEE1 = 0.0006                                              # one way, per unit of notional resized
GROSS = {"sleeve": 1.0, "daily": 0.5, "crowd": 1.0}
CUT = pd.Timestamp("2024-08-29")


# ---------------------------------------------------------------- weighting (pure; tested)

def allocate_w(T: pd.DataFrame, seed: int, lev: float, w: np.ndarray, slots: int = 8) -> list:
    """daily_combos.allocate with each trade's leverage = lev x w[q]; liquidation at that trade's own leverage. w = 1 reproduces it."""
    rng = np.random.default_rng(seed)
    rnd = rng.random(len(T))
    tin = T.t_in.to_numpy("datetime64[ns]")
    order = sorted(range(len(T)), key=lambda q: (tin[q], 0.0, rnd[q]))
    tout, net, worst = T.t_out.to_numpy("datetime64[ns]"), T.net.to_numpy(), T.worst.to_numpy()
    eq, open_, out = 1.0, [], []
    for q in order:
        for p in sorted([p for p in open_ if p[0] <= tin[q]], key=lambda p: p[0]):
            eq += p[1]
        open_ = [p for p in open_ if p[0] > tin[q]]
        if eq <= 0:
            break
        if len(open_) >= slots:
            continue
        size = eq / slots
        lq = lev * w[q]
        liq = 1 / lq - 0.005 - 0.0006
        pnl = -size if worst[q] >= liq else size * max(lq * net[q], -1.0)
        open_.append((tout[q], pnl))
        out.append((q, size, pnl))
    return out


def news_daily_w(trades: list, wfun, slots: int = 10, frac: float = 0.10) -> pd.Series:
    """news.combo.daily with each trade's stake x wfun(t_in). wfun = 1 reproduces it."""
    trades = sorted(trades, key=lambda x: x[0])
    eq, open_, pts = 1.0, [], []
    for t_in, t_out, net in trades:
        for p in sorted([p for p in open_ if p[0] <= t_in]):
            eq += p[1]
            pts.append((p[0], eq))
        open_ = [p for p in open_ if p[0] > t_in]
        if len(open_) >= slots or eq <= 0:
            continue
        open_.append((t_out, eq * frac * wfun(t_in) * net))
    for p in sorted(open_):
        eq += p[1]
        pts.append((p[0], eq))
    s = pd.Series([e for _, e in pts], index=pd.to_datetime([t for t, _ in pts])).groupby(level=0).last()
    s = s.resample("D").last().ffill()
    return s.pct_change().fillna(0.0)


def resized(x: pd.Series, w: pd.Series, gross: float) -> pd.Series:
    """A marked-to-market daily series held at weight w (known at each day's open), minus 6bp x |change in w| x gross on the days w
    changes."""
    w = w.reindex(x.index).ffill().fillna(1.0)
    dw = w.diff().abs().fillna(0.0)
    return x * w - FEE1 * dw * gross


def state_weight(bleed: pd.Series, k: float) -> pd.Series:
    return pd.Series(np.where(bleed.fillna(False).astype(bool), k, 1.0), index=bleed.index)


def day_lookup(bleed: pd.Series):
    """t (any timestamp) -> the bleed state of its UTC day (known at that day's open)."""
    idx = pd.DatetimeIndex(bleed.index).as_unit("ns").asi8
    v = bleed.fillna(False).astype(bool).to_numpy()

    def f(t):
        i = np.searchsorted(idx, pd.Timestamp(t).floor("D").value, side="right") - 1
        return bool(v[i]) if i >= 0 else False
    return f


# ---------------------------------------------------------------- the books

def build(M, idx, bleed_fn, bleed_day, k_flow, k_daily, crowd_mode, crowd, news_trades, capit_T, ndx):
    """One variant's 10 ordering series. crowd_mode: None / 'bleed' / 'always'."""
    from backtest import capit_combos as cc
    out, liq_n = [], [0, 0]
    wnews = (lambda t: k_flow if bleed_fn(t) else 1.0)
    news = news_daily_w(news_trades, wnews).reindex(idx).fillna(0.0)
    for sd, x in enumerate(M):
        coff = cc.PHASES[sd % 4]
        T = capit_T[coff]
        wq = np.array([k_flow if bleed_fn(t) else 1.0 for t in T.t_in])
        tk = allocate_w(T.assign(units=None), sd, 2.0, wq)
        cap = cc.curve(T, tk).pct_change().reindex(idx).fillna(0.0)
        if k_flow != 1.0:
            for q, size, pnl in tk:
                if wq[q] != 1.0:
                    liq_n[1] += 1
                    liq_n[0] += pnl == -size
        wf, wd = state_weight(bleed_day, k_flow), state_weight(bleed_day, k_daily)
        s = (x.trend + x.mn_blend + x.carry + resized(x.sleeve, wf, GROSS["sleeve"]) + x.bids * wf.reindex(idx).ffill().fillna(1.0)
             + resized(x.daily, wd, GROSS["daily"]) + cap + news + ndx)
        if crowd_mode == "always":
            s = s + crowd
        elif crowd_mode == "bleed":
            s = s + resized(crowd, pd.Series(np.where(bleed_day.fillna(False).astype(bool), 1.0, 0.0), index=bleed_day.index), GROSS["crowd"])
        out.append(s)
    return out, liq_n


def main():
    from backtest import all_books as ab
    from backtest import capit_combos as cc
    from backtest import machine_combos as mc
    from backtest import works_map as wm
    from backtest.rsi80_overlap import line_gap
    import news.combo as NC
    t0 = time.time()
    M = pickle.loads((ROOT / "logs" / "daily_combos_cache" / "alt_bear_books.pkl").read_bytes())
    idx = M[0].index
    S, st, _ = wm.load()
    crowd = S["crowd"].reindex(idx).fillna(0.0)
    ndx = ab.ndx_dip().reindex(idx).fillna(0.0)
    NC.TYPES, NC.HOLD, NC.STOP = ("adds_products", "monitoring_tag"), 72, 0.25
    news_trades = NC.news_trades(0.0012)
    capit_T = {off: cc.gen(off, dict(cc.BASE, **mc.CAPIT_BETTER)) for off in cc.PHASES}
    end = idx[-1] + pd.Timedelta(days=1)
    halves = {"tune": (idx[0], CUT), "holdout": (CUT, end)}

    def bleed_of(line):
        b = (st.alt30 <= line).reindex(idx)
        return b, day_lookup(b)

    b15, f15 = bleed_of(BLEED)
    # parity: every weight at 1 must reproduce the cached machine books
    base, _ = build(M, idx, lambda t: False, b15 & False, 1.0, 1.0, None, crowd, news_trades, capit_T, ndx)
    ref_nine = [x[ab.BOOKS].sum(axis=1) + ab.news_book().reindex(idx).fillna(0.0) + ndx for x in M]
    par = max(float((a - b).abs().max()) for a, b in zip(base, ref_nine))
    L = [f"backtest/flow_shift.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the final machine's 9 books, 10 orderings, {idx[0]:%Y-%m-%d} .. "
         f"{idx[-1]:%Y-%m-%d}; trend gains shrunk 3x; halves split {CUT.date()}; judged against the base x k at the same biggest fall", "",
         f"PARITY: all weights 1 reproduce the cached machine (max daily gap {par:.1e}) -> {'OK' if par < 1e-9 else 'MISMATCH - STOP'}",
         f"BLEED (median top-40 alt <= {BLEED:.0%} over 30 days): on {b15.fillna(False).mean() * 100:.1f}% of days; tune "
         f"{b15[idx < CUT].fillna(False).mean() * 100:.1f}%, holdout {b15[idx >= CUT].fillna(False).mean() * 100:.1f}%", ""]
    V = {}
    V["V1 FLOW x2"] = build(M, idx, f15, b15, 2.0, 1.0, None, crowd, news_trades, capit_T, ndx)
    V["V2 SHIFT"] = build(M, idx, f15, b15, 2.0, 0.5, None, crowd, news_trades, capit_T, ndx)
    V["V3 CROWD-B"] = build(M, idx, f15, b15, 1.0, 1.0, "bleed", crowd, news_trades, capit_T, ndx)
    V["V4 ALL"] = build(M, idx, f15, b15, 2.0, 0.5, "bleed", crowd, news_trades, capit_T, ndx)
    V["REF crowd always"] = build(M, idx, f15, b15, 1.0, 1.0, "always", crowd, news_trades, capit_T, ndx)
    V["(V1 at x1.5)"] = build(M, idx, f15, b15, 1.5, 1.0, None, crowd, news_trades, capit_T, ndx)
    for line in (-0.10, -0.20):
        b, f = bleed_of(line)
        V[f"(V2, bleed line {line:.0%})"] = build(M, idx, f, b, 2.0, 0.5, None, crowd, news_trades, capit_T, ndx)
    hdr = f"   {'variant':<26}{'half':>9}{'typical':>10}{'line':>10}{'gap':>9}{'fall':>7}{'worst mo':>9}{'mo up':>7}"
    L += ["THE BASE ($300, 12 months, mean over orderings)"]
    from backtest.machine import summary
    for h, (a, b) in halves.items():
        s = summary([x[(x.index >= a) & (x.index < b)] for x in base])
        L.append(f"   base {h:<9} typical ${s['typ']:,.0f}, bad ${s['bad']:,.0f}, worst month {s['wm']:+.1f}%, fall {s['dd']:.0f}%, months up {s['up']:.0f}%")
    L += ["", "VARIANTS vs THE LINE (the base x k at the same biggest fall)", hdr]
    G = {}
    for nm, (xs, liq) in V.items():
        g = {h: line_gap(base, xs, hh) for h, hh in halves.items()}
        G[nm] = g
        for h in halves:
            c = g[h]["combo"]
            L.append(f"   {nm:<26}{h:>9}{c['typ']:>10,.0f}{g[h]['line_typ']:>10,.0f}{g[h]['gap']:>+9,.0f}{c['dd']:>6.0f}%{c['wm']:>+8.1f}%{c['up']:>6.0f}%"
                     f"{'' if g[h]['inside'] else '  (outside the line)'}")
        if liq[1]:
            L.append(f"   {'':<26}capit2 bleed-day trades at the raised weight: {liq[1]}, liquidated {liq[0]} ({liq[0] / liq[1] * 100:.1f}%)")
    # where the change earned: V2 minus base on bleed days and on other days
    L += ["", "WHERE V2 DIFFERS FROM THE BASE (sum of daily differences, mean over orderings, % of the account)"]
    d = [a - b for a, b in zip(V["V2 SHIFT"][0], base)]
    for h, (a, b) in halves.items():
        m = (idx >= a) & (idx < b)
        on = b15.fillna(False).to_numpy(bool)
        L.append(f"   {h:<9} bleed days {np.mean([x[m & on].sum() for x in d]) * 100:+.1f}%, other days {np.mean([x[m & ~on].sum() for x in d]) * 100:+.1f}%")
    passes = {nm: all(G[nm][h]["gap"] > 0 and G[nm][h]["inside"] for h in halves) for nm in ("V1 FLOW x2", "V2 SHIFT", "V3 CROWD-B", "V4 ALL")}
    liq1 = V["V1 FLOW x2"][1]
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    on = b15.fillna(False).mean()
    L += ["", "PASSING: " + (", ".join(k for k, v in passes.items() if v) or "none") + " (beats the line on both halves, inside its range)",
          "REGISTERED PREDICTIONS",
          f"  F1 V1 does not clear the line on both halves -> {ok(not passes['V1 FLOW x2'])}",
          f"  F2 V2's gap > V1's on both halves -> {ok(all(G['V2 SHIFT'][h]['gap'] > G['V1 FLOW x2'][h]['gap'] for h in halves))}",
          f"  F3 V3's gap < REF's on both halves -> {ok(all(G['V3 CROWD-B'][h]['gap'] < G['REF crowd always'][h]['gap'] for h in halves))}",
          f"  F4 bleed on 25-35% of days -> {ok(0.25 <= on <= 0.35)} ({on * 100:.1f}%)",
          f"  F5 >= 1% of capit2's raised trades liquidated -> {ok(liq1[1] > 0 and liq1[0] / liq1[1] >= 0.01)} ({liq1[0]} of {liq1[1]})",
          f"run time {time.time() - t0:.0f}s"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

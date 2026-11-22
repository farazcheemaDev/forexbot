"""ROUND-NUMBER ORDER CLUSTERS IN FOREX (Osler) - the one documented forced-order mechanism not yet tested here (2026-11-15)

The user: "I see an edge in forex too and we need to discover it, whatever it takes."
Mechanism (Osler 2003 / 2005, from a real dealer's order book): retail and corporate TAKE-PROFIT orders cluster AT round
numbers (the big figure, x.xx00), so a trend approaching one tends to stall / reverse there; STOP-LOSS orders cluster just
BEYOND round numbers, so once a round number is crossed the stops fire and the move runs further ("price cascade").
Both are forced orders sitting at knowable prices - the kind of structure that survives here, not a pattern.
Not tested before: the NASDAQ level fades (nasdaq_levelfade.py, his_levels.py) used index points, one market, no
control levels and not Osler's asymmetry.

DATA  HistData 1-minute BID bars 2007-2026 (backtest/histdata_1m.py, New York clock already fixed), 7 majors.
LEVELS  round = the big figure (every 100 pips; USD/JPY every 1.00 yen). CONTROL = the same events at arbitrary levels,
        the big figure + 23 / 37 / 63 / 77 pips (no 0 or 5 ending). The round-minus-control EXCESS is the order cluster;
        everything else (momentum, mean reversion, time of day) is in both and cancels.
EVENTS (decisions at a closed bar, never on the bar's own future)
  CASCADE  the close crosses a level (previous close on the other side). Enter at the NEXT bar's open in the crossing
           direction, exit at the close H minutes later. Declustered: one event per class per 60 bars per pair.
  FADE     the price reaches a level it has not traded at in the last 60 bars, from below (from above), trading
           THROUGH it by 0.5 pip (a resting limit's honest fill on bid bars). Enter AT the level, against the approach
           (a sell limit at the round number from below), exit at the close H minutes later. All touches count, the
           ones that broke through included (that is the limit order's adverse selection).
COST  1.2 pips a round trip (Exness-like spread + slippage, as fx_gotobi.py); also shown at 0.6. In bp of price.
SPLIT  60 / 40 by time per pair. t over pair-days (one vote a pair-day - events in a chop cluster are not independent).
GATE (registered before the first run) per cell = hypothesis x H (5 / 15 / 60 min), round levels, 7 pairs pooled:
  net mean > 0 with t >= 2 on BOTH halves, AND the excess over control > 0 with t >= 2 on BOTH halves, Holm over the
  6 cells. A pass would be a lead for the forward ledger, not money.

PREDICTIONS (registered 2026-11-15 before the first run)
  O1  CASCADE excess over control is positive pooled (the stop-cascade is real) but under 1 pip at every H.
  O2  FADE: the round-number touch reverses more than a control touch (excess > 0) by under 1 pip.
  O3  No cell passes the gate (net of 1.2 pips everything is negative). Prior that any passes: ~5%.
  O4  The excesses are smaller in the holdout (2018 on) than in the tune half (published 2003 / 2005, algos since).

    python -m backtest.fx_round_levels
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "strategy_analysis" / "data" / "histdata"
LOG = ROOT / "logs" / "fx_round_levels.txt"
PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF"]
HS = (5, 15, 60)
COST_PIPS = 1.2
GRID_PIPS = 100
CONTROL_OFFSETS = (23, 37, 63, 77)
LOOK = 60          # first-touch look-back and declustering window, bars
THROUGH = 0.5      # pips a limit needs the bid to trade through


def pip_of(pair):
    return 0.01 if pair.endswith("JPY") else 0.0001


def load(pair):
    d = pd.read_parquet(DATA / f"{pair}.parquet")
    d = d.sort_values("t", kind="stable").drop_duplicates("t", keep="last").reset_index(drop=True)
    return d


def level_index(x, off, grid):
    """Index of the level band x sits in: levels are off + grid * k."""
    return np.floor((x - off) / grid).astype(np.int64)


def contiguous(t, i, j, bars):
    """True where t[j] - t[i] is no more than bars + 10 minutes (no weekend / data gap inside the window)."""
    return (t[j] - t[i]) <= (bars + 10) * 60_000


def decluster(idx, gap=LOOK):
    keep, last = [], -10**12
    for k in idx:
        if k - last >= gap:
            keep.append(k)
            last = k
    return np.asarray(keep, dtype=np.int64)


def cascade_events(d, off, grid, H):
    """Close crosses a level; enter next open with the cross, exit close at +H. Returns (bar index, signed return)."""
    t, o, c = d.t.to_numpy(), d.o.to_numpy(), d.c.to_numpy()
    n = len(c)
    b = level_index(c, off, grid)
    cross = np.zeros(n, bool)
    cross[1:] = b[1:] != b[:-1]
    sgn = np.zeros(n)
    sgn[1:] = np.sign(b[1:] - b[:-1])
    ok = cross & (np.abs(np.diff(b, prepend=b[0])) == 1)      # one level crossed in one minute (not a data jump)
    idx = np.flatnonzero(ok)
    idx = idx[(idx >= 1) & (idx + H < n)]
    idx = idx[contiguous(t, idx - 1, idx, 1) & contiguous(t, idx, idx + H, H)]
    idx = decluster(idx)
    r = sgn[idx] * (c[idx + H] - o[idx + 1])
    return idx, r


def fade_events(d, off, grid, H, through):
    """First touch of a level in LOOK bars, traded through by `through`; enter AT the level against the approach."""
    idx, level, approach = touch_events(d, off, grid, H, through)
    r = -approach * (d.c.to_numpy()[idx + H] - level)
    return idx, r


def touch_events(d, off, grid, H, through):
    """First touches: (bar index, level, approach) with approach +1 = from below, -1 = from above."""
    t, h, l, c = d.t.to_numpy(), d.h.to_numpy(), d.l.to_numpy(), d.c.to_numpy()
    n = len(c)
    prev_c = np.r_[c[0], c[:-1]]
    up_lvl = off + grid * (level_index(prev_c, off, grid) + 1)          # nearest level above the previous close
    dn_lvl = off + grid * level_index(prev_c, off, grid)                # nearest level at / below it
    hmax = pd.Series(h).shift(1).rolling(LOOK, min_periods=LOOK).max().to_numpy()
    lmin = pd.Series(l).shift(1).rolling(LOOK, min_periods=LOOK).min().to_numpy()
    up = (h >= up_lvl + through) & (hmax < up_lvl)                       # from below: sell limit at up_lvl
    dn = (l <= dn_lvl - through) & (lmin > dn_lvl) & (prev_c > dn_lvl)   # from above: buy limit at dn_lvl
    both = up & dn                                                       # a one-minute range over two levels: skip
    up &= ~both
    dn &= ~both
    idx = np.flatnonzero(up | dn)
    idx = idx[(idx >= LOOK + 1) & (idx + H < n)]
    idx = idx[contiguous(t, idx - LOOK, idx, LOOK) & contiguous(t, idx, idx + H, H)]
    idx = decluster(idx)
    level = np.where(up[idx], up_lvl[idx], dn_lvl[idx])
    approach = np.where(up[idx], 1.0, -1.0)
    return idx, level, approach


def frame(pair, d, kind, off_pips, H):
    p = pip_of(pair)
    grid = GRID_PIPS * p
    off = off_pips * p
    if kind == "cascade":
        idx, r = cascade_events(d, off, grid, H)
    else:
        idx, r = fade_events(d, off, grid, H, THROUGH * p)
    t = d.t.to_numpy()[idx]
    price = d.c.to_numpy()[idx]
    return pd.DataFrame(dict(pair=pair, t=t, day=t // 86_400_000, bp=r / price * 1e4,
                             cost=COST_PIPS * p / price * 1e4, pips=r / p))


def day_t(x):
    """Mean and t over pair-day means."""
    g = x.groupby(["pair", "day"]).bp_net.mean()
    n = len(g)
    if n < 3:
        return np.nan, np.nan, n
    return g.mean(), g.mean() / (g.std(ddof=1) / math.sqrt(n)), n


def excess_t(a, b):
    ga = a.groupby(["pair", "day"]).bp.mean()
    gb = b.groupby(["pair", "day"]).bp.mean()
    if len(ga) < 3 or len(gb) < 3:
        return np.nan, np.nan
    diff = ga.mean() - gb.mean()
    se = math.sqrt(ga.var(ddof=1) / len(ga) + gb.var(ddof=1) / len(gb))
    return diff, diff / se


def p_one(t):
    return 0.5 * math.erfc(t / math.sqrt(2)) if np.isfinite(t) else 1.0


def holm(ps):
    order = np.argsort(ps)
    m = len(ps)
    adj = np.empty(m)
    run = 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (m - k) * ps[i]))
        adj[i] = run
    return adj


def run(pairs=PAIRS, loader=load):
    rows = {}
    split = {}
    for pair in pairs:
        d = loader(pair)
        ts = d.t.to_numpy()
        split[pair] = ts[int(len(ts) * 0.6)]
        for kind in ("cascade", "fade"):
            for H in HS:
                rows.setdefault((kind, H, "round"), []).append(frame(pair, d, kind, 0, H))
                for off in CONTROL_OFFSETS:
                    rows.setdefault((kind, H, "control"), []).append(frame(pair, d, kind, off, H))
    out = {}
    for key, parts in rows.items():
        x = pd.concat(parts, ignore_index=True)
        x["half"] = np.where(x.t < x.pair.map(split), "tune", "hold")
        x["bp_net"] = x.bp - x.cost
        out[key] = x
    return out


def judge(out):
    cells = []
    for kind in ("cascade", "fade"):
        for H in HS:
            r, c = out[(kind, H, "round")], out[(kind, H, "control")]
            cell = dict(kind=kind, H=H)
            for half in ("tune", "hold"):
                rr, cc = r[r.half == half], c[c.half == half]
                m, t, n = day_t(rr)
                ex, ext = excess_t(rr, cc)
                cell[half] = dict(n=len(rr), days=n, gross=rr.bp.mean(), gross_pips=rr.pips.mean(), net=m, t=t,
                                  ctl_gross=cc.bp.mean(), ctl_pips=cc.pips.mean(), excess=ex, ex_t=ext,
                                  net_half=(rr.bp - rr.cost / 2).mean())
            cell["p"] = max(p_one(cell["tune"]["t"]), p_one(cell["hold"]["t"]),
                            p_one(cell["tune"]["ex_t"]), p_one(cell["hold"]["ex_t"]))
            cells.append(cell)
    adj = holm(np.array([c["p"] for c in cells]))
    for c, a in zip(cells, adj):
        c["holm"] = a
        c["pass"] = bool(all(c[h]["net"] > 0 and c[h]["t"] >= 2 and c[h]["excess"] > 0 and c[h]["ex_t"] >= 2
                             for h in ("tune", "hold")) and a < 0.05)
    return cells


def report(cells, out):
    L = [f"backtest/fx_round_levels.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; HistData 1-minute bid bars, "
         f"{', '.join(PAIRS)}; round = big figure, control = +23/37/63/77 pips; cost {COST_PIPS} pips a round trip", "",
         "cell            half   events   gross pips | control pips | EXCESS bp (t)   | net bp (t, pair-days)   net@0.6pip",
         "-" * 118]
    for c in cells:
        for half in ("tune", "hold"):
            s = c[half]
            L.append(f"{c['kind']:<8} H={c['H']:>2}  {half:<5} {s['n']:>7}   {s['gross_pips']:+7.2f}   |   {s['ctl_pips']:+7.2f}    | "
                     f"{s['excess']:+6.2f} ({s['ex_t']:+5.1f})  | {s['net']:+7.2f} ({s['t']:+5.1f}, {s['days']:>5})   {s['net_half']:+6.2f}")
        L.append(f"{'':>16} Holm {c['holm']:.2f}  {'PASS' if c['pass'] else 'no pass'}")
    # per pair, primary horizons, both halves together
    L += ["", "BY PAIR (both halves; gross pips, round minus control):"]
    for kind, H in (("cascade", 15), ("fade", 15), ("cascade", 60), ("fade", 60)):
        r, c = out[(kind, H, "round")], out[(kind, H, "control")]
        parts = []
        for pair in PAIRS:
            rr, cc = r[r.pair == pair], c[c.pair == pair]
            parts.append(f"{pair} {rr.pips.mean() - cc.pips.mean():+.2f}")
        L.append(f"  {kind} H={H}: " + "  ".join(parts))
    # by era: excess per 3 calendar blocks
    L += ["", "BY ERA (excess bp over control, H=15):"]
    for kind in ("cascade", "fade"):
        r, c = out[(kind, 15, "round")], out[(kind, 15, "control")]
        bits = []
        for a, b in (("2007", "2012"), ("2013", "2018"), ("2019", "2027")):
            lo, hi = pd.Timestamp(a).value // 10**6, pd.Timestamp(b).value // 10**6
            rr, cc = r[(r.t >= lo) & (r.t < hi)], c[(c.t >= lo) & (c.t < hi)]
            ex, ext = excess_t(rr, cc)
            bits.append(f"{a}-{int(b) - 1}: {ex:+.2f} (t {ext:+.1f}, n {len(rr)})")
        L.append(f"  {kind}: " + "   ".join(bits))
    npass = sum(c["pass"] for c in cells)
    L += ["", f"VERDICT: {npass} of {len(cells)} cells pass." + (" A LEAD for the forward ledger - check it for bugs first." if npass
          else " Round-number order clusters are not a tradable edge at retail cost on these pairs.")]
    return "\n".join(L)


def main():
    out = run()
    cells = judge(out)
    txt = report(cells, out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    sys.exit(main())

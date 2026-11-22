"""THE "90% BUYERS FOR A MINUTE" ORDER-BOOK RULE, TESTED AS STATED, AND THE FEE ARITHMETIC BEHIND IT (2026-11-04)

THE USER (2026-11-04, Roman Urdu, translated): "In the order book, when 90 percent are buyers - do they keep waiting for a minute, does the wall
stay thick or not? If it does, the trade should open and close. And how can we reduce fees - by leveraging, or what? I want to know how we came to
the conclusion and how we did it."  book_hist.py tested the top-of-book imbalance at one-second to ten-second horizons, passive_markout.py the maker
side, order_flow_lab.py one day of wall anatomy. Nobody had run the sentence the user wrote: bid-side dominance of 90% (or 80%, 70%) that STAYS for
a minute, then trade. This does, on the same seven full Bitget DOGEUSDT days (Tardis, 2025-03 .. 2026-09) and the same rebuilt one-second book.

DEFINITIONS  (all from book_hist's cached grid_<day>.pkl; imbalance = (bid $ - ask $) / (bid $ + ask $), so a 90% bid share is +0.8)
    imb1 / imb5 / imb20   dollar imbalance of the best 1 / 5 / 20 levels per side
    band10 / band25       dollar imbalance of everything within 10 / 25 bp of the mid  (the "wall" proper: depth near the price)
    thr                   0.4 / 0.6 / 0.8  = a bid share of 70% / 80% / 90%
    side                  +1: imbalance >= thr (buyers dominate), trade LONG;  -1: imbalance <= -thr (sellers dominate), trade SHORT
    sustained W           the condition held at EVERY one-second sample of the last W seconds (W = 1, 10, 30, 60), evaluated at second i with
                          samples <= i only. The trigger is the first second the run reaches W.
    entry / exit          a taker order at the NEXT second (ask for a long, bid for a short), out h seconds later at the other side of the book
                          (h = 30 / 60 / 120 / 300); events at least h seconds apart so outcome windows never overlap.
    COSTS                 gross = side x mid move; taker = crossing the spread both ways (0 fee); net = taker - 2 x 6bp (Bitget standard);
                          maker-ideal = gross - 2 x 2bp (a queue-free maker both ways: an UPPER bound, book_hist shows the real fills are the signal's failures).
    CONTROL               the same trade at every second of the same day-hour (the lesson of candle_scan_check.py: signals cluster in time).
                          excess = gross - that baseline.
    PASS                  pooled net > 0 with t >= 2 (one-sided, Holm over every cell with >= 100 events), positive on >= 5 of the 7 days.
    PERSISTENCE           for each feature and threshold: the share of seconds the condition holds, the length of its runs, the share of runs
                          that last 10 / 30 / 60 s - the direct answer to "does the wall stay thick".

REGISTERED BEFORE THE FIRST RUN (2026-11-04; I had read only book_hist's cached grids' summary: imb1 >= 0.8 held in 32% / 20% of the seconds on two days,
imb5 >= 0.8 in 0.6% / 0.0%, imb20 / band10 / band25 never reached 0.8 on those two days - that is why the thresholds go down to 0.4 for the deep features)
    S1  "90% buyers" at the touch is a normal state, not a signal: imb1 >= 0.8 in >= 10% of the seconds on every day. imb20, band10 and band25 never
        reach 0.8 on any of the seven days, and imb5 reaches it in under 2% of seconds on every day.
    S2  The touch does not stay: fewer than 3% of imb1 >= 0.8 runs last 60 s, and the median run is <= 3 s.
    S3  No cell with >= 100 events has a pooled excess over the same-hour baseline beyond +-1.5 bp (the information, if any, is a fraction of a tick).
    S4  Every cell's taker net is negative; the best pooled cell is at or below -8 bp; PASS 0 cells.
    S5  Even the queue-free maker-both-legs upper bound (4 bp) passes 0 cells.
    S6  Waiting longer does not help: for imb1 and imb5 at thr 0.6, the pooled excess at W = 60 is within 1 bp of the excess at W = 1.

    python -m backtest.book_sustained        # all seven days; writes logs/book_sustained.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import book_hist as bh  # noqa: E402
from backtest.candle_scan import holm, p_one_sided  # noqa: E402
from backtest.doge_book import spaced  # noqa: E402

LOG = ROOT / "logs" / "book_sustained.txt"
FEATS = ("imb1", "imb5", "imb20", "band10", "band25")
THRS = (0.4, 0.6, 0.8)
WINS = (1, 10, 30, 60)
HORIZ = (30, 60, 120, 300)
MAX_GAP_MS = 1500                                  # a hole bigger than this in the one-second grid breaks a run and voids an outcome
TAKER_BP, MAKER_BP = bh.TAKER_BP, bh.MAKER_BP
MIN_EVENTS = 100
DAYS = bh.TUNE + bh.LATER
SHARE = {0.4: "70%", 0.6: "80%", 0.8: "90%"}


# ---------------------------------------------------------------- the one-second book
def load(day: str) -> pd.DataFrame:
    g = bh.grid_for(day)[0].copy()
    g["mid"] = (g.bid + g.ask) / 2
    g["spread"] = (g.ask / g.bid - 1) * 1e4
    return g.reset_index(drop=True)


# ---------------------------------------------------------------- persistence
def run_lengths(c, t, max_gap_ms: int = MAX_GAP_MS) -> np.ndarray:
    """For each sample: how many consecutive samples ending here satisfy c (0 where c is False). A gap in time breaks a run."""
    c = np.asarray(c, bool)
    t = np.asarray(t)
    gap = np.r_[False, np.diff(t) > max_gap_ms]
    grp = np.cumsum(~c | gap)
    return pd.Series(c.astype(int)).groupby(grp).cumsum().to_numpy()


def run_durations(c, t, max_gap_ms: int = MAX_GAP_MS) -> np.ndarray:
    """The full length (in samples) of every maximal run of c."""
    rl = run_lengths(c, t, max_gap_ms)
    end = np.r_[rl[1:] <= rl[:-1], True] & (rl > 0)        # the last sample of a run: the next count does not go up
    return rl[end]


def trigger_idx(c, t, win: int, max_gap_ms: int = MAX_GAP_MS) -> np.ndarray:
    """Indices where a run of c reaches exactly `win` samples: the first second the condition has held for `win` seconds. Uses samples <= i only."""
    return np.flatnonzero(run_lengths(c, t, max_gap_ms) == win)


# ---------------------------------------------------------------- outcomes
def moves(t, bid, ask, mid, e, h_ms: int):
    """Entry at sample e, exit h_ms later. Returns (valid, mid move bp, long taker bp, short taker bp). A long buys the ask and sells the bid later,
    a short sells the bid and buys the ask later; an exit sample more than MAX_GAP_MS after the target time voids the event."""
    e = np.asarray(e, int)
    n = len(t)
    x = np.searchsorted(t, t[e] + h_ms, "left")
    xx = np.minimum(x, n - 1)
    valid = (x < n) & (t[xx] - (t[e] + h_ms) <= MAX_GAP_MS)
    mv = (mid[xx] / mid[e] - 1) * 1e4
    tl = (bid[xx] / ask[e] - 1) * 1e4
    ts = (bid[e] / ask[xx] - 1) * 1e4
    return valid, mv, tl, ts


def hour_baseline(t, vals, valid) -> dict:
    """Mean of vals over the valid samples of each clock hour of the day."""
    hr = (np.asarray(t) // 3_600_000)
    s = pd.Series(np.asarray(vals)[valid]).groupby(hr[valid]).mean()
    return s.to_dict()


def day_cells(df: pd.DataFrame) -> dict:
    """Every (feature, thr, win, side, horizon) cell of one day -> dict of event arrays (gross, taker0, base)."""
    t = df.t.to_numpy()
    bid, ask, mid = df.bid.to_numpy(), df.ask.to_numpy(), df.mid.to_numpy()
    n = len(t)
    allidx = np.arange(0, n - 1)
    base = {}
    for h in HORIZ:
        v, mv, tl, ts = moves(t, bid, ask, mid, allidx + 1, h * 1000)
        for side in (1, -1):
            hb = hour_baseline(t[allidx + 1], side * mv, v)
            base[(side, h)] = (hb, float(np.nanmean(np.where(v, side * mv, np.nan))),
                               float(np.nanmean(np.where(v, tl if side > 0 else ts, np.nan))))
    out = {}
    for feat in FEATS:
        x = df[feat].to_numpy()
        for thr in THRS:
            for side in (1, -1):
                c = (x >= thr) if side > 0 else (x <= -thr)
                rl = run_lengths(c, t)
                for win in WINS:
                    trig = np.flatnonzero(rl == win)
                    trig = trig[trig + 1 < n]
                    if not len(trig):
                        continue
                    for h in HORIZ:
                        keep = spaced(t[trig], h * 1000)
                        i = trig[keep]
                        v, mv, tl, ts = moves(t, bid, ask, mid, i + 1, h * 1000)
                        if not v.any():
                            continue
                        i, mv, tl, ts = i[v], mv[v], tl[v], ts[v]
                        hb = base[(side, h)][0]
                        b = np.array([hb.get(hh, np.nan) for hh in (t[i + 1] // 3_600_000)])
                        out[(feat, thr, win, side, h)] = dict(gross=side * mv, taker0=tl if side > 0 else ts, base=b,
                                                              spread=df.spread.to_numpy()[i + 1])
    return out


def persistence_rows(dfs: dict) -> list:
    """Per feature / threshold / side: how often the condition holds and how long its runs last, pooled over the days."""
    rows = []
    for feat in FEATS:
        for thr in THRS:
            for side in (1, -1):
                dur, nsec, nhold, still = [], 0, 0, []
                for day, df in dfs.items():
                    t = df.t.to_numpy()
                    x = df[feat].to_numpy()
                    c = (x >= thr) if side > 0 else (x <= -thr)
                    dur.append(run_durations(c, t))
                    nsec += len(c)
                    nhold += int(c.sum())
                    if len(c) > 60:
                        cc = c[:-60]
                        if cc.any():
                            still.append(float(c[60:][cc].mean()))
                d = np.concatenate(dur) if dur else np.array([])
                rows.append(dict(feat=feat, thr=thr, side=side, share=nhold / max(nsec, 1), runs=len(d),
                                 med=float(np.median(d)) if len(d) else float("nan"),
                                 p10=float((d >= 10).mean()) if len(d) else float("nan"),
                                 p30=float((d >= 30).mean()) if len(d) else float("nan"),
                                 p60=float((d >= 60).mean()) if len(d) else float("nan"),
                                 longest=int(d.max()) if len(d) else 0,
                                 still60=float(np.mean(still)) if still else float("nan")))
    return rows


# ---------------------------------------------------------------- pooling and tests
def tstat(x) -> tuple:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) < 3:
        return float("nan"), float("nan"), len(x)
    se = x.std(ddof=1) / np.sqrt(len(x))
    return float(x.mean()), (float(x.mean() / se) if se > 0 else float("nan")), len(x)


def pool(per_day: dict) -> dict:
    """Pool the events of every day for every cell and compute the columns."""
    keys = {k for d in per_day.values() for k in d}
    rows = {}
    for k in keys:
        parts = [(day, d[k]) for day, d in per_day.items() if k in d]
        g = np.concatenate([p["gross"] for _, p in parts])
        t0 = np.concatenate([p["taker0"] for _, p in parts])
        b = np.concatenate([p["base"] for _, p in parts])
        if len(g) < 30:
            continue
        net = t0 - 2 * TAKER_BP
        mk = g - 2 * MAKER_BP
        ex = g - b
        gm, gt, n = tstat(g)
        nm, nt, _ = tstat(net)
        km, kt, _ = tstat(mk)
        em, et, _ = tstat(ex)
        dpos = sum(1 for _, p in parts if len(p["gross"]) >= 5 and np.mean(p["taker0"] - 2 * TAKER_BP) > 0)
        dmk = sum(1 for _, p in parts if len(p["gross"]) >= 5 and np.mean(p["gross"] - 2 * MAKER_BP) > 0)
        rows[k] = dict(n=n, days=len(parts), gross=gm, gross_t=gt, base=float(np.nanmean(b)), excess=em, excess_t=et,
                       taker0=float(np.mean(t0)), net=nm, net_t=nt, mk=km, mk_t=kt, dpos=dpos, dmk=dmk, spread=float(np.mean(np.concatenate([p["spread"] for _, p in parts]))))
    return rows


def passes(rows: dict) -> tuple:
    """(pass set on taker net, pass set on the ideal maker) - Holm over every cell with >= MIN_EVENTS events."""
    keys = [k for k, r in rows.items() if r["n"] >= MIN_EVENTS and np.isfinite(r["net_t"])]
    out = []
    for col, tcol, dcol in (("net", "net_t", "dpos"), ("mk", "mk_t", "dmk")):
        ps = [p_one_sided(rows[k][tcol]) for k in keys]
        adj = holm(ps) if ps else []
        ok = {k for k, a in zip(keys, adj) if a < 0.05 and rows[k][col] > 0 and rows[k][dcol] >= 5}
        out.append(ok)
    return out[0], out[1]


# ---------------------------------------------------------------- fees
FEE_SCENARIOS = [("Bitget standard: taker in, taker out (0.06% + 0.06%)", 12.0, True),
                 ("Bitget standard: maker in, taker out (0.02% + 0.06%)", 8.0, "in"),
                 ("Bitget standard: maker in, maker out (0.02% + 0.02%)", 4.0, False),
                 ("reported MEXC-style: taker in, taker out (0.02% + 0.02%)", 4.0, True),
                 ("reported MEXC-style: maker in, taker out (0% + 0.02%)", 2.0, "in"),
                 ("reported MEXC-style: maker in, maker out (0% + 0%)", 0.0, False)]
LEVERAGES = (1, 5, 10, 20, 50, 100)


def margin_cost_pct(fee_bp: float, leverage: float) -> float:
    """A round-trip fee of `fee_bp` of NOTIONAL, as a percent of the MARGIN: notional = margin x leverage."""
    return fee_bp * leverage / 100.0


def fmt_cell(r) -> str:
    return (f"n{r['n']:6d} d{r['days']} gross {r['gross']:+6.2f} (base {r['base']:+5.2f}, excess {r['excess']:+5.2f} t{r['excess_t']:+5.1f})  "
            f"taker0 {r['taker0']:+6.2f}  net {r['net']:+7.2f} t{r['net_t']:+6.1f} days+ {r['dpos']}  maker-ideal {r['mk']:+6.2f} t{r['mk_t']:+5.1f}")


def main():
    dfs = {d: load(d) for d in DAYS}
    per_day = {d: day_cells(df) for d, df in dfs.items()}
    rows = pool(per_day)
    pr = persistence_rows(dfs)
    pass_net, pass_mk = passes(rows)
    L = [f"backtest/book_sustained.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; Bitget DOGEUSDT perp, {len(DAYS)} full days "
         f"({DAYS[0]} .. {DAYS[-1]}), one-second rebuilt book; taker {TAKER_BP:g}bp a leg, maker {MAKER_BP:g}bp a leg", ""]
    L.append("0. THE DATA: how often is the book 'lopsided'? (share of seconds with the condition, long side = buyers dominate; median spread in bp)")
    L.append(f"   {'day':<12}{'spread':>7}" + "".join(f"{f + '>=.8':>11}" for f in FEATS))
    for d, df in dfs.items():
        L.append(f"   {d:<12}{df.spread.median():7.2f}" + "".join(f"{float((df[f] >= 0.8).mean()) * 100:10.2f}%" for f in FEATS))
    L += ["", "1. DOES IT STAY? runs of the condition (long side), all seven days pooled",
          f"   {'feature':<8}{'bid share':>10}{'%seconds':>10}{'runs':>9}{'median s':>10}{'>=10 s':>9}{'>=30 s':>9}{'>=60 s':>9}{'longest s':>11}{'still on 60 s later':>21}"]
    for r in pr:
        if r["side"] < 0:
            continue
        L.append(f"   {r['feat']:<8}{SHARE[r['thr']]:>10}{r['share'] * 100:9.2f}%{r['runs']:9d}{r['med']:10.0f}{r['p10'] * 100:8.1f}%{r['p30'] * 100:8.1f}%"
                 f"{r['p60'] * 100:8.1f}%{r['longest']:11d}{r['still60'] * 100 if np.isfinite(r['still60']) else float('nan'):20.1f}%")
    L += ["", "   the SELL side (ask share >= the same level) for comparison:"]
    for r in pr:
        if r["side"] > 0 or r["runs"] == 0:
            continue
        L.append(f"   {r['feat']:<8}{SHARE[r['thr']]:>10}{r['share'] * 100:9.2f}%{r['runs']:9d}{r['med']:10.0f}{r['p10'] * 100:8.1f}%{r['p30'] * 100:8.1f}%"
                 f"{r['p60'] * 100:8.1f}%{r['longest']:11d}")
    L += ["", "2. THE TRADE: the condition has held for 60 s, then buy (or sell) and get out h seconds later (pooled over the days; bp)"]
    for h in HORIZ:
        L.append(f"   --- hold {h} s")
        for side, nm in ((1, "LONG after buyers dominate"), (-1, "SHORT after sellers dominate")):
            for feat in FEATS:
                for thr in THRS:
                    r = rows.get((feat, thr, 60, side, h))
                    if r is None or r["n"] < 30:
                        continue
                    L.append(f"   {nm:<30}{feat:<7}{SHARE[thr]:>4} " + fmt_cell(r))
    L += ["", "3. DOES WAITING LONGER HELP? excess over the same-hour baseline by W (hold 60 s, long, 80% share)"]
    for feat in FEATS:
        cells = []
        for win in WINS:
            r = rows.get((feat, 0.6, win, 1, 60))
            cells.append(f"W{win}: " + (f"n{r['n']:6d} excess {r['excess']:+5.2f}" if r and r["n"] >= 30 else "     (n < 30)      "))
        L.append(f"   {feat:<7}" + "   ".join(cells))
    L += ["", "4. THE BEST CELLS (n >= 100): by taker net, by excess t, and by the queue-free maker upper bound"]
    ok = [(k, r) for k, r in rows.items() if r["n"] >= MIN_EVENTS]
    for title, key in (("taker net", "net"), ("excess t", "excess_t"), ("maker-ideal", "mk")):
        L.append(f"   by {title}:")
        for k, r in sorted(ok, key=lambda kr: -kr[1][key] if np.isfinite(kr[1][key]) else 1e9)[:5]:
            L.append(f"     {k[0]:<7}{SHARE[k[1]]} W{k[2]:>3} {'long ' if k[3] > 0 else 'short'} h{k[4]:>4}  " + fmt_cell(r))
    L += ["", f"   cells with >= {MIN_EVENTS} events: {len(ok)}   PASS on taker net: {len(pass_net)}   PASS on the queue-free maker bound: {len(pass_mk)}", "",
          "5. FEES: what the move must beat, and what leverage does",
          f"   median spread over the seven days: {np.median([df.spread.median() for df in dfs.values()]):.2f} bp (a taker pays about one spread across the round trip)",
          f"   {'scenario':<62}{'fee bp':>7}" + "".join(f"{'x' + str(lv) + ' margin':>11}" for lv in LEVERAGES)]
    for name, fee, _ in FEE_SCENARIOS:
        L.append(f"   {name:<62}{fee:7.1f}" + "".join(f"{margin_cost_pct(fee, lv):10.2f}%" for lv in LEVERAGES))
    best = max((r["gross"] for k, r in ok), default=float("nan"))
    bestx = max((r["excess"] for k, r in ok), default=float("nan"))
    L.append(f"   largest pooled GROSS move of any cell: {best:+.2f} bp; largest excess over the same-hour baseline: {bestx:+.2f} bp")
    # predictions
    p1_a = all(float((df.imb1 >= 0.8).mean()) >= 0.10 for df in dfs.values())
    p1_b = all(float((df[f] >= 0.8).mean()) == 0.0 for df in dfs.values() for f in ("imb20", "band10", "band25"))
    p1_c = all(float((df.imb5 >= 0.8).mean()) < 0.02 for df in dfs.values())
    r1 = [r for r in pr if r["feat"] == "imb1" and r["thr"] == 0.8 and r["side"] > 0][0]
    s2 = r1["p60"] < 0.03 and r1["med"] <= 3
    big = [(k, r) for k, r in rows.items() if r["n"] >= MIN_EVENTS]
    s3 = all(abs(r["excess"]) <= 1.5 for k, r in big)
    s4 = all(r["net"] < 0 for k, r in big) and max((r["net"] for k, r in big), default=-99) <= -8 and not pass_net
    s5 = not pass_mk
    d6 = []
    for feat in ("imb1", "imb5"):
        a, b = rows.get((feat, 0.6, 60, 1, 60)), rows.get((feat, 0.6, 1, 1, 60))
        if a and b and a["n"] >= 30 and b["n"] >= 30:
            d6.append(abs(a["excess"] - b["excess"]))
    s6 = bool(d6) and all(x <= 1.0 for x in d6)
    L += ["", "REGISTERED PREDICTIONS",
          f"  S1 touch lopsided >= 10% of seconds every day; deep book never 90%; imb5 < 2% -> {'RIGHT' if (p1_a and p1_b and p1_c) else 'WRONG'} "
          f"(imb1 {p1_a}, deep-never {p1_b}, imb5 {p1_c})",
          f"  S2 < 3% of imb1 90% runs last 60 s, median run <= 3 s -> {'RIGHT' if s2 else 'WRONG'} ({r1['p60'] * 100:.2f}%, median {r1['med']:.0f} s)",
          f"  S3 every cell's excess within +-1.5 bp -> {'RIGHT' if s3 else 'WRONG'} (largest |excess| {max((abs(r['excess']) for k, r in big), default=float('nan')):.2f})",
          f"  S4 every taker net negative, best <= -8 bp, PASS 0 -> {'RIGHT' if s4 else 'WRONG'} (best {max((r['net'] for k, r in big), default=float('nan')):+.2f}, PASS {len(pass_net)})",
          f"  S5 the queue-free maker bound passes 0 cells -> {'RIGHT' if s5 else 'WRONG'} ({len(pass_mk)})",
          f"  S6 W = 60 within 1 bp of W = 1 -> " + (f"{'RIGHT' if s6 else 'WRONG'} ({', '.join(f'{x:.2f}' for x in d6)})" if d6
                                                  else "UNTESTABLE: fewer than 30 events at W = 60 (the condition almost never lasts that long)")]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

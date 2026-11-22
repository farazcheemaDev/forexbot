"""CANDLE-PATTERN ENTRIES WITH REAL TRADE MANAGEMENT: CUT LOSERS, LET WINNERS RUN, RISK 1R A TRADE (2026-11-02)

backtest/candle_scan.py held every pattern trade for a fixed time with no stop. The user's objection: traders do not trade a
candle shape that way - the money comes from cutting losers fast, letting winners run and sizing sensibly, with the candle only
choosing WHERE to start. This file gives every pattern entry exactly that management and asks whether the SHAPE adds anything
to it, by running the very same management from random entries at the same moment.

ENTRIES    the 17 patterns of candle_scan.pattern_flags, both sides, on 1h / 4h / 1d bars of the point-in-time top-40 perps
           (same universe, same bars, same causality: known at the signal bar's close, ENTER at the next bar's open).
MANAGEMENT two fixed rules, every number set here and never tuned (ATR = the mean true range of the 14 bars up to the signal bar):
             trend  stop at 2 ATR (= 1R); at +3R the stop moves to the entry; a trailing stop 20 ATR behind the best price (the
                    deployed trend book's long rule); out at the close of bar 100 at the latest
             scalp  stop at 1 ATR (= 1R); target at +2R; out at the close of bar 24 at the latest (the usual 'risk 1 to make 2')
           Stops and the trail are checked inside each bar; a gap through the stop fills at the open; a bar that touches both the
           stop and the target counts as the stop; the breakeven move and the trail apply from the NEXT bar (the bar's own
           extreme is not known in advance). No pyramiding.
ENTRY FILTER  1R must be at least 0.2% of the entry price: below that the 12bp fee alone is over 0.6R and a tiny ATR (a stale, flat
           market) would turn the R arithmetic into noise. Applied to pattern entries and random entries alike.
SIZING     every trade risks exactly 1R (fixed-fraction risk): results are in R. Fees are charged in R: (12bp + 1bp / 8h of funding
           on longs) divided by the stop distance as a fraction of price - which is why a tight stop on a 1h bar is expensive.
CONTROL    the same management started from EVERY point-in-time coin-bar, same side, same bar size; the baseline for a trade is the
           mean net R of those random entries at its entry DAY x entry SLOT (the lesson of candle_scan.py). Excess = the trade's
           net R minus that baseline.
SPLIT      tune before 2024-08-29, holdout after; every entry day gets one vote in means and t; a half needs 100 trades on 30 days.
PASS       net R > 0 with t >= 2 AND excess > 0 with t >= 2 on BOTH halves, Holm < 0.05 over all sized cells (cell p = the larger
           one-sided p of the two halves' net t). 17 patterns x 2 sides x 3 bar sizes x 2 managements = 204 cells.
NOT TESTED pyramiding (adding units at +2R), a volatility or equity-dependent size, multi-bar targets, the patterns on forex / gold.

REGISTERED BEFORE THE FIRST RUN (2026-11-02; my prior that any cell passes: under 5%)
  R1  No cell passes.
  R2  The random-entry control is net negative on the holdout (mean net R < 0) for every combination of bar size, management and
      side except at most two: management alone is not a free lunch once the fees are charged.
  R3  At most 3 cells have excess t >= 2 on both halves: the candle shape adds nothing to the management.
  R4  Win rates: the scalp cells average 26-34% (arithmetic of a 1R stop against a 2R target is 33% before costs and drift); the
      trend cells average under 30%.
  R5  No 1h scalp cell has mean net R above 0 on both halves (a 1 ATR stop on 1h bars is about 0.4% of price, so 12bp is ~0.3R).

    python -m backtest.candle_manage
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import candle_scan as cs  # noqa: E402

LOG = ROOT / "logs" / "candle_manage.txt"
MGMT = {"trend": dict(stop=2.0, be=3.0, trail=20.0, target=None, cap=100),
        "scalp": dict(stop=1.0, be=None, trail=None, target=2.0, cap=24)}
ATR_N = 14
MIN_RISK = 0.002                         # 1R as a fraction of the entry price


def atr14(h, l, c):
    """Mean true range of the 14 bars up to and including bar i (NaN before there are 14)."""
    h, l, c = (np.asarray(x, float) for x in (h, l, c))
    pc = np.r_[np.nan, c[:-1]]
    tr = np.fmax(h - l, np.fmax(np.abs(h - pc), np.abs(l - pc)))
    tr[0] = h[0] - l[0]
    return pd.Series(tr).rolling(ATR_N).mean().to_numpy()


def simulate(o, h, l, c, atr, E, side, m):
    """Manage trades signalled on bars E (entry = open of E+1). Returns (r_gross, k_exit, risk_fraction):
    gross R of each trade, the number of bars it was held (the entry bar is bar 1) and 1R as a fraction of the entry price."""
    E = np.asarray(E, int)
    n = len(E)
    e = o[E + 1]
    a = atr[E]
    risk = m["stop"] * a
    stop = e - side * risk
    tgt = e + side * m["target"] * risk if m["target"] else None
    best = e.copy()
    exit_p = np.full(n, np.nan)
    k_exit = np.zeros(n, int)
    act = np.arange(n)
    pick_hi = np.maximum if side > 0 else np.minimum
    for k in range(1, m["cap"] + 1):
        if not len(act):
            break
        j = E[act] + k
        op, hi, lo, cl = o[j], h[j], l[j], c[j]
        st = stop[act]
        if side > 0:
            hit, px = lo <= st, np.minimum(st, op)
        else:
            hit, px = hi >= st, np.maximum(st, op)
        done = hit.copy()
        if tgt is not None:
            tg = tgt[act]
            if side > 0:
                ht, pt = (hi >= tg) & ~hit, np.maximum(tg, op)
            else:
                ht, pt = (lo <= tg) & ~hit, np.minimum(tg, op)
            px = np.where(ht, pt, px)
            done |= ht
        if k == m["cap"]:
            px = np.where(done, px, cl)
            done = np.ones(len(act), bool)
        exit_p[act[done]] = px[done]
        k_exit[act[done]] = k
        keep = ~done
        act, hi, lo = act[keep], hi[keep], lo[keep]
        if not len(act):
            break
        best[act] = np.maximum(best[act], hi) if side > 0 else np.minimum(best[act], lo)
        if m["be"]:
            reached = side * (best[act] - e[act]) >= m["be"] * risk[act]
            stop[act] = np.where(reached, pick_hi(stop[act], e[act]), stop[act])
        if m["trail"]:
            stop[act] = pick_hi(stop[act], best[act] - side * m["trail"] * a[act])
    return side * (exit_p - e) / risk, k_exit, risk / e


def cost_r(k_exit, risk_frac, side, tfh):
    """Fees and funding in R: (12bp + funding on longs) as a fraction of the 1R stop distance."""
    return (cs.FEE + (cs.FUND_H * k_exit * tfh if side > 0 else 0.0)) / risk_frac


def pick_trades(idx, exit_idx):
    """One position per coin: a signal is taken only if it comes on or after the bar where the last trade left."""
    out, last = [], -1
    ex = exit_idx
    for i in idx.tolist():
        if i >= last:
            out.append(i)
            last = ex[i]
    return np.array(out, int)


def half_stats(day, net, key, base, mask):
    """One half of one cell: mean net R, mean excess over the baseline at the trade's day x slot, each with the day-vote t."""
    day, net, key = day[mask], net[mask], key[mask]
    b = base[key]
    ok = np.isfinite(b) & np.isfinite(net)
    day, net, b = day[ok], net[ok], b[ok]
    if len(net) < 3:
        return None
    m, t, days = cs.day_mean_t(net, day)
    x, tx, _ = cs.day_mean_t(net - b, day)
    return dict(n=len(net), days=days, net=m, t=t, exc=x, t_exc=tx, win=float((net > 0).mean()))


def process(d, elig_months, tfh, cells, bsum, bcnt):
    n = len(d)
    if n < 160:
        return
    t = d["time"].to_numpy("datetime64[ns]")
    o, h, l, c = (d[k].to_numpy(float) for k in ("o", "h", "l", "c"))
    atr = atr14(h, l, c)
    fl = cs.pattern_flags(o, h, l, c)
    member = np.isin(t.astype("datetime64[M]"), elig_months)
    step = tfh * 3600 * 10 ** 9
    S = cs.n_slots(tfh)
    for mname, m in MGMT.items():
        valid = cs.valid_mask(t, step, m["cap"]) & member & (o > 0) & (c > 0) & np.isfinite(atr) & (atr > 0)
        E = np.flatnonzero(valid)
        if not len(E):
            continue
        valid[E[m["stop"] * atr[E] / o[E + 1] < MIN_RISK]] = False
        E = np.flatnonzero(valid)
        if not len(E):
            continue
        ent = t[E + 1]
        dy = cs.day_index(ent)
        ky = dy * S + cs.slot_of(ent, tfh)
        for side in (1, -1):
            rg, kx, rf = simulate(o, h, l, c, atr, E, side, m)
            net = rg - cost_r(kx, rf, side, tfh)
            ok = np.isfinite(net)
            bsum[(tfh, mname, side)] += np.bincount(ky[ok], weights=net[ok], minlength=cs.ND * S)
            bcnt[(tfh, mname, side)] += np.bincount(ky[ok], minlength=cs.ND * S)
            net_full = np.full(n, np.nan)
            net_full[E] = net
            exit_idx = np.zeros(n, int)
            exit_idx[E] = E + kx
            key_full = np.zeros(n, int)
            key_full[E] = ky
            day_full = np.zeros(n, int)
            day_full[E] = dy
            exit_list = exit_idx.tolist()
            for name, f in fl.items():
                idx = np.flatnonzero(f & valid & np.isfinite(net_full))
                if not len(idx):
                    continue
                pk = pick_trades(idx, exit_list)
                cells.setdefault((tfh, mname, side, name), []).append((day_full[pk], key_full[pk], net_full[pk]))


def run_universe():
    from backtest.capitulation_wide import hourly
    from backtest.market_neutral import drop_non_crypto
    from backtest.wide_book import eligibility
    elig = drop_non_crypto(eligibility(40))
    coins = sorted(s for s in elig if elig[s] and s.endswith("USDT"))
    cells = {}
    bsum = {(tfh, mn, sd): np.zeros(cs.ND * cs.n_slots(tfh)) for tfh in cs.TFS.values() for mn in MGMT for sd in (1, -1)}
    bcnt = {k: np.zeros_like(v) for k, v in bsum.items()}
    used = 0
    for sym in coins:
        h = hourly(sym)
        if h is None:
            continue
        em = np.array(sorted(elig[sym]), dtype="datetime64[M]")
        used += 1
        for tfh in cs.TFS.values():
            process(cs.to_tf(h, tfh), em, tfh, cells, bsum, bcnt)
    return coins, used, cells, bsum, bcnt


def evaluate(cells, bsum, bcnt):
    rows = []
    for (tfh, mname, side, name), parts in sorted(cells.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][3], -kv[0][2])):
        day = np.concatenate([p[0] for p in parts])
        key = np.concatenate([p[1] for p in parts])
        net = np.concatenate([p[2] for p in parts])
        with np.errstate(invalid="ignore", divide="ignore"):
            base = np.where(bcnt[(tfh, mname, side)] > 0, bsum[(tfh, mname, side)] / np.maximum(bcnt[(tfh, mname, side)], 1), np.nan)
        tu = half_stats(day, net, key, base, day < cs.CUT_DAY)
        ho = half_stats(day, net, key, base, day >= cs.CUT_DAY)
        rows.append(dict(tf=tfh, mg=mname, pat=name, side=side, text=cs.TEXTBOOK[name] == side, tu=tu, ho=ho))
    cand = [r for r in rows if cs.sized(r["tu"]) and cs.sized(r["ho"])]
    ps = [max(cs.p_one_sided(r["tu"]["t"]), cs.p_one_sided(r["ho"]["t"])) for r in cand]
    adj = cs.holm(ps) if ps else []
    for r in rows:
        r["holm"] = 1.0
    for r, a in zip(cand, adj):
        r["holm"] = float(a)
    for r in rows:
        r["pass"] = cs.passes(r["tu"], r["ho"], r["holm"])
        r["info"] = cs.information(r["tu"], r["ho"])
    return rows


def baseline_rows(bsum, bcnt):
    """Random-entry control per (bar size, management, side): mean net R and win share, tune / holdout, from the day-slot sums."""
    out = []
    for (tfh, mname, side), s in bsum.items():
        n = bcnt[(tfh, mname, side)]
        S = cs.n_slots(tfh)
        sd, nd = s.reshape(cs.ND, S).sum(1), n.reshape(cs.ND, S).sum(1)
        a, b = slice(0, cs.CUT_DAY), slice(cs.CUT_DAY, cs.ND)
        out.append((tfh, mname, side, sd[a].sum() / max(nd[a].sum(), 1), sd[b].sum() / max(nd[b].sum(), 1), int(nd.sum())))
    return sorted(out)


def fmt(s):
    if s is None:
        return "  -  "
    return f"n{s['n']:6d} R{s['net']:+6.3f} t{s['t']:+5.1f} exc{s['exc']:+6.3f} t{s['t_exc']:+5.1f} win{s['win'] * 100:3.0f}%"


def score(rows, base):
    cand = [r for r in rows if cs.sized(r["tu"]) and cs.sized(r["ho"])]
    passed = [r for r in rows if r["pass"]]
    r2_bad = [b for b in base if b[4] >= 0]
    inf = [r for r in rows if r["info"]]
    win = {mg: float(np.mean([(r["tu"]["win"] * r["tu"]["n"] + r["ho"]["win"] * r["ho"]["n"]) / (r["tu"]["n"] + r["ho"]["n"]) for r in cand if r["mg"] == mg]))
           for mg in MGMT if any(r["mg"] == mg for r in cand)}
    h1 = [r for r in cand if r["tf"] == 1 and r["mg"] == "scalp" and r["tu"]["net"] > 0 and r["ho"]["net"] > 0]
    return dict(cells=len(rows), sized=len(cand), passed=passed, r1=len(passed) == 0, r2_bad=r2_bad, r2=len(r2_bad) <= 2,
                inf=inf, r3=len(inf) <= 3, win=win,
                r4=(0.26 <= win.get("scalp", 0) <= 0.34) and win.get("trend", 1) < 0.30, h1=h1, r5=len(h1) == 0)


def main():
    coins, used, cells, bsum, bcnt = run_universe()
    rows = evaluate(cells, bsum, bcnt)
    base = baseline_rows(bsum, bcnt)
    sc = score(rows, base)
    L = [f"backtest/candle_manage.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {used} of {len(coins)} PIT-top-40 perps; tune < 2024-08-29; "
         f"1R risk a trade; 12bp + 1bp/8h on longs charged in R; control = same management from every PIT bar at the entry day x slot", ""]
    L.append("RANDOM-ENTRY CONTROL (mean net R a trade, tune / holdout)")
    for tfh, mn, sd, a, b, nn in base:
        L.append(f"  {cs.TFN[tfh]:>2} {mn:<6} {'long ' if sd > 0 else 'short'}  {a:+.3f} / {b:+.3f}   ({nn:,} entries)")
    L += ["", f"{'cell':<34}{'side':<8}{'TUNE':<58}{'HOLDOUT':<58}holm"]
    for r in rows:
        tag = "PASS" if r["pass"] else ("info" if r["info"] else "")
        L.append(f"{cs.TFN[r['tf']] + ' ' + r['mg'] + ' ' + r['pat']:<34}{('book' if r['text'] else 'mirror') + ('L' if r['side'] > 0 else 'S'):<8}"
                 f"{fmt(r['tu']):<58}{fmt(r['ho']):<58}{r['holm']:.2f} {tag}")
    L += ["", f"cells {sc['cells']} ({sc['sized']} sized)   PASS {len(sc['passed'])}   excess t>=2 on both halves: {len(sc['inf'])}",
          "average win rate: " + ", ".join(f"{k} {v * 100:.0f}%" for k, v in sc["win"].items())]
    best = sorted([r for r in rows if cs.sized(r["tu"]) and cs.sized(r["ho"])], key=lambda r: -min(r["tu"]["net"], r["ho"]["net"]))[:8]
    L += ["", "BEST CELLS by the worse half's net R per trade:"]
    for r in best:
        L.append(f"   {cs.TFN[r['tf']]} {r['mg']} {r['pat']} {'long' if r['side'] > 0 else 'short'} ({'textbook' if r['text'] else 'mirror'})  "
                 f"R {r['tu']['net']:+.3f} / {r['ho']['net']:+.3f}  t {r['tu']['t']:+.1f} / {r['ho']['t']:+.1f}  excess {r['tu']['exc']:+.3f} / {r['ho']['exc']:+.3f}  holm {r['holm']:.2f}")
    L += ["", "REGISTERED PREDICTIONS",
          f"  R1 no cell passes -> {'RIGHT' if sc['r1'] else 'WRONG'} ({len(sc['passed'])})",
          f"  R2 random-entry control net negative on the holdout in all but at most 2 of 12 combinations -> {'RIGHT' if sc['r2'] else 'WRONG'} ({len(sc['r2_bad'])} non-negative)",
          f"  R3 at most 3 cells with excess t>=2 on both halves -> {'RIGHT' if sc['r3'] else 'WRONG'} ({len(sc['inf'])})",
          f"  R4 scalp win rate 26-34%, trend under 30% -> {'RIGHT' if sc['r4'] else 'WRONG'} ({', '.join(f'{k} {v * 100:.0f}%' for k, v in sc['win'].items())})",
          f"  R5 no 1h scalp cell net R > 0 on both halves -> {'RIGHT' if sc['r5'] else 'WRONG'} ({len(sc['h1'])})"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

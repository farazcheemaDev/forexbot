"""RSI WITH A PROFIT TARGET AND A STOP LOSS: IS THERE A RATIO THAT PAYS? (2026-11-02)

THE USER (2026-11-02): "RSI was working but with a few big losses - there must be a ratio of taking profit and stop loss that is
profitable." The earlier RSI files each tried ONE or a few exits: rsi_only.py (no stop; one stop variant, +2% target / -4% stop,
which lost on every cell), rsi_factors.py (factor exits), rsi_confluence.py (+2% or four days). Nobody swept the ratio itself.
This does, with the control that decides it: the SAME bracket started from random entries at the same moment.

WHY A RATIO ALONE CANNOT PAY (arithmetic, not a result): with a stop of 1R and a target of T R, a trade with no edge wins a share
1/(1+T) of the time (a coin that moves randomly), so its average is -fees at EVERY ratio. The ratio only picks between winning
often for small amounts and rarely for big ones. A ratio pays only if the ENTRY wins more often than the geometry gives a random
entry - which is what the excess over the control measures.

ENTRIES    RSI(14) (Wilder) on 1h and 4h bars of the point-in-time top-40 perps (candle_scan's universe, dead coins in):
             lo30 / lo25 / lo20   RSI crosses DOWN through 30 / 25 / 20 at a bar's close  -> the textbook LONG
             hi70 / hi75 / hi80   RSI crosses UP through 70 / 75 / 80                      -> the textbook SHORT
             cap20                lo20 AND the bar's quote volume over 3x the mean of the 20 bars before it (rsi_confluence's
                                  candidate "capitulation buy", here with a stop and a target instead of its no-stop exit)
           Both sides are run for every flag; the non-textbook side is the momentum version ('mirror'). Enter at the next open.
BRACKETS   stop = 0.5 / 1 / 2 / 4 ATR(14) (that distance is 1R); target = 0.5 / 1 / 2 / 4 R; out at the close of bar 24 at the
           latest (a day on 1h bars, four days on 4h). 16 brackets, no breakeven move and no trail. Stops are checked inside each
           bar; a gap through the stop fills at the open; a bar touching both counts as the stop (candle_manage.simulate).
SIZING     every trade risks exactly 1R; fees are charged in R: (12bp + 1bp/8h of funding on longs) / the stop distance as a
           fraction of price - which is why a tight stop on a 1h bar is expensive (candle_manage.cost_r).
ENTRY FILTER  1R must be at least 0.2% of the entry price (candle_manage.MIN_RISK), applied to RSI entries and random entries alike.
CONTROL    the same bracket started from EVERY point-in-time coin-bar, same side and bar size; the baseline for a trade is the mean
           net R (and the win share) of those entries at its entry DAY x entry SLOT (the lesson of candle_scan_check.py).
SPLIT      tune before 2024-08-29, holdout after; every entry day gets one vote in means and t; a half needs 100 trades on 30 days.
PASS       net R > 0 with t >= 2 AND excess > 0 with t >= 2 on BOTH halves, Holm < 0.05 over all sized cells.
           7 flags x 2 sides x 2 bar sizes x 16 brackets = 448 cells.
NOT TESTED breakeven or trailing stops, a stop wider than 4 ATR (the no-stop trade of rsi_only.py), several units, 15m bars.

REGISTERED BEFORE THE FIRST RUN (2026-11-02; my prior that any cell passes: under 5%)
  Q1  No cell passes.
  Q2  Management alone is no free lunch: the random-entry control's mean net R on the holdout is negative in all but at most 10 of
      the 64 (bar size x side x bracket) combinations, and none is above +0.05R.
  Q3  The RSI shape adds nothing: averaged over the textbook cells, the excess over the control is within +-0.03R in EVERY bracket on
      both halves, and at most 3 cells have excess t >= 2 on both halves.
  Q4  The win rate is set by the geometry, not by the entry: textbook RSI cells win within 2 points of the control's win share (same
      bracket, same day x slot) on average.
  Q5  cap20 on 4h longs is the one exception: net R > 0 on both halves in at least 4 of its 16 brackets, no bracket passes Holm
      (too few trades), and its best bracket (by the worse half) has a target of 1R or less - small target, wide stop.

AMENDMENT (2026-11-02, after the first run, before any conclusion was drawn from it): the first log printed only the DAY-VOTE mean (each
entry day counts once - right for the t statistics, wrong as a measure of money). The best textbook bracket read +0.37R / +0.26R that way, and
a capped-account check on it (scratch script, not committed) came out at -0.15R / -0.12R a trade and -45%..-95% a year: a market-wide sell-off
carries 40-100 oversold signals in one day, they lose together, and one vote per day makes them count like one quiet day's single signal.
Every cell and bracket line now also prints 'pt' / PER-TRADE R, the trade-weighted mean net R (what an account that takes every signal earns).
Nothing registered above changes: Q1 - Q5 and the PASS bar still read the day-vote numbers and the excess; the money reading is added beside
them. The first run's log is kept as logs/rsi_ratio_dayvote_first_run.txt.

    python -m backtest.rsi_ratio
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import candle_manage as cm  # noqa: E402
from backtest import candle_scan as cs  # noqa: E402

LOG = ROOT / "logs" / "rsi_ratio.txt"
STOPS = (0.5, 1.0, 2.0, 4.0)
REWARDS = (0.5, 1.0, 2.0, 4.0)
BRACKETS = [(s, r) for s in STOPS for r in REWARDS]
CAP = 24
WARM = 60                                  # contiguous bars an RSI needs behind it before its flags are trusted
TFS = (1, 4)
LEVELS_LO = (30, 25, 20)
LEVELS_HI = (70, 75, 80)
VOL_N, VOL_X = 20, 3.0
TEXT = {"lo30": 1, "lo25": 1, "lo20": 1, "cap20": 1, "hi70": -1, "hi75": -1, "hi80": -1}


def rsi14(c):
    """Wilder RSI(14) of a close series (the recursion rsi_only.py uses)."""
    d = np.r_[0.0, np.diff(np.asarray(c, float))]
    up = pd.Series(np.where(d > 0, d, 0.0)).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    dn = pd.Series(np.where(d < 0, -d, 0.0)).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(dn > 0, 100 - 100 / (1 + up / dn), 100.0)


def rsi_flags(r, v):
    """Signal flags known at a bar's close: the RSI crossing a level on that bar, and the volume rule for cap20."""
    r = np.asarray(r, float)
    prev = np.r_[np.nan, r[:-1]]
    out = {}
    for lv in LEVELS_LO:
        out[f"lo{lv}"] = (prev >= lv) & (r < lv)
    for lv in LEVELS_HI:
        out[f"hi{lv}"] = (prev <= lv) & (r > lv)
    m = pd.Series(np.asarray(v, float)).shift(1).rolling(VOL_N).mean().to_numpy()
    with np.errstate(invalid="ignore"):
        out["cap20"] = out["lo20"] & (np.asarray(v, float) > VOL_X * m)
    return out


def warm_mask(t, step_ns, w):
    """True where the w bars before i exist and are contiguous in time with bar i."""
    n = len(t)
    brk = np.r_[False, np.diff(np.asarray(t, "datetime64[ns]").astype("int64")) != step_ns]
    seg = np.cumsum(brk)
    i = np.arange(n)
    j0 = np.clip(i - w, 0, n - 1)
    return (i >= w) & (seg[j0] == seg[i])


def to_tf(h, hours):
    """Bars of `hours` hours from the 1h frame (with quote volume); a bar is kept only when all its hours exist."""
    g = h.set_index("time").resample(f"{hours}h")
    out = pd.DataFrame({"o": g["open"].first(), "h": g["high"].max(), "l": g["low"].min(), "c": g["close"].last(),
                        "v": g["qvol"].sum(), "n": g["close"].count()})
    return out[out.n == hours].drop(columns="n").reset_index()


def breakeven(tgt, cost_r):
    """Win share at which a bracket (stop 1R, target tgt R, cost cost_r per trade) breaks even: p*tgt - (1-p) - cost = 0."""
    return (1.0 + cost_r) / (1.0 + tgt)


def new_acc():
    return {k: {(tfh, bi, sd): np.zeros(cs.ND * cs.n_slots(tfh)) for tfh in TFS for bi in range(len(BRACKETS)) for sd in (1, -1)}
            for k in ("sum", "cnt", "win", "cost")}


def process(d, elig_months, tfh, cells, acc):
    """Add one coin's RSI trades (every flag, both sides, every bracket) and its random-entry control to the accumulators."""
    n = len(d)
    if n < 200:
        return
    t = d["time"].to_numpy("datetime64[ns]")
    o, h, l, c = (d[k].to_numpy(float) for k in ("o", "h", "l", "c"))
    v = d["v"].to_numpy(float)
    atr = cm.atr14(h, l, c)
    fl = rsi_flags(rsi14(c), v)
    member = np.isin(t.astype("datetime64[M]"), elig_months)
    step = tfh * 3600 * 10 ** 9
    S = cs.n_slots(tfh)
    base_ok = (cs.valid_mask(t, step, CAP) & warm_mask(t, step, WARM) & member & (o > 0) & (c > 0)
               & np.isfinite(atr) & (atr > 0))
    for bi, (stp, tgt) in enumerate(BRACKETS):
        m = dict(stop=stp, be=None, trail=None, target=tgt, cap=CAP)
        valid = base_ok.copy()
        E = np.flatnonzero(valid)
        if not len(E):
            continue
        valid[E[stp * atr[E] / o[E + 1] < cm.MIN_RISK]] = False
        E = np.flatnonzero(valid)
        if not len(E):
            continue
        ent = t[E + 1]
        dy = cs.day_index(ent)
        ky = dy * S + cs.slot_of(ent, tfh)
        for side in (1, -1):
            rg, kx, rf = cm.simulate(o, h, l, c, atr, E, side, m)
            cost = cm.cost_r(kx, rf, side, tfh)
            net = rg - cost
            ok = np.isfinite(net)
            kk = (tfh, bi, side)
            acc["sum"][kk] += np.bincount(ky[ok], weights=net[ok], minlength=cs.ND * S)
            acc["cnt"][kk] += np.bincount(ky[ok], minlength=cs.ND * S)
            acc["win"][kk] += np.bincount(ky[ok & (net > 0)], minlength=cs.ND * S)
            acc["cost"][kk] += np.bincount(ky[ok], weights=cost[ok], minlength=cs.ND * S)
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
                pk = cm.pick_trades(idx, exit_list)
                cells.setdefault((tfh, bi, side, name), []).append((day_full[pk], key_full[pk], net_full[pk]))


def run_universe():
    from backtest.capitulation_wide import hourly
    from backtest.market_neutral import drop_non_crypto
    from backtest.wide_book import eligibility
    elig = drop_non_crypto(eligibility(40))
    coins = sorted(s for s in elig if elig[s] and s.endswith("USDT"))
    cells, acc, used = {}, new_acc(), 0
    for sym in coins:
        hh = hourly(sym)
        if hh is None:
            continue
        em = np.array(sorted(elig[sym]), dtype="datetime64[M]")
        used += 1
        for tfh in TFS:
            process(to_tf(hh, tfh), em, tfh, cells, acc)
    return coins, used, cells, acc


def half(day, net, key, base, bwr, mask):
    """cm.half_stats plus 'bw': the control's mean win share at the same trades' day x slot keys."""
    s = cm.half_stats(day, net, key, base, mask)
    if s is None:
        return None
    k, x = key[mask], net[mask]
    ok = np.isfinite(base[k]) & np.isfinite(x)
    s["bw"] = float(np.mean(bwr[k][ok]))
    s["pt"] = float(np.mean(x[ok]))                                    # trade-weighted mean net R: what an account taking every signal earns
    return s


def evaluate(cells, acc):
    rows, cache = [], {}
    for (tfh, bi, side, name), parts in sorted(cells.items(), key=lambda kv: (kv[0][0], kv[0][3], kv[0][2] * -1, kv[0][1])):
        kk = (tfh, bi, side)
        if kk not in cache:
            cnt, sm, wn = acc["cnt"][kk], acc["sum"][kk], acc["win"][kk]
            with np.errstate(invalid="ignore", divide="ignore"):
                cache[kk] = (np.where(cnt > 0, sm / np.maximum(cnt, 1), np.nan), np.where(cnt > 0, wn / np.maximum(cnt, 1), np.nan))
        base, bwr = cache[kk]
        day = np.concatenate([p[0] for p in parts])
        key = np.concatenate([p[1] for p in parts])
        net = np.concatenate([p[2] for p in parts])
        rows.append(dict(tf=tfh, bi=bi, stop=BRACKETS[bi][0], tgt=BRACKETS[bi][1], flag=name, side=side, text=TEXT[name] == side,
                         tu=half(day, net, key, base, bwr, day < cs.CUT_DAY), ho=half(day, net, key, base, bwr, day >= cs.CUT_DAY)))
    cand = [r for r in rows if cs.sized(r["tu"]) and cs.sized(r["ho"])]
    adj = cs.holm([max(cs.p_one_sided(r["tu"]["t"]), cs.p_one_sided(r["ho"]["t"])) for r in cand]) if cand else []
    for r in rows:
        r["holm"] = 1.0
    for r, a in zip(cand, adj):
        r["holm"] = float(a)
    for r in rows:
        r["pass"] = cs.passes(r["tu"], r["ho"], r["holm"])
        r["info"] = cs.information(r["tu"], r["ho"])
    return rows


def control_rows(acc):
    """Random-entry control per (bar size, bracket, side): mean net R tune / holdout, win share, mean cost in R, entries."""
    out = {}
    for kk, s in acc["sum"].items():
        S = cs.n_slots(kk[0])
        n, w, cst = acc["cnt"][kk], acc["win"][kk], acc["cost"][kk]
        sd, nd = s.reshape(cs.ND, S).sum(1), n.reshape(cs.ND, S).sum(1)
        a, b = slice(0, cs.CUT_DAY), slice(cs.CUT_DAY, cs.ND)
        tot = max(n.sum(), 1)
        out[kk] = dict(tu=sd[a].sum() / max(nd[a].sum(), 1), ho=sd[b].sum() / max(nd[b].sum(), 1), win=w.sum() / tot, cost=cst.sum() / tot,
                       n=int(n.sum()))
    return out


def bracket_summary(rows, ctrl):
    """Per (bracket, side): the textbook RSI cells (cap20 excluded) averaged - how many are positive on both halves, net R,
    excess over the control, win share against the control's and against the break-even share."""
    out = {}
    for bi, (stp, tgt) in enumerate(BRACKETS):
        for side in (1, -1):
            rs = [r for r in rows if r["bi"] == bi and r["side"] == side and r["text"] and r["flag"] != "cap20"
                  and cs.sized(r["tu"]) and cs.sized(r["ho"])]
            if not rs:
                continue
            cost = float(np.mean([ctrl[(r["tf"], bi, side)]["cost"] for r in rs]))
            out[(bi, side)] = dict(
                cells=len(rs), both=sum(1 for r in rs if r["tu"]["net"] > 0 and r["ho"]["net"] > 0),
                tu=float(np.mean([r["tu"]["net"] for r in rs])), ho=float(np.mean([r["ho"]["net"] for r in rs])),
                ptu=float(np.mean([r["tu"]["pt"] for r in rs])), pho=float(np.mean([r["ho"]["pt"] for r in rs])),
                xtu=float(np.mean([r["tu"]["exc"] for r in rs])), xho=float(np.mean([r["ho"]["exc"] for r in rs])),
                win=float(np.mean([s["win"] for r in rs for s in (r["tu"], r["ho"])])),
                bw=float(np.mean([s["bw"] for r in rs for s in (r["tu"], r["ho"])])), need=breakeven(tgt, cost))
    return out


def fmt(s):
    if s is None:
        return "  -  "
    return f"n{s['n']:6d} R{s['net']:+6.3f} t{s['t']:+5.1f} exc{s['exc']:+6.3f} t{s['t_exc']:+5.1f} win{s['win'] * 100:3.0f}% pt{s['pt']:+6.3f}"


def score(rows, ctrl, bs):
    cand = [r for r in rows if cs.sized(r["tu"]) and cs.sized(r["ho"])]
    passed = [r for r in rows if r["pass"]]
    nonneg = [k for k, v in ctrl.items() if v["ho"] >= 0]
    top = max(v["ho"] for v in ctrl.values())
    textbook = [r for r in cand if r["text"] and r["flag"] != "cap20"]
    info = [r for r in rows if r["info"]]
    xmax = max([abs(v[k]) for v in bs.values() for k in ("xtu", "xho")] or [0.0])
    gaps = [abs(s["win"] - s["bw"]) for r in textbook for s in (r["tu"], r["ho"])]
    gap = float(np.mean(gaps)) if gaps else float("nan")
    cap = [r for r in cand if r["flag"] == "cap20" and r["side"] == 1 and r["tf"] == 4]
    cap_pos = [r for r in cap if r["tu"]["net"] > 0 and r["ho"]["net"] > 0]
    cap_best = max(cap, key=lambda r: min(r["tu"]["net"], r["ho"]["net"])) if cap else None
    return dict(cells=len(rows), sized=len(cand), passed=passed, q1=len(passed) == 0,
                nonneg=nonneg, top=top, q2=len(nonneg) <= 10 and top <= 0.05,
                info=info, xmax=xmax, q3=xmax < 0.03 and len(info) <= 3,
                gap=gap, q4=bool(gap < 0.02),
                cap=cap, cap_pos=cap_pos, cap_best=cap_best,
                q5=bool(len(cap_pos) >= 4 and not any(r["pass"] for r in cap) and cap_best is not None and cap_best["tgt"] <= 1.0))


def main():
    coins, used, cells, acc = run_universe()
    rows = evaluate(cells, acc)
    ctrl = control_rows(acc)
    bs = bracket_summary(rows, ctrl)
    sc = score(rows, ctrl, bs)
    L = [f"backtest/rsi_ratio.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {used} of {len(coins)} PIT-top-40 perps; tune < 2024-08-29; "
         f"stop = 1R = a multiple of ATR(14), target in R, out at bar {CAP}; 12bp + 1bp/8h on longs charged in R; control = same bracket from "
         f"every PIT bar at the entry day x slot", ""]
    for tfh in TFS:
        for side in (1, -1):
            L.append(f"RANDOM-ENTRY CONTROL {cs.TFN[tfh]} {'long ' if side > 0 else 'short'}: mean net R a trade (trade-weighted), tune / holdout   "
                     f"[win share, break-even share]    ({ctrl[(tfh, 0, side)]['n']:,} entries at the first bracket)")
            L.append(f"   {'stop \\ target':<14}" + "".join(f"{str(r) + 'R':<34}" for r in REWARDS))
            for stp in STOPS:
                cellsrow = []
                for tgt in REWARDS:
                    bi = BRACKETS.index((stp, tgt))
                    c = ctrl[(tfh, bi, side)]
                    cellsrow.append(f"{c['tu']:+.2f}/{c['ho']:+.2f} [{c['win'] * 100:2.0f}% {breakeven(tgt, c['cost']) * 100:2.0f}%]".ljust(34))
                L.append(f"   {str(stp) + ' ATR':<14}" + "".join(cellsrow))
            L.append("")
    L.append("TEXTBOOK RSI vs THE CONTROL, by bracket (the 3 oversold-long flags x 2 bar sizes = up to 6 cells; the 3 overbought-short flags the same)")
    L.append(f"   {'bracket':<16}{'side':<7}{'cells':<7}{'both+':<7}{'day-vote R t/h':<18}{'PER-TRADE R t/h':<18}{'excess t/h':<17}{'win':<6}{'control':<9}{'needed'}")
    for (bi, side), v in sorted(bs.items(), key=lambda kv: (kv[0][1] * -1, kv[0][0])):
        stp, tgt = BRACKETS[bi]
        L.append(f"   {str(stp) + 'ATR/' + str(tgt) + 'R':<16}{'long' if side > 0 else 'short':<7}{v['cells']:<7}{v['both']:<7}"
                 f"{v['tu']:+.3f}/{v['ho']:+.3f}   {v['ptu']:+.3f}/{v['pho']:+.3f}   {v['xtu']:+.3f}/{v['xho']:+.3f}   {v['win'] * 100:3.0f}%  {v['bw'] * 100:3.0f}%     {v['need'] * 100:3.0f}%")
    L.append("")
    L.append("BY REWARD:RISK RATIO (pooled over the four stops; mean of the bracket means above)")
    for tgt in REWARDS:
        for side in (1, -1):
            vs = [bs[(BRACKETS.index((s, tgt)), side)] for s in STOPS if (BRACKETS.index((s, tgt)), side) in bs]
            if vs:
                L.append(f"   1 : {tgt:<4}{'long' if side > 0 else 'short':<7} day-vote R {np.mean([v['tu'] for v in vs]):+.3f} / {np.mean([v['ho'] for v in vs]):+.3f}   "
                         f"PER-TRADE R {np.mean([v['ptu'] for v in vs]):+.3f} / {np.mean([v['pho'] for v in vs]):+.3f}   "
                         f"excess {np.mean([v['xtu'] for v in vs]):+.3f} / {np.mean([v['xho'] for v in vs]):+.3f}   win {np.mean([v['win'] for v in vs]) * 100:.0f}% "
                         f"vs control {np.mean([v['bw'] for v in vs]) * 100:.0f}% (break-even {np.mean([v['need'] for v in vs]) * 100:.0f}%)")
    L += ["", f"{'cell':<26}{'side':<8}{'TUNE':<58}{'HOLDOUT':<58}holm"]
    for r in rows:
        tag = "PASS" if r["pass"] else ("info" if r["info"] else "")
        L.append(f"{cs.TFN[r['tf']] + ' ' + r['flag'] + ' ' + str(r['stop']) + 'ATR/' + str(r['tgt']) + 'R':<26}"
                 f"{('book' if r['text'] else 'mirror') + ('L' if r['side'] > 0 else 'S'):<8}{fmt(r['tu']):<58}{fmt(r['ho']):<58}{r['holm']:.2f} {tag}")
    L += ["", f"cells {sc['cells']} ({sc['sized']} sized)   PASS {len(sc['passed'])}   excess t>=2 on both halves: {len(sc['info'])}"]
    best = sorted([r for r in rows if cs.sized(r["tu"]) and cs.sized(r["ho"])], key=lambda r: -min(r["tu"]["net"], r["ho"]["net"]))[:10]
    L += ["", "BEST CELLS by the worse half's net R per trade:"]
    for r in best:
        L.append(f"   {cs.TFN[r['tf']]} {r['flag']} {r['stop']}ATR/{r['tgt']}R {'long' if r['side'] > 0 else 'short'} ({'textbook' if r['text'] else 'mirror'})  "
                 f"R {r['tu']['net']:+.3f} / {r['ho']['net']:+.3f}  t {r['tu']['t']:+.1f} / {r['ho']['t']:+.1f}  excess {r['tu']['exc']:+.3f} / {r['ho']['exc']:+.3f}  "
                 f"n {r['tu']['n']}/{r['ho']['n']}  win {r['tu']['win'] * 100:.0f}%/{r['ho']['win'] * 100:.0f}%  holm {r['holm']:.2f}")
    L += ["", "cap20 (RSI under 20 + volume spike) 4h LONG, all sized brackets:"]
    for r in sorted(sc["cap"], key=lambda r: -min(r["tu"]["net"], r["ho"]["net"])):
        L.append(f"   {r['stop']}ATR/{r['tgt']}R  TUNE {fmt(r['tu'])}  HOLDOUT {fmt(r['ho'])}  holm {r['holm']:.2f}")
    if not sc["cap"]:
        L.append("   (no bracket has 100 trades on 30 days in both halves)")
    cb = sc["cap_best"]
    L += ["", "REGISTERED PREDICTIONS",
          f"  Q1 no cell passes -> {'RIGHT' if sc['q1'] else 'WRONG'} ({len(sc['passed'])})",
          f"  Q2 control negative on the holdout in all but <= 10 of 64, none above +0.05R -> {'RIGHT' if sc['q2'] else 'WRONG'} "
          f"({len(sc['nonneg'])} non-negative, highest {sc['top']:+.3f})",
          f"  Q3 textbook excess within +-0.03R in every bracket, <= 3 cells with excess t>=2 on both halves -> {'RIGHT' if sc['q3'] else 'WRONG'} "
          f"(largest bracket excess {sc['xmax']:.3f}, {len(sc['info'])} cells)",
          f"  Q4 textbook win share within 2 points of the control's -> {'RIGHT' if sc['q4'] else 'WRONG'} (mean gap {sc['gap'] * 100:.1f} points)",
          f"  Q5 cap20 4h long: >= 4 brackets positive on both halves, none passes, best has target <= 1R -> {'RIGHT' if sc['q5'] else 'WRONG'} "
          f"({len(sc['cap_pos'])} positive of {len(sc['cap'])} sized; best "
          + (f"{cb['stop']}ATR/{cb['tgt']}R" if cb else "n/a") + ")"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

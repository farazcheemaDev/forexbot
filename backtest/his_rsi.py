"""COULD IT BE RSI? Every common RSI setting at his moments, and as a NASDAQ signal in its own right (2026-11-02)

The user, 2026-11-02, after being told his side is not found in 72 sections of tests: "could it be RSI?" - and, earlier, "there must be a correlation somewhere".
What was already measured (his_ta.py, his_strategy.md s30): RSI(14) on 1-minute and 5-minute candles at his 25 clean entries ranks 0.46 / 0.44 against nearby moments (p 0.50 / 0.33):
ordinary. That is ONE setting. A scalper can use any RSI period on any candle length, as a level, as a slope, or as a hook out of an extreme. This file tests the grid.

THE GRID (51 cells, all sign-aligned to his direction s so that a high value always means "momentum in his direction" and a low one "against it / pullback"):
    candle length x RSI periods   15 s: 2 3 5 7 9 14 | 1 min: 2 3 5 7 9 14 | 5 min: 2 3 5 7 9       (17 setups; Wilder smoothing; only CLOSED candles)
    form                          lvl  = the RSI of the last closed candle
                                  chg  = that minus the RSI three candles earlier
                                  hook = (flag) the RSI crossed UP through 30 (sign-aligned) within the last 3 closed candles
STAGE A (does he stand out?): his 25 clean entries (April on, NASDAQ) vs ~80 moments of the same day within 20 minutes, same direction (his_ta.py's design); continuous cells by rank
          (0.50 = ordinary), flags by his rate vs the nearby rate (Poisson-binomial); Holm over 51. Power: with n = 25 the standard error of a mean rank is 0.058, so only a rank
          beyond about 0.69 / 0.31 survives Holm - if RSI were what he uses, it would show that big.
STAGE B (is it a signal at all?): every tick day, 40 random seconds x both directions; the 3-minute +7/-7 race on the NET side (entry at the quote, exit at the quote; 50% = break-even,
          the base is ~36%). For each cell the extreme third (or flag on/off) is CHOSEN ON THE FIRST HALF of the days and READ ON THE SECOND; one-sided binomial test against 50%, Holm over 51.

REGISTERED BEFORE THE FIRST RUN (2026-11-02)
    P1  Stage A: no cell survives Holm over 51. The smallest raw p is between 0.003 and 0.10 (the best of 51 correlated null cells). The 1-minute RSI(14) level reproduces his_ta's rank (0.46) within 0.05.
    P2  Stage A: if any cell leads, it is a pullback-side cell (rank below 0.5: he enters after RSI has cooled), not a momentum cell - his entries are calm pullbacks (his_strategy s64).
    P3  Stage B: no cell's chosen extreme reaches 50% net on the second half with Holm p < 0.05; the best second-half net race stays below 45%.
    P4  Stage B: of the 51 cells, 20 to 31 have the same sign of (high - low) mid race in both halves (a coin's worth), i.e. no RSI setting is consistently directional on these days.

RESULT (2026-11-02; logs/his_rsi.txt)
    Stage A: 0 of 51 cells reach raw p < 0.05 (chance alone gives ~2.6), 0 survive Holm. Smallest raw p 0.111 (the 15-second RSI(2) hook: 6 of his 25 entries vs 39% nearby); the best
    continuous cells are 5-minute levels at rank 0.44-0.45 (p 0.31-0.35), all on the pullback side but nowhere near the 0.69 needed after Holm. 21 of 34 continuous cells sit below 0.5.
    The 1-minute RSI(14) reproduces his_ta.py (rank 0.46, p 0.50). Stage B (181 tick days, 11,982 moment x direction pairs): the best extreme chosen on the first half reads 37.5% net on
    the second (base 35.8%, break-even 50%), 0 cells with Holm < 0.05, and 28 of 51 cells keep the sign of (high - low) mid race across both halves (a coin gives ~26).
    Scored: P1 half wrong (right on Holm and on the reproduction; the smallest raw p, 0.111, is above my 0.003-0.10 range - less lucky than chance), P2 right, P3 right, P4 right.
    Limits: n = 25 entries, so only a rank beyond ~0.69 survives Holm - RSI is not his dominant rule-like trigger, and a mild preference cannot be ruled out. RSI as a 3-minute NASDAQ signal
    is dead at the spread on these 181 days. (RSI does work in ONE place in this repo: the DAILY NASDAQ RSI(2) dip-buy, already one of the machine's books.)

    python -m backtest.his_rsi        writes logs/his_rsi.txt          tests: python tests/test_his_rsi.py
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_local import race  # noqa: E402
from backtest.his_predictors import race_net  # noqa: E402
from backtest.his_ta import GMT, ROOT, TICKS, candles, pz, wilder  # noqa: E402

TFS = {"15s": (15, 60, (2, 3, 5, 7, 9, 14)),        # candle seconds, warm-up closed candles (15 minutes), RSI periods
       "1m": (60, 30, (2, 3, 5, 7, 9, 14)),
       "5m": (300, 12, (2, 3, 5, 7, 9))}
LOOK = 3                                            # candles for the slope and for the hook window
LEVEL = 30.0                                        # the hook crosses UP through this (sign-aligned) RSI
FORMS = ("lvl", "chg")
CELLS_CONT = [f"{tf}_rsi{n}_{f}" for tf, (_, _, ps) in TFS.items() for n in ps for f in FORMS]
CELLS_FLAG = [f"{tf}_rsi{n}_hook" for tf, (_, _, ps) in TFS.items() for n in ps]
CELLS = CELLS_CONT + CELLS_FLAG


def rsi_series(c, n):
    """Wilder RSI of a close series. No losses at all: 100 if there were gains, 50 if the series never moved."""
    d = np.diff(c, prepend=c[0])
    up, dn = wilder(np.maximum(d, 0.0), n), wilder(np.maximum(-d, 0.0), n)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        r = 100.0 - 100.0 / (1.0 + up / np.where(dn > 0, dn, np.nan))
    return np.where(dn > 0, r, np.where(up > 0, 100.0, 50.0))


def make_day(ts, mid):
    """(ts, mid, {candle name: {period: RSI array}}) for one tick day; ts in seconds since 09:30 New York."""
    out = {}
    for name, (w, _, periods) in TFS.items():
        c = candles(ts, mid, w)["c"]
        out[name] = {n: rsi_series(c, n) for n in periods}
    return ts, mid, out


def feats(day, t, s):
    """The 51 cells at second t of the day for a trade in direction s (+1 buy, -1 sell), or None before the warm-up. Only candles closed BEFORE t are read."""
    out = {}
    for name, (w, warm, periods) in TFS.items():
        k = int(t // w) - 1
        if k < warm:
            return None
        for n in periods:
            r = day[2][name][n]
            if k >= len(r):
                return None
            o = r if s == 1 else 100.0 - r
            out[f"{name}_rsi{n}_lvl"] = float(o[k])
            out[f"{name}_rsi{n}_chg"] = float(o[k] - o[k - LOOK])
            out[f"{name}_rsi{n}_hook"] = bool(any(o[j - 1] < LEVEL <= o[j] for j in range(k - LOOK + 1, k + 1)))
    return out


def holm(p):
    """Holm-adjusted p-values (monotone) for a dict of raw p-values."""
    order = sorted(p, key=p.get)
    adj, run = {}, 0.0
    for i, key in enumerate(order):
        run = max(run, min(1.0, p[key] * (len(order) - i)))
        adj[key] = run
    return adj


def stage_a(cache, days_obj, x, rng):
    ranks, flag_obs, flag_ps, kept = [], {k: 0 for k in CELLS_FLAG}, {k: [] for k in CELLS_FLAG}, 0
    for r in x.itertuples():
        et = pd.Timestamp(r.utc).tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)
        d = et.normalize()
        if d not in cache or cache[d] is None:
            continue
        D = days_obj(d)
        t0 = (et - (d + pd.Timedelta(hours=9, minutes=30))).total_seconds()
        s = 1 if r.side == "BUY" else -1
        mine = feats(D, t0, s)
        if mine is None:
            continue
        near = []
        for _ in range(200):
            f = feats(D, t0 + rng.uniform(30, 1200) * rng.choice((-1, 1)), s)
            if f is not None:
                near.append(f)
            if len(near) >= 80:
                break
        N = pd.DataFrame(near)
        kept += 1
        ranks.append({k: (N[k] < mine[k]).mean() + 0.5 * (N[k] == mine[k]).mean() for k in CELLS_CONT})
        for k in CELLS_FLAG:
            flag_obs[k] += int(mine[k])
            flag_ps[k].append(N[k].mean())
    RA = pd.DataFrame(ranks)
    pA, desc = {}, {}
    for k in CELLS_CONT:
        v = RA[k]
        z = (v.mean() - 0.5) / (np.sqrt(1 / 12) / np.sqrt(len(v)))
        pA[k], desc[k] = pz(z), f"rank {v.mean():.2f}"
    for k in CELLS_FLAG:
        ps = np.array(flag_ps[k])
        e, var = ps.sum(), (ps * (1 - ps)).sum()
        pA[k] = pz((flag_obs[k] - e) / np.sqrt(var)) if var > 0 else 1.0
        desc[k] = f"his {flag_obs[k]:>2}/{len(ps)} vs nearby {ps.mean() * 100:4.1f}%"
    return kept, pA, desc


def stage_b(cache, days, days_obj, rng):
    from scipy.stats import binomtest
    rows = []
    for d in days:
        D = days_obj(d)
        ts, mid, spr = cache[d]
        for t in rng.uniform(1800, 23400, 40):
            for s in (1, -1):
                f = feats(D, t, s)
                o = race(ts, mid, t, s)
                if f is None or o is None:
                    continue
                rows.append(f | {"o": o, "on": race_net(ts, mid, spr, t, s), "day": d})
    P = pd.DataFrame(rows)
    mid_day = days[len(days) // 2]
    res, same_sign = {}, 0
    for k in CELLS:
        q = P.dropna(subset=[k, "on"])
        if k in CELLS_FLAG:
            hi, lo = q[k].astype(bool), ~q[k].astype(bool)
        else:
            hi, lo = q[k] >= q[k].quantile(2 / 3), q[k] <= q[k].quantile(1 / 3)
        h1, h2 = q.day < mid_day, q.day >= mid_day
        m1, m2 = q["on"][hi & h1].mean(), q["on"][lo & h1].mean()
        side, name = (hi, "high/on") if m1 >= m2 else (lo, "low/off")
        sel1, sel2 = q["on"][side & h1], q["on"][side & h2]
        n2, k2 = len(sel2), int(sel2.sum())
        p = binomtest(k2, n2, 0.5, alternative="greater").pvalue if n2 else 1.0
        res[k] = dict(side=name, first=sel1.mean() * 100, second=(k2 / n2 * 100) if n2 else np.nan, n2=n2, p=p)
        qo = P.dropna(subset=[k, "o"])
        if k in CELLS_FLAG:
            h, l = qo[k].astype(bool), ~qo[k].astype(bool)
        else:
            h, l = qo[k] >= qo[k].quantile(2 / 3), qo[k] <= qo[k].quantile(1 / 3)
        a, b = qo.day < mid_day, qo.day >= mid_day
        d1 = qo["o"][h & a].mean() - qo["o"][l & a].mean()
        d2 = qo["o"][h & b].mean() - qo["o"][l & b].mean()
        same_sign += int(np.sign(d1) == np.sign(d2))
        res[k]["d1"], res[k]["d2"] = d1 * 100, d2 * 100
    return P, res, same_sign


def main():
    cache = pickle.loads(TICKS.read_bytes())
    days = [d for d in sorted(cache) if cache[d] is not None]
    DD = {}

    def days_obj(d):
        if d not in DD:
            ts, mid, _ = cache[d]
            DD[d] = make_day(ts, mid)
        return DD[d]

    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    x["utc"] = x.open_time - pd.Timedelta(hours=GMT)
    x = x[x.utc >= "2026-04-01"]
    kept, pA, desc = stage_a(cache, days_obj, x, np.random.default_rng(17))
    hA = holm(pA)
    out = [f"backtest/his_rsi.py - {len(CELLS)} RSI cells ({len(CELLS_CONT)} continuous, {len(CELLS_FLAG)} hooks)",
           f"\nSTAGE A - his {kept} clean entries vs ~80 moments of the same day within 20 minutes, same direction. Smallest raw p-values (of {len(CELLS)}):"]
    for k in sorted(pA, key=pA.get)[:8]:
        out.append(f"  {k:<16}{desc[k]:<26} p {pA[k]:.3f}  Holm {hA[k]:.3f}")
    ref = "1m_rsi14_lvl"
    out.append(f"  reproduction check: {ref} {desc[ref]}  p {pA[ref]:.3f}   (his_ta.py, same entries: rank 0.46, p 0.50)")
    out.append(f"  cells with raw p < 0.05: {sum(v < 0.05 for v in pA.values())} of {len(pA)} (chance alone gives ~{0.05 * len(pA):.1f}); with Holm < 0.05: {sum(v < 0.05 for v in hA.values())}")
    pos = [k for k in CELLS_CONT if desc[k].startswith("rank") and float(desc[k].split()[1]) < 0.5]
    out.append(f"  continuous cells with rank below 0.5 (pullback side): {len(pos)} of {len(CELLS_CONT)}")

    P, res, same = stage_b(cache, days, days_obj, np.random.default_rng(23))
    hB = holm({k: v["p"] for k, v in res.items()})
    base = P["on"].dropna().mean() * 100
    out.append(f"\nSTAGE B - {len(P)} random moment x direction pairs on {P.day.nunique()} days; NET +7/-7 race, base {base:.1f}%, break-even 50%."
               f"\n  extreme chosen on the first half of the days, read on the second:")
    out.append(f"  {'cell':<16}{'chosen':>9}{'1st half':>10}{'2nd half':>10}{'n 2nd':>7}{'p':>8}{'Holm':>7}")
    for k in sorted(res, key=lambda c: res[c]["p"])[:8]:
        v = res[k]
        out.append(f"  {k:<16}{v['side']:>9}{v['first']:>9.1f}%{v['second']:>9.1f}%{v['n2']:>7}{v['p']:>8.3f}{hB[k]:>7.3f}")
    best2 = max(v["second"] for v in res.values() if np.isfinite(v["second"]))
    out.append(f"  best second-half net race over all {len(res)} cells: {best2:.1f}%   cells with Holm < 0.05: {sum(v < 0.05 for v in hB.values())}")
    out.append(f"  mid race (high - low), same sign in both halves: {same} of {len(res)} cells (a coin gives ~{len(res) / 2:.0f})")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_rsi.txt").write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

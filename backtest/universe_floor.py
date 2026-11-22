"""DOES A VOLUME FLOOR REMOVE THE LIVE LOSSES? THE MARKET-NEUTRAL AND DAILY BOOKS WITHOUT THE SMALL NAMES (2026-11-02)

THE QUESTION (the user: "Yes, run it", after the forward-test read of 2026-11-02): the live accounts' biggest losses came from
small, pumpy names - SOPH squeezed in the market-neutral (MN) short leg, AKE -45% in the daily book, BTW in five books at once
(CLAUDE.md s10, 2026-11-02 forward test). The backtest's MN book ranks the point-in-time top-60 by the PRIOR month's volume and the
daily book trades the top-40. Does narrowing those universes - top-20 / 30 / 40 for MN, top-20 / 30 for the daily book - lift the
risk-adjusted result, or does the cross-section's edge live in the smaller names?

WHAT IS TESTED (nothing in a bot changes; this is a backtest on the cached data)
  MN     the machine's MN book exactly as all_books.machine_books builds it: half 30-day momentum, half RSI(14), 10% of the
         eligible names a side (at least 3), weekly, the +50% short-leg exit, 12bp on turnover, real funding. Universe =
         eligibility(N) after drop_non_crypto, N in {20, 30, 40} against the base N = 60. Run on all 7 rebalance weekdays.
         `scored_run_floor` is mn_combos / moderate_retests.scored_run with two switches (the minimum number of eligible names,
         which is hard-coded at 20 there and would skip every week of a top-20 universe; and a fixed number of names a side);
         at N = 60 it must reproduce scored_run exactly - asserted in main().
         CONTROL: N = 60 with 3 names a side, because a smaller universe also means fewer names a side (3 / 3 / 4 against 6) -
         a floor that "wins" only by being as concentrated as the control has found concentration, not coin size.
  DAILY  daily_combos.gen with the deployed 20-day-mean exit (T20), PIT top-40 against top-30 and top-20, 8 slots, 3 day
         boundaries x 10 slot orderings, marked to market (dc.curve). The floors are subsets of the base by construction.

THE BAR (registered before the run)
  A floor PASSES if its Sharpe (MN: weekly net, annualised x sqrt(52)) is higher than the base's on BOTH halves (split
  2024-04-07, by booking date) on average over the 7 weekdays AND higher on at least 5 of the 7 weekdays on EACH half.
  Daily: tune CAGR and holdout CAGR both higher than the base on average over the 30 (boundary, ordering) pairs, with the
  worst fall not deeper. The paired differences are reported as mean +- se (the pairs share a market, so the se is a guide).

REGISTERED BEFORE RUNNING (2026-11-02; prior that any floor passes: about 15%)
  U1  No MN floor (20 / 30 / 40) passes the bar: the cross-sectional spread lives in the smaller names. (85%)
  U2  The top-20 MN floor is the worst of the three by paired Sharpe (three names a side from ~18 coins). (75%)
  U3  In the weeks the live tape resembles (alt-median 30-day return <= -15%), no floor turns the MN mean weekly return above
      +0.5% (the base is about -0.4% to +0.3%). (80%)
  U4  The daily-book floors LOWER the holdout CAGR (its money is pump trades in the smaller names) and do not make the worst
      fall materially shallower. (75%)
  U5  Verdict: no floor is worth a shadow book; nothing changes. (85%)

    python -m backtest.universe_floor
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import daily_combos as dc  # noqa: E402
from backtest import mn_combos as m  # noqa: E402
from backtest import moderate_retests as mr  # noqa: E402
from backtest import pair_lab as pl  # noqa: E402

LOG = ROOT / "logs" / "universe_floor.txt"
HOLDOUT = pl.HOLDOUT
MN_BASE = 60
MN_FLOORS = (20, 30, 40)
DAILY_BASE = 40
DAILY_FLOORS = (30, 20)
STARTS = tuple(range(7))
HOLD, LOOK, FRAC = 7, 30, 0.1
ALT_BLEED = -0.15


# ---------------------------------------------------------------- the MN runner
def scored_run_floor(score_mat, start=0, min_names=20, k_fixed=None):
    """moderate_retests.scored_run with stop="short_only", short_stop=0.5 (the live exit) and two switches: `min_names`, the
    fewest eligible names a week needs (scored_run: 20), and `k_fixed`, names a side instead of 10% of the eligible (>= 3)."""
    Dd = m.ohl()
    idx, X_, Fx, ff = Dd["idx"], Dd["X"], Dd["Fx"], Dd["ff"]
    rows, pl_, ps_ = [], set(), set()
    for i in range(LOOK + 1 + start, len(idx) - HOLD - 1, HOLD):
        t0 = idx[i]
        ok = (Dd["Em"][Dd["months"][i]] & ((t0.value - Dd["fv"]) // 86_400_000_000_000 >= m.MIN_AGE_D)
              & np.isfinite(X_[i]) & np.isfinite(X_[i - LOOK]))
        if ok.sum() < min_names:
            continue
        cand = np.flatnonzero(ok)
        past = score_mat[i, cand]
        k = k_fixed if k_fixed is not None else max(int(len(cand) * FRAC), 3)
        order = cand[np.argsort(np.where(np.isnan(past), np.inf, past), kind="stable")]
        sh, lo = order[:k], order[-k:]
        fwd = ff[i + HOLD] / X_[i] - 1
        fwd = fwd.copy()
        for x in sh:
            lvl = X_[i, x] * (1 + 0.5)
            for dd in range(i + 1, i + HOLD + 1):
                if np.isfinite(Dd["Hi"][dd, x]) and Dd["Hi"][dd, x] >= lvl:
                    fwd[x] = max(Dd["Op"][dd, x], lvl) / X_[i, x] - 1
                    break
        fnd = Fx[i + 1:i + HOLD + 1].sum(axis=0)
        gross = 0.5 * fwd[lo].mean() - 0.5 * fwd[sh].mean()
        carry = 0.5 * (-fnd[lo].mean()) + 0.5 * fnd[sh].mean()
        L_, S_ = {Dd["cols"][x] for x in lo}, {Dd["cols"][x] for x in sh}
        cost = m.FEE * min((len(L_ ^ pl_) + len(S_ ^ ps_)) / (4 * k), 1.0)
        pl_, ps_ = L_, S_
        rows.append((t0 + pd.Timedelta(days=HOLD), gross + carry - cost))
    return pd.Series([r for _, r in rows], index=pd.DatetimeIndex([t for t, _ in rows])).groupby(level=0).sum()


def score_mats(X):
    """The two rankings of all_books.machine_books: 30-day return and RSI(14), both known at close i."""
    C = pd.DataFrame(X)
    d = C.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()
    mom = X / np.r_[np.full((LOOK, X.shape[1]), np.nan), X[:-LOOK]] - 1
    return mom, rsi


def blend(mom, rsi, start, min_names=20, k_fixed=None):
    a = scored_run_floor(mom, start, min_names, k_fixed)
    b = scored_run_floor(rsi, start, min_names, k_fixed)
    idx = a.index.union(b.index)
    return 0.5 * a.reindex(idx).fillna(0.0) + 0.5 * b.reindex(idx).fillna(0.0)


def set_universe(elig):
    """Point the shared MN data at a different eligibility map; returns what to restore."""
    D = m.data()
    old = D["Em"]
    D["Em"] = {mo: np.array([mo in elig.get(s, ()) for s in D["cols"]]) for mo in sorted(set(D["months"]))}
    return old


# ---------------------------------------------------------------- statistics
def sharpe(x, per=52):
    x = np.asarray(x, float)
    sd = x.std(ddof=1) if len(x) > 1 else np.nan
    return float(x.mean() / sd * np.sqrt(per)) if sd and np.isfinite(sd) and sd > 0 else float("nan")


def max_fall(x):
    c = np.cumprod(np.r_[1.0, 1.0 + np.asarray(x, float)])           # the start counts as the first peak
    return float((1 - c / np.maximum.accumulate(c)).max()) if len(c) > 1 else float("nan")


def halves(s):
    return s[s.index < HOLDOUT], s[s.index >= HOLDOUT]


def paired(a, b):
    """a, b: equal-length arrays of the same pairs. Mean difference (a - b), its se, and the number of pairs a is higher."""
    d = np.asarray(a, float) - np.asarray(b, float)
    d = d[np.isfinite(d)]
    se = d.std(ddof=1) / np.sqrt(len(d)) if len(d) > 1 else float("nan")
    return float(d.mean()), float(se), int((d > 0).sum()), len(d)


def mn_passes(floor, base):
    """floor, base: {'tune': [Sharpe per weekday], 'hold': [...]}. The registered bar."""
    for h in ("tune", "hold"):
        dm, _, wins, n = paired(floor[h], base[h])
        if not (dm > 0 and wins >= 5):
            return False
    return True


def daily_passes(floor, base):
    """floor, base: {'tune': [CAGR per pair], 'hold': [...], 'fall': [...]} over the same (boundary, ordering) pairs."""
    for h in ("tune", "hold"):
        if not paired(floor[h], base[h])[0] > 0:
            return False
    return bool(np.nanmean(floor["fall"]) <= np.nanmean(base["fall"]))


# ---------------------------------------------------------------- the daily runner
def restrict_panel(PN, elig):
    """Replace each coin's eligible-months set by `elig`'s (a subset of the base by construction)."""
    for s, P in PN.items():
        P["el"] = elig.get(s, set())
    return PN


def daily_run(elig, lev=1.0):
    orig = dc.panel
    dc.panel = lambda off: restrict_panel(orig(off), elig)
    try:
        cfg = dict(dc.BASE, mean_n=20)
        out = {}
        for off in dc.PHASES:
            T = dc.gen(off, cfg)
            ntr = len(T)
            for sd in dc.SEEDS:
                tk = dc.allocate(T, sd, lev, prio=False)
                st = dc.stats(dc.curve(T, tk, off, lev))
                out[(off, sd)] = dict(st, trades=ntr)
        return out
    finally:
        dc.panel = orig


# ---------------------------------------------------------------- main
def main():
    from backtest.market_neutral import drop_non_crypto
    from backtest.wide_book import eligibility
    warnings.filterwarnings("ignore")
    L = [f"backtest/universe_floor.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; split {HOLDOUT:%Y-%m-%d}; "
         f"MN base top-{MN_BASE}, floors {MN_FLOORS}; daily base top-{DAILY_BASE}, floors {DAILY_FLOORS}", ""]

    def say(s=""):
        L.append(s)
        print(s, flush=True)

    D = m.data()
    mom, rsi = score_mats(D["X"])
    base_em = D["Em"]
    elig_mn = {n: drop_non_crypto(eligibility(n)) for n in MN_FLOORS}
    elig_mn[MN_BASE] = None                                   # the data's own map

    # self-check: the switches change nothing at the base
    ref = mr.scored_run(mom, start=0, stop="short_only", short_stop=0.5)
    mine = scored_run_floor(mom, start=0)
    assert ref.index.equals(mine.index) and np.allclose(ref.to_numpy(), mine.to_numpy(), atol=1e-12), "scored_run_floor != scored_run at the base"
    say("self-check: scored_run_floor at the base universe reproduces moderate_retests.scored_run exactly "
        f"({len(ref)} weeks, start 0)")

    # alt-market state at each rebalance, from the base universe's own members
    X, idx = D["X"], D["idx"]
    alt = pd.Series(np.nan, index=idx)
    for i in range(LOOK, len(idx)):
        mem = base_em[D["months"][i]] & np.isfinite(X[i]) & np.isfinite(X[i - LOOK])
        if mem.sum() >= 10:
            alt.iloc[i] = np.nanmedian(X[i, mem] / X[i - LOOK, mem] - 1)

    variants = [(f"base top-{MN_BASE}", MN_BASE, None, 20),
                (f"control top-{MN_BASE}, 3 a side", MN_BASE, 3, 20)]
    for n in MN_FLOORS:
        variants.append((f"floor top-{n}", n, None, 12 if n <= 20 else 20))
    res = {}
    for name, n, kf, mnames in variants:
        old = set_universe(elig_mn[n]) if elig_mn.get(n) is not None else None
        try:
            ser = {st: blend(mom, rsi, st, mnames, kf) for st in STARTS}
        finally:
            if old is not None:
                D["Em"] = old
        res[name] = ser

    say("1. MARKET-NEUTRAL BOOK: weekly net on the 7 rebalance weekdays (mean over weekdays; Sharpe is annualised x sqrt(52))")
    say(f"   {'variant':<26}{'weeks':>6}  {'tune Sharpe':>11}{'hold Sharpe':>12}  {'mean %/wk t/h':>15}  {'worst week':>10}  {'max fall':>8}  {'worst-weekday hold Sharpe':>26}")
    stat = {}
    for name, ser in res.items():
        sh_t, sh_h, mu_t, mu_h, worst, fall = [], [], [], [], [], []
        for st, s in ser.items():
            t, h = halves(s)
            sh_t.append(sharpe(t)), sh_h.append(sharpe(h))
            mu_t.append(t.mean()), mu_h.append(h.mean())
            worst.append(s.min()), fall.append(max_fall(s.to_numpy()))
        stat[name] = dict(tune=sh_t, hold=sh_h)
        say(f"   {name:<26}{int(np.mean([len(s) for s in ser.values()])):>6}  {np.nanmean(sh_t):>+11.2f}{np.nanmean(sh_h):>+12.2f}  "
            f"{np.mean(mu_t) * 100:>+6.2f}/{np.mean(mu_h) * 100:>+6.2f}%   {np.min(worst) * 100:>+9.1f}%  {np.mean(fall) * 100:>7.0f}%  {np.nanmin(sh_h):>+26.2f}")
    say()
    say("   paired against the base (mean difference in Sharpe over the 7 weekdays +- se, weekdays higher):")
    base = stat[f"base top-{MN_BASE}"]
    verdict_mn = {}
    for name in res:
        if name.startswith("base"):
            continue
        cells = []
        for h in ("tune", "hold"):
            dm, se, w, n = paired(stat[name][h], base[h])
            cells.append(f"{h} {dm:+.2f} +- {se:.2f} ({w}/{n})")
        ok = mn_passes(stat[name], base) if name.startswith("floor") else None
        verdict_mn[name] = ok
        say(f"   {name:<26}" + "   ".join(cells) + (f"   -> {'PASS' if ok else 'no pass'}" if ok is not None else "   (control)"))
    ctl = stat[f"control top-{MN_BASE}, 3 a side"]
    say("   floors against the k-matched control (is it coin size, or only fewer names a side?):")
    for n in MN_FLOORS:
        nm = f"floor top-{n}"
        cells = []
        for h in ("tune", "hold"):
            dm, se, w, nn = paired(stat[nm][h], ctl[h])
            cells.append(f"{h} {dm:+.2f} +- {se:.2f} ({w}/{nn})")
        say(f"   {nm:<26}" + "   ".join(cells))

    say()
    say("2. THE LIVE TAPE: mean weekly net in weeks that follow an alt market down >= 15% in 30 days (median member), by variant")
    say(f"   {'variant':<26}{'bleed weeks':>12}{'mean %/wk':>11}{'weeks<0':>9}{'worst':>8}   {'other weeks %/wk':>17}")
    for name, ser in res.items():
        bl, ot = [], []
        for st, s in ser.items():
            a = alt.reindex(s.index - pd.Timedelta(days=HOLD)).to_numpy()
            bl.append(s[a <= ALT_BLEED]), ot.append(s[a > ALT_BLEED])
        b, o = pd.concat(bl), pd.concat(ot)
        say(f"   {name:<26}{len(b) // len(STARTS):>12}{b.mean() * 100:>+11.2f}{(b < 0).mean() * 100:>8.0f}%{b.min() * 100:>+7.1f}%   {o.mean() * 100:>+17.2f}")

    say()
    say("3. DAILY BOOK (deployed 20-day-mean exit, 8 slots, 3 day boundaries x 10 orderings = 30 pairs, marked to market)")
    elig_d = {n: pl.universe() if n == DAILY_BASE else eligibility(n) for n in (DAILY_BASE,) + DAILY_FLOORS}
    dres = {n: daily_run(elig_d[n]) for n in elig_d}
    keys = sorted(dres[DAILY_BASE])
    grab = lambda n, k: np.array([dres[n][q][k] for q in keys], float)  # noqa: E731
    say(f"   {'variant':<12}{'trades/boundary':>16}{'tune CAGR':>11}{'hold CAGR':>11}{'fall':>7}{'worst month':>13}")
    for n in elig_d:
        tr = np.mean([dres[n][(o, 0)]["trades"] for o in dc.PHASES])
        say(f"   top-{n:<8}{tr:>16.0f}{np.nanmean(grab(n, 'tune')) * 100:>+10.0f}%{np.nanmean(grab(n, 'hold')) * 100:>+10.0f}%"
            f"{np.nanmean(grab(n, 'fall')) * 100:>6.0f}%{np.nanmean(grab(n, 'wm')) * 100:>+12.0f}%")
    verdict_d = {}
    for n in DAILY_FLOORS:
        fl = {k: grab(n, k) for k in ("tune", "hold", "fall")}
        bs = {k: grab(DAILY_BASE, k) for k in ("tune", "hold", "fall")}
        cells = []
        for k in ("tune", "hold"):
            dm, se, w, nn = paired(fl[k], bs[k])
            cells.append(f"{k} {dm * 100:+.0f} +- {se * 100:.0f} points ({w}/{nn})")
        verdict_d[n] = daily_passes(fl, bs)
        say(f"   top-{n} vs top-{DAILY_BASE}: " + "   ".join(cells) + f"   fall {np.nanmean(fl['fall']) * 100:.0f}% vs {np.nanmean(bs['fall']) * 100:.0f}%"
            f"   -> {'PASS' if verdict_d[n] else 'no pass'}")

    say("   the bet-smaller line: the BASE (top-40) at lower leverage - does any floor beat it at its own fall?")
    smaller = {lv: daily_run(elig_d[DAILY_BASE], lv) for lv in (0.75, 0.5)}
    for lv, r in smaller.items():
        g = lambda k: np.nanmean([r[q][k] for q in keys])  # noqa: E731
        say(f"   top-{DAILY_BASE} at {lv}x{'':<6}{'':>16}{g('tune') * 100:>+10.0f}%{g('hold') * 100:>+10.0f}%{g('fall') * 100:>6.0f}%{g('wm') * 100:>+12.0f}%")

    say()
    say("PREDICTIONS (registered above):")
    bleed = {name: np.mean([s[alt.reindex(s.index - pd.Timedelta(days=HOLD)).to_numpy() <= ALT_BLEED].mean() for s in ser.values()])
             for name, ser in res.items()}
    u3 = all(bleed[f"floor top-{n}"] <= 0.005 for n in MN_FLOORS)
    say(f"   U3 no floor lifts the live-tape MN mean above +0.5%/wk: {'RIGHT' if u3 else 'WRONG'}  "
        f"({ {k: round(v * 100, 2) for k, v in bleed.items()} })")
    hold_lower = all(np.nanmean(grab(n, 'hold')) < np.nanmean(grab(DAILY_BASE, 'hold')) for n in DAILY_FLOORS)
    fall_shallower = {n: np.nanmean(grab(DAILY_BASE, 'fall')) - np.nanmean(grab(n, 'fall')) for n in DAILY_FLOORS}
    say(f"   U4 daily floors lower the holdout CAGR: {'RIGHT' if hold_lower else 'WRONG'}; and no floor makes the fall materially "
        f"shallower (>= 5 points): {'RIGHT' if max(fall_shallower.values()) < 0.05 else 'WRONG'}  "
        f"(fall gain {({k: round(v * 100) for k, v in fall_shallower.items()})} points)")
    mnp = {n: verdict_mn[f"floor top-{n}"] for n in MN_FLOORS}
    say(f"   U5 no floor is worth a shadow book (nothing passes the bar): {'RIGHT' if not any(mnp.values()) and not any(verdict_d.values()) else 'WRONG'}")
    say(f"   U1 no MN floor passes: {'RIGHT' if not any(mnp.values()) else 'WRONG'}  ({mnp})")
    pairs = {n: np.nanmean([paired(stat[f'floor top-{n}'][h], base[h])[0] for h in ('tune', 'hold')]) for n in MN_FLOORS}
    say(f"   U2 top-20 is the worst MN floor: {'RIGHT' if min(pairs, key=pairs.get) == 20 else 'WRONG'}  (mean paired Sharpe {({k: round(v, 2) for k, v in pairs.items()})})")
    LOG.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"written {LOG}")


if __name__ == "__main__":
    main()

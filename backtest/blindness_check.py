"""IS THE TEST TEMPLATE BLIND? A positive control: plant a trader with KNOWN skill into real data and see whether the repo's own tests catch it (2026-11-08)

THE USER (2026-11-08, after a day of null results): "there is a pattern in how you test them, you use the same generic thing to test". Fair: most chart-idea tests
here use one template (events on closed 1h candles, entry at the next open, a fixed bracket, 12bp + funding, a random-entry control, both halves, day-clustered t).
The worry has two parts, and this file measures both instead of arguing:
  BIAS   does the template report a real edge smaller than it is (the fee, the control or the pessimistic fills eating it)?
  POWER  how big must a real edge be before the template's own gate says PASS?

TEST 1 - THE CRYPTO SWEEP / ZONE TEMPLATE (sweep_zone.py, sweep_zone_daily.py, sweep_confluence.py). The REAL event times are kept - every sweep the study found,
  same coins, same hours, same stop distances (the arm-A bracket: stop at the sweep extreme less 0.25 ATR, target 3R, out after 72 bars, 12bp + funding, gap-aware,
  stop first inside a bar), same random-hour controls (same coin and month, same stop distance), same day-clustered t, same halves (2024-04-07), the same gate
  (net R > 0 on both halves, excess over the control > 0 on both halves, holdout Holm p < 0.05 over the study's 6 cells, >= 100 holdout trades). ONLY THE DIRECTION
  is replaced: a planted trader goes the way the price actually moves over the next 24 hours with probability p and the other way otherwise (p = 0.50 is a coin).
  Both sides of every event are simulated once, so a rep is just a draw of sides. Three samples: ALL sweeps (the study's arm A), the 4h-ZONED sweeps (arm B's
  events) and the DAILY-ZONED sweeps with a next-zone target (the daily study's arm B events), all on the arm-A bracket so only the sample size differs.
  The planted edge in R is measured exactly (the p-weighted mean of the two sides' outcomes), so detection can be read against a true edge, not a guess.

TEST 2 - THE ANALYST DESK'S REGISTERED FORWARD TEST (backtest/analyst_sweetspot.score, used as written: 30 bets, mean >= +0.15R a bet, t >= 2, hit above the random
  odds, both halves positive). Pool = the desk's own replay calls with a stop of 0.8% or more (6,928, strategy_analysis/data/analyst_replay/calls.json). A forward
  window = the calls of 30 consecutive bets (day + side) from a random start day, so the real clustering is kept. Planted skill: every LOSS or EXPIRED call is turned
  into a WIN with probability q (R = its reward:risk less the 12bp fee in R). The pool's true mean R per bet is measured for each q.

REGISTERED BEFORE THE FIRST RUN (2026-11-08)
  B1  False alarms: at p = 0.50 (and q = 0) the gate passes in at most 5% of reps on every sample.                                                      90%
  B2  No bias: at p = 0.50 the mean excess over the control is within +-0.03R of zero, and at every p the measured net R matches the planted true R within 0.02R.  85%
  B3  ALL sweeps (~12,000 holdout trades a side): a true +0.05R a trade is caught in at least 80% of reps.                                             60%
  B4  4h-ZONED (~250 holdout trades a side): a true +0.10R is caught in under 30% of reps and +0.30R in over 80%.                                         60%
  B5  DAILY-ZONED (~60 holdout a side): never passes (the 100-trade rule); on the statistics alone +0.50R is caught in under 50%.                        65%
  B6  The desk's 30-bet test catches a desk with a true +0.15R a bet in under 30% of windows; it needs about +0.5R a bet for 80%.                        60%

RESULT (2026-11-08, logs/blindness_check.txt; 200 reps a row, 500 windows a row)
  NO BIAS, NO FALSE ALARMS. The measured net R matches the planted true R within 0.008R on every row (within 0.002 on the two larger samples); a coin (p 0.50)
  passes 0% everywhere, excess over the control -0.010 / +0.001 / -0.030R. A planted trader is measured at its true size, after the fee, the funding and the fills.
  WHAT SKILL IS WORTH on this bracket: random direction -0.084R a trade (fee + funding); each point of 24-hour direction accuracy adds ~+0.016R; 55% right is still
  -0.006R; 60% right is +0.07R, 65% +0.15R, 70% +0.23R.
  POWER - it depends entirely on the sample:
    ALL sweeps (~12,200 holdout trades a side): +0.07R caught 100% of the time (+0.15R 100%). On a big sample the template is not blind.
    4h-ZONED (~476 a side): +0.07R caught 12%, +0.15R 66%, +0.23R 98%. sweep_zone.py could have missed a real edge of about +0.10R most of the time.
    DAILY-ZONED (~58 a side): 0% at every size under the gate (the 100-trade rule), 2% at +0.31R even on the statistics alone. sweep_zone_daily.py's
      'underpowered' label was right: that study could not have passed ANY plausible edge.
    THE DESK'S 30-BET TEST: a desk with a true +0.12R a bet passes 3%, +0.28R (hitting 25% against 17.5% random odds) 15%, +0.43R 35%, +0.61R 57%,
      +0.89R (42% against 17.5%) 91%. At 30 bets it can confirm only a very large edge; a NO PASS there would not show the desk has none.
  PREDICTIONS: B1 right (0% false alarms). B2 right. B3 consistent (+0.07R caught 100%; +0.05 itself not on the grid). B4 right (+0.07 12% / +0.15 66%;
    +0.23 98%). B5 right (0% under the gate, 2% at +0.31R). B6 half wrong: +0.15R does pass under 30% (3-15%), but 80% needs about +0.85R a bet, not +0.5R.
  READING: the user's suspicion is half right. The template does not shrink or hide an edge (no bias), and on large samples it would have seen any edge worth
    trading. On RARE setups - the zoned sweeps, the daily zones, the desk's 30 bets - its 'no' means 'could not see', not 'dead': those nulls are uninformative
    below about +0.1R (4h zones), +0.3R (daily zones) and +0.5R a bet (the desk). Fix in method, not in code: print the minimum detectable edge (this file's
    planted-skill power) BEFORE reading any null, and call a null below it 'cannot tell'.

    python backtest/blindness_check.py          (builds logs/blindness_events.pkl on the first run, a few minutes; tests: python tests/test_blindness_check.py)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "blindness_check.txt"
CACHE = ROOT / "logs" / "blindness_events.pkl"
HOLDOUT = pd.Timestamp("2024-04-07")
N_CELLS = 6                          # the studies' 6 gate cells (3 arms x 2 sides): Holm over 6
MIN_HOLD = 100
DIR_H = 24                           # the planted trader knows the sign of the next 24 hours' move with probability p
PS = (0.50, 0.52, 0.55, 0.60, 0.65, 0.70, 0.80)
QS = (0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40)
REPS, WINDOWS = 200, 500
FEE = 0.0012


# ------------------------------------------------------------------ statistics (fast versions of the studies' own)

def t_clustered(y: np.ndarray, codes: np.ndarray, G: int) -> float:
    """sweep_confluence.t_by_day with the day codes precomputed: per-trade mean, standard error clustered by day."""
    N = len(y)
    if G < 3 or N == 0:
        return float("nan")
    m = y.mean()
    S = np.bincount(codes, weights=y - m, minlength=G)
    se = np.sqrt(G / (G - 1) * (S ** 2).sum()) / N
    return float(m / se) if se > 0 else float("nan")


def p_one(t: float) -> float:
    from math import erf, sqrt
    return 1.0 if not np.isfinite(t) else 0.5 * (1 - erf(t / sqrt(2)))


def holm_min_ok(ps: list, n_cells: int = N_CELLS, alpha: float = 0.05) -> list:
    """Holm over n_cells, the other cells null (p = 1): returns, for each given p, whether its Holm-adjusted p is < alpha."""
    full = sorted([(p, k) for k, p in enumerate(ps)] + [(1.0, -1)] * (n_cells - len(ps)))
    run, adj = 0.0, {}
    for r, (p, k) in enumerate(full):
        run = max(run, min(1.0, (n_cells - r) * p))
        if k >= 0:
            adj[k] = run
    return [adj[k] < alpha for k in range(len(ps))]


def gate(R, C, side, hold, codes, G, min_hold=MIN_HOLD):
    """The studies' gate on one planted strategy. Cells = side x {tune, hold}. Returns dict(any, both, stats_any): `any` = at least one side cell passes the
    whole gate, `both` = both pass, `stats_any` = at least one passes without the 100-trade rule."""
    res, ps, rows = [], [], []
    for s in (1, -1):
        mt, mh = (side == s) & ~hold, (side == s) & hold
        if mt.sum() < 3 or mh.sum() < 3:
            rows.append(None)
            ps.append(1.0)
            continue
        tn, hn = R[mt].mean(), R[mh].mean()
        te, he = (R[mt] - C[mt]).mean(), (R[mh] - C[mh]).mean()
        sub = codes[mh]
        u, inv = np.unique(sub, return_inverse=True)
        t = t_clustered(R[mh], inv, len(u))
        ps.append(p_one(t))
        rows.append((tn > 0 and hn > 0 and te > 0 and he > 0, int(mh.sum())))
    hok = holm_min_ok(ps)
    for k, r in enumerate(rows):
        if r is None:
            res.append((False, False))
            continue
        stats_ok = r[0] and hok[k]
        res.append((stats_ok and r[1] >= min_hold, stats_ok))
    return dict(any=any(a for a, _ in res), both=all(a for a, _ in res), stats_any=any(b for _, b in res))


# ------------------------------------------------------------------ test 1: the events, both sides simulated once

def build_events() -> pd.DataFrame:
    from backtest import pair_lab as pl
    from backtest import sweep_zone as z4
    from backtest.capitulation_wide import funding_cum
    T4 = pd.read_pickle(ROOT / "logs" / "sweep_zone_events.pkl")[["coin", "t_in", "day", "rf_a", "zoned"]]
    TD = pd.read_pickle(ROOT / "logs" / "sweep_zone_daily_events.pkl")
    TD = TD[TD.zoned & TD.has_target][["coin", "t_in", "day", "rf_a"]].assign(dzone=True)
    E = T4.merge(TD[["coin", "t_in", "dzone"]], on=["coin", "t_in"], how="outer")
    E = E.merge(TD[["coin", "t_in", "rf_a", "day"]], on=["coin", "t_in"], how="left", suffixes=("", "_d"))
    E["rf_a"] = E.rf_a.fillna(E.rf_a_d)
    E["day"] = E.day.fillna(E.day_d)
    E["zoned"] = E.zoned.fillna(False).astype(bool)
    E["dzone"] = E.dzone.fillna(False).astype(bool)
    E = E.drop(columns=["rf_a_d", "day_d"])
    H = pl.hourly_all()
    rng = np.random.default_rng(7)
    out = []
    for coin, g in E.groupby("coin"):
        hh = H[coin]
        t = hh.time.to_numpy("datetime64[ns]")
        o, h, l, c = (hh[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        n = len(c)
        fc = funding_cum(coin, t, hh)
        ym = pd.DatetimeIndex(t).strftime("%Y-%m").to_numpy()
        by_month = pd.Series(np.arange(n)).groupby(ym).apply(lambda x: x.to_numpy())
        pools = {m: v[(v > z4.TREND_WARM) & (v + z4.HOLD_R + 2 < n)] for m, v in by_month.items()}
        idx = np.searchsorted(t, g.t_in.to_numpy("datetime64[ns]")) - 1           # the signal bar: entry at t[i+1] = t_in
        for (_, r), i in zip(g.iterrows(), idx):
            if i < 0 or i + max(z4.HOLD_R, DIR_H) + 2 >= n or t[i + 1] != np.datetime64(r.t_in, "ns"):
                continue
            e, rf = o[i + 1], float(r.rf_a)
            d = np.sign(c[i + DIR_H] - e)                                         # the true 24-hour direction from the entry
            if d == 0:
                continue
            L = z4.trade_r(i, 1, e * (1 - rf), o, h, l, c, fc)
            S = z4.trade_r(i, -1, e * (1 + rf), o, h, l, c, fc)
            pool = pools.get(ym[i])
            if L is None or S is None or pool is None or not len(pool):
                continue
            k = int(rng.choice(pool))
            ek = o[k + 1]
            CL = z4.trade_r(k, 1, ek * (1 - rf), o, h, l, c, fc)
            CS = z4.trade_r(k, -1, ek * (1 + rf), o, h, l, c, fc)
            if CL is None or CS is None:
                continue
            out.append(dict(coin=coin, t_in=r.t_in, day=r.day, zoned=r.zoned, dzone=r.dzone, rf=rf, d=int(d),
                            RL=L["net"] / rf, RS=S["net"] / rf, CL=CL["net"] / rf, CS=CS["net"] / rf))
    return pd.DataFrame(out)


def plant(E: pd.DataFrame, p: float, rng) -> tuple:
    """Draw the planted trader's sides: the true direction with probability p. Returns (side, R, C)."""
    right = rng.random(len(E)) < p
    side = np.where(right, E.d.to_numpy(), -E.d.to_numpy())
    R = np.where(side > 0, E.RL.to_numpy(), E.RS.to_numpy())
    C = np.where(side > 0, E.CL.to_numpy(), E.CS.to_numpy())
    return side, R, C


def true_edge(E: pd.DataFrame, p: float) -> float:
    """The planted strategy's expected net R a trade: each event's two outcomes weighted by p."""
    up = E.d.to_numpy() > 0
    Rright = np.where(up, E.RL, E.RS)
    Rwrong = np.where(up, E.RS, E.RL)
    return float((p * Rright + (1 - p) * Rwrong).mean())


def test1(E: pd.DataFrame, L: list):
    hold = (pd.to_datetime(E.t_in) >= HOLDOUT).to_numpy()
    codes_all = pd.factorize(pd.to_datetime(E.day).to_numpy())[0]
    for name, m in (("ALL sweeps (arm A's events)", np.ones(len(E), bool)), ("4h-ZONED sweeps (arm B's events)", E.zoned.to_numpy()),
                    ("DAILY-ZONED with a target (daily arm B's events)", E.dzone.to_numpy())):
        X = E[m].reset_index(drop=True)
        hm, codes = hold[m], codes_all[m]
        G = codes.max() + 1
        L.append(f"\n== {name}: {len(X)} events ({int((~hm).sum())} tune / {int(hm.sum())} holdout; about {int(hm.sum()) // 2} holdout trades a side)")
        L.append(f"   {'p right':>8} {'true R':>8} {'measured R':>11} {'excess':>8}  {'PASS (gate)':>12} {'PASS both sides':>16} {'PASS w/o 100-trade rule':>24}")
        for p in PS:
            rng = np.random.default_rng(int(p * 1000))
            got, both, stat, meas, exc = 0, 0, 0, [], []
            for _ in range(REPS):
                side, R, C = plant(X, p, rng)
                g = gate(R, C, side, hm, codes, G)
                got += g["any"]
                both += g["both"]
                stat += g["stats_any"]
                meas.append(R.mean())
                exc.append((R - C).mean())
            L.append(f"   {p:>8.2f} {true_edge(X, p):>+8.3f} {np.mean(meas):>+11.3f} {np.mean(exc):>+8.3f}  {got / REPS * 100:>11.0f}% {both / REPS * 100:>15.0f}% {stat / REPS * 100:>23.0f}%")


# ------------------------------------------------------------------ test 2: the desk's registered 30-bet test

def desk_pool() -> list:
    from backtest import analyst_sweetspot as ss
    raw = json.loads((ROOT / "strategy_analysis" / "data" / "analyst_replay" / "calls.json").read_text())
    rows = []
    for k, r in enumerate(raw):
        if r["stop_pct"] < ss.SWEET_STOP or r["status"] not in ("WIN", "LOSS", "EXPIRED"):
            continue
        rr = abs(r["target"] - r["entry"]) / abs(r["entry"] - r["stop"])
        rows.append(dict(id=k, made_ms=int(r["made_ms"]), day=pd.to_datetime(r["made_ms"], unit="ms").strftime("%Y-%m-%d"), side=r["side"], method=r["method"],
                         status=r["status"], stop_pct=r["stop_pct"], r=float(r["r_net"]), base=float(r["base_p"]), win_r=rr - FEE / r["stop_pct"]))
    rows.sort(key=lambda r: r["made_ms"])
    return rows


def flip(rows: list, q: float, rng) -> list:
    """Planted skill: each LOSS / EXPIRED call becomes a WIN with probability q (R = reward:risk less the fee in R)."""
    out = []
    for r in rows:
        if r["status"] != "WIN" and rng.random() < q:
            r = dict(r, status="WIN", r=r["win_r"])
        out.append(r)
    return out


def window(rows: list, start_day: str, n_bets: int = 30) -> list:
    """The calls of the first n_bets (day, side) bets from start_day on, in date order: what the forward test will have read at its 30th bet."""
    keys, out = [], []
    for r in rows:
        if r["day"] < start_day:
            continue
        k = (r["day"], r["side"])
        if k not in keys:
            if len(keys) == n_bets:
                break
            keys.append(k)
        out.append(r)
    return out if len(keys) == n_bets else []


def pool_bet_mean(rows: list) -> float:
    g = {}
    for r in rows:
        g.setdefault((r["day"], r["side"]), []).append(r["r"])
    return float(np.mean([np.mean(v) for v in g.values()]))


def test2(L: list):
    from backtest import analyst_sweetspot as ss
    pool = desk_pool()
    days = sorted({r["day"] for r in pool})
    starts = days[:-60]
    L.append(f"\n== THE DESK'S 30-BET FORWARD TEST (analyst_sweetspot.score as registered) on its own replay: {len(pool)} calls with a stop >= 0.8%, "
             f"{len(days)} days; {WINDOWS} windows of 30 consecutive bets per row")
    L.append(f"   {'q (losers made winners)':>24} {'hit':>6} {'random odds':>12} {'true R a bet':>13}  {'PASS':>6}  {'mean R a bet in a window, 10th / 50th / 90th pct':>48}")
    for q in QS:
        rng = np.random.default_rng(int(q * 1000) + 1)
        P = flip(pool, q, rng)
        hit = np.mean([r["status"] == "WIN" for r in P])
        base = np.mean([r["base"] for r in P])
        passed, means = 0, []
        for _ in range(WINDOWS):
            w = window(P, starts[int(rng.integers(len(starts)))])
            if not w:
                continue
            s = ss.score(w, since_ms=0)
            passed += s["verdict"].startswith("PASS")
            means.append(s["mean_r"])
        L.append(f"   {q:>24.2f} {hit * 100:>5.1f}% {base * 100:>11.1f}% {pool_bet_mean(P):>+13.3f}  {passed / WINDOWS * 100:>5.0f}%  "
                 f"{np.percentile(means, 10):>+16.2f} / {np.percentile(means, 50):+.2f} / {np.percentile(means, 90):+.2f}")


def main():
    if not CACHE.exists() or "--refit" in sys.argv:
        E = build_events()
        E.to_pickle(CACHE)
    E = pd.read_pickle(CACHE)
    L = [f"backtest/blindness_check.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; planted skill in real data, judged by the studies' own gates; {REPS} reps a row (test 1), "
         f"{WINDOWS} windows a row (test 2)"]
    test1(E, L)
    test2(L)
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

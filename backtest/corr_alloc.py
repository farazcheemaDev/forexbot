"""CORRELATION-CLUSTERED SLOT ALLOCATION — is the correlation tax recoverable?

    python -m backtest.corr_alloc

THE PROPOSITION
    Per-trade expectancy is +0.13R. Portfolio expectancy is +0.03 to +0.087R. The
    difference is not the market taking money - it is the allocator spending 12
    slots on what behaves like ~1.6 independent bets.

    blend.run() allocates slots FIRST-COME-FIRST-SERVED:

        opens = [u for u in opens if u > a_]
        if len(opens) >= slots:
            declined += 1

    There is no notion of what is already held. When nine alts break out in the same
    hour - which is the normal case in crypto - all nine take slots, and the book is
    one bet at 9x size. The claim being tested is that capping slots PER CORRELATION
    CLUSTER buys 12 bets instead of 1.6, at the same gross exposure.

THE CONTROL THAT DECIDES THIS, AND WHY IT IS NOT OPTIONAL
    Any per-cluster cap also REDUCES simultaneous positions. So a naive test would
    show an improvement that is really just de-leveraging, and I would write up
    "correlation clustering works" when the truth is "holding fewer positions works".
    That is exactly the shape of the section-19 retraction in his_strategy.md: a
    result created by the construction of its own control.

    So every clustered run is paired with a RANDOM-CLUSTER run using the SAME number
    of clusters and the SAME cluster sizes, assigned by shuffling the coin labels.
    Both de-leverage identically. Only the correlation run knows which coins are
    redundant.

        correlation clusters beat random clusters  -> the mechanism is real
        correlation ~= random                      -> it was only de-leveraging, and
                                                      the honest fix is fewer slots

    A third baseline - the current global cap at a REDUCED slot count - is run too,
    because if plain "fewer slots" matches both, the clustering machinery is dead
    weight regardless of which way the random comparison falls.

POINT-IN-TIME CLUSTERING
    Clusters are refit on the 1st of each month from the trailing 90 days of hourly
    returns, using only bars that closed BEFORE that timestamp. A trade opening at
    time a_ is assigned using the most recent fit at or before a_. Nothing about a
    trade's outcome, or about any later correlation, can reach the decision.

DEGREES OF FREEDOM, DECLARED
    k (cluster count) and the per-cluster cap are swept. That is a 2-parameter sweep,
    so results are tuned on the first 60% by date and the decision is read off the
    last 40%, which never informs the choice. The correlation window (90d) and refit
    cadence (monthly) are FIXED at the outset and not swept, to keep the sweep small.

REGISTERED PREDICTION (2026-09-18, before running)
    Correlation clustering will NOT beat random clustering. Crypto alt correlations
    sit at 0.7-0.9 and move around; clustering 12 near-identical series produces
    groupings that are mostly noise and that change every refit. I expect both
    clustered variants to improve drawdown by roughly the same amount, and for plain
    "fewer slots" to match them - which would mean the 77% correlation tax is the
    market's, not the allocator's, and is not recoverable by allocation at all.

    If correlation clustering DOES separate from random, that is the first
    allocation-level edge in this project and it goes live.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402

CORR_WINDOW_D = 90          # fixed before running, not swept
REFIT = "MS"                # month start, fixed before running
HINDSIGHT = blend.HINDSIGHT
rng = np.random.default_rng(71)


# --------------------------------------------------------------------------- #
#  point-in-time clustering
# --------------------------------------------------------------------------- #
def returns_panel():
    """Hourly log returns for the book, one column per coin."""
    cols = {}
    for c in blend.BOOK:
        d = blend.load(c)
        if d is None:
            continue
        s = pd.Series(d["close"].to_numpy(float),
                      index=pd.DatetimeIndex(d["time"]))
        cols[c] = np.log(s / s.shift(1))
    return pd.DataFrame(cols).dropna(how="all")


def fit_clusters(panel, k):
    """{refit timestamp -> {coin: cluster id}} using only PRIOR bars.

    At each refit date the correlation matrix is built from the trailing
    CORR_WINDOW_D days of returns ending strictly BEFORE that date.
    """
    out = {}
    dates = pd.date_range(panel.index[0].normalize(), panel.index[-1], freq=REFIT)
    for d in dates:
        win = panel.loc[(panel.index >= d - pd.Timedelta(days=CORR_WINDOW_D))
                        & (panel.index < d)]
        win = win.dropna(axis=1, thresh=int(len(win) * 0.6))
        if len(win) < 24 * 30 or win.shape[1] < k:
            continue
        cm = win.corr().fillna(0.0).to_numpy().copy()
        np.fill_diagonal(cm, 1.0)
        dist = np.clip(1.0 - cm, 0.0, 2.0)
        dist = (dist + dist.T) / 2.0
        np.fill_diagonal(dist, 0.0)
        lab = fcluster(linkage(squareform(dist, checks=False), method="average"),
                       k, criterion="maxclust")
        out[d] = dict(zip(win.columns, lab.astype(int)))
    return out


def shuffle_clusters(fits):
    """Same cluster SIZES, random membership. The de-leveraging control."""
    out = {}
    for d, m in fits.items():
        coins = list(m)
        labs = np.array([m[c] for c in coins])
        out[d] = dict(zip(coins, rng.permutation(labs)))
    return out


# --------------------------------------------------------------------------- #
#  the allocator under test
# --------------------------------------------------------------------------- #
def run_alloc(rules, slots, fits=None, per_cluster=None,
              t_from=None, t_to=None, regime=blend.REGIME_MULT):
    """blend.run() with an optional per-cluster cap layered on top.

    fits=None reproduces blend.run() exactly - that equivalence is asserted in
    main() rather than assumed.
    """
    tr, stops = [], {}
    for r in rules:
        a, s = blend.sleeve(r)
        tr += a
        for kk, v in s.items():
            stops[kk] = max(stops.get(kk, 0.0), v)
    tr.sort(key=lambda x: x[0])
    bear = blend.btc_bear() if regime > 0 else None
    f0 = blend.RISK / 100.0
    fit_dates = sorted(fits) if fits else []

    eq, curve, times = 1.0, [], []
    opens = []                 # list of (close_time, cluster_id)
    Rs, declined, dec_cluster, ruined = [], 0, 0, False
    exposure = []
    for a_, b_, r, _tag, coin in tr:
        if t_from is not None and a_ < t_from:
            continue
        if t_to is not None and a_ >= t_to:
            continue
        opens = [u for u in opens if u[0] > a_]
        if len(opens) >= slots:
            declined += 1
            continue
        cl = None
        if fits:
            i = np.searchsorted(fit_dates, a_, side="right") - 1
            if i < 0:
                continue                      # no fit yet: cannot allocate honestly
            cl = fits[fit_dates[i]].get(coin)
            if cl is None:
                continue
            if sum(1 for u in opens if u[1] == cl) >= per_cluster:
                dec_cluster += 1
                continue
        opens.append((b_, cl))
        exposure.append(len(opens))
        f = f0
        if bear is not None:
            try:
                if bool(bear.asof(a_)):
                    f *= regime
            except Exception:
                pass
        Rs.append(r)
        if not ruined:
            eq *= (1 + r * f)
            if eq <= 0.01:
                eq, ruined = 0.0, True
        curve.append(eq)
        times.append(b_)

    if len(Rs) < 30:
        return None
    R = np.asarray(Rs)
    cur = np.asarray(curve)
    pk = np.maximum.accumulate(np.maximum(cur, 1e-12))
    dd = float((1 - cur / pk).max() * 100)
    ts = pd.DatetimeIndex(times)
    yrs = max((ts[-1] - ts[0]).days / 365.25, 1e-9)
    cagr = (max(cur[-1], 0.0) ** (1 / yrs) - 1) * 100 if not ruined else -100.0
    hc = cagr / HINDSIGHT if cagr > -100 else -100.0
    return dict(n=len(R), declined=declined, dec_cluster=dec_cluster,
                mean=float(R.mean()), dd=dd, ruined=ruined,
                exposure=float(np.mean(exposure)) if exposure else 0.0,
                hpm=((1 + hc / 100) ** (1 / 12) - 1) * 100 if hc > -100 else -100.0,
                R=R, times=ts)


def show(lab, d, width=34):
    if d is None:
        print(f"  {lab:<{width}}  (too few trades)")
        return
    print(f"  {lab:<{width}}{d['n']:>6}{d['exposure']:>7.1f}"
          f"{d['mean']:>+9.3f}{d['hpm']:>+9.2f}%{d['dd']:>8.1f}%"
          f"{d['mean']/max(d['dd'],1e-9)*100:>9.3f}")


HDR = (f"  {'variant':<34}{'n':>6}{'avg pos':>7}{'mean R':>9}"
       f"{'/month':>10}{'maxDD':>8}{'R/DD':>9}")


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: correlation clustering will NOT beat random clustering.")
    print("Alt correlations are 0.7-0.9 and unstable, so clusters are mostly noise.")
    print("If plain 'fewer slots' matches both, the correlation tax is the market's")
    print("and is not recoverable by allocation.\n")

    rules = ("1h", "4h")
    SLOTS = 12

    # --- equivalence guard: fits=None must reproduce blend.run exactly --------
    blend._S.clear()
    base_ref = blend.run(list(rules), SLOTS)
    blend._S.clear()
    base_new = run_alloc(list(rules), SLOTS)
    assert base_ref is not None and base_new is not None
    assert base_ref["n"] == base_new["n"] and \
        abs(base_ref["dd"] - base_new["dd"]) < 1e-9 and \
        abs(base_ref["hpm"] - base_new["hpm"]) < 1e-9, (
            "run_alloc(fits=None) no longer matches blend.run - the baseline in "
            f"every table below would be a different strategy. "
            f"ref n={base_ref['n']} dd={base_ref['dd']:.4f} hpm={base_ref['hpm']:.4f} "
            f"vs new n={base_new['n']} dd={base_new['dd']:.4f} "
            f"hpm={base_new['hpm']:.4f}")
    print(f"  guard OK: run_alloc(fits=None) reproduces blend.run "
          f"({base_ref['n']} trades, {base_ref['dd']:.1f}% DD)\n")

    panel = returns_panel()
    print(f"  return panel: {panel.shape[1]} coins, {len(panel):,} hourly bars, "
          f"{panel.index[0]:%Y-%m-%d} .. {panel.index[-1]:%Y-%m-%d}")
    cm = panel.corr()
    off = cm.to_numpy()[~np.eye(len(cm), dtype=bool)]
    print(f"  pairwise hourly correlation: mean {off.mean():.2f}, "
          f"min {off.min():.2f}, max {off.max():.2f}")
    print(f"  => effective independent bets ~ "
          f"{len(cm) / (1 + (len(cm)-1) * off.mean()):.2f} out of {len(cm)}\n")

    cut = panel.index[0] + (panel.index[-1] - panel.index[0]) * 0.60
    cut = pd.Timestamp(cut).normalize()
    print(f"  tune on bars before {cut:%Y-%m-%d}, decide on the rest\n")

    fits_cache = {k: fit_clusters(panel, k) for k in (2, 3, 4)}
    for k, f in fits_cache.items():
        sizes = [sorted(pd.Series(list(m.values())).value_counts().tolist(),
                        reverse=True) for m in f.values()]
        med = sizes[len(sizes) // 2] if sizes else []
        print(f"  k={k}: {len(f)} monthly refits, typical cluster sizes {med}")
    print()

    print("=" * 96)
    print("1. TUNE WINDOW — does a per-cluster cap beat the global cap?")
    print("=" * 96)
    print(HDR)
    tune = {}
    blend._S.clear()
    tune["baseline global 12"] = run_alloc(list(rules), SLOTS, t_to=cut)
    show("baseline: global cap 12", tune["baseline global 12"])
    for s in (6, 8):
        d = run_alloc(list(rules), s, t_to=cut)
        tune[f"global {s}"] = d
        show(f"control: global cap {s} (fewer slots)", d)
    print()
    for k in (2, 3, 4):
        for cap in (2, 3, 4):
            if cap * k > SLOTS:
                continue
            dc = run_alloc(list(rules), SLOTS, fits_cache[k], cap, t_to=cut)
            dr = run_alloc(list(rules), SLOTS, shuffle_clusters(fits_cache[k]),
                           cap, t_to=cut)
            tune[f"corr k={k} cap={cap}"] = dc
            tune[f"rand k={k} cap={cap}"] = dr
            show(f"CORR  k={k}, max {cap} per cluster", dc)
            show(f"  rand k={k}, max {cap} per cluster  (control)", dr)
    print("\n  'avg pos' is the mean number of simultaneous positions. If CORR and")
    print("  rand share it, they de-leverage identically and only the grouping differs.")

    print("\n" + "=" * 96)
    print("2. THE COMPARISON THAT DECIDES IT — corr minus rand, on the TUNE window")
    print("=" * 96)
    print(f"  {'cell':<22}{'corr /mo':>11}{'rand /mo':>11}{'diff':>9}"
          f"{'corr DD':>10}{'rand DD':>10}{'DD diff':>10}")
    wins = 0
    cells = 0
    for k in (2, 3, 4):
        for cap in (2, 3, 4):
            c, r = tune.get(f"corr k={k} cap={cap}"), tune.get(f"rand k={k} cap={cap}")
            if not c or not r:
                continue
            cells += 1
            if c["hpm"] > r["hpm"]:
                wins += 1
            print(f"  k={k} cap={cap:<16}{c['hpm']:>+10.2f}%{r['hpm']:>+10.2f}%"
                  f"{c['hpm']-r['hpm']:>+9.2f}{c['dd']:>9.1f}%{r['dd']:>9.1f}%"
                  f"{c['dd']-r['dd']:>+9.1f}")
    print(f"\n  correlation beat random in {wins} of {cells} cells "
          f"(coin-flip expectation {cells/2:.1f})")

    print("\n" + "=" * 96)
    print("3. HOLDOUT — the best TUNE cell, on data that never informed the choice")
    print("=" * 96)
    ranked = sorted(((v["hpm"], kk) for kk, v in tune.items()
                     if v and kk.startswith("corr")), reverse=True)
    if not ranked:
        print("  no correlation cell produced enough trades to rank")
        return
    best_hpm, best = ranked[0]
    k = int(best.split("k=")[1].split(" ")[0])
    cap = int(best.split("cap=")[1])
    print(f"  best correlation cell on the tune window: {best} "
          f"({best_hpm:+.2f}%/mo)\n")
    print(HDR)
    out = {}
    out["base"] = run_alloc(list(rules), SLOTS, t_from=cut)
    show("baseline: global cap 12", out["base"])
    out["g8"] = run_alloc(list(rules), 8, t_from=cut)
    show("control: global cap 8", out["g8"])
    out["corr"] = run_alloc(list(rules), SLOTS, fits_cache[k], cap, t_from=cut)
    show(f"CORR  k={k}, max {cap} per cluster", out["corr"])
    out["rand"] = run_alloc(list(rules), SLOTS,
                            shuffle_clusters(fits_cache[k]), cap, t_from=cut)
    show(f"  rand k={k}, max {cap} per cluster  (control)", out["rand"])

    print("\n" + "=" * 96)
    print("VERDICT")
    print("=" * 96)
    c, r, b = out["corr"], out["rand"], out["base"]
    if not (c and r and b):
        print("  holdout too thin to decide.")
        return
    beat_rand = c["hpm"] > r["hpm"] + 0.5
    beat_base = c["hpm"] > b["hpm"]
    print(f"  holdout: baseline {b['hpm']:+.2f}%/mo at {b['dd']:.1f}% DD")
    print(f"           CORR     {c['hpm']:+.2f}%/mo at {c['dd']:.1f}% DD")
    print(f"           random   {r['hpm']:+.2f}%/mo at {r['dd']:.1f}% DD")
    if beat_rand and beat_base and wins > cells * 0.7:
        print("\n  CORRELATION CLUSTERING SURVIVES. It beats its own de-leveraging")
        print("  control on the holdout and won most tune cells. This is the first")
        print("  allocation-level edge in the project - re-check, then ship it.")
    elif beat_base and not beat_rand:
        print("\n  The IMPROVEMENT IS REAL BUT THE MECHANISM IS NOT CORRELATION.")
        print("  Random clusters do as well or better, so what helped was holding")
        print("  fewer simultaneous positions. The honest fix is a lower slot cap,")
        print("  not a clustering engine. Compare the 'global cap 8' row.")
    else:
        print("\n  NOTHING TO RECOVER. The per-cluster cap does not beat the global")
        print("  cap on unseen data. The gap between +0.13R per trade and +0.03R")
        print("  per portfolio is the market's correlation, not the allocator's")
        print("  waste, and no slot rule reclaims it.")


if __name__ == "__main__":
    main()

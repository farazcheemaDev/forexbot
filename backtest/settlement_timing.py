"""DOES PRICE GET PUSHED AROUND THE FUNDING SETTLEMENT? - a microstructure test on 860 perps.

THE MECHANISM (why this could be real and not a pattern)
    Funding is paid only by positions held AT the settlement timestamp. When the rate is
    strongly positive, two groups act on the clock rather than on an opinion:
      - longs who do not want to pay close shortly BEFORE the settlement and re-open after;
      - funding collectors open shorts shortly BEFORE it and close after.
    Both push the perp DOWN into the settlement and release the pressure AFTER it. With a
    negative rate, everything mirrors. That is a non-informational flow on a published
    timetable, which is the one kind of edge this project has found real (doc 02: momentum
    gated by a regime, or structural payment mechanisms). funding_spikes.py tested HOLDING
    through spikes; nobody here has tested the hours around the timestamp.

    Literature: "Temporal Dynamics of Market Microstructure in Cryptocurrency Perpetual
    Futures" (IJFS 2026, 812 symbols, 26 venues) finds statistically significant but
    "economically modest" intraday patterns tied to settlement times. Modest is the risk.

TWO TRADES, BOTH ON THE TIMETABLE
    PRE  (capture): when the PREVIOUS settlement's rate was >= thr, short H hours before the
         next settlement, hold through it (receive that rate), cover at the settlement.
         Mirror for <= -thr. Selection uses only the previous rate - fully causal.
    POST (release): when the settlement just paid >= thr, go LONG at the settlement and hold
         H hours (the pressure lifting). Mirror for <= -thr. The rate is known at entry.
    12bp per round trip. Prices are hourly opens (the open of the bar starting at t is the
    price at t). A 24h quote-volume floor of $10M keeps out coins no one could trade.

    Control: the same window shapes centred 4 hours away from the settlement on 8h-interval
    coins, same coins, same days - so "prices drift down when funding is high" (which is
    funding_spikes.py's finding and says nothing about timing) cannot pass as a timing edge.

REGISTERED PREDICTIONS (before the first run)
    1. The shape is there gross: returns BEFORE a high-positive settlement are below the
       control, and AFTER it above the control.
    2. It is small: for thr 0.03-0.1%/8h the gross effect is a fraction of the rate, i.e. a
       few bp - under the 12bp cost - so every net cell at those thresholds is negative.
    3. Only the extreme bucket (>= 0.3%/8h) clears costs, and only in 2021 / on thin coins,
       the same fate as funding_spikes.py. Expected verdict: DEAD.

    python -m backtest.settlement_timing
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PERPS = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "perps"
FEE = 12 / 1e4
VOL_FLOOR = 10e6
H_PRE, H_POST = (1, 2), (1, 2, 4)
THR = (0.0003, 0.001, 0.003)
HOUR = 3600 * 10**9


def coin_events(sym):
    f1 = PERPS / f"{sym}_1h.csv.gz"; ff = PERPS / f"{sym}_funding.csv.gz"
    if not (f1.exists() and ff.exists()):
        return None
    h = pd.read_csv(f1, usecols=["time", "open", "qvol"])
    fu = pd.read_csv(ff)
    if len(h) < 500 or len(fu) < 20:
        return None
    # force ns: pandas 3 parses these strings at SECOND resolution, and an int64 of that
    # against a nanosecond HOUR matches the wrong bars (first run of this file: dates in 1970)
    t = pd.to_datetime(h["time"]).dt.floor("h").astype("datetime64[ns]").astype("int64").to_numpy()
    o = h["open"].to_numpy(float)
    vol24 = pd.Series(h["qvol"].to_numpy(float)).rolling(24).sum().shift(1).to_numpy()
    s = pd.to_datetime(fu["time"]).dt.floor("h").astype("datetime64[ns]").astype("int64").to_numpy()
    r = fu["rate"].to_numpy(float)
    keep = np.r_[True, np.diff(s) > 0]
    s, r = s[keep], r[keep]
    gap = np.r_[np.nan, np.diff(s) / HOUR]

    def px(tt):
        k = np.searchsorted(t, tt)
        ok = (k < len(t)) & (t[np.minimum(k, len(t) - 1)] == tt)
        out = np.full(len(tt), np.nan)
        out[ok] = o[k[ok]]
        return out

    k0 = np.searchsorted(t, s)
    ok = (k0 < len(t))
    v = np.full(len(s), np.nan)
    v[ok] = vol24[np.minimum(k0[ok], len(t) - 1)]
    d = dict(sym=sym, t=s, r=r, r_prev=np.r_[np.nan, r[:-1]], gap=gap, vol24=v,
             p0=px(s))
    for H in (1, 2, 4):
        d[f"pm{H}"] = px(s - H * HOUR)
        d[f"pp{H}"] = px(s + H * HOUR)
        # control: the same shapes centred 4h earlier (mid-interval on 8h coins)
        d[f"cm{H}"] = px(s - (4 + H) * HOUR)
        d[f"c0{H}"] = px(s - 4 * HOUR)
        d[f"cp{H}"] = px(s - (4 - H) * HOUR)
    return pd.DataFrame(d)


def load_all():
    cache = PERPS.parent / "settlement_events.pkl.gz"
    if cache.exists():
        return pd.read_pickle(cache)
    syms = sorted(Path(f).name[:-len("_1h.csv.gz")] for f in glob.glob(str(PERPS / "*_1h.csv.gz")))
    parts = [x for x in (coin_events(s) for s in syms) if x is not None]
    E = pd.concat(parts, ignore_index=True)
    E.to_pickle(cache)
    return E


def month_boot_t(x, months, reps=2000, seed=3):
    x = np.asarray(x, float); m = np.asarray(months)
    if len(x) < 30:
        return np.nan
    um, inv = np.unique(m, return_inverse=True)
    sums = np.bincount(inv, weights=x, minlength=len(um))
    cnts = np.bincount(inv, minlength=len(um))
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(um), size=(reps, len(um)))
    bs = sums[pick].sum(1) / np.maximum(cnts[pick].sum(1), 1)
    se = bs.std()
    return float(x.mean() / se) if se > 0 else np.nan


def main():
    E = load_all()
    E = E[(E.vol24 >= VOL_FLOOR) & np.isfinite(E.p0)].copy()
    E["dt"] = pd.to_datetime(E.t, unit="ns")
    E["month"] = E.dt.dt.to_period("M").astype(str)
    cut = E.dt.quantile(0.6)
    print(f"{len(E):,} settlements with >= ${VOL_FLOOR/1e6:.0f}M 24h volume on "
          f"{E.sym.nunique()} perps, {E.dt.min():%Y-%m} .. {E.dt.max():%Y-%m}; "
          f"tune < {cut:%Y-%m-%d} <= holdout\n")

    # ---- 1. the SHAPE, gross, against the mid-interval control (8h coins only) -----
    G = E[E.gap == 8].copy()
    print("1. GROSS SHAPE on 8h-interval settlements, bp (settlement window minus control)")
    print(f"  {'rate bucket':<16}{'n':>9}{'pre 2h':>9}{'ctrl':>8}{'excess':>8}"
          f"{'post 2h':>9}{'ctrl':>8}{'excess':>8}")
    edges = [-np.inf, -0.003, -0.001, -0.0003, 0.0003, 0.001, 0.003, np.inf]
    labs = ["<= -0.30%", "-0.30..-0.10%", "-0.10..-0.03%", "-0.03..+0.03%",
            "+0.03..+0.10%", "+0.10..+0.30%", ">= +0.30%"]
    G["b"] = pd.cut(G.r, edges, labels=labs)
    for b, g in G.groupby("b", observed=True):
        pre = (g.p0 / g.pm2 - 1) * 1e4; cpre = (g.c02 / g.cm2 - 1) * 1e4
        post = (g.pp2 / g.p0 - 1) * 1e4; cpost = (g.cp2 / g.c02 - 1) * 1e4
        print(f"  {b:<16}{len(g):>9,}{pre.mean():>+9.1f}{cpre.mean():>+8.1f}"
              f"{(pre - cpre).mean():>+8.1f}{post.mean():>+9.1f}{cpost.mean():>+8.1f}"
              f"{(post - cpost).mean():>+8.1f}")

    # ---- 2. the TRADES, net, every interval ----------------------------------------
    print("\n2. NET TRADES (12bp, funding received/paid where held), bp per trade")
    print(f"  {'trade':<30}{'thr':>7}{'n':>8}{'TUNE':>8}{'t':>6}{'HOLD':>8}{'t':>6}"
          f"{'win%':>6}  by year (mean bp)")
    for thr in THR:
        rows = []
        for H in H_PRE:
            for sgn, lab in ((1, "short"), (-1, "long")):
                sel = (E.r_prev >= thr) if sgn == 1 else (E.r_prev <= -thr)
                g = E[sel & np.isfinite(E[f"pm{H}"])]
                ret = g.p0 / g[f"pm{H}"] - 1
                net = -sgn * ret + sgn * g.r - FEE        # short receives +r; long receives -r
                rows.append((f"PRE {lab} {H}h into settlement", g, net))
        for H in H_POST:
            for sgn, lab in ((1, "long"), (-1, "short")):
                sel = (E.r >= thr) if sgn == 1 else (E.r <= -thr)
                g = E[sel & np.isfinite(E[f"pp{H}"])]
                ret = g[f"pp{H}"] / g.p0 - 1
                net = sgn * ret - FEE
                rows.append((f"POST {lab} {H}h after", g, net))
        for lab, g, net in rows:
            if len(g) < 30:
                continue
            tu = (g.dt < cut).to_numpy(); ho = ~tu
            nb = net.to_numpy() * 1e4
            yr = pd.Series(nb, index=g.dt.dt.year.to_numpy()).groupby(level=0).mean()
            print(f"  {lab:<30}{thr*100:>6.2f}%{len(g):>8,}{nb[tu].mean() if tu.any() else np.nan:>+8.1f}"
                  f"{month_boot_t(nb[tu], g.month.to_numpy()[tu]):>+6.1f}"
                  f"{nb[ho].mean() if ho.any() else np.nan:>+8.1f}"
                  f"{month_boot_t(nb[ho], g.month.to_numpy()[ho]):>+6.1f}"
                  f"{(nb > 0).mean()*100:>6.0f}  " +
                  " ".join(f"{y % 100:02d}:{v:+.0f}" for y, v in yr.items()))
        print()


if __name__ == "__main__":
    main()

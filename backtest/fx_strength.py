"""A CURRENCY-STRENGTH METER, TRADED - and volume as the confirmation (the user's idea, 2026-10-06).

THE IDEA, in the user's words: "check volume rising or not in different markets, the historical relationships between
different currencies, and predict the move from it." The graveyard holds both halves separately and both died (VSA
volume absorption and the volume-surge filter ran BACKWARDS, doc 02 / doc 05; NASDAQ-gold pairs, crypto pairs, DXY->BTC,
intraday cross-market leads all failed). Never tested: the FX trader's own tool - a strength meter across the 8 majors.

HOW
    Seven USD pairs from the Exness MT5 cache (EURUSD, GBPUSD, AUDUSD, NZDUSD, USDJPY, USDCAD, USDCHF; hourly,
    2020-03 -> 2026-09, server clock = UTC). Each currency's log value in USD; its STRENGTH over the last N hours is
    its return minus the average of all 8. Every cross X/Y moves by r_X - r_Y, so the 7 pairs define all 28.
    Every H hours (non-overlapping trades):
        MOMENTUM   buy the strongest currency against the weakest, hold H hours
        REVERSAL   the opposite - the "catch-up" a lagging pair is supposed to make
    N = 1 / 4 / 24 / 120 hours; H = 1 / 4 / 24 hours; 12 cells x 2 directions = 24 tests, Holm over all.
    COSTS (pessimistic for Exness): 1.5 bp a round trip when USD is one side, 3.0 bp for a cross, plus 0.5 bp per
    night held (swap; its true sign depends on the rate gap, so it is charged as a cost).
    VOLUME: tick volume of the pairs in the signal's last N hours against their 20-day same-hour average; a signal is
    "volume-confirmed" if that ratio >= 1.5. MT5 tick volume counts quote updates, not size traded - a proxy, stated.
    Tune < first 60% of the hours <= holdout (CLAUDE.md rule 2).

REGISTERED PREDICTIONS (2026-10-06, before running)
    1. No cell is positive net of costs on BOTH halves with Holm p < 0.05.
    2. The best GROSS cell is momentum at N 24 / 120 and H 24 (FX trends over days), worth under 1 bp a trade after
       costs and failing one half.
    3. Every H = 1 cell loses after costs: costs exceed any hourly predictability.
    4. Volume confirmation does not lift the best cell by more than 1 bp a trade on both halves.

    python -m backtest.fx_strength
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "strategy_analysis" / "data"
PAIRS = {"EURUSDm": ("EUR", +1), "GBPUSDm": ("GBP", +1), "AUDUSDm": ("AUD", +1), "NZDUSDm": ("NZD", +1),
         "USDJPYm": ("JPY", -1), "USDCADm": ("CAD", -1), "USDCHFm": ("CHF", -1)}
CCY = ["USD", "EUR", "GBP", "AUD", "NZD", "JPY", "CAD", "CHF"]
NS, HS = (1, 4, 24, 120), (1, 4, 24)
COST_USD, COST_X, SWAP_NIGHT = 1.5, 3.0, 0.5


def load():
    px, vol = {}, {}
    for f, (c, sgn) in PAIRS.items():
        d = pd.DataFrame(json.load(open(DATA / f"{f}_1h_2400d.json")))
        t = pd.to_datetime(d.t, unit="ms")
        px[c] = pd.Series(sgn * np.log(d.c.to_numpy(float)), index=t)       # log value of c in USD
        vol[c] = pd.Series(d.v.to_numpy(float), index=t)
    P = pd.DataFrame(px).dropna()
    P["USD"] = 0.0
    V = pd.DataFrame(vol).reindex(P.index)
    V["USD"] = V.sum(axis=1)                                                 # USD sits in every pair
    return P[CCY], V[CCY]


def trades(P, V, N, H, sign):
    """Non-overlapping trades every H hours: long strongest / short weakest (sign +1) or the reverse (-1)."""
    a = P.to_numpy()
    v = V.to_numpy()
    idx = P.index
    # same-hour 20-day average of tick volume, per currency
    hour = idx.hour.to_numpy()
    vr = np.full(len(idx), np.nan)
    rows = []
    t = max(N, 24 * 20)
    while t + H < len(idx):
        if (idx[t + H] - idx[t]).total_seconds() > (H + 72) * 3600:        # skip trades across long gaps
            t += H
            continue
        r = a[t] - a[t - N]
        s = r - r.mean()
        hi, lo = int(np.argmax(s)), int(np.argmin(s))
        x, y = (hi, lo) if sign > 0 else (lo, hi)                            # long x, short y
        gross = ((a[t + H, x] - a[t + H, y]) - (a[t, x] - a[t, y])) * 1e4      # bp
        usd = CCY[x] == "USD" or CCY[y] == "USD"
        nights = len(set(idx[t:t + H + 1].date)) - 1
        cost = (COST_USD if usd else COST_X) + SWAP_NIGHT * nights
        # volume confirmation: the two currencies' tick volume over the last N hours vs their same-hour 20-day norm
        same = np.nonzero(hour[t - 24 * 20:t] == hour[t])[0] + (t - 24 * 20)
        base = v[same][:, [x, y]].mean(axis=0)
        recent = v[t - N + 1:t + 1][:, [x, y]].mean(axis=0)
        ratio = float(np.mean(recent / np.where(base > 0, base, np.nan)))
        rows.append((idx[t], gross, gross - cost, ratio))
        t += H
    return pd.DataFrame(rows, columns=["t", "gross", "net", "vratio"])


def stat(x):
    x = np.asarray(x, float)
    if len(x) < 20:
        return np.nan, np.nan, len(x)
    se = x.std(ddof=1) / np.sqrt(len(x))
    return x.mean(), x.mean() / se if se > 0 else np.nan, len(x)


def main():
    from scipy.stats import norm
    P, V = load()
    cut = P.index[int(len(P) * 0.6)]
    print(f"8 currencies from 7 USD pairs, hourly {P.index.min():%Y-%m-%d} .. {P.index.max():%Y-%m-%d}; "
          f"tune < {cut:%Y-%m-%d} <= holdout; costs {COST_USD}/{COST_X} bp + {SWAP_NIGHT} bp a night")
    res = []
    for N in NS:
        for H in HS:
            for sign, lab in ((+1, "momentum"), (-1, "reversal")):
                T = trades(P, V, N, H, sign)
                tu, ho = T[T.t < cut], T[T.t >= cut]
                g, _, _ = stat(T.gross)
                m, tt, n = stat(T.net)
                mt, ttt, _ = stat(tu.net)
                mh, tth, _ = stat(ho.net)
                vc = T[T.vratio >= 1.5]
                vct, vch = vc[vc.t < cut], vc[vc.t >= cut]
                res.append(dict(cell=f"{lab} N{N} H{H}", n=n, gross=g, net=m, t=tt, p=2 * norm.sf(abs(tt)),
                                tune=mt, hold=mh, t_tune=ttt, t_hold=tth,
                                v_n=len(vc), v_tune=stat(vct.net)[0] - mt, v_hold=stat(vch.net)[0] - mh))
    R = pd.DataFrame(res)
    order = R.p.sort_values().index
    R["holm"] = np.nan
    run = 0.0
    for i, ix in enumerate(order):
        run = max(run, min(1.0, R.p[ix] * (len(R) - i)))
        R.loc[ix, "holm"] = run
    out = [f"\n  {'cell':<22}{'trades':>7}{'gross bp':>9}{'net bp':>8}{'t':>7}{'Holm':>7}{'tune':>8}{'hold':>8}"
           f"{'  vol-confirmed: n, lift tune / hold (bp)':>42}"]
    for r in R.sort_values("net", ascending=False).itertuples():
        both = r.tune > 0 and r.hold > 0 and r.holm < 0.05
        out.append(f"  {r.cell:<22}{r.n:>7}{r.gross:>+9.2f}{r.net:>+8.2f}{r.t:>+7.2f}{r.holm:>7.3f}"
                   f"{r.tune:>+8.2f}{r.hold:>+8.2f}{r.v_n:>11}{r.v_tune:>+10.2f}{r.v_hold:>+9.2f}"
                   + ("   <- PASSES" if both else ""))
    passes = R[(R.tune > 0) & (R.hold > 0) & (R.holm < 0.05)]
    out.append(f"\n  cells positive on both halves after costs with Holm < 0.05: {len(passes)} of {len(R)}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "fx_strength.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()

"""TRADE DOGE, READ BTC - the "proper analysis" version, as a model, on 1-minute bars.

THE USER'S CLAIM (2026-10-06)
    "if we do it by proper analysis we won't lose; we trade DOGE but analyse BTC because it affects DOGE - there is
    an edge." scalp_1m.py tested one BTC->DOGE rule (btc_lead: short +1.6bp gross, a tenth of the fee). This tests
    the general version: everything both coins show at a closed minute, combined by a model fitted on the past,
    trading DOGE only when the PREDICTED move beats the fee.

WHAT IS MEASURED
    1. The structure: same-minute correlation of BTC and DOGE 1m returns, and BTC's last k minutes against DOGE's
       NEXT minutes (k = 1, 5, 15) - the lead that a 1m chart can see.
    2. A model. Features at the close of minute t (causal), for BTC and DOGE each:
         returns over 1, 3, 5, 15, 60, 240 minutes (scaled by 60-min volatility), RSI14, place in the 60-min range,
         60-min volatility; plus DOGE's lag behind BTC over 1, 5, 15 minutes (DOGE return - beta x BTC return,
         beta over 1440 minutes).
       Target: DOGE's return from the NEXT open to the close h minutes later, h = 5, 15, 60.
       Models: ridge regression and gradient-boosted trees (sklearn HistGradientBoosting).
       Fit on the first 75% of the tune half; the trade threshold (|predicted move| > c) is chosen on the last 25%
       of the tune half, per fee; the HOLDOUT (last 40%, from 2024-10-19) is touched once.
    3. Trading on the holdout: DOGE in the predicted direction, held h minutes, one at a time, entry next open,
       exit at the close (no stop), 12bp or 4bp round trip. IC = correlation of prediction and outcome.
    4. Leverage 1-40x on 4,000 PKR, whole margin per trade; LIQUIDATION when the worst price inside the hold
       moves 1/lev - 0.5% against the entry (DOGE's own 1m highs and lows).

REGISTERED BEFORE THE RUN (2026-10-06)
    - Same-minute correlation 0.7-0.8. BTC last minute vs DOGE next minute: +0.01 to +0.05.
    - Holdout IC 0.01-0.05 at h = 5, smaller at 60. Best-threshold gross <= +5bp a trade.
    - Net at 12bp negative for every model x horizon; at 4bp at most 1 of 6 positive.
    - 30-40x: every one ruined on the holdout.

RESULT (2026-10-06, logs/btc_doge.txt; holdout 2024-10-19 .. 2026-08-31)
    - Same-minute corr 0.638 (predicted 0.7-0.8: WRONG, lower). BTC's last minute vs DOGE's next minute +0.019
      (right); longer lags are slightly NEGATIVE (-0.010 to -0.015 at 5-15 min).
    - The models DO see something on unseen data: holdout IC +0.012 to +0.046, right direction 50.7-57.4%, gross
      +3.7 to +10.8bp a trade (predicted <= +5bp: WRONG for three of six; and IC is not smaller at 60 min).
    - Taker 12bp: all 6 lose (-1.2 to -8.3bp a trade). Right.
    - Maker 4bp (every limit order filled, no adverse selection - an upper bound): 5 of 6 positive, +0.3 to +6.8bp,
      NONE significant (t +0.1 to +1.8). Predicted at most 1 of 6 positive: WRONG - the edge before fees is a little
      bigger than registered, though still not distinguishable from zero after fees.
    - Leverage: every model x fee is wiped out at 5x and above, including the positive ones (registered: 30-40x;
      it is worse). The best one (ridge, 60 min, maker: +6.8bp, 2.3 trades a day, 4,000 -> 9,392 PKR at 1x) has a
      holdout Kelly of 2.6x, and ONE hold - 2025-10-10 20:53 UTC, DOGE 0.228 -> 0.084 (-63%) inside the hour on
      Binance's own 1m bars, verified - liquidates it at 2x and above.
    Reading: BTC does carry a little information about DOGE's next 5-60 minutes - the user was right about that.
    It is worth +4 to +11bp a trade before fees, which taker fees more than erase, and it cannot carry leverage:
    the price path of one crash hour decides 2x+, not the average edge.

    python -m backtest.btc_doge
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import odds_now as on  # noqa: E402
from backtest.scalp_1m import load  # noqa: E402

LOG = ROOT / "logs" / "btc_doge.txt"
HS = (5, 15, 60)
FEES = {"taker 12bp": 0.0012, "maker 4bp": 0.0004}
CS = [0.0002, 0.0004, 0.0006, 0.0008, 0.0012, 0.0016, 0.0024, 0.0032, 0.0048]
LEVS = (1, 5, 10, 20, 30, 40)
START_PKR = 4000.0
MAINT = 0.005
LOOKBACK = 1440 + 240


def roll_std(x, n):
    return pd.Series(x).rolling(n).std().to_numpy()


def build():
    b, d = load("BTCUSDT"), load("DOGEUSDT")
    return make(d.merge(b, on="time", suffixes=("_d", "_b"), how="inner"))


def make(m):
    """Features, targets and the validity mask from aligned DOGE (_d) and BTC (_b) 1m bars."""
    t = m.time.to_numpy("datetime64[ns]").astype(np.int64)
    X, names = [], []
    rets = {}
    for s in ("b", "d"):
        o, h, l, c = (m[f"{k}_{s}"].to_numpy(float) for k in "ohlc")
        lc = np.log(c)
        r1 = np.r_[np.nan, np.diff(lc)]
        vol = roll_std(r1, 60)
        rets[s] = r1
        for k in (1, 3, 5, 15, 60, 240):
            X.append((lc - np.r_[np.full(k, np.nan), lc[:-k]]) / (vol * np.sqrt(k)))
            names.append(f"{s}_r{k}")
        X.append(on.features(o, h, l, c)["rsi"])
        names.append(f"{s}_rsi")
        hi, lo = pd.Series(h).rolling(60).max().to_numpy(), pd.Series(l).rolling(60).min().to_numpy()
        X.append((c - lo) / (hi - lo))
        names.append(f"{s}_loc60")
        X.append(vol)
        names.append(f"{s}_vol60")
    rb, rd = rets["b"], rets["d"]
    beta = (pd.Series(rb).rolling(1440).cov(pd.Series(rd)) / pd.Series(rb).rolling(1440).var()).to_numpy()
    lcb, lcd = np.log(m.c_b.to_numpy(float)), np.log(m.c_d.to_numpy(float))
    vd = roll_std(rd, 60)
    for k in (1, 5, 15):
        db = lcb - np.r_[np.full(k, np.nan), lcb[:-k]]
        dd = lcd - np.r_[np.full(k, np.nan), lcd[:-k]]
        X.append((dd - beta * db) / (vd * np.sqrt(k)))
        names.append(f"lag{k}")
    X = np.column_stack(X).astype(np.float32)

    od, hd, ld, cd = (m[f"{k}_d"].to_numpy(float) for k in "ohlc")
    n = len(m)
    Y = {}
    for h in HS:
        y = np.full(n, np.nan)
        y[:n - h] = cd[h:] / od[1:n - h + 1] - 1               # entry o[t+1], exit c[t+h]
        Y[h] = y
    bad = np.r_[False, np.diff(t) != 60_000_000_000]
    cb = np.r_[0, np.cumsum(bad)]
    i = np.arange(n)
    lo_i, hi_i = np.maximum(i - LOOKBACK + 1, 0), np.minimum(i + max(HS) + 1, n - 1)
    ok = ((cb[hi_i + 1] - cb[lo_i]) == 0) & np.isfinite(X).all(1)
    ok[:LOOKBACK] = False
    return m, X, names, Y, ok, (rb, rd), (od, hd, ld)


def take(idx, h):
    """Non-overlapping: after a trade at i (exit at close i+h) the next signal must be >= i + h."""
    keep, free = [], -1
    for i in idx:
        if i >= free:
            keep.append(i)
            free = i + h
    return np.array(keep, np.int64)


def mae(idx, side, h, od, hd, ld):
    """Worst adverse move inside each hold, as a fraction of the entry price."""
    out = np.empty(len(idx))
    for j, (i, s) in enumerate(zip(idx, side)):
        e = od[i + 1]
        out[j] = (e - ld[i + 1:i + h + 1].min()) / e if s > 0 else (hd[i + 1:i + h + 1].max() - e) / e
    return out


def lev_path(net, adverse, lev):
    eq, ruin = START_PKR, None
    liq = 1.0 / lev - MAINT
    for j, (x, a) in enumerate(zip(net, adverse)):
        eq = 0.0 if a >= liq else eq * max(0.0, 1 + lev * x)
        if ruin is None and eq < 0.1 * START_PKR:
            ruin = j + 1
        if eq <= 0:
            break
    return eq, ruin


def main():
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    t0 = time.time()
    m, X, names, Y, ok, (rb, rd), (od, hd, ld) = build()
    n = len(m)
    times = m.time.to_numpy()
    split = np.sort(times)[int(n * 0.6)]
    is_tune = times < split
    fit_end = np.sort(times[is_tune])[int(is_tune.sum() * 0.75)]
    lines = [f"backtest/btc_doge.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; {n:,} aligned minutes "
             f"{pd.Timestamp(times[0]):%Y-%m-%d} .. {pd.Timestamp(times[-1]):%Y-%m-%d}; fit < "
             f"{pd.Timestamp(fit_end):%Y-%m-%d} <= threshold choice < {pd.Timestamp(split):%Y-%m-%d} <= HOLDOUT", ""]

    f = np.isfinite(rb) & np.isfinite(rd)
    lines.append(f"1. STRUCTURE (all minutes): same-minute corr(BTC 1m, DOGE 1m) = "
                 f"{np.corrcoef(rb[f], rd[f])[0, 1]:+.3f}")
    lcb, lcd = np.log(m.c_b.to_numpy(float)), np.log(m.c_d.to_numpy(float))
    for k in (1, 5, 15):
        pb = lcb - np.r_[np.full(k, np.nan), lcb[:-k]]
        for hh in (1, 5, 15):
            fwd = np.r_[lcd[hh:] - lcd[:-hh], np.full(hh, np.nan)]
            g = np.isfinite(pb) & np.isfinite(fwd)
            lines.append(f"   BTC's last {k:>2} min vs DOGE's next {hh:>2} min: corr {np.corrcoef(pb[g], fwd[g])[0, 1]:+.4f}")

    lines.append("\n2-4. MODEL -> TRADES ON THE HOLDOUT (DOGE, held h minutes, one at a time):")
    fit_m = ok & (times < fit_end)
    val_m = ok & is_tune & (times >= fit_end)
    hold_m = ok & ~is_tune
    for h in HS:
        y = Y[h]
        fm, vm, hm = fit_m & np.isfinite(y), val_m & np.isfinite(y), hold_m & np.isfinite(y)
        rng = np.random.default_rng(h)
        fit_idx = np.flatnonzero(fm)
        sub = rng.choice(fit_idx, size=min(len(fit_idx), 600_000), replace=False)
        sub.sort()
        models = {
            "ridge": make_pipeline(StandardScaler(), Ridge(alpha=10.0)),
            "trees": HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_leaf_nodes=31,
                                                   min_samples_leaf=500, random_state=0),
        }
        for mname, model in models.items():
            model.fit(X[sub], y[sub])
            pred = np.full(n, np.nan, np.float32)
            rows = np.flatnonzero(ok)                                # predict only where every feature exists
            for a in range(0, len(rows), 500_000):
                r = rows[a:a + 500_000]
                pred[r] = model.predict(X[r])
            ic_v = np.corrcoef(pred[vm], y[vm])[0, 1]
            ic_h = np.corrcoef(pred[hm], y[hm])[0, 1]
            lines.append(f"\n  h={h:>2}m {mname:5}: IC validation {ic_v:+.4f}, HOLDOUT {ic_h:+.4f}")
            for fee_name, fee in FEES.items():
                best = None
                for c in CS:                                         # threshold chosen on validation only
                    idx = take(np.flatnonzero(vm & (np.abs(pred) > c)), h)
                    if len(idx) < 200:
                        continue
                    net = np.sign(pred[idx]) * y[idx] - fee
                    if best is None or net.mean() > best[1]:
                        best = (c, net.mean(), len(idx))
                if best is None:
                    lines.append(f"    [{fee_name}] fewer than 200 validation trades at every threshold")
                    continue
                c = best[0]
                idx = take(np.flatnonzero(hm & (np.abs(pred) > c)), h)
                side = np.sign(pred[idx])
                gross = side * y[idx]
                net = gross - fee
                days = times[idx].astype("datetime64[D]")
                s = pd.Series(net - net.mean()).groupby(days).sum().to_numpy()
                se = np.sqrt((s ** 2).sum() * len(s) / max(len(s) - 1, 1)) / len(net)
                lines.append(f"    [{fee_name}] threshold |pred| > {c * 1e4:.0f}bp (validation net "
                             f"{best[1] * 1e4:+.2f}bp, n {best[2]}) -> HOLDOUT n {len(idx)}, right direction "
                             f"{(gross > 0).mean():.1%}, gross {gross.mean() * 1e4:+.2f}bp, NET {net.mean() * 1e4:+.2f}bp "
                             f"a trade (t {net.mean() / se:+.1f})")
                adv = mae(idx, side, h, od, hd, ld)
                cells = []
                for lev in LEVS:
                    fin, ruin = lev_path(net, adv, lev)
                    cells.append(f"{lev}x {fin:,.0f}" + (f" (gone after {ruin})" if ruin else ""))
                lines.append("      4,000 PKR on the holdout: " + " | ".join(cells))
        print(f"  h={h} done ({time.time() - t0:.0f}s)", flush=True)
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")
    print(f"\n-> {LOG}")


if __name__ == "__main__":
    main()

"""SECONDS-SCALE NASDAQ: CAN THE NEXT 5-60 SECONDS BE PREDICTED BY MORE THAN EXNESS'S SPREAD? (2026-10-12)

The DOGE order-book recording (backtest/doge_book.py) found REAL short-horizon information - book imbalance predicted the
next 10-60 s at IC +0.20..+0.28 on both halves - that was worth only ~1-2bp a move, under Bitget's fee (maker 4bp, taker
12bp a round trip). USTECm on Exness costs only the spread, ~0.4bp in the cash session. So the question the DOGE result
leaves open is whether a 1-2bp predictable move exists on NASDAQ, where it WOULD pay. Exness gives no order book, so the
inputs are what the tick stream itself carries:
    r1 r5 r10 r30 r60 r300   the mid's change over the last k seconds (bp)
    imb10                    up-ticks minus down-ticks of the mid over the last 10 s, over their sum (tick imbalance)
    rate                     ticks in the last 10 s over a tenth-of-300-s average (activity surge)
    sp                       the spread now (bp)
DATA    strategy_analysis/data/ustec_tick_days.pkl (his_microstructure.day_ticks): every USTECm tick 09:30-19:30 ET on
        181 days, 2026-01-02 .. 2026-09-14. Samples every 10 s, 09:35-15:55 ET (the cash session).
TARGET  the mid's move from t + LAT to t + LAT + h, h = 5 / 10 / 30 / 60 s, LAT = 0.5 s (order latency from Pakistan;
        1 s and 2 s also reported for the trade test).
SPLIT   first 60% of days = tune, the rest = holdout.
TESTS   1. IC (Spearman) of each feature with each horizon: mean of the daily ICs, t across days, each half.
        2. A ridge model fit on the tune days; on the holdout, trade only when |prediction| is in the top 1% / 5% of the
           tune days' |prediction|, one position at a time, in the predicted direction, held h seconds; pay half the
           spread at entry and half at exit. Net bp a trade, t by day.

REGISTERED BEFORE THE RUN (2026-10-12)
    E1  The mid-only features carry far less than DOGE's book: |mean daily IC| < 0.05 for every feature and horizon,
        on both halves.
    E2  The strongest effect is short-term REVERSAL at 5-10 s (quote noise): r1 / r5 IC between -0.02 and -0.06.
    E3  On the holdout, the top-1% trades' gross move is under the spread at every horizon: net negative at LAT 0.5 s.

RESULT (2026-10-11 20:46 UTC, logs/ustec_seconds.txt; 181 days, 412,680 samples, holdout from 2026-06-04)
    - Cash-session spread 0.82bp round trip (90th 1.16); the mid's median |move| is 0.60bp in 5 s, 2.16bp in 60 s.
    - E2 WRONG in size, right in kind: every price feature REVERSES on both halves (r10 vs the next 5 s -0.033 / -0.018,
      t -10 / -5), but the ICs are -0.007 to -0.033 - a tenth of DOGE's book (+0.20..+0.28).
    - E1 WRONG because of one feature: the SPREAD has IC +0.03..+0.11 on both halves. Section 3 (added after the first
      run) shows it is not money: when the spread is in its top 10% the mid, the ask and the bid all move -0.13..+0.03bp
      on average - more small up-moves than down, smaller than the down-moves - while a trade there pays 1.25-1.40bp.
    - E3 RIGHT: a ridge model fit on the tune days predicts the holdout (IC +0.010..+0.025, t +3..+5), and its top-1% and
      top-5% trades move +0.00..+0.14bp gross against a ~0.8bp spread: net -0.73..-0.92bp a trade, t -4 to -10, at 0.5,
      1 and 2 s latency alike.
    Reading: the NASDAQ quote has real seconds-scale information (short-term reversal), worth about a tenth of a basis
    point - under a fifth of even Exness's spread. With nq_leadlag.py (2026-10-04: no lag to the CME futures), the
    seconds scale on Exness is closed.

    python -m backtest.ustec_seconds
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
LOG = ROOT / "logs" / "ustec_seconds.txt"
HZ = (5, 10, 30, 60)
LATS = (0.5, 1.0, 2.0)
FEATS = ["r1", "r5", "r10", "r30", "r60", "r300", "imb10", "rate", "sp"]
T0, T1, STEP = 5 * 60, 6 * 3600 + 25 * 60, 10.0          # 09:35 .. 15:55 ET, every 10 s
TUNE = 0.60


def at(ts, x, t):
    """value of the last tick at or before t (t an array)."""
    i = np.searchsorted(ts, t, side="right") - 1
    return x[np.clip(i, 0, len(x) - 1)], i


def day_frame(ts, mid, spr):
    g = np.arange(T0, T1, STEP)
    m0, i0 = at(ts, mid, g)
    ref = m0
    f = {}
    for k in (1, 5, 10, 30, 60, 300):
        mk, _ = at(ts, mid, g - k)
        f[f"r{k}"] = (m0 / mk - 1) * 1e4
    sgn = np.sign(np.diff(mid))
    cu, cd = np.r_[0, np.cumsum(sgn > 0)], np.r_[0, np.cumsum(sgn < 0)]
    j10 = np.searchsorted(ts, g - 10, side="right") - 1
    j300 = np.searchsorted(ts, g - 300, side="right") - 1
    j10, j300 = np.clip(j10, 0, None), np.clip(j300, 0, None)
    up, dn = cu[np.clip(i0, 0, None)] - cu[j10], cd[np.clip(i0, 0, None)] - cd[j10]
    f["imb10"] = np.where(up + dn > 0, (up - dn) / np.maximum(up + dn, 1), 0.0)
    f["rate"] = (i0 - j10) / np.maximum((i0 - j300) / 30.0, 1e-9)
    s0, _ = at(ts, spr, g)
    f["sp"] = s0 / ref * 1e4
    for lat in LATS:
        me, _ = at(ts, mid, g + lat)
        se_, _ = at(ts, spr, g + lat)
        f[f"spe{lat}"] = se_ / ref * 1e4
        for h in HZ:
            mx, _ = at(ts, mid, g + lat + h)
            sx, _ = at(ts, spr, g + lat + h)
            f[f"y{h}_{lat}"] = (mx / me - 1) * 1e4
            f[f"spx{h}_{lat}"] = sx / ref * 1e4
    f["t"] = g
    return pd.DataFrame(f)


def spearman(a, b):
    ra, rb = pd.Series(a).rank().to_numpy(), pd.Series(b).rank().to_numpy()
    if ra.std() == 0 or rb.std() == 0:
        return np.nan
    return float(np.corrcoef(ra, rb)[0, 1])


def trades(D, pred, thr, h, lat):
    """one position at a time: (day, gross bp, net bp) for samples with |pred| >= thr."""
    out = []
    sel = D[np.abs(pred[D.index]) >= thr]
    for d, g in sel.groupby("day", sort=True):
        p = pred[g.index]
        free = -1.0
        for i, t_, pv in zip(g.index, g.t.to_numpy(), p):
            if t_ < free:
                continue
            s = np.sign(pv)
            gross = s * D.at[i, f"y{h}_{lat}"]
            cost = (D.at[i, f"spe{lat}"] + D.at[i, f"spx{h}_{lat}"]) / 2
            out.append((d, gross, gross - cost))
            free = t_ + lat + h
    return pd.DataFrame(out, columns=["day", "gross", "net"])


def tday(x, day):
    s = pd.Series(x).groupby(np.asarray(day)).sum()
    return s.mean() / (s.std(ddof=1) / np.sqrt(len(s))) if len(s) > 2 and s.std(ddof=1) > 0 else np.nan


def main():
    cache = pickle.loads(TICKS.read_bytes())
    days = sorted(d for d, v in cache.items() if v is not None)
    frames = []
    for d in days:
        ts, mid, spr = cache[d]
        if len(ts) < 10_000:
            continue
        fr = day_frame(ts, mid, spr)
        fr["day"] = d
        frames.append(fr)
    D = pd.concat(frames, ignore_index=True)
    D = D[np.isfinite(D[FEATS]).all(axis=1)].reset_index(drop=True)
    ud = sorted(D.day.unique())
    split = ud[int(len(ud) * TUNE)]
    tu = D.day < split
    lines = [f"backtest/ustec_seconds.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; USTECm ticks, {len(ud)} days "
             f"{ud[0]:%Y-%m-%d} .. {ud[-1]:%Y-%m-%d}, samples every 10 s 09:35-15:55 ET: {len(D):,}; holdout from {split:%Y-%m-%d}",
             f"spread (bp, round trip): median {D.sp.median():.2f}, 90th {D.sp.quantile(0.9):.2f}; "
             f"|move| median (bp) " + ", ".join(f"{h}s {D[f'y{h}_0.5'].abs().median():.2f}" for h in HZ), ""]
    lines.append("1. IC: mean of daily Spearman ICs (t across days), tune | holdout, LAT 0.5 s")
    lines.append(f"  {'feature':7}" + "".join(f"{f'{h}s tune':>16}{f'{h}s hold':>16}" for h in HZ))
    ic = {}
    for f in FEATS:
        row = f"  {f:7}"
        for h in HZ:
            for nm, m in (("tune", tu), ("hold", ~tu)):
                v = D[m].groupby("day").apply(lambda g: spearman(g[f], g[f"y{h}_0.5"]), include_groups=False).dropna()
                mu, t = v.mean(), v.mean() / (v.std(ddof=1) / np.sqrt(len(v)))
                ic[(f, h, nm)] = (mu, t)
                row += f"{mu:+9.3f} ({t:+5.1f})"
        lines.append(row)
    lines.append("")
    # 2. ridge model fit on the tune days, traded on the holdout
    X = D[FEATS].to_numpy(float)
    mu_, sd_ = X[tu.to_numpy()].mean(0), X[tu.to_numpy()].std(0)
    Z = (X - mu_) / np.where(sd_ > 0, sd_, 1)
    Z = np.clip(Z, -6, 6)
    lines.append("2. RIDGE on tune days -> holdout trades (one at a time, held h s, half the spread each side), bp a trade")
    best = []
    for h in HZ:
        y = D[f"y{h}_0.5"].to_numpy()
        A = Z[tu.to_numpy()]
        w = np.linalg.solve(A.T @ A + 10.0 * len(A) ** 0.5 * np.eye(A.shape[1]), A.T @ y[tu.to_numpy()])
        pred = pd.Series(Z @ w, index=D.index)
        icp = D[~tu].assign(p=pred[~tu]).groupby("day").apply(lambda g: spearman(g.p, g[f"y{h}_0.5"]), include_groups=False)
        lines.append(f"  h {h:2}s: holdout IC of the model {icp.mean():+.3f} (t {icp.mean() / (icp.std(ddof=1) / np.sqrt(len(icp))):+.1f}); "
                     f"weights " + " ".join(f"{f}{v:+.2f}" for f, v in zip(FEATS, w)))
        for q in (0.99, 0.95):
            thr = np.quantile(np.abs(pred[tu]), q)
            for lat in LATS:
                H = D[~tu].copy()
                p_ = pred.copy()
                tr = trades(H, p_, thr, h, lat)
                if len(tr) < 20:
                    lines.append(f"     top {100 - q * 100:.0f}% LAT {lat:.1f}s: {len(tr)} trades")
                    continue
                tg, tn = tday(tr.gross, tr.day), tday(tr.net, tr.day)
                best.append((h, q, lat, tr.net.mean()))
                lines.append(f"     top {100 - q * 100:.0f}% LAT {lat:.1f}s: {len(tr):6} trades | gross {tr.gross.mean():+.2f}bp (t {tg:+.1f}) | "
                             f"net {tr.net.mean():+.2f}bp (t {tn:+.1f}) | won {np.mean(tr.net > 0) * 100:.0f}%")
    lines.append("")
    # 3. the spread's IC: a real move, or the quote's own bid coming back after a widening? (added after the first run)
    lines.append("3. THE SPREAD'S IC, holdout: when the spread is in its top 10%, what does each side of the quote do? (bp, LAT 0.5 s)")
    H = D[~tu]
    hi = H.sp >= H.sp.quantile(0.9)
    for h in HZ:
        for nm, g in (("top-10% spread", H[hi]), ("the rest", H[~hi])):
            y, dsp = g[f"y{h}_0.5"], (g[f"spx{h}_0.5"] - g["spe0.5"]) / 2
            lines.append(f"  {h:2}s {nm:15}: mid {y.mean():+.2f} | ask {(y + dsp).mean():+.2f} | bid {(y - dsp).mean():+.2f} | "
                         f"a long, bid out - ask in {(y - (g['spe0.5'] + g[f'spx{h}_0.5']) / 2).mean():+.2f}")
    lines.append("")
    big = max(abs(v[0]) for k, v in ic.items())
    lines.append(f"E1 (|IC| < 0.05 everywhere): largest |IC| {big:.3f} -> {'RIGHT' if big < 0.05 else 'WRONG'}")
    rev = [ic[(f, h, nm)][0] for f in ("r1", "r5") for h in (5, 10) for nm in ("tune", "hold")]
    lines.append(f"E2 (r1/r5 reversal at 5-10 s, IC -0.02..-0.06): " + ", ".join(f"{v:+.3f}" for v in rev)
                 + f" -> {'RIGHT' if all(-0.06 <= v <= -0.02 for v in rev) else 'WRONG'}")
    e3 = [b for b in best if b[1] == 0.99 and b[2] == 0.5]
    lines.append(f"E3 (top-1% trades net negative at LAT 0.5 s, every horizon): " + ", ".join(f"{b[0]}s {b[3]:+.2f}" for b in e3)
                 + f" -> {'RIGHT' if e3 and all(b[3] < 0 for b in e3) else 'WRONG'}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

"""MANY INDICATORS TOGETHER, DONE HONESTLY: A WALK-FORWARD CROSS-SECTIONAL MODEL ON THE PIT TOP-40 (2026-11-02)

The user's question after the candle tests: "some correlation of different indicators or patterns together". Combinations of a few
indicators were swept before (rsi_confluence ~2,000 configs, day_long 1,350 filters, tv_indicators, sweep_confluence), and sweeping is
where winners come from luck. This does the grown-up version once: ALL the standard indicators at the same time in a model that is
re-fitted only on the past, scored on dates it has never seen, against the best SINGLE indicator picked the same way.

DATA     the point-in-time top-40 perps (by the prior month's volume, dead coins in, stables and non-crypto dropped), UTC daily bars built
         from the 1h archive (a day counts only with all 24 hours), 2019-09 .. 2026-09.
FEATURES 32, each known at the day's close (tested by perturbing the future): returns over 1 / 3 / 7 / 14 / 30 / 60 days, RSI(14) and
         RSI(3), stochastic(14), Bollinger %b and width (20, 2), distance to the 20- and 50-day EMA, MACD histogram, ATR%, volatility
         ratio (5 / 20), volume z-score and 5 / 30-day volume change, the last candle's body, upper wick, lower wick and close
         location, distance to the 20- and 60-day high and the 20-day low, 7- and 30-day return relative to BTC, share of up days in
         10, best and worst daily return in 30. No funding, no sentiment, no news: price and volume only.
         Every feature is turned into its cross-sectional rank among that day's members (-0.5 .. +0.5), missing = 0.
TARGET   forward return of a coin entered at the NEXT open and left at the close H days after the signal (H = 1, 3, 7; a coin whose
         history ends inside the window is left at its last close), turned into its cross-sectional rank the same way.
MODELS   ridge (alpha 10) and gradient boosting (depth 3, 150 trees, learning rate 0.05, 200 rows per leaf), fixed settings, never tuned;
         SINGLE = the one feature whose mean daily rank correlation with the target is largest in absolute value on the training window,
         traded in its own direction. Re-fitted every calendar quarter from 2022-01, on rows whose whole forward window ends before the
         quarter starts (an embargo of H + 1 days); expanding window.
SCORES   out of sample 2022-01 .. 2026-09, tune half before 2024-08-29, holdout after. Per day: the rank correlation (IC) of the
         prediction with the realised return, and the SPREAD = mean return of the top fifth of the day's coins minus the bottom
         fifth. NET SPREAD = spread - 24bp (12bp round trip on both legs) - the long leg's funding (1bp / 8h; shorts receive nothing).
         Entries are non-overlapping: for each of the H entry-day alignments (weekday anchors!) the mean and t over its days are
         computed, and the cell reports the mean over alignments, the average t and the WORST alignment's mean.
PASS     a (model, H) cell passes if, on BOTH halves, net spread > 0 with t >= 2, its worst alignment is > 0, the IC has t >= 2, and
         Holm < 0.05 over the 6 primary cells (ridge and gradient boosting x 3 horizons; p from the weaker half).
PAIRED   combination minus the best single feature, same days, same rule: does putting everything together beat the best one?

REGISTERED BEFORE THE FIRST RUN (2026-11-02; my prior that any cell passes: under 10%)
  P1  No primary cell passes.
  P2  The mean out-of-sample IC of every primary cell is between -0.01 and +0.04, and ridge and gradient boosting differ by less
      than 0.015: the trees find no structure that the straight line misses.
  P3  The combination does not beat the best single feature: the paired t (combo - single, gross spread) is under 2 on at least one
      half in at least 5 of the 6 cells.
  P4  Every H = 1 cell has a NEGATIVE net spread on both halves (24bp of costs against a one-day edge).
  P5  The gross spread on the holdout is below the tune half's in at least 3 of the 6 cells.

    python -m backtest.indicator_model
"""
from __future__ import annotations

import sys
from math import sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import candle_scan as cs  # noqa: E402

LOG = ROOT / "logs" / "indicator_model.txt"
HORIZONS = (1, 3, 7)
D0 = np.datetime64("2019-09-01")
D1 = np.datetime64("2026-10-01")
FIRST_OOS = np.datetime64("2022-01-01")
CUT = np.datetime64("2024-08-29")
Q, MIN_NAMES, MIN_FEATS = 0.2, 15, 25
RIDGE_ALPHA = 10.0
COST_ROUND_TRIP = 2 * cs.FEE                     # both legs, 12bp each
FEATURES = ["ret1", "ret3", "ret7", "ret14", "ret30", "ret60", "rsi14", "rsi3", "stoch14", "bb_pctb", "bb_width", "ema_d20", "ema_d50",
            "macd_h", "atr_pct", "vol_ratio", "vol_z", "dvol_chg", "body", "upper_wick", "lower_wick", "close_loc", "dist_h20", "dist_l20",
            "dist_h60", "rel_btc7", "rel_btc30", "up_frac10", "max_ret30", "min_ret30", "dist_h20_x_ret7", "ret3_x_volz"]


# ---------------------------------------------------------------- panel

def build_panel():
    """(dates, coins, O, H, L, C, V, M): daily arrays (days x coins) on one global UTC grid."""
    from backtest.capitulation_wide import hourly
    from backtest.market_neutral import drop_non_crypto
    from backtest.wide_book import eligibility
    elig = drop_non_crypto(eligibility(40))
    coins = sorted(s for s in elig if elig[s] and s.endswith("USDT"))
    dates = np.arange(D0, D1)
    T, N = len(dates), len(coins)
    O, Hh, L, C, V = (np.full((T, N), np.nan) for _ in range(5))
    M = np.zeros((T, N), bool)
    gm = dates.astype("datetime64[M]")
    for j, sym in enumerate(coins):
        h = hourly(sym)
        if h is None:
            continue
        g = h.set_index("time").resample("1D")
        d = pd.DataFrame({"o": g["open"].first(), "h": g["high"].max(), "l": g["low"].min(), "c": g["close"].last(),
                          "v": g["qvol"].sum(), "n": g["close"].count()})
        d = d[d.n == 24]
        k = (d.index.values.astype("datetime64[D]") - D0).astype(int)
        ok = (k >= 0) & (k < T)
        for arr, col in ((O, "o"), (Hh, "h"), (L, "l"), (C, "c"), (V, "v")):
            arr[k[ok], j] = d[col].to_numpy(float)[ok]
        M[:, j] = np.isin(gm, np.array(sorted(elig[sym]), dtype="datetime64[M]"))
    return dates, coins, O, Hh, L, C, V, M


# ---------------------------------------------------------------- features

def _rsi(c, n):
    d = c.diff()
    au = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    ad = (-d).clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    with np.errstate(invalid="ignore", divide="ignore"):
        rsi = 100 - 100 / (1 + au / ad)
    return rsi.where(ad > 0, 100.0).where(au.notna() & ad.notna())


def feature_panels(O, H, L, C, V, btc):
    """{name: array (days x coins)}; row t uses the bars up to and including day t."""
    o, h, l, c, v = (pd.DataFrame(x) for x in (O, H, L, C, V))
    lr = np.log(c / c.shift(1))
    f = {}
    for k in (1, 3, 7, 14, 30, 60):
        f[f"ret{k}"] = np.log(c / c.shift(k))
    f["rsi14"], f["rsi3"] = _rsi(c, 14), _rsi(c, 3)
    hi14, lo14 = h.rolling(14).max(), l.rolling(14).min()
    f["stoch14"] = (c - lo14) / (hi14 - lo14)
    ma, sd = c.rolling(20).mean(), c.rolling(20).std()
    f["bb_pctb"] = (c - (ma - 2 * sd)) / (4 * sd)
    f["bb_width"] = 4 * sd / ma
    f["ema_d20"] = c / c.ewm(span=20, adjust=False, min_periods=20).mean() - 1
    f["ema_d50"] = c / c.ewm(span=50, adjust=False, min_periods=50).mean() - 1
    macd = c.ewm(span=12, adjust=False, min_periods=26).mean() - c.ewm(span=26, adjust=False, min_periods=26).mean()
    f["macd_h"] = (macd - macd.ewm(span=9, adjust=False, min_periods=9).mean()) / c
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()]).groupby(level=0).max()
    f["atr_pct"] = tr.rolling(14).mean() / c
    f["vol_ratio"] = lr.rolling(5).std() / lr.rolling(20).std()
    lv = np.log(v.where(v > 0))
    f["vol_z"] = (lv - lv.rolling(20).mean()) / lv.rolling(20).std()
    f["dvol_chg"] = np.log(v.rolling(5).mean() / v.rolling(30).mean())
    rng = (h - l).where(h > l)
    f["body"] = (c - o) / rng
    f["upper_wick"] = (h - pd.concat([o, c]).groupby(level=0).max()) / rng
    f["lower_wick"] = (pd.concat([o, c]).groupby(level=0).min() - l) / rng
    f["close_loc"] = (c - l) / rng
    f["dist_h20"] = c / h.rolling(20).max() - 1
    f["dist_l20"] = c / l.rolling(20).min() - 1
    f["dist_h60"] = c / h.rolling(60).max() - 1
    f["rel_btc7"] = f["ret7"].sub(f["ret7"].iloc[:, btc], axis=0)
    f["rel_btc30"] = f["ret30"].sub(f["ret30"].iloc[:, btc], axis=0)
    f["up_frac10"] = (lr > 0).astype(float).where(lr.notna()).rolling(10).mean()
    f["max_ret30"], f["min_ret30"] = lr.rolling(30).max(), lr.rolling(30).min()
    f["dist_h20_x_ret7"] = f["dist_h20"] * f["ret7"]
    f["ret3_x_volz"] = f["ret3"] * f["vol_z"]
    return {k: f[k].to_numpy(float) for k in FEATURES}


def xs_rank(X, mask):
    """Cross-sectional rank of each row among the masked entries, in [-0.5, +0.5]; entries outside the mask or missing stay NaN."""
    df = pd.DataFrame(np.where(mask, X, np.nan))
    r, n = df.rank(axis=1), df.count(axis=1)
    return ((r - 0.5).div(n.replace(0, np.nan), axis=0) - 0.5).to_numpy(float, copy=True)


def forward_returns(O, C, H):
    """F[t] = close(t+H) / open(t+1) - 1; a coin whose history ENDS inside the window is left at its last close."""
    T, N = O.shape
    Cf = C.copy()
    for j in range(N):
        fin = np.flatnonzero(np.isfinite(C[:, j]))
        if len(fin):
            Cf[fin[-1] + 1:, j] = C[fin[-1], j]
    F = np.full((T, N), np.nan)
    if T > H + 1:
        with np.errstate(invalid="ignore", divide="ignore"):
            F[:T - H] = Cf[H:] / O[1:T - H + 1] - 1
    return F


# ---------------------------------------------------------------- walk-forward

def train_cutoff(start, H):
    """Last entry-day index a model fitted for a block starting at `start` may train on: its whole forward window ends before `start`."""
    return start - H - 1


def make_blocks(dates, first_oos=FIRST_OOS, last=None):
    """Calendar-quarter blocks as (start, stop) index pairs from `first_oos`."""
    last = dates[-1] if last is None else last
    starts = np.arange(first_oos.astype("datetime64[M]"), last.astype("datetime64[M]") + 1, 3).astype("datetime64[D]")
    idx = np.searchsorted(dates, starts)
    return [(int(a), int(b)) for a, b in zip(idx, list(idx[1:]) + [len(dates)]) if b > a]


def day_ics(X, Y, ok):
    """Mean daily Pearson correlation of each feature rank with the target rank over the masked rows, one value per feature."""
    T, N, nf = X.shape
    tot, cnt = np.zeros(nf), 0
    for t in range(T):
        m = ok[t]
        if m.sum() < MIN_NAMES:
            continue
        x, y = X[t][m].astype(float), Y[t][m].astype(float)
        x, y = x - x.mean(0), y - y.mean()
        den = np.sqrt((x ** 2).sum(0) * (y ** 2).sum())
        with np.errstate(invalid="ignore", divide="ignore"):
            tot += np.nan_to_num((x * y[:, None]).sum(0) / den)
        cnt += 1
    return tot / max(cnt, 1)


def walk_forward(X, Y, mem, blocks, H, model):
    """Predictions (days x coins), NaN outside the blocks. X (T, N, nf) ranked features with missing = 0; Y (T, N) target ranks (NaN
    where unknown); mem (T, N) rows that may be used. Each block is fitted on rows up to train_cutoff only."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import Ridge
    pred = np.full(Y.shape, np.nan, np.float32)
    info = []
    for a, b in blocks:
        cut = train_cutoff(a, H)
        if cut < 200:
            continue
        tr = mem[:cut + 1] & np.isfinite(Y[:cut + 1])
        te = mem[a:b]
        if tr.sum() < 5000 or not te.any():
            continue
        Xe = X[a:b][te]
        if model == "single":
            ics = day_ics(X[:cut + 1], Y[:cut + 1], tr)
            k = int(np.argmax(np.abs(ics)))
            out = np.sign(ics[k]) * Xe[:, k]
            info.append(k)
        else:
            Xt, yt = X[:cut + 1][tr], Y[:cut + 1][tr]
            m = Ridge(alpha=RIDGE_ALPHA) if model == "ridge" else HistGradientBoostingRegressor(
                max_depth=3, max_iter=150, learning_rate=0.05, min_samples_leaf=200, l2_regularization=1.0, random_state=0)
            m.fit(Xt, yt)
            out = m.predict(Xe)
            if model == "ridge":
                info.append(np.abs(m.coef_))
        blk = pred[a:b]
        blk[te] = out
    return pred, info


# ---------------------------------------------------------------- scores

def _rank(x):
    return np.argsort(np.argsort(x, kind="stable"), kind="stable").astype(float)


def day_scores(pred, F, M, q=Q, min_names=MIN_NAMES):
    """Per day: IC (Pearson of the two rank vectors), gross spread (top q minus bottom q), top-q return minus the day's mean, names."""
    T = pred.shape[0]
    ic, spread, lexc, nn = (np.full(T, np.nan) for _ in range(4))
    for t in range(T):
        ok = M[t] & np.isfinite(pred[t]) & np.isfinite(F[t])
        n = int(ok.sum())
        if n < min_names:
            continue
        p, f = pred[t, ok].astype(float), F[t, ok]
        k = max(3, int(round(q * n)))
        o = np.argsort(p, kind="stable")
        spread[t] = f[o[-k:]].mean() - f[o[:k]].mean()
        lexc[t] = f[o[-k:]].mean() - f.mean()
        rp, rf = _rank(p), _rank(f)
        if rp.std() > 0 and rf.std() > 0:
            ic[t] = np.corrcoef(rp, rf)[0, 1]
        nn[t] = n
    return ic, spread, lexc, nn


def net_spread(spread, H):
    """Gross spread less 12bp on each leg and the long leg's funding for the H days held."""
    return spread - COST_ROUND_TRIP - cs.FUND_H * 24 * H


def offset_stats(x, H, mask, min_n=20):
    """x per day (NaN where unknown), a half selected by `mask`: for each of the H entry alignments the mean and t of its days; returns the
    mean over alignments of the mean and of t, the WORST alignment's mean and the average count."""
    T = len(x)
    idx = np.arange(T)
    ms, ts, ns = [], [], []
    for o in range(H):
        v = x[mask & np.isfinite(x) & (idx % H == o)]
        if len(v) < min_n or v.std(ddof=1) == 0:
            continue
        ms.append(float(v.mean()))
        ts.append(float(v.mean() / (v.std(ddof=1) / sqrt(len(v)))))
        ns.append(len(v))
    if not ms:
        return dict(mean=np.nan, t=np.nan, worst=np.nan, n=0)
    return dict(mean=float(np.mean(ms)), t=float(np.mean(ts)), worst=float(np.min(ms)), n=float(np.mean(ns)))


def halves(dates):
    tune = (dates >= FIRST_OOS) & (dates < CUT)
    return tune, dates >= CUT


def cell(dates, pred, F, M, H, ref_spread=None):
    """All the numbers of one (model, H) cell. ref_spread = the single-feature model's gross spread for the paired comparison."""
    ic, spread, lexc, nn = day_scores(pred, F, M)
    net = net_spread(spread, H)
    out = {}
    for name, mask in zip(("tu", "ho"), halves(dates)):
        r = dict(ic=offset_stats(ic, H, mask), gross=offset_stats(spread, H, mask), net=offset_stats(net, H, mask),
                 lexc=offset_stats(lexc - cs.FEE - cs.FUND_H * 24 * H, H, mask))
        if ref_spread is not None:
            r["paired"] = offset_stats(spread - ref_spread, H, mask)
        out[name] = r
    out["spread"] = spread
    return out


def passes(c, holm_p):
    for h in ("tu", "ho"):
        r = c[h]
        if not (r["net"]["mean"] > 0 and r["net"]["t"] >= 2 and r["net"]["worst"] > 0 and r["ic"]["t"] >= 2):
            return False
    return holm_p < 0.05


# ---------------------------------------------------------------- main

def main():
    dates, coins, O, Hh, L, C, V, M = build_panel()
    btc = coins.index("BTCUSDT")
    feats = feature_panels(O, Hh, L, C, V, btc)
    ranked = np.stack([np.nan_to_num(xs_rank(feats[k], M), nan=0.0) for k in FEATURES], axis=-1).astype(np.float32)
    nfin = sum(np.isfinite(feats[k]).astype(np.int16) for k in FEATURES)
    mem = M & (nfin >= MIN_FEATS) & np.isfinite(O) & np.isfinite(C)
    blocks = make_blocks(dates)
    L_ = [f"backtest/indicator_model.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(coins)} PIT coins, {int(mem.sum()):,} coin-days, {len(FEATURES)} features, "
          f"{len(blocks)} quarterly blocks from {FIRST_OOS}; tune < {CUT}; 24bp + long funding per trade; top/bottom {int(Q * 100)}%", ""]
    results = {}
    for H in HORIZONS:
        F = forward_returns(O, C, H)
        Y = xs_rank(F, mem & np.isfinite(F))
        preds = {m: walk_forward(ranked, Y, mem, blocks, H, m) for m in ("single", "ridge", "gbm")}
        sing = cell(dates, preds["single"][0], F, mem, H)
        results[(H, "single")] = sing
        for m in ("ridge", "gbm"):
            results[(H, m)] = cell(dates, preds[m][0], F, mem, H, ref_spread=sing["spread"])
        pick = np.bincount(np.array(preds["single"][1], int), minlength=len(FEATURES))
        topk = np.argsort(-pick)[:4]
        L_.append(f"H={H}: single feature chosen most often: " + ", ".join(f"{FEATURES[k]} x{pick[k]}" for k in topk if pick[k] > 0))
        if preds["ridge"][1]:
            coef = np.mean(preds["ridge"][1], axis=0)
            L_.append(f"      ridge |coefficient| largest: " + ", ".join(f"{FEATURES[k]} {coef[k]:.3f}" for k in np.argsort(-coef)[:5]))
    L_.append("")
    L_.append(f"{'cell':<12}{'IC tune / hold (t)':<30}{'gross spread':<22}{'NET spread tune / hold (t)':<38}{'worst align':<17}{'paired vs single (t)'}")
    prim = [(H, m) for H in HORIZONS for m in ("ridge", "gbm")]
    pvals = [cs.p_one_sided(min(results[k]["tu"]["net"]["t"], results[k]["ho"]["net"]["t"])) for k in prim]
    adj = dict(zip(prim, cs.holm(pvals)))
    npass = 0
    for H in HORIZONS:
        for m in ("single", "ridge", "gbm"):
            c = results[(H, m)]
            tu, ho = c["tu"], c["ho"]
            ok = m != "single" and passes(c, adj[(H, m)])
            npass += int(ok)
            pr = (f"{tu['paired']['mean'] * 1e4:+5.1f}bp ({tu['paired']['t']:+.1f}) / {ho['paired']['mean'] * 1e4:+5.1f}bp ({ho['paired']['t']:+.1f})"
                  if "paired" in tu else "")
            L_.append(f"{m + ' H' + str(H):<12}{tu['ic']['mean']:+.3f} ({tu['ic']['t']:+.1f}) / {ho['ic']['mean']:+.3f} ({ho['ic']['t']:+.1f})   "
                      f"{tu['gross']['mean'] * 1e4:+6.1f} / {ho['gross']['mean'] * 1e4:+6.1f}bp   "
                      f"{tu['net']['mean'] * 1e4:+6.1f}bp ({tu['net']['t']:+.1f}) / {ho['net']['mean'] * 1e4:+6.1f}bp ({ho['net']['t']:+.1f})   "
                      f"{tu['net']['worst'] * 1e4:+6.1f} / {ho['net']['worst'] * 1e4:+6.1f}  {pr}  holm {adj.get((H, m), float('nan')):.2f} {'PASS' if ok else ''}")
    ics = [results[k][h]["ic"]["mean"] for k in prim for h in ("tu", "ho")]
    p2 = all(-0.01 <= x <= 0.04 for x in ics) and all(
        abs(results[(H, "ridge")][h]["ic"]["mean"] - results[(H, "gbm")][h]["ic"]["mean"]) < 0.015 for H in HORIZONS for h in ("tu", "ho"))
    p3n = sum(1 for k in prim if min(results[k]["tu"]["paired"]["t"], results[k]["ho"]["paired"]["t"]) < 2)
    p4 = all(results[(1, m)][h]["net"]["mean"] < 0 for m in ("ridge", "gbm") for h in ("tu", "ho"))
    p5n = sum(1 for k in prim if results[k]["ho"]["gross"]["mean"] < results[k]["tu"]["gross"]["mean"])
    L_ += ["", f"PRIMARY CELLS PASSING: {npass} of 6",
           "REGISTERED PREDICTIONS",
           f"  P1 no primary cell passes -> {'RIGHT' if npass == 0 else 'WRONG'} ({npass})",
           f"  P2 every IC in [-0.01, +0.04] and ridge vs gbm differ by < 0.015 -> {'RIGHT' if p2 else 'WRONG'} (ICs {min(ics):+.3f} .. {max(ics):+.3f})",
           f"  P3 combination does not beat the best single feature (paired t < 2 on a half) in >= 5 of 6 -> {'RIGHT' if p3n >= 5 else 'WRONG'} ({p3n} of 6)",
           f"  P4 every H = 1 cell net spread negative on both halves -> {'RIGHT' if p4 else 'WRONG'}",
           f"  P5 holdout gross spread below tune in >= 3 of 6 -> {'RIGHT' if p5n >= 3 else 'WRONG'} ({p5n} of 6)"]
    txt = "\n".join(L_)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

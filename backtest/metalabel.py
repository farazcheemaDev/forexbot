"""META-LABELING — don't find a new signal, learn which signals to skip.

THE PROBLEM THIS ATTACKS, IN OUR OWN NUMBERS
--------------------------------------------
On 4 years of untouched crypto data the momentum families measure:

    gross expectancy  +0.05R
    fees              -0.04 to -0.08R
    net                ~0.00 to -0.01R

The pattern is real and smaller than the cost of harvesting it. There are only
two ways out: pay less per trade (the live maker probe), or TAKE FEWER, BETTER
TRADES. Meta-labeling is the second.

Mechanism, stated precisely (my first description of this was sloppy): each trade
pays the same fee whether or not we filter, so filtering does NOT buy a fee
discount. What it buys is SELECTION - if a model can identify the subset where
gross expectancy is +0.15R instead of +0.05R, that subset nets +0.10R after the
same fee. The bad trades removed take their losses AND their fees with them.

METHOD (after neurotrader888/TrendlineBreakoutMetaLabel, itself following
Lopez de Prado's "Advances in Financial Machine Learning")
----------------------------------------------------------
  1. Run the PRIMARY strategy exactly as validated. Record, at each entry, a set
     of features describing the market at that moment.
  2. Label each trade 1 if it won, 0 if it lost.
  3. Train a shallow classifier to predict the label from the features.
  4. Live, take a signal only when the model says P(win) > threshold.

The model never decides direction - only whether to act on a signal the primary
strategy already produced. That is what makes it far less prone to overfitting
than searching for a new signal.

WHAT WE DO DIFFERENTLY FROM THE REFERENCE
-----------------------------------------
  * ATR is SHIFTED. The reference computes features with atr[i] at entry bar i,
    which leaks bar i's own range. That exact bug cost us 0.25R/trade of fiction
    earlier today. Every feature here uses data through bar i-1 only.
  * Trained on the DEVELOPMENT window, tested on the UNTOUCHED holdout, so the
    meta-model faces genuinely unseen data.
  * THREE CONTROLS, because a filter that removes trades will look better by
    accident if you only compare it to the unfiltered set:
        unfiltered   - the raw strategy
        RANDOM       - discard the same FRACTION of trades at random. This is the
                       critical control: if meta-labeling cannot beat a coin
                       flip that keeps the same number of trades, it learned
                       nothing and the apparent gain is just a smaller sample.
        shuffled-y   - train on randomly permuted labels. Any "edge" that
                       survives this is leakage in the pipeline.

    python -m backtest.metalabel
    python -m backtest.metalabel --asset ETHUSDT --fam rsi_mom
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.holdout_sweep import USED_DAYS, signals_for  # noqa: E402
from backtest.mass_search import FILTERS, fetch  # noqa: E402
from bot.core.indicators import (adx, atr as atr_ind, ema,  # noqa: E402
                                 efficiency_ratio, rsi)
from bot.strategies.base import Action  # noqa: E402

SL, TP, FEE_BP = 2.0, 3.0, 10.0
PROB_THRESHOLDS = (0.50, 0.55, 0.60)
ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT",
          "AVAXUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT"]


def feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """All features, every one shifted so bar i uses data through i-1 only.

    Scale-free by construction (ratios or ATR-normalised), so one model can be
    trained across assets priced from $0.08 to $70,000.
    """
    c, h, lo, v = df["close"], df["high"], df["low"], df["volume"]
    a = atr_ind(df, 14)
    f = pd.DataFrame(index=df.index)
    f["atr_pct"] = a / c                                  # volatility regime
    f["vol_rel"] = v / v.rolling(168).median()            # VOLUME - never used before
    f["adx"] = adx(df, 14)
    f["er20"] = efficiency_ratio(c, 20)                   # trendiness
    f["rsi14"] = rsi(c, 14)
    f["dist_ema50"] = (c - ema(c, 50)) / a                # extension, in ATR
    f["ret10_atr"] = (c - c.shift(10)) / a                # momentum magnitude
    f["range_rel"] = (h - lo) / a                         # today's bar vs baseline
    f["bb_pos"] = ((c - c.rolling(20).mean())
                   / (c.rolling(20).std() + 1e-12))       # z-score in the band
    f["hour"] = df["time"].dt.hour if "time" in df else 0  # crypto session effect
    return f.shift(1)                                     # <-- causality


FEATS = ["atr_pct", "vol_rel", "adx", "er20", "rsi14", "dist_ema50",
         "ret10_atr", "range_rel", "bb_pos", "hour"]


def build_dataset(df: pd.DataFrame, fam: str, p: tuple,
                  filt: str = "none") -> pd.DataFrame:
    """Run the primary strategy; return one row per trade: features + R + label."""
    sig = FILTERS[filt](df, signals_for(df, fam, p)).to_numpy()
    feats = feature_frame(df)
    fv = feats[FEATS].to_numpy(float)
    o, hi, lo = (df["open"].to_numpy(float), df["high"].to_numpy(float),
                 df["low"].to_numpy(float))
    a = atr_ind(df, 14).to_numpy(float)
    fee = FEE_BP / 10000.0

    rows = []
    pos = None
    for i in range(1, len(df)):
        if pos is None and sig[i] != Action.HOLD and np.isfinite(a[i - 1]) and a[i - 1] > 0:
            if not np.all(np.isfinite(fv[i])):
                continue
            d = 1 if sig[i] == Action.BUY else -1
            e = o[i]
            risk = SL * a[i - 1]
            pos = dict(d=d, e=e, risk=risk, stop=e - d * risk,
                       targ=e + d * TP * a[i - 1], x=fv[i].copy(), i=i)
        if pos is not None:
            d, e, risk = pos["d"], pos["e"], pos["risk"]
            hit_sl = (lo[i] <= pos["stop"]) if d == 1 else (hi[i] >= pos["stop"])
            hit_tp = (hi[i] >= pos["targ"]) if d == 1 else (lo[i] <= pos["targ"])
            px, taker = ((pos["stop"], True) if hit_sl else
                         ((pos["targ"], False) if hit_tp else (None, True)))
            if px is not None:
                R = (px - e) * d / risk - (fee * e + fee * abs(px)) / risk / 2
                rows.append(dict(entry_i=pos["i"], exit_i=i, R=R,
                                 y=1 if R > 0 else 0,
                                 **{k: pos["x"][j] for j, k in enumerate(FEATS)}))
                pos = None
    return pd.DataFrame(rows)


def summarise(R: np.ndarray, label: str, n_all: int) -> dict:
    if len(R) == 0:
        return dict(label=label, n=0, meanR=0.0, sumR=0.0, win=0.0, kept=0.0)
    return dict(label=label, n=len(R), meanR=float(R.mean()),
                sumR=float(R.sum()), win=float((R > 0).mean()),
                kept=len(R) / n_all if n_all else 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fam", default="bb_break")
    ap.add_argument("--params", default="30,1.5")
    ap.add_argument("--trees", type=int, default=400)
    ap.add_argument("--depth", type=int, default=3)
    args = ap.parse_args()

    from sklearn.ensemble import RandomForestClassifier

    p = tuple(float(x) if "." in x else int(x) for x in args.params.split(","))
    print(f"META-LABELING  primary = {args.fam}{p}  "
          f"forest: {args.trees} trees, depth {args.depth}")
    print(f"features ({len(FEATS)}): {', '.join(FEATS)}\n")

    train_rows, test_rows = [], []
    for a in ASSETS:
        try:
            d = fetch(a, "1h", 2400)
        except Exception:
            continue
        cut = d.time.iloc[-1] - pd.Timedelta(days=USED_DAYS)
        hold = d[d.time < cut].reset_index(drop=True)     # NEVER used to choose
        used = d[d.time >= cut].reset_index(drop=True)    # development window
        if len(hold) < 3000:
            continue
        tr = build_dataset(used, args.fam, p)
        te = build_dataset(hold, args.fam, p)
        if len(tr) < 50 or len(te) < 50:
            continue
        tr["asset"] = a; te["asset"] = a
        train_rows.append(tr); test_rows.append(te)
        print(f"  {a:9} train(dev)={len(tr):5}  test(holdout)={len(te):5}")

    train = pd.concat(train_rows, ignore_index=True)
    test = pd.concat(test_rows, ignore_index=True)
    print(f"\nTRAIN on development window: {len(train)} trades "
          f"(win rate {train.y.mean()*100:.1f}%)")
    print(f"TEST on untouched holdout:   {len(test)} trades "
          f"(win rate {test.y.mean()*100:.1f}%)")

    Xtr, ytr = train[FEATS].to_numpy(float), train["y"].to_numpy(int)
    Xte = test[FEATS].to_numpy(float)
    Rte = test["R"].to_numpy(float)

    mdl = RandomForestClassifier(n_estimators=args.trees, max_depth=args.depth,
                                 min_samples_leaf=50, random_state=42, n_jobs=-1)
    mdl.fit(Xtr, ytr)
    prob = mdl.predict_proba(Xte)[:, 1]

    # shuffled-label model: any surviving edge here is pipeline leakage
    rng = np.random.default_rng(0)
    shuf = RandomForestClassifier(n_estimators=args.trees, max_depth=args.depth,
                                  min_samples_leaf=50, random_state=42, n_jobs=-1)
    shuf.fit(Xtr, rng.permutation(ytr))
    prob_shuf = shuf.predict_proba(Xte)[:, 1]

    # --- does the model RANK trades at all? AUC is the cleanest single number.
    # A fixed 0.50 threshold is meaningless when the base win rate is ~41%: a
    # calibrated model centres its probabilities near 0.41, so >0.50 keeps only a
    # tiny tail. Rank-based selection is the right test.
    def auc(y, s):
        o = np.argsort(s)
        r = np.empty(len(s), float); r[o] = np.arange(1, len(s) + 1)
        n1 = y.sum(); n0 = len(y) - n1
        if n1 == 0 or n0 == 0:
            return float("nan")
        return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))

    yte = test["y"].to_numpy(int)
    print(f"\nranking skill on the holdout:  AUC = {auc(yte, prob):.4f}   "
          f"(0.50 = no skill)")
    print(f"  shuffled-label model AUC     = {auc(yte, prob_shuf):.4f}   "
          f"(sanity: must be ~0.50)")

    print(f"\nmean R by predicted-probability decile (should rise if ranking works):")
    dec = pd.qcut(prob, 10, labels=False, duplicates="drop")
    print(f"  {'decile':>7} {'n':>6} {'meanR':>9} {'win%':>6}")
    for dd in sorted(pd.unique(dec[~pd.isna(dec)])):
        m = dec == dd
        print(f"  {int(dd)+1:>7} {m.sum():>6} {Rte[m].mean():>+9.4f} "
              f"{(Rte[m] > 0).mean()*100:>6.1f}")

    print(f"\n{'variant':32} {'trades':>7} {'kept%':>6} {'win%':>6} "
          f"{'meanR':>8} {'sumR':>9}")
    base = summarise(Rte, "unfiltered (raw strategy)", len(Rte))
    print(f"{base['label']:32} {base['n']:>7} {100.0:>6.1f} "
          f"{base['win']*100:>6.1f} {base['meanR']:>+8.4f} {base['sumR']:>+9.1f}")

    # keep the top X% by predicted probability — meaningful sample sizes
    for frac in (0.50, 0.30, 0.20, 0.10):
        cut = np.quantile(prob, 1 - frac)
        keep = prob >= cut
        s = summarise(Rte[keep], f"META-LABEL top {frac*100:.0f}%", len(Rte))
        if s["n"] < 30:
            print(f"{s['label']:32} {s['n']:>7}  too few trades to judge")
            continue
        # RANDOM control at the SAME size — the decisive comparison. If the model
        # cannot beat blindly keeping the same number of trades, it learned nothing.
        k = int(keep.sum())
        rnd = [Rte[rng.choice(len(Rte), k, replace=False)].mean() for _ in range(400)]
        rnd_p95 = float(np.percentile(rnd, 95))
        sh_keep = prob_shuf >= np.quantile(prob_shuf, 1 - frac)
        print(f"{s['label']:32} {s['n']:>7} {s['kept']*100:>6.1f} "
              f"{s['win']*100:>6.1f} {s['meanR']:>+8.4f} {s['sumR']:>+9.1f}")
        print(f"{'  random same-size control':32} {k:>7} {'':>6} {'':>6} "
              f"{np.mean(rnd):>+8.4f}          95th {rnd_p95:+.4f}")
        print(f"{'  shuffled-label control':32} {int(sh_keep.sum()):>7} {'':>6} "
              f"{'':>6} {Rte[sh_keep].mean():>+8.4f}")
        print(f"{'  ->':32} "
              f"{'BEATS random control' if s['meanR'] > rnd_p95 else 'no better than dropping trades at random'}")

    imp = sorted(zip(FEATS, mdl.feature_importances_), key=lambda x: -x[1])
    print("\nfeature importance:")
    for k, vv in imp:
        print(f"   {k:12} {vv:.4f}")


if __name__ == "__main__":
    main()

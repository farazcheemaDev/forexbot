"""PROTOCOL LAB - why the registry exists: selection bias and the cost wall, shown on real price data (2026-10-30). DOGE perp on Bitget, ONE day: 2026-06-01.

WHAT THIS IS: three DESCRIPTIVE demonstrations on the teaching day (2026-09-01 stays unread; nothing here is a hypothesis test and nothing is a result to trade on).
    A. THE WINNER'S CURSE. A researcher tries 60 rules (4 book features x 5 entry quantiles x 3 horizons), keeps the one with the best gross move on the first 60% of
       the day and reads it on the last 40%. Done on the REAL features and on 50 independent SHIFTED copies of them (no link to the future at all).
    B. RIGHT BUT UNPROFITABLE. The simplest rule (imb1 in its top / bottom decile, thresholds from the first 60%) read on the last 40%, at each horizon: how often it
       is right, its gross move, and what is left after a maker (4bp) and a taker (12bp) round trip.
    C. HOW LONG TO PAPER TRADE. Independent trades needed to detect a true mean per trade at 80% power, from the per-trade spread of those very trades.
RULE FOR A TRADE: at every h-th second (non-overlapping), long if the feature is at or above its tune-half q-quantile, short if at or below its (1 - q) quantile,
the gross move is the signed mid change over the next h seconds, one decision per h seconds. Thresholds come from the first 60% of the seconds only.

REGISTERED BEFORE THE FIRST RUN (2026-10-30)
    P1  Winner's curse: over 50 shifted-feature draws the in-sample best of the 60 rules has a mean gross move above +1.0bp, while the mean gross move of the SAME rules on the
        last 40% is within +-0.5bp of zero.
    P2  On the real features the selected rule is a book-imbalance rule (imb1, imb5 or band10) at h = 5 s or 30 s; its out-of-sample gross is 40-100% of its in-sample gross.
    P3  The selected real rule's out-of-sample gross is below 4bp, so its net after even the ideal maker round trip is negative.
    P4  imb1's decile rule on the last 40%: hit rate among non-zero moves 52-62% at 5 s and 30 s, gross move +0.5 to +1.5bp.

FIRST RUN (2026-10-30 09:26): P1 right (null: in-sample best +2.92bp, out of sample +0.04bp); P2 WRONG (the real search picked imb5 at q 0.90, h 300 s: +3.60bp on 36
    trades in-sample, -0.14bp out of sample - the few-trade long horizon wins any search by raw mean, the real signal imb1 at 5 s, +0.79bp with se 0.06, loses it); P3 right;
    P4 half wrong (gross +0.79 / +1.46bp is in range; the hit rates 76% / 64% are above the 52-62% I guessed).
ADDED AFTER THE FIRST RUN, BEFORE THE VARIANT WAS RUN: select by t = mean / se instead of by the mean.
    P5  With selection by t, the real search picks a book-imbalance rule at h = 5 s and its out-of-sample gross is at least 60% of its in-sample gross; over the 50 shifted draws
        the in-sample best t has a median between 2.2 and 3.2 and the out-of-sample mean gross stays within +-0.3bp of zero (selection by t reduces, and does not remove, the curse).

SECOND RUN (same day): P5 half right. REAL search by t: imb1, q 0.90, h 5 s, in-sample +0.72bp on 2,074 trades (t 15.3), out of sample +0.79bp (109%) - right. NULL searches by t:
    in-sample best t median 2.13 (10th-90th 1.30 .. 2.71) - just under my 2.2-3.2; out of sample mean -0.39bp (median -0.01) - outside my +-0.3bp. Selecting by t separates the real
    rule (t 15.3) from the best noise rule (t <= 2.7 in 90% of draws) cleanly; selecting by the mean did not.
    python -m backtest.protocol_lab          writes logs/protocol_lab.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.order_flow_registry import trades_needed  # noqa: E402
from backtest.window_lab import FEATURES, MIN_SHIFT_S, fwd_change_bp, load_day, shifted  # noqa: E402

LOG = ROOT / "logs" / "protocol_lab.txt"
QS = (0.80, 0.90, 0.95, 0.98, 0.99)
HS = (5, 30, 300)
SPLIT = 0.6
MIN_TRADES = 30
MAKER_BP, TAKER_BP = 4.0, 12.0


def decision_idx(a: int, b: int, h: int) -> np.ndarray:
    """Decision seconds in [a, b) whose whole forward window t .. t + h ends inside the segment: non-overlapping, one every h seconds."""
    return np.arange(a, b - h, h)


def thresholds(feat: np.ndarray, h: int, q: float, split: int):
    """(low, high) cut-offs: the (1 - q) and q quantiles of the feature at the TUNE segment's decision seconds only."""
    f = feat[decision_idx(0, split, h)]
    f = f[np.isfinite(f)]
    return float(np.quantile(f, 1 - q)), float(np.quantile(f, q))


def gross_moves(feat: np.ndarray, fwd: np.ndarray, h: int, lo: float, hi: float, a: int, b: int) -> np.ndarray:
    """Signed mid moves (bp) of the trades the rule takes in [a, b): long at or above `hi`, short at or below `lo`."""
    idx = decision_idx(a, b, h)
    f, y = feat[idx], fwd[idx]
    side = np.where(f >= hi, 1.0, np.where(f <= lo, -1.0, 0.0))
    ok = (side != 0) & np.isfinite(f) & np.isfinite(y)
    return (side * y)[ok]


def select_and_read(F: dict, fwd_by_h: dict, n: int, split_frac: float = SPLIT, criterion: str = "mean"):
    """Try every (feature, q, h): keep the rule with the best in-sample score (criterion "mean": the mean gross move; "t": mean / standard error), needing at least
    MIN_TRADES trades, then read it out of sample. Returns (config, in_sample_mean, in_sample_n, out_of_sample_mean, out_of_sample_n, in_sample_t)."""
    split = int(n * split_frac)
    best = None
    for c, feat in F.items():
        for q in QS:
            for h in HS:
                lo, hi = thresholds(feat, h, q, split)
                g = gross_moves(feat, fwd_by_h[h], h, lo, hi, 0, split)
                if len(g) < MIN_TRADES:
                    continue
                t = float(g.mean() / (g.std(ddof=1) / np.sqrt(len(g)))) if g.std(ddof=1) > 0 else 0.0
                score = g.mean() if criterion == "mean" else t
                if best is None or score > best[0]:
                    best = (score, (c, q, h), float(g.mean()), len(g), lo, hi, t)
    _, (c, q, h), m_in, n_in, lo, hi, t_in = best
    go = gross_moves(F[c], fwd_by_h[h], h, lo, hi, split, n)
    return (c, q, h), m_in, n_in, (float(go.mean()) if len(go) else float("nan")), len(go), t_in


def hit_rate(g: np.ndarray) -> float:
    nz = g[g != 0]
    return float((nz > 0).mean()) if len(nz) else float("nan")


def main():
    rng = np.random.default_rng(11)
    mid, F, signed, absd, t0 = load_day()
    n = len(mid)
    split = int(n * SPLIT)
    fwd = {h: fwd_change_bp(mid, h) for h in sorted(set(HS) | {60})}
    L = [f"backtest/protocol_lab.py, DOGEUSDT perp on Bitget, 2026-06-01 (Tardis), {n:,} seconds, tune = first {SPLIT:.0%} ({split:,} s), read = last {1 - SPLIT:.0%}, "
         f"run {__import__('pandas').Timestamp.now():%Y-%m-%d %H:%M}"]

    L.append("\nA. THE WINNER'S CURSE: best of 60 rules chosen in-sample, read out of sample")
    cfg, m_in, n_in, m_out, n_out, _ = select_and_read(F, fwd, n)
    L.append(f"  REAL features: the best rule is {cfg[0]} at q {cfg[1]:.2f}, h {cfg[2]} s: in-sample {m_in:+.2f}bp gross on {n_in} trades; out of sample {m_out:+.2f}bp on {n_out} trades "
             f"({m_out / m_in * 100:.0f}% of the in-sample figure)")
    ins, outs, picked = [], [], []
    for _ in range(50):
        Fs = {c: shifted(f, int(rng.integers(MIN_SHIFT_S, n - MIN_SHIFT_S))) for c, f in F.items()}
        cf, a, na, b, nb, _ = select_and_read(Fs, fwd, n)
        ins.append(a)
        outs.append(b)
        picked.append(cf[2])
    ins, outs = np.array(ins), np.array(outs)
    ok = np.isfinite(outs)
    L.append(f"  50 SHIFTED draws (no link to the future): in-sample best gross: mean {ins.mean():+.2f}bp, median {np.median(ins):+.2f}, 10th-90th percentile "
             f"{np.percentile(ins, 10):+.2f} .. {np.percentile(ins, 90):+.2f}; the same rules out of sample: mean {outs[ok].mean():+.2f}bp, median {np.median(outs[ok]):+.2f}, "
             f"positive in {np.mean(outs[ok] > 0) * 100:.0f}% of draws")
    L.append(f"  horizons the null searches picked: " + ", ".join(f"{h} s {picked.count(h)}" for h in HS) + " (the few-trade, big-variance long horizons win the search)")

    L.append("\n   THE SAME SEARCH, CHOOSING BY t = mean / standard error INSTEAD OF BY THE MEAN")
    cfg, m_in, n_in, m_out, n_out, t_in = select_and_read(F, fwd, n, criterion="t")
    L.append(f"  REAL features: the best rule is {cfg[0]} at q {cfg[1]:.2f}, h {cfg[2]} s: in-sample {m_in:+.2f}bp gross on {n_in} trades (t {t_in:.1f}); out of sample "
             f"{m_out:+.2f}bp on {n_out} trades ({m_out / m_in * 100:.0f}% of the in-sample figure)")
    rng2 = np.random.default_rng(11)
    ts, outs_t, pk = [], [], []
    for _ in range(50):
        Fs = {c: shifted(f, int(rng2.integers(MIN_SHIFT_S, n - MIN_SHIFT_S))) for c, f in F.items()}
        cf, a, na, b, nb, tt = select_and_read(Fs, fwd, n, criterion="t")
        ts.append(tt)
        outs_t.append(b)
        pk.append(cf[2])
    ts, outs_t = np.array(ts), np.array(outs_t)
    L.append(f"  50 SHIFTED draws: in-sample best t: median {np.median(ts):.2f}, 10th-90th percentile {np.percentile(ts, 10):.2f} .. {np.percentile(ts, 90):.2f}; "
             f"the same rules out of sample: mean {np.nanmean(outs_t):+.2f}bp, median {np.nanmedian(outs_t):+.2f}; horizons picked: " + ", ".join(f"{h} s {pk.count(h)}" for h in HS))

    L.append("\nB. RIGHT BUT UNPROFITABLE: imb1 decile rule (q 0.90), thresholds from the tune part, read on the last 40%")
    L.append(f"  {'h':>5s} {'trades':>7s} {'right (non-zero)':>17s} {'gross bp':>9s} {'+-se':>6s} {'sd/trade':>9s} {'net maker 4bp':>14s} {'net taker 12bp':>15s}")
    sds = {}
    for h in (5, 30, 60, 300):
        lo, hi = thresholds(F["imb1"], h, 0.90, split)
        g = gross_moves(F["imb1"], fwd[h], h, lo, hi, split, n)
        sds[h] = g.std(ddof=1)
        L.append(f"  {h:>3d} s {len(g):7d} {hit_rate(g) * 100:16.0f}% {g.mean():+9.2f} {g.std(ddof=1) / np.sqrt(len(g)):6.2f} {sds[h]:9.2f} {g.mean() - MAKER_BP:+14.2f} {g.mean() - TAKER_BP:+15.2f}")

    L.append("\nC. HOW MANY INDEPENDENT TRADES TO DETECT A TRUE MEAN (80% power, two-sided 5%), using each horizon's measured sd per trade")
    L.append(f"  {'h':>5s} {'sd/trade':>9s} {'trades / day':>13s} " + " ".join(f"{'mean ' + str(mu) + 'bp':>12s}" for mu in (0.25, 0.5, 1.0, 2.0)) + f" {'days for 1bp':>13s}")
    for h in (5, 30, 60, 300):
        lo, hi = thresholds(F["imb1"], h, 0.90, split)
        per_day = len(gross_moves(F["imb1"], fwd[h], h, lo, hi, split, n)) / ((n - split) / 86400)
        L.append(f"  {h:>3d} s {sds[h]:9.2f} {per_day:13,.0f} " + " ".join(f"{trades_needed(mu, sds[h]):12,d}" for mu in (0.25, 0.5, 1.0, 2.0))
                 + f" {trades_needed(1.0, sds[h]) / per_day:13.1f}")
    L.append("  (the registry also demands at least 20 distinct confirm DAYS, because a day is one cluster of one market: for the fast horizons the days, not the trades, are the binding constraint)")
    txt = "\n".join(L)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

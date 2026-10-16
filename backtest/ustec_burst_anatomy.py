"""THE BURST HE CATCHES - can a NASDAQ burst be seen coming, and which way, in the seconds before it starts? (2026-10-12)

THE USER (2026-10-12): "we discovered something - the burst in NASDAQ - I think that has something to do with his strategy
... we are so close to crack his strategy". The reframing: 46 clicks are too few to learn from, but what his trades CATCH
is a NASDAQ burst - +7 points within seconds of his click (his_clock_exits.py: the market had NOT moved before his click,
median 0.00 points in 5 s, then went his way 40 of 46 times). Bursts happen thousands of times. If what precedes a burst
- its timing AND its direction - is visible in the seconds before, that is his strategy as a bot, whether or not he does
it by eye; and his clicks should sit where such a model says a burst is coming.

DATA     Exness USTECm ticks, strategy_analysis/data/ustec_tick_days.pkl: 181 days 2026-01-02 .. 09-14, 09:30-19:30 New
         York, mid and spread. A 1-second grid of the last mid and the tick count per second.
TARGETS  OCCURRENCE: the mid moves >= 7 points from its value at second t within the next 5 s.  DIRECTION: the sign of
         that first >= 7-point excursion.
FEATURES (all from ticks at or before t): quote rate over 5 / 30 / 300 s and its ratios; absolute 1-second movement over
         5 / 30 / 300 s and ratios; range of the last 30 / 300 s; signed move over 1 / 5 / 15 / 30 / 60 / 300 s; up-minus-down
         seconds over the last 10 s; spread now vs its 300-s median; second of the minute, minute of the hour, hour; the
         day's movement so far; seconds since the last completed burst.
MODELS   gradient-boosted trees (sklearn HistGradientBoostingClassifier), fit on the first 60% of days, scored on the
         rest (AUC). Then a BOT: on holdout days, when the occurrence score is in the tune days' top 0.5% / 0.1%, enter one
         second later at the real ask / bid in the direction model's side and race +-7 points (30-min cap), one position
         at a time - against random sides at the same seconds. And HIS 46 clicks scored on both models.

REGISTERED BEFORE THE RUN (2026-10-12)
    B1  Bursts are partly foreseeable in TIME: occurrence AUC on holdout days >= 0.70 (volatility and quote rate cluster).
    B2  Their DIRECTION is not: direction AUC <= 0.55 (s36: his side is in no price history).
    B3  The bot fails after the spread: net points a trade <= 0 at both thresholds.
    B4  His clicks sit higher than his own sittings' other seconds on the occurrence score (median percentile >= 70);
        the direction model agrees with his side no better than 60%.

RESULT (2026-10-12, logs/ustec_burst_anatomy.txt) - bursts can be seen coming; which WAY they go cannot.
    392,421 burst seconds (6.8% of all seconds).
    B1 RIGHT: occurrence AUC 0.861 on holdout days, carried by recent movement and range (av30 0.89, av300 0.88, rg300 0.87,
       dayvol 0.86): bursts come in volatile stretches.
    B2 RIGHT: direction AUC 0.513; no signed feature above 0.508 (r1..r300, imb10).
    B3 RIGHT: the bot loses -1.76 / -1.82 points a trade (26,804 / 14,075 trades, t -42 / -32), the same as a random side
       at the same seconds (-1.73 / -1.72). Knowing WHEN without WHICH WAY is a coin flip that pays the spread.
    B4 WRONG on its first half: his clicks are NOT at predicted bursts - median percentile 59 in his own windows, top
       quintile 24% (chance 20%). The direction model agrees with his side 48%.
    Follow-up, his_burst_after.py: after his click a burst comes no more often than at other seconds (22% vs 23% within
    10 s), and his +7 arrives at the ordinary pace (median 29 s vs 33 s; 36% vs 38% completed by a burst). His moves are
    ordinary moves; only his SIDE is special (39 of 41 on the mid).

    python -m backtest.ustec_burst_anatomy
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "ustec_burst_anatomy.txt"
X, H = 7.0, 5
FEATS = ["qr5", "qr30", "qr300", "qr_5_300", "qr_30_300", "av5", "av30", "av300", "av_5_300", "av_30_300", "rg30", "rg300",
         "r1", "r5", "r15", "r30", "r60", "r300", "imb10", "sp_rel", "sec", "minute", "hour", "dayvol", "since"]


def roll_sum(x, n):
    c = np.r_[0, np.cumsum(x)]
    out = np.empty(len(x))
    idx = np.arange(len(x))
    out[:] = c[idx + 1] - c[np.maximum(idx + 1 - n, 0)]
    return out


def day_frame(ts, mid, spr):
    g = np.arange(np.ceil(ts[0]) + 300, ts[-1] - 1800, 1.0)
    gi = np.searchsorted(ts, g, "right") - 1
    m = mid[gi]
    sp = spr[gi]
    cnt = np.diff(np.r_[0, np.searchsorted(ts, g, "right")]).astype(float)
    cnt[0] = 0
    d1 = np.r_[0.0, np.diff(m)]
    a1 = np.abs(d1)
    f = {}
    f["qr5"], f["qr30"], f["qr300"] = roll_sum(cnt, 5), roll_sum(cnt, 30), roll_sum(cnt, 300)
    f["qr_5_300"] = f["qr5"] / np.maximum(f["qr300"] / 60, 1e-9)
    f["qr_30_300"] = f["qr30"] / np.maximum(f["qr300"] / 10, 1e-9)
    f["av5"], f["av30"], f["av300"] = roll_sum(a1, 5), roll_sum(a1, 30), roll_sum(a1, 300)
    f["av_5_300"] = f["av5"] / np.maximum(f["av300"] / 60, 1e-9)
    f["av_30_300"] = f["av30"] / np.maximum(f["av300"] / 10, 1e-9)
    s = pd.Series(m)
    f["rg30"] = (s.rolling(30, min_periods=1).max() - s.rolling(30, min_periods=1).min()).to_numpy()
    f["rg300"] = (s.rolling(300, min_periods=1).max() - s.rolling(300, min_periods=1).min()).to_numpy()
    for k in (1, 5, 15, 30, 60, 300):
        f[f"r{k}"] = m - np.r_[np.full(k, m[0]), m[:-k]]
    f["imb10"] = roll_sum(np.sign(d1), 10)
    sp_med = pd.Series(sp).rolling(300, min_periods=1).median().to_numpy()
    f["sp_rel"] = sp / np.maximum(sp_med, 1e-9)
    clock = g + 9.5 * 3600                                          # seconds after midnight New York
    f["sec"], f["minute"], f["hour"] = clock % 60, (clock // 60) % 60, clock // 3600
    f["dayvol"] = np.cumsum(a1) / np.maximum(np.arange(1, len(a1) + 1), 1) * 60
    # targets: the first >= X excursion in the next H seconds
    fut = np.stack([np.r_[m[k:], np.full(k, np.nan)] - m for k in range(1, H + 1)], axis=1)
    hit_up = np.nan_to_num(fut, nan=0) >= X
    hit_dn = np.nan_to_num(fut, nan=0) <= -X
    first_up = np.where(hit_up.any(1), hit_up.argmax(1), 99)
    first_dn = np.where(hit_dn.any(1), hit_dn.argmax(1), 99)
    occ = (first_up < 99) | (first_dn < 99)
    direction = np.where(first_up < first_dn, 1, np.where(first_dn < first_up, -1, 0))
    # seconds since the last COMPLETED burst (a burst starting at u is known at u + H)
    starts = np.flatnonzero(occ)
    known = starts + H
    last = np.full(len(m), np.nan)
    j = np.searchsorted(known, np.arange(len(m)), "right") - 1
    ok = j >= 0
    last[ok] = np.arange(len(m))[ok] - known[j[ok]]
    f["since"] = np.nan_to_num(last, nan=3600)
    F = pd.DataFrame(f)
    F["t"], F["occ"], F["dir"] = g, occ, direction
    return F, (g, m, sp)


def race(gm, gsp, i, side):
    """enter at grid second i at the real price, +-X on the exit side, 30-min cap: net points."""
    e = gm[i] + side * gsp[i] / 2
    p = side * ((gm[i + 1:i + 1800] - side * gsp[i + 1:i + 1800] / 2) - e)
    up, dn = np.flatnonzero(p >= X), np.flatnonzero(p <= -X)
    if len(up) and (not len(dn) or up[0] < dn[0]):
        return X, up[0] + 1
    if len(dn):
        return -X, dn[0] + 1
    return (float(p[-1]) if len(p) else 0.0), len(p)


def main():
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    cache = pickle.loads((ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl").read_bytes())
    days = sorted(d for d, v in cache.items() if v is not None)
    cut = days[int(len(days) * 0.6)]
    rng = np.random.default_rng(11)
    frames, grids = [], {}
    for d in days:
        F, grid = day_frame(*cache[d])
        F["day"] = d
        keep = F.occ.to_numpy() | (rng.random(len(F)) < 0.08)        # all burst seconds + 8% of the rest
        F["w"] = np.where(F.occ, 1.0, 1 / 0.08)
        frames.append(F[keep])
        grids[d] = grid
    D = pd.concat(frames, ignore_index=True)
    tu = D.day < cut
    lines = [f"backtest/ustec_burst_anatomy.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; Exness USTECm, {len(days)} days; "
             f"holdout from {cut:%Y-%m-%d}; burst = >= {X:g} points within {H} s; burst seconds {int(D.occ.sum()):,} "
             f"({D.occ.sum() / (D.w.sum()) * 100:.2f}% of all seconds)", ""]
    occ_m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, random_state=0)
    occ_m.fit(D.loc[tu, FEATS], D.loc[tu, "occ"], sample_weight=D.loc[tu, "w"])
    p_ho = occ_m.predict_proba(D.loc[~tu, FEATS])[:, 1]
    auc_occ = roc_auc_score(D.loc[~tu, "occ"], p_ho, sample_weight=D.loc[~tu, "w"])
    lines.append(f"B1 OCCURRENCE - holdout AUC {auc_occ:.3f} (0.5 = blind)")
    # which features carry it: holdout AUC of each feature alone (sign-free)
    single = []
    for c in FEATS:
        v = D.loc[~tu, c].to_numpy()
        a = roc_auc_score(D.loc[~tu, "occ"], v, sample_weight=D.loc[~tu, "w"])
        single.append((max(a, 1 - a), c, a))
    single.sort(reverse=True)
    lines.append("   strongest single features (holdout AUC): " + ", ".join(f"{c} {a:.2f}" for _, c, a in single[:8]))
    B = D[D.occ & (D.dir != 0)]
    bt = B.day < cut
    dir_m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, random_state=0)
    dir_m.fit(B.loc[bt, FEATS], B.loc[bt, "dir"] > 0)
    auc_dir = roc_auc_score(B.loc[~bt, "dir"] > 0, dir_m.predict_proba(B.loc[~bt, FEATS])[:, 1])
    lines.append(f"B2 DIRECTION (among bursts) - holdout AUC {auc_dir:.3f}")
    dsing = []
    for c in ("r1", "r5", "r15", "r30", "r60", "r300", "imb10"):
        a = roc_auc_score(B.loc[~bt, "dir"] > 0, B.loc[~bt, c])
        dsing.append(f"{c} {a:.3f}")
    lines.append("   signed single features: " + ", ".join(dsing))
    lines.append("")
    # the BOT on holdout days
    thr = {q: np.quantile(occ_m.predict_proba(D.loc[tu & (D.w > 1), FEATS])[:, 1], q) for q in (0.995, 0.999)}
    lines.append("B3 THE BOT (holdout days): enter 1 s after the occurrence score passes the tune days' threshold, direction from the "
                 "direction model; race +-7 at the real price")
    res_bot = {}
    for q, th in thr.items():
        pts, rnd = [], []
        for d in [x for x in days if x >= cut]:
            F, (g, gm, gsp) = day_frame(*cache[d])
            pr = occ_m.predict_proba(F[FEATS])[:, 1]
            sd = np.where(dir_m.predict_proba(F[FEATS])[:, 1] > 0.5, 1, -1)
            i, free = 0, -1
            for i in np.flatnonzero(pr >= th):
                if i <= free or i + 2 >= len(g):
                    continue
                pnl, dur = race(gm, gsp, i + 1, int(sd[i]))
                pts.append(pnl)
                rnd.append(race(gm, gsp, i + 1, int(rng.choice([-1, 1])))[0])
                free = i + 1 + dur
        pts, rnd = np.array(pts), np.array(rnd)
        res_bot[q] = pts.mean() if len(pts) else np.nan
        lines.append(f"   top {100 - q * 100:.1f}%: {len(pts)} trades | won {np.mean(pts >= X) * 100:.1f}% | net {pts.mean():+.2f} points a trade "
                     f"(t {pts.mean() / (pts.std(ddof=1) / np.sqrt(len(pts))):+.1f}) | random side at the same seconds: won "
                     f"{np.mean(rnd >= X) * 100:.1f}%, {rnd.mean():+.2f}")
    lines.append("")
    # HIS clicks on both models
    from backtest.his_headlines import clicks
    C = clicks()
    N = C[C.kind == "NASDAQ"]
    pct, agree, rows = [], [], []
    for r in N.itertuples():
        et = r.utc.tz_localize("UTC").tz_convert("America/New_York")
        d = pd.Timestamp(et.date())
        if d not in cache or cache[d] is None:
            continue
        F, (g, gm, gsp) = day_frame(*cache[d])
        tsec = (et - et.normalize()).total_seconds() - 9.5 * 3600
        i = np.searchsorted(g, tsec, "right") - 1 - 1                     # the second before his click
        if i < 0 or i >= len(F):
            continue
        pr = occ_m.predict_proba(F[FEATS])[:, 1]
        lo, hi = np.searchsorted(g, tsec - 1200), np.searchsorted(g, tsec + 1200)
        pct.append(float((pr[lo:hi] < pr[i]).mean()))
        side = 1 if r.side == "BUY" else -1
        pdir = dir_m.predict_proba(F[FEATS].iloc[[i]])[:, 1][0]
        agree.append((pdir > 0.5) == (side > 0))
        rows.append((r.utc, side, pr[i], pct[-1], pdir))
    lines.append(f"B4 HIS {len(pct)} NASDAQ clicks: occurrence-score percentile within his own +-20-minute window: median "
                 f"{np.median(pct) * 100:.0f} (top quintile {np.mean(np.array(pct) >= 0.8) * 100:.0f}% of clicks) | direction "
                 f"model agrees with his side {np.mean(agree) * 100:.0f}%")
    lines.append("")
    lines.append("REGISTERED PREDICTIONS")
    lines.append(f"  B1 occurrence AUC {auc_occ:.3f} >= 0.70 -> {'RIGHT' if auc_occ >= 0.70 else 'WRONG'}")
    lines.append(f"  B2 direction AUC {auc_dir:.3f} <= 0.55 -> {'RIGHT' if auc_dir <= 0.55 else 'WRONG'}")
    lines.append(f"  B3 bot net <= 0 at both thresholds: " + ", ".join(f"{v:+.2f}" for v in res_bot.values()) +
                 f" -> {'RIGHT' if all(v <= 0 for v in res_bot.values()) else 'WRONG'}")
    lines.append(f"  B4 his median percentile {np.median(pct) * 100:.0f} (>= 70?), direction agreement {np.mean(agree) * 100:.0f}% (<= 60?) -> "
                 f"{'RIGHT' if np.median(pct) >= 0.7 and np.mean(agree) <= 0.6 else 'WRONG'}")
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

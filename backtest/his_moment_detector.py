"""s105 - THE MOMENT DETECTOR: are his ENTRY MOMENTS visually separable from the other minutes of his own sittings? (2026-11-22)

THE USER (2026-11-22, the last four forensic tests): almost every earlier test tried to predict DIRECTION across all minutes. This one asks a
narrower question - does the chart SHAPE before his click look like the shape before his OTHER clicks, more than the other minutes of the same
sitting do? If it does (leave-one-day-out AUC >= 0.70), the frozen detector is run on unseen tick days; if it does not, chart-pattern hunting is
closed.

DATA (on disk, nothing bought or downloaded)
  clicks   his 46 statement NASDAQ entries (his_tape.entries: statement clock UTC+4 before 2026-03-29, UTC+5 after) + the 4 October entries
           (his_cme_new.CLICKS, UTC+5) = 50. The 3 pre-market clicks of 2026-11-12 are NOT covered: the CME minute file ends 2026-10-29 and the
           Exness tick caches start at 09:30 New York.
  bars     CME NQ 1-minute OHLCV with real volume (strategy_analysis/data/nq_1m/NQ_2026.parquet), per UTC day the contract with the most volume
           that day (no roll inside a lookback), missing minutes filled flat with zero volume.
  sittings 22 minutes before to 20 minutes after each click, merged (his_tape.windows).
SAMPLES at a decision second T (closed bars only - the forming candle is left out on purpose: its length would encode the 5-24 s timing that
  s73 already found, which is not chart shape)
  seq15 / seq30   the last 15 / 30 closed 1-minute bars; per bar: path (close - last close) / ATR, range / ATR, body / ATR, log(volume / the
                  window's mean volume); ATR = mean true range of the last 14 one-minute bars
  seq5m           the last 12 closed 5-minute bars (one hour), the same four features on the 5-minute ATR
  orientation     path and body flip sign for a sell; every reference click is read from HIS side, every candidate in both orientations and
                  the better one kept (so a sell setup matches a mirrored buy setup), and the better orientation is the candidate's implied side
  positives       his 50 clicks; negatives: 5,000 random seconds of his sittings (none within 60 s of a click), and separately every minute of
                  his sittings at second 14 (his median click second) - one sample per distinct minute
DETECTORS (leave-one-DAY-out: a sample of day d is compared only with his clicks of OTHER days)
  A  DTW k-NN: banded dynamic time warping (band 3 / 5 / 2 bars) on seq15, seq30, seq5m; score = -mean of the k smallest distances, k = 3.
     Combined = the sum of the three distances, each z-scored over all pairs. PRIMARY = combined, k = 3.
  B  cosine: one multi-scale vector (15 one-minute returns, ranges and volumes; the 30-bar path every 3rd bar; 12 five-minute returns, ranges
     and volumes), each column scaled on all samples (direction columns not centred, so mirroring stays a sign flip); score = mean of the 3
     highest cosine similarities to other-day clicks.
  Image embeddings: no image model is available locally (torchvision is not installed, no cached weights) and none was downloaded.
SCORING  within-day AUC (his clicks of day d against that day's negatives, weighted by clicks - day-level differences cannot leak in) is the
  primary number; the pooled AUC of all held-out scores is printed beside it; 90% intervals by resampling days.
POWER CHECK (planted): in each sitting the one negative that best fits a textbook setup (a 15-bar move of >= 2.5 ATR, then a 3-bar pullback of
  >= 0.75 ATR against it) is made a pseudo-click, side = the 15-bar move, and the same pipeline is run with his real clicks removed. Also at 70%
  purity (3 in 10 pseudo-clicks replaced by random sitting seconds). If the pipeline cannot see a planted setup, a null on his clicks means
  nothing.
CONDITIONAL STEP (only if the PRIMARY within-day AUC >= 0.70): the frozen detector (references = all 50 clicks) scores every minute (second 14)
  of 10:00-16:00 New York on the tick days with no click of his, the top 0.05% are traded on his implied side, +-7 race at the Exness quote.

REGISTERED BEFORE THE FIRST RUN (2026-11-22)
  M1  PRIMARY (DTW combined, k 3) within-day AUC 0.42-0.58; no detector variant (A at any scale / k, B) reaches 0.70.        (85%)
  M2  The planted setup is recovered: within-day AUC >= 0.80 clean and >= 0.65 at 70% purity - the pipeline can see a shape.   (70%)
  M3  The nearest click's implied side agrees with HIS side on his own clicks within 40-62% (chart shape carries no side).      (75%)
  M4  The conditional step does not run (follows from M1).                                                                     (85%)
  If M1 holds and M2 holds, chart shape does not identify his moments and chart-pattern hunting is closed for good.

RESULT (2026-11-22, logs/his_moment_detector.txt) - CHART SHAPE DOES NOT IDENTIFY HIS MOMENTS. M1-M4 right.
  50 clicks (46 statement + 4 October; the 3 pre-market clicks of 11-12 have no minute bars on disk), 33 sittings, 5,000 random sitting seconds
  and 1,365 distinct sitting minutes. PRIMARY (DTW combined, k 3) within-day AUC 0.484 (90% 0.416-0.559), pooled 0.504; the best of all 7
  variants 0.532 (DTW on the 12 five-minute bars, 90% 0.435-0.611); against every minute of his sittings the same (0.43-0.53).
  The pipeline is NOT blind: a planted pullback-in-trend setup (14 pseudo-clicks, fewer than his 50) is found at 0.842 clean and 0.821 at 70%
  purity (DTW on the last 15 one-minute bars 0.953 / 0.875).
  Implied side: the nearest other-day click's orientation matches his side 64% (DTW) / 38% (cosine) against 36-64% / 34-66% with his sides
  shuffled (p 0.11 / 0.23). The table's cosine 26% becomes 38% under another column scaling: nearest-neighbour 'hub' noise, not a signal.
  Conditional step not run. No image model is available locally. His entry minutes look like the other minutes of his own sittings: chart-
  pattern hunting on his moments is closed.

    python -m backtest.his_moment_detector
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "strategy_analysis" / "data"
NQ = DATA / "nq_1m" / "NQ_2026.parquet"
LOG = ROOT / "logs" / "his_moment_detector.txt"
CME_END = pd.Timestamp("2026-10-30")
N_RANDOM, SEED, K = 5000, 105, 3
BANDS = {"seq15": 3, "seq30": 5, "seq5m": 2}
FW = np.array([1.0, 0.5, 0.5, 0.5])            # feature weights in the DTW cost: path, range, body, volume
DIRF = np.array([1.0, 0.0, 1.0, 0.0])          # which features flip sign with the side


# ----------------------------------------------------------------------------------------------------------------- data
def clicks() -> pd.DataFrame:
    import backtest.his_tape as TP
    from backtest.his_cme_new import clicks as new_clicks
    x = TP.entries()
    a = pd.DataFrame({"utc": x.utc.to_numpy(), "s": x.s.to_numpy(), "src": "statement"})
    n = new_clicks()
    n = n[n.t < CME_END]
    b = pd.DataFrame({"utc": n.t.to_numpy(), "s": n.s.to_numpy(), "src": "new"})
    c = pd.concat([a, b], ignore_index=True).sort_values("utc", kind="stable").reset_index(drop=True)
    c["day"] = c.utc.dt.normalize()
    return c


def sittings(c: pd.DataFrame) -> list:
    w = sorted((t - pd.Timedelta(minutes=22), t + pd.Timedelta(minutes=20)) for t in c.utc)
    out = []
    for a, b in w:
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def load_bars(days) -> dict:
    """{UTC day: DataFrame indexed by every minute 00:00-23:59 UTC, columns o h l c v} for the day's most traded contract."""
    d = pd.read_parquet(NQ)
    d["ts"] = d.ts_event.dt.tz_convert("UTC").dt.tz_localize(None)
    d["day"] = d.ts.dt.normalize()
    d = d[d.day.isin(set(days))]
    out = {}
    for day, g in d.groupby("day"):
        front = g.groupby("instrument_id").volume.sum().idxmax()
        g = g[g.instrument_id == front].drop_duplicates("ts").set_index("ts").sort_index()
        idx = pd.date_range(day, day + pd.Timedelta(hours=23, minutes=59), freq="1min")
        g = g.reindex(idx)
        c = g.close.ffill().bfill()
        g["c"] = c
        g["o"] = g.open.fillna(c)
        g["h"] = g.high.fillna(c)
        g["l"] = g.low.fillna(c)
        g["v"] = g.volume.fillna(0).astype(float)
        out[day] = g[["o", "h", "l", "c", "v"]].to_numpy(float)
    return out


# --------------------------------------------------------------------------------------------------------------- features
def _feat(o, h, l, c, v, atr):
    """(n, 4) per-bar features: path to the last close, range, body (all in ATR), log volume ratio."""
    path = (c - c[-1]) / atr
    rng = (h - l) / atr
    body = (c - o) / atr
    lv = np.log((v + 1.0) / (v.mean() + 1.0))
    return np.stack([path, rng, body, lv], axis=1)


def _tr(o, h, l, c):
    pc = np.concatenate([[o[0]], c[:-1]])
    return np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))


def sample(bars: dict, T: pd.Timestamp):
    """Features at decision second T (UTC) from CLOSED bars only, or None if the history is incomplete."""
    day = T.normalize()
    B = bars.get(day)
    if B is None:
        return None
    i0 = int((T.floor("min") - day) / pd.Timedelta(minutes=1))          # the forming minute's index; closed bars are [:i0]
    if i0 < 80:
        return None
    o, h, l, c, v = (B[:i0, k] for k in range(5))
    tr = _tr(o, h, l, c)
    atr = tr[-14:].mean()
    if not np.isfinite(atr) or atr <= 0:
        return None
    s15 = _feat(o[-15:], h[-15:], l[-15:], c[-15:], v[-15:], atr)
    s30 = _feat(o[-30:], h[-30:], l[-30:], c[-30:], v[-30:], atr)
    j = i0 - i0 % 5                                                        # closed 5-minute bars end at j
    if j < 70:
        return None
    o5 = B[j - 60:j, 0].reshape(12, 5)[:, 0]
    h5 = B[j - 60:j, 1].reshape(12, 5).max(1)
    l5 = B[j - 60:j, 2].reshape(12, 5).min(1)
    c5 = B[j - 60:j, 3].reshape(12, 5)[:, -1]
    v5 = B[j - 60:j, 4].reshape(12, 5).sum(1)
    atr5 = _tr(o5, h5, l5, c5).mean()
    if not np.isfinite(atr5) or atr5 <= 0:
        return None
    s5 = _feat(o5, h5, l5, c5, v5, atr5)
    ret15 = np.diff(c[-16:]) / atr
    vec_dir = np.concatenate([ret15, s30[::3, 0], (c5 - o5) / atr5])
    vec_non = np.concatenate([s15[:, 1], s15[:, 3], s5[:, 1], s5[:, 3]])
    return dict(seq15=s15, seq30=s30, seq5m=s5, vdir=vec_dir, vnon=vec_non,
                tr15=(c[-1] - c[-16]) / atr, pb3=(c[-1] - c[-4]) / atr)


# ------------------------------------------------------------------------------------------------------------------ DTW
def dtw_matrix(A: np.ndarray, B: np.ndarray, band: int, chunk_pairs: int = 120_000) -> np.ndarray:
    """Banded DTW distance between every sequence in A (na, L, F) and every one in B (nb, L, F); squared weighted cost."""
    na, L, F = A.shape
    nb = B.shape[0]
    out = np.empty((na, nb), np.float32)
    step = max(1, chunk_pairs // nb)
    for s0 in range(0, na, step):
        a = A[s0:s0 + step].astype(np.float32)
        n = len(a)
        INF = np.float32(1e18)
        prev = np.full((n, nb, L + 1), INF, np.float32)
        prev[:, :, 0] = 0.0
        for i in range(1, L + 1):
            cur = np.full((n, nb, L + 1), INF, np.float32)
            lo, hi = max(1, i - band), min(L, i + band)
            for jj in range(lo, hi + 1):
                d = a[:, None, i - 1, :] - B[None, :, jj - 1, :]
                cost = (d * d * FW.astype(np.float32)).sum(-1)
                best = np.minimum(np.minimum(prev[:, :, jj], prev[:, :, jj - 1]), cur[:, :, jj - 1])
                cur[:, :, jj] = cost + best
            if i == 1:
                cur[:, :, 0] = INF
            prev = cur
        out[s0:s0 + n] = prev[:, :, L]
    return out


def oriented(seq: np.ndarray, side) -> np.ndarray:
    """seq (n, L, F) read from side (+1 buy / -1 sell): direction features times the side."""
    side = np.asarray(side, float).reshape(-1, 1, 1)
    return seq * np.where(DIRF[None, None, :] > 0, side, 1.0)


# --------------------------------------------------------------------------------------------------------------- scoring
def auc(pos, neg) -> float:
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if not len(pos) or not len(neg):
        return np.nan
    allv = np.concatenate([pos, neg])
    r = pd.Series(allv).rank().to_numpy()
    return (r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def within_day_auc(score, label, day, rng=None, n_boot=2000):
    D = pd.DataFrame(dict(sc=score, y=label, d=day))
    per = []
    for d, g in D.groupby("d"):
        p, n = g.sc[g.y == 1].to_numpy(), g.sc[g.y == 0].to_numpy()
        if len(p) and len(n) >= 5:
            per.append((auc(p, n), len(p)))
    a = np.array(per)
    est = np.average(a[:, 0], weights=a[:, 1])
    lo = hi = np.nan
    if rng is not None and len(a) > 3:
        bs = []
        for _ in range(n_boot):
            k = rng.integers(0, len(a), len(a))
            bs.append(np.average(a[k, 0], weights=a[k, 1]))
        lo, hi = np.percentile(bs, [5, 95])
    return est, lo, hi, len(a)


def pooled_auc(score, label, day, rng=None, n_boot=2000):
    score, label, day = np.asarray(score), np.asarray(label), np.asarray(day)
    est = auc(score[label == 1], score[label == 0])
    lo = hi = np.nan
    if rng is not None:
        days = np.unique(day)
        idx = {d: np.flatnonzero(day == d) for d in days}
        bs = []
        for _ in range(n_boot):
            pick = rng.choice(days, len(days))
            ii = np.concatenate([idx[d] for d in pick])
            bs.append(auc(score[ii][label[ii] == 1], score[ii][label[ii] == 0]))
        lo, hi = np.percentile(bs, [5, 95])
    return est, lo, hi


def detector_scores(S: list, refs: list, k: int = K):
    """For samples S and reference clicks refs (dicts with seq*, vdir, vnon, day, s): leave-one-day-out scores.
    Returns {name: (score array, implied side array)}."""
    qday = np.array([q["day"] for q in S])
    rday = np.array([r["day"] for r in refs])
    rs = np.array([r["s"] for r in refs], float)
    mask = qday[:, None] != rday[None, :]                                  # True = allowed (other day)
    out = {}
    dist = {}
    for name, band in BANDS.items():
        Q = np.stack([q[name] for q in S])
        R = oriented(np.stack([r[name] for r in refs]), rs)
        dp = dtw_matrix(oriented(Q, np.ones(len(Q))), R, band)
        dm = dtw_matrix(oriented(Q, -np.ones(len(Q))), R, band)
        dist[name] = (dp, dm)
    zsum_p = zsum_m = 0.0
    for name in BANDS:
        dp, dm = dist[name]
        both = np.concatenate([dp[mask], dm[mask]])
        mu, sd = both.mean(), both.std()
        zsum_p = zsum_p + (dp - mu) / sd
        zsum_m = zsum_m + (dm - mu) / sd
    dist["combined"] = (zsum_p, zsum_m)
    for name, (dp, dm) in dist.items():
        dmin = np.minimum(dp, dm)
        side = np.where(dp <= dm, 1, -1)
        dmin = np.where(mask, dmin, np.inf)
        for kk in ((1, 3, 5) if name == "combined" else (k,)):
            part = np.sort(dmin, axis=1)[:, :kk]
            sc = -part.mean(1)
            nn = np.argmin(dmin, axis=1)
            out[f"DTW {name} k{kk}"] = (sc, side[np.arange(len(S)), nn])
    # cosine on the multi-scale vector
    Vd = np.stack([q["vdir"] for q in S])
    Vn = np.stack([q["vnon"] for q in S])
    Rd = np.stack([r["vdir"] for r in refs]) * rs[:, None]
    Rn = np.stack([r["vnon"] for r in refs])
    allD = np.concatenate([Vd, np.stack([r["vdir"] for r in refs])])
    allN = np.concatenate([Vn, Rn])
    sdD = np.sqrt((allD ** 2).mean(0)) + 1e-9
    muN, sdN = allN.mean(0), allN.std(0) + 1e-9

    def unit(d, n):
        v = np.concatenate([d / sdD, (n - muN) / sdN], axis=1)
        return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-12)
    Rv = unit(Rd, Rn)
    cp = unit(Vd, Vn) @ Rv.T
    cm = unit(-Vd, Vn) @ Rv.T
    cmax = np.where(mask, np.maximum(cp, cm), -np.inf)
    sidec = np.where(cp >= cm, 1, -1)
    top = -np.sort(-cmax, axis=1)[:, :K]
    nn = np.argmax(cmax, axis=1)
    out[f"cosine multi-scale top{K}"] = (top.mean(1), sidec[np.arange(len(S)), nn])
    return out


# ------------------------------------------------------------------------------------------------------------------ main
def build(c, bars, rng):
    wins = sittings(c)
    ct = c.utc.to_numpy().astype("datetime64[s]").astype(np.int64)
    pos = []
    for r in c.itertuples():
        f = sample(bars, r.utc)
        if f is not None:
            pos.append(dict(f, day=r.day, s=int(r.s), utc=r.utc, y=1, win=-1))
    total = np.array([(b - a).total_seconds() for a, b in wins])
    neg, tries = [], 0
    while len(neg) < N_RANDOM and tries < N_RANDOM * 20:
        tries += 1
        w = rng.choice(len(wins), p=total / total.sum())
        a, b = wins[w]
        T = a + pd.Timedelta(seconds=float(rng.uniform(0, (b - a).total_seconds())))
        T = T.floor("s")
        if np.min(np.abs(ct - T.value // 10**9)) < 60:
            continue
        f = sample(bars, T)
        if f is not None:
            neg.append(dict(f, day=T.normalize(), s=0, utc=T, y=0, win=w))
    mins = []
    for w, (a, b) in enumerate(wins):
        for m in pd.date_range(a.ceil("min"), b.floor("min"), freq="1min"):
            T = m + pd.Timedelta(seconds=14)
            if T > b or np.min(np.abs(ct - T.value // 10**9)) < 60:
                continue
            f = sample(bars, T)
            if f is not None:
                mins.append(dict(f, day=T.normalize(), s=0, utc=T, y=0, win=w))
    return wins, pos, neg, mins


def evaluate(pos, negs, rng, label):
    S = pos + negs
    sc = detector_scores(S, pos)
    y = np.array([q["y"] for q in S])
    d = np.array([q["day"] for q in S])
    rows = []
    for name, (score, side) in sc.items():
        w = within_day_auc(score, y, d, rng)
        p = pooled_auc(score, y, d, rng)
        agree = np.nan
        if label == "his":
            hs = np.array([q["s"] for q in pos])
            agree = float(np.mean(side[:len(pos)] == hs))
        rows.append(dict(detector=name, within=w[0], w_lo=w[1], w_hi=w[2], days=w[3], pooled=p[0], p_lo=p[1], p_hi=p[2], side_agree=agree))
    return pd.DataFrame(rows), sc


def planted(neg, rng, purity=1.0):
    """One pseudo-click per sitting: the negative that best fits a pullback-in-trend setup."""
    by = {}
    for q in neg:
        by.setdefault(q["win"], []).append(q)
    P, rest = [], []
    for w, qs in by.items():
        cand = [q for q in qs if abs(q["tr15"]) >= 2.5 and q["pb3"] * np.sign(q["tr15"]) <= -0.75]
        if not cand:
            rest += qs
            continue
        best = max(cand, key=lambda q: abs(q["tr15"]) - 2 * q["pb3"] * np.sign(q["tr15"]))
        if rng.uniform() > purity:
            best = qs[rng.integers(0, len(qs))]
        P.append(dict(best, y=1, s=int(np.sign(best["tr15"])) or 1))
        tb = best["utc"].value
        rest += [q for q in qs if abs(q["utc"].value - tb) >= 60 * 10**9]
    rest = [dict(q, y=0) for q in rest]
    return P, rest


def side_permutation(pos, n_perm, rng):
    """Implied-side agreement on his clicks (nearest other-day click, both detectors) against his sides shuffled among the clicks.
    DTW(c * q, s_r * r) depends only on c * s_r, so the raw distances are computed once and every shuffle is cheap."""
    n = len(pos)
    d = np.array([q["day"] for q in pos])
    s = np.array([q["s"] for q in pos])
    mask = d[:, None] != d[None, :]
    Zp = Zm = 0.0
    for name, band in BANDS.items():
        Q = np.stack([q[name] for q in pos])
        Dp = dtw_matrix(Q, Q, band)
        Dm = dtw_matrix(oriented(Q, -np.ones(n)), Q, band)
        both = np.concatenate([Dp[mask], Dm[mask]])
        Zp = Zp + (Dp - both.mean()) / both.std()
        Zm = Zm + (Dm - both.mean()) / both.std()
    Vd = np.stack([q["vdir"] for q in pos])
    Vn = np.stack([q["vnon"] for q in pos])
    sdD = np.sqrt((Vd ** 2).mean(0)) + 1e-9
    muN, sdN = Vn.mean(0), Vn.std(0) + 1e-9

    def unit(dd, nn):
        v = np.concatenate([dd / sdD, (nn - muN) / sdN], axis=1)
        return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-12)
    U = unit(Vd, Vn)
    Cp, Cm = U @ U.T, unit(-Vd, Vn) @ U.T
    ar = np.arange(n)

    def agree(sides):
        sr = sides[None, :]
        dplus, dminus = np.where(sr == 1, Zp, Zm), np.where(sr == 1, Zm, Zp)
        nn = np.argmin(np.where(mask, np.minimum(dplus, dminus), np.inf), axis=1)
        a1 = np.mean(np.where(dplus[ar, nn] <= dminus[ar, nn], 1, -1) == sides)
        cplus, cminus = np.where(sr == 1, Cp, Cm), np.where(sr == 1, Cm, Cp)
        nn2 = np.argmax(np.where(mask, np.maximum(cplus, cminus), -np.inf), axis=1)
        a2 = np.mean(np.where(cplus[ar, nn2] >= cminus[ar, nn2], 1, -1) == sides)
        return a1, a2
    obs = np.array(agree(s))
    null = np.array([agree(rng.permutation(s)) for _ in range(n_perm)])
    pv = np.mean(np.abs(null - 0.5) >= np.abs(obs - 0.5) - 1e-12, axis=0)
    return obs, null, pv


def fmt(df, title):
    L = [title, f"  {'detector':<26}{'within-day AUC':>16}{'90% (days)':>18}{'pooled AUC':>12}{'90%':>16}{'side agree':>12}"]
    for r in df.itertuples():
        sa = f"{r.side_agree:>11.0%}" if np.isfinite(r.side_agree) else f"{'':>11}"
        L.append(f"  {r.detector:<26}{r.within:>16.3f}  {r.w_lo:.3f}-{r.w_hi:.3f} ({r.days:>2}){r.pooled:>12.3f}  {r.p_lo:.3f}-{r.p_hi:.3f}{sa}")
    return L


def conditional(c, bars, pos, rng):
    """Frozen detector on unseen tick days: top 0.05% of minutes, his implied side, +-7 race at the quote."""
    from backtest.his_copy_delay import net_race
    ticks = pickle.loads((DATA / "ustec_tick_days.pkl").read_bytes())
    click_days = set(pd.to_datetime(c.utc).dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None))
    bars = load_bars(sorted(d for d, v in ticks.items() if v is not None and d not in click_days and d < CME_END))
    cand = []
    for d, v in ticks.items():
        if v is None or d in click_days:
            continue
        for m in pd.date_range(d + pd.Timedelta(hours=10), d + pd.Timedelta(hours=15, minutes=59), freq="1min"):
            T_ny = m + pd.Timedelta(seconds=14)
            T = T_ny.tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)
            f = sample(bars, T)
            if f is not None:
                cand.append(dict(f, day=pd.Timestamp("1900-01-01"), s=0, utc=T, y=0, nyday=d, t=(T_ny - d - pd.Timedelta(hours=9, minutes=30)).total_seconds()))
    sc = detector_scores(cand, pos)
    score, side = sc["DTW combined k3"]
    k = max(1, int(round(len(cand) * 0.0005)))
    top = np.argsort(-score)[:k]
    res = []
    for i in top:
        q = cand[i]
        ts, mid, spr = ticks[q["nyday"]]
        res.append(net_race(ts, mid, spr, q["t"], int(side[i])))
    res = [r for r in res if r is not None]
    return len(cand), k, (np.mean(res) if res else np.nan), len(res)


def main():
    rng = np.random.default_rng(SEED)
    c = clicks()
    bars = load_bars(sorted(set(c.day) | {d - pd.Timedelta(days=1) for d in c.day}))
    wins, pos, neg, mins = build(c, bars, rng)
    L = [f"backtest/his_moment_detector.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC (s105)",
         f"clicks with CME minute bars: {len(pos)} of {len(c)} (statement {sum(1 for p in pos if p['utc'] < pd.Timestamp('2026-10-01'))}, "
         f"October {sum(1 for p in pos if p['utc'] >= pd.Timestamp('2026-10-01'))}); the 3 pre-market clicks of 2026-11-12 have no minute bars on disk",
         f"sittings: {len(wins)} windows, {sum((b - a).total_seconds() for a, b in wins) / 60:.0f} minutes; negatives: {len(neg)} random seconds, "
         f"{len(mins)} distinct minutes (at second 14); days with clicks: {len({p['day'] for p in pos})}", ""]
    R1, sc1 = evaluate(pos, neg, rng, "his")
    L += fmt(R1, "1. HIS CLICKS vs 5,000 RANDOM SECONDS OF HIS SITTINGS (leave-one-day-out; side agree = nearest click's implied side = his side)")
    R2, _ = evaluate(pos, mins, rng, "his")
    L += [""] + fmt(R2, "2. HIS CLICKS vs EVERY OTHER MINUTE OF HIS SITTINGS (one sample per minute, second 14)")
    P, rest = planted(neg, rng, 1.0)
    R3, _ = evaluate(P, rest, rng, "planted")
    L += ["", f"3. POWER CHECK - a planted pullback-in-trend setup, one pseudo-click per sitting where one fits ({len(P)} pseudo-clicks, "
          f"{len(rest)} negatives; fewer positives than his 50, so this check is the harder one)"]
    L += fmt(R3, "   clean (100% purity)")
    P7, rest7 = planted(neg, np.random.default_rng(SEED + 1), 0.7)
    R4, _ = evaluate(P7, rest7, rng, "planted")
    L += fmt(R4, "   70% purity (3 in 10 pseudo-clicks are random sitting seconds)")
    obs, null, pv = side_permutation(pos, 2000, np.random.default_rng(SEED + 2))
    L += ["", "4. THE IMPLIED SIDE - does the nearest other-day click's orientation carry HIS side? (his sides shuffled among his clicks 2,000 "
          "times; nearest neighbours of a few 'hub' clicks make the binomial p wrong, the shuffle is the honest null)"]
    for j, nm in enumerate(("DTW combined (nearest)", "cosine multi-scale (nearest)")):
        L.append(f"  {nm:<30} agreement {obs[j]:.0%}; shuffled sides: median {np.median(null[:, j]):.0%}, 90% range "
                 f"{np.percentile(null[:, j], 5):.0%}-{np.percentile(null[:, j], 95):.0%}; two-sided p {pv[j]:.3f}")
    prim = R1[R1.detector == "DTW combined k3"].iloc[0]
    best = R1.within.max()
    L += ["", "5. CONDITIONAL STEP (only if the PRIMARY within-day AUC >= 0.70)"]
    if prim.within >= 0.70:
        n, k, wr, nr = conditional(c, bars, pos, rng)
        L.append(f"  RUN: {n} unseen minutes, top {k} (0.05%), +-7 race at the quote won {wr:.0%} of {nr}")
    else:
        L.append(f"  NOT RUN: primary within-day AUC {prim.within:.3f} < 0.70 (best of all {len(R1)} variants {best:.3f})")
    agree = R1[R1.detector == "DTW combined k3"].side_agree.iloc[0]
    clean = R3[R3.detector == "DTW combined k3"].within.iloc[0]
    p70 = R4[R4.detector == "DTW combined k3"].within.iloc[0]
    L += ["", "PREDICTIONS",
          f"  M1 primary within-day AUC in 0.42-0.58 ({prim.within:.3f}) and no variant >= 0.70 (best {best:.3f}) -> "
          f"{'RIGHT' if 0.42 <= prim.within <= 0.58 and best < 0.70 else 'WRONG'}",
          f"  M2 planted recovered: clean >= 0.80 ({clean:.3f}), 70% purity >= 0.65 ({p70:.3f}) -> {'RIGHT' if clean >= 0.80 and p70 >= 0.65 else 'WRONG'}",
          f"  M3 implied side = his side in 40-62% of his clicks ({agree:.0%}) -> {'RIGHT' if 0.40 <= agree <= 0.62 else 'WRONG'}",
          f"  M4 conditional step not run -> {'RIGHT' if prim.within < 0.70 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    sys.exit(main())

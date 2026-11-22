"""IS THERE ANY STATE OF THE CME NQ BOOK AND TAPE THAT CALLS THE NEXT +-7 POINT RACE? - a bulk scan of every second, not just his clicks (2026-11-04)

The user, 2026-11-04: "must be something here we are missing in CME especially." Every earlier CME test (his_tape, his_book, his_fullbook, his_absorb, his_exact, his_loopholes, es_flow_mended) asked ONE feature at a time whether it points
his way at his 46 clicks (n = 25-46, so only a strong simple rule could show). The different question: is there ANY multi-feature state, at ANY second of the 31 windows (21.7 hours of real NQ data around his sittings), after which the next +-7
point race is won by one side far more often than 50%? His 95% is the extreme case of such a state. A model that finds none across every second says the CME feed (as far as these caches carry it) does not hold his information.

DATA (all cached, nothing bought; the user's remaining Databento credit is ~USD 26 and each purchase needs their OK): nq_bbo1s.pkl (NQ mid, one second), nq_book_1s.pkl (10 levels of bid / ask SIZES, one second), nq_trades_windows.pkl (every NQ trade
with its aggressor side), 31 windows of 42 minutes (22 before to 20 after each entry). Entries and sides from strategy_analysis/statement_trades.csv (his_tape.entries).
LABEL    at second i: entry at the mid two seconds later (a conservative lag), +1 if the mid reaches entry + 7 points before entry - 7 within 240 s, -1 the other way, dropped if neither.
FEATURES at second i, from data up to i only: mid moves over 1 / 2 / 5 / 10 / 30 / 60 / 120 s (points), 30 / 120 s volatility, position in the last 5 / 15 minutes' range, book imbalance over the best 1 / 3 / 5 / 10 levels and its 5-s change, depth,
         signed aggressor volume over 1 / 2 / 5 / 10 / 30 / 60 s, normalised flow over 30 / 60 s, trade counts, big-trade (>= 5 lots) flow, last aggressor, seconds since the last trade, minutes since the open.
MODEL    gradient boosting (shallow), leave-one-WINDOW-out (31 folds): every prediction comes from a model that never saw that window.
REPORTED pooled out-of-sample AUC; accuracy in the most confident 20% / 10% / 5% of seconds, all seconds and THINNED (one event per 60 s per window - neighbouring seconds are the same race); the model at his 46 click seconds (agreement with his
         side, and whether the label machinery reproduces his wins); simple one-feature benchmarks.
THE BAR  A trade at Exness costs ~2.2 points: with +-7 points won or lost, the side must be right 0.5 + 2.16/14 = 65% of the time to break even. 95% is his.

REGISTERED BEFORE THE FIRST RUN (2026-11-04)
    S1  Pooled out-of-sample AUC is between 0.52 and 0.60.   (AMENDED after the first run: the pooled AUC of leave-one-window-out predictions is biased below 0.5 by the training up-rate; the within-window AUC is the number to read)
    S2  No confidence bucket with at least 100 thinned events reaches 65% accuracy (prior that one does: 7%).
    S3  At his click seconds the model agrees with his side 40-62% of the time (his side is not in the CME feed).
    S4  The label machinery is right: at his click seconds the race outcome equals his side at least 80% of the time (it should be ~90%+; this checks the timing and the sign, not an edge).

RESULT (2026-11-04, logs/his_cme_scan.txt; 31 windows = 22.7 hours, 66,806 labelled seconds, 32 features, leave-one-window-out gradient boosting)
    The CME feed, as these caches carry it, holds no state that calls the next +-7 point race. Mean WITHIN-WINDOW AUC 0.521 over 31 windows (standard error 0.018: 1.2 se from a coin flip; windows range 0.31-0.83). Most confident 20% / 10% / 5% of seconds, thinned to one event
    a minute: 48.5% (412 events) / 44.7% (219) / 42.3% (130) right; the two smaller buckets (50 and 28 events) are too small to read. Best bucket with >= 100 independent events: 48.5%, against the 65% an Exness trade needs and his ~95%. One-feature benchmarks: signed flow 50.3%,
    book imbalance 50.1-50.2%, last 30 s move 50.1%, last 60 s move 50.8%. At his 46 clicks (42 resolved): the label machinery reproduces his side 83% of the time (it sees HIS wins), while the CME model's call agrees with his side 45% (binomial p 0.64).
    A BUG OF MINE, found because a number was impossible: the first run printed a pooled AUC of 0.454 and confident buckets right only 38-42% of the time - below a coin flip. Cause: with leave-one-window-out the training up-rate moves opposite to the held-out window's, so pooled probabilities
    are anti-correlated with the outcome (the up-rate ALONE, no features, scores 0.389 pooled). Fixed: centre each fold on its training up-rate, read the within-window AUC. Predictions: S1 as registered (pooled AUC 0.52-0.60) was wrong because of that bias - amended after the run to the within-window AUC (0.521, inside the
    band by 0.001); S2, S3, S4 right.
    LIMITS: 31 windows hold ~1,300 independent races, so a model can learn only a state that recurs often; a rare, complex state is NOT excluded. Not in these caches: per-order data (the MBO was deleted; its features are kept), ES flow inside this model (single-feature ES tests died in es_flow_mended.py),
    other CME products (VIX futures, micro NQ, options on futures). More days would cost USD 0.80 a session (mbp-1) against a remaining credit of roughly USD 26 (no balance API); each purchase needs the user's OK.
    Tests: 11; 22 of 23 planted bugs caught (the survivor, a tie rule, is equivalent: a tie occurs only when neither barrier is reached). The first mutation pass left 8 survivors; each got a test (default settings, sells, big-trade threshold, partial tails, thinning across windows and order).

    python -m backtest.his_cme_scan          writes logs/his_cme_scan.txt        tests: python tests/test_his_cme_scan.py
"""
from __future__ import annotations

import pickle
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "strategy_analysis" / "data"
T_PTS, LAG, HORIZON, WARM, BIG = 7.0, 2, 240, 120, 5
MOVES = (1, 2, 5, 10, 30, 60, 120)
FLOWS = (1, 2, 5, 10, 30, 60)


def race_labels(mid, lag=LAG, horizon=HORIZON, t=T_PTS):
    """+1 / -1 / 0 per second i: which side of entry = mid[i+lag] is reached first within `horizon` seconds after the entry second (0 = neither, or not enough data)."""
    n = len(mid)
    out = np.zeros(n, dtype=np.int8)
    for i in range(n - lag - 1):
        p0 = mid[i + lag]
        seg = mid[i + lag + 1:i + lag + 1 + horizon]
        if len(seg) < horizon:
            continue
        up = np.flatnonzero(seg >= p0 + t)
        dn = np.flatnonzero(seg <= p0 - t)
        iu, idn = (up[0] if len(up) else horizon + 1), (dn[0] if len(dn) else horizon + 1)
        if iu == idn:
            continue
        out[i] = 1 if iu < idn else -1
    return out


def window_features(mid, book, tns, tsize, taggr, sec_ns, et_minutes):
    """Feature matrix (rows = seconds, columns = names) using only data up to and including each second. `book` has bid_sz_00..09 / ask_sz_00..09 per second."""
    n = len(mid)
    f = {}
    for k in MOVES:
        m = np.full(n, np.nan)
        m[k:] = mid[k:] - mid[:-k]
        f[f"m{k}"] = m
    d = np.r_[0.0, np.diff(mid)]
    for k in (30, 120):
        f[f"vol{k}"] = pd.Series(d).rolling(k).std().to_numpy()
    for k, nm in ((300, "pos5"), (900, "pos15")):
        hi, lo = pd.Series(mid).rolling(k, min_periods=60).max().to_numpy(), pd.Series(mid).rolling(k, min_periods=60).min().to_numpy()
        f[nm] = (mid - lo) / np.maximum(hi - lo, 1e-9)
    b = book[[f"bid_sz_{i:02d}" for i in range(10)]].to_numpy(float)
    a = book[[f"ask_sz_{i:02d}" for i in range(10)]].to_numpy(float)
    for L in (1, 3, 5, 10):
        bs, as_ = b[:, :L].sum(axis=1), a[:, :L].sum(axis=1)
        f[f"imb{L}"] = (bs - as_) / np.maximum(bs + as_, 1.0)
    f["dimb1"] = np.r_[np.full(5, np.nan), f["imb1"][5:] - f["imb1"][:-5]]
    f["depth"] = np.log1p(b.sum(axis=1) + a.sum(axis=1))
    sgn = np.r_[0, np.cumsum(tsize * taggr)]
    tot = np.r_[0, np.cumsum(tsize)]
    cnt = np.r_[0, np.arange(1, len(tns) + 1)]
    bgs = np.r_[0, np.cumsum(np.where(tsize >= BIG, tsize * taggr, 0))]
    j = np.searchsorted(tns, sec_ns, side="right")
    for k in FLOWS:
        i0 = np.searchsorted(tns, sec_ns - k * 10**9, side="right")
        f[f"flow{k}"] = (sgn[j] - sgn[i0]).astype(float)
        if k in (30, 60):
            f[f"nflow{k}"] = (sgn[j] - sgn[i0]) / np.maximum(tot[j] - tot[i0], 1)
    for k in (5, 30):
        i0 = np.searchsorted(tns, sec_ns - k * 10**9, side="right")
        f[f"ntr{k}"] = (cnt[j] - cnt[i0]).astype(float)
    for k in (30, 60):
        i0 = np.searchsorted(tns, sec_ns - k * 10**9, side="right")
        f[f"big{k}"] = (bgs[j] - bgs[i0]).astype(float)
    last = np.where(j > 0, taggr[np.maximum(j - 1, 0)], 0)
    f["lastaggr"] = last.astype(float)
    f["since"] = np.where(j > 0, np.minimum((sec_ns - tns[np.maximum(j - 1, 0)]) / 1e9, 60.0), 60.0)
    f["tod"] = et_minutes.astype(float)
    return pd.DataFrame(f)


def thin(conf, win, sec, gap=60):
    """Indices of the events kept when walking down by confidence and dropping any within `gap` seconds of a kept event in the same window."""
    order = np.argsort(-conf, kind="stable")
    kept, last = [], {}
    for i in order:
        w, s = win[i], sec[i]
        if any(abs(s - t) < gap for t in last.get(w, ())):
            continue
        last.setdefault(w, []).append(s)
        kept.append(i)
    return np.array(kept, dtype=int)


def bucket_accuracy(p, y, win, sec, q, gap=60):
    """Accuracy of the call sign(p - 0.5) among the most confident share q of seconds: (all seconds n, acc, thinned n, acc)."""
    conf = np.abs(p - 0.5)
    sel = np.flatnonzero(conf >= np.quantile(conf, 1 - q))
    right = (np.where(p > 0.5, 1, -1) == y)
    kept = sel[thin(conf[sel], win[sel], sec[sel], gap)]
    return len(sel), float(right[sel].mean()), len(kept), float(right[kept].mean()) if len(kept) else float("nan")


def centre(p, base):
    """Centre each fold's probabilities on its own training up-rate, so 0.5 means 'no better than the base rate'."""
    return p - base + 0.5


def mean_window_auc(yb, p, win_id, min_n=200):
    """AUC inside each window that has both outcomes and more than min_n labelled seconds; the list of them."""
    from sklearn.metrics import roc_auc_score
    return [roc_auc_score(yb[win_id == w], p[win_id == w]) for w in np.unique(win_id) if len(np.unique(yb[win_id == w])) == 2 and (win_id == w).sum() > min_n]


def load_all():
    from backtest import his_tape as TP
    bbo = pickle.loads((DATA / "nq_bbo1s.pkl").read_bytes())
    book = pickle.loads((DATA / "nq_book_1s.pkl").read_bytes())
    trd = pickle.loads((DATA / "nq_trades_windows.pkl").read_bytes())
    ent = TP.entries()
    wins = []
    for k in bbo:
        mid = bbo[k]
        mid = mid[~mid.index.duplicated()]
        idx = pd.DatetimeIndex(mid.index)
        bk = book[k].reindex(idx, method="ffill")
        T = trd[k].sort_values("ns")
        sec_ns = idx.as_unit("ns").asi8
        et = idx.tz_localize("UTC").tz_convert("America/New_York")
        etm = (et.hour * 60 + et.minute + et.second / 60.0 - 570).to_numpy()
        X = window_features(mid.to_numpy(float), bk, T["ns"].to_numpy(), T["size"].to_numpy(float), T["aggr"].to_numpy(float), sec_ns, etm)
        wins.append(dict(key=k, X=X, y=race_labels(mid.to_numpy(float)), start=idx[0], mid=mid.to_numpy(float), sec_ns=sec_ns))
    return wins, ent


def main():
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    warnings.filterwarnings("ignore")
    wins, ent = load_all()
    names = list(wins[0]["X"].columns)
    Xs, ys, ws, ss = [], [], [], []
    for w, win in enumerate(wins):
        keep = (win["y"] != 0) & (np.arange(len(win["y"])) >= WARM)
        Xs.append(win["X"].to_numpy()[keep]); ys.append(win["y"][keep]); ws.append(np.full(keep.sum(), w)); ss.append(np.flatnonzero(keep))
    X, y, win_id, sec = np.vstack(Xs), np.concatenate(ys), np.concatenate(ws), np.concatenate(ss)
    out = [f"backtest/his_cme_scan.py - {len(wins)} windows of NQ data ({sum(len(w['y']) for w in wins) / 3600:.1f} hours), {len(y):,} labelled seconds (race +-{T_PTS:g} points within {HORIZON} s, entry {LAG} s later); up wins {np.mean(y == 1) * 100:.1f}%; {len(names)} features; leave-one-window-out", ""]
    p = np.full(len(y), np.nan)
    base = np.full(len(y), np.nan)
    for w in range(len(wins)):
        te = win_id == w
        m = HistGradientBoostingClassifier(max_depth=3, max_iter=150, learning_rate=0.05, random_state=0)
        m.fit(X[~te], (y[~te] == 1).astype(int))
        p[te] = m.predict_proba(X[te])[:, 1]
        base[te] = np.mean(y[~te] == 1)
    yb = (y == 1).astype(int)
    out.append(f"POOLED AUC of the raw probabilities {roc_auc_score(yb, p):.3f}; of the training up-rate ALONE (no features at all) {roc_auc_score(yb, base):.3f}  <- below 0.5 by construction: holding a window out moves the other windows' up-rate the opposite way (the leave-one-out artifact). Evaluate within windows:")
    p = centre(p, base)
    aucs = mean_window_auc(yb, p, win_id)
    out.append(f"MEAN WITHIN-WINDOW AUC {np.mean(aucs):.3f} over {len(aucs)} windows (min {np.min(aucs):.3f}, max {np.max(aucs):.3f}; standard error of the mean {np.std(aucs) / np.sqrt(len(aucs)):.3f}); pooled AUC of the centred probabilities {roc_auc_score(yb, p):.3f}; accuracy of the centred call over all labelled seconds {np.mean(np.where(p > 0.5, 1, -1) == y) * 100:.1f}%")
    auc = float(np.mean(aucs))
    out.append(f"\n{'most confident share':>22}{'seconds':>9}{'acc':>7}{'thinned n':>11}{'acc':>7}   (the bar: 65% to beat the Exness spread; his: ~95%)")
    best = 0.0
    for q in (0.20, 0.10, 0.05, 0.02, 0.01):
        n, a, nt, at = bucket_accuracy(p, y, win_id, sec, q)
        out.append(f"{q * 100:>21.0f}%{n:>9}{a * 100:>6.1f}%{nt:>11}{at * 100:>6.1f}%" + ("   (fewer than 100 independent events: low power)" if nt < 100 else ""))
        if nt >= 100:
            best = max(best, at)
    out.append(f"   best accuracy among buckets with >= 100 thinned events: {best * 100:.1f}%")
    # one-feature benchmarks
    out.append("\nONE-FEATURE BENCHMARKS (call = sign of the feature, all labelled seconds; and following the last 30 s move):")
    for nm in ("flow30", "flow60", "imb1", "imb5", "m30", "m60"):
        v = X[:, names.index(nm)]
        ok = np.isfinite(v) & (v != 0)
        out.append(f"   {nm:<8} with the sign {np.mean(np.sign(v[ok]) == y[ok]) * 100:5.1f}%  (n {ok.sum():,})")
    imp = []
    # his clicks
    from backtest.his_tape import to_utc  # noqa: F401
    rows = []
    for e in ent.itertuples():
        t = pd.Timestamp(e.utc)
        for w, win in enumerate(wins):
            a, b = win["start"], win["start"] + pd.Timedelta(seconds=len(win["y"]) - 1)
            if a <= t <= b:
                i = int((t - a).total_seconds())
                r = np.flatnonzero((win_id == w) & (sec == i))
                lab = win["y"][i]
                rows.append((e.s, lab, p[r[0]] if len(r) else np.nan))
                break
    R = pd.DataFrame(rows, columns=["his", "label", "p"])
    lab_ok = R[R.label != 0]
    out.append(f"\nAT HIS {len(R)} CLICK SECONDS (inside the windows): the +-{T_PTS:g} race outcome equals his side in {np.mean(lab_ok.label == lab_ok.his) * 100:.0f}% of {len(lab_ok)} resolved clicks (S4: label machinery check)")
    rp = R.dropna(subset=["p"])
    agree = np.mean(np.where(rp.p > 0.5, 1, -1) == rp.his)
    out.append(f"   the CME model's call agrees with his side in {agree * 100:.0f}% of {len(rp)} clicks (50% = no information); mean confidence |p-0.5| at his clicks {np.mean(np.abs(rp.p - 0.5)):.3f} vs {np.mean(np.abs(p - 0.5)):.3f} at all seconds")
    from scipy.stats import binomtest
    out.append(f"   binomial p of that agreement against 50%: {binomtest(int(round(agree * len(rp))), len(rp), 0.5).pvalue:.2f}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_cme_scan.txt").write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

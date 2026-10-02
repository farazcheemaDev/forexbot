"""DOES HE READ THE BOOK? - the real CME NQ order book at his moments (Databento MBP-10).

WHY (his_strategy.md s36-s37)
    At his click he knows which way the next 1-5 minutes go (s36), and the real futures TRADE flow does not tell him
    (s37: 48-55% agreement, rank 0.48-0.54). What is left that a screen can show: the ORDER BOOK - resting size, not
    trades. Book imbalance (more size bid than offered, or liquidity pulled from one side) is a different signal from
    trade flow and, at seconds, a stronger one in the microstructure literature. A depth-of-market ladder is a common
    retail tool, so it is a plausible thing for him to watch.

DATA
    Databento GLBX.MDP3 `mbp-10` (every book update, 10 price levels a side), front-volume NQ, the same windows as
    his_tape.py (22 min before to 20 min after each entry), priced at $8.30 before download. Read in chunks and reduced
    to ONE snapshot per second (the last state in each second) - the raw stream never sits in memory or on disk.
    Cached per second under strategy_analysis/data/ (git-ignored: public repo, CME data). Aggregates only committed.

AT EACH MOMENT T (his entries and the same-sitting moments, as in his_tape.py), signed by the side (> 0 = his way):
    q1      top-of-book imbalance (bid size - ask size) / (bid + ask) at the best level, at T
    q1_30   q1 averaged over the 30 s before T
    d5      the same over the 5 best levels a side;  d10 over all 10
    pull30  liquidity pulled: change in 10-level ASK depth minus change in BID depth over the last 30 s, / depth
            (> 0 for a buy = offers being pulled faster than bids - the classic "the wall is gone" read)

TESTS (as his_tape.py)
    A. DIRECTION - does the book's lean agree with HIS side at his click?   (binomial vs 50%)
    B. TIMING    - is it leaning his way more at his moment than at the sitting's other moments?  (rank vs 0.50)
    C. A RULE    - at the sitting's moments, trade WITH a top-decile lean: does it win the +-7 race?

REGISTERED PREDICTIONS (2026-10-02, before any book data is fetched)
    1. A: 50-60% at every feature - after s37 I no longer expect the futures to carry his side.
    2. B: ranks 0.45-0.55.
    3. C: a top-decile book lean wins 50-55% of +-7 races - book imbalance predicts seconds, not 1-5 minutes.
    If any of A >= 75% with C >= 60%, the book is his source and a bot can read it too. If all hold near 50%, the
    futures market - trades and book - does not carry what he sees, and the remaining candidates are off-screen.

    python -m backtest.his_book
"""
from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backtest.his_tape as TP  # noqa: E402
from backtest.his_race_curve import race2  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "strategy_analysis" / "data" / "nq_book_1s.pkl"
SCHEMA = "mbp-10"
FEATS = ("q1", "q1_30", "d5", "d10", "pull30")


def reduce_window(store) -> pd.DataFrame:
    """MBP-10 stream -> one row per second (the last book state in that second): level sizes only."""
    bid = [f"bid_sz_{i:02d}" for i in range(10)]
    ask = [f"ask_sz_{i:02d}" for i in range(10)]
    parts = []
    it = store.to_df(count=250_000)
    for df in (it if not isinstance(it, pd.DataFrame) else [it]):
        df = df.reset_index()
        tcol = "ts_event" if "ts_event" in df.columns else df.columns[0]
        sec = pd.to_datetime(df[tcol], utc=True).dt.tz_localize(None).dt.floor("s")
        g = df[bid + ask].assign(sec=sec.to_numpy()).groupby("sec").last()
        parts.append(g)
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts)
    return out[~out.index.duplicated(keep="last")].sort_index().astype(np.float64)


def fetch(cl, wins):
    C = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
    need = [w for w in wins if (str(w[0]), str(w[1])) not in C]
    for i, (a, b) in enumerate(need, 1):
        store = cl.timeseries.get_range(dataset=TP.DATASET, symbols=[TP.SYMBOL], schema=SCHEMA, stype_in=TP.STYPE,
                                        start=a.isoformat() + "Z", end=b.isoformat() + "Z")
        C[(str(a), str(b))] = reduce_window(store)
        print(f"  fetched {i}/{len(need)} windows ({len(C[(str(a), str(b))]):,} seconds)", flush=True)
        CACHE.write_bytes(pickle.dumps(C))
    B = pd.concat(C.values())
    return B[~B.index.duplicated(keep="last")].sort_index()


def features(B, at: pd.Timestamp):
    """Book features at `at` (UTC, naive), unsigned; None if the book is not there."""
    k = B.index.searchsorted(at, side="right") - 1
    if k < 31:
        return None
    row = B.iloc[k]
    if (at - B.index[k]).total_seconds() > 5:
        return None
    bs = [row[f"bid_sz_{i:02d}"] for i in range(10)]
    as_ = [row[f"ask_sz_{i:02d}"] for i in range(10)]

    def imb(n, r_b=bs, r_a=as_):
        b, a = sum(r_b[:n]), sum(r_a[:n])
        return (b - a) / (b + a) if b + a > 0 else np.nan

    w = B.iloc[max(k - 30, 0):k + 1]
    q1w = ((w.bid_sz_00 - w.ask_sz_00) / (w.bid_sz_00 + w.ask_sz_00)).mean()
    old = B.iloc[max(k - 30, 0)]
    bid10_now, ask10_now = sum(bs), sum(as_)
    bid10_old = sum(old[f"bid_sz_{i:02d}"] for i in range(10))
    ask10_old = sum(old[f"ask_sz_{i:02d}"] for i in range(10))
    depth = (bid10_now + ask10_now + bid10_old + ask10_old) / 2
    pull = ((ask10_old - ask10_now) - (bid10_old - bid10_now)) / depth if depth > 0 else np.nan
    return dict(q1=imb(1), q1_30=q1w, d5=imb(5), d10=imb(10), pull30=pull)


def main(argv=None):
    from scipy.stats import binomtest, wilcoxon
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-usd", type=float, default=25.0)
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args(argv)
    x = TP.entries()
    wins = TP.windows(x)
    cl = TP.client()
    usd = 0.0
    for w0, w1 in wins:
        usd += float(cl.metadata.get_cost(dataset=TP.DATASET, symbols=[TP.SYMBOL], schema=SCHEMA, stype_in=TP.STYPE,
                                          start=w0.isoformat() + "Z", end=w1.isoformat() + "Z"))
    print(f"{len(wins)} windows of {TP.SYMBOL} {SCHEMA}: estimated cost ${usd:.2f}")
    if usd > a.max_usd and not a.go:
        sys.exit(f"over the ${a.max_usd:.0f} limit - rerun with --go to accept ${usd:.2f}")
    B = fetch(cl, wins)

    ticks = pickle.loads(TP.TICKS.read_bytes())
    rows = []
    for r in x.itertuples():
        day = ticks.get(r.d)
        if day is None or r.t < 960:
            continue
        ts, mid, _ = day
        base = (r.d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC")
        base = base.tz_localize(None)
        others = x[x.d == r.d].t.to_numpy()
        starts = [("his", r.t)] + [("near", r.t + 60 * m) for m in list(range(-20, 0)) + list(range(1, 21))
                                   if r.t + 60 * m > 960 and np.min(np.abs(others - (r.t + 60 * m))) >= 60]
        for who, t in starts:
            f = features(B, base + pd.Timedelta(seconds=float(t)))
            if f is None:
                continue
            rows.append(dict(entry=r.Index, who=who, s=r.s, race_up=race2(ts, mid, t, 1, 600, 7, 7), **f))
    D = pd.DataFrame(rows)
    H, N = D[D.who == "his"], D[D.who == "near"]
    out = [f"{len(H)} of his entries with the book in range; {len(N)} same-sitting moments; {len(B):,} one-second "
           f"book snapshots in {len(wins)} windows (aggregates only - raw data stays local)"]

    out.append("\nA. DIRECTION - does the book lean HIS way at his click?")
    out.append(f"  {'feature':>8}{'agrees':>9}{'p':>8}")
    for k in FEATS:
        v = (H[k] * H.s).dropna()
        v = v[v != 0]
        p = binomtest(int((v > 0).sum()), len(v), 0.5).pvalue if len(v) else np.nan
        out.append(f"  {k:>8}{(v > 0).mean():>8.0%}{p:>8.3f}")

    out.append("\nB. TIMING - his moment's lean (signed his way) ranked among the sitting's moments")
    out.append(f"  {'feature':>8}{'rank':>8}{'p':>8}")
    for k in FEATS:
        rk = []
        for e, g in D.groupby("entry"):
            h, n = g[g.who == "his"], g[g.who == "near"]
            if len(h) and len(n) >= 10 and np.isfinite(h[k].iat[0]):
                rk.append(((n[k] * n.s).dropna() < h[k].iat[0] * h.s.iat[0]).mean())
        p = wilcoxon(np.array(rk) - 0.5).pvalue if len(rk) > 5 else np.nan
        out.append(f"  {k:>8}{np.mean(rk):>8.2f}{p:>8.3f}")

    out.append("\nC. A RULE - at the sitting's moments, trade WITH a top-decile book lean")
    out.append(f"  {'feature':>8}{'race won':>10}{'n':>6}")
    for k in FEATS:
        v = N.dropna(subset=[k, "race_up"])
        v = v[v[k] != 0]
        top = v[v[k].abs() >= v[k].abs().quantile(0.9)]
        won = np.where(np.sign(top[k]) > 0, top.race_up, 1 - top.race_up).astype(float)
        out.append(f"  {k:>8}{np.mean(won):>9.0%}{len(won):>6}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_book.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()

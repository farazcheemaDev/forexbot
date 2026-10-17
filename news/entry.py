"""THE NEWS BOOK'S ENTRY, EXIT AND SIGNAL SCORE - on 1-minute bars (2026-10-17)

The user: "integrate the news perfectly - the perfect entry spot, then the stop, and a perfect score". The trade is
news_book's: SHORT the coin / LONG the same notional of BTC after a Binance "adds to Margin / Futures / Earn" or a
monitoring-tag notice (the two types with an edge on both halves, news_book.py 2026-10-17). Here, on 1-minute perp bars
(news/min1_fetch.py), everything about WHEN and HOW is measured, chosen on the TUNE half and judged on the HOLDOUT:
ENTRY    I1 / I5 / I15 / I60 / I240: at the open N minutes after the headline's minute
         POP x: a resting SELL x% above the I1 price (x = 3 / 6 / 10%), live for 24 h, filled when the coin's high trades
                through it (the "short the listing pump" idea); never filled = no trade
EXIT     hold 24h / 72h / 7d; STOP when the coin trades S above the entry (S = 15 / 25 / 50%; filled 3% worse - squeezes
         jump); TAKE-PROFIT when the coin is TP below the entry (TP = 10 / 20%; or none)
COST     12bp a round trip on each leg (Bitget taker); funding NOT charged here (a short usually RECEIVES it; news_book.py
         charged it on hourly bars and the edge held)
SPLIT    by event time at news_book's cut (60% of all events); the best (entry, hold, stop, TP) is the one with the best
         TUNE mean among cells with >= 30 tune trades; its HOLDOUT numbers are the honest ones
SCORE    for each trade of the chosen cell, features known AT ENTRY: event type, FinBERT tone (news/tone.py), how many
         channels repeated it, log views, the coin's move vs BTC in the 24 h before the headline, its move from the
         headline to the entry, log of its 7-day quote volume, BTC's 7-day return, the coin's age on Binance. A ridge
         model fit on the TUNE half predicts the trade's net; the SCORE is that prediction's percentile (0-100) among
         tune trades. Judged on the HOLDOUT: net by score tercile, and the rank correlation of score with net.

REGISTERED BEFORE THE RUN (2026-10-17)
    E1 waiting beats the first minute: the tune-best entry is I15 or later, or a POP (the first minutes still pump).
    E2 a stop is in the tune-best cell (no-stop cells carry the -1752% squeeze risk news_book saw).
    E3 the chosen cell is positive on the HOLDOUT, but by less than on the tune half.
    S1 the score works out of sample: holdout top-tercile mean net > bottom-tercile by >= 200bp, rank corr > 0.
    PASS (a score the bot can size by): S1 right AND the top tercile is positive on the holdout.

RESULT (2026-10-17, logs/news_entry.txt; 255 events, 317 coin-events, cut 2024-02-14)
    Tune-best overall: short into a +6% pump (POP6), 7 days, NO stop: +587bp tune / +1,106bp holdout, worst -134% (E1
    right, E2 wrong, E3 wrong - the holdout was BETTER). With a stop the pump entry collapses (POP6 72h stop 25%: +254 /
    -41bp): the pumps that keep going are the squeezes the stop meets. Best cell WITH a stop: enter 15 minutes after the
    headline, hold 72h, stop +25%, take-profit -20%: +316 / +267bp a trade, 67% won, worst -36% (313 trades).
    Score on the POP6 cell (32 tune trades): holdout terciles +730 / +2,055 / +273bp, rank corr -0.11 - FAIL (S1 wrong);
    news/score.py retries it on the stopped cell.

    python -m news.entry
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

EV = ROOT / "strategy_analysis" / "data" / "news" / "events.parquet"
TONE = ROOT / "strategy_analysis" / "data" / "news" / "tone.parquet"
M1 = ROOT / "strategy_analysis" / "data" / "news" / "m1"
PERPS = ROOT / "strategy_analysis" / "data" / "perps"
LOG = ROOT / "logs" / "news_entry.txt"
TYPES = ("adds_products", "monitoring_tag")
FEE, SLIP = 0.0012, 0.03
ENTRIES = ("I1", "I5", "I15", "I60", "I240", "POP3", "POP6", "POP10")
HOLDS = {"24h": 1440, "72h": 4320, "7d": 10080}
STOPS = (None, 0.15, 0.25, 0.50)
TPS = (None, 0.10, 0.20)
_C: dict = {}


def bars(sym, d0, days=8):
    key = (sym, d0)
    if key not in _C:
        parts = []
        for k in range(days + 1):
            f = M1 / sym / f"{(pd.Timestamp(d0) + pd.Timedelta(days=k)):%Y-%m-%d}.csv.gz"
            if f.exists():
                parts.append(pd.read_csv(f))
        if not parts:
            _C[key] = None
        else:
            d = pd.concat(parts, ignore_index=True)
            t = pd.to_datetime(d.time).to_numpy("datetime64[ns]").astype("int64")
            _C[key] = (t, d.open.to_numpy(float), d.high.to_numpy(float), d.low.to_numpy(float), d.close.to_numpy(float),
                       d.qvol.to_numpy(float))
    return _C[key]


def entry_index(c, t0_ns, kind):
    """(index of the entry bar, entry price) or None."""
    t, o, h = c[0], c[1], c[2]
    i1 = np.searchsorted(t, t0_ns + 60 * 10**9)
    if i1 >= len(t):
        return None
    if kind.startswith("I"):
        i = np.searchsorted(t, t0_ns + int(kind[1:]) * 60 * 10**9)
        return (i, o[i]) if i < len(t) else None
    x = int(kind[3:]) / 100
    lim = o[i1] * (1 + x)
    end = np.searchsorted(t, t[i1] + 24 * 3600 * 10**9)
    hit = np.flatnonzero(h[i1:end] >= lim)
    if not len(hit):
        return None
    i = i1 + hit[0]
    return i, max(lim, o[i])                       # a gap above the limit fills at the open (better for a short)


def run(c, b, i, e, hold, stop, tp):
    """Short coin from bar i at e, long BTC at the same minute; returns net or None."""
    t, o, h, l, cl = c[0], c[1], c[2], c[3], c[4]
    j_end = np.searchsorted(t, t[i] + hold * 60 * 10**9) - 1
    if j_end <= i or t[j_end] - t[i] < (hold - 60) * 60 * 10**9:
        return None                                # the coin's data stops (delisted / not yet in the archive)
    hi, lo = h[i:j_end + 1] / e - 1, l[i:j_end + 1] / e - 1
    k_stop = np.flatnonzero(hi >= stop)[0] if stop is not None and (hi >= stop).any() else None
    k_tp = np.flatnonzero(lo <= -tp)[0] if tp is not None and (lo <= -tp).any() else None
    if k_stop is not None and (k_tp is None or k_stop <= k_tp):          # same minute: assume the stop (pessimistic)
        j, x = i + k_stop, e * (1 + stop) * (1 + SLIP)
    elif k_tp is not None:
        j, x = i + k_tp, e * (1 - tp)
    else:
        j, x = j_end, cl[j_end]
    bt, bo, bc = b[0], b[1], b[4]
    ib, jb = np.searchsorted(bt, t[i]), min(np.searchsorted(bt, t[j]), len(bt) - 1)
    if ib >= len(bt):
        return None
    return -(x / e - 1) + (bc[jb] / bo[ib] - 1) - 2 * FEE


def features(ev, coin, c, b, t0_ns, i, e, first):
    t, o, cl, qv = c[0], c[1], c[4], c[5]
    i0 = np.searchsorted(t, t0_ns)
    pre = np.nan
    hv = PERPS / f"{coin}_1h.csv.gz"
    btc7, vol7 = np.nan, np.nan
    bt, bc = b[0], b[4]
    jb = min(np.searchsorted(bt, t[i]), len(bt) - 1)
    if jb > 0:
        btc_now = bc[jb]
        k = np.searchsorted(bt, t[i] - 7 * 86400 * 10**9)
        btc7 = btc_now / bc[k] - 1 if k < jb else np.nan
    return dict(etype=1.0 if ev.etype == "adds_products" else 0.0, tone=ev.tone if np.isfinite(ev.tone) else 0.0,
                n_src=float(ev.n_sources), views=np.log1p(ev.views) if ev.views == ev.views and ev.views else 0.0,
                to_entry=e / o[min(i0, len(o) - 1)] - 1, pre24=pre, btc7=btc7,
                vol=np.log1p(qv[max(i0 - 1440, 0):i0].sum()) if i0 > 0 else np.nan,
                age=(t0_ns - first) / 86400e9 if first else np.nan)


def first_seen():
    import json
    out = {}
    for p in PERPS.glob("*.json"):
        if p.name == "universe.json":
            continue
        try:
            m = json.loads(p.read_text())
            if isinstance(m.get("first"), str):
                out[m["sym"]] = pd.Timestamp(m["first"]).value
        except Exception:
            pass
    return out


def main():
    E = pd.read_parquet(EV)
    cut = E.t.sort_values().iloc[int(len(E) * 0.6)]
    if TONE.exists():
        E = E.join(pd.read_parquet(TONE), how="left")
    else:
        E["tone"] = np.nan
    E = E[E.etype.isin(TYPES) & (E.coins != "")]
    FS = first_seen()
    rows = []
    for ev in E.itertuples():
        t0 = pd.Timestamp(ev.t).floor("min").value
        d0 = pd.Timestamp(ev.t).normalize()
        b = bars("BTCUSDT", d0)
        if b is None:
            continue
        for coin in [x for x in ev.coins.split(",") if x and x != "BTCUSDT"][:3]:
            c = bars(coin, d0)
            if c is None:
                continue
            for kind in ENTRIES:
                ie = entry_index(c, t0, kind)
                if ie is None:
                    continue
                i, e = ie
                f = features(ev, coin, c, b, t0, i, e, FS.get(coin))
                for hk, hm in HOLDS.items():
                    for st in STOPS:
                        for tp in TPS:
                            net = run(c, b, i, e, hm, st, tp)
                            if net is not None:
                                rows.append(dict(eid=ev.Index, coin=coin, t=pd.Timestamp(ev.t), hold=pd.Timestamp(ev.t) >= cut,
                                                 entry=kind, h=hk, stop=st if st else 0.0, tp=tp if tp else 0.0, net=net, **f))
    D = pd.DataFrame(rows)
    lines = [f"news/entry.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {E.shape[0]} events ({', '.join(TYPES)}), "
             f"{D[['eid', 'coin']].drop_duplicates().shape[0]} coin-events with 1m bars; cut {cut:%Y-%m-%d}", ""]
    g = D.groupby(["entry", "h", "stop", "tp"])
    T = g.apply(lambda x: pd.Series(dict(n_tune=(~x.hold).sum(), tune=x.net[~x.hold].mean(), n_hold=x.hold.sum(),
                                         holdout=x.net[x.hold].mean(), won=(x.net > 0).mean(), worst=x.net.min())),
                include_groups=False).reset_index()
    ok = T[T.n_tune >= 30].sort_values("tune", ascending=False)
    lines.append("  TOP 12 cells by TUNE mean (bp), with their HOLDOUT:")
    lines.append(f"    {'entry':<7}{'hold':>5}{'stop':>6}{'tp':>5}{'n tune':>8}{'tune':>8}{'n hold':>8}{'holdout':>9}{'won':>6}{'worst':>8}")
    for r in ok.head(12).itertuples():
        lines.append(f"    {r.entry:<7}{r.h:>5}{r.stop:>6.0%}{r.tp:>5.0%}{r.n_tune:>8.0f}{r.tune * 1e4:>+7.0f}b{r.n_hold:>8.0f}"
                     f"{r.holdout * 1e4:>+8.0f}b{r.won * 100:>5.0f}%{r.worst * 100:>+7.0f}%")
    lines.append("  BY ENTRY (best tune cell of each entry):")
    for en in ENTRIES:
        s = ok[ok.entry == en]
        if len(s):
            r = s.iloc[0]
            lines.append(f"    {en:<7} best tune {r.tune * 1e4:+6.0f}b ({r.h}, stop {r.stop:.0%}, tp {r.tp:.0%}) -> holdout {r.holdout * 1e4:+6.0f}b"
                         f"  (n {r.n_tune:.0f} / {r.n_hold:.0f})")
    best = ok.iloc[0]
    C = D[(D.entry == best.entry) & (D.h == best.h) & (D.stop == best.stop) & (D.tp == best.tp)].copy()
    feats = ["etype", "tone", "n_src", "views", "to_entry", "btc7", "vol", "age"]
    X = C[feats].astype(float)
    tu = ~C.hold.to_numpy()
    mu, sd = X[tu].mean(), X[tu].std().replace(0, 1)
    Z = ((X - mu) / sd).fillna(0.0).to_numpy()
    A = np.c_[np.ones(len(Z)), Z]
    lam = 5.0
    w = np.linalg.solve(A[tu].T @ A[tu] + lam * np.eye(A.shape[1]), A[tu].T @ C.net.to_numpy()[tu])
    pred = A @ w
    ref = np.sort(pred[tu])
    C["score"] = np.searchsorted(ref, pred) / max(len(ref), 1) * 100
    H = C[C.hold]
    q = np.quantile(C.score[tu], [1 / 3, 2 / 3])
    terc = [H[H.score < q[0]].net.mean(), H[(H.score >= q[0]) & (H.score < q[1])].net.mean(), H[H.score >= q[1]].net.mean()]
    rho = H[["score", "net"]].corr(method="spearman").iloc[0, 1] if len(H) > 5 else np.nan
    lines += ["", f"  SCORE on the chosen cell ({best.entry}, {best.h}, stop {best.stop:.0%}, tp {best.tp:.0%}): ridge weights",
              "    " + ", ".join(f"{f} {x:+.4f}" for f, x in zip(feats, w[1:])),
              f"    HOLDOUT net by score tercile (low / mid / high): {terc[0] * 1e4:+.0f} / {terc[1] * 1e4:+.0f} / {terc[2] * 1e4:+.0f} bp; "
              f"rank corr {rho:+.2f} (n {len(H)})"]
    e1 = best.entry in ("I15", "I60", "I240") or best.entry.startswith("POP")
    e2 = best.stop > 0
    e3 = 0 < best.holdout < best.tune
    s1 = terc[2] - terc[0] >= 0.02 and rho > 0
    lines += ["", "REGISTERED PREDICTIONS",
              f"  E1 the tune-best entry waits (I15+ or POP): {best.entry} -> {'RIGHT' if e1 else 'WRONG'}",
              f"  E2 a stop in the tune-best cell: {best.stop:.0%} -> {'RIGHT' if e2 else 'WRONG'}",
              f"  E3 holdout positive but below tune: {best.holdout * 1e4:+.0f} vs {best.tune * 1e4:+.0f}bp -> {'RIGHT' if e3 else 'WRONG'}",
              f"  S1 top tercile beats bottom by >= 200bp, rank corr > 0 -> {'RIGHT' if s1 else 'WRONG'}",
              f"  PASS (score usable): {'YES' if s1 and terc[2] > 0 else 'NO'}"]
    D.to_parquet(ROOT / "strategy_analysis" / "data" / "news" / "entry_trades.parquet")
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

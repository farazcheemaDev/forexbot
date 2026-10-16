"""DOES HE READ ABSORPTION? - a hidden buyer (or seller) soaking up the other side on the real CME NQ book (2026-10-12)

WHY      his_burst_after.py: his +7 comes at the ORDINARY pace (median 29 s, = any +-7 move) and NOT as a burst. News
         arrives as a jump; a big player working a large order arrives as ordinary-paced pressure. A big player who
         hides his size (an iceberg, or a desk re-filling the best bid as it is hit) leaves one footprint a screen-reader
         can see on a depth ladder: aggressive selling keeps hitting the bid, the bid keeps refilling, and the price does
         not fall - "absorption". It fits what is measured at his click: the price has not moved (median 0.00 points in
         5 s, his_clock_exits.py). (I first cited his_book.py's q1 rank 0.39, p 0.019 here as an iceberg's thin
         queue - it was a tie artifact, 0.46 / p 0.51 with mid-ranks, his_strategy s44.) his_tape.py tested the SIGN of
         the flow and his_book.py the SIZE of the book, never the two together.

DATA     already on disk, nothing fetched: Databento CME NQ trades with aggressor side (nq_trades_windows.pkl), the
         10-level book one snapshot a second (nq_book_1s.pkl) and the bbo mid a second (nq_bbo1s.pkl), 22 min before to 20
         min after each of his NASDAQ entries (31 windows). Races on Exness USTECm ticks (his_race_curve.race2).

PER SECOND, only in seconds where the NQ mid did not change ("held"):
    hidden_bid  = sell-aggressor lots + change in best-bid size   (> 0: the bid was hit and refilled beyond what showed)
    hidden_ask  = buy-aggressor lots  + change in best-ask size
    support     = hidden_bid - hidden_ask                         (> 0: a hidden buyer)
    absorbed    = sell lots - buy lots                            (> 0: net selling that failed to move the price)
AT EACH MOMENT T, over w = 15 / 30 / 60 / 120 s before T, signed by the side (> 0 = his way):
    sup_w, abs_w as sums;  res_w = NQ mid change over w minus beta x net aggressor flow over w (beta fit on all moments,
    no side used): > 0 = the price held up better than the flow says.
TESTS as his_tape.py / his_book.py: A his side agrees with the sign at his click (binomial); B his moment ranked among
the same sitting's moments (+-1..20 min, Wilcoxon on mid-ranks); C a rule at the sitting's moments: trade with a
top-decile reading, +-7 race.

REGISTERED BEFORE THE RUN (2026-10-12)
    1. A: 50-62% for every feature and window (I expect it to fail like the tape and the book).
    2. B: ranks 0.44-0.58.
    3. C: the top-decile rule wins 46-56% of races.
    LEAD LINE: any feature with A >= 70% (p < 0.01) AND B >= 0.62 -> absorption is his read; then it gets a bot test on
    full days of CME data (priced first). Otherwise absorption on the CME book is ruled out.

RESULT (2026-10-12, logs/his_absorb.txt) - RULED OUT; no feature near the lead line. 42 entries, 1,553 sitting moments.
    A 38-63% (no p < 0.16), B ranks 0.41-0.52 (res15 0.41, p 0.042 - one of 12, AGAINST him), C 44-52%. Predictions
    1-3 "wrong" only at their edges (38%, 63%; 0.41; 44%), all toward noise. Measurement check: the NQ mid changes in
    91% of seconds, so the "held-second" counts (sup, abs) are sparse and carry ~0 even at all seconds (corr with the
    next 10-60 s <= 0.008, vs +0.02..+0.05 for plain flow); res (price move vs flow over every second) is the usable
    absorption read, and it says nothing his way.

    python -m backtest.his_absorb
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.his_tape as TP  # noqa: E402
from backtest.his_race_curve import race2  # noqa: E402

DATA = ROOT / "strategy_analysis" / "data"
LOG = ROOT / "logs" / "his_absorb.txt"
W = (15, 30, 60, 120)


def seconds_frame() -> pd.DataFrame:
    """one row per second inside each cached window: mid, best sizes, buy / sell lots, and the derived per-second terms."""
    T = pickle.loads((DATA / "nq_trades_windows.pkl").read_bytes())
    B = pickle.loads((DATA / "nq_book_1s.pkl").read_bytes())
    M = pickle.loads((DATA / "nq_bbo1s.pkl").read_bytes())
    parts = []
    for key in T:
        a, b = pd.Timestamp(key[0]), pd.Timestamp(key[1])
        grid = pd.date_range(a.ceil("s"), b.floor("s"), freq="s")
        t = T[key]
        sec = pd.to_datetime(t["ns"].to_numpy()).floor("s")
        vol = pd.DataFrame({"sec": sec, "buy": np.where(t.aggr == 1, t["size"], 0),
                            "sell": np.where(t.aggr == -1, t["size"], 0)}).groupby("sec").sum()
        m = M.get(key)
        bk = B.get(key)
        if m is None or bk is None or not len(m) or not len(bk):
            continue
        m = m.copy()
        m.index = pd.to_datetime(m.index).floor("s")
        m = m[~m.index.duplicated(keep="last")]
        F = pd.DataFrame(index=grid)
        F["mid"] = m.reindex(grid, method="ffill")
        F["bid1"] = bk["bid_sz_00"].reindex(grid, method="ffill")
        F["ask1"] = bk["ask_sz_00"].reindex(grid, method="ffill")
        F["buy"] = vol["buy"].reindex(grid).fillna(0.0)
        F["sell"] = vol["sell"].reindex(grid).fillna(0.0)
        held = (F.mid.diff() == 0).to_numpy()
        hb = np.where(held & (F.sell > 0), F.sell + F.bid1.diff(), 0.0)
        ha = np.where(held & (F.buy > 0), F.buy + F.ask1.diff(), 0.0)
        F["support"] = np.nan_to_num(hb) - np.nan_to_num(ha)
        F["absorbed"] = np.where(held, F.sell - F.buy, 0.0)
        F["flow"] = F.buy - F.sell
        parts.append(F)
    S = pd.concat(parts)
    return S[~S.index.duplicated(keep="first")].sort_index()


def at_features(S, cs, at: pd.Timestamp):
    k = S.index.searchsorted(at, side="right") - 1
    if k < 121 or (at - S.index[k]).total_seconds() > 2:
        return None
    if (S.index[k] - S.index[k - 120]).total_seconds() != 120:          # the 2 minutes before must be one window
        return None
    out = {}
    for w in W:
        out[f"sup{w}"] = cs["support"][k + 1] - cs["support"][k + 1 - w]
        out[f"abs{w}"] = cs["absorbed"][k + 1] - cs["absorbed"][k + 1 - w]
        out[f"flow{w}"] = cs["flow"][k + 1] - cs["flow"][k + 1 - w]
        out[f"dp{w}"] = S.mid.iat[k] - S.mid.iat[k - w]
    return out


def main():
    from scipy.stats import binomtest, wilcoxon
    S = seconds_frame()
    cs = {c: np.r_[0.0, np.cumsum(S[c].to_numpy())] for c in ("support", "absorbed", "flow")}
    x = TP.entries()
    ticks = pickle.loads(TP.TICKS.read_bytes())
    rows = []
    for r in x.itertuples():
        day = ticks.get(r.d)
        if day is None or r.t < 960:
            continue
        ts, mid, _ = day
        base = (r.d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)
        others = x[x.d == r.d].t.to_numpy()
        starts = [("his", r.t)] + [("near", r.t + 60 * m) for m in list(range(-20, 0)) + list(range(1, 21))
                                   if r.t + 60 * m > 960 and np.min(np.abs(others - (r.t + 60 * m))) >= 60]
        for who, t in starts:
            f = at_features(S, cs, base + pd.Timedelta(seconds=float(t)))
            if f is None:
                continue
            rows.append(dict(entry=r.Index, who=who, s=r.s, race_up=race2(ts, mid, t, 1, 600, 7, 7), **f))
    D = pd.DataFrame(rows)
    feats = []
    for w in W:
        beta = (D[f"dp{w}"] * D[f"flow{w}"]).sum() / max((D[f"flow{w}"] ** 2).sum(), 1e-9)
        D[f"res{w}"] = D[f"dp{w}"] - beta * D[f"flow{w}"]
        feats += [f"sup{w}", f"abs{w}", f"res{w}"]
    H, N = D[D.who == "his"], D[D.who == "near"]
    out = [f"backtest/his_absorb.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(S):,} CME NQ seconds in the cached "
           f"windows; {len(H)} of his entries, {len(N)} same-sitting moments", ""]
    out.append("A. DIRECTION - sign agrees with HIS side at his click      B. TIMING - his moment ranked in his sitting"
               "      C. RULE - trade with a top-decile reading at the sitting's moments")
    out.append(f"  {'feature':>8}{'agree':>8}{'p':>8}{'rank':>8}{'p':>8}{'race won':>10}{'n':>6}")
    res = {}
    for k in feats:
        v = (H[k] * H.s).dropna()
        v = v[v != 0]
        ag = (v > 0).mean() if len(v) else np.nan
        pa = binomtest(int((v > 0).sum()), len(v), 0.5).pvalue if len(v) else np.nan
        rk = []
        for _, g in D.groupby("entry"):
            h, n = g[g.who == "his"], g[g.who == "near"]
            if len(h) and len(n) >= 10 and np.isfinite(h[k].iat[0]):
                hv = h[k].iat[0] * h.s.iat[0]
                nv = (n[k] * n.s).dropna()
                rk.append((nv < hv).mean() + 0.5 * (nv == hv).mean())
        pb = wilcoxon(np.array(rk) - 0.5).pvalue if len(rk) > 5 else np.nan
        u = N.dropna(subset=[k, "race_up"])
        u = u[u[k] != 0]
        top = u[u[k].abs() >= u[k].abs().quantile(0.9)]
        won = np.where(np.sign(top[k]) > 0, top.race_up, 1 - top.race_up).astype(float)
        res[k] = (ag, pa, np.mean(rk), np.mean(won))
        out.append(f"  {k:>8}{ag:>8.0%}{pa:>8.3f}{np.mean(rk):>8.2f}{pb:>8.3f}{np.mean(won):>10.0%}{len(won):>6}")
    out.append("")
    A = [v[0] for v in res.values()]
    Bk = [v[2] for v in res.values()]
    C = [v[3] for v in res.values()]
    lead = [k for k, v in res.items() if v[0] >= 0.70 and v[1] < 0.01 and v[2] >= 0.62]
    out.append("REGISTERED PREDICTIONS")
    out.append(f"  1 A within 50-62%: range {min(A):.0%}..{max(A):.0%} -> {'RIGHT' if min(A) >= 0.5 and max(A) <= 0.62 else 'WRONG'}")
    out.append(f"  2 B within 0.44-0.58: range {min(Bk):.2f}..{max(Bk):.2f} -> {'RIGHT' if min(Bk) >= 0.44 and max(Bk) <= 0.58 else 'WRONG'}")
    out.append(f"  3 C within 46-56%: range {min(C):.0%}..{max(C):.0%} -> {'RIGHT' if min(C) >= 0.46 and max(C) <= 0.56 else 'WRONG'}")
    out.append(f"  LEAD LINE (A >= 70%, p < 0.01, B >= 0.62): {', '.join(lead) if lead else 'none'}")
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

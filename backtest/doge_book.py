"""DOES THE ORDER BOOK GIVE A RETAIL SCALPER AN EDGE ON DOGE? - scoring book_rec.py's live recording (2026-10-09).

The predictions R1-R5 are registered in book_rec.py's docstring, written before any data was recorded. This file only
scores them. Everything is at Bitget's DOGE perp mid (bid+ask)/2, aligned by the EXCHANGES' own timestamps.

FEATURES (each known at its snapshot)
    bg_imb1/5/20/50     Bitget book imbalance over the top k levels: (bid $ - ask $) / (bid $ + ask $)
    bg_band10/25        Bitget imbalance of the $ resting within 0.10% / 0.25% of the mid
    bg_micro            Bitget microprice minus mid, in bp (the size-weighted fair price inside the spread)
    bn_imb1/5/20, bn_band10/25   the same on Binance, the bigger venue
    basis               Binance mid minus Bitget mid, bp (Binance above -> Bitget should follow up)
    bn_lead2            Binance mid change over the last ~2 s minus Bitget's, bp
    btc5 / btc30        BTC mid change over the last 5 / 30 s, bp
    flow10 / flow30     net taker notional over the last 10 / 30 s, both venues, as a share of all traded notional
TARGET  Bitget mid change over the next 10 / 30 / 60 / 300 s, bp.
TESTS   IC = Spearman on NON-overlapping samples (one every h seconds), on each half of the recording.
        Extreme deciles: thresholds from the FIRST half; on the SECOND half, long above the 90th percentile and short
        below the 10th, one signal per h seconds; the move in the signalled direction (mid to mid), and the move a
        taker actually gets (buy at the ask, sell at the bid) less 12bp, and mid-to-mid less 4bp (maker, optimistic:
        it assumes the limit orders fill).

    python -m backtest.doge_book
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "strategy_analysis" / "data" / "doge_book"
LOG = ROOT / "logs" / "doge_book.txt"
HORIZONS = (10, 30, 60, 300)


def load():
    b = pd.read_csv(DATA / "book.csv")
    b = b.dropna(subset=["bg_ts", "bg_bid", "bg_ask"]).copy()
    b["t"] = b.bg_ts.astype("int64")
    b = b.sort_values("t", kind="stable").drop_duplicates("t").reset_index(drop=True)
    tr = pd.read_csv(DATA / "trades.csv").drop_duplicates(["venue", "id"])
    tr = tr[tr.t >= b.t.min() - 60_000].sort_values("t", kind="stable").reset_index(drop=True)
    return b, tr


def features(b: pd.DataFrame, tr: pd.DataFrame) -> pd.DataFrame:
    f = pd.DataFrame({"t": b.t})
    mid = (b.bg_bid + b.bg_ask) / 2
    f["mid"], f["bid"], f["ask"] = mid, b.bg_bid, b.bg_ask
    for c in ("bg_imb1", "bg_imb5", "bg_imb20", "bg_imb50", "bg_band10", "bg_band25",
              "bn_imb1", "bn_imb5", "bn_imb20", "bn_band10", "bn_band25"):
        f[c] = b[c]
    micro = (b.bg_bid * b.bg_aq1 + b.bg_ask * b.bg_bq1) / (b.bg_bq1 + b.bg_aq1)
    f["bg_micro"] = (micro / mid - 1) * 1e4
    bn_mid = (b.bn_bid + b.bn_ask) / 2
    f["basis"] = (bn_mid / mid - 1) * 1e4
    f["bn_lead2"] = (np.log(bn_mid).diff(2) - np.log(mid).diff(2)) * 1e4
    btc = (b.btc_bid + b.btc_ask) / 2
    f["btc5"] = np.log(btc).diff(5) * 1e4
    f["btc30"] = np.log(btc).diff(30) * 1e4
    # taker flow over the last w seconds, both venues
    tt = tr.t.to_numpy()
    usd = (tr.price * tr.qty).to_numpy()
    sgn = np.where(tr.side.to_numpy() == "buy", 1.0, -1.0)
    cs_net, cs_all = np.r_[0.0, np.cumsum(sgn * usd)], np.r_[0.0, np.cumsum(usd)]
    for w in (10, 30):
        z = np.searchsorted(tt, f.t.to_numpy(), "right")
        a = np.searchsorted(tt, f.t.to_numpy() - w * 1000, "right")
        tot = cs_all[z] - cs_all[a]
        f[f"flow{w}"] = np.where(tot > 0, (cs_net[z] - cs_net[a]) / np.where(tot > 0, tot, 1), 0.0)
    # liquidations (liq_rec.py): a SELL order is a long being liquidated
    t = f.t.to_numpy()
    lq = DATA / "liqs.csv"
    if lq.exists():
        L = pd.read_csv(lq).dropna(subset=["t"]).sort_values("t", kind="stable")
        lt = L.t.to_numpy("int64")
        sg = np.where(L.side.to_numpy() == "SELL", 1.0, -1.0)            # +1 = long liquidated (forced sell)
        for name, m in (("mkt", np.ones(len(L), bool)), ("doge", (L.symbol == "DOGEUSDT").to_numpy())):
            cs = np.r_[0.0, np.cumsum(np.where(m, sg * L.usd.to_numpy(), 0.0))]
            cl = np.r_[0.0, np.cumsum(np.where(m & (sg > 0), L.usd.to_numpy(), 0.0))]
            z, a = np.searchsorted(lt, t, "right"), np.searchsorted(lt, t - 60_000, "right")
            f[f"{name}_liq60"] = cs[z] - cs[a]                           # net long-minus-short liquidated $
            f[f"{name}_longliq60"] = cl[z] - cl[a]
    oif = DATA / "oi.csv"
    if oif.exists():
        O = pd.read_csv(oif).dropna().sort_values("t", kind="stable")
        ot, ov = O.t.to_numpy("int64"), O.oi_coins.to_numpy(float)
        i_now = np.searchsorted(ot, t, "right") - 1
        i_then = np.searchsorted(ot, t - 300_000, "right") - 1
        ok = (i_now >= 0) & (i_then >= 0)
        f["oi5m"] = np.where(ok, (ov[np.maximum(i_now, 0)] / ov[np.maximum(i_then, 0)] - 1) * 1e4, np.nan)
    # forward moves
    for h in HORIZONS:
        j = np.searchsorted(t, t + h * 1000, "left")
        ok = j < len(t)
        jj = np.where(ok, j, len(t) - 1)
        f[f"fwd{h}"] = np.where(ok, (mid.to_numpy()[jj] / mid.to_numpy() - 1) * 1e4, np.nan)
        # what a taker gets: long buys the ask now and sells the bid later; short the reverse
        f[f"tl{h}"] = np.where(ok, (f.bid.to_numpy()[jj] / f.ask.to_numpy() - 1) * 1e4, np.nan)
        f[f"ts{h}"] = np.where(ok, (f.bid.to_numpy() / f.ask.to_numpy()[jj] - 1) * 1e4, np.nan)
    return f


FEATS = ["bg_imb1", "bg_imb5", "bg_imb20", "bg_imb50", "bg_band10", "bg_band25", "bg_micro",
         "bn_imb1", "bn_imb5", "bn_imb20", "bn_band10", "bn_band25", "basis", "bn_lead2", "btc5", "btc30",
         "flow10", "flow30", "mkt_liq60", "doge_liq60", "oi5m"]


def spaced(idx_t: np.ndarray, gap_ms: int) -> np.ndarray:
    """Indices of samples at least gap_ms apart (greedy, in time order)."""
    keep, last = [], -np.inf
    for i, t in enumerate(idx_t):
        if t - last >= gap_ms:
            keep.append(i)
            last = t
    return np.array(keep, int)


def ic(x, y):
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 30:
        return np.nan, int(m.sum())
    rx, ry = pd.Series(x[m]).rank().to_numpy(), pd.Series(y[m]).rank().to_numpy()
    return float(np.corrcoef(rx, ry)[0, 1]), int(m.sum())


def score(f: pd.DataFrame):
    # halves by SNAPSHOT COUNT, not by clock: a ~2 h network outage (2026-10-09 18:53..21:00 UTC) left the clock's second
    # half with ~8 minutes of data
    half = f.t.iloc[len(f) // 2]
    A, B = f[f.t < half], f[f.t >= half]
    rows = []
    for h in HORIZONS:
        for c in FEATS:
            r = dict(feat=c, h=h)
            if c not in f:
                continue
            for nm, P in (("ic1", A), ("ic2", B)):
                s = P.iloc[spaced(P.t.to_numpy(), h * 1000)]
                r[nm], r[nm + "_n"] = ic(s[c].to_numpy(float), s[f"fwd{h}"].to_numpy(float))
            lo, hi = A[c].quantile(0.10), A[c].quantile(0.90)
            sig = B[(B[c] >= hi) | (B[c] <= lo)].copy()
            if hi == lo:
                sig = sig.iloc[:0]
            sig["d"] = np.where(sig[c] >= hi, 1, -1)
            sig = sig.iloc[spaced(sig.t.to_numpy(), h * 1000)].dropna(subset=[f"fwd{h}"])
            r["n_sig"] = len(sig)
            if len(sig):
                mv = sig.d * sig[f"fwd{h}"]
                taker = np.where(sig.d > 0, sig[f"tl{h}"], sig[f"ts{h}"]) - 12
                r.update(move=mv.mean(), move_se=mv.std(ddof=1) / np.sqrt(len(mv)) if len(mv) > 1 else np.nan,
                         hit=(mv > 0).mean(), taker=taker.mean(), maker=(mv - 4).mean())
            rows.append(r)
    return pd.DataFrame(rows), A, B


def verdict(ok: bool, *vals) -> str:
    """RIGHT / WRONG - or TOO FEW DATA while any value it rests on is still missing."""
    return "TOO FEW DATA" if any(not np.isfinite(v) for v in vals) else ("RIGHT" if ok else "WRONG")


def main():
    b, tr = load()
    f = features(b, tr)
    R, A, B = score(f)
    span = (f.t.iloc[-1] - f.t.iloc[0]) / 60_000
    mv = f.mid.pct_change().abs() * 1e4
    lines = [f"backtest/doge_book.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; book_rec.py recording "
             f"{pd.Timestamp(f.t.iloc[0], unit='ms'):%Y-%m-%d %H:%M} .. {pd.Timestamp(f.t.iloc[-1], unit='ms'):%H:%M} UTC "
             f"({span:.0f} min, {len(f):,} snapshots, {len(tr):,} trades); halves split at "
             f"{pd.Timestamp(A.t.iloc[-1], unit='ms'):%H:%M}",
             f"DOGE mid {f.mid.iloc[0]:.5f} -> {f.mid.iloc[-1]:.5f}; spread median {((f.ask / f.bid - 1) * 1e4).median():.2f}bp; "
             f"mid moves by 1 s: median {mv.median():.2f}bp; typical |move| at 10/30/60/300 s: "
             + ", ".join(f"{f[f'fwd{h}'].abs().median():.1f}" for h in HORIZONS) + "bp", ""]
    lines.append("IC (Spearman, non-overlapping) first half / second half, and the extreme-decile trade on the SECOND half "
                 "(thresholds from the first): move in bp, hit rate, net after costs")
    for h in HORIZONS:
        lines.append(f"  horizon {h} s")
        for _, r in R[R.h == h].iterrows():
            lines.append(f"    {r.feat:10} IC {r.ic1:+.3f} / {r.ic2:+.3f}  (n {r.ic1_n}/{r.ic2_n}) | decile signals {r.n_sig:4}"
                         + (f": move {r.move:+6.2f}bp (se {r.move_se:4.2f}), hit {r.hit * 100:3.0f}%, taker net {r.taker:+6.2f}bp, "
                            f"maker net {r.maker:+6.2f}bp" if r.n_sig else ""))
    lines.append("")
    g = lambda c, h: R[(R.feat == c) & (R.h == h)].iloc[0]  # noqa: E731
    r1 = g("bg_imb5", 10)
    lines.append(f"R1 (bg_imb5 -> next 10 s, IC > +0.05 on both halves): {r1.ic1:+.3f} / {r1.ic2:+.3f} -> "
                 f"{verdict(r1.ic1 > 0.05 and r1.ic2 > 0.05, r1.ic1, r1.ic2)}")
    r2 = g("bg_imb5", 30)
    lines.append(f"R2 (bg_imb5 extreme deciles, 30 s move < 4bp): {r2.move:+.2f}bp on {r2.n_sig} signals -> "
                 f"{verdict(r2.move < 4, r2.move if r2.n_sig >= 20 else np.nan)}")
    r3 = g("bn_lead2", 10)
    lines.append(f"R3 (Binance lead -> next 10 s IC > +0.05, move < 2bp): IC {r3.ic1:+.3f} / {r3.ic2:+.3f}, move {r3.move:+.2f}bp -> "
                 f"IC {verdict(r3.ic1 > 0.05 and r3.ic2 > 0.05, r3.ic1, r3.ic2)}, move {verdict(r3.move < 2, r3.move if r3.n_sig >= 20 else np.nan)}")
    r4 = g("flow30", 60)
    lines.append(f"R4 (flow30 -> next 60 s, |IC| < 0.05): {r4.ic1:+.3f} / {r4.ic2:+.3f} -> "
                 f"{verdict(abs(r4.ic1) < 0.05 and abs(r4.ic2) < 0.05, r4.ic1, r4.ic2)}")
    big = R[(R.h >= 60) & (R.move > 12) & (R.n_sig >= 20)]               # a feature counts only on 20+ signals
    lines.append(f"R5 (no feature moves > 12bp at 60 s+ in its extreme decile): {len(big)} do -> "
                 + (("TOO FEW DATA" if R[R.h >= 60].n_sig.min() < 20 else "RIGHT") if not len(big) else "WRONG: " + ", ".join(
                     f"{a}@{h}s {m:+.1f}bp (n {n})" for a, h, m, n in zip(big.feat, big.h, big.move, big.n_sig))))
    for c, nm, txt in (("doge_liq60", "L1", None), ("mkt_liq60", "L2", "|IC| < 0.05 at 300 s"), ("oi5m", "L3", "|IC| < 0.05 at 300 s")):
        if c not in f:
            lines.append(f"{nm}: no {c} data yet")
            continue
        if nm == "L1":
            x = f[["t", "doge_longliq60", "doge_liq60", "fwd300"]].dropna()
            nz = x[x.doge_liq60 != 0]
            if len(nz) < 10:
                lines.append(f"L1: {int((f.doge_liq60 != 0).sum())} snapshots with any DOGE liquidation in the last 60 s - "
                             f"too few to score (registered: < 20 bursts expected on a quiet day)")
                continue
            q = nz.doge_liq60.abs().quantile(0.9)
            ev = nz[nz.doge_liq60.abs() >= q]
            ev = ev.iloc[spaced(ev.t.to_numpy(), 300_000)]
            mvv = np.sign(ev.doge_liq60) * ev.fwd300
            lines.append(f"L1: {len(ev)} DOGE liquidation bursts (|net| >= ${q:,.0f} in 60 s): move in the snap-back direction "
                         f"over 5 min {mvv.mean():+.2f}bp, hit {(mvv > 0).mean() * 100:.0f}%")
            continue
        r = g(c, 300)
        lines.append(f"{nm} ({c}, {txt}): IC {r.ic1:+.3f} / {r.ic2:+.3f} -> "
                     f"{verdict(abs(r.ic1) < 0.05 and abs(r.ic2) < 0.05, r.ic1, r.ic2)}")
    best = R.dropna(subset=["taker"]).sort_values("taker", ascending=False).head(5)
    lines.append("Best five by TAKER net on the second half: " + "; ".join(
        f"{a}@{h}s {t:+.2f}bp (move {m:+.2f}, n {n})" for a, h, t, m, n in zip(best.feat, best.h, best.taker, best.move, best.n_sig)))
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

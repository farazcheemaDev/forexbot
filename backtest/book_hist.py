"""THE ORDER-BOOK CHECKLIST ON BACK DATA - Bitget DOGE perp, seven full days (2026-10-28).

The user, after the checklist (record a pair's book and trades and rebuild a valid book / spread, depth, imbalance and
flow around a move / replay and test one hypothesis on later unseen data / paper-trade with fees, slippage, missed
fills): "can't we do it on the back data". book_rec.py's own recording is 262 minutes with REST snapshots, so this uses
Tardis.dev's free first-of-month days instead: the exchange's full update stream (incremental_book_L2) and the complete
tape for BITGET's DOGEUSDT perp - the venue and the coin the earlier result was about (doc 02, 2026-10-09: the book's
signals are real, the move they predict is 1-2bp). Data in strategy_analysis/data/book_hist/bitget/ (gitignored):
    tune days   2025-03-01  2025-06-01  2025-09-01      thresholds and nothing else are taken from these
    later days  2025-12-01  2026-03-01  2026-06-01  2026-09-01      scored once, never tuned on
    2026-09-01 also has Tardis' own top-25 snapshots, the independent check on the rebuilt book.

WHAT IS MEASURED (one function per checklist line)
    1. rebuild()   the book from the update stream, sampled every second. Valid = never crossed, equal to the independent
                   snapshots, and equal to the exchange's own snapshot at every reconnect (a feed that lost messages would not be).
    2. event_study()   the top 1% of 10-second mid moves (non-overlapping): what the spread, the touch quantity on the side
                   being consumed, the imbalance and the taker flow looked like BEFORE, and the flow during.
    3. hypothesis()    ONE pre-registered claim: top-of-book imbalance (bid $ - ask $ over bid $ + ask $, level 1) predicts the
                   next 10 s of the mid. Thresholds (10th / 90th percentile) from the tune days, applied to the later days.
                   Other features and the 30 s horizon are printed as exploratory (not part of the claim).
    4. replay()    the same signals traded the way an account could: a post-only limit at the touch, filled only when the TAPE
                   fills it (a trade through the price, or enough volume AT the price to clear the queue ahead), cancelled after
                   10 s, 0.5 s latency, one position at a time, exit at the touch (taker) or by a second limit with a taker
                   fallback. Bitget's standard fees: maker 2bp, taker 6bp a leg. Missed fills count as no trade.

REGISTERED BEFORE ANY OF THE SEVEN DAYS WAS READ (2026-10-28; only file headers and the first rows had been looked at)
    B1  The rebuilt book is valid: crossed in < 0.01% of seconds on every day; the rebuilt top-5 prices equal the independent
        snapshot's in >= 98% of seconds on 2026-09-01; at reconnect snapshots the rebuilt (pre-snapshot) top-5 equals the
        snapshot in >= 80% of cases.
    E1  Around the top-1% 10 s moves: the spread at the start is >= 1.3x its median; the touch quantity on the side being
        consumed is below its 60 s median in >= 55% of events; the imbalance points the move's way (d*imb1 > 0) in >= 60%;
        the taker flow in the 10 s BEFORE is not aligned (mean d*flow < +0.10) while the flow DURING the move is (> +0.40).
    H1  imb1 -> next 10 s: IC between +0.05 and +0.30 on every later day (the 262-minute recording read +0.20 / +0.25);
        the extreme-decile move in the signalled direction is +0.3..+2.5bp on every later day - under the 4bp maker round
        trip; pooled taker net below -9bp.
    M1  Entry fill rate within 10 s 30-70% (queue ahead = the whole touch, qf 1.0: 20-60%); signals that FILL moved less in
        the signalled direction than signals that did not, by >= 0.5bp (adverse selection); every cost-realistic variant
        averages negative per signal on the pooled later days, the best at <= -1bp; no variant positive on >= 3 of 4 later
        days. A PASS would need: pooled net per taken signal > 0 at t > 2, positive on >= 3 of 4 later days, at qf 1.0.
    If all of B1/E1/H1/M1 hold the thread is closed for retail on this venue: real information, nothing to take after costs.

    python -m backtest.book_hist            all days present; writes logs/book_hist.txt
"""
from __future__ import annotations

import heapq
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest.doge_book import ic, spaced  # noqa: E402

DATA = ROOT / "strategy_analysis" / "data" / "book_hist" / "bitget"
CACHE = ROOT / "strategy_analysis" / "data" / "book_hist"
LOG = ROOT / "logs" / "book_hist.txt"
TUNE = ["2025-03-01", "2025-06-01", "2025-09-01"]
LATER = ["2025-12-01", "2026-03-01", "2026-06-01", "2026-09-01"]
MAKER_BP, TAKER_BP = 2.0, 6.0          # Bitget USDT-futures standard: 0.02% / 0.06% a leg
TTL_MS, LAT_MS = 10_000, 500
EPS = 1e-9


# ---------------------------------------------------------------- 1. the book, rebuilt from the update stream
def topk(book: dict, k: int, bid: bool) -> list:
    return heapq.nlargest(k, book.items()) if bid else heapq.nsmallest(k, book.items())


def feat_row(bt: list, at: list, bids: dict, asks: dict) -> tuple:
    """(bid, ask, bq1, aq1, imb1, imb5, imb20, band10, band25) from the top levels and the full sides."""
    def imb(k):
        b = sum(p * q for p, q in bt[:k])
        a = sum(p * q for p, q in at[:k])
        return (b - a) / (b + a) if b + a > 0 else 0.0
    mid = (bt[0][0] + at[0][0]) / 2
    out = [bt[0][0], at[0][0], bt[0][1], at[0][1], imb(1), imb(5), imb(20)]
    for frac in (0.001, 0.0025):
        lo, hi = mid * (1 - frac), mid * (1 + frac)
        b = sum(p * q for p, q in bids.items() if p >= lo)
        a = sum(p * q for p, q in asks.items() if p <= hi)
        out.append((b - a) / (b + a) if b + a > 0 else 0.0)
    return tuple(out)


GRID_COLS = ["t", "bid", "ask", "bq1", "aq1", "imb1", "imb5", "imb20", "band10", "band25"]


def rebuild(path, grid_ms: int = 1000, chunk: int = 500_000):
    """Apply the update stream row by row. Returns (grid DataFrame, stats dict).

    A row with is_snapshot true opens a block that REPLACES the whole book; amount 0 deletes a level. The state is
    sampled at every grid_ms boundary as of the end of that millisecond (rows stamped <= the boundary are applied).
    stats: crossed seconds, empty seconds, reconnect blocks and how many matched the pre-block book (top 5 per side)."""
    bids: dict = {}
    asks: dict = {}
    bb, ba = 0.0, float("inf")
    rows: list = []
    stats = dict(samples=0, crossed=0, empty=0, blocks=0, block_match=0, rows=0)
    in_snap, snap_ts, pre = False, None, None
    next_g, last_row, dirty = None, None, True

    def close_block():
        nonlocal in_snap, pre
        if pre is not None and bids and asks:
            stats["blocks"] += 1
            post = (topk(bids, 5, True), topk(asks, 5, False))
            stats["block_match"] += int(post == pre)
        in_snap, pre = False, None

    for ch in pd.read_csv(path, usecols=["timestamp", "is_snapshot", "side", "price", "amount"], chunksize=chunk,
                          dtype={"timestamp": "int64", "price": "float64", "amount": "float64"}):
        ts = (ch.timestamp.to_numpy() // 1000).tolist()
        sn = ch.is_snapshot.to_numpy(bool).tolist()
        sd = (ch.side.to_numpy() == "bid").tolist()
        pr = ch.price.tolist()
        am = ch.amount.tolist()
        for t, snap, isbid, p, a in zip(ts, sn, sd, pr, am):
            if next_g is None:
                next_g = (t // grid_ms + 1) * grid_ms
            while t > next_g:                                    # emit the state as of every boundary passed
                stats["samples"] += 1
                if not bids or not asks:
                    stats["empty"] += 1
                elif bb >= ba:
                    stats["crossed"] += 1
                else:
                    if dirty or last_row is None:
                        last_row = feat_row(topk(bids, 20, True), topk(asks, 20, False), bids, asks)
                        dirty = False
                    rows.append((next_g,) + last_row)
                next_g += grid_ms
            stats["rows"] += 1
            if snap:
                if not in_snap or t != snap_ts:
                    if in_snap:
                        close_block()
                    pre = (topk(bids, 5, True), topk(asks, 5, False)) if bids and asks else None
                    bids.clear()
                    asks.clear()
                    bb, ba = 0.0, float("inf")
                    in_snap, snap_ts = True, t
            elif in_snap:
                close_block()
            dirty = True
            if isbid:
                if a > 0:
                    bids[p] = a
                    if p > bb:
                        bb = p
                else:
                    bids.pop(p, None)
                    if p == bb:
                        bb = max(bids) if bids else 0.0
            else:
                if a > 0:
                    asks[p] = a
                    if p < ba:
                        ba = p
                else:
                    asks.pop(p, None)
                    if p == ba:
                        ba = min(asks) if asks else float("inf")
    if in_snap:
        close_block()
    g = pd.DataFrame(rows, columns=GRID_COLS)
    return g, stats


def check_vs_snapshots(g: pd.DataFrame, path, k: int = 5) -> tuple:
    """Share of seconds whose rebuilt top-k PRICES (and, separately, quantities) equal the latest independent snapshot at
    or before that second. Returns (price match, quantity match, n)."""
    cols = ["timestamp"] + [f"{s}[{i}].{x}" for i in range(k) for s in ("asks", "bids") for x in ("price", "amount")]
    s = pd.read_csv(path, usecols=cols)
    s["t"] = s.timestamp // 1000
    s = s.sort_values("t", kind="stable").drop_duplicates("t", keep="last").reset_index(drop=True)
    j = np.searchsorted(s.t.to_numpy(), g.t.to_numpy(), "right") - 1
    ok = j >= 0
    s0, g0 = s.iloc[j[ok]].reset_index(drop=True), g[ok].reset_index(drop=True)
    return _top_match(g0, s0, "price"), _top_match(g0, s0, "amount"), len(g0)


def _top_match(g0, s0, what) -> float:
    # only the touch (bid, ask, bq1, aq1) is kept in the grid; the deeper levels are checked at the reconnect blocks
    if what == "price":
        return float((np.isclose(g0.bid, s0["bids[0].price"]) & np.isclose(g0.ask, s0["asks[0].price"])).mean())
    return float((np.isclose(g0.bq1, s0["bids[0].amount"]) & np.isclose(g0.aq1, s0["asks[0].amount"])).mean())


def grid_for(day: str, force: bool = False):
    pk = CACHE / f"grid_{day}.pkl"
    if pk.exists() and not force:
        return pd.read_pickle(pk)
    g, st = rebuild(DATA / f"{day}_incremental_book_L2.csv.gz")
    out = (g, st)
    pd.to_pickle(out, pk)
    return out


def load_trades(day: str) -> pd.DataFrame:
    """Tardis trades: side is the TAKER's side. Columns t (ms), side, price, qty (coins)."""
    tr = pd.read_csv(DATA / f"{day}_trades.csv.gz", usecols=["timestamp", "side", "price", "amount"])
    tr = tr.rename(columns={"amount": "qty"})
    tr["t"] = tr.timestamp // 1000
    return tr.sort_values("t", kind="stable").reset_index(drop=True)[["t", "side", "price", "qty"]]


# ---------------------------------------------------------------- features
HORIZONS = (10, 30)


def features(g: pd.DataFrame, tr: pd.DataFrame) -> pd.DataFrame:
    f = g.copy()
    f["mid"] = (f.bid + f.ask) / 2
    f["spread"] = (f.ask / f.bid - 1) * 1e4
    f["micro"] = ((f.bid * f.aq1 + f.ask * f.bq1) / (f.bq1 + f.aq1) / f.mid - 1) * 1e4
    tt = tr.t.to_numpy()
    usd = (tr.price * tr.qty).to_numpy()
    sg = np.where(tr.side.to_numpy() == "buy", 1.0, -1.0)
    cs_net, cs_all = np.r_[0.0, np.cumsum(sg * usd)], np.r_[0.0, np.cumsum(usd)]
    t = f.t.to_numpy()

    def flow(lo_ms, hi_ms):                                      # taker net share over (t+lo, t+hi]
        z = np.searchsorted(tt, t + hi_ms, "right")
        a = np.searchsorted(tt, t + lo_ms, "right")
        tot = cs_all[z] - cs_all[a]
        return np.where(tot > 0, (cs_net[z] - cs_net[a]) / np.where(tot > 0, tot, 1), 0.0)
    f["flow10"], f["flow30"] = flow(-10_000, 0), flow(-30_000, 0)
    f["flow_during"] = flow(0, 10_000)                           # the outcome window: used only to describe events
    f["ret_prior10"] = (f.mid / f.mid.shift(10) - 1) * 1e4
    f["aq1_rel"] = f.aq1 / f.aq1.rolling(60, min_periods=20).median()
    f["bq1_rel"] = f.bq1 / f.bq1.rolling(60, min_periods=20).median()
    for h in HORIZONS:
        j = np.searchsorted(t, t + h * 1000, "left")
        ok = j < len(t)
        jj = np.where(ok, j, len(t) - 1)
        m, b, a = f.mid.to_numpy(), f.bid.to_numpy(), f.ask.to_numpy()
        f[f"fwd{h}"] = np.where(ok, (m[jj] / m - 1) * 1e4, np.nan)
        f[f"tl{h}"] = np.where(ok, (b[jj] / a - 1) * 1e4, np.nan)      # a taker long: buy the ask, sell the bid later
        f[f"ts{h}"] = np.where(ok, (b / a[jj] - 1) * 1e4, np.nan)
    return f


# ---------------------------------------------------------------- 2. what changed around a big move
def event_study(f: pd.DataFrame) -> dict:
    a = f.fwd10.abs()
    thr = a.quantile(0.99)
    ev = f[a >= thr]
    ev = ev.iloc[spaced(ev.t.to_numpy(), 30_000)]
    d = np.sign(ev.fwd10.to_numpy())
    med_spread = f.spread.median()
    consumed = np.where(d > 0, ev.aq1_rel, ev.bq1_rel)
    out = dict(n=len(ev), thr=thr, spread_ratio=float(ev.spread.median() / med_spread),
               thin=float(np.nanmean(consumed < 1.0)), imb1=float(np.mean(d * ev.imb1 > 0)),
               imb1_mean=float(np.mean(d * ev.imb1)), pre_flow=float(np.mean(d * ev.flow10)),
               pre_flow_se=float(np.std(d * ev.flow10, ddof=1) / np.sqrt(len(ev))),
               during_flow=float(np.mean(d * ev.flow_during)), prior_ret=float(np.nanmean(d * ev.ret_prior10)),
               base_imb1=float(np.mean(np.sign(f.fwd10.dropna()) * f.imb1[f.fwd10.notna()] > 0)))
    return out


# ---------------------------------------------------------------- 3. the one claim, tuned on early days, read on later ones
def hypothesis(tune: dict, later: dict, feat: str = "imb1", h: int = 10) -> list:
    pool = pd.concat([x[feat] for x in tune.values()])
    lo, hi = pool.quantile(0.10), pool.quantile(0.90)
    rows = []
    for day, f in later.items():
        s = f.iloc[spaced(f.t.to_numpy(), h * 1000)]
        r_ic, n_ic = ic(s[feat].to_numpy(float), s[f"fwd{h}"].to_numpy(float))
        sig = f[(f[feat] >= hi) | (f[feat] <= lo)].copy()
        sig["d"] = np.where(sig[feat] >= hi, 1, -1)
        sig = sig.iloc[spaced(sig.t.to_numpy(), h * 1000)].dropna(subset=[f"fwd{h}"])
        mv = sig.d * sig[f"fwd{h}"]
        taker = np.where(sig.d > 0, sig[f"tl{h}"], sig[f"ts{h}"]) - 2 * TAKER_BP
        rows.append(dict(day=day, ic=r_ic, n_ic=n_ic, n=len(sig), move=float(mv.mean()),
                         se=float(mv.std(ddof=1) / np.sqrt(len(mv))), hit=float((mv > 0).mean()),
                         taker=float(np.mean(taker)), maker_ideal=float((mv - 2 * MAKER_BP).mean())))
    return rows


# ---------------------------------------------------------------- 4. the same signals, filled by the tape
def maker_fill(tt, tside, tprice, tqty, t_post: int, price: float, queue_ahead: float, rests_bid: bool,
               ttl_ms: int = TTL_MS):
    """When (ms) a post-only limit placed at t_post is filled by the tape, else None.

    A resting BID is hit by taker SELLS: a sell strictly below its price means the whole level was cleared (filled);
    sells AT the price first use up the queue ahead of us, and we fill once their cumulative size reaches it.
    A resting ASK mirrors this with taker BUYS. Trades stamped at or before t_post do not count."""
    want = "sell" if rests_bid else "buy"
    i = int(np.searchsorted(tt, t_post, "right"))
    end = t_post + ttl_ms
    cum = 0.0
    n = len(tt)
    while i < n and tt[i] <= end:
        if tside[i] == want:
            p = tprice[i]
            through = (p < price - EPS) if rests_bid else (p > price + EPS)
            if through:
                return int(tt[i])
            if abs(p - price) <= EPS:
                cum += tqty[i]
                if cum >= queue_ahead:
                    return int(tt[i])
        i += 1
    return None


def replay(f: pd.DataFrame, tr: pd.DataFrame, sig: pd.DataFrame, hold_s: int, qf: float, exit_mode: str) -> pd.DataFrame:
    """sig has columns t (ms) and d (+1 long / -1 short). One position at a time; returns one row per signal TAKEN."""
    tt, ts_, tp, tq = tr.t.to_numpy(), tr.side.to_numpy(), tr.price.to_numpy(), tr.qty.to_numpy()
    gt = f.t.to_numpy()
    bid, ask, bq1, aq1, mid = f.bid.to_numpy(), f.ask.to_numpy(), f.bq1.to_numpy(), f.aq1.to_numpy(), f.mid.to_numpy()
    out, free = [], -1
    for t0, d in zip(sig.t.to_numpy(), sig.d.to_numpy()):
        if t0 < free:
            continue
        i0 = int(np.searchsorted(gt, t0))
        if i0 >= len(gt) or gt[i0] != t0:
            continue
        long = d > 0
        p0 = bid[i0] if long else ask[i0]
        q0 = (bq1[i0] if long else aq1[i0]) * qf
        tf = maker_fill(tt, ts_, tp, tq, t0 + LAT_MS, p0, q0, rests_bid=long)
        jh = int(np.searchsorted(gt, t0 + hold_s * 1000, "left"))
        if jh >= len(gt):
            continue
        sig_move = d * (mid[jh] / mid[i0] - 1) * 1e4
        row = dict(t=t0, d=d, filled=tf is not None, sig_move=sig_move, net=0.0)
        if tf is None:
            free = t0 + TTL_MS + LAT_MS
            out.append(row)
            continue
        te = tf + hold_s * 1000
        je = int(np.searchsorted(gt, te + LAT_MS, "left"))
        if je >= len(gt):
            continue
        fee_out, px_out = TAKER_BP, (bid[je] if long else ask[je])
        t_done = gt[je]
        if exit_mode == "maker":                                  # a second limit at the touch, taker fallback after TTL
            pe = ask[je] if long else bid[je]
            qe = (aq1[je] if long else bq1[je]) * qf
            tx = maker_fill(tt, ts_, tp, tq, int(gt[je]) + LAT_MS, pe, qe, rests_bid=not long)
            if tx is not None:
                fee_out, px_out, t_done = MAKER_BP, pe, tx
            else:
                jf = int(np.searchsorted(gt, gt[je] + TTL_MS + LAT_MS, "left"))
                if jf >= len(gt):
                    continue
                px_out = bid[jf] if long else ask[jf]
                t_done = gt[jf]
        gross = d * (px_out / p0 - 1) * 1e4
        row.update(net=gross - MAKER_BP - fee_out, gross=gross, t_fill=tf)
        free = int(t_done) + 1
        out.append(row)
    return pd.DataFrame(out)


def replay_signals(f: pd.DataFrame, lo: float, hi: float, feat: str = "imb1") -> pd.DataFrame:
    s = f[(f[feat] >= hi) | (f[feat] <= lo)]
    return pd.DataFrame({"t": s.t.to_numpy(), "d": np.where(s[feat].to_numpy() >= hi, 1, -1)})


def summarize(rows: list) -> dict:
    """Pool replay() outputs across days: opportunity-weighted net (a missed fill is 0), fill rate, adverse selection."""
    A = pd.concat(rows) if rows else pd.DataFrame(columns=["filled", "net", "sig_move"])
    if not len(A):
        return dict(n=0)
    filled = A[A.filled]
    unf = A[~A.filled]
    per_day = [r.net.mean() for r in rows if len(r)]
    return dict(n=len(A), fill=float(A.filled.mean()), net_sig=float(A.net.mean()),
                net_se=float(A.net.std(ddof=1) / np.sqrt(len(A))) if len(A) > 1 else np.nan,
                net_fill=float(filled.net.mean()) if len(filled) else np.nan,
                adverse=float(filled.sig_move.mean() - unf.sig_move.mean()) if len(filled) and len(unf) else np.nan,
                days_pos=int(sum(x > 0 for x in per_day)), days=len(per_day))


# ---------------------------------------------------------------- the report
def main():
    days = [d for d in TUNE + LATER if (DATA / f"{d}_incremental_book_L2.csv.gz").exists()]
    lines = [f"backtest/book_hist.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; Bitget DOGEUSDT, Tardis free days: "
             + ", ".join(days), ""]
    grids, feats = {}, {}
    for d in days:
        g, st = grid_for(d)
        grids[d] = (g, st)
        tr = load_trades(d)
        feats[d] = features(g, tr)
        lines.append(f"[B1] {d}: {st['rows']:,} update rows -> {len(g):,} valid seconds of {st['samples']:,}; crossed "
                     f"{st['crossed']} ({st['crossed'] / max(st['samples'], 1) * 100:.4f}%), empty {st['empty']}; snapshot "
                     f"blocks {st['blocks']} (this feed is top-15 snapshots ~6/s, NOT diffs + reconnects), previous book == next block at {st['block_match']}"
                     + (f" ({st['block_match'] / st['blocks'] * 100:.0f}%)" if st["blocks"] else "") + f"; {len(tr):,} trades")
        print(lines[-1], flush=True)
    snap = DATA / "2026-09-01_book_snapshot_25.csv.gz"
    if "2026-09-01" in grids and snap.exists():
        pm, qm, n = check_vs_snapshots(grids["2026-09-01"][0], snap)
        lines.append(f"[B1] 2026-09-01 vs Tardis' independent snapshots, {n:,} seconds: touch prices equal {pm * 100:.2f}%, "
                     f"touch quantities equal {qm * 100:.2f}%")
    lines.append("")
    tune = {d: feats[d] for d in TUNE if d in feats}
    later = {d: feats[d] for d in LATER if d in feats}
    if not tune or not later:
        print("\n".join(lines))
        return
    lines.append("[E1] the top 1% of 10 s mid moves (spaced 30 s), per later day: spread vs median / touch thinner than its 60 s "
                 "median / imb1 points the way (all-moves base) / flow BEFORE and DURING (aligned share of volume) / "
                 "the 10 s before already moved")
    for d, f in {**tune, **later}.items():
        e = event_study(f)
        lines.append(f"  {d}: n {e['n']}, |move| >= {e['thr']:.1f}bp | spread x{e['spread_ratio']:.2f} | thin {e['thin'] * 100:.0f}% | "
                     f"imb1 {e['imb1'] * 100:.0f}% (base {e['base_imb1'] * 100:.0f}%) | flow before {e['pre_flow']:+.2f} "
                     f"(se {e['pre_flow_se']:.2f}), during {e['during_flow']:+.2f} | prior 10 s {e['prior_ret']:+.1f}bp")
    lines.append("")
    lines.append("[H1] imb1 -> next 10 s; thresholds (10th/90th) from the tune days, read on the later days: IC, then the "
                 "extreme-decile trade (mid move in the signalled direction, hit rate, taker net after 12bp, ideal-maker net after 4bp)")
    allrows = []
    for feat, h in (("imb1", 10), ("imb1", 30), ("micro", 10), ("imb5", 10), ("band10", 10)):
        rows = hypothesis(tune, later, feat, h)
        tag = "  PRIMARY" if (feat, h) == ("imb1", 10) else "  exploratory"
        lines.append(f" {tag}: {feat} @ {h} s")
        for r in rows:
            lines.append(f"    {r['day']}: IC {r['ic']:+.3f} (n {r['n_ic']}) | {r['n']:4} signals: move {r['move']:+.2f}bp "
                         f"(se {r['se']:.2f}), hit {r['hit'] * 100:.0f}%, taker net {r['taker']:+.2f}, maker-ideal {r['maker_ideal']:+.2f}")
        allrows.append(rows)
    lines.append("")
    pool = pd.concat([x["imb1"] for x in tune.values()])
    lo, hi = pool.quantile(0.10), pool.quantile(0.90)
    lines.append(f"[M1] the primary signal (imb1 <= {lo:+.3f} short / >= {hi:+.3f} long) traded the way an account could, on the "
                 f"later days: post at the touch, 0.5 s latency, 10 s to fill, one position at a time, fees maker {MAKER_BP:g}bp / "
                 f"taker {TAKER_BP:g}bp a leg; net per signal TAKEN (a missed fill is a 0)")
    for hold in (10, 30):
        for qf in (1.0, 0.5):
            for mode in ("taker", "maker"):
                res = []
                for d, f in later.items():
                    tr = load_trades(d)
                    res.append(replay(f, tr, replay_signals(f, lo, hi), hold, qf, mode))
                s = summarize(res)
                lines.append(f"  hold {hold:2} s, queue x{qf:.1f}, exit {mode:5}: {s['n']:5} signals taken, fill {s['fill'] * 100:3.0f}%, "
                             f"net/signal {s['net_sig']:+6.2f}bp (se {s['net_se']:.2f}), net/fill {s['net_fill']:+6.2f}bp, "
                             f"filled-minus-unfilled signalled move {s['adverse']:+.2f}bp, days positive {s['days_pos']}/{s['days']}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

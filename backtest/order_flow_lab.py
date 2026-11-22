"""ORDER-FLOW LAB - real numbers for the Module 2 lessons (docs/27), DOGE perp on Bitget, ONE day: 2026-06-01 (2026-10-30).

WHAT THIS IS: three DESCRIPTIVE measurements that make the lessons concrete. None is a test of a trading hypothesis and none is a result to trade on.
    A. one real book snapshot (the day's first): depth in dollars, imbalance over 1 / 5 / 20 levels, the microprice, depth bands
    B. executed pressure vs price on the same day: signed taker dollars per window (1 s, 5 s, 30 s, 1 min, 5 min) against the mid change in the
       SAME window (price impact: mechanical) and in the NEXT window (the only part that could ever be a signal)
    C. wall anatomy: every big resting level the day produced, how long it lived, how much of it was EXECUTED (the tape traded at its price)
       and how much was CANCELLED (it left without a trade), and how far from the mid it was when it left
DATA: Tardis' Bitget DOGEUSDT update stream and tape (strategy_analysis/data/book_hist/bitget/). 2026-06-01 is a true diff stream (aggregated BY PRICE
    LEVEL: a row says "price P now holds total size Q"; individual orders are invisible). It is used here as the TEACHING / DEFINITION day. 2026-09-01,
    the other true diff day, is NOT read, so it stays available for one confirmatory look later; anything that becomes a hypothesis is registered in
    Module 4 and judged on data recorded after this date, on the ten pairs.
WALL (exploratory definition, K_REL / MIN_USD / NEAR / SCAN below, chosen BEFORE seeing any wall statistic): within the 20 nearest levels of a side, a level
    whose dollar size is at least 5x the median of the 10 nearest levels AND at least $20,000. It is followed from the second it is first seen until it
    falls under 50% of its peak (or under the wall threshold), the book is re-synced by a snapshot, or the day ends (censored). A level cannot restart within
    60 s of ending. EXECUTED = tape volume at that price on the consuming side (taker buys hit asks, taker sells hit bids) while it is followed; CANCELLED =
    what left the level beyond that, per episode: max(removed - executed, 0). Because the book is aggregated, a cancel cannot be told from a partial
    withdrawal, and an iceberg refill looks like a new order.

REGISTERED BEFORE THE FIRST RUN (2026-10-30)
    L1  Same-window correlation of signed taker flow with the mid change is clearly positive at every window and grows with the window (>= +0.3 at 30 s and
        longer): price impact is mechanical. The NEXT-window correlation is small (|rho| < 0.10) at every window.
    L2  Walls are short-lived: the median lifetime is under 30 s.
    L3  Most of what leaves a wall is cancelled, not executed: cancelled share of removed dollars > 70%.
    L4  Cancels happen far from the touch: > 60% of cancelled dollars leave while the wall is more than 3bp from the mid; executions are concentrated
        within 1bp (> 60% of executed dollars).
    L5  Replenishment is uncommon: under 25% of episodes add back at least half of their starting size.

    python -m backtest.order_flow_lab          all three parts; writes logs/order_flow_lab.txt (about 5 minutes: it replays 5.5M book updates)
    python -m backtest.order_flow_lab --cache  the same, reusing the saved wall episodes (seconds)
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.book_hist import CACHE, DATA, load_trades, topk  # noqa: E402

LOG = ROOT / "logs" / "order_flow_lab.txt"
DAY = "2026-06-01"
K_REL, MIN_USD, NEAR, SCAN = 5.0, 20_000.0, 10, 20
END_FRAC, COOLDOWN_MS = 0.5, 60_000
BUCKETS = [(0.0, 1.0), (1.0, 3.0), (3.0, 10.0), (10.0, float("inf"))]
BUCKET_NAMES = ["<= 1bp", "1-3bp", "3-10bp", "> 10bp"]
WINDOWS = (1, 5, 30, 60, 300)


def bucket(dist_bp: float) -> int:
    for i, (lo, hi) in enumerate(BUCKETS):
        if lo <= dist_bp < hi:
            return i
    return len(BUCKETS) - 1


# ------------------------------------------------------------------ C. the wall tracker (pure: fed events, returns episodes)

class WallTracker:
    """Follows big resting levels. Feed it: start() when a scan sees a wall, on_update() for every size change at a followed level, on_trade() for every
    print, resync() at a snapshot block, finish() at the end. Dollar amounts are price x quantity at the level's own price."""

    def __init__(self):
        self.live: dict = {}
        self.done: list = []
        self.recent: dict = {}

    def start(self, key, usd: float, ts: int, dist_bp: float) -> bool:
        if key in self.live or ts - self.recent.get(key, -10 ** 15) < COOLDOWN_MS:
            return False
        self.live[key] = dict(side="bid" if key[0] else "ask", price=key[1], t0=ts, s0=usd, peak=usd, size=usd, added=0.0, removed=0.0, executed=0.0,
                              rem_b=[0.0] * len(BUCKETS), exe_b=[0.0] * len(BUCKETS), birth_bp=dist_bp, min_bp=dist_bp)
        return True

    def on_update(self, key, old_qty: float, new_qty: float, ts: int, mid: float, floor_usd: float = 0.0):
        w = self.live.get(key)
        if w is None:
            return
        p = key[1]
        dist = abs(p - mid) / mid * 1e4
        if new_qty > old_qty:
            w["added"] += (new_qty - old_qty) * p
        elif new_qty < old_qty:
            d = (old_qty - new_qty) * p
            w["removed"] += d
            w["rem_b"][bucket(dist)] += d
        w["size"] = new_qty * p
        w["peak"] = max(w["peak"], w["size"])
        w["min_bp"] = min(w["min_bp"], dist)
        if w["size"] < END_FRAC * w["peak"] or w["size"] < floor_usd:
            self.close(key, ts, "faded")

    def on_trade(self, taker_side: str, price: float, qty: float, mid: float):
        key = (taker_side == "sell", price)                     # a taker SELL hits the bids; a taker BUY lifts the asks
        w = self.live.get(key)
        if w is None:
            return
        usd = qty * price
        w["executed"] += usd
        w["exe_b"][bucket(abs(price - mid) / mid * 1e4)] += usd

    def touch_distance(self, mid: float):
        for key, w in self.live.items():
            w["min_bp"] = min(w["min_bp"], abs(key[1] - mid) / mid * 1e4)

    def close(self, key, ts: int, why: str):
        w = self.live.pop(key, None)
        if w is None:
            return
        w["t1"], w["why"], w["life_s"] = ts, why, (ts - w["t0"]) / 1000.0
        rem, exe = w["removed"], min(w["executed"], w["removed"])
        w["cancelled"] = max(rem - w["executed"], 0.0)
        w["cancel_share"] = (w["cancelled"] / rem) if rem > 0 else float("nan")
        self.recent[key] = ts
        self.done.append(w)

    def resync(self, ts: int):
        for key in list(self.live):
            self.close(key, ts, "resync")

    def finish(self, ts: int):
        for key in list(self.live):
            self.close(key, ts, "censored")


def wall_anatomy(day: str = DAY) -> pd.DataFrame:
    tr = load_trades(day)
    tt, ts_, tp, tq = tr.t.to_numpy(), tr.side.to_numpy(), tr.price.to_numpy(float), tr.qty.to_numpy(float)
    n_tr, ti = len(tt), 0
    W = WallTracker()
    bids: dict = {}
    asks: dict = {}
    bb, ba = 0.0, float("inf")
    next_g, in_snap, snap_ts, last_t = None, False, None, 0

    def scan(ts):
        if not bids or not asks or bb >= ba:
            return
        mid = (bb + ba) / 2
        for isbid, book in ((True, bids), (False, asks)):
            lv = topk(book, SCAN, isbid)
            usd = [p * q for p, q in lv]
            if len(usd) < NEAR:
                continue
            thr = max(K_REL * statistics.median(usd[:NEAR]), MIN_USD)
            for (p, q), u in zip(lv, usd):
                if u >= thr:
                    W.start((isbid, p), u, ts, abs(p - mid) / mid * 1e4)
        W.touch_distance(mid)

    path = DATA / f"{day}_incremental_book_L2.csv.gz"
    for ch in pd.read_csv(path, usecols=["timestamp", "is_snapshot", "side", "price", "amount"], chunksize=500_000,
                          dtype={"timestamp": "int64", "price": "float64", "amount": "float64"}):
        ts = (ch.timestamp.to_numpy() // 1000).tolist()
        sn = ch.is_snapshot.to_numpy(bool).tolist()
        sd = (ch.side.to_numpy() == "bid").tolist()
        pr = ch.price.tolist()
        am = ch.amount.tolist()
        for t, snap, isbid, p, a in zip(ts, sn, sd, pr, am):
            if next_g is None:
                next_g = (t // 1000 + 1) * 1000
            while t > next_g:
                scan(next_g)
                next_g += 1000
            while ti < n_tr and tt[ti] <= t:
                if bids and asks and bb < ba:
                    W.on_trade(ts_[ti], tp[ti], tq[ti], (bb + ba) / 2)
                ti += 1
            if snap:
                if not in_snap or t != snap_ts:
                    W.resync(t)
                    bids.clear()
                    asks.clear()
                    bb, ba = 0.0, float("inf")
                    in_snap, snap_ts = True, t
            else:
                in_snap = False
            book = bids if isbid else asks
            old = book.get(p, 0.0)
            valid = bids and asks and bb < ba
            mid = (bb + ba) / 2 if valid else None
            if a > 0:
                book[p] = a
                if isbid and p > bb:
                    bb = p
                elif not isbid and p < ba:
                    ba = p
            else:
                book.pop(p, None)
                if isbid and p == bb:
                    bb = max(bids) if bids else 0.0
                elif not isbid and p == ba:
                    ba = min(asks) if asks else float("inf")
            if not snap and mid is not None and (isbid, p) in W.live:
                W.on_update((isbid, p), old, a, t, mid, floor_usd=MIN_USD)
            last_t = t
    W.finish(last_t)
    return pd.DataFrame(W.done)


def describe_walls(E: pd.DataFrame) -> list:
    L = []
    P = L.append
    real = E[E.why != "resync"]
    P(f"  episodes {len(E)} ({(E.why == 'resync').sum()} cut by a snapshot re-sync and excluded, {(real.why == 'censored').sum()} still alive at the end of the day); "
      f"bids {(real.side == 'bid').sum()}, asks {(real.side == 'ask').sum()}")
    P(f"  size at first sight: median ${real.s0.median():,.0f}, 90th percentile ${real.s0.quantile(0.9):,.0f}; distance from the mid when first seen: "
      f"median {real.birth_bp.median():.1f}bp")
    q = real.life_s.quantile([0.1, 0.25, 0.5, 0.75, 0.9]).to_numpy()
    P(f"  lifetime in seconds, 10/25/50/75/90th percentile: " + " / ".join(f"{v:,.0f}" for v in q))
    P("  share of episodes that ended within: " + ", ".join(f"{s} s {(real.life_s <= s).mean() * 100:.0f}%" for s in (1, 5, 30, 300)))
    rem, exe = real.removed.sum(), np.minimum(real.executed, real.removed).sum()
    canc = real.cancelled.sum()
    P(f"  dollars that LEFT the followed levels ${rem:,.0f}: executed (tape traded at the price) {exe / rem * 100:.0f}%, cancelled {canc / rem * 100:.0f}%")
    cs = real.cancel_share.dropna()
    P(f"  by episode: mostly cancelled (>75%) {(cs > 0.75).mean() * 100:.0f}%, mixed {((cs >= 0.25) & (cs <= 0.75)).mean() * 100:.0f}%, mostly executed (<25%) "
      f"{(cs < 0.25).mean() * 100:.0f}%  (of {len(cs)} with anything removed)")
    rb = np.array(real.rem_b.tolist()).sum(0)
    eb = np.array(real.exe_b.tolist()).sum(0)
    eb_c = np.minimum(eb, rb)
    cb = rb - eb_c
    P("  where it left (distance of the level from the mid at that moment):")
    P(f"    {'':8s} {'left $':>14s} {'executed $':>14s} {'cancelled $':>14s} {'share of all cancels':>20s} {'share of all executions':>24s}")
    for i, nm in enumerate(BUCKET_NAMES):
        P(f"    {nm:8s} {rb[i]:14,.0f} {eb_c[i]:14,.0f} {cb[i]:14,.0f} {cb[i] / max(cb.sum(), 1) * 100:19.0f}% {eb_c[i] / max(eb_c.sum(), 1) * 100:23.0f}%")
    P(f"  replenished (added back at least half of the starting size while followed): {(real.added >= 0.5 * real.s0).mean() * 100:.0f}% of episodes")
    P(f"  got within 1bp of the mid at some point: {(real.min_bp <= 1).mean() * 100:.0f}%; ended while still more than 5bp away: {(real.min_bp > 5).mean() * 100:.0f}%")
    P("  BY HOW CLOSE THE WALL EVER CAME TO THE MID (a wall can only be executed if price comes to it):")
    P(f"    {'closest approach':26s} {'episodes':>9s} {'median life s':>14s} {'executed share of $ left':>25s} {'any execution':>14s} {'median start $':>15s}")
    for nm, m in (("never closer than 5bp", real.min_bp > 5), ("came within 3bp", real.min_bp <= 3), ("came within 1bp", real.min_bp <= 1)):
        x = real[m]
        if len(x):
            ex = np.minimum(x.executed, x.removed).sum() / max(x.removed.sum(), 1)
            P(f"    {nm:26s} {len(x):9d} {x.life_s.median():14.1f} {ex * 100:24.1f}% {(x.executed > 0).mean() * 100:13.0f}% {x.s0.median():15,.0f}")
    q = real.birth_bp.quantile([0.1, 0.25, 0.5, 0.75, 0.9]).round(1).tolist()
    P(f"  distance from the mid when FIRST SEEN, 10/25/50/75/90th percentile (bp): {q} - first seen is not born: a level is first seen when it enters the "
      f"{SCAN}-level window, which on a 1bp tick is only ~{SCAN}bp wide, so the many near 19-20bp walked in from outside")
    return L


# ------------------------------------------------------------------ B. executed pressure vs price

def flow_vs_price(day: str = DAY) -> list:
    g, _ = pd.read_pickle(CACHE / f"grid_{day}.pkl")
    mid = ((g.bid + g.ask) / 2).to_numpy(float)
    t_ms = g.t.to_numpy("int64")
    t0 = (t_ms[0] // 1000) * 1000
    sec = ((t_ms - t0) // 1000).astype(int)
    mid_s = np.full(sec.max() + 1, np.nan)
    mid_s[sec] = mid
    mid_s = pd.Series(mid_s).ffill().to_numpy()
    tr = load_trades(day)
    s = ((tr.t.to_numpy() - t0) // 1000).astype(int)
    keep = (s >= 0) & (s < len(mid_s))
    usd = (tr.qty.to_numpy(float) * tr.price.to_numpy(float) * np.where(tr.side.to_numpy() == "buy", 1.0, -1.0))[keep]
    s = s[keep]
    L = [f"  {len(tr):,} trades; net taker dollars per window (buys +, sells -) against the mid change in bp over the same window and over the NEXT window",
         f"  {'window':>7s} {'bins':>6s} {'same-window rho':>16s} {'bp per $100k':>13s} {'signs agree':>12s} {'next-window rho':>16s}"]
    for w in WINDOWS:
        nb = len(mid_s) // w - 1
        flow = np.bincount(s // w, weights=usd, minlength=nb + 1)[:nb]
        dm = (mid_s[(np.arange(nb) + 1) * w] - mid_s[np.arange(nb) * w]) / mid_s[np.arange(nb) * w] * 1e4
        ok = np.isfinite(dm)
        f, d = flow[ok], dm[ok]
        rho = pd.Series(f).corr(pd.Series(d), method="spearman")
        slope = np.cov(f, d)[0, 1] / np.var(f, ddof=1) * 1e5
        nz = (f != 0) & (d != 0)
        agree = np.mean(np.sign(f[nz]) == np.sign(d[nz]))
        lag = pd.Series(f[:-1]).corr(pd.Series(d[1:]), method="spearman")
        L.append(f"  {w:>5d} s {len(f):6d} {rho:16.3f} {slope:13.2f} {agree * 100:11.0f}% {lag:16.3f}")
    return L


# ------------------------------------------------------------------ A. one real snapshot

def snapshot_example(day: str = DAY) -> list:
    d = pd.read_csv(DATA / f"{day}_incremental_book_L2.csv.gz", usecols=["timestamp", "is_snapshot", "side", "price", "amount"], nrows=6000)
    d = d[(d.timestamp == d.timestamp.iloc[0]) & d.is_snapshot]
    bd = d[d.side == "bid"].sort_values("price", ascending=False).reset_index(drop=True)
    ak = d[d.side == "ask"].sort_values("price").reset_index(drop=True)
    for x in (bd, ak):
        x["usd"] = x.price * x.amount
    mid = (bd.price[0] + ak.price[0]) / 2
    L = [f"  the day's first snapshot, {pd.to_datetime(d.timestamp.iloc[0], unit='us')} UTC: {len(bd)} bid levels, {len(ak)} ask levels; best bid {bd.price[0]}, "
         f"best ask {ak.price[0]}, spread {(ak.price[0] - bd.price[0]) / mid * 1e4:.2f}bp",
         f"  {'level':>5s} {'bid price':>10s} {'bid $':>10s} {'ask price':>10s} {'ask $':>10s}"]
    for i in range(6):
        L.append(f"  {i + 1:>5d} {bd.price[i]:10.5f} {bd.usd[i]:10,.0f} {ak.price[i]:10.5f} {ak.usd[i]:10,.0f}")
    for k in (1, 5, 20):
        b, a = bd.usd[:k].sum(), ak.usd[:k].sum()
        L.append(f"  imbalance over the nearest {k:>2d} level(s): bid ${b:,.0f} vs ask ${a:,.0f} -> (B - A) / (B + A) = {(b - a) / (b + a):+.3f}")
    qb, qa = bd.amount[0], ak.amount[0]
    micro = (bd.price[0] * qa + ak.price[0] * qb) / (qa + qb)
    L.append(f"  microprice (each side's price weighted by the OTHER side's size) {micro:.6f} vs mid {mid:.6f}: {(micro - mid) / mid * 1e4:+.2f}bp")
    for bp in (10, 25):
        b = bd[bd.price >= mid * (1 - bp / 1e4)].usd.sum()
        a = ak[ak.price <= mid * (1 + bp / 1e4)].usd.sum()
        L.append(f"  depth within {bp}bp of the mid: bids ${b:,.0f}, asks ${a:,.0f}")
    return L


def main():
    L = [f"backtest/order_flow_lab.py, DOGEUSDT perp on Bitget, {DAY} (Tardis), run {pd.Timestamp.now():%Y-%m-%d %H:%M}",
         "\nA. ONE REAL BOOK SNAPSHOT"]
    L += snapshot_example()
    L += ["\nB. EXECUTED PRESSURE VS PRICE (descriptive)"] + flow_vs_price()
    cache = CACHE / f"walls_{DAY}.pkl"
    E = pd.read_pickle(cache) if ("--cache" in sys.argv and cache.exists()) else wall_anatomy()
    L += [f"\nC. WALL ANATOMY (wall = >= {K_REL:g}x the median of the {NEAR} nearest levels and >= ${MIN_USD:,.0f}, looked for in the {SCAN} nearest)"] + describe_walls(E)
    txt = "\n".join(L)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")
    E.to_pickle(CACHE / f"walls_{DAY}.pkl")


if __name__ == "__main__":
    main()

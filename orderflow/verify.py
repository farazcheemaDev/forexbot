"""Verify a recording: rebuild every book from the raw frames and report whether it can be trusted (Module 5).

    python -m orderflow.verify strategy_analysis/data/orderflow_trial

For each pair it replays the raw frames through orderflow.book.Book and reports: how many snapshots / updates / gaps / frames arrived while unsynced; whether the rebuilt
book was ever crossed; the cadence of updates; how far local receive time lags the server timestamp (network delay PLUS any clock offset of this PC - the two cannot be
separated); the snapshot depth and how many basis points it covers; how the book's level count drifts; trade counts, duplicates and ordering; the bytes on disk; and the
result of every SNAPSHOT AUDIT. Bitget's `seq` is global across connections, so a fresh snapshot fetched over a second connection (audit/) must equal the rebuilt
book at the SAME seq, level for level: 'exact' = that seq exists in the main stream and the books are identical; 'differ' = it exists and they are not (a real problem);
'approx' = the seq falls between two main messages, so the snapshot is compared with the last main state before it (identical = fine, different = inconclusive on a hot
book); 'outside' = the snapshot is older or newer than the recording. (The first design compared with Bitget's REST order book instead and matched only 30%: the REST book
is not tied to the stream's state. See orderflow/recorder.py, R4.)
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

import orjson

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orderflow.book import Book  # noqa: E402
from orderflow.store import EventLog, iter_raw  # noqa: E402


def _pct(xs, q):
    if not xs:
        return float("nan")
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def load_audits(root: Path, pair: str) -> list:
    """The pair's audit snapshots, sorted by seq: dicts with seq, ts, bids, asks (dicts price -> size)."""
    out = []
    for _, raw in iter_raw(Path(root), pair):
        try:
            d = orjson.loads(raw)["data"][0]
            out.append(dict(seq=d["seq"], ts=int(d["ts"]), bids={float(p): float(s) for p, s in d["bids"]}, asks={float(p): float(s) for p, s in d["asks"]}))
        except Exception:
            continue
    return sorted(out, key=lambda a: a["seq"])


def same_book(book: Book, a: dict) -> bool:
    return book.bids == a["bids"] and book.asks == a["asks"]


def verify_pair(root: Path, pair: str, audit_root: Path = None, since: str = None) -> dict:
    """`root` holds the pair's raw frames (root/<pair>/); the audit snapshots are read from `audit_root`/<pair>/ (default: ../audit next to root)."""
    book = Book()
    aud = load_audits(audit_root if audit_root is not None else Path(root).parent / "audit", pair)
    ai = 0
    audit_res = dict(exact=0, differ=0, approx_same=0, approx_diff=0, outside=0)
    r = dict(pair=pair, frames=0, snapshots=0, checkpoints=0, updates=0, gaps=0, unsynced=0, crossed=0, trades=0, trade_dupes=0, trade_disorder=0, bad=0,
             first_recv=None, last_recv=None, snap_depth=None, snap_cover_bp=None, max_levels=0, end_levels=0)
    gaps_ms, lag_books, lag_trades, nlev = [], [], [], []
    last_book_ts, seen_trades, last_trade_max = None, set(), None
    desc_msgs = multi_msgs = 0
    first_seq = None
    side_usd = {"buy": 0.0, "sell": 0.0}
    for recv_ns, raw in iter_raw(root, pair, since):
        r["frames"] += 1
        r["first_recv"] = r["first_recv"] or recv_ns
        r["last_recv"] = recv_ns
        try:
            m = orjson.loads(raw)
            ch, act, data = m["arg"]["channel"], m["action"], m["data"]
        except Exception:
            r["bad"] += 1
            continue
        if ch == "books":
            d = data[0]
            seq = d.get("seq")
            first_seq = first_seq if first_seq is not None else seq
            while ai < len(aud) and seq is not None and seq > aud[ai]["seq"]:           # this audit's seq was passed without an exact hit
                if aud[ai]["seq"] < first_seq or not book.ready:
                    audit_res["outside"] += 1
                else:
                    audit_res["approx_same" if same_book(book, aud[ai]) else "approx_diff"] += 1
                ai += 1
            res = book.apply(act, d)
            if ai < len(aud) and book.ready and book.seq == aud[ai]["seq"]:
                audit_res["exact" if same_book(book, aud[ai]) else "differ"] += 1
                ai += 1
            if res == "checkpoint":
                r["checkpoints"] += 1
                last_book_ts = int(d["ts"])
            if res == "snapshot":
                r["snapshots"] += 1
                if r["snap_depth"] is None:
                    r["snap_depth"] = book.snapshot_depth
                    r["snap_cover_bp"] = book.coverage_bp()
                last_book_ts = int(d["ts"])
            elif res == "ok":
                r["updates"] += 1
                ts = int(d["ts"])
                if last_book_ts is not None:
                    gaps_ms.append(ts - last_book_ts)
                last_book_ts = ts
                lag_books.append(recv_ns / 1e6 - ts)
                nlev.append(len(d["bids"]) + len(d["asks"]))
            elif res == "gap":
                r["gaps"] += 1
            elif res == "unsynced":
                r["unsynced"] += 1
            if book.ready:
                if book.crossed():
                    r["crossed"] += 1
                lv = len(book.bids) + len(book.asks)
                r["max_levels"] = max(r["max_levels"], lv)
                r["end_levels"] = lv
        elif ch == "trade":
            stamps = [int(t["ts"]) for t in data]
            if act == "update":
                if len(stamps) > 1:
                    multi_msgs += 1
                    desc_msgs += stamps == sorted(stamps, reverse=True) and stamps != sorted(stamps)
                if last_trade_max is not None and max(stamps) < last_trade_max:
                    r["trade_disorder"] += 1                                          # a whole message older than the previous one
                last_trade_max = max(stamps)
            for t in data:
                tid, ts = t["tradeId"], int(t["ts"])
                if tid in seen_trades:
                    r["trade_dupes"] += 1
                    continue
                seen_trades.add(tid)
                r["trades"] += 1
                side_usd[t["side"]] = side_usd.get(t["side"], 0.0) + float(t["price"]) * float(t["size"])
                if act == "update":
                    lag_trades.append(recv_ns / 1e6 - ts)
    r.update(gap_ms=(_pct(gaps_ms, .1), _pct(gaps_ms, .5), _pct(gaps_ms, .9)), lag_books_ms=(_pct(lag_books, .1), _pct(lag_books, .5), _pct(lag_books, .9)),
             lag_trades_ms=(_pct(lag_trades, .1), _pct(lag_trades, .5), _pct(lag_trades, .9)), levels_per_update=statistics.median(nlev) if nlev else float("nan"),
             trade_usd=side_usd)
    while ai < len(aud):                                                              # audits newer than the last recorded message
        audit_res["outside"] += 1
        ai += 1
    r["audit"] = audit_res
    r["multi_trade_msgs"], r["newest_first_msgs"] = multi_msgs, int(desc_msgs)
    pdir = Path(root) / pair
    r["disk_bytes"] = sum(p.stat().st_size for p in pdir.glob("*.log.gz")) if pdir.exists() else 0
    return r


def report(root: Path, pairs=None, since: str = None) -> str:
    root = Path(root)
    events = EventLog(root / "events.jsonl").read()
    pairs = pairs or sorted(p.name for p in (root / "raw").iterdir() if p.is_dir())
    rows = [verify_pair(root / "raw", p, root / "audit", since) for p in pairs]
    L = []
    dur = max((r["last_recv"] - r["first_recv"]) / 1e9 for r in rows if r["first_recv"]) if rows else 0
    kinds = {}
    for e in events:
        kinds[e["type"]] = kinds.get(e["type"], 0) + 1
    L.append(f"{root}: {len(rows)} pairs, {dur / 60:.1f} minutes recorded; events: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
    L.append(f"{'pair':9s} {'frames':>8s} {'snap/ck':>8s} {'updates':>8s} {'gaps':>4s} {'unsy':>5s} {'cross':>5s} {'trades':>7s} {'dupe':>4s} {'badO':>4s} {'upd gap ms p10/50/90':>22s} "
             f"{'lag ms p10/50/90':>18s} {'lvls/upd':>8s} {'audit exact/differ/approx/out':>30s}")
    for r in rows:
        L.append(f"{r['pair']:9s} {r['frames']:8d} {str(r['snapshots']) + '/' + str(r['checkpoints']):>8s} {r['updates']:8d} {r['gaps']:4d} {r['unsynced']:5d} {r['crossed']:5d} {r['trades']:7d} {r['trade_dupes']:4d} "
                 f"{r['trade_disorder']:4d} {r['gap_ms'][0]:6.0f}/{r['gap_ms'][1]:4.0f}/{r['gap_ms'][2]:5.0f}  {r['lag_books_ms'][0]:5.0f}/{r['lag_books_ms'][1]:4.0f}/{r['lag_books_ms'][2]:5.0f}  "
                 f"{r['levels_per_update']:8.1f} {r['audit']['exact']:9d}/{r['audit']['differ']}/{r['audit']['approx_same'] + r['audit']['approx_diff']}/{r['audit']['outside']}")
    L.append("")
    L.append(f"{'pair':9s} {'snapshot depth (bids, asks)':>28s} {'covers (bid, ask) bp':>24s} {'levels at end / max':>20s} {'disk MB':>8s} {'MB / day':>9s} {'trades/s':>9s}")
    tot = 0.0
    for r in rows:
        secs = max((r["last_recv"] - r["first_recv"]) / 1e9, 1.0)
        perday = r["disk_bytes"] / secs * 86400 / 1e6
        tot += perday
        d, c = r["snap_depth"] or (0, 0), r["snap_cover_bp"] or (float("nan"),) * 2
        L.append(f"{r['pair']:9s} {str(d):>28s} {c[0]:11.1f}, {c[1]:9.1f} {r['end_levels']:10d} / {r['max_levels']:<8d} {r['disk_bytes'] / 1e6:8.2f} {perday:9.0f} {r['trades'] / secs:9.2f}")
    L.append(f"extrapolated disk use of all pairs: {tot:,.0f} MB a day = {tot * 30 / 1e3:,.1f} GB for 30 days (a straight multiple of this window; busy hours differ)")
    return "\n".join(L)


def main():
    args = sys.argv[1:]
    since = None
    if "--since" in args:
        i = args.index("--since")
        since = args[i + 1]
        del args[i:i + 2]
    if not args:
        raise SystemExit("usage: python -m orderflow.verify <recording folder> [--since YYYY-MM-DD_HH] [pair ...]")
    txt = report(Path(args[0]), args[1:] or None, since)
    print(txt)


if __name__ == "__main__":
    main()

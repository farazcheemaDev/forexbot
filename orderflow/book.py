"""One pair's order book, rebuilt from Bitget's public `books` channel (Module 5).

WHAT THE FEED SENDS (measured on the live feed 2026-10-30, docs/27 Module 5): a `snapshot` message (200 levels a side; BTC 500) and then `update` messages about every
100 ms. Each message holds data[0] = {asks, bids, ts, seq, pseq}: `asks` / `bids` are lists of [price, size] STRINGS; size "0" deletes the level; `ts` is the SERVER
time in ms; `seq` numbers the message and `pseq` is the `seq` of the message before it. There is NO checksum on this channel, so integrity rests on the chain:
an update is valid only if its `pseq` equals the `seq` of the last message applied. A break means a message was missed and the book can no longer be trusted
until a new snapshot arrives.

THE BOOK IS AGGREGATED BY PRICE LEVEL: a row says "price P now holds total size Q". Individual orders are invisible.

All accessors treat `ready = False` (before a snapshot, or after a gap) as "no book".
"""
from __future__ import annotations

import json
import math


def _levels(rows) -> list:
    return [(float(p), float(s)) for p, s in rows]


class Book:
    def __init__(self):
        self.bids: dict = {}
        self.asks: dict = {}
        self.seq = None
        self.ts = 0                 # server time (ms) of the last applied message
        self.ready = False
        self.snapshot_depth = (0, 0)

    # ------------------------------------------------------------------ applying messages
    def apply(self, action: str, d: dict) -> str:
        """Apply one `books` message body. Returns 'snapshot', 'checkpoint', 'ok', 'gap' (chain broken: the book is now not ready) or 'unsynced' / 'ignored'.
        A 'checkpoint' is OUR OWN message (see checkpoint_message): the book as it stood after `seq`, written at the top of every hourly file so that the file can be read on
        its own. It replaces the book exactly like a snapshot, but it is the same chain position, so the next update's pseq still equals its seq."""
        if action in ("snapshot", "checkpoint"):
            self.bids = {p: s for p, s in _levels(d["bids"]) if s > 0}
            self.asks = {p: s for p, s in _levels(d["asks"]) if s > 0}
            self.seq, self.ts, self.ready = d.get("seq"), int(d["ts"]), True
            self.snapshot_depth = (len(self.bids), len(self.asks))
            return action
        if action != "update":
            return "ignored"
        if not self.ready:
            return "unsynced"
        if d.get("pseq") != self.seq:
            self.ready = False
            return "gap"
        # parse EVERYTHING before touching the book: a malformed message must raise with the book unchanged, never half-applied
        bids, asks, seq, ts = _levels(d["bids"]), _levels(d["asks"]), d["seq"], int(d["ts"])
        for rows, book in ((bids, self.bids), (asks, self.asks)):
            for p, s in rows:
                if s == 0:
                    book.pop(p, None)
                else:
                    book[p] = s
        self.seq, self.ts = seq, ts
        return "ok"

    def checkpoint_message(self, pair: str) -> str:
        """The current book as one JSON frame in the exchange's own snapshot layout (action 'checkpoint'); prices and sizes are written with repr() so they parse back exactly."""
        d = dict(bids=[[repr(p), repr(s)] for p, s in sorted(self.bids.items(), reverse=True)], asks=[[repr(p), repr(s)] for p, s in sorted(self.asks.items())],
                 ts=str(self.ts), seq=self.seq, pseq=self.seq)
        return json.dumps({"action": "checkpoint", "arg": {"instType": "USDT-FUTURES", "channel": "books", "instId": pair}, "data": [d], "ts": self.ts}, separators=(",", ":"))

    # ------------------------------------------------------------------ the touch
    def best(self):
        if not self.ready or not self.bids or not self.asks:
            return None
        return max(self.bids), min(self.asks)

    def crossed(self) -> bool:
        b = self.best()
        return b is not None and b[0] >= b[1]

    def mid(self) -> float:
        b = self.best()
        return (b[0] + b[1]) / 2 if b else math.nan

    def spread_bp(self) -> float:
        b = self.best()
        return (b[1] - b[0]) / ((b[0] + b[1]) / 2) * 1e4 if b else math.nan

    def levels(self, side: str, n: int) -> list:
        """The n levels nearest the touch on a side ('bid' or 'ask'), as (price, size), nearest first."""
        if not self.ready:
            return []
        if side == "bid":
            return sorted(self.bids.items(), reverse=True)[:n]
        return sorted(self.asks.items())[:n]

    # ------------------------------------------------------------------ depth, in dollars and in basis points (never in level counts)
    def usd_within(self, side: str, bp: float) -> float:
        """Dollars resting on a side within `bp` basis points of the mid. NaN when the recorded depth does not reach that far (the band would be truncated)."""
        b = self.best()
        if b is None:
            return math.nan
        mid = (b[0] + b[1]) / 2
        book = self.bids if side == "bid" else self.asks
        if not book:
            return math.nan
        far = min(book) if side == "bid" else max(book)
        if abs(far - mid) / mid * 1e4 < bp:
            return math.nan
        return sum(p * s for p, s in book.items() if abs(p - mid) / mid * 1e4 <= bp)

    def coverage_bp(self) -> tuple:
        """How far from the mid the farthest recorded level lies, in bp: (bid side, ask side)."""
        b = self.best()
        if b is None:
            return math.nan, math.nan
        mid = (b[0] + b[1]) / 2
        return (mid - min(self.bids)) / mid * 1e4, (max(self.asks) - mid) / mid * 1e4

    def imbalance_levels(self, k: int) -> float:
        """(B - A) / (B + A) over the k nearest levels of each side, in dollars."""
        bd, ak = self.levels("bid", k), self.levels("ask", k)
        if not bd or not ak:
            return math.nan
        B, A = sum(p * s for p, s in bd), sum(p * s for p, s in ak)
        return (B - A) / (B + A) if B + A > 0 else math.nan

    def imbalance_band(self, bp: float) -> float:
        B, A = self.usd_within("bid", bp), self.usd_within("ask", bp)
        return (B - A) / (B + A) if B + A > 0 else math.nan

    def microprice_offset_bp(self) -> float:
        """Level-1 microprice (each side's price weighted by the OTHER side's size) minus the mid, in bp."""
        bd, ak = self.levels("bid", 1), self.levels("ask", 1)
        if not bd or not ak:
            return math.nan
        (pb, qb), (pa, qa) = bd[0], ak[0]
        mid = (pb + pa) / 2
        return ((pb * qa + pa * qb) / (qa + qb) - mid) / mid * 1e4

"""Turn a raw recording into one row per decision instant, under a strict timestamp rule (Module 5).

THE RULE (docs/27 Lessons 3.5 and 4.2): a row for decision instant T uses ONLY what was stamped STRICTLY BEFORE  cut = T - lag_ms  by the exchange (server `ts`).
    book     = every `books` message with ts < cut applied, in order (a message stamped exactly `cut` is NOT in the row)
    flow     = taker dollars of trades with  cut - w < ts < cut  (a trade stamped exactly `cut` is NOT in the row)
`lag_ms` is the delay between an event happening and your program being able to act on it. 0 is the researcher's ideal; the measured receive delay on this PC was
about 146 ms (docs/27 Module 5), and the registry's fill model adds 500 ms of order latency - use lag_ms >= 150 for anything that claims to be tradable.

A row exists only when the book is READY (a snapshot was applied and the pseq chain unbroken). `book_age_ms` = cut - the stamp of the last applied message: a large age
means the pair was quiet (or the feed was stale); filter on it before trusting a row.

Columns: t (decision instant, ms), bid, ask, mid, spread_bp, imb1 and imb5 (dollars over 1 / 5 levels), imb_band{b} and bid_usd_{b} / ask_usd_{b} (dollars within b bp of the
mid; NaN where the recorded depth does not reach b bp), micro_bp, flow_{w}s (taker-flow share over the last w seconds, NaN when nothing traded), book_age_ms.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import orjson
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orderflow.book import Book  # noqa: E402
from orderflow.store import iter_raw  # noqa: E402

BANDS = (2, 5, 10, 25)
FLOW_S = (1, 5, 30, 60, 300)


def _parse(frames):
    """Split frames into book messages (in file order) and a de-duplicated, time-sorted trade table."""
    books, trades = [], {}
    for _, raw in frames:
        try:
            m = orjson.loads(raw)
            ch = m["arg"]["channel"]
        except Exception:
            continue
        if ch == "books":
            books.append((m["action"], m["data"][0]))
        elif ch == "trade":
            for t in m["data"]:
                trades[t["tradeId"]] = (int(t["ts"]), float(t["price"]), float(t["size"]), t["side"])
    rows = sorted(trades.values(), key=lambda x: x[0])
    ts = np.array([r[0] for r in rows], dtype="int64")
    usd = np.array([r[1] * r[2] for r in rows], dtype=float)
    sgn = np.array([1.0 if r[3] == "buy" else -1.0 for r in rows], dtype=float)
    return books, ts, np.r_[0.0, np.cumsum(usd * sgn)], np.r_[0.0, np.cumsum(usd)]


def grid_from_frames(frames, step_ms: int = 1000, lag_ms: int = 0, start_ms: int = None, end_ms: int = None) -> pd.DataFrame:
    books, tts, csign, cabs = _parse(frames)
    book = Book()
    out = []
    next_t = None

    def emit(T):
        cut = T - lag_ms
        b = book.best()
        if b is None:
            return
        row = dict(t=T, bid=b[0], ask=b[1], mid=book.mid(), spread_bp=book.spread_bp(), imb1=book.imbalance_levels(1), imb5=book.imbalance_levels(5),
                   micro_bp=book.microprice_offset_bp(), book_age_ms=cut - book.ts)
        for bp in BANDS:
            B, A = book.usd_within("bid", bp), book.usd_within("ask", bp)
            row[f"bid_usd_{bp}"], row[f"ask_usd_{bp}"] = B, A
            row[f"imb_band{bp}"] = (B - A) / (B + A) if (B + A) > 0 else math.nan
        hi = int(np.searchsorted(tts, cut, side="left"))                       # trades stamped strictly before the cut
        for w in FLOW_S:
            lo = int(np.searchsorted(tts, cut - w * 1000, side="right"))        # and strictly after cut - w
            den = cabs[hi] - cabs[lo]
            row[f"flow_{w}s"] = (csign[hi] - csign[lo]) / den if den > 0 else math.nan
        out.append(row)

    for action, d in books:
        ts = int(d["ts"])
        if next_t is None:
            next_t = (ts // step_ms + 1) * step_ms                                 # the first decision instant after the first message
            if start_ms is not None:
                next_t = max(next_t, ((start_ms + step_ms - 1) // step_ms) * step_ms)
        while next_t - lag_ms <= ts:                                           # the book as it stands holds every message stamped before the cut
            if end_ms is not None and next_t > end_ms:
                return pd.DataFrame(out)
            emit(next_t)
            next_t += step_ms
        book.apply(action, d)
    return pd.DataFrame(out)


def day_coverage(df: pd.DataFrame, fresh_ms: int = 2000, step_ms: int = 1000) -> pd.Series:
    """Share of each UTC day's decision instants for which this pair has a usable row: a ready book no staler than `fresh_ms`. The registry (AMENDMENTS 2026-10-30)
    counts a day only if this is at least 0.9. Index: the UTC day (a pandas Timestamp at midnight)."""
    if df.empty:
        return pd.Series(dtype=float)
    day = pd.to_datetime(df["t"], unit="ms", utc=True).dt.floor("D")
    ok = (df["book_age_ms"] <= fresh_ms).astype(float)
    per_day = 86_400_000 // step_ms
    return ok.groupby(day).sum() / per_day


def grid(root: Path, pair: str, **kw) -> pd.DataFrame:
    return grid_from_frames(iter_raw(Path(root) / "raw", pair), **kw)

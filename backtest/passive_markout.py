"""PASSIVE MARKOUT - can a MAKER on a wide-spread pair earn the spread, and does the order book help avoid being picked off? (2026-11-02)

THE REBUTTAL BEING TESTED (the user, 2026-11-02, asking for the counters to "one-tick signals cannot beat the fee"): stop predicting; REST orders at the touch, earn the spread, pick pairs
whose spread is wide in basis points, and use the book (imbalance) to avoid the side that is about to be run over.

THE MEASUREMENT (standard microstructure, "markout"): every time a taker SELL prints at or below the best bid, a resting bid at the touch would (queue permitting) have been filled at the
bid. Its markout at horizon h is how far the mid is from that fill price h seconds later, in basis points of the mid: (mid_{t+h} - bid) / mid. The half-spread is earned at once; whatever the
mid does afterwards is ADVERSE SELECTION if negative (the people who hit a bid know something, or just push the price). A taker BUY at the ask fills a resting offer; its markout is
(ask - mid_{t+h}) / mid. This is an UPPER BOUND on a real maker (a real one is behind a queue and fills only a share of these prints, and the share it gets is not random).
NET BOUNDS PER FILL, entry by maker (fee 2bp):  upper = markout - 2bp (exit free at the mid);  lower = markout - 2bp - half-spread(t+h) - 6bp (exit by a taker order at the touch).
A round trip as a maker both ways is between the two.

DATA: the order-flow recorder's trial recordings of 2026-10-30 (strategy_analysis/data/orderflow_trial*; ten pairs, 10 + 6 + 2.5 + 4 + 15 + 5 minutes, 13:57-15:03 UTC, the busy US-open hours). The book at
time t is the last message stamped strictly before the print; the mid at t + h is the last message stamped at or before t + h (both within 2 s of fresh). Trades are de-duplicated by trade id across
recordings (some overlapped). EXPLORATORY: ~40 minutes of one afternoon; it can say "not obviously dead" or "dead", never "an edge".

REGISTERED BEFORE THE FIRST RUN (2026-11-02)
    M1  On the narrow and medium pairs (BTC, SOL, XRP, DOGE, SUI, LINK) the mean markout at 30 s is below the 2bp entry fee: no maker edge, and the lower bound is negative everywhere.
    M2  The widest-spread pairs (DOT, ADA, SHIB, WLD) have positive markouts at 30 s, smaller than their half-spread (adverse selection eats part of it); on DOT the upper-bound net
        (markout - 2bp) is positive in this window; the lower bound (taker exit) is negative on every pair.
    M3  When the book leans WITH the fill (a passive buy while imb1 > +0.5, a passive sell while imb1 < -0.5) the 30 s markout is at least 1bp better than when it leans against it,
        averaged over pairs - the book does help avoid being picked off - but not enough to make any lower bound positive.
    M4  The wide pairs have too few prints in 40 minutes (under 400) for a standard error below 3bp: whatever they show is a pointer, not a measurement.

RESULT (2026-11-02; logs/passive_markout.txt)
    FIRST RUN HAD A DEFINITION BUG, found before interpreting it: every print at or BELOW the touch was counted as a fill AT the touch. On BTC 76% of those were deeper levels of a sweep
    (a resting order at the top bid is not filled at its own price by a print three levels down), and sweeps are the most informed trades. Fixed: a fill = a print exactly at the touch,
    one per taker order per millisecond (12 tests, 8 of 8 mutations caught). Numbers below are the corrected ones; the first-run column is kept in the log.
    30 s markout vs the fill price (bp, includes the half-spread earned at once): BTC -0.91, SOL -1.47, XRP -1.19, DOGE -1.41, SUI -1.71, LINK -0.82, WLD -2.31, SHIB -0.57, ADA +0.29, DOT -0.83
    (standard errors 0.3-1.5, clustered by minute). EVERY pair's net bound is negative: maker entry + free exit at the mid (UPPER) -1.7 to -4.3bp; maker entry + taker exit (LOWER) -8.9 to -14.1bp.
    Imbalance leaning WITH the fill is better than leaning against it on 10 of 10 pairs (average +3.0bp, BTC +1.6 +- 0.6 on 1,399 vs 3,425 fills; DOT +13.3 on 13 fills is a pointer, not a measurement),
    and it still leaves BTC at +0.1 against a 2bp fee. Caveat that favours the sceptic: a touch that leans your way has a LONG QUEUE in front of you, and this upper bound ignores queues.
    Scored: M1 right; M2 WRONG (negative on 3 of the 4 wide pairs, DOT's upper-bound net is -2.8, only ADA's markout is positive and it is +0.3 +- 0.6); M3 right (both halves);
    M4 wrong on the numbers (170-1,145 fills, standard errors 0.6-1.5bp), right in spirit for the WITH cells (13-132 fills).
    Exploratory: ~40 minutes of one afternoon (13:57-15:03 UTC, busy), ten pairs. It can say "nothing here", never "an edge".

    python -m backtest.passive_markout        writes logs/passive_markout.txt        tests: python tests/test_passive_markout.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import orjson

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orderflow.book import Book  # noqa: E402
from orderflow.store import iter_raw  # noqa: E402

LOG = ROOT / "logs" / "passive_markout.txt"
DATA = ROOT / "strategy_analysis" / "data"
SESSIONS = ["orderflow_trial", "orderflow_trial2", "orderflow_trial3", "orderflow_trial4", "orderflow_trial5", "orderflow_trial_straddle"]
PAIRS = ["BTCUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "SUIUSDT", "LINKUSDT", "WLDUSDT", "SHIBUSDT", "ADAUSDT", "DOTUSDT"]
HORIZONS_S = (1, 5, 30, 60)
MAKER_BP, TAKER_BP = 2.0, 6.0                       # Bitget standard, per side
FRESH_MS = 2000
BLOCK_MS = 60_000


def block_mean_se(x: np.ndarray, block: np.ndarray):
    """Mean of x and its standard error with observations clustered into blocks (trades in one minute are one market): sqrt(sum_b (S_b - m N_b)^2) / N."""
    x = np.asarray(x, float)
    ok = np.isfinite(x)
    x, block = x[ok], np.asarray(block)[ok]
    n = len(x)
    if n < 2:
        return float("nan"), float("nan"), n
    m = x.mean()
    codes = np.unique(block, return_inverse=True)[1]
    s = np.bincount(codes, weights=x)
    c = np.bincount(codes)
    g = len(s)
    se = np.sqrt(g / max(g - 1, 1) * np.sum((s - m * c) ** 2)) / n
    return float(m), float(se), n


def session_states(folder: Path, pair: str):
    """(ts, bid, ask, imb1) for every applied book message of one recording, and its de-duplicated trades (ts, price, size, side, id)."""
    book = Book()
    ts, bid, ask, imb = [], [], [], []
    trades = {}
    for _, raw in iter_raw(folder / "raw", pair):
        try:
            m = orjson.loads(raw)
            ch = m["arg"]["channel"]
        except Exception:
            continue
        if ch == "books":
            res = book.apply(m["action"], m["data"][0])
            if res in ("ok", "snapshot", "checkpoint") and book.ready:
                b = book.best()
                if b is None:
                    continue
                B1, A1 = b[0] * book.bids[b[0]], b[1] * book.asks[b[1]]
                ts.append(book.ts)
                bid.append(b[0])
                ask.append(b[1])
                imb.append((B1 - A1) / (B1 + A1) if B1 + A1 > 0 else np.nan)
        elif ch == "trade":
            for t in m["data"]:
                trades[t["tradeId"]] = (int(t["ts"]), float(t["price"]), float(t["size"]), t["side"])
    return np.array(ts, "int64"), np.array(bid), np.array(ask), np.array(imb), trades


def markouts(ts, bid, ask, imb, trades: dict, seen: set, touch_only: bool = True):
    """One row per fill that a resting touch order would have had (side +1 = our resting BID filled by a taker sell; -1 = our resting ASK filled by a taker buy).

    touch_only=True (the definition after the 2026-11-02 correction): the print must be EXACTLY at the touch, and a taker order that prints several times in the same millisecond counts
    once. touch_only=False is the first run's definition: every print at or BELOW the touch counted as a fill AT the touch - on BTC 76% of those were deeper levels of a sweep, which
    a resting top-of-book order does not fill at its own price, and the sweeps are the most informed trades, so that version is biased against the maker."""
    rows = []
    mid = (bid + ask) / 2
    counted = set()
    for tid, (t, price, size, side) in sorted(trades.items(), key=lambda kv: kv[1][0]):
        if tid in seen:
            continue
        i = int(np.searchsorted(ts, t, side="left")) - 1                          # last state stamped strictly before the print
        if i < 0 or t - ts[i] > FRESH_MS:
            continue
        if side == "sell" and (price == bid[i] if touch_only else price <= bid[i]):
            direction, fill = 1, bid[i]
        elif side == "buy" and (price == ask[i] if touch_only else price >= ask[i]):
            direction, fill = -1, ask[i]
        else:
            continue
        if touch_only:
            if (t, side) in counted:
                continue
            counted.add((t, side))
        row = dict(t=t, side=direction, spread_bp=(ask[i] - bid[i]) / mid[i] * 1e4, imb=imb[i], tid=tid)
        for h in HORIZONS_S:
            j = int(np.searchsorted(ts, t + h * 1000, side="right")) - 1
            if j <= i or ts[j] < t + h * 1000 - FRESH_MS or t + h * 1000 > ts[-1]:
                row[f"m{h}"] = np.nan
                row[f"hs{h}"] = np.nan
                continue
            row[f"m{h}"] = direction * (mid[j] - fill) / mid[i] * 1e4
            row[f"hs{h}"] = (ask[j] - bid[j]) / 2 / mid[i] * 1e4
        rows.append(row)
    return rows


def collect(pair: str, touch_only: bool = True):
    seen, out = set(), []
    for s in SESSIONS:
        folder = DATA / s
        if not (folder / "raw" / pair).exists():
            continue
        ts, bid, ask, imb, trades = session_states(folder, pair)
        if len(ts) < 10:
            continue
        rows = markouts(ts, bid, ask, imb, trades, seen, touch_only)
        seen.update(r["tid"] for r in rows)
        seen.update(trades)                                                        # every print of this recording is now spoken for (overlapping recordings)
        out += rows
    return out


def main():
    L = [f"backtest/passive_markout.py, run {__import__('datetime').datetime.now():%Y-%m-%d %H:%M}; ten pairs, the 2026-10-30 trial recordings, queue-free upper bound, maker fee {MAKER_BP:g}bp, taker {TAKER_BP:g}bp per side",
         "FILLS = a print exactly at the touch, one per taker order per millisecond (the first run counted every print at or below the touch: last column shows what that did)",
         "", f"  {'pair':9s} {'spread bp':>9s} {'fills':>7s} | {'markout 1 s':>13s} {'5 s':>13s} {'30 s':>13s} {'60 s':>13s} | {'half-spread':>11s} | {'net UPPER 30 s':>14s} {'net LOWER 30 s':>14s} | {'first-run def. 30 s':>19s}"]
    allrows = {}
    for p in PAIRS:
        rows = collect(p)
        allrows[p] = rows
        if not rows:
            continue
        g = lambda k: np.array([r[k] for r in rows], float)
        blk = (g("t") // BLOCK_MS).astype("int64")
        sp = np.median(g("spread_bp"))
        cells = {h: block_mean_se(g(f"m{h}"), blk) for h in (1, 5, 30, 60)}
        hs30 = np.nanmean(g("hs30"))
        m30 = cells[30][0]
        up = m30 - MAKER_BP
        lo = m30 - MAKER_BP - hs30 - TAKER_BP
        old = collect(p, touch_only=False)
        og = np.array([r["m30"] for r in old], float)
        ob = (np.array([r["t"] for r in old], float) // BLOCK_MS).astype("int64")
        om = block_mean_se(og, ob)[0]
        L.append(f"  {p:9s} {sp:9.2f} {len(rows):7d} | " + " ".join(f"{cells[h][0]:+7.2f}+-{cells[h][1]:4.2f}" for h in (1, 5, 30, 60)) + f" | {sp / 2:11.2f} | {up:+14.2f} {lo:+14.2f} | {om:+10.2f} ({len(old)})")
    L.append("")
    L.append("DOES THE BOOK HELP AVOID BEING PICKED OFF? 30 s markout when imb1 leans WITH the fill (bid-heavy for our bid, ask-heavy for our offer) vs AGAINST it (|imb1| > 0.5 on the touch):")
    L.append(f"  {'pair':9s} {'WITH: n':>8s} {'markout':>13s} | {'AGAINST: n':>10s} {'markout':>13s} | {'difference':>10s}")
    diffs = []
    for p in PAIRS:
        rows = allrows[p]
        if not rows:
            continue
        g = lambda k: np.array([r[k] for r in rows], float)
        lean = g("side") * g("imb")                                                # + when the touch leans our way
        m30, blk = g("m30"), (g("t") // BLOCK_MS).astype("int64")
        w, a = lean > 0.5, lean < -0.5
        mw, sw, nw = block_mean_se(m30[w], blk[w])
        ma, sa, na = block_mean_se(m30[a], blk[a])
        d = mw - ma
        if nw > 5 and na > 5:
            diffs.append(d)
        L.append(f"  {p:9s} {nw:8d} {mw:+7.2f}+-{sw:4.2f} | {na:10d} {ma:+7.2f}+-{sa:4.2f} | {d:+10.2f}")
    L.append(f"  average difference over the pairs with both cells filled: {np.mean(diffs):+.2f}bp ({len(diffs)} pairs)")
    # one worked example for the lesson: the first DOT print that would have filled a resting bid
    ex = next((r for r in allrows["DOTUSDT"] if r["side"] == 1 and np.isfinite(r["m30"])), None)
    if ex:
        L.append("")
        L.append(f"  worked example (DOT): a taker SELL at {ex['t']} ms met a resting bid; spread then {ex['spread_bp']:.1f}bp, imb1 {ex['imb']:+.2f}; markout 5 s {ex['m5']:+.2f}bp, 30 s {ex['m30']:+.2f}bp, 60 s {ex['m60']:+.2f}bp")
    txt = "\n".join(L)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

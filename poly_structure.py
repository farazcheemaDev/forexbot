"""POLYMARKET STRUCTURE SCAN - READ-ONLY. Is there a structural (not directional) edge a $221 account can take?

WHY THIS, AND WHY NOT MORE DIRECTIONAL BETS
    Every directional Polymarket test here is dead (docs/08, backtest/poly_weather.py, poly_rescore.py). What was never
    measured is STRUCTURE: prices that must obey an identity whatever happens. Two kinds:

    1. SUM GAPS in NEGATIVE-RISK events (at most one outcome can win; docs.polymarket.com/concepts/negative-risk).
       NO basket  - buy NO on every named outcome, k legs. At most one outcome wins, so the basket pays AT LEAST k-1,
                    and converting all k No shares is atomic (docs): (k-1) USDC back at once. Profit per set =
                    (k-1) - sum(NO asks) - fees = (sum of YES bids) - 1 - fees. Valid on every neg-risk event, augmented
                    or not: a winner that is not named only makes the basket pay k.
       YES basket - buy YES on every outcome. Pays exactly 1 only if the outcome set is COMPLETE, which holds for
                    standard (non-augmented) neg-risk events only; held to resolution, so capital is locked until then.
                    Augmented events (placeholders, "Other") are NOT scanned on this side.
    2. LIQUIDITY REWARDS (docs.polymarket.com/market-makers/liquidity-rewards): resting orders within a max spread of the
       midpoint share a daily pool, scored ((v-s)/v)^2 * size, two-sided boosted (one side /3 for mid in 0.10-0.90).
       This script prices the reward only; fills (adverse selection) cannot be seen read-only.

FEES (docs.polymarket.com/trading/fees, read 2026-10-26): taker fee = shares * rate * p * (1-p); makers pay none. The rate
    comes from each market's own feeSchedule. Every leg of a basket is a TAKER leg, so every leg is charged.

WHAT IT DOES NOT SEE (stated, not hidden)
    * Whether the order would still be there when it arrives (latency); `--watch` measures how long gaps live.
    * Gas / relayer cost of the conversion, USDC route costs, UMA dispute risk, a voided or 50-50 event (a cancelled
      match pays 0.5 per leg, below the k-1 bound).
    * Adverse selection on reward quotes. The 1-day price path gives a rough touch cost for the best few markets only.
    * Sport events' in-play repricing: a sum gap there can be a stale book, not money.

REGISTERED PREDICTIONS (2026-10-26, BEFORE the first run)
    P1  Net of fees and with depth walked, at most 3 of ~1,200 neg-risk events show an EXECUTABLE (every leg at least the
        venue minimum) positive basket at any one census, and the best one earns under 1.5% on its capital.
    P2  In `--watch`, most positive episodes die inside 2 minutes (median under 60 s); gaps that persist are the
        augmented/placeholder artifacts, not money.
    P3  Rewards: among markets whose minimum order fits $221, the median upper-bound yield is under 0.3% a day; the best
        are over 1% a day only where a pool is large against thin books, and the 1-day touch cost removes most of it.
    P4  Verdict: NO EDGE a $221 account can bank. Reward-making may stay a forward-paper CANDIDATE, not a book.

VERDICT RULES (fixed now)
    ARB EDGE  = in `--watch` at least 5 distinct episodes with net return >= 0.5% on capital >= $50 and median duration
                >= 60 s (a human-speed bot with 2 s latency could take them).
                AMENDED 2026-10-26, after the first census and BEFORE any watch: that return is for the NO basket, which
                converts back to cash at once. The YES basket is paid only at resolution, so it must clear 15% a YEAR
                (return x 365 / days to the event's end). The census's three executable YES gaps (0.5-2.3% over 157-432
                days = 0.7-1.9% a year) are the time value of money on a complete set, not a gap; the amendment stops
                them counting.
    REWARD CANDIDATE = at least 3 markets with min size fitting $221 whose upper-bound yield is >= 0.5%/day AND whose
                1-day touch cost leaves >= half of it. Even then only a CANDIDATE: fills are unmeasured.
    Anything else is reported dead. No orders, no keys, standard library only.

    python poly_structure.py --census                 one pass over every neg-risk event
    python poly_structure.py --watch 30 --every 20    census, then re-price the near-misses every 20 s for 30 min
    python poly_structure.py --rewards                reward markets that fit the capital
    python poly_structure.py --report                 read the logs written above
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
UA = "Mozilla/5.0"
CAPITAL = 221.0
BATCH = 500                    # /books takes at most 500 tokens
NEAR = 0.03                    # an event is "near" a gap if its top-of-book gross gap is within this of zero
MIN_PROFIT = 0.10              # a basket must earn at least this many dollars to count as a positive sample
OUT = Path(__file__).resolve().parent / "strategy_analysis" / "data" / "poly_structure"
CENSUS_COLS = ["ts", "event_id", "title", "kind", "legs", "exhaustive", "gross_top", "net_top", "shares",
               "capital", "profit", "roi", "ann_roi", "executable", "need", "profit_cap", "days_to_end"]
MIN_ANN_YES = 0.15             # a YES basket is paid at resolution: it must clear this a YEAR to count
MIN_ROI_NO = 0.005             # a NO basket converts back to cash at once: 0.5% on the capital


def asc(s) -> str:
    return str(s).encode("ascii", "replace").decode()


def num(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------------------------------- network ----
def get(url: str, data=None, tries: int = 4, timeout: int = 40):
    """GET, or POST when `data` (a JSON-able object) is given. Retries 429 / 5xx / network errors with backoff.
    A 4xx other than 429 is the caller's to handle (422 = gamma's offset limit), so it is raised at once."""
    body = None if data is None else json.dumps(data).encode()
    last = None
    for k in range(tries):
        try:
            rq = urllib.request.Request(url, data=body, headers={"User-Agent": UA, "Accept": "application/json",
                                                                 "Content-Type": "application/json"})
            return json.load(urllib.request.urlopen(rq, timeout=timeout))
        except urllib.error.HTTPError as e:
            last = e
            if e.code != 429 and e.code < 500:
                raise
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            last = e
        time.sleep(1.5 * (k + 1))
    raise RuntimeError(f"{url[:90]}: {last}")


def list_events(pause: float = 0.15) -> list:
    """Every active event, newest page by 24h volume. Gamma refuses offsets past ~3,000 with a 422: stop there."""
    out, off = [], 0
    while off < 3000:
        try:
            page = get(f"{GAMMA}/events?active=true&closed=false&limit=100&offset={off}"
                       f"&order=volume24hr&ascending=false")
        except urllib.error.HTTPError:
            break
        if not isinstance(page, list) or not page:
            break
        out += page
        off += 100
        time.sleep(pause)
    return out


def fetch_books(tokens: list, pause: float = 0.15) -> dict:
    """{token: book}. Tokens with no order book are simply absent from the reply - absent means no liquidity."""
    books = {}
    toks = list(dict.fromkeys(tokens))
    for i in range(0, len(toks), BATCH):
        rep = get(f"{CLOB}/books", data=[{"token_id": t} for t in toks[i:i + BATCH]])
        for b in rep if isinstance(rep, list) else []:
            books[str(b.get("asset_id"))] = b
        time.sleep(pause)
    return books


# ---------------------------------------------------------------------------------------------------- parsing ----
def parse_event(e: dict) -> dict:
    """The few fields the scan reads, per market. `live` = can be traded now; `yn` = a plain Yes/No market."""
    ms = []
    for m in e.get("markets") or []:
        toks, outs = m.get("clobTokenIds"), m.get("outcomes")
        try:
            toks = json.loads(toks) if isinstance(toks, str) else toks
            outs = json.loads(outs) if isinstance(outs, str) else outs
        except ValueError:
            continue
        if not toks or len(toks) != 2:
            continue
        sched = m.get("feeSchedule") or {}
        rate = (num(sched.get("rate"), 0.05) if sched else 0.05) if m.get("feesEnabled") else 0.0
        ms.append(dict(
            cid=m.get("conditionId"), q=m.get("question") or "", yes=str(toks[0]), no=str(toks[1]),
            yn=list(outs or []) == ["Yes", "No"],
            live=bool(m.get("active")) and not m.get("closed") and bool(m.get("enableOrderBook"))
            and m.get("acceptingOrders") is not False,
            other=bool(m.get("negRiskOther")), rate=rate, exp=num(sched.get("exponent"), 1.0),
            min_size=num(m.get("orderMinSize"), 5.0), bid=num(m.get("bestBid")), ask=num(m.get("bestAsk")),
            spread=num(m.get("spread")), vol24=num(m.get("volume24hr"), 0.0)))
    return dict(id=str(e.get("id")), title=e.get("title") or "", neg=bool(e.get("negRisk")),
                aug=bool(e.get("negRiskAugmented")), end=e.get("endDate"), markets=ms)


def days_to_end(ev: dict, now: datetime) -> float:
    try:
        end = datetime.fromisoformat(str(ev.get("end")).replace("Z", "+00:00"))
    except ValueError:
        return float("nan")
    return (end - now).total_seconds() / 86400


# ----------------------------------------------------------------------------------------------------- books ----
def levels(book, side: str) -> list:
    """[(price, size)] best first: asks ascending, bids descending. Zero/negative sizes and bad prices dropped."""
    rows = []
    for r in (book or {}).get(side) or []:
        p, s = num(r.get("price")), num(r.get("size"))
        if p is not None and s is not None and 0 < p <= 1 and s > 0:
            rows.append((p, s))
    return sorted(rows, reverse=(side == "bids"))


def fee_per_share(price: float, rate: float, exp: float = 1.0) -> float:
    """docs.polymarket.com/trading/fees: fee = shares * rate * p * (1 - p). Taker only."""
    return rate * (price * (1.0 - price)) ** exp


def best_set(legs: list, payout: float, budget: float | None = None) -> dict:
    """Walk every leg's asks together and buy equal shares of each while one more set still earns money net of fees.

    legs: [{"asks": [(price, size)...] ascending, "rate": taker fee rate, "exp": exponent}]
    payout: what one complete set returns (k-1 for a NO basket, 1 for a YES basket).
    Returns shares bought, price paid, fees, capital (= price + fees), profit, and the TOP-OF-BOOK margin per share
    before (gross) and after (net) fees. budget caps the capital spent. A leg with no asks makes the basket impossible.
    """
    out = dict(shares=0.0, cost=0.0, fees=0.0, capital=0.0, profit=0.0, gross_top=None, net_top=None)
    if not legs or any(not l["asks"] for l in legs):
        return out
    out["gross_top"] = payout - sum(l["asks"][0][0] for l in legs)
    out["net_top"] = payout - sum(l["asks"][0][0] + fee_per_share(l["asks"][0][0], l["rate"], l["exp"]) for l in legs)
    idx = [0] * len(legs)
    rem = [l["asks"][0][1] for l in legs]
    while True:
        px = [l["asks"][idx[i]][0] for i, l in enumerate(legs)]
        fee = sum(fee_per_share(p, l["rate"], l["exp"]) for p, l in zip(px, legs))
        margin = payout - sum(px) - fee
        if margin <= 1e-12:
            break
        step = min(rem)
        if budget is not None:
            step = min(step, (budget - out["capital"]) / (sum(px) + fee))
        if step <= 1e-9:
            break
        out["shares"] += step
        out["cost"] += step * sum(px)
        out["fees"] += step * fee
        out["capital"] += step * (sum(px) + fee)
        out["profit"] += step * margin
        for i in range(len(legs)):
            rem[i] -= step
            if rem[i] <= 1e-9:
                idx[i] += 1
                if idx[i] >= len(legs[i]["asks"]):
                    return out
                rem[i] = legs[i]["asks"][idx[i]][1]
    return out


def event_baskets(ev: dict, books: dict, now: datetime, budget: float = CAPITAL) -> list:
    """One row per basket kind that can be priced for this neg-risk event."""
    rows = []
    ms = [m for m in ev["markets"] if m["live"] and m["yn"] and not m["other"]]
    for kind in ("no", "yes"):
        if kind == "yes":
            # complete set only: a standard (non-augmented) event whose every market is tradable
            if ev["aug"] or len(ev["markets"]) < 2 or not all(m["live"] and m["yn"] for m in ev["markets"]):
                continue
            use, payout = ev["markets"], 1.0
        else:
            if len(ms) < 2:
                continue
            use, payout = ms, float(len(ms) - 1)
        legs, need = [], 0.0
        for m in use:
            b = books.get(m[kind])
            legs.append(dict(asks=levels(b, "asks"), rate=m["rate"], exp=m["exp"]))
            need = max(need, num((b or {}).get("min_order_size"), m["min_size"]))
        full, cap = best_set(legs, payout), best_set(legs, payout, budget)
        if full["gross_top"] is None:
            continue
        roi = full["profit"] / full["capital"] if full["capital"] else 0.0
        days = days_to_end(ev, now)
        rows.append(dict(
            ts=int(now.timestamp()), event_id=ev["id"], title=asc(ev["title"])[:70], kind=kind + "_basket",
            legs=len(use), exhaustive=int(not ev["aug"]), gross_top=round(full["gross_top"], 5),
            net_top=round(full["net_top"], 5), shares=round(full["shares"], 2), capital=round(full["capital"], 2),
            profit=round(full["profit"], 4), roi=round(roi, 5), ann_roi=ann_return(kind, roi, days),
            executable=int(full["shares"] >= need > 0), need=need, profit_cap=round(cap["profit"], 4),
            days_to_end=round(days, 1)))
    return rows


def ann_return(kind: str, roi: float, days: float):
    """Yearly return of a YES basket (held to the event's end); None for a NO basket, which is cash again at once."""
    if kind != "yes" or not days == days:
        return None
    return round(roi * 365.0 / max(days, 1.0), 5)


def worth_taking(kind: str, peak_roi: float, peak_ann, peak_capital: float) -> bool:
    """The amended verdict rule: NO basket 0.5% on >= $50; YES basket 15% a year on >= $50."""
    if peak_capital < 50:
        return False
    return (peak_ann or 0.0) >= MIN_ANN_YES if kind == "yes_basket" else peak_roi >= MIN_ROI_NO


def positive(r: dict) -> bool:
    return bool(r["executable"]) and r["profit"] >= MIN_PROFIT


def census(events: list, now: datetime, only: set | None = None) -> tuple:
    """-> (rows, books, mirror) for the given parsed events (or just ids in `only`)."""
    evs = [e for e in events if e["neg"] and (only is None or e["id"] in only)]
    toks = [m[k] for e in evs for m in e["markets"] if m["live"] and m["yn"] for k in ("yes", "no")]
    books = fetch_books(toks)
    rows = [r for e in evs for r in event_baskets(e, books, now)]
    return rows, books, mirror_gaps(evs, books)


def mirror_gaps(evs: list, books: dict) -> list:
    """|best NO ask - (1 - best YES bid)| per market: ~0 if the NO book is just the YES book mirrored."""
    out = []
    for e in evs:
        for m in e["markets"]:
            yb, na = levels(books.get(m["yes"]), "bids"), levels(books.get(m["no"]), "asks")
            if yb and na:
                out.append(abs(na[0][0] - (1.0 - yb[0][0])))
    return out


# -------------------------------------------------------------------------------------------------- episodes ----
class Episodes:
    """Runs of consecutive samples in which a basket was positive. Duration is last-seen minus first-seen, so a
    one-sample episode has duration 0 and is only known to be shorter than the sampling interval."""

    def __init__(self):
        self.open, self.done = {}, []

    def update(self, ts: float, key: tuple, row: dict | None):
        if row is not None and positive(row):
            e = self.open.setdefault(key, dict(key=key, start=ts, last=ts, n=0, peak_profit=0.0, peak_roi=0.0,
                                               peak_ann=0.0, peak_capital=0.0, title=row["title"]))
            e["last"], e["n"] = ts, e["n"] + 1
            e["peak_profit"] = max(e["peak_profit"], row["profit"])
            e["peak_roi"] = max(e["peak_roi"], row["roi"])
            e["peak_ann"] = max(e["peak_ann"], row.get("ann_roi") or 0.0)
            e["peak_capital"] = max(e["peak_capital"], row["capital"])
        elif key in self.open:
            self.done.append(dict(self.open.pop(key), censored=0))

    def close_all(self):
        for k in list(self.open):
            self.done.append(dict(self.open.pop(k), censored=1))


def duration(e: dict) -> float:
    return e["last"] - e["start"]


# ---------------------------------------------------------------------------------------------------- rewards ----
def score(v: float, s: float) -> float:
    """Order score ((v-s)/v)^2 for spread s inside max spread v; 0 outside."""
    return ((v - s) / v) ** 2 if 0 <= s < v else 0.0


def side_scores(yes_book, no_book, mid: float, v: float, min_size: float) -> tuple:
    """(Q_one, Q_two) of everything resting in the market, v and spreads in PRICE units (cents / 100).
    Q_one = YES bids + NO asks; Q_two = YES asks + NO bids. A NO order at p is a YES order at 1-p."""
    q1 = q2 = 0.0
    for p, s in levels(yes_book, "bids"):
        if s >= min_size:
            q1 += score(v, mid - p) * s
    for p, s in levels(no_book, "asks"):
        if s >= min_size:
            q1 += score(v, mid - (1.0 - p)) * s
    for p, s in levels(yes_book, "asks"):
        if s >= min_size:
            q2 += score(v, p - mid) * s
    for p, s in levels(no_book, "bids"):
        if s >= min_size:
            q2 += score(v, (1.0 - p) - mid) * s
    return q1, q2


def q_min(q1: float, q2: float, mid: float, c: float = 3.0) -> float:
    """docs: mid in [0.10, 0.90] lets one side score at 1/c; outside, only two-sided liquidity scores."""
    if 0.10 <= mid <= 0.90:
        return max(min(q1, q2), max(q1, q2) / c)
    return min(q1, q2)


def adjusted_mid(book_yes, min_size: float):
    """Midpoint of the best bid and ask among orders at least min_size, else None."""
    b = [p for p, s in levels(book_yes, "bids") if s >= min_size]
    a = [p for p, s in levels(book_yes, "asks") if s >= min_size]
    return (b[0] + a[0]) / 2.0 if b and a else None


def reward_estimate(yes_book, no_book, rate: float, v_cents: float, min_size: float, offset_frac: float,
                    size: float | None = None) -> dict | None:
    """Upper-bound reward for a two-sided quote on the YES token at `offset_frac` of the max spread, size `size`
    (default the minimum), against what rests there now. BEFORE adverse selection: nothing here is a fill."""
    mid = adjusted_mid(yes_book, min_size)
    if mid is None or rate <= 0 or v_cents <= 0:
        return None
    v = v_cents / 100.0
    s = offset_frac * v
    size = float(size or min_size)
    q1, q2 = side_scores(yes_book, no_book, mid, v, min_size)
    other = q_min(q1, q2, mid)
    ours = score(v, s) * size                      # a bid and an ask of `size` each: Q_one = Q_two = ours
    share = ours / (ours + other) if ours + other > 0 else 0.0
    capital = size * ((mid - s) + (1.0 - (mid + s)))   # bid collateral + the ask as a NO bid's collateral
    return dict(mid=mid, s=s, size=size, share=share, per_day=rate * share, capital=capital,
                yield_day=rate * share / capital if capital > 0 else 0.0, others=other)


def touch_cost(points: list, s: float, size: float) -> tuple:
    """Re-quote at each print +/- s; a next print through the quote fills it at the quote and marks at that print.
    -> (fills, dollars lost). Ignores any bounce back and anything inside a minute: a rough lower bound on the cost."""
    fills = 0
    lost = 0.0
    for a, b in zip(points, points[1:]):
        if b <= a - s:
            fills, lost = fills + 1, lost + ((a - s) - b) * size
        elif b >= a + s:
            fills, lost = fills + 1, lost + (b - (a + s)) * size
    return fills, lost


# ------------------------------------------------------------------------------------------------ persistence ----
def write_rows(path: Path, rows: list, cols: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)


EPISODE_COLS = ["event_id", "kind", "title", "start", "last", "duration_s", "samples", "peak_profit", "peak_roi",
                "peak_ann", "peak_capital", "censored"]


def episode_rows(done: list) -> list:
    return [dict(event_id=e["key"][0], kind=e["key"][1], title=e["title"], start=int(e["start"]), last=int(e["last"]),
                 duration_s=int(duration(e)), samples=e["n"], peak_profit=round(e["peak_profit"], 4),
                 peak_roi=round(e["peak_roi"], 5), peak_ann=round(e["peak_ann"], 5),
                 peak_capital=round(e["peak_capital"], 2), censored=e["censored"])
            for e in done]


def load_events(max_age_min: float = 10.0) -> list:
    """Parsed events, from a cache younger than max_age_min, else a fresh ~1 minute pass over gamma."""
    cache = OUT / "events_cache.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < max_age_min * 60:
        return json.loads(cache.read_text(encoding="utf-8"))
    evs = [parse_event(e) for e in list_events()]
    OUT.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(evs), encoding="utf-8")
    return evs


def show_rows(rows: list, n: int = 10):
    print(f"  {'kind':<10}{'legs':>5}{'gross_top':>10}{'net_top':>9}{'shares':>9}{'capital':>9}{'profit':>9}"
          f"{'roi%':>7}{'%/yr':>7}{'exec':>5}  title")
    for r in rows[:n]:
        print(f"  {r['kind']:<10}{r['legs']:>5}{r['gross_top']:>10.4f}{r['net_top']:>9.4f}{r['shares']:>9.1f}"
              f"{r['capital']:>9.2f}{r['profit']:>9.2f}{100 * r['roi']:>7.2f}"
              f"{(100 * r['ann_roi'] if r.get('ann_roi') is not None else float('nan')):>7.1f}"
              f"{r['executable']:>5}  {r['title'][:42]}")


def run_census(args) -> tuple:
    now = now_utc()
    print(f"census {now:%Y-%m-%d %H:%M:%S} UTC - reading events...", flush=True)
    evs = load_events(args.cache_min)
    neg = [e for e in evs if e["neg"]]
    print(f"  events {len(evs)}, neg-risk {len(neg)} (augmented {sum(e['aug'] for e in neg)}), "
          f"markets in neg-risk {sum(len(e['markets']) for e in neg)}", flush=True)
    rows, books, mirror = census(evs, now)
    write_rows(OUT / "census.csv", rows, CENSUS_COLS)
    by_kind = {k: [r for r in rows if r["kind"] == k] for k in ("no_basket", "yes_basket")}
    print(f"  priced {len(rows)} baskets from {len(books)} books; mirror check |NO ask-(1-YES bid)| "
          f"median {statistics.median(mirror) if mirror else float('nan'):.4f}, max {max(mirror) if mirror else float('nan'):.4f}"
          f" over {len(mirror)} markets")
    for k, rs in by_kind.items():
        pos = [r for r in rs if r["net_top"] > 0]
        ex = [r for r in rs if positive(r)]
        print(f"\n{k}: {len(rs)} priced | top-of-book net>0: {len(pos)} | executable and >= ${MIN_PROFIT:.2f}: {len(ex)}"
              f" | total executable profit ${sum(r['profit'] for r in ex):.2f}, at the ${CAPITAL:.0f} cap "
              f"${sum(r['profit_cap'] for r in ex):.2f}")
        show_rows(sorted(rs, key=lambda r: -r["net_top"]), 8)
    return rows, evs


def run_watch(args):
    rows, evs = run_census(args)
    near = {r["event_id"] for r in rows if r["gross_top"] > -NEAR or r["net_top"] > -NEAR}
    print(f"\nwatching {len(near)} near-break-even events for {args.watch:g} min, every {args.every:g} s", flush=True)
    ep, t_end, ticks = Episodes(), time.time() + args.watch * 60, 0
    while time.time() < t_end and near:
        t0 = time.time()
        now = now_utc()
        try:
            snap, _, _ = census(evs, now, only=near)
        except RuntimeError as e:
            print("  tick failed:", e, flush=True)
            time.sleep(args.every)
            continue
        ticks += 1
        write_rows(OUT / "watch.csv", [r for r in snap if r["net_top"] > -NEAR], CENSUS_COLS)
        seen = {(r["event_id"], r["kind"]): r for r in snap}
        for key in set(seen) | set(ep.open):
            ep.update(t0, key, seen.get(key))
        npos = sum(positive(r) for r in snap)
        if ticks % 3 == 1 or npos:
            print(f"  {now:%H:%M:%S} tick {ticks}: positive now {npos}, open episodes {len(ep.open)}, "
                  f"closed {len(ep.done)}", flush=True)
        time.sleep(max(0.0, args.every - (time.time() - t0)))
    ep.close_all()
    write_rows(OUT / "episodes.csv", episode_rows(ep.done), EPISODE_COLS)
    summarise_episodes(ep.done, args.every)


def summarise_episodes(done: list, every: float):
    big = [e for e in done if worth_taking(e["key"][1], e["peak_roi"], e["peak_ann"], e["peak_capital"])]
    durs = sorted(duration(e) for e in done)
    print(f"\nepisodes: {len(done)} positive runs (sampling every {every:g} s; duration 0 = under one sample)")
    if durs:
        print(f"  duration median {statistics.median(durs):.0f} s, max {durs[-1]:.0f} s; "
              f"censored (still open at the end) {sum(e['censored'] for e in done)}")
    print(f"  worth taking (NO basket >= 0.5% / YES basket >= 15% a year, on capital >= $50): {len(big)}"
          + (f", median duration {statistics.median(duration(e) for e in big):.0f} s" if big else ""))
    for e in sorted(done, key=lambda e: -e["peak_profit"])[:8]:
        print(f"  {e['key'][1]:<10} dur {duration(e):>5.0f}s n={e['n']:>3} peak profit ${e['peak_profit']:>7.2f}"
              f" roi {100 * e['peak_roi']:>5.2f}% ({100 * e['peak_ann']:>5.1f}%/yr) cap ${e['peak_capital']:>7.2f}"
              f"  {e['title'][:34]}")


def fetch_reward_markets() -> list:
    out, cursor = [], ""
    while True:
        r = get(f"{CLOB}/rewards/markets/current" + (f"?next_cursor={cursor}" if cursor else ""))
        out += r.get("data") or []
        cursor = r.get("next_cursor")
        if not cursor or cursor == "LTE=" or not r.get("data"):
            break
        time.sleep(0.15)
    return out


def run_rewards(args):
    print("reward markets...", flush=True)
    rw = fetch_reward_markets()
    evs = load_events(args.cache_min)
    by_cid = {m["cid"]: (e, m) for e in evs for m in e["markets"]}
    elig = []
    for r in rw:
        rate = sum(c.get("rate_per_day") or 0 for c in r.get("rewards_config") or [])
        v, ms = r.get("rewards_max_spread") or 0, r.get("rewards_min_size") or 0
        hit = by_cid.get(r.get("condition_id"))
        if rate > 0 and v > 0 and ms > 0 and hit and hit[1]["live"] and hit[1]["yn"] and ms <= args.max_min_size:
            elig.append((rate, v, ms, hit[0], hit[1]))
    print(f"  {len(rw)} markets pay rewards; {len(elig)} are live, have a window, and a minimum order of "
          f"<= {args.max_min_size:g} shares", flush=True)
    books = fetch_books([m[k] for *_, m in elig for k in ("yes", "no")])
    res = []
    for rate, v, ms, e, m in elig:
        for tag, frac in (("tight", 0.25), ("wide", 0.6)):
            est = reward_estimate(books.get(m["yes"]), books.get(m["no"]), rate, v, ms, frac)
            if est and est["capital"] <= CAPITAL:
                res.append(dict(est, tag=tag, rate=rate, v=v, min_size=ms, event=asc(e["title"])[:34],
                                q=asc(m["q"])[:38], yes=m["yes"], spread=m["spread"]))
    res.sort(key=lambda r: -r["yield_day"])
    for tag in ("tight", "wide"):
        ys = sorted(r["yield_day"] for r in res if r["tag"] == tag)
        if ys:
            print(f"\n{tag} quotes ({'25' if tag == 'tight' else '60'}% of the max spread), minimum size, two-sided:"
                  f" {len(ys)} markets | yield per day: median {100 * statistics.median(ys):.3f}%, "
                  f"p90 {100 * ys[int(0.9 * (len(ys) - 1))]:.3f}%, max {100 * ys[-1]:.3f}% | "
                  f">=0.5%/day: {sum(y >= 0.005 for y in ys)} | >=1%/day: {sum(y >= 0.01 for y in ys)}")
    tight = [r for r in res if r["tag"] == "tight"]
    contested = [r for r in tight if r["share"] <= 0.5]
    print(f"\nuncontested today (our quote alone would take over half the pool): {len(tight) - len(contested)} of "
          f"{len(tight)} - day-one pools or empty books; their yield is not believable")
    cy = sorted(r["yield_day"] for r in contested)
    if cy:
        print(f"contested ({len(contested)}): yield per day median {100 * statistics.median(cy):.3f}%, "
              f"p90 {100 * cy[int(0.9 * (len(cy) - 1))]:.3f}%, >=0.5%/day {sum(y >= 0.005 for y in cy)}")

    def history_cost(r):
        try:
            pts = [p["p"] for p in get(f"{CLOB}/prices-history?market={r['yes']}&interval=1d&fidelity=1")["history"]]
        except (RuntimeError, urllib.error.HTTPError, KeyError):
            pts = []
        time.sleep(0.1)
        if len(pts) <= 30:
            return False
        fills, lost = touch_cost(pts, r["s"], r["size"])
        r.update(fills=fills, lost=lost, net_usd=r["per_day"] - lost, net=(r["per_day"] - lost) / r["capital"])
        return True

    top = contested[:args.touch_n]
    print(f"\ntop {len(top)} CONTESTED by upper-bound yield, with a rough 1-day touch cost (a print through the quote "
          f"fills it, no bounce back credited):")
    print(f"  {'$/day':>7}{'cap $':>8}{'yld%/d':>8}{'share':>7}{'fills':>6}{'lost $':>8}{'net%/d':>8}  market")
    for r in top:
        if history_cost(r):
            print(f"  {r['per_day']:>7.2f}{r['capital']:>8.1f}{100 * r['yield_day']:>8.3f}{r['share']:>7.2f}"
                  f"{r['fills']:>6}{r['lost']:>8.2f}{100 * r['net']:>8.3f}  {r['event']} | {r['q']}")
    rng = random.Random(7)
    sample = [r for r in rng.sample(contested, min(args.sample, len(contested))) if history_cost(r)]
    if sample:
        nets = sorted(r["net"] for r in sample)
        ratio = sorted(r["lost"] / r["per_day"] for r in sample if r["per_day"] > 0)
        slots = max(1, int(CAPITAL // statistics.median(r["capital"] for r in sample)))
        print(f"\nRANDOM sample of {len(sample)} contested markets (seed 7, not picked by yield): touch cost vs reward")
        print(f"  net per day on the quote's capital: median {100 * statistics.median(nets):.3f}%, mean "
              f"{100 * statistics.mean(nets):.3f}%, positive in {sum(n > 0 for n in nets)} of {len(nets)}; "
              f"lost/reward median {statistics.median(ratio):.2f}")
        print(f"  ${CAPITAL:.0f} fits ~{slots} such markets: mean net ${slots * statistics.mean(r['net_usd'] for r in sample):.2f}"
              f" a day (median market ${slots * statistics.median(r['net_usd'] for r in sample):.2f}); the touch cost is "
              f"a floor on adverse selection only if prices never bounce back")
    write_rows(OUT / "rewards.csv", [{k: v for k, v in r.items() if k != "yes"} for r in res],
               ["tag", "event", "q", "rate", "v", "min_size", "mid", "s", "size", "share", "per_day", "capital",
                "yield_day", "others", "spread", "fills", "lost", "net"])
    seen = [r for r in top if "net" in r]
    good = [r for r in seen if r["yield_day"] >= 0.005 and r["net"] >= r["yield_day"] / 2]
    print(f"\nREWARD CANDIDATE test as registered (>=3 markets with yield >= 0.5%/day and touch cost under half of it): "
          f"{len(good)} of the top {len(seen)} contested")


def run_report(args):
    ep = OUT / "episodes.csv"
    if ep.exists():
        rows = list(csv.DictReader(ep.open(encoding="utf-8")))
        done = [dict(key=(r["event_id"], r["kind"]), start=float(r["start"]), last=float(r["last"]), n=int(r["samples"]),
                     peak_profit=float(r["peak_profit"]), peak_roi=float(r["peak_roi"]),
                     peak_ann=float(r.get("peak_ann") or 0.0), peak_capital=float(r["peak_capital"]),
                     title=r["title"], censored=int(r["censored"]))
                for r in rows]
        summarise_episodes(done, float("nan"))
    else:
        print("no episodes.csv yet - run --watch")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--census", action="store_true")
    ap.add_argument("--watch", type=float, metavar="MINUTES")
    ap.add_argument("--every", type=float, default=20.0)
    ap.add_argument("--rewards", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--cache-min", type=float, default=10.0)
    ap.add_argument("--max-min-size", type=float, default=300.0)
    ap.add_argument("--touch-n", type=int, default=8)
    ap.add_argument("--sample", type=int, default=150)
    a = ap.parse_args()
    if a.watch:
        run_watch(a)
    elif a.census:
        run_census(a)
    elif a.rewards:
        run_rewards(a)
    elif a.report:
        run_report(a)
    else:
        ap.print_help()


if __name__ == "__main__":
    sys.exit(main())

"""IS POLYMARKET MISPRICED? — the longshot-bias test, done properly.

THE CLAIM BEING TESTED
    In betting markets, longshots are systematically OVERPRICED and favourites
    UNDERPRICED. It is one of the oldest documented anomalies in horse racing and it
    survives in most bookmaker markets. If it holds on Polymarket, the exploit is
    mechanical: buy high-probability contracts, hold to resolution, collect the gap.

WHY POLYMARKET IS WORTH THE TROUBLE AT ALL
    It has NO MINIMUM ORDER. That is the single constraint that killed every
    small-capital idea measured today: Bitget's $5 floor forces a $10 account to risk
    1.26% per trade whether it wants to or not, and that forced over-risk is why 70%
    of paths die. On Polymarket a $10 account can hold twenty genuine positions.

    And because a contract SETTLES ITSELF at $1 or $0, a hold-to-resolution strategy
    crosses the spread ONCE. Measured live on the tradeable markets, that is ~2-3.5%
    one way - expensive but survivable, where round-tripping at 5-7% would not be.

THE TEST
    For every resolved market: take the YES price N days BEFORE it closed, bucket by
    that price, and measure what fraction of each bucket actually resolved YES.

    Perfect calibration means resolution rate == price, in every bucket. The claim
    predicts a specific shape:
        low buckets  (longshots)  resolve LESS often than their price  -> overpriced
        high buckets (favourites) resolve MORE often than their price -> underpriced

    An edge only counts if the gap beats the ~2-3% it costs to get in.

THREE WAYS THIS TEST CAN LIE, AND WHAT IS DONE ABOUT EACH
    1. CLUSTERING. Twenty "will X win the nomination" markets are ONE event: one
       resolves YES and nineteen resolve NO by construction. Treating them as twenty
       independent observations would inflate significance enormously - the same error
       that made a pooled crypto p-value meaningless earlier today. Markets are
       therefore grouped by event and the EVENT COUNT is reported as the real sample
       size alongside the market count.
    2. SELECTION. Ordering by volume selects large, well-known markets, which are
       exactly the ones most likely to be efficiently priced. That biases AGAINST
       finding an edge, so it is the conservative direction - but it is stated rather
       than hidden.
    3. HORIZON. The bias is not the same 1 day out as 90 days out. Several horizons
       are reported rather than one convenient choice.

REGISTERED PREDICTION (2026-09-14, before running)
    Classic longshot bias shows up: the sub-10% buckets resolve YES less often than
    their price, by a few points. But favourites will be close to fair, because the
    high-probability end of a heavily traded market is where the money concentrates.
    Net: a real anomaly at the longshot end that is NOT exploitable, because the
    profitable side of it is SHORTING longshots, and a contract already priced at 3c
    has at most 3c of downside to capture against a 2-3% entry cost.

    If favourites resolve YES more than 3 points above their price, that IS
    exploitable and it is the first genuinely new edge found today.

    python -m backtest.polymarket_bias --markets 800
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

GAMMA = "https://gamma-api.polymarket.com/markets"
CLOB = "https://clob.polymarket.com/prices-history"
CACHE = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "poly"
CACHE.mkdir(parents=True, exist_ok=True)
BUCKETS = [(0.00, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 0.35),
           (0.35, 0.50), (0.50, 0.65), (0.65, 0.80), (0.80, 0.90),
           (0.90, 0.95), (0.95, 1.00)]


def get(u, tries=3, t=25):
    for a in range(tries):
        try:
            r = urllib.request.Request(u, headers={"User-Agent": "research/1.0"})
            return json.load(urllib.request.urlopen(r, timeout=t))
        except Exception:
            if a == tries - 1:
                return None
            time.sleep(1.5)
    return None


def fetch_markets(n, order="volumeNum"):
    """Resolved markets, paged. Cached to disk.

    ORDERING IS A SELECTION DECISION, not a convenience. Ordering by volumeNum picks
    the most-traded markets, and a longshot that CAME IN generates far more volume
    than one that fizzled - so a volume-ordered sample is biased toward underdogs
    winning. The first run of this file did exactly that and found longshots
    UNDERPRICED, the opposite of the documented anomaly, which is the signature of
    that bias rather than a discovery. Ordering by endDate instead samples on
    something unrelated to the outcome.
    """
    f = CACHE / f"resolved_{n}_{order}.json"
    if f.exists():
        return json.load(open(f, encoding="utf-8"))
    out, off = [], 0
    while len(out) < n:
        page = get(f"{GAMMA}?closed=true&limit=100&offset={off}"
                   f"&order={order}&ascending=false")
        if not page:
            break
        out += page
        off += 100
        if len(page) < 100:
            break
        print(f"    {len(out)} markets...", flush=True)
    out = out[:n]
    json.dump(out, open(f, "w", encoding="utf-8"))
    return out


def history(token):
    f = CACHE / f"h_{token[:24]}.json"
    if f.exists():
        try:
            return json.load(open(f, encoding="utf-8"))
        except Exception:
            pass
    h = get(f"{CLOB}?market={token}&interval=max&fidelity=1440")
    pts = (h or {}).get("history") or []
    json.dump(pts, open(f, "w", encoding="utf-8"))
    return pts


def parse(m):
    """(yes_outcome, yes_token, close_epoch, event_key) or None."""
    try:
        op = m.get("outcomePrices")
        if isinstance(op, str):
            op = json.loads(op)
        oc = m.get("outcomes")
        if isinstance(oc, str):
            oc = json.loads(oc)
        if not op or not oc or len(op) < 2:
            return None
        if str(oc[0]).strip().lower() != "yes":
            return None                      # only binary Yes/No markets
        y = float(op[0])
        if y not in (0.0, 1.0):
            return None                      # not cleanly resolved
        tk = m.get("clobTokenIds")
        if isinstance(tk, str):
            tk = json.loads(tk)
        if not tk:
            return None
        end = m.get("endDate") or m.get("closedTime")
        if not end:
            return None
        end = str(end).replace("Z", "+00:00").replace(" ", "T")
        import datetime as dt
        try:
            ce = dt.datetime.fromisoformat(end).timestamp()
        except ValueError:
            return None
        # EVENT KEY: markets in the same event resolve together by construction.
        ev = m.get("events") or []
        key = (ev[0].get("id") if ev and isinstance(ev[0], dict)
               else m.get("negRiskMarketID") or m.get("conditionId"))
        return y, tk[0], ce, str(key)
    except Exception:
        return None


def price_at(pts, close_epoch, days, min_span_days=None):
    """Price `days` before trading STOPPED, anchored on the last traded point.

    ANCHORED ON THE HISTORY, NOT ON endDate. The gamma `endDate` is a NOMINAL
    resolution date and is often nowhere near the last trade: on a date-ordered
    sample its median gap is +574 days, and 100% of those markets had endDate more
    than a week past their final trade. Using it made `endDate - 1 day` and
    `endDate - 7 days` both fall beyond the entire price history, so both returned the
    FINAL price - which is why the 1-day and 7-day tables came out byte-identical, and
    why the test appeared to show a 24% edge. It was measuring "markets trading at 73c
    when trading stopped mostly resolved YES", i.e. the market being right.

    The last traded timestamp is when the market actually stopped pricing, so it is
    the only sound anchor.

    min_span_days rejects a market whose history is too short to look back that far -
    otherwise a 3-day-old market silently contributes its first tick as a "30 days
    out" price. 21% of one sample had under 8 days of history.
    """
    ts = [p for p in pts if p.get("t") is not None and p.get("p") is not None]
    if len(ts) < 2:
        return None
    last_t = ts[-1]["t"]
    first_t = ts[0]["t"]
    need = (min_span_days if min_span_days is not None else days) * 86400
    if last_t - first_t < need:
        return None
    cutoff = last_t - days * 86400
    best = None
    for p in ts:
        if p["t"] <= cutoff:
            best = p
        else:
            break
    return float(best["p"]) if best else None


def table(samples, label, spread_cost=0.025):
    """samples: list of (price, outcome, event_key)."""
    if len(samples) < 50:
        print(f"  {label}: only {len(samples)} samples — not enough")
        return None
    events = len({s[2] for s in samples})
    print(f"\n  {label}   {len(samples)} markets across {events} EVENTS "
          f"(events are the real sample size)")
    print(f"  {'price bucket':<14} {'n':>5} {'avg price':>10} {'resolved YES':>13} "
          f"{'gap':>8} {'se':>7} {'edge after cost':>16}")
    rows = []
    for lo, hi in BUCKETS:
        sel = [s for s in samples if lo <= s[0] < hi]
        if len(sel) < 15:
            continue
        p = np.array([s[0] for s in sel]); y = np.array([s[1] for s in sel])
        # se on the EVENT count, not the market count: markets inside one event are
        # not independent draws
        ne = len({s[2] for s in sel})
        rate = y.mean()
        se = float(np.sqrt(max(rate * (1 - rate), 1e-9) / max(ne, 1)))
        gap = rate - p.mean()
        # buying this bucket and holding: you pay avg price + spread, receive `rate`
        edge = rate - (p.mean() + spread_cost)
        rows.append((lo, hi, len(sel), ne, p.mean(), rate, gap, se, edge))
        flag = ""
        if abs(gap) > 2 * se:
            flag = " *"
        print(f"  {f'{lo:.2f}-{hi:.2f}':<14} {len(sel):>5} {p.mean():>10.3f} "
              f"{rate:>12.3f} {gap:>+8.3f} {se:>7.3f} {edge:>+15.3f}{flag}")
    print("   * gap exceeds 2 standard errors on the EVENT count")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", type=int, default=800)
    ap.add_argument("--order", default="volumeNum",
                    help="volumeNum biases toward dramatic markets; endDate does not")
    ap.add_argument("--spread", type=float, default=0.025,
                    help="one-way entry cost, from live measurement (~2-3.5%)")
    args = ap.parse_args()
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED PREDICTION: longshot bias appears at the low end but is NOT")
    print("exploitable (the profitable side is shorting 3c contracts). Favourites")
    print("resolving >3 points above their price WOULD be exploitable and new.\n")

    print(f"fetching up to {args.markets} resolved markets...", flush=True)
    ms = fetch_markets(args.markets, args.order)
    print(f"  {len(ms)} returned")
    good = [g for g in (parse(m) for m in ms) if g]
    print(f"  {len(good)} are cleanly resolved binary Yes/No markets")
    print(f"  spanning {len({g[3] for g in good})} distinct events")

    print("\nfetching price history (cached)...", flush=True)
    hist = {}
    for i, (y, tok, ce, ev) in enumerate(good):
        hist[tok] = history(tok)
        if (i + 1) % 100 == 0:
            print(f"    {i+1}/{len(good)}", flush=True)

    print("\n" + "=" * 104)
    print("CALIBRATION — does the price predict the outcome?")
    print("=" * 104)
    print("Perfect calibration: 'resolved YES' equals 'avg price' in every row.")
    print(f"'edge after cost' buys the bucket at its price plus a "
          f"{args.spread*100:.1f}% one-way spread and holds to resolution.")
    allrows = {}
    for days in (1, 7, 30):
        samples = []
        for y, tok, ce, ev in good:
            p = price_at(hist.get(tok) or [], ce, days)
            if p is None or not (0.0 < p < 1.0):
                continue
            samples.append((p, y, ev))
        allrows[days] = table(samples, f"{days} day(s) before resolution",
                              args.spread)

    print("\n" + "=" * 104)
    print("VERDICT")
    print("=" * 104)
    hits = []
    for days, rows in allrows.items():
        if not rows:
            continue
        for lo, hi, n, ne, pm, rate, gap, se, edge in rows:
            if edge > 0 and gap > 2 * se and ne >= 20:
                hits.append((days, lo, hi, ne, pm, rate, edge))
    if not hits:
        print("  NOTHING is mispriced by more than the cost of entering.")
        print("  Polymarket's prices are well enough calibrated that a")
        print("  hold-to-resolution strategy cannot pay for its own spread. The")
        print("  no-minimum-order property is real and valuable, but there is no")
        print("  edge here to spend it on.")
    else:
        print("  BUCKETS THAT BEAT THE SPREAD, on 20+ independent events:")
        for days, lo, hi, ne, pm, rate, edge in sorted(hits, key=lambda h: -h[6]):
            print(f"    {days:>2}d out, price {lo:.2f}-{hi:.2f}: paid "
                  f"{pm:.3f}, resolved {rate:.3f}  ->  "
                  f"{edge:+.3f} per $1 staked ({edge*100:+.1f}%)")
        print("\n  Before believing it: these buckets were selected AFTER seeing the")
        print("  table, across 3 horizons x 10 buckets = 30 cells, so roughly 1.5")
        print("  would clear 2 standard errors by chance. Trust a bucket only if its")
        print("  NEIGHBOURS lean the same way and it repeats at other horizons.")


if __name__ == "__main__":
    main()

"""PRE-REGISTERED FORWARD TEST — is Polymarket's 50-65c band really underpriced?

WHAT THE BACKTEST FOUND, AND WHY IT IS NOT BELIEVED
    backtest/polymarket_bias.py measured, on 800 resolved markets with the price taken
    30 days before trading stopped:

        price 0.50-0.65  ->  resolved YES 80-86% of the time   (+22 to +28 points)
        per-event t = +3.03 and +3.87 on two independent samples
        both time halves positive in both samples
        not event-concentrated (42 markets from 35 distinct events)

    That is a +25% edge per resolution. It should not exist in a market with hundreds
    of millions of dollars of volume, and THREE separate measurement artifacts were
    already found and fixed inside that same test today:

      1. ordering by volume selected markets where the underdog came in, which flipped
         the sign of the classic longshot bias
      2. anchoring the horizon on gamma's nominal `endDate` - a median of 574 days
         after the last real trade - made the 1-day and 7-day tables byte-identical
         and silently sampled the FINAL price
      3. which meant the first "edge" was measuring the market being right, not wrong

    The most likely remaining artifact cannot be ruled out from history at all:
    REQUIRING 30 DAYS OF PRICE HISTORY MAY SELECT TOWARD YES. A market heading for NO
    often stops trading early - the candidate withdraws, the event fizzles - while one
    heading for YES keeps trading until it resolves. If so, "has 30+ days of history"
    is partly a filter for outcomes that happened, and the filter is baked into which
    history exists.

WHY FORWARD DATA SETTLES IT
    Recording a live price on an OPEN market involves no history-length filter, no
    sampling order, and no anchor to get wrong. The market either resolves YES or it
    does not. Nothing about how the snapshot was taken can depend on the outcome,
    because the outcome has not happened yet.

    And prediction markets resolve fast - hundreds a week - so this answers in weeks.

THE PREDICTION, FIXED BEFORE ANY DATA IS COLLECTED
    H1  Markets snapshotted at a price of 0.50-0.65 resolve YES SIGNIFICANTLY more
        often than 0.575 (the bucket's typical price).
    H2  The gap is large enough to beat a 2.5% one-way entry spread.
    H3  (the real claim) the gap is at least +0.10, i.e. half the backtested +0.25.

    SUCCESS CRITERION, ALSO FIXED NOW
      * at least 120 resolved snapshots in the 0.50-0.65 band, AND
      * observed YES rate exceeds the mean snapshot price by more than 2 standard
        errors computed on the EVENT count, AND
      * the gap exceeds +0.10
    Anything less is reported as inconclusive. Every band is recorded, not just the
    interesting one, so the whole calibration curve can be checked and so this cannot
    quietly become a test of only the band that already looked good.

HONEST TIMELINE
    ~200-600 open binary markets are snapshotted per run, of which maybe 5-10% sit in
    the 0.50-0.65 band. Resolutions arrive over days to months depending on the market.
    Expect a first readable answer in 4-8 WEEKS and a solid one in 3 months.

    This records data. It places no orders and needs no keys or funds.

    python poly_forward.py --once      one snapshot, then resolve what it can
    python poly_forward.py             daily loop
    python poly_forward.py --report
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"; LOGS.mkdir(exist_ok=True)
SNAP = LOGS / "poly_snapshots.csv"
LOGF = LOGS / "poly_forward.log"
GAMMA = "https://gamma-api.polymarket.com/markets"
BANDS = [(0.00, 0.05), (0.05, 0.15), (0.15, 0.30), (0.30, 0.50),
         (0.50, 0.65), (0.65, 0.80), (0.80, 0.90), (0.90, 1.00)]
POLL_H = 24


def log(m):
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} | {m}"
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get(u, tries=3):
    for a in range(tries):
        try:
            r = urllib.request.Request(u, headers={"User-Agent": "research/1.0"})
            return json.load(urllib.request.urlopen(r, timeout=30))
        except Exception:
            if a == tries - 1:
                return None
            time.sleep(2)
    return None


def load_snaps() -> dict:
    """condition_id -> row. One snapshot per market, the FIRST time it is seen.

    Never overwritten: re-snapshotting the same market later would let its price drift
    toward the outcome, which is precisely the leak that broke the backtest.
    """
    if not SNAP.exists():
        return {}
    out = {}
    with open(SNAP, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["condition_id"]] = row
    return out


def append(rows):
    new = not SNAP.exists()
    cols = ["ts_utc", "condition_id", "event_id", "question", "price", "bid", "ask",
            "spread", "liquidity", "volume", "end_date", "resolved", "outcome",
            "resolved_ts"]
    with open(SNAP, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def rewrite(snaps):
    cols = ["ts_utc", "condition_id", "event_id", "question", "price", "bid", "ask",
            "spread", "liquidity", "volume", "end_date", "resolved", "outcome",
            "resolved_ts"]
    tmp = SNAP.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in snaps.values():
            w.writerow({c: r.get(c, "") for c in cols})
    tmp.replace(SNAP)


def snapshot(snaps):
    """Record every OPEN binary market not already recorded."""
    fresh, off, seen = [], 0, 0
    while off < 1200:
        page = get(f"{GAMMA}?closed=false&limit=100&offset={off}"
                   f"&order=volumeNum&ascending=false")
        if not page:
            break
        for m in page:
            seen += 1
            try:
                oc = m.get("outcomes")
                if isinstance(oc, str):
                    oc = json.loads(oc)
                if not oc or str(oc[0]).strip().lower() != "yes":
                    continue
                cid = m.get("conditionId")
                if not cid or cid in snaps:
                    continue
                bb, ba = m.get("bestBid"), m.get("bestAsk")
                if bb is None or ba is None:
                    continue
                bb, ba = float(bb), float(ba)
                if not (0.0 < bb < ba < 1.0):
                    continue
                mid = (bb + ba) / 2.0
                ev = m.get("events") or []
                row = dict(
                    ts_utc=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}",
                    condition_id=cid,
                    event_id=(ev[0].get("id") if ev and isinstance(ev[0], dict)
                              else m.get("negRiskMarketID") or cid),
                    question=(m.get("question") or "")[:90].replace(",", ";"),
                    price=f"{mid:.4f}", bid=f"{bb:.4f}", ask=f"{ba:.4f}",
                    spread=f"{ba-bb:.4f}",
                    liquidity=f"{float(m.get('liquidityNum') or 0):.0f}",
                    volume=f"{float(m.get('volumeNum') or 0):.0f}",
                    end_date=str(m.get("endDate") or ""), resolved="0",
                    outcome="", resolved_ts="")
                fresh.append(row)
                snaps[cid] = row
            except Exception:
                continue
        if len(page) < 100:
            break
        off += 100
    if fresh:
        append(fresh)
    log(f"snapshot: scanned {seen} open markets, recorded {len(fresh)} new "
        f"(total tracked {len(snaps)})")
    return len(fresh)


def resolve(snaps):
    """Fill in outcomes for snapshots whose market has since closed."""
    pend = [r for r in snaps.values() if r.get("resolved") != "1"]
    if not pend:
        return 0
    done = 0
    for i in range(0, len(pend), 20):
        ids = [r["condition_id"] for r in pend[i:i + 20]]
        q = "&".join(f"condition_ids={c}" for c in ids)
        page = get(f"{GAMMA}?{q}&limit=20")
        if not page:
            continue
        for m in page:
            cid = m.get("conditionId")
            if cid not in snaps or not m.get("closed"):
                continue
            try:
                op = m.get("outcomePrices")
                if isinstance(op, str):
                    op = json.loads(op)
                y = float(op[0])
                if y not in (0.0, 1.0):
                    continue
            except Exception:
                continue
            snaps[cid]["resolved"] = "1"
            snaps[cid]["outcome"] = str(int(y))
            snaps[cid]["resolved_ts"] = \
                f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}"
            done += 1
    if done:
        rewrite(snaps)
    log(f"resolved {done} snapshots this pass")
    return done


def report(snaps):
    res = [r for r in snaps.values() if r.get("resolved") == "1"]
    log("---- PRE-REGISTERED POLYMARKET FORWARD TEST ----")
    log(f"   tracked {len(snaps)} markets, {len(res)} resolved so far")
    if not res:
        log("   no resolutions yet")
        return
    print(f"\n   {'band':<13} {'n':>5} {'events':>7} {'avg price':>10} "
          f"{'resolved YES':>13} {'gap':>8} {'se':>7} {'edge -2.5%':>11}")
    target = None
    for lo, hi in BANDS:
        sel = [r for r in res if lo <= float(r["price"]) < hi]
        if not sel:
            continue
        p = np.array([float(r["price"]) for r in sel])
        y = np.array([float(r["outcome"]) for r in sel])
        ne = len({r["event_id"] for r in sel})
        rate = y.mean()
        se = float(np.sqrt(max(rate * (1 - rate), 1e-9) / max(ne, 1)))
        gap = rate - p.mean()
        flag = " *" if abs(gap) > 2 * se else ""
        if (lo, hi) == (0.50, 0.65):
            target = (len(sel), ne, p.mean(), rate, gap, se)
        print(f"   {f'{lo:.2f}-{hi:.2f}':<13} {len(sel):>5} {ne:>7} "
              f"{p.mean():>10.3f} {rate:>12.3f} {gap:>+8.3f} {se:>7.3f} "
              f"{rate-p.mean()-0.025:>+11.3f}{flag}")
    print("   * gap exceeds 2 standard errors on the EVENT count")
    if not target:
        log("   nothing resolved in the 0.50-0.65 band yet")
        return
    n, ne, pm, rate, gap, se = target
    ok_n = n >= 120
    ok_sig = gap > 2 * se
    ok_size = gap > 0.10
    print(f"\n   THE PRE-REGISTERED BAND 0.50-0.65:")
    print(f"     n {n} (need 120): {ok_n}")
    print(f"     gap {gap:+.3f} vs 2se {2*se:.3f}: {ok_sig}")
    print(f"     gap exceeds +0.10: {ok_size}")
    if ok_n and ok_sig and ok_size:
        print("     -> ALL THREE MET. The backtested anomaly is real and the")
        print("        history-length selection worry was unfounded.")
    elif ok_n:
        print("     -> ENOUGH DATA, criteria NOT met. The backtested +0.25 was a")
        print("        measurement artifact, most likely the history-length filter.")
    else:
        print("     -> INCONCLUSIVE by design. No verdict until n reaches 120.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    snaps = load_snaps()
    if args.report:
        report(snaps); return
    log("=" * 78)
    log("POLYMARKET FORWARD TEST — records data only, no orders, no keys, no funds")
    log("  H3: markets snapshotted at 0.50-0.65 resolve YES at least +0.10 above")
    log("      their price. Backtest said +0.25; I do not believe it.")
    log("  success needs 120 resolutions in that band, >2se, and gap > +0.10")
    log(f"  {len(snaps)} markets already tracked")
    if args.once:
        snapshot(snaps); resolve(snaps); report(snaps); return
    while True:
        try:
            snapshot(snaps)
            resolve(snaps)
            report(snaps)
        except KeyboardInterrupt:
            log("stopped"); return
        except Exception as e:
            log(f"cycle error: {type(e).__name__}: {str(e)[:180]}")
        time.sleep(POLL_H * 3600)


if __name__ == "__main__":
    main()

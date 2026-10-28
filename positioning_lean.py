"""POSITIONING LEAN - which side of the metals futures is crowded, what has followed that before, and what must roll or be delivered next (2026-10-28)

The user: "make futures positional data from the CFTC report and CME's settlements / delivery, compute and correlate both - the tool must tell me which side
of the market will have an imbalance, and beforehand". This prints, per metal (platinum, palladium, gold, silver, copper):

  1. CFTC (weekly, Disaggregated, futures + options combined; the report for a Tuesday is public on Friday 15:30 New York):
     managed money's net position as a share of open interest - the CROWDED SIDE - and its rank among the last 3 years of weeks; swap dealers (the other
     side); the number of managed-money traders short and the share of open interest the 4 biggest net shorts hold.
  2. WHAT HAS FOLLOWED THAT READING (backtest/cot_metals.py, 2006-2026, 20 trading days after the Friday release, 12bp charged): the average next-4-week move
     after weeks with the same rank bucket, in the tune half and the holdout half, and the REGISTERED TEST'S VERDICT for the market: LEAN only if the
     contrarian signal passed (circular-shift p < 0.05, same sign on both halves, buckets ordered as registered); otherwise NO LEAN - which is what to expect.
  3. CME (recorded from today in logs/cme_snap/ - the free feed keeps only 5 days, so this part has NO tested history): open interest by contract month,
     the share of it still sitting in the next delivery month, the days to FIRST NOTICE DAY (the last business day of the month before the delivery month),
     and the PENDING ROLL: managed money cannot take delivery, so its net position in that month has to be rolled or closed before first notice - a net
     SHORT crowd must BUY the delivery month back (and sell the next one), a net LONG crowd must SELL it. This is arithmetic about who has to trade and
     roughly when, NOT a forecast of the price: rolling a position moves the calendar spread, not the outright price, and the size is an estimate (the CFTC
     figure includes options at their delta, and is a Tuesday's).
The honest limit, stated by the tool every time: the side that MUST trade is knowable beforehand; which way the PRICE goes is not, unless the test says so.

    python positioning_lean.py            the readout (downloads the latest CFTC reports and prices; reads logs/cme_snap/)
    python positioning_lean.py --json     the same numbers as JSON
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from backtest import cot_metals as cm  # noqa: E402

SNAP = ROOT / "logs" / "cme_snap"
TEST_JSON = ROOT / "logs" / "cot_metals.json"
MONTHS = {m: i + 1 for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}
CME_KEY = {"PL": "PL", "PA": "PA", "GC": "GC", "SI": "SI", "HG": "HG"}


def last_business_day(y: int, m: int) -> date:
    d = date(y + (m == 12), 1 if m == 12 else m + 1, 1) - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def first_notice(contract_month: str) -> date:
    """'DEC 26' -> the last business day of November 2026 (holidays ignored: the last business day of these months is never a holiday)."""
    mon, yy = contract_month.split()
    y, m = 2000 + int(yy), MONTHS[mon]
    return last_business_day(y - (m == 1), 12 if m == 1 else m - 1)


def latest_snapshot() -> tuple:
    files = sorted(SNAP.glob("20*.csv"))
    if not files:
        return None, {}
    out: dict = {}
    with open(files[-1], newline="") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["product"], []).append(r)
    return datetime.strptime(files[-1].stem, "%Y-%m-%d").date(), out


def cme_view(key: str, snap_date, snap: dict) -> dict | None:
    rows = snap.get(CME_KEY[key])
    if not rows:
        return None
    tot = [r for r in rows if r["month"] == "Total"]
    months = [r for r in rows if r["month"] != "Total" and float(r["open_interest"] or 0) > 0]
    total_oi = float(tot[0]["open_interest"]) if tot else sum(float(r["open_interest"]) for r in months)
    active = max(months, key=lambda r: float(r["open_interest"]))
    fnd = first_notice(active["month"])
    nxt = sorted((r for r in months if first_notice(r["month"]) > fnd), key=lambda r: first_notice(r["month"]))
    spread = None
    if nxt and active["settle"] not in ("", "-") and nxt[0]["settle"] not in ("", "-"):
        spread = float(nxt[0]["settle"]) - float(active["settle"])
    return dict(date=str(snap_date), active=active["month"], active_oi=float(active["open_interest"]), total_oi=total_oi, share=float(active["open_interest"]) / total_oi,
                fnd=str(fnd), days_to_fnd=(fnd - snap_date).days, next=nxt[0]["month"] if nxt else None, next_oi=float(nxt[0]["open_interest"]) if nxt else None,
                spread=spread, active_settle=float(active["settle"]) if active["settle"] not in ("", "-") else None)


def ordinal(p: float) -> str:
    n = int(round(p * 100))
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def futures_only_net(code: str) -> tuple:
    """Managed money's net lots in FUTURES ONLY (the Disaggregated futures-only report) for the latest week: the roll and delivery concern futures, and the
    futures-and-options-combined figure the test uses counts options at their delta (gold: 532k combined against 401k of CME futures)."""
    import urllib.parse
    q = urllib.parse.urlencode({"$where": f"cftc_contract_market_code='{code}'", "$limit": 1, "$order": "report_date_as_yyyy_mm_dd DESC"})
    r = cm._get(f"https://publicreporting.cftc.gov/resource/72hh-3qpy.json?{q}")[0]
    return float(r["m_money_positions_long_all"]) - float(r["m_money_positions_short_all"]), float(r["open_interest_all"]), r["report_date_as_yyyy_mm_dd"][:10]


def verdicts() -> dict:
    if TEST_JSON.exists():
        return json.loads(TEST_JSON.read_text())
    return {}


def main():
    as_json = "--json" in sys.argv
    snap_date, snap = latest_snapshot()
    tests = verdicts()
    res = {}
    lines = []
    out = lines.append
    out(f"POSITIONING LEAN - metals - run {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")
    for key, m in cm.MARKETS.items():
        f = cm.build(key, "etf")
        last = f.iloc[-1]
        d = f.index[-1]
        known = f.dropna(subset=["fwd", "rank_mm"])
        net_lots = float(last["mm_long"] - last["mm_short"])
        side = "SHORT" if net_lots < 0 else "LONG"
        rank = float(last["rank_mm"])
        bucket = "<= 10th" if rank <= 0.10 else ">= 90th" if rank >= 0.90 else "10-25" if rank <= 0.25 else "75-90" if rank >= 0.75 else "25-75"
        tab = {row[0]: row for row in cm.bucket_table(known, "rank_mm")}
        n, mean, hit, mt, mh = tab[bucket][1:]
        verdict = tests.get(key, {}).get("verdict", "(run backtest/cot_metals.py for the verdict)")
        cme = cme_view(key, snap_date, snap) if snap_date else None
        out("")
        out(f"{m['name'].upper()}  CFTC report {d.date()} (public Fri {(d + timedelta(days=3)).date()}; next report Fri {(d + timedelta(days=10)).date()})")
        out(f"  CROWDED SIDE: managed money {side}, net {net_lots:+,.0f} lots = {last['mm_net'] * 100:+.0f}% of open interest ({int(last['oi']):,}); rank {ordinal(rank)} of the last 3 years "
            f"(4-week change {last['d4'] * 100:+.1f} points). Swap dealers net {last['sw_net'] * 100:+.0f}%. {int(last['n_mm_short'])} managed-money traders short; the 4 biggest net shorts hold {last['top4_short']:.0f}% of open interest.")
        out(f"  HISTORY at rank bucket {bucket}: {n} weeks; the next 4 weeks averaged {mean * 100:+.2f}% (up {hit * 100:.0f}% of the time) - tune {mt * 100:+.2f}%, holdout {mh * 100:+.2f}%.")
        out(f"  TEST VERDICT: {verdict}")
        roll = None
        if cme:
            fut_net, fut_oi, fut_date = futures_only_net(m["code"])
            roll_side = "BUY the delivery month back (and sell the next)" if fut_net < 0 else "SELL the delivery month (and buy the next)"
            roll = dict(lots=abs(fut_net), share_of_active=abs(fut_net) / cme["active_oi"], side=roll_side, futures_only_report=fut_date)
            sp = f", {cme['next']} trades {cme['spread']:+.2f} over it ({'contango: a short is paid to roll, a long pays' if cme['spread'] > 0 else 'backwardation: a long is paid to roll, a short pays'})" if cme["spread"] is not None and cme["next"] else ""
            out(f"  CME {cme['date']}: {cme['active']} holds {cme['active_oi']:,.0f} of {cme['total_oi']:,.0f} open interest ({cme['share'] * 100:.0f}%); first notice day {cme['fnd']} ({cme['days_to_fnd']} days){sp}.")
            out(f"  PENDING ROLL (arithmetic, not a price forecast): managed money's {abs(fut_net):,.0f} net FUTURES lots ({'short' if fut_net < 0 else 'long'}, CFTC futures-only report {fut_date}) = "
                f"{roll['share_of_active'] * 100:.0f}% of that month's open interest must be rolled or closed before first notice -> the side that has to trade: {roll_side}.")
        res[key] = dict(report=str(d.date()), side=side, net_lots=net_lots, mm_net=float(last["mm_net"]), rank=rank, bucket=bucket, hist=dict(n=n, mean=mean, up=hit, tune=mt, hold=mh),
                        verdict=verdict, cme=cme, roll=roll)
    out("")
    out("WHAT THIS CAN AND CANNOT TELL YOU: the CROWDED side and the side that MUST trade at the next first-notice day are facts you can read today. Which way the price")
    out("moves afterwards is only a 'lean' if the verdict above says LEAN; the registered test (logs/cot_metals.txt) is the thing to read before trusting any arrow.")
    out("CME's free feed keeps 5 days: the CME block is a record that starts 2026-10-27 and has no tested history yet.")
    if as_json:
        print(json.dumps(res, default=str, indent=1))
    else:
        print("\n".join(lines))


if __name__ == "__main__":
    main()

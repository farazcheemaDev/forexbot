"""THE CROWD-SQUEEZE BOOK, ON PAPER - long the coins the crowd is most short, short the most long (2026-10-23)

THE USER (2026-10-23): "do 2 3" - (2) the market-mood readout on the dashboard, (3) paper-test the crowd book. Doc 22
freezes new books to 2027-04-09; the user overrode it for THIS PAPER RECORD only. It is not part of the final machine:
its own $300, its own files, nothing shared with combo_bot, and the machine's day-45 checkpoint is untouched. Real money
would still need doc 22's rules.

THE RULE - news/positioning_hist.py's backtest, the same rule, not a variant:
  universe  the top 40 USDT perps by the prior month's quote volume, listed >= 30 days, stables / gold dropped
            (news/mood_now.universe = drop_non_crypto(wide_book.eligibility(40)))
  signal    each coin's long / short ACCOUNT ratio (Binance, every user) at the anchor: the last 5-minute row before
            00:00 UTC (the backtest read the archive day's last row, 23:45-23:50)
  legs      rank the coins with a ratio and a price; LONG the bottom quarter (most short), SHORT the top quarter
            (positioning_hist.quarters); 0.5 of the sleeve a side, equal weights; under 16 coins -> no trade that week
  held      7 days, from the anchor's 00:00 UTC daily close to the next anchor's; funding on the entry notional for every
            settlement in (entry, exit] (a long pays, a short receives - Binance stamps a settlement a few ms after the
            hour, so times are read to the minute); fee 12bp x min(2 x the share of names changed, 1) of the sleeve, as
            the backtest charges it (about twice the real cost when only some names change - kept, so this is the
            backtest's own book and its band applies)
  sleeves   MONDAY and THURSDAY anchors, $150 each ($300 together; a weekly book on one weekday has misled this repo)
FILLS     at the anchor's daily close, as the backtest. Prices and the crowd are read AT the anchor from Binance's history
          (30 days kept), so a late run changes nothing; a delisted coin closes at its last daily close.
FILES     logs/crowd_paper/state.json, weeks.csv (per sleeve-week and coin), sleeves.csv (per sleeve-week), marks.csv
          (daily equity), and logs/mood/mood.json (news/mood_now.snapshot, for the dashboard). STANDARD LIBRARY ONLY
          (the VM has ~50 MB free).
RUNS      hourly on the VM (deploy/crowd-paper.service + .timer); public Binance endpoints, no keys, no orders.

REGISTERED BEFORE THE FIRST ANCHOR (2026-10-23). Yardstick: crowd_bands.json / logs/crowd_bands.txt - this book over every
N-week stretch of 2022-01 .. 2026-09 (positioning_hist.py --band):
  VERDICT at 26 weeks (the Monday sleeve's 26th close, 2027-04-26 00:00 UTC), the two sleeves' return since the start:
    under -6.5% (the backtest's 10th percentile of 26-week stretches)  -> DEAD, stop it
    -6.5% .. +18.4% (under the backtest's median)                     -> not shown; run on to 52 weeks (p10 there -7.0%)
    +18.4% or more                                                     -> held up; a candidate for doc 22's money rules
  C1 funding: the book's summed funding over 26 weeks is POSITIVE (crowded shorts pay the long quarter).
  C2 the 26-week result lands in the backtest's middle half (+4.6% .. +27.1%).
  C3 at least one long-leg coin rises 50% or more in its week within the 26 weeks (the squeezes are the engine).
  A month swings -6% .. +11% in the backtest: read the first two months as noise. The dashboard places the live result
  in the backtest's range from week 4.

    python -m news.crowd_paper            one cycle: the mood snapshot, any due week close / open, the daily mark
    python -m news.crowd_paper --status
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from news import mood_now as mn  # noqa: E402

DIR = ROOT / "logs" / "crowd_paper"
STATE, WEEKS, SLEEVES_CSV, MARKS = DIR / "state.json", DIR / "weeks.csv", DIR / "sleeves.csv", DIR / "marks.csv"
MOOD = ROOT / "logs" / "mood" / "mood.json"
START_USD = 300.0
SLEEVES = {"mon": 0, "thu": 3}                      # weekday of the anchor
FIRST = {"mon": "2026-10-26", "thu": "2026-10-29"}  # the first anchors, registered
FEE = 12.0 / 1e4
MIN_COINS = 16
DAY = mn.DAY_MS
MINUTE = 60_000


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def log(msg: str):
    print(f"{now_utc():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def ms(d: datetime) -> int:
    return int(d.timestamp() * 1000)


def day0(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


# ------------------------------------------------------------------ the rule (tests/test_crowd_paper.py: = the backtest's)

def quarters(crowd: dict) -> tuple[set, set]:
    """positioning_hist.quarters on a {sym: ratio} dict: the bottom and the top quarter of the pct ranking."""
    p = mn.pct_rank(crowd)
    return {s for s, x in p.items() if x <= 0.25}, {s for s, x in p.items() if x >= 0.75}


def turnover_fee(prev_l: set, prev_s: set, ln: set, sn: set) -> float:
    ch = (len(ln ^ prev_l) + len(sn ^ prev_s)) / max(2 * (len(ln) + len(sn)), 1)
    return FEE * min(ch * 2, 1.0)


def legs(crowd: dict, price: dict) -> list[dict]:
    """The week's positions: long the most-short quarter, short the most-long one, 0.5 of the sleeve a side."""
    ok = {s: c for s, c in crowd.items() if c is not None and price.get(s)}
    if len(ok) < MIN_COINS:
        return []
    lo, hi = quarters(ok)
    return ([dict(sym=s, side=1, w=0.5 / len(lo), entry=price[s]) for s in sorted(lo)]
            + [dict(sym=s, side=-1, w=0.5 / len(hi), entry=price[s]) for s in sorted(hi)])


def gross(pos: list[dict], px: dict, fund: dict) -> float:
    """The sleeve's return on its opening equity: sum of side x weight x (price move - funding paid by a long)."""
    return sum(p["side"] * p["w"] * (px[p["sym"]] / p["entry"] - 1 - fund.get(p["sym"], 0.0)) for p in pos)


# ------------------------------------------------------------------ Binance, read at a time

def price_at(sym: str, at_ms: int):
    """The close of the last daily bar that closed by at_ms (an anchor's own 00:00 close; a delisted coin's last)."""
    k = mn.get(f"{mn.FAPI}/fapi/v1/klines?symbol={sym}&interval=1d&endTime={at_ms - DAY}&limit=1")
    return float(k[-1][4]) if k else None


def funding_sum(sym: str, a_ms: int, b_ms: int) -> float:
    """Funding rates summed over settlements in (a, b], each read to the minute."""
    f = mn.get(f"{mn.FAPI}/fapi/v1/fundingRate?symbol={sym}&startTime={a_ms + MINUTE}&endTime={b_ms + MINUTE - 1}&limit=1000")
    return sum(float(x["fundingRate"]) for x in f)


# ------------------------------------------------------------------ state

def fresh() -> dict:
    return dict(started=now_utc().strftime("%Y-%m-%d %H:%M:%S"), start=START_USD, first=min(FIRST.values()),
                sleeves={k: dict(equity=START_USD / len(SLEEVES), next=FIRST[k], pos=[], fee=0.0, opened=None,
                                 prev_l=[], prev_s=[], weeks=0, fund_usd=0.0) for k in SLEEVES}, marked=None)


def load() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else fresh()


def save(st: dict):
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=1))
    os.replace(tmp, STATE)


def append(p: Path, row: dict):
    new = not p.exists()
    with p.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)


# ------------------------------------------------------------------ one anchor: close last week, open this one

def close_week(k: str, sl: dict, a_ms: int, price=price_at, fsum=funding_sum):
    pos, o_ms = sl["pos"], ms(day0(sl["opened"]))
    px = {p["sym"]: price(p["sym"], a_ms) or p.get("mark") or p["entry"] for p in pos}
    fund = {p["sym"]: fsum(p["sym"], o_ms, a_ms) for p in pos}
    g = gross(pos, px, fund)
    eq0 = sl["equity"]
    net = g - sl["fee"]
    sl["equity"] = eq0 * (1 + net)
    f_usd = -sum(p["side"] * p["w"] * fund[p["sym"]] for p in pos) * eq0
    sl["fund_usd"] += f_usd
    sl["weeks"] += 1
    close = datetime.fromtimestamp(a_ms / 1000, timezone.utc).strftime("%Y-%m-%d")
    for p in pos:
        r = px[p["sym"]] / p["entry"] - 1
        append(WEEKS, dict(sleeve=k, opened=sl["opened"], closed=close, sym=p["sym"], side=p["side"], w=round(p["w"], 6),
                           entry=p["entry"], exit=px[p["sym"]], ret=round(r, 6), fund=round(fund[p["sym"]], 8),
                           usd=round(eq0 * p["side"] * p["w"] * (r - fund[p["sym"]]), 4)))
    append(SLEEVES_CSV, dict(sleeve=k, opened=sl["opened"], closed=close, n_long=sum(p["side"] > 0 for p in pos),
                             n_short=sum(p["side"] < 0 for p in pos), gross=round(g, 6), fee=round(sl["fee"], 6),
                             net=round(net, 6), funding_usd=round(f_usd, 4), equity_before=round(eq0, 4),
                             equity_after=round(sl["equity"], 4)))
    log(f"CLOSE {k} week {sl['opened']} -> {close}: gross {g * 100:+.2f}% fee {sl['fee'] * 100:.2f}% -> ${sl['equity']:.2f}")
    sl["pos"], sl["fee"] = [], 0.0


def open_week(k: str, sl: dict, a_ms: int, universe=None, crowd=None, price=price_at):
    a = datetime.fromtimestamp(a_ms / 1000, timezone.utc)
    names = (universe or mn.universe)(now=a)
    cr = {s: (crowd or mn.crowd_at)(s, a_ms)[0] for s in names}
    px = {s: price(s, a_ms) for s in names if cr.get(s) is not None}
    new = legs(cr, px)
    if not new:
        log(f"OPEN {k} {a:%Y-%m-%d}: only {sum(v is not None for v in cr.values())} coins with a crowd reading - no trade this week")
        sl["opened"] = None
        return
    ln, sn = {p["sym"] for p in new if p["side"] > 0}, {p["sym"] for p in new if p["side"] < 0}
    sl["fee"] = turnover_fee(set(sl["prev_l"]), set(sl["prev_s"]), ln, sn)
    sl["prev_l"], sl["prev_s"] = sorted(ln), sorted(sn)
    for p in new:
        p["mark"], p["fund"] = p["entry"], 0.0
    sl["pos"], sl["opened"] = new, f"{a:%Y-%m-%d}"
    log(f"OPEN {k} {a:%Y-%m-%d}: long {' '.join(s[:-4] for s in sorted(ln))} | short {' '.join(s[:-4] for s in sorted(sn))}"
        f" | fee {sl['fee'] * 100:.2f}% on ${sl['equity']:.2f}")


def anchors(st: dict, now: datetime, **kw):
    """Every anchor that has come due since the last run, in time order (missed ones too: the history is 30 days)."""
    due = sorted((day0(sl["next"]), k) for k, sl in st["sleeves"].items() if day0(sl["next"]) <= now)
    while due:
        a, k = due.pop(0)
        sl = st["sleeves"][k]
        if sl["pos"]:
            close_week(k, sl, ms(a), **{x: v for x, v in kw.items() if x in ("price", "fsum")})
        open_week(k, sl, ms(a), **{x: v for x, v in kw.items() if x in ("universe", "crowd", "price")})
        sl["next"] = f"{a + timedelta(days=7):%Y-%m-%d}"
        save(st)
        if day0(sl["next"]) <= now:
            due = sorted(due + [(day0(sl["next"]), k)])


# ------------------------------------------------------------------ the daily mark

def sleeve_now(sl: dict) -> float:
    """The sleeve's equity at its positions' last marks (marks / funding refreshed daily)."""
    if not sl["pos"]:
        return sl["equity"]
    return sl["equity"] * (1 + gross(sl["pos"], {p["sym"]: p["mark"] for p in sl["pos"]},
                                     {p["sym"]: p["fund"] for p in sl["pos"]}) - sl["fee"])


def mark(st: dict, now: datetime, price=price_at, fsum=funding_sum):
    today = f"{now:%Y-%m-%d}"
    if st.get("marked") == today:
        return
    d_ms = ms(day0(today))
    for sl in st["sleeves"].values():
        if not sl["pos"]:
            continue
        o_ms = ms(day0(sl["opened"]))
        for p in sl["pos"]:
            p["mark"] = price(p["sym"], d_ms) or p["mark"]
            p["fund"] = fsum(p["sym"], o_ms, d_ms) if d_ms > o_ms else 0.0
    eq = {k: round(sleeve_now(sl), 4) for k, sl in st["sleeves"].items()}
    append(MARKS, dict(day=today, mon=eq["mon"], thu=eq["thu"], total=round(sum(eq.values()), 4)))
    st["marked"] = today
    log(f"MARK {today}: mon ${eq['mon']:.2f} thu ${eq['thu']:.2f} total ${sum(eq.values()):.2f}")


# ------------------------------------------------------------------ the cycle

def write_mood():
    try:
        S = mn.snapshot()
    except Exception as e:  # noqa: BLE001 - the readout is context; the book must still run
        log(f"mood snapshot failed: {type(e).__name__}: {str(e)[:120]}")
        return
    MOOD.parent.mkdir(parents=True, exist_ok=True)
    tmp = MOOD.with_suffix(".tmp")
    tmp.write_text(json.dumps(S, separators=(",", ":")))
    os.replace(tmp, MOOD)


def cycle():
    now = now_utc()
    write_mood()
    st = load()
    anchors(st, now)
    mark(st, now)
    save(st)


def status() -> str:
    st = load()
    L = [f"CROWD-SQUEEZE PAPER BOOK (news/crowd_paper.py), started {st['started']} UTC, ${st['start']:.0f} on paper"]
    tot = 0.0
    for k, sl in st["sleeves"].items():
        e = sleeve_now(sl)
        tot += e
        L.append(f"   {k}: ${e:.2f} (booked ${sl['equity']:.2f}, {sl['weeks']} weeks closed, funding ${sl['fund_usd']:+.2f}),"
                 f" next anchor {sl['next']}" + (f", holding {len(sl['pos'])} legs since {sl['opened']}" if sl["pos"] else ""))
    L.append(f"   total ${tot:.2f} ({(tot / st['start'] - 1) * 100:+.2f}%), last mark {st.get('marked')}")
    return "\n".join(L)


if __name__ == "__main__":
    if "--status" in sys.argv:
        print(status())
    else:
        cycle()

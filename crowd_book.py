"""THE CROWD-SQUEEZE BOOK INSIDE THE MACHINE - `combo_bot.py --final --crowd` (the FRESH paper account only; 2026-10-25)

THE USER (2026-10-25): "add the crowd book to the machine now ... add to fresh only", at full size. news/crowd_paper.py
keeps running on its own (its own $300 and its own verdict); this is the same book as one more book of the netted
account, so the account the user may later fund carries it - backtest/crowd_combo.py measured that account: +34% (2022-24)
/ +77% (2024-26) on the typical $300 year at x1.0, worst month 1-3 points deeper, 10/10 orderings (BACKTEST, picked from
the same data, a lead).

THE RULE - news/crowd_paper.py's own functions, unchanged:
  universe   news/mood_now.universe (the top 40 by the prior month's volume, listed >= 30 days, stables dropped)
  signal     each coin's long / short account ratio at the anchor (mood_now.crowd_at: the last 5-minute row before it)
  legs       crowd_paper.legs: LONG the most-short quarter, SHORT the most-long, 0.5 a side, equal weights; < 16 coins ->
             no trade that week
  halves     MONDAY and THURSDAY anchors (00:00 UTC), each with half of the book's capital
  size       K_CROWD x the ACCOUNT's equity at the anchor, halved per sleeve - so the book grows and shrinks with the
             account, like every other book here (the standalone paper book compounds its own $150 halves instead)
  fee        crowd_paper.turnover_fee (the backtest's 12bp x min(2 x names changed, 1)) on the half's capital, at the open
  funding    funding_sum over (entry, exit] per leg, charged at the close (a long pays, a short receives)
LIVE vs THE PAPER BOOK / BACKTEST, stated so it can be subtracted
  1. Entries and exits at the bot's live price on the first poll after the anchor (~1-2 minutes after 00:00 UTC), not at
     the daily close. A late process (down at the anchor) rebalances at its first poll - after a gap of more than a week
     only the latest anchor is traded (the weeks in between cannot be, live).
  2. Netted with the other books per coin; the account's 14.5x gross gate covers it (the backtest did not model the gate).
  3. P&L booked at each week's close into the account (st["equity"], cum["crowd"]); the dashboard marks open legs live.
MAIN IS UNTOUCHED: without --crowd there is no "crowd" key in the state and every function here is a no-op.

    python combo_bot.py --mode dry --final --account fresh --crowd        (deploy/combo-bot-fresh.service)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from news import crowd_paper as cpb
from news import mood_now as mn

K_CROWD = 1.0
SLEEVES = cpb.SLEEVES                 # {"mon": 0, "thu": 3}
DAY = 86_400_000


def log(m: str):
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} {m}", flush=True)


def next_anchor(wd: int, now: datetime) -> str:
    """The first 00:00 UTC on weekday wd strictly after now's day start (today's anchor, if any, has passed)."""
    d = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=1)
    while d.weekday() != wd:
        d += timedelta(days=1)
    return f"{d:%Y-%m-%d}"


def fresh(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    return dict(on=True, sleeves={k: dict(next=next_anchor(wd, now), pos=[], cap=0.0, opened=None, prev_l=[], prev_s=[],
                                          weeks=0) for k, wd in SLEEVES.items()})


def ensure(st: dict, on: bool) -> None:
    """--crowd: give the state its book (once); without the flag nothing is added."""
    if on and "crowd" not in st["fin"]:
        st["fin"]["crowd"] = fresh()
        log(f"CROWD: book added at x{K_CROWD:g} of the account; first anchors "
            + ", ".join(f"{k} {s['next']}" for k, s in st["fin"]["crowd"]["sleeves"].items()))


def active(st: dict) -> bool:
    return bool((st.get("fin") or {}).get("crowd", {}).get("on"))


def targets(st: dict) -> dict:
    """Signed coin quantities the crowd legs hold, by Binance symbol."""
    out: dict = {}
    if not active(st):
        return out
    for sl in st["fin"]["crowd"]["sleeves"].values():
        for p in sl["pos"]:
            out[p["sym"]] = out.get(p["sym"], 0.0) + p["qty"]
    return out


def _book(st, pnl, fee):
    st["equity"] += pnl - fee
    cum = st.setdefault("cum", {})
    cum["crowd"] = cum.get("crowd", 0.0) + pnl
    cum["fees"] = cum.get("fees", 0.0) + fee
    cum["crowd_fees"] = cum.get("crowd_fees", 0.0) + fee            # so the scorecard can leave the whole book out


def close_week(st: dict, k: str, sl: dict, prices: dict, now_ms: int, fund, rec=None) -> None:
    legs = []                                                       # every leg first: a network failure books nothing
    for p in sl["pos"]:
        px = prices.get(p["sym"]) or p["entry"]                     # a coin with no price now: closed flat, logged
        f = fund(p["sym"], p["t_ms"], now_ms)
        legs.append((p, px, f, p["side"] * p["w"] * (px / p["entry"] - 1 - f) * sl["cap"]))
    pnl = sum(x[3] for x in legs)
    _book(st, pnl, 0.0)
    for p, px, f, r in legs:
        if not prices.get(p["sym"]):
            log(f"CROWD {k}: no price for {p['sym']} at the close - booked flat")
        if rec:
            rec(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}", book="crowd", symbol=p["sym"],
                     entry=f"{p['entry']:.8g}", exit=f"{px:.8g}", ret=f"{p['side'] * (px / p['entry'] - 1 - f):.5f}",
                     pnl=f"{r:.4f}", why=f"{k} week, {'long' if p['side'] > 0 else 'short'}",
                     equity=f"{st['equity']:.4f}"))
    sl["weeks"] += 1
    log(f"CROWD CLOSE {k} week from {sl['opened']}: P&L {pnl:+.2f} on ${sl['cap']:.2f} ({pnl / sl['cap'] * 100:+.2f}%) "
        f"-> account {st['equity']:.2f}")
    sl["pos"], sl["cap"] = [], 0.0


def open_week(st: dict, k: str, sl: dict, a: datetime, prices: dict, now_ms: int,
              universe=None, crowd=None) -> None:
    a_ms = int(a.timestamp() * 1000)
    names = (universe or mn.universe)(now=a)
    cr = {s: (crowd or mn.crowd_at)(s, a_ms)[0] for s in names}
    px = {s: prices.get(s) for s in names if cr.get(s) is not None and prices.get(s)}
    new = cpb.legs(cr, px)
    if not new:
        log(f"CROWD OPEN {k} {a:%Y-%m-%d}: only {len(px)} coins with a reading and a price - no trade this week")
        sl["opened"] = None
        return
    cap = K_CROWD * st["equity"] / len(SLEEVES)
    ln, sn = {p["sym"] for p in new if p["side"] > 0}, {p["sym"] for p in new if p["side"] < 0}
    fee = cpb.turnover_fee(set(sl["prev_l"]), set(sl["prev_s"]), ln, sn) * cap
    for p in new:
        p.update(qty=p["side"] * p["w"] * cap / p["entry"], t_ms=now_ms)
    sl.update(pos=new, cap=cap, opened=f"{a:%Y-%m-%d}", prev_l=sorted(ln), prev_s=sorted(sn))
    _book(st, 0.0, fee)
    log(f"CROWD OPEN {k} {a:%Y-%m-%d} on ${cap:.2f}: long {' '.join(s[:-4] for s in sorted(ln))} | short "
        f"{' '.join(s[:-4] for s in sorted(sn))} | fee ${fee:.2f}")


def poll(st: dict, prices: dict, now_ms: int, rec=None, fund=None, universe=None, crowd=None) -> None:
    """Every poll: any anchor that has come due closes its half's week and opens the next (at today's live prices)."""
    if not active(st) or not prices:
        return
    import final_books as fb
    fund = fund or fb.funding_sum
    now = datetime.fromtimestamp(now_ms / 1000, timezone.utc)
    for k, wd in SLEEVES.items():
        sl = st["fin"]["crowd"]["sleeves"][k]
        a = cpb.day0(sl["next"])
        if now < a:
            continue
        while a + timedelta(days=7) <= now:                          # down for over a week: only the latest anchor
            log(f"CROWD {k}: anchor {a:%Y-%m-%d} missed (process down) - not traded")
            a += timedelta(days=7)
        try:
            if sl["pos"]:
                close_week(st, k, sl, prices, now_ms, fund, rec)
            open_week(st, k, sl, a, prices, now_ms, universe, crowd)
        except Exception as e:  # noqa: BLE001 - a network failure: nothing booked twice, tried again next poll
            log(f"CROWD {k}: anchor {a:%Y-%m-%d} not processed ({type(e).__name__}: {str(e)[:120]}) - retrying next poll")
            return
        sl["next"] = f"{a + timedelta(days=7):%Y-%m-%d}"


def status(st: dict) -> None:
    if not active(st):
        return
    c = st["fin"]["crowd"]
    for k, sl in c["sleeves"].items():
        print(f"  crowd {k}: {len(sl['pos'])} legs on ${sl['cap']:.2f} since {sl['opened']}, {sl['weeks']} weeks closed, "
              f"next anchor {sl['next']}")
    print(f"  crowd booked P&L {st.get('cum', {}).get('crowd', 0.0):+.2f}")

"""THE CRASH-BID DESK - doc 16's rule executed on combo_bot.py's account (`combo_bot.py --wick`).

THE RULE (doc 16, wick_paper.py, identical numbers)
    Every hour, a resting post-only BUY 10% under the previous hour's close on each of the top-40
    perps (Binance's prior-month volume ranking, mapped to the venue), 1/40 of account equity each.
    None on days BTC's 50-day label is BEAR. Once 10 bids have filled in the hour, the rest are
    CANCELLED. Everything that filled is sold at the hour's close.

HOW IT LIVES INSIDE combo_bot.py (one account, one bot, one net position per coin)
    - The desk only ever places LIMIT BUYS. It never sells. Its filled quantity is added to the
      bot's targets (`hold`), so combo_bot's netting keeps it; at the hour's close the desk clears
      `hold`, and the very next execute() sells it at market through the same netting that runs
      the other books. So a fill on a coin the trend book is short simply shrinks the short.
    - watch() runs every few seconds between the bot's 2-minute polls. It counts fills from the
      venue's open-order list and cancels the remaining bids the moment the tenth has filled.
      The cap is WHY this cannot run on the 2-minute poll: on 2025-10-10 38 of 40 bids filled
      inside minutes, and uncapped that hour left 10% of the account (joint_worst_hour.py).
    - Stale bids (the process was down across an hour) are cancelled on the first tick.

WHAT IT CANNOT PROTECT AGAINST, stated so nobody assumes otherwise
    If the machine running the bot is DOWN while bids rest, they can fill with no cap and no exit
    until it returns (the VM service restarts in 30 s; a dead VM does not). The 30% disaster stops
    combo_bot places cover a filled position only after the next execute().

    python combo_bot.py --mode demo --wick                          the rule, on the demo
    python combo_bot.py --mode demo --wick --wick-dist 0.001 --wick-cap 2 --wick-usd 30   order-path
        test: bids 0.1% under the last close so they fill within the hour, cap 2 so the cancel path
        runs, $30 a bid so the demo's BTC / ETH minimum sizes are met

AT $300 (checked against Bitget's real market list, 2026-09-25): $7.50 a bid is under Bitget's minimum
size for BTC, ETH, SOL, LINK, UNI, NEAR, AAVE and LIT, so about 30 of the 40 coins get bids; the desk
logs which. 1000PEPE / 1000SHIB are not mapped (Bitget prices single PEPE / SHIB) and are skipped.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

HOUR_S = 3600
TOP_N = 40
BID_K = 0.10
CAP = 10
TICK_S = 3
MIN_ORDER = 5.0


def fresh() -> dict:
    return dict(hour=None, orders={}, hold={}, fills=0, cap_hit=False, bear_day=None, month=None,
                coins=[], hours=0, total_fills=0, caps_hit=0)


class WickDesk:
    """venue: combo_bot.Venue (or a fake). coins_fn(month) -> Binance symbols; label_fn(day) -> 'bear'...;
    equity_fn() -> dollars to size from; log(str)."""

    def __init__(self, venue, coins_fn, label_fn, equity_fn, log, dist=BID_K, cap=CAP, dry=False,
                 record=None, size_usd=None):
        self.venue, self.coins_fn, self.label_fn, self.equity_fn = venue, coins_fn, label_fn, equity_fn
        self.log, self.dist, self.cap, self.dry, self.record = log, dist, cap, dry, record
        self.size_usd = size_usd                   # tests only: a fixed $ per bid

    # ------------------------------------------------------------ the hour
    def tick(self, st: dict, now: float | None = None) -> bool:
        """Call every TICK_S. Returns True when an hour rolled over: the caller must execute() now,
        which sells the finished hour's fills."""
        w = st.setdefault("wick", fresh())
        now = time.time() if now is None else now
        H = int(now // HOUR_S * HOUR_S)
        if w["hour"] != H:
            self.close_hour(st)
            self.open_hour(st, H)
            return True
        self.watch(st)
        return False

    def close_hour(self, st: dict):
        """Cancel what is still resting, read the final fills (for the record), and release `hold`
        so the next execute() sells it."""
        w = st["wick"]
        if not w["orders"]:
            w["hold"] = {}
            return
        for oid, o in w["orders"].items():
            if o["status"] == "open" and not self.dry:
                try:
                    self.venue.cancel_limit(o["s"], oid)
                except Exception as e:  # noqa: BLE001 - an already-filled or gone order
                    self.log(f"WICK {o['sym']}: cancel note {str(e)[:100]}")
                o["status"] = "cancelled"
        if not self.dry:
            self.watch(st, final=True)
        sold = {k: v for k, v in w["hold"].items() if v}
        if self.record:
            self.record(dict(hour=datetime.fromtimestamp(w["hour"], timezone.utc).strftime("%Y-%m-%d %H:00"),
                             bids=len(w["orders"]), fills=w["fills"], cap_hit=int(w["cap_hit"]),
                             sold=" ".join(f"{k[:-4]}:{v:.6g}" for k, v in sold.items())))
        if sold:
            self.log(f"WICK hour closed: {w['fills']} filled{' (cap hit)' if w['cap_hit'] else ''} - "
                     f"selling {', '.join(k[:-4] for k in sold)} at the close")
        w["hold"], w["orders"] = {}, {}

    def open_hour(self, st: dict, H: int):
        w = st["wick"]
        w.update(hour=H, orders={}, fills=0, cap_hit=False)
        w["hours"] += 1
        ts = datetime.fromtimestamp(H, timezone.utc)
        day, month = f"{ts:%Y-%m-%d}", f"{ts:%Y-%m}"
        if w.get("label_day") != day:
            w["bear_day"] = self.label_fn(day) == "bear"
            w["label_day"] = day
            self.log(f"WICK day {day}: {'BEAR - no bids today' if w['bear_day'] else 'bids on'}")
        if w["bear_day"]:
            return
        if w["month"] != month or not w["coins"]:
            w["coins"], w["month"] = list(self.coins_fn(month)), month
            self.log(f"WICK universe {month}: {len(w['coins'])} coins")
        size = self.size_usd or self.equity_fn() / TOP_N
        if size < MIN_ORDER:
            self.log(f"WICK: ${size:.2f} a bid is under the ${MIN_ORDER:g} minimum - no bids this hour")
            return
        placed, small, unlisted = 0, [], []
        for sym in w["coins"]:
            s = self.venue.symbol(sym)
            if s is None:                              # e.g. 1000PEPE: Bitget prices single PEPE
                unlisted.append(sym[:-4])
                continue
            try:
                prev = self.venue.prev_close(s, H)
                if not prev:
                    continue
                bid = prev * (1 - self.dist)
                try:
                    n = self.venue.contracts(s, size / bid)
                except Exception:                      # ccxt: below the venue's minimum amount
                    n = 0.0
                if n <= 0 or n * self.venue.coin_size(s) * bid < MIN_ORDER:
                    small.append(sym[:-4])
                    continue
                if self.dry:
                    oid = f"dry-{sym}-{H}"
                else:
                    self.venue.settings(s)
                    o = self.venue.limit_buy(s, n, bid)
                    oid = str(o.get("id"))
                w["orders"][oid] = dict(sym=sym, s=s, bid=bid, contracts=n, filled=0.0, counted=False,
                                        status="open")
                placed += 1
            except Exception as e:  # noqa: BLE001
                self.log(f"WICK {sym}: bid not placed ({str(e)[:120]})")
        self.log(f"WICK {ts:%Y-%m-%d %H:00}: {placed} bids placed {self.dist:.1%} under the last close, "
                 f"${size:.2f} each, cap {self.cap}{' (DRY: none sent)' if self.dry else ''}")
        note = (tuple(small), tuple(unlisted))
        if note != tuple(map(tuple, w.get("skipped_note", ((), ())))):
            w["skipped_note"] = [list(small), list(unlisted)]
            if small:
                self.log(f"WICK: ${size:.2f} is under the venue's minimum size for {', '.join(small)} - "
                         f"no bids there until the account is larger")
            if unlisted:
                self.log(f"WICK: not mapped on this venue: {', '.join(unlisted)} - no bids there")

    # ------------------------------------------------------------ fills and the cap
    def watch(self, st: dict, final: bool = False):
        """Read fills; add them to `hold`; cancel the rest once `cap` bids have filled."""
        w = st.get("wick")
        if self.dry or not w or not w["orders"]:
            return
        try:
            pend = self.venue.pending()                    # {order id: filled contracts}
        except Exception as e:  # noqa: BLE001
            self.log(f"WICK: cannot read open orders ({str(e)[:100]})")
            return
        for oid, o in w["orders"].items():
            if o["status"] == "done":
                continue
            if oid in pend:                                # still resting, maybe partly filled
                filled = pend[oid]
            else:                                          # gone: fully filled, or cancelled
                try:
                    filled = self.venue.filled(o["s"], oid)
                except Exception as e:  # noqa: BLE001
                    self.log(f"WICK {o['sym']}: cannot read order {oid} ({str(e)[:80]})")
                    continue
                o["status"] = "done"
            if filled > o["filled"] + 1e-12:
                coins = (filled - o["filled"]) * self.venue.coin_size(o["s"])
                w["hold"][o["sym"]] = w["hold"].get(o["sym"], 0.0) + coins
                o["filled"] = filled
                if not o["counted"]:
                    o["counted"] = True
                    w["fills"] += 1
                    w["total_fills"] += 1
                    self.log(f"WICK FILL {o['sym']} at <= {o['bid']:.6g} ({w['fills']} this hour)")
        if w["fills"] >= self.cap and not w["cap_hit"] and not final:
            w["cap_hit"] = True
            w["caps_hit"] += 1
            left = [(oid, o) for oid, o in w["orders"].items() if o["status"] == "open" and not o["counted"]]
            for oid, o in left:
                try:
                    self.venue.cancel_limit(o["s"], oid)
                    o["status"] = "cancelled"
                except Exception as e:  # noqa: BLE001
                    self.log(f"WICK {o['sym']}: cancel at cap FAILED ({str(e)[:100]})")
            self.log(f"WICK CAP: {w['fills']} fills this hour - cancelled the other {len(left)} bids")

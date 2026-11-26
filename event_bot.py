"""THE EVENT ACCOUNT - a separate $300 PAPER account that runs only the final machine's event books (2026-11-27).

THE USER (2026-11-26/27): "what can we deduce, what's working, what can we do" -> "Yes, set it up". After the final machine's
day-45 KILL (doc 22 s3b: main $224.29 against $261.30 on 2026-11-23) the books that held up were the ones that wait for a
forced trader or a payment with a trigger: funding carry, capit2 (the capitulation limit buy), the news shorts, the NASDAQ
dip-buy and the crash bids. Everything that lost was a RANKING of pump coins (market-neutral, daily breakout) plus the trend
longs. This account is the first with the losers switched off - a NEW pre-registered test, which is what doc 22 s3b says may
reopen the funding question. It is paper only: no orders, no keys, `--mode dry` is hard-coded and `--account events` writes
only to logs/combo_bot_dry_final_events/. ALLOW_REAL is untouched.

HOW IT RUNS (no running bot's file is changed). This wrapper imports combo_bot / combo_paper / final_books, changes FIVE
settings in ITS OWN process, and calls combo_bot.main() with `--mode dry --final --account events`:
    cp.K_MN = 0, cp.K_SLEEVE = 0, cp.signal -> 0   the market-neutral book rebalances to nothing (every name is under the
                                                    $5 floor at a zero stake) and the bear sleeve never takes a position
    cp.trend_poll -> no-op                          no trend book
    fb.K_DAILY = 0, fb.daily_entry -> False         no daily breakout book (it never buys; a zero-size buy would be noise)
    fb.K_CARRY = 1.0                                carry at TWICE the machine's x0.5 - the one registered change of weight
Everything else - capit2 at its 2x resting limit, the news and NASDAQ-dip books, the crash-bid ledger (none on BEAR days), the
carry book's +50% short exit, costs 12bp round trip, funding, the 10x account gate - is the machine's own code, byte for byte
(final_books.py, news_books.py, combo_bot.py), so this record measures the books, not a re-implementation of them.

WHY CARRY x1.0. On 2026-11-13 (main) and 2026-11-07 (fresh) the machine's carry rebalance came back EMPTY: final_books.py:459
drops a name whose stake K_CARRY x equity x 0.5 / n_longs is under Bitget's $5, and every name has the same stake, so the whole
basket goes - the one book that was making money (+$9.9 / +$16.3) switched itself off after a 20% fall. At x1.0 the stake is
$12.5 at $300 and the book stays on until equity falls under about $120. That is a weight change the backtest has not seen at
the deployed series' scale, so backtest/event_account_registered.py prices the exact set (carry x1.0 = twice the deployed carry
column; the series are linear in the weight) BEFORE the first live day.

THE FLOORS THAT REMAIN (Bitget's $5 minimum; read them as part of the record, not as faults):
    crash bids  equity / 40 per bid       off under $200 of equity   (and on every BEAR day, by design)
    carry       x1.0, 12 longs            off under about $120
    news        1/10 of equity a trade    off under about $50
    capit2      equity x 2 / 4 slots      off under about $10
    NASDAQ dip  the whole account at 1x   off under $5

PRE-REGISTERED 2026-11-27, BEFORE THE FIRST LIVE DAY (numbers named in docs/22-decision-rule.md s4c; the backtest claim is
logs/event_account_registered.txt)
    START    $300 paper, first poll after the service starts (the date is the first line of logs/combo_bot_dry_final_events/
             combo_paper.log, `started` in combo_state.json). Poll every 2 minutes like the machine.
    COMPARE  live equity (booked + open, the dashboard's number) against the backtest range of the same set over the same
             number of days (the 'Event books' scorecard, once built) and against the machine's own books on the same days.
    The lines (kill / verdict dates and percentages) are written in docs/22 s4c next to the backtest result they were taken from;
    they cannot move after the first live day.

    python event_bot.py            run it (the service does this: deploy/combo-bot-events.service)
    python event_bot.py --status   the machine's own status line for this account
    python event_bot.py --once     one poll, then stop
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

ACCOUNT = "events"
EVENT_BOOKS = ("carry", "capit2", "news", "ndx", "bids")
SWITCHED_OFF = ("trend", "mn", "sleeve", "daily", "crowd")
K_CARRY_EVENTS = 1.0
FORBIDDEN = ("--mode", "--final", "--account", "--crowd", "--wick", "--wick-dist", "--wick-cap", "--wick-usd")


def configure() -> dict:
    """Switch the non-event books off and set carry's weight, IN THIS PROCESS ONLY. Returns what it replaced (the tests
    restore it). Nothing on disk changes, and a process that never calls this - main, fresh, v2 - is exactly as before."""
    import combo_paper as cp
    import final_books as fb
    saved = dict(K_MN=cp.K_MN, K_SLEEVE=cp.K_SLEEVE, signal=cp.signal, trend_poll=cp.trend_poll,
                 K_DAILY=fb.K_DAILY, daily_entry=fb.daily_entry, K_CARRY=fb.K_CARRY)
    cp.K_MN = 0.0
    cp.K_SLEEVE = 0.0
    cp.signal = lambda *a, **k: 0                       # the bear sleeve never holds
    cp.trend_poll = lambda *a, **k: None                # no trend book
    fb.K_DAILY = 0.0
    fb.daily_entry = lambda c: False                    # the daily book never buys
    fb.K_CARRY = K_CARRY_EVENTS
    return saved


def restore(saved: dict):
    import combo_paper as cp
    import final_books as fb
    cp.K_MN, cp.K_SLEEVE, cp.signal, cp.trend_poll = saved["K_MN"], saved["K_SLEEVE"], saved["signal"], saved["trend_poll"]
    fb.K_DAILY, fb.daily_entry, fb.K_CARRY = saved["K_DAILY"], saved["daily_entry"], saved["K_CARRY"]


def argv_for(extra: list) -> list:
    """combo_bot's argv for this account. The mode, the machine, the account and the optional books are NOT the caller's to
    change: this process is a dry paper account of the event books and nothing else."""
    bad = [a for a in extra if a.split("=")[0] in FORBIDDEN]
    if bad:
        raise SystemExit(f"event_bot.py is fixed to --mode dry --final --account {ACCOUNT}; do not pass {' '.join(bad)}")
    return ["combo_bot.py", "--mode", "dry", "--final", "--account", ACCOUNT] + list(extra)


def main():
    sys.argv = argv_for(sys.argv[1:])
    import combo_bot as cb
    configure()
    cb.main()


if __name__ == "__main__":
    main()

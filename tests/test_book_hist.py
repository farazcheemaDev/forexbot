"""Offline tests for backtest/book_hist.py - the book rebuild and the tape's fill rule. No network, no real data.

    python tests/test_book_hist.py
"""
from __future__ import annotations

import gzip
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import book_hist as bh  # noqa: E402

HDR = "exchange,symbol,timestamp,local_timestamp,is_snapshot,side,price,amount\n"


def stream(rows):
    """rows: (t_ms, is_snapshot, side, price, amount) -> a gz file in a temp dir; returns its path."""
    d = Path(tempfile.mkdtemp())
    p = d / "l2.csv.gz"
    with gzip.open(p, "wt") as f:
        f.write(HDR)
        for t, s, side, price, amt in rows:
            f.write(f"x,DOGEUSDT,{t * 1000},{t * 1000},{'true' if s else 'false'},{side},{price},{amt}\n")
    return p


SNAP0 = [(0, True, "bid", 9.0, 5), (0, True, "bid", 8.0, 7), (0, True, "ask", 10.0, 4), (0, True, "ask", 11.0, 6)]


def test_updates_deletes_and_best_levels():
    rows = SNAP0 + [(1200, False, "bid", 9.5, 3),            # a new best bid
                    (2100, False, "bid", 9.5, 0),            # ... deleted again: best falls back to 9.0
                    (2200, False, "ask", 10.0, 0),           # the best ask goes: 11.0 becomes the touch
                    (3300, False, "bid", 8.0, 9)]            # a deeper level changes: the touch does not
    g, st = bh.rebuild(stream(rows))
    by = g.set_index("t")
    assert by.loc[1000, ["bid", "ask"]].tolist() == [9.0, 10.0]
    assert by.loc[2000, "bid"] == 9.5 and by.loc[2000, "bq1"] == 3      # the update stamped 1200 is in the 2 s sample
    assert by.loc[3000, ["bid", "ask", "ask"]].tolist() == [9.0, 11.0, 11.0]
    assert by.loc[3000, "aq1"] == 6 and st["crossed"] == 0


def test_a_row_on_the_boundary_belongs_to_that_second_and_the_next_row_does_not():
    rows = SNAP0 + [(2000, False, "bid", 9.2, 1), (2001, False, "bid", 9.4, 1), (3500, False, "bid", 9.4, 0)]
    g, _ = bh.rebuild(stream(rows))
    by = g.set_index("t")
    assert by.loc[2000, "bid"] == 9.2 and by.loc[3000, "bid"] == 9.4


def test_a_crossed_book_is_counted_and_not_sampled():
    rows = SNAP0 + [(1500, False, "bid", 10.5, 2), (2500, False, "bid", 10.5, 0), (4500, False, "bid", 9.0, 6)]
    g, st = bh.rebuild(stream(rows))
    assert st["crossed"] == 1 and 2000 not in set(g.t)
    assert {3000, 4000} <= set(g.t)                                      # after the crossing level is deleted the book is valid again


def test_reconnect_snapshot_replaces_the_book_and_is_compared_with_the_book_before_it():
    clean = SNAP0 + [(1500, False, "bid", 9.1, 2)]
    same = [(5000, True, "bid", 9.1, 2), (5000, True, "bid", 9.0, 5), (5000, True, "bid", 8.0, 7),
            (5000, True, "ask", 10.0, 4), (5000, True, "ask", 11.0, 6)]
    g, st = bh.rebuild(stream(clean + same + [(6200, False, "ask", 10.0, 0)]))
    assert st["blocks"] == 1 and st["block_match"] == 1                 # nothing was lost: the snapshot equals the rebuilt book
    lost = [(5000, True, "bid", 9.0, 5), (5000, True, "bid", 8.0, 7),    # the 9.1 bid cancelled and we never heard
            (5000, True, "ask", 10.0, 4), (5000, True, "ask", 11.0, 6)]
    g, st = bh.rebuild(stream(clean + lost + [(6200, False, "ask", 10.0, 0)]))
    assert st["blocks"] == 1 and st["block_match"] == 0 and g.set_index("t").loc[5000, "bid"] == 9.0


def test_imbalance_uses_dollars_on_the_top_levels():
    g, _ = bh.rebuild(stream(SNAP0 + [(2500, False, "bid", 9.0, 5)]))
    r = g.iloc[0]                                                       # bid $45 vs ask $40 at level 1
    assert abs(r.imb1 - (45 - 40) / 85) < 1e-12
    assert abs(r.imb5 - ((45 + 56) - (40 + 66)) / (45 + 56 + 40 + 66)) < 1e-12


# ------------------------------------------------------------------ the tape's fill rule
def tape(rows):
    return (np.array([r[0] for r in rows], dtype="int64"), np.array([r[1] for r in rows]),
            np.array([r[2] for r in rows], float), np.array([r[3] for r in rows], float))


def test_bid_fills_on_a_sell_through_it_not_on_a_buy_and_not_before_the_order():
    tt, sd, pr, q = tape([(100, "sell", 8.9, 1), (1200, "buy", 8.0, 5), (1300, "sell", 8.99, 1)])
    assert bh.maker_fill(tt, sd, pr, q, 1000, 9.0, 100, True) == 1300     # the 8.9 sell at t=100 is before the order; buys never fill a bid
    assert bh.maker_fill(tt, sd, pr, q, 1000, 8.99, 100, True) is None    # 8.99 is AT the bid: queue ahead 100 not cleared by 1


def test_queue_ahead_must_be_cleared_by_volume_at_the_price():
    tt, sd, pr, q = tape([(1100, "sell", 9.0, 40), (1200, "sell", 9.0, 40), (1300, "sell", 9.0, 40)])
    assert bh.maker_fill(tt, sd, pr, q, 1000, 9.0, 100, True) == 1300     # 40+40+40 >= 100 at the third print
    assert bh.maker_fill(tt, sd, pr, q, 1000, 9.0, 130, True) is None
    assert bh.maker_fill(tt, sd, pr, q, 1000, 9.0, 0, True) == 1100       # nobody ahead: the first print fills


def test_ask_mirrors_it_and_the_order_expires():
    tt, sd, pr, q = tape([(1100, "buy", 10.0, 5), (1200, "sell", 12.0, 5), (1300, "buy", 10.1, 1), (30000, "buy", 13.0, 9)])
    assert bh.maker_fill(tt, sd, pr, q, 1000, 10.0, 50, False) == 1300    # a buy ABOVE the ask fills it; the 5 at the price did not
    assert bh.maker_fill(tt, sd, pr, q, 1000, 12.5, 0, False) is None     # the buy through 12.5 is at 30 s: past the 10 s life
    assert bh.maker_fill(tt, sd, pr, q, 1000, 12.5, 0, False, ttl_ms=40_000) == 30000


def test_replay_one_long_filled_and_one_missed():
    t = np.arange(0, 60_000, 1000)
    f = bh.pd.DataFrame(dict(t=t, bid=9.0, ask=9.01, bq1=100.0, aq1=100.0, imb1=0.0, imb5=0.0, imb20=0.0, band10=0.0,
                             band25=0.0)).assign(mid=9.005)
    f.loc[f.t >= 20_000, ["bid", "ask", "mid"]] = [9.05, 9.06, 9.055]
    tr = bh.pd.DataFrame(dict(t=[1500], side=["sell"], price=[8.99], qty=[1.0]))   # trades through the 9.00 bid at 1.5 s
    sig = bh.pd.DataFrame(dict(t=[0, 40_000], d=[1, 1]))
    r = bh.replay(f, tr, sig, hold_s=10, qf=1.0, exit_mode="taker")
    assert r.filled.tolist() == [True, False]                           # the second long (t=40 s) has no tape: missed, net 0
    gross = (9.0 / 9.0 - 1) * 1e4                                       # exit at 11.5 s -> bid still 9.0: flat
    assert abs(r.net[0] - (gross - bh.MAKER_BP - bh.TAKER_BP)) < 1e-9 and r.net[1] == 0.0


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests pass")

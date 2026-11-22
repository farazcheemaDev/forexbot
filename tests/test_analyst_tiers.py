"""Tests for backtest/analyst_tiers.py (the Analyst desk's calls re-booked on small accounts).

Run as a script (no pytest on this PC):  python tests/test_analyst_tiers.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import analyst_tiers as at  # noqa: E402

BASE = 1_700_006_400_000          # 2023-11-15 00:00:00 UTC, a day boundary
H = 3_600_000


def row(i, made_h, exit_h, stop, r, status="WIN"):
    return dict(id=i, made_ms=BASE + made_h * H, exit_ms=None if exit_h is None else BASE + exit_h * H, symbol="BTCUSDT", side="long", method="SR",
                status=status, stop_pct=stop, target_pct=2 * stop, r=r, booked=True, nobook=False, pnl_usd=0.0)


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_sizing_and_pnl_by_hand():
    s = at.simulate([row(1, 0, 5, 0.02, 2.0)], 1000, 1.0)                  # risk $10; +2R = +$20 (the fee is already inside r_net)
    assert s["taken"] == 1 and near(s["equity"], 1020.0) and s["wins"] == 1 and near(s["ret"], 0.02)
    s = at.simulate([row(1, 0, 5, 0.02, -1.1, "LOSS")], 1000, 1.0)
    assert near(s["equity"], 989.0) and s["losses"] == 1 and near(s["worst"], -11.0) and near(s["maxdd"], 0.011)


def test_the_max_fall_is_measured_from_the_highest_equity_not_the_start():
    s = at.simulate([row(1, 0, 1, 0.02, 2.0), row(2, 2, 3, 0.02, -1.1, "LOSS")], 1000, 1.0)       # 1000 -> 1020 -> 1020 - 1.1 x 10.2
    assert near(s["equity"], 1020 - 11.22) and near(s["maxdd"], 11.22 / 1020)


def test_the_five_dollar_minimum_blocks_a_small_order():
    s = at.simulate([row(1, 0, 5, 0.019, 2.0)], 10, 0.5)                   # risk $0.05 / 1.9% = $2.63 notional: under $5
    assert s["small"] == 1 and s["taken"] == 0 and near(s["equity"], 10.0)
    s = at.simulate([row(1, 0, 5, 0.019, 2.0)], 10, 1.0)                   # $0.10 / 1.9% = $5.26: placeable
    assert s["small"] == 0 and s["taken"] == 1 and s["equity"] > 10.0


def test_the_three_times_cap():
    s = at.simulate([row(1, 0, 5, 0.002, 2.0)], 100, 1.0)                  # $1 risk / 0.2% = $500 notional against a $300 cap
    assert s["nobook"] == 1 and s["taken"] == 0 and near(s["equity"], 100.0)


def test_overlapping_calls_share_the_cap_and_a_later_call_is_free_again():
    a, b, c = row(1, 0, 10, 0.005, 1.0), row(2, 1, 12, 0.005, 1.0), row(3, 11, 15, 0.005, 1.0)   # $200 notional each on $100, cap $300
    s = at.simulate([a, b, c], 100, 1.0)
    assert s["nobook"] == 1 and s["taken"] == 2                            # b overlaps a (400 > 300); c is made after a exits
    assert at.simulate([a, row(2, 11, 15, 0.005, 1.0)], 100, 1.0)["taken"] == 2


def test_equity_moves_when_a_call_exits_including_the_same_instant():
    a = row(1, 0, 5, 0.01, 2.0)                                            # risk $1.00 -> +$2.00
    after = at.simulate([a, row(2, 6, 9, 0.01, 1.0)], 100, 1.0)            # sized on 102: risk 1.02, +1.02
    assert near(after["equity"], 100 + 2.0 + 1.02)
    before = at.simulate([a, row(2, 3, 9, 0.01, 1.0)], 100, 1.0)           # made while a is open: sized on 100, +1.00
    assert near(before["equity"], 100 + 2.0 + 1.0)
    same = at.simulate([a, row(2, 5, 9, 0.01, 1.0)], 100, 1.0)             # made at a's exit instant: the hourly cycle scores first
    assert near(same["equity"], 100 + 2.0 + 1.02)


def test_an_open_call_holds_cap_room_and_never_pays():
    o = row(1, 0, None, 0.005, None, "open")
    o["r"] = None
    s = at.simulate([o, row(2, 1, 5, 0.005, 1.0)], 100, 1.0)               # open call $200 + the next $200 > $300
    assert s["taken"] == 1 and s["nobook"] == 1 and s["still_open"] == 1 and near(s["equity"], 100.0)


def test_step_down_halves_risk_after_two_losses_and_a_win_restores_it():
    rows = [row(1, 0, 1, 0.01, -1.0, "LOSS"), row(2, 2, 3, 0.01, -1.0, "LOSS"), row(3, 4, 5, 0.01, 1.0), row(4, 6, 7, 0.01, 1.0)]
    fixed = at.simulate(rows, 1000, 1.0)["equity"]
    adapt = at.simulate(rows, 1000, 1.0, step_down=True)["equity"]
    e2 = 1000 - 10.0 - 9.9
    e3 = e2 + e2 * 0.005                                                   # third call at half risk
    e4 = e3 + e3 * 0.01                                                    # a win has reset the streak: full risk again
    assert near(adapt, e4) and adapt != fixed


def test_day_stop_pauses_after_a_losing_day_and_resumes_the_next_day():
    rows = [row(1, 1, 2, 0.01, -1.0, "LOSS"), row(2, 3, 4, 0.01, 1.0), row(3, 25, 26, 0.01, 1.0)]   # day 0: a loss then a call; day 1: a call
    free = at.simulate(rows, 1000, 1.0, day_stop=2.0)                      # the loss is 1% < 2%: nothing paused
    assert free["paused"] == 0 and free["taken"] == 3
    stop = at.simulate(rows, 1000, 1.0, day_stop=0.5)                      # 1% down >= 0.5% -> the second call of day 0 is skipped
    assert stop["paused"] == 1 and stop["taken"] == 2
    assert at.simulate([row(1, 1, 2, 0.01, 1.0)], 1000, 1.0, day_stop=0.5)["taken"] == 1      # a day with no loss is never paused


def test_mechanics_by_hand():
    m = at.mech(10, 1.0, 0.008)
    assert near(m["risk"], 0.1) and near(m["notional"], 12.5) and near(m["lev"], 1.25) and m["L"] == 2 and near(m["margin"], 6.25)
    assert near(m["fee"], 12.5 * 0.0012) and near(m["fee_r"], 0.0012 / 0.008) and near(m["liq"], 0.5 - 0.005)
    assert m["placeable"] and not m["capped"] and near(m["need_pct"], 5 * 0.008 / 10 * 100)
    assert not at.mech(10, 1.0, 0.03)["placeable"] and at.mech(100, 1.0, 0.002)["capped"]


def test_the_replay_reproduces_the_desks_own_book_on_the_saved_snapshot():
    rows = at.load(ROOT / "logs" / "analyst_calls_snapshot.csv")
    e, we, t, wt, nb, wnb = at.check(rows)
    assert abs(e - we) < 0.05 and t == wt and nb == wnb, (e, we, t, wt, nb, wnb)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")

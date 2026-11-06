"""Tests for backtest/analyst_sweetspot.py: the registered definition, the cutoff, the independent-bet unit and the pass bar.

Run as a script (no pytest on this PC):  python tests/test_analyst_sweetspot.py
"""
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.analyst_sweetspot as ss  # noqa: E402

REG = ss.REGISTERED_MS


def call(i, day="2026-11-10", side="long", stop=0.01, r=1.0, status="WIN", made=None, method="SMC", base=0.2):
    return dict(id=i, made_ms=REG + 3_600_000 * (i + 1) if made is None else made, day=day, side=side, method=method, status=status, stop_pct=stop, r=r, base=base)


def test_the_registration_instant_and_the_definition_are_the_registered_ones():
    assert ss.REGISTERED_UTC == "2026-11-06 15:00" and REG == 1793977200000
    assert ss.SWEET_STOP == 0.008 and ss.SCALP_STOP == 0.004
    assert (ss.MIN_BETS, ss.MIN_MEAN_R, ss.MIN_T) == (30, 0.15, 2.0)


def test_only_calls_made_at_or_after_the_registration_count_and_only_resolved_ones():
    rows = [call(1, made=REG - 1), call(2, made=REG), call(3, made=REG + 1, status="EXPIRED", r=-0.3), call(4, status="open", r=None)]
    fw = ss.resolved(ss.forward(rows))
    assert [r["id"] for r in fw] == [2, 3]                                   # the call one millisecond before is excluded; an expired call HAS an outcome; an open call has none


def test_the_sweet_spot_is_a_stop_of_at_least_0_8_percent_inclusive():
    rows = [call(1, stop=0.0079), call(2, stop=0.008), call(3, stop=0.05), call(4, stop=None)]
    assert [r["id"] for r in ss.sweet(rows)] == [2, 3]


def test_a_bet_is_one_day_and_one_side_and_is_valued_by_the_mean_of_its_calls():
    rows = [call(1, r=2.0), call(2, r=-1.0), call(3, r=1.0, side="short"), call(4, day="2026-11-11", r=-1.0, status="LOSS")]
    b = dict(ss.bets(rows))
    assert b[("2026-11-10", "long")] == 0.5 and b[("2026-11-10", "short")] == 1.0 and b[("2026-11-11", "long")] == -1.0
    assert [k for k, _ in ss.bets(rows)] == sorted(b)                        # date order (the halves are cut in this order)
    assert abs(st.mean(v for _, v in ss.bets(rows)) - (0.5 + 1.0 - 1.0) / 3) < 1e-12      # equal weight per bet, not per call


def test_t_is_the_mean_over_its_standard_error_and_undefined_below_three_bets():
    x = [0.5, 1.0, -1.0, 2.0]
    assert abs(ss.tstat(x) - st.mean(x) / (st.stdev(x) / 2.0)) < 1e-12
    assert ss.tstat([1.0, 2.0]) is None and ss.tstat([1.0, 1.0, 1.0]) is None


def test_the_verdict_needs_every_part_of_the_bar():
    ok = dict(n_bets=30, mean_r=0.2, t=2.5, hit=0.4, base=0.2, h1=0.1, h2=0.3)
    assert ss.verdict(**ok).startswith("PASS")
    assert ss.verdict(**{**ok, "n_bets": 29}).startswith("NOT YET")
    for k, v in (("mean_r", 0.149), ("t", 1.99), ("hit", 0.2), ("h1", 0.0), ("h2", -0.1)):
        assert ss.verdict(**{**ok, k: v}).startswith("NO PASS"), k
    assert ss.verdict(**{**ok, "t": None}).startswith("NO PASS")
    assert ss.verdict(**{**ok, "mean_r": 0.15, "t": 2.0}).startswith("PASS")          # the bar's own values pass: at least +0.15R and t at least 2.0
    assert ss.verdict(**{**ok, "hit": 0.2}).startswith("NO PASS") and ss.verdict(**{**ok, "h2": 0.0}).startswith("NO PASS")   # a hit rate equal to the random odds, or a flat half, does not


def test_score_runs_the_whole_chain_on_forward_sweet_spot_calls_only():
    rows = []
    for d in range(30):                                                       # 30 distinct winning days (+1R) ...
        rows.append(call(d, day=f"2026-12-{d + 1:02d}" if d < 30 else "", r=1.0 + (d % 3) * 0.1))
    rows.append(call(100, day="2026-12-01", stop=0.002, r=-5.0, status="LOSS"))   # a scalp-sized call: not in the sweet spot
    rows.append(call(101, made=REG - 5000, day="2026-11-01", r=9.0))              # made before the registration: not scored
    s = ss.score(rows)
    assert s["calls"] == 30 and s["bets"] == 30 and s["verdict"].startswith("PASS")
    assert abs(s["mean_r"] - st.mean(1.0 + (d % 3) * 0.1 for d in range(30))) < 1e-12
    assert s["hit"] == 1.0 and s["base"] == 0.2 and s["h1"] > 0 and s["h2"] > 0


def test_the_two_halves_are_the_first_and_the_last_half_of_the_bets_by_date():
    rows = [call(d, day=f"2026-12-{d + 1:02d}", r=1.0 if d < 15 else 0.2) for d in range(30)]
    s = ss.score(rows)
    assert s["bets"] == 30 and abs(s["h1"] - 1.0) < 1e-12 and abs(s["h2"] - 0.2) < 1e-12        # 15 and 15, in date order


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")

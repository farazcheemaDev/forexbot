"""Offline tests for backtest/analyst_review.py - the arithmetic of the review (fees in R, excursions, re-scoring under other brackets).

    python tests/test_analyst_review.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import analyst_review as ar  # noqa: E402

MIN = 60_000


def bars(spec, t0=1_000_000 * MIN):
    """spec = [(open, high, low, close), ...] one per minute from t0."""
    return [(t0 + i * MIN, o, h, l, c) for i, (o, h, l, c) in enumerate(spec)]


def call(side="long", entry=100.0, stop_pct=0.01, rr=2.0, expires_min=100):
    t0 = 1_000_000 * MIN
    sgn = 1 if side == "long" else -1
    return dict(id="1", symbol="TESTUSDT", side=side, mode="market", entry=entry, stop=entry * (1 - sgn * stop_pct),
                target=entry * (1 + sgn * stop_pct * rr), stop_pct=stop_pct, target_pct=stop_pct * rr, rr=rr,
                expires_ms=t0 + expires_min * MIN, made_ms=t0 - MIN, status="open")


def test_the_fee_in_r_and_the_gross_result():
    assert abs(ar.fee_r(0.008066) - 0.0012 / 0.008066) < 1e-12
    assert abs(ar.fee_r(0.0015) - 0.8) < 1e-12                       # a 0.15% stop pays 0.8R of fee on every call
    r = dict(r_net=-1.148766, stop_pct=0.008066)
    assert abs(ar.gross_r(r) + 1.0) < 1e-3                           # a stop-out is -1R before the fee
    w = dict(r_net=1.4449, stop_pct=0.007398)
    assert abs(ar.gross_r(w) - 1.607) < 1e-2                         # a target hit is +RR before the fee


def test_excursions_are_measured_in_the_calls_direction_and_only_up_to_the_end():
    b = bars([(100, 101, 99, 100), (100, 103, 98, 102), (102, 110, 90, 100)])
    mfe, mae = ar.excursions("long", 100.0, b, b[1][0])
    assert abs(mfe - 0.03) < 1e-12 and abs(mae - 0.02) < 1e-12        # the third bar (after the end) is not counted
    mfe, mae = ar.excursions("short", 100.0, b, b[1][0])
    assert abs(mfe - 0.02) < 1e-12 and abs(mae - 0.03) < 1e-12
    assert ar.excursions("long", 100.0, [], 0) == (0.0, 0.0)


def test_does_price_reach_the_target_after_the_stop():
    b = bars([(100, 100, 99, 99.5), (99.5, 100, 99, 99.5), (99.5, 101, 99.4, 100.5), (100.5, 106, 100, 105)])
    t_exit = b[1][0]
    assert abs(ar.later_reaches_target("long", 100.0, 105.0, b, t_exit, b[3][0]) - 2.0) < 1e-12        # the 105 target is touched 2 minutes after the exit
    assert ar.later_reaches_target("long", 100.0, 105.0, b, t_exit, b[2][0]) is None                  # the call expired first
    assert ar.later_reaches_target("long", 100.0, 120.0, b, t_exit, b[3][0]) is None
    s = bars([(100, 100, 99.5, 99.8), (99.8, 100, 97, 98), (98, 99, 97.5, 98.5)])
    assert ar.later_reaches_target("short", 100.0, 98.0, s, s[0][0], s[2][0]) == 1.0                   # a short's target is below


def test_the_stop_that_would_have_survived_is_the_worst_move_against_the_position():
    b = bars([(100, 100.5, 99.8, 100), (100, 101, 97.5, 98), (98, 104, 97, 103)])
    assert abs(ar.stop_that_would_have_survived("long", 100.0, b, b[0][0], b[1][0]) - 0.025) < 1e-12      # to bar 1: 97.5
    assert abs(ar.stop_that_would_have_survived("long", 100.0, b, b[0][0], b[2][0]) - 0.03) < 1e-12       # to bar 2: 97
    assert abs(ar.stop_that_would_have_survived("short", 100.0, b, b[0][0], b[2][0]) - 0.04) < 1e-12      # against a short: the 104 high


def test_rescoring_under_a_wider_stop_and_a_nearer_target():
    c = call()                                                       # stop 99, target 102
    b = bars([(100, 100.2, 98.8, 99.0), (99.0, 99.5, 98.5, 99.2), (99.2, 102.5, 99.1, 102.2)])
    base = ar.rescore(c, b, now=10 ** 15)
    assert base["status"] == "LOSS" and abs(base["exit_price"] - 99.0) < 1e-9                     # stopped in the first minute
    wide = ar.rescore(c, b, stop_mult=2.0, now=10 ** 15)                                          # stop 98: survives the 98.5 low
    assert wide["status"] == "WIN" and abs(wide["exit_price"] - 102.0) < 1e-9
    near = ar.rescore(c, bars([(100, 100.2, 99.5, 100.1), (100.1, 101.2, 100.0, 101.0)]), target_r=1.0, now=10 ** 15)   # target 101
    assert near["status"] == "WIN" and abs(near["exit_price"] - 101.0) < 1e-9
    sh = call(side="short")                                          # stop 101, target 98
    s = bars([(100, 100.5, 99.5, 100), (100, 100.8, 97.5, 98)])
    out = ar.rescore(sh, s, now=10 ** 15)
    assert out["status"] == "WIN" and abs(ar.trade_gross(out) - 0.02) < 1e-9                       # a short's gross return is positive when price falls
    assert ar.rescore(c, bars([(100, 100.2, 99.5, 100.0)]), now=0) is None                         # still open: no result


def test_mean_standard_error_and_the_buckets():
    m, se = ar.mean_se([1.0, 2.0, 3.0, 4.0])
    assert abs(m - 2.5) < 1e-12 and abs(se - (1.2909944487358056 / 2)) < 1e-12
    assert ar.mean_se([5.0])[0] == 5.0 and ar.mean_se([5.0])[1] != ar.mean_se([5.0])[1]
    assert ar.bucket_rr(2.5) == "RR <= 2.5" and ar.bucket_rr(3.0) == "RR 2.5-4" and ar.bucket_rr(4.01) == "RR > 4"
    assert ar.bucket_stop(0.0039) == "stop < 0.4%" and ar.bucket_stop(0.006) == "stop 0.4-0.8%" and ar.bucket_stop(0.008) == "stop >= 0.8%"


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests pass")

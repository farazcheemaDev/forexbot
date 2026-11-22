"""Tests for backtest/wall_persistence.py (the wall-persistence study, Step 1 of the v2 order-book spec).

Run as a script (no pytest on this PC):  python tests/test_wall_persistence.py
"""
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import wall_persistence as wp  # noqa: E402

K = wp.K
TICK = 0.01


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(b))


def lv(base_q=100.0, wall_k=None, wall_q=None, p0=100.0, down=True, l1=None):
    """15 levels of one side: prices p0, p0 -/+ tick ...; quantity base_q everywhere, wall_q at index wall_k, l1 at index 0."""
    step = -TICK if down else TICK
    prices = np.array([p0 + k * step for k in range(K)])
    q = np.full(K, base_q)
    if wall_k is not None:
        q[wall_k] = wall_q
    if l1 is not None:
        q[0] = l1
    return prices, q


def flat_ctx(n=400, trades=(), bid=100.0):
    T = (np.arange(n) * 1000).astype("int64")
    BP = np.tile(bid - TICK * np.arange(K), (n, 1))
    AP = np.tile(bid + TICK + TICK * np.arange(K), (n, 1))
    BQ, AQ = np.full((n, K), 100.0), np.full((n, K), 100.0)
    tr = sorted(trades)
    tt = np.array([t for t, *_ in tr], dtype="int64")
    ts = np.array([s for _, s, _, _ in tr], dtype=object)
    tp = np.array([p for _, _, p, _ in tr], dtype=float)
    tq = np.array([q for _, _, _, q in tr], dtype=float)
    return wp.make_ctx(T, BP, BQ, AP, AQ, tt, ts, tp, tq, tick=TICK)


# ---------------------------------------------------------------- registry
def test_the_registered_numbers_are_pinned():
    assert wp.registry_digest() == wp.REGISTRY_SHA256


# ---------------------------------------------------------------- the tracker
def test_the_registered_cutoff_decides_what_is_a_wall():
    t = wp.WallTracker(True)
    p, q = lv(wall_k=3, wall_q=1000.0)                       # mean + 2.5 sd = 721 here: 1000 is a wall
    t.update(1000, p, q, {}, None)
    assert len(t.walls) == 1 and near(list(t.walls)[0], p[3])
    t2 = wp.WallTracker(True)
    p, q = lv(wall_k=3, wall_q=300.0)                        # 300 < 3.5 x the median (350): not a wall
    t2.update(1000, p, q, {}, None)
    assert not t2.walls


def make_wall(side_bid=True, q=3000.0, k=3):
    t = wp.WallTracker(side_bid)
    p, qq = lv(wall_k=k, wall_q=q, down=side_bid, p0=100.0 if side_bid else 100.01)
    t.update(1000, p, qq, {}, None)
    return t, p, qq, p[k]


def test_trades_that_eat_a_wall_do_not_make_it_a_pull_on_either_side():
    for bid in (True, False):
        t, p, q, wpx = make_wall(bid)
        q2 = q.copy()
        q2[3] = 1500.0
        t.update(2000, p, q2, {wpx: 1500.0}, None)           # 1500 contracts of taker volume at the wall's price
        w = t.walls[wpx]
        assert near(w.pulled, 0.0) and w.invalid_at is None


def test_a_wall_that_shrinks_with_no_trades_is_a_pull_and_becomes_invalid():
    t, p, q, wpx = make_wall()
    q2 = q.copy()
    q2[3] = 1800.0                                           # 1200 of 3000 gone, no trades: 40% >= 35%
    t.update(2000, p, q2, {}, None)
    w = t.walls[wpx]
    assert near(w.pulled, 1200.0) and w.invalid_at == 2000
    assert t.valid(30_000, p[0]) is None


def test_the_cancel_ratio_boundary_is_inclusive_and_below_it_stays_valid():
    t, p, q, wpx = make_wall()
    q2 = q.copy()
    q2[3] = 3000.0 * 0.70                                    # 30% pulled: still valid
    t.update(2000, p, q2, {}, None)
    assert t.walls[wpx].invalid_at is None
    q3 = q.copy()
    q3[3] = 3000.0 * 0.65                                    # 35% pulled in total: invalid (>=)
    t.update(3000, p, q3, {}, None)
    assert t.walls[wpx].invalid_at == 3000


def test_a_sweep_through_the_wall_is_not_a_pull_on_either_side():
    for bid, through in ((True, 99.0), (False, 101.0)):
        t, p, q, wpx = make_wall(bid)
        q2 = q.copy()
        q2[3] = 0.0
        t.update(2000, p, q2, {}, through)                   # taker trades beyond the wall's price: the level was swept
        assert wpx not in t.walls and not any(w.invalid_at for w in t.history)


def test_a_pulled_wall_that_is_still_big_is_not_registered_again():
    t, p, q, wpx = make_wall()
    q2 = q.copy()
    q2[3] = 1800.0
    t.update(2000, p, q2, {}, None)
    t.update(3000, p, q2, {}, None)
    assert len(t.history) == 1 and t.history[0].invalid_at == 2000


def test_a_level_that_leaves_the_window_is_not_a_pull():
    t, p, q, wpx = make_wall()
    p2, q2 = lv(p0=p[0] + 12 * TICK)                          # the book moved up 12 ticks: the old wall's price (index 3) is now below the 15-level window
    assert p2.min() > wpx                                     # (a 4-tick move would leave it inside the window, where its missing size WOULD be a pull)
    t.update(2000, p2, q2, {}, None)
    assert wpx not in t.walls and t.history[0].invalid_at is None and t.history[0].dead_at == 2000


def test_valid_needs_age_distance_and_no_pull():
    t, p, q, wpx = make_wall(k=3)
    best = p[0]
    assert t.valid(1000 + 19_999, best) is None              # 19.999 s old
    assert t.valid(1000 + 20_000, best) is not None          # exactly 20 s: valid
    far, pf, qf, wf = make_wall(k=14)                         # 14 ticks = about 14 bp behind the touch
    assert far.valid(1000 + 30_000, pf[0]) is None
    near_, pn, qn, wn = make_wall(k=0)                        # the wall IS the touch: distance 0 is allowed
    got = near_.valid(1000 + 30_000, pn[0])
    assert got is not None and near(got[0], 0.0)


# ---------------------------------------------------------------- scan: the signal rule
def scan_ctx(n=60, wall_bid=True, imb_bq=300.0, imb_aq=40.0, trades=(), both=False):
    c = flat_ctx(n, trades)
    BP, BQ, AP, AQ = c["BP"], c["BQ"].copy(), c["AP"], c["AQ"].copy()
    BQ[:, 0], AQ[:, 0] = imb_bq, imb_aq
    if wall_bid or both:
        BQ[:, 3] = 3000.0
    if (not wall_bid) or both:
        AQ[:, 3] = 3000.0
    return wp.make_ctx(c["T"], BP, BQ, AP, AQ, c["tt"], c["ts"], c["tp"], c["tq"], tick=TICK)


def test_a_bid_wall_with_strong_bid_imbalance_signals_a_long_after_twenty_seconds():
    sigs, walls = wp.scan(scan_ctx())
    assert sigs and all(s["d"] == 1 for s in sigs) and sigs[0]["t"] == 21_000          # registered at 1 s, valid at 21 s
    assert near(sigs[0]["wall"].px, 100.0 - 3 * TICK)


def test_imbalance_below_the_threshold_gives_no_signal_and_the_wrong_sign_gives_the_other_side():
    assert wp.scan(scan_ctx(imb_bq=300.0, imb_aq=100.0))[0] == []                      # imbalance +0.5 < 0.6
    assert wp.scan(scan_ctx(wall_bid=True, imb_bq=40.0, imb_aq=300.0))[0] == []         # ask-heavy with only a BID wall: nothing
    sigs, _ = wp.scan(scan_ctx(wall_bid=False, imb_bq=40.0, imb_aq=300.0))
    assert sigs and all(s["d"] == -1 for s in sigs)


def test_walls_on_both_sides_eaten_only_by_trades_both_stay_valid_in_a_full_scan():
    # a second at 24-25 s: 1,500 contracts sold at the bid wall's price and 1,500 bought at the ask wall's price; both walls shrink to 1,500
    c0 = scan_ctx(n=60, both=True)
    bpx, apx = float(c0["BP"][0, 3]), float(c0["AP"][0, 3])
    tr = [(24_500, "sell", bpx, 1500.0), (24_600, "buy", apx, 1500.0)]
    c = scan_ctx(n=60, both=True, trades=tr)
    c["BQ"][25:, 3] = 1500.0
    c["AQ"][25:, 3] = 1500.0
    _, walls = wp.scan(c)
    assert len(walls) == 2 and all(w.invalid_at is None for w in walls)
    c2 = scan_ctx(n=60, both=True)                                                      # the same shrink with NO trades is a pull on both
    c2["BQ"][25:, 3] = 1500.0
    c2["AQ"][25:, 3] = 1500.0
    _, walls2 = wp.scan(c2)
    assert len(walls2) == 2 and all(w.invalid_at is not None for w in walls2)


def test_a_sweep_seen_by_the_scan_uses_the_most_aggressive_trade_price_on_each_side():
    c0 = scan_ctx(n=60, both=True)
    bpx, apx = float(c0["BP"][0, 3]), float(c0["AP"][0, 3])
    tr = [(24_500, "sell", bpx, 10.0), (24_600, "sell", bpx - TICK, 5.0), (24_700, "buy", apx, 10.0), (24_800, "buy", apx + TICK, 5.0)]
    c = scan_ctx(n=60, both=True, trades=tr)
    c["BQ"][25:, 3] = 0.0                                                               # both walls vanish in the same second that trades went THROUGH them
    c["AQ"][25:, 3] = 0.0
    _, walls = wp.scan(c)
    assert len(walls) == 2 and all(w.invalid_at is None for w in walls)


# ---------------------------------------------------------------- the quote
def test_the_quote_is_one_tick_in_front_of_the_wall_never_beyond_the_touch():
    c = flat_ctx()
    q, qa, off = wp.quote_for(c, 10, 1, wall_px=99.97)
    assert near(q, 99.98) and off == 2 and near(qa, 100.0)
    q, qa, off = wp.quote_for(c, 10, 1, wall_px=100.0)                                  # the wall is the touch: join it, do not cross
    assert near(q, 100.0) and off == 0
    q, qa, off = wp.quote_for(c, 10, -1, wall_px=100.04)                                # ask side: best ask 100.01, wall 3 ticks behind
    assert near(q, 100.03) and off == 2
    q, qa, off = wp.quote_for(c, 10, -1, wall_px=100.01)
    assert near(q, 100.01) and off == 0
    q, qa, off = wp.quote_for(c, 10, 1, offset_ticks=3)                                 # a control: 3 ticks behind the touch
    assert near(q, 99.97) and off == 3
    q, qa, off = wp.quote_for(c, 10, -1, offset_ticks=3)
    assert near(q, 100.04) and off == 3


# ---------------------------------------------------------------- the fill and the bracket, by hand
def run_long(trades, cancel_ms=None, q_ahead=50.0, bp=8.0, mut=None):
    c = flat_ctx(400, trades)
    if mut:
        mut(c)
    return wp.attempt(c, 10, 1, 100.0, q_ahead, cancel_ms, bp, bp)


FILL = (10_600, "sell", 100.0, 60.0)             # 60 sold at 100.00 clears the 50 ahead of us: filled at 10.6 s


def test_a_queue_is_cleared_before_a_bid_fills_and_a_through_trade_fills_at_once():
    assert not run_long([(10_600, "sell", 100.0, 40.0)])["filled"]                       # 40 < 50 ahead
    assert run_long([FILL])["filled"]
    r = run_long([(10_600, "sell", 99.99, 1.0)])                                         # a sell below our price: the level was cleared
    assert r["filled"] and r["t_fill"] == 10_600
    assert not run_long([(10_400, "sell", 99.99, 1.0)])["filled"]                        # before the order reached the book (10.5 s)


def test_a_cancel_before_the_order_is_live_or_before_the_fill_leaves_it_unfilled():
    assert not run_long([FILL], cancel_ms=10_400)["filled"]
    assert not run_long([FILL], cancel_ms=10_550)["filled"]                              # cancelled at 10.55 s, fill at 10.6 s
    assert run_long([FILL], cancel_ms=10_700)["filled"]


def test_target_net_of_fees_by_hand():
    r = run_long([FILL, (12_000, "buy", 100.09, 5.0)])                                   # tp = 100.08: a buy through it fills the maker target
    assert r["kind"] == "target" and near(r["gross"], 8.0, 1e-6) and near(r["net"], 8.0 - 1.5 - 1.5, 1e-6) and r["end_ms"] == 12_000


def test_stop_is_a_taker_exit_at_the_touch_half_a_second_after_the_trigger():
    def drop(c):
        c["BP"][13:, 0] = 99.90
    r = run_long([FILL, (12_000, "sell", 99.90, 5.0)], mut=drop)                         # stop = 99.92: a sell at 99.90 triggers at 12.0 s
    assert r["kind"] == "stop" and near(r["gross"], -10.0, 1e-6) and near(r["net"], -10.0 - 1.5 - 4.5, 1e-6) and r["end_ms"] == 12_500


def test_a_stop_and_a_target_in_the_same_millisecond_count_as_the_stop():
    def drop(c):
        c["BP"][13:, 0] = 99.90
    r = run_long([FILL, (12_000, "buy", 100.09, 5.0), (12_000, "sell", 99.90, 5.0)], mut=drop)
    assert r["kind"] == "stop"


def test_scratch_at_ninety_seconds_is_a_maker_exit_at_the_touch():
    r = run_long([FILL, (105_600, "buy", 100.02, 1.0)])                                  # scratch ask 100.01 posted at 101.1 s; a buy through it fills
    assert r["kind"] == "scratch" and near(r["gross"], 1.0, 1e-6) and near(r["net"], 1.0 - 1.5 - 1.5, 1e-6)


def test_the_forced_exit_at_one_hundred_twenty_seconds_is_a_taker_at_the_bid():
    r = run_long([FILL])
    assert r["kind"] == "timeout" and near(r["gross"], 0.0, 1e-6) and near(r["net"], -6.0, 1e-6) and r["end_ms"] == 131_100


def test_a_short_is_the_mirror_image():
    c = flat_ctx(400, [(10_600, "buy", 100.01, 60.0), (12_000, "sell", 99.92, 5.0)])
    r = wp.attempt(c, 10, -1, 100.01, 50.0, None, 8.0, 8.0)                              # tp = 100.01 x (1 - 8bp) = 99.93: a sell through it
    assert r["filled"] and r["kind"] == "target" and near(r["gross"], 8.0, 1e-6) and near(r["net"], 5.0, 1e-6)


def test_the_entry_is_cancelled_when_the_mid_runs_ten_bp_away():
    c = flat_ctx(400)
    c["mid"][15:] = 100.0 * (1 + 11e-4)                                                  # 11 bp above the bid from 15 s on
    assert wp.away_cancel_ms(c, 10, 1, 100.0) == 15_000
    assert wp.away_cancel_ms(c, 10, -1, 100.0) is None                                   # for a short the same move is not 'away from the ask' in this sense
    c["mid"][15:] = 100.0 * (1 - 11e-4)
    assert wp.away_cancel_ms(c, 10, -1, 100.0) == 15_000


# ---------------------------------------------------------------- the scheduler and the controls
def test_one_attempt_per_wall_one_position_at_a_time_and_a_cooldown():
    c = flat_ctx(400)
    w1, w2, w3, w4 = (wp.Wall(99.97, 0, 3000.0) for _ in range(4))
    sigs = [dict(i=10, t=10_000, d=1, wall=w1), dict(i=11, t=11_000, d=1, wall=w1),     # the same wall again
            dict(i=12, t=12_000, d=1, wall=w2),                                          # a new wall while the first attempt is working
            dict(i=50, t=50_000, d=1, wall=w3),                                          # after it ended (40.5 s) but inside the 15 s cooldown
            dict(i=200, t=200_000, d=1, wall=w1),                                        # free again, but this wall has had its attempt
            dict(i=300, t=300_000, d=1, wall=w4)]
    out = wp.run_signals(c, sigs, 8.0, 8.0)
    assert [r["t"] for r in out] == [10_000, 300_000] and out[0]["offset"] == 2 and near(out[0]["wall_age_s"], 10.0)


def test_a_pulled_wall_cancels_the_working_entry():
    c = flat_ctx(400, [FILL])
    w = wp.Wall(99.97, 0, 3000.0)
    w.invalid_at = 10_550
    out = wp.run_signals(c, [dict(i=10, t=10_000, d=1, wall=w)], 8.0, 8.0)
    assert len(out) == 1 and not out[0]["filled"] and out[0]["end_ms"] == 10_550


def test_controls_use_the_same_side_the_same_distance_and_a_nearby_time_never_the_same_second():
    c = flat_ctx(2000)
    seen = []
    real = wp.attempt
    wp.attempt = lambda ctx, i0, d, quote, qa, cm, tp, sl: seen.append((i0, d, quote)) or dict(filled=False)
    try:
        wp.run_controls(c, [dict(i=500, d=1, offset=3), dict(i=900, d=-1, offset=2)], 8.0, 8.0, np.random.default_rng(7))
    finally:
        wp.attempt = real
    assert len(seen) == 2 * wp.N_CONTROLS
    for i0, d, quote in seen[:wp.N_CONTROLS]:
        assert i0 != 500 and abs(i0 - 500) <= wp.CONTROL_WINDOW_S and d == 1 and near(quote, 100.0 - 3 * TICK)
    for i0, d, quote in seen[wp.N_CONTROLS:]:
        assert i0 != 900 and abs(i0 - 900) <= wp.CONTROL_WINDOW_S and d == -1 and near(quote, 100.01 + 2 * TICK)


# ---------------------------------------------------------------- statistics and the registered rule
def sig(filled=100, gross=6.0, net=2.0, sd=10.0):
    return dict(filled=filled, gross=gross, net=net, gross_sd=sd)


def test_the_excess_t_by_hand_and_the_control_counts_as_filled_over_five():
    t = wp.excess_t(sig(100, 6.0, 2.0, 10.0), sig(500, 1.0, -3.0, 10.0))              # controls: 500 / 5 = 100 effective; se = sqrt(1 + 1)
    assert near(t, 5.0 / 2 ** 0.5)
    assert wp.excess_t(sig(1), sig(500)) == 0.0


def test_the_registered_rule_needs_every_condition():
    ctl = sig(500, 1.0, -3.0, 10.0)
    assert wp.passes(sig(100, 6.0, 2.0), ctl)
    assert not wp.passes(sig(29, 6.0, 2.0), ctl)                                         # too few filled trades
    weak_ctl = sig(500, -5.0, -9.0, 10.0)                                                # so weak that only the gross bar can fail below
    assert wp.passes(sig(100, 6.0, 2.0), weak_ctl)
    assert not wp.passes(sig(100, 3.0, 2.0), weak_ctl)                                   # gross under +4.5 bp
    assert not wp.passes(sig(100, 6.0, -0.5), ctl)                                       # net not positive
    assert not wp.passes(sig(100, 6.0, 2.0), sig(500, 5.5, 2.0, 10.0))                   # barely beats its controls


def test_holm_by_hand_and_the_summary():
    assert [round(x, 6) for x in wp.holm([0.01, 0.04, 0.03, 0.2])] == [0.04, 0.09, 0.09, 0.2]
    s = wp.summarize([dict(filled=True, gross=6.0, net=2.0, kind="target"), dict(filled=True, gross=-4.0, net=-8.0, kind="stop"),
                      dict(filled=False, gross=0.0, net=0.0, kind="unfilled")])
    assert s["attempts"] == 3 and s["filled"] == 2 and near(s["fill_rate"], 2 / 3) and near(s["gross"], 1.0) and near(s["net"], -3.0) and near(s["win"], 0.5)


def test_the_tick_is_inferred_from_the_touch_prices():
    BP = np.array([[100.00], [99.99], [99.97]]); AP = np.array([[100.01], [100.00], [99.98]])
    assert near(wp.infer_tick(BP, AP), 0.01)


def test_the_confirm_half_is_refused_unless_the_tune_half_passed():
    keep_log, keep_argv = wp.LOG, sys.argv
    with tempfile.TemporaryDirectory() as d:
        wp.LOG = Path(d) / "log.txt"
        wp.LOG.write_text("The tune half FAILS the registered rule: KILL.\n", encoding="utf-8")
        sys.argv = ["x", "--confirm"]
        try:
            try:
                wp.main()
                raise AssertionError("the confirm half ran after a failed tune half")
            except SystemExit as e:
                assert "refused" in str(e)
        finally:
            wp.LOG, sys.argv = keep_log, keep_argv


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")

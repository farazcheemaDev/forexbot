"""analyst.py offline: synthetic candles, a temp folder, no network. Run as a script: python tests/test_analyst.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import analyst as an  # noqa: E402
import desk  # noqa: E402

H1, H4, D1, MIN = 3_600_000, 14_400_000, 86_400_000, 60_000
NOW = 1_800_000_000_000 // H1 * H1 + 7 * MIN                     # seven minutes past an hour, like the timer


def tri_wave(n, lo, hi, period, t0, width):
    """A triangle wave with a spike at each peak and trough so every pivot is strict: highs hi+1.2, lows lo-1.2."""
    half, out = period // 2, []

    def x(i):
        ph = i % period
        return lo + (hi - lo) * (ph / half if ph <= half else (period - ph) / half)
    for i in range(n):
        o, c = x(i), x(i + 1)
        h, l = max(o, c) + 0.2, min(o, c) - 0.2
        if i % period == half - 1 or i % period == half:
            h = max(h, hi + 1.2) if i % period == half else h
        if i % period == half:
            h = hi + 1.2
        if i % period == 0:
            l = lo - 1.2
        out.append((t0 + i * width, o, h, l, c))
    return out


def ramp_bars(closes, t0, width):
    out, prev = [], closes[0]
    for i, c in enumerate(closes):
        out.append((t0 + i * width, prev, max(prev, c) + 0.2, min(prev, c) - 0.2, c))
        prev = c
    return out


def flat_bars(n, mid, rng, t0, width):
    return [(t0 + i * width, mid, mid + rng / 2, mid - rng / 2, mid) for i in range(n)]


def lin(a, b, n):
    return [a + (b - a) * (k + 1) / n for k in range(n)]


def sr_world():
    """4h and daily waves between 100 and 120 (many touches at 98.8 / 121.2); 1h flat near 105 with a wide range; the caller sets the last 1h bar."""
    h4 = tri_wave(300, 100, 120, 20, NOW - 300 * H4, H4)
    d1 = tri_wave(200, 100, 120, 20, NOW - 200 * D1, D1)
    h1 = flat_bars(120, 105.0, 1.0, NOW - 120 * H1, H1)
    return h1, h4, d1


def test_pivots_cluster_and_levels_find_the_strong_support_and_resistance():
    h1, h4, d1 = sr_world()
    lv = an.sr_levels(h4, d1)
    sup = [x for x in lv if x["price"] < 110]
    res = [x for x in lv if x["price"] > 110]
    assert sup and res
    s = max(sup, key=lambda x: x["touches"])
    r = max(res, key=lambda x: x["touches"])
    assert abs(s["price"] - 98.8) < 0.5 and s["touches"] >= 3, s
    assert abs(r["price"] - 121.2) < 0.5 and r["touches"] >= 3, r
    assert an.cluster([(100.0, 1), (100.2, 2), (110.0, 3)], 0.5)[0]["touches"] == 2
    assert len(an.cluster([(100.0, 1), (101.0, 2)], 0.5)) == 2          # two zones further apart than the tolerance stay two


def test_sr_bounce_fires_on_a_wick_from_a_strong_support_and_not_when_the_bar_closes_below_it():
    h1, h4, d1 = sr_world()
    t = NOW - H1
    good = h1[:-1] + [(t, 100.9, 101.2, 98.9, 101.0)]
    sig = [s for s in an.signals("TESTUSDT", good, h4, d1, 101.0) if s["method"] == "SR"]
    assert len(sig) == 1 and sig[0]["side"] == "long", sig
    s = sig[0]
    assert s["stop"] < 98.8 and abs(s["target"] - 121.2) < 0.5 and s["entry"] == 101.0
    below = h1[:-1] + [(t, 100.0, 100.2, 98.0, 98.2)]                     # closes under the support
    assert not [x for x in an.signals("TESTUSDT", below, h4, d1, 98.2) if x["method"] == "SR" and x["side"] == "long"]
    nowick = h1[:-1] + [(t, 98.95, 101.6, 98.9, 101.5)]                    # reaches the level but with no lower wick to speak of
    assert not [x for x in an.signals("TESTUSDT", nowick, h4, d1, 101.5) if x["method"] == "SR" and x["side"] == "long"]


def test_sr_ignores_a_close_below_the_level_even_with_a_long_wick_and_a_level_with_only_two_touches():
    h1, h4, d1 = sr_world()
    t = NOW - H1
    under = h1[:-1] + [(t, 98.7, 98.8, 97.8, 98.5)]                        # a long lower wick, but the bar CLOSES under the 98.8 support
    assert not [x for x in an.signals("TESTUSDT", under, h4, d1, 98.9) if x["method"] == "SR" and x["side"] == "long"]
    two = ramp_bars([110.0] * 30 + lin(110, 100, 3) + lin(100, 110, 3) + [110.0] * 120 + lin(110, 100, 3) + lin(100, 110, 3) + [110.0] * 130,
                    NOW - 292 * H4, H4)
    two = [(t, o, h, 98.8 if abs(c - 100.0) < 1e-9 else l, c) for (t, o, h, l, c) in two]      # a distinct spike low at each of the two dips
    for k in (80, 220):                                                                          # two spike highs: a resistance to aim at, also 2 touches
        t, o, h, l, c = two[k]
        two[k] = (t, o, 121.2, l, c)
    dflat = flat_bars(200, 110.0, 1.0, NOW - 200 * D1, D1)
    lv = an.sr_levels(two, dflat)
    assert lv and max(x["touches"] for x in lv if x["price"] < 105) == 2, lv     # the support exists but has two touches only
    bounce = h1[:-1] + [(t, 100.9, 101.2, 98.9, 101.0)]                    # the same clean bounce bar that fires at a 3+ touch support
    assert not [x for x in an.signals("TESTUSDT", bounce, two, dflat, 101.0) if x["method"] == "SR"], "a 2-touch level must not fire"


def test_sr_rejection_short_mirrors_the_bounce():
    h1, h4, d1 = sr_world()
    t = NOW - H1
    bars = h1[:-1] + [(t, 119.4, 121.1, 119.2, 119.5)]                     # touches the 121.2 resistance, closes well below with an upper wick
    sig = [s for s in an.signals("TESTUSDT", bars, h4, d1, 119.5) if s["method"] == "SR" and s["side"] == "short"]
    assert len(sig) == 1 and sig[0]["stop"] > 121.2 and sig[0]["target"] < 119.5, sig


def test_fib_pullback_long_in_the_50_to_786_zone_and_not_outside_it():
    h4 = ramp_bars([100.0] * 25 + lin(100, 120, 15) + lin(120, 107.6, 15) + [107.6] * 25, NOW - 80 * H4, H4)
    d1 = tri_wave(200, 100, 120, 20, NOW - 200 * D1, D1)
    h1 = flat_bars(120, 107.6, 2.0, NOW - 120 * H1, H1)
    up = h1[:-1] + [(NOW - H1, 107.2, 108.2, 106.8, 107.9)]                # closed up
    sig = [s for s in an.signals("TESTUSDT", up, h4, d1, 107.6) if s["method"] == "FIB"]
    assert len(sig) == 1 and sig[0]["side"] == "long" and abs(sig[0]["target"] - 120.2) < 0.3, sig
    assert sig[0]["stop"] < 120.2 - 0.886 * 20.4                          # beyond the 88.6% level
    down_bar = h1[:-1] + [(NOW - H1, 108.0, 108.4, 106.8, 107.2)]          # closed down: no FIB long
    assert not [s for s in an.signals("TESTUSDT", down_bar, h4, d1, 107.6) if s["method"] == "FIB"]
    deep = [s for s in an.signals("TESTUSDT", up, h4, d1, 116.0) if s["method"] == "FIB"]
    assert not deep, deep                                                   # only 19% retraced: outside 50-78.6%
    too_deep = [s for s in an.signals("TESTUSDT", up, h4, d1, 102.5) if s["method"] == "FIB"]
    assert not too_deep, too_deep                                           # 87% retraced: past 78.6%, the swing is failing


def test_smc_sweep_needs_a_reclaim_and_an_up_close():
    h1, h4, d1 = sr_world()
    t = NOW - H1
    sweep = h1[:-1] + [(t, 104.8, 105.3, 103.0, 105.0)]                    # under the 24-bar low (104.5), closes back above it, up bar
    sig = [s for s in an.signals("TESTUSDT", sweep, h4, d1, 105.0) if s["method"] == "SMC"]
    assert len(sig) == 1 and sig[0]["side"] == "long" and sig[0]["stop"] < 103.0, sig
    assert abs((sig[0]["target"] - 105.0) / (105.0 - sig[0]["stop"]) - 2.0) < 1e-6          # the 24-bar high is too close: 2R
    no_reclaim = h1[:-1] + [(t, 104.0, 104.2, 103.0, 103.5)]               # swept but closes under the old low
    assert not [s for s in an.signals("TESTUSDT", no_reclaim, h4, d1, 103.5) if s["method"] == "SMC"]
    down_close = h1[:-1] + [(t, 105.2, 105.3, 103.0, 104.9)]               # reclaimed but closed DOWN
    assert not [s for s in an.signals("TESTUSDT", down_close, h4, d1, 104.9) if s["method"] == "SMC" and s["side"] == "long"]


def test_build_refuses_thin_reward_and_noise_or_absurd_stops():
    a1 = 1.0
    assert an.build("X", "SR", "long", 100, 98, 104, a1, "ok")                          # rr 2, stop 2 ATR
    assert an.build("X", "SR", "long", 100, 98, 102.5, a1, "thin") is None              # rr 1.25 < 1.5
    assert an.build("X", "SR", "long", 100, 99.9, 105, a1, "noise") is None             # stop 0.1 ATR
    assert an.build("X", "SR", "long", 100, 90, 130, a1, "absurd") is None              # stop 10 ATR
    assert an.build("X", "SR", "long", 100, 98, None, a1, "no target") is None
    assert an.build("X", "SR", "short", 100, 98, 104, a1, "wrong way") is None


def patched():
    d = Path(tempfile.mkdtemp())
    an.D, an.CALLS, an.STATE, an.LEVELS, an.MARKS = d, d / "calls.csv", d / "state.json", d / "levels.json", d / "marks.csv"
    return d


def world_fetch(minute_price=101.0, spike_at=None, now=NOW):
    h1, h4, d1 = sr_world()
    h1 = h1[:-1] + [(now - H1, 100.9, 101.2, 98.9, 101.0)]                # a closed bounce bar, then the forming bar
    h1.append((now - 7 * MIN, 101.0, 101.1, 100.9, 101.0))

    def fetch(sym, interval, start=None, end=None, limit=500):
        if interval == "1h":
            return h1
        if interval == "4h":
            return h4
        if interval == "1d":
            return d1
        n = max(0, min(int((end - start) // MIN) + 1, limit))
        return [(start + i * MIN, minute_price, minute_price + 0.05 if (spike_at is None or start + i * MIN < spike_at) else 130.0, minute_price - 0.05, minute_price)
                for i in range(n)]
    return fetch


def test_cycle_logs_the_call_before_its_outcome_once_and_writes_the_levels():
    patched()
    st = an.cycle(NOW, world_fetch(), ["TESTUSDT"])
    rows = an.load_calls()
    sr = [r for r in rows if r["method"] == "SR"]
    assert len(sr) == 1 and sr[0]["status"] == "open" and float(sr[0]["base_p"]) >= 0 and sr[0]["made_ms"] == str(NOW)
    assert st["equity"] == an.START                                        # nothing resolved yet: the book has not moved
    lev = __import__("json").loads(an.LEVELS.read_text())["symbols"]["TESTUSDT"]
    assert lev["support"] and lev["resistance"] and lev["price"] == 101.0 and "typical_move_pct" in lev
    an.cycle(NOW + 10 * MIN, world_fetch(now=NOW + 10 * MIN), ["TESTUSDT"])
    assert len([r for r in an.load_calls() if r["method"] == "SR"]) == 1    # an open call blocks a duplicate


def test_a_target_hit_books_the_paper_book_sized_on_the_equity_at_entry():
    patched()
    an.cycle(NOW, world_fetch(), ["TESTUSDT"])
    call = [r for r in an.load_calls() if r["method"] == "SR"][0]
    later = NOW + 3 * H1
    st = an.cycle(later, world_fetch(minute_price=101.0, spike_at=NOW + 2 * H1, now=later), ["TESTUSDT"])
    done = [r for r in an.load_calls() if r["id"] == call["id"]][0]
    assert done["status"] == "WIN" and done["booked"] == "1", done
    expect = float(done["r_net"]) * float(call["risk_usd"])
    assert abs(float(done["pnl_usd"]) - expect) < 1e-3 and abs(st["equity"] - (an.START + expect)) < 1e-3, (st, done)
    assert abs(float(call["risk_usd"]) - an.START * an.RISK_PCT / 100) < 1e-6          # 0.5% of the equity AT ENTRY, not of the later equity


def test_two_calls_resolving_together_are_each_sized_on_the_equity_at_their_own_entry():
    patched()
    st = dict(started="x", start=an.START, equity=an.START, peak=an.START)
    made = NOW - 3 * H1

    def row(i, sym):
        return dict(id=i, made_utc="x", made_ms=made, symbol=sym, side="long", mode="market", entry=100.0, stop=98.0, target=104.0, expires_ms=made + 24 * H1,
                    method="SR", note="x", equity=300.0, risk_pct=0.5, risk_usd=1.5, qty=1.0, notional=75.0, lev=0.25, stop_pct=0.02, target_pct=0.04, rr=2.0,
                    be_p=0.35, base_p=0.4, status="open", why="x", nobook=0, booked=0)
    rows = [row(1, "AAAUSDT"), row(2, "BBBUSDT")]

    def fetch(sym, interval, start=None, end=None, limit=1500):
        n = min(int((end - start) // MIN) + 1, limit)
        return [(start + i * MIN, 100.0, 104.5 if i == 5 else 100.2, 99.9, 100.0) for i in range(n)]     # both touch the target in minute 5
    assert an.score_open(st, rows, NOW, fetch) == 2
    one = float(rows[0]["r_net"]) * 1.5
    assert abs(float(rows[0]["pnl_usd"]) - one) < 1e-4 and abs(float(rows[1]["pnl_usd"]) - one) < 1e-4, rows   # the second is NOT resized by the first's profit
    assert abs(st["equity"] - (an.START + 2 * one)) < 1e-4


def test_cooldown_blocks_a_refire_for_six_hours_after_the_call_ends():
    patched()
    an.cycle(NOW, world_fetch(), ["TESTUSDT"])
    t1 = NOW + 26 * H1                                                      # two hours after the 24h horizon: it expires, the cooldown (6h) still holds
    an.cycle(t1, world_fetch(now=t1), ["TESTUSDT"])
    sr = [r for r in an.load_calls() if r["method"] == "SR"]
    assert len(sr) == 1 and sr[0]["status"] in ("EXPIRED", "WIN", "LOSS"), sr      # the same bounce is still on the chart, but no refire inside the cooldown
    ended = int(float(sr[0]["exit_ms"]))
    assert not an.allowed(an.load_calls(), "TESTUSDT", "SR", ended + 2 * H1)           # inside the cooldown
    assert an.allowed(an.load_calls(), "TESTUSDT", "SR", ended + 7 * H1)               # after it
    assert an.allowed(an.load_calls(), "TESTUSDT", "FIB", ended + 1)                   # another rule is independent


def test_the_gross_cap_scores_a_call_but_takes_no_paper_money():
    patched()
    old = an.MAX_GROSS
    an.MAX_GROSS = 0.0001                                                   # any position is over the cap
    try:
        st = an.cycle(NOW, world_fetch(), ["TESTUSDT"])
        c = [r for r in an.load_calls() if r["method"] == "SR"][0]
        assert str(c["nobook"]) == "1"
        later = NOW + 3 * H1
        st = an.cycle(later, world_fetch(spike_at=NOW + 2 * H1, now=later), ["TESTUSDT"])
        done = [r for r in an.load_calls() if r["id"] == c["id"]][0]
        assert done["status"] == "WIN" and done["booked"] in ("0", "", 0)
        assert st["equity"] == an.START                                     # scored as a prediction, no money moved
        s = an.stats(an.load_calls())
        assert s["wins"] == 1 and s["resolved"] == 1
    finally:
        an.MAX_GROSS = old


def test_stats_hit_rate_baseline_and_the_30_call_gate():
    def row(i, status, r, base=0.4, m="SR"):
        return dict(id=i, symbol="X", method=m, status=status, r_net=r, base_p=base, be_p=0.35, pnl_usd=r * 1.5, risk_usd=1.5)
    few = an.stats([row(i, "WIN" if i < 3 else "LOSS", 1.9 if i < 3 else -1.1) for i in range(10)])
    assert few["verdict"] == "NOT ENOUGH CALLS" and few["wins"] == 3 and abs(few["baseline"] - 0.4) < 1e-9
    good = an.stats([row(i, "WIN" if i < 24 else "LOSS", 1.9 if i < 24 else -1.1) for i in range(30)])
    assert good["verdict"] == "EDGE" and good["p"] < 0.05
    bad = an.stats([row(i, "WIN" if i < 10 else "LOSS", 1.9 if i < 10 else -1.1) for i in range(30)])
    assert bad["verdict"] == "NO EDGE PROVEN" and bad["avg_r"] < 0.2
    mixed = an.stats([row(i, "WIN", 1.0, m="FIB") for i in range(3)] + [row(9, "LOSS", -1.0, m="SMC")])
    assert set(mixed["by_method"]) == {"FIB", "SMC"} and mixed["by_method"]["FIB"]["n"] == 3


def test_the_random_baseline_is_read_on_the_one_minute_grid_the_calls_are_scored_on():
    patched()

    def fetch(sym, interval, start=None, end=None, limit=500):
        if interval != "1m":
            return world_fetch()(sym, interval, start, end, limit)                  # the hourly world is flat: on hours, nothing ever reaches the target
        n = max(0, min(int((end - start) // MIN) + 1, limit))
        px = lambda i: 100.0 * 1.0002 ** ((start - NOW) / MIN + i)                  # noqa: E731 - minutes that climb 33% a day
        return [(start + i * MIN, px(i), px(i) * 1.00002, px(i) * 0.99999, px(i)) for i in range(n)]
    an.cycle(NOW, fetch, ["TESTUSDT"])
    call = [r for r in an.load_calls() if r["method"] == "SR"][0]
    assert float(call["base_p"]) > 0.9, call["base_p"]                              # a random entry on those minutes nearly always meets the target


def lrow(i, made_h, exit_h, side="long", entry=100.0, px=104.0, status="WIN", mae=0.0, stop_pct=0.02):
    return dict(id=i, symbol="X", side=side, made_ms=made_h * H1, exit_ms=exit_h * H1, entry=entry, exit_price=px, status=status, mae=mae, stop_pct=stop_pct)


def test_mae_is_the_worst_move_against_the_position_up_to_the_exit_only():
    bars = [(0, 100.0, 100.5, 98.0, 99.0), (60_000, 99.0, 101.0, 97.0, 100.0), (120_000, 100.0, 106.0, 90.0, 105.0)]
    call = dict(side="long", entry=100.0, exit_ms=60_000)
    assert abs(an.mae_of(call, bars) - 0.03) < 1e-9                       # the 90 low after the exit does not count
    assert abs(an.mae_of(dict(side="short", entry=100.0), bars) - 0.06) < 1e-9     # a short is hurt by the highs; no exit yet = all bars
    assert an.mae_of(dict(side="long", entry=100.0, exit_ms=""), []) == 0.0
    assert an.mae_of(dict(side="long", entry=100.0), [(0, 100.0, 101.0, 100.0, 100.5)]) == 0.0      # price never went against it


def test_a_resolved_call_carries_its_worst_move():
    patched()
    an.cycle(NOW, world_fetch(), ["TESTUSDT"])
    later = NOW + 3 * H1
    deep = NOW + H1

    def fetch(sym, interval, start=None, end=None, limit=500):
        base = world_fetch(spike_at=NOW + 2 * H1, now=later)
        if interval != "1m":
            return base(sym, interval, start, end, limit)
        bars = base(sym, interval, start, end, limit)
        return [(t, o, h, 99.0 if t == deep else l, c) for t, o, h, l, c in bars]
    an.cycle(later, fetch, ["TESTUSDT"])
    done = [r for r in an.load_calls() if r["method"] == "SR"][0]
    assert done["status"] == "WIN" and abs(float(done["mae"]) - (101.0 - 99.0) / 101.0) < 1e-4, done


def test_leverage_fee_and_direction_on_the_whole_account():
    win, loss = lrow(1, 0, 5, px=104.0), lrow(2, 0, 5, px=98.0, status="LOSS")
    f10, liq = an.leveraged_result(win, 10)
    assert not liq and abs(f10 - 10 * (0.04 - 0.0012)) < 1e-9                  # the fee is 12bp of the NOTIONAL = 12bp x 10 of the account
    assert abs(an.leveraged_result(loss, 10)[0] - 10 * (-0.02 - 0.0012)) < 1e-9
    sh = lrow(3, 0, 5, side="short", entry=100.0, px=96.0)
    assert abs(an.leveraged_result(sh, 20)[0] - 20 * (0.04 - 0.0012)) < 1e-9   # a short gains when price falls
    assert an.leveraged_result(lrow(4, 0, 5, px=100.0, status="EXPIRED"), 10)[0] < 0      # flat after fees is a loss
    assert an.leveraged_result(lrow(5, 0, 5, px=85.0, status="LOSS", mae=0.05), 10) == (-1.0, False)      # a result worse than the whole margin is capped at it


def test_liquidation_happens_before_a_winning_exit_when_the_dip_passes_one_over_leverage_less_the_margin_floor():
    dip = lrow(1, 0, 5, px=104.0, mae=0.03)                                   # wins in the end, but dipped 3% first
    assert an.leveraged_result(dip, 30)[:2] == (-1.0, True)                    # 30x: liquidated at 1/30 - 0.5% = 2.83%
    f20, liq20 = an.leveraged_result(dip, 20)
    assert not liq20 and f20 > 0.7                                             # 20x: liquidation sits at 4.5%
    assert not an.leveraged_result(dip, 10)[1]
    edge = lrow(2, 0, 5, px=104.0, mae=1 / 30 - desk.MMR)
    assert an.leveraged_result(edge, 30)[1] is True and an.leveraged_result(lrow(3, 0, 5, px=104.0, mae=1 / 30 - desk.MMR - 1e-4), 30)[1] is False


def test_without_a_worst_move_record_a_stop_out_counts_as_at_least_the_stop_against_it():
    stopped = lrow(1, 0, 5, px=96.0, status="LOSS", stop_pct=0.04)
    stopped.pop("mae")
    assert an.leveraged_result(stopped, 30)[1] is True and an.leveraged_result(stopped, 10)[1] is False
    won = lrow(2, 0, 5, px=104.0)
    won.pop("mae")
    assert an.leveraged_result(won, 30)[1] is False


def test_scenario_takes_one_position_at_a_time_and_compounds_on_what_it_holds():
    rows = [lrow(1, 0, 10, px=104.0), lrow(2, 5, 12, px=104.0), lrow(3, 10, 20, px=104.0)]
    s = an.scenario(rows, 100, 10)
    one = 1 + 10 * (0.04 - 0.0012)
    assert s["taken"] == 2 and s["skipped_busy"] == 1                          # call 2 appeared while call 1 was open; call 3 made at the exit is taken
    assert abs(s["equity"] - 100 * one * one) < 1e-6 and abs(s["ret"] - (one * one - 1)) < 1e-9


def test_a_liquidation_empties_the_account_and_later_calls_cannot_be_taken():
    rows = [lrow(1, 0, 5, px=104.0, mae=0.05), lrow(2, 10, 15, px=104.0)]
    s = an.scenario(rows, 100, 30)
    assert s["liquidated"] == 1 and s["taken"] == 1 and s["skipped_small"] == 1 and s["equity"] == 0 and s["ruined"] and s["worst"] == -1.0
    assert abs(s["maxdd"] - 1.0) < 1e-12


def test_the_five_dollar_minimum_order_is_the_only_thing_capital_changes():
    rows = [lrow(1, 0, 5, px=104.0), lrow(2, 6, 9, px=98.0, status="LOSS"), lrow(3, 12, 18, px=104.0)]
    a, b = an.scenario(rows, 20, 10), an.scenario(rows, 300, 10)
    assert abs(a["ret"] - b["ret"]) < 1e-12 and abs(b["equity"] / a["equity"] - 15) < 1e-9      # the same multiple, in dollars scaled by capital
    assert (b["wins"], b["losses"]) == (2, 1) and b["taken"] == 3
    tiny = an.scenario(rows, 0.4, 10)                                          # 0.4 x 10 = $4 of notional: under the venue's $5
    assert tiny["taken"] == 0 and tiny["skipped_small"] == 3


def test_the_deepest_fall_is_measured_from_the_highest_account_and_calls_are_taken_in_the_order_made():
    win, loss = lrow(1, 0, 5, px=104.0), lrow(2, 6, 9, px=98.0, status="LOSS")
    s = an.scenario([win, loss], 100, 10)
    a, b = 1 + 10 * (0.04 - 0.0012), 1 + 10 * (-0.02 - 0.0012)
    assert abs(s["maxdd"] - (1 - b)) < 1e-9 and abs(s["equity"] - 100 * a * b) < 1e-6      # the fall is from the winner's peak, not from the start
    early, late = lrow(3, 0, 10, px=104.0), lrow(4, 5, 12, px=98.0, status="LOSS")
    assert an.scenario([late, early], 100, 10) == an.scenario([early, late], 100, 10)       # given out of order, still one position at a time in the order made
    assert an.scenario([late, early], 100, 10)["wins"] == 1                                 # the earlier call (a win) was the one taken
    old_fee = desk.FEE
    desk.FEE = 0.25                                                                         # a result of exactly zero after fees is not a win
    try:
        flat = an.scenario([lrow(5, 0, 5, entry=100.0, px=125.0)], 100, 10)
    finally:
        desk.FEE = old_fee
    assert (flat["wins"], flat["losses"], flat["equity"]) == (0, 1, 100.0)


def test_calls_after_the_first_open_one_are_left_pending_not_guessed():
    rows = [lrow(1, 0, 5, px=104.0), dict(lrow(2, 6, 7), status="open", exit_price="", exit_ms=""), lrow(3, 7, 8, px=104.0)]
    s = an.scenario(rows, 100, 10)
    assert s["taken"] == 1 and s["pending"] == 1
    two_open = rows + [dict(lrow(4, 9, 10), status="open", exit_price="", exit_ms="")]
    assert an.scenario(two_open, 100, 10)["pending"] == 1                              # the FIRST open call (hour 6) sets the horizon, not the last (hour 9)
    assert [r["taken"] for r in an.grid(rows)] == [1] * 12 and len(an.grid(rows)) == 12
    assert {(g["capital"], g["lev"]) for g in an.grid(rows)} == {(c, x) for c in an.CAPITALS for x in an.LEVERAGES}


if __name__ == "__main__":
    tests =[v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")

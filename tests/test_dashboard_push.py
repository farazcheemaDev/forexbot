"""dashboard_push.py's scorecard maths: where a live result sits in the backtest's N-day range (offline, no network)."""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dashboard_push as dp  # noqa: E402

LEVELS = [0, 25, 50, 75, 100]


def test_pctile_interpolates_and_clips():
    q = [-0.10, -0.02, 0.0, 0.02, 0.10]
    assert dp.pctile(-0.5, LEVELS, q) == 0.0 and dp.pctile(0.5, LEVELS, q) == 100.0
    assert abs(dp.pctile(-0.01, LEVELS, q) - 37.5) < 1e-9          # halfway between the 25th and the 50th
    assert abs(dp.pctile(0.06, LEVELS, q) - 87.5) < 1e-9


def test_pctile_a_tied_value_sits_in_the_middle_of_its_tie():
    q = [0.0, 0.0, 0.0, 0.01, 0.05]                                 # an often-idle book: zero up to the 50th
    assert dp.pctile(0.0, LEVELS, q) == 25.0


def test_band_at_interpolates_between_stored_lengths():
    b = {"7": dict(q=[0.0, 0.1, 0.2, 0.3, 0.4], idle=0.5), "14": dict(q=[0.0, 0.3, 0.4, 0.5, 0.6], idle=0.1)}
    q, idle = dp.band_at(b, [7, 14], 10.5)
    assert [round(x, 6) for x in q] == [0.0, 0.2, 0.3, 0.4, 0.5] and abs(idle - 0.3) < 1e-9
    q, _ = dp.band_at(b, [7, 14], 400)                               # older than the grid: the longest stretch
    assert q == b["14"]["q"]


def test_status_lines():
    assert dp.status(3, False, 0) == "worse" and dp.status(10, False, 0) == "below"
    assert dp.status(50, False, 0) == "ok" and dp.status(80, False, 0) == "above"
    assert dp.status(40, True, 0.6) == "idle"                       # no trade yet, and that is common
    assert dp.status(2, True, 0.05) == "worse"                       # no trade yet, and that is rare


def test_scorecard_waits_a_week_and_then_places_every_book():
    books = {b: dict(booked=0.0, open=0.0) for b in dp.SCORE_BOOKS}
    books["trend"] = dict(booked=-9.0, open=0.0)
    flat = dict(q=[-0.1, -0.02, 0.0, 0.02, 0.1], idle=0.0)
    bands = dict(levels=LEVELS, lengths=[1, 30], span="x", made="y",
                 books={b: {"1": flat, "30": flat} for b in dp.SCORE_BOOKS}, total={"1": flat, "30": flat})
    now = int(time.time())
    for age in (3600, 6.9 * 86400):                                  # under a week: weekly books do not compare yet
        young = datetime.fromtimestamp(now - age, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        assert dp.scorecard(young, now, books, 291.0, 300.0, bands)["ready"] is False
    old = datetime.fromtimestamp(now - 10 * 86400, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    sc = dp.scorecard(old, now, books, 291.0, 300.0, bands)
    assert sc["ready"] and len(sc["books"]) == len(dp.SCORE_BOOKS)
    tr = next(r for r in sc["books"] if r["book"] == "trend")
    assert tr["usd"] == -9.0 and abs(tr["pctile"] - 21.875) < 0.05 and tr["status"] == "below"   # -3% of $300
    assert sc["total"]["status"] == "below" and sc["total"]["usd"] == -9.0
    assert dp.scorecard(old, now, books, 291.0, 300.0, None)["ready"] is False                      # no yardstick


def test_crowd_book_is_marked_live_like_the_books_own_mark_and_scored_from_week_4():
    import json
    import tempfile
    from news import crowd_paper as cp
    d = Path(tempfile.mkdtemp())
    st = cp.fresh()
    sl = st["sleeves"]["mon"]
    sl.update(equity=160.0, fee=0.0012, opened="2026-10-26",
              pos=[dict(sym="AUSDT", side=1, w=0.25, entry=10.0, mark=11.0, fund=0.002),
                   dict(sym="CUSDT", side=1, w=0.25, entry=2.0, mark=2.2, fund=0.0),
                   dict(sym="BUSDT", side=-1, w=0.5, entry=4.0, mark=3.0, fund=-0.001)])
    (d / "state.json").write_text(json.dumps(st))
    bands = dict(levels=[5, 10, 25, 50, 75, 90, 95], lengths=[1, 52], span="x",
                 total={"1": dict(q=[-0.05, -0.03, -0.01, 0.0, 0.02, 0.05, 0.06], idle=0.0),
                        "52": dict(q=[-0.1, -0.07, 0.14, 0.32, 0.47, 1.2, 1.5], idle=0.0)})
    old = dp.CROWD
    dp.CROWD = d
    try:
        first = dp.day_ts(st["first"])
        c = dp.crowd({"AUSDT": 11.0, "BUSDT": 3.0}, first + 3 * 7 * 86400, bands)    # CUSDT has no price: its mark
        c5 = dp.crowd({"AUSDT": 11.0, "BUSDT": 3.0}, first + 5 * 7 * 86400, bands)
    finally:
        dp.CROWD = old
    assert abs(c["equity"] - round(cp.sleeve_now(sl) + 150.0, 2)) < 0.006
    assert len(c["legs"]) == 3 and {r["side"] for r in c["legs"]} == {"long", "short"}
    assert c["score"]["ready"] is False and c5["score"]["ready"] is True
    assert 0 <= c5["score"]["pctile"] <= 100 and c5["score"]["status"] in ("worse", "below", "ok", "above")


def test_venue_symbols_find_binances_price_in_the_same_units():
    p = {"1000SHIBUSDT": 0.012, "1000CHEEMSUSDT": 0.002, "RAYSOLUSDT": 2.5, "SOLUSDT": 190.0}
    assert abs(dp.price(p, "SHIBUSDT") - 0.000012) < 1e-15                    # Bitget's SHIB
    assert abs(dp.price(p, "1MCHEEMSUSDT") - 2.0) < 1e-12                     # Bitget's 1MCHEEMS
    assert dp.price(p, "RAYUSDT") == 2.5 and dp.price(p, "SOLUSDT") == 190.0 and dp.price(p, "NOPEUSDT") is None


def test_the_fuel_gauge_reaches_the_page_inside_the_mood_market():
    import json
    import tempfile
    from pathlib import Path
    snap = dict(t="2026-10-26 20:00 UTC", coins=[], market=dict(fear_greed=50, fuel=dict(
        n=39, runners=0.0513, med=-0.1926, disp=0.2228, runners_pct=28.0, med_pct=23.0, disp_pct=35.0, state="LOW")))
    f = Path(tempfile.mkdtemp()) / "mood.json"
    f.write_text(json.dumps(snap))
    old = dp.MOOD
    dp.MOOD = f
    try:
        m = dp.mood()
    finally:
        dp.MOOD = old
    assert m["market"]["fuel"]["state"] == "LOW" and abs(m["market"]["fuel"]["runners"] - 0.0513) < 1e-9


def test_mood_and_crowd_absent_until_their_files_exist():
    import tempfile
    old = dp.MOOD, dp.CROWD
    dp.MOOD, dp.CROWD = Path(tempfile.mkdtemp()) / "none.json", Path(tempfile.mkdtemp())
    try:
        assert dp.mood() is None and dp.crowd({}, int(time.time()), None) is None
    finally:
        dp.MOOD, dp.CROWD = old


def test_closed_trades_label_every_short_a_short():
    """The trade log has no side column. 2026-10-26: the carry book's +50% squeeze exit on BULLA (a short, -55%, -$2.12)
    showed as a LONG on the dashboard. Every short the log can hold must say short; everything else long."""
    import tempfile
    d = Path(tempfile.mkdtemp())
    rows = [
        "ts,book,symbol,entry,exit,ret,pnl,why,equity",
        "2026-10-26 10:01:27,carry,BULLAUSDT,0.08185,0.1272,-0.55406,-2.1191,short_exit,253.2",
        "2026-10-26 09:00:00,news,ABCUSDT,1.0,0.9,0.1,0.5,take_profit,254.0",
        "2026-10-26 08:00:00,crowd,AAVEUSDT,100,90,-0.1,-0.7,\"mon week, short\",254.0",
        "2026-10-26 07:00:00,crowd,BTWUSDT,1.6,1.4,-0.12,-0.9,\"mon week, long\",254.0",
        "2026-10-26 06:00:00,daily,AKEUSDT,0.039,0.0316,-0.19,-3.0,mean exit,254.0",
        "2026-10-26 05:00:00,ndx,QQQUSDT,700,710,0.014,0.9,above_sma5,254.0",
        "2026-10-26 04:00:00,bids,SOLUSDT,100,101,0.01,0.1,hour_close,254.0",
    ]
    (d / "combo_final_trades.csv").write_text("\n".join(rows) + "\n")
    got = {(r["book"], r["sym"]): r["side"] for r in dp.closed_trades(d)}
    assert got == {("carry", "BULLAUSDT"): "short", ("news", "ABCUSDT"): "short", ("crowd", "AAVEUSDT"): "short",
                   ("crowd", "BTWUSDT"): "long", ("daily", "AKEUSDT"): "long", ("ndx", "QQQUSDT"): "long",
                   ("bids", "SOLUSDT"): "long"}, got
    carry = [r for r in dp.closed_trades(d) if r["book"] == "carry"][0]
    assert carry["pct"] == -0.55406 and carry["pnl"] == -2.1191            # the numbers were always right


def _analyst_world():
    """A temp logs/analyst with 4 calls (open booked long, open NOT-booked short, a booked win, an unbooked loss), a book at $303 and one set of levels."""
    import json
    import tempfile
    import analyst as an
    d = Path(tempfile.mkdtemp())
    call = lambda **k: dict(made_utc="2026-10-27 10:00:00", made_ms=1, expires_ms=int(time.time() * 1000) + 10 * 3_600_000, method="SR", why="w",  # noqa: E731
                            rr=2.0, be_p=0.4, base_p=0.35, **k)
    rows = [
        call(id=1, symbol="BTCUSDT", side="long", entry=100.0, stop=98.0, target=106.0, stop_pct=0.02, risk_usd=1.5, notional=75.0, status="open", nobook=0),
        call(id=2, symbol="ETHUSDT", side="short", entry=50.0, stop=51.0, target=47.0, stop_pct=0.02, risk_usd=1.5, notional=75.0, status="open", nobook=1),
        call(id=3, symbol="SOLUSDT", side="long", entry=10.0, stop=9.8, target=10.6, stop_pct=0.02, risk_usd=1.5, notional=75.0, status="WIN", nobook=0,
             exit_ms=2_000, exit_price=10.6, r_net=2.0, booked=1, pnl_usd=3.0),
        call(id=4, symbol="XRPUSDT", side="short", entry=2.0, stop=2.04, target=1.9, stop_pct=0.02, risk_usd=1.5, notional=75.0, status="LOSS", nobook=1,
             exit_ms=3_000, exit_price=2.04, r_net=-1.06, booked=0, pnl_usd=""),
    ]
    old = (an.D, an.CALLS)
    an.D, an.CALLS = d, d / "calls.csv"
    try:
        an.save_calls(rows)
    finally:
        an.D, an.CALLS = old
    (d / "state.json").write_text(json.dumps(dict(started="2026-10-27 09:00:00", started_ms=1_800_000_000_000, start=300.0, equity=303.0, peak=303.0)))
    (d / "marks.csv").write_text("day,equity\n2026-10-27,300.0\n")
    (d / "levels.json").write_text(json.dumps(dict(t=5, made="2026-10-27 12:07:00", symbols={"BTCUSDT": dict(
        symbol="BTCUSDT", price=100.0, atr1_pct=0.004, typical_move_pct=0.02, support=[dict(price=95.0, touches=3)],
        resistance=[dict(price=105.0, touches=4)], fib=dict(trend="up", hi=110.0, lo=90.0, levels={}, retraced=0.5), gaps=[])})))
    return d


def test_the_analyst_desk_is_marked_live_and_only_booked_calls_move_its_book():
    d = _analyst_world()
    old = dp.ANALYST
    dp.ANALYST = d
    try:
        a = dp.analyst_view({"BTCUSDT": 101.0, "ETHUSDT": 55.0}, int(time.time()))
    finally:
        dp.ANALYST = old
    one = [c for c in a["open"] if c["id"] == 1][0]
    two = [c for c in a["open"] if c["id"] == 2][0]
    assert abs(one["r"] - (0.01 - 0.0012) / 0.02) < 1e-3 and abs(one["upnl"] - 0.66) < 0.006        # +1% on a 2% stop, fee in
    assert two["upnl"] is None and two["booked"] is False and two["r"] < -2                          # a short that went against it, not booked
    assert abs(a["equity"] - 303.66) < 0.006 and a["booked"] == 303.0                              # only the booked call is in the book
    assert a["curve"]["h"][-1][1] == a["equity"] and a["curve"]["h"][0][1] == 300.0


def test_the_analyst_desk_levels_are_measured_from_the_live_price_and_the_record_is_complete():
    import json
    d = _analyst_world()
    old = dp.ANALYST
    dp.ANALYST = d
    try:
        a = dp.analyst_view({"BTCUSDT": 101.0}, int(time.time()))
    finally:
        dp.ANALYST = old
    s = a["symbols"]["BTCUSDT"]
    assert s["price"] == 101.0 and s["calls"] == [1]                                                # live price, not the logged 100
    assert abs(s["support"][0]["dist"] - (95 / 101 - 1)) < 1e-4 and s["support"][0]["dist"] < 0 < s["resistance"][0]["dist"]
    assert abs(s["fib"]["retraced"] - 0.45) < 1e-3                                                  # (110 - 101) / 20
    assert s["typical"] == [round(101 * 0.98, 8), round(101 * 1.02, 8)]
    assert [r["id"] for r in a["recent"]] == [4, 3] and a["recent"][0]["usd"] is None and a["recent"][1]["usd"] == 3.0
    assert a["stats"]["resolved"] == 2 and a["stats"]["wins"] == 1 and a["stats"]["min_resolved"] == 30
    json.dumps(a, allow_nan=False)                                                                  # the page parses it: no NaN / Infinity


def test_the_leverage_grid_is_built_from_the_logged_calls_and_the_replay_file_is_optional():
    import json
    import tempfile
    d = _analyst_world()
    old = dp.ANALYST, dp.ANALYST_REPLAY
    dp.ANALYST, dp.ANALYST_REPLAY = d, Path(tempfile.mkdtemp()) / "none.json"
    try:
        a = dp.analyst_view({"BTCUSDT": 101.0}, int(time.time()))
        gone = a["what_if"]
        rf = Path(tempfile.mkdtemp()) / "replay.json"
        cell = dict(capital=100, lev=10, equity=1.0, ret=-0.99, taken=5, wins=1, liquidated=0, skipped_busy=2, pending=0, worst=-0.3, maxdd=0.99, ruined=True,
                    skipped_small=3, extra="dropped")
        rf.write_text(json.dumps(dict(made="x", span=["a", "b"], years=4.8, calls=10, taken=7, per_year=2, symbols={"BTCUSDT": {}}, grid=dict(all=[cell], tune=[cell], hold=[cell]),
                                      stats=dict(all=dict(hit=0.15, avg_r=-0.3)), by_method=dict(SR=dict(n=3, hold=dict(n=1), tune=dict(n=2), junk=1)),
                                      boot=[dict(lev=10, median=0.0, ruin=1.0)], check_1m=dict(days=90, calls=720, s1h=dict(hit=0.19), s1m=dict(hit=0.2)),
                                      paper_book=dict(final=12.3456789, maxdd=0.97, booked=5, skipped=1, weekly=-0.02, by_year={"2022": -0.5}))))
        dp.ANALYST_REPLAY = rf
        b = dp.analyst_view({"BTCUSDT": 101.0}, int(time.time()))["what_if"]
    finally:
        dp.ANALYST, dp.ANALYST_REPLAY = old
    assert gone["replay"] is None and len(gone["live"]) == 12                     # 4 capitals x 3 leverages
    assert {(c["capital"], c["lev"]) for c in gone["live"]} == {(c, x) for c in (20, 50, 100, 300) for x in (10, 20, 30)}
    assert all(c["taken"] == 0 and c["pending"] == 2 for c in gone["live"])        # both resolved calls were made no earlier than the first open one: left pending
    assert b["replay"]["grid"]["hold"][0]["equity"] == 1.0 and "extra" not in b["replay"]["grid"]["all"][0] and "skipped_small" not in b["replay"]["grid"]["all"][0]
    assert b["replay"]["check_1m"]["s1m"]["hit"] == 0.2 and gone["replay"] is None
    assert b["replay"]["paper_book"]["final"] == 12.3457 and b["replay"]["paper_book"]["by_year"]["2022"] == -0.5
    assert b["replay"]["boot"][0]["ruin"] == 1.0 and set(b["replay"]["by_method"]["SR"]) == {"n", "hold", "tune"} and "symbols" not in b["replay"]
    json.dumps(b, allow_nan=False)


def test_the_analyst_desk_is_absent_until_it_has_run():
    import tempfile
    old = dp.ANALYST
    dp.ANALYST = Path(tempfile.mkdtemp())
    try:
        assert dp.analyst_view({"BTCUSDT": 1.0}, int(time.time())) is None
    finally:
        dp.ANALYST = old


def _basket_state():
    """Fresh-account-shaped state: an MN basket struck 10-31 (AKE short opened at 0.0139, since fallen to a 0.0022 daily mark),
    a carry basket, one daily-book position and one NASDAQ dip buy (these two are NOT daily-marked)."""
    return dict(
        mn=dict(base=250.0, last_rebal="2026-10-31", weights={"AKEUSDT": -0.04, "BIRBUSDT": 0.04, "NEWUSDT": 0.04},
                mark_px={"AKEUSDT": 0.002197, "BIRBUSDT": 0.10, "NEWUSDT": 2.0}),
        exec=dict(mn_qty={"AKEUSDT": -719.0, "BIRBUSDT": 125.0}, carry_qty={"AKEUSDT": -359.5}),
        fin=dict(carry=dict(base=125.0, last_rebal="2026-10-31", weights={"AKEUSDT": -0.04}, mark_px={"AKEUSDT": 0.002197}),
                 daily=dict(open={"AINUSDT": dict(qty=100.0, entry=0.23, t_ms=1_793_000_000_000)}),
                 ndx=dict(open=dict(qty=0.5, entry=690.0, t_ms=1_793_000_000_000, days=2))))


PRICES = {"AKEUSDT": 0.005, "BIRBUSDT": 0.11, "NEWUSDT": 2.0, "AINUSDT": 0.10, "QQQUSDT": 660.0, "BTCUSDT": 76000.0}


def _rows():
    return dp.open_positions(_basket_state(), dict(PRICES))


def test_struck_price_is_weight_times_base_over_coins_and_refuses_what_it_cannot_know():
    assert abs(dp.struck_price(-0.04, 250.0, -719.0) - 0.04 * 250.0 / 719.0) < 1e-12        # a short: both signs negative, price positive
    assert abs(dp.struck_price(0.04, 250.0, 125.0) - 0.08) < 1e-12
    assert dp.struck_price(0.04, 250.0, None) is None and dp.struck_price(0.04, 250.0, 0) is None
    assert dp.struck_price(0.04, 0, 125.0) is None and dp.struck_price(0.0, 250.0, 125.0) is None
    assert dp.struck_price(0.04, 250.0, -125.0) is None                                      # weight and coins disagree on the side: not trustworthy


def test_daily_marked_rows_say_so_and_carry_the_price_they_were_opened_at():
    rows = {(r["book"], r["sym"]): r for r in _rows()}
    ake = rows[("mn", "AKEUSDT")]
    assert ake["daily"] == 1 and ake["side"] == "short"
    assert ake["entry"] == 0.002197                                                           # `entry` stays the last daily MARK (what the P&L is measured from)
    assert abs(ake["open_px"] - 0.04 * 250.0 / 719.0) < 1e-9 and abs(ake["open_px"] - 0.0139082) < 1e-6
    assert abs(ake["chg_open"] - (0.005 / ake["open_px"] - 1)) < 1e-4 and ake["chg_open"] < 0          # the PRICE is down 64% since the basket was struck
    car = rows[("carry", "AKEUSDT")]
    assert car["daily"] == 1 and abs(car["open_px"] - 0.04 * 125.0 / 359.5) < 1e-9


def test_the_pnl_of_a_daily_row_is_still_todays_move_so_the_page_still_adds_up():
    ake = next(r for r in _rows() if r["book"] == "mn" and r["sym"] == "AKEUSDT")
    qty = 250.0 * -0.04 / 0.002197
    assert abs(ake["upnl"] - qty * (0.005 - 0.002197)) < 1e-3 and ake["upnl"] < 0              # a short loses when the price rises from the day's mark
    assert abs(ake["pct"] - ake["upnl"] / abs(qty * 0.002197)) < 1e-4 and ake["pct"] < -1.0   # -130% of the day's exposure, a one-day figure
    total = sum(r["upnl"] for r in _rows())
    expect = (250.0 * -0.04 / 0.002197 * (0.005 - 0.002197) + 250.0 * 0.04 / 0.10 * (0.11 - 0.10) + 250.0 * 0.04 / 2.0 * 0.0
              + 125.0 * -0.04 / 0.002197 * (0.005 - 0.002197) + 100.0 * (0.10 - 0.23) + 0.5 * (660.0 - 690.0))
    assert abs(total - expect) < 1e-2


def test_rows_booked_at_entry_are_not_marked_daily_and_unknown_coins_degrade_quietly():
    rows = {(r["book"], r["sym"]): r for r in _rows()}
    for key in (("daily", "AINUSDT"), ("ndx", "QQQUSDT")):
        assert "daily" not in rows[key] and "open_px" not in rows[key]                          # their entry IS the entry
    new = rows[("mn", "NEWUSDT")]                                                             # the bot holds no coins for it: no price to show, no crash
    assert new["daily"] == 1 and new["open_px"] is None and new["chg_open"] is None
    st = _basket_state()
    del st["exec"]                                                                            # an older state file without the execution ledger
    old = dp.open_positions(st, dict(PRICES))
    assert all(r["open_px"] is None for r in old if r.get("daily")) and len(old) == len(_rows())


def test_the_feed_stays_valid_json_with_the_new_fields():
    import json
    json.dumps(_rows(), allow_nan=False)


def test_wilson_interval_matches_known_values_and_handles_the_edges():
    lo, hi = dp.wilson(8, 10)
    assert abs(lo - 0.4902) < 1e-3 and abs(hi - 0.9433) < 1e-3          # the textbook 95% Wilson interval for 8 of 10
    lo, hi = dp.wilson(5, 10)
    assert abs(lo + hi - 1.0) < 1e-12                                  # symmetric around one half
    assert dp.wilson(0, 10)[0] == 0.0 and abs(dp.wilson(0, 10)[1] - 0.2775) < 1e-3
    assert dp.wilson(3, 0) is None


def test_stop_size_kinds_use_the_registered_edges():
    assert dp.call_kind(0.0039) == "scalp" and dp.call_kind(0.004) == "mid" and dp.call_kind(0.0079) == "mid"
    assert dp.call_kind(0.008) == "sweet" and dp.call_kind(0.05) == "sweet" and dp.call_kind(None) is None


def _row(i, day, side, method, status, stop, r):
    return dict(id=str(i), made_utc=f"{day} 10:07", side=side, method=method, status=status, stop_pct=str(stop), r_net=str(r), symbol="XRPUSDT")


def test_the_desks_history_counts_independent_bets_and_puts_the_range_on_the_bets():
    rows = [_row(1, "2026-11-04", "long", "SMC", "WIN", 0.01, 2.0), _row(2, "2026-11-04", "long", "SMC", "WIN", 0.012, 1.0),     # one bet: day 4, long
            _row(3, "2026-11-05", "short", "SR", "LOSS", 0.01, -1.1), _row(4, "2026-11-05", "short", "SMC", "EXPIRED", 0.02, 0.4),      # one bet: day 5, short
            _row(5, "2026-11-06", "long", "SMC", "LOSS", 0.009, -1.0),                                                                  # one bet
            _row(6, "2026-11-06", "long", "SMC", "WIN", 0.002, 5.0),                                                                    # scalp-sized: not in 'sweet'
            _row(7, "2026-11-06", "long", "SMC", "open", 0.01, "")]                                                                     # open: no outcome
    h = dp.desk_history(rows, "sweet")
    assert h["n"] == 5 and h["bets"] == 3 and h["wins"] == 2 and abs(h["hit"] - 0.4) < 1e-9
    assert abs(h["mean_r"] - (2.0 + 1.0 - 1.1 + 0.4 - 1.0) / 5) < 1e-3                          # per call, EXPIRED counted
    assert abs(h["mean_r_bet"] - ((1.5 + (-0.35) + (-1.0)) / 3)) < 1e-3                         # per bet: the mean of each day-and-side group, equal weights
    lo, hi = dp.wilson(0.4 * 3, 3)
    assert abs(h["lo"] - round(lo, 3)) < 1e-9 and abs(h["hi"] - round(hi, 3)) < 1e-9              # the interval counts 3 bets, not 5 calls
    assert dp.desk_history(rows, "sweet", "SR")["n"] == 1 and dp.desk_history(rows, "scalp")["n"] == 1
    assert dp.desk_history(rows, "mid") == dict(n=0, bets=0)


def test_a_day_with_calls_on_both_sides_is_two_bets():
    rows = [_row(1, "2026-11-04", "long", "SMC", "WIN", 0.01, 1.0), _row(2, "2026-11-04", "short", "SMC", "LOSS", 0.01, -1.0)]
    assert dp.desk_history(rows, "sweet")["bets"] == 2 and dp.desk_history(rows, "sweet")["n"] == 2


def test_bear_sleeve_rows_are_daily_marked_too():
    st = dict(sleeve=dict(hold={"XRPUSDT": 12.0}, mark_px={"XRPUSDT": 2.0}))
    row = dp.open_positions(st, {"XRPUSDT": 2.2})[0]
    assert row["book"] == "sleeve" and row["daily"] == 1 and abs(row["upnl"] - 12.0 * (2.2 / 2.0 - 1)) < 1e-3 and "open_px" not in row


def _fib_symbol(trend, hi, lo, px, atr):
    rng = hi - lo
    ret = (hi - px) / rng if trend == "up" else (px - lo) / rng
    lev = {"0.886": hi - 0.886 * rng if trend == "up" else lo + 0.886 * rng}
    return dict(price=px, atr1_pct=atr / px, fib=dict(trend=trend, hi=hi, lo=lo, levels=lev, retraced=ret), support=[], resistance=[])


def test_the_fib_preview_is_the_exact_call_the_rule_would_log():
    up = dp.watch_items({"AAAUSDT": _fib_symbol("up", 110.0, 100.0, 103.0, 0.5)})[0]
    stop = (110 - 0.886 * 10) - 0.25 * 0.5
    assert up["kind"] == "FIB" and up["side"] == "long" and up["fires"] is True
    assert abs(up["stop"] - round(stop, 8)) < 1e-9 and up["target"] == 110.0
    assert abs(up["stop_pct"] - round((103 - stop) / 103, 5)) < 1e-9 and abs(up["rr"] - round(7 / (103 - stop), 2)) < 1e-9
    dn = dp.watch_items({"BBBUSDT": _fib_symbol("down", 110.0, 100.0, 107.0, 0.5)})[0]
    stop = (100 + 0.886 * 10) + 0.25 * 0.5
    assert dn["side"] == "short" and dn["fires"] is True and abs(dn["stop"] - round(stop, 8)) < 1e-9 and dn["target"] == 100.0
    wide = dp.watch_items({"CCCUSDT": _fib_symbol("up", 110.0, 100.0, 103.0, 0.3)})[0]            # ATR too small: the stop is more than 4 ATR away
    assert wide["fires"] is False and "no call" in wide["need"]
    assert dp.watch_items({"DDDUSDT": _fib_symbol("up", 110.0, 100.0, 108.0, 0.5)}) == []         # 20% retraced: outside the 50-78.6% zone


def test_the_preview_leaves_out_gold_and_qqq_while_the_desk_cannot_call_them():
    from datetime import datetime, timezone

    def ms(s):
        return int(datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp() * 1000)
    syms = {k: _fib_symbol("up", 110.0, 100.0, 103.0, 0.5) for k in ("XAUUSDT", "QQQUSDT", "BTCUSDT")}
    assert {w["symbol"] for w in dp.watch_items(syms)} == {"XAUUSDT", "QQQUSDT", "BTCUSDT"}                 # no run time given: unchanged
    assert {w["symbol"] for w in dp.watch_items(syms, ms("2026-11-14 12:07"))} == {"BTCUSDT"}               # Saturday: gold and QQQ shut
    assert {w["symbol"] for w in dp.watch_items(syms, ms("2026-11-10 03:07"))} == {"XAUUSDT", "BTCUSDT"}    # Asian night: gold open, QQQ shut
    assert {w["symbol"] for w in dp.watch_items(syms, ms("2026-11-10 16:07"))} == {"XAUUSDT", "QQQUSDT", "BTCUSDT"}
    assert {w["symbol"] for w in dp.watch_items(syms, ms("2026-11-10 15:07"))} == {"XAUUSDT", "BTCUSDT"}    # QQQ: that run reads the 09:00 EST candle


def test_the_fib_preview_respects_the_zone_edges_and_the_desks_reward_to_risk_floor():
    assert dp.watch_items({"AAAUSDT": _fib_symbol("up", 110.0, 100.0, 106.0, 0.5)}) == []         # 40% retraced: not yet in the 50-78.6% zone
    assert dp.watch_items({"BBBUSDT": _fib_symbol("up", 110.0, 100.0, 101.5, 0.5)}) == []         # 85% retraced: past the zone
    thin = dp.watch_items({"CCCUSDT": _fib_symbol("up", 104.0, 100.0, 102.0, 0.5)})[0]            # 50% in, but 2.0 of reward for 1.67 of risk
    assert thin["fires"] is False and 1.0 < thin["rr"] < 1.5                                       # under the desk's 1.5R floor: no call, though above 1.0R


def test_the_sr_watch_ignores_levels_beyond_1_5_atr_and_levels_on_the_wrong_side_of_the_price():
    base = dict(price=100.0, atr1_pct=0.005, fib=None, support=[], resistance=[])
    assert dp.watch_items({"AAAUSDT": dict(base, support=[dict(price=98.5, touches=4)])}) == []         # 3 ATR below: too far
    assert dp.watch_items({"BBBUSDT": dict(base, support=[dict(price=100.3, touches=4)])}) == []        # a 'support' ABOVE the price, 0.6 ATR away: not a long
    assert dp.watch_items({"CCCUSDT": dict(base, resistance=[dict(price=99.7, touches=4)])}) == []      # a 'resistance' BELOW the price: not a short
    short = dp.watch_items({"DDDUSDT": dict(base, resistance=[dict(price=100.5, touches=4)])})
    assert len(short) == 1 and short[0]["side"] == "short" and short[0]["dist_atr"] == 1.0


def test_the_sr_watch_gives_a_stop_range_and_only_lists_strong_nearby_levels_on_the_right_side():
    v = dict(price=100.0, atr1_pct=0.005, fib=None,
             support=[dict(price=99.5, touches=4), dict(price=97.0, touches=5), dict(price=99.9, touches=2)],
             resistance=[dict(price=104.0, touches=3), dict(price=101.0, touches=2)])
    items = dp.watch_items({"EEEUSDT": v})
    assert len(items) == 1                                              # 97 is 6 ATR away, 99.9 has 2 touches, the 104 resistance is 8 ATR away
    it = items[0]
    assert it["kind"] == "SR" and it["side"] == "long" and it["touches"] == 4 and it["dist_atr"] == 1.0 and it["level"] == 99.5
    assert abs(it["stop_pct_lo"] - round((0.5 + 0.25) / 100, 5)) < 1e-9 and abs(it["stop_pct_hi"] - round((0.5 + 0.75) / 100, 5)) < 1e-9
    assert it["kind_size"] == "maybe" and it["rr"] == (round(4 / 1.25, 2), round(4 / 0.75, 2))
    v2 = dict(v, support=[dict(price=101.0, touches=4)], resistance=[])                              # a 'support' above the price cannot bounce a long
    assert dp.watch_items({"FFFUSDT": v2}) == []
    v3 = dict(v, support=[dict(price=99.0, touches=4)], atr1_pct=0.01)                               # 1.0 below at 1 ATR: stop at least 1.0 + 0.5 = 1.5%: sweet-spot-sized for sure
    assert dp.watch_items({"GGGUSDT": v3})[0]["kind_size"] == "sweet"


def test_sweet_view_tags_open_calls_prices_them_from_here_and_counts_down_to_the_next_run():
    rows = [_row(i, f"2026-11-0{1 + i // 2}", "long" if i % 2 else "short", "SMC", "WIN" if i % 3 else "LOSS", 0.01, 1.0 if i % 3 else -1.0) for i in range(10)]
    rows.append(_row(20, "2026-11-06", "long", "SMC", "open", 0.01, ""))
    open_calls = [dict(id=20, symbol="XRPUSDT", side="long", method="SMC", entry=100.0, stop=99.0, target=103.0, mark=100.5)]
    sv = dp.sweet_view(rows, open_calls, {}, 1793965016)
    c = sv["calls"][0]
    assert c["kind"] == "sweet" and c["odds_scope"] == "method" and c["odds"]["n"] == 10 and abs(c["rr_now"] - 2.5 / 1.5) < 0.01 and c["valid"] is True
    stale = dp.sweet_view(rows, [dict(open_calls[0], mark=102.0)], {}, 1793965016)["calls"][0]
    assert abs(stale["rr_now"] - round(1 / 3, 2)) < 0.01 and stale["valid"] is False                  # most of the move has happened: under the desk's own 1.5R
    short = dp.sweet_view(rows, [dict(open_calls[0], side="short", entry=100.0, stop=101.0, target=97.0, mark=99.5)], {}, 1793965016)["calls"][0]
    assert abs(short["rr_now"] - 2.5 / 1.5) < 0.01 and short["valid"] is True
    assert sv["next_run"] == 1793966820 and dp.sweet_view(rows, [], {}, 1793966820 - 200)["next_run"] == 1793966820      # 12:07 UTC, whichever side of :07 now is
    between = dp.sweet_view(rows, [dict(open_calls[0], mark=100.9)], {}, 1793965016)["calls"][0]                      # (103-100.9) / (100.9-99) = 1.1R: above 1.0, below the desk's 1.5R
    assert 1.0 < between["rr_now"] < 1.5 and between["valid"] is False
    few = rows + [_row(31, "2026-11-02", "long", "SR", "WIN", 0.01, 1.0), _row(32, "2026-11-03", "long", "SR", "LOSS", 0.012, -1.0), _row(33, "2026-11-06", "long", "SR", "open", 0.01, "")]
    sr = dp.sweet_view(few, [dict(open_calls[0], id=33, method="SR")], {}, 1793965016)["calls"][0]
    assert sr["odds_scope"] == "size" and sr["odds"]["n"] == 12 and sr["kind"] == "sweet"                            # only 2 resolved SR calls: fall back to ALL sweet-spot calls
    assert dp.sweet_view(rows, [], {}, 1793966820)["next_run"] == 1793966820 + 3600                                   # exactly at :07 the next run is an hour away
    assert sv["def_stop"] == 0.008 and sv["registered"].startswith("2026-11-06 15:00")
    from backtest import analyst_sweetspot as ss
    assert dp.SWEET_REGISTERED_MS == ss.REGISTERED_MS == sv["registered_ms"] and dp.SWEET_STOP == ss.SWEET_STOP and dp.SCALP_STOP == ss.SCALP_STOP and dp.SWEET_BETS == ss.MIN_BETS   # the page and the scorer cannot drift apart


def test_the_forward_block_uses_the_registered_scorer_and_never_breaks_the_feed():
    import tempfile
    old = dp.ANALYST
    d = Path(tempfile.mkdtemp())
    try:
        dp.ANALYST = d                                                                                # no calls.csv: the scorer cannot load, the block falls back
        assert dp.sweet_view([], [], {}, 1793965016)["forward"]["verdict"].startswith("NOT YET")
        (d / "calls.csv").write_text("id,made_utc,made_ms,symbol,side,method,status,stop_pct,r_net,base_p\n"
                                     "1,2026-11-07 10:07,1794045600000,XRPUSDT,long,SMC,WIN,0.01,1.5,0.2\n"
                                     "2,2026-11-05 10:07,1793872800000,XRPUSDT,long,SMC,WIN,0.01,1.5,0.2\n")             # the second was made BEFORE the registration
        fw = dp.sweet_view([], [], {}, 1793965016)["forward"]
        assert fw["bets"] == 1 and fw["calls"] == 1 and fw["needed"] == 30 and fw["verdict"].startswith("NOT YET - 1 of 30")
    finally:
        dp.ANALYST = old


class _FakeEx:
    """An exchange that has ONE method. Any other call (an order, a transfer, a leverage change) raises AttributeError."""
    def __init__(self, bal=None, boom=None):
        self.bal, self.boom, self.calls = bal, boom, []

    def fetch_balance(self):
        self.calls.append("fetch_balance")
        if self.boom:
            raise self.boom
        return self.bal


_WENV = {"BITGET_RO_KEY": "k-SECRETKEY-1", "BITGET_RO_SECRET": "s-SECRETSEC-2", "BITGET_RO_PASSPHRASE": "p-SECRETPASS-3"}


def _wallet_dir():
    import tempfile
    return Path(tempfile.mkdtemp()) / "wallet.json"


def test_the_wallet_reader_is_inert_without_all_three_read_only_variables():
    seen = []
    for env in ({}, {"BITGET_RO_KEY": "a"}, {"BITGET_RO_KEY": "a", "BITGET_RO_SECRET": "b"}, dict(_WENV, BITGET_RO_PASSPHRASE="")):
        assert dp.wallet_view(env=env, factory=lambda *a: seen.append(a), cache=_wallet_dir()) is None
    assert seen == []                                                  # the exchange was never even constructed
    assert "BITGET_API_KEY" not in dp.WALLET_ENV and all(k.startswith("BITGET_RO_") for k in dp.WALLET_ENV)      # never the demo bot's keys


def test_the_wallet_reader_returns_three_totals_and_makes_exactly_one_call():
    ex = _FakeEx(bal={"USDT": {"total": 250.456, "free": 200.25, "used": 50.2}, "info": [{"accountId": "123456789"}]})
    got = []
    out = dp.wallet_view(env=_WENV, factory=lambda *a: (got.append(a), ex)[1], now=1000, cache=_wallet_dir())
    assert out == dict(t=1000, equity=250.46, available=200.25, used=50.2)                         # no account id, nothing else
    assert got == [("k-SECRETKEY-1", "s-SECRETSEC-2", "p-SECRETPASS-3")] and ex.calls == ["fetch_balance"]
    empty = dp.wallet_view(env=_WENV, factory=lambda *a: _FakeEx(bal={}), now=1000, cache=_wallet_dir())
    assert empty == dict(t=1000, equity=0.0, available=0.0, used=0.0)                              # a wallet with no USDT line is a zero wallet, not a crash


def test_the_wallet_is_cached_for_five_minutes_and_ttl_zero_forces_a_read():
    path = _wallet_dir()
    ex = _FakeEx(bal={"USDT": {"total": 100.0, "free": 90.0, "used": 10.0}})
    f = lambda *a: ex  # noqa: E731
    dp.wallet_view(env=_WENV, factory=f, now=1000, cache=path)
    dp.wallet_view(env=_WENV, factory=f, now=1000 + 299, cache=path)
    assert ex.calls == ["fetch_balance"]                               # inside the five minutes: served from the file
    dp.wallet_view(env=_WENV, factory=f, now=1000 + 300, cache=path)
    assert len(ex.calls) == 2                                          # at five minutes: read again
    dp.wallet_view(env=_WENV, factory=f, now=1000 + 301, cache=path, ttl=0)
    assert len(ex.calls) == 3                                          # the key check always reads


def test_a_failed_read_leaves_only_the_error_class_and_is_not_retried_every_minute():
    import json
    path = _wallet_dir()
    ex = _FakeEx(boom=RuntimeError("bad key k-SECRETKEY-1 secret s-SECRETSEC-2"))
    out = dp.wallet_view(env=_WENV, factory=lambda *a: ex, now=1000, cache=path)
    assert out == dict(t=1000, error="RuntimeError")
    blob = json.dumps(out) + path.read_text()
    assert "SECRET" not in blob                                        # neither the feed value nor the cache file can echo a secret
    again = dp.wallet_view(env=_WENV, factory=lambda *a: ex, now=1100, cache=path)
    assert again["error"] == "RuntimeError" and ex.calls == ["fetch_balance"]          # a bad key is not hammered every minute
    broken = dp.wallet_view(env=_WENV, factory=lambda *a: (_ for _ in ()).throw(ImportError("no ccxt")), now=5000, cache=_wallet_dir())
    assert broken == dict(t=5000, error="ImportError")


def test_the_wallet_reader_contains_no_way_to_trade_or_move_money():
    import ast
    import inspect
    import textwrap
    tree = ast.parse(textwrap.dedent(inspect.getsource(dp.wallet_view)) + "\n" + textwrap.dedent(inspect.getsource(dp._bitget)))
    names = ({n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
             | {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and len(n.value) < 60})        # code, not the docstring
    banned = ("create_order", "cancel", "transfer", "withdraw", "set_leverage", "set_margin", "set_position", "privatepost", "private_post", "sandbox", "paptrading")
    assert [n for n in names if any(b in n.lower() for b in banned)] == []
    calls = [n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    assert calls.count("fetch_balance") == 1                           # the one exchange call
    assert [c for c in calls if c.startswith(("fetch_", "create_", "edit_", "set_", "private_", "privatePost", "privateGet"))] == ["fetch_balance"]


if __name__ == "__main__":
    tests =[v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")

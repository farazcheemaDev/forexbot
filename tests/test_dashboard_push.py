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


if __name__ == "__main__":
    tests =[v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")

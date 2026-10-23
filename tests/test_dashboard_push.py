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


def test_mood_and_crowd_absent_until_their_files_exist():
    import tempfile
    old = dp.MOOD, dp.CROWD
    dp.MOOD, dp.CROWD = Path(tempfile.mkdtemp()) / "none.json", Path(tempfile.mkdtemp())
    try:
        assert dp.mood() is None and dp.crowd({}, int(time.time()), None) is None
    finally:
        dp.MOOD, dp.CROWD = old


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")

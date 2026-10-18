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


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")

"""breadth_rec.py offline: the New York clock, the day split and previous close, the breadth arithmetic by hand, which days count as
complete, the backfill pieces, and a whole run on a fake Yahoo (idempotent; a failed fetch stores nothing). No network."""
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import breadth_rec as br  # noqa: E402


def utc(y, mo, d, h, mi=0):
    return int(datetime(y, mo, d, h, mi, tzinfo=timezone.utc).timestamp())


def chart(pc, bars):
    """A Yahoo-shaped chart result from [(utc seconds, close, volume)]."""
    return {"meta": {"chartPreviousClose": pc}, "timestamp": [b[0] for b in bars],
            "indicators": {"quote": [{"open": [b[1] for b in bars], "high": [b[1] for b in bars], "low": [b[1] for b in bars],
                                      "close": [b[1] for b in bars], "volume": [b[2] for b in bars]}]}}


def test_ny_offset_matches_the_time_zone_database():
    from zoneinfo import ZoneInfo
    ny = ZoneInfo("America/New_York")
    t = datetime(2025, 1, 1, tzinfo=timezone.utc)
    while t < datetime(2028, 1, 1, tzinfo=timezone.utc):
        assert br.ny_offset_h(t) == int(t.astimezone(ny).utcoffset().total_seconds() // 3600), t
        t += timedelta(minutes=30)


def test_split_days_previous_close_and_gaps():
    # 2026-11-19 (EST, UTC-5): 15:58 and 15:59 regular, 16:30 post; 2026-11-20: 04:00 pre, 09:30 regular; one bar with no close
    bars = [(utc(2026, 11, 19, 20, 58), 101.0, 10), (utc(2026, 11, 19, 20, 59), 102.0, 20), (utc(2026, 11, 19, 21, 0), 106.0, 9),
            (utc(2026, 11, 19, 21, 30), 105.0, 5),
            (utc(2026, 11, 20, 9, 0), 104.0, 0), (utc(2026, 11, 20, 14, 30), 103.0, 50), (utc(2026, 11, 20, 14, 31), None, 7)]
    res = chart(100.0, bars)
    res["indicators"]["quote"][0]["open"][1] = None                 # a missing open is filled with the close
    d = br.split_days(res)
    assert list(d) == ["2026-11-19", "2026-11-20"]
    assert d["2026-11-19"]["pc"] == 100.0                           # the first day: chartPreviousClose
    assert d["2026-11-20"]["pc"] == 102.0                           # the 15:59 regular close, not the 16:00 or 16:30 post-market bars
    assert d["2026-11-19"]["o"][1] == 102.0
    assert len(d["2026-11-20"]["t"]) == 2                           # the bar with no close is dropped


def test_breadth_by_hand():
    t0 = utc(2026, 11, 20, 14, 30)                                  # 09:30 New York
    tp, t1, t2, t3 = t0 - 30 * 60, t0 + 60, t0 + 120, t0 + 180      # 09:00 pre-market, 09:31, 09:32, 09:33
    stocks = {"A": {"pc": 10.0, "t": [tp, t0, t1, t2], "c": [11.0, 11.0, 12.0, 12.0], "v": [1000, 100, 200, 300]},
              "B": {"pc": 10.0, "t": [t0, t1, t2], "c": [9.0, 8.0, 9.0], "v": [10, 20, 30]},
              "C": {"pc": 5.0, "t": [t0, t2, t3], "c": [5.0, 4.0, 4.5], "v": [1, 2, 4]}}
    for s in stocks.values():
        s.update(o=s["c"], h=s["c"], l=s["c"])
    rr = br.breadth(stocks)
    assert [x["minute_ny"] for x in rr] == ["09:00", "09:30", "09:31", "09:32", "09:33"]
    r = rr[1:]
    assert rr[0]["vold_day"] == 1000                                # pre-market: A alone, above its close
    assert r[0]["vold_day"] == 100 - 10                             # the open restarts the day's volume (A's 1,000 pre-market left out)
    # 09:33: only C traded (up: state +1); A keeps +1 from 09:31, B +1 from 09:32 -> tick +3 (TICK counts every stock's last direction)
    assert (r[3]["tick"], r[3]["n_traded"], r[3]["vold_min"]) == (3, 1, 4)
    assert (r[3]["adv"], r[3]["dec"]) == (1, 2) and r[3]["vold_day"] == 600 - (60 + 7)
    # 09:30: no earlier close, so no tick yet; A above its close, B below, C equal
    assert (r[0]["tick"], r[0]["adv"], r[0]["dec"], r[0]["vold_min"]) == (0, 1, 1, 0)
    assert r[0]["vold_day"] == 100 - 10
    # 09:31: A up (+1), B down (-1), C did not trade
    assert (r[1]["tick"], r[1]["vold_min"], r[1]["n_traded"]) == (0, 200 - 20, 2)
    assert r[1]["vold_day"] == (100 + 200) - (10 + 20)
    # 09:32: A flat (keeps +1), B up (+1), C down (-1) -> tick +1; C now below its close
    assert (r[2]["tick"], r[2]["adv"], r[2]["dec"], r[2]["add"]) == (1, 1, 2, -1)
    assert r[2]["vold_min"] == 30 - 2
    assert r[2]["vold_day"] == 600 - (60 + 3)
    assert abs(r[2]["trin"] - (1 / 2) / (600 / 63)) < 1e-4


def test_complete_days():
    fri_6pm = datetime(2026, 11, 20, 23, 0, tzinfo=timezone.utc)    # 18:00 New York: Friday's post-market still open
    assert br.complete_days(fri_6pm, 6)[-1] == "2026-11-19"
    fri_810pm = datetime(2026, 11, 21, 1, 10, tzinfo=timezone.utc)  # 20:10 New York
    days = br.complete_days(fri_810pm, 6)
    assert days[-1] == "2026-11-20" and "2026-11-15" not in days and "2026-11-14" not in days
    assert len(days) == 5


def test_backfill_pieces_cut_at_new_york_midnight():
    now = datetime(2026, 11, 22, 2, 0, tzinfo=timezone.utc)
    spans = br.backfill_spans(now)
    edges = [int(x.split("&")[0].split("=")[1]) for x in spans] + [int(spans[-1].split("&")[1].split("=")[1])]
    for e in edges[:-1]:
        assert br.ny_local(e).strftime("%H:%M") == "00:00", br.ny_local(e)
    assert all(b - a <= 7 * 86400 + 3600 for a, b in zip(edges[:-1], edges[1:]))
    assert now.timestamp() - edges[0] < 30 * 86400
    assert edges[-1] == int(now.timestamp())


def test_merge_pieces():
    recs = [{"sym": "A", "pc": None, "t": [1, 2], "o": [1, 2], "h": [1, 2], "l": [1, 2], "c": [1, 2], "v": [1, 1]},
            {"sym": "A", "pc": 9.0, "t": [2, 3], "o": [2, 3], "h": [2, 3], "l": [2, 3], "c": [2, 3], "v": [1, 1]}]
    m = br.merge(recs)
    assert m["A"]["t"] == [1, 2, 3] and m["A"]["c"] == [1, 2, 3] and m["A"]["pc"] == 9.0


def fake_yahoo(calls):
    def fetch(sym, span):
        calls.append((sym, span))
        if sym == "QQQ":
            return None
        base = {"A": 10.0, "B": 20.0, "C": 30.0}[sym]
        bars = []
        for day, hour in ((19, 14), (20, 14)):
            for k in range(5):
                bars.append((utc(2026, 11, day, hour, 30 + k), base + (k if sym != "B" else -k), 100))
        return chart(base, bars)
    return fetch


def test_whole_run_is_idempotent_and_a_failed_fetch_stores_nothing():
    old_fetch, old_pause = br.fetch, br.PAUSE
    br.PAUSE = 0
    try:
        d = Path(tempfile.mkdtemp())
        calls = []
        br.fetch = fake_yahoo(calls)
        now = datetime(2026, 11, 21, 2, 0, tzinfo=timezone.utc)
        br.run(d, now=now, symbols=("A", "B", "C"))
        mn = d / "minute"
        assert sorted(f.name for f in mn.glob("*.csv")) == ["2026-11-19.csv", "2026-11-20.csv"]
        assert sorted(f.name for f in mn.glob("*.empty")) == ["2026-11-16.empty", "2026-11-17.empty", "2026-11-18.empty"]
        assert (d / "raw" / "2026-11-20.json.gz").exists()
        assert all(span == "range=5d" for _, span in calls)
        n = len(calls)
        br.run(d, now=now, symbols=("A", "B", "C"))
        assert len(calls) == n                                      # nothing new: no request at all
        d2 = Path(tempfile.mkdtemp())
        br.fetch = lambda sym, span: None
        br.run(d2, now=now, symbols=("A", "B", "C"))
        assert not list((d2 / "minute").glob("*")) if (d2 / "minute").exists() else True
    finally:
        br.fetch, br.PAUSE = old_fetch, old_pause


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")

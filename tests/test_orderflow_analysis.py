"""orderflow/verify.py and features.py on a hand-built recording with known timings.
Run as a script: python tests/test_orderflow_analysis.py"""
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orderflow import features as ft  # noqa: E402
from orderflow import store, verify  # noqa: E402

PAIR = "XRPUSDT"
LAG_NS = 150_000_000                                                                              # local receive = server stamp + 150 ms


def msg(action, channel, data):
    return json.dumps({"action": action, "arg": {"instType": "USDT-FUTURES", "channel": channel, "instId": PAIR}, "data": data, "ts": 0})


def lv(rows):
    return [[str(p), str(s)] for p, s in rows]


def book_msg(action, ts, seq, pseq, bids=(), asks=()):
    return ts, msg(action, "books", [dict(bids=lv(bids), asks=lv(asks), ts=str(ts), seq=seq, pseq=pseq)])


def trade_msg(action, ts, tid, price, size, side):
    return ts, msg(action, "trade", [dict(ts=str(ts), price=str(price), size=str(size), side=side, tradeId=tid)])


def recording(extra=(), drop=()):
    """Snapshot at 10_000, an update every 100 ms (the one stamped EXACTLY 11_000 changes the bid size), and three trades (10_500, 10_900, and one stamped exactly 11_000)."""
    frames = [book_msg("snapshot", 10_000, 100, 0, bids=[(100.00, 600), (99.99, 900), (99.97, 1000)], asks=[(100.01, 500), (100.02, 800), (100.04, 1000)])]
    seq = 100
    for ts in range(10_100, 16_100, 100):
        bids = [(100.00, 1200)] if ts == 11_000 else []
        frames.append(book_msg("update", ts, seq + 1, seq, bids=bids))
        seq += 1
    frames += [trade_msg("update", 10_500, "t1", 100.01, 10, "buy"), trade_msg("update", 10_900, "t2", 100.00, 20, "sell"), trade_msg("update", 11_000, "t3", 100.01, 5, "buy")]
    frames += list(extra)
    frames = [f for f in frames if f not in drop]
    frames.sort(key=lambda f: f[0])
    return [(ts * 1_000_000 + LAG_NS, raw) for ts, raw in frames]


def write(root, frames, pair=PAIR):
    w = store.RawWriter(Path(root) / "raw", pair)
    for recv_ns, raw in frames:
        w.write(recv_ns, raw)
    w.close()


def row(df, t):
    return df[df.t == t].iloc[0]


def numbers(df):
    return df.drop(columns="t").to_numpy(float)


# ------------------------------------------------------------------ features: the strict timestamp rule

def test_a_message_or_trade_stamped_exactly_on_the_cut_is_not_in_that_row_but_is_in_the_next():
    df = ft.grid_from_frames(recording())
    r = row(df, 11_000)
    assert r.bid == 100.00 and r.ask == 100.01 and abs(r.mid - 100.005) < 1e-12
    B1, A1 = 100.00 * 600, 100.01 * 500                                                           # the bid-size change is stamped 11_000: NOT visible at T = 11_000
    assert abs(r.imb1 - (B1 - A1) / (B1 + A1)) < 1e-12
    s, a = 100.01 * 10 - 100.00 * 20, 100.01 * 10 + 100.00 * 20                                  # trades t1, t2 only: t3 (stamped 11_000) is excluded
    assert abs(r.flow_1s - s / a) < 1e-12 and abs(r.flow_5s - s / a) < 1e-12
    r2 = row(df, 12_000)
    B1b = 100.00 * 1200
    assert abs(r2.imb1 - (B1b - A1) / (B1b + A1)) < 1e-12                                        # now the book change is in
    assert math.isnan(r2.flow_1s)                                                                  # the 1 s window (11_000, 12_000) is open at 11_000: t3 is not inside it ...
    s5, a5 = s + 100.01 * 5, a + 100.01 * 5
    assert abs(r2.flow_5s - s5 / a5) < 1e-12 and abs(r2.flow_60s - s5 / a5) < 1e-12              # ... but it is in the 5 s and 60 s windows


def test_lag_moves_the_cut_back_and_book_age_measures_staleness():
    df = ft.grid_from_frames(recording(), lag_ms=500)
    r = row(df, 11_000)                                                                           # cut = 10_500: t1 (stamped 10_500) and t2 are NOT before it
    assert math.isnan(r.flow_1s) and r.book_age_ms == 10_500 - 10_400                              # the last book message stamped before 10_500 is the one at 10_400
    r0 = row(ft.grid_from_frames(recording()), 11_000)
    assert r0.book_age_ms == 11_000 - 10_900


def test_bands_report_nan_where_the_recorded_depth_does_not_reach():
    r = row(ft.grid_from_frames(recording()), 11_000)
    assert not math.isnan(r.bid_usd_2) and not math.isnan(r.ask_usd_2)                           # levels sit 3.5bp out: a 2bp band is covered
    assert math.isnan(r.bid_usd_5) and math.isnan(r.imb_band5) and math.isnan(r.bid_usd_25)      # a 5bp band is not
    assert abs(r.bid_usd_2 - (100.00 * 600 + 99.99 * 900)) < 1e-9


def test_no_row_changes_if_the_future_is_truncated_or_scrambled():
    full = ft.grid_from_frames(recording())
    part = ft.grid_from_frames([f for f in recording() if f[0] // 1_000_000 < 13_650])      # only what was stamped before 13_500 has arrived
    common = part.t.tolist()
    assert len(common) >= 3 and common == full.t.tolist()[:len(common)]
    assert np.allclose(numbers(part), numbers(full[full.t.isin(common)]), equal_nan=True)
    scr = recording(extra=[trade_msg("update", 11_300, "t9", 100.01, 99999, "sell"), book_msg("update", 11_500, 115, 114, bids=[(100.00, 99999)])],
                    drop=[book_msg("update", 11_500, 115, 114)])                                  # the future is CHANGED (not deleted: a deleted message is a gap)
    scrambled = ft.grid_from_frames(scr)
    assert np.allclose(row(full, 11_000).drop("t").to_numpy(float), row(scrambled, 11_000).drop("t").to_numpy(float), equal_nan=True)   # its cut is before 11_300: identical
    assert abs(row(full, 12_000).flow_5s - row(scrambled, 12_000).flow_5s) > 0.5                                                          # positive control: the changed trade IS in the next row


def test_no_row_is_emitted_while_the_book_is_not_ready():
    """Before the first snapshot is applied, and between a broken chain and the next snapshot, there is no book: a row would be invented data."""
    df = ft.grid_from_frames(recording(), lag_ms=1500)                                              # T = 11_000 needs the book as of 9_500: before the snapshot
    assert 11_000 not in df.t.tolist() and 12_000 in df.t.tolist()
    frames = [book_msg("snapshot", 10_000, 100, 0, bids=[(100.00, 600), (99.99, 900), (99.97, 1000)], asks=[(100.01, 500), (100.02, 800), (100.04, 1000)])]
    seq = 100
    for ts in range(10_100, 13_001, 100):
        frames.append(book_msg("update", ts, seq + 1, seq))
        seq += 1
    frames.append(book_msg("update", 13_050, 999, 998))                                              # the chain breaks here ...
    frames.append(book_msg("snapshot", 14_050, 500, 0, bids=[(100.00, 700), (99.99, 900), (99.97, 1000)], asks=[(100.01, 500), (100.02, 800), (100.04, 1000)]))
    seq = 500
    for ts in range(14_100, 16_001, 100):                                                           # ... and a new chain starts at the next snapshot
        frames.append(book_msg("update", ts, seq + 1, seq))
        seq += 1
    frames = [(ts * 1_000_000 + LAG_NS, raw) for ts, raw in frames]
    t = ft.grid_from_frames(frames).t.tolist()
    assert 13_000 in t and 14_000 not in t and 15_000 in t and 16_000 in t                          # no row for the unsynced second; rows resume after the snapshot
    assert row(ft.grid_from_frames(frames), 15_000).imb1 == (100.00 * 700 - 100.01 * 500) / (100.00 * 700 + 100.01 * 500)


def test_a_day_counts_only_if_the_book_was_ready_and_fresh_for_most_of_it():
    import pandas as pd
    day0 = int(pd.Timestamp("2026-11-01", tz="UTC").timestamp() * 1000)
    t = list(range(day0, day0 + 86_400_000, 1000))
    df = pd.DataFrame({"t": t, "book_age_ms": 100.0})
    cov = ft.day_coverage(df)
    assert len(cov) == 1 and abs(cov.iloc[0] - 1.0) < 1e-12
    df.loc[: 8_639, "book_age_ms"] = 5_000.0                                                         # the first 10% of the day was stale
    assert abs(ft.day_coverage(df).iloc[0] - 0.9) < 1e-9
    short = pd.DataFrame({"t": t[: 3 * 3600], "book_age_ms": 100.0})                                  # only three hours were recorded
    assert abs(ft.day_coverage(short).iloc[0] - 3 / 24) < 1e-9 and ft.day_coverage(short).iloc[0] < 0.9
    assert ft.day_coverage(pd.DataFrame({"t": [], "book_age_ms": []})).empty


def test_trades_in_the_snapshot_and_the_updates_are_counted_once():
    snap_t = trade_msg("snapshot", 10_400, "t1", 100.01, 10, "buy")                                # the same trade id appears again: de-duplicated
    a = ft.grid_from_frames(recording())
    b = ft.grid_from_frames(recording(extra=[snap_t]))
    assert np.allclose(numbers(a), numbers(b), equal_nan=True)


# ------------------------------------------------------------------ verify

def test_verify_counts_cadence_lag_trades_and_depth():
    td = tempfile.mkdtemp()
    try:
        write(td, recording())
        r = verify.verify_pair(Path(td) / "raw", PAIR)
        assert r["snapshots"] == 1 and r["updates"] == 60 and r["gaps"] == 0 and r["crossed"] == 0 and r["trades"] == 3 and r["trade_dupes"] == 0 and r["bad"] == 0
        assert r["gap_ms"] == (100, 100, 100) and abs(r["lag_books_ms"][1] - 150) < 1e-6 and r["snap_depth"] == (3, 3)
        assert abs(r["snap_cover_bp"][0] - (100.005 - 99.97) / 100.005 * 1e4) < 0.01
        assert r["end_levels"] == 6 and abs(r["trade_usd"]["buy"] - 100.01 * 15) < 1e-9 and r["trade_usd"]["sell"] == 2000.0
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_verify_sees_a_gap_and_a_duplicate_trade():
    td = tempfile.mkdtemp()
    try:
        write(td, recording(extra=[book_msg("update", 11_050, 999, 998), trade_msg("update", 11_100, "t1", 100.01, 10, "buy")]))
        r = verify.verify_pair(Path(td) / "raw", PAIR)
        assert r["gaps"] == 1 and r["unsynced"] > 0 and r["trade_dupes"] == 1
    finally:
        shutil.rmtree(td, ignore_errors=True)


def test_verify_sees_a_crossed_book():
    td = tempfile.mkdtemp()
    try:
        extra = [book_msg("update", 16_150, 161, 160, bids=[(100.02, 5)])]                          # a bid above the best ask, with a valid chain position
        write(td, recording(extra=extra))
        assert verify.verify_pair(Path(td) / "raw", PAIR)["crossed"] >= 1
    finally:
        shutil.rmtree(td, ignore_errors=True)


def snap_frame(ts, seq, bids, asks):
    return ts, msg("snapshot", "books", [dict(bids=lv(bids), asks=lv(asks), ts=str(ts), seq=seq, pseq=0)])


def audit_result(frames_main, audit_snaps):
    td = tempfile.mkdtemp()
    try:
        write(td, frames_main)
        w = store.RawWriter(Path(td) / "audit", PAIR)
        for ts, raw in audit_snaps:
            w.write(ts * 1_000_000 + 300_000_000, raw)
        w.close()
        return verify.verify_pair(Path(td) / "raw", PAIR)["audit"]
    finally:
        shutil.rmtree(td, ignore_errors=True)


AT_115_BIDS = [(100.00, 1200), (99.99, 900), (99.97, 1000)]          # the synthetic book after the message with seq 115 (stamped 11_500)
AT_115_ASKS = [(100.01, 500), (100.02, 800), (100.04, 1000)]


def test_a_snapshot_at_a_seq_in_the_stream_must_equal_the_rebuilt_book_exactly():
    same = snap_frame(11_500, 115, AT_115_BIDS, AT_115_ASKS)
    r = audit_result(recording(), [same])
    assert r == dict(exact=1, differ=0, approx_same=0, approx_diff=0, outside=0), r
    off_by_one_size = snap_frame(11_500, 115, [(100.00, 1201)] + AT_115_BIDS[1:], AT_115_ASKS)
    assert audit_result(recording(), [off_by_one_size]) == dict(exact=0, differ=1, approx_same=0, approx_diff=0, outside=0)
    extra_level = snap_frame(11_500, 115, AT_115_BIDS + [(99.90, 5)], AT_115_ASKS)                 # a level the rebuilt book does not have
    assert audit_result(recording(), [extra_level])["differ"] == 1
    before_change = snap_frame(10_500, 105, [(100.00, 600)] + AT_115_BIDS[1:], AT_115_ASKS)         # an earlier seq is checked against the book AT that seq (before the 11_000 change)
    assert audit_result(recording(), [before_change])["exact"] == 1


def test_a_seq_between_two_messages_is_compared_with_the_book_before_it_and_labelled_approximate():
    frames = [book_msg("snapshot", 10_000, 100, 0, bids=[(100.00, 600)], asks=[(100.01, 500)]),
              book_msg("update", 10_100, 110, 100, bids=[(100.00, 700)]),
              book_msg("update", 10_200, 120, 110, bids=[(100.00, 800)])]
    frames = [(ts * 1_000_000 + LAG_NS, raw) for ts, raw in frames]
    at_110 = snap_frame(10_150, 115, [(100.00, 700)], [(100.01, 500)])                               # seq 115 lies between 110 and 120: the book after 110 is the nearest earlier state
    assert audit_result(frames, [at_110]) == dict(exact=0, differ=0, approx_same=1, approx_diff=0, outside=0)
    not_that = snap_frame(10_150, 115, [(100.00, 999)], [(100.01, 500)])
    assert audit_result(frames, [not_that])["approx_diff"] == 1


def test_snapshots_older_or_newer_than_the_recording_are_outside_not_counted_as_failures():
    old = snap_frame(5_000, 50, AT_115_BIDS, AT_115_ASKS)
    new = snap_frame(99_000, 9_999, AT_115_BIDS, AT_115_ASKS)
    assert audit_result(recording(), [old, new]) == dict(exact=0, differ=0, approx_same=0, approx_diff=0, outside=2)
    both = audit_result(recording(), [snap_frame(11_500, 115, AT_115_BIDS, AT_115_ASKS), old, new])
    assert both["exact"] == 1 and both["outside"] == 2


def test_trade_ordering_is_judged_per_message_and_newest_first_batches_are_just_counted():
    td = tempfile.mkdtemp()
    try:
        batch_desc = (10_800, msg("update", "trade", [dict(ts="10800", price="100.0", size="1", side="buy", tradeId="a"), dict(ts="10700", price="100.0", size="1", side="buy", tradeId="b")]))
        batch_asc = (10_900, msg("update", "trade", [dict(ts="10850", price="100.0", size="1", side="sell", tradeId="c"), dict(ts="10900", price="100.0", size="1", side="sell", tradeId="d")]))
        late = (11_000, msg("update", "trade", [dict(ts="10600", price="100.0", size="1", side="buy", tradeId="e")]))         # a whole message older than the one before
        frames = [book_msg("snapshot", 10_000, 100, 0, bids=[(100.00, 600)], asks=[(100.01, 500)]), batch_desc, batch_asc, late]
        write(td, [(ts * 1_000_000 + LAG_NS, raw) for ts, raw in frames])
        r = verify.verify_pair(Path(td) / "raw", PAIR)
        assert r["trades"] == 5 and r["multi_trade_msgs"] == 2 and r["newest_first_msgs"] == 1 and r["trade_disorder"] == 1
    finally:
        shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")

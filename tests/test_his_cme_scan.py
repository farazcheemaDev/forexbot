"""Tests for backtest/his_cme_scan.py: the race label (lag, sign, horizon), look-ahead-free features, thinning, bucket accuracy and the within-window evaluation that replaced the biased pooled AUC.

Run as a script (no pytest on this PC):  python tests/test_his_cme_scan.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.his_cme_scan as sc  # noqa: E402


def test_race_label_is_plus_one_for_the_upper_barrier_first_and_minus_one_for_the_lower():
    up = np.r_[np.full(5, 100.0), np.full(10, 108.0)]                  # entry at i+2 = 100, then 108 (+8): the up barrier
    dn = np.r_[np.full(5, 100.0), np.full(10, 92.0)]
    lab_u = sc.race_labels(up, lag=2, horizon=5, t=7.0)
    lab_d = sc.race_labels(dn, lag=2, horizon=5, t=7.0)
    assert lab_u[0] == 1 and lab_d[0] == -1
    both = np.r_[np.full(5, 100.0), 108.0, 108.0, 90.0, 90.0, 90.0, 90.0, 90.0]
    assert sc.race_labels(both, lag=2, horizon=5, t=7.0)[0] == 1        # +8 comes before -10
    flat = np.full(20, 100.0)
    assert sc.race_labels(flat, lag=2, horizon=5, t=7.0)[0] == 0


def test_default_settings_are_a_two_second_lag_a_seven_point_barrier_and_a_240_second_horizon():
    n = 400
    pre = np.full(n, 100.0)
    pre[1:] = 108.0                                                     # the jump happens at second 1, BEFORE the default entry at second 2: nothing to win afterwards
    assert sc.race_labels(pre)[0] == 0
    small = np.full(n, 100.0)
    small[10:] = 106.0                                                  # +6 is under the 7-point barrier
    assert sc.race_labels(small)[0] == 0
    inside = np.full(n, 100.0)
    inside[242:] = 108.0                                                # the last second inside the window: entry second 2 + 240 seconds = index 242
    outside = np.full(n, 100.0)
    outside[243:] = 108.0
    assert sc.race_labels(inside)[0] == 1 and sc.race_labels(outside)[0] == 0


def test_a_tail_shorter_than_the_horizon_is_not_labelled_even_if_it_already_touched_a_barrier():
    mid = np.r_[np.full(7, 100.0), 108.0, 108.0]
    lab = sc.race_labels(mid, lag=2, horizon=4, t=7.0)
    assert lab[4] == 0 and lab[5] == 0


def test_big_trades_only_count_from_five_lots_up_and_sells_flip_the_flow_sign():
    t0 = 1_700_000_000 * 10**9
    n = 100
    sec_ns = t0 + np.arange(n) * 10**9
    mid = np.full(n, 100.0)
    book = pd.DataFrame({**{f"bid_sz_{i:02d}": np.ones(n) for i in range(10)}, **{f"ask_sz_{i:02d}": np.ones(n) for i in range(10)}})
    tns = np.array([t0 + 40 * 10**9, t0 + 41 * 10**9, t0 + 42 * 10**9])
    f = sc.window_features(mid, book, tns, np.array([4.0, 5.0, 6.0]), np.array([1.0, -1.0, -1.0]), sec_ns, np.zeros(n))
    r = f.iloc[45]
    assert r["big30"] == -11.0                                            # 5 and 6 lots count (both sells), the 4-lot buy does not
    assert r["flow30"] == 4.0 - 5.0 - 6.0 and r["nflow30"] < 0 and r["lastaggr"] == -1.0
    assert r["ntr30"] == 3.0 and r["ntr5"] == 2.0                          # the window is (t-5 s, t]: the trade stamped exactly 5 s back is outside it


def test_a_jump_before_the_entry_second_does_not_count_and_short_tails_are_unlabelled():
    mid = np.r_[100.0, 108.0, 108.0, 108.0, 108.0, 108.0, 108.0, 108.0, 108.0]
    lab = sc.race_labels(mid, lag=2, horizon=4, t=7.0)
    assert lab[0] == 0                                                  # the move to 108 happened at second 1, before the entry at second 2
    assert (lab[-3:] == 0).all()                                        # no room for a full horizon after the entry


def mk_window(n=400, seed=3):
    rng = np.random.default_rng(seed)
    t0 = 1_700_000_000 * 10**9
    sec_ns = t0 + np.arange(n) * 10**9
    mid = 100 + np.cumsum(rng.normal(0, 0.5, n))
    cols = {f"bid_sz_{i:02d}": rng.integers(1, 20, n).astype(float) for i in range(10)}
    cols.update({f"ask_sz_{i:02d}": rng.integers(1, 20, n).astype(float) for i in range(10)})
    book = pd.DataFrame(cols)
    m = 3000
    tns = np.sort(t0 + rng.integers(0, n * 10**9, m))
    tsize = rng.integers(1, 9, m).astype(float)
    taggr = rng.choice([-1.0, 1.0], m)
    return mid, book, tns, tsize, taggr, sec_ns, np.arange(n) / 60.0


def test_features_at_second_k_never_use_data_after_k():
    mid, book, tns, tsize, taggr, sec_ns, etm = mk_window()
    base = sc.window_features(mid, book, tns, tsize, taggr, sec_ns, etm)
    k = 250
    mid2, book2 = mid.copy(), book.copy()
    mid2[k + 1:] += 40.0
    book2.iloc[k + 1:] *= 5.0
    late = tns > sec_ns[k]
    tsize2, taggr2 = tsize.copy(), taggr.copy()
    tsize2[late] *= 7.0
    taggr2[late] = -taggr2[late]
    alt = sc.window_features(mid2, book2, tns, tsize2, taggr2, sec_ns, etm)
    a, b = base.iloc[k].to_numpy(), alt.iloc[k].to_numpy()
    assert np.allclose(a, b, equal_nan=True), [c for c, x, y in zip(base.columns, a, b) if not (x == y or (np.isnan(x) and np.isnan(y)))]
    assert not np.allclose(base.iloc[k + 5].to_numpy(), alt.iloc[k + 5].to_numpy(), equal_nan=True)         # while later rows, of course, do move


def test_features_are_signed_up_is_positive_buy_aggression_is_positive_bid_heavy_book_is_positive():
    mid, book, tns, tsize, taggr, sec_ns, etm = mk_window()
    i = 200
    mid[i] = mid[i - 5] + 3.0
    for c in book.columns:
        book.loc[i, c] = 10.0 if c.startswith("bid_") else 1.0
    taggr = np.ones_like(taggr)                                         # every trade is a buy
    f = sc.window_features(mid, book, tns, tsize, taggr, sec_ns, etm).iloc[i]
    assert abs(f["m5"] - 3.0) < 1e-12
    assert f["imb1"] > 0.8 and f["imb10"] > 0.8
    assert f["flow30"] > 0 and f["nflow30"] > 0.99 and f["lastaggr"] == 1.0


def test_flows_count_a_trade_stamped_exactly_on_the_second_and_exclude_the_next_second():
    t0 = 1_700_000_000 * 10**9
    sec_ns = t0 + np.arange(100) * 10**9
    tns = np.array([t0 + 50 * 10**9, t0 + 51 * 10**9 + 1])
    mid = np.full(100, 100.0)
    book = pd.DataFrame({**{f"bid_sz_{i:02d}": np.ones(100) for i in range(10)}, **{f"ask_sz_{i:02d}": np.ones(100) for i in range(10)}})
    f = sc.window_features(mid, book, tns, np.array([3.0, 5.0]), np.array([1.0, 1.0]), sec_ns, np.zeros(100))
    assert f["flow1"].iloc[50] == 3.0                                    # the trade at exactly second 50 is in second 50's one-second window
    assert f["flow1"].iloc[51] == 0.0 and f["flow2"].iloc[51] == 3.0     # and the trade a nanosecond after second 51 is not yet visible at 51
    assert f["flow1"].iloc[52] == 5.0


def test_thin_keeps_the_most_confident_event_and_drops_neighbours_in_the_same_window_only():
    conf = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.65, 0.45, 0.3, 0.95])
    win = np.array([0, 0, 0, 1, 0, 1, 0, 2, 2])
    sec = np.array([100, 130, 170, 130, 400, 1000, 1030, 500, 520])
    kept = sc.thin(conf, win, sec, gap=60)
    assert sorted(kept) == [0, 2, 3, 4, 5, 6, 8]
    assert 8 in kept and 7 not in kept                                   # of two events 20 s apart the MORE confident one stays, whichever comes first in the array
    assert 1 not in kept                                                  # 130 is within 60 s of 100 in the same window
    assert 6 in kept and 5 in kept                                        # 1000 (window 1) and 1030 (window 0) are 30 s apart but in different windows: both stay


def test_bucket_accuracy_uses_the_most_confident_share_and_the_sign_of_the_call():
    p = np.array([0.95, 0.05, 0.9, 0.1, 0.55, 0.45, 0.5, 0.52, 0.48, 0.51])
    y = np.array([1, -1, -1, -1, 1, -1, 1, 1, -1, -1])
    win, sec = np.arange(10), np.arange(10) * 100
    n, acc, nt, at = sc.bucket_accuracy(p, y, win, sec, 0.4)
    assert n == 4 and abs(acc - 0.75) < 1e-12                             # the four most confident: 0.95 right, 0.05 right, 0.9 wrong, 0.1 right
    assert nt == 4 and abs(at - 0.75) < 1e-12


def test_centring_and_the_within_window_auc_ignore_a_per_window_level_shift():
    rng = np.random.default_rng(0)
    win = np.repeat(np.arange(6), 400)
    yb = rng.integers(0, 2, len(win))
    signal = yb * 0.2 + rng.normal(0, 0.1, len(win))                     # a real, ranking signal inside every window
    shift = np.repeat(rng.normal(0, 0.5, 6), 400)                         # a window-specific level that has nothing to do with the outcome
    p = 0.5 + signal + shift
    aucs = sc.mean_window_auc(yb, p, win)
    assert len(aucs) == 6 and np.mean(aucs) > 0.9                         # the shift does not hide the within-window ranking
    from sklearn.metrics import roc_auc_score
    assert roc_auc_score(yb, p) < np.mean(aucs) - 0.1                     # while the pooled AUC does get hurt by it
    base = np.repeat(np.array([0.4, 0.6]), 3)
    assert np.allclose(sc.centre(np.array([0.4, 0.6]), np.array([0.4, 0.6])), 0.5)
    assert len(sc.mean_window_auc(np.array([1] * 300), np.zeros(300), np.zeros(300, int))) == 0       # a window with one outcome has no AUC


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")

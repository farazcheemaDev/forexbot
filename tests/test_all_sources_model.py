"""Offline tests for backtest/all_sources_model.py - every new feature family's timing (nothing after the day's close, the unlock
schedule only ahead), the grid helpers, the market block's causal percentile, the planted feature, the training mask, the verdict,
and that gradient boosting finds a link between a coin feature and a market feature when one exists. Synthetic data only.

    python tests/test_all_sources_model.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import all_sources_model as am  # noqa: E402
from backtest import indicator_model as im  # noqa: E402

D = np.arange(np.datetime64("2024-01-01"), np.datetime64("2024-01-21"))       # 20 days


def test_trailing_and_leading_sums_by_hand():
    a = np.array([[1.0], [2.0], [3.0], [4.0], [5.0]])
    assert np.allclose(am.trailing_sum(a, 2)[:, 0], [1, 3, 5, 7, 9])
    assert np.allclose(am.trailing_sum(a, 7)[:, 0], [1, 3, 6, 10, 15])               # window longer than the history
    assert np.allclose(am.leading_sum(a, 2)[:, 0], [5, 7, 9, 5, 0])                  # rows t+1 .. t+2, never row t
    assert np.allclose(am.leading_sum(a, 1)[:, 0], [2, 3, 4, 5, 0])


def test_grids_drop_unknown_coins_and_off_grid_days():
    g = am.to_grid(D, ["A", "B"], ["2024-01-02", "2024-01-02", "2023-12-31", "2024-01-05"], ["A", "Z", "A", "B"], [1.0, 2.0, 3.0, 4.0])
    assert g[1, 0] == 1.0 and g[4, 1] == 4.0 and np.isfinite(g).sum() == 2
    c = am.count_grid(D, ["A", "B"], ["2024-01-02", "2024-01-02", "2024-01-02"], ["A", "A", "B"], [1.0, 2.0, 5.0])
    assert c[1, 0] == 3.0 and c[1, 1] == 5.0 and c.sum() == 8.0


def test_funding_day_t_holds_only_its_own_settlements():
    f = pd.DataFrame({"time": ["2024-01-02 00:00:00.000", "2024-01-02 08:00:00.000", "2024-01-02 16:00:00.000",
                               "2024-01-03 00:00:00.007", "2024-01-04 08:00:00.000", "2024-01-05 08:00:00.000"],
                      "rate": [0.001, 0.002, 0.003, 0.9, 0.5, 0.2]})
    out = am.funding_panels(D, ["A"], loader=lambda s: f)
    d1 = out["fund1"][:, 0]
    assert np.isnan(d1[0]) and abs(d1[1] - 0.002) < 1e-12 and abs(d1[2] - 0.9) < 1e-12      # 01-03 00:00 is day 01-03's
    assert np.isnan(out["fund7"][1, 0]) and abs(out["fund7"][3, 0] - np.mean([0.002, 0.9, 0.5])) < 1e-12
    assert abs(out["fund_chg"][4, 0] - (0.2 - np.mean([0.002, 0.9, 0.5, 0.2]))) < 1e-12


def test_news_counts_land_on_the_utc_day_and_never_early():
    ev = pd.DataFrame({"t": pd.to_datetime(["2024-01-02 23:59:59", "2024-01-03 00:00:01", "2024-01-02 12:00:00", "2024-01-02 13:00:00",
                                            "2024-01-10 09:00:00"]),
                       "etype": ["other", "list_spot", "other", "hack", "monitoring_tag"],
                       "coins": ["A", "A", "", "A,B", "B"]})
    tone = [0.2, 0.6, -0.5, 0.4, 0.0]
    nf, mn, mt = am.news_panels(D, ["A", "B"], ev, tone)
    assert nf["news1"][1, 0] == 2 and nf["news1"][2, 0] == 1 and nf["news1"][1, 1] == 1        # 'A,B' counts for both
    assert nf["listing7"][1, 0] == 0 and nf["listing7"][2, 0] == 1 and nf["listing7"][8, 0] == 1 and nf["listing7"][9, 0] == 0
    assert nf["hack7"][1, 1] == 1 and nf["hack7"][0, 1] == 0
    assert nf["delist7"][9, 1] == 1 and nf["delist7"][8, 1] == 0
    assert abs(nf["tone7"][1, 0] - 0.3) < 1e-12 and abs(nf["tone7"][2, 0] - 0.4) < 1e-12        # (0.2 + 0.4) / 2, then + 0.6
    assert np.isnan(nf["tone7"][0, 0])
    assert mn[1] == 1 and mn.sum() == 1 and abs(mt[1] + 0.5) < 1e-12 and np.isnan(mt[0])        # the untagged headline is market-wide
    assert nf["news7"][2, 0] == 3 and abs(nf["news_spike"][2, 0] - np.log(4 / (3 * 7 / 30 + 1))) < 1e-12


def test_unlocks_read_the_schedule_ahead_and_the_past_behind():
    rows = [dict(sym="XYZ", ts=int(pd.Timestamp("2024-01-10 14:00").timestamp()), tokens=5.0, kind="cliff", max_supply=100.0,
                 adj_supply=None),
            dict(sym="PEPE", ts=int(pd.Timestamp("2024-01-05").timestamp()), tokens=1.0, kind="cliff", max_supply=50.0, adj_supply=200.0),
            dict(sym="XYZ", ts=int(pd.Timestamp("2024-01-12").timestamp()), tokens=99.0, kind="linear", max_supply=100.0, adj_supply=None)]
    u = am.unlock_panels(D, ["XYZUSDT", "1000PEPEUSDT", "BTCUSDT"], rows)
    nx, la = u["unl_next7"][:, 0], u["unl_last7"][:, 0]
    k = 9                                                                               # 2024-01-10
    assert np.allclose(nx[k - 7:k], 5.0) and nx[k] == 0 and nx[k - 8] == 0              # known from 7 days before, not on the day
    assert np.allclose(la[k:k + 7], 5.0) and la[k + 7] == 0 and la[k - 1] == 0
    assert abs(u["unl_next7"][3, 1] - 0.5) < 1e-12                                     # adj_supply wins over max_supply; 1000-prefix
    assert u["unl_next7"][:, 2].sum() == 0                                              # linear vesting is not a cliff


def test_news_types_partnership_whale_treasury_and_unlock_headlines():
    ev = pd.DataFrame({"t": pd.to_datetime(["2024-01-04 10:00", "2024-01-04 11:00", "2024-01-05 11:00", "2024-01-06 11:00"]),
                       "etype": ["partnership", "treasury_buy", "whale", "unlock"], "coins": ["A", "A", "A", "A"]})
    nf, _, _ = am.news_panels(D, ["A"], ev, [0.0] * 4)
    assert nf["partner7"][3, 0] == 1 and nf["whale7"][3, 0] == 1 and nf["whale7"][4, 0] == 2 and nf["unlocknews7"][5, 0] == 1
    assert nf["unlocknews7"][4, 0] == 0 and nf["partner7"][2, 0] == 0


def test_size_liquidity_and_age():
    C = np.full((40, 2), 10.0)
    C[:3, 1] = np.nan
    V = np.tile(np.arange(1.0, 41)[:, None], (1, 2))
    s = am.size_panels(C, V)
    assert np.isnan(s["liq30"][18, 0]) and abs(s["liq30"][19, 0] - np.log(np.mean(np.arange(1.0, 21)))) < 1e-12   # 20 days needed
    assert abs(s["liq30"][39, 0] - np.log(np.mean(np.arange(11.0, 41)))) < 1e-12                                  # a 30-day mean
    assert s["age"][0, 0] == 0 and s["age"][5, 0] == 5 and np.isnan(s["age"][2, 1]) and s["age"][3, 1] == 0


def test_fear_and_greed_day_t_reads_the_value_dated_t(tmp=Path(__file__).resolve().parent / "_fng_tmp.csv"):
    pd.DataFrame({"Unnamed: 0": ["2024-01-02", "2024-01-03"], "fng": [30.0, 70.0]}).to_csv(tmp, index=False)
    try:
        v = am.load_fng(D, tmp)
    finally:
        tmp.unlink()
    assert np.isnan(v[0]) and v[1] == 30.0 and v[2] == 70.0 and np.isnan(v[3])


def test_the_market_raw_values_by_hand():
    T, N = 40, 6
    C = np.full((T, N), 100.0)
    C[:, 0] = 100 * 1.01 ** np.arange(T)                                                  # coin 0 = 'BTC', +1% a day
    C[30:, 1] = 125.0                                                                     # up 25% vs 30 days ago: in the fuel
    C[30:, 2] = 115.0                                                                     # up 15%: not in it
    lc = pd.DataFrame(np.log(C))
    price = {"ret30": (lc - lc.shift(30)).to_numpy(), "ret7": (lc - lc.shift(7)).to_numpy()}
    M = np.ones((T, N), bool)
    r = am.market_raw(C, M, price, np.zeros((T, N)), np.zeros(T), np.zeros(T), np.zeros(T), 0)
    assert abs(r["btc_ret7"][20] - 7 * np.log(1.01)) < 1e-12 and np.isnan(r["btc_ret7"][6])
    assert abs(r["btc_ret30"][35] - 30 * np.log(1.01)) < 1e-12
    assert abs(r["fuel"][35] - 2 / 6) < 1e-12                                             # 'BTC' (+34.8% in 30 days) and coin 1 (+25%)
    assert np.isnan(r["fuel"][29]) and np.isnan(r["btc_ma50"][39])                        # 30 days of history / 50 days needed
    assert abs(r["breadth20"][35] - 3 / 6) < 1e-12                                        # BTC, coins 1 and 2 above their 20-day mean


def test_the_market_block_never_reads_a_later_day():
    rng = np.random.default_rng(9)
    T, N = 160, 8
    dates = np.arange(np.datetime64("2023-01-01"), np.datetime64("2023-01-01") + np.timedelta64(T, "D"))

    def block(C):
        lc = pd.DataFrame(np.log(C))
        price = {"ret30": (lc - lc.shift(30)).to_numpy(), "ret7": (lc - lc.shift(7)).to_numpy()}
        fund = np.cumsum(rng.standard_normal((T, N)), 0) * 0 + C / 1e4
        return am.market_block(dates, C, np.ones((T, N), bool), price, fund, np.arange(T, dtype=float), np.sin(np.arange(T)),
                               np.arange(T, dtype=float), 0)

    C = 100 * np.exp(np.cumsum(rng.normal(0, 0.03, (T, N)), 0))
    a = block(C)
    C2 = C.copy()
    C2[121:] *= np.exp(rng.normal(0, 0.5, (T - 121, N)))
    b = block(C2)
    for k in am.MARKET:
        assert np.allclose(a[k][:121], b[k][:121], equal_nan=True), k
        assert np.isfinite(a[k][130:]).all(), k
    assert not np.allclose(a["btc_ret7"][121:], b["btc_ret7"][121:])                         # the test can see a change
    assert a["dow"][1] == pd.Timestamp("2023-01-02").dayofweek and a["month"][40] == 2


def test_coin_base_strips_the_thousand_prefixes_only():
    assert am.coin_base("1000PEPEUSDT") == "PEPE" and am.coin_base("1000000BOBUSDT") == "BOB"
    assert am.coin_base("BTCUSDT") == "BTC" and am.coin_base("1INCHUSDT") == "1INCH"


def test_position_features_use_the_days_own_row():
    pos = pd.DataFrame({"sym": ["A"] * 9, "day": [str(d) for d in D[:9]], "crowd": np.linspace(1, 2, 9), "top_acc": [1.0] * 9,
                        "top_pos": [2.0] * 9, "taker": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 4.0], "oi": [100.0 * 2 ** i for i in range(9)]})
    V = np.full((len(D), 1), 50.0)
    V[8, 0] = 120.0                                                                       # 7-day mean at day 8: (6 x 50 + 120) / 7 = 60
    p = am.position_panels(D, ["A"], pos, V)
    assert abs(p["oi_chg1"][3, 0] - np.log(2)) < 1e-12 and abs(p["oi_chg7"][8, 0] - 7 * np.log(2)) < 1e-12
    assert np.isnan(p["oi_chg7"][6, 0])
    assert abs(p["taker7"][8, 0] - (6 + 4) / 7) < 1e-12 and p["taker1"][8, 0] == 4.0
    assert abs(p["oi_vol"][8, 0] - 25600.0 / 60.0) < 1e-9
    assert abs(p["crowd_chg7"][8, 0] - np.log(2.0 / np.linspace(1, 2, 9)[1])) < 1e-12
    assert np.isnan(p["crowd"][9, 0])                                                   # no row, no value


def test_social_sums_seven_days_of_hits():
    b = pd.DataFrame({"sym": ["A", "A", "A"], "day": ["2024-01-01", "2024-01-03", "2024-01-09"], "hits": [1.0, 2.0, 4.0],
                      "tone": [0.1, 0.3, 0.5]})
    s = am.social_panels(D, ["A", "B"], b)
    assert s["bsky7"][2, 0] == 3.0 and s["bsky7"][8, 0] == 6.0 and s["bsky7"][9, 0] == 4.0
    assert abs(s["bsky_tone7"][2, 0] - 0.2) < 1e-12 and np.isnan(s["bsky7"][:, 1]).all()


def test_causal_percentile_ignores_later_days():
    x = np.array([5.0, 1.0, 3.0, 2.0, 4.0, 10.0])
    p = am.causal_pct(x, w=4, min_periods=2)
    assert np.isnan(p[0]) and p[1] == 0.5 and abs(p[2] - 2 / 3) < 1e-12 and abs(p[4] - 1.0) < 1e-12     # window 1, 3, 2, 4
    y = x.copy()
    y[5] = -100.0
    assert np.allclose(am.causal_pct(y, w=4, min_periods=2)[:5], p[:5], equal_nan=True)


def test_market_stats_use_members_only():
    A = np.array([[0.3, 0.1, 0.25, 9.0, 0.0, 0.5], [0.0] * 6])
    M = np.array([[True, True, True, False, True, True], [True, True, True, True, False, False]])
    f = am._xs_stat(A, M, lambda v: float(np.mean(v > np.log(1.2))))
    assert abs(f[0] - 3 / 5) < 1e-12 and np.isnan(f[1])                                 # 9.0 is not a member; row 1 has 4 < 5 names


def test_the_training_mask_starts_at_train_from():
    dates = np.arange(np.datetime64("2021-12-25"), np.datetime64("2022-01-05"))
    mem = np.ones((len(dates), 2), bool)
    mem[-1, 1] = False
    tm = am.train_mask(mem, dates)
    assert not tm[:7].any() and tm[7:-1].all() and tm[-1, 0] and not tm[-1, 1]


def test_the_planted_feature_has_the_asked_correlation():
    rng = np.random.default_rng(3)
    F = rng.standard_normal((400, 30))
    mem = np.ones(F.shape, bool)
    Y = im.xs_rank(F, mem)
    Y[:50] = np.nan                                                                       # unknown future: pure noise there
    pl = am.planted(Y, mem, 0.3, seed=1)
    ok = np.isfinite(Y)
    r = np.corrcoef(pl[ok], Y[ok])[0, 1]
    assert 0.25 < r < 0.35, r
    assert abs(np.corrcoef(pl[:50].ravel(), F[:50].ravel())[0, 1]) < 0.1             # 1,500 noise values: se ~0.026


def test_gradient_boosting_finds_a_link_that_flips_with_the_market():
    """target = sign(market) x coin feature: invisible to a straight line on ranks, plain to trees given the market block."""
    rng = np.random.default_rng(5)
    T, N = 700, 40
    dates = np.arange(np.datetime64("2022-01-01"), np.datetime64("2022-01-01") + np.timedelta64(T, "D"))
    regime = np.repeat(rng.choice([-1.0, 1.0], T // 20 + 1), 20)[:T]
    x = rng.standard_normal((T, N))
    F = 0.02 * regime[:, None] * x + 0.02 * rng.standard_normal((T, N))
    mem = np.ones((T, N), bool)
    Y = im.xs_rank(F, mem)
    xr = np.nan_to_num(im.xs_rank(x, mem), nan=0.0)
    noise = np.nan_to_num(im.xs_rank(rng.standard_normal((T, N)), mem), nan=0.0)
    coin = np.stack([xr, noise], -1).astype(np.float32)
    mk = np.broadcast_to(regime[:, None, None], (T, N, 1)).astype(np.float32)
    blocks = im.make_blocks(dates, np.datetime64("2023-01-01"))
    with_mkt = im.walk_forward(np.concatenate([coin, mk], -1), Y, mem, blocks, 1, "gbm")[0]
    ridge = im.walk_forward(coin, Y, mem, blocks, 1, "ridge")[0]
    ic_g = np.nanmean(im.day_scores(with_mkt, F, mem)[0])
    ic_r = np.nanmean(im.day_scores(ridge, F, mem)[0])
    assert ic_g > 0.3 and abs(ic_r) < 0.1, (ic_g, ic_r)


def test_vol_neutral_removes_the_volatility_line_and_keeps_the_rest():
    rng = np.random.default_rng(4)
    T, N = 5, 20
    atr = rng.standard_normal((T, N))
    z = rng.standard_normal((T, N))
    mem = np.ones((T, N), bool)
    mem[0, 3] = False
    out = am.vol_neutral(3.0 * atr + z + 7.0, atr, mem)
    for t in range(T):
        ok = mem[t]
        r = out[t, ok]
        assert abs(r.mean()) < 1e-9 and abs(np.corrcoef(r, atr[t, ok])[0, 1]) < 1e-9                 # nothing of atr left
        A = np.column_stack([np.ones(int(ok.sum())), atr[t, ok]])
        zr = z[t, ok] - A @ np.linalg.lstsq(A, z[t, ok], rcond=None)[0]
        assert np.allclose(r, zr)                                                                    # exactly z's own residual is kept
    assert np.isnan(out[0, 3])
    few = np.zeros((T, N), bool)
    few[:, :5] = True
    assert np.isnan(am.vol_neutral(z, atr, few)).all()                                              # under 15 names: no day


def test_the_verdict_separates_a_link_from_price_alone():
    def half(net=5e-4, t=2.5, worst=1e-4, ict=2.5, pt=2.5):
        return dict(net=dict(mean=net, t=t, worst=worst), ic=dict(t=ict), paired=dict(t=pt))
    good = {(7, "gbm"): dict(tu=half(), ho=half())}
    assert am.verdict(good, {}, {(7, "gbm"): 0.01})[0] == "CANDIDATE"
    assert am.verdict({(7, "gbm"): dict(tu=half(), ho=half(pt=1.5))}, {}, {(7, "gbm"): 0.01})[0] == "PRICE-ONLY"
    assert am.verdict(good, {}, {(7, "gbm"): 0.2})[0] == "NO PASS"
    assert am.verdict({(7, "gbm"): dict(tu=half(t=1.5), ho=half())}, {}, {(7, "gbm"): 0.01})[0] == "NO PASS"
    assert am.bar_met(dict(tu=half(), ho=half(pt=0.0))) and not am.bar_met(dict(tu=half(worst=-1e-4), ho=half()))


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests passed")

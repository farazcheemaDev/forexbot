"""Tests for backtest/sweep_zone_more.py: the samples (ranks 41-100, spot before 2020), the repointed loaders, the per-coin setup, the reproduction check,
the power line and the verdict. Offline (no data files). Run as a script: python tests/test_sweep_zone_more.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.sweep_zone_more as m  # noqa: E402


def test_the_power_line_is_holm_first_step_plus_80_percent_power():
    assert abs(m.mde80(0.1) - 0.1 * (2.4977 + 0.8416)) < 1e-3                 # z(1 - 0.05/8) = 2.4977, z(0.80) = 0.8416
    assert abs(m.mde80(0.1, k=1) - 0.1 * (1.6449 + 0.8416)) < 1e-3


def test_point_at_moves_every_loader_the_studies_use():
    f = Path("somewhere")
    m.point_at(f)
    assert m.wb.DATA == f and m.cw.PERPS == f and m.sc.PERPS == f
    m.point_at(m.PERPS)
    assert m.wb.DATA == m.PERPS and m.cw.PERPS == m.PERPS and m.sc.PERPS == m.PERPS


def test_the_samples_are_ranks_41_to_100_and_spot_before_2020():
    old = m.wb.eligibility
    try:
        m.wb.eligibility = lambda n: ({"A": {"2021-01", "2021-02", "2021-03"}, "B": {"2021-01"}, "C": {"2021-05"}} if n == 100
                                      else {"A": {"2021-01"}, "C": {"2021-05"}})
        assert m.samples("perp") == {"A": {"2021-02", "2021-03"}, "B": {"2021-01"}}          # C only ever in the top-40: not new
        m.wb.eligibility = lambda n: {"X": {"2019-11", "2019-12", "2020-01"}, "Y": {"2020-02"}}
        assert m.samples("spot") == {"X": {"2019-11", "2019-12"}}                              # 2020 on is the perps' era
        assert m.wb.DATA == m.SPOT and m.cw.PERPS == m.SPOT and m.sc.PERPS == m.SPOT
    finally:
        m.wb.eligibility = old
        m.point_at(m.PERPS)


class _Mod:
    HOLD, TREND_WARM = 5, 2
    got = {}

    @staticmethod
    def coin_events(t, o, h, l, c, q, rate, fc, elig, pools, ym, rng):
        _Mod.got = dict(elig=elig, pools=pools, ym=ym)
        return [dict(x=1)]


def _hourly(n=40):
    t = pd.date_range("2021-01-31 20:00", periods=n, freq="h")
    return pd.DataFrame(dict(time=t, open=1.0, high=1.1, low=0.9, close=1.0, qvol=1.0))


def test_the_per_coin_setup_is_the_studies_own():
    old_h, old_fc, old_lr, old_min = m.cw.hourly, m.cw.funding_cum, m.sc.last_rate, m.np
    try:
        m.cw.hourly = lambda s: _hourly(500)
        m.cw.funding_cum = lambda s, t, hh: np.zeros(len(t))
        m.sc.last_rate = lambda s, t: np.zeros(len(t))
        rows = m.coin_rows(_Mod, "AAAUSDT", {"2021-02"}, np.random.default_rng(0))
        g = _Mod.got
        assert rows == [dict(x=1, coin="AAAUSDT")]
        assert not g["elig"][:4].any() and g["elig"][4:400].all()                            # January's 4 hours are not eligible
        allp = np.concatenate(list(g["pools"].values()))
        assert allp.min() == 3 and allp.max() == 500 - 5 - 3                                  # > TREND_WARM, and room for the hold (+2) before the end
        assert m.coin_rows(_Mod, "AAAUSDT", set(), np.random.default_rng(0)) == [dict(x=1, coin="AAAUSDT")] and not _Mod.got["elig"].any()
        cap = {}
        old_ce = m.z4.coin_events
        m.z4.coin_events = lambda *a: cap.setdefault("pools", a[9]) and []
        m.coin_rows(m.z4, "AAAUSDT", {"2021-02"}, np.random.default_rng(0))
        m.z4.coin_events = old_ce
        assert np.concatenate(list(cap["pools"].values())).max() == 500 - m.z4.HOLD_R - 3       # the 4h study's own 72-bar hold
        m.cw.hourly = lambda s: _hourly(300)
        assert m.coin_rows(_Mod, "AAAUSDT", {"2021-02"}, np.random.default_rng(0)) == []    # under 400 hours: skipped, as the studies do
    finally:
        m.cw.hourly, m.cw.funding_cum, m.sc.last_rate = old_h, old_fc, old_lr


def test_rows_match_reports_the_differing_columns_and_ignores_the_controls():
    a = pd.DataFrame(dict(t_in=pd.to_datetime(["2021-01-01", "2021-01-02"]), side=[1, -1], net_a=[0.1, -0.2], ctrl_a=[0.0, 0.0]))
    assert m.rows_match(a, a.copy()) == []
    b = a.copy()
    b["ctrl_a"] = [9.0, 9.0]
    assert m.rows_match(a, b) == []
    b["net_a"] = [0.1, -0.3]
    assert m.rows_match(a, b) == ["net_a"]
    assert m.rows_match(a.iloc[:1], a) == ["rows 1 vs 2"]


def _cell(n, mu, ctrl=-0.1, first=None, seed=0, noise=0.5):
    rng = np.random.default_rng(seed)
    t = pd.date_range("2021-01-01", periods=n, freq="D")
    R = mu + rng.normal(0, noise, n)
    if first is not None:
        R[: n // 2] = first + rng.normal(0, noise, n // 2)
    return pd.DataFrame(dict(t_in=t, day=t, net=R, ctrl=np.full(n, ctrl), rf=np.ones(n)))


def test_the_verdict_needs_every_part_of_the_bar():
    v = m.verdicts([("good", _cell(400, 0.4), "net", "ctrl", "rf")])[0]
    assert v["ok"] and v["word"] == "PASS" and abs(v["R"] - 0.4) < 0.08
    assert not m.verdicts([("few", _cell(80, 0.6), "net", "ctrl", "rf")])[0]["ok"]                      # under 100 trades
    assert not m.verdicts([("one half", _cell(400, 0.4, first=-0.3), "net", "ctrl", "rf")])[0]["ok"]    # the first half loses
    assert not m.verdicts([("no excess", _cell(400, 0.4, ctrl=0.9), "net", "ctrl", "rf")])[0]["ok"]     # the random control does better
    many = [("good", _cell(400, 0.4), "net", "ctrl", "rf")] + [(f"null{k}", _cell(400, 0.0, seed=k + 1), "net", "ctrl", "rf") for k in range(7)]
    vs = m.verdicts(many)
    assert vs[0]["ok"] and not any(x["ok"] for x in vs[1:])
    weak = m.verdicts([("weak", _cell(150, 0.05, noise=1.5), "net", "ctrl", "rf")])[0]
    assert not weak["ok"] and weak["mde"] > 0.15 and weak["word"].startswith("no (cannot tell")


def _alt(n, mu, amp=0.5, ctrl=-0.1):
    """one trade a day, R = mu +- amp alternating: mean exactly mu, t = mu / (amp / sqrt(n)) (one trade per cluster), both halves = mu."""
    t = pd.date_range("2021-01-01", periods=n, freq="D")
    R = mu + amp * np.where(np.arange(n) % 2 == 0, 1.0, -1.0)
    return pd.DataFrame(dict(t_in=t, day=t, net=R, ctrl=np.full(n, ctrl), rf=np.ones(n)))


def test_holm_is_over_all_eight_cells_not_one():
    weak = ("weak", _alt(100, 0.11), "net", "ctrl", "rf")                               # t = 2.2, raw one-sided p 0.014
    assert m.verdicts([weak])[0]["ok"]                                                # alone it passes
    nulls = [(f"null{k}", _alt(100, 0.0), "net", "ctrl", "rf") for k in range(7)]
    v = m.verdicts([weak] + nulls)[0]
    assert not v["ok"] and 0.05 <= v["holm"] < 0.2                                    # among 8 cells: 0.014 x 8 = 0.11


def test_a_strong_result_carried_by_one_half_is_refused():
    x = _cell(400, 1.0, first=-0.05, noise=0.5)                                      # overall +0.47R, t far above any line, but the first half loses
    v = m.verdicts([("one half", x, "net", "ctrl", "rf")])[0]
    assert v["h1"] < 0 < v["h2"] and v["t"] > 5 and not v["ok"]


def test_the_halves_split_at_the_median_date():
    s = m.cell_stats(_cell(100, 0.0, first=1.0, noise=0.0), "net", "ctrl", "rf")
    assert s["h1"] == 1.0 and s["h2"] == 0.0 and s["n"] == 100


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")

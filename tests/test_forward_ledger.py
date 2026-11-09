"""Offline tests for backtest/forward_ledger.py - the pins, the forward window (entry at or after the registration instant, exit
already passed), each replay's arithmetic, the lines (too early / dead / on track / below / confirmed with Holm) and the JSON.
Synthetic data only; the study functions are stubbed where a test is about the ledger's own filters.

    python tests/test_forward_ledger.py
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from math import sqrt
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import forward_ledger as fl  # noqa: E402

F0 = fl.FORWARD_FROM_MS


@contextmanager
def patched(mod, **kw):
    old = {k: getattr(mod, k) for k in kw}
    try:
        for k, v in kw.items():
            setattr(mod, k, v)
        yield
    finally:
        for k, v in old.items():
            setattr(mod, k, v)


def test_the_registry_and_the_rules_are_still_the_pinned_ones():
    assert fl.registry_digest() == fl.REGISTRY_SHA256, "a registered number changed"
    assert fl.rule_digest() == fl.RULE_SHA256, "a study function the replays use changed"
    assert fl.FORWARD_FROM_MS == 1794182400000 and fl.N_MIN == 5


def test_the_fomc_trade_is_24h_to_5min_before_net_of_cost_and_only_forward():
    t = np.arange(F0 - 2 * 86400000, F0 + 10 * 86400000, 60000, dtype=np.int64)
    c = 100 + (t - t[0]) / 86400000.0                                                  # +1 a day, linear
    st = (F0 + 3 * 86400000) / 1000                                                    # a statement 3 days after the start
    early = (F0 + 0.5 * 86400000) / 1000                                               # entry 24 h before = before the start
    late = (t[-1] + 3600000) / 1000                                                    # its exit minute is not in the data yet
    out = fl.replay_fomc(t, c, [st, early, late, st], F0)
    assert len(out) == 1 and out[0]["t"] == int((st - 86400) * 1000)
    e0, e1 = (st - 86400) * 1000, (st - 300) * 1000
    want = ((100 + (e1 - t[0]) / 86400000) / (100 + (e0 - t[0]) / 86400000) - 1 - fl.FOMC_COST) * 100
    assert abs(out[0]["value"] - want) < 1e-6


def test_the_inside_bar_replay_keeps_only_forward_entries_with_24_hours_behind_them():
    t = np.arange(F0 - 86400000, F0 + 3 * 86400000, 60000, dtype=np.int64)
    o = h = l = c = np.full(len(t), 100.0)  # noqa: E741
    k_before, k_in, k_end = np.searchsorted(t, F0 - 60000), np.searchsorted(t, F0), len(t) - 30
    trades = {0: (0.5, 0.01, k_before), 1: (1.5, 0.02, k_in), 2: (-1.0, 0.01, k_end)}

    def fake_signals(*a, look=20):
        return np.array([0, 1, 2]), np.array([1.0, 2.0, 3.0]), np.array([0.0, 0.0, 0.0])

    def fake_touch(T, O, H, L, C, bs_j, S, Lx, k, costf):
        assert k == 2 and abs(costf - 1.27e-4) < 1e-12
        return trades[int(S) - 1]

    with patched(fl.ibb, signals=fake_signals, trade_touch=fake_touch, bars30=lambda *a: (np.array([0, 1, 2]),) * 5):
        out = fl.replay_ib(t, o, h, l, c, F0)
    assert [x["value"] for x in out] == [1.5] and out[0]["t"] == int(t[k_in]) and "2.00%" in out[0]["note"]


def test_the_inside_bar_replay_runs_on_the_mirrored_market():
    seen = {}

    def fake_bars(T, O, H, L, C):
        seen["H"], seen["L"] = H.copy(), L.copy()
        return (np.array([], np.int64),) * 5

    t = np.arange(0, 600000, 60000, dtype=np.int64)
    h, l = np.full(10, 101.0), np.full(10, 99.0)  # noqa: E741
    with patched(fl.ibb, bars30=fake_bars, signals=lambda *a, look=20: (np.array([], int), np.array([]), np.array([]))):
        fl.replay_ib(t, np.full(10, 100.0), h, l, np.full(10, 100.0), 0)
    assert (seen["H"] == -99.0).all() and (seen["L"] == -101.0).all()                # a long = the short of the upside-down market


def test_the_gold_replay_uses_released_and_finished_events_only():
    calls = []

    def ticks(t0):
        calls.append(t0)
        return (np.array([0.0]), np.array([1.0]), np.array([1.0]))

    res = {"side": 1, "net_bp": 12.5, "slip_bp": 9.0, "stopped": False, "trig_s": 1.0}
    s0 = F0 / 1000
    now = s0 + 10 * 86400
    with patched(fl.gnt, straddle=lambda ts, bid, ask, T0, x, lat: dict(res) if (x, lat) == (5, 1.0) else None):
        out = fl.replay_gold([s0 - 60, s0 + 86400, now - 3600, s0 + 86400], ticks, F0, now)
    assert calls == [s0 + 86400]                                                      # before the start / exit not passed: not fetched
    assert len(out) == 1 and out[0]["value"] == 12.5 and out[0]["t"] == int((s0 + 86400) * 1000) and "long" in out[0]["note"]
    with patched(fl.gnt, straddle=lambda *a: None):
        assert fl.replay_gold([s0 + 86400], ticks, F0, now) == []                      # no trigger within the hour: no trade


def test_the_lines_by_hand():
    assert fl.judge([1.0] * 4, 0.5, 1.0)["status"] == "too early"
    v = [0.4, 0.6, 0.5, 0.3, 0.7]
    d = fl.judge(v, 0.5, 1.0)
    assert d["status"] == "on track" and abs(d["dead_line"] - (0.5 - 2 / sqrt(5))) < 1e-12
    assert abs(d["t"] - 0.5 / (np.std(v, ddof=1) / sqrt(5))) < 1e-9
    assert fl.judge([x - 0.4 for x in v], 0.5, 1.0)["status"] == "below the claim"          # mean 0.1 < half the claim, above the line
    assert fl.judge([0.1, 0.3, 0.2, 0.0, 0.4], 0.5, 1.0)["status"] == "below the claim"       # mean 0.2: under half (0.25), over a third
    assert fl.judge([-1.0, -0.9, -1.1, -1.0, -1.2], 0.5, 1.0)["status"] == "dead"          # mean -1.04 < 0.5 - 0.894
    assert fl.judge([-0.3, -0.4, -0.35, -0.38, -0.36], 0.5, 1.0)["status"] == "below the claim"   # -0.358 is above -0.394


def test_confirmation_needs_t_2_and_holm_across_the_leads():
    r = {"a": dict(status="on track", t=3.0, p=0.01), "b": dict(status="on track", t=2.5, p=0.02),
         "c": dict(status="below the claim", t=0.1, p=0.5), "d": dict(status="too early", t=None, p=None)}
    fl.holm_confirm(r)
    assert abs(r["a"]["p_holm"] - 0.03) < 1e-12 and abs(r["b"]["p_holm"] - 0.04) < 1e-12 and abs(r["c"]["p_holm"] - 0.5) < 1e-12
    assert r["a"]["status"] == r["b"]["status"] == "confirmed" and r["c"]["status"] == "below the claim" and "p_holm" not in r["d"]
    r2 = {"a": dict(status="dead", t=3.0, p=0.001), "b": dict(status="on track", t=1.9, p=0.001)}
    fl.holm_confirm(r2)
    assert r2["a"]["status"] == "dead" and r2["b"]["status"] == "on track"                  # dead stays dead; t < 2 is not confirmed
    r3 = {"a": dict(status="on track", t=2.2, p=0.02), "b": dict(status="on track", t=2.1, p=0.03), "c": dict(status="on track", t=2.0, p=0.04)}
    fl.holm_confirm(r3)
    assert all(x["status"] == "on track" for x in r3.values())                              # 0.06 / 0.06 / 0.06 after Holm


def test_years_to_confirm_and_the_month_list():
    assert abs(fl.years_to_confirm(0.25, 0.9, 8.0) - 4 * (0.9 / 0.25) ** 2 / 8) < 1e-12
    assert fl.ff_month_names(F0, F0 + 36 * 86400000) == ["nov.2026", "dec.2026", "jan.2027"]


def test_epoch_seconds_ignore_the_parsed_unit():
    assert fl.epoch_s(["2026-12-04 13:30:00"]) == [1796391000]
    assert fl.epoch_s(["2026-12-04 13:30:00+00:00", "2026-12-09 19:00:00"]) == [1796391000, 1796842800]


def test_the_json_keeps_the_newest_30_events_first_and_flags_a_changed_rule():
    trades = {"pre_fomc": [dict(t=i, value=float(i), note="") for i in range(40)]}
    res = fl.summarise(trades, True)
    J = fl.ledger_json(trades, res, F0 + 1000, {})
    pf = next(x for x in J["leads"] if x["id"] == "pre_fomc")
    assert pf["n"] == 40 and len(pf["events"]) == 30 and pf["events"][0]["t"] == 39 and pf["events"][-1]["t"] == 10
    assert J["forward_from"] == F0 // 1000 and J["registry_ok"] and J["rule_ok"]
    assert abs(pf["years"] - round(fl.years_to_confirm(0.25, 0.9, 8.0), 1)) < 1e-9
    bad = fl.summarise(trades, False)
    assert all(v["status"] == "RULE CHANGED" and v["n"] == 0 for v in bad.values())


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(n, "tests passed")

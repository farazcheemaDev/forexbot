"""order_flow_registry.py offline: the registry is pinned, its arithmetic is right, and judge() applies every criterion on its own.
Run as a script: python tests/test_order_flow_registry.py"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import order_flow_registry as reg  # noqa: E402

GOOD = dict(t=4.5, p_shift=0.004, gross_bp=26.0, net_bp=14.0, cost_bp=12.0, n_trades=900, n_days=30, day_pos_frac=0.8, same_sign_pairs=4, increment_t=2.6, saving_bp=1.4)


def test_the_registry_is_pinned_by_its_digest():
    assert reg.digest() == reg.REGISTRY_SHA256, "a registered number changed: amend deliberately (AMENDMENTS + the digest), never silently"
    changed = copy.deepcopy(reg.REGISTRY)
    changed["common"]["shift_null_p"] = 0.05
    assert reg.digest(changed) != reg.REGISTRY_SHA256                                           # one loosened criterion changes the digest
    changed = copy.deepcopy(reg.REGISTRY)
    changed["H-imb"]["horizons_s"] = [30, 60, 300, 3600]
    assert reg.digest(changed) != reg.REGISTRY_SHA256


def test_each_hypothesis_states_a_cell_count_that_matches_its_own_lists():
    R = reg.REGISTRY
    assert R["H-imb"]["cells"] == len(R["H-imb"]["features"]) * len(R["H-imb"]["lookbacks_s"]) * len(R["H-imb"]["horizons_s"]) == 18
    assert R["H-flow"]["cells"] == len(R["H-flow"]["features"]) * len(R["H-flow"]["lookbacks_s"]) * len(R["H-flow"]["horizons_s"]) == 15
    assert R["H-approach"]["cells"] == len(R["H-approach"]["horizons_s"]) == 2
    assert R["H-combo"]["cells"] == len(R["H-combo"]["horizons_s"]) == 2
    assert R["H-exec"]["cells"] == len(R["H-exec"]["adverse_rank"]) * len(R["H-exec"]["horizons_s"]) == 2
    for a, b in ((reg.TUNE_PAIRS, reg.TEST_PAIRS), (reg.TUNE_PAIRS, reg.CONTROL_PAIRS), (reg.TEST_PAIRS, reg.CONTROL_PAIRS)):
        assert not set(a) & set(b)                                                              # tune, test and control pairs never overlap
    assert len(reg.TUNE_PAIRS) + len(reg.TEST_PAIRS) + len(reg.CONTROL_PAIRS) == 10


def test_the_bonferroni_cutoff_follows_the_cell_count():
    assert abs(reg.cut_t(1) - 1.96) < 0.001 and abs(reg.cut_t(20) - 3.023) < 0.002 and abs(reg.cut_t(750) - 3.988) < 0.003
    assert reg.cut_t(15) < reg.cut_t(18) < reg.cut_t(750)
    assert abs(reg.cut_t(18) - 2.99) < 0.02


def test_costs_match_the_worked_examples_of_lesson_1_2():
    assert abs(reg.round_trip_cost_bp("taker", 1.2) - 13.2) < 1e-12                              # 12bp of fees + the spread crossed once
    assert abs(reg.round_trip_cost_bp("maker", 1.2) - 4.0) < 1e-12                               # both legs maker, every order fills
    assert abs(reg.round_trip_cost_bp("mixed", 1.2) - 8.6) < 1e-12
    assert abs(reg.round_trip_cost_bp("taker", 1.2, slip_bp=0.5) - 14.2) < 1e-12                 # slippage on both legs
    assert abs(reg.round_trip_cost_bp("taker", 0.0, fee_taker_bp=4.0) - 8.0) < 1e-12
    try:
        reg.round_trip_cost_bp("limit", 1.0)
        assert False
    except ValueError:
        pass


def test_power_arithmetic():
    assert reg.trades_needed(1.0, 5.56) == 243                                                   # (1.96 + 0.8416)^2 x 5.56^2
    assert reg.trades_needed(0.5, 5.56) > 3.9 * reg.trades_needed(1.0, 5.56) and reg.trades_needed(2.0, 5.56) < 62
    assert reg.trades_needed(1.0, 1.0) == 8


def test_what_noise_reaches_when_you_search_k_cells():
    assert abs(reg.null_max_abs_t(1) - 0.6745) < 0.001                                           # the median |Z|
    assert 1.95 < reg.null_max_abs_t(15) < 2.10 and 3.3 < reg.null_max_abs_t(1000) < 3.5          # the lab's single draw over 1,000 null cells reached 3.8: above the median, as it may be
    assert reg.null_max_abs_t(1000) < reg.null_max_abs_t(1000, 0.95) and reg.null_max_abs_t(10) < reg.null_max_abs_t(100)


def test_judge_passes_a_result_that_meets_every_criterion():
    for hid in ("H-imb", "H-flow", "H-approach", "H-combo", "H-exec"):
        ok, rows = reg.judge(hid, GOOD)
        assert ok, (hid, rows)
    assert len(reg.judge("H-combo", GOOD)[1]) == 4 and len(reg.judge("H-imb", GOOD)[1]) == 3


def test_judge_fails_on_each_criterion_alone():
    def fails(hid, **kw):
        ok, rows = reg.judge(hid, dict(GOOD, **kw))
        assert not ok, (hid, kw)
        return [k for k, good, _ in rows if not good]
    assert fails("H-imb", t=2.9) == ["K1"]                                                       # 18 cells need 2.99
    assert fails("H-imb", p_shift=0.011) == ["K1"]
    assert fails("H-flow", t=2.9) == ["K1"]                                                      # 15 cells need 2.94
    assert reg.judge("H-flow", dict(GOOD, t=2.96))[0] and not reg.judge("H-imb", dict(GOOD, t=2.96))[0]      # the same t passes 15 cells and fails 18
    assert fails("H-imb", gross_bp=23.9) == ["K2"]                                               # gross must reach 2 x the 12bp cost
    assert fails("H-imb", net_bp=0.0) == ["K2"]
    assert fails("H-imb", n_days=19) == ["K3"] and fails("H-imb", n_trades=199) == ["K3"]
    assert fails("H-imb", day_pos_frac=0.74) == ["K3"] and fails("H-imb", same_sign_pairs=2) == ["K3"]
    assert fails("H-combo", increment_t=1.9) == ["K4"]
    assert fails("H-exec", saving_bp=0.9) == ["K2e"]
    assert fails("H-exec", saving_bp=2.0, t=1.0) == ["K1"]
    assert reg.judge("H-imb", dict(GOOD, increment_t=-9.0, saving_bp=-9.0))[0]                   # K4 / K2e are not asked of H-imb


def test_a_criterion_loosened_in_a_copy_changes_the_verdict_and_the_digest():
    loose = copy.deepcopy(reg.REGISTRY)
    loose["common"]["positive_day_fraction"] = 0.5
    assert reg.judge("H-imb", dict(GOOD, day_pos_frac=0.6), loose)[0] and not reg.judge("H-imb", dict(GOOD, day_pos_frac=0.6))[0]
    assert reg.digest(loose) != reg.REGISTRY_SHA256


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")

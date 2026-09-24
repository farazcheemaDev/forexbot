"""Offline tests for combo_paper.py's own rules - the parts it adds on top of blend_paper.py and
mn_paper.py, whose code it imports unchanged. No network. Each rule is checked where it must fire
and where it must not, and against the backtest's own function where one exists.

    python tests/test_combo_paper.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.argv = [sys.argv[0]]
import blend_paper as bp  # noqa: E402
import combo_paper as cp  # noqa: E402
try:                        # the research tree pulls in libraries a minimal VM venv may lack
    from backtest.market_neutral import btc_regime  # noqa: E402
except Exception as e:      # noqa: BLE001
    btc_regime = None
    print(f"SKIP regime cross-check: backtest import failed ({type(e).__name__}: {e})")

TMP = Path(tempfile.mkdtemp())
REAL_TRIPLE, REAL_LOG = bp.TRIPLE_TRADES, bp.LOGF
cp.set_dir(TMP)


def test_patches_stay_inside_the_scratch_dir():
    assert bp.TRIPLE_TRADES == TMP / "trades_combo_trend.csv" != REAL_TRIPLE
    assert bp.LOGF == TMP / "combo_paper.log" != REAL_LOG
    assert bp.MAX_LEVERAGE == 9.0


def test_anchor_never_above_equity_and_lags_a_boom():
    hist = [[f"d{i}", 100.0] for i in range(30)]
    assert cp.anchored(200.0, hist) == 100.0              # boom: sized on the average
    assert cp.anchored(80.0, hist) == 80.0                # fall: never above today's equity
    assert cp.anchored(150.0, []) == 150.0                # no history yet: equity
    hist2 = [[f"d{i}", 100.0] for i in range(9)] + [[f"e{i}", 200.0] for i in range(21)]
    assert cp.anchored(250.0, hist2) == 200.0             # only the last 21 days count


def test_ladder_excludes_today_and_averages_seven():
    sig = {f"2026-01-{d:02d}": 1 for d in range(1, 32)}
    assert cp.ladder_pos(sig, "2026-01-20") == 1.0
    sig2 = {"2026-01-20": 1}                              # decided today: not held today
    assert cp.ladder_pos(sig2, "2026-01-20") == 0.0
    assert abs(cp.ladder_pos(sig2, "2026-01-21") - 1 / 7) < 1e-12
    assert abs(cp.ladder_pos(sig2, "2026-01-27") - 1 / 7) < 1e-12
    assert cp.ladder_pos(sig2, "2026-01-28") == 0.0       # held exactly 7 days


def test_rebalance_minimum_and_closing():
    new, traded, skipped = cp.rebalance({"A": 10.0}, {"A": 13.0})
    assert new == {"A": 10.0} and traded == 0 and skipped == 1        # +$3 is under $5
    new, traded, skipped = cp.rebalance({"A": 3.0}, {})
    assert new == {} and traded == 3.0 and skipped == 0               # a close always goes
    new, traded, _ = cp.rebalance({}, {"B": -20.0})
    assert new == {"B": -20.0} and traded == 20.0


def test_signal_only_in_bear():
    assert cp.signal("bear", 0.05) == 1 and cp.signal("bear", 0.40) == -1
    assert cp.signal("bear", 0.20) == 0
    assert cp.signal("bull", 0.05) == 0 and cp.signal("chop", 0.40) == 0


def test_regime_matches_the_backtest_function():
    if btc_regime is None:
        return
    rng = np.random.default_rng(3)
    px = 30000 * np.exp(np.cumsum(rng.normal(0, 0.03, 400)))
    idx = pd.date_range("2022-01-01", periods=400, freq="D")
    ref = btc_regime(pd.DataFrame({"BTCUSDT": px}, index=idx))        # label for day k uses close k-1
    got = [cp.regime(px[:k]) for k in range(80, 400)]
    want = list(ref.iloc[80:400])
    assert got == want, sum(a != b for a, b in zip(got, want))
    assert {"bull", "bear", "chop"} <= set(got)            # the test exercises all three


def test_breadth():
    up = pd.DataFrame({"close": np.linspace(1, 2, 30)})
    dn = pd.DataFrame({"close": np.linspace(2, 1, 30)})
    bars = {"A": up, "B": up, "C": dn, "D": dn}
    assert cp.breadth20(bars, ["A", "B", "C", "D"]) == 0.5
    assert cp.breadth20(bars, ["A"]) == 1.0


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")

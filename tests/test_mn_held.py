"""Offline tests for the held-coin fix (2026-09-29) in BOTH market-neutral books: combo_paper's
MN leg and mn_paper.py. A coin the book holds but that has fallen out of the top-120 pool by
24h volume must still be priced and kept; a coin that is really gone (unlisted, or no bar for
the day) must still be exited at its last mark. The exchange is faked; no network.

Before the fix a held coin outside the pool was exited as if delisted - CAP, CYS and TUT on the
VM in the combo's first three days. test_*_keeps_a_held_coin fails on that code.

    python tests/test_mn_held.py
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
import combo_paper as cp  # noqa: E402
import mn_paper as mp  # noqa: E402

TMP = Path(tempfile.mkdtemp())
cp.set_dir(TMP)
mp.STATE, mp.MARKS, mp.REBAL = TMP / "mnp_state.json", TMP / "mnp_marks.csv", TMP / "mnp_reb.csv"
mp.LOGF = TMP / "mn_paper.log"          # set_dir already points it here; be explicit

T = pd.Timestamp("2026-09-28")          # the last CLOSED daily bar (its open time)
POOL = [f"C{i}USDT" for i in range(40)]
HELD, GONE, STALE = "HELDUSDT", "GONEUSDT", "STALEUSDT"


def frame(n: int, last=T, px=1.0, end_px=None) -> pd.DataFrame:
    c = np.full(n, px)
    if end_px is not None:
        c[-1] = end_px
    return pd.DataFrame({"time": pd.date_range(end=last, periods=n, freq="D"),
                         "close": c, "qvol": np.full(n, 1e6)})


FAKE_DAILY = {
    "BTCUSDT": frame(120, px=60000.0),
    HELD: frame(5, end_px=1.10),                       # +10% on the day, still listed
    STALE: frame(5, last=T - pd.Timedelta(days=1)),   # listed, but no bar for T (halted)
}


def fake(fetched: list):
    def daily(sym, limit=None):
        fetched.append(sym)
        return FAKE_DAILY.get(sym)
    return dict(perp_universe=lambda: (POOL + ["BTCUSDT", HELD, STALE], {}),
                candidates=lambda syms: list(POOL),
                fetch_all=lambda syms: {s: frame(80) for s in syms},
                daily=daily, funding_since=lambda s, since: 0.0)


def patched(fn, fetched):
    saved = {k: getattr(mp, k) for k in fake(fetched)}
    try:
        for k, v in fake(fetched).items():
            setattr(mp, k, v)
        return fn()
    finally:
        for k, v in saved.items():
            setattr(mp, k, v)


W = {HELD: 0.25, GONE: 0.25, STALE: 0.25, "C0USDT": -0.25}
PX0 = {s: 1.0 for s in W}


def test_combo_keeps_a_held_coin_outside_the_pool():
    st = cp.fresh()
    st["mn"].update(weights=dict(W), mark_px=dict(PX0), base=200.0,
                    last_rebal=f"{T - pd.Timedelta(days=2):%Y-%m-%d}", n_rebal=1)
    st["last_day"], st["last_fund_ms"] = f"{T:%Y-%m-%d}", 1
    fetched: list = []
    patched(lambda: cp.daily(st), fetched)
    assert st["last_day"] == f"{T + pd.Timedelta(days=1):%Y-%m-%d}"   # the day was processed
    w = st["mn"]["weights"]
    assert HELD in w, "held coin outside the pool was exited - the pre-fix bug"
    assert abs(st["cum"]["mn"] - 200.0 * 0.25 * 0.10) < 1e-9, st["cum"]["mn"]   # its +10% counted
    assert st["mn"]["mark_px"][HELD] == 1.10
    assert GONE not in w and STALE not in w          # really gone: still exited at last mark
    assert set(fetched) >= {HELD, STALE} and GONE not in fetched       # unlisted: not even asked
    assert "C0USDT" not in fetched                   # pool coins come from fetch_all, not twice


def test_mn_paper_keeps_a_held_coin_outside_the_pool():
    st = mp.fresh()
    st.update(weights=dict(W), mark_px=dict(PX0), base_eq=200.0, equity=200.0,
              last_bar=f"{T - pd.Timedelta(days=1):%Y-%m-%d}",
              last_rebal=f"{T - pd.Timedelta(days=2):%Y-%m-%d}", n_rebal=1, last_fund_ms=1)
    fetched: list = []
    patched(lambda: mp.cycle(st), fetched)
    assert st["last_bar"] == f"{T:%Y-%m-%d}" and st["n_marks"] == 1
    assert HELD in st["weights"], "held coin outside the pool was exited - the pre-fix bug"
    assert abs(st["equity"] - (200.0 + 200.0 * 0.25 * 0.10)) < 1e-9, st["equity"]
    assert st["mark_px"][HELD] == 1.10
    assert GONE not in st["weights"] and STALE not in st["weights"]


def test_held_closes_filters():
    fetched: list = []
    got = patched(lambda: mp.held_closes([HELD, GONE, STALE], POOL + [HELD, STALE], T), fetched)
    assert got == {HELD: 1.10}


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")

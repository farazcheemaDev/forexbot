"""Offline tests for backtest/capitulation_wide.py's 4h bars and funding window. No network, no data files.

    python tests/test_capitulation_wide.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import capitulation_wide as cw  # noqa: E402


def hours(n):
    t = pd.date_range("2024-01-01", periods=n, freq="h").astype("datetime64[ns]")
    p = np.arange(n, dtype=float) + 100
    return pd.DataFrame({"time": t, "open": p, "high": p + 0.5, "low": p - 0.5, "close": p + 0.2, "qvol": 1.0})


def test_four_hour_phases():
    h = hours(48)
    d0 = cw.four_hour(h, 0)
    assert d0.time.iloc[0] == pd.Timestamp("2024-01-01 00:00") and d0.o.iloc[0] == 100 and d0.c.iloc[0] == 103.2
    assert d0.h.iloc[0] == 103.5 and d0.l.iloc[0] == 99.5 and d0.v.iloc[0] == 4.0
    d1 = cw.four_hour(h, 60)
    full = d1[d1.time >= "2024-01-01 01:00"].iloc[0]
    assert full.time == pd.Timestamp("2024-01-01 01:00") and full.o == 101 and full.c == 104.2


def test_funding_window(tmp_path=None):
    h = hours(48)
    times = cw.four_hour(h, 0).time.to_numpy()
    real = cw.PERPS
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        cw.PERPS = Path(td)
        pd.DataFrame({"time": ["2024-01-01 08:00:00.004", "2024-01-01 16:00:00.002"], "rate": [0.001, 0.002]}).to_csv(
            Path(td) / "XUSDT_funding.csv.gz", index=False, compression="gzip")
        fc = cw.funding_cum("XUSDT", times, h)
        cw.PERPS = real
    # bars start 00,04,08,12,16,20,...: the 08:00 settlement is counted from the 08:00 bar on, x its open (108)
    assert fc[0] == 0 and fc[1] == 0 and abs(fc[2] - 0.001 * 108) < 1e-12
    assert abs(fc[4] - (0.001 * 108 + 0.002 * 116)) < 1e-12


def test_archive_holes_are_kept_and_real_halts_cut():
    """2026-10-09: a 73-hour archive hole (2022-02-26..28 on 47 coins) must NOT end a coin's history; a gap of more
    than 7 days (BNX's 21-day halt) must. The old 48-hour rule cut XRP, SOL and 49 others at 2022-02-25."""
    d = hours(2000)
    hole = d.drop(index=range(1000, 1072)).reset_index(drop=True)          # 73h between two rows
    assert len(cw.halt_cut(hole)) == len(hole), "an archive hole cut the coin's history"
    halt = d.drop(index=range(1000, 1200)).reset_index(drop=True)          # a 201h gap
    assert len(cw.halt_cut(halt)) == 1000, "a real halt was not cut"


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")

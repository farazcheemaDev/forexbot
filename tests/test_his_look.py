"""Smoke test for backtest/his_look.py's winter-offset option (his_strategy.md s35), run end to end on a
FAKE tick cache and a FAKE statement - the real ones live on the PC.

One winter trade, truly at 10:15 New York time (15:15 UTC), stamped the suspected way (UTC + 4), and one
summer trade at 11:30 New York (UTC + 5). Defaults must reproduce the old script (April on only); the
winter option must draw the winter trade at 10:15; and the old single offset must put it at 09:15, before
the open, where it cannot be drawn - which is how a clock error hides trades.

    python tests/test_his_look.py
"""
from __future__ import annotations

import pickle
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import his_look  # noqa: E402

TMP = Path(tempfile.mkdtemp())
WINTER, SUMMER = pd.Timestamp("2026-02-10"), pd.Timestamp("2026-06-10")


def fixtures():
    rng = np.random.default_rng(0)
    cache = {}
    for d in (pd.Timestamp("2026-02-09"), WINTER, pd.Timestamp("2026-06-09"), SUMMER):
        ts = np.arange(0, 23400, 1.0)                                    # seconds from 09:30 ET
        cache[d] = (ts, 25000 + np.cumsum(rng.normal(0, 1, len(ts))), np.full(len(ts), 1.5))
    (TMP / "ticks.pkl").write_bytes(pickle.dumps(cache))
    rows = [("2026-02-10 19:15:10", "2026-02-10 19:16:40", "BUY"),      # 15:15 UTC = 10:15 EST, stamped +4
            ("2026-06-10 20:30:05", "2026-06-10 20:31:20", "SELL")]     # 15:30 UTC = 11:30 EDT, stamped +5
    pd.DataFrame([dict(open_time=o, close_time=c, symbol="NASDAQ Mar", side=s, lots=0.1,
                       open_price=25100.0, close_price=25107.0 if s == "BUY" else 25093.0, net=70.0)
                  for o, c, s in rows]).to_csv(TMP / "statement.csv", index=False)


def run(*extra, out):
    return his_look.main(["--trades", str(TMP / "statement.csv"), "--ticks", str(TMP / "ticks.pkl"),
                          "--out", str(TMP / out), *extra])


def test_defaults_reproduce_the_old_script():
    fixtures()
    x = run(out="a")
    assert len(x) == 1 and x.open.iloc[0] == pd.Timestamp("2026-06-10 11:30:05")
    assert sorted(p.name for p in (TMP / "a").glob("*.png")) == ["01.png"]


def test_winter_option_draws_the_winter_trade_at_the_corrected_hour():
    fixtures()
    x = run("--winter-gmt", "4", "--since", "2026-01-01", out="b")
    assert list(x.open) == [pd.Timestamp("2026-02-10 10:15:10"), pd.Timestamp("2026-06-10 11:30:05")]
    assert len(list((TMP / "b").glob("*.png"))) == 2


def test_the_old_offset_hides_the_winter_trade_before_the_open():
    fixtures()
    x = run("--since", "2026-01-01", out="c")                            # UTC+5 all year
    assert list(x.open) == [pd.Timestamp("2026-06-10 11:30:05")]         # 09:15 ET: before the open


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")

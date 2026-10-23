"""news/crowd_paper.py offline: the live book against the backtest's own code (news/positioning_hist.py), no network."""
import random
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from news import crowd_paper as cp  # noqa: E402
from news import positioning_hist as ph  # noqa: E402


class Files:
    """crowd_paper's files moved to a temp folder for the test."""
    def __enter__(self):
        d = Path(tempfile.mkdtemp())
        self.old = {k: getattr(cp, k) for k in ("DIR", "STATE", "WEEKS", "SLEEVES_CSV", "MARKS")}
        for k, f in (("DIR", d), ("STATE", d / "s.json"), ("WEEKS", d / "w.csv"), ("SLEEVES_CSV", d / "sl.csv"),
                     ("MARKS", d / "m.csv")):
            setattr(cp, k, f)
        return d

    def __exit__(self, *a):
        for k, v in self.old.items():
            setattr(cp, k, v)


def test_legs_match_the_backtest_on_every_archived_date():
    """Every date in the positioning cache (2022-26, ties included): the live quarters = positioning_hist.quarters."""
    if not ph.CACHE.exists():
        print("   (skipped: no positioning cache on this machine)")
        return
    F = pd.read_parquet(ph.CACHE).dropna(subset=["crowd"])
    n = 0
    for day, g in F.groupby("day"):
        v = g.set_index("sym")["crowd"]
        if len(v) < cp.MIN_COINS:
            continue
        assert cp.quarters(v.to_dict()) == ph.quarters(v), day
        n += 1
    assert n > 400, n
    rnd = random.Random(7)
    for _ in range(300):                                            # heavy ties
        v = pd.Series({f"C{i}USDT": float(rnd.randint(1, 6)) for i in range(rnd.randint(16, 45))})
        assert cp.quarters(v.to_dict()) == ph.quarters(v)


def test_turnover_fee_is_the_backtests():
    rnd = random.Random(3)
    pool = [f"C{i}" for i in range(30)]
    for _ in range(500):
        a, b, c, d = (set(rnd.sample(pool, rnd.randint(0, 11))) for _ in range(4))
        assert cp.turnover_fee(a, b, c, d) == ph.turnover_fee(a, b, c, d)


def week_fixture(seed=1, n=24):
    rnd = random.Random(seed)
    syms = [f"C{i}USDT" for i in range(n)] + ["BTCUSDT"]
    return dict(crowd={s: rnd.uniform(0.5, 3.0) for s in syms}, p0={s: rnd.uniform(1, 100) for s in syms},
                move={s: rnd.uniform(-0.4, 0.8) for s in syms}, fund={s: rnd.uniform(-0.01, 0.01) for s in syms})


def test_one_live_week_equals_the_backtest_week():
    """Open at a Monday anchor, close a week later: the sleeve's equity moves by exactly positioning_hist.book's net
    week on the same numbers (BTC's move cancels; funding and the fee as the backtest charges them)."""
    try:
        import scipy  # noqa: F401 - positioning_hist.book's IC; the VM has no scipy, the PC runs this check
    except ImportError:
        print("   (skipped: no scipy here)")
        return
    X = week_fixture()
    A, B = cp.ms(cp.day0("2026-11-02")), cp.ms(cp.day0("2026-11-09"))
    px = lambda s, t: X["p0"][s] * (1 + X["move"][s]) if t == B else X["p0"][s]  # noqa: E731
    with Files():
        st = cp.fresh()
        sl = st["sleeves"]["mon"]
        cp.open_week("mon", sl, A, universe=lambda now: list(X["crowd"]), crowd=lambda s, t: (X["crowd"][s], 0.5), price=px)
        cp.close_week("mon", sl, B, price=px, fsum=lambda s, a, b: X["fund"][s])
    btc = X["move"]["BTCUSDT"]
    D = pd.DataFrame([dict(a=pd.Timestamp("2026-11-02"), s=s, fwd=X["move"][s] - btc, fund=X["fund"][s], crowd=X["crowd"][s])
                      for s in X["crowd"]])
    net = ph.book(D, "crowd", ph.SIGN["crowd"])[1].iloc[0]
    assert abs(sl["equity"] - 150.0 * (1 + net)) < 1e-9, (sl["equity"], 150 * (1 + net))
    assert sl["weeks"] == 1 and sl["pos"] == []


def test_the_long_side_is_the_crowds_most_short_quarter():
    X = week_fixture(n=20)
    with Files():
        sl = cp.fresh()["sleeves"]["thu"]
        cp.open_week("thu", sl, cp.ms(cp.day0("2026-10-29")), universe=lambda now: list(X["crowd"]),
                     crowd=lambda s, t: (X["crowd"][s], 0.5), price=lambda s, t: X["p0"][s])
    order = sorted(X["crowd"], key=X["crowd"].get)
    longs = {p["sym"] for p in sl["pos"] if p["side"] > 0}
    shorts = {p["sym"] for p in sl["pos"] if p["side"] < 0}
    assert set(order[:5]) <= longs and set(order[-5:]) <= shorts and not longs & shorts
    assert abs(sum(p["w"] for p in sl["pos"] if p["side"] > 0) - 0.5) < 1e-12
    assert abs(sum(p["w"] for p in sl["pos"] if p["side"] < 0) - 0.5) < 1e-12
    assert abs(sl["fee"] - cp.FEE) < 1e-12                          # first week: every name new -> the full 12bp


def test_under_16_coins_no_trade_and_last_weeks_names_kept():
    with Files():
        sl = cp.fresh()["sleeves"]["mon"]
        sl["prev_l"], sl["prev_s"] = ["AUSDT"], ["BUSDT"]
        names = [f"C{i:02d}USDT" for i in range(20)]               # 15 with a reading, all different
        cp.open_week("mon", sl, cp.ms(cp.day0("2026-10-26")), universe=lambda now: names,
                     crowd=lambda s, t: (1.0 + names.index(s), 0.5) if names.index(s) < 15 else (None, None),
                     price=lambda s, t: 10.0)
    assert sl["pos"] == [] and sl["opened"] is None and sl["prev_l"] == ["AUSDT"]


def test_funding_window_is_half_open_to_the_minute():
    """Settlements are stamped a few ms after the hour: (a, b] must skip a's own and keep b's."""
    seen = []
    old = cp.mn.get
    cp.mn.get = lambda u: seen.append(u) or []
    try:
        cp.funding_sum("XUSDT", 1_000_000_000_000, 1_000_604_800_000)
    finally:
        cp.mn.get = old
    assert "startTime=1000000060000" in seen[0] and "endTime=1000604859999" in seen[0]


def test_missed_anchors_run_in_time_order():
    X = week_fixture(n=20)
    seen = []
    kw = dict(universe=lambda now: list(X["crowd"]), crowd=lambda s, t: (X["crowd"][s], 0.5),
              price=lambda s, t: X["p0"][s], fsum=lambda s, a, b: 0.0)
    old_open = cp.open_week

    def spy(k, sl, a_ms, **k2):
        seen.append((k, datetime.fromtimestamp(a_ms / 1000, timezone.utc).strftime("%m-%d")))
        return old_open(k, sl, a_ms, **k2)
    cp.open_week = spy
    try:
        with Files():
            st = cp.fresh()
            cp.anchors(st, datetime(2026, 11, 6, 12, tzinfo=timezone.utc), **kw)
    finally:
        cp.open_week = old_open
    assert seen == [("mon", "10-26"), ("thu", "10-29"), ("mon", "11-02"), ("thu", "11-05")], seen
    assert st["sleeves"]["mon"]["next"] == "2026-11-09" and st["sleeves"]["thu"]["next"] == "2026-11-12"
    assert st["sleeves"]["mon"]["weeks"] == 1 and st["sleeves"]["thu"]["weeks"] == 1
    assert abs(st["sleeves"]["mon"]["equity"] - 150 * (1 - cp.FEE)) < 1e-9          # flat prices: the first fee only


def test_nothing_happens_before_the_first_anchor():
    with Files():
        st = cp.fresh()
        cp.anchors(st, datetime(2026, 10, 25, 23, 59, tzinfo=timezone.utc))
        assert all(not sl["pos"] and sl["weeks"] == 0 for sl in st["sleeves"].values())
        assert np.isclose(sum(cp.sleeve_now(sl) for sl in st["sleeves"].values()), 300.0)


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")

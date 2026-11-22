"""Tests for backtest/oi_flush_pit.py - run as a script (no pytest on this PC): python tests/test_oi_flush_pit.py"""
import io
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest import oi_flush_pit as op  # noqa: E402

NS_H = op.NS_H


def bars(prices, start="2024-01-01"):
    t = pd.date_range(start, periods=len(prices), freq="h").to_numpy("datetime64[ns]")
    return t, np.asarray(prices, float)


def crash(n=200, at=50, depth=0.10, after=None):
    p = np.full(n, 100.0)
    p[at:] = 100.0 * (1 - depth)
    if after is not None:
        p[at + 1:at + 1 + len(after)] = after
        p[at + 1 + len(after):] = after[-1]
    return p


def run(p, elig=None, fc=None, t=None):
    if t is None:
        t, c = bars(p)
    else:
        c = np.asarray(p, float)
    fc = np.zeros(len(c) + 1) if fc is None else fc
    elig = np.ones(len(c), bool) if elig is None else elig
    return op.coin_events("X", t, c, fc, elig)


def test_event_timing_entry_and_target():
    ev = run(crash(after=[91.0, 92.0, 96.0]))
    assert len(ev) == 1
    e = ev[0]
    t, _ = bars(crash())
    assert e["t_ev"] == pd.Timestamp(t[50]) + op.H                 # known at the END of the event bar
    assert e["t_entry"] == pd.Timestamp(t[51]) + op.H
    assert e["why"] == "target" and e["hours"] == 2 and abs(e["gross"] - (96 / 91 - 1)) < 1e-12
    assert abs(e["net"] - (e["gross"] - op.COST)) < 1e-12


def test_drop_line_pause_and_eligibility():
    assert run(crash(depth=0.07)) == []
    p = crash(depth=0.10)
    p[60:] = 80.0
    assert len(run(p)) == 2                                        # second leg waits out the 24-hour pause
    el = np.ones(200, bool)
    el[50] = False
    ev = run(crash(), elig=el)
    assert all(e["t_ev"] != pd.Timestamp(bars(crash())[0][50]) + op.H for e in ev)


def test_holes_block_events_and_entries():
    p = crash()
    t, c = bars(p)
    t2 = t.copy()
    t2[40:] = t2[40:] + np.timedelta64(NS_H, "ns")                 # a missing hour inside the 24-hour look-back
    ev = run(c, t=t2)
    assert [e["t_ev"] for e in ev] == [pd.Timestamp(t2[64]) + op.H]   # bars 50-63 look across the hole; 64 is clean
    t3 = t.copy()
    t3[51:] = t3[51:] + np.timedelta64(NS_H, "ns")                 # no bar the hour after the event: no entry
    assert run(c, t=t3) == []


def test_time_exit_delisting_and_funding():
    after = [90.0] + [85.0] * 10 + [88.0] * 200
    e = run(crash(n=400, after=after))[0]
    assert e["why"] == "time" and e["hours"] == op.MAX_H and not e["cut"]
    assert abs(e["worst"] - (85 / 90 - 1)) < 1e-12
    p = crash(n=80, after=[90.0] * 29)                             # the coin stops trading 28 hours after entry
    e = run(p)[0]
    assert e["cut"] and e["hours"] == 79 - 51
    fc = np.zeros(201)
    fc[52:] = 0.3                                                  # at the entry instant (start of bar 52): not charged
    fc[53:] = 0.3 + 0.9                                            # inside the hold: charged
    fc[54:] = 0.3 + 0.9 + 0.6                                      # at the exit instant (end of bar 53): charged
    fc[60:] = 0.3 + 0.9 + 0.6 + 0.45                               # after the exit: not charged
    e = run(crash(after=[90.0, 90.0, 96.0]), fc=fc)[0]             # entry close of 51, exit close of 53
    assert e["hours"] == 2 and abs(e["fund"] - 1.5 / 90.0) < 1e-12
    assert abs(e["net"] - (e["gross"] - op.COST - e["fund"])) < 1e-12


def test_target_is_measured_from_the_entry_and_touch_counts():
    e = run(crash(after=[80.0, 84.0]))[0]                          # entry 80; 84 = exactly +5%
    assert e["why"] == "target" and e["hours"] == 1
    e = run(crash(n=300, after=[95.0, 94.6] + [94.0] * 200))[0]    # 94.6 is +5% on the event close 90, not on the entry 95
    assert e["why"] == "time"


def test_worst_is_measured_after_the_entry():
    e = run(crash(n=300, after=[95.0, 93.0] + [94.0] * 200))[0]    # the event close (90) is below every later price
    assert abs(e["worst"] - (93.0 / 95.0 - 1)) < 1e-12


def test_oi_lookup_tolerance():
    ts = pd.to_datetime(["2024-01-01 00:00", "2024-01-01 00:05", "2024-01-01 00:20"]).astype("datetime64[ns]").astype("int64").to_numpy()
    v = np.array([100.0, 110.0, 120.0])
    assert op.oi_at(ts, v, pd.Timestamp("2024-01-01 00:05")) == 110.0
    assert op.oi_at(ts, v, pd.Timestamp("2024-01-01 00:14")) == 110.0
    assert np.isnan(op.oi_at(ts, v, pd.Timestamp("2024-01-01 00:16")))      # last stamp 11 minutes old
    assert np.isnan(op.oi_at(ts, v, pd.Timestamp("2023-12-31 23:59")))
    assert op.days_for(pd.Timestamp("2024-01-02 00:05")) == {"2024-01-02", "2024-01-01"}
    assert op.days_for(pd.Timestamp("2024-01-02 03:00")) == {"2024-01-02"}


def test_attach_oi_and_groups():
    with tempfile.TemporaryDirectory() as tmp:
        old = op.DAYS
        op.DAYS = Path(tmp)
        try:
            (op.DAYS / "X").mkdir()
            for d, oi in (("2024-01-01", 1000.0), ("2024-01-02", 880.0)):
                st = pd.date_range(d, periods=288, freq="5min")
                pd.DataFrame({"create_time": st.strftime("%Y-%m-%d %H:%M:%S"), "sum_open_interest": oi}).to_csv(op.DAYS / "X" / f"{d}.csv", index=False)
            (op.DAYS / "Y").mkdir()
            (op.DAYS / "Y" / "2024-01-02.csv").write_text("")      # a day Binance does not serve
            E = pd.DataFrame(dict(sym=["X", "Y"], t_ev=[pd.Timestamp("2024-01-02 12:00")] * 2))
            A = op.attach_oi(E)
            assert abs(A.loc[0, "doi"] + 0.12) < 1e-12 and A.loc[0, "g"] == "FLUSH"
            assert A.loc[1, "g"] == "NO_OI"
        finally:
            op.DAYS = old


def test_parse_zip_and_needed_days():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("X-metrics-2024-01-01.csv", "create_time,symbol,sum_open_interest,sum_open_interest_value\n2024-01-01 00:05:00,X,5,10\n")
    d = op.parse_zip(buf.getvalue())
    assert list(d.columns) == ["create_time", "sum_open_interest"] and d.iloc[0, 1] == 5
    E = pd.DataFrame(dict(sym=["X"], t_ev=[pd.Timestamp("2024-01-03 00:00")]))
    assert op.needed(E) == [("X", "2024-01-01"), ("X", "2024-01-02"), ("X", "2024-01-03")]


def frame(n_tune, n_hold, flush_net, build_net, days_each=1, start="2023-01-01"):
    rows = []
    t = pd.Timestamp(start)
    for k in range(n_tune + n_hold):
        for g, base in (("FLUSH", flush_net), ("BUILD", build_net)):
            r = base + (0.01 if k % 2 else -0.01)
            rows.append(dict(sym="X", t_ev=t, day=t.normalize(), g=g, net=r, gross=r + op.COST, why="time", doi=-0.2 if g == "FLUSH" else 0.1,
                             drop=-0.1, cut=False))
        t += pd.Timedelta(days=days_each)
    return pd.DataFrame(rows)


def test_verdict_bar():
    E, _ = op.split_halves(frame(100, 0, 0.02, 0.0))
    v, S = op.verdict(E)
    assert v == "PASS" and S["holdout"]["n"] >= 30
    E, _ = op.split_halves(frame(100, 0, 0.02, 0.03))               # FLUSH positive but under BUILD
    assert op.verdict(E)[0] == "no pass"
    E, _ = op.split_halves(frame(40, 0, 0.02, 0.0))                 # holdout too small
    assert op.verdict(E)[0] == "cannot tell"
    E, _ = op.split_halves(frame(100, 0, -0.005, -0.02))
    assert op.verdict(E)[0] == "no pass"
    E, _ = op.split_halves(frame(100, 0, 0.0025, 0.0))             # t 1.6-1.9 on the halves: under the bar
    v, S = op.verdict(E)
    assert v == "no pass" and all(1.5 < S[h]["t"] < 2 for h in S)
    E, _ = op.split_halves(frame(62, 0, 0.02, 0.0))                 # holdout 25 trades: too few
    v, S = op.verdict(E)
    assert v == "cannot tell" and S["holdout"]["n"] == 25
    F = frame(100, 0, 0.02, 0.0)
    late = F["t_ev"] >= F["t_ev"].sort_values().iloc[int(len(F) * 0.6)]
    F.loc[late & (F.g == "FLUSH"), "net"] -= 0.03                   # good on the tune half, losing on the holdout
    E, _ = op.split_halves(F)
    v, S = op.verdict(E)
    assert S["tune"]["t"] >= 2 and S["holdout"]["m"] < 0 and v == "no pass"


def test_split_ignores_events_without_oi():
    F = frame(50, 0, 0.01, 0.0)
    extra = F.iloc[:10].copy()
    extra["g"], extra["t_ev"] = "NO_OI", pd.Timestamp("2030-01-01")
    E, cut = op.split_halves(pd.concat([F, extra], ignore_index=True))
    S = E[E.g != "NO_OI"].sort_values("t_ev")
    assert cut == S["t_ev"].iloc[int(len(S) * 0.6)] and (E[E.g == "NO_OI"].half == "none").all()


if __name__ == "__main__":
    n = 0
    for k, f in sorted(globals().items()):
        if k.startswith("test_"):
            f()
            n += 1
    print(f"{n} tests passed")

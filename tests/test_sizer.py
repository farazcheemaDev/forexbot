"""Tests for dashboard/lib/size.mjs (the position sizer): the REAL JavaScript function is run by node and compared with hand arithmetic.

Run as a script (no pytest on this PC):  python tests/test_sizer.py
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = (ROOT / "dashboard" / "lib" / "size.mjs").as_uri()
FEE, MAINT = 0.0012, 0.005


def run(**kw):
    js = f"import {{ sizeCall }} from '{MOD}'; console.log(JSON.stringify(sizeCall({json.dumps(kw)})));"
    r = subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(b))


def test_a_long_sized_by_hand():
    r = run(side="long", entry=100, stop=98.4, target=108, bal=1000, lev=10, riskPct=0.005)
    s = 0.016
    notional = 5 / (s + FEE)
    assert near(r["stopPct"], s) and near(r["notional"], notional) and near(r["qty"], notional / 100) and r["capped"] is False
    assert near(r["margin"], notional / 10) and near(r["marginShare"], notional / 10 / 1000) and r["affordable"] is True
    assert near(r["liqDist"], 0.1 - MAINT) and near(r["liqPrice"], 100 * (1 - 0.095))                 # 90.5: the price that wipes the margin
    assert near(r["lossAtStop"], 5.0) and near(r["lossShare"], 0.005)                                  # a stop-out costs exactly the risk share, fee included
    assert near(r["targetPct"], 0.08) and near(r["gainAtTarget"], notional * (0.08 - FEE))
    assert near(r["room"], 0.095 - s) and near(r["roomX"], 0.095 / s) and r["status"] == "ok"
    assert r["maxLev"] == 27                                                                           # floor(1 / (2 x 1.6% + 0.5%))


def test_a_short_mirrors_the_long():
    r = run(side="short", entry=100, stop=101.6, target=92, bal=1000, lev=10, riskPct=0.005)
    assert near(r["liqPrice"], 100 * (1 + 0.095)) and near(r["targetPct"], 0.08) and near(r["stopPct"], 0.016)
    assert near(r["lossAtStop"], 5.0) and r["status"] == "ok"


def test_the_room_between_the_stop_and_liquidation_by_leverage():
    base = dict(side="long", entry=100, stop=98.4, target=108, bal=1000, riskPct=0.005)        # a 1.6% stop
    assert run(**base, lev=50)["status"] == "danger"          # liquidation 1.5% away is INSIDE the 1.6% stop: liquidated before the stop
    assert run(**base, lev=30)["status"] == "tight"           # 2.83% away: past the stop, but not twice as far (3.2%)
    assert run(**base, lev=20)["status"] == "ok"              # 4.5% away
    assert run(**base, lev=27)["status"] == "ok" and run(**base, lev=28)["status"] == "tight"   # maxLev 27 is exactly where the 2x gap ends
    assert run(**base, lev=50)["room"] < 0 < run(**base, lev=20)["room"]


def test_the_desks_three_times_cap_and_the_margin_check():
    capped = run(side="long", entry=100, stop=99.97, target=101, bal=100, lev=10, riskPct=0.005)         # 0.03% stop: 0.5 / 0.0015 = 333 wanted
    assert capped["capped"] is True and near(capped["notional"], 300) and capped["lossAtStop"] < 0.5          # capped: the loss at the stop is smaller than the risk share
    free = run(side="long", entry=100, stop=99.8, target=101, bal=100, lev=10, riskPct=0.005)
    assert free["capped"] is False
    poor = run(side="long", entry=100, stop=99.2, target=104, bal=100, lev=1, riskPct=0.005)             # 0.8% stop: notional 0.5 / 0.0092 = 54; at 1x the margin is 54 of 100
    assert poor["affordable"] is True
    poor = run(side="long", entry=100, stop=99.5, target=104, bal=100, lev=1, riskPct=0.01)              # 1% risk on a 0.5% stop: notional 1 / 0.0062 = 161 at 1x needs 161 of 100
    assert poor["affordable"] is False and poor["marginShare"] > 1


def test_nonsense_gets_no_size_not_a_wrong_one():
    ok = dict(side="long", entry=100, stop=98.4, target=108, bal=1000, lev=10, riskPct=0.005)
    assert run(**{**ok, "stop": 101}) is None                  # a long's stop above its entry
    assert run(**{**ok, "side": "short"}) is None              # the same numbers read as a short: stop on the winning side
    assert run(**{**ok, "bal": 0}) is None and run(**{**ok, "lev": 0.5}) is None and run(**{**ok, "riskPct": 0}) is None
    wrong_target = run(**{**ok, "target": 99})                 # a target on the losing side: no gain figure, still sized
    assert wrong_target["gainAtTarget"] is None and wrong_target["targetPct"] < 0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")

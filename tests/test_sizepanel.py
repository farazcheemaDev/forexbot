"""Tests for dashboard/lib/sizepanel.mjs (the logic behind the size panel): the REAL JavaScript is run by node and compared with hand arithmetic.

Run as a script (no pytest on this PC):  python tests/test_sizepanel.py
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = (ROOT / "dashboard" / "lib" / "sizepanel.mjs").as_uri()
FEE = 0.0012


def js(expr):
    code = f"import {{ parseNum, levelsFor, buildSizing, fmtQty, MIN_NOTIONAL }} from '{MOD}'; console.log(JSON.stringify({expr}));"
    r = subprocess.run(["node", "--input-type=module", "-e", code], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def near(a, b, tol=1e-9):
    return abs(a - b) <= tol * max(1.0, abs(b))


def build(**kw):
    base = dict(side="long", entry=100, stop=98, target=105, bal=1000, lev=10, riskPct=1)
    base.update(kw)
    return js(f"buildSizing({json.dumps(base)})")


def test_what_a_person_types_becomes_a_positive_number_or_nothing():
    good = js('["20", "20.5", " 20.5 ", "1,000", ".5", "20."].map(parseNum)')
    assert good == [20, 20.5, 20.5, 1000, 0.5, 20]
    bad = js('["", "abc", "-3", "0", "0.0", "1e3", "2 0", null, undefined, "NaN", "Infinity"].map(parseNum)')
    assert bad == [None] * 11


def test_the_levels_come_from_the_price_now_or_the_desks_logged_entry():
    call = dict(side="long", entry=100, mark=101, stop=98, target=105)
    assert js(f"levelsFor({json.dumps(call)}, 'now')") == dict(side="long", entry=101, stop=98, target=105)
    assert js(f"levelsFor({json.dumps(call)}, 'logged')") == dict(side="long", entry=100, stop=98, target=105)
    for mark in (None, 0, -5):                                              # no usable price now: fall back to the logged entry
        assert js(f"levelsFor({json.dumps({**call, 'mark': mark})}, 'now')")["entry"] == 100


def test_a_call_sized_by_hand():
    # the XRP call the desk logged at 16:07 UTC: 1.40% stop, 7.94% target, $20 at 5x and 1% risk
    entry = 1.187
    r = build(entry=entry, stop=entry * (1 - 0.014), target=entry * (1 + 0.0794), bal=20, lev=5, riskPct=1)
    notional = 20 * 0.01 / (0.014 + FEE)
    assert r["ok"] and not r["belowMin"] and not r["notAffordable"] and not r["capped"] and not r["noTarget"] and not r["targetGone"]
    assert near(r["r"]["notional"], notional) and near(r["r"]["qty"], notional / entry) and near(r["r"]["margin"], notional / 5)
    assert near(r["r"]["lossAtStop"], 0.2) and near(r["r"]["gainAtTarget"], notional * (0.0794 - FEE)) and near(r["rr"], 0.0794 / 0.014)
    assert near(r["needRiskPct"], 5 * (0.014 + FEE) / 20 * 100) and r["minLev"] == 1 and r["r"]["status"] == "ok" and r["r"]["maxLev"] == 30


def test_the_five_dollar_minimum_and_the_risk_that_would_reach_it():
    r = build(entry=100, stop=97, target=106, bal=10, lev=5, riskPct=0.5)          # $0.05 risk / 3.12% = $1.60
    assert r["ok"] and r["belowMin"] and near(r["r"]["notional"], 0.05 / 0.0312) and near(r["needRiskPct"], 5 * 0.0312 / 10 * 100)
    assert not build(entry=100, stop=97, target=106, bal=10, lev=5, riskPct=1.57)["belowMin"]     # just above the 1.56% needed
    assert build(entry=100, stop=97, target=106, bal=10, lev=5, riskPct=1.55)["belowMin"]


def test_leverage_too_low_to_afford_the_margin_and_the_lowest_that_fits():
    r = build(entry=100, stop=99.5, target=101, bal=10, lev=1, riskPct=1.5)         # notional 0.15 / 0.0062 = $24.19 on a $10 balance at 1x (under the 3x cap of $30)
    assert r["notAffordable"] and not r["capped"] and near(r["r"]["notional"], 0.15 / 0.0062) and r["minLev"] == 3
    ok = build(entry=100, stop=99.5, target=101, bal=10, lev=3, riskPct=1.5)
    assert not ok["notAffordable"] and near(ok["r"]["margin"], 0.15 / 0.0062 / 3)
    capped = build(entry=100, stop=99.5, target=101, bal=10, lev=1, riskPct=2)       # 2% would be $32.26: the 3x rule cuts it to $30, which still needs 3x
    assert capped["capped"] and near(capped["r"]["notional"], 30) and capped["minLev"] == 3


def test_the_three_times_cap_makes_the_loss_at_the_stop_smaller_than_the_risk():
    r = build(entry=100, stop=99.97, target=100.5, bal=100, lev=10, riskPct=1)
    assert r["capped"] and near(r["r"]["notional"], 300) and near(r["r"]["lossAtStop"], 300 * (0.0003 + FEE)) and r["r"]["lossAtStop"] < 1.0


def test_a_target_already_passed_or_not_given_has_no_gain_and_no_ratio():
    gone = build(entry=100, stop=98, target=99)                                       # a long whose target is below the price
    assert gone["ok"] and gone["targetGone"] and not gone["noTarget"] and gone["rr"] is None and gone["r"]["gainAtTarget"] is None
    none = build(entry=100, stop=98, target=None)                                      # a trade typed by hand without a target
    assert none["ok"] and none["noTarget"] and not none["targetGone"] and none["rr"] is None
    short = build(side="short", entry=100, stop=102, target=95)
    assert short["ok"] and near(short["rr"], 5 / 2) and not short["targetGone"]


def test_a_stop_on_the_wrong_side_is_refused_with_the_reason_for_that_side():
    long_ = build(side="long", entry=100, stop=101)
    short = build(side="short", entry=100, stop=99)
    assert not long_["ok"] and "below the entry for a long" in long_["reason"]
    assert not short["ok"] and "above the entry for a short" in short["reason"]


def test_every_missing_or_silly_input_gets_its_own_message():
    assert "balance" in build(bal=None)["reason"] and "balance" in build(bal=0)["reason"]
    assert "leverage" in build(lev=None)["reason"] and "leverage" in build(lev=0.5)["reason"]
    assert "risk" in build(riskPct=None)["reason"] and "risk" in build(riskPct=0)["reason"] and "risk" in build(riskPct=101)["reason"]
    assert "entry" in build(entry=None)["reason"] and "entry" in build(stop=None)["reason"]
    assert build(riskPct=100)["ok"]                                                    # 100% is the edge of allowed, not past it


def test_the_room_between_the_stop_and_liquidation_by_leverage():
    base = dict(entry=100, stop=98.4, target=108, bal=1000, riskPct=1)                 # a 1.6% stop
    assert build(**base, lev=50)["r"]["status"] == "danger" and build(**base, lev=50)["r"]["room"] < 0
    assert build(**base, lev=30)["r"]["status"] == "tight"
    assert build(**base, lev=20)["r"]["status"] == "ok" and build(**base, lev=20)["r"]["room"] > 0


def test_coin_quantities_are_shown_with_a_readable_number_of_digits():
    out = js('[130.4, 100, 99.999, 12.3456, 1, 0.0123456, 0.01, 0.000123456, NaN, Infinity].map(fmtQty)')
    assert out == ["130", "100", "100.00", "12.35", "1.00", "0.0123", "0.0100", "0.000123", "–", "–"]


def test_the_minimum_order_constant_is_five_dollars():
    assert js("MIN_NOTIONAL") == 5


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")

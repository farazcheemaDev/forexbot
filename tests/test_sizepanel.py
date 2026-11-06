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
    code = f"import {{ parseNum, levelsFor, buildSizing, fmtQty, MIN_NOTIONAL, todaysPick, plainSetup, liveFromHere }} from '{MOD}'; console.log(JSON.stringify({expr}));"
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


def mk(id, kind="sweet", **kw):
    c = dict(id=id, side="long", entry=100, stop=98, target=105, mark=100, sw=dict(kind=kind, valid=True))
    c.update(kw)
    return c


def pick(calls, scored_ids):
    return js(f"(() => {{ const p = todaysPick({json.dumps(calls)}, (c) => {json.dumps(scored_ids)}.includes(c.id)); return p === null ? null : p.id; }})()")


def live(c):
    return js(f"liveFromHere({json.dumps(c)})")


def test_a_call_is_only_worth_entering_while_the_price_is_still_between_a_real_stop_and_the_target():
    assert live(mk(1))                                                                  # 2% from the stop, target ahead
    assert live(mk(1, mark=None))                                                       # no price now: judged at the logged entry
    assert not live(mk(1, mark=98.2))                                                   # 0.18% above a 98 stop: scalp-sized from here
    assert not live(mk(1, mark=98))                                                     # at the stop
    assert not live(mk(1, mark=97))                                                     # past the stop: the call is over
    assert not live(mk(1, mark=105))                                                    # at the target
    assert not live(mk(1, mark=106))                                                    # past the target
    assert not live(mk(1, sw=dict(kind="sweet", valid=False)))                          # the desk's own 1.5R floor no longer holds from here
    assert live(mk(1, mark=98.6))                                                       # 0.7% above the stop: a middle size, still fine to size
    short = dict(side="short", entry=100, stop=102, target=95)
    assert live(mk(1, mark=100, **short)) and not live(mk(1, mark=101.8, **short)) and not live(mk(1, mark=102, **short)) and not live(mk(1, mark=95, **short))


def test_the_bots_pick_is_the_newest_live_sweet_spot_call_that_counts_in_the_test():
    calls = [mk(84), mk(86), mk(88), mk(91, "mid"), mk(93)]
    assert pick(calls, [93]) == 93
    assert pick(calls, [86]) == 86                       # a call that counts beats a newer one that does not
    assert pick(calls, [86, 88]) == 88                   # of two that count, the newer
    assert pick(calls, []) == 93                         # none counts: the newest sweet-spot call
    assert pick(calls[:3] + [mk(95, "mid"), mk(96, "scalp")], []) == 88    # newer middle / scalp calls are never the pick


def test_a_call_the_price_has_already_run_through_is_not_the_pick():
    calls = [mk(88), mk(93, mark=98.2)]                  # 93 is the newest and counts, but its stop is 0.18% away now
    assert pick(calls, [93]) == 88                       # the older live call is the pick instead
    assert pick([mk(93, mark=98.2), mk(94, mark=97)], [93, 94]) is None         # every call is dead from here: no pick


def test_no_sweet_spot_call_means_no_pick():
    assert pick([], []) is None
    assert pick([mk(91, "mid"), mk(92, "scalp"), mk(93, "small")], [91, 92, 93]) is None
    assert pick([dict(id=7)], [7]) is None               # a call without the sweet-spot block cannot be a pick


def test_a_scalp_sized_stop_is_flagged_on_the_entry_used():
    assert build(entry=100, stop=99.7, target=103)["scalpStop"] is True                # 0.3%
    assert build(entry=100, stop=99.5, target=103)["scalpStop"] is False               # 0.5%
    assert build(entry=100, stop=99.7, target=103, side="long")["ok"]


def test_the_desks_setups_are_described_in_plain_words():
    out = js('[["SR","long"],["SR","short"],["FIB","long"],["FIB","short"],["SMC","long"],["SMC","short"],["XYZ","long"]].map(([m, s]) => plainSetup(m, s))')
    assert len(set(out)) == 7 and out[6] == "the desk's rule fired"
    assert "bounced up off a level" in out[0] and "turned back down at a level" in out[1]
    assert "Fibonacci zone of the last upward move" in out[2] and "Fibonacci zone of the last downward move" in out[3]
    assert "dipped under the lowest low of the last 24 hours" in out[4] and "poked above the highest high of the last 24 hours" in out[5]
    assert not any(" SMC " in x or " SR " in x or "SMC" == x for x in out[:6])      # no bare jargon labels
    assert js("plainSetup('SMC', 'weird')") == out[4]                                # an unknown side reads as a long, not as nothing


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("ok", fn.__name__)
    print(len(tests), "tests passed")

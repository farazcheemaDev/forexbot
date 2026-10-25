"""poly_structure.py offline: fake gamma and CLOB, no network. Run as a script (no pytest on this PC)."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import poly_structure as ps  # noqa: E402

NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


def approx(a, b, tol=1e-9):
    return abs(a - b) <= tol


def book(asks=(), bids=(), min_size=5):
    return dict(asks=[dict(price=str(p), size=str(s)) for p, s in asks],
                bids=[dict(price=str(p), size=str(s)) for p, s in bids], min_order_size=str(min_size))


def market(i, rate=0.0, live=True, other=False, yn=True):
    return dict(cid=f"c{i}", q=f"Outcome {i}", yes=f"y{i}", no=f"n{i}", yn=yn, live=live, other=other, rate=rate,
                exp=1.0, min_size=5.0, bid=None, ask=None, spread=None, vol24=0.0)


def event(markets, aug=False):
    return dict(id="E1", title="Test event", neg=True, aug=aug, end="2026-12-31T00:00:00Z", markets=markets)


def no_books(yes_bids, depth=100.0):
    """Books where each outcome's NO ask is 1 - its YES bid (the mirror), `depth` shares at the top."""
    b = {}
    for i, p in enumerate(yes_bids):
        b[f"n{i}"] = book(asks=[(round(1 - p, 4), depth)])
        b[f"y{i}"] = book(bids=[(p, depth)])
    return b


def test_fee_matches_the_docs_table():
    assert approx(100 * ps.fee_per_share(0.5, 0.05), 1.25)          # sports peak
    assert approx(100 * ps.fee_per_share(0.30, 0.05), 1.05)
    assert approx(100 * ps.fee_per_share(0.70, 0.05), 1.05)         # symmetric
    assert approx(100 * ps.fee_per_share(0.5, 0.07), 1.75)          # crypto peak
    assert approx(100 * ps.fee_per_share(0.01, 0.04), 0.0396)


def test_best_set_walks_depth_and_stops_at_zero_margin():
    legs = [dict(asks=[(0.30, 10), (0.35, 10), (0.50, 10)], rate=0, exp=1),
            dict(asks=[(0.30, 25)], rate=0, exp=1),
            dict(asks=[(0.30, 100)], rate=0, exp=1)]
    r = ps.best_set(legs, 1.0)
    # first 10 sets cost .90 (margin .10), next 10 cost .95 (margin .05); leg 0's third level would be 1.10: not taken
    assert approx(r["shares"], 20) and approx(r["profit"], 1.5) and approx(r["capital"], 18.5), r
    assert approx(r["gross_top"], 0.10) and approx(r["net_top"], 0.10)


def test_fees_are_charged_on_every_leg():
    legs = [dict(asks=[(0.30, 10)], rate=0.05, exp=1), dict(asks=[(0.30, 10)], rate=0.05, exp=1),
            dict(asks=[(0.30, 10)], rate=0.05, exp=1)]
    r = ps.best_set(legs, 1.0)
    margin = 1 - 0.90 - 3 * 0.05 * 0.30 * 0.70
    assert approx(r["net_top"], margin) and approx(r["profit"], 10 * margin, 1e-9), r
    # a gap smaller than the fees is not a trade
    thin = [dict(asks=[(0.33, 10)], rate=0.05, exp=1)] * 3
    assert ps.best_set(thin, 1.0)["shares"] == 0 and ps.best_set(thin, 1.0)["gross_top"] > 0


def test_budget_caps_the_capital():
    legs = [dict(asks=[(0.30, 100)], rate=0, exp=1)] * 3
    assert approx(ps.best_set(legs, 1.0, budget=9.0)["shares"], 10)
    assert approx(ps.best_set(legs, 1.0, budget=4.5)["capital"], 4.5)


def test_a_leg_without_asks_makes_the_basket_impossible():
    r = ps.best_set([dict(asks=[(0.3, 10)], rate=0, exp=1), dict(asks=[], rate=0, exp=1)], 1.0)
    assert r["shares"] == 0 and r["gross_top"] is None


def test_no_basket_pays_k_minus_one():
    ev = event([market(i) for i in range(3)])
    rows = ps.event_baskets(ev, no_books([0.40, 0.35, 0.30]), NOW)         # YES bids sum 1.05
    r = [x for x in rows if x["kind"] == "no_basket"][0]
    assert approx(r["gross_top"], 0.05, 1e-6), r
    assert r["shares"] == 100 and approx(r["profit"], 5.0, 1e-3) and r["executable"] == 1, r
    # k instead of k-1 would read this basket as 1.05 + 1 richer
    fair = ps.event_baskets(event([market(i) for i in range(3)]), no_books([0.30, 0.30, 0.30]), NOW)
    assert [x for x in fair if x["kind"] == "no_basket"][0]["profit"] == 0.0


def test_yes_basket_only_on_complete_standard_events():
    asks = {f"y{i}": book(asks=[(0.30, 50)]) for i in range(3)}            # sum 0.90: 10 points under
    asks.update({f"n{i}": book(asks=[(0.75, 50)]) for i in range(3)})
    std = ps.event_baskets(event([market(i) for i in range(3)]), asks, NOW)
    yes = [x for x in std if x["kind"] == "yes_basket"]
    assert len(yes) == 1 and approx(yes[0]["profit"], 5.0, 1e-3), yes
    assert not [x for x in ps.event_baskets(event([market(i) for i in range(3)], aug=True), asks, NOW)
                if x["kind"] == "yes_basket"]
    dead = [market(0), market(1), market(2, live=False)]
    assert not [x for x in ps.event_baskets(event(dead), asks, NOW) if x["kind"] == "yes_basket"]


def test_other_and_dead_markets_stay_out_of_the_no_basket():
    ms = [market(0), market(1), market(2, other=True), market(3, live=False)]
    rows = ps.event_baskets(event(ms, aug=True), no_books([0.55, 0.55, 0.9, 0.9]), NOW)
    r = [x for x in rows if x["kind"] == "no_basket"][0]
    assert r["legs"] == 2 and approx(r["gross_top"], 0.10, 1e-6), r       # k=2: pays 1, costs .45+.45


def test_below_the_venue_minimum_is_not_executable():
    ev = event([market(i) for i in range(3)])
    r = [x for x in ps.event_baskets(ev, no_books([0.40, 0.35, 0.30], depth=3.0), NOW) if x["kind"] == "no_basket"][0]
    assert r["shares"] == 3 and r["executable"] == 0 and not ps.positive(r), r


def test_a_missing_book_prices_nothing():
    ev = event([market(i) for i in range(3)])
    books = no_books([0.40, 0.35, 0.30])
    del books["n2"]
    assert not [x for x in ps.event_baskets(ev, books, NOW) if x["kind"] == "no_basket"]


def test_parse_event_reads_fees_tokens_and_flags():
    raw = dict(id=7, title="T", negRisk=True, negRiskAugmented=True, endDate="2026-12-31T00:00:00Z", markets=[
        dict(conditionId="c", question="Q", outcomes='["Yes", "No"]', clobTokenIds='["a", "b"]', active=True, closed=False,
             enableOrderBook=True, acceptingOrders=True, feesEnabled=True, feeSchedule=dict(rate=0.04, exponent=1),
             negRiskOther=True, bestBid=0.4, bestAsk=0.45, orderMinSize=5),
        dict(conditionId="d", question="Q2", outcomes='["Yes", "No"]', clobTokenIds='["e", "f"]', active=True, closed=False,
             enableOrderBook=True, feesEnabled=False),
        dict(conditionId="g", clobTokenIds='["only-one"]')])
    e = ps.parse_event(raw)
    assert e["aug"] and e["neg"] and len(e["markets"]) == 2
    a, b = e["markets"]
    assert a["rate"] == 0.04 and a["yes"] == "a" and a["no"] == "b" and a["live"] and a["other"] and a["yn"]
    assert b["rate"] == 0.0 and not b["other"]


def test_fetch_books_batches_by_500_and_tolerates_missing():
    calls = []

    def fake(url, data=None, **kw):
        calls.append(len(data))
        return [dict(asset_id=d["token_id"], asks=[], bids=[]) for d in data if not d["token_id"].endswith("0")]

    old, ps.get = ps.get, fake
    try:
        books = ps.fetch_books([f"t{i}" for i in range(1200)], pause=0)
    finally:
        ps.get = old
    assert calls == [500, 500, 200] and len(books) == 1200 - 120


def test_reward_scoring_follows_the_docs():
    assert approx(ps.score(3, 1), (2 / 3) ** 2) and ps.score(3, 3) == 0 and ps.score(3, 4) == 0
    # docs worked example, side one: ((3-1)/3)^2*100 + ((3-2)/3)^2*200 + ((3-1)/3)^2*100
    q = ps.score(3, 1) * 100 + ps.score(3, 2) * 200 + ps.score(3, 1) * 100
    assert approx(q, 111.1111111, 1e-6)
    assert approx(ps.q_min(100, 20, 0.5), 33.3333333, 1e-6)                # one-sided leaning: max(min, max/3)
    assert approx(ps.q_min(100, 20, 0.5), max(20, 100 / 3))
    assert ps.q_min(100, 20, 0.95) == 20                                   # extreme midpoint: two-sided only
    assert ps.q_min(100, 0, 0.5) > 0 and ps.q_min(100, 0, 0.05) == 0


def test_reward_share_against_an_equal_competitor_is_half():
    yes = book(bids=[(0.49, 100)], asks=[(0.51, 100)])
    e = ps.reward_estimate(yes, book(), rate=100.0, v_cents=3.0, min_size=20, offset_frac=1 / 3, size=100)
    assert approx(e["mid"], 0.50) and approx(e["share"], 0.5, 1e-9) and approx(e["per_day"], 50.0, 1e-6), e
    assert approx(e["capital"], 100 * (0.49 + 0.49), 1e-9)                 # bid + the ask as a NO bid
    tight = ps.reward_estimate(yes, book(), 100.0, 3.0, 20, 0.1, size=100)
    wide = ps.reward_estimate(yes, book(), 100.0, 3.0, 20, 0.8, size=100)
    assert tight["share"] > e["share"] > wide["share"]


def test_orders_under_the_minimum_do_not_score_and_a_one_sided_book_has_no_mid():
    yes = book(bids=[(0.49, 10)], asks=[(0.51, 10)])
    assert ps.reward_estimate(yes, book(), 100.0, 3.0, 20, 0.5) is None
    assert ps.reward_estimate(book(bids=[(0.49, 100)]), book(), 100.0, 3.0, 20, 0.5) is None
    q1, q2 = ps.side_scores(book(bids=[(0.49, 100)]), book(asks=[(0.52, 100)]), 0.50, 0.03, 20)
    assert approx(q1, ps.score(0.03, 0.01) * 100 + ps.score(0.03, 0.02) * 100)   # a NO ask at .52 = a YES bid at .48
    assert q2 == 0


def test_touch_cost_marks_a_fill_at_the_print_that_went_through():
    f, lost = ps.touch_cost([0.50, 0.50, 0.46, 0.46], 0.03, 100)
    assert f == 1 and approx(lost, 0.01 * 100, 1e-9)
    f, lost = ps.touch_cost([0.50, 0.52, 0.51, 0.50], 0.03, 100)
    assert f == 0 and lost == 0
    f, lost = ps.touch_cost([0.50, 0.55], 0.03, 100)
    assert f == 1 and approx(lost, 0.02 * 100, 1e-9)


def test_episodes_track_runs_and_censor_the_open_one():
    good = dict(executable=1, profit=1.0, roi=0.01, capital=100.0, title="x")
    bad = dict(executable=1, profit=0.0, roi=0.0, capital=0.0, title="x")
    ep = ps.Episodes()
    k = ("E", "no_basket")
    for t, r in ((0, good), (20, good), (40, bad), (60, good)):
        ep.update(t, k, r)
    assert len(ep.done) == 1 and ps.duration(ep.done[0]) == 20 and ep.done[0]["n"] == 2
    ep.update(80, k, None)                                                 # the event dropped out of the sample
    assert len(ep.done) == 2 and ps.duration(ep.done[1]) == 0
    ep.update(100, k, good)
    ep.close_all()
    assert ep.done[-1]["censored"] == 1 and not ep.open


def test_a_yes_basket_is_judged_per_year_and_a_no_basket_per_trade():
    assert ps.ann_return("no", 0.01, 100) is None and ps.ann_return("yes", 0.01, float("nan")) is None
    assert approx(ps.ann_return("yes", 0.0225, 432.4), 0.0225 * 365 / 432.4, 1e-4)
    assert not ps.worth_taking("yes_basket", 0.0225, 0.019, 278)          # the census's Maduro gap: a 432-day bond
    assert ps.worth_taking("yes_basket", 0.05, 0.40, 278)
    assert ps.worth_taking("no_basket", 0.006, None, 100) and not ps.worth_taking("no_basket", 0.004, None, 100)
    assert not ps.worth_taking("no_basket", 0.02, None, 40)               # under $50 of capital
    asks = {f"y{i}": book(asks=[(0.30, 50)]) for i in range(3)}
    asks.update({f"n{i}": book(asks=[(0.75, 50)]) for i in range(3)})
    rows = ps.event_baskets(event([market(i) for i in range(3)]), asks, NOW)
    yes = [r for r in rows if r["kind"] == "yes_basket"][0]
    assert approx(yes["ann_roi"], yes["roi"] * 365 / yes["days_to_end"], 2e-3), yes   # days rounded to 0.1 in the row
    assert all(r["ann_roi"] is None for r in rows if r["kind"] == "no_basket")


def test_a_basket_must_clear_the_dollar_floor():
    assert not ps.positive(dict(executable=1, profit=0.05)) and ps.positive(dict(executable=1, profit=0.5))
    assert not ps.positive(dict(executable=0, profit=50.0))


def test_census_prices_only_neg_risk_events_end_to_end():
    ev = event([market(i) for i in range(3)])
    plain = dict(ev, id="P", neg=False)
    books = no_books([0.40, 0.35, 0.30])

    def fake(url, data=None, **kw):
        assert url.endswith("/books")
        return [dict(books[d["token_id"]], asset_id=d["token_id"]) for d in data if d["token_id"] in books]

    old, ps.get = ps.get, fake
    try:
        rows, got, mirror = ps.census([ev, plain], NOW)
    finally:
        ps.get = old
    assert {r["event_id"] for r in rows} == {"E1"} and len(got) == 6
    assert max(mirror) < 1e-9


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")

"""crowd_book.py offline: the crowd-squeeze book inside the machine (--crowd, the fresh account). No network, no keys.

    python tests/test_crowd_book.py
"""
from __future__ import annotations

import json
import random
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.argv = [sys.argv[0]]
import combo_paper as cp  # noqa: E402

cp.set_dir(Path(tempfile.mkdtemp()))
import crowd_book as crb  # noqa: E402
import dashboard_push as dp  # noqa: E402
import final_books as fb  # noqa: E402
import news_books as nbk  # noqa: E402
from news import crowd_paper as cpb  # noqa: E402

SUN = datetime(2026, 10, 25, 17, tzinfo=timezone.utc)
MON = datetime(2026, 10, 26, 0, 2, tzinfo=timezone.utc)
MS = lambda d: int(d.timestamp() * 1000)  # noqa: E731
NOFUND = lambda s, a, b: 0.0  # noqa: E731


def account(eq=300.0, crowd=True, now=SUN):
    st = dict(equity=eq, cum=dict(trend=0.0, mn=0.0, sleeve=0.0, fees=0.0), last_day=None, exec={},
              trend=dict(open={}), mn=dict(weights={}, mark_px={}, base=0.0), sleeve=dict(hold={}, mark_px={}))
    st["fin"] = fb.fresh()
    nbk.ensure(st)
    if crowd:
        st["fin"]["crowd"] = crb.fresh(now)
    return st


def market(seed=1, n=24):
    rnd = random.Random(seed)
    syms = [f"C{i:02d}USDT" for i in range(n)]
    return (syms, {s: rnd.uniform(0.5, 3.0) for s in syms}, {s: rnd.uniform(1, 100) for s in syms},
            {s: rnd.uniform(-0.3, 0.6) for s in syms}, {s: rnd.uniform(-0.01, 0.01) for s in syms})


def kw(syms, crowd):
    return dict(universe=lambda now: syms, crowd=lambda s, t: (crowd[s], 0.5))


def test_without_the_flag_nothing_exists_and_nothing_changes():
    st = account(crowd=False)
    crb.ensure(st, False)
    assert "crowd" not in st["fin"] and crb.targets(st) == {}
    before = json.dumps(st, sort_keys=True)
    syms, crowd, px, _, _ = market()
    crb.poll(st, px, MS(MON), fund=NOFUND, **kw(syms, crowd))
    assert json.dumps(st, sort_keys=True) == before                          # main's state is untouched


def test_the_first_anchors_are_the_next_monday_and_thursday():
    s = crb.fresh(datetime(2026, 10, 25, 17, tzinfo=timezone.utc))["sleeves"]       # a fixed clock: ensure() reads the real one
    assert s["mon"]["next"] == "2026-10-26" and s["thu"]["next"] == "2026-10-29"
    assert crb.fresh(datetime(2026, 10, 26, 5, tzinfo=timezone.utc))["sleeves"]["mon"]["next"] == "2026-11-02"
    st = account(crowd=False)
    crb.ensure(st, True)                                                              # the real clock: only that it adds a book
    assert set(st["fin"]["crowd"]["sleeves"]) == {"mon", "thu"} and st["fin"]["crowd"]["on"]


def test_at_the_anchor_the_half_opens_the_papers_legs_on_half_the_account():
    st = account()
    syms, crowd, px, _, _ = market()
    crb.poll(st, px, MS(SUN), fund=NOFUND, **kw(syms, crowd))                 # before the anchor: nothing
    assert crb.targets(st) == {}
    crb.poll(st, px, MS(MON), fund=NOFUND, **kw(syms, crowd))
    sl = st["fin"]["crowd"]["sleeves"]["mon"]
    want = cpb.legs(crowd, px)
    assert [(p["sym"], p["side"]) for p in sl["pos"]] == [(p["sym"], p["side"]) for p in want]
    assert abs(sl["cap"] - 150.0) < 1e-9 and sl["next"] == "2026-11-02"
    t = crb.targets(st)
    for p in sl["pos"]:
        assert abs(t[p["sym"]] - p["side"] * p["w"] * 150.0 / px[p["sym"]]) < 1e-9
    assert abs(st["equity"] - (300.0 - cpb.FEE * 150.0)) < 1e-9                # the first week: every name new
    assert st["fin"]["crowd"]["sleeves"]["thu"]["pos"] == []                  # Thursday's half waits for Thursday
    ft = fb.targets(st)                                                        # and the account's targets carry it
    assert all(abs(ft[s] - q) < 1e-12 for s, q in t.items())


def test_a_week_books_the_backtests_net_week_on_the_halfs_capital():
    st = account()
    syms, crowd, px0, move, fund = market(seed=3)
    crb.poll(st, px0, MS(MON), fund=NOFUND, **kw(syms, crowd))
    sl = st["fin"]["crowd"]["sleeves"]["mon"]
    pos, cap, eq0 = [dict(p) for p in sl["pos"]], sl["cap"], st["equity"]
    px1 = {s: px0[s] * (1 + move[s]) for s in syms}
    nxt = datetime(2026, 11, 2, 0, 2, tzinfo=timezone.utc)
    crb.poll(st, px1, MS(nxt), fund=lambda s, a, b: fund[s], **kw(syms, crowd))
    g = cpb.gross(pos, px1, fund)                                              # crowd_paper's own week
    reopen_fee = cpb.turnover_fee(set(p["sym"] for p in pos if p["side"] > 0), set(p["sym"] for p in pos if p["side"] < 0),
                                  set(sl["prev_l"]), set(sl["prev_s"])) * sl["cap"]
    assert abs(st["cum"]["crowd"] - g * cap) < 1e-9 and sl["weeks"] == 1 and sl["pos"]
    thu = st["fin"]["crowd"]["sleeves"]["thu"]                                 # Thursday's 10-29 anchor came due too
    fees = st["cum"]["crowd_fees"]
    assert abs(fees - (cpb.FEE * 150.0 + reopen_fee + cpb.FEE * thu["cap"])) < 1e-9
    assert abs(st["equity"] - (eq0 + cpb.FEE * 150.0 + g * cap - fees)) < 1e-9


def test_after_more_than_a_week_down_only_the_latest_anchor_trades():
    st = account()
    syms, crowd, px, _, _ = market()
    late = datetime(2026, 11, 10, 3, tzinfo=timezone.utc)                     # mon 10-26 and 11-02 missed
    crb.poll(st, px, MS(late), fund=NOFUND, **kw(syms, crowd))
    s = st["fin"]["crowd"]["sleeves"]
    assert s["mon"]["opened"] == "2026-11-09" and s["mon"]["next"] == "2026-11-16"
    assert s["thu"]["opened"] == "2026-11-05" and s["thu"]["next"] == "2026-11-12"


def test_a_network_failure_books_nothing_and_retries():
    st = account()
    syms, crowd, px, _, _ = market()
    boom = lambda s, t: (_ for _ in ()).throw(ConnectionError("down"))  # noqa: E731
    crb.poll(st, px, MS(MON), fund=NOFUND, universe=lambda now: syms, crowd=boom)
    sl = st["fin"]["crowd"]["sleeves"]["mon"]
    assert sl["pos"] == [] and sl["next"] == "2026-10-26" and st["equity"] == 300.0
    crb.poll(st, px, MS(MON) + 120_000, fund=NOFUND, **kw(syms, crowd))
    assert sl["pos"] and sl["next"] == "2026-11-02"


def test_a_failure_at_the_close_books_nothing_twice():
    st = account()
    syms, crowd, px, _, _ = market()
    crb.poll(st, px, MS(MON), fund=NOFUND, **kw(syms, crowd))
    eq, n = st["equity"], len(st["fin"]["crowd"]["sleeves"]["mon"]["pos"])
    nxt = MS(datetime(2026, 11, 2, 0, 2, tzinfo=timezone.utc))
    crb.poll(st, px, nxt, fund=lambda s, a, b: (_ for _ in ()).throw(ConnectionError("down")), **kw(syms, crowd))
    sl = st["fin"]["crowd"]["sleeves"]["mon"]
    assert st["equity"] == eq and len(sl["pos"]) == n and sl["next"] == "2026-11-02" and sl["weeks"] == 0


def test_the_dashboard_shows_the_legs_and_leaves_the_book_out_of_the_scorecard():
    st = account()
    syms, crowd, px, move, _ = market(seed=5)
    crb.poll(st, px, MS(MON), fund=NOFUND, **kw(syms, crowd))
    rows = [r for r in dp.open_positions(st, px) if r["book"] == "crowd"]
    assert len(rows) == len(st["fin"]["crowd"]["sleeves"]["mon"]["pos"]) and {r["side"] for r in rows} == {"long", "short"}
    d = Path(tempfile.mkdtemp())
    (d / "combo_state.json").write_text(json.dumps(dict(st, started="2026-10-17 01:15:28")))
    px1 = {s: px[s] * (1 + move[s]) for s in syms}
    a = dp.account("t", d, px1, MS(MON) // 1000, False, None)
    crowd_open = sum(r["upnl"] for r in dp.open_positions(st, px1) if r["book"] == "crowd")
    assert abs(a["books"]["crowd"]["open"] - round(crowd_open, 2)) < 0.006
    flat = dict(q=[-0.1, -0.02, 0.0, 0.02, 0.1], idle=0.0)
    bands = dict(levels=[0, 25, 50, 75, 100], lengths=[1, 30], span="x", made="y",
                 books={b: {"1": flat, "30": flat} for b in dp.SCORE_BOOKS}, total={"1": flat, "30": flat})
    old = datetime(2026, 10, 10, tzinfo=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    (d / "combo_state.json").write_text(json.dumps(dict(st, started=old)))
    a = dp.account("t", d, px1, MS(MON) // 1000, False, bands)
    ex = a["equity"] - (st["cum"]["crowd"] + crowd_open - st["cum"]["crowd_fees"])     # the account without the book
    assert a["score"]["ready"] and abs(a["score"]["total"]["usd"] - round(ex - 300.0, 2)) < 0.011
    main_like = account(crowd=False)                                          # no crowd: no bar
    (d / "combo_state.json").write_text(json.dumps(dict(main_like, started="2026-10-17 01:15:28")))
    assert "crowd" not in dp.account("t", d, px1, MS(MON) // 1000, False, None)["books"]


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(tests)} passed")

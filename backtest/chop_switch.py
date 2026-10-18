"""CAN THE TREND BOOK BLEED LESS IN SIDEWAYS MARKETS? - entry rules tested inside the 9-book machine (2026-10-18)

backtest/chop_gap.py (logs/chop_gap.txt): in sideways months the 9-book machine's typical month is -2.1%, and every book
except the trend book earns (the rest: +7.8% typical); the trend book's typical sideways month is -7.3%. So the gap is
the trend book. backtest/month_regime.py found a month-start BTC signal (btc_ma) that held on unseen 2017-19 months, but
it scaled each month's BOOKED returns - trades opened earlier too, which no bot can do (its own LIMIT note; CLAUDE.md
trap "weighting a series booked at close"). This file applies every rule AT ENTRY (dd_fixes.sim gate_fn), to the trend
book only, and puts the result back into the 9-book machine.

    G0  none - the deployed trend book (must reproduce final_machine.trend_capped(6.25) exactly: asserted)
    G1  month btc_ma OUT   no new trend trade in a month that started with BTC under its 42-day (1000h) mean
    G2  month btc_ma HALF  the same, half size
    G3  daily chop HALF    half size on days the BTC regime reads chop (doc 20 row 1, as a control - expected to fail)
    G4  ER HALF            BTC's 30-day efficiency ratio (|30-day move| / sum of daily moves, the day before) < 0.25:
                           half size - Kaufman's chop meter, never tried here
    G5  ER OUT             the same, no new trade
PASS (registered): the machine's typical 12 months on $300 >= G0 on BOTH halves (tune before 2024-08-29 / holdout), its
biggest fall no deeper than G0's on either half, and the typical sideways month better than G0's.
REGISTERED BEFORE THE RUN (2026-10-18)
    W1 G3 fails (doc 20: cutting the trend book in chop costs the turn into bull).
    W2 no gate passes.
    W3 every gate lifts the typical sideways month by at least +1 point (that part is what they aim at).

RESULT (logs/chop_switch.txt): no gate passes; W1 / W2 / W3 RIGHT. The month switch FLIPS between halves (G1 tune
$1,457 vs $3,927, holdout $13,315 vs $9,416) - month_regime.py's 2017-19 win was its booked-return attribution. G4 (ER
half) is the one trade-off worth a control: typical sideways month -2.1% -> +3.1%, fall 45/49% -> 39/43%, worst month 4
points better, for 12% / 8% of the typical year.

--control: IS G4 JUST BETTING SMALLER? The trend book at a constant 0.6 / 0.7 / 0.8 / 0.9x (every entry), the 9-book
machine around it; G4's typical year against the constant line's at G4's own fall, each half (linear between the two
nearest sizes).
REGISTERED BEFORE THE CONTROL RUN (2026-10-18)
    M1 G4 does NOT beat the bet-smaller line on both halves (its typical year at its fall is no better than the
       constant-size trend book's at the same fall).

CONTROL RESULT (logs/chop_switch.txt) - M1 RIGHT: G4 sits BELOW the bet-smaller line on both halves ($3,437 vs $3,719
tune, $8,628 vs $9,513 holdout at its own fall). The chop meter is betting smaller, done worse. What the control found
instead: the trend book at a constant 0.6-0.8x keeps the typical year and cuts the fall - read in trend_size.py.

    python -m backtest.chop_switch
    python -m backtest.chop_switch --control
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "chop_switch.txt"
CACHE = ROOT / "logs" / "chop_switch_trend.pkl"


def btc_signals():
    from backtest.market_neutral import btc_regime, load_panel
    C, _, _ = load_panel()
    b = C["BTCUSDT"].dropna()
    ma42 = b / b.rolling(42).mean() - 1
    month_ok = (ma42.resample("ME").last().shift(1) > 0)              # known at the month's first day
    month_ok.index = month_ok.index.to_period("M")
    er = (b - b.shift(30)).abs() / b.diff().abs().rolling(30).sum()
    er = er.shift(1)                                                   # the day before
    reg = btc_regime(C)
    return month_ok, er, reg, C


def gates(month_ok, er, reg):
    def day_of(t):
        return pd.Timestamp(t).normalize()

    def g_month(mult):
        return lambda r, t, ctx: 1.0 if bool(month_ok.get(pd.Timestamp(t).to_period("M"), True)) else mult

    def g_chop(mult):
        return lambda r, t, ctx: mult if reg.asof(day_of(t)) == "chop" else 1.0

    def g_er(mult):
        def f(r, t, ctx):
            v = er.asof(day_of(t))
            return mult if (v == v and v < 0.25) else 1.0
        return f
    return {"G0": None, "G1": g_month(0.0), "G2": g_month(0.5), "G3": g_chop(0.5), "G4": g_er(0.5), "G5": g_er(0.0)}


def trend_books(G: dict, cache_file: Path = CACHE) -> dict:
    """final_machine.trend_capped(6.25) with an entry gate: per gate, per seed, the daily return (gains shrunk)."""
    if cache_file.exists():
        return pickle.loads(cache_file.read_bytes())
    import backtest.dd_fixes as Dd
    from backtest import machine_combos as mc
    from backtest.bar_phase import rows_for_phase
    from backtest.bull_boost import regimes
    from backtest.worst_month import TCACHE
    cache = pickle.loads(TCACHE.read_bytes())
    bear = regimes()[1000]
    bn, bv = pd.DatetimeIndex(bear.index).as_unit("ns").asi8, bear.to_numpy(bool)
    trows = Dd.decompose(rows_for_phase(0, tight=True, time_stop=(100, 2.0), max_units=7))
    out = {}
    for name, gate in G.items():
        out[name] = {}
        for sd in mc.SEEDS:
            r = Dd.sim(trows, bn, bv, sd, lev=6.25, size_fn=Dd.anchor(21), gate_fn=gate).pct_change().fillna(0.0)
            s = cache[("shrink", sd)]
            out[name][sd] = pd.Series(np.where(r > 0, s * r, r), index=r.index)
        print(f"  {name} done", flush=True)
    cache_file.write_bytes(pickle.dumps(out))
    return out


def machine_daily(T_name: dict, M, nw, nd) -> list:
    from backtest import machine_combos as mc
    from backtest.chop_gap import BOOKS, NAMES
    out = []
    for sd, x in zip(mc.SEEDS, M):
        d = pd.DataFrame({nm: x[src] for src, nm in NAMES.items()})
        d["trend"] = T_name[sd].reindex(x.index).fillna(0.0)
        d["news"], d["ndx"] = nw.reindex(x.index).fillna(0.0), nd.reindex(x.index).fillna(0.0)
        out.append(d[BOOKS].sum(axis=1))
    return out


def control():
    """G4 against the trend book simply run smaller, at the same biggest fall, each half."""
    from backtest.all_books import machine_books, ndx_dip, news_book
    from backtest.machine import CUT, summary
    month_ok, er, reg, _ = btc_signals()
    G4 = {"G4": gates(month_ok, er, reg)["G4"], "G0": None}
    sizes = (0.6, 0.7, 0.8, 0.9)
    const = {f"x{k}": (lambda kk: (lambda r, t, ctx: kk))(k) for k in sizes}
    T = trend_books(gates(month_ok, er, reg))
    Tc = trend_books(const, ROOT / "logs" / "chop_switch_const.pkl")
    Tc.update({"x1.0": T["G0"], "G4": T["G4"]})
    M = machine_books()
    nw, nd = news_book(), ndx_dip()
    lines = ["", "CONTROL - is G4 just betting smaller? (the trend book at a constant size, the 9-book machine around it)",
             f"   {'line':<6}{'half':>8}{'typical':>9}{'fall':>6}{'worst mo':>9}"]
    S = {}
    for name in [f"x{k}" for k in sizes] + ["x1.0", "G4"]:
        daily = machine_daily(Tc[name], M, nw, nd)
        for half, s in (("tune", summary([x[x.index < CUT] for x in daily])), ("holdout", summary(daily, CUT))):
            S[(name, half)] = s
            lines.append(f"   {name:<6}{half:>8} ${s['typ']:>7,.0f}{s['dd']:>5.0f}%{s['wm']:>+8.1f}%")
    verdict = []
    for half in ("tune", "holdout"):
        pts = sorted(((S[(f'x{k}', half)]['dd'], S[(f'x{k}', half)]['typ']) for k in list(sizes) + [1.0]))
        dd4, typ4 = S[("G4", half)]["dd"], S[("G4", half)]["typ"]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        line = float(np.interp(dd4, xs, ys))
        verdict.append(typ4 > line)
        lines.append(f"   {half}: G4 ${typ4:,.0f} at a {dd4:.0f}% fall | the constant-size line at that fall ${line:,.0f} -> "
                     f"G4 {'ABOVE' if typ4 > line else 'below'} the bet-smaller line")
    lines += ["", f"  M1 G4 does not beat the bet-smaller line on both halves -> {'RIGHT' if not all(verdict) else 'WRONG'}"]
    txt = "\n".join(lines)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(txt + "\n")
    print(txt)


def main():
    from backtest import final_machine as fm
    from backtest import machine_combos as mc
    from backtest.all_books import machine_books, ndx_dip, news_book
    from backtest.chop_gap import BOOKS, NAMES, month_labels, monthly
    from backtest.machine import CUT, summary
    month_ok, er, reg, _ = btc_signals()
    T = trend_books(gates(month_ok, er, reg))
    ref = fm.trend_capped(6.25)
    for sd in mc.SEEDS:                                    # G0 must BE the deployed trend book
        a, b = T["G0"][sd], ref[sd].reindex(T["G0"][sd].index).fillna(0.0)
        assert np.allclose(a.to_numpy(), b.to_numpy(), atol=1e-12), f"G0 does not reproduce trend_capped, seed {sd}"
    M = machine_books()
    nw, nd = news_book(), ndx_dip()
    lab = month_labels(reg)
    lines = [f"backtest/chop_switch.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; the 9-book machine with the "
             f"trend book's ENTRIES gated; $300, 12 months, 10 orderings; trend gains shrunk, the rest raw",
             "   G0 reproduces final_machine.trend_capped(6.25) on all 10 orderings (asserted)", "",
             f"   share of days each gate acts on: month btc_ma OUT {1 - month_ok.mean():.0%} of months | chop "
             f"{(reg == 'chop').mean():.0%} of days | ER < 0.25 {(er < 0.25).mean():.0%} of days", "",
             f"   {'gate':<5}{'half':>8}{'typical':>9}{'bad':>7}{'worst':>7}{'worst mo':>9}{'fall':>6}{'up':>5}"
             f"{'chop typ':>10}{'bull typ':>10}{'bear typ':>10}"]
    R = {}
    for name in T:
        daily, parts = [], []
        for k, (sd, x) in enumerate(zip(mc.SEEDS, M)):
            d = pd.DataFrame({nm: x[src] for src, nm in NAMES.items()})
            d["trend"] = T[name][sd].reindex(x.index).fillna(0.0)
            d["news"], d["ndx"] = nw.reindex(x.index).fillna(0.0), nd.reindex(x.index).fillna(0.0)
            daily.append(d[BOOKS].sum(axis=1))
            m = monthly(d).iloc[1:-1]
            m["reg"] = lab.reindex(m.index).to_numpy()
            parts.append(m)
        P = pd.concat(parts).dropna(subset=["reg"])
        typ = {g: P[P.reg == g].account.median() for g in ("chop", "bull", "bear")}
        for half, s in (("tune", summary([x[x.index < CUT] for x in daily])), ("holdout", summary(daily, CUT))):
            R[(name, half)] = (s, typ)
            lines.append(f"   {name:<5}{half:>8} ${s['typ']:>7,.0f} ${s['bad']:>5,.0f} ${s['worst']:>5,.0f}{s['wm']:>+8.1f}%"
                         f"{s['dd']:>5.0f}%{s['up']:>4.0f}%{typ['chop'] * 100:>+9.1f}%{typ['bull'] * 100:>+9.1f}%"
                         f"{typ['bear'] * 100:>+9.1f}%")
    passed = []
    for name in T:
        if name == "G0":
            continue
        ok = all(R[(name, h)][0]["typ"] >= R[("G0", h)][0]["typ"] and R[(name, h)][0]["dd"] <= R[("G0", h)][0]["dd"]
                 for h in ("tune", "holdout")) and R[(name, "tune")][1]["chop"] > R[("G0", "tune")][1]["chop"]
        if ok:
            passed.append(name)
    lift = {n: (R[(n, "tune")][1]["chop"] - R[("G0", "tune")][1]["chop"]) * 100 for n in T if n != "G0"}
    g3 = "G3" not in passed
    lines += ["", f"   PASSED: {', '.join(passed) if passed else 'none'}", "", "REGISTERED PREDICTIONS",
              f"  W1 G3 fails -> {'RIGHT' if g3 else 'WRONG'}",
              f"  W2 no gate passes -> {'RIGHT' if not passed else 'WRONG'} ({', '.join(passed) or 'none'})",
              f"  W3 every gate lifts the typical sideways month >= +1 point: "
              + ", ".join(f"{n} {v:+.1f}" for n, v in lift.items())
              + f" -> {'RIGHT' if all(v >= 1 for v in lift.values()) else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    control() if "--control" in sys.argv else main()

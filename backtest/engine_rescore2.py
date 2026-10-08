"""PHASE 2 (the thin kills): the ENGINE kills that were never re-scored on the corrected engine (2026-10-08).

CLAUDE.md rule 9 allows a kill to be reopened when its MEASUREMENT was broken. Three engine bugs were fixed on 2026-09-23
(funding never charged, bar-label entry times, sequential compounding) and graveyard_rescore.py re-scored the exits,
sleeves, trails, slots, risk and entry band that died on the old engine - but not these, all measured on the old engine
(their baselines read "+19.29%/mo" or "+13.17%/mo holdout", the pre-fix numbers):
    pyramid_exits.py (2026-09-20)   scale_out (each ADDED unit gets its own 5xATR trail, never re-bought), avg_be
                                    (breakeven at the AVERAGE entry), ratchet (20 -> 10xATR past +10R)
    final_variants.py (2026-09-23)  stop 1.5x / 3x ATR (1x and 4x were unusable either way), an entry LIMIT 0.25x / 1x
                                    ATR under the signal close (live 5 bars)
    book_structure.py (2026-09-23)  bb(20, 2.0) and bb(50, 1.5) entries; risk x1.5 / x1.0 / x0.5 by sleeve 1h / 4h / 12h
The funding fix is not neutral between these: scale_out and the ratchet SHORTEN holds and were denied the funding they
save, the limit entry and a wider stop lengthen them. (Per-coin caps and slot rules were re-run on the causal allocator
in slot_ideas.py; correlation clusters died for allocator-free reasons.)

ENGINE: graveyard_rescore.walk copied with four options added (stop width, breakeven at the average entry, scale_out,
pullback limit); with the options off it is asserted to reproduce graveyard_rescore.walk row for row. A scaled-out unit
is still charged funding to the position's close - a bias AGAINST scale_out, stated. Scoring is graveyard_rescore.score:
real entry times, funding, entry-sized compounding, 12 slots, 1000h gate, 10 orderings PAIRED with the base; the bar
is BOTH halves by more than 2 paired standard errors. Two bases: MAIN (deployed rules, as graveyard_rescore) and the
TRIPLE (tight + time stop + 7 units - the book v2 runs), each variant applied on top of it.

REGISTERED BEFORE RUNNING: none clears the bar against the TRIPLE (its tight exit and time stop already protect gains).
Against MAIN: scale_out and the ratchet improve the worst month but cost return on at least one half; avg_be fails;
stop 1.5x is "tune only", 3x loses both; the limit entries lose both (they miss the runners); bb(20,2) / bb(50,1.5)
lose; risk-by-sleeve is tune-only. At most 1 of 10 clears the bar on either base.

RESULT (2026-10-08, logs/engine_rescore2.txt): on the corrected engine every one of these kills STANDS but one, on both
    bases. MAIN (+4.88 / +4.88 %/mo): scale_out -3.56 / -0.34, avg_be -1.95 / -0.74, ratchet -1.78 / -1.22, stop 1.5x
    -0.74 / -2.43, stop 3x -1.77 / -2.80, limit 0.25x -1.24 / -0.78, limit 1x tune only, bb(20,2) and bb(50,1.5) lose
    the holdout. TRIPLE (+8.89 / +10.76): all lose at least one half. The exception: risk x1.5 / x1.0 / x0.5 by sleeve
    clears the bar on both (+0.47 / +0.98 main, +0.75 / +2.27 triple) - with deeper falls; sleeve_risk_control.py
    then shows it is holdout-only at matched risk. Predictions: none clears against the triple - WRONG in form (one
    did, before the control), right after it; scale_out / ratchet better worst month but cost return - right; the
    rest - right.

    python -m backtest.engine_rescore2
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import blend  # noqa: E402
from backtest import graveyard_rescore as G  # noqa: E402
from backtest.bear_side import sleeve_sided  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.causal_t0 import real_t0  # noqa: E402
from backtest.engine_variants import break_map, shorts_for  # noqa: E402
from backtest.funding_cost import charged, long_funding, short_funding  # noqa: E402
from backtest.pyramid import FEE_BP  # noqa: E402
from backtest.shortside import signals  # noqa: E402
from backtest.timeframes import resample  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402

LOG = ROOT / "logs" / "engine_rescore2.txt"
_C: dict = {}


def walk2(df, rule, coin, trail=None, tb=None, time_stop=None, hi_thresh=None, hi_mult=1.0, atr_n=14,
          add_every=None, max_units=None, be_at=None, sl_mult=None, be_avg=False, scale_out=False, pull=None,
          pull_expire=5):
    ae = blend.ADD_EVERY if add_every is None else add_every
    mu = blend.MAX_UNITS if max_units is None else max_units
    ba = blend.BE_AT if be_at is None else be_at
    slm = blend.SL_MULT if sl_mult is None else sl_mult
    s = signals(df, "long", "all").to_numpy()
    o = df["open"].to_numpy(float); h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float); c = df["close"].to_numpy(float)
    a = atr_ind(df, atr_n).to_numpy(float)
    t = df["time"].to_numpy()
    fee = FEE_BP / 1e4
    wide = blend.LONG_TRAIL if trail is None else trail
    out, pos, pend = [], None, None

    def close(px, i):
        R = (sum(px - e for e in pos["ents"]) - sum(fee * e for e in pos["ents"]) + pos["banked"]) / pos["risk"]
        out.append(dict(t0=t[pos["bar"]], t1=t[i], R=float(R), side="long", sf=pos["risk"] / pos["e0"],
                        adds=list(pos["addt"]), coin=coin, rule=rule))

    def open_pos(px, i, atr):
        r = slm * atr
        return dict(risk=r, stop=px - r, best=px, bar=i, ents=[px], e0=px, nxt=1, tight=False, addt=[t[i]],
                    barmed=(tb is None or not tb[i]), banked=0.0, ever=1, ust=[None])

    for i in range(1, len(df)):
        if pos is None and pend is None and s[i] == 1 and np.isfinite(a[i - 1]) and a[i - 1] > 0:
            if pull is None:
                pos = open_pos(o[i], i, a[i - 1])
            else:
                pend = dict(lim=c[i - 1] - pull * a[i - 1], until=i + pull_expire - 1, atr=a[i - 1])
        if pos is None and pend is not None:
            if lo[i] <= pend["lim"]:
                pos = open_pos(min(o[i], pend["lim"]), i, pend["atr"])
                pend = None
            else:
                if i >= pend["until"]:
                    pend = None
                continue
        if pos is None:
            continue
        r = pos["risk"]; e0 = pos["e0"]
        if tb is not None and i > pos["bar"]:
            if not tb[i]:
                pos["barmed"] = True
            elif pos["barmed"]:
                pos["tight"] = True
        if lo[i] <= pos["stop"]:
            close(pos["stop"], i); pos = None; continue
        if scale_out:                                       # an added unit hit its own trail: bank it, never re-buy
            keep_e, keep_s = [pos["ents"][0]], [None]
            for e, us in zip(pos["ents"][1:], pos["ust"][1:]):
                if us is not None and lo[i] <= us:
                    pos["banked"] += us - e - fee * e
                else:
                    keep_e.append(e); keep_s.append(us)
            pos["ents"], pos["ust"] = keep_e, keep_s
        if time_stop and i - pos["bar"] >= time_stop[0] and (c[i] - e0) / r < time_stop[1]:
            close(c[i], i); pos = None; continue
        if pos["ever"] < mu and (h[i] - e0) / r >= pos["nxt"] * ae:
            pos["ents"].append(e0 + pos["nxt"] * ae * r); pos["ust"].append(None); pos["nxt"] += 1
            pos["ever"] += 1
            pos["addt"].append(t[i])
        pos["best"] = max(pos["best"], h[i])
        m = 5.0 if pos["tight"] else wide
        if hi_thresh is not None and (pos["best"] - e0) / r >= hi_thresh:
            m = m * hi_mult
        cand = pos["best"] - m * a[i - 1]
        if (pos["best"] - e0) / r >= ba:
            cand = max(cand, float(np.mean(pos["ents"])) if be_avg else e0)
        if cand > pos["stop"]:
            pos["stop"] = cand
        if scale_out:
            u = pos["best"] - 5.0 * a[i - 1]
            pos["ust"] = [None] + [max(x, u) if x is not None else u for x in pos["ust"][1:]]
    if pos is not None:
        close(c[-1], len(df) - 1)
    return out


def rows2(rules=("1h", "4h", "12h"), tight=False, **kw):
    key = (tuple(rules), tight, tuple(sorted(kw.items())))
    if key in _C:
        return _C[key]
    out = []
    for rule in rules:
        out += shorts_for(rule)
        for coin in blend.BOOK:
            d = blend.load(coin)
            if d is None:
                continue
            df = resample(d, rule)
            if len(df) < 300:
                continue
            out += walk2(df, rule, coin, tb=break_map(df, rule) if tight else None, **kw)
    out = charged(real_t0(short_funding(long_funding(out))))
    _C[key] = out
    return out


def check():
    """walk2 with every new option off == graveyard_rescore.walk, row for row (and on the triple's options)."""
    for coin, rule in (("XRPUSDT", "1h"), ("LINKUSDT", "4h"), ("ADAUSDT", "12h")):
        df = resample(blend.load(coin), rule)
        for kw in (dict(), dict(tb=break_map(df, rule), time_stop=(100, 2.0), max_units=7)):
            a, b = G.walk(df, rule, coin, **kw), walk2(df, rule, coin, **kw)
            assert len(a) == len(b) > 0 and all(x["t0"] == y["t0"] and x["t1"] == y["t1"] and abs(x["R"] - y["R"]) < 1e-9
                                                for x, y in zip(a, b)), (coin, rule, kw.keys())
    return "walk2 reproduces graveyard_rescore.walk on 3 coin/sleeves, plain and triple"


def main():
    bear = regimes()[1000]
    ts = pd.DatetimeIndex(sorted(x[0] for x in sleeve_sided("1h")[0]))
    cut = ts[int(len(ts) * 0.6)]
    lines = [f"backtest/engine_rescore2.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; corrected engine, 10 paired orderings, "
             f"tune < {cut:%Y-%m-%d} <= holdout; %/mo is CAGR/3, DD and worst month raw", check(), ""]
    print(lines[1], flush=True)
    TRI = dict(tight=True, time_stop=(100, 2.0), max_units=7)
    V = {"scale_out (added units trail 5xATR)": dict(scale_out=True), "avg_be (breakeven at the average entry)": dict(be_avg=True),
         "ratchet 20 -> 10xATR past +10R": dict(hi_thresh=10.0, hi_mult=0.5), "stop 1.5xATR": dict(sl_mult=1.5),
         "stop 3xATR": dict(sl_mult=3.0), "entry limit 0.25xATR under": dict(pull=0.25), "entry limit 1xATR under": dict(pull=1.0)}
    SLEEVE_W = {"1h": 1.5, "4h": 1.0, "12h": 0.5}
    for bname, bkw in (("MAIN", {}), ("TRIPLE", TRI)):
        B = G.score(rows2(**bkw), bear, cut)
        lines.append(f"BASE {bname}: tune {B['tune'][:, 0].mean():+.2f}%/mo DD {B['tune'][:, 1].mean():.0f}% | holdout "
                     f"{B['hold'][:, 0].mean():+.2f}%/mo DD {B['hold'][:, 1].mean():.0f}% worst month {B['hold'][:, 2].mean():+.1f}%")
        print(lines[-1], flush=True)

        def show(lab, R):
            dt = R["tune"][:, 0] - B["tune"][:, 0]; dh = R["hold"][:, 0] - B["hold"][:, 0]
            st, sh = dt.std(ddof=1) / np.sqrt(len(dt)), dh.std(ddof=1) / np.sqrt(len(dh))
            both = dt.mean() > 2 * st and dh.mean() > 2 * sh
            v = "CLEARS THE BAR" if both else ("holdout only" if dh.mean() > 2 * sh else ("tune only" if dt.mean() > 2 * st else "-"))
            lines.append(f"  {bname:6} + {lab:40} tune {R['tune'][:, 0].mean():+6.2f}% DD {R['tune'][:, 1].mean():3.0f}% | hold "
                         f"{R['hold'][:, 0].mean():+6.2f}% DD {R['hold'][:, 1].mean():3.0f}% wm {R['hold'][:, 2].mean():+5.1f}% | "
                         f"d {dt.mean():+.2f}+-{st:.2f} / {dh.mean():+.2f}+-{sh:.2f} -> {v}")
            print(lines[-1], flush=True)

        for lab, kw in V.items():
            show(lab, G.score(rows2(**{**bkw, **kw}), bear, cut))
        show("risk x1.5 / x1.0 / x0.5 by sleeve 1h/4h/12h",
             G.score([dict(r, R=r["R"] * SLEEVE_W.get(r["rule"], 1.0)) for r in rows2(**bkw)], bear, cut))
        import backtest.bear_side as BS
        import backtest.engine_variants as EV
        import backtest.funding_cost as FC
        import backtest.shortside as SS
        for p_, k_ in ((20, 2.0), (50, 1.5)):
            SS.BB_P, SS.BB_STD = p_, k_
            EV._CACHE.clear(); BS._S.clear(); FC._SH.clear(); _C.clear()
            show(f"entry bb({p_}, {k_})", G.score(rows2(**bkw), bear, cut))
        SS.BB_P, SS.BB_STD = 30, 1.5
        EV._CACHE.clear(); BS._S.clear(); FC._SH.clear(); _C.clear()
        lines.append("")
        LOG.write_text("\n".join(lines) + "\n")
    LOG.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

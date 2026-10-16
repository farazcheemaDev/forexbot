"""DATA SURPRISES AT MINUTE RESOLUTION, 2007-2026 (HistData.com) - is there a tradable move in the first minutes after
the jump? (2026-10-12)

fx_surprises.py measured the reaction on daily noon fixes (blurred by a day's other news) and at minute resolution only
for 2026 (23 US releases on Exness). Free minute bars for every day since 2007 (backtest/histdata_1m.py - HistData.com;
Dukascopy, tried first in backtest/dukascopy_1m.py, throttled after a few hundred days) let the minutes right after each
number be measured over 19 years. A CLOCK CHECK runs first: on the US payroll days the biggest 1-minute move must sit in
the release minute (HistData stamps fixed EST; a wrong offset would show here, not in the results).

EVENTS   fx_surprises.events(): high-impact releases with a forecast, one SCORE per currency and minute (|score| >= 1)
PRICES   HistData BID minute bars; the dollar = the average of -EURUSD, -GBPUSD, +USDJPY; other currencies their own pair
WINDOWS  (minutes from the release minute; the price is the open of that minute's bar, or the last price before it)
         JUMP     -1 -> +5     the reaction (not tradable: the number is not known before it prints)
         FAST     +1 -> +15    entered one minute after the number - the earliest a person or a simple bot acts
         HOUR     +5 -> +65
         HALF DAY +5 -> +245
COSTS    the spread right after a release is wide: it is MEASURED on Exness's 2026 ticks (backtest/mt5_1m.py) at the
         entry minute of each window, for the US releases of 2026, and applied to every year (an assumption - spreads
         were wider before ~2015, so early years are flattered); half of it at entry, half of the normal spread at exit
PASS     net > 0 with t >= 2 on both halves (60/40 by date).

REGISTERED BEFORE THE RUN (2026-10-12)
    M1  JUMP has the surprise's sign in >= 65% of releases with |score| >= 1 and >= 70% with |score| >= 2.
    M2  HOUR and HALF DAY are within 2 se of zero (all releases, and USD alone).
    M3  FAST continues the surprise's direction (gross t > 2) - news momentum in the first minutes - but net of the
        post-release spread it does not pass on both halves.
    M4  No window passes.

RESULT (2026-10-12 08:45 UTC, logs/fx_surprises_1m.txt; 2,078 releases 2007-08 .. 2026-09, holdout from 2016-08)
    THE FIRST RUN WAS WRONG - A CLOCK BUG, CAUGHT BY THE CLOCK CHECK: HistData's stamps are New York time WITH daylight
    saving (it documents fixed EST). Converted with a fixed +5 h, every summer release sat an hour early, its jump fell
    into the +5 -> +65 window, and the run showed a "post-release drift" of +10.5bp at t +21 with 9 "passes"; the check
    had the payroll jump at minute 0 on only 51 of 209 days. Fixed in histdata_1m.parse; now 132 of 210 at minute 0 and
    the rest within 3 minutes.
    - M1 RIGHT: within 5 minutes the currency moves the surprise's way 81.1% of the time, +14.2bp (non-USD 83.6%, +17.7bp;
      USD 77.7%, +9.3bp).
    - M3 RIGHT: one minute after the number there is a little left - +0.79bp gross (t +2.8) to +15 minutes - and the
      spread (0.69bp, measured on Exness's 2026 releases) takes all but +0.10bp.
    - M2 WRONG the other way: after the first minutes nothing continues - the next hour -0.12bp (t -0.3) - and over half a
      day non-USD releases give back -3.1bp (t -3.0): a mild reversal, not a drift.
    - M4 RIGHT: no window passes. The closest is the biggest US surprises (|score| >= 2, 250 releases): +2.05bp net at +1
      -> +15 minutes, tune +1.25 (t +1.0) / holdout +2.68 (t +2.4) - one half, about 13 trades a year: ~0.3% a year.
    Reading: the number is in the price within five minutes, four times in five the right way; there is no drift
    afterwards to collect at retail speed.

    python -m backtest.fx_surprises_1m          (needs backtest/histdata_1m.py's cache)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import histdata_1m as dk  # noqa: E402
from backtest import mt5_1m  # noqa: E402
from backtest.fx_surprises import events  # noqa: E402

LOG = ROOT / "logs" / "fx_surprises_1m.txt"
MIN = 60_000
TUNE = 0.60
SIDE = {"EURUSD": 1, "GBPUSD": 1, "AUDUSD": 1, "NZDUSD": 1, "USDJPY": -1, "USDCAD": -1, "USDCHF": -1}   # +1: the foreign ccy is the base
WIN = {"JUMP": (-1, 5), "FAST": (1, 15), "HOUR": (5, 65), "HALF DAY": (5, 245)}


def px_at(t_arr, o_arr, c_arr, t):
    """price at time t: the open of the bar starting at t, else the close of the last bar before t."""
    i = np.searchsorted(t_arr, t)
    if i < len(t_arr) and t_arr[i] == t:
        return o_arr[i]
    if i == 0:
        return np.nan
    if t - t_arr[i - 1] > 30 * MIN:                               # stale - no price in the last 30 minutes
        return np.nan
    return c_arr[i - 1]


def news_spreads():
    """median Exness spread (bp) at minute +1 / +5 after 2026's US releases, and at ordinary minutes."""
    E = events()
    E = E[(E.currency == "USD") & (E.utc >= "2026-01-01")]
    out = {}
    for sym in ("EURUSDm", "GBPUSDm", "USDJPYm"):
        b = mt5_1m.load(sym).set_index("t")
        rel = (b.sp_o / b.c) * 1e4
        for m in (1, 5):
            v = [rel.get(int(pd.Timestamp(u).timestamp() * 1000) // MIN * MIN + m * MIN, np.nan) for u in E.utc]
            out.setdefault(m, []).append(np.nanmedian(v))
        out.setdefault("normal", []).append(rel.median())
    return {k: float(np.mean(v)) for k, v in out.items()}


def main():
    sp = news_spreads()
    cost = {"JUMP": np.nan, "FAST": sp[1] / 2 + sp["normal"] / 2, "HOUR": sp[5] / 2 + sp["normal"] / 2,
            "HALF DAY": sp[5] / 2 + sp["normal"] / 2}
    bars = {}
    for p in SIDE:
        try:
            d = dk.load(p)
            bars[p] = (d.t.to_numpy(np.int64), d.o.to_numpy(), d.c.to_numpy())
        except FileNotFoundError:
            pass
    E = events()
    # CLOCK CHECK: where, relative to the stamped release minute, is the biggest 1-minute move on payroll days?
    nfp = E[(E.currency == "USD") & E.names.str.contains("Non-Farm Employment Change") & ~E.names.str.contains("ADP")]
    offs = []
    ta, oa, ca = bars["EURUSD"]
    for u in nfp.utc:
        t0 = int(pd.Timestamp(u).timestamp() * 1000) // MIN * MIN
        i0, i1 = np.searchsorted(ta, t0 - 30 * MIN), np.searchsorted(ta, t0 + 30 * MIN)
        if i1 - i0 < 40:
            continue
        r = np.abs(np.diff(ca[i0:i1]))
        offs.append(int((ta[i0 + 1 + int(np.argmax(r))] - t0) // MIN))
    clock = pd.Series(offs).value_counts().head(4).to_dict() if offs else {}
    E = E[E.score.abs() >= 1]
    rows = []
    for r in E.itertuples():
        t0 = int(pd.Timestamp(r.utc).timestamp() * 1000) // MIN * MIN
        pairs = ["EURUSD", "GBPUSD", "USDJPY"] if r.currency == "USD" else [dict(EUR="EURUSD", GBP="GBPUSD", JPY="USDJPY",
                                                                             AUD="AUDUSD", NZD="NZDUSD", CAD="USDCAD", CHF="USDCHF")[r.currency]]
        if not all(p in bars for p in pairs):
            continue
        rec = dict(utc=r.utc, ccy=r.currency, score=r.score)
        ok = True
        for w, (a, b) in WIN.items():
            mv = []
            for p in pairs:
                ta, oa, ca = bars[p]
                pa, pb = px_at(ta, oa, ca, t0 + a * MIN), px_at(ta, oa, ca, t0 + b * MIN)
                if not (np.isfinite(pa) and np.isfinite(pb)):
                    ok = False
                    break
                s = SIDE[p] * (1 if r.currency != "USD" else -1)       # the move of the currency that released
                mv.append(s * (pb / pa - 1))
            if not ok:
                break
            rec[w] = float(np.mean(mv))
        if ok:
            rows.append(rec)
    D = pd.DataFrame(rows).sort_values("utc", kind="stable").reset_index(drop=True)
    cut = D.utc.iloc[int(len(D) * TUNE)]
    lines = [f"backtest/fx_surprises_1m.py, {pd.Timestamp.now(tz="UTC"):%Y-%m-%d %H:%M} UTC; HistData minute bars; {len(D)} releases "
             f"(|score| >= 1) {D.utc.min():%Y-%m} .. {D.utc.max():%Y-%m}; holdout from {cut:%Y-%m-%d}",
             f"Exness spread after 2026's US releases (median, bp): at +1 min {sp[1]:.2f}, at +5 min {sp[5]:.2f}, ordinary "
             f"{sp['normal']:.2f} -> cost a trade FAST {cost['FAST']:.2f}bp, HOUR / HALF DAY {cost['HOUR']:.2f}bp",
             f"CLOCK CHECK - minute of the biggest 1-min EURUSD move on {len(offs)} payroll days, relative to the release "
             f"(0 = the release minute): {clock}", ""]
    tt = lambda y: y.mean() / (y.std(ddof=1) / np.sqrt(len(y))) if len(y) > 2 and y.std(ddof=1) > 0 else np.nan  # noqa: E731
    res = {}
    for nm, m in (("all, |score| >= 1", D.score.abs() >= 1), ("USD, |score| >= 1", (D.ccy == "USD")),
                  ("others, |score| >= 1", D.ccy != "USD"), ("all, |score| >= 2", D.score.abs() >= 2),
                  ("USD, |score| >= 2", (D.ccy == "USD") & (D.score.abs() >= 2))):
        g = D[m]
        s = np.sign(g.score)
        line = f"  {nm:22} n {len(g):5} | JUMP right {(np.sign(g['JUMP']) == s).mean() * 100:4.1f}% {(s * g['JUMP']).mean() * 1e4:+5.1f}bp"
        res[(nm, "JUMP")] = (np.sign(g["JUMP"]) == s).mean()
        for w in ("FAST", "HOUR", "HALF DAY"):
            gross = s * g[w]
            net = gross - cost[w] / 1e4
            tu, ho = net[g.utc < cut], net[g.utc >= cut]
            res[(nm, w)] = dict(gross=gross.mean(), gt=tt(gross), net=net.mean(), tu=tu.mean(), t_tu=tt(tu), ho=ho.mean(), t_ho=tt(ho))
            line += f" | {w} gross {gross.mean() * 1e4:+5.2f} (t {tt(gross):+.1f}) net {net.mean() * 1e4:+5.2f}"
        lines.append(line)
    lines.append("")
    lines.append("NET BY HALF (bp a trade, t): tune / holdout")
    for (nm, w), v in res.items():
        if w == "JUMP":
            continue
        lines.append(f"  {nm:22} {w:8}: {v['tu'] * 1e4:+6.2f} ({v['t_tu']:+.1f}) / {v['ho'] * 1e4:+6.2f} ({v['t_ho']:+.1f})")
    passes = [k for k, v in res.items() if k[1] != "JUMP" and v["tu"] > 0 and v["ho"] > 0 and v["t_tu"] >= 2 and v["t_ho"] >= 2]
    lines.append(f"  PASS: {passes or 'none'}")
    lines.append("")
    lines.append("REGISTERED PREDICTIONS")
    j1, j2 = res[("all, |score| >= 1", "JUMP")], res[("all, |score| >= 2", "JUMP")]
    lines.append(f"  M1 JUMP right {j1 * 100:.1f}% (|score|>=1), {j2 * 100:.1f}% (>=2) -> {'RIGHT' if j1 >= 0.65 and j2 >= 0.70 else 'WRONG'}")
    m2 = all(abs(res[(nm, w)]["gt"]) < 2 for nm in ("all, |score| >= 1", "USD, |score| >= 1") for w in ("HOUR", "HALF DAY"))
    lines.append(f"  M2 HOUR / HALF DAY gross t: " + ", ".join(f"{nm.split(',')[0]} {w} {res[(nm, w)]['gt']:+.1f}"
                                                             for nm in ("all, |score| >= 1", "USD, |score| >= 1") for w in ("HOUR", "HALF DAY"))
                 + f" -> {'RIGHT' if m2 else 'WRONG'}")
    f_ = res[("all, |score| >= 1", "FAST")]
    m3 = f_["gt"] > 2 and not any(k[1] == "FAST" for k in passes)
    lines.append(f"  M3 FAST gross {f_['gross'] * 1e4:+.2f}bp (t {f_['gt']:+.1f}), net {f_['net'] * 1e4:+.2f}bp; FAST passes "
                 f"{[k for k in passes if k[1] == 'FAST'] or 'none'} -> {'RIGHT' if m3 else 'WRONG'}")
    lines.append(f"  M4 passes: {passes or 'none'} -> {'RIGHT' if not passes else 'WRONG'}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

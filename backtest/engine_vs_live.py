"""THE ENGINE AGAINST THE LIVE PAPER BOOKS - trade by trade, on the same Binance candles.

The user, 2026-10-05: "our engine had some issues... check the engine again". The strongest check available: the seven
paper books on the VM (blend_paper.py, polling Binance's 1h klines every 120 s since 2026-09-14) have closed ~50
trades each. The backtest engine every result since 2026-09-23 rests on (graveyard_rescore.walk / rows: causal
entries, funding, entry-sized compounding) is run over the SAME weeks on the SAME candles (blend.load = Binance spot
1h klines), and each live trade is matched to the engine trade on the same coin, sleeve and side that closed in the
same bar. Any difference in which trades exist, their entry / exit prices, unit counts or R is a bug in the engine or
in the live bot - and either matters.
  main    = the deployed rules (no tight exit, no time stop, 5 units)  vs  logs/trades_blend.csv
  triple  = tight exit + time stop (100 bars, 2R) + 7 units             vs  logs/trades_blend_triple.csv
The live logs live on the VM; pass the folder holding copies:  python -m backtest.engine_vs_live <folder>
The live R does not charge funding (blend_paper.py's paper books do not), so engine R is compared BEFORE funding.

REGISTERED PREDICTION (2026-10-05, before running): >= 90% of live trades match an engine trade; matched entries and
exits agree within ~10bp (the live bot fills at its 2-minute poll, the engine at the bar open / the exact stop); unit
counts agree on >= 90%; the engine's R is slightly BETTER than live on average (+0.05 to +0.2R a trade: exact-level
adds and stops, against fills up to 2 minutes late).

    python -m backtest.engine_vs_live <folder with trades_blend*.csv>
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import blend  # noqa: E402
from backtest.engine_variants import break_map, shorts_for  # noqa: E402
from backtest.graveyard_rescore import walk  # noqa: E402
from backtest.timeframes import resample  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FEE = 12 / 1e4          # backtest.pyramid.FEE_BP, round trip, charged on each unit's entry
DUR = {"1h": pd.Timedelta(hours=1), "4h": pd.Timedelta(hours=4), "12h": pd.Timedelta(hours=12)}


def extend_cache():
    """blend.fetch's disk cache stops at 2026-09-11 16:00 (written once, never refreshed), before the live books
    started. Append the missing hours from Binance IN MEMORY only (blend._D), so the cache file and every result
    computed from it stay reproducible."""
    import json
    import urllib.request
    now = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    for sym in list(blend.BOOK) + ["BTCUSDT"]:
        d = blend.load(sym)
        if d is None:
            continue
        cur, rows = int(d.time.max().value // 10**6) + 3600_000, []
        while cur < now:
            u = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1h&startTime={cur}&limit=1000"
            r = json.load(urllib.request.urlopen(u, timeout=25))
            if not r:
                break
            rows += r
            cur = r[-1][0] + 3600_000
        n = pd.DataFrame([{"time": pd.Timestamp(k[0], unit="ms"), "open": float(k[1]), "high": float(k[2]),
                           "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])} for k in rows])
        n = n[n.time + pd.Timedelta(hours=1) <= pd.Timestamp(now, unit="ms")]          # closed bars only
        blend._D[sym] = pd.concat([d, n]).drop_duplicates("time").sort_values("time").reset_index(drop=True)


def engine(tight, **kw):
    out = []
    for rule in ("1h", "4h", "12h"):
        for r in shorts_for(rule):
            out.append(r | {"rule": rule})
        for coin in blend.BOOK:
            d = blend.load(coin)
            if d is None:
                continue
            df = resample(d, rule)
            tb = break_map(df, rule) if tight else None
            out += walk(df, rule, coin, tb=tb, **kw)
    E = pd.DataFrame(out)
    E["t0"], E["t1"] = pd.to_datetime(E.t0), pd.to_datetime(E.t1)
    return E


def entry_px(E):
    """the engine enters at the OPEN of bar t0 (graveyard_rescore.walk; shorts likewise)"""
    px = []
    for r in E.itertuples():
        df = resample(blend._D[r.coin], r.rule).set_index("time")
        px.append(float(df.open.get(r.t0, np.nan)))
    return np.array(px)


def match(L, E):
    """by ENTRY: same coin, sleeve and side, the engine entry within 48 h of the live one (estimated as its close time
    minus `bars` bars - which proved loose by up to a day on long holds), and the closest ENTRY PRICE within 1%"""
    rows, used = [], set()
    for i, r in L.iterrows():
        dur = DUR[r.sleeve]
        t_in = r.ts - r.bars * dur
        cand = E[(E.coin == r.symbol) & (E.rule == r.sleeve) & (E.side == r.side) &
                 ((E.t0 - t_in).abs() <= pd.Timedelta(hours=48)) & ((E.px / r.entry - 1).abs() <= 0.01)]
        cand = cand[[j not in used for j in cand.index]]
        if len(cand):
            j = (cand.px / r.entry - 1).abs().idxmin()
            used.add(j)
            e = E.loc[j]
            n = len(e.adds)
            risk = e.sf * e.px
            if r.side == "long":       # invert walk(): R = (sum(x - e_k) - fee * sum(e_k)) / risk, e_k = e0 + 2k R
                ents = [e.px + k * 2.0 * risk for k in range(n)]
                x_eng = (e.R * risk + (1 + FEE) * sum(ents)) / n
            else:
                x_eng = np.nan
            rows.append(dict(i=i, j=j, R_live=r.R, R_eng=e.R, units_live=r.units, units_eng=n,
                             px_live=r.entry, px_eng=e.px, x_live=r.exit, x_eng=x_eng, t_in=t_in, t0=e.t0, ts=r.ts,
                             t1=e.t1, coin=r.symbol, rule=r.sleeve, side=r.side))
        else:
            rows.append(dict(i=i, j=None, R_live=r.R, units_live=r.units, px_live=r.entry, t_in=t_in, ts=r.ts,
                             coin=r.symbol, rule=r.sleeve, side=r.side))
    return pd.DataFrame(rows), used


def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "logs"
    extend_cache()
    out = [f"candles: {blend._D['XRPUSDT'].time.min():%Y-%m-%d} .. {blend._D['XRPUSDT'].time.max():%Y-%m-%d %H:%M} UTC "
           "(disk cache to 2026-09-11 16:00, the rest appended in memory)"]
    for name, f, tight, kw in (("main", "trades_blend.csv", False, {}),
                                ("triple", "trades_blend_triple.csv", True, dict(time_stop=(100, 2.0), max_units=7))):
        L = pd.read_csv(folder / f, parse_dates=["ts"])
        E = engine(tight, **kw)
        live_from = (L.ts - L.bars * L.sleeve.map(DUR)).min()
        Ew = E[(E.t1 >= live_from) & (E.t0 <= L.ts.max())].copy()
        Ew["px"] = entry_px(Ew)
        M, used = match(L, Ew)
        mt = M[M.j.notna()]
        closed_in = Ew[(Ew.t1 <= L.ts.max())]
        eng_only = closed_in[~closed_in.index.isin(used)]
        out.append(f"\n{name.upper()}: {len(L)} live trades closed {L.ts.min():%Y-%m-%d} .. {L.ts.max():%Y-%m-%d} (entries from "
                   f"{live_from:%Y-%m-%d}); engine trades over the same span {len(closed_in)}")
        out.append(f"  matched BY ENTRY {len(mt)} of {len(L)} live ({len(mt)/len(L)*100:.0f}%); live-only {len(M) - len(mt)}; "
                   f"engine-only {len(eng_only)} (shorts {int((eng_only.side == 'short').sum())}, longs {int((eng_only.side == 'long').sum())})")
        if len(mt):
            dpx = (mt.px_eng / mt.px_live - 1) * 1e4
            dR = mt.R_eng - mt.R_live
            out.append(f"  entry price, engine vs live: median {dpx.median():+.1f}bp, |diff| > 20bp on {int((dpx.abs() > 20).sum())}")
            out.append(f"  R: live total {mt.R_live.sum():+.2f}, engine total {mt.R_eng.sum():+.2f}; engine - live per trade "
                       f"median {dR.median():+.3f}, mean {dR.mean():+.3f}; |diff| > 0.25R on {int((dR.abs() > 0.25).sum())}")
            out.append(f"  units agree on {int((mt.units_live == mt.units_eng).sum())} of {len(mt)}")
            big = mt.assign(dR=dR, dpx=dpx).loc[lambda z: z.dR.abs() > 0.25].sort_values("dR", key=abs, ascending=False)
            for r in big.head(12).itertuples():
                out.append(f"    {r.coin:<9}{r.rule:<4}{r.side:<6} live {r.R_live:+7.2f}R {int(r.units_live)}u in {r.px_live:.5g} "
                           f"out {r.x_live:.5g} ({r.ts:%m-%d %H:%M}) | engine {r.R_eng:+7.2f}R {int(r.units_eng)}u in "
                           f"{r.px_eng:.5g} ({r.t0:%m-%d %H:%M}) out {r.x_eng:.5g} ({r.t1:%m-%d %H:%M})")
        for r in M[M.j.isna()].head(10).itertuples():
            out.append(f"    LIVE ONLY   in~{r.t_in:%m-%d %H:%M} out {r.ts:%m-%d %H:%M} {r.coin:<9}{r.rule:<4}{r.side:<6} {r.R_live:+.2f}R")
        for r in eng_only.sort_values("t0").head(10).itertuples():
            out.append(f"    ENGINE ONLY in {r.t0:%m-%d %H:%M} out {r.t1:%m-%d %H:%M} {r.coin:<9}{r.rule:<4}{r.side:<6} {r.R:+.2f}R")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "engine_vs_live.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()

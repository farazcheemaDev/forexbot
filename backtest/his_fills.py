"""ARE HIS FILLS PRICES THE REAL MARKET TRADED? - his entries and exits against the real NQ contract, sub-second.

WHY (the user, 2026-10-04: "I'm sure there is something we are missing")
    Rule from CLAUDE.md s9: when a result looks impossibly good, look for what makes it look good. Every test of what
    he could SEE came back empty (s26-s41), while what happens AFTER his click favours him on 25 of 26 days. One number
    in our own results was passed over: his_race_curve.py's test D, the points he BANKED against the real market's
    move over the same seconds - at zero offset he banked +3.47 points MORE than the market moved (summer +3.24), about
    half of a +7 trade. Two readings:
      (a) a sub-second artifact: statement times are whole seconds, and a +7 take-profit hit inside a fast second
          leaves the 1-second mid behind;
      (b) his FILLS are better than the real market offered - a broker pricing his trades, not a forecast. That would
          explain everything at once: why nothing recorded before his click predicts him, and how a manager shows the
          same rate on every client account at one small broker.
    His instrument is a named futures month (NASDAQ Mar / June / Sep, quarter-point grid), so his prices can be checked
    against the real contract's TRADES - every print, sub-second - with no basis to estimate.

DATA: Databento GLBX.MDP3 `trades`, raw symbols NQH6 / NQM6 / NQU6, 5 s before to 6 s after each of his NASDAQ entry
      and exit seconds (corrected clock). Priced before download; raw data local only.

PER EVENT (an entry or an exit; side = the direction of THAT order: entry BUY buys, its exit sells)
    inside     his price lies within the real traded range of [t-1, t+2) s
    fav        how much better than the market his price was: buy -> ref - price, sell -> price - ref,
               ref = the median real print in the stated second [t, t+1) (else the nearest print)
    banked vs real   his points against the real move from ref(open) to ref(close)

REGISTERED PREDICTIONS (2026-10-04, before any data is fetched)
    1. >= 90% of his prices lie inside the real traded range of their second (+-1 s): he trades the real contract.
    2. Median fav at entry and at exit is between -0.5 and +0.25 points: market orders pay about the spread.
    3. Banked minus real move averages under +1 point: test D's +3.47 was the 1-second mid lagging fast seconds.
    If instead fav is >= +1 point at the median or prices sit outside the market, his edge is his fills, not a forecast.

    python -m backtest.his_fills
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backtest.his_tape as TP  # noqa: E402
from backtest.his_clock_check import to_utc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "strategy_analysis" / "data" / "nq_fill_prints.pkl"
MONTH = {"NASDAQ Mar": "NQH6", "NASDAQ June": "NQM6", "NASDAQ Sep": "NQU6"}


def events():
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time", "close_time"])
    x = x[x.symbol.isin(MONTH)].copy()
    x["raw"] = x.symbol.map(MONTH)
    x["s"] = np.where(x.side.str.upper() == "BUY", 1, -1)
    x["t_open"] = to_utc(x.open_time, 4.0, 5.0)
    x["t_close"] = to_utc(x.close_time, 4.0, 5.0)
    return x.reset_index(drop=True)


def fetch(x):
    C = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else {}
    cl = TP.client()
    req = []
    for r in x.itertuples():
        for t in (r.t_open, r.t_close):
            key = (r.raw, str(t))
            if key not in C:
                req.append((key, r.raw, t - pd.Timedelta(seconds=5), t + pd.Timedelta(seconds=6)))
    if req:
        usd = sum(float(cl.metadata.get_cost(dataset=TP.DATASET, symbols=[raw], schema="trades", stype_in="raw_symbol",
                                             start=a.isoformat() + "Z", end=b.isoformat() + "Z"))
                  for _, raw, a, b in req)
        print(f"fetching {len(req)} event windows of real prints: estimated ${usd:.2f}", flush=True)
        if usd > 5:
            sys.exit("over $5 - stopped")
        for key, raw, a, b in req:
            df = cl.timeseries.get_range(dataset=TP.DATASET, symbols=[raw], schema="trades", stype_in="raw_symbol",
                                         start=a.isoformat() + "Z", end=b.isoformat() + "Z").to_df().reset_index()
            tcol = "ts_event" if "ts_event" in df.columns else df.columns[0]
            C[key] = pd.DataFrame({"t": pd.to_datetime(df[tcol], utc=True).dt.tz_localize(None),
                                   "px": df["price"].astype(float).to_numpy(), "size": df["size"].to_numpy()})
        CACHE.write_bytes(pickle.dumps(C))
    return C


def at(C, raw, t, price, side):
    p = C.get((raw, str(t)))
    if p is None or p.empty:
        return None
    sec = p[(p.t >= t) & (p.t < t + pd.Timedelta(seconds=1))]
    near = p[(p.t >= t - pd.Timedelta(seconds=1)) & (p.t < t + pd.Timedelta(seconds=2))]
    if near.empty:
        return None
    ref = float(sec.px.median()) if len(sec) else float(near.iloc[(near.t - t).abs().argmin()].px)
    return dict(inside=bool(near.px.min() - 1e-9 <= price <= near.px.max() + 1e-9),
                fav=(ref - price) if side > 0 else (price - ref), ref=ref,
                lo=float(near.px.min()), hi=float(near.px.max()), n=len(sec))


def main():
    x = events()
    C = fetch(x)
    rows = []
    for r in x.itertuples():
        e = at(C, r.raw, r.t_open, r.open_price, r.s)          # entry: his side
        c = at(C, r.raw, r.t_close, r.close_price, -r.s)        # exit: the opposite order
        if e is None or c is None:
            continue
        banked = r.s * (r.close_price - r.open_price)
        real = r.s * (c["ref"] - e["ref"])
        rows.append(dict(raw=r.raw, winter=r.t_open < pd.Timestamp("2026-03-29"), banked=banked, real=real,
                         e_in=e["inside"], c_in=c["inside"], e_fav=e["fav"], c_fav=c["fav"],
                         e_out=0.0 if e["inside"] else min(abs(r.open_price - e["lo"]), abs(r.open_price - e["hi"])),
                         c_out=0.0 if c["inside"] else min(abs(r.close_price - c["lo"]), abs(r.close_price - c["hi"]))))
    D = pd.DataFrame(rows)
    out = [f"{len(D)} of {len(x)} NASDAQ trades with real NQ prints at both entry and exit (contracts "
           f"{', '.join(sorted(D.raw.unique()))}); raw prints stay local",
           f"\n1. INSIDE THE REAL MARKET - his price within the real traded range of its second (+-1 s)",
           f"   entries {D.e_in.mean():.0%}   exits {D.c_in.mean():.0%}"
           f"   | outside: median distance entries {D.e_out[~D.e_in].median() if (~D.e_in).any() else 0:.2f}, "
           f"exits {D.c_out[~D.c_in].median() if (~D.c_in).any() else 0:.2f} pts",
           f"\n2. HOW MUCH BETTER THAN THE MARKET (points; + = better than the real median print of that second)",
           f"   entries: median {D.e_fav.median():+.2f}, mean {D.e_fav.mean():+.2f}, better in {(D.e_fav > 0).mean():.0%}",
           f"   exits:   median {D.c_fav.median():+.2f}, mean {D.c_fav.mean():+.2f}, better in {(D.c_fav > 0).mean():.0%}",
           f"\n3. BANKED vs THE REAL MOVE between his two seconds",
           f"   banked {D.banked.mean():+.2f} pts a trade | real move {D.real.mean():+.2f} | gap {(D.banked - D.real).mean():+.2f}"
           f" (median {(D.banked - D.real).median():+.2f})",
           f"   winter gap {(D.banked - D.real)[D.winter].mean():+.2f} ({int(D.winter.sum())}), summer "
           f"{(D.banked - D.real)[~D.winter].mean():+.2f} ({int((~D.winter).sum())})"]
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_fills.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()

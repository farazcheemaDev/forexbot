"""UPBIT LISTING FADE - short the coin on Binance after Upbit's KRW listing pump.

WHERE THIS CAME FROM (listing_events.py, 2026-09-22)
    122 Upbit KRW listing notices for coins already on Binance. The pump is real (median
    peak +29% within 60 min of the notice) and is gone before a home setup can act: +17%
    is already in the price at the first full minute. Chasing it loses. But the coin then
    FALLS: entries 0-15 min after the notice lost -5% by 24h and -9% by 72h, |t| > 2.
    So the trade is the other side: short after the pump.

    Mechanism, stated so it can be wrong: Korean retail buys on the notice; the coin is
    already liquid elsewhere, so the buying is a one-off flow with no new holders behind
    it, and arbitrageurs sell the Upbit premium back into every other venue. The same
    "sell the news" shape as the perp-listing result in bear_shorts.py.

WHAT IS TESTED, AND HOW IT COULD FAIL
    Short the Binance USDT-M PERP (a short must be on a perp) at the open of the minute
    `entry` minutes after the notice. Exit after `hold`, or at a stop checked on 1-minute
    highs (a gap fills at the open). 10bp taker round trip plus 20bp slippage, and the
    ACTUAL funding paid or received (after a pump funding is usually positive, which
    pays the short - but it can flip).

    The failure mode is the squeeze: one coin that doubles after listing costs more than
    many small wins earn. So every row shows the worst trade and the win rate, and the
    stops are swept.

PRIMARY, REGISTERED BEFORE RUNNING
    entry +60 min, hold 72h, stop +50%. The +60 min entry was NOT among the delays looked
    at in listing_events.py (0/1/2/5/15), so this row is not selected on seen data.
    Prediction: positive, smaller than the -9% seen at 72h from earlier entries (some of
    the fade happens in the first hour), and 2026 weaker than 2025.

    python -m backtest.upbit_fade
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import listing_events as L  # noqa: E402

PERPS = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "perps"
COST = (10 + 20) / 1e4
ENTRIES = (15, 60, 240)
HOLDS = {"24h": 1440, "72h": 4320, "7d": 10080}
STOPS = (None, 0.5, 0.25)


def perp_window(coin, t):
    """1m perp bars from 1 day before to 8 days after the notice, and the symbol."""
    for sym in (f"{coin}USDT", f"1000{coin}USDT"):
        days = [(t + pd.Timedelta(days=k)).strftime("%Y-%m-%d") for k in range(-1, 9)]
        parts = [L.day_1m("um", sym, d) for d in days]
        parts = [p for p in parts if p is not None]
        if not parts:
            continue
        d = pd.concat(parts).drop_duplicates("t").sort_values("t")
        d["time"] = pd.to_datetime(d.t, unit="ms")
        d = d.set_index("time")
        if (d.index < t - pd.Timedelta(minutes=60)).any():
            return sym, d
    return None, None


def funding_series(sym):
    f = PERPS / f"{sym}_funding.csv.gz"
    if not f.exists():
        return None
    fr = pd.read_csv(f, parse_dates=["time"])
    return fr.set_index("time")["rate"]


def trade(d, fr, t, entry, hold, stop):
    te = (t.ceil("min") if t != t.ceil("min") else t + pd.Timedelta(minutes=1)) \
        + pd.Timedelta(minutes=entry)
    if te not in d.index:
        return None
    e = d.at[te, "o"]
    tx = te + pd.Timedelta(minutes=hold)
    w = d.loc[te:tx]
    if len(w) < 10 or w.index[-1] < tx - pd.Timedelta(minutes=30):
        return None
    x, t_out = w.c.iloc[-1], w.index[-1]
    if stop:
        sp = e * (1 + stop)
        hit = np.flatnonzero(w.h.to_numpy() >= sp)
        if len(hit):
            k = hit[0]
            x = max(sp, w.o.iloc[k]) if k > 0 else sp
            t_out = w.index[k]
    ret = (e - x) / e - COST
    fu = 0.0
    if fr is not None:
        f = fr.loc[te:t_out]
        if len(f):
            px = d.c.reindex(f.index.floor("min")).ffill().to_numpy()
            ok = np.isfinite(px)
            fu = float((f.to_numpy()[ok] * px[ok]).sum() / e)
    return dict(ret=ret + fu, fund=fu, runup=w.h.max() / e - 1)


def one(ev):
    sym, d = perp_window(ev["coin"], ev["t"])
    if d is None:
        return []
    fr = funding_series(sym)
    out = []
    for en in ENTRIES:
        for hn, hm in HOLDS.items():
            for st in STOPS:
                r = trade(d, fr, ev["t"], en, hm, st)
                if r:
                    out.append(dict(t=ev["t"], coin=ev["coin"], entry=en, hold=hn,
                                    stop=st, **r))
    return out


def line(x, lab):
    r = x.ret.to_numpy()
    t = r.mean() / (r.std(ddof=1) / np.sqrt(len(r))) if len(r) > 2 else np.nan
    return (f"  {lab:<30}{len(r):>4}{r.mean()*100:>+8.2f}%{np.median(r)*100:>+8.2f}%"
            f"{(r > 0).mean()*100:>6.0f}%{x.fund.mean()*100:>+7.2f}%{r.min()*100:>+8.0f}%"
            f"{t:>+7.2f}")


HDR = (f"  {'':<30}{'n':>4}{'mean':>9}{'median':>9}{'win':>7}{'fund':>8}{'worst':>9}"
       f"{'t':>7}")


def main():
    ev = L.events()
    ev = ev[ev.kind == "UPBIT_KRW"].to_dict("records")
    rows = []
    with ThreadPoolExecutor(12) as ex:
        for got in ex.map(one, ev):
            rows += got
    T = pd.DataFrame(rows)
    T.to_pickle(L.OUT / "upbit_fade.pkl")
    print(f"UPBIT KRW LISTING FADE - short the Binance perp. {T.coin.nunique()} events had "
          f"a Binance perp before the notice. Costs 30bp + actual funding.\n")
    prim = T[(T.entry == 60) & (T.hold == "72h") & (T.stop == 0.5)].sort_values("t")
    cut = prim.t.quantile(0.6)
    print("PRIMARY (registered): entry +60 min, hold 72h, stop +50%")
    print(HDR)
    print(line(prim, "all"))
    print(line(prim[prim.t < cut], f"tune (< {cut:%Y-%m})"))
    print(line(prim[prim.t >= cut], "HOLDOUT"))
    for y in sorted(prim.t.dt.year.unique()):
        z = prim[prim.t.dt.year == y]
        if len(z) >= 3:
            print(line(z, f"  {y}"))
    print("\nGRID (secondary)")
    print(HDR)
    for en in ENTRIES:
        for hn in HOLDS:
            for st in STOPS:
                x = T[(T.entry == en) & (T.hold == hn) &
                      (T.stop.isna() if st is None else T.stop == st)]
                if len(x) >= 10:
                    print(line(x, f"+{en}m {hn} stop {'none' if st is None else f'+{st*100:.0f}%'}"))
        print()
    # what does a book of these look like: one event at a time is rare to overlap
    print("AS A BOOK, primary rule, each short sized at 20% of equity (no leverage beyond 1x "
          "on that slice):")
    eq, peak, dd = 1.0, 1.0, 0.0
    for r in prim.ret:
        eq *= 1 + 0.20 * r
        peak = max(peak, eq); dd = max(dd, 1 - eq / peak)
    yrs = max((prim.t.max() - prim.t.min()).days / 365.25, 0.1)
    print(f"  {len(prim)} trades over {yrs:.1f} years: x{eq:.2f} "
          f"({(eq ** (1 / yrs) - 1) * 100:+.0f}%/yr), max DD {dd*100:.0f}%")


if __name__ == "__main__":
    main()

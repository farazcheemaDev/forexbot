"""HOW MANY SECONDS DOES THE SETTLEMENT EDGE LAST? - tick data around negative-funding settlements.

settlement_check.py found the POST short (short right after a settlement that paid <= -0.10%,
hold 2h) worth +43bp gross when entered at the first trade of the settlement minute and
+10bp one minute later - below the 12bp cost. The PRE long (long from t-2h, receive the
funding) is +35bp net if it can sell at the first trade after the settlement and ~0 a minute
later. So the whole question is latency, and 1-minute bars cannot answer it.

This measures, on Binance's aggTrades archive (every trade, millisecond stamps, aggressor
side), the price a market order would actually get L seconds after the settlement:
    POST short entry  = first SELL-aggressor print at or after t + L  (you hit the bid)
    POST short exit   = last BUY-aggressor print before t + 2h         (you lift the ask)
    PRE long exit     = first SELL-aggressor print at or after t + L   (after the settlement,
                        so the funding was received)
L from 0.1s to 60s. A bot in AWS Tokyo next to Binance is ~0.005s; a PC in Pakistan
~0.15-0.4s round trip; an hourly poller like this project's bots, minutes.

Sample: 60 random POST-selected events (rate <= -0.10%, 4h/8h coins, >= $10M 24h volume),
2024-2026, seed fixed.

REGISTERED PREDICTION (before running): the drop is front-loaded but not instantaneous.
At L = 1s more than half of the t+0 edge remains (gross >= +20bp); by L = 5s it is ~+10bp.
If so, a Tokyo VM captures it and a Pakistan PC captures part of it.

    python -m backtest.settlement_ticks
"""
from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.settlement_check import settle_book, trades  # noqa: E402
from backtest.settlement_timing import VOL_FLOOR, load_all  # noqa: E402

CACHE = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "ticks_settle"
LAT = (0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60)
N = 60


def ticks(sym, t):
    """Trades from t-15min to t+2h05m for one settlement, cached per event."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{sym}_{t:%Y%m%d%H}.csv.gz"
    if f.exists():
        d = pd.read_csv(f)
        return d if len(d) else None
    frames = []
    for day in sorted({(t - pd.Timedelta(minutes=15)).strftime("%Y-%m-%d"),
                       (t + pd.Timedelta(hours=2, minutes=5)).strftime("%Y-%m-%d")}):
        u = (f"https://data.binance.vision/data/futures/um/daily/aggTrades/{sym}/"
             f"{sym}-aggTrades-{day}.zip")
        try:
            raw = urllib.request.urlopen(urllib.request.Request(
                u, headers={"User-Agent": "research"}), timeout=120).read()
            z = zipfile.ZipFile(io.BytesIO(raw))
            d = pd.read_csv(z.open(z.namelist()[0]), header=None)
            if not str(d.iloc[0, 0]).isdigit():
                d = d.iloc[1:]
            d = d.iloc[:, [1, 5, 6]]
            d.columns = ["p", "T", "m"]
            d["p"] = d.p.astype(float); d["T"] = d["T"].astype(np.int64)
            d["m"] = d.m.astype(str).str.lower().eq("true")      # True = seller was aggressor
            frames.append(d)
        except Exception:
            pass
    if not frames:
        pd.DataFrame(columns=["p", "T", "m"]).to_csv(f, index=False); return None
    d = pd.concat(frames)
    t0 = t.value // 10**6
    d = d[(d["T"] >= t0 - 15 * 60_000) & (d["T"] <= t0 + 125 * 60_000)].sort_values("T")
    d.to_csv(f, index=False, compression="gzip")
    return d if len(d) else None


def main():
    E_all = load_all()
    book = settle_book(E_all)
    E = E_all[(E_all.vol24 >= VOL_FLOOR) & np.isfinite(E_all.p0)].copy()
    E["dt"] = pd.to_datetime(E.t, unit="ns")
    E["month"] = E.dt.dt.to_period("M").astype(str)
    g = trades(E, book, 0.001, 2, "POST", -1)
    g = g[(g.gap >= 4) & (g.dt >= "2024-01-01")].reset_index(drop=True)
    rng = np.random.default_rng(21)
    S = g.iloc[rng.choice(len(g), size=min(N, len(g)), replace=False)]
    rows = []
    for ev in S.itertuples():
        t = pd.Timestamp(ev.t, unit="ns")
        d = ticks(ev.sym, t)
        if d is None:
            continue
        t0 = t.value // 10**6
        T, P, M = d["T"].to_numpy(), d["p"].to_numpy(), d["m"].to_numpy(bool)
        sells = M; buys = ~M
        # exit: last buy-aggressor print before t+2h
        kb = np.nonzero(buys & (T < t0 + 7_200_000))[0]
        if not len(kb):
            continue
        exit_px = P[kb[-1]]
        before = np.nonzero(sells & (T < t0))[0]
        rec = dict(sym=ev.sym, t=t, r=ev.r, pre_last=P[before[-1]] if len(before) else np.nan)
        for L in LAT:
            k = np.nonzero(sells & (T >= t0 + int(L * 1000)))[0]
            if len(k):
                rec[f"in{L}"] = P[k[0]]
                rec[f"lag{L}"] = (T[k[0]] - t0) / 1000
        rec["exit"] = exit_px
        rows.append(rec)
    R = pd.DataFrame(rows)
    print(f"{len(R)} events with ticks (of {len(S)} sampled), 2024-2026, rate <= -0.10%, 4h/8h coins\n")
    print("  POST short, gross bp to the t+2h exit (12bp cost + no funding for a 2h hold on 4h/8h coins)")
    print(f"  {'enter at':<12}{'mean':>8}{'median':>8}{'net 12bp':>10}{'win':>6}{'median actual lag':>20}")
    for L in LAT:
        x = (R[f"in{L}"] / R.exit - 1) * 1e4
        print(f"  t+{L:<10}{x.mean():>+8.1f}{x.median():>+8.1f}{x.mean() - 12:>+10.1f}"
              f"{(x > 12).mean()*100:>5.0f}%{R[f'lag{L}'].median():>18.2f}s")
    y = (R[f"in{LAT[0]}"] / R.pre_last - 1) * 1e4
    print(f"\n  price jump across the settlement instant (first sell print after t vs last before t):"
          f" mean {y.mean():+.1f}bp, median {y.median():+.1f}bp")
    print("  PRE long exit, price vs the last print before t (negative = what waiting costs):")
    for L in LAT:
        z = (R[f"in{L}"] / R.pre_last - 1) * 1e4
        print(f"    exit t+{L:<6}{z.mean():>+8.1f}bp  (funding received on these events: "
              f"{-R.r.mean()*1e4:+.1f}bp)")


if __name__ == "__main__":
    main()

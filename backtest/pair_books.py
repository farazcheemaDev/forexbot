"""TWO NO-HINDSIGHT BOOKS THAT EARN IN OPPOSITE MARKETS - daily Bollinger trend + 4h capitulation (2026-10-08).

tv_indicators.py's table (selected AFTER looking, so a description first): the deployed entry on DAILY bars - close
above Bollinger(30, 1.5), out at the next open after a close under the 30-day mean, 30-day cap - made +7.35% a trade
on the point-in-time top-40 (tune +10.0 / holdout +2.0%). It earns in bull runs; the capitulation book
(capitulation_exits.py tp5_nw, breadth K>=5) earns in crashes (90% of its trades with BTC under its 1000h mean).
Checked: the daily book by year, as a 10,000 PKR 8-slot account, and the two books on one account (each with its own
8 slots of half the equity), against each alone.

REGISTERED BEFORE RUNNING: the daily book's holdout gain is mostly 2024-11; its 8-slot 1x account makes +20..+60% a
year over the full period with 2021 dominating; the pair has a smaller worst fall than either book alone.

RESULT (2026-10-08, logs/pair_books.txt; random same-day order over 10 seeds in the session's check)
    - Daily book by year: 2020 +12.7% a trade, 2021 +20.4, 2022 -7.3, 2023 +6.1, 2024 +0.3, 2025 +8.0, 2026 -1.3; half
      of its holdout sum is 2024-10-15 .. 12-15 (predicted "mostly 2024-11": about half - right in spirit).
    - 10,000 PKR, 8 slots, 1x: daily alone +87..+117%/yr (median +95%), worst fall 45-58%; capitulation alone +9..+11%;
      THE PAIR (half each) +47..+59%/yr (median +51%), worst fall 25-34%, worst month -12%, months up 47%, median month
      -0.2%, months >= +10% 22%, last 12 months +66%; by year ~ 2020 +60%, 2021 +350%, 2022 -21%, 2023 +31%, 2024 +27%,
      2025 +20%, 2026 to Sep +33%. The same for every capitulation phase. At 2x the daily book is liquidated (fall 99%).
    - Predictions: daily 1x +20..+60%/yr - WRONG (higher, +95%); the pair's fall below either alone - right (27% vs 49%).
    Both books are point-in-time with dead coins: NO hindsight haircut (rule 5), stated so.

    python -m backtest.pair_books
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "pair_books.txt"


def curve(T, lev, slots, share=1.0):
    """Daily equity (start 1.0) of `share` of an account: equity x share / slots per trade, skip while full."""
    liq = 1 / lev - 0.005 - 0.0006
    eq, open_, pts = 1.0, [], []
    for r in T.sort_values("t_in", kind="stable").itertuples():
        for p in sorted([p for p in open_ if p[0] <= r.t_in]):
            eq += p[1]
            pts.append((p[0], eq))
        open_ = [p for p in open_ if p[0] > r.t_in]
        if len(open_) >= slots or eq <= 0:
            continue
        size = eq * share / slots
        open_.append((r.t_out, -size if r.worst >= liq else size * max(lev * r.net, -1.0)))
    for p in sorted(open_):
        eq += p[1]
        pts.append((p[0], eq))
    s = pd.Series([e for _, e in pts], index=pd.DatetimeIndex([t for t, _ in pts])).groupby(level=0).last()
    return s


def stats(eq):
    d = eq.resample("D").last().ffill()
    yrs = (d.index[-1] - d.index[0]).days / 365
    cagr = d.iloc[-1] ** (1 / yrs) - 1 if d.iloc[-1] > 0 else -1.0
    mo = d.resample("ME").last().pct_change().dropna()
    return cagr, float((1 - d / d.cummax()).max()), (mo > 0).mean(), mo.min(), d


def main():
    tv = pd.read_csv(ROOT / "logs" / "tv_indicators_trades.csv.gz", parse_dates=["t"])
    D = tv[(tv.tf == "1d") & (tv.ind == "bb") & (tv.exit == "own")].copy()
    # tv_indicators stored only entries; rebuild exit times as entry + holding is not stored -> use a 30-day cap upper
    # bound for slot release would distort; so the daily book is re-run here with exit times.
    from backtest.capitulation_wide import funding_cum, hourly
    from backtest.rsi_factors import prep
    from backtest.tv_indicators import bars, indicators, own_exit
    from backtest.wide_book import eligibility
    el = eligibility(40)
    rows = []
    for s in sorted(k for k, m in el.items() if m):
        h = hourly(s)
        if h is None:
            continue
        d = bars(h, "1d", 0)
        if len(d) < 120:
            continue
        P = prep(d, np.full(len(d), np.nan))
        fc = funding_cum(s, d.time.to_numpy(), h)
        ent, exs = indicators(P)["bb"]
        ym, t = d.time.dt.strftime("%Y-%m").to_numpy(), d.time.to_numpy()
        free = 0
        for i in np.flatnonzero(np.nan_to_num(ent).astype(bool)):
            if i < 60 or i < free or i + 3 >= len(t) or ym[i] not in el[s]:
                continue
            j, net, worst = own_exit(i, np.nan_to_num(exs).astype(bool), P, fc, 30)
            rows.append((s, t[i + 1], t[min(j, len(t) - 1)], net, worst))
            free = j + 1
    D = pd.DataFrame(rows, columns=["coin", "t_in", "t_out", "net", "worst"])
    D["t_in"], D["t_out"] = pd.to_datetime(D.t_in), pd.to_datetime(D.t_out)
    C = pd.read_csv(ROOT / "logs" / "capitulation_exits_trades.csv", parse_dates=["t_in", "t_out"])
    C = C[C.exit == "tp5_nw"]
    lines = [f"backtest/pair_books.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; daily bb (own exit) + 4h capitulation tp5_nw "
             f"(phase 0 and +180); 8 slots per book", ""]
    lines.append(f"DAILY BOOK: {len(D)} trades, avg {D.net.mean() * 100:+.2f}%, win {np.mean(D.net > 0):.0%}; by year: "
                 + " ".join(f"{y}:{g.net.mean() * 100:+.1f}%({len(g)})" for y, g in D.groupby(D.t_in.dt.year)))
    hold = D[D.t_in >= "2024-04-07"]
    nov = hold[(hold.t_in >= "2024-10-15") & (hold.t_in < "2024-12-15")].net.sum() / max(hold.net.sum(), 1e-9)
    lines.append(f"  holdout {hold.net.mean() * 100:+.2f}% a trade ({len(hold)}); share of the holdout sum from 2024-10-15..12-15: {nov:.0%}")
    for lev in (1, 2):
        lines.append(f"\n{lev}x:")
        for off in (0, 180):
            Cp = C[C.off == off]
            res = {}
            for nm, eq in (("daily alone", curve(D, lev, 8)), ("capitulation alone", curve(Cp, lev, 8))):
                res[nm] = stats(eq)
            ed, ec = curve(D, lev, 8, 0.5), curve(Cp, lev, 8, 0.5)
            idx = ed.index.union(ec.index)
            both = (ed.reindex(idx).ffill().fillna(1.0) - 1) + (ec.reindex(idx).ffill().fillna(1.0) - 1) + 1
            res["THE PAIR (half each)"] = stats(both)
            for nm, (cagr, dd, up, worst_m, _d) in res.items():
                lines.append(f"  [cap phase +{off}m] {nm:22}: {cagr * 100:+6.0f}%/yr, worst fall {dd:.0%}, months up {up:.0%}, "
                             f"worst month {worst_m * 100:+.0f}%")
            d = res["THE PAIR (half each)"][4]
            yr = d.resample("YE").last()
            yr = (yr / yr.shift(1).fillna(1.0) - 1)
            lines.append("      the pair by year: " + " ".join(f"{t.year}:{v * 100:+.0f}%" for t, v in yr.items()))
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")


if __name__ == "__main__":
    main()

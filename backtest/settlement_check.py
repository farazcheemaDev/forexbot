"""TRYING TO BREAK THE SETTLEMENT RESULT - three flattering assumptions, removed one at a time.

settlement_timing.py (first pass, logged) found something its registered predictions did NOT
expect: around settlements where funding is strongly NEGATIVE, price rises into the
settlement and falls after it (8h coins, <= -0.30%: +138bp excess before, -138bp after), and
"short right after a settlement that paid <= -0.10%" is positive in every year 2020-2026.
The mechanism fits - shorts close to dodge a payment, then re-open. It also fits three ways
of being fooled, so each is tested here BEFORE anything is believed:

  1. FUNDING CROSSED WHILE HOLDING WAS NOT CHARGED. Coins with extreme funding are often
     moved to 4h or 1h intervals. A 2h short entered right after one settlement on a 1h coin
     crosses two more, each paid by shorts. Here every settlement strictly inside the hold
     (and the exit instant, conservatively) is charged or credited by side.
  2. THE ENTRY PRICE. The hourly open is the first trade at/after the settlement second. If
     the drop happens in the first seconds, a real bot never gets that price. 1-minute bars
     on a random sample of events: enter at t, t+1m, t+3m, t+5m.
  3. SLIPPAGE. These are often small coins. Costs 12bp and a 30bp stress.

Also split by funding interval, by liquidity tier, and by year.

REGISTERED PREDICTIONS (before running this file)
    - Charging crossed funding kills the POST short on 1h-interval coins and trims 4h ones;
      8h coins keep most of it.
    - A 1-minute delay removes most of the POST edge (front-loaded), little of the PRE edge.
    - At 30bp costs nothing survives below the -0.30% bucket.
    Verdict expected: a thin residue on 8h coins at extreme funding, too rare to be a book.

    python -m backtest.settlement_check           # hourly, all events
    python -m backtest.settlement_check --minute  # + the 1-minute latency sample
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.settlement_timing import VOL_FLOOR, load_all, month_boot_t  # noqa: E402

HOUR = 3600 * 10**9


def settle_book(E_all):
    """sym -> (settlement times ns, rates), from the unfiltered event table."""
    return {s: (g.t.to_numpy(np.int64), g.r.to_numpy(float))
            for s, g in E_all.groupby("sym", sort=False)}


def crossed(book, sym, a, b):
    """Sum of rates for settlements with a < s <= b (vectorised over events)."""
    out = np.zeros(len(sym))
    df = pd.DataFrame(dict(sym=sym, a=a, b=b))
    for s, g in df.groupby("sym"):
        ts, rs = book[s]
        cs = np.r_[0.0, np.cumsum(rs)]
        ia = np.searchsorted(ts, g.a.to_numpy(np.int64), side="right")
        ib = np.searchsorted(ts, g.b.to_numpy(np.int64), side="right")
        out[g.index.to_numpy()] = cs[ib] - cs[ia]
    return out


def trades(E, book, thr, H, kind, sign_side):
    """kind PRE: enter t-H, exit t; selected on r_prev. POST: enter t, exit t+H; on r.
    sign_side: -1 = negative-funding side (PRE long / POST short), +1 = positive side
    (PRE short / POST long). Returns event frame with gross price R and funding R."""
    if kind == "PRE":
        sel = (E.r_prev <= -thr) if sign_side < 0 else (E.r_prev >= thr)
        g = E[sel & np.isfinite(E[f"pm{H}"])].reset_index(drop=True)
        d = 1 if sign_side < 0 else -1                  # long on negative side
        px = d * (g.p0 / g[f"pm{H}"] - 1)
        a, b = g.t.to_numpy(np.int64) - H * HOUR, g.t.to_numpy(np.int64)
    else:
        sel = (E.r <= -thr) if sign_side < 0 else (E.r >= thr)
        g = E[sel & np.isfinite(E[f"pp{H}"])].reset_index(drop=True)
        d = -1 if sign_side < 0 else 1                  # short on negative side
        px = d * (g[f"pp{H}"] / g.p0 - 1)
        a, b = g.t.to_numpy(np.int64), g.t.to_numpy(np.int64) + H * HOUR
    fund = -d * crossed(book, g.sym.to_numpy(), a, b)   # a long pays +r, a short receives it
    g = g.assign(px=px.to_numpy(), fund=fund)
    return g


def report(lab, g, cut, costs=(12, 30)):
    tu = (g.dt < cut).to_numpy(); ho = ~tu
    parts = []
    for c in costs:
        nb = (g.px + g.fund - c / 1e4).to_numpy() * 1e4
        parts.append(f"{c:>3}bp: tune {nb[tu].mean():+6.1f} (t{month_boot_t(nb[tu], g.month.to_numpy()[tu]):+.1f})"
                     f" hold {nb[ho].mean():+6.1f} (t{month_boot_t(nb[ho], g.month.to_numpy()[ho]):+.1f})")
    print(f"  {lab:<34}{len(g):>7,}  px {g.px.mean()*1e4:+6.1f}  fund {g.fund.mean()*1e4:+6.1f} | "
          + " | ".join(parts))


def hourly():
    E_all = load_all()
    book = settle_book(E_all)
    E = E_all[(E_all.vol24 >= VOL_FLOOR) & np.isfinite(E_all.p0)].copy()
    E["dt"] = pd.to_datetime(E.t, unit="ns")
    E["month"] = E.dt.dt.to_period("M").astype(str)
    cut = E.dt.quantile(0.6)
    print(f"tune < {cut:%Y-%m-%d} <= holdout | bp per trade, funding charged on every settlement held\n")
    for thr in (0.001, 0.003):
        print(f"--- |rate| >= {thr*100:.2f}% -----------------------------------------------")
        for kind, H in (("PRE", 2), ("POST", 2), ("POST", 4)):
            for side in (-1, 1):
                name = {("PRE", -1): "PRE long (neg funding)", ("PRE", 1): "PRE short (pos funding)",
                        ("POST", -1): "POST short (neg funding)", ("POST", 1): "POST long (pos funding)"}[(kind, side)]
                g = trades(E, book, thr, H, kind, side)
                if len(g) < 30:
                    continue
                report(f"{name} {H}h", g, cut)
        print()

    print("--- POST short 2h after a <= -0.10% settlement, split ---------------------")
    g = trades(E, book, 0.001, 2, "POST", -1)
    for lab, m in (("interval 8h", g.gap == 8), ("interval 4h", g.gap == 4),
                   ("interval 1-2h", g.gap <= 2),
                   ("24h volume >= $50M", g.vol24 >= 50e6), ("24h volume $10-50M", g.vol24 < 50e6)):
        if m.sum() >= 30:
            report(lab, g[m.to_numpy()].reset_index(drop=True), cut)
    print("\n  by year, 12bp, funding charged (mean bp, n):")
    nb = (g.px + g.fund - 12 / 1e4) * 1e4
    for y, v in nb.groupby(g.dt.dt.year):
        print(f"    {y}: {v.mean():+7.1f}  n={len(v):,}  win {(v > 0).mean()*100:.0f}%")
    return E, book, cut


def minute(E, book, n=240, seed=7):
    """Latency: 1-minute bars around a random sample of POST-short and PRE-long events."""
    from backtest.listing_events import day_1m
    rng = np.random.default_rng(seed)
    g = trades(E, book, 0.001, 2, "POST", -1)
    g = g[g.gap >= 4].reset_index(drop=True)              # 4h/8h coins: the survivable part
    pick = g.iloc[rng.choice(len(g), size=min(n, len(g)), replace=False)]
    rows = []
    for _, ev in pick.iterrows():
        t = pd.Timestamp(ev.t, unit="ns")
        days = sorted({(t - pd.Timedelta(hours=3)).strftime("%Y-%m-%d"),
                       (t + pd.Timedelta(hours=3)).strftime("%Y-%m-%d")})
        parts = [day_1m("um", ev.sym, d) for d in days]
        parts = [p for p in parts if p is not None]
        if not parts:
            continue
        d = pd.concat(parts).drop_duplicates("t").set_index("t").sort_index()
        tm = t.value // 10**6

        def o(k):
            v = d["o"].get(tm + k * 60_000)
            return float(v) if v is not None else np.nan
        exit_ = o(120)
        rec = dict(year=t.year, fund=ev.fund, pre_in=o(-120), pre_out0=o(0), pre_out1=o(1))
        for k in (0, 1, 3, 5):
            rec[f"post{k}"] = -(exit_ / o(k) - 1) if np.isfinite(o(k)) else np.nan
        rows.append(rec)
    R = pd.DataFrame(rows)
    print(f"\nLATENCY, 1-minute bars, {len(R)} random POST-short events (<= -0.10%, 4h/8h coins)")
    print("  gross bp, short from entry to t+2h (funding not included here):")
    for k in (0, 1, 3, 5):
        x = R[f"post{k}"].dropna() * 1e4
        print(f"    enter t+{k}m: mean {x.mean():+6.1f}  median {x.median():+6.1f}  n {len(x)}")
    x0 = (R.pre_out0 / R.pre_in - 1).dropna() * 1e4
    x1 = (R.pre_out1 / R.pre_in - 1).dropna() * 1e4
    print(f"  PRE long from t-2h, exit at t: {x0.mean():+6.1f}  exit at t+1m: {x1.mean():+6.1f} "
          "(price only; this sample is POST-selected, so it is a timing check, not a PRE result)")


def main():
    E, book, cut = hourly()
    if "--minute" in sys.argv:
        minute(E, book)


if __name__ == "__main__":
    main()

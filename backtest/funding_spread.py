"""THE CROSS-EXCHANGE FUNDING GAP - a trade that does not care which way the market goes (2026-10-18)

The user, on the sideways gap: "try everything, we need to fill this gap too". Doc 20 lists what failed in chop; this
was never tested: the same coin pays different funding on two exchanges. Short it where funding is HIGHER, long it where
it is LOWER: the two price moves cancel, the funding difference is collected every settlement.

DATA (backtest/funding_spread_fetch.py, public APIs): funding of the top-120 (by Binance volume) USDT perps listed on BOTH
Binance and Bybit today - Binance and Bybit from 2022-01, Bitget ~90 days (all its API keeps). Crypto only (Binance's
underlyingType COIN). Coins delisted before today are missing (survivors - flatters nothing obvious here: the trade is
direction-free, but dead coins had the wildest funding, which is where both the money and the liquidations were).
RULE
    a day's funding = the sum of a venue's settlements in (00:00, 24:00] UTC (handles 8h / 4h / 1h intervals alike)
    at each 00:00 UTC, from settled days only: each coin's trailing K-day mean gap g = f_A - f_B
    hold the N coins with the largest |g| above theta (bp a day): short on the venue paying more, long on the other;
    earn that day's actual gap; drop a coin when it leaves the top N / falls under theta
    fees: taker on both legs at entry and exit (Binance 5bp, Bybit 5.5bp, Bitget 6bp a side)
    capital: each leg on its own exchange at L = 2x (a +50% move liquidates the short leg; counted, not modelled)
    returns on the capital tied up (both exchanges' margin); empty slots earn 0
GRID  K in {3, 7}, theta in {2, 5, 10} bp/day, N in {5, 10} - 12 cells, chosen on the TUNE half (before 2024-08-29),
      read on the holdout. By BTC regime (market_neutral.btc_regime, month = most of its days).
REGISTERED BEFORE THE RUN (2026-10-18)
    F1 Binance-Bybit, the tune-chosen cell, after fees: under +10%/yr on capital on the holdout.
    F2 the gap is bigger in bull months than sideways ones: sideways months average under +0.5% on capital.
    F3 Bitget's gaps with Binance (last ~90 days) are larger than Bybit's with Binance (mean |gap| of the top 10).

RESULT (2026-10-18, logs/funding_spread.txt) - DEAD. Binance-Bybit 2022-2026, 91 coins: the median coin-day gap is
1.0 bp, the day's 10 widest average 8.5 bp, against 21 bp to open and close both legs - and the wide gaps do not persist
(they flip within days). The tune-chosen cell (K 7, theta 5, N 10) makes +1.1%/yr tune and +0.1%/yr holdout (Sharpe
0.06); 6 of 12 cells lose on both halves. Sideways months +0.13% average (F2 WRONG only because bull months are no
better: the gap is ~0 in every market). Last 89 days: Binance-Bitget +1.95% (+8%/yr annualised, one short window), its
gap 13.5 bp/day vs Binance-Bybit 18.6 (F3 WRONG). F1 RIGHT. At maker fees (~8 bp a round trip) roughly +3%/yr at best -
not worth capital split across two exchanges.

    python -m backtest.funding_spread
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "strategy_analysis" / "data" / "funding_spread"
LOG = ROOT / "logs" / "funding_spread.txt"
FEE = {"binance": 5e-4, "bybit": 5.5e-4, "bitget": 6e-4}
LEV = 2.0
CUT = pd.Timestamp("2024-08-29")
GRID = [(k, th, n) for k in (3, 7) for th in (2, 5, 10) for n in (5, 10)]


def crypto_only(syms: list) -> list:
    info = json.loads(urllib.request.urlopen(urllib.request.Request(
        "https://fapi.binance.com/fapi/v1/exchangeInfo", headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read())
    kind = {s["symbol"]: (s.get("underlyingType"), tuple(s.get("underlyingSubType") or ())) for s in info["symbols"]}
    return [s for s in syms if kind.get(s, ("?",))[0] == "COIN" and not any("TradFi" in x or "Stock" in x
                                                                            for x in kind.get(s, ("", ()))[1])]


def daily(venue: str, sym: str) -> pd.Series:
    p = DATA / f"{venue}_{sym}.csv"
    if not p.exists():
        return pd.Series(dtype=float)
    d = pd.read_csv(p)
    if d.empty:
        return pd.Series(dtype=float)
    day = pd.to_datetime((d.ts_ms - 1) // 86_400_000 * 86_400_000, unit="ms")     # a 00:00 settlement ends the day before
    s = d.groupby(day).rate.sum()
    full = pd.date_range(s.index.min(), s.index.max(), freq="D")
    return s.reindex(full)                                  # a missing day inside the range stays NaN (no data)


def panel(a: str, b: str, syms: list) -> pd.DataFrame:
    """Daily gap f_a - f_b per coin (NaN where either venue has no data)."""
    cols = {}
    for s in syms:
        x, y = daily(a, s), daily(b, s)
        if len(x) and len(y):
            g = (x - y).dropna()
            if len(g) > 20:
                cols[s] = g
    return pd.DataFrame(cols).sort_index()


def run(G: pd.DataFrame, a: str, b: str, k: int, th_bp: float, n: int) -> pd.DataFrame:
    """Daily return on capital, the coins held, and the fee paid."""
    sig = G.rolling(k, min_periods=k).mean().shift(1)       # settled days only
    fee_leg = FEE[a] + FEE[b]
    leg = LEV / 2 / n                                       # each pair's leg notional per unit of capital
    held: dict = {}                                         # coin -> direction (+1: short a / long b)
    rows = []
    for t in G.index:
        s = sig.loc[t].dropna()
        s = s[s.abs() >= th_bp / 1e4]
        want = dict((c, int(np.sign(s[c]))) for c in s.abs().sort_values(ascending=False).index[:n])
        fee = 0.0
        for c, dsgn in held.items():
            if want.get(c) != dsgn:
                fee += leg * fee_leg                        # exit both legs
        for c, dsgn in want.items():
            if held.get(c) != dsgn:
                fee += leg * fee_leg                        # enter both legs
        held = want
        g = G.loc[t]
        earn = sum(leg * dsgn * g[c] for c, dsgn in held.items() if np.isfinite(g.get(c, np.nan)))
        rows.append((t, earn - fee, fee, len(held), np.mean([abs(g[c]) for c in held if np.isfinite(g.get(c, np.nan))])
                     if held else 0.0))
    return pd.DataFrame(rows, columns=["t", "ret", "fee", "n", "gap"]).set_index("t")


def stats(r: pd.Series) -> tuple:
    if len(r) < 20:
        return (np.nan, np.nan, np.nan)
    c = (1 + r).cumprod()
    yrs = len(r) / 365.0
    cagr = c.iloc[-1] ** (1 / yrs) - 1
    dd = float((1 - c / c.cummax()).max())
    sh = r.mean() / r.std() * np.sqrt(365) if r.std() > 0 else np.nan
    return cagr, dd, sh


def main():
    from backtest.market_neutral import btc_regime, load_panel
    syms = crypto_only(json.loads((DATA / "universe.json").read_text()))
    C, _, _ = load_panel()
    reg = btc_regime(C)
    lines = [f"backtest/funding_spread.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(syms)} crypto coins on "
             f"both Binance and Bybit (top 120 by volume today); fees taker both legs; {LEV:g}x a leg", ""]
    G = panel("binance", "bybit", syms)
    lines.append(f"1. BINANCE - BYBIT, {G.index[0]:%Y-%m-%d} .. {G.index[-1]:%Y-%m-%d}, {G.shape[1]} coins")
    absg = G.abs()
    top10 = absg.apply(lambda r: r.dropna().nlargest(10).mean(), axis=1)
    lines.append(f"   the gap itself: median coin-day |gap| {absg.stack().median() * 1e4:.2f} bp/day; mean of the day's "
                 f"10 widest {top10.mean() * 1e4:.1f} bp/day (fees: {(FEE['binance'] + FEE['bybit']) * 2e4:.0f} bp a round trip)")
    lines.append(f"   {'K':>3}{'theta':>6}{'N':>4}{'tune CAGR':>11}{'fall':>6}{'Sharpe':>7}{'hold CAGR':>11}{'fall':>6}"
                 f"{'Sharpe':>7}{'held':>6}{'fees/yr':>9}")
    res = {}
    for k, th, n in GRID:
        R = run(G, "binance", "bybit", k, th, n)
        tu, ho = R[R.index < CUT], R[R.index >= CUT]
        st, sh = stats(tu.ret), stats(ho.ret)
        res[(k, th, n)] = (R, st, sh)
        lines.append(f"   {k:>3}{th:>6}{n:>4}{st[0] * 100:>+10.1f}%{st[1] * 100:>5.0f}%{st[2]:>7.2f}"
                     f"{sh[0] * 100:>+10.1f}%{sh[1] * 100:>5.0f}%{sh[2]:>7.2f}{R.n.mean():>6.1f}{R.fee.sum() / (len(R) / 365) * 100:>8.1f}%")
    best = max(res, key=lambda c: res[c][1][2] if np.isfinite(res[c][1][2]) else -9)
    R = res[best][0]
    lines += ["", f"   TUNE-CHOSEN cell K {best[0]} theta {best[1]} N {best[2]}: holdout CAGR {res[best][2][0] * 100:+.1f}%, "
              f"Sharpe {res[best][2][2]:.2f}"]
    lab = reg.groupby(reg.index.to_period("M")).agg(lambda s: s.value_counts().idxmax())
    m = (1 + R.ret).groupby(R.index.to_period("M")).prod() - 1
    m = m.iloc[1:-1]
    mr = pd.DataFrame({"ret": m, "reg": lab.reindex(m.index)}).dropna()
    lines.append("   by market (month = the BTC regime most of its days carried): average / typical month, months up")
    for g in ("bull", "chop", "bear"):
        x = mr[mr.reg == g].ret
        lines.append(f"     {g:<5} {len(x):>3} months  {x.mean() * 100:+6.2f}% / {x.median() * 100:+6.2f}%  up {(x > 0).mean() * 100:3.0f}%")
    yr = (1 + R.ret).groupby(R.index.year).prod() - 1
    lines.append("   by year: " + "  ".join(f"{y} {v * 100:+.1f}%" for y, v in yr.items()))
    # the two-month Bitget window
    lines += ["", "2. THE LAST ~90 DAYS (Bitget's whole API history): mean |gap| of the day's 10 widest coins, bp/day; "
                  "and the tune-chosen rule on each pair"]
    win = {}
    for a, b in (("binance", "bybit"), ("binance", "bitget"), ("bybit", "bitget")):
        Gp = panel(a, b, syms)
        if Gp.empty:
            continue
        Gp = Gp[Gp.index >= G.index[-1] - pd.Timedelta(days=88)]
        t10 = Gp.abs().apply(lambda r: r.dropna().nlargest(10).mean(), axis=1).mean()
        Rp = run(Gp, a, b, *best)
        c = (1 + Rp.ret).prod() - 1
        win[(a, b)] = t10
        lines.append(f"   {a:>8}-{b:<7} {Gp.shape[1]:>3} coins  top-10 |gap| {t10 * 1e4:5.1f} bp/day   rule: {c * 100:+.2f}% "
                     f"over {len(Rp)} days ({((1 + c) ** (365 / max(len(Rp), 1)) - 1) * 100:+.0f}%/yr)")
    chop = mr[mr.reg == "chop"].ret.mean()
    bull = mr[mr.reg == "bull"].ret.mean()
    f3 = win.get(("binance", "bitget"), np.nan) > win.get(("binance", "bybit"), np.nan)
    lines += ["", "REGISTERED PREDICTIONS",
              f"  F1 tune-chosen holdout CAGR {res[best][2][0] * 100:+.1f}% (< +10) -> {'RIGHT' if res[best][2][0] < 0.10 else 'WRONG'}",
              f"  F2 bull {bull * 100:+.2f}% vs sideways {chop * 100:+.2f}% a month; sideways < +0.5% -> "
              f"{'RIGHT' if bull > chop and chop < 0.005 else 'WRONG'}",
              f"  F3 Bitget-Binance gap {win.get(('binance', 'bitget'), np.nan) * 1e4:.1f} > Bybit-Binance "
              f"{win.get(('binance', 'bybit'), np.nan) * 1e4:.1f} bp/day -> {'RIGHT' if f3 else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

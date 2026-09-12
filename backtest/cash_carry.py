"""DELTA-NEUTRAL CASH-AND-CARRY, selected cross-sectionally.

WHY THIS, AFTER FIVE FAILURES
-----------------------------
Every strategy tested today found a real effect that was too small or too noisy:

    crypto momentum       +0.05R gross   vs 0.04-0.08R fees
    gold donchian         regime-dependent, -14.9%/yr unseen
    VSA absorption        +0.045R, does not survive peer instruments
    intramarket diff      +15bp, below the mining noise floor
    funding cross-section +2 to +15bp carry, SWAMPED by unhedged price noise

The last one is the interesting failure: the carry was MECHANICAL and behaved
exactly as designed (growing with hold length while cost stayed fixed). It died
because "equal dollar long/short across different coins" is not actually neutral -
the baskets had different volatilities, leaving price noise 10-30x the carry.

THE FIX IS STRUCTURAL, NOT STATISTICAL
--------------------------------------
Hold BOTH LEGS IN THE SAME COIN:

    LONG  spot        (or the coin outright)
    SHORT perpetual   (same coin, same notional)

Now the price exposure cancels by construction - not by weighting, not by
estimation. What remains is:

    + funding received on the short perp   (mechanical, paid 3x/day)
    - change in the spot/perp BASIS        (small, and mean-reverting because the
                                            perp is tethered to spot by funding)

This requires NO price forecast. It is a fee-collection business, not a bet. That
is a different category from everything above, and the only category that has not
yet failed here.

CROSS-SECTIONAL SELECTION is what turns 4%/yr into something interesting: instead
of holding BTC (funding ~+4%/yr), hold whichever coins are currently paying the
most. Measured maxima on small alts reached 0.35-0.58% per 8h = 380-630%
annualised while they last.

WHAT IS MEASURED HONESTLY HERE
  * real SPOT and real PERP prices, so the basis is measured, never assumed
  * funding only collected when POSITIVE (long spot/short perp can only harvest
    positive funding; negative-funding coins would need short spot, i.e. borrow)
  * costs on BOTH legs at every rebalance
  * two halves, and correlation to BTC (it should be ~0)

    python -m backtest.cash_carry
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.funding_xs import UNIVERSE, funding_history  # noqa: E402

CACHE = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data"


def spot_8h(sym: str) -> pd.DataFrame | None:
    """SPOT 8h closes (api.binance.com), as opposed to the perp (fapi)."""
    f = CACHE / f"spot8h_{sym}.csv"
    if f.exists():
        return pd.read_csv(f, parse_dates=["t"])
    out, end = [], int(time.time() * 1000)
    for _ in range(3):
        u = (f"https://api.binance.com/api/v3/klines?symbol={sym}"
             f"&interval=8h&limit=1000&endTime={end}")
        try:
            r = json.load(urllib.request.urlopen(u, timeout=25))
        except Exception:
            return None
        if not r:
            break
        out = r + out
        end = int(r[0][0]) - 1
        time.sleep(0.25)
    if not out:
        return None
    d = pd.DataFrame([{"t": pd.to_datetime(k[0], unit="ms"),
                       "close": float(k[4])} for k in out])
    d = d.drop_duplicates("t").sort_values("t")
    d.to_csv(f, index=False)
    return d.reset_index(drop=True)


def perp_8h(sym: str) -> pd.DataFrame | None:
    f = CACHE / f"px8h_{sym}.csv"
    if f.exists():
        return pd.read_csv(f, parse_dates=["t"])
    return None


def build():
    F, S, Pp = {}, {}, {}
    for s in UNIVERSE:
        fr = funding_history(s)
        sp = spot_8h(s)
        pp = perp_8h(s)
        if fr is None or sp is None or pp is None:
            continue
        if len(fr) < 600 or len(sp) < 600 or len(pp) < 600:
            continue
        F[s] = fr.set_index("t")["fundingRate"]
        S[s] = sp.set_index("t")["close"]
        Pp[s] = pp.set_index("t")["close"]
    F = pd.DataFrame(F).sort_index()
    S = pd.DataFrame(S).sort_index()
    Pp = pd.DataFrame(Pp).sort_index()
    idx = F.index.intersection(S.index).intersection(Pp.index)
    return F.loc[idx], S.loc[idx], Pp.loc[idx]


def simulate(F, S, Pp, k: int, hold: int, min_funding: float,
             fee_bp: float) -> dict | None:
    """Long spot + short perp on the top-k funding payers. Rebalance every `hold`.

    per-period P&L per position =
        + funding_received                       (short perp receives when f>0)
        + (spot_return - perp_return)            (basis change; ~0 by tethering)
    """
    sret = np.log(S).diff().shift(-1)
    pret = np.log(Pp).diff().shift(-1)
    rows = []
    i, n = 1, len(F)
    while i < n - hold:
        f0 = F.iloc[i].dropna()
        cand = f0[f0 > min_funding]
        if len(cand) < 1:
            i += hold
            continue
        picks = cand.nlargest(min(k, len(cand))).index
        pnl = 0.0
        for h in range(hold):
            j = i + h
            if j >= n - 1:
                break
            for c in picks:
                fv = F.iloc[j].get(c)
                sr = sret.iloc[j].get(c)
                pr = pret.iloc[j].get(c)
                if pd.notna(fv):
                    pnl += fv / len(picks)                  # funding received
                if pd.notna(sr) and pd.notna(pr):
                    pnl += (sr - pr) / len(picks)           # basis change
        pnl -= 2 * fee_bp / 10000.0                         # two legs, round trip
        rows.append((F.index[i], pnl))
        i += hold
    if len(rows) < 25:
        return None
    t = [r[0] for r in rows]
    r = np.array([r[1] for r in rows])
    yrs = (t[-1] - t[0]).days / 365.25
    eq = np.cumprod(1 + r)
    pk = np.maximum.accumulate(eq)
    dd = float(((pk - eq) / pk).max() * 100)
    ann = float((eq[-1] ** (1 / yrs) - 1) * 100) if eq[-1] > 0 else -100
    return dict(n=len(r), bp=float(r.mean() * 1e4), ann=ann, dd=dd,
                mar=(ann / dd if dd > 0 else np.inf), win=float((r > 0).mean()),
                sharpe=float(r.mean() / r.std() * np.sqrt(len(r) / yrs))
                if r.std() > 0 else 0.0, t=t, r=r)


def main():
    print("Building funding + SPOT + PERP panels (cached after first run)...")
    F, S, Pp = build()
    print(f"  {F.shape[1]} coins with all three series, {len(F)} settlements "
          f"({F.index.min().date()} .. {F.index.max().date()})")

    # how big is the basis noise we are relying on being small?
    basis = (np.log(S) - np.log(Pp))
    bd = basis.diff().stack().dropna()
    print(f"\n  basis change per 8h: sd {bd.std()*1e4:.2f}bp, "
          f"99th pct |x| {np.percentile(np.abs(bd),99)*1e4:.1f}bp")
    print(f"  (this is the ONLY price risk left; compare to funding of 2-50bp/8h)")
    fpos = F.stack().dropna()
    print(f"  funding: mean {fpos.mean()*1e4:+.2f}bp/8h, "
          f"90th {np.percentile(fpos,90)*1e4:+.1f}bp, "
          f"99th {np.percentile(fpos,99)*1e4:+.1f}bp\n")

    mid = len(F) // 2
    print(f"{'k':>3} {'hold':>6} {'minF':>7} {'fee':>5} | "
          f"{'1st half':>16} | {'2nd half':>16} | {'FULL':>26}")
    print(f"{'':>3} {'':>6} {'':>7} {'':>5} | {'n':>5}{'bp':>6}{'ann%':>7} | "
          f"{'n':>5}{'bp':>6}{'ann%':>7} | {'ann%':>7}{'maxDD%':>8}{'MAR':>6}{'Sh':>5}")
    good = []
    for fee in (12.0, 4.0):
        for k in (1, 3, 5):
            for hold in (3, 9, 21):
                for mf in (0.0, 0.0002):
                    a = simulate(F.iloc[:mid], S.iloc[:mid], Pp.iloc[:mid], k, hold, mf, fee)
                    b = simulate(F.iloc[mid:], S.iloc[mid:], Pp.iloc[mid:], k, hold, mf, fee)
                    fu = simulate(F, S, Pp, k, hold, mf, fee)
                    if not (a and b and fu):
                        continue
                    print(f"{k:>3} {hold*8:>5}h {mf*1e4:>6.0f}b {fee:>5.0f} | "
                          f"{a['n']:>5}{a['bp']:>+6.1f}{a['ann']:>+7.1f} | "
                          f"{b['n']:>5}{b['bp']:>+6.1f}{b['ann']:>+7.1f} | "
                          f"{fu['ann']:>+7.1f}{fu['dd']:>8.1f}{fu['mar']:>6.2f}"
                          f"{fu['sharpe']:>5.2f}")
                    if a["ann"] > 0 and b["ann"] > 0:
                        good.append((fu["sharpe"], k, hold, mf, fee, fu))
    if not good:
        print("\nnothing positive in BOTH halves.")
        return
    good.sort(reverse=True, key=lambda x: x[0])
    sh, k, hold, mf, fee, fu = good[0]
    print(f"\nBEST consistent: k={k} hold={hold*8}h minFunding={mf*1e4:.0f}bp fee={fee:.0f}bp")
    print(f"  ann {fu['ann']:+.1f}%  maxDD {fu['dd']:.1f}%  MAR {fu['mar']:.2f}  "
          f"Sharpe {sh:.2f}  win {fu['win']*100:.1f}%  ({fu['n']} rebalances)")
    btc = np.log(Pp["BTCUSDT"]).diff(hold).reindex(pd.Index(fu["t"]))
    c = float(pd.Series(fu["r"], index=fu["t"]).corr(btc))
    print(f"  correlation to BTC = {c:+.3f}  "
          f"({'DELTA NEUTRAL as designed' if abs(c) < 0.25 else 'residual directional exposure'})")
    print(f"\n  positive in both halves: {len(good)} of the configs tested")


if __name__ == "__main__":
    main()

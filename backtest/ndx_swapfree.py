"""WHAT A SWAP-FREE ACCOUNT CHANGES: holding NASDAQ, timed and levered, with no overnight cost (2026-10-22)

THE USER (2026-10-22): "there must be something you are not looking at". What every NASDAQ / gold hold here died on was
not the market but the SWAP: fx_anomalies.py T1 - NASDAQ's overnight session grosses +3.41bp a night (1999-2026) and nets
-0.32bp after 0.77bp spread + 2.04bp swap. MT5 read 2026-10-22 (the user's Exness DEMO, Trial16): USTECm swap long -658.9
points a lot a night (~2.2bp), swap SHORT 0; XAUUSDm and US30m the same pattern. Exness grants swap-free status to many
accounts (the user must check theirs). With no swap, leverage on an index CFD costs nothing to hold - the thing a futures
trader pays ~5%/yr for. This file measures what that is worth, honestly timed:
  R0  BUY AND HOLD NASDAQ (^NDX daily, Yahoo, 1999-2026 - the dot-com crash included)
  R1  ABOVE 200   long while NASDAQ closed above its 200-day average, else flat (Gayed & Bilello 2016, "Leverage for the
                  long run": levered index exposure is only survivable with a trend exit)
  R2  CALM CURVE  long while VIX closed BELOW VIX3M (the volatility curve in contango; from 2006-07), else flat
  R3  BOTH        long only when R1 and R2 agree
  each at 1x, 2x, 3x of equity, rebalanced daily; decided on a close and held from that close (VIX settles 15 min
  after NASDAQ closes: re-run with one more day of delay, the 2x results hold - R1 +23.0% / R3 +19.0%, fall 41%)
  plus OVERNIGHT  T1 again: long from the 16:00 close to the 09:30 open, swap-free (HistData NSXUSD minutes, 2010-2026)
COSTS     0.77bp a round trip on every change of position (Exness USTECm) + 0.1bp a day of rebalancing at 2-3x;
          SWAP-FREE, and WITH 2.04bp a night on the long notional (Friday holds pay 3 nights)
PASS      a timing rule must beat BUY AND HOLD at the same leverage on Sharpe in BOTH halves (60/40 by date) AND fall less

REGISTERED BEFORE THE RUN (2026-10-22)
  S1 OVERNIGHT swap-free nets > 0 with t >= 2 over 2010-2026, positive on both halves.
  S2 R1 beats buy-and-hold on Sharpe on both halves and roughly halves the biggest fall (the 2000-02 and 2008 crashes).
  S3 R2 does the same from 2006; R3 has the best Sharpe of the three.
  S4 WITH swap, 3x buy-and-hold loses >= 12 points a year to swap; swap-free 3x R1 has CAGR >= +25%/yr with a fall <= 60%.

RESULT (2026-10-22, logs/ndx_swapfree.txt; BACKTEST) - the swap is what was killing NASDAQ; free of it, leverage pays.
  - The swap at 3x costs ~27 points a year: 3x buy-and-hold 2006-2026 +33.3%/yr swap-free vs +6.6% with swap (fall 95%).
  - OVERNIGHT swap-free +3.73bp a night net, t +2.53 (tune t +2.44 / holdout +1.41) - S1 RIGHT; with swap +0.52bp.
  - Timing does NOT beat holding on Sharpe on both halves (S2, S3 WRONG): its value is the fall. 2006-2026 at matched fall:
    buy-and-hold 1x +16.1%/yr, fall 54% vs R3 (200-day + VIX curve) 2x +20.4%, fall 49%, worst month -19%; R1 2x +22.3%,
    fall 49%. 1999-2026 (the dot-com crash): hold 1x +10.6%, fall 83%; R1 2x +15.2%, fall 85% - the 200-day exit did NOT
    save a levered book from 2000-02 (S4 WRONG: 3x R1 +18.4%, fall 95%).
  - CORE (R3 2x) + the intraday NOISE book (2010-12..2026-09, daily correlation -0.09): +32.2%/yr, fall 33%, Sharpe 1.11,
    worst month -18%; with NOISE at 3x +37.8%, fall 36%. 2010-2026 was NASDAQ's best era; the core is NASDAQ itself
    (beta), only NOISE is an edge.
  - Needs: a swap-free account ON USTEC (the user's MT5 demo charges ~2.2bp a night on longs, 0 on shorts), and capital -
    the 0.05-lot minimum is ~$1,500 of NASDAQ: 2x needs ~$750, at $300 the smallest position is 5x.

    python -m backtest.ndx_swapfree
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.fx_anomalies import yf_daily  # noqa: E402

LOG = ROOT / "logs" / "ndx_swapfree.txt"
SPREAD, SWAP, REBAL = 0.77e-4, 2.04e-4, 0.1e-4
TUNE = 0.60


def stats(r: pd.Series):
    c = (1 + r).cumprod()
    yrs = (r.index[-1] - r.index[0]).days / 365.25
    cg = c.iloc[-1] ** (1 / yrs) - 1 if c.iloc[-1] > 0 else -1.0
    sh = r.mean() / r.std(ddof=1) * np.sqrt(252) if r.std(ddof=1) > 0 else 0.0
    mo = (1 + r).resample("ME").prod() - 1
    return cg, (1 - c / c.cummax()).max(), sh, mo.min(), r.min()


def book(pos: pd.Series, ret: pd.Series, nights: pd.Series, lev: float, swap: bool):
    p = pos.fillna(0.0) * lev
    turn = p.diff().abs().fillna(p.abs())
    r = p * ret - turn * SPREAD / 2 - (p.abs() * REBAL if lev > 1 else 0.0)
    if swap:
        r = r - p.clip(lower=0) * nights * SWAP
    return r.clip(lower=-1.0)


def main():
    nd = yf_daily("^NDX", start="1999-01-01").Close
    vix = yf_daily("^VIX", start="1990-01-01").Close
    v3 = yf_daily("^VIX3M", start="2006-01-01").Close
    nd = nd[nd.index >= "1999-01-04"]
    ret = nd.pct_change().fillna(0.0)
    nights = pd.Series(nd.index.to_series().diff().dt.days.fillna(1).to_numpy(), index=nd.index)
    above = (nd > nd.rolling(200).mean()).astype(float)
    calm = (vix.reindex(nd.index).ffill() < v3.reindex(nd.index).ffill()).astype(float).where(v3.reindex(nd.index).ffill().notna())
    pos = {"R0 buy and hold": pd.Series(1.0, index=nd.index),
           "R1 above the 200-day": above.shift(1),
           "R2 VIX below VIX3M": calm.shift(1),
           "R3 both": (above * calm).shift(1)}
    L = [f"backtest/ndx_swapfree.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; ^NDX daily {nd.index[0]:%Y-%m-%d}..{nd.index[-1]:%Y-%m-%d}; "
         f"first 60% of days = tune", ""]
    res = {}
    for span, start in (("1999-2026 (R2 / R3 start when VIX3M does, 2006-07)", "1999-01-04"), ("2006-07 on (all four comparable)", "2006-07-20")):
        L += [span, f"   {'rule':<24}{'lev':>4}{'swap':>6}{'CAGR':>8}{'fall':>6}{'Sharpe':>7}{'worst mo':>9}{'worst day':>10}"
                    f"{'tune Sh':>8}{'hold Sh':>8}{'in mkt':>7}"]
        for lab, p in pos.items():
            m = p.index >= start
            pp = p[m]
            if pp.isna().all():
                continue
            first = pp.first_valid_index()
            for lev in (1, 2, 3):
                for sw in (False, True):
                    r = book(pp[first:], ret[m][first:], nights[m][first:], lev, sw)
                    cg, dd, sh, wm, wd = stats(r)
                    cut = int(len(r) * TUNE)
                    a, b = r.iloc[:cut], r.iloc[cut:]
                    sa = a.mean() / a.std() * np.sqrt(252)
                    sb = b.mean() / b.std() * np.sqrt(252)
                    res[(span, lab, lev, sw)] = dict(cg=cg, dd=dd, sh=sh, sa=sa, sb=sb)
                    L.append(f"   {lab:<24}{lev:>3}x{'yes' if sw else 'free':>6}{cg * 100:>+7.1f}%{dd * 100:>5.0f}%{sh:>7.2f}"
                             f"{wm * 100:>+8.1f}%{wd * 100:>+9.1f}%{sa:>8.2f}{sb:>8.2f}{(pp[first:] > 0).mean() * 100:>6.0f}%")
        L.append("")
    # overnight, minutes
    from backtest.fx_intraday_pub import session
    A, dates, prev = session("NASDAQ")
    on = pd.Series(A["o"][1:, 0] / A["c"][:-1, -1] - 1, index=dates[1:])
    gap_n = pd.Series((dates[1:] - dates[:-1]).days, index=dates[1:])
    on_net = on - SPREAD - 0.5e-4
    cut = int(len(on_net) * TUNE)
    t = lambda x: x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))  # noqa: E731
    L += ["OVERNIGHT, NASDAQ 16:00 -> 09:30 (HistData minutes; net of 0.77 + 0.5bp, swap-free)",
          f"   gross {on.mean() * 1e4:+.2f}bp a night, net {on_net.mean() * 1e4:+.2f}bp t {t(on_net):+.2f} | tune {on_net.iloc[:cut].mean() * 1e4:+.2f} "
          f"t {t(on_net.iloc[:cut]):+.2f} | hold {on_net.iloc[cut:].mean() * 1e4:+.2f} t {t(on_net.iloc[cut:]):+.2f}; with swap "
          f"{(on_net - gap_n * SWAP).mean() * 1e4:+.2f}bp", ""]
    # the swap-free core with the intraday NOISE book beside it (noise_book.py's series), 2010-11 on
    from backtest.fx_intraday_pub import INSTR, SLIP, noise
    g, _, n = noise(A, prev)
    nz = pd.Series(g - (INSTR["NASDAQ"][4] + SLIP) / 1e4 * n, index=dates)
    core = book(pos["R3 both"], ret, nights, 2, False)
    j = pd.DataFrame({"core": core, "noise": nz}).dropna()
    j = j[j.index >= nz.index[15]]
    L += [f"CORE (R3 at 2x, swap-free) + NOISE (intraday), {j.index[0]:%Y-%m-%d}..{j.index[-1]:%Y-%m-%d}; daily correlation "
          f"{j.core.corr(j.noise):+.2f}", f"   {'book':<34}{'CAGR':>8}{'fall':>6}{'Sharpe':>7}{'worst mo':>9}{'worst day':>10}"]
    for lab, r in (("core 2x", j.core), ("NOISE 2x", 2 * j.noise), ("core 2x + NOISE 2x", j.core + 2 * j.noise),
                   ("core 2x + NOISE 3x", j.core + 3 * j.noise)):
        cg, dd, sh, wm, wd = stats(r)
        L.append(f"   {lab:<34}{cg * 100:>+7.1f}%{dd * 100:>5.0f}%{sh:>7.2f}{wm * 100:>+8.1f}%{wd * 100:>+9.1f}%")
    L.append("")
    k = "2006-07 on (all four comparable)"
    s2 = (res[(span, "R1 above the 200-day", 1, False)]["sa"] > res[(span, "R0 buy and hold", 1, False)]["sa"]
          for span in [k])
    r0, r1 = res[("1999-2026 (R2 / R3 start when VIX3M does, 2006-07)", "R0 buy and hold", 1, False)], res[("1999-2026 (R2 / R3 start when VIX3M does, 2006-07)", "R1 above the 200-day", 1, False)]
    s2 = r1["sa"] > r0["sa"] and r1["sb"] > r0["sb"] and r1["dd"] <= 0.6 * r0["dd"]
    q = {lab: res[(k, lab, 1, False)] for lab in pos}
    s3 = (q["R2 VIX below VIX3M"]["sa"] > q["R0 buy and hold"]["sa"] and q["R2 VIX below VIX3M"]["sb"] > q["R0 buy and hold"]["sb"]
          and q["R3 both"]["sh"] >= max(q["R1 above the 200-day"]["sh"], q["R2 VIX below VIX3M"]["sh"]))
    b3f, b3s = res[(k, "R0 buy and hold", 3, False)], res[(k, "R0 buy and hold", 3, True)]
    r13 = res[("1999-2026 (R2 / R3 start when VIX3M does, 2006-07)", "R1 above the 200-day", 3, False)]
    s4 = (b3f["cg"] - b3s["cg"] >= 0.12) and r13["cg"] >= 0.25 and r13["dd"] <= 0.60
    s1 = t(on_net) >= 2 and on_net.iloc[:cut].mean() > 0 and on_net.iloc[cut:].mean() > 0
    L += ["REGISTERED PREDICTIONS",
          f"  S1 overnight swap-free t >= 2, both halves positive -> {'RIGHT' if s1 else 'WRONG'}",
          f"  S2 R1 beats buy-and-hold Sharpe on both halves, fall <= 60% of hold's (1999-2026, 1x) -> {'RIGHT' if s2 else 'WRONG'}",
          f"  S3 R2 beats hold on both halves and R3 has the best Sharpe (2006 on, 1x) -> {'RIGHT' if s3 else 'WRONG'}",
          f"  S4 swap costs 3x hold >= 12 points a year; swap-free 3x R1 >= +25%/yr with fall <= 60% -> {'RIGHT' if s4 else 'WRONG'} "
          f"(swap cost {(b3f['cg'] - b3s['cg']) * 100:.1f} pts; 3x R1 {r13['cg'] * 100:+.1f}%, fall {r13['dd'] * 100:.0f}%)"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

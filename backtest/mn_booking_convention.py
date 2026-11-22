"""DOES THE LIVE PAPER BOOK THE MARKET-NEUTRAL BASKET THE WAY THE BACKTEST DID? - buy-and-hold vs "re-struck at every daily mark" on the same weekly baskets (2026-11-06)

Found while reading the AKE short on 2026-11-06 (CLAUDE.md s10, 'check the dashboard'): the fresh account's market-neutral AKE short was struck 10-31 at 0.013907 and the price is -64% since, which a
fixed-coin short books as +$6.57 - yet the account has booked about +$2.48 on it. The reason is in the code: `combo_paper.py` line ~278 books each day `base x w x (close / previous daily mark - 1)` and then
moves the mark (line ~322), i.e. every day the position is re-struck at the SAME dollar weight (daily rebalancing, a constant-notional book). `backtest/mn_combos.mn_run` (the backtest every MN figure rests on) books the week
as `0.5 x mean(close[i + 7] / close[i] - 1)` per leg: BUY-AND-HOLD, fixed coins - which is also what the bot's real-order ledger (`exec.mn_qty`: coins fixed at the rebalance) would hold. Two conventions for one basket.

THE QUESTION. On the SAME weekly baskets (mn_run's own selection, 30-day return, top / bottom 10%, all 7 start days), how far apart are the two, on average and week by week, and does it have a sign? If the live convention is
systematically worse, the forward test's verdict (day-45 line, doc 22) is read on a harsher book than the one that was backtested; if it is only noise, today's gap was path luck.
Gross price return only: funding and the weekly fee are identical in both. The daily convention here charges NO cost for its daily re-striking (the live paper does not either), which a real constant-notional book would pay.

CHECK: with the buy-and-hold booking this file's weekly net must equal `mn_run(start=s)` exactly for every start day (asserted).

REGISTERED BEFORE THE FIRST RUN (2026-11-06)
    K1  The conventions are not systematically different: the mean weekly gap (daily-reset minus buy-and-hold, gross) is under 0.15 percentage points in absolute value on every one of the 7 start days (prior 50%).
    K2  They disagree a lot week by week: the standard deviation of the weekly gap is above 1.5 percentage points (prior 65%).
    K3  If there is a sign, the daily-reset convention is the LOWER one (it re-buys losers and re-sells winners inside the week, a contrarian overlay on a momentum basket) (prior 60%).
    K4  Both conventions give a positive Sharpe on the full history; their Sharpe ratios differ by under 0.25 (prior 55%).

RESULT (2026-11-06, logs/mn_booking_convention.txt; 337 weekly baskets x 7 start days, 2020-2026, the PIT top-60)
    The two bookings of the SAME basket disagree a lot week by week and agree on average. CHECK passed: the buy-and-hold booking reproduces mn_run(start=s) exactly on all 7 start days. Daily-reset minus buy-and-hold, gross: mean -0.126 percentage points a week (per start day -0.37..+0.03,
    t -1.5..+0.2: none significant; negative on 5 of 7 days), standard deviation 3.49 points a week, 25% of weeks differ by more than 1 point, correlation 0.915. Sharpe (start day 0) 1.21 buy-and-hold vs 1.26 daily-reset; the daily-reset Sharpe is higher on 6 of 7 start days.
    By half -0.073 (tune) / -0.213 (holdout); by year 2021 -0.44, 2025 -0.70, 2026 +0.25 (2026 so far: buy-and-hold +1.94, daily-reset +2.19 gross %/wk). The tails: the 2025-09 MYX squeeze weeks, 2025-09-10 -71.5 points and 2025-09-12 +55.1 - in a squeeze the two conventions disagree by dozens of points.
    LIVE, fresh's basket struck 2026-10-31 (price only, funding and fees identical; state file + Binance daily closes): MN re-struck daily -$1.97 vs fixed coins +$3.40; carry -$3.29 vs +$0.71; together -$5.26 vs +$4.11 = $9.37 of fresh's -$90 since the start (AKE short alone: +$3.41 vs +$6.71). Main's baskets were struck today: no gap yet.
    Predictions: K1 wrong (the largest start-day mean gap is 0.367, not under 0.15, though none is significant), K2 right (3.49), K3 right on the sign and not significant, K4 right.
    LIMITS: the pure momentum MN (mn_run), not the final machine's momentum / RSI blend, and not the funding-ranked carry book (mn_run's score="funding7" would test it); the daily convention is charged no cost for its daily re-striking (a real constant-notional book would pay it); earlier live baskets were not reconstructed (their weights are not stored).
    Tests: 5; 18 of 18 planted bugs caught.

    python -m backtest.mn_booking_convention        writes logs/mn_booking_convention.txt        tests: python tests/test_mn_booking_convention.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, ROOT.as_posix())

LOOK, HOLD, FRAC = 30, 7, 0.1


def basket_gap(R, ff, X, i, hold, lo, sh):
    """One weekly basket entered at row i: (buy-and-hold gross, daily-reset gross, long-leg gap, short-leg gap).
    buy-and-hold = fixed coins: 0.5 x mean(close[i+hold] / close[i] - 1) per leg (mn_run's own booking);
    daily-reset  = constant notional re-struck at every daily mark: the sum of the days' simple returns (combo_paper's booking)."""
    fwd = ff[i + hold] / X[i] - 1
    dly = np.nansum(R[i + 1:i + hold + 1], axis=0)
    bh = 0.5 * fwd[lo].mean() - 0.5 * fwd[sh].mean()
    dr = 0.5 * dly[lo].mean() - 0.5 * dly[sh].mean()
    return bh, dr, 0.5 * (dly[lo].mean() - fwd[lo].mean()), -0.5 * (dly[sh].mean() - fwd[sh].mean())


def weeks(start=0, look=LOOK, hold=HOLD, frac=FRAC):
    """mn_run's weekly baskets (score 'ret', no regime / cap / stop) booked both ways. One row per rebalance: booking date, gross each way, the legs' gaps, carry, cost."""
    from backtest.bear_chop import FEE
    from backtest.market_neutral import MIN_AGE_D
    from backtest.mn_combos import data
    D = data()
    idx, X, Fx, ff, R = D["idx"], D["X"], D["Fx"], D["ff"], D["R"]
    rows, pl_, ps_ = [], set(), set()
    for i in range(look + 1 + start, len(idx) - hold - 1, hold):
        t0 = idx[i]
        ok = (D["Em"][D["months"][i]] & ((t0.value - D["fv"]) // 86_400_000_000_000 >= MIN_AGE_D)
              & np.isfinite(X[i]) & np.isfinite(X[i - look]))
        if ok.sum() < 20:
            continue
        cand = np.flatnonzero(ok)
        past = X[i, cand] / X[i - look, cand] - 1
        k = max(int(len(cand) * frac), 3)
        order = cand[np.argsort(np.where(np.isnan(past), np.inf, past), kind="stable")]
        sh, lo = order[:k], order[-k:]
        bh, dr, glo, gsh = basket_gap(R, ff, X, i, hold, lo, sh)
        fnd = Fx[i + 1:i + hold + 1].sum(axis=0)
        carry = 0.5 * (-fnd[lo].mean()) + 0.5 * fnd[sh].mean()
        L_, S_ = {D["cols"][x] for x in lo}, {D["cols"][x] for x in sh}
        cost = FEE * min((len(L_ ^ pl_) + len(S_ ^ ps_)) / (4 * k), 1.0)
        pl_, ps_ = L_, S_
        rows.append((t0 + pd.Timedelta(days=hold), bh, dr, glo, gsh, carry, cost))
    df = pd.DataFrame(rows, columns=["date", "bh", "dr", "long_gap", "short_gap", "carry", "cost"]).groupby("date").sum()
    df["net_bh"] = df.bh + df.carry - df.cost
    df["net_dr"] = df.dr + df.carry - df.cost
    df["gap"] = df.dr - df.bh
    return df


def sharpe(x):
    x = np.asarray(x, float)
    return float(x.mean() / x.std(ddof=1) * np.sqrt(52)) if len(x) > 2 and x.std(ddof=1) > 0 else float("nan")


def tstat(x):
    x = np.asarray(x, float)
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 else float("nan")


def main():
    from backtest.mn_combos import HOLDOUT, mn_run
    out = [f"backtest/mn_booking_convention.py - MN weekly baskets (30-day return, top / bottom {FRAC:.0%}), booked buy-and-hold (the backtest) and re-struck daily (the live paper), gross price return, all 7 start days", ""]
    per = {}
    for s in range(7):
        w = weeks(start=s)
        ref = mn_run(start=s)
        common = w.index.intersection(ref.index)
        gap = float((w.net_bh.reindex(common) - ref.reindex(common)).abs().max())
        assert len(common) == len(ref) == len(w) and gap < 1e-9, f"start {s}: not mn_run ({len(common)} / {len(ref)} / {len(w)} weeks, max gap {gap:.2e})"
        per[s] = w
    out.append(f"CHECK: the buy-and-hold booking reproduces mn_run(start=s) exactly on all 7 start days ({len(per[0])} weeks each)")
    out.append("\nTHE GAP, daily-reset minus buy-and-hold, gross, percentage points per week (t per start day: its weeks do not overlap)")
    out.append(f"   {'start':>5}{'weeks':>7}{'mean gap':>10}{'t':>7}{'sd of gap':>11}{'|gap|>1pt':>11}{'corr':>7}{'long leg':>10}{'short leg':>10}{'Sharpe bh':>11}{'Sharpe dr':>11}")
    allgap = []
    for s, w in per.items():
        allgap.append(w.gap.mean())
        out.append(f"   {s:>5}{len(w):>7}{w.gap.mean() * 100:>+10.3f}{tstat(w.gap):>+7.1f}{w.gap.std() * 100:>11.2f}{(w.gap.abs() > 0.01).mean() * 100:>10.0f}%{np.corrcoef(w.bh, w.dr)[0, 1]:>7.3f}"
                   f"{w.long_gap.mean() * 100:>+10.3f}{w.short_gap.mean() * 100:>+10.3f}{sharpe(w.net_bh):>+11.2f}{sharpe(w.net_dr):>+11.2f}")
    avg = pd.concat(per.values())
    out.append(f"   {'all':>5}{len(avg):>7}{avg.gap.mean() * 100:>+10.3f}{'':>7}{avg.gap.std() * 100:>11.2f}{(avg.gap.abs() > 0.01).mean() * 100:>10.0f}%{np.corrcoef(avg.bh, avg.dr)[0, 1]:>7.3f}"
               f"{avg.long_gap.mean() * 100:>+10.3f}{avg.short_gap.mean() * 100:>+10.3f}{sharpe(per[0].net_bh):>+11.2f}{sharpe(per[0].net_dr):>+11.2f}   (Sharpe: start day 0)")
    out.append("\nBY HALF (booking date; tune before the holdout) and BY YEAR, mean gap in percentage points per week, averaged over the 7 start days")
    for nm, m in (("tune", avg.index < HOLDOUT), ("holdout", avg.index >= HOLDOUT)):
        out.append(f"   {nm:<8} n {int(m.sum()):>5}  mean gap {avg.gap[m].mean() * 100:>+7.3f}  mean buy-and-hold {avg.bh[m].mean() * 100:>+7.3f}  mean daily-reset {avg.dr[m].mean() * 100:>+7.3f}")
    yr = avg.groupby(avg.index.year)
    out.append("   " + "  ".join(f"{y}: {g.gap.mean() * 100:+.2f}" for y, g in yr))
    out.append("   weekly net return, mean %/wk, buy-and-hold vs daily-reset by year: " + "  ".join(f"{y}: {g.net_bh.mean() * 100:+.2f}/{g.net_dr.mean() * 100:+.2f}" for y, g in yr))
    worst = avg.gap.nsmallest(4)
    best = avg.gap.nlargest(4)
    out.append("   the four weeks where daily-reset lost most to buy-and-hold: " + ", ".join(f"{d:%Y-%m-%d} {v * 100:+.1f}" for d, v in worst.items()))
    out.append("   the four weeks where it gained most:                     " + ", ".join(f"{d:%Y-%m-%d} {v * 100:+.1f}" for d, v in best.items()))
    recent = avg[avg.index >= "2026-01-01"]
    out.append(f"   2026 so far ({len(recent) // 7} weeks x 7 start days): mean gap {recent.gap.mean() * 100:+.3f}  buy-and-hold {recent.bh.mean() * 100:+.3f}  daily-reset {recent.dr.mean() * 100:+.3f} (gross %/wk)")
    out.append(f"\nSCORING: K1 mean gap under 0.15 on every start day: {all(abs(g) < 0.0015 for g in allgap)} (largest {max(abs(g) for g in allgap) * 100:.3f}); K2 sd above 1.5: {avg.gap.std() > 0.015} ({avg.gap.std() * 100:.2f}); "
               f"K3 sign negative: {avg.gap.mean() < 0} ({avg.gap.mean() * 100:+.3f}); K4 both Sharpe positive and within 0.25: "
               f"{sharpe(per[0].net_bh) > 0 and sharpe(per[0].net_dr) > 0 and abs(sharpe(per[0].net_bh) - sharpe(per[0].net_dr)) < 0.25}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "mn_booking_convention.txt").write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

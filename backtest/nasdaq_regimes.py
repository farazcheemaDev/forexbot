"""NASDAQ, mechanism first: (1) WHEN does the noise rule work - the dealer-gamma regime; (2) is there a closing-hour flow from leveraged ETFs? (2026-11-03)

The user, 2026-11-03: "analyse how many strategies ... start testing ... a full-proof strategy ... think outside the box". The honest frame: nothing is fool-proof; what can be demanded is a fixed admission bar (a mechanism written down first,
positive on both halves with t >= 2 after costs and Holm, survives double costs, a low correlation with what is already in, then a forward record). These are the first two candidates under that bar.

PART 1 - REGIME-CONDITIONED NOISE. Mechanism: when dealers are SHORT gamma (stress, volatility curve inverted, wild tape) they trade WITH the move and trends extend - a momentum rule should earn there; when they are LONG gamma
they trade against the move and breakouts fail. noise_attack.py found that all of NOISE's profit sits on days VXN closed above its 1-year median (+2.21 bp, t +3.24, on 49% of days; the other days +0.03) - but found AFTER looking. So
the proxies here are fixed in advance and two of them are different from VXN:
    P1  the volatility curve is INVERTED at the previous close (VIX > VIX3M)                                     [2006-07 on]
    P2  VXN at the previous close above its trailing 252-day median (the post-hoc one; NOT independent evidence) [2009 on]
    P3  the previous session's NASDAQ range (high-low)/close above its trailing 60-session median               [from the same minute bars]
The rule, costs and sessions are exactly fx_intraday_pub.noise() (HistData NASDAQ minute bars 2010-11..2026-09, 0.77 bp spread + 0.5 bp slippage per entered trade). Reported: the net bp/day on regime days vs the other days, t,
tune (first 60% of sessions) / holdout, and the Sharpe of trading ONLY the regime days (zeros elsewhere).
PART 2 - THE CLOSING HOUR. Mechanism: leveraged ETFs must rebalance in the last hour in the direction of the day's move (up days: buy; down days: sell), in proportion to the day's return; so a large move through 15:30 should continue
into the 16:00 close. Rule: at 15:30 go WITH the day's move if it is beyond k x the trailing 14-session mean absolute day return (k = 0.5, 1.0, 1.5), exit at the close; entry at the next minute's open.

REGISTERED BEFORE THE FIRST RUN (2026-11-03)
    R1  The two new proxies P1 and P3 do NOT both confirm P2: at most one of them has regime-day profit with t >= 2 on both halves AND off-day profit near zero. (I expect the VXN result to be partly a post-hoc echo.)
    R2  P1 (curve inversion) is rare (< 20% of sessions), so even if it works it cannot carry the book alone.
    R3  Trading only the P2 days has a higher Sharpe than all days (it is how it was found), but no proxy lifts the Sharpe above 1.0.
    R4  Part 2: no k has a positive net expectancy with t >= 2.4 on BOTH halves (Holm over 3).

RESULT (2026-11-03; logs/nasdaq_regimes.txt; 3,686 sessions 2010-11..2026-09; all days +2.25 bp/day, Sharpe 0.74)
    PART 1. P1 VIX > VIX3M: 7% of sessions, on-days +9.98 bp (t +1.7), off +1.65 (t +2.3); tune +9.68 (t 1.6), holdout +10.60 (t 0.9); Sharpe of trading only those days 0.45. P2 VXN > 1y median: 49%, on +4.54 (t +3.2), off +0.07;
    tune +4.40 (t 2.7), holdout +4.73 (t 1.9); Sharpe on-only 0.85 (the post-hoc one: it replicates, and the holdout t is a hair under 2). P3 range > 60-session median: 49%, on +3.01 (t 2.2), off +1.50 (t 1.7); tune +4.09
    (t 2.5), holdout +1.44 (t 0.6); Sharpe 0.58. NO proxy has on-day profit t >= 2 on both halves with off-day profit near zero. R1 RIGHT (neither independent proxy confirms VXN), R2 RIGHT (P1 is 7% of days), R3 RIGHT.
    PART 2 (closing hour, with the day's move at 15:30): continuation is there before costs and gone after them - gross +1.07 / +0.91 / +0.77 bp a trade at k = 0.5 / 1.0 / 1.5 (170 / 103 / 61 trades a year), net -0.20 / -0.36 / -0.50
    (t -0.3 / -0.4 / -0.4), reversing the rule loses 2.0-2.3 bp. R4 RIGHT.
    Reading: 'NOISE earns mostly in stressed markets' keeps its direction on three proxies (on-days +3 to +10 bp vs off-days +0 to +1.7) but no proxy is confirmed strongly enough to GATE trades; the right use is a SHADOW
    arm in the bot (log the flags, judge them forward). The leveraged-ETF closing-hour flow is real but smaller than the cost of trading it.

    python -m backtest.nasdaq_regimes        writes logs/nasdaq_regimes.txt          tests: python tests/test_nasdaq_regimes.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.fx_intraday_pub import INSTR, SLIP, TUNE, noise, session  # noqa: E402

KS = (0.5, 1.0, 1.5)
CLOSE_MIN = 360                                     # 15:30 New York = minute 360 of the session


def tstat(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std() > 0 else 0.0


def prior_value(series: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    """The latest value of `series` strictly BEFORE each session date (previous close): shift by one observation, then carry forward to the session calendar."""
    return series.shift(1).reindex(pd.DatetimeIndex(dates).normalize(), method="ffill")


def regimes(dates, A, vix, vix3m, vxn):
    """Boolean Series (index = session dates) for P1, P2, P3. Everything is known at the previous close."""
    idx = pd.DatetimeIndex(dates).normalize()

    def flag(raw: pd.Series, needs: pd.Series) -> pd.Series:
        """1.0 / 0.0 from the previous close, NaN where the history the flag needs does not exist yet."""
        return prior_value(raw.astype(float), dates).where(prior_value(needs, dates).notna())

    v3 = vix3m.reindex(vix.index)
    med = vxn.rolling(252).median()
    rng = pd.Series((A["h"].max(axis=1) - A["l"].min(axis=1)) / A["c"][:, -1], index=idx)
    rmed = rng.rolling(60).median()
    p3 = (rng > rmed).astype(float).shift(1).where(rmed.shift(1).notna())
    return {"P1 VIX > VIX3M": flag(vix > v3, v3), "P2 VXN > 1y median": flag(vxn > med, med), "P3 range > 60d median": p3}


def summarize(net: np.ndarray, flag: np.ndarray, cut: int):
    """On-regime vs off-regime: means (bp), t, tune / holdout on-regime mean and t, share of days, and the Sharpe of trading only the on-days."""
    ok = ~np.isnan(flag.astype(float))
    on, off = ok & (flag == True), ok & (flag == False)  # noqa: E712
    idx = np.arange(len(net))
    a, b = on & (idx < cut), on & (idx >= cut)
    only = np.where(on, net, 0.0)
    return dict(share=on.sum() / max(ok.sum(), 1), on=net[on].mean() * 1e4, ton=tstat(net[on]), off=net[off].mean() * 1e4, toff=tstat(net[off]),
                tune=net[a].mean() * 1e4, ttune=tstat(net[a]), hold=net[b].mean() * 1e4, thold=tstat(net[b]),
                sharpe=only[ok].mean() / only[ok].std(ddof=1) * np.sqrt(252) if only[ok].std() > 0 else 0.0,
                sharpe_all=net[ok].mean() / net[ok].std(ddof=1) * np.sqrt(252))


def close_flow(A, prev, k, look=14, cost=None):
    """Part 2. Returns (net per session, trades per session): with the day's move through 15:30 beyond k x its trailing mean absolute value, go WITH it until the close."""
    O, C = A["o"], A["c"]
    day = C[:, CLOSE_MIN - 1] / O[:, 0] - 1
    sig = pd.Series(np.abs(day)).rolling(look).mean().shift(1).to_numpy()
    side = np.where(day > k * sig, 1.0, np.where(day < -k * sig, -1.0, 0.0))
    side[~np.isfinite(sig)] = 0.0
    gross = side * (C[:, -1] / O[:, CLOSE_MIN] - 1)
    c = cost if cost is not None else (INSTR["NASDAQ"][4] + SLIP) / 1e4
    return gross - c * np.abs(side), np.abs(side)


def main():
    from backtest.fx_anomalies import yf_daily
    A, dates, prev = session("NASDAQ")
    cost = (INSTR["NASDAQ"][4] + SLIP) / 1e4
    g, _, nt = noise(A, prev)
    net = g - cost * nt
    cut = int(len(dates) * TUNE)
    vix, v3, vxn = yf_daily("^VIX").Close, yf_daily("^VIX3M").Close, yf_daily("^VXN").Close
    R = regimes(dates, A, vix, v3, vxn)
    out = [f"backtest/nasdaq_regimes.py - NASDAQ noise rule, {len(dates)} sessions {dates[0]:%Y-%m}..{dates[-1]:%Y-%m}; net of {(INSTR['NASDAQ'][4] + SLIP):.2f} bp per entered trade; tune = first {cut} sessions",
           f"\nPART 1 - NOISE BY REGIME (regime values are the PREVIOUS close's). All days: {net.mean() * 1e4:+.2f} bp/day (t {tstat(net):+.2f}), Sharpe {net.mean() / net.std(ddof=1) * np.sqrt(252):.2f}",
           f"   {'regime':<24}{'days on':>8}{'on bp/day':>10}{'t':>6}{'off bp/day':>11}{'t':>6}{'tune on':>9}{'t':>6}{'hold on':>9}{'t':>6}{'Sharpe on-only':>15}{'Sharpe all':>11}"]
    S = {}
    for name, flag in R.items():
        s = summarize(net, flag.to_numpy(dtype=float), cut)
        S[name] = s
        out.append(f"   {name:<24}{s['share'] * 100:>7.0f}%{s['on']:>+10.2f}{s['ton']:>+6.1f}{s['off']:>+11.2f}{s['toff']:>+6.1f}{s['tune']:>+9.2f}{s['ttune']:>+6.1f}{s['hold']:>+9.2f}{s['thold']:>+6.1f}{s['sharpe']:>15.2f}{s['sharpe_all']:>11.2f}")
    conf = [n for n, s in S.items() if s["on"] > 0 and s["ttune"] >= 2 and s["thold"] >= 2 and abs(s["off"]) < 0.5]
    out.append(f"   proxies with regime-day profit t >= 2 on BOTH halves and off-day profit near zero: {conf}")
    out.append("\nPART 2 - CLOSING HOUR (go with the day's move at 15:30, out at the close):")
    out.append(f"   {'k':>5}{'trades/yr':>10}{'gross bp':>9}{'net bp/trade':>13}{'t':>6}{'tune':>8}{'t':>6}{'hold':>8}{'t':>6}{'net if reversed':>16}")
    P2 = {}
    for k in KS:
        n_, tr = close_flow(A, prev, k)
        m = tr > 0
        if m.sum() < 30:
            continue
        x = n_[m]
        idx = np.flatnonzero(m)
        gtr = x.mean() + cost
        rev = (-(x + cost)) - cost
        P2[k] = dict(ev=x.mean() * 1e4, t=tstat(x), tune=x[idx < cut].mean() * 1e4, tt=tstat(x[idx < cut]), hold=x[idx >= cut].mean() * 1e4, th=tstat(x[idx >= cut]))
        out.append(f"   {k:>5.1f}{m.sum() / (len(dates) / 252):>10.0f}{gtr * 1e4:>+9.2f}{x.mean() * 1e4:>+13.2f}{tstat(x):>+6.1f}{P2[k]['tune']:>+8.2f}{P2[k]['tt']:>+6.1f}{P2[k]['hold']:>+8.2f}{P2[k]['th']:>+6.1f}{rev.mean() * 1e4:>+16.2f}")
    pos = [k for k, v in P2.items() if v["ev"] > 0 and v["tt"] >= 2.4 and v["th"] >= 2.4]
    out.append(f"   k with a positive net expectancy and t >= 2.4 on both halves: {pos}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "nasdaq_regimes.txt").write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

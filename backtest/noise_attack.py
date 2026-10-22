"""TRYING TO BREAK NOISE ON NASDAQ - the one near-pass of the published intraday rules (2026-10-22)

fx_intraday_pub.py: NOISE (Zarattini, Aziz & Barbon 2024) on NASDAQ, HistData NSXUSD 2010-11..2026-09, 3,686 days: +2.25bp
a day net of 1.27bp a trade, t +2.83 (tune +1.99 / holdout +2.01), Sharpe 0.74 at 1x, 13 of 17 years positive - a hundredth
of a t under the pass line on the tune half. A borderline result is a bug or luck until shown otherwise:
  A1 DECISION PHASE   decisions at :00/:30 shifted by 0, 5, 10, 15, 20, 25 minutes (the bar-phase test)
  A2 LOOKBACK         sigma over 7 / 10 / 14 / 20 / 30 days
  A3 COSTS x2         2.54bp a round trip
  A4 LATE FILL        filled 1 (base) / 2 / 5 minutes after the decision
  A5 THE BROKER       the same rule on Exness's own USTECm minute bars (mt5_1m.py, 2026) at Exness's measured cash-session
                      spread; daily correlation with HistData's 2026 days
  A6 LEGS             longs only / shorts only
  A7 NOT JUST DRIFT   NOISE's daily net regressed on the session's own return (CONTROL): alpha and its t
  A8 HIS HELP         no new entries after 12:00 New York (his sittings are the New York morning, his_plain.py); trading only
                      on days when VXN closed above its trailing 1-year median (he leans to trending, negative-gamma days,
                      his_gex.py)
REGISTERED BEFORE THE RUN (2026-10-22)
  N1 positive in all 6 decision phases, t >= 2 overall in at least 4.
  N2 positive at every lookback.
  N3 at costs x2 still positive, t < 2.
  N4 the 5-minute late fill keeps at least half the edge.
  N5 Exness 2026 days correlate >= 0.8 with HistData's.
  N6 both legs positive.
  N7 alpha over the session drift positive with t >= 2.
  N8 the morning-only and the high-VXN versions each earn less over the whole period than the base.

RESULT (2026-10-22, logs/noise_attack.txt) - it held every attack except double costs. N1-N8 all RIGHT.
  All 6 decision phases positive, t >= 2 overall in 6 of 6 (+1.69..+2.37bp); every lookback 7..30 days positive (+1.65..+2.39);
  a 5-minute late fill keeps +2.18bp; Exness's own USTECm bars in 2026 +3.14bp a day vs HistData's +1.68 on the same 155 days
  (daily correlation +0.93); alpha over the session drift +2.37bp t +2.99. Weak spots: costs x2 (2.54bp) leave +1.20bp t
  +1.50; the short leg alone t +1.30; ALL of it comes on days VXN closed above its 1-year median (+2.21bp t +3.24 on 49% of
  days, the low-VXN days +0.03bp) - his lean to wild days (his_gex.py) points the same way, found after looking. Morning-only
  (his sittings) keeps +1.34bp but the holdout fades to +0.47.

    python -m backtest.noise_attack
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.fx_intraday_pub import INSTR, SLIP, TUNE, noise, session, session_df, tstat  # noqa: E402

LOG = ROOT / "logs" / "noise_attack.txt"


def summ(net, cut):
    a, b = net[:cut], net[cut:]
    sh = net.mean() / net.std(ddof=1) * np.sqrt(252) if net.std() > 0 else 0.0
    return (f"{net.mean() * 1e4:>+7.2f}bp t {tstat(net):>+5.2f} | tune {a.mean() * 1e4:>+6.2f} t {tstat(a):>+5.2f} | "
            f"hold {b.mean() * 1e4:>+6.2f} t {tstat(b):>+5.2f} | Sharpe {sh:4.2f}")


def main():
    A, dates, prev = session("NASDAQ")
    cut = int(len(dates) * TUNE)
    cost = (INSTR["NASDAQ"][4] + SLIP) / 1e4
    net = lambda g, n, c=cost: g - c * n  # noqa: E731
    g0, gl0, n0 = noise(A, prev)
    base = net(g0, n0)
    L = [f"backtest/noise_attack.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; NASDAQ HistData {dates[0]:%Y-%m-%d}..{dates[-1]:%Y-%m-%d}, "
         f"{len(dates)} days; net a day, cost {cost * 1e4:.2f}bp a round trip", "", f"   base            {summ(base, cut)}", "",
         "A1 DECISION PHASE (minutes added to :00 / :30)"]
    ph = {}
    for p in (0, 5, 10, 15, 20, 25):
        g, _, n = noise(A, prev, phase=p)
        ph[p] = net(g, n)
        L.append(f"   +{p:>2} min        {summ(ph[p], cut)}")
    L += ["", "A2 LOOKBACK (days in sigma)"]
    lk = {}
    for k in (7, 10, 14, 20, 30):
        g, _, n = noise(A, prev, look=k)
        lk[k] = net(g, n)
        L.append(f"   {k:>2} days        {summ(lk[k], cut)}")
    c2 = net(g0, n0, 2 * cost)
    L += ["", "A3 COSTS x2", f"   {2 * cost * 1e4:.2f}bp        {summ(c2, cut)}", "", "A4 LATE FILL (minutes after the decision)"]
    lf = {}
    for dl in (1, 2, 5):
        g, _, n = noise(A, prev, delay=dl)
        lf[dl] = net(g, n)
        L.append(f"   {dl} min          {summ(lf[dl], cut)}")

    # A5 the broker
    from backtest.mt5_1m import load
    E = load("USTECm")
    Ae, de, pe = session_df(E, "NASDAQ")
    lt = pd.to_datetime(E.t, unit="ms").dt.tz_localize("UTC").dt.tz_convert("America/New_York")
    cash = ((lt.dt.hour * 60 + lt.dt.minute >= 570) & (lt.dt.hour < 16)).to_numpy()
    sp_bp = float(np.median(E.sp.to_numpy()[cash] / E.c.to_numpy()[cash])) * 1e4
    ge, _, ne = noise(Ae, pe)
    ce = (sp_bp + SLIP) / 1e4
    ex = pd.Series(ge - ce * ne, index=de)
    hd = pd.Series(base, index=dates)
    both = ex.index.intersection(hd.index)
    both = both[both >= de[15]]
    corr = np.corrcoef(ex[both], hd[both])[0, 1]
    L += ["", "A5 THE BROKER: Exness USTECm 1m bars (2026), its median cash-session spread "
          f"{sp_bp:.2f}bp a round trip (+{SLIP}bp)",
          f"   Exness {len(both)} days: {ex[both].mean() * 1e4:+.2f}bp a day (t {tstat(ex[both].to_numpy()):+.2f}); HistData same days "
          f"{hd[both].mean() * 1e4:+.2f}bp; daily correlation {corr:+.2f}"]

    gL, _, nL = noise(A, prev, side=1)
    gS, _, nS = noise(A, prev, side=-1)
    L += ["", "A6 LEGS", f"   longs only     {summ(net(gL, nL), cut)}", f"   shorts only    {summ(net(gS, nS), cut)}"]

    ctl = A["c"][:, -1] / A["o"][:, 0] - 1
    X = np.c_[np.ones(len(ctl)), ctl]
    beta, *_ = np.linalg.lstsq(X, base, rcond=None)
    res = base - X @ beta
    se = np.sqrt(res.var(ddof=2) * np.linalg.inv(X.T @ X)[0, 0])
    L += ["", "A7 NOT JUST DRIFT: NOISE net = alpha + beta x the session's return",
          f"   alpha {beta[0] * 1e4:+.2f}bp a day, t {beta[0] / se:+.2f}; beta {beta[1]:+.3f}; correlation {np.corrcoef(base, ctl)[0, 1]:+.2f}"]

    gm, _, nm = noise(A, prev, last=150)            # minute 150 after 09:30 = 12:00
    morn = net(gm, nm)
    from backtest.fx_anomalies import yf_daily
    v = yf_daily("^VXN", start="2009-01-01").Close
    hi = (v > v.rolling(252).median()).shift(1)
    hv = hi.reindex(dates, method="ffill").fillna(False).astype(bool).to_numpy()
    hvx = np.where(hv, base, 0.0)
    L += ["", "A8 HIS HELP", f"   no entries after 12:00 NY   {summ(morn, cut)}",
          f"   only when VXN > 1y median   {summ(hvx, cut)}   ({hv.mean() * 100:.0f}% of days)",
          f"   the other days (VXN low)    {summ(np.where(hv, 0.0, base), cut)}"]

    n1 = all(ph[p].mean() > 0 for p in ph) and sum(tstat(ph[p]) >= 2 for p in ph) >= 4
    n2 = all(lk[k].mean() > 0 for k in lk)
    n3 = c2.mean() > 0 and tstat(c2) < 2
    n4 = lf[5].mean() >= 0.5 * lf[1].mean()
    n5 = corr >= 0.8
    n6 = net(gL, nL).mean() > 0 and net(gS, nS).mean() > 0
    n7 = beta[0] > 0 and beta[0] / se >= 2
    n8 = morn.mean() < base.mean() and hvx.mean() < base.mean()
    L += ["", "REGISTERED PREDICTIONS",
          f"  N1 positive in all 6 phases, t >= 2 in >= 4 ({sum(tstat(ph[p]) >= 2 for p in ph)}) -> {'RIGHT' if n1 else 'WRONG'}",
          f"  N2 positive at every lookback -> {'RIGHT' if n2 else 'WRONG'}",
          f"  N3 costs x2 positive, t < 2 -> {'RIGHT' if n3 else 'WRONG'}",
          f"  N4 a 5-minute late fill keeps >= half -> {'RIGHT' if n4 else 'WRONG'}",
          f"  N5 Exness vs HistData daily correlation >= 0.8 ({corr:+.2f}) -> {'RIGHT' if n5 else 'WRONG'}",
          f"  N6 both legs positive -> {'RIGHT' if n6 else 'WRONG'}",
          f"  N7 alpha over drift t >= 2 ({beta[0] / se:+.2f}) -> {'RIGHT' if n7 else 'WRONG'}",
          f"  N8 morning-only and high-VXN each earn less than the base -> {'RIGHT' if n8 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

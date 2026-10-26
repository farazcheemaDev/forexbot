"""CAN THE BEST FOREX-SIDE BOOK PASS A FUNDED-ACCOUNT CHALLENGE? (2026-10-26)

THE USER (2026-10-26): "try forex market again, theres huge potential sitting there too". The repo has tested forex as a
way to grow a $221-300 account (every rule dead, NASDAQ NOISE the one candidate: +22% a year at x5, fall 56%). It never
tested the other way a small stake reaches a large forex account: a funded-account challenge ("prop firm") - pay a fee,
trade the firm's 10,000-100,000 USD under loss limits, keep ~80% of the profit. This file measures ONE thing: how often the
NOISE book's real daily history passes the published two-step rules, against a ZERO-EDGE control, and what a fee then buys.
It does NOT test any firm's honesty, payout record or fine print - that cannot be measured from here (see the end).

RULES MODELLED (the commonly published 2-step; sources disagree on details, so every limit is a parameter and the user must
read the real firm's page): phase 1 target +10%, phase 2 target +5%; the account must stay above 90% of the START balance
(static max loss 10%); no single day may lose 5% of the start balance; no minimum days; the time limit per phase is varied
(21 trading days ~ 30 calendar, 42 ~ 60 calendar, or none). Phase 2 starts fresh the next day. Funded phase: profits above
the start balance are paid out 80% at every 21-day mark and the balance resets; a breach ends it.
THE BOOK: backtest/noise_book.py's daily net return at 1x (NASDAQ NOISE at Exness costs, intraday only - flat overnight, so
no swap), scaled by a constant leverage k. HISTORY 2010-2026; rolling start on every day; tune = the first 60% of days.
THE CONTROL: the same days with the book's average daily return removed (zero drift, same volatility and fat tails).
A challenge is a LOTTERY whose odds the structure sets; the book's edge is the DIFFERENCE from the control.
OPTIMISTIC BY CONSTRUCTION: the daily series is close-to-close, so an intraday loss that touches the 5% daily limit before
the close is not seen; commissions, firm data-feed differences and any news-trading / consistency rules are not charged.

REGISTERED BEFORE THE FIRST RUN (2026-10-26)
  Q1  With NO time limit the book passes BOTH phases in over 50% of rolling starts at k = 1-2 (the barriers are wide
      against its 8%-a-year volatility at k = 1).
  Q2  The zero-edge control passes both phases in 25-40% of starts with no time limit (a random walk: 1/2 x 2/3 = 33%),
      so the edge adds less than 30 points to the pass rate.
  Q3  With a 21-trading-day limit per phase the book passes both phases in under 10% of starts at every k <= 3.
  Q4  With a 21-day limit the edge adds under 5 points over the control at every k (the edge is small beside a month's noise).
  Q5  The pass rate is not better on the holdout than on the tune half by more than 10 points (no decay, no gift).
DECISION LINES  The funded route is worth the user's time only if (a) there is a firm whose time limit is 42 days or longer
  AND whose rules the user has read on its own site, (b) the book's pass rate exceeds the control's by 10 points or more on
  BOTH halves at the k chosen, and (c) the expected first-year payout times the pass rate is at least 3x the fee. Otherwise
  it is a bought lottery ticket and is reported as that.

    python -m backtest.prop_pass
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.fx_intraday_pub import INSTR, SLIP, TUNE, noise, session  # noqa: E402

LOG = ROOT / "logs" / "prop_pass.txt"
T1, T2, DL, ML = 0.10, 0.05, 0.05, 0.10
SPLIT_FUNDED, PAY = 21, 0.80
CAP = 1000                                    # "no limit" = at most 1000 trading days (~4 years) per phase


def phase(r: np.ndarray, s: int, k: float, target: float, tmax: int):
    """Returns (outcome, days used). outcome: pass / daily / max / time / end."""
    eq = 1.0
    for t in range(min(tmax, CAP)):
        i = s + t
        if i >= len(r):
            return "end", t
        d = eq * k * r[i]
        if d <= -DL:
            return "daily", t + 1
        eq += d
        if eq <= 1 - ML:
            return "max", t + 1
        if eq >= 1 + target:
            return "pass", t + 1
    return "time", min(tmax, CAP)


def funded(r: np.ndarray, s: int, k: float, days: int = 252):
    """Year-one funded run: paid out 80% of profit at each 21-day mark; returns (paid as a fraction of the account, blown)."""
    eq, paid = 1.0, 0.0
    for t in range(days):
        i = s + t
        if i >= len(r):
            return paid, False, True
        d = eq * k * r[i]
        if d <= -DL:
            return paid, True, False
        eq += d
        if eq <= 1 - ML:
            return paid, True, False
        if (t + 1) % SPLIT_FUNDED == 0 and eq > 1:
            paid += PAY * (eq - 1)
            eq = 1.0
    return paid, False, False


def run(r: np.ndarray, starts: range, k: float, tmax: int, with_funded: bool = False):
    n = p1 = p12 = fail = to = 0
    pay_all, pay_pass, blown, got, took = [], [], 0, 0, []
    for s in starts:
        o1, d1 = phase(r, s, k, T1, tmax)
        if o1 == "end":
            continue
        n += 1
        if o1 == "pass":
            p1 += 1
            o2, d2 = phase(r, s + d1, k, T2, tmax)
            if o2 == "pass":
                p12 += 1
                took.append(d1 + d2)
                if with_funded:
                    paid, bl, ended = funded(r, s + d1 + d2, k)
                    if not ended:
                        pay_pass.append(paid)
                        blown += bl
                        got += paid > 0
                continue
            fail += o2 in ("daily", "max")
            to += o2 == "time"
        else:
            fail += o1 in ("daily", "max")
            to += o1 == "time"
    out = dict(n=n, p1=p1 / n if n else 0, both=p12 / n if n else 0, fail=fail / n if n else 0, timeout=to / n if n else 0)
    out["days"] = float(np.median(took)) if took else float("nan")
    if with_funded and pay_pass:
        out.update(paid=float(np.mean(pay_pass)), got=got / len(pay_pass), blown=blown / len(pay_pass))
    return out


def main():
    A, dates, prev = session("NASDAQ")
    cost = (INSTR["NASDAQ"][4] + SLIP) / 1e4
    g, _, nn = noise(A, prev)
    r = np.asarray(g - cost * nn, float)
    r0 = r - r.mean()                                   # the zero-edge control
    N = len(r)
    cut = int(N * TUNE)
    spans = {"all": range(0, N - 60), "tune": range(0, cut), "holdout": range(cut, N - 60)}
    L = [f"backtest/prop_pass.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; NASDAQ NOISE daily history {dates[0]:%Y-%m-%d}.."
         f"{dates[-1]:%Y-%m-%d} ({N} days), mean {r.mean() * 1e4:+.2f}bp/day, sd {r.std() * 100:.2f}%/day at 1x; rolling starts",
         f"rules: +{T1 * 100:g}% then +{T2 * 100:g}%, max loss {ML * 100:g}% static, daily loss {DL * 100:g}%; BOTH = passes both phases", ""]
    res = {}
    for tmax, tl in ((CAP, "no time limit"), (42, "42 trading days a phase"), (21, "21 trading days a phase")):
        L.append(f"-- {tl}")
        L.append(f"   {'k':>3} {'span':<8} {'BOOK both':>10} {'ph1':>6} {'fail':>6} {'timeout':>8} |"
                 f" {'CTRL both':>10} {'ph1':>6} {'fail':>6} {'timeout':>8} | {'edge':>7}")
        for k in (1, 2, 3, 4, 5):
            for sp, rg in spans.items():
                b, c = run(r, rg, k, tmax), run(r0, rg, k, tmax)
                res[(tmax, k, sp)] = (b["both"], c["both"])
                L.append(f"   x{k:<2} {sp:<8} {b['both'] * 100:>9.1f}% {b['p1'] * 100:>5.0f}% {b['fail'] * 100:>5.0f}% {b['timeout'] * 100:>7.0f}% |"
                         f" {c['both'] * 100:>9.1f}% {c['p1'] * 100:>5.0f}% {c['fail'] * 100:>5.0f}% {c['timeout'] * 100:>7.0f}% |"
                         f" {(b['both'] - c['both']) * 100:>+6.1f}")
        L.append("")
    L.append("-- TIME TO PASS BOTH PHASES, no time limit (median trading days over the starts that pass; 252 = a year)")
    for k in (1, 2, 3, 4, 5):
        L.append(f"   x{k}: book {run(r, spans['all'], k, CAP)['days']:.0f} days | control {run(r0, spans['all'], k, CAP)['days']:.0f} days")
    L.append("")
    L.append("-- FUNDED YEAR after passing (no time limit; paid 80% of profit every 21 days; fraction of the account)")
    L.append(f"   {'k':>3} {'span':<8} {'BOOK paid':>10} {'any pay':>8} {'blown':>6} | {'CTRL paid':>10} {'any pay':>8} {'blown':>6}")
    fund = {}
    for k in (1, 2, 3):
        for sp in ("all", "holdout"):
            b, c = run(r, spans[sp], k, CAP, True), run(r0, spans[sp], k, CAP, True)
            fund[(k, sp)] = (b, c)
            L.append(f"   x{k:<2} {sp:<8} {b.get('paid', 0) * 100:>9.1f}% {b.get('got', 0) * 100:>7.0f}% {b.get('blown', 0) * 100:>5.0f}% |"
                     f" {c.get('paid', 0) * 100:>9.1f}% {c.get('got', 0) * 100:>7.0f}% {c.get('blown', 0) * 100:>5.0f}%")
    L += ["", "-- WHAT A FEE BUYS (per attempt, as a fraction of the account; fee 1.2% of the account is an ASSUMPTION - read the real price;",
          "   'friction' halves the payouts, since only ~45% of the people who pass are reported to be paid)"]
    for k in (1, 2, 3):
        b, _ = fund[(k, "all")]
        pb = res[(CAP, k, "all")][0]
        ev = pb * b.get("paid", 0)
        L.append(f"   x{k}: P(pass both) {pb * 100:.0f}% x first-year payout {b.get('paid', 0) * 100:.1f}% = {ev * 100:.2f}% of the account"
                 f" per attempt; fee 1.2% -> {ev / 0.012:.1f}x the fee (with friction {ev * 0.45 / 0.012:.1f}x)")
    q1 = all(res[(CAP, k, "all")][0] > 0.50 for k in (1, 2))
    q2 = all(0.25 <= res[(CAP, k, "all")][1] <= 0.40 for k in (1, 2, 3)) and all(res[(CAP, k, "all")][0] - res[(CAP, k, "all")][1] < 0.30 for k in (1, 2, 3))
    q3 = all(res[(21, k, "all")][0] < 0.10 for k in (1, 2, 3))
    q4 = all(res[(21, k, "all")][0] - res[(21, k, "all")][1] < 0.05 for k in (1, 2, 3, 4, 5))
    q5 = all(res[(CAP, k, "holdout")][0] - res[(CAP, k, "tune")][0] <= 0.10 for k in (1, 2, 3))
    L += ["", "REGISTERED PREDICTIONS",
          f"  Q1 no time limit, both phases over 50% at k=1-2 -> {'RIGHT' if q1 else 'WRONG'}",
          f"  Q2 control 25-40% with no limit, edge adds under 30 points -> {'RIGHT' if q2 else 'WRONG'}",
          f"  Q3 21-day limit, both phases under 10% at k<=3 -> {'RIGHT' if q3 else 'WRONG'}",
          f"  Q4 21-day limit, edge adds under 5 points at every k -> {'RIGHT' if q4 else 'WRONG'}",
          f"  Q5 holdout not better than tune by over 10 points -> {'RIGHT' if q5 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

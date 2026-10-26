"""THE crypto-regime-analyzer COMPOSITE AS A PREDICTOR / DIAL FOR OUR MACHINE (2026-10-27)

tradermonty/claude-trading-skills' crypto-regime-analyzer scores the crypto market 0-100 from six components (BTC trend
structure 25%, alt breadth 20%, BTC dominance 15%, perpetual funding 15%, drawdown + volatility 15%, momentum thrust 10%) and
bands it RISK_ON >= 80 / NEUTRAL / RISK_OFF < 40. Its own references/VALIDATION.md says the bands are "descriptive heuristics, not
allocation rules" and that no historical test exists. The user said not to treat earlier negatives as final, and the sentiment
dials tested earlier (Fear & Greed, breadth label, regime weights) were different objects. So: build THIS composite from the
skill's tables, point-in-time, and ask whether it carries information about our machine.

BUILT FROM  the daily panel (market_neutral.load_panel: every Binance perp's daily close and funding). Components as the
  skill's methodology tables give them: (1) BTC trend: stack base 90 / 65 / 55 / 45 / 15 / 50 by price vs 50 and 200-day
  averages, +-10 for a rising / falling 200-day average over 20 days (flat band +-0.3%); (2) alt breadth: share of the
  point-in-time top-20 (BTC out) above their own 200-day average (>=80% 95, >=65% 80, >=50% 65, >=35% 45, >=20% 25, else 10),
  +-5 when the 50-day breadth leads / lags by 15 points; (4) funding: average of the top-20's daily funding / 3 as an 8h rate
  (<= -0.010% 80, <= 0 65, <= 0.010% 75, <= 0.030% 55, <= 0.060% 30, above 10); (5) drawdown of BTC from its 1-year high
  (<=10% 90, <=20% 75, <=35% 55, <=50% 35, <=65% 20, else 10; the skill's volatility modifier text is cut off in the file and is
  NOT used); (6) share of the universe + BTC with a positive 30-day return (>=85% 90, >=65% 75, >=45% 55, >=25% 35, >=10% 20, else 35).
  (3) BTC dominance has no free history -> its weight is redistributed, which the skill allows with >= 4 components.
READ    at each month-end close; it applies to the NEXT month.
TARGETS logs/chop_gap_months.pkl: the final machine's monthly return (mean of 10 orderings, trend gains shrunk 3x) and BTC's.
TESTS   V1 Spearman(score at month-end, next month's machine return) and the same for next-month BTC, both halves (split at
        the 60% month); V2 the DIAL: exposure RISK_ON 100% / NEUTRAL 100% / RISK_OFF 50% on the machine's monthly return,
        against (b) the bet-smaller line (constant exposure = the rule's average) on log growth and worst month, both halves.

REGISTERED BEFORE THE FIRST RUN (2026-10-27)
  W1  No monotone relation: |Spearman| < 0.25 with the machine's next month on at least one half (n ~ 39 per half; the
      noise band is +-0.3).
  W2  RISK_OFF is under 20% of months (the BTC trend component dominates and BTC was above its averages most of 2020-26).
  W3  The dial does not beat the bet-smaller line on BOTH log growth and worst month on both halves.
PASS    |Spearman| >= 0.3 with the right sign on both halves, OR the dial beats the line on both halves; otherwise NO SIGNAL.

    python -m backtest.crypto_regime_score
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.market_neutral import drop_non_crypto, load_panel  # noqa: E402
from backtest.regime_signals import member_mask  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

LOG = ROOT / "logs" / "crypto_regime_score.txt"
W = {"trend": 25, "breadth": 20, "funding": 15, "dd": 15, "thrust": 10}


def band(x, table, default):
    for thr, val in table:
        if x >= thr:
            return val
    return default


def components():
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    F.index = C.index
    X = C.to_numpy(float)
    mem = member_mask(C, first, drop_non_crypto(eligibility(20))) & np.isfinite(X)
    cols = list(C.columns)
    ib = cols.index("BTCUSDT")
    b = C["BTCUSDT"]
    ma50, ma200 = b.rolling(50).mean(), b.rolling(200).mean()
    slope = ma200 / ma200.shift(20) - 1
    A50 = C.rolling(50).mean().to_numpy()
    A200 = C.rolling(200).mean().to_numpy()
    n = len(C)
    out = {k: np.full(n, np.nan) for k in W}
    hi1y = b.rolling(365, min_periods=300).max()
    for d in range(1, n):
        # trend structure
        p, m5, m2 = b.iloc[d], ma50.iloc[d], ma200.iloc[d]
        if np.isfinite(m2) and np.isfinite(slope.iloc[d]):
            if abs(p / m5 - 1) < 1e-9 and abs(m5 / m2 - 1) < 1e-9:
                base = 50
            elif p > m5 > m2:
                base = 90
            elif m5 > m2 and m2 <= p <= m5:
                base = 65
            elif m5 > m2 and p < m2:
                base = 55
            elif p > m5 and m5 <= m2:
                base = 45
            elif p < m5 < m2:
                base = 15
            else:
                base = 50
            mod = 10 if slope.iloc[d] > 0.003 else (-10 if slope.iloc[d] < -0.003 else 0)
            out["trend"][d] = min(100, max(0, base + mod))
        # alt breadth / thrust / funding on the PIT top-20 known at d-1
        mm = mem[d - 1].copy()
        mm[ib] = False
        mm &= np.isfinite(A200[d])
        if mm.sum() >= 5:
            b200 = np.mean(X[d, mm] > A200[d, mm])
            b50 = np.mean(X[d, mm] > A50[d, mm])
            s = band(b200, [(0.8, 95), (0.65, 80), (0.5, 65), (0.35, 45), (0.2, 25)], 10)
            s += 5 if b50 - b200 >= 0.15 else (-5 if b200 - b50 >= 0.15 else 0)
            out["breadth"][d] = min(100, max(0, s))
        uni = mem[d - 1].copy()
        uni[ib] = True
        if d >= 31:
            ok = uni & np.isfinite(X[d]) & np.isfinite(X[d - 30])
            if ok.sum() >= 5:
                pos = np.mean(X[d, ok] / X[d - 30, ok] > 1)
                out["thrust"][d] = band(pos, [(0.85, 90), (0.65, 75), (0.45, 55), (0.25, 35), (0.10, 20)], 35)
        fm = mem[d - 1] & np.isfinite(F.iloc[d].to_numpy(float))
        if fm.sum() >= 2:
            f8 = np.mean(F.iloc[d].to_numpy(float)[fm]) / 3.0
            out["funding"][d] = (80 if f8 <= -0.0001 else 65 if f8 <= 0 else 75 if f8 <= 0.0001 else 55 if f8 <= 0.0003 else 30 if f8 <= 0.0006 else 10)
        if np.isfinite(hi1y.iloc[d]):
            dd = 1 - b.iloc[d] / hi1y.iloc[d]
            out["dd"][d] = 90 if dd <= 0.10 else 75 if dd <= 0.20 else 55 if dd <= 0.35 else 35 if dd <= 0.50 else 20 if dd <= 0.65 else 10
    comp = pd.DataFrame(out, index=C.index)
    w = pd.Series(W, dtype=float)
    avail = comp.notna()
    wsum = (avail * w).sum(axis=1)
    score = (comp.fillna(0) * w).sum(axis=1) / wsum
    score[(avail.sum(axis=1) < 4) | (wsum < 0.65 * 100)] = np.nan          # the skill's fail-closed rule (dominance's 15 missing)
    return score, comp, C


def spearman(a, b):
    ra, rb = pd.Series(a).rank(), pd.Series(b).rank()
    return float(np.corrcoef(ra, rb)[0, 1])


def main():
    score, comp, C = components()
    me = score.resample("ME").last().dropna()
    me.index = me.index.to_period("M")
    P = pd.read_pickle(ROOT / "logs" / "chop_gap_months.pkl")
    acct = P.groupby("month")["account"].mean()
    acct.index = pd.PeriodIndex(acct.index, freq="M")
    btc = C["BTCUSDT"].resample("ME").last().pct_change()
    btc.index = btc.index.to_period("M")
    prior = me.copy()
    prior.index = prior.index + 1                                     # month-end score -> the NEXT month
    D = pd.DataFrame(dict(score=prior, acct=acct, btc=btc)).dropna()
    cut = int(len(D) * 0.6)
    halves = {"tune": D.iloc[:cut], "holdout": D.iloc[cut:]}
    L = [f"backtest/crypto_regime_score.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; composite from 5 of the skill's 6 components "
         f"(dominance has no history), {len(D)} months {D.index[0]} .. {D.index[-1]}; score at month-end -> next month",
         f"  score: mean {D.score.mean():.0f}, min {D.score.min():.0f}, max {D.score.max():.0f}; months RISK_ON {np.mean(D.score >= 80) * 100:.0f}% / "
         f"NEUTRAL {np.mean((D.score >= 40) & (D.score < 80)) * 100:.0f}% / RISK_OFF {np.mean(D.score < 40) * 100:.0f}%", ""]
    sp = {}
    for hn, h in halves.items():
        sp[hn] = (spearman(h.score, h.acct), spearman(h.score, h.btc), len(h))
        L.append(f"  V1 {hn:8} n {len(h)}: Spearman(score, machine next month) {sp[hn][0]:+.2f} | (score, BTC next month) {sp[hn][1]:+.2f}")
    L.append("")
    expo = D.score.map(lambda s: 0.5 if s < 40 else 1.0)
    res = {}
    for hn, h in halves.items():
        e = expo.loc[h.index]
        r = h.acct * e
        const = h.acct * e.mean()

        def stats(x):
            x = x.clip(lower=-0.99)
            return np.log1p(x).mean() * 12 * 100, x.min() * 100

        a, b = stats(r), stats(const)
        res[hn] = (a, b, e.mean())
        L.append(f"  V2 {hn:8} dial (RISK_OFF x0.5; avg exposure {e.mean() * 100:.0f}%): log growth {a[0]:+.0f}%/yr, worst month {a[1]:+.1f}% | "
                 f"matched constant: {b[0]:+.0f}%/yr, {b[1]:+.1f}% | unscaled machine: {stats(h.acct)[0]:+.0f}%/yr, {stats(h.acct)[1]:+.1f}%")
    w1 = any(abs(sp[h][0]) < 0.25 for h in halves)
    w2 = np.mean(D.score < 40) < 0.20
    dial_beats = all(res[h][0][0] > res[h][1][0] and res[h][0][1] > res[h][1][1] for h in halves)
    sig = all(abs(sp[h][0]) >= 0.3 for h in halves) and np.sign(sp["tune"][0]) == np.sign(sp["holdout"][0])
    L += ["", "REGISTERED PREDICTIONS",
          f"  W1 |Spearman| < 0.25 on at least one half -> {'RIGHT' if w1 else 'WRONG'}",
          f"  W2 RISK_OFF under 20% of months ({np.mean(D.score < 40) * 100:.0f}%) -> {'RIGHT' if w2 else 'WRONG'}",
          f"  W3 the dial does not beat the matched constant on both log growth and worst month on both halves -> {'RIGHT' if not dial_beats else 'WRONG'}",
          f"  VERDICT: {'SIGNAL' if (sig or dial_beats) else 'NO SIGNAL'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

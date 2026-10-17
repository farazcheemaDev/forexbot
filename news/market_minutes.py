"""MARKET-WIDE NEWS, MINUTE BY MINUTE: does BTC react, which way, and is anything left for a bot? (2026-10-17)

news/impact.py reads hourly bars from the next hour's open, so a market-wide headline (ETF, Fed, regulation, hack,
treasury buys) whose move is over in minutes reads ~0 there. Here, on Binance BTCUSDT 1-minute bars (2022-01 .. 2026-08,
strategy_analysis/data/min1), for every market-wide event with a FinBERT tone (news/tone.py):
    t0      the headline's minute; DURING = BTC's move from that minute's open to its close (the market's reaction while
            the headline posts - a bot cannot have it)
    after   BTC's move from the open of the NEXT minute (t0 + 1 min: a fast bot's earliest entry) to +1 / +5 / +15 /
            +60 minutes, signed by tone (a positive headline's move counts as is, a negative one's sign is flipped):
            > 0 = BTC kept going the way the headline points
    groups  type x tone bucket (pos >= 0.5, neg <= -0.5); neutral headlines are reported unsigned
    cost    a BTC perp round trip ~12bp (taker) - a move must beat it to be a trade
CONTROL  the same calculation at random minutes (signed by a coin flip) - the noise floor.

REGISTERED BEFORE THE RUN (2026-10-17)
    M1 DURING, signed by tone, is positive for etf / regulation / macro (the headline's minute moves its way), 2-10bp.
    M2 after +1 minute, the signed move is under 5bp for every group - nothing a 12bp round trip can catch.
    M3 no group's +5 / +15 / +60 signed move exceeds 12bp with t >= 2.

    python -m news.market_minutes
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from news.impact import MARKET  # noqa: E402

EV = ROOT / "strategy_analysis" / "data" / "news" / "events.parquet"
TONE = ROOT / "strategy_analysis" / "data" / "news" / "tone.parquet"
M1 = ROOT / "strategy_analysis" / "data" / "min1" / "BTCUSDT_1m.parquet"
LOG = ROOT / "logs" / "news_market_minutes.txt"
HS = (1, 5, 15, 60)


def main():
    E = pd.read_parquet(EV).join(pd.read_parquet(TONE), how="inner")
    E = E[E.etype.isin(MARKET) & (E.coins.isin(["", "BTCUSDT"]) | E.coins.str.contains("BTCUSDT"))]
    B = pd.read_parquet(M1)
    t = B.time.to_numpy("datetime64[ns]").astype("int64")
    o, c = B.o.to_numpy(float), B.c.to_numpy(float)
    E = E[(E.t >= B.time.iloc[0]) & (E.t <= B.time.iloc[-1] - pd.Timedelta(hours=2))]
    m0 = pd.to_datetime(E.t).dt.floor("min").to_numpy("datetime64[ns]").astype("int64")
    i0 = np.searchsorted(t, m0)
    ok = (i0 < len(t) - 61) & (t[np.minimum(i0, len(t) - 1)] == m0)
    E, i0 = E[ok], i0[ok]
    during = c[i0] / o[i0] - 1
    after = {h: c[i0 + h] / o[i0 + 1] - 1 for h in HS}
    b = np.where(E.tone >= 0.5, "pos", np.where(E.tone <= -0.5, "neg", "neu"))
    sgn = np.where(b == "pos", 1.0, np.where(b == "neg", -1.0, 1.0))
    rng = np.random.default_rng(3)
    rj = rng.integers(0, len(t) - 61, 50_000)
    rs = np.where(rng.random(len(rj)) < 0.5, 1.0, -1.0)
    ctl = {h: rs * (c[rj + h] / o[rj + 1] - 1) for h in HS}
    ctl_d = rs * (c[rj] / o[rj] - 1)
    lines = [f"news/market_minutes.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(E):,} market-wide events with a tone, "
             f"BTC 1m {B.time.iloc[0]:%Y-%m} .. {B.time.iloc[-1]:%Y-%m}; bp, signed by tone (neutral unsigned); mean / t", "",
             f"  {'group':<18}{'n':>6}{'DURING':>14}" + "".join(f"{'+' + str(h) + 'm':>14}" for h in HS)]

    def cell(v):
        v = v * 1e4
        tt = v.mean() / (v.std(ddof=1) / np.sqrt(len(v))) if len(v) > 2 and v.std() > 0 else 0.0
        return f"{v.mean():>+7.1f}/{tt:>+5.1f}", v.mean(), tt
    res = {}
    for et in sorted(set(E.etype)):
        for bk in ("pos", "neg", "neu"):
            m = (E.etype.to_numpy() == et) & (b == bk)
            if m.sum() < 30:
                continue
            s = sgn[m]
            cells = [cell(s * during[m])] + [cell(s * after[h][m]) for h in HS]
            res[(et, bk)] = cells
            lines.append(f"  {et + ':' + bk:<18}{m.sum():>6}" + "".join(f"{x[0]:>14}" for x in cells))
    cc = [cell(ctl_d)] + [cell(ctl[h]) for h in HS]
    lines.append(f"  {'CONTROL (random)':<18}{len(rj):>6}" + "".join(f"{x[0]:>14}" for x in cc))
    m1 = [res[(e, k)][0][1] for e in ("etf", "regulation", "macro") for k in ("pos", "neg") if (e, k) in res]
    m2 = [abs(v[1][1]) for (e, k), v in res.items() if k != "neu"]
    m3 = [(e, k, h) for (e, k), v in res.items() if k != "neu" for h, x in zip(HS[1:], v[2:]) if x[1] > 12 and x[2] >= 2]
    lines += ["", "REGISTERED PREDICTIONS",
              f"  M1 DURING positive 2-10bp for etf / regulation / macro (pos and neg): {[round(x, 1) for x in m1]} -> "
              f"{'RIGHT' if m1 and all(2 <= x <= 10 for x in m1) else 'WRONG'}",
              f"  M2 +1 minute under 5bp everywhere: max |{max(m2) if m2 else 0:.1f}| -> {'RIGHT' if m2 and max(m2) < 5 else 'WRONG'}",
              f"  M3 no +5/+15/+60 move > 12bp with t >= 2: {m3 if m3 else 'none'} -> {'RIGHT' if not m3 else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

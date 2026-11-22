"""The NASDAQ trader's GOLD pattern as a rule: buy gold after a 2-hour slide, sell after a 2-hour pop - does it make money? (2026-11-13)

THE USER: "we have his strategy on gold ... can we profit from that strategy on gold". What we have (his_fade_stretch.py): his gold entries sit at
the faded end of the last 2 hours' range (rank 0.661, p 0.002) - he buys low / sells high in the 2-hour range. But 37 of his 43 gold trades are one
day (2026-02-02, a 99th-percentile gold day) and they won the +-$3.875 race 51% (his_strategy s39). So it is his PATTERN; whether it makes money
was never tested. Here it is, as a rule, on 16 years of gold minutes, against random entries.

DATA    HistData XAUUSD 1-minute BID bars 2010-01 .. 2026-09 (5.87M bars). Cost: Exness XAUUSDm's spread today is ~0.6bp (2026-11-10, MT5 ticks);
        charged 1.5bp a round trip (spread + slippage), and reported again at 3bp. Bid-only bars: the cost stands in for the spread.
SIGNAL  checked every 15 minutes (on the quarter hour): pos = where the last close sits in the last 120 minutes' high-low range (1-minute bars).
        pos <= Q -> LONG (fade a slide); pos >= 1 - Q -> SHORT (fade a pop). Q = 0.10 (primary) or 0.25. Entry at the next minute's open.
        No signal if the 120 min before or the 240 min after holds a gap of more than 10 minutes (weekends, the daily break).
EXITS   E1 his shape: target +0.08% (~$3.5 at $4,000), stop -1.0%, out after 240 min      (the race he wins on NASDAQ, no tight stop)
        E2 the race: +-0.08%, out after 240 min                                          (does the direction carry information?)
        E3 bigger: +-0.25%, out after 240 min
        A bar touching both target and stop counts as the stop.
CONTROL the same exits from EVERY quarter-hour mark, both sides (random entries at the same clock grid).
SPLIT   2010-01 .. 2019-12 tune / 2020-01 .. 2026-09 holdout (about 60 / 40 of the bars). Bet = signals of one UTC day in one direction; t over bets.

REGISTERED BEFORE THE RUN (2026-11-13)
  G1  On the E2 race the fade signal (Q 0.10) wins no more than random entries + 2 points on the holdout.                (70%)
  G2  His shape (E1, Q 0.10) loses money after 1.5bp on both halves.                                                     (80%)
  G3  No cell passes: net > 0 with t >= 2 on BOTH halves AND an excess over the random control with t >= 2 on both.         (85%)

RESULT (2026-11-13, logs/gold_fade_stretch.txt) - NO PASS; G1-G3 right. Every cell loses per trade after 1.5bp, in EVERY year 2010-2026.
  The fade carries a sliver of direction (E2 race 51.7% / 51.0% vs random 50.3% / 50.2%; excess +0.1..+0.6bp) - about a tenth of the cost.
  His shape (E1, Q 0.10) wins 79-82% and nets -1.31 / -1.09bp a trade. The positive 't/bet' column is the day-vote trap (CLAUDE.md s3): per trade
  every cell is negative. Not written into doc 02 / CLAUDE.md yet (usage limit).

    python -m backtest.gold_fade_stretch
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOG = ROOT / "logs" / "gold_fade_stretch.txt"
MIN = 60_000
LOOK, HOLD = 120, 240
SPLIT = pd.Timestamp("2020-01-01").value // 10**6
EXITS = {"E1 his shape +0.08% / -1% / 4h": (0.0008, 0.01), "E2 race +-0.08% / 4h": (0.0008, 0.0008), "E3 +-0.25% / 4h": (0.0025, 0.0025)}


def load():
    from backtest import fx_intraday_pub as fip
    d = pd.read_parquet(fip.HD / "XAUUSD.parquet").sort_values("t").drop_duplicates("t").reset_index(drop=True)
    return d.t.to_numpy(np.int64), d.o.to_numpy(float), d.h.to_numpy(float), d.l.to_numpy(float), d.c.to_numpy(float)


def marks(t, h, l, c):
    """Indices i (the bar whose close is read) on quarter hours with clean windows; returns i, pos."""
    gap = np.diff(t) > 10 * MIN
    bad = np.concatenate([[0], np.cumsum(gap)])                      # gap counter: equal before and after = no gap between
    q = (t // MIN) % 15 == 14                                         # the bar ending on the quarter hour (minute 14, 29, 44, 59)
    i = np.flatnonzero(q)
    i = i[(i >= LOOK) & (i + HOLD + 1 < len(t))]
    i = i[(bad[i] == bad[i - LOOK]) & (bad[i + HOLD + 1] == bad[i])]
    hh = pd.Series(h).rolling(LOOK).max().to_numpy()
    ll = pd.Series(l).rolling(LOOK).min().to_numpy()
    rng = hh[i] - ll[i]
    ok = rng > 0
    i = i[ok]
    return i, (c[i] - ll[i]) / rng[ok]


def walk(i, s, o, h, l, tp, sl):
    """Enter at the open of bar i+1, side s; returns R in % of price (gross)."""
    out = np.empty(len(i))
    for k, (a, sd) in enumerate(zip(i, s)):
        e = o[a + 1]
        H, Lo = h[a + 1:a + 1 + HOLD], l[a + 1:a + 1 + HOLD]
        if sd == 1:
            hit_t, hit_s = np.flatnonzero(H >= e * (1 + tp)), np.flatnonzero(Lo <= e * (1 - sl))
        else:
            hit_t, hit_s = np.flatnonzero(Lo <= e * (1 - tp)), np.flatnonzero(H >= e * (1 + sl))
        ft = hit_t[0] if len(hit_t) else HOLD
        fs = hit_s[0] if len(hit_s) else HOLD
        if fs <= ft and fs < HOLD:
            out[k] = -sl
        elif ft < HOLD:
            out[k] = tp
        else:
            out[k] = sd * (o[a + 1 + HOLD] / e - 1) if a + 1 + HOLD < len(o) else 0.0
    return out


def tbet(t, s, r):
    b = pd.DataFrame({"d": t // 86_400_000, "s": s, "r": r}).groupby(["d", "s"]).r.mean()
    return b.mean(), b.mean() / (b.std(ddof=1) / np.sqrt(len(b))), len(b)


def main():
    t, o, h, l, c = load()
    I, pos = marks(t, h, l, c)
    L = [f"backtest/gold_fade_stretch.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(t):,} gold minutes {pd.to_datetime(t[0], unit='ms'):%Y-%m} .. "
         f"{pd.to_datetime(t[-1], unit='ms'):%Y-%m}; {len(I):,} clean quarter-hour marks; split 2020-01-01; cost 1.5bp (and 3bp)", ""]
    rng = np.random.default_rng(3)
    ctl_i = I[rng.random(len(I)) < 0.25]                              # a quarter of all marks, random side
    ctl_s = np.where(rng.random(len(ctl_i)) < 0.5, 1, -1)
    S, X = {}, {}
    for ex, (tp, sl) in EXITS.items():
        rc = walk(ctl_i, ctl_s, o, h, l, tp, sl)
        for half, m in (("tune", t[ctl_i] < SPLIT), ("hold", t[ctl_i] >= SPLIT)):
            X[(ex, half)] = rc[m]
        L.append(ex)
        L.append(f"  random entries      tune: won {(X[(ex, 'tune')] > 0).mean() * 100:4.1f}%  net {(X[(ex, 'tune')].mean() - 0.00015) * 1e4:+6.2f}bp   "
                 f"hold: won {(X[(ex, 'hold')] > 0).mean() * 100:4.1f}%  net {(X[(ex, 'hold')].mean() - 0.00015) * 1e4:+6.2f}bp   (n {m.sum():,} hold)")
        for Q in (0.10, 0.25):
            sel = (pos <= Q) | (pos >= 1 - Q)
            ii, ss = I[sel], np.where(pos[sel] <= Q, 1, -1)
            r = walk(ii, ss, o, h, l, tp, sl)
            for half, m in (("tune", t[ii] < SPLIT), ("hold", t[ii] >= SPLIT)):
                rr, base = r[m], X[(ex, half)]
                net = rr - 0.00015
                mb, tb, nb = tbet(t[ii][m], ss[m], net)
                ex_t = (rr.mean() - base.mean()) / np.sqrt(rr.var(ddof=1) / len(rr) + base.var(ddof=1) / len(base))
                S[(ex, Q, half)] = dict(n=len(rr), won=(rr > 0).mean(), net=net.mean(), net3=(rr - 0.0003).mean(), tb=tb, exc=rr.mean() - base.mean(), ext=ex_t)
                s_ = S[(ex, Q, half)]
                L.append(f"  fade Q {Q:.2f} [{half}]  n {s_['n']:>6,}  won {s_['won'] * 100:4.1f}% (random {(base > 0).mean() * 100:4.1f}%)  net {s_['net'] * 1e4:+6.2f}bp "
                         f"(3bp: {s_['net3'] * 1e4:+6.2f})  t/bet {tb:+5.1f} ({nb:,} bets)  excess over random {s_['exc'] * 1e4:+5.2f}bp (t {ex_t:+4.1f})")
            yr = pd.Series(r - 0.00015, index=pd.to_datetime(t[ii], unit="ms").year).groupby(level=0).mean() * 1e4
            L.append(f"    by year (net bp): " + " ".join(f"{y}:{v:+.1f}" for y, v in yr.items()))
        L.append("")
    passes = [(ex, Q) for ex in EXITS for Q in (0.10, 0.25) if all(S[(ex, Q, hf)]["net"] > 0 and S[(ex, Q, hf)]["tb"] >= 2 and S[(ex, Q, hf)]["ext"] >= 2 for hf in ("tune", "hold"))]
    e2 = S[("E2 race +-0.08% / 4h", 0.10, "hold")]
    e2b = (X[("E2 race +-0.08% / 4h", "hold")] > 0).mean()
    e1 = [S[("E1 his shape +0.08% / -1% / 4h", 0.10, hf)]["net"] for hf in ("tune", "hold")]
    L += ["PREDICTIONS",
          f"  G1 E2 fade wins <= random + 2 pts on the holdout ({e2['won'] * 100:.1f}% vs {e2b * 100:.1f}%) -> {'RIGHT' if e2['won'] <= e2b + 0.02 else 'WRONG'}",
          f"  G2 his shape loses after 1.5bp on both halves ({e1[0] * 1e4:+.2f} / {e1[1] * 1e4:+.2f}bp) -> {'RIGHT' if max(e1) < 0 else 'WRONG'}",
          f"  G3 no cell passes (passing: {passes or 'none'}) -> {'RIGHT' if not passes else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    sys.exit(main())

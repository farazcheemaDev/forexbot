"""'HIGH LEVERAGE, LIQUIDATION FAR AWAY, WAIT AS LONG AS IT TAKES TO BE IN PROFIT' ON BTC (2026-11-02)

The user's idea: put $50 on one BTC trade at 50x or 100x, trust that BTC will not reach the liquidation price any time soon, and wait
however long it takes to be in profit. Two things are measured, on Binance BTCUSDT perp 1h bars 2020-01 .. 2026-09 (58,940 bars):

  A  HOW OFTEN BTC REACHES THE LIQUIDATION LEVEL. For every hour as an entry (at the next open), the share of entries whose low
     (long) comes down to the liquidation price within 1 hour / 1 day / 7 days / 30 days / 90 days. Liquidation distance =
     1 / leverage - 0.5% maintenance margin (the smallest-tier assumption; check the exchange's own liquidation price).
  B  THE RULE ITSELF. Enter at any hour, no stop, wait until price has moved +0.30% in your favour (about +0.18% after the 0.12% taker
     round trip) or you are liquidated; a bar that touches both counts as liquidated; at most 5,000 hours (208 days), then marked at the
     close. Return on margin: win = (0.30% - 0.12% fees - funding) x leverage, liquidation = -100%. Longs pay funding 1bp per 8h of
     notional while they wait, shorts receive nothing (the repo's convention).

No predictions were registered (arithmetic, not a search): the check is the random-walk value d / (d + 0.30%) for the share of wins.

    python -m backtest.wait_leverage
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "logs" / "wait_leverage.txt"
FILE = ROOT / "strategy_analysis" / "data" / "perps" / "BTCUSDT_1h.csv.gz"
MMR, FEE2, FUND_H, TGT, CAP = 0.005, 0.0012, 1e-4 / 8, 0.003, 5000
LEVS = (100, 50, 20, 10)
HORIZONS = ((1, "1 hour"), (24, "1 day"), (168, "7 days"), (720, "30 days"), (2160, "90 days"))


def load():
    d = pd.read_csv(FILE, usecols=["time", "open", "high", "low", "close"])
    d["time"] = pd.to_datetime(d["time"])
    d = d.drop_duplicates("time").sort_values("time", kind="stable").reset_index(drop=True)
    return d, [d[k].to_numpy(float) for k in ("open", "high", "low", "close")]


def liq_distance(lev):
    return 1.0 / lev - MMR


def touch_share(arr, e, K, dist, side=1):
    """Share of entries (at the open of bar i+1, i = 0 .. n-2) whose liquidation level is touched within the K bars i+1 .. i+K:
    longs when the low is at or under e x (1 - dist), shorts when the high is at or over e x (1 + dist). Entries without K bars ahead are left out."""
    n = len(arr)
    i = np.arange(0, n - 1)
    ok = i + K < n
    s = pd.Series(arr[::-1]).rolling(K, min_periods=K)
    ext = (s.min() if side > 0 else s.max()).to_numpy()[::-1]            # ext[j] = extreme of bars j .. j+K-1
    hit = ext[i[ok] + 1] <= e[i[ok]] * (1 - dist) if side > 0 else ext[i[ok] + 1] >= e[i[ok]] * (1 + dist)
    return float(hit.mean())


def first_touch(o, h, l, c, E, side, dist, tgt, cap):
    """For entries at the open of E+1: (code, hours, mark). code 1 = target first, -1 = liquidated first (a bar touching both counts as
    liquidated), 0 = neither within `cap` bars (mark = the return at the close of bar E+cap)."""
    E = np.asarray(E, int)
    ee = o[E + 1]
    liq, tg = ee * (1 - side * dist), ee * (1 + side * tgt)
    code, kk = np.zeros(len(E), int), np.full(len(E), cap)
    act = np.arange(len(E))
    for k in range(1, cap + 1):
        if not len(act):
            break
        j = E[act] + k
        hl, ht = (l[j] <= liq[act], h[j] >= tg[act]) if side > 0 else (h[j] >= liq[act], l[j] <= tg[act])
        wn = ht & ~hl
        code[act[hl]], kk[act[hl]] = -1, k
        code[act[wn]], kk[act[wn]] = 1, k
        act = act[~(hl | wn)]
    return code, kk, c[E + cap] / ee - 1


def margin_returns(code, kk, mark, side, lev, tgt=TGT):
    """Return on margin per try: win = (tgt - fees - funding) x lev; liquidated = -100%; unresolved = marked, floored at -100%."""
    fund = FUND_H * kk if side > 0 else 0.0
    return np.where(code == 1, (tgt - FEE2 - fund) * lev,
                    np.where(code == -1, -1.0, np.maximum(-1.0, (side * mark - FEE2 - fund) * lev)))


def main():
    d, (o, h, l, c) = load()
    n = len(d)
    e = o[1:]
    L = [f"backtest/wait_leverage.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; BTCUSDT 1h, {n:,} bars {d.time.min():%Y-%m-%d} .. {d.time.max():%Y-%m-%d}; "
         f"maintenance margin {MMR * 100:.1f}%, taker fees 0.06% a side, target +{TGT * 100:.2f}%", ""]
    L.append("A  SHARE OF RANDOM LONG ENTRIES WHOSE LIQUIDATION LEVEL IS TOUCHED WITHIN ...")
    L.append(f"{'leverage':>9}{'distance':>10}" + "".join(f"{name:>9}" for _, name in HORIZONS))
    for lev in LEVS:
        dist = liq_distance(lev)
        L.append(f"{lev:>8}x{dist * 100:>9.1f}%" + "".join(f"{touch_share(l, e, K, dist) * 100:>8.0f}%" for K, _ in HORIZONS))
    E = np.arange(0, n - 1 - CAP)
    L += ["", "B  THE RULE: wait, no stop, until +0.30% in your favour or liquidated",
          f"{'':>10}{'side':>6}{'win':>7}{'liquidated':>12}{'open>208d':>11}{'median hrs to win':>19}{'mean return on margin / try':>29}{'10 tries without a wipe-out':>29}"]
    for lev in LEVS:
        for side in (1, -1):
            code, kk, mark = first_touch(o, h, l, c, E, side, liq_distance(lev), TGT, CAP)
            ret = margin_returns(code, kk, mark, side, lev)
            pw, pl, pu = (code == 1).mean(), (code == -1).mean(), (code == 0).mean()
            L.append(f"{lev:>9}x{'long' if side > 0 else 'short':>6}{pw * 100:>6.0f}%{pl * 100:>11.0f}%{pu * 100:>10.1f}%{np.median(kk[code == 1]):>19.0f}"
                     f"{ret.mean() * 100:>28.1f}%{(1 - pl) ** 10 * 100:>28.1f}%")
    L += ["", "random-walk check, P(target first) = d / (d + 0.30%): " + ", ".join(f"{lev}x {liq_distance(lev) / (liq_distance(lev) + TGT) * 100:.0f}%" for lev in LEVS),
          "while you wait, funding on a long: $50 at 100x ($5,000 position) = $%.2f a day = %.1f%% of the margin; at 50x ($2,500) = $%.2f = %.1f%%"
          % (5000 * 3e-4, 5000 * 3e-4 / 50 * 100, 2500 * 3e-4, 2500 * 3e-4 / 50 * 100),
          f"a win pays (0.30% - 0.12%) x leverage on the margin: ${50 * 0.0018 * 100:.2f} at 100x, ${50 * 0.0018 * 50:.2f} at 50x, against a loss of the whole $50"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

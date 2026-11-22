"""Is there anything in the CANDLE itself at his entries - body, wicks, reversal shapes? At scale. (2026-11-14)

The user: "is there something in the candles?" The momentum test used slope (close-to-close) and found 50%. This tests the intrabar
SHAPE the slope misses: the last closed 1-min candle's body direction, body/range, upper/lower wick, and the hammer / shooting-star /
engulfing reversal shapes - does any of it predict the +-7 race? At every 1-min-close+13s moment in his two windows over all 2026
(the clean large sample), and marked for his 53. 1-min OHLC built from the 1-second mid.

    python -m backtest.his_candle_shape
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest.his_setup_sweep import WINDOWS, day_series, race  # noqa: E402

LOG = ROOT / "logs" / "his_candle_shape.txt"


def candle(mid, t, sec):
    """OHLC of the closed 1-min candle [sec-60, sec) from the 1-s mid; indices via t dict."""
    a = t.get(sec - 60)
    b = t.get(sec - 1)
    if a is None or b is None or b <= a:
        return None
    w = mid[a:b + 1]
    return w[0], w.max(), w.min(), w[-1]


def main():
    import MetaTrader5 as mt5
    assert mt5.initialize(), mt5.last_error()
    mt5.symbol_select("USTECm", True)
    days = pd.bdate_range("2026-01-02", "2026-11-13").strftime("%Y-%m-%d")
    rows = []
    nday = 0
    for day in days:
        s = day_series(mt5, day)
        if s is None:
            continue
        nday += 1
        mid = s.to_numpy()
        sod = (s.index.hour * 3600 + s.index.minute * 60 + s.index.second).to_numpy()
        t = {int(v): k for k, v in enumerate(sod)}
        for w0, w1 in WINDOWS:
            for sec in range(w0, w1, 60):
                i = t.get(sec + 13)
                if i is None or i < 2 * 60 or i + 10 * 60 + 1 >= len(mid):
                    continue
                c1 = candle(mid, t, sec)
                c0 = candle(mid, t, sec - 60)
                if c1 is None:
                    continue
                o, h, l, cl = c1
                rng = h - l
                if rng <= 0:
                    continue
                up_first, _ = race(mid, i, 1)
                if not np.isfinite(up_first):
                    continue
                body = cl - o
                br = abs(body) / rng
                uw = (h - max(o, cl)) / rng
                lw = (min(o, cl) - l) / rng
                engulf = 0
                if c0 is not None:
                    o0, h0, l0, cl0 = c0
                    if body > 0 and cl0 < o0 and cl >= o0 and o <= cl0:
                        engulf = 1
                    elif body < 0 and cl0 > o0 and cl <= o0 and o >= cl0:
                        engulf = -1
                rows.append(dict(up=int(up_first), dir=int(np.sign(body)), br=br, uw=uw, lw=lw, rng=rng, engulf=engulf))
    mt5.shutdown()
    R = pd.DataFrame(rows)
    base = R.up.mean()
    L = [f"backtest/his_candle_shape.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {nday} days, {len(R)} moments; "
         f"base rate +7-first = {base * 100:.1f}%", "",
         "1. CANDLE BODY DIRECTION as a continuation call (call up if the last candle was bullish):"]
    g = R[R.dir != 0].copy()
    g["hit"] = (g.dir > 0) == (g.up == 1)
    L.append(f"   overall {g.hit.mean() * 100:.1f}% over {len(g)}")
    g["q"] = pd.qcut(g.br, 5, labels=False, duplicates="drop")
    for q, gg in g.groupby("q"):
        L.append(f"     body/range {gg.br.min():.2f}-{gg.br.max():.2f} (n {len(gg):>5}): continuation hit {gg.hit.mean() * 100:5.1f}%  "
                 f"[+7-first {gg.up.mean() * 100:.1f}%]")
    L += ["", "2. REVERSAL WICKS - forward +7-first rate by wick (a hammer = long lower wick should bounce UP; a star = long upper wick should drop):"]
    for lab, m in (("hammer (lower wick >= 0.5)", R.lw >= 0.5), ("strong hammer (>= 0.66)", R.lw >= 0.66),
                   ("star (upper wick >= 0.5)", R.uw >= 0.5), ("strong star (>= 0.66)", R.uw >= 0.66),
                   ("doji (body/range <= 0.1)", R.br <= 0.1)):
        x = R[m]
        L.append(f"   {lab:<30} n {len(x):>5}  +7-first {x.up.mean() * 100:5.1f}% (base {base * 100:.1f}%)")
    L += ["", "3. ENGULFING:",
          f"   bullish engulf n {int((R.engulf == 1).sum())}  +7-first {R[R.engulf == 1].up.mean() * 100:.1f}%",
          f"   bearish engulf n {int((R.engulf == -1).sum())}  +7-first {R[R.engulf == -1].up.mean() * 100:.1f}%"]
    # strongest deviation from base
    cells = []
    for lab, x in (("body-dir strongest quintile", g[g.q == g.q.max()].assign(v=lambda d: d.hit)["v"]),
                   ("hammer>=0.66 uprate", R[R.lw >= 0.66].up), ("star>=0.66 downrate", 1 - R[R.uw >= 0.66].up)):
        if len(x) > 30:
            cells.append((lab, x.mean(), len(x)))
    worst = max((abs(v - 0.5), lab, v, n) for lab, v, n in cells) if cells else (0, "none", 0.5, 0)
    L += ["", "VERDICT",
          f"  biggest edge over 50%: {worst[1]} = {worst[2] * 100:.1f}% (n {worst[3]}). "
          + ("WORTH A LOOK." if worst[0] >= 0.05 else "Nothing in the candle shape - every cell ~50%. The candle he clicks on does not predict the move.")]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    sys.exit(main())

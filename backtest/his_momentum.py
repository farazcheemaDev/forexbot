"""Is short-horizon momentum continuation predictive at NASDAQ entries - generally, or only at his moments? (2026-11-14)

My blind read scored 70% on his 53 (p 0.003); the mechanical 60-min-trend rule only 54%. So my read used RECENT momentum/shape.
This tests that cleanly and at scale: at every 1-min-close+13s moment in his two windows over all 2026, call the +-7 race in the
direction of the last k-minute slope, sweep k and the slope magnitude. If strong-slope cells beat ~55%, it is a mechanizable edge
(recheck for bugs); if flat ~50%, momentum continuation is NOT predictive in general and my 70% was his-moment selection or noise.

    python -m backtest.his_momentum
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest.his_setup_sweep import WINDOWS, day_series, race  # noqa: E402

LOG = ROOT / "logs" / "his_momentum.txt"
KS = [3, 5, 10]


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
                if i is None or i < 11 * 60 or i + 10 * 60 + 1 >= len(mid):
                    continue
                e = mid[i]
                up_first, _ = race(mid, i, 1)   # did +7 come before -7 (absolute)?
                if not np.isfinite(up_first):
                    continue
                rec = {"up": up_first}
                for k in KS:
                    j = t.get(sec + 13 - k * 60)
                    rec[f"s{k}"] = e - mid[j] if j is not None else np.nan
                rows.append(rec)
    mt5.shutdown()
    R = pd.DataFrame(rows)
    L = [f"backtest/his_momentum.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {nday} days, {len(R)} window moments; "
         "call the +-7 race in the direction of the last k-min slope", ""]
    for k in KS:
        col = f"s{k}"
        g = R.dropna(subset=[col]).copy()
        g["call_up"] = g[col] > 0
        g["hit"] = g.call_up == (g.up == 1)
        overall = g.hit.mean()
        L.append(f"last {k:>2}-min slope: call-continuation hit {overall * 100:.1f}% over {len(g)} moments")
        # by |slope| quintile
        g["q"] = pd.qcut(g[col].abs(), 5, labels=False, duplicates="drop")
        for q, gg in g.groupby("q"):
            L.append(f"    |slope| {gg[col].abs().min():5.1f}-{gg[col].abs().max():6.1f} pts: n {len(gg):>5}  continuation hit {gg.hit.mean() * 100:5.1f}%")
        L.append("")
    best = 0.0
    for k in KS:
        col = f"s{k}"
        g = R.dropna(subset=[col]).copy()
        g["hit"] = (g[col] > 0) == (g.up == 1)
        g["aq"] = pd.qcut(g[col].abs(), 5, labels=False, duplicates="drop")
        best = max(best, g[g.aq == g.aq.max()].hit.mean())
    L += ["VERDICT",
          f"  strongest-slope cell hit rate: {best * 100:.1f}% (coin flip 50%). "
          + ("MECHANIZABLE LEAD - recheck." if best >= 0.55 else "Flat ~50%: momentum continuation is NOT predictive in general; "
             "my 70% on his 53 was his-moment selection or noise, not a rule.")]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    sys.exit(main())

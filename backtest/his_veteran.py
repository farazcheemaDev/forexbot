"""A FOREX VETERAN'S RULES OF THUMB, AGAINST HIS SIDE - gap, VWAP, the day's open, time of day.

WHY (the user, 2026-10-04: "a person with 20 years of forex experience")
    His side is not in the price at any horizon (s36, s39), the futures tape, book or futures-cash gap (s37, s38, s40).
    The session-anchored heuristics an experienced index trader uses were never tested against his DIRECTION:
      - the opening GAP: fade it (gap up -> sell) or go with it;
      - VWAP: price above the session's volume-weighted average -> sell back to it, or buy with it;
      - the day's OPEN: above it -> bullish day bias;
      - time of day: buy or sell more at particular hours.

DATA: MT5 USTECm 5-minute bars (UTC labels) with tick volume for VWAP; his entries at the corrected clock.

REGISTERED PREDICTIONS (2026-10-04, before running)
    1. No anchor agrees with his side above 70% or below 30%; none survives Holm over the 6 tests.
    2. At his moments, the best anchor rule wins the +-7 race under 70% (his 88%).

    python -m backtest.his_veteran
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_race_curve import race2  # noqa: E402
from backtest.his_tape import TICKS, entries  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BARS = ROOT / "strategy_analysis" / "data" / "USTECm_5m_400d.json"


def main():
    from scipy.stats import binomtest
    b = pd.DataFrame(json.load(open(BARS)))
    b["t"] = pd.to_datetime(b["t"], unit="ms")
    b = b.set_index("t").sort_index()
    b["et"] = b.index.tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)
    x = entries()
    ticks = pickle.loads(TICKS.read_bytes())
    rows = []
    for r in x.itertuples():
        day = b[b.et.dt.normalize() == r.d]
        sess = day[(day.et.dt.time >= pd.Timestamp("09:30").time()) & (day.et <= r.et - pd.Timedelta(minutes=5))]
        prev = b[(b.et < r.d + pd.Timedelta(hours=16)) & (b.et.dt.normalize() < r.d)]
        prev = prev[prev.et.dt.time < pd.Timestamp("16:00").time()]
        if sess.empty or prev.empty:
            continue
        o = float(sess.o.iat[0])
        now = float(sess.c.iat[-1])
        tp = (sess.h + sess.l + sess.c) / 3
        vwap = float((tp * sess.v).sum() / sess.v.sum()) if sess.v.sum() > 0 else np.nan
        row = dict(s=r.s,
                   gap_fade=-np.sign(o - float(prev.c.iat[-1])),        # gap up -> sell
                   vwap_revert=-np.sign(now - vwap),                       # above VWAP -> sell
                   vwap_trend=np.sign(now - vwap),
                   open_bias=np.sign(now - o),                            # above the open -> buy
                   morning=1 if r.et.hour < 12 else -1)                   # +1: a morning trade (direction test below)
        dayt = ticks.get(r.d)
        if dayt is not None:
            ts, mid, _ = dayt
            row["his"] = race2(ts, mid, r.t, r.s, 600, 7, 7)
            for k in ("gap_fade", "vwap_revert", "vwap_trend", "open_bias"):
                sd = int(row[k])
                row["race_" + k] = race2(ts, mid, r.t, sd, 600, 7, 7) if sd else None
        rows.append(row)
    D = pd.DataFrame(rows)
    out = [f"{len(D)} NASDAQ entries with a full session and the prior close; his own +-7 race "
           f"{pd.to_numeric(D.his, errors='coerce').mean():.0%}",
           f"\n  {'rule':>12}{'agrees':>9}{'p':>8}{'race if side = rule':>22}"]
    ps = {}
    for k in ("gap_fade", "vwap_revert", "vwap_trend", "open_bias"):
        v = (D[k] * D.s)
        v = v[v != 0]
        ps[k] = binomtest(int((v > 0).sum()), len(v), 0.5).pvalue
        rc = pd.to_numeric(D["race_" + k], errors="coerce").mean()
        out.append(f"  {k:>12}{(v > 0).mean():>8.0%}{ps[k]:>8.3f}{rc:>21.0%}")
    am, pm = D[D.morning > 0], D[D.morning < 0]
    out.append(f"\n  time of day: before noon ET he buys {(am.s > 0).mean():.0%} of {len(am)}; "
               f"after noon {(pm.s > 0).mean():.0%} of {len(pm)}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_veteran.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()

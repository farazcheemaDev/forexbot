"""ES AGGRESSOR FLOW as the side in the mended engine (2026-10-16)

his_exact.py's rule C: at his sittings' ordinary moments, trading WITH the top-quintile ES aggressor flow over the last
2-10 s won NQ's +-7 race (Exness mid) 55-60% (317 moments a cell) - the first side anywhere in s36-s68 to reach 60%.
Mid races are not money: here it goes through the mended engine (his_mended.run, +7 / -S at the real Exness bid / ask).
DATA     ES mbp-1 trades (his_exact.py caches, his 31 windows only - 22.8 hours), Exness USTECm 1-s grid.
SIDE     sign of (ES buy - sell aggressor volume) / volume over the last w = 2 / 3 / 5 / 10 s, when |value| is in the top
         quintile (threshold from the TUNE days); entry with his 0.7-point pullback, and without it ("nopb").
STOPS    5 / 7 / 10 / 15; split by day, first 60% tune, last 40% holdout; the coin at the same seconds as control.

REGISTERED BEFORE THE RUN (2026-10-16)
    1. The mid-race 55-60% does not survive the spread: no cell positive on both halves.
    2. The win rate beats the coin by 2-8 points at the same stop (the information is real but small).
    LEAD LINE: positive on both halves, t >= 2 each, >= 100 holdout trades -> buy ES + NQ data for all 181 days and run
    it through backtest/mended_harness.py.

RESULT (2026-10-16, logs/es_flow_mended.txt) - DEAD; prediction 1 right, 2 wrong (no edge at all), lead line not hit.
    27 windows, 19.9 hours. All 64 cells lose on both halves, -1.15..-4.51 points a trade; the win rate over the coin at
    the same seconds is -9..+7 points, median +0.1. The 55-60% MID race (his_exact.py rule C) does not survive buying at
    the ask: an executable +7 needs the mid to go +9.2 before -(S - 2.2), and ES flow does not see that far.

    python -m backtest.es_flow_mended
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.his_exact as HX  # noqa: E402
import backtest.his_mended as MD  # noqa: E402
import backtest.his_tape as TP  # noqa: E402
from backtest.his_style_bot import day_grid  # noqa: E402

LOG = ROOT / "logs" / "es_flow_mended.txt"
WS = (2, 3, 5, 10)
STOPS = (5, 7, 10, 15)


def main():
    wins = TP.windows(TP.entries())
    E = HX.lean({(str(a), str(b)): pickle.loads((HX.ES_DIR / HX._name((str(a), str(b)))).read_bytes()) for a, b in wins})
    tr = E[E.action == HX.ACT["T"]]
    tns = tr.ns.to_numpy()
    sg = tr.side.to_numpy().astype(np.int64) * tr["size"].to_numpy()
    cf, cv = np.r_[0, np.cumsum(sg)], np.r_[0, np.cumsum(np.abs(sg))]
    cache = pickle.loads(TP.TICKS.read_bytes())
    days = sorted(d for d, v in cache.items() if v is not None)
    cut = days[int(len(days) * 0.6)]
    plan = []
    for a, b in wins:
        d = a.tz_localize("UTC").tz_convert("America/New_York").tz_localize(None).normalize()
        if d not in cache or cache[d] is None:
            continue
        g, gm, gsp, _ = day_grid(cache[d])
        base = (d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)
        off = int(g[0])
        lo = max(int((a - base).total_seconds()) + 15 - off, 5)
        hi = min(int((b - base).total_seconds()) - off, len(gm) - MD.CAP - 2)
        if hi - lo < 60:
            continue
        sec = np.arange(len(gm)) + off
        at = base.value + sec * 10**9
        j = np.searchsorted(tns, at, "right")
        flow = {}
        for w in WS:
            i0 = np.searchsorted(tns, at - w * 10**9, "right")
            v = cv[j] - cv[i0]
            flow[w] = np.where(v > 0, (cf[j] - cf[i0]) / np.maximum(v, 1), 0.0)
        plan.append((d, gm, gsp, lo, hi, flow))
    thr = {w: np.quantile(np.abs(np.concatenate([p[5][w][p[3]:p[4]] for p in plan if p[0] < cut])), 0.8) for w in WS}
    out = [f"backtest/es_flow_mended.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(plan)} windows "
           f"({sum(p[4] - p[3] for p in plan) / 3600:.1f} h), holdout from {cut:%Y-%m-%d}; {len(tr):,} ES trades", "",
           f"  {'side':<16}{'stop':>5}{'half':>9}{'trades':>8}{'won':>7}{'p*':>6}{'net/trade':>11}{'t':>7}{'coin won':>10}{'coin net':>10}"]
    orig = MD.pullback_ok
    R = {}
    for pb in (True, False):
        MD.pullback_ok = orig if pb else (lambda gm, i, s: True)
        for w in WS:
            for S in STOPS:
                for half in ("tune", "HOLDOUT"):
                    a, c = [], []
                    rng = np.random.default_rng(5)
                    for d, gm, gsp, lo, hi, flow in plan:
                        if (d < cut) != (half == "tune"):
                            continue
                        f = flow[w]
                        sig = np.where(f >= thr[w], 1, np.where(f <= -thr[w], -1, 0))
                        a += MD.run(gm, gsp, sig, lo, hi, S)
                        c += MD.run(gm, gsp, None, lo, hi, S, rng)
                    n, wr, m, t = MD.stats(a)
                    _, cw, cm, _ = MD.stats(c)
                    lab = f"esflow{w}{'' if pb else ' nopb'}"
                    R[(lab, S, half)] = (n, wr, m, t, cw)
                    out.append(f"  {lab:<16}{S:>5}{half:>9}{n:>8}{wr * 100:>6.0f}%{S / (7 + S) * 100:>5.0f}%{m:>+11.2f}{t:>+7.1f}"
                               f"{cw * 100:>9.0f}%{cm:>+10.2f}")
    MD.pullback_ok = orig
    cells = {k[:2] for k in R}
    both = sorted(c for c in cells if R[c + ("tune",)][2] > 0 and R[c + ("HOLDOUT",)][2] > 0)
    lead = [c for c in both if R[c + ("tune",)][3] >= 2 and R[c + ("HOLDOUT",)][3] >= 2 and R[c + ("HOLDOUT",)][0] >= 100]
    edge = [R[k][1] - R[k][4] for k in R if np.isfinite(R[k][1])]
    out += ["", "REGISTERED PREDICTIONS",
            f"  1 no cell positive on both halves: {both if both else 'none'} -> {'RIGHT' if not both else 'WRONG'}",
            f"  2 win rate over the coin 2-8 points: {min(edge) * 100:+.0f}..{max(edge) * 100:+.0f} (median {np.median(edge) * 100:+.1f}) -> "
            f"{'RIGHT' if 0.02 <= np.median(edge) <= 0.08 else 'WRONG'}",
            f"  LEAD LINE: {lead if lead else 'not hit'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

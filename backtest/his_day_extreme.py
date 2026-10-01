"""IS HE CLOSER TO THE DAY'S HIGH / LOW THAN THE MOMENTS AROUND HIM? - the winter charts' one eye impression, tested.

Reading his January-March charts at the corrected hour (his_strategy.md s35f), 11 of 15 entries sat at or near the
day's high or low so far - he faded some extremes and followed the break of others. s34's eye impression ("he trades
off key levels") failed its test, and his_keylevels.py pools the day's high/low with eight other levels, so this one is
isolated here before anyone believes it.

For each of his entries (corrected clock: winter UTC+4, s35c) and for the same-sitting moments (every whole-minute
offset within 20 minutes, same second of the minute, same direction - his_keylevels.py's comparison set):
  d_ext   points from the mid to the nearer of the day's high / low SO FAR (09:30 ET to that second)
  d_with  points to the extreme his trade points AWAY from (a buy: the low; a sell: the high) - "how far it has run"
  d_into  points to the extreme his trade points INTO (a buy: the high; a sell: the low) - "how close to a break"
Rank = share of the sitting's moments with a SMALLER value (low = his are closer). 0.50 is ordinary.

REGISTERED PREDICTION (2026-10-02, before running): all three rank 0.40-0.60, nothing near Holm - the moments within
20 minutes of an entry near an extreme are near the same extreme, so the impression is the sitting, not the click.

    python -m backtest.his_day_extreme
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_clock_check import to_utc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
GMT, WINTER = 5.0, 4.0


def feats(ts, mid, t, s):
    k = np.searchsorted(ts, t, side="right")
    if k < 60:
        return None
    hi, lo, p = mid[:k].max(), mid[:k].min(), mid[k - 1]
    d_hi, d_lo = hi - p, p - lo
    return dict(d_ext=min(d_hi, d_lo), d_with=d_lo if s > 0 else d_hi, d_into=d_hi if s > 0 else d_lo)


def main():
    from scipy.stats import wilcoxon
    cache = pickle.loads(TICKS.read_bytes())
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    u = to_utc(x.open_time, WINTER, GMT)
    x["et"] = u.dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    x["d"] = x.et.dt.normalize()
    x["t"] = (x.et - x.d - pd.Timedelta(hours=9, minutes=30)).dt.total_seconds()
    x = x[(x.t > 960) & x.d.map(lambda d: cache.get(d) is not None)]
    R = {k: [] for k in ("d_ext", "d_with", "d_into")}
    mine_all = {k: [] for k in R}
    for r in x.itertuples():
        ts, mid, _ = cache[r.d]
        s = 1 if r.side == "BUY" else -1
        mine = feats(ts, mid, r.t, s)
        if mine is None:
            continue
        others = x[x.d == r.d].t.to_numpy()
        near = [feats(ts, mid, r.t + 60 * m, s) for m in list(range(-20, 0)) + list(range(1, 21))
                if r.t + 60 * m > 960 and np.min(np.abs(others - (r.t + 60 * m))) >= 60]
        near = [n for n in near if n]
        if len(near) < 10:
            continue
        for k in R:
            R[k].append(np.mean([n[k] < mine[k] for n in near]))
            mine_all[k].append(mine[k])
    n = len(R["d_ext"])
    out = [f"his {n} clean entries (corrected clock, after 09:46 ET) vs the same-sitting moments, same second, same "
           f"direction; rank = share of those moments CLOSER than his (low = his are closer)"]
    ps = {k: wilcoxon(np.array(v) - 0.5).pvalue for k, v in R.items()}
    order = sorted(ps, key=ps.get)
    holm = {k: min(1.0, max(ps[j] * (len(ps) - i) for i, j in enumerate(order[:order.index(k) + 1])))
            for k in ps}
    for k, lab in (("d_ext", "to the nearer day extreme"), ("d_with", "to the extreme behind him"),
                   ("d_into", "to the extreme ahead of him")):
        out.append(f"  {k:<7} rank {np.mean(R[k]):.2f}   his median {np.median(mine_all[k]):>6.1f} pts   "
                   f"within 10 pts: {np.mean(np.array(mine_all[k]) <= 10):.0%}   p {ps[k]:.3f}   Holm {holm[k]:.3f}"
                   f"   ({lab})")
    # STAGE B: does room-ahead WIN races at random moments? If not, it is a preference, not his edge.
    from backtest.his_race_curve import race2
    rng = np.random.default_rng(31)
    his_days = set(x.d)
    rows = []
    for d in sorted(k for k, v in cache.items() if v is not None):
        ts, mid, _ = cache[d]
        for t in rng.uniform(960, min(ts[-1] - 700, 23400), 40):
            for s in (1, -1):
                f = feats(ts, mid, t, s)
                o = race2(ts, mid, t, s, 600, 7, 7)
                if f and o is not None:
                    rows.append(dict(day=d, his=d in his_days, o=o, **f))
    B = pd.DataFrame(rows)
    out.append(f"\nSTAGE B - {len(B)} random moment x direction pairs on {B.day.nunique()} days; 7-point mid race "
               f"base {B.o.mean():.1%}")
    mid_day = sorted(B.day.unique())[B.day.nunique() // 2]
    w = lambda g: g.o.mean() * 100  # noqa: E731
    for k in ("d_into", "d_with"):
        lo, hi = B[k].quantile([1 / 3, 2 / 3])
        a1, a2 = B[B.day < mid_day], B[B.day >= mid_day]
        out.append(f"  {k:<7} near third {w(B[B[k] <= lo]):.1f}%  far third {w(B[B[k] >= hi]):.1f}%  "
                   f"(far - near: 1st half {w(a1[a1[k] >= hi]) - w(a1[a1[k] <= lo]):+.1f}, "
                   f"2nd half {w(a2[a2[k] >= hi]) - w(a2[a2[k] <= lo]):+.1f})")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_day_extreme.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()

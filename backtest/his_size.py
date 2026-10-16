"""HOW BIG CAN A COPY OF HIM BE ON $221? - the trader's edge, sized by its worst move against you (2026-10-10).

The council (2026-10-10) ranked copying the NASDAQ trader first - the only edge in the repo replicated out of sample
(his_strategy.md s35d: 36/41 short races vs ~55% for random moments) - and named the open question: his edge is worth
+6.6..+7.0 points a trade to a copy 5-10 s late (his_copy_delay.py), i.e. $0.33 a trade at Exness's 0.05-lot minimum
(USTECm pays $1 a point per lot). It only matters at a larger size, and he trades with NO stop: a 7-point target, held
until hit (his_copy_delay's "his exit": closed at 30 minutes if never hit). So the size a $221 account can carry is set
by how far a copied trade goes AGAINST you before it resolves - which nobody had measured.

METHOD (the same 46 clean entries, ticks and clock as logs/his_copy_delay_all.txt: --winter-gmt 4, from 2026-01-01)
    each entry copied 0 / 5 / 10 s late at the Exness quote (enter at mid +- half the spread, mark on the exit side);
    his exit: +7 points, no stop, else closed at 30 min. Per trade: the result in points and the MAX ADVERSE EXCURSION
    (the deepest open loss before the exit), in points.
    The same rule from the SAME-SITTING moments (whole minutes +-1..20 from each entry, his direction) gives a much larger
    sample of how deep a +7/no-stop/30-min trade can go - the tail his 46 trades are too few to show.
SIZING RULE (registered by the council before the run): the largest lot at which the worst adverse excursion costs no
more than 25% of $221 = $55.25 (lots = 55.25 / worst points). KILL if that is <= 0.1 lot (the edge would be worth about
$4 a month or less on own capital) - unless a prop firm's rules allow copying (a separate check).

REGISTERED BEFORE RUNNING (2026-10-10)
    S1  The worst adverse excursion of a 5-10 s copy over his 46 trades is 15-40 points -> 0.14-0.37 lot by his own record.
    S2  The same-sitting moments' 99th percentile is 2-4x his own worst (his sample is too small to show the tail) ->
        0.05-0.10 lot when sized on it.
    S3  At the size S2 allows, the copy earns ~$2-4 a month (+6.6 points x lots x ~5 trades a month): KILL by the rule.

RESULT (2026-10-09 23:51 UTC, logs/his_size.txt; 42 of his 46 trades have ticks; the baseline reproduces
logs/his_copy_delay_all.txt byte for byte)
    - Copies 5 / 10 s late: won 98% / 100%, +6.56 / +7.00 points a trade, median hold ~40 s; deepest move against the
      copy: median 4-5, 90th percentile 18-19, WORST 40.5 / 40.9 points. S1 WRONG by a hair (predicted 15-40).
    - The same rule from 1,603 same-sitting moments: won 91%, +2.68 points a trade (the no-stop target's structure);
      deepest move: 90th 42.6, 99th 148.8, worst 315.4 points. S2 RIGHT: the 99th is 3.6x his own worst.
    - Sized on that 99th percentile, the lot is 0.37 (~$9,300 notional, ~42x on $221): +$13.82 a month, 6.3% of $221 a
      month at his ~5.5 trades. Sized on the WORST same-sitting move (315 points), 0.18 lot: +$6.52 a month, 3.0%.
      S3 WRONG: both sizes are above 0.10 lot, so by the rule registered before the run THE EDGE PASSES - it is not
      killed by size. (At 0.37 lot a 315-point move would be a $117 open loss, 53% of the account: the 25% limit holds
      only to the 99th percentile.)
    Reading: the strongest edge in the repo is worth roughly 3-6% a month on $221 at survivable sizes, IF it can be
    copied live within 10 s - which needs his signals. Next per the council: ask him once for a timestamped feed and
    demo-copy it for a month (kill: no reply in 2 weeks, or demo copies under +3 points a trade after the spread).

    python -m backtest.his_size
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.his_clock_check import to_utc  # noqa: E402

TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
LOG = ROOT / "logs" / "his_size.txt"
GMT, WINTER = 5.0, 4.0
CAPITAL, LIMIT = 221.0, 0.25
T, W = 7.0, 1800
DELAYS = (0, 5, 10)


def trade(ts, mid, spr, t, s):
    """His exit copied at t: (result points, max adverse excursion points, seconds held) - or None without ticks."""
    i = np.searchsorted(ts, t, side="right") - 1
    if i < 0 or i >= len(ts) - 1:
        return None
    e = mid[i] + s * spr[i] / 2                                # pay the spread on entry
    j1 = min(np.searchsorted(ts, t + W, side="right"), len(ts) - 1)
    p = s * ((mid[i + 1:j1] - s * spr[i + 1:j1] / 2) - e)     # marked on the side you would exit at
    if not len(p):
        return None
    hit = np.flatnonzero(p >= T)
    k = hit[0] if len(hit) else len(p) - 1
    res = T if len(hit) else float(p[-1])
    mae = max(0.0, -float(p[:k + 1].min()))
    return res, mae, float(ts[i + 1 + k] - t)


def main():
    cache = pickle.loads(TICKS.read_bytes())
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    utc = to_utc(x.open_time, WINTER, GMT)
    x["et"] = utc.dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    x = x[utc >= "2026-01-01"]
    x["d"] = x.et.dt.normalize()
    x["t"] = (x.et - x.d - pd.Timedelta(hours=9, minutes=30)).dt.total_seconds()
    his = {d: [] for d in DELAYS}
    near = []
    days = set()
    for r in x.itertuples():
        if r.d not in cache or cache[r.d] is None:
            continue
        ts, mid, spr = cache[r.d]
        s = 1 if r.side == "BUY" else -1
        days.add(r.d)
        for d in DELAYS:
            o = trade(ts, mid, spr, r.t + d, s)
            if o:
                his[d].append(o)
        others = x[x.d == r.d].t.to_numpy()
        for m in list(range(-20, 0)) + list(range(1, 21)):
            t0 = r.t + 60 * m
            if t0 > 60 and np.min(np.abs(others - t0)) >= 60:
                o = trade(ts, mid, spr, t0 + 5, s)
                if o:
                    near.append(o)
    span_m = (x.et.max() - x.et.min()).days / 30.44
    per_month = len(x) / span_m if span_m > 0 else np.nan
    allow = CAPITAL * LIMIT
    lines = [f"backtest/his_size.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; his {len(x)} NASDAQ trades from 2026-01-01 "
             f"({per_month:.1f} a month), {len(his[5])} with ticks; his exit = +{T:.0f} points, no stop, 30-min close; Exness "
             f"quotes; loss limit {LIMIT:.0%} of ${CAPITAL:.0f} = ${allow:.2f}", ""]
    lines.append("COPIED d seconds late: result and the deepest move against the position before it resolved (points)")
    for d in DELAYS:
        a = np.array(his[d])
        res, mae, hold = a[:, 0], a[:, 1], a[:, 2]
        lines.append(f"  {d:2d}s: {len(a)} trades | avg result {res.mean():+.2f} pts, won {np.mean(res >= T) * 100:.0f}% | "
                     f"adverse move: median {np.median(mae):.1f}, 90th {np.percentile(mae, 90):.1f}, WORST {mae.max():.1f} pts | "
                     f"median hold {np.median(hold):.0f} s | worst result {res.min():+.1f}")
    nm = np.array(near)
    lines.append(f"  SAME-SITTING moments, same rule, 5 s: {len(nm)} trades | won {np.mean(nm[:, 0] >= T) * 100:.0f}%, avg "
                 f"{nm[:, 0].mean():+.2f} pts | adverse move: median {np.median(nm[:, 1]):.1f}, 90th "
                 f"{np.percentile(nm[:, 1], 90):.1f}, 99th {np.percentile(nm[:, 1], 99):.1f}, WORST {nm[:, 1].max():.1f} pts")
    lines.append("")
    w5 = max(np.array(his[5])[:, 1].max(), np.array(his[10])[:, 1].max())
    p99, worst_near = np.percentile(nm[:, 1], 99), nm[:, 1].max()
    edge = np.mean([np.array(his[5])[:, 0].mean(), np.array(his[10])[:, 0].mean()])
    lines.append(f"SIZING ($1 a point per lot; the lot that keeps the worst adverse move within ${allow:.2f}); edge used: "
                 f"{edge:+.2f} pts a trade (avg of the 5 s and 10 s copies), {per_month:.1f} trades a month")
    for nm_, worst in (("his own worst (5-10 s copies)", w5), ("same-sitting 99th percentile", p99),
                       ("same-sitting worst", worst_near)):
        lots = allow / worst
        lines.append(f"  sized on {nm_:32} {worst:6.1f} pts -> {lots:.2f} lot (notional ~${lots * 25000:,.0f}, "
                     f"~{lots * 25000 / CAPITAL:.0f}x) -> ${edge * lots * per_month:5.2f} a month, "
                     f"{edge * lots * per_month / CAPITAL * 100:4.1f}% of ${CAPITAL:.0f}")
    lines.append("")
    lo = allow / max(p99, w5)
    lines.append(f"S1 (his worst 15-40 pts): {w5:.1f} -> {'RIGHT' if 15 <= w5 <= 40 else 'WRONG'}")
    lines.append(f"S2 (same-sitting 99th = 2-4x his worst): {p99 / w5:.1f}x -> {'RIGHT' if 2 <= p99 / w5 <= 4 else 'WRONG'}")
    lines.append(f"S3 / KILL RULE: the size the tail allows is {lo:.2f} lot -> {'KILL (<= 0.10 lot)' if lo <= 0.10 else 'PASSES (> 0.10 lot)'}; "
                 f"worth ${edge * lo * per_month:.2f} a month on ${CAPITAL:.0f}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

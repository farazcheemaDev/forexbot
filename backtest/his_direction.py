"""HOW DOES HE CHOOSE DIRECTION? - fade vs follow, on every NASDAQ entry at its corrected hour.

WHY NOW
    The user (2026-10-02): "I want to copy his STRATEGY, not his trades." A strategy has two parts: WHEN he enters
    and WHICH WAY. Everything since s26 has been about WHEN - and his timing is at chance in every recorded feature.
    WHICH WAY was flagged as "the next analysis" in s14 (8 usable cases then, ~85 needed) and never run. It can be
    now: 46 trades, all with ticks, at the hour s35c confirmed.

    And the record contradicts itself. s25 described "a NASDAQ-led 5-min move, then a 30-s dip, entered mid-candle"
    - FOLLOWING the 5-minute move, against the last 30 seconds. Reading the winter charts (s35f), five of fifteen
    entries FADED an exhausted spike at the day's high. Both cannot be his rule.

WHAT IS MEASURED (USTECm mid, Exness ticks; winter UTC+4, summer UTC+5)
    1. For horizons 15 s .. 30 min: the market's move into his entry, signed by his side.
       > 0 = he FOLLOWS that move, < 0 = he FADES it. Share following, binomial p against 50%.
    2. At HIS OWN moments, give a mechanical rule his timing and let it choose the side: "follow the last H" and
       "fade the last H", for each H. Its +-7 mid race (600 s) against his 88%. If a rule matches him, his direction
       is mechanical and his whole skill is timing. If none comes close, which way is part of his skill too.
    3. Summer and winter separately, since the charts suggested winter differs.

REGISTERED PREDICTIONS (2026-10-02, before running)
    1. No horizon is followed or faded with a consistency above 75%: his direction is not one mechanical rule.
    2. The 30-s horizon is FADED more often than followed (s25's "30-s dip"), and the 5-min horizon FOLLOWED more often
       than faded - but winter shows more fades of the 5-min move than summer.
    3. At his own moments the best mechanical side rule wins the race well below his 88% - under 70%. Which way is
       part of his skill, not only when.

    python -m backtest.his_direction
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_clock_check import EU_DST, to_utc  # noqa: E402
from backtest.his_race_curve import race2  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TICKS = ROOT / "strategy_analysis" / "data" / "ustec_tick_days.pkl"
GMT, WINTER = 5.0, 4.0
H = (15, 30, 60, 120, 300, 900, 1800)


def lab(h):
    return f"{h}s" if h < 60 else f"{h // 60}m"


def main():
    from scipy.stats import binomtest
    cache = pickle.loads(TICKS.read_bytes())
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    u = to_utc(x.open_time, WINTER, GMT)
    x["winter"] = (u < EU_DST).to_numpy()
    x["et"] = u.dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    x["d"] = x.et.dt.normalize()
    x["t"] = (x.et - x.d - pd.Timedelta(hours=9, minutes=30)).dt.total_seconds()
    rows = []
    for r in x.itertuples():
        day = cache.get(r.d)
        if day is None:
            continue
        ts, mid, _ = day
        k = np.searchsorted(ts, r.t, side="right") - 1
        if k < 1:
            continue
        s = 1 if r.side == "BUY" else -1
        row = dict(winter=r.winter, s=s, his=race2(ts, mid, r.t, s, 600, 7, 7))
        for h in H:
            j = np.searchsorted(ts, r.t - h, side="right") - 1
            mv = (mid[k] - mid[j]) if j >= 0 else np.nan
            row[f"mv{h}"] = s * mv                                       # > 0: he follows
            # the mechanical rules, given his timing: follow / fade the last h
            side = np.sign(mv) if j >= 0 and mv != 0 else 0
            row[f"fol{h}"] = race2(ts, mid, r.t, int(side), 600, 7, 7) if side else None
            row[f"fad{h}"] = race2(ts, mid, r.t, int(-side), 600, 7, 7) if side else None
        rows.append(row)
    D = pd.DataFrame(rows)
    out = [f"{len(D)} NASDAQ entries with ticks ({int(D.winter.sum())} winter, {int((~D.winter.astype(bool)).sum())} "
           f"summer); his own +-7 race: {np.nanmean(D.his.astype(float)):.0%}"]

    out.append("\n1. FADE OR FOLLOW - the move INTO his entry, signed by his side (> 0 = he follows it)")
    out.append(f"  {'horizon':>8} | {'all: follows':>13}{'p':>8}{'median pts':>11} | {'winter':>8}{'summer':>8}")
    for h in H:
        v = D[f"mv{h}"].dropna()
        nz = v[v != 0]
        f = (nz > 0).mean()
        p = binomtest(int((nz > 0).sum()), len(nz), 0.5).pvalue
        w = D[D.winter.astype(bool)][f"mv{h}"].dropna()
        sm = D[~D.winter.astype(bool)][f"mv{h}"].dropna()
        out.append(f"  {lab(h):>8} | {f:>12.0%}{p:>8.3f}{v.median():>+11.1f} | {(w[w != 0] > 0).mean():>7.0%}"
                   f"{(sm[sm != 0] > 0).mean():>8.0%}")

    out.append("\n2. GIVE A MECHANICAL RULE HIS TIMING - which side would it pick, and would it win the +-7 race?")
    out.append(f"  {'rule':>16} | {'race won':>9}{'n':>5} | {'agrees with his side':>21}")
    best = ("", 0.0)
    for h in H:
        for kind, col in (("follow last", f"fol{h}"), ("fade last", f"fad{h}")):
            v = D[col].dropna().astype(float)
            agree = D[f"mv{h}"].dropna()
            agree = (agree > 0).mean() if kind == "follow last" else (agree < 0).mean()
            out.append(f"  {kind + ' ' + lab(h):>16} | {v.mean():>8.0%}{len(v):>5} | {agree:>20.0%}")
            if v.mean() > best[1]:
                best = (kind + " " + lab(h), v.mean())
    out.append(f"\n  best mechanical side rule at his moments: {best[0]} -> {best[1]:.0%}, against his "
               f"{np.nanmean(D.his.astype(float)):.0%}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_direction.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()

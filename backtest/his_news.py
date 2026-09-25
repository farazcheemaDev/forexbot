"""DOES HE TRADE THE NEWS? His NASDAQ entries against the SAME CLOCK TIME on every other day.

The user, 2026-09-25: "other than charts he also relies on news". Reading his trades on the chart
(backtest/his_charts.py, logs/his_charts_*.png) showed two entries 30-45 minutes after a huge 08:30 ET
bar - the US data-release time. News was never tested on his record. A news footprint is abnormal
movement and volume, and both are also normal at fixed clock times (08:30 releases, the 09:30 open),
so the comparison must be TIME-OF-DAY MATCHED: each of his entries is ranked against the same ET
minute on every other trading day in the data. Under "no news effect" his percentile ranks are
uniform (mean 0.50). Nothing here is labelled from the outcome (the lesson of his_strategy.md s20).

FEATURES, all from 5-minute bars that CLOSED before his entry (USTECm, 2025-09 to 2026-09):
  shock60   the largest bar range in the prior 60 minutes, each bar divided by the median range of
            its own clock slot
  vol30     tick volume over the prior 30 minutes / that clock window's median
  move60    absolute move over the prior 60 minutes / that window's median
  day0830   today's 08:30 ET bar range / the 08:30 slot's median (a data-release footprint), only
            for entries after 08:35
  since     minutes since today's most recent shock bar (range >= 3x its slot median); none = 999
  FOMC      whether the entry falls on a Fed decision day (federalreserve.gov calendar)

REGISTERED PREDICTION (2026-09-25, before running): if he trades news, shock60, vol30 and day0830
rank high (mean percentile 0.60+, a third of entries in the top 20%); I expect a moderate effect -
mean ~0.60 on shock60 and day0830, p < 0.05 on at least one after Holm over five - and FOMC days
over-represented (base rate 8 of ~250 days, ~3%).

    python -m backtest.his_news
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "strategy_analysis" / "data"
GMT = 5.0


def bars():
    d = pd.DataFrame(json.load(open(DATA / "USTECm_5m_2400d.json")))
    d["t"] = pd.to_datetime(d.t, unit="ms")
    d = d.set_index("t").sort_index()
    d["et"] = d.index.tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)
    d["slot"] = d.et.dt.hour * 60 + d.et.dt.minute
    d["day"] = d.et.dt.normalize()
    d["rng"] = d.h - d.l
    return d


def fomc_days():
    H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124"}
    t = urllib.request.urlopen(urllib.request.Request(
        "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", headers=H), timeout=30).read().decode("utf-8", "replace")
    out = set()
    for year in ("2025", "2026"):
        i = t.find(f"{year} FOMC Meetings")
        if i < 0:
            continue
        seg = t[i:i + 25000]
        for mon, days in re.findall(r'fomc-meeting__month[^>]*>\s*<strong>([A-Za-z/]+)</strong>.*?fomc-meeting__date[^>]*>([0-9\-]+)', seg, flags=re.S):
            last = days.split("-")[-1]
            m = mon.split("/")[-1][:3]
            try:
                out.add(pd.Timestamp(f"{year}-{m}-{last}"))
            except Exception:
                pass
    # the page also carries minutes/notation-vote dates; every regular decision is on a WEDNESDAY
    # (the second day of a two-day meeting), so keep only those - 8 a year
    return {d for d in out if d.weekday() == 2}


def main():
    d = bars()
    med_rng = d.groupby("slot").rng.median()
    med_v = d.groupby("slot").v.median()
    d["rr"] = d.rng / d.slot.map(med_rng)
    d["vr"] = d.v / d.slot.map(med_v)
    d["shock"] = d.rr >= 3
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    x["utc"] = x.open_time - pd.Timedelta(hours=GMT)
    x = x[(x.utc > d.index[0] + pd.Timedelta(days=2)) & (x.utc < d.index[-1])]
    days = sorted(d.day.unique())
    by_day = {k: g for k, g in d.groupby("day")}

    def feats(day, minute):
        """Features for ET clock `minute` (minutes after midnight) on `day`, from bars closed by then."""
        g = by_day.get(day)
        if g is None:
            return None
        closed = g[g.slot + 5 <= minute]
        if len(closed) < 12:
            return None
        last12, last6 = closed.iloc[-12:], closed.iloc[-6:]
        if (last12.slot.iloc[-1] + 5) < minute - 5:
            return None                                             # a data gap right before
        f = {"shock60": last12.rr.max(), "vol30": last6.v.sum(), "move60": abs(last12.c.iloc[-1] - last12.o.iloc[0])}
        b830 = g[g.slot == 510]
        f["day0830"] = b830.rr.iloc[0] if (len(b830) and minute >= 515) else np.nan
        sh = closed[closed.shock]
        f["since"] = (minute - (sh.slot.iloc[-1] + 5)) if len(sh) else 999
        return f

    rows = []
    for r in x.itertuples():
        et = pd.Timestamp(r.utc).tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)
        minute = et.hour * 60 + et.minute
        mine = feats(et.normalize(), minute)
        if mine is None:
            continue
        ctrl = [feats(dd, minute) for dd in days if dd != et.normalize()]
        ctrl = [c for c in ctrl if c is not None]
        if len(ctrl) < 50:
            continue
        C = pd.DataFrame(ctrl)
        rec = dict(et=et, net=r.net)
        for k in ("shock60", "vol30", "move60", "day0830"):
            v = C[k].dropna()
            rec[k] = np.nan if (np.isnan(mine[k]) or not len(v)) else (v < mine[k]).mean() + 0.5 * (v == mine[k]).mean()
        v = C["since"]
        rec["since"] = (v > mine["since"]).mean() + 0.5 * (v == mine["since"]).mean()   # high = more RECENT shock
        rec["n_ctrl"] = len(C)
        rows.append(rec)
    R = pd.DataFrame(rows)
    print(f"{len(R)} of his NASDAQ entries have 5-minute bars around them; each ranked against the same ET minute "
          f"on ~{int(R.n_ctrl.median())} other days.\n")
    print("Percentile rank of his entry among the same clock time on other days (0.50 = ordinary).")
    ps = {}
    print(f"  {'feature':<9}{'n':>4}{'mean rank':>11}{'in top 20%':>12}{'expected':>10}{'p (mean>0.5)':>14}")
    for k, lab in (("shock60", "largest bar, prior 60 min"), ("vol30", "volume, prior 30 min"),
                   ("move60", "move, prior 60 min"), ("day0830", "today's 08:30 bar"), ("since", "recency of a shock")):
        v = R[k].dropna()
        z = (v.mean() - 0.5) / (np.sqrt(1 / 12) / np.sqrt(len(v)))
        p = 1 - 0.5 * (1 + erf(z / sqrt(2)))
        ps[k] = p
        print(f"  {k:<9}{len(v):>4}{v.mean():>11.2f}{(v >= 0.8).mean()*100:>11.0f}%{'20%':>10}{p:>14.3f}   {lab}")
    order = sorted(ps, key=ps.get)
    holm = {k: min(1.0, max(ps[j] * (len(ps) - i) for i, j in enumerate(order[:order.index(k) + 1]))) for k in ps}
    print("  Holm-corrected: " + ", ".join(f"{k} {holm[k]:.3f}" for k in order))
    try:
        F = fomc_days()
        on = R.et.dt.normalize().isin(F)
        tdays = pd.Series(days)
        base = tdays.isin(F).mean()
        print(f"\nFOMC decision days: {on.sum()} of {len(R)} entries ({on.mean()*100:.0f}%) against a base rate of "
              f"{base*100:.1f}% of trading days ({len(F)} decision dates found for 2025-26)")
    except Exception as e:
        print(f"\nFOMC calendar unavailable: {e}")
    hi = R[(R.shock60 >= 0.8) | (R.day0830 >= 0.8)]
    lo = R.drop(hi.index)
    print(f"\nHis results on 'news-footprint' entries (shock60 or day0830 in the top 20%): {len(hi)} trades, "
          f"${hi.net.sum():.2f}, ${hi.net.mean():.2f} each | the rest: {len(lo)} trades, ${lo.net.mean():.2f} each")
    R.to_csv(ROOT / "logs" / "his_news_ranks.csv", index=False)


if __name__ == "__main__":
    main()

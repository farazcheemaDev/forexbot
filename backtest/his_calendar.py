"""HIS TRADES AGAINST THE REAL NEWS CALENDAR - speeches, releases, surprises, to the minute.

The user, 2026-09-26: "he also does rely on news... some person who comes to speech and whatever the word
he says affects the market and also other economics stuff... cross check the dates". §24's news test
(his_news.py) read news only from its PRICE FOOTPRINT (abnormal bars) plus Fed decision days. It never
checked an actual calendar. This does: ForexFactory's calendar (backtest/ff_calendar.py; release times
to the second, impact, actual vs forecast, and FF's notes on unscheduled events), which is what a retail
news trader has open.

Event classes (USD only):
  REL      high-impact releases and decisions (CPI, NFP, PPI, claims, ISM, retail sales, GDP, PCE, FOMC
           statement / rate / minutes...) - everything high-impact that is not a speech
  SPEECH   any "... Speaks" / "Testifies" / "Press Conference" (Fed members, Treasury, the President)
  BIG      the President, the Fed Chair (Warsh / Powell), Treasury Sec Bessent, FOMC press conferences
  SURPRISE any event FF marks as a surprise or added after its release time (unscheduled news)
Features of a moment m:
  rel_60 / rel_180   a REL released in the 60 / 180 minutes before m
  next_rel_60        a REL due in the next 60 minutes
  speech_live        a SPEECH started in the 60 minutes before m (speeches run ~30-60 min)
  big_live           a BIG speech started in the 120 minutes before m
  mh_30              any USD medium/high event within 30 minutes either side
  surprise_120       a SURPRISE event in the 120 minutes before m
CONTROL: each entry against the SAME ET clock time on every other US trading day of his period
(2026-01-02..09-15), since releases and speeches sit at fixed clock times. Expected count = sum of the
per-entry control rates; z from the Poisson-binomial variance; Holm over 7. Repeated on his FIRST entry
of each day (same-day entries share the same news). Also: days he traded vs all days, his $ per trade
with and without news, and a trade-by-trade list of the news around each entry (logs/his_calendar.txt).

REGISTERED PREDICTION (2026-09-26, before running): news does not mark his entries. Every feature's rate
is within 0.7-1.5x of the same-clock-time control and none survives Holm; next_rel_60 is at or below
control. His trading days carry high-impact releases at the base rate. If speeches were his edge I would
expect speech_live / big_live at 2x+ with p < 0.01 - I do not expect that.

    python -m backtest.his_calendar
"""
from __future__ import annotations

import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.ff_calendar import load  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GMT = 5.0
HOLIDAYS = {"2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07"}
SPEECH_RX = r"Speaks|Testifies|Press Conference"
BIG_RX = r"President Trump|Warsh|Powell|Bessent|FOMC Press Conference"
FEATS = ("rel_60", "rel_180", "next_rel_60", "speech_live", "big_live", "mh_30", "surprise_120")


def classes(cal):
    u = cal[cal.currency == "USD"].copy()
    sp = u.name.str.contains(SPEECH_RX, case=False)
    ev = {
        "REL": u[(u.impact == "high") & ~sp].utc.to_numpy("datetime64[ns]"),
        "SPEECH": u[sp].utc.to_numpy("datetime64[ns]"),
        "BIG": u[sp & u.name.str.contains(BIG_RX, case=False)].utc.to_numpy("datetime64[ns]"),
        "MH": u[u.impact.isin(["medium", "high"])].utc.to_numpy("datetime64[ns]"),
        "SURPRISE": u[u.notice.str.contains("surprise|after its release", case=False)].utc.to_numpy("datetime64[ns]"),
    }
    return {k: np.sort(v) for k, v in ev.items()}, u


def any_in(arr, a, b):
    """any event in (a, b]"""
    return np.searchsorted(arr, b, side="right") > np.searchsorted(arr, a, side="right")


def feats(E, m):
    m = np.datetime64(m, "ns")
    mn = np.timedelta64(60, "s")
    return dict(rel_60=any_in(E["REL"], m - 60 * mn, m), rel_180=any_in(E["REL"], m - 180 * mn, m),
                next_rel_60=any_in(E["REL"], m, m + 60 * mn), speech_live=any_in(E["SPEECH"], m - 60 * mn, m),
                big_live=any_in(E["BIG"], m - 120 * mn, m), mh_30=any_in(E["MH"], m - 31 * mn, m + 30 * mn),
                surprise_120=any_in(E["SURPRISE"], m - 120 * mn, m))


def et_to_utc(ts):
    return ts.tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)


def zp(obs, ps):
    ps = np.asarray(ps)
    e, v = ps.sum(), (ps * (1 - ps)).sum()
    z = (obs - e) / sqrt(v) if v > 0 else 0.0
    return e, z, 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))


def holm(p):
    order = sorted(p, key=p.get)
    return {k: min(1.0, max(p[j] * (len(p) - i) for i, j in enumerate(order[:order.index(k) + 1]))) for k in p}


def test(entries, E, days, title, out):
    obs = {k: 0 for k in FEATS}
    ps = {k: [] for k in FEATS}
    for r in entries.itertuples():
        mine = feats(E, r.utc)
        clock = r.et - r.et.normalize()
        ctrl = [feats(E, et_to_utc(d + clock)) for d in days if d != r.et.normalize()]
        for k in FEATS:
            obs[k] += mine[k]
            ps[k].append(np.mean([c[k] for c in ctrl]))
    res = {k: zp(obs[k], ps[k]) for k in FEATS}
    h = holm({k: v[2] for k, v in res.items()})
    out.append(f"\n{title}: {len(entries)} entries against the same ET clock time on {len(days)} trading days")
    out.append(f"  {'feature':<14}{'his':>6}{'expected':>10}{'ratio':>7}{'z':>7}{'p':>7}{'Holm':>7}")
    for k in FEATS:
        e, z, p = res[k]
        out.append(f"  {k:<14}{obs[k]:>6}{e:>10.1f}{obs[k] / e if e else np.nan:>7.2f}{z:>+7.2f}{p:>7.3f}{h[k]:>7.3f}")


def main():
    cal = load()
    E, U = classes(cal)
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x["utc"] = x.open_time - pd.Timedelta(hours=GMT)
    x["et"] = x.utc.dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    x = x.sort_values("utc", kind="stable")
    days = [d for d in pd.bdate_range("2026-01-02", "2026-09-15") if f"{d:%Y-%m-%d}" not in HOLIDAYS]
    nq = x[x.symbol.str.startswith("NASDAQ")]
    out = [f"ForexFactory calendar: {len(cal)} events; USD: {len(E['REL'])} high-impact releases, {len(E['SPEECH'])} speeches "
           f"({len(E['BIG'])} President / Fed Chair / Treasury Sec / FOMC press conference), {len(E['SURPRISE'])} surprise-flagged."]
    test(nq, E, days, "NASDAQ, every entry", out)
    test(nq.groupby(nq.et.dt.normalize()).head(1), E, days, "NASDAQ, first entry of each day", out)
    oth = x[~x.symbol.str.startswith("NASDAQ")]
    oth = pd.concat([oth[oth.utc.dt.date != pd.Timestamp("2026-02-02").date()],
                     oth[oth.utc.dt.date == pd.Timestamp("2026-02-02").date()].head(1)])
    test(oth, E, days, "GOLD + SILVER (the 2026-02-02 burst of 37 counted once)", out)

    # days he traded NASDAQ vs all trading days
    tdays = set(nq.et.dt.normalize())
    def dayflags(d):
        a, b = et_to_utc(d), et_to_utc(d + pd.Timedelta(hours=24))
        f = {k: any_in(E[k], np.datetime64(a, "ns"), np.datetime64(b, "ns")) for k in ("REL", "BIG", "SURPRISE")}
        top = U[(U.utc > a) & (U.utc <= b) & U.name.str.contains(r"CPI|Non-Farm|Federal Funds Rate", case=False)]
        f["CPI/NFP/FOMC"] = len(top) > 0
        return f
    D = pd.DataFrame([dayflags(d) | {"his": d in tdays} for d in days])
    out.append(f"\nDAYS: {int(D.his.sum())} days he traded NASDAQ vs {int((~D.his.astype(bool)).sum())} days he did not")
    for k in ("REL", "BIG", "SURPRISE", "CPI/NFP/FOMC"):
        a, b = D[D.his][k].mean(), D[~D.his.astype(bool)][k].mean()
        out.append(f"  day has {k:<13} his days {a*100:5.1f}%   other days {b*100:5.1f}%")

    # $ per trade with / without news, and the trade-by-trade list
    rows = []
    for r in nq.itertuples():
        f = feats(E, r.utc)
        before = U[(U.utc <= r.utc) & (U.utc > r.utc - pd.Timedelta(hours=3)) & U.impact.isin(["medium", "high"])].tail(2)
        after = U[(U.utc > r.utc) & (U.utc <= r.utc + pd.Timedelta(hours=1)) & U.impact.isin(["medium", "high"])].head(1)
        sp = U[(U.utc <= r.utc) & (U.utc > r.utc - pd.Timedelta(hours=2)) & U.name.str.contains(SPEECH_RX, case=False)].tail(1)
        desc = lambda g, sgn: "; ".join(f"{e.name} ({sgn}{abs((r.utc - e.utc).total_seconds()) / 60:.0f}m{', ' + e.impact[0] if e.impact else ''}"  # noqa: E731
                                          f"{', a ' + e.actual + ' f ' + e.forecast if e.actual else ''})" for e in g.itertuples())
        rows.append(f | {"et": r.et, "side": r.side, "net": r.net, "before": desc(before, "-"), "speech": desc(sp, "-"),
                         "after": desc(after, "+")})
    T = pd.DataFrame(rows)
    out.append("\nNASDAQ $ per trade (net), with vs without each feature")
    for k in FEATS:
        a, b = T[T[k]].net, T[~T[k].astype(bool)].net
        out.append(f"  {k:<14} with: n {len(a):>2}  ${a.mean() if len(a) else np.nan:7.2f}  win {(a > 0).mean()*100 if len(a) else np.nan:4.0f}%"
                   f"   without: n {len(b):>2}  ${b.mean():7.2f}  win {(b > 0).mean()*100:4.0f}%")
    out.append("\nEVERY NASDAQ ENTRY and the USD news around it (medium/high in the 3 h before, any speech in the 2 h before, "
               "medium/high in the hour after; m = minutes)")
    for r in T.itertuples():
        out.append(f"  {r.et:%Y-%m-%d %H:%M:%S} ET {r.side:<4} ${r.net:>7.2f} | before: {r.before or '-'} | speech: {r.speech or '-'}"
                   f" | after: {r.after or '-'}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_calendar.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()

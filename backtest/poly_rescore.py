"""POLYMARKET FAVOURITES, RE-SCORED WITHOUT THE EARLY-RESOLUTION BIAS (2026-10-10)

poly_forward.py's live log showed markets priced 80-90c resolving YES 94.7% of the time against an 84.9% average price
(+9.8 points, beyond 2 se on events) - flagged at once as probably the EARLY-RESOLUTION bias: a "will X happen by date D"
market resolves YES the moment X happens, but a NO has to wait for D, so the resolved-so-far sample is stacked with
YESes. The council (2026-10-10) asked for the re-score that removes it, on the log already in hand:
    ON SCHEDULE   only markets that resolved at or after their scheduled end date (minus 1 day)
    DEADLINE PAST every market whose scheduled end date passed >= 3 days ago, whatever its resolution time - the full
                  population the bias cannot reach (markets still unresolved are counted and reported, not dropped silently)
    EARLY         markets that resolved more than 1 day before their scheduled end date (where the bias lives)
Gap = resolved-YES rate minus the average snapshot price; se on EVENTS (several markets of one event are one bet).

REGISTERED BEFORE RUNNING (2026-10-10)
    P1  The 80-90c excess is mostly the bias: ON SCHEDULE and DEADLINE PAST, the 80-90c gap is under +3 points (the
        council's kill line) - or its 2-se interval includes zero.
    P2  EARLY resolutions are YES at well above their price in every band above 15c.

RESULT (2026-10-10 00:53 UTC, logs/poly_rescore.txt; 2,647 markets tracked, 796 resolved)
    P2 RIGHT, and it is large: markets resolved EARLY went YES +26 to +36 points above their price in every band from 15c
       to 90c (80-90c: 13 of 13 YES).
    P1 - KILLED BY THE REGISTERED RULE, though not by a small number: removing the early resolutions takes the 80-90c gap
       from +10.1 to +7.9 points ON SCHEDULE (se 4.8, 26 markets / 23 events) and +8.1 among all markets whose deadline
       passed (se 4.6, 27 / 24). Both are inside 2 se of zero, which the rule set before the run counts as a kill. Honest
       reading: what remains is +8 points the sample cannot tell from zero - no edge to fund, nothing proven either way.
    Also visible (not a new test): long shots priced 5-15c resolved YES 2.9% against 9.1% on schedule (-6.2 points, 2 se)
    - the favourite-longshot bias again, as in the weather markets; its holding period runs to each market's deadline,
    so its return per day is unknown from this log.

    python -m backtest.poly_rescore
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SNAP = ROOT / "logs" / "poly_snapshots.csv"
LOG = ROOT / "logs" / "poly_rescore.txt"
BANDS = [(0.00, 0.05), (0.05, 0.15), (0.15, 0.30), (0.30, 0.50), (0.50, 0.65), (0.65, 0.80), (0.80, 0.90), (0.90, 1.00)]


def table(d: pd.DataFrame, label: str, lines: list):
    lines.append(f"{label}: {len(d)} markets, {d.event_id.nunique()} events")
    lines.append(f"  {'band':10} {'n':>5} {'events':>7} {'avg price':>10} {'resolved YES':>13} {'gap':>8} {'se (events)':>12}")
    out = {}
    for a, b in BANDS:
        g = d[(d.price >= a) & (d.price < b)]
        if len(g) < 5:
            continue
        ev = g.groupby("event_id").agg(y=("yes", "mean"), p=("price", "mean"))
        gap = g.yes.mean() - g.price.mean()
        se = (ev.y - ev.p).std(ddof=1) / np.sqrt(len(ev)) if len(ev) > 1 else np.nan
        out[(a, b)] = (len(g), len(ev), gap, se)
        lines.append(f"  {a:.2f}-{b:.2f} {len(g):5} {len(ev):7} {g.price.mean():10.3f} {g.yes.mean():13.3f} {gap:+8.3f} {se:12.3f}"
                     + ("  *" if np.isfinite(se) and abs(gap) > 2 * se else ""))
    lines.append("")
    return out


def main():
    s = pd.read_csv(SNAP)
    s["end"] = pd.to_datetime(s.end_date, utc=True, errors="coerce")
    s["rts"] = pd.to_datetime(s.resolved_ts, utc=True, errors="coerce")
    s["snap"] = pd.to_datetime(s.ts_utc, utc=True, errors="coerce")
    now = pd.Timestamp.now(tz="UTC")
    res = s[s.resolved.astype(str) == "1"].copy()
    res["yes"] = (res.outcome.astype(str).str.upper().isin(["YES", "1", "1.0", "TRUE"])).astype(int)
    lines = [f"backtest/poly_rescore.py, {now:%Y-%m-%d %H:%M} UTC; logs/poly_snapshots.csv: {len(s)} markets tracked, {len(res)} "
             f"resolved; outcomes seen: {sorted(res.outcome.astype(str).unique())[:6]}", ""]
    table(res, "ALL RESOLVED (as poly_forward --report)", lines)
    early = res[res.rts < res.end - pd.Timedelta(days=1)]
    sched = res[res.rts >= res.end - pd.Timedelta(days=1)]
    table(early, "EARLY - resolved > 1 day before the scheduled end", lines)
    a = table(sched, "ON SCHEDULE - resolved at/after the scheduled end (-1 day)", lines)
    past = s[s.end < now - pd.Timedelta(days=3)].copy()
    pr = past[past.resolved.astype(str) == "1"].copy()
    pr["yes"] = (pr.outcome.astype(str).str.upper().isin(["YES", "1", "1.0", "TRUE"])).astype(int)
    lines.append(f"DEADLINE PAST >= 3 days: {len(past)} markets, {len(pr)} resolved, {len(past) - len(pr)} still unresolved "
                 f"(disputed / extended / not yet settled - left out)")
    b = table(pr, "DEADLINE PAST - resolved", lines)
    for nm, o in (("ON SCHEDULE", a), ("DEADLINE PAST", b)):
        if (0.80, 0.90) in o:
            n, ne, gap, se = o[(0.80, 0.90)]
            verdict = "KILL (under +3 points or within 2 se of zero)" if gap < 0.03 or not (np.isfinite(se) and gap > 2 * se) \
                else "SURVIVES"
            lines.append(f"P1 {nm}: 80-90c gap {gap:+.3f} (se {se:.3f}, {n} markets / {ne} events) -> {verdict}")
        else:
            lines.append(f"P1 {nm}: fewer than 5 markets in 80-90c - not decidable")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

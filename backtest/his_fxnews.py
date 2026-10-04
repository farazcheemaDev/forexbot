"""DOES HE TRADE NON-DOLLAR NEWS? - every non-USD ForexFactory event around his NASDAQ entries.

WHY (the user: "20 years of FOREX experience")
    s28 (his_calendar.py) tested the calendar for USD events only - releases, Fed speakers, the Chair, surprises - and
    nothing survived Holm. An FX trader follows every currency's news. His sittings fall around 10:00-11:30 New York,
    the European afternoon, when ECB / Bank of England officials speak and European data lands, and CNY data moves
    risk overnight. ff_calendar.csv already holds 2,900+ non-USD events (EUR 861, GBP 537, JPY 356, CNY 212, ...).

METHOD: his_calendar.test() unchanged - each of his entries (corrected clock) against the same New York clock time on
every other trading day - with the event classes rebuilt from non-USD rows:
    REL      non-USD high-impact releases (not speeches)
    SPEECH   non-USD speeches
    BIG      central-bank governors: Lagarde, Bailey, Ueda, Macklem, Bullock, Schlegel / Jordan, Orr / Hawkesby, Pan
    MH       any non-USD medium/high event
    SURPRISE non-USD events flagged as surprises
And the same again for EUR + GBP alone (the European afternoon).

REGISTERED PREDICTIONS (2026-10-04, before running)
    1. Nothing survives Holm in either run; every ratio lies within 0.5-2.
    2. If anything leans, it is European speeches (speech_live) - the hours fit.

    python -m backtest.his_fxnews
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_calendar import HOLIDAYS, SPEECH_RX, test  # noqa: E402
from backtest.his_tape import entries  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GOV_RX = r"lagarde|bailey|ueda|macklem|bullock|schlegel|jordan|orr|hawkesby|pan gongsheng|governor"


def load():
    c = pd.read_csv(ROOT / "strategy_analysis" / "data" / "ff_calendar.csv")
    c["utc"] = pd.to_datetime(c.utc)
    if c.utc.dt.tz is not None:
        c["utc"] = c.utc.dt.tz_convert("UTC").dt.tz_localize(None)
    c["notice"] = c.notice.fillna("").astype(str)
    c["name"] = c.name.fillna("").astype(str)
    return c


def classes(c, keep):
    u = c[keep].copy()
    sp = u.name.str.contains(SPEECH_RX, case=False)
    ev = {"REL": u[(u.impact == "high") & ~sp].utc, "SPEECH": u[sp].utc,
          "BIG": u[sp & u.name.str.contains(GOV_RX, case=False)].utc,
          "MH": u[u.impact.isin(["medium", "high"])].utc,
          "SURPRISE": u[u.notice.str.contains("surprise|after its release", case=False)].utc}
    return {k: np.sort(v.to_numpy("datetime64[ns]")) for k, v in ev.items()}, u


def main():
    c = load()
    x = entries()
    days = [d for d in pd.bdate_range("2026-01-02", "2026-09-15") if f"{d:%Y-%m-%d}" not in HOLIDAYS]
    out = []
    for title, keep in (("NON-USD, every currency", ~c.currency.isin(["USD", "All"])),
                        ("EUR + GBP (the European afternoon)", c.currency.isin(["EUR", "GBP"]))):
        E, u = classes(c, keep)
        out.append(f"\n{title}: {len(E['REL'])} high-impact releases, {len(E['SPEECH'])} speeches "
                   f"({len(E['BIG'])} governors), {len(E['MH'])} medium/high, {len(E['SURPRISE'])} surprises")
        test(x, E, days, "NASDAQ, every entry (corrected clock)", out)
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_fxnews.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()

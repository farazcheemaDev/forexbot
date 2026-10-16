"""WERE HIS ENTRIES PLACED LIVE? - the OPENING tickets on the broker's counter (2026-10-13)

WHY      his_strategy s56: being right about the next minute 95% of the time is beyond public data, so either a private
         live source (A) or entries not decided live (B). his_tickets.py proved the CLOSES live, but the statement prints
         only closing tickets. The app's History shows, for each tapped trade, an "ID" (the closing ticket) AND an "Open
         Ticket" - in the 55 screenshots the user sent on 2026-09-10 ("Strategy video/"), never read for this. One
         counter numbers every order of every client (~2,700 a day). A position opened live takes the counter's value at
         its open time: below its own close ticket by the orders placed in between (more for a longer hold, more in a busy
         hour), and in sequence with his other trades' tickets. A position created at the close (or later) would sit
         right next to its close ticket whatever the hold.

DATA     OPEN below: (closing ID, open ticket) read off the expanded rows of the screenshots, 20 trades (NASDAQ, gold,
         silver); times and the closing tickets of all 91 trades from strategy_analysis/statement_trades.csv (gitignored).

REGISTERED BEFORE THE RUN (2026-10-13): if B, the open-to-close ticket gap is ~1 at every hold and does not grow with it;
if live, every open ticket sits below its close, every event (opens and closes of all trades) is in counter order, and
the gap grows with the hold (log-log corr > 0.5).

RESULT (2026-10-13, logs/his_open_tickets.txt) - HIS ENTRIES WERE PLACED LIVE. 20 of 20 matched by closing ID. All 111
    events (91 closes + 20 opens) in counter order, 0 out of sequence; every open ticket below its own close; the gap
    runs 1..52 tickets (median 6) and grows with the hold (log-log corr +0.53; the rest is the hour - 2 tickets in 3.7
    minutes late in the New York evening, 52 in 3 minutes in the New York morning). Only 2 of 20 gaps are exactly 1
    (holds of 10 s and 56 s). He trades in busier hours than the record's average (5.1 vs 1.9 tickets a minute).
    Hypothesis B (entries not decided live) is refuted; his edge is a live read (his_strategy s57).

    python -m backtest.his_open_tickets
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "logs" / "his_open_tickets.txt"

# closing ID -> open ticket, from the app's History screenshots (Strategy video/, 2026-09-10)
OPEN = {13772286: 13772284, 13313277: 13313276, 13766506: 13766500, 13766494: 13766490, 13720716: 13720715,
        13673738: 13673735, 13672072: 13672065, 13646721: 13646719, 13646717: 13646714, 13206057: 13206040,
        13215001: 13214949, 13224444: 13224435, 13248009: 13247998, 13252800: 13252778, 13263023: 13263015,
        13278242: 13278235, 13284330: 13284327, 13294567: 13294561, 13303736: 13303734, 13303743: 13303738}


def main():
    s = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time", "close_time"])
    s = s.dropna(subset=["ticket"]).astype({"ticket": np.int64})
    m = s[s.ticket.isin(OPEN)].copy()
    m["open_ticket"] = m.ticket.map(OPEN)
    m["hold_s"] = (m.close_time - m.open_time).dt.total_seconds()
    m["gap"] = m.ticket - m.open_ticket
    out = [f"backtest/his_open_tickets.py; {len(m)} of {len(OPEN)} screenshot trades matched to the statement by closing ID", ""]
    out.append(m[["open_time", "close_time", "symbol", "side", "hold_s", "open_ticket", "ticket", "gap"]]
               .sort_values("open_time").to_string(index=False))
    out.append("")
    # every event of the record, in time order: the 91 closes + these opens
    ev = pd.concat([pd.DataFrame({"t": s.close_time, "k": s.ticket, "what": "close"}),
                    pd.DataFrame({"t": m.open_time, "k": m.open_ticket, "what": "open"})]).sort_values(["t", "k"], kind="stable")
    dk = np.diff(ev.k.to_numpy())
    dt = np.diff(ev.t.to_numpy()).astype("timedelta64[s]").astype(float)
    bad = int(((dk <= 0) & (dt > 0)).sum())
    out.append(f"all {len(ev)} events (91 closes + {len(m)} opens) in time order: tickets out of order {bad}")
    below = bool((m.open_ticket < m.ticket).all())
    r = np.corrcoef(np.log(m.hold_s.clip(lower=1)), np.log(m.gap.clip(lower=1)))[0, 1]
    out.append(f"open ticket below its own close in every trade: {below}; gap 1..{m.gap.max()} tickets (median {m.gap.median():.0f}); "
               f"log gap vs log hold corr {r:+.2f}; gaps of exactly 1: {(m.gap == 1).sum()} of {len(m)}")
    out.append(f"tickets a minute during his holds: median {np.median(m.gap / (m.hold_s / 60)):.1f} (range "
               f"{(m.gap / (m.hold_s / 60)).min():.1f}..{(m.gap / (m.hold_s / 60)).max():.1f}); the whole record averages "
               f"{(s.ticket.max() - s.ticket.min()) / ((s.close_time.max() - s.close_time.min()).total_seconds() / 60):.1f}")
    live = bad == 0 and below and r > 0.5
    out.append("")
    out.append("VERDICT: entries placed LIVE (in counter order, gaps grow with the hold)" if live else
               "VERDICT: NOT consistent with live entries - look closer")
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

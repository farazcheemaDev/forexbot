"""WAS HIS RECORD PLACED LIVE? - the broker's closing-ticket counter against the stamped close times (2026-10-12)

WHY      Every test of him finds ordinary moments, nothing before them, ordinary moves after - and only the SIDE right.
         That is also exactly what a record built AFTER the fact leaves (pick moments where the price later went +7
         first). s34's check (his exits look like a mechanical target) cannot tell the two apart: a hindsight record that
         exits at the first touch of +7 looks the same. The tickets can. The statement prints each trade's CLOSING-deal
         ticket (s39), drawn from one counter that the broker advances for every client (~2,700 a day). A trade closed
         live gets the counter's value at its stamped close time; a trade entered later gets the value at entry time -
         out of order, or a near-consecutive run for closes minutes apart.

DATA     strategy_analysis/statement_trades.csv (gitignored) + his_statement_2026-10_trades.csv (no tickets).

REGISTERED BEFORE THE RUN (2026-10-12): if live, tickets rise with close time except inside one second, and the ticket
gap between consecutive closes grows with the time gap (no run of <= 2 tickets for closes >= 3 minutes apart).

RESULT (2026-10-12, logs/his_tickets.txt) - LIVE. 91 trades: the tickets rise with close time in all 90 consecutive
    pairs (two pairs closed in the same second); log ticket gap vs log time gap corr +0.99 (31 min -> 153 tickets,
    7.1 h -> 1,666, 3 min -> 5-10 in the evening); of 45 pairs >= 3 min apart none carries <= 2 tickets (min 5). The
    trades were closed when the statement says, in sequence with the broker's other clients' orders.

    python -m backtest.his_tickets
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "logs" / "his_tickets.txt"


def main():
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["close_time"])
    x = x.dropna(subset=["ticket"]).sort_values(["close_time", "ticket"], kind="stable").reset_index(drop=True)
    days = (x.close_time.max() - x.close_time.min()).total_seconds() / 86400
    dt = x.close_time.diff().dt.total_seconds().to_numpy()[1:]
    dk = np.diff(x.ticket.to_numpy())
    same_sec = dt == 0
    out = [f"backtest/his_tickets.py; {len(x)} trades with tickets, {x.close_time.min():%Y-%m-%d} .. {x.close_time.max():%Y-%m-%d}; "
           f"counter {(x.ticket.max() - x.ticket.min()) / days:,.0f} tickets a day on average", ""]
    out.append(f"tickets rising with close time: {(dk > 0).sum()} of {len(dk)} consecutive pairs; the rest share one second: "
               f"{bool(np.all(same_sec[dk <= 0]))}")
    far = dt >= 180
    out.append(f"closes >= 3 min apart: {far.sum()} pairs, ticket gap min {dk[far].min():.0f}, median {np.median(dk[far]):.0f}; "
               f"pairs with <= 2 tickets: {int((dk[far] <= 2).sum())}")
    r = np.corrcoef(np.log(dt[(dt > 0) & (dk > 0)]), np.log(dk[(dt > 0) & (dk > 0)]))[0, 1]
    out.append(f"log ticket gap vs log time gap: corr {r:+.2f}")
    out.append("")
    out.append("largest gaps: time (s) -> tickets")
    for i in np.argsort(dt)[::-1][:6]:
        out.append(f"   {dt[i]:>9,.0f} s -> {dk[i]:>6,.0f}")
    out.append("")
    out.append("VERDICT: closes recorded LIVE, in sequence with the broker's other orders" if (dk[far] > 2).all()
               and np.all(same_sec[dk <= 0]) else "VERDICT: tickets out of sequence - look closer")
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

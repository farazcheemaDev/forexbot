"""HE TRADES TO A ~10% MONTHLY TARGET - and how large he trades to reach it (2026-10-13)

The user: he has said that "around 10 percent is safer to trade with". The statement, month by month: the trade at
which the month's trading profit crosses 10% of the capital held, what he did after it, and his size as notional /
capital and as % of the account per NASDAQ point. Capital per month = trading P&L / return, from his_strategy s16.

RESULT (2026-10-13, logs/his_monthly_target.txt): from April every month lands at +7.8..+13.6%; he stops at or just past
    10% (April: crossed on his 7th trade, then none; June: three trades on ONE day, +11.1%, then none; July one more,
    September two small ones) or just short (May +7.8%, August +9.4%). Size: notional 24x the account in January, 57-58x
    in April-May, 85-176x from June; a NASDAQ point is 0.2-0.6% of the account, with no stop. He needs 3-5 wins a month,
    so he can wait for the clearest moments: ~5 NASDAQ trades in ~11,000 session minutes a month.

    python -m backtest.his_monthly_target
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CAP = {1: 207 / 0.127, 2: 359 / 0.216, 3: 139 / 0.038, 4: 404 / 0.119, 5: 271 / 0.078, 6: 375 / 0.111, 7: 463 / 0.136,
       8: 495 / 0.094, 9: 615 / 0.117}


def main():
    s = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time", "close_time"])
    s = s.sort_values("close_time", kind="stable")
    s["m"] = s.close_time.dt.month
    out = ["backtest/his_monthly_target.py - month by month, all instruments (capital from his_strategy s16)", ""]
    for m, g in s.groupby("m"):
        c = CAP[m]
        cum = g.net.cumsum() / c * 100
        cross = np.flatnonzero(cum.to_numpy() >= 10)
        line = f"2026-{m:02d}: capital ~${c:,.0f}, {len(g)} trades on {g.close_time.dt.date.nunique()} days, month {cum.iloc[-1]:+.1f}%"
        if len(cross):
            f = cross[0]
            after = g.iloc[f + 1:]
            line += f" | crossed 10% on trade {f + 1} ({g.close_time.iloc[f]:%m-%d %H:%M}); after it {len(after)} trades, {after.net.sum() / c * 100:+.1f}%"
        else:
            line += " | did not reach 10%"
        out.append(line)
    n = s[s.symbol.str.startswith("NASDAQ")].copy()
    n["cap"] = n.m.map(CAP)
    n["notional_x"] = n.lots * 100 * n.open_price / n.cap
    n["pct_per_point"] = n.lots * 100 / n.cap * 100
    out += ["", "NASDAQ size by month (medians): lots, notional / capital, % of the account per point",
            n.groupby("m")[["lots", "notional_x", "pct_per_point"]].median().round(2).to_string()]
    txt = "\n".join(out)
    (ROOT / "logs" / "his_monthly_target.txt").write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

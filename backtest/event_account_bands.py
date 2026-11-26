"""THE EVENT ACCOUNT'S SCORECARD BANDS (2026-11-27): the backtest range of event_bot.py's book set for every N-day stretch.

Same construction as scorecard_bands.py (which builds dashboard_bands.json for the whole machine) - same windows, same 33
quantile levels, same 29 stretch lengths, books in DOLLARS of the stretch's starting account (they add up to the account,
asserted) - for the REGISTERED set only: carry x1.0 (twice the deployed column), crash bids, capit2, news, NASDAQ dip.
Written to event_bands.json (repo root, committed); dashboard_push.py places the events account's live result in it from day
7. The set and its sizing are the ones backtest/event_account_registered.py priced BEFORE any live day (logs/
event_account_registered.txt); this file adds no choice, only the distribution of every stretch length.

    python -m backtest.event_account_bands      (writes event_bands.json and logs/event_account_bands.txt)
"""
import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest.scorecard_bands import LENGTHS, LEVELS, band, dollar_windows, pctile, windows  # noqa: E402

warnings.filterwarnings("ignore")
OUT = ROOT / "event_bands.json"
LOG = ROOT / "logs" / "event_account_bands.txt"
CARRY_X = 2.0            # the deployed carry column is x0.5; the events account runs x1.0


def main():
    from backtest.all_books import machine_books, ndx_dip, news_book
    M = machine_books()
    idx = M[0].index
    news_all, ndx_all = news_book(), ndx_dip()
    news = news_all.reindex(idx).fillna(0.0)
    news_from = news[news != 0].index[0]
    nw = [news_all.reindex(x.index).fillna(0.0).to_numpy() for x in M]
    nd = [ndx_all.reindex(x.index).fillna(0.0).to_numpy() for x in M]
    series = {"carry": [x["carry"].to_numpy() * CARRY_X for x in M], "bids": [x["bids"].to_numpy() for x in M],
              "capit2": [x["capit2"].to_numpy() for x in M], "news": nw, "ndx": nd}
    tot = [sum(series[nm][k] for nm in series) for k in range(len(M))]
    nf = [int(np.searchsorted(x.index, news_from)) for x in M]
    out = dict(made=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC", source="backtest/event_account_bands.py",
               span=f"{idx[0]:%Y-%m-%d} .. {idx[-1]:%Y-%m-%d}", levels=LEVELS, lengths=LENGTHS, books={})
    for nm, rs in series.items():
        out["books"][nm] = {str(n): band(np.concatenate([dollar_windows(r, t, n, nf[k] if nm == "news" else 0)
                                                          for k, (r, t) in enumerate(zip(rs, tot))]))
                            for n in LENGTHS}
    assert all(len(r) == len(t) for rs in series.values() for r, t in zip(rs, tot))
    out["total"] = {str(n): band(np.concatenate([windows(pd.Series(t), n, compound=True) for t in tot])) for n in LENGTHS}
    chk = sum(dollar_windows(series[nm][0], tot[0], 30) for nm in series) - windows(pd.Series(tot[0]), 30, compound=True)
    assert np.abs(chk).max() < 1e-9, f"books do not add up to the account: {np.abs(chk).max()}"
    OUT.write_text(json.dumps(out, separators=(",", ":")))

    lines = [f"backtest/event_account_bands.py, {out['made']}; {out['span']}; news from {news_from:%Y-%m-%d}; carry x{CARRY_X / 2:g}; "
             f"10 slot orderings pooled; the account = carry + bids + capit2 + news + ndx"]
    lines.append("ACCOUNT, every N-day stretch (compounded), % of the start:")
    lines.append(f"{'days':>5} {'p1':>7} {'p5':>7} {'p10':>7} {'p25':>7} {'p50':>7} {'p75':>7} {'p95':>7}  {'below 0':>8}")
    for n in (14, 30, 42, 60, 90, 120, 180, 365):
        b = out["total"][str(n)]
        q = dict(zip(LEVELS, b["q"]))
        v = np.concatenate([windows(pd.Series(t), n, compound=True) for t in tot])
        lines.append(f"{n:>5} {q[1] * 100:>+7.1f} {q[5] * 100:>+7.1f} {q[10] * 100:>+7.1f} {q[25] * 100:>+7.1f} {q[50] * 100:>+7.1f} "
                     f"{q[75] * 100:>+7.1f} {q[95] * 100:>+7.1f}  {np.mean(v < 0) * 100:>7.1f}%")
    lines.append("")
    lines.append("by book, 90 days, $ as a share of the start (p5 / p50 / p95; idle = no P&L at all):")
    for nm in series:
        b = out["books"][nm]["90"]
        q = dict(zip(LEVELS, b["q"]))
        lines.append(f"  {nm:<8} {q[5] * 100:>+6.1f} {q[50] * 100:>+6.1f} {q[95] * 100:>+6.1f}   idle {b['idle'] * 100:.0f}%")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

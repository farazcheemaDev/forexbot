"""IS THE NOISE RULE WHAT THE NASDAQ TRADER USES TO KNOW HIS DIRECTION? (2026-11-21)

THE USER (2026-11-21), after hearing what the NASDAQ 'noise area' bot (forex_bot.py) would earn: "could this be something that he, the
NASDAQ trader, uses to see the directions of his trades beforehand". The noise rule (Zarattini, Aziz & Barbon; fx_intraday_pub.noise):
a band around the day's open (the max / min of the open and the previous close) widened by sigma(m), the average absolute move from the
open at that minute over the previous 14 sessions; a close above it -> long, below -> short, inside -> flat; the bot decides at :00 / :30
from 10:00 New York. His NASDAQ side was never compared with it (his_strategy.md: no public feature tested so far carries his side).
DATA   his NASDAQ trades: the broker statement (strategy_analysis/statement_trades.csv, 46 trades; statement clock UTC+4 in winter, UTC+5
       in summer - his_clock_check.to_utc, as his_direction.py reads it) and the later ones (logs/his_new_trades.csv, New York times)
       while the minute data lasts; Exness USTECm 1-minute bars 2026-01-01 .. 2026-10-09 (strategy_analysis/data/mt5_1m/USTECm.parquet;
       his broker's NASDAQ = Exness + a constant, minute moves corr 0.992 - his_chart_capfx.py), cut into sessions by
       fx_intraday_pub.session_df.
AT EACH CLICK inside the cash session (09:31-16:00 New York): the last CLOSED minute before it (he clicks ~14 s after a minute's close,
       his_click_timing.py) and the band at that minute -> STATE +1 above / -1 below / 0 inside; and the BOT'S POSITION = the rule's
       decision at the last :00 / :30 checkpoint already closed (flat before 10:01).
MEASURES  his clicks in / out of the cash session; in / out of the band; his side against the state and against the bot's position:
       agreement, binomial test against 50%; his banked points when he agreed and when he did not (descriptive, few trades).
REGISTERED BEFORE THE FIRST NUMBER (2026-11-21)
  H1  His side agrees with the state on at most 65% of his cash-session clicks where the price is outside the band, binomial p > 0.05:
      he is not following the noise rule. (80%)
  H2  At least a third of his cash-session clicks come while the price is INSIDE the band, where the rule would not trade. (55%)
  H3  His side agrees with the bot's position on at most 65% of the clicks where the bot holds one. (80%)

    python -m backtest.his_noise
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOG = ROOT / "logs" / "his_noise.txt"
WINTER, GMT = 4.0, 5.0                                   # his_direction.py's clock


def his_trades() -> pd.DataFrame:
    from backtest.his_clock_check import to_utc
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x = x[x.symbol.str.startswith("NASDAQ")].copy()
    u = to_utc(x.open_time, WINTER, GMT)
    et = u.dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    side = np.where(x.side == "BUY", 1, -1)
    a = pd.DataFrame({"et": et.to_numpy(), "side": side, "pts": side * (x.close_price - x.open_price).to_numpy(), "src": "statement"})
    n = pd.read_csv(ROOT / "logs" / "his_new_trades.csv")
    b = pd.DataFrame({"et": pd.to_datetime(n.date + " " + n.ny_time), "side": np.where(n.side == "BUY", 1, -1),
                      "pts": n.banked.astype(float), "src": "later"})
    return pd.concat([a, b], ignore_index=True).sort_values("et").reset_index(drop=True)


def bands(A: dict, prev: np.ndarray, look: int = 14):
    """The noise band's two edges for every session and minute (fx_intraday_pub.noise's construction)."""
    O, C = A["o"], A["c"]
    op = O[:, :1]
    sig = pd.DataFrame(np.abs(C / op - 1)).rolling(look).mean().shift(1).to_numpy()
    base_u = np.maximum(op[:, 0], prev)[:, None]
    base_l = np.minimum(op[:, 0], prev)[:, None]
    return base_u * (1 + sig), base_l * (1 - sig), C


def main():
    from scipy.stats import binomtest
    from backtest.fx_intraday_pub import session_df
    d = pd.read_parquet(ROOT / "strategy_analysis" / "data" / "mt5_1m" / "USTECm.parquet")
    A, dates, prev = session_df(d, "NASDAQ")[:3]
    UB, LB, C = bands(A, np.asarray(prev, float))
    di = {pd.Timestamp(x).normalize(): i for i, x in enumerate(dates)}
    T = his_trades()
    rows, outside_session, no_data = [], 0, 0
    for r in T.itertuples():
        day = r.et.normalize()
        sec = (r.et - day - pd.Timedelta(hours=9, minutes=30)).total_seconds()
        if not 60 <= sec < 390 * 60:
            outside_session += 1
            continue
        i = di.get(day)
        m = int(sec // 60) - 1                           # the last minute bar that has closed
        if i is None or not (np.isfinite(UB[i, m]) and np.isfinite(C[i, m])):
            no_data += 1
            continue
        state = 1 if C[i, m] > UB[i, m] else (-1 if C[i, m] < LB[i, m] else 0)
        pos = 0
        for md in range(30, m + 1, 30):
            if np.isfinite(UB[i, md]):
                pos = 1 if C[i, md] > UB[i, md] else (-1 if C[i, md] < LB[i, md] else 0)
        width = (UB[i, m] - LB[i, m]) / C[i, m]
        rows.append(dict(et=r.et, side=r.side, pts=r.pts, src=r.src, state=state, pos=pos, width=width,
                         dist=(C[i, m] - UB[i, m]) / C[i, m] if state > 0 else ((C[i, m] - LB[i, m]) / C[i, m] if state < 0 else 0.0)))
    X = pd.DataFrame(rows)
    out = [f"backtest/his_noise.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; his NASDAQ trades {len(T)} (statement "
           f"{int((T.src == 'statement').sum())}, later {int((T.src == 'later').sum())}); Exness USTECm minutes "
           f"{pd.Timestamp(dates[0]):%Y-%m-%d} .. {pd.Timestamp(dates[-1]):%Y-%m-%d}", "",
           f"  outside the cash session (09:31-16:00 New York): {outside_session}; no minute data / sigma not ready: {no_data}; "
           f"scored: {len(X)}"]
    ins = X[X.state == 0]
    o = X[X.state != 0]
    agree = int((o.side == o.state).sum())
    p1 = binomtest(agree, len(o), 0.5).pvalue if len(o) else float("nan")
    out.append(f"  inside the band (the rule would be flat): {len(ins)} of {len(X)} ({len(ins) / max(len(X), 1):.0%}); his banked points "
               f"there: mean {ins.pts.mean():+.2f}, won {(ins.pts > 0).mean():.0%}")
    out.append(f"  outside the band: {len(o)}; his side = the rule's side on {agree} ({agree / max(len(o), 1):.0%}), binomial p {p1:.3f}; "
               f"banked when agreeing {o[o.side == o.state].pts.mean():+.2f} ({(o[o.side == o.state].pts > 0).mean():.0%} won), "
               f"against {o[o.side != o.state].pts.mean():+.2f} ({(o[o.side != o.state].pts > 0).mean():.0%} won)")
    hb = X[X.pos != 0]
    agree_b = int((hb.side == hb.pos).sum())
    p3 = binomtest(agree_b, len(hb), 0.5).pvalue if len(hb) else float("nan")
    out.append(f"  the BOT holds a position at {len(hb)} of his clicks; his side = the bot's side on {agree_b} "
               f"({agree_b / max(len(hb), 1):.0%}), binomial p {p3:.3f}; the bot is flat at {int((X.pos == 0).sum())}")
    out.append(f"  band width at his clicks: median {X.width.median():.2%} of the price")
    out += ["", "  each scored click (New York time, his side, the band state, the bot's position, his banked points):"]
    for r in X.itertuples():
        out.append(f"    {r.et:%Y-%m-%d %H:%M:%S}  {'BUY ' if r.side > 0 else 'SELL'}  state {r.state:+d}  bot {r.pos:+d}  {r.pts:+7.2f} pts  {r.src}")
    ok = lambda b: "RIGHT" if b else "WRONG"  # noqa: E731
    out += ["", "REGISTERED PREDICTIONS",
            f"  H1 agrees with the state on <= 65% outside the band, p > 0.05 -> {ok(agree / max(len(o), 1) <= 0.65 and p1 > 0.05)} "
            f"({agree} of {len(o)}, p {p1:.3f})",
            f"  H2 >= a third of cash-session clicks inside the band -> {ok(len(ins) >= len(X) / 3)} ({len(ins)} of {len(X)})",
            f"  H3 agrees with the bot's position <= 65% -> {ok(agree_b / max(len(hb), 1) <= 0.65)} ({agree_b} of {len(hb)}, p {p3:.3f})"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

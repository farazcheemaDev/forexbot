"""THE NEWS BOT'S WINDOW: how much of a data surprise's jump is still there 0.5 / 1 / 2 / 5 / 10 / 60 SECONDS after the
number prints - on Exness's own ticks, at the real ask / bid (2026-10-12)

THE USER (2026-10-12): "yes run the seconds capture test". fx_surprises_1m.py: a high-impact release moves its currency
the surprise's way 81% of the time within 5 minutes (+14bp), but entered ONE MINUTE after, only +0.8bp is left (the
spread takes it). The only way a forex bot can use the information that drives forex is to read the official number the
instant it is published (US payrolls / CPI at 08:30:00 ET on bls.gov, etc.) and trade within seconds. This measures what
that bot would have got, on every 2026 release with an Exness tick history (MT5 ticks start 2026-01).

EVENTS  fx_surprises.events(): high-impact releases with a forecast, |score| >= 1, 2026-01 .. 2026-09; the release
        second is ForexFactory's (e.g. 12:30:00 UTC). Pairs: a USD release on EURUSD, GBPUSD, USDJPY (the dollar's side);
        any other currency's on its own USD pair (EURUSD GBPUSD USDJPY AUDUSD NZDUSD USDCAD USDCHF, Exness "m" symbols).
TRADE   the bot knows the surprise's sign at the release second (it read the number). Entered d seconds after the
        release at the first tick at or after t0 + d, at the ASK to buy / BID to sell (the spread actually quoted then);
        out at t0 + 60 s and at t0 + 300 s at the other side. d = 0 uses the quote 1 second BEFORE the release (the jump
        itself, not achievable). Net bp a trade = the move in the surprise's direction minus every spread crossed.
CLOCK   a check runs first: on 2026's payroll and CPI releases the biggest 1-second mid move must fall within the
        first 2 seconds after the stamped release time (HistData's DST clock produced a fake drift in fx_surprises_1m).
NOT IN  slippage beyond the quoted price, broker last-look / requotes at news, the latency of reading the number -
        all make a live bot worse than this.

REGISTERED BEFORE THE RUN (2026-10-12)
    S1  Most of the jump is gone within a second: entered at d = 1 s, the move to +60 s is under half the full jump's.
    S2  A bot entering at d = 2 s still nets >= +2bp a trade to +60 s on US releases (|score| >= 1) after the real spread.
    S3  At d = 10 s the net is <= 0.
    S4  The spread at the release second is >= 3x its median of the minute before.
    (~50-100 events: a feasibility read, not a verdict - a positive S2 earns a longer, out-of-sample record.)

RESULT (2026-10-12 13:36 UTC, logs/fx_news_seconds.txt; 51 releases, 97 release-pair trades, 69 of them USD)
    - THE WINDOW IS ONE SECOND, AND IT IS EXNESS'S. US releases, out at +60 s, net at the real ask / bid: entered 0.5 s or
      1 s after the stamped release +6.2bp a trade (t +3.9, 81-83% won); at 2 s +0.6bp (t +0.8, 54%); at 5 s 0.0; at 10 s
      -0.9bp (S3 RIGHT). S1 WRONG (at 1 s 5.8 of the full 8.2bp mid move was still there) and S2 WRONG (+0.6 at 2 s).
    - The CLOCK CHECK says why: on 15 of 18 payroll / CPI releases Exness's biggest 1-second move falls in [t0 + 1, t0 + 2) -
      the futures and the interbank market move in the first milliseconds of 08:30:00, so Exness's quote reaches it about a
      second late (or its tick clock runs ~1 s behind true time - the data cannot separate the two; either way no one can
      read the number before 08:30:00). S4 WRONG: the spread does NOT widen in those seconds (0.74bp before and after) -
      the quote stays tight while it is stale.
    - Non-USD releases (28 trades) fade more slowly: +1.3..+3.3bp at 2-5 s to +300 s - too few to read.
    Reading: there is no market edge left two seconds after a number; what exists in the first second is the BROKER's
    late repricing. Trading it is latency arbitrage against the broker - prohibited in retail broker terms (trades voided,
    accounts closed), defended in practice by last-look and slippage this test cannot model, and it needs the number
    within ~0.5 s of release, which free sources (bls.gov etc.) do not deliver from Pakistan. A news bot on Exness is not
    a legitimate or durable edge; at a realistic 2-5 s it earns nothing.

    python -m backtest.fx_news_seconds
"""
from __future__ import annotations

import datetime as dt
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.fx_surprises import events  # noqa: E402

LOG = ROOT / "logs" / "fx_news_seconds.txt"
CACHE = ROOT / "strategy_analysis" / "data" / "news_ticks"
PAIR = {"EUR": "EURUSDm", "GBP": "GBPUSDm", "JPY": "USDJPYm", "AUD": "AUDUSDm", "NZD": "NZDUSDm", "CAD": "USDCADm",
        "CHF": "USDCHFm"}
BASE_IS_FOREIGN = {"EURUSDm": True, "GBPUSDm": True, "AUDUSDm": True, "NZDUSDm": True, "USDJPYm": False, "USDCADm": False,
                   "USDCHFm": False}
DELAYS = (0, 0.5, 1, 2, 3, 5, 10, 30, 60)
EXITS = (60, 300)


def ticks(mt5, sym, t0: pd.Timestamp):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{sym}_{t0:%Y%m%d_%H%M%S}.pkl"
    if f.exists():
        return pickle.loads(f.read_bytes())
    a = dt.datetime.fromtimestamp(t0.timestamp() - 120, dt.timezone.utc)
    b = dt.datetime.fromtimestamp(t0.timestamp() + 420, dt.timezone.utc)
    mt5.symbol_select(sym, True)
    r = mt5.copy_ticks_range(sym, a, b, mt5.COPY_TICKS_ALL)
    out = None
    if r is not None and len(r):
        d = pd.DataFrame(r)
        d = d[(d.bid > 0) & (d.ask >= d.bid)]
        out = (d.time_msc.to_numpy() / 1000.0, d.bid.to_numpy(float), d.ask.to_numpy(float))
    f.write_bytes(pickle.dumps(out))
    return out


def main():
    import MetaTrader5 as mt5
    assert mt5.initialize(), mt5.last_error()
    E = events()
    E = E[(E.utc >= "2026-01-01") & (E.score.abs() >= 1)].reset_index(drop=True)
    rows, clock = [], []
    try:
        for r in E.itertuples():
            t0 = pd.Timestamp(r.utc).tz_localize("UTC")
            T0 = t0.timestamp()
            pairs = ["EURUSDm", "GBPUSDm", "USDJPYm"] if r.currency == "USD" else [PAIR[r.currency]]
            for sym in pairs:
                tk = ticks(mt5, sym, t0)
                if tk is None:
                    continue
                ts, bid, ask = tk
                if (ts < T0 - 60).sum() < 5 or (ts > T0 + 300).sum() < 5:
                    continue
                mid = (bid + ask) / 2
                # direction of the PAIR that profits from the surprise
                cur_up = np.sign(r.score) if r.currency != "USD" else -np.sign(r.score)    # the foreign ccy's direction
                side = cur_up if BASE_IS_FOREIGN[sym] else -cur_up                         # +1 buy the pair
                # clock: the biggest 1-second mid move around the release
                if r.currency == "USD" and any(k in r.names for k in ("Non-Farm Employment Change", "CPI m/m")):
                    sec = np.floor(ts - T0).astype(int)
                    m = (sec >= -30) & (sec <= 30)
                    if m.sum() > 10:
                        s_ = pd.Series(mid[m], index=sec[m]).groupby(level=0).last()
                        jumps = s_.diff().abs()
                        clock.append(int(jumps.idxmax()))
                pre = np.searchsorted(ts, T0 - 1, "right") - 1
                sp_pre = np.median((ask - bid)[(ts >= T0 - 60) & (ts < T0)] / mid[(ts >= T0 - 60) & (ts < T0)]) * 1e4
                sp_rel = np.median((ask - bid)[(ts >= T0) & (ts < T0 + 2)] / mid[(ts >= T0) & (ts < T0 + 2)]) * 1e4 \
                    if ((ts >= T0) & (ts < T0 + 2)).any() else np.nan
                rec = dict(utc=r.utc, ccy=r.currency, sym=sym, score=r.score, sp_pre=sp_pre, sp_rel=sp_rel)
                for d in DELAYS:
                    j = pre if d == 0 else np.searchsorted(ts, T0 + d, "left")
                    if j >= len(ts):
                        continue
                    e = ask[j] if side > 0 else bid[j]
                    for x in EXITS:
                        k = np.searchsorted(ts, T0 + x, "right") - 1
                        if k <= j:
                            continue
                        xp = bid[k] if side > 0 else ask[k]
                        rec[f"d{d}_x{x}"] = side * (xp / e - 1) * 1e4
                        rec[f"m{d}_x{x}"] = side * (mid[k] / mid[j] - 1) * 1e4          # mid move, no spread
                rows.append(rec)
    finally:
        mt5.shutdown()
    D = pd.DataFrame(rows)
    lines = [f"backtest/fx_news_seconds.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; Exness ticks, 2026 high-impact releases "
             f"(|score| >= 1): {D.utc.nunique()} releases, {len(D)} release-pair trades ({(D.ccy == 'USD').sum()} USD on 3 pairs)",
             f"CLOCK CHECK - second of the biggest 1-s mid move on US payroll / CPI releases (0 = the stamped second): "
             f"{pd.Series(clock).value_counts().sort_index().to_dict() if clock else 'none'}",
             f"SPREAD: median the minute before {D.sp_pre.median():.2f}bp, in the first 2 s after {D.sp_rel.median():.2f}bp "
             f"({D.sp_rel.median() / D.sp_pre.median():.1f}x)", ""]
    tt = lambda y: y.mean() / (y.std(ddof=1) / np.sqrt(len(y))) if len(y) > 2 and y.std(ddof=1) > 0 else np.nan  # noqa: E731
    res = {}
    for nm, m in (("all", D.score.abs() >= 1), ("USD", D.ccy == "USD"), ("others", D.ccy != "USD"),
                  ("|score| >= 2", D.score.abs() >= 2)):
        g = D[m]
        lines.append(f"{nm} ({len(g)} trades): net bp a trade at the real ask/bid [mid move without spread] - won %")
        for x in EXITS:
            row = f"  out at +{x:3d}s:"
            for d in DELAYS:
                col = f"d{d}_x{x}"
                if col not in g:
                    continue
                y = g[col].dropna()
                ym = g[f"m{d}_x{x}"].dropna()
                res[(nm, d, x)] = (y.mean(), tt(y), ym.mean(), len(y))
                row += f" | d={d:g}s {y.mean():+5.1f} [{ym.mean():+5.1f}] {np.mean(y > 0) * 100:3.0f}%"
            lines.append(row)
        lines.append("")
    lines.append("t of the net, USD releases, out at +60 s: " + ", ".join(
        f"d={d:g}s {res[('USD', d, 60)][1]:+.1f}" for d in DELAYS if ("USD", d, 60) in res))
    lines.append("")
    lines.append("REGISTERED PREDICTIONS")
    full, d1 = res[("all", 0, 60)][2], res[("all", 1, 60)][2]
    lines.append(f"  S1 mid move to +60 s: full jump {full:+.1f}bp, entered at 1 s {d1:+.1f}bp -> {'RIGHT' if d1 < 0.5 * full else 'WRONG'}")
    s2 = res[("USD", 2, 60)][0]
    lines.append(f"  S2 USD, d = 2 s, net to +60 s {s2:+.2f}bp (t {res[('USD', 2, 60)][1]:+.1f}) -> {'RIGHT' if s2 >= 2 else 'WRONG'}")
    s3 = res[("all", 10, 60)][0]
    lines.append(f"  S3 all, d = 10 s, net {s3:+.2f}bp -> {'RIGHT' if s3 <= 0 else 'WRONG'}")
    ratio = D.sp_rel.median() / D.sp_pre.median()
    lines.append(f"  S4 spread at release / before: {ratio:.1f}x -> {'RIGHT' if ratio >= 3 else 'WRONG'}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

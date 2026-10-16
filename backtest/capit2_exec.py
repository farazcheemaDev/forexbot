"""CAPIT2: A RESTING LIMIT (as backtested) OR A 2-MINUTE POLL AT MARKET (as the live bot does)? (2026-10-10)

The council (2026-10-10, item 3): execution is an edge that needs no new signal. capit2's backtest (capit_combos /
capit_stack, logs/capit_stack.txt) buys with a RESTING LIMIT 2% under the signal close, live for the next 4h bar, filled
at min(the bar's open, the limit) once the bar trades 0.3% through it, at the 2bp MAKER fee. The live final bot
(final_books.capit2_poll) cannot rest an order inside its netting: every ~2 minutes it buys AT MARKET (6bp taker) if the
live price is at or under limit x 0.997. It misses a dip that happens between polls, and buys deeper when it does fill.
Measured here on the same signals with 1-minute bars of each fill window (Binance USDT perps REST; delisted coins that
Binance no longer serves are skipped and counted):
    LIMIT   filled if the window's low <= limit x 0.997; entry min(window open, limit); entry fee 2bp
    POLL    polls at each 2-minute mark (both phases - even and odd minutes - averaged); entry at the first poll price
            <= limit x 0.997; entry fee 6bp
    EXIT    identical for both: capit_combos.exit_tp from the fill bar (+5% target not in the fill bar, not-working after
            24 bars from the signal, 43-bar cap, funding), exit fee 6bp for both
Score per SIGNAL (a miss counts 0): the mode with the higher mean wins. By construction a poll fill implies a limit fill.

REGISTERED BEFORE RUNNING (2026-10-10)
    X1  The poll fills 70-90% of the signals the limit fills.
    X2  When both fill, the poll enters 0.2-0.6% deeper than the limit - more than its extra 4bp fee.
    X3  Per signal the two modes are within 0.3 points of each other: execution does not change capit2's verdict.

RESULT (2026-10-10 01:00 UTC, logs/capit2_exec.txt; 387 signals 2020-03..2026-02, 385 with 1m bars)
    X1 RIGHT: the limit fills 55% of signals, the poll 45% - 81% of the limit's fills.
    X2 WRONG: when both fill the poll buys 1.10% deeper (median 0.71%), far more than its extra 0.04% fee - yet a filled
       trade nets only +3.99% against +3.91%, because the +5% target is set FROM the entry: a deeper fill moves the target
       down with it and helps only the trades that leave by the clock.
    X3 WRONG: per signal the resting limit earns +2.15% against the poll's +1.76% - +0.39 points (se 0.09), ~18% of the
       book's edge. The 47 fills the poll misses are the best trades (94% won, +4.42%): the fastest wick-and-bounce.
    Consequence: the live final bot's capit2 (final_books.capit2_poll, a 2-minute poll at market) runs ~18% under the
    rule that was backtested. The fix is a RESTING post-only limit watched by a fast fill loop - the crash desk's
    machinery (wick_live.py). Not changed here: the bot's code is frozen by the council's decision rule; the user decides.

    python -m backtest.capit2_exec
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import capit_combos as cc  # noqa: E402

CACHE = ROOT / "strategy_analysis" / "data" / "capit2_1m"
LOG = ROOT / "logs" / "capit2_exec.txt"
FAPI = "https://fapi.binance.com"
LIMIT, THROUGH, MAKER, TAKER = 0.02, 0.003, 0.0002, 0.0006


def minutes(coin: str, start_ms: int):
    """240 one-minute bars from start_ms (the fill window), cached; None if Binance does not serve the symbol."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{coin}_{start_ms}.json"
    if f.exists():
        r = json.loads(f.read_text())
        return r or None
    url = f"{FAPI}/fapi/v1/klines?symbol={coin}&interval=1m&startTime={start_ms}&limit=240"
    r = []
    for k in range(3):
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                r = json.loads(resp.read().decode())
            break
        except Exception as e:
            if "400" in str(e):
                break
            time.sleep(1 + k)
    r = [[int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4])] for x in r if int(x[0]) < start_ms + 240 * 60_000]
    f.write_text(json.dumps(r))
    time.sleep(0.05)
    return r or None


def main():
    PN, S = cc.panel4(0), cc.signals(0)
    S = S[(S.K >= 5) & (S.drop24 <= -0.10)].reset_index(drop=True)
    FEE = cc.FEE
    rows, skipped = [], 0
    for r in S.itertuples():
        P = PN[r.coin]
        i = r.i
        if i + 3 >= len(P["c"]):
            continue
        lim = P["c"][i] * (1 - LIMIT)
        thr = lim * (1 - THROUGH)
        start = int(pd.Timestamp(P["t"][i + 1]).timestamp() * 1000)
        m = minutes(r.coin, start)
        if not m or len(m) < 200:
            skipped += 1
            continue
        mo, ml, mc = np.array([x[1] for x in m]), np.array([x[3] for x in m]), np.array([x[4] for x in m])
        rec = dict(t=r.t, coin=r.coin)
        # LIMIT (resting, as backtested)
        if ml.min() <= thr:
            e = min(mo[0], lim)
            _, net, *_ = cc.exit_tp(i, i + 1, e, P, fc=P["fc"], limit_fill=True)
            rec["lim"] = net + FEE - MAKER - TAKER
            rec["e_lim"] = e
        # POLL (live: at market on 2-minute marks, both phases)
        nets, ents = [], []
        for ph in (0, 1):
            k = next((k for k in range(ph, len(mc), 2) if mc[k] <= thr), None)
            if k is None:
                nets.append(0.0)
                ents.append(np.nan)
                continue
            e = mc[k]
            _, net, *_ = cc.exit_tp(i, i + 1, e, P, fc=P["fc"], limit_fill=True)
            nets.append(net + FEE - TAKER - TAKER)
            ents.append(e)
        rec["poll"] = float(np.mean(nets))
        rec["poll_fill"] = float(np.mean([np.isfinite(x) for x in ents]))
        rec["e_poll"] = float(np.nanmean(ents)) if np.isfinite(ents).any() else np.nan
        rows.append(rec)
    D = pd.DataFrame(rows)
    D["lim"] = D.get("lim", pd.Series(np.nan, index=D.index))
    lim_fill = D["lim"].notna()
    both = lim_fill & (D.poll_fill > 0)
    ev_lim, ev_poll = D["lim"].fillna(0.0), D.poll
    dif = ev_lim - ev_poll
    lines = [f"backtest/capit2_exec.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; capit2 signals (K >= 5, coin -10% in "
             f"24h), phase 0: {len(S)} signals, {len(D)} with Binance 1m bars, {skipped} skipped (symbol not served); "
             f"{D.t.min():%Y-%m-%d} .. {D.t.max():%Y-%m-%d}", ""]
    lines.append(f"FILLS: limit {lim_fill.mean() * 100:.0f}% of signals | poll {D.poll_fill.mean() * 100:.0f}% (both phases "
                 f"averaged) | poll fills as a share of limit fills {D.poll_fill[lim_fill].mean() * 100:.0f}%")
    dd = (D.e_lim[both] / D.e_poll[both] - 1) * 100
    lines.append(f"ENTRY when both fill ({int(both.sum())} signals): the poll buys {dd.mean():+.2f}% deeper on average "
                 f"(median {dd.median():+.2f}%) - against its extra {(TAKER - MAKER) * 100:.2f}% fee")
    lines.append(f"NET A FILLED TRADE: limit {D['lim'][lim_fill].mean() * 100:+.2f}% | poll "
                 f"{(D.poll[D.poll_fill > 0] / D.poll_fill[D.poll_fill > 0]).mean() * 100:+.2f}%")
    lines.append(f"PER SIGNAL (a miss = 0): limit {ev_lim.mean() * 100:+.3f}% | poll {ev_poll.mean() * 100:+.3f}% | "
                 f"limit - poll {dif.mean() * 100:+.3f} points (se {dif.std(ddof=1) / np.sqrt(len(dif)) * 100:.3f}), "
                 f"limit better on {(dif > 0).mean() * 100:.0f}% of signals")
    missed = D[lim_fill & (D.poll_fill < 1)]
    lines.append(f"SIGNALS THE POLL MISSES (in at least one phase) that the limit fills: {len(missed)}; their net under the "
                 f"limit {missed['lim'].mean() * 100:+.2f}% a trade, won {(missed['lim'] > 0).mean() * 100:.0f}%")
    lines.append("")
    x1 = D.poll_fill[lim_fill].mean()
    lines.append(f"X1 (poll fills 70-90% of limit fills): {x1 * 100:.0f}% -> {'RIGHT' if 0.7 <= x1 <= 0.9 else 'WRONG'}")
    lines.append(f"X2 (poll 0.2-0.6% deeper): {dd.mean():+.2f}% -> {'RIGHT' if 0.2 <= dd.mean() <= 0.6 else 'WRONG'}")
    lines.append(f"X3 (modes within 0.3 points per signal): {dif.mean() * 100:+.3f} -> {'RIGHT' if abs(dif.mean() * 100) <= 0.3 else 'WRONG'}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

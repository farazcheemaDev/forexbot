"""MAKING THE RUNNING MACHINE MATCH ITS OWN BACKTEST, and cheaper fills - what each fix is worth (2026-10-22)

THE USER (2026-10-22): "how can we eliminate losses from our current bot and make it more profitable - do something about
it too". Losses cannot be braked away here (worst_month.py: 16 brakes lose to betting smaller; profit_take.py, coin_cap.py,
alt_bear.py, chop_switch.py, regime_weights.py: every loss filter cost more than it saved). What has NOT been done is to
make the RUNNING bot (combo-bot-final, `--mode dry --final`, no `--wick`) do what its backtest does:
  BASE  the running machine: trend + MN blend + carry 0.5 + sleeve + daily 0.5 + capit2 (2x) + news + NASDAQ dip x1
        (all_books.machine_books, 10 orderings; trend gains shrunk for hindsight, the rest raw)
  F1    capit2 as BACKTESTED (a resting post-only limit) instead of as RUNNING (a 2-minute poll at market): the poll earns
        +1.76% a signal against +2.15% (capit2_exec.py), so BASE's capit2 is the limit's and the running bot's is
        approximated as 0.82 x its daily P&L (labelled: an approximation)
  F2    the crash bids switched ON (`--wick`): in every backtest the machine is quoted from, not in the running bot
  F3    the market-neutral blend and the carry book rebalanced with post-only LIMIT orders: 6bp a round trip (Bitget maker
        2bp a side + 1bp of adverse fill each side) instead of 12bp; recomputed with mn_combos.FEE
  ALL   F1 + F2 + F3
Each against the RUNNING machine on the SAME ordering (paired): $300 typical year, worst month, fall, months up - tune
(before 2024-08-29) and holdout.

REGISTERED BEFORE THE RUN (2026-10-22)
  X1 F2 raises the typical year on both halves; the worst month moves by under 2 points.
  X2 F1 adds 3-8% to the typical year on both halves.
  X3 F3 adds 2-6% to the typical year on both halves.
  X4 no fix moves the share of months up by more than 3 points.

RESULT (2026-10-22, logs/machine_fixes.txt; BACKTEST) - three fixes, each 10/10 orderings on both halves; together
  +22% / +14% on the typical year (tune / holdout), worst month and fall unchanged within a point.
  F1 capit2 as a resting limit: +3.4% / +3.9%. F2 crash bids on: +15.4% / +7.4%, worst month -19.8 -> -18.9 (tune) /
  -30.7 -> -31.3 (holdout), months up +2 / +1. F3 MN + carry at limit fees: +2.5% / +2.4%. X1-X3 RIGHT; X4 WRONG (ALL
  moves months up by 4 points on the tune half). First run: my MN rebuild added the momentum and RSI halves with
  Series.add(fill_value=0) and did not reproduce all_books (0.28 a day apart on 336 days); combined as machine_books does
  (each reindexed first) it reproduces to 0.0 - now asserted.
  Built 2026-10-22: F1 (final_books.capit2_poll fills at the limit on 1-minute lows) and F2 (final_books.bids_poll, the
  crash bids as a ledger inside the dry account). F3 needs a real post-only order path - not built.

    python -m backtest.machine_fixes
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "machine_fixes.txt"
CACHE = ROOT / "logs" / "daily_combos_cache" / "alt_bear_books.pkl"
POLL = 1.76 / 2.15


def maker_books(fee):
    """the MN blend and carry series per ordering, all_books.machine_books' construction, at a given round-trip fee."""
    from backtest import machine_combos as mc
    from backtest import mn_combos as m
    from backtest.moderate_retests import scored_run
    old = m.FEE
    m.FEE = fee
    try:
        D = m.data()
        C = pd.DataFrame(D["X"])
        d = C.diff()
        up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
        dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
        rsi = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()
        mom = D["X"] / np.r_[np.full((30, D["X"].shape[1]), np.nan), D["X"][:-30]] - 1
        out = {}
        for sd in mc.SEEDS:
            o = sd % 7
            if o in out:
                continue
            out[o] = (scored_run(mom, start=o, stop="short_only", short_stop=0.5),       # combined as machine_books
                      scored_run(rsi, start=o, stop="short_only", short_stop=0.5),       # does: each reindexed first
                      0.5 * m.mn_run(look=1, score="funding7", fwin=7, frac=0.2, start=o, stop="short_only", short_stop=0.5))
        return out
    finally:
        m.FEE = old


def main():
    from backtest.all_books import machine_books, ndx_dip, news_book
    from backtest.machine import CUT, summary
    M = pickle.loads(CACHE.read_bytes()) if CACHE.exists() else machine_books()
    news, ndx = news_book(), ndx_dip()
    mk12, mk6 = maker_books(12.0 / 1e4), maker_books(6.0 / 1e4)
    from backtest import machine_combos as mc
    V = {k: [] for k in ("RUNNING", "F1 capit2 as a resting limit", "F2 crash bids on", "F3 MN + carry at limit fees", "ALL")}
    chk = []
    for sd, x in zip(mc.SEEDS, M):
        idx = x.index
        r = lambda s: s.reindex(idx).fillna(0.0)  # noqa: E731
        o = sd % 7
        mn12, ca12 = 0.5 * r(mk12[o][0]) + 0.5 * r(mk12[o][1]), r(mk12[o][2])
        mn6, ca6 = 0.5 * r(mk6[o][0]) + 0.5 * r(mk6[o][1]), r(mk6[o][2])
        chk.append(max((mn12 - x.mn_blend).abs().max(), (ca12 - x.carry).abs().max()))
        common = x.trend + x.sleeve + x.daily + r(news) + r(ndx)
        run = common + mn12 + ca12 + POLL * x.capit2
        V["RUNNING"].append(run)
        V["F1 capit2 as a resting limit"].append(common + mn12 + ca12 + x.capit2)
        V["F2 crash bids on"].append(run + x.bids)
        V["F3 MN + carry at limit fees"].append(common + mn6 + ca6 + POLL * x.capit2)
        V["ALL"].append(common + mn6 + ca6 + x.capit2 + x.bids)
    assert max(chk) < 1e-9, f"the 12bp rebuild does not reproduce all_books' MN / carry ({max(chk):.2e})"
    L = [f"backtest/machine_fixes.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; 10 orderings; trend gains shrunk, the rest raw; "
         f"the 12bp rebuild of MN + carry reproduces all_books' series to {max(chk):.1e}", "",
         f"   {'machine ($300, 12 months)':<34}{'half':>8}{'typical':>9}{'bad':>8}{'worst':>8}{'worst mo':>9}{'fall':>6}{'mo up':>7}"
         f"{'vs RUNNING, paired':>26}"]
    S = {}
    for lab, xs in V.items():
        for half in ("tune", "holdout"):
            if half == "tune":
                s = summary([x[x.index < CUT] for x in xs])
                per = [summary([x[x.index < CUT]])["typ"] for x in xs]
            else:
                s = summary(xs, CUT)
                per = [summary([x], CUT)["typ"] for x in xs]
            S[(lab, half)] = (s, np.array(per))
            pair = ""
            if lab != "RUNNING":
                d = (np.array(per) - S[("RUNNING", half)][1]) / S[("RUNNING", half)][1] * 100
                pair = f"{d.mean():+.1f}% +- {d.std(ddof=1) / np.sqrt(len(d)):.1f}, {int((d > 0).sum())}/10"
            L.append(f"   {lab:<34}{half:>8} ${s['typ']:>7,.0f} ${s['bad']:>6,.0f} ${s['worst']:>6,.0f}{s['wm']:>+8.1f}%"
                     f"{s['dd']:>5.0f}%{s['up']:>6.0f}%{pair:>26}")
        L.append("")
    g = lambda lab, h: (S[(lab, h)][1] / S[("RUNNING", h)][1] - 1).mean() * 100  # noqa: E731
    x1 = all(g("F2 crash bids on", h) > 0 and abs(S[("F2 crash bids on", h)][0]["wm"] - S[("RUNNING", h)][0]["wm"]) < 2
             for h in ("tune", "holdout"))
    x2 = all(3 <= g("F1 capit2 as a resting limit", h) <= 8 for h in ("tune", "holdout"))
    x3 = all(2 <= g("F3 MN + carry at limit fees", h) <= 6 for h in ("tune", "holdout"))
    x4 = all(abs(S[(k, h)][0]["up"] - S[("RUNNING", h)][0]["up"]) <= 3 for k in V for h in ("tune", "holdout"))
    L += ["REGISTERED PREDICTIONS",
          f"  X1 crash bids raise the typical year on both halves, worst month within 2 points -> {'RIGHT' if x1 else 'WRONG'}",
          f"  X2 capit2 limit adds 3-8% on both halves -> {'RIGHT' if x2 else 'WRONG'}",
          f"  X3 MN + carry at limit fees add 2-6% on both halves -> {'RIGHT' if x3 else 'WRONG'}",
          f"  X4 no fix moves months up by more than 3 points -> {'RIGHT' if x4 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

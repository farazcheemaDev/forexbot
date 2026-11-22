"""The Analyst desk is in profit on paper - is there a strategy in it? (2026-11-12)

THE USER: "analyse the analyst desk, it's in profit, and see if we got a good strategy from it". On 2026-11-12 the desk's $300 paper book was at
$320.79 (+6.93%) after 119 resolved calls in 16.4 days, while its average call was -0.18R after fees (`analyst.py --status` on the VM). A book
can be up while the average call is down only if the calls it BOOKED differ from the ones it did not (the 3x gross cap skips a call whose
notional would push the open total past 3x the equity - tight stops make big notionals), or if a few big winners carry it.

DATA  logs/analyst_calls_20261112.csv (the live log copied read-only from the VM, 119 calls 2026-10-27 .. 11-12); the replay's 10,580 calls
      (strategy_analysis/data/analyst_replay/calls.json, 2022-02 .. 2026-10) for the base rate.

QUESTIONS AND PREDICTIONS (written before the numbers below were computed)
  P1  The book's profit is the cap's doing: booked calls average > 0R, unbooked calls average well under -0.5R.                       (70%)
  P2  It is concentrated: without its 3 best booked calls the book is at or under $300.                                             (60%)
  P3  It is luck the replay already contains: in the replay's OWN paper book (same rules, same cap), at least 5% of 119-call
      stretches end +6.9% or better, although that book loses ~3%/week overall.                                                     (65%)
  P4  No slice of the live record clears t >= 2 over independent bets (day + side).                                                  (75%)
  P5  The registered sweet-spot forward test (stop >= 0.8%, calls made after 2026-11-06 15:00 UTC) is still under 30 bets and not
      positive at t >= 2.                                                                                                             (90%)

RESULT (2026-11-12, logs/analyst_profit_check.txt) - NOT A STRATEGY YET. P1, P2, P4, P5 right; P3 wrong (the stretch is rarer than I guessed).
  The +$20.79 is the 3x cap's doing: the 83 BOOKED calls average +0.173R (t +0.8 over 27 bets); the 36 the cap skipped average -0.992R (3 won) -
  the cap skips tight stops, so it works as a stop-width filter. The best 3 booked calls are worth more than the whole profit (without them $296.49);
  shorts made +$21.54, longs -$0.76 (a falling market). Stops >= 0.8%: +0.329R (t +1.2) over all 47 - but the 14 made AFTER the 2026-11-06
  registration are -0.182R a call, -0.057R a bet (9 bets): the pocket has not shown up out of sample. In the replay's own book (same rules and cap)
  a +6.9% 119-call stretch happens 2.5% of the time; the same slices there lose (stop >= 0.8% -0.126R, SMC & stop >= 0.8% -0.136R). The one
  finding that agrees live and replay: stops under 0.4% lose (-0.76R live, -0.59R replay, t -6.3) - a loss to avoid, not an edge.

    python -m backtest.analyst_profit_check [path/to/calls.csv]
"""
from __future__ import annotations

import heapq
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "logs" / "analyst_calls_20261112.csv"
REPLAY = ROOT / "strategy_analysis" / "data" / "analyst_replay" / "calls.json"
LOG = ROOT / "logs" / "analyst_profit_check.txt"
REG_MS = 1793977200000                      # 2026-11-06 15:00 UTC, the sweet-spot registration
RISK, CAP, START = 0.005, 3.0, 300.0


def bets(x: pd.DataFrame) -> pd.Series:
    t = pd.to_datetime(x.made_ms, unit="ms")
    return x.assign(day=t.dt.floor("D")).groupby(["day", "side"]).r_net.mean()


def tstat(b: pd.Series) -> float:
    return float(b.mean() / (b.std(ddof=1) / np.sqrt(len(b)))) if len(b) > 2 and b.std(ddof=1) > 0 else np.nan


def line(lab: str, x: pd.DataFrame) -> str:
    if not len(x):
        return f"  {lab:<40} n    0"
    b = bets(x)
    usd = x.pnl_usd.sum() if "pnl_usd" in x else np.nan
    return (f"  {lab:<40} n {len(x):>4}  bets {len(b):>3}  won {int((x.status == 'WIN').sum()):>3} ({(x.status == 'WIN').mean() * 100:3.0f}% vs random "
            f"{x.base_p.mean() * 100:3.0f}%)  R/call {x.r_net.mean():+.3f}  R/bet {b.mean():+.3f} (t {tstat(b):+.1f})  book ${usd:+.2f}")


def book_curve(rows: pd.DataFrame) -> list:
    """The desk's book arithmetic (analyst_replay.paper_book): risk 0.5% of the booked equity at entry, skip a call that would push open
    notional past 3x equity, book at exit. Returns [(call_index, equity at that call's entry)] for every call, booked or not."""
    eq, open_, out = START, [], []
    for k, r in enumerate(rows.itertuples(index=False)):
        while open_ and open_[0][0] <= r.made_ms:
            _ex, _n, rr, risk = heapq.heappop(open_)
            eq += rr * risk
        out.append(eq)
        risk = eq * RISK
        notional = risk / r.stop_pct
        if sum(o[1] for o in open_) + notional > CAP * eq:
            continue
        heapq.heappush(open_, (r.exit_ms, notional, r.r_net, risk))
    return out


def main():
    live = pd.read_csv(sys.argv[1] if len(sys.argv) > 1 else LIVE)
    live = live[live.status.isin(["WIN", "LOSS", "EXPIRED"])].copy()
    for c in ("r_net", "pnl_usd", "stop_pct", "base_p", "made_ms", "rr"):
        live[c] = pd.to_numeric(live[c], errors="coerce")
    live["booked"] = live.booked.astype(int).astype(bool)
    L = [f"backtest/analyst_profit_check.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; live log {len(live)} resolved calls "
         f"{live.made_utc.min()} .. {live.made_utc.max()}; book P&L ${live.pnl_usd.sum():+.2f} on $300", "",
         "1. WHERE THE PROFIT IS"]
    L.append(line("all calls", live))
    L.append(line("BOOKED (inside the 3x cap)", live[live.booked]))
    L.append(line("NOT booked (over the cap)", live[~live.booked]))
    for lab, m in (("stop < 0.4%", live.stop_pct < 0.004), ("stop 0.4-0.8%", live.stop_pct.between(0.004, 0.008, inclusive="left")),
                   ("stop >= 0.8%", live.stop_pct >= 0.008)):
        L.append(line(lab, live[m]))
    for meth in ("SR", "FIB", "SMC"):
        L.append(line(f"rule {meth}", live[live.method == meth]))
    for sym, g in live.groupby("symbol"):
        L.append(line(f"symbol {sym}", g))
    L.append(line("long", live[live.side == "long"]))
    L.append(line("short", live[live.side == "short"]))
    bk = live[live.booked].sort_values("pnl_usd", ascending=False)
    top = bk.head(5)
    L += ["", "2. HOW CONCENTRATED",
          "  best 5 booked calls: " + "; ".join(f"#{r.id} {r.symbol[:-4]} {r.side} {r.method} {r.r_net:+.2f}R ${r.pnl_usd:+.2f}" for r in top.itertuples()),
          f"  book without its best 1 / 3 / 5 calls: ${300 + bk.pnl_usd.sum() - bk.pnl_usd.head(1).sum():.2f} / "
          f"${300 + bk.pnl_usd.sum() - bk.pnl_usd.head(3).sum():.2f} / ${300 + bk.pnl_usd.sum() - bk.pnl_usd.head(5).sum():.2f}",
          f"  share of booked R from the best 3 days: {bets(bk).groupby(level=0).sum().sort_values(ascending=False).head(3).sum():+.2f} of "
          f"{bets(bk).groupby(level=0).sum().sum():+.2f} (day-and-side means summed)"]
    # 3. the base rate: the replay's own book over stretches of the same length
    rp = pd.DataFrame(json.loads(REPLAY.read_text())).sort_values("made_ms", kind="stable").reset_index(drop=True)
    curve = np.array(book_curve(rp))
    n = len(live)
    w = curve[n:] / curve[:-n] - 1
    days = (live.made_ms.max() - live.made_ms.min()) / 86_400_000
    span = rp.made_ms.to_numpy()
    k = np.searchsorted(span, span + days * 86_400_000)
    ok = k < len(span)
    wd = curve[k[ok]] / curve[np.flatnonzero(ok)] - 1
    live_ret = live.pnl_usd.sum() / 300
    L += ["", f"3. IS +{live_ret * 100:.1f}% UNUSUAL FOR THIS DESK? The replay's own paper book (same rules, 0.5% risk, 3x cap), {len(rp)} calls 2022-26:",
          f"  whole replay: $300 -> ${curve[-1]:.2f}",
          f"  every stretch of {n} consecutive calls: median {np.median(w) * 100:+.1f}%, 90th pct {np.percentile(w, 90) * 100:+.1f}%, "
          f"share at +{live_ret * 100:.1f}% or better {(w >= live_ret).mean() * 100:.1f}%",
          f"  every stretch of {days:.1f} days: median {np.median(wd) * 100:+.1f}%, 90th pct {np.percentile(wd, 90) * 100:+.1f}%, "
          f"share at +{live_ret * 100:.1f}% or better {(wd >= live_ret).mean() * 100:.1f}%"]
    # replay stats for the slices the live record makes look good
    rp["booked_like"] = True
    L += ["", "4. THE SAME SLICES ON 4.7 YEARS OF REPLAY (per call, after 12bp)"]
    for lab, m in (("all", rp.r_net == rp.r_net), ("rule SMC", rp.method == "SMC"), ("stop >= 0.8%", rp.stop_pct >= 0.008),
                   ("SMC & stop >= 0.8%", (rp.method == "SMC") & (rp.stop_pct >= 0.008)), ("stop < 0.4%", rp.stop_pct < 0.004)):
        x = rp[m]
        L.append(f"  {lab:<24} n {len(x):>5}  won {(x.status == 'WIN').mean() * 100:4.1f}% vs random {x.base_p.mean() * 100:4.1f}%  R/call {x.r_net.mean():+.3f}  "
                 f"R/bet {bets(x).mean():+.3f} (t {tstat(bets(x)):+.1f})")
    fw = live[(live.made_ms >= REG_MS) & (live.stop_pct >= 0.008)]
    fb = bets(fw)
    L += ["", "5. THE REGISTERED FORWARD TEST (stop >= 0.8%, made after 2026-11-06 15:00 UTC; bar: 30 bets, >= +0.15R a bet, t >= 2, hit above random, both halves positive)",
          line("forward sweet spot", fw)]
    slices = [live, live[live.booked], live[live.method == "SMC"], live[live.stop_pct >= 0.008]]
    best_t = max(tstat(bets(x)) for x in slices if len(x) > 5)
    bk_r, nb_r = live[live.booked].r_net.mean(), live[~live.booked].r_net.mean()
    w3 = 300 + bk.pnl_usd.sum() - bk.pnl_usd.head(3).sum()
    L += ["", "PREDICTIONS",
          f"  P1 booked > 0R and unbooked < -0.5R ({bk_r:+.3f} / {nb_r:+.3f}) -> {'RIGHT' if bk_r > 0 and nb_r < -0.5 else 'WRONG'}",
          f"  P2 without the best 3 booked calls the book is <= $300 (${w3:.2f}) -> {'RIGHT' if w3 <= 300 else 'WRONG'}",
          f"  P3 >= 5% of the replay's {n}-call stretches end at +{live_ret * 100:.1f}% or better ({(w >= live_ret).mean() * 100:.1f}%) -> "
          f"{'RIGHT' if (w >= live_ret).mean() >= 0.05 else 'WRONG'}",
          f"  P4 no slice reaches t >= 2 over bets (best of all / booked / SMC / stop >= 0.8%: {best_t:+.2f}) -> {'RIGHT' if best_t < 2 else 'WRONG'}",
          f"  P5 forward test under 30 bets and not passing ({len(fb)} bets, {fb.mean() if len(fb) else float('nan'):+.3f}R) -> "
          f"{'RIGHT' if len(fb) < 30 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

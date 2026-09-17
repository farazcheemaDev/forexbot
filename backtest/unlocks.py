"""TOKEN UNLOCK CLIFFS — a scheduled, non-informational supply shock.

    python -m backtest.unlocks

WHY THIS CATEGORY IS DIFFERENT FROM EVERYTHING ELSE IN THIS REPO
    Nineteen indicator families, VSA, meta-labeling, funding carry, cash-and-carry,
    cross-sectional funding and the vol premium have all been tested here. Every one
    of them predicted price from price, or collected a fee that competition drove to
    the cost of capital.

    A vesting cliff is neither. It is a supply increase at a timestamp PUBLISHED
    MONTHS IN ADVANCE, written into a contract. The seller is a fund or a team whose
    tokens just became transferable, and their decision to sell is not information
    about value - it is a calendar. Same mechanism class as the liquidation-cascade
    thesis, except the date is known weeks ahead instead of milliseconds.

    So this is the only place in the project where the input is not a price.

THE DATA, AND IT IS FREE
    defillama-datasets.llama.fi/emissions/{slug} - no key, no paid tier.
    372 protocols carry emission schedules; 101 of them have a token trading on
    Binance USDT perps, giving 18,836 scheduled events of which 14,066 are cliffs
    already in the past. Daily bars come from Binance perps (84,058 of them).

THE CONTROL, WHICH IS THE WHOLE TEST
    Alt-coins drift DOWN. Shorting a random alt on a random day in this sample makes
    money, so "unlock shorts were profitable" proves nothing at all. Every event
    window is therefore compared against NON-EVENT windows OF THE SAME TOKENS over
    THE SAME DATES, identical in length and direction.

    That is the section-19 lesson from his_strategy.md applied before the fact: a
    control that differs from the treatment in any way other than the treatment
    manufactures the result.

    Direction here is fixed SHORT by the hypothesis, not derived from the data, so
    the specific §19 bug - assigning controls a direction computed from the quantity
    being tested - cannot occur.

TWO BIASES THAT CANNOT BE REMOVED, STATED PLAINLY
    * SCHEDULE REVISION. DefiLlama serves the schedule as it stands TODAY. Projects
      do renegotiate vesting. If a cliff was quietly moved, this file sees the new
      date, not the date the market was watching at the time. That flatters the test.
    * SURVIVORSHIP. Only tokens trading on Binance today are here. This project has
      already measured a 30% death rate among USDT pairs, and dead tokens are exactly
      the ones whose unlocks hurt most. That also flatters the test.
    Both biases push the same way, so a NEGATIVE result here is strong and a positive
    one needs more work before it is believed.

COSTS
    12bp round trip, the FEE_BP convention used across this repo for Binance-class
    venues, charged on every window including the controls.

REGISTERED PREDICTION (2026-09-18, before running)
    The excess return of unlock windows over matched non-event windows will be small
    and will not survive correction. The schedule is public, the effect is famous,
    and anything this visible is front-run: by the time the cliff arrives the supply
    is already priced. If anything shows up it will be in the RUN-UP (T-5 to T-1)
    rather than on the day, because that is where an anticipated event gets traded.

    I also expect the raw unlock-short return to look profitable while the EXCESS
    over control is ~zero, because alts fell over this sample. That gap between the
    raw number and the excess is the entire reason the control exists.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DATA = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data"
FEE_BP = 12.0
THRESH = 1.0          # primary: daily aggregate cliff >= 1.0% of supply
rng = np.random.default_rng(97)

# (entry offset, exit offset) in days relative to the unlock day. Declared here,
# before running. The PRIMARY cell is the first one; the rest are secondary and
# Holm-corrected as a family.
GRID = [(-1, 1), (-5, -1), (-5, 1), (-3, 0), (0, 1), (0, 3), (-1, 3), (-1, 5)]
PRIMARY = GRID[0]


def load_prices():
    px = json.load(open(DATA / "unlock_prices.json"))
    out = {}
    for s, rows in px.items():
        if len(rows) < 120:
            continue
        d = pd.DataFrame(rows, columns=["t", "o", "h", "l", "c", "qv"])
        d["day"] = pd.to_datetime(d.t, unit="ms").dt.normalize()
        out[s] = d.set_index("day")[["c", "qv"]].sort_index()
    return out


def load_events(prices):
    rows = json.load(open(DATA / "unlock_events.json"))
    df = pd.DataFrame([r for r in rows if r["kind"] == "cliff"])
    df["day"] = pd.to_datetime(df.ts, unit="s").dt.normalize()
    df["supply"] = df.adj_supply.fillna(df.max_supply)
    df = df[(df.supply > 0) & df.sym.isin(prices)]
    # several categories can unlock on the same day: aggregate per token-day
    g = (df.groupby(["sym", "day"])
         .agg(tokens=("tokens", "sum"), supply=("supply", "first")).reset_index())
    g["pct"] = g.tokens / g.supply * 100
    return g


def window_ret(p: pd.DataFrame, day, a: int, b: int):
    """Short return over [day+a, day+b] net of costs. None if the window is not
    fully covered by bars, so a missing day never silently becomes a zero."""
    i = p.index.searchsorted(day)
    if i <= 0 or i >= len(p):
        return None
    ia, ib = i + a, i + b
    if ia < 0 or ib >= len(p) or ib <= ia:
        return None
    pa, pb = float(p.c.iloc[ia]), float(p.c.iloc[ib])
    if pa <= 0 or pb <= 0:
        return None
    return (pa - pb) / pa * 100 - FEE_BP / 100.0     # SHORT, net


def controls(p, ev_days, a, b, n_per, span):
    """Non-event windows for the SAME token inside the SAME date span."""
    lo, hi = span
    cand = [d for d in p.index
            if lo <= d <= hi and
            all(abs((d - e).days) > 10 for e in ev_days)]
    if len(cand) < 5:
        return []
    pick = rng.choice(len(cand), size=min(n_per, len(cand)), replace=False)
    out = []
    for j in pick:
        r = window_ret(p, cand[j], a, b)
        if r is not None:
            out.append(r)
    return out


def holm(ps):
    o = np.argsort(ps)
    m = len(ps)
    out = np.empty(m)
    prev = 0.0
    for r, i in enumerate(o):
        prev = max(prev, min(1.0, (m - r) * ps[i]))
        out[i] = prev
    return out


def perm_p(a, b, n=20000):
    obs = a.mean() - b.mean()
    allv = np.concatenate([a, b])
    k = len(a)
    cnt = 0
    for _ in range(n):
        p = rng.permutation(allv)
        if abs(p[:k].mean() - p[k:].mean()) >= abs(obs):
            cnt += 1
    return obs, cnt / n


def build(prices, ev, a, b, thresh):
    """Returns (treatment array, control array, per-token counts)."""
    T, C, per_tok = [], [], {}
    big = ev[ev.pct >= thresh]
    for sym, g in big.groupby("sym"):
        p = prices[sym]
        days = list(g.day)
        span = (p.index[0], p.index[-1])
        hits = [window_ret(p, d, a, b) for d in days]
        hits = [h for h in hits if h is not None]
        if not hits:
            continue
        all_days = list(ev[ev.sym == sym].day)
        cs = controls(p, all_days, a, b, n_per=max(20, 4 * len(hits)), span=span)
        if len(cs) < 5:
            continue
        T += hits
        C += cs
        per_tok[sym] = (len(hits), float(np.mean(hits)), float(np.mean(cs)))
    return np.array(T), np.array(C), per_tok


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: the excess over matched controls will be small and will not")
    print("survive correction - the schedule is public and anything this visible is")
    print("front-run. The raw short return WILL look profitable because alts fell;")
    print("that gap is why the control exists.\n")

    prices = load_prices()
    ev = load_events(prices)
    print(f"  {len(prices)} tokens with usable daily bars")
    print(f"  {len(ev):,} token-days with a cliff unlock, "
          f"{ev.day.min():%Y-%m-%d} .. {ev.day.max():%Y-%m-%d}")
    past = ev[ev.day < pd.Timestamp.utcnow().tz_localize(None)]
    print(f"  {len(past):,} of them in the past")
    for th in (0.5, 1.0, 2.0, 5.0):
        s = past[past.pct >= th]
        print(f"    >= {th:4.1f}% of supply: {len(s):5,} token-days "
              f"across {s.sym.nunique():3} tokens")
    print()

    print("=" * 96)
    print(f"1. THE PRIMARY TEST — short across [T{PRIMARY[0]:+d}, T{PRIMARY[1]:+d}] "
          f"on cliffs >= {THRESH}% of supply")
    print("=" * 96)
    T, C, per_tok = build(prices, past, *PRIMARY, THRESH)
    if len(T) < 30:
        print(f"  only {len(T)} usable events - underpowered, stopping")
        return
    obs, p = perm_p(T, C)
    print(f"  {'':24}{'n':>7}{'mean %':>10}{'median':>9}{'win%':>8}{'sd':>8}")
    print(f"  {'UNLOCK windows (short)':<24}{len(T):>7}{T.mean():>+10.3f}"
          f"{np.median(T):>+9.3f}{100*(T>0).mean():>7.0f}%{T.std():>8.2f}")
    print(f"  {'matched NON-event (short)':<24}{len(C):>7}{C.mean():>+10.3f}"
          f"{np.median(C):>+9.3f}{100*(C>0).mean():>7.0f}%{C.std():>8.2f}")
    print(f"\n  EXCESS over control: {obs:+.3f}%   permutation p = {p:.3f}")
    print(f"  tokens contributing: {len(per_tok)}")
    print("\n  Read the EXCESS line, not the raw mean. The raw mean is mostly the")
    print("  fact that alt-coins fell over this sample.")

    print("\n" + "=" * 96)
    print("2. THE WINDOW GRID — where in the event does anything happen?")
    print("=" * 96)
    print(f"  {'window':<16}{'n':>6}{'unlock':>10}{'control':>10}"
          f"{'excess':>9}{'p':>8}{'Holm':>8}")
    raws, cells = [], []
    for a, b in GRID:
        t, c, _ = build(prices, past, a, b, THRESH)
        if len(t) < 30:
            print(f"  T{a:+d}..T{b:+d}{'':<8}{len(t):>6}  too few")
            continue
        o, pv = perm_p(t, c)
        raws.append(pv)
        cells.append((a, b, len(t), t.mean(), c.mean(), o, pv))
    hp = holm(np.array(raws)) if raws else []
    for (a, b, n, tm, cm, o, pv), h in zip(cells, hp):
        star = " **" if h < .05 else (" *" if pv < .05 else "")
        print(f"  T{a:+d}..T{b:+d}{'':<8}{n:>6}{tm:>+10.3f}{cm:>+10.3f}"
              f"{o:>+9.3f}{pv:>8.3f}{h:>8.3f}{star}")
    print("\n  ** survives Holm across the whole grid   |   * uncorrected only")

    print("\n" + "=" * 96)
    print(f"3. DOES SIZE MATTER? — excess on the primary window by cliff size")
    print("=" * 96)
    print(f"  {'threshold':<16}{'n':>6}{'unlock':>10}{'control':>10}"
          f"{'excess':>9}{'p':>8}")
    for th in (0.5, 1.0, 2.0, 5.0, 10.0):
        t, c, _ = build(prices, past, *PRIMARY, th)
        if len(t) < 30:
            print(f"  >= {th:5.1f}% {'':<6}{len(t):>6}  too few")
            continue
        o, pv = perm_p(t, c)
        print(f"  >= {th:5.1f}% {'':<6}{len(t):>6}{t.mean():>+10.3f}"
              f"{c.mean():>+10.3f}{o:>+9.3f}{pv:>8.3f}")
    print("\n  A real supply shock should scale with size. A flat or noisy column")
    print("  across thresholds is the signature of no effect.")

    print("\n" + "=" * 96)
    print("4. PER-TOKEN — is any excess concentrated in a handful of names?")
    print("=" * 96)
    rows = sorted(((v[1] - v[2], k, v[0]) for k, v in per_tok.items()), reverse=True)
    pos = sum(1 for r in rows if r[0] > 0)
    print(f"  {pos} of {len(rows)} tokens had a positive excess "
          f"(coin-flip expectation {len(rows)/2:.1f})")
    print(f"\n  {'best 5':<10}{'excess %':>10}{'n':>5}      {'worst 5':<10}"
          f"{'excess %':>10}{'n':>5}")
    for i in range(min(5, len(rows) // 2)):
        g, s, n = rows[i]
        g2, s2, n2 = rows[-(i + 1)]
        print(f"  {s:<10}{g:>+10.2f}{n:>5}      {s2:<10}{g2:>+10.2f}{n2:>5}")

    print("\n" + "=" * 96)
    print("VERDICT")
    print("=" * 96)
    surv = [c for c, h in zip(cells, hp) if h < .05]
    print(f"  primary window T{PRIMARY[0]:+d}..T{PRIMARY[1]:+d}: "
          f"excess {obs:+.3f}% at p={p:.3f}")
    if not surv:
        print("\n  NOTHING SURVIVES. No window beats matched non-event windows of the")
        print("  same tokens once the grid is corrected for. The unlock is already in")
        print("  the price by the time it happens - which is what a published schedule")
        print("  should do in any market with participants.")
        print("\n  And remember both biases flatter this test: the schedule is the")
        print("  revised one, and dead tokens are missing. The true result is worse")
        print("  than what is printed above.")
    else:
        print(f"\n  {len(surv)} window(s) survived Holm. Before believing it: check the")
        print("  per-token table for concentration, and re-run with the delisted-coin")
        print("  universe from backtest/dead_fetch.py to kill the survivorship bias.")


if __name__ == "__main__":
    main()

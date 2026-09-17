"""TOKEN UNLOCKS ON THE COINS THAT DIED — the test that decides it.

    python -m backtest.unlocks_dead

WHAT backtest/unlocks.py LEFT OPEN
    On 101 Binance-listed tokens, shorting T-1..T+1 into a cliff of >=1% of supply
    beat matched non-event windows of the same tokens by +0.998% (n=508 against all
    20,301 control windows, p=0.016). Stable across 40 control redraws (sd 0.20).

    It failed two better tests: it did not scale with cliff size (+0.001% at the 0.5%
    threshold, +1.06% at 2%, +0.66% at 5%) and nothing survived Holm across eight
    declared windows (best corrected p=0.114).

    And it carried a bias that could not be removed there: SURVIVORSHIP. Only tokens
    trading on Binance today were in the sample, and tokens that died of supply are
    exactly the ones an unlock should hurt most.

THE PREDICTION THAT MAKES THIS A REAL TEST
    This is the one follow-up worth running, because the two explanations make
    OPPOSITE predictions on dead coins:

        if the +1% is a REAL supply effect  -> it should be LARGER here. These are
            the tokens whose supply actually buried them.
        if the +1% was SURVIVORSHIP         -> it should VANISH or invert. On
            survivors, a token that took an unlock and recovered is present; on the
            dead, the ones that never recovered are present too, and the control
            windows absorb the decline instead of the event windows.

    That asymmetry is what makes this decisive rather than another sample.

THE DATA
    backtest/dead_fetch.py already holds 202 delisted USDT pairs as hourly CSVs,
    downloaded from data.binance.vision in 2026-09 - AFTER this hypothesis was
    formed, so it is virgin test data for it. 15 of those 202 carry a DefiLlama
    unlock schedule, giving 780 scheduled events.

    Fifteen tokens is thin and it is stated rather than hidden. It is also biased in
    a way that works AGAINST the survivorship explanation: DefiLlama only tracks
    protocols notable enough to document, so even these dead coins are the more
    successful dead coins. A survivorship artifact should therefore be WEAKER here
    than in the live sample, not absent - so a clean vanish is strong evidence.

METHOD
    Identical to backtest/unlocks.py: same window, same >=1% threshold, same 12bp
    round trip, same matched-control construction (non-event windows of the SAME
    tokens over the SAME dates, all of them, no sampling). Nothing is retuned. The
    only thing that changes is the universe.

REGISTERED PREDICTION (2026-09-18, before running)
    The excess VANISHES or goes negative on the dead universe, because the live
    result already failed to scale with cliff size and a mechanism that does not
    scale is usually a composition effect rather than a force. I expect the pooled
    survivorship-free number to land near zero, which closes the category.

    If instead the excess is LARGER on dead coins, that is the first real
    non-informational edge found in this project and it changes what we deploy.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.unlocks import FEE_BP, PRIMARY, THRESH, holm, perm_p  # noqa: E402
from backtest.unlocks import load_events as load_events_live  # noqa: E402
from backtest.unlocks import load_prices as load_prices_live  # noqa: E402
from backtest.unlocks import window_ret  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data"
DEAD = DATA / "dead"
GRID = [(-1, 1), (-5, -1), (-5, 1), (-3, 0), (0, 1), (0, 3), (-1, 3), (-1, 5)]
rng = np.random.default_rng(113)


def load_prices_dead():
    """Daily closes for the delisted tokens, resampled from the hourly archive."""
    out = {}
    ev = json.load(open(DATA / "unlock_events_dead.json"))
    for sym in sorted({r["sym"] for r in ev}):
        f = DEAD / f"{sym}USDT_1h.csv.gz"
        if not f.exists():
            continue
        d = pd.read_csv(f, parse_dates=["time"])
        d = d.set_index("time").sort_index()
        day = d["close"].resample("1D").last().dropna()
        qv = (d["close"] * d["volume"]).resample("1D").sum()
        if len(day) < 120:
            continue
        out[sym] = pd.DataFrame({"c": day, "qv": qv.reindex(day.index).fillna(0.0)})
    return out


def load_events_dead(prices):
    rows = json.load(open(DATA / "unlock_events_dead.json"))
    df = pd.DataFrame([r for r in rows if r["kind"] == "cliff"])
    df["day"] = pd.to_datetime(df.ts, unit="s").dt.normalize()
    df["supply"] = df.adj_supply.fillna(df.max_supply)
    df = df[(df.supply > 0) & df.sym.isin(prices)]
    g = (df.groupby(["sym", "day"])
         .agg(tokens=("tokens", "sum"), supply=("supply", "first")).reset_index())
    g["pct"] = g.tokens / g.supply * 100
    return g


def build_full(prices, ev, a, b, thresh):
    """Treatment and ALL matched controls. No sampling, so no redraw noise."""
    T, C, per_tok = [], [], {}
    big = ev[ev.pct >= thresh]
    for sym, g in big.groupby("sym"):
        p = prices[sym]
        hits = [window_ret(p, d, a, b) for d in g.day]
        hits = [h for h in hits if h is not None]
        if not hits:
            continue
        alld = list(ev[ev.sym == sym].day)
        cand = [d for d in p.index if all(abs((d - e).days) > 10 for e in alld)]
        cs = [window_ret(p, d, a, b) for d in cand]
        cs = [x for x in cs if x is not None]
        if len(cs) < 5:
            continue
        T += hits
        C += cs
        per_tok[sym] = (len(hits), float(np.mean(hits)), float(np.mean(cs)))
    return np.array(T), np.array(C), per_tok


def main():
    print(__doc__.split("REGISTERED PREDICTION")[0].rstrip())
    print("\nREGISTERED: the excess VANISHES or inverts on dead coins. A mechanism")
    print("that does not scale with cliff size is usually composition, not force.")
    print("If it is LARGER on the dead, it is the first real non-informational edge")
    print("in this project.\n")

    pd_dead = load_prices_dead()
    ev_dead = load_events_dead(pd_dead)
    print(f"  DEAD universe:  {len(pd_dead)} delisted tokens with usable bars, "
          f"{len(ev_dead):,} cliff token-days")
    print(f"                  {ev_dead.day.min():%Y-%m-%d} .. "
          f"{ev_dead.day.max():%Y-%m-%d}")
    pd_live = load_prices_live()
    ev_live = load_events_live(pd_live)
    ev_live = ev_live[ev_live.day < pd.Timestamp.now("UTC").tz_localize(None)]
    ev_dead = ev_dead[ev_dead.day < pd.Timestamp.now("UTC").tz_localize(None)]
    print(f"  LIVE universe:  {len(pd_live)} listed tokens, "
          f"{len(ev_live):,} cliff token-days (for reference)")
    for th in (0.5, 1.0, 2.0):
        s = ev_dead[ev_dead.pct >= th]
        print(f"    dead, >= {th:4.1f}% of supply: {len(s):4} token-days across "
              f"{s.sym.nunique():2} tokens")
    print()

    a, b = PRIMARY
    print("=" * 96)
    print(f"1. THE DECIDING COMPARISON — short T{a:+d}..T{b:+d}, cliffs >= {THRESH}% "
          f"of supply")
    print("=" * 96)
    print(f"  {'universe':<14}{'events':>8}{'controls':>10}{'unlock':>10}"
          f"{'control':>10}{'excess':>9}{'p':>8}{'tokens':>8}")
    res = {}
    for lab, pr, ee in (("LIVE (survivors)", pd_live, ev_live),
                        ("DEAD (delisted)", pd_dead, ev_dead)):
        T, C, pt = build_full(pr, ee, a, b, THRESH)
        if len(T) < 15:
            print(f"  {lab:<14}{len(T):>8}   too few events to test")
            res[lab] = None
            continue
        o, p = perm_p(T, C)
        res[lab] = (T, C, o, p, pt)
        print(f"  {lab:<14}{len(T):>8}{len(C):>10}{T.mean():>+10.3f}"
              f"{C.mean():>+10.3f}{o:>+9.3f}{p:>8.3f}{len(pt):>8}")

    # pooled: the survivorship-free number
    if res.get("LIVE (survivors)") and res.get("DEAD (delisted)"):
        Tp = np.concatenate([res["LIVE (survivors)"][0], res["DEAD (delisted)"][0]])
        Cp = np.concatenate([res["LIVE (survivors)"][1], res["DEAD (delisted)"][1]])
        op, pp = perm_p(Tp, Cp)
        print(f"  {'POOLED':<14}{len(Tp):>8}{len(Cp):>10}{Tp.mean():>+10.3f}"
              f"{Cp.mean():>+10.3f}{op:>+9.3f}{pp:>8.3f}")
        print("\n  POOLED is the survivorship-free estimate: every token with a")
        print("  schedule and a price history, dead or alive, in one sample.")

    dead = res.get("DEAD (delisted)")
    if dead is None:
        print("\n  Not enough dead-coin events at this threshold to decide. See "
              "section 2.")

    print("\n" + "=" * 96)
    print("2. DEAD COINS BY CLIFF SIZE — does it scale where it should scale most?")
    print("=" * 96)
    print(f"  {'threshold':<14}{'events':>8}{'unlock':>10}{'control':>10}"
          f"{'excess':>9}{'p':>8}")
    for th in (0.25, 0.5, 1.0, 2.0, 5.0):
        T, C, _ = build_full(pd_dead, ev_dead, a, b, th)
        if len(T) < 15:
            print(f"  >= {th:5.2f}%{'':<5}{len(T):>8}   too few")
            continue
        o, p = perm_p(T, C)
        print(f"  >= {th:5.2f}%{'':<5}{len(T):>8}{T.mean():>+10.3f}"
              f"{C.mean():>+10.3f}{o:>+9.3f}{p:>8.3f}")
    print("\n  On the tokens that died of supply, a real effect should be strongest")
    print("  at the largest cliffs. The live sample went the other way.")

    print("\n" + "=" * 96)
    print("3. DEAD COINS, THE WINDOW GRID (Holm across all 8)")
    print("=" * 96)
    print(f"  {'window':<14}{'events':>8}{'unlock':>10}{'control':>10}"
          f"{'excess':>9}{'p':>8}{'Holm':>8}")
    raws, cells = [], []
    for wa, wb in GRID:
        T, C, _ = build_full(pd_dead, ev_dead, wa, wb, THRESH)
        if len(T) < 15:
            continue
        o, p = perm_p(T, C)
        raws.append(p)
        cells.append((wa, wb, len(T), T.mean(), C.mean(), o, p))
    hp = holm(np.array(raws)) if raws else []
    for (wa, wb, n, tm, cm, o, p), h in zip(cells, hp):
        star = " **" if h < .05 else (" *" if p < .05 else "")
        print(f"  T{wa:+d}..T{wb:+d}{'':<6}{n:>8}{tm:>+10.3f}{cm:>+10.3f}"
              f"{o:>+9.3f}{p:>8.3f}{h:>8.3f}{star}")

    print("\n" + "=" * 96)
    print("4. PER-TOKEN, DEAD UNIVERSE")
    print("=" * 96)
    if dead:
        rows = sorted(((v[1] - v[2], k, v[0]) for k, v in dead[4].items()),
                      reverse=True)
        pos = sum(1 for r in rows if r[0] > 0)
        print(f"  {pos} of {len(rows)} dead tokens had a positive excess "
              f"(coin-flip {len(rows)/2:.1f})")
        for g, s, n in rows:
            print(f"    {s:<8}{g:>+9.2f}%   n={n}")

    print("\n" + "=" * 96)
    print("VERDICT")
    print("=" * 96)
    live = res.get("LIVE (survivors)")
    if not (live and dead):
        print("  One universe was too thin to compare. The category stays open only")
        print("  to the extent that this test could not be run, which is a data")
        print("  limit rather than a result.")
        return
    lo, ld = live[2], dead[2]
    print(f"  live excess {lo:+.3f}%  (p={live[3]:.3f})")
    print(f"  dead excess {ld:+.3f}%  (p={dead[3]:.3f})")
    if ld > lo:
        print("\n  LARGER ON THE COINS THAT DIED. That is the direction a genuine")
        print("  supply effect must go, and it is the opposite of what survivorship")
        print("  would produce. Re-check the size-scaling column before deploying.")
    elif ld <= 0:
        print("\n  IT INVERTS ON DEAD COINS. The live +1% was survivorship: on")
        print("  survivors the recovered tokens are present and the never-recovered")
        print("  are missing. Category closed - and the live result should not have")
        print("  been reported as 'not dead, not tradable'. It is dead.")
    else:
        print("\n  SMALLER ON DEAD COINS, and the same direction. Consistent with a")
        print("  weak real effect contaminated by survivorship, but with this few")
        print("  dead tokens it is not separable. Not deployable either way.")


if __name__ == "__main__":
    main()

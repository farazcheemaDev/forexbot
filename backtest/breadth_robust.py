"""THIRD ROUND on the bear-market breadth trade: make the result concrete or kill it.

breadth_attack.py left three soft spots (logs/breadth_attack.txt): the trade's t is only
2.1-2.5, the 50-day breadth version fails the holdout, and it was found by a scan. This file
asks the questions that settle "is it real" with numbers rather than adjectives. Every run
uses the conservative setting: entered ONE DAY after the signal, 12bp, actual funding (exact
settlement window), 1bp/day basket rebalancing.

  1. PERMUTATION  (a) breadth circularly shifted against prices by >= 60 days, 1,000 times -
                  keeps breadth's own persistence, destroys its timing; (b) the SAME long and
                  short days reshuffled across bear days in 7-day blocks, 1,000 times - same
                  exposure, random timing. p = share of fakes that match the real rule.
  2. GRID         breadth average 10/15/20/30 x hold 3/5/7/10/14 x tail share 20/25/33/40% x
                  universe top-40/60/100 = 240 cells. How many are positive on BOTH halves?
  3. BEAR LABEL   'bear' = BTC below its m-day average and that average down more than s over
                  20 days, m 30/50/100 x s 0/2/5%. Nine definitions.
  4. EPISODES     consecutive signal days grouped into episodes; each episode's own P&L. The
                  honest sample size is the episode count, not the day count.
  5. COSTS        12 / 30 / 60 bp round trip, rebalancing 1 / 3 bp a day.
  6. $221         a 5-coin basket traded with Bitget's $5 minimum: an order that would move a
                  coin by less than $5 is skipped, and the position is whatever was really
                  bought. Also BTC + ETH.

REGISTERED PREDICTIONS (2026-09-24, before running)
  1. both permutation p < 0.05.
  2. >= 70% of the cells with breadth 10-20 positive on both halves; breadth 30 weaker.
  3. positive on both halves for >= 7 of the 9 bear definitions.
  4. >= 60% of long (capitulation) episodes and >= 55% of short episodes make money.
  5. still positive at 60bp round trip.
  6. the 5-coin basket skips < 10% of orders and keeps >= 80% of the frictionless return.

    python -m backtest.breadth_robust
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest import breadth_trade as bt  # noqa: E402
from backtest.breadth_attack import START, ls_signal  # noqa: E402
from backtest.breadth_trade import CUT, stats  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel  # noqa: E402
from backtest.regime_signals import member_mask  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

REPS = 1000


def ls_q(br, gate, q):
    """ls_signal with tail share q (1/3 in the original)."""
    g = gate.to_numpy(bool); b = br.to_numpy(float)
    s = np.zeros(len(b)); hist = []
    for d in range(len(b)):
        if len(hist) >= 60 and g[d] and np.isfinite(b[d]):
            lo, hi = np.quantile(hist, [q, 1 - q])
            s[d] = 1.0 if b[d] <= lo else (-1.0 if b[d] >= hi else 0.0)
        if g[d] and np.isfinite(b[d]):
            hist.append(b[d])
    return pd.Series(s, index=br.index)


def run(sig, inst, lag=1, h=7, side_bp=None, rebal=None):
    ret, fund, rb = inst
    old = (bt.H, bt.SIDE_BP)
    bt.H = h
    if side_bp is not None:
        bt.SIDE_BP = side_bp
    try:
        x, pos = bt.ladder(sig, ret, fund, rb if rebal is None else rebal, lag)
    finally:
        bt.H, bt.SIDE_BP = old
    return x[x.index >= START], pos[pos.index >= START]


def halves(x):
    a, b = x[x.index < CUT], x[x.index >= CUT]
    f = lambda g: ((1 + g).prod() ** (365 / max(len(g), 1)) - 1) * 100  # noqa: E731
    return f(x), f(a), f(b)


def breadth_n(C, mask, n):
    X = C.to_numpy(float)
    ma = C.rolling(n, min_periods=n).mean().to_numpy()
    ok = np.isfinite(ma) & mask
    cnt = ok.sum(1)
    return pd.Series(((X > ma) & ok).sum(1) / np.where(cnt > 0, cnt, np.nan), index=C.index).shift(1)


def basket(C, Fx, first, n):
    X = C.to_numpy(float); ff = pd.DataFrame(X).ffill().to_numpy(); fx = Fx.to_numpy(float)
    m = member_mask(C, first, drop_non_crypto(eligibility(n))) & np.isfinite(X)
    r = np.full(len(C), np.nan); f = np.full(len(C), np.nan)
    for d in range(1, len(C)):
        mem = m[d - 1]
        if mem.sum() >= min(8, n):
            r[d] = np.nanmean(ff[d, mem] / X[d - 1, mem] - 1); f[d] = fx[d, mem].mean()
    return pd.Series(r, index=C.index), pd.Series(f, index=C.index), bt.REBAL_BP


def small_account(C, Fx, first, sig, coins_fn, cap=221.0, min_order=5.0, lag=1, h=7):
    """Trade the ladder's target position on a real basket with a minimum order size.
    coins_fn(d) -> the basket's symbols for day d. Returns (equity series, skipped share)."""
    X = C.to_numpy(float); fx = Fx.to_numpy(float)
    cols = {s: i for i, s in enumerate(C.columns)}
    s = sig.to_numpy()
    tgt = np.zeros(len(s))
    for k in range(h):
        tgt += np.r_[np.zeros(lag + k), s[:len(s) - lag - k]] / h
    eq = cap
    hold = {}                                   # symbol -> signed notional (dollars)
    curve, tried, skipped = [], 0, 0
    for d in range(1, len(C)):
        # mark to market over row d, and funding (a short receives positive funding)
        pnl = 0.0
        for sym, nv in list(hold.items()):
            i = cols[sym]
            if not (np.isfinite(X[d, i]) and np.isfinite(X[d - 1, i])):
                continue                          # stopped trading: exits at last print (0 move)
            r = X[d, i] / X[d - 1, i] - 1
            pnl += nv * r - nv * fx[d, i]
            hold[sym] = nv * (1 + r)
        eq += pnl
        if eq <= 0:
            curve.append(0.0); break
        # rebalance toward target at the close of row d (the position for row d+1)
        want_pos = tgt[d + 1] if d + 1 < len(tgt) else 0.0
        basket_syms = coins_fn(d) if want_pos != 0 else []
        want = {sym: want_pos * eq / len(basket_syms) for sym in basket_syms}
        for sym in set(hold) | set(want):
            cur, w = hold.get(sym, 0.0), want.get(sym, 0.0)
            if abs(w - cur) < 1e-9:
                continue
            tried += 1
            if abs(w - cur) < min_order and not (w == 0.0 and abs(cur) > 0):
                skipped += 1                      # too small to place; closing is always allowed
                continue
            eq -= abs(w - cur) * bt.SIDE_BP
            if w == 0.0:
                hold.pop(sym, None)
            else:
                hold[sym] = w
        curve.append(eq)
    c = pd.Series(curve, index=C.index[1:1 + len(curve)])
    return c, skipped / max(tried, 1)


def main():
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    F.index = C.index
    reg = btc_regime(C).reindex(C.index)
    Fx = exact_funding(C.index, C.columns)
    X = C.to_numpy(float)
    masks = {N: member_mask(C, first, drop_non_crypto(eligibility(N))) & np.isfinite(X) for N in (40, 60, 100)}
    alt = basket(C, Fx, first, 40)
    top10 = basket(C, Fx, first, 10)
    bear = reg == "bear"
    b20 = breadth_n(C, masks[60], 20)
    s0 = ls_q(b20, bear, 1 / 3)
    x0, p0 = run(s0, alt)
    real = halves(x0)[0]
    print(f"reference (breadth20, top-60, hold 7, tails 1/3, alt index, lag 1): {real:+.1f}%/yr\n")

    # 1. permutations
    rng = np.random.default_rng(11)
    circ = []
    for _ in range(REPS):
        k = int(rng.integers(60, len(b20) - 60))
        sh = pd.Series(np.roll(b20.to_numpy(), k), index=b20.index)
        circ.append(halves(run(ls_q(sh, bear, 1 / 3), alt)[0])[0])
    circ = np.array(circ)
    sv = s0.to_numpy(); bi = np.flatnonzero(bear.to_numpy(bool))
    blocks = [bi[i:i + 7] for i in range(0, len(bi), 7)]
    shuf = []
    for _ in range(REPS):
        order = rng.permutation(len(blocks))
        vals = np.concatenate([sv[blocks[j]] for j in order])[:len(bi)]
        fake = np.zeros(len(sv)); fake[bi] = vals
        shuf.append(halves(run(pd.Series(fake, index=s0.index), alt)[0])[0])
    shuf = np.array(shuf)
    print("1. PERMUTATION (alt index, %/yr)")
    print(f"   circular shift of breadth, {REPS}x: fakes median {np.median(circ):+.1f}, 95th pct "
          f"{np.percentile(circ, 95):+.1f}, best {circ.max():+.1f} | real {real:+.1f} | "
          f"p = {(circ >= real).mean():.3f}")
    print(f"   same days reshuffled in 7-day blocks, {REPS}x: fakes median {np.median(shuf):+.1f}, 95th pct "
          f"{np.percentile(shuf, 95):+.1f}, best {shuf.max():+.1f} | real {real:+.1f} | "
          f"p = {(shuf >= real).mean():.3f}")

    # 2. grid
    print("\n2. GRID (top-10 basket): cells positive on BOTH halves")
    rows = []
    for N in (40, 60, 100):
        for n in (10, 15, 20, 30):
            br = breadth_n(C, masks[N], n)
            for q in (0.20, 0.25, 1 / 3, 0.40):
                s = ls_q(br, bear, q)
                for h in (3, 5, 7, 10, 14):
                    a, t, hh = halves(run(s, top10, h=h)[0])
                    rows.append(dict(N=N, n=n, q=q, h=h, all=a, tune=t, hold=hh))
    G = pd.DataFrame(rows)
    G["both"] = (G.tune > 0) & (G.hold > 0)
    print(f"   all 240 cells: {G.both.sum()} positive on both halves ({G.both.mean()*100:.0f}%), "
          f"median {G['all'].median():+.1f}%/yr, worst {G['all'].min():+.1f}")
    for key in ("n", "N", "h", "q"):
        g = G.groupby(key).agg(both=("both", "mean"), med=("all", "median"), tune=("tune", "median"),
                               hold=("hold", "median"))
        print(f"   by {key}: " + " | ".join(f"{k if key != 'q' else round(k, 2)}: {r.both*100:.0f}% both, "
                                          f"med {r.med:+.0f} (t {r.tune:+.0f} / h {r.hold:+.0f})"
                                          for k, r in g.iterrows()))
    G.to_csv(Path(__file__).resolve().parents[1] / "logs" / "breadth_grid.csv", index=False)

    # 3. bear label
    print("\n3. BEAR LABEL (alt index / top-10, %/yr: all | tune | holdout)")
    b = C["BTCUSDT"]
    for m in (30, 50, 100):
        ma = b.rolling(m).mean(); slope = ma / ma.shift(20) - 1
        for s_ in (0.0, 0.02, 0.05):
            g = ((b < ma) & (slope < -s_)).shift(1, fill_value=False).astype(bool)
            sg = ls_q(b20, g, 1 / 3)
            a1 = halves(run(sg, alt)[0]); a2 = halves(run(sg, top10)[0])
            print(f"   BTC < {m:>3}d avg, slope < -{s_*100:.0f}%  ({g.mean()*100:>3.0f}% of days): alt "
                  f"{a1[0]:+6.1f} | {a1[1]:+6.1f} | {a1[2]:+6.1f}    top-10 {a2[0]:+6.1f} | {a2[1]:+6.1f} | {a2[2]:+6.1f}")

    # 4. episodes: each maximal run of same-sign signal days (gaps <= 3 days) is one episode;
    #    its P&L = the book's P&L from its first tranche's entry to its last tranche's exit
    print("\n4. EPISODES (alt index): consecutive same-direction signal days, gaps <= 3 days")
    x_full, pos_full = run(s0, alt)
    sd = s0[s0 != 0]
    eps = []
    cur = None
    for t, v in sd.items():
        if cur and v == cur["side"] and (t - cur["end"]).days <= 4:
            cur["end"] = t
        else:
            if cur:
                eps.append(cur)
            cur = dict(side=v, start=t, end=t)
    if cur:
        eps.append(cur)
    out = []
    for e in eps:
        # this episode's own tranches only: the signal restricted to its days
        only = s0.where((s0.index >= e["start"]) & (s0.index <= e["end"]), 0.0)
        xe, _ = run(only, alt)
        out.append(dict(side="LONG" if e["side"] > 0 else "SHORT", start=e["start"].date(),
                        days=int((only != 0).sum()), ret=((1 + xe).prod() - 1) * 100))
    E = pd.DataFrame(out)
    for sd_ in ("LONG", "SHORT"):
        g = E[E.side == sd_]
        print(f"   {sd_:<5}: {len(g)} episodes, {(g.ret > 0).sum()} made money ({(g.ret > 0).mean()*100:.0f}%), "
              f"mean {g.ret.mean():+.2f}%, median {g.ret.median():+.2f}%, best {g.ret.max():+.1f}%, worst {g.ret.min():+.1f}%")
    print("   every episode (account %, the book's slice of it):")
    for _, r in E.iterrows():
        print(f"     {r.side:<5} {r.start}  {r.days:>3} signal days  {r.ret:+6.2f}%")

    # 5. costs
    print("\n5. COSTS (alt index, %/yr all | tune | holdout)")
    for rt in (12, 30, 60):
        for rb in (1, 3):
            a = halves(run(s0, alt, side_bp=rt / 2 / 1e4, rebal=rb / 1e4)[0])
            print(f"   {rt:>2}bp round trip, {rb}bp/day rebalancing: {a[0]:+6.1f} | {a[1]:+6.1f} | {a[2]:+6.1f}")

    # 6. $221
    print("\n6. $221 WITH A $5 MINIMUM ORDER (lag 1, 7-day ladder netted into one daily target)")
    vol = {}
    m10 = masks[40]
    elig5 = drop_non_crypto(eligibility(5))
    months = C.index.strftime("%Y-%m")
    cols = list(C.columns)

    by_month = {m: [s for s in cols if m in elig5.get(s, ())] for m in sorted(set(months))}
    ci = {s: i for i, s in enumerate(cols)}

    def top5(d):
        return [s for s in by_month[months[d]] if np.isfinite(X[d, ci[s]])][:5]

    def btceth(d):
        return ["BTCUSDT", "ETHUSDT"]

    for lab, fn in (("top-5 basket", top5), ("BTC + ETH", btceth)):
        for tag_, t0 in (("full", START), ("holdout", CUT)):
            sig = s0.where(s0.index >= t0, 0.0)
            c, skip = small_account(C, Fx, first, sig, fn)
            c = c[c.index >= t0]
            yrs = len(c) / 365
            print(f"   {lab:<13} {tag_:<8} $221 -> ${c.iloc[-1]:,.0f}  ({((c.iloc[-1]/221) ** (1/yrs) - 1)*100:+.1f}%/yr, "
                  f"DD {(1 - c / c.cummax()).max()*100:.0f}%), orders skipped for size {skip*100:.1f}%")
        # frictionless reference on the same basket: ladder on the basket's own daily return
    print("   (frictionless ladder on the alt index, same windows: "
          f"full {halves(x0)[0]:+.1f}%/yr, holdout {halves(x0)[2]:+.1f}%/yr)")


if __name__ == "__main__":
    main()

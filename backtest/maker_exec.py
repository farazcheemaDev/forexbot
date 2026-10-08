"""LIMIT-ORDER (MAKER) EXECUTION FOR TODAY'S BEST 1-MINUTE EDGES - the one thing scalp_1m / btc_doge only bounded.

WHY
    The user (2026-10-06): "find an edge, there is something you have undermined." Audit of today's work: funding
    carry and spikes were already measured dead (doc 02); the leverage and one-shot tests are arithmetic on measured
    paths. The gap is EXECUTION. scalp_1m and btc_doge filled every trade at the next minute's open and treated
    "maker 4bp" as an upper bound. That is wrong in BOTH directions:
      - for the trader: a limit order pays the maker fee (Bitget 0.02% a side, some venues less) and fills at its
        own price, not the next open;
      - against the trader: a resting buy fills only when the price falls THROUGH it, so fills are concentrated on
        the trades that are going wrong (adverse selection).
    This measures both.

THE EXECUTION MODEL (1m bars, Binance USDT-M perps, 2022-01 .. 2026-08; holdout from 2024-10-19)
    Entry   a limit at the signal minute's close, valid 3 minutes; FILLED only if a later minute trades THROUGH it
            (buy: low < limit; sell: high > limit - strictly, so touching is not a fill). Unfilled = no trade.
    Exits   model trades (btc_doge): a limit at the close h minutes after the fill, valid 3 minutes, filled only on a
            trade-through, else closed at market (taker) at the 3rd minute's close.
            rule trades (scalp_1m rsi_mom short 2R): take-profit by limit (maker, trade-through), stop 2xATR by stop-
            market (taker, gap-through filled at the open), 60-minute timeout at market (taker). Stop first if a
            minute touches both.
    Fees    maker f in {0, 1, 2bp} a leg (2bp = Bitget's standard maker), taker 6bp (Bitget's standard taker).
    Compared with the SAME signals filled at the next open (what scalp_1m / btc_doge assumed): the gap is the
    adverse-selection cost of resting orders.

REGISTERED BEFORE THE RUN (2026-10-06)
    - Fill rate within 3 minutes 50-70%.
    - Filled trades do >= 2bp a trade WORSE gross than the same signals at the next open (adverse selection).
    - rsi_mom short 2R (BTC and DOGE): negative even at 0bp maker - its stops and timeouts still pay 6bp taker.
    - btc_doge models (h 15 and 60): gross with maker execution +3 to +8bp; positive only at 0-1bp maker; t < 2.

RESULT (2026-10-06, logs/maker_exec.txt; A = holdout 2024-10-19 .. 2026-08-31, B = all of 2022-01 .. 2026-08)
    - Limits at the signal close fill 93-96% of the time within 3 minutes on a strict trade-through (predicted
      50-70%: WRONG - 1m prices revisit the last close almost always).
    - Adverse selection, maker gross vs the next-open gross of EVERY signal tried: -2.3 / -2.4bp (15-min models),
      -1.8 / -1.6bp (60-min models), -0.6 / -1.3bp (rsi_mom BTC / DOGE). Predicted >= 2bp: right at 15 min, a
      little smaller elsewhere. (A first printout compared against the FILLED signals only and understated it -
      the 4-7% that never fill are mostly ones that moved the trader's way at once, i.e. the adverse selection.)
    - rsi_mom short 2R: -4.0 / -4.5bp a trade even at 0bp maker (stops and timeouts pay 6bp taker). Dead. Right.
    - btc_doge ridge, 60 min: +8.3bp gross; NET +4.07bp a trade at Bitget's standard 2bp maker (t +1.0), +7.97bp at
      0bp (t +1.9); break-even maker fee 4.1bp a leg. Ridge 15 min: +1.19bp at 2bp (t +0.5), +5.10bp at 0bp
      (t +2.3). Trees: +2.2 / -1.1bp at 0bp, negative at 2bp. Predicted "positive only at 0-1bp, t < 2": WRONG for
      ridge 60, which stays positive at Bitget's fee - but at t +1.0 it is not distinguishable from zero.
    Reading: the execution assumption was the thing undermined, and fixing it moves ONE candidate (ridge, 60 min,
    limit orders) from "loses at taker fees" to "+4bp a trade at Bitget's maker fee, unproven". At 1x that is about
    +60% over 22 months IF real (1,490 trades); it has no stop, so leverage meets the 2025-10-10 hour. It is a
    candidate for a forward paper test, not a result. The holdout has now been read by btc_doge and by this file.

    python -m backtest.maker_exec
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import odds_now as on  # noqa: E402
from backtest import btc_doge as bd  # noqa: E402
from backtest import scalp_1m as sc  # noqa: E402

LOG = ROOT / "logs" / "maker_exec.txt"
W = 3
TAKER = 0.0006
MAKERS = (0.0, 0.0001, 0.0002)
CS = bd.CS


def limit_fill(i, side, price, h, l, w=W):
    """First minute in i+1..i+w that trades THROUGH price (buy: low < price; sell: high > price), or -1."""
    seg = l[i + 1:i + 1 + w] < price if side > 0 else h[i + 1:i + 1 + w] > price
    return i + 1 + int(np.argmax(seg)) if seg.any() else -1


def model_trade(i, side, hold, o, h, l, c):
    """Maker entry at c[i]; exit limit at c[x], x = fill + hold, else market at c[x + W].
    Returns (gross, n_maker_legs, n_taker_legs, exit index) or None if the entry never fills."""
    n = len(c)
    j = limit_fill(i, side, c[i], h, l)
    if j < 0 or j + hold + W >= n:
        return None
    x = j + hold
    k = limit_fill(x, -side, c[x], h, l)                     # the exit is a sell for a long
    if k >= 0:
        ex, maker_out = c[x], 1
    else:
        ex, maker_out = c[x + W], 0
        k = x + W
    return side * (ex / c[i] - 1), 1 + maker_out, 1 - maker_out, k


def rule_trade(i, side, atr_i, o, h, l, c, k_r=2, hold=60):
    """Maker entry at c[i]; stop 2xATR (stop-market, taker), target k_r R (limit, maker, trade-through),
    timeout at market. Returns (gross, maker legs, taker legs, exit index) or None."""
    n = len(c)
    j = limit_fill(i, side, c[i], h, l)
    if j < 0 or j + hold + 1 >= n:
        return None
    e = c[i]
    r = on.STOP_ATR * atr_i
    stop, tp = e - side * r, e + side * k_r * r
    for m in range(j, min(j + hold, n - 1) + 1):
        if m == j:
            # the fill minute: only the part of the bar after the fill is unknown - be pessimistic, stop counts
            hit_s = (l[m] <= stop) if side > 0 else (h[m] >= stop)
            if hit_s:
                return side * (stop / e - 1), 1, 1, m
            continue
        hit_s = (l[m] <= stop) if side > 0 else (h[m] >= stop)
        hit_t = (l[m] < tp) if side < 0 else (h[m] > tp)
        if hit_s:
            fill = min(o[m], stop) if side > 0 else max(o[m], stop)
            return side * (fill / e - 1), 1, 1, m
        if hit_t:
            return side * (tp / e - 1), 2, 0, m
    m = min(j + hold, n - 1)
    return side * (c[m] / e - 1), 1, 1, m


def run_set(idx, sides, fn, times, split, next_open_gross):
    """Execute signals one at a time (a signal is skipped while a trade is open). Returns a summary dict."""
    rows, free, tried, open_all = [], -1, 0, []
    for i, s in zip(idx, sides):
        if i < free:
            continue
        tried += 1
        open_all.append(next_open_gross(i, s))                 # every signal tried, filled or not
        r = fn(i, s)
        if r is None:
            continue
        g, mk, tk, ex = r
        rows.append((i, g, mk, tk, next_open_gross(i, s)))
        free = ex + 1
    if not rows:
        return None
    a = np.array(rows)
    i_, g, mk, tk, g_open = a[:, 0].astype(np.int64), a[:, 1], a[:, 2], a[:, 3], a[:, 4]
    tune = times[i_] < split
    days = times[i_].astype("datetime64[D]")
    out = dict(tried=tried, filled=len(a), gross=g.mean(), gross_open=np.nanmean(g_open),
               gross_open_all=np.nanmean(open_all),
               maker_legs=mk.mean(), taker_legs=tk.mean())
    for f in MAKERS:
        net = g - mk * f - tk * TAKER
        mu = net.mean()
        s_ = pd.Series(net - mu).groupby(days).sum().to_numpy()
        se = np.sqrt((s_ ** 2).sum() * len(s_) / max(len(s_) - 1, 1)) / len(net)
        out[f] = dict(net=mu, t=mu / se, tune=net[tune].mean() if tune.any() else np.nan,
                      hold=net[~tune].mean() if (~tune).any() else np.nan)
    out["breakeven_maker_bp"] = (g.mean() - tk.mean() * TAKER) / mk.mean() * 1e4
    return out


def fmt(name, s):
    if s is None:
        return f"  {name}: no fills"
    cells = "  ".join(f"maker {f * 1e4:.0f}bp: {s[f]['net'] * 1e4:+.2f}bp (t {s[f]['t']:+.1f}; tune {s[f]['tune'] * 1e4:+.2f} / "
                      f"hold {s[f]['hold'] * 1e4:+.2f})" for f in MAKERS)
    return (f"  {name}: {s['filled']}/{s['tried']} filled ({s['filled'] / s['tried']:.0%}); gross {s['gross'] * 1e4:+.2f}bp "
            f"vs {s['gross_open'] * 1e4:+.2f}bp for the filled signals and {s['gross_open_all'] * 1e4:+.2f}bp for EVERY "
            f"signal tried, at the next open; legs maker {s['maker_legs']:.2f} / "
            f"taker {s['taker_legs']:.2f}; break-even maker fee {s['breakeven_maker_bp']:+.2f}bp a leg\n      {cells}")


def main():
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    t0 = time.time()
    lines = [f"backtest/maker_exec.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; limits valid {W} min, filled only on a "
             f"trade-through; taker {TAKER * 1e4:.0f}bp", ""]

    # ---- A. the btc_doge models, with maker execution on the holdout
    m, X, names, Y, ok, _, (od, hd, ld) = bd.build()
    cd = m.c_d.to_numpy(float)
    n = len(m)
    times = m.time.to_numpy()
    split = np.sort(times)[int(n * 0.6)]
    is_tune = times < split
    fit_end = np.sort(times[is_tune])[int(is_tune.sum() * 0.75)]
    lines.append("A. btc_doge models (fit < 2024-02, threshold on 2024-02..10 by maker-execution GROSS, HOLDOUT shown):")
    for hold in (15, 60):
        y = Y[hold]
        fm = ok & (times < fit_end) & np.isfinite(y)
        vm = ok & is_tune & (times >= fit_end) & np.isfinite(y)
        hm = ok & ~is_tune & np.isfinite(y)
        sub = np.sort(np.random.default_rng(hold).choice(np.flatnonzero(fm), 600_000, replace=False))
        for mname, model in (("ridge", make_pipeline(StandardScaler(), Ridge(alpha=10.0))),
                             ("trees", HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05,
                                                                    max_leaf_nodes=31, min_samples_leaf=500,
                                                                    random_state=0))):
            model.fit(X[sub], y[sub])
            pred = np.full(n, np.nan)
            r_ = np.flatnonzero(ok)
            for a in range(0, len(r_), 500_000):
                pred[r_[a:a + 500_000]] = model.predict(X[r_[a:a + 500_000]])

            def fn(i, s, hold=hold):
                return model_trade(i, s, hold, od, hd, ld, cd)

            def nxt(i, s, hold=hold):
                return s * (cd[i + hold] / od[i + 1] - 1)

            best = None
            for c_ in CS:
                idx = np.flatnonzero(vm & (np.abs(pred) > c_))
                if len(idx) < 300:
                    continue
                sv = run_set(idx, np.sign(pred[idx]), fn, times, split, nxt)
                if sv and sv["filled"] >= 200 and (best is None or sv["gross"] > best[1]):
                    best = (c_, sv["gross"])
            if best is None:
                lines.append(f"  h={hold} {mname}: too few validation fills")
                continue
            idx = np.flatnonzero(hm & (np.abs(pred) > best[0]))
            lines.append(fmt(f"h={hold:>2}m {mname} |pred| > {best[0] * 1e4:.0f}bp", run_set(idx, np.sign(pred[idx]), fn,
                                                                                       times, split, nxt)))
        print(f"  A h={hold} done ({time.time() - t0:.0f}s)", flush=True)

    # ---- B. the best named gross edge: rsi_mom short 2R, BTC and DOGE, all of history
    lines.append("\nB. rsi_mom short 2R (scalp_1m's best named gross edge), every signal 2022-01 .. 2026-08:")
    for coin in ("BTCUSDT", "DOGEUSDT"):
        d = sc.load(coin)
        o, h, l, c = (d[k].to_numpy(float) for k in "ohlc")
        f = on.features(o, h, l, c)
        ok_c = sc.valid_mask(d) & f["ok"]
        tms = d.time.to_numpy()
        sig = sc.rules(d, f)["rsi_mom"][1] & ok_c
        idx = np.flatnonzero(sig)
        idx = idx[idx < len(c) - 70]
        atr = f["atr"]

        def fn(i, s):
            return rule_trade(i, s, atr[i], o, h, l, c)

        oc = on.races(o, h, l, c, atr, -1, None, ks=(2,), hold=60, fee=0.0)[2]

        def nxt(i, s):
            return oc[2][i] / 100                              # gross % at the next open, same exits

        lines.append(fmt(coin, run_set(idx, -np.ones(len(idx)), fn, tms, split, nxt)))
        print(f"  B {coin} done ({time.time() - t0:.0f}s)", flush=True)

    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")
    print(f"\n-> {LOG} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()

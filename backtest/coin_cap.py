"""ONE COIN IN SEVERAL BOOKS - how often, how much, and what a per-coin cap would do (2026-10-20)

Seen live (2026-10-19): BTW was held LONG by the market-neutral, carry and daily books at once, in both paper accounts,
and its -18.8% day hit all three. The liquidation test (liq_now.py) found the mirror risk: one small coin SHORT in both
MN and carry, squeezing. The user agreed to test "a per-coin limit across all strategies". This measures it on the
backtest's own positions, coin by coin, day by day.

    exposure  signed share of the account per coin per day, summed over:
                MN (half momentum / half RSI-ranked, 10% each side, weekly; 0.25/k a coin a half) - moderate_retests' ranking
                carry x0.5 (long the lowest 7-day funding, short the highest, 20% each side, weekly)
                daily x0.5 (1/8 of the account a trade, long)      capit2 at 2x (2/8 a trade, long)
                news (short the coin 0.10, long BTC 0.10)
              the trend book (12 large coins, sized by its own simulator) and NASDAQ are left out - noted
    P&L       each coin's close-to-close return on the exposure held into that day (an approximation: entries / exits
              inside a day and the MN short exits are not modelled here)
    CAP X     each coin's NET exposure trimmed to +-X; the trimmed part's P&L is removed from the machine (fees ignored)
              X = 15% (also cuts capit2's own 25% a coin) / 25% (only stacking above a capit2 position) / 35%
    judged    inside the 9-book machine (10 orderings, $300, 12 months), tune before 2024-08-29

RUN 1 (2026-10-20 11:53) capped BTC too - the news book's hedge leg (6-7 open news trades = 66% BTC long): the 15% cap
then left news shorts unhedged. Run 2 exclude BTC from the cap and from the counts. Predictions unchanged.

REGISTERED BEFORE THE RUN (2026-10-20)
    K1 some coin carries more than 15% of the account on at least 10% of days (stacking is common).
    K2 a 15% cap changes the machine's typical year by less than 5% on both halves.
    K3 a 15% cap improves the worst month by at least 1 point on at least one half.

RESULT (2026-10-20, run 2, logs/coin_cap.txt; run 1 kept as logs/coin_cap_run1.txt) - K1 RIGHT, K2 / K3 WRONG.
    Stacking is common and moderate: a coin over 15% of the account on 42% of days, over 25% on 5%, the largest ~32-35%
    (DOGE on 2022-11-09, BCH 2024-04-14). A 15% cap costs -1.9% / -11.9% of the typical year (tune / holdout) and moves
    the worst month and fall by under a point - the machine's big losses are market-wide (the trend book), not one
    coin. A 25% cap costs ~0 (+0.4% / -0.6%) and rarely binds; 35% never. Not a return lever; at 25% it is free
    insurance against a freak single-coin day the monthly figures cannot see. The MN + carry squeeze case (liq_now.py,
    10.4% short) sits under any of these caps - there the protection is the exchange stops and the +50% short exits.

    python -m backtest.coin_cap
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "coin_cap.txt"
CAPS = (0.15, 0.25, 0.35)


def basket_weeks(score_mat, start, look, frac, D, m):
    """(i, end_i, longs, shorts, k) of each weekly basket - mn_combos' selection (ranking from score_mat row i)."""
    idx, X_ = D["idx"], D["X"]
    hold, out = 7, []
    for i in range(look + 1 + start, len(idx) - hold - 1, hold):
        t0 = idx[i]
        ok = (D["Em"][D["months"][i]] & ((t0.value - D["fv"]) // 86_400_000_000_000 >= m.MIN_AGE_D)
              & np.isfinite(X_[i]) & np.isfinite(X_[i - look]))
        if ok.sum() < 20:
            continue
        cand = np.flatnonzero(ok)
        past = score_mat[i, cand]
        k = max(int(len(cand) * frac), 3)
        order = cand[np.argsort(np.where(np.isnan(past), np.inf, past), kind="stable")]
        out.append((i, i + hold, order[-k:], order[:k], k))
    return out


def main():
    from backtest import capit_combos as cc
    from backtest import daily_combos as dc
    from backtest import machine_combos as mc
    from backtest import mn_combos as m
    from backtest.all_books import BOOKS, machine_books, ndx_dip, news_book
    from backtest.machine import CUT, summary
    from backtest.profit_take import score_mats
    from backtest.liq_now import news_taken
    D = m.data()
    idx, X = D["idx"], D["X"]
    cols = list(D["cols"])
    col = {c: j for j, c in enumerate(cols)}
    R = np.vstack([np.full(X.shape[1], np.nan), X[1:] / X[:-1] - 1])            # return INTO day t
    R = np.nan_to_num(R)
    nT = len(idx)
    mom, rsi = score_mats()
    if "SC7" not in D:
        D["SC7"] = -pd.DataFrame(D["Fx"]).rolling(7, min_periods=7).sum().to_numpy()
    day_of = pd.DatetimeIndex(idx).normalize()

    def add_trades(E, T, taken, w):
        tin = pd.DatetimeIndex(T.t_in.to_numpy("datetime64[ns]")).normalize()
        tout = pd.DatetimeIndex(T.t_out.to_numpy("datetime64[ns]")).normalize()
        coins = T.coin.to_numpy()
        for q, _, _ in taken:
            j = col.get(coins[q])
            if j is None:
                continue
            a, b = day_of.searchsorted(tin[q]), day_of.searchsorted(tout[q])
            E[a + 1:b + 1, j] += w                                               # held into days a+1 .. b

    # news positions (the same in every ordering)
    En = np.zeros((nT, len(cols)))
    for t_in, t_out, coin in news_taken():
        a = day_of.searchsorted(pd.Timestamp(t_in).normalize())
        b = day_of.searchsorted(pd.Timestamp(t_out).normalize())
        if coin in col:
            En[a + 1:b + 1, col[coin]] -= 0.10
        if "BTCUSDT" in col:
            En[a + 1:b + 1, col["BTCUSDT"]] += 0.10
    dT = {off: dc.gen(off, dict(dc.BASE, mean_n=20)) for off in dc.PHASES}
    cT = {off: cc.gen(off, dict(cc.BASE, **mc.CAPIT_BETTER)) for off in cc.PHASES}
    M = machine_books()
    nw, nd = news_book(), ndx_dip()
    RUNNING = [b for b in BOOKS if b != "bids"]
    base_daily, capped = [], {c: [] for c in CAPS}
    share_days = {c: [] for c in (0.10, 0.15, 0.25)}
    maxE, top = [], []
    for sd, x in zip(mc.SEEDS, M):
        o = sd % 7
        E = En.copy()
        for half in (mom, rsi):                                                  # MN: 0.25 / k a coin a half
            for i, j_end, lo, sh, k in basket_weeks(half, o, 30, 0.1, D, m):
                E[i + 1:j_end + 1, lo] += 0.25 / k
                E[i + 1:j_end + 1, sh] -= 0.25 / k
        for i, j_end, lo, sh, k in basket_weeks(D["SC7"], o, 1, 0.2, D, m):     # carry x0.5: 0.5 x 0.5 / k
            E[i + 1:j_end + 1, lo] += 0.25 / k
            E[i + 1:j_end + 1, sh] -= 0.25 / k
        doff, coff = dc.PHASES[sd % 3], cc.PHASES[sd % 4]
        add_trades(E, dT[doff], dc.allocate(dT[doff], sd), 0.5 / 8)
        add_trades(E, cT[coff], dc.allocate(cT[coff].assign(units=None), sd, 2.0), 2.0 / 8)
        A = np.abs(E)
        if "BTCUSDT" in col:                     # BTC is the news book's HEDGE leg (and the market): never capped,
            A[:, col["BTCUSDT"]] = 0.0           # never counted - run 1 trimmed the hedges (66% BTC on 2025-07-10)
        mx = A.max(axis=1)
        maxE.append(float(mx.max()))
        jj = np.unravel_index(np.argmax(A), A.shape)
        top.append((float(A[jj]), cols[jj[1]], f"{idx[jj[0]]:%Y-%m-%d}"))
        live = mx > 0
        for c in share_days:
            share_days[c].append(float((mx[live] > c).mean()))
        daily = (x[RUNNING].sum(axis=1) + nw.reindex(x.index).fillna(0.0) + nd.reindex(x.index).fillna(0.0))
        base_daily.append(daily)
        for c in CAPS:
            trim = np.sign(E) * np.maximum(A - c, 0.0)
            adj = pd.Series(-(trim * R).sum(axis=1), index=day_of).groupby(level=0).sum()
            capped[c].append(daily.add(adj.reindex(daily.index).fillna(0.0), fill_value=0.0))
    lines = [f"backtest/coin_cap.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; per-coin net exposure across MN, carry, "
             f"daily, capit2 (2x) and news; the 9-book machine (no crash bids), $300, 12 months, 10 orderings", "",
             "1. HOW OFTEN ONE COIN CARRIES A LOT (days with any position; median over orderings)",
             "   " + "   ".join(f"> {c:.0%} of the account on {np.median(v) * 100:.0f}% of days" for c, v in share_days.items()),
             f"   the largest single-coin exposure: median {np.median(maxE) * 100:.0f}% of the account; e.g. "
             + "; ".join(f"{a * 100:.0f}% {cn} {d}" for a, cn, d in sorted(top, reverse=True)[:3]), "",
             "2. THE MACHINE WITH A PER-COIN CAP",
             f"   {'cap':<10}{'half':>8}{'typical':>9}{'bad':>8}{'worst':>8}{'worst mo':>9}{'fall':>6}{'up':>5}"]
    S = {}
    for name, ser in [("none", base_daily)] + [(f"{c:.0%}", capped[c]) for c in CAPS]:
        for half, s in (("tune", summary([z[z.index < CUT] for z in ser])), ("holdout", summary(ser, CUT))):
            S[(name, half)] = s
            lines.append(f"   {name:<10}{half:>8} ${s['typ']:>7,.0f} ${s['bad']:>6,.0f} ${s['worst']:>6,.0f}{s['wm']:>+8.1f}%"
                         f"{s['dd']:>5.0f}%{s['up']:>4.0f}%")
    k1 = np.median(share_days[0.15]) >= 0.10
    k2 = all(abs(S[("15%", h)]["typ"] / S[("none", h)]["typ"] - 1) < 0.05 for h in ("tune", "holdout"))
    k3 = any(S[("15%", h)]["wm"] - S[("none", h)]["wm"] >= 1.0 for h in ("tune", "holdout"))
    lines += ["", "REGISTERED PREDICTIONS",
              f"  K1 a coin over 15% on >= 10% of days: {np.median(share_days[0.15]) * 100:.0f}% -> {'RIGHT' if k1 else 'WRONG'}",
              f"  K2 15% cap moves the typical year < 5% on both halves: " + ", ".join(
                  f"{h} {S[('15%', h)]['typ'] / S[('none', h)]['typ'] - 1:+.1%}" for h in ("tune", "holdout"))
              + f" -> {'RIGHT' if k2 else 'WRONG'}",
              f"  K3 15% cap improves the worst month >= 1 point on a half: " + ", ".join(
                  f"{h} {S[('15%', h)]['wm'] - S[('none', h)]['wm']:+.1f}" for h in ("tune", "holdout"))
              + f" -> {'RIGHT' if k3 else 'WRONG'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

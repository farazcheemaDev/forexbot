"""LIQUIDATION STRESS FOR THE MACHINE THAT RUNS NOW - before any real money (2026-10-18)

The user: "I just want to know I won't be liquidated on this bot". liq_stress.py (2026-10-16) answered for the machine of
that day: no hour since 2020 under the liquidation line, closest 29% left. Since then: the NEWS book (short coin / long
BTC, 1/10 of the account a leg, up to 10 open), the NASDAQ-DIP book (QQQ at 1x the account), the gross cap 11.5x -> 14.5x
(the liquidation line rises with it), and the crash bids are NOT in the running final bot (no --wick). Same method:
every open position at its worst price of each hour, all at once (harsher than reality).

    trend / daily / capit2 2x / bids   liq_stress.py's own construction (orderings 0, 1, 2)
    news     news.combo's deployed rule (adds_products + monitoring_tag, 72h, +25% stop), first 10 open at a time; each
             hour: the coin at its HIGH (a squeeze against the short) and BTC at its LOW, 0.10 of the account a leg,
             not capped at the stop (the bot checks it every 2 minutes; a squeeze can jump past it)
    ndx      ndx_capit.py's deployed rule (RSI(2) < 10 at the close, out above the 5-day mean / 10 closes), QQQ at 1x the
             account, entered at the 16:00 New York close; each hour at the NASDAQ-100's hourly LOW (HistData NSXUSD
             1-minute bars, New York clock -> UTC). The 24/7 QQQ perp's weekend moves are not in this data.
    MN/carry hedged baskets - their risk is ONE shorted coin squeezing: bounded separately as the largest 1-hour spike
             (high / open - 1) of any point-in-time top-60 coin since 2020, times the largest short one coin can carry
             (MN 1/12 + carry 1/24 x 0.5 = 10.4% of the account)
LINES  liquidation at ~1.5% of gross notional: 21.75% left at the 14.5x cap (17% at the old 11.5x). Conservative: the
       account is rarely at its cap in a crash hour.

REGISTERED BEFORE THE RUN (2026-10-18)
    L1 the running machine (no bids; + news + NASDAQ) stays above the 21.75% line in every ordering, and its worst hour
       is no more than 5 points worse than liq_stress.py's FULL machine (29 / 41 / 50% left).
    L2 the NASDAQ-dip book alone never loses more than 15% of the account in one hour.
    L3 the single-coin squeeze bound is under 10% of the account.

RESULT (2026-10-18, logs/liq_now.txt) - NO hour since 2020 crosses the 21.75% line; L1 / L2 RIGHT, L3 WRONG.
    Running now, worst hour left (ordering 0 / 1 / 2): 55% (2025-10-10 21:00, trend -38) / 32% (2021-12-04 05:00, capit2
    2x -54, daily -14) / 51% (2025-02-03 02:00, capit2 -62). Dropping the crash bids helped (41 -> 55% in ordering 0);
    news (worst 78% alone, a squeeze 2025-09-08) and NASDAQ (87% alone, 2020-03-13; worst point in a trade -12.7%) add ~0
    at the crash hours. capit2 at 1x: 55 / 59 / 80% - the big safety dial (liq_fix.py: ~11% of the typical year).
    The squeeze bound is real, not a bad tick: LUNA +452% in the hour of 2022-05-11 13:00 (0.503 -> 2.777 high, its
    collapse's dead-cat bounce); 12 of 470 top-60 coins spiked > +100% in one hour since 2020, several 2024-26 small
    coins. At the most one coin can be shorted across MN + carry (10.4%) that is -47%; stacked on the worst hour it
    crosses the line (a pessimistic stack: shorts gain in a crash hour). NOT in this test: the live bot's 30% exchange
    stop on every position and the books' +50% short exits, which cut a squeeze to ~3-10% of the account unless the
    stop gaps. A per-coin short cap is the untested fix if real money goes in.

    python -m backtest.liq_now
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.dd_fixes as D  # noqa: E402
from backtest import blend  # noqa: E402
from backtest import capit_combos as cc  # noqa: E402
from backtest import daily_combos as dc  # noqa: E402
from backtest import machine_combos as mc  # noqa: E402
from backtest.bar_phase import rows_for_phase  # noqa: E402
from backtest.bull_boost import regimes  # noqa: E402
from backtest.capitulation_wide import hourly  # noqa: E402
from backtest.joint_worst_hour import trend_frac  # noqa: E402
from backtest.liq_stress import book_worst  # noqa: E402
from backtest.wick_5m import CACHE, per_fill  # noqa: E402
from backtest.wick_better import fills, load_all  # noqa: E402

LOG = ROOT / "logs" / "liq_now.txt"
LINE_NOW, LINE_OLD = 0.015 * 14.5, 0.015 * 11.5
MAX_SHORT_ONE_COIN = 1 / 12 + 0.5 / 24


def news_taken() -> list:
    """(t_in ns, t_out ns, coin) of the trades the deployed news rule takes, first 10 open at a time."""
    import news.combo as NC
    import news.news_book as NB
    NC.TYPES, NC.HOLD, NC.STOP = ("adds_products", "monitoring_tag"), 72, 0.25
    E = pd.read_parquet(NB.EV)
    E = E[E.etype.isin(NC.TYPES) & (E.coins != "")]
    tr = []
    for r in E.itertuples():
        entry = (pd.Timestamp(r.t).floor("h") + pd.Timedelta(hours=1)).value
        for coin in r.coins.split(",")[:3]:
            if not coin or coin == "BTCUSDT":
                continue
            x = NB.trade(coin, entry, NC.HOLD, NC.STOP)
            if x is not None:
                tr.append((entry, int(x[2]), coin))
    tr.sort()
    taken, open_ = [], []
    for t_in, t_out, coin in tr:
        open_ = [o for o in open_ if o > t_in]
        if len(open_) >= 10:
            continue
        open_.append(t_out)
        taken.append((t_in, t_out, coin))
    return taken


def _span(h, t_in, t_out):
    ti = pd.DatetimeIndex(h.time).as_unit("ns").asi8
    a, b = np.searchsorted(ti, t_in, "left"), np.searchsorted(ti, t_out, "left")
    return ti, a, min(b, len(ti) - 1)


def news_worst(taken, grid, Hc) -> np.ndarray:
    gi = grid.asi8
    out = np.zeros(len(grid))
    if "BTCUSDT" not in Hc:
        Hc["BTCUSDT"] = hourly("BTCUSDT")
    hb = Hc["BTCUSDT"]
    bt = pd.DatetimeIndex(hb.time).as_unit("ns").asi8
    for t_in, t_out, coin in taken:
        if coin not in Hc:
            Hc[coin] = hourly(coin)
        h = Hc[coin]
        if h is None:
            continue
        ti, a, b = _span(h, t_in, t_out)
        if b < a:
            continue
        e = float(h.open.iloc[a])
        coin_loss = -0.10 * (h.high.to_numpy()[a:b + 1] / e - 1)          # the short at the hour's high
        ib = np.searchsorted(bt, ti[a:b + 1])
        ok = ib < len(bt)
        eb = float(hb.open.iloc[np.searchsorted(bt, ti[a])])
        btc = np.zeros(b + 1 - a)
        btc[ok] = 0.10 * (hb.low.to_numpy()[ib[ok]] / eb - 1)            # the BTC long at the hour's low
        ga = np.searchsorted(gi, ti[a:b + 1])
        m = ga < len(grid)
        np.add.at(out, ga[m], np.minimum(coin_loss + btc, 0.0)[m])
    return out


def ndx_worst(grid) -> tuple:
    from backtest import ndx_capit as nc
    d, P, L, S = nc.load()
    tr = nc.run(P, L["rsi2_10"], 1, "close", "X2", False)
    dates = pd.to_datetime(P["dates"])
    x = pd.read_parquet(ROOT / "strategy_analysis" / "data" / "histdata" / "NSXUSD.parquet")
    t = pd.to_datetime(x.t, unit="ms")
    m1 = pd.Series(x.c.to_numpy(), index=t)
    hl = pd.Series(x.l.to_numpy(), index=t).resample("h").min().dropna()
    gi = grid.asi8
    out = np.zeros(len(grid))
    worst_trade = 0.0

    def close_ts(day):                                                  # 16:00 New York, as naive UTC
        return pd.Timestamp(f"{day:%Y-%m-%d} 16:00").tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)
    n = 0
    for i, k, g, net, _ in tr:
        t_in, t_out = close_ts(dates[i]), close_ts(dates[k])
        if t_in < grid[0] or t_in > grid[-1]:
            continue
        e = m1.asof(t_in)
        if not np.isfinite(e):
            continue
        seg = hl[(hl.index > t_in) & (hl.index <= t_out)]
        loss = seg.to_numpy() / e - 1
        if not len(loss):
            continue
        n += 1
        worst_trade = min(worst_trade, float(loss.min()))
        ga = np.searchsorted(gi, seg.index.as_unit("ns").asi8)
        m = ga < len(grid)
        np.add.at(out, ga[m], np.minimum(loss, 0.0)[m])
    return out, n, worst_trade


def squeeze_bound() -> tuple:
    from backtest.market_neutral import drop_non_crypto
    from backtest.wide_book import eligibility
    elig = drop_non_crypto(eligibility(60))
    best = (0.0, None, None)
    for c, months in elig.items():
        h = hourly(c)
        if h is None or not len(h):
            continue
        tt = pd.to_datetime(h.time)
        ok = tt.dt.strftime("%Y-%m").isin(months).to_numpy() & (tt >= "2020-01-01").to_numpy()
        if not ok.any():
            continue
        sp = (h.high.to_numpy() / h.open.to_numpy() - 1)[ok]
        j = int(np.nanargmax(sp))
        if sp[j] > best[0]:
            best = (float(sp[j]), c, tt[ok].iloc[j])
    return best


def main():
    px = {}
    for c in blend.BOOK:
        d = blend.load(c)
        if d is not None:
            px[c] = d.set_index(pd.DatetimeIndex(d["time"]).as_unit("ns"))[["high", "low", "close"]]
    grid = pd.date_range(min(p.index[0] for p in px.values()), max(p.index[-1] for p in px.values()), freq="h").as_unit("ns")
    H = {c: p.reindex(grid).ffill() for c, p in px.items()}
    bear = regimes()[1000]
    bn, bv = pd.DatetimeIndex(bear.index).as_unit("ns").asi8, bear.to_numpy(bool)
    rows = D.decompose(rows_for_phase(0, tight=True, time_stop=(100, 2.0), max_units=7))
    XA, _, bear_day = load_all()
    ok = per_fill(fills(XA[XA.in40], k=0.10, skip_bear=bear_day), pickle.loads(CACHE.read_bytes()))
    ok = ok[ok.ok.astype(bool)]
    x = ok.assign(tie=np.random.default_rng(0).random(len(ok))).sort_values(["t", "minute", "tie"])
    y = x[x.groupby("t").cumcount() < 10]
    w = y.groupby("t").after.sum() / 40
    w.index = pd.DatetimeIndex(w.index).as_unit("ns")
    bids = w.reindex(grid).fillna(0.0).to_numpy()
    Hc = {}
    taken = news_taken()
    news = news_worst(taken, grid, Hc)
    ndx, n_ndx, ndx_trade = ndx_worst(grid)
    sq, sq_coin, sq_t = squeeze_bound()
    sq_cost = sq * MAX_SHORT_ONE_COIN
    dT = {off: dc.gen(off, dict(dc.BASE, mean_n=20)) for off in dc.PHASES}
    cT = {off: cc.gen(off, dict(cc.BASE, **mc.CAPIT_BETTER)) for off in cc.PHASES}
    out = [f"backtest/liq_now.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; hourly grid {grid[0]:%Y-%m-%d} .. {grid[-1]:%Y-%m-%d}; "
           f"every open position at its worst price of the hour; liquidation line {LINE_NOW:.2%} left at the 14.5x cap "
           f"({LINE_OLD:.0%} at 11.5x)",
           f"  news: {len(taken)} trades taken (first 10 open); NASDAQ dip: {n_ndx} trades in the window, its worst point inside "
           f"a trade {ndx_trade:+.1%} of the account",
           f"  MN / carry squeeze bound: the largest 1-hour spike of a top-60 coin since 2020 is {sq:+.0%} ({sq_coin}, "
           f"{sq_t:%Y-%m-%d %H:00}); at the most one coin can be shorted ({MAX_SHORT_ONE_COIN:.1%} of the account) "
           f"that is {sq_cost:.1%} of the account", "",
           "  account LEFT in the worst hour (and when)"]
    R = {}
    for sd in (0, 1, 2):
        tr = trend_frac(rows, bn, bv, sd, grid, H).to_numpy()
        doff, coff = dc.PHASES[sd % 3], cc.PHASES[sd % 4]
        dtk = [q for q, _, _ in dc.allocate(dT[doff], sd)]
        ctk = {L: [q for q, _, _ in dc.allocate(cT[coff].assign(units=None), sd, L)] for L in (1.0, 2.0)}
        daily = book_worst(dT[doff], dtk, grid, 0.5 / 8, Hc)
        cap = {L: book_worst(cT[coff], ctk[L], grid, L * 1.0 / 8, Hc) for L in (1.0, 2.0)}
        now = tr + daily + cap[2.0] + news + ndx
        combos = {"OLD FULL (liq_stress: + bids, no news/ndx)": tr + bids + daily + cap[2.0],
                  "RUNNING NOW (no bids, + news + ndx)": now,
                  "running now + crash bids": now + bids,
                  "running now, capit2 at 1x": tr + daily + cap[1.0] + news + ndx,
                  "news alone": news, "NASDAQ dip alone": ndx}
        out.append(f"\n  ordering {sd}")
        for nm, v in combos.items():
            left = 1 + v
            i = int(np.argmin(left))
            R[(sd, nm)] = (left[i], grid[i])
            out.append(f"    {nm:<44}{left[i] * 100:>5.0f}%  {grid[i]:%Y-%m-%d %H:00}   under 50%: {(left < 0.5).sum():>3} h, "
                       f"under the line: {(left < LINE_NOW).sum():>2} h")
        o = np.argsort(now)[:5]
        out.append("    the 5 worst hours, running now: " + ", ".join(
            f"{grid[i]:%Y-%m-%d %H:00} {(1 + now[i]) * 100:.0f}% (trend {tr[i] * 100:+.0f}, daily {daily[i] * 100:+.0f}, "
            f"capit2 {cap[2.0][i] * 100:+.0f}, news {news[i] * 100:+.0f}, ndx {ndx[i] * 100:+.0f})" for i in o))
        worst = R[(sd, "RUNNING NOW (no bids, + news + ndx)")][0]
        out.append(f"    + the squeeze bound on top of the worst hour (a stacked worst case): {(worst - sq_cost) * 100:.0f}% left")
    rn = "RUNNING NOW (no bids, + news + ndx)"
    old = {0: 0.41, 1: 0.29, 2: 0.50}
    l1 = all(R[(sd, rn)][0] > LINE_NOW and R[(sd, rn)][0] >= old[sd] - 0.05 for sd in (0, 1, 2))
    l2 = all(R[(sd, "NASDAQ dip alone")][0] >= 0.85 for sd in (0, 1, 2))
    out += ["", "REGISTERED PREDICTIONS",
            f"  L1 running now above {LINE_NOW:.1%} everywhere and within 5 points of 41 / 29 / 50%: "
            f"{[round(R[(sd, rn)][0] * 100) for sd in (0, 1, 2)]} -> {'RIGHT' if l1 else 'WRONG'}",
            f"  L2 NASDAQ dip alone loses < 15% in its worst hour: {round((1 - R[(0, 'NASDAQ dip alone')][0]) * 100, 1)}% -> "
            f"{'RIGHT' if l2 else 'WRONG'}",
            f"  L3 squeeze bound < 10% of the account: {sq_cost:.1%} -> {'RIGHT' if sq_cost < 0.10 else 'WRONG'}"]
    txt = "\n".join(out)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

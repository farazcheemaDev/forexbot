"""THE DAILY BREAKOUT BOOK: is there a discrepancy between its backtest and its forward test, and if so what is wrong? (2026-11-15)

THE USER (2026-11-15): "check if there is a discrepancy between the daily breakout backtest and the forward test, and if there is,
what are we doing wrong". Live (both final-machine paper accounts, logs copied read-only from the VM): main 10 closed trades, 1 won,
-$35; fresh 8, 0 won, -$35; three trades lost 45-57% (AKE, AIN, JCT). daily_book_live_check.py (11-12) found the losing streak normal
for the book and the SIZE of the losers not: trades under -40% are 0.4% of the backtest's 5,064 trades and 3 of 18 live.

THREE PLACES A DISCREPANCY CAN SIT, each checked here:
  A  THE CODE - does the live bot take the trades the backtest's rule takes on the same days? The backtest rule (daily_combos.gen,
     BASE with mean_n=20: close > Bollinger(30, 1.5) upper band on a coin with >= 60 days of bars, buy at the next open, sell at the
     next open after a close under the 20-day mean, cap 30 days, 12bp, funding) is replayed on Binance's daily bars to now, on the
     backtest's universe rule (top-40 by the PRIOR month's quote volume, listed >= 30 days at the month start), and every live trade
     is matched by coin, entry day, entry price, exit day and exit price. Two universe conventions are scored: the backtest's (the
     month of the SIGNAL bar, daily_combos.gen's ym[i]) and the live bot's (the month of the run = the entry day).
  B  THE DATA - which coins the backtest never saw. daily_combos.panel drops every coin with fewer than 120 daily bars in the whole
     data set (`if len(d) < 120: continue`): a coin listed and delisted inside four months, or listed in the last four months
     before the data ends (2026-09), is never traded, although it was in the top-40. The rule is run on those coins with the
     same code (gen through a patched panel; parity with the cached panel checked first).
  C  THE DRAW - is the live result something the backtest's own trades produce, by coin age at entry and in stretches of
     consecutive trades?

REGISTERED BEFORE THE RUN (2026-11-15)
  Q1 (85%) The live book IS the backtest's rule: every live entry is a replay signal (same coin and entry day) and its exit is on the
     replay's exit day; entry and exit prices within 1% of the replay's daily open (the bot fills 0-4 minutes after it).
  Q2 (60%) At least one live trade is not a backtest trade only because of the month boundary (the live bot reads the NEW month's
     top-40 for the last close of the old month; the backtest the old month's) - AIN, bought 2026-11-01, is the candidate.
  Q3 (70%) The 120-bar panel rule drops >= 10 coins that were in the top-40, and the rule's trades in them lose more per trade
     than in the kept coins.
  Q4 (65%) In the backtest, trades in coins listed under 180 days at entry lose 40%+ at least 3x as often as trades in older coins.
  Q5 (70%) AKE, AIN and JCT were each listed under 180 days before the live entry.

RESULT (2026-11-15 12:50 UTC, logs/daily_live_vs_backtest.txt): NO CODE DISCREPANCY - the live losses are the rule's own trades; the
  RUN is outside the backtest's history. Q1 right on trades (16 of 18 live trades are replay trades on the same entry AND exit day;
  replay -22.7% vs live -22.1% a trade on main), two fills >1% off the open (JCT +2.3%, bought 1.5 min into a pump; fresh's BTW +1.4%,
  the account started at 01:15). IOST (taken) and RAYSOL 10-09 (missed, replay -12%) are the pre-10-22 24h-volume universe, already
  fixed. Q2 RIGHT: AIN (-57%) is a trade only under the live month rule - but D shows that rule is no worse over history (holdout
  +0.6..+0.9 points a trade better at all 3 boundaries): a convention, not a fault. Q3 WRONG: the 120-bar panel rule drops 12 coins
  (0.8% of top-40 coin-months, mostly 2026-08 stock tokens), 7 trades, -3.7% a trade, none under -40%. Q4 WRONG: under -40% 0.3%
  (listed < 180 d) vs 0.5%. Q5 WRONG: AKE 392, AIN 478, JCT 363 days listed - not new coins; older small caps that entered the top-40
  on pump volume. THE DRAW: 10 consecutive backtest trades averaging <= -22.1% happen in 0.59% of runs (none since 2025; worst since
  2025 -20.4%); 3 trades under -40% in 10: never. D (post hoc): a 20-35% disaster stop removes the -40% losers and lowers the
  per-trade mean on BOTH halves at all 3 boundaries (pump trades wick through it and recover) - as the 2xATR stop did
  (daily_combos.py). Nothing to fix in the code; what is wrong is the book's evidence (its holdout rests on 5 pump trades, doc 02).

    python -m backtest.daily_live_vs_backtest <folder with live_daily.txt and month_pool.json>
"""
from __future__ import annotations

import json
import pickle
import re
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "daily_live_vs_backtest.txt"
DATA = ROOT / "strategy_analysis" / "data" / "daily_live"
FAPI = "https://fapi.binance.com"
FEE, BB_N, BB_K, MEAN_N, CAP, MIN_I, TOP = 0.0012, 30, 1.5, 20, 30, 60, 40
DAY_MS = 86_400_000


def get(u):
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    for k in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            if k == 3:
                print("  fetch failed:", u[:90].encode("ascii", "replace").decode(), type(e).__name__)
                return None
            time.sleep(2 + 3 * k)


# ------------------------------------------------------------------ live trades
def live_trades(path: Path) -> pd.DataFrame:
    """Pairs of DAILY BUY / DAILY CLOSE lines per account from the copied combo_paper.log extracts."""
    acct, rows, open_ = None, [], {}
    buy = re.compile(r"^(\S+ \S+) \| DAILY BUY (\S+) at (\S+)")
    cls = re.compile(r"^(\S+ \S+) \| DAILY CLOSE (\S+) at (\S+) \((\w+)\): ([-+0-9.]+)% net")
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            acct = "main" if line.strip().endswith("combo_bot_dry_final") else "fresh"
            continue
        m = buy.match(line)
        if m:
            open_[(acct, m[2])] = (pd.Timestamp(m[1]), float(m[3]))
            continue
        m = cls.match(line)
        if m and (acct, m[2]) in open_:
            tb, pb = open_.pop((acct, m[2]))
            rows.append(dict(acct=acct, coin=m[2], t_buy=tb, px_buy=pb, t_sell=pd.Timestamp(m[1]), px_sell=float(m[3]),
                             why=m[4], net=float(m[5]) / 100))
    for (a, s), (tb, pb) in open_.items():
        rows.append(dict(acct=a, coin=s, t_buy=tb, px_buy=pb, t_sell=pd.NaT, px_sell=np.nan, why="open", net=np.nan))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ Binance data
def klines_all(refresh=False):
    f = DATA / "klines_1d.pkl"
    if f.exists() and not refresh and time.time() - f.stat().st_mtime < 6 * 3600:
        return pickle.loads(f.read_bytes())
    info = get(f"{FAPI}/fapi/v1/exchangeInfo")
    syms = {s["symbol"]: int(s.get("onboardDate", 0)) for s in info["symbols"]
            if s.get("quoteAsset") == "USDT" and s.get("contractType") == "PERPETUAL" and s.get("status") == "TRADING"
            and s["symbol"].isascii()}                                 # a few symbols carry non-ASCII names; never in the live pool
    K = {}
    for n, s in enumerate(sorted(syms)):
        k = get(f"{FAPI}/fapi/v1/klines?symbol={s}&interval=1d&limit=400")
        if k and len(k) > 2:
            d = pd.DataFrame([[int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[7])] for x in k],
                             columns=["t", "o", "h", "l", "c", "q"])
            K[s] = d.iloc[:-1].reset_index(drop=True)            # the forming bar is dropped (as mn_paper.daily does)
        time.sleep(0.06)
        if n % 100 == 0:
            print(f"  klines {n}/{len(syms)}", flush=True)
    out = dict(K=K, onboard=syms, at=int(time.time() * 1000))
    DATA.mkdir(parents=True, exist_ok=True)
    f.write_bytes(pickle.dumps(out))
    return out


def month_top(K: dict, month: str, n=TOP) -> list:
    """The backtest's rule (wide_book.eligibility): listed >= 30 days at the month start, ranked by the prior month's volume."""
    ms = pd.Timestamp(month + "-01")
    prev = (ms - pd.Timedelta(days=1)).strftime("%Y-%m")
    vol = {}
    for s, d in K.items():
        first = pd.to_datetime(d.t.iloc[0], unit="ms")
        if (ms - first).days < 30:
            continue
        m = d[pd.to_datetime(d.t, unit="ms").dt.strftime("%Y-%m") == prev]
        if len(m):
            vol[s] = float(m.q.sum())
    return sorted(vol, key=lambda s: -vol[s])[:n]


def funding(sym, a_ms, b_ms):
    """Sum of funding rates settled in (a, b] (half-open, bounded at both ends - CLAUDE.md mistake #15)."""
    r = get(f"{FAPI}/fapi/v1/fundingRate?symbol={sym}&startTime={a_ms + 1}&endTime={b_ms}&limit=1000") or []
    return float(sum(float(x["fundingRate"]) for x in r))


def replay(K, uni: dict, start: pd.Timestamp, conv: str, fund=True) -> pd.DataFrame:
    """daily_combos.gen's loop on fresh bars, for entries on or after `start`. uni = {month: set(top-40)};
    conv 'bt' = membership of the signal bar's month (gen's ym[i]), 'live' = of the entry day's month (the bot's)."""
    rows = []
    coins = set().union(*uni.values())
    for s in sorted(coins):
        d = K.get(s)
        if d is None or len(d) < BB_N + 5:
            continue
        o, c, t = d.o.to_numpy(), d.c.to_numpy(), d.t.to_numpy()
        S = pd.Series(c)
        m, sd = S.rolling(BB_N).mean().to_numpy(), S.rolling(BB_N).std(ddof=0).to_numpy()
        mx = S.rolling(MEAN_N).mean().to_numpy()
        ent = np.nan_to_num(c > m + BB_K * sd).astype(bool)
        days_listed = (t - t[0]) // DAY_MS                     # 400 bars fetched: an old coin's index is >= 60 anyway
        free = 0
        for i in np.flatnonzero(ent):
            if i + 1 >= len(c) or i < free or days_listed[i] < MIN_I:
                continue
            t_in = pd.to_datetime(t[i + 1], unit="ms")
            if t_in < start:
                continue
            mon = pd.to_datetime(t[i if conv == "bt" else i + 1], unit="ms").strftime("%Y-%m")
            if s not in uni.get(mon, set()):
                continue
            e, jo, why = o[i + 1], None, "open"
            for j in range(i + 1, min(i + 1 + CAP, len(c))):
                if c[j] < mx[j]:
                    jo, why = j + 1, "mean20"
                    break
            if jo is not None and jo >= len(c):              # the exit open has not printed in the fetched (closed) bars
                jo, why = None, "exit_next_open"
            if jo is None:
                x, t_out, free = c[-1], pd.NaT, len(c)
            else:
                x, t_out, free = o[jo], pd.to_datetime(t[jo], unit="ms"), jo
            fr = funding(s, int(t[i + 1]), int(t[jo]) if jo is not None else int(t[-1]) + DAY_MS) if fund else 0.0
            rows.append(dict(coin=s, t_in=t_in, px_in=e, t_out=t_out, px_out=x, why=why, fund=fr,
                             net=x / e - 1 - FEE - fr, age_d=int(days_listed[i + 1])))
    return pd.DataFrame(rows)


def part_a(folder: Path, L: list):
    live = live_trades(folder / "live_daily.txt")
    D = klines_all()
    K, onboard = D["K"], D["onboard"]
    oct_ = month_top(K, "2026-10")
    nov = month_top(K, "2026-11")
    pool = json.loads((folder / "month_pool.json").read_text())["2026-11"]
    live_nov = [s for s in pool if s in K][:TOP]
    uni = {"2026-10": set(oct_), "2026-11": set(nov)}
    L += ["A. THE CODE - the backtest's rule replayed on Binance's daily bars, every live trade matched", "",
          f"  universe check: November top-40 by this file's rule vs the live bot's saved pool: {len(set(nov) & set(live_nov))} of 40 "
          f"shared (only here: {' '.join(sorted(set(nov) - set(live_nov))) or '-'}; only live: {' '.join(sorted(set(live_nov) - set(nov))) or '-'})"]
    out = {}
    for acct, start in (("main", pd.Timestamp("2026-10-09")), ("fresh", pd.Timestamp("2026-10-17"))):
        for conv in ("bt", "live"):
            out[(acct, conv)] = replay(K, uni, start, conv)
    for acct in ("main", "fresh"):
        lv = live[live.acct == acct].copy()
        rb, rl = out[(acct, "bt")], out[(acct, "live")]
        L += ["", f"  {acct.upper()}: {len(lv)} live trades | replay, backtest month rule: {len(rb)} trades | live month rule: {len(rl)}",
              f"    {'coin':<14}{'live in':>12}{'replay in':>12}{'in px bp':>9}{'live out':>11}{'replay out':>12}{'out px bp':>10}"
              f"{'live net':>10}{'replay net':>11}{'listed d':>9}  in backtest-month universe?"]
        for _, r in lv.iterrows():
            day = r.t_buy.normalize()
            cand = rl[(rl.coin == r.coin) & (rl.t_in == day)]
            inbt = not rb[(rb.coin == r.coin) & (rb.t_in == day)].empty
            if cand.empty:
                L.append(f"    {r.coin:<14}{r.t_buy:%m-%d %H:%M}  NOT A REPLAY SIGNAL")
                continue
            q = cand.iloc[0]
            bp_in = (r.px_buy / q.px_in - 1) * 1e4
            bp_out = (r.px_sell / q.px_out - 1) * 1e4 if pd.notna(r.px_sell) else np.nan
            L.append(f"    {r.coin:<14}{r.t_buy:%m-%d}{q.t_in:%m-%d}{bp_in:>+12.0f}"
                     f"{(r.t_sell.strftime('%m-%d') if pd.notna(r.t_sell) else 'open'):>11}"
                     f"{(q.t_out.strftime('%m-%d') if pd.notna(q.t_out) else 'open'):>12}{bp_out:>+10.0f}"
                     f"{r.net * 100:>+9.1f}%{q.net * 100:>+10.1f}%{q.age_d:>9}  {'yes' if inbt else 'NO - only by the live month rule'}")
        keyl = set(zip(lv.coin, lv.t_buy.dt.normalize()))
        extra = rl[[(a, b) not in keyl for a, b in zip(rl.coin, rl.t_in)]]
        L.append("    replay trades the live book did not take: " + (", ".join(f"{a} {b:%m-%d} ({n * 100:+.1f}%)" for a, b, n in
                                                                       zip(extra.coin, extra.t_in, extra.net)) or "none"))
        L.append(f"    replay mean per trade: backtest month rule {rb.net.mean() * 100:+.1f}% ({len(rb)}), live rule {rl.net.mean() * 100:+.1f}% "
                 f"({len(rl)}); live {lv.net.mean() * 100:+.1f}% ({lv.net.notna().sum()})")
    ages = {s: (pd.Timestamp(r.t_buy) - pd.to_datetime(onboard.get(s, 0), unit="ms")).days
            for s, r in live[live.acct == "main"].set_index("coin").iterrows()}
    L.append("")
    L.append("  live coins, days listed on Binance futures at the live entry (exchangeInfo onboardDate): " +
             "  ".join(f"{s.replace('USDT', '')} {a}" for s, a in ages.items()))
    L.append(f"  AIN in the October top-40 (backtest month rule for an Oct-31 signal): {'yes' if 'AINUSDT' in oct_ else 'NO'}; "
             f"in November's: {'yes' if 'AINUSDT' in nov else 'NO'}")
    return live, out, ages, uni


# ------------------------------------------------------------------ part B: coins the backtest dropped
def part_b(L: list):
    from backtest import daily_combos as dc
    from backtest import pair_lab as pl
    from backtest.capitulation_wide import funding_cum, hourly
    from backtest.rsi_factors import prep
    from backtest.tv_indicators import bars
    cfg = dict(dc.BASE, mean_n=20)
    P0 = dc.panel(0)
    el = pl.universe()
    want = [s for s, mm in el.items() if mm and s not in P0]
    extra, short_n = {}, {}
    for s in want:
        h = hourly(s)
        if h is None:
            continue
        d = bars(h, "1d", 0)
        short_n[s] = len(d)
        if len(d) < MIN_I + 5:
            continue
        P = prep(d, np.full(len(d), np.nan))
        P["t"] = d.time.to_numpy("datetime64[ns]")
        P["fc"] = funding_cum(s, d.time.to_numpy(), h)
        P["ym"] = d.time.dt.strftime("%Y-%m").to_numpy()
        P["el"] = el[s]
        extra[s] = P
    full = dict(P0)
    full.update(extra)
    old_panel, old_x = dc.panel, dict(dc._X)
    try:
        dc.panel = lambda off: full if off == 99 else old_panel(off)
        dc._X[99] = {s: {} for s in full}
        T_all = dc.gen(99, cfg)
    finally:
        dc.panel = old_panel
        dc._X.clear(); dc._X.update(old_x)
    T0 = dc.gen(0, cfg)
    a = T0.sort_values(["coin", "t_in"]).reset_index(drop=True)
    b = T_all[T_all.coin.isin(P0)].sort_values(["coin", "t_in"]).reset_index(drop=True)
    parity = len(a) == len(b) and np.allclose(a.net.to_numpy(), b.net.to_numpy()) and (a.t_in.to_numpy() == b.t_in.to_numpy()).all()
    em = sum(len(el[s]) for s in want)
    em_all = sum(len(m) for m in el.values())
    Td = T_all[~T_all.coin.isin(P0)]
    L += ["", "B. THE DATA - coins in the top-40 that daily_combos.panel drops (fewer than 120 daily bars in the whole data set)", "",
          f"  parity: the rule through the patched panel reproduces gen(0) on the kept coins: {'YES' if parity else 'NO - result below not trusted'}"
          f" ({len(a)} trades)",
          f"  coins in the PIT top-40 at least one month but not in the panel: {len(want)} ({em} of {em_all} top-40 coin-months, "
          f"{em / em_all * 100:.1f}%); with >= {MIN_I + 5} daily bars (can trade at all): {len(extra)}",
          f"  their trades by the same rule: {len(Td)}; mean {Td.net.mean() * 100:+.2f}% a trade, won {(Td.net > 0).mean() * 100:.0f}%, "
          f"under -40%: {(Td.net < -0.4).mean() * 100:.1f}%  (kept coins: mean {T0.net.mean() * 100:+.2f}%, won {(T0.net > 0).mean() * 100:.0f}%, "
          f"under -40% {(T0.net < -0.4).mean() * 100:.1f}%)" if len(Td) else "  their trades by the same rule: none"]
    if len(Td):
        L.append("    " + "  ".join(f"{r.coin.replace('USDT', '')} {pd.Timestamp(r.t_in):%Y-%m-%d} {r.net * 100:+.0f}%" for r in Td.itertuples()))
    return T0, P0


# ------------------------------------------------------------------ part C: the draw
def part_c(T0, P0, live, ages, L: list):
    first = {s: pd.Timestamp(P["t"][0]) for s, P in P0.items()}
    T = T0.copy()
    T["t"] = pd.to_datetime(T.t_in)
    T["age"] = [(t - first[s]).days for s, t in zip(T.coin, T.t)]
    bins = [(60, 120), (120, 180), (180, 365), (365, 99999)]
    L += ["", "C. THE DRAW - the backtest's own trades (boundary 0h, every signal), by days since the coin's first bar at entry", "",
          f"  {'age at entry':<16}{'trades':>7}{'mean':>9}{'median':>9}{'won':>6}{'< -40%':>8}{'< -25%':>8}   2025-26: trades, mean, < -40%"]
    for lo, hi in bins:
        g = T[(T.age >= lo) & (T.age < hi)]
        r = g[g.t >= "2025-01-01"]
        if not len(g):
            continue
        L.append(f"  {f'{lo}-{hi} d' if hi < 99999 else f'{lo}+ d':<16}{len(g):>7}{g.net.mean() * 100:>+8.1f}%{g.net.median() * 100:>+8.1f}%"
                 f"{(g.net > 0).mean() * 100:>5.0f}%{(g.net < -0.4).mean() * 100:>7.1f}%{(g.net < -0.25).mean() * 100:>7.1f}%   "
                 f"{len(r)}, {r.net.mean() * 100:+.1f}%, {(r.net < -0.4).mean() * 100:.1f}%" if len(r) else "")
    young = T.age < 180
    L.append(f"  -> under -40%: listed < 180 d {(T[young].net < -0.4).mean() * 100:.1f}% vs older {(T[~young].net < -0.4).mean() * 100:.1f}%")
    lv = live[live.acct == "main"].dropna(subset=["net"])
    n, mu, big = len(lv), lv.net.mean(), int((lv.net < -0.4).sum())
    s = T.sort_values("t").net.to_numpy()
    roll = np.convolve(s, np.ones(n) / n, mode="valid")
    bigr = np.convolve((s < -0.4).astype(float), np.ones(n), mode="valid")
    s2 = T[T.t >= "2025-01-01"].sort_values("t").net.to_numpy()
    roll2 = np.convolve(s2, np.ones(n) / n, mode="valid")
    bigr2 = np.convolve((s2 < -0.4).astype(float), np.ones(n), mode="valid")
    L += ["", f"  main's {n} live trades: mean {mu * 100:+.1f}% a trade, {big} under -40%. Of the backtest's runs of {n} consecutive trades:",
          f"    mean <= {mu * 100:+.1f}%: {(roll <= mu).mean() * 100:.2f}% of runs (since 2025: {(roll2 <= mu).mean() * 100:.2f}%); "
          f">= {big} trades under -40%: {(bigr >= big).mean() * 100:.2f}% (since 2025: {(bigr2 >= big).mean() * 100:.2f}%)",
          f"    worst run's mean: {roll.min() * 100:+.1f}% (since 2025 {roll2.min() * 100:+.1f}%)"]
    return T


def part_d(L: list):
    """Two things that could be 'what we are doing wrong', on the backtest's own trades (all 3 day boundaries, per trade,
    every signal - a first look, not the slot-allocated account): (1) the live bot's month rule (membership of the ENTRY
    day's month) instead of the backtest's (the signal bar's); (2) a fixed % disaster stop on the daily low, filled at
    min(open, level) - it would have cut AKE / AIN / JCT. Added after parts A-C were read (post hoc, said so in the log)."""
    from backtest import daily_combos as dc
    cfg = dict(dc.BASE, mean_n=20)
    ho = pd.Timestamp(dc.HOLDOUT)
    L += ["", f"D. POST HOC, the backtest's own trades per trade (tune before {ho:%Y-%m-%d} / holdout after / 2025-26), each day boundary", ""]
    old = dc.panel
    try:
        for off in dc.PHASES:
            P0 = old(off)
            cells = [("base: backtest month rule", P0, cfg),
                     ("live month rule (entry day's month)",
                      {s: dict(P, ym=np.concatenate([P["ym"][1:], P["ym"][-1:]])) for s, P in P0.items()}, cfg)]
            for pct in (0.20, 0.25, 0.30, 0.35):
                cells.append((f"+ {pct:.0%} disaster stop", {s: dict(P, atr=pct * np.r_[P["o"][1:], np.nan]) for s, P in P0.items()},
                              dict(cfg, stop=1.0)))                 # gen's stop = e - stop x atr[i]; atr[i] := pct x open[i+1]
            for nm, PN, cf in cells:
                dc.panel = lambda o, PN=PN: PN
                dc._X[90 + off] = {s: {} for s in PN}
                T = dc.gen(90 + off, cf)
                t = pd.to_datetime(T.t_in)
                a, b, c = T.net[t < ho], T.net[t >= ho], T.net[t >= "2025-01-01"]
                L.append(f"  {off:>2}h {nm:<38} n {len(T):>5} | tune {a.mean() * 100:+6.2f}%  holdout {b.mean() * 100:+6.2f}%  "
                         f"2025-26 {c.mean() * 100:+6.2f}% | under -40% {(T.net < -0.4).mean() * 100:.2f}%")
            dc.panel = old
    finally:
        dc.panel = old
        for k in [k for k in dc._X if k >= 90]:
            dc._X.pop(k)


def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "logs"
    L = [f"backtest/daily_live_vs_backtest.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; daily breakout book (Bollinger(30, 1.5), "
         "out under the 20-day mean), live paper vs backtest", ""]
    live, out, ages, uni = part_a(folder, L)
    print("\n".join(L), flush=True)
    T0, P0 = part_b(L)
    T = part_c(T0, P0, live, ages, L)
    part_d(L)
    txt = "\n".join(L)
    print(txt)
    LOG.write_text(txt, encoding="utf-8")
    pickle.dump(dict(live=live, replay=out, uni=uni), open(DATA / "replay.pkl", "wb"))


if __name__ == "__main__":
    main()

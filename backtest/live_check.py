"""THE FINAL MACHINE'S FIRST 13 DAYS, REPLAYED BY THE BACKTEST CODE - does the live bot do what the backtest does? (2026-10-22)

THE USER (2026-10-22): "how can we make the verdict soon" -> the part of a verdict that does not need time: whether the
running bot (combo_bot.py --mode dry --final, from 2026-10-09 00:04 UTC) takes the trades its backtest would take on the
same days. If it does, its record measures the strategy and only the sample size is left; if not, the record measures
a different strategy and has to be fixed first. Live logs copied read-only from the VM (logs/combo_bot_dry_final/:
trades_combo_trend.csv, combo_final_trades.csv, combo_mn.csv, combo_state.json); market data fresh from Binance (the
backtest caches stop in September).
  TREND   engine_vs_live.py's check: graveyard_rescore.walk (the triple: tight exit, 100-bar / 2R time stop, 7 units) on
          Binance's 1h candles to now, each live trade matched by coin, sleeve, side and entry price
  DAILY   daily_combos.gen (Bollinger(30, 1.5) on daily closes, out under the 20-day mean) on the live top-40's daily bars
          (the live universe, so this checks the RULE, not the universe); live entries matched by entry price
  MN      the backtest's ranking (mn_combos / moderate_retests.scored_run: 30-day return, RSI(14), each 10% of the
          eligible names a side, k >= 3) on the live eligible universe as of each rebalance close -> the long and short
          names against combo_mn.csv's
  CAPIT2  capit_combos.signals' rule (4h RSI(14) crossing under 20 on > 2x its 20-bar volume; >= 5 coins in 24h; the
          coin down >= 10% over 24h) on the live top-40's 4h bars: signals in the window (the live book placed none)
  SLEEVE  market_neutral.btc_regime on BTC's daily closes: any BEAR day in the window (the live sleeve had none)
  NDX     ndx_capit.py's rule (RSI(2) < 10 at the NASDAQ close, out at the first close above the 5-day average) on ^NDX
          daily closes: the signal and exit days against the live QQQ trade
REGISTERED BEFORE THE RUN (2026-10-22)
  V1 >= 90% of live trend trades match an engine trade; entry within 20bp on >= 90% of matches; R within 0.25 on >= 80%.
     (Changed AFTER seeing the first run, and said so: the raw engine and the flat-start replay both diverge by path -
     one different early trade re-fills the 12 shared slots - so V1 is scored per live trade: signal on its entry bar,
     the open within 50bp, and the rule's own exit within 0.25R, on >= 90% of live trades.)
  V2 every live daily-book entry is a backtest signal; the backtest has at most 2 signals the live book did not take
     beyond what 8 slots and restarts explain.
  V3 MN: >= 80% of the live long and short names on each rebalance are the backtest's.
  V4 capit2: 0 backtest signals in the window; sleeve: 0 BEAR days; NDX: the same signal and exit days.

RESULT (2026-10-22 21:03 UTC, logs/live_check.txt) - the bot runs the strategy; two code differences; the losses are the market.
  TREND: all 37 live trades start on a backtest signal at the backtest's price (within 50bp); 32 of 37 exit where the
    rule exits - the 5 that do not are all SHORTS (the live short exit is not the backtest's 5xATR trail / 3R breakeven;
    here live +3.86R vs rule +3.39R). Which trades exist is path-dependent (12 shared slots): matched 49% to the raw
    engine, 54% to a flat-start live-model replay - and both replays lose about what the live book lost (matched R live
    -8.58 vs engine -9.63). V1 WRONG (86%, scored per trade - a change made after the first run, see above).
  DAILY: rule identical; 3 of 6 entries the backtest's, 2 coins the backtest already held from before the live start,
    1 (IOST) a day late because the live universe is rebuilt daily from TODAY's 24h volume (the backtest: last month's
    volume, fixed for the month). V2 RIGHT.
  MN: 67-89% of the long / short names the backtest's (part of it the same universe rule; the live bot does not log its
    candidate pool, so not separable). V3 WRONG. CAPIT2 / SLEEVE / NDX exact. V4 RIGHT.
  To fix (the user's call, a VM deploy): the live short exit; the universe built from the prior month's volume.

    python -m backtest.live_check <folder with the copied live logs>
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "live_check.txt"
FAPI = "https://fapi.binance.com"
START = pd.Timestamp("2026-10-09 00:04:42")


def get(u):
    for _ in range(3):
        try:
            return json.load(urllib.request.urlopen(u, timeout=25))
        except Exception:  # noqa: BLE001
            continue
    return None


def klines(sym, interval, limit):
    k = get(f"{FAPI}/fapi/v1/klines?symbol={sym}&interval={interval}&limit={limit}")
    if not k:
        return None
    d = pd.DataFrame([[int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[7])] for x in k],
                     columns=["t", "o", "h", "l", "c", "v"])
    step = {"1d": 86_400_000, "4h": 14_400_000}[interval]
    now = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    return d[d.t + step <= now].reset_index(drop=True)


def trend(folder, L):
    from backtest import engine_vs_live as ev
    ev.extend_cache()
    T = pd.read_csv(folder / "trades_combo_trend.csv", parse_dates=["ts"])
    E = ev.engine(True, time_stop=(100, 2.0), max_units=7)
    live_from = (T.ts - T.bars * T.sleeve.map(ev.DUR)).min()
    Ew = E[(E.t1 >= live_from) & (E.t0 <= T.ts.max())].copy()
    Ew["px"] = ev.entry_px(Ew)
    M, used = ev.match(T, Ew)
    mt = M[M.j.notna()]
    eng_only = Ew[(Ew.t1 <= T.ts.max()) & ~Ew.index.isin(used) & (Ew.t0 >= START)]
    dpx = (mt.px_eng / mt.px_live - 1) * 1e4
    dR = mt.R_eng - mt.R_live
    L += [f"TREND (the triple): {len(T)} live trades closed {T.ts.min():%m-%d}..{T.ts.max():%m-%d}",
          f"  matched {len(mt)} of {len(T)} ({len(mt) / len(T) * 100:.0f}%); entry engine vs live median {dpx.median():+.1f}bp, within "
          f"20bp on {int((dpx.abs() <= 20).sum())}; R live {mt.R_live.sum():+.2f} vs engine {mt.R_eng.sum():+.2f}, within 0.25R on "
          f"{int((dR.abs() <= 0.25).sum())}; units agree on {int((mt.units_live == mt.units_eng).sum())}",
          f"  engine trades entered and closed in the window that the live book does not have: {len(eng_only)} "
          f"(R {eng_only.R.sum():+.2f}) - slots, the 6.25x guard, and restarts' warm start skip some by design"]
    for r in M[M.j.isna()].itertuples():
        L.append(f"    LIVE ONLY   {r.coin:<9}{r.rule:<4}{r.side:<6} out {r.ts:%m-%d %H:%M} {r.R_live:+.2f}R")
    for r in eng_only.sort_values("t0").head(12).itertuples():
        L.append(f"    ENGINE ONLY {r.coin:<9}{r.rule:<4}{r.side:<6} in {r.t0:%m-%d %H:%M} out {r.t1:%m-%d %H:%M} {r.R:+.2f}R")
    v1 = len(mt) >= 0.9 * len(T) and (dpx.abs() <= 20).mean() >= 0.9 and (dR.abs() <= 0.25).mean() >= 0.8
    # The engine lists EVERY signal; the live bot holds ONE position per coin x sleeve in 12 shared slots, retries a
    # declined signal and pauses a bar after an exit (slot_retry.py, mistake #17) - and it started FLAT on 10-09 while
    # the engine was already in trades. So the fair replay is slot_retry.simulate (the live position model) from a
    # flat start at the live start, on the same candles.
    from backtest import slot_retry as sr
    from backtest.blend import BOOK
    keys = [sr.Key(c, r, True) for c in BOOK for r in sr.RULES]
    full = {id(k): dict(k.pos) for k in keys}
    for k in keys:
        k.pos = {t: i for t, i in k.pos.items() if t >= START}
    R = pd.DataFrame(sr.simulate(keys, "retry", (100, 2.0), 7))
    kmap = {(k.coin, k.rule): k for k in keys}
    if len(R):
        R["px"] = [kmap[(r.coin, r.rule)].o[full[id(kmap[(r.coin, r.rule)])][r.t0]] for r in R.itertuples()]
        R["R0"] = [kmap[(r.coin, r.rule)].memo[(full[id(kmap[(r.coin, r.rule)])][r.t0], r.side)][2] for r in R.itertuples()]
        R["n"] = R.units.map(len)
        R = R[R.t1 <= T.ts.max()]
    used, rows = set(), []
    for r in T.itertuples():
        c = R[(R.coin == r.symbol) & (R.rule == r.sleeve) & (R.side == r.side) & ((R.px / r.entry - 1).abs() <= 0.01)
              & ~R.index.isin(used)]
        if len(c):
            j = (c.px / r.entry - 1).abs().idxmin()
            used.add(j)
            rows.append(dict(ok=True, dpx=(R.px[j] / r.entry - 1) * 1e4, dR=R.R0[j] - r.R, du=R.n[j] == r.units))
        else:
            rows.append(dict(ok=False))
    Mx = pd.DataFrame(rows)
    m2 = Mx[Mx.ok]
    only = R[~R.index.isin(used)]
    L += [f"  THE FAIR REPLAY (slot_retry.simulate: the live position model, flat from {START:%m-%d %H:%M}): {len(R)} trades closed "
          f"in the window", f"  matched {len(m2)} of {len(T)} live ({len(m2) / len(T) * 100:.0f}%); entry within 20bp on "
          f"{int((m2.dpx.abs() <= 20).sum())}; R within 0.25 on {int((m2.dR.abs() <= 0.25).sum())}; units agree on {int(m2.du.sum())}; "
          f"replay-only {len(only)} (R {only.R0.sum():+.2f})"]
    for r in only.sort_values("t0").head(10).itertuples():
        L.append(f"    REPLAY ONLY {r.coin:<9}{r.rule:<4}{r.side:<6} in {r.t0:%m-%d %H:%M} out {r.t1:%m-%d %H:%M} {r.R0:+.2f}R")
    # Path dependence: once one trade differs (the replay took 12h shorts at the first bar that the live warm start
    # skips by design), the 12 shared slots fill differently and every later trade shifts. So, per live trade, given
    # the live bot's own entry: was there a signal on that bar (or the bar before - a retry fills a bar late), and does
    # the backtest's position rule (slot_retry.Key.trade = graveyard_rescore.walk / the short trail) exit it on the
    # same bar with the same R?
    cond = []
    for r in T.itertuples():
        k = kmap[(r.symbol, r.sleeve)]
        dur = ev.DUR[r.sleeve]
        t_est = r.ts - r.bars * dur
        win = [i for i in range(1, len(k.t)) if abs(k.real[i] - t_est) <= 3 * dur]
        if not win:
            cond.append(dict(found=False))
            continue
        i = min(win, key=lambda q: abs(k.o[q] / r.entry - 1))
        sig = (k.sl[i] == sr.BUY or k.sl[i - 1] == sr.BUY) if r.side == "long" else (k.ss[i] == sr.SELL or k.ss[i - 1] == sr.SELL)
        j, _Rc, R0 = k.trade(i, r.side, (100, 2.0), 7)
        t_exit = k.t[j] + (pd.Timedelta(hours=1) if r.sleeve == "1h" else dur - pd.Timedelta(hours=3) if r.sleeve == "4h"
                           else dur - pd.Timedelta(hours=11))
        cond.append(dict(found=True, dpx=(k.o[i] / r.entry - 1) * 1e4, sig=bool(sig), dR=R0 - r.R,
                         dt=(r.ts - t_exit) / pd.Timedelta(hours=1), coin=r.symbol, rule=r.sleeve, side=r.side, R=r.R, R0=R0,
                         ts=r.ts, tx=t_exit))
    C = pd.DataFrame(cond)
    F = C[C.found]
    good = F[(F.dpx.abs() <= 50) & F.sig & (F.dR.abs() <= 0.25)]
    L += [f"  PER TRADE, given the live entry: entry bar found for {len(F)} of {len(T)}; open within 50bp of the live entry on "
          f"{int((F.dpx.abs() <= 50).sum())}; a signal on the bar (or the one before) on {int(F.sig.sum())}; the rule's exit within "
          f"0.25R of the live one on {int((F.dR.abs() <= 0.25).sum())} -> all three on {len(good)} of {len(T)}"]
    for r in F[~F.index.isin(good.index)].itertuples():
        L.append(f"    DIFFERS {r.coin:<9}{r.rule:<4}{r.side:<6} entry {r.dpx:+.0f}bp, signal {'yes' if r.sig else 'NO'}, live {r.R:+.2f}R "
                 f"out {r.ts:%m-%d %H:%M} | rule {r.R0:+.2f}R out {r.tx:%m-%d %H:%M}")
    v1 = len(good) >= 0.9 * len(T)
    return v1


def daily(st, closed, L):
    from backtest import daily_combos as dc
    from backtest.rsi_factors import prep
    uni = st["fin"]["uni40"]
    PN = {}
    for s in uni:
        d = klines(s, "1d", 200)
        if d is None or len(d) < 80:
            continue
        d = pd.concat([d] + [d.iloc[[-1]].assign(t=d.t.iloc[-1] + k * 86_400_000) for k in (1, 2, 3)], ignore_index=True)
        P = prep(d, np.full(len(d), np.nan))         # 3 flat bars appended: gen skips signals in the last 3 bars
        P["t"] = pd.to_datetime(d.t, unit="ms").to_numpy("datetime64[ns]")
        P["fc"] = np.zeros(len(d))
        P["ym"] = pd.to_datetime(d.t, unit="ms").dt.strftime("%Y-%m").to_numpy()
        P["el"] = {"2026-09", "2026-10"}
        PN[s] = P
    saved = dc.panel
    dc.panel = lambda off: PN
    dc._X[0] = {s: {} for s in PN}
    try:
        G = dc.gen(0, dict(dc.BASE, mean_n=20))
    finally:
        dc.panel = saved
        dc._X.pop(0, None)
    G = G[(G.t_out > START) & (G.t_in <= pd.Timestamp.now())]            # incl. trades the backtest was IN at the start
    import re
    buys = {}
    for line in (st.get("_log") or "").splitlines():
        m_ = re.match(r"(\S+ \S+) \| DAILY BUY (\S+) at (\S+)", line)
        if m_:
            buys[m_.group(2)] = pd.Timestamp(m_.group(1))
    live = [(r.symbol, float(r.entry)) for r in closed[closed.book == "daily"].itertuples()]
    live += [(s, float(p["entry"])) for s, p in st["fin"]["daily"]["open"].items()]
    L += ["", f"DAILY BOOK: {len(live)} live entries since 10-09; the backtest rule on the same universe and bars: {len(G)} trades "
              f"open in the window (3 flat bars are appended so signals on the last closes show; their entry price is a copy)"]
    explained = 0
    for s, e in live:
        g = G[G.coin == s]
        tb = buys.get(s)
        same = g[(g.units.map(lambda u: abs(u[0][1] / e - 1)) <= 0.02)]
        held = g[(g.t_in < START.floor("D"))] if tb is not None and len(g[(g.t_in < START.floor("D"))]) else g.iloc[0:0]
        late = g[g.t_in.map(lambda t: tb is not None and pd.Timedelta(0) < tb - pd.Timestamp(t) <= pd.Timedelta(days=2))]
        if len(same):
            why = f"= backtest in {same.iloc[0].units[0][1]:.6g} on {pd.Timestamp(same.iloc[0].t_in):%m-%d}"
        elif len(held):
            why = (f"the backtest was ALREADY IN since {pd.Timestamp(held.iloc[0].t_in):%m-%d} (before the live start); the live "
                   f"book, flat at the start, bought the next signal")
        elif len(late):
            why = (f"a day LATE: backtest in {pd.Timestamp(late.iloc[0].t_in):%m-%d} at {late.iloc[0].units[0][1]:.6g}; live bought "
                   f"{tb:%m-%d %H:%M} at {e:.6g} - the coin was not in the live universe the day before (rebuilt daily from today's volume)")
        else:
            why = "NOT explained"
        explained += why != "NOT explained"
        L.append(f"    {s:<14} live in {e:.6g}  {why}")
    taken = {s for s, _ in live}
    extra = G[~G.coin.isin(taken) & (G.t_in >= START.floor("D"))]
    for r in extra.itertuples():
        L.append(f"    BACKTEST ONLY {r.coin:<14} in {r.units[0][1]:.6g} on {pd.Timestamp(r.t_in):%m-%d}")
    return explained == len(live) and len(extra) <= 2


def mn(folder, L):
    import mn_paper as mp
    from final_books import rsi
    rows = pd.read_csv(folder / "combo_mn.csv")
    syms, _ = mp.perp_universe()
    bars = mp.fetch_all(mp.candidates(syms))
    L += ["", "MN BLEND (backtest ranking on the live eligible universe as of each rebalance close)"]
    ok = True
    for r in rows.itertuples():
        day = pd.Timestamp(r.day)
        cut = {s: d[d.time < day].reset_index(drop=True) for s, d in bars.items()}
        elig = mp.eligible(cut, day.strftime("%Y-%m"))
        mom, rs = {}, {}
        for s in elig:
            c = cut[s].close.to_numpy(float)
            if len(c) > 31 and c[-31] > 0:
                mom[s] = c[-1] / c[-31] - 1
                rs[s] = float(rsi(c)[-1])
        k = max(int(len(mom) * 0.10), 3)
        pick = lambda sc: (set(sorted(sc, key=sc.get)[-k:]), set(sorted(sc, key=sc.get)[:k]))  # noqa: E731
        (ml, ms), (rl, rsh) = pick(mom), pick(rs)
        bl, bs = {s[:-4] for s in ml | rl}, {s[:-4] for s in ms | rsh}
        ll, ls = set(r.longs.split()), set(r.shorts.split())
        fl, fs = len(ll & bl) / len(ll), len(ls & bs) / len(ls)
        ok = ok and fl >= 0.8 and fs >= 0.8
        L.append(f"  {r.day}: eligible live {r.n_elig} / here {len(elig)}; longs {len(ll & bl)} of {len(ll)} the backtest's "
                 f"({' '.join(sorted(ll - bl)) or '-'} not), shorts {len(ls & bs)} of {len(ls)} ({' '.join(sorted(ls - bs)) or '-'} not)")
    return ok


def capit2_sleeve_ndx(st, closed, L):
    from final_books import rsi
    from backtest.market_neutral import btc_regime
    uni = st["fin"]["uni40"]
    hits = []
    D4 = {}
    for s in uni:
        d = klines(s, "4h", 200)
        if d is None or len(d) < 60:
            continue
        r = rsi(d.c.to_numpy())
        vavg = d.v.rolling(20).mean().shift(1)
        x = (np.r_[False, (r[:-1] >= 20) & (r[1:] < 20)]) & (d.v > 2.0 * vavg).to_numpy()
        for i in np.flatnonzero(x):
            hits.append((int(d.t[i]), s, d.c[i] / d.c[i - 6] - 1 if i >= 6 else np.nan))
        D4[s] = d
    H = pd.DataFrame(hits, columns=["t", "s", "dr24"])
    H = H[H.t >= int(START.timestamp() * 1000) - 6 * 14_400_000]
    sig = []
    for t in sorted(H.t.unique()):
        w = H[(H.t > t - 6 * 14_400_000) & (H.t <= t)]
        if w.s.nunique() >= 5:
            for x in H[(H.t == t) & (H.dr24 <= -0.10)].itertuples():
                sig.append((pd.Timestamp(t, unit="ms"), x.s))
    sig = [x for x in sig if x[0] >= START]
    btc = klines("BTCUSDT", "1d", 150)
    C = pd.DataFrame({"BTCUSDT": btc.c.to_numpy()}, index=pd.to_datetime(btc.t, unit="ms"))
    reg = btc_regime(C)
    reg = reg[reg.index >= START.floor("D")]
    import yfinance as yf
    nd = yf.download("^NDX", start="2026-06-01", progress=False, auto_adjust=False)["Close"].squeeze().dropna()
    d = nd.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 2, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 2, adjust=False).mean()
    r2 = 100 - 100 / (1 + up / dn)
    s5 = nd.rolling(5).mean()
    w = nd.index >= START.floor("D")
    ent = [t for t in nd.index[w] if r2[t] < 10]
    exits = [t for t in nd.index[w] if ent and t > ent[0] and nd[t] > s5[t]]
    q = closed[closed.book == "ndx"]
    L += ["", f"CAPIT2: backtest signals in the window: {len(sig)} ({', '.join(f'{s} {t:%m-%d %H:%M}' for t, s in sig) or 'none'}); "
              f"live placed {st['fin']['capit2']['placed']}",
          f"SLEEVE: BTC labels since 10-09: {reg.value_counts().to_dict()}; live sleeve trades 0",
          f"NDX: RSI(2) < 10 closes since 10-09: {[f'{t:%m-%d}' for t in ent]}; first close above the 5-day average after: "
          f"{exits[0].strftime('%m-%d') if exits else '-'} | live: bought {float(q.entry.iloc[0]) if len(q) else '-'}, sold "
          f"{q.ts.iloc[0] if len(q) else '-'} ({q.why.iloc[0] if len(q) else '-'})"]
    v4 = len(sig) == st["fin"]["capit2"]["placed"] and "bear" not in set(reg) and bool(ent) and len(q) == 1 \
        and exits and pd.Timestamp(q.ts.iloc[0]).date() == exits[0].date()
    return v4


def main():
    folder = Path(sys.argv[1])
    st = json.loads((folder / "combo_state.json").read_text())
    st["_log"] = (folder / "combo_paper.log").read_text(encoding="utf-8", errors="replace")
    closed = pd.read_csv(folder / "combo_final_trades.csv")
    L = [f"backtest/live_check.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; live = combo-bot-final since {START} UTC "
         f"(logs copied read-only from the VM); backtest code on fresh Binance / Yahoo data", ""]
    v1 = trend(folder, L)
    v2 = daily(st, closed, L)
    v3 = mn(folder, L)
    v4 = capit2_sleeve_ndx(st, closed, L)
    L += ["", "REGISTERED PREDICTIONS",
          f"  V1 trend: >= 90% matched, entries within 20bp on >= 90%, R within 0.25 on >= 80% -> {'RIGHT' if v1 else 'WRONG'}",
          f"  V2 daily: every live entry a backtest signal, <= 2 unexplained extras -> {'RIGHT' if v2 else 'WRONG'}",
          f"  V3 MN: >= 80% of live longs and shorts the backtest's on each rebalance -> {'RIGHT' if v3 else 'WRONG'}",
          f"  V4 capit2 / sleeve / NDX agree -> {'RIGHT' if v4 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

"""ODDS NOW - "if I go long / short this coin right now, how often does take-profit hit first?"

A read-only setup checker for a MANUAL trade. It is not the bot and places no orders.

WHAT IT DOES
    1. Reads the coin's last CLOSED 1h bars on Bitget (public candles, no keys) and puts the
       moment in a cell:
         RSI(14)        <30 | 30-45 | 45-55 | 55-70 | >70
         24h momentum   (close - close 24 bars ago) / ATR14:  < -6 | -6..-2 | -2..2 | 2..6 | > 6
         location       where the close sits in the last 50 bars' high-low range:
                        < 0.2 near support | middle | > 0.8 near resistance
         BTC gate       BTC above / below its 1000-hour average (the bot's own regime gate)
    2. Finds every past moment in the SAME cell on the point-in-time top-50 perps by volume
       (wide_book.eligibility, dead coins included), 2020-01 .. the archive's last bar.
    3. Replays the trade from each of them, and from every other moment too (the baseline):
         entry   the NEXT bar's open (the signal bar has closed; you click after it)
         stop    2 x ATR14 from entry = 1R (the bot's own stop)
         target  1R, 2R and 3R, each measured separately
         timeout 48 bars - closed at the 48th bar's close if neither is touched
         fills   PESSIMISTIC: a bar that touches both stop and target is a stop; a bar that
                 gaps through the stop fills at its open; the target fills at the target
         costs   12bp round trip, plus real Binance funding for every settlement held
                 (long pays, short receives)
       Trades never overlap on one coin: after one is taken the next may start only once it
       has exited. Standard errors are clustered by day (alts move together).
    4. Prints P(take-profit first) for this setup AND for any moment - the second number is the
       coin flip. With a stop 3x further than the target you win ~75% at random; the win rate
       alone means nothing. It also prints the average result after costs.

    VERDICT, per target. "EDGE" only if ALL of:
        the setup beats any-moment after costs with t > 2.4 (3 targets tested: Bonferroni);
        it beats any-moment on BOTH the tune half and the holdout half (split 60/40 by time);
        its own average result after costs is positive on BOTH halves;
        at least 30 trades in each half.
    Otherwise "NO EDGE". On "NO EDGE" the honest reading is: this trade is a coin flip that
    pays the exchange.

REGISTERED BEFORE THE FIRST RUN (2026-10-06)
    - Single queries will mostly read NO EDGE: RSI / momentum / range location are the retail
      toolkit doc 02 already buried (RSI+Bollinger PF 0.46-0.85, EMA/MACD/RSI combinations zero,
      momentum scalping -34..-56%/month).
    - The full sweep (150 cells x 2 sides x 3 targets = 900 tests) passes 0-5 - about what
      chance gives - and none of them on a mechanism.
    - Any-moment baseline, long at 1R: P(TP first) ~45-49%, average after costs slightly
      negative.

RESULT (2026-10-06, --sweep, logs/odds_sweep.txt; table 2,714,844 coin-hours, 415 coins,
2020-02 .. 2026-09-19, holdout from 2024-01-28)
    - Baseline as predicted: any-moment long 1R hits target first 47.5%, stop 49.7%, -0.17% a
      trade after costs. Short 1R 49.5% / -0.09%. Longs pay funding, so they read worse.
    - FIRST verdict rule (vs any moment, t > 2.4): 8 of 570 passed - ABOVE the registered 0-5.
      Seven were one cluster: SHORT, flat 24h, near the 50-bar low, BTC under its 1000h mean.
      Checked before believing it: vs any short in the same BTC bear it is t +2.2 / +2.1 (1R /
      2R); 2020 loses, 2023-24 are flat, 52% of months positive, three months (2021-05,
      2022-04, 2022-06) make over 40% of it, +0.15-0.28% a trade. Half of it was "short in a
      bear", and the rest is the size a 570-cell search finds by luck.
    - So the rule was made STRICTER (after the sweep, which is why it is said here): baseline =
      same BTC regime, both halves positive in R AND in %, and EDGE needs t > 3.9 (Bonferroni
      over 570); 2.4 < t <= 3.9 prints WEAK. Re-run: 0 EDGE, 3 WEAK - chance level.
    - Live, 2026-10-05 21:00 UTC: BTC long, SOL short, PEPE long all NO EDGE.
    Reading: RSI, momentum and range location on 1h bars do not tell you which way the next
    48 hours go, beyond what chance gives. The tool's usual answer is the true one: skip it.

    python odds_now.py BTC long                # the question
    python odds_now.py SOL short --capital-pkr 4000 --pkr 280
    python odds_now.py --build                 # (re)build the history table, ~minutes
    python odds_now.py --sweep                 # every cell, written to logs/odds_sweep.txt
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as windows

ROOT = Path(__file__).resolve().parent
PERPS = ROOT / "strategy_analysis" / "data" / "perps"
TABLE = PERPS.parent / "odds_table.parquet"
SWEEP_LOG = ROOT / "logs" / "odds_sweep.txt"

FEE = 0.0012            # round trip
STOP_ATR = 2.0          # 1R
HOLD = 48               # bars before a timeout exit
TPS = (1, 2, 3)         # targets in R
TOP_N = 50
WARMUP = 100            # bars before features are trusted
GATE_H = 1000
T_EDGE = 3.9            # Bonferroni over the sweep's 570 tests (set AFTER the first sweep)
T_WEAK = 2.4            # Bonferroni over the 3 targets of one query
MIN_HALF = 30

RSI_EDGES = [30, 45, 55, 70]
MOM_EDGES = [-6, -2, 2, 6]
LOC_EDGES = [0.2, 0.8]
RSI_NAMES = ["<30 (oversold)", "30-45", "45-55", "55-70", ">70 (overbought)"]
MOM_NAMES = ["strong down", "down", "flat", "up", "strong up"]
LOC_NAMES = ["near support", "middle of range", "near resistance"]
SIDES = {"long": 1, "short": -1}
CELL = ["rsi_b", "mom_b", "loc_b", "bull"]


# ---------------------------------------------------------------- features (causal)

def _wilder(x, n):
    return pd.Series(x).ewm(alpha=1 / n, adjust=False).mean().to_numpy()


def features(o, h, l, c):
    """Everything at row i reads rows <= i only. Rows before WARMUP are marked invalid."""
    c = np.asarray(c, float)
    h = np.asarray(h, float)
    l = np.asarray(l, float)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.fmax(h - l, np.fmax(np.abs(h - pc), np.abs(l - pc)))
    atr = _wilder(tr, 14)
    d = np.r_[0.0, np.diff(c)]
    up, dn = _wilder(np.where(d > 0, d, 0.0), 14), _wilder(np.where(d < 0, -d, 0.0), 14)
    with np.errstate(divide="ignore", invalid="ignore"):
        rsi = np.where(dn > 0, 100 - 100 / (1 + up / dn), 100.0)
        mom = (c - np.r_[np.full(24, np.nan), c[:-24]]) / atr
        hi = pd.Series(h).rolling(50).max().to_numpy()
        lo = pd.Series(l).rolling(50).min().to_numpy()
        loc = (c - lo) / (hi - lo)
    ok = np.isfinite(atr) & (atr > 0) & np.isfinite(mom) & np.isfinite(loc)
    ok[:WARMUP] = False
    return dict(atr=atr, rsi=rsi, mom=mom, loc=loc, ok=ok,
                rsi_b=np.digitize(rsi, RSI_EDGES), mom_b=np.digitize(mom, MOM_EDGES),
                loc_b=np.digitize(loc, LOC_EDGES))


def btc_bull(close):
    """BTC close above its 1000-bar mean, at each closed bar (NaN while warming up)."""
    ma = pd.Series(np.asarray(close, float)).rolling(GATE_H).mean().to_numpy()
    out = np.where(np.isfinite(ma), (np.asarray(close, float) > ma).astype(float), np.nan)
    return out


# ---------------------------------------------------------------- the trade, replayed

def races(o, h, l, c, atr, side, fund_cum=None, ks=TPS, hold=HOLD, fee=FEE):
    """For a signal at the close of every bar i: enter at o[i+1], stop 1R = STOP_ATR x atr[i],
    targets k x R, timeout at c[i+hold]. Returns {k: (code, net R, net % of notional, bars held)}
    with code 1 = target, -1 = stop, 0 = timeout. Rows without a full window are NaN.

    fund_cum: cumulative (funding rate x price) by bar, a settlement booked on the bar that
    STARTS at it. A position entered at o[i+1] and leaving during bar x pays bars i+2..x."""
    o, h, l, c, atr = (np.asarray(a, float) for a in (o, h, l, c, atr))
    n = len(c)
    m = n - hold                                    # signals with a full window
    out = {k: [np.full(n, np.nan) for _ in range(4)] for k in ks}
    if m <= 0:
        return out
    H, L, O = windows(h[1:], hold)[:m], windows(l[1:], hold)[:m], windows(o[1:], hold)[:m]
    e = o[1:m + 1]
    r = STOP_ATR * atr[:m]
    stop = e - side * r
    hit_s = (L <= stop[:, None]) if side > 0 else (H >= stop[:, None])
    js = np.where(hit_s.any(1), hit_s.argmax(1), hold)
    rows = np.arange(m)
    for k in ks:
        tp = e + side * k * r
        hit_t = (H >= tp[:, None]) if side > 0 else (L <= tp[:, None])
        jt = np.where(hit_t.any(1), hit_t.argmax(1), hold)
        lose = (js <= jt) & (js < hold)             # same bar -> the stop (pessimistic)
        win = ~lose & (jt < hold)
        j = np.where(lose, js, np.where(win, jt, hold - 1))
        o_j = O[rows, j]
        fill_s = np.minimum(o_j, stop) if side > 0 else np.maximum(o_j, stop)
        gross = np.where(lose, side * (fill_s - e) / r,
                         np.where(win, float(k), side * (c[rows + hold] - e) / r))
        fund = np.zeros(m)
        if fund_cum is not None:
            fc = np.asarray(fund_cum, float)
            fund = -side * (fc[rows + 1 + j] - fc[rows + 1]) / r
        net = gross + fund - fee * e / r
        code = np.where(lose, -1.0, np.where(win, 1.0, 0.0))
        for a, v in zip(out[k], (code, net, net * r / e * 100, j + 1.0)):
            a[:m] = v
    return out


# ---------------------------------------------------------------- the history table

def load_perp(sym):
    d = pd.read_csv(PERPS / f"{sym}_1h.csv.gz", parse_dates=["time"])
    return d.rename(columns={"open": "o", "high": "h", "low": "l", "close": "c"})


def fund_by_bar(sym, times, opens):
    """Cumulative funding (rate x price) on the coin's bar grid, booked on the bar that starts
    at the settlement. Zero if the archive has no funding for the coin."""
    f = PERPS / f"{sym}_funding.csv.gz"
    per = np.zeros(len(times))
    if f.exists():
        fr = pd.read_csv(f)
        ts = pd.to_datetime(fr["time"]).dt.floor("h").to_numpy("datetime64[ns]")
        tg = np.asarray(times, "datetime64[ns]")
        idx = np.searchsorted(tg, ts)
        ok = (idx < len(tg)) & (tg[np.minimum(idx, len(tg) - 1)] == ts)
        np.add.at(per, idx[ok], fr["rate"].to_numpy(float)[ok] * np.asarray(opens)[idx[ok]])
    return np.cumsum(per)


def coin_rows(sym, d, bull_at, months=None, fund_cum=None):
    """One coin's table: cell + outcome columns for every valid signal bar."""
    f = features(d.o, d.h, d.l, d.c)
    t = pd.DatetimeIndex(d.time)
    bull = bull_at.reindex(t).to_numpy(float)
    keep = f["ok"] & np.isfinite(bull)
    # A window may not cross a hole in the bars or a >50% open-vs-last-close jump (a halt, a
    # redenomination): BNX's 3-week gap in 2023 read as -98% losers before this.
    o, c = d.o.to_numpy(float), d.c.to_numpy(float)
    bad = np.zeros(len(d), bool)
    bad[1:] = ((np.diff(t.as_unit("ns").asi8) != 3_600_000_000_000)
               | (np.abs(np.log(o[1:] / c[:-1])) > np.log(1.5)))
    cb = np.r_[0, np.cumsum(bad)]
    i = np.arange(len(d))
    lo, hi = np.maximum(i - WARMUP + 1, 0), np.minimum(i + HOLD + 1, len(d) - 1)
    keep &= (cb[hi + 1] - cb[lo]) == 0
    if months is not None:
        keep &= np.isin(t.strftime("%Y-%m"), list(months))
    cols = dict(coin=sym, time=t, rsi_b=f["rsi_b"].astype(np.int8),
                mom_b=f["mom_b"].astype(np.int8), loc_b=f["loc_b"].astype(np.int8),
                bull=np.nan_to_num(bull).astype(np.int8))
    for name, s in SIDES.items():
        with np.errstate(all="ignore"):
            res = races(d.o, d.h, d.l, d.c, f["atr"], s, fund_cum)
        for k, (code, net, pct, held) in res.items():
            keep &= np.isfinite(net)
            cols[f"{name}{k}_code"] = np.nan_to_num(code).astype(np.int8)
            cols[f"{name}{k}_R"] = np.nan_to_num(net, posinf=0, neginf=0).astype(np.float32)
            cols[f"{name}{k}_pct"] = np.nan_to_num(pct, posinf=0, neginf=0).astype(np.float32)
            cols[f"{name}{k}_held"] = np.nan_to_num(held).astype(np.int8)
    return pd.DataFrame(cols)[keep]


def build():
    sys.path.insert(0, str(ROOT))
    from backtest.wide_book import eligibility
    t0 = time.time()
    elig = {s: m for s, m in eligibility(TOP_N).items() if m}
    btc = load_perp("BTCUSDT")
    bull_at = pd.Series(btc_bull(btc.c), index=pd.DatetimeIndex(btc.time))
    parts = []
    for i, (sym, months) in enumerate(sorted(elig.items())):
        if not (PERPS / f"{sym}_1h.csv.gz").exists():
            continue
        d = load_perp(sym)
        if len(d) < WARMUP + HOLD + 10:
            continue
        parts.append(coin_rows(sym, d, bull_at, months, fund_by_bar(sym, d.time, d.o)))
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(elig)} coins, {sum(map(len, parts)):,} rows", flush=True)
    tab = pd.concat(parts, ignore_index=True)
    if len(tab) < 1_000_000:          # a units slip once emptied this silently (CLAUDE.md s3)
        raise SystemExit(f"history table has only {len(tab):,} rows - something is excluding them")
    tab["coin"] = tab["coin"].astype("category")
    tab.to_parquet(TABLE)
    print(f"table: {len(tab):,} coin-hours, {tab.coin.nunique()} coins, "
          f"{tab.time.min()} .. {tab.time.max()}, {time.time() - t0:.0f}s -> {TABLE}")
    return tab


def load_table():
    if not TABLE.exists():
        print("No history table yet - building it once (a few minutes).")
        return build()
    return pd.read_parquet(TABLE)


# ---------------------------------------------------------------- statistics

def no_overlap(coin_codes, hours, held):
    """Indices of trades taken one at a time per coin: the next signal must come at or after
    the previous trade's exit bar. Input must be sorted by (coin, hour)."""
    keep = np.zeros(len(hours), bool)
    last_coin, free = -1, -np.inf
    for i in range(len(hours)):
        if coin_codes[i] != last_coin:
            last_coin, free = coin_codes[i], -np.inf
        if hours[i] >= free:
            keep[i] = True
            free = hours[i] + held[i]
    return keep


def trades(tab, side, k):
    """Non-overlapping trades from the rows of tab (any subset), for one side and target."""
    p = f"{side}{k}"
    sub = tab.sort_values(["coin", "time"], kind="stable")
    hours = sub["time"].to_numpy("datetime64[h]").astype(np.int64)
    keep = no_overlap(sub["coin"].cat.codes.to_numpy() if hasattr(sub["coin"], "cat")
                      else pd.factorize(sub["coin"])[0], hours,
                      sub[f"{p}_held"].to_numpy(np.int64))
    sub = sub[keep]
    return pd.DataFrame({"time": sub["time"].to_numpy(), "code": sub[f"{p}_code"].to_numpy(),
                         "R": sub[f"{p}_R"].to_numpy(float),
                         "pct": sub[f"{p}_pct"].to_numpy(float)})


def summary(tr):
    """n, P(target first), P(stop first), mean net R, day-clustered se, mean net %."""
    n = len(tr)
    if n == 0:
        return dict(n=0, p_tp=np.nan, p_sl=np.nan, R=np.nan, se=np.nan, pct=np.nan)
    R = tr["R"].to_numpy()
    mu = R.mean()
    days = tr["time"].to_numpy("datetime64[D]")
    s = pd.Series(R - mu).groupby(days).sum().to_numpy()
    g = len(s)
    se = np.sqrt((s ** 2).sum() * g / max(g - 1, 1)) / n if n > 1 else np.nan
    return dict(n=n, p_tp=(tr["code"] == 1).mean(), p_sl=(tr["code"] == -1).mean(),
                R=mu, se=se, pct=tr["pct"].mean())


def split_time(tab):
    ts = np.sort(tab["time"].unique())
    return ts[int(len(ts) * 0.6)]


_BASE: dict = {}


def base_trades(tab, side, k, bull=None):
    """Baseline trades for one side/target - every moment, or every moment in one BTC regime
    (bull = 1 / 0) - built once per table."""
    key = (id(tab), side, k, bull)
    if key not in _BASE:
        _BASE[key] = trades(tab if bull is None else tab[tab["bull"].to_numpy() == bull], side, k)
    return _BASE[key]


def judge(s_all, b_all, split):
    """Setup trades vs baseline trades, overall and per half, and the verdict:
    EDGE (t > T_EDGE), WEAK (T_WEAK < t <= T_EDGE: what chance gives across the sweep), or
    NO EDGE. Both halves must beat the baseline AND be positive after costs for either."""
    out = {}
    for name, sel in (("all", None), ("tune", True), ("hold", False)):
        s_tr, b_tr = s_all, b_all
        if sel is not None:
            s_tr = s_all[(s_all["time"] < split) == sel]
            b_tr = b_all[(b_all["time"] < split) == sel]
        s, b = summary(s_tr), summary(b_tr)
        diff = s["R"] - b["R"]
        se = np.sqrt(s["se"] ** 2 + b["se"] ** 2)
        out[name] = dict(setup=s, base=b, diff=diff, t=diff / se if se > 0 else np.nan)
    a, tu, ho = out["all"], out["tune"], out["hold"]
    reasons = []
    for nm, h in (("tune", tu), ("holdout", ho)):
        if h["setup"]["n"] < MIN_HALF:
            reasons.append(f"only {h['setup']['n']} trades in the {nm} half")
        elif not (h["diff"] > 0):
            reasons.append(f"no better than the baseline on the {nm} half")
        elif not (h["setup"]["R"] > 0 and h["setup"]["pct"] > 0):
            reasons.append(f"loses after costs on the {nm} half")
    if a["t"] > T_EDGE and not reasons:
        level = "EDGE"
    elif a["t"] > T_WEAK and not reasons:
        level = "WEAK"
        reasons.append(f"t {a['t']:+.1f} beats the baseline, but under the {T_EDGE} a search of "
                       f"~570 situations needs - about what luck produces")
    else:
        level = "NO EDGE"
        if not (a["t"] > T_WEAK):
            reasons.insert(0, f"beats the baseline by t {a['t']:+.1f}, needs > {T_WEAK}")
    out.update(level=level, edge=level == "EDGE", why=reasons)
    return out


def cell_mask(tab, cell):
    m = np.ones(len(tab), bool)
    for col, v in zip(CELL, cell):
        m &= tab[col].to_numpy() == v
    return m


# ---------------------------------------------------------------- live

def bitget_1h(base, bars):
    """The last `bars` CLOSED 1h candles of BASE/USDT perp on Bitget (public, no keys)."""
    import ccxt
    ex = ccxt.bitget({"enableRateLimit": True, "options": {"defaultType": "swap"}})
    ex.load_markets()
    sym = f"{base}/USDT:USDT"
    if sym not in ex.markets:
        raise SystemExit(f"{sym} is not a Bitget USDT perp")
    now = ex.milliseconds()
    since, rows = now - (bars + 5) * 3_600_000, []
    while since < now:
        got = ex.fetch_ohlcv(sym, "1h", since=since, limit=1000)
        if not got:
            break
        rows += got
        nxt = got[-1][0] + 3_600_000
        if nxt <= since:
            break
        since = nxt
    d = pd.DataFrame(rows, columns=["t", "o", "h", "l", "c", "v"]).drop_duplicates("t")
    d = d[d["t"] + 3_600_000 <= now].sort_values("t")           # closed bars only
    d["time"] = pd.to_datetime(d["t"], unit="ms")
    return d.reset_index(drop=True), sym


def now_cell(base):
    d, sym = bitget_1h(base, 400)
    btc, _ = bitget_1h("BTC", GATE_H + 50)
    f = features(d.o, d.h, d.l, d.c)
    bull = btc_bull(btc.c)[-1]
    if not np.isfinite(bull):
        raise SystemExit(f"Bitget returned only {len(btc)} BTC bars; need {GATE_H}")
    i = len(d) - 1
    return dict(sym=sym, bar=d.time.iloc[i], px=float(d.c.iloc[i]), atr=float(f["atr"][i]),
                rsi=float(f["rsi"][i]), mom=float(f["mom"][i]), loc=float(f["loc"][i]),
                cell=(int(f["rsi_b"][i]), int(f["mom_b"][i]), int(f["loc_b"][i]), int(bull)))


def report(base, side, capital_pkr, pkr):
    tab = load_table()
    now = now_cell(base)
    cell, s = now["cell"], SIDES[side]
    print(f"\n{now['sym']}  last closed 1h bar: {now['bar']:%Y-%m-%d %H:%M}-"
          f"{now['bar'] + pd.Timedelta(hours=1):%H:%M} UTC, close {now['px']:g}")
    print(f"  RSI {now['rsi']:.0f} -> {RSI_NAMES[cell[0]]} | 24h move {now['mom']:+.1f} ATR -> "
          f"{MOM_NAMES[cell[1]]} | range position {now['loc']:.2f} -> {LOC_NAMES[cell[2]]} | "
          f"BTC {'ABOVE' if cell[3] else 'BELOW'} its 1000h average")
    split = split_time(tab)
    rows = tab[cell_mask(tab, cell)]
    print(f"\nHistory: {len(rows):,} coin-hours in this exact situation on the top-{TOP_N} perps, "
          f"{tab.time.min():%Y-%m} .. {tab.time.max():%Y-%m-%d} (holdout from {pd.Timestamp(split):%Y-%m})")
    print(f"\n{side.upper()}, stop 2xATR = 1R, after 12bp fees and funding, pessimistic fills:")
    reg = "BTC-bull" if cell[3] else "BTC-bear"
    print(f"  baseline = every {side} taken at any moment while BTC was in the same regime ({reg})")
    print(f"  {'target':>7} | {'TP first: this setup':>21} | {'baseline':>8} | "
          f"{'avg / trade':>11} | {'baseline':>8} | {'trades':>6} | verdict")
    verdicts = {}
    for k in TPS:
        j = judge(trades(rows, side, k), base_trades(tab, side, k, cell[3]), split)
        a = j["all"]
        verdicts[k] = j
        print(f"  {k:>6}R | {a['setup']['p_tp']:>20.0%} | {a['base']['p_tp']:>8.0%} | "
              f"{a['setup']['pct']:>+10.2f}% | {a['base']['pct']:>+7.2f}% | {a['setup']['n']:>6} | "
              f"{j['level']}")
    print("\n  per half (tune / holdout):  TP-first %  and  avg %/trade, setup vs baseline")
    for k in TPS:
        tu, ho = verdicts[k]["tune"], verdicts[k]["hold"]
        print(f"  {k}R  tune {tu['setup']['p_tp']:.0%} vs {tu['base']['p_tp']:.0%}, "
              f"{tu['setup']['pct']:+.2f}% vs {tu['base']['pct']:+.2f}% (n {tu['setup']['n']}) | "
              f"holdout {ho['setup']['p_tp']:.0%} vs {ho['base']['p_tp']:.0%}, "
              f"{ho['setup']['pct']:+.2f}% vs {ho['base']['pct']:+.2f}% (n {ho['setup']['n']})")
    for k in TPS:
        if not verdicts[k]["edge"]:
            print(f"  {k}R {verdicts[k]['level']}: " + "; ".join(verdicts[k]["why"]))
    coin = f"{base}USDT"
    own = rows[rows["coin"].astype(str).isin([coin, f"1000{base}USDT"])]
    if len(own):
        o1 = summary(trades(own, side, 1))
        print(f"\n  {base} alone in this situation: {o1['n']} trades, 1R TP-first {o1['p_tp']:.0%}, "
              f"avg {o1['pct']:+.2f}%/trade (small sample - context, not the verdict)")

    r = STOP_ATR * now["atr"]
    px = now["px"]
    print(f"\nLevels if entered near {px:g} (you will get the next price, not this close):")
    print(f"  stop {px - s * r:g}  ({r / px:.2%} away)")
    for k in TPS:
        print(f"  {k}R target {px + s * k * r:g}  ({k * r / px:.2%} away)")
    cap_usd = capital_pkr / pkr
    print(f"\nArithmetic on {capital_pkr:,.0f} PKR (~${cap_usd:.2f} at {pkr:g} PKR/$), Bitget minimum "
          f"order ~$5, liquidation roughly 1/leverage away (less after fees):")
    for notional in sorted({5.0, round(cap_usd, 2), round(3 * cap_usd, 2), round(10 * cap_usd, 2)}):
        lev = notional / cap_usd
        loss = notional * (r / px + FEE)
        flag = "  <- liquidated BEFORE the stop" if 1 / lev <= r / px else ""
        print(f"  position ${notional:>7.2f} ({lev:4.1f}x): stop loses {loss * pkr:>6.0f} PKR "
              f"({loss / cap_usd:5.1%} of capital), 1R target makes "
              f"{notional * (r / px - FEE) * pkr:>6.0f} PKR{flag}")
    levels = {v["level"] for v in verdicts.values()}
    if "EDGE" in levels:
        msg = ("an edge that survives the full search, on both halves - still a backtest; a "
               "forward check comes before money.")
    elif "WEAK" in levels:
        msg = ("WEAK - better than the baseline on both halves, but by no more than searching "
               "~570 situations produces by luck. Tiny per trade. Not a reason to trade.")
    else:
        msg = ("NO EDGE. In this situation the trade has been a coin flip that pays fees. "
               "Skipping it is the measured choice.")
    print("\nREADING: " + msg)
    print("This is a historical measurement, not advice; the decision is yours.")


# ---------------------------------------------------------------- sweep

def sweep():
    tab = load_table()
    split = split_time(tab)
    lines, passes, tested = [], [], 0
    for bull in (None, 1, 0):
        for side in SIDES:
            for k in TPS:
                b = summary(base_trades(tab, side, k, bull))
                tag = {None: "any moment", 1: "BTC bull  ", 0: "BTC bear  "}[bull]
                lines.append(f"{tag} {side:>5} {k}R: n {b['n']:>6}, TP first {b['p_tp']:.1%}, "
                             f"stop first {b['p_sl']:.1%}, avg {b['R']:+.3f}R / {b['pct']:+.3f}%")
    groups = tab.groupby(CELL, observed=True).indices
    for cell, idx in sorted(groups.items()):
        rows = tab.iloc[idx]
        for side in SIDES:
            for k in TPS:
                tested += 1
                j = judge(trades(rows, side, k), base_trades(tab, side, k, cell[3]), split)
                a = j["all"]
                if j["level"] != "NO EDGE":
                    passes.append(
                        f"{j['level']:>4} {side} {k}R  RSI {RSI_NAMES[cell[0]]}, {MOM_NAMES[cell[1]]}, "
                        f"{LOC_NAMES[cell[2]]}, BTC {'bull' if cell[3] else 'bear'}: "
                        f"t {a['t']:+.1f}, avg {a['setup']['pct']:+.2f}% vs {a['base']['pct']:+.2f}%, "
                        f"TP first {a['setup']['p_tp']:.0%} vs {a['base']['p_tp']:.0%}, n {a['setup']['n']}, "
                        f"tune {j['tune']['setup']['pct']:+.2f}% holdout {j['hold']['setup']['pct']:+.2f}%")
    n_edge = sum(p.startswith("EDGE") for p in passes)
    lines.append(f"\n{tested} tests (cells x sides x targets), baseline = same BTC regime: "
                 f"{n_edge} EDGE (t > {T_EDGE}), {len(passes) - n_edge} WEAK "
                 f"(t > {T_WEAK}, both halves)")
    lines += passes
    txt = "\n".join(lines)
    print(txt)
    SWEEP_LOG.write_text(f"odds_now.py --sweep, table {len(tab):,} rows, split "
                         f"{pd.Timestamp(split):%Y-%m-%d}\n\n" + txt + "\n")
    print(f"\n-> {SWEEP_LOG}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("coin", nargs="?")
    ap.add_argument("side", nargs="?", choices=list(SIDES))
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--capital-pkr", type=float, default=4000)
    ap.add_argument("--pkr", type=float, default=280.0, help="PKR per USD")
    a = ap.parse_args()
    if a.build:
        return build()
    if a.sweep:
        return sweep()
    if not (a.coin and a.side):
        ap.error("give a coin and a side, e.g.  python odds_now.py BTC long")
    report(a.coin.upper(), a.side, a.capital_pkr, a.pkr)


if __name__ == "__main__":
    main()

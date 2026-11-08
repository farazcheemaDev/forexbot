"""THE RSI-80 MOMENTUM PAPER BOOK - registered 2026-11-08, before its first trade. PAPER ONLY: public Binance futures prices, no keys, no orders.

THE USER (2026-11-08): "yes, record it" - after backtest/rsi80_more.py found the rule positive on data it had never seen (+0.14R a trade on perps ranked 41-100
and 2017-19 spot, a narrow no-pass at t 1.80) and backtest/rsi80_overlap.py showed it is NOT the trend book again (daily correlation -0.04, different days,
89% different coins) but not a proven add-on either. A forward record is the only evidence left. This book is OUTSIDE main and fresh (doc 22 override,
like the crowd book): it touches no bot, and the code freeze on the bots stands.

THE RULE (frozen; backtest/rsi_ratio.py's cell, reproduced in plain Python - tests/test_rsi80_paper.py checks every piece against the backtest's own code
on real coin history, trade for trade):
  UNIVERSE  Binance USDT perpetuals (crypto only: underlying type COIN, no stable / gold / fiat bases), ranked by the PRIOR calendar month's quote volume,
            listed 30+ days before the month began; the top 100, fixed for the month (the backtest's point-in-time rule, wide_book.eligibility).
  SIGNAL    on a CLOSED 4h bar: Wilder RSI(14) of the closes crosses UP through 80 (previous bar <= 80, this bar > 80), with 60 contiguous 4h bars behind it,
            the coin in the universe of the signal bar's month, and no position open in that coin (a signal on the bar a trade left on is allowed).
  ENTRY     LONG at the OPEN of the next 4h bar (the backtest's fill). The price this job actually sees is logged beside it (the real fill is minutes later).
            Not taken if the job runs more than an hour into that bar (no stale entries; a missed bar's signal is lost, its exits are not).
  EXITS     stop = entry - 4 x ATR(14) (ATR = the plain mean of the last 14 true ranges) = 1R; target = entry + 4R; on each 4h bar from the entry bar on:
            the stop first (a gap through it fills at the open), then the target (a gap past it fills at the open), else out at the close of bar 24 (4 days).
            A trade whose stop is under 0.2% of the entry is not taken.
  COSTS     12bp of the notional round trip; the FUNDING the coin really paid over the hold (Binance fundingRate, settlements in (entry, exit end]).
            The backtest's flat 1bp / 8h figure is logged beside it so the forward R compares with the backtest like for like.
  ACCOUNT   $300 paper, every signal taken; each risks 1% of the BOOKED equity at entry (rule 12); notional = risk / stop distance; a position under $5, or one
            that would take the open notional past 10x the equity, is still scored as a prediction but takes no paper money ('not booked').

WHAT TO EXPECT (backtest, the coins it never saw - logs/rsi80_more.txt; bands from the trades in logs/rsi80_more_trades.pkl, computed 2026-11-08):
  About +0.13R a trade before the day-clustering, ~360 signals a year on the top 100; most trades lose a little and a few burst weeks carry it.
  12-week stretches on the unseen coins: mean R a trade 10th pct -0.17, median +0.06, 75th +0.24, 39% of them below zero; 22 weeks: 10th -0.11, median +0.07,
  30% below zero (on all top-100 coins incl. where it was found: 12 weeks 10th -0.24 / median +0.12; 22 weeks 10th -0.09 / median +0.16).
  So a five-month record can only catch a CLEAR failure; confirming a +0.1R edge would take one to two years.

REGISTERED LINES (2026-11-08, before the first trade; mean R = net of fees and REAL funding, booked and not-booked trades alike)
  KILL   at 2027-01-31: with at least 30 resolved trades, a mean R under -0.24 (the all-top-100 12-week 10th percentile, the lenient one) -> DEAD, stop the book.
  VERDICT at 2027-04-09 (with the machine's verdict, doc 22): HELD UP = mean R >= +0.072 (the unseen coins' 22-week median) AND the paper account above $300;
         DEAD = mean R under -0.107 (their 22-week 10th percentile); anything between = CANNOT TELL, the record runs on to 2027-10-09 under the same lines.
  Predictions: F1 by 2027-01-31 the book has 40-140 resolved trades (75%); F2 its 12-week mean R is above zero (60%); F3 the real fills (the price the job saw)
  average within 0.3% of the bar opens it books (70%); F4 HELD UP at 2027-04-09 (35%), DEAD (15%).
AMENDED 2026-11-08 21:15 UTC, at the user's word ("yes, check sooner"), with 1 trade open and none resolved: the job runs 30 SECONDS after each 4h bar
  closes (00:00:30, 04:00:30, ... UTC) instead of 5 minutes after. Nothing booked changes - entries are still booked at the bar's open, exits on closed bars - so
  the registered lines and the verdict are untouched. Only the 'seen' price logged beside each entry moves: the first trade (JCTUSDT, 2026-11-08 20:00) was seen
  5 minutes late at 0.01609 against a 0.013213 open (+21.8%), which says nothing about what a bot at the open would get. F3 is scored on the entries from
  this amendment on; that first trade's gap stays on the record, labelled.

CHECKED BEFORE THE FIRST RUN: tests/test_rsi80_paper.py, 14 tests - the RSI / ATR / exits equal rsi_ratio / candle_manage's, and the live loop replayed over the
  real 4h history of SOL, DOGE, LINK and AVAX reproduces every one of the backtest's trades (same entry, same exit bar, same R; its only extra trades sit where
  the backtest's own rule could not see 24 bars ahead); 27 of 28 planted bugs caught, the 28th equivalent (a second look at an already-decided bar), a do-nothing
  control survived. One live run on the PC (2026-11-08 18:12 UTC): 516 perps read, the November top 100 ranked, 100 coins checked, no signal.

    python rsi80_paper.py            one run: manage open trades on every closed 4h bar, check the bar that just closed for signals, write the logs
    python rsi80_paper.py --status   the record against the registered lines
State in logs/rsi80/ (state.json, trades.csv). On the VM: deploy/rsi80-paper.service + .timer (30 seconds after every 4h close since 2026-11-08 21:15 UTC; :05 before).
"""
from __future__ import annotations

import csv
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
D = ROOT / "logs" / "rsi80"
STATE, TRADES = D / "state.json", D / "trades.csv"
API = "https://fapi.binance.com"
MIN, H1, H4, DAY = 60_000, 3_600_000, 14_400_000, 86_400_000
RSI_N, ATR_N, LEVEL = 14, 14, 80.0
STOP_ATR, TARGET_R, CAP = 4.0, 4.0, 24
WARM = 60
MIN_RISK = 0.002
FEE = 12e-4
FUND_H = 1e-4 / 8.0
START, RISK, MIN_POS, MAX_GROSS = 300.0, 0.01, 5.0, 10.0
TOP_N, MIN_AGE_D = 100, 30
LATE_MS = H1
NON_CRYPTO = {"PAXG", "XAUT", "EUR", "GBP", "AEUR", "USDC", "TUSD", "BUSD", "FDUSD", "USDP", "DAI", "USD1", "USDE", "SUSDE"}   # = market_neutral.NON_CRYPTO
REGISTERED_UTC = "2026-11-08"
KILL_DATE, KILL_R, KILL_MIN = "2027-01-31", -0.24, 30
VERDICT_DATE, HELD_R, DEAD_R, EXTEND_DATE = "2027-04-09", 0.072, -0.107, "2027-10-09"
COLS = ["coin", "signal_ms", "entry_ms", "entry", "seen_px", "stop", "target", "rf", "exit_ms", "exit", "kind", "bars", "gross_r", "fund_real",
        "net_r_flat", "net_r", "booked", "risk_usd", "notional", "pnl_usd", "equity_after"]


def log(m: str):
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} {m}", flush=True)


def ts(ms) -> str:
    return datetime.fromtimestamp(int(ms) / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M")


# ------------------------------------------------------------------ public data (Binance USDT-M futures)

def get(path: str, params: dict, tries: int = 5):
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "forexbot-paper"}), timeout=20) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001 - network / rate limit: back off and retry
            if k == tries - 1:
                raise
            log(f"GET {path} {params.get('symbol', '')}: {type(e).__name__}, retry {k + 1}")
            time.sleep(2 * (k + 1))


def bars4h(sym: str, fetch=None) -> list:
    """[(open_ms, o, h, l, c, close_ms)] - the last 499 4h bars (weight 2), the forming one included. The RSI's start-up memory after 440 bars is (13/14)^440
    ~ 1e-14 of the first bar's: the same crosses as the backtest's full-history RSI."""
    rows = (fetch or get)("/fapi/v1/klines", dict(symbol=sym, interval="4h", limit=499))
    return [(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), int(r[6])) for r in rows]


def funding(sym: str, a_ms: int, b_ms: int, fetch=None) -> float:
    """Funding a long paid, as a fraction of the notional: the rates settled in (a, b] (half-open, bounded at both ends - mistake #15)."""
    if b_ms <= a_ms:
        return 0.0
    rows = (fetch or get)("/fapi/v1/fundingRate", dict(symbol=sym, startTime=a_ms + 1, endTime=b_ms, limit=1000))
    return float(sum(float(r["fundingRate"]) for r in rows if a_ms < int(r["fundingTime"]) <= b_ms))


def candidates(fetch=None) -> list:
    info = (fetch or get)("/fapi/v1/exchangeInfo", {})
    out = []
    for s in info["symbols"]:
        if (s.get("quoteAsset") == "USDT" and s.get("contractType") == "PERPETUAL" and s.get("status") == "TRADING"
                and s.get("underlyingType", "COIN") == "COIN" and s.get("baseAsset") not in NON_CRYPTO):
            out.append(s["symbol"])
    return sorted(out)


def month_start_ms(month: str) -> int:
    return int(datetime.strptime(month + "-01", "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)


def prev_month(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def rank_universe(daily: dict, month: str) -> list:
    """The top TOP_N by the prior month's quote volume among coins listed MIN_AGE_D+ days before the month began. daily = {sym: [(open_ms, qvol)]}."""
    m0, pm = month_start_ms(month), prev_month(month)
    p0, p1 = month_start_ms(pm), m0
    vol = {}
    for s, rows in daily.items():
        if not rows or (m0 - rows[0][0]) / DAY < MIN_AGE_D:
            continue
        v = sum(q for t, q in rows if p0 <= t < p1)
        if v > 0:
            vol[s] = v
    return sorted(vol, key=lambda s: -vol[s])[:TOP_N]


def universe(st: dict, month: str, fetch=None) -> list:
    """This month's universe, computed once and kept in the state."""
    if month in st["universe"]:
        return st["universe"][month]
    daily, syms = {}, candidates(fetch)
    for s in syms:
        try:
            rows = (fetch or get)("/fapi/v1/klines", dict(symbol=s, interval="1d", limit=70))
            daily[s] = [(int(r[0]), float(r[7])) for r in rows]
        except Exception as e:  # noqa: BLE001
            log(f"universe: {s} daily bars failed ({type(e).__name__})")
        if fetch is None:
            time.sleep(0.05)
    if len(daily) < 0.9 * len(syms):
        raise RuntimeError(f"universe {month}: read {len(daily)} of {len(syms)} perps - not saved, retried next run")
    st["universe"][month] = rank_universe(daily, month)
    log(f"UNIVERSE {month}: top {len(st['universe'][month])} of {len(daily)} perps by {prev_month(month)} quote volume")
    return st["universe"][month]


# ------------------------------------------------------------------ the rule (plain Python; tests pin it to rsi_ratio / candle_manage)

def rsi14(closes: list) -> list:
    """Wilder RSI(14): exponential means (alpha 1/14, from the first bar) of the up and down moves; 100 where the down mean is 0 (= rsi_ratio.rsi14)."""
    a, up, dn, out = 1.0 / RSI_N, 0.0, 0.0, []
    prev = None
    for c in closes:
        d = 0.0 if prev is None else c - prev
        u, w = (d if d > 0 else 0.0), (-d if d < 0 else 0.0)
        if prev is None:
            up, dn = u, w
        else:
            up, dn = (1 - a) * up + a * u, (1 - a) * dn + a * w
        out.append(100.0 if dn <= 0 else 100.0 - 100.0 / (1.0 + up / dn))
        prev = c
    return out


def atr14(h: list, l: list, c: list) -> list:  # noqa: E741
    """The plain mean of the last 14 true ranges (None before 14) (= candle_manage.atr14)."""
    tr = []
    for i in range(len(c)):
        tr.append(h[0] - l[0] if i == 0 else max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
    out = []
    for i in range(len(c)):
        out.append(None if i < ATR_N - 1 else sum(tr[i - ATR_N + 1:i + 1]) / ATR_N)
    return out


def contiguous(t: list, i: int, w: int) -> bool:
    """bars i-w .. i exist and are consecutive 4h bars (rsi_ratio.warm_mask)."""
    return i >= w and all(t[j + 1] - t[j] == H4 for j in range(i - w, i))


def signal(bars: list, i: int, r: list | None = None, a: list | None = None) -> dict | None:
    """The trade a signal on bar i opens at the open of bar i+1, or None (the backtest's conditions, the universe and position checks aside)."""
    if i + 1 >= len(bars) or i < 1:
        return None
    t = [b[0] for b in bars]
    o, h, l, c = ([b[k] for b in bars] for k in (1, 2, 3, 4))  # noqa: E741
    r = r or rsi14(c)
    a = a or atr14(h, l, c)
    if not (contiguous(t, i, WARM) and t[i + 1] - t[i] == H4 and o[i] > 0 and c[i] > 0 and a[i] is not None and a[i] > 0):
        return None
    if not (r[i - 1] <= LEVEL < r[i]):
        return None
    e = o[i + 1]
    risk = STOP_ATR * a[i]
    if e <= 0 or risk / e < MIN_RISK:
        return None
    return dict(signal_ms=t[i], entry_ms=t[i + 1], entry=e, stop=e - risk, target=e + TARGET_R * risk, rf=risk / e, bars=0)


def step(tr: dict, bar: tuple) -> dict | None:
    """One more 4h bar of an open trade (bar k = tr['bars'] + 1; the entry bar is bar 1): the stop first, gaps at the open, then the target, else out at the
    close of bar CAP. Returns the exit or None (still open; tr['bars'] advanced)."""
    k = tr["bars"] + 1
    _, o, h, l, c, close_ms = bar  # noqa: E741
    tr["bars"] = k
    if l <= tr["stop"]:
        return dict(exit=min(tr["stop"], o), kind="stop", bars=k, exit_ms=close_ms)
    if h >= tr["target"]:
        return dict(exit=max(tr["target"], o), kind="target", bars=k, exit_ms=close_ms)
    if k == CAP:
        return dict(exit=c, kind="time", bars=k, exit_ms=close_ms)
    return None


def costs(tr: dict, ex: dict, fund_real: float) -> dict:
    """R before costs, net of the backtest's flat funding (like for like), and net of the funding really paid."""
    risk = tr["entry"] * tr["rf"]
    g = (ex["exit"] - tr["entry"]) / risk
    hours = ex["bars"] * 4
    return dict(gross_r=g, net_r_flat=g - (FEE + FUND_H * hours) / tr["rf"], net_r=g - (FEE + fund_real) / tr["rf"])


# ------------------------------------------------------------------ the book

def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return dict(started_ms=int(time.time() * 1000), equity=START, peak=START, universe={}, open={}, checked={}, free_from={})


def save_state(st: dict):
    D.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st))
    tmp.replace(STATE)


def append_trade(row: dict):
    D.mkdir(parents=True, exist_ok=True)
    new = not TRADES.exists()
    with open(TRADES, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)


def open_gross(st: dict) -> float:
    return sum(tr["notional"] for tr in st["open"].values() if tr["booked"])


def manage(st: dict, coin: str, bars: list, now: int, fetch=None) -> None:
    """Every CLOSED bar after the last one processed, for the coin's open trade; a closed trade is booked and logged."""
    tr = st["open"].get(coin)
    if tr is None:
        return
    for b in bars:
        if b[0] < tr["entry_ms"] + (tr["bars"]) * H4 or b[5] >= now:
            continue
        if b[0] != tr["entry_ms"] + tr["bars"] * H4:
            continue                                                        # a hole in the bars: wait for it to fill rather than skip a bar
        ex = step(tr, b)
        if ex is None:
            continue
        fr = funding(coin, tr["entry_ms"], ex["exit_ms"], fetch)
        cst = costs(tr, ex, fr)
        pnl = tr["risk_usd"] * cst["net_r"] if tr["booked"] else 0.0
        st["equity"] += pnl
        st["peak"] = max(st["peak"], st["equity"])
        row = dict(coin=coin, **{k: tr[k] for k in ("signal_ms", "entry_ms", "entry", "seen_px", "stop", "target", "rf", "booked", "risk_usd", "notional")},
                   exit_ms=ex["exit_ms"], exit=ex["exit"], kind=ex["kind"], bars=ex["bars"], fund_real=fr, pnl_usd=round(pnl, 6),
                   equity_after=round(st["equity"], 6), **{k: round(v, 6) for k, v in cst.items()})
        append_trade(row)
        del st["open"][coin]
        st["free_from"][coin] = ex["exit_ms"] - H4                          # the exit bar's open: a signal on that bar is allowed (cm.pick_trades: i >= exit)
        log(f"EXIT {coin} {ex['kind']} after {ex['bars']} bars: {cst['net_r']:+.2f}R (flat-funding {cst['net_r_flat']:+.2f}R){'' if tr['booked'] else ' (not booked)'}"
            f" -> book ${st['equity']:.2f}")
        return


def try_entry(st: dict, coin: str, bars: list, now: int, uni_of, ind: tuple | None = None) -> None:
    """The bar that just closed, once: a signal opens a trade at the next bar's open. `ind` = (rsi, atr) already computed for these bars (the history
    replay in the tests; the live job computes them here)."""
    closed = [b for b in bars if b[5] < now]
    if len(closed) < 2 or len(closed) == len(bars):
        return                                                              # no forming bar yet: the entry open is not known
    i = len(closed) - 1
    sig_ms = closed[i][0]
    if st["checked"].get(coin, 0) >= sig_ms:
        return
    st["checked"][coin] = sig_ms
    if coin in st["open"] or sig_ms < st["free_from"].get(coin, 0):
        return
    if coin not in uni_of(ts(sig_ms)[:7]):
        return
    tr = signal(bars, i, *(ind or (None, None)))
    if tr is None:
        return
    if now - tr["entry_ms"] > LATE_MS:
        log(f"LATE {coin}: signal on {ts(sig_ms)} seen {(now - tr['entry_ms']) / MIN:.0f} min into the entry bar - not taken")
        return
    eq = st["equity"]
    risk_usd = RISK * eq
    notional = risk_usd / tr["rf"]
    booked = notional >= MIN_POS and open_gross(st) + notional <= MAX_GROSS * eq
    tr.update(seen_px=bars[-1][4], risk_usd=round(risk_usd, 6), notional=round(notional, 6), booked=bool(booked))
    st["open"][coin] = tr
    log(f"ENTRY {coin} long at {tr['entry']:.6g} (seen {tr['seen_px']:.6g}), stop {tr['stop']:.6g}, target {tr['target']:.6g}, risk ${risk_usd:.2f}, "
        f"notional ${notional:.2f}{'' if booked else ' - NOT BOOKED (under $5 or over the 10x cap)'}")


def run(now: int | None = None, fetch=None) -> dict:
    now = now or int(time.time() * 1000)
    st = load_state()
    month = ts(now)[:7]
    try:
        uni = universe(st, month, fetch)
    except Exception as e:  # noqa: BLE001 - no universe this run: still manage the open trades, take no new ones
        log(f"universe {month} unavailable ({type(e).__name__}: {str(e)[:80]}) - exits only this run")
        uni = []

    def uni_of(m):
        if m == month:
            return uni
        try:
            return universe(st, m, fetch)
        except Exception:  # noqa: BLE001
            return []
    coins = sorted(set(uni) | set(st["open"]))
    for coin in coins:
        try:
            bars = bars4h(coin, fetch)
        except Exception as e:  # noqa: BLE001 - one coin failing must not stop the rest
            log(f"{coin}: no bars ({type(e).__name__})")
            continue
        manage(st, coin, bars, now, fetch)
        try_entry(st, coin, bars, now, uni_of)
        if fetch is None:
            time.sleep(0.05)
    save_state(st)
    log(f"run: {len(coins)} coins, {len(st['open'])} open (${open_gross(st):.2f} notional), book ${st['equity']:.2f}")
    return st


# ------------------------------------------------------------------ the record

def read_trades() -> list:
    if not TRADES.exists():
        return []
    return list(csv.DictReader(open(TRADES, newline="", encoding="utf-8")))


def verdict(rows: list, equity: float, today: str) -> str:
    n = len(rows)
    m = sum(float(r["net_r"]) for r in rows) / n if n else float("nan")
    if today >= KILL_DATE and today < VERDICT_DATE and n >= KILL_MIN and m < KILL_R:
        return f"DEAD - the kill line ({n} trades, mean {m:+.3f}R < {KILL_R})"
    if today >= VERDICT_DATE:
        if m < DEAD_R:
            return f"DEAD ({n} trades, mean {m:+.3f}R < {DEAD_R})"
        if m >= HELD_R and equity > START:
            return f"HELD UP ({n} trades, mean {m:+.3f}R >= {HELD_R}, book ${equity:.2f})"
        return f"CANNOT TELL ({n} trades, mean {m:+.3f}R) - runs on to {EXTEND_DATE} under the same lines"
    return f"NOT YET - {n} resolved trades; kill check {KILL_DATE}, verdict {VERDICT_DATE}"


def status() -> str:
    st = load_state()
    rows = read_trades()
    n = len(rows)
    L = [f"RSI-80 MOMENTUM PAPER BOOK (registered {REGISTERED_UTC}; since {ts(st['started_ms'])} UTC): book ${st['equity']:.2f} from ${START:.0f}, "
         f"{len(st['open'])} open, {n} resolved"]
    if n:
        mr = sum(float(r["net_r"]) for r in rows) / n
        mf = sum(float(r["net_r_flat"]) for r in rows) / n
        wins = sum(1 for r in rows if float(r["net_r"]) > 0)
        slip = [abs(float(r["seen_px"]) / float(r["entry"]) - 1) for r in rows if float(r["entry"]) > 0]
        exits = ", ".join("%s %d" % (k, sum(1 for r in rows if r["kind"] == k)) for k in ("stop", "target", "time"))     # no nested f-strings: the VM runs Python 3.10
        L.append(f"  mean R a trade {mr:+.3f} (real funding) / {mf:+.3f} (the backtest's flat funding); {wins} of {n} positive; "
                 f"exits {exits}; the price seen vs the bar open booked: mean {sum(slip) / len(slip) * 100:.2f}% apart")
    L.append(f"  backtest bands for comparison: 12 weeks 10th -0.17 / median +0.06 (unseen coins); 22 weeks 10th -0.11 / median +0.07")
    L.append(f"  VERDICT: {verdict(rows, st['equity'], datetime.now(timezone.utc).strftime('%Y-%m-%d'))}")
    for c, tr in sorted(st["open"].items()):
        L.append(f"  open {c}: in {ts(tr['entry_ms'])} at {tr['entry']:.6g}, stop {tr['stop']:.6g}, target {tr['target']:.6g}, bar {tr['bars']} of {CAP}"
                 f"{'' if tr['booked'] else ' (not booked)'}")
    return "\n".join(L)


if __name__ == "__main__":
    if "--status" in sys.argv:
        print(status())
    else:
        run()

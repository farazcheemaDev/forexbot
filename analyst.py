"""THE ANALYST DESK - chart rules that PREDICT first, are scored on real candles, and trade a separate paper book (2026-10-27).

THE USER (2026-10-27): "show on the dashboard in real time the support / resistance and the expected movement; the bot first predicts,
then records how many times it was right and how much it would have made on paper - a separate book".
WHAT THIS IS: an automatic version of desk.py. Hourly it reads the candles of a watchlist, draws the levels a chart-reader would
(clustered support / resistance, a Fibonacci retracement of the last swing, unfilled fair value gaps), and applies THREE fixed rules
written below. A rule that fires logs a CALL (side, entry now, stop, target, horizon) together with the odds a random entry with
the same stop % / target % / hours would have - BEFORE its outcome is known. Calls are scored on public 1-minute bars with desk.py's
pessimistic rules, and each is taken by a separate PAPER book of $300 (risk 0.5% of the book per call, sized on the equity at
entry, fee 12bp, gross capped at 3x). It is NOT part of main or fresh (those are the machines being judged), places no orders,
uses no keys, and is not advice.
THE HONEST PRIOR: the repo has tested these ideas for months (doc 02; ict_fvg.py, odds_now.py) and none shows an edge after costs.
This is a forward measurement of the user's idea, not a bet that it works. The dashboard shows each call next to its random baseline.

THE LEVELS (all from CLOSED bars of Binance futures, public data)
  support / resistance  4h fractal pivots (3 bars each side, last 300 bars) and daily pivots (2 each side, last 200 bars), highs and lows
                        pooled, clustered within 0.5 x ATR(4h); a level needs >= 2 touches; "strong" = >= 3.
  fibonacci             the last 60 4h bars' highest high and lowest low; the one that came LATER is the end of the swing; retracements
                        38.2 / 50 / 61.8 / 78.6 / 88.6% of it. A swing under 3 x ATR(4h) is ignored.
  fair value gaps       1h three-candle gaps (strong impulse >= 1 ATR, gap >= 0.25 ATR) from the last 72 bars that no later bar has traded back through.
  typical move          the standard deviation of the last 14 daily returns - context, NOT a forecast.
THE THREE RULES (long shown; short mirrors). All on the last CLOSED 1h bar, entry = the price when the hour's job runs
  SR   bounce: a strong support (>= 3 touches) within 0.25 ATR(1h) above / up to 1 ATR below the bar's low, the bar closes above it
       with a lower wick >= 50% of its range. Stop = the lower of the low and the level, less 0.5 ATR. Target = the nearest resistance. 24h.
  FIB  pullback: the 4h swing is up and price has retraced 50-78.6% of it, and the last 1h bar closed up. Stop = the 88.6% level less 0.25 ATR.
       Target = the swing high. 48h.
  SMC  sweep and reclaim: the bar's low is under the lowest low of the 24 bars before it, it closes back above that low and closes up.
       Stop = the bar's low less 0.25 ATR. Target = the 24-bar high if that is >= 1.5R away, else 2R. 24h.
  Every call needs reward:risk >= 1.5 and a stop of 0.3-4 ATR(1h). One open call per symbol and rule; 6 hours of cooldown after one ends.
SCORING  desk.resolve (market fill, a bar touching both stop and target = loss, a gap exits at the open, expiry at the horizon's close).
PAPER BOOK  $300; each call risks 0.5% of the BOOKED equity at entry; notional = risk / stop %; calls that would push open notional past
  3x equity are still scored as predictions but take no paper money ('not booked'). Equity = booked P&L + open calls at live prices.

REGISTERED BEFORE THE FIRST CALL (2026-10-27)
  A1  After the first 30 resolved calls the hit rate (target first) does not beat the average random-entry baseline of those calls at
      one-sided p < 0.05 (the rules carry no edge at 12bp).
  A2  The paper book is below its $300 start after its first 100 resolved calls and the average R after fees is negative.
  A3  The three rules are not distinguishable: no rule beats its own baseline at p < 0.05 with 30 resolved calls.
  A4  The watchlist produces 5 to 40 calls a week.
WHAT IF YOU TRADED THESE CALLS WITH LEVERAGE (added 2026-10-27, the user: "10x 20x 30x, capital 20 / 50 / 100 / 300 - how would that result in")
  The same calls, taken by a trader who puts the WHOLE account on each one at 10x / 20x / 30x (isolated margin, one position at a time: a call that
  appears while one is open is skipped), the stop and target as logged, 12bp of the NOTIONAL as the round-trip fee (= 12bp x leverage of the account).
  Liquidation = the price moving 1/leverage - 0.5% against the position at any time before the exit (the call's worst move, 'mae', read from the
  same 1-minute bars): the whole margin is lost. Capital only scales dollars (a percentage result is the same on $20 and $300); the one thing it can
  change is the $5 minimum order. `grid(rows)` = 4 capitals x 3 leverages; `backtest/analyst_replay.py` runs the same rules over history on 1h bars.
  A5  On the history replay no rule beats its break-even hit rate on BOTH halves after 12bp (1h bars, a bar touching both = loss).
  A6  All-in with one position at a time, the median 12-month outcome resampled from the replay's calls is under the start at 10x, 20x and 30x, and
      the chance of losing 90% of the account is >= 20% at 30x and rises with leverage.
  A7  Capital changes dollars, not percentages: $20 and $300 end at the same multiple (the $5 minimum does not bind all-in).
  A8  More leverage raises the best case and lowers the median (the pattern of scalp_1m.py --kelly: leverage cannot rescue a thin edge).
REVIEW  at 100 resolved calls or 2027-01-31, whichever comes first: if the average R after fees is <= 0 or p >= 0.05 the book is retired
  (kept as a record); it never trades real money. Doc 22's freeze is respected: nothing here touches a bot; the book is the user's
  explicit override (2026-10-27), like the crowd book.

    python analyst.py            one cycle: score open calls, redraw the levels, log new calls
    python analyst.py --status   the record
"""
from __future__ import annotations

import csv
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import desk

ROOT = Path(__file__).resolve().parent
D = ROOT / "logs" / "analyst"
STATE, CALLS, LEVELS, MARKS = D / "state.json", D / "calls.csv", D / "levels.json", D / "marks.csv"
WATCH = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "XAUUSDT", "QQQUSDT"]
START = 300.0
RISK_PCT = 0.5
MAX_GROSS = 3.0
HOURS = dict(SR=24, FIB=48, SMC=24)
COOLDOWN_H = 6
MIN_RR = 1.5
MIN_RESOLVED = 30
H1, H4, D1 = 3_600_000, 14_400_000, 86_400_000
COLS = desk.COLS + ["why", "nobook", "booked", "pnl_usd", "mae"]
CAPITALS = (20, 50, 100, 300)
LEVERAGES = (10, 20, 30)


def log(m: str):
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} {m}", flush=True)


# ------------------------------------------------------------------ the chart

def closed(bars: list, width_ms: int, now_ms: int) -> list:
    """Drop the bar still forming."""
    return [b for b in bars if b[0] + width_ms <= now_ms]


def atr(bars: list, n: int = 14) -> float:
    tr = [max(b[2] - b[3], abs(b[2] - bars[i][4]), abs(b[3] - bars[i][4])) for i, b in enumerate(bars[1:])]
    t = tr[-n:]
    return sum(t) / len(t)


def pivots(bars: list, k: int) -> list:
    """Fractal highs and lows: a bar whose high (low) is strictly beyond the k bars on each side. [(price, t)]"""
    out = []
    for i in range(k, len(bars) - k):
        h, l = bars[i][2], bars[i][3]
        nb = [j for j in range(i - k, i + k + 1) if j != i]
        if all(h > bars[j][2] for j in nb):
            out.append((h, bars[i][0]))
        if all(l < bars[j][3] for j in nb):
            out.append((l, bars[i][0]))
    return out


def cluster(points: list, tol: float) -> list:
    out = []
    for p, t in sorted(points):
        if out and abs(p - out[-1]["sum"] / out[-1]["touches"]) <= tol:
            c = out[-1]
            c["sum"] += p
            c["touches"] += 1
            c["last_t"] = max(c["last_t"], t)
        else:
            out.append(dict(sum=p, touches=1, last_t=t))
    return [dict(price=c["sum"] / c["touches"], touches=c["touches"], last_t=c["last_t"]) for c in out]


def sr_levels(h4c: list, d1c: list) -> list:
    pts = pivots(h4c[-300:], 3) + pivots(d1c[-200:], 2)
    return [lv for lv in cluster(pts, 0.5 * atr(h4c)) if lv["touches"] >= 2]


def fib_swing(h4c: list, look: int = 60) -> dict | None:
    seg = h4c[-look:]
    hi_i = max(range(len(seg)), key=lambda i: seg[i][2])
    lo_i = min(range(len(seg)), key=lambda i: seg[i][3])
    hi, lo = seg[hi_i][2], seg[lo_i][3]
    rng = hi - lo
    if rng < 3 * atr(h4c):
        return None
    up = lo_i < hi_i                                             # the low came first: an up swing, price retraces DOWN from the high
    lv = {r: (hi - r * rng if up else lo + r * rng) for r in (0.382, 0.5, 0.618, 0.786, 0.886)}
    return dict(trend="up" if up else "down", hi=hi, lo=lo, rng=rng, levels=lv)


def fvg_zones(h1c: list, look: int = 72) -> list:
    seg, a, out = h1c[-look:], atr(h1c), []
    for i in range(2, len(seg)):
        c1, c2, c3 = seg[i - 2], seg[i - 1], seg[i]
        if c3[3] > c1[2] and c2[4] > c2[1] and c2[4] - c2[1] >= a and c3[3] - c1[2] >= 0.25 * a:
            if all(b[3] > c1[2] for b in seg[i + 1:]):
                out.append(dict(side="bull", lo=c1[2], hi=c3[3]))
        if c3[2] < c1[3] and c2[4] < c2[1] and c2[1] - c2[4] >= a and c1[3] - c3[2] >= 0.25 * a:
            if all(b[2] < c1[3] for b in seg[i + 1:]):
                out.append(dict(side="bear", lo=c3[2], hi=c1[3]))
    return out


def daily_sd(d1c: list, n: int = 14) -> float:
    r = [math.log(d1c[i][4] / d1c[i - 1][4]) for i in range(len(d1c) - n, len(d1c))]
    m = sum(r) / len(r)
    return math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1))


# ------------------------------------------------------------------ the three rules

def build(sym: str, method: str, side: str, price: float, stop: float, target: float | None, a1: float, why: str) -> dict | None:
    if target is None or desk.geometry_ok(side, price, stop, target):
        return None
    risk, reward = abs(price - stop), abs(target - price)
    if reward / risk < MIN_RR or not (0.3 * a1 <= risk <= 4 * a1):
        return None
    return dict(symbol=sym, method=method, side=side, entry=price, stop=stop, target=target, hours=HOURS[method], why=why)


def signals(sym: str, h1c: list, h4c: list, d1c: list, price: float) -> list:
    out = []
    a1 = atr(h1c)
    o, h, l, c = h1c[-1][1:5]
    rng = max(h - l, 1e-12)
    lv = sr_levels(h4c, d1c)
    sup = sorted([x for x in lv if x["price"] < price], key=lambda x: -x["price"])
    res = sorted([x for x in lv if x["price"] > price], key=lambda x: x["price"])
    # SR - a bounce / rejection at a strong level
    for S in sup[:2]:
        if S["touches"] >= 3 and S["price"] - 1.0 * a1 <= l <= S["price"] + 0.25 * a1 and c > S["price"] and (min(o, c) - l) / rng >= 0.5:
            out.append(build(sym, "SR", "long", price, min(l, S["price"]) - 0.5 * a1, res[0]["price"] if res else None, a1,
                             f"bounce at the {S['touches']}-touch support {S['price']:.6g}"))
    for R in res[:2]:
        if R["touches"] >= 3 and R["price"] - 0.25 * a1 <= h <= R["price"] + 1.0 * a1 and c < R["price"] and (h - max(o, c)) / rng >= 0.5:
            out.append(build(sym, "SR", "short", price, max(h, R["price"]) + 0.5 * a1, sup[0]["price"] if sup else None, a1,
                             f"rejection at the {R['touches']}-touch resistance {R['price']:.6g}"))
    # FIB - a pullback into 50-78.6% of the last 4h swing, the last 1h bar closing with the swing
    sw = fib_swing(h4c)
    if sw:
        if sw["trend"] == "up":
            ret = (sw["hi"] - price) / sw["rng"]
            if 0.5 <= ret <= 0.786 and c > o:
                out.append(build(sym, "FIB", "long", price, sw["levels"][0.886] - 0.25 * a1, sw["hi"], a1,
                                 f"pullback {ret * 100:.0f}% into the up swing {sw['lo']:.6g}-{sw['hi']:.6g}"))
        else:
            ret = (price - sw["lo"]) / sw["rng"]
            if 0.5 <= ret <= 0.786 and c < o:
                out.append(build(sym, "FIB", "short", price, sw["levels"][0.886] + 0.25 * a1, sw["lo"], a1,
                                 f"pullback {ret * 100:.0f}% into the down swing {sw['hi']:.6g}-{sw['lo']:.6g}"))
    # SMC - a liquidity sweep of the last 24 bars' extreme, reclaimed on the same bar
    prior = h1c[-25:-1]
    pl, ph = min(b[3] for b in prior), max(b[2] for b in prior)
    if l < pl and c > pl and c > o:
        stop = l - 0.25 * a1
        tgt = ph if (ph - price) / max(price - stop, 1e-12) >= MIN_RR else price + 2 * (price - stop)
        out.append(build(sym, "SMC", "long", price, stop, tgt, a1, f"swept the 24-bar low {pl:.6g} and reclaimed it"))
    if h > ph and c < ph and c < o:
        stop = h + 0.25 * a1
        tgt = pl if (price - pl) / max(stop - price, 1e-12) >= MIN_RR else price - 2 * (stop - price)
        out.append(build(sym, "SMC", "short", price, stop, tgt, a1, f"swept the 24-bar high {ph:.6g} and reclaimed it"))
    return [s for s in out if s]


def describe(sym: str, h1c: list, h4c: list, d1c: list, price: float) -> dict:
    """What the dashboard draws for one symbol: the levels, the swing, the gaps, the typical move."""
    lv = sr_levels(h4c, d1c)
    sup = sorted([x for x in lv if x["price"] < price], key=lambda x: -x["price"])[:3]
    res = sorted([x for x in lv if x["price"] > price], key=lambda x: x["price"])[:3]
    sw = fib_swing(h4c)
    z = fvg_zones(h1c)
    zn = sorted(z, key=lambda g: min(abs(g["lo"] - price), abs(g["hi"] - price)))[:2]
    sd = daily_sd(d1c)
    return dict(symbol=sym, price=price, atr1_pct=atr(h1c) / price, typical_move_pct=sd,
                support=[dict(price=round(x["price"], 8), touches=x["touches"]) for x in sup],
                resistance=[dict(price=round(x["price"], 8), touches=x["touches"]) for x in res],
                fib=None if not sw else dict(trend=sw["trend"], hi=sw["hi"], lo=sw["lo"], levels={str(k): v for k, v in sw["levels"].items()},
                                              retraced=((sw["hi"] - price) / sw["rng"]) if sw["trend"] == "up" else ((price - sw["lo"]) / sw["rng"])),
                gaps=[dict(side=g["side"], lo=g["lo"], hi=g["hi"]) for g in zn])


# ------------------------------------------------------------------ calls and the paper book

def load_calls() -> list:
    if not CALLS.exists():
        return []
    with open(CALLS, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_calls(rows: list) -> None:
    D.mkdir(parents=True, exist_ok=True)
    tmp = CALLS.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COLS})
    tmp.replace(CALLS)


def load_state(now: int) -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return dict(started=desk.ts(now), started_ms=now, start=START, equity=START, peak=START)


def save_state(st: dict) -> None:
    D.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st))
    tmp.replace(STATE)


def allowed(rows: list, sym: str, method: str, now: int) -> bool:
    for r in rows:
        if r["symbol"] == sym and r["method"] == method:
            if r["status"] == "open":
                return False
            end = r.get("exit_ms") or r["expires_ms"]
            if now - int(float(end)) < COOLDOWN_H * H1:
                return False
    return True


def new_call(st: dict, rows: list, sig: dict, h1c: list, now: int, fetch=desk.klines, bcache: dict | None = None) -> dict:
    eq = st["equity"]
    p = desk.plan_numbers(sig["side"], sig["entry"], sig["stop"], sig["target"], eq, RISK_PCT)
    base = desk.minute_baseline(sig["symbol"], sig["side"], p["stop_pct"], p["target_pct"], sig["hours"], now, fetch, h1c[-500:], bcache)     # on the scoring grid
    open_gross = sum(float(r["notional"]) for r in rows if r["status"] == "open" and r.get("nobook") != "1" and r.get("nobook") != 1)
    nobook = open_gross + p["notional"] > MAX_GROSS * eq
    return dict(id=len(rows) + 1, made_utc=desk.ts(now), made_ms=now, symbol=sig["symbol"], side=sig["side"], mode="market", entry=sig["entry"],
                stop=sig["stop"], target=sig["target"], expires_ms=now + sig["hours"] * H1, method=sig["method"], note=sig["why"], equity=round(eq, 4),
                risk_pct=RISK_PCT, risk_usd=round(p["risk_usd"], 4), qty=p["qty"], notional=round(p["notional"], 4), lev=round(p["lev"], 3),
                stop_pct=round(p["stop_pct"], 6), target_pct=round(p["target_pct"], 6), rr=round(p["rr"], 4), be_p=round(p["be_p"], 4),
                base_p=round(base["p_tp"], 4), status="open", why=sig["why"], nobook=int(nobook), booked=0)


def mae_of(call: dict, bars: list) -> float:
    """The worst move AGAINST the position, as a share of the entry, from the fill to the exit (to now while the call is open)."""
    entry = float(call["entry"])
    end = float(call["exit_ms"]) if call.get("exit_ms") not in (None, "") else float("inf")
    seg = [b for b in bars if b[0] <= end]
    if not seg:
        return 0.0
    if call["side"] == "long":
        return max(0.0, (entry - min(b[3] for b in seg)) / entry)
    return max(0.0, (max(b[2] for b in seg) - entry) / entry)


def score_open(st: dict, rows: list, now: int, fetch=desk.klines) -> int:
    n = 0
    for i, r in enumerate(rows):
        if r["status"] != "open":
            continue
        made, exp = int(float(r["made_ms"])), int(float(r["expires_ms"]))
        start = made // 60_000 * 60_000 + 60_000
        bars = desk.bars_between(r["symbol"], start, min(now, exp + 60_000), fetch)
        new = desk.resolve(r, bars, now)
        new["mae"] = round(max(mae_of(new, bars), float(r.get("mae") or 0.0)), 6)
        if new["status"] in ("WIN", "LOSS", "EXPIRED"):
            n += 1
            if str(new.get("nobook")) not in ("1",):
                pnl = float(new["r_net"]) * float(new["risk_usd"])
                st["equity"] += pnl
                st["peak"] = max(st["peak"], st["equity"])
                new["booked"], new["pnl_usd"] = 1, round(pnl, 4)
        rows[i] = new
    return n


def mark_day(now: int, equity: float) -> None:
    day = datetime.fromtimestamp(now / 1000, timezone.utc).strftime("%Y-%m-%d")
    D.mkdir(parents=True, exist_ok=True)
    have = set()
    if MARKS.exists():
        have = {r["day"] for r in csv.DictReader(open(MARKS, newline="", encoding="utf-8"))}
    if day in have:
        return
    new = not MARKS.exists()
    with open(MARKS, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["day", "equity"])
        w.writerow([day, round(equity, 4)])


def cycle(now: int | None = None, fetch=desk.klines, watch=WATCH) -> dict:
    now = now or desk.now_ms()
    st = load_state(now)
    rows = load_calls()
    resolved = score_open(st, rows, now, fetch)
    levels, fired, bcache = {}, 0, {}
    for sym in watch:
        try:
            h1 = fetch(sym, "1h", None, None, 500)
            h4 = fetch(sym, "4h", None, None, 300)
            d1 = fetch(sym, "1d", None, None, 200)
        except Exception as e:  # noqa: BLE001 - one symbol failing must not stop the rest
            log(f"{sym}: no candles ({type(e).__name__}: {str(e)[:80]})")
            continue
        h1c, h4c, d1c = closed(h1, H1, now), closed(h4, H4, now), closed(d1, D1, now)
        if len(h1c) < 100 or len(h4c) < 80 or len(d1c) < 40:
            continue
        price = h1[-1][4]
        levels[sym] = describe(sym, h1c, h4c, d1c, price)
        for sig in signals(sym, h1c, h4c, d1c, price):
            if allowed(rows, sym, sig["method"], now):
                rows.append(new_call(st, rows, sig, h1c, now, fetch, bcache))
                fired += 1
                r = rows[-1]
                log(f"CALL #{r['id']} {sym} {r['side']} [{r['method']}] {r['note']}: entry {r['entry']:.6g} stop {r['stop']:.6g} target {r['target']:.6g} "
                    f"(random baseline {float(r['base_p']) * 100:.0f}%){' - NOT BOOKED (gross cap)' if r['nobook'] else ''}")
    D.mkdir(parents=True, exist_ok=True)
    LEVELS.write_text(json.dumps(dict(t=now, made=desk.ts(now), symbols=levels), separators=(",", ":")))
    save_calls(rows)
    save_state(st)
    mark_day(now, st["equity"])
    log(f"cycle: {resolved} resolved, {fired} new call(s), {sum(r['status'] == 'open' for r in rows)} open, book ${st['equity']:.2f}")
    return st


def stats(rows: list) -> dict:
    done = [r for r in rows if r["status"] in ("WIN", "LOSS", "EXPIRED")]
    out = dict(calls=len(rows), open=sum(r["status"] == "open" for r in rows), resolved=len(done), wins=sum(r["status"] == "WIN" for r in done),
               losses=sum(r["status"] == "LOSS" for r in done), expired=sum(r["status"] == "EXPIRED" for r in done))
    if done:
        rs = [float(r["r_net"]) for r in done]
        out.update(avg_r=sum(rs) / len(rs), hit=out["wins"] / len(done), baseline=sum(float(r["base_p"]) for r in done) / len(done),
                   breakeven=sum(float(r["be_p"]) for r in done) / len(done), pnl=sum(float(r["pnl_usd"] or 0) for r in done))
        var = sum(float(r["base_p"]) * (1 - float(r["base_p"])) for r in done)
        z = (out["wins"] - sum(float(r["base_p"]) for r in done)) / math.sqrt(var) if var > 0 else 0.0
        out["p"] = 1 - 0.5 * (1 + math.erf(z / math.sqrt(2)))
        out["verdict"] = ("NOT ENOUGH CALLS" if len(done) < MIN_RESOLVED else "EDGE" if (out["avg_r"] > 0 and out["p"] < 0.05) else "NO EDGE PROVEN")
        by = {}
        for m in ("SR", "FIB", "SMC"):
            g = [r for r in done if r["method"] == m]
            if g:
                by[m] = dict(n=len(g), wins=sum(r["status"] == "WIN" for r in g), avg_r=sum(float(r["r_net"]) for r in g) / len(g),
                             baseline=sum(float(r["base_p"]) for r in g) / len(g), pnl=sum(float(r["pnl_usd"] or 0) for r in g))
        out["by_method"] = by
    return out


def _f(x, default: float = 0.0) -> float:
    try:
        v = float(x)
        return v if v == v else default
    except (TypeError, ValueError):
        return default


def leveraged_result(r: dict, lev: float) -> tuple:
    """(the account's result as a fraction, liquidated?) of one resolved call taken with the WHOLE account at `lev`x isolated margin."""
    side = 1 if r["side"] == "long" else -1
    entry, px = _f(r["entry"]), _f(r["exit_price"])
    gross = side * (px / entry - 1)
    mae = _f(r.get("mae"), -1.0)
    if mae < 0:                                                  # no worst-move record: a stop-out moved at least the stop against it
        mae = _f(r.get("stop_pct")) if r["status"] == "LOSS" else 0.0
    if mae >= 1.0 / lev - desk.MMR:                              # the exchange closes it before the stop or the target: the margin is gone
        return -1.0, True
    return max(-1.0, lev * (gross - desk.FEE)), False


def scenario(rows: list, capital: float, lev: float) -> dict:
    """The calls as one trader would have taken them: the whole account at `lev`x on each call, one position at a time, calls in the order made.
    A call made while the previous one is still open is skipped; so is any call once the account is too small for the $5 minimum order. Calls made
    after the first still-open call are left out (their place in the sequence depends on it): `pending` counts them."""
    open_made = [_f(r["made_ms"]) for r in rows if r["status"] == "open"]
    horizon = min(open_made) if open_made else float("inf")
    done = sorted((r for r in rows if r["status"] in ("WIN", "LOSS", "EXPIRED")), key=lambda r: _f(r["made_ms"]))
    eq, peak, busy = float(capital), float(capital), 0.0
    out = dict(capital=capital, lev=lev, taken=0, wins=0, losses=0, liquidated=0, skipped_busy=0, skipped_small=0, pending=0, worst=0.0, maxdd=0.0)
    for r in done:
        made = _f(r["made_ms"])
        if made >= horizon:
            out["pending"] += 1
            continue
        if made < busy:
            out["skipped_busy"] += 1
            continue
        if eq * lev < desk.MIN_NOTIONAL:
            out["skipped_small"] += 1
            continue
        frac, liq = leveraged_result(r, lev)
        eq *= 1.0 + frac
        busy = _f(r.get("exit_ms"))
        out["taken"] += 1
        out["wins"] += frac > 0
        out["losses"] += frac <= 0
        out["liquidated"] += liq
        out["worst"] = min(out["worst"], frac)
        peak = max(peak, eq)
        out["maxdd"] = max(out["maxdd"], 1.0 - eq / peak)
    out.update(equity=eq, ret=eq / capital - 1.0, ruined=eq * lev < desk.MIN_NOTIONAL)
    return out


def grid(rows: list, capitals=CAPITALS, levs=LEVERAGES) -> list:
    return [scenario(rows, c, L) for c in capitals for L in levs]


def status() -> str:
    rows = load_calls()
    st = load_state(desk.now_ms())
    s = stats(rows)
    L = [f"ANALYST DESK (paper), started {st['started']} UTC, ${st['start']:.0f} -> booked ${st['equity']:.2f} ({(st['equity'] / st['start'] - 1) * 100:+.2f}%)",
         f"  calls {s['calls']}: open {s['open']}, resolved {s['resolved']} (wins {s['wins']}, losses {s['losses']}, expired {s['expired']})"]
    if s["resolved"]:
        L.append(f"  hit rate {s['hit'] * 100:.0f}% vs random baseline {s['baseline'] * 100:.0f}% vs break-even {s['breakeven'] * 100:.0f}%; average {s['avg_r']:+.2f}R after fees; "
                 f"book P&L ${s['pnl']:+.2f}; one-sided p {s['p']:.3f}; {s['verdict']} (needs {MIN_RESOLVED})")
        for m, g in s.get("by_method", {}).items():
            L.append(f"    {m:<4} n {g['n']:3d}  hit {g['wins'] / g['n'] * 100:3.0f}% vs baseline {g['baseline'] * 100:3.0f}%  avg {g['avg_r']:+.2f}R  P&L ${g['pnl']:+.2f}")
        L.append("  what if the whole account went on each call (one at a time), starting $100:")
        for sc in (scenario(rows, 100, x) for x in LEVERAGES):
            L.append(f"    {sc['lev']:>2.0f}x  ${sc['equity']:8.2f} ({sc['ret'] * 100:+6.1f}%)  taken {sc['taken']}, liquidated {sc['liquidated']}, skipped (busy) {sc['skipped_busy']}, "
                     f"worst {sc['worst'] * 100:+.0f}%, deepest fall {sc['maxdd'] * 100:.0f}%")
    return "\n".join(L)


if __name__ == "__main__":
    if "--status" in sys.argv:
        print(status())
    else:
        cycle()

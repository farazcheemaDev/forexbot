"""THE DESK - a plan for a manual trade, logged BEFORE the outcome, scored on real 1-minute candles (2026-10-27).

THE USER (2026-10-27): "can we sit and analyse the charts - support and resistance, Fibonacci, smart money concepts, whatever -
and when it clicks open a trade, with everything calculated: where the loss is cut and where profit is taken?"
THE HONEST PART: the repo has tested support / resistance, Fibonacci, fair value gaps, sweeps and the indicator toolkit many times
(doc 02; backtest/ict_fvg.py, odds_now.py, doge_live.py) and none shows an edge after costs on its own. A plan with its levels fixed in
advance is still worth having - it forces the arithmetic before the click - and whether OUR chart reading works can only be
measured. This file does both: it prices a plan, logs it as a PAPER call, and scores it later. It places no orders, uses no keys,
reads only public Binance futures data (crypto, and the TradFi perps: XAUUSDT, XAGUSDT, QQQUSDT ... - forex majors are not on
Binance; they need the PC's MT5 and are not wired here). Nothing it prints is advice to trade; a real order is the user's own
act, outside this repo, and the bots' ALLOW_REAL gates are untouched.

WHAT A PLAN IS
  python desk.py plan SYMBOL long|short ENTRY STOP TARGET [--hours 48] [--equity 221] [--risk-pct 1] [--method sr|fib|smc|other] [--note "..."]
      ENTRY = a price (a LIMIT that must be touched before the call expires) or 'mkt' (the live price now).
      It prints: stop and target as % of price, reward:risk, the fee in R units, the win rate needed to break even AFTER fees, the position
      size for the risk you chose, the leverage that needs, the liquidation distance against the stop, how many ATRs the stop is, and
      the BASELINE - how often a random entry with the SAME stop % and target % over the SAME hours hit the target first on the coin's
      last ~21 days. A call is only interesting if the reader beats that number, not 50%.
  python desk.py score      resolve open calls on the 1-minute bars after they were made
  python desk.py stats      the record: wins, losses, average R after fees, against the baselines logged with each call
  python desk.py list

HOW A CALL IS SCORED (pessimistic, fixed here before any call is logged)
  fill      market: at the live price when made. limit: the first 1m bar whose range touches ENTRY (long: low <= entry), filled AT entry;
            never touched before expiry = NOFILL (not counted as a trade). Bars start at the NEXT full minute after the call.
  after     the fill bar itself counts: if it also reaches the stop it is a LOSS. Then every 1m bar: stop touched = LOSS, a bar that gaps
            through the stop exits at its OPEN; target touched = WIN at the target; a bar touching BOTH = LOSS.
  expiry    filled but unresolved at expiry: closed at the last bar's close (EXPIRED).
  cost      12bp round trip (Bitget's taker, charged on every filled call); funding ignored (calls are short).
  R         the net result divided by the stop distance, so -1.0 = the stop and +reward:risk = the target, each less the fee in R.
VERDICT RULE  at least 30 filled, resolved calls; then 'EDGE' only if the average R is positive AND the win rate beats the average
  baseline of those calls with a one-sided p < 0.05. Below 30 it says NOT ENOUGH CALLS and nothing else. Methods (sr / fib / smc / other)
  are compared only once each has 30.

REGISTERED BEFORE THE FIRST CALL (2026-10-27)
  D1  The first 30 filled calls do not clear the verdict rule (retail chart levels carry no edge after costs - doc 02).
  D2  The average R after fees of those calls is below zero (the fee alone is ~0.1-0.4R at typical stops).
  D3  The win rate of calls with a reward:risk of 2 or more is below the break-even rate for their geometry.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
D = ROOT / "logs" / "desk"
CALLS = D / "calls.csv"
FAPI = "https://fapi.binance.com"
FEE = 12e-4                     # round trip, as a share of the position
MMR = 0.005                     # maintenance margin used for the liquidation estimate
MIN_NOTIONAL = 5.0              # Bitget's minimum order value, USD
MIN_CALLS = 30
COLS = ["id", "made_utc", "made_ms", "symbol", "side", "mode", "entry", "stop", "target", "expires_ms", "method", "note", "equity",
        "risk_pct", "risk_usd", "qty", "notional", "lev", "stop_pct", "target_pct", "rr", "be_p", "base_p",
        "status", "filled_ms", "exit_ms", "exit_price", "r_net"]


def get(path: str):
    for k in range(3):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(FAPI + path, headers={"User-Agent": "Mozilla/5.0"}), timeout=30))
        except Exception:  # noqa: BLE001
            if k == 2:
                raise
            time.sleep(1 + 2 * k)


def klines(symbol: str, interval: str, start_ms: int | None = None, end_ms: int | None = None, limit: int = 1500):
    q = f"/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    if start_ms is not None:
        q += f"&startTime={int(start_ms)}"
    if end_ms is not None:
        q += f"&endTime={int(end_ms)}"
    return [(int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4])) for k in get(q)]       # (t, o, h, l, c)


def bars_between(symbol: str, start_ms: int, end_ms: int, fetch=klines):
    """Every 1-minute bar with open time in [start_ms, end_ms], paged."""
    out, t = [], start_ms
    while t <= end_ms:
        page = fetch(symbol, "1m", t, end_ms, 1500)
        if not page:
            break
        out += page
        t = page[-1][0] + 60_000
        if len(page) < 1500:
            break
    return [b for b in out if b[0] <= end_ms]


# ------------------------------------------------------------------ the arithmetic of a plan

def geometry_ok(side: str, entry: float, stop: float, target: float) -> str | None:
    if side == "long" and not (stop < entry < target):
        return "a long needs stop < entry < target"
    if side == "short" and not (target < entry < stop):
        return "a short needs target < entry < stop"
    return None


def plan_numbers(side: str, entry: float, stop: float, target: float, equity: float, risk_pct: float) -> dict:
    stop_pct = abs(entry - stop) / entry
    target_pct = abs(target - entry) / entry
    rr = target_pct / stop_pct
    fee_r = FEE / stop_pct
    win_r, loss_r = rr - fee_r, 1.0 + fee_r                        # net results in R of a target hit / a stop hit
    be_p = loss_r / (win_r + loss_r) if win_r + loss_r > 0 else 1.0
    risk_usd = equity * risk_pct / 100.0
    notional = risk_usd / stop_pct
    lev = notional / equity
    L = max(1, math.ceil(lev))                                      # isolated margin = notional / L
    liq_pct = 1.0 / L - MMR
    return dict(stop_pct=stop_pct, target_pct=target_pct, rr=rr, fee_r=fee_r, win_r=win_r, loss_r=loss_r, be_p=be_p, risk_usd=risk_usd,
                notional=notional, qty=notional / entry, lev=lev, liq_pct=liq_pct, liq_ratio=stop_pct / liq_pct if liq_pct > 0 else float("inf"))


def baseline(bars: list, side: str, stop_pct: float, target_pct: float, horizon: int, step: int = 1) -> dict:
    """How often a RANDOM entry (the close of every `step`-th bar) with this stop % and target % meets the target first within `horizon` bars.
    A bar touching both counts as the stop. Overlapping starts - an estimate, not a test."""
    win = loss = to = 0
    n = len(bars)
    for i in range(0, n - horizon - 1, step):
        e = bars[i][4]
        stop = e * (1 - stop_pct) if side == "long" else e * (1 + stop_pct)
        tgt = e * (1 + target_pct) if side == "long" else e * (1 - target_pct)
        res = 0
        for j in range(i + 1, i + horizon + 1):
            hi, lo = bars[j][2], bars[j][3]
            hit_stop = lo <= stop if side == "long" else hi >= stop
            hit_tgt = hi >= tgt if side == "long" else lo <= tgt
            if hit_stop:
                res = -1
                break
            if hit_tgt:
                res = 1
                break
        win += res == 1
        loss += res == -1
        to += res == 0
    m = max(win + loss + to, 1)
    return dict(p_tp=win / m, p_sl=loss / m, p_to=to / m, n=m)


BASE_DAYS = 14                  # how much 1-minute history the random-entry baseline reads
BASE_STEP = 15                  # a random entry every 15 minutes inside it


def minute_baseline(sym: str, side: str, stop_pct: float, target_pct: float, hours: int, now_ms: int, fetch=klines, fallback: list | None = None,
                    cache: dict | None = None) -> dict:
    """The random-entry odds on the SAME 1-minute grid the calls are scored on. The 1-hour version (`baseline` on hourly bars) counts every hour that
    touches both ends as a stop, which scores chance harsher than the 1-minute scoring scores a call - so it understated what luck does and flattered
    the call (found 2026-10-27, backtest/analyst_replay_1m.py). Falls back to the hourly bars in `fallback` when the symbol has under three horizons
    of minutes (a new listing); `grid` says which was used. `cache` shares one symbol's minutes across the calls of a cycle."""
    bars = cache.get(sym) if cache is not None else None
    if bars is None:
        bars = bars_between(sym, now_ms - BASE_DAYS * 86_400_000, now_ms - 60_000, fetch)
        if cache is not None:
            cache[sym] = bars
    if len(bars) >= hours * 60 * 3:
        return dict(baseline(bars, side, stop_pct, target_pct, hours * 60, BASE_STEP), grid="1m")
    return dict(baseline(fallback or [], side, stop_pct, target_pct, hours), grid="1h")


def atr_pct(bars: list, n: int = 14) -> float:
    tr = [max(b[2] - b[3], abs(b[2] - bars[i][4]), abs(b[3] - bars[i][4])) for i, b in enumerate(bars[1:])]
    return sum(tr[-n:]) / len(tr[-n:]) / bars[-1][4]


# ------------------------------------------------------------------ scoring

def resolve(call: dict, bars: list, now_ms: int) -> dict:
    """Score one call on the 1-minute bars (open time >= made_ms rounded up to the next full minute for a market call)."""
    c = dict(call)
    side, entry, stop, target = c["side"], float(c["entry"]), float(c["stop"]), float(c["target"])
    expires = int(float(c["expires_ms"]))
    sp = abs(entry - stop) / entry
    filled_i = None
    mode = c["mode"]
    for i, (t, o, h, l, cl) in enumerate(bars):
        if t > expires:
            break
        if mode == "market":
            filled_i = i
            break
        if (side == "long" and l <= entry) or (side == "short" and h >= entry):
            filled_i = i
            break
    if filled_i is None:
        c["status"] = "NOFILL" if now_ms >= expires else "open"
        return c
    c["filled_ms"] = bars[filled_i][0]
    for t, o, h, l, cl in bars[filled_i:]:
        if t > expires:
            break
        hit_stop = l <= stop if side == "long" else h >= stop
        hit_tgt = h >= target if side == "long" else l <= target
        if hit_stop:                                                  # includes a bar that touches both
            gap = (o <= stop) if side == "long" else (o >= stop)
            px = o if gap and t != bars[filled_i][0] else stop
            return finish(c, "LOSS", t, px, entry, sp)
        if hit_tgt:
            return finish(c, "WIN", t, target, entry, sp)
    last = [b for b in bars if b[0] <= expires]
    if now_ms >= expires and last:
        return finish(c, "EXPIRED", last[-1][0], last[-1][4], entry, sp)
    c["status"] = "open"
    return c


def finish(c: dict, status: str, t: int, px: float, entry: float, sp: float) -> dict:
    gross = (px - entry) / entry if c["side"] == "long" else (entry - px) / entry
    c.update(status=status, exit_ms=t, exit_price=px, r_net=(gross - FEE) / sp)
    return c


# ------------------------------------------------------------------ storage

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


def now_ms() -> int:
    return int(time.time() * 1000)


def ts(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M")


# ------------------------------------------------------------------ commands

def cmd_plan(a, fetch=klines) -> int:
    sym = a.symbol.upper()
    sym = sym if sym.endswith("USDT") else sym + "USDT"
    h1 = fetch(sym, "1h", None, None, 500)
    last = h1[-1][4]
    mode = "market" if str(a.entry).lower() in ("mkt", "market") else "limit"
    entry = last if mode == "market" else float(a.entry)
    stop, target = float(a.stop), float(a.target)
    bad = geometry_ok(a.side, entry, stop, target)
    if bad:
        print(f"REFUSED: {bad} (entry {entry:g}, stop {stop:g}, target {target:g})")
        return 2
    p = plan_numbers(a.side, entry, stop, target, a.equity, a.risk_pct)
    horizon = max(1, int(a.hours))
    b = minute_baseline(sym, a.side, p["stop_pct"], p["target_pct"], horizon, now_ms(), fetch, h1)
    atr = atr_pct(h1)
    warn = []
    if p["notional"] < MIN_NOTIONAL:
        warn.append(f"position ${p['notional']:.2f} is under Bitget's ${MIN_NOTIONAL:.0f} minimum - raise the risk % or widen the stop")
    if p["lev"] > 10:
        warn.append(f"needs {p['lev']:.1f}x - a stop this tight is inside normal noise and the size is large")
    if p["liq_ratio"] > 0.5:
        warn.append(f"the stop is {p['liq_ratio'] * 100:.0f}% of the way to liquidation at {max(1, math.ceil(p['lev']))}x isolated - use less leverage")
    if p["stop_pct"] < 0.5 * atr:
        warn.append(f"the stop is only {p['stop_pct'] / atr:.2f} of an hour's average range - expect to be stopped by noise")
    if p["be_p"] > 0.6:
        warn.append(f"you must win {p['be_p'] * 100:.0f}% of the time just to break even after fees")
    print(f"PLAN {sym} {a.side.upper()} - {'MARKET now' if mode == 'market' else 'LIMIT'} entry {entry:g} (last {last:g})  stop {stop:g}  target {target:g}  "
          f"within {horizon}h")
    print(f"  stop {p['stop_pct'] * 100:.2f}% away, target {p['target_pct'] * 100:.2f}% away, reward:risk {p['rr']:.2f}; the 12bp fee is {p['fee_r']:.2f}R")
    print(f"  net if it works {p['win_r']:+.2f}R, if it fails {-p['loss_r']:+.2f}R -> you need to win {p['be_p'] * 100:.0f}% to break even")
    print(f"  BASELINE (random entries, same stop %, target %, {horizon}h, last {len(h1)} hourly bars): target first {b['p_tp'] * 100:.0f}%, "
          f"stop first {b['p_sl'] * 100:.0f}%, neither {b['p_to'] * 100:.0f}%")
    print(f"  size for ${a.equity:g} risking {a.risk_pct:g}% (${p['risk_usd']:.2f}): position ${p['notional']:.2f} = {p['qty']:.6g} {sym[:-4]}, {p['lev']:.1f}x, "
          f"isolated liquidation ~{p['liq_pct'] * 100:.1f}% away; the stop is {p['stop_pct'] / atr:.1f} x the last hour range")
    for w in warn:
        print(f"  WARNING: {w}")
    if a.no_log:
        print("  (not logged)")
        return 0
    rows = load_calls()
    made = now_ms()
    rows.append(dict(id=len(rows) + 1, made_utc=ts(made), made_ms=made, symbol=sym, side=a.side, mode=mode, entry=entry, stop=stop, target=target,
                     expires_ms=made + horizon * 3_600_000, method=a.method, note=a.note or "", equity=a.equity, risk_pct=a.risk_pct,
                     risk_usd=round(p["risk_usd"], 4), qty=p["qty"], notional=round(p["notional"], 4), lev=round(p["lev"], 3),
                     stop_pct=round(p["stop_pct"], 6), target_pct=round(p["target_pct"], 6), rr=round(p["rr"], 4), be_p=round(p["be_p"], 4),
                     base_p=round(b["p_tp"], 4), status="open"))
    save_calls(rows)
    print(f"  logged as PAPER call #{len(rows)} ({ts(made)} UTC) before its outcome; `python desk.py score` resolves it. Not advice - a record.")
    return 0


def cmd_score(fetch=klines) -> int:
    rows = load_calls()
    n_new = 0
    for i, r in enumerate(rows):
        if r.get("status") not in ("open", ""):
            continue
        made, exp = int(float(r["made_ms"])), int(float(r["expires_ms"]))
        end = min(now_ms(), exp + 60_000)
        start = made // 60_000 * 60_000 + 60_000                  # the next full minute: nothing from before the call existed
        bars = bars_between(r["symbol"], start, end, fetch)
        new = resolve(r, bars, now_ms())
        if new["status"] != "open":
            n_new += 1
        rows[i] = new
    save_calls(rows)
    print(f"scored: {n_new} call(s) resolved this run")
    return cmd_list()


def cmd_list() -> int:
    for r in load_calls():
        rn = f"{float(r['r_net']):+.2f}R" if r.get("r_net") not in ("", None) else ""
        print(f"  #{r['id']:>3} {r['made_utc']} {r['symbol']:<10} {r['side']:<5} {r['mode']:<6} e {float(r['entry']):<10g} sl {float(r['stop']):<10g} "
              f"tp {float(r['target']):<10g} rr {float(r['rr']):.1f} base {float(r['base_p']) * 100:.0f}% [{r['method']}] {r['status']:<8} {rn}")
    return 0


def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def cmd_stats() -> int:
    rows = load_calls()
    done = [r for r in rows if r.get("status") in ("WIN", "LOSS", "EXPIRED")]
    print(f"calls {len(rows)}: open {sum(r.get('status') == 'open' for r in rows)}, no fill {sum(r.get('status') == 'NOFILL' for r in rows)}, "
          f"filled and resolved {len(done)}")
    if not done:
        return 0
    wins = [r for r in done if r["status"] == "WIN"]
    losses = [r for r in done if r["status"] == "LOSS"]
    ex = [r for r in done if r["status"] == "EXPIRED"]
    rs = [float(r["r_net"]) for r in done]
    print(f"  wins {len(wins)}, losses {len(losses)}, expired {len(ex)}; average {sum(rs) / len(rs):+.2f}R after fees, total {sum(rs):+.2f}R")
    base = sum(float(r["base_p"]) for r in done) / len(done)
    be = sum(float(r["be_p"]) for r in done) / len(done)
    print(f"  hit rate (target first, of all resolved) {len(wins) / len(done) * 100:.0f}%  vs the random-entry baseline {base * 100:.0f}%  vs break-even {be * 100:.0f}%")
    if len(done) < MIN_CALLS:
        print(f"  NOT ENOUGH CALLS ({len(done)} of {MIN_CALLS}) - no verdict yet")
        return 0
    var = sum(float(r["base_p"]) * (1 - float(r["base_p"])) for r in done)
    z = (len(wins) - sum(float(r["base_p"]) for r in done)) / math.sqrt(var) if var > 0 else 0.0
    p = 1 - norm_cdf(z)
    edge = sum(rs) / len(rs) > 0 and p < 0.05
    print(f"  one-sided p that the hit rate beats the baselines: {p:.3f} -> {'EDGE (positive average R and p < 0.05)' if edge else 'NO EDGE PROVEN'}")
    for m in sorted({r['method'] for r in done}):
        g = [r for r in done if r["method"] == m]
        print(f"    method {m:<6} n {len(g):3d}" + (f"  average {sum(float(r['r_net']) for r in g) / len(g):+.2f}R" if len(g) >= MIN_CALLS else "  (under 30: not compared)"))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="paper desk: plan, log and score manual trade calls (public data, no keys, no orders)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("symbol")
    p.add_argument("side", choices=["long", "short"])
    p.add_argument("entry")
    p.add_argument("stop")
    p.add_argument("target")
    p.add_argument("--hours", type=float, default=48)
    p.add_argument("--equity", type=float, default=221.0)
    p.add_argument("--risk-pct", type=float, default=1.0)
    p.add_argument("--method", default="other", choices=["sr", "fib", "smc", "other"])
    p.add_argument("--note", default="")
    p.add_argument("--no-log", action="store_true")
    sub.add_parser("score")
    sub.add_parser("stats")
    sub.add_parser("list")
    a = ap.parse_args(argv)
    return {"plan": lambda: cmd_plan(a), "score": cmd_score, "stats": cmd_stats, "list": cmd_list}[a.cmd]()


if __name__ == "__main__":
    sys.exit(main())

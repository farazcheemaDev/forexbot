"""THE ANALYST DESK'S THREE RULES REPLAYED OVER HISTORY, WITH THE WHOLE ACCOUNT AT 10x / 20x / 30x (2026-10-27)

The user, before the desk went live: "10x 20x 30x leverage, capital 20 / 50 / 100 / 300 - how would that result in". The desk has no record yet
(it has never run), so this replays analyst.py's own rules - `analyst.signals`, unchanged, fixed before any history was read - over about
4.8 years of Binance perp candles and scores the calls the way the desk will, only coarser: 1-HOUR bars instead of 1-minute (a bar that
touches both stop and target = a loss, so this is the harsher of the two). Then `analyst.scenario` takes the same calls with the whole account
at each leverage, one position at a time, liquidation from each call's worst move.
CAUSAL: a signal reads only bars closed by the end of hour i (1h) and the 4h / daily bars closed by then (aggregated from the same 1h bars,
UTC-aligned); the entry is the OPEN of hour i+1; scoring starts in that bar. One open call per symbol and rule, 6 hours of cooldown, as live.
MARKETS  BTC ETH SOL XRP BNB (2022-01-01 on), gold (XAUUSDT) and QQQ (QQQUSDT) from their listing dates. Fee 12bp of notional.
SPLIT    tune = the first 60% of the calls' time span, holdout = the last 40% (nothing was tuned on either: the rules are the desk's).

REGISTERED BEFORE THE FIRST RUN (2026-10-27; the same lines are A5-A8 in analyst.py)
  A5  No rule beats its break-even hit rate on BOTH halves after 12bp.
  A6  All-in, one position at a time, the median 12-month outcome resampled from these calls is under the start at 10x, 20x and 30x, and the
      chance of losing 90% of the account at some point in those 12 months is >= 20% at 30x and rises with leverage.
  A7  $20 and $300 end at the same multiple (capital changes dollars, not percentages).
  A8  More leverage raises the best case (90th percentile) and lowers the median.
  A9  (added with the bootstrap) At 1x the same calls lose less than they do at 10x: the rules' gross edge is thinner than the fee at any size.
RESAMPLE  the calls taken one at a time (leverage does not change which are taken) drawn with replacement, a year's worth of them, 20,000 paths;
  "ruin" = the account at or under 10% of its start at any point; liquidation counted per call.

    python -m backtest.analyst_replay            full run (downloads and caches the candles on first use)
    python -m backtest.analyst_replay --sample   BTC only, 2025-01 on (a quick check of the machinery)
Writes logs/analyst_replay.txt (what is printed) and analyst_replay.json (the dashboard's copy of the grid).
"""
from __future__ import annotations

import bisect
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import analyst as an  # noqa: E402
import desk  # noqa: E402

CACHE = ROOT / "strategy_analysis" / "data" / "analyst_replay"
OUT_TXT, OUT_JSON = ROOT / "logs" / "analyst_replay.txt", ROOT / "analyst_replay.json"
H1, H4, D1 = an.H1, an.H4, an.D1
START_MS = int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
WATCH = an.WATCH
REF_LEVS = (1, 3, 5, 10, 20, 30)
PATHS = 20_000
LINES: list = []


def say(s: str = ""):
    print(s, flush=True)
    LINES.append(s)


# ------------------------------------------------------------------ candles

def history(sym: str, start_ms: int, end_ms: int) -> list:
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{sym}_1h.json"
    have = json.loads(p.read_text()) if p.exists() else []
    if have and have[0][0] > start_ms + 2 * H1:                              # a cache that starts later than asked (an earlier --sample run): back-fill the front
        t, front = start_ms, []
        while t < have[0][0]:
            page = desk.klines(sym, "1h", t, have[0][0] - H1, 1500)
            if not page:                                                     # nothing earlier exists: a listing that is younger than the span
                break
            front += [list(b) for b in page]
            t = page[-1][0] + H1
            if len(page) < 1500:
                break
        have = front + have
    t = have[-1][0] + H1 if have else start_ms
    while t + H1 <= end_ms:
        page = desk.klines(sym, "1h", t, end_ms, 1500)
        if not page:
            break
        have += [list(b) for b in page if b[0] + H1 <= end_ms]
        t = page[-1][0] + H1
        if len(page) < 1500:
            break
    seen, out = set(), []
    for b in have:
        if b[0] not in seen:
            seen.add(b[0])
            out.append(tuple(b))
    out.sort()
    p.write_text(json.dumps(out))
    return [b for b in out if b[0] >= start_ms]


def aggregate(bars: list, width_ms: int) -> list:
    """Complete UTC-aligned groups of 1h bars only (a group with a missing hour is dropped)."""
    per = width_ms // H1
    groups: dict = {}
    for b in bars:
        groups.setdefault(b[0] // width_ms, []).append(b)
    out = []
    for k in sorted(groups):
        g = groups[k]
        if len(g) == per:
            out.append((g[0][0], g[0][1], max(x[2] for x in g), min(x[3] for x in g), g[-1][4]))
    return out


# ------------------------------------------------------------------ the replay

def replay_symbol(sym: str, bars: list) -> list:
    if len(bars) < 700:
        return []
    h4all, d1all = aggregate(bars, H4), aggregate(bars, D1)
    s4, sd = [b[0] for b in h4all], [b[0] for b in d1all]
    memo: dict = {}
    sr0, fib0 = an.sr_levels, an.fib_swing
    cur = [sym]
    an.sr_levels = lambda h4c, d1c: memo.setdefault(("sr", cur[0], h4c[-1][0], d1c[-1][0]), sr0(h4c, d1c))
    an.fib_swing = lambda h4c, look=60: memo.setdefault(("fib", cur[0], h4c[-1][0]), fib0(h4c, look))
    rows, blocked_until = [], {}
    try:
        for i in range(500, len(bars) - 1):
            T = bars[i][0] + H1                                            # the hour has just closed
            nxt = bars[i + 1]
            if nxt[0] != T:                                                # a hole in the data: no signal across it
                continue
            h1c = bars[i - 499:i + 1]
            h4c = h4all[max(0, bisect.bisect_right(s4, T - H4) - 300):bisect.bisect_right(s4, T - H4)]
            d1c = d1all[max(0, bisect.bisect_right(sd, T - D1) - 200):bisect.bisect_right(sd, T - D1)]
            if len(h4c) < 80 or len(d1c) < 40:
                continue
            for sig in an.signals(sym, h1c, h4c, d1c, nxt[1]):
                key = (sym, sig["method"])
                if T < blocked_until.get(key, 0):
                    continue
                p = desk.plan_numbers(sig["side"], sig["entry"], sig["stop"], sig["target"], 300.0, an.RISK_PCT)
                span = bars[i + 1:i + 1 + sig["hours"]]                      # the bars the call lives through (entry bar first)
                if len(span) < sig["hours"]:
                    continue
                call = dict(side=sig["side"], mode="market", entry=sig["entry"], stop=sig["stop"], target=sig["target"],
                            expires_ms=T + sig["hours"] * H1)
                res = desk.resolve(call, span, T + (sig["hours"] + 2) * H1)
                if res["status"] not in ("WIN", "LOSS", "EXPIRED"):
                    continue
                mae = an.mae_of(res, span)
                base = desk.baseline(h1c[-500:], sig["side"], p["stop_pct"], p["target_pct"], sig["hours"])
                rows.append(dict(symbol=sym, method=sig["method"], side=sig["side"], made_ms=T, entry=sig["entry"], stop=sig["stop"], target=sig["target"],
                                 exit_ms=res["exit_ms"] + H1, exit_price=res["exit_price"], status=res["status"], r_net=res["r_net"], mae=mae,
                                 stop_pct=p["stop_pct"], be_p=p["be_p"], base_p=base["p_tp"], pnl_usd=0.0))
                blocked_until[key] = res["exit_ms"] + H1 + an.COOLDOWN_H * H1
    finally:
        an.sr_levels, an.fib_swing = sr0, fib0
    return rows


# ------------------------------------------------------------------ the desk's own paper book

def paper_book(rows: list, start: float = an.START) -> dict:
    """analyst.py's book over the replay: every call risks RISK_PCT of the BOOKED equity at its entry (sized once, not re-sized), a call that would push the
    open notional past MAX_GROSS x equity is not booked, a result is booked when the call ends. The same arithmetic the live desk uses."""
    import heapq
    eq, peak, maxdd, booked, skipped = start, start, 0.0, 0, 0
    open_: list = []                                                  # (exit_ms, notional, r_net, risk_usd)
    marks = [(rows[0]["made_ms"], start)] if rows else []

    def realise(upto: float):
        nonlocal eq, peak, maxdd
        while open_ and open_[0][0] <= upto:
            ex, _n, r, risk = heapq.heappop(open_)
            eq += r * risk
            peak = max(peak, eq)
            maxdd = max(maxdd, 1.0 - eq / peak)
            marks.append((ex, eq))
    for r in sorted(rows, key=lambda r: r["made_ms"]):
        realise(r["made_ms"])
        risk = eq * an.RISK_PCT / 100.0
        notional = risk / r["stop_pct"]
        if sum(o[1] for o in open_) + notional > an.MAX_GROSS * eq:
            skipped += 1
            continue
        booked += 1
        heapq.heappush(open_, (r["exit_ms"], notional, r["r_net"], risk))
    realise(float("inf"))
    years: dict = {}
    for t, e in marks:
        y = datetime.fromtimestamp(t / 1000, timezone.utc).year
        a, _b = years.get(y, (e, e))
        years[y] = (a, e)
    span_w = (rows[-1]["made_ms"] - rows[0]["made_ms"]) / (7 * 86_400_000) if rows else 1
    return dict(final=eq, ret=eq / start - 1, maxdd=maxdd, booked=booked, skipped=skipped, weeks=span_w,
                weekly=(eq / start) ** (1 / span_w) - 1 if eq > 0 else -1.0, by_year={str(y): (b / a - 1) for y, (a, b) in years.items()})


# ------------------------------------------------------------------ reading the calls

def taken_one_at_a_time(rows: list) -> list:
    out, busy = [], 0.0
    for r in sorted(rows, key=lambda r: r["made_ms"]):
        if r["made_ms"] >= busy:
            out.append(r)
            busy = r["exit_ms"]
    return out


def bootstrap(taken: list, per_year: int, lev: float, rng: random.Random) -> dict:
    fr = [an.leveraged_result(r, lev) for r in taken]
    ends, ruin, liq = [], 0, 0
    for _ in range(PATHS):
        eq, bad, l = 1.0, False, 0
        for _k in range(per_year):
            f, lq = fr[rng.randrange(len(fr))]
            eq = max(0.0, eq * (1.0 + f))
            l += lq
            if eq <= 0.10:
                bad = True
        ends.append(eq)
        ruin += bad
        liq += l
    ends.sort()
    q = lambda x: ends[min(len(ends) - 1, int(x * len(ends)))]  # noqa: E731
    return dict(lev=lev, median=q(0.5), p10=q(0.10), p90=q(0.90), mean=sum(ends) / len(ends), below_start=sum(e < 1 for e in ends) / len(ends),
                doubled=sum(e >= 2 for e in ends) / len(ends), ruin=ruin / PATHS, liq_per_year=liq / PATHS)


def show_stats(label: str, rows: list):
    s = an.stats(rows)
    if not s["resolved"]:
        say(f"  {label}: no calls")
        return s
    say(f"  {label}: {s['resolved']} calls, hit {s['hit'] * 100:.1f}% vs random {s['baseline'] * 100:.1f}% vs break-even {s['breakeven'] * 100:.1f}%, "
        f"avg {s['avg_r']:+.3f}R after fees, one-sided p {s['p']:.3f}")
    return s


def fmt_grid(rows: list, title: str):
    say(f"  {title}")
    say("    capital  " + "  ".join(f"{x:>2d}x: end $ / taken / liq / maxdd" for x in an.LEVERAGES))
    g = {(c["capital"], c["lev"]): c for c in an.grid(rows)}
    for cap in an.CAPITALS:
        say(f"    ${cap:<5d}   " + "  ".join(
            f"{g[(cap, x)]['equity']:>9.2f} /{g[(cap, x)]['taken']:>4d} /{g[(cap, x)]['liquidated']:>3d} /{g[(cap, x)]['maxdd'] * 100:>4.0f}%" for x in an.LEVERAGES))


def main():
    sample = "--sample" in sys.argv
    now = int(time.time() * 1000) // H1 * H1
    start = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000) if sample else START_MS
    syms = ["BTCUSDT"] if sample else WATCH
    say(f"ANALYST DESK REPLAY, {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, 1h bars, fee 12bp, 1 position per symbol and rule")
    rows, per_sym = [], {}
    for sym in syms:
        try:
            bars = history(sym, start, now)
        except Exception as e:  # noqa: BLE001
            say(f"  {sym}: no candles ({type(e).__name__})")
            continue
        t0 = time.time()
        r = replay_symbol(sym, bars)
        per_sym[sym] = dict(bars=len(bars), calls=len(r), first=desk.ts(bars[0][0]) if bars else None)
        say(f"  {sym}: {len(bars)} hourly bars from {per_sym[sym]['first']}, {len(r)} calls ({time.time() - t0:.0f}s)")
        rows += r
    if not rows:
        say("no calls")
        return
    rows.sort(key=lambda r: r["made_ms"])
    if not sample:
        (CACHE / "calls.json").write_text(json.dumps(rows))
    t_first, t_last = rows[0]["made_ms"], rows[-1]["made_ms"]
    split = t_first + 0.6 * (t_last - t_first)
    tune, hold = [r for r in rows if r["made_ms"] < split], [r for r in rows if r["made_ms"] >= split]
    years = (t_last - t_first) / (365.25 * 86_400_000)
    say(f"\n{len(rows)} calls over {years:.2f} years ({desk.ts(t_first)[:10]} .. {desk.ts(t_last)[:10]}), {len(rows) / years / 52:.1f} a week; split at {desk.ts(int(split))[:10]}")

    say("\nTHE RULES (hit rate = target first; break-even includes the 12bp fee; random = same stop / target / hours at a random hour)")
    all_s = show_stats("all rules, whole span", rows)
    t_s, h_s = show_stats("all rules, tune", tune), show_stats("all rules, holdout", hold)
    by = {}
    for m in ("SR", "FIB", "SMC"):
        a, b, c = [r for r in rows if r["method"] == m], [r for r in tune if r["method"] == m], [r for r in hold if r["method"] == m]
        sa, sb, sc = show_stats(f"{m} whole", a), show_stats(f"{m} tune", b), show_stats(f"{m} hold", c)
        by[m] = dict(n=len(a), tune=dict(n=len(b), avg_r=sb.get("avg_r"), hit=sb.get("hit"), be=sb.get("breakeven"), p=sb.get("p")),
                     hold=dict(n=len(c), avg_r=sc.get("avg_r"), hit=sc.get("hit"), be=sc.get("breakeven"), p=sc.get("p")))
    a5 = [m for m in by if (by[m]["tune"].get("hit") or 0) > (by[m]["tune"].get("be") or 1) and (by[m]["hold"].get("hit") or 0) > (by[m]["hold"].get("be") or 1)]
    say(f"  A5 (no rule beats break-even on both halves): rules that DO: {a5 or 'none'}")

    say("\nTHE WHOLE ACCOUNT ON EACH CALL, one position at a time (the same calls for every leverage; final account in dollars from each capital)")
    fmt_grid(rows, "whole span")
    fmt_grid(tune, "tune half")
    fmt_grid(hold, "holdout half")
    early = taken_one_at_a_time(rows)[:8]                                   # before any account is wiped down to the minimum order
    e20, e300 = an.scenario(early, 20, 10), an.scenario(early, 300, 10)
    say(f"  A7: after the first 8 calls $20 stands at {e20['equity'] / 20:.4f}x and $300 at {e300['equity'] / 300:.4f}x at 10x "
        f"({'same' if abs(e20['equity'] / 20 - e300['equity'] / 300) < 1e-9 else 'DIFFERENT'}); over the whole span the small accounts stop trading earlier only because "
        f"a wiped-out account falls under the $5 minimum order (at 10x, under $0.50)")

    pb = paper_book(rows)
    say()
    say(f"THE DESK'S OWN PAPER BOOK over the same calls (${an.START:.0f}, {an.RISK_PCT}% of the booked equity a call, open notional capped at {an.MAX_GROSS:.0f}x):")
    say(f"  ends ${pb['final']:,.2f} ({pb['ret'] * 100:+.1f}%), deepest fall {pb['maxdd'] * 100:.0f}%, {pb['booked']} calls booked, {pb['skipped']} over the cap; "
        f"{pb['weekly'] * 100:+.2f}% a week on average; by year " + ", ".join(f"{y} {v * 100:+.0f}%" for y, v in pb["by_year"].items()))
    taken = taken_one_at_a_time(rows)
    per_year = max(1, round(len(taken) / years))
    say(f"\nRESAMPLED YEARS: {len(taken)} calls taken one at a time over {years:.2f} years = {per_year} a year; {PATHS} paths of {per_year} calls drawn with replacement")
    say("  leverage  median  10th pct  90th pct  mean   under start  doubled  ruin(<=10%)  liquidations/yr")
    rng = random.Random(20261027)
    boot = []
    for lev in REF_LEVS:
        b = bootstrap(taken, per_year, lev, rng)
        boot.append(b)
        say(f"  {lev:>5d}x  {b['median']:>6.2f}x  {b['p10']:>7.2f}x  {b['p90']:>7.2f}x  {b['mean']:>5.2f}x  {b['below_start'] * 100:>9.0f}%  {b['doubled'] * 100:>6.0f}%  "
            f"{b['ruin'] * 100:>9.0f}%  {b['liq_per_year']:>8.2f}")
    bm = {b["lev"]: b for b in boot}
    say("  A6 median under the start at 10x / 20x / 30x: " + " / ".join(str(bm[x]["median"] < 1) for x in (10, 20, 30)) +
        f"; ruin at 30x {bm[30]['ruin'] * 100:.0f}% (>= 20%: {bm[30]['ruin'] >= 0.20}), rising with leverage: {bm[10]['ruin'] <= bm[20]['ruin'] <= bm[30]['ruin']}")
    say(f"  A8 best case up and median down with leverage (10x -> 30x): p90 {bm[10]['p90']:.2f}x -> {bm[30]['p90']:.2f}x, median {bm[10]['median']:.2f}x -> {bm[30]['median']:.2f}x")
    say(f"  A9 1x median {bm[1]['median']:.2f}x vs 10x {bm[10]['median']:.2f}x: " + ("1x loses less" if bm[1]["median"] > bm[10]["median"] else "1x does NOT lose less"))

    out = dict(made=desk.ts(int(time.time() * 1000)), span=[desk.ts(t_first)[:10], desk.ts(t_last)[:10]], years=round(years, 2), calls=len(rows), taken=len(taken),
               per_year=per_year, symbols=per_sym, by_method=by, paper_book=pb,
               stats=dict(all=all_s_json(all_s), tune=all_s_json(t_s), hold=all_s_json(h_s)),
               grid=dict(all=an.grid(rows), tune=an.grid(tune), hold=an.grid(hold)), boot=boot, capitals=list(an.CAPITALS), levs=list(an.LEVERAGES))
    if not sample:
        OUT_JSON.write_text(json.dumps(out, separators=(",", ":")))
        OUT_TXT.parent.mkdir(exist_ok=True)
        OUT_TXT.write_text("\n".join(LINES) + "\n", encoding="utf-8")
        say(f"\nwrote {OUT_JSON.name} and {OUT_TXT.relative_to(ROOT)}")


def all_s_json(s: dict) -> dict:
    return {k: s.get(k) for k in ("resolved", "wins", "losses", "expired", "hit", "baseline", "breakeven", "avg_r", "p")}


if __name__ == "__main__":
    main()

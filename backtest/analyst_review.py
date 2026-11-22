"""THE ANALYST DESK, REVIEWED CALL BY CALL: WHICH CALLS WON AND WHY, WHICH FAILED AND WHY, AND WHAT A FIX COULD AND COULD NOT BE (2026-11-02)

The user: "analyse the Analyst desk on the dashboard - which trades were successful and why, which did not hit their targets and why, and
what could we do differently to fix those - deeply." The record is the desk's own call log (logs/analyst/calls.csv on the VM, snapshot in
logs/analyst_calls_snapshot.csv: 52 calls made 2026-10-27 .. 2026-11-01, 48 resolved, 4 open) plus the public 1-minute bars of every call's
whole life and the day after (cached in strategy_analysis/data/analyst_paths/). Nothing here changes the desk, which stays a forward
measurement; this explains what that measurement is made of.

WHAT IS MEASURED
  record     hit rate against the random-entry baseline and the break-even rate the desk logged with every call; the gross result in R (before the
             12bp fee, which the desk charges in R as 12bp / stop %) - the number that says whether the entries had any skill; by rule, side,
             symbol, reward:risk, stop width.
  winners    time to target, how close they came to the stop (MAE as a share of the stop), how many other calls rode the same market move.
  losers     minutes to the stop, the best they ever did (MFE as a share of the distance to target), whether price reached the TARGET after the
             stop took them out ("right idea, stop too tight") and the stop that would have survived.
  what-ifs   the same entries re-scored with desk.resolve (its pessimistic rules) under other brackets: stop x1.5 / x2, target at 1R / 1.5R / 2R,
             and subsets (no reward:risk above 4, no stop under 0.4%, longs only, one rule only). Every variant is judged by its mean GROSS return
             per trade with a standard error: a variant with no edge earns about 0 before fees whatever its geometry, so only a mean beyond two
             standard errors would mean anything - and with ~48 calls on ~20 independent market moves, that is a high bar.

REGISTERED AFTER READING THE CALL TABLE AND BEFORE COMPUTING ANY PATH (2026-11-02)
  H1  The record is bracket geometry, not entry skill: the hit rate is within 8 points of the average random baseline, and the mean gross R is <= 0.
  H2  Fees are a large part of the loss: the mean fee is >= 0.25R a call, and >= 0.4R for stops under 0.4% of price.
  H3  Calls with reward:risk above 4 have no wins among them and account for most of the losses.
  H4  Most losers die fast: the median time to the stop is under 3 hours, and at least half never reach 25% of the distance to target.
  H5  At least 20% of the losers would have hit their target later, before the call expired (a stop inside the noise).
  H6  No what-if variant reaches a mean gross return 2 standard errors above 0 (nothing to fix mechanically).

    python -m backtest.analyst_review
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import desk  # noqa: E402

SNAP = ROOT / "logs" / "analyst_calls_snapshot.csv"
PATHS = ROOT / "strategy_analysis" / "data" / "analyst_paths"
LOG = ROOT / "logs" / "analyst_review.txt"
FEE = desk.FEE
DONE = ("WIN", "LOSS", "EXPIRED")


def f(x, d=0.0):
    try:
        v = float(x)
        return v if v == v else d
    except (TypeError, ValueError):
        return d


def fee_r(stop_pct: float) -> float:
    """The 12bp round trip in units of the call's risk (1R = the stop distance)."""
    return FEE / stop_pct


def gross_r(r: dict) -> float:
    """Result in R BEFORE the fee: the desk's r_net adds the fee back."""
    return f(r["r_net"]) + fee_r(f(r["stop_pct"]))


def side_sign(side: str) -> int:
    return 1 if side == "long" else -1


def excursions(side: str, entry: float, bars: list, end_ms: float = float("inf")):
    """(MFE, MAE) as shares of the entry over the bars with open time <= end_ms: the best and the worst the position was."""
    seg = [b for b in bars if b[0] <= end_ms]
    if not seg:
        return 0.0, 0.0
    hi, lo = max(b[2] for b in seg), min(b[3] for b in seg)
    if side == "long":
        return max(0.0, hi / entry - 1), max(0.0, 1 - lo / entry)
    return max(0.0, 1 - lo / entry), max(0.0, hi / entry - 1)


def later_reaches_target(side: str, entry: float, target: float, bars: list, after_ms: float, expires_ms: float):
    """Minutes after `after_ms` at which price first touches the target before the call's expiry (None = never)."""
    for t, o, h, l, c in bars:
        if t <= after_ms or t > expires_ms:
            continue
        if (side == "long" and h >= target) or (side == "short" and l <= target):
            return (t - after_ms) / 60000
    return None


def stop_that_would_have_survived(side: str, entry: float, bars: list, start_ms: float, until_ms: float):
    """The stop distance (share of entry) that would have survived until `until_ms`: the worst move against the position by then."""
    return excursions(side, entry, [b for b in bars if b[0] >= start_ms], until_ms)[1]


def rescore(r: dict, bars: list, stop_mult: float = 1.0, target_r: float | None = None, now: float = 0.0) -> dict | None:
    """The same entry scored by desk.resolve with the stop moved to stop_mult x its distance and, if given, the target at target_r x the ORIGINAL
    stop distance. Returns the finished call (status, exit_price, exit_ms) or None while it is still open."""
    side, entry = r["side"], f(r["entry"])
    sp = f(r["stop_pct"])
    c = dict(r)
    c["stop"] = entry * (1 - stop_mult * sp) if side == "long" else entry * (1 + stop_mult * sp)
    if target_r is not None:
        c["target"] = entry * (1 + target_r * sp) if side == "long" else entry * (1 - target_r * sp)
    out = desk.resolve(c, bars, now)
    return out if out["status"] in DONE else None


def trade_gross(out: dict) -> float:
    """Gross return of a scored call as a share of the entry, in the call's direction (no fee)."""
    e, px = f(out["entry"]), f(out["exit_price"])
    return side_sign(out["side"]) * (px / e - 1)


def mean_se(xs: list):
    n = len(xs)
    if n == 0:
        return float("nan"), float("nan")
    m = sum(xs) / n
    if n < 2:
        return m, float("nan")
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    return m, sd / math.sqrt(n)


def load_calls() -> list:
    with open(SNAP, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def get_path(r: dict, now_ms: int) -> list:
    """The 1-minute bars of the call's life and the rest of its horizon (cached)."""
    PATHS.mkdir(parents=True, exist_ok=True)
    fp = PATHS / f"{r['id']}_{r['symbol']}.json"
    if fp.exists() and r["status"] in DONE:
        return [tuple(b) for b in json.loads(fp.read_text())]
    start = int(f(r["made_ms"])) // 60_000 * 60_000 + 60_000
    end = min(now_ms - 60_000, int(f(r["expires_ms"])) + 60_000)
    bars = desk.bars_between(r["symbol"], start, end)
    if r["status"] in DONE and end >= int(f(r["expires_ms"])):
        fp.write_text(json.dumps(bars))
    return bars


def bucket_rr(rr: float) -> str:
    return "RR <= 2.5" if rr <= 2.5 else "RR 2.5-4" if rr <= 4 else "RR > 4"


def bucket_stop(sp: float) -> str:
    return "stop < 0.4%" if sp < 0.004 else "stop 0.4-0.8%" if sp < 0.008 else "stop >= 0.8%"


def summarize(rows: list, label: str) -> str:
    if not rows:
        return f"  {label:<18} no calls"
    n, w = len(rows), sum(r["status"] == "WIN" for r in rows)
    base = sum(f(r["base_p"]) for r in rows) / n
    be = sum(f(r["be_p"]) for r in rows) / n
    gr = [gross_r(r) for r in rows]
    nr = [f(r["r_net"]) for r in rows]
    gm, gse = mean_se(gr)
    return (f"  {label:<18} n {n:3d}  wins {w:2d} ({w / n * 100:3.0f}%)  random baseline {base * 100:3.0f}%  break-even {be * 100:3.0f}%   "
            f"gross {gm:+.2f}R (se {gse:.2f})  net {sum(nr) / n:+.2f}R  fee {sum(fee_r(f(r['stop_pct'])) for r in rows) / n:.2f}R")


def main():
    import time
    now = int(time.time() * 1000)
    rows = load_calls()
    done = [r for r in rows if r["status"] in DONE]
    paths = {r["id"]: get_path(r, now) for r in rows}
    L = [f"backtest/analyst_review.py, {desk.ts(now)} UTC; {len(rows)} calls ({len(done)} resolved, {len(rows) - len(done)} open) from the desk's log, "
         f"made {min(r['made_utc'] for r in rows)} .. {max(r['made_utc'] for r in rows)}", ""]
    # ------------------------------------------------------------------ 1 the record
    L.append("1  THE RECORD (gross = before the 12bp fee; 0 = no skill, whatever the brackets)")
    L.append(summarize(done, "all resolved"))
    for key, name in (("method", "rule"), ("side", "side"), ("symbol", "symbol")):
        for v in sorted({r[key] for r in done}):
            L.append(summarize([r for r in done if r[key] == v], f"{name} {v}"))
    for b in ("RR <= 2.5", "RR 2.5-4", "RR > 4"):
        L.append(summarize([r for r in done if bucket_rr(f(r["rr"])) == b], b))
    for b in ("stop < 0.4%", "stop 0.4-0.8%", "stop >= 0.8%"):
        L.append(summarize([r for r in done if bucket_stop(f(r["stop_pct"])) == b], b))
    wins, losses, exp = ([r for r in done if r["status"] == s] for s in ("WIN", "LOSS", "EXPIRED"))
    groups = {}
    for r in done:
        groups.setdefault((int(f(r["made_ms"])) // 86_400_000, r["side"]), []).append(r)
    L += ["", f"   independent bets (calls made the same UTC day in the same direction = one move): {len(groups)}; "
              f"bets whose hit rate beat their baseline: {sum((sum(x['status'] == 'WIN' for x in g) / len(g)) > sum(f(x['base_p']) for x in g) / len(g) for g in groups.values())}"]
    # ------------------------------------------------------------------ 2 winners
    L += ["", "2  THE WINNERS"]
    L.append(f"   {'id':>3} {'when':<12}{'symbol':<9}{'side':<6}{'rule':<5}{'RR':>5}{'stop%':>7}{'min to target':>14}{'MAE/stop':>10}{'same-move calls':>17}   note")
    for r in wins:
        bars = paths[r["id"]]
        mfe, mae = excursions(r["side"], f(r["entry"]), bars, f(r["exit_ms"]))
        mins = (f(r["exit_ms"]) - f(r["filled_ms"])) / 60000
        grp = groups[(int(f(r["made_ms"])) // 86_400_000, r["side"])]
        L.append(f"   {r['id']:>3} {r['made_utc'][5:]:<12}{r['symbol']:<9}{r['side']:<6}{r['method']:<5}{f(r['rr']):>5.1f}{f(r['stop_pct']) * 100:>7.2f}{mins:>14.0f}{mae / f(r['stop_pct']):>10.2f}"
                 f"{len(grp):>17}   {r['note'][:60]}")
    tt = sorted((f(r["exit_ms"]) - f(r["filled_ms"])) / 60000 for r in wins)
    L.append(f"   minutes to target: median {tt[len(tt) // 2]:.0f}, quartiles {tt[len(tt) // 4]:.0f} / {tt[3 * len(tt) // 4]:.0f}; "
             f"winners' average RR {sum(f(r['rr']) for r in wins) / len(wins):.2f}, stop {sum(f(r['stop_pct']) for r in wins) / len(wins) * 100:.2f}%")
    # ------------------------------------------------------------------ 3 losers
    L += ["", "3  THE LOSERS (stopped out)"]
    mins_l, mfe_frac, late, need = [], [], [], []
    for r in losses:
        bars = paths[r["id"]]
        entry, tgt = f(r["entry"]), f(r["target"])
        mfe, mae = excursions(r["side"], entry, bars, f(r["exit_ms"]))
        mins_l.append((f(r["exit_ms"]) - f(r["filled_ms"])) / 60000)
        mfe_frac.append(mfe / f(r["target_pct"]))
        late.append(later_reaches_target(r["side"], entry, tgt, bars, f(r["exit_ms"]), f(r["expires_ms"])))
        need.append(stop_that_would_have_survived(r["side"], entry, bars, f(r["filled_ms"]), f(r["expires_ms"])) / f(r["stop_pct"]))
    ms = sorted(mins_l)
    L.append(f"   minutes from fill to stop: median {ms[len(ms) // 2]:.0f}, quartiles {ms[len(ms) // 4]:.0f} / {ms[3 * len(ms) // 4]:.0f}; stopped within 60 min: "
             f"{sum(m <= 60 for m in mins_l)} of {len(mins_l)}, within 3 h: {sum(m <= 180 for m in mins_l)}")
    mf = sorted(mfe_frac)
    L.append(f"   best the loser ever did, as a share of the distance to target: median {mf[len(mf) // 2] * 100:.0f}%, "
             f"reached >= 25%: {sum(x >= 0.25 for x in mfe_frac)}, >= 50%: {sum(x >= 0.5 for x in mfe_frac)}, >= 75%: {sum(x >= 0.75 for x in mfe_frac)} of {len(mfe_frac)}")
    nl = sum(x is not None for x in late)
    L.append(f"   price touched the TARGET after the stop, before the call expired ('stopped then right'): {nl} of {len(late)}")
    L.append(f"   stop that would have survived to expiry, in multiples of the stop used: median {sorted(need)[len(need) // 2]:.1f}x; "
             f"survived at 1.5x: {sum(x <= 1.5 for x in need)}, at 2x: {sum(x <= 2.0 for x in need)}, at 3x: {sum(x <= 3.0 for x in need)} of {len(need)}")
    L.append(f"   {'id':>3} {'when':<12}{'symbol':<9}{'side':<6}{'rule':<5}{'RR':>5}{'stop%':>7}{'min to stop':>12}{'best vs target':>15}{'target later?':>15}{'stop needed':>12}")
    for r, m, mfv, lt, nd in zip(losses, mins_l, mfe_frac, late, need):
        L.append(f"   {r['id']:>3} {r['made_utc'][5:]:<12}{r['symbol']:<9}{r['side']:<6}{r['method']:<5}{f(r['rr']):>5.1f}{f(r['stop_pct']) * 100:>7.2f}{m:>12.0f}"
                 f"{mfv * 100:>14.0f}%{('yes, +%.0f min' % lt) if lt is not None else 'no':>15}{nd:>11.1f}x")
    L += ["", f"   the {len(exp)} EXPIRED calls (neither stop nor target inside the horizon): " + "; ".join(
        f"#{r['id']} {r['symbol']} {r['side']} {r['method']} RR {f(r['rr']):.1f} ended {f(r['r_net']):+.2f}R" for r in exp)]
    # ------------------------------------------------------------------ 4 fees and geometry
    L += ["", "4  FEES AND GEOMETRY"]
    frs = [fee_r(f(r["stop_pct"])) for r in done]
    L.append(f"   the 12bp fee is {sum(frs) / len(frs):.2f}R a call on average (median {sorted(frs)[len(frs) // 2]:.2f}R, largest {max(frs):.2f}R); "
             f"total {sum(frs):.1f}R of the {sum(f(r['r_net']) for r in done):+.1f}R net, i.e. gross {sum(gross_r(r) for r in done):+.1f}R")
    for b in ("stop < 0.4%", "stop 0.4-0.8%", "stop >= 0.8%"):
        g = [r for r in done if bucket_stop(f(r["stop_pct"])) == b]
        if g:
            L.append(f"   {b:<14} {len(g):2d} calls: fee {sum(fee_r(f(r['stop_pct'])) for r in g) / len(g):.2f}R each, win share needed to break even "
                     f"{sum(f(r['be_p']) for r in g) / len(g) * 100:.0f}% vs a random entry's {sum(f(r['base_p']) for r in g) / len(g) * 100:.0f}%")
    hi_rr = [r for r in done if f(r["rr"]) > 4]
    L.append(f"   RR > 4: {len(hi_rr)} calls, {sum(r['status'] == 'WIN' for r in hi_rr)} wins, random baseline {sum(f(r['base_p']) for r in hi_rr) / max(len(hi_rr), 1) * 100:.0f}% a call, "
             f"{sum(f(r['r_net']) for r in hi_rr):+.1f}R of the {sum(f(r['r_net']) for r in done):+.1f}R total")
    # ------------------------------------------------------------------ 5 what-ifs
    L += ["", "5  WHAT-IFS: the same entries under other brackets (hindsight, in-sample; judged by mean GROSS return per trade, 12bp not charged - a no-edge variant earns ~0)"]
    L.append(f"   {'variant':<34}{'n':>4}{'hit':>6}{'mean gross %':>14}{'se %':>7}{'t':>6}{'mean net % (12bp)':>19}")
    variants = {}

    def add(name, picks):
        g = [trade_gross(o) for o in picks if o is not None]
        if not g:
            return
        m, se = mean_se(g)
        hit = sum(1 for o in picks if o is not None and o["status"] == "WIN") / len(g)
        variants[name] = (len(g), m, se)
        L.append(f"   {name:<34}{len(g):>4}{hit * 100:>5.0f}%{m * 100:>14.3f}{se * 100:>7.3f}{(m / se if se else float('nan')):>6.1f}{(m - FEE) * 100:>19.3f}")

    def scored(subset, **kw):
        return [rescore(r, paths[r["id"]], now=now, **kw) for r in subset]

    mism = sum(1 for r in done if (rescore(r, paths[r["id"]], now=now) or {}).get("status") != r["status"])
    L.append(f"   (sanity: re-scoring every call unchanged reproduces the logged status for {len(done) - mism} of {len(done)})")
    add("as logged", scored(done))
    add("stop x1.5", scored(done, stop_mult=1.5))
    add("stop x2", scored(done, stop_mult=2.0))
    add("target at 1R", scored(done, target_r=1.0))
    add("target at 1.5R", scored(done, target_r=1.5))
    add("target at 2R (RR capped at 2)", scored([r for r in done if f(r["rr"]) > 2], target_r=2.0) + scored([r for r in done if f(r["rr"]) <= 2]))
    add("stop x2 and target at 2R", scored(done, stop_mult=2.0, target_r=2.0))
    add("no RR above 4", scored([r for r in done if f(r["rr"]) <= 4]))
    add("no stop under 0.4%", scored([r for r in done if f(r["stop_pct"]) >= 0.004]))
    add("RR <= 4 and stop >= 0.4%", scored([r for r in done if f(r["rr"]) <= 4 and f(r["stop_pct"]) >= 0.004]))
    add("longs only", scored([r for r in done if r["side"] == "long"]))
    add("shorts only", scored([r for r in done if r["side"] == "short"]))
    for m in ("SR", "SMC", "FIB"):
        add(f"rule {m} only", scored([r for r in done if r["method"] == m]))
    # ------------------------------------------------------------------ 6 the tape
    L += ["", "6  THE TAPE these calls lived in (Binance perp daily candles)"]
    for sym in ("BTCUSDT", "ETHUSDT", "XAUUSDT", "QQQUSDT"):
        try:
            d = desk.klines(sym, "1d", int(min(f(r["made_ms"]) for r in rows)) - 86_400_000, None, 12)
            L.append(f"   {sym:<8}" + "  ".join(f"{desk.ts(b[0])[5:10]} {(b[4] / b[1] - 1) * 100:+.1f}%" for b in d))
        except Exception as e:  # noqa: BLE001
            L.append(f"   {sym}: no candles ({type(e).__name__})")
    # ------------------------------------------------------------------ scoring of the registered hypotheses
    n = len(done)
    hit, base = len(wins) / n, sum(f(r["base_p"]) for r in done) / n
    gmean = sum(gross_r(r) for r in done) / n
    small = [r for r in done if f(r["stop_pct"]) < 0.004]
    h1 = abs(hit - base) <= 0.08 and gmean <= 0
    h2 = (sum(frs) / n >= 0.25) and (small and sum(fee_r(f(r["stop_pct"])) for r in small) / len(small) >= 0.4)
    h3 = len(hi_rr) > 0 and not any(r["status"] == "WIN" for r in hi_rr) and sum(f(r["r_net"]) for r in hi_rr) / sum(f(r["r_net"]) for r in done) > 0.3
    h4 = ms[len(ms) // 2] < 180 and sum(x < 0.25 for x in mfe_frac) >= len(mfe_frac) / 2
    h5 = nl / len(losses) >= 0.2
    h6 = not any(v[0] >= 8 and v[2] > 0 and v[1] / v[2] >= 2 for k, v in variants.items() if k != "as logged")
    L += ["", "REGISTERED HYPOTHESES",
          f"  H1 hit rate within 8 points of the random baseline and gross R <= 0 -> {'RIGHT' if h1 else 'WRONG'} (hit {hit * 100:.0f}% vs {base * 100:.0f}%, gross {gmean:+.2f}R a call)",
          f"  H2 fee >= 0.25R a call and >= 0.4R for stops under 0.4% -> {'RIGHT' if h2 else 'WRONG'} ({sum(frs) / n:.2f}R; {sum(fee_r(f(r['stop_pct'])) for r in small) / max(len(small), 1):.2f}R for {len(small)} small-stop calls)",
          f"  H3 RR > 4: no wins and most of the loss -> {'RIGHT' if h3 else 'WRONG'}",
          f"  H4 median time to stop < 3 h and half never reach 25% of the way -> {'RIGHT' if h4 else 'WRONG'}",
          f"  H5 >= 20% of losers touched the target later -> {'RIGHT' if h5 else 'WRONG'} ({nl} of {len(losses)})",
          f"  H6 no variant 2 standard errors above 0 gross -> {'RIGHT' if h6 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

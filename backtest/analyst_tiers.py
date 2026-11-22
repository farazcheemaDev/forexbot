"""THE ANALYST DESK'S REAL CALLS REPLAYED ON $10 / $20 / $50 ACCOUNTS (2026-11-06).

THE USER (2026-11-06): three prompts for a $10 / $20 / $50 crypto account (a rule set with sizing and costs, an adaptive framework with circuit
breakers, a 10-trade simulation) - "based off the Analyst desk strategies, not the other books". This file answers them with the desk's own
rules and its OWN RECORD instead of invented trades.

WHAT IT DOES
    Takes the desk's call log (logs/analyst/calls.csv on the VM; every call's stop %, its net result in R after the 12bp fee, made / exit times)
    and re-books the calls on a different starting balance and risk, with the desk's own booking rules (analyst.new_call / score_open):
      risk_usd = booked equity at the call x risk %;  notional = risk_usd / stop %;  pnl = r_net x risk_usd (r_net already holds the fee);
      a call that would push open notional past 3x equity takes no money ('nobook'); equity moves when a call EXITS (a call made at time t
      sees every exit at or before t, as the hourly cycle scores before it logs new calls).
    Added for small accounts: a call whose notional is under Bitget's $5 minimum cannot be placed ('small').
    Optional rules: step_down (risk halves after 2 booked losses in a row, back after a win), day_stop (no new call on a UTC day once that
    day's closed P&L is down this share of equity).
    CHECK: at $300 / 0.5% the replay must reproduce the desk's own booked equity and its not-booked flags, or nothing below is reported.

WHAT IT DOES NOT MODEL: Bitget's per-coin lot steps (not checked here; the 2026-09-26 audit found rounding errors of 4-9% at $221), slippage beyond the
    logged fill, funding, liquidation
    (at the desk's sizing the notional is at most 3x equity, so isolated liquidation is 32%+ away against stops of at most a few percent).
    The sweet-spot cut (stop >= 0.8%) was found after looking at these same calls: its numbers flatter. 87 resolved calls are a small sample.

    python backtest/analyst_tiers.py [calls.csv]
"""
from __future__ import annotations

import csv
import math
import statistics as st
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import desk  # noqa: E402

FEE, MMR, MIN_NOTIONAL = desk.FEE, desk.MMR, desk.MIN_NOTIONAL
MAX_GROSS = 3.0
SWEET_STOP = 0.008
SCALP_STOP = 0.004
TIERS = (10.0, 20.0, 50.0)
RISKS = (0.5, 1.0, 2.0)
DONE = ("WIN", "LOSS", "EXPIRED")


def fnum(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def load(path):
    rows = []
    for r in csv.DictReader(open(path, encoding="utf-8")):
        rows.append(dict(id=int(r["id"]), made_ms=fnum(r["made_ms"]), exit_ms=fnum(r.get("exit_ms")), symbol=r["symbol"], side=r["side"],
                         method=r["method"], status=r["status"], stop_pct=fnum(r["stop_pct"]), target_pct=fnum(r.get("target_pct")),
                         r=fnum(r.get("r_net")), booked=str(r.get("booked")) == "1", nobook=str(r.get("nobook")) == "1",
                         pnl_usd=fnum(r.get("pnl_usd")) or 0.0))
    return rows


def day_of(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d")


def simulate(rows, capital, risk_pct, pick=None, step_down=False, day_stop=None):
    calls = sorted((r for r in rows if pick is None or pick(r)), key=lambda r: (r["made_ms"], r["id"]))
    eq = peak = float(capital)
    open_, day_pnl, path = [], {}, []
    out = dict(capital=float(capital), risk=risk_pct, taken=0, nobook=0, small=0, paused=0, wins=0, losses=0, worst=0.0, maxdd=0.0)
    state = dict(streak=0)

    def settle(upto):
        nonlocal eq, peak
        due = sorted((o for o in open_ if o["exit_ms"] is not None and o["exit_ms"] <= upto), key=lambda o: (o["exit_ms"], o["id"]))
        for o in due:
            open_.remove(o)
            eq += o["pnl"]
            peak = max(peak, eq)
            out["maxdd"] = max(out["maxdd"], 1.0 - eq / peak)
            if o["pnl"] > 0:
                out["wins"] += 1
                state["streak"] = 0
            else:
                out["losses"] += 1
                state["streak"] += 1
            out["worst"] = min(out["worst"], o["pnl"])
            d = day_of(o["exit_ms"])
            day_pnl[d] = day_pnl.get(d, 0.0) + o["pnl"]
            path.append((o["id"], o["pnl"], eq))

    for r in calls:
        settle(r["made_ms"])
        rp = risk_pct / 2.0 if (step_down and state["streak"] >= 2) else risk_pct
        risk_usd = eq * rp / 100.0
        notional = risk_usd / r["stop_pct"]
        if day_stop is not None and day_pnl.get(day_of(r["made_ms"]), 0.0) <= -day_stop / 100.0 * eq:
            out["paused"] += 1
            continue
        if notional < MIN_NOTIONAL:
            out["small"] += 1
            continue
        if sum(o["notional"] for o in open_) + notional > MAX_GROSS * eq:
            out["nobook"] += 1
            continue
        pnl = r["r"] * risk_usd if r["r"] is not None else 0.0
        open_.append(dict(id=r["id"], exit_ms=r["exit_ms"] if r["r"] is not None else None, notional=notional, pnl=pnl))
        out["taken"] += 1
    settle(float("inf"))
    out.update(equity=eq, ret=eq / capital - 1.0, still_open=len(open_), path=path)
    return out


def check(rows):
    """The replay at the desk's own settings against the desk's own booked P&L and not-booked flags."""
    sim = simulate(rows, 300.0, 0.5)
    want_eq = 300.0 + sum(r["pnl_usd"] for r in rows if r["booked"])
    want_taken = sum(1 for r in rows if not r["nobook"])
    want_nobook = sum(1 for r in rows if r["nobook"])
    return sim["equity"], want_eq, sim["taken"], want_taken, sim["nobook"], want_nobook


def sweet(r):
    return r["stop_pct"] >= SWEET_STOP


def mech(capital, risk_pct, stop):
    risk = capital * risk_pct / 100.0
    notional = risk / stop
    lev = notional / capital
    L = max(1, math.ceil(lev))
    return dict(risk=risk, notional=notional, lev=lev, L=L, margin=notional / L, fee=notional * FEE, fee_r=FEE / stop,
                liq=1.0 / L - MMR, placeable=notional >= MIN_NOTIONAL, capped=notional > MAX_GROSS * capital,
                need_pct=MIN_NOTIONAL * stop / capital * 100.0)


def stats_line(label, rs):
    done = [r for r in rs if r["status"] in DONE and r["r"] is not None]
    if not done:
        return f"  {label:34}  none"
    w = sum(1 for r in done if r["status"] == "WIN")
    return f"  {label:34}  {len(done):>3} resolved, {w:>2} won ({w / len(done):.0%}), mean {st.mean(r['r'] for r in done):+.2f}R a call"


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "logs" / "analyst" / "calls.csv"
    rows = load(path)
    L = [f"backtest/analyst_tiers.py, {datetime.now():%Y-%m-%d %H:%M}; {path.name}: {len(rows)} calls, "
         f"{sum(r['status'] in DONE for r in rows)} resolved, {sum(r['status'] == 'open' for r in rows)} open"]
    e, we, t, wt, nb, wnb = check(rows)
    ok = abs(e - we) < 0.05 and t == wt and nb == wnb
    L.append(f"CHECK at $300 / 0.5% vs the desk's own book: replay equity {e:.4f} vs desk {we:.4f}; taken {t} vs {wt}; not booked {nb} vs {wnb} -> "
             f"{'MATCH' if ok else 'MISMATCH'}")
    if not ok:
        print("\n".join(L))
        raise SystemExit("the replay does not reproduce the desk's own book - not reporting tier results")
    L += ["", "THE RECORD (net of the 12bp fee, in R)", stats_line("all calls", rows),
          stats_line("stop >= 0.8% (sweet spot, post hoc)", [r for r in rows if sweet(r)]),
          stats_line("stop 0.4% - 0.8%", [r for r in rows if SCALP_STOP <= r["stop_pct"] < SWEET_STOP]),
          stats_line("stop < 0.4% (scalp-sized)", [r for r in rows if r["stop_pct"] < SCALP_STOP])]
    for m in ("SR", "FIB", "SMC"):
        L.append(stats_line(f"rule {m}", [r for r in rows if r["method"] == m]))
        L.append(stats_line(f"rule {m}, stop >= 0.8%", [r for r in rows if r["method"] == m and sweet(r)]))

    L += ["", "ACCOUNT MECHANICS at 1% risk (desk sizing: notional = risk / stop; isolated margin = notional / ceil(notional / equity); fee 12bp of notional)",
          f"  {'tier':>5}{'stop':>6}{'risk $':>8}{'notional':>10}{'x equity':>9}{'margin $':>9}{'fee $':>7}{'fee in R':>9}{'liq away':>9}  placeable? / risk % needed for $5"]
    for cap in TIERS:
        for stop in (0.004, 0.008, 0.016, 0.03):
            m = mech(cap, 1.0, stop)
            flag = "NO (under $5)" if not m["placeable"] else ("over the 3x cap" if m["capped"] else "yes")
            L.append(f"  ${cap:>4.0f}{stop:>6.1%}{m['risk']:>8.2f}{m['notional']:>10.2f}{m['lev']:>9.2f}{m['margin']:>9.2f}{m['fee']:>7.3f}"
                     f"{m['fee_r']:>9.2f}{m['liq']:>9.1%}  {flag}; needs {m['need_pct']:.2f}%")

    L += ["", "REPLAY of the resolved calls on each tier (the desk's booking rules; 'small' = under the $5 minimum, 'nobook' = over the 3x cap)",
          f"  {'set':>6}{'tier':>6}{'risk':>6}{'end $':>9}{'return':>8}{'max fall':>9}{'taken':>6}{'W/L':>8}{'small':>6}{'nobook':>7}{'worst $':>9}"]
    for label, pick in (("all", None), ("sweet", sweet)):
        for cap in TIERS:
            for rk in RISKS:
                s = simulate(rows, cap, rk, pick)
                L.append(f"  {label:>6}{cap:>5.0f}${rk:>5.1f}%{s['equity']:>9.2f}{s['ret']:>8.0%}{s['maxdd']:>9.0%}{s['taken']:>6}"
                         f"{s['wins']:>4}/{s['losses']:<3}{s['small']:>6}{s['nobook']:>7}{s['worst']:>9.2f}")

    L += ["", "ADAPTIVE RULES at 1% risk (step_down = risk halves after 2 booked losses in a row; day_stop = no new call once the day is down 2% of equity)",
          f"  {'set':>6}{'tier':>6}{'rule':>22}{'end $':>9}{'return':>8}{'max fall':>9}{'taken':>6}{'paused':>7}"]
    for label, pick in (("all", None), ("sweet", sweet)):
        for cap in TIERS:
            for name, kw in (("fixed", {}), ("step_down", dict(step_down=True)), ("day_stop 2%", dict(day_stop=2.0)),
                             ("both", dict(step_down=True, day_stop=2.0))):
                s = simulate(rows, cap, 1.0, pick, **kw)
                L.append(f"  {label:>6}{cap:>5.0f}${name:>22}{s['equity']:>9.2f}{s['ret']:>8.0%}{s['maxdd']:>9.0%}{s['taken']:>6}{s['paused']:>7}")

    byid = {r["id"]: r for r in rows}
    L += ["", "THE FIRST TEN TRADES TO CLOSE (sweet-spot calls only - a post-hoc set - at 1% risk, per tier)"]
    for cap in TIERS:
        s = simulate(rows, cap, 1.0, sweet)
        L.append(f"  ${cap:.0f}: start {cap:.2f}")
        for i, (cid, pnl, eqv) in enumerate(s["path"][:10], 1):
            c = byid[cid]
            L.append(f"    {i:>2}. call {cid:>3} {c['symbol']:8} {c['side']:5} {c['method']:3} stop {c['stop_pct']:.2%} {c['status']:7} {c['r']:+.2f}R"
                     f"  ${pnl:+.3f}  -> ${eqv:.2f}")
    txt = "\n".join(L)
    print(txt)
    (ROOT / "logs" / "analyst_tiers.txt").write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

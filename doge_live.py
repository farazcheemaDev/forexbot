"""DOGE LIVE FORWARD TEST - frozen scalping rules and my own calls, scored on Bitget's real 1-minute bars (2026-10-09).

The user (2026-10-09): analyse the coin today, predict, and "see in real time basically live forward testing ... the end
result will be a strategy for scalping that is working today and worth a shot today". Paper only: no keys, no orders.

TWO RECORDS, both written BEFORE the outcome is known:
  RULES   the rules frozen in logs/doge_live/registered.json (written once by --register, with a timestamp; the loop never
          changes it). Each is one of backtest/doge_adapt.py's menu rules - same signals, same fills: signal on a closed
          bar, entry at the next 1m bar's open, stop first if one bar touches stop and target, time stop. Only signals
          AFTER the registration time count.
  CALLS   my discretionary predictions (--call): side, entry, target, stop, minutes. Market calls fill at the last
          close when made; a limit call must be touched first. WIN = target before stop, LOSS = stop first (or the same
          bar), EXPIRED = neither in time, marked at the last close. Same fee as the rules.
Fees: 12bp a round trip (Bitget taker both sides) is the headline; 4bp (maker both) beside it, optimistic.

    python doge_live.py --register "1m|level_bounce|both|1|1" "5m|bb_revert|both|2|1"   freeze the rules (once)
    python doge_live.py --loop                                                        score every minute
    python doge_live.py --call long 0.08460 0.08520 0.08430 30 "range low bounce"     log a call (entry 'mkt' = now)
    python doge_live.py --status                                                      the scoreboard
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backtest import bitget_1m as bg  # noqa: E402
from backtest import doge_adapt as da  # noqa: E402

D = ROOT / "logs" / "doge_live"
REG, CALLS, TRADES = D / "registered.json", D / "calls.csv", D / "rule_trades.csv"
MIN = 60_000
FEE, FEE_MAKER = 0.0012, 0.0004


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def ts(ms) -> str:
    return f"{pd.Timestamp(int(ms), unit='ms'):%Y-%m-%d %H:%M}"


def parse_rule(s: str) -> tuple:
    tf, name, side, stop_k, tgt_r = s.split("|")
    return (tf, name, side, float(stop_k), float(tgt_r))


def rule_trades(d1: pd.DataFrame, rule: tuple, since_ms: int) -> list:
    """Every trade of `rule` whose signal bar CLOSED after since_ms: closed ones with their outcome, and the open one
    (if any) with its status so far. One position at a time, as the backtest."""
    tf_s, name, side, stop_k, tgt_r = rule
    tf = int(tf_s[:-1])
    b = da.bars(d1, tf)
    sig, A = da.signals(b, d1, tf)
    lo, sh = sig[name]
    lo = lo if side in ("both", "long") else np.zeros_like(lo)
    sh = sh if side in ("both", "short") else np.zeros_like(sh)
    t1, o1, h1, l1, c1 = (d1[k].to_numpy() for k in ("t", "o", "h", "l", "c"))
    pos1 = {int(x): i for i, x in enumerate(t1)}
    H = da.TIME_STOP[tf]
    ct = b.close_t.to_numpy()
    ev = sorted([(i, 1) for i in np.flatnonzero(lo)] + [(i, -1) for i in np.flatnonzero(sh)])
    free_t, out = -1, []
    for i, sd in ev:
        if ct[i] <= free_t:
            continue
        j0 = pos1.get(int(ct[i]))
        if j0 is None:
            if ct[i] >= int(t1[-1]) + MIN and ct[i] > since_ms:      # signal on the last closed bar: entry is NOW
                out.append(dict(signal_t=int(ct[i]), side=sd, status="pending", entry=None))
                free_t = np.inf
            continue
        e = o1[j0]
        dist = stop_k * A[i]
        if not np.isfinite(dist) or dist <= 0:
            continue
        stop, tgt = e - sd * dist, e + sd * tgt_r * dist
        end = min(j0 + H, len(t1))
        hh, ll = h1[j0:end], l1[j0:end]
        s_hit = (ll <= stop) if sd > 0 else (hh >= stop)
        t_hit = (hh >= tgt) if sd > 0 else (ll <= tgt)
        si, ti = np.flatnonzero(s_hit), np.flatnonzero(t_hit)
        s0 = si[0] if len(si) else H
        g0 = ti[0] if len(ti) else H
        rec = dict(signal_t=int(ct[i]), entry_t=int(t1[j0]), side=sd, entry=e, stop=stop, target=tgt)
        if s0 <= g0 and s0 < end - j0:
            k = j0 + s0
            x = stop if k == j0 else (min(o1[k], stop) if sd > 0 else max(o1[k], stop))
            rec.update(status="closed", why="stop", exit_t=int(t1[k]) + MIN, exit=x)
        elif g0 < end - j0:
            k = j0 + g0
            rec.update(status="closed", why="target", exit_t=int(t1[k]) + MIN, exit=tgt)
        elif end - j0 >= H:
            k = j0 + H - 1
            rec.update(status="closed", why="time", exit_t=int(t1[k]) + MIN, exit=c1[k])
        else:
            rec.update(status="open", last=c1[-1])
            if ct[i] > since_ms:
                out.append(rec)
            free_t = np.inf
            continue
        free_t = rec["exit_t"]
        if ct[i] > since_ms:
            out.append(rec)
    for r in out:
        if r["status"] == "closed":
            r["gross"] = r["side"] * (r["exit"] / r["entry"] - 1)
    return out


def resolve_call(c: dict, d1: pd.DataFrame) -> dict:
    """Score one call on the 1m bars after it was made."""
    t1, o1, h1, l1, c1 = (d1[k].to_numpy() for k in ("t", "o", "h", "l", "c"))
    sd = 1 if c["side"] == "long" else -1
    made, exp = int(c["made_ms"]), int(c["made_ms"]) + int(c["minutes"]) * MIN
    i0 = int(np.searchsorted(t1, made // MIN * MIN + MIN))           # the first bar that opens after the call
    if i0 >= len(t1):
        return dict(c, status="waiting")
    entry, j = float(c["entry"]), i0
    if c.get("limit"):
        filled = None
        for k in range(i0, len(t1)):
            if t1[k] >= exp:
                break
            if (sd > 0 and l1[k] <= entry) or (sd < 0 and h1[k] >= entry):
                filled = k
                break
        if filled is None:
            return dict(c, status="unfilled" if t1[-1] + MIN >= exp else "waiting")
        j = filled
    tgt, stop = float(c["target"]), float(c["stop"])
    for k in range(j, len(t1)):
        if t1[k] >= exp:
            x = c1[k - 1]
            return dict(c, status="expired", exit=x, gross=sd * (x / entry - 1), exit_t=ts(t1[k]))
        s_hit = (l1[k] <= stop) if sd > 0 else (h1[k] >= stop)
        g_hit = (h1[k] >= tgt) if sd > 0 else (l1[k] <= tgt)
        if s_hit:
            return dict(c, status="LOSS", exit=stop, gross=sd * (stop / entry - 1), exit_t=ts(t1[k] + MIN))
        if g_hit:
            return dict(c, status="WIN", exit=tgt, gross=sd * (tgt / entry - 1), exit_t=ts(t1[k] + MIN))
    return dict(c, status="open", last=c1[-1], unreal=sd * (c1[-1] / entry - 1))


def load_calls() -> list:
    return pd.read_csv(CALLS).to_dict("records") if CALLS.exists() else []


def scoreboard(d1: pd.DataFrame, say=print):
    lines = [f"DOGE LIVE FORWARD TEST - {ts(now_ms())} UTC, last closed bar {ts(d1.t.iloc[-1])}, price {d1.c.iloc[-1]:.5f}"]
    if REG.exists():
        reg = json.loads(REG.read_text())
        since = int(reg["registered_ms"])
        lines.append(f"RULES frozen {ts(since)} UTC ({(now_ms() - since) / 3_600_000:.1f}h ago) - net at 12bp (4bp maker in brackets), 1x:")
        allc, rows = [], []
        for s in reg["rules"]:
            tr = rule_trades(d1, parse_rule(s), since)
            cl = [x for x in tr if x["status"] == "closed"]
            g = np.array([x["gross"] for x in cl])
            allc += list(g)
            op = [x for x in tr if x["status"] in ("open", "pending")]
            net = (g - FEE) if len(g) else g
            lines.append(f"  {s:32} {len(cl):3} closed, win {np.mean(net > 0) * 100 if len(g) else 0:3.0f}% | net "
                         f"{net.sum() * 100 if len(g) else 0:+6.2f}% ({(g - FEE_MAKER).sum() * 100 if len(g) else 0:+.2f}%) | "
                         f"avg {net.mean() * 100 if len(g) else 0:+.3f}% a trade" + (" | OPEN " + (
                             f"{'long' if op[0]['side'] > 0 else 'short'} @{op[0]['entry']:.5f} stop {op[0]['stop']:.5f} "
                             f"target {op[0]['target']:.5f}" if op[0].get("entry") else "entering now") if op else ""))
            for x in cl:
                rows.append(dict(rule=s, signal=ts(x["signal_t"]), entry_t=ts(x["entry_t"]), side=x["side"], entry=x["entry"],
                                 stop=x["stop"], target=x["target"], exit_t=ts(x["exit_t"]), exit=x["exit"], why=x["why"],
                                 net_12bp=round((x["gross"] - FEE) * 100, 4)))
        if rows:
            D.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(rows).to_csv(TRADES, index=False)
        g = np.array(allc)
        if len(g):
            lines.append(f"  ALL RULES: {len(g)} trades, net {((g - FEE).sum()) * 100:+.2f}% at 12bp, {((g - FEE_MAKER).sum()) * 100:+.2f}% "
                         f"at 4bp; wins {np.mean(g - FEE > 0) * 100:.0f}%")
    calls = [resolve_call(c, d1) for c in load_calls()]
    if calls:
        lines.append("MY CALLS:")
        done = [c for c in calls if c["status"] in ("WIN", "LOSS", "expired")]
        for c in calls:
            extra = (f"{c['status']} {(c['gross'] - FEE) * 100:+.3f}% net" if c["status"] in ("WIN", "LOSS", "expired")
                     else (f"open, now {c['unreal'] * 100:+.3f}% gross" if c["status"] == "open" else c["status"]))
            lines.append(f"  #{c['id']} {c['made']} {c['side']:5} {'limit ' if c.get('limit') else ''}@{float(c['entry']):.5f} "
                         f"tgt {float(c['target']):.5f} stop {float(c['stop']):.5f} {int(c['minutes'])}m - {extra} | {c['note']}")
        if done:
            g = np.array([c["gross"] for c in done])
            lines.append(f"  CALLS SCORED: {len(done)}, wins {sum(c['status'] == 'WIN' for c in done)}, "
                         f"net {((g - FEE).sum()) * 100:+.2f}% at 12bp")
    for ln in lines:
        say(ln)
    return lines


def data(days: float = 3) -> pd.DataFrame:
    d = bg.fetch("DOGE", days, quiet=True)
    return d[d.t >= d.t.max() - int(days * 86_400_000)].reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--register", nargs="+")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--call", nargs=6, metavar=("SIDE", "ENTRY", "TARGET", "STOP", "MINUTES", "NOTE"))
    a = ap.parse_args()
    D.mkdir(parents=True, exist_ok=True)
    if a.register:
        if REG.exists():
            raise SystemExit(f"already registered: {REG.read_text()} - the rules are frozen; start a new file to change them")
        for s in a.register:
            r = parse_rule(s)
            assert r[0] in ("1m", "5m") and r[2] in ("both", "long", "short"), s
        REG.write_text(json.dumps(dict(registered=ts(now_ms()), registered_ms=now_ms(), rules=a.register), indent=1))
        print(f"frozen at {ts(now_ms())} UTC: {a.register}")
        return
    if a.call:
        side, entry, tgt, stop, minutes, note = a.call
        d1 = data(1)
        last = float(d1.c.iloc[-1])
        limit = entry != "mkt"
        e = last if not limit else float(entry)
        tgt, stop = float(tgt), float(stop)
        assert side in ("long", "short")
        assert (tgt > e > stop) if side == "long" else (tgt < e < stop), "target / stop on the wrong side of the entry"
        calls = load_calls()
        c = dict(id=len(calls) + 1, made=ts(now_ms()), made_ms=now_ms(), side=side, entry=e, limit=limit, target=tgt,
                 stop=stop, minutes=int(minutes), note=note, price_at_call=last)
        pd.DataFrame(calls + [c]).to_csv(CALLS, index=False)
        print(f"call #{c['id']} logged {c['made']} UTC: {side} {'limit' if limit else 'market'} @{e:.5f} target {tgt:.5f} stop "
              f"{stop:.5f}, {minutes} min (price {last:.5f}) - {note}")
        return
    if a.status:
        scoreboard(data())
        return
    if a.loop:
        while True:
            try:
                d1 = data()
                print("-" * 100, flush=True)
                scoreboard(d1, say=lambda m: print(m, flush=True))
            except Exception as e:
                print(f"{ts(now_ms())} loop error: {type(e).__name__}: {str(e)[:150]}", flush=True)
            time.sleep(max(5, 60 - time.time() % 60 + 3))             # 3 s after each minute closes
    ap.print_help()


if __name__ == "__main__":
    main()

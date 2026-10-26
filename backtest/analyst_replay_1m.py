"""HOW HARSH WAS THE REPLAY'S 1-HOUR SCORING? THE SAME CALLS RE-SCORED ON 1-MINUTE CANDLES (2026-10-27)

backtest/analyst_replay.py scores every call on 1-HOUR bars, where a bar that touches both the stop and the target counts as a loss. The live
desk scores on 1-MINUTE bars, which can tell which was hit first, so the replay is the harsher of the two. This measures by how much, on the
calls of the last 90 days (all symbols): each call is re-scored on the 1-minute candles from its entry to its horizon, with the same entry,
stop, target and the same desk.resolve rules; then hit rate, average R, the worst move and the leverage grid are compared with the 1h scoring
of the SAME calls. Nothing is re-tuned; the calls are the replay's (analyst.signals, unchanged).

REGISTERED BEFORE THE FIRST RUN (2026-10-27)
  M1  On 1-minute candles the hit rate rises by 2 to 8 points over the 1h scoring (touching both is a coin flip, not a loss) and the average R
      rises by 0.05 to 0.15 - and stays NEGATIVE: the rules still lose after the 12bp fee.
  M2  The leverage verdict does not change: at 10x the whole account is still wiped out or ends below its start on this slice.
  M3  The worst move (mae) is a little SMALLER on 1-minute bars only where the 1h scoring stopped a call out early; on the whole it is the same.

    python -m backtest.analyst_replay_1m
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import analyst as an  # noqa: E402
import desk  # noqa: E402
from backtest import analyst_replay as rp  # noqa: E402

DAYS = 90
H1 = an.H1


def minute_bars(sym: str, start_ms: int, end_ms: int) -> list:
    return desk.bars_between(sym, start_ms, end_ms, desk.klines)


def main():
    now = int(time.time() * 1000) // H1 * H1
    since = now - DAYS * 86_400_000
    rows = []
    for sym in rp.WATCH:
        bars = rp.history(sym, rp.START_MS, now)
        warm = [b for b in bars if b[0] >= since - 210 * 86_400_000]            # 200 daily bars of levels are enough: the same calls as the full replay
        rows += [r for r in rp.replay_symbol(sym, warm) if r["made_ms"] >= since]
    rows.sort(key=lambda r: r["made_ms"])
    print(f"{len(rows)} calls since {desk.ts(since)[:10]} (1h scoring)", flush=True)
    scored = []
    t0 = time.time()
    for k, r in enumerate(rows):
        hours = an.HOURS[r["method"]]
        call = dict(side=r["side"], mode="market", entry=r["entry"], stop=r["stop"], target=r["target"], expires_ms=r["made_ms"] + hours * H1)
        bars = minute_bars(r["symbol"], r["made_ms"], r["made_ms"] + hours * H1 - 60_000)
        if not bars:
            continue
        res = desk.resolve(call, bars, r["made_ms"] + (hours + 2) * H1)
        if res["status"] not in ("WIN", "LOSS", "EXPIRED"):
            continue
        mae = an.mae_of(res, bars)
        scored.append((r, dict(r, status=res["status"], r_net=res["r_net"], exit_price=res["exit_price"], exit_ms=res["exit_ms"] + 60_000, mae=mae)))
        if k % 50 == 49:
            print(f"  {k + 1}/{len(rows)} re-scored ({time.time() - t0:.0f}s)", flush=True)
    a, b = [x[0] for x in scored], [x[1] for x in scored]
    sa, sb = an.stats(a), an.stats(b)
    print(f"\n{len(scored)} calls re-scored")
    for lab, s in (("1h bars  ", sa), ("1m bars  ", sb)):
        print(f"  {lab}: hit {s['hit'] * 100:.1f}% (random on 1h bars {s['baseline'] * 100:.1f}%, break-even {s['breakeven'] * 100:.1f}%), avg {s['avg_r']:+.3f}R, "
              f"wins {s['wins']} losses {s['losses']} expired {s['expired']}")
    print(f"  M1: hit {100 * (sb['hit'] - sa['hit']):+.1f} points, avg R {sb['avg_r'] - sa['avg_r']:+.3f}; still negative after fees: {sb['avg_r'] < 0}")
    for lab, rr in (("1h", a), ("1m", b)):
        print(f"  grid on the {lab} scoring (end $ from $100 / taken / liquidated):  " + "   ".join(
            f"{x}x ${an.scenario(rr, 100, x)['equity']:.2f} / {an.scenario(rr, 100, x)['taken']} / {an.scenario(rr, 100, x)['liquidated']}" for x in (1, 3, 10, 20, 30)))
    same = sum(abs(x[0]["mae"] - x[1]["mae"]) < 5e-4 for x in scored) / len(scored)
    print(f"  M3: worst move within 0.05 points on {same * 100:.0f}% of calls; mean mae 1h {sum(x[0]['mae'] for x in scored) / len(scored) * 100:.2f}% "
          f"vs 1m {sum(x[1]['mae'] for x in scored) / len(scored) * 100:.2f}%")
    out = dict(days=DAYS, calls=len(scored), s1h={k: sa.get(k) for k in ("hit", "baseline", "breakeven", "avg_r", "wins", "losses", "expired")},
               s1m={k: sb.get(k) for k in ("hit", "baseline", "breakeven", "avg_r", "wins", "losses", "expired")})
    (ROOT / "logs" / "analyst_replay_1m.json").write_text(json.dumps(out))
    full = ROOT / "analyst_replay.json"
    if full.exists():                                                 # the dashboard shows this next to the replay's own numbers
        r = json.loads(full.read_text())
        r["check_1m"] = out
        full.write_text(json.dumps(r, separators=(",", ":")))


if __name__ == "__main__":
    main()

"""A blind self-test: can Claude call his direction from the pre-entry shape alone? (2026-11-14)

THE USER: "it should be you figuring out, not me." So I take the test. `make` writes the 53 pre-entry price shapes (points from
entry) in a shuffled blind order, with NO side / date / outcome - only what is visible before his click. I read blind_charts.txt,
commit one call (u = +7 first / up, d = -7 first / down) per blind id WITHOUT opening blind_key.json, then `score` grades them.

    python -m backtest.his_blind make
    python -m backtest.his_blind score u d u d ...     (53 calls, in blind-id order)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = Path("C:/Users/HP/AppData/Local/Temp/claude/fef2cc426e076a16/20580fec-5e7c-4155-b549-2f55b3e95bb2/scratchpad/his_trainer.json")
CH = ROOT / "logs" / "his_blind_charts.txt"
KEY = ROOT / "logs" / "his_blind_key.json"
import random


def closes(card):
    """close (points from entry) per minute, as a dict m->c."""
    return {c[0]: c[4] for c in card["candles"]}


def make():
    cards = json.loads(SRC.read_text())
    rng = random.Random(20261114)
    order = list(range(len(cards)))
    rng.shuffle(order)
    key, lines = {}, []
    for bid, i in enumerate(order, 1):
        card = cards[i]
        truth = "u" if (card["side"] == 1) == (card["outcome"] == "WON") else "d"
        key[bid] = truth
        cl = closes(card)
        last = [cl.get(m) for m in range(-20, 1)]
        last = [round(x, 1) if x is not None else None for x in last]
        t60 = cl.get(-60); t30 = cl.get(-30); t10 = cl.get(-10)
        trend = f"-60m {t60:+.0f}  -30m {t30:+.0f}  -10m {t10:+.0f}  entry 0.0" if None not in (t60, t30, t10) else "trend n/a"
        lines.append(f"#{bid:02d}  {trend}\n       last 20m closes (pts from entry): " +
                     " ".join(f"{x:+.0f}" if x is not None else "--" for x in last))
    CH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    KEY.write_text(json.dumps(key), encoding="utf-8")
    print(f"wrote {CH} ({len(key)} blind charts). Do NOT open {KEY.name}.")


def score(calls):
    key = json.loads(KEY.read_text())
    calls = [c.lower() for c in calls if c.lower() in ("u", "d")]
    assert len(calls) == len(key), f"need {len(key)} calls, got {len(calls)}"
    ok = sum(calls[b - 1] == key[str(b)] for b in range(1, len(key) + 1))
    n = len(key)
    import math
    # one-sided binomial tail P(>= ok) under p=0.5
    p = sum(math.comb(n, k) for k in range(ok, n + 1)) / 2**n
    print(f"my blind calls: {ok}/{n} = {ok / n * 100:.0f}% correct (coin flip 50%, him 92%); P(>= this by chance) = {p:.3f}")
    up = sum(v == "u" for v in key.values())
    print(f"truth was up {up}/{n}, down {n - up}/{n}; I called up {calls.count('u')}, down {calls.count('d')}")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "make":
        make()
    elif len(sys.argv) >= 2 and sys.argv[1] == "score":
        score(sys.argv[2:])
    else:
        print(__doc__)

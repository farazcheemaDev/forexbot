"""Clean blind test: can Claude call direction on RANDOM NASDAQ charts it has never seen the outcome of? (2026-11-14)

The user: I got 70% on his charts - try random ones. This is uncontaminated (I have never seen these outcomes). `make` draws 60 random
NASDAQ moments in his two windows across 2026, writes the pre-entry shape (points from entry) in blind order with NO outcome, keeps a
hidden key. I read random_charts.txt, commit one call (u = +7 first, d = -7 first) each WITHOUT opening random_key.json, then `score`.
If I beat 50% here, chart-reading has a real directional edge; if ~50%, my 70% on his 53 was his-moment-specific, not a general skill.

    python -m backtest.his_blind_random make
    python -m backtest.his_blind_random score u d u d ...
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CH = ROOT / "logs" / "random_charts.txt"
KEY = ROOT / "logs" / "random_key.json"
WINDOWS = [(15 * 3600, 15 * 3600 + 45 * 60), (18 * 3600 + 15 * 60, 19 * 3600 + 15 * 60)]
K, RACE_S, N = 7.0, 10 * 60, 60


def series_around(mt5, day, sec):
    a = pd.Timestamp(f"{day}", tz="UTC") + pd.Timedelta(seconds=sec - 65 * 60)
    b = pd.Timestamp(f"{day}", tz="UTC") + pd.Timedelta(seconds=sec + 16 * 60)
    tk = mt5.copy_ticks_range("USTECm", a.tz_localize(None).tz_localize("UTC").to_pydatetime(),
                              b.tz_localize(None).tz_localize("UTC").to_pydatetime(), mt5.COPY_TICKS_ALL)
    if tk is None or len(tk) < 500:
        return None
    s = pd.Series((tk["bid"] + tk["ask"]) / 2.0, index=pd.to_datetime(tk["time_msc"], unit="ms"))
    return s[~s.index.duplicated(keep="last")].resample("1s").last().ffill()


def make():
    import MetaTrader5 as mt5
    assert mt5.initialize(), mt5.last_error()
    mt5.symbol_select("USTECm", True)
    days = list(pd.bdate_range("2026-01-05", "2026-11-13").strftime("%Y-%m-%d"))
    rng = random.Random(777)
    key, lines, got = {}, [], 0
    tries = 0
    while got < N and tries < N * 6:
        tries += 1
        day = rng.choice(days)
        w0, w1 = rng.choice(WINDOWS)
        sec = rng.randrange(w0, w1, 60) + 13
        s = series_around(mt5, day, sec)
        if s is None:
            continue
        sod = (s.index.hour * 3600 + s.index.minute * 60 + s.index.second).to_numpy()
        t = {int(v): k for k, v in enumerate(sod)}
        i = t.get(sec)
        if i is None or i < 60 * 60 or i + RACE_S + 1 >= len(s):
            continue
        mid = s.to_numpy()
        e = mid[i]
        seg = mid[i + 1:i + 1 + RACE_S] - e
        up = np.flatnonzero(seg >= K)
        dn = np.flatnonzero(seg <= -K)
        if not len(up) and not len(dn):
            continue
        truth = "u" if (len(up) and (not len(dn) or up[0] < dn[0])) else "d"
        got += 1
        key[got] = truth
        cl = {m: mid[t[sec + m * 60]] - e for m in range(-60, 1) if (sec + m * 60) in t}
        last = [round(cl[m], 1) if m in cl else None for m in range(-20, 1)]
        t60, t30, t10 = cl.get(-60), cl.get(-30), cl.get(-10)
        trend = f"-60m {t60:+.0f}  -30m {t30:+.0f}  -10m {t10:+.0f}  entry 0.0" if None not in (t60, t30, t10) else "trend n/a"
        lines.append(f"#{got:02d}  {trend}\n       last 20m closes (pts from entry): " +
                     " ".join(f"{x:+.0f}" if x is not None else "--" for x in last))
    mt5.shutdown()
    # shuffle blind order
    order = list(range(1, got + 1))
    rng.shuffle(order)
    remap = {old: new for new, old in enumerate(order, 1)}
    blines = [None] * got
    bkey = {}
    for old_line, old in zip(lines, range(1, got + 1)):
        new = remap[old]
        body = old_line.split("  ", 1)[1]
        blines[new - 1] = f"#{new:02d}  {body}"
        bkey[new] = key[old]
    CH.write_text("\n".join(blines) + "\n", encoding="utf-8")
    KEY.write_text(json.dumps(bkey), encoding="utf-8")
    base = sum(v == "u" for v in bkey.values())
    print(f"wrote {CH} ({got} random blind charts). +7-first truth: {base}/{got}. Do NOT open {KEY.name}.")


def score(calls):
    import math
    key = json.loads(KEY.read_text())
    calls = [c.lower() for c in calls if c.lower() in ("u", "d")]
    assert len(calls) == len(key), f"need {len(key)}, got {len(calls)}"
    n = len(key)
    ok = sum(calls[b - 1] == key[str(b)] for b in range(1, n + 1))
    p = sum(math.comb(n, k) for k in range(ok, n + 1)) / 2**n
    print(f"random blind calls: {ok}/{n} = {ok / n * 100:.0f}% (coin flip 50%); P(>= by chance) = {p:.3f}")
    up = sum(v == "u" for v in key.values())
    print(f"truth up {up}/{n}, down {n - up}/{n}; I called up {calls.count('u')}, down {calls.count('d')}")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "make":
        make()
    elif len(sys.argv) >= 2 and sys.argv[1] == "score":
        score(sys.argv[2:])
    else:
        print(__doc__)

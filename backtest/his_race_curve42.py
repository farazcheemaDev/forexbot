"""HIS RACE CURVE ON ALL 42 ENTRIES (corrected clock) - how his edge changes with the size of the move (2026-10-13)

his_race_curve.py (s32) measured +-2..+-15 on the 25 clean summer entries; this repeats it on every NASDAQ entry with
Exness ticks at the corrected clock (his_tape.entries), against the same sitting's moments (+-1..20 min, his direction).
Also printed: a driftless random walk whose +-7 outcome matches his (won 88%) - what you would see if nothing but the
+-7 result were special about his entries (gambler's ruin, conditioned on which side was hit first).

RESULT (2026-10-13, logs/his_race_curve42.txt): his 62 / 71 / 74 / 71 / 73 / 88 / 83 / 83 / 88 / 88 / 84% at +-2..+-15
    against 53-59% for his sittings' other moments. No peak at his +7 target (s32's 88-then-80 was 25-trade noise).
    Against a driftless walk with his +-7 outcome: below 7 points his paths look like that walk (62 vs 61% at +-2, 74
    vs 72% at +-4 - nothing special in the first points); above 7 the move keeps going his way far more than the walk
    (88 vs 76% at +-10, 88 vs 72% at +-12, 84 vs 68% at +-15). He picks the start of a move that runs 15+ points, not
    a 7-point blip - and the first few points of it are noise.

    python -m backtest.his_race_curve42
"""
import pickle
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import backtest.his_tape as TP  # noqa: E402
from backtest.his_race_curve import race2  # noqa: E402

TS = (2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15)


def main():
    x = TP.entries()
    ticks = pickle.loads(TP.TICKS.read_bytes())
    his, near = {T: [] for T in TS}, {T: [] for T in TS}
    for r in x.itertuples():
        day = ticks.get(r.d)
        if day is None or r.t < 960:
            continue
        ts, mid, _ = day
        others = x[x.d == r.d].t.to_numpy()
        for T in TS:
            v = race2(ts, mid, r.t, r.s, 600, T, T)
            if v is not None:
                his[T].append(v)
        for m in list(range(-20, 0)) + list(range(1, 21)):
            t = r.t + 60 * m
            if t <= 960 or np.min(np.abs(others - t)) < 60:
                continue
            for T in TS:
                v = race2(ts, mid, t, r.s, 600, T, T)
                if v is not None:
                    near[T].append(v)
    p7 = np.mean(his[7])

    def hind(T):
        # P(win +-T) on a driftless walk whose +-7 outcome matches his (won with p7): below 7, the walk conditioned on
        # reaching +7 first wins +-T with (T+7)/14, one conditioned on -7 first with (7-T)/14; above 7, from +7 (or -7)
        # it reaches +T before -T with (7+T)/2T (or (T-7)/2T)
        if T <= 7:
            return p7 * (T + 7) / 14 + (1 - p7) * (7 - T) / 14
        return p7 * (7 + T) / (2 * T) + (1 - p7) * (T - 7) / (2 * T)
    out = ["backtest/his_race_curve42.py - race to +-T within 600 s, his entries (corrected clock) vs his sittings' other moments",
           "T          " + "".join(f"{T:>7}" for T in TS),
           "his        " + "".join(f"{np.mean(his[T]) * 100:>6.0f}%" for T in TS),
           "n          " + "".join(f"{len(his[T]):>7}" for T in TS),
           "sittings   " + "".join(f"{np.mean(near[T]) * 100:>6.0f}%" for T in TS),
           "hindsight  " + "".join(f"{hind(T) * 100:>6.0f}%" for T in TS) + "   (picked only for winning +-7, random walk after)"]
    txt = "\n".join(out)
    (ROOT / "logs" / "his_race_curve42.txt").write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

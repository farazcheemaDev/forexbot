"""DOES THE EXNESS NASDAQ QUOTE LAG THE CME FUTURES? - a lead-lag edge of our own (doc 21).

WHY
    his_basis.py (his_strategy.md s40) found, incidentally, that betting AGAINST Exness following the futures lost:
    "Exness follows the futures" won 56-62% of +-7 races at top-decile futures-cash deviations. That was measured on
    overlapping moments around the trader's entries - not a valid sample. If the Exness USTECm quote lags the CME
    NQ futures by seconds, a bot that watches the futures can trade Exness in the direction the futures already
    went. This is the one market-data edge class doc 11 left open for a retail account: it is priced within a second
    by co-located bots on the exchanges, but a broker's CFD quote can lag.

DATA (already local)
    CME NQ futures mid each second (Databento bbo-1s, 31 windows, ~23 h), Exness USTECm ticks (mid and spread).

TESTS
    1. LAG: correlation of 1-s futures returns with 1-s Exness returns k seconds later, k = -5..+10.
    2. CATCH-UP: when the futures moved >= M points over the last L seconds and Exness moved less than half of that,
       how far does Exness move in the futures' direction over the next 1 / 3 / 5 / 10 / 30 s? Against the Exness
       spread paid to enter and exit.
    3. THE RULE, net: enter Exness at the quote 1 s after the signal (a realistic reaction), exit after H seconds at the
       quote. Points per trade after the spread.

REGISTERED PREDICTIONS (2026-10-04, before running)
    1. The correlation peaks at k = 0; the k = +1 value is under a third of the k = 0 value. Exness lags the futures by
       well under a second, so 1-second data sees almost no lead.
    2. The catch-up after an unmatched >= 2-point futures move is under 1 point on average.
    3. The rule nets below zero after the spread at every horizon. The 56-62% in s40 was momentum around his entries.

    python -m backtest.nq_leadlag
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_basis import futures_mid  # noqa: E402
from backtest.his_tape import TICKS, entries, windows  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MOVES = (1.0, 2.0, 3.0)
LOOK = (1, 2, 3, 5)
HOLD = (1, 3, 5, 10, 30)


def paired():
    """Per window: a DataFrame indexed by UTC second with fut, cash, spr."""
    fut = futures_mid()
    fut = fut[(fut > 1000) & np.isfinite(fut)]
    ticks = pickle.loads(TICKS.read_bytes())
    out = []
    for a, b in windows(entries()):
        et = a.tz_localize("UTC").tz_convert("America/New_York").tz_localize(None)
        d = et.normalize()
        day = ticks.get(d)
        if day is None:
            continue
        ts, mid, spr = day
        base = (d + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC").tz_localize(None)
        sec = pd.date_range(a.floor("s"), b.floor("s"), freq="1s")
        s0 = (sec - base).total_seconds().to_numpy()
        k = np.searchsorted(ts, s0, side="right") - 1
        ok = (k >= 0) & (s0 <= ts[-1])
        f = fut.reindex(sec, method="ffill").to_numpy(float)
        w = pd.DataFrame({"fut": f, "cash": np.where(ok, mid[np.clip(k, 0, None)], np.nan),
                          "spr": np.where(ok, spr[np.clip(k, 0, None)], np.nan)}, index=sec).dropna()
        if len(w) > 600:
            out.append(w)
    return out


def main():
    P = paired()
    n_sec = sum(len(w) for w in P)
    out = [f"{len(P)} windows, {n_sec:,} paired seconds of CME NQ futures (bbo-1s) and Exness USTECm; "
           f"Exness spread median {np.median(np.concatenate([w.spr.to_numpy() for w in P])):.2f} pts"]

    out.append("\n1. LAG - corr(futures 1-s return at t, Exness 1-s return at t+k)")
    cc = []
    for k in range(-5, 11):
        a, b = [], []
        for w in P:
            df, dc = w.fut.diff().to_numpy(), w.cash.diff().to_numpy()
            if k >= 0:
                a.append(df[1:len(df) - k]); b.append(dc[1 + k:])
            else:
                a.append(df[1 - k:]); b.append(dc[1:len(dc) + k])
        a, b = np.concatenate(a), np.concatenate(b)
        m = np.isfinite(a) & np.isfinite(b)
        cc.append((k, float(np.corrcoef(a[m], b[m])[0, 1])))
    out.append("  " + "  ".join(f"k{k:+d}:{c:+.2f}" for k, c in cc))

    out.append("\n2. CATCH-UP - futures moved >= M pts over the last L s, Exness moved < half of it;"
               " Exness's next move in the futures' direction (pts)")
    out.append(f"  {'M':>4}{'L':>4}{'events':>8}" + "".join(f"{f'+{h}s':>8}" for h in HOLD))
    best = None
    for M in MOVES:
        for L in LOOK:
            ev = {h: [] for h in HOLD}
            cnt = 0
            for w in P:
                f, c = w.fut.to_numpy(), w.cash.to_numpy()
                df = f[L:] - f[:-L]
                dc = c[L:] - c[:-L]
                idx = np.nonzero((np.abs(df) >= M) & (np.abs(dc) < np.abs(df) / 2))[0] + L
                last = -10**9
                for i in idx:
                    if i - last < 30:                  # one event per 30 s, so events do not overlap
                        continue
                    last = i
                    sgn = np.sign(f[i] - f[i - L])
                    cnt += 1
                    for h in HOLD:
                        if i + 1 + h < len(c):
                            ev[h].append(sgn * (c[i + 1 + h] - c[i + 1]))
            out.append(f"  {M:>4.0f}{L:>4}{cnt:>8}" + "".join(f"{np.mean(ev[h]) if ev[h] else np.nan:>+8.2f}"
                                                            for h in HOLD))
            if ev[HOLD[1]] and (best is None or np.mean(ev[HOLD[1]]) > best[0]):
                best = (np.mean(ev[HOLD[1]]), M, L, cnt)
    sp = float(np.median(np.concatenate([w.spr.to_numpy() for w in P])))
    out.append(f"\n3. NET - entered at the quote 1 s after the signal, out H s later at the quote: the move above "
               f"minus one spread ({sp:.2f} pts).")
    if best:
        out.append(f"  best cell at +3 s: M {best[1]:.0f}, L {best[2]} s, {best[3]} events, "
                   f"{best[0]:+.2f} pts gross -> {best[0] - sp:+.2f} pts net")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "nq_leadlag.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()

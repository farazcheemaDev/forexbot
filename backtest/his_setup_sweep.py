"""His exact setup, strength swept: can momentum continuation at his moments be mechanized? (2026-11-14)

THE USER: "I want his edge, there must be something logical and simple" -> run the one framing never run exactly as his setup.
His setup, from the notes (s30, s34, s55, s67, s73): in his two time windows, the day in a trend, a STRONG recent move, a SHALLOW pullback,
enter ~13 s after a 1-minute close as it resumes in the trend direction. The question: sweep the momentum STRENGTH; does the +-7 race (his own
measure) ever reach ~80%+? If yes, that is a mechanizable rule and we would have his edge. If no at every strength, his 88% is discretionary
selection, not a threshold.

DATA   Exness USTECm ticks via MT5 (2026-01 on), resampled to a 1-second mid, per UTC trading day.
WINDOWS  his two clusters: 15:00-15:45 and 18:15-19:15 UTC (20:00-20:45 / 23:15-00:15 Pakistan, UTC+5).
SETUP at a candidate second t (each 1-min close + 13 s inside a window), using ONLY data <= t:
  trend  = sign(mid(t) - mid(t-30min)); require |30-min move| >= 10 pts (a real trend).
  over the last 15 min: swing high H, swing low L; impulse = H-L (points) = the STRENGTH that is swept.
  pullback: for an uptrend, retrace = (H - mid(t)) / impulse must be in [0.1, 0.6] (shallow, not a full reversal); mirror for downtrend.
  resume: mid(t) - mid(t-60s) has the trend sign (turning back the trend way) -> enter in the trend direction.
RACE   from entry mid e: +7 before -7 within 10 min on the 1-s series. win = +7 first (his ~88% is on this measure).
SWEEP  impulse strength thresholds 0 / 10 / 20 / 30 / 50 / 80 pts (keep setups with impulse >= threshold).
CONTROLS  (a) every 1-min-close+13s moment in the windows, trend direction, same race (no setup filter);
          (b) random direction at those moments. Net at 2.0 pts round-trip cost (his spread ~2.16).

REGISTERED BEFORE THE RUN (2026-11-14)
  P1  No strength threshold with >= 30 setups reaches a 75% race win rate.                                      (80%)
  P2  The race win rate stays within 48-60% across all strength thresholds (continuation ~ a coin flip on direction). (70%)
  P3  Higher strength does NOT lift the race win rate monotonically toward his 88%.                             (75%)
  P4  His setup beats the window baseline by < 8 points of race win rate at every strength.                     (70%)
  P5  Net of 2.0 pts cost, no strength cell with >= 30 setups averages >= +1.0 pt a trade.                      (75%)

RESULT (2026-11-14, logs/his_setup_sweep.txt; 225 days, 5,493 setups) - NO mechanical rule. P1-P5 all right.
  His exact setup (his two windows, a trend, a 15-min impulse, a 0.1-0.6 pullback, resume 13s after a 1-min close, trend direction) wins the
  +-7 race 49.2-49.8% at EVERY strength threshold (0-80 pts), against his 88%. The window baseline (every close+13s, trend direction) is exactly
  50.0% (19,348 moments) = random direction 50.0%: inside his windows, with-trend entry is a coin flip. By strength sextile 46-51%, no rise with
  strength. Net -2.0 to -2.2 pts a trade (the cost). So continuation at his moments is NOT directional - the mechanical rule cannot be built,
  which is the same wall as ustec_burst_anatomy.py (burst direction AUC 0.51). His 88% is discretionary selection, not a threshold on any feature.

    python -m backtest.his_setup_sweep
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOG = ROOT / "logs" / "his_setup_sweep.txt"
WINDOWS = [(15 * 3600, 15 * 3600 + 45 * 60), (18 * 3600 + 15 * 60, 19 * 3600 + 15 * 60)]  # seconds-of-day UTC
TREND_S, SWING_S, RESUME_S = 30 * 60, 15 * 60, 60
TRACK, RACE_S, K = 10.0, 10 * 60, 7.0
THRESH = [0, 10, 20, 30, 50, 80]
COST = 2.0
RNG = np.random.default_rng(11)


def day_series(mt5, day):
    a = pd.Timestamp(f"{day} 13:30", tz="UTC")
    b = pd.Timestamp(f"{day} 19:40", tz="UTC")
    tk = mt5.copy_ticks_range("USTECm", a.to_pydatetime(), b.to_pydatetime(), mt5.COPY_TICKS_ALL)
    if tk is None or len(tk) < 2000:
        return None
    s = pd.Series((tk["bid"] + tk["ask"]) / 2.0, index=pd.to_datetime(tk["time_msc"], unit="ms"))
    s = s[~s.index.duplicated(keep="last")].resample("1s").last().ffill()
    return s


def race(mid, i0, side):
    e = mid[i0]
    seg = side * (mid[i0 + 1:i0 + 1 + RACE_S] - e)
    up = np.flatnonzero(seg >= K)
    dn = np.flatnonzero(seg <= -K)
    if not len(up) and not len(dn):
        return np.nan, np.nan
    win = 1.0 if len(up) and (not len(dn) or up[0] < dn[0]) else 0.0
    res = K if win else -K
    return win, res


def main():
    import MetaTrader5 as mt5
    assert mt5.initialize(), mt5.last_error()
    mt5.symbol_select("USTECm", True)
    days = pd.bdate_range("2026-01-02", "2026-11-13").strftime("%Y-%m-%d")
    rows, base, randc = [], [], []
    nday = 0
    for day in days:
        s = day_series(mt5, day)
        if s is None:
            continue
        nday += 1
        mid = s.to_numpy()
        sod = (s.index.hour * 3600 + s.index.minute * 60 + s.index.second).to_numpy()
        t = {int(v): k for k, v in enumerate(sod)}  # second-of-day -> index (last wins)
        def idx(sec):
            return t.get(sec)
        for w0, w1 in WINDOWS:
            for sec in range(w0, w1, 60):
                i = idx(sec + 13)
                if i is None or i < SWING_S + 5 or i + RACE_S + 1 >= len(mid):
                    continue
                i30 = idx(sec + 13 - TREND_S) if idx(sec + 13 - TREND_S) is not None else i - TREND_S
                if i30 < 0:
                    continue
                trend = np.sign(mid[i] - mid[i30])
                if trend == 0 or abs(mid[i] - mid[i30]) < 10:
                    continue
                w = mid[i - SWING_S:i + 1]
                H, L = w.max(), w.min()
                impulse = H - L
                if impulse <= 0:
                    continue
                retr = (H - mid[i]) / impulse if trend > 0 else (mid[i] - L) / impulse
                resume = np.sign(mid[i] - mid[i - RESUME_S])
                # window baseline: every close+13s, trend direction
                wb, rb = race(mid, i, trend)
                if np.isfinite(wb):
                    base.append(wb)
                    randc.append(race(mid, i, RNG.choice([-1, 1]))[0])
                if not (0.1 <= retr <= 0.6 and resume == trend):
                    continue
                win, res = race(mid, i, trend)
                if np.isfinite(win):
                    rows.append((impulse, win, res, day))
    mt5.shutdown()
    R = pd.DataFrame(rows, columns=["impulse", "win", "res", "day"])
    base = np.array([b for b in base if np.isfinite(b)])
    randc = np.array([b for b in randc if np.isfinite(b)])
    L = [f"backtest/his_setup_sweep.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {nday} days, {len(R)} setups, "
         f"{len(base)} window-baseline moments; race +-{K:.0f} pts, {RACE_S // 60}-min cap, cost {COST} pts", "",
         f"WINDOW BASELINE (every 1-min close+13s in his windows, trend direction): race won {base.mean() * 100:.1f}% (n {len(base)}); "
         f"random direction {randc.mean() * 100:.1f}%", "",
         "HIS SETUP by momentum strength (impulse = 15-min swing range):"]
    best = 0.0
    for thr in THRESH:
        g = R[R.impulse >= thr]
        if len(g) < 5:
            L.append(f"  impulse >= {thr:>3} pts: n {len(g):>4}  (too few)")
            continue
        wr = g.win.mean()
        net = g.res.mean() - COST
        # day-clustered se on win rate
        byday = g.groupby("day").win.mean()
        se = byday.std(ddof=1) / np.sqrt(len(byday)) if len(byday) > 2 else np.nan
        best = max(best, wr if len(g) >= 30 else best)
        L.append(f"  impulse >= {thr:>3} pts: n {len(g):>4}  race won {wr * 100:5.1f}% (day-se {se * 100:4.1f})  "
                 f"net {net:+5.2f} pts/trade  excess over baseline {(wr - base.mean()) * 100:+5.1f} pts")
    # strength deciles, to see any monotone rise
    if len(R) > 50:
        R["bin"] = pd.qcut(R.impulse, 6, labels=False, duplicates="drop")
        L += ["", "  by strength sextile:"]
        for b, g in R.groupby("bin"):
            L.append(f"    impulse {g.impulse.min():5.0f}-{g.impulse.max():5.0f} pts: n {len(g):>4}  race {g.win.mean() * 100:5.1f}%  net {g.res.mean() - COST:+5.2f}")
    cells = [(thr, R[R.impulse >= thr]) for thr in THRESH]
    big = [(thr, g.win.mean(), g.res.mean() - COST) for thr, g in cells if len(g) >= 30]
    p1 = not any(wr >= 0.75 for _, wr, _ in big)
    p2 = all(0.48 <= wr <= 0.60 for _, wr, _ in big)
    mono = [wr for _, wr, _ in big]
    p3 = not (len(mono) >= 3 and all(mono[i] < mono[i + 1] for i in range(len(mono) - 1)) and mono[-1] > 0.75)
    p4 = all((wr - base.mean()) < 0.08 for _, wr, _ in big)
    p5 = not any(net >= 1.0 for _, _, net in big)
    L += ["", "PREDICTIONS",
          f"  P1 no >=30-setup cell reaches 75% race ({max((wr for _, wr, _ in big), default=0) * 100:.1f}% max) -> {'RIGHT' if p1 else 'WRONG'}",
          f"  P2 race within 48-60% at every strength -> {'RIGHT' if p2 else 'WRONG'}",
          f"  P3 strength does not lift race monotonically to >75% -> {'RIGHT' if p3 else 'WRONG'}",
          f"  P4 setup beats baseline by < 8 pts everywhere -> {'RIGHT' if p4 else 'WRONG'}",
          f"  P5 no >=30-setup cell nets >= +1.0 pt -> {'RIGHT' if p5 else 'WRONG'}",
          "",
          f"His actual: ~88% race win on 53 trades. Max mechanical cell here: {max((wr for _, wr, _ in big), default=0) * 100:.1f}%."]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    sys.exit(main())

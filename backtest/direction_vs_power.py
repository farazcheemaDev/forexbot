"""'They predicted the direction correctly but not the power - fixed TP / SL is why they failed': tested on the Analyst desk's own calls (2026-11-12)

THE USER: "fixed tp sl dont work, thats why they failed even though they predicted the direction correctly but not the power". If that is true,
the desk's calls should (A) move in the called direction more often / further than random entries once the bracket is taken away, and (B) make
money with exits that let the move decide (no target, a trailing stop, breakeven then trail, or no stop at all).

DATA  the replay's signals (strategy_analysis/data/analyst_replay/candidates_filters_oos.pkl, built by analyst_filters_oos.py; the no-filter
      cooldown gives the replay's own 10,580 calls, 2022-02 .. 2026-10) and its cached 1h bars. Entry = the next bar's open, as the replay.
A  DIRECTION ONLY   signed return from the entry to the close H hours later, H = 1 / 4 / 12 / 24 / 72, no stop, no target; gross, and net of 12bp.
B  POWER            the furthest the price went the call's way (MFE) and against it (MAE) within 24h, in units of the call's own stop distance.
C  EXITS WITHOUT A FIXED TARGET (net R = return / stop distance, less 12bp in R; stop filled at the stop or the open if gapped; trail moves at a close)
     C1 the desk's stop, no target, out at 24h         C2 the same, out at 72h
     C3 the desk's stop, then a 3 x ATR(1h) trail from the best close, up to 72h      C4 the same, up to 168h
     C5 the desk's stop, breakeven after +1R, then the 3 x ATR trail, up to 168h      C6 a 2 x ATR trail from the start, up to 72h
CONTROL  for every call, 2 random entries on the same symbol and side within +-30 days, given the SAME stop distance (%) and the same exits.
         Excess = the call minus the mean of its controls; t over bets (calls of one UTC day and side = one bet). Split 2024-12-07.
THE BAR  the thesis holds if some C exit has net R/bet > 0 with t >= 2 on BOTH halves and a positive excess over its control on both halves.
         'Direction right' = the 24h signed gross return beats the control's with t >= 2 on both halves.

REGISTERED BEFORE THE RUN (2026-11-12)
  T1  Direction is NOT right: the 24h signed gross excess over random entries is under t 2 on at least one half.                   (80%)
  T2  Power: the calls' 24h MFE (in stop units) is no larger than the controls' on both halves.                                     (70%)
  T3  No C exit passes the bar.                                                                                                      (90%)
  T4  Every C exit is still negative per call on both halves (the fee and the stop-outs remain).                                    (75%)
  T5  The C exits earn about the same from random entries: |excess| under 0.05R a call on the holdout for at least 4 of the 6.     (65%)

RESULT (2026-11-12, logs/direction_vs_power.txt; 10,522 calls) - THE THESIS IS REFUTED. T1-T4 right, T5 wrong.
  DIRECTION: per CALL the desk's calls do no better than random entries on the same symbol and side - 24h signed return -0.080% vs -0.049%
  (tune), -0.071% vs +0.047% (holdout); 'right' 50.0-51.5% of the time. The positive per-BET excess (+0.11..+0.27%, t up to 4.6) is the
  day-vote trap of CLAUDE.md s3: quiet days with one call outvote crash days with many; per call it is not there.
  POWER: within 24h the calls run LESS far their way than random entries given the same stop (median MFE 1.55 vs 1.83-1.94 stop-lengths)
  and less far against them - they are quieter moments, not under-captured big moves.
  EXITS: every non-fixed exit (no target 24h / 72h, 3 ATR trail to 72h / 168h, breakeven then trail, 2 ATR trail) is negative per call on
  both halves (-0.06..-0.22R); they beat random entries per call on the tune half and lose to them on the holdout. None passes.
  So the bracket was not what killed the desk: with any exit, its entries are coin flips that pay the fee.

    python -m backtest.direction_vs_power
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import analyst as an  # noqa: E402
from backtest.analyst_filters_oos import CACHE, CAND, SPLIT, take  # noqa: E402

LOG = ROOT / "logs" / "direction_vs_power.txt"
FEE = 0.0012
HS = (1, 4, 12, 24, 72)
EXITS = {"C1 stop, no target, 24h": ("fixed", 24), "C2 stop, no target, 72h": ("fixed", 72), "C3 stop + 3 ATR trail, 72h": ("trail3", 72),
         "C4 stop + 3 ATR trail, 168h": ("trail3", 168), "C5 breakeven at +1R, then trail, 168h": ("be", 168), "C6 2 ATR trail from the start, 72h": ("trail2", 72)}
K_CTL = 2


def sim(o, h, l, c, e, side, stop_pct, atr, mode, max_h):
    """One trade from the open of bar e. Returns the signed return (fraction of the entry)."""
    entry = o[e]
    risk = entry * stop_pct
    stop = entry - side * (2 * atr if mode == "trail2" else risk)
    best = entry
    last = min(e + max_h - 1, len(c) - 1)
    for k in range(e, last + 1):
        if side == 1:
            if l[k] <= stop:
                return (min(o[k], stop) if k > e else stop) / entry - 1
            best = max(best, c[k])
            if mode == "trail3":
                stop = max(stop, best - 3 * atr)
            elif mode == "trail2":
                stop = max(stop, best - 2 * atr)
            elif mode == "be" and best >= entry + risk:
                stop = max(stop, entry, best - 3 * atr)
        else:
            if h[k] >= stop:
                return 1 - (max(o[k], stop) if k > e else stop) / entry
            best = min(best, c[k])
            if mode == "trail3":
                stop = min(stop, best + 3 * atr)
            elif mode == "trail2":
                stop = min(stop, best + 2 * atr)
            elif mode == "be" and best <= entry - risk:
                stop = min(stop, entry, best + 3 * atr)
    return side * (c[last] / entry - 1)


def measure(A, e, side, stop_pct):
    o, h, l, c, atr = A
    if e + 170 >= len(c) or not np.isfinite(atr[e - 1]):
        return None
    entry = o[e]
    out = {}
    for H in HS:
        out[f"d{H}"] = side * (c[e + H - 1] / entry - 1)
    hi, lo = h[e:e + 24].max(), l[e:e + 24].min()
    risk = entry * stop_pct
    out["mfe"] = ((hi - entry) if side == 1 else (entry - lo)) / risk
    out["mae"] = ((entry - lo) if side == 1 else (hi - entry)) / risk
    for lab, (mode, mh) in EXITS.items():
        sp = 2 * atr[e - 1] / entry if mode == "trail2" else stop_pct
        out[lab] = sim(o, h, l, c, e, side, stop_pct, atr[e - 1], mode, mh) / sp - FEE / sp
    return out


def arrays(bars):
    b = np.array(bars, float)
    o, h, l, c = b[:, 1], b[:, 2], b[:, 3], b[:, 4]
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    atr = pd.Series(tr).rolling(14).mean().to_numpy()
    return o, h, l, c, atr


def bet_t(v, day, side):
    b = pd.Series(np.asarray(v, float)).groupby([np.asarray(day), np.asarray(side)]).mean()
    se = b.std(ddof=1) / np.sqrt(len(b))
    return float(b.mean()), float(b.mean() / se) if se > 0 else np.nan


def main():
    C = pd.read_pickle(CAND)
    order = {s: k for k, s in enumerate(an.WATCH)}
    C = C.assign(o=C.symbol.map(order)).sort_values(["o", "made_ms"], kind="stable").drop(columns="o").reset_index(drop=True)
    calls = take(C, lambda r: True)
    rng = np.random.default_rng(0)
    A = {s: arrays(json.loads((CACHE / f"{s}_1h.json").read_text())) for s in an.WATCH}
    rows = []
    for r in calls.itertuples(index=False):
        side = 1 if r.side == "long" else -1
        a = A[r.symbol]
        m = measure(a, r.i + 1, side, r.stop_pct)
        if m is None:
            continue
        cs = []
        for _ in range(K_CTL * 4):
            j = int(rng.integers(max(600, r.i - 720), min(len(a[3]) - 200, r.i + 720)))
            if abs(j - r.i) < 24:
                continue
            x = measure(a, j + 1, side, r.stop_pct)
            if x is not None:
                cs.append(x)
            if len(cs) == K_CTL:
                break
        if len(cs) < K_CTL:
            continue
        row = dict(symbol=r.symbol, method=r.method, side=r.side, made_ms=r.made_ms, r_net=r.r_net, stop_pct=r.stop_pct)
        for k in m:
            row[k] = m[k]
            row["c_" + k] = float(np.mean([x[k] for x in cs]))
        rows.append(row)
    D = pd.DataFrame(rows)
    t = pd.to_datetime(D.made_ms, unit="ms")
    D["day"], D["half"] = t.dt.floor("D"), np.where(t < SPLIT, "tune", "hold")
    L = [f"backtest/direction_vs_power.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(D)} of {len(calls)} desk calls with {K_CTL} random-entry controls each; split {SPLIT.date()}",
         f"   the desk as it is (its own bracket): {D.r_net.mean():+.3f}R a call", "",
         "A. DIRECTION ONLY (no stop, no target): signed GROSS return to the close H hours later; 'right' = share of calls above zero"]
    res = {}
    for half in ("tune", "hold"):
        x = D[D.half == half]
        for H in HS:
            m, tt = bet_t(x[f"d{H}"] - x[f"c_d{H}"], x.day, x.side)
            L.append(f"   {half:<5} {H:>3}h  calls {x[f'd{H}'].mean() * 100:+.3f}% (right {(x[f'd{H}'] > 0).mean() * 100:4.1f}%)   random {x[f'c_d{H}'].mean() * 100:+.3f}%   "
                     f"excess {m * 100:+.3f}% (t {tt:+.2f})   net of 12bp {(x[f'd{H}'].mean() - FEE) * 100:+.3f}%")
            res[("d", H, half)] = (m, tt)
    L += ["", "B. POWER within 24h, in units of the call's own stop distance (MFE = furthest its way, MAE = furthest against)"]
    for half in ("tune", "hold"):
        x = D[D.half == half]
        m, tt = bet_t(x.mfe - x.c_mfe, x.day, x.side)
        m2, t2 = bet_t(x.mae - x.c_mae, x.day, x.side)
        L.append(f"   {half:<5} MFE calls {x.mfe.median():.2f} (median) / random {x.c_mfe.median():.2f}; mean excess {m:+.3f} (t {tt:+.2f})   |   "
                 f"MAE calls {x.mae.median():.2f} / random {x.c_mae.median():.2f}; mean excess {m2:+.3f} (t {t2:+.2f})")
        res[("mfe", half)] = (m, tt)
    L += ["", "C. EXITS WITHOUT A FIXED TARGET (net R after 12bp; excess = the call minus its random-entry controls with the same exit)"]
    passed = []
    for lab in EXITS:
        ok = True
        for half in ("tune", "hold"):
            x = D[D.half == half]
            m, tt = bet_t(x[lab], x.day, x.side)
            em, et = bet_t(x[lab] - x["c_" + lab], x.day, x.side)
            L.append(f"   {lab:<38} {half:<5} R/call {x[lab].mean():+.3f}  R/bet {m:+.3f} (t {tt:+.2f})  won {(x[lab] > 0).mean() * 100:4.1f}%  "
                     f"random R/call {x['c_' + lab].mean():+.3f}  excess/bet {em:+.3f} (t {et:+.2f})")
            res[(lab, half)] = dict(rc=x[lab].mean(), rb=m, t=tt, ex=em, exc=x[lab].mean() - x["c_" + lab].mean())
            ok &= m > 0 and tt >= 2 and em > 0
        if ok:
            passed.append(lab)
    L += ["", "   by rule, C4 (stop + 3 ATR trail, 168h), R/call tune | hold: " + "  ".join(
        f"{mth} {D[(D.method == mth) & (D.half == 'tune')]['C4 stop + 3 ATR trail, 168h'].mean():+.3f} | "
        f"{D[(D.method == mth) & (D.half == 'hold')]['C4 stop + 3 ATR trail, 168h'].mean():+.3f}" for mth in ("SR", "FIB", "SMC"))]
    d24 = [res[("d", 24, h)] for h in ("tune", "hold")]
    dir_right = all(m > 0 and t >= 2 for m, t in d24)
    mfe_bigger = all(res[("mfe", h)][0] > 0 and res[("mfe", h)][1] >= 2 for h in ("tune", "hold"))
    all_neg = all(res[(lab, h)]["rc"] < 0 for lab in EXITS for h in ("tune", "hold"))
    same = sum(abs(res[(lab, "hold")]["exc"]) < 0.05 for lab in EXITS)
    L += ["", f"VERDICT: direction right = {dir_right}; exits that pass the bar: {passed or 'none'}", "", "REGISTERED PREDICTIONS",
          f"  T1 direction NOT right at 24h (excess {d24[0][0] * 100:+.3f}% t {d24[0][1]:+.2f} / {d24[1][0] * 100:+.3f}% t {d24[1][1]:+.2f}) -> {'RIGHT' if not dir_right else 'WRONG'}",
          f"  T2 MFE no larger than random on both halves ({res[('mfe', 'tune')][0]:+.3f} t {res[('mfe', 'tune')][1]:+.2f} / {res[('mfe', 'hold')][0]:+.3f} t {res[('mfe', 'hold')][1]:+.2f}) -> "
          f"{'RIGHT' if not mfe_bigger else 'WRONG'}",
          f"  T3 no C exit passes -> {'RIGHT' if not passed else 'WRONG'}",
          f"  T4 every C exit negative per call on both halves -> {'RIGHT' if all_neg else 'WRONG'}",
          f"  T5 |excess| < 0.05R on the holdout for >= 4 of 6 exits ({same}) -> {'RIGHT' if same >= 4 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

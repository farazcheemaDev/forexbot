"""AUDIT CHECK (2026-11-10): a VOLATILITY screen on the market-neutral book.

Two findings that were never joined: (1) indicator_model / all_sources_model: low-volatility coins beat high-volatility
ones in ranks every year 2022-26 (IC +0.10..+0.18), and the spread fails only because the SHORT leg holds squeeze-prone
coins; (2) the live MN book's long leg lost 7 of 7 weeks holding pumped micro-caps.  universe_floor.py tried a VOLUME
floor (no pass).  This tries the screen the IC actually points at: do not rank the most volatile third of the eligible
names (30-day std of daily returns, known at the rebalance close) - both legs, long leg only, short leg only.
k is taken from the FULL eligible count, so every variant holds as many names a side as the base (k-matched).

Book = the machine's: half 30-day momentum, half RSI(14), weekly, +50% short exit, 12bp turnover, real funding,
7 rebalance weekdays.  Split = pair_lab.HOLDOUT (as universe_floor).

THE BAR (registered before the run; universe_floor's): Sharpe higher than the base on BOTH halves on average over the
7 weekdays AND on >= 5 of 7 weekdays on EACH half.

REGISTERED BEFORE RUNNING
  V1 screen on BOTH legs passes: 25%.
  V2 screen on the LONG leg only passes: 30%.
  V3 screen on the SHORT leg only makes the worst week / fall shallower but does not pass on Sharpe: 60%.
  V4 expected failure mode if none pass: wins the holdout, loses the tune half (momentum's money was in the wild names
     in 2020-21).

RESULT (2026-11-10, logs/audit_mn_vol_screen.txt): NO VARIANT PASSES. Sharpe tune / holdout: base +1.38 / +1.36; both legs
  +1.27 / +0.72 (2/7, 0/7 weekdays better); long leg +1.26 / +1.34 (2/7, 3/7); short leg +1.35 / +0.95 (3/7, 0/7).
  V1, V2 wrong as hoped-for passes (predicted unlikely); V3 WRONG (the short-leg screen does not make the worst week or
  the fall shallower); V4 WRONG (the screens lose the HOLDOUT more than the tune half). The book's money is in the wild
  names on both legs. Side fact: the base long leg earns +1.59%/wk on the tune half and -0.05%/wk on the holdout; the
  short leg -0.54% / +1.11% - the book changed legs between halves. No tests / planted-bug round (an audit check).

    python -m backtest.audit_mn_vol_screen
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtest import mn_combos as m  # noqa: E402
from backtest import moderate_retests as mr  # noqa: E402
from backtest import pair_lab as pl  # noqa: E402

HOLD, LOOK, FRAC = 7, 30, 0.1
HOLDOUT = pl.HOLDOUT
Dd = m.ohl()
idx, X_, Fx, ff = Dd["idx"], Dd["X"], Dd["Fx"], Dd["ff"]
C = pd.DataFrame(X_)
d = C.diff()
up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
RSI = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()
MOM = X_ / np.r_[np.full((30, X_.shape[1]), np.nan), X_[:-30]] - 1
VOL = np.log(C).diff().rolling(30, min_periods=20).std().to_numpy()


def run(score_mat, start=0, drop=0.0, legs="both", detail=False):
    rows, pl_, ps_ = [], set(), set()
    for i in range(LOOK + 1 + start, len(idx) - HOLD - 1, HOLD):
        t0 = idx[i]
        ok = (Dd["Em"][Dd["months"][i]] & ((t0.value - Dd["fv"]) // 86_400_000_000_000 >= m.MIN_AGE_D)
              & np.isfinite(X_[i]) & np.isfinite(X_[i - LOOK]))
        if ok.sum() < 20:
            continue
        cand = np.flatnonzero(ok)
        past = score_mat[i, cand]
        k = max(int(len(cand) * FRAC), 3)
        order = cand[np.argsort(np.where(np.isnan(past), np.inf, past), kind="stable")]
        if drop > 0:
            v = VOL[i, cand]
            cut = np.nanquantile(v, 1 - drop)
            wild = set(cand[np.where(np.isnan(v), True, v > cut)])     # unknown volatility counts as wild
        else:
            wild = set()
        oks = [x for x in order if not (x in wild and legs in ("both", "short"))]
        okl = [x for x in order if not (x in wild and legs in ("both", "long"))]
        sh, lo = np.array(oks[:k]), np.array(okl[-k:])
        fwd = (ff[i + HOLD] / X_[i] - 1).copy()
        for x in sh:
            lvl = X_[i, x] * 1.5
            for dd in range(i + 1, i + HOLD + 1):
                if np.isfinite(Dd["Hi"][dd, x]) and Dd["Hi"][dd, x] >= lvl:
                    fwd[x] = max(Dd["Op"][dd, x], lvl) / X_[i, x] - 1
                    break
        fnd = Fx[i + 1:i + HOLD + 1].sum(axis=0)
        gl, gs = 0.5 * fwd[lo].mean(), -0.5 * fwd[sh].mean()
        carry = 0.5 * (-fnd[lo].mean()) + 0.5 * fnd[sh].mean()
        L_, S_ = {Dd["cols"][x] for x in lo}, {Dd["cols"][x] for x in sh}
        cost = m.FEE * min((len(L_ ^ pl_) + len(S_ ^ ps_)) / (4 * k), 1.0)
        pl_, ps_ = L_, S_
        rows.append((t0 + pd.Timedelta(days=HOLD), gl + gs + carry - cost, gl, gs))
    df = pd.DataFrame(rows, columns=["t", "net", "long", "short"]).groupby("t").sum()
    return df if detail else df["net"]


def blend(start, drop, legs, detail=False):
    a, b = run(MOM, start, drop, legs, detail), run(RSI, start, drop, legs, detail)
    return 0.5 * a.add(b, fill_value=0) if not detail else 0.5 * a.add(b, fill_value=0)


def sharpe(s):
    return float(s.mean() / s.std() * np.sqrt(52)) if len(s) > 5 and s.std() > 0 else np.nan


def fall(s):
    c = np.r_[1.0, (1 + s).cumprod().to_numpy()]
    return float((1 - c / np.maximum.accumulate(c)).max())


# parity: with no screen this must be moderate_retests.scored_run
for st in (0, 3):
    a = run(MOM, st)
    b = mr.scored_run(MOM, start=st, stop="short_only", short_stop=0.5)
    assert np.allclose(a.to_numpy(), b.reindex(a.index).to_numpy(), atol=1e-12) and len(a) == len(b), "parity failed"
print("parity with moderate_retests.scored_run: OK;  split", HOLDOUT)

VARS = [("base", 0.0, "both"), ("drop top-vol 1/3, both legs", 1 / 3, "both"), ("drop top-vol 1/3, long leg", 1 / 3, "long"),
        ("drop top-vol 1/3, short leg", 1 / 3, "short"), ("drop top-vol 1/5, both legs", 0.2, "both"),
        ("drop top-vol 1/2, both legs", 0.5, "both")]
RES = {}
for lab, drop, legs in VARS:
    per = []
    for st in range(7):
        df = 0.5 * run(MOM, st, drop, legs, True).add(run(RSI, st, drop, legs, True), fill_value=0)
        per.append(df)
    RES[lab] = per

print(f"\n{'variant':<30}{'half':>8}{'Sharpe':>8}{'days>base':>10}{'wk mean':>9}{'long':>8}{'short':>8}{'worst wk':>9}{'fall':>6}")
for lab, _, _ in VARS:
    for half in ("tune", "holdout"):
        sh, mean, lg, st_, ww, fl, better = [], [], [], [], [], [], 0
        for stn in range(7):
            df = RES[lab][stn]
            y = df[df.index < HOLDOUT] if half == "tune" else df[df.index >= HOLDOUT]
            b = RES["base"][stn]
            yb = b[b.index < HOLDOUT] if half == "tune" else b[b.index >= HOLDOUT]
            sh.append(sharpe(y["net"])); mean.append(y["net"].mean()); lg.append(y["long"].mean()); st_.append(y["short"].mean())
            ww.append(y["net"].min()); fl.append(fall(y["net"]))
            better += sharpe(y["net"]) > sharpe(yb["net"])
        print(f"{lab:<30}{half:>8}{np.mean(sh):>+8.2f}{better:>8}/7{np.mean(mean) * 100:>+8.2f}%{np.mean(lg) * 100:>+7.2f}%"
              f"{np.mean(st_) * 100:>+7.2f}%{np.min(ww) * 100:>+8.1f}%{np.mean(fl) * 100:>5.0f}%")

print("\nby year, mean weekly net % (average of 7 weekdays): base vs both-legs 1/3 vs long-leg 1/3")
tab = {}
for lab in ("base", "drop top-vol 1/3, both legs", "drop top-vol 1/3, long leg", "drop top-vol 1/3, short leg"):
    tab[lab[:26]] = pd.concat([x["net"].groupby(x.index.year).mean() for x in RES[lab]], axis=1).mean(axis=1) * 100
print(pd.DataFrame(tab).round(2).to_string())

"""THE MARKET-NEUTRAL BOOK x WHAT WORKED - the combinations not yet run (2026-10-08, goal: "every combination we
haven't ran").

The book (doc 10, bear_chop.fast_run fshift=1, pair_lab.mn_daily): every 7 days on the point-in-time top-60 (dead coins
in, no stables/gold), rank by 30-day return, long the top decile and short the bottom decile, equal dollars, 1x gross;
fees on the turnover, real funding both legs. Tested so far: lookback 30 / 90, basket width 0.10-0.50, a stop on the
short leg, top-100, a day's lag, a cap on each coin-week (mn_capped.py), regime sizing (ties), as an overlay at
0.5 / 1 / 1.5x. NEVER tested: the day of the week it rebalances on (every published figure is one start day), other
lookbacks and holds, the score (volatility-adjusted / skip-the-last-days / several lookbacks - standard in the
momentum literature), and switching it off in one BTC regime.

    R  the base on all 7 rebalance days (its own bar-phase check, never run)
    L  lookback 14 / 60;  H  hold 3 / 14 days
    S  score: 30-day return / 30-day volatility; 30-day return skipping the last 3 days; mean rank of 14/30/60-day
    G  off (flat) in BEAR weeks; off in BULL weeks (BTC 50-day trend, a day lagged)

PASS (registered): the book is a scalable overlay, so the test is risk-adjusted - Sharpe higher than the base's on the
tune half AND the holdout (split 2024-04-07, by booking date), both on average over the rebalance days and on the worst
rebalance day.

REGISTERED BEFORE RUNNING (2026-10-08):
    R  Sharpe varies by about +-0.3 across the 7 rebalance days, positive on both halves on every day.
    L/H  lookback 14 and hold 3 lose to costs and noise; lookback 60 and hold 14 are weaker than the base. None passes.
    S  volatility-adjusted momentum passes (the literature's most robust tweak); skip-3 and the composite tie.
    G  off-in-bear raises the tune half (2022) and lowers the holdout (bear weeks earn their funding): fails.
       Off-in-bull fails badly (bull weeks are the book's best).

RESULT (2026-10-08, logs/mn_combos.txt, logs/mn_rebalance_days.txt): THE REBALANCE DAY - never checked before -
    decides survival. The base on the 7 days: Sharpe tune +0.79..+1.46, holdout +1.17..+1.84 on six; on start +6 the
    holdout is +0.03 with a 100% fall (2025-09-12 week -99%: MYX squeezed the short basket). Capped +100% (v3) survives
    all 7 (worst day +0.64 / +0.71). The live bot's 30% disaster stop modelled as an exit costs Sharpe (+0.73 / +0.99)
    - and live it is no exit at all: combo_bot's netting re-opens the position 2 minutes later. A short-leg BOOK exit
    at +50% (out until the next rebalance): mean +1.06 / +1.31 (base +1.06 / +1.33), worst day +0.85 / +0.76, falls
    29-42%, worst week -29% - the wipe-out gone at no average cost. The 9 variants: none beats the base's mean Sharpe
    on both halves (lookback 14/60, hold 3/14, vol-adjusted, skip-3, composite, off in bear/bull). Predictions: R +-0.3
    all positive - WRONG (one day wiped out); L/H none pass - right; S vol-adjusted passes - WRONG; G - right.

    python -m backtest.mn_combos
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import pair_lab as pl  # noqa: E402
from backtest.bear_chop import FEE  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.market_neutral import MIN_AGE_D, drop_non_crypto, load_panel  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

LOG = ROOT / "logs" / "mn_combos.txt"
HOLDOUT = pl.HOLDOUT
_D: dict = {}


def data():
    if not _D:
        C, F, first = load_panel()
        C.index = C.index.astype("datetime64[ns]")
        Fx = exact_funding(C.index, C.columns).reindex(columns=C.columns).fillna(0.0).to_numpy(float)
        elig = drop_non_crypto(eligibility(60))
        idx, X, cols = C.index, C.to_numpy(float), list(C.columns)
        months = idx.strftime("%Y-%m")
        _D.update(idx=idx, X=X, cols=cols, Fx=Fx, months=months,
                  fv=np.array([pd.Timestamp(first[s]).value for s in cols]),
                  Em={m: np.array([m in elig.get(s, ()) for s in cols]) for m in sorted(set(months))},
                  ff=pd.DataFrame(X).ffill().to_numpy(),
                  R=np.r_[np.full((1, X.shape[1]), np.nan), X[1:] / X[:-1] - 1],
                  reg=pl.btc_regime_daily())
    return _D


def ohl():
    """Daily open / high / low on the close panel's grid (for intraday stops)."""
    D = data()
    if "Hi" not in D:
        from backtest.market_neutral import DATA
        o, h, l = {}, {}, {}
        for s in D["cols"]:
            d = pd.read_csv(DATA / f"{s}_1d.csv.gz", parse_dates=["time"])
            d = d[d.close > 0].drop_duplicates("time").set_index("time")
            o[s], h[s], l[s] = d["open"], d["high"], d["low"]
        idx = D["idx"]
        for k, m in (("Op", o), ("Hi", h), ("Lo", l)):
            D[k] = pd.DataFrame(m).reindex(index=idx, columns=D["cols"]).to_numpy(float)
    return D


def mn_run(look=30, hold=7, frac=0.1, start=0, score="ret", off_regime=None, cap=None, stop=None, short_stop=None,
           lag=0, fwin=7):
    """mn_capped.mn_series generalised. Returns the net per rebalance, booked at entry + hold (daily-indexed).
    score="funding7" is bear_chop's test 6 (funding carry): long the LOWEST 7-day funding sum, short the highest,
    ranked on row i - lag (row j = funding over days j-6..j, all settled by close j), with look=1 as it ran."""
    D = ohl() if stop is not None else data()
    idx, X, Fx, ff, R = D["idx"], D["X"], D["Fx"], D["ff"], D["R"]
    if score == "funding7" and f"SC{fwin}" not in D:                 # fwin: the funding window in days (7 = test 6)
        D[f"SC{fwin}"] = -pd.DataFrame(Fx).rolling(fwin, min_periods=fwin).sum().to_numpy()
    i0 = look + 1 + start                                   # the base's own date grid (mn_series starts at look + 1)
    while i0 < (61 if score == "comp" else look + 1):
        i0 += hold
    rows, pl_, ps_ = [], set(), set()
    for i in range(i0, len(idx) - hold - 1, hold):
        t0 = idx[i]
        if off_regime is not None and D["reg"].asof(t0) == off_regime:
            pl_, ps_ = set(), set()
            rows.append((t0 + pd.Timedelta(days=hold), 0.0))
            continue
        ok = (D["Em"][D["months"][i]] & ((t0.value - D["fv"]) // 86_400_000_000_000 >= MIN_AGE_D)
              & np.isfinite(X[i]) & np.isfinite(X[i - look]))
        if ok.sum() < 20:
            continue
        cand = np.flatnonzero(ok)
        if score == "ret":
            past = X[i, cand] / X[i - look, cand] - 1
        elif score == "funding7":
            past = D[f"SC{fwin}"][i - lag, cand]
        elif score == "skip3":
            past = X[i - 3, cand] / X[i - look, cand] - 1
        elif score == "voladj":
            vol = np.nanstd(R[i - look + 1:i + 1][:, cand], axis=0)
            past = (X[i, cand] / X[i - look, cand] - 1) / np.where(vol > 0, vol, np.nan)
        else:                                                                   # composite: mean rank of 14/30/60
            rk = [pd.Series(X[i, cand] / X[i - lb, cand] - 1).rank(pct=True).to_numpy() for lb in (14, 30, 60)]
            past = np.nanmean(np.vstack(rk), axis=0)
        k = max(int(len(cand) * frac), 3)
        order = cand[np.argsort(np.where(np.isnan(past), np.inf, past), kind="stable")]
        sh, lo = order[:k], order[-k:]
        fwd = ff[i + hold] / X[i] - 1
        if cap is not None:
            fwd = np.clip(fwd, -1.0, cap)
        if stop is not None:                      # the live bot's disaster stop: fixed from the entry, intraday
            fwd = fwd.copy()
            for legs, sgn in (((sh, 1),) if stop == "short_only" else ((sh, 1), (lo, -1))):
                for x in legs:
                    lvl = X[i, x] * (1 + sgn * (short_stop if stop == "short_only" else stop))
                    for d in range(i + 1, i + hold + 1):
                        hit = D["Hi"][d, x] >= lvl if sgn > 0 else D["Lo"][d, x] <= lvl
                        if np.isfinite(D["Hi"][d, x]) and hit:
                            op = D["Op"][d, x]
                            fill = max(op, lvl) if sgn > 0 else min(op, lvl)
                            fwd[x] = fill / X[i, x] - 1
                            break
        fnd = Fx[i + 1:i + hold + 1].sum(axis=0)
        gross = 0.5 * fwd[lo].mean() - 0.5 * fwd[sh].mean()
        carry = 0.5 * (-fnd[lo].mean()) + 0.5 * fnd[sh].mean()
        L_, S_ = {D["cols"][x] for x in lo}, {D["cols"][x] for x in sh}
        cost = FEE * min((len(L_ ^ pl_) + len(S_ ^ ps_)) / (4 * k), 1.0)
        pl_, ps_ = L_, S_
        rows.append((t0 + pd.Timedelta(days=hold), gross + carry - cost))
    return pd.Series([r for _, r in rows], index=pd.DatetimeIndex([t for t, _ in rows])).groupby(level=0).sum()


def stats(s, hold):
    per = 365 / hold
    out = {}
    for nm, x in (("tune", s[s.index < HOLDOUT]), ("hold", s[s.index >= HOLDOUT])):
        out[nm] = x.mean() / x.std() * np.sqrt(per) if x.std() > 0 else 0.0
        out[nm + "_ann"] = (1 + x).prod() ** (per / max(len(x), 1)) - 1
    c = (1 + s).cumprod()
    out["fall"] = float((1 - c / c.cummax()).max())
    return out


def main():
    lines = [f"backtest/mn_combos.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}; PIT top-60, 1x gross; Sharpe tune / holdout "
             f"(split {HOLDOUT:%Y-%m-%d}), annualised return, biggest fall", ""]
    ref = pl.mn_daily()
    mine = mn_run()
    common = ref.index.intersection(mine.index)
    gap = float((ref.reindex(common) - mine.reindex(common)).abs().max())
    lines.append(f"CHECK: start-day 0 reproduces pair_lab.mn_daily on {len(common)} of {len(ref)} rebalances, max gap {gap:.1e}")
    print(lines[-1], flush=True)
    assert gap < 1e-9 and len(common) >= len(ref) - 9, "mn_run != mn_daily"

    def offsets(hold):
        return list(range(hold)) if hold <= 7 else list(range(0, hold, 2))

    V = {"BASE look 30 / hold 7": dict(),
         "L lookback 14": dict(look=14), "L lookback 60": dict(look=60),
         "H hold 3": dict(hold=3), "H hold 14": dict(hold=14),
         "S volatility-adjusted": dict(score="voladj"), "S skip the last 3 days": dict(score="skip3"),
         "S mean rank 14/30/60": dict(score="comp"),
         "G off in BEAR weeks": dict(off_regime="bear"), "G off in BULL weeks": dict(off_regime="bull")}
    res = {}
    for nm, kw in V.items():
        hold = kw.get("hold", 7)
        res[nm] = [stats(mn_run(start=o, **kw), hold) for o in offsets(hold)]
    b = res["BASE look 30 / hold 7"]
    lines.append("")
    lines.append("R. THE BASE ON EACH REBALANCE DAY: Sharpe tune / holdout, annualised tune / holdout, fall")
    for o, s in enumerate(b):
        lines.append(f"  start +{o}d: {s['tune']:+.2f} / {s['hold']:+.2f} | {s['tune_ann'] * 100:+.0f}% / {s['hold_ann'] * 100:+.0f}% | "
                     f"fall {s['fall'] * 100:.0f}%")
    lines.append("")
    bt, bh = np.mean([s["tune"] for s in b]), np.mean([s["hold"] for s in b])
    wt, wh = min(s["tune"] for s in b), min(s["hold"] for s in b)
    lines.append(f"  {'variant':28} | Sharpe tune / hold: mean, worst day | ann. tune / hold | fall | verdict")
    for nm, rs in res.items():
        mt, mh = np.mean([s["tune"] for s in rs]), np.mean([s["hold"] for s in rs])
        xt, xh = min(s["tune"] for s in rs), min(s["hold"] for s in rs)
        ok = mt > bt and mh > bh and xt > wt and xh > wh
        lines.append(f"  {nm:28} | {mt:+.2f} / {mh:+.2f}, worst {xt:+.2f} / {xh:+.2f} | "
                     f"{np.mean([s['tune_ann'] for s in rs]) * 100:+.0f}% / {np.mean([s['hold_ann'] for s in rs]) * 100:+.0f}% | "
                     f"{np.mean([s['fall'] for s in rs]) * 100:.0f}% | {'-' if nm.startswith('BASE') else ('PASS' if ok else 'fail')}")
        print(lines[-1], flush=True)
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n")
    print("\n" + txt)


if __name__ == "__main__":
    main()

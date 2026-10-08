"""THE MARKET-NEUTRAL OVERLAY WITHOUT ITS LOTTERY TICKETS (2026-10-08).

pair_lab.py --fixes: the pair + the market-neutral book (doc 10) x0.5 read +100%/yr, x1 +148%/yr. Inspected: the MN
book's 2026 (+374% to September) is a handful of pumps in a 3-6 name book - AKE +296% / +158% / +130%, RIVER +213%, BEAT
+244% in single weeks; 2022-2024 were -7% / +10% / -5%. This rebuilds the MN book (bear_chop.fast_run's rules exactly)
with each coin's weekly move CAPPED at +100% (and -100% for the floor), so no single pump carries it, and re-measures
the overlay.

REGISTERED BEFORE RUNNING: with the cap, the overlay x0.5 still adds +10..+25 points of CAGR to the pair, keeps months
up >= 55%, and adds ~0 in 2022-2024.

RESULT (2026-10-08, logs/mn_capped.txt): the uncapped rebuild reproduces fast_run exactly. MN alone by year, uncapped /
    capped +100%: 2026 +374% / +165%, other years unchanged-ish (2022-24 -7/+10/-5%). Pair + MN x0.5: +100% -> +90%/yr
    capped (+79% at a +50% cap), months up 60%, median month +2.4%; it adds ~0 in 2022-24 (right). Predicted +10..+25
    points: WRONG - it adds +27..+38.

    python -m backtest.mn_capped
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

LOG = ROOT / "logs" / "mn_capped.txt"


def mn_series(cap=None, look=30, hold=7, frac=0.1):
    """bear_chop.fast_run (fshift=1) with each coin's forward return clipped at `cap`. Returns the daily-indexed series
    (booked at entry + hold, as pair_lab.mn_daily)."""
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    Fx = exact_funding(C.index, C.columns).reindex(columns=C.columns).fillna(0.0).to_numpy(float)
    elig = drop_non_crypto(eligibility(60))
    idx, X, cols = C.index, C.to_numpy(float), list(C.columns)
    months = idx.strftime("%Y-%m")
    fv = np.array([pd.Timestamp(first[s]).value for s in cols])
    Em = {m: np.array([m in elig.get(s, ()) for s in cols]) for m in sorted(set(months))}
    ff = pd.DataFrame(X).ffill().to_numpy()
    rows, pl_, ps_ = [], set(), set()
    for i in range(look + 1, len(idx) - hold - 1, hold):
        t0 = idx[i]
        ok = Em[months[i]] & ((t0.value - fv) // 86_400_000_000_000 >= MIN_AGE_D) & np.isfinite(X[i]) & np.isfinite(X[i - look])
        if ok.sum() < 20:
            continue
        cand = np.flatnonzero(ok)
        past = X[i, cand] / X[i - look, cand] - 1
        k = max(int(len(cand) * frac), 3)
        order = cand[np.argsort(np.where(np.isnan(past), np.inf, past), kind="stable")]
        sh, lo = order[:k], order[-k:]
        fwd = ff[i + hold] / X[i] - 1
        if cap is not None:
            fwd = np.clip(fwd, -1.0, cap)
        fnd = Fx[i + 1:i + hold + 1].sum(axis=0)
        gross = 0.5 * fwd[lo].mean() - 0.5 * fwd[sh].mean()
        carry = 0.5 * (-fnd[lo].mean()) + 0.5 * fnd[sh].mean()
        L_, S_ = {cols[x] for x in lo}, {cols[x] for x in sh}
        cost = FEE * min((len(L_ ^ pl_) + len(S_ ^ ps_)) / (4 * k), 1.0)
        pl_, ps_ = L_, S_
        rows.append((t0 + pd.Timedelta(days=hold), gross + carry - cost))
    return pd.Series([r for _, r in rows], index=pd.DatetimeIndex([t for t, _ in rows])).groupby(level=0).sum()


def main():
    reg = pl.btc_regime_daily()
    raw = pl.mn_daily()
    mine = mn_series(None)
    common = raw.index.intersection(mine.index)
    gap = float((raw.reindex(common) - mine.reindex(common)).abs().max())
    lines = [f"backtest/mn_capped.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}",
             f"CHECK: the uncapped rebuild reproduces pair_lab.mn_daily (bear_chop.fast_run) - max gap {gap:.2e} "
             f"-> {'MATCH' if gap < 1e-9 else 'MISMATCH'}", ""]
    if gap >= 1e-9:
        LOG.write_text("\n".join(lines) + "\n")
        raise SystemExit("rebuild does not reproduce fast_run")
    C = pl.capit_trades(0)
    D = pl.daily_trades()
    for nm, s in (("MN uncapped", raw), ("MN capped at +100%/coin-week", mn_series(1.0)), ("MN capped at +50%", mn_series(0.5))):
        d = (1 + s).cumprod()
        yr = d.resample("YE").last()
        yr = yr / yr.shift(1).fillna(1.0) - 1
        lines.append(f"{nm} alone 1x by year: " + " ".join(f"{t.year}:{v * 100:+.0f}%" for t, v in yr.items()))
        for w in (0.5, 1.0):
            ms = pd.DataFrame([pl.metrics(pl.account({"daily": (D, 0.5, 8), "capit": (C, 0.5, 8)}, seed=sd,
                                                    extra_daily=w * s)[0], reg) for sd in range(10)]).median()
            sub = []
            for sd in range(3):
                dd = pl.account({"daily": (D, 0.5, 8), "capit": (C, 0.5, 8)}, seed=sd, extra_daily=w * s)[0]
                base = pl.account({"daily": (D, 0.5, 8), "capit": (C, 0.5, 8)}, seed=sd)[0]
                a, b = dd["2022-01-01":"2024-12-31"], base["2022-01-01":"2024-12-31"]
                sub.append((a.iloc[-1] / a.iloc[0]) ** (1 / 3) - (b.iloc[-1] / b.iloc[0]) ** (1 / 3))
            lines.append(f"  pair + {nm} x{w}: {ms.cagr * 100:+.0f}%/yr ({ms.tune * 100:+.0f}/{ms.hold * 100:+.0f}), fall {ms.dd:.0%}, "
                         f"up {ms.up:.0%}, median month {ms.med * 100:+.1f}%, worst {ms.worst * 100:+.0f}% | bull {ms.bull * 100:+.1f} "
                         f"chop {ms.chop * 100:+.1f} bear {ms.bear * 100:+.1f} | adds in 2022-24: {np.mean(sub) * 100:+.0f} points/yr")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n")


if __name__ == "__main__":
    main()

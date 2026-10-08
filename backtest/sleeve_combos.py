"""THE BEAR BREADTH SLEEVE x TODAY'S CAPITULATION SIGNAL - the combinations not yet run (2026-10-08).

The sleeve (doc 13; dd_fix_more.py builds logs/breadth_real_1x.pkl): on BEAR days (BTC 50-day trend), long the top-5
basket when breadth20 over the PIT top-60 is in the bottom third of prior bear days, short it in the top third; a 7-day
ladder, filled a day later, on a $221 account with a $5 minimum. Its 240-setting grid was all on its own breadth
measure. Never combined with the capitulation signal found today (>= 5 PIT top-40 coins with a 4h RSI(14) cross under
20 and a volume spike within 24h - a different, faster measure of the same washout):
    long only        drop the short side (shorting high breadth in a bear)
    short only       drop the long side
    + capitulation   also long on bear days within 72h after a capitulation (known by that day's close)
    capit instead    long ONLY within 72h after a capitulation (the capitulation signal replaces low breadth); short as is
One phase (daily closes at 00 UTC - the panel has no other); halves split 2024-04-07. Judged against the sleeve's own
leverage line (its daily returns x 0.5 / 1 / 1.5 / 2) at the same biggest fall, on both halves.

REGISTERED BEFORE RUNNING: the start reproduces logs/breadth_real_1x.pkl (self-check). Long-only and short-only each
fail one half (doc 13 found both sides earn); "+ capitulation" adds a few trades and ties; "capit instead" fails
(capitulations are rarer than low-breadth days, and the sleeve's edge is the slow bounce, not the first day).

RESULT (2026-10-08, logs/sleeve_combos.txt): the rebuild reproduces breadth_real_1x.pkl (gap 2e-16). Base +31.9% /
    +6.2% CAGR, fall 20%. All 4 fail: long only -25.8 / -1.2 under the line, short only -12.1 / -5.6, + capitulation
    longs -0.5 / -0.8 (a tie), capitulation instead of low breadth -12.4 / -2.1. Predictions - right.

    python -m backtest.sleeve_combos
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import capit_combos as cc  # noqa: E402
from backtest import pair_lab as pl  # noqa: E402
from backtest.breadth_attack import ls_signal  # noqa: E402
from backtest.breadth_robust import breadth_n, small_account  # noqa: E402
from backtest.carry_check import exact_funding  # noqa: E402
from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel  # noqa: E402
from backtest.regime_signals import member_mask  # noqa: E402
from backtest.wide_book import eligibility  # noqa: E402

LOG = ROOT / "logs" / "sleeve_combos.txt"
H = pl.HOLDOUT


def stats(r):
    c = (1 + r).cumprod()

    def cg(x):
        yrs = (x.index[-1] - x.index[0]).days / 365
        return (x.iloc[-1] / x.iloc[0]) ** (1 / yrs) - 1 if x.iloc[-1] > 0 else -1.0
    return dict(tune=cg(c[c.index < H]), hold=cg(c[c.index >= H]), fall=float((1 - c / c.cummax()).max()))


def main():
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    Fx = exact_funding(C.index, C.columns)
    reg = btc_regime(C).reindex(C.index)
    X = C.to_numpy(float)
    m60 = member_mask(C, first, drop_non_crypto(eligibility(60))) & np.isfinite(X)
    bear = reg == "bear"
    sig = ls_signal(breadth_n(C, m60, 20), bear)
    e5 = drop_non_crypto(eligibility(5))
    months = C.index.strftime("%Y-%m")
    bym = {m: [s for s in C.columns if m in e5.get(s, ())] for m in sorted(set(months))}
    ci = {s: i for i, s in enumerate(C.columns)}
    top5 = lambda d: [s for s in bym[months[d]] if np.isfinite(X[d, ci[s]])][:5]  # noqa: E731
    run = lambda s_: small_account(C, Fx, first, s_, top5, cap=221.0)[0].pct_change().fillna(0.0)  # noqa: E731
    base = run(sig)
    ref = pd.read_pickle(ROOT / "logs" / "breadth_real_1x.pkl")["full"]
    common = base.index.intersection(ref.index)
    gap = float((base.reindex(common) - ref.reindex(common)).abs().max())
    lines = [f"backtest/sleeve_combos.py, {pd.Timestamp.now():%Y-%m-%d %H:%M}",
             f"CHECK: the base reproduces logs/breadth_real_1x.pkl on {len(common)} days, max gap {gap:.1e}"]
    print(lines[-1], flush=True)
    assert gap < 1e-9, "sleeve rebuild != breadth_real_1x"
    S = cc.signals(0)
    S = S[S.K >= 5]
    known = pd.DatetimeIndex(S.t) + pd.Timedelta(hours=4)
    # day d's close is d + 1 day (00 UTC): a capitulation within the 72h before it
    ends = C.index + pd.Timedelta(days=1)
    kn = np.sort(known.as_unit("ns").asi8)
    e_ns = ends.as_unit("ns").asi8
    hi = np.searchsorted(kn, e_ns, side="right")
    lo = np.searchsorted(kn, e_ns - 72 * 3600 * 10 ** 9, side="right")
    capit = pd.Series(hi > lo, index=C.index) & bear.to_numpy()
    V = {"BASE (as built)": sig, "long only": sig.clip(lower=0), "short only": sig.clip(upper=0),
         "+ capitulation longs": sig.where(~capit, 1.0),
         "capitulation instead of low breadth": sig.where(sig < 0, 0.0).where(~capit, 1.0)}
    bs = {k: stats(k * base) for k in (0.5, 1.0, 1.5, 2.0)}
    pts = sorted((v["fall"], v["tune"], v["hold"]) for v in bs.values())
    lines.append(f"  capitulation days flagged: {int(capit.sum())} bear days; low-breadth long days: {int((sig > 0).sum())}")
    lines.append("  the line (base x 0.5 / 1 / 1.5 / 2): " + "; ".join(f"{f * 100:.0f}% {a * 100:+.0f}%/{b * 100:+.0f}%" for f, a, b in pts))
    for nm, s_ in V.items():
        r = base if nm.startswith("BASE") else run(s_)
        st = stats(r)
        dt = st["tune"] - np.interp(st["fall"], [p[0] for p in pts], [p[1] for p in pts])
        dh = st["hold"] - np.interp(st["fall"], [p[0] for p in pts], [p[2] for p in pts])
        lines.append(f"  {nm:36} CAGR {st['tune'] * 100:+.1f}% / {st['hold'] * 100:+.1f}% fall {st['fall'] * 100:.0f}% | vs line "
                     f"{dt * 100:+.1f} / {dh * 100:+.1f} -> {'-' if nm.startswith('BASE') else ('PASS' if dt > 0 and dh > 0 else 'fail')}")
        print(lines[-1], flush=True)
    LOG.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

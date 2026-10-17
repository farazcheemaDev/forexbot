"""THE SIGNAL SCORE on the stopped news trade (2026-10-17)

news/entry.py's score was fit on its tune-best cell - shorting a +6% pump, NO stop - with 32 tune trades, and failed on
the holdout (rank corr -0.11, the middle tercile best). The user wants a stop, and the best cell WITH one (chosen on the
tune half among cells with a stop, entry.py's saved trades): enter 15 minutes after the headline, hold up to 72h,
stop +25%, take-profit -20% - +316bp tune / +267bp holdout a trade, 67% won, worst -36%, 313 trades.
Same features and ridge model as entry.py, fit on the tune half of THIS cell; the score is the prediction's percentile
among tune trades (0-100). Also a SIMPLE score from the two features a person would pick first (the move from the
headline to the entry, and the coin's 24 h volume), each ranked and averaged - fewer knobs to over-fit.

REGISTERED BEFORE THE RUN (2026-10-17)
    S2 neither score separates the holdout: top-tercile minus bottom-tercile under 200bp, or rank corr <= 0, for both
       (expected: ~100 tune trades cannot fit 8 features).
    PASS (a score the bot can size by): top tercile - bottom tercile >= 200bp AND rank corr > 0 on the holdout.

RESULT (2026-10-17, logs/news_score.txt) - NO USABLE SCORE (S2 right). Ridge holdout terciles +171 / +1,309 / -90bp
    (rank corr +0.09); simple +192 / +364 / +297bp (+0.12). One feature holds its sign on both halves: the coin's 24 h
    quote volume (rank corr +0.20 tune / +0.24 holdout - liquid coins squeeze less); coin age -0.15 / -0.13. Seen after
    looking: a lead for the forward record, not a rule. Size every news trade the same.

    python -m news.score
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "logs" / "news_score.txt"
FEATS = ["etype", "tone", "n_src", "views", "to_entry", "btc7", "vol", "age"]
CELL = dict(entry="I15", h="72h", stop=0.25, tp=0.20)


def judge(C, score_col):
    tu = ~C.hold.to_numpy()
    H = C[C.hold]
    q = np.quantile(C[score_col][tu], [1 / 3, 2 / 3])
    t = [H[H[score_col] < q[0]].net.mean(), H[(H[score_col] >= q[0]) & (H[score_col] < q[1])].net.mean(),
         H[H[score_col] >= q[1]].net.mean()]
    rho = H[[score_col, "net"]].corr(method="spearman").iloc[0, 1]
    return t, rho


def main():
    D = pd.read_parquet(ROOT / "strategy_analysis" / "data" / "news" / "entry_trades.parquet")
    C = D[(D.entry == CELL["entry"]) & (D.h == CELL["h"]) & np.isclose(D.stop, CELL["stop"]) & np.isclose(D.tp, CELL["tp"])].copy()
    tu = ~C.hold.to_numpy()
    X = C[FEATS].astype(float)
    mu, sd = X[tu].mean(), X[tu].std().replace(0, 1)
    Z = ((X - mu) / sd).fillna(0.0).to_numpy()
    A = np.c_[np.ones(len(Z)), Z]
    w = np.linalg.solve(A[tu].T @ A[tu] + 5.0 * np.eye(A.shape[1]), A[tu].T @ C.net.to_numpy()[tu])
    pred = A @ w
    ref = np.sort(pred[tu])
    C["ridge"] = np.searchsorted(ref, pred) / len(ref) * 100
    r1 = C.to_entry.rank(pct=True)
    r2 = C.vol.rank(pct=True)
    s_tu = np.sort(((r1 + r2) / 2)[tu])
    C["simple"] = np.searchsorted(s_tu, (r1 + r2) / 2) / len(s_tu) * 100
    lines = [f"news/score.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; cell {CELL}; {tu.sum()} tune / {(~tu).sum()} holdout trades; "
             f"mean net tune {C.net[tu].mean() * 1e4:+.0f}bp, holdout {C.net[~tu].mean() * 1e4:+.0f}bp", "",
             "  ridge weights (standardised): " + ", ".join(f"{f} {x * 1e4:+.0f}bp" for f, x in zip(FEATS, w[1:])),
             "  single-feature rank correlation with net, tune / holdout:"]
    for f in FEATS:
        a = C[tu][[f, "net"]].corr(method="spearman").iloc[0, 1]
        b = C[~tu][[f, "net"]].corr(method="spearman").iloc[0, 1]
        lines.append(f"    {f:<9}{a:>+7.2f}{b:>+8.2f}")
    res = {}
    for sc in ("ridge", "simple"):
        t, rho = judge(C, sc)
        res[sc] = (t, rho)
        lines.append(f"  {sc:<7} score, HOLDOUT net by tercile (low / mid / high): {t[0] * 1e4:+.0f} / {t[1] * 1e4:+.0f} / {t[2] * 1e4:+.0f} bp, "
                     f"rank corr {rho:+.2f}")
    passed = [sc for sc, (t, rho) in res.items() if t[2] - t[0] >= 0.02 and rho > 0]
    lines += ["", "REGISTERED PREDICTIONS",
              f"  S2 neither score separates the holdout -> {'RIGHT' if not passed else 'WRONG (' + ', '.join(passed) + ' passes)'}",
              f"  PASS: {passed if passed else 'none - size every news trade the same'}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

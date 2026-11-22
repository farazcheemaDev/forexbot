"""WINDOW LAB - real numbers for the Module 3 lessons (docs/27): windows, persistence and the statistics of overlapping samples. DOGE perp on Bitget,
ONE day: 2026-06-01 (2026-10-30).

WHAT THIS IS: descriptive measurements on the teaching day (the same day as order_flow_lab.py; 2026-09-01 stays unread). Nothing here is a trading hypothesis
and nothing is a result to trade on. The point is to SEE, on real data, five things Module 3 teaches:
    1. what a window is worth: how big the mid move is over 1 s / 5 s / 30 s / 1 min / 5 min compared with the 4bp and 12bp round-trip costs
    2. persistence and decay: how long a book feature and taker flow persist, and how a feature's predictive power (IC) fades with the horizon
    3. overlap: the same IC measured on every second (overlapping) vs on non-overlapping windows, and what a shuffled-feature null says
    4. multiple testing: how many of 1,000 cells built from a feature that has NO relation to the future still pass t > 2, naive vs non-overlapping
    5. non-stationarity: how the size of moves differs across the day
DATA: the 1-second grid of the rebuilt book (strategy_analysis/data/book_hist/grid_2026-06-01.pkl: bid, ask, imbalance over 1 / 5 / 20 levels, depth band)
and Tardis' tape for the day. Feature at second t uses only information up to t; the target at horizon h is the mid change from t to t+h (bp).
NULL: a feature shifted circularly by a random lag (3,600 s or more): it keeps the feature's own persistence and loses any link to the future.

REGISTERED BEFORE THE FIRST RUN (2026-10-30)
    W1  Mid-change dispersion follows random-walk scaling: std(h) / (std(1 s) x sqrt(h)) is between 0.6 and 1.4 at 5 s, 30 s, 1 min and 5 min. At 1 s more than
        70% of windows show no change in the mid. The share of 5-minute windows moving more than the 12bp taker round trip is between 20% and 60%.
    W2  |IC| of top-of-book imbalance falls monotonically from 1 s to 5 min (non-overlapping samples) and is under 0.05 at 5 min (n = 288, standard error ~0.06).
    W3  Persistence: imb1's autocorrelation is above 0.4 at a 1 s lag and under 0.15 at 60 s. Taker-flow share in non-overlapping 5 s windows has a lag-1
        autocorrelation above +0.05 (one parent order split into many prints).
    W4  Overlap inflation: the naive t of imb1 -> 30 s measured on every second is at least 3x the t measured on non-overlapping 30 s windows.
    W5  Against the shifted-feature null, the real imb1 -> 5 s and imb1 -> 30 s ICs both have p < 0.05.
    W6  On 1,000 null cells (4 features x 5 horizons x 50 shifted draws) the naive overlapping |t| > 2 rate is above 25%; the non-overlapping rate is 2-10%.

AMENDED AT THE FIRST PRINTOUT (before any prediction was graded): the taker-flow FEATURE (the "flow 5s" row of part 2) read IC +0.199 against the next second because it
    included the trades of the second being predicted (alignment: see known_flow_share). Rebuilt from earlier seconds only it reads +0.029, in line with
    order_flow_lab.py (+0.036). Nothing else in the file uses trade data against a forward target. tests/test_window_lab.py fails on the old feature.

    python -m backtest.window_lab          writes logs/window_lab.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.book_hist import CACHE, load_trades  # noqa: E402

LOG = ROOT / "logs" / "window_lab.txt"
DAY = "2026-06-01"
HORIZONS = (1, 5, 30, 60, 300)
FEATURES = ["imb1", "imb5", "imb20", "band10"]
MAKER_BP, TAKER_BP = 4.0, 12.0
MIN_SHIFT_S = 3600


# ------------------------------------------------------------------ the statistics (pure functions, tested in tests/test_window_lab.py)

def fwd_change_bp(mid: np.ndarray, h: int) -> np.ndarray:
    """Mid change from second t to t + h, in bp of the mid at t; NaN where t + h is past the end of the data."""
    out = np.full(len(mid), np.nan)
    if h < len(mid):
        out[: len(mid) - h] = (mid[h:] - mid[: len(mid) - h]) / mid[: len(mid) - h] * 1e4
    return out


def spearman(x: np.ndarray, y: np.ndarray):
    """Rank correlation on the finite pairs. Returns (rho, n)."""
    ok = np.isfinite(x) & np.isfinite(y)
    n = int(ok.sum())
    if n < 3:
        return float("nan"), n
    rx, ry = pd.Series(x[ok]).rank().to_numpy(), pd.Series(y[ok]).rank().to_numpy()
    rx, ry = rx - rx.mean(), ry - ry.mean()
    d = np.sqrt((rx * rx).sum() * (ry * ry).sum())
    return (float((rx * ry).sum() / d) if d > 0 else float("nan")), n


def t_from_rho(rho: float, n: int) -> float:
    """t of a correlation if the n samples were independent."""
    return float(rho * np.sqrt((n - 2) / max(1 - rho * rho, 1e-12)))


def ic_overlap(feat: np.ndarray, fwd: np.ndarray):
    """Every second is a sample: consecutive samples share almost all of their target window."""
    rho, n = spearman(feat, fwd)
    return rho, n, t_from_rho(rho, n)


def ic_nonoverlap(feat: np.ndarray, fwd: np.ndarray, h: int, offset: int = 0):
    """One sample every h seconds: the target windows do not overlap."""
    rho, n = spearman(feat[offset::h], fwd[offset::h])
    return rho, n, t_from_rho(rho, n)


def acf(x: np.ndarray, lag: int) -> float:
    """Pearson autocorrelation at a lag, on the finite pairs."""
    a, b = x[:-lag], x[lag:]
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3 or np.std(a[ok]) == 0 or np.std(b[ok]) == 0:
        return float("nan")
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def shifted(feat: np.ndarray, k: int) -> np.ndarray:
    """The feature moved k seconds around the circle: same persistence, no link to the future."""
    return np.roll(feat, k)


def null_ic(feat: np.ndarray, fwd: np.ndarray, rng, draws: int = 200):
    """IC of circularly shifted copies of the feature against the target (overlapping samples)."""
    n = len(feat)
    ks = rng.integers(MIN_SHIFT_S, n - MIN_SHIFT_S, size=draws)
    return np.array([spearman(shifted(feat, int(k)), fwd)[0] for k in ks])


def trailing_flow_share(signed: np.ndarray, absd: np.ndarray, lookback: int) -> np.ndarray:
    """Taker-flow share over the `lookback` seconds ending at each second (uses that second and earlier only)."""
    cs, ca = np.r_[0.0, np.cumsum(signed)], np.r_[0.0, np.cumsum(absd)]
    n = len(signed)
    lo = np.maximum(np.arange(1, n + 1) - lookback, 0)
    num, den = cs[1:] - cs[lo], ca[1:] - ca[lo]
    return np.where(den > 0, num / np.where(den > 0, den, 1), np.nan)


def known_flow_share(signed: np.ndarray, absd: np.ndarray, lookback: int) -> np.ndarray:
    """Taker-flow share that is KNOWN at the start of second i: the trades of seconds i - lookback .. i - 1.
    Bin i holds the trades stamped in [T_i, T_i + 1 s), and the book row labelled i is the book AS OF T_i, so bin i happens AFTER that row, inside the very second
    a forward target from i is made of. trailing_flow_share alone includes it. Found at this lab's first printout: 5 s flow -> next 1 s read IC +0.199 with bin i
    included and +0.029 without (the same second's flow alone correlates +0.63 with that second's move: it IS the move)."""
    t = trailing_flow_share(signed, absd, lookback)
    return np.r_[np.nan, t[:-1]]


# ------------------------------------------------------------------ the day

def load_day(day: str = DAY):
    g, _ = pd.read_pickle(CACHE / f"grid_{day}.pkl")
    g = g.sort_values("t", kind="stable").reset_index(drop=True)
    sec = ((g.t.to_numpy("int64") - g.t.iloc[0]) // 1000).astype(int)
    n = sec.max() + 1
    full = pd.DataFrame({c: np.nan for c in ["bid", "ask"] + FEATURES}, index=range(n))
    for c in ["bid", "ask"] + FEATURES:
        full.loc[sec, c] = g[c].to_numpy(float)
    full = full.ffill()
    mid = ((full.bid + full.ask) / 2).to_numpy(float)
    tr = load_trades(day)
    s = ((tr.t.to_numpy() - g.t.iloc[0]) // 1000).astype(int)
    keep = (s >= 0) & (s < n)
    usd = (tr.qty.to_numpy(float) * tr.price.to_numpy(float))[keep]
    sgn = np.where(tr.side.to_numpy()[keep] == "buy", 1.0, -1.0)
    signed = np.bincount(s[keep], weights=usd * sgn, minlength=n)[:n]
    absd = np.bincount(s[keep], weights=usd, minlength=n)[:n]
    return mid, {c: full[c].to_numpy(float) for c in FEATURES}, signed, absd, int(g.t.iloc[0])


def main():
    rng = np.random.default_rng(7)
    mid, F, signed, absd, t0_ms = load_day()
    n = len(mid)
    L = [f"backtest/window_lab.py, DOGEUSDT perp on Bitget, {DAY} (Tardis), {n:,} seconds, run {pd.Timestamp.now():%Y-%m-%d %H:%M}"]
    fwd = {h: fwd_change_bp(mid, h) for h in HORIZONS}

    L.append("\n1. HOW BIG IS A MOVE, BY WINDOW (mid change from t to t+h, all start seconds)")
    L.append(f"  {'window':>7s} {'std bp':>8s} {'std/(std1*sqrt h)':>18s} {'no change':>10s} {'median |move|':>14s} {'|move|>4bp':>11s} {'|move|>12bp':>12s} {'std / 12bp':>11s}")
    s1 = np.nanstd(fwd[1])
    for h in HORIZONS:
        x = fwd[h][np.isfinite(fwd[h])]
        sd = x.std()
        L.append(f"  {h:>5d} s {sd:8.2f} {sd / (s1 * np.sqrt(h)):18.2f} {np.mean(x == 0) * 100:9.0f}% {np.median(np.abs(x)):14.2f} "
                 f"{np.mean(np.abs(x) > MAKER_BP) * 100:10.0f}% {np.mean(np.abs(x) > TAKER_BP) * 100:11.0f}% {sd / TAKER_BP:11.2f}")
    up = {h: np.mean(fwd[h][np.isfinite(fwd[h]) & (fwd[h] != 0)] > 0) for h in HORIZONS}
    L.append("  share of the non-zero moves that are up: " + ", ".join(f"{h} s {up[h] * 100:.0f}%" for h in HORIZONS))

    L.append("\n2. PERSISTENCE AND DECAY")
    L.append("  autocorrelation of the feature itself, by lag (sampled every second):")
    L.append(f"  {'feature':>8s} " + " ".join(f"{'lag ' + str(k) + ' s':>9s}" for k in (1, 5, 30, 60, 300)))
    for c in FEATURES:
        L.append(f"  {c:>8s} " + " ".join(f"{acf(F[c], k):9.2f}" for k in (1, 5, 30, 60, 300)))
    L.append("  taker-flow share in NON-overlapping windows of w seconds: lag-1 autocorrelation (does buying beget buying?)")
    cells = []
    for w in HORIZONS:
        m = n // w
        sg = signed[: m * w].reshape(m, w).sum(1)
        ab = absd[: m * w].reshape(m, w).sum(1)
        sh = np.where(ab > 0, sg / np.where(ab > 0, ab, 1), np.nan)
        cells.append(f"{w} s {acf(sh, 1):+.3f} (n {m})")
    L.append("    " + ", ".join(cells))
    L.append("  IC (rank correlation) of each feature with the NEXT h seconds, NON-overlapping samples (one every h seconds); in brackets the samples")
    L.append(f"  {'feature':>8s} " + " ".join(f"{'h=' + str(h) + ' s':>16s}" for h in HORIZONS))
    ic_tab = {}
    for c in FEATURES:
        row = []
        for h in HORIZONS:
            rho, k, t = ic_nonoverlap(F[c], fwd[h], h)
            ic_tab[c, h] = (rho, k, t)
            row.append(f"{rho:+.3f} ({k:,})")
        L.append(f"  {c:>8s} " + " ".join(f"{r:>16s}" for r in row))
    flow5 = known_flow_share(signed, absd, 5)
    row = []
    for h in HORIZONS:
        rho, k, t = ic_nonoverlap(flow5, fwd[h], h)
        row.append(f"{rho:+.3f} ({k:,})")
    L.append(f"  {'flow 5s':>8s} " + " ".join(f"{r:>16s}" for r in row) + "   (taker-flow share over the 5 s BEFORE each second)")

    L.append("\n3. OVERLAP: the same IC, three ways (imb1 -> next h seconds)")
    L.append(f"  {'h':>5s} {'rho overlap':>12s} {'n':>8s} {'naive t':>8s} | {'rho non-ov':>11s} {'n':>7s} {'t':>7s} | {'inflation':>9s} | {'shift-null sd':>13s} {'p (shift)':>10s}")
    for h in HORIZONS:
        ro, no, to = ic_overlap(F["imb1"], fwd[h])
        rn, nn, tn = ic_nonoverlap(F["imb1"], fwd[h], h)
        nul = null_ic(F["imb1"], fwd[h], rng, 200)
        p = (1 + np.sum(np.abs(nul) >= abs(ro))) / (1 + len(nul))
        L.append(f"  {h:>3d} s {ro:12.3f} {no:8,d} {to:8.1f} | {rn:11.3f} {nn:7,d} {tn:7.1f} | {to / tn if tn else float('nan'):8.1f}x | {nul.std():13.4f} {p:10.3f}")

    L.append("\n4. MULTIPLE TESTING: cells built from a SHIFTED feature (no link to the future), 4 features x 5 horizons x 50 draws = 1,000 cells")
    naive_t, honest_t = [], []
    for _ in range(50):
        for c in FEATURES:
            k = int(rng.integers(MIN_SHIFT_S, n - MIN_SHIFT_S))
            sf = shifted(F[c], k)
            for h in HORIZONS:
                _, _, to = ic_overlap(sf, fwd[h])
                _, _, tn = ic_nonoverlap(sf, fwd[h], h)
                naive_t.append(to)
                honest_t.append(tn)
    naive_t, honest_t = np.array(naive_t), np.array(honest_t)
    L.append(f"  |t| > 2: naive overlapping {np.mean(np.abs(naive_t) > 2) * 100:.0f}% of cells; non-overlapping {np.mean(np.abs(honest_t) > 2) * 100:.0f}% "
             f"(honest expectation ~5%); |t| > 3: {np.mean(np.abs(naive_t) > 3) * 100:.0f}% vs {np.mean(np.abs(honest_t) > 3) * 100:.1f}%; largest naive |t| {np.abs(naive_t).max():.1f}, "
             f"largest honest |t| {np.abs(honest_t).max():.1f}")
    real_o = [ic_overlap(F[c], fwd[h])[2] for c in FEATURES for h in HORIZONS]
    real_n = [ic_nonoverlap(F[c], fwd[h], h)[2] for c in FEATURES for h in HORIZONS]
    L.append(f"  the 20 REAL cells on this day: naive |t| > 2 in {sum(abs(x) > 2 for x in real_o)}, non-overlapping |t| > 2 in {sum(abs(x) > 2 for x in real_n)}; "
             f"after a Bonferroni cut for 20 cells (|t| > 3.0): naive {sum(abs(x) > 3.0 for x in real_o)}, non-overlapping {sum(abs(x) > 3.0 for x in real_n)}")

    L.append("\n5. THE CLOCK: the size of 1-minute mid moves and the traded dollars, by 4-hour block (UTC)")
    f60 = fwd[60]
    sec_of_day = (t0_ms // 1000) % 86400 + np.arange(n)
    L.append(f"  {'UTC block':>10s} {'std 1-min move bp':>18s} {'traded $':>12s} {'net taker share of $':>22s}")
    for b in range(6):
        m = ((sec_of_day // 3600) // 4 == b) & np.isfinite(f60)
        if m.sum() > 100:
            L.append(f"  {b * 4:02d}-{b * 4 + 4:02d} UTC {np.std(f60[m]):18.2f} {absd[m].sum():12,.0f} {signed[m].sum() / max(absd[m].sum(), 1):22.3f}")
    txt = "\n".join(L)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

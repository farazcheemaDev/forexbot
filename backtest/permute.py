"""Bar permutation for Monte Carlo Permutation Tests (MCPT).

Method credit: neurotrader888/mcpt, itself following Timothy Masters,
"Testing and Tuning Market Trading Systems", and Good, "Permutation,
Parametric and Bootstrap Tests of Hypotheses".

WHAT THIS IS FOR
----------------
A backtest tells you how a strategy did. It does NOT tell you whether that
result is distinguishable from luck - especially after searching hundreds of
configs, where the best result is partly just the largest random deviation.

Permutation fixes this by building the NULL DISTRIBUTION empirically. We
shuffle the bars so that any real serial structure (trends, momentum,
mean-reversion - anything a strategy could exploit) is destroyed, while the
statistical character of the market is preserved:

    preserved:  bar-shape distribution, volatility, fat tails, skew, gap
                distribution, price level and scale
    destroyed:  the ORDER of moves - i.e. every exploitable pattern

Re-running the whole strategy search on permuted data therefore answers:
"how good a result would my search process find in data with no edge at all?"
If the real result isn't clearly better than that, the result is data mining.

HOW THE SHUFFLE WORKS
---------------------
Each bar is decomposed into log-relative components:
    gap  = log(open)  - log(prev close)      <- overnight/inter-bar move
    hi   = log(high)  - log(open)            \
    lo   = log(low)   - log(open)             > intrabar shape, kept TOGETHER
    cl   = log(close) - log(open)            /
Intrabar triples are shuffled with one permutation (so high >= open >= low
relationships and realistic candle shapes survive), gaps with a separate one.
Prices are then rebuilt cumulatively from a fixed starting bar.

start_index keeps the first N bars REAL. That is what makes the walk-forward
test possible: the strategy trains on genuine data and is measured on
permuted out-of-sample data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

OHLC = ["open", "high", "low", "close"]


def get_permutation(df: pd.DataFrame, start_index: int = 0,
                    seed: int | None = None) -> pd.DataFrame:
    """Return one permutation of an OHLC frame. Bars before start_index are real.

    OHLC prices are permuted; VOLUME is reordered with the same intrabar index so
    each bar keeps its own volume (see note below). Other columns (time, ...) pass
    through unchanged.
    """
    assert start_index >= 0
    n = len(df)
    if start_index >= n - 2:
        raise ValueError(f"start_index {start_index} leaves nothing to permute (n={n})")

    rng = np.random.default_rng(seed)
    log = np.log(df[OHLC].to_numpy(dtype=float))
    o, h, l, c = log[:, 0], log[:, 1], log[:, 2], log[:, 3]

    # relative components
    gap = np.empty(n); gap[0] = 0.0
    gap[1:] = o[1:] - c[:-1]
    r_h, r_l, r_c = h - o, l - o, c - o

    p0 = start_index + 1                 # first bar that gets permuted
    m = n - p0
    idx_intra = rng.permutation(m)        # shuffle candle shapes together
    idx_gap = rng.permutation(m)          # shuffle gaps independently

    out = log.copy()                     # keeps real bars up to start_index
    ph, pl, pc = r_h[p0:][idx_intra], r_l[p0:][idx_intra], r_c[p0:][idx_intra]
    pg = gap[p0:][idx_gap]

    # VECTORISED rebuild. The recursion close[i] = close[i-1] + gap[i] + close_rel[i]
    # telescopes into a cumulative sum, so no Python loop is needed:
    #     close = close[start] + cumsum(gap + close_rel)
    #     open[i] = close[i-1] + gap[i]
    # Identical output to the loop, ~100x faster — which is what makes multi-asset
    # MCPT with hundreds of permutations feasible.
    closes = out[start_index, 3] + np.cumsum(pg + pc)
    prev_closes = np.concatenate(([out[start_index, 3]], closes[:-1]))
    opens = prev_closes + pg
    out[p0:, 0] = opens
    out[p0:, 1] = opens + ph
    out[p0:, 2] = opens + pl
    out[p0:, 3] = closes

    res = df.copy()
    res[OHLC] = np.exp(out)
    # VOLUME travels with its own bar. A bar's range and its volume belong
    # together; shuffling ranges while leaving volume in place would destroy the
    # range/volume relationship that Volume Spread Analysis exploits, making the
    # null far too easy to beat. Carry it with idx_intra so the contemporaneous
    # link survives and only the ORDERING dies.
    if "volume" in res.columns:
        v = df["volume"].to_numpy(dtype=float).copy()
        v[p0:] = v[p0:][idx_intra]
        res["volume"] = v
    return res


def get_permutation_multi(dfs: list[pd.DataFrame], start_index: int = 0,
                          seed: int | None = None) -> list[pd.DataFrame]:
    """Permute several markets with ONE SHARED index, so cross-sectional
    correlation survives while serial structure dies.

    This matters for any RELATIVE strategy (e.g. intramarket difference). The
    null we want is "the spread between two assets has no exploitable serial
    structure" - NOT "the two assets are unrelated". Permuting each market with
    its own index would destroy their contemporaneous correlation too, making the
    permuted world far easier to beat than reality and the p-value meaninglessly
    optimistic.

    All frames must share an identical time index.
    """
    assert len(dfs) >= 1
    n = len(dfs[0])
    for d in dfs:
        if len(d) != n:
            raise ValueError("all markets must have the same length")
    if start_index >= n - 2:
        raise ValueError(f"start_index {start_index} leaves nothing to permute")

    rng = np.random.default_rng(seed)
    p0 = start_index + 1
    m = n - p0
    idx_intra = rng.permutation(m)      # ONE shuffle, reused for every market
    idx_gap = rng.permutation(m)

    out = []
    for df in dfs:
        log = np.log(df[OHLC].to_numpy(dtype=float))
        o, h, l, c = log[:, 0], log[:, 1], log[:, 2], log[:, 3]
        gap = np.empty(n); gap[0] = 0.0
        gap[1:] = o[1:] - c[:-1]
        r_h, r_l, r_c = h - o, l - o, c - o

        res = log.copy()
        ph, pl, pc = r_h[p0:][idx_intra], r_l[p0:][idx_intra], r_c[p0:][idx_intra]
        pg = gap[p0:][idx_gap]
        # vectorised rebuild — see note in get_permutation
        closes = res[start_index, 3] + np.cumsum(pg + pc)
        opens = np.concatenate(([res[start_index, 3]], closes[:-1])) + pg
        res[p0:, 0] = opens
        res[p0:, 1] = opens + ph
        res[p0:, 2] = opens + pl
        res[p0:, 3] = closes
        r = df.copy()
        r[OHLC] = np.exp(res)
        if "volume" in r.columns:                  # see note in get_permutation
            v = df["volume"].to_numpy(dtype=float).copy()
            v[p0:] = v[p0:][idx_intra]
            r["volume"] = v
        out.append(r)
    return out


def sanity_check(df: pd.DataFrame, seed: int = 0) -> dict:
    """Confirm a permutation preserves distribution but destroys structure."""
    perm = get_permutation(df, seed=seed)
    rr = np.log(df["close"]).diff().dropna()
    pr = np.log(perm["close"]).diff().dropna()

    def autocorr(x, k=1):
        return float(pd.Series(x.values).autocorr(k))

    # LOCAL trendiness (Kaufman efficiency over a rolling window). Note the
    # WHOLE-SAMPLE version is useless as a diagnostic: shuffling returns cannot
    # change where the path ends, so total displacement is preserved by
    # construction. It is local structure - the kind a strategy trades - that
    # permutation destroys.
    def eff(x, w=20):
        net = x.diff(w).abs()
        path = x.diff().abs().rolling(w).sum()
        return float((net / path).mean())

    bad = (perm[["open", "high", "low", "close"]].isna().any().any()
           or not (perm["high"] >= perm[["open", "close"]].max(axis=1) - 1e-9).all()
           or not (perm["low"] <= perm[["open", "close"]].min(axis=1) + 1e-9).all())
    return dict(
        real_mean=rr.mean(), perm_mean=pr.mean(),
        real_std=rr.std(), perm_std=pr.std(),
        real_skew=rr.skew(), perm_skew=pr.skew(),
        real_kurt=rr.kurt(), perm_kurt=pr.kurt(),
        real_ac1=autocorr(rr), perm_ac1=autocorr(pr),
        real_eff=eff(np.log(df["close"])), perm_eff=eff(np.log(perm["close"])),
        ohlc_violation=bool(bad),
    )


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backtest.mass_search import fetch

    df = fetch("BTCUSDT", "1h", 900)
    s = sanity_check(df, seed=7)
    print(f"BTCUSDT 1h, {len(df)} bars\n")
    print(f"{'stat':12} {'REAL':>12} {'PERMUTED':>12}   verdict")
    print(f"{'mean':12} {s['real_mean']:>12.6f} {s['perm_mean']:>12.6f}   preserved")
    print(f"{'stdev':12} {s['real_std']:>12.6f} {s['perm_std']:>12.6f}   preserved")
    print(f"{'skew':12} {s['real_skew']:>12.4f} {s['perm_skew']:>12.4f}   preserved")
    print(f"{'kurtosis':12} {s['real_kurt']:>12.4f} {s['perm_kurt']:>12.4f}   preserved")
    print(f"{'autocorr(1)':12} {s['real_ac1']:>12.4f} {s['perm_ac1']:>12.4f}   should -> ~0")
    print(f"{'local eff(20)':12} {s['real_eff']:>12.4f} {s['perm_eff']:>12.4f}   should drop")
    print(f"\nOHLC integrity violated: {s['ohlc_violation']}")

"""EVERY FAMILY EVER TRIED LONG, RUN SHORT - fairly this time.

THE OLD RESULT AND WHY IT IS NOT THE LAST WORD
    tv_test.py and mass_search.py: "19 of 19 families profitable long, 0 of 19 short".
    That was measured on 9 coins that are big TODAY. For a short seller, today's
    survivors are the worst possible sample: the 339 perps that died (LUNA, FTT, SRM and
    hundreds of alts that bled to zero) are exactly the coins a short wanted, and the
    test could not see one of them. It was also 1h only, with no regime conditioning.

WHAT THIS DOES
    * Universe: all 864 USDT perps Binance ever listed, dead included (perp_fetch.py),
      filtered POINT IN TIME to the 40 most-traded perps of the PRIOR month, listed >= 30
      days. What was liquid then, not what is famous now.
    * Every family: the 9 in mass_search.gen_signals and the 8 TradingView families in
      tv_test.py, at the parameters used on the long side. SELL signals only.
    * The DEPLOYED short management for every family: 2xATR stop, 5xATR trail, breakeven
      floor at 3R, one unit. 12bp round trip, and the ACTUAL funding each short paid or
      received, in R. Pessimistic same-bar fills (strict_fill), so absolute numbers sit
      below the blend's short sleeve; the family-vs-random comparison is unaffected.
    * 1h, 4h and 12h, like the blend.
    * Reported for ALL entries and for BEAR-ONLY entries (BTC below its 1000h average,
      the live bot's gate).

THE CONTROL THAT DECIDES IT
    In a bear market, shorting ANYTHING makes money, so a family "working" in bears proves
    nothing. Every cell is compared with RANDOM short entries on the same coins, same
    timeframe, same exit, same regime, at the signal density of the deployed short rule.
    A family is only an edge if it beats random entries, and that is tested across months
    (paired: family's monthly mean R minus random's) with Holm over every cell.

    python -m backtest.short_families
"""
from __future__ import annotations

import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DATA = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "perps"
TFS = ["1h", "4h", "12h"]
TOP_N, MIN_AGE_D = 40, 30
SEEDS = (11, 22, 33)

MS = {"ma_cross": (20, 100), "donchian": (20,), "rsi_mom": (7, 40, 60),
      "bb_break": (30, 1.5), "macd": (12, 26, 9), "roc_mom": (24, 2.0),
      "rsi_rev": (14, 30, 70), "bb_rev": (20, 2.0)}
# zscore_rev(20, 2.0) is omitted: it is bb_rev(20, 2.0) by construction (a close above
# mean + 2sd IS a z-score above 2), so including both would count one test twice.
TV = ["supertrend", "keltner_brk", "squeeze_rel", "psar", "aroon", "adx_dmi",
      "ichimoku", "chandelier"]


def eligibility():
    """{sym: set of 'YYYY-MM' months in which the coin was a top-40 perp by the PRIOR
    month's quote volume and at least 30 days old}. From the daily bars."""
    vols = {}
    first = {}
    for p in DATA.glob("*_1d.csv.gz"):
        s = p.name.split("_")[0]
        d = pd.read_csv(p, parse_dates=["time"])
        if len(d) < 5:
            continue
        first[s] = d.time.iloc[0]
        vols[s] = d.set_index("time")["qvol"].resample("ME").sum()
    V = pd.DataFrame(vols).fillna(0.0)
    elig = {s: set() for s in V.columns}
    for i in range(1, len(V.index)):
        prev, cur = V.index[i - 1], V.index[i]
        mstart = cur.to_period("M").start_time
        ok = [s for s in V.columns if (mstart - first[s]).days >= MIN_AGE_D]
        top = V.loc[prev, ok].sort_values(ascending=False).index[:TOP_N]
        for s in top:
            elig[s].add(cur.strftime("%Y-%m"))
    return elig


def btc_bear():
    d = pd.read_csv(DATA / "BTCUSDT_1h.csv.gz", parse_dates=["time"])
    s = d.set_index("time")["close"]
    return (s < s.rolling(1000).mean()).shift(1).fillna(False)


def signal_sets(df):
    from backtest.mass_search import gen_signals
    from backtest import tv_test
    out = {}
    for fam, p in MS.items():
        try:
            out[fam] = gen_signals(df, fam, p)
        except Exception:
            pass
    for fam in TV:
        try:
            out[fam] = tv_test.FAMS[fam](df)
        except Exception:
            pass
    return out


def one_coin(args):
    """All families x timeframes for one coin; returns trade rows. Runs in a worker."""
    sym, months = args
    from backtest.convex import run_uncapped
    from backtest.timeframes import resample
    from bot.core.indicators import atr as atr_ind
    from bot.strategies.base import Action
    f = DATA / f"{sym}_1h.csv.gz"
    if not f.exists() or not months:
        return []
    d = pd.read_csv(f, parse_dates=["time"]).rename(columns={"qvol": "volume"})
    d = d[d.close > 0].reset_index(drop=True)
    gap = d.time.diff().dt.total_seconds().fillna(3600) / 3600
    if (gap > 48).any():                      # relisted symbol: first episode only
        d = d.iloc[:int(np.argmax(gap.values > 48))].reset_index(drop=True)
    if len(d) < 500:
        return []
    # only simulate around months the coin was eligible (plus warm-up and run-off)
    lo = pd.Timestamp(min(months) + "-01") - pd.Timedelta(days=60)
    hi = pd.Timestamp(max(months) + "-01") + pd.Timedelta(days=120)
    d = d[(d.time >= lo) & (d.time <= hi)].reset_index(drop=True)
    if len(d) < 500:
        return []
    fr = DATA / f"{sym}_funding.csv.gz"
    if fr.exists():
        fu = pd.read_csv(fr, parse_dates=["time"])
        px = d.set_index("time")["close"].reindex(fu.time.dt.floor("h")).to_numpy()
        ok = np.isfinite(px)
        ft, cs = fu.time.to_numpy()[ok], np.cumsum(fu.rate.to_numpy()[ok] * px[ok])
    else:
        ft, cs = np.array([], dtype="datetime64[ns]"), np.array([])

    def fund(t0, t1):
        if not len(ft):
            return 0.0
        a = np.searchsorted(ft, t0, "right"); b = np.searchsorted(ft, t1, "right")
        if b <= a:
            return 0.0
        return float(cs[b - 1] - (cs[a - 1] if a > 0 else 0.0))

    rows = []
    for tf in TFS:
        df = resample(d, tf)
        if len(df) < 200:
            continue
        t = df["time"].to_numpy()
        atr = atr_ind(df, 14).to_numpy(float)
        sets = signal_sets(df)
        base = sets.get("bb_break")
        dens = float((base == Action.SELL).mean()) if base is not None else 0.05
        for sd in SEEDS:
            # deterministic across processes (hash() is salted per interpreter)
            seed = int.from_bytes(hashlib.md5(f"{sym}|{tf}|{sd}".encode()).digest()[:4],
                                  "little")
            rng = np.random.default_rng(seed)
            r = np.where(rng.random(len(df)) < dens, Action.SELL, Action.HOLD)
            sets[f"RANDOM_{sd}"] = pd.Series(r, index=df.index)
        for fam, sig in sets.items():
            sig = sig.where(sig == Action.SELL, Action.HOLD)
            if int((sig == Action.SELL).sum()) == 0:
                continue
            # strict_fill: a 5xATR trail advanced off a bar's low can sit inside that
            # bar's range; the optimistic default is worth ~0.07R/trade on shorts
            # (exitlab.py), more than the short sleeve's whole edge. close_at_end:
            # a coin that DIED while we were short is the trade dead data exists for.
            R, idx, bars, _D = run_uncapped(df, sig, sl_mult=2.0, fee_bp=12.0,
                                            mode="trail_atr", trail=5.0, be_at=3.0,
                                            strict_fill=True, close_at_end="close")
            for r_, i_, b_ in zip(R, idx, bars):
                e = int(i_) - int(b_)
                if e < 1 or not np.isfinite(atr[e - 1]):
                    continue
                t0, t1 = t[e], t[int(i_)]
                m = pd.Timestamp(t0).strftime("%Y-%m")
                if m not in months:
                    continue
                risk = 2.0 * atr[e - 1]
                # a frozen price (delisting settlement) has ATR ~ 0, which turns any
                # move into +-1e30 R. 1,387 such trades on 6 coins in the first run.
                if risk < 0.001 * df["open"].iat[e]:
                    continue
                rows.append((sym, tf, fam, pd.Timestamp(t0), float(r_) + fund(t0, t1) / risk))
    return rows


def paired_t(a, b, reps=2000):
    """Pooled per-trade mean of a minus b, with the standard error from resampling
    whole MONTHS (trades in one month share one market move).

    The first version averaged each month's mean and differenced those. That weights a
    quiet month with two trades the same as a crash month with two hundred, and trend
    families trade exactly in the crash months - so it reported donchian 12h at
    t -5.76 against random while their per-trade means were -0.051 vs -0.058."""
    ka, kb = a.index.to_period("M"), b.index.to_period("M")
    months = sorted(set(ka) | set(kb))
    sa = a.groupby(ka).sum().reindex(months).fillna(0).to_numpy()
    na = a.groupby(ka).size().reindex(months).fillna(0).to_numpy()
    sb = b.groupby(kb).sum().reindex(months).fillna(0).to_numpy()
    nb = b.groupby(kb).size().reindex(months).fillna(0).to_numpy()
    if na.sum() < 30 or len(months) < 12:
        return np.nan, len(months)
    diff = sa.sum() / na.sum() - sb.sum() / nb.sum()
    rng = np.random.default_rng(7)
    ix = rng.integers(0, len(months), size=(reps, len(months)))
    boot = sa[ix].sum(1) / np.maximum(na[ix].sum(1), 1) - sb[ix].sum(1) / np.maximum(nb[ix].sum(1), 1)
    se = boot.std(ddof=1)
    return (float(diff / se) if se > 0 else np.nan), len(months)


def month_t(x, reps=2000):
    """Pooled mean R over its month-block-bootstrap standard error."""
    k = x.index.to_period("M")
    s_ = x.groupby(k).sum().to_numpy(); n_ = x.groupby(k).size().to_numpy()
    if n_.sum() < 30 or len(s_) < 12:
        return np.nan
    rng = np.random.default_rng(3)
    ix = rng.integers(0, len(s_), size=(reps, len(s_)))
    boot = s_[ix].sum(1) / np.maximum(n_[ix].sum(1), 1)
    se = boot.std(ddof=1)
    return float(s_.sum() / n_.sum() / se) if se > 0 else np.nan


def main():
    from scipy.stats import norm
    pkl = DATA.parent / "short_families_trades.pkl"
    if "--from-pickle" in sys.argv and pkl.exists():
        T = pd.read_pickle(pkl)
        n0 = len(T)
        T = T[T.R.abs() <= 100]            # the frozen-price trades the guard now blocks
        print(f"re-analysing {len(T):,} saved trades ({n0 - len(T):,} frozen-price "
              f"trades dropped)")
        return analyse(T)
    elig = eligibility()
    syms = [s for s, m in elig.items() if m and (DATA / f"{s}_1h.csv.gz").exists()]
    print(f"{len(syms)} perps were ever a top-{TOP_N} perp (dead included); simulating "
          f"{len(MS) + len(TV)} families + 3 random seeds x {TFS}", flush=True)
    rows = []
    with ProcessPoolExecutor(7) as ex:
        for k, got in enumerate(ex.map(one_coin, [(s, elig[s]) for s in syms],
                                       chunksize=4)):
            rows += got
            if (k + 1) % 50 == 0:
                print(f"  {k + 1}/{len(syms)} coins", flush=True)
    T = pd.DataFrame(rows, columns=["sym", "tf", "fam", "t0", "R"])
    T.to_pickle(pkl)
    analyse(T)


def analyse(T):
    from scipy.stats import norm
    bear = btc_bear()
    T["bear"] = bear.reindex(T.t0.dt.floor("h")).fillna(False).to_numpy(bool)
    cut = T.t0.quantile(0.6)
    print(f"{len(T):,} trades; tune < {cut:%Y-%m-%d} <= holdout; "
          f"{T[T.fam.str.startswith('RANDOM')].shape[0]:,} of them random-control\n")

    T["is_rand"] = T.fam.str.startswith("RANDOM")
    fams = [f for f in list(MS) + TV if f in set(T.fam)]
    tests = []
    for regime in ("ALL", "BEAR"):
        X = T if regime == "ALL" else T[T.bear]
        print("=" * 118)
        print(f"{regime} ENTRIES" + ("  (BTC below its 1000h average)" if regime == "BEAR"
                                     else ""))
        print("=" * 118)
        print(f"  {'family':<13}{'tf':>4}{'n':>7}{'coins':>6}{'meanR':>8}{'PF':>6}"
              f"{'t(mo)':>7}{'tune':>8}{'hold':>8} |{'random':>8}{'vs rand':>9}{'t':>6}")
        for tf in TFS:
            R = X[(X.tf == tf) & X.is_rand].set_index("t0").R
            rt = R[R.index < cut].mean(); rh = R[R.index >= cut].mean()
            print(f"  {'RANDOM':<13}{tf:>4}{len(R):>7}{'':>6}{R.mean():>+8.3f}"
                  f"{'':>6}{month_t(R):>+7.2f}{rt:>+8.3f}{rh:>+8.3f} |")
            for fam in fams:
                x = X[(X.tf == tf) & (X.fam == fam)]
                if len(x) < 30:
                    continue
                s = x.set_index("t0").R
                w, l = s[s > 0].sum(), -s[s < 0].sum()
                tp, _ = paired_t(s, R)
                tests.append((regime, fam, tf, tp))
                print(f"  {fam:<13}{tf:>4}{len(s):>7}{x.sym.nunique():>6}{s.mean():>+8.3f}"
                      f"{w / l if l else np.inf:>6.2f}{month_t(s):>+7.2f}"
                      f"{s[s.index < cut].mean():>+8.3f}{s[s.index >= cut].mean():>+8.3f} |"
                      f"{R.mean():>+8.3f}{s.mean() - R.mean():>+9.3f}{tp:>+6.2f}")
            print()

    # Holm across every family x tf x regime: does the family beat RANDOM entries?
    ok = [(r, f, tf, t) for r, f, tf, t in tests if np.isfinite(t)]
    ps = sorted(((1 - norm.cdf(t), r, f, tf, t) for r, f, tf, t in ok))
    m = len(ps)
    print("=" * 118)
    print(f"HOLM over {m} cells, one-sided 'beats random short entries' at 5%:")
    surv = []
    for k, (p, r, f, tf, t) in enumerate(ps):
        if p > 0.05 / (m - k):
            break
        surv.append((r, f, tf, t, p))
    for r, f, tf, t, p in surv:
        print(f"  SURVIVES  {r:<4} {f:<13} {tf:>4}  t {t:+.2f}  p {p:.5f}")
    if not surv:
        print("  nothing survives. Best five before correction:")
        for p, r, f, tf, t in ps[:5]:
            print(f"    {r:<4} {f:<13} {tf:>4}  t {t:+.2f}  p {p:.4f}")


if __name__ == "__main__":
    main()

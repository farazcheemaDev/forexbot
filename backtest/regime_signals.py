"""WHAT PREDICTS THE NEXT WEEK *INSIDE* CHOP AND *INSIDE* BEAR?

btc_signals.py (doc 12) tested fourteen signals over ALL days together. The trend book earns in
bull and nothing in chop (948 days) or bear (581). The question here is narrower and has never
been asked: within each of those two regimes, does anything tell you where the next 7 days go?

SIGNALS (every value for day D uses data through the end of day D-1)
    the 14 from btc_signals.features() (Coinbase premium, flows, MVRV, positioning, taker, VIX,
    momentum, ...), from its cached logs/btc_signals_features.csv.gz, plus seven new ones:
    breadth20 / breadth50  share of the PIT top-60 perps (dead coins included) closing above
                           their 20- / 50-day average. Claimed on the web as a capitulation
                           bottom-finder: "near 20% or below ... market-wide capitulation".
    fear_greed             alternative.me Fear & Greed index (lagged a day), read contrarian.
    dvol / dvol_chg7       Deribit BTC implied volatility (30d) and its 7-day change. Claimed:
                           low DVOL after a sideways stretch precedes a big move.
    mkt_funding            median 7-day funding sum over the PIT top-60 (crowding).
    btc_dd90               BTC's distance below its 90-day high (depth of the fall).
TARGETS: BTC's next-7-day return, and an equal-weight index of the PIT top-40 (delisted coins
exit at their last print) - the alt book is where the trend book actually trades.
TEST: top-minus-bottom tercile of the forward return, WITHIN the regime (market_neutral.
btc_regime, the label for day D is known at D), daily samples, month-block bootstrap t, the
two halves reported separately (holdout from 2024-08-29), Holm over every (signal, regime,
target) cell. PASS = registered sign on BOTH halves AND Holm < 0.05.

REGISTERED PREDICTIONS (2026-09-24, before running)
  signs: the 14 old signals carry the sign doc 12 FOUND over all days (toptrader and vix
  contrarian); the new ones: breadth -, fear_greed -, dvol +, dvol_chg7 -, mkt_funding -,
  btc_dd90 - (a deeper fall -> a better next week; all four "contrarian" signs say that
  extremes of fear precede bounces).
  outcome: at most two cells pass Holm, both in BEAR and both contrarian (breadth or Fear &
  Greed on the alt index). Nothing passes in CHOP - chop is defined as the absence of a trend,
  and every doc-12 signal is a trend or flow proxy.
  If something passes, it gets a costed trade with a causal threshold before anything is claimed.

    python -m backtest.regime_signals
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.btc_signals import holm, spread_t  # noqa: E402
from backtest.market_neutral import btc_regime, drop_non_crypto, load_panel  # noqa: E402
from backtest.wide_book import MIN_AGE_D, eligibility  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SIG = ROOT / "strategy_analysis" / "data" / "signals"
CUT = pd.Timestamp("2024-08-29")
H = 7
OLD = dict(cb_prem=+1, cb_prem_chg=+1, oi_vs_px=-1, toptrader=-1, taker=+1, alt_vs_btc=+1,
           mvrv=-1, netflow=-1, qqq_trend=+1, dxy_trend=-1, vix=+1, tsmom=+1, btc_vol=+1,
           adr_growth=+1)
NEW = dict(breadth20=-1, breadth50=-1, fear_greed=-1, dvol=+1, dvol_chg7=-1, mkt_funding=-1,
           btc_dd90=-1)


def member_mask(C, first, elig):
    """bool T x N: coin is PIT-eligible in that row's month and old enough."""
    cols = list(C.columns)
    months = C.index.strftime("%Y-%m")
    fv = np.array([pd.Timestamp(first[s]).value for s in cols])
    em = {m: np.array([m in elig.get(s, ()) for s in cols]) for m in sorted(set(months))}
    age = ((C.index.asi8[:, None] - fv[None, :]) // 86_400_000_000_000) >= MIN_AGE_D
    return np.vstack([em[m] for m in months]) & age


def build(C, F, first):
    """Features and targets indexed by day D (bar-open date). Row D-1 of C is the close at the
    start of day D, so 'data through the end of D-1' is C up to row D-1, i.e. shift(1)."""
    X = C.to_numpy(float)
    ff = pd.DataFrame(X).ffill().to_numpy()
    m60 = member_mask(C, first, drop_non_crypto(eligibility(60))) & np.isfinite(X)
    m40 = member_mask(C, first, drop_non_crypto(eligibility(40))) & np.isfinite(X)
    out = pd.DataFrame(index=C.index)
    for n in (20, 50):
        ma = C.rolling(n, min_periods=n).mean().to_numpy()
        above = (X > ma) & np.isfinite(ma) & m60
        cnt = (np.isfinite(ma) & m60).sum(1)
        out[f"breadth{n}"] = pd.Series(above.sum(1) / np.where(cnt > 0, cnt, np.nan), index=C.index).shift(1)
    f7 = F.reindex(columns=C.columns).fillna(0.0).rolling(7).sum().to_numpy()
    out["mkt_funding"] = pd.Series(np.nanmedian(np.where(m60, f7, np.nan), axis=1), index=C.index).shift(1)
    b = C["BTCUSDT"]
    out["btc_dd90"] = (b / b.rolling(90, min_periods=30).max() - 1).shift(1)
    fg = pd.read_csv(SIG / "fear_greed.csv", parse_dates=["time"]).set_index("time")["value"]
    fg.index = fg.index.astype("datetime64[ns]")
    out["fear_greed"] = fg.reindex(C.index).ffill().shift(1)
    dv = pd.read_csv(SIG / "dvol_btc.csv", parse_dates=["time"]).set_index("time")["close"]
    dv.index = dv.index.astype("datetime64[ns]")
    dv = dv.reindex(C.index).ffill(limit=3)
    out["dvol"] = dv.shift(1)
    out["dvol_chg7"] = (dv / dv.shift(7) - 1).shift(1)
    old = pd.read_csv(ROOT / "logs" / "btc_signals_features.csv.gz", index_col=0, parse_dates=True)
    old.index = old.index.astype("datetime64[ns]")
    out = out.join(old[list(OLD)], how="left")
    # targets: from the open of D (= close of row D-1) to the open of D+H (= close of row D+H-1)
    fwd_btc = b.shift(-(H - 1)) / b.shift(1) - 1
    alt = np.full(len(C), np.nan)
    for d in range(1, len(C) - H + 1):
        mem = m40[d - 1]
        if mem.sum() >= 10:
            alt[d] = np.nanmean(ff[d + H - 1, mem] / X[d - 1, mem] - 1)
    out["fwd_btc"], out["fwd_alt"] = fwd_btc, alt
    return out


def main():
    from scipy.stats import norm
    C, F, first = load_panel()
    C.index = C.index.astype("datetime64[ns]")
    F.index = C.index
    reg = btc_regime(C)
    D = build(C, F, first)
    D["regime"] = reg.reindex(D.index)
    D = D[D.index <= pd.Timestamp("2026-09-11")]           # the cached doc-12 features end here
    print(f"days {D.index[0]:%Y-%m-%d} .. {D.index[-1]:%Y-%m-%d} | regime days: "
          + "  ".join(f"{k} {int(v)}" for k, v in D.regime.value_counts().items()))
    print("for each regime, the target's mean next-7-day return (the baseline a signal has to beat):")
    for r in ("bull", "chop", "bear"):
        g = D[D.regime == r]
        print(f"  {r:<5} BTC {g.fwd_btc.mean()*100:+.2f}%  alt index {g.fwd_alt.mean()*100:+.2f}%  (n {len(g)})")
    sigs = {**OLD, **NEW}
    res = []
    for regime in ("chop", "bear"):
        for tgt in ("fwd_btc", "fwd_alt"):
            for k, sgn in sigs.items():
                g = D[D.regime == regime][[k, tgt]].dropna()
                if len(g) < 120:
                    res.append((regime, tgt, k, sgn, len(g), np.nan, np.nan, np.nan, np.nan, 1.0)); continue
                est, t = spread_t(g[k], g[tgt], g.index, reps=1000)
                tu, ho = g[g.index < CUT], g[g.index >= CUT]
                a = spread_t(tu[k], tu[tgt], tu.index, reps=10)[0] if len(tu) > 60 else np.nan
                bb = spread_t(ho[k], ho[tgt], ho.index, reps=10)[0] if len(ho) > 60 else np.nan
                p = float(2 * (1 - norm.cdf(abs(t)))) if np.isfinite(t) else 1.0
                res.append((regime, tgt, k, sgn, len(g), est, t, a, bb, p))
    adj = holm(np.array([r[-1] for r in res]))
    print(f"\n{len(res)} cells, Holm over all of them. Spread = top-third minus bottom-third of the signal, "
          "next-7-day return, %")
    cur = None
    for (regime, tgt, k, sgn, n, est, t, a, bb, p), h in zip(res, adj):
        if (regime, tgt) != cur:
            cur = (regime, tgt)
            print(f"\n  {regime.upper()} -> {'BTC' if tgt == 'fwd_btc' else 'ALT INDEX'}")
            print(f"  {'signal':<12}{'pred':>5}{'n':>6}{'spread':>9}{'t':>7}{'TUNE':>8}{'HOLD':>8}{'Holm p':>8}  verdict")
        if not np.isfinite(est):
            print(f"  {k:<12}{sgn:>+5d}{n:>6}   too few"); continue
        ok = np.isfinite(a) and np.isfinite(bb) and np.sign(a) == sgn and np.sign(bb) == sgn
        wrong = np.isfinite(a) and np.isfinite(bb) and np.sign(a) == -sgn and np.sign(bb) == -sgn
        v = ("PASS" if ok and h < 0.05 else "sign holds both halves" if ok
             else "OPPOSITE sign both halves" if wrong else "")
        print(f"  {k:<12}{sgn:>+5d}{n:>6}{est*100:>+8.2f}%{t:>+7.2f}{a*100:>+7.2f}%{bb*100:>+7.2f}%{h:>8.3f}  {v}")
    D.to_csv(ROOT / "logs" / "regime_signals_features.csv.gz", compression="gzip")


if __name__ == "__main__":
    main()

"""SETTLING VSA NOW instead of waiting four months for the forward test.

WHY THE FOUR-MONTH WAIT IS AVOIDABLE
------------------------------------
vsa_forward.py exists because I wrote that "the historical crypto holdout has now
been spent on this question, so no further retrospective slicing can settle it."
Two things have changed since, and both make that statement wrong.

1. THE HISTORICAL VERDICT WAS MEASURED WITH THE PROFIT CAP.
   vsa.py, vsa_crossasset.py and vsa_forward.py all use SL=2.0, TP=3.0 - a winner
   is force-closed at +1.5R. That cap is now known to be the single error that
   produced false negatives across eighteen families (see holdout_uncapped.py:
   trend went 3/11 -> 11/11 positive once it was removed). The famous "VSA failed
   the cross-asset gate, 16/28" is therefore not a spent holdout. It is a
   CONTAMINATED MEASUREMENT. Re-measuring the same question with a correct exit is
   new information, not post-hoc slicing of an exhausted sample.

   This also means the forward test as configured cannot answer the money
   question at all - it inherits the same cap. At best it says whether the
   absorption filter SEPARATES good trades from bad, with both arms crippled.

2. THERE ARE NOW 202 DELISTED COINS OF GENUINELY VIRGIN DATA.
   dead_fetch.py downloaded them AFTER every VSA hypothesis was formed, to fix
   survivorship bias. Nothing about VSA - not the dev cut, not the liquidity
   split, not the bb_break parameters - was chosen with any knowledge of these
   series. That is the same epistemic status as forward data, and it is
   already on disk.

   Forward data arrives at ~3 trades/day/cell. Four months buys ~400 trades per
   cell. The dead set contains thousands, right now, across 202 independent
   assets instead of 20 correlated ones. It is a strictly stronger test that
   costs minutes rather than a third of a year.

   What forward data still has that this does not: it is immune to any
   preprocessing decision I might unconsciously tune. So this file does not
   replace vsa_forward.py - it front-runs it, and the forward test keeps
   accumulating as the independent check.

PREDICTION REGISTERED BEFORE THE FIRST RUN (2026-09-13), same shape as the
forward test's H1/H2/H3 so the two are directly comparable:

  H1  on the DEAD set:  diff = meanR(dev < -0.5) - meanR(dev >= -0.5) > 0
  H2  diff(high-liquidity half) > diff(low-liquidity half)
  SUCCESS: diff > 0 at t >= 2 ACROSS COINS (not pooled) and > half of coins
           improved, on data whose exit rule is uncapped.

  MY EXPECTATION IS FAILURE. The cross-asset gate failed 16/28, the liquidity
  story was invented after seeing that failure, and it had no mechanism (zero-dev
  share and range/volume correlation showed no liquidity gradient). I expect diff
  ~= 0.00 +/- 0.03 and roughly half the coins improving. Writing that down so a
  null cannot be reinterpreted afterwards as "well, it was directionally right".

WHY THE t IS TAKEN ACROSS COINS AND NOT ACROSS TRADES
    Pooling trades treats 40,000 trades as 40,000 independent draws. They are
    not: crypto coins move together, so one good month for the whole market
    inflates a pooled t enormously. The honest unit of independence here is the
    COIN. Both are printed - if the pooled t is large and the across-coin t is
    not, the pooled number is measuring market direction, not the filter.

    python -m backtest.vsa_fast            (dead set only, the real test)
    python -m backtest.vsa_fast --live     (adds the 20 forward-test coins)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.dead_fetch import DEAD  # noqa: E402
from backtest.holdout_sweep import signals_for  # noqa: E402
from backtest.mass_search import FILTERS, fetch  # noqa: E402
from backtest.convex import run_uncapped  # noqa: E402
from backtest.rtest import run_r  # noqa: E402
from backtest.vsa import vsa_indicator  # noqa: E402
from bot.core.indicators import atr as atr_ind  # noqa: E402

FEE_BP = 10.0                 # matches vsa_forward.py exactly
DEV_CUT = -0.5                # pre-registered, unchanged
PRIMARY = ("bb_break", (30, 1.5))
SL = 2.0
MIN_TRADES = 30               # per coin, per cell, to count that coin at all
MIN_BARS = 1200               # a coin needs history past the 336-bar VSA warm-up

LIVE = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "BNBUSDT", "SOLUSDT", "ARBUSDT",
        "LINKUSDT", "ADAUSDT", "DOGEUSDT", "DOTUSDT",
        "XLMUSDT", "AAVEUSDT", "UNIUSDT", "PEPEUSDT", "ETCUSDT", "BCHUSDT",
        "ATOMUSDT", "APTUSDT", "NEARUSDT", "OPUSDT"]


# --------------------------------------------------------------------------
def cell_split(df, exit_kw, dev_shift=1, close_at_end=None):
    """Every bb_break signal taken once; dev RECORDED at entry, never gated.

    This is the forward test's paired design run on history. The two cells come
    from ONE pass, so they cannot differ because of position-overlap: splitting
    the signal series first and running twice would let each half take trades the
    other half was holding through, which silently changes the sample.

    dev is sampled at the ENTRY bar. run_uncapped enters at open[i] and reports
    exit index i_x with bars held b, so the entry bar is i_x - b exactly.
    """
    sig = FILTERS["none"](df, signals_for(df, *PRIMARY))
    if int((sig != 0).sum()) == 0:
        return None
    if exit_kw is None:                       # the OLD capped rule, for contrast
        R, idx = run_r(df, sig, SL, 3.0, FEE_BP)
        bars = np.zeros(len(idx), dtype=int)   # run_r gives no hold length
        ent = None
    else:
        R, idx, bars, _d = run_uncapped(df, sig, sl_mult=SL, fee_bp=FEE_BP,
                                        close_at_end=close_at_end, **exit_kw)
        ent = np.maximum(idx - bars, 0)
    if not len(R):
        return None
    dev = vsa_indicator(df).shift(dev_shift).to_numpy(float)
    if ent is None:
        # run_r reports only exit indices. Recover entries by replaying its exact
        # state machine, including its ATR guard - without that guard the
        # reconstruction would count early NaN-ATR bars as entries that run_r
        # skipped, and every dev would then be assigned to the wrong trade.
        a = atr_ind(df, 14).to_numpy(float)
        ent = _entries_from_signals(sig.to_numpy(), idx,
                                    np.isfinite(a) & (a > 0))
    dv = dev[np.clip(ent, 0, len(dev) - 1)]
    ok = np.isfinite(dv)                      # first 336 bars are unclassifiable
    if ok.sum() < MIN_TRADES:
        return None
    R, dv = R[ok], dv[ok]
    inf = dv < DEV_CUT
    return dict(n_in=int(inf.sum()), n_out=int((~inf).sum()),
                m_in=float(R[inf].mean()) if inf.any() else np.nan,
                m_out=float(R[~inf].mean()) if (~inf).any() else np.nan,
                sd_in=float(R[inf].std(ddof=1)) if inf.sum() > 1 else np.nan,
                sd_out=float(R[~inf].std(ddof=1)) if (~inf).sum() > 1 else np.nan,
                R_in=R[inf], R_out=R[~inf])


def _entries_from_signals(s, exits, atr_ok):
    """Entry bar for each exit, replaying run_r's flat/in-position state machine.

    atr_ok is run_r's own entry guard (finite, positive ATR at i-1); omitting it
    would shift every trade's dev by one position on any coin whose first signal
    lands inside the ATR warm-up.
    """
    out, k, i = [], 0, 1
    n = len(s)
    while k < len(exits) and i < n:
        if s[i] != 0 and atr_ok[i - 1]:
            out.append(i)
            k += 1
            i = int(exits[k - 1]) + 1          # flat again only after that exit
        else:
            i += 1
    while len(out) < len(exits):
        out.append(int(exits[len(out)]))
    return np.asarray(out, dtype=int)


def agg(cells):
    """Pool, and separately average the PER-COIN differences.

    The across-coin statistic is the one that matters: it treats each coin as one
    observation, so a single market-wide good stretch cannot manufacture
    significance the way it can in the pooled t.
    """
    usable = [c for c in cells if c and c["n_in"] >= MIN_TRADES
              and c["n_out"] >= MIN_TRADES]
    if not usable:
        return None
    Ri = np.concatenate([c["R_in"] for c in usable])
    Ro = np.concatenate([c["R_out"] for c in usable])
    sei = Ri.std(ddof=1) / np.sqrt(len(Ri))
    seo = Ro.std(ddof=1) / np.sqrt(len(Ro))
    sed = float(np.sqrt(sei ** 2 + seo ** 2))
    pooled_diff = float(Ri.mean() - Ro.mean())
    per = np.asarray([c["m_in"] - c["m_out"] for c in usable], float)
    per = per[np.isfinite(per)]
    t_coin = (float(per.mean() / (per.std(ddof=1) / np.sqrt(len(per))))
              if len(per) > 1 and per.std(ddof=1) > 0 else 0.0)
    better = int((per > 0).sum())
    return dict(coins=len(usable), n_in=len(Ri), n_out=len(Ro),
                m_in=float(Ri.mean()), m_out=float(Ro.mean()),
                md_in=float(np.median(Ri)), md_out=float(np.median(Ro)),
                w_in=float((Ri > 0).mean() * 100),
                w_out=float((Ro > 0).mean() * 100),
                diff=pooled_diff, t_pool=pooled_diff / sed if sed else 0.0,
                coin_diff=float(per.mean()), med_diff=float(np.median(per)),
                t_coin=t_coin, better=better, total=len(per),
                sign_p=sign_test(better, len(per)))


def sign_test(k, n):
    """Two-sided exact binomial p for k of n coins improved, against p=0.5.

    THIS IS THE HEADLINE STATISTIC, not mean R, and the reason is visible in the
    output: on delisted microcaps a 20xATR trail on a token that rose 1000x before
    dying produces an R in the thousands, because R's denominator is the ATR at
    entry when the coin was worth a fraction of a cent. One such trade moves a
    mean over 37,000 trades by several whole R. Those returns are not fiction -
    the trade really did that - but a MEAN built from them measures which cell
    caught the lottery ticket, not whether the filter selects better trades.

    Counting how many of ~170 independent coins the filter improved is immune to
    that entirely: a coin counts once whether its best trade made 1R or 5000R.
    """
    if n == 0:
        return float("nan")
    from math import comb
    tail = sum(comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2.0 ** n
    return float(min(1.0, 2.0 * tail))


def load_dead(limit=None):
    files = sorted(DEAD.glob("*_1h.csv.gz"))
    if limit:
        files = files[:limit]
    out = {}
    for f in files:
        try:
            d = pd.read_csv(f, parse_dates=["time"])
        except Exception:
            continue
        if len(d) < MIN_BARS:
            continue
        out[f.name.split("_")[0]] = d
    return out


def load_live():
    out = {}
    for s in LIVE:
        try:
            d = fetch(s, "1h", 2400)
        except Exception:
            continue
        if len(d) >= MIN_BARS:
            out[s] = d
    return out


HDR = (f"{'exit rule':<26} {'coins':>5} {'n dev<-.5':>9} {'meanR':>8} "
       f"{'win%':>5} {'n rest':>8} {'meanR':>9} {'win%':>5} {'medR d':>7} "
       f"{'t coin':>7} {'coins+':>9} {'sign p':>8}")


def row(tag, a):
    if not a:
        return f"{tag:<26} (insufficient)"
    return (f"{tag:<26} {a['coins']:>5} {a['n_in']:>9} {a['m_in']:>+8.3f} "
            f"{a['w_in']:>5.1f} {a['n_out']:>8} {a['m_out']:>+9.3f} "
            f"{a['w_out']:>5.1f} {a['med_diff']:>+7.3f} {a['t_coin']:>+7.2f} "
            f"{a['better']:>4}/{a['total']:<4} {a['sign_p']:>8.2}")


EXITS = [("capped 3R (the OLD rule)", None),
         ("trail 3xATR", dict(mode="trail_atr", trail=3.0)),
         ("trail 5xATR", dict(mode="trail_atr", trail=5.0)),
         ("trail 10xATR", dict(mode="trail_atr", trail=10.0)),
         ("trail 20xATR", dict(mode="trail_atr", trail=20.0))]


def panel(data, title, close_at_end=None, dev_shift=1):
    print("=" * 118)
    print(title)
    print("=" * 118)
    print(HDR)
    best = None
    for tag, ex in EXITS:
        cells = [cell_split(df, ex, dev_shift, close_at_end)
                 for df in data.values()]
        a = agg(cells)
        print(row(tag, a), flush=True)
        if a and (best is None or abs(a["t_coin"]) > abs(best[1]["t_coin"])):
            best = (tag, a)
    print()
    return best


def liq_split(data, ex, close_at_end=None):
    """HIGH vs LOW liquidity by median dollar volume per bar - a MECHANICAL rule,
    the median of this sample, not a hand-picked list. H2 lives or dies here."""
    dv = {k: float((d["close"] * d["volume"]).median()) for k, d in data.items()}
    med = float(np.median(list(dv.values())))
    out = {}
    for name, keys in (("HIGH liq (above median $vol)",
                        [k for k in data if dv[k] >= med]),
                       ("LOW  liq (below median $vol)",
                        [k for k in data if dv[k] < med])):
        out[name] = agg([cell_split(data[k], ex, 1, close_at_end) for k in keys])
    return out, med


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="also run the 20 forward-test coins (NOT virgin data)")
    ap.add_argument("--limit", type=int, help="cap the dead set, for a smoke test")
    args = ap.parse_args()

    print(__doc__.split("PREDICTION REGISTERED")[0].rstrip())
    print("\nPREDICTION REGISTERED BEFORE RUNNING: diff > 0 at across-coin t >= 2")
    print("and >half of coins improved. My stated expectation: FAILURE, diff ~0.\n")

    dead = load_dead(args.limit)
    print(f"loaded {len(dead)} delisted coins from {DEAD}")
    print(f"   these were downloaded AFTER every VSA hypothesis was formed -> "
          f"virgin\n")

    b_dead = panel(dead, "1. THE REAL TEST — 202 DELISTED COINS, VIRGIN DATA. "
                         "Exit at last close (announced delist).",
                   close_at_end="close")

    # H2: the liquidity differential, on virgin data, with a mechanical split
    ex = dict(mode="trail_atr", trail=5.0)
    print("=" * 118)
    print("2. H2 — DOES THE FILTER IMPROVE WITH LIQUIDITY?  (trail 5xATR, "
          "dead set, split at this sample's median $vol/bar)")
    print("=" * 118)
    print(HDR)
    groups, med = liq_split(dead, ex, close_at_end="close")
    for name, a in groups.items():
        print(row(name, a), flush=True)
    hi, lo = groups.get("HIGH liq (above median $vol)"), \
        groups.get("LOW  liq (below median $vol)")
    if hi and lo:
        print(f"\n   median split at ${med:,.0f}/bar")
        print(f"   per-coin MEDIAN diff:  HIGH {hi['med_diff']:+.4f}   "
              f"LOW {lo['med_diff']:+.4f}   differential "
              f"{hi['med_diff'] - lo['med_diff']:+.4f}")
        print(f"   coins improved:        HIGH {hi['better']}/{hi['total']}   "
              f"LOW {lo['better']}/{lo['total']}")
        print(f"   H2 (HIGH better than LOW): "
              f"{'HOLDS' if hi['med_diff'] > lo['med_diff'] else 'FAILS'}"
              f"   — but H2 is only interesting if H1 passed at all")
    print()

    # causality robustness: the live bot uses dev at i-2, vsa.py used i-1
    print("=" * 118)
    print("3. CAUSALITY ROBUSTNESS — dev sampled one bar earlier (what the live "
          "bot actually sees)")
    print("=" * 118)
    print(HDR)
    for sh, lbl in ((1, "dev at i-1 (vsa.py)"), (2, "dev at i-2 (live bot)")):
        a = agg([cell_split(df, ex, sh, "close") for df in dead.values()])
        print(row(lbl, a), flush=True)
    print()

    if args.live:
        live = load_live()
        print(f"loaded {len(live)}/{len(LIVE)} forward-test coins")
        print("   NOT virgin: the liquidity groups were formed after seeing "
              "these. Suggestive only.\n")
        panel(live, "4. THE 20 FORWARD-TEST COINS ON HISTORY — what the forward "
                    "test would say in four months")

    print("=" * 118)
    print("HOW TO READ THIS")
    print("=" * 118)
    print("HEADLINE = 'coins+' and its sign p. Fraction of independent coins the")
    print("filter improved, tested against a coin flip. It is immune to the")
    print("outlier problem that makes mean R unreadable on this data (a dead")
    print("microcap that rose 1000x before delisting can post an R in the")
    print("thousands, because R's denominator is the ATR from when it was worth")
    print("a fraction of a cent - so a single trade can move a mean over 37,000")
    print("trades by whole R).")
    print("\nSECOND: 't coin', the across-coin t on per-coin differences. Needs")
    print("|t| >= 2 in the POSITIVE direction to support the filter.")
    print("\nIGNORE any large 'meanR' in the rest column at wide trails - that is")
    print("the lottery-ticket effect above, not an edge the filter is missing.")
    print("\nIf coins+ is at or below half everywhere, VSA is settled TODAY: the")
    print("filter does not separate, the capped exit was not hiding anything,")
    print("and vsa_forward.py can be stopped rather than run four more months.")
    print("If coins+ is BELOW half significantly, the filter is actively")
    print("harmful - which is still a usable result: invert it or drop volume.")


if __name__ == "__main__":
    main()

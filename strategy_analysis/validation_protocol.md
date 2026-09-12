# Validation protocol — the gate every strategy must pass

Written 2026-09-11, after a strategy passed a permutation test at p=0.0050 and
then lost 12.6%/yr on data it had never seen. Both numbers were correct. The
mistake was believing the first one meant something it does not.

Nothing goes near real money without clearing every gate below, in order.

---

## The gates

| # | Gate | Catches | Blind to | Tool |
|---|------|---------|----------|------|
| 1 | In-sample optimisation | nothing — this is where bias is *created* | everything | `mass_search.py` |
| 2 | Parameter-plateau check | single-setting flukes | regime fits | manual sweep |
| 3 | In-sample MCPT | mining within a declared search | choices made *before* the search was declared | `mcpt.py --step insample` |
| 4 | Walk-forward + MCPT | parameters that decay over time | the walk-forward's own tuned settings | `mcpt.py --step walkforward` |
| 5 | **Virgin holdout** | regime fits, pre-search choices, everything above | the future | `final_oos.py` |
| 6 | Forward test on demo | execution reality, spread, slippage | slow — months per verdict | the live bots |
| 7 | MAR sanity check | results too good to be real | — | see below |

Gate 5 is the one that matters, and it is the one I skipped for months.

## What MCPT can and cannot do

MCPT shuffles the bars so serial structure dies while the return distribution,
volatility, fat tails and total drift survive. It then re-runs **the whole
search** on each shuffle, so the multiple-comparisons penalty is applied
automatically. That is genuinely valuable, and it correctly killed our crypto
momentum work (p 0.29 on BTC, 0.29 on SOL).

What it cannot see: the strategy *definition* is fixed before it runs. Family,
direction constraint, filter set, exit multiples, timeframe, and which slice of
history you even loaded — all chosen by a human who had already looked at the
data. MCPT holds those constant and tests the residue.

**Passing MCPT rules out one failure mode. It does not establish an edge.**

## The case study — keep this, it is the whole lesson

Strategy: `donch_lo(80,200)` + er30 filter on gold (PAXG 1h), 2 ATR stop /
3 ATR target, 10bp costs. Exactly the family the live forex bot trades.

| Evidence | Result |
|---|---|
| Parameter plateau | all 20 configs profitable, PF 1.18–1.47, smooth |
| In-sample MCPT | **p = 0.0050** — 0 of 200 shuffles beat it |
| Walk-forward MCPT | **p = 0.0099** — 0 of 100 shuffles beat it |
| Walk-forward PF | 1.386, implying +12.9%/month at 3% risk |
| MAR ratio | 3.0–5.3 — above the plausible ceiling (gate 7 flagged it) |
| **Virgin holdout (2.54 yr)** | **PF 0.752, mean R −0.169, −12.6%/yr, 3 losing years** |

Every alternative explanation was ruled out before accepting this:

- **Test bias?** No. Calibration on 12 no-edge datasets: mean p = 0.546
  (expected 0.5), false-positive rate at 5% = 0.00. The machinery is sound, so
  p = 0.0050 was a genuine result, not an artefact.
- **Bad holdout data?** No. 6 zero-volume bars in 31,304, 43 flat bars, max gap
  0.62%, median bar range within 5% of the development window.
- **A single fluke setting?** No. All 20 parameter combinations were profitable
  in development with a smooth monotonic plateau.
- **Unlucky permutations?** No. 0 of 200 and 0 of 100.

What remained was regime: gold's er30 pass rate was 28.0% in development versus
20.1% in the holdout. The strategy needed trend persistence the recent window
happened to supply in abundance.

Mechanism, once measured: gold's er30 pass rate was **28.0%** in the window
used for development and **20.1%** in the holdout. The recent period supplied
40% more trend persistence than normal. The strategy was a bet on that regime,
not an edge. Data quality in the holdout was verified clean first (6 zero-volume
bars in 31,304, gaps under 0.62%) — the failure is real, not an artifact.

## Gate 7: the MAR sanity check

MAR = CAGR / max drawdown. Long-run systematic track records land around
0.5–1.0; a sustained 2.0 is top-decile. Treat anything above ~2.5 as a red flag
that something leaked.

Our gold walk-forward showed MAR 3.0–5.3. That alone should have stopped me
before the holdout did.

Its corollary bounds the whole project:

```
tolerate 20% drawdown -> ~2.8%/month     ceiling
tolerate 30% drawdown -> ~4.0%/month
tolerate 40% drawdown -> ~5.0%/month
10%/month = 214% CAGR -> needs 107% drawdown at MAR 2  = impossible
```

**10%/month is not a hard target, it is an arithmetically unavailable one.**
A realistic ceiling for a survivable systematic strategy is 3–5%/month, and
reaching even that requires an edge we have not yet found.

## Gate 5b: cross-INSTRUMENT holdout (added 2026-09-11)

A time holdout is not enough. The NASDAQ level-fade strategy passed, on NQ 5m:
all 24 configs positive, a monotone decay across four timeframes, *stronger* in
liquid cash hours than overnight (the opposite of an artifact), tolerance of
spread up to ~5.5 points, and breadth MCPT p=0.0565. Five converging signals.

It then failed on every close analogue — ES 8/24 configs, RTY 12/24, YM 5/24,
GC 0/24 — with only 1 of 5 non-NQ instruments positive. ES and RTY correlate
>0.9 with NQ and share its microstructure; a real equity-index effect cannot be
absent there. The effect was NQ-specific, i.e. noise in one 60-day window.

So: **run every candidate on instruments that played no part in finding it.**
Different instruments are a second, independent axis of out-of-sample, and it is
often cheaper to obtain than more history (Yahoo caps 5m data at 60 days, but
there are dozens of liquid futures).

Corollary, learned the hard way twice in one day: converging evidence is not
proof. Cross-era consistency was manufactured by the ATR look-ahead; monotone
cross-timeframe ordering was manufactured by chance. Both were exactly the
patterns the textbooks say to look for.

## HOLDOUT CONTAMINATION LEDGER — read before trusting a "holdout" result

A holdout is spent the moment you look at its structure. Track it honestly or you
will fool yourself twice with the same data.

| Data | Status | Spent on |
|---|---|---|
| crypto 1h holdout (2020-02..2024-03, 9 assets) | **PARTLY SPENT** | the 18-family sweep (one clean look); then its `atr_pct` DECILE structure was examined during meta-labeling, so any volatility-band hypothesis is now fitted to it |
| PAXG gold holdout (2020-08..2024-03) | **SPENT** | one clean look, `final_oos.py` |
| NQ/ES/YM/RTY/GC/CL 5m (60d) | **SPENT** | level_fade cross-instrument test |
| crypto 5m (180d) | partly | fill-rate and fee-scaling measurement only |
| crypto 1h XS holdout (2025-04..2026-09, 28 coins) | **2 of 2 looks SPENT — CLOSED** | look #1 cross-sectional momentum at lb=48/hold=24/k=5/Kaufman-gate-0.30 (neutral −12.1%/yr, long-only +12.9%); look #2 at lb=168/hold=24/k=5/no-gate. No third look. Further work on cross-sectional momentum needs data after 2026-09-12. |

Worked example of the cost: the "volatility middle band" looked strong on the
crypto holdout (+0.0299R vs -0.0071 unfiltered, 7/9 assets positive) — but the
band edges were chosen from that holdout's own deciles, and on the development
window the rule REVERSED to -0.0070R. Testing it against the window it was not
fitted to is what exposed it.

Rule: when a hypothesis is generated by inspecting data, that data can no longer
test it. Either hold a second slice back from the start, or test on a different
axis (other assets, other instruments) as the cross-asset gate does.

## First strategy to clear the battery (2026-09-12)

**Market-neutral cross-sectional momentum.** Rank 21 long-history coins by 168h
return, long the top 5 and short the bottom 5 at equal dollars, rebalance daily,
Bitget taker fees charged on actual turnover.

| Gate | Result |
|---|---|
| Grid robustness | 96/120 configs positive Sharpe (**80%**, chance is 50%), median +0.58 |
| Dev (21 coins, 39,748 h) | +34.7%/yr, Sharpe **+1.09**, beta **−0.01** |
| MCPT, shared-index, 300 perms | **p = 0.0033** — 0/300 beat real; permuted mean −0.525, sd 0.452, max +0.649 |
| Virgin holdout, 500 unseen days | +12.6%/yr, Sharpe +0.62, beta −0.06, **t = +0.72 (NOT significant)** |
| Cost audit | fees 13.5%/yr against gross 29.1%/yr — 46% of gross |

The permuted mean being **negative** matters: with no signal you still pay the
fees, so the null world loses money. The edge is measured net of that.

### The finding that made it work
The same signal, same data, same period, two portfolio constructions:

| | holdout return | holdout DD | beta |
|---|---|---|---|
| long-only top-5 | **−7.3%/yr** | 57.0% | +0.91 |
| market-neutral L/S | **+12.6%/yr** | 23.7% | −0.06 |

A 20-point swing from removing beta. The earlier verdict "regime-gated momentum
fails in portfolio simulation (+0.03R, 35–59% DD)" was a **portfolio construction
failure misdiagnosed as an edge failure**. At ρ≈0.8, 20 coins is ~1.6 effective
bets — 20× the risk for 1.6× the diversification.

### The Kaufman gate REVERSES sign between the two designs
The efficiency-ratio ≥ 0.30 filter that made the long-only strategy work is
**destructive to the ranking version — all 60 gated configs negative, t = −9 to
−25.** It keeps only cleanly-trending coins, so the bottom-ranked survivor is
still rising and the short leg is shorting a live uptrend. A filter is not a
property of a signal; it is a property of a signal *plus a construction*.

### What it is NOT
Not a 10%/month strategy. At 1× it is ~12–35%/yr at Sharpe 0.6–1.1. The holdout
measured a +10% month **6% of the time**, matching the normal model's 6.3% — so
the leverage arithmetic is calibrated: 2× gives a +10% month ~25% of the time with
~47% drawdowns; 4× reaches ~40% but with ~95% drawdown, i.e. ruin.

### Two dev-measured improvements that CANNOT be tested on existing data
The holdout is spent (2 looks, see ledger). Both need data created after
2026-09-12, which `xs_paper.py` is now generating:
- dispersion gate p50 — dev Sharpe **2.05** vs 1.26, fees 7.8 vs 12.9 %/yr
- index hedge k=5 h=8 — dev MAR **1.94** vs 1.38, Sharpe 1.67 vs 1.26

### Two methodology bugs found in this run
1. **The MCPT was silently testing a 190-day stub.** `load_frames` intersects the
   index across all coins, and TONUSDT (listed 2024-08) collapsed 45,575 bars to
   4,577. On that stub the permuted Sharpe sd was 1.345 — unable to resolve
   anything below Sharpe 2.2 — and it returned a meaningless p=0.2687. Fixed with
   `LONG_UNIVERSE`. **Any shared-index MCPT must print its bar count**; an
   intersection can quietly destroy a test.
2. A "bug" that was not one: the `replace(0)→ffill(limit=hold-1)` weight fill was
   *correct* — the limit blocks exactly at the next rebalance row. Verified by a
   numpy rewrite reproducing every figure to the decimal. The rewrite was still
   worth it for a ~50× speedup.

## Gate 5c: the VIRGIN-COIN gate, and what it found (2026-09-12)

When the time holdout is spent, **unused instruments are still a valid
out-of-sample axis**. Every parameter for cross-sectional momentum was chosen on
the 28 coins in `xs_momentum.UNIVERSE`; ~58 other liquid perps took no part in any
choice. Testing frozen parameters on those is a real test, available in hours
rather than months. `backtest/xs_wide.py`.

### Result 1: it killed an apparent upgrade, in one pass
`momsh_168h` (rank by risk-adjusted move) scored **1.64 vs 0.95** on the coins it
was searched on — a best-of-14 result. On virgin coins it **lost to plain
`mom_168h` in 6/6 cells** (k=5/10/20 × 6/12bp). A best-of-N figure on its own
search data is a hypothesis; this settled it in two hours. It is retained in
`xs_paper.py` as a negative control with a pre-registered prediction (D < A).

### Result 2: the wide-universe gain is survivorship, not edge
`mom_720h`, frozen, Sharpe by group over 2022-08..2026-09:

| group | n | k5/6bp | k5/12bp | k10/6bp | k10/12bp |
|---|---|---|---|---|---|
| USED majors (tuned on) | 27 | +0.83 | +0.57 | +0.72 | +0.44 |
| **VIRGIN established** | 24 | **−0.02** | **−0.24** | **−0.03** | **−0.28** |
| VIRGIN recent listings | 34 | +0.70 | +0.51 | +0.99 | +0.78 |
| VIRGIN all | 58 | +0.59 | +0.38 | +0.47 | +0.21 |

The all-58 result is a blend; the edge lives **entirely in the recent listings** —
WIF, BONK, PENGU, TRUMP, MUBARAK, TUT, DOGS, TREE, SOPH, WLFI, ONDO, VIRTUAL. That
is the maximum-survivorship-bias population: coins that launched and pumped are in
today's top-120 by volume, and the thousands that launched and died are absent
entirely. Binance's public API does not serve delisted history, so the bias cannot
be corrected — only recognised.

**Conclusion: do NOT widen the universe.** "More coins" does not improve this
strategy; it imports survivorship bias.

### What this does to the earlier verdict
It narrows the claim and lowers confidence. Cross-sectional momentum's support is
now specifically **large-cap crypto**: MCPT p=0.0033 and a positive 500-day unseen
time holdout, both on that universe. A comparable-sized universe of established
mid-caps that was never used shows **nothing**. If the effect were a robust
economic phenomenon it should appear in mid-caps too — arguably more strongly,
since they are less efficient. Its absence there is real evidence that the majors
result is narrower, or luckier, than it looked this morning.

It is not a refutation: the majors result has two independent confirmations that
do not depend on coin choice. But the confident reading ("first strategy to clear
the battery") should now be stated as "clears the battery **on large-cap crypto
only**, and fails to generalise to a comparable unused universe."

### Reusable lesson
A shared-index MCPT **must print its coin count and bar count**. Restricting the
virgin set to full-history coins for the permutation test cut it to 24 coins and
flipped the real Sharpe from +0.59 to −0.02 — the intersection silently changed
which population was being tested. This is the second time an intersection
quietly destroyed a test in one day (the first: TONUSDT cutting 45,575 bars to
4,577). `xs_mcpt.py` now raises on an empty index and takes `--min-bars`.

## THE PROFIT-CAP ERROR (2026-09-12) — invalidates six earlier files

Every strategy test in this project until now closed winners at a fixed target:
`run_r(df, sig, SL=2.0, TP=3.0)`. A 3×ATR target against a 2×ATR stop caps a
winner at **+1.5R**; one sweep setting, `(2.0, 1.2)`, capped at **+0.6R** — which
needs a 62% win rate merely to break even. `holdout_sweep.py`'s own docstring
said "a win caps at +1.5R". It was documented and its implication missed for
weeks, because everything was graded by mean R and Sharpe — two metrics that
*punish* large wins and therefore hid the damage.

**Files whose verdicts are void or compromised:** `holdout_sweep.py` (the
"SURVIVORS: NONE" result), `mass_search.py`, `vsa.py`, `adaptive_rsi.py`,
`nasdaq_levelfade.py`, `final_oos.py` (the gold kill).
**Files unaffected:** `intramarket.py`, `metalabel.py`, `liq_cascade.py`,
`funding_xs.py`, `mcpt.py`, and all `xs_momentum` work (fixed holding period, no
target).

Capping is only fatal to TREND strategies. For mean-reversion a tight target *is*
the thesis, so those kills stand. `holdout_uncapped.py` confirmed the distinction
with a prediction registered before running:

| | positive CAPPED | positive UNCAPPED | mean improvement |
|---|---|---|---|
| trend families (11) | 3/11 | **11/11** | **+0.274R** |
| mean-reversion (7) | 0/7 | 3/7 | +0.088R |

Trend improved 3× more than mean-reversion, so the cap — not some generic
inflation — is what changed.

### But the recovered edge is BETA, not edge
Long/short split of all 11 uncapped survivors on the 2020-02..2024-03 holdout:

| | long | short |
|---|---|---|
| rsi_trend | +0.605 | −0.018 |
| macd_trend | +0.562 | +0.007 |
| rsi_mom | +0.545 | +0.025 |
| donchian | +0.510 | +0.021 |
| bb_break | +0.503 | +0.036 |
| roc_mom | +0.477 | −0.025 |
| ma_cross | +0.379 | +0.081 |
| macd | +0.375 | −0.025 |

Every long side +0.38…+0.61R; every short side ≈0, **five of eleven negative**. A
real inefficiency would pay something on the weak side. This pays nothing.

Two windows settle it:

| window | long | short | reading |
|---|---|---|---|
| holdout 2020-2024 (greatest bull run) | +0.51 | +0.02 | pure beta, huge numbers |
| virgin coins 2022-2026 (incl. bear) | +0.034 | +0.025 | symmetric, tiny numbers |

**The large numbers exist only where the market rose. The regime-independent edge
is ~+0.03R.** What was recovered is leveraged long crypto trend-following — a
legitimate strategy (every managed-futures fund runs it) that produces large
returns while the asset class rises and bleeds through any extended bear market.
It is not an inefficiency and must not be described as one.

Caveat on the t-statistics: pooling ~14 configs × 9 correlated assets inflates
them badly. `rsi_mom`'s nominal t=+15.32 on n=55,211 represents maybe a few
hundred independent observations; the honest figure is nearer 3–4.

### Rules added
- **Never fix a profit target on a trend/breakout/momentum family.** Test a
  trailing stop, and sweep its width — the result was monotonic in trail width
  across every trend family tested.
- **Always report long-side and short-side mean R separately.** A near-zero short
  side in a rising market means the result is drift. This single column
  reclassified an apparent +174%/yr discovery as beta.
- **Never grade a skewed strategy by Sharpe alone.** Sharpe divides by total
  volatility including upside, so it rejects exactly the payoff shape a
  high-return mandate needs. Report skew, max trade R, and the monthly
  distribution.

## Gate 6: POINT-IN-TIME UNIVERSE (2026-09-12) — the last look-ahead

A universe chosen from today's largest coins is a look-ahead that **survives every
signal-level causality fix**, because it lives in the universe definition rather
than in the indicator. Trend-following is uniquely exposed: a coin joins today's
top nine *because* it trended enormously, which is exactly what the strategy
harvests. Selecting on the outcome you are capturing is close to circular.

`backtest/pit_universe.py` ranks all ~284 coins (alive + 202 delisted) by each
month's realised dollar volume and trades only the **prior** month's top N.

| universe | risk | CAGR | DD | MAR | /month |
|---|---|---|---|---|---|
| FIXED today's top 9 | 0.5% | +259.2% | 78.0% | 3.32 | **+11.24%** |
| FIXED today's top 9 | 1.0% | +700.8% | 95.5% | 7.34 | +18.93% |
| **POINT-IN-TIME top 9** | 0.5% | **+85.4%** | 84.6% | **1.01** | **+5.28%** |
| POINT-IN-TIME top 9 | 1.0% | +148.1% | 98.2% | 1.51 | +7.87% |
| buy-and-hold, same coins | — | ~40% | ~77% | 0.53 | ~2.8% |

**Hindsight premium ≈ 2.1×.** The +11.24%/month headline becomes **+5.28%/month**
once coins are selected only on information available at the time.

Universe churn is the reason: **54 distinct coins** passed through the
point-in-time top nine over 76 months. The 2020-06 top nine was ADA, BCH, BNB,
BTC, EOS, ETH, LINK, LTC, XRP — EOS and BCH have since faded badly, and today's
nine includes SOL and AVAX, which **did not exist** for the first third of the
original backtest.

### There IS a real edge, and the leverage response proves it
With stablecoins left in the ranking, doubling risk made returns *fall*
(+37.1% → +34.9%) — variance drag exceeding the edge, i.e. no edge. Excluded,
doubling risk nearly doubles return (+85.4% → +148.1%). A genuine edge scales with
risk; noise does not. This is a cleaner test for edge-vs-noise than any t-stat.

### Two traps found building this gate
1. **Stablecoins in a volume ranking.** BUSD ranked into the top nine. A trend
   strategy cannot work on an asset pinned to $1 — no trend, and a near-zero ATR
   makes the fee toll (`fee × price / 2×ATR`) enormous. Left in, they silently
   burned scarce slots and cost **more than half the return** (+2.67% → +5.28%
   per month). Ranking by liquidity is not the same as ranking by tradability.
2. **Asymmetric data coverage.** The dead-coin archive reaches back to 2017 while
   the live caches begin 2020-02, so before 2020 the point-in-time universe could
   contain *only* coins that later died — and BTC did not appear at all. The test
   was rigged against itself until the window was clipped to 2020-06+. Any
   point-in-time study must verify both populations are represented in every
   period it scores.

### Rules added
- **Never select a universe from present-day rankings.** Rank point-in-time, from
  a metric known at the time, and include delisted names.
- **Exclude stablecoins from any volume-ranked universe.**
- **Test edge-vs-noise by doubling the risk.** Return that rises with risk is an
  edge; return that falls is variance drag on nothing.
- **Verify data coverage per period** before trusting a rolling-universe result.

## INDICATOR SEARCH IS EXHAUSTED (2026-09-12) — 19 families, one phenomenon

Tested here with uncapped trailing exits: 11 classic families (donchian, bb_break,
rsi_mom, macd, ma_cross, roc_mom, rsi_trend, stoch_rsi_pb, macd_trend, donch_lo,
zscore) and 8 popular TradingView staples never tried before (supertrend, keltner
breakout, TTM squeeze release, parabolic SAR, aroon, ADX/DMI, ichimoku,
chandelier). `backtest/tv_indicators.py`, `backtest/tv_test.py`.

**All 19 show the same signature.** Uncapped, 7/8 of the new families clear the fee
toll (+0.18R to +0.48R against a ~0.096R toll on BTC) — and **0/8 have a short
side**:

| family | best meanR | long | short |
|---|---|---|---|
| keltner_brk | +0.476 | — | — |
| supertrend | +0.326 | — | — |
| chandelier | +0.319 | +0.728 | −0.106 |
| ichimoku | +0.285 | +0.578 | −0.007 |
| aroon | +0.250 | — | — |

Nineteen formulas producing one pattern is one finding, not nineteen: these
indicators all detect the same underlying phenomenon, and on 2020-26 crypto that
phenomenon is **the asset class rising**. A twentieth adds search space, not
information.

### Applying them cross-sectionally does not rescue them
`backtest/tv_crosssec.py` converted each to a continuous score (ATR-normalised so
scores compare across coins) and ranked coins on it, long top-k / short bottom-k —
the one construction that ever produced a symmetric edge here.

| | Sharpe | beta |
|---|---|---|
| best: keltner, hold 48, k=5 | +0.49 | +0.02 |
| positive cells | **6/14 (43%, below chance)** | |
| reference: cross-sectional **plain return** momentum | **+1.09** | −0.01 |

Beta sat at +0.01…+0.07 throughout, so the neutralisation mechanism works
perfectly — the failure is in the scores. Supertrend, Aroon, PSAR and Ichimoku are
**lossy transforms of price**: they discretise, lag and smooth. Ranking on them
ranks a degraded copy of what raw return already carries.

**For cross-sectional ranking, the raw return is the best available score.**
Indicator transforms subtract information rather than adding it.

### Rule added
- **Stop searching indicators.** The differentiator in this project was never the
  indicator, it was portfolio construction. Ranking rather than predicting produced
  the only symmetric, beta-neutral, permutation-validated result (p=0.0033) — and
  it did so on plain returns with no indicator at all. Spend effort on
  construction, costs, universe selection and sizing, all of which moved results by
  2x-9x today, not on the signal library.

## THE VOLATILITY RISK PREMIUM (2026-09-12) — best-validated result in the project

`backtest/volprem.py`. 5.47 years of Deribit DVOL (BTC 30-day implied vol index,
2021-03..2026-09, paged out of the public API) against subsequent 30-day realised
vol. For each day: `earned = DVOL(t) − RV(t → t+30d)`. Causal by construction —
DVOL(t) is known at t and RV is what happens afterwards.

**This is harvesting, not predicting** — the same family as funding carry, which was
the only other thing here that ever worked by mechanism. Option buyers overpay for
insurance; the seller collects a risk premium without forecasting direction.

| filter (trailing 1y IV percentile, causal) | % of time | mean | positive | worst | t (independent windows) |
|---|---|---|---|---|---|
| always sell | 100% | +9.41 | 73.7% | −43.84 | **+4.68** |
| IV > 25th pct | 57% | +12.97 | 83.7% | −40.46 | **+4.92** |
| **IV > 50th pct** | 31% | **+14.53** | **90.0%** | −36.18 | **+4.38** |
| IV > 80th pct | 10% | +16.26 | 93.1% | −30.14 | +2.41 |

Note the t-stats are computed on ~66 INDEPENDENT 30-day windows, not the 1968
overlapping daily observations (which give a meaningless nominal t of +25.6).

### It survived 2022, which is the test that matters
| year | mean | positive |
|---|---|---|
| 2021 | +19.26 | 88.7% |
| **2022** | **+13.20** | **67.4%** (LUNA in May, FTX in November) |
| 2023 | +7.34 | 72.9% |
| 2024 | +8.03 | 75.4% |
| 2025 | +7.12 | 73.4% |
| 2026 unfiltered | +0.74 | 63.4% |
| **2026 with IV > 50th pct** | **+8.59** | **92.3%** |

Positive in all six calendar years. The apparent 2026 collapse was **entirely from
selling cheap vol** — all eight worst periods were January 2026, when IV was 38%
(5-year median 55.5%) and realised came in at 79–82%. That is writing insurance
below cost. The filter removes it and restores 2026 to trend.

### The filter improves the mean AND the tail
Rare and worth noting: mean +9.41 → +16.26 while worst-case improves −43.84 →
−30.14. Most filters buy return with risk; this one buys both, because refusing to
sell cheap insurance removes precisely the episodes where realised blows through
implied.

### WHY IT IS NOT ACTIONABLE AT SMALL SIZE
| | |
|---|---|
| BTC option minimum | 0.1 BTC = **$7,711** notional per leg |
| ETH option minimum | 1 ETH = **$2,522** notional per leg |
| median bid-ask | 5.5% of premium → ~**1.1 vol points**, ~8% of the edge |

A straddle is two legs, so the smallest viable position is ~$5,000 of ETH notional,
needing roughly $600–1,200 initial margin plus an adverse-move buffer: **~$2,000+
in practice.** The edge is real and out of reach below that. Deribit **testnet** is
free and is the right place to run it until capital allows.

### Cross-instrument gate: PASSES (weaker on ETH)
The gate that killed the NASDAQ level-fade and exposed gold. Same window,
2021-07..2026-08:

| asset | filter | n | mean | positive | worst | t (indep) |
|---|---|---|---|---|---|---|
| BTC | always | 1849 | +9.41 | 73.7% | −43.84 | +4.68 |
| BTC | IV>50th | 580 | +14.53 | 90.0% | −36.18 | +4.38 |
| ETH | always | 1849 | +6.36 | 66.3% | −50.08 | +2.51 |
| ETH | IV>50th | 836 | +9.86 | 73.0% | −34.45 | +2.91 |

The filter improves mean AND tail on **both** instruments — independent
confirmation of the mechanism. But ETH pays ~two-thirds of BTC's premium at t=+2.91
vs +4.38, so this is not uniform across crypto: BTC's option market is deepest and
pays best. Unfortunate, since BTC is the $7,711 leg and ETH the $2,522 one.

### Realised-vol estimator: the premium survives, ~30% smaller than first measured
Close-to-close daily RV understates true variation for a jumpy asset and therefore
flatters the seller. Quantified rather than left as a caveat:

| RV estimator | median RV | IV>50th mean | positive | worst | t |
|---|---|---|---|---|---|
| close-to-close | 45.7% | +14.53 | 90.0% | −36.18 | +4.38 |
| hourly | 48.6% | +12.38 | 88.1% | −20.30 | +4.27 |
| **Parkinson (high-low)** | **50.7%** | **+10.07** | **84.3%** | −31.35 | **+3.27** |
| median implied (DVOL) | 55.0% | | | | |

Parkinson captures intraday range that close-to-close misses and is the
conservative choice. **Quote +10 vol points, not +14.5.** The bias was worth ~30%
of the apparent edge. Implied still exceeds the most conservative realised estimate
by +4.3 points unconditionally and +10.1 filtered.

### Model biases, ALL of which flatter the seller
- variance-swap approximation ignores gamma/path risk, which hurts a real seller
  when the path is jumpy rather than merely wide
- realised vol is close-to-close, understating true variation for a jumpy asset
- no margin/liquidation modelling: a short option can be liquidated before expiry
  even when it would have expired worthless
- worst observed is not worst possible: −43.84 is the worst in 5.5 years, and
  March 2020 (pre-DVOL) was far worse

**Negative skew is the defining risk**: worst −36.18 against a mean +14.53, so one
bad window costs ~2.5 months of gains. This is the mirror image of the trend
strategy's shape (24% win rate, rare huge winners). Sizing must be set by the tail,
never by the mean.

## PYRAMIDING (2026-09-12) — the largest single lever found, and it was a blind spot

`backtest/pyramid.py`. For this entire project the engine took **one unit per
signal** and trailed it out. That was never tested, never questioned, and it was
costing more than every indicator examined combined.

Adding to a winning position — unit 1 on the signal, another each time price
advances 2R from the original entry, up to 5, all sharing one ratcheting trailing
stop — measured **risk-matched** on the point-in-time, survivorship-free universe
(total exposure held at 0.5% in every row):

| units | risk/unit | CAGR | DD | MAR | per month |
|---|---|---|---|---|---|
| 1 | 0.500% | +138.1% | 89.3% | 1.55 | +7.50% |
| 3 | 0.167% | +186.1% | 79.2% | 2.35 | +9.15% |
| **5** | **0.100%** | **+205.4%** | **72.2%** | **2.84** | **+9.75%** |

**Monotonic on all three metrics** — more return AND less drawdown AND better MAR
at identical total risk. Not leverage: the 1-unit control reproduced +138.1%/89.3%
exactly in the same code path.

### Why it works
Additions are funded by open profit, so size grows only after price has confirmed,
while the 87% of trades that fail still lose a single unit. It shifts exposure off
the entry — where almost everything fails — and onto the confirmed part of a move.
Exits cannot reach that asymmetry: a trail decides *when* to leave, a pyramid
decides *how much is on when you are right*.

### The two things that limit it
**Profit concentration is extreme.** Of 3,420 positions, the top 25 (0.7%) produce
**85% of all profit**; the single best is 12%. The strategy waits, bleeds, and
occasionally catches something enormous. Flat months are the normal experience.

**More units need MORE capital, not less.** With 5 units the per-unit risk is
0.1%, so each order is 5x smaller and needs 5x the equity to clear an exchange
minimum. Minimum viable capital, by order floor:

| config | floor $0.21 | floor $1.00 | floor $5.00 |
|---|---|---|---|
| 1 unit @0.50% | $5 | $23 | $116 |
| 5 units @0.10% | $9 | $45 | $223 |

So the better-returning config is the harder one to afford. An earlier claim of
"$9 minimum" for the 5-unit version was **wrong** — it used 0.5% for the order
floor while the config risks 0.1% per unit.

### Rule added
- **Never freeze position construction.** Every large gain in this project came
  from position management — profit cap, position cap, trail width, stop width,
  and now unit count — while 19 indicator families all found the same thing. When
  a result disappoints, check what the engine was never allowed to do before
  looking for a better signal.

## Standing rules

1. Carve the holdout **first**, before any exploration. Never load it twice.
2. Report the grid size next to every p-value — a wider search mines a higher
   noise floor, so a p-value is meaningless without it.
3. When testing N assets, correct for N. Four assets means the bar is 0.0125,
   not 0.05.
4. Any result implying MAR > 2.5 is presumed broken until explained.
5. A negative control belongs in every batch. Mean reversion scored PF 0.890
   against a permuted median of 1.038 — that is what a *correctly detected*
   non-edge looks like, and it is how we know the machinery works.
6. Structural trades (funding carry) are not price predictions, so gates 3–5
   apply differently — but they still need a holdout and a cost audit.

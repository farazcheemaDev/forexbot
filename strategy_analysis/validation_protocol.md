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

## THE PRICE-MIRROR BUG (2026-09-12) — never transform data to reuse an engine

To trade shorts through a long-only pyramid engine I mirrored each price series
around **twice its first close** and traded the mirror as a long. That is valid
only if price never doubles.

    SOLUSDT: first close 2.95 -> mirror base 5.90; max close 286.24
             mirrored price at the high = -280.34
             92% of bars had a NEGATIVE mirrored price

`run_uncapped` charges the fee as `fee * entry_price`, so a negative or wildly
wrong "price" charged a wrong fee. It **flattered shorts ~4x**: +0.117R reported
against a true +0.028R.

**Caught only because two of my own files disagreed on identical trade counts** —
`shortside.py` (native short path, `d = -1`) said +0.0284R on n=7313 while the
mirrored version said +0.117R on the same 7313 trades. After the fix both report
+0.0284R exactly.

`run_uncapped` had handled shorts correctly all along: stop above entry, trail
above the low water mark ratcheting down, `R = (exit-entry)*d/risk`, fee on the
real price. **The wrapper was never needed.**

### Numbers this invalidated (do not cite these)
+11.04%/month at matched drawdown; "shorts improve MAR"; profit concentration of
22.5%/50.2%/70.1%; the 0.16%/0.20% risk rows (+12.92%, +15.14%/month).

### Corrected results
| config | risk/unit | CAGR | DD | per month |
|---|---|---|---|---|
| long only | 0.10% | +205.4% | 72.2% | +9.75% |
| long + short | 0.10% | +173.2% | 65.3% | +8.73% |
| long + short | 0.13% | +240.1% | 74.8% | +10.74% |

Interpolating the two-sided curve to long-only's 72.2% drawdown gives ~+222%/yr,
about **+10.2%/month against +9.75%** — so shorts are worth roughly **half a point
a month**, not the 1.3 points first claimed. They also still rescue the losing
years (2022 −27.7%→−12.0%, 2025 −29.1%→−3.2%), which is worth more than the half
point in a market that stops rising.

### Rules added
- **Never transform the price series to reuse an engine.** Add the direction to the
  engine instead. Any transform that assumes something about price levels (that it
  will not double, not go negative, stay in a range) will break on real data.
- **Run every important measurement two independent ways.** Disagreement between two
  of your own implementations is the cheapest bug detector available, and it is the
  only thing that caught this.
- **Suspect any fee that is not charged on a real, observed price.**

## VSA IS DEAD (2026-09-13) — and a "spent holdout" was not actually spent

`vsa_forward.py` was built on the claim that "the historical crypto holdout has now
been spent on this question, so no further retrospective slicing can settle it" —
committing to a FOUR MONTH wait. That claim was wrong on two counts, and
`backtest/vsa_fast.py` settled the question in twenty minutes.

### Why the holdout was not spent
1. **Every VSA measurement used the profit cap.** `vsa.py`, `vsa_crossasset.py` and
   `vsa_forward.py` all run SL=2.0 / TP=3.0 — a winner force-closed at +1.5R. The
   famous "failed the cross-asset gate, 16/28" was therefore not an exhausted
   sample, it was a CONTAMINATED MEASUREMENT. Re-running the same question with a
   correct exit is new information, not post-hoc slicing.
2. **199 delisted coins were already on disk**, downloaded by `dead_fetch.py`
   AFTER every VSA hypothesis was formed. Nothing about VSA — the dev cut, the
   liquidity split, the bb_break parameters — was chosen with any knowledge of
   those series. That is the epistemic status of forward data, available now.
   238,000 trades across 199 independent assets, against the forward test's
   ~3 trades/cell/day.

The prediction, including the expectation of failure, was registered in the
`vsa_fast.py` docstring before the first run.

### Result: the filter is ANTI-predictive, not merely useless
199 delisted coins, every bb_break signal taken once, dev recorded at entry and
never used to gate (paired design, one pass, so position overlap cannot differ
between cells).

| exit | filter meanR | win% | rest meanR | win% | median per-coin diff | coins improved | sign p |
|---|---|---|---|---|---|---|---|
| capped 3R (old) | -0.066 | 38.5 | -0.035 | 40.0 | -0.035 | 68/171 | 0.0091 |
| trail 3xATR | -0.025 | 32.5 | +0.055 | 33.6 | -0.051 | 73/174 | 0.040 |
| trail 5xATR | -0.080 | 26.5 | +0.079 | 28.0 | -0.108 | 57/160 | 0.00034 |
| trail 10xATR | -0.126 | 18.2 | +0.238 | 19.6 | -0.230 | 45/139 | 3.9e-05 |
| trail 20xATR | -0.234 | 11.9 | (outlier) | 13.1 | -0.362 | 22/96 | 9.4e-08 |

Fewer than half the coins improved under EVERY exit rule, significant at p<0.001
at the trails actually traded. Three confirmations:

* **The liquidity hypothesis is backwards on virgin data.** HIGH-liquidity half
  24/77 coins improved (p=0.0013); LOW half 33/83 (p=0.078). The story that
  justified the forward test's entire HIGH/LOW design fails in the opposite
  direction.
* **Wider trails make it worse** (-0.035R -> -0.362R). If the cap had been hiding
  an edge, uncapping would reveal one. It reveals the opposite.
* **On the 20 forward-test coins it is a coin flip** — 8-11 of 20 in every row,
  sign p 0.48-1.0. The one mildly positive cell in the whole output (+0.041R,
  t_pool +2.02, 11/20) is the CAPPED exit on the NON-VIRGIN coins. That is exactly
  what the original finding was.

### Why the original p=0.0099 was an artifact
It pooled trades. Pooling treats 40,000 trades as 40,000 independent draws, but
crypto coins move together, so one good market stretch inflates a pooled t
enormously. On the live coins the pooled t is +2.02 while the across-coin t is
+1.32 and the coin count is 11/20.

### Mean R is unreadable on delisted microcaps
At a 20xATR trail the rest cell shows mean R +13.177. A dead microcap that rose
1000x before delisting posts an R in the thousands, because R's denominator is the
ATR from when it was worth a fraction of a cent — one trade moves a mean over
37,865 trades by whole R. The returns are real; the MEAN measures which cell caught
the lottery ticket. Hence the sign test as headline: a coin counts once whether its
best trade made 1R or 5000R.

A matching diagnostic: shifting dev one bar (i-1 -> i-2, what the live bot sees)
FLIPS the pooled diff from -0.080/+0.079 to +0.230/+0.060, while the coin counts
stay below half in both (57/160, 65/154). The fragile statistic reverses, the robust
one holds. That gap is how you tell which to trust.

### Rules added
- **A "spent holdout" is not spent if the measurement itself was broken.**
  Re-measuring a contaminated result is new information. Check what exit rule,
  fee model and universe a killed verdict used before accepting the kill.
- **Before committing to a forward test, look for a dataset that postdates the
  hypothesis.** Delisted assets, a newly added venue, a different asset class:
  any data downloaded after the idea was formed is virgin, and it is available
  today. A months-long wait is only justified when no such data exists.
- **The unit of independence in crypto is the COIN, not the trade.** Report a
  pooled statistic and an across-coin statistic side by side in every filter test.
  When they disagree, the pooled one is measuring market direction.
- **On heavy-tailed data, count assets instead of averaging returns.** A sign test
  across assets is immune to single-trade outliers. Add median-per-asset alongside
  every mean.
- **Shift the indicator one bar as a robustness check.** A real effect does not
  reverse sign; a statistic that does was never measuring the indicator.

## THE CAPITAL FLOOR IS A STRATEGY CONSTRAINT (2026-09-13)

Measured in `backtest/venue_floor.py`, `backtest/small_book.py`,
`backtest/cheap_wide.py`. This closes the "can it run on small capital" question.

### The floor, and why it is an absorbing barrier
    floor = min_order_notional x stop_fraction / risk_fraction / (1 - maxDD)

Divided by (1 - maxDD) because an account below the venue's minimum order cannot
place a trade, and recovery comes from trades. It is a one-way door, not an
inconvenience.

Three wrong answers were given before this was measured properly - $9, then
$116/$35 - each computed off the CHEAPEST coin in the book instead of the binding
one, and each too low. A portfolio's floor is set by its most EXPENSIVE contract,
because the book needs every coin in it. ETH's 0.01 step is ~$25 of notional and
that single fact sets the 9-coin book's floor at ~$1,140.

### The finding that generalises
**Chasing return with risk RAISES the capital floor rather than lowering it.**
Doubling risk per unit roughly doubles CAGR but more than doubles drawdown, and the
(1 - maxDD) term then explodes: at 94% drawdown the padding required is 16x what it
is at 0%. So "just use more risk to hit the target on less money" is arithmetically
backwards.

26 combinations of book size (6-20 coins), slot cap (8-20) and risk
(0.13-0.30%/unit) were swept on the 20 most liquid MEXC contracts with a minimum
order under $2.50 (so ETH and BTC excluded by construction):

| config | capital | honest /month | maxDD |
|---|---|---|---|
| 9 major coins, 0.13%/unit (validated) | $1,140 | +10.73% | 67.5% |
| 12 cheap coins, 0.30%/unit | $438 | +12.18% | 94.3% |
| 20 cheap coins, 0.13%/unit | $272 | +6.30% | 78.0% |
| 12 cheap coins, 0.13%/unit | $184 | +5.81% | 68.7% |

**EVERY cell clearing +10%/month had maxDD 94-99%. No exceptions in 26 cells.**
Nothing under $438 cleared it at any risk level.

### Cheap contracts are genuinely worse per unit of risk
Median stop distance is 2.5-3.8% of price on the cheap book against 1.2-2.2% on
majors. Wider stops mean noisier breakouts, so more risk is needed for the same
return, and risk compounds into drawdown. At k=4 the cheap book earned 47pp less
CAGR than the major book. This is a real penalty, not a data artifact.

### The slot cap was binding and raising it does not help
At 12 coins with the inherited 8 slots, more trades were DECLINED (5,394) than
taken (2,782). Raising slots to 12 lifted raw return but pushed maxDD 68.7% ->
81.2%, so the floor rose from $184 to $305 - worse on the only axis that matters.
Breadth beyond roughly SLOTS+1 buys drawdown, not return.

### Rules added
- **A portfolio's capital floor is set by its most expensive contract**, never its
  average or cheapest. Compute it per coin and take the max.
- **Quote the floor at the BOTTOM of the measured drawdown**, not at starting
  equity. A configuration that cannot trade at its trough has a return of zero.
- **Never propose higher risk as a route to a lower capital requirement.** Check
  the (1 - maxDD) term before suggesting it; it usually reverses the conclusion.
- **Report the minimum-order source and date.** Exchange metadata is a claim to
  verify with one real demo order, and step sizes are priced in the coin, so an
  ETH-priced step moves with ETH.

## DRAWDOWN CONTROL (2026-09-13) — a breakeven stop is not a profit cap

`backtest/ddcontrol.py`. Prompted by the LIVE bot, not a backtest: three demo shorts
were open at +0.70R to +2.13R and all three had stops still on the losing side of
entry. A 5xATR trail gives back 2.5R and a 20xATR trail gives back 10R, so nothing
is protected until a trade is deep in profit. That gap is where drawdown lives and
it had never been tested against.

### The result
12 cheap contracts, 8 slots, breakeven threshold swept 1R-6R at two risk levels:

| risk | control | honest /month | maxDD | floor |
|---|---|---|---|---|
| 0.30 | none | +12.17% | 95.2% | $520 |
| 0.30 | breakeven @3R | **+13.93%** | **87.6%** | **$200** |
| 0.13 | none | +5.81% | 71.0% | $197 |
| 0.13 | breakeven @3R | +6.38% | 58.8% | $139 |

Capital requirement down 61%, return UP. The drawdown was waste, not risk premium.

### Why it does not repeat the profit-cap error
A profit TARGET caps the ceiling and deletes the rare enormous winners the strategy
lives on. A breakeven STOP raises the floor and leaves the ceiling open - the trail
still runs to 20xATR. Opposite mechanism. This distinction is worth holding onto: it
is the difference between the worst error in this project and one of the better
findings.

### Why the result is believed
Swept 1R-6R at 0.13 and 0.30: **12 of 12 cells reduced maxDD**, and BOTH risk levels
peak at 3R on a smooth curve with 2R and 4R also beating baseline. A smooth
single-peaked response at the same location under two different risk settings is
evidence. Compare the FIRST pass of this same test, which showed a spike at 3R with
4R markedly worse - that was the signature of the bug below, not of an edge.

### Two bugs found in this file, both of which flattered the result
1. **Look-ahead in the drawdown throttle.** Trades were walked in ENTRY order and
   each R compounded on arrival, then that running equity decided whether to
   throttle. With 8 concurrent slots the throttle was sized using the OUTCOME of
   positions that had entered earlier and not yet exited. It inflated the throttle's
   return by ~5%/month (+12.97% -> +7.82%) and reported a $90 floor where the causal
   version gives $102. Fix: hold trades pending until their EXIT time and let the
   throttle see realized equity only - which is what a live bot sees, because
   unrealized P&L on an open position is not equity you can size from.
2. **Two different rules compared as one.** Longs got trail-plus-breakeven-floor;
   shorts got `run_uncapped(mode="breakeven")`, which SUSPENDS the trail until the
   threshold is met. So variant A mixed a protection change with a holding-period
   change. The tell was the trade count FALLING below baseline as the threshold rose,
   which a pure breakeven floor cannot do. Fixed by adding `be_at` to run_uncapped
   as a mode-independent floor.

### What failed
* **Volatility targeting** - the standard institutional drawdown control, and my
  registered prediction for best of the four. Raised return but raised maxDD more;
  the floor went UP 84-183%. Scaling size up in quiet periods loads the book right
  before volatility expands.
* **Drawdown throttle** (halve risk 25% below peak) - cuts maxDD to 79.6% but costs
  4.3 points of monthly return, falling below target.
* **Going flat in a drawdown** - destroys the strategy (+0.46%/month). Recoveries
  begin at the bottom; a flat book misses them.

### Rules added
- **A stop that raises the floor is safe; a target that caps the ceiling is not.**
  Never generalise the profit-cap finding into "don't manage exits".
- **Sweep the parameter, don't report the best cell.** A smooth single-peaked
  response at a consistent location across other settings is evidence. A spike whose
  neighbours are much worse is a fitted number or a bug - here it was a bug.
- **Position sizing may only read REALIZED equity.** Any rule that reads the equity
  curve must settle trades at their exit time, or it sizes using outcomes that have
  not happened. Check this in every adaptive-risk rule.
- **One change per variant.** If two sleeves implement "the same" control with
  different engine modes, the variant measures neither.

## WHY A $50 ACCOUNT CANNOT REACH +10%/MONTH (2026-09-13)

`backtest/floor50.py`. Three routes, all attacking the term that sets the floor -
`min_order x stop_fraction` of the single WORST coin in the book.

1. **Breakeven @3R on the 9 majors.** Return +10.72% -> **+11.80%/month**, maxDD
   67.6% -> 66.9%, floor $1,143 -> $1,122. Return improvement is free and worth
   adopting; the drawdown barely moves. Prediction of maxDD 55-62% was WRONG, and
   the reason matters: the alts' 95% drawdown was per-trade waste, which a stop
   rule fixes. The majors' 67% is CORRELATED PORTFOLIO drawdown - all nine falling
   together - and no per-trade exit rule touches it.
2. **Substitute rather than drop the expensive coin.** Rank every liquid MEXC
   contract by min_order x stop_fraction, take the cheapest 9-16. Floors came out
   tiny and **every book drew down 99.6-100%**.
3. **Same search with a hard liquidity floor** ($400k and $1M median $vol/bar).
   Still 91.7-100% maxDD; best honest return across the whole cheap-minimum search
   was +5.38%/month. One cell reached a **$26** floor at +4.61%/month, 96.7% maxDD.

### The structural reason, which is the reusable part
**A contract's minimum order is small because the coin's PRICE is low, and coins
reach a low price by FALLING.** Selecting for a low minimum order therefore selects
for coins in decline - the search kept surfacing ILV, ICX, CVC, GALA, COTI at
$30k-170k of volume per bar against XRP's $6.8M. Low capital requirement and high
return are not two dials to trade off; they are anti-correlated through the coin's
price history. No filter fixes this, because the filter is the problem.

### Final capital answer
| config | honest /month | maxDD | floor |
|---|---|---|---|
| 12 reputable alts, 0.30%/unit, BE@3R | +13.93% | 87.6% | $200 |
| 9 majors, 0.13%/unit, BE@3R | +11.80% | 66.9% | $1,122 |
| anything below $50 | <= +5.38% | 91-100% | - |

$200 is the cheapest config clearing +10%/month, and at 87.6% maxDD it holds ~$25 at
the trough - exactly its own minimum requirement, so it survives by nothing. The
$1,122 major book is the one fit for real funds.

### Rules added
- **A low capital floor and a high drawdown in the same row is near
  self-contradictory.** The floor already divides by (1 - maxDD), so a 97% drawdown
  row is claiming the account can trade on cents. Prefer the LOWEST DRAWDOWN that
  clears the target, not the lowest floor.
- **Never select instruments on a property correlated with price decline.** Minimum
  order size, unit price, and tick size all encode how far a coin has fallen.
- **Engine cross-check:** floor50's chain reproduced the independently validated
  +10.73%/month on the 9-major book to two decimals (+10.72%). Any new engine must
  hit that number before its other outputs are quoted.

## ADAPTIVE-BY-EQUITY: THE PRINCIPLE HOLDS, THE MECHANISM DOES NOT (2026-09-13)

`backtest/bootstrap_tier.py`. Proposal under test: take profit at a fixed target
while the account is small, to climb to a threshold, then switch to the trailing
rule. The reasoning is legitimate - near an absorbing barrier the objective is
P(reach target before ruin), not expected growth, and capping the right tail cuts
variance hard in a fat-tailed distribution.

### Why it fails: the cap does not lower the edge, it REVERSES it
| exit | mean R | win% |
|---|---|---|
| trailing (validated) | **+0.3049** | 24.8 |
| TP@1R | **-0.0481** | 67.4 |
| TP@2R | **-0.0289** | 51.5 |
| TP@3R | **-0.0212** | 41.5 |

Negative expectancy at every target. No bet-sizing rule makes a losing bet reach a
goal, and the simulation confirms 0.0% P(reach 5x) from every stake. TP@1R wins 67%
of trades while losing money - the highest win rate in the project attached to the
worst expectancy, which is worth remembering the next time a win rate is quoted as
evidence.

### What the simulation DID find: the venue is the cause of small-account ruin
Bitget's $5 minimum order against a 2.43% stop forces $0.12 of risk per trade - 0.61%
of a $20 account, ~5x the validated 0.13%. The venue makes a small account gamble.

Same edge, same exit, only the minimum order changes:

| stake | floor | forced risk | P(5x) | P(ruin) | median end |
|---|---|---|---|---|---|
| $10 | Bitget $5.00 | 1.22% | 24.8% | **74.6%** | $0 |
| $10 | MEXC XRP $1.34 | 0.33% | 12.3% | **32.4%** | $15 |
| $10 | MEXC ADA $0.21 | 0.13% | 5.3% | **0.0%** | $13 |
| $20 | Bitget $5.00 | 0.61% | 25.2% | **56.4%** | $0 |
| $20 | MEXC ADA $0.21 | 0.13% | 5.3% | **0.0%** | $25 |

**The correct tier rule: small capital -> low-minimum VENUE and low-minimum coins at
the INTENDED risk; larger capital -> majors and full breadth.** The adaptation is
where and what you trade, not when you take profit.

### Method notes
* **Block bootstrap, not i.i.d.** Blocks of 20 trades preserve the losing streaks
  that actually kill small accounts; an i.i.d. resample scatters them and flatters
  every variant equally.
* **Position sizing must be `max(min_order, risk_target)`.** A percentage-only
  simulation hides the trap: a shrinking account does not risk a shrinking amount,
  it risks a rising FRACTION. This one line is what surfaced the venue finding.
* **The growth column is pessimistic and the ruin column is the robust output.**
  The sim runs ONE unit with non-overlapping trades, so exposure is ~5-8x below the
  live 5-unit/8-slot config. Quote the ruin ordering, not the median equity.
* **Deflate the edge before quoting survival odds.** The raw R came from a fixed book
  of today's survivors; mean R was cut 3x (subtracting 2/3 of the mean, preserving
  variance and tail shape) before any probability was reported. On the undeflated
  edge $20 showed 66.5% P(reach 5x); deflated it is 25.2%. Reporting the first would
  have been the fourth over-promise on capital in this project.

### Rules added
- **A high win rate is not evidence of an edge.** TP@1R: 67.4% winners, -0.048R.
  Always quote mean R next to any win rate.
- **Never quote a survival probability from an undeflated edge.** Apply the hindsight
  correction to the distribution BEFORE the Monte Carlo, not to the answer after.
- **Check whether the VENUE, not the strategy, is producing the result.** Minimum
  order size silently sets the risk floor for a small account, and no strategy
  parameter can override it.

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

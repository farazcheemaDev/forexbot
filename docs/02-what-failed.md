# The graveyard

Every approach tested and killed. **Read this before proposing anything** — most
new ideas are already in here.

"PF" is profit factor: gross wins ÷ gross losses. Below 1.0 means it lost money.

## Dead: tried to predict reversals

Everything in this group tried to call a turning point. Every single one failed.
That consistency is the most useful thing in this document.

| Approach | Result |
|---|---|
| Mean reversion / fading extremes (Bollinger + RSI, z-score) | PF **0.46–0.85** across forex, gold, crypto |
| Level-fade at round numbers and prior-day highs/lows | PF ~1.0, not robust |
| Liquidity-sweep / stop-hunt reversal (ICT style) | PF **0.53–0.79** |
| VWAP reversion | PF **0.46–0.85** |
| StochRSI, both reversion and pullback framings | no robust edge |
| Pairs / spread trading NASDAQ vs gold & silver | correlation only +0.19, PF **0.12–0.70** |
| Classic indicators on EUR/USD (EMA cross, MACD, RSI, Donchian, Bollinger) | zero robust combinations |

**The pattern:** what worked was either momentum gated by a trend filter, or
structural (a payment mechanism, not a forecast). Everything that tried to
*predict* a reversal failed. Treat any new reversal idea as guilty until proven
otherwise.

## Dead: too expensive to trade

| Approach | The number that killed it |
|---|---|
| Momentum scalping, Nasdaq intraday | **−34% to −56% per month** after spread |
| Crypto 1-minute, 5-minute, 15-minute | fee toll exceeds the edge |
| Market making crypto | BTC spread is **0.01 basis points** — nothing to capture |

**The metric worth remembering:** the fee toll in R units is
`fee × price ÷ (2 × ATR)`. It tells you, before any backtest, whether a timeframe
can pay for itself. Anything above ~0.15R per trade is hopeless.

**Important correction:** "5-minute bars are dead" is true for *crypto*, where
fees are a percentage of notional. It is **false** for gold and Nasdaq futures,
where the spread is fixed: gold's 5-minute toll is 0.044R and Nasdaq's 0.038R,
both *cheaper* than BTC hourly. Those instruments died for a different reason
(the strategies themselves), not cost.

## Dead: capital floor too high

| Approach | Why it's out of reach |
|---|---|
| Options volatility selling (Deribit DVOL) | needs **~$2,000** per contract |
| Gold / forex via Exness MT5 | minimum lot sizes make small capital unusable |

The options one hurts, because it **worked**: implied volatility exceeded
subsequent realised volatility by **+10.07 volatility points** on the
conservative Parkinson estimator, **84.3% hit rate**, t = +3.27, positive in all
six years *including 2022*. It is the cleanest statistical edge found in this
entire project. It is simply not accessible at $50–500.
(`backtest/volprem.py`)

## Dead: sounded good, measured badly

| Approach | Result |
|---|---|
| New-listing momentum | Looked like +0.122R — but **81% of those trades couldn't be taken** with a real position cap. Once capped: every cell negative. |
| Indicator search (8 more TradingView families: supertrend, Keltner, TTM squeeze, PSAR, Aroon, ADX/DMI, Ichimoku, Chandelier) | **19 of 19 families profitable long, 0 of 19 short.** They all detect the same phenomenon. Searching for more indicators is exhausted. |
| Cross-sectional versions of those 19 | 6/14 positive, best Sharpe +0.49 — worse than plain price momentum's **+1.09** |
| Meta-labelling (ML filter on signals) | normalised volume was the #2 feature of 10; still didn't save it |
| **VSA / volume absorption filter** | Looked significant at p = 0.0099 — but that pooled correlated coins and used the capped exit. On 199 virgin delisted coins the filter helps **fewer than half** the coins under every exit rule (57/160 at the trail we trade, p = 0.00034). It is *anti*-predictive. [Full writeup](05-vsa.md) |

The 19-of-19 result is the reason we stopped looking for indicators. When every
indicator family gives the same answer, the indicator is not the variable that
matters. Position management, costs and universe selection moved results by
**2–9×**; indicator choice moved them by almost nothing.

## Alive but too small

| Approach | Result |
|---|---|
| Perpetual funding-rate carry (long spot + short perp) | **DEAD as of 2026-09-14, and the old "+5–8%/year" was wrong for this era.** `backtest/cash_carry.py` run to completion for the first time: funding measured **+0.25bp per 8h** over Nov 2024 – Sep 2026, which is **2.7%/year gross**. Best of 18 cells is +0.5%/yr and negative in one half. Fees (4bp maker per leg) exceed the carry. |
| Cross-sectional market-neutral momentum | Passed a shuffled-market test at **p = 0.0033** (0 of 300 shuffles beat it) and an unseen 500-day holdout (+12.6% vs −7.3% for long-only). But Sharpe 0.62 — genuine and too small. |
| Trend following gold / silver / BTC (Donchian, MACD) | PF 1.05–1.09. The initial "+114%/yr on gold" was gold's 2022–26 bull run, not an edge. |
| Crypto momentum + Kaufman efficiency filter | PF 1.25–1.31 at real Bitget fees, profitable on 6/6 unseen assets. Portfolio correlation tax cut it to +0.03 to +0.087R with 35–59% drawdowns. |

The cross-sectional one is worth keeping alive: market-neutral by construction
(ranking cancels market beta), so it does not need crypto to go up. It's running
as a forward test in `xs_paper.py`.

## Revived from the dead

Six strategies were **wrongly killed** by a measurement bug — a profit target
that capped every winner at +1.5R. When re-tested without it:

- Trend following: 3 of 11 profitable → **11 of 11** (+0.274R average)
- Mean reversion: 0 of 7 → 3 of 7 (+0.088R)

Mean reversion's kill largely still stands. Trend's did not. This is the one
legitimate reason to reopen a graveyard entry: **the measurement itself was
broken, not the strategy.** See [doc 03](03-mistakes.md).

## Interesting non-results worth keeping

- **Kaufman efficiency ratio reverses sign** between directional and
  cross-sectional designs. A filter that helps one hurts the other. Never carry a
  filter across designs without re-testing it.
- **Shorting crypto is not symmetric to longing it.** 19 of 19 indicator
  families found a long edge and none found a short edge — until exits were
  tuned separately per direction, at which point shorts became usable.
- **203 of 735 USDT pairs that ever existed are delisted** — a 30% death rate.
  Any backtest on today's coin list is measuring survivors. Those dead coins are
  also **virgin test data**, because they were downloaded after most hypotheses
  were formed — which is how VSA got settled in twenty minutes instead of four
  months.
- **Pooling trades fakes significance.** Crypto coins move together, so 40,000
  pooled trades are nowhere near 40,000 independent observations. Count coins, not
  trades. This alone explains one of this project's two "statistically significant"
  results.

---

## Forex, metals and indices (2026-09-14) — `backtest/forex.py`

First test ever run outside crypto, on 6.6 years of H1 and 1–4 years of M5/M15 pulled
free from the MT5 terminal (`fx_fetch.py`). **Costs are measured, not assumed** —
`mt5.symbol_info` spreads, plus **swap charged per trade from the bars each trade was
actually open**, because winners run and losers get stopped, so an average would tax
winners too little.

### A. The deployed config on instruments it has never seen

`bb_break(30,1.5)`, 20×ATR trail, BE@3R. After spread **and** swap, split 60/40 in time:

| Instrument | meanR | PF | In-sample → holdout | Verdict |
|---|---|---|---|---|
| **XAGUSDm 1h** | **+0.226** | **1.28** | +0.076 → **+0.458** | **HOLDS** |
| **XAGUSDm 4h** | **+0.195** | **1.26** | +0.008 → **+0.499** | **HOLDS** |
| XAUUSDm 4h | +0.697 | 1.86 | **−0.437** → +3.705 | **ONE REGIME** |
| XAUUSDm 1h | +0.188 | 1.24 | **−0.056** → +0.622 | **ONE REGIME** |
| USDJPYm 4h | +0.480 | 1.64 | +1.329 → **−0.281** | dies OOS |
| USDJPYm 1h | +0.174 | 1.21 | +0.303 → −0.009 | dies OOS |
| EURUSDm 4h | +0.062 | 1.08 | +0.351 → −0.346 | dies OOS |
| EURUSDm 1h | −0.172 | 0.80 | −0.023 → −0.349 | dead both |
| GBPUSDm 1h / 4h | −0.189 / −0.242 | 0.77 / 0.71 | negative | dead / dies OOS |
| **USTECm 1h** | **−0.537** | **0.36** | −0.424 → −0.818 | dead both |
| **US30m 1h** | **−0.493** | **0.41** | −0.481 → −0.515 | dead both |

**Gold's headline is a lie the holdout catches.** +0.697R at PF 1.86 on 4h looks like the
best result in the table. It is **negative in-sample and +3.705 out-of-sample** — the
entire result is the 2024–2026 gold bull market. That is the *same* inflation already
recorded for the first gold test, arriving in a new costume.

**Silver is the only thing that holds**, positive in both halves and stronger in the
holdout. Modest (PF 1.26–1.28) and it carries the most expensive spread here (9.52bp
round trip, 7× gold's), so treat it as a lead, not a result.

**FX majors are dead**, as predicted — most efficient market that exists.

### B. His level fade — settled, on years instead of 60 days

`strategy_analysis/his_strategy.md` §8 named the blocker: *"Free NQ 5m history = only 60
days."* That blocker is gone. Tested on his **primary** instrument (NASDAQ = `USTECm`) and
his **secondary** (gold), at 5m and 15m, 3,649–6,759 trades each:

| Instrument | Best PF across three stop/target profiles |
|---|---|
| USTECm 5m | **0.78** |
| USTECm 15m | **0.84** |
| XAUUSDm 5m | **0.77** |
| XAUUSDm 15m | **0.81** |

**Dead on both of his own instruments, on years of data, at every stop/target setting.**
Not marginal — losing 12–20% of risk per trade over thousands of trades. This closes the
question that §8 left open.

**But his timing intuition was real.** The session window was tested separately, and
**his 13:00–15:00 ET window is the best of the three windows in all four samples**:

| Sample | His window | 09–12 ET | All hours |
|---|---|---|---|
| USTECm 5m | **PF 0.97** | 0.88 | 0.78 |
| USTECm 15m | **PF 0.97** | 0.83 | 0.84 |
| XAUUSDm 5m | **PF 0.81** | 0.86 | 0.77 |
| XAUUSDm 15m | **PF 0.87** | 0.85 | 0.81 |

Consistently least-bad, never above 1.0. **The human's read on *when* was right and the
encoding of *what* is what fails** — which is the honest answer to "was he lucky or good":
the timing was skill, the level logic does not systematize.

### Two predictions of mine that were wrong

1. **"Indices will fail on swap."** They fail on the **signal**. USTECm is PF **0.41 on
   spread alone**; swap only moved it 0.41 → 0.36. Wrong cause attributed.
2. **"Swap is 15–35× the spread."** Based on a two-week hold that does not happen — the
   measured median hold is **0.7–5.3 days**, so swap runs ~1–5× the spread. Real, and it
   took gold 4h from PF 2.25 → 1.86, but not the dominant cost I claimed.

---

## Market-neutral / "does not care about the market" — the category is closed (2026-09-14)

Two fully-designed strategies existed in the repo with **no recorded run**. Both were run
to completion. Both are dead.

**`backtest/funding_xs.py`** — cross-sectional funding dislocation. Rank the universe by
funding, short the crowded longs, long the crowded shorts, equal dollar weight. Market
neutral, no price forecast, funding collected on both legs. **All 18 cells negative:
−20% to −75%/year.** Mean −17 to −48bp per trade against a 12bp cost. Rotating every
8–72h pays fees faster than crowding unwinds.

**`backtest/cash_carry.py`** — the structurally cleaner version: both legs in the **same
coin**, so price cancels by construction rather than by weighting. **Nothing positive in
both halves.** Best cell +0.5%/year at maker fees, negative in the second half.

### The one line that explains it, and closes the category

```
funding: mean +0.25bp/8h, 90th +1.0bp, 99th +3.5bp
basis change per 8h: sd 4.93bp
```

**Funding averaged 0.25 basis points per 8 hours — 2.7%/year gross.** Maker fees are 4bp
per leg round trip. **The service pays less than it costs to provide.** The old graveyard
figure of "+5–8%/year" was measured on an earlier, higher-funding era and does not hold for
Nov 2024 – Sep 2026.

### Why this was always going to be the answer

Returns come from exactly three places:

1. **Bearing risk** — paid for holding what others won't. This is the trend book, and it is
   **regime-dependent by definition**, because the regime *is* the risk.
2. **Providing a service** — liquidity, leverage, settlement. The fee is set by
   competition, and competition drives it toward the cost of capital. **Measured here:
   2.7%/year.**
3. **Information nobody else has** — unavailable at retail.

**Asking for category-1 returns with category-2 risk is arithmetically unavailable.** If a
market-neutral book paid 10%/month, every fund on earth would lever it until the rate
collapsed. **That funding pays 2.7% is the proof it is genuinely low-risk.**

> **Regime dependence is not a defect of the strategy. It is the receipt for the return.**
> A book that earned in 2021 and 2024 and not 2025 is being paid to bear crypto trend
> risk. Remove the regime dependence and you remove the payment.

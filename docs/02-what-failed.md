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
| Perpetual funding-rate carry (long spot + short perp) | **+5–8%/year**, positive in 80–85% of all 8-hour periods over 3 years. Structurally real, just modest. |
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

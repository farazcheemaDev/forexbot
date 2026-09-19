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
| Gold / forex via Exness MT5 | minimum lot sizes make small capital unusable |

### Options vol selling: the floor claim was WRONG, and it died anyway (2026-09-18)

This entry used to read *"Deribit DVOL needs ~$2,000 per contract"* and cited
+10.07 vol points at an 84.3% hit rate, t = +3.27. **Both halves were wrong.**

**The floor was a Deribit-only number.** Verified live from the exchange APIs:

| venue / underlying | min notional | 24h option volume | ATM spread |
|---|---|---|---|
| Deribit BTC (0.1 BTC) | $7,643 | - | - |
| Deribit ETH (1 ETH) | $2,446 | - | - |
| Binance BTC (0.01) | **$764** | $7.7M | 0.5-1.4% |
| Binance ETH (0.01) | **$24.46** | $2.5M | 0.2-1.1% |
| Binance SOL/DOGE/XRP/BNB | $1.50-9 | $6k-12k | too thin |
| Binance XAU (gold) | $43 | $4.4k | too thin |

Spreads are **0.2-1.4% of premium**, not the 2-5% `volprem.py` assumed. The
capital constraint that closed this category simply does not exist.

**The cited edge was stale too.** Re-running `volprem.py` on data through
2026-08 gives +9.48 vol points at **73.6%** positive, honest t = +4.68 - not
84.3% and +3.27.

**It dies for a better reason** (`backtest/volprem_eth.py`):

| | mean | pos% | worst window | one bad window costs | honest t |
|---|---|---|---|---|---|
| BTC | +8.61 | 72.3% | -45.24 | 5.3 average windows | **+4.56** |
| **ETH** | **+4.51** | 64.4% | **-111.60** | **24.7 average windows** | **+1.96** |

**The only instrument small capital can size is ETH, and ETH does not carry the
premium** - half the mean, 2.5x the tail, not significant. The registered
prediction was that ETH would be *better* than BTC because its realised vol is
higher. It is far worse.

**And the premium is gone this year, on both:**

| year | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| BTC | +18.02 | +12.17 | +6.61 | +7.18 | +6.45 | **+0.00** |
| ETH | +11.56 | +8.96 | +5.33 | +3.35 | **-2.55** | +0.44 |

A monotone decline to exactly zero. The worst BTC windows in all 5.5 years are
every one of them **January 2026**.

**The one conditional test failed.** "Sell only when IV is already high" - the
standard result in the literature - came in at p = 0.083 in-sample and
**p = 0.289 on the holdout**. ETH DVOL today (50.6) sits below the 72.7
threshold anyway, so the filter would not even fire.

**For the record, BTC at its floor is the one configuration worth writing down:**
0.01 contracts = $764 notional on $221 of capital = 3.46x, and there is no
smaller size. +6.51%/month on the 5.5-year average, +4.80% on 2025,
**-0.31% on 2026 YTD**, worst 30-day window **-35.9% of capital**. Not a petty
return - a *non-current* one. Revisit only if the premium comes back, which is
one number checked daily.
(`backtest/volprem.py`, `backtest/volprem_eth.py`)

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

## Dead: correlation-clustered slot allocation (2026-09-18) — `backtest/corr_alloc.py`

The claim was that the gap between **+0.13R per trade** and **+0.03R per portfolio**
is the allocator's waste, not the market's, because `blend.run()` fills slots
first-come-first-served with no idea what is already held. Cap slots *per
correlation cluster* and 12 slots should buy 12 bets instead of 1.6.

**The premise is true.** Measured on 57,594 hourly bars across the 12-coin book:
mean pairwise correlation **0.63**, which is **1.51 effective independent bets out
of 12**.

**The fix does not work.** Clusters refit monthly on the trailing 90 days, strictly
point-in-time, k and the per-cluster cap swept, tuned on the first 60% and decided
on the last 40%:

| holdout variant | mean R | /month | maxDD | R/DD |
|---|---|---|---|---|
| baseline, global cap 12 | +1.224 | **+14.60%** | 78.4% | 1.561 |
| control, global cap 8 | +1.743 | +13.44% | **69.0%** | **2.525** |
| CORR k=4, max 3 per cluster | +1.012 | +7.87% | 73.5% | 1.378 |
| random k=4, max 3 per cluster | +0.635 | +3.34% | 73.2% | 0.867 |

Correlation clustering **halves the return** and does not even reduce drawdown as
much as simply lowering the slot cap. On the tune window it beat its own
random-cluster control in **2 of 8 cells against a coin-flip expectation of 4**.

**The registered prediction was right for the right reason.** Twelve series that
all correlate 0.51-0.76 do not have stable clusters; each monthly refit produces a
different arbitrary grouping. There is nothing for a clustering engine to find.

> **The correlation tax is the market's, not the allocator's.** No slot rule
> reclaims it, because the redundancy is in the assets rather than in the choice of
> which ones to hold.

### The byproduct, which matters more than the test

The de-leveraging control - plain **global cap 8** - dominates the deployed cap of
12 on risk-adjusted terms in **both** halves, and `blend.py`'s own existing sweep
says the same thing. `corr_alloc.py` reproduces `blend.py`'s drawdowns to the
decimal (87.0% / 78.4% / 69.0%), which is an independent cross-check of both.

From `blend.py`, out of sample, with the MEXC minimum-order table:

| sleeves | slots | /month | maxDD | **capital floor** |
|---|---|---|---|---|
| 1h + 4h | 8 | +11.96% | 69.0% | **$167** |
| 1h + 4h | 12 | +13.62% | 78.4% | $240 |
| **1h + 4h + 12h** (deployed) | **8** | +8.32% | 57.0% | **$217** |
| **1h + 4h + 12h** (deployed) | **12** | **+13.17%** | 75.2% | **$377** |

**The deployed configuration's own out-of-sample capital floor is $377, and the
account is $221.** Twelve slots buys +4.85 points of monthly return and raises the
floor by $160 - past the account. That is not a return/risk trade-off, it is the
absorbing barrier from doc 00: below the minimum order the account cannot recover
by trading.

Eight slots is the configuration that fits $221. Recorded here rather than shipped,
because changing the live config mid-forward-test resets the trade count to zero -
decide it when the forward test has its ~200 closed trades.

---

## Not dead, not tradable: token unlock cliffs (2026-09-18) — `backtest/unlocks.py`

The only test in this project whose input is not a price. A vesting cliff is a
supply increase at a timestamp published months in advance, so the seller's decision
is a calendar rather than information - the same non-informational mechanism class as
the liquidation-cascade thesis, with weeks of warning instead of milliseconds.

**The data is free.** `defillama-datasets.llama.fi/emissions/{slug}` needs no key.
372 protocols carry schedules; **101 have a token on Binance USDT perps**, giving
18,836 scheduled events, 14,066 of them past cliffs, against 84,058 daily bars.

**The control is the whole test.** Alts fell over this sample, so shorting anything
made money. Every event window is matched against non-event windows **of the same
tokens over the same dates**. With all 20,301 eligible control windows used - no
sampling - shorting T-1 to T+1 on cliffs >= 1% of supply gives:

| | n | mean | excess | p |
|---|---|---|---|---|
| unlock windows | 508 | +1.151% | | |
| all matched non-event windows | 20,301 | +0.153% | **+0.998%** | **0.016** |

That is a stable number, not a sampling artifact: across 40 different random control
draws the excess ran **+1.010% with an sd of 0.200**, never changing sign, p < 0.05
in 26 of 40. *(An earlier reading of mine blamed control resampling for the spread
between 1.258 and 0.662. Wrong - the resampling sd is only 0.2pp and those values sit
inside its range.)*

**It fails for two better reasons.**

**1. It does not scale with the supply shock.** A real cliff effect must grow with
cliff size. It does not:

| threshold | n | excess | p |
|---|---|---|---|
| >= 0.5% of supply | 862 | **+0.001%** | 0.996 |
| >= 1.0% | 508 | +0.998% | 0.016 |
| >= 2.0% | 241 | +1.059% | 0.087 |
| >= 5.0% | 51 | +0.662% | 0.607 |

Exactly zero at 0.5%, peaks in the middle, fades at the largest cliffs. A mechanism
does not behave that way; noise with one lucky band does.

**2. Nothing survives the window grid.** Eight declared entry/exit windows,
Holm-corrected as a family: best corrected **p = 0.114**. The T-1..T+1 and T-5..T+1
cells are uncorrected hits only - which is what 8 tests produce by chance.

Per-token, **27 of 50 tokens had a positive excess against a coin-flip 25**, and both
tails are single-event names (YB +45% on n=1, XPL -55% on n=1).

**Two biases flatter all of the above and cannot be removed here:**
- **Schedule revision.** DefiLlama serves today's schedule. A quietly renegotiated
  cliff is seen at its new date, not the date the market watched.
- **Survivorship.** Binance-listed tokens only. This project already measured a 30%
  death rate among USDT pairs, and dead tokens are exactly the ones whose unlocks
  hurt most.

### The follow-up was run, and it could not settle it (2026-09-18)

`backtest/unlocks_dead.py`. 15 of the 202 delisted pairs in `dead_fetch.py` carry a
DefiLlama schedule, giving **116 usable cliff events across 11 tokens**.

| universe | events | controls | unlock | control | excess | p |
|---|---|---|---|---|---|---|
| LIVE (survivors) | 508 | 20,301 | +1.151% | +0.153% | **+0.998%** | 0.016 |
| **DEAD (delisted)** | **116** | **10,937** | +0.591% | -0.168% | **+0.759%** | **0.402** |
| POOLED | 624 | 31,238 | +1.047% | +0.041% | +1.006% | 0.011 |

**My registered prediction was wrong.** I expected the excess to vanish or invert on
dead coins if it was survivorship. It did neither - same sign, only slightly smaller.

**But the test had no power to decide.** On the dead arm the per-event sd is 11.78%:

```
to detect +0.759% at 80% power, p<0.05  ->  ~3,780 events needed
                                  have  ->       116
smallest effect detectable at n=116     ->     +4.33%
effect under test                       ->     +0.76%   (5.7x too small to see)
```

**The deciding test was underpowered by 33x.** Its p=0.402 is not evidence of
absence; it is the absence of evidence. And only 116 such events exist, so this is a
**hard data ceiling, not a research gap** - no amount of further work raises it.

The POOLED p=0.011 is not a fix either: 81% of its events are the live sample, so
pooling dilutes the test rather than removing the bias.

### What the dead universe DID show, and it is the real result

Size-scaling fails a second time, independently, and worse:

| dead, threshold | events | excess | p |
|---|---|---|---|
| >= 0.25% of supply | 196 | +0.691% | 0.336 |
| >= 0.50% | 123 | +0.647% | 0.472 |
| >= 1.00% | 116 | +0.759% | 0.408 |
| >= 2.00% | 47 | +0.408% | 0.773 |
| **>= 5.00%** | 20 | **-1.665%** | 0.413 |

**On the coins that actually died of supply, the largest cliffs show a NEGATIVE
excess.** Two independent universes, and in both the effect fails the one property a
supply mechanism cannot fail: it must grow with the size of the supply.

Nothing survives Holm on the dead grid either (all corrected p = 1.000), and 6 of 11
tokens were positive against a coin-flip 5.5, with every tail owned by an n=1 name
(OM +6.79% on one event, OMNI -6.94% on one).

> **Verdict: the category is closed by power, not by evidence.** There is a stable
> ~+1% on survivors that cannot be shown to be real and cannot be shown to be
> spurious, and the data needed to tell the difference does not exist. Treat it as
> untradable and stop - an effect you cannot distinguish from survivorship at 33x
> less data than required is not something to risk money on.

---

## Dead: protecting the pyramid (2026-09-20) — `backtest/pyramid_exits.py`

Prompted by the live book: +161.7R open, -139.0R if every position fell back to its
printed stop. The breakeven floor protects only the FIRST unit; a 5-unit position
stopped there loses 0+2+4+6+8 = -20R. Profit targets were ruled out first: the top
1% of 5,503 trades carry 114% of all profit, and capping winners at +6R turns
+14,323R into -4,398R. So three ways to protect gains **without capping them** were
tested on the deployed 1h+4h+12h / 12-slot blend. The rewritten exit engine
reproduces `run_pyramid` exactly on 12 coin/sleeve pairs, and that is asserted.

| variant | tune /mo | DD | floor | holdout /mo | DD | floor |
|---|---|---|---|---|---|---|
| current (first-entry BE) | +29.23% | 75.7% | $385 | +13.17% | 75.2% | $377 |
| scale_out (added units on 5xATR) | +8.77% | 46.7% | $176 | +12.10% | **45.7%** | **$172** |
| avg_be (BE at average entry) | +9.94% | 67.2% | $285 | +8.77% | 49.4% | $185 |
| ratchet (20 -> 10xATR past +10R) | +19.85% | 73.2% | $349 | +15.04% | 71.7% | $331 |

**None pass the declared rule** (better return/drawdown on tune AND holdout, lower
floor). All three improve the holdout and lose the tune window.

**Scale-out's holdout looked almost free, and the yearly split shows why:**

| year | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| current | 299 | 1783 | 2 | 673 | 1423 | 102 | 14 |
| scale_out | 95 | 522 | 61 | 183 | 560 | 187 | 73 |
| difference | -205 | **-1261** | +59 | -490 | -863 | +85 | +59 |

*(summed R x 0.30%, not compounded - comparable across rows, not exact)*

It wins every **weak** year (2022, 2025, 2026) by a little and loses every **trend**
year (2020, 2021, 2023, 2024) by a lot. The holdout starts 2024-08-29, so it is mostly
2025-2026 - the weak regime - and that is what made scale-out look nearly costless. It
is insurance that pays in chop and costs the years the strategy exists for.

Why, in one position: live AVAX at 5 units and +46.8R gets **33.4R of it from units
2-5.** The added units ARE the right tail. Protecting them removes it.

Of 1,081 full pyramids (3+ units) under the current exit, **68% closed at a loss**
and the mean was still **+23.57R**. That is not a defect to fix; it is the shape of
the edge.

> **The -20R-at-breakeven exposure is the price of the +1,804R trade.** Every way of
> protecting it tested here is a way of selling that trade.

Registered predictions: avg_be failing was right; "scale_out cuts drawdown most and
costs most return" was right on the full sample; **"ratchet likeliest to pass" was
wrong** - it is worse in nearly every year.

**It does not fix the capital floor for free.** Scale-out's $172 floor fits the $221
account, but only by shrinking the strategy into a weak-regime one. It belongs in the
same end-of-forward-test decision as 8 slots versus 12, not as a patch.

---

## Dead: human supervision as a signals-only bot (2026-09-20) — `backtest/human_loop.py`

If the bot only alerts and a person places the trade, three things change. All were
simulated on the deployed blend (1h+4h+12h, 12 slots), exits assumed to be resting
stop orders that fire on time - an assumption that favours the human.

| | full /mo | DD | floor | total R | holdout /mo | holdout floor |
|---|---|---|---|---|---|---|
| bot, no delay (deployed) | +23.82% | 75.7% | $385 | +14,323 | **+13.17%** | $377 |
| human, 1h late | +19.64% | 84.4% | $602 | +13,465 | +6.14% | $619 |
| human, 3h late | +16.77% | 81.1% | $495 | +13,886 | +4.07% | $496 |
| human, 8h late | +19.27% | 76.8% | $404 | +14,047 | +2.56% | $340 |
| human, asleep 8h a night | +14.89% | 81.5% | $506 | **+11,559** | +6.11% | $364 |

**Delay does not destroy the signal's edge.** Total R moves only -2% to -3% even at
8 hours, and the ordering of the drawdown column is not monotone (1h late is the
WORST at 84.4%). What delay wrecks is the realised path: the capital floor jumps from
$385 to $602 at one hour late, and every holdout figure collapses. Read that as
path instability, not as a dose-response - `blend.run` compounds by trade order
(mistake #6), so hpm is path-sensitive in a way total R is not.

**Sleep is the honest cost of being a person:** -19% of the raw edge (14,323 -> 11,559
R), holdout return more than halved, floor $385 -> $506. A breakout that is still
firing at wake-up is taken; one that faded is gone.

**Random skipping is far cheaper than predicted** - 30 draws each:

| | median /mo | 5th pct | 95th pct | worst | draws below half the bot |
|---|---|---|---|---|---|
| bot, takes all | +23.82% | | | | |
| skip 10% of signals | +21.45% | +17.02% | +24.28% | +16.44% | 0 of 30 |
| skip 25% of signals | +16.00% | +12.49% | +19.14% | +11.65% | 2 of 30 |

**Registered prediction wrong:** I expected skipping to widen the spread badly,
because 1% of trades carry 114% of profit. It does not - the cost is roughly
proportional. The mechanism is the correlation already measured here: 12 slots hold
~1.5 independent bets, so a skipped signal frees its slot for another coin breaking
out on the same move. **The book's redundancy, which caps the return, also makes it
robust to a distracted operator.**

### What was NOT simulated, because it is already measured

A supervisor taking profit early. Capping winners at +6R turns +14,323R into
-4,398R. That is the one override a person watching a position at +46.8R is most
tempted to make, and it is the only one that is catastrophic.

> **Supervision has no step in this strategy that a human does better.** Every
> channel measured subtracts. The legitimate human roles are the ones a backtest
> cannot express: a kill switch for venue failure (a bot does not know its exchange
> is insolvent), the capital decision ($377 floor against $221), and the go-live gate.

---

## Dead: cheaper fees as a step change (2026-09-20) — `backtest/fee_sweep.py`

The reasoning was: this project's measured breakeven is 6-8.5bp round trip, every test
ran at Bitget's 12bp taker, and Hyperliquid is 3bp maker-maker (verified from its API:
234 perp markets, maker 0.015%/taker 0.045%, zero gas per trade/cancel/modify, up to
40x leverage, no KYC). A 4x fee cut on a strategy priced past its own breakeven should
be transformative.

**It is worth +0.67 points of monthly return.** Deployed config, 12 slots, holdout:

| fee | what it needs | holdout /mo | DD | floor | n | mean R |
|---|---|---|---|---|---|---|
| 12bp | Bitget taker (every test so far) | +13.17% | 75.2% | $377 | 2032 | +1.374 |
| 9bp | Hyperliquid TAKER - venue change only | +13.40% | 74.5% | $367 | 2032 | +1.390 |
| 6bp | one maker, one taker | +13.62% | 73.9% | $358 | 2032 | +1.405 |
| **3bp** | Hyperliquid MAKER both sides | **+13.84%** | 73.2% | $349 | 2032 | +1.421 |
| 2bp | high-volume maker tier | +13.92% | 73.0% | $346 | 2032 | +1.426 |

**The trade count is identical at every fee level** - 2032 - which is the tell. No trade
changes sign; each one just keeps a little more.

### Why the registered prediction (roughly double) was wrong

The 6-8.5bp breakeven belongs to the **short-horizon momentum families**, whose gross
edge is ~+0.05R per trade. **It does not belong to this strategy.** The blend's stop is
2xATR, which on these alts is 8-15% of price, so 12bp is only **~0.02R** - about 2% of
its +1.374R average trade. A trend book with a huge average trade is structurally
fee-insensitive, and conflating the two breakevens was the error.

> **Fee reduction helps strategies whose edge is small per trade. This one's edge is
> 1.4R per trade.**

### And Hyperliquid is WORSE for this book, not better

I claimed a $10 minimum order with 20-40x leverage would stop the capital floor from
binding. That is backwards: the floor is `min_order_NOTIONAL x stop / risk / (1-DD)`,
and leverage does not reduce the notional.

| venue | binding coin | capital floor |
|---|---|---|
| MEXC (min order $0.005-$2.28) | NEAR | **$349** |
| Hyperliquid ($10 min order value) | ENA | **$1,846** |

**5.3x worse.** MEXC's sub-dollar minimums are the reason this book is fundable at all.
For the deployed blend, stay where it is.

### Where the fee win is actually available

`backtest/maker_r.py` already measured it, for the families that DID die on fees:
bb_break goes from **-3.32 sumR/yr at taker to +21.81 at maker** (86.5% fill, with
non-fill and adverse selection both modelled), and rsi_mom and roc_mom the same. That
is a genuine sign flip - but a rough conversion of the best row lands near 2%/month
after the hindsight divisor, not above 10%. Worth measuring properly; not worth
expecting a step change from.

---

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

### The qualification this argument needs (added 2026-09-20)

The "every fund would lever it" argument assumes the strategy SCALES. It only binds on
strategies with capacity. A niche that absorbs $2,000 before its own edge disappears is
invisible to a fund with $200M - the cost of researching and operating it exceeds
anything it can return at that size - so competition never arrives and the rate never
collapses.

**That is not a loophole in the argument, it is the boundary of it.** Every category in
this graveyard was tested at a size where capacity does not bind (crypto perps, majors,
liquid options), so the argument applies to all of them. But it does NOT license the
conclusion "nobody earns 1.5%/day", and it was used that way in this project more than
once. High rates on small capital are exactly where capacity-limited edges live.

Two things stay true regardless:
- **Compounding still ends it.** Any rate is a temporary rate, because the capital grows
  into the capacity limit. 1.5%/day on $500 is credible; 1.5%/day sustained is not, and
  the arithmetic that "breaks the world economy" applies to the GOAL, never to the claim.
- **Capacity-limited does not mean edge.** It means competition is absent, not that a
  profitable trade exists. It has to be measured like anything else.

> **Regime dependence is not a defect of the strategy. It is the receipt for the return.**
> A book that earned in 2021 and 2024 and not 2025 is being paid to bear crypto trend
> risk. Remove the regime dependence and you remove the payment.

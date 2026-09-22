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

## RETRACTED same day: taker-flow continuation (2026-09-20) — `backtest/positioning.py`

The first test in this project whose input is not price, and the first survivor in
weeks. Binance's free positioning archive (`backtest/metrics_fetch.py`): **5,989,482
rows**, 13 symbols, 5-minute resolution, back to 2020-09 for BTC. Four features
declared before looking, three horizons, Holm across all 12, significance computed
**across coins** (never pooled across rows), quintiles ranked on a trailing 90 days
with `closed="left"`.

| family | h | coins | mean spread | coins agreeing | t | p | Holm |
|---|---|---|---|---|---|---|---|
| **taker** | **4** | 11 | **-0.094%** | **10/11** | -5.69 | 0.000 | **0.002** |
| taker | 12 | 11 | -0.058% | 6/11 | -2.26 | 0.047 | 0.423 |
| crowd | 24 | 11 | +0.377% | 9/11 | 2.64 | 0.025 | 0.273 |
| crowd | 12 | 11 | +0.179% | 9/11 | 2.59 | 0.027 | 0.273 |
| size_gap | 24 | 11 | +0.249% | 8/11 | 1.98 | 0.076 | 0.610 |
| oi_div | 24 | 11 | +0.305% | 8/11 | 1.39 | 0.194 | 1.000 |

**Holdout: taker at 4h HOLDS** - spread **-0.142%** (larger than in tune), t = -6.79,
p = 0.000, and again **10 of 11 coins agree**.

### My direction was backwards, and so was my pick

`taker` was declared as an EXHAUSTION feature and negated accordingly, so a negative
spread means the hypothesis is inverted: **aggressive taker BUYING predicts 4-hour
continuation, not exhaustion.** It is short-horizon order-flow momentum.

I also predicted `oi_div` was likeliest because it has a mechanism. It measured
nothing (p=0.194 at best). And I dismissed order flow earlier in the same session as
an institutional fantasy on the grounds that its edge lives in seconds and dies to
12bp of fees. **It survives at a 4-hour horizon with 12bp charged.**

### What it is and is not worth

- The effect **decays with horizon** - -0.094% at 4h, -0.058% at 12h, -0.013% at 24h -
  which is what a real flow effect should do, and it means the usable window is ~4h.
- The magnitude is **small**: 0.14% net per 4h on a top-minus-bottom quintile SPREAD,
  so ~0.07% per leg. It is a cross-sectional long/short, which is also why it is
  interesting - the market factor cancels, and correlation is this book's ceiling.
- **It does NOT gate the deployed blend.** As an entry filter on the 1h sleeve,
  taker's pooled gap looks large (+0.891R) but only **6 of 11 coins agree** - a coin
  flip. The pooled number is the trap; the agreement column is the test.

### The secondary lead

`crowd` (share of all accounts long, tested contrarian) shows **+0.377% at 24h with
9 of 11 coins agreeing** and fails Holm at 0.273. Under this project's rules that is
discarded - but it has a longer horizon and a bigger effect than the survivor, and it
deserves one dedicated test with its own registered prediction rather than a slot in a
12-test family.

### RETRACTION (2026-09-20, hours later) — `backtest/taker_ls.py`

It became a portfolio and died **gross of all fees**, in two independent
constructions:

| construction | turnover/period | gross/period tune | gross/period holdout |
|---|---|---|---|
| cross-sectional L/S, k=3 | 1.31 | **-0.0009%** | -0.0009% |
| time-series, directional | 1.55 | **-0.0182%** | -0.0013% |
| time-series, market-neutral | 1.09 | **-0.0162%** | -0.0094% |

At zero fees. Every row negative. The fee ladder is then irrelevant - 12bp takes it
to -80%/yr and 3bp to -40%/yr, but there was nothing to charge fees against.

**So the quintile spread was not an edge, it was a statistic that does not
translate.** The likeliest reason is the one thing the across-coin t-test cannot fix:
`positioning.py` measured on an HOURLY grid with 4-hour forward returns, so every
observation overlapped the next three. Quintile membership persists across consecutive
hours, which means far fewer independent episodes than the row count implies. Testing
across coins corrects the standard error for correlation BETWEEN coins; it does
nothing about overlap WITHIN a coin's own series. Re-sampled to a non-overlapping
4-hour grid, the effect is gone.

**The "10 of 11 coins agreeing" figure survived both a Holm correction and a holdout
and was still not tradable.** That is the third time in this project a result passed
correction and a holdout and was wrong anyway (see §19 in his_strategy.md, and
mistake #9). Consistency across coins is not the same as consistency across
independent time.

### What IS worth keeping from this

**The capital floor of a book with no stop.** Every floor in this project came from
`min_order x stop_fraction / risk`, where an 8-15% stop against 0.30% risk is a ~40x
amplifier. A position-sized book has no stop in that formula, so its floor is just the
minimum orders of its open positions:

| book | floor |
|---|---|
| the deployed blend (stop-sized) | **$377** |
| a 6-position no-stop book (MEXC minimums) | **$8** |

**That is a 47x difference, and it is structural rather than about this signal.** It is
the first real answer to "what can $10-20 trade": not a stop-and-target strategy -
those are priced out by construction - but a position-sized one. Any future search for
a micro-capital strategy should start from that constraint rather than discover it at
the end.

The 5,989,482-row positioning archive is also now cached locally and reusable, and the
`crowd` lead (+0.377% at 24h, 9 of 11 coins) has never been tested as a portfolio -
though after today the prior on a quintile spread translating should be low.

### What has to happen before this is a strategy

A cross-sectional long/short backtest on the taker feature: real slot caps, real
fees, per-coin minimum order sizes, and a capital floor. A quintile spread is not a
trade. Until that runs, this is a measured effect, not an edge.

---

## Dead: crowd positioning as a book (2026-09-20) — `backtest/crowd_ls.py`

The second and last lead from the positioning archive, tested as a PORTFOLIO first
this time rather than as a quintile spread - the lesson from the taker retraction.
Contrarian on `count_long_short_ratio`, each coin against its own trailing 90 days,
non-overlapping grids.

**Gross, before any cost:**

| hold | mode | turnover | gross/period tune | gross/period holdout |
|---|---|---|---|---|
| 12h | directional | 0.56 | **+0.1492%** | **+0.0280%** |
| 12h | market-neutral | 0.40 | +0.0214% | **-0.0120%** |
| 24h | directional | 0.74 | +0.2921% | **-0.0174%** |
| 24h | market-neutral | 0.51 | +0.0157% | **-0.0512%** |

One configuration - 12h directional - is positive gross in both halves. It dies anyway:

| fee | tune CAGR | holdout CAGR | holdout Sharpe |
|---|---|---|---|
| 0bp | +88.8% (DD 35.2%, Sharpe 1.73) | **-4.8%** | 0.29 |
| 3bp | +80.7% | -10.1% | 0.20 |
| **12bp** | +58.6% | **-24.2%** | **-0.06** |

**And the mode column is the whole story.** "Directional" allows net market exposure;
"market-neutral" removes it. The neutral version measures **+0.0214% then -0.0120%** -
nothing. So the tune window's +88.8% CAGR at Sharpe 1.73 is **beta, not alpha**: it is
a long-biased book in a rising market, and it does not survive either the holdout or
the removal of market exposure.

Note also that gross +0.0280%/period produced a **-4.8% CAGR** in the holdout. The
arithmetic mean of period returns is positive while the compounded result is negative -
volatility drag. Mean per-period return is not a return.

**Both leads from the positioning archive are now closed**, and the archive's headline
result was an artifact of overlapping windows. The data itself (5,989,482 rows) stays
cached and free; what it does not contain is an edge we can find.

### The one thing carried forward from this whole line

A book with **no stop** has a capital floor of **$6-8** for 4-8 positions, against the
deployed blend's **$377**, because `min_order x stop_fraction / risk` is a ~40x
amplifier that a position-sized book never enters. That is structural, signal-
independent, and the correct starting constraint for any future micro-capital search.

---

## Settled: 0.30% risk is correctly sized, and the $377 "floor" is not a survival line (2026-09-20) — `backtest/ruin.py`

Every capital floor in this project came from MAX DRAWDOWN padded by 1/(1-DD). That is
one historical worst case, not a probability. This computes the actual thing: block
bootstrap (blocks of 25, so losing streaks survive resampling) of the strategy's own
realised trade Rs, 20,000 paths per cell, against the real absorbing barriers - each
coin needs `min_order x stop / risk` of equity before it can be sized, and those lines
differ 500x across the book, so a falling account loses coins one at a time rather than
dying.

**On the REAL point-in-time trade distribution** (7,281 trades from the
survivorship-free universe, delisted coins included, mean **+1.602R**, sd 57.37),
starting from $221, after 600 trades (~2.5 months at the live rate):

| risk/unit | median equity | 5th pct | P(crippled: <6 coins) | P(halved) | P(2x+) |
|---|---|---|---|---|---|
| 0.10% | $343 | $152 | 0.0% | 0.1% | 37.3% |
| 0.20% | $458 | $105 | 0.0% | 6.1% | 51.0% |
| **0.30% (deployed)** | **$526** | $68 | **0.0%** | 13.0% | 54.2% |
| 0.50% | **$572** | $28 | 0.8% | 22.1% | 54.4% |
| 0.75% | $483 | $9 | 6.3% | 30.6% | 51.1% |
| 1.00% | $302 | $2 | 16.7% | 39.2% | 46.1% |

**Growth-optimal is 0.50%; the deployed 0.30% captures 92% of it at a third of the
cripple risk.** The deployed size is right. 1.00% is visibly past the optimum - median
equity FALLS from $572 to $302 as risk doubles, which is the signature of over-betting.

### A false alarm of mine, and what caused it

A first pass used a SYNTHETIC haircut - every R shifted down until the mean was one
third of the fixed-book mean - to stand in for the point-in-time edge. It reported
**P(crippled) = 43.1%** at the deployed 0.30% and a median outcome of $221 -> $78, i.e.
that the live bot was mis-sized by 6x. **That was an artifact of the haircut.**

The 3.0x hindsight premium measured in `pit_universe.py` is on COMPOUNDED ANNUAL
RETURN, not on mean R per trade. The real PIT mean is **+1.602R against the fixed
book's +2.603R - a 1.6x haircut, not 3x** - and the PIT universe also has a FATTER
right tail (best trade +4,437R against +1,804R), because it contains coins that mooned
while they were eligible. Shifting a distribution down by a constant destroys that.

The process worked - the result was flagged as method-dependent and verified before
anything was changed - but the lesson is specific: **do not convert a return-level
correction into a trade-level one by subtraction.** Use the real distribution.

### The correction that matters more

I have repeatedly described the deployed config as needing **$377** against $221 of
capital, and called that a live defect. It is not a survival threshold.

`floor = min_order x stop / risk / (1 - DD)` asks: *after the worst historical
drawdown, can I still fund the DEAREST coin in the book?* At 0.30% risk the line where
half the book becomes unfundable is **$18** - the account would have to fall 92% to get
there, and P is 0.0% over 600 trades.

> **$377 is a comfort level, not a floor.** At $221 a deep drawdown costs access to the
> one or two most expensive coins (NEAR, ENA), not the book. So 8 slots versus 12 is a
> RETURN question, not a survival question, and the earlier framing of it as a defect
> was wrong.

---

## Dead: buying diversification with risk on a $5 account (2026-09-20) — `backtest/ruin.py`

Raising risk lowers every funding line, because required equity is
`min_order x stop / risk`. So a $5 account CAN fund more coins by betting bigger. The
question is what that costs. PIT distribution, 600 trades, starting from $5:

| risk/unit | coins fundable | worst historical trade | median equity | 5th pct | P(crippled) | P(<$1) |
|---|---|---|---|---|---|---|
| 0.30% | 3 of 12 | -11% | $11.72 | $1.54 | 100.0% | 1.1% |
| **0.50%** | 4 of 12 | -19% | **$12.81** | $0.63 | 99.9% | 9.5% |
| 1.00% | 5 of 12 | -38% | $7.22 | $0.05 | 99.3% | 28.9% |
| 2.00% | 8 of 12 | -75% | $0.22 | $0.00 | 94.2% | 59.9% |
| 3.00% | 10 of 12 | **-113%** | $0.00 | $0.00 | 97.0% | 81.3% |
| 5.00% | 11 of 12 | -188% | $0.00 | $0.00 | 100.0% | 99.7% |

**The median peaks at 0.50% and collapses.** By 2% it is $0.22; by 3% the worst single
historical position (-37.7R) exceeds the whole account, and 1 trade in 7,280 is worse
than -100% (1 in 161 at 5% risk). **No risk level leaves the account un-crippled** -
P(crippled) never falls below 94%.

> **You cannot buy diversification with risk.** Betting bigger to fund more coins adds
> variance faster than it adds independent bets.

That is the third independent confirmation of the rule already in doc 00 - *"chasing
return with risk RAISES the capital floor rather than lowering it"* - arriving this time
from the ruin side rather than the drawdown side.

**The one legitimate use of $5:** not a trading account, an INSTRUMENT. Real money on a
real venue is the only way to verify fills, fees and slippage against what the backtest
assumes. The demo order-path test cannot do that. $5 is a good instrumentation cost and
a terrible investment.

---

## REOPENED: silver is fundable at $25, not $15,869 (2026-09-20)

`backtest/forex.py` found exactly one instrument outside crypto that survives: **silver**,
positive in BOTH halves and stronger out of sample (meanR +0.226, PF 1.28 on 1h;
+0.195, PF 1.26 on 4h; in-sample +0.076 -> holdout +0.458). It was parked because
"minimum lot sizes make small capital unusable" - Exness's 0.01 lot is 50 oz, which is
$47.61 of risk on a 2xATR stop.

**That was a broker artifact, not a market constraint.** Verified live from the Binance
futures API on 2026-09-20:

| venue | minimum | equity needed at 0.30% risk/unit |
|---|---|---|
| Exness (0.01 lot = 50 oz) | 50 oz | **$15,869** |
| **Binance XAGUSDT perp** | **$5 notional**, step 0.001 | **$25.22** |

**629x.** And it is liquid: **$145M of 24h quote volume, 73,130 trades**. Gold
(XAUUSDT, $258M/day) and tokenised gold (XAUTUSDT) list too.

Funding, from 500 periods of history: **XAGUSDT +0.322bp/8h mean (+3.5%/yr paid by
longs), median 0.000bp** with occasional spikes to +3.99bp. XAUUSDT +0.247bp/8h. A real
but modest cost, and income on the short side.

**This is the second time the identical error appeared today.** The options premium was
filed under "needs ~$2,000 per contract" on a Deribit figure when Binance's minimum was
$24.46. Silver was filed under "minimum lot sizes make small capital unusable" on an
Exness figure when Binance's minimum was $5 of notional. **A capital floor quoted from
ONE venue is not a capital floor.** Both entries were wrong in the same direction, and
in both cases nobody had checked a second venue.

### Why this matters more than the floor

The crypto blend's weakness is measured: most of its lifetime profit is 2021 and 2024,
with 2025 and 2026 earning a small fraction. **Metals trended in 2025-2026 precisely
when crypto did not.** A validated trend strategy on a different asset class is the
textbook second stream - and a second uncorrelated stream is the only thing in finance
that cuts drawdown without cutting return.

### What has to be tested before believing it

1. **Re-cost it on Binance.** forex.py charged MT5 spread (9.52bp round trip) plus swap.
   Binance perp is ~10bp round trip taker, ~4bp maker, plus 3.5%/yr funding on longs.
   Similar, but it must be measured rather than assumed.
2. **Measure the correlation** of the silver sleeve's monthly returns against the blend's.
   That is the entire point, and it must be computed on CALENDAR months.
3. **Regime risk.** Silver passes the test gold failed - positive in both halves, not
   just the recent one. But its holdout half is 6x stronger than its in-sample half, and
   that holdout coincides with the metals bull market. It is one instrument, on one
   signal family, in one regime that has been kind.

The XAGUSDT perp itself only onboarded 2026-01-07, so the backtest must use the 6.6
years of MT5 bars for signal and the perp only for cost and execution.

---

## PROMISING, not proven: silver as a second book (2026-09-20) — `backtest/silver_pair.py`

### Silver survives Binance's costs

| cost model | trades | meanR | PF | in-sample | holdout |
|---|---|---|---|---|---|
| MT5 (what forex.py charged) | 1,015 | +0.749 | 1.62 | +0.103 | +1.718 |
| **Binance TAKER** (10bp + 0.97bp/night funding) | 1,015 | **+0.746** | 1.62 | +0.099 | +1.717 |
| Binance MAKER (4bp) | 1,015 | +0.811 | 1.70 | +0.166 | +1.779 |

The venue change is free: Binance funding (+0.322bp/8h measured over 500 periods) is
CHEAPER than Exness swap, and the fee is unchanged. Note these Rs are per POSITION of up
to 5 pyramid units, so they are not comparable to forex.py's single-unit +0.226.

### The correlation is genuinely zero

**Monthly correlation with the crypto blend: -0.042 over 80 overlapping months.** Not
low - zero. And the by-year table shows why:

| year | crypto | silver |
|---|---|---|
| 2020 | +299% | **+77%** |
| 2021 | +1,783% | **-26%** |
| 2022 | +2% | **-37%** |
| 2023 | +673% | +12% |
| 2024 | +1,423% | +6% |
| 2025 | +103% | **+61%** |
| **2026** | **+14%** | **+135%** |

**They alternate.** Crypto earns in 2021/2023/2024; silver earns in 2020/2025/2026 - and
2026, crypto's worst year, is silver's best by a wide margin.

### The pair does cut drawdown

| book | /month | maxDD | return/DD |
|---|---|---|---|
| crypto only | +22.25% | 90.9% | 0.245 |
| **75/25 crypto/silver** | **+20.42%** | **76.2%** | **0.268** |
| 50/50 | +16.94% | 64.3% | 0.263 |
| silver only | +1.83% | 56.9% | 0.032 |

**90.9% -> 76.2% of drawdown for 1.8 points of monthly return.** That is the first
risk improvement found in two weeks that does not come out of the return.

### Why it is NOT proven

1. **Silver's edge is 17x stronger in its holdout than in-sample** (+0.099 -> +1.717),
   and that holdout is the metals bull market. Gold was killed for this exact pattern -
   gold was NEGATIVE in-sample, silver is barely positive. That is a thin distinction.
2. **Silver lost money in 2021 and 2022** and made almost everything in 2025-2026. Two
   good years is not a track record.
3. **Silver wins only 28% of months.** As a standalone book it is close to worthless
   (+1.83%/mo at 56.9% DD); its entire value here is the correlation.
4. **The crypto series in this test omits the regime gate.** `blend.run`'s raw R was used
   without the x0.25 BTC-bear multiplier, so crypto's +22.25%/month and 90.9% drawdown
   are both inflated relative to the deployed config's ~13%/mo and ~75%. The correlation
   is unaffected and the relative drawdown improvement should hold, but the absolute
   levels in the tables above are not the deployed numbers.
5. The XAGUSDT perp itself only listed 2026-01-07, so live execution on it is unproven.

### What to do

Paper-trade it alongside the crypto blend. It costs nothing, it needs $25 of capital
rather than $15,869, and it answers the only open question - whether silver earns outside
the metals bull - in real time rather than by argument. Do not size it as a second engine;
size it as the insurance the numbers say it is.

---

## WORKS: the regime gate is pointed the wrong way for shorts (2026-09-20) — `backtest/bear_side.py`

The deployed config applies ONE multiplier to both sides - while BTC is below its
1000h average, longs AND shorts are quarter-sized. A bear regime is precisely when a
short should work and a long should not, so the gate is symmetric where it has no
reason to be. `blend.sleeve()` discards the side tag, which is why this split had never
been measured.

### Shorts earn more in bears, but they are not an engine

15,736 sleeve trades, 2020-02 to 2026-09, **54% of trades open in a bear regime**:

| | n | mean R | win% | total R |
|---|---|---|---|---|
| long, bull | 2,935 | **+6.295** | 8% | +18,475 |
| long, bear | 2,693 | +0.237 | 4% | +638 |
| short, bull | 4,324 | +0.014 | 31% | +59 |
| **short, bear** | 5,784 | **+0.081** | 34% | +470 |

**+0.081R in bears against +0.014R in bulls.** Real, consistent, and small - my
registered prediction of +0.2R vs -0.3R was wrong in both directions. And it is NOT one
year: short-in-bear R is positive in **6 of 7 years** (only 2021 negative), strongest in
2022 (+0.280) and 2025 (+0.152).

### Sizing the hedge when it is needed improves everything

Five gate variants, declared before running, as (long, short) bear multipliers:

| variant | TUNE /mo | DD | floor | HOLD /mo | DD | floor |
|---|---|---|---|---|---|---|
| current (0.25L, 0.25S) | +29.23% | 75.7% | $385 | +13.17% | 75.2% | $377 |
| free_short (0.25L, 1.00S) | +30.47% | 68.8% | $300 | +13.96% | 73.4% | $352 |
| **lean_short (0.25L, 2.00S)** | **+32.07%** | **59.8%** | **$233** | **+14.91%** | **71.5%** | **$328** |
| flat_long (0.00L, 1.00S) | +22.86% | 84.7% | $611 | +14.07% | 69.4% | $306 |
| all_in_bear (1.00L, 1.00S) | +30.76% | 86.5% | $694 | +11.60% | 88.4% | $805 |

**lean_short improves return, drawdown AND capital floor, in BOTH halves.** That is the
first change in two weeks that is not paid for out of something else. `all_in_bear`
being clearly worse is the control confirming the existing gate does real work.

### The mechanism, so this is not mistaken for "shorts make money"

Shorts average +0.081R - nowhere near a profit source. docs/01 already records that the
short sleeve is a drawdown hedge (78.6% -> 68.9%). What this test found is that **the
hedge was being shrunk in the only regime where it pays.** Doubling it there cuts
drawdown, and lower drawdown compounds into higher return. The gain is risk management,
not a new edge.

### The multiplier sweep, and why 3x is the defensible number (2026-09-20)

**First, what a big short multiplier actually risks.** Shorts are ONE unit on a 5xATR
trail with breakeven at 3R - no pyramid. The **worst short-in-bear trade in the whole
sample is -1.19R** (1st percentile -1.11R). So:

| multiplier | risk per unit | worst single short |
|---|---|---|
| 2x | 0.60% | -0.7% of equity |
| 3x | 0.90% | -1.1% |
| 4x | 1.20% | -1.4% |
| 6x | 1.80% | -2.1% |

**That is the whole reason this sweep can go so high.** A pyramided long can lose 20R at
breakeven and 37.7R at worst; a short's loss is bounded near -1.2R. 6x on shorts is not
remotely 6x on longs.

**The curve at the deployed long multiplier (0.25):**

| short mult | tune /mo | holdout /mo | holdout DD | holdout MAR |
|---|---|---|---|---|
| 0.25 *(deployed)* | +29.23% | +13.17% | 75.2% | 17.53 |
| 1.00 | +30.47% | +13.96% | 73.4% | 19.01 |
| 2.00 | +32.07% | +14.91% | 71.5% | 20.87 |
| **3.00** | +33.59% | **+15.75%** | **70.6%** | 22.31 |
| 4.00 | +35.03% | +16.47% | 72.4% | **22.75** |
| 6.00 | +37.69% | +17.58% | 79.5% | 22.12 |

**Return is MONOTONE to the edge of the grid.** That is not a peak - it is "6x was the
largest value tested". `bear_side.sweep()` printed *"both halves peak in the same place,
that is evidence"*, and **that logic is wrong at a grid boundary**: a monotone response
has no interior optimum and says nothing about where to stop.

**Drawdown is what has a real optimum.** It falls to a minimum at **3x (70.6%)** and then
rises - 72.4% at 4x, 79.5% at 6x. That U-shape IS the smooth single-peaked response
docs/00 calls evidence, and it is the number to trust.

So: **3x minimises drawdown, 4x maximises MAR, and return keeps climbing past both**
because past 3x you are no longer sizing a hedge, you are adding a +0.081R book at size.
The drawdown turn is where that crossover happens.

**Recommendation: 0.25 long / 3.0 short in bears.** +15.75%/mo against +13.17%
deployed, at 70.6% drawdown against 75.2%. 4x is defensible on MAR; 6x is off the grid
edge and should not be trusted.

Also from the grid: the LONG multiplier barely matters in the tune window (0.25 / 0.50 /
1.00 all within 0.4 points) but matters clearly in the holdout, where 0.25 is best and
1.00 is worst by 4.9 points. The existing long gate is doing real work.

### RECHECKED by close date, and the drawdown claim shrinks (2026-09-20) — `backtest/bear_date.py`

`bear_side.run` and `blend.run` both apply each trade's P&L in order of trade OPEN time -
mistake #6. That bites hardest here, because shorts exit in hours on a 5xATR trail while
pyramided longs run for weeks on 20xATR, so **changing the long/short mix changes the
holding-period mix, which is exactly what an open-order curve mis-times.** The whole case
for 3x was a drawdown shape, so it had to be rebuilt on a curve indexed by CLOSE DATE.

| short mult | TUNE /mo | TUNE DD | HOLD /mo | HOLD DD | worst month | win% |
|---|---|---|---|---|---|---|
| 0.25 *(deployed)* | +27.13% | 72.6% | **+9.07%** | 76.9% | -32.8% | 38% |
| 1.00 | +28.27% | 67.1% | +9.55% | 76.0% | -33.0% | 46% |
| 2.00 | +29.65% | 59.4% | +9.93% | **75.6%** | -33.7% | 50% |
| **3.00** | +30.85% | **54.5%** | **+10.07%** | 76.1% | -37.2% | 54% |
| 4.00 | +31.90% | 57.2% | +9.99% | 78.7% | -43.5% | 58% |
| 6.00 | +33.55% | 63.0% | +9.27% | 84.1% | -56.0% | 58% |

**Three things change, two of them against the earlier write-up.**

1. **The deployed config's honest holdout return drops from +13.17% to +9.07% per
   month.** A 31% haircut, purely from fixing the compounding order. Every "+13%" figure
   in this repo that came from `blend.run` carries the same defect.
2. **The drawdown benefit is much smaller than claimed.** Holdout DD goes 76.9% -> 76.1%
   at 3x - under one point, not the 4.6 points the trade-order run reported. The large
   drawdown improvement (72.6% -> 54.5%) exists only in the TUNE window.
3. **But the evidence got STRONGER in one way.** By trade order, holdout return was
   monotone to the grid edge, which is no evidence at all. By date it has a real
   **interior peak at 3x (+10.07%)**, falling to +9.99% at 4x and +9.27% at 6x. MAR also
   peaks at 3x. An interior optimum agreed on by two different accounting methods is
   worth more than a monotone slope.

Also visible: the worst single month gets steadily worse - **-32.8% at 0.25x to -37.2% at
3x to -56.0% at 6x**. So 3x buys ~1 point of monthly return and 16 points of monthly win
rate for ~4.4 points of worst-month.

**Neither method is correct.** Trade-order scrambles time; close-date books a
twenty-week trade's entire P&L on a single day, which inflates daily variance. True
drawdown needs bar-level mark-to-market of open positions, which no file here does. What
the two methods AGREE on is the direction and the location: **leaning short in a bear
helps, and the useful range is 2x-3x.** What they disagree on is how much drawdown it
saves, so that part should not be quoted.

**Revised recommendation: 0.25 long / 3.0 short, claimed as +1 point of monthly return
and a better win rate, NOT as a drawdown fix.**

### Before shipping

- Only three short multipliers were tried (0.25 / 1.00 / 2.00). 2.00 beats the other two;
  it is not established as optimal, and sweeping further would be fitting the multiplier.
- The tune window's drawdown gain (-15.9 points) is four times the holdout's (-3.7). The
  effect is weaker out of sample, as usual.
- ~88% of the short-in-bear total R comes from 2022 and 2025, even though the sign holds
  in 6 of 7 years.
- Do not change the live config mid-forward-test; this is a candidate for the decision at
  ~200 closed trades, alongside 8-vs-12 slots.

---

## Dead, and it validates the existing design: splitting slots by side (2026-09-20) — `backtest/slot_split.py`

Shorts are 64% of all sleeve trades and contribute +529R against longs' +19,113R. The
shared 12-slot queue therefore gives most of its capacity to the side that produces
almost none of the profit, and the live bot declines ~7 signals for every one it takes -
so who gets the slot is not academic. Separate caps per side, compounded by CLOSE DATE:

| split | TUNE /mo | DD | HOLD /mo | DD | worst month | longs taken | shorts taken |
|---|---|---|---|---|---|---|---|
| **shared 12 (deployed)** | +27.13% | 72.6% | **+9.07%** | 76.9% | -32.8% | 919 | 1,113 |
| 2 long / 10 short | +2.39% | 39.0% | +0.43% | **38.6%** | -26.3% | 362 | 2,375 |
| 6 long / 6 short | +7.23% | 64.6% | +5.13% | 51.5% | -25.5% | 910 | 1,509 |
| 8 long / 4 short | +12.40% | 70.3% | +5.88% | 61.6% | **-19.4%** | 1,151 | 1,063 |
| 10 long / 2 short | +21.32% | 76.8% | +5.98% | 71.0% | -29.6% | 1,397 | 527 |
| 12 long / 0 short | +24.58% | 80.6% | +6.49% | 82.8% | -47.6% | 1,579 | 0 |
| 8/8 = 16 total *(more exposure)* | +12.09% | 71.6% | +5.95% | 58.2% | -24.1% | 1,151 | 1,990 |
| 12/12 = 24 total *(more exposure)* | +23.66% | 81.6% | +7.15% | 74.9% | -42.7% | 1,579 | 2,714 |

**The shared queue beats every split, including the two with MORE total exposure.**

### The part that is genuinely surprising

**12 long / 0 short takes 1,579 longs - 72% more than the shared queue's 919 - and
returns 28% LESS** (+6.49% against +9.07%). So the extra longs a bigger long cap admits
are *worse than the average long*. The rationing is selecting better trades, not merely
fewer.

The mechanism: **the shared cap is not a naive queue, it is a limit on TOTAL concurrent
exposure.** When many signals fire in the same hour - which is the normal case in
crypto - it takes the first 12 and declines the correlated pile-on behind them. Split the
caps and that pile-on gets admitted; 12/12 allows up to 24 concurrent positions in a book
measured at ~1.5 independent bets, and it earns less than 12 shared.

That also retroactively explains `backtest/corr_alloc.py`, where correlation clustering
lost to a plain global cap: **the global cap was already doing the correlation work.**

**Registered prediction half right.** I predicted reserving slots for longs would beat
the shared cap clearly - wrong, it loses 2.6 to 8.6 points of monthly return. I predicted
drawdown would worsen as the short hedge thins - right, and strongly: 38.6% at 2/10
rising monotonically to 82.8% at 12/0.

**Also worth keeping:** 8 long / 4 short has the best worst-month of any row (-19.4%
against the deployed -32.8%) at 61.6% drawdown, for 3.2 points of monthly return. If a
future decision ever prioritises the worst month over the mean, that is the row.

**Net effect on the deployed config: none.** The shared 12-slot queue stands, and the
only surviving improvement from today's work is the 3.0x short multiplier in bears
(+9.07% -> +10.07% per month, win rate 38% -> 54%).

---

## Dead: relative-value dispersion as a bear trade (2026-09-20) — `backtest/bear_alpha.py`

The last untested structural shape for earning when crypto falls. Every prior short test
shorted a coin outright, fighting crypto's upward drift and paying funding. This one is
RELATIVE: long BTC, short the alts, dollar-neutral, only while the regime gate says bear.
The market factor cancels, so it needs only alts to fall FURTHER than BTC.

| book | months | geo/month | median | up% | maxDD |
|---|---|---|---|---|---|
| deployed crypto book *(reference)* | 80 | +24.44% | -1.17% | 48% | 76.4% |
| bear: long BTC / short alts, GROSS | 73 | +0.19% | +0.26% | 55% | 22.2% |
| **bear: net of fees** | 78 | **+0.04%** | +0.04% | 50% | 23.3% |
| bull mirror: long alts / short BTC, net | 78 | +0.74% | -0.11% | 45% | 32.6% |

**+0.04% per month is zero.** Weekly turnover 0.50, so fees take almost the entire gross.

### And it loses in the year it was built for

| year | deployed | bear dispersion | bull mirror |
|---|---|---|---|
| 2021 | +1,612% | -9.3% | **+109.0%** |
| 2022 | +62% | +10.2% | -3.9% |
| 2023 | +622% | +17.3% | +3.6% |
| 2024 | +1,359% | -10.6% | +5.3% |
| 2025 | +196% | +20.7% | -8.4% |
| **2026** | +42% | **-14.0%** | -18.1% |

**2026 - the current non-trending year, the exact conditions this was meant to exploit -
is the bear leg's worst.** And the bull mirror's entire lifetime profit is 2021's alt
season; it is negative in 4 of 7 years. Monthly correlation with the deployed book is
-0.010, genuinely zero - but an uncorrelated stream that returns nothing is worth nothing.

### Correcting my own tool, for the second time today

`bear_alpha.main()` printed **"BOTH DIRECTIONS WORK - that is a dispersion edge"** because
its verdict test was `cumulative > 1`. A +0.04%/month result passes that and is
indistinguishable from zero. Earlier the same day `bear_side.sweep()` printed "both halves
peak in the same place, that is evidence" at a grid boundary, where a monotone response is
no evidence at all. **Both verdict functions were too lax, and in both cases the tables
contradicted the verdict line.** Read the tables.

### Part 1: the regime gate is a detector, and a noisy one

Months tagged by the gate's state at their start:

| month started in | n | mean | median | up% | sum |
|---|---|---|---|---|---|
| bull | 46 | +66.6% | **+0.85%** | 50% | +3,063% |
| bear | 34 | +31.2% | **-2.56%** | 44% | +1,062% |

It does discriminate - positive median in bull-start months, negative in bear-start
months, and 74% of the profit sum in bull months. But **the gate flipped state 41 times in
80 months, once every 2 months.** It identifies that a trend has begun, late and with
whipsaw. **There is no predictor here and there is no point building one.**

### The conclusion for bear markets, now settled

Five independent attempts at a crypto short edge: 19 indicator families (none), the short
sleeve (+0.081R, a hedge), taker flow (retracted), crowd positioning (beta), and now
relative-value dispersion (+0.04%/mo). **Crypto does not offer a retail-accessible short
edge.**

*(2026-09-21: one exception, and it is event-driven, not a book. When an old coin gets its
first Binance perp, shorting it against BTC earned +10%/trade and passed a placebo. The
events stopped in May 2025. See "Three new bear ideas" below.)*

**What DID earn in 2026:** silver, +135%, while crypto made +14% and the dispersion trade
lost 14%. The answer to "how do we earn when crypto falls" is not a crypto short - it is
not crypto. See the silver entry above.

---

## MEASURED for the first time: we keep 21% of peak (2026-09-21) — `backtest/giveback.py`

Prompted by the live book: AVAX +89.2R open with its stop still at the entry price. Nobody
had measured the obvious thing - for a position that reaches a peak of +X R, what does it
actually close at? 5,628 long pyramid positions, deployed config, all three sleeves:

| peak bucket | n | median peak | median exit | capture | sum exit | given back |
|---|---|---|---|---|---|---|
| 0-2R | 3,777 | +0.5 | -1.0 | -212% | -3,947 | +6,362 |
| 2-5R | 624 | +3.1 | -4.1 | -129% | -2,126 | +4,176 |
| 5-10R | 422 | +6.6 | **-6.1** | -92% | -1,927 | +4,889 |
| 10-20R | 242 | +13.8 | **-10.1** | -73% | -2,114 | +5,555 |
| **20-50R** | 227 | **+31.4** | **-12.4** | **-40%** | -2,330 | +9,786 |
| 50-100R | 138 | +65.7 | +11.3 | 17% | +1,415 | +8,109 |
| **100R+** | **198** | **+186.5** | **+79.2** | **42%** | **+30,141** | +31,186 |

**Across everything: peak sum +89,176R, exit sum +19,113R. We keep 21% of peak and give
back 70,063R.**

### Two facts that are worse than "we give back a lot"

**1. Every bucket from 5R to 50R closes NEGATIVE on the median.** A position that showed
+31.4R at its peak closes at **-12.4R**. That is the pyramid plus the breakeven floor: it
adds units on the way up, reverses, and the floor sits at the FIRST entry, so the added
units lose 2R, 4R, 6R, 8R each.

**2. 198 positions out of 5,628 - 3.5% - produce +30,141R against the book's total
+19,113R.** Everything below +50R of peak sums to **-12,444R**. The strategy is 3.5% of its
trades carrying 158% of the profit, which is even more concentrated than the 1%/114%
figure measured on trades.

### Six more exit rules tested. All worse.

A trail that leaves the 20xATR alone until a HIGH threshold, then tightens - the opposite
of `pyramid_exits.py`'s ratchet, which started at +10R and taxed the whole distribution:

| rule | positions | total R | vs deployed | median exit of >50R peaks |
|---|---|---|---|---|
| deployed | 5,628 | **+19,113** | - | +39.5 |
| tighten above +80R to 0.5x | 6,068 | +14,932 | -4,181 | +46.8 |
| tighten above +80R to 0.25x | 6,279 | +9,476 | -9,637 | **+58.3** |
| tighten above +40R to 0.5x | 6,379 | +13,464 | -5,649 | +40.6 |
| tighten above +20R to 0.25x | 7,409 | +5,974 | -13,139 | +43.1 |

**Tightening DOES capture more of each big winner** - median exit on >50R peaks rises from
+39.5 to +58.3. **And total R falls anyway.** Look at the position count: 5,628 becomes
6,279. Exiting a winner early does not bank the profit, it **puts you back in the queue for
another entry**, and a fresh entry is a 77%-loser lottery. The giveback is not waste; it is
the alternative to re-entry.

### The reason no exit rule can work, stated properly

**At the moment a position is at +31R, it is observationally identical to a 100R+ position
passing through +31R on its way to +186R.** The median 20-50R position closes at -12.4R;
the median 100R+ position closes at +79.2R; and at +31R they look the same. Any rule keyed
on R must treat them identically.

> **This is not a tuning problem, it is an identification problem.** Nine exit rules have
> now been tested (profit target, scale-out, average-entry breakeven, uniform ratchet, and
> five high-threshold trails). All of them lose, and they lose for the same reason: the
> information needed to act is not present at the moment of acting.

The only thing that could break the tie is a FEATURE at +20R that separates continuation
from reversal - which is a new signal, not an exit rule. That is the one remaining version
of this question and it is well defined: **among positions that first cross +20R, does
anything predict which reach +100R?** If nothing does, the question closes permanently.

---

## CLOSED: the runner is identifiable and still not tradable (2026-09-21) — `backtest/runner_id.py`, `backtest/runner_pnl.py`

The last version of the exit question. `giveback.py` established that at +20R a position
heading for -12R and one heading for +186R are observationally identical, so the only
remaining hope was a FEATURE that separates them.

**563 positions crossed +20R. 198 (35%) went on to +100R.** Runners close at **+79.2R**
median, the rest at **-5.3R**. Perfect foresight - closing the 365 non-runners at +20R -
would be worth **+9,246R against the book's lifetime +19,113R**. A 48% improvement. The
prize was real.

### A feature does separate them, and it survives everything

Eight features declared before looking, Holm-corrected, then held out by date:

| feature | runners | others | AUC | p | Holm |
|---|---|---|---|---|---|
| **atr_ratio** (ATR now / ATR at entry) | **1.948** | **1.783** | **0.604** | **0.003** | **0.028** |
| ext_ma | 1.249 | 1.195 | 0.565 | 0.004 | 0.028 |
| btc_bear | 0.096 | 0.188 | 0.454 | 0.028 | 0.170 |
| coin_30 | 0.213 | 0.170 | 0.544 | 0.055 | 0.276 |
| bars_held, r_per_bar, units, btc_30 | - | - | 0.45-0.55 | 0.20-0.87 | 1.000 |

**Holdout: `atr_ratio` HOLDS with a HIGHER AUC out of sample - 0.604 -> 0.647, p=0.001.**
`ext_ma` does not (AUC 0.513). So volatility expansion since entry genuinely predicts
which positions run.

**Both registered predictions were wrong.** I said `r_per_bar` would be best - it measured
nothing (AUC 0.546, p=0.811). And I said any survivor would be a REGIME feature; this is a
position feature.

### Using it loses money at every threshold

Exit at the CLOSE of the crossing bar (never its high) when volatility has not expanded,
with re-entries allowed to happen normally - which is what makes this P&L rather than a
statistic:

| rule | positions | total R | vs deployed |
|---|---|---|---|
| **deployed (hold everything)** | 5,628 | **+19,113** | - |
| exit if atr_ratio < 1.5 | 6,141 | +17,945 | -1,168 |
| exit if atr_ratio < 1.8 | 6,745 | +13,115 | **-5,999** |
| exit if atr_ratio < 1.9 | 6,958 | +11,470 | -7,643 |
| exit if atr_ratio < 2.5 | 7,907 | +6,207 | -12,907 |

**Monotonically worse the more the filter is used** - and 1.8-1.9 is precisely where the
two distributions part, so this is not a bad threshold choice. It is the rule.

### Why a real feature still cannot be used

Two costs, and together they swamp an AUC of 0.647:

1. **The error asymmetry.** Exiting a true runner at +20R gives up **59.2R** (79.2 - 20).
   Saving a true reversal gains **25.3R** (20 - -5.3). You lose 2.3x more when wrong than
   you gain when right, and at AUC 0.647 you are wrong about a third of the time in each
   direction.
2. **There is no cash state.** Position count rises 5,628 -> 7,907. Exiting does not bank
   the profit, it returns you to the queue, and the next entry is a 77%-loser lottery. The
   same mechanism killed the six high-threshold trails.

> **Ten exit rules have now been tested and all ten lose.** Profit target, scale-out,
> average-entry breakeven, uniform ratchet, five high-threshold trails, and a
> statistically validated runner-detector. **The 21% capture is not a defect to be
> engineered away - it is the strategy.**

**This question is closed.** Hold everything, keep 21% of peak, and stop looking for an
exit rule. Any future idea here must first explain how it beats the 2.3:1 error asymmetry
AND the re-entry drag, because those two facts kill every rule regardless of how good its
signal is.

---

## Dead: take profit early and trade more often (2026-09-21) — `backtest/freq_capture.py`

Every prior exit test held the entry fixed, so it only measured the capture side. This
sweeps BOTH axes: entry looseness (Bollinger k from 1.0 to 2.5) against a fixed profit
target. And it is the one version of the idea not killed by costs - `fee_sweep.py` showed
a 2xATR stop is 8-15% of price here, so 12bp is ~0.012R against a +3.4R average position.
**Trading ten times as often costs almost nothing in fees.**

**The relationship is monotone, and that settles it.** Single unit, 2xATR stop, k=1.5:

| exit | target in R | trades | frequency | win% | **mean R** | total R |
|---|---|---|---|---|---|---|
| target 2xATR | 1.0R | 45,854 | **8.1x** | **51%** | **-0.011** | -509 |
| target 3xATR | 1.5R | 32,915 | 5.8x | 42% | +0.003 | +89 |
| target 5xATR | 2.5R | 20,302 | 3.6x | 30% | +0.027 | +556 |
| target 10xATR | 5.0R | 9,242 | 1.6x | 19% | +0.076 | +704 |
| **none - 20xATR trail, 5-unit pyramid** | - | 5,628 | 1.0x | **6%** | **+3.396** | **+19,113** |

**Every time the target widens, mean R rises and the win rate falls.** Five points, no
inflection. A monotone function has its optimum at the boundary, and the boundary is **no
target at all.**

The win rates also land almost exactly on their own breakeven lines - 51% against 50% for
a 1:1 payoff, 42% against 40%, 30% against 28.6%, 19% against 16.7%. **The strategy is
barely better than a coin flip at any fixed target.** Its entire edge lives past +5R.

**Frequency cannot close the gap.** The deployed mean R is +3.396 against the best
target cell's +0.045 - a **75x** difference. The loosest entry tested buys **9.3x** the
trades. To match on total R you would need ~428,000 trades, and they would all compete for
the same 12 slots, which this test does not even model.

**Entry looseness barely matters on its own**, which is a mild validation of the deployed
parameter: k=1.0 gives +18,705R, k=1.5 (deployed) +19,113R, k=2.0 +18,530R, k=2.5
+16,638R. The deployed setting is at the peak of a flat curve.

> **Taking profit early works exactly as intended - the win rate goes from 6% to 51%.
> And it makes no money.** Win rate is not P&L. This is the eleventh exit rule tested and
> the eleventh to lose.

**Labelling correction:** the first run of this file printed targets as "+2R..+10R" when
`run_r`'s `tp_mult` is in ATR units and 1R = 2xATR. Every target was half what the label
said. The conclusion is unchanged - the monotone relationship holds either way - but the
numbers above are the corrected ones.

---

## Answered: isolated margin at high leverage (2026-09-21) — `backtest/mae.py`, `backtest/lev_test.py`

The idea, and it is a good one: post a small ISOLATED margin at high leverage. The most you
can lose is the margin; the upside is uncapped. A lottery ticket with a known ticket price.

**The measured fact that makes it plausible.** Maximum adverse excursion - how far below
entry a position goes before it wins:

| group | n | median MAE | 75th | 90th |
|---|---|---|---|---|
| ALL positions | 5,628 | 3.21% | 5.25% | 8.36% |
| **RUNNERS (peak >= +100R)** | 198 | **1.04%** | 2.03% | 3.65% |
| non-runners | 5,430 | 3.28% | 5.33% | 8.48% |

**Runners barely dip.** They go up almost immediately; losers chop around first. So a tight
liquidation line removes losers preferentially - at 20x (liquidation ~-5%) **94.9% of
runners survive while only 72.8% of all positions do.**

### The first pass said 20x BEATS the deployed config. It was wrong.

That pass dropped liquidated positions instead of charging them, and did not let the signal
re-fire. Both fixed - liquidation modelled as a stop at avg_entry x (1 - 1/L), firing
whenever it is tighter than the strategy's own stop, R charged over all units, re-entries
allowed:

| leverage | liquidation at | positions | liquidated | win% | mean R | total R | vs deployed |
|---|---|---|---|---|---|---|---|
| **none (deployed)** | - | 5,628 | 0 | 6% | **+3.396** | **+19,113** | - |
| 3x | -33.3% | 5,629 | 1 | 6% | +3.395 | +19,111 | **-2** |
| 5x | -20.0% | 5,642 | 46 | 6% | +3.386 | +19,105 | **-8** |
| **10x** | **-10.0%** | 5,817 | 503 | 6% | +3.284 | **+19,105** | **-8** |
| 20x | -5.0% | 6,873 | 2,645 | 4% | +2.491 | +17,119 | -1,994 |
| 50x | -2.0% | 11,453 | 9,915 | 2% | +1.286 | +14,724 | -4,389 |
| 100x | -1.0% | 20,300 | **20,002** | 1% | +0.469 | +9,522 | -9,591 |

**Two findings, one useful and one decisive.**

**Up to 10x is FREE.** -8R out of +19,113R is noise. Only 503 of 5,817 positions liquidate
and total R is unchanged. That matters because the live book already runs at **1.20x gross**
(measured: $250.72 of notional on $209.77 of equity), so some futures leverage is already
in use and there is headroom to 10x at no cost.

**Above 10x it degrades monotonically, and the mechanism is not the loss size.** Look at the
position count: 5,628 at no leverage, **20,300 at 100x, of which 20,002 are liquidations.**
Mean R stays POSITIVE at every leverage (+0.469 even at 100x) - the strategy does not
become a loser, it becomes a much worse one, because frequency rises 3.6x while mean R
falls 7.2x.

> **Isolated margin caps the loss per event. High leverage multiplies the number of
> events.** Losing 0.3% is nothing; losing it 20,002 times is everything. That is the
> answer to "if losing does not matter, why not max leverage".

Same shape as `freq_capture.py`: monotone in the parameter, so the optimum sits at the
boundary - here, the lowest leverage. And the same re-entry drag that killed eleven exit
rules kills this too: being removed from a position does not bank anything, it returns you
to the queue.

**Caveats that make the table optimistic:** -1/L ignores maintenance margin, fees and
slippage, so real liquidation is closer than shown; and a liquidation is a market order on
a wick, which can close you at a price the 1h low does not capture.

---

## Answered: bigger pyramid adds, "more leverage on each add" (2026-09-21) — `backtest/escalate.py`

The idea: buy unit 1 at normal size, then put more leverage on each later add. Leverage by
itself only changes the margin you post, so the real question is whether each add should be
a **bigger notional** than the one before.

**The adds already carry more risk than unit 1.** Unit 5 is bought 8R above the first
entry, and the stop is floored at breakeven, so it can lose 8R on its own. That is why a
5-unit position stopped at breakeven loses 20R. Making the adds bigger scales up that loss
along with the runners.

**Method.** Weights do not change when anything exits, so the trade list and the slot cap
are the same in every variant. The simulation runs once and keeps each unit's own R. Each
weight scheme is then a dot product over those rows. A guard asserts that equal weights
reproduce `run_pyramid` exactly (5,628 positions). Shorts are unchanged. Results are
compounded by close date.

**Each unit earns about the same total, and every unit's median is a loss:**

| unit | bought | mean R | median R | win% | total R |
|---|---|---|---|---|---|
| 1 | 5,628 | +0.68 | -1.03 | 10% | +3,806 |
| 2 | 1,849 | +2.19 | -2.04 | 23% | +4,052 |
| 3 | 1,081 | +3.58 | -3.55 | 32% | +3,867 |
| 4 | 729 | +5.20 | -2.67 | 38% | +3,791 |
| 5 | 562 | +6.40 | -2.21 | 40% | +3,597 |

**The literal idea (same first bet, bigger adds) is just betting more:**

| scheme | tune /mo | DD | holdout /mo | DD | worst month | worst position |
|---|---|---|---|---|---|---|
| **deployed** (1,1,1,1,1) | +27.03% | 73% | **+9.07%** | 77% | -32.8% | -6.2% |
| adds x1.25 each | +40.16% | 87% | +10.83% | 90% | -57.2% | -12.3% |
| *control: flat at 1.5x risk* | +37.54% | 87% | +10.79% | 90% | -49.6% | -9.3% |
| adds x1.5 each | +54.47% | 96% | +9.54% | 98% | **-95.2%** | -22.3% |
| *control: flat at 2x risk* | +45.86% | 94% | +11.10% | 96% | -66.4% | -12.3% |
| adds x2 each (1,2,4,8,16) | -3.31% | 100% | -3.32% | 100% | -230.6% | -59.9% — **ruin in both halves** |

**x1.25 per add gives the same result as raising the whole book to 0.45% risk** (+10.83% vs
+10.79%, both at 90% drawdown), with a worse worst month. Once the adds reach x1.5 the
flat control wins outright, and x2 wipes out the account. This is the risk-size question
from `ruin.py` again. Taking drawdown from 77% to 90% buys about 1.7%/month, and that trade
was already declined.

**With the same total budget and only the shape changed:** back-loading (smaller first
unit, bigger adds) cuts drawdown from 77% to 65% at a cost of 0.6%/month. Scaled up until
drawdown matches the deployed book, back-loaded x1.5 at 1.2x risk makes **+9.54% vs +9.07%**
on the holdout. Three reasons it is not adopted:
- its worst month is -42.8% against -32.8%, and its worst single position is -10.1% against -6.2%;
- the gain shrinks out of sample, from +4.4%/month on the tune half to +0.5% on the holdout;
- **unit 1 falls to 0.46x of today's size**, and at $221 Binance's $5 floor already rejects
  30% of signals at full size (`blend_testnet.py` dry run). A smaller first unit gets
  rejected even more often.

Worth rechecking once the account is large enough that minimum order sizes stop binding.

---

## Three new bear ideas on every perp that ever existed (2026-09-21) — `backtest/perp_fetch.py`, `backtest/bear_shorts.py`

Every earlier short test used today's 12-14 big coins. This one uses **all 864 USDT perps
Binance ever listed, 339 of them dead**, with perp prices, 12bp, and the actual funding paid
or received at every settlement. Each result is shown raw and as **excess** over shorting a
point-in-time index of established perps for the same days, because shorting anything in
2022 made money. t-statistics are computed across months.

### 1. Shorting new listings: dead (registered primary failed)

Primary, registered before the data: new token, short at the open of day 1, hold 30 days,
stop at +100%.

| | n | mean | median | win% | funding | t (months) | excess |
|---|---|---|---|---|---|---|---|
| all | 645 | +2.2% | **+11.3%** | 63% | -0.8% | +0.68 | +1.7% |
| holdout | 258 | +1.6% | +4.2% | 59% | -1.1% | **-0.02** | -1.0% |
| as a book (10 slots, 1x) | 386 taken | **+0.66%/mo** | | | | max DD 72% | worst month -66.6% |

**The typical new listing does fall 11% in its first month. The average short still makes
nothing**, because the few that double wipe out the rest. Without a stop it is a catastrophe:
the worst single trade loses **-12,741%** of its notional. Best of 36 grid cells t = +1.90,
which does not survive Holm. My prediction that 2021 would be the losing year was wrong;
2024 was.

### 2. Fading pumps: dead

Short an established perp after +30% to +100% in 3-7 days: **22 of 24 cells have a negative
mean.** The median is positive and the mean is negative in almost every cell, the same
squeeze arithmetic as idea 1. This makes seven failed reversal ideas.

### 3. Shorting the weakest coins: dead as a bear trade

| weekly short, mean | bottom decile (30d) | everything | top decile |
|---|---|---|---|
| BTC-bear weeks | -0.37% | **+0.05%** | -1.27% |
| BTC-bull weeks | -0.14% | -1.59% | -2.16% |

**Even shorting everything earns nothing in bear weeks.** By the time BTC is below its
average the fall has already happened, and bounces follow. In bear weeks, shorting the
losers does worse than shorting everything, and shorting the winners is the worst choice in
every regime. That is cross-sectional momentum again (`xs_paper.py`), not a bear edge.

### The lead: an OLD coin getting its first Binance perp

This came from the grid's control group, not the registered primary, so read it as a
finding to confirm. It is a coin that had traded on Binance spot for more than 60 days
before its perp was listed. Short it at the open of day 7, hold 30 days, stop at +50%, and
**buy the same dollar amount of BTC as a hedge** (BTC funding and fees charged):

| | n | pair mean | median | t (months) | months up |
|---|---|---|---|---|---|
| all | 199 | **+10.3%** | +17.1% | +3.06 | 73% |
| tune (< 2023-08) | 119 | +6.6% | +13.0% | +1.08 | 64% |
| **holdout** | 80 | **+16.0%** | +20.1% | **+4.10** | 88% |

**It passes a placebo.** Run the same trade on the same coins starting later, when there is
no listing, and the result disappears:

| enter on day | 7 | 60 | 120 | 180 | 365 | 540 |
|---|---|---|---|---|---|---|
| pair mean | **+10.3%** | -0.3% | +1.5% | +2.5% | +0.2% | +1.3% |
| t | **+3.06** | -0.05 | +0.93 | +1.24 | +0.84 | +0.92 |

So this is not the general bleed of small altcoins against BTC. The effect belongs to the
listing window.

**It has a dose-response, and a known mechanism.** The longer the coin traded without a way
to short it, the bigger the effect: +6.0% (60-180 days of spot history), +3.9% (180-365),
+8.5% (365-730), **+15.8% at 730+ days (t +2.91)**. That is Miller's short-sale-constraint
hypothesis. While nobody can short a coin, its price reflects only the optimists. A perp lets
the pessimists in, and the price corrects. It is also the documented story of CME Bitcoin
futures in December 2017.

### Why it cannot be traded: the events have run out

| year | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| old-coin perp listings | 37 | 40 | 13 | 58 | 38 | 13 | **0** |

**The last one was OGUSDT on 2025-05-12.** Binance has now listed a perp for
almost every old spot coin it had. In 2026 only 17 of 223 new perps had Binance spot at all.
Binance lists perps first now. Of the 120 spot coins still without a perp, most are
tokenized stocks (MSTRB, NVDAB...). The crypto ones left are a short list: LUNA, FTT, RAY,
XNO, REQ, OSMO, NEXO, AI, CITY, GLMR, 1000SATS.

**What it is worth:** a real edge with a mechanism, a placebo pass and a dose-response,
whose supply of events on Binance has dried up. Worth a small watcher that alerts when
Binance lists a perp for a coin with long spot history, since each event is worth about +10%
to +16% on the pair. It is not a book. Other venues listing their first perp on an old coin
are the obvious place to look next. The mechanism should be weaker there if Binance or
someone else already lets people short the coin.

---

## Dead: the deployed rules on Binance's 199 TradFi perps (2026-09-21) — `backtest/tradfi.py`

Binance futures now lists 199 non-crypto perps on the same account, with the same code and
the same $5 minimum: gold, silver, platinum, palladium, copper, WTI, Brent, natgas, SPY,
QQQ, country ETFs and ~150 stocks. The hope was more independent bets, since 12 coins
behave like 1.5. The deployed rules were run unchanged on daily bars back to 2005. Fills
are gap-aware (a stop the market opens through fills at the open), and costs are 12bp plus
1bp/8h funding on longs. A guard reproduces `run_pyramid` on crypto to within 0.2R.

**The diversification is real. The edge is not.**

| | result |
|---|---|
| correlation with the crypto blend | **-0.06 to +0.09** for all 12 commodities/ETFs |
| effective bets within those 12 | **~4.0** (mean pairwise corr +0.18), vs crypto's 1.5 |
| **commodities + ETFs as a book** | **-0.03%/mo, 83% DD. Loses in 14 of 19 years; 2026 alone is +227% (the metals bull)** |
| hold in both halves | 1 of 12 (QQQ, at +0.10R) |

Gold, silver, Brent, Korea and Japan are all "one regime": negative in the first 60% of
history, positive only in the recent bull. That is the same pattern that killed gold in
`forex.py`, now on 20 years.

**Stocks cannot be measured on Binance's own list.** NVDA +22.6R per position, AVGO +26.3R,
PLTR +44.3R. Binance lists these stocks *because* they won, the same selection that put a
3x premium into the crypto book. The fair version uses the **40 largest US companies at
end-2005**, chosen by size at the time:

| | result |
|---|---|
| hold in both halves | 8 of 40 |
| longs | +6.9R per position, but **negative every year 2006-2013** (2008: -580R) |
| shorts | **-0.38R per position, 3,154 of them** (PF 0.49), negative in 18 of 21 years |
| as a book (12 slots) | **+0.21%/mo, 81% DD** |

On daily bars a 20xATR trail means holding for years. The long results are mostly the
2014-2026 US bull market carried on a wide stop, after eight straight losing years. Adding
the long-only stock book to crypto lifts the 2020-26 overlap from +24.3% to +26.7%/month
only because that overlap is the stock bull. The book would have lost 2006-2013 on its own.

**Short side on stocks is the cleanest negative result in the project**: 3,154 positions,
losing in 18 of 21 years, including 2008 barely (+45R) and 2022 (-22R). Shorting trend
breakdowns does not work on equities any more than on crypto.

---

## CLOSED: every long family, run short, fairly (2026-09-22) — `backtest/short_families.py`

The old result ("19 of 19 families profitable long, 0 of 19 short") was measured on 9 coins
that are big today. That is the worst possible sample for shorts, because the coins that
died were the best shorts. This rerun removes every excuse:

- **Universe:** the 365 perps that were ever a top-40 perp by the prior month's volume,
  dead ones included (LUNA, FTT, SRM...), chosen point in time.
- **Families:** 16: ma_cross, donchian, rsi_mom, bb_break, macd, roc_mom, rsi_rev, bb_rev,
  supertrend, keltner, squeeze, psar, aroon, adx_dmi, ichimoku, chandelier.
- **Timeframes:** 1h, 4h and 12h, with all entries and bear-only entries (BTC below its
  1000h average).
- **Management:** the deployed short rules (2xATR stop, 5xATR trail, breakeven at 3R), 12bp,
  actual funding in R, and pessimistic same-bar fills.
- **Size:** 776,936 trades.
- **The control:** random short entries on the same coins, timeframe, exit and regime, at the
  deployed rule's signal density. The test is the pooled per-trade difference, with the
  standard error from resampling whole months.

**Result: over 96 cells, nothing beats random entries after Holm.** Five cells reach
p < 0.05, which is what chance produces in 96 tries. The best is psar 12h at t = +2.20.

| random short entries | 1h | 4h | 12h |
|---|---|---|---|
| all regimes | -0.056R | -0.034R | -0.058R |
| **bear only** | +0.001R | **+0.104R** | +0.069R |

**In bears, the entire short profit comes from being short, not from the signal.** At 4h the
deployed `bb_break` short makes +0.068R in bears, which is *less* than random entries
(+0.104R). The short sleeve works as a hedge because the regime gate puts it on in bears. Its
entry rule contributes nothing. Even the random 4h bear number is only t = +1.45 on its own.

Two measurement errors were caught and fixed before the result was read:
1. **Frozen prices.** Six coins sat at a frozen price during delisting (FTT, BAKE, HIFI,
   VANRY, ALPACA, LEND). ATR was about zero there, so R came out near ±1e30 on 1,387 trades.
   A guard now drops any trade whose stop distance is under 0.1% of price.
2. **The wrong statistic.** The first paired test averaged each month's mean and weighted
   every month equally. It reported donchian 12h at t = -5.76 against random while their
   per-trade means were -0.051 and -0.058. Trend families trade in crash months, so
   equal-weighting months punishes them for months in which they barely traded.

**This closes the question of short signals on crypto.** It has now been tested on
survivors, on the dead, at three timeframes, in both regimes and against a random baseline.
A chart pattern does not tell you when to short crypto any better than a coin flip. What
matters is whether you are short at all during a bear, and the regime gate already
decides that.

---

## Dead: trading exchange listing announcements (2026-09-22) — `backtest/listing_events.py`, `backtest/upbit_fade.py`

An information edge rather than a chart signal. When Upbit (Korea) or Binance announces a
listing for a coin that already trades, a new user base arrives at once. Announcements come
from Upbit's notice API (777 notices, original posting time) and Binance CMS catalog 48
(2,263 articles). Prices come from Binance's 1-minute archive, for coins that already traded
there.

**The pump is real, and it is gone before a home setup can act.** The table covers 122
Upbit KRW listings:

| | |
|---|---|
| peak within 60 min of the notice | **median +29%**, mean +47% |
| already in the price at the first full minute | **+17%** |
| buy 1 min late, sell after 1h / 24h / 72h | -0.5% / **-5.4%** / **-9.0%** (net) |

The fastest bots take the whole move in under a minute. There is no leak beforehand (the 60
minutes before the notice average +0.9% with a median of 0).

**The fade looks like an edge until funding is charged.** The primary test was registered
before running: short the Binance perp 60 minutes after the notice, hold 72h, stop +50%,
30bp costs.

| | n | mean | median | win | **funding** | t |
|---|---|---|---|---|---|---|
| all | 117 | +2.32% | +5.53% | 66% | **-4.51%** | +1.05 |
| holdout | 47 | +2.86% | +5.16% | 66% | -5.50% | +0.76 |
| 2026 | 34 | **-1.39%** | +2.46% | 56% | -5.63% | -0.32 |

**The price fade is about +7% gross, and funding takes -4.5% of it.** Everyone shorts the
pump, so shorts pay longs about 1.5% a day. The perp market prices the expected fade into
the cost of carrying the short. As a book at 20% per trade: +10%/yr, 24% drawdown. The best
of 27 grid cells is t = +2.26, which does not survive Holm.

**Binance spot listings of perp-first coins** (n = 33) show +3.4% in the first hour for a
1-minute-late entry. That is not significant, and 2026 is weaker (+1.5%). **Binance perp
launches** (n = 20) fall 12% over 72h, but that is the old-coin perp event, which stopped
occurring in May 2025.

**What this category teaches:** the information edge is real and large, but it is priced
within seconds, and what the fast money leaves behind is priced into funding. A retail
poller arrives after both.

---

## Dead: buying Solana memecoin graduations (2026-09-22) — `backtest/meme_grad.py`, `meme_collector.py`

The trade most "memecoin bots" run is to buy a pump.fun coin when it graduates from its
bonding curve to a PumpSwap pool. The only honest sample is **every** graduate, including
the dead ones. pump.fun's API lists graduates newest-first but pages only ~1,050 deep, which
is the last ~24 hours. So this is one full day of graduations, fetched in random order,
with minute candles from GeckoTerminal.

**What was excluded, and why:**
- "Complete" coins that never really filled a curve: 82 of 223 had an opening market value
  outside $20k-$300k (one pool was worth $2.82).
- A handful of data glitches, such as a $160M "market value" one minute after a $47k open.

Costs are 2% round trip, with a 5% stress case. An exit worth under 5% of entry is booked
as a total loss.

**Full day, 631 real graduations** (692 real, minus 61 data glitches whose price jumps
more than 50x inside the first hour on dust volume; one "WSOS" pool showed a $167M market
value on $500 a minute of trading, and alone turned the 1h mean from -55% to +10% until it
was excluded - see the bug note below):

| strategy | n | mean (net) | 95% CI | median | win | lost >90% |
|---|---|---|---|---|---|---|
| buy +1 min, sell +15 min | 631 | -27.9% | [-37%, -18%] | -74.2% | 26% | 37% |
| buy +1 min, sell +1h | 631 | **-55.1%** | [-67%, -42%] | -96.9% | 10% | 62% |
| buy +1 min, sell +6h | 528 | **-80.0%** | [-88%, -70%] | -100% | 3% | 76% |
| buy +15 min, sell +1h | 631 | -27.6% | [-35%, -19%] | -14.1% | 10% | 25% |
| buy +15 min, sell +6h | 528 | -43.5% | [-48%, -39%] | -37.0% | 8% | 32% |
| **wait for proof**: still above graduation price at +1h, then hold 6h | 56 of 631 | **-62.8%** | [-79%, -44%] | -100% | 16% | 55% |

The only row whose interval reaches zero is buy +15 min / sell +15 min (-6.8%, [-17%, +8%]).

**A bug that nearly reversed the headline.** The glitch flag was computed but never
applied. The column is object dtype (True/False/NaN), and `~` on Python bools gives -1/-2,
both truthy, so the filter kept everything. Worse, the edit that was meant to apply it had
silently failed to patch the file. With the 61 glitches still in, two 1h rows showed
**positive** means (+10.3%, +17.9%). This is the same `~`-on-object-dtype slip that
bull_boost.py hit on the same day. Any boolean column read back from a DataFrame of mixed
rows needs `.astype(bool)` before it is negated.

**What the price paths show.** A typical coin graduates at ~$50k, spikes to $75-110k within
five minutes as snipers buy, and is worth ~$2,400 by minute fifteen. The insiders who
bundled the launch sell everything into the first buyers. Only **9%** of graduates are
still above their graduation price an hour later, and even those lose 63% over the next six
hours. The spike in the first minutes is real, but trading it means being inside the
graduation block itself, which is a sub-second race among professional snipers that a home
setup cannot enter.

**Limits:** this is one day. `meme_collector.py` (data only, no wallet) now records every
graduation as it happens and fetches each coin's first week once it is 7 days old, so
day- and week-long holds can be measured forward. Nothing in the first read suggests
waiting will rescue it: the hold that waited for proof was the worst row.

---

## Dead: copying the best Hyperliquid traders (2026-09-22) — `backtest/hl_copy.py`

Hyperliquid publishes every account's PnL history. "Copy the top wallets" only works if
last period's winners keep winning, so this tests that precondition on the wallets' **own**
returns. Copying can only do worse: lag, slippage and sizing.

**Sample:** 3,000 random accounts from the 40,078 on the public leaderboard that traded at
least $1M lifetime. The leaderboard still lists blown-up accounts (16,308 of its 46,621 are
worth under $10), so losers are in it. At each month-end, accounts worth at least $10k are
ranked by return over the prior 90 days, then measured over the next 30. That gives 27
months, with 58 to 767 accounts each.

| next-month return, top decile vs everyone | months | mean difference | median vs median | rank correlation |
|---|---|---|---|---|
| all months | 27 | -2.98% (t -0.45) | -4.86% (t -1.10) | +0.044 |
| excluding the HYPE airdrop months (Sep-Dec 2024) | 23 | +2.55% (t +0.75) | -3.65% (t -1.24) | +0.069 |
| 2025-2026 only | 18 | +1.04% (t +0.24) | **-5.79%** (t -1.62) | +0.074 |

**No persistence.** The correlation between one quarter's ranking and the next month's
result is about +0.05. The **typical** top-decile trader does *worse* than the typical
trader the following month (-4% to -6% median vs median). The occasional positive mean
comes from a few outliers; in 2025-09 the top decile averaged +49% while its median lost
40%. Last quarter's leaderboard is mostly luck and leverage, and luck does not persist.
Copying it adds costs to a signal that is not there.

---

## Answered: betting more in bull markets (2026-09-22) — `backtest/bull_boost.py`

The idea: keep the x0.25 bear gate, and raise long risk *above* 1x while BTC is above its
average. The control is raising risk uniformly in every regime. A bull-only boost is worth
something only if it buys more return per point of drawdown than simply betting more.

Every row also reports the account's **gross leverage** through time, built from each
position's actual stop distance and the bar each pyramid unit was added.

| 1000h gate (deployed) | tune /mo | DD | holdout /mo | DD | worst month | gross leverage p99 |
|---|---|---|---|---|---|---|
| **deployed (bull x1)** | +22.87% | 54% | **+11.63%** | 64% | -42.9% | **8.7x** |
| bull x1.25 | +27.06% | 66% | +13.74% | 70% | -54.3% | 10.9x |
| bull x1.5 | +30.77% | 75% | +15.51% | 76% | -65.8% | 13.0x |
| bull x2 | +36.97% | 87% | +18.09% | 84% | -88.7% | 17.2x |
| *uniform x1.25* | +28.14% | 64% | +13.62% | 72% | -53.6% | 10.9x |
| *uniform x1.5* | +32.93% | 72% | +15.21% | 79% | -64.3% | 13.1x |
| *uniform x2* | +41.22% | 84% | +17.32% | 88% | -85.8% | 17.5x |

**Three findings:**

1. **The regime condition adds nothing.** Bull-only and uniform boosts land in the same place:
   slightly better on the holdout, slightly worse on the tune half. It is "bet more" with an
   extra step.
2. **Any boost breaks the leverage ceiling.** The deployed book already reaches **8.7x gross
   at the 99th percentile** (9.6x at peak). x1.25 takes it to 10.9x, and x2 to 17x. This is
   not tradable at the 10x setting, and `lev_test.py` showed liquidation turns destructive
   above 10x.
3. **The tail grows fast.** In a block bootstrap, the chance of an 80% drawdown within three
   years is **0.9% deployed, 11% at x1.5, and 35% at x2**.

**What this also uncovered: the research backtests used a different gate from the one
deployed.** `blend.btc_bear()` uses a 200h average. The live bots have used 1000h since
2026-09-14. On the 1000h gate the deployed config's holdout is **+11.63%/mo at 64% DD**,
against **+9.07% at 77%** on the 200h gate that escalate, bear_date, bear_side and tradfi
all used. The deployed book is better than those files reported. However, 1000h was
chosen by a sweep that included this holdout period, so treat +11.63% as optimistic and
+9.07% as the conservative figure. Relative comparisons within any one file are unaffected.

**The deployed sizing is at the ceiling already.** Returns grow only through more capital or
a better edge. Leverage and risk have no room left.

---

## PROMISING: tighten the alts' trails when BTC's own trend breaks (2026-09-22) — `backtest/btc_exit.py`

The first exit change in this project that does not lose. It came from asking whether
BTC reversal patterns could protect the whole alt book.

**The reversal patterns predict nothing.** After each BTC signal switches on, BTC's next 7
days average about the same as any week (+0.96%):

| signal | BTC next 7d after switch-on |
|---|---|
| below 1000h average | -0.30% |
| 5% / 8% / 12% below 7-day high | -0.09% / +1.56% / **+2.01%** (a bounce) |
| 4h trail break, 3 / 5 ATR | -0.01% / -0.18% |
| **bearish RSI divergence** | **+0.93%**, which is noise |
| EMA20 < EMA50 | +0.07% |

**Closing every alt long on a BTC signal loses** in 8 of 8 signals, as predicted. The
registered primary (regime flip + close) made +15,474R against +19,113R. The cause is the
same re-entry drag that killed eleven exit rules.

**Tightening instead of closing** means switching open longs from the 20xATR trail to 5xATR
(or 3x) once BTC's signal fires. That cuts drawdown without losing profit. Each setting was
run over 5 random tie-break orders. The **order in which simultaneous entries are taken
moves the deployed book's holdout between +4.2% and +11.4%/mo**, so single-run
differences under ~3%/mo are noise.

| mean of 5 orderings | long R | tune /mo | DD | holdout /mo | DD | worst month |
|---|---|---|---|---|---|---|
| **deployed** | +19,113 | +20.11% | 58% | +8.74% | 61% | -37.2% |
| BTC 4h trail5, tighten 5x | +23,742 | +17.27% | **36%** | +11.42% | 56% | **-21.4%** |
| BTC 4h EMA20/50, tighten 5x | +22,086 | +15.21% | **40%** | +11.96% | **39%** | **-22.9%** |
| BTC 4h trail3, tighten 5x | +19,452 | +12.87% | **34%** | +15.98% | **37%** | **-23.3%** |

**In the neighbourhood** (22 settings: BTC trail 4-8 ATR on 4h/12h, EMA pairs, tighten to
3-10 ATR), **drawdown falls in nearly every setting** (tune DD 32-55% against 58%) and total
long R is at or above deployed in most. The best region is a BTC 4h trail of 4-5 ATR,
tightening to 3x: +25,233R to +28,871R, tune DD 32-34%, worst month about -20%. Monthly
*returns* are split: lower on the tune half, higher on the holdout.

**By year, it trades the biggest bull years for the choppy ones:**

| year | deployed | trail5 tighten | EMA tighten |
|---|---|---|---|
| 2021 | +1,267% | +766% | +559% |
| 2022 | **-34%** | **+7%** | **+12%** |
| 2023 | +342% | **+816%** | +561% |
| 2024 | +1,133% | +955% | +885% |
| 2026 | +91% | +153% | +181% |

(sum of R x risk, not compounded)

**Why it works where eleven exit rules failed:** those keyed on the position's own R, where
a runner and a reversal look identical. BTC's trend state is information from *outside* the
position, which is the one thing `giveback.py` said could break the tie. It does not
predict tops, as the first table shows. It separates trending markets, where the 20x trail
should stay wide, from choppy ones, where the wide trail just gives profit back.

**Before shipping:** this was selected from 24 first-pass variants, then checked across a
neighbourhood. That is strong evidence of a real drawdown effect and weak evidence of a
return effect. It should run forward beside the deployed rules before it replaces them.

---

## Dead: collecting funding spikes on small perps (2026-09-22) — `backtest/funding_spikes.py`

The average funding rate died in `cash_carry.py`. This tested the fat tail instead: when a
small coin's funding runs at 0.1-2% per settlement, collect it with price hedged. The data
covers 477 perps that had Binance spot and 2,068,799 settlements. Costs are 0.30% for four
taker legs, entering after the settlement that revealed the spike.

**Positive spikes (short the perp, hold spot): the ceiling was a 2021 phenomenon.** Mean net
per event, before any basis risk, entering at >= 0.20% per 8h:

| 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| +0.45% | **+1.82%** (788 events) | ~0 (3) | ~0 (4) | +0.08% | +0.26% | +0.10% |

Since 2022 even the best case, with no price risk at all, barely clears fees. The median
event loses.

**Negative spikes: the fully hedged version is large and growing** (<= -0.50% per 8h: 976
events in 2025 at +2.89% mean, 1,123 in 2026 at +3.11%). **But it cannot be built.**
Collecting negative funding means long perp and short spot, which requires borrowing the
coin. The funding is negative precisely because the coin cannot be borrowed and shorted
anywhere else. The unhedged version, long the perp only, is what can actually be traded:

| long the perp while funding <= -0.50%/8h | n | funding | price | **net** | median | win |
|---|---|---|---|---|---|---|
| 2025 | 970 | +3.21% | -2.03% | +1.08% | -1.84% | 39% |
| 2026 | 1,123 | +3.41% | -4.12% | **-0.81%** | -3.35% | 33% |
| all | 2,818 | +3.05% | -3.26% | **-0.31%** | -2.72% | 36% |

**The price falls by about what the funding pays.** Shorts pay for the right to short a
falling coin, and the market sets that price close to the expected fall. This is the third
time in two days that funding has absorbed an apparent edge, after the Upbit fade (-4.5%)
and new-listing shorts. **Funding is where the market prices what everyone can already see.**

---

## Dead: ranking which signal gets the last slot (2026-09-22) — `backtest/slot_priority.py`

The slots bind constantly: 1,093 moments had more simultaneous signals than free slots,
involving 3,865 signals, and the paper bot has declined 462 signals against 47 taken.
Random tie-breaking alone moves the deployed holdout between +5.1% and +10.4%/mo. So
*which* trade takes the slot matters a lot, and choosing it better would add return with
no added risk.

Five features known at entry were each ranked in both directions: timeframe, 30-day
momentum, ATR%, breakout strength, and volume surge. In the portfolio run two looked
consistent, momentum HIGH-first (+22.6% / +11.1% against random's +19.5% / +8.9%) and
breakout LOW-first. Both sat inside the random band's range.

**The head-to-head test says the portfolio result was path noise.** It asks, at every
moment with two or more simultaneous signals (3,230 of them), whether the signals ranked
higher on the feature earned more R than those ranked lower. R is capped at -25/+100 so
one runner cannot decide it, and t comes from a month-block bootstrap:

| feature | high minus low | t | tune | holdout |
|---|---|---|---|---|
| 30d momentum | **-0.201R** | -1.28 | -0.20R | -0.20R |
| breakout strength | -0.049R | -0.34 | -0.05R | -0.05R |
| ATR% | +0.044R | +0.27 | +0.03R | +0.07R |
| volume surge | -0.240R | -1.66 | -0.09R | -0.45R (t -2.12) |
| timeframe | +0.120R | +0.11 | +0.39R | -0.39R |

**Higher-momentum signals earn slightly *less*.** The portfolio gain did not come from
picking better trades. It came from knock-on effects on which slots were free later.
Nothing known at entry says which of two simultaneous signals will run.

**What this means for reading any result:** the ±3-5%/mo spread from slot order is pure
luck and cannot be steered. It sits inside every backtest figure in this document and
inside the live paper account.

---

## PROMISING: the runner is predictable AT ENTRY, and it sizes (2026-09-22) — `backtest/entry_runner.py`

`runner_id.py` found a feature (`atr_ratio`) that separates runners, but only *after* a
trade crossed +20R, and using it to exit lost money. This asks the untested question: at
**entry**, before a slot is committed, can we rank signals by their chance of becoming a
big runner (peak >= 50R)? 5,628 long positions, features from bars closed at/before entry,
a logistic model fit on the first 60% of history and scored only on the last 40%.

**The runner is genuinely predictable out-of-sample:**

| | holdout AUC |
|---|---|
| full model (8 features) | **0.675** |
| position-only model (drop the two BTC/regime features) | **0.591** |
| best single feature: `ext_ma` (price / 200-bar mean) | 0.607 |
| `atr_expand` (ATR / its 60-bar average) | 0.596 |

The model's **top decile of holdout signals runs at 10.7% (mean +10.77R); its bottom decile
at 1.8% (mean -2.09R)**, against a 5.2% / +1.03R base. Extended coins with expanding
volatility become runners more often — the trend-persistence premise, now measured at entry.

**It does NOT help slot priority.** The prediction is cross-time (regime + trend state), not
cross-sectional. Within a contested moment, where all signals share one regime, the AUC is
0.383 (n=39) — no power to rank simultaneous signals. Using it to pick contested slots cost
-0.69%/mo. This is why `slot_priority.py` found nothing: the pick is between signals that
look alike.

**Where it pays is SIZING.** Scale each position's risk by its runner-rank, mean held
constant, so it is not simply betting more. Against a uniform bet **at the same drawdown**
(the control `bull_boost.py` demands):

| scheme (holdout) | /mo | DD | uniform at same DD | edge |
|---|---|---|---|---|
| deployed (flat) | +10.51% | 64% | - | - |
| size by full model, ±90% | +16.64% | 75% | +12.59% | **+4.04%** |
| size by position-only, ±50% | +12.30% | **65%** | +10.75% | **+1.55%** |
| size by position-only, ±90% | +12.98% | 67% | +11.07% | **+1.91%** |

The position-only rows are the honest ones — they cannot be regime-timing, and they add
**+1.5 to +2%/mo at essentially the deployed drawdown**. The full-model edge is larger but
leans on the market-regime features, which the gate already partly captures.

**Why this is PROMISING, not shipped:**
- It is one holdout period. The AUC is the solid part; the +1.5-2%/mo sizing edge is a
  second-order quantity and more fragile.
- Sizing scales positions linearly here. It does **not** re-check the MEXC min-order floor
  (smaller positions may be rejected at $221) or slippage. At $221 the floor already binds;
  this is cleanest on a larger account.
- `coin_90` carries a negative coefficient (90-day winners run less) while `ext_ma` is
  positive — momentum and mean-reversion partly fighting. The OOS AUC survives it, but it is
  a sign the model is near its data's limit; keep it small (few features, strong
  regularisation).

**Next step:** a third paper book that sizes by the position-only model, beside the main and
tight books, so the sizing edge is validated forward and the min-order interaction is seen
live. This is the first entry-time predictive signal found in the project.

### The two edges STACK, via drawdown -> leverage capacity (2026-09-22) — `backtest/runner_leverage.py`

Asked whether the edge is worth more, four levers were tested on the proper non-overlapping
book (5,628 deployed longs), every figure averaged over 5 random slot-orderings because
that ordering alone swings a single run by several %/mo:

1. **Stronger model:** gradient boosting lifts holdout AUC to **0.614** (logistic 0.591).
   Modest.
2. **Harder sizing:** dropping the bottom 20% of runner-probability and tilting the rest
   +-90% beats a uniform bet **at the same drawdown by +3.3%/mo** (vs +2.9% for a plain
   linear tilt). The bottom decile really is dead money.
3. **Sizing and the tight exit COMPETE, they do not add.** On the tight-exit book the sizing
   edge shrinks to +1.3-1.5%/mo, because the tight trail clips the very runners sizing loads
   onto.
4. **But the tight exit's real gift is drawdown, and drawdown is leverage capacity.** This is
   what I had missed. The tight exit cuts drawdown (52% vs 59% flat) and the worst month far
   more (-17.5% vs -38.2%). A lower-drawdown book can safely carry more risk:

| holdout, 5 orderings averaged | /mo | drawdown | worst month |
|---|---|---|---|
| **today's book** (deployed exit, flat) | +8.86% | 59% | -38.2% |
| tight exit, flat, **levered x1.20** to 59% DD | +13.03% | 59% | -21.0% |
| tight exit + convex sizing, **levered x1.15** to 59% DD | **+15.14%** | 59% | **-22.4%** |

**At the same drawdown, the combination earns about +6%/mo more than today, with a worst
month roughly half as deep.** The gain is not from betting blindly more (that was
`bull_boost.py`, dead); it is from spending the drawdown the tight exit frees up.

**Three hard caveats, so this is a lead and not a promise:**
- **One holdout period.** The tight exit itself is still awaiting forward confirmation
  (`btc_exit.py`), and the +6%/mo is a single draw of history stacked on a model tuned on
  the other 60%.
- **The leverage ceiling binds.** The book already runs ~8.7x gross at the 99th percentile
  (`bull_boost.py`); x1.15-1.20 pushes it near 10x, where `lev_test.py` showed liquidations
  start to bite. The extra risk may not be executable in full, which would shrink the +6%.
- **Min-order floor and slippage are not re-checked**, and at $221 the floor already binds.

**Disposition:** validate the pieces at 1x first (no extra leverage) - the tight exit is
already live on paper, and the runner-sizing book is the next to add. The leverage-up is a
decision for after both hold forward, and only once the gross-leverage interaction is
measured on real stop fractions.

---

## Five engine stones turned (2026-09-23) — `backtest/engine_variants.py`, `variant_leverage.py`, `vol_target.py`

Everything outside the engine was already tested, so this batch attacked the untested choices
INSIDE it. Every figure is averaged over 5 random orderings of simultaneous entries, because
that ordering alone swings a run by 3-5%/mo. Deployed baseline: **tune +19.29%/mo at 55% DD,
holdout +8.44%/mo at 57% DD, worst month -33.9%, gross leverage 8.7x at the 99th percentile.**

### 1. RETRACTED the same day: pyramid adds on pullbacks

The idea: units 2-5 are filled at fixed +2R breakout levels - bought HIGH, which is exactly
where the -20R breakeven loss comes from. Fill them on a pullback instead. It looked like the
best result in the project:

| pullback 0.25xATR + tight exit | tune | holdout | DD | worst |
|---|---|---|---|---|
| **as first measured (WRONG)** | +19.4% | **+17.4%** | 47% | -19.7% |
| **strictly causal (right)** | +12.6% | +9.3% | 64% | -25.7% |
| deployed | +19.3% | +8.4% | 57% | -33.9% |

It survived a plateau check (0.1 to 1.0 all beat base, peaking at an INTERIOR 0.25) and a
leverage check. It died on causality. **The add was armed by a bar's HIGH and filled at that
same bar's LOW**, which assumes the high came first - intrabar look-ahead, the same class of
bug as the entry-bar stop check in doc 03. Requiring the fill to wait for the next bar cut
the 1x holdout from +15.4% to +4.2%, dropped gross leverage from 8.5x to 4.3x (most adds
never fill at all), and left it **worse than deployed on the tune half and tied on the
holdout**. Dead.

> **A plateau and an interior optimum are not evidence of realism.** Both held here while the
> result was an artifact. Only the causality check found it.

### 2. New sleeves: no winner

Slots stay at 12, so extra sleeves mostly add declines. Holdout /mo: base (1h+4h+12h) +8.44%;
+8h **+10.33%** but tune falls to +16.12%; +1d +4.91%; +2h +9.00% at 72% tune DD; 12h+1d alone
-1.15%. Nothing clears "better on both halves by >2%/mo". Adding a daily sleeve actively hurts.

### 3. Multi-timeframe alignment: dead

Taking 1h/4h entries only when the coin's 12h sleeve is also above its band cuts 5,628 longs
to 2,006 and the holdout to +4.41%. Filter number N, same grave.

### 4. Volatility targeting: dead, and instructively so

Scaling risk by (target / realised vol of the book's own daily P&L), the standard
managed-futures lever, is **worse on both halves AND has higher drawdown** (14d: +2.69%
holdout at 69% DD; 30d: +3.46% at 75%; 60d: +9.24% at 78%; base 57%). The mechanism is
visible in hindsight: **this book's volatility is lowest just before trends start and highest
during them**, so inverse-vol sizing bets big into the quiet stretches that precede reversals
and small during the moves that pay.

### 5. A modest, executable lead: shorts sized up while BTC's 4h trail is broken

`short_families.py` showed no short ENTRY signal beats random and the regime is the whole
edge; `btc_exit.py` validated BTC's 4h trail break as a market-weakness signal. Untested until
now: use it to size the short sleeve.

| shorts x M on break | tune | holdout | DD | worst | gross (p99 / max) |
|---|---|---|---|---|---|
| x1 (deployed) | +19.29% | +8.44% | 57% | -33.9% | 8.7x / 9.6x |
| **x5** | +19.61% | +9.78% | 49% | -31.7% | 8.7x / <10x |
| **x8** | **+19.83%** | **+10.76%** | **47%** | **-30.5%** | 8.7x / <10x |
| x12 | +20.11% | +12.01% | 44% | -29.8% | 9.1x / 10.5x |
| x20 | +20.58% | +14.38% | 43% | -29.8% | 9.2x / **17.3x** |

Better on both halves, lower drawdown and a better worst month - and it is **monotone with no
turnover**, which by this project's own rule means the grid boundary, not an optimum. Two
things bound it:

- **Leverage.** Shorts are rare and short-lived, so p99 gross barely moves, but MAX gross
  breaks 10x by x12. **x5-x8 is the executable range.**
- **It rests on few trades.** Only **224 of 10,108 shorts (2.2%)** are entered while the break
  is on, 100 of them in the holdout. Their mean is **+0.481R against +0.043R** for all other
  shorts - a 9x better selection across **84 independent break episodes**.

**Significance, month-block bootstrapped:** +0.439R pooled (**t +2.10**), +0.313R on the tune
half (t +1.10), +0.592R on the holdout (t +1.98). Positive in both halves, neither
individually significant. Encouragingly it is a whole-distribution shift, not one outlier:
**win rate 41% vs 32%, median -0.419R vs -0.963R.**

**Disposition:** a real-looking but modest lead (+2.3%/mo holdout at x8, drawdown 57% -> 47%),
mechanism understood, executable, and using a signal already validated elsewhere. It belongs
in the forward test, not in a conclusion.

---

## Dead, and it reverses an old result: BREADTH does not scale (2026-09-23) — `backtest/wide_book.py`

`cheap_wide.py` measured that return scales with breadth (3 coins +1.9%/mo, 9 coins
+10.7%/mo) and the deployed book then took TWELVE coins, chosen for minimum-order
affordability. With `perp_fetch.py`'s 855 perps (339 dead) the honest version is finally
testable: same 12 slots, same engine, same perp price data, but signals drawn from a
point-in-time top-N universe where dead coins are present while they lived.

| universe, 12 slots | trades | coins | tune /mo | DD | holdout /mo | DD |
|---|---|---|---|---|---|---|
| **12 deployed coins** | 10,601 | 11 | **+13.08%** | 66% | **+6.56%** | 63% |
| PIT top-30 | 40,939 | 283 | +5.32% | 78% | -0.09% | 68% |
| PIT top-60 | 79,598 | 469 | +6.26% | 79% | -0.13% | 76% |
| PIT top-100 | 128,146 | 588 | +5.28% | 77% | +0.75% | 64% |

**Wider is drastically worse**, and more slots only buys drawdown: top-100 at 30 slots gives
+16.38% tune at **93% DD** and +0.24% on the holdout.

**Why the old result reversed:** breadth was measured on coins that exist TODAY. In a
survivorship-free universe the extra names are mostly things that pumped once and died -
their breakouts chop and bleed, and they consume the slots. Two readings, both worth holding:
the twelve are "cheap but REPUTABLE" and that quality filter is doing real work; and part of
their edge is knowing in 2026 which coins stayed reputable, which is the same hindsight
premium `pit_universe.py` already priced at 3x. Either way, **trading more coins is not the
lever.**

## The best book assemblable from what survived (2026-09-23) — `backtest/composite.py`

Three changes are on paper. They touch different parts of the book - long exits, short
sizing, long sizing - so they should be near-independent. Measured together, seed-averaged
over 5 orderings, on the `engine_variants` path where stop fractions and add times are real
so gross leverage can be checked:

| book, 1x risk | tune | DD | holdout | DD | worst month | gross p99 / max |
|---|---|---|---|---|---|---|
| deployed | **+19.29%** | 55% | +8.44% | 57% | -33.9% | 8.7x / 9.6x |
| tight exit | +16.08% | 37% | +12.73% | 54% | -20.9% | 9.1x / 10.0x |
| **tight + short boost x5** (what is on paper) | +16.49% | 39% | **+14.49%** | 48% | **-21.0%** | 9.3x / 10.0x |
| tight + short boost x8 | +16.78% | 39% | **+15.72%** | 42% | -21.0% | 9.3x / 10.0x |

**Two of the three stack; the third adds nothing.** On the `composite.py` path, ALL THREE
(+15.09% holdout at 43% DD) is no better than tight + short boost alone (+13.65% at 38% DD)
once leverage headroom is accounted for - runner sizing raises drawdown enough to cost the
leverage it would otherwise buy.

**What it is worth, honestly:**
- **Holdout return roughly doubles** (+14.5% vs +8.4%) with drawdown 48% vs 57% and a worst
  month -21% vs -34%. Executable as-is: no extra leverage is used.
- **It costs tune-half return** (+16.5% vs +19.3%). The gain is holdout-only, and both
  components' evidence is holdout-favouring - so this may be a statement about 2024-2026
  rather than about the strategy.
- **There is no room to lever it.** Gross max already touches 10x, so the +20%/mo levered
  figures in `composite.py` are not reachable.
- The short-boost half rests on 224 trades, t +2.10 pooled. That fragility carries into the
  composite.

**Both halves of the winning pair are already running on paper** (tight since 2026-09-21,
short boost x5 since 2026-09-23). Nothing to change; the forward test decides it.

---

## Four structural choices, all dead - and one validates the design (2026-09-23) — `backtest/book_structure.py`

Baseline: tune +19.29%/mo at 55% DD, holdout +8.44% at 57%. Bar to clear: better on BOTH
halves by >2%/mo. Seed-averaged over 5 orderings.

| variant | tune | holdout | DD (hold) | worst |
|---|---|---|---|---|
| **max 1 position per coin** | +9.87% | **+2.15%** | **78%** | -40.8% |
| max 2 per coin | +16.43% | +5.73% | 59% | -37.8% |
| trail 30x/20x/12x (wide on fast sleeves) | +21.25% | +9.27% | 64% | -39.4% |
| trail 10x/20x/40x (wide on slow) | +10.46% | +12.78% | 55% | -29.4% |
| risk x1.5/x1.0/x0.5 | +21.85% | +9.78% | 67% | -40.3% |
| risk x2.0/x1.0/x0.25 | +23.89% | +10.43% | **76%** | -48.3% |
| bb(20, 2.0) | +18.20% | +7.49% | 59% | -36.9% |
| bb(50, 1.5) | +21.37% | +7.07% | 71% | -24.3% |
| bb(30, 1.25) | +18.94% | +13.36% | 64% | -36.6% |

**Nothing passes.** Three things worth keeping:

**1. Duplicate coins across sleeves are a FEATURE.** The live book holds NEAR, DOT and LINK
twice each, which looked like wasteful concentration. Capping it to one position per coin
**cut the holdout from +8.44% to +2.15% and raised drawdown to 78%**. When a coin genuinely
trends, all three sleeves fire on it, and holding all three is how the book catches its
biggest winners. Capping duplicates forces the slots into worse coins. `corr_alloc.py` capped
by cluster and `slot_split.py` by side; both also failed. **Every attempt to make this book
more diversified has lost money.**

**2. Per-sleeve risk weights are just leverage.** Tilting risk toward the 1h sleeve raises
return and drawdown together (x2.0/x1.0/x0.25: +23.89% tune but 68/76% DD) - the `bull_boost.py`
pattern again, not an edge.

**3. The recurring shape of every near-miss.** Widening the slow sleeve's trail, and loosening
the entry band, both **help the holdout and hurt the tune half** (10x/20x/40x: +12.78% holdout
vs +10.46% tune; bb(30,1.25): +13.36% vs +18.94%). That is the same asymmetry the tight exit
and the short boost show. Either 2024-2026 genuinely rewards slower, looser trend capture, or
these variants are all fitting the same recent regime. **Treat any holdout-only improvement in
this project as regime-dependent until it survives forward.**

---

## The last three dimensions, and an admission about the holdout (2026-09-23) — `backtest/final_variants.py`

Baseline: tune +19.29%/mo at 55% DD, holdout +8.44% at 57%, worst -33.9%.

| variant | tune | holdout | DD | worst |
|---|---|---|---|---|
| stop 1xATR | +24.02% | +9.67% | **91%** | -57.9% |
| stop 1.5xATR | +19.22% | +7.61% | 81% | -48.1% |
| stop 3xATR | +11.16% | +2.60% | 45% | -26.2% |
| stop 4xATR | +5.00% | +1.49% | 21% | -14.5% |
| time stop: below 0R after 100 bars | +20.15% | +9.30% | 54% | -29.4% |
| **time stop: below 2R after 100 bars** | +17.38% | **+12.90%** | 49% | **-22.4%** |
| entry limit 0.25xATR below the signal close | +13.97% | +5.16% | 61% | -29.8% |
| entry limit 1xATR below | +18.61% | +2.03% | 67% | -32.1% |

**The 2xATR stop is well chosen.** Tighter earns more on both halves and is unusable (91%
drawdown); wider is safe and weak. The deployed value sits at the sensible middle of a steep
trade-off, which is what a well-set parameter looks like.

**Entry on a pullback is dead even done causally** - which is the confirmation the retracted
ADD version needed. The limit is placed from the signal bar's close and can only fill on a
LATER bar, so no intrabar ordering is assumed, and every setting loses on both halves. Waiting
for a dip misses the signals that never look back, and those are the ones that pay.

### The admission: this holdout is no longer a clean test

Count the modifications that came out "helps the holdout, costs the tune half":

| change | tune vs base | holdout vs base |
|---|---|---|
| BTC-break tight exit | -3.2 | **+4.3** |
| short boost x5-x8 | -2.8 | **+6.1** |
| trail 10x/20x/40x | -8.8 | **+4.3** |
| entry band bb(30, 1.25) | -0.4 | **+4.9** |
| time stop below 2R after 100 bars | -1.9 | **+4.5** |
| runner sizing (position-only) | +4.7 | **+2.4** |

Six independent knobs all point the same way. There are two readings and they are not
mutually exclusive:

1. **Real:** 2024-2026 rewards slower, looser, more protective trend capture than 2020-2024
   did, and every knob that moves in that direction helps.
2. **Overfitting by repetition:** dozens of variants have now been scored against this ONE
   holdout in a single day. Selecting the ones that improved it is exactly how a holdout stops
   being out-of-sample, no matter that each individual test was clean.

**Both readings demand the same thing: stop mining this split.** No further variant should be
adopted on the strength of this holdout. The tight exit and the short boost are already
running on paper against data that did not exist when they were fitted, and that forward
record - not another backtest - is what decides them.

---

## SETTLED: the minimum order is not the binding constraint (2026-09-23) — `backtest/small_capital.py`

`blend.run` reported an implied capital "floor" from the widest stop and the largest minimum
order, but no test ever SIMULATED the rejections. That matters because the effect compounds:
a small account skips signals whose unit is below the venue minimum, which changes what it
holds, which changes how fast it grows, which changes what it can next afford.

**Two honesty fixes this file needed:**
- **The minimum is a COIN count, not a dollar amount.** MEXC's minimum is one contract, so its
  dollar value tracked the coin's price. NEAR's minimum was $1.21 in 2020 and is $2.28 now;
  ENA's was **$6.15** at its 2024 listing and is $1.39 now. The step is recovered in coin units
  and re-priced at every trade.
- **Equity may only advance from trades that have already CLOSED.** The first version of this
  file compounded in entry order and read 85% drawdowns where the same book measures 56% -
  mistake #6 again, caught by that discrepancy. A second bug let a **98% drawdown** config be
  chosen as "best" because the ruin test only fired at a 99% loss.

**Result: percentage returns are flat from about $15 to $5,000.**

| starting capital | signals skipped for size | holdout /mo | DD |
|---|---|---|---|
| $10 | **18%** | +14.33% | 62% |
| $15 | 11% | +13.18% | 56% |
| $25 | 9% | +10.97% | 56% |
| $50 | 4% | +12.19% | 56% |
| $100 | 1% | +12.45% | 56% |
| $221 (deployed) | **0%** | +10.32% | 56% |
| $5,000 | 0% | +10.30% | 56% |

**At $221 the minimum order rejects nothing at all.** At $100 it costs 1% of signals, at $25
9%, and only below ~$15 does it bite (18%).

**Do not read the tiny accounts as better.** The spread from +10.3% to +14.3% sits inside the
+-3%/mo ordering noise, and the mechanism is mechanical: a unit's notional is equity x risk /
stop fraction, so rejections fall hardest on WIDE-stop trades, i.e. the 12h sleeve and the
high-volatility coins. Skipping those is the same mild tilt `book_structure.py` measured when
weighting away from 12h. It is not an edge, and $10 pays for it with a 62% drawdown.

**Also retired:** "the best configuration for a small account". Sweeping risk and slots per
capital just cranks risk to whatever drawdown limit is imposed (0.50%/12 slots at a **76%**
drawdown). Higher risk does genuinely reduce rejections - a real small-capital mechanism, since
a bigger unit clears the minimum - but the drawdown cost dominates it. **No special
small-account configuration is needed; the deployed 0.30%/12-slot book works unchanged from
about $15 up.**

**What the dollars imply, with the warning that matters more than the number.** Over the
24-month holdout at the haircut rate, $221 implies about **$2,400** and $100 about **$1,700**.
The simulation's own raw endings are 6x those, which is what the 3x hindsight haircut and
coin-selection bias exist to discount. And per the admission above, **this holdout has been
scored by dozens of variants in one day, so it is no longer a clean test.** The only unbiased
evidence in this project is the four paper books, now running against prices that did not
exist when any of this was fitted.

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

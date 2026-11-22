# The graveyard


> **One category was REOPENED on 2026-09-23 and is no longer in this graveyard.**
> Market-neutral cross-sectional momentum was filed here as "genuine and too small"
> (Sharpe 0.62) on a narrow universe. Re-tested on the point-in-time, survivorship-free
> universe with real funding and measured turnover it reads Sharpe 1.16 and correlates
> **+0.09** with the deployed book — see [doc 10](10-market-neutral.md). The kill was
> legitimate for what was tested; the universe was what changed. Its bear-market
> performance turns out to be **funding carry, not prediction** — the momentum spread's
> gross return is negative in bears in every variant.

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

## RETRACTED: most of the short boost was look-ahead (2026-09-23) — `backtest/causal_t0.py`

Found while adding funding to the engine. Every engine row carries `t0` = the **label** of its
entry bar. For the 1h sleeve that is the real entry time. For the resampled sleeves it is not:
`timeframes.resample()` labels a bar by its right edge, so a 4h bar labelled L opens at L−3h,
and `signals()` enters at the bar's open. **4h rows are stamped 3 hours after their real entry,
12h rows 11 hours after.**

`vol_target.short_boost()` and `composite.rowset()` tag a short as boosted with
`btc_trail(5).asof(t0)`. On a 4h/12h row that returns a BTC bar that **closed after the short
was opened**: the flag is on *because* BTC broke down during the trade.

| shorts tagged "boosted" | n | mean R | others |
|---|---|---|---|
| as measured (flag at label t0) | 224 | **+0.481R** | +0.043R |
| causal (flag known at real entry) | 298 | **+0.305R** | +0.045R |
| tagged only because of the look-ahead | 118 | +0.766R | |

On the 4h and 12h sleeves the two tag sets share **zero** trades. The real effect exists: at
+0.305R against +0.045R, boosted shorts still do about 7× better per trade. What doesn't
survive is its value to the book. Re-scored over 20 paired orderings
(`backtest/honest_rescore.py`, causal t0, funding charged):

| vs main book | tune /mo | holdout /mo |
|---|---|---|
| short boost x5, as previously reported (`composite.py`) | +0.3 | **+1.3** (x8: +2.3) |
| **short boost x5, causal** | **−0.10 ± 0.01** | **+0.46 ± 0.04** |

**The short boost is worth about +0.5%/mo on the holdout and nothing on the tune half.** The
`sboost` paper book should track `main` closely; do not read that as the market refuting it.
The live code (`blend_paper.trig_at`) was always causal, since a live bot can't see the future.
Only the backtest estimate was inflated.

The **tight exit's** alignment (`engine_variants.break_map`) was checked and is causal. The
regime gate and the slot order also read the late `t0`, which is why the corrected *main* book
moves too (tune +19.29% → +16.48%, holdout +8.44% → +10.47%, fees only). That movement is
mostly slot-order reshuffling, which is inside the ±3–5%/mo ordering noise.

> **The trap:** a bar's label is not its entry time. Any `asof(t0)` on a resampled row reads
> the future by up to one bar. Use `causal_t0.real_t0(rows)` before gating, ordering or
> tagging anything by time.

---

## MEASURED for the first time: funding costs 21% of the long book's profit (2026-09-23) — `backtest/funding_cost.py`

No file behind the deployed book (`pyramid.py`, `convex.py`, `blend.py`, `engine_variants.py`,
`bull_boost.py`) ever charged funding. For a book whose whole edge is five-unit pyramids held for
weeks through bull markets, that is not a rounding error. Actual Binance funding, per unit, per
settlement held, real entry times:

| side | sleeve | positions | mean R | funding R | funding as % of R |
|---|---|---|---|---|---|
| long | 1h | 4,098 | +2.532 | −0.328 | **−12.9%** |
| long | 4h | 1,121 | +5.435 | −1.381 | **−25.4%** |
| long | 12h | 409 | +6.467 | −2.982 | **−46.1%** |
| short | all | 10,108 | ≈+0.05 | +0.005 to +0.013 | (received) |

**Longs paid −4,111R against +19,112R of lifetime long profit (21.5%)**, and 2021 alone paid
−2,364R. The worst single position is an ADA 12h pyramid held 466 days through 2021: +1,804R
before funding, −462R of funding. That is plausible, because ADA funding averaged about 39%/yr
that year while the position's notional rose ~50×.

| causal t0, 5 orderings | tune /mo | DD | holdout /mo | DD |
|---|---|---|---|---|
| main, fees only (what every doc reported) | +16.48% | 44% | +10.47% | 50% |
| **main, fees + funding** | **+12.23%** | 47% | **+9.86%** | 51% |

**Registered prediction:** 6–15% of long R, −2 to −4%/mo tune, −1 to −2%/mo holdout. **Worse
than predicted on the share (21.5%) and the tune half (−4.25). Milder on the holdout (−0.61).**

**And the venue the account uses charges more.** Bitget's API serves only ~3 months of funding
(265 settlements from 2026-06-25). Over that window Bitget's mean rate was **higher than
Binance's on all 11 book coins it lists**: 0.37–0.77bp/8h against −0.09–0.59bp. So the cost
above is a **floor** for this account, not an estimate.

**Side effect: cross-exchange funding arbitrage is screened out.** The Bitget−Binance gap on the
book's coins averaged ~0.25bp/8h, about 2.7%/yr gross, against ~22bp for four taker legs.
That's the same service-provision return `cash_carry.py` already measured. Not backtested
further.

---

## UPGRADED: the tight exit now helps BOTH halves (2026-09-23) — `backtest/honest_rescore.py`

Two of the six "helps holdout, costs tune" knobs in the holdout admission above were the short
boost and the tight exit. With causal t0 and funding charged, 20 orderings, each variant
compared with main **on the same ordering**:

| vs main | tune /mo | holdout /mo | tune DD | holdout DD | worst month |
|---|---|---|---|---|---|
| main (absolute) | +11.45% | +8.37% | 49% | 52% | −38.5% |
| **tight** | **+2.15 ± 0.66** | **+2.79 ± 0.74** | 41% | 49% | **−33.5%** |
| short boost x5 | −0.10 ± 0.01 | +0.46 ± 0.04 | 50% | 50% | −38.5% |
| tight + short boost x5 | +1.84 ± 0.65 | +3.29 ± 0.73 | 44% | 49% | −33.5% |

(daily-sum %/mo, so the absolute levels are ~2× achievable; see the compounding section below.
Under entry-sized compounding tight beats main by **+2.9 tune / +2.0 holdout**,
`compounding.py`.)

**The tight exit no longer has the mined-holdout signature.** It helps both halves, and the tune
half gain comes mostly from funding: exiting chop earlier stops paying for positions that were
going nowhere. The ± is **ordering noise only**, not market sampling error, so ~3σ here means
"not an artifact of slot order" and says nothing about whether the market repeats. It was also
selected from 24 variants (`btc_exit.py`). **Still, of everything on paper, it is the one
improvement whose evidence got stronger under correction, not weaker.**

The main book's own spread across 20 orderings: **tune +8.6% to +15.6%, holdout +3.2% to
+12.3%/mo.** Any single-run comparison inside that band is noise.

---

## PROMISING, with a catch: route the 12h sleeve to spot (2026-09-23) — `backtest/funding_routes.py`

A spot long pays no funding. Bitget spot costs 8bp more per round trip than the perp, which is
~0.007R on a 12h unit against ~3R of funding per 12h position.

| causal, funding charged, 5 orderings | tune /mo | holdout /mo | routed notional / equity p99 | max |
|---|---|---|---|---|
| all perp (main) | +12.23% | +9.86% | | |
| **12h longs on spot** | **+13.66%** | +9.95% | **0.64x** | 1.11x |
| 4h + 12h longs on spot | +14.63% | +10.06% | 2.04x | 2.40x |
| all longs on spot (upper bound) | +16.32% | +10.20% | 9.16x | 10.18x |

**Registered prediction right on return (+1.4 tune, +0.1 holdout); wrong on fit.** I predicted
the 12h sleeve's notional would fit in cash (p99 < 0.5x). It doesn't: 0.64x at p99, 1.11x at
peak. So the 12h sleeve can only be spot-routed if **spot holdings count as futures collateral**,
as they do in a unified trading account. Whether Bitget's UTA accepts these 12 coins, and at
what haircut, is unverified. The gain is also regime-shaped: it is large when funding is high
(bull years) and ~0 now. It is a pure cost saving, with no prediction in it, which is why it is
the one item from today worth building if the collateral question comes back yes.

## Dead: tightening the trail when funding goes extreme — same file

The BIS "carry predicts crash risk" idea used as an exit: while the coin's last-3-settlement
funding is above a threshold, open longs trail at 5xATR (the tight book's mechanics).

| | tune /mo | DD | holdout /mo | DD |
|---|---|---|---|---|
| main (funding charged) | +12.23% | 47% | +9.86% | 51% |
| tighten above 0.03%/8h | +7.49% | **61%** | +10.97% | **61%** |
| tighten above 0.05%/8h | +8.45% | 63% | +11.68% | 53% |

**Registered prediction wrong in direction:** I expected it to help the tune half (2021). It
guts it. The 2021 runners paid extreme funding **the whole way up**, so tightening on funding
clipped exactly the positions that made the year. This is exit rule number twelve to die, and
it has the "helps holdout, costs tune" shape again.

---

## Dead: nine entry features from the literature, one pre-registered family (2026-09-23) — `backtest/entry_features.py`

Sources: BIS WP 1087 *Crypto carry* (funding predicts crash risk); Concretum Group *Seasonality
in Bitcoin Intraday Trend Trading* (the "Monday Asia open" trend window, weak US Sunday);
practitioner claims that breakouts on rising open interest are "new money"; stablecoin supply
growth as a liquidity regime signal (DefiLlama); Fear & Greed read contrarian (alternative.me).
Every position the rules would open (15,734), causal t0, funding charged, R capped
[−25, +100], top-minus-bottom tercile, month-block bootstrap. Pass required the predicted
sign on **both** halves and Holm p < 0.05.

| side | feature | predicted | tune | holdout | pooled t | Holm | coins agreeing |
|---|---|---|---|---|---|---|---|
| long | coin funding, last 24h | − | +0.31 | −0.00 | +0.49 | 1.000 | 4/12 |
| long | BTC funding, last 7d | − | −2.12 | +2.33 | −0.32 | 1.000 | 6/12 |
| long | open-interest change, 24h | + | −0.47 | −1.18 | −1.17 | 1.000 | 3/11 |
| long | weekend entry | − | −0.90 | −1.20 | −1.74 | 0.740 | 9/12 |
| long | Monday Asia-open entry | + | −0.90 | −1.04 | −1.45 | 1.000 | 3/12 |
| long | stablecoin supply 30d growth | + | +1.62 | −2.99 | +0.50 | 1.000 | 7/12 |
| long | Fear & Greed | − | −0.00 | +1.89 | +1.26 | 1.000 | 1/12 |
| short | coin funding, last 24h | + | +0.05 | +0.30 | +1.50 | 1.000 | 9/12 |
| short | BTC funding, last 7d | + | +0.02 | +0.37 | +0.58 | 1.000 | 8/12 |

**Nothing passes.** Registered expectation: "at most one passes, most likely coin funding on
longs". That feature is the *wrong sign*: long breakouts on expensive funding do slightly
**better**, which is trend persistence rather than fragility. Open interest is wrong-signed
too, and the Asia-open effect (a finding about BTC intraday trend models) does not carry over to
this book's alt breakouts. Two features keep their sign on both halves without significance:
weekend long entries are weaker (9/12 coins), and shorts do better on high funding (9/12).
Under the rules both are discarded. Neither is strong enough to size on.

These nine features are also the regime variables for any alternative gate. Stablecoin growth,
market funding and Fear & Greed all flip sign between halves at the trade level, so a gate
built on them has nothing to stand on. **Not tested as gates, for that reason.**

---

## Dead: equity-curve trading (2026-09-23) — `backtest/equity_filter.py`

The most common retail "improvement" to a system: halve risk while the book's own
closed-trade equity is below its 30- or 90-day average. Entry-sized compounding (see below),
causal t0, funding charged, 10 orderings.

| | tune /mo | DD | holdout /mo | DD |
|---|---|---|---|---|
| no filter (main, corrected) | +4.88% | 54% | +4.86% | 53% |
| equity < 30d mean → x0.5 | +3.77% | 35% | +2.73% | 37% |
| equity < 90d mean → x0.5 | +4.04% | 37% | +2.89% | 37% |
| *control: every trade x0.7* | +3.99% | 41% | +4.12% | 40% |
| *control: every trade x0.5* | +3.21% | 30% | +3.35% | 30% |

At matched drawdown (~36%) the uniform control reads about +3.6% tune and +3.7% holdout. The
filter ties it on the tune half and trails it by ~1%/mo on the holdout. **It is a slower way of
betting less.** The registered prediction ("worse on both halves") was right about return and
wrong to ignore the drawdown, which is why the control was needed. The mechanism is the one
`vol_target.py` found: this book's losing stretches come just before its trends, so shrinking
after losses leaves it small when the next trend starts.

---

## THE BOOK EARNS ABOUT HALF OF WHAT THE ENGINE REPORTS: the compounding convention (2026-09-23) — `backtest/compounding.py`

Found when `equity_filter.py`'s baseline read +13.50%/mo on the holdout against
`honest_rescore.py`'s +8.37% for the same book: same trades, same slots, same gate, same risk
fraction. The only difference was how P&L becomes equity. The repo uses three conventions:

| convention | used by | what it assumes |
|---|---|---|
| **sequential**: `eq *= 1 + R·f` at each close | `small_capital.simulate` → `expectations.py` → doc 00's planning table; **also `blend_paper.py`'s own paper-book equity** | each closing trade is scaled by the equity at its close |
| **daily sum**: `eq_day *= 1 + Σ R·f` | `bull_boost.evaluate` → `engine_variants`, `composite`, `regime_gate`, most doc tables | the same, within a day |
| **entry-sized**: `eq += R·f·eq_at_entry` | nothing, until now | a position's dollars are fixed when it opens, which is **what the bot does** (`risk_usd = equity × risk` at entry; adds reuse the unit) |

The first two are the same error at different scales. When runner A closes at +200% of equity,
a still-open runner B was sized on the old equity, and its dollars do not grow because A
banked. Scaling B's R by the new equity credits it with a position size it never had. In this
book the whole edge is a few overlapping runners, so the error compounds on itself. One
holdout ordering has five trades closing on 2024-12-09 for +420% of equity summed: sequential
turns that half's ×36 into ×105.

Causal t0, funding charged, 10 orderings:

| book | half | sequential | daily sum | **entry-sized** | DD (entry-sized) |
|---|---|---|---|---|---|
| main | tune | +12.05% | +11.54% | **+4.88%** | 54% |
| main | holdout | +13.50% | +8.83% | **+4.88%** | 53% |
| tight | tune | +16.85% | +14.32% | **+7.75%** | 42% |
| tight | holdout | +19.52% | +11.58% | **+6.86%** | 50% |

(%/mo after the 3× haircut. Un-haircut, entry-sized main is **+10.5%/mo** on both halves and
tight **+15.0% / +13.6%**.)

**Registered prediction right:** entry-sized below daily sum, both far below sequential. What I
did not predict was the size: **about half**, on both halves.

### Can a sizing rule recover it? No — `backtest/mtm_sizing.py`

The obvious lever: size new entries on equity *including* open positions' unrealised P&L,
so new trades grow with the runners.

| book | sizing base | tune /mo | DD | holdout /mo | DD |
|---|---|---|---|---|---|
| main | closed equity (the bot today) | +4.88% | 54% | +4.86% | 53% |
| main | + half of open gains | +4.81% | 56% | +4.91% | 54% |
| main | + all open P&L (MTM) | +4.67% | 62% | +4.92% | 56% |
| tight | closed equity | +7.72% | 42% | +6.84% | 50% |
| tight | + all open P&L (MTM) | +8.26% | 52% | +7.22% | 56% |

**Registered prediction wrong:** I expected MTM to recover 60–80% of the gap. It recovers
almost none and costs 6–10 points of drawdown. The gap was never about the base for NEW
trades. Daily-sum implicitly resizes positions that are **already open**, and no entry-time
rule can reproduce that. Resizing an open runner means buying more of it at today's higher
price, which does not earn R from the original entry. **The daily-sum and sequential figures are
not achievable returns. They are an accounting artifact.**

### What it changes

- **Every %/mo figure from `evaluate()` is roughly 2× the achievable return**, and every figure
  from `small_capital.py` / `expectations.py` more than that. Relative comparisons inside one
  file mostly survive (tight beats main under all three), but no absolute level does.
- **The paper books overstate their own equity.** `blend_paper.py` line ~523 does
  `st["equity"] *= (1 + R * risk_used / 100)` at close, for a position sized at entry. A real
  account at the same R will show less. The fix is to store `risk_usd` at entry and add
  `R × risk_usd` at close. **Not changed here** because it is the live paper process, so the
  user decides. The trade log has enough to rebuild the correct equity after the fact.
- **The planning numbers change.** `backtest/expectations_honest.py`, $200, entry-sized,
  10 orderings, upside haircut 3× and downside raw:

| book | window | median month | months losing | worst month | median 12 mo (raw) | median 12 mo (haircut) | $200 → | DD |
|---|---|---|---|---|---|---|---|---|
| *as documented (sequential, label t0)* | holdout | −1.01% | 60% | −34.3% | +153% | +51% | $302 | 57% |
| **main, corrected** | holdout | −0.49% | 56% | **−41.6%** | **+61%** | **+20%** | **$241** | 54% |
| **tight, corrected** | holdout | −0.50% | 56% | −34.7% | **+128%** | **+43%** | **$285** | 51% |
| main, corrected | full | −0.58% | 55% | −41.6% | +251% | +84% | $367 | 57% |
| tight, corrected | full | −0.01% | 50% | −34.7% | +338% | +113% | $425 | 51% |

**Registered prediction:** 12-month median well under +58% ✓ (+20%); months losing above 57% ✗
(56%, unchanged).

---

## Not measurable here: exchange launchpools (2026-09-23)

Lock BGB (Bitget) or BNB (Binance), or sometimes USDT, and receive newly listed tokens. It is
not a trading strategy, but it answers the mandate directly, because **per-user caps favour
small accounts**. Published figures, none verified: Binance's own count of ~$226 of rewards
per BNB over Jan 2024 – Mar 2025 (valued at first-day closes, the peak launchpool era); Bitget
Launchpool averaging ~40% APR (Bitget news, Oct 2025) and PoolX 10–45%. Three reasons it is
not in the plan:
1. **It competes for the same dollars.** Staked coins are locked and are not futures margin.
2. **The staked asset carries its own price risk.** BGB/BNB exposure is a bet on the
   exchange token; USDT pools pay far less than the headline rates.
3. **There is no history to test.** Bitget's public API does not serve past pools. The only
   honest measurement is a forward log of pool APRs and the realised sale price of each reward.

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

---

## Re-scored on the corrected engine (2026-09-23 evening) — see [doc 11, part 2](11-money-machine-search.md)

After the three engine fixes (doc 03 #12–14), the engine-level kills were re-run
(`backtest/graveyard_rescore.py`). **Nothing buried came back to life.** The tight exit is
confirmed on both halves. A time stop (exit below +2R after 100 bars) added on top of it
improves the worst month on both halves (+8 / +13 pts) and is a paper candidate. The
bb(30,1.25) and 10/20/40-trail near-misses turn negative on both halves: their old holdout
gains were the unfunded engine. The liquidation-cascade bounce, which never had a verdict, is
dead on 4 years of data (`backtest/cascade_redux.py`).

---

## Dead: six strategies for BEAR and CHOP markets (2026-09-24) — `backtest/bear_chop.py`, `backtest/carry_check.py`

**Why these were run.** The trend book earns in bull months (+23%/mo main, +47%/mo triple) and
about zero in bear and chop (`logs/regime_and_liq.txt`), which is 63% of days. The ask was a
strategy for those days. Everything below uses the point-in-time universe with dead coins
(no 3x haircut applies, because nothing here was picked with hindsight), 12bp, actual funding,
the holdout from 2024-08-29, and `market_neutral.btc_regime` for bull/bear/chop, so the rows
line up with `regime_and_liq.py`. Predictions were written into the docstrings before anything ran.

| # | strategy | result | verdict | log |
|---|---|---|---|---|
| 1 | cross-sectional short-term reversal, market-neutral (1/3/7-day look × 1/3/7-day hold × ranked same close or a day earlier) | **all 18 cells net-negative**, −1.08 to −7.59 %/mo. The only positive gross (+1.74%/mo, 1-day look) turns to −2.79% once ranked a day earlier, so it came from the close print itself | dead | `logs/bear_chop_1.txt` |
| 2 | crypto pairs stat-arb (Engle-Granger, 180-day formation, 10 pairs, z 2 → 0, stop 4) | **−0.38%/mo**, tune −0.42, holdout −0.30. **72% of trades exit at the \|z\|>4 stop**, i.e. the "cointegrated" pairs broke apart within the month. Chop +0.40%/mo, bull −1.26 | dead | `logs/bear_chop_2.txt` |
| 3 | daily trend shorts with pyramids (BB(30,1.5) break, trail 3/5/10×ATR, 1/3/5 units), bear-gated, top-40 incl. dead coins | **worse than RANDOM short entries in every cell**, by −0.17 to −0.27R per trade (**t −3.8 to −4.6** across months). Random bear shorts also lose (−0.08 to −0.25R) | dead | `logs/bear_chop_34.txt` |
| 4 | mean reversion gated to one regime (fade BB(20,2), exit at the mean) | chop −0.064R/trade (vs random: +0.048R, t +1.06); bear −0.000R (t −0.47); bull −0.115R (t −0.06). **No gate beats random** | dead | `logs/bear_chop_34.txt` |
| 5 | short BTC / ETH whenever below their own 1000h (42-day) average | BTC **−3%/yr, DD 66%** (2022, when BTC fell ~65%: only +17%); ETH **−14%/yr, DD 90%**. Long-above/flat-below remains the best rule (BTC +45%/yr, DD 51%) | dead | `logs/bear_chop_1.txt` |
| 6 | market-neutral funding carry (short the highest 7-day funding decile, long the lowest, weekly) | +0.78%/wk on average, and **−107% of the account in ONE week**: short MYX while it rose **+1,137%** (2025-09). Maximum drawdown 133% (the account is gone) | dead: a squeeze-tail harvest | `logs/carry_check.txt` |

### What surprised me

- **Test 3's sign.** I predicted daily bear shorts would earn raw R and merely fail to beat
  random. They lose, and the *signal is significantly worse than random*: a breakdown
  below the band in a bear market is followed by a bounce. That is the same fact as
  `bear_shorts.py` ("by the time BTC is below its average the fall has already happened")
  measured from the other side, at the single-trade level with a control.
- **Test 6 looked like the first real bear strategy for a few minutes:** +1.24%/wk in bear
  regimes, positive in 6 of 7 years, both halves positive. The repo's rule ("every large
  improvement was a bug until proven otherwise") is why `carry_check.py` exists, and it found no
  bug. What it found was worse, because the result is real and the book still cannot be traded:
  - the coins with the highest funding are the ones that get short-squeezed;
  - the five worst weeks are MYX +1,137%, ESPORTS +603%, WIF +316%, AKE +166% and BNX +512%;
  - the edge is fragile everywhere else it was checked:

  | carry variant (`logs/carry_check.txt`) | holdout %/wk | bear %/wk | worst week |
  |---|---|---|---|
  | 7-day rank, exact settlement window | +1.14 | +1.24 | −107% |
  | funding clipped at ±0.5% per settlement | −0.23 | +1.00 | −105% |
  | coins listed ≥ 180 days only | −0.39 | +1.14 | −41% |
  | 30-day rank instead of 7 | +0.42 | **−0.44** | −35% |
  | 3-day rank instead of 7 | −2.44 | −0.54 | −130% |

  A bear-regime return that changes sign with the look-back window is not a property of the
  market.

### A small correction found on the way

`market_neutral.run` credits funding over days *i..i+hold−1*, but the book is held from close
*i* (00:00 of day *i+1*) to close *i+hold*, so the window is one day early. For the carry test
that was look-ahead: the coins picked for paying on day *i* were credited day *i*. For doc 10's
momentum book it is negligible: **+1.222 → +1.212 %/wk** (`logs/bear_chop_6.txt`). Doc 10's numbers
stand. `bear_chop.fast_run(fshift=1)` and `carry_check.exact_funding` carry the right window.

### The answer to "what do we run in bear and chop"

- **Chop already has an answer, and it is on paper.** Doc 10's market-neutral momentum book
  earns **+1.39%/wk in chop** on the exact funding window (`logs/carry_check.txt`), against the
  trend book's ~0. Nothing tested today beats it there.
- **Bear had no answer beyond what the bot already does** when this section was written.
  Shorting coins, shorting BTC, shorting breakdowns, fading, pairs and carry all lose or blow
  up. The trend book reads −0.74 to +0.26 %/mo there (`logs/regime_and_liq.txt`), and the
  momentum book is roughly flat (+0.19%/wk). **Later the same day, a candidate:**
  [doc 13](13-bear-breadth.md). Market breadth predicts the next week *inside* bears (the one
  Holm pass in 84 cells). Traded both ways only in bears, it made +25–27%/yr at 1× with zero
  correlation to the trend book. It is not deployed, and it needs a forward test.

---

## Dead: three crash-bid refinements, and one bear idea (2026-09-25) — `backtest/wick_funding.py`, `backtest/squeeze_bear.py`, `backtest/wick_exit.py`

Each had a mechanism and a registered prediction. None of them survives.

**1. Crash bids only on crowded-long coins** (`wick_funding.py`, `logs/wick_funding.txt`). The idea:
a wick on a coin whose longs were paying high funding is pure forced selling, so it should bounce
more. On the tune half it looks right: +3.21% a fill in the top funding tercile, against +2.31% in
the bottom. On the holdout it reverses: **−0.14%** in the top tercile, against +1.24% in the bottom.
Skipping the bottom tercile cuts the holdout from +16.9% to +4.2%/yr. Prediction wrong. Dead.

**2. Selling squeeze spikes in BEAR markets** (`squeeze_bear.py`, `logs/squeeze_bear.txt`). This is
the crash bids' mirror, tried only where it has a reason to work: a 10% hourly spike in a bear
market as forced short-covering, which should fade. It does not.
- At 10% on BEAR days: **−0.43% a fill** (tune −0.90%, holdout +0.08%).
- The worst single fill is **−339%**: LUNA's dead-cat bounce on 2022-05-11.
- At 15–20% the halves disagree in sign.

Prediction wrong. Dead.

**3. Holding the crash-bid fills longer** (`wick_exit.py`, `logs/wick_exit.txt`, 1-minute bars
2022–2026, both venues).
- Selling 120 minutes after the fill beats the hour close by **+0.21 a fill (se 0.16)**: not
  significant, and negative in 2022.
- It barely deepens the worst paper loss while held: −16.8% against −16.0%.
- "Hold longer only after a capped wave" is worse than either.

**Not adopted.** The paper book `wick_paper.py` records the +120 exit beside the rule.

**Settled on the way: the venue** (`wick_bitget.py`, `logs/wick_bitget.txt`). Doc 16's crash bids
were replayed on Bitget's own 1-minute bars, 2022–2026, with the paper book's code. Coins Bitget no
longer serves used Binance's bars as a stand-in, so dead coins still count.
- On Bitget's own bars: **+1.01% a kept fill** (949 fills, se 0.23); tune +1.60%, holdout +0.74%.
- **The same coin-hour on both venues: Bitget +0.86%, Binance +0.87%**, a difference of −0.01
  (se 0.01).
- Fills before the cap: 97% of Binance's count.

The venue question doc 16 left open is answered: Bitget is as good as Binance for this.

---

## Dead: 33 forex tests — nine documented effects and the Asian-range breakout (2026-09-25) — `backtest/fx_anomalies.py`, `backtest/fx_breakout.py`

Doc 18 has the detail. In short:
- **Nine published calendar and session effects:** overnight drift (NDX, SPX), turn of month
  (NDX, SPX), gold and silver outside New York hours, FX home-hours depreciation, month-end USD
  rebalancing, and the NDX intraday control.
- **The retail Asian-range breakout at the London open:** EURUSD, GBPUSD, USDJPY and gold, 2 stops
  × 3 exits.

**All 33 fail after Exness costs**, on both halves, with Holm. The effects are real but a few
basis points. For example, NDX overnight is +3.4bp a night gross against 2.8bp of spread + swap,
and turn-of-month is +5bp over any 4-day hold.

**T8 re-checked 2026-10-11 (`backtest/fx_t8_exness.py`, rule 9 - the measurement was broken).** Yahoo's EURUSD=X
bars are dated a day off Exness's (see CLAUDE.md s3), so T8's "month-end" return was the day before. On Exness's own
prices, 78 month-ends 2020-2026: **-4.06bp a month, t -0.83, right sign 43 of 78 - the kill stands.** Yahoo realigned
by a day (corr 0.947 with Exness) gives -4.74bp over 2003-2026, both halves negative; to the 16:00 London fix,
-3.81bp. The published +4.13bp was the wrong day.

**What survives, and only swap-free:** 12-month trend on commodities + indices (`fx_tsmom.py`,
doc 18 §4), +5.5%/yr at 10% volatility, 2004–2026, both halves. The FX legs of that book earn
nothing (Sharpe 0.03).

**Same day, the trader's own pattern as a rule** (`backtest/his_micro.py`, his_strategy.md §24). What
his 1-minute charts show, encoded: join the 1-minute trend after a 1–3 bar pause, 5/7/10-point target,
20-point stop, 5-minute time stop, 10:30–15:30 ET. **18 of 18 cells lose**: −3.5 to −5.4 points a
trade net, 53–66% wins against ~74% needed. News-footprint ranks of his entries are also ordinary
(`his_news.py`). His edge is choosing which pause, and that is not in the bars.

**Same day, at tick level** (his_strategy.md §25). The pause the trader joins, now exactly measured:
a NASDAQ-led 5-minute move, then a market-wide 30-second dip, entered mid-candle. It was tested as
a rule on every second of April–September with real bid/ask:
- `his_pullback_ticks.py`, 9 cells: −2.9 to −3.1 points a trade;
- `his_leadership_ticks.py`, 3 cells with NASDAQ leading the S&P: −3.0 to −3.5.

Random entries in the same hours make −2.9. **No better than random.** His selection among those
pauses is not in the tick price, the tape speed, the other indices, news before or after, or the
day's trend.

**2026-09-26, the trader's pause markers as rules** (his_strategy.md §26), every trading day April–September
with real USTECm bid/ask:
- limit orders at 25/50/100 futures levels vs offset and random levels (`his_levels.py`): all −2.8 to
  −3.5 points a trade;
- a quiet hammer in a trend, with and without a round level (`his_setup.py`): −2.3 to −2.7 vs random
  −2.6;
- rejection wick + not extended (`his_predictors.py`): 34.4% vs 33.9% net race win.

**Dead as rules.** The rejection wick alone is a real but small 3-minute predictor (+3.1 points of win
rate, both halves).

**2026-09-26, order flow at the trader's moments** (his_strategy.md §27). Binance QQQUSDT's buyer/seller-tagged
trades on 24 days (`his_orderflow_archive.py`, `his_orderflow_check.py`):
- Binance follows the Exness NASDAQ price by up to a second and never leads it (correlation 0.567 in the
  same second, 0.015 with Binance a second ahead).
- At his entries the flow only restates the dip and the quiet candle (ranks 0.38, p 0.04–0.06; nothing
  survives Holm).
- As a 3-minute predictor it is ~0 (+0.8 over 40 samples). A first-draw +11.7 was sampling luck.
- Net of the spread, no decile comes near break-even (31–37% against 50%).

**Dead.** This was the last free data source for his pick.

**2026-09-26, the trader's entries against the real news calendar** (his_strategy.md §28,
`his_calendar.py`). ForexFactory's calendar: 216 high-impact dollar releases and 333 speeches (the
President, the Fed Chair, Fed members, the Treasury Secretary), each entry against the same New York clock
time on 175 other days:
- **Nothing survives Holm.**
- His trading days carry releases at the base rate (44.8% vs 45.6%) and big speeches too (31% vs 29%).
- The only hint is more trades on release mornings (13 vs 8.2 within 3 h, p 0.044), gone when each day
  counts once (7 vs 5.3).
- His biggest days had nothing on the calendar.

**Scheduled news does not pick his moments.** Unscheduled posts are untested (they need the archive).

**Same day, the trader's entries against Trump's posts** (his_strategy.md §29, `his_posts.py`, CNN's
Truth Social archive). 5,709 posts in his period:
- Posts that NASDAQ jumped on came before his entries at chance (5 vs 3.7, p 0.50).
- So did market-topic posts (7 vs 7.2).
- **Nothing survives Holm.** Two striking cases (a "stocks should go up" post before his jobs-day buys, an
  AI post before his biggest session) are what 46 trades throw up. The news angle is closed.

**Same day, smart-money concepts and the standard indicators at the trader's moments** (his_strategy.md §30,
`his_ta.py`). Liquidity sweeps, fair value gaps, break of structure, premium/discount, EMA, RSI, Stochastic,
MACD and Bollinger, on 1- and 5-minute candles rebuilt from ticks.
- Against the other moments of the same 20 minutes, his 25 clean entries rank ordinary on every one: ranks
  0.40–0.54, flags 0.95–1.33×, nothing near Holm.
- On all days no feature gets the net race near break-even (best 37.6% against 35.8%, 50% needed).

**Same day, every 1-minute candle pattern at the trader's moments** (his_strategy.md §31, `his_1m.py`).
There were 13 patterns: pin bar, inside bar, engulfing, doji, outside bar, stars, tweezers, pullback candles,
and the forming candle at his click. Each was measured against the same 20 minutes at the same second of
the minute:
- the best are the inside bar (2.09×, p 0.044) and the pin bar (2.21×, p 0.086);
- nothing survives Holm (best 0.58);
- no pattern gets the net race above 37% (50% needed).

**Same day, the eight biggest NASDAQ stocks, the dollar and bitcoin before the trader's entries**
(his_strategy.md §32, `his_generals.py`). NVDA, MSFT, AAPL, AMZN, GOOGL, META, AVGO and TSLA from MT5 ticks at
1 second, aligned to the second:
- they lead Exness's NASDAQ by at most 5 seconds;
- at his entries they rank ordinary (0.43–0.58), and so do the dollar and bitcoin;
- on 114 days none moves the 7-point race by more than +3.1 points.

**Dead.** His edge itself was re-tested and is real: 10 of 12 days at ±7, t 5.8 (`his_race_curve.py`).

**Same day, every feature at once** (his_strategy.md §33, `his_model.py`). 75 features in logistic and random-forest
models, trained to tell the trader's moment from the 40 other moments of the same sitting at the same second of
the minute. Scored only on unseen days, his moment ranks 0.505 / 0.486, against luck's 0.497 / 0.490 (p 0.36 /
0.55). The top-scored moments on 106 other days win the 7-point race 50.4% / 49.1%.

The power check (`--power`) recovers planted 2–3 feature patterns at 0.72–0.96, so a combination that strong
would have been found. **Dead: his information is not in the recorded data.**

**Same day, the trader's charts read by eye, and his key levels** (his_strategy.md §34, `his_look.py`,
`his_keylevels.py`). His 25 clean trades were drawn on his broker's scale with yesterday's high, low and close,
the open, the first-15-minute range and the day's high and low.
- By eye: ordinary setups (pullbacks, level bounces, a breakout), with look-alikes on every chart.
- Tested: his entries sit a median 37 points from the nearest key level, ordinary against his sitting (rank
  0.54).
- **The eye's level impression came from 4–5 memorable trades.**
- **Not dead:** his record is real-time (exits identical to a mechanical target, `his_extremes.py`), and a copy
  within ~10 s keeps his edge on these 25 trades (`his_copy_delay.py`, §34).

---

## Dead: two ways to make the market-neutral book bigger (2026-09-26) — `backtest/mn_stop.py`, `backtest/mn_scale.py`

**Why it was worth trying.** The product earns +71%/mo in rising markets and +7.6% in falling
ones, and about nothing in SIDEWAYS (+0.2% average, −4.5% typical, 32% of months up,
`logs/machine.txt`). Sideways is 25 of 79 months. Of the four books only the market-neutral one
earns in every regime, and it is held at 1× for a single reason: its worst week is **−24.2% of the
whole account**. Make that tail smaller and the book can be run bigger, which is the one thing the
sideways cell needs. Both attempts failed, and the first failed for an instructive reason.

**1. A stop on the short leg** (`mn_stop.py`, `logs/mn_stop.txt`). The book shorts the bottom
momentum decile — beaten-down coins, which are exactly the ones that squeeze — with no stop of any
kind. Per-name stops at +50% to +300%, checked on daily closes, exiting at the close that breached
the level so a gap is paid in full:

| short stop | %/wk | CHOP | Sharpe | DD | worst week | stopped |
|---|---|---|---|---|---|---|
| +50% | +1.098% | +1.058% | 1.10 | 35% | −23.2% | 2.3% |
| +100% | +1.162% | +1.326% | 1.15 | 39% | **−26.3%** | 0.3% |
| none | **+1.222%** | **+1.403%** | **1.22** | 37% | **−24.2%** | — |

The stop makes the worst week **worse** and fires on 0.3% of positions at +100%. It books the
bottom of a squeeze that reverts inside the week. Four of six registered predictions wrong.

**The premise was itself wrong, and that is the lesson.** The single-name blow-ups quoted to
motivate this (MYX +1137%, 2025-09-05) are the five worst weeks of the **funding carry** variant in
`logs/carry_check.txt` — a different book, with a −107% worst week. The momentum book that is
actually deployed has never had its worst weeks decomposed, and its −24.2% is not one name running
away. *Check which book a number belongs to before building on it.*

**2. A wider basket** (`mn_scale.py`, `logs/mn_scale.txt`). `frac=0.1` is hard-coded in
`market_neutral.run`, `bear_chop.fast_run`, `crash_days.mn_basket` and `bear_shorts.weakest`, and
is swept nowhere. On the PIT top-60 a decile is **six names a side**, so one name is a sixth of a
leg. If the tail were concentration, width would cut it:

| frac | names/side | %/wk | CHOP | Sharpe | worst week |
|---|---|---|---|---|---|
| **0.10** | 6 | **+1.222%** | **+1.403%** | **1.22** | −24.2% |
| 0.15 | 8 | +1.083% | +0.811% | 1.13 | −17.2% |
| 0.25 | 14 | +0.573% | +0.302% | 0.80 | −30.8% |
| 0.50 | 28 | +0.333% | +0.067% | 0.80 | −14.0% |

The signal dilutes faster than the tail shrinks, and the worst week is not even monotonic. Scaled
to a common worst week, frac 0.10 beats every wider basket on chop return. **frac 0.10 is already
the right number.** The decisive prediction was wrong.

**What survived instead.** Not a change to the book — a change to its WEIGHT. See
[doc 19](19-all-weather.md): the book is simply run at 2×, which the mix can carry, and that is
what lifts the sideways cell.

---

## Dead on inspection: crash bids sized up in sideways markets (2026-10-01) — `logs/wick_capped.pkl`

**Why it was worth checking.** Of the four books, only the crash bids have the right *shape* for sideways months
(88% of them up, `all_weather.py`), and they are held at 1× by their tail. If that tail lived in bull-to-bear turns,
the bids could run larger only in chop. **It does not** (cap 10, days labelled by `btc_regime`):

| regime | days | days with fills | mean per day | worst day |
|---|---|---|---|---|
| bull | 882 | 247 | +0.078% | −1.50% |
| **chop** | 959 | 262 | **+0.035%** | **−3.35%** |
| bear | 614 | 0 (no bids by rule) | — | — |

**7 of the 8 worst days are chop days** (2020-03-12, 2026-06-02, 2026-04-17, 2026-03-24, 2022-05-09, 2025-11-07,
2024-10-15). Sizing up in chop buys the fatter tail and the half-size edge together. Not built. The full list of what
has been tried for sideways markets, and why it is closed at retail, is in [doc 20](20-the-product.md) §3.

---

## Dead: trading Exness's NASDAQ quote off the CME futures (lead-lag), 2026-10-04 — `backtest/nq_leadlag.py`

Found incidentally in `his_basis.py` (his_strategy §40): around the trader's entries, "Exness follows the futures" won
56–62% of ±7 races. Tested properly on **72,082 paired seconds** of CME NQ futures (Databento bbo-1s) and Exness USTECm
ticks, predictions committed first (`logs/nq_leadlag.txt`):
- **No lag to trade.** Correlation of 1-s futures returns with Exness returns: **+0.89 at the same second, +0.13 one
  second later**, ~0 after. Exness reprices within the second.
- **No catch-up worth the spread.** After the futures move ≥ 1–3 points over 1–5 s that Exness has matched by less than
  half, Exness's next move in the futures' direction averages −0.35 to +0.47 points over 1–10 s (≤ +1.5 at 30 s, mixed
  signs) against a **2.16-point median spread**. Best cell net **−1.84 points a trade**.
- All three registered predictions right. The 56–62% was momentum on correlated moments around his entries.

**2026-10-05, crowd sentiment and retail attention** (`sentiment.py`, `sentiment_dial.py`). The user: "sentiment
drives crypto". Never tested before: Fear & Greed as a timing signal (alternative.me, 2018–), and retail attention
(Wikipedia views of Bitcoin, Cryptocurrency, Ethereum and Dogecoin, 2015–).
- **On BTC itself nothing passes:** 15 cells, all fail Holm, and several flip between halves.
- **On the combo's next 7 days, two cells pass:**
  - Fear & Greed top third against bottom third: +8.10 points (+7.20 / +9.16 by half), Holm 0.011;
  - attention: +7.02, Holm 0.030.
  - Both are **momentum, not contrarian**, and both survive the book's own 30-day return, BTC's 30-day return and the
    1000h gate as controls (t 2.26 / 2.52). Predicted the opposite, and predicted nothing would pass.
- **As a dial it is dead.** 1.5x in the top third and 0.5x in the bottom, with thirds from an expanding window,
  paired on 10 orderings:
  - **Fear & Greed lowers Sharpe on both halves:** −0.145 and −0.066, 0 of 10 orderings better in either. Its
    CAGR rises, but the worst fall rises faster: 50 → 61% and 60 → 73%.
  - Attention: −0.034 / +0.016.
- **The reading:** greedy weeks pay more because they are wilder. Sizing up in them is betting bigger on worse
  terms.

---

## Dead: a currency-strength meter with volume confirmation, 2026-10-06 — `backtest/fx_strength.py`, `fx_strength_check.py`

**The user's idea:** "check whether volume is rising in different markets, use the historical relationships between
currencies, and predict the move." Both halves had died separately (VSA and the volume-surge filter ran backwards; the
NASDAQ–gold and crypto pairs, DXY→BTC and the intraday cross-market leads all failed). The combination, as an FX trader
builds it, had not been tried: an **8-currency strength meter** (USD, EUR, GBP, JPY, AUD, NZD, CAD, CHF) from the seven
USD pairs, hourly 2020-03 → 2026-09 from the Exness MT5 cache, with MT5 tick volume as the confirmation.
Predictions committed before each run; costs 1.5 bp a round trip with USD on one side, 3.0 bp for crosses, 0.5 bp a night.

**`fx_strength.py` — 24 cells** (buy the strongest against the weakest, or the reverse; strength over 1 / 4 / 24 / 120
hours; held 1 / 4 / 24 hours; `logs/fx_strength.txt`):
- **0 of 24 pass** (positive after costs on both halves with Holm < 0.05).
- **Momentum loses even before costs**: every "strongest vs weakest" cell is negative gross. Currency strength mildly
  REVERSES at these horizons, and the reversal is smaller than the cost at every setting but one (fade the last hour's
  extremes over 24 h: +2.70 bp net, t 1.76, Holm 0.32).
- Predictions 1, 3, 4's direction held; 2 (momentum best gross at days) wrong; **4 wrong in the interesting way** — on
  that one cell, volume-confirmed trades (tick volume ≥ 1.5× the hour's norm) earned +7.2 / +21.4 bp more on tune /
  holdout (190 trades).

**`fx_strength_check.py` — the bug hunt** (`logs/fx_strength_check.txt`). That cell steps 24 bars at a time, so every
trade sat at one hour of the day (20:00 UTC, next to the daily FX rollover, when quotes widen and tick volume spikes).
The same rule at each of the 24 start hours:
- plain reversal is **negative at 21 of 24 hours** (−1 to −7.7 bp); the best is **21:00 UTC, the rollover** (+2.5 bp),
  where real spreads are far wider than the cost charged;
- volume-confirmed trades swing hour to hour (−20 then +16, −9 then +35 bp on ~130 trades each); **4 of 24 hours are
  positive on both halves — chance gives ~6**; outside the rollover they average **−1.6 bp**.
- Prediction 2 (volume lift only at rollover, nothing elsewhere) right in substance; prediction 1 half right (the cell
  sat at 20:00, beside the rollover, not inside it).

**Verdict:** the volume lift was the hour of day plus noise; currency strength carries no tradable relationship at 1–24
hours after Exness costs. Consistent with `fx_tsmom.py`: the FX legs of the one surviving trend book earn nothing.

## Dead again, on the causal allocator: the slot ideas (2026-10-06) — `backtest/slot_ideas.py`, `backtest/slot_split_matched.py`

**Why reopened.** Mistake #17 (doc 03): the old allocator freed a slot at the label of the exit bar, before the
position had closed. The ideas whose verdicts rested on how slots are handed out were re-run on the triple with:
- causal slot release;
- the live bot's position model (one position per coin × sleeve, retry, one-bar pause);
- 10 orderings, each variant paired against the 12-slot book.

**Not reopened:**
- slot priority, which was killed by a head-to-head of simultaneous signals that never touched the allocator;
- correlation clusters, which did not exist (12 coins at ~0.63 pairwise).

**The 12-slot book (the bot):** +9.97% tune / +4.97% holdout per month, worst fall 64% / 56%, gross leverage 9.5×
at p99.

| variant | tune Δ %/mo | hold Δ %/mo | worst fall t/h | lev p99 | verdict |
|---|---|---|---|---|---|
| 8 slots | −2.20 | −1.20 | 50 / 46% | 6.2× | dead |
| 16 slots | +2.30 (10/10) | +0.13 | 69 / 63% | **12.4×** | tune only, over the 10× line |
| 20 slots | +3.56 | +0.48 | 77 / 66% | 15.6× | over the line |
| split 8 long / 4 short | −1.74 | +2.21 | 49 / 45% | 9.5× | flips |
| split 10 / 2 | −1.74 | +2.11 | 55 / 57% | 12.3× | flips |
| split 6 / 6 | −2.37 | +1.10 | **37 / 39%** | 7.2× | flips |
| max 1 position per coin | −2.65 | −0.04 | 63 / 55% | 12.7× | dead |
| max 2 per coin | +0.94 | +0.35 | 62 / 56% | 11.0× | not significant |
| control: 12 slots at 0.40% | +1.72 | +0.30 | 75 / 67% | 12.7× | |

**The one near-miss: 6 long / 6 short at matched drawdown.** The shared book was scaled down to the split's own
drawdown:
- On the deployed bar grid the split earned more on BOTH halves: +1.74 ± 0.57 and +2.01 ± 0.46. That was a pass,
  and a surprise; I had predicted holdout-only.
- **On the other three bar phases it lost on the tune half:** −0.82, −2.89 and −1.71 (`logs/slot_split_phases.txt`).
- It passed on 1 of 4 phases, so it is **dead**. The phase-0 pass was where the 4h/12h candles happen to start.

This is the check that kept the tight exit and the 7-unit pyramid, and here it did its job the other way.

**Predictions:** all right except two. The shared pool does NOT beat every split on the holdout. And the 6/6 split
did not hold across phases, though I predicted it would.

## Dead: "what are my odds right now" from RSI, momentum and support/resistance (2026-10-06) — `odds_now.py`

**The question (the user's):** on any day, read RSI, momentum and support/resistance for a coin, and say "go long
here: X% chance of take-profit, stop there". `odds_now.py` answers it by history. It puts the moment in a cell:
- RSI(14), 5 buckets;
- 24h move in ATR units, 5 buckets;
- place in the 50-bar range, 3 buckets;
- the BTC 1000h gate.

It then replays every past moment in that cell on the point-in-time top-50 perps, dead coins included (2.7M
coin-hours, 2020-02 .. 2026-09). Entry is the next open, the stop 2×ATR, targets 1/2/3R, a 48-bar timeout,
pessimistic fills, 12bp, real funding. Trades on one coin do not overlap, and standard errors are clustered by day.

**The coin flip, measured:** at any moment a 1R long hits target first 47.5% of the time and averages −0.17% a trade
after costs. A short is 49.5% / −0.09%. With the stop 3× further than the target the win rate reads ~75% with no
skill at all, so a TP-first percentage means nothing without its baseline.

**The sweep** (150 cells × 2 sides × 3 targets; 570 occur):
- Against any moment, 8 passed t > 2.4 on both halves, above the registered 0–5. Seven were one cluster: short,
  flat 24h, near the 50-bar low, BTC bear.
- Against **any short in the same BTC bear** that cluster is t +2.2 / +2.1. 2020 loses, 2023–24 are flat, and 52%
  of months are positive. Three months make 40% of it, and it earns +0.15–0.28% a trade.
- The rule was then made stricter: same-regime baseline, both halves positive in R and %, and t > 3.9 to correct
  for the 570 tests. The result is **0 EDGE and 3 WEAK**, which is chance level (`logs/odds_sweep.txt`).

**Prediction:** single queries mostly NO EDGE, which was right. The sweep passing 0–5 was right only after the
regime baseline: the first, looser rule gave 8. The baseline at 45–49% was right.

**Kept as a tool, not a strategy.** Its usual answer, "NO EDGE, skip it", is the measured one. Live on 2026-10-05
21:00 UTC: BTC long, SOL short and PEPE long were all NO EDGE. 11 offline tests in `tests/test_odds_now.py`: a planted
drift is found at t 10.3 and a random walk reads t 0.6. Three code mutations (a same-bar stop read as a win, a gap
filled at the stop, overlapping trades) each fail them.

**Two bugs caught before any number was read:**
- BNX's three-week halt in 2023: a 48-bar window ran across the hole and read as −98% trades. Windows now may not
  cross a missing hour or a >50% open-vs-close jump.
- The `[us]` datetime unit (pandas 3) made that hole check exclude EVERY row, which is the §3 trap again. It is
  forced to ns, and the build now refuses a table under 1M rows.

## Dead: 1-minute scalping on BTC and DOGE at 30-40x - "even a small edge makes money with leverage" (2026-10-06) — `backtest/scalp_1m.py`

**The idea (the user's):** stick to BTC and DOGE, read 1-minute RSI and the like, and let 30–40× leverage turn a
small edge into money.

**The arithmetic first.** Fees are charged on the position, not the margin:

| round trip | 1× | 10× | 20× | 30× | 40× |
|---|---|---|---|---|---|
| taker 12bp | 0.12% | 1.2% | 2.4% | 3.6% | **4.8% of the account per trade** |
| maker 4bp | 0.04% | 0.4% | 0.8% | 1.2% | 1.6% |

A 1-minute 2×ATR stop is 0.122% of price on BTC and 0.240% on DOGE, so 12bp is **0.98R / 0.50R a trade** before any
signal. Doc 02's line for a hopeless timeframe is 0.15R.

**The test** (2,453,760 one-minute bars each, 2022-01 .. 2026-08, holdout from 2024-10-19):
- seven named rules (RSI reversal, RSI with an EMA200 trend filter, RSI momentum, EMA 9/21, Bollinger fade and
  break, 60-bar breakout), plus BTC-leads-DOGE and odds_now's 150 cells;
- stop 2×ATR, 1R/2R targets, a 60-bar timeout, pessimistic fills, funding;
- 572 tests per fee level.

| cost | net-positive on both halves | WEAK (t > 2.4) | EDGE (t > 4.0) |
|---|---|---|---|
| none (gross) | 207 | 43 | **8, all shorts, +0.5 to +1.9bp a trade** |
| maker 4bp | 4 | 1 | 0 |
| taker 12bp | **0** | 0 | 0 |

The before-fee edges are real (t up to 6.1, both halves): 1-minute downside moves are faster than upside ones, so
short targets fill a little more often. They are one-tenth to one-half of the cheapest fee.

**Leverage, directly** (`--kelly`, `logs/scalp_1m_kelly.txt`). The three best gross edges, the whole margin in every
trade, 4,000 PKR, judged on the holdout. Growth per trade is lev × mean − lev² × variance / 2, so a small edge has
a small best leverage:

| edge | cost | Kelly lev (tune) | at Kelly | 30× | 40× |
|---|---|---|---|---|---|
| RSI momentum short, BTC | zero fees | 11.3× | 1.1M PKR | **0** | **0** |
| RSI momentum short, DOGE | zero fees | 4.0× | 240k PKR | **0** | **0** |
| best DOGE cell | zero fees | 6.8× | 208k PKR | **0** | **0** |
| same three | maker 0% + 2bp on stops | −7× / −1.6× / 1.6× | 796 / 1,880 / 6,160 PKR at 1× | 0 | 0 |

**Even at zero fees, which no venue offers, 30–40× ruins every one of them** - the same edge that compounds at
5–11× is destroyed by variance at 30×. At the cheapest real cost two lose at every leverage and the third (chosen
on the full sample) earns +0.56bp a trade at 1×.

**Predictions:** all right, and the leverage one was stronger than registered (3 of 3 ruined at zero fees, ≥2
predicted).

> **Leverage cannot create an edge, and past the Kelly leverage it destroys a real one.** The leverage that pays is
> set by the edge, not by the account size - for anything findable on 1-minute charts it is single digits, at fees
> nobody retail pays.

Also learned: a one-cut causality test missed a planted look-ahead because breakout signals are sparse (§3, "a
test that cannot exhibit the bug"). `tests/test_scalp_1m.py` now cuts at 150 points in both directions and catches
it.

## Dead after fees, and dead at any leverage: trading DOGE on a model of BTC + DOGE (2026-10-06) — `backtest/btc_doge.py`

**The claim (the user's):** "with proper analysis we won't lose - trade DOGE, analyse BTC, because BTC moves DOGE."
`scalp_1m.py` had tested one BTC→DOGE rule. This is the general version: 27 features from both coins at a closed
minute go into a model (ridge and gradient-boosted trees):
- returns over 1–240 minutes, RSI, range position, volatility;
- DOGE's lag behind BTC.

The target is DOGE's next 5 / 15 / 60 minutes. The model is fitted on 2022-01 .. 2024-02, the trade threshold is
picked on 2024-02 .. 2024-10, and it trades the unseen 2024-10 .. 2026-08. Causality is checked at 150 cut points,
and a planted centred window is caught.

**The user was right that the information exists:**
- same-minute correlation is 0.64;
- BTC's last minute vs DOGE's next minute is +0.019;
- on the unseen data the models' IC is +0.012 to +0.046, they get the direction right 51–57% of the time, and they
  make **+3.7 to +10.8bp a trade before fees**.

| fees | result on the unseen 22 months |
|---|---|
| taker 12bp | **all 6 lose**, −1.2 to −8.3bp a trade |
| maker 4bp (every limit fills, no adverse selection) | 5 of 6 positive, +0.3 to +6.8bp, **none significant** (t ≤ 1.8) |

**Leverage: all 12 are wiped out at 5×, and at 10/20/30/40×** - including the positive ones. The best (ridge, 60
minutes, maker fees) turns 4,000 PKR into 9,392 at 1×. Its own Kelly leverage is 2.6×. One hold, 2025-10-10 20:53
UTC, liquidates it at 2× and above: DOGE went 0.228 → 0.084 (−63%) inside the hour on Binance's 1m bars, verified
bar by bar. **At high leverage the outcome is decided by the worst minute of the worst day, not by the average
edge.**

**Predictions:**
- right: the lag-1 correlation, all taker results lose, every leverage ≥30× ruined;
- wrong: the same-minute correlation (lower than the 0.7–0.8 I gave), the gross edge (up to +10.8bp against my
  +5bp), maker-fee positives (5 of 6 against my "at most 1"), and ruin already at 2–5×, not only at 30–40×.

## Dead: one high-leverage trade on indicators and volume (2026-10-06) — `backtest/one_shot.py`

**The question (the user's):** "if I sit one time and open a trade with high leverage, there's a chance I can make good
money by following indicators and volume."

**The bet:** the whole stake as isolated margin at 10/20/40×, on BTC or DOGE. The target is double / triple / 5×
the stake, against liquidation, within 3 days. The data is Binance 1m bars with volume and taker-buy volume,
2022-01 .. 2026-08.

**The entries:**
- random minutes;
- five indicator + volume setups: oversold with a volume spike, breakout with volume, trend pullback, taker flow,
  and "BTC confirms" for DOGE.

The tests caught four planted bugs (a tie read as a win, two volume look-aheads, a centred window) once the test
data was made to fire every side of every setup.

**There IS a chance - it is the coin flip's** (40×, random moment, `logs/one_shot.txt`):

| outcome | BTC | DOGE | fair game |
|---|---|---|---|
| double before liquidation | 37–38% | 40–44% | 42.5% |
| triple | 16–17% | 23–27% | 27.5% |
| 5× | 4% | 10% | 16% |
| average result on the stake, per shot | −13% / −14% | −10% / −18% | |

**Indicators and volume move it by about one point.** At 40× and a double target, 0 of 18 setup lines beat random
by more than 4 points on both halves; the best gains are +1 to +1.6 points. Every setup's average result is negative
(−7% to −23% of the stake on the holdout).

**Predictions:** right on the double odds and the setups; too high on 5× (the 3-day window cuts the long runs).

**Every leverage, and splitting the stake** (`python -m backtest.one_shot --grid`, `logs/one_shot_grid.txt`; random
moments, long and short averaged). With 30 days to run, the real odds sit on the fair-game line at every leverage
from 20×. **Higher leverage makes the odds WORSE for the same goal**, because maintenance and fees are a bigger
share of a smaller distance:

| leverage | P(double), BTC / DOGE, 30 days | lose everything | average result per shot |
|---|---|---|---|
| 2× | 0.3% / 6.7% (mostly still open at 30 days) | 0.4% / 7.0% | −0.2% / −0.3% |
| 5× | 16% / 39% | 18% / 40% | −0.9% / −1.2% |
| 10× | 40% / 47% | 43% / 50% | −3.4% / −3.0% |
| 20× | 46% / 47% | 53% / 53% | −6.7% / −6.3% |
| 40× | 43% / 43% | 57% / 57% | −14.8% / −13.9% |
| 100× | 28% / 28% | 72% / 72% | −44.6% / −43.5% |

**Money does not change any of it.** Fees and liquidation are percentages, so every PKR amount above Bitget's ~$5
minimum has the same odds.

**Splitting the stake into k shots leaves the average where it was.** At 40× on BTC: one shot loses everything 52% of
the time and doubles 38%; four shots lose everything 7% of the time, double 2%, and end below the start 50%. The
average stays −13% to −14%.

**Prediction:** right on every point (worse odds with leverage, fair-game 49.6 / 42.5 / 28%, splitting changes only
the spread).

## Candidate, not dead: BTC→DOGE with limit orders (2026-10-06) — `backtest/maker_exec.py`

**Why it was re-tested:** the user said "there is something you have undermined." Auditing the day's work, it was
**execution**. `scalp_1m` and `btc_doge` filled every trade at the next open and treated maker fees as a loose
upper bound. This file models limit orders properly. A limit at the signal close is valid 3 minutes and fills only
when price trades THROUGH it. Fees are maker 0/1/2bp (2bp = Bitget's standard) and taker 6bp.

**Fills and adverse selection:**
- 93–96% of limits fill (I predicted 50–70%).
- Filled trades earn 0.6–2.4bp less than the next-open version of every signal tried. That gap is the adverse
  selection.
- A first printout compared against filled signals only and understated it, because the 4–7% that never fill are
  mostly the ones that moved the trader's way at once.

| strategy (holdout for A) | gross with limits | net at 2bp maker (Bitget) | net at 0bp |
|---|---|---|---|
| **ridge BTC+DOGE model, 60 min** | +8.3bp | **+4.07bp (t +1.0)** | +7.97bp (t +1.9) |
| ridge, 15 min | +5.4bp | +1.19bp (t +0.5) | +5.10bp (t +2.3) |
| trees, 60 / 15 min | +2.4 / −0.9bp | −1.75 / −5.03bp | +2.18 / −1.11bp |
| rsi_mom short 2R, BTC / DOGE | +0.1 / −0.3bp | −6.6 / −7.1bp | −4.0 / −4.5bp (stops pay taker) |

**Reading:** the first thing today that is positive after Bitget's real fees, and only just. At t +1.0 it cannot be
told from zero. The holdout has now been read twice (`btc_doge`, this file). IF real, it is about +60% over 22 months
at 1×, 1,490 trades. It has no stop, so leverage meets the 2025-10-10 hour (−63% on DOGE inside it).

**Status:** candidate for a pre-registered forward paper test. No money, and nothing in any bot.

## Answered: "I don't want small gains" - go-for-broke on 4,000 PKR, re-measured (2026-10-06) — `backtest/lottery_v2.py`

**The question:** the only route here to a big multiple with a positive average is the trend book's edge at high
risk on a small account (micro_bot's idea). `lottery.py` measured it on 2026-09-24. Three things came later and are
fixed here:
- mistake #17, the slot freed at the exit bar's label;
- the 7-unit triple;
- the 10× guard on pyramid ADDS, not only entries.

It also uses the user's actual stake, 4,000 PKR = $14.29, and Bitget's per-coin minimums on the 12-coin book. It
reproduces `triple_capped.simulate` exactly with the old release, and `lottery._pit_coin`'s rows exactly at 5 units.

**Honest universe (PIT top-12, dead coins in), 4,000 PKR, 12 months** (`logs/lottery_v2.txt`):

| risk per unit | ≥5× | ≥10× | ≥20× | ruined (−90%) | **ever under $5 (stuck)** | ended below start |
|---|---|---|---|---|---|---|
| 1% | 23% | 16% | 13% | 0% | **35%** | 48% |
| 2% | 29% | 22% | 18% | 6% | **49%** | 49% |
| 4% | 13% | 12% | 11% | 33% | | 68% |

70–75% of units are refused at this stake, because they fall under Bitget's $5 minimum.

**It depends on which year you start in** (2% risk, `logs/lottery_v2_detail.txt`):

| starts in | chance of ≥5× | median result |
|---|---|---|
| 2020-07 .. 2021-04 | 75% | ×204 |
| 2021-05 .. 12 | 0% | ×0.23 |
| 2022 | 0% | ×1.27 |
| 2023 | 0% | ×0.21 (every account under $5) |
| 2024 | 62% | ×7.1 |
| 2025 | 33% | ×1.26 |

**Against the 40× single shot:** that shot reaches 5× 4–17% of the time and loses 13–14% of the stake on average.

**Predictions:** wrong on the headline (10–20% with 30–60% ruin) - the odds are better. The −90% ruin line hid the
stuck accounts (35–49% "ever under $5" was predicted to be far above ruin, and it was). Wrong that 2022+ starts
would be ≤10% (2024: 62%).

**Status:** an answer, not a deployment. It is the trend book at 1–2% risk a unit. `micro_bot.py`'s own settings
(10 coins, single unit, 4%) were NOT re-measured, and 4% is worse here. Real money needs `ALLOW_REAL`, a human gate.

## Answered: micro_bot re-measured with its own settings (2026-10-06) — `backtest/micro_honest.py`

**Why it was re-measured:** `micro_bot.py` quoted "29.7% chance of $10 → $50, 70% ruin" from `microacct.py`
(2026-09-14). That estimate was pre-correction, trades were shuffled one at a time, and the edge was deflated
synthetically.

**What this replays:** the bot's own rules on real 1h paths, with an account-level book across its 10 coins:
- Bollinger(30, 1.5) breaks, longs and shorts, 1 unit;
- stop 2×SMA-ATR; trail 20× (longs) / 5× (shorts); breakeven at 3R;
- 4% risk; the $5 floor raised UPWARD; at most 3 positions; 10× per position;
- no regime gate; it stops opening at 5×.

**How it is modelled:**
- the bot places no exchange stop, so exits fill at the next open after the breached bar;
- sizing is on mark-to-market equity, as Bitget reports it;
- liquidation is checked every hour at each position's worst price;
- 63 monthly starts × 2 orderings, 12 months each.

The exits are tested equal to `micro_bot.manage()` bar by bar.

| 12 months | ended ≥5× (touched) | ended ≥2× | wiped out | liquidated |
|---|---|---|---|---|
| its 10 coins, $10, 4% (as built) | **29%** (42%) | 42% | 56% | 17% |
| its 10 coins, 4,000 PKR, 4% / 2% | 32% / 25% | 45% / 51% | 47% / **17%** | 10% / 3% |
| no-hindsight top-12, 4,000 PKR, 4% / 2% | 25% / 29% | 42% / 44% | 53% / **36%** | 29% / 18% |

**Where the wins come from:** real runs - AVAX 2021-01, SHIB 2021-10 and 2024-02, DOGE 2024-10/11. 20–50% of trades
win, and the top 3 trades make 50–100% of the profit.

**It swings with the start year** (4%):
- 2022 starts: 8–12%;
- 2024 starts: 62–71%;
- 2025 starts: 6% on its 10 coins against 72% on the no-hindsight universe.

**Verdict:** the old 29.7% roughly survives as "ended at 5× or more", with 47–56% wiped out at 4%. **2% gives the
same chance of 5× with 20–30 points less ruin.** Not changed in the bot - a human decides `RISK_PCT` and
`ALLOW_REAL`.

**Predictions:**
- wrong: 10–20% (the true figure is higher), the honest universe being lower (it is about equal), and 2% beating
  4% on P(5×) (a tie);
- right: ruin of 40–70% at 4%, and liquidations occur.

**At 10,000 PKR ($35.71)** (2026-10-08, `--pkr 10000`; `logs/lottery_v2_10000pkr.txt`,
`logs/lottery_v2_detail_10000pkr.txt`, `logs/micro_honest_10000pkr.txt`). Honest universe, 12 months:

| | ≥5× | ≥10× | ended below start | ever under $5 / ruined |
|---|---|---|---|---|
| **trend book (triple), 1% a unit** | **38%** | 30% | 37% | **5% / 2%** |
| trend book, 2% | 31% | 23% | 44% | 25% / 13% |
| micro_bot rules, 2% / 4% | 17% / 22% (ended) | | | ruined 10% / 44% |

**What the bigger stake buys:** the $5 minimum refuses about half of units, against 70–75% at 4,000 PKR. That lets
1% risk work. At 4,000 PKR the same row read 23% ≥5×, with 35% ever under $5.

**The trend book at 1% now beats micro_bot's own rules** at every risk level.

**By start year it is still mostly the year** (trend book, 1%):

| starts in | chance of ≥5× |
|---|---|
| 2020-07 .. 2021-04 | 80% |
| 2021-05 .. 12 | 19% |
| 2022 | 0% |
| 2023 | 0% (88% ended below start) |
| 2024 | 79% |
| 2025 | 56% |

**Predictions:**
- the trend book's best at 30–35%: actual 38%;
- micro_bot at 2%: predicted 27–33%, actual 17%, with ruin 10% against the predicted 25–35%;
- micro_bot at 4%: predicted 25–32% / 45–55%, actual 22% / 44%.

## Dead as asked: a one-day long on 10,000 PKR, picked by every combination of 20 indicators (2026-10-08) — `backtest/day_long.py`

**The question (the user's):** go long at the daily close (00:00 UTC), close 24 hours later, and choose the day with
indicators: RSI, EMAs, SMA200, MACD, Bollinger, Stochastic, dips and pops, volume, 20-day highs and lows, ADX, BTC
trend and funding. Every single condition, pair and triple: 1,350 filters × BTC/ETH/SOL/DOGE/XRP.

The data is Binance perp 1h bars from 2020 to 2026-09, with 12bp fees, funding, and liquidation from the hourly
lows. The tests catch 3 planted bugs. Building it found a dead condition of my own ("20-day high" compared the
close with a HIGH, so it almost never fired).

**Holdout 2024-03-31 on** (`logs/day_long.txt`):
- **Long every day loses:** −0.09 to −0.13% a day on 4 of 5 coins, after fees and funding.
- **No filter is EDGE.**
- **Indicators picked on 2020–23 failed on 2024–26.** The per-coin best picks lost 45–173 PKR a trade at 1× on
  10,000 PKR.
- **Leverage only speeds it up.** All-in at 10× is under 1,000 PKR in 1–13 trades.

**The one thing that shows (after looking, so NOT out of sample):** a daily breakout while BTC trends up
(`20d_high & btc>ema50`):

| coin | holdout %/day | without its best 3 days |
|---|---|---|
| BTC | 0.00 | |
| ETH | +0.02 | |
| SOL | +0.58 | +0.14 |
| DOGE | +2.21 | +1.11 |
| XRP | +2.83 | +1.99 |

46–61% of the DOGE/XRP gain is November 2024. At 1–3× it grew 10,000 PKR on the three alts. At 10× and above every
coin was wiped out by intraday swings.

**Reading:** this is alt-coin momentum, the trend book's own edge, seen at one day without stops.

**Predictions** (in the file): wrong on the baseline (more negative), on the WEAK count (overlapping filters), and on
"tune picks no better" (+0.40 against −0.13, from a few days). Right on 0 EDGE and on fast ruin at 10×.

## Dead: 15-minute bars, long and short, on 10,000 PKR (2026-10-08) — `backtest/scalp_15m.py`

**The test:** `scalp_1m.py`'s test one timeframe up, on BTC/ETH/SOL/DOGE/XRP 15m perp bars from 2020-09 to 2026-08:
- 7 rules, BTC-lead and the 150 cells, long AND short;
- stop 2×ATR, targets 1R/2R, a 15-hour timeout;
- holdout from 2024-04-07.

**The bigger bar cuts the fee toll five- to tenfold:** 12bp is 0.09–0.17R, against 0.50–0.98R at 1 minute. Even so:

| fee | net-positive on both halves | WEAK | EDGE |
|---|---|---|---|
| taker 12bp | 27 of 980 | 1 | 0 |
| maker 4bp | 110 | 2 | 0 |

**The one survivor:** shorting DOGE after a 15m overbought spike in a BTC bull. On the holdout it made +0.10% a trade
(against +0.51% on the tune half), with 176 trades in 2.4 years.

**On 10,000 PKR:**
- 1× → 11,580 PKR, 3× → 13,019, 10× → 2,729;
- 20× is wiped out in 36 trades.

**Predictions:** right on the WEAK/EDGE counts. Wrong on BTC's fee toll (0.17R, not 0.35R) and on 10× being
wiped out.

## Answered: "I used to make money with just RSI" - true in some years (2026-10-08) — `backtest/rsi_only.py`

**The question:** the retail RSI trade has no stop. Buy when RSI(14) crosses under 30 or 25, then take +1% or +2%,
or sell when RSI gets back to 50 or 70. Shorts are the mirror. Every earlier test here used a 2×ATR stop, so this is
tested on its own: 15m/1h/4h, BTC/ETH/SOL/DOGE/XRP, 2020-09 to 2026-08, 12bp, funding, a 7-day cap. Tests catch a
planted stop/target tie bug.

**The classic long** (under 30, +2%, no stop), all coins and timeframes:

| year | win rate | sum of trade returns |
|---|---|---|
| 2020 | 90% | **+145%** |
| 2021 | 90% | **+558%** |
| 2022 | 81% | **−737%** |
| 2023 | 83% | **+421%** |
| 2024 | 82% | −24% |
| 2025–26 | 78% | **−639%** |

**It wins 8–9 trades in 10 in every year, including the years it loses.** The rare loss is −17% to −55% (no stop),
with dips inside a trade of up to 68%.

**Since 2024-04, on 10,000 PKR all-in:**
- 1× ends at 2,000–8,900 PKR on 14 of 15 coin/timeframe cells;
- 3× is wiped on 12 of 15;
- 5× and 10× are wiped on all 15.

**Shorts without a stop:** worse than −100%, which means liquidation. With a 4% stop, every variant is negative.

**One recent exception, picked from 60 variants:** 4h longs at RSI < 25 averaged +0.2–1.5% a trade since 2024-04,
on about 60–80 trades.

**Reading:** the user's experience is real for 2020, 2021 and 2023. The win rate is no warning of which kind of year
it is.

## Dead: RSI(14) both ways with "factor" exits instead of a stop (2026-10-08) — `backtest/rsi_factors.py`

**The user's idea:** long when RSI(14) is too low, short when it is too high, with no fixed stop. "Factors" decide when
to get out:
- RSI going further;
- a break of the 50-bar low or high from BEFORE the entry;
- BTC moving 3% against the position;
- a volume spike against a losing position;
- not in profit after 24 bars;
- a 6×ATR disaster stop.

Each was tested with and without an EMA200 trend filter: 336 configurations × BTC/ETH/SOL/DOGE/XRP, 15m/1h/4h,
2020-09 to 2026-08. The tests catch two planted bugs, but only after the test path was made long enough to tell an
exit from the data's end - twice.

**Longs, holdout average per trade:**

| exit factor | holdout per trade | win rate | worst trade |
|---|---|---|---|
| none | −0.12% | 73% | −44% |
| rsi_deeper | −0.33% | 71% | −42% |
| level_break | −0.29% | 42% | −17% |
| btc_against | −0.50% | 64% | −38% |
| vol_against | −0.31% | 55% | −26% |
| not_working | −0.05% | 60% | −34% |
| atr6 | −0.42% | 68% | −36% |

**No factor turns it positive.** Most cut winners faster than losers.

**Shorts lose with every factor.**

**The trend filter (EMA200) hurt longs in 2022** (−1.27% against −0.56% a trade) and helped in the up years.

**Picked on 2020–24:** the top 5 all lost on the holdout (−0.24 to −0.82% a trade). On 10,000 PKR:
- 1× ends at 3,300–11,400 PKR;
- 5× is mostly wiped.

The only both-halves survivors are 4h longs at RSI < 25 with a +2% target, the same exception `rsi_only.py` found.

**Predictions:** wrong on how much the factors cut the worst trade, and on the trend filter in 2022.

## CANDIDATE: the 4h "capitulation buy" - extreme RSI + a volume spike (2026-10-08) — `backtest/rsi_confluence.py`

**The search (the user's "relationship between RSI and another indicator"):**
- extreme RSI(14): long under 20/15/10, short over 80/85/90;
- confirmations alone and in pairs: support/resistance, Bollinger, divergence, a volume spike, higher-timeframe
  RSI, Stochastic, trend, BTC trend;
- about 2,000 configurations × 5 coins × 15m/1h/4h.

The fast exits are tested equal to `rsi_factors.trade()`, and the confirmations are tested causal.

**Shorts at high RSI lose everywhere. Very low RSI longs bounce.** One rule survives every check
(`--verify`: by distinct day, 4 bar phases, by year, by coin):

> **4h RSI(14) crosses under 20 AND the bar's volume is over 3× its 20-bar average → buy the next 4h open, take +2%,
> exit after 4 days if not in profit.**

| bar phase | avg per trade | tune / holdout | t by day | win rate |
|---|---|---|---|---|
| 0 | +1.61% | +1.63% / +1.58% | 6.9 | 96% |
| +1h | +1.00% | +1.55% / +0.53% | 3.8 | 91% |
| +2h | +0.91% | +0.26% / +1.45% | 3.7 | 88% |
| +3h | +1.30% | +0.96% / +1.67% | 4.5 | 92% |

Every year from 2020 to 2026 is positive (2022 +1.3%), and so is every coin.

**The honest size is ~+1.0% a trade.** Phase 0 is where it was found.

**But it is RARE:** ~13 signals a year across the 5 coins. 10,000 PKR split over the coins, 2020-09 to 2026-03:

| leverage | 10,000 PKR ended at |
|---|---|
| 1× | 11,600–12,500 |
| 3× | 11,800–19,600 |
| 10× | 0 |

A trade's deepest dip reached 29–53%.

**Status:** candidate, from the same family as the crash bids (doc 16) and the bear-breadth bounce (doc 13). It came
from the ~10th sweep of this holdout, so a forward paper record decides.

**Not adopted:**
- the 1h variants, which fade with the bar phase;
- 15m RSI < 10, where 55% of the profit is 5 days;
- divergence, which never helped.

**The capitulation buy on coins it has never seen** (2026-10-08, `backtest/capitulation_wide.py`). The frozen rule
was run on the point-in-time top-40, dead coins included, from 4h bars built from the 1h archive.

**Other coins:**
- ~44 signals a year (5.5× the majors), with an 85–93% win rate;
- +1.15 / +0.79 / +0.09 / +1.10% a trade across the 4 bar phases;
- holdout +1.31 / +0.75 / −0.22 / +1.28%;
- 24 of 27 coins positive;
- **but the t by distinct day is only +2.0 / +0.3 / −1.3 / +0.5**, because a few crash days carry big losers (worst
  −16 to −52%).

**On the majors from this data source**, the +2h phase drops to +0.15%. The phase is sensitive to quote against base
volume.

**LUNA never fired**, so its exclusion changes nothing.

**On money:** 10,000 PKR per trade makes +500 to +6,300 PKR a year at 1× depending on the phase. Signals bunch,
though: 19 on the busiest day.

**Status:** still a candidate. The direction carries to unseen coins, the confidence does not, and a top-40 paper
tracker would give a forward verdict in ~6 months.

**More frequency from the capitulation buy?** (2026-10-08, `backtest/capitulation_freq.py`,
`backtest/capitulation_breadth.py`). The grid: RSI 20/25/30 × volume 2/3/5× × 4h/1h × top-40/top-100, run in a
realistic 10,000 PKR account (3 slots, skip while full).

**Loosening trades the edge for frequency:**
- RSI 25 earns +0.1% a trade, and RSI 30 is negative;
- every 1h version loses on the holdout;
- the best phase-averaged account makes only **+395 PKR a year** at 1×.

**Why:** on a crash day the FIRST 3 signals average −0.65..+0.85% and the LATER ones +1.1..+1.8%. The first coins to
capitulate keep falling.

**The breadth idea (after-the-fact):** buy only once ≥5 coins have capitulated within 24h. On the top-40 with
RSI<20 and volume > 2×:
- ~55 signals a year;
- **+1.1 to +1.7% a trade in all 4 bar phases**;
- the 10,000 PKR account makes **+570 to +1,260 PKR a year at 1×** and **+1,280 to +3,480 at 2×**, positive in
  every phase.

K=3 was not enough. K was chosen after looking.

**Status:** the best version of this candidate. Forward paper decides.

## Dead: "study one coin (DOGE) and make 1,000 PKR a month on 10,000" (2026-10-08) — `backtest/doge_focus.py`

**The menu:** 134 DOGE strategies on 1h and 4h bars:
- RSI dip-buys and capitulation buys;
- breakouts with ATR trails, long and short;
- EMA crosses, long and short;
- the deployed Bollinger family.

All with 12bp, funding, and liquidation from each trade's deepest dip.

**The honest version of "studying a coin" is a WALK-FORWARD:** each month, trade the strategy that did best over
the previous 3/6/12 months. Over 57 months from 2021-12:

| look-back | 10,000 PKR at 1× | at 3× |
|---|---|---|
| 3 months | 1,798 | 0 |
| 6 months | 11,620 | 731 |
| 12 months | 3,177 | 8 |

- The median month is 0% or lower, and only 28–35% of months are up.
- The hindsight-best strategy (EMA 20/50, 1,040,190 PKR) is the illusion.
- Even buy-and-hold DOGE has a −3.4% median month.

**Months of +10% happen** (25–32% at 3×), always beside months that wipe the account.

**Predictions:** right on the illusion and the walk-forward. Wrong on the +10% month count, which was higher
because volatility is higher - not because of skill.

## CANDIDATE, improved: capitulation + breadth with a +5% exit, and as a machine sleeve (2026-10-08) — `backtest/capitulation_exits.py`, `capitulation_tp5.py`, `machine_capit.py`

**The setup:** the entry is frozen (top-40, 4h RSI<20, volume > 2×, ≥5 coins within 24h). Only the exit changes:

| exit | per trade, 4 bar phases | win rate | both halves |
|---|---|---|---|
| **tp5_nw** (+5%, or out after 24 bars if not in profit) | **+2.4 to +3.1%** | 80–85% | positive |
| tp2_nw (the old exit) | +1.1 to +1.7% | 92–97% | positive |
| tp10_nw | +3.2 to +4.4% | 62–68% | |
| 3/7-day holds | +2.7 to +4.7% | 58–67% | |
| ATR trailing stops | lose | | |

tp10 and the holds have deeper dips that hurt leveraged accounts.

**The tp5_nw rule, checked further** (`capitulation_tp5.py`):
- t by distinct day 2.0–3.5;
- 2022 is flat in two phases; the other years are positive;
- it is carried by the non-major coins (+2.5 to +3.3% a trade, against +0.2 to +1.8% on the majors).

**Accounts from 10,000 PKR:**

| account | per year | worst fall |
|---|---|---|
| 8 slots, 2× | +17 to +30% | 18–33% |
| 8 slots, 3× | +19 to +35% | up to 63% |
| 5× | wiped | |

I predicted +30..+80% a year: wrong, it is lower.

**As a sleeve of the machine** (`machine_capit.py`, $300, raw - point-in-time, so no haircut):
- monthly correlation with the machine is **+0.08**;
- at 1× it lifts the typical year from $1,812 to $2,072 (last 2 years: $1,625 to $1,806); at 2× to $2,295 / $2,045;
- the worst month is unchanged (−29.3% / −25.0%).

Predicted correlation ~0 and +5..+15%: right. Predicted a better worst month: wrong (unchanged).

**Breadth extended** (2026-10-08, `backtest/breadth_events.py`):
- **1h breadth longs: dead.** Holdout ≈ 0.
- **Euphoria shorts (RSI>80 + volume + breadth): dead.**
- **The 4h breadth long is a PLATEAU.** Every window (6/24h) × K (5/8) × target (3/5%) is positive in all 4 phases on
  both halves. With K ≥ 8 and +5%: +2.7 to +4.1% a trade, ~40–47 a year, and 10,000 PKR at 8 slots makes +15–25% a
  year at 2×.

## CANDIDATE - THE BEST NO-HINDSIGHT RESULT IN THE REPO: a daily trend book + the capitulation book (2026-10-08) — `backtest/tv_indicators.py`, `daily_phase.py`, `pair_books.py`

**TradingView's community favourites lose to the deployed Bollinger breakout** on 4h bars, with either exit:
SuperTrend, Squeeze, Ichimoku, PSAR, Hull, Williams %R, CCI, MFI, OBV, Heikin-Ashi and VWAP.

**The standout from that table** (so selected after looking) is the deployed entry on DAILY bars with its own exit:
- buy the next open after a daily close above Bollinger(30, 1.5);
- sell the next open after a close under the 30-day mean;
- 30-day cap; point-in-time top-40, dead coins included.

| check | result |
|---|---|
| per trade | **+7.35%**, holdout +2.0% |
| 6 day boundaries | +6.7 to +7.4% a trade, holdout +1.1 to +2.4%, t by day 2.9–3.4 |
| 10,000 PKR, 8 slots, 1× | +69 to +117% a year (10 random same-day orders) |
| worst fall | 45–63% |
| 2022 | −7.3% a trade |

It earns in bull runs. The capitulation book earns in crashes (90% of its trades are with BTC under its 1000h mean).

**THE PAIR** (half the account each, 8 slots each, 1×, `pair_books.py`):
- **+47 to +59% a year** (median +51%);
- worst fall **25–34%**, worst month −12%;
- months up 47%, median month −0.2%, 22% of months at +10% or more;
- **last 12 months +66%**.

By year: 2020 ~+60%, 2021 ~+350%, **2022 −21%**, 2023 ~+31%, 2024 ~+27%, 2025 ~+20%, 2026 to September ~+33%.

The result is the same for all 4 capitulation phases and all 10 orderings. At 2× the daily book is liquidated.

**What it is:** two simple rules, both point-in-time, robust to bar phase and slot order. On paper it is the strongest
combination found. It is still lumpy: half of months are flat or down.

**What it is not:** proven forward. The daily book was picked from a table after looking, and the capitulation entry
came from ~10 sweeps of this holdout. A forward paper record decides.

## THE PAIR, DIAGNOSED AND FIXED: "machine v3" on point-in-time books only (2026-10-08) — `backtest/pair_lab.py`, `mn_capped.py`, `pair_full.py`

**The user's goal:** "see where we are losing gains, fix it, adjust to every type of market."

**The diagnosis** (`logs/pair_lab_diagnosis.txt`):
1. The capitulation half is idle 95% of days.
2. The daily book skips 53% of its signals because its slots are full, and the skipped signals are as good as the
   taken ones.
3. The pair loses in BEAR months (−2.1% a month) and is weak in chop (+2.2%).
4. Costs are only 1.6% of gross.

**The fixes, each alone and then across phases:**

| fix | result | verdict |
|---|---|---|
| cap 60 days | evens the halves (+56%) | small |
| more slots | less exposure, not more return | no |
| one shared pool | raises the tune half and LOWERS the holdout | no |
| BTC 1000h gate | the holdout falls across phases | **dropped** |
| **the market-neutral book (doc 10) at 0.5×, each coin-week capped at +100%** | **+82–90%/yr** | **kept** |
| **the bear breadth sleeve (doc 13) at 1×** | bear months **+6.6%**, every year positive | **kept** |

The MN cap matters: uncapped, 2026's AKE/RIVER/BEAT pumps carried the MN book to +374%.

**THE SYSTEM:** daily book + capitulation book (half each, 1×) + capped MN ×0.5 + bear sleeve ×1. Every component is
point-in-time with dead coins, so there is no haircut. Over 6 phase combinations × 10 orders:

| | result |
|---|---|
| growth | **+133%/yr** (5th–95th +123..+144) |
| tune / holdout | +172 / **+83** |
| worst fall | 40% |
| months up | 65% |
| median month | **+4.6%** |
| average month by market | bull +13.3 / chop +3.2 / **bear +6.6** |
| months at +10% or better | 40% |
| months at −5% or worse | 14% |

By year: 2020 +124%, 2021 +799%, **2022 +64%**, 2023 +39%, 2024 +21%, 2025 +100%, 2026 to September +132%.

**Caveats:**
- The daily and capitulation books came from today's searches.
- The MN book's live leg lost money in its first two weeks (combo_paper, −$13).
- The overlays share margin, at up to ~2.5× gross.
- Forward paper decides.

**The last two pain points** (`backtest/pair_tweaks.py`):
- The chop dial (MN ×1 in chop days) lifts chop months from +3.2 to +5.0% and growth to +150%/yr, but deepens the fall
  from 40% to 48%. It is a risk dial, not a fix, and not the default.
- The 21-day equity anchor on the daily book changes nothing. Dead here.

**Capital floor** (`backtest/pair_min_capital.py`): at 10,000 PKR the pair cannot trade at 8 slots per book. Every
position would be $2.23, under Bitget's $5 minimum.
- From 25,000 PKR it trades fully: 0% refused, +51%/yr.
- At 10,000 PKR only a concentrated 3-slot version fits: +63%/yr, but a 57% fall and a −23% worst month.
- The full machine v3 needs roughly 100,000–150,000 PKR, because the MN overlay and the bear sleeve spread thinner.

## Machine v2 × v3: MIX B (2026-10-08) — `backtest/machine_mix.py`

**MIX B** = v3 (the pair + capped MN ×0.5 + bear sleeve) + v2's trend book at 0.5× + v2's crash bids. On $300 over 12
months (6 years / last 2 years):

| | MIX B | v2 |
|---|---|---|
| typical year | **$1,406 / $1,355** | $1,812 / $1,625 |
| bad year | $722 / $1,029 | $725 / $1,060 |
| worst year | **$290 / $480** | $222 / $454 |
| worst month | **−16% / −16%** | −29% / −25% |
| biggest fall | 45% / 38% | 57% / 45% |
| months up | 64% / 68% | 57% / 64% |

MIX B keeps about 80% of v2's typical year with about half its worst month. Everything at full size (MIX C) adds a
little return for v2-like risk. Prediction: right.

## "v2.1": today's two books added to the running bot (2026-10-08) — `backtest/v2_addons.py`

Asked: add only what helps to the bot that is already running, and make its worst month less bad. Tested against the
"just bet smaller" line (v2 × k): an add-on counts only if it earns more than a smaller v2 at the same worst month,
on all 6 years and on the last 2. Today's books are marked to market here (pair_lab.account booked them at close),
and the daily book's cap exits now free their slot at the close, not the open (`logs/v2_addons.txt`).

| $300, 12 months (6 years / last 2) | typical | worst month | biggest fall |
|---|---|---|---|
| v2 as running | $1,812 / $1,625 | −29.3% / −25.0% | 57% / 45% |
| **v2 + capitulation book + daily book, everything ×0.75** | **$1,777 / $1,773** | **−21.1% / −20.2%** | 53% |
| the same at ×1 | $2,529 / $2,566 | −27.3% / −26.2% | **64%** / 50% |

- **The daily book does the work.** Alone it beats the line by +43% / +41% and makes the worst month 1.5 points less
  bad (23 of 30 orderings × phases). The capitulation book adds +4–10% and never moves the worst month.
- **Swapping v2's MN for the capped one fails** (−6% to −18% at the same worst month).
- **Caveats.** The daily book was picked after looking. Alone it makes +64–68%/yr on the tune half and +24–31% on the
  holdout: it holds, at under half the rate. By year the ×0.75 mix beats v2 in 2020–21, ties 2023–25, and loses
  2022 (+5% vs +27%) and 2026 (+330% vs +454%). Four of the add-ons' six best months are in 2021.
- **CORRECTED the same evening** (see the combination sweep below): the -21% row sat on the market-neutral book's
  lucky rebalance day. Measured honestly, the add-ons buy about one point of worst month, plus return.
- **Predictions:** 3 right, 4 wrong; the wrong ones are listed in the file. The cap-exit fix *raised* the daily
  book's growth (+0 to +5 points), so the early slot release had not flattered it.


## The combination sweep: every untested combination of what worked, then the thin kills (2026-10-08)

Asked (goal): "run every type of combination we haven't run for the things which worked ... then see what we have
claimed not working with very less backing behind that claim". About 150 variants, each with its prediction written
into its file first, each judged against "just bet smaller" (the base's own leverage line) on both halves and every
bar phase. With that many tries on one mined holdout, a few passes are expected by chance; the ones below are
consistent across every phase and have a mechanism, and still go to forward paper before money.

**What passed.**
- **The capitulation book, improved** (`capit_combos.py`, `capit_stack.py`, `logs/capit_combos.txt`,
  `logs/capit_stack.txt`): only coins down >= 10% over 24h, bought with a limit 2% under the signal close (live for the
  next 4h bar). ~30 trades a year, +3.9% / +4.4% a trade (base +2.4% / +3.1%), 1x fall 4% (base 12%); passes in all 4
  phases, also when a limit fills only on a 0.3% trade-through. 4 of 28 single changes passed (BTC down 5%, coin down
  10%, limit 2%, limit 4%); stacking adds nothing beyond the limit. Stops ruin it; market filters fail.
- **A short-leg exit for the market-neutral book** (`mn_combos.py`, `logs/mn_rebalance_days.txt`): see the risk below.

**The finding that matters most: the market-neutral book's rebalance day decides whether it survives.** Every MN
figure in this repo is one rebalance day. On the 7 days, six are fine and one is WIPED OUT on the holdout: the week of
2025-09-12 lost 99% (MYX squeezed the short basket). v2's published machine figures sit on a lucky day: with the day
rotated (`machine_combos.py`), v2's worst year is $17 from $300. The live bot is exposed too: its 30% disaster stop is a
backstop that the netting re-enters two minutes later, so it is no exit. A short-leg BOOK exit at +50% (out of that
name until the next rebalance) keeps the average (Sharpe +1.06 / +1.31 vs +1.06 / +1.33) and removes the wipe-out
(worst week -29% instead of -99%, falls 29-42%). The capped MN (v3) also survives all 7 days.

**The machine, measured honestly** (`machine_combos.py`, `logs/machine_combos.txt`; $300, 6 years / last 2):

| | typical | worst month | worst year |
|---|---|---|---|
| v2 as published (MN on its lucky day) | $1,812 / $1,625 | -29.3% | $222 |
| v2, MN on the rotating day | $2,385 / $3,134 | -35.6% | **$17** |
| v2 safe (MN short-leg exit +50%) | $2,248 / $2,741 | -31.3% | $196 |
| v2 safe + daily + capitulation improved | $3,036 / $4,767 | -35.3% | $191 |

The last row beats "v2 safe, smaller" by +11% / +34% at the same worst month. Scaled to the published v2's typical
year, its worst month is -26.0% (v2 safe -27.2%, published v2 -29.3%). **This corrects the "v2.1" entry above**: its
-21% sat on the lucky MN day; honestly measured the add-ons buy about one point of worst month, plus return.

**Caught before it was believed.** Regime weights across the machine read +45% / +70% over the line. The trend book
books each unit when it CLOSES, so weighting its daily series by the label of the close day sizes a position after its
outcome. Weighted at entry (`regime_weights.py`) it fails: -12% on 6 years.

**What failed** (each file holds the numbers):
- the daily book: 0 of 37 changes (`daily_combos.py`), 0 of 4 stacks (`daily_stack.py`). **Its holdout rests on 5
  trades** (MYX, RIVER, AKE, PIPPIN, SOON/PENGU, 2025-26): without them its holdout is -30% to -39% a year;
- v2's trend book x breadth / daily agreement / capitulation: 0 of 4 (`trend_combos.py`);
- crash bids x the capitulation signals: 0 of 5 (`wick_capit.py`);
- the bear sleeve x the capitulation signal: 0 of 4 (`sleeve_combos.py`);
- MN lookbacks, holds, scores, regime switches: none beats the base's Sharpe (`mn_combos.py`);
- volatility targeting on the machine (`machine_combos.py`).

**The thin kills, re-tested (phase 2).**

| claim | its old backing | re-test | now |
|---|---|---|---|
| "indicators are exhausted; they all detect the same thing" | longs on 9 hindsight coins, hourly | 9 families + an ER filter on DAILY bars, PIT top-40 (`daily_families.py`) | **stands, now properly backed**: bb(30,1.5) is first of 22 daily entries; Keltner closest |
| funding carry is untradeable | one week (MYX -107%) | 7 rebalance days, +50% short exit (`carry_revisit.py`) | **stands**: no wipe-out, but holdout Sharpe +0.28 - it faded |
| stops on the MN short leg cost return (`mn_stop.py`) | one rebalance day | 7 days, a book exit (`mn_combos.py`) | **reversed**: free on average, removes the wipe-out |
| "volume is anti-useful in crypto" | hourly VSA, 1m setups | the capitulation book with and without it (`capit_volume.py`) | **wrong as stated**: needed in the base book, redundant once the 10% drop is required |
| pairs stat-arb | 4 settings | 6 more (`pairs_revisit.py`) | **stands**: all negative on both halves |
| the 1h capitulation buy | one test, holdout ~0 | with today's two fixes (`capit_1h.py`) | **stands**: 3x the trades, holdout +5%/yr vs the 4h book's +13-15% |
| "every reversal idea fails" | early hourly tests | - | **too broad**: the capitulation book, crash bids and the bear sleeve are reversal buys that work, all keyed to forced selling |

**Phase 2 completed the same night: [doc 21](21-graveyard-audit.md) audits EVERY kill** (doc 02, doc 11, docs 12-13,
this session), rates its backing, and re-tests every thin one the data allows: the pre-fix engine kills
(`engine_rescore2.py`, `sleeve_risk_control.py`), long BTC / short alts on a PIT basket (`bear_alpha_pit.py`), MN basket
width on 7 days (`mn_width7.py`), crash bids up in chop (`wick_chop_size.py`), the ICT sweep / prior-day fade
(`sweep_reclaim.py`) and memecoin graduations on later days (`meme_days.py`). Nothing came back as a book; one kill
reversed (the MN short-leg stop) and two claims were too broad ("volume is anti-useful", "every reversal fails").


## The archive-hole bug, the re-run, and the last combinations (2026-10-09)

**The bug** (`backtest/capitulation_wide.halt_cut`, test in `tests/test_capitulation_wide.py`). Every loader of the perp
archive cut a coin's history at its first gap over 48 hours, meant for real halts (BNX's 21-day stop). Two ARCHIVE holes
- 2022-02-26..28 (73h, 47 coins) and 2022-04-01..02 (49h, 48 coins), prices a few percent apart across them - cut 51
coins (XRP, SOL, LTC, NEAR, FIL, TRX, XLM...) at 2022-02-25: **16.4% of all point-in-time top-40 coin-months were missing**
from every daily-book, capitulation and pair result. Now only a gap of more than 7 days cuts. All 34 affected scripts
were re-run; their logs are current and their docstrings say so.

**What changed** (all point-in-time, 12bp + funding):

| | before the fix | after | file |
|---|---|---|---|
| plain capitulation book (+5% exit) | 57-62 a year, +2.4..+3.1% a trade | **73-78 a year, +1.9..+2.7%** | `logs/capitulation_exits.txt` |
| the pair (daily + capitulation, half each, 1x) | +48%/yr, fall 27%, 2022 -21% | +50%/yr, **fall 36-37%, 2022 -32%** | `logs/pair_books.txt` |
| the daily book alone, 8 slots 1x | +69..+90%/yr | +83..+100%/yr, falls 53-61% | `logs/daily_phase.txt` |
| machine v3 | +133%/yr, holdout +83 | **+140%/yr, holdout +86**, fall 40% | `logs/pair_tweaks.txt` |
| MIX B ($300, 6y / 2y) | $1,406 / $1,355 | $1,487 / $1,370, worst month -17% / -15% | `logs/machine_mix.txt` |
| **capit2's rule** (coin -10% + limit 2%, 0.3% trade-through) | passed, 4 phases | **still passes, 4 phases**: +3.0% / +4.3% a trade vs +1.5% / +3.1%, ~35 a year, 1x fall 10% vs 22% | `logs/capit_stack.txt` |
| **"E"** (v2 + MN short-leg exit + daily + improved capitulation), MN on every weekday | worst month -26.0% at v2's typical year | **-21.0%** (v2 safe -27.2%, published v2 -29.3%), fall 42% vs 57% | `logs/machine_combos.txt` |

The 2026-10-08 correction ("the add-ons buy ~1 point of worst month") was itself made on the truncated data; on the full
data they buy ~6 points over "v2 safe" and ~8 over the published v2, plus return. Three of the four single capitulation
improvements now fail one phase by a hair; their stack (capit2's rule) still passes.

**New passes on the corrected data - candidates, after paper:**
- the daily book's exit under the 20-day mean, and its BTC exit (out when BTC closes under its own 20-day mean): both pass
  all 3 day boundaries (`logs/daily_combos.txt`); stacked, the fall drops 65% -> 48% at about the same growth
  (`logs/daily_stack.txt`);
- the market-neutral book ranked HALF by 30-day momentum and HALF by RSI(14): Sharpe +1.39 / +1.36 vs momentum's +1.06 /
  +1.31 over the 7 rebalance weekdays, worst weekday +1.21 / +0.90 vs +0.85 / +0.76, falls 27-38% vs 29-42%
  (`backtest/mn_blend_rsi.py`). Found while re-testing an old kill; RSI was one of two indicators tried.

**Every combination, finished:**
- all 728 machines (6 books x 0 / 0.5 / 1, `backtest/machine_factorial.py`): the pick made on the first 4 years is every
  book at full size ("E"), and on the 2 years it never saw it ranks first of 728 - but its worst month there (-30.4%) is
  past the -28.2% ceiling it was picked under;
- every pair of filters (`backtest/filter_pairs.py`): daily book 1 of 78 (chance), capitulation 8 of 136 (each a crash
  condition plus a market filter), and **0 of 26 single changes improve capit2's rule**;
- trend book x today's signals 0/4, crash bids x capitulation 0/5, sleeve x capitulation 0/4, regime weights (no leak)
  fail, the 1h capitulation still loses to the 4h book (their logs).

**The remaining thin / moderate kills, re-tested** (`backtest/moderate_retests.py`, `logs/moderate_retests.txt`):
grid bots on 15 more coins 4 of 120 profitable - stands; the hourly trend engine on the PIT top-40 vs the 12 coins
(corrected engine, no funding on either) holdout -0.75 vs +3.67 %/mo (main), +3.46 vs +12.48 (triple) - "breadth does
not scale" stands; meta-labelling fails - stands; VWAP reversion on daily bars is positive a trade (+0.7..+2.7%) but a
LOSING account (holdout -23..-39%/yr, falls 78-88%: `backtest/vwap_daily.py`) - stands; cross-sectional indicator
ranking is NOT worse than momentum - that claim was wrong (above); memecoin graduations on the collector's full record
(309 graduates, 9 days: +1 min / +1h -54.6%) - stands.

**Also found and fixed: `backtest/tv_indicators.py` had been a LIBRARY** (supertrend, keltner, ttm_squeeze, psar, aroon,
dmi, ichimoku, chandelier) imported by `tv_test.py` and `tv_crosssec.py`, and the 2026-10-08 study was written under
the same name and replaced it. The library is restored verbatim (from 91c9dbe) inside the same file; all importers work.


## The re-tested kills swept over their parameters, and the indicator families inside the machine (2026-10-09)

The audit (doc 21) had re-tested each thin kill at one or a few settings. A kill that holds at one setting can hide a
working neighbour, so each was swept (`backtest/kill_sweeps.py`, logs `logs/kill_sweeps_*.txt`), and the two partial
reversals were checked again (`backtest/kill_followups.py`, `logs/kill_followups.txt`):

| kill | swept over | now |
|---|---|---|
| pairs stat-arb | formation 60/90/180 x entry z 1.5/2/2.5 x stop 4/none (18) | **stands**: all 18 negative on both halves |
| meta-labelling | logistic / boosted trees x keep top 50/30% (4) | **stands**: all 4 fail the line |
| memecoin graduations | all 12 entry x exit pairs + 3 wait-for-proof, full 9-day record | **stands**: all 15 negative (`logs/meme_days_all.txt`) |
| grid bots | 4% / 5% spacing, gated, 20 survivors + 20 coins that DIED | **stands**: gated wide grids look positive on survivors (holdout median +2..+3%/yr) and LOSE on coins that died (-4%/yr) - survivorship |
| VWAP reversion (daily) | VWAP 10/20/50 x stretch 1.5/2/2.5/3 ATR x hold 5/12/20 (36), as accounts | **partly reversed**: one corner - VWAP(10), 2.5-3 ATR under - is a positive account at all 3 day boundaries, but small (+1..+8%/yr at 1x, 3-15 trades a year): the capitulation buy again |
| funding carry MN | window 3/7/14/30 x short exit none/+50/+100% x basket 10/20% (24), 7 weekdays | **partly reversed**: 7-day window, 20% basket, +50% exit: Sharpe +1.40 / +0.74, positive on every weekday; as a 0.5x overlay on the MN blend it lifts both halves (+1.21 / +1.07 vs +0.97 / +0.96 on one date grid) - uncorrelated (-0.01). A candidate |
| cross-sectional indicators | RSI 14/7, MACD histogram, ROC 14, Stochastic, CCI, %b; blends 25/50/75% | no single indicator beats momentum on the holdout; **momentum + RSI blends at 25-50% beat momentum on both halves** (the candidate) |

**The indicator families inside the machine** (`backtest/family_machine.py`, `logs/family_machine.txt`): each of 11 daily
entries x 3 exits as machine E's daily book, against E's own size line. Only ONE beats E on both spans - the same
Bollinger entry with the **20-day-mean exit** (+8% / +13% at the same worst month). Every indicator family loses to bb
in the machine (Keltner the closest, -6..-25%). The 20-day + BTC-exit stack that passed on its own (daily_stack.py)
HURTS inside the machine (-13% / -11%): the trend book already exits on BTC's break, so the daily book's second BTC exit
only gives up return. Prediction (no family beats bb by > 5%) right; (the BTC-exit stack helps the machine) wrong.

**Candidates for paper, after all of this** (none is in any bot): the daily book's 20-day-mean exit; the market-neutral
book ranked half by momentum / half by RSI; funding carry (7-day, 20% basket, +50% exit) at 0.5x beside it.

## Dead: "analyse DOGE today and scalp it live" - the fee wins; the book's edge lasts 10-30 seconds (2026-10-09)

**The user's method:** skip years of backtests, read the coin today (levels, indicators, the live chart in TradingView),
predict, and forward-test in real time. Tested three ways, every prediction registered before the data:
- **`backtest/doge_adapt.py`** - the method's honest history: every 6 hours pick the best of 228 scalping rules (VWAP
  fade, Bollinger re-entry, volume breakout, EMA pullback, level bounce, opening range, RSI fades; 1m/5m; ATR brackets)
  over the trailing 6h..7d and trade it for 6 hours, on 90 days of Bitget's own 1m DOGE bars. **Every window loses
  -0.09..-0.15% a trade at 12bp - the fee; before costs the pick makes ~0 over the next 6 hours.** 0 of 228 rules are
  positive over the 90 days. Rankings persist (rho +0.45..+0.60) only because busy rules pay the most fees every window.
- **`backtest/doge_bigtarget.py`** - "aim for 1%": 790 rules with 0.5-2% targets and 4h/24h time stops win exactly as often
  as RANDOM entries at every bracket and lose the fee. Accuracy needed falls with the target (62% at 0.5/0.5, 37% at 2/1)
  and accuracy got falls with it (49.8% -> 38.2%), as a coin flip does. 2 of 790 positive on both halves.
- **`book_rec.py` / `liq_rec.py` / `backtest/doge_book.py`** - the scalper's information, recorded live for ~2 hours at 1 s:
  Bitget and Binance books and trades, BTC, OKX liquidations, Binance open interest (262 min, 7,795 snapshots, halves by
  snapshot count). Book imbalance, microprice and the Binance-Bitget gap predict Bitget's next 10 s on both halves (IC
  +0.20..+0.25) and still at 60 s (+0.10..+0.28) - **but the move in their extreme decile is ~1-2bp at every horizon**.
  Maker net -2..-3bp, taker -11..-13bp. It is the market makers' edge: they collect the spread and pay ~0 in fees.
- **Live** (`doge_live.py`, rules frozen 16:35 UTC, stopped 21:09 UTC): 7 trades, 29% won, -1.41% net at 12bp (-0.85% at
  4bp) - `logs/doge_live/rule_trades.csv`. Two range-edge limit calls (0.8% targets) never filled. Too few to judge
  anything alone; the 90 days are the evidence.
- **Leverage** does not help: Bitget charges 0.06% of ORDER VALUE (verified on the demo account's own fills at 20x), so the
  fee scales with the position exactly as the move does.
**Reading:** on DOGE at retail costs and home-PC speed, the predictable part of the move is smaller than the round trip at
every horizon tested - seconds to a minute (book), minutes (1m/5m rules), hours (1% brackets). What is left is slower trades on forced
flows (capit2, liquidation cascades), where a multi-percent move dwarfs the fee and fast bots do not hold.


## Dead: the crypto scalping tests on NASDAQ, US30, gold and forex at Exness spreads (2026-10-11)

**The user:** "the scalping strategies we applied on crypto ... and also other that we didnt apply on nasdaq or forex -
give it a shot". The DOGE tests died on the fee (12bp = 1.73 one-minute ATRs on DOGE). An Exness Standard account charges
only the spread: **0.12 (gold), 0.21 (US30), 0.24 (NASDAQ) of a one-minute ATR, 0.57-0.68 on EURUSD / GBPUSD / USDJPY**,
7-14x cheaper than DOGE on the indices and gold. So the question was whether the rules carried a small gross edge the
crypto fee had hidden. Data: **`backtest/mt5_1m.py`** builds 1m MID bars from every Exness tick with the spread at each
minute (MT5 caps bars at 100,000 but not ticks): 2026-01-01 .. 2026-10-09, six instruments, holdout from 2026-06-19.
Predictions registered in each file before its run.
- **`backtest/cfd_scalp.py`** - doge_adapt's 228 rules (ORB at 09:30 New York; clock time stops), 1,368 instrument-rules:
  **0 survivors** (t > 2 by day on both halves). Before ANY cost the median rule makes -0.08 / -0.02 / -0.03bp a trade on
  NASDAQ / US30 / gold and +0.00..+0.03bp on forex; 38-64% of rules are positive at zero cost - a coin flip. Net positive:
  3% NASDAQ, 4% US30, 18% gold (its long breakouts; best +4.95bp a trade, t +1.1 / +2.0), 0-1% forex. The user's
  "pick the recent winner" walk-forward loses at every window on every instrument and never beats a random positive rule.
- **`backtest/cfd_bigtarget.py`** - doge_bigtarget's bigger brackets (0.25-1.0 of a daily ATR, 4h / 24h, spread + swap)
  on 5m/15m/1h entries, 4,820 rules: **0 beat random entries by 2 se on both halves**; the rules' win rates sit within
  2 points of random's in 27 of 30 instrument-brackets and 3.2 points under it in one. A random long did not pay either
  (NASDAQ +2.6 / -3.2bp by half, gold -0.9 / -2.1bp).
- **`backtest/ustec_seconds.py`** - the order-book question without a book (Exness has none): NASDAQ's own tick stream,
  181 days, 412,680 samples in the cash session. The next 5-60 s ARE predictable - every price feature reverses on both
  halves (IC -0.007..-0.033, t to -10), a tenth of DOGE's book - but a ridge model's top-1% trades move +0.00..+0.14bp
  gross against a 0.82bp spread: **net -0.73..-0.92bp a trade at 0.5 / 1 / 2 s latency**. The spread's own IC (+0.03..
  +0.11) is a rank effect, not money: when it is wide, mid, ask and bid move -0.13..+0.03bp. With `nq_leadlag.py` (no
  lag to the CME futures), the seconds scale on Exness is closed.
**Reading:** on DOGE the cost was the visible killer; here the cost is 7-14x smaller and the rules still lose, because
before costs they make nothing. These entries carry no direction on any of the seven markets tested, at seconds,
minutes or hours. A cheaper market shrinks the loss to the spread. It does not turn a coin flip into an edge. His own
pattern as a rule had already died on NASDAQ (`his_micro.py`, 18 of 18 cells); what still wins on NASDAQ is HIS
direction at HIS moment (his_strategy.md s35-47), which only his live signals carry.

## CANDIDATE (not dead): NASDAQ's sharp down days, bought and sold on the first bounce (2026-10-11) — `backtest/ndx_capit.py`, `backtest/ndx_capit_check.py`

**The user:** "something we tried on crypto should work on NASDAQ - we have clues of our own from his strategy". The
crypto family that survived everything is buying FORCED selling (capit2, crash bids); his usable clue is the trade's
shape - NASDAQ, a quick exit, no stop. Equity indices have that mechanism on the daily scale (the published RSI(2) / IBS
reversal, 2004-09) and a 27-year record (^NDX 1999-2026, four bear markets). Predictions registered in both files.
- **22 of 192 cells pass** (net > 0 with t >= 2 on both halves AND above a buy-every-day control per day in the market).
  The strongest, sold on the first close above the 5-day average (max 10 days), 1x, NASDAQ CFD costs:
  RSI(2) under 10 - 12 a year, won 70%, **+0.95% a trade** (+1.18% t 4.8 / +0.57% t 3.5), CAGR +11%, fall 22%;
  three down closes - +1.02% (t 6.1 / 3.9); a close under Bollinger(20,2) - +1.29%, 6 a year, fall 13%.
- **Checked before belief:** a smooth plateau (36 neighbour settings all positive on both halves); half the edge after
  publication, still positive; since 2020 t 1.5-5 and since 2023 stronger (NASDAQ's AI rise); Exness USTECm's own 16:00
  close tracks it (corr 0.9989).
- **Against it:** frozen on five other indices it is weak - 3 of 120 cells pass, all on the S&P; Dow, DAX, Nikkei and
  STOXX are small and insignificant. It is a NASDAQ effect and rests on NASDAQ staying NASDAQ. The worst move against a
  trade was **20-26%** (2000-01, 2008): at Exness's 0.05-lot minimum (~7x on $221) that is ruin. **Bitget's QQQ/USDT perp**
  ($5 minimum, tracks the close at corr 0.9993) can hold it at 1-2x on $221.
- **Size of the prize:** ~10-12% a year at 1x, in the market 15-20% of days - about $25-50 a year on $221 at 1-2x. Real,
  modest, and not 10% a month. Next, if anything: a forward paper record of ONE frozen rule (RSI(2) < 10 at the close, out
  above the 5-day average) - doc 22 decides whether that counts as a new book.

## Dead: the NASDAQ dip-buy, and his "join the move after a pause" at the daily scale, on forex, gold and silver (2026-10-11) — `backtest/fx_capit.py`

**The user:** "take something from the research on him and the strategies that worked or failed on crypto, for forex -
not copying him." Carried over: crypto's forced-flow bounce, which passed on NASDAQ (`ndx_capit.py`); his one usable
clue, entering a young move right after a short pause against it, as its daily form (buy dips only above the 200-day
average, sell rallies only below it); his shape (a target with no stop). Both directions, since forex has no drift;
Exness spreads and the swap of the side held. Predictions registered in the file.
- **On Exness's own prices (MT5 1h -> New York 17:00 days, 2020-2026): 1 of 1,296 cells passes** (GBPUSD, 14 trades -
  chance). Median cells -0.05..+0.09% a trade on the majors; gold's dip-buys +0.03% a trade through its 2024-26 rise;
  silver nothing. The trend gate changes nothing (better in 55% of cells, at ~0).
- **On Yahoo's 2003-2026 bars 80 cells "pass" at t up to +25 - a data bug.** Yahoo's forex daily bars are not
  consistent: the open sits ~27bp from the previous close (Exness ~1bp), the close is not the end of the high/low window
  (92-95% "bounces" after a close near the low; Exness 49-50%), and the bars are dated a day off Exness's. Trap added to
  CLAUDE.md s3. `fx_anomalies.py`'s T8 (month-end USD) read these closes, so it was re-measured (rule 9) in
  `backtest/fx_t8_exness.py`: the kill stands (below, in the 2026-09-25 entry).
**Reading:** the NASDAQ bounce is a property of a rising, volatile stock index. Forex, gold and silver at daily scale
show no bounce to buy or rally to sell, with or without his "pause". What stays standing on Exness: `fx_tsmom.py`'s
12-month trend on a swap-free account (+5.5%/yr at 10% volatility, from indices and commodities, not forex).

## Dead: NASDAQ's last hour following its first ("market intraday momentum") - NASDAQ scalping closed (2026-10-12) — `backtest/ndx_close_momo.py`

**Why tested:** the council's one remaining NASDAQ scalping idea, the only minute-scale effect with a forced counterparty
(dealer gamma hedging and leveraged-ETF rebalancing near the close; Gao, Han, Li, Zhou 2018). Registered with a kill line:
if it fails, NASDAQ scalping is closed. Flat by 16:00 ET (no swap), 0.8bp a round trip.
- **NQ futures 2024-04 .. 2026-09 (588 days):** the return from the previous close to 10:00 ET has a correlation of
  **-0.005** with the 15:00-16:00 hour. Its sign is right 53.2% of days, **+0.26bp a day** (t -0.19 / +0.54 by half);
  big first moves do worse (-0.24bp); adding the 14:00 hour -1.76bp. Always-long the last hour -1.25bp.
- **Exness USTECm, the paper's exact half-hours (242 days):** +0.41bp a day, and the halves flip sign (-2.59 / +4.89bp).
**Reading:** not present in NASDAQ in 2024-2026. Every NASDAQ horizon is now tested - seconds (`ustec_seconds.py`,
`nq_leadlag.py`), minutes (`cfd_scalp.py`), hours (`cfd_bigtarget.py`), the session close (this) - and none carries a
direction worth the spread. **NASDAQ scalping is closed.** What stands on NASDAQ is the daily dip-buy (CANDIDATE above).

## Dead as a trade, true as an explanation: thirty years of what DRIVES forex (2026-10-12) — `backtest/fx_macro_data.py`, `fx_drivers.py`, `fx_surprises.py`

**The user (/goal):** "run these economic data and all other data that drives forex and correlation with them - the last
30 years". Every earlier forex test read price patterns; this reads the INFORMATION forex is said to move on. Fed H.10
noon rates 1996-2026 for EUR JPY GBP AUD NZD CAD CHF; H.15 yields; BIS policy rates; OECD 3m / 10y rates; CFTC
speculator positioning; VIX, S&P 500, oil, gold, copper; ForexFactory's calendar with forecasts, 2007-2026 (6,810
release groups). Predictions registered in each file. Two questions kept apart: what MOVES WITH a currency in the same
period (explains, cannot be traded) and what PREDICTS the next period (the only kind that can).
- **What moves with forex** (`fx_drivers.py`, same month): risk appetite - the S&P 500 (AUD +0.52, CAD +0.51, NZD +0.46;
  VIX the mirror) - copper and gold (+0.25..+0.53), oil for CAD (+0.38), and the US 2-year yield (dollar up when it
  rises: JPY -0.40, CHF -0.29). Central-bank policy-rate changes move with nothing (-0.05..+0.05): markets price the
  2-year yield before the bank acts.
- **What predicts forex** (next month): nothing - 77 driver-currency correlations all within +-0.13.
- **11 trading rules on Exness costs, 0 pass** (every Holm p 1.00): carry earns +2.6%/yr only where carry is paid
  (Exness pays none: -0.26%/yr); commodity-led CAD / AUD +0.74%/yr then flips on the holdout; fading crowded CFTC
  positioning, following positioning changes, rate changes, the US 2-year, risk and momentum all lose.
- **Data surprises** (`fx_surprises.py`): a release moves its currency the surprise's way ~60% of days (+15bp; at minute
  resolution 16 of 23 US releases in 2026, +6bp in 5 minutes). After that, nothing: the drift from the first noon is
  -0.9..-2.9bp at 1-5 days (t under 1), +5 to +60 minutes -0.2bp. Big US surprises keep 9% of their jump the next day.
- **2-year yield gaps** (`fx_rates2y.py`, added after the user's "you did not have all the information"): daily 2y
  yields from the Bundesbank, Japan's Ministry of Finance, the Bank of Canada and the SNB (the BoE, RBA and RBNZ were
  unreachable from this PC). The 2y gap is the rate measure that moves with forex - same month EUR +0.40, JPY +0.41,
  CAD +0.31, CHF +0.27, where the policy-rate gap showed ~0 - and it predicts nothing (next week / month <= 0.09).
  Trading the currency back to its rate-implied fair value: +1.3%/yr at Exness, holdout only (t -0.3 / +1.7); the
  currency catching up to its rate move: -1.1%/yr; following the 2y trend: negative. 0 of 4 pass.
- **Who is positioned** (`fx_tff.py`, the CFTC's Traders in Financial Futures, 2006-2026, 1,059 weeks): in the same
  Tuesday-to-Tuesday week hedge funds add as a currency rises (EUR +0.30, JPY +0.32, AUD +0.24), asset managers too
  (+0.12..+0.28), and the banks take the other side (dealers -0.27..-0.48). The following week: nothing (|r| <= 0.07);
  0 of 5 rules pass, all negative at Exness (fade crowded hedge funds -1.2%/yr, follow their flow -2.9%/yr).
  CBOE's currency volatility indices could not be fetched (CBOE: access denied; Yahoo: ^EVZ delisted).
- **Data surprises at minute resolution** (`fx_surprises_1m.py`, HistData.com 1-minute bars 2007-2026, 2,078 releases):
  the currency moves the surprise's way 81% of the time within 5 minutes (+14bp). Entered a minute after the number,
  +0.8bp more by +15 minutes (t +2.8) - the 0.69bp spread takes it; the next hour ~0; half a day a mild giveback. 0 of
  15 windows pass. A first run showed a +10bp "drift" at t +21: HistData's clock is New York time with daylight
  saving, not the fixed EST it documents, so summer jumps landed in the hour-after window (CLAUDE.md s3).
- **Central-bank speech tone** (`fx_speeches.py`, 8,850 BIS speeches 1996-2026, hawkish minus dovish words): the count
  is real (the Fed's tone tracks the US 2-year yield, +0.45) but a bank's tone relative to the Fed moves nothing in
  the same month, and the next-month lean (up to +0.17) flips between halves when traded. 0 of 2 pass.
- **News mood** (`fx_news_tone.py`, GDELT tone and volume of news about each economy, 2017-2026): same week -0.06..
  +0.06, next week <= 0.06; 0 of 3 rules pass. OANDA's retail order books: not reachable by the user; untested.
**Reading:** forex is driven by risk, commodities, market interest rates and data surprises - all of it priced within
minutes, none of it known early enough to trade at retail speed. With the 33 calendar tests, the scalping menu and the
daily dip / rally rules, forex is now tested from seconds to months on both price and information. The one forex-account
result standing is still the 12-month multi-market trend on a swap-free account (`fx_tsmom.py`).

## Not a market edge: the news bot's one-second window is the broker's (2026-10-12) — `backtest/fx_news_seconds.py`

**Why tested:** the user's case for a forex bot - lower costs, real information behind forex - leads to one place: a bot that
reads the official number the instant it prints and trades in seconds (the jump is 81% right within 5 minutes, but entered a
minute later only +0.8bp is left: `fx_surprises_1m.py`). Measured on Exness's own ticks, every 2026 high-impact release
(51 releases, 97 trades), entered d seconds after the stamped release at the real ask / bid:
- **US releases, out at +60 s: +6.2bp a trade at 0.5-1 s (t +3.9, 81-83% won); +0.6bp at 2 s (t +0.8); 0.0 at 5 s; -0.9bp
  at 10 s.** A one-second cliff.
- **Why:** on 15 of 18 payroll / CPI releases Exness's biggest 1-second move is in the SECOND second after 08:30:00 - its quote
  reaches the market about a second late (or its tick clock runs ~1 s behind), and its spread does not widen meanwhile.
**Reading:** two seconds after a number there is nothing left for anyone; the first second is the broker's stale quote.
Trading that is latency arbitrage against the broker - against retail brokers' terms (trades voided, accounts closed),
countered by last-look and slippage this test cannot see, and it needs the number within ~0.5 s, which free sources do not
deliver from Pakistan. Not a legitimate or durable forex bot.

## The sideways gap on the 9-book machine: four attempts dead, one size trade-off (2026-10-18)

**Why tested:** the user - "we don't have a bot for choppy markets ... try everything, we need to fill this gap too" -
and, mid-way, "in choppy markets using RSI should work I guess". Doc 20's -4.5% typical sideways month was machine v2's.
- **Measured first** (`chop_gap.py`): the running 9-book machine's typical sideways month is **-2.1%** (44% up); without the
  trend book **+7.8%**. Every other book averages >= 0 in sideways months; the trend book's typical one is -7.3%. The gap
  is the trend book, and its worst sideways months came right before bull runs.
- **Trend-entry switches** (`chop_switch.py`, applied AT ENTRY inside the machine): 0 of 5 pass. `month_regime.py`'s
  month-start BTC switch, which held on 2017-19, FLIPS between halves once applied at entry (tune $1,457 vs $3,927, holdout
  $13,315 vs $9,416) - its 2017-19 win was the booked-return attribution its own LIMIT note warned about. Kaufman's
  efficiency-ratio chop meter at half size is the best-looking (sideways month -2.1 -> +3.1%, fall -6 points) and sits
  BELOW the bet-smaller line on both halves (--control).
- **Cross-exchange funding gap** (`funding_spread.py`, Binance-Bybit 2022-26, 91 coins; Bitget's 90 days): the median gap
  is 1 bp a day, the widest 10 average 8.5 bp, fees 21 bp a round trip, and wide gaps flip within days: +0.1%/yr holdout.
- **Mean reversion gated by the chop meter** (`chop_revert.py`, PIT top-40 daily): -13..-54%/yr tune, -18..-41% holdout;
  still -2.0% a sideways month at best. Stretched coins keep going.
- **RSI in sideways markets** (`rsi_chop.py`): the retail RSI dip-buy (rsi_only.py's 115,312 trades) LOSES inside BTC-chop
  on every timeframe and both halves (-0.27..-2.27% a trade) and earns outside it - it is a rising-market trade. RSI(14) /
  RSI(2) daily reversals, gated: none positive on both halves.
- **What does fill it: a smaller trend book** (`trend_size.py`): at 0.8x the typical sideways month is 0.0%, at 0.7x +1.1%,
  with the typical year about unchanged and falls ~7 points shallower - paid for in the TOP of a 2021-type bull (0.7x on
  2020-24: good year -25%, average -38%; on 2024-26: good +7%, average -3%). Not a new edge - a size choice.
**Reading:** doc 20's "chop is closed at retail" stands for new books; the sideways gap is the trend book's bleed, and the
only lever that moves it is the trend book's SIZE. Choosing it is choosing between 2021-type upside and steadier sideways
months.

## Taking the unusual profit early, and a per-coin cap (2026-10-20)

**Why tested:** the user, after BTW (held long by three books) ran +46% then fell 19% in a day and the MN book gave back a
+$3.83 week-to-date: "for unusual profits we should take profit and exit early, they can bear fast"; and the per-coin
limit proposed after the liquidation test.
- **Daily book take-profit / protect-the-profit** (`profit_take.py`, both books reproduced exactly first): TP +30 / +50 /
  +100%, or a trail armed at +30% / +50% - every version lowers the machine's typical year on both halves (holdout $9,416 ->
  $6,271..$8,050), falls unchanged. The early exit sells the pumps that KEPT going, which pay for the book.
- **MN basket take-profit** (+2 / +3 / +5 / +8% within the week, or give-back +3% -> +1.5%): all worse on both halves;
  +2% softens the worst week (-21% -> -16%) for 40% of the holdout's typical year.
- **Per-coin cap** (`coin_cap.py`; run 1 wrongly capped BTC, the news book's hedge leg): stacking is common (a coin over 15%
  of the account on 42% of days) but the machine's big losses are market-wide - a 15% cap costs 12% of the holdout's
  typical year and moves the worst month by under a point; 25% costs ~0 and rarely binds.
**Reading:** hold-to-rule stays; the profit comes from the runs that keep going. A 25% per-coin cap is free insurance for
real money, not a return lever.

## What the outside world suggests, tested on our data (2026-10-20) - `research_ideas.py`, `dsr_check.py`

**Why tested:** the user: "search the web / research what algorithmic traders and repos do, and include what improves our
bots". Read: Zarattini, Pagani & Barbon 2025 ("Catching Crypto Trends", Donchian ensemble + vol sizing, Sharpe ~1.58
2015-25); Grobys et al. 2025 (volatility-managed crypto momentum); Barroso & Santa-Clara 2015; Quantpedia's Bitcoin
hour-of-day study; Bailey & Lopez de Prado's Deflated Sharpe Ratio; Carver's multi-speed trend + buffering; freqtrade's
lookahead checks. Most of the practice is ALREADY here (three trend speeds, causality checks, point-in-time universes with
dead coins, pre-registration, netting that skips small adjustments).
- **Donchian ensemble, as published:** Sharpe 0.85 / 0.38 (tune / holdout) on our PIT top-20 vs the daily book's 1.56 /
  1.05; replacing the daily book halves the holdout, adding it moves nothing.
- **Vol-managed MN:** -19% of the holdout's typical year for 2 points of worst week (cap 1), or flips (cap 2). Dead.
- **BTC 21:00-23:00 UTC:** +5..+8bp gross, -4..-7bp after 12bp. Dead.
- **Deflated Sharpe:** the machine's 1.72 survives ~1,000 tried ideas over 2020-26 (DSR 0.99; 0.85 at 10,000); the 2024-26
  half alone does not (0.44 at 100).
**Reading:** the published state of the art did not beat what this repo built; its most useful import is a measuring
stick - the DSR says the backtest is suggestive, not proof, which is what the paper record is for.

## Dead: a book for alt bears the BTC label misses (2026-10-22) - `backtest/alt_bear.py`

**Why tested:** two weeks of falling big alts with BTC flat; both paper accounts down 10-12%; the bear sleeve idle because
it reads only BTC's 50-day trend. The user: "can we do something about it for bears like this". The ALT label is the same
rule on the PIT top-40 alt index; ALT-ONLY = alt bear while BTC is not (14.9% of days since 2020-03, 36 episodes, median 8
days; half were followed by a BTC bear within 30 days).
- **The sleeve's breadth rule on ALT-ONLY days:** -9..-12%/yr, holdout -21..-33%, fall ~60% (`logs/alt_bear.txt`). On all
  alt-bear days, or BTC-bear OR alt-bear, it is tune-only. Out of sample (2017-19 spot, frozen) the ALT-ONLY rule made
  +22..+25%/yr - the sign flips between eras, like the sleeve's chop placebo. Dead.
- **Shorting alts when they trend down:** -2.9%/yr on ALT-ONLY days, -18%/yr on every alt-bear day. Dead.
- **Defence - the trend book's longs x0.5 on alt-bear days, at entry:** below the bet-smaller line on the holdout in all 4
  bar phases; no longs at all: fall 67% vs 50% (`logs/alt_bear_defence.txt`). Dead.
- **What the machine already does there** (`logs/alt_bear_books.txt`, descriptive): +4.0% per 30 days - trend -9.1%, MN
  +4.9%, daily +4.2%, capit2 +2.3%.
**Reading:** these markets are covered by the books that do not need a trend; the trend book loses there, as in sideways
months, and the only lever on it is its size (`trend_size.py`, declined 2026-10-18).

## The forex search, "every possible thing" (2026-10-22): dead except one CANDIDATE - NASDAQ's intraday "noise" momentum

**Why tested:** the user: "test every possible thing or strategy you have, his strategy's help also and all the other info -
I want a crazy good strategy" (Exness). The intraday tests so far had 9 months (Exness ticks) or 2.5 years (NQ 1h) - no
power for a 1-3bp-a-day edge - so this reopens NASDAQ intraday ON PURPOSE (the 2026-10-12 kill line) on HistData's free
minute bars: FX 2007-2026, NASDAQ / S&P / DAX / gold 2010-2026. Exness spreads + 0.5bp slippage throughout.
- **Published intraday rules** (`fx_intraday_pub.py`): the 5-minute opening-range breakout (Zarattini & Aziz 2023) and the
  "noise area" momentum (Zarattini, Aziz & Barbon 2024) on 7 instruments. FX majors, gold, DAX: every rule loses, every
  year. S&P: same sign as NASDAQ, weaker. **NASDAQ NOISE: +2.25bp a day net, t +2.83, Sharpe 0.74 at 1x, 13 of 17 years up;
  tune t +1.99 / holdout +2.01 - a hundredth under the line.**
- **Attacked** (`noise_attack.py`): positive in all 6 decision phases and every lookback, survives a 5-minute late fill,
  Exness's own 2026 bars agree (daily corr 0.93), alpha over the session drift t +2.99. Weak: double costs (t 1.5), the
  short leg, and ALL of it sits on days VXN is above its 1-year median (found after looking).
- **Slower families** (`fx_daily_families.py`): currency momentum / value / both (spot, swap-free) ~0; crosses (AUDNZD,
  EURGBP, EURCHF) mean reversion dead; weekend gaps fill 67-73% of the time and still lose; the trend book reproduces
  (+5.4%/yr swap-free) and 3-speed / 23 markets do not improve it. **Pre-FOMC drift on NASDAQ: +0.25% an event, t +3.14,
  tune t +1.51 - a lead, all of it after 2016.**
- **Machine learning across 10 markets** (`fx_ml_leadlag.py`, ridge + trees, 2011-18 -> 2019-26): IC under 0.03, gross
  under 1.4bp, 0 of 10 net positive with t > 0.2.
- **His help:** his sittings (NY morning only) weaken it; his lean to wild days matches where NOISE earns (VXN filter,
  post-hoc); his +10%-a-month stop changes nothing (`noise_book.py`).
- **As a $300 account** (`noise_book.py`, BACKTEST): Exness's USTECm minimum (0.05 lot ~ $1,500) makes $300 run it at x5:
  +21.6%/yr 2010-26 / +26.2% holdout, fall 56% / 45%, worst month -20%, worst day -13.7%. x3 (needs $500): +14% / +17%,
  fall 37% / 29%. + pre-FOMC at x3: +18.9% / +27.1%, Sharpe 0.90 / 1.14.
- **Gold alone, 2010-2026 minute bars** (`gold_focus.py`, the user: "gold and NASDAQ only"): long gold in Asian hours
  (18:00 -> 03:00 NY) +4.2bp a day gross, t +4.2 - partly a bid-only artifact of the wide 18:00 reopen spread; from 19:00
  +2.7bp, ~+1bp net, i.e. gold's own rise. The first 6 minutes after a US data surprise go its way 75% (+17bp) and are gone
  before a retail order; following later loses. No trend rule beats holding gold (swap-free +12%/yr 2001-26, fall 44%).
  NOISE on two more gold sessions: dead. Gold has no edge here beyond going up.
- **What was missed: the SWAP** (`ndx_swapfree.py`, the user: "there must be something you are not looking at"). Every
  NASDAQ / gold hold died on Exness's overnight swap (~2.2bp a night on longs; 0 on shorts on the user's demo). Swap-free:
  NASDAQ's overnight session nets +3.7bp a night (t +2.5); 3x buy-and-hold 2006-26 +33%/yr vs +7% with swap. A crash filter
  (above the 200-day AND VIX below VIX3M) at 2x: +20%/yr, fall 49% (2006-26) - beats 1x holding at matched fall but not on
  Sharpe, and 1999-2026 the 200-day exit did not save a levered book from the dot-com crash (fall 85%). That core at 2x +
  NOISE at 2x: +32%/yr, fall 33%, Sharpe 1.1 (2010-26, BACKTEST). Mostly NASDAQ's own rise, levered; needs a swap-free
  account on USTEC and ~$750+.
**Reading:** forex itself has nothing at retail cost - every currency rule at every horizon from minutes to months is dead
here. The one thing that holds is a US-index intraday effect (consistent with dealer-gamma and leveraged-ETF hedging flows
into the close), worth a Sharpe of ~0.75-0.9: a good book, not a crazy one. A CANDIDATE for an Exness demo record, not money.

## Not a kill - the running bot made to match its own backtest (2026-10-22) - `backtest/machine_fixes.py`

**Why:** the user: "how can we eliminate losses from our current bot and make it more profitable". Every loss brake has
been tested dead (worst_month.py's 16 brakes, profit_take.py, coin_cap.py, alt_bear.py, chop_switch.py). What had not
been done was making combo-bot-final do what its yardstick does. Paired against the RUNNING machine on the same 10
orderings, typical year tune / holdout: **capit2 as a resting limit +3.4% / +3.9%** (the live 2-minute poll misses the
fastest wicks, capit2_exec.py), **the crash bids switched on +15.4% / +7.4%** (counted in every final-machine backtest,
missing from the running dry bot), MN + carry at maker fees +2.5% / +2.4% (needs a real order path). All three:
+22% / +14%, worst month and fall unchanged within a point. The first two are built (final_books.capit2_poll,
final_books.bids_poll), tested, and await the user's word to deploy.

## The sentiment engine, "all the good stuff" (2026-10-23) - `news/impact_by_source.py`, `news/positioning_hist.py`, `news/bsky_hist.py`

**Why:** the user: "we need to make better sentiment analysis tool ... add all the good stuff, also work on getting news
from X". Predictions registered in each file before its run. Full table in doc 25 s7.
- **Exchange notices by source** (`logs/news_impact_by_source.txt`, 1,446 notices): Binance adds_products stays the one
  strong type (already the news book). New spot listings drift down 7 days on every venue but only cover a thin coin's
  cost. Delistings, unlocks: nothing. S2 / S4 right; S1 (direction right, t short) and S3 wrong.
- **Positioning** (`logs/positioning_hist.txt`, Binance metrics archive 2022-26, PIT top-40, Monday and Thursday): no
  pass (Q4 right; Q1-Q3 wrong). A LEAD: the crowd-contrarian book +37% / +48%/yr, t 1.8-2.0 - funding (+0.32%/wk) plus
  squeezes in heavily shorted small coins (MYX, SIREN, AIA +200-300% weeks), mostly 2025-26. Taker flow: IC +0.06
  (momentum), no book either way (post-hoc follow run, `logs/positioning_taker_follow.txt`: -9.8% / +6.7%/yr).
- **Bluesky** (`logs/bsky_hist.txt`, 25 coins, 17,075 coin-days, 2024-11 .. 2026-09): attention IC -0.007, tone +0.062
  tune / -0.019 holdout, crypto-wide attention vs BTC -0.03. Dead (B2-B4 right, B1 wrong).
- **X:** no free legal source; not scraped.
**Kept:** the readout `news/mood_now.py` (crowd, funding, taker, OI per coin, the crowd book's quarters flagged) -
information, not a book.
- **Headline keywords** (`news/keywords.py`, `logs/news_keywords.txt`; the user: "avoid API cost - check how each type of
  news or keyword affected the market"): 18,886 coin events and 42,918 market hours, 1,493 / 2,526 words and pairs. Words
  pass at the rate shifted (random) outcomes give; a word score learned on 2020-24 has holdout IC -0.005 outside the
  known exchange types and loses -156bp a trade. The coherent cluster ('margin', 'convert', 'add') is adds_products,
  already the news book. The free regex classifier (news/enrich.py) holds what the text carries; no case for a paid
  AI reader unless it finds a new event type.

## Dead: the crowd as a filter on the machine's entries (2026-10-23) - `backtest/crowd_filter.py`

**Why:** the user: "learn why the accounts are down and do something without butchering our gains". Live (194 positions,
both accounts): longs lost in every crowd bucket (the alt sell-off); shorts on crowd-short coins lost, shorts on
crowd-long coins made money; trend longs on crowd-long coins -$16. Tested on the whole deployed machine, 2022-26, one
book filtered at a time (trend longs / shorts, daily longs, MN shorts / longs, all): **nothing passes on both spans**.
Keeping the trend book out of crowd-long coins costs -35% of the 2024-26 typical year (0/10) - the crowded-long coins are
the bull runners. MN short filter +1.3% / -3.3%. The crowd pays as its own balanced book (crowd_combo.py), not as a veto.

## Dead: Polymarket sum gaps; reward quoting left unproven (2026-10-26) - `poly_structure.py`, `tests/test_poly_structure.py`

**Why:** the user asked what niche markets are left beyond the crypto machine. Every DIRECTIONAL Polymarket test here is
dead (doc 08, `poly_weather.py`, `poly_rescore.py`); STRUCTURE - prices that must obey an identity whatever happens - had
never been measured. Read-only, standard library, no keys, no orders. Predictions and verdict rules were written into the
file's docstring before the first run (one amendment, below, made after the census and before any watch).

**Method.** Fees are the docs' formula, `fee = shares x rate x p(1-p)`, taker only, rate from each market's own
`feeSchedule` (docs.polymarket.com/trading/fees). Books are depth-walked, so a gap counts only as far as shares can be
bought and only if every leg meets the venue's minimum order. NO basket = buy NO on every named outcome of a neg-risk
event: at most one outcome wins, so it pays at least k-1, and converting the No shares is atomic (the docs' words), so
the cash is back at once. YES basket = buy YES on every outcome of a standard (non-augmented) event: paid at resolution.
Rewards use the docs' quadratic score; fills cannot be seen read-only.

**Results (2026-10-25 20:22-20:56 UTC; `logs/poly_structure_census.txt`, `_watch.txt`, `_rewards.txt`):**
- Census: 2,100 active events, 1,216 neg-risk (614 augmented), 21,788 markets, ~27,000 books. The NO books are exact
  mirrors of the YES books (|NO ask - (1 - YES bid)| = 0.0000 on 8,420 markets).
- **NO basket: 669 priced, 0 with a positive top of book after fees; the closest is -0.1 cent a set.** Watched 30
  minutes, 89 ticks, 222 near-break-even events: 1 sample in 9,212 was positive (+0.2 cent, never executable), 0 episodes.
- **YES basket: 3 executable, none an arbitrage.** OpenAI IPO market cap +0.8-1.5% and Maduro prison time +2.3% over 432
  days, top-selling artist +0.5% over 157 days = **1.2-2.0% a year**: the time value of a complete set. The first two sat
  unchanged for the whole 30 minutes. The verdict rule was amended before the watch (YES baskets must clear 15% a year);
  **0 episodes were worth taking.**
- Rewards: 14,120 markets pay; 5,994 are live with a window and a minimum order of <= 300 shares. Upper-bound yield on a
  minimum-size two-sided quote at 25% of the max spread: median 1.12% a day, but 1,338 of 5,917 are uncontested (our
  quote alone would take over half the pool: day-one pools and empty books, not believable). Contested: median 0.60% a
  day, and the median pool pays **$0.17 a day** to a minimum-size quote. A rough touch cost (a 1-minute print through the
  quote fills it, no bounce back credited) on a RANDOM 150 contested markets: lost/reward median 1.66, net median
  **-0.80% a day**, positive in 70 of 150. The rule as registered (>= 3 markets with yield >= 0.5% a day and touch cost
  under half of it) passes on 4 of the top 8 contested - markets picked on the very pool size it then rewards.

**Predictions:** P1 right on the count (3 executable), wrong on size (2.4% against 1.5% - but over 432 days). P2 wrong:
the median episode lasted 575 s, because the long ones are the time-value gaps; the only short ones were $0.11 baskets.
P3 wrong on the upper bound (median 1.12% a day, predicted < 0.3%), right that the touch cost removes most of it. P4 right
for the sum gaps; for rewards the registered rule says CANDIDATE and a random sample says negative, so it is reported as
**unproven, not a book**.

**Not seen, and each can only make it worse:** latency (a gap could be gone before an order lands), gas or relayer cost of
the conversion, a voided or 50-50 event (a cancelled match pays 0.5 a leg, below the k-1 bound), UMA dispute risk, and
adverse selection on real fills. Polymarket's own geoblock endpoint says this PC (PK) is not blocked - that is not a
legal answer for the user's case. Polymarket does not pay reward amounts under $1.

**What it means.** A retail account cannot take Polymarket's sum gaps: bots close them before a human sees them, and the
ones left are bonds at 1-2% a year. The only live question is reward quoting, and it needs a forward PAPER quoter on the
trade tape (trade-through fills and 1 / 10 / 60-minute mark-outs), not another read-only scan. Under doc 22 (research
stop 2026-12-31, code freeze to 2027-04-09) that is an override like the crowd book; nothing was started.


## Dead: the NASDAQ dip-buy on 81 other tradfi series (2026-10-26) — `backtest/stock_dip.py`, `logs/stock_dip.txt`

The running QQQ book (RSI(2) < 10 at the close, out at the first close above the 5-day mean, max 10 days) was applied
UNCHANGED to the 81 daily series in `strategy_analysis/data/tradfi` (4 broad ETFs, 8 commodity/metal ETFs, 69 stocks), all of
which Binance lists as perps. Costs 12bp + 3bp a calendar day; tune < 2015-08; t by ENTRY DATE (a crash day is one bet).
Predictions and the kill line were written in the file before the first run.

- **Broad ETFs: 0 of 4 pass both halves.** SPY +0.36% (t 2.4) / +0.25% (t 1.1); **QQQ +0.60% (t 2.5) / +0.31% (t 1.6)**;
  EWJ +0.30% / -0.09%; EWY +0.39% / -0.22%. Under these costs the running NDX book is worth about 12 trades a year at +0.3% on
  the holdout = **~+4% a year at 1x**, not the +0.95% a trade of `ndx_capit.py` (that was the ^NDX index, swap 2.3bp a night).
- **Commodity/metal ETFs: 0 of 8; pooled -0.34% a trade, t -3.0** (the dip keeps falling).
- **69 single stocks pooled (34,223 trades, survivor-biased so flattering): +0.18% a trade, tune t 2.2 / holdout t 0.8;
  4 of 58 individual series (7%) pass both halves = chance.** Everything pooled: tune t 1.8 / holdout t -0.2. **No lead.**

**Predictions:** D1 right (0 of 4), D2 right (+0.18%, family fail), D3 right (0 of 8), D4 right (7%), D5 wrong (no decay
after 2010: +0.17% before, +0.15% after). **What it means:** the forced-selling bounce is an INDEX effect (QQQ, a little SPY);
single stocks fall for reasons and keep falling. No book on the other tradfi perps. The control's per-day return is negative
after costs, so the "x2 the control" line is met trivially and the t-lines decide.

## A lottery unless there is no time limit: the funded-account ("prop firm") route — `backtest/prop_pass.py`, `logs/prop_pass.txt`

The user asked to "try forex again - huge potential". The repo had tested forex only as a way to GROW a $221-300 account.
Never tested: pay a fee, trade a firm's 10,000-100,000 USD under loss limits, keep ~80% of the profit. This measures how
often NASDAQ NOISE's real daily history (`noise_book.py`, 2010-2026, 3,686 days, +2.25bp a day, Exness costs, intraday so no
swap) passes the commonly published TWO-STEP rules (+10% then +5%, 10% static max loss, 5% daily loss), against a ZERO-EDGE
CONTROL (the same days with the mean removed). Rolling start on every day; k = constant leverage. BACKTEST; the firm, its
fine print and its payouts are NOT tested and cannot be from here.

| both phases passed | x1 | x2 | x3 | x4 | x5 |
|---|---|---|---|---|---|
| no time limit: book / control | 66% / 45% | 58% / 23% | 41% / 17% | 37% / 15% | 36% / 14% |
| median days to pass (book) | 432 | 199 | 112 | 76 | 53 |
| 42 trading days a phase: book / control | 0.3% / 0% | 5.9% / 3.9% | 9.6% / 6.8% | 12.8% / 8.7% | 17.9% / 10.7% |
| 21 trading days a phase: book / control | 0% / 0% | 1.8% / 1.4% | 3.8% / 3.1% | 7.0% / 5.0% | 10.1% / 7.2% |

- **With a time limit it is a lottery that leverage sets, not the edge:** the edge adds +0.3 to +7 points; the pass rate rises
  with k only because variance reaches the target; the same rises for the zero-edge control. At 21 days nothing is above 10%.
- **With NO time limit the edge matters (+17 to +46 points at k >= 2, both halves) but it takes months to a year and a half**
  (199 days at x2). At x1 the holdout edge is -3.6 points (the halves disagree), at x2 +28.5 tune / +45.6 holdout.
- **A random walk with no time limit passes both phases ~1 time in 3-4 by structure alone** (control 14-45%, theory 33% at
  zero drift) - which is why firms add time limits, consistency rules and payout conditions. Sources found 2026-10-26: reported
  pass rates 5-14% per attempt, ~7% of all traders ever paid, only ~45% of the people who pass paid
  (<https://track360.io/blog/prop-trading-industry-statistics-2026>, <https://www.financemagnates.com/forex/only-1-in-20-traders-pass-prop-firm-challenges-reports-the-funded-trader/>);
  FTMO's published 2-step numbers match the rules used, but its fee and 1-step limits conflict between sources
  (<https://backtrex.com/en/prop-firms/ftmo>).
- Funded year after passing (no limit; 80% of profit paid every 21 days): x1 pays 7.4% of the account, 88% get a payout, 0%
  blown (the control 1.6% / 22% blown); x2 pays 14.7%, 25% blown; **x3 is blown 85% of the time.** With an ASSUMED fee of 1.2%
  of the account: x1 4.1x the fee, x2 7.1x, x3 3.8x - and 1.9x / 3.2x / 1.7x after halving for the payout friction.
- Optimistic by construction: close-to-close days miss an intraday touch of the 5% daily limit; commissions, data-feed
  differences, news-trading and consistency rules are not charged; the overlapping starts share one history (the control's
  halves read 37% and 66%), so the effective sample is a handful of paths.

**Predictions:** Q1 right, Q2 wrong (the edge added 21-46 points with no limit), Q3 right, Q4 right, Q5 wrong (x2's
holdout is 13 points above tune). **What it means:** the funded route is the one way found in this repo for a $221 stake to
trade a large forex/index account, but it only rewards an edge at a firm with NO time limit (a rare term, read on the firm's
own page); everywhere else it is a bought ticket at 1-10%. NOISE is itself a candidate (tune t 1.99) with no forward record.
Nothing was bought, started or deployed; the decision and the firm checks are the user's.


## The Claude trading skills, checked and tested (2026-10-27) — two repos, three plugin pages, nine tests

The user: "check all of them and see if we can take something from them, and do not assume that because we tested something
already it is certified wrong." Sources, read as UNTRUSTED data (shallow copies in a scratch folder, nothing run from them):
[tradermonty/claude-trading-skills](https://github.com/tradermonty/claude-trading-skills) (74 skills, mostly US-equity screeners)
and [SKE-Labs/agent-trading-skills](https://github.com/SKE-Labs/agent-trading-skills) (56 skills; its "day-trading" set is the one the
user remembered). SKE's v4 skills are frameworks, not recipes: each says to freeze thresholds, charge costs, hold out data, expire
zones and count unfilled ones - this repo's own protocol - and none gives a rule with an edge. Every rule below was implemented as
the skill's code / text states it, with predictions and a kill line in the file BEFORE the first run.

| Skill (repo) | Test | Result |
|---|---|---|
| COT contrarian chain: `cot-contrarian-detector` (156-week COT Index, crowded >= 90 / <= 10) + `technical-analyst` weekly detectors (key reversal, failed extreme, failed breakout, continuation veto) + exit at index 50 / swing stop (tradermonty) | `cot_shapiro.py` (7 currency futures 1996-2026), `cot_shapiro_more.py` (+ gold, silver, WTI, S&P, Nasdaq-100, 10-year note: CFTC legacy reports, Yahoo prices), steps 1 + 3 only (step 2, news failure, is manual in the skills) | **NO PASS.** FX: 202 trades, +0.35% spot / +0.17% net a trade, mirror F8 -0.33%; tune -0.02% a week (t -0.4), holdout +0.12% (t +2.1); circular-shift null p 0.26 (trade mean) / 0.04 (holdout week). Pooled 13 markets: 324 trades, +0.67% spot, **tune 0.00% / holdout +0.10% a week (t 1.1)**, null p 0.10 / 0.17; the confirmation adds nothing over crowding alone (C1: +0.05% a week, t 1.4; on the six new markets +0.16% a week, t 2.1 swap-free, -0.04% a trade with swap). Predictions: S1, S4, X1-X4 right; S2, S3 wrong |
| IBD distribution days: `ibd-distribution-day-monitor` (tradermonty) | `dist_days.py`: QQQ, SPY 1993-2026 and BTC 2020-2026, the skill's counting reproduced against its tracker code; exposure map NORMAL/CAUTION 100%, HIGH 75%, SEVERE 50% | **NO RULE.** The thresholds are loose: 23% of QQQ days are raw distribution days, so HIGH/SEVERE sit on 65% of days (average exposure 73%). No return information (next 20 days HIGH+SEVERE +0.48% vs NORMAL +0.90% tune, +1.48% vs +1.37% holdout). Tune half: Sharpe 0.28 vs hold 0.33, timing as good as the rule in 48% of shifted series. Holdout (2015-): Sharpe 0.99 vs 0.91, fall 24% vs 35% (matched constant 26%), only 3% of shifts as good; BTC holdout fall 37% vs 53%. Recent decade only. Y2-Y4 right, Y1 wrong |
| `residual-edge-analyzer` (tradermonty), a method | `residual_edge.py` on `chop_gap_months.pkl` (the machine's monthly books, 78 months) | **Insight, not a rule.** The machine is not BTC beta: beta 0.78 but **R2 0.02**; its biggest months came with BTC flat or down (2024-12: machine +524%, BTC -2.9%; 2025-10: +112%, BTC -3.9%). Alpha t +3.8 (HAC) is not a reliable measure with returns this heavy-tailed: drop the best 3 of 78 months and the average month falls +40% -> +25% (the t-stats of those trimmed fits were not kept: the trimmed months were re-sorted, which scrambles the HAC lag order); median month +7.8% (BTC +2.7%), 69% of months up. Z1, Z4, Z5 right; Z2, Z3 wrong |
| `crypto-regime-analyzer` (tradermonty), 5 of its 6 components (dominance has no history) | `crypto_regime_score.py`: the composite vs the machine's next month, and as a dial | **NO SIGNAL.** Spearman +0.32 tune / +0.15 holdout; RISK_OFF in 26% of months; the x0.5 dial avoids the holdout's worst month (-14% vs -28%) but is slightly worse than the matched constant on the tune half (worst month -13.8% vs -12.4%). The skill's own VALIDATION.md says the bands are untested. W1, W3 right; W2 wrong |
| `altcoin-rotation` breadth gate (SKE): share of the PIT top-40 beating BTC over 30 days < 0.35 | `alt_rotation_gate.py` through `alt_bear.py --defence`'s machinery (triple trend book, 4 phases x 10 orderings, decided at entry) | **NO GATE.** On 49% of days (64% inside BTC-bear labels, 35% inside BTC-bull); trend longs x0.5 there: tune +458% vs base +788%, fall 41% vs 50%, below the bet-smaller line in all 4 phases (-118/-42 ... -133/-21). R2 right; R1, R3 wrong |
| `stockbee-exhaustion-hammer-screener`, `stockbee-momentum-burst-screener` (tradermonty), skill defaults | `stockbee_crypto.py`: 360 PIT-top-40 perps, daily, 2020-2026 | **NONE PASS.** Hammer A -0.30% a trade (holdout -1.05%, t -2.1), A_U -0.15%, its no-candle context C1 -0.05%: the candle adds nothing (-0.25%). Burst long B_L +0.56% (tune +0.79 / holdout +0.20, **t 0.9**, Holm 0.78), mirror short -0.34%. H1, H3 right; H2 wrong |
| `fair-value-gaps` (SKE, ICT) | `ict_fvg.py`: 8 coins 1h + NASDAQ 5m, retest limit, 24-bar expiry, 3 matched random-time controls per zone | **DEAD.** Crypto -0.07% tune / -0.13% holdout vs control -0.16% / -0.14%; NASDAQ -0.01% vs 0.00%; zones touched 83% vs 82% (crypto), 78% vs 73% (NASDAQ): not magnets. F1-F3 right |
| `gap-trading` (SKE) | `ndx_gap.py` (18 registered cells: three gap sizes x opening ranges 5/15/30 x continuation/fade, Holm over 18) then `ndx_gap_check.py` | **A real but small CANDIDATE that is mostly NOISE.** NASDAQ gap >= 1 x 14-day ATR, continuation after a 15 / 30-minute opening range: **+22.7 / +25.7bp a trade net, t 3.1 / 3.5, tune t 2.2 / 2.1, holdout t 2.2 / 2.8, Holm 0.02 / 0.00; 132-144 trades in 16 years (8.3 a year).** Checks: 14 of 16 years positive, all 10 neighbours positive on both halves, S&P positive (+7bp, t 1.4) and DAX not, gap-ups +20bp / gap-downs +31bp, placebo mean +1.0bp (real above its 99th percentile), +23bp at triple cost. **But** NOISE earns +16.8bp on the same days (daily correlation +0.68), and NOISE's profit sits there: +10bp a day on the 6% biggest-gap days against +1.5bp on quiet days, 26% of its total. Worth +2.1% a year at 1x (+11% at x5, worst trade -8% of the account). G1-G3 wrong (my predicted null did not hold); K4 yes |

Read and NOT run, with the reason: `drawdown-circuit-breaker` (2% day / 5% week / 8% month halts) blocks only NEW entries, which a
booked-at-close series cannot test (CLAUDE.md s3); its monthly line would trip in 12% of the machine's months (trend book alone
28%); the 16 earlier account brakes failed against betting smaller (`worst_month.py`). CANSLIM, VCP, PEAD, earnings, dividend,
13F and market-top screeners need US-equity fundamentals / constituent data this repo does not have and Bitget / Binance /
Exness do not trade. `pair-trade-screener`: only a survivor-biased stock list is on disk, and crypto pairs died 6 of 6.
`mt5-robot-tester`, the edge-pipeline and journal skills: process tools (selection from mass backtests is the thing this repo
guards against). The three plugin pages: TradingCalc is a free-tier crypto-futures calculator (PnL, liquidation, sizing: the
bot already computes these); TradeOS AI turns MACD / RSI / ATR rules into alert agents behind a sign-in; "Crypto Spot Futures
Analyzer" has no vendor page to inspect - description only. None adds an edge; none was installed.

**What can be taken:** nothing as a new return stream. Methods: the circular-shift null for event rules (`cot_shapiro.py`), the
residual-edge view (the machine's return is alt breakout convexity, not BTC), and the NOISE finding above (size NOISE up on
big-gap days if it is ever run). Faint leads, none a pass: COT crowding alone in non-currency futures (swap-free only), the
momentum-burst long in crypto (t 0.9), distribution-day timing in the last decade. Data added: `strategy_analysis/data/fx_macro/cot_more.csv`.


## The machine is a convex payoff: what that does to waiting and to the day-45 line; the "fuel" state is readable but not tradable (2026-10-27) — `backtest/convexity.py`, `backtest/runner_gate.py`

The user: "do something about the most useful finding" (`residual_edge.py`: the machine's backtest return is not BTC exposure, it is a few explosive alt months). It changes no rule - the lines in doc 22 are not moved - but it changes how the record must be READ, so it was priced on the machine's own 10-ordering DAILY account series (`scorecard_bands.py`'s construction, cached to `logs/daily_combos_cache/machine_account_daily.pkl`, 2020-02..2026-09). All figures are the BACKTEST, hindsight-shrunk trend book, "if the machine works as backtested"; 10 orderings share one market path and windows overlap, so the counts of distinct start-months are printed beside them. Predictions in both files before the first run.

| | |
|---|---|
| **Lumpiness** | the best 5% of days carry 126% of the total log growth (the rest net negative); the best 10% of months 53%. The account sits below its previous peak 88% of days; the longest stretch without a new high is 248 days (223-287 across orderings) |
| **Waiting, from a random start** | +20% reached by day 90 / 180 / 365: 83% / 95% / 100%; +50%: 61% / 88% / 99%; +100%: 43% / 73% / 95% (the backtest compounds ~+1,000%+ a year, so even its quiet stretches look fast - another reason to read the live record against the percentile bands, not against these) |
| **The day-45 line (doc 22 s3b: KILL under -12.9%)** | 20,355 windows from 68 start-months; **9% of windows are under the line at day 45** (38 months). Under it: above their start by day 90 45%, day 180 **73%**, day 365 **99%**. Over it: 87% / 96% / 100%. So a working machine is killed ~1 time in 11, and what a KILL then gives up recovers within half a year 3 times in 4 - the trade doc 22 chose (a dead machine is killed 58% of the time, `verdict_power.py`). The line stays as written |
| **Today's analogue** (13-18% down at day 17; main is -15.1%) | 1,095 windows from 47 start-months: 67% were over the line at day 45; above start by day 90 63%, day 180 87%, day 365 100% |
| **What is NEW: the fuel at the time** | the killed windows split by the share of the top-40 already running (see below) at day 45: **LOW fuel 625 windows / 26 months: above start by day 180 only 57% (median +10%), 365 99%; MID 914 windows: 78% / 100%; HIGH 247 windows: 94% / 100%.** A kill zone with low fuel is a longer drought, not a different outcome. Descriptive sub-split of the kill set, not a rule |

**The fuel** (`convexity.py` part 4, 72 months, Spearman with the trend book's NEXT month, tune / holdout): share of the point-in-time top-40 (BTC out) up more than 20% over 30 days **+0.35 / +0.46**; the median coin's 30-day move +0.23 / +0.61; cross-sectional dispersion +0.20 / +0.26; alt breadth +0.12 / +0.15. By tercile of the runner share at the previous month-end (split 5.1% / 20.5%): **LOW: trend book next month mean -0.5%, median -5.2%, up 18% of months (account +12.6% mean, +3.9% median); MID +3.0% / -3.7% / 36%; HIGH +69.4% mean, +25.1% median, up 70% of months (account +95.4%, worst month -12.6%).** Not all big months follow a high reading: 2025-07 (+143%) followed 5%. The SAME-month relation is weak at monthly resolution (dispersion +0.28 / -0.12).
**Live, 2026-10-26 20:38 UTC:** 5.1% of the top-40 running (percentile 18-28 of 2020-26), the median coin -19% in 30 days (23rd), dispersion 34th; only QNT +93% and BTW +24% are up; LSK -53%, ONE -47%, BR -44%, USELESS -43%, LIT -35%. Both live trend books are net SHORT the 12 large caps (main 8 of 11 positions short, fresh 9 of 12; the shorts are +1-13% each, +$6.28 / +$1.32 open) and hold no long runner. That is the LOW state: the fuel for an explosive month is absent, the book earns small on the decline, and a drought is the expected experience, not a malfunction.

**`runner_gate.py` - can the state be TRADED?** At entry, the trend book's LONGS x0.5 when the runner share is below its expanding 33rd percentile (on 33% of days), x1.5 above the expanding 67th; the alt_bear.defence machinery (4 bar phases x 10 orderings, the cached bet-smaller line re-checked): **NO GATE.** LOW x0.5: tune +591% vs the base +788%, holdout +527% vs +498%, fall 45% vs 50%; against the line, **tune -88 / -164 / -82 / -69 points, holdout +60 / +58 / +90 / +63** across the four phases. That is the mined-holdout signature (CLAUDE.md s2: "helps holdout, costs tune"), not a pass. HIGH x1.5: tune +757%, holdout +500%, fall 54%; -99/-23, -148/-74, -180/+6, -99/-23. Predictions: T1, T2, T3 right; T4 wrong (the cached panel ends 2026-09-21, before the October decline; the live gauge says LOW).
Predictions in `convexity.py`: C3, C4 right; C1, C2, C5, C6 wrong (the best 10% of months carry 53%, not 60%; the backtest is far faster than I guessed; dispersion does not explain the same month at 0.4; live dispersion is below its median).

**What was built:** `news/mood_now.fuel()` + `news/fuel_bands.json` (the 2020-26 history, written by `convexity.py --bands`) - the dashboard's mood card gets a "Trend-book fuel" line (state, share running, percentile, median coin). Standard library only; `tests/test_mood_now.py` 8 tests (3 new, 4 mutations caught), `tests/test_dashboard_push.py` 10; the Next.js app compiles. **Deployed 2026-10-27 at the user's word** (commit `a100fa2` on top of `a773935`, gauge only; VM tests pass, a mood snapshot carried `fuel` into the feed payload, every bot and paper-book file byte-identical, nothing restarted; Vercel "Deployment has completed"): display only, no book reads it.

## The Analyst desk's three chart rules replayed over 4.7 years, and the whole account at 10x / 20x / 30x (2026-10-27) — `backtest/analyst_replay.py`, `backtest/analyst_replay_1m.py`, `logs/analyst_replay.txt`

**The question** (the user, before the desk went live): "10x 20x 30x leverage, capital $20 / $50 / $100 / $300 - how would that result in". The desk (`analyst.py`: support / resistance bounce, Fibonacci pullback, liquidity sweep, written before any history was read) has no record, so its own `signals()` were replayed unchanged on Binance perp 1-hour candles (BTC ETH SOL XRP BNB from 2022-01-01, gold and QQQ from their listings), entry at the next hour's open, scoring with `desk.resolve` (a bar touching both stop and target = a loss), one open call per symbol and rule, 6 hours of cooldown. `analyst.scenario` then takes the same calls with the WHOLE account on each, one position at a time, 12bp of notional as the fee (= 12bp x leverage of the account), liquidation at 1/leverage - 0.5% against the position at any moment (each call's worst move from the same bars).

**Result (10,580 calls, 2022-02-10 .. 2026-10-25, 43 a week; split at 2024-12-07):**

| | calls | hit (target first) | random entry, same stop / target | break-even | average after 12bp |
|---|---|---|---|---|---|
| all rules, tune / holdout | 5,934 / 4,646 | 18.8% / 17.1% | 19.5% / 19.2% | 30.6% / 31.0% | -0.160R / -0.245R |
| support / resistance | 4,646 | 26.2% | 27.2% | 36.0% | -0.216R |
| Fibonacci | 1,078 | 5.8% | 8.4% | 26.7% | -0.030R (holdout +0.026R, tune -0.072R) |
| liquidity sweep | 4,856 | 13.0% | 14.4% | 26.7% | -0.216R |

The rules are right a little LESS often than a random entry with the same stop and target, and far less often than the fee needs. **No rule beats break-even on both halves.**

**The whole account, one position at a time** (the same calls for every leverage): 10x, 20x and 30x end wiped out on the whole span, on the tune half and on the holdout, for $20, $50, $100 and $300 alike (a wiped-out account falls under Bitget's $5 minimum order and stops trading; $300 ends at the same percentage as $20). One year of calls drawn 20,000 ways (568 calls a year taken one at a time, start = 1x):

| leverage | typical year | 10th / 90th percentile | ends under start | loses 90% on the way | liquidations a year |
|---|---|---|---|---|---|
| 1x | 0.39x | 0.20x / 0.81x | 95% | 1% | 0 |
| 3x | 0.03x | 0.00x / 0.21x | 99% | 87% | 0 |
| 5x | 0.00x | 0.00x / 0.01x | 100% | 99% | 0.2 |
| 10x | 0.00x | 0.00x / 0.00x | 100% | 100% | 1.7 |
| 20x | 0.00x | - | 100% | 100% | 21 |
| 30x | 0.00x | - | 100% | 100% | 67 |

The arithmetic is the whole story: 568 trades a year at 12bp of notional is 68% of the account a year in fees at 1x, 680% at 10x, before the average call loses 0.2R. Leverage multiplies the average and cannot change its sign (`scalp_1m.py --kelly` said the same about 1-minute scalping).

**The desk's own book** (0.5% risk a call, open notional capped at 3x - what the dashboard's Analyst tab will show live): over the same calls $300 would have ended at $0.09 (-3.26% a week; 2022 -72%, 2023 -66%, 2024 -87%, 2025 -83%, 2026 -86%; 9,409 calls booked, 1,171 over the cap). **Expect the live book to bleed about 3% a week; 100 resolved calls arrive in about two and a half weeks, so its registered review (A1-A3) will be quick.**

**Is it the 1-hour scoring?** `analyst_replay_1m.py` re-scored the last 90 days' 720 calls on 1-MINUTE candles (which can tell which end was hit first): hit 19.2% -> 19.6%, average -0.249R -> -0.236R, every leverage outcome on that slice identical. The replay is not an artifact of coarse bars.

**Predictions** (registered in the files' docstrings before the first run): A5 right; A6 right (median 0.00x at 10x / 20x / 30x, ruin 100%); A7 right ($20 and $300 stand at the same multiple until a wiped-out account hits the $5 minimum); **A8 wrong** (the best case does not rise with leverage - the 90th percentile falls from 0.81x at 1x to 0.00x at 10x: with a negative average, leverage worsens every percentile); A9 right (1x loses less than 10x). **A4 wrong at the top** (43 calls a week against "5 to 40"). M1 wrong (I expected +2 to +8 hit-rate points from minute scoring; it was +0.4), M2 right, M3 half right (the worst move matches within 0.05 points on 61% of calls; its mean is 0.87% on hours and 0.70% on minutes).

**Two bugs found on the way, both mine, both fixed before any number was quoted:** (1) the first full run reused a BTC cache left by the quick `--sample` run (BTC from 2025, not 2022) - `history()` now back-fills a cache that starts later than asked; (2) the live desk's random-entry baseline was measured on 1-HOUR bars while its calls are scored on 1-MINUTE bars, which understates what chance does and flatters the call - `desk.minute_baseline` now reads 14 days of 1-minute candles on the scoring grid (hourly fallback for a listing under three horizons old). Both have tests that fail on the old code.

**What it means.** Nothing to deploy as a way to make money: the chart rules lose at every leverage, and the fee at leverage is what ends the account. The desk stays what it was built as - a forward MEASUREMENT of the user's idea (paper only, no orders, no keys), retired at its review. Caveats: a replay, not a forecast; overlapping calls make the p-values approximate; the replay's calls are the desk's rules unchanged but the desk's 3x cap and sizing are applied only in the paper-book line.

## The yearly backtest without the hindsight coin list: the total holds, the years move (2026-10-27) — `backtest/pit_years.py`, `logs/pit_years.txt`

**Asked:** "re-run the yearly numbers with the trend book trading coins chosen point-in-time (no hindsight list), so I can see what the current setup would really have made each year". The machine's yearly figures (`backtest/all_books.py`, the series the dashboard's scorecard uses) trade the trend book on `blend.BOOK` - 12 alts picked in 2026 - with its gains shrunk 3x. Here the trend book trades, each month, the 12 most-traded ALTS by the prior month's volume (perp archive, dead coins in; BTC, ETH, stablecoins, metals, oil and stock tokens out, as the live list has none), with today's rules unchanged (triple, 6.25x guard, 21-day anchor, x0.25 under BTC's 1000h average), NO shrink. The other 8 books are untouched. Profit per calendar year on a FIXED $300 (no compounding), median of 10 orderings.

**Check first:** the 12 hindsight coins through the same pipeline reproduce the published trend book within 4% over 2020-26 (+$4,468 vs +$4,282), same sign every year.

| Fixed $300 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 (to Sep) | 2020-26 |
|---|---|---|---|---|---|---|---|---|
| trend, hindsight list (published) | +342 | +1,217 | −125 | +344 | +1,863 | +315 | +290 | +4,282 |
| **trend, point-in-time alts** | +216 | +1,703 | −16 | +510 | +470 | +1,334 | +212 | +4,545 |
| machine, published | +875 | +2,386 | +232 | +780 | +2,208 | +1,287 | +632 | +8,385 |
| **machine, point-in-time** | **+723** | **+2,939** | **+365** | **+915** | **+834** | **+2,228** | **+566** | **+8,645** |
| machine, point-in-time, without MYX | +723 | +2,939 | +365 | +915 | +834 | +1,558 | +568 | +7,977 |

**Reading.** The 3x shrink landed near the honest total by luck; it put 2024's money in coins a 2024 trader would not have chosen (SUI, ENA, WLD), and the point-in-time book made 2025 instead - mostly through ONE coin: **MYX** (the 2025-09 squeeze; in the alt top 12 only Sep-Oct 2025) is 76% of 2025's winning long R. Every year is still positive; 2022 is carried by the bear sleeve and capitulation, not the trend book. Freeing the slot at the exit bar's close instead of its label: +$10 ± 185 paired, 6/10 - no difference here. Predictions: Y1 (2024 under half) right, Y2 (2021 at least the hindsight's) right, Y3 (2022 loses) right, Y5 (every year positive) right; **Y4 wrong** (expected the machine 20-50% lower; it is about the same), **Y6 wrong** (no measurable slot cost). **Still a backtest:** the other 8 books were chosen on these years, the live bot's position model is not modelled (2026-10-06: 1-2 %/mo under the engine), no capacity limit, and the live record (main −15% in 18 days, ~8th percentile of its band) is the measurement that counts.

## The order-book checklist on back data: the signal is real and stable, the tape fills only the wrong side (2026-10-28) - `backtest/book_hist.py`, `logs/book_hist.txt`, `tests/test_book_hist.py`

**Asked:** the user pasted a four-step order-book checklist (record a pair's book and trades and rebuild a valid book / spread, depth, imbalance and flow around a move / replay and test one hypothesis on later unseen data / paper-trade with fees, slippage, missed fills), then "can't we do it on the back data". `book_rec.py`'s own recording is 262 minutes of 1-second REST snapshots with a polled tape (Bitget trades capped at 100 per poll: 4,132 captured), so this uses Tardis.dev's free first-of-month days for BITGET's DOGEUSDT perp: **7 days, 2025-03-01 .. 2026-09-01, 95 million update rows, the complete tape** (52k-146k trades a day). Tune days 2025-03 / 06 / 09 (thresholds only); later unseen days 2025-12 / 2026-03 / 2026-06 / 2026-09. Predictions B1, E1, H1, M1 are in the file's docstring, written before any of the days was read.

**Step 1, the book (B1).** Rebuilt row by row, sampled every second: **crossed in 0 of 86,399 seconds on every one of the 7 days; on 2026-09-01 the touch prices AND quantities equal Tardis' independent top-25 snapshots in 100.00% of seconds** (right on both; the snapshot file comes from the same recorded feed, so this checks my rebuild, not their recording's completeness). **The third part was wrong, and its premise too:** until at least 2026-03-01 the "update stream" is NOT a diff stream - it is top-15-per-side snapshots about 6.6 a second (~570,000 snapshot blocks a day), so "equal at reconnects" is meaningless there (1-9%). Only 2026-06-01 and 2026-09-01 are true diff streams (~65 rows a second, a 200- or 1000-level snapshot at the start and at 4 reconnects). At those 8 reconnects (silences of 0.1-1.4 s) the rebuilt top 5 matched the fresh snapshot **0 times of 8** - the book had moved while the feed was away, so a rebuild is valid only because it RESYNCS at the snapshot (it does). Registered >= 80%: wrong. The depth features beyond the touch (imb5, imb20, band10, band25) are capped at 15 levels on five of the seven days.

**Step 2, around the top-1% 10-second moves (E1)** - 125-219 events a day, |move| >= 10-19bp:

| | registered | measured, 7 days |
|---|---|---|
| spread at the start vs its median | >= 1.3x | **x1.00 on six days**, x1.21 on one - wrong (the spread is one tick, 1.2bp, nearly always) |
| touch quantity on the consumed side below its 60 s median | >= 55% | 44-56%, about 51% pooled - wrong |
| imb1 points the move's way | >= 60% | 44-58%, none at 60% - wrong |
| taker flow in the 10 s BEFORE aligned | < +0.10 | -0.14 .. +0.04 - right (two days leaned the other way, -0.12 and -0.14, at 2.0-2.3 se) |
| taker flow DURING the move | > +0.40 | **+0.43 .. +0.75** - right (this is the move itself being traded) |

What changes around a move on this coin: **only the flow, and only while it happens.** Nothing in the spread or the touch depth, read once a second, announces it.

**Step 3, one claim on later days (H1): imb1 (level-1 dollar imbalance) -> the next 10 s of the mid; thresholds 10th/90th percentile from the tune days (short at <= -0.942, long at >= +0.958).**

| later day | IC | signals | move in the signalled direction | hit | taker net after 12bp | ideal maker (every limit fills) after 4bp |
|---|---|---|---|---|---|---|
| 2025-12-01 | +0.118 | 3,666 | +0.99bp (se 0.09) | 56% | -11.75 | -3.01 |
| 2026-03-01 | +0.104 | 2,468 | +1.04bp (se 0.12) | 55% | -12.03 | -2.96 |
| 2026-06-01 | +0.175 | 4,743 | +0.91bp (se 0.05) | 55% | -12.09 | -3.09 |
| 2026-09-01 | +0.245 | 5,592 | +0.94bp (se 0.04) | 52% | -12.28 | -3.06 |

**Right on all three (IC in +0.05..+0.30, move +0.3..+2.5bp, taker net below -9bp).** It holds on four unseen months and agrees with the 262-minute recording (IC +0.20 / +0.25, 1-2bp). The effect is real and stable: **about one tick (1.2bp) toward the thin side.** Exploratory (not part of the claim): the 30 s horizon halves the IC (+0.04..+0.13) at the same ~+0.9bp; microprice reproduces imb1; imb5 and band10 are weaker (+0.04..+0.10, +0.15..+0.6bp).

**Step 4, the same signals, filled by the tape (M1):** a post-only limit at the touch, filled only by a trade through the price or by enough volume AT it to clear the queue ahead (queue x1.0 = all of it, x0.5 = half cancels), 0.5 s latency, 10 s to fill, one position at a time, exit by taker or by a second limit with a taker fallback, Bitget's standard fees (maker 2bp, taker 6bp a leg). 8 variants (hold 10 / 30 s x queue x exit), 11,500-14,600 signals taken over the four later days:

- **Fill rate 20-22% in all eight** - and the queue assumption barely matters (22% at x1.0 and at x0.5), because the fills are TRADE-THROUGHS: a long fires when the bid is thick and the ask thin, price tends to rise away from the bid, and the bid fills mostly when price falls through it.
- **Filled signals moved 4.8-5.1bp LESS in the signalled direction than the unfilled ones** (registered >= 0.5bp: right, ten times over). Before any fee a filled trade is already about **-3bp**.
- **Net per signal taken (a missed fill is a zero): -2.04 .. -2.41bp (se 0.04-0.06); per FILL -10.0 .. -11.0bp; days positive 0 of 4 in every variant.**

Verdicts: fill rate registered 30-70% - **wrong** (20-22%; the qf-1.0 line of 20-60% was right at its edge); adverse selection - right; every variant negative, best <= -1bp - right (best -2.04); no variant positive on >= 3 of 4 days - right. The registered PASS (positive pooled net at t > 2, >= 3 of 4 days, at qf 1.0) is **not met by a wide margin.**

**What it means.** The order book of Bitget DOGE tells you about one tick, correctly, month after month - and a one-tick edge is 1.2bp against a 4bp maker round trip even if every limit fills, and the limits that do fill are the signal's failures. **A zero-fee venue would not rescue it** (the filled trades are -3bp before fees). Retail DOGE book trading is closed, on a stronger footing than 2026-10-09's (7 days of full tape over 17 months, thresholds set before the later days were seen, queue-aware fills). The thread's open pieces are measurement, not edge: a live diff-stream recorder (Bitget's `books` channel carries `seq` / `pseq`; the public websocket works from this PC, probed 2026-10-28) would give a true "rebuild and resync" test and queue-position data.

**Caveats:** seven single days (the first of each month), not a continuous year; a 1-second decision grid and an assumed 0.5 s latency; the touch only on the five snapshot-feed days; the queue model ignores our own order's effect and models cancellations only as a halved queue; Bitget VIP0 fees. None of these can turn -2bp a signal into a profit; they could move it by tenths.

**Predictions scored:** B1 two of three right (the third wrong, and its premise); E1 two of five right; H1 three of three right; M1 four of five right (the fill-rate range wrong). My model of what happens AROUND a move (E1) was the worst-calibrated part: it assumed a stress signature that a one-tick-spread coin does not show at one-second resolution.

## Who is crowded in the metals, and does it say what comes next? CFTC positions on platinum / palladium / gold / silver / copper, and the CME delivery picture (2026-10-28) — `backtest/cot_metals.py`, `positioning_lean.py`, `logs/cot_metals.txt`

**The ask** (the user, with a screenshot of the CFTC Disaggregated report for 2026-10-20 beside CME's Final Settlements page): "make futures positional data from the CFTC report and CME delivery / settlements, compute and correlate both, say how to test; the tool must tell me which side will have an imbalance, and beforehand." The screenshot is **palladium** (open interest 25,696, managed money 5,385 long / 17,528 short = 68% of open interest short) and **platinum** (73,635; 17,786 long / 11,171 short), found by matching its numbers to the CFTC API (dataset `kh3c-gbw2`, futures and options combined).

**What exists to test.** CFTC: weekly Disaggregated reports back to 2006-06 (free public API), public on Friday for the Tuesday. CME: the free settlement feed behind the 'Final Settlements' page keeps **only the last 5 trade dates** per product (its `TradeDate` list has 5 entries; older dates return empty - checked in the browser pane; plain scripts get 403 and are not worked around); delivery notices are PDFs with a one-year file; the history is CME DataMine (paid). So the CFTC side is testable now and the CME side can only be RECORDED from today (`logs/cme_snap/`, first file 2026-10-27).

**The test** (registered in the file before the first run; per market, 4-week horizon, 12bp, entry = the close of the first trading day after the Friday release, circular-shift null, tune / holdout, Holm over 15 cells): S1 crowd rank (managed-money net / open interest, trailing 3-year percentile; registered contrarian), S2 swap-dealer rank (+), S3 4-week change in the crowd (+).

| market (956 weeks, 2008-06..2026-09) | S1 IC all / tune / holdout | shift p | crowded-short / crowded-long bucket, next 4 weeks | S3 IC | passes |
|---|---|---|---|---|---|
| platinum | -0.108 / -0.158 / -0.142 | 0.16 | +0.5% / -3.0% | -0.041 | no |
| palladium | -0.031 / -0.068 / +0.036 | 0.46 | +0.3% / -0.5% | -0.052 | no |
| gold | -0.006 / -0.042 / +0.004 | 0.51 | +0.1% / +1.1% | -0.014 | no |
| silver | -0.027 / -0.016 / -0.062 | 0.39 | -1.2% / -0.0% | -0.012 | no |
| copper | -0.032 / -0.161 / +0.129 | 0.35 | -0.9% / -1.6% | +0.055 | no |

**0 of 15 cells pass, on the physical-metal ETFs and on front-month futures alike; the best Holm-adjusted p is 0.80.** The nearest thing to a lead is platinum's crowd rank (contrarian sign on both halves, IC -0.11; futures IC -0.09, p 0.07) and copper's positioning momentum (futures IC +0.08, p 0.053, holdout +0.16): both short of the rule, neither survives Holm. Pooled contrarian IC over the five metals: -0.041 (ETF) / -0.006 (futures).

**Predictions:** P1 right (0 of 15, at most 1 allowed); P2 half right (palladium's crowded-short bucket averaged +0.35% on ETF prices against -0.81% for all weeks, p 0.13 - not distinguishable - but -0.21% on futures prices, so 'up' is not even stable); P3 right; **P4 wrong** (positioning momentum had the registered sign in only 1 of 5 markets, I expected 3); P5 right (no verdict changes between ETF and futures prices); P6 right (the tool says NO LEAN for palladium).

**What 'extreme' means (the screenshot's palladium).** Managed money is net short 47% of the open interest, but that is only the **28th percentile of palladium's own last 3 years** - it has been far more crowded before - and the crowd added 13 points of net short in the last 4 weeks. 'Crowded' is relative; no rank bucket of palladium, platinum, gold, silver or copper has reliably been followed by a move in either direction.

**What the CME snapshot adds (arithmetic, not history).** On 2026-10-27 palladium's December contract holds 24,137 of 26,209 open interest (92%), first notice day is 2026-11-30 (34 days), March trades +12.00 over it (contango: a short is paid to roll). Managed money's 11,994 net FUTURES short lots (CFTC futures-only) = 50% of that month's open interest: it cannot take delivery, so that is the size that has to be bought back (and sold in March) before first notice. Platinum's January month holds 72% (first notice 2026-12-31) and its January -> April roll has started (April open interest 11,640 -> 16,455 in five days); gold 72% (36% of that month is managed-money net long to be sold), silver 74%, copper 49%. **The side that must trade, and roughly when, is knowable beforehand; what that does to the price is not tested** - rolling moves the calendar spread more than the outright, and there is no spread history to test it on. The record (`logs/cme_snap/`, one file per day or week through several first-notice cycles) is the way to test it; a year of it gives about eight cycles per metal.

**The tool** (`positioning_lean.py`, tests `tests/test_cot_metals.py` 6, 10 of 10 mutations caught - the entry date, the rank's look-ahead, the cost, the p direction, the pass rule, the first-notice month): per metal it prints the crowded side and rank, what followed that reading before (tune and holdout), the registered test's verdict (LEAN only if the signal passed - today none do), and the CME block (delivery-month share, days to first notice, pending roll side and size). It states the limit every time: the side that must trade is a fact, the direction of the price is only a 'lean' if the test says so.

**Caveats.** Weekly data with overlapping 4-week returns (the shift null accounts for it); two price sources agree; CFTC 'combined' counts options at their delta (the roll size uses the futures-only report); no intraday imbalance can come from weekly positions - the trader of doc 23 acts in seconds, and nothing here reaches that scale. Related earlier kills: `cot_shapiro.py` / `cot_shapiro_more.py` (legacy report, 13 markets), `fx_tff.py` (currencies).

## Gold: does managed money's pending roll move the calendar spread before first notice? CME open interest by delivery month x CFTC positions, 2016-2026 (2026-10-28) — `backtest/gold_roll.py`, `logs/gold_roll.txt`

**What was bought** (the user: "gold first", after the quote): Databento `GLBX.MDP3` `statistics` for `GC.FUT`, 2010-06-07 .. 2026-10-26 - daily settlement price, open interest and cleared volume for every gold futures month (13.5M records including spreads, 231 MB in `strategy_analysis/data/cme_stats/`, gitignored), **$1.01** of the Databento credit. Delivery notices are not in it; open interest left in the delivery month approximates what is delivered.

**Data facts found before the first run (not results):** the feed has **no open interest before late 2015** (2010-14: none, 2015: 11% of days, 2016 on: 70-94%), so only cycles from 2016 can be used; settlements are complete from 2010. Open interest for a trade date is published after the session and Databento stamps it with that date, while **CME's web page shows it one trading day later** (the page's 10/26 total 401,077 = the feed's 10-23, three days checked, all three totals match to the contract) - so the snapshots in `logs/cme_snap/` carry open interest one day older than their label (README corrected), and the test reads the PREVIOUS day's open interest at t0 (the only one known at t0's settle).

**The test** (predictions G1-G5 registered in the file first): every even delivery month (Feb..Dec) with open interest known 20 trading days before first notice F (the last trading day of the previous month): 51 cycles, 2016-02 .. 2026-06. Feature = managed money's net FUTURES lots (CFTC futures-only report public before t0) / the delivery month's open interest. Mechanism: a net LONG crowd sells M and buys the next month N, widening N - M; a net SHORT crowd does the reverse. Outcomes from t0 to F: the spread change (N - M, % of price), the outright return, the share of M's open interest still there at F, and a spread trade in the crowd's direction ($30 charged per 100-ounce round trip).

| result (51 cycles; 46 net long, 5 net short) | value |
|---|---|
| open interest still in M at F | median 2%, worst cycle 9% (the roll is mechanical and nearly complete); IC with roll share +0.10 |
| spread change vs roll share | IC +0.139 (tune +0.307, holdout -0.191), one-sided permutation p 0.162 |
| mean spread change | -0.012 points; net-long cycles -0.008, net-short (5) -0.043 |
| outright return over the same 20 days vs roll share | IC -0.117, p 0.79 |
| spread trade in the crowd's direction, $30 charged | mean -$43 a cycle (t -1.38, hit 29%); tune +$1, holdout -$107 |

**VERDICT: NO LEAD** - the spread does not reliably move with managed money's pending roll in gold.

**Predictions:** G1 right (at most 40% stays - it is 2%; |IC| < 0.2); G2 right (the registered positive sign, p 0.16 - and the IC flips sign between the halves); G3 right; G4 right (under $30, not positive on both halves); **G5 half wrong** (mean spread change is -0.012, not positive; its dependence on the crowd's sign is 0.035 points, under the 0.05 limit, but on 5 short cycles).

**What this does and does not say.** With 51 cycles a correlation below about 0.25 cannot reach p < 0.05, so this rules out a LARGE spread effect in gold and nothing smaller. The mechanical half is confirmed (98% of the delivery month's open interest is gone by first notice: the crowd does roll, on the dates the tool prints). The **net-short half is untested**: gold's crowd was net short in only 5 of 51 cycles, while palladium's is net short most of the time (the screenshot: 50% of December's open interest to be bought back). Palladium and platinum (quoted $0.48 for both, full history) are the right next test; the user has not yet approved that pull.

**Cost so far:** $1.01 of the Databento credit (gold). Cheap daily top-ups (about $0.001 a day for five metals) would replace the manual browser snapshots as the forward record.

## Liquidity sweep + seven confluence factors: the sweep's information is real, nothing lifts it above the fee (2026-10-30) — `backtest/sweep_confluence.py`, `logs/sweep_confluence.txt`

**The question** (the user, about the Analyst desk): "I see potential in the liquidity sweep; combined with other factors we can make the quality of signals better - possibly a good signal generator even for less capital". What was known: `sweep_reclaim.py` (10-08) found the swept-and-reclaimed prior-day level beats a matched random entry on both halves and still loses after 12bp; the desk's own SMC rule hit its target 13.0% against 14.4% for a random entry (doc 02, the Analyst replay entry).

**The test** (everything registered in the file's docstring first): the desk's own sweep (the bar trades under the lowest low of the previous 24 bars, closes back above it and above its open; short mirrors) on the point-in-time top-40 including dead coins, 1-hour bars 2020-02 .. 2026-09, 60,664 events (28,715 long, 31,949 short; events of one coin and side within 12 bars dropped), in at the next open, stop at the sweep's extreme, out 24 bars later (T24; a +2% target version TP2 beside it), 12bp + funding, matched control = a random hour of the same coin and month with the same stop distance, halves split 2024-04-07. Seven factors with a fixed favourable direction, every one read from bars up to the signal bar (tested for look-ahead by cutting and by scrambling the future): sweep depth in ATR, the bar's volume over the prior 24 hours' median, close location, **breadth** (coins sweeping the same side in the same hour), alignment with the 168-hour trend, equal lows / highs at the level (touches in the previous 72 bars), funding against the side. Stage 1: one factor at a time, cut = the tune half's top tercile, confirmed only if tune spread > 0 with t > 2 and holdout spread > 0 with Holm p < 0.05 over the 14 cells. Stage 2: stack the factors the tune half selected, choose the threshold on tune only, read the holdout once.

| | tune (to 2024-04) | holdout |
|---|---|---|
| long sweep, T24, unfiltered | net +0.07% (t +0.7), gross +0.19%, excess vs control +0.24% (t +2.1) | net -0.20% (t -2.5), gross -0.08%, excess +0.07% (t +0.7) |
| long, +2% target (TP2) | net -0.12%, excess +0.11% (t +2.5) | net -0.16%, excess +0.10% (t +2.3) |
| short sweep, T24 | net -0.09%, gross +0.03%, excess +0.13% (t +2.2) | net -0.05%, gross +0.07%, excess +0.05% (t +0.7) |

**Stage 1: 0 of 14 cells confirmed.** No factor has the registered sign with t > 2 on the tune half for longs (best: close location +0.21%, t +1.4). The one significant holdout cell is **negative: long sweeps in a high-breadth hour (15 or more coins sweeping their lows together) net -0.59% a trade on the holdout** (spread -0.55%, t -3.1; -0.47% without the three worst days, so not the 2025-10-10 hour), against +0.21% on the tune half - a flip, but a direction that matches the capitulation entries (`capitulation_freq.py`: the first signals of a crash keep falling, later ones bounce). Volume on shorts flips (-0.16% t -1.9 on tune, +0.25% t +2.0 on holdout). **Stage 2:** the tune half selects no long factor and one short factor (trend); that short subset nets +0.05% on tune and -0.05% on the holdout (7bp gross), +0.1 sd above a random flag of the same share. **Not tradable.**

**Predictions:** Q1 half right (the sweep beats its control in all four long rows, t > 2 in three; seven of eight rows lose after 12bp, the long T24 tune row is +0.07% at t +0.7); Q2 right on the count (0 of 14, limit 3) and wrong on which: volume and breadth were the predicted best, and breadth is the one significant negative; Q3 right (no tradable subset, 70% registered); Q4 not testable (no long subset); Q5 right (gross never above +0.19%).

**What this says.** The information in a sweep is real and small: 5-25bp over a random entry with the same stop, against a fee of 12bp and a gross edge that is about zero since 2024. Seven natural confluence factors do not add to it, and the factor with the strongest holdout effect says the opposite of the capitulation idea (a market-wide flush is not a place to buy the first reclaim). A filter would have to lift the gross edge of the best subset from about 0 to over 0.3% a trade; no factor here moves it by more than +0.2% on the tune half or holds that on the holdout. Not tested, because the hourly archive has none: open interest and liquidation volume at the sweep (the true stop-run fingerprint), order-book depth, and higher-timeframe levels (weekly highs / lows). **Do not build on the sweep as a signal; the Analyst desk keeps measuring it forward until its review.** Caveats: one definition of the sweep (24 bars) and two exit structures; the control matches the stop distance but not the hour's volatility; factor cuts are terciles chosen once.

**A bug of mine, found at the first printout and fixed before a verdict was read:** the t-statistic averaged the DAY means while the printed mean is per trade, so a negative mean could print a positive t (long holdout net -0.20% "t +3.6"; busy flush days count thirty times in the mean and once in the day-mean t). It is now the per-trade mean with day-clustered errors (`tests/test_sweep_confluence.py` 7 tests, 17 of 17 mutations caught, including a look-ahead in the level, the volume median, the trend mean, the ATR and the 24-bar return). `sweep_reclaim.py` uses the same day-mean convention; its excess figures are means over trades with a day-mean t, so its t values (+7.3, +4.6) overstate; the means are unchanged.

## Faster bear labels for the breadth sleeve: none beats the live one; the extra days are worth about nothing (2026-10-30) - `backtest/bear_label_test.py`, `logs/bear_label_test.txt`, `tests/test_bear_label_test.py`

**Asked:** BTC fell 4% in a day to ~$77k, 4.8% under its 50-day average and 6.9% under the bot's 1000h average, "clearly a bear market" - and the bear breadth sleeve (doc 13; `combo_paper.py` SLEEVE, also in the final machine) held nothing: $0.00 booked and open on main and fresh. **Why:** its switch is `btc_regime`'s BEAR = close under the 50-day average AND that average down more than 2% over 20 days; on the 2026-10-29 close the average was still RISING 1.5%, so the label read CHOP (the paper book's `combo_sleeve.csv`: chop on every day since at least 10-23), while breadth20 was already 8.3% (under the 10% line). At $77k flat the live label would not flip for 21 more daily closes. The user's question: would a faster label have helped? Tested read-only, nothing in any bot changed (code freeze, doc 22).

**Test** (registered in the file's docstring before the 12 cells ran): everything of the live sleeve except the label - 7-day ladder, entered a day after the signal, long at breadth20 <= 0.10 and short at >= 0.288 (the bot's fixed cut-offs), 12bp, exact funding, 1bp/day rebalancing - on the alt index (top-40) and the top-10 basket. Label = close under an N-day average (N 20 / 30 / 42 [~the 1000h gate] / 50) x the average's 20-day slope (none / below 0 / below -2%); (50d, -2%) is the live label. The live label reproduces `btc_regime` on all 2,456 days. A faster label is a CANDIDATE only if it beats the live one on both halves AND in Sharpe, within 5 points of its fall and worst week, on both instruments, AND beats the live sleeve scaled to the same fall on the holdout, AND a neighbouring cell passes the first two.

| alt index, lag 1 (tune < 2024-08-29) | CAGR | tune / hold | fall | worst week | Sharpe | in market |
|---|---|---|---|---|---|---|
| **live (50d, -2%), the bot's fixed cut-offs** | +28.7% | +32.4 / +21.0 | 30% | -10.7% | 1.07 | 29% |
| 30d, below 0 | +25.6% | +29.2 / +18.0 | 48% | -22.1% | 0.87 | 35% |
| 42d, -2% | +27.5% | +32.3 / +17.6 | 24% | -10.7% | 1.03 | 29% |
| 42d, price only (~ the 1000h gate) | +18.7% | +16.9 / +22.9 | 57% | -32.1% | 0.63 | 51% |
| 50d, price only | +20.6% | +18.4 / +25.5 | 58% | -32.1% | 0.66 | 50% |
| 20d, price only | +1.1% | -2.0 / +8.2 | 70% | -32.1% | 0.25 | 59% |

**Result: NO candidate in either run.** The live label has the best Sharpe in 3 of the 4 tables (the 4th: (42d, -2%), a near-twin that flips only 7 closes earlier, is within 0.01) and the shallowest worst week; every label that adds in-market time (35-60% of days) pays for it in fall (37-70% against 30%) and Sharpe (0.25-0.91 against 1.07). The faster labels' EXTRA days (BEAR for them, not for the live label), traded alone: Sharpe -0.39 .. +0.17 against the live label's 1.07, CAGR -17.9% .. +1.2% - about nothing, and negative for the price-only labels, which is exactly today's situation (BTC under its average, average still rising, breadth low). Matched risk: scaling the LIVE sleeve to the fall of the price-only 50d label (x2.2) gives tune +65% / holdout +49% against that label's +18% / +26%: 'just bet more of the strict label' wins by a wide margin.

**Post-hoc robustness (added after run 1 because the fixed cut-offs are terciles of the live label's own bear days, which can favour it):** each label with its own causal expanding terciles (`signal_expanding`, >= 60 prior bear days). The live label then reproduces doc 13's old log to the decimal (+27.0%, tune +31.0 / hold +18.7, fall 20%, worst week -9.5%, Sharpe 1.24, 25% in market: a check on the machinery). Higher raw CAGR does appear - 50d price-only +36.9% (tune +43.8 / hold +22.9), 42d price-only +34.3% - but with falls of 48% / 45% and worst weeks of -22% (Sharpe 1.07 / 1.00 against 1.24); (42d, -2%) comes closest: +28.0% (31.3 / 21.1), fall 24%, Sharpe 1.25, and fails only the matched-risk check (live x1.22 earns +23.0% on the holdout against 21.1) and the top-10 basket (tune 30.6 vs 31.3). Still no candidate. The extra days under this run: Sharpe -0.17 .. +0.54, mixed in sign, never near the live label's 1.24.

**Today** (read after the 2026-10-29 close, $77,963; flips at $77,000 flat): BEAR already for 20d (any slope), 30d price-only, 42d price-only, 50d price-only; 30d below 0 after 2 more closes, 30d -2% after 5, 42d below 0 / -2% after 8 / 14, 50d below 0 after 12, **the live label after 21.** So a faster label WOULD be on today - and the test says that on the days it adds, the sleeve earned about nothing.

**Predictions scored:** B0 half right (CAGR +28.7% inside +22..+32; fall 30% vs registered 15-25%, in market 29% vs 22-28% - the bot's FIXED cut-offs run a deeper fall than the expanding ones: 30% / 29% vs 20% / 25%, an observation, not a recommendation). F1 right (30d below 0 35%, 20d price-only 59%). **F2 right: no candidate, in both runs.** F3 right (every extra-days Sharpe far below the live label's). F4 mostly right (30d below 0 is NOT yet bear; it flips in 2 closes). F5 right (the matched-risk live sleeve out-earns every faster label that beat the live one on a half). R1 half right (no candidate; but the live label is NOT within 2 points of the best CAGR in the expanding run - it is 9.9 points below 50d price-only, bought with 2.4x the fall).

**What it means.** The sleeve is off today because the label that paid historically is a SLOW one: it needs the 50-day average itself to be falling, i.e. a bear that has already lasted weeks, and the label that would catch today also catches every 4% drop in a bull market. Nothing here is a reason to change the running sleeve; it is a reason to expect it to switch on around mid-November if BTC stays near $77k (earlier if it falls), and a reminder that 'BTC is down' and 'the bear sleeve's regime' are different things. Caveats: one sleeve design (7-day ladder, breadth terciles), 2020-26 only (three bear episodes), the alt index is not buildable at $221, label cells were swept once on this split. The old doc 13 label table (30/50/100-day x slope, 6 of 6 positive on both halves) agrees: faster is not better, it is only also positive.


## The classic candlestick patterns as trading rules: 17 patterns x 2 sides x 3 bar sizes x 2 holds = 204 cells on the PIT top-40 - nothing passes, and the first run's "replicated edge" was a control leak (2026-11-02) - `backtest/candle_scan.py`, `backtest/candle_scan_check.py`, `logs/candle_scan.txt`, `logs/candle_scan_check.txt`, `tests/test_candle_scan.py`

**Question** (the user: "did we test candle chart patterns"). Before this the repo had tested candles only at one NASDAQ trader's moments (`his_1m.py`, 13 one-minute patterns, none survives Holm) and one daily hammer / burst screener (`stockbee_crypto.py`: hammer -0.30% a trade). Nobody had scanned the textbook patterns as stand-alone rules. Predictions K1-K5 are in the file's docstring, written before the first run (prior that anything passes: under 5%).

**Design.** 364 point-in-time top-40 perps (by the prior month's volume, dead coins in), Binance perp bars built from the 1h archive into 1h / 4h / 1d (a bar counts only if all its hours exist; every trade window is checked for contiguity). 17 patterns from open / high / low / close of the signal bar and earlier bars only (causality tested by truncating the data): hammer, inverted hammer, hanging man, shooting star, bullish / bearish engulfing, piercing line, dark cloud cover, morning / evening star, three white soldiers / three black crows, bullish / bearish harami, doji after a decline / a rise, inside bar. Known at the signal bar's close; ENTER at the next bar's open, EXIT at the close H = 1 or 5 bars after the signal (1h/5h, 4h/20h, 1d/5d); no stop, no target, no tuning; one position per coin. Both sides of every pattern (textbook and mirror). 12bp round trip, longs pay funding 1bp / 8h, shorts receive nothing. Tune before 2024-08-29, holdout after. Statistics give every entry DAY one vote. PASS = net > 0 and t >= 2 AND excess over the matched baseline > 0 and t >= 2 on both halves AND Holm < 0.05 over all sized cells.

**Result (final run, control = entry day x entry slot): PASS 0 of 204.** Only one cell has net > 0 with t >= 2 on both halves - 1h H1 three black crows BOUGHT (the mirror of the textbook short): net +0.13% / +0.12% a trade, t +2.8 / +2.4, excess over its matched baseline just +0.04% / +0.10% (t 1.9 / 2.3), Holm 1.00; at 25bp round trip it is zero. Cells whose excess has t >= 2 on the tune half: 13, kept on the holdout: 0. Cells with |t| >= 2: 14 on the tune half (7 mirror pairs of ~102, about 5 expected by chance), 4 on the holdout (2 pairs). The textbook direction is a coin flip in sign at 1h / 4h (32 of 64 cells negative). Unconditional drift for reference (long, gross per trade, tune / holdout): 1h H1 +0.007% / -0.004%, 4h H5 +0.129% / -0.068%, 1d H5 +0.814% / -0.381%. Per-cell table: `logs/candle_scan.txt`.

**The leak, and how it was found.** The first run used a DAY-matched control (each trade minus the mean of all coins entered the same day) and read: 27 cells with excess t >= 2 on BOTH halves, 8 cells with excess above +0.30% on both halves with 200+ trades, 27 of 49 tune-half cells replicating. The biggest were FADES of strong 4h candles, in both directions, with tens of thousands of trades: bullish engulfing sold +0.44% / +0.34% excess (n 24,557 / 11,881, t +8.3 / +4.0), bearish engulfing bought +0.34% / +0.22%, bearish harami sold +0.43% / +0.41%, doji after a rise sold +0.63% / +0.28%. Because the repo's rule is that every big result is a bug until shown otherwise, `candle_scan_check.py` re-measured those cells (post-hoc, predictions registered before its run): with the baseline also matched on the entry SLOT (the hour of the day, 6 slots for 4h) the excess is -0.00% / -0.00%, -0.06% / -0.08%, -0.02% / +0.06%, -0.03% / -0.07%; 1h H5 doji-after-a-rise short -0.01% / -0.01%. The patterns cluster on market-wide moves in particular slots, and the market's own reaction at that moment is not in a day-wide average. The control was amended (CLAUDE.md s3 has the trap) and the whole table re-run; the first run's log is `logs/candle_scan_daymatched_superseded.txt`. The check also shows the cells were NOT driven by a few days (10 best days removed: excess unchanged), not by one coin (no coin over 5% of the positive total at 4h) and not by one year - the leak was the control, not an outlier. Net returns of those cells were positive (+0.16% .. +0.34% a trade at 12bp, t 1.6-3.2) but that is the market-wide reaction at those moments, which the pattern coin shares with every other coin: pattern coins against other coins at the same moment earn nothing extra. Unconditional slot drift is small and does not persist across halves (4h H5 slots: +0.02..+0.21% on tune, -0.09..-0.03% on holdout).

**Predictions scored.** K1 right (0 pass). K2 right (1 cell net > 0 with t >= 2 on both halves; limit 10). K3: first run WRONG (27 of 49 tune-excess cells replicated), final run RIGHT (0 of 13). K4 (strong candles reverse at 1h / 4h): first run WRONG (21 of 64 textbook cells negative), final run WRONG by a coin flip (32 of 64 = exactly half). K5 (no cell with 200+ trades per half above +0.30% excess on both halves): first run WRONG (8), final run WRONG (5, all 4h / 1d cells with a few hundred to a few thousand trades and t at most +2.7; the 1d H5 cells also have overlapping 5-day windows, so their t is inflated).
Post-hoc check predictions: S1 (slot-matched excess keeps half) WRONG - the whole finding; Y1 (excess positive in 5 of 7 years) right; C1 (25bp: 4h H5 cells still net positive on both halves) WRONG; D1 (positive with the 10 best days out) right; N1 (>60% of coins positive, none over 15%) wrong for the two small cells (15-19 coins, 13-16%).

**What it means.** Candlestick patterns, on their own, carry no information about the coin that prints them: not at 1h, 4h or 1d, not in the textbook direction and not in its mirror, once the control matches the day and the time of day. The one family that looked real (fading strong candles) was the market's own reversal at the moment the candle formed, which every coin shares. Loose thread, not a result: a MARKET-LEVEL rule (fade the whole market after a strong 4h move) is not what this tested and is untested; its net t at 20h was 1.6-3.2 per half before any Holm correction, and the repo's reversal family (capit2, crash bids) already trades the forced-selling version of it. Caveats: pattern thresholds fixed once (body vs the 10-bar mean body, 30% / 10% of range); no stop or target variants; 2020-26 crypto only (the textbook patterns were written for stocks and futures with gaps; forex and gold at Exness prices not scanned); the control also contains the signalling coins, so a pattern that appears on almost every coin at once is controlled away by construction - that case is a market-timing question, not a pattern question.


## Candle patterns WITH trade management (stop, breakeven, trailing, 1R sizing): the shape adds nothing to the management, and the management is a bet on the market's direction (2026-11-02) - `backtest/candle_manage.py`, `logs/candle_manage.txt`, `tests/test_candle_manage.py`

**Question** (the user, after being told the trend book is 'cut losers fast, let winners run, size sensibly': "what about testing these on candle charts"). The first scan (`candle_scan.py`) held every pattern trade for a fixed time with no stop, which is not how a trader uses a candle. Here the candle only chooses WHERE to start; every entry gets the same management a trader would use, and the control runs that very management from random entries. Predictions R1-R5 are in the file's docstring, written before the first run (prior that a cell passes: under 5%).

**Design.** The 17 patterns, both sides, 1h / 4h / 1d bars, point-in-time top-40 perps, entry at the next bar's open (same universe and causality as `candle_scan.py`). Two fixed managements, never tuned (ATR = mean true range of the 14 bars up to the signal bar): TREND = stop 2 ATR (1R), stop to the entry at +3R, trailing stop 20 ATR behind the best price (the deployed trend book's long rule), out at bar 100 at the latest; SCALP = stop 1 ATR, target +2R, out at bar 24 at the latest. Stops and the trail are checked inside each bar (a gap fills at the open; a bar touching both stop and target counts as the stop; breakeven and trail apply from the next bar). Every trade risks exactly 1R; fees (12bp + funding on longs) are charged in R, i.e. divided by the stop distance. Entries whose 1R is under 0.2% of price are skipped (also for the random entries). CONTROL: the same management from EVERY point-in-time coin-bar, same side and bar size, averaged at the trade's entry day x slot. No pyramiding. 204 cells; PASS = net R > 0 and t >= 2 AND excess > 0 and t >= 2 on both halves AND Holm < 0.05.

**Result: PASS 0 of 204 (195 sized). Cells whose excess over the random entries has t >= 2 on both halves: 0.** |t| >= 2 on the excess happens in 17 cells on the tune half and 12 on the holdout, and none keeps its sign on both. Per-cell table: `logs/candle_manage.txt`.

**The management is a regime bet, not a free lunch.** Random entries with the same management, mean net R per trade, tune / holdout: 1h scalp long -0.135 / -0.149, short -0.058 / -0.048; 1h trend long -0.058 / -0.117, short +0.019 / +0.022; 4h scalp long -0.101 / -0.117, short +0.008 / +0.019; 4h trend long +0.140 / -0.128, short -0.027 / +0.017; 1d scalp long -0.042 / -0.147, short +0.009 / +0.070; **1d trend long +0.737 / -0.195, short -0.201 / +0.186.** A random daily long with 'let winners run' made +0.74R a trade in 2020-24 and loses 0.2R since: the bull-market amplifier of CLAUDE.md s6, seen again on random entries. Every long combination is negative on the holdout; the five non-negative holdout combinations are all shorts (alts fell after 2024-08). Win rates match the live book's profile: TREND cells 23% winners, SCALP just over 34% (a 1R stop against a 2R target is 33% before costs).

**Where the apparent winners come from.** 50 of 204 cells have net R > 0 on both halves, and 41 of them are SHORTS; 11 have t >= 2 on both halves, all shorts. Examples: 4h scalp bullish engulfing sold R +0.086 / +0.108 (t +3.9 / +3.5, n 21,376 / 10,426, Holm 0.05), 1h trend bearish harami sold +0.115 / +0.144 (t +3.1 / +3.2, Holm 0.19), 4h scalp doji after a rise sold +0.097 / +0.095 (t +4.0 / +2.8), 1h trend hanging man sold +0.115 / +0.145. Their excess over the random entries at the same day and slot is -0.03 .. +0.03 R (t within +-2.0): a random short at that moment earns the same. The pattern's coins print at market-wide up-moves; what pays is being short after them, with these stops, on every coin alike.

**Predictions scored.** R1 right (0 pass). R2 WRONG (the random-entry control is non-negative on the holdout in 5 of 12 combinations, limit 2 - all five are shorts). R3 right (0 cells with excess t >= 2 on both halves). R4 half wrong (trend 23%, under 30% as predicted; scalp just above the 34% top of the range). R5 WRONG (4 one-hour scalp cells have net R > 0 on both halves, all shorts, R at most +0.05, t at most 2.8, excess -0.03 .. +0.02).

**What it means.** Giving candle entries the stops, breakeven, trail and fixed-risk sizing of a real trader does not rescue them: the shape adds nothing over the same management from random entries (excess within +-0.03R, no cell with t >= 2 on both halves). What the management earns is the market's direction while the trade is open, which is the same regime dependence the machine itself has. Loose thread, now with two different exits pointing the same way (the 20-hour hold in `candle_scan.py`, the 1 ATR / 2R scalp here): shorting after broad strong up-moves on 4h bars is positive on both halves with t 3-4 - a MARKET-LEVEL fade, not a candle result, best Holm 0.05 over 204 cells and found after looking, untested as a market-level rule; the tail risk is a short squeeze on a small coin (MYX +1,137% in a week). Caveats: no pyramiding (the machine's units change is the part that survived every test), one trend rule and one scalp rule, ATR fixed at the signal bar, crypto only, the control contains the signalling coins, the last 24 / 100 bars of every coin's history cannot hold a trade.


## The market-level fade (short the crypto market after a strong 4h up-move): dead, and the sign is the other way - strong up-moves continue (2026-11-02) - `backtest/market_fade.py`, `logs/market_fade.txt`, `tests/test_market_fade.py`

**Question** (the loose thread of `candle_scan.py` and `candle_manage.py`, then the user: "Test it"). Two different exit rules had found that 41 of the 50 candle cells positive on both halves were shorts, with zero excess over random entries at the same moment: 'being short after broad strong up-moves on 4h bars pays on every coin alike'. That is a claim about the market, so it was tested as a market rule, once, with a three-fold bar because the lead was found after looking. Predictions T1-T4 are in the file's docstring, written before the run (my prior that it passes: ~20%).

**Design.** R(t) = the equal-weight mean 4h return of the point-in-time top-40 perps (at least 10 coins); z(t) = R(t) over the standard deviation of the previous 180 bars (itself excluded). Signal z >= thr (1.5, 2.0, 2.5); enter at the next 4h open, exit at the close H = 1, 5 or 12 bars after the signal (4h, 20h, 48h); SHORT the equal-weight basket of the same coins (and BTCUSDT alone); one trade at a time; 12bp on the notional, shorts receive no funding, no stop. Reference: the mirror, LONG after z <= -thr. Null: the whole signal series moved by a random whole number of days (30 or more, time of day kept), 1,500 shifts, p per half. PASS = the primary cell (basket, z >= 2.0, H = 5) positive with t >= 2 and shift p < 0.05 on both halves AND at least 7 of the 9 basket-short cells positive on both halves.

**Result: NO PASS - and not close. The primary cell loses on both halves.** Basket short, z >= 2.0, 20h: 184 / 95 trades, mean net **-1.22% / -0.60% a trade** (t -3.4 / -1.5, shift p 1.000 / 0.933); negative in every year (sum of net on 1x notional: 2020 -23%, 2021 -84%, 2022 -59%, 2023 -47%, 2024 -57%, 2025 -11%, 2026 -16%); median trade -1.4%, 5th percentile -7.7%, **worst -28.4%** (a one-way squeeze). Plateau: 0 of 9 basket-short cells positive on both halves (the only positive half is 48h at z >= 1.5 on the holdout, +0.34%, p 0.20). BTC alone has the same sign (-0.72% / -0.38% at z >= 2, H5). Shorting the basket at EVERY bar for 20h earns -0.25% / -0.06% a trade (the drift of the period), so the fade is worse than shorting at random: after a strong 4h up-move the basket went on to rise about +1.1% (tune) and +0.5% (holdout) over the next 20 hours on average - continuation, which is what the trend book trades; not tested as a rule here (it was not registered).
Reference, the mirror (long after z <= -thr, the capitulation family): positive on the tune half with shift p 0.001-0.003 (basket H1 +0.47%, H5 +0.81%, H12 +1.61% at z <= -2, t 2.1-2.9) and gone on the holdout (+0.07%, -0.22%, -0.69%; shift p 0.19, 0.58, 0.77); BTC alone shows nothing. So even the known bounce is not a market-level 4h-z-score rule since 2024-08; the repo's working version is coin-level forced selling (capit2: coin -10% in 24h plus a limit order).

**Predictions scored.** T1 right (the primary does not pass). T2 right (plateau 0 of 9). T3 right (the mirror beats the short on both halves - trivially, the short loses). T4 right (worst trade -28.4%).

**What it means.** The thread is closed. The shorts that paid in the candle scans had no excess over their own controls, and the market rule they seemed to point to loses money in every year. I did not chase why a random managed short at the candle moments earned +0.1R while a short after the strongest up-moves loses: the direct test is the cleaner one and both read the same data. Caveats: one signal definition (equal-weight z of 4h returns with a 180-bar scale), three thresholds and holds, no stop on the fade, the basket is 40 coins so 12bp is on notional, funding on shorts counted as zero (positive funding after pumps would have paid shorts a few bp, not 1%).


## "High leverage on BTC, liquidation far away, wait as long as it takes to be in profit" (2026-11-02) - `backtest/wait_leverage.py`, `logs/wait_leverage.txt`, `tests/test_wait_leverage.py`

**The idea** (the user): $50 on one BTC trade at 50x or 100x, trust that BTC will not reach the liquidation price soon, wait however long it takes to be in profit. No predictions were registered (arithmetic, not a search); the check is the random-walk value d / (d + target). BTCUSDT 1h bars 2020-01 .. 2026-09 (58,940), every hour an entry at the next open, liquidation distance = 1 / leverage - 0.5% maintenance margin (smallest-tier assumption), 0.06% taker a side, longs pay 1bp / 8h funding while waiting.

**A. BTC does reach the liquidation level.** Share of entries whose liquidation level is touched within 1 day / 7 days / 30 days: 100x (0.5% away) 80% / 93% / 96%, and 27% within the first hour; 50x (1.5%) 50% / 80% / 89%; 20x (4.5%) 12% / 47% / 70%; 10x (9.5%) 2% / 18% / 45% (66% within 90 days). 'BTC will not touch it soon' is wrong at 50x and 100x.

**B. The rule: wait with no stop until price is +0.30% in your favour (about +0.18% after the 0.12% round trip) or liquidated.** Wins are frequent and fast (median 1-2 hours) and the average try loses money, because a loss is the whole margin: 100x long 56% wins / 44% liquidated, mean return on margin -34.5% a try (short -34.7%); 50x 82% / 18%, -10.4% (short -10.9%); 20x 94% / 6%, -2.9% (-3.9%); 10x 97% / 3%, -1.1% (-2.3%). Ten tries without a wipe-out: 0.3% at 100x, 14% at 50x, 53% at 20x. The simulated win shares match the random-walk values (62% / 83% / 94%). A win pays $9.00 at 100x and $4.50 at 50x on $50 against a $50 loss; waiting costs funding of $1.50 a day at 100x (3% of the margin) and $0.75 a day at 50x (1.5%).

**What it means.** The strategy has the shape of the retail RSI trade (doc 02, 2026-10-08): a high win rate that feels like it works, ended by one total loss. It agrees with `one_shot.py` (100x: -44% of the stake a try) and `scalp_1m.py --kelly` (the best edges tolerate 4-11x at zero fees). Keeping liquidation truly far away means little leverage on the whole account, i.e. holding BTC with a few dollars of profit; and 'wait however long' on a perp pays funding the whole time. Caveats: one maintenance-margin assumption (check the exchange's liquidation price), hourly bars (a bar touching both target and liquidation counts as liquidated), funding fixed at 1bp / 8h, longs and shorts both shown, 2020-26 only.


## Many indicators together, done honestly: a walk-forward cross-sectional model on the PIT top-40 - nothing passes, but one real tilt appears (low volatility beats high volatility), and it is not a closing-print artifact (2026-11-02) - `backtest/indicator_model.py`, `backtest/indicator_model_check.py`, `logs/indicator_model.txt`, `logs/indicator_model_check.txt`, `tests/test_indicator_model.py`

**Question** (the user: "some correlation of different indicators or patterns together ... run it"). Combinations of a few indicators had been swept before (rsi_confluence ~2,000 configs, day_long 1,350 filters, tv_indicators, sweep_confluence); sweeps produce winners by luck (protocol_lab: the best of 60 noise rules +2.9bp in sample, +0.04bp out). This is the one proper version: ALL the standard indicators at once in a model fitted only on the past, scored on dates it never saw, against the best single indicator picked the same way. Predictions P1-P5 are in the file's docstring (prior that any cell passes: under 10%).

**Design.** 364 point-in-time top-40 perps, UTC daily bars from the 1h archive, 91,042 coin-days. 32 price-and-volume features known at the day's close (returns over 1-60 days, RSI(14) and (3), stochastic, Bollinger %b and width, EMA distances, MACD histogram, ATR%, volatility ratio, volume z-score and change, the last candle's body / wicks / close location, distance to highs and lows, returns relative to BTC, share of up days, best and worst day; causality tested by perturbing the future) turned into cross-sectional ranks; target = the rank of the forward return entered at the next open and left H = 1, 3 or 7 days later. Ridge (alpha 10) and gradient boosting (depth 3, 150 trees), fixed settings, refitted every calendar quarter from 2022-01 on rows whose whole window ends before the quarter (embargo H + 1 days); SINGLE = the one feature with the largest mean daily rank correlation on the training window, traded in its own direction. Scores out of sample 2022-01 .. 2026-09, tune before 2024-08-29: the daily rank correlation (IC) and the SPREAD (top fifth minus bottom fifth) net of 24bp and the long leg's funding, with non-overlapping entries for each of the H weekday alignments (mean, t, worst alignment). PASS = net spread > 0 with t >= 2, worst alignment > 0 and IC t >= 2 on both halves, Holm < 0.05 over the 6 primary cells.

**Result: 0 of 6 pass (best Holm 0.92). Mean IC, ridge / gradient boosting / single, tune and holdout: H1 +0.108 / +0.115 / +0.091 and +0.105 / +0.110 / +0.094; H3 +0.119 / +0.122 / +0.108 and +0.130 / +0.137 / +0.134; H7 +0.126 / +0.134 / +0.127 and +0.175 / +0.182 / +0.190 (t 5-14 everywhere).** Net spread (tune / holdout): ridge H1 -8.5 / +5.4bp (t -0.8 / +0.3), H3 +4.4 / +5.0bp, H7 +34 / +46bp (t +0.5 / +0.4); gradient boosting H1 -7.7 / +5.2bp, H3 +26 / +39bp (t +1.0 / +0.8), H7 +62 / +153bp a week (t +1.0 / +1.4); several worst alignments are negative. The combination does not beat the best single feature (paired t under 2 in 6 of 6; best gradient boosting H7 +54bp t +1.2 / +94bp t +0.5).

**What the IC is.** The single feature was ATR% (average true range over price) in 17-19 of the 19 fits - used with the NEGATIVE sign: LOW-volatility coins outperform HIGH-volatility coins in rank terms (the rank of ATR% against the next day's return is -0.086 over all days; the same day's -0.153). By calendar year the single feature's IC at H1 is +0.109 (2022), +0.071, +0.082, +0.116, +0.080 (2026). The ridge adds only about +0.015 IC to it. Because +0.10 is far above anything in this repo (and the repo's cross-sectional reversal once 'came from the close print'), `indicator_model_check.py` re-scored the same predictions with entry delayed: at 01:00 UTC the H1 IC keeps about 90% (single +0.082 / +0.094 against +0.091 / +0.094; ridge +0.097 / +0.099 against +0.108 / +0.105), at 04:00 about 85%, and entering a whole day later still gives +0.090 / +0.095 (single) and at H7 +0.126 / +0.189. It is a persistent cross-sectional tilt, not an artifact. As a trade it stays unproven: the top-minus-bottom-fifth spread has heavy tails (the high-volatility leg is where pumps and squeezes live), so net t is 1.4 at best; a long-only version (top fifth, i.e. the calmest coins, minus the universe, net of 12bp and funding) is +27 / +41bp a week at H7 for the single feature (t +0.8 / +0.8) and +18 / +28bp for ridge (t +0.6 / +0.6), and negative at H1.

**Predictions scored.** P1 right (0 of 6 pass). P2 WRONG (I registered every IC between -0.01 and +0.04; they are +0.105 .. +0.182). P3 right (the combination never beats the best single feature significantly: 6 of 6). P4 WRONG (the H1 holdout net spreads of ridge and gradient boosting are slightly positive, +5bp, t +0.3). P5 WRONG (0 of 6: the holdout gross spread is above the tune half's in every cell). Post-hoc check: C1 (H1 IC halves with a one-hour delay) WRONG, C2 (H7 keeps 70%) right.

**What it means.** The answer to 'many indicators together' is that they add almost nothing to ONE of them: a volatility measure used backwards carries nearly the whole signal. That signal is the low-volatility effect - the calm coins (BTC, ETH, BNB and similar) beat the wild ones every year 2022-2026 - which is the cross-sectional face of the alts' bleed against the majors, the repo's dead 'long BTC / short alts' dispersion trade (`bear_alpha_pit.py`) in a wider costume. It is real in ranks and not capturable at a significant level as a spread. Caveats: 2022-26 is one long stretch of alts underperforming the majors, so this may be the regime rather than a stable premium (2020-21 only trained the model, it was never scored); price-and-volume features only; one model family each; the target's NaN handling drops coins with no exit price; no funding or sentiment feature on purpose.


## The Analyst desk reviewed call by call: why the winners won, why the losers lost, and what a fix could and could not be (2026-11-02) - `backtest/analyst_review.py`, `logs/analyst_review.txt`, `logs/analyst_calls_snapshot.csv`, `tests/test_analyst_review.py`

**Question** (the user): analyse the Analyst desk on the dashboard in depth - which trades succeeded and why, which did not hit their targets and why, and what to do differently. Data: the desk's own log (52 calls, 2026-10-27 .. 2026-11-01, 48 resolved: 12 wins, 31 losses, 5 expired, 4 open; book $296.53 booked) plus the 1-minute bars of every call's life and the rest of its horizon. Hypotheses H1-H6 were registered in the file after reading the call table and before any path was computed.

**The record.** 25% of calls hit the target against a 20% random-entry baseline and a 31% break-even rate; gross result -0.10R a call (se 0.20) BEFORE fees, -0.35R after. The 12bp fee costs 0.24R a call on average (0.51R for the 10 calls with stops under 0.4% of price, up to 0.76R): 11.7R of the -16.7R net loss is fees, gross is -4.9R. By rule: SMC (sweep and reclaim) 29% vs 16% baseline, gross +0.11R; SR (support / resistance) 25% vs 25%, gross -0.17R; FIB 0 of 3. By side: longs 36% vs 11% baseline (gross +0.25R, n 14), shorts 21% vs 24% (gross -0.25R, n 34). Only 11 independent bets (calls on the same day in the same direction ride one market move); 5 of them beat their baseline.

**The call that did the damage: reward:risk above 4.** 16 calls (a third of all), 0 wins against a 8% random baseline, -1.27R each, -20.3R in total - MORE than the whole net loss of -16.7R; the other 32 calls are +3.6R net (RR 2.5 or less: 23 calls, 39% hit vs 30% baseline vs 40% break-even, +0.07R net). They come from tiny stops (0.15-0.5% of price: the rule puts the stop 0.5 ATR beyond the level) against targets 4-16R away (the nearest resistance or the 24-bar extreme). Stops of 0.8% or more: 13 calls, 6 wins (46% vs 15%), gross +0.80R (se 0.43) - a post-hoc bucket on about five independent moves, not a finding.

**Winners (12).** Median 481 minutes to the target (quartiles 287 / 1,394); they barely went against the position (median MAE 0.25 of the stop); average RR 2.1, stop 0.84%. Nine of the twelve rode two market moves: the 2026-10-28 21:07 sweep-and-reclaim SHORTS (ETH, SOL, gold, with QQQ expiring in profit) fired in the same hour after a spike, and the 10-29 longs at supports (XRP, ETH, BNB) came on the day BTC fell 4.1% (a capitulation bounce, the repo's known family). Winning calls are patient and close to the market's move; there is no sign of a level that works on its own.
**Losers (31).** Median 217 minutes to the stop (6 within an hour, 12 within three); the best they ever did was a median 12% of the way to the target (7 of 31 reached a quarter, 5 half, 2 three quarters: #1 XRP got to 95% in 701 minutes, #21 BTC to 97%). Price touched the TARGET after the stop and before expiry in only 4 of 31 - so 'stopped then right' is not the failure; the typical loser simply moved the wrong way. The stop that would have survived to expiry was a median 3.0x the stop used (2x: 8 of 31; 3x: 15 of 31).
**What-ifs on the same entries** (desk.resolve's pessimistic rules; judged by mean GROSS return per trade, which is ~0 for a no-edge variant): as logged +0.080% (se 0.173); stop x1.5 +0.010%; stop x2 -0.045%; target at 1R +0.048% (hit rate 48%); at 1.5R +0.053%; RR capped at 2 +0.089%; no RR above 4 +0.302% (t 1.2, n 32, net +0.18%); RR <= 4 and stop >= 0.4% +0.341% (t 1.2, n 29, net +0.22%); SMC only +0.510% (t 1.6); SR only -0.183%; FIB only -0.816% (t -2.7, 3 calls). None reaches two standard errors above zero; widening the stop makes it worse.

**Predictions scored.** H1 right (hit 25% vs 20%, gross -0.10R). H2 half wrong (mean fee 0.24R, just under 0.25R; 0.51R for the small-stop calls, as predicted). H3 right (RR > 4: no wins, -20.3R of the -16.7R). H4 half wrong (median time to the stop 217 minutes, over my 3 hours; but 24 of 31 never reached 25% of the way). H5 wrong (4 of 31 losers touched the target later, 13%, not 20%). H6 right (no variant 2 standard errors above zero).

**What it means and what a fix could be.** The entries have no demonstrated skill (gross about zero); the loss is mostly self-inflicted geometry and fees: calls whose targets are 4-16R away with stops a few ticks wide almost never hit, and every call pays 12bp whatever its stop. Honest options, in order of how much the data supports them: (1) filter the desk's own calls to RR <= 4 and stop >= 0.4% - a subset of what it already logs, so it needs no new bot and can be judged on the next calls (the in-sample subset is about +0.1R net a call with t 1.2: not proven, but it removes the losses that are certain); (2) do NOT widen stops (the what-ifs say it hurts; only 13% of losers came back); (3) cheaper execution (maker orders) would cut the fee to about a third and still leave the book at about -0.18R a call (gross -0.10R less fee 0.08R); (4) the two groups with a tilt worth more calls rather than a rewrite are SMC sweep-and-reclaim and long bounces at supports, each too small (n 21 / 14, t 1.6 / 0.6 gross) to claim. Nothing was changed on the desk: its review (100 resolved calls or 2027-01-31, doc 22) stands as the verdict. Caveats: 48 calls on about 11 independent bets in one week (BTC +0.9, +0.5, -4.1, -0.8, +0.3, +0.5% on the days); every what-if is in-sample and reuses the same entries; the 'target later' and 'stop needed' numbers look at the path to expiry, which a trader would not have seen.

## 2026-11-02 (night) - A volume floor on the market-neutral and daily books: every floor wins the holdout, loses the tune half, and loses to betting smaller (`backtest/universe_floor.py`)

**Why it was run.** The forward-test read of the same day (CLAUDE.md s10) found the live losses concentrated in small, pumpy names - SOPH squeezed in the MN short leg, AKE -45% in one daily-book trade, BTW in five books at once. The user: "Yes, run it" to a test of narrowing the universes. Nothing in any bot changed; this is a backtest on the cached data.

**What was tested.** The machine's MN book as `all_books.machine_books` builds it (half 30-day momentum, half RSI(14), 10% of the eligible names a side, at least 3, weekly, +50% short-leg exit, 12bp on turnover, real funding) on the PIT top-N by the prior month's volume, N = 60 (base) against 40 / 30 / 20, on all 7 rebalance weekdays; plus a control (N = 60 with 3 names a side) because a smaller universe also means fewer names a side. The daily book (deployed 20-day-mean exit, 8 slots, 3 day boundaries x 10 orderings, marked to market) on the PIT top-40 against top-30 and top-20. `scored_run_floor` is `moderate_retests.scored_run` with the hard-coded 20-name minimum and the names-a-side rule as switches; it reproduces `scored_run` exactly at the base (asserted in `main()` and in `tests/test_universe_floor.py`, 11 tests, 20 of 20 mutations caught). Bar, registered first: a floor passes only with a higher Sharpe than the base on BOTH halves (split 2024-04-07) on average over the 7 weekdays and higher on at least 5 of 7 weekdays on each half (daily: both halves' CAGR higher and the fall no deeper).

**Result: no floor passes, and the pattern is the repo's mined-holdout signature.**
| MN (Sharpe, mean of 7 weekdays) | tune | holdout | paired vs base, tune / holdout | max fall |
|---|---|---|---|---|
| base top-60 | +1.38 | +1.36 | - | 31% |
| top-40 | +0.98 | +1.44 | -0.40 (0/7 weekdays) / +0.07 (6/7) | 44% |
| top-30 | +0.84 | +1.51 | -0.54 (0/7) / +0.15 (5/7) | 47% |
| top-20 | +0.62 | +1.55 | -0.76 (0/7) / +0.19 (7/7) | 46% |
| control, top-60 with 3 names a side | +1.43 | +1.23 | +0.04 / -0.13 | 42% |
Every floor loses the tune half on all 7 weekdays and gains on the holdout; against the k-matched control the holdout gain is +0.21..+0.32, so on the holdout it is coin size and not concentration, and the tune half says the opposite. In the live tape's weeks (alt-median 30-day return <= -15%, 97 weeks per weekday) no floor helps: base -0.17%/wk, top-40 -0.32, top-30 -0.21, top-20 -0.41 (other weeks +1.84 / +1.79 / +1.79 / +1.60); the worst week gets no better (-25 to -31% against -26%). Daily book: top-40 +157% tune / +65% holdout / fall 61%; top-30 +95% / +23% / 65%; top-20 +102% / +36% / 50%; both floors are lower on both halves in 30 of 30 pairs (tune -61 / -55 points, holdout -41 / -29). Top-20's 11-point shallower fall does not beat the bet-smaller line: the base at 0.75x has +116% / +52% / fall 51%.

**Predictions scored.** U1 right (no MN floor passes), U2 right (top-20 worst of the three), U3 right (no floor lifts the live-tape mean above +0.5%/wk), U4 half wrong (the daily floors lower the holdout, but top-20's fall is 11 points shallower; it fails the bet-smaller line), U5 right (nothing worth a shadow book).

**What it means.** The small names are not what is wrong with the live books: removing them costs the tune half across the board, helps only on 2024-26 (when large coins held up better than the pump coins), does not help in the weeks that resemble the live tape and deepens the MN fall (31% -> 44-47%). A volume floor is not a lever; the MN book's weak weeks in alt-bleed tapes (-0.17%/wk here, -0.4% in the earlier cut) are what the strategy does in that regime. Caveat: volume rank is the only size measure in the data (no market capitalisation), so 'micro-cap' is approximated by 'not among the most-traded'. In the live bot's November pool file (`logs/combo_bot_dry_final/month_pool.json`, taken here as listed in volume order; the names were picked from the October pool, not checked) BTW sits 19th, AKE 50th, PONS 65th, USELESS 88th, MARSCOIN 103rd, and FLOCK and SOPH are not in its first 120 - so several of the names that hurt are not tested by a top-20/30/40 floor in either direction, and the live universe is rebuilt from the prior month's volume and differs from the backtest's by 37 of 120 names (CLAUDE.md s10, 2026-10-22). Kills stay permanent: do not propose a size floor again without a measure of size that is not volume rank.

## 2026-11-02 (evening) - The maker rebuttal tested: resting at the touch on wide-spread pairs earns the spread and gives all of it back (`backtest/passive_markout.py`, `logs/passive_markout.txt`, `tests/test_passive_markout.py`)

The user asked for the counters to "the order-book edge is smaller than the fee". The strongest one: stop predicting, rest orders at the touch as a MAKER, pick pairs whose spread is wide in basis points, and use the book (imbalance) to avoid being picked off. Tested on the ~40 minutes of real order books the Module 5 recorder captured for the ten pairs (2026-10-30, 13:57-15:03 UTC). Predictions M1-M4 are in the file's docstring and were written before the first run.

**The measurement (a "markout").** Every time a taker SELL prints exactly at the best bid, a resting bid there (queue permitting) is filled at the bid; its markout is how far the mid has moved from that fill price 1 / 5 / 30 / 60 seconds later, in bp (a buy at the ask is the mirror). The half-spread is earned at once; whatever the mid does afterwards is adverse selection when negative. Net bounds per fill, maker fee 2bp: UPPER = markout - 2bp (exit free at the mid), LOWER = markout - 2bp - half-spread - 6bp (exit by a taker order). The queue is ignored, so this is the most generous version of the maker's day. Standard errors cluster by minute.

| pair | spread bp | fills | markout 5 s | 30 s | 60 s | half-spread | net UPPER 30 s | net LOWER 30 s |
|---|---|---|---|---|---|---|---|---|
| BTC | 0.01 | 10,516 | -0.47 | -0.91 +- 0.32 | -1.51 | 0.01 | -2.91 | -8.92 |
| SOL | 0.11 | 3,534 | -1.01 | -1.47 +- 0.55 | -1.62 | 0.05 | -3.47 | -9.53 |
| XRP | 0.81 | 2,201 | -0.78 | -1.19 +- 0.41 | -1.88 | 0.40 | -3.19 | -9.59 |
| DOGE | 1.33 | 632 | -1.24 | -1.41 +- 0.90 | -2.58 | 0.66 | -3.41 | -10.09 |
| SUI | 1.13 | 1,159 | -1.03 | -1.71 +- 0.79 | -2.24 | 0.57 | -3.71 | -10.29 |
| LINK | 0.91 | 683 | -1.26 | -0.82 +- 0.42 | -0.93 | 0.46 | -2.82 | -9.30 |
| WLD | 2.49 | 1,145 | -0.67 | -2.31 +- 1.49 | -2.91 | 1.24 | -4.31 | -11.57 |
| SHIB | 2.12 | 390 | -0.06 | -0.57 +- 0.88 | -0.98 | 1.06 | -2.57 | -9.85 |
| ADA | 5.24 | 565 | -0.43 | +0.29 +- 0.57 | -0.10 | 2.62 | -1.71 | -10.32 |
| DOT | 10.60 | 170 | -0.37 | -0.83 +- 0.87 | -1.72 | 5.30 | -2.83 | -14.12 |

**Book lean (30 s markout, imb1 leaning WITH the fill vs AGAINST it):** WITH is better on 10 of 10 pairs, average +3.0bp (BTC +1.61, SOL +1.04, XRP +0.70, DOGE +4.17, SUI +0.68, LINK +1.96, WLD +5.80, SHIB +0.61, ADA +0.50, DOT +13.33 on 13 fills). BTC's is the one with weight (+0.12 +- 0.38 on 1,399 fills vs -1.50 +- 0.52 on 3,425) and it still leaves BTC at +0.1bp against a 2bp fee.

**A bug of mine, found before the first table was interpreted.** The first run counted every print at or BELOW the touch as a fill AT the touch. A count of prints against the pre-print book (BTC, one recording: 2,786 sells at the bid, 8,718 strictly below it) showed 76% were deeper levels of a sweep, which a resting top-of-book order does not fill at its own price, and sweeps are the most informed trades. Fixed (a fill = a print exactly at the touch, one per taker order per millisecond; first-run column kept in the log). It moved BTC from -1.50 to -0.91 and changed no conclusion. Two of my own tests were wrong first (a markout that is exactly 0, and a toy recording that ended before the horizon); the mutation pass then found two missing tests (the same-millisecond dedupe and the end-of-recording guard), both added: 12 tests, 8 of 8 mutations caught.

**Predictions scored.** M1 right (no narrow or medium pair earns the 2bp fee, every lower bound negative). M2 WRONG: I expected the wide pairs to keep part of their half-spread and DOT's upper-bound net to be positive. DOT's mid moved ~6bp against the maker within 30 s (half-spread 5.3bp earned, -0.83bp left), WLD and SHIB are negative, only ADA is positive (+0.29 +- 0.57). M3 right on both halves (the lean helps, by +3.0bp on average; no lower bound turns positive). M4 wrong on the numbers (170-1,145 fills, standard errors 0.6-1.5bp) and right in spirit for the WITH cells (13-132 fills).

**What it means.** On these 40 minutes a passive maker with perfect queue priority would LOSE on all ten pairs, before the exit, because the mid moves against the filled side by about the half-spread or more within 30 s (adverse selection). The book does carry information about which fills are toxic, as the lean split shows, but not enough to reach a 2bp maker fee, and the lean cell is the one the queue-free bound flatters most (a touch leaning your way means a long queue ahead of you, so you only fill when a large taker clears it). This is the same answer `book_hist.py` found with a queue-aware replay on seven DOGE days (maker fills lose, the fills are the signal's failures), reached from a different side.

**Limits.** About 40 minutes of one busy afternoon, one session; fills are an upper bound with no queue; the maker fee of 2bp is the standard tier (a VIP or zero-fee maker tier would change the UPPER column by up to 2bp, which still leaves 9 of 10 pairs negative at 0 fee and ADA at +0.3 on a +-0.6 error); the lean cells are small on the wide pairs. A real answer needs the official multi-day record, which was never started (project parked at the user's word, 2026-10-30). Nothing deployed, nothing committed.

## 2026-11-02 (late) - RSI with a take-profit / stop-loss ratio: no ratio pays per trade, the best cell's "+0.37R" was a weighting convention, and the one rescue was a look-ahead (`backtest/rsi_ratio.py`, `backtest/rsi_ratio_check.py`, `logs/rsi_ratio.txt`, `logs/rsi_ratio_check.txt`)

**Why it was run.** The user, remembering the RSI results: "you said RSI was working but with a few big losses - there must be a ratio of taking profit and stop loss that is profitable." The earlier RSI files each tried one or a few exits (`rsi_only.py`: no stop, and one +2% / -4% bracket that lost on every cell; `rsi_factors.py`: factor exits; `rsi_confluence.py`: +2% or four days). Nobody had swept the ratio itself against a control. Nothing in any bot changed.

**The arithmetic first.** With a stop of 1R and a target of T R, a trade with no edge wins 1/(1+T) of the time, so its average is minus the fees at EVERY ratio; the ratio only chooses between winning often for small amounts and rarely for big ones. A ratio can pay only if the ENTRY wins more often than a random entry does with the same bracket. Break-even win share = (1 + cost) / (1 + T), cost in R.

**What was tested (`rsi_ratio.py`, predictions Q1-Q5 in its docstring).** RSI(14) crossings on 1h and 4h bars of the point-in-time top-40 perps (364 coins, dead ones in): under 30 / 25 / 20 (the textbook long), over 70 / 75 / 80 (the textbook short), and RSI under 20 with a 3x volume spike (`cap20`, the capitulation buy). Both sides for every flag; 16 brackets (stop 0.5 / 1 / 2 / 4 ATR = 1R, target 0.5 / 1 / 2 / 4 R, out at bar 24); 12bp + funding charged in R; each cell against the SAME bracket from every point-in-time coin-bar at the same entry day x slot; tune / holdout at 2024-08-29; PASS = net and excess both t >= 2 on both halves and Holm < 0.05 over 448 cells. Tests: 13, 27 of 27 mutations caught.

**Result: PASS 0 of 448, and no ratio makes money per trade.**

| textbook oversold LONG, per-trade mean net R (tune / holdout), 6 cells per bracket averaged | 1 : 0.5 | 1 : 1 | 1 : 2 | 1 : 4 |
|---|---|---|---|---|
| pooled over the four stops | -0.159 / -0.117 | -0.128 / -0.070 | -0.122 / -0.046 | -0.127 / -0.038 |

Per bracket: all 16 are negative on the tune half (-0.04 to -0.40R); on the holdout 15 of 16 are negative (-0.35 to -0.00R) and the best, a 4 ATR stop with a 1R target, is +0.010R. The textbook SHORT (overbought) is negative in every one of its 16 brackets on both halves (-0.04 to -0.48R) and is WORSE than a random short entered at the same moment by 0.02 to 0.18R: after RSI crosses up through 70 the coin tends to keep going.
- **The win share is set by the bracket, not by the RSI:** textbook cells win within 1.7 points of the control's win share on average (e.g. 1 ATR / 2R: 34% against 33%; break-even about 36%). The excess over a random entry at the same moment is -0.03 to +0.07R on the long side, so the bracket decides how often and how much, and the entry decides nothing.
- **Random entries lose under every bracket too:** 54 of the 64 (bar size x side x bracket) control cells are negative on the holdout; the 10 that are not are all 4h shorts, the highest +0.049R.
- **cap20 (RSI under 20 + volume spike) on 4h longs, 273-288 trades on the tune half, 136-137 on the holdout:** negative per trade on the tune half in all 16 brackets (-0.02 to -0.41R), positive on the holdout in 15 of 16 (+0.09 to +0.78R). The sign flips between halves, so nothing here is a result - but note what a stop does to the one RSI trade that had an edge: `rsi_confluence.py`'s +2% / four days / NO stop was +1.0% a trade on both halves, with dips inside the trade of 29-53%. Put a stop of 4 ATR (8-12% on 4h bars) on it and the tune half is negative.

**Two traps that nearly produced a false answer (both are now in CLAUDE.md s3).**
1. **The day-vote mean is not money.** The first log printed only the mean of entry-day means (every day one vote - right for the t statistics, as in `candle_scan.py`). The best textbook bracket, 1h RSI under 30, stop 1 ATR, target 4R, read **+0.368R / +0.257R** (t +8.2 / +4.7, Holm 0.00); its excess over the control was only +0.03 / +0.01. A check on the trades gave **-0.150R / -0.123R a trade** and negative in each of 2020-2026 (`rsi_ratio_check.py`, 27,507 trades): a market-wide sell-off puts 100 or more oversold signals into one day (median day 8, p90 43, max 102 for this bracket, 122 for the 0.5 ATR one), they lose together (worst day -107R on 102 trades, 2022-01-21), and one vote per day makes them weigh like a quiet day's single winner. A capped account (0.3% of booked equity risked a trade, at most 3 / 5 / 10 open, 5 orderings of simultaneous signals, $300) ends at x0.07 / x0.02 / x0.00 over the 4.5 tune years and x0.26 / x0.14 / x0.06 over the 2.1 holdout years for that bracket; every one of the 36 account rows (four brackets, three caps, ungated and two causal gates) loses money on both halves, between -16% and -96% a year. `rsi_ratio.py` now prints the per-trade mean beside every day-vote mean (the first run's log is kept as `logs/rsi_ratio_dayvote_first_run.txt`).
2. **A look-ahead rescue.** Splitting those trades by how many coins signalled on the SAME CALENDAR DAY looked like the fix: days with 1-24 signals win +0.03 to +0.90R a trade, flush days (25+) lose -0.33 to -0.49R, same signs on both halves (32 of 32 quiet-day buckets positive). The day's count includes signals at hours the bot has not yet seen. Counted over the 24 hours up to and including the entry hour, **0 of 40 buckets are positive** (-0.02 to -0.42R) and gating on it (24 or 9 signals) still loses 16-84% a year. Same family as the intrabar look-ahead and "selecting on the future" in CLAUDE.md s3.

**The one per-trade-positive cell.** 15 cells keep an excess over the control with t >= 2 on both halves. Fourteen are 1h "mirror" longs - buying the RSI cross UP through 70 or 75 - with excess +0.03 to +0.16R and per-trade means of -0.30 to -0.00R: the entry carries real information against a random entry at that moment and cannot pay 12bp at stops of 0.5-4 ATR on 1h bars. The fifteenth, **4h RSI over 80, long, 4 ATR stop, 4R target** (775 / 313 trades, win 50% / 52%), is +0.227R / +0.292R per trade with excess +0.186 / +0.188R (t +3.8 / +2.1), Holm 1.00 over 448 cells. Strong up-moves continuing is what `market_fade.py` found the day before and what the trend book already trades; a stop of 4 ATR on a 4h bar is 8-10% of price. A lead found after looking at 448 cells, not tested further, not a candidate.

**Predictions scored.** Q1 right (0 pass). Q2 right, just (10 non-negative control cells, highest +0.049). Q3 WRONG (15 cells, not at most 3, and the textbook shorts sit up to 0.18R BELOW the control rather than within 0.03). Q4 right (1.7 points). Q5 WRONG (no bracket is positive on both halves). The three predictions of `rsi_ratio_check.py`, stated after the fact (C1 per-trade negative everywhere, C2 same-day buckets "rescue" and causal ones do not, C3 every capped account loses), were all right.

**What it means.** For RSI mean-reversion entries there is no take-profit / stop-loss ratio that pays. The classic retail shape (win 80-90% with a small target and a rare big loss) is the no-stop trade of `rsi_only.py`; cutting the big loss with a stop costs more in bounces than it saves (cap20 is the clean case), and ratios that win less often (1:2, 1:4) just trade a smaller win share for a bigger payoff at the same average, minus the fee. The money in this family is not in the ratio: it is the capitulation buy that the machine already runs as capit2 (a coin down 10% in 24 hours, a limit order 2% under the close, a +5% exit, no price stop), which `rsi_confluence.py` and `capitulation_*.py` measured at +1% to +4% a trade. Anyone trading RSI by hand should expect about -0.1R a trade whatever ratio they pick, with the fee taking 0.1-0.3R of it at stop distances of 0.5-2% of price.

**Limits.** Stops 0.5-4 ATR and targets 0.5-4R only, a 24-bar cap, no breakeven move, trail or pyramid; 1h and 4h bars; point-in-time top-40; the wide no-stop trade is `rsi_only.py` / `rsi_confluence.py`. The day-vote convention also sits in `candle_scan.py` and `candle_manage.py`: their conclusions (nothing passes) stand, but their printed R columns are day-vote means, and a positive cell there would have needed this per-trade check. The causal gate was tested at two thresholds on the four brackets that read best, not on all 16. The numbers in `rsi_ratio_check.py` were first run as scratch scripts (same results).

## 2026-11-02 (night) - "Could it be RSI?": every common RSI setting at the NASDAQ trader's entries, and as a signal on its own - no (`backtest/his_rsi.py`, `logs/his_rsi.txt`, `tests/test_his_rsi.py`)

The user, told that his direction was not found in 72 sections of tests, asked whether it could be RSI. RSI(14) on 1- and 5-minute candles was already measured at his clean entries (his_ta.py, s30: rank 0.46 / 0.44, p 0.50 / 0.33). That is one setting, so the grid was run: 15-second, 1-minute and 5-minute candles x RSI periods 2-14 x three forms (the level, the three-candle slope, and a hook up through 30) = 51 cells, every one sign-aligned to his direction, closed candles only. Predictions P1-P4 in the file first.

**Stage A (does he stand out?)**, his 25 clean entries (April on) vs ~80 same-day moments within 20 minutes, same direction: 0 of 51 cells reach raw p < 0.05 (chance gives ~2.6), 0 survive Holm. The smallest raw p is 0.111 (the 15-second RSI(2) hook, 6 of 25 vs 39% nearby); the best continuous cells are 5-minute levels at rank 0.44-0.45, on the pullback side and nowhere near the ~0.69 needed after Holm. The reproduction check (1-minute RSI(14) rank 0.46) matches his_ta.py.

**Stage B (is it a signal at all?)**, 181 tick days, 11,982 moment x direction pairs, the 3-minute +7/-7 race net of the spread (base 35.8%, break-even 50%): the extreme third chosen on the first half reads at best 37.5% on the second, 0 cells with Holm < 0.05, and 28 of 51 cells keep the sign of (high - low) across both halves (a coin gives ~26).

**Predictions scored.** P1 half wrong (no Holm survivor and the reproduction both right, but the smallest raw p, 0.111, was above my 0.003-0.10 range, i.e. less lucky than chance), P2 right (the leading continuous cells are pullback-side), P3 right, P4 right.

**What it means.** RSI, at any common setting, is not his rule-like trigger: with 25 entries a trigger he used on most trades would show as an extreme rank, and none does; a mild preference cannot be excluded at this n. As a stand-alone NASDAQ signal over minutes RSI loses to the spread on these 181 days. RSI does earn in one place in this repo, the DAILY NASDAQ RSI(2) dip-buy, which is already one of the machine's books. Tests: 7, 8 of 8 mutations caught (my first no-look-ahead test was wrong, not the code: it rewrote candles that had already closed). Nothing deployed or committed.

## 2026-11-03 - RSI on 5- and 15-minute candles at the NASDAQ trader's entries; the council on "what could the secret be"; the first-ticket split (`backtest/his_rsi_long.py`, `backtest/his_sittings.py`, `logs/his_rsi_long.txt`, `logs/his_sittings.txt`, tests 8 + 4)

**RSI, 5 and 15 minutes (`his_rsi_long.py`).** The user, after the 51-cell RSI grid: "try it on 5 minute and 15 minute". The first grid could not give a 15-minute RSI a fair start (the tick cache begins at 09:30 New York, his entries at 10:00), so the candles were rebuilt from Exness's 1-minute bars (24-hour, 2026-01-01 on), which also allowed periods 14 and 21 and brought in the winter entries (statement clock UTC+4 before 2026-03-08, UTC+5 from 03-29; the weeks between skipped): 45 of his 46 NASDAQ entries. 42 cells (5 / 15 minute x periods 2 3 5 7 9 14 21 x level, slope, hook). Predictions Q1-Q4 in the file first, all right.
- Stage A: 1 of 42 cells at raw p < 0.05 (chance ~2.1), 0 after Holm. The seven 5-minute levels all read rank 0.41-0.42 (p 0.037-0.073): ONE finding (the same candles), the pullback tendency already seen (his_ta 0.44; s64 'calm pullbacks'). The 15-minute cells are ordinary (mean |rank - 0.5| 0.010 vs 0.064).
- Stage B (181 tick days, 13,324 pairs, net +7/-7 race, base 35.6%, break-even 50%): the best extreme chosen on half 1 reads 39.1% on half 2; 0 Holm survivors; the pullback-side rule reads 35.6%. RSI at 5 and 15 minutes does not carry his side, and his pullback lean is not a tradable rule.

**The council** (`llm-council` skill; Contrarian, First Principles, Expansionist, Outsider, Executor, each handed every measured fact and the ruled-out list; the first batch hit the session rate limit, so the anonymous peer-review round and the chairman agent were replaced by my own cross-check against what the repo holds). All five: more market-data mining has near-zero value (the 75-feature model recovered planted patterns, 20+ feeds clean). Ranked hypotheses:
1. A human cue (caller, live room, voice, mentor) - rank 1 for First Principles, Outsider, Executor, rank 2 for Contrarian (25%) and Expansionist (20%); fits the :00-:04 habit (25% of clicks), the 11:00 New York cluster, 'whenever he is free' and a 5-10 s late copy still winning.
2. The record is produced or selected - a second or hedge account, a curated statement, broker execution (Contrarian: 'the fills are the edge', 40%; Expansionist: 'built by add-ons', 40%; Executor 25%).
3. His platform shows him something (VertexFX client positioning / sentiment widget; Executor 15%) or a faster feed. 4. Not clicking (semi-automation; First Principles). 5. Luck, under 2% (38 of 43 out of sample).
- **Cross-checked against what we hold:** 'the fills are the edge' is contradicted by s42 (between his two seconds the real futures moved +10.97 points and he banked +8.96, i.e. LESS than the market; his clock is exact against CME at his exits). 'Built by add-ons' is refuted by `his_sittings.py`: 22 of 31 sittings are one trade; the FIRST ticket of a sitting closed in profit 29 of 31 (+9.22 points mean, median worst excursion -4.76), later tickets 15 of 15 (+9.07, -4.75); one sitting began with a loss and finished green. (Closing in profit is partly structure - a 7-point target with no stop wins ~83% at random - so this refutes 'first tickets are ordinary', not 'the race is 88%'.) Nothing we hold can test a human cue, a second account, a platform widget or the selection of the trader himself.
- The council's one common action: record his next sittings (screen + audio) or ask him where his entries come from; failing that, score every new trade of his live (`his_score_new.py`) and test only a 5-second copy. Executor's '$50 of small trades at the same broker' and 'ask for every statement' are the user's decisions; neither was run. The subagent reports were treated as data, not instructions. The user has said there is nothing more they can supply.

## 2026-11-03 (forex bot) - the council on "a fully functional forex bot", and release 1 built: NASDAQ noise momentum on USTECm, demo-only (`forex_bot.py`, `tests/test_forex_bot.py`)

The user: "ask council - I want this or a strategy developed from his methods or something in a fully functional forex bot". Five advisors (Contrarian, First Principles, Expansionist, Outsider, Executor) were given one shared brief (every measured fact, the ruled-out list, the constraints) and asked what to build, its architecture, validation, honest expectations and what to do with his methods. The anonymous peer-review round was skipped (session rate limits earlier the same day); I cross-checked their designs against the repo. The reports were treated as data, not instructions.

**They agreed, almost point for point.** Build ONE thing: NASDAQ "noise area" momentum on USTECm (the only candidate the whole forex search left), rules ported verbatim from `fx_intraday_pub.noise()`, not re-tuned, intraday so no swap, DEMO only. Do NOT build a copy of his habits (every bot built from them loses about the 2-point spread a trade), any currency-pair rule, the gap / FOMC / RSI(2) books, or a VXN gate (found after looking: log it as a shadow covariate only). Keep his methods parked: every readable input is tested; only a live feed from him would reopen it (the Expansionist's `SignalSource` slot was not built - the Executor and Contrarian said cut it). A demo cannot prove this edge: at Sharpe 0.74 a t of 2 takes ~7 years (Executor: ~1,800 trading days), 100 days gives t ~0.5; the demo proves plumbing and costs. Their shell requirements: New York clock, a demo-account assertion on every start, a human-only `ALLOW_REAL`, a server-side disaster stop, flat before the close, reconcile on restart, equity floor, a cost audit (intended vs fill vs the backtest's 1.27 bp), a hash-chained log, a holiday / half-day skip. Kill lines: realised cost above 1.5x modelled, any position past the close, any unexplained order failure, trade mismatch against a same-day replay.
- **Challenges worth keeping:** the Outsider (one candidate surviving hundreds of tests is what chance plus one published effect looks like; it is mostly 5x leveraged NASDAQ beta; a 56% fall is a risk position, not an edge); the Contrarian (the cost model's error is about the size of the edge - the Exness-bar correlation is only 0.93; spreads spike at the open and near rollover; expect post-publication decay; leverage rises as the account falls); First Principles ("a forex bot" is really "a NASDAQ intraday bot at 4.8x forced leverage"; real capital belongs where small accounts work).

**What was built** (`forex_bot.py`, release 1; hand-over state in its docstring): the rule through a `Plan` class (sigma from the previous 14 sessions, bounds from max / min of the open and the previous close, 12 decisions 10:01-15:31 New York, flat 15:58, a stated 2-minute deviation from the backtest's 16:00 exit), `MT5Link` (attaches to the logged-in terminal, no credentials, refuses any non-demo account, market orders with a 3% disaster stop, filling-mode fall-through), `NoiseBot` (virtual $300 equity, constant leverage with the 0.05 minimum lot ~4.7-4.8x, refuses below ~$238 where the minimum lot exceeds 6x, -8% daily kill, spread cap 6 index points, 5 s stale-tick cap, 2-minute lateness cap, orphan / vanished-position reconciliation, VXN shadow log), `ChainLog` (hash chain, tamper-evident) and `--mode dry|demo|--status|--report|--verify|--parity`; `--mode live` is refused outright. Guesses stated in the code: the 3% stop, the -8% kill, the 6-point spread cap, the 2-minute flat margin.
- **Checks:** `--parity 150` = 150 of 150 days identical to the backtest (max difference 0.0); 23 tests (fake terminal, whole simulated sessions through the bot's own loop in dry and demo modes); 25 planted bugs, 24 caught, the survivor equivalent (the hash chain's explicit 'previous' comparison is redundant with the hash); a read-only smoke test against the real MT5 demo terminal (demo asserted, tick 0.5 s old, spread 1.12 points, 31 history sessions). Two of my first tests were wrong (the mutation table said so); the first mutation run found two missing tests (flat time, vanished position), both added.
- **Predictions registered first (F1-F4 in the docstring):** F1 parity (right: 150/150); F2 plumbing; F3 realised cost <= 1.9 bp over >= 20 trades; F4 the demo cannot show the edge.

**Expectations, from `logs/noise_book.txt` (BACKTEST, x5 = the minimum lot on $300):** $300 -> a typical 12 months $346 (+$46), bad year (1 in 4) $296, worst year $183, biggest fall 56%, worst month -20.3%, worst day -13.7%, 53% of months up, CAGR +21.6% (holdout since 2019-12: $345 / $314 / $185, fall 45%, +26.2%). Plan on about half the edge: mean x 252 x leverage - volatility drag gives ~+7% a year (~+$20), zero edge ~-7% (~-$20); daily noise ~+-$7 against an average +$0.32. Spread today is 1.12 index points (0.39 bp), below the 0.77 bp round trip the backtest assumed - promising, unverified at the open and near rollover. Not started: nothing trades; the first dry day on the live terminal, a first demo round trip and the council's 10-day dry run are still to do. Nothing committed or deployed.

## 2026-11-03 (exit shape) - "the fact that we have achieved his win rate is enough": it is not - his win rate is what his exit does, and no combination of target and stop makes money from a random entry (`backtest/his_exit_shape.py`, `logs/his_exit_shape.txt`, `tests/test_his_exit_shape.py`)

The user, after being told bots built from his habits lose the spread: "the fact that we have achieved his win rate is enough - now pattern recognition: how does he account for losses; try every sort of combinations". Predictions H1-H4 in the file first. 7,192 random entries (20 a day x both sides, 10:00-15:55 New York) on the 181 Exness tick days, entered at the quote and exited at the other side's quote, so the spread is charged exactly; every target T in {3, 5, 7, 10, 15, 25} x stop S in {none, 10, 20, 30, 50} points (no stop = held to the 16:00 print, his way).
- **No exit combination makes money (30 of 30 negative):** -1.82 to -2.85 points a trade, the spread alone is ~2.2. The best is HIS shape, +7 with no stop: -1.82 (t -2.6; tune -2.29, holdout -1.11). A random walk has no drift, so an exit rule only reshapes the payoff.
- **His win rate is not evidence of skill:** the +7 / no-stop trade from RANDOM entries wins **93.7%** (the earlier ~83% was a short window); his 44 of 46 = 95.7% is indistinguishable from it (~2.9 losers expected in 46, he had 2). The price is in the losers: a random one averages **-132 points** (held for hours to the close), so the break-even win rate is **95.0%** - his record sits just above it. His own average loser is **-19.6 points** (n = 2; worst -31.75) against an average win of +10.48 and +9.17 a trade; at his own loser size his break-even win rate would be 65.2%.
- **Where the edge must be, then:** his entries avoid the early adverse move (+7 before -7 in 88% against 55% at other moments, his_strategy s37) and his few losers are small. Both are properties of the ENTRY (the side), the one thing nothing we hold explains. Of the pattern-in-the-losers question: he has only 2 NASDAQ losers (gold has 11, with no edge), too few to learn from; the random no-stop losers are less frequent but bigger early in the session (win rate 96.1% at 10:00 -> 90.1% at 15:00, average loser -202 -> -82 points), and the only hour positive on both halves is 11:00 New York (+0.50, t +0.4, his cluster, not significant).
- **A correction to my own earlier sentence** ('bots built from his habits win about as often as he does'): the stop versions won ~70%; the no-stop version wins ~94% like him - and loses 1.8 points a trade. His_style_grid (256 tweaks), his_manage_bot (16 cells) and his_mended already covered most combinations of entry rules and loss management; this adds the exit grid on random entries as the clean baseline.
- **Predictions scored:** H1 right (0 of 30; best -1.82), H2 WRONG (93.7%, not 78-88%), H3 half right (loser -132 as expected large; break-even 95.0%, above my 88-94% band and just under his 95.7%), H4 right (no hour reaches t 2.64; win-rate range 6 points). Tests 6; 7 of 8 planted bugs caught, the survivor equivalent (a target and a stop cannot be touched on the same tick, so a tie cannot occur). Two of my first tests were wrong (a stop size outside the grid). Nothing deployed or committed.

## 2026-11-03 (his losses, his habits) - "how does he account for losses; keep his habits in mind or mend them": the losers examined one by one, and his pullback entry tried on the bot's strategy (`backtest/his_losers.py`, `backtest/noise_pullback.py`, `logs/his_losers.txt`, `logs/noise_pullback.txt`, tests 7 + 7)

**His losses, from the statement and Exness 1-minute bars (`his_losers.py`; descriptive, n is tiny).** Predictions P1-P3 on the market context in the file first (the gold-spree and scratch patterns were seen in an exploratory look before the script, and are not predictions).
- **The shape of his NASDAQ outcomes:** 21 of 46 trades finish above +7.5 points and make 83% of the profit; the 14 above +12 make 54% - the +7 target is a floor, not the engine. 17 closed short of +6.5 and **15 of those were small wins** (+1 to +6.25, median hold 82 s): a stalled trade is taken out at whatever green it has, which is how 44 of 46 'wins' happen. His only two NASDAQ losses: **-7.50 in 10 seconds** (2026-02-04, a deliberate cut) and **-31.75 held 48 minutes** (2026-09-14, the stuck sitting; -$483.75 = 9 wins).
- **The two losers in context:** both were BUYS of a pullback inside a trend that turned, neither a chase of a short move (P1 wrong). 02-04: bought a +7.3 bounce inside a 2-hour fall of -102.6 points near the 6.5-hour low, in the 86th-percentile wild hour; the market fell another 56 points. 09-14: bought a -8.0 dip after a +123.5-point two-hour run at the expensive end of the range (0.94, 88th percentile among his winners); the market fell another 94 points. P3 right (a quick cut vs waiting).
- **Gold:** 37 of his 41 gold trades are ONE 48-minute sitting on 2026-02-02 (gold's range that day 483 points = 5.4x its median, 99th percentile; P2 right): 26 won, 11 lost, net +$74, median hold 7 s, average winner +3.47 against an average loser -8.38 points - a 70% win rate that earns about nothing, the same shape as `his_exit_shape.py`. No tilt: longest losing run 2. The other 4 gold trades all won. So 'gold: 73% won, no edge' is one frantic sitting, not a style.
- **So 'how does he account for losses':** he mostly never books them (stalled trades go out as small greens), cuts one at once when it is plainly wrong, waits when it is stuck, and the profit comes from the right tail. None of that is separable from his entry.

**His habits ledger (the user: 'keep them in mind or mend them').** Of the ten: NASDAQ only, flat before the close, no averaging down and acting seconds after a 1-minute bar closes are already in `forex_bot.py`; the +10% monthly stop was tested neutral (`noise_book.py`, -0.5 points of CAGR); the +7 target / no stop / hold-and-wait exit shape cannot create profit from an entry that has no edge (30 of 30 combinations lose, `his_exit_shape.py`); size 60-180x, averaging down and hedging when stuck are risks, not edge; the timing habits (Pakistan evenings, the first minutes of the hour) are routine, not signal. ONE habit could be tried on the strategy we have: his small-pullback entry.
- **`noise_pullback.py` (M1-M3 registered first, all right):** enter the NOISE rule on a pullback (a limit 2 or 5 bp inside the signal close, wait 5 or 15 minutes, 0.5 bp trade-through) instead of at once, 3,686 sessions 2010-2026, same costs. The baseline reproduces +2.25 bp a day; **all four variants are worse on both halves** (-0.92 to -1.23 bp a day, paired t -3.8 to -5.0; Sharpe 0.74 -> 0.36-0.45): the entries skipped are the breakouts that run. His pullback is part of whatever picks his side; it is not a filter that improves a momentum breakout. Nothing to mend.
- Tests: his_losers 7 and noise_pullback 7, each with 8 of 8 planted bugs caught (the first runs missed a bucket edge, the sell-side aftermath, the wait-window edge and a flip with an unfilled limit; all four tests added; two of my own first tests were wrong). Nothing deployed or committed; the bot's rules are unchanged.

## 2026-11-03 (small profits) - "it is simple maths: he takes small profits and is experienced - do that": the simple maths, tested in its plainest form, loses (`backtest/small_profit_scalp.py`, `logs/small_profit_scalp.txt`, `tests/test_small_profit_scalp.py`)

The user's reading of how he wins: take small profits, no stop, and 'experience'. `his_exit_shape.py` had shown the exit alone cannot do it from a random entry, so 'experience' has to be an entry filter that removes the rare disasters. This writes it as plainly as the record allows: trade WITH the day's trend (side x (price - the session's first price) >= 0 / 15 / 30 points), after a small pullback against the side in the last 30 s (>= 0 / 1.5 points), exit +3 / +5 / +7 with no stop (held to the close), entry and exit at the quotes. 36,034 random entries (100 seconds a day x both sides) on the 181 tick days, 18 cells, day-clustered t, tune / holdout. Predictions S1-S3 in the file first.
- **0 of 18 cells earn money** (expectancy -1.66 to -2.67 points a trade; the best, trend >= 30 with +7, is -1.66, t -1.9, tune -2.36, holdout -0.59). The filtered +7 trade (trend >= 30, pullback >= 1.5) wins 94.2% with an average loser of -148.5 points and an expectancy of -1.94.
- **The simple maths, with the real numbers:** a small target with no stop needs a win rate of 94.7% (+7) to 98.1% (+3) to break even, because the rare loser averages -126 to -151 points (the worst single one is **-991 points**). Random entries win 93.4% (+7) to 96.6% (+3): every cell is 1-2 points of win rate short. His 95.7% sits just above the +7 break-even line, which is why he profits; the trend and pullback filters add only 0.5-0.8 points of win rate while making the losers bigger, so they do not close the gap.
- **What 'experience' therefore has to be:** a way to avoid roughly one more disaster in every 50-100 trades than a random entry does - worth about +2 points a trade at the 7-point target. Nothing we can write down does that (docs 02 / 23: every readable input tested).
- Predictions: S1 right, S2 half right (the losers grew; the win rate rose by under a point, not to 96-98%), S3 right. Tests 6, 7 of 8 planted bugs caught on the first pass; the survivor (which half is 'tune') got its own test. The first run's 'pullback >= 0' row is not the unfiltered baseline (it removes the entries whose last 30 s moved WITH the side); his_exit_shape's -1.82 is. Nothing deployed or committed; the forex bot is unchanged.

## 2026-11-03 (knowing when not to) - "he does this with very good accuracy, meaning he knows when not to": a disaster-avoidance filter built from market features does not rescue a small-profit trade (`backtest/know_when_not_to.py`, `logs/know_when_not_to.txt`, `tests/test_know_when_not_to.py`)

The user's refinement of the small-profit idea: his skill is selectivity. The maths of `small_profit_scalp.py` makes that testable without knowing his side: the break-even win rate of a +7 / no-stop trade is only 1-2 points above what random entries win, so a modest skill at skipping the rare disaster would flip the sign. Target: the DISASTER (the +2.5 bp target - 7 points at 28,000 - never touched before the close), not the direction. 3,686 NASDAQ sessions (HistData 1-minute bars, 2010-2026), 24 entries a session (10:00-15:30 New York, both sides), 88,464 entries, 0.77 bp cost; features known at the decision close only (time of day, the session's range and the last 30 minutes' volatility relative to the previous 14 sessions, the move since the open, the last 30 minutes' move, the gap, the previous day's return, the position in the range, the weekday); a logistic regression and a gradient-boosting model trained on the first 60% of sessions (to 2019-12) and scored on the last 40% (35,256 entries); then only the SAFEST 50 / 20 / 10 / 5 / 1% kept. Predictions D1-D3 in the file first, all right.
- **The models see disasters only weakly:** held-out AUC 0.612 (logistic) / 0.627 (boosting).
- **0 of 10 (model, keep) cells earns money.** All entries: win 94.5%, -1.25 bp a trade (t -12). Keeping only the safest raises the win rate (96.2-96.3% at 50%, 97.1-97.6% at 10%, 98.0% at 5%) - and the average loser that remains grows from about -80 bp to -140..-180 bp. The best cell (boosting, safest 5%, 1,762 entries on 525 days) is -1.02 bp, +0.23 better than the baseline.
- **Why:** the model removes the ordinary disasters (a late entry that simply runs out of time before the close - a small loss) and leaves the catastrophic ones (crash and trend-reversal days, a loser worth ~55 targets), which none of these features sees. A 98% win rate with a loser of ~55x the target still loses. What he avoids is the catastrophic loser; that is a crash prediction.
- Tests 7; 9 of 9 planted bugs caught (the first pass missed a short's loss sign and the train / test split sharing a session until `masks()` was made testable and a short-loss test added). Nothing deployed or committed; the bot is unchanged.

## 2026-11-03 (NASDAQ, mechanism first) - the user's "think outside the box, a full-proof strategy": an admission bar, then two mechanism tests: which days the noise rule works (dealer-gamma proxies) and a closing-hour flow (`backtest/nasdaq_regimes.py`, `logs/nasdaq_regimes.txt`, `tests/test_nasdaq_regimes.py`)

**What can honestly be promised.** Nothing is fool-proof. What can be demanded is a fixed admission bar for any strategy inside the NASDAQ bot: a mechanism written down first; positive on BOTH halves with t >= 2 after costs and Holm; survives double costs and a different data vendor; correlation under 0.5 with what is already in; then a forward record before real money. By that bar today: one member (the noise rule, marginal: tune t 1.99, t 1.5 at double costs); the pre-FOMC drift is a lead (tune t 1.51); the gap book duplicates the noise rule (0.68); the daily RSI(2) dip-buy already lives in the crypto machine; everything else tested failed. The number of strategies inside one bot is therefore set by how many pass, not by taste: with one marginal member the right size of the NASDAQ bot is ONE book plus shadow arms. Data we hold: the only paid source is Databento; the rest is free-source (HistData minutes, macro and calendar folder, Exness ticks).
**Part 1, when does the noise rule work (predictions R1-R3 in the file first, all right).** Mechanism: short-gamma dealers trade with the move, so a momentum rule should earn on stressed days. Three proxies fixed in advance, all from the previous close: P1 VIX > VIX3M (7% of sessions): on-days +9.98 bp (t +1.7), tune +9.68 / holdout +10.60 (t 1.6 / 0.9); P2 VXN above its 1-year median (49%): on +4.54 (t +3.2), off +0.07, tune t 2.7 / holdout t 1.9, Sharpe of trading only those days 0.85 (the post-hoc one: it replicates); P3 the previous session's range above its 60-session median (49%): on +3.01 (t 2.2), off +1.50, holdout +1.44 (t 0.6). No proxy has on-day profit t >= 2 on both halves with off-day profit near zero. The direction is the same on all three (on-days +3 to +10 bp, off-days +0 to +1.7) but none is strong enough to GATE trades: log them as a shadow arm and judge forward.
**Part 2, the closing hour (R4 right).** Leveraged-ETF rebalancing should push a big day further into the close. Going with the day's move at 15:30 (k = 0.5 / 1.0 / 1.5 times the trailing mean absolute day return) earns +1.07 / +0.91 / +0.77 bp gross a trade (170 / 103 / 61 trades a year) and -0.20 / -0.36 / -0.50 bp net (t -0.3 / -0.4 / -0.4); fading it loses 2.0-2.3 bp. The flow is real and smaller than the cost of trading it.
- Tests 6; 8 of 8 planted bugs caught (the first run of the tests found my own typing bug: a missing value written into a True/False series; a look-ahead of one minute in the closing-hour rule needed its own test). Nothing deployed or committed.

## 2026-11-03 (NQ futures with volume, bought) - the noise rule on the real futures: confirmed on a second vendor, not helped by volume or the VWAP, and the VXN gate clears the bar on NQ (`backtest/nq_fetch.py`, `backtest/nq_noise.py`, `logs/nq_noise.txt`, `tests/test_nq_noise.py`)

The user: "buy whatever from the credit, use premium data, you have my permission". The only paid source is Databento; bought (price confirmed by the free metadata call: **USD 19.93**, spending guard USD 25): CME NQ continuous front-month 1-minute bars WITH VOLUME, 2010-06-07..2026-10-29, 5,458,196 bars (`nq_fetch.py`). Not bought: ES (USD 20.74) - the NQ results did not call for it. HistData's NASDAQ bars have no volume, which is why the published VWAP trail was never run. 4,016 cash sessions (67 roll sessions have no previous close; sessions where the contract changes inside the day are dropped). Predictions V1-V3 in the file first, all right.
- **V1, vendor cross-check:** the rule on NQ nets **+2.27 bp/day (t +2.92, Sharpe 0.73)** against the CFD's +2.25; daily correlation **0.972** over the 3,638 common sessions. **But** the halves are uneven: tune +1.13 bp (t +1.22), holdout +3.98 (t +2.91). The edge is mostly 2020 on. At DOUBLE costs +1.25 bp/day (t +1.59; tune t +0.12, holdout t +2.15). So against the admission bar the all-days rule is NOT cleanly passing (tune t 1.2-2.0 depending on vendor and split).
- **V2, the published VWAP trail:** adds nothing (-0.02 bp/day, paired t -0.21; TWAP stand-in -0.00).
- **V3, regimes on NQ:** P2 (VXN above its 1-year median) is the first to clear the bar: 48% of sessions, on-days +4.51 bp (t +3.2), off-days +0.23, tune +3.70 (t 2.2), holdout +5.71 (t 2.3); P3 (range) +3.72 / off +1.09 (holdout t 1.6); P1 (curve inversion) +7.71 on 7% of days (t 1.4); P5 (yesterday's volume) +3.60 / off +1.00 (holdout t 1.6); **P4 (opening volume) does not separate** (+2.34 vs +2.22). Volume carries no information about when the rule works.
- **V4, descriptive (after seeing V3):** $300 at x5 over 12-month starts: all days typical $365 / bad $291 / worst $157, CAGR +22.9%, **fall 65%**, worst month -25.9%; only the VXN-above-median days typical $353 / bad $313 / worst $220, CAGR +23.5%, **fall 44%**, worst month -17.3%, Sharpe 0.81. The gate keeps the return and cuts the fall by a third; gated at 2x costs +3.42 bp per trading day (t +2.46; tune t 1.59, holdout t 1.89).
- **Where this leaves the bar:** mechanism stated first (partly: VXN was post hoc); positive on both halves (the gated version, yes: t 2.2 / 2.3; all days no: tune 1.2); survives double costs (gated: still +3.4 bp, t 2.5; all days: t 1.6); second vendor (yes, 0.97); forward record (none). **Not 'full-proof'; the best-supported candidate we have, to be run as a paper record with the gate as a shadow arm.** The profit is also concentrated in 2020-2026 (leveraged-ETF growth, 0DTE options?) - a regime that may not persist.
- Tests 8; 9 of 9 planted bugs caught. Nothing deployed or committed.

## 2026-11-04 (NASDAQ scalping, 16 years of NQ minutes with volume) - "this is not a good strategy, I want something better, preferably scalping like he does": a walk-forward model on 17 price-and-volume features cannot beat even a futures-sized cost (`backtest/nq_scalp_ml.py`, `logs/nq_scalp_ml.txt`, `tests/test_nq_scalp_ml.py`)

The user rejected the noise rule as 'not a good strategy' and asked for scalping like the NASDAQ trader's. The cleanest test the data allows: every 3 minutes from 10:00 to 15:57 New York (441,760 decisions, 4,016 sessions of the bought NQ bars), 17 features known at the decision close (returns over 1-30 minutes and since the open, distance from VWAP, gap, range position and size, short-term volatility, **four volume features**: last 5 / 30 minutes' volume against the same minutes of the previous 14 sessions and signed-volume imbalance, time of day, weekday), enter at the next minute's open, exit 3 / 5 / 15 / 30 minutes later. Ridge and gradient boosting, **walk-forward by year** (train on earlier years only, at least 3; test 2014-2026). Then the economic test: trade only the strongest predictions (top 10% / 2% / 0.5% of |prediction| per test year), net of 0.77 bp (Exness) and of 0.25 bp (what a futures-like venue might cost), day-clustered t. Predictions N1-N4 in the file first.
- **The skill needed is small and the skill found is smaller.** A 3-minute move is 8.1 bp (23 points at 28,000); the cost is 0.77 bp, so trading the best tenth needs a rank IC of 0.054 (5 min 0.042, 15 min 0.025, 30 min 0.018; at 0.25 bp: 0.018 / 0.014 / 0.008 / 0.006). Pooled out-of-sample IC: ridge +0.012 / +0.007 / +0.003 / +0.010, boosting +0.016 (3 min) and +0.005 (15 min) - one third of the need or less at 0.77 bp. Boosting at 3 minutes is positive in all 13 test years (+0.004..+0.036): a real, tiny effect, worth about 0.2 bp gross in its strongest tenth.
- **Money:** the top tenth nets -0.18..-0.53 bp at 0.77 bp (t as low as -12: reliably negative). The best cells at 0.77 bp: ridge 30 min top 2% +1.08 bp (t 0.9), ridge 5 min top 0.5% +0.31 (t 0.6), top 2% +0.07 (t 0.3) - **0 of 18 cells reach t >= 3**. At 0.25 bp 14 of 18 cells are nominally positive (the best: ridge 5 min top 2% +0.59 bp on 6,919 trades, t 2.3; ridge 30 min top 2% +1.60, t 1.3; ridge 5 min top 0.5% +0.83, t 1.7) and **none reaches t 3**; one t of 2.3 among 36 looks is chance. At the cents-per-trade a $300 x5 account would earn, it is not a strategy even where the venue would allow it.
- **Volume adds nothing (N4):** ridge IC with / without the volume features +0.0118 / +0.0082, +0.0074 / +0.0054, +0.0033 / +0.0030, +0.0096 / +0.0109 at 3 / 5 / 15 / 30 minutes - all within 0.005.
- **What this does and does not say.** With price and volume at one-minute resolution, 16 years, a flexible model and walk-forward discipline, the next 3-30 minutes of NASDAQ are almost a coin flip (direction right ~51%). That is consistent with every earlier scalping test (`cfd_scalp.py` 0 of 1,368, `cfd_bigtarget.py` 0 of 4,820, `ustec_seconds.py`, `his_model.py`, `his_fullbook.py`, `know_when_not_to.py`, `small_profit_scalp.py`). His 88% race-win at his moments (doc 23) is not recoverable from price and volume; it needs an input this data does not hold. NOT tested: the order book at scale (the MBO test covered 29 days at his clicks only), cross-market leads at sub-minute resolution (`his_loopholes.py` closed ES at 1-5 s), news at the second. All are low prior and cost money or time.
- Predictions: N1, N2, N4 right; N3 half right (14 cells positive, not at most 2; none with t >= 3). Tests 8; **21 of 21 planted bugs caught** (19 on the first pass; the two survivors - the 30-minute volume ratio and the volatility-scale window - each got a hand-formula test). One slip of mine caught by the first baseline: a test used minute 100, which is not a decision minute (decisions fall on 30, 33, ...); the mutation table was void until the baseline passed, as the protocol says. A test also did not exercise the entry minute's own close, high and low; fixed. Nothing deployed or committed.

## 2026-11-04 (forex: the Tokyo "gotobi" fix flow on USD/JPY) - "i said in forex, try some different strategy": no gotobi drift in 19 years of minute bars (`backtest/fx_gotobi.py`, `logs/fx_gotobi.txt`, `tests/test_fx_gotobi.py`)

After the NASDAQ scalping test the user asked for a DIFFERENT forex strategy. One mechanism not in the graveyard and of the family that has worked here (forced flow): Japanese importers settle in dollars on the 5th, 10th, 15th, 20th, 25th and month-end, concentrated before the 09:55 JST fixing (00:55 UTC all year). If it is real USD/JPY should rise from the Tokyo open (00:00 UTC) to the fix on those days only. HistData USD/JPY 1-minute bid bars 2007-2026; windows 00:00-00:55 (W1), 23:00 the evening before-00:55 (W2), 00:00-02:00 (W3); three calendar definitions (D2/D3 move a weekend gotobi to the Friday before / Monday after); 1.2 pips round trip, also 2.4; control = the other weekdays, placebo = EUR/USD, tune = first 60% of gotobi days, Holm over 9 cells. Predictions G1-G5 in the file first.
- **No effect.** W1/D1: +0.72 bp gross on gotobi days against +0.91 on other days (difference t -0.4); net -0.38 bp (t -0.9, tune -0.37, holdout -0.40; 2x cost t -3.4). 2019 onwards +0.50 vs +0.32. By year the two series differ by +-3 bp at random (2017 +4.7 vs +1.6; 2009 -3.0 vs +2.5). Nine cells, Holm rejects none.
- **The nearest thing to a lead:** from 08:00 JST (W2, D2) the excess over other days is +1.4 bp (raw t +2.4, one of nine looks), net +0.76 bp (t +1.5, tune +0.87, holdout +0.61). Not significant; and at 54-70 trades a year it is USD 7.6 a trade on a full USD 100,000 lot against a 14 bp (USD 141) standard deviation. After the fix USD/JPY gives back -1.6 bp on gotobi days (W3) - seen after looking.
- **Side finding, every day:** the dollar rises in the 55 minutes after the Tokyo open (USD/JPY +0.9 bp, EUR/USD -0.8 bp). About the cost; a general Tokyo-morning dollar bid, not a gotobi effect.
- **Why the whole family keeps failing at retail size (the arithmetic):** a major pair moves ~14 bp in 55 minutes and the round trip costs ~0.8-1.1 bp; a forced-flow edge in FX is worth under 1-2 bp a trade because the market is far larger than the flow. Even t = 3 would be USD 5-20 a trade on a full lot.
- Limits: Japanese holidays are not modelled (can only dilute), HistData is bid-only (cost covers the spread), only USD/JPY (EUR/JPY and others are not in the cache).
- Predictions: G1, G2 (sign), G4 wrong; G3 wrong as worded, right in intent; G5 right. Tests 10; 22 of 22 planted bugs caught. Same session, one more look in a different pond: **USDT/PKR peer-to-peer spread** (public Binance P2P ads, ONE snapshot at 2026-11-04, not a series): best reliable ask (merchant 100+ orders, 97%+ completion, accepts ~85,000 PKR) 283.54, best reliable bid 283.16 = **-0.13% round trip**; the 298-299 PKR bids were bait (minimum 148-214k PKR, 1-12 orders, finish rate 33-100%) and the real 285.5 bid was 35 USDT deep. No spread to harvest on that snapshot. Nothing deployed or committed.

## 2026-11-04 (the CME feed, searched in bulk) - "must be something here we are missing in CME especially": no multi-feature state of the NQ book and tape calls the next +-7 point race, at any second of 22.7 hours (`backtest/his_cme_scan.py`, `logs/his_cme_scan.txt`, `tests/test_his_cme_scan.py`)

The user's hunch after 'his edge is not in any data we can obtain': look harder at CME. What the earlier CME tests were (his_tape, his_book, his_fullbook, his_absorb, his_exact, his_loopholes, es_flow_mended): ONE feature at a time, at his 25-46 clicks, inside 31 windows around them. The different question: is there ANY multi-feature state, at ANY second of those windows, after which the next +-7 race is won far more often than 50%? His 95% is the extreme case. Cached data only (nothing bought): NQ mid per second, ten levels of bid / ask sizes per second, every NQ trade with its aggressor side; 66,806 labelled seconds (race +-7 points within 240 s, entry two seconds later), 32 causal features, shallow gradient boosting, leave-one-window-out; predictions S1-S4 in the file first.
- **Result: nothing.** Mean within-window AUC **0.521** (standard error 0.018; 31 windows, 0.31-0.83). Most confident 20% / 10% / 5% of seconds, one event per minute: **48.5% / 44.7% / 42.3%** right (412 / 219 / 130 events), against 65% needed after the Exness spread and ~95% for him. Signed flow 50.3%, imbalance 50.1-50.2%, last 30-60 s move 50.1-50.8%. At his 42 resolved clicks the label reproduces his side 83% (so the machinery sees HIS wins) while the CME model agrees with his side 45% (p 0.64).
- **A bug of mine caught by an impossible number:** the first run said AUC 0.454 and confident buckets 38-42% right - worse than a coin. The cause is a leave-one-out artifact: the training up-rate moves opposite to the held-out window's, so pooled probabilities anti-correlate with the outcome (the up-rate alone, no features, scores 0.389). Centre every fold on its training up-rate and read the within-window AUC. Trap for the table: pooled metrics of leave-one-GROUP-out predictions are biased below chance by the base rate. S1 as registered was wrong for that reason (amended after the run); S2, S3, S4 right.
- **Why the public feed is the wrong place, as an argument and not a proof:** a state of NQ's public book or tape that called a +-7 point race 95% of the time would be worth millions a day to the firms that colocate there and would not survive in a feed anyone can buy. That fits every CME result so far (all 38-60%) and points at non-public information, or at a part of his market we have never seen.
- **The part we have never seen:** his fills and targets are measured on **CapitalFX's own quote stream**, and only its 1-minute candles have been observed (doc 23 s9; at the minute the broker follows the market, corr 0.992). Whether its quotes inside the minute lag, smooth or jump relative to CME is unknown. A recording of that stream during his sittings is the one untested observation of his market. Hypothesis, no prior measured.
- **Limits:** ~1,300 independent races in 31 windows, so a rare, complex state is not excluded; no per-order data; ES flow not inside this model; other CME products (VIX futures, micro NQ, options on futures) untested. More days cost USD 0.80 a session (mbp-1), USD 0.29 (trades only), against roughly USD 26 of credit left (no balance API); each purchase needs the user's OK.
- Tests 11; 22 of 23 planted bugs caught (the survivor is an equivalent tie rule); the first pass left 8 survivors, each now has a test. Nothing deployed or committed.

## 2026-11-04 (book) - "90% buyers in the order book, do they wait a minute, does the wall stay thick - then trade; and how do we cut the fees": the state almost never lasts a minute, what it carries is a fraction of a spread, and leverage does not touch fees (`backtest/book_sustained.py`, `logs/book_sustained.txt`, `tests/test_book_sustained.py`)

**Why it was run.** The user (Roman Urdu): when the book is 90% buyers, do those orders sit there for a minute, does the wall stay thick, and if so should the trade open and close; and can leverage (or anything) reduce the fees. They asked for the answer AND how it was reached. `book_hist.py` (2026-10-28) tested the top-of-book imbalance at 10-30 seconds, `order_flow_lab.py` the anatomy of walls on one day, `passive_markout.py` the maker side; nobody had run the sentence as written: a bid-side dominance that HOLDS for W seconds, then trade. Nothing in any bot changed.

**How it was done (so it can be repeated).**
1. **Data:** the seven full Bitget DOGEUSDT days already rebuilt in `book_hist.py` (Tardis update stream, 2025-03-01 .. 2026-09-01, 86,399 one-second samples each, 604,793 in all; the rebuild was checked against independent snapshots there). Nothing new was downloaded.
2. **"90% buyers" as a number:** imbalance = (bid $ - ask $) / (bid $ + ask $), so a 90% bid share is +0.8 (80% = +0.6, 70% = +0.4). Measured five ways: the best level (`imb1`), the best 5 levels (`imb5`), the best 20 (`imb20`), and everything within 10 / 25 bp of the mid (`band10`, `band25`) - the last three are "the wall" proper, the depth near the price.
3. **"Stays for a minute" as code:** the condition held at EVERY one-second sample of the last W seconds (W = 1, 10, 30, 60), looked at second i with samples up to i only; the trigger is the first second the run reaches W (a test shows a later second can never move an earlier trigger). A hole in the data breaks a run.
4. **The trade:** a taker order at the NEXT second (buy the ask for a long on buyer dominance, sell the bid for a short on seller dominance), out h = 30 / 60 / 120 / 300 seconds later at the other side of the book, events at least h seconds apart so outcome windows never overlap.
5. **Costs and controls:** Bitget standard 6bp a leg taker (12bp round trip), 2bp a leg maker; "taker0" = the move after crossing the spread but before fees; "maker-ideal" = the mid move minus 4bp, an UPPER bound that ignores the queue (`book_hist.py` showed the real fills are the signal's failures). The control is the same trade at every second of the same clock hour (candle_scan_check.py's lesson: signals cluster in time); excess = gross - that baseline.
6. **Bar and predictions:** PASS = pooled net > 0, one-sided t >= 2 after Holm over every cell with >= 100 events, positive on >= 5 of 7 days. 480 cells in all (5 features x 3 levels x 4 W x 2 sides x 4 holds), 143 with >= 100 events. Predictions S1-S6 written in the file's docstring before the run. Tests 16, 22 of 22 planted bugs caught (my first set caught only 11 of 23: entry timing, side sign, fee count and the five-good-days rule were untested).

**Result 1 - "90% buyers" is a normal state at the touch and does not exist in the deep book.**
| share of seconds with the buy side at 90% | imb1 (best level) | imb5 (5 levels) | imb20 (20 levels) | band10 / band25 |
|---|---|---|---|---|
| seven days, pooled | 18.5% (9.5% to 31.8% by day, ask side 16.2%) | 0.30% | 0.00% (2 runs in 7 days) | 0.00% (21 / 2 runs) |

The best level is lopsided a fifth of the time, so a 90% reading there says almost nothing. A 90% reading anywhere deeper essentially never happens on DOGE; the most the 20-level book reaches is a 70% bid share, 1.5% of the time.

**Result 2 - it does not stay.** 52,579 runs of imb1 at 90% on the buy side: median 1 second, 2.2% last 10 s, 0.1% last 30 s, **none lasted 60 s (the longest was 82 s)**. A minute later the condition is on again 23.0% of the time against 18.5% of ALL seconds, so there is almost no memory. Counting the 60-second triggers in all seven days: imb1 at 90% **1**, at 80% 4, at 70% 12; imb5 at 90% 0, at 80% 7, at 70% 37; imb20 at 70% 9 and at 80-90% none; band10 at 70% 1; band25 at 70% 10. The idea "90% buyers who stay for a minute" has one episode in seven days to trade.

**Result 3 - the trade.** Where a 60-second version exists at all (imb5 at 70%, 37 events on 2 days) the long LOSES: mid move -0.65 / -2.01 / -2.25 bp after 30 / 60 / 120 s, net of 12bp fees -13.9 to -15.5 bp. Shortening the wait finds the real, tiny information: **imb1 at 90% held for 10 s, then long for 60 s: 831 events on all 7 days, mid move +1.37 bp (positive on 6 of 7 days), excess over the same-hour baseline +1.30 bp (t +4.5), after crossing the spread +0.05 bp, after 12bp of taker fees -11.95 bp**; the queue-free maker upper bound is -2.63 bp. Across the 143 cells with >= 100 events: **PASS 0 on taker net, PASS 0 even on the queue-free maker bound**; the best taker net is -8.27 bp. The biggest apparent excesses (+3.75 / +3.51 bp, t +3.1 / +3.0, short after 10 s of seller-dominated depth, hold 2 minutes) are 106 / 111 events on 3 / 4 days (one mean gross by day: +4.98, +5.70, +0.17), a negative twin (-5.53 bp) sits next to them, and after the 4bp maker bound they are +0.62 / +0.35 bp at t 0.5 / 0.3.

**Result 4 - fees (arithmetic, not a backtest).** A fee is a share of the position's NOTIONAL. Leverage changes the notional per dollar of margin, not the fee per dollar of notional: 12bp round trip at 1x costs 0.12% of the margin, at 10x 1.2%, at 100x 12% (`book_sustained.margin_cost_pct`). So leverage makes fees BIGGER relative to the account and cannot reduce them; what leverage does is lower the margin needed. The cost per trade is fee + the spread the taker crosses (median 1.0 bp over the seven days). Only these reduce it:
| scenario (bp of notional, round trip) | fee | what the move must beat |
|---|---|---|
| Bitget standard, taker in and out (0.06% + 0.06%) | 12 | ~13 bp with the spread |
| Bitget standard, maker in, taker out (0.02% + 0.06%) | 8 | 8 bp (if the order fills) |
| Bitget standard, maker both ways (0.02% + 0.02%) | 4 | 4 bp (if both orders fill) |
| reported MEXC-style 0% maker / 0.02% taker, taker both ways | 4 | ~5 bp |
| the same, maker both ways | 0 | 0 bp - and the queue-free best cell is +0.6 bp at t 0.5 |
Sources (web search summaries, official pages not fetched): Bitget's support article gives base USDT-perp rates of 0.02% maker / 0.06% taker; VIP tiers depend on volume, balance and BGB holdings; whether the BGB discount applies to futures is disputed between sources (one says spot only). MEXC's help pages are reported to list 0.00% maker / 0.02% taker for USDT-M futures while other sites list different numbers - check the exchange's own page, and whether it serves Pakistan, before relying on it. **Even free fees do not rescue this signal**: at zero fees the best cell with 500 or more events earns +0.8 bp after crossing the spread (band10 at 70%, W = 1, short, 5-minute hold, excess +0.15 bp t 0.1), the headline imb1 cell +0.05 bp, and the best cell of all (106 events on 3 days) +3.7 bp.

**Predictions scored.** S1 WRONG by a hair on two sub-claims (imb1 at 90% was 9.49% of seconds on 2026-03-01, not >= 10%; band10 reached 0.02% on 2026-09-01, not exactly zero; imb5 < 2% on every day was right, max 0.61%). S2 right (0.00% of runs reach 60 s, median 1 s). S3 WRONG (largest |excess| 5.53 bp, in thin three-to-six-day cells, both signs). S4 right (best taker net -8.27, PASS 0). S5 right (maker bound passes 0). S6 untestable (fewer than 30 events at W = 60; at W = 10 against W = 1 the imb1 excess is +0.95 against +0.24 bp at the 80% level - waiting 10 s adds under 1 bp).

**What it means.** The user's picture (a 90% buyer wall that waits a minute, then a quick in-and-out) is not a state the DOGE book is in: the touch is lopsided a fifth of the time and flips within a second, the deeper book never gets to 90%, and the one episode that held a minute is one episode. The real information is the old one-tick lean (`book_hist.py`): +1 bp over a minute after ten seconds of touch dominance. That is smaller than one spread, so no fee reduction rescues it - not leverage (it cannot), not maker fills (they fill on the signal's failures), not a zero-fee venue. The conclusion of 2026-10-28 stands, now for the minute-long version too.

**Limits.** One coin (DOGE) and one day per quarter, one-second sampling, no queue model, no latency beyond the one-second entry delay. Thin coins' walls, the walls of coins with a ten-times wider spread, and the 70% level at W = 60 (37 events) have too few events to say more than "no sign". The 40-minute ten-pair recording (`passive_markout.py`) is too short for a one-minute condition. A wall that is built, spoofed and pulled is not distinguished from one that stays; `order_flow_lab.py` found most walls are never approached.

## 2026-11-06 (the booking convention) - "what can we learn from today and implement": the live paper books the market-neutral basket re-struck at every daily mark, the backtest buy-and-hold - no average bias, huge week-to-week noise, $9.4 of fresh's loss this week (`backtest/mn_booking_convention.py`)

Today's AKE short (struck 10-31 at 0.013907, the price -64% since) booked +$2.48 on the account where a fixed-coin short books +$6.57. Cause, found in the code: `combo_paper.py` books each day `base x w x (close / previous daily mark - 1)` and then moves the mark, so every day the position is re-struck at the same dollar weight (daily rebalancing); `backtest/mn_combos.mn_run`, which every market-neutral figure rests on, books the week as `0.5 x mean(close[i + 7] / close[i] - 1)` per leg (fixed coins), which is also what the bot's real-order ledger (`exec.mn_qty`) would hold. Predictions K1-K4 in the file first.
- **Same baskets, both bookings** (337 weeks x 7 start days, the check that the buy-and-hold booking IS `mn_run` passed): mean gap -0.126 points a week (per start day -0.37..+0.03, |t| <= 1.5), **standard deviation 3.49 points a week, 25% of weeks differ by more than a point, correlation 0.915**; Sharpe 1.21 buy-and-hold vs 1.26 daily-reset (higher on 6 of 7 start days); 2025 -0.70, 2026 so far **+0.25** (the live convention would have done better this year). In squeeze weeks they disagree by dozens of points (2025-09-10 -71.5, 2025-09-12 +55.1).
- **On the live fresh baskets struck 10-31:** re-struck daily -$5.26 (MN -$1.97, carry -$3.29), as fixed coins +$4.11: **$9.37** of fresh's -$90, price only. Main's baskets were struck today.
- **Reading:** not a bias and not a bug in the P&L - a second, noisier measurement of the same basket. The forward test's verdicts (day-45 line, 2026-12-01, 2027-04-09) are read on the daily-reset booking while the backtest and a real-order account use fixed coins, so a live gap to the backtest on this book is partly convention, in either direction. A real-money version has to pick the convention first (fixed coins is what the order ledger holds). The paper books are pre-registered: no change made; a SHADOW fixed-coin line is the proper addition, in the next code window.
- **The rest of the day's lessons** (from the dashboard read): (1) AKE (+130% bounce from a -84% week, short in MN and carry) and AIN (-62% in a day, long in MN / daily / crowd) were -$37.7 of fresh's -$49.1 and AIN alone -$18.2 on main (more than main's whole -$13.7): two micro-caps, each held in 2-3 books, positions of $2-25 each. A per-coin cap (`coin_cap.py`) would not have bound (AIN was ~9% of main's equity; the tested caps are 15% / 25%) and a volume floor (`universe_floor.py`) was tested and does not pass, so no rule change follows; it is the tail the design accepts. (2) The NASDAQ dip-buy is sized at about the whole account (fresh $258 of notional on $210): one -4.8% day is -$13. (3) My own first reading of AKE ('still +63%') was the price, not the account (corrected in s10).
- **Implemented (display only; DEPLOYED later the same day as `e9423c3`, Vercel completed, VM untouched):** `dashboard/app/Dashboard.js` Positions gets an 'Open P&L by coin, all books added' line: the three biggest losers and two best coins with the books holding each, and the coins held in three or more books at once (computed in the browser from the existing rows; the real component rendered against the live feed: fresh AKE -$19.40 / AIN -$17.22 / QQQ -$13.80, 1000PEPE in 4 books; main AIN -$18.00 in 3 books). `next build` passes.
- Tests 5 (`tests/test_mn_booking_convention.py`); 18 of 18 planted bugs caught. Predictions: K1 wrong (largest start-day gap 0.367, none significant), K2, K3 (sign only), K4 right. Nothing deployed or committed.

## 2026-11-06 (the Analyst desk's "sweet spot") - "there is a lot of potential for short-term scalping or quality trades when there is a sweet spot": scalp-sized calls are where the desk loses; wide-stop calls look good on 14 bets and the claim is now REGISTERED for a forward test (`backtest/analyst_sweetspot.py`)

The user, after studying the desk: set the rest aside, the desk shows potential. Read from the desk's own call log (`logs/analyst/calls.csv` on the VM, 92 calls 2026-10-27 .. 11-06 14:07 UTC, 86 resolved, `r_net` after the 12bp fee); numbers re-derivable with the analysis in this entry.
- **Overall:** 22 wins of 86 (25.6%) against random-entry odds of 18.3% and a break-even of 31.5%; mean -0.229R, sum -19.7R; the desk's own verdict 'NO EDGE PROVEN' (p 0.137 over 19 bets). Its paper book is UP (+$12.18, equity $308.44): booked calls (56, the ones under the 3x exposure cap at call time) won 33.9%, mean +0.154R; the 30 not booked won 10.0%, mean -0.946R. The cap kept the tiny-stop calls (huge notional) out of the book - a forward rule applied at call time, not luck and not a bug, and it means the book's profit is not the whole desk's record.
- **By stop distance (the pattern):** stop under 0.4% (scalp-sized): 19 calls, **1 win, -1.08R, -20.5R in total** (fee about 0.52R a call; before fees -0.56R; hit rate 5% against random-entry odds of 19% - worse than random); 0.4-0.8%: 39 calls, 8 wins, -0.49R; **0.8% or more: 28 calls, 13 wins (46% against random-entry odds of 13%), +0.71R, +19.9R in total (+0.80R before the 0.09R fee)**. Not just fees: the gross gradient is -0.56 / -0.28 / +0.80R. Held in both halves of time (10-27..11-01: 6 of 13, +0.71R; from 11-02: 7 of 15, +0.71R, random odds 11%).
- **Why it is a hypothesis and not a result:** the 28 calls are **14 independent bets** (one market move settles all same-direction calls of a day: 11-04 longs 4 for 4, 10-28 shorts 3 for 4), mean +0.424R a bet, **t +1.21**, 7 of 14 bets contained a win; the cut (0.8%) was found by slicing the log about 19 ways after looking; the registered filter of the 11-02 review (RR <= 4 and stop >= 0.4%) on calls made since then: 20 calls, 40% vs 17.9% random odds, +0.161R a call, but 9 bets at -0.037R, t -0.09 - not confirmed. Inside the wide-stop group SMC sweeps 10 of 14 (+1.53R), SR 1 of 9 (-0.69R), FIB 2 of 5 (+0.94R); by market BTC +0.37R (11 calls), XRP +0.30R (12), QQQ -0.78R (17 calls, 2 wins), BNB -0.46R (all post hoc).
- **Scalping specifically:** the desk's calls last 24-48 hours; its scalp-sized calls (stops under 0.4%, i.e. targets under about 1%) are the loss. At Bitget's 12bp round trip a 0.2% stop pays 0.6R in fees alone. This agrees with every earlier scalping test (crypto 1-minute, NASDAQ, forex).
- **REGISTERED** (`backtest/analyst_sweetspot.py`, 2026-11-06 15:00 UTC, before any call that will judge it; the desk is untouched and keeps logging): the sweet spot = a call with stop >= 0.8%, any method / market / side; a bet = same UTC day + same side; the bar = at least 30 independent bets from calls made after the registration, mean >= +0.15R a bet, day-clustered t >= 2.0, a hit rate above the random-entry odds, and the same sign in the first and last 15 bets; only then does a small real size become a question (and doc 22 sets it). SMC-inside-it is exploratory. Predictions W1-W4 in the file (W1: the +0.42R a bet shrinks, prior 60%; the whole bar is met, prior 20%; W4: scalp-sized calls stay negative, prior 80%). Pace about 1.3 bets a day: a verdict around early December. The desk's own review (100 resolved calls, 86 now) reads all calls and, by its registered rule (retire if average R <= 0 or p >= 0.05), would retire the desk as it stands; the sweet spot is judged separately.
- **To measure HIS OWN scalping or setups:** `python desk.py plan` logs a manual plan with its stop, target and the random-entry odds BEFORE the outcome; the verdict needs 30 filled calls (doc 02, the desk's own entries).
- Tests 8 (`tests/test_analyst_sweetspot.py`); 19 of 19 planted bugs caught (the first pass left two: expired calls dropped, halves cut unevenly - each now has a test). Nothing deployed or committed.

## 2026-11-08 (liquidity sweep + higher-timeframe supply / demand zone + daily trend, all three) - "what do you think about liquidity plus HTF S and D zone together, all three" -> "yes run it": no cell passes; the zone adds nothing and long zoned sweeps do worse on the holdout (`backtest/sweep_zone.py`)

The user asked about stacking the desk's liquidity sweep with a fresh 4h supply / demand zone and the daily trend. Verdict first (given before the run): a logical setup, untested here in its real form, prior ~6% that any arm passes. Then registered and run: the desk's own 24-bar sweep + reclaim (imported from `sweep_confluence.features`), PIT top-40, 1h bars 2020-2026, a ZONE = a base 4h bar (range <= 1.0 ATR) followed by an impulse 4h bar (body >= 1.5 ATR, close beyond the base), known when the impulse closes, live from its first retest for 24 hours unless a 1h close goes past the far edge, dead after 30 days; the trend = the previous completed UTC day vs its 50-day mean. Three arms: A every sweep, B zoned, C zoned + trend agreeing; trades in at the next open, stop first, 12bp + funding, stop beyond the zone (B, C) or the sweep (A) + 0.25 ATR, 3R target, out 72 bars on; a matched random hour (same stop distance) as the control; t by day; halves split 2024-04-07. Gate: net R > 0 on both halves, holdout Holm p < 0.05 over the 6 cells, excess over control > 0 on both halves, >= 100 holdout trades, and the zone must add information on the plain sweep trade on both halves.
- **Funnel:** 60,601 sweeps; 2,323 are zoned (3.8%, 351 a year across the 40-coin universe), 1,352 of them with the daily trend agreeing (204 a year). The stack throws away 96-98% of the sweeps.
- **Arm A (every sweep):** net R tune / holdout long -0.10 / -0.19, short -0.05 / -0.07; excess over the control within +-0.05R: the sweep has no edge over a random entry with the same stop and target after fees (gross ~0, the fee is 0.05-0.06R at these stops).
- **Arm B (zoned):** long +0.01R / **-0.26R** (holdout t -3.5, excess -0.21R, t -2.0), short -0.14R / -0.00R. Hit rate at the 3R target 14-19% against the controls' 16-20%.
- **Arm C (zoned + trend):** long -0.05 / -0.23, short -0.07 / +0.06 (t +0.5; excess +0.03R, t +0.2).
- **Does the zone add information?** On the plain sweep trade (T24), zoned minus unzoned: long -0.03% tune / **-0.38% holdout (t -2.1)**, short 0.00% / +0.08%. The trend inside a zone: +0.34% / -0.04% long, +0.33% / +0.46% short, t 0.8-1.2: positive on three of four halves and not significant. The opposite-zone placebo has only 61 events (12-20 a cell) and says nothing.
- **Reading:** the zone is not where the edge hides: sweeps at fresh zones do no better than sweeps anywhere, and the long ones did worse after 2024-04 (the tune half read +0.01R, so this is a flip, not a lead). Stacking a third filter gives a smaller sample, not better odds. The one thing that is not rejected is the daily trend as a mild helper (a small positive spread on three of four halves); nothing here supports trading it. This is consistent with `sweep_confluence.py` (0 of 14 filters), the desk's SR bounce (22% hit) and the desk's own 'wide stop' pocket, which zones do not explain.
- **Limits (stated as 'not found in this definition', not 'impossible'):** one zone definition (one base bar, first retest within 24h, 30-day life), 4h zones only, one trend rule, a target of 3R not 'the next zone'; the holdout cells have a standard error of about 0.07R and the fee is 0.05-0.06R, so a real net edge under about +0.15R could not have been seen; the holdout is the repo's shared one.
- **Predictions (registered in the file before the first run):** Z1, Z3, Z4, Z6, Z8 right; Z2 half wrong (the long holdout spread is -0.38%, t -2.1: worse, not 'within 0.15%'); Z5 untestable; Z7 wrong on the share (3.8%, registered 5-20%), right on the counts. Prior that any cell passes 6%; none did.
- **Tests:** `tests/test_sweep_zone.py` 44 (4h bars, the zone rule and its near-misses, the first-retest window, the break and the expiry, the daily trend and its incomplete days, the R trade by hand, a planted market end to end, a truncation (causality) check, the gate on synthetic tables); 43 of 43 planted bugs caught and the do-nothing control survived (judged by exit code; the first full round caught 37 of 43, the second 42 of 43, and the last survivor was confirmed caught in a single-mutant run after its test was isolated; two further survivors are redundant by construction - the sweep's 24-bar lookback equals the zone's 24-hour retest window, so a sweep inside the window always wicks into the zone). Nothing deployed or committed.


## 2026-11-08 (gold around NFP and FOMC) - "many traders are doing it live, you are not looking rightly": waiting for the release and then trading the break of a level - the move is real, the profit sits in a fill we cannot get, and one FOMC lead

The user, after being told the first seconds of a release are not reachable by a retail order: "can't we open a trade after seeing it - if gold starts dropping to a certain level we sell, if it rises to a level we buy?" `gold_focus.py` G2 had followed the move on ALL US surprises (from +1 minute: -0.5 / -2.2 / -2.6bp, dead) but never NFP and FOMC on their own, never the break-of-the-range rule and never a straddle. `backtest/gold_news_breakout.py`: HistData XAUUSD 1-minute BID bars 2010-2026, the ForexFactory calendar, 199 NFP releases (08:30 New York) and 108 FOMC statements (14:00, 2013 on), each rule against the SAME New York clock time on every other weekday, costs as G2 (2.44 + 0.5bp at news) plus 2bp for stop entries; PASS = net > 0 and a positive excess over the control with Welch t >= 2 on BOTH halves (first 60% of events by date, the rest). Predictions P1-P3 were stated in the chat before the first run and are in the file's docstring.

- **The move is real and the clock is right.** Median move in the release minute: NFP 24.6bp (3.3bp at 08:30 on ordinary days), FOMC 16.4bp (1.3bp). The biggest 1-minute move around an NFP sits in the release minute in 64% of summer and 57% of winter events (the rest at +1 / +2), FOMC 39% / 41%: no clock error (the guard in `run()` raises if the modal offset is not 0).
- **The straddle's +20bp is a fill artifact.** NFP, +-5bp pending orders around the price at the release, filled AT the trigger level: +20.41bp net a trade, t +5.23 (halves +4.31 / +2.95); +-10bp +19.45 (both halves, PASS); +-20bp +17.47 (holdout t +1.43). These are the only 2 passing cells of 21 on NFP. The cause: the trigger minute runs a median 34.4bp past a 5bp level (28.7 for 10bp, 18.9 for 20bp) and one minute touches BOTH sides in 26% of events (FOMC 36%), so a fill at the level books a move nobody can fill. Filled at the trigger bar's close the same straddle is -2.82 / -1.29 / +1.94bp, at the bar's worst price -11.36 / -11.75 / -9.87bp. FOMC: LEVEL +12.27 / +8.02 / +12.77 (no pass), CLOSE -0.05 / -4.87 / +4.28, EXTREME -7.16 / -14.66 / -7.39. The profit is in the fill (latency, spread, slippage), which an Exness account does not have.
- **The user's rule, break of the first range, after waiting.** NFP, 5-minute range: LEVEL -3.71, CLOSE -5.83, EXTREME -10.85bp (excess over the control +0.2 / -1.1 / -3.8); 15-minute range -3.99 / -4.70 / -9.96. FOMC, 5-minute range: LEVEL +9.80, CLOSE +9.03, EXTREME +4.44bp on 101 trades (excess +14.9 / +14.5 / +11.1, t +2.29 / +2.29 / +1.73 pooled; tune / holdout t +1.87 / +1.41, +2.05 / +1.27, +1.43 / +1.04); 15-minute range +5.97 / +5.76 / +1.09. Not a pass: t is under 2 in the holdout, the standard error of the net is about 6.5bp (t about 1.4 against zero), it is one of 42 cells (about one is expected at t 2.3 by chance), and the control is -5bp because random breakouts pay cost and slippage. Confirming +9bp would take about 200 events, roughly 25 years of meetings. A LEAD, labelled so.
- **Follow the move.** NFP: +1 minute +1.55 (15m) / +1.65 (60m), +2 minutes +1.87 / +4.40, +5 minutes -4.99 / -2.96bp net; excess over the control +4.7 / +4.4 / +5.1 / +6.9 / -1.9 / -0.3, t +1.79 / +1.10 / +2.16 / +1.85 / -0.79 / -0.09, never t >= 2 on both halves; the entry assumes a fill at the open of minute +1, which a person does not get. FOMC: +2.83 / +2.68 (+1m), -0.40 / +5.07 (+2m), +0.72 / +7.17 (+5m), t +0.70 .. +1.88, 2 x se 5-12bp. So `gold_focus.py`'s 'following later loses' holds from +5 minutes on NFP; the first two minutes show a small, borderline continuation (+4..+5bp gross) that decays fast.
- **Predictions scored.** P1 (follow about zero net, no significant excess) PARTLY WRONG: NFP +1.6 .. +4.4bp at +1 / +2 minutes, not zero, but not significant on both halves. P2 (the break has no significant excess) RIGHT by the registered rule (FOMC pooled t 2.29, halves 2.05 / 1.27). P3 (under 10% that anything clears the bar) RIGHT once the fill is realistic; the first run's 2 passes were the LEVEL-fill straddle. AMENDMENT, same day: the CLOSE and EXTREME fills (cells 11 -> 21 per event type) were added AFTER the straddle read +20bp, because that is the result this repo says to hunt a bug for; the first run's A and B-LEVEL numbers are unchanged.
- **Limits.** HistData is BID only and the release spread is charged as a constant (2.94bp + 2bp), not measured on gold; no tick data before 2026, so the first seconds are untested here (`fx_news_seconds.py`: +6bp at 0.5-1s on FX pairs, gone by 2s); the three fills are bounds, not a model; 199 and 108 events are few (2 x se of a cell 5-15bp); the FOMC cells are correlated. A forward record is the way to settle the FOMC lead (`desk.py plan` before each meeting). Tests 42 (`tests/test_gold_news_breakout.py`); 41 of 41 planted bugs caught over two rounds, a do-nothing control survived; the module reproduces the exploratory run's 60 output lines exactly. Nothing deployed.
- **AUDIT, same day (`backtest/gold_news_ticks.py`, `logs/gold_news_ticks.txt`, `logs/gold_news_ticks_rescore.txt`): the 'fill artifact' reading above is WRONG in its mechanism.** A 1-minute bar's run past the level is mostly continuation that a RESTING stop order earns, not slippage, and the trigger bar's CLOSE is a manual entry, not a stop fill. On Exness XAUUSDm ticks for the 2026 releases (MT5; 8 NFP, 9 CPI, 6 FOMC) a +-5bp stop fills a median +9.1bp past the level on NFP (+11 with a 0.5-1 s delay; CPI / FOMC 0-6bp), and the tick result per event tracks the LEVEL fill (NFP +-5: tick +64.7bp a trade, bar LEVEL +55.5, bar CLOSE -2.1). Re-scored over 2010-2026 with 10bp charged on the entry and 2bp on a stop exit: NFP +-5 +11.1bp a trade, t 2.45 (tune +13.4 t 2.2 / holdout +7.4 t 1.1, 12 of 17 years positive); 15bp: +6.1 (t 1.3); 20bp: +1.1. CPI (never tested above): gross +5.7bp, at 10bp -8.7 (t -3.1), dead. FOMC +-5 at 10bp +2.7 (t 0.4). So the NFP straddle - which is the user's own description ('dropping to a level we sell, rising to a level we buy') - is a weak LEAD, not an artifact and not a pass (holdout t 1.1; one of 42 cells; the slippage comes from 8 events on a demo feed). The way to settle it is a demo straddle on the next NFPs, filled by the broker's execution. The same flawed rule ('believe a stop fill only if the CLOSE fill holds') was reused in the inside-bar entry below; its NASDAQ cell stays a lead, but for the right reason (1 of 56 cells), not because of the CLOSE fill.

## 2026-11-08 (later) - the daily-zones version: "try the daily zones version" -> "run the daily zones test now": no cell passes and the zone cells are too small to say anything (`backtest/sweep_zone_daily.py`)

After `sweep_zone.py` (4h zones) found nothing, the user asked for daily zones, my suggestion being a target at the NEXT zone (the shape zone traders use). A separate file with its own rules and tests (the first study was not edited). Registered first (prior that any cell passes 4%): daily bars from the 1h data; zone = a base day (range <= 1.0 ATR) + an impulse day (body >= 1.5 ATR, close beyond the base), known when the impulse day closes, live from its first retest for 72 hours (broken by a 1h close past the far edge; dead if not retested in 180 days); the desk's 24-bar sweep as the event; trend = previous day vs its 50-day mean; the target = the nearest unbroken opposite zone's near edge beyond the entry (not older than 360 days), taken only if >= 1.5R away; hold <= 240 bars; 12bp + funding; matched random-hour controls with the same stop distance and the event's own reward:risk. Gate as before.
- **Funnel:** 60,390 sweeps; zoned 726 (1.20%, 110 a year); with a >= 1.5R next-zone target 286 (39%, 43 a year); with the daily trend 130 (20 a year). The median target is 7.3 times the risk away, so it is rarely reached (hit rates 0-16%).
- **Result:** 0 of 6 cells pass. Arm A (every sweep) loses again (net R long -0.11 / -0.20, short -0.06 / -0.06, no excess). Arm B tune / holdout: long -0.31 (n 75) / -0.10 (n 68), short +0.21 (n 94) / +0.26 (n 49); arm C: long +0.12 / +0.27 (n 25 / 31), short +0.52 / +0.37 (n 38 / 36); every |t| <= 1.9. **All four zone cells are UNDERPOWERED** (31-68 holdout trades, standard error 0.3-0.5R): this is 'cannot tell', not a rejection.
- **Information test (T24):** zoned minus unzoned is positive on all four halves (+0.47% / +0.16% long, +0.25% / +0.38% short) and nowhere significant (t <= 1.0), unlike the 4h zones (long holdout -0.38%). The trend inside the zones: +1.97% (t +2.6) on the long tune half and -0.01% on the holdout - a flip.
- **Diagnostics:** B and the plain-3R version (Z3) differ by 0.03R on the holdout on both sides, so the target is not what matters. Z3 short holdout is +0.29R with excess +0.64R (t +2.8, n 93): one of about 16 diagnostic cells, which is what chance produces about once; not a finding.
- **Reading:** daily zones are the first version where the information direction is positive on all four halves, and the sample is far too small to confirm it: 43 target trades a year over the whole 40-coin universe means about 4 more years of data for 100 holdout trades a side, and about 9+ months of live paper for 30 bets. So it cannot be proven or killed with what exists. Not found in this definition (one base day, 72h retest, far targets); an edge under about +0.7R a trade could not have been seen. Together with the 4h result and `sweep_confluence.py`: sweeps, levels and zones, as a chart-pattern family, have no measured edge after fees.
- **Predictions:** D1, D3, D4, D6, D8 right; D2 half wrong (short holdout +0.38%, above the +-0.30% band, t +0.9); D5 wrong (C long tune hit 16% vs 4% on 25 trades); D7 right and bigger than expected (all four zone cells under 100 holdout trades).
- **Tests:** `tests/test_sweep_zone_daily.py` 32 (daily bars, zones and their near-misses, the 72-hour window, the zone index and next-zone target, the explicit-target trade, a planted market with a supply zone above and a demand zone below, controls with downside dips, declustering, truncation, the gate); 60 of 60 planted bugs caught over two rounds (52 of 60 first, each of the eight survivors a gap in my tests; then 60 of 60) and the do-nothing control survived. Nothing deployed or committed.

## 2026-11-08 (the inside bar at a new high) - "30 min time frame, a new high, an inside bar (mother and baby candle), the baby's low breaks, enter with the mother's high as stop": no edge on gold, one NASDAQ buy-side lead - `backtest/inside_bar_break.py`, `logs/inside_bar_break.txt`

The user, right after asking for "a working gold forex bot with bigger returns, not petty", described a rule: on 30-minute bars the market makes a new high; the high bar is a big candle (the mother) followed by an inside baby candle; when the baby's low breaks, sell, with the mother's high as the stop. Two throwaway checks on what "bigger returns on gold" can mean came first (scratch scripts, not in the repo, numbers re-derivable from HistData XAUUSD):

- **Gold at leverage is a coin flip.** One all-in shot, 11,378 random entries 2010-2026, 3-day cap, liquidation at 1/L, 2.94bp costs on the stake x L, both sides: at 100x the stake doubles before liquidation 43% of the time and is liquidated 44%, mean -1.6% of the stake a shot; at 200x aiming for 5x it gets there 14% and is liquidated 72%; at 10-20x nothing happens in 3 days (gold moves ~1% a day). The same shape as `one_shot.py` on BTC / DOGE.
- **Gold's daily trend has a leverage ceiling near 3x.** Long above the 200-day average, flat below, daily bars from the minutes, swap-free: 1x +5.9%/yr (fall 33%), 2x +10.0% (57%), 3x +12.1% (74%, the peak), 5x +9.7% (93%), 10x and 20x ruined. 2010-2019 alone made 2-3% a year at best; the 2020-26 gold bull made the rest. With an approximate 4.3%/yr long swap the best is +5.9%/yr; long / short is worse (1x +3.5%). No leverage turns gold's rise into big returns.

**The rule, as I fixed it before the first run** (the user gave no numbers; one reading of each word): 30-minute bars of the 1-minute data; the mother makes a NEW 20-bar high and is at least 1.0 x ATR14 of the bars before it ('big'); the baby is the next bar, inside the mother's range and at most half its size; a SHORT when the baby's low breaks within the next 4 bars (cancelled if the mother's high trades first); stop = the mother's high, target k x R (1, 2, 3), 24-hour time exit; managed on 1-minute bars (stop and target in one minute = the stop, gaps fill at the open). Two fills, because the last test (`gold_news_breakout.py`) found a stop-order fill artifact: TOUCH (sell-stop at the baby's low, +2bp slippage) and CLOSE (market at the close of the first 30-minute bar closing under it). Costs: gold 2.94bp round trip, NASDAQ 1.27bp, everything else 1.5bp (ASSUMED). Control = the same bracket (the trade's risk fraction, k, 24 hours) entered at the same minute-of-day on 5 random other days of the same half, same costs. PASS = net R > 0 and Welch t >= 2 of the excess over the control on BOTH halves (first 60% of signals by time / the rest). Primary cell named first: XAUUSD, short, TOUCH, 2R. 56 cells: gold 2 sides x 2 fills x 3 targets, gold look-back 10 / 50, ten more markets (7 forex pairs, NASDAQ, S&P, DAX) x 2 sides x 2 fills at 2R.

- **Gold, the rule as stated (short at new highs):** TOUCH n 1,342, win 44.5% / 32.2% / 26.4% at 1R / 2R / 3R, net -0.245 / -0.233 / -0.261 R a trade; CLOSE n 910, win 48.0% / 36.4% / 32.0%, net -0.153 / -0.104 / -0.077 R. The random-short control loses about the same (-0.18 .. -0.28 R at 2R), so the excess is nil: t between -0.9 and +0.7 on both halves in all six cells. A 2R trade at a random entry wins one time in three, so a 32% win rate is the coin; the loss is cost (about 0.2 R a trade, because the stop sits close). Look-backs 10 and 50 bars: the same (TOUCH -0.24 / -0.26 R, CLOSE -0.09 / -0.14 R, excess t within +-1.2).
- **Gold, the mirror (long at new lows, the baby's high breaks, stop at the mother's low):** TOUCH -0.15 .. -0.19 R, CLOSE -0.006 .. -0.056 R. The best, CLOSE 1R, is net +0.032 on the holdout with excess t +2.08 there but -0.114 and t +0.03 on the tune half: no pass.
- **The other ten markets at 2R:** every short loses (TOUCH -0.16 .. -0.29 R, CLOSE -0.04 .. -0.12 R); excess t never reaches +2 on both halves. ONE cell passes: **NASDAQ (NSXUSD), the mirror (a buy), TOUCH fill:** n 889, win 40.5%, net +0.079 R (tune +0.031, holdout +0.149), excess t +2.34 / +3.01, against a control (random longs at the same time of day) of -0.12 / -0.11 R. The CLOSE fill of the same cell is better (net +0.130 R, n 602) but its excess t is +1.25 / +2.33, which fails the bar, so by this file's own rule (believe a stop-order result only if the CLOSE fill holds) it is a **LEAD, not a result**: 1 of 56 cells (about a 3% chance of one by luck if every cell were null, ignoring that the cells share trades), it is a NASDAQ dip-buy in the family of `ndx_capit.py` and the machine's QQQ book (long only, new low then a small inside bar then the break up), and it needs the 1.27bp cost to hold. S&P's mirror (-0.05 R touch, +0.02 R close) and DAX's (-0.06 / +0.03) do not repeat it.
- **Predictions (stated in the exploratory script before the run; prior that any cell passes about 5%):** T1 (no cell passes on gold) right for gold, wrong across the table because of the NASDAQ lead; T2 (TOUCH better than CLOSE by more than 0.2 R, the NFP lesson again) WRONG - on gold the stop-order fill is the worse one (-0.23 vs -0.10 R at 2R) because it is filled into whipsaws the close would have skipped; T3 (the mirror as null as the short) right; T4 (the random-short control loses on gold) right.
- **Reading:** the tight-stop inside-bar entry is a pattern whose cost (~0.2 R a trade) is larger than any information it carries; it is the same finding as `candle_scan.py` / `candle_manage.py` (inside bars among 17 patterns, 204 cells each, crypto and 1h / 4h / 1d) now at 30 minutes on gold and forex: random entries with the same bracket do as well. The only thing standing is a NASDAQ buy, which needs a forward record (a paper arm) before it counts; it adds nothing the machine does not already hold in its NASDAQ dip-buy until shown otherwise. Not built: the user's gold bot (the numbers above say no gold rule found gives bigger returns).
- **Limits:** bid-only HistData bars; forex costs are an assumption (1.5bp), not Exness's; 'new high', 'big' and 'baby' are one reading each (only the look-back was varied); controls share the signal's half but not its regime; the cells share trades; the 24-hour hold would cross swap on a non-swap-free account (not charged); no tick data, so the first seconds after a break are untested; the leverage checks are scratch scripts.
- **Tests:** `tests/test_inside_bar_break.py` 42 (each signal condition and its boundary, the true-range ATR, minute-bar management with ties / gaps / the 24-hour edge, both fills, the control's days / time of day / holes / data end, Welch, the pass rule at t exactly 2, the printed line, and a planted five-pattern market end to end with the mirror and the 60/40 split); 100 of 100 planted bugs caught over two rounds (93 first: the seven survivors were gaps in my tests) and the do-nothing control survived; one more mutant is equivalent (a redundant end-of-data guard). The module reproduces the exploratory run's 62 result lines exactly. Nothing deployed or committed.

## 2026-11-08 (the zone studies with more data) - after `blindness_check.py` showed the zone tests could not see a moderate edge, the user: "yes, more data": the 4h zone is dead at any tradable size; daily-zone longs dead; daily-zone shorts a crash-tail lead (`backtest/sweep_zone_more.py`, `logs/sweep_zone_more.txt`)

The two studies' rules FROZEN (their own `coin_events`, the loop checked to reproduce their event rows exactly) on data neither read: Binance perps 2020-26 ranked 41-100 by the prior month's volume (83,969 sweeps, 555 coins) and Binance spot 2017-08 .. 2019-12 (10,218 sweeps, 79 pairs, no funding). Registered first: 8 judged cells (4h B / C, daily B / C, long / short), Holm over 8 on the new sample, net > 0 in both time halves, excess over the random-hour control, >= 100 trades, and a power line (MDE80) printed beside every cell.
- **Verdict on the new data: 0 of 8 pass.** 4h zones: long +0.013R (n 1,537), short -0.146R (n 1,668, t -2.9); pooled with the old sample long -0.042R / short -0.123R with MDE80 +0.15 / +0.16R - an edge of +0.15R would have been seen, and the result is at or below zero: dead at any tradable size. Daily-zone longs -0.19R new, -0.20R pooled (t -2.1): dead.
- **Daily-zone shorts stayed positive** (new: B +0.35R n 149, C +1.12R n 49, t 2.1, Holm 0.13; pooled C +0.72R, t 2.7) but the median trade is -1.0R and ~10 of 123 trades carry the mean (without them +0.09R; B -0.03R): the 2025-10-10 crash (CRV +17.9R), INJ twice, the 2024 alt bleed. A crash-tail bet in the bear sleeve's family, ~14 trades a year: a lead, not a book.
- **More data was less than hoped:** the new zoned samples are 1.4-1.5x the old, not 3x (the coins ranked 41-100 form fewer zones). Predictions M2, M3 right; M1, M5 wrong; M4, M6 half wrong (in the file).
- **Tests:** `tests/test_sweep_zone_more.py` 9; 18 of 18 planted bugs caught over two rounds (the first left the halves rule and the Holm step untested: fixed with exact cases), the do-nothing control survived. Nothing deployed.

## 2026-11-08 (an edge without capital restraints) - the user: "I want an edge that has no capital restraints - liquidity sweep, indicators, whatever": the RSI-above-80 momentum lead replicates in direction on unseen data, misses the bar by a hair, and is not capital-free (`backtest/rsi80_more.py`, `logs/rsi80_more.txt`, `logs/rsi80_more_costs.txt`)

The one lead `rsi_ratio.py` set aside (4h RSI(14) crossing UP through 80 -> long, stop 4 ATR, target 4R, out after 24 bars, one position per coin; +0.227 / +0.292R a trade on the top-40) re-run with that file's own code (reproduced exactly first) on perps ranked 41-100 (2020-26) and spot 2017-19, registered as ONE cell (t >= 2 day-vote, excess t >= 2, both halves).
- **NO PASS, narrowly:** new data +0.138R a trade (perps +0.126R, spot +0.229R), excess over random entries +0.086R (t 2.3), both halves +0.14R, but the day-vote t is 1.80 against 2.0. Smaller than where it was found, the same direction on two independent samples; all 8 neighbouring brackets positive.
- **Shape:** positive in 6 of 7 years on the new coins, but the best 20 of 666 entry days carry it (without them -0.008R a trade, median trade -0.17R): convex alt-momentum bursts, the trend book's family. Real funding is lower than the flat charge; +30bp slippage costs ~0.02R. Not a cost artefact.
- **Capital:** all-in one-at-a-time is ruinous (4-ATR stops on small coins reach 50-70% of the price). At 1-2% risk a trade on the new coins (real funding, +10bp): $100 -> $277 (+19%/yr, fall 26%) / $906 (+45%/yr, fall 48%, up to 7.3x open); 2017-19 spot +19%/yr at 1%. $20 cannot trade it (34 of 2,380 signals clear the $5 minimum at 1%); ~$100 is the floor.
- **Predictions** R1-R4 right, R5 right but marginal. **Not done:** its overlap with the trend book, a forward record. Tests 9; 24 of 24 planted bugs caught (three first survivors were gaps in my synthetic data), control survived.
- **Overlap with the machine (the user: "yes, check overlap"; `backtest/rsi80_overlap.py`, `logs/rsi80_overlap.txt`):** NOT the trend book again - daily correlation -0.04, monthly +0.07; on the RSI book's 20 best days the trend book made -0.36% a day (0 of 20 among its best 10%); +2.0% a month in the machine's worst 20% of months; 89% of its trades in coins the trend book never holds. But as an add-on, on the unseen coins only, it loses to 'bet the machine bigger' on 2020-24 (-$791 on a $300 typical year) and beats it on 2024-26 (+$3,401): no pass. (With the top-40 included it passes both halves, but that is the sample it was chosen on.) Predictions O1-O3 wrong (it overlaps less than I expected), O4, O5 right. Caveat: booked-at-exit series understate shared exposure (the trend book exits weeks later). Tests 3; planted bugs 7 of 7, control survived.

## 2026-11-09 (everything linked) - the user: "run countless combinations where there is a link between anything - indicators, news, market patterns": ONE walk-forward model fed every source on disk finds real rank information, but it is mostly one factor and none of it pays; linking the sources adds nothing (`backtest/all_sources_model.py`, `logs/all_sources_model.txt`)

Asked for the most efficient way to run "countless combinations", the answer given was not to enumerate rules (about 16,000 have been run here; the luckiest of 10,000 unrelated no-edge strategies over 6.5 years shows a Sharpe of about 1.5) but to fit ONE model that sees every source and count it as one test. `indicator_model.py` had done that with price and volume only; every other source had been tested on its own. This joins them: funding, Binance positioning (crowd, top traders, taker flow, open interest), 11 Telegram news channels (counts by event type, FinBERT tone), Bluesky, DefiLlama unlock schedules, coin size and age, and a market block only gradient boosting sees, so it can find interactions (Fear & Greed, BTC trend and volatility, fuel, breadth, dispersion, market-wide news). PIT top-40, rows from 2022-01, quarterly walk-forward, out of sample 2022-10..2026-09, indicator_model's trade (long top fifth / short bottom fifth, 24bp + long funding) and bar; seven predictions registered first.
- **NO PASS: 0 of 6 primary cells, Holm 1.00 in every cell.** Best: ALL gradient boosting at 7 days, net +20.6bp a week (t +0.3) tune / +135.7bp (t +1.0) holdout, worst alignment -14.0bp.
- **Real information, mostly one factor:** daily rank IC +0.10..+0.18 (t 5-11) on both halves at every horizon, and the model with NO price features scores the same (+0.135 / +0.176 at 7 days). Feature by feature (7 days, tune / holdout): atr_pct -0.136 / -0.190; coin age +0.136 / +0.169 (rank correlation with atr_pct -0.65); open interest over volume +0.103 / +0.118 (-0.62); worst day in 30 +0.109 / +0.182 (-0.75). Calm, old, deep coins beat volatile, young ones in 2022-26, and every source re-expresses that. What is not tied to volatility is weak: news count +0.031 / +0.072, 7-day taker flow +0.085 / +0.030, unlocks ahead -0.026 / -0.037, funding +0.012 / +0.038.
- **Linking adds nothing:** ALL minus PRICE (same model, same days), the paired gross spread is never t >= 2 on both halves (6 of 6 cells); IC gain -0.012..+0.020; dropping any one new family costs at most 0.007 of IC.
- **Why it does not pay (post hoc, in the log):** a planted signal with a clean IC of 0.10 traded on its own meets the bar easily (net t +4.5 / +2.6), so the test can see a tradable link. The model's IC of 0.14-0.18 does not, because its bottom fifth is the most volatile coins - the ones that squeeze 100-300% in a week - so the short leg carries the fattest tails. With volatility removed (each day's line on the atr_pct rank taken out of the prediction) a real piece remains, IC +0.04..+0.07 (t 3-9), but it moves prices by about the cost: gross +54 / +88bp a week at 7 days against ~45bp of costs, net t +0.2 / +0.5; 0 of 3 horizons meet the bar.
- **Predictions:** A1 (no pass) right; A2 wrong by a hair (the IC gain reached +0.020 on one half; the paired part was right); A3-A7 wrong: the model without price is as informed as with it (through the same factor), ridge's top coefficient at 7 days is crowd positioning with age next, one holdout 1-day cell was barely positive, the size family (not positioning) mattered most when dropped, and the planted IC 0.10 feature did not lift the MODEL over the bar (the volatility sort's noise swamps it) even though it passes alone.
- **Limits:** each family was looked at alone on 2022-26 before, and the holdout is the shared one, so even a pass would have been a lead; unlock schedules are DefiLlama's current file; Bluesky covers 19% of coin-days. One model family, fixed settings, one trade shape (a quintile long-short); a vol-neutral long-short or long-only design was not registered and was not tuned.
- **Tests:** `tests/test_all_sources_model.py` 20; 39 of 39 planted bugs caught (three first survivors were gaps in my tests: the fuel threshold, BTC's 7-day return, the 30-day liquidity window), the do-nothing control survived. The registered part of the log is identical across three runs (the post-hoc sections were added after the first). Nothing deployed.
- **What it means for 'countless combinations':** on the data on disk the joined search finds information, not money. More combinations on the same history cannot change that; new evidence has to come from forward data (several frozen leads paper-traded at once) or a genuinely new source.

## 2026-11-09 - market profile / auction market theory on NQ: value area, POC, value migration, initial balance, open drive - 0 of 9 cells pass (`backtest/nq_profile.py`, `logs/nq_profile.txt`, `tests/test_nq_profile.py`)

The user asked whether every order-flow and profile tool they had named was tested (heat map, time and sales, gamma, volume profile, market profile, footprint, delta, VWAP, auction market theory). Everything but market profile / auction market theory as stand-alone rules had been (his_volprofile.py, his_gex.py, book_hist.py, his_tape.py, his_cme_scan.py, the VWAP results); then "run the market profile test on NQ". The 16 years of NQ 1-minute bars WITH real volume already on disk (nq_fetch.py, USD 19.93 paid on 2026-11-03), no new spend.
- **Design (registered in the file before the run, prior 5% that any cell passes):** the PREVIOUS cash session's profile, two constructions: TPO (13 half-hour letters, what 'Market Profile' means; primary) and volume-by-price from the real 1-minute volume (the plateau check). Bin = 2bp, value area = the CME two-bins-at-a-time method to 70%. Nine cells, decision at a bar's close and entry at the next open, exit at the 16:00 close or a touched target, no stop: R1 the 80% rule, R2 back to the prior POC, R3 fade the value edge from an inside open, R4 acceptance outside value (with it), R5a / R5b value migration (POC / no overlap), R6a / R6b initial-balance break (all / narrow IB), R7 open drive. 1.27bp a trade (the NQ noise study's cost), also shown at 0.25 and 2.54bp. Control = the SAME trade (side, entry bar, target distance, exit) on every session of the same half, so drift, side mix and time of day are removed. Gate: net > 0 on both halves, excess > 0 on both halves, holdout Holm p < 0.05 over the 9 cells, >= 100 holdout trades, and the volume construction also net > 0 on both halves.
- **Result:** 4,016 sessions (tune 2,409 to 2020-04-14, holdout 1,607). **0 of 9 cells pass, in either construction, and none is even a LEAD.** Net bp a trade, tune | holdout: R1 +2.40 | -1.49, R2 -2.65 | -0.39, R3 -2.33 | -3.93, R4 +0.12 | +0.37, R5a +0.34 | -2.33, R5b -0.75 | -5.71, R6a -3.62 | +1.21, R6b -6.58 | -8.43, R7 +0.43 | +15.59 (holdout t 1.7, 120 trades, Holm p 0.34). The matched-day excess has |t| < 2 in every cell and half (the largest is R1's tune half, 1.9). 65% of sessions open outside the prior value area.
- **The 80% rule is not there:** after an outside open that comes back in and holds two half-hours, the far edge of value is touched 47.6% | 43.5% of the time (tune | holdout) against 43.4% | 44.2% for the same trade on random days. The textbook 80% is not in the data; the matched days do as well.
- **What the controls showed:** shorts lose in R2 / R5a / R5b (-3.6 / -5.1 / -8.3bp) because NQ drifts up (+3.6bp / +2.9bp a session long from the open); the matched-day excess removes it. At a futures-like 0.25bp, R4 and R7 are positive on both halves, but their tune-half excess t is 0.7 and 0.2. R7 (open drive) is the only number that stands out: +15.6bp on the holdout, +0.4bp on the tune half, negative in 2010, 2011, 2015, 2019 and 2025 - one of nine cells, holdout only, the mined-holdout shape; it does not meet its own lead line (t >= 2 on both halves).
- **Predictions:** M1 right (none pass), M2 half right (the far edge is touched about as often as on random days; but 44-48%, not the 55-70% I wrote), M3 wrong (holdout gross is negative for both migration cells; the excess t < 2 part is right), M4 right, M5 right (the first IB break exists on 95.8% of sessions, excess t -1.6 | +1.0, narrow IB worse), M6 right (6.6% of sessions, excess t 0.2 | 1.8), M7 right.
- **Checked:** 39 tests; 98 planted bugs caught over three rounds (88 of 96 first, eight survivors that were all gaps in my tests: rounding vs truncation of the bin width, the value-area pair rule and its 70% boundary, a failed distance check ending the day, the touching boundary of R5b's short side, the entry bar in the matched control, Holm applied in analyze, the volume plateau; then 96 of 97, then the last two in a targeted rerun), the no-op control survived every time; a planted continuation passes the gate and a strong drift with no edge does not.
- **Not found in THIS definition, not 'impossible':** the profile is of the cash session only (no Globex hours); volume is spread evenly over each 1-minute bar's range; a touched target is assumed filled at the target; there is no stop, as taught (so a trade held to the close can lose a lot); costs are the Exness CFD's. Not tested: full-session profiles, single prints / poor highs / excess, composite or weekly profiles, a developing intraday profile as a stand-alone rule on real volume (his_volprofile.py did it on tick counts at one trader's clicks), open types beyond the open drive, other markets (ES). Of the user's list of tools, every item now has at least one test in this repo.

## 2026-11-09 (forced flow, two untested sources) - the user: "test both": crypto options expiry and the bitcoin ETF flows; no pass; the ETF flows are dead, and a small real dip into each monthly options expiry is a lead (`backtest/options_expiry.py`, `backtest/etf_flows.py`, `logs/options_expiry.txt`, `logs/etf_flows.txt`)

After the scoreboard was called what it is ("it's not a new strategy, it's just old ones and their results"), the two forced-flow ideas found untested anywhere in the repo were run, predictions first in each file.

**Options expiry** (Deribit expires at 08:00 UTC: every Friday, the last Friday of the month, the last Friday of a quarter; Binance BTC / ETH perp hours 2020-01..2026-11: 82 monthly expiries (27 quarterly), 276 ordinary Fridays, 1,428 Monday-Thursday days; one trade per event in the tune half's direction, 12bp + funding).
- **NO PASS: 0 of 16 monthly / quarterly cells, 0 of 8 every-Friday cells.** The 24-hour windows flip sign between halves (BTC into24 +90bp tune, -115bp holdout); the MDE80 of a monthly 24-hour cell is 1.1-1.5% a trade, so only big effects were ever visible there.
- **The lead: the 4 hours INTO a monthly expiry.** BTC -49 / -42bp against ordinary Fridays (t -2.5 / -2.7), ETH -52 / -45bp (t -2.5 / -1.6); as a short, net +32.7bp (t 1.9) / +23.0bp (t 1.8) - under the bar, Holm 0.57. Checked after the first run (POST-HOC in the log): BTC falls in 67% of the 82 expiries against 47% of ordinary Fridays; without the 3 worst events -28bp (excess t -2.8); negative in all 7 years (2026 -2bp, 2023 -9bp the weakest); ETH negative in 5 of 7; the last hour 07:00-08:00 UTC (Deribit's futures settle on a 07:30-08:00 average) carries the most (BTC -24bp t -3.2, ETH -31bp t -3.3); the PLACEBO (the Friday one week before) shows nothing (-2 / -5bp, t ~0). Ordinary weekly expiries dip a little too (-15 / -6bp into 08:00): smaller expiry, smaller dip. A real, small, expiry-specific move - found after looking; worth roughly +0.25% a month on the money used, far from the goal.
- **Pinning (X2) wrong:** the hours into a monthly expiry are not quieter (|return| ratio 1.10 BTC, 0.98 ETH); the 4 hours AFTER are wilder (x1.61 BTC t +2.2, x1.50 ETH t +2.4) - the release half of the story, tradable only with options.
- Predictions X1, X3, X4 right; X2 wrong.

**Bitcoin ETF flows** (Farside's daily table of the US spot ETFs, 2024-01-11..2026-11-06, 709 flow days; signal = the day's flow as a percentile of the previous 60; long after a top-fifth inflow day / short after a bottom-fifth outflow day, entered 14:00 UTC the next day, held 24 / 72 h).
- **NO PASS, 0 of 4, and no lead:** long after big inflows +24 / +4bp net (t 1.2 / 0.1); shorts after big outflows lose (-42 / -16bp). The next-24-hour IC is +0.055 / -0.037 (sign flips). The flows follow the price: same UTC day +0.43, previous 5 days +0.37 - the ETF buyers chase what already happened, they do not lead it.
- Predictions E1-E4 right; E5 wrong (the 24-hour cells' MDE80 is 0.8-1.0%, a little under the 1% guessed).

**Tests:** `tests/test_options_expiry.py` 9, `tests/test_etf_flows.py` 7; 28 of 28 planted bugs caught over two rounds (first survivors: no test where the tune and holdout directions disagree, no flow day between the 70th and 80th percentile), the do-nothing control survived. Nothing deployed. The ETF table is kept as daily totals only (`strategy_analysis/data/etf_flows/farside_btc_daily.csv`, gitignored).

## 2026-11-10 (the whole-repo audit) - the user: "audit all the strategies ... find an edge that is so good and we have overlooked, one for low capital, some high frequency, and his edge": two new checks, both no pass; the only lead a forward record can confirm in months is copying the trader (`backtest/audit_event_only.py`, `backtest/audit_mn_vol_screen.py`, `logs/audit_event_only.txt`, `logs/audit_mn_vol_screen.txt`)

**What was read:** doc 21 (every kill rated), doc 23 and `strategy_analysis/his_strategy.md` (s56-s72), STATUS, this file's entries since 2026-10-09, and the live feed (2026-11-10 15:00 UTC: main $255.35 - under the $261.30 day-45 line with 13 days left - fresh $222.49; crash bids 115 fills at +0.42% a fill against +0.8 expected; carry +$18.6 / +$16.3; capit2, news and the bear sleeve have not traded).

**Check 1 - the forced-flow books as their own account** (bear sleeve + crash bids + capit2 + news + NASDAQ dip-buy, `all_books.py`'s own series; predictions E1-E3 in the file first). CAGR +121%, fall 22%, 78% of months up, no 12-month window under its start; $300 typical year $644 / $711 (tune / holdout). The deployed machine scaled down to the same fall (x0.40 / x0.35) makes $1,099 / $1,271: **no pass against bet-smaller**. It wins the bad kind of year (2022 +143% against +56%) and loses the good kind (2026 to September +3% against +188%). Without the news book (picked after looking): CAGR +95%, worst month -12.1% / -3.9%. BACKTEST; the crash bids' in-hour risk and the news book's -25% in 2026 are inside it.

**Check 2 - a volatility screen on the market-neutral book** (do not rank the most volatile third of the eligible names; both legs / long leg / short leg; 7 weekdays; the bar is universe_floor's; predictions V1-V4 first). Joined two findings that had never met: low-volatility coins beat high-volatility ones in ranks (`all_sources_model.py`), and the live MN long leg lost 7 of 7 weeks in pumped micro-caps. **No variant passes**: Sharpe base +1.38 / +1.36; both legs +1.27 / +0.72; long leg +1.26 / +1.34; short leg +1.35 / +0.95; never better on more than 3 of 7 weekdays. The book's money is in the wild names on both legs. Side fact: the base long leg earns +1.59% a week on the tune half and -0.05% on the holdout, the short leg -0.54% / +1.11% - the book changed legs between halves, which is what the live tape shows.

**The audit's reading (no new number):** (1) nothing in the graveyard is a buried book - doc 21 stands; (2) the survivors split into books that PREDICT (trend, MN, daily, carry, crowd: all regime bets, all at or under their bands live) and books that are PAID BY FORCED FLOW (crash bids, capit2, news, sleeve: mechanism, mostly idle, small); (3) high frequency is closed at retail by cost, not by a missing signal - every signal found is 1-2bp against 4-12bp; (4) the trader's side is still not found in anything tested, his forward record since first contact (2026-09-10) is 10 of 11 NASDAQ trades won and 4 of 4 October races, and a copy 5-10 s late is the one lead in this repo whose effect is big enough to confirm or kill in about three months (15 trades: 12 or more wins happens 4% of the time at the 55% baseline, 90% at his 88%) - every other lead needs 6-23 years (`forward_ledger.py`). It needs his entries live; VertexFX documents a client API and mobile notifications (search summary only, not verified).

## 2026-11-10 (weekend gold) - the user: "I want something of my own": the gold token's weekend move snaps back when gold reopens - real, and worth about 2% a year (`backtest/paxg_weekend.py`, `logs/paxg_weekend.txt`, `tests/test_paxg_weekend.py`)

A mechanism not in the graveyard, from the family that has paid here (forced convergence): PAXG trades all weekend while gold is shut (Friday 17:00 - Sunday 18:00 New York), so nobody can arbitrage it; a weekend move is information or noise. Rule: fade the move measured at Sunday 16:00, enter at 17:00 (one bar later, so a bounce in the signal print cannot pay it), exit 2 / 6 / 24 hours after the reopen; 12bp; tune = first 60% of 254 weekends (2020-08 .. 2026-09); a weekday placebo; a hedged version at the reopen. Predictions W1-W6 in the file first.

**Result: the effect is there and it does not pay.** The token wanders a median 0.24% (0.5%+ on 22% of weekends); about a third of the move is information (gold's gap: slope +0.29) and about a third is given back within 6 hours of the reopen (slope -0.28 / -0.37 on the two halves; weekday placebo -0.02, and the placebo trade loses its cost). After fees 0 of 9 cells pass: the primary (0.5%, 6h) is +0.17% / +0.17% a trade, t 1.2 / 0.75, 11.5 trades a year, about +2% a year on the money used, +0.02% without its three best trades, negative in 2026. Moves of 1%+ pay +0.55..+0.78% a trade but there are 13 in six years. Hedged against gold after the reopen: zero - the convergence is over within an hour or two. W2, W5 right; W1, W3, W4, W6 wrong (in the file). Not tested: minute-level entries at the peak of a weekend dislocation, the newer gold perps (months of history), other tokenised assets. Tests 9; no planted-bug round.

## 2026-11-10 (the open-interest flush) - the user: "new strategy in crypto": after an 8% day, coins whose open interest was wiped out bounce more - a weak lead on 13 survivor coins, no pass (`backtest/oi_flush.py`, `backtest/oi_flush_check.py`, `logs/oi_flush.txt`, `logs/oi_flush_check.txt`, `tests/test_oi_flush.py`)

The family that pays here is buying forced selling, always measured by PRICE (a wick, RSI, a 10% day). Open interest measures it directly; `cascade_redux.py` had tested that at 5 minutes (real, under the fee), never at hours-to-days. Rule, written first: a coin down 8%+ on 24 hours ago (one event a coin a day), split by the change of open interest in contracts over the same 24 hours - FLUSH (-10% or more), MID, BUILD (flat or up); long one hour later, out at +5% or after 96 hours; 12bp + funding; day-clustered t; tune = first 60% of events. Data: the 5-minute metrics archive of the 13 coins on disk. Predictions F1-F6 first.

**Result:** 2,044 events on 666 days, 9% of them a flush. FLUSH +1.05% a trade on the tune half (t 1.38) and +2.85% on the holdout (t 1.97, 38 trades on 26 days); BUILD -0.21% / +0.62%; the difference +1.26% / +2.24% (t 1.3 / 1.5). Pooled +1.44%, t 2.07, 29 trades a year. **No pass**, and the post-hoc checks do not strengthen it: no dose-response on the tune half, a within-day advantage on 44% of tune days, the holdout negative without its 5 best days, 2026 negative. The strongest number is the known one: the deepest third of drops bounces whatever open interest did (+1.71% t 2.4 / +2.19% t 3.7) - the capitulation book, on survivor coins. Crowd long share not rising during the fall: +1.62% / +0.68% (same direction, tune only significant). F3-F6 right, F1-F2 wrong. Open: the same split on the PIT top-40 with dead coins (needs the metrics archive for ~100 symbols). Tests 8; no planted-bug round.

## 2026-11-12 (an outside recommendations document on the Analyst desk) - the user attached a 9-page PDF ('Forexbot & Analyst Desk: Strategic Recommendations & Optimization Guide') and asked for a strict audit: several numbers misquoted, its four filters fail together out of sample (`backtest/analyst_filters_oos.py`, `logs/analyst_filters_oos.txt`)

**Its numbers against the repo:** 10,580 calls, 18.04% hit and -99.97% are right (`logs/analyst_replay.txt`, `analyst_replay.json`; the -99.97% is the desk's 0.5%-risk paper book ending at $0.09, not a liquidation); -0.198R is -0.197R; the profit factor 0.42 is not in the repo and the calls give 0.74 (in R); 'statistically significant (p < 0.001)' sits beside a replay whose test for an edge reads p 1.000. '$20-$100 at 10-30x: 100% liquidation' is wrong for the holdout at 10x (0 liquidations, the accounts bleed to $0.35-$0.49), and the replay shows $20 and $300 tracking identically (A7), so neither the $5 minimum nor 'spread noise' was the cause - negative expectancy times leverage was. Its rule figures mix the 4.7-year replay with the desk's ~95 live calls: SR '-0.38R' is neither (replay -0.216R, live -0.35R); SR '-0.69R', FIB '+0.07R', SMC '+1.53R' and the sweet spot's '+0.71R' are post-hoc slices of 9-28 LIVE calls (`backtest/analyst_sweetspot.py`'s docstring: 14 independent bets, t 1.2), not 'stop-adjusted parameter replays'; on the replay the sweet spot is -0.114 / -0.146R and SMC with a stop >= 0.8% -0.128 / -0.150R (`logs/analyst_replay_cuts.txt`). The tight-stop half holds (stop < 0.4%: -0.544 / -0.621R, worst bucket on both halves). The session gate's '-220R to -20R' is wrong: the repo has gold -94.1 -> -66.9R and QQQ -126.8 -> -18.9R (-220.9 -> -85.8R; `analyst.py` docstring); the gate is already live since 2026-11-08 (`f921ca8`) and DST-aware, where the document's hours are wrong half of the year.

**Its four filters, inside the replay engine** (each applied before the 6h cooldown, as a filter in `analyst.py` would; the no-filter variant reproduces the 10,580 calls exactly; predictions O1-O5 first, all right): COMBINED (stop >= 0.8% + 4h EMA50 slope with the call + the live session gate + drop SR) keeps 13% of the calls and loses -0.093R tune / -0.106R holdout a call (t -0.9 / -0.3 per bet), hitting 4-6 points BELOW random entries with the same stop and target on both halves; $300 at 0.5% a call ends $195 / $225. The 4h EMA50 slope alone makes the desk worse (-0.172 / -0.225R, t -3.1 / -2.9). Dead; the break-and-retest rule was not built (the document gives no rule; designing one now would be after looking).

**Its code and plans:** the stop filter calls a `logger` analyst.py does not have and ignores the side; an EMA must be read from the closed 4h bars (`closed()`), not the fetched ones; the circuit breaker calls an undefined `cancel_order` and fails OPEN when the balance is unset; the desk places no orders, so none of it applies there; moving files into `core/` and archiving MT5 would break every import, service and deploy script (MT5 is in use: `forex_bot.py`, `forward_ledger.py`) during the code freeze; the slippage constant has no source; 'prop-firm challenges' repeat `prop_pass.py`'s lottery with no positive-expectancy rule to bring.


## 2026-11-12 (the Analyst desk in profit) - the user: "it's in profit, see if we got a good strategy from it": the paper book's +6.9% is its 3x cap skipping tight-stop calls plus three big short winners; the wide-stop pocket has not shown up since it was registered (`backtest/analyst_profit_check.py`, `logs/analyst_profit_check.txt`, live log `logs/analyst_calls_20261112.csv`)

The desk's book stood at $320.79 (+6.93%) after 119 resolved calls (2026-10-27 .. 11-12) while its average call was -0.18R. Booked calls (inside the 3x gross cap) +0.173R a call (t +0.8 over 27 bets), the 36 calls the cap skipped -0.992R (3 won): the cap refuses big notionals, i.e. tight stops, so it acts as a stop-width filter. Without its best 3 calls the book is $296.49; shorts +$21.54, longs -$0.76. Stops >= 0.8%: +0.33R over 47 calls, but the 14 made after the 2026-11-06 registration are -0.18R (9 bets, -0.06R a bet). In the replay's own book with the same rules, a +6.9% stretch of 119 calls happens 2.5% of the time, and the same slices lose over 4.7 years. Verdict: a lucky / regime-helped stretch of a desk with no measured edge; the registered forward test (30 bets, about early December) is the judge. Predictions P1, P2, P4, P5 right, P3 wrong (in the file). No tests (a read of a log).

## 2026-11-12 (the open-interest flush, point-in-time) - the user: "Yes, run it": the flush lead from 13 coins does not survive the PIT top-40 with dead coins; it was a survivor effect (`backtest/oi_flush_pit.py`, `backtest/oi_flush_pit_check.py`, `logs/oi_flush_pit.txt`, `logs/oi_flush_pit_check.txt`, `tests/test_oi_flush_pit.py`)

`oi_flush.py`'s rule frozen (coin down 8%+ on 24 hours ago, split by the change of open interest in contracts over the same 24 hours, long one hour later, +5% or 96 hours, 12bp + real funding, day-clustered t, first 60% of split events = tune) on the PIT top-40 including dead coins, prices from `pair_lab.hourly`, open interest from Binance's 5-minute metrics archive (27,521 symbol-days fetched, 8,171 not served - mostly before 2021-12). Predictions P1-P6 in the file before any open interest was fetched (prior 20% that it passes).

**Result: NO PASS.** 15,471 events on 357 coins; 10,857 (70%) could be split; FLUSH 14%. FLUSH +0.30% a trade on the tune half (t 0.74, 1,131 trades) and **-1.01% on the holdout** (t -1.03, 394 trades on 239 days); BUILD -0.43% / -0.57%; FLUSH minus BUILD +0.74% / -0.44%. Pooled FLUSH -0.04% a trade, average loser -11.4%, worst -99.4%; no dose-response; worse than the other drops on the same day; holdout without its 5 best days -2.23% (t -2.46). **The 13 coins still show it (FLUSH +1.11% / +3.45%, holdout t 3.05); every other coin does not (+0.20% / -1.52%)** - surviving, liquid coins bounce after a flush, the coins a point-in-time list holds keep falling. The deepest third of drops still beats the shallowest on both halves (+0.86 vs -0.53 / +0.15 vs -0.39): the capitulation family, small, already in the machine. P1, P2, P3, P5 right; P4 wrong; P6 right only mechanically. Tests 11; 28 of 29 planted bugs caught (the survivor is equivalent), control survived. Nothing deployed or committed.

## 2026-11-12 (the perp's premium to spot) - "find me a new strategy" -> "yes, run it": the gap closes within hours, but trading it pays too little and too unevenly; no pass (`backtest/premium_dislocation.py`, `logs/premium_dislocation.txt`, `tests/test_premium_dislocation.py`)

Binance's hourly premium index (perp vs spot index), never tested here, downloaded free for every PIT top-40 coin-month including dead coins (365 coins). Rule written first: perp 0.5%+ under spot -> long one hour later, out when the gap is back inside 0.1% or after 24h (mirror short at +0.5%), 12bp + funding, control = calm hours with the same 24h move. LONG: +0.74% a trade on the tune half (t 2.18), +0.36% on the holdout (t 0.40); 59% of gaps close within 4h; excess over the drop-matched control +0.82% / +1.49% but not significant; without its 5 best days -0.06%; 2026 -0.47%. SHORT: dead (excess -0.48% / -0.90%). A weak lead of the capitulation family, not a book. 6 tests, 11 of 11 planted bugs caught.

## 2026-11-12 (the daily breakout book live) - the user: "daily breakout is shit, not a single positive trade": 1 winner in 18 live trades is inside the book's own history; three 45-57% losers on new hype coins are not (`backtest/daily_book_live_check.py`, `logs/daily_book_live_check.txt`)

Live (combo_final_trades.csv, both accounts): main 1 of 10 won (-$35.18), fresh 0 of 8 (-$34.72), the same signals. Backtest of the same rule (5,064 trades): 34% won, median trade -5.5%, the best 5% of trades carry 135% of the profit; 2025-26 weaker (+3.2% a trade, 27-28% won). Streaks of <= 1 winner in 18 are 9.4% of the backtest's stretches - normal. Not normal: three live trades lost 45-57% (AKE, AIN, JCT) where the backtest has 0.4% of trades below -40%; AIN and JCT are not in the backtest's universe (listed and pumped into the top-40 by volume after the data ends). Earlier fixes (stops, exits, a smaller universe) all failed (doc 02 2026-10-08, `universe_floor.py`). Keeping or dropping the book is the user's call (code freeze to 2027-04-09).

## 2026-11-12 ("they predicted the direction right but not the power - fixed TP / SL is why they failed"): tested on the desk's 10,522 replay calls - refuted (`backtest/direction_vs_power.py`, `logs/direction_vs_power.txt`)

The user's thesis, as a test: take the Analyst desk's calls (4.7-year replay), remove the fixed bracket, and ask (A) did they point the right way more than random entries on the same symbol and side, (B) did the move go further than random, (C) do six exits without a fixed target (no target 24h / 72h, a 3 ATR trail to 72h / 168h, breakeven then trail, a 2 ATR trail) make money. Predictions T1-T5 first; each call had 2 random-entry controls with the same stop and exit. **Per call, direction is no better than random** (24h -0.08% vs -0.05% tune, -0.07% vs +0.05% holdout; right 50-51.5%); the per-bet excess (+0.11..+0.27%, t up to 4.6) is the day-vote trap (one quiet-day call outvotes a crash day's ten). **No under-captured power:** the calls' best move within 24h is SMALLER than random entries' (median 1.55 vs 1.83-1.94 stop-lengths). **Every exit loses per call on both halves** (-0.06..-0.22R); they beat random on the tune half and lose to it on the holdout. The fixed bracket did not kill the desk: its entries are coin flips that pay the fee whatever the exit. T1-T4 right, T5 wrong.

## 2026-11-13 (the Analyst desk 'with proper stops and risk management') - the user: 'it is clearly not random, there is a profitable strategy': written as a rule from the live record and run on 4.7 years - loses on both halves at every risk setting (`backtest/analyst_user_rule.py`, `logs/analyst_user_rule.txt`)

Live (122 calls to 2026-11-13): 23% won vs 18% random, -0.20R a call, book +5.1% (the 3x cap and three shorts). Best groups: stop >= 0.8%, liquidity sweeps, BNB / BTC, shorts - but split at the 2026-11-06 registration, the best group (sweep + stop >= 0.8%: 10 of 17, +1.20R) went 1 of 4 (-0.35R) after it, and the registered wide-stop test is 3 of 16 (-0.30R). Rule fixed before the run: crypto only + SMC + stop >= 0.8% (R0), plus RR <= 4, shorts only, 4h EMA50; risk 0.5 / 1 / 2%, a 3x cap, a 2% day stop. R0: 13.1% / 10.7% won vs 14.1% / 13.3% random, -0.13 / -0.14R a call, negative every year; $300 at 1% -> $12 / $41. Every variant below random odds on both halves; no rule x risk setting above $300 on both halves. Risk management slows the loss, it cannot turn a negative R positive. U1-U4 right, U5 wrong (the day stop helps more than guessed).

## 2026-11-13 (the NASDAQ trader's GOLD pattern as a rule) - the user: 'we have his strategy on gold, can we profit from it': buy after a 2-hour slide / sell after a 2-hour pop loses after costs in every year 2010-2026 (`backtest/gold_fade_stretch.py`, `logs/gold_fade_stretch.txt`)

His gold entries sit at the faded end of the last 2 hours' range (rank 0.661, p 0.002, `his_fade_stretch.py`), but 37 of his 43 gold trades are one day (2026-02-02) and won the race 51%. As a rule on HistData gold minutes 2010-01..2026-09 (checked each quarter hour; bottom / top 10% or 25% of the 2-hour range; exits: his shape +0.08% / -1% / 4h, a +-0.08% race, +-0.25%; 1.5bp a round trip, Exness's spread is ~0.6bp; random entries on the same grid as control): 0 of 6 cells pass, every cell negative per trade in every year. The fade carries a sliver of direction (race 51.7% / 51.0% vs 50.3% / 50.2% random, +0.1..+0.6bp) - a tenth of the cost. His shape wins 79-82% and nets -1.3 / -1.1bp. The positive per-bet t in the log is the day-vote trap. G1-G3 right.

## 2026-11-15 - the Analyst desk's sweet spot, analysed in depth: the live record, a matched random-entry control in R, the forward test's chances, slices, dollars and the 4.7-year replay (`backtest/sweetspot_deep.py`, `logs/sweetspot_deep.txt`)

The user: "I want a detailed analysis of sweet spot signals." Everything on one page, from the live log copied from the VM (`logs/analyst_calls_20261114.csv`: 132 calls, 129 resolved, 57 sweet-spot = stop >= 0.8%, 54 resolved), the desk's cached 4.7-year replay and Binance 1-minute candles. Predictions S1-S5 were registered in the file before the run. An audit script: no tests and no planted-bug round; its one new routine (the random-entry control) reproduces `desk.baseline`'s win rates exactly (same candles, same entry counts) on four brackets.
- **The two samples.** Before the registration (the discovery, now 33 calls / 14 bets with later resolutions): 13 won (39% vs 12% random odds), +0.55R a call, +0.44R a bet [95% -0.26, +1.15], t +1.4. After it (the registered forward sample): 21 calls / 12 bets, 3 won (14% vs 15% random odds), **-0.49R a call, -0.32R a bet [-1.04, +0.41], t -1.0** (two more expired in profit, +1.11R and +1.22R; the 16 losses are -1.06..-1.15R). The discovery's +0.71R over 28 calls would be the 99.3rd percentile of 28-call stretches in the replay: the size expected when the best of ~19 slices is picked, and it regressed.
- **The new piece, a matched random-entry control in R.** Random entries on the same coin, same side, same stop %, target % and hours (every 15 minutes over the desk's live period, scored on 1-minute candles with the desk's rules and the 12bp fee) earn -0.09R a call on the forward brackets (they win 16%, the desk's own logged odds say 15%). Forward excess over it: **-0.39R a call, -0.25R a bet (t -0.8)**; discovery +0.55R a call, +0.54 a bet (t +1.6); all live +0.18R a call, +0.20 a bet (t +0.8) - none significant. **The fee does most of the 'sweet spot':** it costs 0.09R at these stops against 0.57R at scalp-sized ones, and random entries on the scalp brackets lose -0.47R a call; wider stops stop the fee eating the trade, nothing more.
- **The live period paid shorts.** Random shorts on the forward brackets earned +0.41R, random longs -0.40R. The desk's all-live sweet-spot shorts are +0.44R a call (random +0.39R: excess +0.05R, t +0.2); forward longs -0.73R vs random -0.40R, forward shorts -0.09R vs random +0.41R. 'Shorts make the money' was the market, not the signal.
- **The registered forward test:** 12 of 30 bets, bet sd 1.14R (a win +1.4..+1.9R, a loss -1.1R), so t >= 2 at 30 bets needs a mean of about **+0.42R a bet** (the +0.15R clause never binds) and the 18 remaining bets must average **+0.90R**. Chance of passing if the true edge per bet were -0.3 / 0 / +0.2 / +0.3 / +0.5 / +0.8R: 0.0 / 0.0 / 0.0 / 0.2 / 1.3 / 10.1%; averaged over a posterior, **0.0% under a skeptical prior and 0.1% under an enthusiast prior (centred on +0.30R)**. Pace 1.6 bets a day: 30 bets about 2026-11-26. Expect NO PASS.
- **Slices (40 cells, exploratory; the bets are 3-14 per cell).** Forward: no cell positive beyond t +0.4; longs -0.75R a bet (t -3.4, 7 bets, one win in 13); excess over random worst -1.8 (reward:risk 2.5-4). All live: SMC +0.90R a call excess over random (t +2.4, 13 bets) rests on the discovery (forward SMC 1 of 7, -0.68R); SR -0.46R a bet; the best 3 calls are +11.2R of +7.8R: without them -3.4R over 51 calls (-0.07R a call).
- **Dollars (the desk's booking rules, no slippage / funding / lot steps).** Following ONLY the forward sweet-spot calls: $20 at 1% risk $18.03 (-9.8%, fall 10%, 21 calls); 0.5% risk -4.5%, 2% -17.9%; at $10 and 0.5% risk 15 of the 21 calls are under Bitget's $5 minimum. All live sweet-spot calls (the discovery included): $20 at 1% +6.7% (fall 13%), $50 at 0.5% +3.7%.
- **The replay (6,928 sweet-spot calls, 2022-26):** -0.126R a call, hit 16.2% vs 17.5% random; R lost to the hit-rate shortfall -0.063 a call (tune -0.042, holdout -0.098); every year negative per call (2026 -0.163R); by method SR -0.150R (t -4.2 over 1,684 bets), SMC -0.136, FIB -0.036. Stretches of 54 consecutive calls: median -0.14R, 90th percentile +0.16; the live all-time +0.14R sits at the 89th.
- **Predictions:** S1 half right (random R -0.04 all / -0.09 forward against my -0.05..-0.12; forward and all-sample excess within +-0.3R and |t| < 2, but the discovery's +0.54 a bet is outside the band), S2 right, S3 right (best forward slice +0.4; the one large t is negative), S4 right ($18.03), S5 right (-0.49R after vs +0.55R before).
- **Reading:** the sweet-spot signal is not an edge on any measure this repo has: the discovery regressed to a loss, the matched control shows no timing value, the replay says it loses, and the forward test cannot pass at 30 bets. What is true is only that wide stops make the fee cheap. Not found in this definition (stop >= 0.8%, the desk's three rules, 18 days of forward data); the forward test is 'cannot tell' in the strict sense only for edges above about +0.5R a bet. Nothing deployed or committed; the desk keeps logging and the registered scorer keeps counting.

## 2026-11-15 (the liquidation map) - the user: "if we can predict the exact liquidity sweep prices of buyers we can scalp in crypto too with high leverage" -> "Yes, test it": the map finds where forced trading happens, and that does not say which way price goes; no pass (`backtest/liq_map.py`, `backtest/liq_map_fetch.py`, `logs/liq_map.txt`, `logs/liq_map_validate.txt`)

The one sweep idea not yet tested here: an ESTIMATED LIQUIDATION MAP (the idea behind Coinglass's heatmap). Binance's free 5-minute open-interest archive (the hour's last reading, 347 point-in-time top-40 coins incl. dead ones, 2022-01..2026-09, 2.08M coin-hours) rebuilt into a map hour by hour: new open interest booked at the hour's typical price, every contract a long and a short spread over 10x / 20x / 50x / 100x, positions shrunk when open interest falls and removed when price reaches their liquidation price. Every 4 hours the strongest cluster 1-10% away on each side; BIG = the coin's own top fifth over the previous 90 days; a resting limit at the cluster for 24 hours (filled 0.05% through), out after 4h / 24h / a 1.5-ATR stop with a 2R target; 12bp + funding; control = the same order the same distance away at 5 random times of the same coin within 30 days. Rules and five predictions in the file before the run.
- **NO PASS: 0 of 6 cells**, 37,905 events. Clusters sit a median 5.9% (long) / 6.8% (short) away and **fill exactly as often as a random level that far away** (0.97-1.01x on both halves, both sides): no magnet. After the fill **no cell beats the control on both halves** (excess |t| <= 1.9; the short side's holdout excess is negative, -38bp at 4h); the long side loses on the holdout at every exit (-14 / -58 / -45bp), the bracket loses on both halves. MDE80 on the holdout 31-82bp a trade.
- **The map is not blind (post hoc, `--validate`):** on the 60 coins with the longest history, the hour that trades through a CLUSTER carries ~20% more volume than the hour that trades through a random level the same distance away (mean log ratio +0.19 / +0.21, t +13.9 / +15.3; medians 2.45x vs 2.01x the previous 24 hours). So the model does find where extra forced trading (stops, liquidations) happens - and that trading says nothing about the next move: the same finding as the obvious sweep level (`sweep_confluence.py`: real information, ~0 after fees).
- **Leverage:** not tested because nothing survived at 1x; `scalp_1m.py`'s arithmetic stands (the best small edges peak at 4-11x leverage at zero fees; 30-40x wipes them).
- **Predictions:** L1, L2, L4, L5 right; L3 wrong (the short 4h holdout excess is -38bp: worse than random, not inside +-15bp).
- **Limits:** the map is a MODEL (no historical liquidations are published; the leverage mix is assumed; open interest is net); one venue; hourly bars decide fills and exits, so a sweep that fills and reverses inside one hour is scored at the hour's close. A seconds-level version would need tick data the repo does not have for 2022-26.
- **Tests:** `tests/test_liq_map.py` 20; 30 of 30 planted bugs caught over two rounds (first survivors, all gaps in my tests: a short bin at the hour's exact high, the cluster's centre bin, a fill in the reference bar itself, the big-cluster threshold and its history, the month boundary, the open-interest gap reset), the do-nothing control survived. Two of my own slips on the way: a coin whose price history ended before its open interest began crashed the first run (now skipped), and a heredoc turned two `"
"` strings into real newlines (the s3 trap; fixed with the Edit tool). Nothing deployed.

## 2026-11-15 - /goal "find an edge: a perfect combination of every signal, including the Analyst desk's forward data": two walk-forward combination tests, 0 of 39 cells pass (`backtest/combo_meta.py`, `backtest/combo_universe.py`, `logs/combo_meta.txt`, `logs/combo_universe.txt`)

The user set a standing goal: find an edge that gives good signals by combining everything the repo has, the desk's forward data included. Two registered tests (predictions in each file before its run; priors 4% and 3%), because the first one's power check exposed what it could not see.
- **Test 1 - meta-labelling the desk's calls (`combo_meta.py`).** 10,081 replay calls on BTC / ETH / SOL / XRP / BNB (2022-26), each with 55 candle features (returns, ATR, RSI, Bollinger, 24h-range position, distance to the 1000h / daily means, BTC's state, relative strength, breadth, hour, weekday, direction-aligned copies) and, as a second set, the panel's 91 daily signals (funding, positioning, taker flow, open interest, news, tone, unlocks, size / age, fuel, breadth, fear & greed) at the previous day; ridge and a regularised tree; quarterly walk-forward from 2023-01 with a 72-hour embargo; top 10 / 20 / 33% by predicted R. **0 of 12 cells pass.** Selected -0.05..-0.15R a bet against all calls' -0.05; the models that also see the panel do worse (-0.097R, t -1.7); in-sample the same model looks real (selected +0.068 vs -0.057, t +2.2; under the registered within-bet measure +0.454R, t +15.5 against +0.026R out of sample). The raw rank IC of +0.20..+0.25 is mostly an artifact: every loser ends near -1.1R and the small differences are the fee over the stop width, so a model that prefers wide stops scores high; against fee-free R the IC is +0.05..+0.07 and the predictions correlate +0.34..+0.43 with stop width.
- **The first run's gate was blind and the power check said so.** The registered 'uplift per bet' compares selected calls with the other calls of the same day + side, which cancels any skill that works at the level of the market; a planted +0.25R-per-sd skill came out at -0.05R. The gate was amended after that run (selected bets vs all bets, Welch t, selected R/bet > 0 in both halves) and the first-run log kept (`logs/combo_meta_first_run_within_bet_gate.txt`); a test now pins that the new measure sees a market-level skill the old one cancels. With the amended gate and a rank-normal plant a +0.25R-per-sd skill is recovered at only t +1.8: the desk's calls (every one with its own bracket) are a noisy place to look.
- **Test 2 - the clean version (`combo_universe.py`).** The same features and models on a FIXED trade at every 6th hour for the same five markets, both sides, three fixed brackets (1.2% / 2.4% / 24h, 1.2% / 3.6% / 24h, 2% / 4% / 48h): 70,350 candidates each, identical payoff structure, the model only chooses WHEN. All candidates -0.103 / -0.096 / -0.058R (the fee plus a coin flip). Fee-free out-of-sample IC +0.023..+0.055. **0 of 27 cells pass**; P-set cells t -1.3..+1.4; four tree cells with the panel's signals reach t +2.2..+2.3 (G1 top 5%: +0.098R; G2 top 5 / 10 / 20%: +0.111 / +0.088 / +0.075R over all; +0.06..+0.07R in 2023-24 and -0.03..-0.11R in 2025-26; Holm 0.26..0.37): a regime that worked and decayed.
- **The forward data.** Both studies apply every model to the desk's 92 resolved live crypto calls, which no fit ever saw: the models' picks earn +0.16..+0.37R a bet against all -0.04 in test 1 and +0.28..-0.16 in test 2, every |t| <= 1.1 on 13-24 bets. In test 1 the models' picks are 74-80% sweet-spot calls: they re-learned 'prefer wide stops', which is the fee effect (over the replay's out-of-sample years the plain rule 'stop >= 0.8%' is +0.036R above all calls and -0.015R in absolute terms).
- **How far the null reaches.** In test 2 a planted +0.10R-per-sd skill is not recovered (t +0.6) and +0.25R per sd is recovered only partly in test 1: a model with 55-146 correlated signals learns regime noise about as large as a modest real skill. So 'no cell passes' excludes large combination skills (about +0.25R per sd and up), not small ones, and a small one could not be confirmed with this sample either (the standard error of a selected-minus-all difference is ~0.04R a bet).
- **Predictions.** Test 1: M1, M3, M4, M5 right; M2 wrong (raw IC +0.20..+0.25); M6 wrong (not recovered at the registered size, and the registered measure could not see a market-level skill). Test 2: U1, U2, U4 right; U3 half (IC +0.02..+0.055); U5 wrong (the planted skill is not seen).
- **Checked:** tests 20 + 11; planted bugs 40 of 40 (and the later additions) and 15 of 15, a no-op control that survived every round; the first survivors were gaps in my tests (the minimum training size never binding, the random-entry odds being equal for selected and unselected calls, opens that never gapped away from the previous close). Not found in THIS definition (candle and panel signals only, five markets, hourly candidates, three brackets, ridge and a small tree, 2023-26 out of sample); not tested: order-book / tape signals on these candidates, other markets, deeper models, hand-picked feature subsets (picking a subset from these results would be selection on the test).
- **Reading.** The honest answer to the goal as posed: no combination of the signals this repo can see, including the desk's forward calls, produced an edge that survives costs, both halves and a multiple-testing correction. The pieces that do carry money here are the forced-flow books already in forward paper (crash bids, the capitulation buy, the trend book's winners), which a model of candle features cannot find because they are not candle-feature effects. Nothing deployed or committed; no bot or book touched.

## 2026-11-15 (the liquidation map on 1-minute candles) - the user: "test it on 1 minute candles": no pass; the cluster is where forced trading pushes THROUGH, not where it stops (`backtest/liq_map_1m.py`, `logs/liq_map_1m.txt`)

The hourly test (entry above) scored a fill at the hour's close, so a sweep that fills and snaps back within minutes could not show. Every fill of the hourly run (re-collected exactly: 37,905 events, 9,366 cluster fills, plus 19,755 filled controls) was re-scored on Binance's 1-minute futures klines (21,269 coin-days, dead coins included): the fill minute, exits at +5 / +15 / +60 minutes and a scalp bracket (stop 0.5%, target 1.0%, 60 minutes); 12bp + funding. Five predictions in the file first.
- **NO PASS, 0 of 8.** Every primary cell's net is negative on both halves; the scalp bracket loses -20 / -20bp (long) and -18 / -23bp (short) a trade, t -12..-14; no cell beats the same order at a random time (excess |t| <= 1.8).
- **The overshoot (registered M2, right):** within 5 minutes of a cluster fill the price runs a median 0.58% (long) / 0.55% (short) past the level, against 0.48% / 0.48% for random levels the same distance away; 0.5% or more in 55% / 53% of cluster fills vs 49% / 48%. The map marks where stops and liquidations fire, and they push the price through - which is why a tight scalp stop just past the level is the worst place to stand.
- **Deep clusters (8%+ under, registered secondary):** +31 / +35bp at 15 minutes (t 1.6 / 2.1), Holm 0.12, and excess over a random 8% dip ~0: the bounce belongs to the dip (the crash-bid / capit2 effect already running), not to the cluster.
- **Predictions:** M1, M2, M4, M5 right; M3 wrong (the short side's holdout excess at 15 / 60 minutes is -13 / -21bp, worse than random).
- **What the heatmap gives, honestly:** information about WHERE forced trading happens (+20% volume in the hour, +0.1% further overshoot), none about direction. A use that follows from that is execution (keep stops away from clusters; rest bids a little past them), not an entry signal.
- **Tests:** `tests/test_liq_map_1m.py` 8; 15 of 16 planted bugs caught, the survivor equivalent (unfilled rows carry no return and are dropped either way), control survived. Data: `strategy_analysis/data/liqmap_1m/` (gitignored). Nothing deployed.

## 2026-11-15 (orders resting JUST PAST the clusters) - "Yes, test it": the execution use the 1-minute overshoot suggested; no pass, and 'deeper is better' is true of any level (`backtest/liq_map_past.py`, `logs/liq_map_past.txt`)

The one use the overshoot pointed at: rest the order k PAST the cluster (a buy k under a long cluster, a sell k over a short one, k = 0.25 / 0.5 / 1.0%), cancelled 60 minutes after the cluster level trades through, fill 0.05% through its own level; exits +15 / +60 minutes and the same scalp bracket; 12bp + funding; control = the same order past each random level. 18 cells, Holm; six predictions in the file first. Parity: k = 0 reproduces the 1-minute study on all 29,121 rows.
- **NO PASS, 0 of 18.** Longs: +1.5..+22bp on the tune half, -12.7..+0.2bp on the holdout, no excess over random levels at t 2 on either half (largest long 1% 60m +17.2bp tune / -16.4bp holdout). Shorts lose everywhere (-12..-35bp), worse than random on the holdout (-16..-48bp). Every scalp cell -16..-26bp.
- **The overshoot barely changes the fills:** over the hour the order past a cluster fills 1-3 points more often than past a random level (k 0.5%: 73.4% vs 71.8% long, 74.6% vs 72.7% short).
- **'Deeper is better' is any level, not the map (post hoc):** per order placed the long side improves with depth (tune -0.4 -> +12.2bp, holdout -13.8 -> -2.9bp, so P5 was wrong on the tune half), and the random levels show the same slope (holdout at k 1%: -2.9bp both) - a deeper order trades less and pays fewer fees. At a maker entry (~8bp) the long 15m cells read +0.4..+4.2bp on the holdout: noise.
- **Deep longs (8%+ under, k 0.5%, registered secondary):** +56 / +43bp at 15 minutes (t 2.2 / 2.1, Holm 0.03), only +20 / +22bp over random 8%+ dips (t 0.5 / 0.8; MDE80 53bp): the dip again. The crash-bid book already trades it; an excess under ~50bp cannot be seen in 418 trades.
- **Predictions:** P1-P4, P6 right; P5 wrong. **Verdict on the heatmap:** it locates forced trading and nothing usable follows - not an entry (two tests), not an execution edge (this one). Closed.
- **Tests:** `tests/test_liq_map_past.py` 10; 17 of 17 planted bugs caught (two first survivors were gaps in my tests: no short row scored, the scalp's holding cost unchecked), control survived. `liq_map_1m.exits_from` split out of `minute_trade` for reuse; the 1-minute log and table reproduce exactly. Nothing deployed.

## 2026-11-15 (the liquidation map INSIDE the liquidity sweep) - "find me a new strategy from it then or integrate it in liquidity sweep": the one factor the sweep study could not test, now tested; it makes long sweeps worse (`backtest/liq_sweep.py`, `logs/liq_sweep.txt`)

`sweep_confluence.py` (2026-10-30) listed open interest / liquidation volume at the sweep as untested for lack of hourly data; the map work put it on disk. Its own 43,846 sweeps from 2022-02 (43,500 kept, its trades, controls and split), two factors read at the sweep bar's close: **liq** = what the map says the wick liquidated (share of open interest) and **flush** = the REAL fall in open interest during the sweep bar. Stage 1 as in the sweep study (tune 2/3 cut, spread vs unflagged, Holm over 4); PASS for 6 subsets (each factor and both, per side): net > 0 with t >= 2 on both halves, >= 100 holdout trades, spread over the unflagged sweeps > 0 with t >= 2 on both halves, Holm. Five predictions first.
- **NO PASS, 0 of 6; stage 1 0 of 4.** Long sweeps that cleared more leverage do WORSE: spread liq -17 / -7bp, flush -8 / -4bp, both -25 / -13bp; flagged long subsets net -12..-31bp a trade. The SMC story (stops run, sellers gone, the reclaim holds) is not in the data.
- **The one positive cell:** short sweeps where open interest fell during the up-wick (shorts forced out) - spread +11 / +15bp (t 1.2 / 1.5, Holm 0.26), net +3 / +6bp a trade. Under every bar.
- **S2 wrong, and why it matters:** the map's 'liquidated' figure and the real open-interest fall are nearly unrelated (rank +0.07 long, -0.04 short). Post hoc, the map's figure is mostly the wick's depth in ATR (+0.60 / +0.58) - a factor the sweep study already tested (F1, not confirmed). The heatmap model re-measures wick depth.
- **Predictions:** S1, S3, S4, S5 right; S2 wrong. **Tests:** `tests/test_liq_sweep.py` 10; 20 of 20 planted bugs caught, control survived. Nothing deployed. The liquidation map is closed as an entry, an execution trick and a sweep filter.

## 2026-11-15 (forex: round-number order clusters, Osler) - the user: "I see an edge in forex too and we need to discover it, whatever it takes": a REAL forex effect, the first this repo has found, and the Standard account's spread eats it (`backtest/fx_round_levels.py`, `backtest/fx_round_breakout.py`, `logs/fx_round_levels.txt`, `logs/fx_round_breakout.txt`, `logs/fx_round_breakout_ticks.txt`)

The one documented forced-order mechanism in forex never tested here: Osler (2003 / 2005, a dealer's real order book) - take-profit orders cluster AT round numbers (price should stall there), stop-losses just BEYOND them (price should run once through). HistData 1-minute bid bars 2007-2026, 7 majors; round = the big figure (every 100 pips), CONTROL = the same event at arbitrary levels (big figure + 23 / 37 / 63 / 77 pips), so momentum / reversal / time of day cancel and the round-minus-control EXCESS is the order cluster. Predictions in each file first; t over pair-days; 60 / 40 by time.
- **First run (`fx_round_levels.py`), 0 of 6 cells pass, but the excess is real on both halves:** after a close crosses a big figure the next 5 / 15 / 60 minutes run +0.2 / +0.5 / +1.0bp further in the crossing direction than at arbitrary levels (t +5..+9, both halves); fading the first touch of a big figure loses 0.7-1.6bp MORE than at arbitrary levels (t -7..-10): the price runs THROUGH round numbers, it does not bounce off them. Stable in 2007-11, 2013-17, 2019-26 (+0.51 / +0.39 / +0.45bp at 15 min), 6 of 7 pairs (NZD / USD flat). O1, O3 right; O2 WRONG (no take-profit reversal - the stop half only); O4 wrong (no decay since publication).
- **The trade that sits on it (`fx_round_breakout.py`, post hoc, registered before its run):** a stop order at the big figure +- 0.5 pip on the first touch in 60 minutes, out at +15 / +60 minutes. Bars: gross from the trigger +0.9 pips (15 min) / +1.1 pips (60 min) on both halves, arbitrary levels +0.0..+0.1; shorts (exact on bid bars) +1.23..+1.27, longs +0.96..+1.05. Net of 1.2 pips per trade -0.2 / -0.25bp (60 min) - no pass on bars; at 0.6 pip +0.34 / +0.36bp. ~2,270 trades a year across the 7 pairs. B1, B2, B3 right.
- **On Exness's own ticks, 2026-01..11 (`--ticks`, the order simulated tick by tick, long on the ask, short on the bid, real spread and slippage):** the excess replicates (+0.59 pips at 15 min, +1.07 pips at 60 min over arbitrary levels) and the trade loses: -1.01 / -0.57 pips a trade (t -3.5 / -1.1, 1,741 / 1,732 trades), -0.49 / -0.23 with fills at a spread over 2 pips skipped. The spread at these moments averages 1.78 pips on the Standard 'm' symbols (EURUSD 0.87, USDJPY 3.2 incl. rollover blow-outs), slippage past the trigger +0.17 pip. By pair at 60 min: EURUSD +0.87, USDJPY +0.81, the other five -0.9..-1.8 (post hoc, ~250 trades each). B4 half wrong (spread 1.78, not 0.8-1.5; slippage and the negative net right).
- **Reading:** the round-number stop cascade is a real, stable, 19-year forex effect worth about +1 pip a trade over an hour - the size of a retail round trip. It is tradable only where the all-in cost is under ~0.8 pips (a Raw-spread / zero account on EURUSD-class spreads, unverified for the user) and then worth ~+0.3bp a trade. A LEAD conditional on cost, not money.
- **A bug of mine, found before reading the tick result:** the first tick simulator re-armed on any tick between the level and the trigger and found ~0 trades; fixed (the first touch arms a resting stop for 60 minutes), a regression test added. Tests: `tests/test_fx_round_levels.py` 12; planted bugs 8 of 8 caught on the bar code (first round 4 survivors, all gaps in my tests), control survived. Nothing deployed or committed.

## 2026-11-15 (later) - /goal, round 2: a screened model, direction-only features, a per-call re-score, one lead, and no transfer to 284 unseen coins (`backtest/combo_screen.py`, `combo_direction.py`, `combo_rangerev.py`, `combo_rowcheck.py`, `combo_ridge_dissect.py`, `combo_wide.py`)

The first two combination tests (`combo_meta.py` 0 of 12, `combo_universe.py` 0 of 27) were weak nulls: their power check could not recover a planted +0.10R-per-sd skill. This round tried to fix the instrument before concluding anything. Every file has its predictions registered in the docstring first and its RESULT block after.

- **A screened model (`combo_screen.py`, 18 cells):** keep the 8 features most correlated with the clipped outcome inside each training fold, fit a small ridge. 0 of 18 pass; the planted +0.10R / sd skill is recovered as +0.025R (a perfect sort would give +0.175R). The screen keeps REGIME-LEVEL features (side, atr_pct, bb_w in 16 of 16 folds) that flip out of sample. V1 wrong.
- **Direction features only (`combo_direction.py`, 13 features that point one way, ridge and boosting, 18 cells):** 0 of 18 at the bet level (smallest p 0.0071; Bonferroni over the 63 cells tried on these candidates 0.446). Its post-hoc diagnostics printed one thing that looked like an edge: `-a_rng_pos24`, top 10%, selected +0.051R vs all -0.097R = +0.147 (t +4.5, both halves).
- **That +0.147 was an artifact (`combo_rangerev.py`):** the feature is not centred (position in the 24h range is in [0, 1], so negated and 'aligned' it is >= 0 only for shorts): the selection was 100% shorts, compared with an all-sides baseline in a period when shorts out-earned longs (-0.079R vs -0.115R), and the bet (UTC day + side) mean is a DAY-VOTE mean (CLAUDE.md s3). The clean symmetric reversal per call is -0.157R vs -0.096R same-side, matched excess -0.067..-0.071, deciles falling with the score (Spearman -0.79), circular-shift p 0.983. There is no range-reversal edge. W4 (no single feature clears +-2 se) was wrong, and the way it was wrong was the repo's own day-vote trap, reproduced inside a study built to avoid it.
- **The gate itself was the wrong instrument (`combo_rowcheck.py`):** re-scoring all 36 screened / direction cells PER CALL (selected calls vs all calls of the same side, weekly-cluster t, circular-shift null): 0 of 36 have a selected mean >= +0.05R in both halves, and the per-call excess is LARGER than the per-bet excess in 32 of 36 (K2 wrong): the day-vote gate hid a signal rather than inventing one. One cell stands out, the best of 36: G1 (1.2% stop / 2.4% target / 24h, a fixed trade every 6th hour on BTC ETH SOL XRP BNB, both sides, 12bp), the ridge on the 13 direction features, top 5% of each quarterly fold: **selected +0.051R vs -0.084R for all same-side calls = +0.135R, weekly-cluster t +3.1, shift-null p 0.002.**
- **Dissected (`combo_ridge_dissect.py`):** the lead survives the checks meant to kill it - matched to quarter x hour x volatility +0.149, shift p 0.007 on the matched excess, prediction deciles monotone (Spearman +0.94; decile 10 +0.010R, decile 1 -0.180R), coefficients sign-stable (1 of 13 unstable), and the per-call power check now recovers a planted +0.10R / sd as +0.224R (t +4.9; placebo -0.008) - so the per-call score has the power the bet-level gate lacked. What it IS: 85% shorts (88% of the excess) of coins weak against BTC over a week, RSI-low, below their Bollinger band: trend-continuation shorts, i.e. the 2023-26 alt bleed. Where it breaks: the absolute mean is only +0.051R = +6bp a trade after the 12bp fee; +0.080 in 2023-24, +0.019 in 2025-26, 2026 -0.010, 2026Q3 excess -0.20; the best 20 of 191 weeks removed leave -0.007R; 6bp of slippage takes the majors' selected mean to +0.001R; G2 / G3 brackets give +0.091 / +0.045.
- **Out of universe (`combo_wide.py`):** the same rule on every perpetual outside the five that was in the point-in-time top 40 by the prior month's volume (360 coins incl. delisted, 553,006 candidates, 284 coins and 318,014 calls out of sample). **(A) the ridge trained on the five majors only: selected -0.108R vs -0.082R same-side = excess -0.026 (t -1.1), 2025-26 -0.158R, shift p 0.83. (B) a ridge trained on the wide coins: selected -0.042R, excess +0.018 (t +0.6, p 0.124).** G2 / G3 frozen: -0.003 / +0.001. The same code path reproduces the majors' +0.051 / +0.135. The lead does NOT transfer. Funding was not charged (it would flatter the shorts by about what it pays them).
- **The desk's forward data:** the 92 live calls, picks by every model of both rounds: |t| <= 1.1 (bet level), selected means indistinguishable from all calls; nothing there.
- **Reading:** no tradable edge found. The strongest per-call signal in any of the combination tests is a relative one (+0.135R) on five coins in a bearish-alt regime, worth +6bp a trade absolute before slippage, decaying to ~0 in the last 18 months, best of 36 cells after 63 bet-level cells on the same candidates, and absent on 284 coins it never saw. The method lessons: (1) a gate that averages per day-and-side is a day-vote mean even when the study was designed against it - print the per-call mean beside every selected-vs-all difference and use the SAME-SIDE baseline for a selection that is one-sided; (2) a feature meant to point one way must be centred before it is 'aligned' by the side; (3) a power check must be run on the metric that will be read, not on its cousin - the bet-level check said the pipeline was blind, the per-call check said it was not; (4) a relative edge is not an absolute one: always print the selected mean next to the excess.
- **Predictions (all in the file docstrings):** combo_screen V1 wrong, V2, V3, V5 right, V4 half; combo_direction W1 wrong, W2, W3, W5 right, W4 wrong; combo_rangerev R1, R4, R6 right, R2, R3, R5 wrong; combo_rowcheck K1 right, K2, K3 wrong; combo_ridge_dissect D1, D3, D6, D7 wrong, D2, D5 right; combo_wide E1, E3 wrong, E2, E4, E5, E6 right.
- **Checked:** `tests/test_combo_wide.py` 18 tests (hand cases for the contiguity filter, eligibility by month, the first-episode cut, the frozen model's embargo and future-label immunity, the centred reversal score, selection per quarter and side, the same-side control against a side drift, the matched strata, the shift-null on a planted and a random selection, the per-call weekly-cluster t by hand); planted bugs 37 of 37 non-equivalent caught across combo_wide / combo_rangerev / combo_rowcheck / combo_direction / combo_screen, the no-op control survived (the first round left 2: one a test gap, fixed with a contrived hole case; the other the redundant second length guard in `load_perp`, equivalent). Nothing deployed or committed; no bot, book or doc 22 line touched. The goal as posed ('an edge that gives good signals') is NOT met.
- **Round 3 (`backtest/combo_rowcheck2.py`, same day): the 27 cells of round 1 (ridge / boosting on 55 candle features, and boosting on those plus the panel's funding / positioning / taker / open-interest / news / unlock signals) re-scored PER CALL against a bar fixed in advance (excess >= +0.08R, t >= 3, selected >= +0.05R in both halves, shift p < 0.01, then the out-of-universe test).** 0 of 27 have a selected mean >= +0.05R in both halves; the best is +0.107R excess (G1 ridge P top 5%: selected +0.025R, 2025-26 +0.008, shift p 0.005 = 0.31 over 63 cells); adding the panel signals changes nothing (-0.001R paired over nine cells). The best cell frozen on the five majors and applied to 284 point-in-time perpetuals: excess +0.040R (t +1.6, shift p 0.010) with a selected mean of -0.034R (-0.117R at 10bp slippage): a small relative tilt toward trend-continuation shorts, negative in absolute terms. L1-L4 all right. **The desk's own 10,081 replay calls, per call with a stop-width-matched control (`backtest/combo_rowcheck3.py`):** 0 of 12 cells; every selected mean is negative (-0.12..-0.18R); the matched excess (same quarter x rule x side x stop tercile) is on average 0.06 of the plain excess over all calls and at best +0.052R (t +1.6): the earlier ranking skill was the wide-stop / cheap-loser tie-break. M1-M3 right. No model class or information set tried (candle features, the panel's positioning / funding / news signals, screened or direction-only, ridge or boosting, on the desk's calls or on fixed trades) produces an edge that survives per-call scoring, a same-side baseline, and a universe it has never seen.
- **At the user's account (Standard, 2026-11-15):** median spread at the fill 0.8 (EURUSD) .. 1.5 pips (USDCAD). Tick result with fills at a spread of 1 pip or less skipped-above: 60 min -0.51 pips a trade (t -1.0, 908 trades), 15 min -0.63 (t -2.4); only EURUSD is positive, +0.87 pips (t +1.0, 207 trades; +0.60 with the spread filter) - one pair of seven, picked after looking. Retail-account verdict: not tradable on Standard; the edge sits at the cost on every Exness account type checked by arithmetic (Raw / Zero commissions ~0.7 pip a round trip, unverified). Only a forward record of the EURUSD version could say more.

## 2026-11-15 (the map of what works) - "create a map or mapping of all the things that works, connect them, align them": three families, each owning a market; the live accounts sit in the map's worst corner; the liquidation map adds nothing to capit2 (`backtest/works_map.py`, `backtest/liq_capit.py`, `logs/works_map.txt`, `logs/works_map.json`, `logs/liq_capit.txt`; page: the "What Works Map" artifact)

Not a test that passes or fails a book: every book that survived, on one calendar (the final machine's nine as deployed, the mean of the 10 orderings, trend gains shrunk 3x; plus crowd x1.0, RSI-80 at 1% risk and NASDAQ noise at 1x), cut by the market state of each day (BTC bull / chop / bear by its 50-day rule, the fuel gauge's LOW / MID / HIGH, the median top-40 alt's 30-day move), with weekly correlations, the worst and best weeks, and which signal predicts which book's next 30 days. Five expectations registered first.
- **Three families, low correlation between them (+0.04..+0.19 weekly; post hoc grouping):** MOMENTUM (trend, daily, RSI-80) earns when alts run (fuel HIGH +1,324%/yr, annualised mean day at machine weight) and loses in BTC bears (-103%) and deep alt bleeds (-31%); FORCED FLOW (sleeve, capit2, news, crowd, crash bids) is the mirror (bear +174%, deep bleed +192%); NEUTRAL / CARRY (market-neutral, carry, NASDAQ dip, NASDAQ noise) is steady except the market-neutral book in a deep bleed (-31%). The only real overlaps: daily ~ RSI-80 +0.43, market-neutral ~ crowd +0.38.
- **The machine's one losing state is BTC bull while the alts do not run** (BULL + fuel LOW): 75 days in 10 short episodes (3-17 days), -22.6% summed, trend -33.5%, everything else +10.9%. Every other state is positive on both halves, including chop (+170%/yr) and bear (+123%).
- **The signals that work all point at momentum:** fuel, BTC vs its 50-day average and the alt median predict the trend book's and the machine's next 30 days on both halves (rho +0.21..+0.45); nothing predicts the forced-flow books, which fire on their own events.
- **The live tape is the map's worst corner (post hoc):** BTC labelled bull with low fuel to 10-22, then a -33% median alt bleed under a chop label (fuel LOW, Fear & Greed 10, BTC $65,410 on 2026-11-15). In deep bleeds (331 days) the machine still earned +125%/yr, carried by capit2 +85%, sleeve +55%, crowd +54%, news +23%, while market-neutral (-31%) and daily (-16%) lost - and those two are the main account's biggest live losers (-$34.02, -$35.10; 3.6x and 7x the mapped rate over 37 days). Two of the carriers are idle for structural reasons: the sleeve needs a BEAR label the 50-day rule has not given, and the news book has had no qualifying Binance notices. Capit2 (+$6.83) and carry (+$9.91) earn as mapped.
- **The liquidation map aligned with capit2 (`liq_capit.py`, the one working book that trades forced selling; three factors at the signal, registered first):** 0 of 3 confirmed (Holm 0.77). Capit2 on the 743 trades kept from 2022-02 nets +1.95% / +4.22% a trade (92% won) and on the holdout every tercile of every factor earns about +4%: nothing to separate. The REAL open-interest fall over 24 hours leaned the right way on the tune half (+2.0% a trade spread, t 1.6), flat on the holdout. The map's own flush figure runs OPPOSITE to the real open-interest fall (rank -0.28, C2 wrong): the model shrinks every position when open interest falls, so it measures leverage that was built and then wicked, not leverage that left.
- **Expectations:** W1 wrong (bear, not chop, is the machine's weakest BTC state; 11 of 12 books earn in chop), W2 wrong by one pair (daily ~ RSI-80 +0.43 is over the +0.40 line), W3, W4, W5 right. capit2 x map: C1, C3, C4 right, C2 wrong.
- **Tests:** `tests/test_works_map.py` 6 (9 of 9 planted bugs after four test gaps were closed), `tests/test_liq_capit.py` 6 (10 of 10); controls survived. Nothing deployed or committed; no bot changed (code freeze to 2027-04-09).

## 2026-11-15 (shifting weight from momentum to forced flow when the alts bleed) - "Yes, test it": earns where it should, loses to sizing the whole machine up; no pass (`backtest/flow_shift.py`, `logs/flow_shift.txt`)

The map's suggestion, tested against the bet-bigger line (the base x k at the same biggest fall, typical $300 year, both halves). Bleed = the median point-in-time top-40 alt down 15%+ over 30 days (28.8% of days). Weights never read after the outcome: per trade at entry for capit2 (leverage x weight, liquidation at that leverage) and news (stake x weight); per day from the open's state for the marked-to-market sleeve, crash bids, daily book and crowd book, with 6bp x the change in weight x gross on flip days. The trend book stays x1 (cutting it was already tested: runner_gate.py, alt_bear.py). Parity: all weights 1 reproduce the cached machine exactly. Five predictions first.
- **NO PASS.** V1 forced flow x2 in a bleed: -$1,033 / -$547 against the line (tune / holdout). V2 + the daily book x0.5: -$796 / -$313. V3 the crowd book only in a bleed: -$579 / +$2,773. V4 all of it: -$686 / +$3,348. Every judged variant loses on the tune half.
- **It earns where the map said** (V2 minus the base: +103% of the account summed over the tune half's bleed days, +43% over the holdout's) **and pays for it in the tail:** worst month -19.2% -> -26.4% (tune), -31.3% -> -38.5% (holdout); capit2 at 4x has 51 of its 878 bleed-day trades (5.8%) liquidated. Raising the whole machine to the same fall earns more - the trend book's convexity, not the forced-flow books, is the best use of extra risk.
- **The one row that clears the line on both halves is the reference:** the crowd book held always (+$535 / +$4,101) - `crowd_combo.py`'s 2026-10-23 finding again; it is a paper lead (live in the fresh account: -$24.51 so far), verdict 2027-04-09.
- **Printed, not judged:** x1.5 instead of x2: -$220 / +$2,017 (1.9% of raised capit2 trades liquidated); the bleed line at -10%: worse on both halves; at -20%: tune negative.
- **Predictions F1-F5 all right.** Tests `tests/test_flow_shift.py` 7; planted bugs 11 of 11 (three first survivors were gaps in my tests), control survived. Nothing deployed or committed; no bot changed.

### 2026-11-15 - the daily breakout book: backtest vs forward test (`backtest/daily_live_vs_backtest.py`, `logs/daily_live_vs_backtest.txt`)

The user: "check if there is a discrepancy between the daily breakout backtest and the forward test, and what we are doing wrong".
Live: main 10 closed trades, 1 won, -22.1% a trade; fresh 8, 0 won; AKE -45%, AIN -57%, JCT -56%.

- **The code is the backtest's.** `daily_combos.gen`'s rule replayed on Binance daily bars over the live weeks, on the backtest's universe
  rule (the November top-40 matches the live pool 40 of 40): 16 of 18 live trades are replay trades with the same entry and exit day;
  prices within 1% except JCT (+2.3%, filled 1.5 minutes into a pump) and fresh's first BTW (+1.4%, the account started 01:15); replay
  -22.7% vs live -22.1% a trade on main. IOST (taken) and RAYSOL (missed) are the pre-2026-10-22 24h-volume universe, already fixed.
- **One convention differs:** the live bot reads the NEW month's top-40 for the last close of a month, the backtest the signal bar's month.
  AIN (2026-11-01, -57%) exists only under the live convention. Over history the live convention is no worse (per trade: holdout
  +0.6..+0.9 points better at all 3 day boundaries, tune mixed). Not a fault; not changed.
- **The data hides nothing:** the panel's 120-bar rule drops 12 top-40 coins (0.8% of coin-months, mostly 2026-08 stock tokens);
  the rule's 7 trades in them: -3.7% a trade, none under -40%. The three live losers are not new listings (363-478 days on Binance
  futures): older small caps that entered the top-40 on pump volume. Trades under -40% are not more common in young coins (0.3% vs 0.5%).
- **The run is outside the backtest:** 10 consecutive backtest trades averaging <= -22.1%: 0.59% of runs, none since 2025 (worst since
  2025 -20.4%); 3 trades under -40% in 10: never.
- **Post hoc: a 20 / 25 / 30 / 35% disaster stop** (daily low, filled at min(open, level)) removes every -40% loser and lowers the
  per-trade mean on both halves at all three boundaries (e.g. 0h: tune +8.34 -> +6.85..+7.83%, holdout +2.03 -> +1.19..+1.77%): the
  book's pump winners wick through the stop and recover. Same verdict as the 2xATR stop (`daily_combos.py`).
- **Predictions:** Q1 right on trades (2 fills > 1% off), Q2 right, Q3-Q5 wrong. Audit script, no tests (parity: the patched-panel run
  reproduces `gen(0)`'s 1,692 trades exactly). Nothing deployed or changed.
- **Reading:** nothing is wrong in the bot. What is weak is the book's evidence: it was picked after looking at the holdout and its holdout
  rests on 5 pump trades (2026-10-08 entry above). The forward test is showing that fragility; it is judged at the machine's dates (doc 22).


## 2026-11-15 (the works map's states on the Analyst desk) - "add our findings to the analyst desk in any way that improves the signal": following the market's state makes the desk worse; going AGAINST it is a little better (post hoc), now a tag with a registered forward test (`backtest/analyst_states.py`, `logs/analyst_states.txt`, `analyst.py` amendment of 2026-11-15)

The desk's 9,830 crypto replay calls (2022-02 .. 2026-09, `analyst_replay.py`) scored by the market states of `works_map.py` (BTC label, fuel, the median top-40 alt's 30-day move; known at each day's open), as hit rate minus each call's random-entry odds, a bet = same day and direction, halves split 2024-12-07. Four gates registered first (G1 follow the family states, G2 follow the BTC label, G3 no shorts in a deep bleed, G4 FIB only in momentum states, SR / SMC outside them).
- **No gate improves or pays (Holm 0.63-1.00).** Following the state made the calls WORSE: G1 -3.7 / -3.8 points (t -2.5 / -2.0), G2 -3.8 / -3.0. G3 helped on both halves (+3.6 / +7.3, t 1.0 / 2.4) but not significantly on the tune half. Deep-bleed longs hit 3.4 points over random; deep-bleed shorts 6.0 under.
- **Post hoc, the inverse of G1 - calls AGAINST the market's state** (a long while few alts run or the median alt is down 15%+ in 30 days; a short while the alts are not bleeding and BTC is not bear) - beat the rest by +3.7 / +3.8 points (t 2.5 / 2.0), in every year 2022-26 (+1.5..+4.0), inside the sweet spot +3.8 / +3.0. They still lose -0.16 / -0.23R a call: a better signal, not a profitable one. The desk's three setups are reversal trades; they work a little better against the crowd's direction, which fits the forced-flow family.
- **Built (not deployed):** `analyst.py` records each call's market state (BTC label from its closed daily bars; fuel state and the median alt's 30-day move from `logs/mood/mood.json` when under 6 hours old) and its LEAN ('against' / 'with'; gold and QQQ none), with a dated amendment and a REGISTERED forward test (`lean_test`: calls from 2026-11-15 14:00 UTC, after 30 bets of each lean, PASS if against minus with > 0 with Welch t >= 2). The feed carries the state and the lean; the Analyst tab shows a 'Market mood now' line, a with / against badge on the pick, and the record; the bot's pick prefers an 'against' call. No rule, call or the paper book changed.
- **Predictions:** S1-S3 right, S4 wrong (G2 kept 28%). Tests: `tests/test_analyst_states.py` 6; desk 36 (5 new), feed 45 (1 new), size panel 26 (1 new); planted bugs 17 of 17 + 3 of 3 + 3 of 3 (three first survivors were gaps in my tests), controls survived; every changed file compiles on the VM's Python 3.10.12; `next build` passes; checked in a throwaway local copy on the live feed (one made-up long added to see the 'against' path: it became the pick; no console errors; generated password and files deleted, launch.json restored). Pre-existing, not from this change: the top bar's 'Market mood · F&G' link pushes the page 16px wider than a 375px phone.

## 2026-11-15 (following the Analyst tab's graded signals) - "if I follow these signals how will it perform and how often should I get strong signals": every grade loses on the replay; Best setups come ~14 a week in clumps (`backtest/analyst_grades.py`, `logs/analyst_grades.txt`)

The desk's 4.7-year replay (crypto, 9,830 calls, 2022-02 .. 2026-09, hourly scoring, 12bp) graded the way the rebuilt tab grades (`gradeCall`: Best = stop >= 0.8% + against the mood; Weaker = stop >= 0.8% with the mood; Skip = tighter stop), and a $100 account following every call of a grade, entry-sized and compounded by close date.
- **Best setup: -0.141R a call (-0.122 / -0.175 by half), hit 15.9% vs 15.4% random, -0.027R a bet (t -0.8); negative every year 2022-26.** Weaker: -0.117R; Skip: -0.311R (t -5.6). The grade separates bad from less bad; it does not separate winners. The mood raises the hit rate over random but Best setups start from lower odds, so per call they lose about as much as Weaker ones.
- **Following them:** $100 at 1% a call -> $4.87 / $10.45 (falls 96% / 91%); at 2% -> ~$0; at 1% per BET (split across the coins that fire together) -> $100.32 / $64.69 (falls 32% / 44%). The days when several coins fire together lose most, so never risk 1% on each of them.
- **How often:** 13.9 Best setups a week (median 13), ~2.8 coins at once on the days they fire, ~5 independent bets a week, almost every week. E1, E3 right; E2 wrong (expected 1-2 a week).
- **Live so far:** ideas with room 13 test bets at -0.16R a bet; the whole desk 134 ideas, 22% hit vs 30% needed, -0.21R each. Nothing changed on the page or the desk.

## 2026-11-15 (CORRECTION, after the user asked "are you sure 'with market mood' means not good?") - in money, the mood makes no difference; the 'against' edge was the random baseline, not the calls

Re-checked on the same replay (crypto, 9,830 calls): ideas against and with the mood hit the take-profit EQUALLY often (all stops: 18.6% vs 19.0% tune, 17.0% vs 16.8% holdout; stop >= 0.8%: 16.9% vs 17.0%, 14.1% vs 15.2%). What differs is the random-entry baseline: going with the mood a random entry does better (about 21% vs 18%) because the market already drifts that way, so 'with' ideas look worse AGAINST THEIR BASELINE while earning the same. In R: stop >= 0.8% against -0.122 / -0.175 a call, with -0.106 / -0.133; against minus with per bet +0.006 (t 0.1) / -0.056 (t -0.7); all stops +0.034 (t 0.6) / -0.028 (t -0.4). By side, shorts WITH the mood (shorting falling alts) were the least bad group (-0.093R a call). So `analyst_states.py`'s post-hoc '+3.7 / +3.8 points' is real as a measure against random entries and USELESS for money; the deployed grade (Best = against, Weaker = with) and the pick's preference for 'against' are not supported. The registered `lean_test` stays (it measures what it registered); the page should not present the tag as better. **Fixed and deployed the same day (`e79dec5`, the user: 'yes, fix it'):** the tab grades on stop size and price position only ('Has room' / 'Skip'), the mood is a neutral context chip, the pick is the newest idea with room; analyst.py's amendment carries the correction.

## 2026-11-21 (the crash post-mortem) - "keep the paper bots running but can we learn something from these days": the account was not a market bet; its whole record is below every backtest window with the same market move; the crash books had no flushes to feed on (`backtest/crash_lessons.py`, `logs/crash_lessons.txt`; first run `logs/crash_lessons_first_run.txt`)

Read-only. Copies of both final-machine accounts' logs (2026-11-20 ~21:00 UTC), Binance daily and 4h bars, the backtest's own books (`alt_bear_books.pkl`, 10 slot orderings, + works_map's news and NASDAQ series = the 9 books at the live weights; trend gains shrunk 3x, losses raw). Predictions L1-L6 registered before any number, L7-L10 after Parts A-B, D1-D2 before Part D.
- **Not a market bet (A1, A2).** Main's placeable crypto ledger (rebuilt from `combo_exec.csv`, equal to the bot's `exec.virtual_pos` coin for coin) was net SHORT: -0.26x before 11-10, -0.11x in the crash (gross 1.6x / 1.1x), beside a NASDAQ long (QQQ +0.42x / +0.28x). Daily beta to the point-in-time alt index -0.01 over 33 days; on the worst alt day (11-14, -11.1%) main made +2.3%. The -25% came from which coins were held. L1, L2 wrong.
- **Outside the backtest over the whole record (C2).** Main's 42 days (BTC -24.2%, the alt index -28.7%): -24.9%, below every one of the 890 backtest windows with the same BTC and alt moves (+-5 / +-7 points; 15 start months: 2020-03, 2021-05, 2021-10..12, 2022-03 / 08 / 11, 2024-07, 2025-10..12, 2026-01 / 04 / 05). In those windows the machine made a median +23.1% and lost in 25% (worst -24.1%). Fresh, its crowd book taken out: -29.5% against a median +29.1% (below all 680). Phase by phase it looked like 1 in 10 - the October bleed -16.6% (8th percentile of its 2,180 matched windows), the crash -10.0% (10th of 410) - but two such phases in a row are not in the backtest.
- **The gap by book** (whole record, live vs the matched median, % of the $300 start): market-neutral -11.8 vs +5.1 (9th percentile; October alone -12.7% = 3rd), daily -11.7 vs -4.6 (8th), capit2 +0.7 vs +9.7 (16th), sleeve -5.0 vs +1.6 (0th), NASDAQ dip-buy -5.2 vs +1.3 (0th), crash bids -0.1 vs +1.3 (3rd); trend +0.3 vs -3.4 (76th - its shorts paid +8.5% of the account in the crash), carry +3.3 vs +1.0 (69th, then switched off by Bitget's $5 minimum from 11-13). The live by-book figures come from the feed at 11-20 21:00 UTC, a day past the windows' last bar, and 11-20 was a -5.7% BTC day: the sleeve's -5.0 includes -4.2 points from that day alone (its booked marks to the 11-19 close are -0.7). The 890 windows are overlapping cuts of about 15 distinct episodes, so 'below all of them' means worse than the worst of ~15 comparable crashes since 2020, not 1 in 890.
- **capit2 is faithful (D).** Its rule replayed with the bot's own `final_books.capit_signals` on Binance 4h bars gives exactly the 3 trades the bot took (SOL, ADA, FIL at 11-14 20:00; same limits, same exits): 11 RSI-under-20-on-volume hits in 257 bars, 5 with a 10% drop, one wave of 6 coins. The backtest's capit2 also closed trades on a median 2 days per matched window (D2 wrong) - its crash waves paid more. This decline had fewer flush days: 4 days of -5% or worse on the alt index against a median 6 in the matched windows (10th percentile 5); worst day -11.1% against a median -13.2%.
- **Market-neutral (A3, B1).** Live, the long names fell more than the short names in 5 of 6 weeks; the first two baskets' longs had run up +134% / +110% in 30 days. In the backtest's 252 crash weeks (a rebalance with BTC >= 20% under its 60-day high and >= 15% down in 30 days; 25 months) the blend loses too, -0.93% a week, 61% of weeks, on both halves (-0.85 / -1.08) - but from the OTHER leg: last month's losers (its shorts) bounce +1.95% a week, the textbook momentum crash. Weeks with the most-pumped longs are on average better (+1.47% vs +1.23% a week), so a pump screen is not the lesson. Switching MN off in BEAR weeks already failed (`logs/mn_combos.txt`, 2026-10-08).
- **The sleeve (B2).** The BEAR label turned on 11-16 with BTC already 25% under its 60-day high; at breadth 1.7% it went long (the bounce bet) and lost 7.1% of the account in 5 days (including 11-20's -5.7% BTC day) = 3rd percentile of the backtest's 35 BEAR flips' first 5 days, worse than all 11 low-breadth flips (-3.5% .. +5.9%). Over 14 days those flips made money 73% of the time (mean +1.9%; worst 2022-05-10, LUNA, -10.8%); 43% of all flips lose (L6 wrong). Its result is not in yet.
- **The state (C1).** The record started at the top of an alt run: the week of 10-09 was fuel HIGH (48% of the PIT top-40 up > 20% in 30 days, the median alt +10%), then MID, then LOW from 10-23; BTC labelled bull to 10-22, chop to 11-15, bear from 11-16 (the Binance-close label equals the bot's logged label on all 42 days). Phase A was fuel LOW on only 36% of days (L10 wrong): a hot alt market rolling over, not the backtest's BULL + LOW corner.
- **Two measurement traps met (amendments in the file):** valuing a ledger from klines_all's PERPETUAL list silently dropped QQQUSDT (a TradFi perp, ~1x of the account); and an alt index built from November's top-40 for October's days knew October's hype coins (alts read -3.9% from 10-09 where the point-in-time index reads -28.7%). A date check on SIGNED returns read ~0 at every lag (the books bet both ways) and wrongly said 'NOT same-day'; the size of the sleeve's daily moves against the alt index's confirms same-day dating (+0.55 vs +0.04 / +0.08).
- **What it means.** The machine lost as a stock-picker, not as a market bet: its momentum picks (MN longs, daily breakouts, October's trend longs) were the coins that fell hardest in a sell-off that started from a hot alt market, and its crash books - built to buy flushes - met a decline with few of them. The backtest had seen nothing like this record, so the backtest's crash numbers (the machine's +23% median in such markets) are not a planning number. The day-45 KILL (doc 22 s3b, read 2026-11-23 00:04 UTC) stands; the paper bots keep running for the record (the user's wish). Nothing in any bot changed. Not proposed: a pump screen on MN (the backtest says pumped longs pay more on average), a faster bear label (`bear_label_test.py`), bigger shorts in bears (`graveyard_rescore.py`). Open, untested, only on the user's word: MN standing aside in panic states (narrower than the failed BEAR switch; the momentum-crash mechanism has outside support) - a post-hoc idea found by looking at this record, so its prior is low; and the capital floor (a real account needs ~$500+ or fewer carry names, CLAUDE.md s10 2026-11-19).
- **Predictions:** L5, L7, D1 right; L8 half right; L1-L4, L6, L9, L10, D2 wrong.

## 2026-11-21 (later) - "there must be something that we have learnt from this and can implement": two fixes tested, neither holds; what is left to implement is capital, size and the dashboard (`backtest/carry_names.py`, `logs/carry_names.txt`, `backtest/book_drop_check.py`, `logs/book_drop_check.txt`)

- **Keep the carry book alive with fewer coins (the $5-minimum switch-off): not supported.** The live carry book sizes all ~12 coins a side at equity / 48, so below ~$240 every coin is under Bitget's $5 minimum and the book goes empty (doc 22 s4 would allow a fix that keeps a live book doing what was tested). The machine's own carry book (`mn_combos.mn_run` funding7, +50% short exit, 7 weekdays) with fewer coins: Sharpe tune / holdout 12 coins +1.40 / +0.74, 10 +1.31 / +0.57, 8 +1.34 / +0.39, 6 +1.28 / +0.10, 4 +1.11 / +0.03; the worst week deepens -10.5% -> -23.5%; fewer coins lose the holdout on every weekday. Registered N1 (10 / 8 / 6 within 0.2) WRONG, N2 right. A 10-coin floor would only move the switch-off from ~$240 to ~$200 at a cost; not built.
- **Drop the crash's biggest live losers from the machine: not supported.** With / without one book against the full machine scaled to the same biggest fall (10 orderings, by half): without daily the reduced machine beats that line in 0 / 2 of 10 orderings (tune / holdout), without MN 4 / 0, without the NASDAQ dip-buy 0 / 0. Every book adds return per unit of risk on the backtest; one live crash does not overturn that.
- **What is left to implement (no bot code):** (1) CAPITAL - the books' positions are fixed shares of equity and Bitget refuses orders under $5, so each book has a floor: carry ~$240, crash bids ~$200, sleeve ~$175, MN ~$95, daily ~$80, capit2 ~$20 at full size (CLAUDE.md s10 2026-11-19); to keep all of them on after a 35% fall a real account needs ~$370 at full size; (2) SIZE - size is the only risk dial that has beaten every brake here (doc 17; `worst_month.py`), and at half size every floor doubles (carry ~$480, so ~$740 to survive the same fall): a smaller-risk version of this machine needs MORE money, not less; (3) THE DASHBOARD - the scorecard shows a book that holds nothing as 'on track' (carry since 11-13); a book under its floor should say so, with the capital it needs. Not proposed: any rule fitted to this one crash (every obvious one was already tested and failed: doc 02 2026-11-15 / 11-21 entries).

## 2026-11-21 (the desk's longs in the crash week) - "there must be a way to look at the market as a whole - sentiment or anything": the fast market direction as a filter on the Analyst desk; perfect on the crash week, nothing over 4.7 years (`backtest/analyst_fast_market.py`, `logs/analyst_fast_market.txt`)

The desk's live week 11-14..11-20: 16 shorts +21R, 23 longs 1 won, -23R. Tested before: the SLOW market state as a gate (`analyst_states.py`) and every market-wide signal in a model (`combo_meta.py`) - nothing. New here: the FAST direction of the whole market at the day's open, four gates (longs only when it leans up, shorts only when it leans down): F1 the point-in-time alt index over 3 days, F2 over 7 days, F3 BTC over 7 days, F4 Fear & Greed >= 50. On 9,824 crypto replay calls (2022-02 .. 2026-09), in money per bet (same day + side): kept minus dropped F1 -0.022 / +0.085R (tune / holdout, t -0.4 / +1.1), F2 +0.007 / -0.008, F3 -0.073 / +0.022, F4 (trade with the crowd's mood) -0.103 / -0.022 (t -1.9 on the tune half); the kept calls lose on both halves under every gate (-0.02 .. -0.09R a bet). HELPS none, PAYS none (Holm 1.00). On the live crash week the same gates would have dropped 83-100% of the longs and kept +20..+22R against -15..-17R dropped: a rule fitted to one week looks perfect on that week. The market's last 3-7 days do not tell the desk's next day: after a falling week the next day bounces about as often as it falls. Q1-Q4 right. Nothing changed on the desk.

## 2026-11-21 (how a day starts) - "not opening your trades for so long ... predict how it will perform in a day if a day starts like this or that": same-day crypto trades from the day's first hours, flat by midnight; a coin flip (`backtest/day_start.py`, `logs/day_start.txt`)

BTC, ETH, SOL, XRP, BNB hourly bars (the Analyst desk's own cache), 1,759 UTC days 2022-01 .. 2026-10. The start = the first 1 / 4 / 8 / 13 hours (13:00 UTC ~ the US open); trade the rest of the day WITH or AGAINST it, out at 24:00 UTC, 12bp + 1bp per funding settlement; all days and strong starts (top 20% of the coin's earlier starts); a bet = one day; 16 cells. **No pass (Holm 1.00).** After a strong start the rest of the day went the same way on 45% (first hour) to 51% (13h) of coin-days against a 49% base rate. The first hour leans to reversal (strong, net +15 / +21bp, t 0.6 / 0.8), 8 hours to continuation (net +12 / +29bp, t 0.6 / 1.2): 2 of 16 cells positive on both halves after costs, what chance gives. Every all-days cell loses the 12bp. Crypto trades 24/7 and has no real day start; the same idea on NASDAQ, which opens and closes, is the one intraday rule here that held up (`noise_book.py`, `nq_noise.py`; `forex_bot.py` built for it, demo-only, not started). P1 right, P2 and P3 wrong.

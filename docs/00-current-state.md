# Where we stand

*Last updated 2026-09-13.*

## The short version

We have **one strategy that survived every honest test**, and it makes roughly
**+10% a month** in simulation. That is the target, hit — but only just, and with
a drawdown that makes small accounts dangerous.

Everything else we tried is dead. That is not a failure of effort; it is what
honest testing looks like. Most trading ideas do not work, and the ones that
"work" in a sloppy test stop working the moment you charge real fees and stop
cherry-picking which coins to trade.

## The numbers

| | |
|---|---|
| Return | **+240% per year** (≈ +10.7% per month, compounding) |
| Worst drawdown | **74.8%** |
| Won months | ~85% of 30-day blocks positive |
| Minimum capital | **~$1,140** for the 9-coin book. A 4-coin book runs on **$49** but returns ~+3%/mo, not +10.7% |
| Tested on | 2020–2026, hourly bars, 9 coins picked *without hindsight* |

Source: `backtest/pit_universe.py`. Cross-checked against `backtest/twoside.py`.

## What that 74.8% drawdown actually means

It means at some point the account was down about three-quarters from its high
and stayed there for a while before recovering. And *recovery comes from trading*
— so if the account falls below the level where the exchange accepts an order, it
never recovers. **It's dead, not down.** That makes the minimum-order rule an
absorbing barrier, which is why it sets the capital floor.

The binding coin is **ETH**: its smallest tradable step is 0.01 ETH ≈ $25 of
notional. At 0.13% risk per unit and a 2 × ATR stop, a $25 position corresponds to
about $382 of equity — and to survive a 74.8% drawdown and *still* place that
order, you need ~$1,500 to start.

**The constraint is one contract, not the venue.** Dropping the expensive
contracts drops the floor — and it costs return, because return scales with how
many coins are in the book. Both effects measured together in
`backtest/small_book.py`:

| Book | Capital needed (MEXC) | Honest return | Drawdown |
|---|---|---|---|
| 3 cheap — ADA AVAX LINK | **$44** | +1.94%/mo | 45.6% |
| **4 cheap — + XRP** | **$49** | **+2.96%/mo** | 51.1% |
| 5 cheap — + BNB | $209 | +4.36%/mo | 54.0% |
| 6 cheap — + BTC | $258 | +6.01%/mo | 62.8% |
| **9 coins (validated)** | **$1,140** | **+10.73%/mo** | 67.5% |

**This is the actual menu.** $50 buys about 3% a month. $260 buys about 6%.
The headline 10.7% needs about $1,140 and there is no way around that — the
9-coin book requires ETH, and ETH's minimum order is $25.

Two things make this table trustworthy rather than another guess:

- **A built-in control.** The two 9-coin rows are the same coins in a different
  order and come out at +719.8% and +719.1%/yr — so the engine isn't
  order-sensitive.
- **The hindsight divisor is cross-checked.** The raw fixed-book numbers are
  inflated because the book is made of coins that are listed today. The 9-coin row
  reads +719.8%/yr against the point-in-time +240.1%/yr — a ratio of **3.00×**,
  matching the 3.03–3.05× premium measured independently a different way. Every
  "honest" figure above is the raw number divided by that.

MEXC is the venue in this table because it's the only one with no minimum order
*cost* — Bitget, Bybit and Binance all impose a hard $5, which pushes the 4-coin
book from $49 to $487.

**Caveats that matter.** The 3× divisor is a straight-line correction anchored at
the one book size where both measurements exist; the cheap coins may not carry
exactly that premium. And the minimum-order figures come from exchange metadata
dated 2026-09-13, which needs one real demo order to confirm.

## Can anything clear +10%/month for less than $1,140?

Yes — one configuration, and it costs a 94% drawdown.

`backtest/cheap_wide.py` swept **26 combinations** of book size (6–20 coins), slot
cap (8–20) and risk (0.13–0.30%/unit) across the 20 most liquid *cheap* contracts
on MEXC — coins whose minimum order is under $2.50, so ETH and BTC are excluded by
construction. Result:

| Option | Capital | Return | Drawdown |
|---|---|---|---|
| **9 major coins, 0.13%/unit** *(validated)* | $1,140 | +10.73%/mo | **67.5%** |
| **12 cheap coins, 0.30%/unit** | **$438** | **+12.18%/mo** | **94.3%** |
| 20 cheap coins, 0.13%/unit | $272 | +6.30%/mo | 78.0% |
| 12 cheap coins, 0.13%/unit | $184 | +5.81%/mo | 68.7% |

**Every single cell that cleared +10%/month had a drawdown of 94–99%. All of
them, without exception.** That is not a coincidence, it's the mechanism:

> **Chasing return with risk RAISES the capital floor rather than lowering it.**
> The floor is `minimum order ÷ risk fraction ÷ (1 − drawdown)`. Doubling risk
> roughly doubles return but more than doubles drawdown, and the `(1 − drawdown)`
> term explodes. At 94% drawdown you need 16× the padding you'd need at 0%.

Why cheap contracts are worse per unit of risk: their median stop is **2.5–3.8%**
of price against **1.2–2.2%** on the majors. Wider stops mean noisier breakouts, so
you need more risk to reach the same return — and risk compounds into drawdown.

**The $438 option is real, not a trick.** At the bottom of its 94.3% drawdown the
account holds ~$25, which is exactly its own minimum-order requirement. It
survives by nothing. One bad tick worse and it's finished.

**Nothing under $438 cleared +10%/month in any of the 26 combinations tested.**

## Then exit management moved the wall (2026-09-13)

The wall above assumed the exit rule was fixed. It wasn't — and this came from
watching the live demo bot, not from a backtest.

Three shorts were open, all winning, and **all three would still have closed at a
loss**:

| | entry | stop | open profit | if stopped |
|---|---|---|---|---|
| BTC short | 77,122 | 77,334 | +1.78R | **−0.85R** |
| XRP short | 1.3609 | 1.3692 | +2.13R | **−0.87R** |

A 5×ATR trail gives back 2.5R, and the long side's 20×ATR trail gives back 10R.
Nothing is protected until the trade is deep in profit, and the gap between *open*
and *locked* profit is where the drawdown comes from.

Fix: move the stop to entry once a trade has earned +3R, then let the trail keep
running. Measured in `backtest/ddcontrol.py`:

| | Return | Drawdown | Capital |
|---|---|---|---|
| 12 cheap coins, 0.30%, no breakeven | +12.17%/mo | 95.2% | $520 |
| **same + breakeven at 3R** | **+13.93%/mo** | **87.6%** | **$200** |
| 9 major coins, 0.13% *(validated)* | +10.73%/mo | 67.5% | $1,140 |

**Capital requirement fell 61% and the return went up.** Not a trade-off — the
drawdown was pure waste.

### Why this isn't the profit-cap disaster again

A profit **target** caps the ceiling and deletes the rare huge winners that pay for
everything — that bug wrongly killed 8 of 11 trend families. A breakeven **stop**
raises the floor and leaves the ceiling open: the trail still runs to 20×ATR, so
runners survive. Opposite mechanism, opposite result.

### Why this result is trustworthy

The breakeven threshold was swept 1R through 6R at two risk levels. **All 12 cells
reduced drawdown, and both risk levels peaked at the same place (3R) on a smooth
curve** — 2R and 4R are also better than baseline, just less so. A smooth
single-peaked response at a consistent location is evidence; a lone good cell
surrounded by bad ones is curve fitting.

### What did NOT work

- **Volatility targeting** — the standard institutional drawdown control. Raised
  return but raised drawdown more; capital needed went *up* 84–183%. I predicted
  this would be the best of the four. It was the worst.
- **Drawdown throttle** (halve risk when 25% below peak) — cuts drawdown to 79.6%
  but costs 4.3 points of monthly return, dropping below target.
- **Going flat** in a drawdown — destroys the strategy (+0.46%/month). Recoveries
  start at the bottom; if you're flat you miss them.

## The $50 attempt — failed, for a structural reason

Three routes tried (`backtest/floor50.py`), all pushing on the term that actually
sets the floor: `min_order × stop_fraction` of the single worst coin in the book.

**1. Breakeven at 3R on the major coins.** Helped, but barely. Drawdown 67.6% →
66.9%, capital $1,143 → $1,122. Return did improve, +10.72% → **+11.80%/month**,
which is free money — but the majors' drawdown is *correlated portfolio* drawdown,
all nine falling together, and no per-trade stop rule touches that. The alts' 95%
drawdown was full of per-trade waste; this one isn't.

**2. Substitute the expensive coin instead of dropping it.** Rank every liquid MEXC
contract by `min_order × stop_fraction` and take the cheapest 9–16. Floors came out
tiny — and **every book drew down 99.6–100%.** Total wipeout.

**3. Same search with a hard liquidity floor** ($400k and $1M of volume per bar).
Still 91.7–100% drawdown, and the best honest return in the whole cheap-minimum
search was **+5.38%/month**. One configuration did reach a **$26** floor — at
+4.61%/month and a 96.7% drawdown.

### Why $50 and >10%/month are in direct conflict

> **A contract's minimum order is small because the coin's price is low. Coins get
> to a low price by falling.**

So the exact contracts that would let a $50 account trade sit on coins in
structural decline. That's why the selection kept surfacing ILV, ICX, CVC, GALA,
COTI — $30k–170k of volume per bar against XRP's $6.8M — and why every book built
from them wiped out. It isn't a search failure that can be fixed with a better
filter; the two requirements pull against each other by construction.

### Where that leaves the capital question

| Config | Return | Drawdown | Capital |
|---|---|---|---|
| **12 reputable alts, 0.30%, BE@3R** | **+13.93%/mo** | 87.6% | **$200** |
| **9 majors, 0.13%, BE@3R** | **+11.80%/mo** | **66.9%** | **$1,122** |
| anything under $50 | ≤ +5.38%/mo | 91–100% | — |

$200 is the cheapest thing that clears +10%/month, and at 87.6% drawdown a $200
account sees ~$25 at the bottom — exactly its own minimum requirement. It survives
by nothing.

$1,122 is the one to trade with real money: 66.9% drawdown is survivable, the nine
coins have the most history behind them, and the engine reproduced the validated
+10.7%/month figure on this book to two decimals.

## Should a small account take profit? (2026-09-13)

Proposed: make the bot adaptive in equity — take profit at a fixed target while the
account is $10–20 to climb to a threshold, then switch to the trailing rule.

The reasoning behind it is sound. Near the floor, maximising *growth* is the wrong
objective; what matters is the chance of reaching the target before dying. Capping
the upside cuts variance hard, and less variance can raise survival odds even at a
lower average. That's a real effect and worth testing.

**It doesn't work, because the cap doesn't lower the edge — it reverses it.**
Measured per-trade mean R (`backtest/bootstrap_tier.py`):

| Exit rule | Mean R | Win rate |
|---|---|---|
| Trailing (current) | **+0.3049** | 24.8% |
| TP@1R | **−0.0481** | 67.4% |
| TP@2R | **−0.0289** | 51.5% |
| TP@3R | **−0.0212** | 41.5% |

Negative expectancy at every target level. No bet-sizing rule makes a losing bet
reach a goal, and the simulation agrees: **0.0% chance of reaching 5× from every
starting stake.** Note TP@1R wins 67% of its trades — it will look like it's
working right up until the account is gone.

### But the principle was right — the thing to adapt is the VENUE

The simulation found the real cause of small-account ruin, and it isn't the exit
rule. Bitget's **$5 minimum order** against a 2.43% stop forces $0.12 of risk per
trade, which on $20 is 0.61% — five times the validated 0.13%. **The venue makes a
small account gamble.**

Same strategy, same honest edge, only the minimum order changes:

| Stake | Venue floor | Forced risk | P(reach 5×) | **P(ruin)** | median end |
|---|---|---|---|---|---|
| $10 | Bitget $5.00 | 1.22% | 24.8% | **74.6%** | $0 |
| $10 | MEXC XRP $1.34 | 0.33% | 12.3% | **32.4%** | $15 |
| $10 | MEXC ADA $0.21 | 0.13% | 5.3% | **0.0%** | $13 |
| $20 | Bitget $5.00 | 0.61% | 25.2% | **56.4%** | $0 |
| $20 | MEXC ADA $0.21 | 0.13% | 5.3% | **0.0%** | $25 |
| $50 | MEXC ADA $0.21 | 0.13% | 5.3% | **0.0%** | $63 |

**Moving a $20 account from Bitget to MEXC takes ruin from 56% to ~0%** without
touching the strategy. That is the adaptive rule the data supports:

> **Small capital → low-minimum venue and low-minimum coins at the intended risk.
> Larger capital → majors and full breadth.**

The tier switch is real. It's a switch of *where and what* you trade, not *when you
take profit*.

### What this costs, honestly

Removing forced over-risk also removes the lottery ticket. Bitget's $5 floor gave a
25% shot at 5× — because it was betting 5× too large. MEXC gives ~0% ruin and a
median of $13 from $10 over roughly four years of trades.

**Important: that growth figure is pessimistic.** The simulation runs one unit with
non-overlapping trades, so its total exposure is well under the live config's 0.65%
across 8 concurrent slots — roughly 5–8× less. The *ruin ordering* is the robust
finding here; the growth column is a floor, not a forecast.

Unverified: MEXC's minimum orders are metadata, and whether MEXC futures API access
works from Pakistan is unchecked. Both need confirming before this is a plan.

## The $200 config, validated (2026-09-13) — read this before funding anything

Three tests run in `backtest/val200.py`, then 26 optimisation cells with a 60/40
time holdout in `backtest/opt200.py`.

### Test 1 — shuffled markets: STRONG PASS
150 shared-index permutations. Real mean R **+1.055** against a permuted
**+0.055 ± 0.187**. **Zero of 150** permutations matched it. **p = 0.0066.**
The edge is not an artifact of the price path.

### Test 2 — survivorship: PASS, but it resizes the edge
Identical rules on 197 **delisted** coins: mean R **+0.163**, PF 1.11, win 19.3%.
Positive, so the signal is not survivorship-dependent — but the live book's mean R is
**+1.538**, which is **9.4× higher**. Most of the *magnitude* comes from the 12 coins
having survived and appreciated. **The 3× hindsight divisor used throughout may be
too generous.**

### Test 3 — time split: THE PROBLEM

| Period | Mean R | t | Return/month |
|---|---|---|---|
| First 60% (2020-02 → 2024-04) | +2.04 | +3.66 | **+17.01%** |
| Last 40% (2024-05 → 2026-09) | +0.79 | **+1.68** | **+7.95%** |

Per year, share of total profit:

| Year | Mean R | Share of all profit |
|---|---|---|
| 2021 | +5.20 | **40%** |
| 2024 | +3.04 | 31% |
| 2022 | **−0.49** | — |
| **2025** | **+0.03** | **~0%** |
| **2026** | **+0.26** | 2% |

**2025 and 2026 produced 2.5% of all profit on 30% of all trades.** The strategy has
been close to flat for roughly 20 months. The recent half is not statistically
significant (t = 1.68).

### The one improvement that survived the holdout

**Cut risk to ¼ while BTC is below its own 200-hour average.**

| | Return/month | Drawdown | Capital |
|---|---|---|---|
| baseline, last 40% | +7.95% | 84.8% | $163 |
| **+ BTC regime gate, last 40%** | **+8.84%** | **60.7%** | **$63** |

Better return, **24 points less drawdown**, capital floor cut 61%. Believed because
**both** gate strengths improved monotonically (×0.5 → 71.1% DD, ×0.25 → 60.7%), not
one lucky cell. 4 of 26 cells survived where ~1 is expected by chance.

**What failed:** the directional exposure cap — my top prediction. Capping longs at 4
cut drawdown but destroyed return (+1.53%/month out of sample). Crypto's correlated
drawdown cannot be fixed by refusing the trades.

### Honest expectation for $200 today

**~+8.8%/month, ~61% drawdown, on the most recent 2.4 years** — and that period
includes 20 months of near-flat performance. Not the +13.93% quoted earlier, which
was an average carried by 2021 and 2024.

## What we were missing: timeframes, not strategies (2026-09-13)

### The blind spot

Every test in this project — 393 configs, 19 indicator families, the whole drawdown
battery — ran on **1-hour bars**. Lower timeframes were tested and killed on cost.
Higher ones were never tried.

`backtest/timeframes.py`, identical rules on resampled bars:

| Bars | Fee cost/trade | Mean R | Return/mo | Drawdown |
|---|---|---|---|---|
| 1h | 0.045R | +1.538 | +13.93% | 84.8% |
| **4h** | **0.022R** | **+3.761** | +8.67% | 75.4% |
| 12h | 0.012R | +4.110 | +1.53% | 64.5% |
| 1D | 0.008R | +3.412 | +0.73% | 43.4% |

Mean R rises with the bar size exactly as the fee arithmetic predicts. Total return
falls because trade count collapses (6,546 → 308).

### They are almost independent return streams

**Monthly correlation, 1h vs 4h: +0.178.** 12h vs 1h: **−0.082.** Same signal, same
coins, same rules — and they barely move together.

Yearly return at 0.30%/unit:

| | 2022 | 2025 |
|---|---|---|
| 1h only | **−159%** | **−100%** |
| 4h only | +40% | +36% |
| **1h + 4h + 12h** | **+2%** | **+102%** |

**The three-sleeve blend turns both losing years positive.** That is the thing that
was missing — not a better signal, a second sampling of the same one.

| Setup | Return/mo (recent) | Drawdown | Capital | Losing years |
|---|---|---|---|---|
| 1h, 12 slots | +13.19% | 74.3% | **$97** | 2022, 2025 |
| **1h + 4h + 12h, 8 slots** | +8.32% | **57.0%** | $217 | **none** |
| 1h + 4h, 16 slots | **+17.29%** | 85.0% | $345 | 2022 |

Cost of the blend is capital: the longer bars use wider stops, so positions are
smaller and harder to get above the venue minimum.

## Cross-sectional momentum with proper exits: DEAD as a diversifier

`backtest/xs_convex.py`. The market-neutral strategy (MCPT p=0.0033, passed a 500-day
holdout) was dismissed as "too small" before position management was known to be worth
2–9×. Retested with the pyramid and trailing exits, two ways: rank-as-entry, and
rank-as-filter on the breakout.

**Every configuration correlates +0.869 to +0.972 with the breakout book.** Against
1h-vs-4h's +0.178. It is the same bet.

**The reason, predicted before running:** the thing that made it attractive was
dollar-neutrality — matched long and short legs rebalanced together. Replacing that
with individual trailing stops means legs exit at different times, neutrality is gone,
and what's left is the same long-crypto exposure.

**A limit on this test, stated plainly:** it ran on 8 coins, and with 4 per side
"top 4 / bottom 4" selects *every* coin — no discrimination at all. The original used
21 coins. So the time-cap question on the original rebalancing engine is still open;
it just cannot be answered on the $200 book's universe, and a 21-coin version would
include ETH, putting the capital floor back over $1,000.

## Can we capture the profit the trail gives back? (2026-09-13)

From a live observation: three demo shorts peaked at +1.78R, +0.70R and +2.13R and
two later closed at a loss. A 5×ATR trail on a 2×ATR stop gives back **2.5R**, so a
short must reach +2.5R before a cent is protected — and the breakeven was set at 3R,
so on BTC it never armed.

`backtest/exitlab.py` tested four mechanisms never tried before. Fixed profit targets
were not retested — they are already known to make mean R negative.

| Mechanism | Short sleeve | Long sleeve |
|---|---|---|
| baseline (trail only) | −0.036 | **+0.573** |
| breakeven @3R (current) | −0.036 | +0.477 |
| breakeven @1R | −0.122 | +0.117 |
| **scale out 50% @2R** | **−0.013**, DD 75→55% | **+0.241**, maxR 220→111 |
| **ratchet trail tighter @3R** | **−0.003**, DD 75→50% | +0.158 |

**Partial scale-out helps shorts and destroys longs.** On the long sleeve it halves
mean R *and* halves the biggest winner — it is the profit cap wearing a disguise, and
the monster trades are the entire strategy.

**Early breakeven on shorts makes things worse** (−0.122 at 1R): a stop that close gets
picked off by noise, ending trades that would have worked.

**Best short variant: ratchet the trail tighter after +3R** — essentially breakeven
mean R with a third less drawdown.

### The finding that matters more than any of them

Adding a **pessimistic same-bar stop check** — if the stop sits inside the bar's range
it fills in that bar, rather than waiting for the next — moved the short sleeve from
**+0.034 to −0.036**.

**The short sleeve's edge was resting on an optimistic fill assumption.** Every
two-sided figure in this document includes shorts measured the old way. The long
sleeve barely moves under the same check (+0.574 → +0.573), so this is specific to
shorts — their trail sits much closer to price.

### One mechanism is unmeasurable, not failed

A give-back cap (exit when profit retreats a % of its peak) reported **+21.60%/month
at 4.2% drawdown**. Both settings produced the *identical* trade count — 79,738
against the baseline's 7,026 — because both were closing on the entry bar. The banked
profit came from the bar's own high/low, which is not knowable when the order is
placed, and no stop-timing fix repairs that because **the look-ahead is in the profit
itself**. Testing it needs tick or 1-minute data.

### Re-run under the pessimistic fill: today's numbers survive

`backtest/strictfill.py` re-ran everything with the strict rule on **both** sleeves
(applying it to shorts alone would rig the comparison).

| Sleeve | Optimistic | Strict | Damage |
|---|---|---|---|
| long only | +2.727 | +2.686 | **−0.041** |
| short only | +0.034 | **−0.036** | −0.070 |
| long + short | +1.538 | +1.401 | −0.137 |

**Longs are essentially unaffected** — their 20×ATR trail sits far from price.
**Shorts do go negative standalone**, as suspected.

**But the two-sided book still beats long-only on every axis:**

| Config (strict) | Return/mo | Drawdown | Capital | 2022 | 2025 |
|---|---|---|---|---|---|
| long only | +10.89% | 78.5% | $115 | **−217%** | −67% |
| long + short, 1h | +12.06% | 68.9% | **$80** | −167% | −10% |
| **1h + 4h + 12h** | **+12.48%** | **57.7%** | $221 | **+64%** | −9% |
| 1h + 4h | **+19.89%** | 73.9% | — | — | — |

### Why a losing sleeve improves the portfolio

Shorts have **negative** expectancy on their own and still raise compounded return
(+10.89% → +12.06%/month). That is not a contradiction: they cut drawdown from 78.5% to
68.9%, and lower drawdown means less volatility drag, which lifts compounded growth even
at a lower average per trade. **Shorts are a hedge that pays for itself** — they should
be justified that way, never as a profit source.

### Net effect on today's conclusions

The correction costs roughly **1 percentage point of monthly return**. The $200
configuration stands, the blend still has the lowest drawdown of anything measured, and
2022 still goes from −217% (long only) to +64% (blend).

These are full-history figures including 2021. **The recent-period numbers
(~+8.3%/month for the blend) remain the ones to plan against.**

### Not adopted yet

The breakeven rule is **not in the live bots**. Before it goes in it needs the
shuffled-market test and a check on the delisted-coin data, because 12 alts is
exactly the book where survivorship bias would hide. And 87.6% drawdown still means
a $200 account sees $25 at the bottom.

If you halve the risk setting, you roughly halve both the return and the
drawdown: ~+5%/month with ~40% drawdown. That is the trade you actually get to
choose.

## Is +10% conservative or optimistic?

**Conservative in these ways:**
- Coins are chosen by last month's trading volume, never by knowing which ones
  went up. Picking "today's top 9" instead inflates results by **3.05×**
  (measured, `backtest/pit_universe.py`). Everyone selling backtests does the
  inflated version.
- Dead coins are included. 203 USDT pairs have been delisted — a **30% death
  rate** — and positions open when a coin died are counted as losses, not quietly
  deleted.
- Only 8 positions can be open at once, so trades that couldn't physically be
  taken aren't counted.
- Fees charged both ways at Bitget's real taker rate.

**Optimistic in these ways:**
- Fills are assumed at the bar price. In a crash the real fill is worse.
- The window 2020–2026 contained a historic crypto bull run. The short sleeve
  helps in bear years but does not make them good years.
- It's still one strategy on one asset class.

## What's running right now

Six processes (`vsa_forward.py` stopped 2026-09-13 — see [doc 05](05-vsa.md)).
None of them can touch real money — `ALLOW_REAL = False` in
`longtrend_bot.py` is a hard gate that a human has to flip.

| Process | What it is |
|---|---|
| `longtrend_bot.py` | **Bitget demo, real orders.** 3 coins, aggressive risk by request. This is the one to watch. |
| `longtrend_paper.py` | $20 simulated account, 9 coins, the validated 0.13%/unit risk. Long-only. |
| `xs_paper.py` | Cross-sectional momentum forward test, 10 variants. |
| `crypto_maker.py` | Maker fill-rate probe. |
| `crypto_multi.py`, `portfolio_bot.py` | Older multi-coin runners. |

## The three things that actually moved the results

Worth knowing, because they were each worth more than any indicator we tested:

1. **Letting winners run.** Every early test closed profits at a fixed target,
   which capped a winner at +1.5R. Removing that cap turned 3 of 11 trend
   strategies profitable into **11 of 11**. Nothing else came close to this.
2. **Adding to winners.** Buying more of a position that's already up, funded by
   its own open profit, gave more return *and less* drawdown at the same risk.
3. **Not cheating on coin selection.** Worth 3.05× — in the wrong direction.

Indicators, by contrast, barely mattered: we tested 19 different families and
all 19 detected the same thing. See [doc 02](02-what-failed.md).

## What's next

- Deploy the paper runners to Oracle Cloud so they run 24/7 without this PC on.
  Scripts are written (`deploy/setup.sh` + systemd units); needs the VM created.
- Let the demo bot accumulate trades. It has 3 so far.
- Decide on capital. The strategy is ready; $10 is not.

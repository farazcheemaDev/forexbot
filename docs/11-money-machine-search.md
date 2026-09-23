# The money-machine search (2026-09-23)

*Asked for: "a money making machine, separate from the trend book or mixed with it." Every
candidate below was chosen for having a **mechanism**, meaning someone forced to trade on a
clock or a rule, because that is the only kind of edge this project has ever confirmed. Each
had its prediction written into its file before it ran. Every number names its file.*

**Short version: nothing here is a money machine.** One effect is real but belongs to
co-located bots. One is thin and fading. Everything else is dead. The detail matters because
it says *where* edges go to die, and that is the map for the next search.

---

## 1. Funding-settlement timing — REAL, but it lasts a fraction of a second

Funding is paid only by positions held **at** the settlement second. With strongly negative
funding, shorts close just before it (so they don't pay) and reopen just after.

**The shape is there** (`backtest/settlement_timing.py`, 1,393,770 settlements, 776 perps,
2020–2026; 8h coins, 2h before vs 2h after, excess over a mid-interval control):

| funding at settlement | n | before (excess) | after (excess) |
|---|---|---|---|
| ≤ −0.30% | 2,898 | **+137.6bp** | **−137.8bp** |
| −0.30..−0.10% | 6,573 | +31.9bp | −43.4bp |
| ≥ +0.30% | 1,547 | −108.5bp | +39.3bp |

**The registered prediction was wrong in its shape:** I expected the effect on the
*positive*-funding side. The large, clean one is on the negative side.

**Then it was taken apart, one flattering assumption at a time:**

| check | file | result |
|---|---|---|
| charge the funding crossed while holding | `settlement_check.py` | kills 4h holds and 1–2h-interval coins |
| enter 1 minute late, on 1m bars | `settlement_check.py` | POST short +43bp at t → **+10bp at t+1m** (below 12bp cost) |
| tick data: *seconds* late | `settlement_ticks.py` | POST short **+8bp at 0.2s, −6bp at 1s, −15bp at 5s** |
| the funding farm (long through the settlement, sell right after) | `funding_farm.py` | see below |

The post-settlement drop happens **inside the first second**. That's a race between
co-located bots. A PC in Pakistan cannot win it, and neither can a cloud VM anywhere else.

**The funding farm** buys 1–2h before a settlement whose *previous* rate was deeply
negative, collects the payment, and sells ~0.25–0.5s after. It needs a bot firing on a
clock, not on speed. Tick-measured exit cost on its own events: 7.0bp at 0.25s, 9.7bp at 0.5s
(`farm_ticks.py`). Net of 12bp fees and 8.3bp exit slippage (`funding_farm.py`, random
samples):

| previous rate | enter | n | net/event | tune | holdout | 2026 |
|---|---|---|---|---|---|---|
| ≤ −0.10% | t−2h | 800 | +15.9bp | +34.1 | **+5.4** | −1 |
| ≤ −0.10% | t−1h | 800 | +16.3bp | +30.6 | +8.1 | +7 |
| ≤ −0.30% | t−2h | 600 | +48.0bp | +79.1 | +33.8 | **+2** |
| ≤ −0.30% | t−1h | 600 | +31.2bp | +63.0 | +16.5 | +1 |

Per-event SD is 280–530bp, and clustered t-stats run 1.0–2.0. **Registered test: fail at
−0.10%** (holdout under +10bp). **Pass on magnitude at −0.30% / t−2h, but not significant.**
The decisive row is **2026**: the year with the most events (242–271 in these samples) nets
**about zero** at every setting. Whatever this was, it has been arbitraged away this year.

> **Where it went:** funding capture is the most-farmed trade in crypto. The price move that
> pays for it is priced within a second, and what's left over after that has been competed
> to zero.

## 2. Shorting delisting announcements — NOT CONFIRMED — `backtest/delist_events.py`

Binance spot-delisting notices (68 coin-events, 27 notices): short at +10 min, and the coin
keeps falling, **+6.2% net at 3 days, +9.8% at 7 days**, positive both halves. About 12% of the
drop is already gone before entry. But: 27 clusters, t 1.45–2.02, and the random placebo alone
moved the excess by ~2 points between runs.

The pre-registered confirmation used three event types that played no part in finding it:

| event type | coin-events | 7-day excess over placebo |
|---|---|---|
| Binance monitoring-tag notices | 94 | +3.7% (t 1.06); 3-day holdout **−1.7%** |
| Upbit caution designations | 38 | +2.1% |
| Upbit delistings | 24 | **−0.8%** (predicted to be the strongest) |

**Rule written before the run: any negative at 7 days → the SPOT result is noise.** Upbit
delistings are negative. Dead as a book.

## 3. Grid bots — DEAD — `backtest/grid_bot.py`

The exchanges' flagship "money machine," and the obvious mix for a trend book that bleeds in
chop. Neutral futures grid, 20 levels, maker 2bp, funding on the inventory, rolling re-centre;
BTC, ETH, SOL, XRP, DOGE, 2020–2026. The accounting was unit-tested against a synthetic
oscillation (exact) and a synthetic crash (exact) before any real run.

**28 of the 30 configurations lose money** (6 spacing/gate settings on each of 5 coins; counted from `logs/grid_bot.txt`, which is what the house rule means by a number naming its file - an earlier draft said 24 of 26), most by multiples of the ladder's capital (BTC 0.5%
spacing: −174%/yr). The two survivors are BTC 3% (+0.7%/yr) and ETH 2% range-gated (+6.3%/yr,
Sharpe 0.32), which is what chance throws up among 26. **In the trend book's losing months the
grid loses too**, so it isn't even a hedge. The correlation with the trend book is near zero,
not the −0.2 to −0.5 I predicted. A grid is short volatility with inventory risk, and crypto
trends.

## 4. Hyperliquid's HLP vault — WAS a machine, has decayed — `strategy_analysis/data/hlp_vault.json`

A public market-making pool anyone can deposit into. From its own P&L history: **2024 +79%,
2025 +19%, 2026 YTD +7.9%**, the last six months roughly flat, current APR shown as 3%. It is
the same curve as the options premium (doc 02: +18 vol points in 2021 → 0.00 in 2026) and
funding carry: **a structural yield gets competed down to near zero once enough capital
finds it.**

## 5. "CME gaps always fill" — DEAD — `backtest/cme_gap.py`

Fade a ≥1% weekend gap at the CME reopen, target the Friday close, stop at the same distance:
180 trades, **filled first only 42%**, mean **−0.32%/trade**. A mid-week placebo with no
market closed does the same (−0.23%). It is short-term reversal under another name.

---

## What this search says, in one paragraph

Five mechanisms, five different places, one pattern. **Every edge with a real mechanism is
either priced within a second by co-located bots (settlement), or competed down to zero by
capital that found it (funding farm 2026, HLP, vol premium, carry), or too rare to tell from
noise (delistings).** What's left for a small account is the one thing none of those
competitors want: **risk.** The trend book gets paid for sitting through 50% drawdowns and
losing months, which is exactly why it still pays. That's not a consolation; it's the
finding. A "perfect" machine — steady, large, and safe — would be the first thing big capital
removes.


## 6. The first-perp short, extended past the events that ran out — DEAD — `backtest/first_perp.py`

The one event edge in this project that passed a placebo: short a coin when it gets its first
Binance perp, hedged with BTC. It was shelved because Binance ran out of coins with Binance
*spot* history (the last was May 2025). The extension used MEXC/Gate's first candle as "first
traded anywhere," since tokens now trade for months on DEXs and small exchanges before Binance
lists a perp. Same trade: day 7, 30 days, +50% stop, BTC long hedge, 12bp a leg, funding both
legs.

| class | n | pair mean | t (months) | placebo day 60 | tune | holdout |
|---|---|---|---|---|---|---|
| OLD_BN (the original definition, guard) | 199 | **+10.5%** | **+3.07** | −0.3% | +10.5% | none left |
| **OLD_OTHER (the new test)** | 102 | +3.4% | +1.05 | **+10.2%** | +5.0% | **−1.6%** |
| NEW (fresh tokens) | 520 | +3.6% | +1.52 | +3.0% | +10.2% | −1.1% |

**The guard reproduces the original to the decimal** (doc 02: +10.3%, t +3.06), so the
measurement is sound. **The extension fails its registered test.** It loses to its own
day-60 placebo, it is negative on the holdout, and its dose-response is non-monotone
(60–180d −4.6%, 180–365d +6.8%, 365d+ +6.1%, each beaten by its placebo). Prediction 2 (+3–6%,
t 1.5–2.5) was right on the mean and wrong on everything that makes a mean believable.

**What that says about the mechanism:** the short-sale constraint only binds when Binance
really is the first place the coin can be shorted. A token with DEX or small-exchange history
almost always had a perp on Bybit/OKX/Hyperliquid first, so the pessimists were already in.
The edge was specific to a supply of events that no longer exists.

## 7. The coin-level kimchi premium — DEAD — `backtest/kimchi.py`

Korean won can't move freely, so a coin trading far above its Binance price on Upbit (beyond
BTC's own premium) is Korean retail piling into one name. 229 coins on both venues,
2020–2026.

| test | result | registered bar |
|---|---|---|
| weekly: long lowest-premium quintile, short highest | **+0.26%/wk gross**, +0.18% net, t +1.04; tune +0.25, **holdout +0.07** | > +0.5%/wk gross in both halves: **fail** |
| event: premium crosses +5%, 7-day excess (uncosted) | −1.56% (tune −0.73%, holdout −2.66%) | predicted sign: held |
| same event, **costed** (24bp, actual funding, week-clustered) | **+0.06%/event, t +0.85**; placebo, same coins at random weeks: **+0.62%** | |

The category's rule was fixed before the run: if the weekly test fails, it's dead. The event
result looked like it might survive that. It doesn't once fees and funding are charged, and
it comes in under its own placebo. **Funding priced it**, which is the fourth time in this
project (Upbit fade, new-listing shorts, funding spikes, now this).

---

## Which convention these numbers use

**Everything in Part 2 is ENTRY-SIZED** (mistake #14 corrected), which is why its `%/mo`
figures are roughly half those in `logs/honest_rescore.txt`. That file is daily-sum and still
carries #14; it is kept because `compounding.py` was found by the disagreement between them.
Same comparison, two conventions, and the paired difference for the tight exit even swaps
which half looks better:

| tight vs main | tune | holdout | file |
|---|---|---|---|
| entry-sized (use this) | **+2.87 ± 0.28** | **+1.98 ± 0.35** | `graveyard_rescore.txt` |
| daily-sum (superseded) | +2.15 ± 0.66 | +2.79 ± 0.74 | `honest_rescore.txt` |

The verdict is the same either way - tight beats main on both halves - and the entry-sized run
says it with tighter error bars. But do not quote the two side by side.

## The conclusion, now that all seven are in

| # | idea | mechanism real? | reachable by us? | verdict |
|---|---|---|---|---|
| 1 | settlement timing / funding farm | **yes** | sub-second; the farm's residual is ~0 in 2026 | dead for us |
| 2 | delisting shorts | maybe | yes | not confirmed out of sample |
| 3 | grid bots | no (short vol vs a trending asset) | yes | dead |
| 4 | HLP vault | yes (market making) | yes | decayed to ~3–8%/yr |
| 5 | CME gaps | no | yes | dead |
| 6 | first-perp short, new events | yes, for the old class only | yes | the class that works ran out |
| 7 | kimchi premium | plausible | yes | priced by funding |

Add this morning's session (`docs/02`, 2026-09-23 entries): nine literature entry features,
funding-extreme trails, equity-curve trading, mark-to-market sizing and cross-exchange funding
arbitrage, all dead. **That is seventeen more ideas tested today, and not one produces a
steady, large, safe return.** The things that *do* help (the tight exit, the market-neutral
overlay, spot-routing the 12h sleeve) are all improvements to books that get paid for bearing
risk.

**What a small account can actually do better than a fund is hold risk that a fund can't
justify.** It can't be faster than co-located bots, it can't be bigger than the capital that
floods into every structural yield, and it can't see information that the price hasn't already
absorbed through funding. The trend book plus the market-neutral overlay is what that looks
like here. The honest planning numbers are in CLAUDE.md §6, and **no search of free historical
data will produce a "perfect" machine**, because a perfect machine is exactly what big capital
removes first.

### Where genuinely new information could still come from

Every test above used historical data that thousands of others also have. The only
unexploited input left is data **that doesn't exist historically**, which has to be recorded
going forward:
- Hyperliquid publishes every open position and its liquidation price live. Liquidation
  clusters near the current price are a forced-flow map that no archive holds.
- Predicted funding (live `premiumIndex`), not just settled funding. Every test here had to use
  the previous settlement as a proxy.
- Order-book depth around settlements and listings.

None of this is a strategy. It is the raw material the next real test would need, and the
only kind of research left that isn't more mining.

---

# Part 2 — re-checking the graveyard (same day, asked: "what if an edge is sitting in there")

Rule 9 allows reopening a kill only if the measurement was broken, and three engine
measurements were broken (doc 03, #12–14). The funding one is not neutral between variants:
rules that shorten long holds were never credited with the funding they save. So the
engine-level kills and near-misses were re-scored on the corrected engine
(`backtest/graveyard_rescore.py`): real entry times, funding per unit, entry-sized
compounding, 10 orderings, each variant paired with main. The bar was **both halves, more
than 2 paired standard errors** (ordering noise only). Predictions were registered in the
file.

| variant (original verdict) | Δ tune %/mo | Δ holdout %/mo | holdout DD | worst month | now |
|---|---|---|---|---|---|
| main (deployed) | — | — | 53% | −33.5% | |
| **tight exit** (on paper) | **+2.87 ± 0.28** | **+1.98 ± 0.35** | 50% | −31.3% | **confirmed** |
| time stop < +2R after 100 bars (near-miss) | +0.25 ± 0.38 | +2.07 ± 0.56 | 43% | −20.9% | holdout only |
| time stop < 0R after 100 bars | +0.02 | +0.43 | 53% | −36.2% | dead |
| trail ×0.5 above +80R (dead) | −0.21 | +0.03 | 54% | −34.2% | dead |
| **tight + time stop 2R/100** (never run) | **+2.50 ± 0.29** | **+4.34 ± 0.48** | **45%** | **−18.2%** | **clears the bar** |
| 1h+4h (drop the 12h sleeve) | +0.79 | −0.54 | 62% | −35.1% | tune only |
| 1h+4h+8h / 1h+2h+4h / +8h | −0.05 / +0.56 / −1.01 | −0.50 / −0.22 / −0.79 | 51–63% | | dead |
| trail 20/20/12 | −0.26 | +0.19 | 54% | | dead |
| trail 10/20/40 (near-miss, holdout +4.3) | **−2.43** | −0.28 | 50% | | **worse than before** |
| 8 slots | −1.06 | −0.47 | **42%** | −21.3% | less risk, less return |
| risk ×0.67 / ×1.33 | −0.99 / +0.65 | −0.85 / +0.36 | 38% / 65% | −23% / −43.5% | a dial, not an edge |
| bb(30, 1.25) (near-miss, holdout +4.9) | −0.50 | **−0.71** | 68% | | **worse than before** |
| lean short ×3 in bears (WORKS, unshipped) | +0.86 | **−1.28** | 65% | | tune only |

**The one addition on top of what is already on paper: the time stop, measured against
TIGHT alone** (paired, same orderings):

| | Δ return | Δ drawdown | Δ worst month |
|---|---|---|---|
| tune half | −0.37 ± 0.21 %/mo | +3 pts | **+8.4 pts better** |
| holdout | +2.36 ± 0.43 %/mo | −6 pts | **+13.1 pts better** |

Read it the way doc 01 read the 1000h gate. **The worst-month improvement shows up on both
halves in the same direction, so that is the part to trust.** The return gain is
holdout-only, which is the mined-split signature, so that part is not. The mechanism fits
funding: a position still under +2R after 100 bars is dead money that keeps paying funding
while it waits. **Candidate for a sixth paper book: tight + time stop.** It is not a change
to the live config.

**Registered predictions:** time stop beats main on both halves alone ✗ (holdout only);
dropping 12h helps tune and hurts holdout ✓; 20/20/12 beats main ✗; 10/20/40 gets worse ✓;
8 slots no both-halves win ✓; bb(30,1.25) still holdout-only ✗ (now worse on both); lean
short loses its edge ✓.

**Two near-misses were artifacts.** The looser entry band and the wide slow-sleeve trail
each showed ~+4–5%/mo on the old holdout. On the corrected engine both are negative on both
halves. Both lengthen long holds, so both were being spared the funding they cost.

## Other graveyard entries re-checked, and why the rest were not

| entry | why reopened | result |
|---|---|---|
| **liquidation-cascade bounce** (day 1: +46bp, t 3.79) | no verdict was ever recorded. It had 30 days of data and measured "from the low" | **dead** on 4 years (`backtest/cascade_redux.py`, 5.9M stamps, 13 coins): forced sells bounce no more than voluntary sells (+10.5 vs +10.4bp at 30m); forced buys don't revert, they continue; fading forced sells nets −3 to +2bp |
| **options vol premium** | its note says "revisit if the premium comes back" | still gone. BTC 2026 IV − forward RV: Jan −18, Mar +13, May +4, Jul −1 vol pts (Deribit DVOL vs Binance, checked 2026-09-23) |
| meme-graduation week-long holds | the collector was left to gather forward data | only 2 days collected so far; nothing to measure yet |
| wide PIT universe (`wide_book.py`) | same engine | not re-run: the gap (+6.6% vs ≤ +0.8% holdout) is far beyond what funding could close |
| short families, market-neutral, TradFi perps, funding carry, crowd/taker flow, VSA, unlocks, copy-trading, Polymarket | | their own engines already charged funding, or died for reasons today's bugs don't touch |

**Bottom line of the re-check:** no buried edge. The corrected engine makes the tight exit
look better than it did, adds one credible risk improvement on top of it (the time stop), and
shows that two of the old "almost" results were the broken engine talking.

## The stats sheet — `backtest/book_stats.py` (log: `logs/book_stats.txt`)

$221 start, corrected engine (real entry times, funding, entry-sized compounding), 10 orderings.
Holdout = 2024-08-29 onward. **Upside shown raw AND after the 3× hindsight haircut; downside
always raw.**

| holdout | main | tight | **tight + time stop** |
|---|---|---|---|
| average month, haircut / raw | +4.9% / +10.4% | +6.8% / +13.6% | **+9.2% / +17.1%** |
| median month (raw) | −2.3% | −1.6% | **+0.6%** |
| months losing money | 57% | 56% | **48%** |
| worst month (raw) | −40.8% | −34.7% | **−22.6%** |
| typical 12 months, haircut ($221 →) | +22% ($270) | +43% ($315) | **+119% ($485)** |
| 12 months at a loss | 4% | 1% | 1% |
| max drawdown (raw) | 53% | 50% | **45%** |
| trades per month | 79 | 89 | 99 |

Full history (2020–2026), tight + time stop: average month +8.0% haircut; 48% of months losing;
worst month −24.7%; drawdown 48%; typical year +134% haircut. Calendar years raw: 2020 +265%,
2021 +3,504%, **2022 −10%**, 2023 +378%, 2024 +1,542%, 2025 +288%, 2026 +165%.

**Read the downside rows, not the upside ones.** The time stop's extra RETURN is
holdout-only (graveyard_rescore.py: −0.37%/mo on the tune half against tight alone). Its
smaller worst month and drawdown show on both halves. The raw calendar-year figures carry the
coin-selection hindsight the haircut exists for.

---

# Part 3 - "low capital is an advantage" put to the test, and refuted

*2026-09-23, later. Source: `backtest/capacity_edge.py`, log `logs/capacity_edge.txt`.*

Part 1 ended by asserting that what a small account can do better than a fund is hold what a
fund cannot. That was a claim, not a measurement, and it is the kind of claim this project is
supposed to test rather than take comfort in. So it was tested.

**The design.** Run the same cross-sectional momentum book INSIDE volume tiers - ranks 1-20,
21-60, 61-120, 121-250 and 251+ by the prior month's dollar volume, on the 793-perp
survivorship-free panel - and charge a size-dependent impact cost so the identical strategy can
be scored at $200, $20k, $200k, $2M and $20M. Impact uses the square-root law,
`sigma x sqrt(Q/ADV)`, on every name that turns over, with each coin's own trailing 30-day
volatility and dollar ADV. If the thesis is right, small tiers win at $200 and collapse by $2M.

**Registered before running:** gross spread LARGER in small tiers; smallest tier best at $200;
ordering reverses by $2M; the crossover between $50k and $500k.

## All five predictions were wrong, and the gross column says why

`gross` is account-independent, so it is the clean test of where the edge lives:

| tier | median ADV | gross/wk | net/wk at $200 | Sharpe at $200 |
|---|---|---|---|---|
| 1-20 (mega) | $412M | +0.296% | +0.358% | 0.28 |
| **21-60 (large)** | $110M | **+0.539%** | **+0.594%** | **0.61** |
| 61-120 (mid) | $40M | +0.019% | -0.004% | -0.00 |
| 121-250 (small) | $15M | **-0.227%** | -0.248% | -0.45 |
| 251+ (micro) | $5M | **-0.397%** | -0.435% | -0.90 |

**The raw edge gets monotonically WORSE as coins get smaller, and turns negative below about
$40M of daily volume.** Not smaller-but-still-positive. Negative. There is no crossover account
size either, because the small tiers were never ahead to begin with.

**So low capital is not an advantage here. It is merely not a handicap.** That is the same thing
`expectations.py` found from the other direction - capital does not change the percentage - and
it now has a mechanism attached: the coins a fund cannot trade are the coins whose cross-section
carries no signal.

## The one unpredicted result also failed

Ranks **21-60 beat the mega caps almost 2:1** on gross (+0.539% vs +0.296%) with double the
Sharpe, and it was the only tier positive in a BTC bear (+0.049% against mega's -0.615%). Since
the deployed market-neutral book trades PIT top-60 - blending both - dropping the top 20 looked
like a free improvement.

It is not. Paired against the mega tier on the SAME weeks, which is the statistic that matters
because the two tiers share the market:

| | weeks | diff/wk | t | tune | holdout |
|---|---|---|---|---|---|
| 21-60 vs 1-20 | 320 | +0.278% | **0.46** | **+0.501%** | **-0.057%** |

Positive on the tune half, negative on the holdout, t nowhere near 2. **The registered bar was
both halves AND |t| > 2. It fails.** Worth noting the mega tier's own all-sample t is 0.92 and
21-60's is 1.80 - at this sample size the tier decomposition cannot reliably attribute the
top-60 book's Sharpe 1.22 to any band inside it.

## What this closes

- **The capacity thesis is dead as a source of edge.** Small capital buys the same percentage,
  not a better one.
- **`market_neutral.py` keeps PIT top-60 unchanged.** The one candidate change failed its
  holdout.
- **Where capacity DOES bind is worth keeping:** the top-60 book stops working somewhere between
  $2M and $20M (mega +0.171%/wk at $2M, -0.236% at $20M). That is a real number and it says the
  strategy has years of headroom for this account - just no bonus for being small.

*Prediction 3 was the only one partly right: by $20M every tier is negative. Being wrong about
the direction of the size effect while right about the capacity ceiling is not a score of 1 in 5;
it is one correct claim about a strategy that does not have the property it was built to test.*

---

# Part 4 - can LEVERAGE buy the returns instead?

*2026-09-23. Source: `backtest/kelly_corrected.py`. Full table in
[doc 01](01-strategy.md#why-030-risk-per-unit-and-why-turning-it-up-does-not-work).*

If no new edge exists, the remaining lever is size. It was swept on the corrected engine, and
the answer is **no**: 0.30% → 0.45% buys +0.34%/month on the holdout and takes P(80% drawdown)
from 2.7% to 24.7%. The holdout's own growth optimum is 0.45%, below the tune half's 0.60-0.90%,
so the un-fitted data says the deployed setting is close to right rather than timid.

**Two of my four registered predictions were wrong.** I expected gross leverage to bind first -
it does not, the book runs 4.8x at p99 where 10x is the danger line. And I expected the holdout
to tolerate MORE size than the tune half; it tolerates less. Both errors were in the direction of
thinking there was more room than there is.

With Part 3 refuting the capacity thesis and Part 4 refuting the leverage one, the honest
position is that this book's return is what it is: about **+5%/month on the corrected engine at
the deployed risk, ~+7% for the tight variant**, and the ways to make it bigger all cost more
than they pay.

---

# Part 5 - BAR PHASE: a real robustness finding, and two claims I had to retract

*2026-09-23. Source: `backtest/bar_phase.py`, log `logs/bar_phase.txt`.*

Every 4h and 12h figure in this project comes from bars anchored to midnight UTC. Nothing in the
strategy says they should be - it is an accident of how Binance labels klines. Three other grids
are buildable from the 1h bars already cached. No new data, no new rule, no new risk.

**The first write-up of this section claimed the 4-phase blend was a free improvement. It is
not, and the error is more instructive than the test.** I compared the MEDIAN return across ten
orderings for one setup against the median for another. Per-ordering noise here is 0.25-0.48
%/mo, so two medians drawn from different seed outcomes differ by several tenths for no reason.
Everything below is now PAIRED: same ordering, difference taken within it, mean with a standard
error and a win count - which is what `graveyard_rescore.py` already did and this file did not.

## 1. What survives: the deployed number carries 1.3-2.4%/month of phase luck

Within-ordering spread between the best and worst phase:

| window | spread | |
|---|---|---|
| tune | **1.31 %/mo** | |
| holdout | **2.37 %/mo** | larger than the whole tight-exit edge |

That is the finding, and it is **bigger than the spread of medians I first reported (1.09%)**.
Phase 3 is the best phase on tune (+0.67%/mo, t +2.56) and the *worst* on the holdout (−0.99%/mo,
t −2.07) - a clean demonstration that the choice is noise, not signal. The deployed grid is one
draw from a distribution about 2%/month wide, and no part of the strategy justifies it.

**What to do with that:** nothing to the bot, but expectations should carry it. The honest holdout
figure for the deployed book is ±1%/month wider than any single-phase backtest implies.

## 2. What does not survive: the blend is not an improvement

Paired against phase 0, same ordering:

| | tune diff | t | holdout diff | t | holdout wins |
|---|---|---|---|---|---|
| 4-phase blend | **+0.64%/mo** | **+3.70** | **+0.04%/mo** | **+0.19** | 5/10 |

**Tune only.** By this repo's own bar - both halves - it fails. Drawdown paired is 0.1-0.2 points,
not the 4-6 I first claimed.

The one real property: the blend's standard error across orderings is **0.17-0.23 against
0.25-0.48 for single phases**. Averaging four grids genuinely makes the ESTIMATE more stable. That
is worth having for forecasting and it is not extra return.

## 3. At $200 the blend is significantly harmful, and that part is solid

Quartering the capital per book quarters the unit size. Paired, with the venue minimum enforced:

| capital | blend vs 1 phase | t | rejected |
|---|---|---|---|
| **$200** | **−0.83%/mo** | **−3.40** | **8.4%** |
| $1,000 | +0.06%/mo | +0.25 | 0.1% |
| $5,000 | +0.04%/mo | +0.19 | 0.0% |

So the blend is harmful at $200 and neutral above it. There is no capital level at which it helps.

## 4. And the retraction that matters most, because it defended an existing finding

I briefly claimed `small_capital.py` was wrong - that $221 rejects 0.24% of signals and those 5
rejections cost 0.29%/month, so the real threshold was $500 rather than $25. **The 0.24% is right.
The cost was not.** Paired on the same orderings: **−0.02%/month, t = −0.37, worse in 5 of 10.**

`small_capital.py`'s conclusion stands: at $221 the venue minimum is not the binding constraint.
CLAUDE.md and that file's docstring have been reverted, and the trap is now in the trap table -
because it produced two confident, wrong claims within one hour, on two unrelated questions.

## 5. The test that mattered most: is the TIGHT EDGE bigger than phase noise?

The phase spread is 1.3-2.4 %/mo. The tight exit is +2.87 %/mo on tune and +1.98 on the holdout -
the same order of magnitude, measured on ONE grid. If that edge only existed on the grid that
happens to be deployed, it would be phase luck and paper book #2 would rest on nothing.

Paired within each ordering AND within each phase, which isolates the rule from both noise
sources:

| phase | TUNE diff | t | wins | HOLD diff | t | wins |
|---|---|---|---|---|---|---|
| **0 (deployed)** | +2.84% | **+10.18** | 10/10 | +1.98% | **+5.73** | 10/10 |
| 1 | +3.66% | +14.22 | 10/10 | +2.52% | +5.43 | 10/10 |
| 2 | +2.69% | +7.90 | 10/10 | +1.97% | +6.23 | 10/10 |
| 3 | +2.79% | +7.79 | 10/10 | +2.45% | +4.28 | 9/10 |

**Four of four phases, both halves, t between +4.28 and +14.22, and 79 wins out of 80
ordering-by-phase combinations.** Phase 0 reproduces `graveyard_rescore.py`'s +2.87/+1.98 from a
different simulator, which is a third independent confirmation.

**This is the strongest statistical result in the project**, and it draws the distinction that the
phase work exists to draw: the phase spread and the tight edge are the same SIZE, but the spread
flips sign between halves and between phases while the tight edge does not flip anywhere. One is
noise that averages out; the other is a rule. A paired test separates them; comparing medians -
the error in Part 5's first draft - cannot.

**So paper book #2 is on solid ground**, and the tight exit is the one thing this project has that
would survive someone actively trying to break it.

## 6. And the book forked today: is the TIME STOP phase-robust?

Paper book #5 is tight + "close a long still under +2R after 100 bars". It was forked on the
reading that its RETURN gain is holdout-only but its WORST-MONTH gain shows on both halves. The
phase test checks both claims against a noise source that did not exist when the decision was
made:

| phase | TUNE return | t | HOLD return | t | TUNE worst mo | HOLD worst mo |
|---|---|---|---|---|---|---|
| **0 (deployed)** | −0.36% | −1.71 | **+2.36%** | +5.48 | **+8.4** | **+13.1** |
| 1 | +0.03% | +0.08 | **+2.79%** | +13.22 | +3.5 | +10.7 |
| 2 | +0.98% | +3.67 | **+2.51%** | +4.77 | +2.6 | +14.5 |
| 3 | +0.10% | +0.27 | **+1.91%** | +3.86 | +4.1 | +5.2 |

**Both claims hold, and they hold for different reasons:**

- **Return: holdout-only, but emphatically so.** Tune is ~zero and flips sign between phases
  (−0.36 to +0.98). Holdout is positive on every phase, t +3.86 to +13.22, **10/10 orderings on
  all four**. So this is not phase luck - it is a genuine property of the 2024-2026 period.
  Whether that is because the regime rewards cutting dead money or because the holdout is mined
  out remains undecidable, which is precisely why it runs forward instead of being shipped.
- **Worst month: shallower in all 8 cells**, by 2.6 to 14.5 points. That is the part doc 11 said
  to trust, and it now survives the phase dimension as well as the tune/holdout one.

**So forking paper book #5 was the right call and for the right reason:** it is a risk
improvement that might also be a return improvement, not the other way round.

### A limit of this whole method, stated plainly

The 1h sleeve cannot be phase-shifted (only 23 coins have sub-hourly data) and shorts are
identical on every grid by construction. So the phase test can validate **long-side** rules -
tight, the time stop - and **cannot say anything about the short boost** (paper book #4). That
book still rests on a single grid, and there is no cheap way to change that without 1m data for
all twelve coins.

## 7. ATR period: the same size of spread, but it is NOT noise

ATR(14) is Wilder's 1978 convention from commodity charts. Nothing about crypto justifies it, and
in this book it sets three things at once - the stop (2xATR = 1R), the long trail (20xATR), and
therefore the 2R spacing between pyramid adds. It had never been swept.

Registered before running: **a noise measurement, not a parameter search.** Whatever the table
said, 14 would not be changed on the strength of a sweep against a holdout this repo has already
admitted is mined out.

Paired against 14 within each ordering (deployed grid, long side only):

| ATR period | TUNE/mo | diff | t | wins | HOLD/mo | diff | t | wins |
|---|---|---|---|---|---|---|---|---|
| 7 | +3.37% | −1.51% | −5.19 | 1/10 | +3.00% | −1.87% | −4.82 | 1/10 |
| 10 | +4.41% | −0.47% | −1.78 | 3/10 | +4.13% | −0.74% | −2.47 | 2/10 |
| **14 (deployed)** | **+4.88%** | — | — | — | **+4.88%** | — | — | — |
| 21 | +4.11% | −0.77% | −2.22 | 3/10 | +4.69% | −0.19% | −0.57 | 5/10 |
| 28 | +3.87% | −1.01% | −3.78 | 0/10 | +4.30% | −0.57% | −1.46 | 4/10 |

Within-ordering spread: **2.08%/mo on tune, 2.35%/mo on the holdout** - the same magnitude as the
bar-phase spread (1.31 / 2.37).

**But it is a completely different kind of quantity, and that is the finding.** Compare the two:

| | bar phase | ATR period |
|---|---|---|
| spread | 1.31 / 2.37 %/mo | 2.08 / 2.35 %/mo |
| best on tune | phase 3 | **14** |
| best on holdout | phase 0 | **14** |
| worst on both | — (flips) | **7** |
| ordering between halves | **reverses** (phase 3 is best on tune at t +2.56, worst on holdout at t −2.07) | **stable at the extremes** |

Bar phase flips sign between halves, which is what noise does. ATR period does not: **14 is the
best of five on both halves and 7 is the worst on both.** That is a genuine parameter with a broad
optimum around 14-21, not a coin toss.

**Two consequences:**

1. **No change, and now for a reason rather than out of caution.** 14 is already the best cell on
   both halves, so there is nothing to adopt. And unlike bar phase, averaging across periods would
   be strictly worse - it would dilute the optimum toward 7 and 28.
2. **The deployed value is fortunate but not fitted.** ATR(14) came from a 1978 commodity
   convention chosen decades before this project existed, so its landing on the optimum of a
   five-point sweep on both halves is genuinely out-of-sample in the parameter dimension. That is
   the opposite of the usual "interior optimum" warning in doc 02, where the optimum was found by
   searching. Here the search came after the choice.

**And it sharpens the method:** a spread tells you how wide the distribution is; only whether the
ORDERING survives the split tells you if you are looking at a parameter or at noise. Two
quantities of identical spread can be opposite things.

---

# Part 8 - MAX_UNITS: the one genuine return improvement the search found

*2026-09-24. Source: `backtest/pyramid_params.py`, log `logs/pyramid_params.txt`.*

The pyramid is where this book earns: a position that works gets four more units funded by profit
that already exists, and `pyramid.py` found that gave **more return AND less drawdown at matched
risk** - unusual, and the largest improvement in the project's history. Its two governing numbers,
`ADD_EVERY = 2.0` and `MAX_UNITS = 5`, had never been swept on the corrected engine. `BE_AT = 3.0`
was last swept in `ddcontrol.py`, which predates funding, causal entry times and entry-sized
compounding.

Baseline is the **TIGHT** book, not main - an improvement has to beat the leading paper book.

## Two of three parameters are already right

| | result |
|---|---|
| **ADD_EVERY** | 2.0 confirmed. Tighter (1.0, 1.5) is **worse on the holdout** (−0.87%, −0.48%, 0/10 wins, t −7.5 and −6.7) and deepens the worst month to −37%. Wider (3, 4) costs tune return at t −8.7 and −12.5. Registered prediction 1 held. |
| **BE_AT** | 3.0 confirmed. 2R costs −1.13%/mo on the holdout, 5R costs −1.45%, removing it entirely costs −1.79% and takes the worst month to −41.4%. Prediction 3 held, including that removing it raises drawdown. |

## MAX_UNITS = 5 is NOT right, and this one is real

| max units | TUNE diff | t | HOLD diff | t | wins |
|---|---|---|---|---|---|
| 3 | −2.13% | −39.96 | −1.71% | −15.00 | 0/10 |
| 4 | −1.00% | −45.62 | −0.93% | −16.48 | 0/10 |
| **5 (deployed)** | — | — | — | — | — |
| **7** | **+1.30%** | **+33.24** | **+1.07%** | **+18.90** | **10/10** |
| **10** | **+2.79%** | +29.98 | **+1.73%** | +10.35 | 10/10 |

**And it survives the phase test** - both halves, all four bar grids, 10/10 orderings on every one:

| phase | 7u TUNE | t | 7u HOLD | t |
|---|---|---|---|---|
| 0 (deployed) | +1.30% | +33.24 | +1.07% | +18.90 |
| 1 | +1.56% | +33.17 | +1.58% | +21.06 |
| 2 | +1.53% | +20.88 | +1.23% | +16.30 |
| 3 | +1.37% | +14.21 | +1.17% | +20.32 |

## The control that matters: is it just betting more?

More units means more notional, so the obvious objection is that this is leverage in disguise -
the thing `escalate.py` warned about and `bull_boost.py` built a uniform control to catch. Matched
on RETURN:

| setting | HOLD/mo | DD | worst DD | lev p99 |
|---|---|---|---|---|
| 5 units @ 0.30% (deployed) | +6.77% | 50% | 55% | 5.1× |
| **7 units @ 0.30%** | **+7.80%** | **56%** | 60% | **6.3×** |
| 5 units @ 0.42% (matched return) | +7.71% | **64%** | 68% | 7.2× |
| 10 units @ 0.30% | +8.46% | 61% | 64% | 8.3× (**max 10.3× - over the line**) |
| 5 units @ 0.50% | +7.67% | 72% | 76% | 8.6× |

**Reaching 7-unit returns by raising risk instead costs 8 more points of drawdown and more
leverage.** So it is not betting more; it is a better way to deploy the same risk.

**The mechanism, and it is the same one `pyramid.py` found:** units 6 and 7 are only added once a
trade is +10R and +12R up, by which point the breakeven stop sits above entry. Those units carry
almost the full upside and almost none of the downside. Raising risk uniformly instead adds size to
every trade, including the four in five that stop out at −1R. 492 positions reach six units or
more, so this is not a handful of trades.

## What to do, and what not to

**MAX_UNITS = 7, not 10.** Ten earns more (+1.73%/mo holdout) but its maximum gross leverage hits
**10.3×**, past the line where `lev_test.py` found liquidation turns destructive. Seven runs 6.3×
at p99 and 7.8× at maximum, comfortably inside.

**It is not free.** Drawdown goes 50% → 56% and the worst month is unchanged at −31%. It is
better-than-leverage, not costless.

**And it goes to a paper book, not the live config.** That is this project's rule and today is a bad
day to break it: two claims of mine were retracted a few hours ago for exactly the kind of
confidence this result invites. It has cleared more than anything else here - both halves, four
grids, a matched-risk control and a mechanism - which is the argument for forking it, not for
shipping it.

## Part 8b - the units finding STACKS with the time stop, so the book to watch is the triple

*Added 2026-09-24 after `backtest/units_on_tstop.py` (another session) checked the one thing Part 8
left open. Verified by re-running: it reproduces, and it independently reproduces Part 8's own
number from a separate file (+1.31 ± 0.04 / +1.07 ± 0.06 against my +1.30 / +1.07).*

Part 8 measured 7 units against **tight**. The recommended book is **tight + time stop**, so the
question was whether the two rules stack or compete. They act on different positions - the time
stop closes longs still under +2R after 100 bars, units 6-7 are added at +10R and +12R - so they
should add. They do, and by more than on tight alone:

| book | tune %/mo | DD | worst mo | holdout %/mo | DD | worst mo |
|---|---|---|---|---|---|---|
| main (deployed) | +4.88 | 54% | −20.9% | +4.88 | 53% | −33.5% |
| tight (#2) | +7.75 | 42% | −29.7% | +6.86 | 50% | −31.3% |
| tight + 7 units (#6) | +9.06 | 44% | −29.8% | +7.93 | 56% | −31.2% |
| tight + time stop (#5) | +7.38 | 44% | −21.3% | +9.22 | 45% | −18.2% |
| **tight + time stop + 7 units (#7)** | **+8.89** | 48% | −23.6% | **+10.76** | 51% | −19.2% |

Paired: **+1.51 ± 0.06 tune, +1.54 ± 0.08 holdout over TSTOP, 10/10 orderings each.** Against main,
**+4.01 / +5.89**. Units adds *more* on top of the time stop (+1.54) than on tight alone (+1.07),
so the interaction is positive.

**A seventh paper book now runs it**, and the four books #2, #5, #6, #7 form a **2×2 factorial** over
{time stop, 7 units} on the tight base. That reads both main effects *and* their interaction
forward, which no single book can - and forward is the only evidence left that is not mined.

**The cost is real and is the reason this is still paper:** against TSTOP alone the triple gives up
4 points of tune drawdown and 6 of holdout drawdown, and its worst month is 2.3 points deeper on
tune - which was outside `units_on_tstop.py`'s own registered prediction of "within 2 points". The
return is the biggest in the project; the risk is not free.

---

# Part 9 - SLOTS: the cap that binds hardest, and does not pay

*2026-09-24. Source: `backtest/slots_sweep.py`, log `logs/slots_sweep.txt`.*

`MAX_UNITS = 5` was an arbitrary cap set too low. `SLOTS = 12` is the same kind of number and it
binds far harder: the live paper book's status line reads **563 signals declined for want of a slot
against 47 taken**. Twelve coins × three sleeves is 36 possible positions, so 12 slots turns away
two thirds of the book by construction. `graveyard_rescore.py` had only ever swept *downward*.

Baseline is the TRIPLE book - the best configuration measured - so an improvement has to improve on
the best. (Its 12-slot figures here, +8.86% tune / +10.74% holdout, reproduce `units_on_tstop.py`'s
+8.89 / +10.76 from a third separate file.)

| slots | TUNE diff | t | wins | HOLD diff | t | wins | DD | lev p99 |
|---|---|---|---|---|---|---|---|---|
| 8 | −2.77% | −9.65 | 0/10 | −1.21% | −2.11 | 2/10 | 33% | 4.4× |
| **12 (deployed)** | — | — | — | — | — | — | 50% | 6.8× |
| 16 | **+2.02%** | +15.01 | 10/10 | **+0.59%** | **+1.24** | 8/10 | 58% | 8.4× |
| 20 | +3.83% | +16.56 | 10/10 | +0.58% | +1.26 | 6/10 | 71% | **10.5× over** |
| 24 | +4.71% | +19.32 | 10/10 | +0.39% | +1.00 | 5/10 | 75% | 12.4× over |
| 36 | +4.24% | +17.22 | 10/10 | **−0.97%** | −2.71 | 3/10 | 80% | 18.8× over |

**More slots buys tune-half return that does not appear on the holdout** (+2.02% against +0.59% at
t 1.24), and past 16 it breaches the leverage line anyway. Nothing clears the bar.

## The control is the point of this entry

The same matched-risk control that MAX_UNITS=7 **passed**, slots=16 **fails**:

| setting | HOLD/mo | DD | lev p99 |
|---|---|---|---|
| 12 slots @ 0.30% (deployed) | +11.05% | 50% | 6.8× |
| 16 slots @ 0.30% | +11.20% | 58% | 8.4× |
| **12 slots @ 0.40%** | **+12.50%** | 60% | 9.2× |

**Raising risk at 12 slots earns MORE than adding four slots, at the same drawdown.** So extra slots
contribute nothing that plain exposure does not contribute better - they are leverage with worse
terms. Compare MAX_UNITS=7, where matching its return with 5 units cost 8 extra points of drawdown.

> Two changes that both look like "raise an arbitrary cap" gave **opposite** answers to the same
> control. That is what makes the MAX_UNITS finding worth believing: the test that confirmed it is
> a test that can fail, and here it did.

**And the 563 declined signals are not lost money.** They are declined because the slots are held by
positions that are working - which is what a 20×ATR trail on a pyramid does. The book turning away
ten signals for every one it takes is the design operating, not a constraint to relieve.

**Predictions:** 1 wrong (16 does not beat 12 on both halves), 2 right (smaller than the units gain),
3 right (20 slots breaches 10× at p99, capping the usable answer near 16), 4 right (drawdown rises
sub-linearly: doubling slots from 12 to 24 takes drawdown 50% → 75%).

---

# Part 10 - chop and liquidation: the two questions the new config had not been asked

*2026-09-24. Source: `backtest/regime_and_liq.py`, log `logs/regime_and_liq.txt`.*

## 1. In chop, every version of this book earns nothing

Mean %/month **within** each BTC regime, full history, 3× haircut:

| config | BULL | BEAR | **CHOP** | all |
|---|---|---|---|---|
| main (deployed) | +23.05% | +0.26% | **−0.16%** | +7.04% |
| tight | +30.08% | −0.43% | **+0.08%** | +8.75% |
| tight + time stop | +33.10% | −0.64% | **+0.27%** | +9.50% |
| **triple (+7 units)** | **+47.19%** | **−0.74%** | **+0.20%** | +12.57% |

Days by regime: **chop 948, bull 871, bear 581.** So the book earns approximately nothing for
**63% of all days**, and everything in the other 37%.

**And today's improvement does not change that.** It doubles bull-market return (+23% → +47%/mo)
and leaves chop at +0.20% against the deployed −0.16%. In bear it is slightly *worse* (−0.74%
against +0.26%), because tightening exits and adding units both assume something will run.

> The honest sentence: **today's work made a bull-market amplifier, not an all-weather book.** The
> time stop was supposed to help in chop by cutting dead money; it moves chop from −0.16% to
> +0.27%, which is real and is also nothing. Prediction 2 - "the triple beats the deployed book in
> chop by MORE than its overall margin" - is wrong. The margin in chop is 0.36 points against 5.5
> points overall.

## 2. Liquidation: the deployed book is nowhere near it, the triple book touches it

Gross leverage through time, with each unit contributing **from its own add bar** (the earlier
measurement applied every position's final unit count from its first moment, which overstates):

| config | median | p99 | max | % hours >10× | hours >10× |
|---|---|---|---|---|---|
| main (deployed) | 1.0× | 7.8× | 8.8× | **0.00%** | 0 |
| tight | 0.7× | 7.4× | 8.3× | 0.00% | 0 |
| tight + time stop | 0.8× | 7.9× | 8.9× | 0.00% | 0 |
| **triple (+7 units)** | 0.8× | **10.5×** | **12.2×** | **1.27%** | **731** |

**The 7-unit change is what pushes the book over the line.** `lev_test.py` put liquidation risk at
10× gross. The deployed book never reaches it; the triple book spends 731 hours above it, peaking
at 12.2×, where an ~8% adverse gap would liquidate rather than stop out.

**All 731 of those hours are in BULL regimes** (100% of the top-1% leverage hours, spanning
2023-10 to 2025-07), which is when positions are deep in profit and their stops sit above entry -
the least dangerous time to be levered. But a trailing stop does not protect against a gap on a
levered position; the exchange liquidates on margin, not on your stop.

## 3. The live bot already caps this, which means the backtest is optimistic

`blend_paper.py:511` refuses any pyramid add that would take gross notional past
`MAX_LEVERAGE = 10.0`. **The backtest does not model that cap.** So the live paper book cannot
reach 12.2× - it will log `PYRAMID BLOCKED — no margin` instead.

Measured: of 4,315 sixth-and-seventh units attempted across five orderings, **293 (6.8%) were
attempted while the book was already above 10×** and would be blocked live.

That 6.8% is a BOUND, not a measurement - it counts sixth/seventh units attempted while the book
was already over 10×, which is not the same as the number a guard would actually refuse, because a
guard also prevents the book from reaching 10× in the first place.

**`backtest/triple_capped.py` (another session, same day) does the real thing and supersedes this
bound.** Simulating the guard properly: the triple goes from **+10.78% to +10.43%/mo on the
holdout**, a cost of **−0.35 ± 0.02**, with **2.2% of adds blocked**. 5-unit books are unaffected
(−0.00 ± 0.00), which is the control that proves the guard only bites where extra units create the
exposure.

> **So the units change is worth about +1.19%/month live, not +1.54%** (the +1.54 over tight + time
> stop, less the 0.35 the guard costs). My bound of +1.44% was too generous; the measured number is
> lower and it is the one to use.

## What this means for the recommendation

- **Keep the 10× guard.** It is the reason the live book is safe where the backtest is not.
- **The triple book stays paper**, and now for a second reason: its backtest assumed leverage the
  live bot will refuse.
- **Expect +1.19%/month from the units change** (`triple_capped.py`, measured), and expect all
  of it in bull markets.
- **Nothing found today helps in chop.** 63% of days remain a flat line, and the one honest
  improvement to that number is the time stop's +0.4 points.

## Part 10b - "should we remove the 10x guard, since it costs return?"

*Asked 2026-09-24. The guard costs the triple book −0.35 ± 0.02 %/mo on the holdout
(`triple_capped.py`). Measured answer: **no**, and the reason is not caution.*

**At the triple book's peak leverage of 12.2× - the mean of the per-ordering maxima, with a
single ordering reaching 13.2× - the adverse move that liquidates the whole book is 8.2%.**
Not a drawdown of 8.2% - a forced close by the exchange at its price, on every position at
once, regardless of where your stops sit.

**Did that ever happen during the high-leverage hours?** No. Across the 929 hours above 10×, BTC's
worst 24-hour move was **−4.85%**, and not one of those hours had a trailing 24h worse than −8%. The
guard has never been needed in this sample.

**That is not evidence it is unnecessary.** For context, in the same data:

| | |
|---|---|
| BTC falls ≥8% in 24h | **1.24% of all hours** (711 of 57,545); worst ever **−46.4%** |
| SUIUSDT worst 24h | −28.5% (1,206 hours below −8%) |
| ENAUSDT worst 24h | −27.3% (1,914 hours below −8%) |
| WLDUSDT worst 24h | −34.0% (2,077 hours below −8%) |

The book holds twelve **alt** positions, and alts fall two to four times as far as BTC. The
liquidating event occurs in 1–4% of hours; the book is exposed for 1.6% of hours. Over six years
those two ranges did not intersect - and they are correlated in the **wrong** direction, because
every one of the high-leverage hours is in a bull regime (2023-10 to 2025-07), which is precisely
when violent reversals arrive. Leverage peaks late in a run because positions are deep in profit;
runs end with the kind of move that liquidates.

## The argument that settles it

**The backtest cannot model liquidation at all.** Every position in it exits at its stop, its trail
or its time stop. Forced closure at an exchange's mark is not in the model.

> So the unguarded **+10.78%/mo is not "the return with more risk" - it is the return computed in a
> world where the only risk you took on by removing the guard does not exist.** Removing it does not
> buy +0.35%/mo. It buys +0.35%/mo *in a simulation that omits the consequence*.

**The trade on offer is about +4.3%/year of compounded return against a small chance of losing most
of the account in one hour.** Keep the guard. And note what it really is: the guard is the thing that
makes MAX_UNITS=7 a safe change rather than a leveraged one. Without it, 7 units is not the
better-deployment-of-risk that the matched control proved - it is leverage that the model scores as
free.

**The 0.35% cannot be bought back by lowering risk either.** `kelly_corrected.py` puts 0.20%/unit at
−0.96%/mo against 0.30%. Paying 0.96 to recover 0.35 is not a trade.


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

# Part 5 - BAR PHASE: the first thing today that actually works

*2026-09-23. Source: `backtest/bar_phase.py`, log `logs/bar_phase.txt`.*

Every 4h and 12h figure in this project comes from bars anchored to midnight UTC. Nothing in the
strategy says they should be - it is an accident of how Binance labels klines. A 4h bar could
start at 01:00, 02:00 or 03:00, and those grids are buildable from the 1h bars already cached.
No new data, no new rule, no new universe, no new risk.

The 1h sleeve cannot be shifted (only 23 coins have sub-hourly data) and shorts are held fixed,
so everything below is attributable to the 4h and 12h LONG sleeves.

## 1. The deployed number carries about 1%/month of phase luck

| phase | TUNE/mo | DD | HOLD/mo | DD | Sharpe |
|---|---|---|---|---|---|
| **0 (deployed)** | +4.90% | 53% | **+4.97%** | 55% | 1.01 |
| 1 | +4.51% | 66% | +4.92% | 53% | 1.03 |
| 2 | +5.40% | 58% | +4.95% | 58% | 0.97 |
| 3 | **+5.69%** | 55% | +3.88% | 59% | 1.00 |

Spread: **1.18%/mo on tune, 1.09%/mo on the holdout.** I predicted at least 1.5% and overshot.

**The uncomfortable part:** on the holdout, phase 0 - the one that happens to be running - is the
BEST of the four. I predicted it would not be, because it has no reason to be. So the deployed
holdout figure of +4.97% is the top of four draws, and the honest expectation is the phase
average, **+4.68%/mo**. That is a ~0.3%/mo downward revision of the deployed book, and it comes
from an arbitrary choice nobody had questioned.

## 2. Averaging the phases is a real, free improvement

Four phase books, a quarter of the account in each, same aggregate risk:

| window | blend/mo | DD | Sharpe | mean phase/mo | mean phase DD | mean Sharpe |
|---|---|---|---|---|---|---|
| tune | **+5.58%** | **54%** | **1.24** | +5.12% | 58% | 1.09 |
| holdout | **+4.96%** | **52%** | 0.89 | +4.68% | 56% | 0.88 |
| full | **+5.92%** | **56%** | 1.07 | +5.35% | 61% | 1.00 |

The blend beats the average phase on **all three windows** (+0.46, +0.28, +0.57 %/mo) with a
**lower drawdown every time**. That was the registered prediction and the mechanism is exactly
as stated: averaging four noisy series *before* compounding removes volatility drag. It cannot
change the average edge; it only narrows the distribution around it, and narrower compounds
faster.

**Against the specific deployed phase, be precise:** +0.68%/mo on tune, **dead even on the
holdout** (+4.96% vs +4.97%), and 3 points less drawdown on both. The return gain is against a
*randomly chosen* phase, which is the honest comparison, because phase 0 being best on the
holdout is luck we cannot count on repeating.

## 3. The catch, which is a $200 problem specifically

Four books at a quarter of the capital each means every unit is a quarter the size. At $200 that
is roughly a **$3 unit against venue minimums that reach $2.28** (NEAR), so the smallest coins
would start being rejected - and `small_capital.py` established that $221 currently rejects 0%.
**This has not been simulated through `small_capital.py` and must be before it is deployed at
$200.** At $1,000+ the constraint disappears.

## What this is and is not

It is **not a new edge**. It is the removal of an arbitrary implementation choice, which buys
about **+0.3%/month against a random phase and 4-6 points of drawdown**, plus a more honest
expectation for the book already running. After a day in which every edge search failed, that is
the only thing that improved the book - and it improved it by taking luck out, not by finding
anything.


# 27. Order-flow study guide: Modules 0 to 5 (2026-10-30)

**Project:** watch about 10 Bitget USDT-perpetual pairs and test whether three signals - (1) order-book imbalance, (2) buy-wall / sell-wall persistence, (3) executed buying / selling pressure - read over 1 s, 5 s, 30 s, 1 min and 5 min, can tell you when to enter, hold and exit, **after costs**. Research hypotheses, not assumptions.

**Tags used everywhere:** **[F]** established - a documented exchange rule, or a measurement in this repo (file named). **[H]** a hypothesis. **[T]** needs a test. Numbers marked *illustrative* are invented to show arithmetic; they are not market data.

Modules: **0** where you actually start (read first) - **1** mechanics and the cost stack - **2** the three signals and price impact - **3** time windows, persistence, statistics - **4** hypotheses, success criteria, honest backtests - **5** building it (Python, WebSockets, storage, replay, paper trading, no keys).

---

## Module 0. Where you actually start

### 0.1 What this repo has already measured about your signals - DOGE perp on Bitget only

| Your signal | What was measured | Result [F] | File |
|---|---|---|---|
| 1. Imbalance (top of book) | does `(bid $ - ask $) / (bid $ + ask $)` at level 1 predict the next 10 s of the mid? 7 full days, 4 of them never used for tuning | Yes, and stable: rank correlation (IC) +0.10 .. +0.25 on all 4 unseen days. The extreme-decile signal moved the mid **+0.9 .. +1.0bp** in its direction (one tick = 1.2bp) and was right 52-56% of the time. At 30 s the IC halves, the move stays ~0.9bp. | `backtest/book_hist.py`, `logs/book_hist.txt`, doc 02 (2026-10-28) |
| 1b. Imbalance, costs | traded as a taker / as a post-only limit filled only when the tape fills it | Taker: -11.8 .. -12.3bp a trade. Ideal maker (every limit fills): -3.0bp. Realistic limit: only 20-22% fill, and **the fills are the signal's failures** (filled signals moved 4.8-5.1bp less than unfilled ones); net -2.0 .. -2.4bp per signal, **0 of 4 days positive** | same |
| 3. Executed pressure (taker flow) | in the 10 s before the biggest 1% of 10 s moves, and during them | Before: not aligned. During: strongly aligned (+0.43 .. +0.75) - it is the move itself being traded. On the 262-minute live recording, flow vs the next 60 s was -0.01 / -0.09 (a mild reversal, not a lead) | `book_hist.py` (E1); `backtest/doge_book.py` (R4) |
| Spread | does it widen before a big move? | No: one tick (1.2bp) at x1.00 of its median on six of seven days | `book_hist.py` (E1) |

### 0.2 What is genuinely open (this is your project's new ground)
1. **Wall persistence (signal 2) on crypto: never tested as a predictor here** (Module 2's lab gives a one-day *description* of walls, not a test). (The only cancel / pulled-liquidity tests were on CME Nasdaq futures for a different question, `his_cancel_proxy.py`.) The usable data is a limit: Tardis' free Bitget "incremental book" files are **top-15-level snapshots about 6.6 a second, not a diff stream**, until at least 2026-03; only 2026-06-01 and 2026-09-01 are true diff streams [F, `book_hist.py`]. Snapshots cannot tell a cancel from an execution. **You must record your own diff stream** (Bitget's public WebSocket works from this PC [F, CLAUDE.md s3]).
2. **The 1 s and 5 min windows.** The live recording was 1 s REST snapshots; the back data was read at 10 s and 30 s.
3. **Ten pairs.** Only DOGE is measured. The pair survey below says the pairs differ by 100x in the one number that matters.
4. **The three signals together.** Each was only tested alone.
5. **Using the signals to time the other books' orders.** Never tested; see 0.4.

### 0.3 The cost wall - your own worry, made exact
Bitget standard USDT-futures fees are 0.02% maker / 0.06% taker per side [F; the taker 0.0600% was confirmed on this account's demo fills, 2026-10-09; **check your own tier**]. So a round trip costs **12bp as a taker, 4bp as a maker, 8bp mixed**, plus the spread you cross. On DOGE the predicted move was about **1bp**. To clear the wall the combination has to lift the *conditional* move **about 4x if every maker order filled (it does not), about 12x as a taker.** Being right 55% of the time does not change this: DOGE's imbalance was right 52-56% of the time and still lost 12bp a trade.

### 0.4 My prior (a judgement, not a finding)
I put the chance of a retail-tradable result at 1 s - 5 min on these pairs **under one in ten**: the DOGE result is stable across four months, the measured effect is about one tick, and tick-sized moves are what co-located market makers compete away. The project is still worth doing, for three reasons: (a) wall persistence and the windows are untested, (b) a clean "real information, nothing after costs" verdict on ten pairs is itself a result that saves you months, (c) the plausible *use* is not a standalone scalper but **execution timing for the slower books**: when the trend / daily / capitulation books have already decided to buy, does the book state at that moment predict whether a market order slips, or whether waiting a few seconds with a limit order is cheaper? [H-exec, T]. Those books pay 12bp per trade and make tens of bp per trade; saving 1-3bp per fill is small but real, and it is the only way these signals "combine with other books" without needing a standalone edge.

### 0.5 The pair survey - how much room does each pair leave?
Measured by `backtest/pair_spread_survey.py` (Bitget public tickers, 24 samples 5 s apart; **two minutes at one hour of one day, a first picture, repeat at other hours**). Log: `logs/pair_spread_survey.txt`.

| pair | price | spread bp (median) | p10 .. p90 | best bid $ | best ask $ | 24h volume $M | funding / 8h, bp |
|---|---|---|---|---|---|---|---|
| BTCUSDT | 77474 | **0.01** | 0.01 .. 0.01 | 376,245 | 391,603 | 5,507 | 1.00 |
| ETHUSDT | 2213 | **0.05** | 0.05 .. 0.05 | 112,342 | 140,421 | 3,414 | 0.02 |
| SOLUSDT | 95.295 | **0.10** | 0.10 .. 0.10 | 10,511 | 13,784 | 403 | -0.31 |
| XRPUSDT | 1.2234 | **0.82** | 0.82 .. 0.82 | 39,931 | 22,932 | 317 | -0.15 |
| DOGEUSDT | 0.07509 | **1.33** | 1.33 .. 1.33 | 9,800 | 6,308 | 60 | -0.32 |
| SUIUSDT | 0.868 | **1.15** | 1.15 .. 1.15 | 2,588 | 10,577 | 65 | -0.80 |
| LINKUSDT | 10.716 | **0.93** | 0.93 .. 0.93 | 327 | 247 | 38 | 1.00 |
| AVAXUSDT | 8.334 | **1.20** | 1.20 .. 1.20 | 721 | 180 | 16 | -0.14 |
| LTCUSDT | 55.22 | **1.81** | 1.81 .. 1.81 | 174 | 414 | 13 | 0.19 |
| ENAUSDT | 0.18221 | **1.64** | 0.55 .. 3.29 | 158 | 158 | 96 | 0.50 |
| SHIBUSDT | 4.578e-06 | **2.18** | 2.18 .. 2.18 | 269 | 211 | 8 | 0.42 |
| WLDUSDT | 0.3803 | **2.63** | 2.62 .. 2.63 | 3,147 | 3,069 | 47 | -1.42 |
| NEARUSDT | 4.0824 | **0.24** | 0.24 .. 0.74 | 642 | 641 | 118 | -0.25 |
| ADAUSDT | 0.1893 | **5.28** | 5.27 .. 5.28 | 7,131 | 6,753 | 59 | 1.00 |
| ARBUSDT | 0.15577 | **1.28** | 0.64 .. 1.92 | 7,775 | 242 | 22 | -1.40 |
| DOTUSDT | 0.921 | **10.85** | 10.85 .. 10.88 | 9,255 | 6,878 | 15 | -0.70 |

*(run started 2026-10-30 02:44 UTC. An earlier, unsaved run of the same code read LINK $531 / $279 at the best bid / ask against $327 / $247 here: the size at the touch moves by 2x between samples, so one reading of depth is not a measurement of depth.)*

What it says [F for the table, H for the reading]:
- **BTC, ETH, SOL: one tick is 0.01-0.1bp.** Even a perfect "next tick" signal is worth at most a hundredth of the fee. These are controls, not opportunities.
- **Most alts sat on exactly one tick for the whole window, at 0.8-2.6bp** (NEAR lower at 0.2-0.7bp; ENA and ARB flipped between one and several ticks) - the DOGE regime (1.2-1.3bp) that was measured. [H] their tick effect is of the same order, ~1bp, so they will behave like DOGE.
- **ADA (5bp) and DOT (11bp)** have wide spreads. [H] a one-tick effect is bigger in bp there, but a taker also pays the spread, and thin books are where makers earn it and where your resting order is picked off. [T].
- **Depth at the touch is small**: LINK $327 / $247, AVAX $721 / $180, LTC $174 / $414, ENA $158 each side. A $300 market order at 1x already exceeds the best level on several of these (and at 10x it is ten times that). Slippage is a first-order cost for you, not a rounding error.
- Funding is the 8-hourly rate in bp; it matters for holds that cross 00:00 / 08:00 / 16:00 UTC, not for 1 s - 5 min holds (about 1% of 5-minute windows contain a settlement).

**Proposed 10 pairs (spread regimes, 7 of the 10 are in your trading book):** BTCUSDT and SOLUSDT (tiny-tick controls), XRPUSDT, DOGEUSDT (repeats the measured pair), SUIUSDT, LINKUSDT, WLDUSDT, SHIBUSDT (one-tick alts), ADAUSDT, DOTUSDT (wide spread). Your call; I would change nothing else until the first hour of data shows what it costs to store.

### 0.6 The bar, proposed now so it cannot move later
The combined signal earns a forward paper test only if, on held-out days that set no threshold: the flagged subset's mean gross move at its horizon is at least **2x the all-in round-trip cost of the execution style used**, with fills simulated against the tape; net mean > 0 at **t > 2 clustered by day**; positive on **at least 3 of 4 held-out days**; and the **same sign on at least 3 pairs not used to choose the thresholds**. Otherwise the thread is closed for retail on this venue, like DOGE. (Module 4 makes this formal: `backtest/order_flow_registry.py`, criteria K1-K4.) The 10 pairs were accepted on 2026-10-30: BTC, SOL, XRP, DOGE, SUI, LINK, WLD, SHIB, ADA, DOT.

---

## Module 1. The mechanics and the cost stack

### Lesson 1.1 Orders, bid / ask, spread, maker and taker

1. **Simple English.** The *bid* is the highest price someone is waiting to pay; the *ask* is the lowest price someone is waiting to sell at; the *spread* is the gap. A *market order* says "fill me now at whatever is there" - you **take** liquidity. A *limit order* says "only at this price or better" - it sits in the book and you **make** liquidity, if anyone ever trades with it.
2. **Mechanically.** The exchange's matching engine keeps every resting limit order sorted by price, then by arrival time (*price-time priority*: first in, first filled at a price). A market buy removes sell orders from the lowest price upward until your size is filled, so a big order *walks the book* and gets worse prices as it goes. A *post-only* limit order is rejected instead of crossing, which guarantees you pay the maker fee.
3. **Why it matters here.** Every signal in the project is a claim about who wins the next few ticks. The first design decision for any trade is taker (certain fill, pay spread + the larger fee) or maker (cheap, but you may not fill, and you tend to fill when you are wrong - Lesson 1.3).
4. **Example** (*illustrative*, price near 100). Asks: 500 units at 100.01, 800 at 100.02, 1,500 at 100.03. Bids: 600 at 100.00, 900 at 99.99. You market-buy 1,200: 500 at 100.01 and 700 at 100.02.
5. **Formula.** Mid = (bid + ask)/2 = 100.005. Average fill = (500 x 100.01 + 700 x 100.02) / 1,200 = 120,019 / 1,200 = **100.01583**. Cost vs mid in bp = (average fill - mid) / mid x 10,000 = 0.01083 / 100.005 x 10,000 = **1.08bp**. Of that, 0.50bp is half the spread (unavoidable for a taker) and 0.58bp is walking the book (grows with your size).
6. **Measuring it.** From a book snapshot: walk your order size through the levels, as above. From the trade tape: the *effective spread* is 2 x |trade price - mid before the trade| / mid, for trades whose aggressor side is known.
7. **Limits and failure modes.** The book you see is old by the time you act (latency); displayed size is not guaranteed (orders vanish as price approaches); hidden and iceberg orders exist; depth from one snapshot says nothing about how it behaves over a minute.
8. **Interaction.** The hourly books (trend, daily, capitulation) pay this once a trade, and 1-2bp is noise against their 12bp fee and their tens of bp of edge - that is why they can exist. A sub-minute signal pays it every time and has no such cushion.

### Lesson 1.2 The cost stack: fees, spread, slippage, funding, leverage, spot vs futures

1. **Simple English.** Cost per trade = what the exchange charges + the price you give up by crossing the spread + the extra price you give up if your order is larger than what sits at the best price + (for perpetuals) the funding payment if you hold across a settlement.
2. **Mechanically.** *Fees* are a percentage of order value on each side. *Slippage* is average fill vs the price you expected. *Funding*: a perpetual contract has no expiry, so every 8 hours (00:00, 08:00, 16:00 UTC in this repo's perp archive [F, `strategy_analysis/data/perps/*_funding.csv.gz`, checked on DOGE: 6,793 settlements, all at those three hours]; that archive is Binance's, so **confirm the interval of each Bitget pair you record** - some contracts settle more often) longs pay shorts or shorts pay longs `rate x position value`, which keeps the contract near spot. *Leverage* lets position value exceed your money; it multiplies gains, losses **and fees** on your equity, and sets a liquidation price about `1/L` away (minus a maintenance margin). *Spot* = you own the coin: no funding, no liquidation if unleveraged, shorting needs borrowing, and fee tiers differ from perps (look yours up). *Perps* = symmetric long / short, margin, funding, liquidation.
3. **Why it matters here.** It is the wall in 0.3. Leverage is not an edge: it scales the fee as much as the move.
4. **Example** (*illustrative*, spread 1.2bp, signal gross +1.0bp, as on DOGE). Taker: fees 12bp + crossing half the spread on each leg (0.6 + 0.6) = **13.2bp** -> net **-12.2bp**. Ideal maker on both legs, every order fills: 4bp -> net **-3.0bp**. At **10x** the same trade is +10bp gross, -132bp cost = **-1.22% of equity per round trip**; three of them cost 3.7% before any loss from being wrong. Funding: a long held across a +1bp-per-8h settlement pays 1bp of position value, i.e. 10bp of equity at 10x.
5. **Formula.** `net = g - (f_in + f_out) - s - funding`, where `g` is the signed gross move in the direction of the trade, `f` the fees, `s` spread + slippage, and funding = rate x (number of settlements held, signed by side). On equity with leverage `L`: `net_equity = L x net`. Liquidation distance ~ `1/L - maintenance` (the repo's scenarios use `1/L - 0.5%`).
6. **Measuring it.** Fees: your fee page, then confirm on demo fills (done for taker). Spread and depth: the survey above, then the live recorder. Slippage: replay your size through the recorded book. Funding: the per-coin 8-hourly history (the repo's perp archive has it for all 864 USDT perps, dead ones included).
7. **Limits and failure modes.** The commonest backtest error is charging fees on notional but forgetting that a maker order that does not fill is an opportunity cost; or assuming mid-price fills. Fee tiers change with volume; promotional rates change.
8. **Interaction.** `scalp_1m.py --kelly` and doc 02's leverage entries already show this: leverage cannot change the sign of an average, only its size. At 30x the 12bp round trip is 3.6% of the account.

### Lesson 1.3 Expected value, conditional probability, and why "right" is not "profitable"

1. **Simple English.** A signal can call the direction correctly more often than not and still lose money if the moves it catches are smaller than the cost of trading them.
2. **Mechanically.** You care about the *conditional* expectation: the average move **given** the signal fired, not the overall average. Two separate qualities: **reliability** (how often is it right - hit rate, rank correlation) and **profitability** (average net money per trade). A signal can have high reliability and negative profitability.
3. **Why it matters here.** This is the exact worry in your brief, and it is the single most important idea in the project. Step 4 of your plan measures them separately for this reason.
4. **Example** (*illustrative*, fixed-size moves). Signal moves the price `m` bp in your favour when right and `m` against when wrong, right with probability `p`. Taker cost C = 12bp. At m = 1bp you would need p = 6.5 - impossible. At m = 30bp you need p = 0.70. Maker cost C = 4bp (if filled): m = 10bp needs p = 0.70; m = 20bp needs p = 0.60. **Real DOGE data:** p about 0.55, m about 1bp.
5. **Formula.** `E[net] = P(win) x W - P(loss) x L - C`. With equal W = L = m: `E = (2p - 1) x m - C`, so the break-even hit rate is `p* = 1/2 + C/(2m)`. Conditional probability: the **lift** is `P(up | signal) - P(up)`; a lift of 5 points is a 55% signal.
6. **Measuring it.** On non-overlapping samples: hit rate with a confidence interval, mean gross move in the signal's direction, mean net after your cost model, and rank correlation (IC) between the signal and the future move. Report all four; never only the first.
7. **Limits and failure modes.** *Overlapping samples* (a signal that persists for 30 s counted every second) inflate every t-statistic; *clustering* (ten pairs signalling in the same market-wide minute are one event, not ten); *selection* (thresholds picked on the same data they are scored on).
8. **Interaction.** This is the repo's validation protocol (CLAUDE.md s2) in miniature: charge 12bp, hold out the last 40%, test by distinct day, record the prediction first.

### Check yourself (answers at the bottom)
- **E1.** Using the Lesson 1.1 book, you market-buy **1,500** units. Average fill, and cost vs mid in bp?
- **E2.** A signal's average gross move is +3bp in its direction. Taker cost is 12bp fees + 1bp half-spread on each leg. What is the net per trade, and what gross move would break even?
- **E3.** Both legs maker (4bp), every order fills, hit rate 60%, fixed-size moves. What move size `m` breaks even?

**Answers.** E1: (500 x 100.01 + 800 x 100.02 + 200 x 100.03) / 1,500 = 150,027 / 1,500 = 100.018; cost vs mid = 0.013 / 100.005 = **1.30bp**. E2: cost = 12 + 2 = 14bp, net = 3 - 14 = **-11bp**; break-even needs a **14bp** gross average. E3: (2 x 0.6 - 1) x m = 0.2m >= 4 -> **m >= 20bp**.

---

## Module 2. The three signals and price impact

**What the exchange gives you, and what it does not.** Two public feeds carry everything below. (a) The **book feed**: messages of the form "price P now holds total size Q" (Q = 0 deletes the level). It is **aggregated by price level**: you see the total resting at 0.10040, never the individual orders in it [F: the Tardis/Bitget format, `strategy_analysis/data/book_hist/bitget/`; confirm on the live feed in Module 5]. (b) The **trade tape**: every print with its price, size and the **aggressor (taker) side**. Signals 1 and 2 come from (a), signal 3 from (b), and a wall can only be understood by reading (a) and (b) together.

**The lab.** `backtest/order_flow_lab.py` (log: `logs/order_flow_lab.txt`) measured one day of real DOGE data, 2026-06-01 (5.5 million book updates, 86,232 prints). It is **descriptive**: three pictures to learn from, not tests. Predictions L1-L5 were written in the file before it ran. 2026-09-01, the other true diff day, was left unread. Every number tagged [lab] below is from that day and that one pair; do not generalise it.

### Lesson 2.1 Order-book depth and imbalance (your signal 1)

1. **Simple English.** Is there more money waiting to buy than waiting to sell near the current price? The side with less money resting is "thin": it takes less buying to push the price up through it.
2. **Mechanically.** Sum the dollars resting on each side over the nearest `k` levels (or within `X` basis points of the mid): `B` for bids, `A` for asks. The imbalance `I = (B - A) / (B + A)` lies between -1 (all sell side) and +1 (all buy side). The **microprice** weights each side's best price by the *other* side's size, so it sits closer to the thin side: `(P_ask x Q_bid + P_bid x Q_ask) / (Q_bid + Q_ask)`. Why it might predict: a thin ask is cheaper to consume, and market makers lean their quotes the same way.
3. **Why it matters here.** It is the signal the repo has measured: on DOGE, imbalance at the first level predicted the next 10 s with IC +0.10 to +0.25 on four unseen days, but the move was about one tick (+0.9bp) [F, `book_hist.py`]. What is unknown is whether deeper bands, other pairs, other windows, or the combination do better.
4. **Real example** [lab A]. The day's first snapshot: best bid 0.10038 holds **$16,345**, best ask 0.10039 holds **$36**. Level-1 imbalance **+0.996**. Over the nearest 5 levels: bids $220,067 vs asks $241,039 -> **-0.045**. Over 20 levels: $897,361 vs $760,339 -> **+0.083**. The microprice is +0.50bp above the mid (half the spread, because the ask is almost empty). One instant, three different answers: the sign depends on how deep you look.
5. **Formula, step by step.** Level 1: `(16,345 - 36) / (16,345 + 36) = 16,309 / 16,381 = 0.9956`. Level 5: `(220,067 - 241,039) / (220,067 + 241,039) = -0.0455`. In general `B_k = sum over i <= k of P_i x Q_i` and `I_k = (B_k - A_k) / (B_k + A_k)`. A band version uses all dollars with `|P - mid| / mid <= X bp`.
6. **Measuring it.** At each sample time, rebuild the book from the diff stream and take sums over **bands in bp, not level counts**. Levels are not comparable across your pairs: one tick is 0.013bp on BTC, 1.0bp on DOGE and 10.9bp on DOT [F, `logs/pair_spread_survey.txt`; BTC's tick is inferred from its 0.01bp spread], so "20 levels" is about 0.26bp on BTC, 20bp on DOGE and 217bp on DOT. Then compare the imbalance with the mid change over the next window, on non-overlapping samples.
7. **Limits and failure modes.** Level 1 is dominated by tiny orders ($36 flips the sign). Resting size can be withdrawn instantly (Lesson 2.2). In a trend the imbalance can be a *consequence* of the move, not a cause. If you only ever look at the sign of one number you will confuse the first hundredth of a tick with a trade.
8. **Interaction.** Imbalance describes *intent* (what is resting); flow (2.3) describes *action* (what traded). A wall (2.2) changes the imbalance mechanically, so any deep-band imbalance result must be re-run with walls removed before you credit "imbalance".

### Lesson 2.2 Walls: persistence, cancellation, replenishment, execution (your signal 2)

1. **Simple English.** A wall is a level with unusually large resting size: a buy wall below the price, a sell wall above. The folk story is "walls are support and resistance". The accurate version is: **a wall is a promise that costs nothing to withdraw until someone trades into it.** The question is whether the promise is kept when price arrives.
2. **Mechanically.** The size at a price changes for exactly three reasons: (i) a new limit order arrives (size up - an *add*, or a *replenishment* if it follows a trade); (ii) an order is *cancelled* (size down, **no print** on the tape); (iii) a market order trades against it (size down, **and a print at that price** whose aggressor is the opposite side). So over any interval:

   `change in size = added - cancelled - executed`.

   You observe the change (book feed) and the executed part (tape). You do **not** observe `added` and `cancelled` separately - only their net. So `cancelled = size lost - executed` is a **lower bound** (a cancel hidden by an add in the same interval is invisible), and you cannot tell one large order from fifty small ones, or an iceberg refilling from new orders. **Persistence** = how long the level keeps most of its size. **Replenishment** = size coming back after being consumed. **Executed share** = tape volume at that price / size lost there.

   What a wall could mean - three rival stories, which is the whole research question: **(a) support**: price arrives, the wall absorbs the flow and price turns; **(b) decoy**: the wall is pulled as price approaches and the move continues through it; **(c) noise**: it is a market maker's quote ladder following the mid, which carries no information. A single test cannot support one story without ruling out the others.
3. **Why it matters here.** It is your signal 2 and the one this repo has never measured on crypto. Most of what is written about it is stories (a) and (b) without data.
4. **Real numbers** [lab C, `logs/order_flow_lab.txt`]. Wall = at least 5x the median of the 10 nearest levels and at least $20,000, found in the 20 nearest levels. On the day: **2,288 walls**, median size $154,268 at first sight.
   - **Persistence:** median lifetime **15 s**; 29% gone within 5 s, 62% within 30 s, 95% within 5 min.
   - **Replenishment:** only 3% added back at least half of their starting size while followed.
   - **Fate:** of the $497 million that left the followed levels, **99.8% was cancelled and 0.2% executed.**
   - **But look at how close they came:** only **188 of the 2,288 ever came within 3bp of the mid, and 12 within 1bp**; 1,401 never came closer than 5bp. The executed share rises with proximity: 0% (never within 5bp), 3.9% (within 3bp), 29% (within 1bp). And the sanity check that the tape matching works: within 1bp of the mid, **82%** of what left ($874k of $1.07M) was executed.
   - **Reading:** nearly all "wall" liquidity on a 1bp-tick coin sits far from the price, is never tested, and is withdrawn as the quote ladder is re-set. That is story (c), normal and not manipulation. The *informative* sample is the small fraction price actually reaches: about 190 a day within 3bp on this day.
5. **Formula, step by step.** For each followed level: `removed = sum of decreases`; `executed = sum of tape volume at that price on the consuming side` (taker buys hit asks, taker sells hit bids); `cancelled = max(removed - executed, 0)`; `cancel share = cancelled / removed`; `lifetime = time it fell below half its peak - time first seen`. Example (*illustrative*): a wall of 10,000 units at 10.01 ($100,100); 3,000 print there; it falls to 1,000. `removed = 9,000`, `executed = 3,000`, `cancelled = 6,000`, cancel share 6/9 = 67%.
6. **Measuring it.** Record the book feed and the tape on one clock. Define a wall *relative to local depth* (a multiple of the median level in a bp band) and in absolute dollars. Define **approach** by the distance of the best opposing price from the wall in bp. Follow the wall until it falls below half its peak or is consumed. **The conditioning event is the approach**: a wall never approached cannot have predicted anything.
7. **Limits and failure modes.** (i) The book is aggregated: no order IDs. (ii) "First seen" is not "born": the lab sees a level when it enters its 20-level window, which on DOGE is only ~20bp wide, so its birth-distance numbers (many near 19-20bp) are a window artifact. (iii) Every threshold (5x, $20k, 50%) is a choice; the conclusion must survive changing them. (iv) Book messages and prints are stamped separately, so an execution can appear a few milliseconds before or after its book update; sums over a whole episode reduce this. (v) Your own recorder's latency. (vi) Survivorship: only the walls that stayed visible long enough to be seen get counted. (vii) Acting on walls invites being the target of someone who places them to move you; on regulated markets that is spoofing and illegal, on crypto venues assume it happens [H].
8. **Interaction.** Wall + flow is the natural pair: a wall's promise is tested only by flow arriving at it. *Held under heavy taker selling* is absorption (story a); *pulled while flow arrives* is a decoy (story b). A wall also inflates deep imbalance, so imbalance and wall features are not independent.

### Lesson 2.3 Executed buying and selling pressure (your signal 3)

1. **Simple English.** A trade happens when someone crosses the spread: the *aggressor* (taker) is the impatient side. More dollars of aggressive buying than aggressive selling in a window means buying pressure.
2. **Mechanically.** Every print carries price, size and the aggressor side. **Signed flow** in a window `w`: `F_w = sum of (+price x size for taker buys, -price x size for taker sells)`. **Flow share** = `F_w / total traded dollars`, between -1 and +1. (In the literature "order-flow imbalance" often means the change in best bid / ask *sizes*, a book quantity. To avoid confusion this guide says **taker flow** for the tape quantity.)
3. **Why it matters here.** Signal 3, and the quantity that moves the price mechanically. It is also the test every book signal faces.
4. **Real numbers** [lab B]. 86,232 prints (about one a second). Net taker dollars vs the mid change in bp, non-overlapping windows:

   | window | bins | same-window rank correlation | bp of mid per $100k net flow | next-window rank correlation |
   |---|---|---|---|---|
   | 1 s | 86,398 | +0.49 | 2.9 | +0.036 |
   | 5 s | 17,278 | +0.45 | 3.1 | +0.017 |
   | 30 s | 2,878 | +0.38 | 3.6 | -0.021 |
   | 1 min | 1,438 | +0.42 | 3.8 | -0.035 |
   | 5 min | 286 | +0.42 | 4.0 | -0.085 |

   Flow and price move **together** in every window (that is price impact: the flow *is* the move). Flow read at the end of a window says almost nothing about the *next* window on this day (absolute correlation at most 0.085; the 1 s value, +0.036 on 86k bins, is statistically distinguishable from zero but explains about 0.1% of the variance; the 5 min value has a standard error near 0.06). This agrees with the earlier results (`book_hist.py`: flow aligned only *during* a move; `doge_book.py` R4: a mild reversal).
5. **Formula, step by step.** `F_w = sum_i s_i x q_i x p_i`; `share = F_w / sum_i q_i x p_i`; `delta_mid(bp) = (mid_end - mid_start) / mid_start x 10,000`; impact slope `beta = cov(F_w, delta_mid) / var(F_w)`. Example (*illustrative numbers, measured beta*): buys $90k, sells $30k -> `F = +$60k`, share +0.5; with beta = 3.5bp per $100k the same-window move is about **+2.1bp**.
6. **Measuring it.** Use wall-clock bins, **non-overlapping** for any test, and keep two columns apart: the move *inside* the window (contemporaneous, mechanical) and the move *after* it (the only part that can be a signal). For several pairs, scale flow by that pair's trailing traded dollars.
7. **Limits and failure modes.** The great trap: using flow measured through the end of a window to "predict" that same window's move - it looks superb and is circular. Other traps: the aggressor flag depends on the venue (verify on live data); one parent order split into many prints looks like persistent small flow (which is the genuinely interesting part: does signed flow stay autocorrelated? [T]); one huge print can dominate a window (use counts or caps); fake volume on some venues [H].
8. **Interaction.** Flow supplies *timing*, the book supplies *context*. Flow also *causes* the cancellations and executions that make walls disappear, so flow and wall features are measured on the same events.

### Lesson 2.4 Market microstructure and price impact

1. **Simple English.** Prices move because people trade through resting orders, and because other people react to what they see. A big buyer pushes the price up *and* tells everyone a buyer is around.
2. **Mechanically.** Impact has a **temporary** part (the cost of walking the book; makers re-quote and it fades) and a **permanent** part (information: the market raises its estimate of value because the trade might be informed). Market makers quote two sides, earn the spread, and lose when they trade against someone who knows more (**adverse selection**). So they widen spreads, shrink size and cancel quickly when they sense informed flow. That is why walls vanish (2.2) and why **your resting limit order tends to fill precisely when it is wrong**: the people who hit it are the ones selling into a falling price.
3. **Why it matters here.** It explains why every signal above is small and why costs decide the project, and it tells you what a maker order really costs.
4. **Real numbers.** Impact slope on DOGE in the lab: **3-4bp of mid per $100k of net taker flow** in the same window [lab B]. Adverse selection on DOGE with tape-simulated limit orders: filled signals moved **4.8-5.1bp less** in the signalled direction than unfilled ones; net -2.0 to -2.4bp per signal; fill rate 20-22% [F, `book_hist.py`].
5. **Formula, step by step.** Kyle's linear form `delta_p = lambda x Q` (the `beta` above is the estimate of lambda). The square-root law (impact grows roughly with the square root of size) is reported across equities and futures [documented in the literature; **[T] on Bitget - not measured here**]. Adverse selection of a maker order = `E[move | signal not filled] - E[move | signal filled]`.
6. **Measuring it.** Regress the mid change on signed flow by window and by time of day; in a replay, compare the moves after filled and unfilled hypothetical orders (as `book_hist.py` does).
7. **Limits.** Lambda changes with volatility, time of day and news; impact is not linear; the lab's slope is one pair on one day.
8. **Interaction.** For your own order size the picture is mild: at 3.5bp per $100k, a $300 order is about 0.01bp of aggregate impact. The cost that bites is the **thin touch** (the survey: best-level depth often under $300 on the alts) and the spread plus fee, not your effect on the market.

### Lesson 2.5 How the three fit, and where they conflict
They answer different questions: the **book** says what people *say* they will do, **walls** say whether that is *credible*, **flow** says what they *did*. Candidate conditional patterns (all **[H]**, none a finding): *absorption* (heavy taker selling into a bid wall that holds); *pull* (a wall disappears as flow arrives); *thin side + flow the same way* (momentum); *imbalance contradicting flow* (fade?). Each becomes a pre-registered hypothesis in Module 4, with its approach event, window, horizon and cost model written down first.

### What the lab predicted, and what it found
| | registered before the run | found [lab] |
|---|---|---|
| L1 | same-window correlation clearly positive and **growing with window length**; next-window absolute correlation under 0.10 | positive everywhere (+0.38 to +0.49) - **wrong that it grows** (strongest at 1 s); next-window at most 0.085 - right |
| L2 | median wall lifetime under 30 s | 15 s - right |
| L3 | more than 70% of what leaves a wall is cancelled | 99.8% - right, **for a boring reason**: almost none of it was ever approached |
| L4 | cancels mostly far from the touch; executions within 1bp | 96% of cancelled dollars left more than 3bp out; 94% of executed dollars within 1bp - right |
| L5 | under 25% replenished | 3% - right |

Four of five right is not a reason to trust my intuition: L3 and L4 are nearly guaranteed by where walls sit on a 1bp-tick coin.

### What this means for the build (Module 5)
- Record **both feeds on one clock** for the 10 pairs; store the raw messages and compute features offline.
- Define walls and imbalance in **bp bands**. On BTC even 200 levels cover only ~2.6bp, so a wall 10bp away is invisible to a 200-level feed; on DOT 20 levels is ~217bp. [H: check what depth the live Bitget feed delivers per pair.]
- The lab's day was 5.5 million book updates for one pair. Ten pairs is tens of millions a day: measure the first hour's size and compress before committing disk.
- Draft hypotheses for Module 4: **H-imb** (band imbalance -> next window, per pair and horizon); **H-approach** (given a wall within X bp, does it hold or get pulled, and does that predict bounce vs break); **H-flow** (does flow share predict the *next* window; expected near zero from the lab); **H-combo** (approach + flow + imbalance); **H-exec** (does the book state at the moment a slower book orders predict slippage or the benefit of waiting).

### Check yourself (Module 2)
- **E4.** Treat the price as 100 at every level so dollars = units x 100. Bids: 400 at 100.00, 600 at 99.99, 3,000 at 99.98. Asks: 100 at 100.01, 900 at 100.02, 1,500 at 100.03. Find the imbalance over 1 level and over 3 levels, and the level-1 microprice minus the mid in bp.
- **E5.** A 20,000-unit ask wall sits at 100.05. 5,000 units print there as taker buys, and the level now shows 8,000. How much was removed, executed, cancelled, and what is the cancel share?
- **E6.** In one window taker buys are $90k and sells $30k; beta is 3.5bp per $100k. What is the flow share and the expected same-window move? Why can you not trade the window you measured it in?

**Answers.** E4: `I_1 = (400 - 100) / 500 = +0.60`; `I_3 = (4,000 - 2,500) / 6,500 = +0.231` (bids 400 + 600 + 3,000, asks 100 + 900 + 1,500). Microprice = `(100.01 x 400 + 100.00 x 100) / 500 = 100.008`; mid = 100.005; difference 0.003 = **0.30bp**. E5: removed 12,000; executed 5,000; cancelled 7,000; cancel share 7/12 = **58%**. E6: share = `(90 - 30) / 120 = +0.5`; `F = +$60k`, expected move `0.6 x 3.5 = +2.1bp`. You only know `F` when the window has ended, and by then the move it describes has already happened; the tradable question is what the *next* window does, and the lab's next-window correlations are about zero.

---

## Module 3. Time windows, persistence, and the statistics of overlapping samples

**The lab.** `backtest/window_lab.py` (log: `logs/window_lab.txt`, tests: `tests/test_window_lab.py`, 10 tests) measured the same DOGE day as Module 2, 2026-06-01, on a 1-second grid (86,399 seconds). Descriptive again: five pictures, not a strategy. Predictions W1-W6 were written in the file first. 2026-09-01 is still unread. Numbers tagged [lab] are one pair, one day.

**A bug the lab caught in itself, which is the best lesson in this module.** My first printout showed taker flow over the last 5 seconds predicting the *next* second with IC **+0.199** - five times Module 2's +0.036. Too big to believe, so I looked. The book row labelled second `i` is the book as of the *start* of that second, but the trades binned at `i` happen *after* it, inside the very second being predicted. Including them is look-ahead by one bin. Rebuilt from earlier seconds only: **+0.029** (in line with Module 2). The same second's flow alone correlated **+0.63** with that second's move, because the flow *is* the move. The feature is now built by `known_flow_share`, and a test fails on the old version. Moral: every feature needs a timestamp rule written down - "known at the *start* of second `i`" - and a test that proves it.

### Lesson 3.1 Windows: lookback, horizon, holding - and which horizons can pay at all

1. **Simple English.** "A 1-minute window" can mean three different things: how far *back* you look to compute the signal (the **lookback**), how far *forward* you ask it to predict (the **horizon**), and how long you actually *hold* (the **holding period**). Your five windows (1 s, 5 s, 30 s, 1 min, 5 min) should be tested as lookbacks and as horizons separately, not as one number.
2. **Mechanically.** The mid price moves in whole ticks and mostly does a random-walk-like thing, so its typical move over `h` seconds grows with `sqrt(h)`: **`sigma_h = sigma_1 x sqrt(h)`**. A signal's value over a horizon is roughly its correlation with the move times the move's size, so a signal can be strongest at a horizon where the move is far too small to pay for a trade.
3. **Why it matters here.** It decides which of your 25 lookback-horizon pairs are even worth testing. Costs are fixed in bp (4bp ideal maker, 12bp taker round trip); move sizes are not.
4. **Real numbers** [lab 1]. Mid change from `t` to `t + h`, every start second:

   | horizon | std (bp) | std / (std at 1 s x sqrt h) | mid did not move | moved more than 4bp | moved more than 12bp | std / 12bp |
   |---|---|---|---|---|---|---|
   | 1 s | 1.00 | 1.00 | 71% | 1% | 0% | 0.08 |
   | 5 s | 2.32 | 1.04 | 35% | 8% | 0% | 0.19 |
   | 30 s | 5.56 | 1.02 | 10% | 38% | 4% | 0.46 |
   | 1 min | 7.78 | 1.01 | 6% | 54% | 10% | 0.65 |
   | 5 min | 17.24 | 1.00 | 3% | 79% | 43% | 1.44 |

   The `sqrt(h)` law holds almost exactly (the third column). Among the moves that were not zero, **up and down were 50/50 at every horizon** on this day. At 1 s the mid does not move in 71% of windows and moves more than 4bp in 1%: **no 1-second signal can pay a 4bp cost on average, whatever its accuracy.** Only at 30 s and beyond are moves routinely large enough to be worth a fee.
5. **Formula, step by step - what correlation does a signal need?** For a signal in its top fraction `q` of readings, with correlation (IC) `rho` to a move of standard deviation `sigma_h`, the expected move is approximately

   `E[move | top q] = rho x sigma_h x m(q)`, with `m(10%) = 1.755`, `m(5%) = 2.063`, `m(1%) = 2.665`

   (the average of a standard normal above its top-`q` cut-off; exact for jointly normal variables, approximate for fat-tailed prices [F, standard result]). Setting this equal to a cost `C` gives the **required IC**: `rho* = C / (m x sigma_h)`. Check against `book_hist.py`: IC 0.175 at 10 s with `sigma_10` about 3.2bp gives 0.175 x 3.2 x 1.755 = **1.0bp**; it measured +0.9bp.

   | horizon | `sigma_h` | observed IC of imb1 [lab 2] | expected move in the top 10% | IC needed to cover 4bp (maker, if filled) | IC needed to cover 12bp (taker) | observed / needed (maker) |
   |---|---|---|---|---|---|---|
   | 1 s | 1.00 | +0.270 | 0.47bp | 2.28 (impossible) | 6.8 | 0.12 |
   | 5 s | 2.32 | +0.225 | 0.92bp | 0.98 | 2.95 | 0.23 |
   | 30 s | 5.56 | +0.111 | 1.08bp | 0.41 | 1.23 | 0.27 |
   | 1 min | 7.78 | +0.103 | 1.41bp | 0.29 | 0.88 | 0.35 |
   | 5 min | 17.24 | +0.057 (not distinguishable from 0) | 1.72bp | 0.13 | 0.40 | 0.43 |

   **This is the central tension of the project: the signal is strongest where the move is too small, and the move is big enough only where the signal has faded.** Selecting rarer readings raises `m` (top 1% -> 2.665) but cuts the number of trades and assumes the relation stays linear in the tails [T].
6. **Measuring it.** `sigma_h` from the pair's own mid series per horizon (it differs by pair and by time of day); the IC on non-overlapping samples (Lesson 3.3); then the table above for each pair.
7. **Limits and failure modes.** Normality is an approximation; the table is a back-of-envelope screen, not a backtest; the 71% "no change" at 1 s is partly the one-tick structure (the survey: DOGE's spread is one tick of 1bp), so on a pair with a smaller tick the zero share would be smaller; a window that starts inside a news minute is not typical.
8. **Interaction.** **Lookback and horizon are separate axes.** A 1-second or 5-second lookback is a fine *feature* (the book changes fast); a 1-second *horizon* is not tradable. So test lookbacks {1, 5, 30, 60, 300 s} against horizons {30 s, 1 min, 5 min} first (15 cells, not 25), and treat the 1 s and 5 s horizons as diagnostics only.

### Lesson 3.2 Persistence and decay

1. **Simple English.** A signal is only useful while it still describes the future. *Persistence* is how long a feature keeps its value (is it still "bid-heavy" ten seconds later?). *Decay* is how fast its power to predict fades as the horizon lengthens.
2. **Mechanically.** Persistence = the **autocorrelation** of the feature at lag `k` (corr of the value now with the value `k` seconds ago). Decay = the IC of the feature with the move over the next `h` seconds, as `h` grows. For a simple persistent series (AR(1) with coefficient `phi`) the half-life of its autocorrelation is `ln(0.5) / ln(phi)`.
3. **Why it matters here.** It answers your "when to hold and when to exit": the natural holding time is about how long the information lasts. A signal whose IC halves in 5 seconds does not justify a 5-minute hold.
4. **Real numbers** [lab 2]. Autocorrelation of the feature itself:

   | feature | lag 1 s | 5 s | 30 s | 60 s | 300 s |
   |---|---|---|---|---|---|
   | imb1 (top level) | 0.58 | 0.26 | 0.11 | 0.08 | 0.05 |
   | imb5 | 0.69 | 0.41 | 0.24 | 0.20 | 0.14 |
   | imb20 | 0.92 | 0.76 | 0.38 | 0.24 | 0.08 |
   | band10 (depth within 10bp) | 0.84 | 0.68 | 0.43 | 0.33 | 0.21 |

   IC with the next `h` seconds (non-overlapping samples; sample counts in `logs/window_lab.txt`):

   | feature | h = 1 s | 5 s | 30 s | 1 min | 5 min |
   |---|---|---|---|---|---|
   | imb1 | +0.270 | +0.225 | +0.111 | +0.103 | +0.057 |
   | imb5 | +0.124 | +0.110 | +0.075 | +0.041 | +0.074 |
   | imb20 | +0.036 | +0.030 | +0.009 | +0.007 | -0.101 |
   | band10 | +0.125 | +0.110 | +0.076 | +0.053 | +0.063 |
   | taker flow, previous 5 s | +0.029 | +0.028 | +0.005 | -0.010 | -0.065 |

   Two facts. **The slow features are the weak ones**: imb20 is the most persistent at short lags (0.92 at one second) and predicts almost nothing (+0.036); imb1 flickers (0.58, half-life about 1.3 s) and carries nearly all the information. And **taker flow persists but does not predict**: the flow share in non-overlapping windows has lag-1 autocorrelation +0.214 at 1 s, +0.168 at 5 s, +0.142 at 30 s, +0.091 at 1 min and 0.000 at 5 min - buying does beget buying for seconds to a minute (one parent order split into many prints [H]) - yet its IC with the *next* price move is about zero.
5. **Formula, step by step.** `acf(k) = corr(x_t, x_{t+k})`. For imb1, `acf(1) = 0.58`, so treating it as AR(1): half-life = ln 0.5 / ln 0.58 = 1.3 s. The IC decay above is the empirical half-life of its *predictive* power: from 0.270 to 0.111 between 1 s and 30 s, to about half again by 5 min.
6. **Measuring it.** Compute `acf` of every feature at the lags that match your windows; compute IC against each horizon on non-overlapping samples; plot both. Look for the horizon at which IC has fallen to half: that is the first guess for the holding period.
7. **Limits and failure modes.** Persistence is not predictiveness (flow); an IC that is stable on one day may differ on another (that is why the later days stay unread); with 287 five-minute samples the standard error of an IC is about 0.06, so the 5-minute column is noise.
8. **Interaction.** For *exits*: when the feature that justified the entry flips (imb1 turns against you) its predictive value is gone within seconds, but the cost of exiting is the same 12bp-or-4bp whether you exit early or late. For the *other books*: their signals persist for days, which is why a half-second imbalance can only ever help them with *how* to execute, not *whether*.

### Lesson 3.3 Samples, overlap, and what your sample size really is

1. **Simple English.** If you check a signal every second against "the move over the next 30 seconds", consecutive checks share 29 of their 30 seconds. They are not 86,000 independent tests; they are closer to 2,900. Treating them as independent makes every result look far more certain than it is.
2. **Mechanically.** The t-statistic of a correlation, `t = rho x sqrt((n - 2) / (1 - rho^2))`, assumes `n` independent samples. Overlapping targets (and persistent features) break that, so the real standard error is larger. Three honest ways to measure: (a) **non-overlapping samples** - take one every `h` seconds; (b) **a shifted-feature null** - move the feature around the clock by a random lag of an hour or more, which keeps its persistence and destroys any relation to the future, repeat 200 times, and see how big an IC pure chance makes; (c) **cluster by day** (or by time block) so a market-wide minute counts once.
3. **Why it matters here.** It is the difference between "t = 34" and "t = 6" for the very same signal, and between a real finding and a recording artifact. It also governs ten pairs: they share one market, so their signals are correlated and are not ten samples.
4. **Real numbers** [lab 3], imb1 against the next `h` seconds:

   | h | IC, overlapping | naive t | IC, non-overlapping | honest t | t inflated by | null sd of the IC | p against the shifted null |
   |---|---|---|---|---|---|---|---|
   | 1 s | +0.270 | 82.4 | +0.270 | 82.4 | 1.0x | 0.0038 | 0.005 |
   | 5 s | +0.221 | 66.5 | +0.225 | 30.3 | 2.2x | 0.0057 | 0.005 |
   | 30 s | +0.116 | 34.3 | +0.111 | 6.0 | 5.8x | 0.0093 | 0.005 |
   | 1 min | +0.087 | 25.6 | +0.103 | 3.9 | 6.5x | 0.0116 | 0.005 |
   | 5 min | +0.023 | **6.6** | +0.057 | **1.0** | 6.8x | 0.0157 | **0.149** |

   (0.005 is the smallest p that 200 shifted draws can show.) The IC itself barely changes; the **confidence** changes enormously. At 5 minutes the naive method would announce t = 6.6; the honest ones say t = 1.0 and p = 0.15: nothing there. Up to 30 s the inflation is close to `sqrt(h)` (2.2 against sqrt 5 = 2.2; 5.8 against sqrt 30 = 5.5); beyond that it is smaller than `sqrt(h)` (6.5 and 6.8 against 7.7 and 17) because the feature stops persisting. **A second real example from this repo:** the sweep study's first printout gave a long holdout trade mean of -0.20% with "t +3.6", because it averaged day means while the mean was per trade; clustered by day it is **t -2.5** (`logs/sweep_confluence.txt`, doc 02, 2026-10-30).
5. **Formula, step by step.** `t = rho x sqrt((n - 2)/(1 - rho^2))`; with `rho = 0.116` and `n = 86,369` this is 34.3; with the same `rho = 0.111` and the `n = 2,879` non-overlapping samples it is 6.0. The shifted-null p-value is `(1 + number of shifted ICs at least as large in absolute value) / (1 + number of draws)`.
6. **Measuring it.** Always report, side by side, the non-overlapping IC with its `n`, the shifted-null p, and (for several pairs or days) the clustered version. Use more than one offset for the non-overlapping grid (starting at second 0, 1, 2 ...) and check they agree.
7. **Limits and failure modes.** Non-overlapping sampling throws data away (it is the honest price); the shifted null assumes the feature's persistence is stationary; a random circular shift of one *day* still keeps that day's regime in both series; two pairs signalling in the same minute are one event.
8. **Interaction.** For the multi-pair project: a market-wide flush makes every pair's imbalance and flow move together, so the 10 pairs' results must be pooled with time-block clustering and never counted as ten independent confirmations. "Same sign on at least 3 unused pairs" (the Module 0 bar) is a *consistency* check, not an independent-sample count.

### Lesson 3.4 Multiple testing: how many "signals" pure noise produces

1. **Simple English.** If you try enough combinations, some will look significant by luck. Five lookbacks x five horizons x three signals x ten pairs is 750 combinations; at the usual 5% line you expect about 38 "discoveries" with no real signal at all.
2. **Mechanically.** Each test has a false-positive chance `alpha`; over `m` tests you expect `m x alpha` false positives. **Bonferroni**: require `p < alpha / m` (so `alpha / m` per test). **Holm** is the same idea applied step by step and is never weaker. A cleaner defence still: **fewer, pre-registered hypotheses** and **data nobody has looked at**.
3. **Why it matters here.** Your plan has many knobs, and the repo's own history is full of results that were the best of a search (CLAUDE.md s2: "the holdout is mined out").
4. **Real numbers** [lab 4]. 1,000 cells built from **shifted** features (4 features x 5 horizons x 50 random shifts - features with no link to the future):
   - **naive overlapping |t| > 2: 46% of the cells**; |t| > 3: 33%; the largest naive |t| was **25.8**.
   - **non-overlapping |t| > 2: 4%** (the honest expectation is about 5%); |t| > 3: 0.5%; the largest was **3.8**.
   - The 20 real cells of the day: naive |t| > 2 in 19; non-overlapping in 13; with a Bonferroni cut for 20 cells (|t| > 3.0), naive 19 and non-overlapping 12. The 12 survivors are all four book features at horizons from 1 s to 1 min (imb1 at four horizons, imb5 and band10 at 1, 5 and 30 s, imb20 at 1 and 5 s) and **none at 5 minutes**.
   - **Significant is not big.** imb20 at 1 s has t = +10.6 and survives every correction, yet its IC is 0.036: expected top-10% move `0.036 x 1.00 x 1.755 = 0.06bp`. Statistics says "real", the cost table of Lesson 3.1 says "worthless". Always read both.

   Read the 3.8 twice: **searching 1,000 honest cells, the best pure-noise cell reaches |t| 3.8.** A single "t = 3.5" found by looking through a thousand cells means nothing.
5. **Formula, step by step.** Expected false positives `= m x alpha` (750 x 0.05 = 37.5). Bonferroni per-test level `= alpha / m` (0.05 / 750 = 6.7e-5), which for a two-sided normal is `|t| > 3.99`; for 20 cells the cut-off is `|t| > 3.02`. Holm: sort the `m` p-values ascending; compare the `i`-th to `alpha / (m - i + 1)`; stop at the first failure.
6. **Measuring it.** Count your cells **before** looking and write the number down; apply the cut-off for that number to non-overlapping (or clustered) t-statistics; confirm on days that played no part in choosing anything.
7. **Limits and failure modes.** Bonferroni is conservative for correlated tests (your cells are correlated, so the true cut-off is a bit lower); a pre-registered small set is better than a corrected large one; "I only looked at the ones that seemed promising" counts as having tested them all.
8. **Interaction.** This is why Module 0.6 asks for the **same sign on unused pairs and held-out days**: a result that survives a correction *and* replicates elsewhere is the only kind that has ever survived in this repo.

### Lesson 3.5 Reliability vs profitability, ties, base rates, and the clock

1. **Simple English.** "Right 55% of the time" and "makes money" are different claims, and "right" itself needs a definition when the price often does not move at all.
2. **Mechanically.** Report four things separately: **hit rate** among moves that actually happened (up-share of non-zero moves); the **zero share** (windows where nothing moved); the **IC** (rank correlation, robust to size); and the **conditional mean move** after the signal (in bp, gross and net of cost). The **base rate** is what you would get with no signal: here, 50% up among non-zero moves.
3. **Why it matters here.** At short horizons ties dominate (71% of 1-second windows), so a hit rate computed over all windows is mostly "no change". And the clock matters: a test pooled over the whole day mixes busy and quiet regimes.
4. **Real numbers** [lab 1, 5]. Base rate: **50% of non-zero moves are up at every horizon** on this day (no drift to exploit). The clock, by 4-hour block (UTC): the standard deviation of a 1-minute mid move is 6.3-7.1bp in five blocks and **11.3bp in 12-16 UTC** (a factor of 1.6-1.8), and traded dollars are $17.1M in that block against $5.1M in the quietest (a factor of 3.4). The net taker share of dollars swings from -0.21 to +0.27 by block, so "which side was aggressive" is a different story in each part of the day.
5. **Formula, step by step.** `hit rate = ups / (ups + downs)` (ties excluded and reported); lift `= hit rate - base rate`; conditional net mean `= mean(signed move | signal) - cost`. Exercise E7 below combines these.
6. **Measuring it.** Stratify by time of day and by volatility regime; never split train and test at random (adjacent seconds are neighbours): split by **whole days**, earlier for tuning and later for the read.
7. **Limits and failure modes.** One day of one pair (this lab) says nothing about the others; time-of-day patterns can themselves be mined; a signal that works only in the 12-16 UTC block is a different, narrower claim (and a smaller sample).
8. **Interaction.** The books you already run trade on hours-to-days scales and ignore this; the order-flow project would be the first with a strong time-of-day dependence, so it needs the stratified tests from the start.

### What the lab predicted, and what it found
| | registered before the run | found [lab] |
|---|---|---|
| W1 | random-walk scaling within 0.6-1.4; more than 70% of 1 s windows unchanged; 20-60% of 5 min windows beyond 12bp | ratios 1.00-1.04; 71% unchanged (just); 43% - right |
| W2 | imb1 IC falls monotonically 1 s -> 5 min; under 0.05 at 5 min | monotone (0.270, 0.225, 0.111, 0.103, 0.057) - right; 0.057 is **above 0.05** (but within its 0.06 standard error) - half wrong |
| W3 | imb1 autocorrelation above 0.4 at 1 s and under 0.15 at 60 s; flow lag-1 above +0.05 | 0.58 and 0.08; +0.168 at 5 s - right |
| W4 | naive t at 30 s at least 3x the honest t | 34.3 vs 6.0 = 5.8x - right |
| W5 | imb1 -> 5 s and -> 30 s have p < 0.05 against the shifted null | both 0.005 (the floor) - right |
| W6 | naive null-cell rate above 25%; honest 2-10% | 46% and 4% - right |

Five of six right and one half-wrong. The finding that was not predicted at all was the alignment bug above; it was caught only because a number disagreed with an earlier lab.

### What this means for Module 4
- **Cut the grid before looking.** Lookbacks {1, 5, 30, 60, 300 s} x horizons {30 s, 1 min, 5 min} = 15 cells per signal, not 25; the 1 s and 5 s *horizons* are diagnostics (their moves are 0-2 ticks).
- **Two keys for any claim:** a non-overlapping (or day-clustered) t above the multiple-testing cut-off for the registered cell count, **and** a shifted-feature null p below 0.01.
- **Stratify the clock** (at least busy vs quiet hours) and **split by whole days**.
- **Compute the required IC first** (Lesson 3.1) and drop any cell where it exceeds what the data could possibly show.
- Draft hypotheses from Module 2 now carry their lookbacks and horizons; Module 4 turns each into a registered form.

### Check yourself (Module 3)
- **E7.** A feature has IC +0.12 with the next 30 s, where `sigma_30` = 6bp. Expected move in its top 10%? What IC would you need to cover a 4bp maker round trip?
- **E8.** You test a signal against the next 60 seconds on every second of a day (86,399 samples) and get `rho = 0.02`. What naive t does that give? If the effective sample is closer to `n / 60`, what is the honest t?
- **E9.** You will look at 5 lookbacks x 5 horizons x 3 signals x 10 pairs. How many false positives do you expect at the 5% level with no real signal, and what Bonferroni per-test level and |t| cut-off does that imply?

**Answers.** E7: `0.12 x 6 x 1.755 = 1.26bp` (about a third of 4bp); required IC `= 4 / (1.755 x 6) = 0.38`. E8: naive `t = 0.02 x sqrt(86,397 / 0.9996) = 5.88`; honest with `n_eff` about 1,440: `0.02 x sqrt(1,438 / 0.9996) = 0.76` - nothing. E9: `750` cells -> `37.5` expected false positives; per-test level `0.05 / 750 = 6.7e-5`, which is `|t| > 3.99`.

---

## Module 4. The scientific protocol: hypotheses, honest backtests, and deciding whether an edge is real

**What exists now.** (1) `backtest/order_flow_registry.py` - the project's hypotheses, success criteria, cost model and power arithmetic **as code**, pinned by a SHA-256 digest; `judge()` applies the criteria mechanically; tests in `tests/test_order_flow_registry.py` (9 tests, 19 of 19 deliberate breaks caught). (2) `backtest/protocol_lab.py` (log: `logs/protocol_lab.txt`, 9 tests, 12 of 12 deliberate breaks caught) - three demonstrations on the DOGE teaching day: the winner's curse, right-but-unprofitable, and how long to paper trade. Numbers tagged [lab] are one pair, one day. Predictions P1-P5 were written in the file before each run; the ones I got wrong are shown.

**The ground rule of the whole module:** *the criteria are fixed before the data exist.* The registry was written on 2026-10-30, before a single order-flow message for the ten pairs has been recorded. Changing a number in it fails a test; changing it on purpose requires an entry in `AMENDMENTS` saying why and what had already been seen.

### Lesson 4.1 From an idea to a testable hypothesis

1. **Simple English.** "Order-book imbalance seems to matter" is an idea. A *hypothesis* says exactly what you will measure, in which direction, over what horizon, on which data, how you will trade it, what it costs, and what result would prove you wrong - all before you look.
2. **Mechanically.** Every registered hypothesis carries: the **claim** (one sentence); the **feature** (with its timestamp rule); the **lookbacks and horizons** (these set the *cell count*, `m`); the **population** (which pairs, and which are used for tuning vs left unseen); the **signal rule** and **exit**; the **cost model**; and the **criteria**. The cell count `m` fixes the statistical cut-off: `|t| >= z(1 - alpha / (2 m))`.
3. **Why it matters here.** You have thousands of possible combinations (Lesson 3.4). A registered handful turns "search until something looks good" into "ask five questions and accept the answers". It also protects you from me: the registry binds my own future analysis too.
4. **The five registered hypotheses** (`order_flow_registry.REGISTRY`):

   | id | claim in one line | cells `m` | cut-off `|t|` | my prior: statistics (K1) | my prior: pays after costs |
   |---|---|---|---|---|---|
   | H-imb | band imbalance (imb1, 5bp band; lookbacks 1/5/30 s) predicts the move over 30 s / 1 min / 5 min | 18 | 2.99 | 70% | 3% |
   | H-flow | taker-flow share over a lookback ending *before* the decision predicts the move (5 lookbacks x 3 horizons) | 15 | 2.94 | 15% | 1% |
   | H-approach | a wall >= 30 s old, not shrinking, that price approaches within 3bp is traded through less often than an ordinary level, and trading the bounce pays | 2 | 2.24 | 30% | 3% |
   | H-combo | imb1 rank, known 30 s flow and "no wall pulled in 10 s" all agreeing beats the best single signal at the same trade frequency | 2 | 2.24 | 30% | 3% |
   | H-exec | delaying a marketable order of a slower book up to 30 s while imb1 is against it saves >= 1bp | 2 | 2.24 | 25% | 20% |

   The "priors" are my judgement, written down so I can be scored on them; they are not findings. Common design: 8 alt pairs split into **tune pairs** XRP, SUI, LINK, WLD and **test pairs** DOGE, SHIB, ADA, DOT; BTC and SOL are **controls**; the first 10 recorded UTC days **tune** (thresholds only), every later day **confirms**, read once.
5. **Formula, step by step.** Cut-off for `m` cells at overall level 5%: `z(1 - 0.05 / (2m))`. For H-imb `m = 18`: `z(1 - 0.00139) = 2.99`. The four criteria (all must hold):
   - **K1** honest t (per-trade mean, errors clustered by UTC day) `>=` the cut-off, **and** shifted-null `p < 0.01`;
   - **K2** mean gross move `>= 2 x` the all-in round-trip cost of the registered execution style, **and** mean net `> 0` (H-exec: mean saving `>= 1bp`);
   - **K3** at least 20 confirm days, 200 confirm trades, net positive on at least 75% of days, same sign on at least 3 of the 4 test pairs;
   - **K4** (H-combo only) beats the best single signal at matched frequency, paired by day, `t >= 2`.
6. **Measuring it.** Run the hypothesis' own code on the confirm days once, build the results dictionary, call `judge(hid, results)`; it returns the verdict and the line-by-line reasons.
7. **Limits and failure modes.** A registered hypothesis can still be wrong or uninteresting; the priors can be badly calibrated; DOGE has already been looked at, so it is *not* an unused pair for H-imb (stated in the registry). Registration controls what you *test*, not whether the idea is good. The commonest failure is amending the criteria after seeing the data and calling it registered - so amendments are logged as amendments.
8. **Interaction.** Doc 22 (the decision rule) governs the main machine; this registry is the same idea for a new project. If an order-flow hypothesis ever passes, it becomes a candidate for a *forward paper book* run exactly like the others, never a deployment.

### Lesson 4.2 Look-ahead bias and data leakage

1. **Simple English.** A backtest cheats when, at the moment it makes a decision, it already knows something it could not have known. *Look-ahead* = using the future. *Leakage* = information from the test data flowing into the training choices.
2. **Mechanically.** Five entrances for the future: **(a) timestamps** (a feature built from data stamped at or after the decision); **(b) fitted constants** (thresholds, means, quantiles computed on the whole sample, test included); **(c) selection** (choosing which rule, pair or day to report after seeing outcomes); **(d) split mistakes** (neighbouring seconds in both train and test; random splits of time series); **(e) the data itself** (a feed that was repaired afterwards, survivors only, aggregated rows that hide order of events).
3. **Why it matters here.** At 1-second resolution a one-bin error is a 1-second look-ahead, and 1 second is the whole prediction. The project's history is a list of exactly these.
4. **Real cases from this repo and this module:**
   - **(a)** Module 3's lab: flow over the last 5 s "predicted" the next second with IC **+0.199**; with the trades of the predicted second removed, **+0.029** (the same second's flow alone: +0.63). One bin.
   - **(b)** the protocol lab's mutation "thresholds fitted on the whole day" is caught by a test that scrambles the read segment and checks that the rule and its in-sample figures do not move.
   - **(c)** the winner's curse below: the real search by mean reported +3.60bp in-sample, -0.14bp out of sample.
   - **(d)** CLAUDE.md's "bar label read as entry time" (a 4-hour bar's label is 3 hours before its close): a "+0.481R" short boost was 118 look-ahead trades; causally +0.305R.
   - **(e)** Tardis' free Bitget book files before mid-2026 are top-15 *snapshots*, not diffs: a wall's "cancel" cannot be told from an execution there; and the aggregated book hides individual orders.
   - and a statistics leak: the sweep study's t-statistic averaged day means while the printed mean was per trade, so a negative mean printed a positive t.
5. **Formula / tests, step by step.** There is no formula, there are three tests every feature must pass: **truncation** - recompute the feature on data cut right after the decision second; it must not change. **Scrambled future** - randomise everything after the decision; the feature must not change. **Shuffled null** - move the feature by hours; if the result survives, the result was never about the feature. `tests/test_sweep_confluence.py` and `tests/test_window_lab.py` implement the first two for the two feature builders.
6. **Measuring it.** Write the rule "known at the **start** of second `i`" next to each feature; build the feature from a function that is only allowed data stamped strictly earlier; put the truncation test in the test file *before* the first run.
7. **Limits and failure modes.** Tests only catch the leaks you thought to test for; the most dangerous leaks are in the data pipeline (clock offsets between exchange timestamp and local timestamp; the book's `timestamp` vs `local_timestamp`) and are invisible to unit tests. **A result that is too good is the alarm**: the +0.199 was caught only because it disagreed with an earlier lab by a factor of five.
8. **Interaction.** The slower books in this repo already follow these rules (real entry times, funding, no look-ahead); the order-flow project must meet the same standard at a thousand times the resolution.

### Lesson 4.3 Realistic backtests: costs, fills, latency, size

1. **Simple English.** A backtest earns real money only if its fills could have happened. Assuming you buy at the mid, at once, in any size, for the maker fee, is the quickest way to an imaginary edge.
2. **Mechanically.** Model each execution style honestly. **Taker**: you cross the spread and walk the book - cost `= 2 x taker fee + spread + slippage`. **Maker**: you rest an order and wait; `book_hist.maker_fill` fills it only when (i) a taker trade prints *through* its price (the whole level was cleared) or (ii) cumulative taker volume *at* its price reaches the queue ahead of you, after a 0.5 s latency and for at most 10 s; if it never fills, **there is no trade** and no profit or loss. **Funding** is charged if a settlement falls inside the hold. Size: your order walks the recorded book, not the mid.
3. **Why it matters here.** Your worry - the edge smaller than the cost - is decided entirely by this layer, and the maker route has a trap: you fill when you are wrong.
4. **Real numbers.** [`book_hist.py`, DOGE, four unseen days] a post-only limit at the touch filled **20-22%** of signals; the filled ones moved **4.8-5.1bp less** in the signalled direction than the unfilled; net **-2.0 to -2.4bp per signal**, positive on 0 of 4 days. [lab B, DOGE 2026-06-01, read on the last 40%] the imb1 decile rule:

   | horizon | trades | right (among moves that happened) | gross | net after the ideal maker 4bp | net after the taker 12bp |
   |---|---|---|---|---|---|
   | 5 s | 1,226 | **76%** | +0.79bp (se 0.06) | -3.21bp | -11.21bp |
   | 30 s | 199 | 64% | +1.46bp (se 0.35) | -2.54bp | -10.54bp |
   | 1 min | 99 | 61% | +2.02bp (se 0.75) | -1.98bp | -9.98bp |
   | 5 min | 21 | 60% | +2.79bp (se 3.39) | -1.21bp | -9.21bp |

   **Right 76% of the time, and it loses 3.2bp even as an ideal maker.** That is Lesson 1.3's point with real numbers. (The longer horizons earn more per trade but the standard errors swallow them.)
5. **Formula, step by step.** `round_trip_cost_bp`: taker `= 2 x 6 + spread` (DOGE spread 1.33bp -> 13.33bp), maker `= 2 x 2 = 4bp` (before adverse selection), mixed `= 2 + 6 + spread / 2`. Net per trade `= gross - cost - funding`. The registry requires gross `>= 2 x cost`: against the 8bp for ideal maker or 26.7bp for taker on DOGE, the lab's best gross (+0.79bp at 5 s) is about a tenth of the maker bar.
6. **Measuring it.** Replay the recorded book and tape (not bars): a signal at second `T` creates an order with its latency and size; the fill model decides; the exit repeats the same logic. Report fill rate, the fill-conditional move (adverse selection), gross, net, and the cost components separately.
7. **Limits and failure modes.** Queue position is a model (`qf` 1.0 vs 0.5 changes little because fills come from trade-throughs); real latency from your PC is unknown until measured; the book you see is a snapshot of a stream you rebuilt; fee tiers and promotions change; a replay that never lets your order move the market is right for $300 and wrong for $30,000.
8. **Interaction.** This is also how H-exec will be judged: the saving per order is `cost(send now) - cost(wait)`, both simulated on the recorded book at the paper books' own order times.

### Lesson 4.4 Overfitting, out-of-sample, and the winner's curse

1. **Simple English.** If you try many rules and keep the best, the best looks better than it is - by luck. The expected luck grows with the number of rules tried. Only data the search never touched tells you what is left.
2. **Mechanically.** Split **by whole days**: tune first, then read the rest *once*. Fit thresholds on tune data only. Prefer selection by **t** (mean over standard error), which penalises few-trade noise, to selection by the raw mean, which rewards it. Always compare the winner with what *pure noise* achieves under the same search (the shifted-feature null).
3. **Why it matters here.** The repo's own caveat: "the holdout is mined out". An out-of-sample set is a consumable.
4. **Real numbers** [lab A, DOGE 2026-06-01; 60 rules = 4 book features x 5 entry quantiles x 3 horizons; tune = first 60% of the day, read = last 40%]:

   | search | what it picked | in-sample | out of sample |
   |---|---|---|---|
   | **real features, by raw mean** | imb5, q 0.90, 300 s (36 trades) | +3.60bp | **-0.14bp** |
   | 50 **shifted** (no-signal) features, by raw mean | 300 s in 39 of 50 draws | mean **+2.92bp** (10th-90th: +1.36 .. +5.51) | mean **+0.04bp**, positive in 46% of draws |
   | **real features, by t** | imb1, q 0.90, 5 s (2,074 trades) | +0.72bp, **t 15.3** | **+0.79bp** (109%) |
   | 50 shifted features, by t | mixed horizons | best t: median **2.13**, 10th-90th 1.30 .. 2.71 | mean -0.39bp, median -0.01 |

   Read it in this order. **(1)** Pure noise, searched, hands you a "+2.9bp" winner and delivers nothing. **(2)** The real search by mean made the same mistake: it chose a 36-trade 300-second fluke over the genuine imb1 signal (+0.79bp, standard error 0.06). **(3)** Choosing by t finds the real rule, and its t of 15.3 is far outside what the best noise rule reaches (at most 2.7 in 90% of draws). I predicted the selection would pick a book rule at 5-30 s with 40-100% retention (it did not, by the mean) and, for the t-version, a null median t of 2.2-3.2 and out-of-sample within +-0.3bp (it was 2.13 and -0.39): the lesson survived, my numbers were a little off.
5. **Formula, step by step.** The median of the largest `|t|` among `K` independent noise cells solves `(1 - 2(1 - Phi(x)))^K = 0.5` (`null_max_abs_t`): K = 1 -> 0.67; 15 -> 2.00; 100 -> 2.70; 1,000 -> 3.39 (Module 3's single 1,000-cell draw reached 3.8, above the median, as a draw may). The 60 rules above are correlated, so they behave like fewer independent cells (observed median 2.13 against 2.53 for 60 independent). For Sharpe ratios the same logic is the **Deflated Sharpe Ratio**, `SR0 = sqrt(V) x ((1 - g) z(1 - 1/N) + g z(1 - 1/(N e)))` with `g = 0.5772` (Bailey and Lopez de Prado), implemented in `backtest/dsr_check.py`, where the machine's holdout half keeps a DSR of 0.03 at 1,000 tried ideas.
6. **Measuring it.** Compute the winner's in-sample score and *the distribution of winners on shifted features under the same search*; report the winner's percentile in that null. Keep a log of how many rules/cells you have looked at (the cell count `m` of the registry).
7. **Limits and failure modes.** Selecting by t is better, not immune (best noise t was 2.7 in 90% of draws, i.e. above 2); walk-forward schemes still leak if you re-tune after each peek; the confirm days can be spent only once - if a hypothesis fails there, the honest options are "rejected" or "amended and re-recorded on new days", never "retuned on the same days".
8. **Interaction.** The registry's tune / confirm / test-pair split is the multi-pair version of this lab's first-60% / last-40%; the two-key rule (honest t over the cut-off *and* shifted-null p < 0.01) is the t-selection result written as a criterion.

### Lesson 4.5 Is the edge credible? The final scoreboard, and how long to paper trade

1. **Simple English.** A credible edge has five properties at once: it is *large* compared with its cost, *statistically honest*, *replicated* on data and pairs it never saw, *stable* across the day and across regimes, and *capable of absorbing your size*. A paper-trading period is the last, cheapest, out-of-sample test.
2. **Mechanically.** Report, for every cell, a fixed scoreboard: reliability (hit rate among non-zero moves, IC) **separately from** profitability (mean gross, mean net, per cost model); the honest t and the shifted-null p; the cost components; the number of trades and distinct days; the busy-vs-quiet split; the controls (BTC, SOL); and `judge()`'s line-by-line verdict. **Paper trading** = the frozen rules run live on the same feeds: each decision is logged with its timestamp *before* the outcome, fills come from the live book with the queue model, and no parameter changes.
3. **Why it matters here.** Your final aim is a decision: build on this, park it, or drop it. The scoreboard makes that decision a lookup, and the stop rule makes it final.
4. **Real numbers** [lab C]. Independent trades needed to detect a true mean per trade (80% power, two-sided 5%), from each horizon's measured sd per trade, and how long the lab's trade rate would take:

   | horizon | sd per trade | trades per day | trades for 0.5bp | trades for 1bp | trades for 2bp | days for 1bp |
   |---|---|---|---|---|---|---|
   | 5 s | 2.15bp | 3,065 | 145 | 37 | 10 | 0.0 |
   | 30 s | 4.98bp | 498 | 780 | 195 | 49 | 0.4 |
   | 1 min | 7.41bp | 248 | 1,726 | 432 | 108 | 1.7 |
   | 5 min | 15.52bp | 52 | 7,567 | 1,892 | 473 | 36.0 |

   Two consequences. For the fast horizons the **trade count is not the constraint** (a day produces thousands); the constraint is that a day is one cluster of one market, which is why the registry demands **at least 20 distinct confirm days** whatever the trade count. And the effect sizes that matter here are tiny against the sd: detecting a real +1bp at 5 minutes needs 1,892 independent trades, about 36 days of this day's trade rate.
5. **Formula, step by step.** `n = ((z_alpha/2 + z_power) x sd / mu)^2` with `z = 1.96` and `0.84` (`trades_needed`): `mu = 1bp, sd = 5bp` gives `(2.80 x 5)^2 = 197` trades. The economic bar then asks for more than detectability: gross `>= 2 x cost`, i.e. 8bp for an ideal maker round trip: ten times the lab's 5-second gross (+0.79bp) and still about three times its best figure (+2.79bp at 5 minutes, which is noise).
6. **Measuring it.** `judge(hid, results)` on the confirm days; then the paper period: pre-declare its length (at least the 20 days), the metrics, and a **kill rule** (for example: net per trade below zero with a one-sided p < 0.1 after 10 days stops the test).
7. **Limits and failure modes.** Paper trading cannot reveal your own market impact or true latency; a profitable paper period in one regime says little about another; the more hypotheses survive to paper trading, the more pre-registered hypotheses you have effectively run - keep the global count. **Do not move to real money on a paper result alone**: doc 22 sets the repo's own conditions for that, and they are stricter than this project's bar.
8. **Interaction.** If a hypothesis passes, it enters the Analyst-desk style of forward test (frozen rules, logged predictions, retired at its review date); it is never wired into the main machine's code while the code freeze (to 2027-04-09) stands.

### What the protocol lab predicted, and what it found
| | registered before the run | found [lab] |
|---|---|---|
| P1 | null searches: in-sample best above +1.0bp, out of sample within +-0.5bp of zero | +2.92bp and +0.04bp - right |
| P2 | the real search picks a book rule at 5 s or 30 s keeping 40-100% out of sample | picked imb5 at 300 s, -4% retained - **wrong** (the search by mean chases noise) |
| P3 | the selected real rule's out-of-sample gross is below 4bp | -0.14bp - right (trivially) |
| P4 | imb1 decile rule: right 52-62% at 5 s / 30 s, gross +0.5 to +1.5bp | gross +0.79 / +1.46bp right; **right 76% / 64%: above my range** |
| P5 | by t: real picks a book rule at 5 s keeping >= 60%; null median best t 2.2-3.2, out of sample within +-0.3bp | real: imb1 5 s, 109% - right; null median 2.13 and mean -0.39bp - **just outside** |

Two clean (P1, P3 - and P3 was trivial), two half right (P4, P5), one wrong (P2). The misses are informative: P2 failed because the *method* I called "the naive researcher's" is worse than I allowed; P4 failed because the hit rate excluded the 35% of 5-second windows with no move, which makes "right" look better than the money.

### Check yourself (Module 4)
- **E10.** H-flow is registered with 15 cells. On the confirm days its best cell gives t = 3.1 and a shifted-null p of 0.02. Does it pass K1?
- **E11.** Maker cost is 4bp. A rule's confirmed mean gross is 7.5bp and its mean net is +3.5bp, positive on 90% of days, 25 days, 400 trades, same sign on all 4 test pairs, t and p fine. Does it pass K2? Pass the hypothesis?
- **E12.** A cell's true mean is 0.5bp per trade and the sd per trade is 5bp. How many independent trades do you need at 80% power? What if the true mean is 2bp?

**Answers.** E10: the cut-off for 15 cells is 2.94, so `t = 3.1` clears it, but `p = 0.02` is not below the registered 0.01: **K1 fails**. E11: K2 needs gross `>= 2 x 4 = 8bp`; 7.5bp falls short, so **K2 fails** even though the net is positive, and with it the hypothesis (K1 and K3 are not enough: all criteria must hold). This is deliberate: a gross of only twice the cost is the margin against the fill and slippage errors a replay cannot see. E12: `(2.80 x 5 / 0.5)^2 = 785` trades; for 2bp, `(2.80 x 5 / 2)^2 = 50` trades.


---

## Module 5. Build it: recording, proving, and using the order-flow data

**What was built (all public data; nothing here holds a key or can place an order).** A package `orderflow/`: `book.py` (the order book state machine), `store.py` (raw gzip storage), `recorder.py` (the WebSocket recorder), `verify.py` (rebuild and audit a recording), `features.py` (1-second feature rows under the strict timestamp rule). Tests: `tests/test_orderflow_core.py` (21 tests, 33 deliberate code breaks caught, including the checkpoint) and `tests/test_orderflow_analysis.py` (14 tests, 19 breaks caught). Registered predictions R1-R7 sit in `recorder.py`'s docstring; they were written before the first trial. The trials' outputs are in `logs/orderflow_trial*_verify.txt`; the raw trial recordings are in `strategy_analysis/data/orderflow_trial*` (git-ignored). **The official record has not been started** - the registry counts its first 10 days as tune days, and that start is your call (Lesson 5.6).

**What I did differently from what I planned.** I probed the live feed *before* designing anything (four short throwaway scripts), and that changed the design three times: there is no checksum on the `books` channel; Bitget's REST order book is not tied to the stream (my first audit design failed, Lesson 5.3); and `seq` is global across connections (which made an exact audit possible).

### Python skills this project uses, and where to read them

| skill | where it appears | read first |
|---|---|---|
| `async` / `await`, tasks, timeouts | `recorder.py` (`session`, `_ping`, `fetch_snapshots`) | `Recorder.session` |
| dictionaries and sorting as a data structure | `book.py` (price -> size) | `Book.apply`, `Book.levels` |
| bytes, gzip, files that survive a crash | `store.py` | `RawWriter.write` / `flush` |
| JSON (`orjson`) and message routing | `recorder.py` `handle` | `Recorder.handle` |
| numpy `searchsorted` for "everything before time T" | `features.py` | `emit` inside `grid_from_frames` |
| pandas DataFrames, `groupby` by day | `features.day_coverage`, the labs | `day_coverage` |
| testing with hand-built messages and a fake local server | `tests/test_orderflow_*.py` | `fake_exchange` |

### Lesson 5.1 The exchange feed and WebSockets

1. **What it is.** A REST API is ask-and-answer: you request the book, you get one copy. A **WebSocket** is a connection that stays open: you subscribe once and the exchange *pushes* every change. For a book that changes ten times a second a push feed is the only way to see all of it.
2. **How it works (Bitget public v2, `wss://ws.bitget.com/v2/ws/public`).** You send `{"op":"subscribe","args":[{"instType":"USDT-FUTURES","channel":"books","instId":"DOGEUSDT"}, ...]}`. The server answers with an acknowledgement (`"event":"subscribe"`), then one `snapshot` message (the whole book) and then `update` messages. Every update carries only the levels that changed; a size of `"0"` means the level is gone. You must send the text `ping` about every 30 s; the server replies `pong`. The `trade` channel works the same way: a snapshot of recent trades, then one update per batch of prints, each with price, size, **taker side** and a trade id.
3. **What was measured on the live feed** (probes and four trials, 2026-10-30; the numbers are facts about that day's feed, not guarantees):
   - fields of a `books` message: `asks`, `bids` (lists of `[price, size]` strings), `ts` (server time, ms), `seq`, `pseq`. **There is no checksum.**
   - **`pseq` equals the previous message's `seq`**: an unbroken chain over every update recorded (more than 220,000 across ten pairs in five trials, zero breaks).
   - updates arrive in **~100 ms batches** (median gap 100 ms for BTC, XRP, SOL, DOGE, ADA; for the quieter SUI, LINK, WLD, SHIB, DOT the median is 88-98 ms with a 10th percentile of 20-45 ms and a 90th of 116-207 ms: they push when something changes).
   - the snapshot holds **200 levels a side (BTC 500)**. That is a very different number of basis points per pair:

   | pair | BTC | SOL | XRP | SUI | DOGE | LINK | WLD | ADA | SHIB | DOT |
   |---|---|---|---|---|---|---|---|---|---|---|
   | depth covered, each side (bp from the mid), range over the trials | 18-32 | 39-55 | 164-170 | 269-285 | 278-305 | 345-471 | 1,062-1,447 | 1,052-1,162 | 1,825-2,749 | 2,419-4,234 |

   (The server keeps the book at exactly its snapshot depth: the level count never moved from 400, BTC 1,000. Levels that fall outside are removed by the updates.) **Consequence for the registry's bands (2, 5, 10, 25 bp): all are fully covered for the eight alts; for BTC the 25 bp band is sometimes not (29% of seconds in the sample), and `Book.usd_within` returns NaN rather than a truncated number. Walls deeper than ~20-30 bp on BTC are invisible to this feed.**
   - **`seq` is global across connections.** A fresh snapshot fetched over a *second* connection carries a `seq` that exists in the first connection's stream (9 of 9 probes), and the first connection's rebuilt book at that `seq` was identical (Lesson 5.3).
   - local receive time minus the server timestamp: median **118-154 ms**, 90th percentile 141-235 ms, over the three verified trials (118-123 ms in the latest, 131-141 in the one before). This PC's clock was 34 ms from NTP (`w32tm`), so most of it is network and processing delay.
   - trades: BTC 30-42 a second, SOL 7, XRP 3, DOGE ~0.6, DOT ~0.2. In `update` messages carrying several trades, about 2% list them newest-first (`ts` descending): the feature code sorts by `ts`, so it does not matter, but never assume the order.
   - renewing one pair's `books` subscription (unsubscribe, then subscribe) yields a new snapshot in about **600 ms**, and the chain then continues unbroken.
4. **Limits.** One day, one hour of the day (13:50-14:35 UTC, the busy US-open block); no rate-limit was hit but none was probed; Bitget can change the feed.

### Lesson 5.2 The recorder: design and a walk through the code

**Four principles**, each a consequence of something that went wrong elsewhere in this repo:
1. **Store the raw frames; compute everything offline.** If a feature is defined wrongly (Module 3 had one), a raw recording can be re-read, a feature file cannot.
2. **Write the frame to disk first, then think about it.** An exception in your logic must not lose data.
3. **Never crash; always say what happened.** Reconnect with backoff; log every gap, error and reconnect to a separate event log.
4. **Detect, don't trust.** A missed message must be noticed (the `pseq` chain) and repaired (a fresh snapshot), and the repair must itself be audited.

**The state machine of one book** (`orderflow/book.py`, the heart of it):

```python
if d.get("pseq") != self.seq:                 # the message does not follow the last one we applied
    self.ready = False                         # so the book can no longer be trusted ...
    return "gap"                               # ... until a new snapshot arrives
# parse EVERYTHING before touching the book: a malformed message must raise with the book unchanged
bids, asks, seq, ts = _levels(d["bids"]), _levels(d["asks"]), d["seq"], int(d["ts"])
for rows, book in ((bids, self.bids), (asks, self.asks)):
    for p, s in rows:
        if s == 0: book.pop(p, None)          # size 0 deletes the level
        else:      book[p] = s                # otherwise the level now holds exactly this size
self.seq, self.ts = seq, ts
return "ok"
```
Line by line: the first test is the chain check - the only integrity check the feed offers. Parsing *before* mutating is a bug fix from this module: a malformed update with a valid chain position used to half-apply (bids changed, asks not) and leave a silently corrupt book; the test `test_bad_frames_never_stop_the_recording` caught it. The `for` loops are the whole update rule: the exchange sends the new total size at a price, not a delta.

**One frame in, a list of actions out** (`Recorder.handle`, abbreviated):

```python
self.writers[pair].write(recv_ns, raw)        # RAW FIRST: whatever happens next, the frame is on disk
...
res = self.books[pair].apply(m["action"], d)  # follow the book only to DETECT trouble
if res == "gap":
    self.events.write("gap", ...)             # say what happened
    actions.append(("resub", pair))           # and ask for a fresh snapshot of that pair only
```
`handle` is a plain function of one frame (no network), which is why it can be unit-tested with hand-built messages. The connection loop (`session`) only reads frames, calls `handle`, and carries out the actions it returns: renew a subscription, send a `ping` every 20 s, reconnect after 30 s of silence (`SILENCE_S`), and run an audit round every `--audit-every` seconds.

**Hourly checkpoints.** A book is only valid from a snapshot, so reading hour 17 of day 23 would mean replaying the whole recording from the start. To avoid that, whenever the recorder opens a new hourly file it writes the pair's current book as the file's first line (`Book.checkpoint_message`: the exchange's snapshot layout, `"action":"checkpoint"`, the same `seq`, prices and sizes written with `repr` so they parse back exactly; the chain continues because the next update's `pseq` still equals that `seq`). **Tested live across an hour boundary** (a 5-minute recording over 15:00 UTC, `logs/orderflow_trial_straddle_verify.txt`): the 15:00 files open with a checkpoint; the whole recording audits 20 of 20 exact; and the 15:00 hour verified **alone** (`--since 2026-10-30_15`, no earlier data) has 0 gaps and 0 unsynced frames - the checkpoint seeded every book - with the audits taken before the hour correctly set aside as "outside".

**Resources** (the recorder logs its own CPU and memory every minute): 2.6-3.6% of one CPU core and 55-58 MB of memory for all ten pairs. Memory rose from 55 to 58 MB in the first six minutes and then stayed at 57-58 MB for the next nine of a 15-minute run: warm-up, not a leak. The official run logs it every minute (`rss_mb` in the `stats` lines of `events.jsonl`) and the daily routine checks that it stays flat.

### Lesson 5.3 Proving the recording is right: the audit story

**The question.** A recorder that runs for weeks must be able to prove its books are exact, not merely unbroken. The `pseq` chain proves *no message was skipped*; it does not prove *the messages were applied correctly*.

**Attempt 1 (failed, and why it is instructive).** Compare the rebuilt book's top 5 levels with Bitget's **REST** order book fetched every few minutes. I registered a prediction of at least 90% agreement within +-250 ms. Result: **12 of 40 (30%)**. Quiet pairs (LINK 4 of 4, DOT 3 of 4) matched; hot pairs (XRP, DOGE, SUI, WLD, SOL) matched 0 of 4 and, searching +-4 s around each audit, never matched at *any* offset: the same price grid but different sizes (XRP's REST best-ask size was 6 and the next level 2,896, while the stream held 6 and 6). Two explanations were possible: my rebuild drifts, or the REST book is not on the stream's timeline. A cheap test told them apart: SOL's fresh WebSocket snapshot, taken 299 ms after my incremental book, agreed on 79-80% of the deep levels (beyond the nearest 10), and the book's own natural change over ~300 ms agrees on a median 92% (SOL) to 98% (DOGE) of its deep levels. Consistent, but one sample.

**Attempt 2 (worked).** A second probe asked whether `seq` is shared between connections. It is: a second connection's snapshot of SOL, XRP and BTC had a `seq` that appears in the first connection's update stream, and **my rebuilt book at exactly that `seq` was identical level for level, price and size, in 9 of 9 cases** - 200 levels a side, 500 for BTC. So the audit is: every few minutes a short-lived second connection (`fetch_snapshots`) fetches a fresh snapshot of each pair and stores it under `audit/`; `verify.py` finds the main stream's book at the same `seq` and compares the two *exactly*. Results of the live trials: **50 of 50 exact in the 6-minute trial, 10 of 10 and then 20 of 20 in the next two, 89 of 89 audits exact in all** (counting the 9 probe cases); 0 differing, 0 approximate, 0 outside. (The audit classifies a snapshot as `exact`, `differ` - a real problem - `approx` when the `seq` falls between two stream messages, or `outside` the recording; the tests cover all four.)

**What the verifier reports for each pair** (`python -m orderflow.verify <folder>`): snapshots, checkpoints, updates, gaps, frames arriving while unsynced, crossed books, trades, duplicate trades, whole trade messages out of order, the cadence of updates, the receive lag, levels per update, the snapshot depth and its coverage in bp, the audit result, disk bytes and an extrapolated MB per day. **A day is healthy when: gaps are rare and each followed by a snapshot, no crossed books, every audit exact, lag stable, memory flat.**

**Predictions R1-R7** (written before the first trial):

| | registered | found |
|---|---|---|
| R1 | at most 2 chain breaks in a 10-minute, ten-pair trial | **0** over 63,617 updates - right |
| R2 | BTC the largest file, over 40% of the total; ten pairs 0.3-1.5 GB a day | BTC 48%; **1.33-1.38 GB a day** (upper edge; measured in the busy US-open hours) - right |
| R3 | receive lag median 100-250 ms on every pair, 90th percentile under 400 ms | median 118-154 ms, 90th percentile 141-235 ms - right |
| R4 | at least 90% of REST audits match within +-250 ms | **30% - wrong** (the REST book is not tied to the stream); replaced by the seq-aligned snapshot audit, 89 of 89 exact |
| R5 | a renewed subscription gives a new snapshot within 2 s and the chain continues | 600 ms, SOL stayed gap-free - right |
| R6 | the book's level count stays within +-30% of the snapshot depth | **exactly** 400 (BTC 1,000) in every pair, always - right |
| R7 | the three least liquid pairs show uneven update gaps (90th percentile >= 1.5x the median); BTC and XRP ~100 ms steady | DOT 2.2x, SHIB 2.2x, WLD 1.7x; BTC and XRP 99-101 ms - right |

Six right, one wrong, and the wrong one led to the better design.

### Lesson 5.4 From raw frames to signals: one rule for time

**What it is.** The recording is a stream of events; a strategy needs a table, one row per decision instant `T`, whose columns it could have computed *at* `T`. Module 4 showed what happens if a column leaks one second of the future (IC +0.199 became +0.029).

**The rule, as code** (`features.py`):

```python
cut = T - lag_ms
...
hi = int(np.searchsorted(tts, cut, side="left"))                     # trades stamped strictly before the cut
for w in FLOW_S:
    lo = int(np.searchsorted(tts, cut - w * 1000, side="right"))     # and strictly after cut - w
    den = cabs[hi] - cabs[lo]
    row[f"flow_{w}s"] = (csign[hi] - csign[lo]) / den if den > 0 else math.nan
```
and the book loop `while next_t - lag_ms <= ts: emit(next_t)` applies a book message only if its `ts` is strictly less than `cut`. `searchsorted` on a time-sorted array of trade stamps finds "all trades before time `cut`" in one step; `csign` and `cabs` are cumulative sums of signed and absolute dollars, so any window total is a subtraction. **`lag_ms` is your delay between an event happening and being able to act on it**: 0 is the researcher's ideal; the measured receive delay is ~120-150 ms and the registry's fill model adds 500 ms of order latency, so use `lag_ms >= 150` for anything that claims to be tradable.

**A real row** (DOGE, `lag_ms=150`, from the 6-minute trial; one row per second):

| t (UTC) | spread_bp | imb1 | imb5 | imb_band2 | imb_band5 | micro_bp | flow_5s | flow_30s | book_age_ms |
|---|---|---|---|---|---|---|---|---|---|
| 14:18:57 | 1.334 | -0.002 | -0.043 | -0.002 | -0.339 | -0.001 | -0.308 | -0.633 | 50 |
| 14:18:58 | 1.334 | **-0.963** | -0.006 | -0.963 | -0.184 | -0.642 | -0.308 | -0.304 | 49 |
| 14:19:57 | 1.331 | +0.034 | +0.021 | -0.125 | -0.187 | +0.023 | NaN | -0.373 | 50 |

(`imb1` goes from -0.002 to -0.963 in one second: the level-1 flicker of Module 3. `flow_5s` is NaN where nothing traded in the window; `book_age_ms` is how stale the book is at the cut.) **Using it:**

```python
from orderflow.features import grid, day_coverage
df = grid("strategy_analysis/data/orderflow_trial2", "DOGEUSDT", lag_ms=150)
print(day_coverage(df))        # share of each UTC day with a ready, fresh book: the registry counts a day only at >= 0.9
```
and the Module 3 statistics apply to those columns unchanged (`window_lab.ic_nonoverlap(df.imb1.to_numpy(), fwd, h)` with `fwd = fwd_change_bp(df.mid.to_numpy(), h)`). Start flow-based features a few minutes into a file: the 300 s window needs trades from before it.

**Limits.** The grid is 1-second; the 100 ms batches mean sub-second features are possible but are not in this version. A pair with a stale book yields stale rows (filter on `book_age_ms`). Wall features (Module 2's `WallTracker`) are not in `features.py` yet: they need the approach-event logic of H-approach and are written when real data exist.

### Lesson 5.5 Replay, backtesting and paper trading: the design (no trading code yet)

You asked to start with data collection and analysis, not automated trading, so this lesson is the design that the code will follow once there is data to test it on.
1. **Event-time replay.** Merge the book messages and trades of a pair into one list sorted by exchange `ts`, then walk it. At each decision instant the strategy receives *only* the row `features.grid` would give it (same strict rule), and may ask for an order. An order is **not** filled at the mid: it goes to the fill model.
2. **The fill model already exists**: `backtest/book_hist.maker_fill` (a resting buy fills when a taker sell prints *through* its price, or cumulative taker sells *at* its price exceed the queue ahead; 0.5 s latency; 10 s to fill; a missed fill is no trade). Taker orders walk the recorded book at the decision time plus `lag_ms`. Costs come from `order_flow_registry.round_trip_cost_bp`.
3. **Paper trading = the same strategy code driven by the live feed.** Every decision is written to a log *with its timestamp before the outcome exists*; fills are simulated against the live book; no parameter changes during the test; a pre-declared kill rule (Lesson 4.5). It **cannot** send orders: nothing in `orderflow/` has an order function, a key, or an account.
4. **What the registry requires before any of this matters:** a hypothesis passing K1-K4 on the confirm days.

### Lesson 5.6 Running it for real

1. **Where.** On this PC, in a terminal tab you leave open: `python -m orderflow.recorder --out strategy_analysis/data/orderflow`. The VM has ~120 MB of memory free; the recorder needs ~60 MB plus the OS cache, and the disk need (below) is large, so the PC is the place for now.
2. **What must be true.** The PC does not sleep (Windows power settings: "never sleep" while plugged in - **your decision, I have not changed any setting**), the clock stays synced (`w32tm /query /status`), and the folder has ~2.5 GB a day free for 40 days (the measured 1.33-1.38 GB a day was recorded at the busiest hours; allow the margin). D: has 172 GB free.
3. **Daily routine (2 minutes).** `python -m orderflow.verify strategy_analysis/data/orderflow --since <yesterday's last hour>` (each hourly file opens with a *checkpoint* - the current book as a snapshot - so any hour can be checked on its own), then read: gaps, crossed = 0, audits exact, lag stable, memory flat in the stats lines of `events.jsonl`.
4. **The registry's day rule** (amended before any data existed, `AMENDMENTS` 2026-10-30): a UTC day counts for a pair only if its book was ready and no staler than 2 s for at least 90% of the day's seconds (`features.day_coverage`). A day the PC slept through is simply not counted; the 10 tune days and 20 confirm days are counted from days that qualify.
5. **Do not edit the recorder or the features while the official record runs**, except to fix a bug; log any fix in `AMENDMENTS` with the date. The raw frames are the record - features can always be recomputed.
6. **Starting the official record is the next decision, and it is yours:** it fixes day 1 of the tune period, needs the PC on for about 40 days, and its first useful result (the 10 tune days) is two weeks away.

### Check yourself (Module 5)
- **E13.** A pair's `books` stream delivers (seq, pseq): snapshot (100, 0); (110, 100); (125, 110); (140, 130); (150, 140). Which message breaks the chain, what does the book do with it, and with the next one?
- **E14.** The ten pairs record 1,330 MB a day. How many days fit in 100 GB? How much do the 10 tune days plus 30 confirm days need?
- **E15.** Decision instant T = 12,000 ms, `lag_ms` = 300. Trades are stamped 10,700, 10,701, 11,600, 11,699, 11,700, 12,000. Which are in the 1-second flow window?

**Answers.** E13: (140, 130): its `pseq` 130 is not the last `seq` applied (125), so the chain is broken, the message is **not applied** and the book becomes not ready; (150, 140) arrives while the book is unsynced and is ignored (it is still stored raw) until a new snapshot arrives. E14: 100,000 / 1,330 = **75 days**; 40 days need 40 x 1.33 = **53 GB** (about 100 GB with a 2x margin for busy hours). E15: `cut = 11,700`; the window is strictly after 10,700 and strictly before 11,700: **10,701, 11,600 and 11,699** (10,700 is the window's open end; 11,700 is the cut; 12,000 is after it).

---

## Where this leaves you
- **Done:** the concepts (Modules 0-3), the protocol and a code-pinned registry (Module 4), a recorder that has been proven exact on 89 audits and a verifier and feature sampler that follow the timestamp rule (Module 5).
- **Not done, on purpose:** the official recording (your decision, Lesson 5.6), wall features (written when data exist), the replay engine and paper trader (designed in Lesson 5.5; code after there is data to test it on), and any trading. Nothing in this project can place an order.
- **The next step** is the official recording: it starts day 1 of the 10 tune days. After the tune days, thresholds are frozen and the first confirm days begin; no hypothesis is judged before 20 qualifying confirm days.

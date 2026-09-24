# Bear markets: the one signal that predicts inside them (2026-09-24)

*Asked for: "for choppy and bear there must be some signals or possible predictions." Every
number names its file. Status: **a candidate, NOT deployed, needs a forward paper test.***

**Short version.** Twenty-one signals were tested *inside* bear regimes and *inside* chop (84 cells,
Holm across all of them). **One passed, in bears, and it was the one predicted beforehand:
market breadth**, the share of the top-60 perps above their 20-day average. When almost nothing
is above its average in a bear market, alts bounce the next week. When a bear rally has lifted
many coins back above, alts fall. Traded both ways, only in bear regimes, it made **+25–27%/yr
on the whole account at 1×**, positive on both halves and without 2022. It has **zero
correlation with the trend book**, and it turns the trend book's bear months from **−1.6%/mo
to +6.4%/mo** (raw). **Nothing passed in chop.**

**Then it was attacked three times, and it held** (§6–§7):
- **Permutation:** p = 0.001.
- **Parameter grid:** 221 of 240 settings positive on both halves, and none negative overall.
- **Episodes:** 16 of 22 capitulation buys made money.
- **Costs:** survives 5× the fees.
- **Out of sample:** it replicated on **the 2018–2019 bear**, data never used here, with every
  parameter frozen. That period gave **+21.7%/yr**, against −5.0% for being long on every bear day.

Weak spots:
- the drawdown out of sample is 40–42%, twice the in-sample figure;
- at $221 the $5 minimum blocks a third of the orders, and the holdout drops to +8%/yr;
- the chop placebo is inconsistent (−14% in 2020–26, +7–16% in 2017–19).

---

## 1. The scan — `backtest/regime_signals.py` (log `logs/regime_signals.txt`)

Doc 12's fourteen signals plus seven new ones:
- breadth on 20/50-day averages
- the Fear & Greed index
- Deribit's DVOL and its 7-day change
- market-wide funding
- BTC's distance below its 90-day high

The web sources for the new ones are listed at the end. Targets: BTC and an equal-weight index
of the point-in-time top-40 (dead coins included) over the next 7 days. Each test is **within
one regime**
(`market_neutral.btc_regime`), top third minus bottom third, month-block bootstrap, both halves
(holdout from 2024-08-29).

**Registered before running:** *"at most two cells pass Holm, both in BEAR and both contrarian
(breadth or Fear & Greed on the alt index). Nothing passes in CHOP."* That is what happened:

| cell | spread (top − bottom third) | t | tune | holdout | Holm p |
|---|---|---|---|---|---|
| **BEAR → alt index, breadth20** | **−5.90%/wk** | **−3.48** | −5.80% | −3.87% | **0.043 PASS** |
| BEAR → BTC, breadth20 | −3.50%/wk | −2.96 | −3.65% | −1.49% | 0.25 |
| CHOP → BTC, Coinbase premium | +3.28%/wk | +2.38 | +2.93% | +2.52% | 1.0 (the only chop hint) |

Fear & Greed held its sign in bears but was small (−1.51%, t −0.91). DVOL did nothing in chop,
despite the web's claim.

In bear regimes, by breadth20 tercile (next 7 days):

| breadth20 in a bear | alt index | BTC | alt tune | alt holdout |
|---|---|---|---|---|
| low (≤ 10% of coins above their 20d average) | **+3.64%** | +2.81% | +3.66% | +3.52% |
| middle | −0.62% | +0.92% | −1.24% | +0.25% |
| high (≥ 29%) | **−2.26%** | −0.69% | −1.83% | −3.14% |

The same split in chop and bull shows no pattern. It is the index-level version of what
`bear_chop.py` test 3 found from the other side: in a bear, a breakdown is followed by a bounce.

## 2. As a trade — `backtest/breadth_trade.py` (log `logs/breadth_trade.txt`)

**The rule.** On each day that `btc_regime` calls BEAR:
- if breadth20 is in the bottom third of all *previous* bear days, open a long tranche;
- if it is in the top third, open a short tranche;
- otherwise, nothing.

Each tranche is 1/7 of the book and is held 7 days. Outside bears, nothing is opened.

**What is charged:**
- 12bp round trip;
- actual funding over the exact settlement window;
- 1bp/day for rebalancing the basket;
- **entry one full day after the signal.**

| instrument, long low + short high | CAGR | tune /yr | holdout /yr | DD | worst week | in market |
|---|---|---|---|---|---|---|
| alt index (top-40) | **+27.0%** | +31.0% | +18.7% | 20% | −9.5% | 25% of days |
| **top-10 basket** (buildable at $221) | **+25.4%** | +31.3% | +13.4% | 21% | −9.1% | 25% |
| BTC alone | +15.1% | +20.1% | +4.9% | 15% | −7.5% | 25% |
| *control: long the alt index every bear day* | *+0.2%* | *+2.1%* | *−4.0%* | *62%* | *−29.7%* | *32%* |

Both legs earn on their own (alt index, lag 1: long +13.0%/yr, short +12.3%/yr). The fixed "20%
capitulation" line from the web works too (+18.1%/yr), so the result does not hang on the
expanding thresholds.

## 3. Trying to break it — `backtest/breadth_attack.py` (log `logs/breadth_attack.txt`)

| attack | result | verdict |
|---|---|---|
| **placebo**: same rule in CHOP only / BULL only | **−14.3% / −8.6%** per yr (alt index) | passes: it is a bear effect |
| the bot's own gate (BTC < 1000h average) as "bear" | +34% alt / +23% top-10, but DD **45–54%**, worst week −34% | weaker: the stricter label matters |
| plateau, breadth 10 or 20 days × hold 3/7/14 | **all 6 cells positive on both halves** | passes |
| plateau, breadth **50** days | tune +9.4%, **holdout −9.7%** (hold 7) | **fails** |
| month-block bootstrap t | +2.49 alt, +2.23 top-10, +2.11 BTC | real, modest |
| **2022 removed** | +16.7% alt (t 2.29), +13.9% top-10, +8.6% BTC | passes |
| correlation with the triple trend book | **−0.00 daily, −0.03 weekly** | independent |

**With the trend book** (triple, 10× guard, entry-sized, **RAW - the trend side is NOT haircut
here, so these are for comparison inside this table only**):

| months by dominant regime | trend | breadth sleeve | together |
|---|---|---|---|
| bull (31) | +101.2% | +0.1% | +101.3% |
| chop (25) | −1.9% | −0.5% | −2.4% |
| **bear (23)** | **−1.6%** | **+8.1%** | **+6.4%** |

Trend + 1× sleeve: drawdown **50% → 42%**, months up **49% → 57%**, worst month unchanged (−21.9%).

### Predictions against outcomes

| registered | outcome |
|---|---|
| scan: ≤ 2 passes, both bear, contrarian, breadth or Fear & Greed; none in chop | **right**, exactly |
| trade: long side positive on both halves, keeps ≥ half at lag 1 | right (lag 1 was *better*) |
| short side weaker and noisier than the long side | **wrong**: about equal |
| worst week below −15% | **wrong**: −9.5% |
| beats always-long-in-bear on both halves | right |
| placebo regimes ~0 or losing | right |
| every plateau cell positive | **wrong**: breadth50 fails the holdout |
| bootstrap t > 2.5 | **wrong**: 2.1–2.5 |
| positive without 2022 | right |
| correlation with trend in [−0.2, +0.1] | right |

## 4. Why it is a candidate and not a change

- **It was found by searching.** 84 cells were scanned; one passed Holm at p = 0.043, so the
  multiple-testing correction passes, but not by much. The trade's t of 2.1–2.5 is real and
  modest.
- **Only 23 bear months** in six years, and 2022 alone is ~45% of the compounded growth (alt
  index, lag 1: 2022 made +103%, which in log terms is 45% of the six years' total;
  `logs/breadth_trade.txt`). It
  survives without 2022, but on thinner evidence.
- **The 50-day breadth version fails the holdout.** The effect lives at the 10–20 day horizon.
  That is plausible (bear-market bounces are short) but it is a partial plateau.
- **The repo's holdout is mined** (CLAUDE.md §2). The placebo pass and the ex-2022 pass are the
  parts that do not depend on it. Judge it forward.
- **It is idle most of the time.** It trades ~25% of days, only in bears. The market has been in
  a BULL regime since the last bear day on 2026-08-02, so a paper book would sit flat until the
  next bear.
- **The minimum-order constraint is real.** A 7-tranche ladder at 1× on $221 moves ~$32 of
  notional per step, which is $3 per coin in a 10-coin basket, below Bitget's $5 minimum. The
  live version must trade a smaller basket (3–5 coins, or BTC + ETH), or net the ladder into one
  daily target position.

## 5. How to read it live

**Regime.** From BTC daily closes: BEAR when BTC is below its 50-day average AND that average
fell more than 2% over 20 days (`market_neutral.btc_regime`, one day lagged).

**Breadth20.** Take the top 60 USDT perps by the previous month's volume, excluding stables and
gold, listed ≥ 30 days. Breadth20 is the share of them whose daily close is above their own 20-day
average (`breadth_attack.breadth`).

**Thresholds.** From every bear day since 2020: **low ≤ 10.0%, high ≥ 28.8%**.

**Today** (panel end 2026-09-21): regime **BULL**, breadth20 71%, so no position.

Web sources for the candidate signals: [KuCoin on market breadth](https://www.kucoin.com/knowledge-base/Analysis/what-is-market-breadth-indicator-in-crypto),
[Stage Analysis crypto breadth](https://www.stageanalysis.net/blog/326402/crypto-breadth-percentage-of-crypto-coins-above-short-medium-long-term-moving-averages),
[Deribit on DVOL](https://insights.deribit.com/exchange-updates/dvol-deribit-implied-volatility-index/),
[CoinGecko Fear & Greed](https://www.coingecko.com/en/charts/fear-and-greed-index).

---

## 6. Third round: permutation, grid, episodes, costs, $221 — `backtest/breadth_robust.py` (log `logs/breadth_robust.txt`, grid `logs/breadth_grid.csv`)

All runs enter one day after the signal and pay 12bp, funding and 1bp/day rebalancing unless
stated.

| test | result | registered | outcome |
|---|---|---|---|
| **permutation**: breadth circularly shifted ≥ 60 days, 1,000× | fakes median −3.8%/yr, 95th pct +12.0, best +27.1; real +27.0 → **p = 0.001** | p < 0.05 | right |
| **permutation**: the same long/short days reshuffled in 7-day blocks, 1,000× | fakes median −4.6, best +15.5 → **p < 0.001** | p < 0.05 | right |
| **grid**: breadth 10/15/20/30 × hold 3/5/7/10/14 × tails 20/25/33/40% × top-40/60/100 | **221 of 240 cells positive on both halves (92%)**. Median +13.1%/yr; **worst cell +3.5%/yr**. Breadth 15/20: 100% of cells; breadth 30: 73% | ≥ 70% for breadth 10–20 | right |
| **bear label**: BTC below its 30/50/100-day average, slope < 0/−2/−5% | 30- and 50-day labels: **6 of 6 positive on both halves**; 100-day: 1 of 3 | ≥ 7 of 9 | right, exactly 7. A slow label is too late. |
| **episodes** (alt index) | **LONG: 16 of 22 made money (73%)**, mean +3.8%, worst −2.5%. SHORT: 18 of 31 (58%), mean +2.7%, worst −8.3% | ≥ 60% / ≥ 55% | right |
| **costs**: 60bp round trip + 3bp/day | +23.0%/yr (tune +26.9, holdout +15.1) | positive | right |
| **$221, 5-coin basket, $5 minimum** | $221 → **$834** 2020–26 (+22.4%/yr, DD 20%); holdout $221 → $259 (**+8.1%/yr**) | < 10% of orders skipped, keeps ≥ 80% | **wrong**: 33–42% of orders skipped. Full period keeps 83%, but the holdout keeps only 43% |
| $221, BTC + ETH | $221 → $650 (+17.9%/yr); holdout +4.7%/yr | | |

The honest sample size is the episode count, and it is small: 22 capitulations and 31 fades in
five years. Every one is listed in the log.

## 7. Out of sample: the 2018 bear, every parameter frozen — `backtest/breadth_oos.py` (log `logs/breadth_oos.txt`)

**Data.** Binance's BTC-quoted spot book, priced in dollars as ALTBTC × BTCUSDT: 197 assets, dead
pairs included (`backtest/spot2018_fetch.py`). In 2018 most altcoins traded against BTC. This
window, 2017-07 to 2019-12, was never used for this question.

**Frozen.** Nothing was re-chosen:
- the bear label;
- breadth20 over the PIT top-60;
- **the thresholds taken from 2020–26: low ≤ 10.0%, high ≥ 28.8%**;
- the 7-day ladder;
- entry one day after the signal;
- the costs.

No funding is charged (spot). Shorting was not available on Binance spot in 2018, so the short
leg is a measurement of the signal, not a trade anyone could have placed there.

| next 7 days, alt index, in BEAR | low breadth | mid | high | low − high |
|---|---|---|---|---|
| **2017-07 → 2019-12 (out of sample)** | **+2.79%** | +0.07% | **−1.86%** | **+4.65%/wk** |
| 2020-01 → 2026-09 (where it was found) | +3.64% | −0.62% | −2.26% | +5.90%/wk |

| frozen trade, 2017-07 → 2019-12 | CAGR | DD | worst week | 2018 | 2019 |
|---|---|---|---|---|---|
| **BEAR long + short, alt index** | **+21.7%** | 42% | −20.9% | +31.9% | +23.4% |
| BEAR long + short, top-10 | +20.9% | 40% | −20.2% | +18.2% | +35.3% |
| BEAR long + short, BTC | +14.9% | 32% | −14.8% | +18.0% | +19.5% |
| BEAR long only, alt index | +13.9% | 34% | −20.9% | +26.2% | +9.3% |
| BEAR short only, alt index | +6.2% | 25% | −15.0% | +3.3% | +12.4% |
| *control: long every bear day, alt index* | *−5.0%* | *48%* | | | |
| *placebo: CHOP, alt index* | *+7.2%* | *42%* | | | |
| *placebo: BULL, alt index* | *−64.5%* | *93%* | | | |

| registered before running | outcome |
|---|---|
| in bears, low beats high by ≥ 2%/wk | **right**: +4.65%/wk |
| the frozen long+short trade and each leg positive | right for the baskets. **Wrong for BTC's short leg** (−1.6%/yr; −8.1% in 2018) |
| the same rule in CHOP or BULL not positive | **half wrong**: BULL −64%; **CHOP +7 to +16%/yr** (in-sample CHOP was −14%) |
| +5% to +20%/yr on the alt index | **slightly wrong**: +21.7% |

**What the out-of-sample run settles, and what it does not.**
- **Settled:** the bear-market effect is not an artefact of 2020–2026. Frozen thresholds on a
  different market structure, eight years earlier, recover the same shape: capitulation
  bounces, broad rallies fade, the spread about 80% of the in-sample size. The trade beats
  "long every bear day" by ~27 points a year.
- **Not settled: the drawdown.** It was 40–42% at 1× out of sample, twice the in-sample 20%,
  with a −21% week. Size it at **0.5×** if it is ever run beside the trend book.
- **Not settled: chop.** The rule's sign in chop flips between the two periods. That is one more
  reason to gate it to bears only, which the rule already does.
- In BULL regimes the same breadth reading means the **opposite** (2017's mania: high breadth →
  +9.6% the next week). It is a bear-only rule, and running it in a bull would be ruinous.

## 8. Status after three rounds

**The strongest single finding in this repo for bear markets, and the only one with an
out-of-sample replication on frozen parameters.** It is still a candidate, for three reasons:
- the drawdown at 1× is 20–42% depending on the era;
- at $221 the minimum order size costs a lot of it, because the holdout keeps only 43%;
- the market is in a bull regime today, so a forward paper test cannot start producing evidence
  until the next bear.

**The next step is a pre-registered paper book** with these exact frozen rules, sized 0.5×,
trading a 3–5 coin basket.

## 9. Added to the triple book — `backtest/triple_plus_breadth.py` (log `logs/triple_plus_breadth.txt`)

**The two parts:**
- **Trend side:** the triple (tight + time stop + 7 units) with the bot's 10× guard, entry-sized,
  10 orderings. The triple-alone row reproduces CLAUDE.md §6 exactly ($536 / $584).
- **Sleeve:** the frozen rule, traded as the **real $221 version** (5 coins, Bitget's $5 minimum,
  on k × $221 of capital).

**How it is quoted.** Upside is haircut 3× on the WHOLE book, which also shrinks the
point-in-time sleeve, so these figures understate it. Downside is raw.

| $221 after 12 months | typical (haircut) | bad year | years ending < $221 | worst year (raw) | DD (raw) | months up | bear months (raw) |
|---|---|---|---|---|---|---|---|
| **holdout**: triple alone | $536 | $407 | 1% | $207 | 50% | 47% | −4.7% |
| holdout: + 0.5× real sleeve | $544 | $416 | 1% | $214 | 47% | 48% | −2.9% |
| holdout: **+ 1× real sleeve** | **$564** | $435 | 1% | $220 | **44%** | 51% | −0.7% |
| **full history**: triple alone | $584 | $318 | **8%** | $164 | 53% | 49% | −1.5% |
| full: + 0.5× real sleeve | $636 | $344 | 1% | $193 | 50% | 52% | +1.9% |
| full: **+ 1× real sleeve** | **$697** | $368 | **1%** | **$206** | **49%** | **55%** | **+6.1%** |

**What it does.** The bull months are untouched (+121.5% / +93.8% raw either way), because the
sleeve does not trade in bulls. What changes is the bad tail. Over full history, years ending
below $221 fall from 8% to 1%, and the worst year rises from $164 to $206. The drawdown falls 4–6
points and bear months turn positive.

**What it does not do.** It does not fix chop: chop months get slightly worse (−2.0% → −2.7%),
because a "chop" month can contain a few bear days. It does not change the headline much on
the holdout (+$28).

**At $221, 1× is the only size that works.** At 0.5× the $5 minimum blocks 43% of the sleeve's
orders over the full history and 72% on the holdout. Half size makes sense only on a bigger
account.

Registered: *"at k = 0.5 real, the typical year rises $10–40, DD falls 3–6 points, months up
rise ~5, bear months reach ~+2%; at 1.0 the holdout gain is small."* Outcomes:
- DD: right;
- bear months: right on full history;
- the typical-year gain at 0.5×: outside the range both ways, above it on full history (+$52)
  and just under it on the holdout (+$8);
- months up rose 1–3 points, not ~5: wrong.

## 10. Why the account still falls to half, with longs, shorts and the sleeve — `backtest/why_drawdown.py` (log `logs/why_drawdown.txt`)

This section takes apart the triple book's three worst falls in each of 10 orderings, all
measured on realised equity with the 10× guard.

**When.** Always the same windows, whatever the ordering:
- 2020-08 → 2020-11;
- 2023-02 → 2023-10;
- 2023-12 → 2024-03;
- **2024-12 → 2025-07** (the worst in 7 of 10 orderings, −45% to −61%);
- 2025-10 → 2026-05.

**The market was not falling.** BTC went **up** 51% during the 2020 fall and **up** 16% during
the 2024-12 → 2025-07 fall. Across every ordering's worst fall, days were 42% chop, 42% bull and
only **16% bear**.

**Every fall followed a boom.** The account had multiplied **×2.4 to ×7.9 in the 120 days
before** each peak. Every new position is sized at 0.30% of that peak equity.

**What lost the money** (ordering 0's three falls, % of peak equity):

| fall | 1h longs | 4h + 12h longs | shorts | pyramided positions (3+ units) | breadth sleeve |
|---|---|---|---|---|---|
| 2024-12 → 2025-07, −55% | −39.7% (**94% of 215 lost**) | −20.9% | **+6.2%** | −20.2% | **+15.3%** |
| 2020-08 → 2020-11, −45% | −30.8% (94% of 87 lost) | −8.1% | +0.2% | −19.9% | 0.0% (not one bear day) |
| 2025-10 → 2026-05, −44% | −50.7% (95% of 296 lost) | −23.1% | **+46.2%** | −10.0% | +10.1% |

Three mechanisms, in this order of size:
1. **Alt breakouts that fail, hundreds of times.** After a boom, the alts go sideways (often
   while BTC still rises). 94–95% of the 1h long breakouts lose, and 55% of all losing dollars
   are full stop-outs.
2. **Big pyramids giving back.** A 5–7 unit position built in the boom exits on a trail ~10R
   below its best, which is below the average price of its later units. The five largest single
   losses are all 3–7 unit longs, **−11R to −24R, each 2–6% of the account**.
3. **The hedges are too small and too late.** The shorts made money in two of the three falls
   (+6%, +46%), but they are single units, cut to ×0.25 whenever BTC is below its 1000h average,
   and have nothing to short while BTC is rising. The sleeve trades only on bear days, which were
   16% of the fall.

Registered for this file: *"falls follow a bull run and run through chop, not bears; ≥ 60% of the
loss is longs stopped near −1R; shorts lose too; the sleeve is idle."* Outcomes:
- after a bull run and not in bears: right;
- "chop" was half the story: the other half was bull-labelled days;
- full stop-outs were 55%, not ≥ 60%;
- **the shorts made money, not lost it;**
- the sleeve was idle in one fall of three.

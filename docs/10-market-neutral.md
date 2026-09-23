# The second book: market-neutral cross-sectional momentum

*Written 2026-09-23. Source: `backtest/market_neutral.py`, `backtest/combine.py`.
Logs: `logs/market_neutral.txt`, `logs/combine.txt`.*

**Status: validated as a candidate, NOT deployed.** Nothing about the live bots changed
when this was found. Read [the caveats](#the-four-caveats) before you act on it.

## Why it was tested at all, when doc 02 had closed the category

Two asks: a strategy that **combines** with the deployed trend book, and one that
**does not care whether the market is up, down or sideways.** Only one construction can
structurally deliver the second: go long the strongest coins and short the weakest in
equal dollars, so the market's direction cancels *inside* the book instead of having to be
forecast.

Doc 02 had already killed market-neutral ideas, but on narrow universes: funding carry
(2.7%/yr, dead), funding dislocation (`funding_xs.py`, all 18 cells negative), and one
survivor — cross-sectional momentum at Sharpe 0.62, filed as "genuine and too small."

What reopened it was a measurement made in passing by `bear_shorts.py`: shorting the
**weakest** coins beat shorting the strongest in *both* bull and bear weeks, on the
survivorship-free universe. That spread had never been turned into a book with costs.

## What it does

Every 7 days, on the point-in-time top 60 perps by the prior month's volume:

- rank by 30-day return, go **long the top decile, short the bottom decile**, equal dollars
- gross 1× — half the account long, half short, so every figure below is a return on the
  **whole account**, not on one leg
- hold 7 days, rebalance

## What is charged

| Charge | How |
|---|---|
| Survivorship | All 855 perps **including the 339 dead ones**. Nothing knows which coins survive. |
| Fees | 12bp on the notional *actually turned over*, measured from basket overlap — not a flat assumption |
| Funding | The **actual** rate both legs paid or received, from the archive |
| Delisting | A coin that stops trading mid-hold exits at its last print (Binance settles a delisted perp near mark) |

## The result

PIT top-60, 30d momentum, weekly:

| window | weeks | net/week | annualised | Sharpe | gross | funding | cost |
|---|---|---|---|---|---|---|---|
| **ALL** | 337 | **+1.130%** | **+79.6%** | **1.16** | +0.938% | +0.252% | 0.061% |
| bull | 124 | +1.691% | +139.8% | 1.47 | +1.645% | +0.107% | 0.061% |
| **bear** | 86 | **+0.244%** | +13.5% | **0.28** | **−0.132%** | **+0.437%** | 0.061% |
| chop | 127 | +1.181% | +84.5% | 1.39 | +0.973% | +0.269% | 0.061% |

**Robustness — ranked one full day before entry** (so the result cannot depend on ranking
and trading at the same close): ALL +1.021%/wk, Sharpe 0.90. It survives. bull +2.011%,
bear +0.239%, chop +0.585%.

## THE FINDING THAT MATTERS MOST

Look at the **gross** column in the bear row. It is **negative**. And it is negative in
*every* variant tested — top-60 weekly −0.132%, 90d momentum −0.181%, 14-day rebalance
−1.576%, lag-1 −0.164%, top-100 −0.660%.

> **The momentum spread does not work in bear markets. At all. The only reason the bear row
> is positive is FUNDING.** Bear funding carry is +0.437%/wk (+25%/yr) against a momentum
> spread that loses 0.132%/wk.

This is not a disappointment, it is the most reliable part of the result, and it lands
exactly where this project's own structural insight predicts: *the things that worked were
either momentum gated by a regime filter, or structural payment mechanisms.* Ranking by
momentum and shorting the losers happens to select the coins paying the most funding. The
book's regime-indifference is **carry**, not prediction.

It also sets the honest headline: this is **not** a book that performs the same in all
three regimes. It is a book that earns well in bull and chop, and roughly **breaks even in
a bear while collecting carry**. That is still worth having — the trend book is at its
weakest in exactly those stretches — but the claim has to be stated that way.

## Does it combine with the deployed book?

`backtest/combine.py`, 337 overlapping weeks:

**Correlation: +0.092.** By regime: bull +0.16, bear +0.21, chop −0.16. Effectively
independent everywhere, which is the entire reason to consider running it.

| book | /month | /year | drawdown\* | Sharpe | weeks up |
|---|---|---|---|---|---|
| trend blend alone | +10.93% | +247% | 23% | 1.65 | **32%** |
| market-neutral alone | +3.93% | +59% | 37% | 1.16 | 54% |
| **blend 75% / MN 25%** | +9.70% | +204% | **20%** | **1.80** | **53%** |
| blend 50% / MN 50% | +8.16% | +156% | 22% | 1.93 | 57% |
| blend 25% / MN 75% | +6.26% | +107% | 28% | 1.78 | 57% |

\* **These drawdowns compare only to each other.** The trend series is divided by the 3×
hindsight premium, which tames its drawdown too; the same book measures **58%** un-haircut
in `backtest/expectations.py`. Do not quote 23% anywhere else.

**The 75/25 line is the interesting one.** Giving up 11% of the return buys a *lower*
drawdown, a higher Sharpe, and — the part that actually matters to a human — a jump in
weekly win rate from **32% to 53%**. The deployed book loses two weeks in three. A quarter
of the account in an uncorrelated book turns that into a coin flip, without the return
collapsing.

## The four caveats

1. **Two dead years.** 2022 −0.124%/wk and 2024 −0.071%/wk. Six and a half years, two of
   them flat-to-negative. Not a steady income.
2. **2026 is carrying it.** +4.287%/wk over 37 weeks, against +0.74%/wk for 2020–2025
   combined. Excluding 2026 the book earns roughly **+47%/yr, not +80%**. A third of
   2026's return is funding (+0.973%/wk), a rate no other year came near.
3. **It does not scale to a wider universe.** PIT top-100 reads +1.051%/wk overall but
   **bear −0.350%** — the regime-indifference, the one property it was built for, breaks.
   Same direction as `wide_book.py`: breadth hurts here.
4. **It is not haircut and the trend book is.** The 3× hindsight premium exists because the
   trend book's 12 coins were picked with hindsight. This book's universe is point-in-time,
   so there is nothing to haircut — but that asymmetry flatters it in every side-by-side
   table above, including the 75/25 line.

## It is now running forward — `mn_paper.py`, started 2026-09-23

Pre-registered, gross 1.0×, $221 start so it is directly comparable to the other four books.
Verdict at **26 rebalances (6 months)**, and the success test is *two* conditions: net > 0
**and** realised correlation to the main book below +0.30. A positive return at high
correlation counts as a FAIL — that would mean this is the trend book wearing a hat.

First basket: **6 long / 6 short at $18.41 each**, 6bp of turnover cost.

### Two things running it corrected in this document

**1. The minimum-order worry was wrong, and I had the arithmetic backwards.** This page
previously said a "120-name book on $200 means ~$2 positions" and that the venue minimum
would probably bind. A decile of 60 is **6 names per side, not 120** — so the book holds 12
positions of **$18.41** against a Binance minimum of **$5**. The minimum is not binding, and
`mn_paper.py` enforces and logs it per name rather than assuming either way.

**2. The first live basket shorted PAXG and XAUT together** — two claims on physical gold
filling two of six short slots. Excluded by category (`market_neutral.NON_CRYPTO`): same
underlying, and a cross-sectional *crypto* momentum book has no thesis about gold.

Disclosed because it cuts both ways: excluding them also **improves** the backtest, from
+1.130% to **+1.222%/wk** and Sharpe 1.16 → **1.22**. That improvement is gold's 2025–26 bull
run, which is exactly the kind of hindsight this project haircuts everywhere else. The
category argument stands without the number; the number is recorded next to it so the
judgement can be second-guessed. The decision was made **before the first mark**, which is
the only honest moment for it.

*(A first attempt at that exclusion used substring matching and silently deleted `VETUSDT`
— "TUSD" — along with UB, VELVET, WCT and ZBT, then reported the loss as the effect of
removing gold. VET alone was eligible in 27 months. Exact base-asset matching now.)*

## What is still true, and still unresolved

- **Shorting 60 alts needs borrow that exists.** Deep perps only; the PIT universe includes
  names whose perp is thin. Not yet measured.
- **No slippage is modelled**, in the backtest or the paper book. A few bp per side on $18
  clips, stated so it can be subtracted later.
- **No order has been placed anywhere.** This is paper on live Binance prices.

Until the 26 rebalances are in, this is a well-tested hypothesis, not an edge.

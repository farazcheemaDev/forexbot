# 20 — The product: what the bot is, what it earns in each market, and what it cannot do

*2026-10-01. Written for the user's goal: "an end result bot, basically our product ... that can give crazy gains in
every time of market, not just bull." Every number names its file (CLAUDE.md rule 7).*

---

## 1. The product

**`combo_bot.py --mode demo --wick`**, one Bitget account, four books netted per coin:

| book | what it does | when it earns |
|---|---|---|
| **trend** (the triple) | 30-bar Bollinger breaks on 12 coins × 1h/4h/12h, 0.30% risk a unit, tight exit, time stop, up to 7 units, 10× gross guard, 21-day equity anchor | rising markets |
| **market-neutral** | long the top momentum decile, short the bottom, PIT top-60, weekly | every market, mostly on average |
| **bear sleeve** | market breadth: buy capitulation, sell exhaustion, only in bears | falling markets |
| **crash desk** | post-only bids 10% under on the top-40, cap 10 fills an hour, sold at the hour's close, none on bear days | rising and sideways markets |

**Where it runs:** the Azure VM, `combo-bot-demo.service`, since 2026-09-29 19:58 UTC (CLAUDE.md §10). Its paper twin
`combo_paper.py` (without the crash desk) has run there since 2026-09-24, pre-registered, verdict ~2027-03-24.

**What stands between it and money:** `ALLOW_REAL = False`. A human flips it — never a session — and only after the
two-week order-path check passes (`combo_bot.py --mode demo --report`, on the VM, counting from 2026-09-29), on a
**dedicated** account, since the bot closes any position it did not open.

## 2. What it earns, by market

`logs/machine.txt` (the four books on $300, 10 orderings, trend gains shrunk for hindsight and its losses kept whole,
the other books point-in-time and raw):

| market | months (of 80) | average month | typical month | months up |
|---|---|---|---|---|
| **RISING** | 31 | **+71.0%** | **+22.5%** | 71% |
| **FALLING** | 23 | **+7.6%** | **+4.7%** | 64% |
| **SIDEWAYS** | 26 | +0.2% | **−4.5%** | **32%** |

| $300, 12 months | 6 years | last 2 years |
|---|---|---|
| typical | $1,812 | $1,625 |
| bad (1 in 4) | $725 | $1,060 |
| worst | $222 | $454 |
| worst month | −29.3% | −25.0% |
| biggest fall | 57% | 45% |
| account left in the worst hour | 46% | 46% |

These are backtests on a holdout CLAUDE.md calls mined out. Plan on the forward record, not on this table.

## 3. The goal, measured against it

- **Rising markets: crazy gains — yes.** +71% average, +22.5% typical.
- **Falling markets: gains — yes.** +7.6% average, 64% of months up. The bear sleeve does it (doc 13).
- **Sideways markets: NO.** About flat on average, and **the typical sideways month loses about 4.5%**. Fewer than one
  sideways month in three is up.

**That last line is not for lack of trying.** Everything that could plausibly earn in a sideways crypto market at
retail has now been tested here, with predictions registered first:

| idea | file | result |
|---|---|---|
| cut the trend book only in chop | `dd_fixes.py` | −0.46 to −4.48 %/mo, 0–2 wins of 10: it must be in the market to catch the turn into bull |
| make the market-neutral book safer, so it can be bigger (a short stop; a wider basket) | `mn_stop.py`, `mn_scale.py` | both dead: the stop makes the worst week worse; width dilutes faster than it cuts the tail |
| weight the market-neutral book up | `all_weather*.py`, doc 19 | lifts the sideways **average**, not the **typical** month (its own chop month median is +0.2%); not adopted |
| grid trading, incl. gated to ranging markets | `grid_bot.py` | 29 of 30 cells lose after fees and funding |
| cash-and-carry (long spot, short perp) | `cash_carry.py` | 2.7%/yr gross in this era; fees exceed it |
| cross-sectional reversal, pairs, gated mean reversion | `bear_chop.py` | all lose; pairs break apart (72% exit at the stop) |
| 21 signals scanned inside each regime | doc 13 | one passed Holm — in BEARS (now the sleeve). None in chop |
| selling option premium | doc 11 | ~0 in 2026 |
| crash bids sized up only in chop | below | the tail lives in chop |
| a different asset class: the forex/commodity 12-month trend book | `fx_tsmom.py`, doc 18 | dead by arithmetic: +5.5%/yr (~0.45%/mo) swap-free only; even if ALL of it fell in crypto's 26 sideways months it is +1.4%/mo, +4.2% at 3× with ~70% falls - still short of the −4.5% it would have to cover |

**The last row, measured 2026-10-01** (`logs/wick_capped.pkl`, cap 10, labelled by `btc_regime`): the crash bids earn
**+0.035%/day in chop against +0.078% in bull**, and **7 of their 8 worst days are chop days** (2020-03-12 −3.35%,
2026-06-02 −2.72%, 2026-04-17 −2.69% ...). Sizing them up in chop buys the fatter tail and the thinner edge together.

**Why chop is closed at retail.** Every way to earn from a market going nowhere is a way of SELLING volatility —
grids, mean reversion, option premium, carry. Each is priced: by the market makers who sell it for a living, or by
funding that went to ~0 once the carry was crowded. A trend book is the opposite position (it BUYS volatility), and the
premium it pays in chop is what buys its bull months. Nothing here finds that premium for free.

## 4. So what the product is, stated exactly

**A bot that makes large gains in rising markets, makes money in falling markets, and roughly breaks even on average
in sideways markets — where a typical month loses about 4–5% and the year is carried by the other two.**

Do not describe it as "gains in every market". It is closer to that than anything else in the repo, and it is not that.

## 5. What would change this

- **Forward data, not another backtest.** `combo_paper.py` logs each book separately (`combo_marks.csv`). By
  ~2027-03-24 its own record shows the MN book's sideways months directly, which is the evidence doc 19 could not
  produce honestly.
- **Size, not strategy.** The worst month and biggest fall scale with size (`worst_month.py`: everything ×0.7 gives a
  −25.5% worst month and a $1,510 typical year). Sideways months stay about flat at any size.
- **Capital.** It changes dollars, not percentages (CLAUDE.md §6): $221 and $2,210 make the same % a month.

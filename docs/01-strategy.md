# The strategy

The thing that survived. Called **longtrend** in the code.

## In one paragraph

Buy coins that are breaking out to new highs, add more as they keep going, and
never take profit — just follow with a stop that trails a long way behind. Most
trades lose a little. A few run for hundreds of percent and pay for everything.
Separately, short coins that break down, but exit those fast, because crashes are
fast.

## The rules, exactly

### Long entries

| | |
|---|---|
| Signal | Hourly close **above** the upper Bollinger band (30 periods, 1.5 standard deviations) |
| Entry | Next bar's open |
| Initial stop | 2 × ATR(14) below entry — this distance defines "1R" |
| Adding | +1 unit every time the trade gains another **2R**, up to **5 units** total |
| Exit | Stop trails **20 × ATR** behind the best price reached. No take-profit. Ever. |

### Short entries

| | |
|---|---|
| Signal | Hourly close **below** the lower Bollinger band (same 30 / 1.5) |
| Size | **1 unit only** — no pyramiding |
| Exit | Stop trails **5 × ATR** behind the best price. Much tighter than longs. |
| Regime filter | **None.** Tested; it didn't help. |

### Portfolio

| | |
|---|---|
| Universe | 9 coins, re-picked monthly by *previous* month's dollar volume |
| Position cap | 8 open at once, longs and shorts sharing the same 8 slots |
| Risk | 0.13% of equity per unit → 0.65% if a position reaches all 5 units |

## Why each setting is what it is

### Why no take-profit

This is the single most important line in the file. A fixed profit target at 3×
ATR against a 2× ATR stop caps every winner at **+1.5R**. Trend following makes
its money from the rare enormous trade; capping it deletes exactly the trades
that pay for the losers.

Measured: of 6,054 trades in one run, the **top 25 produced 102.3% of the total
profit**. Cap those and there is no strategy left. Removing the cap took trend
families from 3-of-11 profitable to **11-of-11** (`backtest/holdout_uncapped.py`).

### Why 20× ATR for longs but 5× for shorts

Swept both directions independently (`backtest/shortside.py`):

| Trail | Long mean R | Short mean R |
|---|---|---|
| 3× ATR | +0.023 | **+0.025** |
| 5× ATR | — | **+0.028** |
| 12× ATR | — | lower |
| 20× ATR | **+0.897** | **−0.023** |

Longs improve all the way out to 20×. Shorts are *best tight and negative wide*.
Crypto grinds upward and crashes downward — a wide trail on a short gives back
most of the crash before it triggers. Every earlier test used one trail for both
and buried this.

### Why add to winners

Pyramiding was the largest single improvement found after removing the profit cap
(`backtest/pyramid.py`). It gave **more return and less drawdown at matched
total risk**, which is unusual — most return boosters cost drawdown. The reason:
added units are funded by profit that already exists, so the extra size only
appears on trades that are already working.

### Why shorts at all, when they barely make money

Standalone, shorts earn +0.056R against the long side's +0.674R — nearly nothing.
They are in the book because they earn in the years the long book bleeds:

| Year | Short-only return |
|---|---|
| 2021 | −38.7% |
| **2022** | **+91.8%** |
| 2023 | −57.1% |
| 2024 | −7.1% |
| **2025** | **+79.4%** |

The long-only version needs crypto to rise. This is the only thing tested that
addresses that.

### Why 8 slots

Because with more, the strategy takes trades a real account could not fund. An
earlier test pooled every signal regardless of whether a slot was free — on the
new-listing strategy, **81% of the "profitable" trades were ones you couldn't
have taken**, and once the cap was enforced every result went negative.

### Why 9 coins picked by last month's volume

Because picking "the 9 biggest coins today" means picking the coins that
*already went up*. Measured inflation from that hindsight: **3.05×**
(`backtest/pit_universe.py`).

## What this strategy is not

- **Not a prediction engine.** It has no opinion about where price is going. It
  reacts to a breakout and lets the market decide.
- **Not high win rate.** It loses most trades. Asking to "take the win rate to
  maximum" fights the design — a high win rate here means cutting winners short,
  which is the profit-cap bug all over again.
- **Not scalping.** Hourly bars. Crypto's percentage fees make anything faster
  unviable: see [doc 02](02-what-failed.md).

## The files

| File | Role |
|---|---|
| `backtest/pit_universe.py` | The definitive backtest — point-in-time universe, survivorship-free |
| `backtest/pyramid.py` | The add-to-winners engine |
| `backtest/convex.py` | The uncapped trailing-exit engine |
| `backtest/twoside.py` | Long + short sharing one slot cap |
| `backtest/shortside.py` | The asymmetric-exit sweep |
| `longtrend_bot.py` | Live/demo execution on Bitget |
| `longtrend_paper.py` | Paper version, $20 account |

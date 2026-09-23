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
| Own regime filter | **None.** A short-entry-specific filter was tested and didn't help. The book-wide gate below still applies ×0.25 to shorts - that is a different thing. |

### Portfolio

*Updated 2026-09-23 to the config the bots actually run. The previous version of this
table (9 coins, 8 slots, 0.13% risk) described a book that was superseded by the
three-timeframe blend and is no longer what is deployed anywhere.*

| | |
|---|---|
| Universe | **12 coins** (`blend.BOOK`) × **3 sleeves** (1h / 4h / 12h) = 36 independent signal streams |
| Position cap | **12 open at once**, shared across every coin *and* every timeframe |
| Risk | **0.30% of equity per unit** → 1.5% if a position reaches all 5 units |
| Duplicates | A coin may be open in more than one sleeve at once. Tested: that is a **feature**, not a leak (`book_structure.py` — capping at one per coin dropped the holdout to +2.15% at a 78% drawdown) |

### The regime gate

| | |
|---|---|
| Rule | While BTC's last closed 1h bar is **below its 1000-hour average**, risk per unit is cut to **×0.25** |
| Both sides | Applies to longs and shorts alike |
| Live implementation | `blend_paper.btc_bear()`, via `klines_deep()` — Binance caps a klines request at 1000 bars, so the 1000h average needs backwards paging. Verified 2026-09-23: fetches 2000 bars against the 1002 it needs |

**The 1000h vs 200h question is settled — see below. Short answer: the deployed gate is
the better one, and the gain is in drawdown, not return.**

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

### Why shorts at all, when they LOSE money

**Under an honest fill the short sleeve is negative: −0.036R per trade, −0.39%/month**
(`logs/strictfill.txt`). It reads +0.034R only under the optimistic convention, and the
realistic fill costs ~0.07R per short trade — *larger than the sleeve's entire edge*,
because a 5×ATR trail sits close to price where fill optimism actually bites.

**So expect the shorts to lose. A run of losing shorts is the strategy working to
spec, not misbehaving.** They are in the book as a **drawdown hedge**, and they earn
that keep two ways:

- drawdown **78.6% → 68.9%** versus long-only
- and they earn in the years the long book bleeds:

| Year | Short-only return |
|---|---|
| 2021 | −38.7% |
| **2022** | **+91.8%** |
| 2023 | −57.1% |
| 2024 | −7.1% |
| **2025** | **+79.4%** |

The long-only version needs crypto to rise. This is the only thing tested that
addresses that.

**Read the sleeves separately, always.** `--status` breaks results down by side for this
reason: "shorts down, longs open" is the expected shape, and averaging the two together
hides which half is doing what.

### Why a slot cap at all (the number was 8 when this was written, it is 12 now)

Because with more, the strategy takes trades a real account could not fund. An
earlier test pooled every signal regardless of whether a slot was free — on the
new-listing strategy, **81% of the "profitable" trades were ones you couldn't
have taken**, and once the cap was enforced every result went negative.

### Why coins are picked by LAST month's volume (9 then, 12 now)

Because picking "the biggest coins today" means picking the coins that
*already went up*. Measured inflation from that hindsight: **3.05×** - this is where
`blend.HINDSIGHT = 3.0` comes from, and why every %/month figure in these docs is
divided by it.
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

## The 1000h / 200h regime-gate discrepancy, resolved

*Added 2026-09-23. Source: `backtest/regime_gate.py`, log `logs/regime_gate.txt`.*

### What the discrepancy was

The live bots cut risk while BTC is below its **1000-hour** average. But `REGIME_MULT =
0.25` was validated in `opt200.py` against a **200-hour** average, and `blend.btc_bear()` —
the function behind most of this repo's stored figures — still uses `rolling(200)`.

200h is about 8 days. 1000h is about 6 weeks. A multiplier tuned for one being applied to
the other is not a cosmetic mismatch, so it got measured properly instead of staying a note.

### First: they are not the same kind of signal

| gate | hours flagged | entries gated | flips/yr | mean run | longest run | bear-hours in a run ≥7d |
|---|---|---|---|---|---|---|
| 200h | 47% | 54% | 292 | 1.2d | **18d** | 42% |
| 500h | 46% | 52% | 152 | 2.2d | 38d | 71% |
| **1000h** | 45% | 51% | 97 | 3.4d | **88d** | 84% |
| 2000h | 42% | 49% | 63 | 4.9d | 109d | 89% |

**The coverage is nearly identical** — every length flags ~45% of hours and ~50% of entries.
What changes is **persistence**. A 200h gate has *never once* stayed on for a month (0% of
its bear-hours sit in 30-day-plus runs; longest run in six years, 18 days). At 1000h, 49%
do, and the longest run is 88 days. One is a dip filter; the other is a bear-market flag.

*(An earlier version of this table reported median run length, which is ~0.1 days at every
MA and hides the entire difference — price oscillates across any average and throws off a
swarm of one-bar runs. The statistic was wrong, not the data.)*

### Second: the deployed gate is the better one

Deployed book, bear ×0.25, 5 orderings averaged, 3× haircut:

| gate | TUNE/mo | DD | HOLD/mo | DD | worst month |
|---|---|---|---|---|---|
| no gate | +23.97% | 86% | +3.64% | 86% | −48.8% |
| 100h | +23.37% | 81% | +2.38% | 79% | −31.8% |
| **200h** (tuned on) | **+23.48%** | **76%** | **+5.74%** | **74%** | −27.9% |
| 500h | +21.96% | 64% | +7.24% | 69% | −24.7% |
| **1000h** (deployed) | **+19.29%** | **55%** | **+8.44%** | **57%** | −33.9% |
| 2000h | +21.69% | 43% | +8.39% | 49% | −31.8% |

**The answer to "does the discrepancy hurt gains?" is no — it costs 4.2%/month of tune-half
return and buys a 21-point reduction in drawdown.** 76% → 55% on the tune half and 74% →
57% on the holdout.

That drawdown improvement is the part to trust, because **it shows up on both halves in the
same direction and the same size.** The +2.7%/month holdout *return* improvement is the part
not to trust: it is the "helps holdout, costs tune" signature that six other variants
produced on 2026-09-22, which is what an exhausted holdout looks like.

So: **the gate that is running is the right one, for a reason that survives the holdout
caveat.** Nothing needs changing.

### Third: ×0.25 is not a tuned parameter, it is a bet on the next regime

| gate | bear mult | TUNE/mo | DD | HOLD/mo | DD |
|---|---|---|---|---|---|
| 200h | 0.00 | +22.73% | 73% | +6.24% | 71% |
| 200h | **0.25** | **+23.48%** | 76% | **+5.74%** | 74% |
| 200h | 1.00 | +23.97% | 86% | +3.64% | 86% |
| 1000h | 0.00 | +15.73% | 55% | **+10.07%** | **48%** |
| 1000h | **0.25** | **+19.29%** | 55% | +8.44% | 57% |
| 1000h | 0.50 | +21.51% | 69% | +6.79% | 69% |
| 1000h | 1.00 | +23.97% | 86% | +3.64% | 86% |

Read the direction, not the best cell. **On the tune half, a bigger multiplier is always
better. On the holdout, a smaller one is always better. At both gate lengths.** The tune
half (2020 – 2024-08) was trend-rich, so betting through dips paid; the holdout (2024-08 on)
was chop, so cutting paid.

> The bear multiplier is not a parameter with a correct value. It is a bet on whether the
> next stretch trends or chops — and no amount of backtesting on past data can settle that.

×0.25 sits in the middle of that trade-off, which is the only defensible place for it to be
when the direction reverses between halves. **No change warranted.** What *would* be
defensible is treating it as a dial the user sets by conviction, not a number to optimise:
0.00 is the defensive end, 0.50 the aggressive end, and the drawdown cost is steep
(55% → 69% at 1000h going from 0.25 to 0.50).

### One operational trap this uncovered

2000h looks marginally attractive in the table above. **Do not set it without changing the
fetch.** `btc_bear()` requests `REGIME_MA + 100` bars and bails to its cached default if it
gets fewer than `REGIME_MA + 2`. At 2000h that needs 2002 bars from a paging function
currently asked for 2100 — it would work, but the margin is thin, and this exact failure
mode already happened once: when `REGIME_MA` went 200 → 1000 on 2026-09-14 on the old
300-bar fetch, **the gate silently turned itself off while every log line still claimed it
was armed.** Any change to `REGIME_MA` must be verified on the box, not assumed.

## Why 0.30% risk per unit, and why turning it up does not work

*Added 2026-09-23. Source: `backtest/kelly_corrected.py`, log `logs/kelly_corrected.txt`.
This supersedes `ruin.py`, which answered the same question on an engine that overstated
returns ~2x, charged no funding and read some entries from the future - and an overstated
return implies an overstated optimal bet size, so the old answer erred toward MORE leverage
than the strategy can carry.*

Swept on the corrected engine (entry-sized compounding, causal entry times, funding charged,
10 orderings, 3x haircut). Median geometric %/month:

| risk/unit | TUNE/mo | HOLD/mo | DD | worst DD | lev p99 | lev max | P(DD>80%) in 3yr |
|---|---|---|---|---|---|---|---|
| 0.10% | +2.35% | +2.48% | 20% | 27% | 1.6x | 3.1x | 0.1% |
| 0.20% | +3.85% | +4.00% | 38% | 48% | 3.2x | 6.2x | **0.1%** |
| **0.30% (deployed)** | **+4.89%** | **+4.96%** | **53%** | 64% | 4.8x | 9.4x | **2.7%** |
| 0.35% | +5.29% | +5.18% | 60% | 70% | 5.6x | **11.0x** | — |
| 0.45% | +5.86% | +5.30% | 70% | 80% | 7.3x | 14.2x | **24.7%** |
| 0.60% | +6.26% | **+4.55%** | 81% | 92% | 10.0x | 19.0x | — |
| 0.90% | +5.69% | **+0.97%** | 94% | 100% | 15.6x | 29.3x | 94.3% |
| 1.80% | −0.68% | −2.42% | 100% | 100% | 60.8x | 2218x | — |

**The answer is no, and the reason is not the one I predicted.** I expected gross leverage to
bind first. It does not - at the deployed 0.30% the book runs only **4.8x at p99**, so the 10x
p99 line sits near 0.63%. What actually binds is the probability of an unrecoverable drawdown:

> **Going 0.30% → 0.45% buys about +0.34%/month on the holdout and multiplies the chance of an
> 80% drawdown by nine, from 2.7% to 24.7%.** On a $200 account an 80% drawdown is $40, where the
> venue minimums start rejecting signals and the book stops being the book.

Three more things the sweep settles:

- **The holdout wants LESS risk than the tune half, not more.** Growth-optimal is 0.60–0.90% on
  tune but **0.45%** on the holdout, and by 0.60% the holdout return is already *falling*
  (+4.55% against +4.96% at 0.30%). I predicted the opposite. The half that was not fitted says
  the deployed setting is close to right.
- **`risk x1.33` (0.40%) is not the free win it looked like.** `graveyard_rescore.py` had it
  beating main on both halves, and doc 11 called it "a dial, not an edge". True - but its
  MAXIMUM gross leverage crosses 10x by 0.35%, and its ruin probability is on the steep part of
  the curve. It is a dial whose next click costs far more than it pays.
- **Cutting to 0.20% is cheap insurance.** −0.96%/month on the holdout takes P(DD>80%) from
  2.7% to 0.1% and the worst observed drawdown from 64% to 48%. For an account that must survive
  to compound, that is a defensible trade in the other direction.

**The cross-check that matters:** the TIGHT book reads +7.65% tune / +6.77% holdout at 0.30%
against main's +4.89% / +4.96% - agreeing with `graveyard_rescore.py` from a completely separate
simulator. Two independent files, same verdict on the tight exit.


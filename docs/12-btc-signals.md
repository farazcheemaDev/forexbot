# What moves BTC, and what the bot should do about it (2026-09-23)

*Asked for: "the best signals that trigger BTC or where the market moves... a strategy we can
apply on our current bot... because we know when to stop." Every number names its file.*

**Short version.** Fourteen market-timing signals were tested, from outside the price (Coinbase
premium, exchange flows, on-chain valuation, positioning, Nasdaq, the dollar, VIX) and from
BTC itself. **Two weakly predict BTC's direction:** US spot demand (the Coinbase premium) and
BTC's own multi-horizon momentum. **None of them improves the bot** once it already uses the two
BTC rules it runs today. As a pure BTC timing rule, **the bot's own 1000-hour average beat
everything else.** The strategy is the one already running, with the signals that belong in
it named, and a live readout: `python btc_regime_now.py`.

---

## 1. Fourteen signals — `backtest/btc_signals.py` (log `logs/btc_signals.txt`)

Every feature for day D uses data through the end of D−1. Sources: Coinbase Exchange API
(59k hours of BTC-USD, 47k of USDT-USD), the Binance metrics archive, the CoinMetrics community
API (MVRV, exchange in/outflows, active addresses), and Yahoo daily (QQQ, DXY, VIX). Predicted
signs were registered before any result. Month-block bootstrap; Holm across 14.

| signal | predicted | BTC next week, top − bottom third | bot's long trades, top − bottom third |
|---|---|---|---|
| **Coinbase premium, 7d** | + | **+2.11%/wk** (t 1.86), both halves + | **+2.01R** (t 1.94), both halves + |
| **BTC momentum 7/28/90d** | + | **+1.80%/wk** (t 1.97), both halves + | **+1.99R** (t 2.03), both halves + |
| taker buy/sell, 7d | + | +0.61 (holdout ≈ 0) | +2.86R (t 2.02), both halves + |
| dollar (DXY) 20d change | − | −0.81 (holdout +) | −1.98R (t −2.54), both halves − |
| exchange net inflow | − | −1.77 (t −1.48), both halves − | +0.60 (wrong sign) |
| top-trader long/short change | + | **−2.42** (t −2.01): **contrarian** | +0.86 |
| VIX | − | **+1.20**: high fear → BTC up, **contrarian** | +1.69 |
| OI vs price, alt season, MVRV, Nasdaq trend, BTC vol, address growth, premium change | | no consistent sign | fail |

**Nothing passes Holm on its own.** My registered expectation was "at most two pass, likeliest
tsmom and cb_prem". The two I named are the two that held their sign on both halves for both
targets. That is the only reason they are used below.

**What the market is telling you through them**, in plain terms:
- When US buyers pay up on Coinbase, BTC does better the following week.
- When BTC's trend is up on 1, 4 and 13 weeks, it tends to keep going: time-series momentum.
- When the crowd of top traders piles into longs, or VIX is calm, the next week is worse:
  both contrarian.

## 2. Using them on the bot — `backtest/btc_dial.py`

Regime: **BULL** = momentum ≥ +1 and Coinbase premium > 0 (50% of days), **BEAR** = momentum ≤
−1 and premium < 0 (13%), NEUTRAL otherwise. Bot's longs by regime at entry: **BULL +2.22R,
NEUTRAL +0.60R, BEAR +0.05R** (capped). That is a big separation per trade.

| use | tune | holdout | verdict |
|---|---|---|---|
| **risk dial** ×1.5 bull / ×0.5 bear, vs uniform bet at the same drawdown | **−0.71** %/mo | **+1.58** | holdout only |
| dial ×2 / ×1 | −0.57 | +1.47 | holdout only |
| dial ×2 / ×0.5 | −0.94 | +2.12 | holdout only |
| **stop**: tighten open longs when the regime turns BEAR (`logs/btc_dial_stop.txt`) | −0.95 ± 0.35 | −0.07 | dead |

**Why a signal that separates trades so well still adds nothing:** almost all of the bot's
profit is made by runners opened in bull regimes, and bear-regime trades are already cut to
quarter size by the 1000h gate. Scaling up the bull trades is scaling up nearly everything, so
it is betting more, which the uniform control does just as well on the tune half. Registered
predictions 1–3 all failed.

## 3. Trading BTC on them directly — `backtest/btc_timing.py`

Long/flat daily, 5bp a change, BTC funding charged, 2020-03 → 2026-09:

| rule | CAGR | drawdown | Sharpe | tune Sharpe | holdout Sharpe |
|---|---|---|---|---|---|
| buy and hold | +25% | 79% | 0.68 | 0.78 | 0.39 |
| **BTC > 1000h average (the bot's gate)** | **+45%** | **52%** | **1.12** | **1.23** | **0.82** |
| momentum ≥ +1 | +27% | 70% | 0.79 | 0.88 | 0.53 |
| Coinbase premium > 0 | +34% | 76% | 0.81 | 0.81 | 0.96 |
| BULL (both) | +24% | 67% | 0.74 | 0.82 | 0.53 |
| long BULL / short BEAR | +31% | 69% | 0.83 | 0.86 | 0.75 |

**The bot's own gate is the best BTC timing rule in the study**, including on 2025 (+3% against
−11% for holding) and 2026 (+5% against −14%). Registered prediction ("BULL has the best
Sharpe") was wrong. Simple, slow trend beats the clever inputs.

## 4. The last lever: BTC's 4h break at ENTRY — `backtest/btc_entry_gate.py`

The bot uses BTC's 4h trail break to tighten OPEN longs. Skipping or tightening NEW longs
during a break changes only ~30 of 7,434 trades (the break is an event, not a state):
+0.20 ± 0.40 / +0.69 ± 0.47 and +0.48 ± 0.27 / +0.24 ± 0.50 %/mo. Noise.

---

## The strategy, then — what the bot does and why each rule is there

| question | rule | evidence |
|---|---|---|
| **When to be in** | full risk while BTC > its 1000h average, ×0.25 below | best BTC timing rule tested (§3); gate settled in doc 01 |
| **What to buy** | 30-bar Bollinger break at 1.5σ on 1h/4h/12h, pyramid to 5 units | doc 01; indicator search exhausted (doc 02) |
| **When to stop — the market** | BTC's 4h trail breaks → open longs trail at 5×ATR (tight exit) | beats main on both halves, +2.9 / +2.0 %/mo (`graveyard_rescore.py`) |
| **When to stop — the trade** | still under +2R after 100 bars → close (time stop) | worst month −31% → −18%, both halves (`graveyard_rescore.py`) |
| **How much** | **0.3% per unit.** 0.6% is the ceiling for *3-month* lottery odds, not for running the book | `lottery.py` **and** `kelly_corrected.py` - see the note below |

**What it has returned** (`backtest/book_stats.py`, $221, corrected engine; upside after the 3×
hindsight haircut, downside raw).

**READ THE CONFIG COLUMN.** The table above describes tight exit + time stop, which is **paper
book #5 and is not deployed**. The bot running today is the main book. Quoting the bottom row as
"what the bot returns" overstates it by more than double:

| config | status | typical 12mo (holdout) | months losing | worst month | max DD |
|---|---|---|---|---|---|
| **main** | **DEPLOYED** | **$221 → $270 (+22%)** | **57%** | **−40.8%** | **53%** |
| tight exit | paper book #2 | $221 → $315 (+43%) | 56% | −34.7% | 50% |
| tight + time stop | paper book #5 | $221 → $485 (+119%) | 48% | −22.6% | 45% |

The deployed figure agrees with `expectations_honest.py` from a separate simulator ($200 → $241,
i.e. +20%), which is the cross-check that makes it trustworthy. The strategy table above this one
describes where the book is *heading* if the paper books hold up - not where it is.

### The risk ceiling: 0.6% and 0.3% are both right, for different horizons

`lottery.py` finds $221 at 0.6%/unit over **3 months** has 0% ruin (ruin = below 10% of start) and
a better median multiple than 0.3% (1.67× against 1.39×). `kelly_corrected.py` finds that over the
**full 6.5 years**, 0.60% has a *lower* holdout return than 0.30% (+4.55%/mo against +4.96%), a
median drawdown of 81%, and 92% in the worst ordering.

Both are correct. Three months is not long enough for an 80% drawdown to develop, so on a short
horizon more risk is more upside; over years it compounds into destruction. **So 0.6% is a
lottery-ticket setting for money that can be lost inside a quarter, and 0.3% is the setting for a
book meant to keep running.** Doc 01 has the full sweep with leverage and ruin per fraction.

On the honest, no-hindsight coin list (`lottery.py`, PIT top-12): typical year **2.2×** at 0.3%,
**2.6×** at 0.6%; 5× in about one year in four.

**But one coin carries it, and the concentration test in `logs/lottery_concentration.txt` should be
read before anyone acts on those odds.** `lottery.py`'s registered prediction was that PIT12 would
be far worse than the hindsight book at every risk. It came out better, its author went looking for
why, and found it:

| PIT12, $221, 12-month horizon | median × | P(≥5×) |
|---|---|---|
| all starts, 0.3% | 2.20× | 22% |
| all starts, **minus MYX** | 1.97× | **14%** |
| all starts, minus BNB+BTC+MYX | 1.85× | 12% |
| **holdout starts only, 0.3%** | **4.85×** | **49%** |
| **holdout starts, minus MYX** | **2.02×** | **8%** |

**On holdout starts, removing one coin takes the median from 4.85× to 2.02× and the chance of 5×
from 49% to 8%.** MYX contributed **+3,600R of the +13,432R** of all long R in that universe - 27%
from one name - including a single 1h trade worth **+2,205R**, which is an ~82× move from entry
during MYX's September 2025 pump.

That move was real. Whether it was *tradable* is a different question, and the backtest cannot
answer it: MYX in September 2025 was a thin, violently moving token, and the simulation fills at
the bar close with no slippage. The exit is a 20×ATR trailing stop firing into a crash in exactly
the kind of book where that assumption fails hardest.

**So the honest version of the no-hindsight odds is the minus-MYX row: about 2× in a typical year
at 0.3%, with 5× in roughly one year in seven.** The headline 2.2× is not wrong, it is just one
lucky token away from 1.97×, and the holdout figure of 4.85× is more than half one trade.

## The live readout

`python btc_regime_now.py` prints, from public endpoints only (no keys):
- the gate (above or below the 1000h average, and by how much),
- the 4h break level (the price whose 4h close tightens every open long),
- momentum, the Coinbase premium and funding as context.

On 2026-09-23 15:00 UTC: BTC $83,996; gate BULL (+10.2% above $76,222); break level
$81,622 (−2.8%); momentum +3/3; premium +0.002%; funding neutral; regime BULL.

## Update 2026-09-24 — the pyramid finding stacks with the time stop — `backtest/units_on_tstop.py`

The other session's `pyramid_params.py` found MAX_UNITS=7 beats 5 on the tight book (commit
0214658; paper book #6). Its baseline was TIGHT. The recommended book is TIGHT + TIME STOP, so
whether the two stack was checked here. Same corrected engine, 0.30% risk, 10 paired orderings
(`logs/units_on_tstop.txt`):

| book | tune %/mo | DD | worst mo | holdout %/mo | DD | worst mo |
|---|---|---|---|---|---|---|
| main (deployed) | +4.88 | 54% | −20.9% | +4.88 | 53% | −33.5% |
| tight + time stop (paper #5) | +7.38 | 44% | −21.3% | +9.22 | 45% | −18.2% |
| **tight + time stop + 7 units** | **+8.89** | 48% | −23.6% | **+10.76** | 51% | −19.2% |

Paired: **+1.51 ± 0.06 tune, +1.54 ± 0.08 holdout over TSTOP, 10/10 orderings each**; against
main +4.01 / +5.89. The tight + 7 units vs tight figure reproduces pyramid_params.py exactly
(+1.31 / +1.07). **Registered prediction** (+0.9 to +1.3 on both halves, worst month within 2
points): the gain was larger than predicted; the worst month was 2.3 points deeper on the tune
half. No paper book runs all three rules together yet. A seventh book combining #5 and #6 is
the next step, and it belongs to whoever owns `blend_paper.py`.

## Update 2026-09-24 (later) — the triple with the bot's 10× margin guard — `backtest/triple_capped.py`

The triple reaches 12.2× gross leverage in the backtest (`regime_and_liq.py`).
`blend_paper.py` refuses any entry or pyramid add that would take gross notional past 10×
equity. That guard is now modelled: each position is split into its units, and a unit is
refused if it would breach 10× realised equity.

| book | guard | tune %/mo | holdout %/mo | DD | worst month | adds blocked |
|---|---|---|---|---|---|---|
| main | off / 10× | +4.85 / +4.85 | +4.92 / +4.92 | 53% | −33.5% | 0% |
| tight + time stop | off / 10× | +7.44 / +7.44 | +9.25 / +9.25 | 45% | −18.2% | 0% |
| **triple** | off | +8.97 | +10.78 | 51% | −19.2% | — |
| **triple** | **10×** | **+8.72** | **+10.43** | 50% | −19.2% | 2.2% |

- **The guard costs the triple −0.25 ± 0.04 (tune) / −0.35 ± 0.02 (holdout) %/mo.** The 5-unit
  books never reach 10×. With the guard off the file reproduces `units_on_tstop.py` within
  0.1, which is the check that the unit decomposition is right.
- **$221 after 12 months, guarded:** typical **$536** (holdout) / **$584** (full), haircut;
  bad year $407 / $318; ended below $221 in 1% / 8% of windows; worst $207 / $164 raw.
- **Registered prediction** (a 0.1–0.2 %/mo cost, a lower worst month): the cost came out a
  little larger than predicted, and the worst month did not change.
- **A bug caught before any number was quoted.** The first run read 1,116 trades instead of
  1,893 and a guard that never fired. A position that closed on its own entry bar had its close
  sorted before its entry, so it never closed and held a slot forever. It is fixed, commented
  in the file, and verified on one ordering against `btc_dial.taken` (+5.23 vs +5.21 %/mo).

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
| **How much** | 0.3% per unit; 0.6% is the most for "crazy" odds without ruin | `lottery.py` (doc 11 part 3) |

**What it has returned** (`backtest/book_stats.py`, $221, corrected engine; upside also shown
after the 3× hindsight haircut, downside raw):

| | holdout (2024-08 →) | full history |
|---|---|---|
| typical 12 months | **+119% haircut** (+358% raw) | +134% haircut |
| months losing money | 48% | 48% |
| worst month | −22.6% | −24.7% |
| max drawdown | 45% | 48% |

On the honest, no-hindsight coin list (`lottery.py`, PIT top-12): typical year **2.2×** at 0.3%,
**2.6×** at 0.6%; 5× in about one year in four; about 2× in a typical year even with the single
best coin (MYX) removed.

## The live readout

`python btc_regime_now.py` prints, from public endpoints only (no keys):
- the gate (above or below the 1000h average, and by how much),
- the 4h break level (the price whose 4h close tightens every open long),
- momentum, the Coinbase premium and funding as context.

On 2026-09-23 15:00 UTC: BTC $83,996; gate BULL (+10.2% above $76,222); break level
$81,622 (−2.8%); momentum +3/3; premium +0.002%; funding neutral; regime BULL.

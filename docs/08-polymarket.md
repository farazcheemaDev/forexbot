# Polymarket

*Tested 2026-09-14. Status: **large apparent edge, not believed, forward test running.***

## Why it was worth looking at

**No minimum order.** That is the single constraint that killed every small-capital
idea in this project — Bitget's $5 floor forces a $10 account to risk 1.26% per trade
whether it wants to or not, and that forced over-risk is why 70% of paths die. On
Polymarket a $10 account can hold twenty genuine positions.

And a contract **settles itself** at $1 or $0, so a hold-to-resolution strategy crosses
the spread **once**. Measured live: **1.9% of price** in the 50–65¢ band, which is the
cheapest band because that is where the liquidity sits. Round-tripping would cost 5–7%
and be hopeless; entering once and waiting is affordable.

## What the backtest found

800 resolved markets, price taken 30 days before trading stopped:

| Price band | Resolved YES | Gap | Edge after 2.5% cost |
|---|---|---|---|
| 0.10–0.20 | 0.041 | **−0.102** | −0.127 |
| 0.30–0.50 | 0.477 | +0.053 | +0.028 |
| **0.50–0.65** | **0.841** | **+0.266** | **+0.241** |
| 0.65–0.80 | 0.979 | +0.245 | +0.220 |

The low end shows **classic longshot bias in the correct direction** — 14¢ contracts
resolved 4% of the time. That part matches a century of betting-market literature.

The 50–65¢ band shows a **+25% edge per resolution.**

### Checks it survived

| Check | Result |
|---|---|
| Event clustering (42 markets, 35 events) | not concentrated; max 2 per event |
| One observation per event | gap **+0.250**, t = **+3.87** |
| Split by time | older half +0.233, recent half +0.326 |
| Second independent sample (different ordering) | +0.225, t = +3.03, both halves positive |

## Why it is not believed

**Three measurement artifacts were found inside this same test, and each looked like a
discovery first:**

1. **Volume ordering** selected markets where the underdog came in, flipping the sign
   of longshot bias. A longshot that *comes in* generates far more volume than one that
   fizzles.
2. **The `endDate` anchor** sat a median of **574 days** after the last real trade, so
   `endDate − 1 day` and `endDate − 7 days` both fell past the whole price history. The
   1-day and 7-day tables came out **byte-identical** — that is how it was caught.
3. Which meant the first "edge" was sampling the **final** price: it measured the
   market being *right*, not mispriced.

**The remaining suspect cannot be ruled out from history at all.** Requiring 30 days of
price history may select toward YES: a market heading for NO often stops trading
early — the candidate withdraws, the event fizzles — while one heading for YES trades
until it resolves. If so, "has 30+ days of history" is partly a filter for outcomes
that happened, and that filter is baked into which history exists.

A 25% free lunch in a market with hundreds of millions of dollars of volume should not
exist.

## The forward test

`poly_forward.py`, running on the VPS as `poly-forward`. Records live prices on **open**
markets and checks them at resolution. No history-length filter, no sampling order, no
anchor — the outcome has not happened yet, so nothing about the snapshot can depend on
it.

**Pre-registered before any data:**

- at least **120 resolutions** in the 0.50–0.65 band
- observed YES rate exceeds mean snapshot price by more than **2 standard errors** on
  the *event* count
- gap exceeds **+0.10** — half the backtested figure

Anything less is reported inconclusive. **Every band is recorded**, not just the
interesting one, so this cannot quietly become a test of the band that already looked
good.

A market is snapshotted **once**, the first time it is seen, and never overwritten —
re-snapshotting later would let the price drift toward the outcome, which is exactly
the leak that broke the backtest.

### Current state

| | |
|---|---|
| Markets tracked | **978** across 327 events |
| In the 0.50–0.65 band | 27 (need 120) |
| Resolved so far | 0 |
| First readable answer | **4–8 weeks** |

```bash
python poly_forward.py --report
```

## What this is not

**Not a reason to fund a Polymarket bot.** The number is too good and this test has
broken three times. If the forward version confirms it, that is the first genuinely new
edge in the project and it works at $10 — because there is no minimum order. If it does
not, the backtest was survivorship in a new costume and the matter is closed properly.

## Files

| File | Role |
|---|---|
| `backtest/polymarket_bias.py` | the historical calibration test, with all three artifacts documented in the code |
| `poly_forward.py` | the pre-registered forward test |
| `deploy/poly-forward.service` | systemd unit |
| `logs/poly_snapshots.csv` | one row per market, written once |

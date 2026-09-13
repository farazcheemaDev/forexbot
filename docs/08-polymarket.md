# Polymarket

*Tested 2026-09-14. Status: **large edge, artifact hypothesis dead, forward test
running.** Read the 2026-09-14 update below — it reverses the earlier verdict.*

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

**The remaining suspect was:** requiring 30 days of price history may select toward
YES — a market heading for NO often stops trading early, while one heading for YES
trades until it resolves. If so, "has 30+ days of history" is partly a filter for
outcomes that happened.

## That suspect is now dead, and I was wrong (2026-09-14)

`backtest/poly_fast.py`. If a history-length filter creates the edge, the gap **must
grow with market lifetime** — strong where the filter bites, absent where it barely
applies. 9,087 observations across three sampling orderings:

| Market lifetime | Events | Gap | t |
|---|---|---|---|
| **lived 0–7 days** | 46 | **+0.149** | +2.22 |
| lived 7–30 days | 74 | +0.103 | +1.89 |
| lived 30–90 days | 60 | +0.127 | +2.14 |
| lived 90+ days | 30 | +0.018 | +0.20 |

**Flat, and largest in markets that lived under a week** — exactly where the filter
barely applies. A lifetime filter cannot produce that shape. (The 90-day bucket that
looks different is the smallest and least precise of the four, ±0.091. One noisy
endpoint is not a trend.)

**Registered prediction before running: the gap would grow with lifetime. It didn't.**

### And it holds under the weakest possible filter

| Horizon | Events | Gap | t |
|---|---|---|---|
| **1 day** | 205 | **+0.105** | **+3.21** |
| 7 days | 167 | +0.124 | +3.53 |
| 30 days | 113 | +0.174 | +4.29 |

At one day out a market needs one day of history to qualify — essentially no selection
pressure at all.

### The shape is coherent, not scattered

| Band | Priced | Resolved | Gap |
|---|---|---|---|
| 0.00–0.05 | 0.008 | 0.002 | −0.006 |
| 0.20–0.35 | 0.267 | 0.289 | +0.022 |
| 0.35–0.50 | 0.422 | 0.400 | **−0.022** |
| **0.50–0.65** | 0.571 | **0.676** | **+0.105** |
| **0.65–0.80** | 0.717 | **0.844** | **+0.127** |
| 0.95–1.00 | 0.987 | 0.993 | +0.006 |

Calibrated at both extremes, mispriced in the middle-upper range. Mild favourites
underpriced, the just-under-even side overpriced. That is a pattern, not the scatter an
artifact usually leaves.

**Note 0.65–0.80 is larger than the band that was pre-registered.** 0.50–0.65 was chosen
before any of this was visible.

### Current status: more likely real than not — still not funded

The effect survived the test built to kill it. But every one of these is a historical
sample, and historical samples are where all three earlier artifacts lived. The forward
test remains the only thing immune to how the data was chosen.

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
| Markets tracked | **1,768** across 665 events (a full scan — Polymarket has ~2,100 open binary markets) |
| In the 0.50–0.65 band | **59** |
| Resolved so far | 0 |
| First readable answer | **1–3 weeks** |

The collector now scans to exhaustion rather than stopping at 1,200, and checks for
resolutions every 3 hours instead of every 24 — recording a market and noticing it
resolved are different jobs.

**The 120 threshold is not the size needed to see the claim.** It was chosen to resolve
+0.10, half the backtested figure. Detecting the claimed +0.25 needs about **16 events**.
So an interim read can confirm or refute the big claim far sooner — `--report` now prints
what the sample in hand can actually detect, while being explicit that it cannot rule out
a small real edge.

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

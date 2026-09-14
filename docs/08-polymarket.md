# Polymarket

*Tested 2026-09-14. Status: **historical edge survived the test built to kill it; a
FOURTH artifact then turned up; the forward test has produced 0 resolutions and its
timeline is unknown. Nothing is fundable.***

**If you are here to decide whether to deposit money: don't, and read
[What $5 actually buys](#what-5-actually-buys) for why $5 is strictly worse than the
free test already running.**

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

## Why it was not believed

**Four measurement artifacts have been found inside this same test, and each looked like
a discovery first:**

1. **Volume ordering** selected markets where the underdog came in, flipping the sign
   of longshot bias. A longshot that *comes in* generates far more volume than one that
   fizzles.
2. **The `endDate` anchor** sat a median of **574 days** after the last real trade, so
   `endDate − 1 day` and `endDate − 7 days` both fell past the whole price history. The
   1-day and 7-day tables came out **byte-identical** — that is how it was caught.
3. Which meant the first "edge" was sampling the **final** price: it measured the
   market being *right*, not mispriced.
4. **Dead books priced at exactly 0.50** (found 2026-09-14 in the *forward* collector,
   before it could do damage). Polymarket keeps abandoned markets `active`
   indefinitely — 49 of the 1,814 tracked are past their `endDate` and still open, one
   by **ten months**. An abandoned market has bid ~0.002 / ask ~0.998, and **the
   midpoint of that empty book is 0.50 — the middle of the pre-registered target
   band.** `Will Hannover 96 win on 2025-11-28?`: liquidity $0.02, spread 99.6c, never
   traded, reads as a 50¢ contract. The guard `0 < bid < ask < 1` did not exclude it.
   Measured contamination: **3 of 62 band markets (5%)**, small only because the scan
   is ordered by volume — luck, not a filter — and it would have grown as the scan
   reached deeper into the tail. `poly_forward.py` now requires spread ≤ 15c and
   liquidity ≥ $100; the 59 genuine band markets have a median spread under **2c** and
   median liquidity **$43,797**, so nothing real is excluded.

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

### Current status: survived its hardest test, and still not fundable

The effect survived the test built to kill it, and that is worth something. But every one
of these is a historical sample, and historical samples are where all the earlier
artifacts lived — and artifact #4 then showed the *forward* collector was exposed to one
too. The forward test remains the only thing immune to how the data was chosen, and it
has produced **zero** resolutions.

## The forward test

`poly_forward.py`. **Runs on the local PC, not the VPS** — the Azure VM is in Korea
Central and Polymarket returns HTTP 451 there, a jurisdictional block rather than a
network fault. That costs little: it snapshots once a day and markets stay open for
weeks, so a day the PC is off rarely loses a market permanently.

Records live prices on **open** markets and checks them at resolution. No history-length filter, no sampling order, no
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

### Current state (2026-09-14)

| | |
|---|---|
| Markets tracked | **1,814** across 665+ events (a full scan — Polymarket has ~2,100 open binary markets) |
| In the 0.50–0.65 band | **62**, of which **59 clean** after the tradability filter |
| **Resolved so far** | **0** |
| First readable answer | **unknown — see below** |

```bash
python poly_forward.py --report
```

The collector scans to exhaustion rather than stopping at 1,200, and checks for
resolutions every 3 hours instead of every 24 — recording a market and noticing it
resolved are different jobs.

**The 120 threshold is not the size needed to see the claim.** It was chosen to resolve
+0.10, half the backtested figure. Detecting the claimed +0.25 needs about **16 events**.
So an interim read can confirm or refute the big claim far sooner — `--report` prints what
the sample in hand can actually detect, while being explicit that it cannot rule out a
small real edge.

### The timeline estimate was wrong, and how it was wrong matters

**An earlier version of this doc said "1–3 weeks." Delete that from memory.** It was
computed from each market's `endDate`, and `endDate` has now been caught running up to
**ten months early**: 49 tracked markets are past their stated end date and still
trading.

`endDate` is **the same field that produced artifact #2**, where it sat a median of 574
days after the last real trade. So the rule this breaks is not "check your data" — it is
narrower and more embarrassing:

> **A field that has already lied to you once does not get trusted for a second purpose.**
> It was distrusted as a *price anchor* and then used as a *schedule*, as though the
> unreliability were attached to the use rather than to the field.

The honest position: **the time to an answer is unknown and longer than previously
stated.** No estimate replaces it, because there is no field left that would support one.

### What was deliberately NOT done to speed it up

Markets that resolve within days are almost entirely **sports**. Retargeting the
collector at them would produce resolutions quickly — and would quietly swap the
pre-registered population for a different, far better-priced one. That is precisely the
mechanism behind the first three artifacts, so the broad collector runs unchanged and
slow instead.

## What $5 actually buys

The question that prompted this section was "do you have numbers now, then I can deposit
$5." The answer is no, and the arithmetic says $5 makes the evidence *worse*, not better:

| | Free collector | $5 deposited |
|---|---|---|
| Sample | **1,814 markets** | ~10 positions at 50¢ |
| Cost | $0 | $5, plus **2–20%** lost moving USDC to Polygon |
| Time to an answer | months | the same months |

**$5 would pay money for one-180th of the information already being collected free.**
Detecting the claimed +0.25 needs ~16 in-band resolutions; $5 buys ten positions that
each resolve once.

**The one thing a deposit does test, that the collector cannot:** the plumbing. Whether
USDC can be moved onto Polygon from Pakistan, an order placed, and funds withdrawn —
the same role the Bitget demo bot plays for crypto. That is a legitimate purchase, but
it buys an order path, not evidence. **Check the Bitget→Polygon withdrawal fee first:**
at ~$1 on $5 that is 20% gone before the first trade, which argues for $20 rather than
$5 if the plumbing test is to be honest about costs.

## What this is not

**Not yet a reason to fund a Polymarket bot.** The number is large and this test has now
broken **four** times, so the forward evidence comes first. If the forward version
confirms it, that is the first genuinely new edge in the project and it works at $10 —
because there is no minimum order. If it does not, the backtest was survivorship in a new
costume and the matter is closed properly.

**Hypothetically, if it is real** — asked and answered, recorded here so the figure is not
re-derived optimistically later. A +0.105 gap on a 0.571 contract minus ~1.9% entry cost
is **+16% per resolution** at the 1-day horizon (+28% at 30 days; plan against the short
one, which has the least room for hidden selection). Win rate ~68%, each position binary
at +72% or −100%, and a 20-position book swings ±18% per cycle with roughly a 1-in-6
chance of a losing cycle. After haircuts for event correlation, band selection and gas:
**+12–16%/month, and it works from $10.** Better than everything else in this project on
every axis — return, win rate, and minimum capital — **which is exactly why it is not
believed yet.** A finding that good in a market with hundreds of millions flowing through
it is more likely a measurement error than a discovery, and four have already been found
here.

## Files

| File | Role |
|---|---|
| `backtest/polymarket_bias.py` | the historical calibration test, with all three artifacts documented in the code |
| `poly_forward.py` | the pre-registered forward test |
| `backtest/poly_fast.py` | the lifetime-stratification test that killed the artifact hypothesis |
| `deploy/poly-forward.service` | systemd unit — **do not enable in a region that returns 451** |
| `logs/poly_snapshots.csv` | one row per market, written once |

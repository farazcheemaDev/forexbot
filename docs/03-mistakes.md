# Mistakes and the rules they produced

Every bug that produced a wrong result, and what was added to stop it recurring.
This list exists because **most of the "findings" in this project were initially
wrong**, and the pattern of how they were wrong is more valuable than any single
strategy.

Full technical detail:
[`strategy_analysis/validation_protocol.md`](../strategy_analysis/validation_protocol.md).

---

## The big ones

### 1. The profit cap — wrongly killed six strategies

Every early test closed winners at a fixed target (`tp_mult = 3.0` against
`sl_mult = 2.0`), capping every winner at **+1.5R**. For trend following that
isn't a detail, it's the whole result: these strategies make their money from the
rare enormous trade.

**Damage:** a false "SURVIVORS: NONE" across six files and 18 strategy families.
Weeks of work discarded strategies that worked.

**Rule:** no fixed profit target in any trend or momentum test, ever. If a test
uses one, its negative verdicts are void.

### 2. The price-mirror bug — flattered shorts 4×

To reuse the long engine for shorts, prices were mirrored around `2 × first_close`
and traded as longs. Valid only if price never doubles. SOL rose **97×**, so 92%
of its mirrored bars were *negative prices* — and since fees are charged as
`fee × price`, the fee came out with the wrong sign.

**Damage:** shorts reported +0.117R where the correct engine gives +0.028R. Every
two-sided result derived from it was void.

**Caught by:** two of our own test files disagreeing on identical trade counts.

**Rule:** never transform the price series to reuse an engine. Handle direction
natively (`d = −1`). Cross-check any new engine against an existing one on
identical inputs.

### 3. Hindsight universe — 3.05× inflation

Backtesting "the top 9 coins today" means backtesting coins that already went up.

**Rule:** universe selection must be point-in-time — rank by the *previous*
period's dollar volume, never by anything that knows the future.

### 4. Survivorship — 30% of coins are dead

203 of 735 USDT pairs that ever existed are delisted. A backtest on today's list
measures survivors only.

Worse: positions still open when a coin's data *ended* were being silently
dropped — deleting exactly the catastrophe that dead-coin data exists to measure.

**Rule:** include delisted assets, and force-close open positions at the data's
end (`close_at_end="close"` for an announced delisting, `"stop"` for a collapse).

### 5. Unplaceable trades — 81% of one strategy's profit

New-listing momentum showed +0.122R by counting every signal, regardless of
whether a position slot was free. With a real 8-position cap, 81% of those trades
couldn't have been taken, and every result went negative.

**Rule:** every portfolio test enforces a concurrent-position cap.

### 6. Compounding by trade instead of by date

23,539 pooled trades were multiplied sequentially, as if 9 coins' trades happened
one after another at full risk. They overlap in time.

**Symptom that exposed it:** every table showed drawdown of exactly 100.0%.

**Rule:** sum R across trades that closed on the same day, then compound the
daily series.

### 7. Ruin at a rounding error

Equity was allowed to fall to 1e-9 and compound back up, producing "+12,854%/yr
with a 100% drawdown". A real account down 99.99% holds a few cents and cannot
meet any minimum order.

**Rule:** practical ruin floor at 1% of starting equity. Below that the account
is finished and every later figure is fiction.

### 8. A silent no-op family name

`"donch"` was never a valid family name, and `gen_signals` returned an all-HOLD
series instead of raising — so 3 of 7 families in one file did nothing at all and
reported it as a result.

**Rule:** unknown names raise. Never return an empty signal series silently.

---

## Live-trading bugs

### The entry-bar stop check

The bot enters at a bar's close, then checked its stop against *that same bar's*
high/low — data that predates the position. It killed a live ETH short in **62
seconds** at −1.00R. Near-automatic for shorts.

**Fix:** skip stop checks on the entry bar (`entry_bar` guard) and evaluate once
per *closed bar*, not once per 60-second poll. The `bars` counter was counting
polls.

### Duplicate bot instances

A process check (`wmic | grep`) missed a running bot because of line wrapping;
between-bar silence was read as death; the restart put **two bots on one
account**.

**Fix:** `acquire_lock()` — a single-instance lock file.

**Second fix, 2026-09-14:** `health.py`. The lock stops the damage but did nothing about
the *misreading* that caused it. The check now reports three independent signals
separately — process (pid cross-checked against the command line), heartbeat (mtime of
the file written every cycle, **never** the log, because bots log once per closed bar),
and progress — so "silent" can no longer be mistaken for "dead". It also names the state
that is worse than death: **WEDGED**, alive but not writing, holding the lock so a
restart refuses while open trades go unmanaged. See [doc 04](04-operations.md).

---

### 9. Re-trusting a field that had already lied

The Polymarket forward test was given a "1–3 weeks to an answer" estimate computed from
each market's `endDate`. `endDate` was **already known to be unreliable** — it is the
field behind artifact #2, where it sat a median of 574 days after the last real trade.
It was distrusted as a *price anchor*, then used as a *schedule*, as though the
unreliability attached to the use rather than to the field. It ran up to **ten months**
early: 49 tracked markets are past their stated end date and still trading.

**Rule:** a field that has been caught lying once is retired for *every* purpose, not
just the one it was caught on. Distrust attaches to the data, not to the use.

### 10. A liveness guard that admitted dead books

`poly_forward.py` accepted any market satisfying `0 < bid < ask < 1`. An abandoned
Polymarket market — kept `active` indefinitely — has bid ~0.002 / ask ~0.998, and **the
midpoint of that empty book is exactly 0.50, the middle of the pre-registered target
band.** The guard tested that a book was *well-formed*, not that it was *tradable*.

Caught at 5% contamination (3 of 62 band markets) and only that low because the scan
happened to be ordered by volume.

**Rule:** when the claim depends on a cost of execution, every recorded price must be one
that could actually have been executed. Well-formed is not the same as tradable.

### 11. A resolver that could never see a resolution (2026-09-21)

`poly_forward.py` looked up its tracked markets on Gamma with no `closed` filter. **Gamma
silently leaves closed markets out of any query that does not ask for them**, so a market
dropped out of the results at the exact moment it resolved. For a week the log read
"0 resolved" across 1,976 markets. That was read as "slow" when it meant "blind".
Adding `closed=true` found **207 resolutions on the first pass**.

It went unnoticed because zero was a plausible-looking number. Doc 08 had just explained
why the test would be slow, so a count of zero seemed to confirm that explanation.

**Rule:** before trusting a count of zero, check that the code path can produce a
non-zero. Feed the resolver one market that is known to be resolved and watch it come back.

---

## Reporting mistakes

These produced no code bug but wasted time and destroyed trust:

- **Quoted 9-coin returns for a 3-coin book** — a 3× overstatement on the live bot.
- **Quoted numbers from three different simulation engines interchangeably**, and
  two different hindsight ratios (2× vs the measured 3.05×). **Rule:** every
  number in one comparison comes from one engine, or the engine is named.
- **Declared data nonexistent after checking one source** — twice (delisted
  history, tick data). Both were on `data.binance.vision`. **Rule:** "I couldn't
  find it" is not "it doesn't exist"; name the sources checked.
- **Over-generalised "5-minute bars are dead."** True for crypto (percentage
  fees), false for gold and Nasdaq (fixed spread). **Rule:** cost conclusions are
  per-instrument, because the fee *structure* differs.
- **Read MAR (return ÷ drawdown) as improving with risk.** It inflates as
  drawdown approaches 100% because drawdown is capped at 100%. **Rule:** MAR is
  meaningless above ~60% drawdown.
- **Got the minimum capital wrong three times, each time too low.** First $9
  (used 0.5% risk for the order floor while the config risks 0.13%/unit), then
  $116 / $35 (computed off the *cheapest* coin's minimum order instead of the
  *binding* one). Measured properly in `backtest/venue_floor.py`: the 9-coin book
  needs **~$1,500**, because ETH's 0.01 step is $25 of notional and the book needs
  every coin in it. **Rule:** a portfolio's capital floor is set by its most
  expensive contract, never its average or its cheapest — and the floor must hold
  *at the bottom of the drawdown*, because an account that cannot place an order
  cannot recover.
- **Killed the wrong process** (PID 15036 — a running pre-registered test).

---

## The meta-lesson

Nine of the ten errors above made results look **better** than reality; the
profit cap made them look worse. Errors are not randomly signed — a bug that
flatters a strategy survives longer than one that hurts it, because nobody
investigates good news.

**So:** register the prediction before running the test. Every file in
`backtest/` that tests something new now states, in its docstring, what result
would count as failure — *before* the numbers exist.

### 11. Mistake #6 is still live in `blend.py` — the harness that validated everything

`blend.run()` does exactly what rule #6 forbids:

```python
for a_, b_, r, tag, _c in tr:      # trades from 12 coins x 3 timeframes
    eq *= (1 + r * f)              # multiplied SEQUENTIALLY
```

Those trades overlap in time. The rule says sum R across trades closing on the same day,
then compound the daily series. Found 2026-09-14 when two harnesses disagreed on the same
number and the wrong one was the validated one.

**Size of the error, on the deployed config:**

| Window | Per trade (wrong) | **Per day (right)** |
|---|---|---|
| 2020–2026 | +15.47%/mo | **+14.22%/mo** |
| **2026** | **+0.22%/mo** | **−0.13%/mo** |

Over the full history it inflates by ~8% — survivable. **In 2026 it flips the sign.** Every
figure quoted from `blend.run()` today carries this, including the "~+8%/month"
expectation and the +240%/yr headline.

**Rule (restated, because stating it once was not enough):** a rule written in this file is
not applied until the code that produces the headline number is checked against it.
`ddcontrol.py` and `pit_blend.py` compound correctly; `blend.py` never did.

---

## Three found on 2026-09-23, all flattering, all in the engine every result stands on

### 12. A bar's label is not its entry time — `backtest/causal_t0.py`

`timeframes.resample()` labels a 4h/12h bar by its right edge, and `signals()` enters at the
bar's open, so every 4h row's `t0` is **3h after the real entry** and every 12h row's is
**11h after**. Anything that reads a time series with `asof(t0)` on those rows sees the future.
The short boost did (`vol_target.short_boost`, `composite.rowset`), and 118 of its 224
"boosted" shorts were only boosted because BTC broke down *after* they opened. Boosted-short R
fell +0.481 → +0.305 when this was fixed, and the boost's value to the book went from +1.3–2.3
to about +0.5%/mo on the holdout. The regime gate and the slot queue read the same late
stamp. **Rule:** before gating, ordering or tagging engine rows by time, call
`causal_t0.real_t0(rows)`.

### 13. Funding was never charged — `backtest/funding_cost.py`

Fees were charged everywhere and funding nowhere, in a book that holds five-unit pyramids for
weeks through bull markets. It cost **21.5% of lifetime long R**, 46% on the 12h sleeve, and it
takes the tune half from +16.5% to +12.2%/mo. Bitget's funding ran *above* Binance's on all 11
book coins over the window its API serves, so the true cost here is higher. **Rule:** a
position held across settlements is charged `funding_cost.charged(...)`, and any file that
does not is labelled "fees only".

### 14. Compounding a trade by equity it was never sized on — `backtest/compounding.py`

Mistake #6 fixed the ORDER of compounding. It left in place the assumption that a closing
trade's R is scaled by the equity at its close. The bot fixes a position's dollars at entry.
In a book whose profit is a few overlapping runners, scaling each one by equity the others
already banked roughly **doubles** the reported monthly return (holdout main: +8.83% daily sum,
+13.50% sequential, **+4.88% entry-sized**). `mtm_sizing.py` checked whether any entry-time
sizing rule could earn the difference back, and none can. The same assumption sits in
`blend_paper.py`'s paper-book equity. **Rule:** report returns from an entry-sized curve
(`mtm_sizing.simulate(..., "realised")`). Daily-sum figures are for relative comparisons inside
one file only.

All three made results look better. That fits the meta-lesson above: errors that flatter a
result survive longest, because nobody investigates good news.

---

## 15. A funding window that counts the same settlement several times — `mn_paper.py`

*Found 2026-09-24 by another session, verified and re-sized here. **Still open at the time of
writing**, in a LIVE pre-registered paper book.*

`mn_paper.cycle()` accrues funding with:

```python
since = st.get("last_fund_ms") or ...
fnd = {s: funding_since(s, since) for s in w}
...
st["last_fund_ms"] = int(bar.timestamp() * 1000)
```

and `funding_since` calls `/fapi/v1/fundingRate?symbol=...&startTime=since_ms&limit=100`.

**Two faults compound:**

1. **Binance's `startTime` is INCLUSIVE.** Verified against the live endpoint: a query whose
   `startTime` equals a settlement's own timestamp returns that settlement. So the boundary
   settlement is counted in two consecutive windows.
2. **There is no `endTime`.** The window therefore runs from the last bar to **now**, while
   `last_fund_ms` only advances to the **bar**. Everything between the bar and now is counted
   this cycle and again next cycle.

**Measured on the live state (2026-09-24):** the book summed **8 settlements for one daily mark**,
spanning 2026-09-23 00:00 to 2026-09-24 04:00. A day has **three**. So funding is roughly
**doubled**, not over by a third as first reported.

It matters because funding is about a third of that book's edge (+0.252%/wk of its +1.130%/wk in
`market_neutral.py`), and doc 14's recommended mix leans on the book.

**The fix:** `startTime = last_fund_ms + 1`, and an explicit `endTime` at the bar being marked, so
the window is exactly the day being booked.

**Why it should be fixed even though the book is pre-registered:** house rule 9 makes kills
permanent *"unless the measurement itself was broken."* A double-counted settlement is a broken
measurement, not a parameter choice. And the book had **one mark** when this was found, so fixing
it costs essentially nothing while leaving it means months of inflated record.

**Rule:** any accrual window over an external event feed must be **half-open and explicitly
bounded at both ends** — `(last, this_bar]` — and the cursor must advance to the same edge the
window ended at. Never leave the end open and the cursor behind it.


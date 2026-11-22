# CLAUDE.md — read this first, every session

*Last updated 2026-11-21. Dated history in §10.*

This file is the orientation for a new session. It is deliberately short. It tells you the
goal, the rules that keep the numbers honest, where everything is, and the traps that have
already produced wrong answers in this project more than once.

**WHAT IS RUNNING, ON WHICH CODE, WITH WHAT RESULT AND UNDER WHICH GATE: [`docs/STATUS.md`](docs/STATUS.md)** (verified
2026-10-24; re-check in 30 seconds with `bash deploy/verify_status.sh`). It is the single source of truth for current
state and it supersedes the dated pointers below and in docs 00 and 09. **If you change what runs, update it.**

**A LOCAL session on the PC (MT5 open)? There is a task list waiting: [`docs/LOCAL_MT5_TASKS.md`](docs/LOCAL_MT5_TASKS.md).**

**2026-10-09 (night): DOGE scalping, analysed and forward-tested LIVE with TradingView - dead at retail fees; see §10 and doc 02's last entry. The final machine runs on paper on the VM (combo-bot-final).** **2026-10-09: a data-gap bug was fixed and everything re-run - doc 02's last entry has the corrected numbers.** **Coming back after 2026-10-08? [`docs/09-pick-up-here.md`](docs/09-pick-up-here.md) was rewritten that evening: what runs on the VM and the PC, the machine names (v2 / v3 / MIX B / E), the one live change (the MN short-leg exit in `combo_bot.py`), and what is next. [`docs/21-graveyard-audit.md`](docs/21-graveyard-audit.md) rates every kill.**

**2026-10-10: [`docs/22-decision-rule.md`](docs/22-decision-rule.md) fixes when real money may go in, the code freeze to 2027-04-09 and the research stop date (2026-12-31) - read it before proposing any new book.**

**Read this file, then [`docs/STATUS.md`](docs/STATUS.md) for live state (and [`docs/09-pick-up-here.md`](docs/09-pick-up-here.md)
for the machine names and the 2026-10-08 narrative), then [`docs/02-what-failed.md`](docs/02-what-failed.md) before proposing any strategy.**

**[§10, the session log](#10-session-log), is what changed most recently and why** - read it
before trusting a number you find elsewhere in the repo, because three engine bugs on
2026-09-23 changed most of them.

---

## 1. The goal, in the user's words

> "MAXIMUM RETURN OR PROFIT PREFERABLY WITH LOW CAPITAL — IF ANYTHING DOESNT TAKE US
> TOWARDS THAT GOAL DROP IT"

The user is in Pakistan, trades crypto perps on **Bitget** (percentage fees, so small
capital works) and forex/gold on **Exness/MT5** (lot minimums make small capital hard).
Working capital ~**$221**. No co-location, no institutional data, free APIs only.

That mandate is a licence to drop things, and it has been used: most of this repo is a
graveyard, and that is the point.

## 2. The rules that make the numbers mean anything

`strategy_analysis/validation_protocol.md` is the authority. The short version — **breaking
any one of these has produced a wrong answer here before:**

1. **Charge 12bp round-trip** and a pessimistic fill. Never assume the good side of a bar.
2. **Hold out the last 40% and do not tune on it.** Split: `ts[int(len(ts) * 0.6)]`.
3. **Compound by CLOSE DATE, never by entry order.** (Mistake #6. Reading returns in entry
   order showed 85% drawdowns where the same book measures 57%.)
4. **Average over 5 random orderings of simultaneous signals.** Slot-order noise alone is
   ±3–5%/month — bigger than most "edges" found here.
5. **Divide CAGR by `blend.HINDSIGHT` (3.0)** on anything using the 12-coin book, because
   those coins were chosen with hindsight. A point-in-time universe needs no haircut — say
   so explicitly when you skip it, because the asymmetry flatters the un-haircut side.
6. **Point-in-time universes must include dead coins.** 339 of 864 USDT perps are delisted.
   `backtest/perp_fetch.py` has them; `wide_book.eligibility(n)` gives PIT top-N.
7. **Every number in a doc names the file that produced it.** No exceptions.
8. **Record the prediction before the test.** If a result surprised you, the doc says so.
9. **Kills are permanent** unless the *measurement* was broken.
10. **Charge funding** on anything held across settlements: `funding_cost.charged(...)`.
    Funding costs this book 21% of its lifetime long profit (mistake #13).
11. **Use real entry times**: `causal_t0.real_t0(rows)` before any `asof(t0)`, gate or slot
    order. 4h/12h rows carry their bar LABEL, which is 3h/11h after the entry (mistake #12).
12. **Quote returns from an ENTRY-SIZED curve** (`mtm_sizing.simulate(..., "realised")`).
    `bull_boost.evaluate`'s daily sum and `small_capital.simulate`'s sequential compounding
    both scale trades by equity they were never sized on, and they report ~2× what the bot
    can earn (mistake #14). They are fine for comparisons *inside* one file.

### The two findings that survived everything (2026-09-23 / 24)

**The tight exit.** Every other candidate this project has produced was killed, or held on one
half, or turned out to be a bug. The tight exit beats main on **both halves, on all four bar
phases, with t between +4.28 and +14.22 and 79 wins out of 80 ordering-by-phase combinations**
(`backtest/bar_phase.tight_across_phases`), and three independent simulators agree on its size
(+2.8%/mo tune, +2.0%/mo holdout). When something in this repo looks good, this is the standard
it has to meet.

**The second one (2026-09-24): pyramid to 7 units, not 5** (`backtest/pyramid_params.py`). +1.30
tune / +1.07 holdout %/mo over tight, t +33 / +19, 10/10 orderings, both halves on all four bar
phases. It also passes a matched-risk control: reaching the same return by raising risk costs 8
more points of drawdown. The mechanism *was stated here* as "units 6–7 are added at +10R/+12R, above the breakeven stop,
so they carry upside with almost no downside". **That is wrong** (`backtest/why_drawdown.py`,
2026-09-24). Units 6 and 7 **lose money on 49% / 47% of the positions that reach them**, worst
−11.8R / −12.5R each. The reason is the wide trail: 20×ATR sits ~10R below the best price, so a
unit bought at +12R can exit near +2R. They pay on average, +7.4R / +8.1R per unit, because the
winners are enormous, not because the losers are small. Their losses are part of why the
account still halves (doc 13 §10). **It stacks with the time stop**
(`backtest/units_on_tstop.py`): +1.51 ± 0.06 / +1.54 ± 0.08 over tight + time stop, 10/10.
The "triple" (tight + time stop + 7 units) is the best book measured: +8.89% tune / +10.76%
holdout %/mo against main's +4.88 / +4.88, at 48% / 51% drawdown - **but those two figures ignore
the bot's leverage cap; the numbers to quote are +8.72% / +10.43%, below.** **Paper book #7, not
deployed.** The same control rejected 16 slots (`slots_sweep.py`), which is what makes the pass
believable.

**The units change is worth ~+1.19%/mo LIVE, not +1.54%.** +1.54 is its gain over tight + time
stop with no leverage cap; the bot's guard takes 0.35 of it back. An earlier bound of "+1.44%" was
mine and was too generous - it counted units attempted while already over 10×, which is not what a
guard refuses, because a guard also stops the book reaching 10×.

**Quote the triple WITH the 10× margin guard** (`backtest/triple_capped.py`). The triple
reaches 12.2× gross leverage in the backtest (`regime_and_liq.py`), and `blend_paper.py` refuses
any entry or add past 10×. With that guard modelled: **+8.72% tune / +10.43% holdout**, which
costs −0.25 ± 0.04 / −0.35 ± 0.02 (2.2% of adds blocked). 5-unit books are unaffected. With
the guard off, the file reproduces `units_on_tstop.py` within 0.1.

### The holdout is mined out — the most important caveat in the repo

On 2026-09-22, six independent knobs (tight exit, short boost, slow-sleeve trail, looser
band, time stop, runner sizing) all read "helps holdout, costs tune." Either 2024–2026
genuinely rewards slower protective capture, or dozens of variants scored against one
holdout in one day have exhausted it. **Both readings say: adopt nothing further on this
split.** New ideas must be judged by the forward paper books, not by another backtest sweep.

**Update, 2026-09-23 evening** (`backtest/honest_rescore.py`): once measured causally and
with funding, two of the six changed status. The **short boost** was mostly look-ahead and is
worth ~+0.5%/mo. The **tight exit** now helps **both** halves (+2.2 tune / +2.8 holdout, 20
paired orderings), so it no longer carries the mined-holdout signature. It is the strongest
candidate on paper. The rule above still stands for everything else.

## 3. Traps that have already cost real time

| Trap | What happens | Guard |
|---|---|---|
| **`~` on an object-dtype boolean column** | Yields truthy −1/−2 instead of negation. Bit us **twice**: "share of hours in bull: −145%", and a glitch filter that silently kept all 61 glitches and flipped a mean from −55% to +10% | `.astype(bool)` before `~`, always |
| **Intrabar look-ahead** | Arming on a bar's high and filling at that bar's low. A whole "pullback adds" result was retracted; holdout went +15.4% → +4.2% once fixed. **A plateau and an interior optimum did NOT catch it — only an explicit causality check did** | Fill no earlier than `i > armed_bar` |
| **Selecting on the future** | `market_neutral.py` required a finite price at the *end* of the hold, silently excluding coins delisted mid-hold — precisely what the short leg exists for | Selection filters may read only `i` and earlier |
| **Compounding in entry order** | See rule 3 | Realize only trades closed by `t` |
| **Ruin tests set too deep** | A 98%-drawdown config was picked as "best" because the ruin flag only fired at 99% | Ruin = 90% drawdown |
| **Azure Run command JSON-decodes scripts** | A backslash-n inside a pasted heredoc becomes a REAL NEWLINE and breaks Python mid-string | **Patch scripts contain zero backslashes.** Use `chr(10)`. See `deploy/patch_*.sh` |
| **Bash heredocs mangling escapes in Python literals** | Same class of bug, locally | Use the Edit/Write tool for code containing escapes |
| **A data-gap rule that cannot tell an archive hole from a halt** | Every loader cut a coin at its first gap over 48h; two archive holes (2022-02-26..28, 2022-04-01..02, ~48 coins each) cut XRP, SOL and 49 others at 2022-02-25 - 16.4% of PIT top-40 coin-months missing from every daily / capitulation result until 2026-10-09 | `capitulation_wide.halt_cut`: only a gap of more than 7 days is a halt. List a universe's gaps (length, price jump, how many coins share it) before choosing a rule |
| **A weekly book measured on ONE weekday** | Every market-neutral figure used one rebalance day. On one of the seven the 2025-09-12 squeeze wipes the book out (-99%); funding carry and the BTC/alts dispersion trade also changed verdict with the anchor (2026-10-08, `mn_combos.py`, `bear_alpha_pit.py`) | Run any weekly book on all 7 weekdays (`mn_combos.mn_run(start=0..6)`) before quoting it |
| **Weighting a series that is BOOKED AT CLOSE by a label read the same day** | The trend book (`dd_fixes.sim`) books each unit when it closes; weighting its daily series by the regime label of that day is sizing after the outcome. Regime weights read +45% over the line; sized at entry they fail (2026-10-08, `regime_weights.py`) | Apply a size rule at ENTRY (`size_fn`/`gate_fn`), or lag the label by the holding time |
| **Haircutting a LOSS** | The 3× hindsight haircut divides an *annualised* rate by 3, which shrinks losses as eagerly as gains: a real −30% month reads −3.3%, and a year that ended at $92 reads $172. Found while answering "what happens at worst" — the first table showed a worst-ever month of −3.5% | Quote **downside raw, upside haircut**, and label which is which |
| **A non-stable sort on an append-only log** | `sort_values` defaults to quicksort. It reordered simultaneous closes and misaligned a log's own `equity` column against its rows, reading as a $4,534 self-check failure on a log that was correct | `kind="stable"` whenever row order carries meaning |
| **Run command wraps long lines** | Near 50 chars, and a wrapped line's tail RUNS as a command. A wrapped COMMENT loses its `#` and executes. This destroyed a 22KB base64 one-liner | Every line in `deploy/*.sh` under 44 chars; payloads in heredocs, which `base64 -d` decodes however they are broken up |
| **The VM's Python is 3.10, this PC's 3.12** | An f-string nested inside another with the same quote type (legal from 3.12) failed the VM's test run with `SyntaxError: f-string: unmatched '['` (rsi80_paper.py, 2026-11-08) - caught before install only because the tests ran on the VM | Compile every file that will run on the VM with the VM's interpreter before pushing: `ssh forexbot-vm 'cat > /tmp/x.py && /opt/forexbot/.venv/bin/python -m py_compile /tmp/x.py' < file.py` |
| **`VAR=cmd arg` is not an assignment** | `U=sudo -u $OWNER` makes the shell treat `U=sudo` as a prefix and run a command called `-u`. Aborted a live patch at line 34 | No spaces in an assignment value |
| **Testing only the part you changed** | Both of the two bugs above survived a test that exercised only the payload block, because both were outside it | Run the WHOLE script against a fake target with stubbed `systemctl`/`sudo`/`sleep` |
| **Comparing medians across orderings** | Per-ordering noise here is 0.25-0.48 %/mo, so two medians drawn from different seed outcomes differ by several tenths for nothing. It produced TWO confident claims in one hour that both died under a paired test: a blend "beating the average phase with 4-6 points less drawdown" (paired: +0.04%/mo, t=0.19) and "the venue minimum costs $221 0.29%/mo" (paired: -0.02%/mo, t=-0.37) | Pair on the SAME ordering, take the difference, report mean +- se and a win count - as `graveyard_rescore.py` already did |
| **`os.kill(pid, 0)` as a liveness check** | On Windows this is not a no-op - any signal other than CTRL_C/CTRL_BREAK calls `TerminateProcess`, so the “check” **kills the process it is checking**. Caught in a draft of `combo_paper.py` before it ran | Read-only check: PowerShell `Get-Process -Id`, as `mn_paper.single_instance` does |
| **An accrual window left open at one end** | `mn_paper` sums funding from `last_fund_ms` with no `endTime`, so the window runs to NOW while the cursor advances only to the BAR - and Binance's `startTime` is inclusive as well. Measured: **8 settlements summed for a one-day mark**, where a day has 3. Funding roughly doubled (mistake #15, still open) | Half-open and bounded at BOTH ends, `(last, this_bar]`, with the cursor advancing to the same edge |
| **Mixed datetime64 units in the row set** | t0 comes back as `[us]` and t1 as `[ms]`, so `date_range` inherits `[us]` from its bounds while `Timestamp.value` returns ns. `searchsorted` then puts every span past the end of the grid and a whole leverage series came back silently ZERO (2026-09-24, cost a run) | Force BOTH sides with `.as_unit("ns")`, and assert the result is non-zero rather than trusting it |
| **A cancel set defined by bookkeeping, not by the exchange** | `wick_live`'s cap cancelled orders that were `open and not counted`. A PARTLY filled bid is counted but still open, so it survived the cap - and in a sweep deep enough to touch every level, ALL 40 bids are partly filled, so the cap cancelled **0 of 40** (mistake #16, fixed 2026-09-25) | The cancel set is **whatever is still live on the exchange**. Test a safety limit IN the disaster, not in the tidy case |
| **A test that cannot exhibit the bug** | With one position open at a time the two compounding conventions are arithmetically IDENTICAL, so a non-overlapping test showed $0.00 difference and passed while proving nothing. The bug only bites when positions OVERLAP | Construct the case so the bug MUST appear if it is present |
| **Yahoo's FOREX daily bars (`EURUSD=X`, `JPY=X`, ...)** | Not internally consistent: the open sits ~27bp from the previous close (a continuous market: Exness 1.1bp), and the close is not the end of the high/low window - after a close in the bottom fifth of the range the next close rose 92-95% of the time (Exness 49-50%). It produced 79 fake 'passes' at t up to +25 (2026-10-11, `fx_capit.py`). Bars are also dated one day off Exness's (corr 0.948 shifted, 0.05 not). `fx_anomalies.py` T8 (month-end USD) used these closes and measured the day BEFORE the month-end; re-checked on Exness (`fx_t8_exness.py`): the kill stands | Forex daily bars from Exness (`fx_capit.exness_csv`: MT5 1h -> 17:00 New York days). Yahoo forex only for monthly signals (`fx_tsmom.py`), never for anything that reads the close inside a day's range |
| **HistData.com minute bars' clock** | Documented as fixed EST; the stamps are New York time WITH daylight saving. Converted with a fixed +5 h, every summer release sat an hour early, its jump fell into the "hour after" window, and a fake post-release drift read +10.5bp at t +21 with 9 passes (2026-10-12, `fx_surprises_1m.py`). Also: `to_datetime(format=...)` returns datetime64[us] there, so `int64 // 10**6` dated every bar in January 1970 | `histdata_1m.parse` localises to America/New_York. Before any minute-level event study, check that the biggest 1-minute move on payroll days sits in the release minute, winter AND summer |
| **A date-matched control for a pattern that clusters in time** | `candle_scan.py`'s first run compared every candle-pattern trade with the mean of ALL coins entered the same DAY. Patterns cluster in the same 4h slots on market-wide moves, so that control missed the market's own reaction at that moment: 27 cells showed a 'replicated excess' (+0.3..+0.6% a trade, t up to +9, tens of thousands of trades) that fell to -0.07..+0.06% once the baseline also matched the entry SLOT (2026-11-02, `candle_scan_check.py`) | Match the control on every dimension the signal clusters on: entry day AND entry slot (hour of day). Treat a surprise count of 'information' cells as a possible control leak until a stricter control agrees |
| **Binance WEBSOCKETS on this PC** | They connect and then deliver nothing - DOGE's own trade stream gave 0 messages in 12 s (2026-10-09) - while Binance REST works; a liquidation recorder listened to silence for 17 minutes | Probe any stream with a known-busy channel first; on this PC use REST (OKX needs a browser User-Agent, else 403). **Bitget's public websocket DOES work here** (2026-10-28: `books` + `trade` on `wss://ws.bitget.com/v2/ws/public`, a snapshot then ~9 updates/s with `seq` / `pseq`) |
| **Trusting `ls` / `date` in Git Bash for "is it stale?"** | They print the Windows local clock (PKT here) but label it PST, so a log written 20 minutes ago read as 13 hours dead and sent a session hunting a wedge that did not exist (2026-09-26) | Get the time from the PROCESS: `datetime.now(timezone.utc)` in Python, and compare it to the log's own UTC prefix |
| **Timestamp unit mismatch** | `.asof()` raises "Cannot losslessly convert units" (ms index vs ns clock) | `blend_paper._ns()` |
| **Bar label read as entry time** | `asof(t0)` on a 4h/12h row reads a bar that closed hours after the entry. The short boost's "+0.481R" was 118 look-ahead trades; causal, it is +0.305R and worth ~+0.5%/mo | `causal_t0.real_t0(rows)` |
| **Fees charged, funding not** | Every figure for the deployed book was fees-only. Funding takes the tune half +16.5% → +12.2%/mo | `funding_cost.charged(...)` |
| **Scaling a trade by equity it was never sized on** | Daily-sum / sequential compounding credit open runners with profit other trades banked: ~2× the achievable return. `blend_paper.py`'s paper equity does it too | entry-sized curve, `mtm_sizing.simulate(..., "realised")` |
| **A slot freed at the exit bar's LABEL** | `walk()` stamps an exit with the label of the bar the stop is hit in - for 1h, its OPEN - and `taken()` frees the slot for a trade entering at that same open: the allocator knows a position will stop out later that hour. Flattered the tune half 1.3-1.6 %/mo, 0/10 orderings (mistake #17, 2026-10-06). And the live bots are a different book again: one position per key, retry on a declined signal, a one-bar pause - together 1-2 %/mo under every published figure, with deeper falls | Free a slot when the exit bar CLOSES. Reconcile the backtest's position model with the bot's, trade by trade (`engine_vs_live.py`) |
| **Booking P&L at the bar close hides what happened inside the bar** | Doc 15's crash bids made money in the 2025-10-10 21:00 hour *at its close*. Five-minute bars show every bid filled and kept falling, and together with the trend book the account had **10% left** inside that hour (2026-09-25, `joint_worst_hour.py`) | For any book that buys INTO a move, measure the worst price after the fill inside the holding bar, summed across the book and added to what else is open |
| **A day-vote mean read as money** | `candle_scan.py` / `rsi_ratio.py` give every entry day one vote (right for t: a crash day with 100 signals is one bet). On a market-wide sell-off those 100 oversold longs lose together, and one vote per day makes them count like one quiet day's single winner: the best RSI bracket read **+0.37R / +0.26R** and was **-0.15R / -0.12R a trade** (a capped account lost 16-96% a year) (2026-11-02, `rsi_ratio_check.py`). `candle_scan` / `candle_manage` print day-vote means too; their conclusions (all null) stand, but any positive cell there would need the per-trade check | Print the per-trade mean beside every day-vote mean (`rsi_ratio.py` now does) and run the capped account (`rsi_ratio_check.account`) before calling a bracket money |
| **Bucketing trades by a count that includes signals AFTER the entry** | Splitting the oversold longs by 'how many coins signalled that calendar day' made quiet days win +0.14..+0.87R a trade and flush days lose -0.4R, positive on both halves - a clean rescue. The day's count includes signals at hours the bot has not seen. Counted over the 24 hours up to and including the entry hour, all 40 bucket-halves (four brackets x five buckets x two halves) are negative (2026-11-02, `rsi_ratio_check.py`) | Any filter built from a count or a mean must be computable at the entry bar's close: window to (t - w, t], never to the end of the day |
| **A selection judged against the wrong baseline, by a per-day-and-side mean** | `combo_direction.py`'s diagnostics printed a single feature (`-a_rng_pos24`, top 10%) at +0.147R, t +4.5, both halves. The feature was not centred (position in the 24h range is in [0, 1]), so the selection was 100% shorts; the baseline was ALL candidates (half longs) in a period when shorts out-earned longs; and the (UTC day + side) mean is a day-vote mean. Per call, against the same side: -0.157R vs -0.096R, shift-null p 0.983 - worse than random (2026-11-15, `combo_rangerev.py`). The same gate also HID the one per-call lead (the per-call excess was larger than the per-bet excess in 32 of 36 cells) | Print the per-call mean beside every selected-vs-all difference; compare a selection with the SAME-SIDE (and same quarter / hour / volatility) calls, never with the pooled set; centre a feature before aligning it by the side; run the power check on the metric that will be read (the bet-level check said the pipeline was blind, the per-call one did not) |
| **Pooled metrics of leave-one-GROUP-out predictions** | Holding a window (or a year, a coin) out moves the training base rate opposite to the held-out group's, so pooled probabilities anti-correlate with the outcome: a model with NO features scored a pooled AUC of 0.389, and the real one 0.454 with its confident calls 38-42% right - worse than a coin (2026-11-04, `his_cme_scan.py`). It reads like 'anti-learning' and is a bias | Centre each fold on its own training base rate and report the AUC WITHIN each group (mean +- se). If a held-out result is below chance, run the featureless base-rate predictor through the same pipeline before interpreting it |
| **A mutation harness that decides 'survived' by a phrase in the output** | The planted-bug harness called a mutant 'survived' only if the test output contained 'tests passed'; `tests/test_dashboard_push.py` prints 'N passed', so EVERY mutant read as 'caught' and survivors could never appear: the display fix's '15 of 15 planted bugs caught' (2026-11-06, commit `80e0ff1`'s message and this file) was really 14 of 15 - the bear-sleeve rows' `daily` flag was untested. Found because a deliberate do-nothing mutation did not show up as a survivor | Judge a mutant by the test run's EXIT CODE, and always include a no-op CONTROL mutation that MUST survive; if it is reported 'caught' the harness is blind. (The other studies' test files print 'N tests passed', so their results stand.) |
| **Pricing a resting stop order at a news release from 1-minute bars - either way** | A +-5bp pre-release straddle on gold at NFP read **+20bp a trade, t +5, both halves** at LEVEL fills (`gold_news_breakout.py`, 2026-11-08); the same session called it a fill artifact because the trigger minute runs a median 34bp past the level and the trigger bar's CLOSE fill is -2.8bp. **The audit the same day on Exness ticks (`gold_news_ticks.py`) showed that was wrong too**: a stop order fills a median ~9-11bp past a 5bp level on the 2026 NFPs (CPI / FOMC 0-6bp); most of the minute's run is continuation the order earns, and the tick result tracks the LEVEL fill, not the CLOSE. Re-scored with 10bp of entry slippage the straddle is +11bp (t 2.45, holdout t 1.1): a weak lead, not an artifact | A bar's run past the level is NOT slippage, and the bar's CLOSE is a manual entry, not a stop fill. Measure the stop fill on TICKS (MT5 serves Exness ticks from 2026-01) and charge that; quote LEVEL minus the measured slip |
| **A null on a RARE setup read as 'dead'** | The repo's template (closed 1h candles, fixed bracket, 12bp + funding, random-entry control, both halves, Holm, day-clustered t) is UNBIASED (a planted trader is measured at its true size within 0.008R, 0% false alarms) and on all ~60k sweeps it catches a +0.07R edge every time - but on the 4h-zoned sweeps (~476 holdout trades a side) it catches +0.07R only 12% of the time, on the daily zones (~58 a side) it can pass nothing at all, and the Analyst desk's registered 30-bet test passes a desk with a true +0.43R a bet only 35% of the time (`backtest/blindness_check.py`, 2026-11-08) | Before reading a null, print the minimum detectable edge for THAT sample (plant known skill at the real event times, as `blindness_check.py` does) and call a null below it 'cannot tell', never 'dead' |
| **A universe ranked on a LATER period's volume** | The November top-40 (ranked on October's volume) used as October's alt index read alts -3.9% from 10-09; the point-in-time list (each day's month, ranked on the prior month) reads -28.7%. October's volume leaders are October's pumped coins, so the index knew the hype before it happened, and the account's betas to it moved with it (2026-11-21, `crash_lessons.py` first run) | Pick each day's universe from the month that holds the day BEFORE, ranked on the prior month's volume (`wide_book.eligibility`, `crash_lessons.pit_alts`) |
| **Binance's TradFi perps are not contractType PERPETUAL** | A ledger valued from `daily_live_vs_backtest.klines_all` silently dropped QQQUSDT - the NASDAQ dip-buy's ~1x position - and read the account as net short with nothing beside it (2026-11-21). Separately, a date-alignment check on SIGNED daily returns read ~0 at every lag because the books bet both ways, and wrongly said the dates were shifted | List every open position that has no price before reading an exposure (`crash_lessons.unmapped`); check date alignment on the SIZE of moves (`abs`), not their sign |
## 4. Where things are

```
backtest/          every experiment. blend.py holds the deployed constants.
  blend.py           RISK=0.30, HINDSIGHT=3.0, REGIME_MULT=0.25, FEE_BP=12, BOOK (12 coins)
  engine_variants.py long_walk / rows_for — the engine most tests build on
  expectations.py    "if I put in $X for a month, what am I looking at" (doc 00)
  small_capital.py   venue minimum simulated; settled that it is NOT the binding constraint
  market_neutral.py  the second book (doc 10)
  combine.py         does book 2 combine with book 1 (doc 10)
  perp_fetch.py      downloads all 864 perps incl. the 339 dead ones
  wide_book.py       eligibility(n) = PIT top-N universe
  graveyard_rescore.py  rows(tight=, time_stop=, max_units=...) - the CORRECTED engine
                     (funding, real t0) most 2026-09-23/24 tests build on; score() pairs them
  one_year.py / month_dist.py / book_stats.py   what $221 does in a month / a year, per book
  kelly_corrected.py risk-per-unit sweep with leverage and ruin (why 0.30% stays)
backtest/machine_factorial.py / filter_pairs.py / moderate_retests.py / mn_blend_rsi.py / vwap_daily.py  2026-10-09:
                     every book combination (728), every filter pair, the MODERATE kills re-tested, the MN momentum+RSI candidate
docs/21-graveyard-audit.md  EVERY kill, its backing rated, the thin ones re-tested (2026-10-08): engine_rescore2,
                     sleeve_risk_control, bear_alpha_pit, mn_width7, wick_chop_size, sweep_reclaim, meme_days
backtest/daily_combos.py / capit_combos.py / capit_stack.py / mn_combos.py / machine_combos.py  the combination sweep
                     (doc 02, 2026-10-08): capitulation improved (coin -10% + limit -2%); the MN rebalance-day wipe-out and
                     its +50% short-leg exit; the machine measured with MN on every day. Phase-2 re-tests: daily_families,
                     carry_revisit, capit_volume, pairs_revisit, capit_1h, sleeve_combos, trend_combos, wick_capit
backtest/v2_addons.py  today's books ADDED to v2 (marked to market, vs the bet-smaller line): v2 + capitulation + daily,
                     all x0.75 = v2's typical year with the worst month -21% instead of -29% (doc 02, 2026-10-08)
backtest/pair_lab.py / mn_capped.py / pair_full.py  "machine v3": the pair diagnosed and fixed - + capped MN x0.5 +
                     bear sleeve x1 = +133%/yr on paper, every year positive, all point-in-time (doc 02, 2026-10-08)
pair_live.py       THE PAIR, LIVE: read-only Bitget signals (daily Bollinger trend + 4h capitulation breadth, crypto
                     perps only - isRwa stock tokens and stables excluded) and a 10,000 PKR paper book
                     (logs/pair_paper_state.json, logs/pair_paper_trades.csv). --scan / --paper (hourly) / --loop /
                     --status. tests/test_pair_live.py: fake exchange, 4 tests, a breadth-gate mutation caught.
                     ON THE VM since 2026-10-08 (pair-paper.service), with the capit2 SHADOW book: the improved
                     capitulation rule (coin -10% in 24h + limit 2% under), pre-registered H1-H3, own 5,000 PKR
backtest/pair_books.py / daily_phase.py / tv_indicators.py  THE PAIR: daily Bollinger trend book + capitulation book
                     on the PIT top-40, 1x: +51%/yr median, falls 25-34% - the best no-hindsight candidate (doc 02)
backtest/capitulation_exits.py / capitulation_tp5.py / machine_capit.py  the capitulation book with a +5% exit, its
                     accounts, and as a machine sleeve (+14% typical year) (doc 02, 2026-10-08)
backtest/doge_focus.py  one-coin (DOGE) walk-forward over 134 strategies: no route to +10%/month (doc 02)
backtest/capitulation_freq.py / capitulation_breadth.py  more signals = less edge; waiting for >=5 coins to
                     capitulate (breadth) is the best version: ~55/yr, +1.1-1.7%/trade, all 4 phases (post-hoc)
backtest/capitulation_wide.py  the capitulation buy, frozen, on the PIT top-40: carries in direction, not by-day t
backtest/rsi_confluence.py  extreme RSI + confirmations, ~2,000 configs: CANDIDATE 4h capitulation buy (RSI<20 +
                     volume spike), all 4 bar phases, ~+1%/trade but ~13 signals/yr (doc 02, 2026-10-08)
backtest/rsi_factors.py  RSI both ways with factor exits instead of a stop: no factor turns it positive (doc 02)
backtest/rsi_only.py  the no-stop retail RSI trade, 15m/1h/4h x 5 coins, by year: 80-90% win rate always, money only
                     in 2020/2021/2023 (doc 02, 2026-10-08)
backtest/scalp_15m.py  15m long+short on 5 coins, scalp_1m's machinery: 0 EDGE, 1 WEAK at taker (doc 02)
backtest/day_long.py  one-day longs on 10k PKR picked by 1,350 indicator filters x 5 coins: dead as asked (doc 02)
backtest/micro_honest.py  micro_bot's own rules re-measured on real paths: $10 at 4% ends >= 5x 29%, wiped out
                     56%; 2% halves the ruin at the same odds (doc 02, 2026-10-06)
backtest/lottery_v2.py  go-for-broke odds on 4,000 PKR, corrected (causal slots, 7 units, add guard): honest
                     12-month >=5x 23-29% at 1-2%/unit, ~half stuck under $5, decided by the start year (doc 02)
backtest/maker_exec.py  limit-order execution (trade-through fills) for today's 1m edges: ridge BTC->DOGE 60-min
                     is +4bp/trade at Bitget maker, t +1.0 - a forward-test CANDIDATE, nothing more (doc 02)
backtest/one_shot.py  one trade at 10-40x to double/triple/5x the stake, random vs indicator+volume setups: the
                     coin flip's odds minus fees; setups move them ~1 point (doc 02, 2026-10-06)
backtest/btc_doge.py  trade DOGE on a model of BTC+DOGE (1m features, ridge + trees): real but tiny before fees,
                     loses at taker fees, wiped out at 5x+ by the 2025-10-10 hour (doc 02, 2026-10-06)
backtest/scalp_1m.py  1-minute BTC/DOGE scalping at 30-40x, every retail rule + the leverage (Kelly) test: dead
                     even at zero fees past ~10x (doc 02, 2026-10-06)
odds_now.py        "if I go long/short this coin NOW, how often does take-profit hit first?" - a read-only MANUAL
                     trade checker: live Bitget cell (RSI/momentum/range/BTC gate) vs the same cell in history,
                     against the same-regime baseline. Answer is almost always NO EDGE (doc 02, 2026-10-06)
desk.py            2026-10-27: THE DESK - a manual trade plan (entry / stop / target) priced and logged as a PAPER call BEFORE its outcome, scored on
                     real 1-minute bars; `python desk.py plan|score|stats|list`. Size, fees in R, break-even win rate, liquidation distance, and the
                     RANDOM-ENTRY BASELINE for the same stop % / target % / hours. Verdict only after 30 filled calls (D1-D3 predicted none). Crypto and
                     Binance's TradFi perps (XAUUSDT, QQQUSDT ...); no keys, no orders. tests/test_desk.py 12 tests, 10 mutations caught
analyst.py         2026-10-27: THE ANALYST DESK - desk.py automated: hourly it draws support / resistance, a Fibonacci retracement and unfilled gaps on 7
                     markets (BTC ETH SOL XRP BNB gold QQQ), three fixed rules (SR bounce, FIB pullback, SMC sweep) log CALLS with stop / target / the random-entry
                     odds BEFORE the outcome, scored on 1-minute bars; a separate $300 PAPER book (0.5% risk a call, 3x cap). Dashboard tab "Analyst desk"
                     (`dashboard_push.analyst_view`). A1-A4 registered in its docstring (expected: no edge; A1/A3 amended 10-27: same-day, same-direction calls = one bet); review at 100 resolved calls or 2027-01-31.
                     deploy/analyst-paper.service + .timer (hourly :07). tests/test_analyst.py 13 tests (13 of 14 mutations caught, 1 equivalent)
backtest/analyst_replay.py / analyst_replay_1m.py   2026-10-27: the Analyst desk's three rules replayed over 4.7 years of 1h candles (10,580 calls) and the whole
                     account at 10x / 20x / 30x (`analyst.scenario`): wiped out at every leverage, the desk's own book -3.3% a week; the 1-minute re-score agrees (doc 02, last entry)
backtest/pit_years.py   2026-10-27: the main account's machine by calendar year (fixed $300) with the trend book on the point-in-time top-12 alts
                     instead of the hindsight list: total ~unchanged (+$8,645 vs +$8,385), 2024 down, 2025 up - mostly MYX (doc 02, last entry)
backtest/cot_metals.py / positioning_lean.py   2026-10-28: CFTC Disaggregated positions on platinum / palladium / gold / silver / copper vs the next 4 weeks: 0 of 15
                     registered cells pass (ETF and futures prices); the tool prints the crowded side, its history, the test verdict and the CME delivery picture
                     (logs/cme_snap/ - CME's free feed keeps 5 days, so that part is a RECORD from 2026-10-27). tests/test_cot_metals.py 6 (doc 02, last entry)
backtest/gold_roll.py   2026-10-28: GOLD roll test - Databento CME open interest by delivery month (pulled for $1.01, 2016-26 usable) x CFTC managed money: does the pending roll move the
                     calendar spread before first notice? 51 cycles, NO LEAD (IC +0.14, p 0.16, halves flip); the net-short half is untested (5 cycles). tests/test_gold_roll.py 8 (doc 02, last entry)
backtest/sweep_confluence.py   2026-10-30: the Analyst desk's liquidity sweep + 7 confluence factors (depth, volume, close location, breadth, trend, equal lows, funding) on the PIT top-40, 60,664 events:
                     the sweep beats a matched random entry by 5-25bp but the gross edge is ~0 since 2024; 0 of 14 factor cells confirmed; the one significant holdout cell is NEGATIVE (long sweeps in a
                     market-wide flush -0.59% a trade); no tradable stacked subset. tests/test_sweep_confluence.py 7 (17 of 17 mutations caught); doc 02 last entry
backtest/sweep_zone.py   2026-11-08: the desk's liquidity sweep + a fresh 4h supply / demand zone (base bar + 1.5 ATR impulse, first retest within 24h, 30-day life) + the daily 50-day trend, all three together, PIT top-40, 60,601 sweeps (2,323 zoned = 3.8%):
                     arms A every sweep / B zoned / C zoned + trend on their own trades (3R, 72h, 12bp + funding, matched random-hour control): 0 of 6 cells pass; the zone adds nothing (T24 spread long -0.03% tune / -0.38% holdout, t -2.1), B long holdout -0.26R, C short holdout +0.06R (t +0.5);
                     one zone definition, not 'impossible'. tests/test_sweep_zone.py 44 (43 of 43 planted bugs caught); doc 02 last entry
backtest/sweep_zone_daily.py   2026-11-08 (later): the same idea with DAILY zones (base day + 1.5 ATR impulse day, first retest + 72h) and a target at the NEXT opposite zone (>= 1.5R): 60,390 sweeps, 726 zoned (1.2%), 286 with a target (43 a year), 130 with the daily trend:
                     0 of 6 cells pass and the four zone cells are UNDERPOWERED (31-68 holdout trades, se 0.3-0.5R): 'cannot tell'; arm A (every sweep) loses again; the zone information spread is positive on all four halves, not significant. tests/test_sweep_zone_daily.py 32 (60 of 60 planted bugs caught); doc 02 last entry
backtest/nq_profile.py   2026-11-09: MARKET PROFILE / AUCTION MARKET THEORY on 16 years of NQ 1-minute bars with real volume (no new spend): the prior session's TPO profile (primary) and real-volume profile (plateau), value area by the CME method, nine cells (80% rule, back to POC, fade the value edge, acceptance outside value, value migration x2, initial-balance break x2, open drive), matched-day control (the same trade on every session of the same half), 1.27bp, tune / holdout 60 / 40:
                     0 of 9 pass in either construction, none a LEAD; the 80% rule's far-edge touch is 47.6% | 43.5% against 43.4% | 44.2% on random days; R7 open drive +15.6bp on the holdout only (t 1.7, 120 trades, tune +0.4bp). tests/test_nq_profile.py 39 (98 of 98 planted bugs caught over three rounds); doc 02 last entry
docs/27-order-flow-study-guide.md / backtest/pair_spread_survey.py   2026-10-30: the user's order-flow study (imbalance + wall persistence + executed pressure, 10 pairs, 1 s - 5 min): Modules 0-5 written (what book_hist.py already
                     measured on DOGE, what is open, the cost wall, the lessons), a public-ticker spread survey of 16 Bitget pairs (BTC/ETH/SOL 0.01-0.1bp; most alts one tick = 0.8-2.6bp; ADA 5bp, DOT 11bp)
backtest/order_flow_lab.py   2026-10-30: Module 2's teaching lab on ONE real day (DOGE, Bitget, 2026-06-01): a book snapshot (imbalance changes sign with depth), taker flow vs price (same-window rho +0.38..+0.49,
                     ~3-4bp per $100k, next-window |rho| <= 0.085) and WALL ANATOMY (2,288 walls: median life 15 s, 99.8% of what left was cancelled - but only 188 ever came within 3bp of the mid,
                     12 within 1bp). Descriptive, not a test. tests/test_order_flow_lab.py 8 (14 of 14 mutations caught). Doc 27 Module 2
backtest/window_lab.py   2026-10-30: Module 3's lab on the same DOGE day: move size by window (sqrt-time scaling; 71% of 1 s windows unchanged), feature persistence and IC decay (imb1 .27 -> .06 from 1 s to 5 min),
                     overlap inflation (naive t 34 vs honest 6.0 at 30 s), 1,000 shuffled-feature cells (46% naive vs 4% honest pass |t| > 2; best honest noise cell |t| 3.8). Found its own look-ahead bug
                     (flow feature included the predicted second: IC +.199 vs +.029). tests/test_window_lab.py 10 (15 of 15 non-equivalent mutations caught). Doc 27 Module 3
backtest/order_flow_registry.py / protocol_lab.py   2026-10-30: Module 4. The order-flow project's five hypotheses (H-imb 18 cells, H-flow 15, H-approach / H-combo / H-exec 2), criteria K1-K4,
                     cost model, power arithmetic and `judge()` AS CODE, pinned by REGISTRY_SHA256 (tests fail if a registered number changes; amend only via AMENDMENTS); protocol_lab: the winner's curse on the DOGE
                     teaching day (best of 60 rules: +2.9bp in-sample, +0.04bp out for pure noise; the real search by raw mean fell for it too, by t it did not), right-but-unprofitable (76% right, -3.2bp maker),
                     trades needed. tests/test_order_flow_registry.py 9 (19 of 19 mutations), tests/test_protocol_lab.py 9 (12 of 12). Doc 27 Module 4
backtest/bear_label_test.py   2026-10-30: why the bear sleeve was OFF in a 4% BTC drop (its label needs the 50-day average itself falling 2%), and whether a faster label would be better: 12 labels
                     (20/30/42/50-day average x slope none/<0/<-2%) through the sleeve's own engine, fixed and expanding cut-offs: NO candidate; the live label has the best Sharpe in 3 of 4 tables, the extra days it
                     skips are worth about nothing (doc 02, last entry). tests/test_bear_label_test.py 7 (11 of 11 mutations caught)
backtest/candle_scan.py / candle_scan_check.py   2026-11-02: the 17 textbook candlestick patterns (hammer, engulfing, stars, soldiers / crows, harami, doji, inside bar...) as stand-alone rules on the PIT top-40 perps at 1h / 4h / 1d,
                     both sides, 1- and 5-bar holds = 204 cells, entry at the next open, 12bp + funding, control = entry day x entry slot, tune / holdout: 0 pass, 0 keep an excess on both halves. The first run's day-only control leaked
                     the market's reaction at pattern-clustered moments (27 fake 'information' cells; the check script found it). doc 02, last entry. tests/test_candle_scan.py 16 (24 of 24 mutations caught)
backtest/candle_manage.py   2026-11-02: the same 17 patterns as ENTRIES with real trade management (trend: 2 ATR stop, breakeven at +3R, 20 ATR trail; scalp: 1 ATR stop, +2R target), 1R risk a trade, fees in R, versus the SAME management from random entries
                     at the same entry day x slot: 0 of 204 pass, 0 cells with excess t >= 2 on both halves. The management itself is a regime bet (random daily longs +0.74R tune / -0.20R holdout); the 41 shorts that are
                     positive on both halves have zero excess (doc 02, last entry). tests/test_candle_manage.py 11 (19 of 19 mutations caught)
backtest/market_fade.py   2026-11-02: the loose thread of the candle scans tested as a MARKET rule - short the PIT top-40 basket (and BTC) after a strong 4h up-move (equal-weight index z >= 1.5 / 2.0 / 2.5, holds 4h / 20h / 48h), shift-null p, three-fold
                     bar: NO PASS, the primary loses -1.22% / -0.60% a trade on the two halves (negative every year, worst trade -28%); strong up-moves CONTINUE; the mirror (long after strong down-moves) is tune-only. tests/test_market_fade.py 9 (17 of 17 mutations caught)
backtest/wait_leverage.py   2026-11-02: the user's 'high leverage on BTC, liquidation far away, wait until it is in profit' idea on 58,940 hourly bars: BTC touches the 100x liquidation level within a day in 80% of entries (50x: 50%, 20x: 12%);
                     the wait-for-+0.30% rule wins 56% (100x) / 82% (50x) / 94% (20x) of tries and still loses -34.5% / -10.4% / -2.9% of the margin a try. tests/test_wait_leverage.py 5 (8 of 8 mutations caught)
backtest/indicator_model.py / indicator_model_check.py   2026-11-02: ALL standard indicators at once (32 features, ranks) in a walk-forward ridge / gradient-boosting model on the PIT top-40 daily, 2022-26 out of sample: 0 of 6 pass; the IC is
                     +0.10..+0.18 but it is ONE feature used backwards (low ATR% beats high ATR%, every year) - not a closing-print artifact (entry delayed 1 h / 4 h / a day keeps it), not a significant net spread (t <= 1.4). tests/test_indicator_model.py 10 (18 of 18 mutations caught)
backtest/all_sources_model.py   2026-11-09: 'run countless combinations where anything links': ONE walk-forward model (ridge / gradient boosting) fed EVERY source on disk - price, funding, Binance positioning, Telegram news + tone, Bluesky, unlock schedules, size / age, a market block - PIT top-40, out of sample 2022-10..2026-09:
                     NO PASS (0 of 6, Holm 1.00); IC +0.10..+0.18 is mostly ONE factor (calm / old / deep coins beat volatile ones; the model without price scores the same); linking adds ~0 (paired never t 2); vol-neutral IC +0.04..+0.07 nets ~the cost; a planted clean IC 0.10 passes alone, so the test can see a link. tests 20 (39 of 39 planted bugs); doc 02 last entry
backtest/forward_ledger.py   2026-11-09: THE FORWARD LEDGER (the user: 'plan the farm' -> 'yes, build it'): three leads re-run on data after 2026-11-09 00:00 UTC with their study files' OWN code, pinned by hash
                     before the window opened - gold payrolls straddle (Exness ticks via MT5), NASDAQ inside-bar buy and NASDAQ before the Fed (HistData minutes, ForexFactory times); dead at 2 se under the claim,
                     confirmed only at t 2 after Holm; ~10.7 / 23 / 6.5 years to confirm at the claimed size. PC only: `python -m backtest.forward_ledger` (monthly, MT5 open) writes logs/leads/ledger.json;
                     `--check` = parity (889 trades / 128 statements / 8 of 8 releases reproduced). tests 10 (22 of 22 planted bugs). The dashboard's Leads tab (`dashboard_push.leads`) lists it beside every live record
backtest/options_expiry.py / etf_flows.py   2026-11-09: the two forced-flow sources never tested here. OPTIONS EXPIRY (Deribit 08:00 UTC; 82 monthly, 27 quarterly, every Friday): 0 of 24 cells pass; LEAD = the 4 hours
                     into a MONTHLY expiry dip (BTC -49 / -42bp vs ordinary Fridays, t -2.5 / -2.7; 67% of expiries down; every year; mostly 07-08 UTC, the futures' settlement average; placebo a week earlier ~0)
                     but a short nets +0.33 / +0.23% (t 1.9 / 1.8) - small; the 4 hours after are 1.5-1.6x wilder. ETF FLOWS (Farside 2024-01..2026-11): dead - flows follow the price (same day +0.43,
                     past 5 days +0.37), next-day IC +0.055 / -0.037, 0 of 4 cells. tests 9 + 7 (28 of 28 planted bugs); doc 02 last entry
backtest/liq_map.py / liq_map_fetch.py   2026-11-15: 'predict the exact liquidity-sweep prices and scalp with leverage': an ESTIMATED LIQUIDATION MAP from Binance's 5-minute open interest (347 PIT top-40 coins incl. dead, 2022-26; data in
                     strategy_analysis/data/liqmap/): NO PASS, 0 of 6; clusters fill exactly as often as random levels that far away (0.97-1.01x), no bounce after (excess |t| <= 1.9); post hoc the map is NOT blind (cluster hours trade
                     ~20% more volume, t +14 / +15) - it finds forced trading, not direction. tests 20 (30 of 30 planted bugs); doc 02 last entry
backtest/liq_map_1m.py   2026-11-15: the same fills re-scored on Binance 1-minute bars (21,269 coin-days): 0 of 8; scalp bracket -20bp a trade (t -12..-14); the price overshoots a cluster MORE than a random level
                     (median 0.58% vs 0.48%): clusters are where forced trading pushes through; deep (8%+) clusters bounce only as much as any 8% dip. tests 8 (15 of 16, 1 equivalent); doc 02 last entry
backtest/liq_map_past.py   2026-11-15: orders resting 0.25 / 0.5 / 1% PAST the clusters (the execution use): 0 of 18; fills only 1-3 points above random levels; 'deeper is better per order' holds for random levels too
                     (fewer trades, fewer fees); deep longs +43..+56bp at 15m = any 8% dip. The heatmap is closed. tests 10 (17 of 17); doc 02 last entry
backtest/liq_sweep.py   2026-11-15: the map + REAL open-interest fall as filters on sweep_confluence's 43,500 sweeps (the factor that study could not test): 0 of 6, stage 1 0 of 4; long sweeps
                     that cleared more leverage do WORSE (-4..-25bp spread); the map's 'liquidated' figure is mostly wick depth (rank +0.6), unrelated to the real OI fall. tests 10 (20 of 20); doc 02 last entry
backtest/works_map.py   2026-11-15: THE MAP OF WHAT WORKS - every surviving book (final machine's 9 + crowd, RSI-80, NASDAQ noise) on one calendar, cut by BTC state / fuel / alt bleed, weekly correlations,
                     worst weeks, signal -> book. Three families (MOMENTUM trend/daily/rsi80, FORCED FLOW sleeve/capit2/news/crowd/bids, NEUTRAL mn/carry/ndx/noise), weekly corr +0.04..+0.19 between them;
                     the machine's one losing state = BTC bull + fuel LOW (75 days, -22.6%, all trend); the live tape is that corner then a deep alt bleed, where mn and daily lose (the live losers) and
                     the sleeve / news carriers are idle by their triggers. Series cached in logs/works_map_series.pkl; logs/works_map.json feeds the 'What Works Map' artifact. tests 6 (9 of 9); doc 02 last entry
backtest/liq_capit.py   2026-11-15: the liquidation map + real OI flush aligned with capit2 (743 trades from 2022-02): 0 of 3 factors; capit2 already +1.95% / +4.22% a trade, 92% won; the map's flush runs
                     OPPOSITE to the real OI fall (rank -0.28). tests 6 (10 of 10); doc 02 last entry
backtest/crash_lessons.py   2026-11-21: THE CRASH POST-MORTEM of the final machine's live record (read-only, copies of the VM logs): the crypto book was net SHORT (main -0.26x / -0.11x, QQQ +0.4x beside it), beta to alts ~0; the whole record (-24.9%, 42 days) is below all 890 backtest windows with the same BTC + alt move (median +23%); per book MN / daily / capit2 / sleeve / NASDAQ dip under
                     their matched ranges, trend above; capit2 replayed with the bot's own code = its 3 live trades (faithful; the decline had fewer flush days); MN's backtest crash weeks lose via the short leg.
                     `python -m backtest.crash_lessons <copied logs> [--parts ABCD]`; no tests (a read-only audit; capit2 parity with the live trades is its check); doc 02 last entry
backtest/analyst_states.py   2026-11-15: the works map's states on the desk's 9,830 crypto replay calls: 4 registered gates, none improves (following the state makes calls WORSE, -3.7 / -3.8 points);
                     post hoc, calls AGAINST the state beat the rest +3.7 / +3.8 points (t 2.5 / 2.0, every year) and still lose -0.16 / -0.23R -> analyst.py records each call's market state and
                     'lean' with a registered forward test (lean_test, from 2026-11-15 14:00 UTC, 30 bets of each lean); the pick prefers 'against'. tests 6; doc 02 last entry
backtest/flow_shift.py   2026-11-15: forced flow x2 (and daily x0.5, crowd only in bleeds) when the median alt is down 15%+ in 30 days, weights at entry / day-open, vs the bet-bigger line: NO PASS
                     (every variant loses the tune half; earns on bleed days but worst month -19 -> -26%, capit2 at 4x liquidates 5.8%); only 'crowd always' clears both halves. tests 7 (11 of 11); doc 02 last entry
backtest/analyst_review.py   2026-11-02: the Analyst desk's 52 calls reviewed with the 1-minute path of each: gross -0.10R a call (no skill), fees 0.24R a call = 70% of the loss, the 16 calls with RR > 4 went 0 for 16 (-20.3R > the whole -16.7R);
                     losers move the wrong way (only 4 of 31 touched the target later), wider stops make it worse; a filter RR <= 4 and stop >= 0.4% is the only fix the data supports. tests/test_analyst_review.py 6 (9 of 9 mutations caught)
backtest/universe_floor.py   2026-11-02: the MN book on the PIT top-40 / 30 / 20 (base top-60) on all 7 weekdays and the daily book on top-30 / 20 (base top-40) - does dropping the small names help? Every floor loses the tune half
                     (MN Sharpe -0.40..-0.76, 0/7 weekdays) and gains the holdout (+0.07..+0.19), does nothing in the live tape's alt-bleed weeks and deepens the MN fall (31% -> 44-47%); the daily book is lower on both halves
                     in 30 of 30 pairs and top-20's shallower fall loses to the base at 0.75x. NO PASS (doc 02, last entry). tests/test_universe_floor.py 11 (20 of 20 mutations caught)
dashboard sweet-spot card   2026-11-06: the Analyst tab's 'Sweet-spot watch' (`dashboard_push.sweet_view` + `Dashboard.js` SweetSpot): the registered claim and its forward progress, a countdown to the desk's :07 run, every open call tagged sweet / middle / scalp-sized and priced from the live price with the desk's own past odds (95% range on independent bets, 'chosen after looking'), and where a FIB zone or a strong SR level could fire next. BUILT AND TESTED (35 dashboard tests, 34 of 34 planted bugs), DEPLOYED 2026-11-06 17:40 UTC (commit `3cd87d8`, feed + page only)
backtest/analyst_sweetspot.py   2026-11-06: the Analyst desk's 'sweet spot' REGISTERED for a forward test (the user: 'a lot of potential'): the desk's scalp-sized calls (stop < 0.4%) went 1 for 19, -20.5R; calls with a stop of 0.8%+ went 13 for 28 (46% vs 13% random odds, +0.71R) but are only 14 independent bets (t +1.2, cut found after looking).
                     Registered 2026-11-06 15:00 UTC: stop >= 0.8%, bet = day + side, bar = 30 bets, >= +0.15R, t >= 2, hit above random odds, both halves positive; scored on calls made after it. tests 8 (19 of 19 planted bugs); doc 02 last entry
backtest/sweetspot_deep.py   2026-11-15: the Analyst desk's sweet spot (stop >= 0.8%) analysed in depth from the live log (copy: logs/analyst_calls_20261114.csv), the cached replay and Binance 1-minute candles, with a NEW matched random-entry control IN R (same coin, side, stop, target, hours; reproduces desk.baseline's win rates exactly):
                     forward 21 calls / 12 bets -0.32R a bet (t -1.0) vs the discovery's +0.44R (14 bets); excess over random forward -0.25R a bet, all live +0.20 (t +0.8); the fee is 0.09R at these stops vs 0.57R at scalp-sized ones (most of the 'sweet spot'); the live period paid shorts (random shorts +0.4R, longs -0.4R); registered test needs +0.90R from the last 18 bets: P(pass) ~0%; $20 at 1% following only the forward calls -9.8%. Audit script, no tests; doc 02 last entry
backtest/combo_screen.py / combo_direction.py / combo_rangerev.py / combo_rowcheck.py / combo_rowcheck2.py / combo_ridge_dissect.py / combo_wide.py   2026-11-15 (/goal, rounds 2-3; round 3 = round 1's 27 cells per call: 0 of 27, panel signals add -0.001R, best cell frozen on 284 unseen coins +0.040R excess but -0.034R absolute): a screened ridge (0 of 18), a direction-features-only ridge / boosting (0 of 18 at the bet level), the artifact behind a +0.147 diagnostic (uncentred feature, short-only selection vs an all-sides baseline, day-vote mean; per call it is worse than random), a PER-CALL re-score of all 36 cells (0 of 36 with selected >= +0.05R in both halves; ONE lead, G1 ridge on 13 direction features top 5%: +0.051R selected vs -0.084R same-side = +0.135R, t +3.1, shift p 0.002, = trend-continuation shorts, +6bp a trade absolute, ~0 since 2025), and its test on 284 unseen point-in-time coins (frozen on the majors: excess -0.026, selected -0.108R; native: +0.018, -0.042R): does NOT transfer. tests/test_combo_wide.py 18 (37 of 37 non-equivalent planted bugs caught); doc 02 last entry
backtest/combo_meta.py / combo_universe.py   2026-11-15 (/goal 'a perfect combination of every signal, including the desk's forward data'): walk-forward meta-models (ridge and a small tree) over 55 candle features + the panel's 91 daily signals. (1) The desk's 10,081 replay calls: 0 of 12 cells pass, the E set does worse, the raw IC +0.20..+0.25 is the fee / stop-width tie-break (fee-free +0.05..+0.07), the first run's within-bet gate could not see market-level skill (power check) and was amended; (2) a FIXED trade at every 6th hour, 3 brackets, 70k candidates each: 0 of 27 cells, four panel-signal cells t +2.2..+2.3 that decay in 2025-26 (Holm 0.26-0.37);
                     both applied to the 92 live forward calls: nothing (|t| <= 1.1). Power: a planted +0.10R-per-sd skill is NOT recovered, so the null excludes only large combination skills. tests 20 + 11; planted bugs 40 of 40 + 15 of 15 (controls survived); doc 02 last entry
backtest/mn_booking_convention.py   2026-11-06: the live paper books the MN basket RE-STRUCK at every daily mark (combo_paper.py, constant dollar weights) while the backtest (mn_run) and the real-order ledger hold FIXED COINS: same 337 weekly baskets x 7 start days booked both ways - mean gap -0.126 points a week (|t| <= 1.5 per start day, 2026 +0.25),
                     standard deviation 3.49, 25% of weeks differ by over a point, tails of +-50-70 points in the 2025-09 squeeze; on fresh's live baskets -$5.26 vs +$4.11 = $9.4 of its -$90. No bias, a lot of noise; a shadow fixed-coin line is the proper addition. tests 5 (18 of 18 planted bugs); doc 02 last entry
backtest/fx_gotobi.py   2026-11-04: the Tokyo 'gotobi' fix flow on USD/JPY (5th/10th/15th/20th/25th/month-end, long from the 09:00 JST open to the 09:55 JST fix), 19 years of HistData minute bars, 3 windows x 3 calendar definitions, 1.2 pips, EUR/USD placebo: gross +0.72 bp on gotobi days vs +0.91 on other days (t -0.4), net -0.38 bp;
                     the 08:00 JST start is the nearest lead (excess +1.4 bp, net +0.76 bp, t 1.5, Holm rejects none); a general Tokyo-morning dollar bid of ~0.9 bp every day is about the cost. tests 10 (22 of 22 planted bugs); doc 02 last entry
backtest/his_cme_scan.py   2026-11-04: 'must be something in CME': a multi-feature gradient-boosting scan of EVERY second of the 31 windows around his clicks (22.7 h of NQ mid, 10-level book sizes and aggressor-signed trades, 66,806 labelled +-7 races), leave-one-window-out: within-window AUC 0.521 (se 0.018), best bucket with 100+ events 48.5%
                     right (the bar 65%, his 95%); at his clicks the label reproduces his side 83%, the CME model 45%. Found its own bias (pooled leave-one-group-out AUC 0.454 below chance, the up-rate alone 0.389). Not excluded: rare complex states, per-order data, other CME products; the untested observation is CapitalFX's own tick stream. tests 11 (22 of 23 planted bugs); doc 02 last entry
backtest/nq_scalp_ml.py   2026-11-04: can anything predict NASDAQ's next 3-30 minutes? Walk-forward ridge + boosting on 17 price-and-volume features (4 volume), 441,760 decisions on 16 years of bought NQ minutes, test years 2014-2026: pooled rank IC +0.003..+0.016 against +0.054..+0.018 needed at the Exness cost;
                     the strongest tenth nets -0.2..-0.5 bp, 0 of 18 cells reach t 3 at 0.77 bp, 14 of 18 nominally positive at a 0.25 bp futures-like cost and none at t 3 (best +0.59 bp, t 2.3); volume adds nothing. Scalping NASDAQ from public price and volume: not found in 16 years. tests 8 (21 of 21 planted bugs); doc 02 last entry
backtest/nq_fetch.py / nq_noise.py   2026-11-03: Databento NQ 1-minute bars WITH VOLUME bought (USD 19.93, 2010-06..2026-10, 5.46M bars; strategy_analysis/data/nq_1m). The noise rule on the real futures: +2.27 bp/day (CFD +2.25), daily correlation 0.972; halves uneven (tune t 1.2, holdout t 2.9; double costs t 1.6);
                     the published VWAP trail adds nothing (-0.02); opening volume does not predict when it works; VXN-above-median days clear the bar on NQ (+4.51 bp on 48% of days, tune t 2.2 / holdout t 2.3) and cut a $300 x5 account's fall from 65% to 44% at the same CAGR. tests 8 (9 of 9 planted bugs); doc 02 last entry
backtest/nasdaq_regimes.py   2026-11-03: the noise rule by dealer-gamma regime (VIX>VIX3M 7% of days +9.98 bp; VXN>median 49% +4.54 bp t 3.2 Sharpe 0.85 (post-hoc, replicates); range>60d median +3.01, holdout t 0.6): same direction on all three, none strong enough to gate trades -> shadow arm; and the
                     leveraged-ETF closing-hour flow (gross +0.8..+1.1 bp a trade, net -0.2..-0.5 after cost). tests 6 (8 of 8 planted bugs); doc 02 last entry
backtest/know_when_not_to.py   2026-11-03: 'he knows when not to' tested as a DISASTER filter on a +2.5 bp no-stop trade (88,464 entries, 3,686 sessions 2010-2026, logistic + boosting trained to 2019-12, 35,256 test entries): AUC 0.61-0.63; keeping the safest 50/20/10/5/1% raises the win rate to 96-98% but
                     the remaining losers grow to -140..-180 bp (the model removes the harmless late-day misses, not the crash days): 0 of 10 cells earn money (best -1.02 bp vs the baseline -1.25). tests 7 (9 of 9 planted bugs); doc 02 last entry
backtest/small_profit_scalp.py   2026-11-03: 'it is simple maths: take small profits' - written as plainly as possible (trade with the day's trend after a 30 s pullback, +3/+5/+7 no stop, 36,034 random entries, 18 cells): 0 of 18 earn money (best -1.66 points a trade); the break-even win rate is
                     94.7% (+7) to 98.1% (+3) because the rare loser averages -126..-151 points (worst -991), random entries win 93.4-96.6%, so every cell is 1-2 points of win rate short; the trend and pullback filters add under one point. tests 6 (8 of 8 planted bugs); doc 02 last entry
backtest/his_losers.py / noise_pullback.py   2026-11-03: his losses examined (21 of 46 NASDAQ trades above +7.5 make 83% of profit; 15 of 17 trades short of the target are small wins; the two losers were pullback BUYS in a trend that turned: -7.5 cut in 10 s, -31.75 held 48 min; 37 of
                     41 gold trades are one 48-minute sitting on a 99th-percentile day, net +$74) and his pullback entry bolted onto the NOISE rule (all 4 variants worse, -0.9 to -1.2 bp/day, paired t -3.8..-5.0). tests 7 + 7 (8 of 8 planted bugs each); doc 02 last entry
backtest/his_exit_shape.py   2026-11-03: 'we have his win rate, that is enough' - NO: from 7,192 RANDOM entries on 181 tick days every one of 30 target x stop combinations loses (-1.8 to -2.9 points a trade, spread ~2.2); his own exit shape (+7, no stop) wins 93.7% from random entries
                     (his 44/46 = 95.7% is indistinguishable) with an average loser of -132 points, break-even win rate 95.0%; his two real losers averaged -19.6. His win rate is the exit's doing; the edge is in the entry. tests/test_his_exit_shape.py 6 (7 of 8 mutations caught, 1 equivalent); doc 02 last entry
forex_bot.py   2026-11-03: THE FOREX BOT, release 1 - BUILT, NOT RUNNING. NASDAQ "noise area" momentum on Exness USTECm (the one forex-side candidate: fx_intraday_pub.py / noise_book.py), intraday, flat 15:58 New York (no swap), DEMO ONLY: asserts a demo account on every
                     connect, `--mode live` is refused, ALLOW_REAL=False and there is no real-money path. Virtual $300, 0.05 lot (~4.8x), disaster stop 3%, -8% daily kill, spread / stale-tick / holiday filters, restart reconciliation, hash-chained log, cost audit vs the
                     backtest's 1.27 bp. `python forex_bot.py --mode dry|demo | --parity | --report | --verify`. From a five-advisor council (doc 02, last entry). Expect ~+$20 a year on $300 (backtest typical +$46, fall 56%); the demo proves plumbing and costs, not the
                     edge (~7 years for t = 2). tests/test_forex_bot.py 23 (24 of 25 mutations caught, 1 equivalent); parity 150/150 days with the backtest
backtest/his_rsi_long.py / his_sittings.py   2026-11-03: RSI on 5- and 15-minute candles (built from Exness 1-minute bars, so the 15-minute RSI has history; periods 2-21) at his 45 usable NASDAQ entries: 0 of 42 cells survive Holm (the 5-minute levels all read rank 0.41-0.42 = his
                     known pullback lean, p 0.04-0.07, one finding), best second-half net race 39.1% vs 50% break-even. his_sittings: 22 of 31 sittings are one trade; first tickets 29/31 at +9.22 points vs later 15/15 at +9.07 - the record is not built by add-ons. Tests 8 + 4 (10 of 10 and 5 of 5 mutations caught); doc 02 last entry
backtest/his_rsi.py   2026-11-02: 'could it be RSI?' - 51 RSI cells (15 s / 1 min / 5 min candles x periods 2-14 x level, slope, hook) at the NASDAQ trader's 25 clean entries vs nearby moments, and as a 3-minute NASDAQ signal on 181 tick days:
                     0 of 51 reach raw p < 0.05, 0 survive Holm; the best second-half net race is 37.5% (break-even 50%). RSI(14) reproduces his_ta.py (rank 0.46). tests/test_his_rsi.py 7 (8 of 8 mutations caught); doc 02 last entry
backtest/passive_markout.py   2026-11-02: the MAKER rebuttal to 'the order-book edge is smaller than the fee', tested on the ~40 minutes of real books the Module 5 recorder captured (ten pairs, 2026-10-30): markout of a resting order at the touch
                     (queue-free upper bound, 2bp maker fee). 30 s markout -0.8..-2.3bp on 9 of 10 pairs (ADA +0.3 +- 0.6); the mid moves against the filled side by about the half-spread or more, so every pair's net bound is negative (UPPER -1.7..-4.3, LOWER -8.9..-14.1);
                     imbalance leaning WITH the fill is better on 10 of 10 pairs (+3.0bp average) and still leaves BTC at +0.1bp. First run counted every print at or below the touch as a fill (76% of BTC's were sweep levels) - fixed. tests/test_passive_markout.py 12 (8 of 8 mutations caught); doc 02 last entry
backtest/rsi_ratio.py / rsi_ratio_check.py   2026-11-02: "RSI worked with a few big losses - there must be a take-profit / stop-loss ratio that pays": RSI(14) crosses (30 / 25 / 20 long, 70 / 75 / 80 short, plus the capitulation volume rule) on the PIT top-40 at 1h / 4h x 16 brackets
                     (stop 0.5-4 ATR, target 0.5-4R) = 448 cells, each against the SAME bracket from random entries at the same day x slot: PASS 0; per trade every textbook oversold-long bracket loses on the tune half (-0.04..-0.40R) and is at most +0.01R on the holdout;
                     RSI entries win exactly as often as random ones (mean gap 1.7 points), so the ratio only trades win rate for payoff. The best cell's +0.37R was a day-vote mean (-0.15R a trade; capped account -16..-96% a year) and the one rescue (quiet days win) was a look-ahead.
                     tests/test_rsi_ratio.py 13 (27 of 27 mutations caught), tests/test_rsi_ratio_check.py 4 (8 of 8); doc 02 last entry
backtest/book_sustained.py   2026-11-04: the user's sentence tested as written - '90% buyers in the book who stay a minute, then trade' - on the seven Bitget DOGE days (one-second rebuilt book; best level / 5 / 20 levels / within 10 and 25 bp of the mid; bid share 70 / 80 / 90%;
                     held W = 1 / 10 / 30 / 60 s; taker in the next second, out 30-300 s later; control = same clock hour): 90% buyers is a normal state AT THE TOUCH (9.5-31.8% of seconds) and never exists deeper (imb20 / band10 / band25: 2 / 21 / 2 runs in 7 days); touch runs have a median of 1 s and NONE lasted 60 s
                     (one 60-second episode in seven days). After 10 s of touch dominance the next minute moves +1.4 bp (excess +1.3 bp, t 4.5, 831 events) = a third of the 12bp taker fees AND of one spread; PASS 0 of 143 cells even against the queue-free 4bp maker bound. Leverage multiplies fees against margin (12bp = 1.2% of margin at 10x), it cannot cut them.
                     tests/test_book_sustained.py 16 (22 of 22 planted bugs caught); doc 02 last entry
backtest/gold_news_breakout.py   2026-11-08: GOLD around NFP (199 events) and FOMC (108, 2013 on), HistData bid minutes: follow the move 1 / 2 / 5 min after, BREAK the first 5 / 15-minute range (the user's rule) and a +-5 / 10 / 20 bp straddle, each with LEVEL / CLOSE / EXTREME fills, against the same New York clock time on ordinary days.
                     The release minute moves gold a median 24.6bp (NFP) / 16.4bp (FOMC) vs 3.3 / 1.3 on ordinary days. The only passes (NFP straddle at LEVEL fills, +20bp, t +5) are a fill artifact: the trigger minute runs a median 34bp past the level; at the bar's close the same straddle is -3bp, at its worst price -11bp.
                     The break rule: NFP -3.7 .. -10.9bp; FOMC +9.0bp at the close fill (t 2.29 pooled, 2.05 / 1.27 by half, 1 of 42 cells, 2 x se 13bp) = a lead needing ~200 events. Follow: NFP +1.6 .. +4.4 net at +1 / +2 min, never significant on both halves, gone by +5. tests/test_gold_news_breakout.py 42 (41 of 41 planted bugs caught); doc 02 last entry
backtest/inside_bar_break.py   2026-11-08: the user's 'mother and baby' rule - 30-minute bars, a new 20-bar high, a big mother candle (>= 1 ATR14) with an inside baby (<= half its size), SHORT when the baby's low breaks, stop at the mother's high, 1/2/3R targets, 24h exit, managed on 1-minute bars; TOUCH (sell-stop) and CLOSE (market at a bar's close) fills, control = the same bracket at the same minute-of-day on 5 random other days of the same half:
                     gold: TOUCH n 1,342, -0.23R a trade at 2R (win 32% = the coin), CLOSE -0.10R, excess over the control nil (t -0.9..+0.7); the mirror (long at new lows) also null; 7 forex pairs, S&P, DAX: every short loses. ONE cell of 56 passes: NASDAQ buy-side TOUCH (n 889, +0.08R, excess t +2.34 / +3.01) but its CLOSE fill fails the bar (t +1.25 / +2.33) = a LEAD (a NASDAQ dip-buy). Same entry also logs the gold leverage checks (a 100x shot is a coin flip; the daily trend peaks at 3x, +12%/yr, fall 74%). tests/test_inside_bar_break.py 42 (100 of 100 planted bugs caught); doc 02 last entry
orderflow/ (book.py, store.py, recorder.py, verify.py, features.py)   2026-10-30: Module 5. PUBLIC-DATA-ONLY recorder for Bitget's `books` + `trade` websocket channels on the ten registered pairs (raw gzip frames,
                     one file per pair per UTC hour, each opening with a book CHECKPOINT; gap detection by the pseq chain; renewal of a pair's subscription; reconnect with backoff; single-instance lock),
                     a verifier that rebuilds every book and audits it EXACTLY against fresh snapshots from a second connection at the same global seq (89 of 89 exact), and a 1-second feature sampler under
                     the strict timestamp rule (`lag_ms`, `day_coverage`). tests/test_orderflow_core.py 21 (33 of 33 mutations), tests/test_orderflow_analysis.py 14 (19 of 19). No keys, no orders, nothing can trade.
                     `python -m orderflow.recorder --out <folder> [--minutes N]`; `python -m orderflow.verify <folder> [--since YYYY-MM-DD_HH]`. The OFFICIAL record has NOT been started (user's call).
btc_regime_now.py  LIVE read-only readout: 1000h gate, 4h break level, momentum, Coinbase
                     premium, funding. Public endpoints, no keys. (doc 12)
blend_paper.py     THE LIVE PAPER BOOKS — seven in one process. main / tight / sized /
                     sboost / tstop / units / triple. The last four are a 2x2 factorial over
                     {time stop, 7 units} on the tight base: both main effects and the
                     interaction, read forward. Best backtest: triple, **+10.43%/mo**
                     holdout WITH the 10x guard the bot enforces (+10.76% without it -
                     quote the guarded one, see section 6).
mn_paper.py        the 5th book: market-neutral, pre-registered, verdict at 26 rebalances
combo_paper.py     THE COMBINATION (doc 14 s8/s9): triple + 21d anchor + MN 1x + bear sleeve 1x on one
                     $221 paper account, pre-registered. ON THE VM since 2026-09-24 12:40 UTC
                     (combo-paper.service, deploy/install_combo.sh); verdict ~2027-03-24
wick_paper.py      THE CRASH BIDS (doc 16 s7), pre-registered: top-40 bids 10% under, none on BEAR days,
                     first 10 fills an hour, sold at the hour's close; from 1-minute candles after
                     each hour, on BITGET and BINANCE ($300 ledger each, +120-min exit recorded beside).
                     No orders, no keys. For the VM: deploy/install_wick.sh (pulls, verifies, installs
                     wick-paper.service). Verdict at 6 months with 60+ Bitget fills, else 12
xs_paper.py        an EARLIER pre-registered XS test (21 coins, daily). Frozen — do not edit
news/mood_now.py   2026-10-23: LIVE crypto mood, read-only - crowd positioning / funding / taker / OI per coin, the crowd
                     book's quarters flagged (doc 25 s7: positioning a lead, chatter dead). python -m news.mood_now
crowd_book.py      2026-10-25: the crowd book INSIDE the fresh final-machine account (combo_bot.py --crowd, x1.0); main has none
news/crowd_paper.py  2026-10-23: THE CROWD-SQUEEZE PAPER BOOK (doc 22 s4 override): long the crowd's most-short quarter,
                     short the most-long, Monday + Thursday halves, own $300; hourly on the VM (crowd-paper.timer), also
                     writes logs/mood/mood.json for the dashboard. Verdict 2027-04-26 (dead < -6.5%, crowd_bands.json).
                     Standard library only. --status. tests/test_crowd_paper.py checks it against positioning_hist's code
poly_structure.py  2026-10-26: READ-ONLY Polymarket structure scan (neg-risk sum gaps net of the docs' fee formula, how long gaps live,
                     reward-market yield). No orders. tests/test_poly_structure.py 20 tests, 17 mutations caught. Result: dead (doc 02, last entry)
backtest/convexity.py / runner_gate.py   2026-10-27: the machine's daily account series (cached), lumpiness, waiting, the day-45 line priced,
                     the 'fuel' (share of the top-40 already running) that precedes the trend book's good months - readable, not tradable;
                     news/mood_now.fuel() + news/fuel_bands.json = the dashboard gauge (built, not deployed)
backtest/cot_shapiro.py / cot_shapiro_more.py / dist_days.py / residual_edge.py / crypto_regime_score.py / alt_rotation_gate.py /
  stockbee_crypto.py / ict_fvg.py / ndx_gap.py / ndx_gap_check.py   2026-10-27: the Claude trading skills (tradermonty, SKE-Labs) implemented
                     as written and tested, predictions first - nothing passes; one small real effect (large NASDAQ gaps continue) that is
                     mostly the NOISE book; residual_edge: the machine's return is not BTC beta (doc 02, last entry)
sentiment_rec.py   2026-10-12: retail long/short ratios (Myfxbook, OANDA, + 7 brokers via FXSSI) every 30 min, record
                     only (no history is free); predictions R1-R3 in its docstring
breadth_rec.py     2026-11-22: MARKET BREADTH RECORDER on the VM (breadth-rec.timer, daily 02:00 UTC): the Nasdaq-100 stocks' 1-minute bars (public Yahoo
                     chart data, pre/post) -> TICK / ADD / VOLD / TRIN-style breadth per minute, a PROXY of the exchange indices; strategy_analysis/data/breadth/
                     (raw/, minute/, breadth_rec.log); --backfill (29 days), --status. tests/test_breadth_rec.py 7 (10 of 10 planted bugs). For his next trades (s69)
doge_live.py / book_rec.py / liq_rec.py   2026-10-09: DOGE live forward test (frozen rules + logged calls, --call to
                     log a prediction), the order-book and liquidation recorders; scored by backtest/doge_adapt.py,
                     doge_bigtarget.py, doge_book.py. Data in strategy_analysis/data/{bitget_1m,doge_book}/ (gitignored)
backtest/book_hist.py   2026-10-28: the order-book checklist on 7 full Bitget DOGE days (Tardis free days, 95M rows + the tape): book rebuild, event study, one
                     claim tuned on early days and read on later ones, queue-aware limit-order replay with fees. imb1 predicts ONE tick; the tape fills the wrong side;
                     net -2bp a signal, 0 of 4 days positive (doc 02, last entry). tests/test_book_hist.py 9 tests, 12 mutations caught
backtest/fx_macro_data.py / fx_drivers.py / fx_surprises.py / fx_rates2y.py / fx_tff.py / fx_surprises_1m.py / fx_speeches.py /
  fx_news_tone.py / histdata_1m.py   2026-10-12: 30 years of forex DRIVERS (rates, risk, commodities,
                     positioning, data surprises): they move forex the same day; none predicts the next period (doc 02)
backtest/his_tickets.py / his_absorb.py / his_options.py   2026-10-12: his record is live (ticket counter); absorption and the options tape
                     ruled out
backtest/ustec_burst_anatomy.py / his_burst_after.py / ustec_burst_straddle.py   2026-10-12: NASDAQ bursts are foreseeable in time (AUC 0.86), not in
                     direction (0.51); his trades are ordinary moves, not burst trades - only his side is special (his_strategy s52)
backtest/his_clock_exits.py / ustec_burst.py / his_headlines.py / his_hour.py   2026-10-12: the trader's clock (exact), gold (no edge),
                     bursts (= random), headlines and the top of the hour - none reproduces his direction (his_strategy s49-51)
backtest/fx_news_seconds.py   2026-10-12: the news bot's window on Exness ticks - one second, the broker's lag, not an edge
backtest/ndx_close_momo.py   2026-10-12: NASDAQ last-hour momentum (market intraday momentum): dead - NASDAQ scalping closed
backtest/fx_t8_exness.py   2026-10-11: T8 (month-end USD) re-measured on Exness prices - kill stands
backtest/fx_capit.py   2026-10-11: the NASDAQ dip-buy both ways on forex/gold/silver at Exness prices: dead; Yahoo FX daily bars broken
backtest/ndx_capit.py / ndx_capit_check.py   2026-10-11: CANDIDATE - buy NASDAQ's sharp down days (RSI(2) < 10 / 3 down
                     closes), out above the 5-day average; 27 years both halves, weak on other indices, worst trade -20..-26%
backtest/mt5_1m.py / cfd_scalp.py / cfd_bigtarget.py / ustec_seconds.py   2026-10-11: Exness 1m bars from ticks with the real
                     spread; the DOGE scalping menu, the bigger targets and the seconds-scale test on NASDAQ/US30/gold/FX: dead (doc 02)
final_books.py     THE FINAL MACHINE's extra books for combo_bot.py --final (2026-10-09): MN half momentum / half RSI,
                     carry 0.5x, daily Bollinger (20-day exit) 0.5x, capit2 0.5x, the account-level 10x gate. On the VM
                     as combo-bot-final.service (--mode dry: $300 paper, all coins, no orders). tests/test_final_books.py
combo_bot.py       THE LIVE COMBINATION BOT (2026-09-24): combo_paper's three books executed on ONE Bitget
                     account, netted per coin, cross margin, 30% disaster stops, intrabar trend stops.
                     --mode demo (ON THE VM since 2026-09-29, combo-bot-demo.service; the demo lists only SBTC/SETH/SXRP, so every coin is
                     routed onto those by dollar value: an ORDER-PATH test, P&L meaningless), --mode dry
                     (all coins, no orders), --mode live (refused: ALLOW_REAL = False). --report = the
                     2-week check, now with a flip count and a VERDICT line. tests/test_combo_bot.py: 21 offline tests on a fake exchange.
                     --wick adds the CRASH DESK (wick_live.py, doc 17 s5): post-only buys 10% under,
                     cap 10 fills an hour watched every 3 s, sold at the hour's close via the netting.
                     tests/test_wick_live.py: 10 tests, 7 mutations caught. The demo was restarted
                     with it on 2026-09-24 22:52 UTC (test settings first, see s10)
longtrend_bot.py   the OLD Bitget demo bot, STOPPED 2026-09-24 (combo_bot replaced it on the demo
                     account). ALLOW_REAL = False. Its live mode trades a 9-coin list that is NOT the
                     validated 12-coin book - never take it live as it stands
micro_bot.py       the $10 go-for-broke bet. ALLOW_REAL = False. Odds re-measured 2026-10-06 (backtest/micro_honest.py)
health.py          "is anything wedged or dead" — three signals per bot
backtest/wick_better.py, wick_5m.py, joint_worst_hour.py, worst_month.py   the crash bids (docs 15/16):
                     which rule, what happens inside the hour, the account's worst hour, the worst
                     month and recovery. wick_replay.py replays wick_paper.py on past crash hours.
                     Candidate only - nothing in combo_bot.py
docs/              STATUS.md (CURRENT STATE, read first) + 00-26 + README (the index). DOC 21 = the graveyard audit (every kill rated, thin ones re-tested). Doc 02 is the graveyard; read it before proposing.
                     DOC 20 = THE PRODUCT: what combo_bot is, what it earns per market, and the
                     sideways gap with every test that tried to close it.
                     DOC 17 = THE MACHINE v2: all four books, the evidence, every risk in one table.
                     11 = money-machine search, graveyard re-check, lottery odds. 12 = BTC signals.
                     13 bear breadth, 14 drawdown + the final mix, 15/16 crash bids
deploy/            systemd units and the no-backslash VM patch scripts
logs/              state, trades, and the saved stdout of every experiment
```

## 5. The deployed strategy, in one paragraph

`bb_break(30, 1.5)` — a 30-bar Bollinger break at 1.5σ — on **12 coins × 3 sleeves**
(1h/4h/12h) sharing **12 slots**. 0.30% risk per unit, stop at **2×ATR(14) = 1R**. Longs
trail at 20×ATR and **pyramid up to 5 units, one every 2R**; shorts take 1 unit and trail at
5×ATR. Breakeven stop at 3R. While BTC is below its **1000-hour** average, risk is cut to
**×0.25**.

> **The 1000h / 200h gate question is SETTLED** (2026-09-23, `backtest/regime_gate.py`,
> [doc 01](docs/01-strategy.md)). The live bots gate on a **1000h** average; `REGIME_MULT`
> was tuned against **200h**, and `blend.btc_bear()` still uses 200h. Measured: the
> deployed 1000h gate costs 4.2%/month of tune-half return and buys a **21-point drawdown
> reduction** (76% → 55%), consistently on *both* halves. **The gate that is running is the
> right one. No change warranted.** Also settled: the ×0.25 multiplier is not a tunable
> parameter — bigger is better on the tune half and smaller is better on the holdout, at
> *both* gate lengths, so it is a bet on the next regime, not a number with a correct value.
> Backtests using `blend.btc_bear()` still read 200h; that is a known, quantified offset,
> not a bug to silently "fix".

Shorts are **supposed to lose** (−0.036R/trade under honest fill). They are a drawdown
hedge (78.6% → 68.9%), not a profit source.

## 6. What to expect — so you never quote a flattering number

Source: **`backtest/expectations_honest.py`** (2026-09-23), which supersedes
`expectations.py`'s figures. Same method, but with funding charged, real entry times, and
entry-sized compounding (rules 10–12). $200, 10 orderings, upside haircut 3×, downside raw.

| holdout (2024-08 on) | months losing | worst month | median 12 months | $200 → | DD |
|---|---|---|---|---|---|
| **main book (deployed)** | 56% | **−41.6%** | +61% raw / **+20% haircut** | **$241** | 54% |
| **tight book** | 56% | −34.7% | +128% raw / **+43% haircut** | **$285** | 51% |
| *old figure (expectations.py)* | *57%* | *−34%* | *+58% haircut* | *$316* | *58%* |

- **Capital does not change the percentage.** Above ~$25 the rejection rate is ~0% and the
  return is statistically indistinguishable; $10 rejects 2% of signals. Capital buys dollars, not
  rate. (A 2026-09-23 attempt to overturn this - "the venue minimum costs $221 0.29%/month" - was
  itself wrong: unpaired medians. Paired on the same orderings, -0.02%/month at t = -0.37. The
  original claim stands.)
- **The old +58% was inflated mostly by compounding**, not by the market. See mistake #14.
- Full history, entry-sized: main +84% haircut / +251% raw median year, tight +113% / +338%.
  **2021 alone made ~40% of lifetime profit.** Full-history figures are not planning numbers.
- P(losing month) is the one figure no modelling choice can flatter — the haircut is
  monotonic, so it cannot change a sign. It was ~56–57% under every correction.

**The best book, if the paper books hold it up** (triple = tight + time stop + 7 units; $221;
`backtest/one_year.py`, `backtest/month_dist.py`; upside haircut, downside raw):

| $221 after 12 months | bad year (25th) | typical | good year (75th) | ended below $221 | worst year |
|---|---|---|---|---|---|
| main, holdout / full | $250 / $245 | **$270 / $406** | $556 / $905 | 4% / 13% | $134 / $84 |
| triple, no leverage guard | $422 / $325 | $568 / $619 | $1,405 / $1,914 | 1% / 8% | $204 / $163 |
| **triple WITH the bot's 10× guard** (`triple_capped.py`) | **$407 / $318** | **$536 / $584** | — | **1% / 8%** | **$207 / $164** |

Plan on the guarded row. The bot refuses the adds that would breach 10×, so the unguarded row
counts trades it would never place.

Triple, by month: 44–48% of months up; median month −0.5%; a quarter of months beat +20%;
worst month −24% / −30%; best month +850% raw (December 2024). The year is made in one or
two months.

**AND THE WHOLE RETURN IS ONE REGIME** (`backtest/regime_and_liq.py`). Mean %/month *within*
each BTC regime, full history, haircut:

| config | BULL | BEAR | **CHOP** |
|---|---|---|---|
| main (deployed) | +23.05% | +0.26% | **−0.16%** |
| tight + time stop | +33.10% | −0.64% | +0.27% |
| **triple** | **+47.19%** | **−0.74%** | **+0.20%** |

Days by regime: **chop 948, bull 871, bear 581.** The book earns approximately nothing for **63%
of all days** and everything in the other 37%. **And the 2026-09-24 improvement did not change
that** - it doubled the bull number and left chop flat, and in a BEAR the triple is slightly
*worse* than the deployed book, because tightening exits and adding units both assume something
will run.

> So the honest one-liner for anyone deciding whether to run this: **it is a bull-market
> amplifier, not an all-weather book.** Six flat months is the expected experience of a chop
> regime, not a malfunction, and no configuration tested changes it. Doc 11 part 10.

### THE FINAL VERSION (2026-09-24) — the book to judge forward: `combo_paper.py`

**What it is.** One account running three books:
- the triple trend book at 100% (tight + time stop + 7 units), sized by the **21-day equity
  anchor**, with a 9x gross guard;
- the **bear breadth sleeve** at 1x (doc 13);
- the **market-neutral book** at 1x (doc 10).

**How it was measured** (doc 14 §8–§10). The trend book's gains are shrunk for hindsight and its
losses kept whole; the two point-in-time books are raw. This method reads the triple's biggest
fall as 63%, against 53% raw.

| $221, 12 months (`max_mix.py`, `logs/max_mix_pick.txt`) | typical | bad (1 in 4) | worst | years < $221 | biggest fall | months up |
|---|---|---|---|---|---|---|
| triple alone, 6 yrs / last 2 yrs | $592 / $530 | $269 / $368 | $121 / $134 | 21% / 11% | 63% / 58% | 39% / 37% |
| **FINAL, 6 yrs / last 2 yrs** | **$1,210 / $1,125** | **$491 / $740** | $151 / **$312** | 9% / **0%** | 59% / **45%** | **56% / 63%** |

**By market type** (`final_regimes.py`, `logs/final_regimes.txt`; average / typical month):

| | RISING (31 months) | SIDEWAYS (25) | FALLING (23) |
|---|---|---|---|
| triple alone | +58% / +15% | −5.4% / −8.1% | −3.5% / −3.5% |
| **FINAL** | **+67% / +19%** | **−1.3% / −6.4%** | **+7.6% / +4.7%** (64% of months up) |
| made by | trend +56, MN +4.6 | trend −5.2, **MN +4.3**, sleeve −0.7 | trend −3.4, MN +4.5, **sleeve +7.2** |

**Read it as:**
- a bull-market amplifier that now **earns in bears** and **loses less in chop**;
- **chop is still negative**, and that is the one weakness no test fixed;
- at $221, taking half of each month's profit gives ~$31–39 a month.

**Caveats:**
- The MN book's live record in `mn_paper.py` is inflated by the funding bug (§7b). The backtest
  and `combo_paper.py` count funding correctly.
- The sleeve's 2018 out-of-sample fall was 42% at 1x (doc 13 §7).

**THE MACHINE v2 = the final version + the capped crash bids** ([doc 17](docs/17-the-machine.md),
`backtest/machine.py`). On $300, the typical 12 months:
- $1,812 (6 years) and $1,625 (last 2 years), against $1,642 / $1,527 without the crash bids;
- the worst month is the same (−29% / −25%);
- sideways months average +0.2%, against −1.4%.

**Size:** ×1.0. ×1.2 buys only 8% more and deepens the worst month to −34%, with 35% of the account
left in the worst hour.

**Venue:** on Bitget's own prices the crash bids earn the same as on Binance (`wick_bitget.py`).

**A candidate fourth book: crash bids** ([doc 16](docs/16-crash-buys-safe.md), which supersedes doc
15's rule; forward test `wick_paper.py`). It was weak recently: Binance Jan–Jun 2026 −0.37% a fill,
Jul–Sep +2.77%. The rule:
- resting buys 10% under the last close on the PIT top-40;
- 1/40 of equity each;
- **none on BEAR days**;
- **cancel the rest after 10 fills in an hour**;
- sold at the hour's close.

Its numbers:
- alone, +16%/yr (tune +18.5%, holdout +11.4%);
- on $300 with the final version, typical year $1,812 / $1,625 (6 years / last 2 years) against
  $1,642 / $1,527;
- the worst month is about unchanged.

**Never run it uncapped.** Doc 15's version left 10% of the account in the 2025-10-10 hour (§3).

**The worst month cannot be braked away.** 16 monthly brakes all lose to betting smaller
(`worst_month.py`). Size is the only dial: everything ×0.7 gives −25.5% / $1,510, and ×0.5 gives
−18.5% / $1,106.

**Withdrawals through a loss are what kill recovery.** After a −50% month, $20/month taken out
regardless leaves a typical $16 after two years. Paused while under the starting balance, it
recovers like no withdrawals.

**Risk per unit stays 0.30%** (`backtest/kelly_corrected.py`). 0.45% buys +0.34%/mo on main's
holdout and multiplies P(80% drawdown within 3 years) by nine (2.7% → 24.7%), with max gross
leverage past 10×. 0.6%+ has a LOWER holdout return. 7 units adds notional, so the triple has
even less room. More return comes from 7 units or from capital, not from risk.

## 7. Hard safety rules — do not cross these

- **`MAX_LEVERAGE = 10.0` in `blend_paper.py` is not a tuning parameter.** It costs the
  triple book 0.35%/mo and it is the only thing standing between that book and liquidation:
  at its 12.2x peak (a single ordering reached 13.2x), an **8.2% adverse move closes the
  whole account**, and the alts it holds
  fall 27-34% in a day at their worst. The backtest cannot model forced closure, so the
  unguarded return is computed in a world without the risk removing it creates. Asked and
  answered 2026-09-24, doc 11 part 10b.
- **`ALLOW_REAL = False`** in `longtrend_bot.py`, `micro_bot.py` and **`combo_bot.py`** is a gate
  a **human** must edit. Never flip it, never work around it.
- **`combo_bot.py` needs a DEDICATED account.** It nets the whole account to its books, so any
  position it did not open is closed on its first poll.
- **Never handle the user's credentials.** Not in chat, not in a file, not in an argument,
  not in a log. Keys come from the environment only (`BINANCE_TESTNET_KEY`,
  `BITGET_API_KEY`, …) and are used read-only unless the user has asked for an action.
  Sandbox mode is forced and asserted against the resolved URL.
- `strategy_analysis/statement_raw.txt` and `statement_trades.csv` are gitignored — they
  contain a real name and account number. Keep them that way.
- **One account, one bot.** Starting a second bot on the same Bitget account doubles every
  order. Stop the local one before deploying to the VM.
- Dry runs get their **own** state and log files. Sharing a log with the live bot once made
  it look like the live book had gone flat when it had not.

## 7b. OPEN BUGS — read before trusting a live book's numbers

- **FIXED IN THE CODE 2026-10-09, NOT YET IN THE RUNNING DEMO: an order under one venue step killed the whole poll.**
  ccxt's `amount_to_precision` raises (bitget: "must be greater than minimum amount precision") instead of returning 0,
  and `combo_bot.execute` did not catch it - so every later order, the disaster stops AND the state save were skipped,
  every poll, for as long as the books wanted a sub-step change in that coin. Seen on the VM in the final bot's dry run
  (a 0.046-SOL reduce, step 0.1). `Venue.contracts` now returns 0 (refused, logged once);
  `test_an_order_under_one_step_does_not_kill_the_poll` fails on the old code. **combo-bot-demo runs the old code until
  restarted** - it has not hit it (0 poll errors), but if its `--report` ever shows poll errors, this is the first
  suspect. Restarting it is the user's call (its two-week PASS check is due ~2026-10-13).

- **v2's market-neutral book can be wiped out by one squeeze, depending on its rebalance day** (found 2026-10-08,
  `backtest/mn_combos.py`, `logs/mn_rebalance_days.txt`). **FIXED IN `combo_bot.py` AND DEPLOYED 2026-10-08 18:37 UTC** (commit cb6bcbf; only combo-bot-demo restarted,
  every other service's code verified byte-identical; state backup `logs/combo_bot_demo/cs.20261008-183656` on the VM)
  (`mn_squeeze_exits`, `MN_SHORT_EXIT = 0.50`; 2 tests in `tests/test_combo_bot.py`, 23 pass, 5 mutations caught incl.
  the old no-exit behaviour; one dry poll clean). `combo_paper.py` is unchanged - pre-registered - and still carries the risk. Uncapped, on 1 of 7 rebalance days the 2025-09-12 week (MYX) costs 99% of the account. The
  live `combo_bot.py`'s 30% disaster stop does not protect it: the netting re-opens a stopped position on the next poll.
  `combo_paper.py` and the demo bot run the uncapped book on whatever day they started. The tested fix is a short-leg
  BOOK exit at +50% (out of that name until the next rebalance): same average Sharpe across the 7 days, worst week -29%.

- **The seven blend books' RECORDED equity is overstated - the triple's by ~$325** (found
  2026-09-29, `rebuild_equity.py`, **not fixable in place, measured instead**). Positions opened
  before the entry-sized fix carry no `risk_usd`, so blend_paper still sizes them at CLOSE, each
  on the one before. On 2026-09-28 eight such runners closed in two polls and the triple went
  $209.68 -> $883.52 recorded; entry-sized, the same 548R is ~$555. **It WILL recur on main,
  sized and short-boost**: without the tight exit they did not sell on 09-28, so they still hold
  their pre-fix runners (VM 2026-09-29: all 36 / 1 / 1 of their closes legacy, $207 banked), and
  their recorded equity will jump the same way when those close. The four tight books have
  banked theirs. The inflated level stays in every book's state. **Compare the books with `python rebuild_equity.py`** (one line
  per book: recorded, CORRECTED, and a self-check that replays the log to the cent) **or by R -
  never by `blend_paper.py --status` equity.**

- **FIXED 2026-09-29: both market-neutral books dropped held coins that left the top-120 pool.**
  `combo_paper.py` and `mn_paper.py` priced only today's top 120 by 24h volume, and read a held
  coin outside it as delisted: exited at the previous mark, zero for its day, slot empty until
  the next rebalance. The combo lost CAP, CYS and TUT that way in three days (12 names -> 9).
  `mn_paper.held_closes` now prices them; `tests/test_mn_held.py` fails on the old code. Takes
  effect on restart (`deploy/update_combo.sh` on the VM; `mn_paper.py` wherever it runs). The
  three names stay out until the 2026-10-01 rebalance.

- **FIXED 2026-09-25: `wick_live.py`'s cap cancelled nothing in a full sweep** (mistake #16). The
  live crash desk did not implement the cap its own backtest models — doc 16's "capped leaves 47%
  of the account" was a property of `wick_5m.py`, not of the code. Fixed, with two regression tests
  that the old filter fails. **`combo_bot.py` must be restarted to pick it up**; until then the
  running demo carries the old desk.

- **FIXED IN THE BOT 2026-09-29, paper books unchanged:** `combo_bot.py` now reads each coin's
  step, amount minimum and value floor from Bitget's own market record (`Venue.rules`), rounds
  to the NEAREST step, and does not send an order the venue cannot accept - logged once as
  `BELOW VENUE MINIMUM`, counted in `--report`, never an ORDER FAILED. A full close always goes.
  5 new tests in `tests/test_combo_bot.py` (19 total), all 5 fail on the old code. **Takes effect
  when the demo bot on your PC is restarted.** `blend_paper.py`'s MEXC table is untouched - it
  decides the PAPER books' entries, which are pre-registered and hash-checked. Not verified
  against Bitget's live list from the cloud container (network blocks it); `--mode dry` on your
  PC does that. The original finding:
- **The book sizes orders from MEXC's minimums, but trades BITGET** (found 2026-09-26,
  `backtest/bitget_minimums.py`). `combo_bot.py:75` uses a flat `MIN_ORDER = 5.0`
  and `blend_paper.py:239` uses a MEXC table where LINK is $1.13. Bitget also enforces a minimum
  AMOUNT in coins - 1 whole LINK, 1 DOT, 0.1 LTC - which neither file knows about. Measured on the
  triple book with the price at each trade: at $221 Bitget refuses **26.2% of LINK units, 15.1% of
  DOT, 8.4% of LTC, 6.4% of the book**; at $100, 24.2% of the book. Consequences, in order of
  importance:
    1. **It is not a P&L bug.** The netting design means a refused order creates no phantom
       position - the next poll sees the shortfall and retries. And the floor HELPS return
       (+0.48 tune / +0.38 holdout %/mo at $221, paired, 10 orderings), because the units it
       refuses are the ones with the widest stops.
    2. **It is a retry loop.** The bot re-sends an order the venue can never accept, once per
       2-minute poll, until the position closes. 188 of the demo's 230 order failures are this,
       one every 2:10 on the same symbol.
    3. **It breaks the bot's own PASS test**, which requires zero order failures - so the
       two-week order-path check cannot currently distinguish a venue artifact from a real fault.
    4. **Rounding is the part nobody counted**: the amount minimum is also the STEP, so every
       accepted LINK order is rounded to a whole coin - median size error 9.4% at $221, LTC 6.7%,
       DOT 4.3%. That applies to every order, not just the small ones.
  The fix is a per-coin table read from the venue's own `limits` at startup, replacing both the
  flat $5 and the MEXC table. `small_capital.py`'s headline ("the venue minimum is not the binding
  constraint") survives - but it was measured on the wrong venue, so say Bitget when quoting it.

- **The crash desk places ZERO bids on the demo** (found 2026-09-26, not a code fault). At $221 a
  bid is $5.19, and the demo lists only SBTC/SETH/SXRP - all three under Bitget's minimum size at
  that value, so `wick` logs `0 bids placed` every hour. The desk's state confirms it: 3 coins, 3
  lifetime fills, all from the earlier `--wick-usd 30` test settings. **So the cancel-at-cap path
  fixed on 2026-09-25 still cannot be exercised on this demo** - doc 17's "not yet seen on the
  exchange" is stronger than it reads. Seeing it needs `--wick-usd` above the demo's minimums.

- **`mn_paper.py` over-counts funding, roughly double** (mistake #15, found and verified
  2026-09-24, **not yet fixed**). Its `startTime` is inclusive and its window has no `endTime`, so
  it summed **8 settlements for one daily mark** where a day has 3. Funding is ~a third of that
  book's edge, so **its live record is inflated**, and `combo_paper.py`'s market-neutral leg is a
  separate, correct implementation - the bug is confined to `mn_paper.py`. It had ONE mark when
  found, so the cheap fix is to correct the window and reset that book's state; the expensive
  option is to leave it and discount the record later. Doc 14's mix recommendation leans on this
  book, which is why it is listed here rather than buried.

## 8. How to check what is running

```bash
python health.py
```

On the VM (Azure portal → VM → Run command → RunShellScript):

```bash
cd /opt/forexbot && ./.venv/bin/python blend_paper.py --status
```

```bash
cd /opt/forexbot && ./.venv/bin/python combo_paper.py --status
```

**From the user's PC a session can reach the VM directly (since 2026-10-05):** `ssh forexbot-vm` (alias in
`~/.ssh/config`, key `~/.ssh/forexbot_vm`, user root - the bots run as root). No 4KB limit:
`ssh forexbot-vm 'bash -s' < deploy/status_digest.sh`. **Read-only unless the user agrees to a change**; the
key has no passphrase, so remove it (root's `authorized_keys`, comment `forexbot-vm`) or add one before real
keys go on the VM. The VM's address is in the ssh config only - never commit it (the repo is public).

**Everything at once, read-only, under Run command's 4KB:** paste `deploy/status_digest.sh` - services, crash-bid
paper, the seven books' CORRECTED equity, the combo paper book, and the demo bot's two-week verdict (last).

**Deploy to the VM by `git pull`** (the repo was made public 2026-09-23):
`deploy/pull_and_rebuild.sh` pulls, verifies `blend_paper.py` by sha256, restarts and prints
the books. `deploy/check_vm.sh` is a read-only "what is on that box" check.

The old `deploy/patch_*.sh` base64 scripts are superseded. Keep them only as the record of how
the box was patched before the repo was public.

## 9. Working style the user has asked for

- They want things **tested, not discussed.** "Turn every stone." Run the experiment.
- They want **plain English** for results, and honest ones — including when the answer is
  "this is dead."
- **Never present a backtest as a return they will get.** State the haircut, the holdout,
  and the regime dependence every time.
- When a result looks good, the next move is to look for the bug that made it look good.
  Every large improvement in this repo's history was a bug until proven otherwise.
- **Keep `docs/STATUS.md` true.** Deploy, restart, start, stop or retire anything, or let a gate date pass, and the same
  session updates it and re-stamps "Verified" (`bash deploy/verify_status.sh` gives the facts). Put a headline return
  next to its paper result, its drawdown and its gate - never alone.

---

## 10. Session log

*Newest first. One entry per working day, and only what a later session needs to know -
the detail lives in the numbered docs.*

### 2026-11-21 - "keep the paper bots running but can we learn something from these days": the account was not a market bet; its whole record is below every backtest window with the same market move (`backtest/crash_lessons.py`, doc 02 last entry)

- **Read-only post-mortem** (copies of both accounts' logs at 2026-11-20 ~21:00 UTC in the session scratchpad; Binance daily and 4h bars; the backtest's 9 books per slot ordering). Nothing changed on the VM; the paper bots keep running (the user's wish).
- **Not a market bet:** main's placeable crypto book was net short throughout (-0.26x before 11-10, -0.11x in the crash) beside a QQQ long (+0.42x / +0.28x); its daily beta to the point-in-time alt index was -0.01; on the worst alt day (11-14, -11.1%) it made +2.3%. The losses were coin selection.
- **Outside the backtest:** main's 42 days (BTC -24.2%, alts -28.7%) -24.9% = below all 890 backtest windows with the same BTC and alt moves (15 start months; machine median +23.1%, 25% lost); fresh without its crowd book -29.5%, below all 680 (median +29.1%). Each phase alone looked like 1 in 10 (the October bleed 8th percentile, the crash 10th).
- **By book against the matched median (% of $300):** MN -11.8 vs +5.1 (made in October), daily -11.7 vs -4.6, capit2 +0.7 vs +9.7, sleeve -5.0 vs +1.6, NASDAQ dip -5.2 vs +1.3; trend +0.3 vs -3.4 (better: its shorts paid +8.5% in the crash), carry +3.3 vs +1.0 (then off at the $5 floor).
- **capit2 is faithful:** the bot's own `capit_signals` on Binance 4h bars gives exactly its 3 trades; this decline had fewer flush days (4 days of -5% or worse on the alt index vs a median 6). MN's backtest crash weeks lose too (-0.93%/wk, its shorts bouncing - the momentum crash); live it was the long leg (October's pumped coins). The sleeve turned BEAR late (11-16) and its first 5 days (-7.1%) are the 3rd percentile of the backtest's flips. The record began at the top of an alt run (fuel HIGH the week of 10-09).
- **Day-45 KILL stands** (doc 22 s3b; read 2026-11-23 00:04 UTC; main ~$207 against $261.30). Offered, not run: MN standing aside in panic states (post hoc, low prior), and the capital floor for real money.
- **Then "there must be a way to look at the market as a whole" (the desk's longs 1 of 23 in the crash week):** the FAST market direction as a filter on the desk (`backtest/analyst_fast_market.py`: alts 3 / 7 days, BTC 7 days, Fear & Greed): on 9,824 replay calls none helps in money on both halves (Holm 1.00), the kept calls lose under every gate; on the crash week every gate would have kept +20..+22R and dropped -15..-17R - one week fits any rule. Nothing changed on the desk.
- **Then "predict how a day will go from how it starts" (same-day trades, flat by midnight):** `backtest/day_start.py` on the desk's 5 coins, 1,759 days: after a strong start the rest of the day continued on 45-51% of coin-days (base 49%), no cell passes (Holm 1.00); crypto has no real day start - NASDAQ's version is the built, unstarted `forex_bot.py`.
- **Then "could the noise rule be what HE (the NASDAQ trader) uses?":** no (`backtest/his_noise.py`, his_strategy s85): 26 of his 37 cash-session clicks came while the price sat inside the noise band (no signal) and he won 96% of them; outside it his side matched the rule 6 of 11 (p 1.0).
- **Then "the volume pumping of that day or the 15-min chart":** not it (`backtest/his_volume15.py`, his_strategy s86): his side matched the day's direction, the day's / 15-minute buy-minus-sell volume and the last 15-minute candle 50-52% of 50 trades; he clicks at ordinary volume (0.99x, 45th percentile).
- **Then his flip pairs ("that does narrow down"):** `backtest/his_flip_pairs.py`, his_strategy s87: 6 same-day buy/sell pairs; no 1-minute reading flips with him in every pair (best: 3 of 6 as 'buy low / sell high in the last 3-10 minutes'), two pairs flipped within 27 / 39 s inside one candle - the signal is faster than the 1-minute chart.
- **Then "test what we can":** the flip pairs second by second (`backtest/his_flip_seconds.py`, s88: no 1-second reading flips with him in more than 2 of 5 pairs) and the on-exchange buying / selling in QQQ + the 8 mega-caps from the dark-pool cache, no new spend (`backtest/his_lit_flow.py`, s89: agreement 48-61%, ranks 0.48-0.56, rules 50-57% vs 55.7%). Every public source reachable has now been put next to his clicks; his side is in none of them. His broker's own ticks cannot be taken from outside (VertexFX, no authorised feed).
- **Then "there must be something you are not looking at":** the measurement re-checked (stale prices, clock, picked statement, hidden losers: all ruled out) and the last public sources bought at the user's yes - MNQ trades $3.81 + NQ futures options $0.00 (`backtest/his_mnq_optflow.py`, s90): his side vs retail flow 39-59%, vs options 47-62%, rules 50-58% vs 55.7%. SPX 0DTE options are not in Databento's OPRA. A professional's map of his habits (chat): he wins 92-100% with or against the trend, buys or sells, early or late - no setup type.
- **Then "the exit at the previous low is the most important clue":** `backtest/his_exit_levels.py` (s91): 2 of 35 exits at a previous 5-60-minute high / low (6% vs 12% by chance), 3 of 35 at a round 25-level (9%, chance); the level ahead sat 13-45 points away and he was out after 2-25 - his exits are point targets, not chart levels.
- **Then "see what the price did before on that level":** `backtest/his_level_memory.py` (s92): his side matched the textbook level-memory call (held -> bounce, broken -> flip) 8 of 19 (2 of 10 on strong levels); as a rule the call wins 48-50% on 181 days.
- **Then the user's 'against it' hint, sharpened:** at broken levels he trades BACK through them (fake-break / stop-hunt reclaims) - 7 of 7 won (`backtest/his_reclaim.py`, s93); as a rule on 181 days the reclaim wins 50-52% (fresh / strong the same): part of his playbook, not his edge.
- **Then which fake breaks he takes:** `backtest/his_reclaim_detail.py` (s94): depth, time beyond, snap-back, distance to the level, touches, activity - no quintile lifts the reclaim above 52-56% on both halves; his 7 sit spread across all of them.
- **Then "check" (stops absorbed?):** `backtest/his_reclaim_flow.py` (s95): inside his 31 sittings, 175 fake-break moments; absorption 44/59/48% by tercile, snap-back 45/56/50, last-60-s flow toward the reclaim 44/50/57 (t ~1.4, a lean); his 3 covered reclaims sit mid-absorption.
- **Then "buy, I don't care" (the CME tape for all 181 days, quoted $61.85):** NOT bought - a free stand-in first (`backtest/his_reclaim_tickflow.py`, s96: Exness tick direction, rank +0.57 with the CME flow): on 21,211 fake-break moments the last-60-s flow terciles win 49-53%, no lift - the s95 lean was the small sample; buying would not change the answer.
- **Then "search the web: how pros predict fake breaks":** practitioner tells mostly untested; Osler's FX round-number order clusters; the one NQ study (Taylor 2026, arXiv 2610.35887): fake breaks carry nothing beyond the daily trend. That filter on our setup (`backtest/his_reclaim_regime.py`, s97): aligned 51% vs opposed 49-54% - nothing; his reclaims ignore the trend. Untested: delta divergence.
- **Then "run delta":** `backtest/his_reclaim_delta.py` (s98): delta divergence at the fake break (stand-in = real tape on 86%) - with 49.9/52.6% vs without 50.3/52.5%; his 7 reclaims 3 with, 4 without, all won. Every practitioner fake-break signal found is now tested; none picks the reversals.
- **Then the study list for the user's own ideas, and "yes, test" its first item, SMT divergence** (`backtest/his_smt.py`, s99): the Dow or S&P refusing to break its matching level when NASDAQ breaks: Dow +1.8 / -0.5 points, S&P +1.8 / +1.6 (se ~1), both held 50.5 / 52.9% - nothing near 61%; after the shift and candle SMT ~50%. His 7: Dow held 4, S&P 3, both 3 of 6 (base 30 / 19 / 18%, p 0.07-0.13, a lean); he won the 3 where both broke too. Data: Exness US30m minutes = same builder as the tick cache (100% of minutes match).
- **Then "run" (study item 2, Al Brooks)** (`backtest/his_brooks.py`, s100): on the same fake breaks, weak breakout bars +2.3 / +1.0 points and no follow-through +0.7 / +1.7 (Brooks's direction, tiny); signal bar, second entries, the combination flip; his second-entry scalp on every minute 53.8% / 48.5% (a flip). His clicks look like every minute in Brooks's terms (strong signal bar 33% = 33%). Left from the list: Wyckoff spring test, internals (forward only), other chart types.
- **Then "run wyckoff"** (`backtest/his_wyckoff.py`, s101, real CME volume): test vs first push, low-volume tests, range support, effort vs result, the full Wyckoff entry: all within ~2 points or one half only; No. 3 vs No. 1 springs +1.9 / +3.3 (the third method showing 'weak breaks fail a little more', 1-3 points). His 7: 5 at the hour's extreme level (base 31%, p 0.033 among ~12 looks - not significant after correction). Left: internals (forward only), chart types.
- **Then "yes build it": the 'weak break' rule** (`backtest/weak_break.py`, s102): S&P held + weak breakout bar + No. 3 spring + the hour's extreme, score >= 3 of 4, FROZEN by sha256 (86fd452f...) before any day after 09-14 was fetched; fresh NASDAQ ticks + US500m from MT5 stored apart in `strategy_analysis/data/fresh/` (gitignored, 1.3 GB; MT5 lacks 09-15 / 09-16). Seen +4.2 points; FRESH (31 days to 10-29, CME volume ends there): 55.1% vs 52.6%, +2.5 (90% interval -3.3 .. +7.9) - same direction, smaller, no LEAD, far under 61%. His 7 scored >= 3 only once.
- **Then "run tick and renko charts"** (`backtest/his_alt_charts.py`, s103): his clicks follow the 1-MINUTE close (55% in 5-24 s vs 31%, p 0.002), not any Renko (5-20 pts, 10 offsets) or tick-candle size (best raw p 0.19, Holm 1.00); his side vs bricks / tick candles 45-62%; the rules 48-53%. He reads a plain 1-minute chart. Study list done except internals (forward only). The old logs/his_charts_*.png (2026-09-25) predate the winter clock fix (s35) and use 5-minute bars before June.
- **Then "make the picture book" -> "you will notice yourself, not me"** (`backtest/his_picture_book.py` -> logs/his_picture_book/page_01..11.png, 42 trades on the 1-minute chart at his price level; s104): no single picture repeats (~16 fades of sharp pushes at the edge, ~20 pullbacks with the bigger move, 4 breakout buys); OPPOSITE sides on the same chart within seconds, so the side is not in the picture. Its one new idea (`backtest/his_extreme_approach.py`): fade a CLIMAX push into a 60-bar high / low - 53.8% / 55.1% on the seen days, 50.1% on 44 fresh days (09-17 .. 11-20): gone. Trap met: `backtest/his_book.py` was an existing committed study (s38) - a Write overwrote it and it was restored from git at once; check a filename with `git log -- <path>` before writing a new study file.
- **Then "start recording the market breadth from now on vm"**: `breadth_rec.py` DEPLOYED (`3d0f49e`, VM fast-forwarded from `e79dec5`, 14 bot files byte-identical, nothing restarted; `breadth-rec.timer` daily 02:00 UTC; 29-day backfill by hand: 20 trading days 2026-10-26 .. 11-20, 100 stocks - EA and WBD no longer trade; Yahoo hole 2026-11-05 12:11-13:36 New York). The exchange TICK / ADD / VOLD are vendor data (TradingView's free copy may not be pulled by a server), so it computes them from the Nasdaq-100 stocks' 1-minute bars (Yahoo): a proxy. Then **"yes push it"**: the research backlog pushed (study scripts, tests, result logs, the picture book, docs; 400 files, 9.7 MB) after a scan for private data (VM address, email, dashboard / artifact links, keys, the trader's name / account / tickets: none new); `logs/*.pkl` caches (88 MB) and run markers kept local by `.gitignore`.
- **Then "there must be something we can implement":** two fixes tested, neither holds. Carry with fewer coins (to stay on under the $5 minimum) loses its holdout edge below 10 coins (`backtest/carry_names.py`: Sharpe holdout 0.74 -> 0.57 / 0.39 / 0.10 for 10 / 8 / 6); dropping daily, MN or the NASDAQ dip-buy makes the backtest machine worse at the same risk in 8-10 of 10 orderings (`backtest/book_drop_check.py`). What is left: capital (~$370 to keep every book on after a 35% fall at full size; half size needs ~$740 because every floor doubles), size, and a dashboard flag for books under their floor. No bot code changed.

### 2026-11-19 - "audit the whole dashboard and see what's happening": every number on the page is right; the carry book has been switched off by Bitget's $5 minimum since 11-13 (read-only)

- **Audit** (feed `dashboard_push.py --print` + the bots' raw files in ONE read-only ssh call at 17:18 UTC; scratch `audit.py` in the session scratchpad recomputes everything with its own code; `bash deploy/verify_status.sh`): both accounts' booked / open / live equity, all 9-10 books (booked = `cum`, open = positions), books - fees = equity - 300, closed-trade counts, peak / fall / today, every scorecard percentile from `dashboard_bands.json`, the Analyst desk (equity, 156 calls, sweet-spot forward 21 bets -0.116R), the momentum book, the crowd book, v2, both crash-bid ledgers and the Leads rows - ALL MATCH (the one 'difference', news 37.5 vs 35.0 percentile, was my own tie convention). Every mark sits inside Binance's 1-minute range at the feed's minute (41 symbols). The bear label (BTC under its 50-day average, slope -2.45% at the 11-15 close) and breadth20 (1 of 60 above its 20-day average, only AKE, 11-14..11-18) re-derived from Binance: right. News classifier right on all 30 recent headlines (0 tradable notices in 33 days). Services all active, 0 restarts, 145 MB free; combo-bot-final's 'restart pending' = the documented 10-24/10-25 live-only and fresh-only changes (dry booking identical). The page itself rebuilt from `e79dec5` and rendered on this feed in a throwaway local copy (generated password, deleted; launch.json restored): 7 tabs, no NaN / undefined, no console errors, no overflow at 375 px.
- **State (11-19 17:18 UTC):** BTC $62,287, Fear & Greed 10, alts -30% in 30 days. Main $227.91 live (-24.0%, 2.8th percentile), fresh $185.89 (-38.0%; $215.85 without the crowd book, 1.8th). Since 11-15: main -$12.16 (MN -5.0, capit2 FIL -3.4, new QQQ dip-buy -3.0, sleeve -1.9; trend +1.8, bids +0.9). **Day-45 (doc 22 s3b): main needs $261.30 at 2026-11-23 00:04 UTC = +14.7% in 3.3 days; the backtest machine does that in 7-10% of 3-4 day windows (`machine_account_daily.pkl`), far fewer in a bear with fuel LOW - the KILL is near certain.**
- **Found: the carry book is OFF.** `final_books` sizes each of its 24 names at booked equity x 0.5 x 0.5 / 12 = E/48 and skips names under Bitget's $5 floor: below ~$240 the whole basket is skipped. The 11-13 (main, $218) and 11-14 (fresh, $202) rebalances came back EMPTY; it stays off until a weekly rebalance sees ~$240 again. The best book live (+$9.91 / +$16.27, frozen since) is gone, and the scorecard still says 'on track'. Other floors at E: crash bids E/40 ($200: fresh's are already off once the label leaves BEAR), sleeve tranche E/35 ($175), MN ~E/19 (~$95), daily E/16 ($80), capit2 E/4. The backtests have no $5 floor; at $300 the carry book had 25% of room.
- **Display gaps (no wrong totals):** (1) the scorecard shows carry 'on track' while it holds nothing; (2) 'Profit & loss by strategy' bars are BEFORE each book's own costs (fees lumped in one line): crash bids -$0.42 gross is -$2.17 after its 0.38% a fill; (3) the paper books hold positions a Bitget account could not: coins Bitget does not list (AGT, AIN, GTC, RLC) and sub-$5 trend units (WLD $1.09, DOT $1.64...) - books' gross $546 vs the placeable ledger $473 on main, $530 vs $448 on fresh. Offered a page-only fix; nothing changed (code freeze).
- Others: crowd paper $263.88 (-12.0%, every one of 6 closed weeks negative; its 2027-01-25 stop line is -7.8%), Analyst desk $304.25 (+1.4%; 3 shorts open in profit), momentum $297.56 (5 trades, -0.165R), crash bids Bitget +0.24% a fill on 130 (claim +0.8), v2 $129.48 (-41%), pair -7%. The forward ledger was last run 11-09 (PC, monthly).

### 2026-11-15 (evening) - "why are main and fresh down, and where are the bear-market profits": the bear book has not switched on yet, the shorts are small by design, and MN / daily lost where the backtest's crashes made money (read-only)

- **Read** (feed 2026-11-15 ~15:50 UTC via `dashboard_push.py --print`, both accounts' logs copied by scp, scratch script `crash_analog.py` in the session scratchpad - nothing in the repo, nothing changed on the VM). BTC $65.3k, 26% under its 60-day high ($86.6k, 09-21), -22% in 30 days, Fear & Greed 10. **Main $240.07 live (-20.0%, 5.0th percentile, max fall 30%), fresh $202.32 (-32.6%; $227 without the crowd book, 3.1th percentile, "worse").**
- **Where it went (main / fresh, booked + open):** MN -$30.7 / -$32.8, daily -$35.1 / -$34.7, trend -$5.4 / -$16.7 (longs 0 of 45 / 0 of 50 won, -$28 / -$25; booked shorts +$0.8 / +$2.2, OPEN shorts +$22.3 / +$6.8), crowd (fresh) -$24.2, NASDAQ dip +$0.2 / -$6.5; carry +$9.9 / +$16.3, capit2 +$6.7 / +$6.4, bids -$1.3 / -$1.2, sleeve 0, news 0. The crash week (11-10..11-15) cost main -$55, MN -$28 of it.
- **Why no bear profits:** (1) the bear sleeve never fired: its label needs BTC under its 50-day average AND that average down 2% in 20 days; the slope was -1.99% at the 11-14 close, so it reads BEAR from the 2026-11-16 00:00 UTC mark (BTC would need a close above ~$83k to stop it). With breadth20 at 1.7% its first signal is LONG (the capitulation-bounce bet, 1/7 a day for 7 days), not a short. (2) Trend shorts are one unit each and quarter-sized since BTC fell under its 1000h average (first quarter-risk close 10-17/18): the last week's shorts made +14R on main = +$2.48. At full size they would have added ~+$11 on main, against MN + daily -$66. Bigger shorts in bears were tested and failed on the corrected engine (`graveyard_rescore.py` 'lean short x3': tune +0.86, holdout -1.28 %/mo). (3) MN's long leg is pumped micro-caps (11-13 basket: MAGMA, AGT -40%, AIN, JCT, BIRB, IRYS...), short leg majors (XRP, SOL, DOT -10..-13%): in a crash the long leg fell harder. (4) The daily book is long-only; AKE -45%, AIN -57%, JCT -56% fell inside a day between daily-close checks = -$25 of main's -$35.
- **Against the backtest:** 240 analogue days (BTC >= 20% under its 60-day high and >= 15% down in 30 days) in 25 distinct months, 2020-26: the machine over the 37 days INTO such a crash median **+25%** (p25 +3%, 80% up); per book at 1x MN +5.3%, capit2 +1.9%, bids +1.0%, trend -3.1%, daily -2.5%, sleeve ~0 (it pays after); next 90 days median +36%. Live is -20% / -24% (ex-crowd): MN and daily are where live diverges from the backtest's median. CORRECTED the same evening (scratch `crash_books.py`, per episode): episode medians +15%, 8 of 25 episodes negative; MN lost in such crashes too (2024-07 -7%, 2025-11 -12% at 1x, vs live ~-10%) - inside the backtest; the daily book's live loss (~-23% at 1x) is about twice its worst episode found (-10%). Every intuitive fix is already tested and failed (bigger bear shorts, faster bear label, alt-bear shorts, daily 2xATR stop, MN universe floor / vol screen, coin cap, brakes, take-profit); untested: a coin-AGE floor on MN / daily (only carry had one, carry_check F), offered, not run.
- **Day-45 (doc 22 s3b):** main needs $261.30 live at 2026-11-23 00:04 UTC, +8.8% in 8 days; fresh ex-crowd ~$227 against the same line at 12-01. Nothing changed (code freeze).

- **Then "check if there is a discrepancy between the daily breakout backtest and the forward test" (`backtest/daily_live_vs_backtest.py`, `logs/daily_live_vs_backtest.txt`, doc 02 last entry): NO CODE DISCREPANCY.** The backtest rule replayed on Binance bars over the live weeks gives the same trades on the same entry and exit days (16 of 18; replay -22.7% vs live -22.1% a trade on main); IOST / RAYSOL were the pre-10-22 universe (fixed); AIN (-57%) is a trade only because the live bot reads the NEW month's top-40 for the last close of a month - a convention no worse over history. The 120-bar panel rule hides nothing (12 coins, mostly stock tokens, no big losers); AKE / AIN / JCT are 363-478 days listed, not new coins. The run is outside the backtest: 10 trades averaging <= -22% in 0.59% of runs (never since 2025), 3 under -40% in 10 never. A 20-35% disaster stop removes those losers and lowers the per-trade mean on both halves at all 3 boundaries (post hoc). What is wrong is the book's evidence (holdout rests on 5 pump trades), not the bot. Nothing changed.
### 2026-11-15 (forex: round numbers) - the user: "I see an edge in forex too, whatever it takes": Osler's stop cascade at big figures is REAL (19 years, every era, confirmed on Exness ticks) and worth ~+1 pip an hour - the Standard spread eats it (`backtest/fx_round_levels.py`, `backtest/fx_round_breakout.py`, doc 02 last entry)

- **Bars 2007-2026, 7 majors, round vs arbitrary-level control:** crossing a big figure runs +0.5 / +1.0bp further (15 / 60 min) than crossing an arbitrary level, t +5..+9 on both halves; fading a first touch loses 0.7-1.6bp more (the take-profit 'bounce' does not exist). A stop order at the big figure +- 0.5 pip: +1.1 pips gross at 60 min on both halves, net of 1.2 pips -0.2bp a trade (no pass); at 0.6 pip +0.35bp; ~2,270 trades a year.
- **Exness ticks 2026 (real fills):** excess over control +1.07 pips at 60 min (replicates); the trade loses -0.57 pips a trade (spread at fill 1.78 pips on the Standard 'm' symbols, slippage +0.17); EURUSD +0.87 / USDJPY +0.81 net, the rest negative (post hoc). A LEAD conditional on an all-in cost under ~0.8 pips (a Raw / zero account - unverified for the user). Tests 12, planted bugs 8 of 8; my first tick simulator found ~0 trades (fixed before reading). Nothing deployed or committed.
- **The user's account is STANDARD:** at its real spreads (median 0.8-1.5 pips at the fill) the tick result is -0.51 pips a trade even with fills over 1 pip skipped; only EURUSD +0.87 (t +1.0, 207 trades, post hoc). Not tradable on that account.

### 2026-11-15 (the sweet spot in depth; the leverage panel's missing percentage) - the user: "I want a detailed analysis of sweet spot signals", then mid-run "when I choose leverage from the safest option like XRP on 26x the profit didn't update and other information too"

- **Sweet-spot analysis (`backtest/sweetspot_deep.py`, `logs/sweetspot_deep.txt`, doc 02 last entry; predictions S1-S5 registered in the file first, four right, S1 half right):** the registered forward sample is 21 calls / 12 bets at -0.32R a bet (t -1.0) against the discovery's +0.44R; a matched random-entry control in R puts the forward excess at -0.25R a bet and the all-live excess at +0.20 (t +0.8); the fee is 0.09R at these stops against 0.57R at scalp-sized ones; the live period paid shorts (random shorts +0.4R, longs -0.4R); the registered bar needs +0.90R from the last 18 bets, P(pass) about 0%, 30 bets about 2026-11-26; $20 at 1% following only the forward calls -9.8%; the 4.7-year replay -0.126R a call. Nothing deployed or committed.
- **The leverage panel (found by the user):** picking a leverage changes only the margin locked and the liquidation price; the position, the dollars at the stop and at the target are set by the risk % and the stop, so they cannot move (the panel said so in words). What it did NOT show is the number an exchange shows: the profit as a % of the margin locked (XRP long, $20, 1% risk: +19% at 3x, +161% at 26x on the same $0.81). Added `gainOnMargin` / `lossOnMargin` to `dashboard/lib/size.mjs`, to every row of the leverage guide and to ticket lines 5 and 6, and rewrote the leverage text to say what changes and what does not (to make or lose more dollars risk more, not more leverage). Tests: sizer 6, sizepanel 25 (two new, by hand); planted bugs 10 of 10 with the no-op control surviving; `next build` passes; checked in a throwaway local copy on a fresh feed (typed 26x: margin $0.52, liquidation 3.3%, loss -39% / gain +199% on the margin, step 2 says 26x, same $0.20 / $1.03; 375 px no overflow, no console errors; my generated password, files and launch.json restored). **DEPLOYED 2026-11-15 ~11:02 UTC at the user's word ('deploy it'), commit `6c06925`:** the five files `dashboard/app/Dashboard.js`, `dashboard/lib/size.mjs`, `dashboard/lib/sizepanel.mjs`, `tests/test_sizer.py`, `tests/test_sizepanel.py` only (a diff of exactly the leverage fix, 39 lines added / 6 removed; secrets scan of the added lines clean; sizepanel 25, sizer 6, dashboard 44, sweet-spot 8 pass; `next build` passes), from a clean worktree on origin/main, tests re-run there, pushed to main (Co-Authored-By line). The VM was NOT touched (page + styles + logic only); it stays at `847b4bc`. Local main moved to `6c06925` with `reset --mixed` after proving the five working copies identical to the commit (nothing discarded; the other uncommitted work untouched). **Vercel: 'Deployment has completed'** (GitHub commit status of `6c06925`, 11:02 UTC). The live page itself was not opened by me (production password rule).

### 2026-11-15 (the liquidation map) - the user: "if we can predict the exact liquidity sweep prices we can scalp in crypto with high leverage" -> "Yes, test it": no pass; the map finds forced trading, not direction (`backtest/liq_map.py`, doc 02 last entry)

- **Verdict given first (chat):** the obvious sweep level, cascade bounces and open-interest flushes were already dead; leverage cannot rescue a small edge (`scalp_1m.py`); the one untested piece was an estimated liquidation map. Prior ~5%.
- **Built and run:** `backtest/liq_map_fetch.py` (Binance metrics archive, hourly open interest, 347 symbols, 87,273 symbol-days, ~25 min) and `backtest/liq_map.py` (map, events, resting limit at the cluster, 4h / 24h / bracket exits, same-distance random-time controls). 0 of 6 cells; no magnet (fill ratio 0.97-1.01); no bounce; long side loses on the holdout. Post hoc `--validate`: cluster hours trade ~20% more volume than control hours (t +14 / +15), so the map is not blind - it finds forced trading that does not point the next move. L1, L2, L4, L5 right; L3 wrong.
- **Checked:** tests 20, 30 of 30 planted bugs (two rounds), control survived. Nothing deployed, committed or restarted.
- **Then "test it on 1 minute candles"** (`backtest/liq_map_1m.py`, `logs/liq_map_1m.txt`): every fill re-collected exactly (37,905 events / 9,366 cluster fills) and re-scored minute by minute: 0 of 8 cells; the scalp bracket (0.5% / 1.0%) loses ~20bp a trade on both halves; the price runs further past cluster levels than past random ones (median 0.58% vs 0.48%, M2 right); deep (8%+) clusters bounce +31..+35bp at 15 minutes, the same as any 8% dip (excess ~0). The heatmap tells WHERE forced trading happens, not which way. Tests 8, 15 of 16 planted bugs (1 equivalent).
- **Then "Yes, test it" (orders resting just PAST the clusters, `backtest/liq_map_past.py`, `logs/liq_map_past.txt`):** 0 of 18 cells (k 0.25 / 0.5 / 1% x 15m / 60m / scalp x side); fills only 1-3 points more often than past random levels; longs positive on the tune half only, shorts lose everywhere; deeper orders do better per order placed, but random levels show the same slope (fewer trades, fewer fees); deep longs +43..+56bp at 15m equal any 8% dip. P5 wrong (tune half), the rest right. Tests 10, 17 of 17 planted bugs. `liq_map_1m.exits_from` split out (log reproduces exactly). The heatmap is closed: no entry, no execution edge.
- **Then "find me a new strategy from it then or integrate it in liquidity sweep" (`backtest/liq_sweep.py`, `logs/liq_sweep.txt`):** the map's estimate and the real open-interest fall in the sweep hour as filters on `sweep_confluence.py`'s own 43,500 sweeps (2022-02 on): 0 of 6 subsets, stage 1 0 of 4; long sweeps that cleared more leverage do WORSE (spread -4..-25bp); one short cell (OI fell in the up-wick) +11 / +15bp spread, t 1.2 / 1.5. The map's 'liquidated' figure is mostly wick depth (rank +0.60, already tested as F1) and nearly unrelated to the real OI fall (S2 wrong). Tests 10, 20 of 20 planted bugs. Nothing deployed or committed.
- **Then (the user, angry: "you are just too eager to drop it ... create a map of all the things that works, connect them, align them, till this day") - `backtest/works_map.py` + `backtest/liq_capit.py`, the "What Works Map" artifact (private; its link is in memory, not in this public repo), doc 02 last entry.** Every surviving book on one calendar cut by market state: three families with weekly correlation +0.04..+0.19 between them; momentum owns runs (fuel HIGH), forced flow owns bears and alt bleeds, neutral is steady except market-neutral in deep bleeds; the machine's one losing state is BTC bull + fuel LOW (75 days, all trend). Live (read-only from the VM, 2026-11-15 12:03 UTC): BTC $65,410 labelled chop, fuel LOW (1 of 39 running), median alt -33% in 30 days, Fear & Greed 10; main $236.40 (-21.2%, 4.3rd pctile), fresh $198.83; v2 paper $128 (from $192 on 11-13). The live losers (market-neutral -$34, daily -$35) are the books the map says lose in a deep bleed; the sleeve (needs a BEAR label) and news (no notices) are idle carriers. The liquidation map aligned with capit2: 0 of 3, capit2 already wins 92%; the map's flush figure runs opposite to the real OI fall (rank -0.28). Tests 6 + 6, planted bugs 9 of 9 + 10 of 10. Nothing deployed or committed.
- **Then "Yes, test it" (shift weight to forced flow in alt bleeds, `backtest/flow_shift.py`):** NO PASS against the bet-bigger line; every variant loses the tune half (forced flow x2 -$1,033 / -$547; + daily x0.5 -$796 / -$313); it earns on bleed days (+103% / +43% summed) but deepens the worst month 7 points and liquidates 5.8% of capit2's raised trades. Only the crowd book held always clears both halves (+$535 / +$4,101, crowd_combo.py's finding again; on paper). F1-F5 right. Tests 7, 11 of 11 planted bugs.
- **Then "add our findings to the analyst desk in any way that improves the signal" (`backtest/analyst_states.py`, analyst.py amendment of 2026-11-15):** following the market's state makes the desk's calls worse; going AGAINST it is +3.7 / +3.8 points of hit rate over random (post hoc, every year, still -0.16 / -0.23R a call). Each call records BTC label / fuel / median alt 30d (from logs/mood/mood.json) and its lean, a registered forward test (`lean_test`), the feed and the Analyst tab show it and the pick prefers 'against'. Tests 36 / 45 / 26 / 6, planted bugs 23 of 23, compiles on the VM's 3.10. **DEPLOYED 2026-11-15 ~13:16 UTC (the user: "deploy it"), commit `1a4f9d7`** (7 files from a clean worktree; VM fast-forwarded from `847b4bc`, 12 bot files byte-identical, nothing restarted, tests 36 / 45 on the VM, a temp desk cycle read BTC chop / fuel LOW / alts -33.5%; Vercel 'Deployment has completed'). The study files `backtest/analyst_states.py` + test stay uncommitted (research).
- **Then "remove unnecessary stuff from the analyst desk ... from a trader perspective signals should be clear": DEPLOYED 2026-11-15 ~13:50 UTC, commit `258c764` (page only, VM not touched).** The Analyst tab opens on one signal card: coin + direction, a grade (`sizepanel.gradeCall`: Best setup = stop >= 0.8% + still between stop and target + against the mood; Weaker setup = the same with the mood or no mood; Skip = tighter stop or the price ran) with ✓ / ✗ reasons, entry / stop / target / reward-to-risk, then the order in four numbers (size, leverage, loss if stopped, gain at target) and a one-line safety badge; placing steps and the leverage table folded; an 'All open ideas' table with grades; the record in one line; DeskIntro moved into 'Full details'. The top tab bar now scrolls inside itself (it had made the page wider than the screen at every width). Checked in a throwaway local copy on the live feed (desktop and 375 px, no overflow; password and files deleted, launch.json restored). Tests: size panel 27 (gradeCall new), feed 45.
- **Then "if I follow these signals how will it perform and how often" (`backtest/analyst_grades.py`, `logs/analyst_grades.txt`):** on the 4.7-year replay every grade loses: Best setup -0.141R a call (hit 15.9% vs 15.4% random), Weaker -0.117R, Skip -0.311R; $100 following every Best setup at 1% a call -> ~$5-10 per half, at 1% per bet (coins firing together split) -> $100 / $65; Best setups come ~14 a week in clumps of ~2.8 coins (~5 independent bets a week). The grade ranks bad vs less bad, not winners vs losers.
- **CORRECTION (the user: "are you sure 'with market mood' means not good?"):** in money the mood makes NO difference - against and with hit the take-profit equally often (16.9% vs 17.0%, 14.1% vs 15.2% at stop >= 0.8%); the '+4 points' was the random baseline (higher when trading with the drift), and per bet against minus with is +0.006 / -0.056R (t 0.1 / -0.7). The deployed grade (Best = against) and the pick's 'against' preference are not supported; doc 02 last entry. Only the stop size separates the groups (Skip -0.31R vs -0.12..-0.14R). **Fixed and DEPLOYED 2026-11-15 ~16:20 UTC (`e79dec5`, the user: 'yes, fix it'):** `gradeCall` = 'Has room' (stop >= 0.8% + still live) / 'Skip'; the mood is a neutral chip (good = null) and 'for context only'; `todaysPick` = newest idea with room again; analyst.py amendment corrected (docstring only). Tests 27 / 36, planted bugs 5 of 5; VM pulled (bots + feed byte-identical, nothing restarted). The live desk logged its first tagged idea (#136 SOL short, 'with') at 14:07 UTC.
- **Then "find me a strategy that actually makes money":** the answer from what exists, not a new test: the EVENT-ONLY account (`audit_event_only.py`: bear sleeve + crash bids + capit2 + news + NASDAQ dip, no trend / MN / daily / carry): backtest CAGR +121%, fall 22%, 78% of months up, $300 typical year $644 / $711, every calendar year positive (2026 to Sep only +8%, news -25%); without news (picked after looking) +95%, fall 21%. Post hoc by state (`works_map.py` section 6): positive in every state, both halves in all but BULL+LOW; strongest in alt bleeds (+141%/yr) and BTC bears (+138%). Live inside the paper accounts (feed 2026-11-15): main's event books +$5.14 while its other books lost -$63.84; fresh's -$1.71 (NASDAQ dip -$6.46) vs -$97.09; standalone crash bids +0.6% / +1.1%. It loses the bet-smaller line to the full machine on the backtest, but not in this tape. Offered: an 'Event-only account' line on the dashboard from the accounts' own books (no bot change).

- **/goal (2026-11-15, 'find an edge: a perfect combination of every signal, including the desk's forward data'): `backtest/combo_meta.py` and `backtest/combo_universe.py`, doc 02 last entry.** Two registered walk-forward combination tests: the desk's 10,081 replay calls with 55 candle features + the panel's 91 daily signals (0 of 12 cells; the E set does worse; the raw IC +0.20..+0.25 is the fee / stop-width tie-break; the first run's within-bet gate was blind to market-level skill - the power check caught it - and was amended with the first-run log kept), and a fixed trade at every 6th hour on three brackets (0 of 27 cells; four panel-signal cells t +2.2..+2.3 decay in 2025-26, Holm 0.26-0.37). Both on the 92 live forward calls: nothing. The pipeline cannot recover a planted +0.10R-per-sd skill, so the null excludes only large combination skills. Nothing deployed or committed; the goal as posed is NOT met.
- **/goal, round 2 (same day, the Stop hook kept the goal open): the instrument was fixed first, then the one lead was tried on data it had never seen. NO EDGE; the goal as posed is NOT met.** A screened ridge (0 of 18; the screen keeps regime-level features that flip), direction-aligned features only (0 of 18 at the bet level), then a diagnostic that read +0.147R (t +4.5) turned out to be a short-only selection compared with an all-sides baseline plus a day-vote mean (per call -0.157R vs -0.096R, shift-null p 0.983 - worse than random; trap row in s3). Re-scoring all 36 cells PER CALL (the gate averaged per day and side and had hidden the signal): 0 of 36 clear the bar, one lead: the ridge on 13 direction features, G1 bracket, top 5% - selected +0.051R vs -0.084R same-side = +0.135R (weekly-cluster t +3.1, shift-null p 0.002, matched to quarter x hour x volatility +0.149, deciles monotone, a planted +0.10R / sd now recovered as +0.224R). It is trend-continuation shorts of coins weak vs BTC: +6bp a trade absolute after 12bp fees, +0.080R in 2023-24, +0.019R in 2025-26, 2026Q3 excess -0.20, erased by 6bp of slippage, best of 36 cells; **on 284 point-in-time coins it had never seen: frozen on the majors excess -0.026 (selected -0.108R), trained natively +0.018 (selected -0.042R)**. The desk's 92 live forward calls: nothing (|t| <= 1.1). Doc 02's last entry has the numbers and all predictions scored; tests/test_combo_wide.py 18, planted bugs 37 of 37 non-equivalent, control survived. Nothing deployed or committed. Round 3b (`combo_rowcheck3.py`): the desk's own 10,081 replay calls per call with a stop-width / rule / side matched control: 0 of 12, matched excess 0.06 of the plain one, every selected mean negative. Round 3 (`combo_rowcheck2.py`): round 1's 27 richer cells (incl. the panel's funding / positioning / news signals) per call: 0 of 27, panel adds -0.001R, the best frozen on 284 unseen coins +0.040R excess but -0.034R absolute. Open (not started): funding charged on the shorts; only a forward record from here (the desk's calls plus a frozen model's picks logged before their outcome) could say more.

### 2026-11-13 (the Analyst desk, again) - the user: 'it is clearly not random, with proper stops and risk management there is a profitable strategy': run as a rule on 4.7 years, no pass (`backtest/analyst_user_rule.py`, doc 02 last entry)

- **Live breakdown** (`logs/analyst_calls_20261113.csv`, 122 resolved): 23% won vs 18% random odds, -0.20R a call, book $315.41 (+5.1%). Better groups: stop >= 0.8% (+0.27R), sweeps (SMC, +$22.71), BNB / BTC, shorts; worse: stop < 0.4%, SR, gold / QQQ. Split at the 2026-11-06 registration: sweep + stop >= 0.8% 10 of 17 before (+1.20R), 1 of 4 after (-0.35R).
- **The rule (crypto + SMC + stop >= 0.8%, with RR <= 4 / shorts / EMA variants; risk 0.5-2%, 3x cap, 2% day stop) on the replay engine:** -0.13 / -0.14R a call, hit below random odds on both halves, every year negative; no rule x risk setting ends above $300 on both halves. Nothing deployed or committed.
- **Then: "can't you measure his click timing"** (the NASDAQ trader) -> `backtest/his_click_timing.py`: his NASDAQ entries sit 10-16 s after a 1-minute close (median 14 s, 24 of 46 in 5-24 s, p 0.006); exits and gold entries uniform. Fits a chart reader or an alert at the close - the seconds cannot separate them; a screen recording of his next sittings can. his_strategy.md s73.
- **Then: his statement of 2026-11-12 ("trades of this month")**: 5 of 5 won (+$516.90, +7.1%); 3 NASDAQ sells all won the +-7 race at the statement clock UTC+5 (basis steady ~65; UTC+4 / +3 jump), and a copy 0-30 s late wins all three; 7 of 7 new races won since first contact. Traded at 04:38-05:00 New York (pre-market) and outside the 10-16 s click band. his_strategy.md s74; the PDF (name, account number) not copied into the repo.
- **Then (the user: never ask / record him - outside data only, memory `feedback-no-asking-the-trader`)**: `backtest/his_fade_stretch.py` - he does NOT fade a stretched 1-2 hour NASDAQ move (pos rank 0.545, p 0.26; the fade as a rule wins 37.9%); gold yes (p 0.002, one sitting, no edge). Ticket counter: no crowd entering with him (small sample). his_strategy.md s75.
- **Then: "Yes, pull it"** -> `backtest/his_cme_new.py`, NQ mbp-10 for his 7 new clicks (USD 0.99, Databento; cache `strategy_analysis/data/nq_new_mbp10.parquet`): 12 book / flow / move features, ranks 0.34-0.62, nothing; pre-market no different. his_strategy.md s76.
- **Then: "we have his strategy on gold, can we profit from it"** -> `backtest/gold_fade_stretch.py`: his gold pattern (fade the 2-hour stretch) as a rule on 16 years of gold minutes loses after 1.5bp in every year, 0 of 6 cells; the direction it carries is a tenth of the cost. His gold profits were one extreme day (2026-02-02). Doc 02 last entry.
- **Then: "what are we missing for NASDAQ"** -> `backtest/his_after_flow.py` (data on disk): the CME tape AFTER his 53 clicks - his move is concentrated in the first minute (rank 0.72, p < 0.0001) and fades by 5; it is made like any move of that size (matched flow rank 0.50) with no child-order clip signature: no worked big order behind it. his_strategy.md s77.
- **Then: "Yes, buy $4.89"** -> `backtest/his_vix.py` (front VIX future each second, cache `strategy_analysis/data/vx_bbo1s_windows.parquet`): VIX before his 53 clicks ordinary (ranks 0.48-0.54), following it wins 48%, VIX moves with / just after NQ, never first. his_strategy.md s78.
- **2026-11-14: "check asian european"** -> `backtest/his_world_indices.py`: 7 Asian / European index CFDs at his 53 clicks, none moves first (ranks 0.41-0.56, rules 47-49%, NASDAQ leads them all). **CapitalFX's own prices:** its client (unpacked, never run) names server 173.212.212.250 (ports 4401 / 1863) and web service `/vertexweb10/webservice.svc`; VertexFX's GetNewTick is documented as login-free; not yet queried (permission). his_strategy.md s79.
- **Then: "I want his edge, something logical and simple"** -> `backtest/his_setup_sweep.py`: his exact setup (his windows + trend + 15-min impulse + shallow pullback + resume 13s after a 1-min close), strength swept over 225 days / 5,493 setups: the +-7 race wins 49-50% at EVERY strength (window baseline 50.0%, random 50.0%); with-trend continuation at his moments carries no direction. Mechanical rule impossible. NOT selectivity either (the user: his ~5 trades a month are free time, not rare-setup picks; s33 showed his moments are ordinary on 75 features): his 88% is a real-time read of ordinary-looking moments, not a setup or patience. Not found in any public data tested so far (open problem, not closed). his_strategy.md s81.

### 2026-11-12 (an outside document on the Analyst desk) - the user: "strict, skeptical audit" of a 9-page PDF of recommendations: misquotes found; its four filters fail together out of sample (`backtest/analyst_filters_oos.py`, doc 02 last entry)

- **The PDF** (`C:/Users/HP/Downloads/reccomendation.pdf`, images only; rendered with pymupdf because the Read tool needs poppler): right on 10,580 calls, 18.04%, -99.97% (the 0.5% paper book); wrong or unsourced on the profit factor (0.42; the calls give 0.74 in R), '100% liquidation' (holdout at 10x: 0 liquidations), the $5-minimum reasoning (its own section 4.1 contradicts it), the session gate ('-220 -> -20R'; repo -220.9 -> -85.8R; the user's own '-94.1 -> -1.5R' misread analyst.py:53-54, where -1.5R is a loss threshold), and it presents post-hoc slices of 9-28 LIVE calls (+0.71R, +1.53R, -0.69R) as replay results. The gate it proposes is already live and DST-aware (`f921ca8`).
- **`backtest/analyst_filters_oos.py`** (the replay engine with every signal recorded, filters applied before the cooldown; no-filter parity exact): stop >= 0.8% + 4h EMA50 slope + session gate + no SR = 13% of calls, -0.093R / -0.106R a call, hit 4-6 points below random entries on both halves, $300 -> $195 / $225. The EMA50 slope alone makes the desk worse (-0.17 / -0.23R). O1-O5 right. No tests / planted-bug round (an audit check; parity with the replay is its test).
- **Then: "the Analyst desk is in profit, see if we got a strategy"** -> `backtest/analyst_profit_check.py`: book $320.79 (+6.9%, 119 calls) while the average call is -0.18R. The 3x cap skipped 36 tight-stop calls (-0.99R each); booked calls +0.17R (t 0.8); the best 3 calls exceed the whole profit; shorts made it. The wide-stop pocket since its registration: 14 calls, -0.18R. A +6.9% 119-call stretch occurs 2.5% of the time in the replay's own book. Not a strategy; the forward test (30 bets, ~early December) decides.
- **Then: "find me a new strategy" -> "yes, run it"**: `backtest/premium_dislocation.py` (perp's premium to spot, 365 coins incl. dead): no pass - long +0.74% / +0.36% a trade (t 2.2 / 0.4), rests on 5 days, 2026 negative; short dead. And "daily breakout is shit, not one positive trade": `backtest/daily_book_live_check.py` - 1 of 18 live is inside its history (9.4% of 18-trade stretches); three 45-57% losers on new hype coins (AIN, JCT not even in the backtest data) are not. Fresh is $198.62 (-34%): daily -$35, MN -$30, crowd -$21 (fresh only), trend -$20, NASDAQ dip -$6, carry +$16. The open-interest flush on the PIT top-40 (handed-off session) failed: -1.01% a trade on the holdout.
- **Then (as a senior analyst): "find an unbeatable edge ... fixed TP / SL is why they failed, they predicted the direction but not the power"** -> `backtest/direction_vs_power.py` on the desk's 10,522 replay calls with random-entry controls: refuted. Per call the direction is no better than random (the per-bet excess is the day-vote trap), the calls' best moves are smaller than random's, and six exits without a fixed target all lose per call on both halves. Doc 02 last entry.
- **Also today:** the top-40 open-interest flush test was handed off to its own session (`local_67f60bfe-bc68-4a6f-b726-fccce441432d`) when this request arrived. Nothing deployed, committed or restarted.

### 2026-11-10 (the audit) - the user: "audit all the strategies ... an edge so good we overlooked, one for low capital, some high frequency, and his edge in forex": two new checks, no pass; the trader copy is the only lead a forward record can settle in months (doc 02 last entry)

- **Read:** docs 21 / 23, his_strategy s56-72, STATUS, the live feed (2026-11-10 15:00 UTC: **main $255.35, under the $261.30 day-45 line with 13 days left**; fresh $222.49; crash bids 115 fills +0.42% a fill vs +0.8 expected; carry +$18.6 / +$16.3; capit2 / news / sleeve have not traded; v2 paper $213.73). His statement holds NASDAQ (46), gold (41) and silver (4) only - no currency pair.
- **`backtest/audit_event_only.py`** (sleeve + bids + capit2 + news + ndx as an account): CAGR +121%, fall 22%, 78% of months up, typical $300 year $644 / $711; loses to the deployed machine scaled to the same fall ($1,099 / $1,271). Steadier (2022 +143% vs +56%), not better. E1 right, E2 half, E3 wrong.
- **`backtest/audit_mn_vol_screen.py`** (drop the most volatile third from the MN ranking): every variant lowers Sharpe (both legs +1.27 / +0.72 vs base +1.38 / +1.36). Dead. The MN long leg earns +1.59%/wk on the tune half and -0.05% on the holdout; the short leg the reverse.
- **Verdicts given:** no buried book (doc 21 stands); high frequency closed by cost at retail (every signal 1-2bp vs 4-12bp); low capital = the event books (capit2 at $50+, crash bids at $200+) and the trader copy (Exness minimum 0.05 lot); his side not found in anything tested - forward since first contact 10 of 11 trades, 4 of 4 October races. A copy needs ~15 trades (~3 months) to confirm or kill. Not built; waits on the user (his trades since 10-13 from the app's History; whether his entries can be seen live).
- **Then the user: "I want something of my own"** -> a new mechanism tested at once, `backtest/paxg_weekend.py` (the gold token PAXG wanders while gold is shut at the weekend and snaps back at the reopen): the snap-back is real (a third of the move returns within 6h, both halves; weekday placebo zero) and too small - primary cell +0.17% a trade after 12bp, t 1.2 / 0.75, ~11 trades a year, ~+2% a year; 0 of 9 cells pass. Tests 9, no planted-bug round. Offered next (not built): an 'Event account' line on the dashboard = the main account's own forced-flow books as a $300 record of the user's own machine.
- **Then: "new strategy in crypto"** -> `backtest/oi_flush.py` (+ `oi_flush_check.py`): after an 8% day, long the coins whose open interest fell 10%+ (positions wiped out), +5% target / 96h, 13 coins on disk: +1.05% / +2.85% a trade (t 1.4 / 2.0), +1.26% / +2.24% over coins whose open interest rose; pooled t 2.07, 29 trades a year. A weak lead, NO PASS: no dose-response on the tune half, the holdout rests on 5 crash days, 2026 negative, survivor coins. The deepest third of drops bounces whatever open interest did (the capitulation book again). Tests 8. Open (the user's call): the same split on the PIT top-40, which needs Binance's metrics archive for ~100 symbols. Also checked: the news book's 0 trades in 24 days is not a bug - Binance posted none of its two notice types (2026 runs 1-7 a month; `events.parquet`).
- **Then "Yes, run it" (finished 2026-11-12 in a side session): the flush on the PIT top-40 with dead coins** - `backtest/oi_flush_pit.py` (+ `oi_flush_pit_check.py`, tests 11, 28 of 29 planted bugs, control survived; open interest for 27,521 symbol-days cached in `strategy_analysis/data/metrics_days/`, gitignored): **NO PASS**. 15,471 events, 70% splittable, FLUSH 14%: +0.30% / -1.01% a trade (t 0.7 / -1.0), worse than BUILD on the holdout; pooled -0.04%, worst -99%. The 13 coins still show it (+3.45% holdout) and the other coins lose (-1.52%): the 13-coin lead was a survivor effect. Kill. Doc 02 last entry.
- Both checks are audit scripts: no tests, no planted-bug round. Nothing deployed, committed or restarted. Trap met: the orderings' calendars differ by a day - a series indexed on ordering 0 leaves a NaN last day that `all_books.stats1` reads as -100% (align to each ordering's index).

### 2026-11-09 (options expiry and ETF flows) - the user: "it's not a new strategy, it's just old ones and their results" -> "test both": no pass; ETF flows dead; a small real dip into each monthly options expiry (`backtest/options_expiry.py`, `backtest/etf_flows.py`, doc 02 last entry)

- **Why these two:** after the Leads tab was (rightly) called bookkeeping, a repo search found two forced-flow sources with no test anywhere: crypto options expiry and the US spot bitcoin ETF flows (stablecoin supply growth had been tested - dead). Predictions registered in each file before its first run.
- **Results:** options expiry 0 of 24 cells; the 4 hours into a monthly expiry fall ~0.4-0.5% more than ordinary Fridays on both halves and both coins, held up under post-hoc checks (67% of 82 down, every year for BTC, strongest in the 07-08 UTC settlement hour, placebo a week earlier ~0, weekly expiries a smaller dip) - but a short nets only +0.23-0.33% a trade (t 1.8-1.9), ~+0.25% a month on the money used: a lead, not a strategy. The 4 hours after are 1.5x wilder (options territory). ETF flows: 0 of 4, no lead - flows chase the price (+0.43 same day, +0.37 past 5 days) and say nothing about the next day.
- **Checked:** tests 9 + 7; 28 of 28 planted bugs (two first survivors were gaps in my test data), control survived. Nothing deployed or committed. Adding the expiry dip to the forward ledger was offered and declined (the user: "No, leave it"): it stays a lead in doc 02 only, the ledger keeps its three pinned leads.

### 2026-11-09 (the forward farm) - the user: "Yes, plan the farm" -> "Yes, build it": a forward ledger for three leads and one Leads tab for every forward record; DEPLOYED 2026-11-09 ~09:27 UTC (commit `847b4bc`)

- **The plan's finding (chat):** a lead needs ~4 x its backtest years / its backtest t^2 of forward data to reach t = 2 on its own (at its full backtest edge; half the edge = 4x longer) - RSI-80 ~6 years, NASDAQ inside bar ~5 to beat random and 20+ to prove the profit, daily-zone shorts ~10 (corrected from ~5: the plan used a pooled sample), pre-FOMC ~6.5, gold payrolls ~11, FOMC break ~10, maker model ~7. A farm cannot confirm anything soon; it can reject a clearly wrong claim and keep every record in one place. Most leads need no live bot: their prices land in public history.
- **Built:** `backtest/forward_ledger.py` (gold payrolls straddle on Exness ticks, NASDAQ inside-bar buy and NASDAQ before the Fed on HistData minutes; each replay is the study's own functions - parity in `logs/forward_ledger_check.txt`: 889 trades +0.0792R, 128 statements +0.250% t +3.14, 8 of 8 2026 releases equal to `gold_news_ticks.csv`; REGISTRY_SHA256 / RULE_SHA256 pinned 2026-11-08 22:44 UTC before the 2026-11-09 00:00 UTC window; new data kept apart in `strategy_analysis/data/forward/`, the study files untouched). Left out, with reasons in its docstring: daily-zone shorts, the maker model, the FOMC break. First run: 0 forward trades (nothing has happened yet); next payrolls 2026-12-04 13:30 UTC, next Fed 2026-12-09 19:00 UTC. And `dashboard_push.leads` + `book_stats` + the Leads tab (`Dashboard.js` LeadsBoard, `fmt.js`, `globals.css` lead-cell): the machine vs its day-45 line, RSI-80, crowd squeeze, the sweet spot, crash bids, the news / NASDAQ dip / capitulation books inside the machine, and the ledger's three leads, each with its record, its backtest claim (file named), its registered line and a status word.
- **Bugs of mine found on the way:** pandas 3 parses date strings to [us], so `astype(int64) // 10**9` put every Fed statement in 1970 (the parity check found 0 of 128; `epoch_s` forces ns); the HistData refresh started one month late because the study file's last bar (Sep 30 23:58 New York) is stamped 1 Oct UTC, and skipped October. Both fixed before the pins.
- **Checked:** tests 10 (ledger, 22 of 22 planted bugs) and 44 (feed, 5 new; 17 of 17 planted bugs; two first survivors were gaps in my tests), do-nothing controls survived; `next build`; `dashboard_push.py` compiled with the VM's Python 3.10 (from stdin, nothing written on the VM); the tab previewed in a throwaway local copy on the VM's real feed (my generated password, files deleted, launch.json restored): 11 records, no console errors, no page overflow at 375 px. Nothing committed, deployed or restarted.
- **DEPLOYED (the user: "yes, deploy it"), commit `847b4bc`:** from a clean worktree on origin/main, with the three pinned study files the ledger imports (`gold_news_ticks.py`, `gold_news_breakout.py`, `inside_bar_break.py` and their tests - not in the repo before) and `logs/leads/` in .gitignore; secret scan clean; tests 10 / 44 / 42 / 42 in the clean copy; VM fast-forwarded from `f491caa`, 13 bot files byte-identical, service start times unchanged, nothing restarted, feed tests 44 on the VM, the feed builds 11 Leads rows; ledger.json copied to the VM over ssh (sha256 equal) - the route for every later run; Vercel 'Deployment has completed' 09:27 UTC; local main moved with `reset --soft` after proving the 12 files identical, other uncommitted work untouched. At deploy the main account was $261.50 live, $0.20 over its day-45 line. Was (to deploy): commit `backtest/forward_ledger.py`, `tests/test_forward_ledger.py`, `dashboard_push.py`, `tests/test_dashboard_push.py`, `dashboard/app/Dashboard.js`, `dashboard/app/globals.css`, `dashboard/lib/fmt.js` (+ the all-sources study files if wanted) from a clean worktree, push, VM `git pull` (feed only); then a route for `logs/leads/ledger.json` to the VM after each PC run (commit it, or copy it by ssh).

### 2026-11-09 (everything linked) - the user: "what would be the most efficient way to run countless combinations where there is a link between anything - indicators, news, market patterns, smart gambling" -> "Yes, part 1": one model fed every source finds information, not money (`backtest/all_sources_model.py`, doc 02 last entry)

- **The answer given first (chat):** not more enumeration - ~16,000 rule variants already run (counted from this log's big grids), and the luckiest of 10,000 unrelated no-edge strategies over 6.5 years shows a Sharpe of ~1.5; everything that survived here has a forced trader or a structural reason, every pure-pattern family died. Three parts offered: (1) ONE model fed every source, counted as one test; (2) the forced-trader events still untested (crypto options expiry is the one found); (3) a forward paper 'farm' of frozen leads. 'Smart gambling': sizing cannot turn a zero edge into money (one_shot, lottery_v2, wait_leverage). The user chose part 1.
- **Result (`logs/all_sources_model.txt`):** NO PASS (0 of 6 primary cells, Holm 1.00). Daily rank IC +0.10..+0.18 on both halves, but mostly one factor (calm / old / deep coins beat volatile / young ones in 2022-26: age and open interest / volume correlate -0.65 / -0.62 with atr_pct; the model with no price features scores the same); adding the other sources to price lifts IC -0.01..+0.02 and the paired spread is never t >= 2 on both halves. Post hoc: a planted clean IC 0.10 signal passes alone (net t +4.5 / +2.6), so the test can see a tradable link; the model's volatility sort fails because its short leg holds the squeeze-prone coins; with volatility removed IC +0.04..+0.07 remains and nets about the cost (t <= 0.7). Predictions A1 right, A2 wrong by a hair, A3-A7 wrong (in the file).
- **Checked:** 20 tests; 39 of 39 planted bugs caught over two rounds (first survivors: the fuel threshold, BTC's 7-day return, the 30-day liquidity window - gaps in my tests), control survived; the registered part of the log is identical over three runs; the data panel is cached in `strategy_analysis/data/all_sources_panel.npz` (gitignored, 168 MB, rebuild with `--rebuild`, ~70 s). Nothing deployed or committed; no bot or book touched.
- **Open (the user's call):** part 3, the forward paper farm (several frozen leads paper-traded at once, each with a dashboard card; a new book needs a doc 22 override, research stop date 2026-12-31 applies to new backtests), or part 2 (forced-trader events, e.g. options expiry).

### 2026-11-08 (the inside bar at a new high, and "a gold bot with bigger returns") - the user: "I want a working gold forex bot ... bigger returns, not petty", then their 'mother and baby candle' rule: no gold rule gives bigger returns; the pattern has no edge on gold; saved on "Save it" (`backtest/inside_bar_break.py`, doc 02 last entry)

- **Asked first (AskUserQuestion), answered 'both on one demo account' (the FOMC range-break + a gold trend); then the user said 'idc ... I want bigger returns, not petty'.** Two throwaway checks (scratch scripts, not in the repo; HistData XAUUSD): **gold at leverage is a coin flip** (11,378 random entries, 3-day cap: 100x doubles 43% / liquidated 44%, mean -1.6% of the stake a shot; 200x aiming for 5x 14% vs 72% liquidated; 10-20x nothing happens in 3 days) and **gold's daily trend peaks at 3x** (long above the 200-day average, swap-free: 1x +5.9%/yr fall 33%, 2x +10.0% / 57%, 3x +12.1% / 74%, 5x +9.7% / 93%, 10x and 20x ruined; 2010-19 alone 2-3%; ~5.9%/yr best with swap). Nothing was built: the answer given was that the bigger-return bots in this repo are crypto (the trend book / `micro_bot.py` lottery odds), not gold, and the question 'crypto instead or a gold lottery bot' was left open.
- **Then the user's rule** (30-minute bars, a new high, a big mother candle with an inside baby, short when the baby's low breaks, stop at the mother's high) was tested at once, 56 cells (gold 12 + 4 look-back checks + ten markets x 4), TOUCH and CLOSE fills, a matched random-entry control, 1-minute management. **Gold: TOUCH n 1,342, -0.23R a trade at 2R, CLOSE -0.10R, the control loses the same (excess t -0.9..+0.7); the mirror null; every short on seven forex pairs, S&P and DAX loses.** One pass: NASDAQ buy-side TOUCH (+0.08R, excess t +2.34 / +3.01); its CLOSE fill fails the bar (t +1.25 / +2.33), so it is a LEAD. Predictions T1 right for gold (wrong overall), T2 WRONG (the stop-order fill is the worse one on gold), T3, T4 right.
- **Checked:** 42 tests; 100 of 100 planted bugs caught over two rounds with a do-nothing control that survived (93 first; the seven survivors were gaps in my tests - the true-range gap terms, a baby-high check hidden behind the size check, an exact touch of the level, the control's time of day and day pools, its data-end guard and its entry-minute convention); one equivalent mutant (a redundant end-of-data guard). The module reproduces the exploratory run's 62 result lines exactly. Nothing deployed or committed; the working tree already held many other sessions' uncommitted files.
- **Open (the user's call):** whether to build the crypto go-for-broke bot or a gold lottery bot (demo only either way); whether to run the NASDAQ buy-side variant as a forward paper arm.

### 2026-11-08 (audit) - the user: "go through both sessions which tested gold and crypto, I think they didn't do their job right; and how can we improve the Analyst desk's signals": the gold verdict was wrong in its mechanism, the crypto studies stand, and the desk's sweet spot fails on its own history

- **Gold (`backtest/gold_news_ticks.py`, `logs/gold_news_ticks*.txt`):** the 'fill artifact' reading of the NFP straddle rested on 1-minute bars (the trigger minute's 34bp run treated as slippage, the bar's CLOSE treated as a stop fill). On MT5 Exness XAUUSDm ticks for the 2026 releases a resting +-5bp stop fills a median ~9-11bp past the level on NFP (0-6bp on CPI / FOMC) and the tick result tracks the LEVEL fill. Re-scored 2010-26 with 10bp entry slippage: NFP +-5 +11.1bp a trade (t 2.45; tune +13.4 / holdout +7.4, t 1.1); CPI (never tested before) dead; FOMC ~0. A weak lead, not an artifact, not a pass; the user's own description IS the straddle. Corrected: the s3 trap row, doc 02's gold entry, gold_news_breakout.py's docstring. The inside-bar study reused the flawed 'CLOSE must hold' rule; its NASDAQ cell stays a lead for the right reason (1 of 56 cells).
- **Crypto (`sweep_zone.py`, `sweep_zone_daily.py`):** no bug found (causal zones, matched controls, day-clustered t, PIT universe with dead coins, fees + funding). Two design choices cost ~17-18% of zoned sweeps (cooldown applied before zoning; 4h 2,315 -> 2,716, daily 726 -> 857; checking only the newest zone cost nothing) - not enough to change a verdict. The daily cells stay 'cannot tell'; untried power: the 2017-19 spot data and a wider universe.
- **Analyst desk (`backtest/analyst_replay_cuts.py`, `logs/analyst_replay_cuts.txt`; the replay's cached 10,580 calls, 2022-26, and the live log copied to `logs/analyst_calls_20261108.csv`):** the 'sweet spot' (stop >= 0.8%) loses -0.11R tune / -0.15R holdout per call (6,928 calls), hit below random in every year; no slice by stop, RR, rule, side, daily / 1000h trend or 24h momentum beats random entries. A real fault: XAU / QQQ calls made while the UNDERLYING market is shut gap through their stops (live 16 calls -17.8R, about two-thirds of the desk's -26.4R; replay QQQ -0.76R, XAU -0.84R a call). The crypto funnel count was a scratch script (re-derivable with sweep_zone's own functions).
- **Is the template blind? (the user: "there is a pattern in how you test them") - `backtest/blindness_check.py`, `logs/blindness_check.txt`:** a trader with KNOWN skill planted at the real sweep times (both sides of 60,529 events simulated, the arm-A bracket, real controls, the studies' own gate) and the desk's registered 30-bet score run on its replay with losers turned into winners. No bias (measured = planted R within 0.008R), 0% false alarms. Power: all sweeps catch +0.07R 100%; 4h-zoned +0.07R 12% / +0.15R 66% / +0.23R 98%; daily-zoned 0% at any size (100-trade rule; 2% at +0.31R on statistics alone); the desk's 30 bets pass +0.28R a bet 15%, +0.43R 35%, +0.89R 91%. A 24-hour direction caller must be ~58% right to break even on this bracket (55% = -0.006R). So the rare-setup nulls (zones, the desk's forward test) are 'cannot tell', not 'dead'; the big-sample nulls (every sweep, the desk's 6,928-call replay) stand. Predictions B1, B2, B4, B5 right, B3 consistent, B6 half wrong. Tests 9, planted bugs 16 of 16 (one first survivor, Holm's monotone step, fixed with a test), control survived.
- **The zones with more data (the user: "yes, more data") - `backtest/sweep_zone_more.py`, `logs/sweep_zone_more.txt`, doc 02 last entry:** the two studies' rules frozen on perps ranked 41-100 (2020-26) and spot 2017-19 (94,187 new sweeps): 0 of 8 judged cells pass. 4h zones pooled -0.04R long / -0.12R short with an MDE80 of +0.15R: dead at any tradable size. Daily-zone longs dead (-0.20R, t -2.1). Daily-zone shorts stayed positive (new C +1.12R n 49; pooled +0.72R t 2.7) but ~10 of 123 trades carry it (the 2025-10-10 crash, INJ, the 2024 alt bleed; without them +0.09R): a crash-tail lead, not a book. Tests 9, planted bugs 18 of 18, control survived.
- **An edge without capital restraints (the user: "liquidity sweep, indicators, whatever, I don't care") - `backtest/rsi80_more.py`, doc 02 last entry:** the RSI-above-80 4h momentum lead (rsi_ratio.py's one leftover) frozen on perps ranked 41-100 + spot 2017-19: +0.138R a trade, excess t 2.3, both halves positive, but day-vote t 1.80 < 2.0 - NO PASS, narrowly. The best 20 of 666 days carry it (trend-book shape). Real funding cheaper than charged; +30bp slippage -0.02R. Sized at 1% / 2% risk on the new coins: $100 -> $277 (+19%/yr, fall 26%) / $906 (+45%/yr, fall 48%); $20 cannot trade it (positions under $5). Tests 9, planted bugs 24 of 24. **Overlap (`backtest/rsi80_overlap.py`):** not the trend book (daily corr -0.04, its best days are ordinary trend days, +2%/month in the machine's worst months, 89% other coins), but as an add-on on unseen coins it loses to 'bet the machine bigger' on 2020-24 (-$791) and wins on 2024-26 (+$3,401): no pass. Only a forward record can say more.
- **Checks sooner (the user: "yes, check sooner") - DEPLOYED 2026-11-08 ~21:16 UTC, commit `f491caa`:** the paper book's first trade (JCTUSDT, 20:00 UTC) was booked at the bar's open 0.013213 but the job, running at :05, saw 0.01609 (+21.8%): on a pumping micro-cap the backtest's open fill may be far from what a bot gets. The timer now runs at :00:30 (AccuracySec 1s) so the logged 'seen' price measures that gap honestly; booked results, the registered lines and the verdict are unchanged (dated amendment in the docstring; F3 scored from here). Dashboard next-check follows (`next_4h_run` +30 s). Tests 39 / 15, all three Python files compiled with the VM's 3.10 first, VM pulled + timer reinstalled (next 00:00:30), bots byte-identical.
- **The Momentum book on the dashboard (the user: "I don't need a command to check, add it to the dashboard") - DEPLOYED 2026-11-08 ~18:29 UTC, commit `ff4d621`:** a top-bar link and a tab (`Dashboard.js` MomentumBook) fed by `dashboard_push.momentum()` (balance with open BOOKED trades at Binance's live price, open trades with stop / target / R so far / hours left, closed trades, record vs the registered lines taken from rsi80_paper itself, the balance curve in the chart's {d, h} shape with one point per instant); `rsi80-paper.timer` added to the health list. Found in the local preview: the chart was blank because EquityChart wants `curve = {d, h}`, not a list - fixed before the push. Tests 39 (3 new), 11 of 11 planted bugs, `next build`, preview on the VM's real feed and a sample (desktop + 375 px, no overflow, no console errors; throwaway password and files deleted, launch.json restored); both Python files compiled with the VM's 3.10 first. VM pulled (bots byte-identical, nothing restarted); Vercel 'Deployment has completed'. The live page itself was not opened by me.
- **The RSI-80 momentum PAPER book (the user: "yes, record it") - DEPLOYED 2026-11-08 18:16 UTC, commits `7ac483c`, `5f40d3e`, `c33bed7`:** `rsi80_paper.py` (standard library, public Binance futures data, no keys, no orders; $300, 1% of booked equity a trade, real funding; top-100 perps by prior month's volume; 4h RSI(14) up through 80 -> long, stop 4 ATR, target 4R, 24 bars), `deploy/rsi80-paper.{service,timer}` (every 4h at :05 UTC), doc 22 override, registered lines in the docstring (KILL 2027-01-31 under -0.24R with 30+ trades; verdict 2027-04-09: held up >= +0.072R and the book above $300, dead under -0.107R, else extended to 2027-10-09). `tests/test_rsi80_paper.py` 15: the live loop replayed over the real 4h history of SOL / DOGE / LINK / AVAX reproduces every backtest trade (entry, exit bar, R); 27 of 28 planted bugs caught (1 equivalent; the first round's 6 survivors were gaps in my tests: holes behind a signal, the 0.2% floor, a gap past the target, the forming bar, unbooked exits). **Trap met: the VM runs Python 3.10** - a nested same-quote f-string that 3.12 accepts failed the VM's test run before anything was installed; fixed, and both files compiled with the VM's Python before the second push (compile with the VM's interpreter before pushing). VM: 12 service files byte-identical, nothing restarted, first run by hand (top 100 of 516, no signal), timer enabled; local main moved to `c33bed7`, other uncommitted work untouched; STATUS.md re-verified.
- **The fix (the user: "yes, fix it", then "deploy it") - DEPLOYED 2026-11-08 ~16:11 UTC, commit `f921ca8`** (four files from a clean worktree on origin/main, secrets scan of the added lines clean, tests re-run there; VM fast-forwarded from `3cd87d8`, 12 service files byte-identical, no restart - the desk and the feed run on timers; tests 31 / 36 / 8 on the VM; the VM's feed preview lists only crypto on Sunday; a desk cycle in a temp folder on the VM logged 'market shut, no calls: XAUUSDT QQQUSDT'; local main moved to `f921ca8` after proving the four files identical, the other uncommitted work untouched; STATUS.md re-verified). What was built: `analyst.py` `market_open` / `can_call` (US daylight-saving rule written out, no tz database; gold Sunday 18:00 - Friday 17:00 New York less 17:00-18:00 daily; QQQ 09:30-16:00 New York; NYSE holidays and early closes to 2027-12) - no call on XAUUSDT / QQQUSDT unless the market is open at the run AND at the start of the candle read; levels still drawn; recorded as a dated AMENDMENT in the docstring (post hoc, earlier calls count as before). `dashboard_push.watch_items(symbols, next_run)` leaves those two out of the 'coming' preview when the next run cannot call them. Effect: live, 15 calls (1 win, -16.6R) would have been blocked, the other 80 are -9.7R; replay re-run with the gate: gold -94.1R -> -66.9R, QQQ -126.8R -> -18.9R. Not changed: calls made in session can still be HELD across a closure. Tests: test_analyst 31 (5 new), test_dashboard_push 36 (1 new), sweet-spot 8; planted bugs 22 of 22 non-equivalent caught (2 more equivalent: a Sunday / Friday boundary moved inside the daily break), do-nothing control survived (exit-code harness). To deploy: commit `analyst.py`, `dashboard_push.py`, `tests/test_analyst.py`, `tests/test_dashboard_push.py` from a clean worktree on origin/main, VM `git pull` (both run on timers, no restart).

### 2026-11-08 (gold around NFP and FOMC) - the user: "that's bullshit, many traders are doing it live, you are not looking rightly" (after being told a release's first seconds are not reachable by a retail order; the idea: wait, then trade gold's break of a level): tested properly, then saved on "Save it" (`backtest/gold_news_breakout.py`, doc 02 last entry)

- **Run:** NFP (199 events, 08:30 New York) and FOMC (108 statements, 14:00, 2013 on) on gold's HistData BID minute bars 2010-2026; three rules (follow the move 1 / 2 / 5 min after; break the first 5 / 15-minute range - the user's rule; a +-5 / 10 / 20bp straddle) x LEVEL / CLOSE / EXTREME fills for the stop entries, each against the same New York clock time on every other weekday; PASS = net > 0 with excess t >= 2 on both halves. P1-P3 were stated in the chat before the first run (they are in the file). The three fill models were added AFTER the first run, when the NFP straddle read +20bp (t +5): the file's AMENDMENT paragraph says so (cells 11 -> 21 per event type).
- **Result (doc 02 has the table):** the move is real (median release-minute move 24.6bp NFP / 16.4bp FOMC vs 3.3 / 1.3 at the same clock time on ordinary days; the biggest 1-minute move sits in the release minute in summer AND winter - no clock error); the two passes are the straddle at LEVEL fills and nothing else - the trigger minute runs a median 34bp past a 5bp level, and at the bar's close the same straddle is -2.8bp, at its worst price -11.4bp (new row in s3). The user's rule: NFP -3.7 / -5.8 / -10.9bp (level / close / extreme), no better than ordinary days; FOMC +9.8 / +9.0 / +4.4bp (t 2.29 / 2.29 / 1.73 pooled, 2.05 / 1.27 by half at the close fill, 1 of 42 cells, 2 x se about 13bp): a LEAD that needs about 200 events (roughly 25 years of meetings). Follow the move: NFP +1.6 .. +4.4bp net at +1 / +2 minutes (excess t up to +2.2, never both halves), -3 .. -5bp from +5 minutes: gold_focus.py's 'following later loses' stands from +5 minutes, the first two minutes are a small borderline continuation.
- **Predictions:** P1 (follow about zero) PARTLY WRONG, P2 (the break has no significant excess) RIGHT by the registered rule, P3 (under 10% anything clears) RIGHT once the fill is realistic. I had told the user 'following later loses' and 'the retail-safe response is not to predict it' before running anything; the run corrected the first to 'from +5 minutes on'.
- **Checked:** 42 tests; 41 of 41 planted bugs caught over two rounds with a do-nothing control that survived (the first round left 15 alive, all gaps in MY tests: hold and exit times indistinguishable on flat price paths, boundary touches, short-side stops, unequal sample sizes); one mutant is equivalent at the rule level (the stop IS the opposite trigger) and is pinned through `enter()` directly. The refactored module reproduced the exploratory script's 60 output lines exactly. Two of my own tests were wrong first (a fixture whose tail jump was itself a break; an exit price equal to the stop) and were fixed before the second round.
- **Limits:** bid-only bars (the release spread is a constant: 2.44 + 0.5bp, +2bp for stop entries), no tick data before 2026 so the first seconds are untested here (`fx_news_seconds.py`: +6bp at 0.5-1s on FX pairs, gone by 2s), the fills are three bounds not a model, 199 and 108 events are few. Nothing deployed; no bot, book or doc 22 line touched; the working tree already held many other sessions' uncommitted files, so nothing was committed.

### 2026-11-09 (market profile on NQ) - the user: "heat map, time and sales, gamma, volume profile, market profile, footprint, delta, order flow, VWAP, auction market theory - did we check all of them?" -> "run the market profile test on NQ": 0 of 9 cells pass (`backtest/nq_profile.py`, doc 02 last entry)

- **The audit first (answered from the repo):** heat map / book = book_hist.py (7 DOGE days), wall_persistence.py, order_flow_lab.py, his_fullbook.py (CME book at one trader's clicks); time and sales = his_tape.py, order_flow_lab.py; delta / footprint / absorption = his_cme_scan.py, his_absorb.py, es_flow_mended.py; gamma = his_gex.py (QQQ open interest, at one trader's clicks) plus the VIX / VXN proxies in nasdaq_regimes.py; volume profile = his_volprofile.py (tick counts at one trader's clicks); VWAP = daily reversion (small, the capitulation buy again), NQ published VWAP trail (-0.02bp), DOGE VWAP fade. Market profile / auction market theory as stand-alone rules were NOT tested, hence this study.
- **Run:** nine cells on the prior session's TPO profile (primary) and real-volume profile (plateau) of 4,016 NQ cash sessions, matched-day control, 1.27bp, gate as in the file (net > 0 on both halves, excess > 0 on both halves, holdout Holm p < 0.05, >= 100 holdout trades, plateau). **0 of 9 pass, no LEAD.** The 80% rule's far-edge touch is 47.6% | 43.5% against 43.4% | 44.2% for the same trade on random days; 65% of sessions open outside the prior value area. The one number that stands out is R7 (open drive) +15.6bp on the holdout only (t 1.7, 120 trades, tune +0.4bp, Holm 0.34). Predictions M1, M4-M7 right, M2 half right, M3 wrong.
- **Checked:** 39 tests, 98 planted bugs caught over three rounds (88 of 96 first: eight survivors, all gaps in my tests; then 96 of 97; then the last two), control survived. Limits and what is not tested (Globex profiles, single prints, composite profiles, other markets) are in the file and doc 02. Nothing deployed; no bot, book or doc 22 line touched.

### 2026-11-08 (later) - the daily-zones version: "try the daily zones version" -> "run the daily zones test now": 0 of 6 cells pass, the zone cells are too small to say anything (`backtest/sweep_zone_daily.py`, doc 02 last entry)

- **What it was:** the second try at the sweep + zone + trend idea after the 4h result, with DAILY zones (base day + a 1.5 ATR impulse day, first retest + 72 hours) and a target at the NEXT opposite zone (taken only if >= 1.5R away), a separate file with its own registered rules (prior 4% that any cell passes) and tests; `sweep_zone.py` was not edited.
- **Result (`logs/sweep_zone_daily.txt`):** 60,390 sweeps; zoned 726 (1.2%, 110 a year); 286 with a next-zone target (43 a year, median 7.3R away so hit rates are 0-16%); 130 with the daily trend. **0 of 6 pass.** Arm A (every sweep) loses again (net R long -0.11 / -0.20, short -0.06 / -0.06). Arms B and C are positive on the short side (+0.21..+0.52R) and mixed on the long, every |t| <= 1.9, and **all four are UNDERPOWERED** (25-94 trades a half, se 0.3-0.5R). The zone information spread (T24) is positive on all four halves (+0.16..+0.47%) and not significant (t <= 1.0); the trend inside zones flips (+1.97% tune, -0.01% holdout). Z3 (plain 3R) short holdout +0.29R, excess t +2.8, is one of ~16 diagnostic cells.
- **Reading:** 'cannot tell' for the zone arms - at 43 target trades a year the idea cannot be proven or killed with the data there is (~4 more years for 100 holdout trades a side; ~9+ months of live paper for 30 bets). Chart-pattern family overall (sweeps, levels, 4h and daily zones, confluence): no measured edge after fees. Predictions D1, D3, D4, D6, D8 right, D2 half wrong, D5 wrong (a 25-trade cell), D7 right and bigger than expected.
- **Checked:** `tests/test_sweep_zone_daily.py` 32 tests; 60 of 60 planted bugs caught in two rounds (52 of 60 first: eight survivors, each a gap in MY tests - supply / target-index breaks tested only with closes that breached both edges, no downside dip in the control hours, no declustering test, a loose assertion; then 60 of 60), the do-nothing control survived. Nothing deployed; the desk, its pick rule and the dashboard are unchanged. No bot or book touched.

### 2026-11-08 (sweep + zone + trend) - the user: "what do you think about liquidity plus HTF S and D zone together, all three" -> "yes run it": registered, tested, run; 0 of 6 cells pass (`backtest/sweep_zone.py`, doc 02 last entry)

- **Verdict given first (before building, per the low-prior rule):** logical, popular, untested here in its real form (the repo had tested sweeps, levels, trend filters and fair value gaps, never a supply / demand ZONE); prior ~6% that any arm passes; the cheapest honest test was one rule, written first, three arms (A every sweep, B zoned, C zoned + daily trend), matched random-hour controls. The user said 'yes run it'.
- **Result (`logs/sweep_zone.txt`):** 60,601 sweeps, 2,323 zoned (3.8%, 351 a year), 1,352 with the trend agreeing; **0 of 6 gate cells pass.** Arm A (all sweeps) net R long -0.10 / -0.19, short -0.05 / -0.07 (tune / holdout), no excess over the control; B (zoned) long +0.01 / -0.26 (holdout t -3.5, excess -0.21R), short -0.14 / -0.00; C (zoned + trend) long -0.05 / -0.23, short -0.07 / +0.06 (t +0.5). The zone adds no information (T24 spread long -0.03% / -0.38%, holdout t -2.1; short 0.00% / +0.08%); the trend inside a zone is a small positive spread (+0.33..+0.46% on three of four halves, t 0.8-1.2, not significant). Hit rate at 3R 14-19% vs the controls' 16-20%.
- **Reading and limits:** stacking removes 96-98% of the sweeps without improving the odds of the rest; consistent with `sweep_confluence.py` (0 of 14 filters), the desk's SR bounce (22% hit) and the desk's wide-stop pocket (which zones do not explain). Not found in THIS definition (one base bar, first retest within 24h, 4h zones, one trend rule, a 3R target); the holdout standard error is ~0.07R and the fee 0.05-0.06R, so an edge under ~+0.15R could not have been seen; the holdout is the shared, much-read one. Predictions Z1, Z3, Z4, Z6, Z8 right, Z2 half wrong (the long holdout spread is -0.38%, worse not flat), Z5 untestable (61 opposite-zone events), Z7 wrong on the share (3.8% vs 5-20%).
- **Checked:** `tests/test_sweep_zone.py` 44 tests; 43 of 43 planted bugs caught over three rounds (37, 42, then the last confirmed alone), the do-nothing control survived, 2 survivors redundant by construction; the harness is scratch (judged by exit code). The first round's survivors were all gaps in MY tests (a break at the wrong edge, gate clauses not isolated), not in the study. Nothing deployed; the desk, its pick rule and the dashboard are unchanged. No bot or book touched.
- **Same day, earlier:** the simple Analyst tab was DEPLOYED (next entry); the AI-key idea and 'can I make money following the signals' were answered in chat (next entry).

### 2026-11-08 (the Analyst tab made simple) - the user, looking at the live tab: "the analyst desk is so confusing with loads of bullshit; there should be simply one what is analyst desk and its edge, second the best combination signals (liquidity sweep etc.); a normal person cannot open a trade": the tab is now three blocks; built, tested, previewed locally, then DEPLOYED on "deploy the simple tab now" (commit `3b38602`)

- **What was wrong:** the live Analyst tab was ten cards and 9,067 px tall (paper book, sweet-spot tables, a 'coming' table, levels, a ladder, open predictions, a what-if, record by rule, recent calls) with the order panel buried inside the sweet-spot card.
- **What it is now (`DeskIntro`, `SignalNow`, a closed `<details className="more">` in `AnalystDesk`, `dashboard/app/Dashboard.js`):** (1) 'The Analyst desk, in plain words': what it is (a robot chart-reader, 7 markets, three setups in plain words, play money, no order button) and 'Does it have an edge? Not proven' with three bullets read from the feed: the whole record (95 finished, 23% hit, 31% needed, -0.28R each), the one pocket that looks good (stop >= 0.8%: 13 of 34, +0.50R; liquidity sweeps inside it 10 of 18; tiny stops 1 of 21) and why it is not trusted (14 independent bets, found after looking, the fair test has 1 bet at -1.09R so far); (2) 'Signal now': the next-check countdown, the status badge, and the existing order panel (the bot's pick, balance and risk, the six-line ticket) with a new 'How to place it (Bitget app or website)' five-step list (Futures > USDT-M > pair; Isolated and the leverage; Market order, Buy / Long or Sell / Short, size in coins and in USDT; TP/SL prices; skip it if the price already passed the stop or target); (3) everything else behind one button 'Full details: the paper book, record, charts and every open call'. The leverage list is now collapsed ('Want more leverage? See what each level does', the typed-leverage box moved inside it, 'Back to the bot's suggestion' sits in the ticket's leverage row). No logic, feed, bot or book change: the pick rule (`todaysPick`) is unchanged, so the card does NOT prefer liquidity sweeps - it shows the newest sweet-spot call that is still worth entering; the sweep-first cut would be one more slice after looking and was not made.
- **Checked:** four suites pass (sizepanel 24, sizer 5, dashboard 35, sweet-spot 8; the change is JSX and CSS, so no new test applies and no planted-bug round was run); `next build` passes (page 24.4 kB); in a throwaway local copy on a fresh feed from the VM (my generated test password, deleted; server stopped; `.claude/launch.json` restored): the tab is 2,710 px closed (about 3,580 px at 375 px wide) instead of 9,067, three blocks; 'Use 10x' moves the ticket and step 2 to 10x and shows the back button; 'Full details' opens with the 7 old cards and closes; no horizontal overflow at 375 px. The no-pick state was not re-rendered this time (its text is unchanged since 2026-11-07).
- **Desk facts read while checking (feed of 2026-11-08 ~11:10 UTC, `dashboard_push.py --print` on the VM):** the pick the user was shown, XRP long #93, was STOPPED OUT at 02:33 UTC on 11-07 (-1.09R, about -$0.11 on $10 at 1%); the forward test stands at 1 of 30 bets, average -1.09R; XAU long #99 lost -3.27R (a gap through its stop); the wide-stop pocket moved from 13 of 28 to 13 of 34 (six new calls, no win); the desk now has an XRP long #98 (sweep, stop 1.22%) as the pick. Open calls: #95 BTC long scalp-sized, #96 ETH long mid, #97 SOL long mid, #98 XRP long sweet.
- **Deployed (2026-11-08, the user: "deploy the simple tab now"):** `dashboard/app/Dashboard.js` and `dashboard/app/globals.css` only (every page hunk inside `SizePanel`, `SweetSpot`, `AnalystDesk` and the three new components; secrets scan clean; the four suites re-run in the clean copy: 24 / 5 / 35 / 8), from a clean worktree on origin/main, commit `3b38602` pushed to main (Co-Authored-By line). The VM was NOT touched (page + styles only); it stays at `3cd87d8`. Local main moved to `3b38602` with `reset --soft` after proving the two working files identical to the commit (nothing discarded; 153 other uncommitted entries untouched). **Vercel: 'Deployment has completed'** (GitHub commit status of `3b38602`, 2026-11-08 11:24 UTC; pending at the first read, success on the next). The live page itself was not opened by me (production password rule).
- **Asked the same day, answered in chat, nothing built:** (1) 'use a free AI key to analyse the probability' - verdict: free tiers exist (Gemini via AI Studio, Groq, OpenRouter `:free`; limits unverified and disagreeing between sources) and the volume is tiny, but an LLM cannot give a trustworthy probability (it sees only the desk's own numbers, chart-reading is what the desk measures at a loss, and the page already shows measured odds); honest uses are a plain-English explainer and a PRIVATE scored experiment (log its probability before the outcome, compare Brier score against the base rate over the next 30 ideas; my prior under 10% that it beats it); a key would be installed by the user with a hidden-input script on the VM, never pasted in chat, in a separate script that does not touch `analyst.py`; the user has not yet said yes or chosen a provider. (2) 'can I make money following the signals' - answered from `backtest/analyst_tiers.py` on the 11-08 log (95 resolved): all calls 23% hit vs 31% needed, -0.28R, a $20 account at 1% risk +2% in ~12 days; the wide-stop pocket 13 of 34 (38%, +0.50R, likely range 18-64%, post hoc) +17% on $20; the fair test 0 of 1 (-1.09R); today's pick #98 pays 1.75R and needs 40% to break even (random entry 23%); not financial advice, an experiment at $10-20 and 0.5-1% risk, no extra money before the 30-bet test (~early December).

### 2026-11-07 (leverage guide) - the user: "sometimes if I want to up the leverage it should suggest me": the ticket now lists what each leverage does; built, tested, previewed locally, then DEPLOYED on "deploy it" (commit `c4231db`)

- **What it adds (below the ticket's safety line):** 'Want more leverage? Here is what each level does': one row per option - the bot's suggestion, 5x, 10x, 20x and the highest safe leverage (`leverageGuide` in `dashboard/lib/sizepanel.mjs`; only options inside the safe ceiling and that fit the balance) - each with the money it locks (and its share of the balance), how far away liquidation sits, a Safe / Close badge, and a 'Use Nx' button; the row in use is highlighted ('in use'); 'Back to the bot's suggestion' appears when a typed leverage is in force. Plain lines say that higher leverage only locks less money and moves liquidation closer, that the loss at the stop and the gain at the target stay exactly the same, that 'Safe' only means the stop-loss triggers before liquidation, not that the trade wins, and that above the ceiling liquidation would sit under twice as far as the stop.
- **Checked:** `tests/test_sizepanel.py` 24 tests (4 new: the options by hand, only safe options that fit, the ceiling and the wide-stop case); planted-bug check on the guide 7 of 7 real mutants caught, the do-nothing control survived (file restored); sizer 5, dashboard 35, sweet-spot 8 pass; `next build` passes (page 22.8 kB). Server-rendered from the VM's feed (XRP long, $10: 3x suggested locks $2.20, liquidation 32.8% away; 5x $1.32 / 19.5%; 10x $0.66 / 9.5%; 20x $0.33 / 4.5%; 30x highest safe $0.22 / 2.8%; hand-consistent with the ticket). In a throwaway local copy (my generated test password, deleted; server stopped; `.claude/launch.json` restored): 'Use 10x' moves the ticket to 10x ('Your setting', liquidation 1.0742, 9.5%) and highlights that row; 'Back to the bot's suggestion' returns to 3x; a typed 45x (saved from earlier testing) correctly shows Close with no row highlighted and the back button; at 375 px each row is a single column, no horizontal overflow.
- **Deployed (2026-11-07, the user: "deploy it"):** `dashboard/app/Dashboard.js`, `dashboard/app/globals.css`, `dashboard/lib/sizepanel.mjs`, `tests/test_sizepanel.py` only (every page hunk inside the import and `SizePanel`; secrets scan clean; the four suites re-run in the clean copy: 24 / 5 / 35 / 8), from a clean worktree on origin/main, commit `c4231db` pushed to main (Co-Authored-By line). The VM was NOT touched (page + styles + logic only); it stays at `3cd87d8`. Local main moved to `c4231db` after proving the four working copies identical to the commit (a plain fast-forward refused over the four modified files, so the branch pointer was moved with `reset --soft` and the four paths re-synced; nothing discarded, 153 other uncommitted entries untouched). **Vercel: 'Deployment has completed'** (GitHub commit status of `c4231db`, 2026-11-06 22:39 UTC). The live page itself was not opened by me (production password rule).

### 2026-11-07 (the size panel as an order ticket) - the user: "I open the desk with $10 and the coin it recommends (XRP long now); I cannot understand how much leverage is safe or what 'room to spare' means, and I cannot see where it says to open at this price and this stop": the panel now gives an ORDER TICKET with a suggested leverage and a plain safety line; built, tested, previewed locally, then DEPLOYED on "deploy it" (commit `cdf5440`)

- **What was wrong:** the panel printed six number boxes; the entry, stop and target PRICES were only small grey text in the pick box; leverage was a bare box defaulting to 5; the safety result read 'Room beyond your stop: Room to spare'. Nothing said 'do this'.
- **What it shows now (below the pick, after any warnings):** 'If you take this trade, this is what to enter on the exchange': 1 Direction (LONG (buy) / SHORT (sell) XRP/USDT perpetual futures, in plain words what the bet is); 2 Entry price (about the price now, with the desk's logged price beside it, or the logged price); 3 Leverage (the bot's suggestion, with the plain fact that leverage does NOT change what is lost at the stop-loss, only how much money is locked and how close liquidation is, and the safe ceiling); 4 Position size ($ and coins, and the margin it locks); 5 Stop-loss at <price> (percent below / above the entry, and the dollar loss and its share of the balance, fee included); 6 Take-profit at <price> (percent, dollar gain, times the risk). Then one plain line with a badge: Safe / Close / Danger and where liquidation (the exchange force-closing the trade) would be. The pick box no longer repeats the levels; the risk box is worded 'Most you accept losing if the stop-loss hits (% of balance)'.
- **Suggested leverage (`recommendedLeverage` in `dashboard/lib/sizepanel.mjs`):** the leverage box is EMPTY by default and means 'the bot's suggestion': at least 3x, enough to keep the margin at or under half the balance, never above the highest leverage that keeps liquidation twice as far as the stop (`maxLev`); it says 'Too big for your balance' when even that leverage cannot carry the position. A typed leverage overrides it (and keeps the Close / Danger and not-enough-balance warnings). The position and the loss at the stop do not depend on leverage (tested). The saved settings key was bumped to `sizepanel.v2` so an old saved leverage of 5 is ignored.
- **Checked:** `tests/test_sizepanel.py` 20 tests (2 new: the suggestion by hand and on the real XRP numbers); planted-bug check on the new rule 4 of 4 caught, the do-nothing control survived (the earlier 15 on the pick logic still hold); sizer 5, dashboard 35, sweet-spot 8 pass; `next build` passes (page 22.2 kB). Server-rendered from the VM's feed (BNB pick, $20: $12.56, 3x, margin $4.19, stop 682.5952 -> -$0.20, TP 722.56 -> +$0.52, liquidation 465.33, hand-checked). In a throwaway local copy (my generated test password, deleted; server stopped; `.claude/launch.json` restored) with the user's own scenario: $10, XRP long as the pick -> LONG (buy) XRP/USDT, entry about 1.1870, leverage 3x (suggested), size $6.60 (5.56 XRP) locking $2.20, stop-loss 1.1704 (-$0.10), take-profit 1.2813 (+$0.52, 5.7x), Safe (liquidation 0.7973, 32.8% away); a typed 100x -> Danger ('use 30x or less'), 45x -> Close. Phone width: the first layout was cramped (label column took half the width); on small screens the label now sits above its value; no horizontal overflow at 375 px.
- **Deployed (2026-11-07, the user: "deploy it"):** `dashboard/app/Dashboard.js`, `dashboard/app/globals.css`, `dashboard/lib/sizepanel.mjs`, `tests/test_sizepanel.py` only (every page hunk inside the import and the size panel; secrets scan clean; four suites pass), from a clean worktree on origin/main, tests re-run there, commit `cdf5440` pushed to main (Co-Authored-By line). The VM was NOT touched (page + styles + logic only); it stays at `3cd87d8`. Local main fast-forwarded to `cdf5440` after proving the four working copies byte-identical to the commit; 153 other uncommitted entries untouched. **Vercel: 'Deployment has completed'** (GitHub commit status of `cdf5440`, 22:26 UTC). The live page itself was not opened by me (production password rule). Still not built: alerts (deferred by the user), a balance button, a demo-order button; a real-money order button will not be built by the assistant.

### 2026-11-07 (the size panel made simpler: the bot picks) - the user: "this is so confusing, why should I choose between support / resistance, liquidity sweep or whatever, the bot should choose for me": the panel now opens on ONE pick; built and tested locally, then DEPLOYED on "deploy it" (commit `c5030fd`)

- **The complaint was right:** the 'Trade to size' dropdown listed every open desk call with the rule's jargon ('Liquidity sweep', 'Support / resistance'), which read as 'choose a method'. The bot (the desk) already chose; the list only held the other open ideas.
- **What changed:** the panel opens on 'The bot's pick' described in plain words (`plainSetup`: e.g. 'price dipped under the lowest low of the last 24 hours and snapped back above it'), with the logged price, the stop and the target as percentages, the badge 'counts in the forward test' or 'made before the test began, not scored', and a one-line 'why this one'. The other open calls and 'type my own trade' sit behind a button ('Size a different call or type my own trade'); the dropdown no longer shows method names; a choice made there is NOT remembered (the panel always opens on the pick; balance / risk / leverage still are) and the heading then reads 'Your choice' instead of 'The bot's pick'.
- **How the pick is made (`todaysPick`, `liveFromHere` in `dashboard/lib/sizepanel.mjs`):** the newest open sweet-spot call (stop >= 0.8%) that is still worth entering FROM THE PRICE NOW and that counts in the forward test; failing that the newest such call that does not count; failing that no pick (with the reason: no sweet-spot call open, or the open ones are no longer worth entering). 'Still worth entering' = the desk's own from-here 1.5R floor holds (`sw.valid`), the price is not at or past the stop or the target, and the stop is not already scalp-sized (< 0.4%) from the price now. Middle and scalp-sized calls are never the pick. It is a rule, NOT a claim that the pick will win (the forward test stands at 0 of 30 bets) and the text says so.
- **Found on the live feed while building it:** the XRP call that counts in the test (#93) was still open with the price only 0.31% above its stop; sized 'at the price now' it gave a 2.3x position and a flattering 29x reward-to-risk, the exact scalp-sized shape where the desk has won 1 of 19. A pick that ignored the price would have shown it as 'the bot's pick'. Now it is skipped (the pick that day was BNB long #89, before the test, not scored) and the panel carries a 'Scalp-sized stop' warning for ANY choice whose stop is under 0.4% from the entry ('the desk's calls with a stop under 0.4% have won 1 of 19').
- **Checked:** `tests/test_sizepanel.py` 18 tests (6 new: the pick, the 'price ran through it' cases for longs and shorts, the plain wording, the scalp flag); planted-bug check 15 of 15 real mutants caught, the do-nothing control survived (the first run of the earlier set of 7 also passed); sizer 5, dashboard 35, sweet-spot 8 pass; `next build` passes (page 21.5 kB); the REAL component server-rendered from the VM's feed; in a throwaway local copy (my generated test password, deleted; server stopped; `.claude/launch.json` restored) three feed states: the counting XRP call alive -> it is the pick ('counts in the forward test'); the real feed -> BNB (older call, 'not scored'); every call dead from here -> 'no pick' with the reason and no numbers; the other-choices button and by-hand mode work; the scalp warning shows for XRP at the price now; at 375 px no horizontal overflow. One slip found and fixed in review: the heading said 'The bot's pick' for a call the user chose.
- **Deployed (2026-11-07, the user: "deploy it"):** files `dashboard/app/Dashboard.js`, `dashboard/app/globals.css`, `dashboard/lib/sizepanel.mjs`, `tests/test_sizepanel.py` only (every page hunk inside the import and `SizePanel` plus its one-line placement; secrets scan clean; four suites pass), from a clean worktree on origin/main, tests re-run there, commit `c5030fd` pushed to main (Co-Authored-By line). The VM was NOT touched (page + styles + logic only; the feed already carries the fields the pick reads: `sw.valid`, `sw.stop_pct`, the open calls' `mark`); it stays at `3cd87d8`. Local main fast-forwarded to `c5030fd` after proving the four working copies byte-identical to the commit; 153 other uncommitted entries untouched. **Vercel: 'Deployment has completed'** (GitHub commit status of `c5030fd`, 21:46 UTC, about a minute after the push). The live page itself was not opened by me (production password rule). Alerts, the balance button and a demo-order button are still not built (alerts deferred by the user).

### 2026-11-06 (the size panel) - the user: "build the size panel": built, tested, previewed locally, then DEPLOYED on "deploy it" (commit `af5d6e7`, page + styles + two new files; the VM was not touched)

- **What it is:** a "Size a trade" panel inside the Analyst tab's sweet-spot card (between the open calls and the 'Coming' table). Inputs: futures balance, risk %, leverage, which trade (an open desk call - sweet-spot ones first, the one that counts in the forward test pre-selected - or 'by hand': side, entry, stop, optional target), entry at the price now or at the desk's logged price; chips for $10 / $20 / $50 / $100 / $300 and 0.5 / 1 / 2%. Outputs: position size ($, coins, times the balance), margin, the loss if stopped (fee included), the gain at the target and the reward-to-risk, the liquidation price and its distance, the room beyond the stop and the highest leverage that keeps liquidation twice as far as the stop. Warnings: under the $5 minimum order (and the risk % that would reach it), not enough balance (the lowest leverage that fits), cut to 3x the balance by the desk's rule, too much leverage (liquidated before the stop), price already past the stop or the target. A note that these are estimates, that the calls are unproven (the test's bets so far) and that nothing on the page can place an order. Inputs are remembered in the browser only (localStorage, wrapped in try / catch).
- **Files:** `dashboard/lib/sizepanel.mjs` (new: `parseNum`, `levelsFor`, `buildSizing`, `fmtQty`; on top of the unchanged `size.mjs`), `dashboard/app/Dashboard.js` (`SizePanel` and one line in `SweetSpot`), `dashboard/app/globals.css`, `tests/test_sizepanel.py` (12 tests: the real JavaScript run by node against hand arithmetic). Planted-bug check: 20 of 20 real mutants caught and the do-nothing control survived (judged by exit code; three 'caught' lines printed a decoding message from my checker reading a failing test's output, not a test problem).
- **Checked:** the four related suites pass (sizepanel 12, sizer 5, dashboard 35, sweet-spot 8); `next build` passes (page 17.4 -> 20.3 kB); the REAL component server-rendered against the VM's current feed (call #93 pre-selected: $20, 1%, 5x -> $15.39 position, $3.08 margin, -$0.20 at the stop, +$1.24 at the target, liquidation 0.9534, room 16.5x, up to 34x) and re-derived by hand. In a throwaway local copy (my own generated test password, deleted afterwards; server stopped; `.claude/launch.json` restored): $10 at 0.5% shows $3.85 and the under-$5 warning (0.65% needed); 100x shows 'Liquidated before the stop' and 'use 34x or less'; a by-hand short (entry 100, stop 101.6, target 92; $10, 2%, 5x) -> $11.63, $2.33 margin, -$0.20, +$0.92, liquidation 119.50, up to 27x; the values survive a reload; no console errors; at 375 px no horizontal overflow. The live page itself is not opened by me (production password rule).
- **Deployed (the user: "deploy it"):** pre-flight in the main checkout (all four suites, a secrets scan of the four files, the page diff against the last deploy is exactly three hunks: the import, `SizePanel`, one line in `SweetSpot`), then a clean worktree on origin/main with only `dashboard/app/Dashboard.js`, `dashboard/app/globals.css`, `dashboard/lib/sizepanel.mjs`, `tests/test_sizepanel.py`, tests re-run there, commit `af5d6e7` pushed to main (Co-Authored-By line). The VM was NOT touched on purpose (it does not serve the page and the change has no feed or bot part; it stays at `3cd87d8`, which holds the feed code). Local main fast-forwarded to `af5d6e7` after proving the four working copies byte-identical to the commit (the two untracked ones moved to the scratchpad, not deleted); 153 other uncommitted entries untouched. **Vercel: 'Deployment has completed'** (GitHub commit status of `af5d6e7`, 17:57 UTC, about a minute after the push). The live page itself was not opened by me (production password rule).
- **Not done:** a balance button (the wallet reader in `dashboard_push.py` stays dormant: no `BITGET_RO_*` variables), a demo-account order button, alerts. The panel is arithmetic only and cannot trade.

### 2026-11-06 (deployed: the sweet-spot card) - the user: "deploy it": commit `3cd87d8` is live (page, feed and the forward scorer); nothing restarted

- **What went out (7 files, from a clean worktree on origin/main, pushed to main):** `dashboard/app/Dashboard.js` (the sweet-spot card on the Analyst tab), `dashboard_push.py` (`sweet_view` and its helpers in the feed; `wallet_view` + `--wallet-check`, a read-only balance reader that does NOTHING unless `BITGET_RO_KEY / SECRET / PASSPHRASE` are set - not set, the feed's `wallet` is empty - and an ast test pins that it contains no order, transfer or leverage call), `dashboard/lib/size.mjs` (position-size maths: not on the page yet), `backtest/analyst_sweetspot.py` (the registered forward scorer), and `tests/test_dashboard_push.py` 35, `tests/test_sizer.py` 5, `tests/test_analyst_sweetspot.py` 8. Pre-flight: all three suites pass, a secrets scan of the seven files found nothing, `next build` passes; the same suites pass in the clean copy before the commit and on the VM (35 and 8; the sizer test needs node, which only the PC has).
- **The VM:** fast-forwarded `80e0ff1` -> `3cd87d8`; the 12 service files (blend_paper, combo_paper, wick_paper, pair_live, mn_paper, news_books, news/crowd_paper, combo_bot, final_books, wick_live, crowd_book, analyst) byte-identical before and after and every service's start time unchanged (no restart); `forexbot-dash.timer` pushed on its next minute; `dashboard_push.py --print` on the VM builds the new block: `analyst.sweet` (3.6 KB uncompressed) with 6 open calls tagged (5 sweet, 1 middle; only #93, XRP long SMC made 16:07 UTC after the registration, counts for the test), the forward test 'NOT YET - 0 of 30 independent bets', 3 watch rows, `wallet` empty; the feed meta is 45.9 KB raw, 12.5 KB packed. **Vercel: 'Deployment has completed'** (GitHub commit status, 17:38 UTC). The live page itself was not opened by me (production password rule).
- **Local:** main fast-forwarded to `3cd87d8` after proving the seven working copies byte-identical to the commit (the four untracked ones were moved to the scratchpad, not deleted); 153 other uncommitted entries (research files, docs, logs) are untouched. The commit gives the 2026-11-06 15:00 UTC registration of the sweet-spot claim a PUBLIC timestamp (the repo is public): the commit is later than the registered instant, and the only proof the claim was written before it remains this session's record.
- **Not built / not live:** the position-size panel on the page, a balance button, any order button (a real-money one will not be built by the assistant; a demo-account one is an open offer), alerts when a sweet-spot call is logged. At the desk's call 100 (87 resolved on 11-06 at ~9 a day): run `python analyst.py --status`, record the verdict; the user decided the desk KEEPS LOGGING (entry above).

### 2026-11-06 (the Analyst desk's review: the user's decision) - "keep logging": the desk stays on past call 100; nothing to change or deploy

- **Decision (the user, 2026-11-06):** at the desk's own review (100 resolved calls, 87 at ~9 a day when asked; or 2027-01-31) the desk keeps logging calls. The review rule itself (retire the BOOK if the average R after fees is <= 0 or p >= 0.05) stands as a statement about the three rules: on the record so far (-0.24R a call) they fail it, and that is to be written down at call 100 - but the recorder keeps running so the registered wide-stop (stop >= 0.8%) forward test can reach its 30 independent bets (about early December, scored with `python -m backtest.analyst_sweetspot <calls.csv>`).
- **Checked:** the review is only text in `analyst.py`'s docstring (REVIEW, A2); no code and no `deploy/analyst*` file stops the desk at 100 calls or on a date, so keeping it logging needs no change, no restart and no deploy. It still never trades real money and uses no keys. At call 100: run `python analyst.py --status`, record the verdict next to this entry, and tell the user.

### 2026-11-06 (Step 1 run: the wall-persistence test) - the user said "yes" to v2's Step 1, then attached the v3 files (`orderbook_bot_v3_pre_registered_protocol.md`, `test_wall_hypothesis.py`): the passive wall entry is KILLED on the tuning days, the confirming days were NOT read; v3 reviewed

- **What was built:** `backtest/wall_levels.py` (the validated `book_hist.rebuild` with a row function that keeps the best 15 levels per side every second; cache `levels_<day>.pkl`, git-ignored; 0 crossed seconds on all four tune days), `backtest/wall_persistence.py` (v2's rule with its numbers in a `REGISTERED` dict pinned by SHA-256 `2c7c283b...` before any wall statistic was computed; a wall tracker with its own trade totals per side, sweeps counted as trades, and a pulled wall kept tracked and INVALID instead of re-registered; entries one tick in front of the wall and never past the touch; fills from the tape through `book_hist.maker_fill` with the queue ahead; maker target / taker stop / maker scratch at 90 s / forced taker exit at 120 s; Hyperliquid fees 1.5 / 4.5 bp; 5 matched random attempts per signal at the same side and distance, no wall), `tests/test_wall_persistence.py` (31 tests), planted-bug check 32 of 32 real mutants caught and the do-nothing control survived (a first pass found the +4.5 bp bar masked by the t test in my own test; fixed). The confirm half runs only with `--confirm` and is refused unless the tune half passed.
- **Registered split:** tune 2025-03-01, 2025-06-01, 2025-09-01, 2026-06-01 (2026-06-01 because the 20 s age came from its wall statistics); confirm 2025-12-01, 2026-03-01, 2026-09-01 (one read, only on a tune pass). Rule at 8/8 bp: at least 30 filled trades, gross >= +4.5 bp, net > 0, excess t >= 2 against the controls; a pass could only be a lead for a 20-day forward record.
- **RESULT (`logs/wall_persistence.txt`):** 247 signal attempts on the four tune days, ONE filled (0.4%; the controls at the same distance fill 22-24%, 276-300 of 1,235); 8/8 gross -8.0 bp, net -14.0 bp on that trade; the rule fails every line; KILL; the confirm days (2026-09-01 included) stay unread. The 246 unfilled attempts moved +0.53 bp in the signal's direction over 30 s (the one fill -6.99): the one-tick lean, about +0.50 bp over all 247 (not distinguishable from zero; rough se 0.4 bp), against the +4.5 bp bar - a resting entry cannot take it, fills are the failures again. Walls: 21,073 registered on the four days, 90 (0.4%) reached 20 s without ever being pulled. Predictions: W1 right, W2 WRONG (fill rate 0.4%, not 25-60%), W3 right, W4 right in direction (filled n = 1), W5 untestable. Limits: one coin, one venue's tape (Bitget; fees Hyperliquid's), a 1 s book of 15 levels (Hyperliquid pushes 20 levels no faster than every 0.5), only one tune day is a true update stream.
- **v3 review (it arrived after the rule was pinned, so the rule was not changed):** v3 answers the size question ($22 everywhere), concedes the 8/8 fee trap (break-even 73.7%; its 15 / 10 bp bracket breaks even at 57.1%, the code comment says 58.3%, not measured against random entries), fixes the tracker's trade buffer (separate buffers, its 3 tests pass) and the rounding (77,962.5 sell -> 77,963, 2.345678 buy -> 2.3456: correct). But: the 'verified code' is a config, a rounding class, a tracker, a fill simulator and 3 tests (no data loading, scan, random baseline, day-clustered t, shifted null, Bonferroni or 'Mode B'; `episode_scored` is never used); its tracker still deletes a pulled wall and registers it again in the same update as a fresh wall (a wall pulled 40% with no trades is 'valid' again 25 s later: the spoof filter resets itself); 'wall at the touch or within 1 tick' makes 'one tick in front' impossible and the code has no entry rule; its fill simulator has no latency and drops the pulled-wall and price-ran-away cancels, and its markout from the limit price to the mid credits a bid at the touch half a spread (~0.3 bp); its pass rule needs 200 episodes and a day-clustered t from one confirming update-stream day (out of reach: four tune days gave 247 attempts and 1 fill) and never requires a positive net after fees.
- **Documents:** Claude Docs 'Order-Book Bot v2 Spec: Review' (updated with a pointer) and 'Wall-Persistence Study: Results and v3 Review'. **Recommendation given: park the passive wall bot.** The only branch not ruled out is v2's fallback (taking liquidity when a wall within 3 bp vanishes without trades): taker fee 4.5 bp against a half-basis-point lean, expected to fail; it needs a new pinned rule first and the user's say. Nothing deployed or committed; no keys, no orders.

### 2026-11-06 (the v2 remediation spec) - attached `orderbook_bot_20usd_v2_remediation_spec.md` (the other agent's rewrite after the review): reviewed, NOT built; its code run, its brackets priced, its venue claims checked on the primary pages, one figure of mine corrected

- **Document:** "Order-Book Bot v2 Spec: Review" (Claude Doc). v2 properly fixes 6 of the 11 contradictions (one-sided entry, level-1 imbalance 0.60, one 35% cancel cutoff, skew deleted, fees 3 bp win / 6 bp stop, unconditional 90 s / 120 s exit), 2 with a caveat (wall age 20 s was chosen from the 2026-06-01 DOGE day that Step 1 will also score; Hyperliquid chosen but the $20 deposit / bridge / withdrawal cost is not priced), 1 not done ('pruned to 4 parameters' is 12 strategy parameters, 23 config fields) and 2 replaced by a new problem (the 8/8 bp bracket raises the fee hurdle; the order size is $11 in the text and $22 in the config).
- **Primary pages opened (WebFetch):** Lighter fees page: Standard maker 0 ms, cancel / modify 300 ms, taker 300 ms; Premium 0.0040% / 0.0280%, taker 140 ms (v2 RIGHT; my first review said 200 ms for maker and cancel, from a search summary: WRONG, corrected in the first document and in the entry below). Hyperliquid fees: Tier 0 perps 0.045% taker / 0.015% maker. Hyperliquid WebSocket page: l2Book '5 levels if fast, 20 levels if slow' (per side not stated), a full snapshot feed 'pushed on each block that is at least 0.5 since last push' (units not stated) - so the first spec's 50 levels every 100 ms is not available. Rate limits as v2 says (10,000 buffer, 1 request per USDC traded, cancel cap min(limit + 100,000, 2 x limit), one request per 10 s throttled, a batch of n counts n, info requests do not count; WebSocket 2,000 messages a minute, 10 connections, 1,000 subscriptions). HftBacktest: 0.0086% per trade is January-February 2025 INCLUDING a 0.005% maker rebate (taker fee 0.07% in the code); 0.44 bp is a table value for May-July 2025 with no commentary - on Hyperliquid, which charges 1.5 bp instead of paying 0.5 bp, that is about 2 bp worse per maker fill. NOT verified (third-party blogs / trackers only): the reduce-only minimum rule, Pakistan access, the 5 USDC deposit / 1 USDC withdrawal fee (5% of $20 if true), the Reddit quota thread.
- **The v2 brackets, random entries (`backtest/spec_v2_bracket_baseline.py`, self-test only - no planted-bug check, `logs/spec_v2_bracket_baseline.txt`; Binance 1-minute bars 2022-01..2026-08, 120 s = 2 bars, Hyperliquid base fees):** break-even target-first share among decided trades 91 / 80 / 74 / 67% for 4 / 6 / 8 / 12 bp (a win nets tp - 3 bp, a stop costs sl + 6 bp); random entries hit 43-50% and lose 3.4-5.8 bp a trade at every bracket on DOGE and BTC (range = tie as a stop with taker timeouts, to tie split with maker timeouts). 1-minute bars give ties in 22% of DOGE 4/4 entries: small brackets need the tick tape. My predictions (91 / 80 / 74 / 67%; a 3-6 bp loss everywhere) right. The signal would have to lift the target share from about 48% to 74% at 8/8; my guess (not computed) is a pass chance under 5%.
- **Its code, run on hand-built cases (it uses only math and numpy):** the wall tracker clears the trade buffer after the first side's update, so the second side's trade-explained depletion is booked as a pull, the wall is deleted and re-registered at age 0 - with a wall on each side eaten by 500 contracts of trades and no cancels, only the side updated first keeps a valid wall (HIGH: it corrupts the hypothesis being scored); `round_price_directional` is right only when the configured tick equals the price's 5-significant-figure step (BTC sell 77,962.5 -> 77,962.1 and a buy 2.345678 with DOGE's tick -> 2.34569, above the request, both invalid); subtracting an own order that is alone at the best bid deletes the touch (spread 0.59 -> 1.18 bp, imbalance -0.167 -> +0.067); order size and quota arithmetic correct. The 'complete' code has NO state machine, scorer, order manager or exchange adapter, and `test_wall_hypothesis.py`, `probe_hyperliquid_ws.py` and MAX_ACTIONS_PER_FILL do not exist.
- **Test plan (its Step 1 on the 7 Bitget DOGE days) - fix first:** the wall-tracker bug (plus a test that fails on the old code); one order size and a price-derived step; a fill rule from the tape (trade-through with the queue, `book_hist.py`) instead of 'a simulated entry 1 tick inside the wall' (passive fills were the signal's failures); treat 2026-06-01 as a tuning day and keep 2026-09-01 (the one unread real update-stream day) for one confirming read; this project's registered bar (`order_flow_registry.py`: day-clustered t, shifted-null p under 0.01, at least 20 confirming days, 200 trades, 75% of days) and a correction across the four brackets, one independent event per wall episode; tick-level pricing of small brackets; the pass rule written to a file before any result. Only 2 of the 7 Bitget days are true update streams (the rest are 15-level snapshots about 6.6 a second). NOT started: the user's call; expectation is a fail (the measured signal is about one tick; the hurdle is 4-6 bp). Nothing deployed or committed; no orders.

### 2026-11-06 (the Analyst desk on $10 / $20 / $50, and the spec as a document) - "answers for the spec in a document; the earlier prompts based on the Analyst desk strategies, not the other books": two Claude Docs written, the desk's calls replayed on small accounts (`backtest/analyst_tiers.py`)

- **Documents:** "Order-Book Bot $20 Spec: Answers and Review" (the 14-page spec, section by section, the bracket test, venue facts, contradictions, code review, next steps) and "Analyst Desk Plan for $10, $20 and $50 Accounts" (the desk's three rules, sizing and account mechanics, the replay, ten real trades, adaptive rules and circuit breakers, a log format, limits). Both are Claude Docs (links given to the user in chat).
- **The replay** (`backtest/analyst_tiers.py`, `tests/test_analyst_tiers.py` 11 tests, 13 of 13 planted bugs caught and the do-nothing control survived; log `logs/analyst_tiers.txt`; calls `logs/analyst_calls_20261106.csv`, 93 calls 10-27..11-06, 87 resolved): re-books the desk's real calls with its own rules (risk on booked equity, notional = risk / stop, 3x gross cap) plus Bitget's $5 minimum. CHECK first: at $300 / 0.5% it reproduces the desk's own booked equity ($310.5429 vs $310.5430), 62 taken and 31 not booked on both sides.
- **Record:** all 87 resolved: 22 won (25%), -0.24R a call; stop >= 0.8%: 29 resolved, 13 won, +0.65R (post hoc); stop 0.4-0.8%: -0.49R; stop < 0.4%: 1 of 19, -1.08R. Inside the wide-stop cut the SMC sweep won 10 of 15 (+1.36R) and the SR bounce 1 of 9 (-0.69R); FIB 2 of 5.
- **Tiers at 1% risk, 10 days:** all calls +3% to +4% on $10 / $20 / $50 (the 3x cap leaves the tight-stop losers unbooked: at 2% risk 73 of 93 calls are not booked); wide-stop calls only +20% to +22%, maximum fall 3% (post hoc, ~31 trades, ~14 independent bets). At $10 and 0.5% risk 28 of the 34 wide-stop calls are under the $5 minimum. First ten wide-stop closes: +8.1% on every tier (6 wins, 4 losses). Adaptive rules: step-down (halve risk after 2 losses) hurt on all calls; a 2% daily stop looked best on all calls (+11% to +13%) by skipping 5 calls and never fired on the wide-stop set; 87 calls cannot separate them. Not modelled: Bitget lot steps, slippage, funding, gold / QQQ availability on Bitget.
- **Checkpoint to remember:** the desk's own review (100 resolved calls, 87 now at ~9 a day) is days away and its rule retires the desk on the current record (-0.24R); the registered wide-stop forward test (0 of 30 bets) needs the desk to keep logging calls - the user must decide. Nothing deployed; no orders; the assistant places no trades.

### 2026-11-06 (the $20 order-book bot spec, and the $10 / $20 / $50 tiers) - "go through the attached spec deeply" (Downloads/Orderbook Bot 20usd Claude Spec.md.pdf, 14 pages, written with another agent) + three pasted prompts for $10 / $20 / $50 accounts: spec reviewed, NOT built; its trade bracket measured against random entries; tier backtests run

- **The spec:** a single-position post-only 'ping-pong' bot on a perp DEX (Lighter / Paradex / Hyperliquid / Aster): a $10.50 order at 5x isolated, entries at 'valid' liquidity walls (45-60 s old, under 30% cancelled), a z-scored order-book imbalance (OBI > 0.8) over 1% depth, a CVD absorption filter and VWAP / volume-profile confluence, take-profit +0.25%, stop -0.35% (stop-market), a 180 s stale exit, a $1 daily loss limit. Text extracted with pymupdf (the Read tool needs poppler); the reference code covers only rounding, micro-price / VAMP / OBI and a wall detector (no tracker, CVD, VWAP, FSM, order manager).
- **Measured now (`backtest/spec_bracket_baseline.py`, `logs/spec_bracket_baseline.txt`, Binance 1-minute bars 2022-01..2026-08, random entries, +0.25% / -0.35% / 3 bars, stop wins ties):** DOGE target first 13.8% long / 14.6% short, stop first 7.9% / 7.3%, NEITHER 78%; BTC 4.6% / 2.1%, neither 93%. Random entries earn -0.0 to -0.2 bp a trade with no fees and -5.6 to -5.9 bp at Hyperliquid's published 1.5 / 4.5 bp rates (the stop and the stale exit are takers; 'post-only everywhere' cannot cover them). Of the trades that touch a level, random entries already hit the target first 64-69% (break-even 58.3%, 65.1% at Hyperliquid's fees): the loss is the timeouts, 78-93% of trades exit with no gain and still pay about 6 bp. My prediction (DOGE target first 3-8%, stop first 1-3%) was WRONG. No signal tested: that needs recorded books.
- **Against what this repo already measured:** (1) the spec's own cited evidence (HftBacktest OBI, 0.0086% = 0.86 bp a trade) is the same one-tick lean `book_hist.py` found (+0.9..+1.0 bp), 25x smaller than the 25 bp target; (2) a zero-fee venue was already shown not to rescue the maker version (`book_hist.py`: net -2.0..-2.4 bp a signal, 0 of 4 days positive; `passive_markout.py`: 30 s markout -0.8..-2.3 bp on 9 of 10 pairs BEFORE any fee); (3) the spec's OBI is built on 1% DEPTH, the deep version `order_flow_lab.py` / `window_lab.py` found carries almost no information (imbalance changes sign with depth; imb20 predicts ~nothing), while L1 carries the one-tick signal; (4) walls: median life 15 s on the DOGE day, only 188 of 2,288 came within 3 bp of the mid (`order_flow_lab.py`) - a 45-60 s persistence filter keeps few; wall-persistence-predicts-bounces is UNTESTED here (registered H-approach, never recorded - the order-flow project was parked at the user's word on 2026-10-30), not dead.
- **Spec problems found (internal):** it quotes a bid AND an ask while its FSM allows only one side at a time; wall age 60 s (table) vs 45 s (text, config); OBI entry z 0.8 (text) vs 0.85 (code); cancel ratio 30% 'valid' vs 50% 'pulled' leaves 30-50% undefined; the inventory-skew term is dead code with one position of $10.50 (q = 0 flat); the stale exit scratches 'at breakeven / BBO' (a taker) and only if OBI has flipped; c1, c2 of the forecast price, vol_to_half_spread 4.0 and about 15 other numbers are point values with no calibration or holdout; no backtest is specified (only an offline smoke test); effective exposure is $10.50 on $20 (0.53x), a win is $0.026 = 0.13% of the account, the $1 loss limit is 27 stop-outs; most venue facts are cited to ONE secondary blog (cipher-intelligence.pages.dev), no links.
- **Checked on the web (search summaries only, verify before relying):** Lighter's Standard account is fee-free BUT, per Lighter's own page (opened later the same day), maker placement has 0 ms, cancel / modify 300 ms and taker 300 ms latency (Premium 0.0040% maker / 0.0280% taker, taker 140 ms) - the zero fee is paid for with latency, and a 300 ms cancel delay is exactly the spec's 'pulled-wall emergency cancel' (this entry first said 200 ms for maker and cancel, from a search summary: WRONG, corrected); Hyperliquid's address rate limit is 10,000 requests in total plus 1 per 1 USDC traded since the address was created (then one request per 10 s; cancels more generous) - a $20 account trading $10.50 clips earns ~21 requests a round trip, so a cancel / replace quoter runs out within hours to a day. NOT confirmed: whether reduce-only orders are exempt from the $10 minimum, Hyperliquid's l2Book depth (5-20 levels?) and push rate (the spec samples 100 ms and scans 50 levels), withdrawal fee, whether any of these venues is open to Pakistan, the bridge cost for a $20 account.
- **Tiers ($10 / $20 / $50 = 2,800 / 5,600 / 14,000 PKR at 280; `logs/micro_honest_{2800,5600,14000}pkr.txt`, `logs/lottery_v2_{2800,5600,14000}pkr.txt`; backtests, start year decides - 2022 starts 0% reach 5x):** micro_bot's rules, honest PIT12 universe, 12 months, reached 5x / ruined: $10 4% 39% / 60%, 2% 39% / 38%, 1% 24% / 34%; $20 4% 41% / 49%, 2% 34% / 17%, 1% 16% / 5%; $50 4% 37% / 37%, 2% 32% / 2%, 1% 10% / 0%. The trend book (lottery_v2, PIT12, 12 months, >=5x / ruined): $10 1% 21% / 0% with 83% of units refused (the $5 minimum), $20 1% 33% / 2% (65% refused), $50 1% 44% / 2% (46% refused), $50 0.3% 33% / 0%. Reading: below ~$50 the minimum order, not the strategy, decides; 4% risk ruins 37-60% at every size; 1-2% roughly removes the ruin and the big-win odds stay with the trend book at $50. Not done: the Bitget contract minimums (the download worked, the read failed on a text-encoding error - open with encoding='utf-8'), the per-tier position-size table, and an answer to the three prompts.
- **Verdict given:** do not build the bot from this spec as written; the cheapest next test is recording a venue's real book (the `orderflow/` recorder is Bitget-public-only) and scoring the spec's signal on the spec's bracket against `spec_bracket_baseline.py`; ask the user before building (memory `feedback-low-prior-research`). Nothing deployed or committed.

### 2026-11-06 (trading on his behalf) - "you have the keys already; after I see my balance and pick a signal I click OK and you trade for me on Bitget": declined for REAL money; the keys are the demo bot's; what is built and what is offered

- **The keys:** `BITGET_API_KEY / SECRET / PASSWORD` in the user's environment are the DEMO bot's (combo_bot.py: `--mode demo` = Bitget demo SUSDT-FUTURES; `--mode live` refuses to start until a human edits `ALLOW_REAL`; CLAUDE.md s7: keys from the environment only, read-only unless asked, sandbox forced and asserted). No key value was read, printed or used in this session. They reach the SIMULATED account, so a balance read with them shows demo funds, not the user's wallet.
- **Declined, and why:** (1) the assistant does not place real-money trades, whatever the authorisation or a click; (2) the repo's own rule: the live gates are human-edited and never worked around; (3) security: a trade button behind one web password on a public Vercel URL means whoever gets the password can trade the account with leverage; (4) evidence: the sweet-spot claim is unproven (0 of 30 bets), the paper machine is at -21% / -30%, doc 22 puts real money after the verdicts. A real-money version, if the user chooses it later, belongs behind a human-edited gate, a trade-only key (no withdrawal, IP-bound), hard per-trade and per-day caps and a confirmation step off the web page.
- **Built locally, tested, NOT deployed:** `dashboard/lib/size.mjs` (position sizer: size, margin, liquidation price, how far the stop sits inside liquidation, max leverage that keeps a 2x gap, the desk's 0.5% risk and 3x cap; `tests/test_sizer.py` 5, the real JS run by node against hand arithmetic) and `dashboard_push.wallet_view` (read-only balance from BITGET_RO_* variables, inert without them, one `fetch_balance` call, cached 5 minutes, errors reduced to a class name; `--wallet-check`; 5 tests, pinned by an ast test that it contains no order / transfer / leverage call; dashboard tests 35). NOT yet built: the sizer panel on the page, `deploy/bitget_ro_env.sh` (the user-run, hidden-input installer; the first write failed), any order button.
- **Offered:** (1) finish the sizer panel + the read-only wallet (the real balance through a NEW read-only key the user installs with the script, never pasted in chat); (2) a 'place on the Bitget DEMO account' button with the sizer's numbers (sandbox asserted, ALLOW_REAL untouched): the whole chain with real exchange fills at zero risk, and realistic data for the forward test; (3) alerts when a sweet-spot call is logged; (4) a written real-money checklist for after the verdicts. Nothing deployed or committed.

### 2026-11-06 (the sweet-spot card) - "show me exactly when to open a position when a sweet spot is coming, with the probability from past trades": built and tested, NOT deployed; the harness that checked my planted bugs was blind (`dashboard_push.sweet_view`, `Dashboard.js` SweetSpot)

- **What was built (the Analyst tab, under the desk's header card):** the registered claim and its forward progress (0 of 30 bets, 'Unproven'); a countdown to the desk's next run (:07 UTC, when a call is born); every OPEN call tagged sweet-spot (stop >= 0.8%) / middle / scalp-sized, priced FROM HERE (reward:risk from the live price against the desk's 1.5R floor) with the random-entry odds (exact for its stop and target) and the desk's past odds for that stop size and method with a 95% range counted on independent BETS (not calls) and a plain 'chosen after looking, it flatters' line; calls made before the registration are labelled 'not scored'; and a 'coming' table - FIB zones the live price is inside (the exact call the rule would log) and strong SR levels within 1.5 ATR (a stop RANGE, because the stop depends on the hour's wick). Liquidity sweeps cannot be previewed (they need the hour's own wick). Feed: `sweet_view` / `desk_history` / `watch_items` / `wilson` / `call_kind` in `dashboard_push.py`; page: `SweetSpot` in `dashboard/app/Dashboard.js`; the forward block uses the registered scorer `backtest/analyst_sweetspot.py` (a constant check pins the two together).
- **What it can and cannot say honestly:** 'when' is the desk's hourly run (about :07 UTC, entry logged then, so a manual entry differs a little - the from-here ratio shows it); 'probability' is the desk's own record: sweet-spot calls 13 of 28 (46%, 14 bets, likely range 24-70%, mean +0.71R a call / +0.42R a bet), middle 8 of 39 (-0.49R), scalp-sized 1 of 19 (-1.08R) - after looking at them, so optimistic. SMC sweeps inside the sweet spot 10 of 14 (8 bets, range 38-91%). Not a forecast. At the time of writing 5 sweet-spot calls were open (ETH FIB / SR / SMC, BTC SMC, BNB SMC) - all made BEFORE the registration, none scored.
- **Checked:** tests/test_dashboard_push.py 30 (11 new in this entry, including the by-hand Wilson interval, FIB geometry, SR stop ranges, bets, countdown, forward scorer); 34 of 34 real planted bugs in the new logic caught plus the do-nothing control correctly surviving; `next build` passes; the REAL SweetSpot and AnalystDesk components were server-rendered against the desk's real files from the VM with live prices (5 open calls, 5 watch rows) and then looked at in a throwaway localhost copy with a generated password (stopped and deleted afterwards): header, badge, countdown, both tables, no overflow at 591 px.
- **A flaw in my own checking, found and fixed:** the planted-bug harness (a scratch script, not in the repo) called a mutant 'survived' only if the output said 'tests passed'; test_dashboard_push.py prints 'N passed', so no survivor could ever appear and my earlier 'all caught' lines for this file were hollow. Caught because the deliberate do-nothing control did not survive. Re-run with an exit-code harness: the new logic had 8 real survivors (bets by day only, FIB zone edges, FIB 1.5R floor, SR 1.5-ATR limit, wrong-side SR, from-here 1.5R floor, method-cell minimum), each now has a test; the earlier display fix (`80e0ff1`) was **14 of 15, not 15 of 15** (the bear-sleeve `daily` flag was untested; the code was right) and is now 15 of 15 with a sleeve test. Added to the s3 trap table. The other studies' test files print 'N tests passed' so their results stand.
- **To deploy** (not done): commit `dashboard_push.py`, `dashboard/app/Dashboard.js`, `tests/test_dashboard_push.py`, `backtest/analyst_sweetspot.py`, `tests/test_analyst_sweetspot.py` from a clean worktree, push, VM `git pull` (the dash timer picks up the feed; the VM needs `backtest/analyst_sweetspot.py` for the forward block, which otherwise falls back to 'NOT YET'), Vercel redeploys. Committing the registration file also gives the registration a PUBLIC timestamp (the repo is public); the registered instant was 2026-11-06 15:00 UTC, and the only proof that it was written before then is this session's record.

### 2026-11-06 (the Analyst desk) - "keep these aside, the Analyst desk has a lot of potential for scalping / sweet-spot trades": the data half-supports it - scalp-sized calls lose, wide-stop calls look good on 14 bets; registered for a forward test (`backtest/analyst_sweetspot.py`)

- Desk log, 86 resolved calls 10-27..11-06: mean -0.229R overall (verdict 'NO EDGE PROVEN', p 0.137), yet its paper book is up +$12 ($308.44): the 3x cap kept the tiny-stop calls out (booked 56 calls +0.154R, not booked 30 calls -0.946R). By stop: under 0.4% (scalp-sized) 1 win in 19, -20.5R (the whole loss); 0.8% or more 13 wins in 28 (46% vs 13% random-entry odds), +0.71R after fees, in both halves of time - but 14 independent bets, t +1.21, found by slicing about 19 ways after looking; SMC sweeps 10 of 14 inside it. The 11-02 registered filter did not confirm out of sample (9 bets, -0.037R). So: scalps lose, 'quality setups with room' is a hypothesis.
- **Registered 2026-11-06 15:00 UTC** (before any judging call): sweet spot = stop >= 0.8%; 30 independent bets (day + side), mean >= +0.15R, t >= 2, hit above random odds, both halves positive; scored by `python -m backtest.analyst_sweetspot <calls.csv>` on calls made after the registration, about early December. His own setups: `python desk.py plan` first. Nothing deployed or committed.

### 2026-11-06 (later) - "what can we learn from today and implement": the booking convention of the live MN / carry books differs from the backtest's (noise, not bias); two micro-caps made the tail day; one display addition built (`backtest/mn_booking_convention.py`)

- **New and measured:** the live paper books the weekly market-neutral basket re-struck at every daily mark (constant dollar weights, `combo_paper.py`), the backtest (`mn_run`) and the real-order ledger hold fixed coins. Same 337 weekly baskets x 7 start days booked both ways: mean gap -0.126 points a week (|t| <= 1.5 on every start day; 2026 so far +0.25 the OTHER way), sd 3.49, 25% of weeks differ by more than a point, +-50-70 points in the 2025-09 squeeze weeks; Sharpe 1.21 vs 1.26. On fresh's live baskets (struck 10-31) -$5.26 booked vs +$4.11 as fixed coins = $9.4 of its -$90. So: no systematic bias, a noisier read of the same basket, and the forward verdicts (11-23, 12-01, 2027-04-09) rest on the daily-reset booking. Nothing changed (the paper books are pre-registered); the proper addition is a shadow fixed-coin line in the next code window, and a real-money version must choose its convention first. Doc 02, last entry.
- **The tail day:** AKE (+130% bounce, short in 2 books) and AIN (-62%, long in 2-3 books) = -$37.7 of fresh's -$49.1; positions $2-25 each, so a per-coin cap would not have bound, and the volume floor was tested (no pass): no rule change. The NASDAQ dip-buy is sized at about the whole account (-4.8% = -$13). **Implemented and DEPLOYED the same day:** an 'Open P&L by coin, all books added' line on the Positions tab (biggest losers / best coins with their books, coins held in 3+ books); DEPLOYED 2026-11-06 on the user's word ('deploy it'): commit `e9423c3` (only `dashboard/app/Dashboard.js`, 19 lines, from a clean worktree on origin/main, pushed to main), Vercel 'Deployment has completed'. The VM was NOT touched (it does not serve the page; it stays at `80e0ff1`, which holds the feed code). Local main fast-forwarded to `e9423c3`; the rest of the checkout is still uncommitted. The live page itself was not opened by me (production password rule).

### 2026-11-06 - "check the dashboard, why is it in shambles": both accounts at the bottom of their band after a micro-cap day; nothing broken (read-only)

- Read-only, feed of 2026-11-06 11:36 UTC (`ssh forexbot-vm 'cd /opt/forexbot && ./.venv/bin/python dashboard_push.py --print'` + `deploy/verify_status.sh`; the web app needs a login, so the data behind the page was read, not the page). All services active, 0 restarts, feed current, code identical to local HEAD (the only 'restart pending' is combo-bot-final, the documented one).
- **Main $236.56 live (-21.1%, day 28, 4.7th percentile = 'worse', under the 5th), fresh $210.11 live (-30.0%, day 20, 1.8th percentile, -35.6% from its $326 peak).** On 11-02 they were -17.2% / -16.2%. **Today: main -$13.73, fresh -$49.13** (fresh -19% in a day at 3.7x gross; the backtest's daily volatility is 12-15%, the live book had run at 2.8-3.1% - this is the first tail day). Main is $24.5 under the day-45 line ($261.30, read 2026-11-23 00:04 UTC): needs +10.4% in 17 days. Backtest windows that looked like main now (day 28, -21% +-3, 595 windows from 38 start blocks): 46% were over the line at day 45, 76% above their start by day 180, 99% by day 365; fresh's comparable set is 114 windows (72% over the line) - too few and too clustered to lean on. Backtest-conditional.
- **Where today went (feed rows, name summed over books):** main AINUSDT -$18.2 (long in MN + daily, short in carry: the coin fell 62% on 11-06, 0.268 -> 0.101 on Binance), QQQUSDT -$11.5 (the NASDAQ dip-buy, bought 10-30 at 693, Nasdaq -6.6% on 11-05 to 646, now 660); offsets AKE +$6.8 (carry long), BIRB +$6.0. Fresh AKEUSDT -$20.3 (short in MN + carry; AKE bounced +130% from yesterday's 0.002197 close to 0.00505), AINUSDT -$17.4 (daily + crowd longs), QQQUSDT -$13.0, ONEUSDT -$8.2 (+31%), UAIUSDT -$4.1 (+78%). Booked/open by book (main): trend -29.9/+10.7, MN -30.1/-8.1, carry +11.6/+12.4, daily -15.7/-6.9, ndx +5.9/-11.5, bids +1.1; fresh: trend -25.1/+2.1, MN -6.8/-23.2, carry +27.3/-12.8, daily -15.3/-7.5, crowd -6.5/-7.5, ndx 0/-13.0, bids +1.1. Scorecard: main MN 4.9th percentile, daily 9.9th, carry 90.7th ('above'); fresh MN 6.7th, daily 6.4th, carry 87.2th.
- **Display trap, again (CORRECTED later the same day):** the MN / carry / bear-basket rows are booked DAILY: 'entry' is the last daily mark and P&L / % are today's move on that day's exposure - they sum to the account's open P&L, which reconciles to the cent with equity, the by-book totals and the exposure. Fresh's AKE shorts read -130% today. The basket was struck 10-31 at 0.013907 (the 10-30 close) and the PRICE is -64% since, but that is not the account's P&L: booked daily at constant exposure the MN AKE short made +$15.88 through 11-05 and -$13.40 today, net about +$2.5 (a fixed-coin position would be +$6.6). My first reading here, 'still about +63% against the true entry', described the price, not the account, and was wrong. The +50% short-squeeze exit measures the real basket price (exit level ~0.0209) and correctly did not fire. AIN on main's MN is a real -62%.
- **FIXED AND DEPLOYED 2026-11-06, DISPLAY ONLY (the user: 'yes fix the display and double check for any errors', later 'deploy it'; commit `80e0ff1`):** `dashboard_push.open_positions` tags the daily-marked rows `daily`, adds `open_px` (the price the basket was opened at: weight x base / coins from `exec.mn_qty` / `carry_qty`, the identity `combo_bot.mn_squeeze_exits` uses; `struck_price`) and `chg_open` (the price move since); `dashboard/app/Dashboard.js` `Positions` labels those rows 'day mark', prints 'today' under the P&L, shows 'opened at X, price now Y%' and adds a footnote. No bot, book or stored number changed: on the VM's real state files with live prices the old code (git HEAD) and the new code agree on every old field of all 58 / 96 rows and add only the three new ones (43 / 39 rows tagged, a struck price found for every one). Payload +2.3% (about 340 bytes a push). tests/test_dashboard_push.py 19 (5 new; '15 of 15 planted bugs caught' - CORRECTED later the same day: 14 of 15 under a harness that could not report survivors, the bear-sleeve flag was untested, now covered, 15 of 15), `next build` passes, the real `Positions` component was server-rendered against the real feed rows (the login could not be used: the local test password was off limits). DEPLOYED the same day: the three files committed from a clean worktree on origin/main (`80e0ff1`, pushed to main; the checkout's unrelated uncommitted work stayed out), the VM fast-forwarded from `b6feef8` (its two extra commits were research files and logs only), all 12 service files (blend_paper, combo_paper, wick_paper, pair_live, mn_paper, news_books, news/crowd_paper, combo_bot, final_books, wick_live, crowd_book, analyst) byte-identical before and after, no service restarted, 19 tests pass on the VM, `forexbot-dash.timer` pushed the new rows on its next minute (read back from Upstash: main 58 rows / 43 daily-marked / 43 with a struck price, fresh 96 / 39 / 39), Vercel 'Deployment has completed'. The live page itself was not opened: its password cannot be typed on a production page. Local main fast-forwarded to `80e0ff1` (the three files clean, the other uncommitted work untouched).
- **Second pass before deploying (the user: 'check the dashboard again ... check if numbers are accurate'; they gave the dashboard password in chat, which was NOT entered on the live site - production pages are off limits for typed passwords - and was refused by the local test copy, which has its own):** a fresh feed and the bot's raw files pulled from the VM in one read-only call (12:00 UTC), every headline number recomputed independently (`audit_feed.py`, scratchpad): booked = the bot's equity; equity = booked + open; the open P&L of every mn / carry / sleeve / daily / capit2 / ndx row and of all 12 trend rows recomputed from the raw state (0 mismatches on both accounts); crowd rows; booked P&L per book = state `cum`; the by-book totals less fees = equity - 300 to the cent; closed-trade count and total = the two CSV logs; today = live equity minus yesterday's last curve point; exposure and leverage from the coin ledger; fall; every scorecard percentile (account and each book) recomputed from `dashboard_bands.json` - all match. The only flag was marks vs Binance seconds later (QUSDT 1.0-1.25% on a thin coin): the feed's mark sits inside that minute's own range, the price moved after. Known soft spot, by design: closed TREND trades carry an estimated P&L (the log has R, not dollars): -29.44 vs the account's booked trend -29.90 (main), -23.81 vs -25.12 (fresh). The changed page was then looked at in a throwaway localhost copy with a password I generated (stopped and deleted afterwards): 'day mark' / 'today' / 'opened at ... price now ...' render on the daily-marked rows, the entry-booked rows are unchanged, the footnote shows, no horizontal overflow at 591 px.
- **Reading:** not a fault - two micro-cap events (a -62% dump held long in 2-3 books, a +130% bounce held short in 2 books) plus a NASDAQ dip-buy that bought a down day that fell further. The same name in several books (main AIN in 3, fresh 1000PEPE in 4) concentrates the tail; a per-name cap (`coin_cap.py`, 2026-10-20) and a volume floor (`universe_floor.py`, 2026-11-02) were both tested and neither moves the worst month or passes. No change proposed to any bot (code freeze to 2027-04-09, doc 22). v2 `combo_paper` -19.3% (day 42, $178.32), pair paper -18.3%, crash bids +1.68% (96 of 96 fills kept, +0.70% each). Nothing was deployed by the read itself; the display fix below was deployed later the same day.

### 2026-11-04 (book, again) - "90% buyers in the book, do they wait a minute, does the wall stay thick, then open and close; and how do we reduce fees by leverage or what": the state does not last, the signal is under one spread, leverage cannot cut fees (`backtest/book_sustained.py`)

- The user's sentence run as written on the seven Bitget DOGE days of `book_hist.py` (one-second rebuilt book, 604,793 samples), predictions S1-S6 in the file first, 16 tests / 22 of 22 planted bugs caught. **A 90% bid share at the touch is a normal state (9.5% to 31.8% of seconds, ask side 16.2% pooled); in the deeper book (20 levels, within 10 or 25 bp of the mid) it essentially never happens (2 / 21 / 2 runs in seven days) and the deep book tops out at a 70% bid share 1.5% of the time.** Runs at the touch: 52,579, median 1 s, 2.2% reach 10 s, 0.1% 30 s, **none 60 s** (longest 82 s); a minute later it is on 23.0% of the time vs 18.5% of all seconds - almost no memory. 60-second triggers in all seven days: imb1 at 90% **1**, 80% 4, 70% 12; imb5 at 70% 37; deep book 70% 1-10, 80-90% none.
- **The trade:** the only 60-second version with events (imb5 at 70%, 37 on 2 days) loses -0.7..-2.3 bp gross. Shorter waits show the old tiny lean: imb1 at 90% held 10 s, then long 60 s = 831 events, 7 days, gross +1.37 bp, excess over the same-hour baseline +1.30 bp (t +4.5), +0.05 bp after the spread, -11.95 bp after 12bp taker fees, -2.63 bp even as a queue-free maker. 143 cells with >= 100 events, **PASS 0 on taker net and PASS 0 on the 4bp maker bound**; best taker net -8.27 bp. The largest excesses (+3.75 / +3.51 bp, 106 / 111 events on 3 / 4 days) have a negative twin (-5.53 bp) and are +0.6 / +0.4 bp at t 0.5 / 0.3 as makers.
- **Fees:** leverage does not change the fee per dollar of notional; it multiplies it against margin (12bp = 0.12% of margin at 1x, 1.2% at 10x, 12% at 100x). Real levers: maker fills (adverse selection, `passive_markout.py`), volume/VIP tiers, token discounts (the BGB discount on Bitget futures is disputed between sources), another venue (MEXC is reported at 0% maker / 0.02% taker - search summaries only, official pages not fetched, whether it serves Pakistan unchecked). Even at zero fees the best cell with 500+ events earns +0.8 bp. The 2026-10-28 conclusion (real one-tick lean, nothing after costs) stands for the minute-long version. S1 and S3 wrong in detail, S6 untestable (doc 02). Nothing deployed or committed.

### 2026-11-04 (the CME feed, in bulk) - "must be something we are missing in CME": a bulk scan of every second of his 31 windows finds no state that calls the next +-7 race (`backtest/his_cme_scan.py`)

- Earlier CME tests were one feature at a time at his 25-46 clicks. This one: gradient boosting on 32 causal features of the NQ mid, book sizes and aggressor-signed trades, every second of 22.7 hours, leave-one-window-out. Within-window AUC 0.521 (se 0.018); most confident 20% / 10% / 5% of seconds right 48.5% / 44.7% / 42.3% (100+ independent events each) against 65% needed and his ~95%; at his clicks the label reproduces his side 83%, the CME model 45% (p 0.64). The first run printed AUC 0.454 (below chance): a leave-one-group-out base-rate artifact (the up-rate alone scores 0.389), fixed by centring each fold and reading within-window AUCs - a new trap. A public-feed state that called +-7 races 95% of the time would be an HFT gold mine, so the information is most likely non-public; the one observation of his market we have never made is CapitalFX's own quote stream inside the minute. Not excluded: rare complex states (only ~1,300 independent races), per-order data, other CME products. Doc 02, last entry. Nothing deployed or committed.

### 2026-11-04 (forex: gotobi) - "i said in forex, try some different strategy": the Tokyo fix flow on USD/JPY is not there; a USDT/PKR P2P snapshot has no spread (`backtest/fx_gotobi.py`)

- Forced dollar flow before the 09:55 JST fix on the 5th/10th/15th/20th/25th/month-end: +0.72 bp gross on gotobi days vs +0.91 on other days (t -0.4), net of 1.2 pips -0.38 bp; the 08:00 JST start gives excess +1.4 bp, net +0.76 bp, t 1.5, nothing under Holm; a ~0.9 bp Tokyo-morning dollar bid exists every day (about the cost). Even a real forced-flow edge in a major pair is worth under 1-2 bp a trade against ~1 bp cost, so the whole FX family is capped at cents per trade at retail size. G1, G2, G4 wrong; 22 of 22 planted bugs caught. Same day a ONE-snapshot read of the public USDT/PKR P2P ads: reliable round trip -0.13% (the 298 PKR bids were bait); not a series. Doc 02, last entry. Nothing deployed or committed.

### 2026-11-04 (NASDAQ scalping) - "this is not a good strategy, I want something better, preferably scalping like he does": a walk-forward model on 16 years of NQ minutes with volume cannot beat even a futures-sized cost (`backtest/nq_scalp_ml.py`)

- 441,760 decisions, 17 features (4 volume), ridge + boosting trained on earlier years only, test years 2014-2026, horizons 3 / 5 / 15 / 30 minutes: pooled rank IC +0.003..+0.016 against +0.054..+0.018 needed at 0.77 bp; the strongest tenth nets -0.2..-0.5 bp; 0 of 18 cells at t >= 3 at 0.77 bp; at a 0.25 bp futures-like cost 14 of 18 are nominally positive and none reaches t 3 (best +0.59 bp, t 2.3); volume adds nothing. A real but tiny 3-minute signal (positive every year, ~0.2 bp). N1, N2, N4 right, N3 half. Not found in 16 years of price and volume; his edge is not in this data. The noise rule (with the VXN shadow arm) stays the only NASDAQ book standing. Doc 02, last entry. Nothing deployed or committed.

### 2026-11-03 (NQ futures bought) - "buy whatever from the credit, use premium data": NQ minute bars with volume (USD 19.93); the rule is confirmed on a second vendor, volume and VWAP add nothing, the VXN gate clears the bar (`backtest/nq_noise.py`)

- Noise rule on real NQ: +2.27 bp/day, correlation 0.972 with the CFD result; the early half is weak (tune t 1.2; most of the edge is 2020 on; double costs t 1.6). The published VWAP trail: -0.02 bp/day. Volume does not say when the rule works. VXN above its 1-year median: +4.51 bp on 48% of days, both halves t > 2.2, still +3.4 bp at double costs; on a $300 x5 account the gate keeps the CAGR (+23%) and cuts the fall from 65% to 44%. Found after looking, so it goes into the bot as a shadow arm. Not 'full-proof': marginal, regime-dependent, no forward record. Doc 02, last entry. Nothing deployed or committed.

### 2026-11-03 (NASDAQ, mechanism first) - "a full-proof strategy, think outside the box": an admission bar, and the first two mechanism tests (`backtest/nasdaq_regimes.py`)

- Nothing is fool-proof; the demandable thing is an admission bar (mechanism first, both halves t >= 2 after costs and Holm, survives double costs and a second vendor, correlation < 0.5, forward record). Today one member passes marginally (the noise rule), so the NASDAQ bot should hold ONE book plus shadow arms. The user gave permission to spend the Databento credit ('buy whatever'): NQ 1-minute bars with volume (USD 19.93) were bought for the VWAP version and volume regimes (`nq_fetch.py`, `nq_noise.py`); S&P (USD 20.74) deliberately not bought yet.
- Regimes: the noise rule earns in stressed markets on all three proxies fixed in advance (VIX curve inversion, VXN, previous range) but none confirms strongly enough to gate; closing-hour flow: real, below cost. Doc 02, last entry. Nothing deployed or committed.

### 2026-11-03 (knowing when not to) - "he does small profits with great accuracy, meaning he knows when not to": a disaster-avoidance filter does not rescue it (`backtest/know_when_not_to.py`)

- Predicting the DISASTER (target never touched) of a +2.5 bp no-stop trade from time, volatility, range, trend, gap and weekday: AUC 0.61-0.63 held out (2019-12 on); keeping only the safest 5% lifts the win rate to 98.0% yet the surviving losers average -137 bp (~55 targets) and the expectancy stays -1.0 bp (all entries -1.25). 0 of 10 cells positive. What he avoids is the catastrophic loser = a crash prediction; nothing readable makes one. D1-D3 right. Doc 02, last entry. Nothing deployed or committed.

### 2026-11-03 (small profits) - "it is simple maths: small profits plus experience - do that": tested in its plainest form, 0 of 18 cells earn money (`backtest/small_profit_scalp.py`)

- Small target + no stop needs a 94.7-98.1% win rate because the rare loser averages -126..-151 points (worst -991); random entries win 93.4-96.6%; trading with the day's trend after a pullback adds under a point of win rate and makes the losers bigger: best cell -1.66 points a trade. 'Experience' would have to avoid ~one extra disaster per 50-100 trades (+2 points a trade); nothing readable does. No bot built for it (it would be the known loser, at his leverage one -991-point day is ruin). Doc 02, last entry. Nothing deployed or committed.

### 2026-11-03 (his losses, his habits) - "examine his losses; keep his habits in mind or mend them": losses examined, his pullback entry tried on the bot's rule - worse (`backtest/his_losers.py`, `backtest/noise_pullback.py`)

- Losses: 15 of his 17 below-target NASDAQ trades are small wins (that is the win rate), 21 trades above +7.5 make 83% of profit; the two real losers were pullback BUYS in a trend that turned (a 10-second -7.5 cut; a 48-minute -31.75 hold); 37 of his 41 gold trades are one frantic 48-minute sitting on a 99th-percentile day (+$74 net). Habits ledger in doc 02: nothing to bolt on; the one testable habit (pullback entry) made the NOISE rule worse on both halves in all 4 variants (-0.9 to -1.2 bp/day, t -3.8..-5.0). Bot unchanged. Doc 02, last entry. Nothing deployed or committed.

### 2026-11-03 (exit shape) - "we have achieved his win rate, that is enough; pattern-recognise his losses, try every combination": his win rate is the exit's doing (`backtest/his_exit_shape.py`)

- All 30 target x stop combinations from RANDOM entries lose (-1.8 to -2.9 points a trade); the +7 / no-stop shape wins 93.7% from random entries, so his 95.7% is no evidence of skill, and its random losers average -132 points (break-even win rate 95.0%) against his two real losers at -19.6. The edge is in the entry (the side, 88% vs 55% to +7 before -7) and in losing little when wrong - not in any exit rule. H2 wrong (93.7%, not ~83%), H1, H4 right, H3 half. Corrected my own loose earlier sentence (the no-stop bots win ~94% too, and still lose). Doc 02, last entry. Nothing deployed or committed.

### 2026-11-03 (forex bot) - "ask council ... a fully functional forex bot": release 1 built, demo-only, not started (`forex_bot.py`)

- Council (five advisors, one shared brief; peer-review round skipped): build one thing - NASDAQ noise momentum on USTECm, rules verbatim from the backtest, demo only, flat before the close; do not build a copy of his habits, any currency-pair rule, the add-on books or a VXN gate; the demo proves plumbing and costs, not the edge (~7 years for t = 2). Built with their shell: New York clock, demo-account assertion, no real-money path, disaster stop, daily kill, filters, reconciliation, hash-chained log, cost audit. Parity with the backtest 150 of 150 days; 23 tests; 24 of 25 planted bugs caught (the survivor is redundant); read-only smoke test on the real MT5 demo terminal passed. Details and the council's challenges: doc 02, last entry.
- **Numbers the user asked for first (backtest, x5 on $300):** typical 12 months $346, bad $296, worst $183, fall 56%, worst month -20%, worst day -13.7%, 53% of months up; plan on about half the edge: ~+$20 a year, range about -$20 to +$45 in a typical year, -$117 in a bad one. Mostly leveraged NASDAQ beta; t 1.5 at double costs; all profit on high-VXN days (found after looking).
- **Not started:** nothing trades. Next, if the user says go: `python forex_bot.py --mode dry` on the PC (needs the MT5 terminal logged into the demo and the PC awake 19:30-02:00 Pakistan time), 10 trading days, check `--report`; only then `--mode demo`. Also same session: the user's request for 'all strategies of his that we know for sure' was answered from doc 23 (habits and exits are known; the side is not; run as bots they lose the spread). Nothing committed or deployed.

### 2026-11-03 - "try it on 5 minute and 15 minute, also ask the council what the secret could be": RSI nothing; the council's top ideas need him, and the one we could test (add-ons build the record) is refuted

- RSI on 5- and 15-minute candles (`backtest/his_rsi_long.py`; candles from Exness 1-minute bars so the 15-minute RSI has history; 45 of his 46 entries, 42 cells): 0 survive Holm; the 5-minute levels lean to the pullback side (rank 0.41-0.42, one finding, not tradable: 35.6% net race vs 50%). Predictions Q1-Q4 right. Tests 8, 10 of 10 mutations caught (my first tests used decision times too early for the 15-minute warm-up and the mutation table was invalid until the baseline passed).
- Council (five advisors, the peer-review round replaced by my own cross-check after a session rate limit): a human cue (caller / room / voice) first, 'the record is produced or selected' second, his platform third; all five say stop mining market data. Cross-check: 'fills are the edge' conflicts with s42 (he banked +8.96 of a +10.97 market move); 'built by add-ons' is refuted by `backtest/his_sittings.py` (22 of 31 sittings are a single trade; first tickets 29/31 at +9.22 points vs later 15/15 at +9.07; tests 4, 5 of 5 mutations caught). What the council recommends (record his sittings / ask him) needs the trader; the user said there is nothing more they can supply. Nothing deployed or committed. Doc 02, last entry.

### 2026-11-02 (carry) - "our funding carry book is doing too good, right?": fresh's carry +$21 (94.9th percentile) is real accounting and mostly price, not funding; main's carry is +$5.6 (read-only; throwaway script)

- Feed of 2026-11-02 14:56 UTC (`ssh forexbot-vm 'cd /opt/forexbot && ./.venv/bin/python dashboard_push.py --print'`; the VM's stderr line "sizes (json, packed)" lands inside the JSON when both streams go to one file - strip it). Carry book: fresh $21.16 (booked 17.55 + open 3.61, 16.6 days, 94.9th percentile of its band, p95 = +21.33), main $5.58 (booked 2.37 + open 3.21, 24.6 days, 65.9th, "ok"). Same rules, different weekly anchor (main Fridays from 10-09, fresh Saturdays from 10-17).
- **Not a bug.** Rebuilt independently from the logged baskets (`CARRY REBALANCE` lines in `combo_paper.log`, $ per position) plus Binance daily closes and funding: main +$2.36 against the bot's booked +$2.37, fresh +$17.56 against +$17.55. `final_books.funding_sum` is half-open `(start, end]` and bounded at both ends (mistake #15 is NOT in the carry book); the daily mark is `base x (w x return - w x funding)`.
- **It is not carry income.** Fresh: price +$14.50, funding +$3.06 (17%); the short leg (the highest-funding hype coins) made +$17.16 on price and almost no funding (+$0.22), the long leg lost -$2.67 on price and earned +$2.85 funding. AKE's short alone is +$4.95 booked and +$1.83 open (about a third of the total); without it fresh's booked carry is +$12.6. Main: price -$0.15, funding +$2.51, i.e. only the funding paid - its first basket (10-09) lost -$7.55 on the long leg, BTW and BULLA shorts hit the +50% exit (-$4.0, -$2.8). Two clones of one machine, 15 dollars apart in carry from the anchor day alone (one tape, see the forward-test entry).
- **Why it pays now:** the book shorts the crowd's most-long names and longs the least-wanted; in an alt sell-off with micro-cap hype coins dumping (AKE -35% since the last mark, UAI -17%, BRU -8%) the short leg is the winning side. In a squeeze it is the losing side (BULLA +55%, BTW +52% before the exit). Expect it to give this back; the backtest's carry holdout Sharpe is +0.28 (doc 02), and the 95th percentile is where the scorecard says "above", not "proven".
- **Paper realism:** fills at the daily close, 12bp on turnover only, positions $3-6; the shorts are thin names (Bitget 24h turnover: MUBARAK $0.33M, ONE $0.43M, VVV $0.58M, USELESS $0.9M, PONS $1.7M) and 3 of 21 checked names (BTR, SAGA, BULLA) are not on Bitget at all. Nothing changed in any bot; nothing committed.

### 2026-11-02 (late) - "RSI worked but with a few big losses - there must be a profitable take-profit / stop-loss ratio": no ratio pays; the best cell's +0.37R was a day-vote mean and the one rescue was a look-ahead (`backtest/rsi_ratio.py`, `backtest/rsi_ratio_check.py`)

- **The ratio grid** (RSI(14) crosses 30 / 25 / 20 long, 70 / 75 / 80 short, plus the capitulation volume rule; 1h and 4h; PIT top-40; 16 brackets of stop 0.5-4 ATR x target 0.5-4R; each cell against the SAME bracket from random entries at the same day x slot) = 448 cells: **PASS 0**. Per trade, every textbook oversold-long bracket is negative on the tune half (-0.04..-0.40R) and at most +0.01R on the holdout; shorts are negative on both halves in all 16 and worse than random entries. RSI entries win as often as random ones (mean gap 1.7 points), so a ratio only trades win share for payoff and every one nets about minus the fee. Random entries lose in 54 of 64 holdout cells. cap20 with a stop: tune negative at all 16 brackets, holdout positive at 15 - the sign flips, and the no-stop trade of `rsi_confluence.py` is the one that had an edge. Doc 02, last entry.
- **Trap 1, found by a hand check before it was believed:** the first log printed only DAY-VOTE means (each entry day one vote). The best bracket (1h RSI under 30, stop 1 ATR, target 4R) read **+0.368 / +0.257R** (t +8.2 / +4.7, Holm 0.00) and is **-0.150 / -0.123R a trade**, negative in every year 2020-26 (27,507 trades): a sell-off puts 100+ oversold signals in one day, they lose together, one vote a day lets quiet days outvote them. Capped accounts (0.3% risk, K 3 / 5 / 10 open, $300) lose money on both halves in all 36 rows, -16..-96% a year. `rsi_ratio.py` now prints a per-trade column (first run kept as `logs/rsi_ratio_dayvote_first_run.txt`); `candle_scan.py` / `candle_manage.py` print day-vote means too (their null conclusions stand).
- **Trap 2:** bucketing those trades by the number of coins that signalled on the SAME CALENDAR DAY made quiet days win +0.03..+0.90R (32 of 32 buckets positive) - a look-ahead, the count includes hours not yet seen. Counted over the 24 hours up to and including the entry hour: 0 of 40 buckets positive. Both traps are rows in s3.
- One lead, not pursued: 4h RSI over 80, long, 4 ATR stop, 4R target, +0.227 / +0.292R per trade (775 / 313 trades, excess over random +0.19R on both halves) - 1 of 448 cells, Holm 1.00, the trend book's family (strong up-moves continue, `market_fade.py`).
- Predictions: Q1, Q2, Q4 right; Q3 (15 cells with excess, not 3) and Q5 (cap20 is not positive on both halves) wrong; the three stated after the fact in `rsi_ratio_check.py` right. Tests 13 (27 of 27 mutations caught) + 4 (8 of 8). Nothing deployed or committed.

### 2026-11-02 (night) - "could it be RSI?" (the NASDAQ trader's side): 51 RSI settings tested at his entries and as a signal - nothing (`backtest/his_rsi.py`)

- After the user said his edge CAN be rebuilt from data and asked whether it is RSI: the grid (15 s / 1 min / 5 min candles x RSI periods 2-14 x level, slope, hook up through 30; closed candles only) at his 25 clean entries vs nearby moments: 0 of 51 reach raw p < 0.05, 0 survive Holm (smallest raw p 0.111); as a 3-minute NASDAQ signal on 181 tick days the best chosen-on-half-1, read-on-half-2 net race is 37.5% (break-even 50%, base 35.8%). Not his rule-like trigger (n = 25 detects only a rank beyond ~0.69); a mild preference cannot be excluded. RSI works in this repo only as the DAILY NASDAQ RSI(2) dip-buy already in the machine.
- Same session: the maker rebuttal (`passive_markout.py`, entry above) and the user's instruction that his edge is an OPEN problem to be stated as 'not found in X tested', never 'impossible' (memory `feedback-trader-edge-open-problem`). He has no more inputs to give (no tools or habits known to him); the remaining untested sources are private ones. Nothing deployed or committed.

### 2026-11-02 (evening) - "the order book, and the rebuttals - how can we counter this": the strongest counter (be the maker, on wide-spread pairs, use the book) tested on the recorded books: adverse selection eats the spread (`backtest/passive_markout.py`)

- The user asked for the whole order-book topic with the counter-arguments, taught in the chat. The strongest rebuttal to my verdict is not 'predict better' but 'be the MAKER': rest orders at the touch, choose pairs with wide spreads in bp, and use imbalance to avoid being picked off. Tested at once on the ~40 minutes of real books from the Module 5 trial recordings (2026-10-30, ten pairs), predictions M1-M4 first.
- **Result:** after a resting order at the touch is filled, the mid moves against it by about the half-spread or more within 30 s: 30 s markout (spread included) -0.8..-2.3bp on 9 of 10 pairs (ADA +0.3 +- 0.6; DOT's 5.3bp half-spread is all given back, -0.83); every pair's net bound is negative even with perfect queue priority and a free exit (UPPER -1.7..-4.3bp, LOWER -8.9..-14.1). The book helps (imbalance leaning WITH the fill beats leaning against it on 10 of 10 pairs, +3.0bp average, BTC +1.6 +- 0.6 on 1,399 vs 3,425 fills) but BTC's best cell is +0.1bp against a 2bp fee, and that cell has the longest queue, which the bound ignores. M1, M3 right; M2 and M4 wrong.
- **Bug of mine, found before interpreting:** the first run counted every print at or below the touch as a fill at the touch; 76% of BTC's were deeper levels of a sweep (the most informed trades). Fixed (a fill = a print exactly at the touch, once per taker order per millisecond); BTC moved -1.50 -> -0.91, no conclusion changed. 12 tests, 8 of 8 mutations caught (two of my first tests were wrong; the mutation pass found two missing ones). Exploratory: 40 minutes of one busy afternoon; the official multi-day record was never started and the order-flow project stays parked. Nothing deployed or committed. Doc 02, last entry.

### 2026-11-02 (swap-free) - "yes I guess Exness accounts are swap free, you can search the web": plausible for Pakistan, NOT confirmed for the user's account or USTEC; the demo is not swap-free (read-only)

- **The local MT5 terminal** (`Exness-MT5Trial16`, a DEMO, 1:200) charges swap on everything: USTECm long -653.1 points a night (short 0; about $0.33 a night at the 0.05-lot minimum, ~2.3bp of notional a night = ~8% a year at 1x), US500m -162.3, XAUUSDm -474.7, BTCUSDm -1778.7, EURUSDm -5.8. That says nothing about a real client's swap-free status, which is set per client / country.
- **Web:** third-party review sites (tradingbeasts, brokeranalysis, comparebroker) say Exness applies swap-free automatically to accounts from Islamic-majority countries, Pakistan usually named; Exness's own help-center article is titled 'Swap-free status (Islamic countries)' (`exness.com/link/help-center-article/18055079599132/`) but `WebFetch` could not resolve exness.com, so it was NOT read here - the search summary of it says the status can depend on trading activity and that clients who regularly hold large amounts of orders open overnight may not qualify (exactly the NASDAQ core's pattern), and that the status is shown under Trading conditions in the Personal Area. Whether Pakistan is on the official list, whether indices are covered and whether any holding fee applies are all unconfirmed.
- **What it would unlock (throwaway script on `^NDX`, the index not the CFD, 2006-07..2026-09, `ndx_swapfree.py`'s `book` / `stats`):** the crash-filtered core (200-day average + VIX below VIX3M) swap-free at 2x +20.4%/yr, fall 49%, charged +7.6%; at the minimum lot's 4.8x +35.7%/yr, fall 83% (2008 -64%, 2011 -37%, 2022 -63%; 1,299 of 5,076 days more than 50% below the peak), charged +3.6%. USTECm is 28,564: 0.05 lot = $1,428 = 4.8x of $300 / 6.5x of $221, and 2x needs about $714. Not a plan for $300; mostly NASDAQ beta; no forward record.
- **The check only the user can do:** a REAL Exness account's Personal Area -> Trading conditions (swap-free status), then the symbol specification of USTEC on that account in MT5 (swap long / short 0), and one question to Exness support: is USTEC swap-free for my account, is there any holding or administration fee, and can the status be removed for long holds. Nothing changed in any bot.

### 2026-11-02 (universe floor) - "Yes, run it": a volume floor on the market-neutral and daily books does not help (`backtest/universe_floor.py`)

- The user approved the one test left after the forward-test read: drop the small names. MN book (half momentum, half RSI, +50% short exit) on the PIT top-40 / 30 / 20 against the base top-60, all 7 rebalance weekdays, with a k-matched control (top-60, 3 names a side); the daily book on top-30 / 20 against top-40 (3 boundaries x 10 orderings). Predictions U1-U5 in the file first. **No floor passes.** Every MN floor loses the tune half on 0 of 7 weekdays (Sharpe -0.40 / -0.54 / -0.76 for top-40 / 30 / 20) and gains the holdout (+0.07 / +0.15 / +0.19) - the mined-holdout signature; in the weeks that resemble the live tape (alts down >= 15% in 30 days) the base averages -0.17%/wk and the floors -0.21..-0.41; the MN fall goes from 31% to 44-47%. The daily book is lower on both halves in 30 of 30 pairs; top-20's fall is 11 points shallower but the base at 0.75x has +116% / +52% / fall 51% against top-20's +102% / +36% / 50%.
- Predictions: U1, U2, U3, U5 right; U4 half wrong (top-20's fall). **Bug of mine found by the new tests:** `max_fall` ignored the starting equity (a loss in week one was not a fall); fixed, the log's numbers did not move. Also found: `moderate_retests.scored_run` skips any week with fewer than 20 eligible names, which would silently empty a top-20 universe - `scored_run_floor` makes it a parameter and reproduces `scored_run` exactly at the base.
- Caveat for anyone who reopens this: volume rank is the only size measure in the data; in the live November pool file (volume order assumed) BTW is 19th, AKE 50th, PONS 65th, USELESS 88th, MARSCOIN 103rd and FLOCK / SOPH are outside its first 120, so several of the names that hurt sit below every floor tested and a market-capitalisation filter is untested (no data). Nothing deployed or committed. Doc 02, last entry.

### 2026-11-02 (forward test) - "what can we deduce from main and fresh, any signs": one sample, a market-neutral long leg that lost every week, and a loss that is not market beta (read-only; throwaway scripts, nothing in the repo)

- Read-only, feed of 2026-11-01 23:49 UTC (`ssh forexbot-vm 'cd /opt/forexbot && ./.venv/bin/python dashboard_push.py --print'`) plus both accounts' logs (`combo_marks.csv`, `combo_mn.csv`, `trades_combo_trend.csv`, `eq_*_h.csv`). Main $248.32 (-17.2%, day 24, 7.3rd percentile), fresh $251.31 (-16.2% live, day 16, 9.5th). Numbers came from scratchpad scripts, so re-derive before quoting.
- **It is ONE sample, not two:** hourly equity correlation main vs fresh 0.81, daily 0.75; both run the same rules from different start dates. Over the shared window (from 10-17) main -11.3%, fresh -16.9%: crowd book (fresh only, -$7.4) is about half of that gap, the rest is path (carry +$2.4 vs +$17.7, NDX +$7.5 vs +$1.9, trend entries). **Two clones of one machine differ by ~5 points in 16 days: do not read smaller differences.**
- **The loss is not market beta:** hourly regression of account returns on BTC or the median-alt index: R2 5-9% (main), ~0 (fresh), beta -0.3 to -0.4 (main) / ~-0.1 (fresh); BTC -4%, median alt -18% since 10-09. The accounts lose on specific things, not because "the market fell".
- **Where it went (booked + open, main / fresh):** MN -28.8 / -27.8 (55% / 68% of the net loss; 8th / 6.5th percentile), trend -20.0 / -20.9, daily -11.3 / -10.7, crowd 0 / -7.4; carry +2.4 / +17.7, NDX +7.5 / +1.9, bids +0.8 / +0.8; sleeve, capit2, news idle by design.
- **MN: the long leg lost every week.** Seven weekly baskets (4 distinct weeks, two anchor weekdays): long leg -4.0..-13.7% a week, spread (long minus short) negative 7 of 7, mean -6.1% per gross unit (about -3% on the equal-weight basket); the long names rank at the 35th percentile of the week's returns, the short names at the 54th (neither leg picked well). Reproduces on both anchor days (Fri on main, Sat on fresh), so it is not a weekday artifact; the longs are repeatedly the pumped micro-caps (BTW in all four of main's baskets). Universe approximated by 67 coins, equal weights, so indicative.
- **Concentrated in a few days and names:** the 6 worst booked days are 69% (main) / 90% (fresh) of all down-day losses; without the 3 worst days main is -20.7 (not -62.9) and fresh -0.1 (not -50.7). The tail names: SOPH (10-30 squeeze), AKE (daily book -$7.06 on one trade plus bids), BTW (fresh: crowd, daily, carry, bids and MN at once, -$7.6).
- **Trend book: longs 0 of 35 (main) / 0 of 38 (fresh) winners; shorts 15 of 37 (41%) / 11 of 36 (31%).** Backtest (triple, `graveyard_rescore.rows`): longs win ~10% of positions, shorts ~32%. A 35-long stretch with zero winners occurs in 15.7% of backtest stretches (22.9% since 2024-08): unremarkable; shorts are on model. The 10-09 short runners (LTC, XRP, ADA, LINK, SUI, SHIB) are +9..+17% open, +$7.9 on main.
- **Crowd book on fresh:** open long legs -$9.5, short legs +$2.1 (net -$7.4); the standalone paper book is $292.59 after one week.
- **Day-45 line, priced on the backtest's windows (`logs/daily_combos_cache/machine_account_daily.pkl`):** windows near main's day-24 level (-13..-21%): 66% were over -12.9% at day 45 (70% month-weighted), 85% above start by day 180, 99% by 365; fresh at day 16 near -13.7%: 70% over the line. Main needs $261.30 at 2026-11-23 00:04 UTC (+5.2% from $248.32). Backtest-conditional.
- **Not re-done today:** the 10-22 replay of live against backtest code (`backtest/live_check.py`); nothing deployed, nothing committed. Realised daily volatility is 2.8-3.1% against the backtest's 12-15% (its tail days have not happened yet): the forward test has not yet seen the part of the payoff the machine is built around.
- **Follow-up ("so we do nothing?"): is the MN drag an anomaly? No - the backtest's MN is flat-to-negative in exactly this tape.** `machine_books()` (10 orderings, `mn_blend`, ~340 distinct weeks, non-overlapping) bucketed by the PIT top-40's trailing 30-day median coin return (throwaway script, `indicator_model.build_panel`): all weeks +1.18%/wk (44% negative); alts down 15-25% +0.71% (median -0.13%); alts down >25% -0.54%; alts flat (+-5%) +2.37%; today's shape (alts <= -15%, BTC 30d > -8%) -0.42%/wk, 59% of weeks negative, worst week -11.4%. The sign does not replicate across halves (tune -0.19 / holdout +0.63 on alts <= -15%), so it is not a new lever; a regime brake on MN would meet the same 'bet smaller' line the other 16 brakes lost to. Live MN (main weekly -2.2%, +0.4%, -0.3%, -6.1% of start) sits in the bad end of that range, not outside it. No change proposed to any bot (freeze to 2027-04-09). Open and only the user can settle: whether the real Exness account is swap-free on USTEC (decides the NASDAQ core + NOISE path).

### 2026-11-02 (final) - "Run it" (many indicators together) and "analyse the Analyst desk": a low-volatility tilt that is real in ranks and not tradable at significance; the desk loses on geometry and fees (`backtest/indicator_model.py`, `backtest/analyst_review.py`)

- **Many indicators together** (walk-forward ridge + gradient boosting on 32 price/volume features, PIT top-40 daily, refitted quarterly with an embargo, 2022-26 out of sample): 0 of 6 cells pass. My P2, P4, P5 were wrong - the daily rank IC is +0.10..+0.18 (t 5-14). Checked as a bug first: it is the single feature ATR% used with the NEGATIVE sign (low-volatility coins beat high-volatility ones in every year 2022-26), the combination adds about +0.015 IC, and delaying the entry by an hour / four hours / a day keeps 85-100% of it (not a closing-print artifact). The top-minus-bottom spread is too heavy-tailed for net t above 1.4 (best: gradient boosting H7 +62 / +153bp a week, t +1.0 / +1.4); long-only calm coins minus the universe +27 / +41bp a week (t +0.8). It is the repo's dead 'majors vs alts' dispersion in a wider costume, in a period (2022-26) when alts bled. Doc 02, two last entries. Tests 10, 18 of 18 mutations caught.
- **The Analyst desk, call by call** (52 calls, 48 resolved, their 1-minute paths): gross -0.10R a call, the 12bp fee 0.24R a call (11.7R of the -16.7R loss); the 16 calls with reward:risk above 4 (stops 0.15-0.5%, targets 4-16R away) went 0 for 16 and lost -20.3R on their own; the other 32 are +3.6R net. Winners were patient (median 8 h) and nine of twelve rode two market moves; losers moved the wrong way (median best 12% of the way to the target, only 4 of 31 touched it later), and widening stops makes the what-ifs worse. The data supports one fix: judge the subset RR <= 4 and stop >= 0.4% on the next calls (a filter of what the desk already logs; in-sample +0.1R net, t 1.2, unproven). The desk and its review (100 calls or 2027-01-31) are untouched. Nothing committed or deployed. Tests 6, 9 of 9 mutations caught.

### 2026-11-02 (night) - "$50 at 100x / 50x on BTC, liquidation far away, just wait": BTC reaches the level, and the wait rule loses (`backtest/wait_leverage.py`)

- The user's idea measured on 58,940 hourly BTC bars. **BTC touches the liquidation level within a day in 80% of entries at 100x, 50% at 50x, 12% at 20x, 2% at 10x** (within 30 days: 96% / 89% / 70% / 45%). The wait-until-+0.30% rule (no stop) wins 56% / 82% / 94% / 97% of tries at 100x / 50x / 20x / 10x and loses **-34.5% / -10.4% / -2.9% / -1.1% of the margin a try** (the loser loses everything; ten tries without a wipe-out: 0.3% / 14% / 53% / 76%); waiting costs $1.50 a day in funding on $50 at 100x. The retail-RSI shape: a high win rate ended by one total loss. Doc 02, last entry. Nothing deployed or committed. Quick check, no registered predictions (arithmetic); tests 5, 8 of 8 mutations caught.

### 2026-11-02 (last) - "Test it": the market-level fade of strong 4h up-moves is dead, and the sign is the other way (`backtest/market_fade.py`)

- The loose thread of both candle scans (41 of 50 positive-both-halves cells were shorts with zero excess) tested as a market rule: short the PIT top-40 basket after the equal-weight 4h return is z >= 1.5 / 2.0 / 2.5, hold 4h / 20h / 48h, circular day-shift null (1,500 shifts), three-fold bar (primary cell positive with t >= 2 and shift p < 0.05 on both halves, and 7 of 9 cells positive). **NO PASS: the primary (z >= 2.0, 20h) loses -1.22% / -0.60% a trade (tune / holdout), is negative in every year 2020-26, and its worst trade is -28.4%; plateau 0 of 9; BTC alone has the same sign.** After a strong 4h up-move the basket continued up (about +1.1% / +0.5% over 20h) - what the trend book already trades. The mirror (long after strong down-moves) works on the tune half only (shift p 0.001-0.003) and is gone since 2024-08. Predictions T1-T4 all right. Doc 02, last entry. The candle thread is closed: three tests, 0 candidates. Nothing deployed or committed. Tests 9, 17 of 17 mutations caught.

### 2026-11-02 (later) - "what about testing these on candle charts" (cut losers, let winners run, risk 1R): the shape adds nothing to the management (`backtest/candle_manage.py`)

- The user, after hearing the trend book already is stops + breakeven + wide trail + fixed-risk sizing: test candle entries WITH that management. `candle_manage.py`: the 17 patterns as entries, trend management (2 ATR stop, +3R breakeven, 20 ATR trail) and scalp management (1 ATR stop, +2R target), 1R per trade, fees in R, control = the same management from random entries at the same entry day x slot. **PASS 0 of 204; no cell has excess over the random entries with t >= 2 on both halves.** Predictions R1, R3 right; R2, R4 (half), R5 wrong - doc 02, last entry.
- **The management is a regime bet:** random daily longs with the trend management made +0.737R a trade on the tune half and -0.195R on the holdout; every long combination is negative since 2024-08, the five non-negative holdout combinations are all shorts. 41 of the 50 cells positive on both halves are shorts with zero excess: being short after broad up-moves pays on every coin alike. That is the second exit rule pointing at the same loose thread as `candle_scan.py`: a market-level fade of strong 4h up-moves (best Holm 0.05 over 204 cells, found after looking, untested as a market-level rule, squeeze tail). Nothing deployed or committed. Tests 11, 19 of 19 mutations caught.

### 2026-11-02 - "did we test candle chart patterns": partly; now fully - 204 cells on the PIT top-40, nothing passes, and the first run's "replicated edge" was a control leak (`backtest/candle_scan.py`)

- The user asked whether candle patterns were tested; the honest answer was 'only at one NASDAQ trader's moments (`his_1m.py`) and one daily hammer screener (`stockbee_crypto.py`)', then "Run the scan". `candle_scan.py`: 17 textbook patterns x both sides x 1h / 4h / 1d x 1- and 5-bar holds, entry at the next open, 12bp + funding, tune / holdout, Holm over the cells; predictions K1-K5 registered first (prior under 5%). **Final result (control = entry day x slot): PASS 0 of 204; no cell keeps an excess over its matched baseline on both halves; |t| >= 2 hits are at chance.** Doc 02, last entry, has the numbers and all predictions scored (K1, K2, K3 right on the final run; K4, K5 wrong).
- **The first run said otherwise and was wrong:** with a DAY-matched control it showed 27 'information' cells, led by fades of strong 4h candles (+0.3..+0.6% excess, 24,557 / 11,881 trades, t up to +8). `candle_scan_check.py` (post-hoc, predictions first) matched the entry SLOT too and the excess fell to -0.07..+0.06%: the patterns cluster on market-wide moves in particular slots and the day-wide average does not contain the market's reaction at that moment. Control amended, whole table re-run, first-run log kept as `logs/candle_scan_daymatched_superseded.txt`; trap added to s3. Not driven by a few days, one coin or one year - the control was the bug.
- Loose thread, untested and low prior: a market-level fade of strong 4h moves (net t 1.6-3.2 per half at 20h before any multiple-testing correction). Nothing deployed or committed; 3 new logs in logs/. Tests 16, 24 of 24 mutations caught.

### 2026-10-31 (later) - "dashboard isn't looking any good": both accounts -17%, one micro-cap squeeze; nothing broken

- Read-only, 2026-10-30 22:50 UTC (feed: `ssh forexbot-vm 'cd /opt/forexbot && ./.venv/bin/python dashboard_push.py --print'`, plus `deploy/verify_status.sh`). Main $248.75 (-17.1%, day 22), fresh $247.73 (-17.4%, day 14, -24% from its $326 peak); both at the 7.3rd percentile of
  their scorecard band ("below", not under the 5th). All services active, 0 restarts. Main is $12.55 under the day-45 line ($261.30, read 2026-11-23 00:04 UTC). Today: main -$12.75, fresh -$20.24.
- By book (main / fresh): MN -$23.7 / -$25.9 (11th / 6.7th percentile), daily Bollinger -$14.5 / -$14.0, trend -$19.9 / -$20.3; carry +$2.9 / +$17.8 (95th on fresh); NDX dip +$6.0 on main; sleeve / capit2 / news idle by design. Today's hit: SOPH (a micro-cap) +57% against its 10-29 close
  squeezed the MN short leg; BTW -27% and AKE -37% on the MN long side; the crowd book's BTW / USELESS longs -$8 on fresh.
- **The +50% MN short exit worked on main (17:28 UTC, SOPH opened .001412, -$10.48 booked) and did not fire on fresh - by design, not a bug.** Fresh's SOPH short opened 2026-10-24 at .001615, so its exit level is .0024225; the PERP (what the bot reads) traded 4-5% under spot and touched that level
  for two 1-minute bars (18:29-18:30) while spot sat above it for 45 minutes; the bot polls every 120 s. Replayed on fresh's saved state, `mn_squeeze_exits` fires at a price of .0025. A brief spike through a poll-based exit can slip between polls; not changed (code freeze, doc 22).
- The dashboard's MN "entry" is the last DAILY mark, so SOPH reads -57% against the 10-29 close; against the basket's open it was about +37% at reading time. Trap: do not compare spot klines (data-api.binance.vision) with the bot's perp prices on a micro-cap spike - use `fapi.binance.com/fapi/v1/klines`.

### 2026-10-31 - "Binance was hacked and the bot took no trade on it": seen, tagged `hack`, not a traded type; history n=1 (read-only, no code)

- The news book (`news_books.py`) trades only `adds_products` + `monitoring_tag` notices (short the coin, long BTC). On 2026-10-30 02:26 UTC it logged id 9100 "Security Incident Update" as `hack`, `coins: []`, `traded: false` (dashboard feed, `accounts.main.news.recent`): an exchange-level incident has no coin to short.
  The archive (8,394 Binance announcements) has one real exchange hack episode (May 2019) plus four operational suspensions - too few to test; BNB / BTC after them moved wildly with both signs (1 h BNB -853..+467bp; today's incident: BNB +69bp, BTC +79bp at 1 h, no sell-off). Coin-tagged hack headlines (n 3,806) drift -31bp at 72 h / -59bp at 7 d, ~10x below the traded types (`logs/news_impact.txt`).
  Nothing built or changed; a paper 'watch' of hack headlines is the only cheap option and was not made. Throwaway script, numbers re-derivable (memory `news-book-scope-hack-news`). Trap met: a float `startTime` made Binance's klines endpoint reject every call and my `except` swallowed it - print errors, pass ints.

### 2026-10-30 (evening) - "BTC is down, why is the bear book not on?": the sleeve's label is slow on purpose; faster labels tested, none better (`backtest/bear_label_test.py`)

- The user (BTC ~$77k after a -4% day): the bear sleeve did not activate. Read-only (dashboard feed via `ssh forexbot-vm 'cd /opt/forexbot && ./.venv/bin/python dashboard_push.py --print'`, the web app needs a password): sleeve $0.00 booked / open on main and fresh;
  the paper book's `logs/combo_sleeve.csv` says CHOP every day since at least 10-23. **The label is BEAR only if BTC's close is under its 50-day average AND that average is down > 2% over 20 days**: on the 10-29 close BTC was 4.8% under it but the average
  was still +1.5% over 20 days. Breadth20 was 8.3% (under the 10% line), so the long side would open the day the label flips - about 21 daily closes at $77k flat (~11-19 Nov), sooner if BTC falls further. The trend book's 1000h gate (-6.9%, quarter risk) is a different switch and IS on.
- **Faster labels, 12 cells x 2 instruments x 2 cut-off sets: no candidate** (doc 02, last entry). The live label has the best Sharpe in 3 of 4 tables; labels that would be on today (BTC under its 20/30/42/50-day average, no slope) earn more raw return only with 45-70% falls and
  worst weeks of -22..-32%, and the live sleeve scaled to the same fall beats them 2-3x; their extra days earn about nothing. The live label reproduces doc 13's old numbers to the decimal under expanding cut-offs. Side observation: the bot's FIXED cut-offs (0.10 / 0.288) run a 30% fall
  and Sharpe 1.07 where the expanding ones run 20% and 1.24 (same CAGR) - not acted on (code freeze to 2027-04-09).
- Predictions in the file's docstring first: F2 (no candidate) right; B0, F4, R1 each half wrong. Nothing deployed or changed; the 'wait and watch' is the plan: if the sleeve switches on around mid-November, that is the design working. Uncommitted.

### 2026-10-30 (last, fourth) - the order-flow study guide, Module 5: the recorder, the audit and the feature sampler (`orderflow/`)

- The user: "Module 5". Built and tested a PUBLIC-DATA-ONLY package `orderflow/` (no keys, no orders; see the s4 entry), after probing the live Bitget feed BEFORE designing (four throwaway scripts), which changed the design three times.
  **Measured on the live feed (2026-10-30, five trials, 220,000+ updates, 0 `pseq` chain breaks):** the `books` channel has NO checksum (fields asks / bids / ts / seq / pseq); updates come in ~100 ms batches; the snapshot is 200 levels a side (BTC 500), which covers
  only 18-32bp on BTC, 39-55 on SOL, ~165 on XRP, ~280 on DOGE/SUI, 345-471 on LINK, 1,000-1,450 on WLD/ADA, 1,800-2,750 on SHIB and 2,400-4,200bp on DOT (the registry's 2/5/10/25bp bands are covered for the eight alts; BTC's 25bp band is NaN in ~29% of seconds);
  local receive lag 118-154 ms (this PC's clock was 34 ms from NTP); disk 1.33-1.38 GB a day for the ten pairs (busy hours; D: has 172 GB); the recorder costs ~3% of one core and ~58 MB (flat after a 6-minute warm-up).
- **The audit story (R4 wrong, the better design came out of it):** the first audit, the rebuilt top 5 vs Bitget's REST order book, matched only 12 of 40 (30%) - the hot pairs never matched at ANY offset in +-4 s. Diagnosis by experiment: `seq` is GLOBAL across websocket connections, so a fresh snapshot from a SECOND
  short-lived connection must equal the rebuilt book at the same seq exactly - 9 of 9 probes, then 50 of 50 and 30 of 30 in the trials (89 of 89 in all, 0 differing). The REST book is not tied to the stream's state; do not audit against it. Also found: a malformed update with a valid chain position half-applied
  (parse first, mutate after - fixed); trade `ts` arrive newest-first in ~2% of multi-trade batches (the sampler sorts); hourly files now open with a book CHECKPOINT so any hour can be verified or turned into features on its own (tested live across 15:00 UTC); Python can load a STALE .pyc when a file is rewritten twice in
  one second at the same byte length (cost a false registry-digest failure; delete `__pycache__`).
- **Registry amendment (logged in AMENDMENTS, before any official data):** a UTC day counts for a pair only if its book was ready and no staler than 2 s in at least 90% of the day's seconds (`features.day_coverage`); digest re-pinned.
- Predictions R1-R7: six right, R4 wrong. Nothing deployed or committed; trial recordings are in strategy_analysis/data/orderflow_trial* (git-ignored). **The official recording has NOT been started: that fixes day 1 of the 10 tune days and needs this PC awake for ~40 days (user's decision; Windows sleep settings are the user's).** **PARKED at the user's word, 2026-10-30 ("we just wasted our time on it"): the order-flow project is not a route to the goal (CLAUDE.md s1: drop what does not take us there); the official recording was never started and nothing is running. Revisit only if the user asks, e.g. for H-exec (execution timing for the slower books).**

### 2026-10-30 (last, third) - the order-flow study guide, Module 4: the scientific protocol (`backtest/order_flow_registry.py`, `backtest/protocol_lab.py`)

- The user: "Module 4". `docs/27-order-flow-study-guide.md` now has Lessons 4.1-4.5 (hypothesis form; look-ahead and leakage; realistic backtests and fills; overfitting and the winner's curse; credibility, power and paper trading) and exercises E10-E12.
- **The criteria are code.** `order_flow_registry.py` registers H-imb / H-flow / H-approach / H-combo / H-exec before any order-flow data for the ten pairs exists (tune pairs XRP SUI LINK WLD, test pairs DOGE SHIB ADA DOT, controls BTC SOL; first 10 recorded days tune,
  later days confirm once). K1 honest day-clustered t >= the Bonferroni cut-off for its own cell count (2.99 / 2.94 / 2.24) AND shifted-null p < 0.01; K2 gross >= 2x the all-in cost AND net > 0 (H-exec: saving >= 1bp); K3 >= 20 confirm days, 200 trades, positive on 75% of days,
  same sign on 3 of 4 test pairs; K4 (H-combo) beats the best single signal at matched frequency. `judge()` applies them; a digest test fails on any silent edit. My priors are recorded in it (statistics 15-70%, pays after costs 1-3%, H-exec 20%).
- **protocol_lab on the DOGE teaching day (one pair, one day):** pure noise searched over 60 rules gives an in-sample winner of +2.92bp that delivers +0.04bp out of sample; the REAL search by raw mean picked a 36-trade 300 s rule (+3.60bp in-sample, -0.14bp out) over the genuine imb1 5 s signal (+0.79bp, se 0.06) -
  P2 wrong; choosing by t = mean/se found imb1 5 s (in-sample t 15.3, out of sample +0.79bp) while the best noise rule reaches t <= 2.7 in 90% of draws. The imb1 decile rule is right 76% of the time at 5 s (among non-zero moves) and nets -3.2bp as an ideal maker, -11.2bp as a taker.
  Detecting a real +1bp needs 37 / 195 / 432 / 1,892 independent trades at 5 s / 30 s / 1 min / 5 min; the registry's 20-DAY minimum, not the trade count, binds at the fast horizons.
- Predictions P1-P5: two clean, two half right (P4's hit rates and P5's null figures), one wrong (P2). Nothing recorded, deployed or committed. Next: Module 5 (the recorder: Bitget public `books` + `trade`, storage, feature calculators, event-time replay, paper trading).

### 2026-10-30 (last, again) - the order-flow study guide, Module 3: windows, persistence and the statistics of overlapping samples (`backtest/window_lab.py`)

- The user said "start" after Module 2's offer; `docs/27-order-flow-study-guide.md` now has Lessons 3.1-3.5 (windows: lookback vs horizon vs holding; persistence and decay; overlap and effective sample size; multiple testing; reliability vs profitability, ties and the clock),
  exercises E7-E9. W1-W6 registered in the lab's docstring first: five right, W2 half wrong (imb1's 5-minute IC is 0.057, not under 0.05).
- **Findings on the teaching day (DOGE 2026-06-01, 86,399 s; one pair, one day):** the mid moves like a random walk (std 1.0 / 2.3 / 5.6 / 7.8 / 17.2bp at 1 s / 5 s / 30 s / 1 min / 5 min) and does not move at all in 71% of 1-second windows -
  **a 1-second horizon cannot pay a 4bp cost**. Required IC to cover 4bp (maker, if filled) = 4 / (1.755 x sigma_h): 0.41 at 30 s, 0.29 at 1 min, 0.13 at 5 min, against imb1's observed .111 / .103 / .057 (0.27-0.43 of what is needed;
  the formula reproduces book_hist's +0.9bp at 10 s). The signal is strongest where moves are too small and the move is big where the signal is gone. imb1 persists ~1.3 s and carries the information; imb20 persists longest and predicts ~nothing;
  taker flow persists (lag-1 +.21 at 1 s, ~0 at 5 min) but predicts nothing (+.029). Overlap: naive t 34.3 vs honest 6.0 at 30 s; at 5 min naive 6.6 vs honest 1.0 and shifted-null p 0.149. 1,000 shuffled-feature cells: 46% pass |t| > 2 naively, 4% honestly;
  the best honest noise cell reaches |t| 3.8. 12 of the 20 real cells survive a 20-cell Bonferroni (all four book features, 1 s .. 1 min, none at 5 min) - and imb20 at 1 s (t +10.6) is worth 0.06bp: significant is not big.
- **Bug of mine, caught because one number disagreed with an earlier lab:** the flow feature included the trades of the second it was predicting (bin i happens AFTER the book row labelled i): IC +0.199 -> +0.029 once built from earlier seconds only
  (`known_flow_share`; a test fails on the old version). Design consequences for Module 4: test lookbacks {1,5,30,60,300 s} x horizons {30 s, 1 min, 5 min} (15 cells), two keys (honest t above the cell-count cut-off AND shifted-null p < 0.01), stratify the clock, split by whole days.
- Nothing recorded, nothing deployed. Next: Module 4 (hypothesis form and the formal bar), Module 5 (the recorder).

### 2026-10-30 (last) - the order-flow study guide, Module 2: the three signals and price impact, with a one-day wall lab (`backtest/order_flow_lab.py`)

- The user accepted the 10 pairs (BTC, SOL, XRP, DOGE, SUI, LINK, WLD, SHIB, ADA, DOT) and asked for Module 2. `docs/27-order-flow-study-guide.md` now has Lessons 2.1-2.5 (imbalance, walls / cancel vs execute, executed pressure,
  price impact, how they combine) plus exercises E4-E6, drawn from a real day so the numbers are not invented. L1-L5 were registered in the lab's docstring first: L2-L5 right, L1 half wrong (same-window correlation does not grow with the window).
- **What the day showed (DOGE, 2026-06-01 only; 2026-09-01 left unread for a later confirmatory look):** imbalance at the first snapshot was +0.996 at level 1, -0.045 over 5 levels, +0.083 over 20 (the sign depends on depth);
  taker flow and the same-window mid move correlate +0.38..+0.49 (3-4bp per $100k) while the next window's correlation is -0.085..+0.036; 2,288 walls (>= 5x local median, >= $20k), median life 15 s, 3% replenished, **99.8% of what left was
  cancelled - but only 188 walls ever came within 3bp of the mid and 12 within 1bp, and within 1bp 82% of what left was executed**. So a cancelled "wall" is mostly liquidity nobody tested: cancels are not evidence of spoofing, and the
  informative sample for any wall hypothesis is the approach event (~190 a day within 3bp on DOGE). "First seen" is not "born" (20 levels = ~20bp on a 1bp tick; 0.26bp on BTC, ~217bp on DOT): define everything in bp bands.
- Nothing recorded yet, nothing deployed. Next: Module 3 (windows, persistence, statistics), Module 4 (hypothesis form and the formal bar), Module 5 (the recorder).

### 2026-10-30 (later) - the order-flow study guide, Modules 0-1 (`docs/27-order-flow-study-guide.md`); a 16-pair spread survey

- The user (a full brief: monitor ~10 pairs, combine order-book imbalance, buy / sell-wall persistence and executed buy / sell pressure at 1 s .. 5 min, teach the concepts, then the scientific method, then the Python / WebSocket build; no real money,
  no trading keys): Module 0 states where the project really starts - `book_hist.py` (DOGE, 7 full days) already measured signals 1 and 3 (imb1 IC +0.10..+0.25, ~+0.9bp = one tick, taker -12bp, realistic limit fills -2.0..-2.4bp a signal, 0 of 4 days
  positive; flow aligned only DURING a move); **wall persistence, the 1 s / 5 min windows, ten pairs, the combination and execution timing for the other books are untested**. Proposed bar (0.6): flagged-subset gross move >= 2x the all-in cost, net t > 2 by
  day, >= 3 of 4 held-out days, same sign on >= 3 unused pairs. My prior: under one in ten for a retail-tradable result; the plausible use is execution timing (H-exec). Module 1 = orders / spread, the cost stack, expected value (8-part lessons + 3 exercises).
- `backtest/pair_spread_survey.py` (public tickers, 24 samples, 2 minutes): BTC / ETH / SOL 0.01 / 0.05 / 0.10bp; XRP .82, SUI 1.15, LINK .93, AVAX 1.2, DOGE 1.33, LTC 1.81, SHIB 2.18, WLD 2.63; ADA 5.3, DOT 10.9; best-level depth often under $300.
  Proposed 10: BTC, SOL (controls), XRP, DOGE, SUI, LINK, WLD, SHIB (one-tick alts), ADA, DOT (wide). Modules 2-5 (signals, statistics, protocol, build) not written yet. Nothing recorded, nothing deployed.

### 2026-10-30 - the Analyst desk's liquidity sweep with seven confluence factors: the information is real and small, nothing lifts it above the fee (`backtest/sweep_confluence.py`)

- The user (about the desk): "I see potential in the liquidity sweep; combined with other factors we can make the signal better - possibly a good signal generator for less capital". Registered first (factors, directions, stage rules, Q1-Q5 in the file's docstring),
  then run on the PIT top-40, 60,664 sweep events 2020-2026, T24 and TP2 exits, 12bp + funding, matched controls, tune / holdout. **Sweep vs random entry: +5..+25bp (real); gross edge +0.19% long on the tune half, -0.08% since 2024-04; 0 of 14 factor cells confirmed;
  the tune half selects no long factor; the one short stack nets +0.05% / -0.05%. The only significant holdout cell is negative: long sweeps in a market-wide flush (15+ coins at once) -0.59% a trade (flip from +0.21% on tune).** Not tradable. Doc 02, last entry.
- **Bug of mine, found at the first printout:** `t_by_day` averaged day means while the printed mean was per trade (a negative net printed a positive t). Now the per-trade mean with day-clustered errors. `sweep_reclaim.py` has the same convention: its t values (+7.3 / +4.6) overstate, its means do not.
- Not tested (no hourly data): open interest / liquidation volume at the sweep, order-book depth, weekly levels. Prior: low, seven of seven natural factors were null and a filter must lift the gross edge from ~0 to over 0.3% a trade. The desk keeps running to its review (100 resolved calls or 2027-01-31).
  Nothing deployed, nothing committed.

### 2026-10-28 - the order-book checklist on back data: the one-tick signal is real and stable, the tape fills the wrong side (`backtest/book_hist.py`)

- The user pasted a 4-step order-book checklist, then "can't we do it on the back data". Source: Tardis.dev's free first-of-month Bitget DOGEUSDT days
  (range-GET works, HEAD answers 404; `strategy_analysis/data/book_hist/bitget/`, 527 MB, gitignored): 7 days 2025-03 .. 2026-09, 95M rows, the complete tape.
  Tune 2025-03/06/09 (thresholds only), unseen 2025-12 / 2026-03 / 2026-06 / 2026-09. Predictions in the file's docstring first. Doc 02's last entry.
- **Result: dead for retail, on a stronger footing than 10-09.** imb1 -> next 10 s: IC +0.10..+0.25 and +0.9..+1.0bp on all four unseen days (about one tick, 1.2bp);
  a queue-aware limit at the touch fills 20-22% and the fills are the signal's failures (-4.8..-5.1bp worse than the unfilled, about -3bp before fees);
  net -2.0..-2.4bp a signal, 0 of 4 days positive in all 8 variants. A zero-fee venue would not rescue it. Event study (E1) mostly wrong: the spread stays one tick, only flow DURING the move shows.
- **Trap met:** Tardis' Bitget `incremental_book_L2` is top-15 SNAPSHOTS ~6.6/s (not diffs) until at least 2026-03; only 2026-06-01 and 2026-09-01 are real diff streams. "Check the book at reconnects" is meaningless on the first kind. The rebuild is exact on 2026-09-01 (touch equals Tardis' snapshots 100.00%, 86,399 s) and resyncs at snapshots.
- A background run died silently after 3 of 7 days (exit 4, no traceback); the rerun finished from the cache. Read a "should finish by itself" claim only after the notification.
- Not done, and only measurement: a live diff-stream recorder (Bitget `books`, `seq`/`pseq`) for a true rebuild test. Nothing deployed; `tests/test_book_hist.py` 9 tests, 12 mutations caught. Uncommitted.

### 2026-10-28 (later) - gold first: CME open interest from Databento ($1.01), the pending roll vs the calendar spread - no lead; net-short half untested

- The user found where the CME history was: Databento (key in the environment; checked read-only, quotes free). "Gold first" -> `GC.FUT` statistics 2010-06..2026-10-26, $1.01, 231 MB. `backtest/gold_roll.py` (G1-G5 registered first,
  `tests/test_gold_roll.py` 8, 10 of 10 mutations caught): 51 cycles 2016-2026, managed money's net futures lots / the delivery month's open interest vs the change of the Feb-Dec-type spread into first notice:
  IC +0.14, p 0.16, tune +0.31 / holdout -0.19; the spread trade loses -$43 a cycle after $30; the outright shows nothing. **NO LEAD.** The roll itself is real (2% of the month's open interest left at first notice).
- **Data traps met:** the feed has NO open interest before late 2015; CME's web page shows open interest one trading day later than the feed's date (three totals matched exactly) - the `logs/cme_snap` files are labelled one day late (README
  corrected); the test reads the previous day's open interest. A first run crashed on all-NaN open interest (2010-14) before this was handled; fixed with a test that fails on the old code.
- **Next, if the user approves (a spend): palladium + platinum, $0.48** - gold was net long in 46 of 51 cycles, so the 'short crowd buys the delivery month back' half (palladium's case) is untested; the other three metals are $3.70 more.
  Cheap daily top-ups (about $0.001 a day) would keep the record going without the browser. Nothing deployed.

### 2026-10-28 - the metals positioning tool: CFTC + CME, tested; no lean; the side that MUST trade is knowable, the price direction is not

- The user (a screenshot of the CFTC Disaggregated report for 2026-10-20 - palladium and platinum - and CME's Final Settlements page): "make futures positional data from it, compute and correlate
  both, say how to test; the tool must tell me which side will have an imbalance, beforehand". `backtest/cot_metals.py` (predictions P1-P6 registered in the docstring first) tested managed-money
  crowd rank, swap-dealer rank and positioning change on platinum / palladium / gold / silver / copper, 956 weeks, 4-week horizon, 12bp, circular-shift null, tune / holdout:
  **0 of 15 cells pass on ETF and on futures prices; best Holm-adjusted p 0.80.** P4 wrong (positioning momentum has the registered sign in 1 of 5 markets). Palladium's 'extreme' net short
  (-47% of open interest) is the 28th percentile of its own last 3 years.
- **CME has no free history:** the settlement feed keeps 5 trade dates (read from a script inside the cmegroup.com page in the browser pane - plain scripts get 403, not worked around), delivery
  history is paid DataMine. `logs/cme_snap/` is a RECORD from 2026-10-27 (palladium December = 92% of open interest, first notice 2026-11-30, managed money's net short = 50% of that month to be
  bought back; platinum's January -> April roll already under way). `positioning_lean.py` prints the crowded side, the history, the verdict and this CME block; the pending-roll side is arithmetic,
  not a price forecast. **Keep the record going** (one snapshot a day or a week; it cannot be rebuilt) - it is the only way to test roll pressure.
- Nothing deployed, nothing running, no orders. New: cot_metals.py, positioning_lean.py, tests/test_cot_metals.py, logs/cme_snap/, logs/cot_metals.{txt,json}. Doc 02 last entry.

### 2026-10-27 (evening) - the machine's years without the hindsight coin list (`backtest/pit_years.py`)

- The user asked for the machine's year-by-year results, then: "are these really the current strategy on previous years?" and "re-run with
  coins chosen point-in-time". The published yearly series (all_books, fixed $300: 2020 +875, 2021 +2,386, 2022 +232, 2023 +780, 2024 +2,208,
  2025 +1,287, 2026 to Sep +632) trades the trend book on blend.BOOK (picked in 2026) with gains shrunk 3x. Compounded, the same series reads
  $300 -> 197 million x over 2020-26 - arithmetic with no capacity limit; quote fixed-stake years, never that.
- **Point-in-time** (each month the 12 most-traded alts by the prior month's volume, today's rules, no shrink; check: the hindsight coins
  through the same pipeline reproduce the published trend book within 4%): machine 2020 +723, 2021 +2,939, 2022 +365, 2023 +915, **2024 +834**,
  **2025 +2,228**, 2026 +566 - total +8,645 vs +8,385. The total survives; the years move: 2024's money was hindsight coins (SUI / ENA / WLD),
  and 2025's is mostly MYX (76% of that year's winning long R; without it 2025 +1,558). Y4 / Y6 wrong. Doc 02's last entry.

### 2026-10-27 (afternoon) - the Analyst desk's verdict test amended: same-day, same-direction calls are one bet

- Review of the night's session and a read-only check (verify_status.sh, the feed): all services up, the desk ran every hour without an error, the feed
  pushed every minute. The desk's first 6 resolved calls showed the flaw: four SR shorts (XRP, gold, ETH, SOL) stopped within 21 minutes by one move,
  and A1's z-test counted them as four independent bets - more certain than the data, in either direction.
- **Amended at the user's word, 2026-10-27 13:56 UTC, with 6 of 30 calls resolved:** `analyst.day_bets` groups calls by (UTC day made, side); each
  group = one bet (its hit rate minus its average random baseline); `bet_p` = one-sided Student's t over the bets (`t_upper`, standard library -
  the VM has no scipy; checked against scipy to 1e-9). `stats()['p']` is the new p (the verdict and the review read it), `['p_calls']` the old
  one, `['bets']` the count; per rule too (A3). Written into the docstring, doc 22's override and STATUS. The replay's logged p values predate it
  (per call; none under 0.37). tests/test_analyst.py 26 (6 of 6 mutations caught); the dashboard tab says how many bets the calls make.
- Not seen rendered: the dashboard (live and local copy) is behind the password, and reading even the local test password was refused - the
  user signs in to look. `next build` passes.

### 2026-10-27 (night, last) - the Analyst desk built: levels and predictions on the dashboard, a separate paper book (NOT DEPLOYED yet)

- The user: "show it on the dashboard in real time - support / resistance and expected movement per the analysis - the bot first predicts, then records how many
  times it was right and how much it would have made on paper, a separate book from fresh and main". Built as `analyst.py` (the engine) + `dashboard_push.analyst_view`
  (the feed) + a dashboard tab "Analyst desk" + `deploy/analyst-paper.{service,timer}` (hourly at :07, stdlib only, MemoryMax 120M). Everything is registered in the
  file's docstring before the first call: three fixed rules, A1-A4 (expected: no edge at 12bp - the repo's own tests of these ideas are all dead, doc 02), review at 100
  resolved calls or 2027-01-31, retired if average R <= 0 or p >= 0.05; never real money. Not part of main or fresh; touches no bot (doc 22 override, same kind as the crowd book).
- Honest framing on the page itself: "expected movement" = the nearest levels and a typical day's size (1 sd of 14 daily moves) - context, not a forecast; each open call
  shows the odds a random entry with the same stop / target / hours would have, and the break-even hit rate. A call that would push open notional past 3x the book is
  still scored as a prediction but takes no paper money ("not booked").
- Tests: `tests/test_analyst.py` 13 (the survivor of 14 mutations is an equivalent mutant), `tests/test_dashboard_push.py` +3 (10 of 10 mutations of `analyst_view` caught);
  checked in the local preview harness (desktop and 375px phone width, no overflow) on live Binance levels plus sample calls. `.gitignore`: `logs/analyst/`, `logs/desk/`.
- **DEPLOYED 2026-10-26 22:45 UTC at the user's word ("deploy it"; commit `ae96a46`, committed directly on main because local = origin).** VM fast-forwarded from `a100fa2`, tests 24 + 13 + 14 pass
  there, every bot / paper-book file byte-identical, no service restarted; `analyst-paper.service` run once by hand (0 calls, book $300), `analyst-paper.timer` enabled (hourly :07); the feed
  payload carries `meta.analyst` (5.1 KB gzipped meta in all); Vercel "Deployment has completed". The same pull brought the two older commits (the Polymarket scan, the dashboard's carry
  short-exit label fix). `verify_status.sh`: all services active, code identity matches, the one 'restart pending' (main, 10-22 code) is the documented one. STATUS.md updated.

- **Leverage and capital, replayed (the user: "10x 20x 30x, capital $20 / $50 / $100 / $300 - how would that result in"; then "deploy it").** `analyst.scenario / grid / leveraged_result`
  (the whole account on each call, one position at a time, liquidation from each call's worst move `mae`, fee 12bp x leverage) + `backtest/analyst_replay.py` (the same rules over 4.7
  years of 1h candles: **10,580 calls, 18.0% right vs 30.8% needed, -0.20R each; 10x / 20x / 30x all wiped out; 1x a typical 0.39x year; the desk's own 0.5%-risk book -3.3% a week**) +
  `analyst_replay_1m.py` (the same calls on 1-minute candles: +0.4 points - not a scoring artifact). Dashboard: a "What if the whole account went on every call?" card (live record
  and history replay tabs). **Two bugs of mine found and fixed first:** a BTC cache left by a `--sample` run (BTC covered 2025 only) and a baseline measured on hourly bars while the calls
  are scored on minutes (`desk.minute_baseline`). Wrong predictions kept in doc 02: A8, M1, A4's top end. tests/test_analyst.py 24 (incl. 18 of 18 mutations of the leverage code
  caught), test_desk 13, test_dashboard_push 14. **DEPLOYED 2026-10-27 at the user's word ("deploy it")** - see STATUS.md for the commit and the first run.

### 2026-10-27 (night) - the desk: chart-reading calls, planned in advance and scored

- The user (bot aside): "sit and analyse the charts - support / resistance, Fibonacci, smart money - and when it clicks open a trade, with the loss level and the profit level
  calculated". The repo's evidence is that none of those carries an edge after costs on its own (doc 02; `ict_fvg.py` today, `odds_now.py`, `his_ta.py`). What can be
  done honestly is the PROCESS and its measurement: `desk.py` prices a plan (size for the risk chosen, fee in R, break-even win rate, liquidation distance vs the stop,
  the stop in hourly ranges) and the BASELINE (how often a random entry with the same stop % / target % / hours hit the target first on the coin's last ~21 days -
  e.g. 7% for a BTC long with a 1.5% stop and 3% target over 48h on 2026-10-27), logs it as a PAPER call, and `score` resolves it on public 1-minute bars with
  pessimistic rules (a bar touching both = loss, gaps exit at the open, expiry, no-fill). Verdict only after 30 filled calls; D1-D3 (none clears it, average R
  negative, 2R+ calls below break-even) registered in the file. No keys, no orders, ALLOW_REAL untouched; not advice - a record. Forex majors are not on Binance (MT5 later).

### 2026-10-27 (later) - the convexity finding acted on: waiting priced, the day-45 line priced, the "fuel" readable but not tradable, a gauge built (not deployed)

- The user: "do something about the most useful finding" (`residual_edge.py`: the machine's return is a few explosive alt months, not BTC exposure). `backtest/convexity.py` on the machine's cached daily account series (10 orderings, `logs/daily_combos_cache/machine_account_daily.pkl`) and `backtest/runner_gate.py`; predictions first; full table in doc 02's last entry.
- **Priced, backtest-conditional ("if it works as backtested"):** the best 5% of days carry 126% of the log growth; the account is below its peak 88% of days, longest stretch without a high 248 days. **The day-45 line (doc 22 s3b, NOT moved): 9% of backtest windows sit under -12.9% at day 45; of those 73% are above their start by day 180 and 99% by day 365** (over the line: 96% / 100%). Today's analogue (13-18% down at day 17): 67% were over the line at day 45, 87% above start by day 180.
- **The fuel:** the share of the PIT top-40 already up >20% in 30 days predicts the trend book's NEXT month (Spearman +0.35 / +0.46 on the two halves; lowest third of readings: mean -0.5%, median -5.2%, 18% of months up; highest third: +69% mean, 70% up). **Killed windows that were also LOW-fuel at day 45 recovered slower: above start by day 180 only 57% (median +10%) vs 78% MID, 94% HIGH; all back by day 365.** Live: 5.1% running (percentile ~18-28), median coin -19% in 30 days, both trend books net SHORT the large caps (+$6 open on main) with no long runner = the LOW state; a drought is the expected experience.
- **Not tradable:** `runner_gate.py`, trend longs x0.5 in LOW / x1.5 in HIGH through the 4-phase x 10-ordering defence machinery: NO GATE - LOW x0.5 beats the line on the holdout (+58..+90 points in all 4 phases) and loses it on the tune half (-69..-164): the mined-holdout signature. The fuel is something to READ.
- **DEPLOYED 2026-10-27 at the user's word (commit `a100fa2`, only the gauge on top of `a773935`):** `news/mood_now.fuel()` + `news/fuel_bands.json` + a "Trend-book fuel" line on the dashboard's mood card (`dashboard/app/Dashboard.js`) + `backtest/convexity.py`. `tests/test_mood_now.py` 8 pass (4 mutations caught), `tests/test_dashboard_push.py` 9-10, `next build` OK; on the VM the tests pass, a mood snapshot carried `fuel` into the feed payload, every bot and paper-book file was byte-identical before and after, nothing restarted; Vercel: "Deployment has completed". Built in a separate worktree on top of `origin/main` so the older unpushed commits (Polymarket scan, dashboard short-exit label fix - the user's earlier "not yet") did NOT go to the VM. Display only; no book reads it. **The user could not find it** (it was only on the Mood tab): `9873966` adds a "Fuel LOW" label to the top bar of every tab, checked in the local copy with a real snapshot (main / fresh / Mood on desktop, fresh at 375px) before the push - the harness is `dashboard/.local/serve.cjs` (`dashboard-local` in `.claude/launch.json`).

### 2026-10-27 - the Claude trading skills checked: two repos read, nine rule sets tested, nothing new to run; one real small gap effect that is NOISE

- The user: "check all of them and see if we can take something from them, and do not assume that because we tested something already it is certified wrong." Read (untrusted, scratch copies, nothing executed): tradermonty/claude-trading-skills (74 skills) and SKE-Labs/agent-trading-skills (56; its day-trading set is the "famous day trader skill"), plus the three directory plugins' pages. SKE's v4 skills are frameworks that repeat this repo's own protocol; tradermonty's are mostly US-equity screeners. Full table: doc 02 last entry.
- **Tested exactly as the skills state them, predictions first** (all files in `backtest/`, logs in `logs/`): `cot_shapiro.py` + `cot_shapiro_more.py` (Jason Shapiro's COT contrarian chain, steps 1 + 3, 13 futures markets, circular-shift null) NO PASS, tune 0.00% / holdout +0.10% a week; `dist_days.py` (IBD distribution days on QQQ / SPY / BTC) NO RULE, recent decade only; `crypto_regime_score.py` NO SIGNAL; `alt_rotation_gate.py` (breadth gate through the alt-bear defence harness) NO GATE; `stockbee_crypto.py` (hammer / burst) NONE PASS, burst long +0.56% t 0.9; `ict_fvg.py` DEAD (touch rates = random pullbacks); `residual_edge.py` (a method, not a rule); `ndx_gap.py` + `ndx_gap_check.py` (below).
- **`residual_edge.py` is the useful one:** the machine's backtest return is NOT BTC exposure (R2 0.02, beta 0.78); its giant months came with BTC flat or down (2024-12 +524% vs BTC -2.9%) - alt breakout convexity, dropping the best 3 of 78 months cuts the average month from +40% to +25% (heavy tails: the HAC alpha t of +3.8 is not a reliable measure), the median month is +7.8% (BTC +2.7%). This is why a BTC-bull / alts-down tape hurts without contradicting the backtest, and why 45 days is a noisy read.
- **`ndx_gap.py`: a CANDIDATE that is mostly NOISE.** NASDAQ gaps >= 1 x 14-day ATR, continuation after a 15 / 30-minute opening range: +22.7 / +25.7bp a trade, t 3.1 / 3.5, both halves t >= 2.1, Holm 0.02 / 0.00 over the registered 18 cells (my G1, "none pass", was wrong). `ndx_gap_check.py`: 14 of 16 years, plateau 10 of 10, S&P positive, DAX not, both directions, clean placebo, +23bp at triple cost - and a duplicate of NOISE (daily correlation +0.68; NOISE earns +10bp a day on the biggest-gap 6% of days = 26% of its profit). Worth +2.1% a year at 1x (8.3 trades a year); nothing deployed. Doc 02.
- **Plugins** (TradingCalc, TradeOS AI, Crypto Spot Futures Analyzer): descriptions only, nothing installed, no edge. **Added data:** `strategy_analysis/data/fx_macro/cot_more.csv` (CFTC legacy reports for gold, silver, WTI, S&P, Nasdaq-100, 10-year note). **Trap met again:** a Bash heredoc with backslashes aborted a patch before writing (the s3 row on heredocs) - the Edit tool did it.

### 2026-10-26 (later) - the dashboard read for itself; the dip-buy on other tradfi series: dead; the funded-account route: a lottery unless there is no time limit

- The user: "you have the dashboard, see for yourself what is working and what is not, find hidden clues, try forex again, there is huge potential". The web app needs a login (no password entered); the same snapshot was read read-only with `ssh forexbot-vm 'cd /opt/forexbot && ./.venv/bin/python dashboard_push.py --print'` plus `deploy/verify_status.sh` (14:23 UTC). Nothing deployed, restarted or bought.
- **Read.** Services 7 of 7 active, 0 restarts, ~160 MB free, disk 9%. **Main $254.82 live (-15.1%, day 17.6, 8.4th percentile = "below"; $6.48 under the day-45 line); fresh $279.97 (-6.7%, day 9.6, 18.8th, "below").** Working: crash bids (+1.90% Bitget, 63 fills at +1.21% each), the NASDAQ dip-buy (+$5.87, one trade, main), carry on fresh (+$7.20, 85.9th). Not working: trend (-$25.9 booked, 13 of 51 won), daily Bollinger (below its range on BOTH accounts, 17.8th / 11.6th; 1 of 8 closed trades won; the 10-08 audit already flagged it "picked after looking"), carry on main (-$8.6: BULLA +55% closed at the +50% exit, -$2.12), MN (-$9.0 main). Idle by design: capit2 (needs a -10% day), sleeve (BTC label BULL), news (23 headlines in 7 days, none of its two types). The two accounts run the same book rules and differ mainly by start date (fresh also has the coin map and the crowd book): -15% against -7%.
- **Checks that came back clean:** "today" -3.70 on main and +3.70 on fresh is a coincidence (hourly curve checked); the crowd book's first live anchor (Mon 10-26 00:00) opened IDENTICAL legs in the standalone book and inside fresh (21 each: 10 long, 11 short; entries within a minute); standalone $299.24 after one day (BTW -19% in 14 hours is the drag).
- **`backtest/stock_dip.py`** (the running QQQ rule, frozen, on 81 tradfi series): **dead** - broad ETFs 0 of 4 pass both halves (QQQ +0.60% t 2.5 / +0.31% t 1.6), commodity ETFs 0 of 8 (pooled -0.34%, t -3.0), 69 stocks pooled +0.18% (tune t 2.2 / holdout t 0.8; 4 of 58 individually = chance). Under 12bp + 3bp a day the running NDX book is worth ~+4% a year at 1x. The bounce is an INDEX effect. D1-D4 right, D5 wrong. Doc 02.
- **`backtest/prop_pass.py`** (NOISE through the published two-step funded-account rules, with a zero-edge control): **with a time limit it is a lottery** - 21 days a phase passes 0-10% (control 0-7%), 42 days 0.3-18% (control 0-11%); the edge adds 0-7 points and leverage sets the odds. **With NO time limit the edge adds 17-46 points at k >= 2** (x2: 58% vs 23%, median 199 days; x1: 66% vs 45%, 432 days), and a funded year at x2 pays 14.7% of the account with 25% blown; x3 is blown 85%. With an assumed 1.2% fee: 3-7x the fee, 1.7-3.2x after halving for payout friction. Optimistic (close-to-close days, no commissions or firm rules). Q1, Q3, Q4 right; Q2, Q5 wrong. Doc 02. **Nothing here is a firm's honesty or payout record - the user must read the real terms; pass rates reported by the industry are 5-14%.**
- **Forex, what is left (the honest list):** (1) whether the REAL Exness account is swap-free on USTEC (Pakistan accounts are widely reported to be auto swap-free; USTEC unconfirmed) - decides the NASDAQ core + NOISE path (+32%/yr, fall 33%, mostly beta, ndx_swapfree.py); (2) retail long/short history is not freely downloadable (Dukascopy shows only 4 checkpoints), so the FX crowd idea can only be tested by RECORDING `sentiment_rec.py` again (it died after one day, 2,660 rows); (3) a funded account needs a no-time-limit firm. No new currency rule was run: every family in doc 02's forex entries stands.

### 2026-10-26 - Polymarket structure scan (`poly_structure.py`): sum gaps dead, reward quoting unproven

- The user asked for other markets to run bots on ("niche trading markets"); picked Polymarket STRUCTURE (identities, not
  predictions - every directional test there is dead). Read-only; fee = shares x rate x p(1-p), taker only (docs); depth
  walked; venue minimum respected. Predictions and verdict rules in the file's docstring BEFORE the first run.
- **NO basket (instant, via neg-risk conversion): 669 priced, 0 positive after fees, closest -0.1 cent; 30-minute watch of
  222 near-break-even events: 1 sample in 9,212 positive, 0 episodes. YES basket: 3 executable, all 1.2-2.0% a YEAR (432-day
  and 157-day bonds), held unchanged for the whole watch = time value, not a gap. 0 episodes worth taking** (rule amended
  after the census, before the watch: YES baskets must clear 15% a year). NO books are exact mirrors of YES books.
- **Rewards: upper bound looks large (median 1.12% a day, 0.60% contested) but the median pool pays $0.17 a day to a
  minimum-size quote, and a rough touch cost on a random 150 markets gives net -0.80% a day.** The registered rule passes on
  4 of the top 8 (picked on pool size); the random sample does not. Unproven; needs a forward PAPER quoter on the trade tape.
- Predictions: P1 half right, P2 wrong (median episode 575 s - the long ones are the bonds), P3 wrong on the upper bound,
  P4 right for sum gaps. Nothing deployed, nothing running, no orders; STATUS.md unchanged. Raw data in
  strategy_analysis/data/poly_structure/ (gitignored); summaries in logs/poly_structure_{census,watch,rewards}.txt.
- **Dashboard label bug, FIXED IN THE CODE, NOT DEPLOYED (2026-10-26):** `dashboard_push.closed_trades` showed the carry
  book's +50% squeeze exits (`why="short_exit"`, always shorts) as "long" - today's BULLA exit (-55%, -$2.12) and 10-14's
  BTW. The log has no side column and only news / crowd shorts were recognised. P&L and % were always right. Fixed in
  `dashboard_push.py` (reads `why == "short_exit"`), `test_closed_trades_label_every_short_a_short` fails on the old code
  (9 tests pass); checked against the VM's real log (both carry exits now read short). The VM's `forexbot-dash.timer` picks
  it up on its next `git pull` - the user said not to deploy yet. (MN's own short-leg exit writes no trade row.)
- Same day, in chat: collectables / "no-capital" ideas and whether the repo is a product (answer: not the bot as a money
  machine - no verified record, repo is public with no LICENSE; sellable as a validation/audit service, content, custom bot
  work, and later the forward record).

### 2026-10-25 (last) - the crowd book INSIDE the fresh account (`crowd_book.py`, `--crowd`, x1.0) - DEPLOYED

- The user: "add the crowd book to the machine now ... fresh only, full size". `crowd_book.py` = news/crowd_paper.py's
  rule as one more book of the netted account (Monday + Thursday halves, K 1.0 x account equity / 2 per half, the
  backtest's fee, funding at the close, live prices at the first poll after the anchor; > a week down -> only the latest
  anchor). Without `--crowd` nothing exists (main untouched). Dashboard: its own bar and positions; the scorecard leaves
  it out (cum crowd / crowd_fees). tests/test_crowd_book.py 8 tests, 7 mutations caught; all other suites pass.
- **DEPLOYED 2026-10-25 16:59 UTC (commit a0da49c)**: VM pulled, paper-book files blob-identical, tests pass on the VM,
  fresh state backed up (logs/backup_20261025-165930), deploy/combo-bot-fresh.service + `--crowd`, ONLY combo-bot-fresh
  restarted ("CROWD: book added", first anchors 10-26 / 10-29, 0 poll errors). Main NOT restarted, on purpose: it runs
  10-22's code (verify_status.sh's "restart pending" for it is expected). Fresh now also runs the 10-24 coin map (PEPE /
  RAY entered its ledger). Doc 22 s3b: fresh's 12-01 read is taken without the crowd book. STATUS.md updated.

### 2026-10-25 (later) - "this kind of market": common, usually survived (`backtest/market_now.py`)

- The user (dashboard, fresh account): "is it going good, and how often does this kind of market come?" Live 10-25 16:40
  UTC: fresh $275.90 (-8.0%, 8.6 days, 14th percentile), main $259.05 (-13.7%, 16.7 days, 10th; $2.25 under the day-45
  line). The market since 10-09: BTC's label BULL 14 of 17 days but BTC -2.5%; top-40 alts' median -9.8% (30 days -19.8%,
  15.6% behind BTC). Such 17-day stretches (BTC-BULL label, alts >= 5% behind BTC): 16% of all windows, 34 months of
  2020-26; the machine's median in them +7.1%, 39% down; the live -13.7% = their 16th percentile; after them the machine
  was up over the next 90 days 73-100% of the time in every period (sizes are bull-run backtest numbers). M2 wrong.

### 2026-10-25 - one status page (`docs/STATUS.md`): a documentation review checked, and the stale pages fixed

- The user pasted a review of the documentation (not of code or the VM): rigorous research record, but the "what do I
  trust now" pages disagreed. Checked and TRUE: `docs/00` was stamped 2026-09-23 and still described `longtrend_bot`
  as the live system; `docs/09` stopped at 10-09 and listed `combo-bot-demo` as running (stopped 10-17); the root
  README still carried the scaffold checklist (risk manager, strategies, backtester "unfinished"); `docs/README.md`
  listed 23-26 outside its reading order; this file's stamp said 10-12 over entries to 10-23.
- **Fixed:** `docs/STATUS.md` (what runs where, code identity, paper result beside its backtest, drawdown and gate, the
  dates, what waits on the user, how to read the numbers); `deploy/verify_status.sh` (read-only, one command, prints the
  facts the page quotes); the root README rewritten; banners on docs 00, 09 and 24 pointing at STATUS; the docs index
  regrouped with 23-26 in the main path. Everything on the page was verified against the VM, not copied from older docs.
- **Found while verifying (all on STATUS.md):** the main final-machine account's LIVE equity was $260.44 on day 15,
  $0.86 under the day-45 KILL line ($261.30, read 2026-11-23 00:04 UTC - not before); machine v2 (`combo_paper`) is at
  -30.2% on day 30 = the **1.6th percentile** of BULL-start 30-day windows (`backtest/combo_window.py --days 30 --live
  -0.3022`, `logs/combo_window_30d.txt`; registered guess 1st-2nd, right), so it is already under the 5th-percentile
  line that applies from month 3 (~2026-12-24); the pair's daily book is 0 for 6 closed trades (-20.5% avg).
- **Trap, new:** file modification times on the VM are useless for "did the process load the current code": a `reset
  --hard` on 2026-10-17 rewrote them without changing content, and a first version of the script raised four false
  "restart pending" warnings. The check now asks git what each service's files held at its start time (the HEAD reflog)
  and compares with now. Verified result: all six long-running services run the code now on disk; the VM (`dd5eaaf`) is
  four commits behind origin/main (`d5e1fb4`), and the only bot files that differ are the 10-24 real-order pieces.
- Nothing was deployed or restarted; every VM command was read-only.

### 2026-10-23 (later) - the sentiment engine finished: one lead (crowd positioning), chatter dead; a live readout

- The user: "better sentiment analysis tool - add all the good stuff, also get news from X". Doc 25 s7 has the table.
  `news/impact_by_source.py`: other exchanges' notices add little to Binance adds_products. `news/positioning_hist.py`
  (Binance metrics archive 2022-26): crowd-contrarian book +37 / +48%/yr, t 1.8-2.0 - a LEAD (funding + squeezes, mostly
  2025-26), no pass; taker flow IC +0.06, no book either way. `news/bsky_hist.py`: Bluesky chatter and tone, 25 coins -
  dead. X: no free legal source (official API / LunarCrush paid); not scraped.
- **`news/mood_now.py`**: live read-only readout - crowd long %, rank, funding, taker, OI per coin of the backtest's
  universe (top 40 by PRIOR month's volume, cached monthly in strategy_analysis/data/news/mood_pool.json), the crowd
  book's quarters flagged. Live endpoints checked against the archive. `tests/test_mood_now.py` (run as a script: no
  pytest on this PC) 3 tests, 3 mutations caught. The AI headline reader waits on the user's own Anthropic key and a
  model choice.
- **The user: "do 2 3" - the mood readout on the dashboard and the crowd book on paper.** `news/crowd_paper.py` (doc 22
  s4 override, outside the final machine; verdict 2027-04-26, lines in its docstring before the first trade, first
  anchors Mon 2026-10-26 / Thu 10-29), `crowd_bands.json` (positioning_hist.py --band: 26 weeks p10 -6.5%, median +18.4%,
  80% of stretches up), mood_now rewritten standard-library only (the VM had 55 MB free). positioning_hist refactored
  (quarters / turnover_fee / book shared; both logs reproduced exactly). dashboard_push.py: meta.mood + meta.crowd;
  Dashboard.js: two cards. Tests: crowd_paper 8 (every archived date's legs = the backtest's; one live week = the
  backtest's week), mood_now 5, dashboard_push 7; 9 mutations caught.
- **Headline keywords instead of a paid AI reader** (the user: "avoid API cost"): `news/keywords.py` - words pass at
  chance on coins and on BTC; a tune-learned word score has no holdout value. The event types already hold it; the AI
  reader is not worth paying for unless it finds a new event type. DEPLOYED the same day: crowd-paper.timer on the VM
  (commits 4059523, 09937ab; bot files blob-identical; first run failed on a missing folder - fixed, tested, re-run).
- **The whole recipe + the crowd book** (`backtest/crowd_combo.py`, the user: "we will add it later - tell me the numbers
  combined"): deployed machine + crowd x0.5 / x1.0 on the same dates. Typical 12 months on $300, 2022-01..2024-08:
  $1,177 -> $1,362 / $1,519; 2024-08..2026-09: $9,838 -> $12,914 / $16,045; 10/10 orderings, worst month and fall within
  1.5 points at x0.5, beats the machine scaled to the same fall on both spans. Picked from the same data; paper decides.
  At $300, x0.5 legs (~$3.75) are under Bitget's $5 minimum - x1.0 or more capital.
- **"Can't wait till April" - the crowd book judged without waiting** (`news/crowd_fast.py`, F1-F5 all right): the 6
  unseen weeks since the data ended, through crowd_paper's own code, +9.6% (77th percentile; the machine lost ~13% then);
  positive on all 7 anchor weekdays (+33..+53%/yr); Bybit's crowd gives the same book (rank corr +0.68), 2021 (never seen)
  positive but weak; a forward record alone is slow (66% right at 13 weeks, 74% at 26). Registered before the first live
  anchor: KILL checkpoint 2027-01-25 (< -7.8%), verdict moved to 2027-04-09 with the machine's (dead < -6.6%, held up
  >= +16.8%). Data: the positioning cache now holds all 7 weekdays; Bybit 4h ratios in strategy_analysis/data/news/.
- **Why the accounts are down, and the crowd as a filter** (the user: "learn from it without butchering gains"): live, the
  alt sell-off - longs lost in every crowd bucket; trend breakouts on big coins (SUI XRP LINK LTC ADA DOT ARB) and MN
  shorts squeezed. `backtest/crowd_filter.py`: crowd filters on each book's entries, whole machine, 2022-26 - none passes
  both spans; trend longs off crowd-long coins -35% of the 2024-26 year. Dead (doc 02). The working lever stays: the
  crowd book as its own book (+9.6% over the same weeks the machine lost ~13%).
- **The real-order pieces built (the user: "yes")**, so nothing technical stands before a real account: the COIN MAP
  (`combo_bot.Venue.mapped` / `scale`: Bitget's names and units - 1000SHIB = 1,000 SHIB, 1000PEPE, 1000FLOKI, 1000LUNC,
  1000CHEEMS = 0.001 1MCHEEMS, RAYSOL = RAY; checked on live prices, 657 of Binance's perps map, 0 off by > 0.2%, 91 not
  listed on Bitget; quantities and prices converted in execute(), crash-desk fills converted back in wick_live.watch);
  CAPIT2'S LIMIT ON THE VENUE (`final_books.capit2_orders`, called at the top of every execute(): post-only buy at the
  limit while a slot is free, fills read before the netting, the rest cancelled when the bar ends, paper fallback where
  no order can rest); `--final --mode live` always runs the real crash desk (`wants_desk`). tests/test_live_orders.py
  10 tests, 8 mutations caught; all other suites pass. Doc 22: the user chose FULL size (x1.0) for real money, not x0.65.
  Not deployed to the paper bots (dry mode uses none of it except the map in its ledger).
- **Bitget's smaller coin list** (`backtest/bitget_coverage.py`): the books choose from Binance; 91 Binance perps are not on
  Bitget. Trend 0% affected; news shorts 32% of trades; MN 15-21% of slots. The whole machine restricted to Bitget-listed
  coins: -8.8% (2020-24) / +16.5% (2024-26) on the typical year - no consistent cost. The user: decide the exchange
  later, after the bot performs. Binance: all coins, fees 0.05% vs 0.06%, a testnet with real coins, but $20 minimums on
  ETH / LINK / LTC / BCH and $50 on BTC.

### 2026-10-23 - the day-45 checkpoint written into doc 22 (s3b), before its data

- The user: "I want the verdict soon". `backtest/verdict_power.py`: the record separates the backtested machine from a
  zero-edge one at 65% (2 weeks), 69% (1 month), 74% (45 days) and no better after (73% at 6 months) - the machine's months
  cluster by regime. **Doc 22 s3b: main account KILL if live equity < $261.30 (-12.9%) at 2026-11-23 00:04 UTC** (fresh
  read beside it on 2026-12-01); over it = a weak yes that does not meet s2; a pre-set small-stake option if the user
  funds anyway. Reading at 2026-10-23 10:23 UTC: main $254.26 live. VM verified on the latest bot code (7148366), 0 errors.

### 2026-10-22 (very last) - the live bot checked against the backtest code, trade by trade (`backtest/live_check.py`)

- The user: "how can we make the verdict soon" -> check what does not need time. On the final machine's 13 live days:
  every trend entry is a real signal at the backtest's price; 32 / 37 exits are the rule's - the 5 others all SHORTS (a
  live short-exit difference, open); the daily book's rule is identical, its universe is rebuilt daily from today's
  volume (open); MN 67-89% name overlap; capit2 / sleeve / NDX exact. Replays of the same days lose what the live book
  lost: the -13% is the market.
- **The cause of the trend differences, found exactly**: blend_paper's ATR is a 14-bar SIMPLE mean (the backtest: Wilder,
  bot.core.indicators.atr) and its trail moves off the bar just closed (the backtest: the bar before). With both, the
  replay reproduces 37 of 37 live exits (32 with the backtest's). FIXED IN THE FINAL BOTS ONLY (final_books.enable:
  bp.atr = wilder_atr, bp.manage = manage_bt); blend_paper.py and the seven paper books are untouched - they keep the
  simple-mean ATR, a known offset from every backtest. Universe: final_books.month_pool = every listed perp ranked by
  the PRIOR month's volume, fixed for the month (520 perps read in ~4 min, once a month; 37 of 120 names differ from
  the 24h pool; IOST ranks 42nd). Tests 20 / 26 / 5, three mutations caught.

### 2026-10-22 (last) - the running bot made to match its backtest: capit2 resting limits + the crash bids (DEPLOYED)

- The user: "eliminate losses / make it more profitable". Loss brakes were all tested dead before; what was missing is
  the bot doing what its yardstick does. `backtest/machine_fixes.py` (paired, 10/10 orderings, both halves): capit2 as a
  resting limit +3.4% / +3.9% of the typical year; the crash bids on +15.4% / +7.4% (the final machine's backtests all
  count them; combo-bot-final ran without them, and wick_live's DRY desk fills nothing); MN + carry at maker fees +2.5%
  (needs a real post-only path - not built). All: +22% / +14%, worst month / fall unchanged.
- Built and tested locally: `final_books.capit2_poll` fills a limit AT the limit from closed 1-minute lows since the last
  poll (fallback: the poll's price); `final_books.bids_poll` = wick_paper's rule booked into the dry account each hour
  (book "bids"), called by combo_bot.poll when no real desk runs. tests/test_final_books.py 18 (3 mutations caught),
  test_combo_bot.py 26. Dashboard + scorecard bands now include "bids" (bands rebuilt, run 4).
- **DEPLOYED 2026-10-22 20:36 UTC (the user's yes, commit 59f2412)**: pulled on the VM, blend_paper / combo_paper /
  wick_paper / pair_live / mn_paper / news_books blob-identical, tests 18 + 26 + 5 pass on the VM, state backed up to
  logs/backup_20261022-203627/, only combo-bot-final and combo-bot-fresh restarted; "BIDS: crash-bid ledger on" logged.
  Deployed pair in machine_fixes.py: +19% / +12% typical year. A real account would still need the capit2 limit and
  the desk ON the venue (`--wick`), and the status line does not show the bids book yet (dashboard does).
- Readings at deploy: final $261.02 booked (-13.0%, day 13), fresh $267.19 (-10.9%, day 5); combo_paper (v2) $166.65
  (-24.6%, day 28) = 4.1th percentile of BULL-start 28-day windows (`combo_window.py --days 28`; under doc 22's 5th
  line, which applies from month 3); crash-bid paper Bitget +1.20% a fill on 54 (expected +0.8..+1.0).

### 2026-10-22 (later) - the forex search, "every possible thing": one CANDIDATE, NASDAQ intraday noise momentum

- HistData minute bars added: gold (XAUUSD), S&P (SPXUSD), DAX (GRXEUR) 2010-2026, beside the 7 FX majors and NASDAQ.
- `fx_intraday_pub.py` (opening-range breakout, "noise area" momentum) / `noise_attack.py` / `fx_daily_families.py` (currency
  momentum / value, pre-FOMC, crosses, weekend gaps, trend book variants) / `fx_ml_leadlag.py` (ridge + trees, 10 markets)
  / `noise_book.py` ($300 account). Every forex rule dead; NASDAQ NOISE +2.25bp a day net, Sharpe 0.74 at 1x, survives
  phases / lookbacks / late fills / Exness's own bars, tune t 1.99 (a hundredth short). Pre-FOMC drift a lead (+0.25% an
  event). At $300 Exness's 0.05-lot minimum forces x5: +22%/yr, fall 56% (BACKTEST). Reopened NASDAQ intraday on purpose:
  the 2026-10-12 kill line was set on 9 months / 2.5 years of data. Doc 02's last entry.
- Gold alone (`gold_focus.py`, 2010-2026 minutes): no edge beyond gold rising - the Asian-hours "gain" was partly a bid-only
  reopen artifact (HistData is bid-only: check any session that starts at a reopen); news jumps are over in 6 minutes.
- `ndx_swapfree.py`: what every NASDAQ hold died on was the SWAP. Swap-free, a crash-filtered (200-day + VIX curve) NASDAQ
  core at 2x + NOISE at 2x = +32%/yr, fall 33% (2010-26 BACKTEST, mostly NASDAQ beta). The user's MT5 is an Exness DEMO
  (Trial16, 1:200): USTECm longs pay ~2.2bp a night, shorts 0; the real account's swap-free status is unknown.

### 2026-10-22 - accounts down 10-12% in an alt sell-off; a book for alt bears tested: dead (doc 02's last entry)

- Dashboard read 18:56 UTC: main $262.46 (-12.5%, 13.8 days, account at the 10th percentile of its backtest band - "below
  typical", not under the 5th), fresh $269.88 (-10%); trend, MN, daily and carry all losing, NASDAQ dip +$5.87. Feed and
  services healthy. Bear sleeve idle: BTC's label stayed BULL (10-21 close 2.9% over its 50-day average, rising +5.2%).
- `backtest/alt_bear.py`: the sleeve's rule on ALT-ONLY bear days (alt index in a 50-day downtrend, BTC not) loses in
  2020-26 and wins in 2017-19 - flips; shorting alts in their downtrends loses; trend longs x0.5 in alt bears fails the
  bet-smaller line in all 4 phases. On such days the machine historically made +4% per 30 days (MN and daily carry it).
  Today is not even ALT-ONLY by the rule: big alts -10..-18% in 30 days, small coins pumping - chop.

### 2026-10-20 (last) - the trader: the scalper toolkit cross-checked; NASDAQ TICK tested (his_strategy s69)

- Web research on what NASDAQ / forex scalpers watch: everything was already tested on him except market internals and
  dealer gamma. `backtest/his_tick.py`: NASDAQ TICK (USI:TICKQ) via the user's TradingView - the plan keeps ~5,000 bars,
  so 1-minute TICK reaches only 2026-09-28, 5-minute 2026-07-20 (12 of his trades). TICK extremes rank 0.59 at his clicks
  (ordinary); he went WITH the last 5-minute TICK 9 of 12 (p ~0.15, = s36's "with the last move"). Not his edge at this
  resolution. Open: a forward 1-minute TICK record for his next trades; GEX needs paid options open interest.
- `backtest/his_gex.py` (+ `his_gex_fetch.py` / `his_gex_fetch_fast.py`; Databento $7.03, the user approved $15): dealer
  gamma from QQQ open interest. He leans to negative-gamma (trending) days (40% vs 61%) and clicks far from the gamma walls
  (rank 0.61, survives a window and an after-a-move check) - style; his side vs the magnet 51%, vs the nearer wall 49% -
  no direction. The scalper toolkit is now fully tested on him (his_strategy s69-70).
- `backtest/his_combine.py` (s71): every per-trade outcome x every condition on record, 98 tests - only volatility survives
  Holm (tick rate before -> bigger adverse swing); his side from all conditions together 51% leave-one-out. Suggestive:
  he wins more against a big session move (-0.42 raw).
- `news/signal_channels.py` + `backtest/his_signals.py` (s72): 18 public NASDAQ / gold signal channels on Telegram (71
  public of ~350 probed names), ~32,000 messages - 0 of his 89 entries had a call in the 10 minutes before. Public NASDAQ
  calls barely exist; a private feed is untestable.
- TradingView launch note: the Store build gives spawn EPERM; start the local copy with --remote-debugging-port=9222
  (it worked from PowerShell); the chart was restored to the user's BINANCE:BTCUSDT 1-minute afterwards.

### 2026-10-20 (later) - outside research tested: nothing beats the machine; the Deflated Sharpe as a yardstick

- `backtest/research_ideas.py`: the published Donchian ensemble (Zarattini et al. 2025) - Sharpe 0.85 / 0.38 on our PIT
  data vs the daily book's 1.56 / 1.05; vol-managed MN (Grobys et al. 2025) - costs 19% of the holdout; BTC 21-23 UTC -
  real gross (+5..+8bp) and below the fee. Most outside best practice is already in the repo.
- `backtest/dsr_check.py`: the machine's Sharpe 1.72 has a Deflated Sharpe of 0.99 over 2020-26 at 1,000 tried ideas
  (0.85 at 10,000) but only 0.44 on the 2024-26 half at 100 - the formal case for waiting on the paper record.

### 2026-10-20 - full VM check; profit-taking and a per-coin cap tested (doc 02's last entry)

- VM check (user: "check all the things"): all services up, 0 restarts, one network blip since 10-14; protections firing
  (fresh account's MN dropped BR at +52%); 3 sub-$5 orders correctly refused. The MN book has no take-profit by design:
  it holds a weekly basket and books daily, so +$3.83 (10-19) -> -$3.43 (10-20) was BTW -18.8% and two shorts bouncing.
  Open item before real money: 1000SHIB / 1000PEPE / RAYSOL are UNMAPPED on Bitget (the paper books count their P&L, a
  live account could not place them) - a symbol-mapping fix; and BTW sat long in three books at once.
- `backtest/profit_take.py` (+ `daily_combos.gen` cfg tp / ptrail, off by default): every daily-book take-profit /
  protect-the-profit and every MN basket take-profit lowers the machine on both halves. Hold-to-rule stays.
- `backtest/coin_cap.py`: a coin is over 15% of the account on 42% of days; a 15% cap costs 12% of the holdout and does not
  move the worst month; 25% ~free, rarely binds - insurance for real money, not a return lever.

### 2026-10-18 - the sideways gap: the 9-book machine measured; 4 ideas dead; the lever is the trend book's size

- `backtest/chop_gap.py`: 9-book machine, typical sideways month **-2.1%** (v2 -4.5%); without the trend book +7.8% -
  the gap is the trend book (-7.3% typical in sideways months). C1-C3 right.
- Dead (doc 02's last entry): trend-entry switches (`chop_switch.py`; month_regime.py's 2017-19 win was its booked-return
  attribution - at entry it flips between halves; the efficiency-ratio meter is below the bet-smaller line), the
  Binance-Bybit-Bitget funding gap (`funding_spread.py` + `funding_spread_fetch.py`, +0.1%/yr), chop-gated mean reversion
  (`chop_revert.py`), RSI in sideways markets (`rsi_chop.py`: the RSI dip-buy LOSES in BTC-chop, earns outside it).
- `backtest/trend_size.py`: trend book 0.8x -> typical sideways month 0.0%, 0.7x -> +1.1%, typical year ~unchanged, falls
  ~7 points shallower; costs the top of a 2021-type bull (0.7x on 2020-24: good year -25%, average -38%; 2024-26 ~0).
  A size choice for the user - DECIDED: the trend book stays at 1.0x (the user: "I can't miss on big gains").
- `backtest/liq_now.py` (the user: "I just want to know I won't be liquidated"): the RUNNING machine (no crash bids,
  + news + NASDAQ, 14.5x cap -> line 21.75% left), every position at its hour's worst price: worst hour 55 / 32 / 51% left
  (orderings 0 / 1 / 2) - never under the line since 2020; capit2 at 2x is the tail (at 1x: 55 / 59 / 80%). A shorted
  small coin squeezing is the other tail: LUNA +452% in one hour (2022-05-11), 12 coins > +100% in an hour since 2020;
  at the max one-coin short (MN + carry 10.4%) -47% before the live 30% exchange stops / +50% short exits. Before real
  money: consider capit2 1x and a per-coin short cap (untested).
- Also 2026-10-18: the dashboard SCORECARD (below, 2026-10-17 entry) - and month_regime.py's "losing months 48% -> 12% on
  2017-19" is retracted as a bot result (booked-return attribution).

### 2026-10-17 (deploy) - the news book and the NASDAQ-dip book run in the final machine (paper, VM)

- **DEPLOYED 2026-10-17 00:16 / 00:19 UTC (commits 6158110, 567bbcb, the user's OK)**: `news_books.py` + final_books /
  combo_bot wiring; only combo-bot-final restarted; blend_paper / combo_paper / wick_paper verified unchanged; state
  backed up (logs/backup_20261017-*); tests on the VM 12 + 16 + 25 pass. GROSS_CAP 14.5x (paper only).
- First polls: NEWS watching binance_announcements from message 9062 (the live page parses; ~1 tradable notice a week).
  NDX bought QQQUSDT at 710.40 on the 2026-10-16 signal (RSI(2) 0.7 - QQQ 752 -> 711 in a week) - 4h after the close,
  before the 3h late guard existed (567bbcb); the position stands.
- Status: `./.venv/bin/python combo_bot.py --mode dry --final --status` (lines "news" / "ndx"). Next: the dashboard on
  Vercel (docs/24, the user chose Vercel), then the scorecard / proposals loop.
- **Dashboard feed LIVE 2026-10-17 00:47 UTC**: `/etc/forexbot-dash.env` (written by the user via `deploy/dash_env.sh`),
  `forexbot-dash.timer` pushes `dashboard_push.py`'s snapshot to Upstash every minute (first push verified by read-back).
  combo-bot-final restarted once at 00:47 for the news headline list (backup logs/backup_20261017-004742). The Vercel
  app (`dashboard/`, read-only token) is the user's step. Upstash free plan: ~1.2 GB/month feed + ~90 KB per page refresh.
- **Dashboard v2 + a FRESH $300 account (2026-10-17, the user: "a new $300 fresh started from today on the newest
  version")**: `combo_bot.py --account fresh` (dry only, own state in logs/combo_bot_dry_final_fresh/, test in
  test_combo_bot.py) runs as `combo-bot-fresh.service` beside combo-bot-final. `dashboard_push.py` now sends each account's
  LIVE equity (booked + open P&L since the bot last booked it), Binance-style positions, trade history (trend P&L
  estimated from R - its log has no dollars), P&L by book, curves (own files logs/dashboard/eq_<id>_{m,h}.csv), gzip'd
  to ~6 KB. VM memory: ~120 MB free before the second bot - watch swap.
- **combo-bot-demo STOPPED and disabled 2026-10-17 01:25 UTC (the user: "if it's not significant then remove")**: the
  order-path test was done - 191 orders over 16.9 days, all filled and priced, 0 order / stop failures, median slippage
  +1.3bp, 13 flips; VERDICT stayed NOT YET only for 2 Bitget network blips. Final report on the VM in
  logs/combo_bot_demo/final_report_20261017.txt. Its DEMO-account positions and disaster stops were left as they were
  (demo money). Memory free went 110 -> 258 MB.
- **The SCORECARD (2026-10-18; docs/24 phase 2, the user: "yes" to building it)**: `backtest/scorecard_bands.py` writes
  `dashboard_bands.json` - each book's (and the account's) backtest range for every N-day stretch, N 1..365, as quantiles,
  books in DOLLARS of the stretch's starting account (they add up to the account, asserted). `dashboard_push.py` places
  each account's live result for its age in that range (percentile -> worse < 5 / below < 25 / on track / better > 75,
  or idle) from day 7 on (MN / carry are booked weekly in the backtest). First read, main account at 9.0 days, -4.5%:
  account 25th percentile; carry 5.9th (-$7.75); the rest on track or idle. Three runs - run 1 summed daily returns
  (wrong once equity grows), run 2 died on a 2,401 vs 2,400-day calendar mismatch between orderings (all_books.py has
  the same latent one-NaN-day issue, tiny, unmeasured). tests/test_dashboard_push.py (5 tests, 2 mutations caught).
  The equity chart is drawn on an even time grid (lightweight-charts spaces points, not time).

### 2026-10-17 (last) - all books together (`backtest/all_books.py`); general news is dead even split by tone

- Correlations between all 9 books are low (max +0.38). In the machine's worst months only the trend book really hurts
  (-9.2%); news (+1.9%) and the NASDAQ dip-buy (+1.0%) pay then. The full set (7 books + news + ndx_dip x1): $300 typical
  year $4,435 / $9,838 (tune / holdout) vs $3,774 / $5,494 deployed, fall 42 / 49% vs 46 / 51%, months up 67 / 68%.
- `news/tone.py` + `news/impact.py --tone` + `news/market_minutes.py`: general news (ETF, macro, regulation, hacks...)
  split by FinBERT tone - good and bad barely differ; BTC does not move even in the headline's minute (+-2bp, = random);
  nothing at 1 min .. 7 days. ~20 of ~340 type x tone x horizon cells pass t >= 2 - what chance gives. Dead.

### 2026-10-17 (later) - the news trade's entry, exit and score on 1-minute bars (`news/entry.py`, `news/score.py`)

- 1m perp bars around every adds_products / monitoring_tag event (`news/min1_fetch.py`, data.binance.vision daily archive).
- Entry: shorting a +6% pump with NO stop is best (+587 / +1,106bp) but needs no stop; with a stop it dies. **The trade to
  use: enter 15 min after the headline, short coin / long BTC, hold <= 72h, stop +25%, take-profit -20%: +316 / +267bp a
  trade, 67% won, worst -36%** (313 trades). Score: none survives the holdout; liquidity (24h volume) is the one
  consistent lead. Tone of all 150k headlines is being scored (`news/tone.py`, FinBERT) for the tone split of general news.

### 2026-10-17 - the news book corrected, and connected to the machine (`news/combo.py`)

- **Correction:** 2026-10-16's "news book +12..+27%/yr" measured only adds_products + monitoring_tag (a filter bug in
  `news_book.py` dropped list_spot / new_pairs from the TUNE-CHOSEN group). All four registered types: +7%/yr, fall 58%,
  -9% at 50bp a leg - weak. Per type: adds_products and monitoring_tag strong on both halves; list_spot small; new_pairs noise.
- **Narrowed (adds_products + monitoring_tag, chosen after looking - a CANDIDATE):** +19%/yr, fall 27%, +14% at 50bp a leg,
  correlation -0.05 with the machine. Added at w 1 (1/10 of equity a trade): typical year +10% tune / +57% holdout, worst
  month -30 -> -32%. Heavier weights blow the holdout fall out to 57-71%. Forward paper decides; not in any bot.

### 2026-10-16 (late) - the sentiment engine: news carries a real coin-level edge (docs/25, docs/26)

- `news/` package: tg_history.py / tg_fast.py (180k messages, 11 public crypto Telegram channels via the VM, 2018-26),
  enrich.py (event types, coins incl. 950 learned names, de-dup), impact.py (excess over each coin's own drift),
  veto_test.py (veto on daily / capit2: no effect), news_book.py (short coin / long BTC after bad-for-coin news, with a
  same-coin CONTROL). Result: exchange listings / Binance adds-products / monitoring tags / new pairs -> the coin lags
  for days; news book +12..+27%/yr, fall 17-27%, vs control ~0; edge +240..+544bp a trade on both halves. Market-wide
  news ~0. NOT YET: minute-level entry timing, correlation with the machine, a paper book. Models (FinBERT,
  CryptoBERT) in strategy_analysis/data/models (gitignored); torch / transformers installed (CPU).

### 2026-10-16 - crypto with room: leverage and slots, liquidation modelled per position

- The user: "run every crypto test with liquidation far away, and the ones capital stopped". Backtests here were always
  percentage-based - capital limited what could RUN, not what was tested. What was held back was leverage and slot count.
- **`backtest/no_limits.py`**: the daily trend book wants 1x (holdout +32%/yr; 1.5x +4%, 2x -56%); the capitulation book
  wants leverage (1-4 liquidations in 455 trades at 3x); more slots trade return for a smaller fall (the pair at 24 slots
  +31%/yr, fall 17%, vs 8 slots +50%, 37%).
- **`backtest/capit2_lev.py`**: capit2 at **2x** = +20.0 / +29.9 %/yr (tune / holdout) vs +8.6 / +14.3 at 1x, fall 10 -> 12%,
  0.6% liquidated; 3x helps the holdout only (fall 33%); 5x loses.
- **`backtest/final_capit2_lev.py`**: the deployable final machine with capit2 at the full share and 2x: typical $4,098 / $5,494
  on $300 (deployed $3,400 / $4,735), the SAME -30% worst month, months up 64%. BACKTEST; changing final_books.py is the user's call.
- **DEPLOYED 2026-10-16 01:05 UTC (commit 1a16c5d, the user's OK)**: `final_books.py` capit2 at K 1.0 x 2x with a -49.4%
  liquidation-equivalent exit; account gate 10x -> 11.5x (the books' summed peaks - the user: "we can exceed the account
  cap"; paper only, reconsider before real money). `pair_live.py` retries Bitget network errors / 429s with backoff instead
  of exiting (212 restarts before). Only combo-bot-final and pair-paper restarted; blend_paper / combo_paper blobs verified
  unchanged; state backed up to logs/backup_20261016-*/ on the VM; tests 16 + 25 + 8 pass on the VM.
- **Out of sample, Binance SPOT 2017-08..2019-12** (`backtest/spot_fetch.py` -> strategy_analysis/data/spot1719, 89 coins;
  `backtest/oos1719.py`, frozen rules, funding 0): PASS - trend +57%/yr (2018 +7%: shorts paid), daily +17% (2018 -27%),
  MN +3% (traded 2019 only), capit2 2x +1% (2018 -17%; its 2x is NOT supported out of sample), combined +88%/yr, fall
  48%, 2018 -22%. 2017 barely covered (few USDT pairs). Liquidation: `backtest/liq_stress.py` / `liq_fix.py` (no hour
  since 2020 under the 17% line; capit2 2x is the tail - 29% left in the worst ordering, 1.5x 43%). `final_confidence.py`.
- VM read 2026-10-16: final machine dry $268.08 (-10.6% day 7), combo paper $175.74 (-20.5% day 21), crash bids +0.84% / +0.75%
  a fill, pair 9,870 PKR, demo 180 orders / 0 failures / 2 poll errors, pair-paper restarts 212.

### 2026-10-15 (evening UTC) - VM check: everything running; the demo's 2 poll errors are network; pair-paper crash-loops

- **Read-only check** (`ssh forexbot-vm`, `deploy/status_digest.sh`): 7 services active, up 31 days, disk 9%, RAM tight
  (67 MB free of 896; 2 GB swap, 657 MB used; no OOM kills).
- **Demo two-week check, 14.6 days:** 177 orders, 177 real fills, 0 order / stop failures, 11 flips, slippage median
  +1.3bp (worst +47.8). **VERDICT NOT YET only for 2 poll errors**, both Bitget `NetworkError` on the positions GET
  (2026-10-06 15:07, 2026-10-15 01:44); the next poll ran normally each time. Not the s7b sub-step bug.
- **Books:** crash bids on target (Bitget +0.84% a fill on 34, Binance +0.74% on 32); seven books CORRECTED main $403,
  tight $433, tstop $440, units $475, triple $484; combo paper day 21 $179.02 (-19%: trend -$34.62, MN -$6.92), fair H1
  x0.810 vs triple x0.828; final machine (dry, $300 from 2026-10-09) $276.34; pair 9,882 PKR (capit 9 closed, 67% won,
  +2.58% avg; daily 1 closed -17.7%, 4 open). BTC $82.4k, +0.8% over its 1000h average.
- **pair-paper restarted 206 times since 2026-10-08** (about once an hour): `pair_live.py --loop` exits on a Bitget
  `RequestTimeout` / 429 `DDoSProtection` during the hourly scan; systemd restarts it after 60 s and the restart's full
  re-fetch invites the next 429. Its state still saves every hour, so no hour is lost yet. Fix (a bug fix, allowed by
  doc 22 s4): catch ccxt network / rate-limit errors per cycle and retry with backoff. **Not applied - user's call.**

### 2026-10-12 (last) - the NASDAQ burst: seen coming, not which way; his trades are not burst trades

- The user: "the burst in NASDAQ has something to do with his strategy". **`backtest/ustec_burst_anatomy.py`** (181 days of
  Exness ticks, 1-s grid, trees fit on 60% of days): a >= 7-point / 5-s burst (6.8% of seconds) is foreseeable in TIME
  (holdout AUC 0.861, volatility clustering) but not in DIRECTION (0.513). A bot entering at the top 0.5% / 0.1% of burst
  scores loses -1.76 / -1.82 points a trade, = a random side. His clicks sit at a median 59th percentile of burst score.
- **`backtest/his_burst_after.py`**: after his click a burst comes 22% vs 23% at other seconds; his +7 arrives in a median
  29 s vs 33 s for any +-7 move, 36% vs 38% via a burst. His moves are ordinary; only his side (39 of 41 on the mid) is
  special, and no feature carries it (his_strategy s52).
- **`backtest/ustec_burst_straddle.py`** (use the timing without a side: stops 2-4 points either side at the most volatile
  seconds): -2.0 points a trade on the holdout, +0.05..+0.16 better than the same bracket at random seconds. Dead.
- **`backtest/his_tickets.py`**: his record is LIVE - the closing tickets rise with close time in 90 of 90 pairs and track a
  ~2,700/day broker counter (log-log +0.99); s34's 'real-time' proof had only covered his exits. **`backtest/his_absorb.py`**:
  absorption (hidden size soaking up flow) on the cached CME data at his clicks - ruled out (his_strategy s53).
  **`backtest/his_options.py`**: the options tape (0DTE QQQ flow, Databento OPRA, $16.04 with the user's OK) - ruled out:
  agrees with his side 38-55%, no predictive value for the next minute.
- **His broker is CapitalFX** (statement header); "VertexPro" was the app, VertexFX Trader Pro (not MetaTrader). His own chart,
  screenshotted by the user (**`backtest/his_chart_capfx.py`**): CapitalFX's NASDAQ Dec = Exness + 207 points, 1-minute moves
  corr 0.992 - his screen is the market (his_strategy s54). The app's clock is UTC+3; his statement's UTC+5.
- **`backtest/his_retest.py`** (micro-levels, the last 15 minutes' high / low and retests): he enters a little nearer a recent
  level with room ahead (rank 0.41, p 0.044) - a style lean; as a rule -1.9 points a trade, = random (s55).
  **[docs/23-his-strategy.md](docs/23-his-strategy.md) is the readable summary of everything known about him.**
- **2026-10-13, his_strategy s56** (`backtest/his_race_curve42.py`): his edge rises with the move's size and holds to +-15
  (62% at +-2, 88% at +-7..+-12); 95% at a 30-s horizon is beyond any public data, so either a private live source (A) or
  entries not decided live (B) - the closes are proven live, the ENTRIES never were. The user's app is logged into the
  statement's own account: its History (opening tickets?) and a live screenshot of his next trade settle A vs B.
- **`backtest/his_open_tickets.py`**: the app's History screenshots (2026-09-10) carry OPEN tickets - 20 trades, all 111 events
  in counter order, open-close gaps 1-52 growing with the hold: **his entries were placed live; B refuted** (s57).
- **s58**: "~10% is safer" = his MONTHLY TARGET (`backtest/his_monthly_target.py`: he stops at ~10%, 60-180x notional, no
  stop, ~5 NASDAQ trades a month). **`backtest/ndx_aplus.py`**: 16 years of NASDAQ minute bars searched for a RARE chart
  setup at his selectivity - TEST AUC 0.506, top 0.05% of calls ~58% before spread, his entries ordinary to it. No A+ setup.
- **`backtest/his_volprofile.py`** (volume profile from Exness tick counts: POC, value area, six reads): his side 41-55%,
  rules = random, -1.2..-2.1 points a trade (s59). His Orders tab is empty: market orders, the click is the decision.
- **`backtest/his_pasted_ideas.py`**: seconds 00-04 CME flow (51%) and DAX / STOXX lead (36-53%) - ruled out (s60).
  `backtest/his_pasted_ideas2.py`: copiers after his click (tape = any 7-point move) and a strike magnet (31-57%) - ruled out.
  `backtest/his_pasted_ideas3.py`: block trades before him (faint lean, rule 48-49%), empty target zone (52%), squawk after-headlines (0.87x) - ruled out.
- **`backtest/ndx_aplus_ticks.py`**: the rare-setup search at TICK level (181 days) - AUC 0.505; a 70% top-0.1% bucket was 7
  episodes counted 57 times each (`ndx_aplus_ticks_check.py`). No tick-rhythm setup (s61).
- **2026-10-15 `backtest/his_fullbook.py`**: the FULL CME book (MBO, $39.09, 29 days) at his clicks - imbalance and walls 38-56%,
  rules = his sittings' 55% drift. Ruled out (s63). Raw MBO deleted at the user's word (features kept: nq_mbo_features.pkl).
- **`backtest/his_winners_days.py`** (s64): his 5 losing races were fast, chased moments; winners calm pullbacks; his days lean trending.
  **`his_score_new.py`**: score a new trade of his from the app's History in one command -> logs/his_new_trades.csv.
- **`backtest/his_style_bot.py`** (s65): a bot from ALL his habits (trend day, calm pullback, +7/-30) - every cell loses on both
  halves (-2.5..-5 pts a trade at 70% wins); the flipped side loses less. Dead.
  `backtest/his_style_grid.py`: 256 tweaks chosen on tune days - the best reads -0.25 on the holdout, 2/256 positive on both. Dead.
- **`backtest/his_sec_filings.py` / `his_darkpool.py` / `his_options.py --ndx`** (s66): mega-cap SEC filings (none near his clicks), dark-pool
  prints ($6.07; blocks against him = his pullback, rules 49-51%) and NDX index options ($0.88; 49-57%) - all ruled out.
- **`backtest/his_plain.py`** (s67, his own list read line by line): 74% of his trades sit in two Pakistan-time evening windows
  (the '11:00 NY' cluster is his routine); 2026-09-14 he averaged down and hedged a stuck long; size / order carry no confidence.
  **`backtest/his_manage_bot.py`**: his scratch / average / hedge management at his hours, trend or coin side - 16/16 cells lose. Dead.
- **s68 final audit**: `his_loopholes.py` (ES 1-5 s lead; a sub-second CME sweep / stale fills) and `his_cancel_proxy.py`
  (pulled liquidity) - all CLOSED; `his_mended.py` (+7 / pullback / stops 5-30 / quote- and CME-flow sides): every cell
  loses ~the 2.16-point spread; a side needs 63% at -10 / 72% at -15 for Sharpe 2 on 500 trades a year. Dead.
  Exact data ($9.10): `his_exact.py` (ES top of book / flow / blocks, NQ cancels) closed; `es_flow_mended.py` (ES flow as the
  side) dies at the spread. **`backtest/mended_harness.py` = the engine + gate any future signal must pass first.**

### 2026-10-12 (later) - /goal: thirty years of what DRIVES forex - it explains moves, it predicts none

- **Data** (`backtest/fx_macro_data.py`, FRED is blocked from this PC): Fed H.10 noon FX and H.15 yields 1996-, BIS policy
  rates, OECD 3m / 10y rates (no GBP / CHF 10y), CFTC positioning 1995-, VIX / S&P / oil / gold / copper, and the
  ForexFactory calendar with forecasts 2007-2026 (237 months). Cached in `strategy_analysis/data/fx_macro/`.
- **`backtest/fx_drivers.py`** (368 months): same-month moves follow risk (S&P: AUD +0.52, CAD +0.51), copper / gold
  (+0.25..+0.53), oil -> CAD +0.38 and the US 2-year yield (JPY -0.40) - NOT policy-rate changes (~0). Next-month: all
  77 correlations within +-0.13. 0 of 11 rules pass on Exness; carry +2.6%/yr only where carry is paid (Exness: -0.26%).
- **`backtest/fx_surprises.py`** (6,810 releases): the surprise moves the currency its way ~60% of days (+15bp; 16 of
  23 within 5 minutes in 2026); the drift after it is ~0 at 1 hour to 5 days. No rule passes. Doc 02's last entry.
- **`backtest/fx_rates2y.py`** (after the user's "you did not have all the information"): daily 2-YEAR yields from
  each issuer (Bundesbank, Japan MoF, Bank of Canada, SNB; BoE / RBA / RBNZ unreachable from this PC). The 2y gap is
  the real rate driver - same month EUR +0.40, JPY +0.41, CAD +0.31, CHF +0.27 - and predicts nothing (<= 0.09);
  catch-up, fair-value and rate-trend rules 0 of 4 pass (fair value +1.3%/yr, holdout only).
- **`backtest/fx_tff.py`** (the user: "do all the free ones"): CFTC hedge funds / asset managers / dealers, 2006-2026 -
  same-week moves follow the textbook (funds buy as it rises +0.09..+0.32, dealers sell -0.27..-0.48); next week
  nothing (<= 0.07); 0 of 5 rules pass. Dukascopy's free minute bars (`backtest/dukascopy_1m.py`, plain HTTP - it
  answers bursts with a 301 to HTTPS, which times out here) was throttled; HistData.com (`backtest/histdata_1m.py`, one zip
  per pair-year, 7 pairs 2007-2026) replaced it. **`fx_surprises_1m.py`**: a release moves its currency the surprise's way
  81% of the time within 5 minutes (+14bp); +1 -> +15 min keeps +0.8bp gross (the spread takes it), the next hour ~0, half
  a day a mild reversal; 0 windows pass (the first run's +10bp "drift" was HistData's DST clock - trap in s3).
- **`backtest/fx_speeches.py`** (8,850 BIS central bankers' speeches 1996-2026, hawk - dove words): the Fed's tone tracks the
  US 2-year (+0.45) - the count is real - but relative tone does not move currencies the same month and its next-month
  lean flips between halves; 0 of 2 rules pass. **`backtest/fx_news_tone.py`** (GDELT news tone / volume per economy,
  2017-2026): ~0 same week, ~0 next week, 0 of 3 pass. OANDA's order books: the user cannot reach OANDA; not tested.
- **`sentiment_rec.py` - RETAIL POSITIONING, RECORDED FROM 2026-10-12** (the user: "start recording myfxbook sentiment").
  Myfxbook's page is Cloudflare-guarded (not bypassed) and its API needs a login; FXSSI's public endpoint republishes the
  long share at Myfxbook, OANDA, Dukascopy, IG, FXBlue, XM and 4 more, 25 instruments, no login. Every 30 min to
  `strategy_analysis/data/sentiment/fxssi_ratios.csv` (gitignored; the response's client IP is not stored). Predictions
  R1-R3 registered in its docstring; score after >= 3 months. Running on the PC (session background) - the VM would
  make it durable (user's call).
- **`backtest/fx_news_seconds.py`** (the user: "run the seconds capture test"): 2026 releases on Exness ticks - entered
  0.5-1 s after the print +6.2bp a trade (t +3.9), at 2 s +0.6bp, at 10 s -0.9bp. Exness's quote reaches the
  market ~1 s late (clock check: the jump in the 2nd second on 15 of 18); that window is broker latency arbitrage, not
  an edge (against broker terms, needs the number in <0.5 s). **His latest statement** (his_strategy.md s48): 2 new
  trades on 2026-10-08, both won the +-7 race in 1-2 s - out-of-sample record 38 of 43.
- **`backtest/his_headlines.py`** (the user: "run the headline test"): FinancialJuice / Walter Bloomberg / Breaking Market
  News (public Telegram, fetched through the VM - t.me times out from this PC) against his 89 clicks: no excess in the
  15 s before (0.48x matched); the 60 s excess is his habit of trading in minutes :00-:04 of the hour (25% of NASDAQ
  clicks). The headline wire is ruled out (his_strategy.md s49).
- **`backtest/his_hour.py`** (the user: "that's your answer, you haven't checked it properly"): only 3 of his 48 NASDAQ
  clicks follow a US release (his top-of-hour clicks are mostly 11:00 New York); following the first reaction to
  every release 2010-2026 loses -1.2..-1.7bp (= no-release minutes); following the closed hourly candle (9 of his
  12) is 49-51% on 17,036 hours. HistData NSXUSD 1m 2010-2026 added (same DST clock).
- **Council 2 ("if not news, what?") and its tests**: `backtest/his_clock_exits.py` - his main broker's clock is exact
  (best shift 0 s vs CME and Exness), the market had NOT moved his way before his click (median 0.00 points in 5 s)
  and he still won 40 of 46; his 41 GOLD trades have no edge (51% vs 47%). `backtest/ustec_burst.py` - following or
  fading NASDAQ bursts = random (34-35% vs 35.4%), -2 points a trade. Kill line hit: his direction is not
  reproducible from market data; only he can say what he uses (his_strategy.md s51).

### 2026-10-12 - the council; NASDAQ's last-hour momentum (its one remaining test) is dead: NASDAQ scalping closed

- Council (crypto ideas on forex / NASDAQ scalping / what to take from him): nothing from crypto works on currency pairs
  (no forced sellers); NASDAQ scalping dead because entries carry no direction; the dip-buy is NASDAQ-only and partly
  hindsight; his lesson is to size on the worst move and that an edge can live in a person. First step it named: test
  the PKR -> USDT -> PKR money path with ~3,000 PKR (doc 22 needs it).
- **`backtest/ndx_close_momo.py`** (Gao et al.'s market intraday momentum, the council's one allowed test): NQ 2024-2026,
  first window vs last hour correlation -0.005, best rule +0.26bp a day; Exness's exact half-hours flip sign between
  halves. No pass -> by the registered kill line, NASDAQ scalping is closed at every horizon.

### 2026-10-11 (last) - the NASDAQ dip-buy and his daily "pause" on forex, gold, silver: nothing; a Yahoo data bug found

- `backtest/fx_capit.py`: ndx_capit's rules both ways, with the trend gate as his "join the move after a pause" at the
  daily scale, on 7 forex majors (Yahoo 2003-2026 and Exness 2020-2026) and gold / silver (Exness). **On Exness's own
  prices 1 of 1,296 cells passes (14 trades, chance)**; gold's dip-buys +0.03% a trade through its rise.
- **Yahoo forex daily bars are broken for anything inside a day** (open ~27bp off the previous close; 92-95% "bounces";
  dated a day off): 79 fake passes at t up to +25. New trap in s3. **`fx_t8_exness.py` re-checked T8 (month-end USD) on Exness prices: -4.06bp a month, t -0.83 - the kill
  stands;** Yahoo had read the day before the month-end (+4.40bp on the same months, 55bp a month apart). Realigned by
  a day, Yahoo 2003-2026 gives -4.74bp, both halves negative.

### 2026-10-11 (later) - CANDIDATE: NASDAQ's sharp down days bought (crypto's forced-flow family + his trade shape)

- `backtest/ndx_capit.py` on ^NDX 1999-2026: **22 of 192 cells pass both halves vs a buy-every-day control**; best: RSI(2)
  under 10 at the close, out at the first close above the 5-day average - +0.95% a trade, 12 a year, CAGR +11% at 1x,
  fall 22%. `backtest/ndx_capit_check.py`: smooth plateau, half the edge after publication, strong since 2020; **weak on
  S&P / Dow / DAX / Nikkei / STOXX (3 of 120 pass)**; worst trade -20..-26% -> ruin at Exness's 0.05-lot minimum on
  $221. Bitget's QQQ/USDT perp (isRwa, $5 minimum) tracks the NASDAQ close (corr 0.9993) and can carry it at 1-2x.
  Doc 02's CANDIDATE entry. Not running anywhere; a forward paper record is the user's call (doc 22).

### 2026-10-11 - the crypto scalping tests carried to NASDAQ, US30, gold and forex: dead, and not because of cost

- Asked: "the scalping strategies we applied on crypto ... on nasdaq or forex - give it a shot" (a research request
  inside doc 22's window; no bot touched). **`backtest/mt5_1m.py`**: 1m MID bars built from every Exness tick with the
  real spread (MT5 caps bars at 100,000, not ticks; ticks start 2026-01-01), cached in `strategy_analysis/data/mt5_1m/`.
- The spread is 0.12-0.24 of a 1-minute ATR on gold / US30 / NASDAQ and 0.57-0.68 on the forex majors, against 1.73 for
  DOGE's 12bp - 7-14x cheaper. **Still: `cfd_scalp.py` 0 of 1,368 rules survive; `cfd_bigtarget.py` 0 of 4,820 beat random
  entries; `ustec_seconds.py` real 5-60 s reversal worth +0.00..+0.14bp against a 0.82bp spread.** Gross is ~0 everywhere:
  the entries choose direction like a coin. The walk-forward "pick the recent winner" loses on every instrument.
  Doc 02's last entry. Registered predictions: Q1/Q2/Q5, F2, E3 right; Q3, F1 (by 0.2 points), F3, E1, E2 wrong.

### 2026-10-10 (last) - the councils' shortlist finished; the decision rule written (doc 22)

- **Polymarket 80-90c favourites** without the early-resolution bias (`backtest/poly_rescore.py`): +10.1 -> +7.9 points on
  schedule (se 4.8, 23 events) - inside 2 se, killed by its registered rule. Early resolutions ran +26..+36 points YES.
- **capit2 execution** (`backtest/capit2_exec.py`, 387 signals, 1m bars): the backtested resting limit earns +2.15% a
  signal, the live bot's 2-minute poll at market +1.76% (+0.39 points, se 0.09) - the poll misses the fastest bounces (94%
  winners). Fix = a resting post-only limit (crash-desk machinery); not applied - code frozen, the user decides.
- **Capped exchange rewards**: premise fails - Bitget Launchpool pays pro-rata to stake (only the stake is capped).
- **`docs/22-decision-rule.md`**: verdict dates, fund / kill / extend lines (same-regime percentile, the BTC-1000h
  benchmark, tradable capital, a tested PKR money path), code freeze to 2027-04-09, research stop 2026-12-31.

### 2026-10-10 (later) - two councils, and the trader's copy passes the size test (`backtest/his_size.py`)

- Council 1 ("weather / >10%/month"): drop weather; no tested path to >10%/month; freeze the bots, write the decision
  rule before more paper data; capital, not strategy, is the binding constraint. Council 2 ("overlooked edges"): ranked
  (1) copying the NASDAQ trader live, (2) per-person-capped exchange rewards (launchpools/competitions, forward log),
  (3) maker execution on running books, (4) re-scoring the Polymarket 80-90c log; set a stop date for the research.
- **The trader's size test** (his_strategy.md s47): copies 5-10 s late won 98-100%, +6.6..+7.0 pts, worst adverse move
  ~41 pts; same-sitting moments' 99th percentile 149 pts. Sized on that tail, 0.37 lot = ~+$14/month (6.3%) on $221;
  on the worst move (315 pts) 0.18 lot = ~+$6.5. Passes the pre-registered 0.10-lot kill line. Needs his live signals.

### 2026-10-10 - Polymarket weather markets vs a free forecast: efficient (`backtest/poly_weather.py`, doc 08)

- From a reel ("Grok agent", $50 -> "thousands", "pivot to weather / NOAA"; its own screens: $339, 43-52% wins). 4,782
  resolved daily-temperature days, 22 cities, 51,848 bucket histories vs Open-Meteo's day-before forecasts, walk-forward:
  **the market beats the forecast in every city** (log loss 1.27 vs 1.71); the reel's buy-if-8-points-cheap rule loses
  35-46% per $1; the longshot bias is spread-sized. Same-day (look-ahead) forecast beats the market - pipeline sound.
  Untested: NOAA station forecasts (NBM / MOS via Iowa Environmental Mesonet). Caches in strategy_analysis/data/poly_weather/
  (events.json is 690 MB, gitignored).

### 2026-10-09 (night) - "analyse DOGE today, trade it live": the fee wins at scalping speed; the book's edge is 10-30 s

- **TradingView is wired in**: the MCP bridge lives in `D:/TRADING/tradingview-mcp`; `D:/forexbot/.mcp.json` (gitignored)
  points at it, loading as native tools when Claude Code is next started in forexbot. Until then its CLI works:
  `node D:/TRADING/tradingview-mcp/src/cli/index.js quote|ohlcv|screenshot|draw ...`. TradingView Desktop is the Store build:
  launch the LOCAL COPY `%LOCALAPPDATA%/tradingview-mcp/TradingView.Desktop_*/TradingView.exe --remote-debugging-port=9222`
  (launching from WindowsApps fails with spawn EPERM). Six "AI" support/resistance lines were drawn on the DOGE chart
  (ids in `logs/doge_live_drawings.txt`); the user's own drawings were left alone.
- **`backtest/doge_adapt.py`** (the user's method, honestly): every 6 h pick the best of 228 scalping rules over the trailing
  6h/12h/24h/3d/7d and trade it for 6 h, 90 days of Bitget 1m bars (`backtest/bitget_1m.py`, fetcher fixed for a 1-bar
  hole per page). **Loses at every window, -0.09..-0.15% a trade at 12bp = the fee; 0 of 228 rules positive.**
- **`backtest/doge_bigtarget.py`** ("aim for 1%"): 790 rules with 0.5-2% targets on 5m/15m/1h entries win exactly as often
  as RANDOM entries at every bracket and lose the fee (-0.12% a trade); 2 of 790 positive on both halves. Bigger targets
  shrink the fee's share of the risk (an edge would pay there) but the chart entries have none at the hours scale.
- **The order book, recorded live** (`book_rec.py` 1 s snapshots of Bitget + Binance DOGE books, trades and BTC;
  `liq_rec.py` OKX liquidations + Binance OI; scored by `backtest/doge_book.py`, predictions in the recorders' docstrings):
  on the full 262 min (7,795 snapshots, halves by count - a ~2 h network outage made the clock split meaningless), book
  imbalance, microprice and the Binance-Bitget gap predict the next 10 s on both halves (IC +0.20..+0.25) and still at
  60 s (+0.10..+0.28) - **but the move they predict is ~1-2bp at every horizon**: maker net -2..-3bp, taker -11..-13bp.
  R1-R3 right; R4 wrong (taker flow vs the next minute: -0.01 / -0.09, a mild reversal). An earlier 110-min read said the
  information was "gone by 60 s" - the full recording corrects that; the size verdict stands. The edge belongs to market
  makers. Liquidations: one tiny DOGE event on a quiet day - untested.
- **Live forward test** (`doge_live.py`, rules frozen 16:35 UTC in `logs/doge_live/registered.json`, stopped 21:09 UTC at
  the user's call): **7 trades, 29% won, -1.41% net at 12bp** (-0.85% at 4bp) - VWAP fade short 2 won / 2 lost -0.08%,
  EMA pullback 0/2 -0.85%, my level bounce 0/1 -0.47% (`logs/doge_live/rule_trades.csv`). My two range-edge limit calls
  never filled (`calls.csv`). A ~2 h network drop froze the loop at 18:53; restarted, it rebuilt the record from Bitget's
  bars, so nothing was lost. Bitget's fee re-verified on the demo's own fills: **0.0600% of ORDER VALUE at 20x**.
- Next, if anything: slower forced-flow trades (capit2, liquidation cascades) where a 1%+ move dwarfs the fee; a
  zero-maker-fee venue (not yet checked); or the user logging 30 calls with `doge_live.py --call` to measure their own edge.

### 2026-10-09 (late) - THE FINAL MACHINE built into the bot (`--final`) and running on paper on the VM

- **Asked:** "make the final version of bot combining all the rsi and other good stuff that maximises gain and then
  deploy it to vm". Built as `final_books.py` + `combo_bot.py --final`: machine v2's books + the MN book ranked half
  momentum / half RSI(14) + funding carry 0.5x + the daily Bollinger book with the 20-day exit 0.5x + capit2 0.5x, one
  account, netted per coin. **The whole account is held under 10x** (`final_books.gross_gate`); the trend book's own
  guard drops 9x -> 6.25x, since the other books can hold 3.75x at their peaks.
- **Its backtest, as deployed** (`backtest/final_machine.py`, DEPLOYABLE line; $300, trend gains shrunk, BACKTEST
  ONLY): typical year $3,400 / $4,735 (6 yrs / last 2), median month +4.6% / +7.3%, ~4 months in 10 lose, **worst month
  -30%**, fall 60% / 51%. The 10x cap costs 11% / 19% of the typical year and does NOT soften the worst month
  (registered: 2-5 points less bad - wrong). x0.65 = $1,806 / $2,297 with a -20% worst month.
- **On the VM as `combo-bot-final.service`: `--mode dry`** - a $300 virtual account on all coins, public data, NO orders,
  no keys; beside the demo, which is untouched (its two-week PASS check is not restarted). Real money stays impossible:
  `ALLOW_REAL = False`. Status: `./.venv/bin/python combo_bot.py --mode dry --final --status` on the VM.
- **Found while building it:** (1) the DRY ledger never closed a position its books exited (a coin no book wants had no
  price; only the venue branch looked it up) - fixed, `test_dry_ledger_closes_what_the_books_exit` fails on the old
  code; P&L was never affected (it is booked by the books). (2) On a late start the daily book bought a 24-hour-old
  signal 10.7% from its close (PUMP) - buys now only within 3h of the close (`LATE_MS`), exits always.
  (3) **On the VM, every poll died** on `InvalidOrder: amount of SOL must be greater than minimum amount precision`:
  ccxt RAISES for an order under one step instead of returning 0, and the exception aborted the poll - no later order,
  no stops, **no state save**. `Venue.contracts` now reads it as zero contracts (refused once, logged). **The demo bot
  carries this bug until it is restarted** (it has not hit it: 0 poll errors). (4) A basket rebalanced late was marked
  from the stale close - the first VM run booked -$6.90 on day 1 from moves it never held; late rebalances are now
  marked at live prices (`final_books.rebase`). The first VM state (10 minutes old) was archived and the book restarted
  fresh after 00:00 UTC on 2026-10-09.
- Tests: `tests/test_final_books.py` 15, every rule where it must fire and where it must not; **16 mutations, all
  caught**. `tests/test_combo_bot.py` 25 (two new ones fail on the old code). Live vs backtest differences (capit2 by market order on a 0.3% trade-through
  each 2-min poll, not a resting limit; slot ties by volume) are listed in `final_books.py`'s docstring.

### 2026-10-09 - the archive-hole bug; everything re-run; every combination and thin kill finished

- **Loader bug** (`capitulation_wide.halt_cut`): a >48h-gap rule read two archive holes as halts and cut 51 coins at
  2022-02-25 (16.4% of PIT top-40 coin-months). Now > 7 days. 34 scripts re-run - **their logs supersede the RESULT lines
  quoted in s10 entries below for 2026-10-06..08** (doc 02, "The archive-hole bug" has the table).
- Corrected headlines: capit2's rule still passes in all 4 phases (+3.0 / +4.3% a trade, `logs/capit_stack.txt`) and 0 of
  26 changes improve it (`logs/filter_pairs.txt`); the plain capitulation book is weaker (+1.9..+2.7% a trade); v3 +140%/yr;
  **"E" at the published v2's typical year: worst month -21% (v2 safe -27%)** - the 2026-10-08 "~1 point" correction was
  on the truncated data.
- New candidates (paper first): daily-book exits (20-day mean + BTC exit, fall 65 -> 48%: `logs/daily_stack.txt`); the MN
  book half momentum / half RSI-ranked (`backtest/mn_blend_rsi.py`: beats momentum on both halves and the worst weekday).
- Finished: 728-machine factorial (honest pick = E), every filter pair, the MODERATE kills (`moderate_retests.py`: grid,
  wide PIT engine, meta-labelling, VWAP - all stand; the XS-indicator kill was wrong), memes on the full 9-day record.
- `backtest/tv_indicators.py` had overwritten an older library (aroon, dmi, ...) that `tv_test.py` / `tv_crosssec.py`
  import - restored inside the same file.

### 2026-10-08 (late) - step 2: the improved capitulation book runs forward on the VM

- `pair_live.py` gained the **capit2 shadow book** (coin down >= 10% over 24h + a limit 2% under the signal close, filled
  only on a 0.3% trade-through; target not in the fill bar; clocks from the signal) - its own 5,000 PKR, the pair's two
  books unchanged. Pre-registered H1-H3 in the docstring. 3 new tests (7 in `tests/test_pair_live.py`), 5 mutations
  caught. Deployed as `pair-paper.service` on the VM (hourly), state moved from the PC.
- The first live capitulation (2026-10-08 12:00 UTC bar, 7 coins: ETH XRP SOL DOGE UNI BCH LTC) was recorded by the
  plain book ~3h late; capit2 correctly placed nothing (their 24h drops were 5-7%, under its 10%).
- `meme_days.py`: memecoin graduations on 7 more days - the kill stands (+1 min / +1h -66.9%, 0/7 days positive).

### 2026-10-08 (the goal's second half) - EVERY kill audited: docs/21-graveyard-audit.md

- Every kill in doc 02 / doc 11 / docs 12-13 / this session rated STRONG / MODERATE / THIN / DATA-LIMITED; every THIN one
  the data allows was re-tested. **Nothing came back as a book.** Reversed: the MN short-leg stop (`mn_combos.py`). Wrong as
  stated: "volume is anti-useful", "every reversal fails". Re-tested and standing: protecting the pyramid, stop width,
  entry limits, bb(20,2)/(50,1.5), risk by sleeve (cleared the paired bar, failed matched risk: `engine_rescore2.py`,
  `sleeve_risk_control.py`); long BTC / short alts on a PIT basket (+0.55%/mo on the original weekday, 1 of 7 weekly
  anchors: `bear_alpha_pit.py`); MN width on 7 days (`mn_width7.py`); crash bids up in chop (`wick_chop_size.py`); ICT
  sweep / prior-day fade (real information, loses after fees: `sweep_reclaim.py`); memecoin graduations on later days
  (`meme_days.py`); funding carry, pairs, indicators on daily PIT bars, 1h capitulation (earlier entry).
- Lesson, again: a weekly book must be checked on all 7 weekdays (MN, carry, dispersion all moved with the anchor).

### 2026-10-08 (goal: every combination, then the thin kills) - ~150 variants; one real risk found

- **The market-neutral book's REBALANCE DAY decides survival** (`mn_combos.py`, `logs/mn_rebalance_days.txt`): on 6 of 7
  days fine, on one the holdout is wiped out (2025-09-12 week -99%, MYX squeeze). v2's figures sit on a lucky day; rotated,
  v2's worst year is $17 (`machine_combos.py`). The live bot's 30% disaster stop does not help (the netting re-enters).
  **Fix: a short-leg BOOK exit at +50%** - same average Sharpe, worst week -29%. Not in any bot yet (user's call; §7b).
- **Capitulation improved** (`capit_combos.py`, `capit_stack.py`): coins down >= 10% in 24h + a limit 2% under - all 4
  phases, ~30/yr, +3.9 / +4.4% a trade, 1x fall 4%; volume rule then redundant (`capit_volume.py`).
- **Machine, honest MN** (`machine_combos.py`): v2 safe + daily + improved capitulation beats "v2 safe smaller" +11% / +34%;
  at v2's typical year the worst month is -26.0% (v2 safe -27.2%). **This corrects the v2.1 entry below (-21% was the lucky
  MN day).** Regime weights' +45% was a look-ahead (trend booked at close); fixed, it fails (`regime_weights.py`).
- Nothing improves the daily book (0/37, 0/4 stacks, 0/10 indicator families on daily PIT bars); its holdout rests on 5 pump
  trades (without them -30..-39%/yr). Trend x today's signals 0/4, crash bids x capitulation 0/5, sleeve x capitulation 0/4.
- Thin kills re-tested: funding carry stands (holdout Sharpe +0.28 with the exit); pairs stand (6/6 negative); "indicators
  exhausted" stands, now backed on daily PIT; "volume anti-useful" is wrong as stated; the MN-stop kill is reversed. Doc 02.

### 2026-10-08 - "v2.1": today's two books ADDED to the running bot (`backtest/v2_addons.py`)

- v2 + the capitulation book + the daily Bollinger book, everything x0.75: **same typical year as v2 ($1,777 / $1,773 vs
  $1,812 / $1,625 on $300), worst month -21% / -20% vs -29% / -25%**, fall 53% vs 57%. Passes the bet-smaller line on
  both spans; the daily book does the work, the capitulation book is small. Full size: +50% typical, fall 64%.
- **CORRECTED the same evening (`machine_combos.py`):** the -21% sat on the market-neutral book's lucky rebalance
  day. Measured with the day rotated, the add-ons buy about one point of worst month (-26.0% vs -27.2%), plus return.
- Swapping v2's MN for the capped one fails. The daily book was picked after looking and makes under half on the
  holdout what it makes on the tune half; the x0.75 mix loses 2022 and 2026 to v2. Forward paper before money.

### 2026-10-08 - the names, and MIX B (v2 x v3)

- **Machine v2** = the running one (combo_bot demo + combo_paper on the VM): triple trend (12 coins) + MN 1x + bear sleeve
  + crash bids. **Machine v3** = this session's: daily Bollinger book + capitulation book + capped MN x0.5 + bear sleeve
  (point-in-time only). Not running yet (only the pair half, on the PC: pair_live.py).
- `machine_mix.py`: **MIX B = v3 + v2's trend at 0.5 + crash bids** - $300 -> $1,406 / $1,355 typical year (v2 $1,812 /
  $1,625), worst month -16% (v2 -29%), worst year $290 / $480 (v2 $222 / $454). The best balance measured.
- Capital: the pair cannot trade at 10,000 PKR (every order under Bitget's $5); ~25,000 PKR runs the pair, ~100-150k PKR
  the full v3 (`pair_min_capital.py`); MIX B needs at least that.

### 2026-10-08 (goal: fix the pain points) - "machine v3": pair + capped MN + bear sleeve, +133%/yr on paper

- `pair_lab.py` diagnosis: capitulation half idle 95% of days; daily book skips 53% of signals; bear months -2.1%.
  Fixes that FAILED: more slots, a shared pool (holdout down), the 1000h gate (holdout down across phases), longer caps
  (small). Fixes that WORKED: the market-neutral book x0.5 with each coin-week CAPPED at +100% (`mn_capped.py`: 2026's
  AKE/RIVER/BEAT pumps otherwise carry it) and the doc-13 bear sleeve x1 (bear months +6.6%).
- `pair_full.py`: daily + capitulation (halves, 1x) + capped MN x0.5 + bear sleeve x1, no gate: **+133%/yr (+123..+144
  over 6 phase combos x 10 orders), holdout +83%, fall 40%, 65% of months up, median month +4.6%, every year positive
  (2022 +64%)**. All point-in-time. Not proven forward; the combo paper's MN leg is -$13 live so far.

### 2026-10-08 - pair_live.py: the pair as live signals + a paper book

- Read-only scanner on Bitget public data; first live pass 2026-10-08: daily BUY PUMP; capitulation breadth 0. Caught
  on its first run: Bitget's top-40 includes stock tokens (SPCX, isRwa=YES) the backtest never had - now excluded.
  Paper book from 10,000 PKR. To make it a forward record it must run hourly (the VM is the place - user's call).

### 2026-10-08 (goal: keep searching) - THE PAIR: daily Bollinger trend + capitulation, +51%/yr, no hindsight

- `tv_indicators.py`: TradingView favourites (SuperTrend, Squeeze, Ichimoku, PSAR, Hull, W%R, CCI, MFI, OBV, Heikin-Ashi,
  VWAP) lose to the deployed Bollinger entry. Standout: Bollinger(30,1.5) on DAILY bars, out under the 30-day mean:
  +7.35%/trade on the PIT top-40; `daily_phase.py`: positive at all 6 day boundaries, holdout +1.1..+2.4%.
- `pair_books.py`: half the account in that daily book, half in the capitulation book, 1x: **+47..+59%/yr (median +51%),
  worst fall 25-34%, last 12 months +66%**, 2022 -21%; robust to capitulation phase and slot order. Point-in-time, no
  haircut. Lumpy (median month ~0). Daily book picked after looking -> forward paper decides. 2x = liquidation.

### 2026-10-08 (goal: keep searching) - capitulation with a +5% exit; as a machine sleeve

- `capitulation_exits.py` / `capitulation_tp5.py` / `machine_capit.py` (doc 02): the breadth capitulation entry with
  "+5% or out after 24 bars if not in profit": **+2.4..+3.1%/trade in all 4 phases, both halves**; 10,000 PKR at 8 slots
  2x: +17..+30%/yr, falls 18-33%. Uncorrelated with the machine (+0.08): as a sleeve it lifts the machine's typical
  year $1,812 -> $2,072 (1x) / $2,295 (2x) on $300, worst month unchanged. An increment, not a breakthrough.

### 2026-10-08 - "study DOGE only, 1,000 PKR a month on 10k": the walk-forward says no

- `backtest/doge_focus.py` (doc 02): 134 DOGE strategies; each month trade the best of the trailing 3/6/12 months.
  10,000 PKR -> 1,798 / 11,620 / 3,177 at 1x, ~0 at 3x over 57 months; median month <= 0. Hindsight best (EMA 20/50):
  1.04M PKR - the illusion. +10% months exist at 3x (25-32%) only beside months that wipe the account.

### 2026-10-08 - more frequency from the capitulation buy: loosening kills it; BREADTH helps

- `capitulation_freq.py`: RSI 25/30, 1h, top-100 all add signals and lose the edge; a realistic 3-slot 10,000 PKR
  account makes at best +395 PKR/yr at 1x. Cause: the FIRST signals of a crash keep falling (-0.65..+0.85%/trade),
  later ones bounce (+1.1..+1.8%).
- `capitulation_breadth.py` (post-hoc): only after >=5 coins capitulated in 24h -> top-40, RSI<20, vol>2x: ~55/yr,
  +1.1..+1.7%/trade in all 4 phases, +570..+1,260 PKR/yr at 1x, +1,280..+3,480 at 2x on 10,000 PKR. Candidate.

### 2026-10-08 - the capitulation buy on unseen coins: direction holds, confidence does not

- `backtest/capitulation_wide.py`: the frozen rule on the PIT top-40 (dead coins in). Other coins: ~44 signals/yr,
  85-93% win, +0.8 to +1.2%/trade in 3 of 4 bar phases (+0.09% in one), 24/27 coins positive, but t by DAY only
  -1.3..+2.0. LUNA never fired. 10,000 PKR per trade: +0.5k to +6.3k PKR/yr at 1x by phase; signals bunch (19 on one
  day). Candidate; a top-40 paper tracker would settle it in ~6 months.

### 2026-10-08 - extreme RSI + confirmations: one CANDIDATE, the 4h capitulation buy

- `backtest/rsi_confluence.py` (doc 02): ~2,000 configs. **4h RSI(14) crossing under 20 with a >3x volume spike, +2% or
  out after 4 days:** positive on both halves in all 4 bar phases (+0.9 to +1.6%/trade, t by day 3.7-6.9), every
  year 2020-26, every coin. Honest ~+1.0%/trade, ~13 signals a year across 5 coins: 10,000 PKR -> ~12k at 1x over 5.5
  years, ~12-20k at 3x, 0 at 10x (dips inside trades 29-53%). Shorts at high RSI lose everywhere. Found in the ~10th
  sweep of this holdout -> forward paper before anything. Same family as the crash bids.

### 2026-10-08 - RSI both ways with "factor" exits instead of a stop: dead

- `backtest/rsi_factors.py` (doc 02): 6 factor exits (RSI deeper, level break, BTC against, volume against, not working,
  6xATR) x trend filter, 336 configs x 5 coins x 15m/1h/4h. **No factor makes the holdout positive** (longs -0.05 to
  -0.50%/trade); shorts lose with all; the EMA200 filter HURT longs in 2022. Tune-picked top 5 all lost on the
  holdout. Only 4h RSI<25 longs (+2%, no stop) held on both halves - rsi_only's exception again.

### 2026-10-08 - "I used to make money with just RSI": true in 2020/2021/2023, false in 2022/2025-26

- `backtest/rsi_only.py` (doc 02): the retail RSI trade - buy the cross under 30/25, take +1-2% or exit on RSI 50/70,
  NO stop - on 15m/1h/4h x 5 coins. **Wins 76-95% of trades in every year; sum of returns 2021 +558%, 2023 +421%,
  2022 -737%, 2025-26 -639%.** Since 2024-04 on 10,000 PKR: 1x ends 2-9k on 14 of 15 cells, 5x+ wiped on all.
  The win rate never says which year it is - that is why it feels like it works.

### 2026-10-08 - 15-minute bars, long and short: dead after fees

- `backtest/scalp_15m.py` (doc 02): 5 coins, 2020-09..2026-08, scalp_1m's rules + cells both sides. Fee toll 0.09-0.17R
  (1m: 0.5-1R) and still **taker: 1 WEAK, 0 EDGE of 980**. Best pick (short DOGE overbought spikes in a bull):
  +0.10%/trade on the holdout; 10,000 PKR -> 11,580 at 1x over 2.4 years, gone at 20x in 36 trades.

### 2026-10-08 - "a one-day long on 10k PKR, every indicator combination": dead as asked

- `backtest/day_long.py` (doc 02): long at 00:00 UTC for 24h, 1,350 filters (20 conditions, singles/pairs/triples)
  x 5 coins. **Holdout: long every day -0.1%/day, 0 EDGE, tune-picked indicators lose on the holdout, 10x all-in gone
  in 1-13 trades.** The only thing visible - daily breakout + BTC uptrend on SOL/DOGE/XRP, +0.6 to +2.8%/day, half of
  it Nov 2024, nothing on BTC/ETH - was found after looking at the holdout; it is the trend book's momentum.

### 2026-10-08 - combo paper day 14: -20.6%, at the backtest's 5th percentile

- VM `combo_paper.py --status`: **$175.56 (-20.56%)**, trend -$31.77, MN -$13.25, sleeve idle, 11 trend positions open;
  H1 fair combo x0.794 vs triple x0.835 (59 trades). BTC $82.5k, +1.8% over its 1000h average (was +7.2% on 10-05),
  4h trail break 2026-10-08 04:00 UTC.
- `combo_window.py --days 14 --live -0.2056` (`logs/combo_window_14d.txt`; the default reproduces the day-11 log
  exactly): **5.0th percentile of BULL-start 14-day windows, 2.6th of all** (registered 5-8th / 3-5th: BULL right,
  all slightly worse). Starts this bad came from 20 distinct months; 18 ended the 182 days above the start, but 11
  of the 20 are the 2020-21 bull, and the two that did not recover started in 2022-08 (bear) and 2024-06 (chop).
  **Inside the backtest, at its edge. Not a verdict; a reason not to fund real money before the paper record does.**

### 2026-10-08 - the same odds at 10,000 PKR

- `lottery_v2.py --pkr 10000` / `micro_honest.py --pkr 10000`: at $35.71 the $5 minimum refuses ~half the units (vs
  70-75% at 4,000 PKR), so **the trend book at 1% a unit becomes the best row: >=5x 38%, >=10x 30%, ended below start
  37%, ever under $5 only 5%** (honest universe, 12 months). micro_bot's rules: 17-22% ended >=5x. Still the start
  year: 2022-23 starts 0%, 2024 starts 79% (doc 02).

### 2026-10-06 (last of all) - micro_bot re-measured with its OWN settings

- `backtest/micro_honest.py`: micro_bot's exact rules (exits tested equal to `manage()`), account-level, MTM sizing,
  market exits after the bar close, hourly liquidation. **$10 at its 4%: ENDED >= 5x 29% (touched 42%), wiped out
  56%. 4,000 PKR at 2%: 25-29% >= 5x with 17-36% wiped out - same odds, far less ruin.** Wins are real runs (AVAX
  2021, SHIB 2021/2024, DOGE late 2024); 2022 starts 8-12%, 2024 starts 62-71%. micro_bot.py's docstring now points
  here. RISK_PCT and ALLOW_REAL untouched (human decisions).

### 2026-10-06 (after final) - "I don't want small gains": go-for-broke on 4,000 PKR, re-measured

- `backtest/lottery_v2.py` = `lottery.py` + mistake #17's causal release + the 7-unit triple + the 10x guard on ADDS +
  the user's $14.29 + Bitget per-coin minimums. Self-checks: reproduces triple_capped exactly, and lottery's PIT rows.
- **PIT12 (honest), 4,000 PKR, 12 months, 2% a unit: >=5x 29%, >=10x 22%, >=20x 18%; but 49% of accounts fell under
  $5 (stuck in practice) and 49% ended below the start.** The 40x one-shot: 5x 4-17%, average -14%.
- **It is the start year:** 2020-07..2021-04 starts 75% >=5x, 2024 starts 62%; 2021-05..2023 starts 0% (2023: every
  account under $5). `lottery.py`'s and `micro_bot.py`'s older odds are superseded by this file.

### 2026-10-06 (final) - "find what you undermined": execution - and one weak CANDIDATE

- Audit: funding carry/spikes were already dead (doc 02); the gap was EXECUTION - today's 1m tests filled at the next
  open. `backtest/maker_exec.py` models limits properly (fill only on a trade-through): 93-96% fill, adverse
  selection 0.6-2.4bp. **The ridge BTC+DOGE 60-min model is +4.07bp a trade at Bitget's 2bp maker (t +1.0), +60%
  over 22 months at 1x IF real.** Not significant, holdout read twice, no stop. Candidate for a forward paper test
  only (doc 02). rsi_mom shorts stay dead even at 0bp maker.

### 2026-10-06 (one more) - "one trade, high leverage, indicators and volume": the coin flip, minus fees

- `backtest/one_shot.py`: the whole stake at 10/20/40x on BTC/DOGE, target 2x/3x/5x the stake before
  liquidation. **40x: P(double) 37-44%, P(5x) 4-10%, average -9% to -21% of the stake a shot.** Five indicator +
  volume setups: 0 of 18 beat random by >4 points on both halves (best +1.6), all negative on average. Volume
  stays anti-useful in crypto (doc 02: VSA, volume surge, and now this).
- `--grid`: 2-100x. **Higher leverage = worse odds for the same goal and a bigger average loss** (10x -3%, 20x -7%,
  40x -14%, 100x -44% of the stake a shot). Stake size changes nothing (percentages); splitting it changes the
  spread, not the average.

### 2026-10-06 (last) - "analyse BTC, trade DOGE": the information is real, the trade is not

- `backtest/btc_doge.py`: 27 BTC+DOGE features into ridge and gradient-boosted trees, fit 2022-24, traded on unseen
  2024-10 .. 2026-08. **The models do predict a little** (holdout IC +0.01 to +0.05, 51-57% right direction, +4 to
  +11bp a trade gross). **Taker 12bp: all 6 lose. Maker 4bp: 5 of 6 slightly positive, none significant.**
- **Every version is wiped out at 5x and above.** One hour - 2025-10-10 21:20 UTC, DOGE -63% inside the hour on
  Binance 1m bars - liquidates anything at 2x+. Quote this whenever high leverage on an alt is proposed.

### 2026-10-06 (later still) - 1-minute scalping at 30-40x: dead, and leverage cannot rescue a small edge

- **The user's follow-up:** 30-40x leverage, BTC and DOGE only, 1-minute RSI and the like - "even a small edge makes
  money because of leverage". `backtest/scalp_1m.py` (doc 02 entry). Binance 1m perp bars cached in
  `strategy_analysis/data/min1/` (2022-01 .. 2026-08, downloaded from data.binance.vision).
- **Fees are charged on the POSITION**: 12bp at 40x = 4.8% of the account per round trip. A 1m stop is ~0.12% (BTC) /
  0.24% (DOGE) of price, so 12bp = 0.98R / 0.50R a trade before any signal.
- **572 tests per fee level: 0 net-positive at 12bp, 0 EDGE at 4bp.** Before fees 8 real edges (all shorts,
  +0.5 to +1.9bp a trade), a tenth to a half of the cheapest fee.
- **`--kelly`: the leverage question itself.** The three best gross edges have a Kelly leverage of 4-11x at ZERO fees;
  at 30x and 40x all three wipe the account on the holdout even at zero fees. Quote this whenever leverage is
  proposed as the way to make a small edge pay.

### 2026-10-06 (later) - "what are my odds right now": a manual-trade checker, and the answer is no edge

- **The user asked** for something other than the bot: read RSI / momentum / support-resistance on the day and say
  "long here has X% to take profit, stop there", for 3-5k PKR (~$14). Built as **`odds_now.py`** (read-only,
  Bitget public candles, no keys, no orders): it puts the moment in a cell and replays every past moment in that
  cell on the PIT top-50 perps (2.7M coin-hours, dead coins in), against the same-regime baseline. Doc 02 entry.
- **A TP-first % means nothing alone**: any moment, 1R long hits target first 47.5% (-0.17% a trade after costs).
- **Sweep, 570 tests: 0 EDGE, 3 WEAK - chance.** The first, looser rule (vs any moment) passed 8, above the
  registered 0-5; it was "short in a BTC bear" plus luck (t +2.2 against the same-regime baseline). The rule was
  tightened AFTER that (same-regime baseline, t > 3.9 for EDGE) - stricter, and said so in the file.
- Live 2026-10-05 21:00 UTC: BTC long, SOL short, PEPE long - all NO EDGE. Usage: `python odds_now.py BTC long`.
- History table: `strategy_analysis/data/odds_table.parquet` (gitignored, `--build`, ~3 min). It ends 2026-09-19 with
  the perp archive; it does not need to be current - it is the history the live cell is looked up in.

### 2026-10-05 - back on the crypto bot: SSH to the VM, first full reading

- **SSH access** from the user's PC (see §8). First digest (`deploy/status_digest.sh`), all four services active.
- **Demo bot, day 5.6 of 14:** 87 orders, 87 real fills, 0 failures, 0 poll errors, 0 stop-placement failures,
  8 flips, slippage median +1.3bp. On track for PASS ~2026-10-13/14.
- **Seven books, CORRECTED:** main $301.47, tight $481.86, tstop $480.09, units $529.08, triple $527.45 (all MATCH).
- **Combo paper, day 11: $188.07 (-14.9%)** - trend -$19.62, MN -$13.03 (-$11.88 on day 1), sleeve idle; fair H1
  combo x0.851 vs triple x0.903. BULL regime while breadth20 fell 0.97 -> 0.78. **Not outside the backtest**
  (`combo_window.py`): an 11-day fall of 15%+ is 6.7% of all windows and 10.2% of BULL-start windows; day 11 sits
  at the 10th percentile. Prediction 5-10% right, BULL 3-6% wrong (bull windows swing hardest).
- **Crash-bid paper, 19 Bitget fills:** -0.06% a fill against +0.8-1.0% expected; Binance +0.24% on 20. Too few
  to read; verdict needs 60.
- **No new bug in the live records:** the combo MN's -$11.88 on day 1 is real market moves (its momentum longs
  MUBARAK -16% / AKE -17% / BTW -8% that day, shorts bouncing), reversed the next day.
- **Sentiment** (`sentiment.py`, `sentiment_dial.py`, doc 02): Fear & Greed and Wikipedia attention predict the
  combo's NEXT WEEK (momentum, both halves, survive controls) - but as a size dial Fear & Greed LOWERS Sharpe on
  both halves (0/10 orderings), worst fall 50->61% / 60->73%. Greedy weeks pay more because they are wilder.

### 2026-10-06 - the engine checked against the live books: a fourth flattering bug (doc 03 #17)

- **The engine reproduces the live books' trades** where both hold them: entry median 0.0bp, R -0.004, units
  agree; one key alone, 15,735 of 15,736 trades identical (`engine_vs_live.py`, `slot_retry.py` CHECK A).
- **The engine's candle cache (`blend.fetch`, `*_1h_2400d.json`) stops 2026-09-11 16:00** and is never
  refreshed. Harmless for history; any test of recent weeks silently sees nothing.
- **Mistake #17, the allocator look-ahead:** slots freed at the exit bar's label. Fixed causally: tune -1.55 /
  -1.33 %/mo (main / triple, 0/10), holdout +0.25 / -0.55.
- **The live bots (blend_paper.cycle, so combo_bot too) are a different book:** one position per key, retry,
  a one-bar pause. **Plan on 1-2 %/mo under the published figures, with deeper falls** (triple, this file's
  terms: +4.52 holdout vs the engine's +6.71). Removing the pause changes nothing; the rest is mixed across
  halves, so the bot is not changed.
- **Graveyard:** the earlier corrected-engine rescore (doc 11 part 2) already re-ran every engine kill. The only
  kills that rested on the allocator are the slot ones (16 slots, slot priority, correlation allocation, slots
  by side) - the legitimate reopening under rule 9.
- **Slot ideas re-run** (`slot_ideas.py`, `slot_split_matched.py`, doc 02): on the causal allocator with the live
  position model, nothing passes. More slots = tune-only and past 10x; splits flip between halves. 6 long / 6
  short beat the shared book at MATCHED drawdown on both halves on the deployed grid, then lost the tune half on
  the other 3 bar phases - dead. The live-model triple: +9.97 / +4.97 %/mo, falls 64 / 56%, 9.5x p99 leverage.

### 2026-10-01 - his January-March clock may be one hour off (his_strategy.md s35)

- **Found in our own table, no new data** (`logs/his_vs_market.csv`): split at the EU clock change (03-29) his
  record is two traders. Before: the real market moved his way in 37% of trades (-1.3 pts) and his broker's basis
  jumps -192..+351 between days. After: 96% (+10.2 pts) and a smooth futures roll-down. s25 called the January-March
  prices "not the market's"; a one-hour winter clock error gives the same picture. Every script uses one `GMT = 5.0`;
  s14 split +4/+5, s15 tested +0/+3/+5/+7 pooled, s25 searched only +-600 s pooled.
- **`backtest/his_clock_check.py`** tests it per period on the PC (MT5 ticks). Synthetic test plants the error and
  finds it, and finds none when none is planted. **Registered: winter best = UTC+4, summer = UTC+5 (the control).**
  If right: ~19 more clean trades (25 -> ~44) for the copy-delay test, and s25's doubt about his broker goes away.
- **Handed to a local session:** `docs/LOCAL_MT5_TASKS.md` (clock check, tick cache for Jan-Mar via
  `backtest/his_tick_cache.py`, the winter charts via `his_look.py --winter-gmt`, re-running the copy test on ~44
  trades). The cloud container cannot reach MT5.

### 2026-10-02 - the trader's winter clock: CONFIRMED one hour off (his_strategy s35b-c)

- **`his_clock_check.py` run on the PC's MT5** against predictions registered in s35: control (after 29 Mar)
  UTC+5 PASS; **before 08 Mar best UTC+4**, median |pts - mv| 4.29, market his way 94% (against 9.99 and 39% at the
  old UTC+5). **12 of 12 decisive winter trades favour UTC+4, none UTC+5.** The 08-29 Mar trade reads at UTC+3/+4,
  clearly not +5, so the statement's clock changed on the EU date.
- **MT5's own labels are UTC** (`mt5_clock_anchor.py`: the US cash open sits at 14:30 / 13:30 / 13:30 UTC across the
  three periods). So the hour is in the timezone the statement's times are written in. **The statement itself is
  genuine** - the user downloaded it from VertexPro; a broker server clock that changes in March explains the shift.
- **Consequences:** s25's "off-market winter prices" was the clock; his winter trades are as good as his summer ones;
  the clean sample grows 25 -> ~44. `his_calendar.py` (s28), `his_posts.py` (s29) and `his_news.py` (s24) put winter
  trades an hour early against outside clocks and must be re-run - the handoff's step 4 did not list them.
- **Steps 2-4 done the same day** (s35d-f; every script first reproduced its committed log byte for byte):
  - **his edge replicates out of sample**: winter 14/15 at the +-7 race vs 55% nearby (p 0.002), all 36/41 (p 7e-6);
  - **a copy within 5-10 s keeps it** (+6.6 to +7.0 pts a trade vs +2.5 to +2.9 for the same exit at random moments);
    gone by 20 s. USTECm pays $1/point per lot, min 0.05; he trades NASDAQ ~5.5 times a month;
  - **still not decodable**: 13 markers rank 0.44-0.56 on 41 entries; the 75-feature decoder scores 0.445 / 0.469
    against a 0.495 null on 33 entries; news, calendar and posts re-run at the corrected clock - nothing survives Holm;
  - the winter charts show the same ordinary setups as summer. One eye impression ("at the day's high/low") was
    measured (`his_day_extreme.py`) and was wrong; a mild preference for room ahead reached Holm 0.048 but wins no
    races at random moments.
  - **Where reverse-engineering stands: what his trades do is solved and replicated; how he picks them is in no data
    recorded here. The only route to his edge is copying him live, not decoding him.**
- **His DIRECTION is not in the price either** (s36, `his_direction.py`): he follows the prior move 44-59% at
  every horizon from 15 s to 30 min (none significant), and at his own moments the best of 14 follow/fade rules wins
  the race 57% against his 88%. His moment + his side = 88%; either alone ~50-57%. At his click he knows WHICH WAY,
  from something not in price history: real futures order flow, the book, a live headline, or someone else.
  **Decisive test: CME NQ trades with aggressor side (Databento, $125 free credit on a new account, user signs up,
  key in env only).**

### 2026-09-29 - "triple x4.142" was accounting; the combo's H1 yardstick fixed at day 5

- **The combo's day-5 status** read combo x0.951 against triple x4.142. The triple number is
  two artifacts stacked (§7b): its reference was REALISED equity while it held runners opened
  ~09-17 that the combo never held, and eight of them closed on 09-28 through the legacy
  sized-at-close path ($209.68 -> $883.52; entry-sized ~$555). Confirmed to the cent on the
  VM's own rows: each legacy close is `prev x (1 + 0.003 x R)`, LTC's post-fix long is not.
- **H1 now reads a fair line** (`combo_paper.triple_fair`): the triple's trades OPENED since
  the combo started, replayed from $221, sized at entry. The registered line is still printed,
  labelled. Prediction recorded before the VM's first reading: x0.90-x1.05.
- **`rebuild_equity.py` rewritten**: all seven books, forked books replayed from main at the
  fork, and a self-check that reproduces the recorded column row by row by modelling the bot's
  IN-POLL order (BOOK coin order, then sleeve). Without that order the real 09-28 rows cannot
  be reproduced - SHIB, WLD and ARB were opened between closes of the same poll. The old
  check only modelled the legacy convention, so it could never pass on a log spanning the fix.
- **MN held-coin bug fixed** in both market-neutral books (§7b).
- **Azure Run command keeps only the last ~4KB of output.** A paste that runs several commands
  shows only the tail; ask for one command, or a filtered one, at a time.
- To deploy: `deploy/update_combo.sh` (pull, blob-id check that blend_paper.py is unchanged,
  tests, restart combo-paper only, status, corrected equity).
- **Deployed on the VM 2026-09-29, first readings** (update_combo.sh output):
  - H1 fair: **combo x0.945 | triple x0.966** on 12 trades. Inside the predicted x0.90-x1.05.
  - `rebuild_equity.py`: **all seven books MATCH to the cent** (fix marker 2026-09-23 06:09:05).
    Corrected, recorded: main $207.15 / $207.25, tight $492.75 / $727.43, tstop $489.53 / $715.04,
    units $544.77 / $878.14, triple $541.55 / $863.09.
  - The factorial on corrected equity: **7 units +$52** (units - tight, triple - tstop),
    **time stop -$3** (tstop - tight, triple - units). ONE event - the same runners banked on the
    09-28 break, units 6-7 added to them after the fork. The backtest's direction, once; not a
    verdict. Main's $207 is not comparable here: its runners are still open.
- **The other session's "all-weather" weights (MN 1.5x, sleeve 1.5x) are NOT adopted.** Its commit
  `e5d4c70` / doc 19 never reached GitHub. Its own honest finding stands (a typical sideways month
  still loses ~4% at every weight), but two of its passes are weaker than stated: the bar-phase
  check cannot test an MN change (MN is identical in every phase), and its matched-risk control
  used the weekly-booked fall that `max_mix.py` says is too shallow for large MN shares. The
  running `combo_paper.py` logs each book separately (`combo_marks.csv`), so those weights can be
  read from its own record in six months without a new test.
- **Bitget minimums fixed in `combo_bot.py`** (§7b) - the step between the bot and a readable
  two-week PASS check.
- **The demo bot can move to the VM** (`combo-bot-demo.service`). It MOVES, it does not copy:
  one account, one bot, and the guard cannot see across machines. Steps: stop the PC bot; on the
  PC run `deploy/make_key_paste.ps1`, which copies a Run command paste to the clipboard that
  writes the PC's BITGET_* variables to `/etc/forexbot.env` (600, root; base64 in 30-char pieces,
  and it refuses values systemd would misread); paste it; then paste
  `deploy/install_demo_bot.sh`. The installer refuses with no keys file or another bot on the VM.
  It starts fresh, so its first poll closes what the PC bot left open. Tested on a fake VM and
  with the real PowerShell script. **If the Bitget key is IP-whitelisted to the PC, add the VM's
  IP on Bitget, or every private call fails.**
- **DONE: the demo bot runs on the VM since 2026-09-29 19:58 UTC** (`combo-bot-demo.service`,
  `--mode demo --wick`, fresh state in `logs/combo_bot_demo/`). The PC demo (pid 4600) was told
  to stop. First poll: MN rebalance #1 (12 names, $18.42 each), then it netted the PC bot's
  leftovers - SBTC reduced, SETH and SXRP closed - every fill priced by `fetch_order`, slippage
  +4.3 / -1.1 / +4.7bp, and a disaster stop placed. **The crash desk placed its first real-settings
  bid** (XRP, $5.52 = equity/40; BTC and ETH are still under Bitget's minimum). One bid an hour
  still cannot exercise the cap-at-10 path. The two-week `--report` check restarts from here, on
  the fixed code. Check: `./.venv/bin/python combo_bot.py --mode demo --report` on the VM.
- **First `--report` on the VM, 0.8 days in: clean.** 25 orders, 25 real fills, 0 order failures (the PC
  had 230), 0 stop-placement failures, 0 poll errors, slippage median +2.6bp / worst +9.3bp, 3 intrabar
  trend exits, open/add/reduce/close all seen. The report never counted FLIPS although its PASS rule
  requires one; it now does (`flips()`), and prints `VERDICT: PASS` or `NOT YET - <what is missing>`
  (`verdict()`, 14 days, median slippage <= 5bp). PASS is due ~2026-10-13.

### 2026-09-26 - the trader's pick: every free source read, none holds it (his_strategy.md §26-34)

- **His moment is real on mid prices:** 87% (20/23) of 3-minute +7/-7 races won, against 54% for
  other moments of the same 20 minutes, same direction (`his_local.py`, p 0.001). **Net of the
  spread it is 42% vs 42%.**
- **The markers:** a 30-s dip against him, a quiet candle with a rejection wick, and a round 25
  level. None survives Holm. Only the wick predicts on every day, and only +3 points
  (`his_predictors.py`). Every rule built from them loses like random.
- **Order flow** (Binance QQQ archives, downloaded with the user's OK, not committed): the perp
  follows the NASDAQ price by up to 1 s. Its flow restates the dip and adds ~0. A first-run
  +11.7 was one lucky sample (40 re-draws: +0.8, sd 3.8). **Re-draw a moment-sample before
  believing it.**
- **Left:** CME's own order flow (paid; the user would open the account), his screen, or luck in
  a statement picked for looking good. Recommended: stop unless a screen recording exists.
- **The real news calendar** (ForexFactory, `ff_calendar.py` / `his_calendar.py`, §28): releases,
  Fed speakers, the Chair, Trump's speeches, surprises - his entries and his days match the
  same clock time on other days; nothing survives Holm. His best days had no scheduled news.
- **Trump's posts** (CNN archive, downloaded with the user's OK, `his_posts.py`, §29): posts that
  moved NASDAQ came before his entries at chance (5 vs 3.7). The news angle is closed.
- **His sessions and the retail toolkit** (§30, `his_ta.py`): he trades whenever he is free, 1-3
  trades, leaves green (29 of 30 sittings), and one sitting makes the month from May on. Smart-money
  concepts and EMA/RSI/Stochastic/MACD/Bollinger rank ordinary at his moments vs the same 20
  minutes; nothing near Holm.
- **Every 1-minute candle pattern** (§31, `his_1m.py`): 13 patterns incl. the forming candle, at
  the same second of the minute; best inside bar 2.09x (p 0.044), nothing survives Holm.
- **His edge re-tested, and the big stocks** (§32): the 87% is real - 10 of 12 days at +-7 (t 5.8),
  8 of 12 at +-10, not at +-4: it is direction over 1-5 minutes. The 8 biggest NASDAQ stocks,
  the dollar and bitcoin (MT5 ticks) rank ordinary before his entries. His broker has no lag.
- **Every feature at once** (§33, `his_model.py`): 75 features, logistic + forest, unseen days: his
  moment ranks 0.505 / 0.486 vs luck 0.50 (p 0.36 / 0.55); a planted 2-3 feature pattern is
  recovered at 0.72-0.96 (`--power`). His information is real and is not in any recorded data.
- **Charts read by eye; real-time; copyable** (§34): ordinary setups with look-alikes on every chart;
  key levels ordinary (median 37 pts away). Exits identical to a mechanical target, so the record
  is real-time (`his_extremes.py`). A copy 5-10 s late at Exness keeps the edge on his 25 trades
  (net +-7 race 64-72%, +6.3 to +7.0 pts a trade); gone by 20 s (`his_copy_delay.py`).

### 2026-09-25 (day) - back to forex: 33 tests dead, one that holds swap-free (doc 18)

**The trader's material has nothing left to read.**
- The video and all 55 screenshots are his trade-history list; **none shows his chart**
  (his_strategy.md §23).
- The broker statement adds nothing beyond §16–22: every trade row has the same type code "L",
  and there are no pending orders.
- His entry choice (+10.4 points a trade) cannot be traced further without asking him, or without
  a recording of his chart.

**33 new forex tests, all dead after Exness costs** (doc 02 entry, doc 18):
- nine published calendar and session effects (`fx_anomalies.py`);
- the Asian-range breakout, 24 cells (`fx_breakout.py`).

**One holds: 12-month trend on 16 markets** (`fx_tsmom.py`, `fx_tsmom_check.py`).
- +5.5%/yr at 10% volatility, 2004–2026, both halves (Sharpe 0.52 / 0.62).
- **It needs a swap-free account**: with swap it is −1.6%/yr.
- It comes from commodities and indices. FX earns nothing (Sharpe 0.03).
- At $300 it fits only on a Cent account, and even there gold and silver are too big.
- **Next:** ask the user whether their Exness account is swap-free.

**Tick level** (his_strategy.md §25). MT5 has USTECm TICKS from 2026-01 (UTC-aware datetimes are
required: a naive one is read as local time).
- **His broker's prices.** January–March fills often sat outside the real market, earning more
  than the market ever offered in ~10 of 20 trades. April–September is clean (100% inside, basis
  ±0.5).
- **The pause he joins:** a NASDAQ-led 5-min move, then a market-wide 30-s dip, entered
  mid-candle; +7 before −7 in ~85–88% against 50% at random.
- **As a rule it equals random** (−3.0 points a trade). His pick is not in ticks, pace, other
  indices, news or the day's trend: most likely the order book.
- **His 96% is partly structure:** a 7-point target with no stop wins 83% even at random.

**His charts, read at the user's prompt** (his_strategy.md §24):
- `his_charts.py` draws all 46 NASDAQ trades on real bars: he joins the 1-minute trend after a
  small pause, and some trades follow 08:30 ET releases.
- `his_news.py`: news footprints are ordinary against the same clock time; 0 trades on Fed days.
- `his_micro.py`: the pattern as a rule, 18 of 18 cells lose.
- His edge is which pause he picks: tape, not bars.

**The crash desk's cap bug** was found and fixed by the other session (commit 9e6365e: a partly
filled bid escaped the cancel). The demo was restarted on the fix (pid 4600).

### 2026-09-25 (night) - the machine v2, the crash bids on Bitget, and the crash desk (doc 17)

**The venue question, answered without waiting 6 months** (`wick_bitget.py`). The user could not
wait for `wick_paper.py`'s verdict. Bitget serves 1-minute history back to 2022, so the paper
book's own code was replayed over 2022–2026 on both venues. Dead coins used Binance's bars as a
stand-in.
- Bitget's own bars: **+1.01% a kept fill** (949 fills);
- the same coin-hour on both venues: +0.86% against +0.87%.

Two bugs were caught in the replay's own bookkeeping before it was believed:
- a Bash heredoc silently skipped an edit (the trap in §3);
- hour keys came back in seconds, not ms, so no stand-in was tagged. Now unit-proof, with an
  assertion.

**Four more ideas dead** (doc 02, 2026-09-25 entry). Each had a mechanism and a registered
prediction:
- crash bids filtered by funding: the holdout reverses;
- selling bear-market squeezes: −0.43% a fill, worst −339%;
- holding fills 2 hours: +0.21, se 0.16, not adopted;
- holding longer only after a capped wave.

**The machine v2** (`machine.py`): see §6 and doc 17. The size dial settles ×1.0.

**The crash desk** (`wick_live.py`, `combo_bot.py --wick`):
- limit buys only;
- a 3-second fill watcher enforces the cap (the 2-minute poll cannot);
- fills sit in the targets until the hour's close, then leave through the netting.
- **Tests:** 10 offline tests, 7 mutations caught.
- **Read-only check against Bitget's markets:** at $7.50 a bid, 8 of 40 coins are under the
  minimum size, and 1000PEPE / 1000SHIB are unmapped.

**The demo bot was restarted with the desk** (pid 8524 stopped and verified; the new process writes
to `logs/combo_bot_demo/stdout_wick.log`):
- it runs with TEST settings (`--wick-dist 0.001 --wick-cap 2 --wick-usd 30`) so the order path
  runs within hours;
- **seen working:** placing, filling, a disaster stop on the fill, release at the hour's close,
  and a netting sale 2 s after the close.

**Done 2026-09-25 00:01 UTC:** after two clean cycles, the demo was restarted with the REAL settings
(`combo_bot.py --mode demo --wick`, pid 10512, `logs/combo_bot_demo/stdout_wick_real.log`). The main
books' state carried over both restarts.

**Not yet seen on the exchange:** the cancel-at-cap. It needs 2 fills in one hour, but it uses the
same cancel call the hour closes used successfully, and its trigger is tested offline.

### 2026-09-25 - crash bids made safe, the worst month, and coming back (doc 16)

**Better crash bids** (`wick_better.py`, ~25 variants):
- Skipping BEAR days and using the top-40 pass against "just bet smaller" on both halves. Bear-day
  wicks earn +0.12% a fill (holdout −0.88%) and hold every LUNA fill.
- Closer bids, volatility-scaled bids, ladders, a 3-hour reference, the next-hour exit and top-60
  do not pass.
- I predicted skipping bears would cost growth. It did not.

**The hidden risk** (`wick_5m.py`: 5-minute bars on 4,345 fill hours):
- The hourly model's fills are exact.
- After a fill the price keeps falling: median −3.9%, 1 in 20 −22.5%.
- On 2025-10-10 21:00 the bids' paper loss was −52% of the account. With the trend book the same
  hour, **10% left** (`joint_worst_hour.py`, prediction right).
- Cancelling after 10 fills per hour leaves 47% and keeps +16%/yr. That is better than uniform
  sizing to the same in-hour loss, but it costs ~46% of the uncapped growth; I predicted 10–15%.

**The worst month** (`worst_month.py`):
- With doc 15's bids it was May 2022 (−35.5%: bids −22.4%, sleeve −13.1%). With the new bids the
  worst months are trend + MN months again.
- 16 brakes (trend or whole account, −10/−15/−20% this month, rolling) all fail against betting
  smaller. They sit out the recovery.

**Recovery:**
- All 172 falls of 20%+ (10 orderings) recovered: median 14 days from the low, longest 232.
- A made-up −50% month comes back within 24 months in 100% of starts at backtest growth, 62% at
  +50%/yr and 52% at +25%/yr.
- **$20/month withdrawn straight through it leaves a typical $16.**
- A first stress (halve every up-day) was the wrong question: it removes the edge, not half the
  return. Kept as a record.

**Status:** candidate, nothing in `combo_bot.py`.

**The paper book `wick_paper.py` (doc 16 §7), asked for by the user.**
- **What it runs:** Bitget and Binance, on 1-minute candles. It records the hour-close exit and the
  +120-minute exit side by side.
- **Tests:** 13 offline tests; 6 mutations are each caught.
- **Replay on past crash hours** (`wick_replay.py`):
  - on 2025-10-10 Bitget filled 35 of 40 bids against Binance's 38, so its wicks were nearly as deep;
  - on 1-minute bars the in-hour paper loss is −16.3%, so H4's limit was set at −20% before the
    start.
- **Installer:** `deploy/install_wick.sh`, tested on a fake VM, with the hash of the committed file.
  **Running once the user pastes it.** Check with
  `./.venv/bin/python wick_paper.py --status` on the VM.
- **Found while registering it:** the rule lost money on Binance in Jan–Jun 2026 (−0.37% a fill). It
  is written into the file's expectations.

### 2026-09-24 - the first real return improvement, seven paper books, and what moves BTC

**Later still: why the account halves, and the mix that fixes it** ([doc 14](docs/14-drawdown.md)).

*The cause.* The falls come AFTER booms, in sideways or rising markets (16% of their days are
bear). 94% of 1h alt breakouts fail, and stacked 5–7 unit positions give back profit.

*The fixes tested.* 56 fixes against the "just bet smaller" frontier. Smaller-after-boom,
pause-after-failures, tighter trails, per-unit stops and a lower guard all fail. One survives the
four-phase check: the **equity anchor**, which sizes the trend book from min(equity, 21-day
average) and adds +0.2–0.8 %/mo.

*What works.* Adding the two independent books:
- the market-neutral book made +22 / +55 / +52% during the three worst falls;
- the bear sleeve (doc 13).

*The best mix.* **Trend at 70% + anchor + sleeve + 0.5× MN.** For $221 the typical year is
**$736 against the triple's $584**, the biggest fall **35% against 53%**, no losing year in six,
and the worst year $241 (`final_anchor.py`). It passes on all four bar phases, both halves.

*Those figures were understated.* They haircut the whole mix. `max_mix.py` haircuts only the
trend book, by shrinking its gains and keeping its losses. On that basis:
- the 70% mix is worth $961;
- **trend 100% + anchor + sleeve 1× + MN 1×** is worth **$1,210 a year against the triple's $592
  at the same risk** (6 years), and **$1,125 against $530 over the last 2 years** (0% losing
  years, fall 45% against 58%);
- taking half of each month's profit gives ~$31–39 a month on $221.

Also measured:
- the user's regime-sized MN idea ties the fixed sizing;
- the sleeve at 2× tops the grid, but its 2018 out-of-sample fall (42% at 1×) rules it out.

See doc 14 §8.

*Status:* candidate, not deployed with money. The whole mix runs forward as **`combo_paper.py`**
**on the VM** (`combo-paper.service`, started 2026-09-24 12:40:12 UTC, pre-registered, verdict at
6 months ~2027-03-24, doc 14 section 9). A local run from 07:12 that morning was stopped and
archived when the VM copy came up, so there is one record.

**Late: the first bear-market signal that replicates out of sample** ([doc 13](docs/13-bear-breadth.md)).

*The search.* Six bear/chop strategies died first (doc 02: reversal, pairs, daily shorts, gated
mean reversion, shorting BTC under the gate). The seventh, funding carry, averaged +0.78%/wk and
lost 107% in one week to a short squeeze (MYX +1,137%). Then 21 signals were scanned *inside*
regimes (84 cells, Holm). One passed, the one predicted: **breadth20 in BEAR regimes**. Low
breadth (≤ 10% of the top-60 above their 20-day average) is followed by a bounce; high breadth
(≥ 28.8%) by a fade. Long low / short high, only in bears:
- **+25–27%/yr at 1×**, on both halves;
- permutation p = 0.001;
- 221 of 240 grid settings positive on both halves;
- 16 of 22 capitulation episodes won;
- survives 5× costs;
- zero correlation with the trend book;
- **replicated on the 2018–19 bear with frozen parameters** (+21.7%/yr against −5.0% for
  always-long, `breadth_oos.py`).

*Candidate, not deployed:*
- DD is 20–42% at 1×;
- at $221 the $5 minimum skips a third of orders (holdout +8%/yr);
- a BULL regime runs today, so a paper book would sit flat until the next bear.

Nothing was found for chop.

**The best book changed.** MAX_UNITS 5 → 7 (see §2) is the first genuine RETURN improvement
the whole search found. It stacks with the time stop, and the triple (tight + time stop + 7
units) measures +10.43%/mo holdout WITH the bot's 10x guard (+10.76% without it) against
main's +4.88% (haircut, entry-sized), with a
typical year for $221 of **$536–584 with the guard** ($568–619 without it) against main's
$270–406 (§6). It is a backtest on a
mined holdout; the paper books decide.

**Seven paper books are live on the VM** (user deployed 2026-09-24; `blend_paper.py` sha256
2c144637…c72a verified against origin/main before the paste). Books #2/#5/#6/#7 form a 2×2
factorial over {time stop, 7 units} on the tight base. **The Bitget demo bot now carries both**
(2026-09-24): `longtrend_bot.py` imports `TSTOP_BARS`, `TSTOP_R`, `UNITS_MAX` and `MAX_LEVERAGE`
from `blend_paper.py`, asserts `MAX_UNITS == UNITS_MAX`, and applies blend_paper's 10× gross
guard to entries AND adds. The guard is essential here: the demo PAYS from ~2,900 SUSDT but SIZES
as $221, so the exchange would never refuse an add. It still also runs short boost and runner
sizing, so it is "triple + two extras", matching no paper book exactly. It tests the order path,
not the strategy. `tests/test_longtrend_rules.py` drives the real `cycle()` offline (8 tests),
and three mutations (an 8th unit, no guard, no time stop) each fail it. **It takes effect only
after the running demo process is restarted.** The books will not diverge until BTC closes a 4h
bar under the break level (~$81.6k on 09-23; `python btc_regime_now.py` shows it live) or a trade
reaches +10R.

**Chop and liquidation, the two questions the new config had not been asked**
(`backtest/regime_and_liq.py`, doc 11 part 10). Both answers matter more than the headline. The
improvement is **bull-only**: it doubles bull-market return and leaves chop at +0.20%/mo against
the deployed −0.16%, with bear slightly *worse*. 63% of days earn nothing, before and after. And
the 7-unit change is what takes the book past 10× gross leverage - 731 hours, peaking at 12.2×,
all of them in bulls - which only `blend_paper.py`'s existing margin guard prevents live. See §6.

**Four theses tested and refuted today**, all with predictions registered first:
- **"low capital is an advantage"** (`capacity_edge.py`): the gross edge gets monotonically WORSE
  in smaller coins and turns negative below ~$40M daily volume. All five predictions wrong. Low
  capital is not an advantage, only not a handicap.
- **"risk can buy crazy returns"** (`kelly_corrected.py`): 0.30 → 0.45% buys +0.34%/mo and
  multiplies P(80% drawdown) by nine. The holdout's own optimum is BELOW the tune half's.
- **more slots** (`slots_sweep.py`): 16 slots is tune-only (+2.02% at t 15 / +0.59% at t 1.2) and
  fails the same matched-risk control that MAX_UNITS passed - 12 slots at 0.40% earns more at the
  same drawdown. The 563 declined signals are the design working.
- **bar-phase blending** (`bar_phase.py`): retracted, see the trap table.

**"Should we remove the 10× guard, since it costs return?"** Asked and answered with a
measurement (doc 11 part 10b): **no.** At the triple book's 12.2× peak an **8.2% adverse move closes
the whole account**. It never happened during the 929 exposed hours (worst BTC 24h there: −4.85%) -
but BTC falls ≥8% in 24h in **1.24% of all hours** and the book holds alts that fall 27–34% at their
worst. The exposure is 1.6% of hours and it sits entirely in bull regimes, which is when reversals
arrive. Decisively: **the backtest cannot model liquidation at all**, so the unguarded return is
computed in a world without the risk that removing the guard creates. Also: the guard is what makes
MAX_UNITS=7 a *better deployment of risk* rather than leverage the model scores as free.

**What moves BTC (doc 12, `backtest/btc_signals.py`).** Fourteen market-timing signals were
tested: Coinbase premium, exchange flows, MVRV, positioning, taker flow, Nasdaq, DXY, VIX,
momentum and others. Only the Coinbase premium and BTC's 7/28/90d momentum held their sign on
both halves, weakly (t ≈ 1.9–2.0), and **neither improves the bot**:
- as a risk dial it helps the holdout only (`btc_dial.py`);
- as an exit it hurts;
- as an entry gate it is noise (`btc_entry_gate.py`).

As a pure BTC timing rule, **the bot's own 1000h gate beat all of them** (Sharpe 1.12 vs 0.68
for holding; `btc_timing.py`). Two signals work contrarian: top traders piling long, and calm
VIX, both precede weaker weeks.

**The graveyard re-checked on the corrected engine** (doc 11 part 2, `graveyard_rescore.py`):
- no buried edge among exits, sleeves, trails, slots or the entry band;
- the bb(30,1.25) and 10/20/40-trail near-misses were the unfunded engine, and both now lose
  on both halves;
- the liquidation-cascade bounce, which never had a verdict, is dead on 4 years
  (`cascade_redux.py`);
- the options premium is still ~0 in 2026.

The pyramid dimension was the one I did NOT re-check. The other session did, and that is where
the edge was. Lesson: re-check EVERY parameter family of the engine after a measurement fix,
not just the ones that were killed.

**"Crazy returns on low capital" answered** (doc 11 part 3, `lottery.py`, `kelly_corrected.py`):
- $10 cannot trade: Bitget's $5 minimum rejects 87–96% of units;
- $50 is the practical floor;
- capital buys dollars, not rate;
- risk above ~0.35–0.45% buys ruin faster than return;
- on the no-hindsight PIT top-12, a typical year at 0.30% is ~2.2× (about 2× without MYX,
  which alone is 27% of that universe's long profit);
- 5× happens in roughly one year in four.

**Housekeeping.**
- `.gitignore` covers `logs/*_state.json`, which misses `blend_state_tight.json`,
  `…_tstop.json`, `…_triple.json` and the others. Harmless while nobody `git add -A`s, but a
  committed copy would be restored over live state by the VM's `git reset --hard`. Worth adding
  `logs/blend_state*.json`.
- The 2026-09-23 advice that 0.6% per unit was fine for "crazy returns" was wrong for a book
  meant to keep running: it holds only on a ~3-month horizon (`kelly_corrected.py`).

**The combination book was verified, not taken on trust** (2026-09-24). `combo_paper.py` built by
another session: 432 lines, parses, **7 tests pass** (at `tests/test_combo_paper.py`, not the repo
root), running at $220.87, committed and pushed. Checked specifically that it cannot damage the
seven VM books: its only reference to them is a **read** of `blend_state_triple.json` in
`triple_ref()`, for its pre-registered H1 comparison. It writes only its own files. Day 0: 6 trend
positions, 12 market-neutral names, and the bear sleeve **correctly idle** (bull regime, 85% of
coins above their 20-day average).

Two bugs came out of that build, one caught before it ran and one still open - both now in the trap
table, and the second as mistake #15 and §7b:
- `os.kill(pid, 0)` **kills the process on Windows**. Caught in a draft.
- `mn_paper.py` over-counts funding roughly **twofold** (8 settlements for a one-day mark). The
  first report called it a daily double-count; measuring it showed the window also has no
  `endTime`, so it is larger than that. **Not fixed** - it is a live pre-registered book, and the
  call to fix it belongs to the user. The recommendation stands: fix now, while that book has one
  mark, rather than discount three months of record later.

**WHERE THE DAY LEFT THE GOAL** ("crazy returns, or small capital, or something out of the box").

One of the three was achieved. **MAX_UNITS 5 → 7 is worth ~+1.19%/mo live** and works at $100
capital - that is the small-capital half. The crazy-returns half was tested four ways and refused
every time: capacity tiers, the risk dial, more slots, bar-phase blending. Eleven new test files,
four theses refuted with predictions registered first, and **two of my own claims retracted plus a
third corrected**, all for the same error - comparing medians across random draws instead of pairing
within them.

**Two caveats that belong beside the headline, not below it.** The book is a **bull-market
amplifier**: 63% of days are chop or bear and earn approximately nothing, before and after today's
work. And the 7-unit change is what takes the book toward the liquidation line, so its safety rests
on the margin guard, not on the rule itself.

**What NOT to do next.** Nothing is left to tune. Six years has now been swept across indicators,
timeframes, exits, stops, universe size, capacity, leverage, bar phase, ATR period, pyramid spacing
and slot count. The one result that survived did so because the test confirming it is a test that was
watched to FAIL on something else the same day - that is the standard, and another sweep on this
split cannot meet it. **The seven books have to earn their own evidence forward.** First meaningful
read: ~30 closed trades per book, or whenever BTC closes a 4h bar below the break level and books
#2/#5/#6/#7 finally diverge.

### 2026-09-23 - three flattering bugs, the numbers halved, two books added

**Three bugs in the engine every stored result rested on** (doc 03, #12-14). Each made
results look BETTER than they were, which is the direction to expect:

- **funding was never charged** - 21.5% of lifetime long R, 46% on the 12h sleeve
- **4h/12h rows carried the bar LABEL**, 3h and 11h after the real entry, so anything using
  `asof(t0)` read the future. The short boost did: 118 of 224 "boosted" shorts were boosted
  only because BTC broke down AFTER they opened. Its value fell from +1.3-2.3 to ~+0.5%/mo
- **trades compounded against equity they were never sized on** - roughly 2x everything

**The planning numbers changed, and not slightly.** $200 over a year: $316 -> **$241** (main),
**$285** (tight). Per month +4.3% -> **+1.6%** main, **+3.0%** tight. Worst month -34% ->
**-41.6%**. The one figure that survived every correction: **56% of months lose money.**

**What improved.** The tight exit now beats main on BOTH halves (+2.87 +- 0.28 tune, +1.98 +-
0.35 holdout, entry-sized); before the fixes it read as costing tune-half return. And the
market-neutral book is better as an **overlay on the same margin** (k=0.25 on tight: +1.2%/mo,
no extra drawdown, winning weeks 37% -> 50%) than as a split of capital, which is what I first
told the user and had to correct.

**Two books added, six running.** `mn_paper.py` (market-neutral, pre-registered, verdict at 26
rebalances) and blend_paper's fifth book **TSTOP** = tight + close a long still under +2R after
100 bars. Its return edge is holdout-only against tight; its **worst-month** edge shows on both
halves, and that is the part to trust.

**Doc 11, the money-machine search.** Seven mechanism-based ideas plus ~17 others: all dead.
Verified by re-running, one count corrected (28 of 30 grid configs lose, not 24 of 26). The
pattern is the finding: every real edge is priced within a second by co-located bots, competed
to zero by the capital that found it, or too rare to separate from noise.

**Deployment fixed.** The user made the repo public, so the VM now deploys by `git pull` - a
69-line script instead of 584 lines of base64. Three paste attempts failed first, for two
reasons now in the trap table: Run command wraps near 50 chars, and `U=sudo -u $OWNER` is not
an assignment.

**`--status` now reports realised / marked / floor for all five books.** Live reading:
realised $209.77, **marked $440.36**, floor $153.06. Realised alone badly understates a book
holding runners - losers stop out fast and get banked, winners sit open for weeks - which is
why 35 closed trades read -1.03R while 12 open positions sat at +4R to +8R. The FLOOR is where
an exit-rule difference appears first, weeks before realised equity moves.

**One piece of luck worth recording.** The entry-sized fix landed about a week before those 12
runners close. Under the old line they would have credited ~$480 instead of ~$233 on a $221
account, and it would have been reported as real.

**What NOT to do next.** Nothing needs tuning. Six books are accumulating forward data, and
after three bugs in one day that all pointed the same way, forward data is the only evidence
left that cannot be mined. Next meaningful read: ~30 closed trades per book, or whenever BTC
breaks its 4h trend and the books finally diverge.

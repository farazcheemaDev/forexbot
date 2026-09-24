# CLAUDE.md — read this first, every session

*Last updated 2026-09-24. Dated history in §10.*

This file is the orientation for a new session. It is deliberately short. It tells you the
goal, the rules that keep the numbers honest, where everything is, and the traps that have
already produced wrong answers in this project more than once.

**Read this file, then [`docs/09-pick-up-here.md`](docs/09-pick-up-here.md) for live state,
then [`docs/02-what-failed.md`](docs/02-what-failed.md) before proposing any strategy.**

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
| **Haircutting a LOSS** | The 3× hindsight haircut divides an *annualised* rate by 3, which shrinks losses as eagerly as gains: a real −30% month reads −3.3%, and a year that ended at $92 reads $172. Found while answering "what happens at worst" — the first table showed a worst-ever month of −3.5% | Quote **downside raw, upside haircut**, and label which is which |
| **A non-stable sort on an append-only log** | `sort_values` defaults to quicksort. It reordered simultaneous closes and misaligned a log's own `equity` column against its rows, reading as a $4,534 self-check failure on a log that was correct | `kind="stable"` whenever row order carries meaning |
| **Run command wraps long lines** | Near 50 chars, and a wrapped line's tail RUNS as a command. A wrapped COMMENT loses its `#` and executes. This destroyed a 22KB base64 one-liner | Every line in `deploy/*.sh` under 44 chars; payloads in heredocs, which `base64 -d` decodes however they are broken up |
| **`VAR=cmd arg` is not an assignment** | `U=sudo -u $OWNER` makes the shell treat `U=sudo` as a prefix and run a command called `-u`. Aborted a live patch at line 34 | No spaces in an assignment value |
| **Testing only the part you changed** | Both of the two bugs above survived a test that exercised only the payload block, because both were outside it | Run the WHOLE script against a fake target with stubbed `systemctl`/`sudo`/`sleep` |
| **Comparing medians across orderings** | Per-ordering noise here is 0.25-0.48 %/mo, so two medians drawn from different seed outcomes differ by several tenths for nothing. It produced TWO confident claims in one hour that both died under a paired test: a blend "beating the average phase with 4-6 points less drawdown" (paired: +0.04%/mo, t=0.19) and "the venue minimum costs $221 0.29%/mo" (paired: -0.02%/mo, t=-0.37) | Pair on the SAME ordering, take the difference, report mean +- se and a win count - as `graveyard_rescore.py` already did |
| **`os.kill(pid, 0)` as a liveness check** | On Windows this is not a no-op - any signal other than CTRL_C/CTRL_BREAK calls `TerminateProcess`, so the “check” **kills the process it is checking**. Caught in a draft of `combo_paper.py` before it ran | Read-only check: PowerShell `Get-Process -Id`, as `mn_paper.single_instance` does |
| **An accrual window left open at one end** | `mn_paper` sums funding from `last_fund_ms` with no `endTime`, so the window runs to NOW while the cursor advances only to the BAR - and Binance's `startTime` is inclusive as well. Measured: **8 settlements summed for a one-day mark**, where a day has 3. Funding roughly doubled (mistake #15, still open) | Half-open and bounded at BOTH ends, `(last, this_bar]`, with the cursor advancing to the same edge |
| **Mixed datetime64 units in the row set** | t0 comes back as `[us]` and t1 as `[ms]`, so `date_range` inherits `[us]` from its bounds while `Timestamp.value` returns ns. `searchsorted` then puts every span past the end of the grid and a whole leverage series came back silently ZERO (2026-09-24, cost a run) | Force BOTH sides with `.as_unit("ns")`, and assert the result is non-zero rather than trusting it |
| **A test that cannot exhibit the bug** | With one position open at a time the two compounding conventions are arithmetically IDENTICAL, so a non-overlapping test showed $0.00 difference and passed while proving nothing. The bug only bites when positions OVERLAP | Construct the case so the bug MUST appear if it is present |
| **Timestamp unit mismatch** | `.asof()` raises "Cannot losslessly convert units" (ms index vs ns clock) | `blend_paper._ns()` |
| **Bar label read as entry time** | `asof(t0)` on a 4h/12h row reads a bar that closed hours after the entry. The short boost's "+0.481R" was 118 look-ahead trades; causal, it is +0.305R and worth ~+0.5%/mo | `causal_t0.real_t0(rows)` |
| **Fees charged, funding not** | Every figure for the deployed book was fees-only. Funding takes the tune half +16.5% → +12.2%/mo | `funding_cost.charged(...)` |
| **Scaling a trade by equity it was never sized on** | Daily-sum / sequential compounding credit open runners with profit other trades banked: ~2× the achievable return. `blend_paper.py`'s paper equity does it too | entry-sized curve, `mtm_sizing.simulate(..., "realised")` |

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
                     $221 paper account, pre-registered, verdict at 6 months. Local; health.py sees it
xs_paper.py        an EARLIER pre-registered XS test (21 coins, daily). Frozen — do not edit
longtrend_bot.py   the Bitget demo bot. ALLOW_REAL = False
micro_bot.py       the $10 go-for-broke bet. ALLOW_REAL = False
health.py          "is anything wedged or dead" — three signals per bot
docs/              00-12 + README. Doc 02 is the graveyard; read it before proposing.
                     11 = money-machine search, graveyard re-check, lottery odds. 12 = BTC signals
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
- **`ALLOW_REAL = False`** in `longtrend_bot.py` and `micro_bot.py` is a gate a **human**
  must edit. Never flip it, never work around it.
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

---

## 10. Session log

*Newest first. One entry per working day, and only what a later session needs to know -
the detail lives in the numbered docs.*

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

*Status:* candidate, not deployed. The whole mix runs forward as **`combo_paper.py`** (started
2026-09-24, local, pre-registered, verdict at 6 months, doc 14 section 9).

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

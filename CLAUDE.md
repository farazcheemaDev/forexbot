# CLAUDE.md — read this first, every session

*Last updated 2026-09-23.*

This file is the orientation for a new session. It is deliberately short. It tells you the
goal, the rules that keep the numbers honest, where everything is, and the traps that have
already produced wrong answers in this project more than once.

**Read this file, then [`docs/09-pick-up-here.md`](docs/09-pick-up-here.md) for live state,
then [`docs/02-what-failed.md`](docs/02-what-failed.md) before proposing any strategy.**

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
blend_paper.py     THE LIVE PAPER BOOKS — five in one process
                     main / tight / sized / sboost / tstop (tight + time stop)
mn_paper.py        the 5th book: market-neutral, pre-registered, verdict at 26 rebalances
xs_paper.py        an EARLIER pre-registered XS test (21 coins, daily). Frozen — do not edit
longtrend_bot.py   the Bitget demo bot. ALLOW_REAL = False
micro_bot.py       the $10 go-for-broke bet. ALLOW_REAL = False
health.py          "is anything wedged or dead" — three signals per bot
docs/              00-10 + README. Doc 02 is the graveyard; read it before proposing
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

- **Capital does not change the percentage.** Above ~$25 the rejection rate is 0% and the
  return is identical; $10 rejects 2% of signals. Capital buys dollars, not rate.
- **The old +58% was inflated mostly by compounding**, not by the market. See mistake #14.
- Full history, entry-sized: main +84% haircut / +251% raw median year, tight +113% / +338%.
  **2021 alone made ~40% of lifetime profit.** Full-history figures are not planning numbers.
- P(losing month) is the one figure no modelling choice can flatter — the haircut is
  monotonic, so it cannot change a sign. It was ~56–57% under every correction.

## 7. Hard safety rules — do not cross these

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

## 8. How to check what is running

```bash
python health.py
```

On the VM (Azure portal → VM → Run command → RunShellScript):

```bash
cd /opt/forexbot && ./.venv/bin/python blend_paper.py --status
```

`git pull` on the VM **fails** — no cached credentials, no interactive prompt. Patch in
place with `deploy/patch_*.sh`, which are gzip+base64 and sha256-verified.

## 9. Working style the user has asked for

- They want things **tested, not discussed.** "Turn every stone." Run the experiment.
- They want **plain English** for results, and honest ones — including when the answer is
  "this is dead."
- **Never present a backtest as a return they will get.** State the haircut, the holdout,
  and the regime dependence every time.
- When a result looks good, the next move is to look for the bug that made it look good.
  Every large improvement in this repo's history was a bug until proven otherwise.

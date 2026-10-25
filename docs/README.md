# Documentation

Everything we know about this project. **Current state is one page: [`STATUS.md`](STATUS.md)** - what is running where, on
which code, the paper result beside its backtest and drawdown, the real-money gate and the dates, with the day it was last
verified. Everything else here is either a rule, a research note, or a dated snapshot.

**New session? [`CLAUDE.md`](../CLAUDE.md) first** - the short version of the rules and the traps, and the only file you
must not skip - then STATUS, then the rest in the order below.

## 1. Start here, in this order

| # | Document | What's in it |
|---|---|---|
| - | [`CLAUDE.md`](../CLAUDE.md) | **The orientation file.** The goal, the twelve validation rules, the traps that have produced wrong answers here, the hard safety gates, and a dated session log (its s10 is what changed most recently and why). |
| - | [**STATUS**](STATUS.md) | **The current state, verified.** What is running where, code identity, each book's paper result next to its backtest, the day-45 kill line, the dates, what waits on the user. Re-check with `bash deploy/verify_status.sh`. |
| 22 | [The decision rule](22-decision-rule.md) | **When real money may go in (fund / kill / extend lines, the BTC-1000h benchmark, a tested PKR money path), the code freeze to 2027-04-09 and the research stop date 2026-12-31 - written 2026-10-10 before the verdict data; the day-45 checkpoint added 2026-10-23.** |
| 02 | [The graveyard](02-what-failed.md) | Every approach tested and killed, with the number that killed it. Read before proposing anything. |
| 03 | [Mistakes and rules](03-mistakes.md) | Every bug that produced a wrong result, and the rule added to stop it recurring. |
| 21 | [The graveyard audit](21-graveyard-audit.md) | **Every kill in the repo, its backing rated, every thin one re-tested (2026-10-08).** Nothing came back as a book; the MN short-leg stop kill was reversed (now in the bot); "volume is useless" and "every reversal fails" were too broad. Read with doc 02's last entry, the combination sweep. |

## 2. What the bot is, and the end goal

| # | Document | What's in it |
|---|---|---|
| 26 | [The one bot - the end goal](26-the-one-bot.md) | **THE END GOAL**: one bot, five layers (edges, eyes on the world, risk, execution, a learning loop that proposes but never self-tunes), where each stands today, and the road from here. |
| 20 | [The product](20-the-product.md) | What combo_bot is, what it earns in each market type, and the sideways gap with every test that tried to close it. |
| 17 | [The machine, v2](17-the-machine.md) | Four books on one account: trend + market-neutral + bear sleeve + **capped crash bids**. $300 typical 12 months **$1,812** (6 yrs) / **$1,625** (last 2), worst month −29% / −25%, fall 57% / 45%. The crash bids work on **Bitget's own prices** (+1.01% a fill, same as Binance). Size dial: ×1.2 buys 8% more for a −34% worst month - stay at ×1.0. Every risk in one table. The crash desk is built into the live bot (`--wick`) and ran its order path on the demo. |
| 01 | [The strategy](01-strategy.md) | Exactly what the bot trades and why each setting is what it is. |
| 04 | [Running the bots](04-operations.md) | **`python health.py`** - is it working? Plus start/stop, deployment, the real-money gate. (What is live *now*: STATUS.) |
| 06 | [Deploying $221](06-deploy-221.md) | *2026-09-13.* Putting the validated config on a VPS: the steps, and the two things that would invalidate the test. (Deployment is by `git pull` now - CLAUDE.md s8.) |

## 3. The trader, the sentiment engine and the dashboard

| # | Document | What's in it |
|---|---|---|
| 23 | [The NASDAQ trader](23-his-strategy.md) | **The NASDAQ trader, everything known**: his record (real, live, not luck), his method, his edge (the side, ~95%), every source ruled out, what a bot can take from him. The lab notebook behind it: [`strategy_analysis/his_strategy.md`](../strategy_analysis/his_strategy.md). |
| 24 | [The dashboard](24-dashboard-plan.md) | **The live dashboard**: every trade and book live, a scorecard against the backtest, safe "learning" (record, score, propose - never self-tune), sentiment sources and costs. *Planned 2026-10-16; built since* (STATUS s2). |
| 25 | [The sentiment engine](25-sentiment-engine.md) | **Designed, then tested**: collect, enrich, score; each news category's weight LEARNED from the price moves that followed it (event studies), then vetoes / exits for the bot. Its s7 has the results: one lead (crowd positioning), chatter dead. |

## 4. Research notes

| # | Document | What's in it |
|---|---|---|
| 10 | [The second book](10-market-neutral.md) | Market-neutral cross-sectional momentum: **correlation +0.09** with the live book, and why its bear-market performance is carry, not prediction. |
| 11 | [The money-machine search](11-money-machine-search.md) | Seven mechanism-based ideas (funding settlements down to tick data, delistings, grid bots, HLP, CME gaps, first-perp shorts, the kimchi premium). **None is a machine**, and each result shows where edges go to die. |
| 12 | [BTC signals](12-btc-signals.md) | Fourteen market-timing signals (Coinbase premium, exchange flows, MVRV, positioning, Nasdaq, dollar, VIX, momentum). Two weakly predict BTC; **none improves the bot**; the bot's own 1000h gate is the best BTC timing rule tested. Live readout: `python btc_regime_now.py`. |
| 13 | [Bear markets: the breadth signal](13-bear-breadth.md) | 21 signals tested *inside* bear and chop regimes. One passes (Holm, both halves): **market breadth in bears**, where capitulation bounces and broad bear rallies fade. Traded only in bears: +25–27%/yr at 1×, zero correlation with the trend book. Permutation p = 0.001, 92% of 240 settings positive on both halves, and **it replicated on the 2018 bear with frozen parameters** (+21.7%/yr). Now the bear sleeve in the machine (DD 20–42% at 1×). Nothing passes in chop. |
| 14 | [Why the account halves, and the fix](14-drawdown.md) | The falls come after booms, in sideways/rising markets, not bears. 56 named fixes tested against "just bet smaller": all fail except an **equity anchor** (size from the 21-day average). What works is **trend at 70% + anchor + bear sleeve + half-size market-neutral**: $221 typical year $736 vs $584, biggest fall 35% vs 53%, no losing year in six. Four bar phases, both halves. |
| 15 | [Profiting from crashes](15-crash-wicks.md) | You cannot short a crash; you can BUY one. Resting bids 10% under the price on the top-20 coins, sold at the end of the same hour: **+30.8%/yr** with crash-hour slippage, positive every year and both halves, survives without 2021, works on Bitget's own candles. Worst month gets worse. **Superseded by doc 16's rule** (this version hid a near-wipe-out). |
| 16 | [Crash buys made safe; the worst month; coming back](16-crash-buys-safe.md) | Crash bids get better by **skipping BEAR days and using the top-40** (the bids' own worst month −22% → −1%/−3%). Five-minute bars show doc 15's book **hid a near-wipe-out**: on 2025-10-10 the bids and the trend book together left 10% of the account in one hour. Cancel the remaining bids after 10 fills: 47% left, +16%/yr alone. Sixteen monthly brakes all lose to just betting smaller. Every 20%+ fall recovered; a made-up −50% month comes back in 52–100% of cases within 2 years, **unless withdrawals continue through the loss**. Paper book `wick_paper.py` pre-registered (Bitget + Binance). |
| 18 | [Back to forex](18-forex-again.md) | The trader's video and screenshots hold **no chart** - his entry choice (+10 pts a trade, his_strategy.md s22) cannot be traced further without asking him. **33 new forex tests all fail after Exness costs** (nine documented calendar/session effects, the Asian-range breakout). One holds: **12-month trend on commodities + indices, +5.5%/yr at 10% volatility 2004-2026, both halves - but only on a SWAP-FREE account** (with swap, -1.6%/yr), and at $300 only on a Cent account. FX legs earn nothing. |
| 19 | [All-weather](19-all-weather.md) | Another session's MN 1.5x / sleeve 1.5x weights for sideways months. **Not adopted** - CLAUDE.md s10 (2026-09-29) says why. |
| 05 | [VSA](05-vsa.md) | The one open question, and how it got settled. |
| 07 | [The $5–10 account](07-micro-account.md) | The go-for-broke bet: 29.7% chance of 5×, 70% chance of zero. The odds, and why two of my predictions about it were wrong. (Re-measured 2026-10-06: `backtest/micro_honest.py`.) |
| 08 | [Polymarket](08-polymarket.md) | A +25% apparent edge, **four** artifacts found inside the same test, and why $5 buys worse evidence than the free collector. (Weather markets and the 80-90c favourites were tested later and killed: doc 22 s5. The sum-gap structure scan was killed 2026-10-26: doc 02, last entry.) |

## 5. Dated snapshots - do not use for current state

| # | Document | What's in it |
|---|---|---|
| 09 | [Pick up here](09-pick-up-here.md) | *2026-10-08 / 10-09.* The machine names (v2 / v3 / MIX B / E) and the 2026-10-08 narrative. Its "what is running" table is out of date; STATUS replaces it. |
| 00 | [Where we stand](00-current-state.md) | *2026-09-23.* Plain English on capital, the regime dependence and the early exits. Its planning figures and its "what's running" section are superseded (banner at the top). |

## Also in the repo

- [`LOCAL_MT5_TASKS.md`](LOCAL_MT5_TASKS.md) - the task list for a LOCAL session on the PC with MT5 open.
- [`strategy_analysis/validation_protocol.md`](../strategy_analysis/validation_protocol.md) - the full testing gates, in
  technical detail. This is the authority; docs 02 and 03 here are the readable summary of it.
- [`README.md`](../README.md) - repo-level overview and the MT5 smoke test.

## House rules for this folder

1. **A number without a source is not a number.** Every figure here says which
   file produced it, so it can be re-run.
2. **Record the prediction before the test, not the interpretation after it.**
   Every result in doc 02 that was a surprise says so.
3. **Kills are permanent unless the measurement itself was broken.** Six
   strategies were wrongly killed by a profit-cap bug and had to be revived;
   that is the only legitimate reason to reopen something in the graveyard.
4. **A headline return never stands alone.** Put its forward-paper result, its drawdown and the real-money gate beside
   it, and say whether it is a backtest. Keep STATUS true when anything running changes.

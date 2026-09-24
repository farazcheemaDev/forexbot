# Documentation

Everything we know about this project, in the order you'd want to read it.
**New session? [`CLAUDE.md`](../CLAUDE.md) first** - it is the short version
of the rules and the traps, and it is the only file you must not skip.

| # | Document | What's in it |
|---|---|---|
| 09 | [**Pick up here**](09-pick-up-here.md) | **Start here after a break.** What's running, what's optional, and what to expect. |
| 00 | [Where we stand](00-current-state.md) | Plain English. The numbers, the money, what's running right now. |
| 01 | [The strategy](01-strategy.md) | Exactly what the bot trades and why each setting is what it is. |
| 02 | [The graveyard](02-what-failed.md) | Every approach tested and killed, with the number that killed it. Read before proposing anything. |
| 03 | [Mistakes and rules](03-mistakes.md) | Every bug that produced a wrong result, and the rule added to stop it recurring. |
| 04 | [Running the bots](04-operations.md) | **`python health.py`** — is it working? Plus what's live, start/stop, deployment, the real-money gate. |
| 05 | [VSA](05-vsa.md) | The one open question, and how it got settled. |
| 06 | [Deploying $221](06-deploy-221.md) | **Start here to put the validated config on a VPS.** Steps, and the two things that would invalidate the test. |
| 07 | [The $5–10 account](07-micro-account.md) | The go-for-broke bet: 29.7% chance of 5×, 70% chance of zero. The odds, and why two of my predictions about it were wrong. |
| 08 | [Polymarket](08-polymarket.md) | A +25% apparent edge, **four** artifacts found inside the same test, and why $5 buys worse evidence than the free collector already running. |
| 10 | [The second book](10-market-neutral.md) | Market-neutral cross-sectional momentum: **correlation +0.09** with the live book, and why its bear-market performance is carry, not prediction. |
| 11 | [The money-machine search](11-money-machine-search.md) | Seven mechanism-based ideas (funding settlements down to tick data, delistings, grid bots, HLP, CME gaps, first-perp shorts, the kimchi premium). **None is a machine**, and each result shows where edges go to die. |
| 12 | [BTC signals](12-btc-signals.md) | Fourteen market-timing signals (Coinbase premium, exchange flows, MVRV, positioning, Nasdaq, dollar, VIX, momentum). Two weakly predict BTC; **none improves the bot**; the bot's own 1000h gate is the best BTC timing rule tested. Live readout: `python btc_regime_now.py`. |
| 13 | [Bear markets: the breadth signal](13-bear-breadth.md) | 21 signals tested *inside* bear and chop regimes. One passes (Holm, both halves): **market breadth in bears**, where capitulation bounces and broad bear rallies fade. Traded only in bears: +25–27%/yr at 1×, zero correlation with the trend book. Permutation p = 0.001, 92% of 240 settings positive on both halves, and **it replicated on the 2018 bear with frozen parameters** (+21.7%/yr). **A candidate, not deployed** (DD 20–42% at 1×). Nothing passes in chop. |
| 14 | [Why the account halves, and the fix](14-drawdown.md) | The falls come after booms, in sideways/rising markets, not bears. 56 named fixes tested against "just bet smaller": all fail except an **equity anchor** (size from the 21-day average). What works is **trend at 70% + anchor + bear sleeve + half-size market-neutral**: $221 typical year $736 vs $584, biggest fall 35% vs 53%, no losing year in six. Four bar phases, both halves. **Candidate, not deployed.** |
| 15 | [Profiting from crashes](15-crash-wicks.md) | You cannot short a crash; you can BUY one. Resting bids 10% under the price on the top-20 coins, sold at the end of the same hour: **+30.8%/yr** with crash-hour slippage, positive every year and both halves, survives without 2021, works on Bitget's own candles; added to the final version on $300 the typical year goes $1,642 -> $1,937. Worst month gets worse. **Candidate, no paper book yet.** |
| 16 | [Crash buys made safe; the worst month; coming back](16-crash-buys-safe.md) | Crash bids get better by **skipping BEAR days and using the top-40** (the bids' own worst month −22% → −1%/−3%). Five-minute bars show doc 15's book **hid a near-wipe-out**: on 2025-10-10 the bids and the trend book together left 10% of the account in one hour. Cancel the remaining bids after 10 fills: 47% left, +16%/yr alone. Sixteen monthly brakes all lose to just betting smaller. Every 20%+ fall recovered; a made-up −50% month comes back in 52–100% of cases within 2 years, **unless withdrawals continue through the loss**. **Candidate; paper book `wick_paper.py` pre-registered (Bitget + Binance).** |

## Also in the repo

- [`CLAUDE.md`](../CLAUDE.md) — **the orientation file. Read it before this folder.**
  The goal, the nine validation rules, the eight traps that have produced wrong
  answers here, and the hard safety gates.
- [`strategy_analysis/validation_protocol.md`](../strategy_analysis/validation_protocol.md) —
  the full testing gates, in technical detail. This is the authority; docs 02 and
  03 here are the readable summary of it.
- [`strategy_analysis/his_strategy.md`](../strategy_analysis/his_strategy.md) —
  the original human scalper's method, reverse-engineered and tested.
- [`README.md`](../README.md) — repo-level setup.

## House rules for this folder

1. **A number without a source is not a number.** Every figure here says which
   file produced it, so it can be re-run.
2. **Record the prediction before the test, not the interpretation after it.**
   Every result in doc 02 that was a surprise says so.
3. **Kills are permanent unless the measurement itself was broken.** Six
   strategies were wrongly killed by a profit-cap bug and had to be revived;
   that is the only legitimate reason to reopen something in the graveyard.

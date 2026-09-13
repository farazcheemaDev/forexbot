# Documentation

Everything we know about this project, in the order you'd want to read it.

| # | Document | What's in it |
|---|---|---|
| 00 | [Where we stand](00-current-state.md) | Plain English. The numbers, the money, what's running right now. |
| 01 | [The strategy](01-strategy.md) | Exactly what the bot trades and why each setting is what it is. |
| 02 | [The graveyard](02-what-failed.md) | Every approach tested and killed, with the number that killed it. Read before proposing anything. |
| 03 | [Mistakes and rules](03-mistakes.md) | Every bug that produced a wrong result, and the rule added to stop it recurring. |
| 04 | [Running the bots](04-operations.md) | What's live, how to start/stop, Oracle deployment, the real-money gate. |
| 05 | [VSA](05-vsa.md) | The one open question, and how it got settled. |
| 06 | [Deploying $221](06-deploy-221.md) | **Start here to put the validated config on a VPS.** Steps, and the two things that would invalidate the test. |
| 07 | [The $5–10 account](07-micro-account.md) | The go-for-broke bet: 29.7% chance of 5×, 70% chance of zero. The odds, and why two of my predictions about it were wrong. |
| 09 | [**Pick up here**](09-pick-up-here.md) | **Start here after a break.** What's running, what's optional, and what to expect. |
| 08 | [Polymarket](08-polymarket.md) | A +25% apparent edge, three artifacts found inside the same test, and the forward test now running to settle it. |

## Also in the repo

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

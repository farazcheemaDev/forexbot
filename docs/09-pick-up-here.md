# Pick up here

*Rewritten 2026-09-23. State below verified the same day with `python health.py`.*

**If you are a new Claude session, read [`CLAUDE.md`](../CLAUDE.md) first.** It has the
validation rules and the traps. This file is just "what is running and what is next."

## Nothing is broken. Nothing is urgent.

`health.py` ends with *"Nothing needs attention."*

| What | Where | Status |
|---|---|---|
| **$221 blend — the validated strategy** | Azure VM, `blend-paper` | **running 24/7** ✅ |
| **Three forked paper books** (tight / sized / short-boost) | same process on the VM | **running, all four books live** ✅ |
| Bitget demo order-path test | your PC, pid 7612 | **running, 3 longs open, heartbeat 11s** ✅ |
| Polymarket forward collector | your PC, Startup launcher | running, 2,065 rows ✅ |
| Status page | Azure VM, `status-server` | running ✅ |
| $10 micro bot | built, `ALLOW_REAL = False` | off, by design |

## The four paper books, and why there are four

One process, four independent books, all on the same live price feed. They exist because
2026-09-22 produced six variants that all "helped the holdout and cost the tune half" —
which is exactly what an exhausted holdout looks like. Rather than pick one on a backtest,
all of them run forward and the market decides.

| book | what is different | forked |
|---|---|---|
| **main** | the validated config, unchanged | original |
| **tight** | long trail drops to 5×ATR once BTC breaks its 4h trend | 2026-09-21 23:30 |
| **sized** | entry size tilted ±90% by a frozen at-entry runner model | 2026-09-22 19:37 |
| **short-boost** | short risk ×5 | 2026-09-22 21:05 |

**All four are still identical**, and will stay that way until BTC breaks. The tight and
short-boost books only diverge on a **4h close below roughly $81,752** (−5.2% from here),
which historically fires about every 15 days. Don't read "no divergence" as "no effect."

Check them:

```bash
cd /opt/forexbot && ./.venv/bin/python blend_paper.py --status
```

## The Bitget demo bot now runs all three validated rules

As of 2026-09-22 `longtrend_bot.py` imports the tight exit, the short boost and the runner
sizing straight from `blend_paper.py`, so the demo account and the paper books cannot drift
apart. Dry runs write to `logs/longtrend.dryrun.log` and their **own** state file — that
separation exists because sharing a log once made the live book look flat when it was not.

`ALLOW_REAL = False` is still in place. A human flips that or nobody does.

## What to expect, so it isn't a surprise

**Read the capital table in [doc 00](00-current-state.md).** The two numbers that matter:

- **57% of single months lose money** (holdout, and the haircut cannot change that sign)
- **capital does not change the percentage** — above ~$25 every level returns the same rate

A month tests the machinery, not the returns. Numbers start meaning something around 30
closed trades, and you lose 4 trades in 5 **by design**.

## The one new thing worth your attention

[**Doc 10 — the second book.**](10-market-neutral.md) Market-neutral cross-sectional
momentum on the survivorship-free universe: Sharpe 1.16, and **correlation +0.09** with the
book you are already running. Mixing 25% of it in raises Sharpe 1.65 → 1.80, *lowers*
drawdown, and takes the weekly win rate from **32% to 53%** for 11% less return.

It is **not deployed and should not be** until it runs forward as a fifth paper book. Two of
its six years are flat-to-negative, 2026 is carrying a third of the result, and the minimum
order has never been simulated against a 120-name book on $200 — which is where it will
probably break.

## Open jobs, in the order I'd do them

1. **Run the market-neutral book as a fifth paper book** (~1 hour). It is the only
   unexplored direction left that isn't more mining. Everything needed is in
   `backtest/market_neutral.py`.
2. **Move the Bitget demo bot to the VM** (~15 min, [doc 06](06-deploy-221.md)). Stop the
   local bot first — one account, one bot, or every order doubles. IP-whitelist the key to
   the VM and drop Withdraw permission while you are in there.
3. **Reconcile the 1000h / 200h gate discrepancy.** The live bots gate on a 1000-hour BTC
   average; the backtests were run on 200. Don't "fix" it silently — re-run the backtests on
   1000h and see what changes.
4. **Binance testnet keys, created by you**, if you want a real slippage measurement.
   `blend_testnet.py` reads them from the environment only.
5. **Nothing on Polymarket.** 229 resolutions in and the +0.25 edge claim is effectively
   refuted (8/14 inside the band). Do not deposit. [Doc 08](08-polymarket.md).

## What NOT to do

**Stop sweeping the holdout.** ~75 configurations in one day, then dozens more on
2026-09-22, against the same six years and the same single split. Further sweeps are mining,
not research — and doc 02 records four separate cases where a "plateau with an interior
optimum" was a look-ahead bug rather than an edge.

The next real information comes from the paper books running forward, not from this machine.

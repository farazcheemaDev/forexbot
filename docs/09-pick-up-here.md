# Pick up here

*Rewritten 2026-09-23. State below verified the same day with `python health.py`.*

**If you are a new Claude session, read [`CLAUDE.md`](../CLAUDE.md) first.** It has the
validation rules and the traps. This file is just "what is running and what is next."

## Nothing is broken. Nothing is urgent.

`health.py` ends with *"Nothing needs attention."*

| What | Where | Status |
|---|---|---|
| **$221 blend — the validated strategy** | Azure VM, `blend-paper` | **running 24/7** ✅ |
| **Four forked paper books** (tight / sized / short-boost / **tstop**) | same process on the VM | **running, all five books live** ✅ |
| Bitget demo order-path test | your PC, pid 7612 | **running, 3 longs open, heartbeat 11s** ✅ |
| Polymarket forward collector | your PC, Startup launcher | running, 2,065 rows ✅ |
| Status page | Azure VM, `status-server` | running ✅ |
| **Market-neutral paper book (5th)** | your PC, `mn_paper.py` | **running, 6L/6S, $220.87** ✅ |
| $10 micro bot | built, `ALLOW_REAL = False` | off, by design |

## The five paper books, and why there are five

One process, five independent books, all on the same live price feed. They exist because
2026-09-22 produced six variants that all "helped the holdout and cost the tune half" —
which is exactly what an exhausted holdout looks like. Rather than pick one on a backtest,
all of them run forward and the market decides.

| book | what is different | forked |
|---|---|---|
| **main** | the validated config, unchanged | original |
| **tight** | long trail drops to 5×ATR once BTC breaks its 4h trend | 2026-09-21 23:30 |
| **sized** | entry size tilted ±90% by a frozen at-entry runner model | 2026-09-22 19:37 |
| **short-boost** | short risk ×5 | 2026-09-22 21:05 |
| **tstop** | tight, PLUS close a long still under +2R after 100 bars | 2026-09-23 |

**The first four are still identical**, and will stay that way until BTC breaks. The tight and
short-boost books only diverge on a **4h close below roughly $81,752** (−5.2% from here),
which historically fires about every 15 days. Don't read "no divergence" as "no effect."

### Re-scored on 2026-09-23 evening: what each book should now be expected to show

Three engine errors were found and fixed: bar labels read as entry times, funding never
charged, and compounding by equity a trade was never sized on (doc 03, #12–14). Re-scored
(`backtest/honest_rescore.py`, `backtest/compounding.py`):

| book | expectation now | why |
|---|---|---|
| **tight** | **the favourite**: beats main on both halves, +2–3%/mo, shallower worst month | its gain survived every correction; part of it is simply paying less funding |
| **short-boost** | **tracks main within ~0.5%/mo** | most of its backtest edge was look-ahead. A flat result is the prediction, not a failure |
| sized | not re-scored | its model and features are causal; funding and compounding would move it like main |
| main | +4.9%/mo haircut (+10.5% raw) on both halves, entry-sized | about half the figures quoted before today |

**The paper books' own equity is overstated.** `blend_paper.py` compounds each close by the
current equity (`st["equity"] *= 1 + R × risk_used`), but it sized the position at entry. A
real account at the same R shows less. The two-line fix (store `risk_usd` at entry, add
`R × risk_usd` at close) is **not applied**: it changes a live process's accounting mid-test,
so it is your call. Compare books by R and trade counts, not by equity, until it is fixed.

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

1. ~~Run the market-neutral book as a fifth paper book.~~ **Done 2026-09-23** —
   `mn_paper.py`, running locally, pre-registered, verdict at 26 rebalances. Read it with
   `python mn_paper.py --status`. **It should be moved to the VM**, for the same reason the
   blend lives there: a book on a machine that gets switched off cannot accumulate a record.
2. **Move the Bitget demo bot to the VM** (~15 min, [doc 06](06-deploy-221.md)). Stop the
   local bot first — one account, one bot, or every order doubles. IP-whitelist the key to
   the VM and drop Withdraw permission while you are in there.
3. ~~Reconcile the 1000h / 200h gate discrepancy.~~ **Done 2026-09-23** —
   `backtest/regime_gate.py`, written up in [doc 01](01-strategy.md). The deployed 1000h gate
   is the better one: it costs 4.2%/month of tune-half return and buys a 21-point drawdown
   reduction on *both* halves. Nothing to change.
4. **Binance testnet keys, created by you**, if you want a real slippage measurement.
   `blend_testnet.py` reads them from the environment only.
5. **Nothing on Polymarket.** 229 resolutions in and the +0.25 edge claim is effectively
   refuted (8/14 inside the band). Do not deposit. [Doc 08](08-polymarket.md).
6. **Decide on the paper-book equity fix** (added 2026-09-23). See the re-score above. Two
   lines in `blend_paper.py`, then a VM patch. Until then, judge books by R, not equity.
7. **Find out whether Bitget's unified account takes spot alts as futures collateral**
   (~15 min of reading, no code). If it does, routing the 12h sleeve's longs to spot saves
   its funding bill: +1.4%/mo on the tune half and ~0 now, in exchange for 8bp more fee
   (`backtest/funding_routes.py`, doc 02). It is a pure cost cut with no prediction in it.
   It does not fit as separate cash (0.64× equity at p99).
8. **When `mn_paper.py` passes its verdict, overlay it on the tight book at k = 0.25–0.5.**
   Don't split capital: `backtest/combine_honest.py` shows the overlay adds ~1.2%/mo at
   unchanged drawdown and lifts weeks-up from 37% to 50%. Margin under the overlay has not
   been simulated; do that first.
9. **Make the engine's defaults honest.** New tests should call `causal_t0.real_t0`,
   `funding_cost.charged` and an entry-sized evaluator (CLAUDE.md rules 10–12). The old files
   stay as they are; their docs now carry the corrected figures next to the originals.

## A second Run-command trap, found the hard way 2026-09-23

Doc 09 already warned that Azure Run command JSON-decodes a script, so **backslashes** get
corrupted. There is a second one, and it broke a patch on the live VM:

> **Long lines get wrapped at roughly 47-56 characters, and a wrapped line's tail runs as a
> command.**

`patch_entry_sized.sh` v1 carried its payload as a single 22KB `echo '<base64>' | base64 -d`
line. That shattered into hundreds of fragments, each reported as `: not found`. A wrapped
comment is worse than a wrapped command, because the tail loses its `#` and executes.

**The rules for any VM patch script, now enforced by the generator:**

1. **Every line under 44 characters** - commands *and* comments.
2. **Payloads go in a heredoc**, never in a command line. `base64 -d` ignores newlines, so
   heredoc data survives being wrapped at any width.
3. **No backslashes** (the original trap).
4. **`set -e` before the hash check**, so a corrupted decode aborts before the `mv` and the
   live file is never touched.
5. **Split a sha256 across short assignments** (`H1..H4`, 19 chars each) rather than one
   82-character line.

Verified by hard-wrapping the finished script and running it: correct at 47, 40 and 30 chars,
and at 26 chars it fails *safely* - `set -e` catches it and `blend_paper.py` is untouched.

One thing that looked like a third trap and was not: the shell's `<command>: not found`
message prints the command *after* quote removal, so single quotes appeared to have been
stripped when they were merely not echoed. Quotes are fine. Line length is the whole problem.

**Check the box before patching it:** `deploy/check_vm.sh` is read-only and reports which
version of `blend_paper.py` is on disk, by sha256, against both known-good hashes.

## What NOT to do

**Stop sweeping the holdout.** ~75 configurations in one day, then dozens more on
2026-09-22, against the same six years and the same single split. Further sweeps are mining,
not research — and doc 02 records four separate cases where a "plateau with an interior
optimum" was a look-ahead bug rather than an edge.

The next real information comes from the paper books running forward, not from this machine.

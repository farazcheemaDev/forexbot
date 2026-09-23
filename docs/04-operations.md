# Running the bots

## The real-money gate

`longtrend_bot.py` line 91:

```python
ALLOW_REAL = False
```

Nothing can place an order with real funds while that is `False`. It is not a
config setting and not an environment variable — a human has to edit the file.
That is deliberate.

Everything currently running is either Bitget **demo** (`SUSDT-FUTURES`) or pure
paper simulation.

## What's running (as of 2026-09-13)

| PID | Process | What it does |
|---|---|---|
| 16728 | `longtrend_bot.py --mode demo` | **Bitget demo, real API orders.** 3 coins, aggressive risk (0.40%/unit × 5 units) by explicit request. |
| — | `longtrend_paper.py` | $20 simulated account, 9 coins, validated 0.13%/unit. **Long + short** since 2026-09-13. Logs an `alive |` heartbeat every closed bar, so silence now means dead rather than quiet. |
| 18504 | `xs_paper.py` | Cross-sectional momentum, 10 books (5 variants × 1× and 3× leverage). |
| 19620 | `crypto_maker.py` | Maker fill-rate probe. |
| 18912 | `crypto_multi.py` | Older multi-coin runner. |
| 18744 | `portfolio_bot.py` | Older portfolio runner. |

Refresh that list any time:

```bash
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | Select-Object ProcessId,CommandLine | Format-Table -AutoSize -Wrap"
```

**Do not trust `wmic | grep` for this** — line wrapping made it miss a running bot
once, and the restart created two bots on one account. See
[doc 03](03-mistakes.md).

## Starting and stopping

Start the demo bot:

```bash
python -u longtrend_bot.py --mode demo
```

Start the $20 paper runner:

```bash
python -u longtrend_paper.py
```

Stop one by PID:

```bash
powershell -NoProfile -Command "Stop-Process -Id 16728"
```

**Before killing anything, confirm what the PID actually is.** A wrong PID
already killed a running pre-registered test once.

State survives restarts — each bot writes its open positions to `logs/*_state.json`
and reloads them. The demo bot also holds a single-instance lock, so a second copy
refuses to start rather than double-trading.

## Is it working? One command

```bash
python health.py
```

**Use this instead of eyeballing the process list.** On 2026-09-12 a duplicate bot was
started against the same demo account because `wmic | grep` wrapped a long command line
so a running bot looked absent, and its between-bar silence was read as death — two weak
signals agreeing produced a confident wrong answer
([doc 03](03-mistakes.md), `longtrend_bot.acquire_lock`).

So `health.py` reports **three independent signals separately**, and when they disagree
that disagreement is the point:

| Signal | What it is | Why not the obvious thing |
|---|---|---|
| **Process** | pid from the bot's own lock file, **cross-checked against the command line** | a pid can be recycled after a crash; a stale lock plus any python process would otherwise read as alive |
| **Heartbeat** | mtime of the file the bot writes **every cycle** (`*_state.json`) | **not the log.** The bots log once per closed *bar* — a 12h sleeve is silent for 12h while working perfectly — but they `save_state()` every poll |
| **Progress** | equity, open positions, trades taken, rows recorded | a healthy bot can legitimately take no trades for days, so this is reported *apart* from the verdict |

| Verdict | Meaning | Do |
|---|---|---|
| `OK` | alive and writing | nothing |
| `WEDGED` | **alive but not writing** — worse than dead: it holds the lock so a restart refuses, and it is not trailing stops on open trades | kill the pid, then start it |
| `DEAD` | gone | start it |
| `PROBABLY OK` | files fresh, process not visible | **trust the files.** Do not start a second copy — this is the exact direction the 2026-09-12 mistake went |
| `TWO COPIES` | two instances of one bot | kill all but one immediately; duplicates double every order |

Other forms:

```bash
python health.py --log demo      # tail one bot's log
python health.py --vm <VM-IP>    # also read the VM's status page (TCP 8080 must be open)
```

## Logs

| File | Contents |
|---|---|
| `logs/longtrend.log` | demo bot events |
| `logs/trades_longtrend.csv` | demo bot closed trades |
| `logs/ltp_state.json`, `logs/trades_ltpaper.csv` | $20 paper account |
| `logs/vsaf_trades.csv`, `logs/vsaf_state.json` | VSA forward test |
| `logs/vsa_fast.txt` | the VSA historical resolution ([doc 05](05-vsa.md)) |

## Checking status remotely

`status_server.py` serves read-only JSON over HTTP:

```bash
python -u status_server.py
```

It is deliberately narrow: GET only (every other verb returns 405), never reads
the environment, and serves a fixed allow-list of files under `logs/`. Set
`STATUS_TOKEN` and pass it as `?t=<token>` before exposing it to the internet.

## Oracle Cloud deployment

Written and ready, not yet run. Files in `deploy/`:

| File | Purpose |
|---|---|
| `setup.sh` | ARM64 setup: sets clock to UTC, creates the venv, installs deps |
| `longtrend-paper.service` | systemd unit for the paper runner |
| `xs-paper.service` | systemd unit for the cross-sectional test |
| `status-server.service` | systemd unit for the status JSON |

All units use `Restart=always`, `ProtectSystem=full`, and
`ReadWritePaths=logs`. MetaTrader5 is excluded from the install — it's
Windows-only and the ARM VM can't use it.

### Steps you have to do by hand

1. Create the Oracle VM (Ampere ARM, Ubuntu).
2. Open port 8080 in **both** places — the VCN security list **and** the
   instance's iptables. Oracle images ship with iptables blocking it, and only
   fixing the security list is the usual reason "the port is open but nothing
   responds".
3. `export STATUS_TOKEN=<something long>` before enabling `status-server`.
4. Run `deploy/setup.sh`, then `systemctl enable --now` each unit you want.

The demo bot is **not** in the deploy set. It places real API orders, and it
should not be started on a second machine while it's running here.

## Risk settings reference

| Setting | Demo bot | Paper runner | Validated backtest |
|---|---|---|---|
| Risk per unit | 0.40% | 0.13% | 0.13% |
| Short sleeve | on (5× ATR) | **on (5× ATR, added 2026-09-13)** | on (5× ATR) |
| Max units | 5 | 5 | 5 |
| Long trail | 20 × ATR | 20 × ATR | 20 × ATR |
| Short trail | 5 × ATR | (long-only) | 5 × ATR |
| Position cap | 8 | 8 | 8 |
| Coins | 3 | 9 | 9 |

The demo bot's 0.40% is roughly **3× the validated setting**, on purpose, to
generate trades and surface bugs fast. Do not read its returns as a forecast —
and note the 3-coin book will behave very differently from the 9-coin backtest.

## Free forex and metals history (2026-09-14)

```bash
python fx_fetch.py --list                  # what depth is available
python fx_fetch.py                         # majors + gold, 1h and 4h
python fx_fetch.py --symbols XAUUSDm --tf 1h 15m --days 2400
```

**The belief that forex intraday history was limited to 30–60 days was wrong.** The MT5
terminal already installed on this machine holds ~60,000 H1 bars per symbol back to
**2014** — 12.2 years — on a free Exness demo account. No API key, nothing purchased.

**What hid it:** `mt5.copy_rates_range()` returns `(-2, 'Terminal: Invalid params')` for
every intraday timeframe at every date range, *including ranges well inside the data it
holds*. D1 works; M1 and H1 do not. That error reads like "no such data."
`copy_rates_from_pos()` works on the same symbol and timeframe — and a single request
above ~50,000 bars fails with the *same* misleading error, so page size matters too.

> **Rule:** page with `copy_rates_from_pos`. Never read `copy_rates_range`'s error as
> proof the data is absent.

**It needs no changes to the backtest suite.** `mass_search.fetch()` is cache-first, so
writing MT5 bars into `{symbol}_{interval}_{days}d.json` makes all 90 backtest files
accept forex without knowing where the bars came from.

| Verified | |
|---|---|
| `XAUUSDm` 1h | 38,845 bars, 2020-02-18 → 2026-09-14 |
| `EURUSDm` 1h | 40,901 bars, same window |
| Server clock | **UTC+0.0** on `Exness-MT5Trial16` — no offset to correct |

Two things that would silently corrupt a crypto comparison, both handled: MT5 stamps
**server time** (this server happens to be UTC; `--utc` converts if you switch brokers),
and forex has no consolidated tape so `volume` is **tick count**, an activity proxy, not
size.

### Do not use `rtest.run_r` for trend following on this data

`run_r` is a fixed stop/target engine. Setting `tp_mult` high to dodge the profit cap
removes the target **without adding a trailing exit**, so a position can run for years and
the only realistic exit left is the stop. The symptom is unmistakable and was seen
immediately on gold: **2.4% win rates on 42 trades in 6.6 years**, with mean R carried
entirely by a couple of enormous winners.

That is not an edge, it is a missing exit. Trend-following tests belong in
`backtest/convex.py`, which has real trails. Use `fee_abs` for forex (spread in price
units — gold ≈0.30, EURUSD ≈0.00010), not `fee_bp`.

## The demo order-path test records real fills now (2026-09-21)

`longtrend_bot.py` exists to verify that real orders fill where the backtest assumes.
It was not recording a real fill on ANY path:

* a TRAIL exit logged `exit = rec["stop"]` - the price we wanted - then sent a market
  order whose actual fill was never read.
* a position closed by the exchange stop logged `exit = ""` and `R = ""`. **4 of the
  first 6 trades carried no result at all.**

`actual_fill()` now recovers the price from three sources, best first: the order
response (`average`/`price`), then `fetch_order` by id, then `fetch_my_trades`. Every
one is wrapped - a recording improvement must never break the trading loop - and a
total failure falls back to the assumed price and labels itself `assumed`.

**The trade CSV schema changed**, so the old 6 rows were rotated to
`logs/trades_longtrend_v1_noslip.csv`. New columns:

```
ts, symbol, entry, exit, exit_intended, exit_src, R, slip_bp, reason, bars
```

`exit` is now the real fill, `exit_intended` the price asked for, `slip_bp` the
difference signed so negative is worse for us, and `exit_src` says which of the three
sources produced it. **Read `exit_src`: a column full of `assumed` means the venue is
not returning fills and the test is still measuring nothing.**

### What this test can and cannot tell you

**Bitget's demo lists only 3 contracts - SBTC, SETH, SXRP.** It cannot be widened to
the 12-coin book; the bot's own startup banner says so. So it verifies the ORDER PATH
(orders place, stops fire, fills get recorded) on the two most liquid coins on earth.
It does **not** measure slippage on ENA, WLD, SUI or ARB, which is what going live at
$200 would actually depend on. At 0.86 trades/day it also needs ~6 weeks for 30 fills.

For slippage on the real book the options are a venue whose testnet lists the actual
symbols (Binance futures testnet does), or a small real account. Neither is built.

## Order-path test on Binance futures testnet (2026-09-21) — `blend_testnet.py`

`longtrend_bot.py` can only reach 3 contracts (Bitget demo lists SBTC/SETH/SXRP), so it
measures fills on the most liquid coins on earth rather than on ENA, WLD, SUI or ARB.
**Binance's futures testnet lists all 12 of the book** - verified 2026-09-21: 605 trading
symbols, every book coin present, $5 minimum notional, SHIB as `1000SHIBUSDT`. So the real
configuration can be run against a real matching engine.

```
set BINANCE_TESTNET_KEY=...      from testnet.binancefuture.com (fake money)
set BINANCE_TESTNET_SECRET=...
python -u blend_testnet.py --dry-run    # loop only, places nothing, needs no keys
python -u blend_testnet.py              # places orders on TESTNET
python -u blend_testnet.py --status      # includes the slippage summary
```

### The problem blend_paper.py never had to solve

The strategy holds logical positions keyed by coin AND sleeve - `DOTUSDT:1h` and
`DOTUSDT:4h` are open simultaneously right now, and the same for LINK and NEAR. **An
exchange holds ONE NET POSITION PER SYMBOL.** There is no way to give a venue two separate
long positions in DOT.

So this bot keeps the logical book internally and sends only the **net delta per symbol**.
Confirmed working in the dry run: AVAX:4h and AVAX:12h both opened and produced a single
1.276239-contract order; NEAR:1h and NEAR:4h produced a single 3.72-contract order.

**blend_paper has therefore been simulating something not directly executable**, which is
worth knowing before real money is involved.

### No exchange stop, deliberately

Netting makes per-sleeve stops incoherent - three sleeves with three stops cannot be one
stop on the net. Stops are managed in-process only, so **a dead bot leaves positions
unprotected.** Fine on fake money; it is the reason this design cannot be lifted to a live
account unchanged. A live version needs one sleeve per coin, or a disaster stop on the net
at the worst sleeve's level.

### What the first dry run already proved

Seven signals taken, **three rejected for size**:

```
[ENAUSDT:4h]  SKIPPED - unit $4.89 below the $5.00 Binance minimum
[NEARUSDT:12h] SKIPPED - unit $4.78 below the $5.00 Binance minimum
[ARBUSDT:12h] SKIPPED - unit $3.92 below the $5.00 Binance minimum
```

**At $221 equity and 0.30% risk, unit sizes land at $3.92-$11.49, and Binance's $5 floor
rejects roughly 30% of signals.** That is the venue floor measured against a real matching
engine instead of read off a table, and it confirms doc 00: MEXC's sub-dollar minimums are
the only reason $221 works at all. Binance, Bitget and Bybit all need roughly 2-3x the
capital to run this book intact.

### Safety

Keys from the environment ONLY - never a file, never an argument, never logged. Sandbox
mode is forced and then **asserted against the resolved URL**; the bot refuses to start if
the endpoint is not testnet, so there is no flag that points it at live Binance. A pid lock
prevents a second instance. Reconciliation runs both ways every cycle and an orphan
position is reported, never adopted.

## The TIGHT book beside the paper blend (2026-09-22) — `blend_paper.py`

`blend_paper.py` now runs two books in one process on the same prices. The **main** book is
the deployed rules, unchanged. It was verified identical to the old code on the same state.
The **tight** book forks from it on the first cycle, with the same equity and the same open
positions, and differs by one rule: when BTC's 4h close breaks its own trail (highest close
since the last break minus 5 x ATR), its open longs switch from the 20xATR trail to 5xATR
for good. The evidence is in `backtest/btc_exit.py` and doc 02 ("PROMISING: tighten the
alts' trails").

| file | what |
|---|---|
| `logs/blend_state.json`, `logs/trades_blend.csv` | main book, as before |
| `logs/blend_state_tight.json`, `logs/trades_blend_tight.csv` | tight book (trades carry a `tightened` column) |

`python blend_paper.py --status` prints both books, the equity difference, and which tight
positions are on the tightened trail. **The books stay identical until BTC breaks its 4h
trend**; breaks come roughly every two weeks (the last three were 08-03, 08-14 and 09-10).
An error anywhere in the tight path is logged and skipped, and the main book is saved
before the tight path runs.

**Deploying:** the VM cannot `git pull`, so `deploy/patch_tight_book.sh` carries the file
gzipped and base64-encoded, with no backslashes (see doc 09). It checks the sha256, backs
up the old file to `logs/blend_paper.py.bak-<stamp>`, restarts `blend-paper`, and prints
the status. To roll back:

    cp /opt/forexbot/logs/blend_paper.py.bak-<stamp> /opt/forexbot/blend_paper.py && systemctl restart blend-paper

## The SIZED book, third beside main and tight (2026-09-22) — `blend_paper.py`

A third book runs in the same process. It takes the same signals and exits as the **main**
book, but scales each new long's risk by a frozen runner-probability model
(`backtest/runner_leverage.py`, position-only logistic, holdout AUC 0.591), mean factor ~1,
so it carries no more total risk than main — it moves risk from low-runner-odds signals to
high ones. Shorts are unsized. The model is frozen to plain-numpy constants in the file, so
the VM needs no sklearn.

| file | book |
|---|---|
| `logs/blend_state.json`, `logs/trades_blend.csv` | main (deployed) |
| `logs/blend_state_tight.json`, `logs/trades_blend_tight.csv` | tight (BTC-break trail) |
| `logs/blend_state_sized.json`, `logs/trades_blend_sized.csv` | sized (runner-probability risk; trades carry `size_fac`) |

`python blend_paper.py --status` prints all three. The sized book forks from main on the
first cycle (existing positions at ×1.0) and diverges as new longs open at factors between
0.10× and 1.90×. **Watch two things:** whether it out-earns main at similar drawdown, and
how often a factor < 1 drops a long below the MEXC minimum (that rejection is the $221
interaction we want to measure). Each extra book saves the main book first and isolates its
own errors, so neither tight nor sized can cost the main book a cycle.

**Deploy:** `deploy/patch_sized_book.sh` (gzip+base64, sha256-checked, no backslashes — doc
09), same pattern as the tight book. Rollback: restore `logs/blend_paper.py.bak-<stamp>`
and restart `blend-paper`.

## The SHORT-BOOST book, fourth beside main/tight/sized (2026-09-23) — `blend_paper.py`

One process, four books, one set of klines. The fourth scales a SHORT's risk **x5** when
BTC's 4h trail is broken at its entry (`SBOOST_MULT`). Evidence: shorts entered during a
break earned **+0.481R against +0.043R** for all other shorts across 84 break episodes
(`backtest/vol_target.py`). x5 is the safe end of the executable x5-x8 band — above x8 the
book's **maximum** gross leverage breaks 10x.

| file | book |
|---|---|
| `logs/blend_state.json` / `trades_blend.csv` | main (deployed) |
| `logs/blend_state_tight.json` / `trades_blend_tight.csv` | tight (BTC-break trail on longs) |
| `logs/blend_state_sized.json` / `trades_blend_sized.csv` | sized (runner-probability risk, `size_fac`) |
| `logs/blend_state_sboost.json` / `trades_blend_sboost.csv` | short-boost (`boosted` flag per short) |

**Read the `boosted` flag, not the equity gap.** Only ~2% of shorts are entered during a
break, so the equity lines separate slowly; the trades file lets you compare boosted vs
un-boosted mean R directly. `--status` prints that comparison as soon as a boosted short
closes.

**Deploy:** `deploy/patch_sboost_book.sh` (gzip+base64, sha256-checked, no backslashes).
Rollback: restore `logs/blend_paper.py.bak-<stamp>` and restart `blend-paper`.

## The entry-sized equity fix (2026-09-23)

*Mistake #14 in [doc 03](03-mistakes.md). Source: `backtest/compounding.py`,
`deploy/patch_entry_sized.sh`.*

`blend_paper.py` sized a position's dollar risk at OPEN (`risk_usd = equity * risk% / 100`)
but credited its result as a FRACTION of equity at CLOSE. So a trade's dollars grew with
profits other trades banked while it was open - something the bot cannot do, because it never
resizes an open position. In a worked case (open at $221, close at $400, +10R) the old line
paid **1.81x** what a real account would earn.

**Fixed:** `risk_usd` is stored on the position at open and the close does
`equity += R * risk_usd`. Verified exact for single units and for 5-unit pyramids, because
every pyramid add reuses `rec["notional"]` so `R` already aggregates the units.

All four books share the `cycle()` that holds this, so one fix covers main, tight, sized and
short-boost. `mn_paper.py` got the same convention (`base_eq`, set at each rebalance).
`longtrend_bot.py` needed nothing - its equity is the real exchange balance.

### To apply it on the VM

```bash
cat deploy/patch_entry_sized.sh
```

Paste the contents into Azure portal > VM > Run command > RunShellScript. It backs up
`blend_paper.py` **and all four state files**, verifies sha256
`15c8d624027e7018383edb3eb6b7ff32be5e813773d5c95c0e22728a4a32a363`, syntax-checks, writes a
marker line into `blend_paper.log`, restarts and prints `--status`.

### Rebuilding the pre-fix equity, correctly

`rebuild_equity.py` replays a book's whole history under the entry-sized convention from its
trade log. It works because **R is invariant to the accounting** - the log records R and the
`risk_pct` each trade was sized at, so the curve can be recomputed under either convention.

```bash
python rebuild_equity.py                    # every book it finds
python rebuild_equity.py --csv corrected.csv
```

On the VM, `deploy/rebuild_equity.sh` installs and runs it. **It is read-only with respect to
the books** - no state written, no equity touched, nothing restarted - so it is safe before or
after `patch_entry_sized.sh`.

**It checks itself before printing anything.** It first replays the OLD convention and
confirms that reproduces the log's own `equity` column per timestamp. If that fails it says so
and the corrected numbers must not be trusted.

Validated on a 1,500-trade synthetic log built from the backtest engine, where the answer was
known independently: the bug had turned **$10,022 into $315,437** over 2.3 years - a 31x
overstatement, because the error compounds rather than being a fixed multiple.

Two things that validation exposed, both worth knowing:

- **`sort_values` defaults to quicksort, which is NOT stable.** The trade log is append-only
  and its `equity` column is only meaningful in written order; a non-stable sort reordered
  simultaneous closes and misaligned the column against its own rows, reading as a $4,534
  self-check failure on a log that was correct. 217 of 1,500 closes shared a timestamp.
  `kind="stable"` is load-bearing there.
- **The corrected curve is order-sensitive in a way the old one is not.** The old convention
  multiplies, so its final value is independent of how simultaneous closes are ordered. The
  entry-sized one is not, because an open reads the equity standing at that instant: ~0.15% of
  total return on the test log. Same slot-order noise the backtests average over 5 seeds.

One approximation: equity at OPEN needs the entry time, and the log records only the close, so
entry is recovered as `ts - bars x sleeve_hours`. `--show-ambiguity` counts the opens that land
within an hour of a close, where that estimate could put an open on the wrong side of a banked
profit.

### What the patch itself does NOT do

- **It does not rewrite past equity.** Equity recorded before the marker line was credited
  the old way and is overstated. The book was below its $221 start when the fix landed, so
  the accumulated error is small, but it is not zero.
- **It does not touch R.** `logs/trades_blend*.csv` records R and `risk_pct` per trade, so the
  record stays comparable across the fix - and `rebuild_equity.py` above turns that into a
  corrected curve whenever it is wanted.
- **Positions already open** carry no `risk_usd` and fall back to the old behaviour for their
  one closing trade, logging `pre-fix position, no risk_usd`. Expect a few of those lines
  once, then none.

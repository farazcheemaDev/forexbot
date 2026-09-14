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

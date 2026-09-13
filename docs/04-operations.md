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

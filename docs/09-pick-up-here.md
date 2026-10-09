# Pick up here

*Rewritten 2026-10-08 ~19:00 UTC; top sections added 2026-10-09. State verified the same hour: `systemctl list-units` on the VM over `ssh forexbot-vm`
(read-only), and `python health.py` on the PC.*

**If you are a new Claude session, read [`CLAUDE.md`](../CLAUDE.md) first** (rules, traps, safety gates), then this file
(what is running, what is next), then the last entries of [doc 02](02-what-failed.md) and [doc 21](21-graveyard-audit.md)
before proposing anything - most ideas have been tested, and doc 21 says how well.

## 2026-10-09 (night): DOGE scalping, live with TradingView - dead at retail fees (nothing left running)

The user asked to stop backtesting for years and instead read DOGE today, predict, and forward-test live. Done, and it
does not work at retail costs - full write-up in doc 02's last entry, numbers in CLAUDE.md s10:
- "pick what worked in the last hours/days, trade it next": loses the fee at every look-back (`backtest/doge_adapt.py`);
- 1-2% targets: the chart entries win exactly as often as random ones (`backtest/doge_bigtarget.py`);
- the order book predicts the next 10-60 s (real, IC +0.1..+0.25) but only ~1-2bp of movement (`backtest/doge_book.py`);
- live: 7 trades, -1.41% net (`doge_live.py`, `logs/doge_live/`).
**Nothing from this session is still running** (stopped 2026-10-09 21:09 UTC at the user's call).

**How to use what was built:**
- **TradingView from Claude Code:** the bridge is in `D:/TRADING/tradingview-mcp`; `.mcp.json` here (gitignored, this PC
  only) loads it as MCP tools in a session started in `D:/forexbot`. TradingView Desktop must run with the debug port:
  start `%LOCALAPPDATA%/tradingview-mcp/TradingView.Desktop_*/TradingView.exe --remote-debugging-port=9222` (the Store
  path fails with EPERM). Without MCP tools, the CLI works: `node D:/TRADING/tradingview-mcp/src/cli/index.js status`
  (also `quote`, `ohlcv -n 100`, `screenshot -r chart`, `draw shape -t horizontal_line -p PRICE`, `range --from --to`).
- **Bitget 1m history:** `python -m backtest.bitget_1m DOGE BTC --days 90` (cache in `strategy_analysis/data/bitget_1m/`).
- **Log a trade idea and have it scored honestly:** `python doge_live.py --call long 0.0842 0.0852 0.0838 120 "why"`
  (entry `mkt` = now), then `python doge_live.py --status`. 30 calls tell whether the caller beats break-even.
- **A new live rule test:** `logs/doge_live/registered.json` is FROZEN; move that folder aside to register new rules
  (`--register "5m|level_bounce|both|2|1" ...`, names from `backtest/doge_adapt.py`), then `--loop`.
- **Order book / liquidations:** `python book_rec.py` and `python liq_rec.py` (public data; Binance WEBSOCKETS do not work
  on this PC, REST does; OKX needs a browser User-Agent), then `python -m backtest.doge_book`.

## 2026-10-09 (late): THE FINAL MACHINE runs on paper on the VM

`combo_bot.py --final` (+ `final_books.py`) = machine v2 + the MN book ranked half momentum / half RSI + funding carry 0.5x
+ the daily Bollinger book (20-day exit) 0.5x + capit2 0.5x, the whole account held under 10x (trend guard 6.25x).
**On the VM as `combo-bot-final.service`, `--mode dry`: $300 virtual, all coins, no orders, no keys**, beside the demo.
Backtest of exactly this (`backtest/final_machine.py`, DEPLOYABLE): typical year $3,400 / $4,735 on $300, worst month
-30% - BACKTEST ONLY. Read it: `./.venv/bin/python combo_bot.py --mode dry --final --status` on the VM. Trades in
`logs/combo_bot_dry_final/combo_final_trades.csv`, orders in `combo_exec.csv`, the log in `combo_paper.log`.
Next decision (the user's): after the demo's PASS (~2026-10-13), whether the demo account should run `--final` instead.

## 2026-10-09: the archive-hole bug - fixed, and EVERYTHING re-run

A loader rule cut 51 coins (XRP, SOL, LTC...) at a 2022 data-archive hole; 16.4% of PIT top-40 coin-months were missing.
Fixed (`capitulation_wide.halt_cut`) and all 34 affected scripts re-run - their logs are current. The headline changes
and every new result are in doc 02's last entry, "The archive-hole bug, the re-run, and the last combinations". In short:
capit2's rule still passes (and nothing improves it); the plain capitulation book is weaker; machine "E" is BETTER than
the 2026-10-08 correction said (worst month -21% at the published v2's typical year); two daily-book exits and a
momentum + RSI market-neutral book are new paper candidates. `backtest/tv_indicators.py` was found to have overwritten an
older indicator library - restored.

**Last session note (2026-10-09, end of day):** the full "final machine" (everything that passed, together) is measured in
`backtest/final_machine.py` / `logs/final_machine.txt` - backtest only. Stopped partway by the user: `trend_factorial.py`
(37 of 216 settings, none beat the deployed config) and part B of `family_machine.py` (families x filters, no pass so
far). Paper candidates not yet built: the daily book's 20-day exit, the MN book ranked half momentum / half RSI, funding
carry (7-day, 20% basket, +50% exit) at 0.5x.

## What is running

| what | where | status |
|---|---|---|
| **blend-paper** - the seven trend paper books (main / tight / sized / sboost / tstop / units / triple) | Azure VM | running. Compare books with `rebuild_equity.py`, never `--status` equity (CLAUDE.md s7b) |
| **combo-paper** - "machine v2" on paper: triple trend + MN 1x + bear sleeve, pre-registered | Azure VM | running since 2026-09-24; day 14 -20.6% (5th percentile of its backtest). **Its MN book has NO short-leg exit** (pre-registered, unchanged) - see the risk below. Verdict ~2027-03-24 |
| **combo-bot-demo** - v2 executed on the Bitget DEMO (order-path test, P&L meaningless) | Azure VM | running. **Restarted 2026-10-08 18:37 UTC with the MN short-leg exit** (commit cb6bcbf). Two-week PASS check due ~2026-10-13: `./.venv/bin/python combo_bot.py --mode demo --report` on the VM |
| **wick-paper** - crash-bid paper book (Bitget + Binance) | Azure VM | running; verdict at 60+ Bitget fills |
| **combo-bot-final** - THE FINAL MACHINE on paper: `combo_bot.py --mode dry --final` ($300 virtual, all coins, no orders) | Azure VM | **started 2026-10-09** (`deploy/combo-bot-final.service`). `--status` as above |
| status-server | Azure VM | running |
| **pair-paper** - `pair_live.py --loop`: the pair (daily + capitulation, 10,000 PKR) AND the **capit2 shadow book** (improved capitulation, own 5,000 PKR, pre-registered H1-H3 in the file's docstring) | Azure VM | **running hourly since 2026-10-08** (`deploy/pair-paper.service`); state moved from the PC (PC copy renamed `.moved-to-vm`). `./.venv/bin/python pair_live.py --status` on the VM. First capitulation event recorded 2026-10-08 (7 coins, entered ~3h late on the PC before the move) |
| meme / Polymarket collectors | PC | append to `logs/meme_graduates.csv`, `logs/poly_snapshots.csv` |
| `mn_paper.py` (old 5th book) | PC | **dead 8.9 days** (stale lock) and carries the funding bug (s7b). Superseded; not worth restarting |

`health.py` on the PC still says "COMBO BOT on the Bitget DEMO: not running. Start it" - **ignore that line**: the demo bot
moved to the VM on 2026-09-29 and must not also run on the PC (one account, one bot).

## The names (the user asks by these)

| name | what | status |
|---|---|---|
| **machine v2** | triple trend (12 hand-picked coins) + market-neutral 1x + bear sleeve + capped crash bids (`backtest/machine.py`, doc 17) | running (paper + demo) |
| **machine v3** | daily Bollinger book + 4h capitulation book (PIT top-40) + capped MN x0.5 + bear sleeve (`backtest/pair_full.py`) | backtest only |
| **MIX B** | v3 + v2's trend at x0.5 + crash bids (`backtest/machine_mix.py`) | backtest only |
| **"E"** | v2 with the MN short-leg exit + daily book + IMPROVED capitulation (`backtest/machine_combos.py`) | backtest only; corrected data: beats "v2 safe, smaller" +45% / +59% (6y / 2y) at the same worst month; -21% worst month at the published v2's typical year |

## What the 2026-10-08 work found (read the docs for numbers)

1. **A real risk, fixed in the demo bot:** the market-neutral book was only ever measured on ONE rebalance weekday. On one of
   the seven, the 2025-09-12 squeeze (MYX) costs the uncapped book 99% of the account. The bot's 30% disaster stop does not
   help (the netting re-opens). Fix: `combo_bot.mn_squeeze_exits` - a short 50% above its opening price is dropped until the
   next rebalance. Tests: `python tests/test_combo_bot.py` (23). Backtest: `backtest/mn_combos.py`, `logs/mn_rebalance_days.txt`.
2. **The capitulation book, improved:** only coins down >= 10% in 24h, bought with a limit 2% under the signal close
   (`backtest/capit_combos.py`, `capit_stack.py`, `capit_volume.py`). Not yet in any live or paper code.
3. **Corrections:** "v2.1 cuts the worst month to -21%" sat on the lucky MN weekday (honestly ~1 point); regime weights'
   +45% was a look-ahead (the trend book is booked at its close). Both corrected in doc 02 and CLAUDE.md s10.
4. **The graveyard audit ([doc 21](21-graveyard-audit.md)):** every kill rated; every thin one re-tested; nothing came back as
   a book. Only `meme_days.py` was still fetching when this was written - its result goes into doc 21 section G.

## What is next (each needs the user's go-ahead)

1. **Step 2 is DONE (2026-10-08):** capit2 runs on the VM. Judge it at 30 closed capit2 trades or 12 months (H1: > +1% a
   trade; H2: 50-80% of limits filled; H3: beats the plain book on shared signals). ~2-3 signals a month - be patient.
2. Decide later, from paper records, whether "E" (daily book + improved capitulation added to v2) goes into `combo_bot.py`.
   It needs ~$300+ of capital to clear Bitget's $5 minimum per order.
3. `combo_paper.py` keeps the MN risk by design (pre-registered). If the user wants the paper record protected too, that is
   a new paper book, not an edit.

## Reproducing the 2026-10-08 backtests on a fresh clone

- Market data and caches are gitignored (`strategy_analysis/data/`, `logs/daily_combos_cache/`, `logs/pair_lab_cache/`):
  every script rebuilds its own on first run. The first `daily_combos` / `capit_combos` run builds ~1.3 GB of panels.
- The trend book series behind every machine script (`strategy_analysis/data/worst_month_trend.pkl`) is built by
  `python -m backtest.machine`.
- Three large trade dumps are not committed (`logs/rsi_factors_trades.csv`, `logs/rsi_only_trades.csv`,
  `logs/tv_indicators_trades.csv.gz`); their scripts rewrite them.
- Every new script starts with a self-check that reproduces the file it extends (asserted), and its docstring holds the
  registered prediction and the RESULT.

## Traps that cost time on 2026-10-08 (also in CLAUDE.md s3)

- **A weekly book must be checked on all 7 weekdays** - the MN book, funding carry and the BTC/alts dispersion trade all
  changed verdict with the anchor day.
- **The trend book (`dd_fixes.sim`) books P&L when units CLOSE** - never weight its daily series by a label read on the
  same day; size at entry (`regime_weights.py`).
- **Bash heredocs mangle backslash escapes in Python** (twice today) - write code with the Edit/Write tool.

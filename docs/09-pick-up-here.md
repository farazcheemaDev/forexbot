# Pick up here

*Rewritten 2026-10-08 ~19:00 UTC. State verified the same hour: `systemctl list-units` on the VM over `ssh forexbot-vm`
(read-only), and `python health.py` on the PC.*

**If you are a new Claude session, read [`CLAUDE.md`](../CLAUDE.md) first** (rules, traps, safety gates), then this file
(what is running, what is next), then the last entries of [doc 02](02-what-failed.md) and [doc 21](21-graveyard-audit.md)
before proposing anything - most ideas have been tested, and doc 21 says how well.

## 2026-10-09: the archive-hole bug - fixed, and EVERYTHING re-run

A loader rule cut 51 coins (XRP, SOL, LTC...) at a 2022 data-archive hole; 16.4% of PIT top-40 coin-months were missing.
Fixed (`capitulation_wide.halt_cut`) and all 34 affected scripts re-run - their logs are current. The headline changes
and every new result are in doc 02's last entry, "The archive-hole bug, the re-run, and the last combinations". In short:
capit2's rule still passes (and nothing improves it); the plain capitulation book is weaker; machine "E" is BETTER than
the 2026-10-08 correction said (worst month -21% at the published v2's typical year); two daily-book exits and a
momentum + RSI market-neutral book are new paper candidates. `backtest/tv_indicators.py` was found to have overwritten an
older indicator library - restored.

## What is running

| what | where | status |
|---|---|---|
| **blend-paper** - the seven trend paper books (main / tight / sized / sboost / tstop / units / triple) | Azure VM | running. Compare books with `rebuild_equity.py`, never `--status` equity (CLAUDE.md s7b) |
| **combo-paper** - "machine v2" on paper: triple trend + MN 1x + bear sleeve, pre-registered | Azure VM | running since 2026-09-24; day 14 -20.6% (5th percentile of its backtest). **Its MN book has NO short-leg exit** (pre-registered, unchanged) - see the risk below. Verdict ~2027-03-24 |
| **combo-bot-demo** - v2 executed on the Bitget DEMO (order-path test, P&L meaningless) | Azure VM | running. **Restarted 2026-10-08 18:37 UTC with the MN short-leg exit** (commit cb6bcbf). Two-week PASS check due ~2026-10-13: `./.venv/bin/python combo_bot.py --mode demo --report` on the VM |
| **wick-paper** - crash-bid paper book (Bitget + Binance) | Azure VM | running; verdict at 60+ Bitget fills |
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

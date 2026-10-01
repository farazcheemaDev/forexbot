# Tasks for a LOCAL session on the PC (MT5 open) — written 2026-10-01

*For a Claude session running on the user's PC in `D:\forexbot`, where the Exness MT5 terminal and
`strategy_analysis/statement_trades.csv` are. The cloud session that wrote this cannot reach MT5 or the
exchanges. Read `CLAUDE.md` first (the rules), then `strategy_analysis/his_strategy.md` §34–§35.*

## The question

**Was the trader's January–March clock one hour off?** Every analysis of him converts the broker statement
with one offset, `GMT = 5.0`, for all nine months. Split at the European clock change (2026-03-29), his record
looks like two different traders (`logs/his_vs_market.csv`):

| | before 29 Mar (19 trades) | after 29 Mar (27 trades) |
|---|---|---|
| real market moved his way | 37%, −1.3 pts | 96%, +10.2 pts |
| \|his points − market move\|, median | 11.0 | 3.2 |
| his broker's basis across days | erratic, −192 … +351 | smooth futures roll-down |
| trades before the New York open | 10 of 19 | 1 of 27 |

§25 read the left column as "his broker's January–March prices are not the market's". A one-hour winter clock
error gives the same picture. If it is the clock, 19 more trades become usable (25 → ~44) for the tests that
decide whether he can be copied, and his January–March charts — never cross-checked at their real hour — can
be read for the first time.

## Before you start

1. `git pull` in `D:\forexbot`.
2. The Exness MT5 terminal is open and logged in; Python has `MetaTrader5`, `pandas`, `numpy`, `matplotlib`.
3. `strategy_analysis/statement_trades.csv` exists. **It carries a real name and account number. It is
   gitignored. Never commit it, never paste its rows into a doc, a log or a chat.**
4. Offline tests first, so a broken checkout is caught before MT5 is touched:
   ```
   python tests/test_his_clock_check.py
   python tests/test_his_look.py
   ```
   Both must print `3 passed`.

## Step 1 — the clock check (the deciding step)

```
python -m backtest.his_clock_check
```

**The prediction is already registered** (in the script's docstring and §35, 2026-10-01, before any run):
- after 29 Mar: best offset **UTC+5**. This is the CONTROL. If it says FAIL, stop: the method is broken.
  Debug before anything else.
- before 08 Mar: best offset **UTC+4**, median |pts − mv| ≤ 5, market his way in ≥ 80% of trades (against
  11.0 and 37% at UTC+5).
- 08–29 Mar is 1–2 trades: a hint only.

**Decide:**

| result | meaning | next |
|---|---|---|
| winter best = 4.0, error ≤ 5, ≥ 80% his way | **CONFIRMED** | steps 2–4 |
| winter best = 5.0 | not the clock: §25 stands | write it up (step 5), stop |
| winter best = 3.5 / 4.5 / 6 or the gap is unclear | partial | write it up, report to the user before going on |
| control FAIL | the method is broken | find the bug first |

It also writes `logs/his_clock_check.csv` (per trade and offset). Look at the winter trades one by one at the
best offset: if one or two still have a large error, name them rather than averaging them away.

## Step 2 — add January–March to the tick cache (only if confirmed)

The cache (`strategy_analysis/data/ustec_tick_days.pkl`) starts on 2026-04-01. This adds only the missing days:

```
python -m backtest.his_tick_cache --from 2026-01-02 --to 2026-03-31
```

It reports days with no ticks (holidays, or before MT5's history begins). If January is missing, say so — the
oldest trades cannot be drawn without it.

## Step 3 — the charts, cross-checked at the corrected hour (only if confirmed)

**Register a prediction in §35 BEFORE looking** — e.g. "the winter charts show the same ordinary setups as
summer (pullbacks, level bounces, 2–4 look-alikes per chart); nothing new". Then:

```
python -m backtest.his_look --winter-gmt 4 --since 2026-01-01 --out logs/his_look_all
```

Read every January–March chart by eye, the way §34 read the summer ones: the setup (pullback, level bounce,
breakout), the look-alikes he did not take, and anything on the chart that recurs at his clicks and not at the
look-alikes. Then test any impression against the same-sitting moments, as §34 did with
`his_keylevels.py`, before believing it — §34's eye impression ("he trades off levels") failed that test.

## Step 4 — re-run the deciding tests on ~44 trades (only if confirmed)

These scripts each use one `GMT = 5.0` and keep only `>= "2026-04-01"`:
`his_copy_delay.py` (can he be copied?), `his_local.py` (the 87% race), `his_extremes.py` (is the record
real-time?), and also `his_keylevels.py`, `his_model.py`, `his_1m.py`, `his_ta.py`.

For each one you re-run:
1. add `--winter-gmt` and `--since` the way `his_look.py` did, converting with
   `backtest.his_clock_check.to_utc(t, winter, 5.0)`, **with defaults that reproduce the old output exactly**
   (check that first: run with defaults and compare against its log in `logs/`);
2. run with `--winter-gmt 4 --since 2026-01-01`;
3. report old (25 trades) and new (~44) side by side, and the winter trades on their own. Do not tune
   anything on these trades — they are a check, not a training set.

**`his_copy_delay.py` first.** It is the one that decides whether a copier is worth building
(§34: a 5–10 s copy kept the edge on 25 trades; that is too few to plan on).

## Step 5 — record and push

- Append the result to `strategy_analysis/his_strategy.md` §35: confirmed or refuted, against the registered
  prediction, every number with the file that produced it (CLAUDE.md rule 7).
- Add a dated entry to `CLAUDE.md` §10.
- Commit the new logs and charts (`logs/his_clock_check.csv`, `logs/his_look_all/*.png`, the re-run logs) and
  the code. **Before committing, check that nothing contains the statement's name or account number.**
- Push the branch, then fast-forward `main` (the user has asked for this; the VM deploys from `main`).

## While you are on the PC (optional, unrelated to the clock)

1. **Check the bot's new Bitget minimum-order rules against Bitget's real market list.** The cloud session
   could not reach Bitget. The dry-run bot (`combo_bot.py --mode dry`, was pid 5648) still runs OLD code:
   stop it, start it again on the new code, and check its log (`logs/combo_bot_dry/combo_paper.log`) for
   `BELOW VENUE MINIMUM` lines and for LINK / DOT / LTC orders rounded to whole steps. Never run it in
   `--mode demo` or `--mode live`: the demo bot now runs on the VM, and one account is one bot.
2. **Restart `mn_paper.py`** (was pid 8996) so it picks up the held-coin fix (CLAUDE.md §7b).

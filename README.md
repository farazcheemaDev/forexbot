# forexbot

A trading research lab and a set of paper-trading bots. It began as an MT5 forex bot; most of the work, and everything
now running, is on **crypto perpetuals** (Bitget and Binance data), with forex, gold and NASDAQ tested and mostly killed.
Built to be inspectable, not a black box: most of the repo is the record of what was tested and why it died.

**No real money is in anything, and nothing here is advice or a forecast.** A backtest is what a rule did on history;
the evidence is the forward paper record, and real money is gated by a decision rule written before that record existed.

## Where it stands

**[`docs/STATUS.md`](docs/STATUS.md) is the one page for the current state**: what is running where, on which code,
the paper result next to its backtest and drawdown, the real-money gate, and the dates that matter. It carries the date it
was last verified and a one-command re-check (`bash deploy/verify_status.sh`).

Then: [`CLAUDE.md`](CLAUDE.md) (the goal, the validation rules, the traps that have produced wrong answers, the hard
safety gates, and a dated session log), [`docs/22-decision-rule.md`](docs/22-decision-rule.md) (when real money may go
in), and [`docs/README.md`](docs/README.md) (the full index of the research notes).

## Principles

- **Paper and demo until proven.** `ALLOW_REAL = False` in every bot that could place a real order; only a human edits it.
- **No credentials in the repo.** Exchange keys come from the environment only; MT5 attaches to an already-logged-in terminal.
- **Honest backtests.** Fees on every trade (12bp round-trip), a held-out last 40% never tuned on, point-in-time
  universes that include dead coins, funding charged, hindsight shrunk, and a prediction recorded before each test.
- **Kills are permanent** unless the measurement itself was broken (`docs/02-what-failed.md`, `docs/21-graveyard-audit.md`).

## Layout

```
CLAUDE.md            orientation: goal, validation rules, traps, safety gates, dated log
docs/                STATUS.md (current state), README.md (index), research notes 00-26
backtest/            every experiment; blend.py holds the deployed constants
news/                news / sentiment / positioning engine and the crowd-squeeze paper book
combo_bot.py         the combination bot (dry / Bitget-demo; live is gated), with final_books.py, wick_live.py
blend_paper.py       the seven trend paper books;  combo_paper.py  machine v2;  wick_paper.py  crash bids
pair_live.py         the daily + capitulation pair and the capit2 shadow book
dashboard/           the live dashboard (web app);  dashboard_push.py  feeds it from the VM
bot/                 the original MT5 layer: broker, risk manager, execution, strategies
deploy/              systemd units, deploy scripts, verify_status.sh
tests/               offline tests on fake exchanges (run each as a script: python tests/test_combo_bot.py)
logs/                state, trade records, and the saved output of every experiment
strategy_analysis/   validation protocol (the authority on testing), the trader study, cached data (gitignored)
```

## Checking on it

```bash
bash deploy/verify_status.sh     # read-only: VM services, code identity, live equity vs the day-45 line
python health.py                 # PC-side: is anything wedged or dead
```

## MT5 smoke test (the original forex layer, optional)

1. Install MetaTrader 5, log into a **demo** account, enable Algo Trading.
2. `pip install -r requirements.txt`
3. Copy `config/config.example.yaml` to `config/config.yaml` and fill in the login/server.
4. `python check_connection.py` prints account info and candles.

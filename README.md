# Forex Bot (MT5, demo-first)

Automated trading bot on MetaTrader 5 via the official Python API. Demo-first,
with honest backtesting and hard risk limits. Built to be inspectable, not a
black box.

## Guiding principles
- **Demo until proven.** No real money until backtest + live-demo show a real edge.
- **No password in the repo.** The bot attaches to an already-logged-in MT5
  terminal; your trading password stays in MT5.
- **Honest backtests.** Realistic spread/slippage, out-of-sample + walk-forward,
  few parameters. A pretty backtest is not proof.
- **Risk first.** Position sizing, daily loss cap, max open trades enforced
  before any signal is acted on.

## Structure
```
forexbot/
  config/            # config.yaml (private) + config.example.yaml
  bot/
    core/            # broker (MT5), risk manager, execution
    strategies/      # plug-in strategies (base + implementations)
    data/            # news / economic-calendar filter
  backtest/          # backtester + A/B harness
  logs/              # trade logs, performance DB
  check_connection.py  # Step 1 smoke test
```

## Setup
1. Install MetaTrader 5 desktop, log into your **demo** account, enable Algo Trading.
2. `pip install -r requirements.txt`
3. Copy `config/config.example.yaml` -> `config/config.yaml`, fill in login/server + API keys.
4. `python check_connection.py`  ← should print account info + candles.

## Status
- [x] Project scaffold
- [x] MT5 broker connection + smoke test
- [ ] Risk manager
- [ ] Strategy 1 (EMA crossover) + Strategy 2 (Bollinger + RSI)
- [ ] Backtester (realistic costs, walk-forward)
- [ ] News / economic-calendar filter
- [ ] Live-demo loop + performance logging

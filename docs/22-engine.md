# 22 — The engine: how it works, end to end

*Written 2026-10-13, at the user's request: "complete documentation of the engine I have built so far ... from where we
are fetching the data, how it is processed, what the end result is, how all the things work, the factors", **excluding
the strategies and everything running on dry run**. Separate parts cover where the budget held the engine back, which
paid sources would improve it and how, and what changes if the capital constraint is removed.*

**What this document is NOT about.** It does not explain any strategy's rules or say whether one makes money. That is in
docs 01, 02, 10, 13, 16, 17 and 20. It also does not cover the `--final` book set running in `--mode dry` on the VM
(`final_books.py`, `combo-bot-final.service`), or any paper book's results. Strategies show up here only as *plug-ins*:
"a book produces target positions". What follows is the machinery under them: data in, processing, simulation,
validation, execution, records, deployment, monitoring.

Every statement names the file that implements it (CLAUDE.md rule 7). Line numbers are left out because they move.

---

## Contents

1. [The engine in one picture](#1-the-engine-in-one-picture)
2. [Layer 1 — data sources: where everything comes from](#2-layer-1--data-sources)
3. [Layer 2 — storage and caches](#3-layer-2--storage-and-caches)
4. [Layer 3 — data processing: from raw bars to clean, causal inputs](#4-layer-3--data-processing)
5. [Layer 4 — the simulation engine (backtester)](#5-layer-4--the-simulation-engine)
6. [Layer 5 — the validation machinery](#6-layer-5--the-validation-machinery)
7. [Layer 6 — the live execution engine](#7-layer-6--the-live-execution-engine)
8. [Layer 7 — records, reports and outputs](#8-layer-7--records-reports-and-outputs)
9. [Layer 8 — deployment, operations and monitoring](#9-layer-8--deployment-operations-and-monitoring)
10. [Layer 9 — the test harness](#10-layer-9--the-test-harness)
11. [The forex / MT5 side of the engine](#11-the-forex--mt5-side-of-the-engine)
12. [The end result: what the engine produces](#12-the-end-result)
13. [Known limits of the engine itself](#13-known-limits-of-the-engine-itself)
14. [**Where the budget held the engine back**](#14-where-the-budget-held-the-engine-back)
15. [**Paid sources that would make the engine better**](#15-paid-sources-that-would-make-the-engine-better)
16. [**If the capital constraint is removed**](#16-if-the-capital-constraint-is-removed)

---

## 1. The engine in one picture

```
 ┌──────────────────────────── LAYER 1: DATA SOURCES (all free / public) ────────────────────────────┐
 │ Binance REST (spot + USDT-M perps)   data.binance.vision archive (incl. 339 dead perps)            │
 │ Bitget via ccxt (market rules, 1m bars, orders)   OKX / Coinbase / Deribit / Upbit / Hyperliquid   │
 │ Sentiment + macro: alternative.me, Wikimedia, CoinMetrics, DefiLlama, yfinance                     │
 │ Forex: MT5 terminal (Exness ticks + bars), ForexFactory, Fed calendar; Databento (free credit)     │
 └──────────────────────────────────────────────┬──────────────────────────────────────────────────────┘
                                                │ fetch → cache to disk (gitignored)
 ┌──────────────── LAYER 2: STORAGE ─────────────▼─────────────────────────────────────────────────────┐
 │ strategy_analysis/data/{perps, min1, metrics, bitget_1m, doge_book, ...}  *.json / *.csv.gz / .parquet│
 └──────────────────────────────────────────────┬──────────────────────────────────────────────────────┘
                                                │ load → clean → resample → align
 ┌──────────────── LAYER 3: PROCESSING ──────────▼─────────────────────────────────────────────────────┐
 │ dedupe + stable sort · halt_cut (>7 day gap) · OHLC-correct resample · real entry time (causal_t0)  │
 │ ns-unit timestamps · point-in-time universe (wide_book.eligibility) · funding aligned to settlements│
 │ indicators (bot/core/indicators.py)                                                                 │
 └──────────────────────────────────────────────┬──────────────────────────────────────────────────────┘
                     ┌──────────────────────────┴───────────────────────────┐
                     ▼  (history)                                            ▼  (now)
 ┌───── LAYER 4: SIMULATION ENGINE ─────┐                ┌───── LAYER 6: LIVE EXECUTION ENGINE ─────┐
 │ bar-by-bar walk → trade rows (R)     │                │ poll every 120 s                          │
 │ + fees + funding per settlement      │                │ books → signed coin targets               │
 │ slot allocator, random tie orderings │                │ netting: targets − account = orders       │
 │ entry-sized compounding by close date│                │ venue rules, price sanity, market orders  │
 │ leverage series, metrics             │                │ disaster stops, intrabar stop checks      │
 └──────────────┬───────────────────────┘                │ state saved atomically each poll          │
                ▼                                        └──────────────┬────────────────────────────┘
 ┌───── LAYER 5: VALIDATION ────────────┐                               ▼
 │ 60/40 holdout · paired orderings ·   │                ┌───── LAYER 7: RECORDS ────────────────────┐
 │ bar phases · weekdays · Holm · MCPT ·│                │ state JSON · trades CSV · exec CSV · logs │
 │ matched-risk control · registered    │                │ --status · --report (PASS/NOT YET)        │
 │ predictions · haircut                │                │ rebuild_equity · status_server · health   │
 └──────────────────────────────────────┘                └───────────────────────────────────────────┘
                                 LAYER 8: Azure VM, systemd, git-pull deploy, ssh
                                 LAYER 9: 26 offline test files with fake exchanges + mutation checks
```

The engine has **two halves that share their code**:

- The **historical half** (`backtest/`): turns years of bars into trade rows, then equity curves, then honest metrics.
- The **live half** (`blend_paper.py`, `combo_paper.py`, `combo_bot.py`, `wick_live.py`): runs the same decision code
  on the latest closed bar. It then either books the result on paper or reconciles a real exchange account to it.

The live bots import their decision functions from the same modules the backtests use. "What the backtest
assumed" and "what the bot does" can therefore be compared trade by trade (`backtest/engine_vs_live.py`, CLAUDE.md §10
2026-10-06).

---

## 2. Layer 1 — data sources

Everything the engine reads is **public and free**, apart from one use of a paid vendor's free credit (Databento, §2.6).
No API key is needed for any data feed. Keys exist only for *placing orders* on Bitget, and come from the environment
(§7.8).

### 2.1 The core price feeds (what every backtest and live bot rests on)

| source | endpoint | what it gives | used by | notes |
|---|---|---|---|---|
| **Binance spot REST** | `api.binance.com/api/v3/klines` | 1h OHLCV per symbol, 1,000 bars a request | `backtest/mass_search.fetch` (history, cached as `{SYM}_1h_2400d.json`); `blend_paper.klines` (live, last 900 bars) | Live signals come from Binance because it has the deepest history, so live and backtest are priced the same way (`blend_paper.klines` docstring) |
| **Binance USDT-M perps REST** | `fapi.binance.com/fapi/v1/...` | `exchangeInfo` (what is listed, min notional), `ticker/24hr` (24h volume ranking), `ticker/price` (all prices in one call), `klines`, `fundingRate` | `mn_paper.perp_universe` / `candidates`, `combo_bot.binance_prices`, `perp_fetch` (current month) | `fundingRate` shares a 500-requests-per-5-minutes limit, so `perp_fetch.funding` sleeps 0.7 s between pages |
| **Binance public archive** | `data.binance.vision` (S3 bucket listing + monthly zip files) | **every USDT-M perp that ever existed**: daily and 1h klines, funding rates; spot first-listing dates; 1m klines; the daily positioning `metrics` files | `backtest/perp_fetch.py`, `backtest/metrics_fetch.py`, `backtest/scalp_1m.py` | **This is the single most important source.** It keeps delisted symbols, which the live API does not: 864 USDT perps, **339 of them dead**. Without it, every universe would carry survivorship bias (CLAUDE.md rule 6) |
| **Bitget** (via the `ccxt` library) | public: `load_markets`, `fetch_ohlcv`, `fetch_ticker`; private v2 mix endpoints | the execution venue. Per-coin contract size, amount step, amount minimum and value minimum; 1m candles back to 2022; positions, equity, orders | `combo_bot.Venue`, `backtest/bitget_1m.py`, `wick_paper.py`, `backtest/bitget_minimums.py` | The 1m history endpoint serves **200 bars a request** (the recent endpoint 1,000), so 90 days of 1m bars is ~650 requests (`bitget_1m.py`) |

**How the archive downloader works** (`backtest/perp_fetch.py`):

1. List every directory under `data/futures/um/monthly/klines/` through the S3 `list-type=2` API, following
   continuation tokens (`list_prefix`).
2. Keep `*USDT` symbols with no underscore (dated futures are excluded).
3. Mark each symbol alive or dead from the live `exchangeInfo`.
4. For each symbol, 16 threads in parallel:
   - download every monthly zip of 1d klines and funding;
   - for live symbols, top up the current, not-yet-archived month from the REST API;
   - record the first SPOT month, so an old coin that got a perp late can be told apart from a new token.
5. Write `{SYM}_1d.csv.gz`, `{SYM}_funding.csv.gz` and a per-symbol `{SYM}.json` meta file. The run is **resumable**:
   a symbol whose meta file exists is skipped.
6. `--hourly` repeats the process for 1h bars (`{SYM}_1h.csv.gz`).
7. `universe.json` lists every usable symbol, with first and last date, alive flag and bar count.

### 2.2 Positioning, order flow and liquidations

| source | what | file | limit that shaped it |
|---|---|---|---|
| Binance `metrics` daily archive | open interest, top-trader long/short ratios (by count and by size), all-account ratio, taker buy/sell ratio, every 5 minutes, from 2020-09 | `backtest/metrics_fetch.py` → `strategy_analysis/data/metrics/{SYM}.csv.gz` | The REST endpoints (`/futures/data/openInterestHist` and similar) keep **only 30 days**. Real history means one archive file per symbol per day |
| Bitget + Binance order books, trades, BTC best bid/ask | 50-level / 20-level books about once a second, taker trades every ~2 s | `book_rec.py` → `strategy_analysis/data/doge_book/` | **No free historical order book exists**, so it can only be recorded live, forward. 262 minutes were recorded (CLAUDE.md §10, 2026-10-09) |
| OKX liquidations, Binance open interest | every published liquidation for 5 swaps, polled every ~10 s; OI every ~10 s | `liq_rec.py` | Binance's liquidation **websocket** delivers nothing on the user's PC network; OKX REST needs a browser User-Agent or it returns 403 |
| Hyperliquid | leaderboard and `info` API | `backtest/hl_copy.py`, `first_perp.py` | — |

### 2.3 Regime, sentiment and macro inputs

| source | what | file |
|---|---|---|
| Coinbase Exchange API | BTC-USD and USDT-USD candles → the "Coinbase premium" | `btc_regime_now.py`, `backtest/btc_signals.py` |
| alternative.me | Fear & Greed index history | `backtest/sentiment.py`, `signals_fetch.py` |
| Wikimedia REST API | Wikipedia page views (attention) | `backtest/sentiment.py` |
| CoinMetrics community API | MVRV, exchange net flows (on-chain) | `backtest/btc_signals.py` |
| Deribit public API | options data (implied volatility for the volatility-premium tests) | `backtest/volprem.py`, `volprem_eth.py` |
| DefiLlama | token unlock schedules (`defillama-datasets.llama.fi/emissions`), stablecoin supply | `backtest/unlocks.py`, `entry_features.py` |
| yfinance | Nasdaq / QQQ, DXY, VIX, commodities, indices | `backtest/tradfi.py`, `fx_tsmom.py`, `nq_*.py` |

### 2.4 Event data

| source | what | file |
|---|---|---|
| Upbit API | Korean listings, delistings, KRW prices (kimchi premium) | `backtest/kimchi.py`, `listing_events.py`, `delist_events.py` |
| Binance announcements (`bapi/composite`) | listing announcements | `backtest/listing_events.py` |
| MEXC, Gate.io | first-listing dates on other venues | `backtest/first_perp.py` |
| pump.fun + GeckoTerminal | memecoin graduations and their DEX prices | `meme_collector.py`, `backtest/meme_grad.py` |
| Polymarket gamma + CLOB APIs | prediction-market prices | `poly_forward.py`, doc 08 |

### 2.5 Live, read-only "what is the market doing now" tools

These read public endpoints, need no keys and place no orders:

- `btc_regime_now.py`: the BTC regime gate, the 4h break level, momentum, the Coinbase premium and funding.
- `odds_now.py`: looks a live moment up in a historical table of 2.7M coin-hours (`strategy_analysis/data/odds_table.parquet`).

### 2.6 The forex / index sources

| source | what | file |
|---|---|---|
| **MetaTrader 5 terminal** (Exness, Python `MetaTrader5` package, Windows only) | bars and **millisecond bid/ask ticks** (USTECm from 2026-01), contract specs | `bot/core/broker.py`, `bot/core/instrument.py`, `backtest/his_ticks.py`, `his_tick_cache.py` |
| ForexFactory calendar | economic releases and surprises | `backtest/ff_calendar.py` |
| Federal Reserve FOMC calendar | Fed meeting days | `backtest/his_news.py` |
| Alpaca news API | headlines | `backtest/his_headlines.py` |
| CNN archive of Trump posts | post times | `backtest/his_posts.py` |
| **Databento** (paid vendor, used on the $125 sign-up credit) | CME NQ trades with aggressor side | `backtest/his_tape.py`; 801,045 trades for **$1.33** of credit (`strategy_analysis/his_strategy.md` §37) |

---

## 3. Layer 2 — storage and caches

All market data lives under **`strategy_analysis/data/`, which is gitignored**. A fresh clone holds none of it, and every
script rebuilds its own cache on first run (doc 09, "Reproducing the 2026-10-08 backtests").

| path | content | format | built by |
|---|---|---|---|
| `strategy_analysis/data/{SYM}_1h_2400d.json` | Binance spot 1h bars, ~6.5 years | JSON rows `t o h l c v` | `mass_search.fetch` (via `blend.load`) |
| `strategy_analysis/data/perps/` | every USDT-M perp: `_1d`, `_1h`, `_funding` `.csv.gz` + `{SYM}.json` meta + `universe.json` | gzip CSV | `perp_fetch.py` |
| `strategy_analysis/data/min1/` | Binance 1m perp bars (BTC, DOGE, 2022-01 to 2026-08) | — | `scalp_1m.py` |
| `strategy_analysis/data/bitget_1m/{COIN}.parquet` | Bitget 1m bars, closed bars only, topped up incrementally | parquet | `bitget_1m.py` |
| `strategy_analysis/data/metrics/` | 5-minute positioning per symbol | gzip CSV | `metrics_fetch.py` |
| `strategy_analysis/data/doge_book/` | live order book, trades, liquidations, OI | CSV | `book_rec.py`, `liq_rec.py` |
| `strategy_analysis/data/odds_table.parquet` | 2.7M coin-hours of cells for `odds_now.py` | parquet | `odds_now.py --build` (~3 min) |
| `strategy_analysis/data/worst_month_trend.pkl` | the trend book's daily series used by every portfolio-mix script | pickle | `python -m backtest.machine` |
| `logs/*_cache/` | per-study panels (e.g. `daily_combos_cache`, ~1.3 GB on first build) | parquet / pickle | the study scripts |

**Two cache rules the engine relies on:**

- **Caches are append-and-reuse.** A cache file that exists is read, not re-downloaded.
  `strategy_analysis/data/{SYM}_1h_2400d.json` is therefore **frozen at the date it was built (2026-09-11 16:00)**. Any
  test of recent weeks must use a fresh fetch (CLAUDE.md §10, 2026-10-06). See §13.
- **Secrets never go in the data folder or the repo.** `statement_raw.txt` and `statement_trades.csv` (a real name and
  account number) are gitignored. Raw Databento CME data stays in the ignored folder; only aggregates are committed.

---

## 4. Layer 3 — data processing

Each step below exists because skipping it once produced a wrong answer. The trap table in CLAUDE.md §3 has the history.

### 4.1 Cleaning

| step | rule | where | why |
|---|---|---|---|
| Deduplicate | one row per bar open time | every loader (`drop_duplicates("t")`) | archive months overlap the live top-up |
| Sort | `sort_values(..., kind="stable")` | `capitulation_wide.hourly` and later loaders | the default quicksort reordered simultaneous rows and broke a log's self-check (trap table) |
| Drop bad prices | `close > 0` | `wide_book.one_coin`, `capitulation_wide.hourly` | zero-price rows in some archive files |
| **Halt cut** | stop a coin's history at the first gap **longer than 7 days** (a real halt or relisting); keep shorter gaps | `capitulation_wide.halt_cut` | the old 48h rule read two 2022 archive holes as halts and cut 51 coins at 2022-02-25, so 16.4% of point-in-time coin-months were missing (fixed 2026-10-09) |
| Minimum history | a coin needs > 600 hourly bars; a sleeve needs ≥ 300 resampled bars | `capitulation_wide.hourly`, `blend.sleeve` | indicators need warm-up |
| Closed bars only | the forming bar is never used | `blend_paper.cycle` (`df.iloc[:-1]`), `bitget_1m` (drops the last bar while forming) | a forming bar's high/low/close are not final |

### 4.2 Resampling (1h → 4h / 12h / daily)

`backtest/timeframes.resample` and `blend_paper.resample`:

- aggregation is **first open, max high, min low, last close, summed volume**. Taking `last` for `high` would silently
  disable every stop check;
- `label="right", closed="right"`, so a 4h bar is labelled with its END time.

**The bar-label trap.** Because of that labelling, a 4h row's label is 3h after the real entry, and a 12h row's is
11h after. `backtest/causal_t0.real_t0(rows)` moves every row's `t0` back to the real entry time,
`label − rule + 1h` (`LATE` table). The real time is then used for ordering, for regime gates and for anything read
with `asof(t0)`. Mistake #12: the short boost's "+0.481R" was 118 look-ahead trades.

**Bar phases.** A 4h bar can start at 00:00, 01:00, 02:00 or 03:00 UTC. `capitulation_wide.four_hour(h, offset_min)` and
`backtest/bar_phase.py` rebuild bars at every phase, so a result can be checked on all four (§6).

### 4.3 Time handling

- **Every clock is UTC.** `deploy/setup.sh` sets the VM's timezone to UTC, because bots keyed to hourly bars drift on
  local time.
- **Timestamps are forced to nanoseconds** before any comparison: `.as_unit("ns")`, and `blend_paper._ns()` for `asof`.
  A mix of `[us]` and `[ms]` once made `searchsorted` place every span past the end of the grid, and a leverage series
  came back silently zero (trap table).
- **Git Bash clocks lie** on the Windows PC: they print local PKT time labelled PST. Freshness checks take the time from
  Python (`datetime.now(timezone.utc)`).

### 4.4 The point-in-time universe

`backtest/wide_book.eligibility(top_n)` builds a survivorship-free universe:

1. Read every perp's daily quote volume and sum it by calendar month.
2. For each month, take the **top N by the PRIOR month's volume**, among coins listed for at least 30 days.
3. Return `{symbol: set of 'YYYY-MM' months it was eligible}`.
4. A trade counts only if its coin was eligible **at entry**.

Dead coins are in the universe while they traded. Nothing knows in advance which coins survive. Selection filters
may read only data from the entry time or earlier: `market_neutral.py` once required a price at the END of the hold
and silently dropped coins that died mid-hold (trap table).

Live, the same idea is free: `mn_paper.perp_universe` reads today's listings, then ranks by 24h quote volume in one
request (`candidates`). Stock tokens (`isRwa`) and stablecoins are excluded on Bitget (`pair_live.py`).

### 4.5 Funding alignment

`backtest/funding_cost.py`:

1. Read the archive's funding history and floor each settlement to the hour.
2. Take the coin's price at each settlement by forward-filling the 1h opens.
3. Store `(settlement time in ns, rate × price)`.
4. Funding paid between two times uses a **half-open window `(t_from, t_to]`** via `searchsorted(side="right")`
   (`paid`). Open at both ends, the window double-counts: that is the still-open `mn_paper.py` bug, mistake #15.

### 4.6 Indicators

`bot/core/indicators.py` holds pure, vectorised pandas functions: `ema`, `sma`, `rsi`, `atr`, `bollinger`, `macd`,
`adx`, `donchian`, `efficiency_ratio` and others. `backtest/tv_indicators.py` adds the TradingView family (SuperTrend,
Squeeze, Ichimoku, PSAR, Hull, Williams %R, CCI, MFI, OBV, Heikin-Ashi, VWAP, plus the restored aroon/DMI library).
Indicators read only the past: an entry on bar *i* is sized from `atr[i-1]`.

---

## 5. Layer 4 — the simulation engine

### 5.1 The walk: one coin, one timeframe, bar by bar

The core simulators are `backtest/pyramid.run_pyramid` (long side, with adds), `backtest/convex.run_uncapped` (one unit,
several exit modes) and their corrected descendants `engine_variants.long_walk` and `graveyard_rescore.walk` (funding,
time stops and extra exits). They all follow the same causal contract:

| rule | implementation |
|---|---|
| **Entry** at the OPEN of the bar after the signal bar | `pos = dict(..., stop=o[i] - risk, ...)` |
| **Size** from the PREVIOUS bar's ATR | `risk = sl_mult * a[i-1]`; 1R = the stop distance |
| **Stop checked first**, against the bar's own extreme, before the trail moves | `hit = lo[i] <= pos["stop"]` happens before the trail update |
| **Adds fill at the trigger price**, never at the bar's high | `entries.append(entries[0] + next_add * add_every * risk)` |
| **Pessimistic same-bar fill** (`strict_fill`) | if the stop just advanced into this bar's range, it is assumed filled in this bar |
| **Never fill before arming** | a level armed on bar *i* fills only at `i > armed_bar` (the "pullback adds" retraction: holdout +15.4% → +4.2%) |
| **Fees** on every unit, both sides | `cost = sum(fee * e for e in entries) / risk`, `FEE_BP = 12` round trip |
| Open position at the end of data | closed at the last close |

The walk's output is a list of **trade rows**: entry time `t0`, exit time `t1`, result `R` (in units of the initial
risk, net of fees), side, coin, timeframe (`rule`), the times of each add (`adds`), the stop as a fraction of price
(`sf`), and units used and bars held. Everything after this point works on rows. That keeps the per-coin walk separate
from portfolio decisions.

The walk can do: fixed stop, ATR trailing stop, breakeven floor, pyramiding up to N units every k·R, time stop, and
alternative exits. **What values a strategy uses is strategy configuration, not engine.** The current constants are in
`backtest/blend.py` and `blend_paper.py`.

### 5.2 Funding, charged per unit per settlement

`funding_cost.charged(...)`, `long_funding`, `short_funding`:

```
funding R  =  − side × Σ over settlements held ( rate_s × price_s ) / r
```

Here `r` is the position's 1R price distance. Each unit is charged from its real fill time to the real exit. Adds are
counted from their bar's start, which over-counts by at most one settlement, so it is conservative for a long. Nothing
is charged before a coin's perp existed. Funding cost the deployed book **21.5% of its lifetime long profit** (mistake #13).

### 5.3 The portfolio allocator

`graveyard_rescore.taken` / `mtm_sizing.simulate` / `bull_boost.evaluate` take all rows from all coins and timeframes
and decide which become positions:

1. **Order by real entry time.** Simultaneous entries are broken by a **seeded random tie-breaker**
   (`rng.random(len(rows))`). Every figure is averaged over 5–10 seeds, because ordering alone moves a month by
   ±3–5%.
2. **Shared slots** (12): a row is declined if every slot is taken.
3. **Slot release causality.** A slot is freed when the exit bar CLOSES, not at the exit bar's label. Freeing it at the
   label let the allocator "know" a stop would hit later that hour, which flattered the tune half by 1.3–1.6%/mo
   (mistake #17).
4. **Regime gate at real entry**: `bear.asof(t0)` multiplies risk. BTC regimes come from `bull_boost.regimes()`
   (BTC close vs its 200h and 1000h average, shifted one bar so it is known at decision time).
5. **Risk per trade** = `RISK/100 × multipliers`, converted to dollars per R.

### 5.4 Compounding: three conventions, and only one is the truth

| convention | where | what it does | use |
|---|---|---|---|
| daily sum | `bull_boost.evaluate` | sums each day's `R × f` and compounds daily | comparisons **inside one file** only |
| sequential | `small_capital.simulate`, `blend.run` | multiplies equity by `(1 + R·f)` trade after trade | comparisons inside one file only |
| **entry-sized, realised** | **`mtm_sizing.simulate(..., "realised")`**, `graveyard_rescore` `curve(..., "entry_sized")` | a position's dollars are fixed **at entry** from equity of trades **already closed**; P&L is banked **at close date** | **the only one to quote** (rule 12) |

The first two credit open positions with profit that other trades banked later, which roughly doubles the return
(mistake #14). Banking by close date, not entry order, is rule 3: in entry order the same book showed 85% drawdown
instead of 57%. `mtm_sizing` also offers `"mtm"` and `"half"` modes, which size new entries on equity including open
profit, as a measured alternative.

### 5.5 Leverage accounting

`bull_boost.evaluate(..., grid=...)` adds every unit's notional (`f / sf`, risk divided by stop width) onto an hourly
grid between its add time and exit. The result is the account's gross leverage at every hour; the 99th percentile
and the maximum are reported. `backtest/triple_capped.py` replays the live **10× gross guard**: an entry or add that
would breach it is refused, as `blend_paper.MAX_LEVERAGE = 10.0` does live. **The simulator cannot model a forced
liquidation**, which is why the guard is a hard rule and not a tuning knob (CLAUDE.md §7).

### 5.6 Intrabar reality checks

Hourly bars hide what happens inside the hour. For any book that buys into a move, the engine re-measures on finer bars:

- `backtest/wick_5m.py`: 5-minute bars for every fill hour;
- `joint_worst_hour.py`: the whole account's worst point inside an hour, summed across books;
- `wick_bitget.py`: Bitget's own 1m bars, replaying the live code over 2022–2026.

### 5.7 Metrics produced

`backtest/compounding.summarize` and the study scripts report:

- %/month (`hpm`) — after the **3× hindsight haircut** on anything using the hand-picked 12 coins;
- raw %/month;
- CAGR;
- max drawdown (on the realised curve);
- worst month (**raw**);
- months losing;
- typical / bad / worst 12-month outcome for a given starting balance (`one_year.py`, `month_dist.py`);
- p99 and max leverage;
- per-regime returns (`regime_and_liq.py`).

**The haircut asymmetry.** Dividing an annualised rate by 3 shrinks losses as eagerly as gains. So **downside is quoted
raw and upside haircut**, and each is labelled (trap table: "Haircutting a LOSS").

---

## 6. Layer 5 — the validation machinery

The authority is `strategy_analysis/validation_protocol.md`. In engine terms, these are the gates a result passes
through:

| gate | how | tool |
|---|---|---|
| **Holdout** | split at `ts[int(len(ts) * 0.6)]`; tune on the first 60%, judge on the last 40% | every study |
| **Paired orderings** | variant and baseline on the SAME seed; report mean ± standard error of the difference and a win count (e.g. 10/10) | `graveyard_rescore.score`; trap: "Comparing medians across orderings" |
| **Bar phases** | rebuild 4h bars at 4 offsets and repeat | `bar_phase.py`, `capitulation_wide.four_hour` |
| **Weekdays** | run any weekly book from each of the 7 weekdays | `mn_combos.mn_run(start=0..6)` |
| **Matched-risk control** | does the variant beat "the baseline at more (or less) risk" at the same drawdown? | `slots_sweep.py`, `sleeve_risk_control.py`, `worst_month.py` |
| **Multiple comparisons** | Holm correction across scanned signals | doc 13, `his_*` studies |
| **Monte Carlo permutation (MCPT)** | shuffle bars, re-run the whole search | `mcpt.py` |
| **Permutation / bootstrap** | signal-date permutation; block bootstrap of drawdowns | `breadth_oos.py`, `bull_boost.bootstrap_dd` |
| **Out-of-period replication** | frozen parameters on data never seen (e.g. the 2018 bear) | `breadth_oos.py` |
| **Registered prediction** | the expected result is written into the file's docstring BEFORE it runs; the RESULT is appended after | every study file |
| **Self-check** | a new script first reproduces the file it extends, and asserts it | doc 09 |
| **Forward paper** | the only evidence that cannot be mined | the paper books |

---

## 7. Layer 6 — the live execution engine

The live engine is built around `combo_bot.py`, which delegates its decisions to the paper modules (`combo_paper.py`,
`blend_paper.py`, `mn_paper.py`). This section describes the **machinery**: how a decision becomes an order, and what
protects the account. Which books feed it is strategy.

### 7.1 The loop

`combo_bot.main` → `poll` every **`POLL_S = 120` seconds**:

1. **Equity.** In live mode the books size off the real account (`venue.equity()`). Demo and dry modes use a virtual
   equity.
2. **Daily step.** Once per UTC day, `cp.daily(st)` runs the daily/weekly books and refreshes their fixed coin
   quantities.
3. **Bar step.** `cp.trend_poll` → `blend_paper.cycle` walks every coin × timeframe. It acts **once per closed bar**
   (`last_bar[key]`) and never on the forming bar. One klines download per coin per poll is shared by every book
   (`kc` cache), so extra books cost no API calls and all books see identical bars.
4. **Execute** (§7.2).
5. **Save state** (§7.7).
6. Between polls, an optional 3-second watcher runs for resting limit orders (§7.5).

**Warm start** (`combo_bot.warm_start`). On a fresh start, the last closed bar may have closed hours ago (up to 12h).
A paper book would enter at that stale close; a real order would fill at today's price. The first dry run showed LTC
"entered" 8% away from the market. So every coin and timeframe with no open position is marked as having already seen
its latest bar, and entries come only from bars that close after the start. Open positions keep being managed.

### 7.2 From books to orders: netting

Bitget in **one-way mode** holds one net position per coin, so separate books cannot each place their own orders.
The engine nets instead:

```
book_targets(st)      → {symbol: signed coin quantity} summed over every book
   (route_demo)       → demo only: every coin mapped onto SBTC/SETH/SXRP by dollar value
Venue.symbol()        → Binance name → Bitget market (e.g. XRPUSDT → XRP/USDT:USDT); unlisted coins skipped, logged once
Venue.positions()     → what the account really holds  (dry mode: a virtual ledger)
plan_orders(targets, actual, prices) → [(symbol, side, qty, reduce_only, why)]
```

`plan_orders` rules:

- skip a change worth less than `MIN_ORDER = $5`, **except a full close, which always goes**;
- a position that **changes sign** is closed first with a reduce-only order, then reopened. No single order both closes
  and opens, which is what the `--report` flip counter looks for;
- shrinking → `reduce` (reduce-only); growing → `open` / `add`.

A held coin that no book wants any more is still looked up for a price, so it gets closed. Until 2026-10-09 the virtual
ledger kept such positions open (`test_dry_ledger_closes_what_the_books_exit`).

### 7.3 Before an order is sent

For each planned order, in `combo_bot.execute`:

1. **The venue's own minimums** (`Venue.rules`): amount step, minimum amount and minimum value, read from Bitget's
   market record (`load_markets`), not from a table. Bitget's amount minimum is also its step: 1 whole LINK, 0.1 LTC.
2. **Round to the NEAREST step** (`Venue.contracts(..., nearest=True)`). ccxt truncates, which biased every LINK order
   small by a median 9.4%. An amount under one step makes ccxt raise `InvalidOrder`; this is caught and read as zero
   contracts. Uncaught, it once killed every poll (CLAUDE.md §7b).
3. **Refusal** (`Venue.refusal`): an order the venue cannot accept is not sent, and is logged **once** with a fixed
   phrase (`BELOW VENUE MINIMUM`). It is not re-sent every poll. Before this fix the demo logged 188 identical
   failures.
4. **Price sanity**: the venue's last price must be within **3%** (`PRICE_TOL`) of Binance's. A larger gap is what a
   symbol mismatch looks like (1000PEPE vs PEPE), so the order is refused.
5. **Account settings** per symbol on first use: **cross margin** and leverage setting 20 (`Venue.settings`). Isolated
   10× would liquidate an alt ~9% against entry, inside many trend stops. The cap on real exposure is the books' own
   gross guard, not this exchange setting.

### 7.4 Sending, pricing and recording a fill

- **Market orders** (`Venue.order`), reduce-only where needed.
- **Fill price.** Bitget's create-order response carries no fill price, so `fill_price` re-reads the order by id up
  to 3 times (`fetch_order.average`). If that fails it falls back to the assumed price and labels it `assumed`.
  Recording never breaks trading.
- **Slippage** in basis points against the Binance reference, signed so positive means against us.
- Every order is appended to `combo_exec.csv`: time, mode, symbol, side, quantity, why, reduce flag, reference price,
  fill, price source, slippage, notional.

### 7.5 Protection layers

| layer | what | where |
|---|---|---|
| **Intrabar stop check** | every poll, a trend position whose stop the live price has crossed is flagged `breached` and exited at market. The flag is sticky until the bar closes, so a bounce cannot re-buy a stop-out inside the same bar | `combo_bot.mark_breaches` |
| **Disaster stop** | one exchange-side trigger order per net position, **30%** beyond the mark, reduce-only, re-placed when size or side changes, cancelled when flat. It is the backstop if the process or machine dies, not the strategy's exit | `combo_bot.stops`, `CAT_STOP` |
| **Short-leg squeeze exit** | a market-neutral short 50% above its opening price is dropped until the next rebalance. The netting would otherwise re-open a position the disaster stop closed | `combo_bot.mn_squeeze_exits` |
| **Gross leverage guard** | entries and adds that would take the book past its cap are refused | `blend_paper.MAX_LEVERAGE = 10.0` |
| **Limit-order fill watcher** | for resting post-only limit orders: polls `pending()` every 3 s, counts fills, cancels the rest once a cap is reached, and hands fills to the netting at the hour's close. The cancel set is **whatever is still live on the exchange**, not what bookkeeping thinks is open (mistake #16) | `wick_live.WickDesk`, `Venue.limit_buy/pending/cancel_limit` |

### 7.6 Modes

| mode | venue | keys | orders | equity |
|---|---|---|---|---|
| `demo` | Bitget demo, `SUSDT-FUTURES` (lists only SBTC/SETH/SXRP, so every coin is routed onto them: tests the order path, P&L meaningless) | yes | yes, demo funds | virtual $221 |
| `dry` | Bitget's REAL market list (unauthenticated ccxt) + live Binance prices | none | none; a virtual ledger | virtual |
| `live` | `USDT-FUTURES` | yes | real | the account's real equity |

### 7.7 Hard gates

1. **`ALLOW_REAL = False`** in `combo_bot.py`, `longtrend_bot.py` and `micro_bot.py`. `resolve()` refuses
   `--mode live` while it is False. Only a human edits it.
2. **One account, one bot.** `guard_one_bot` lists every python process (PowerShell `Get-CimInstance` on Windows,
   `ps` on Linux) and refuses to start if another trading bot is running. If it cannot list processes, it refuses
   rather than guess. It sees only its own machine.
3. **Single-instance lock** per state directory: `combo_bot.pid` via `combo_paper.single_instance`. The liveness check
   is read-only. `os.kill(pid, 0)` kills the process on Windows (trap table).
4. **Dedicated account.** The netting closes any position the bot did not open.
5. **One-way position mode** is set on connect (`connect`).

### 7.8 Credentials

- Keys come **only from the environment**: `BITGET_API_KEY`, `BITGET_SECRET`, `BITGET_PASSWORD`.
- On the VM they live in `/etc/forexbot.env` (chmod 600, root, not in git), loaded by systemd's `EnvironmentFile=`.
- `deploy/make_key_paste.ps1` moves them from the PC without them ever entering a chat or a committed file.
- The key should be IP-whitelisted to the VM with no withdrawal right. `ALLOW_REAL` is the second layer, not the first.

### 7.9 State

- **Atomic state writes**: write `*.tmp`, then `os.replace` (`combo_paper.save`, `blend_paper.save_state`). A kill
  mid-write cannot corrupt state.
- `load()` fills any missing keys from `fresh()`, so older state files keep working after a code change.
- Each mode and book set has its own directory (`logs/combo_bot_<mode>[_final]/`). Dry runs never share files with a
  live bot (CLAUDE.md §7).
- A poll exception is caught and logged as `poll error`, and the loop continues. `--report` counts these.

---

## 8. Layer 7 — records, reports and outputs

| output | content | produced by |
|---|---|---|
| `logs/<dir>/combo_state.json`, `logs/blend_state*.json` | open positions, last bar seen per key, equity history, execution state (stops, refusals, virtual ledger) | the bots, every poll |
| `trades_*.csv` | one row per closed trade | `blend_paper.rec_trade`, `combo_paper.append` |
| `combo_exec.csv` | every order, with real fill and slippage | `combo_bot.execute` |
| `combo_paper.log` / `*.log` | the event diary (written per closed bar, so it is quiet between bars) | `combo_paper.log` |
| `combo_marks.csv` | each book's daily mark, separately | `combo_paper.daily` |
| `--status` | equity, open positions, targets, unmapped coins, stops, virtual ledger | `combo_bot.main`, `combo_paper.status` |
| **`--report`** | the two-week order-path check. **PASS** needs 14 days, 0 order failures, 0 stop-placement failures, 0 poll errors, every fill priced, median slippage ≤ 5bp, and at least one open, add, reduce, close and flip | `combo_bot.report`, `verdict` |
| `rebuild_equity.py` | each paper book's equity rebuilt entry-sized from its own trade log, with a self-check that replays the recorded column to the cent | `rebuild_equity.py` |
| `logs/*.txt` | saved stdout of every experiment: the numbers each doc cites | study scripts |

---

## 9. Layer 8 — deployment, operations and monitoring

### 9.1 Where it runs

- **Azure VM** (Azure for Students): Ubuntu 22.04, size **B2ats v2 (2 vCPU, 1 GiB RAM)**, Premium SSD P6 64 GB,
  region **Central India**. US regions are geo-blocked by Binance. A 2 GB swap file is mandatory, because several pandas
  processes do not fit in 1 GiB. 750 free hours a month covers exactly one VM (doc 06).
- **The user's Windows PC**: MT5 (Windows-only), TradingView Desktop, the recorders, and ad-hoc backtests.

### 9.2 Install and update

| step | file |
|---|---|
| first setup: UTC clock, venv, deps (MT5 excluded), Binance reachability smoke test, one no-order blend cycle | `deploy/setup.sh` |
| deploy = `git pull` (the repo is public), verify `blend_paper.py` by sha256, restart, print the books | `deploy/pull_and_rebuild.sh`, `update_combo.sh` |
| install one service with checks (refuses with no keys file or another bot running) | `deploy/install_demo_bot.sh`, `install_combo.sh`, `install_wick.sh` |
| read-only "what is on that box" | `deploy/check_vm.sh`, `status_digest.sh` (everything, under 4 KB of output) |

### 9.3 systemd units (`deploy/*.service`)

- `Restart=on-failure`, `RestartSec=120`.
- Order-placing units add `StartLimitBurst=3` in 600 s, so a crash loop stays down and waits for a human.
- Hardening: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=full`, `ProtectHome=read-only`,
  `ReadWritePaths=<app>/logs` (a bot can write only its logs).
- Output to the journal; `python -u` for unbuffered logs.

### 9.4 Access

- `ssh forexbot-vm` from the PC (alias and key in `~/.ssh/config`; the address is never committed).
- **Azure Run command** as a fallback. Its constraints shaped every deploy script: output truncated to the last
  ~4 KB, long lines wrap near 50 characters and the wrapped tail runs as a command, and pasted scripts are
  JSON-decoded. So deploy scripts keep lines under 44 characters, contain **no backslashes** (`chr(10)` instead) and
  carry payloads in heredocs.

### 9.5 Monitoring

**`health.py`**: three independent signals per bot, reported separately because they can disagree:

| signal | source |
|---|---|
| PROCESS | the pid from the bot's own lock file, cross-checked against its command line |
| HEARTBEAT | mtime of the state file written **every poll**, not the log, which is quiet for up to 12h between bars |
| PROGRESS | equity, positions, trades, rows: reported, not judged |

Verdicts: `OK`, `WEDGED` (alive but not writing: worse than dead), `DEAD`, `PROBABLY OK` (trust the files), and
`TWO COPIES`.

**`status_server.py`**: a read-only JSON page (GET only, a fixed allow-list of files under `logs/`, never reads the
environment, optional `STATUS_TOKEN`).

---

## 10. Layer 9 — the test harness

`tests/` holds 26 files that run offline:

- **Fake exchanges.** `test_combo_bot.py`, `test_wick_live.py` and `test_pair_live.py` drive the real code against an
  in-memory exchange that mimics ccxt: markets, steps, minimums, partial fills, `InvalidOrder`.
- **Regression tests that fail on the old code.** Each fixed bug gets a test that is shown to fail before the fix.
  Examples: `test_an_order_under_one_step_does_not_kill_the_poll`, `test_dry_ledger_closes_what_the_books_exit`,
  `test_mn_held.py`.
- **Mutation checks.** A rule is deliberately broken (an 8th unit, no guard, no time stop, a cancel set by
  bookkeeping) and the suite must catch it. Counts are recorded in CLAUDE.md §4/§10 (e.g. 16 of 16 mutations caught in
  `test_final_books.py`).
- **"Test in the disaster, not the tidy case."** Safety limits are tested in the situation they exist for, e.g. every
  bid partly filled (trap table, mistake #16).
- **Whole-script tests for deploy scripts**, against a fake target with stubbed `systemctl`, `sudo` and `sleep`.

Run: `python tests/test_combo_bot.py` (each file runs on its own; no pytest dependency is assumed).

---

## 11. The forex / MT5 side of the engine

`bot/` is the original MT5 engine (README.md). It is separate from the crypto engine and runs only on Windows:

| module | role |
|---|---|
| `bot/core/broker.py` | attaches to an already-running, logged-in MT5 terminal (`mt5.initialize()`). The password stays in MT5, never in the project |
| `bot/core/instrument.py` | reads real contract specs (pip size, pip value, spread) from MT5, so backtests use the right costs per instrument |
| `bot/core/execution.py` | orders tagged with a magic number, so the bot touches only its own positions; prices normalised to the symbol's digits; filling mode read from the symbol |
| `bot/core/risk.py` | position sizing, daily loss cap, max open trades, checked before any order |
| `bot/core/adaptive.py` | two gates: a statistical cut (only after a minimum trade count) and a circuit breaker (at any sample size) |
| `bot/core/filters.py` | post-signal filters. MT5 times are broker server time (Exness ~EET), not UTC |
| `bot/core/tradelog.py` | append-only event log + action CSV |
| `bot/strategies/` | plug-in strategy classes on a common `base.py` (`Action.BUY/SELL/HOLD`), built by `factory.py` |
| `config/config.yaml` | private settings (gitignored; `config.example.yaml` is the template) |

**Clock lesson.** MT5's own labels are UTC, but a broker statement's times shifted one hour on the EU clock change
(`backtest/his_clock_check.py`, CLAUDE.md §10 2026-10-02). Check any foreign clock against an outside anchor
(`mt5_clock_anchor.py`: the US cash open).

---

## 12. The end result

**Historical half.** For any strategy plugged in, the engine produces:

1. trade rows (entry, exit, R net of fees and funding, units, adds, stop width);
2. an entry-sized, close-date-banked daily equity curve per random ordering;
3. a leverage series;
4. metrics for each holdout half: haircut %/month, drawdown, worst month (raw), months losing, 12-month outcome
   distribution for a starting balance, per-regime returns;
5. a verdict against a pre-registered prediction, with paired standard errors and win counts.

**Live half.** It produces:

1. a reconciled exchange account (or a virtual ledger) that holds exactly what the books want;
2. a priced, slippage-measured record of every order;
3. an exchange-side backstop stop on every position;
4. state that survives restarts;
5. a two-week PASS / NOT YET verdict on the order path;
6. health checks that separate dead, wedged and quiet.

---

## 13. Known limits of the engine itself

These are engine properties to keep in mind, not bugs waiting to be fixed (open bugs are in CLAUDE.md §7b):

| limit | effect |
|---|---|
| The cached 1h history (`*_1h_2400d.json`) stops at 2026-09-11 16:00 | a backtest of recent weeks silently sees nothing; delete the cache or fetch fresh |
| Signals from **Binance** prices, execution on **Bitget** | price differences are guarded (3%), but backtests on Binance bars are a proxy for Bitget fills. Measured equal for the crash bids (`wick_bitget.py`) |
| Hourly bars as the main resolution | inside-the-hour paths need the 5m/1m checks (§5.6) |
| No liquidation model | the simulator does not know the exchange would close a position; the 10× guard is the substitute |
| Live position model ≠ the backtest allocator | one position per key, retries, a one-bar pause: plan on 1–2%/mo under published figures (`engine_vs_live.py`) |
| A 120-second poll | the engine acts in minutes, never in seconds; any edge that lives under a minute is out of reach by design |
| REST snapshots, about 1 s at best | websockets are unreliable on the PC network |
| `mn_paper.py`'s open funding window (mistake #15) and the blend books' recorded-equity overstatement | read those books through `rebuild_equity.py`, not `--status` |

---

## 14. Where the budget held the engine back

The constraint set (CLAUDE.md §1): **~$221 of capital, no co-location, no institutional data, free APIs only, a free
student VM.** Below is every place the repo records that constraint changing a result or a design, with its source.

### 14.1 Capital (~$221 / 10,000 PKR)

| where it binds | measured effect | source |
|---|---|---|
| Bitget's **$5 minimum order** and **per-coin minimum amounts** (1 LINK, 1 DOT, 0.1 LTC) | at $221 Bitget refuses **6.4% of the book's units** (26.2% of LINK's); every accepted LINK order is rounded by a median 9.4% | `backtest/bitget_minimums.py`, CLAUDE.md §7b |
| $10 accounts | 87–96% of units rejected; **$50 is the practical floor** | `lottery.py`, CLAUDE.md §10 2026-09-24 |
| The limit-order desk on the demo | at $221 a bid is $5.19, under the minimum on all three demo coins, so **0 bids placed**; the cap-cancel path cannot be exercised | CLAUDE.md §7b |
| Point-in-time books on 10,000 PKR | every order under $5: **cannot trade**. ~25,000 PKR is needed for the smallest combination; ~100–150k PKR for the full set | `pair_min_capital.py`, CLAUDE.md §10 2026-10-08 |
| Wider universes | most of the 30–100-coin books cannot be funded at $221 | `wide_book.py` docstring |
| The forex side | Exness lot minimums; the one forex book that holds fits at $300 only on a **Cent** account, and even there gold and silver are too big | doc 18 |

**What capital does not change.** Above ~$25 the return in **percent** is the same. Capital buys dollars, not rate
(CLAUDE.md §6). So the capital limit costs coverage (refused orders, untradeable coins, untested code paths), not
percentage return.

### 14.2 Fees: the retail tier

- Taker round trip **12bp** (Bitget charges 0.06% of order value per side; re-verified on the demo's fills); maker
  0.02% per side.
- It decided every fast strategy:
  - **1-minute scalping**: 0 of 572 tests net-positive at 12bp (`scalp_1m.py`);
  - **order-book signals**: real (IC +0.10 to +0.25 out to 60 s), but the move is 1–2bp, so maker net −2 to −3bp
    and taker −11 to −13bp. "The edge belongs to market makers" (`backtest/doge_book.py`);
  - **BTC→DOGE model**: +4bp a trade at maker, not significant; loses at taker (`maker_exec.py`, `btc_doge.py`);
  - **DOGE live forward test**: −1.41% over 7 trades at 12bp (`doge_live.py`).
- A **zero-maker-fee or rebate venue was never checked** (CLAUDE.md §10, 2026-10-09).

### 14.3 Speed: no co-location

- **Funding-settlement edge.** The post-settlement drop is **+8bp at 0.2 s, −6bp at 1 s, −15bp at 5 s**, a race won
  by co-located bots. "A PC in Pakistan cannot win it, and neither can a cloud VM anywhere else" (doc 11 §1,
  `settlement_ticks.py`).
- **The copy-a-trader result**: a copy within 5–10 s keeps the edge, but it is gone by 20 s (`his_copy_delay.py`).
- The engine polls every 120 s and records the book by REST at ~1 s. Binance websockets deliver nothing on the PC.

### 14.4 Free data: what was missing, and the workaround

| missing for free | consequence | workaround used |
|---|---|---|
| **Historical order books (L2)** | no backtest of book signals over months; only 262 minutes, recorded live | `book_rec.py` |
| **Historical liquidations** | the liquidation hypotheses (L1–L3) **could not be tested**: a quiet day gave one $103 event | `liq_rec.py` (forward only); the hourly cascade test (`cascade_redux.py`) used price, not liquidations |
| Positioning (OI, long/short) beyond **30 days** via the API | — | the daily archive, one file per symbol per day (`metrics_fetch.py`); Binance only, no Bitget/OKX/Bybit |
| Bitget history for **dead** coins | Bitget-price replays need a stand-in | Binance bars used for dead coins (`wick_bitget.py`) |
| Bitget 1m history before 2022; 200 bars a request | slow, limited replays | `bitget_1m.py` cache |
| Clean archive coverage | two 2022 holes in Binance's archive cut 51 coins until 2026-10-09 | `halt_cut` (> 7 days only) |
| Tick-level crypto history | intrabar questions answered on 1m/5m bars, not ticks | `wick_5m.py`, `scalp_1m.py` |
| NQ intraday history (yfinance: **60 days of 5m bars**) | forex/index rules could not be validated over years | MT5 ticks (only from **2026-01**), then Databento on free credit |
| On-chain data | only CoinMetrics' free community metrics (MVRV, flows) | — |
| Real-time news | free calendars and archives only | ForexFactory, Fed calendar, Alpaca, CNN archive |

### 14.5 Compute and hosting

- **One free VM with 1 GiB RAM** (750 free hours = one machine). Swap is mandatory. Every bot, paper book and recorder
  shares it. Heavy backtests (a 728-combination factorial, 1.3 GB panels) run on the PC instead, and two of them were
  stopped part-way (doc 09).
- **Azure Run command** limits (4 KB output, line wrapping, JSON decoding) dictated how deploy scripts are written,
  until ssh access was set up on 2026-10-05.
- The cloud dev container is blocked from Bitget, so venue checks run only from the PC (CLAUDE.md §7b).

---

## 15. Paid sources that would make the engine better

**Read this first.** No data purchase can fix the two constraints that decided most results here: **retail fees** and
**no co-location** (§14.2–14.3). The repo's finding is that every edge found was priced away by fees or by faster
players, not missed for lack of data (doc 11). The purchases below remove **measurement** gaps: tests that could not
be run, or were run on a proxy. They do not create edges. Prices were checked on 2026-10-13 from the vendors' public
pages and third-party listings, and they change, so confirm before paying.

### Ranked by what they would unlock for this engine

| # | source | approx. cost | what it adds to the engine | gap it closes (§14) |
|---|---|---|---|---|
| 1 | **CoinGlass API** | Hobbyist **$29/mo**, Startup $79/mo (personal use); Standard $299, Professional $699 | cross-exchange **liquidation history**, open interest, funding and long/short ratios, Bitget included; daily data all-time, 1h data ~180 days on the cheapest tier | the untested liquidation hypotheses; positioning beyond Binance and beyond 30 days. **The cheapest real upgrade.** |
| 2 | **Tardis.dev** | individual / solo discounts exist; third-party listings quote roughly **$50–900/mo** for small plans, published plans up to thousands. **The first day of every month is free, without a key** | tick-level trades, **full L2 order book history** (snapshots + incremental updates), liquidations, funding, OI, for Binance, Bitget, OKX, Bybit and more | months of order-book history instead of 262 minutes; Bitget's own history; exact intrabar fills. **Try the free first-of-month days before paying**: they are enough to re-run `doge_book.py` on dozens of full days |
| 3 | **CoinAPI** | pay-as-you-go with **$25 free credit**; Startup $79/mo, Streamer $249, Pro $599; flat files $10 per 1,000 calls + $1–3/GB | normalised trades, quotes and order-book snapshots across many venues | an alternative to #2. Better if only small, targeted pulls are needed |
| 4 | **Databento** | pay-as-you-go; **$125 sign-up credit**, $1.33 used so far | CME futures tick data with aggressor side (NQ, ES, CME BTC/ETH futures); MBO order book | the forex/index side: years of NQ instead of yfinance's 60 days; CME bitcoin basis. **Mostly still unspent: use the credit first** |
| 5 | **A lower fee tier / a maker-rebate venue** | not a data purchase: Bitget VIP tiers depend on volume or token holdings, and some venues pay makers. Not checked yet | lowers the 12bp round trip, the single number that killed every fast strategy | §14.2. **Larger effect than any data item**, but out of reach at $221 of volume; check whether a zero- or negative-maker-fee venue exists before buying data for fast strategies |
| 6 | **A larger or second VM** | ~$10–30/mo for 2–4 GiB RAM, after the student credit | runs recorders (`book_rec`, `liq_rec`) 24/7 beside the bots; ends the swap pressure | forward order-book and liquidation data with no subscription. **The cheapest way to own months of L2 data is to record it** |
| 7 | **A VPS in Tokyo** (near Binance/Bitget matching engines) | ~$5–20/mo | lower latency and less slippage on market orders | does **not** win the sub-second races (doc 11); a second-order improvement |
| 8 | **Polygon.io** (US stocks / indices) | paid tiers | long intraday history for Nasdaq stocks and indices | an alternative to #4 for the forex/index studies |
| 9 | **Glassnode / CryptoQuant** (on-chain) | paid tiers | better on-chain metrics than CoinMetrics' free set | **low priority**: doc 12 found MVRV and exchange flows do not improve the bot |
| 10 | **A paid news / squawk feed** | varies | real-time headlines | **low priority**: no news angle survived Holm (his_strategy.md §24, §28, §29) |

### How each paid source helps, in detail

For each source, this section says what changes inside the engine, which existing script it upgrades, the test it
would make possible, and the honest prior. The prior comes from what the free version of the same test already showed.

#### CoinGlass: positioning and liquidations across every venue

- **What changes in the engine.** A new loader beside `metrics_fetch.py`. It gives open interest, funding,
  long/short ratios and **liquidation totals for Bitget, OKX, Bybit and Binance**, not Binance alone. Today the engine's
  positioning data comes from Binance only; Bitget's own positioning is never seen.
- **Scripts it upgrades:**
  - `liq_rec.py` / `doge_book.py`: the L1–L3 liquidation hypotheses were registered and never testable (one $103
    event on a quiet day). Years of liquidation history decide them in an afternoon.
  - `cascade_redux.py`: the liquidation-cascade bounce was killed on hourly *price* bars. With real liquidation
    volumes, a cascade can be identified directly instead of inferred from price.
  - `btc_signals.py`: the "top traders piling long precede weaker weeks" result can be re-checked on all venues.
  - `capitulation_*.py`: the capitulation entry could require real forced selling, not only a price drop.
- **Honest prior.** Moderate. The capitulation family is the one place repeated tests found a direction that holds
  (doc 02, capit2). Liquidation data is the most direct measure of forced selling, the mechanism behind it. Positioning
  alone failed as a BTC timer (doc 12), so only the liquidation side is promising.

#### Tardis.dev (or CoinAPI): tick and order-book history

- **What changes in the engine.**
  - The backtester gets a **tick/L2 replay mode**. Stops, adds and limit fills can be resolved on the real sequence of
    trades instead of hourly highs and lows. This removes the "bar extreme" assumption in `pyramid.run_pyramid` and the
    trade-through rule in `maker_exec.py`.
  - The market-making question can be measured on months of data instead of 262 minutes.
- **Scripts it upgrades:**
  - `doge_book.py`: from one afternoon to months. Its R5 ("no feature gives a move above 12bp at 60 s or longer") was
    **not decidable** on 14 samples; months make it decidable.
  - `maker_exec.py`: measure queue position and adverse selection exactly. Today a limit fills only if price trades
    through it, which is pessimistic but blind to the queue.
  - `wick_5m.py` / `joint_worst_hour.py`: the crash hour of 2025-10-10, replayed tick by tick. That is the account's
    worst hour, and today it is measured on 1m/5m bars.
  - `wick_bitget.py`: Bitget's own history for dead coins, replacing the Binance stand-in.
  - `settlement_ticks.py`: the funding-settlement race measured on more venues and more years.
- **Honest prior.** The engine's accounting gets more exact, but no new edge is likely. Every free tick-level test so
  far said the information is real and the move is smaller than the fee. Months of data will most likely confirm that
  more precisely. The value is in checking the existing books' fills, especially the crash-hour fills.

#### Databento: CME futures

- **What changes in the engine.** The forex/index studies stop depending on yfinance's 60 days and on MT5 ticks that
  start in 2026-01.
- **Scripts it upgrades:**
  - `nq_*.py`, `fx_tsmom.py`: years of index and commodity futures at any resolution;
  - a **CME bitcoin futures basis** series (CME vs Binance), a regime input the crypto engine has never had.
- **Honest prior.** Low for the copy-trader question (`his_tape.py` already ruled the tape out). Useful for the
  forex/commodity trend book, the one forex result that held (doc 18). Most of the $125 credit is still unspent.

#### A better fee tier or venue

- **What changes in the engine.** One constant: `FEE_BP = 12` in `blend.py`, `blend_paper.py` and the study scripts.
- **Why it matters most.**
  - The fee is the number that decided the 1-minute, 15-minute, order-book, BTC→DOGE and DOGE live tests.
  - At a 2bp maker fee the BTC→DOGE model reads +4bp a trade (`maker_exec.py`), not significant but positive.
  - At a maker *rebate*, the 1–2bp order-book move (`doge_book.py`) stops being a loss.
- **Honest prior.** This is the only change that could turn a measured "real but too small" signal into a positive
  one. It cannot be bought at $221: fee tiers follow traded volume or holdings (see §16).

#### A second VM or a larger one

- **What changes.** `book_rec.py` and `liq_rec.py` run 24/7 beside the bots instead of on the PC for an evening. The
  recorders already exist and are tested.
- **Honest prior.** The cheapest route to owned L2 and liquidation data (~$10–30/mo). The catch is time: months of
  recording before anything can be tested.

### What to do first, if any money is spent

1. **Free first.** Pull Tardis's free first-of-month days for DOGE/BTC on Bitget and Binance, and spend the remaining
   Databento credit. Both cost nothing and test whether the paid version is worth it.
2. **CoinGlass Hobbyist ($29/mo, one month)** to test the liquidation hypotheses `liq_rec.py` registered, on years
   instead of one quiet day. Cancel if they fail, as the registered predictions expect most will.
3. **Record instead of buying** for anything forward-looking: put `book_rec.py` and `liq_rec.py` on the VM (or a small
   second one).
4. **Before buying anything for scalping or order-book trading**, find the fee tier or venue that would make a 1–2bp
   edge pay. Without that, better data only measures the same loss more precisely.

Sources for the prices: [CoinGlass pricing](https://coinglass.com/pricing),
[Tardis.dev](https://tardis.dev/) and [its FAQ](https://docs.tardis.dev/faq/general),
[CCXT vs Tardis.dev](https://docs.ccxt.com/docs/comparisons/ccxt-vs-tardis),
[CoinAPI pricing](https://www.coinapi.io/market-data-api/pricing),
[CoinAPI flat files](https://www.coinapi.io/products/flat-files/pricing); Databento from
`strategy_analysis/his_strategy.md` §36–37.

---

## 16. If the capital constraint is removed

The question: what happens to the engine if the account is not ~$221 but $2,000, $20,000 or more? Two answers are
easy to mix up. **Capital changes what the engine can DO** (orders accepted, books run, code paths exercised).
**It barely changes the PERCENTAGE the strategies earn.** Every number below names its file.

### 16.1 What does NOT change

| claim | evidence |
|---|---|
| **The monthly percentage is the same from ~$100 to $5,000** | `backtest/small_capital.py` (`logs/small_capital.txt`), deployed config: tune +20.12% at $25 and +20.14% at $100 to $5,000; holdout +10.3% to +12.5% with no trend; drawdown 56% at every size. (Measured on MEXC's minimums, CLAUDE.md §7b.) |
| **Risk per unit stays 0.30%** | `backtest/kelly_corrected.py`: 0.45% buys +0.34%/mo and multiplies the chance of an 80% drawdown within 3 years by nine (2.7% → 24.7%). This is a property of the strategy, not of the account size |
| **The worst month and the biggest fall stay the same in percent** | they scale with position SIZE, not with capital (`worst_month.py`) |
| **The regime dependence stays** | the trend book earns in bull markets and roughly nothing in chop at any capital (`regime_and_liq.py`, doc 20) |
| **Speed and fees stay retail**, unless volume reaches a fee tier (16.2) | §14.2–14.3 |
| **Low capital is not an advantage either** | `backtest/capacity_edge.py`: the edge gets WORSE in smaller coins, so a small account has no niche a fund cannot reach (doc 11 part 3) |

**One small effect goes the other way.** At $221, Bitget's minimums refuse the units with the widest stops, and that
*helps* return: +0.48 tune / +0.38 holdout %/mo, paired over 10 orderings (`backtest/bitget_minimums.py`, CLAUDE.md
§7b). A large account takes those units, so on paper it earns a fraction of a percent less a month. This is a side effect
of the minimum, not a tested rule. It is not a reason to stay small.

### 16.2 What capital unlocks in the engine

| today, at ~$221 | with more capital | evidence |
|---|---|---|
| Bitget refuses **6.4%** of the trend book's units (24.2% at $100); 26.2% of LINK's | **~0% refused**: every order the books want is placed | `bitget_minimums.py` |
| every accepted LINK order rounded by a median **9.4%** (step = 1 LINK) | rounding error shrinks in proportion to order size (≈0.9% at 10× the size) | CLAUDE.md §7b |
| the crash desk places **0 bids** on the demo (a $5.19 bid is under every demo coin's minimum); its cap-and-cancel path has never run on the exchange | bids of $50+ on all 40 coins; the cap path can finally be tested live | CLAUDE.md §7b |
| the bear sleeve skips **a third of its orders** (holdout +8%/yr instead of its full figure) | the sleeve runs as backtested | doc 13 |
| the point-in-time pair **cannot trade at 10,000 PKR**; ~25,000 PKR runs the pair, **~100–150k PKR** the full v3 set; "E" needs ~$300+ | every candidate combination fits on one account | `pair_min_capital.py`, doc 09 |
| a 4,000 PKR account has 70–75% of units refused; at 10,000 PKR about half | removed; small-account odds tables stop being dominated by refusals | `lottery_v2.py` |
| forex: the one book that holds fits only on a **Cent** account at $300, and gold/silver are too big even there | a standard swap-free account with every leg, including gold and silver | doc 18 |
| order-path testing on the demo, P&L meaningless | a real dedicated account large enough that every book trades: the forward record finally measures the strategies, not the plumbing | doc 20 |
| retail fee tier | trading volume rises with capital; above some 30-day volume or asset threshold a lower Bitget tier applies (not measured; check Bitget's VIP table) | §14.2 |
| withdrawals: half of each month's profit ≈ **$31–39/month** at $221 (backtest, typical) | the same percentage in bigger dollars: at $2,210 roughly ten times that. **Backtest figures, not a forecast** | CLAUDE.md §6 |

**What the engine needs for it.** Nothing new in the code: `combo_bot.py --mode live` already reads the account's
real equity, and every size is a fraction of equity. Only two things change:

- `ALLOW_REAL`, which a human sets;
- a **dedicated account**, because the bot nets the whole account to its books.

### 16.3 Where capital starts to hurt: capacity

A large account eventually moves the price it trades. `backtest/capacity_edge.py` measured this for the market-neutral
momentum book with a square-root impact model (`impact = daily volatility × sqrt(order / daily volume)`), charged on
both legs. Net %/week by volume tier and account size (`logs/capacity_edge.txt`):

| tier (by prior month's volume) | $200 | $20,000 | $200,000 | $2,000,000 | $20,000,000 |
|---|---|---|---|---|---|
| ranks 1–20 (mega) | +0.358% | +0.341% | +0.300% | +0.171% | −0.236% |
| ranks 21–60 (large) | +0.594% | +0.569% | +0.509% | +0.320% | −0.280% |
| ranks 61–120 (mid) | −0.004% | −0.035% | −0.109% | −0.342% | −1.080% |

Read it as:

- **up to ~$200,000** the top-60 books lose about a tenth of their edge to impact;
- **at $2 million** about half;
- **at $20 million** the edge is gone.

The trend book trades 12 mid-size alts (ARB, WLD, ENA and others), and its impact has **not** been measured. Its
pyramids add into moves, which costs more than a weekly rebalance, so its ceiling is probably lower than the
market-neutral book's. The crash desk buys into crashes, when order books are thinnest; its capacity is the least
known of all. **Measure impact before scaling either past five figures.**

### 16.4 Bottom line

- **Removing the capital constraint makes the engine run as designed.** Every order is accepted, every book fits on
  one account, the crash desk and bear sleeve trade fully, and the forward record measures the strategies instead of the
  venue's minimums.
- **It does not raise the percentage.** It raises dollars, with the same percentage drawdowns. A −30% month is still
  −30%, so a bigger account loses bigger dollars in the bad months.
- **After capital, the binding constraints are fees, speed and the market regime.** Capital helps with one of them,
  through a lower fee tier at high volume.
- **There is a ceiling.** Somewhere between $200,000 and $2,000,000 the market-neutral book's edge starts to shrink
  measurably; the other books need their own impact test first.

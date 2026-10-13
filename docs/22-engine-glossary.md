## Glossary: every term, section by section

*Plain-English meanings of the technical terms in this document, grouped by the section where each first appears. A term
explained once is not repeated later.*

### How to read the references

| term | meaning |
|---|---|
| **`file.py`, `backtest/...`** | a file in the project's code. Every number in this document names the file that produced it, so it can be re-run and checked |
| **CLAUDE.md** | the project's rulebook: the goal, the rules that keep results honest, and the known traps |
| **doc 02, doc 13, ...** | the numbered write-ups in the project's `docs/` folder. Doc 02 lists every idea tested and dropped |
| **mistake #12, #17, ...** | entries in doc 03, the list of bugs that once produced a wrong result, each with the rule added to stop it recurring |
| **§7.5** | section 7.5 of this document |

### 1. The engine in one picture

| term | meaning |
|---|---|
| **Engine** | all the machinery under the strategies: getting data, cleaning it, testing strategies on history, placing orders, keeping records |
| **Strategy / book** | a set of trading rules. A "book" is one strategy's set of positions. Several books can share one account |
| **Backtest** | running a strategy over past prices to see what it would have done |
| **Paper trading / paper book** | running a strategy live on current prices but with pretend money: no real orders |
| **Demo account** | an exchange account funded with play money (on Bitget, "SUSDT"). Real orders, fake money |
| **Live** | real orders with real money. Locked in this project until a human unlocks it |
| **API** | the doorway an exchange gives programs to read prices and send orders |
| **Bitget, Binance, OKX, Coinbase** | crypto exchanges. Bitget is where orders go; Binance supplies most of the price data |
| **ccxt** | a free code library that talks to ~100 exchanges in the same way, so the bot does not need exchange-specific code |
| **Netting** | adding up what every book wants to hold in a coin and sending one order for the difference (§7.2) |
| **Holdout** | the last 40% of history, kept unseen while a strategy is designed, then used once to judge it |
| **R** | the unit of risk: the amount a trade loses if its stop is hit. A "+3R" trade made three times what it risked |
| **Slot** | one place for an open position. The account allows a fixed number (12), shared by all coins and timeframes |
| **Compounding** | letting gains (and losses) change the size of later trades |

### 2. Layer 1 — data sources

| term | meaning |
|---|---|
| **Spot** | buying the actual coin |
| **Perpetual futures ("perp")** | a contract that tracks a coin's price with no expiry date. It can be held long (betting up) or short (betting down), with leverage |
| **USDT-M** | perps settled in USDT, a dollar-pegged stablecoin |
| **Long / short** | a long profits when price rises; a short profits when it falls |
| **Leverage** | controlling a position larger than the money in the account. 10× means $100 controls $1,000 |
| **OHLCV / candle / bar / kline** | one time period's open, high, low, close prices and volume. "1h bars" are hourly candles |
| **Quote volume** | trading volume measured in dollars (USDT) rather than coins |
| **REST** | asking a server for data one request at a time. The engine's normal way of reading data |
| **Websocket** | a connection the server pushes data down continuously. Faster, but on the user's PC network Binance's deliver nothing |
| **Endpoint** | one specific address on an exchange's API, e.g. "give me klines" or "give me funding rates" |
| **Rate limit** | how many requests an exchange allows per minute before it refuses |
| **data.binance.vision / archive** | Binance's free public store of historical data files, including coins that no longer trade |
| **S3 bucket** | Amazon's file storage, which hosts that archive. The engine lists its folders to find every file |
| **Dead / delisted coin** | a coin the exchange has stopped trading. 339 of 864 USDT perps are dead |
| **Survivorship bias** | testing only on coins that still exist today. It flatters results, because the coins that crashed and died are left out |
| **Funding rate** | a payment between longs and shorts on a perp, settled every few hours (usually every 8h), that keeps the perp's price near the real coin's. When positive, longs pay shorts |
| **Settlement** | the moment a funding payment is made |
| **Exchange info / market record** | the exchange's list of what it trades and each coin's rules: smallest order, size step, contract size |
| **Contract size, step, minimum amount, minimum notional** | the units the exchange trades in; the smallest increment an order can change by (e.g. 1 LINK); the smallest order in coins; the smallest order in dollars ($5 on Bitget) |
| **Open interest (OI)** | the total size of all open positions in a coin's futures. Rising OI means new money entering |
| **Long/short ratio, "top traders"** | the share of accounts (or of position size) that is long versus short; "top traders" is the largest accounts |
| **Taker / maker** | a taker's order fills immediately against waiting orders; a maker's order waits in the book until someone trades against it. Takers pay higher fees |
| **Taker buy/sell ratio** | whether aggressive buyers or aggressive sellers dominated a period |
| **Order book / levels / L2** | the list of waiting buy orders (bids) and sell orders (asks) at each price. "50 levels" means the 50 nearest prices on each side. L2 is this list by price level |
| **Bid / ask / spread / mid** | the best buy price, the best sell price, the gap between them, and the halfway price |
| **Liquidation** | the exchange force-closing a leveraged position because the account can no longer cover its losses |
| **User-Agent** | the label a program sends to identify itself. OKX blocks requests that do not look like a web browser |
| **Coinbase premium** | the gap between bitcoin's price on Coinbase (mostly US buyers) and on Binance. A positive premium suggests US demand |
| **Fear & Greed index** | a daily 0–100 sentiment score for the crypto market |
| **On-chain data, MVRV, exchange net flows** | measurements read from the blockchain itself. MVRV compares bitcoin's market value with the value at which each coin last moved; net flows are coins moving into or out of exchanges |
| **Options, implied volatility** | options are contracts giving the right to buy or sell at a set price; implied volatility is how much movement their prices expect |
| **Token unlock** | a scheduled date when locked-up coins (held by founders or investors) become sellable |
| **Stablecoin supply** | how many dollar-pegged coins exist; a rough gauge of money waiting to buy |
| **Kimchi premium** | the extra price Korean exchanges (Upbit) sometimes pay for crypto |
| **Memecoin graduation, DEX** | a joke coin on pump.fun "graduates" when it raises enough to list on a decentralised exchange (DEX), where trading happens directly on the blockchain |
| **Prediction market (Polymarket)** | a market where people bet on real-world outcomes |
| **Regime / BTC gate** | the market's state, judged from bitcoin. The gate cuts risk to a quarter while BTC is below its 1000-hour average |
| **Moving average** | the average price over the last N bars, e.g. the last 1,000 hours |

### 3. Layer 2 — storage and caches

| term | meaning |
|---|---|
| **Cache** | a saved copy of downloaded data, so it is not downloaded again |
| **Gitignored** | kept out of the code repository on purpose (too big, or private) |
| **JSON, CSV, .csv.gz, parquet, pickle** | file formats: JSON and CSV are plain text; .gz is compressed; parquet is a fast column format for large tables; pickle is Python's own save format |
| **Panel** | a large table of many coins over many dates, built once and reused |

### 4. Layer 3 — data processing

| term | meaning |
|---|---|
| **Deduplicate** | remove repeated rows |
| **Stable sort** | a sort that keeps the original order of rows that tie. A non-stable sort once scrambled a log |
| **Halt / relisting** | a coin stopped trading and later restarted, often at a very different price. Its history is cut there |
| **Archive hole** | a gap in Binance's archive where data is simply missing, not a real halt. Two holes in 2022 once cut 51 coins by mistake |
| **Resample** | turn hourly bars into 4-hour, 12-hour or daily bars |
| **Bar label** | the timestamp a bar is filed under. Here a 4h bar is labelled with its END time, 3 hours after a trade inside it really began |
| **Look-ahead bias** | a backtest accidentally using information that was not yet known at the time of the trade. The most common way backtests lie |
| **Causal** | using only information available at that moment. The opposite of look-ahead |
| **Bar phase** | the hour a 4h bar starts on (00:00, 01:00, 02:00 or 03:00 UTC). A real result should hold on all four |
| **UTC** | world standard time. Every clock in the engine uses it |
| **Nanosecond (ns) timestamps** | storing every time in one unit. Mixing units once made a whole calculation silently return zero |
| **Point-in-time (PIT) universe** | the list of coins as it actually was each month, including coins that later died. Removes survivorship bias |
| **Top-N by prior month's volume** | each month's universe is the N most-traded coins of the month before, so nothing knows the future |
| **Half-open window `(a, b]`** | a time range that excludes its start and includes its end, so no payment is counted twice |
| **Indicator** | a formula on price and volume, e.g. an average or an oscillator |
| **EMA / SMA** | exponential and simple moving averages |
| **RSI** | Relative Strength Index, 0–100: how much of recent movement was up. Below 30 is "oversold", above 70 "overbought" |
| **ATR** | Average True Range: the average size of a bar's move over the last 14 bars. Used to set stop distances |
| **Bollinger Bands** | a moving average with bands a set number of standard deviations above and below it. A close outside a band is a "break" |
| **MACD, ADX, Donchian, efficiency ratio** | other standard indicators: momentum (MACD), trend strength (ADX), highest high / lowest low of N bars (Donchian), how straight the recent path was (efficiency ratio) |
| **SuperTrend, Ichimoku, PSAR, VWAP, Heikin-Ashi, ...** | indicators popular on TradingView. VWAP is the volume-weighted average price; Heikin-Ashi is a smoothed candle style |

### 5. Layer 4 — the simulation engine

| term | meaning |
|---|---|
| **Walk** | stepping through history one bar at a time and applying the rules as if live |
| **Entry at the next bar's open** | a signal seen at a bar's close is traded at the next bar's opening price, the earliest a real bot could |
| **Stop / stop-loss** | the price at which a losing trade is closed |
| **Trailing stop ("trail")** | a stop that follows price upward (for a long) and never moves back down |
| **Breakeven stop** | moving the stop to the entry price once a trade is far enough ahead |
| **Pyramiding / units / adds** | adding to a winning position in steps. Each addition is a "unit" |
| **Time stop** | closing a trade that has not made enough progress after a set number of bars |
| **Basis point (bp)** | one hundredth of a percent. 12bp = 0.12% |
| **Round trip** | buying and then selling (or the reverse): both fees together |
| **Pessimistic fill** | when it is unclear what happened inside a bar, assume the worse price |
| **Slippage** | the difference between the expected price and the price actually filled |
| **Trade row** | one simulated trade: entry time, exit time, result in R, coin, timeframe and so on |
| **Sleeve / timeframe** | the same rules run on a different bar size (1h, 4h, 12h). Each is a "sleeve" |
| **Slot allocator** | the part that decides which signals become positions when slots run out |
| **Tie-breaker / orderings / seeds** | when several signals arrive at once, which comes first changes the result. The engine tries 5–10 random orders ("seeds") and averages them |
| **Risk per unit (0.30%)** | each unit risks 0.30% of the account if its stop is hit |
| **Daily-sum / sequential / entry-sized compounding** | three ways of turning trades into an account balance. Only "entry-sized" (each trade sized from money already banked when it opened) matches what a real bot can do; the other two overstate returns about twice over |
| **Realised vs unrealised (mark-to-market)** | realised: profit from closed trades. Unrealised: paper profit on open trades at today's price |
| **Banked at close date** | a trade's result counts on the day it closes, not the day it opened |
| **Notional / gross leverage** | notional is a position's full dollar size. Gross leverage is all positions added up, divided by the account |
| **p99** | the 99th percentile: a value exceeded only 1% of the time |
| **10× guard** | a hard rule refusing any order that would take total positions past 10 times the account |
| **Intrabar** | what happened inside a bar, between its open and close |
| **%/month (hpm), CAGR** | average monthly return; compound annual growth rate |
| **Drawdown** | the fall from the account's highest point to a later low |
| **Hindsight haircut** | the 12-coin list was chosen knowing which coins did well, so its upside is divided by 3. Losses are not shrunk |
| **Regime returns** | results split by market type: rising (bull), falling (bear), sideways (chop) |

### 6. Layer 5 — the validation machinery

| term | meaning |
|---|---|
| **Validation** | checking that a result is real rather than luck or a bug |
| **Tune half / holdout half (60/40 split)** | design on the first 60% of history, judge on the last 40% |
| **Overfitting / data mining** | trying so many variations that one looks good by chance. A "mined-out" holdout has been used to judge so many ideas that it no longer proves anything |
| **Paired comparison** | comparing two versions on the exact same random ordering, so ordering luck cancels out |
| **Standard error (se), t-stat** | how uncertain an average is, and how many standard errors it sits from zero. A t above ~2 is unlikely to be luck |
| **Win count (e.g. 10/10)** | in how many of the orderings the new version beat the old |
| **Weekday anchor / rebalance day** | which day of the week a weekly strategy trades on. A result must hold on all 7 |
| **Matched-risk control** | checking whether the same gain could be had simply by betting bigger. If so, the "improvement" is just more risk |
| **Multiple comparisons, Holm correction** | when many ideas are tested, some pass by luck. Holm's method raises the bar for each test to account for that |
| **p-value** | the chance of seeing a result this good if there were really no effect. Small is good; 0.001 is one in a thousand |
| **Monte Carlo permutation test (MCPT)** | shuffling the price history many times and re-running the whole search. If shuffled data does as well, the result is not real |
| **Bootstrap** | re-sampling the results many times to see how much they could vary |
| **Out-of-period replication** | re-testing frozen rules on a different period never used, e.g. the 2018 bear market |
| **Registered prediction** | the expected result is written into the file before the test runs, so it cannot be explained away afterwards |
| **Forward test** | running on new data as it arrives. The only evidence that cannot be mined |

### 7. Layer 6 — the live execution engine

| term | meaning |
|---|---|
| **Poll** | one cycle of the bot: read prices, decide, send orders. Every 120 seconds here |
| **Warm start** | on restart, ignore signals from bars that closed before the bot came back, so it never buys at an old price |
| **Closed bar vs forming bar** | a closed bar is finished; the forming bar is the current one, whose prices are still changing |
| **One-way mode** | an exchange setting where each coin has one net position (long or short), not separate long and short positions |
| **Signed quantity** | a position size with a sign: +5 means long 5 coins, −5 means short 5 |
| **Demo routing** | the demo account lists only 3 coins, so every coin's order is redirected onto one of them by dollar value. It tests the order path, not the profit |
| **Symbol mapping** | translating a coin's name between exchanges, e.g. XRPUSDT on Binance → XRP/USDT:USDT on Bitget |
| **Market order / limit order / post-only** | a market order fills now at the best price available; a limit order waits at a chosen price; post-only is a limit order that is cancelled rather than filled immediately, so it always pays the lower maker fee |
| **Reduce-only** | an order that can only shrink a position, never open or enlarge one |
| **Flip** | going from long to short (or the reverse) in one step: close first, then open |
| **Precision / rounding to the nearest step** | order sizes must be whole multiples of the step. Rounding to the nearest (not always down) keeps sizes accurate |
| **InvalidOrder** | the error the exchange library raises for an order it cannot place |
| **Price sanity check** | refuse an order if Bitget's price is more than 3% from Binance's, which usually means the wrong coin was matched |
| **Cross vs isolated margin** | cross: the whole account backs every position; isolated: each position has its own small pot and is liquidated sooner |
| **Fill price, fetch_order** | the price an order actually executed at. Bitget does not report it with the order, so the bot asks again by order ID |
| **Disaster stop / trigger order** | an order resting on the exchange that closes a position if price moves 30% against it. A backstop if the bot or its machine dies |
| **Intrabar stop check / breach** | checking stops against the live price every poll, not just when a bar closes |
| **Market-neutral book, short leg, rebalance** | a book that holds equal longs and shorts so market direction matters little. The short leg is its shorts; rebalancing resets the holdings weekly |
| **Short squeeze** | a sharp price jump that forces shorts to buy back, pushing the price higher still |
| **Fill watcher, cap** | for resting limit orders: checks every 3 seconds how many have filled and cancels the rest once a set number has |
| **Modes: demo / dry / live** | demo: play-money orders; dry: no orders at all, a pretend ledger; live: real money |
| **ALLOW_REAL** | a switch in the code that must be changed by a person before real money can be traded |
| **Lock file, PID, single instance** | a file showing a bot is already running (with its process number), so a second copy refuses to start and cannot double every order |
| **Environment variable** | a setting held by the operating system rather than in a file. API keys live there, never in the code |
| **API key / secret / passphrase** | the credentials that let a program trade an exchange account |
| **IP whitelist** | restricting an API key to work only from named internet addresses, e.g. the server |
| **Atomic write** | write to a temporary file, then swap it into place in one step, so a crash never leaves a half-written file |

### 8. Layer 7 — records, reports and outputs

| term | meaning |
|---|---|
| **State file** | the bot's memory on disk: open positions, last bar seen, balance |
| **Log** | a running diary of what the bot did |
| **--status / --report** | commands that print the bot's current state, and the two-week check of whether its order path works |
| **PASS criteria** | what the two-week check requires: 14 days, no failed orders or stops, no errors, every fill priced, small slippage, and every kind of order seen at least once |
| **Self-check** | a script first reproduces a known result to the cent before it is trusted to produce a new one |
| **Status page (JSON)** | a read-only web page that shows the bots' state in a machine-readable format |

### 9. Layer 8 — deployment, operations and monitoring

| term | meaning |
|---|---|
| **VM (virtual machine), Azure** | a rented computer in a data centre; Azure is Microsoft's cloud |
| **vCPU, RAM, swap** | processor cores; working memory; disk space used as overflow memory when RAM runs out |
| **Region, geo-block** | where the data centre is; exchanges refuse connections from some countries (Binance blocks US addresses) |
| **systemd service** | Linux's way of running a program in the background, starting it at boot and restarting it if it crashes |
| **Restart policy, StartLimitBurst** | when to restart a crashed program; StartLimitBurst stops it after 3 crashes in 10 minutes so a broken bot waits for a human |
| **Hardening (ProtectSystem, ReadWritePaths ...)** | settings that stop a service from writing anywhere except its own log folder |
| **git pull deploy** | updating the server by downloading the latest code from the repository |
| **sha256** | a fingerprint of a file. If even one character changes, the fingerprint changes, so it proves the right file was deployed |
| **ssh** | a secure remote login to the server |
| **Run command** | Azure's web-page way of running a script on the server, used before ssh was set up |
| **Heartbeat** | a file the bot updates every cycle; if it goes stale, the bot has stopped working |
| **Wedged** | the process is alive but stuck: worse than dead, because it blocks a restart and is not managing trades |
| **Journal** | systemd's log of what a service printed |

### 10. Layer 9 — the test harness

| term | meaning |
|---|---|
| **Offline test** | a test that runs without the internet or an exchange |
| **Fake exchange (mock)** | a pretend exchange in memory that behaves like Bitget, so the bot's real code can be tested safely |
| **Regression test** | a test written for a bug that was fixed, shown to fail on the old code, so the bug cannot return unnoticed |
| **Mutation test** | deliberately breaking a rule in the code to check that the tests catch it |

### 11. The end result

| term | meaning |
|---|---|
| **Equity curve** | the account balance over time |
| **12-month outcome distribution** | how a year typically ends, how a bad year ends and how the worst year ends, measured across many start dates and orderings |

### 12. Known limits of the engine itself

| term | meaning |
|---|---|
| **Proxy** | a stand-in measurement used when the real one is unavailable, e.g. Binance prices for Bitget fills |
| **Liquidation model** | simulating the exchange force-closing positions. The backtester does not do this, which is why the 10× guard is a hard rule |
| **Live position model** | how the real bot handles positions (one per coin and timeframe, retries, a one-bar pause), which differs slightly from the backtest |

### 13. Where the budget held the engine back

| term | meaning |
|---|---|
| **Retail fee tier** | the standard fee ordinary customers pay. Big traders pay less |
| **Scalping** | very short trades, seconds to minutes, aiming at small moves. Fees eat most of the profit at retail rates |
| **Information coefficient (IC)** | how well a signal ranks the next price move: 0 means no relation, +0.1 to +0.2 is real but modest |
| **Co-location** | placing a trading computer in the exchange's own data centre so orders arrive in microseconds. Big firms do it; this project cannot |
| **Latency** | the delay between something happening and the bot reacting |
| **Funding-settlement race** | a price move right after a funding payment that lasts under a second; won by co-located firms |
| **Tick data** | every single trade, not bars |
| **Positioning data** | open interest and long/short ratios: who holds what |
| **Forward recording** | collecting data from now on, because no free history exists |

### 14. Paid sources that would make the engine better

| term | meaning |
|---|---|
| **CoinGlass** | a paid data service that collects liquidations, open interest, funding and long/short ratios from all the major exchanges |
| **Tardis.dev / CoinAPI** | paid services selling historical tick data and full order books for crypto exchanges |
| **Databento** | a paid market-data vendor for regulated exchanges such as CME, billed per download |
| **CME** | the Chicago Mercantile Exchange, the regulated US exchange where institutions trade bitcoin and ether futures |
| **Basis (CME vs Binance)** | the price gap between CME's bitcoin futures and the crypto exchanges' price. It shows how much institutions are willing to pay |
| **Aggressor side** | whether a trade was started by a buyer taking the ask or a seller hitting the bid |
| **MBO (market by order)** | the order book at its finest detail: every individual order, not just totals per price |
| **Snapshots + incremental updates** | a full copy of the order book, then every change to it, which together rebuild the book at any moment |
| **Tick / L2 replay** | re-running history trade by trade through the order book instead of by bars |
| **Queue position** | where a waiting limit order stands in line at its price; it fills only after the orders ahead of it |
| **Adverse selection** | limit orders tend to fill just before price moves against them, because the trader on the other side knew something |
| **Liquidation tests L1–L3** | three predictions written before recording began (`liq_rec.py`): L1, a burst of forced long sells in DOGE is followed by a bounce within 5 minutes; L2, market-wide liquidations do not predict DOGE's next 5 minutes; L3, changes in open interest do not either. Never tested: the recording day was too quiet |
| **Liquidation cascade** | forced sells pushing price down, which triggers more forced sells, and so on |
| **Capitulation** | a sharp sell-off in which many coins dump at once, often followed by a bounce |
| **R5** | a prediction in the order-book recorder (`book_rec.py`): no order-book signal leads to a move bigger than the 12bp fee over a minute or longer. Undecidable on one afternoon's data |
| **Decile** | a tenth of the data; the "top decile" is the 10% with the highest values |
| **VIP tier, maker rebate** | lower fee levels for high-volume traders; a rebate means the exchange pays makers for waiting orders instead of charging them |
| **VPS, matching engine** | a small rented server; the exchange's computer that matches buy and sell orders. A VPS near it cuts delay |
| **Flat files** | bulk data downloads as files, instead of request by request |
| **Personal vs commercial use tiers** | cheaper data plans allow only personal use; business use needs a higher tier |
| **Glassnode / CryptoQuant** | paid on-chain data services |

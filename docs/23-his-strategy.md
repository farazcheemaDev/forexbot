# 23 - The NASDAQ trader: everything we know about his strategy

*Written 2026-10-12. The readable summary of nine months of work. The lab notebook behind it, with every test in full,
is [`strategy_analysis/his_strategy.md`](../strategy_analysis/his_strategy.md); the section numbers (s16, s34 ...)
below point into it, and every number names the section or file that measured it. His name and account number are
in the gitignored statement files only and appear nowhere here.*

---

## 1. In one paragraph

He scalps a NASDAQ futures CFD at the broker **CapitalFX** on the **VertexFX Trader Pro** app. He sits down whenever
he is free, takes one to three trades, aims for about **+7 points** with **no stop**, and is usually out within a
minute or two. He wins **44 of 46** NASDAQ trades. The record is genuine, it was traded live, it is far beyond luck, and
it kept working on trades that did not exist when it was first measured. What makes him special is one thing only: **at
the moment he clicks, he knows which way NASDAQ will go over the next minute or so - he is right about 95% of the time
- and nothing in any market data we can obtain carries that knowledge.** His timing, his chart, his entries and the
moves that pay him are all ordinary. His side is not.

---

## 2. The record - real, live, not luck

| fact | number | where |
|---|---|---|
| statement | CapitalFX, 2026-01-01 .. 2026-10-12, 93 closed trades (91 + 2 in October) | s16, s48 |
| NASDAQ | **46 trades to September, 44 won (95.7%), +$3,130**; then 2 more on 2026-10-08, both won | s16, s48 |
| gold | 41 trades, 73% won, +$118 - and **no edge** (his gold entries win the race 51% vs 47% for nearby moments) | s16, s51 |
| account | ~11.5% a month on the capital held, **0 losing months in 9**, worst drawdown 10.9%, profit factor 4.71 | s16 |
| withdrawals | paid out of trading profit (profit covers 125% of what he withdrew) | s16 |
| the statement | genuine: downloaded by the user from the app; reconstructed to the cent | s16, s35b |
| **closed live** | the closing tickets follow the broker's live counter (~2,700 orders a day across all clients) in all 90 consecutive pairs; gaps between tickets track gaps in time (corr +0.99) | s53, `backtest/his_tickets.py` |
| **opened live** | the app's opening tickets for 20 trades: all 111 events (opens and closes) in counter order, 0 out of sequence; each open sits below its close by 1-52 tickets, growing with the hold - his entries were real-time decisions, not set afterwards | s57, `backtest/his_open_tickets.py` |
| **not luck** | he won most of his races on **22 of 23 trading days** (p 2e-5); for one random account to look this good, a manager would need ~47,000 accounts | s37 |
| **works out of sample** | January-March (measured later): 14 of 15; the two October trades: both won within 1-2 s; overall **38 of 43** | s35e, s48 |
| his clock | exact to the second (best shift 0 s against CME and Exness); before the EU clock change it reads UTC+4, after UTC+5 | s35, s51 |

---

## 3. His method, as far as it can be written down

**What he trades.** CapitalFX's NASDAQ contract named by month ("NASDAQ Mar / June / Sep / Dec") - priced off the real
CME NASDAQ futures on a quarter-point grid, ~207 points above the cash index in October (the futures premium). Mostly
market orders, not resting limits. (s39, s54)

**When.** Whenever he is free: 30 sittings in 8.4 months, 20 of them a single trade, first entry anywhere from 05:00 to
18:00 New York. **29 of 30 sittings ended in profit.** One sitting makes the month from May on. (s30)
- A quarter of his NASDAQ clicks fall in the first five minutes of an hour, mostly **11:00 New York** - not a release
  time. (s49, s50)
- About half his entries come **5-24 seconds after a 1-minute candle closes** (24 of 46, p 0.011), strongest on his
  follow-up trades: he watches the 1-minute chart and acts a few seconds after a candle. (s39, s44)
- His first trade of a sitting wins as often as the later ones - no outside alert calls him to the screen. (s44)

**The entry moment.**
- The market has **not** moved his way yet: median 0.00 points in the 5 seconds before his click. (s51)
- He enters on a **small pullback** against himself (~0.7 points in the 1-6 seconds before), in the better part of the
  minute but never at the exact low. (s34)
- He leans toward entering a little nearer a level from the last 15 minutes, with room ahead (rank 0.41 / 0.59). A
  lean, not a rule. (s55)
- His clicks are **not** at moments when a burst is likely (median 59th percentile of his own sittings). (s52)

**Which way.** This is the whole edge, and it is not in the price:
- he follows the prior move 44-59% at every horizon from 15 seconds to 30 minutes - neither a trend-follower nor a fader
  (s36); the 1-hour to 20-day trend agrees with him 43-63% (s39);
- at his moments, the best of 14 price-based side rules wins 57%; his side at other moments ~55%; **his moment + his
  side ~90%**. Neither half works alone. (s36)

**The exit.** A take-profit of about **+7 points** - median banked exactly 7.00, the same point targets repeat (he
watches points, not dollars) - and **no stop**. Winners are held a median **1.3 minutes**, losers a median 24 minutes
(the worst: -31.75 points for 48 minutes, one -$484 loss that cost about nine wins). On 2026-10-08 he exited by hand
instead (+15.5 at the previous low, +5.5 after 6 seconds). (s21, s46, s54)

**His own clock.** On Pakistan time (UTC+5, fixed all year) 74% of his NASDAQ trades fall in two evening windows,
~20:00-20:45 and ~23:15-00:15 - so the "11:00 New York" cluster is his routine, not a market event (s67).

**When he is stuck** (2026-09-14, the only overlap in the record): he adds lower, then scalps the other way while still
holding the loser, and closes it only once the opposite trades have paid for it. He also scratches trades that do not
go at +1..+3.5 points. Lot size and trade order carry no confidence: his side is equally good on every trade (s67).
As a bot on a coin-flip or trend side, this management loses on both halves (`backtest/his_manage_bot.py`).

**Size and target.** A median 0.07 lot, about $54 a win (s46) - but 60-180x the account in notional, so a NASDAQ point is
0.2-0.6% of the account, with no stop. He trades to a **~10% monthly target** ("around 10% is safer") and stops: June
was three trades on one day. So he needs only ~5 NASDAQ trades a month and can wait for the clearest moments. (s58)

---

## 4. What his edge looks like, measured

| measure | him | the same sittings' other moments | where |
|---|---|---|---|
| +7 before -7 (the "race") | **88%** (36 of 41) | 55% | s35e |
| +10 before -10 | majority on **25 of 26 days** | - | s35e |
| his side reaches +7 first on the mid price | **95%** (39 of 41) | ~50% | s52 |
| at +-2 to +-4 points | ordinary | - | s32 |
| time to +7 | median **29 s** | 33 s for any 7-point move | s52 |
| reached through a 5-second burst | 36% of his wins | 38% of any move | s52 |
| real NASDAQ futures between his two seconds | **+10.97 points his way**; he banked +8.96 (the broker kept ~2) | - | s42 |
| a copy placed 5 / 10 s late | won 98% / 100%, +6.6 / +7.0 points | gone by 20 s | s34, s47 |

So: **his moves are ordinary moves** - same speed, same shape as any 7-point move. **His edge is direction over the
next 1-5 minutes**, not the next few ticks, and it is decided before the market shows anything.

---

## 5. His own chart

Seen at last on 2026-10-12, through the user's VertexFX app (NASDAQ Dec, 1-minute, around his two October trades;
`backtest/his_chart_capfx.py`, s54). **It is the real market**: CapitalFX's candles sit a steady 207 points above
Exness's every minute (197-212) and the minute-by-minute moves correlate **0.992**. Nothing on his screen that the
market did not show.

What it showed him that afternoon (13:00-13:25 New York): a violent range, +-40-55 points a minute.
- **SELL 13:10:48** at 30,938.75 as a bounce stalled -> out 47 s later at 30,923.25, the low of four minutes before: +15.5.
- **BUY 13:17:55** at 30,928.75 on the retest of that low -> out 6 s later: +5.5.
- Held three minutes instead, the sell would have been about -60 points and the buy about -80.

---

## 6. What does NOT tell him the side - every test

Each one was run with predictions recorded first; "his moments" are compared with the other moments of the same
sittings.

| idea | result | where / file |
|---|---|---|
| price history, 15 s to 20 days; trend; fade | 44-63% agreement, nothing significant | s36, s39 `his_direction.py`, `his_direction_htf.py` |
| 1-minute candle patterns (13, incl. the forming candle) | best 2.09x, p 0.044, nothing survives Holm | s31 `his_1m.py` |
| indicators: EMA / RSI / Stochastic / MACD / Bollinger; smart-money concepts | ordinary | s30 `his_ta.py` |
| key levels (day's open, yesterday's H/L/C, first 15 min, round numbers) | ordinary; median 37 points away | s34 `his_keylevels.py` |
| micro-levels (last 15 minutes' high / low, retests) | a lean (rank 0.41), no side; as a rule = random | s55 `his_retest.py` |
| 75 features in one model | 0.505 / 0.486 on unseen days (0.50 = luck); the same pipeline finds a planted pattern at 0.72-0.96 | s33 `his_model.py` |
| **a RARE chart setup at his selectivity** - 16 years of minute bars, the model's top 0.05% most confident calls | ~55-58% before the spread; his entries ordinary to it, side agreement 40% | s58 `ndx_aplus.py` |
| volume profile: point of control, value area (yesterday's and developing), six classic reads | 41-55% agreement; as rules = random | s59 `his_volprofile.py` |
| CME NASDAQ futures trade tape (aggressor side) | 48-55% agreement | s37 `his_tape.py` |
| CME order book, 10 levels | ordinary (one cell was a tie artifact, corrected) | s38, s44 `his_book.py` |
| absorption (flow that fails to move the price) | 38-63%, nothing | s53 `his_absorb.py` |
| futures-cash gap | 50-60%, nothing | s40 `his_basis.py` |
| bonds, S&P, Russell, euro, yen, gold, oil futures (1-second) | one cell of 32, chance | s44 `his_crossfut.py` |
| the 8 biggest NASDAQ stocks, the dollar, bitcoin | ordinary | s32 `his_generals.py` |
| **QQQ options flow (0DTE)** - 297,508 trades | 38-55% agreement, no predictive value | s53 `his_options.py` |
| bursts (following, predicting, a straddle around them) | bursts foreseeable in time, not direction; every bot = random | s51, s52 `ustec_burst*.py` |
| economic calendar, any currency; surprises; first reactions | nothing survives Holm | s28, s43, s50 `his_calendar.py`, `his_hour.py` |
| Fed speakers, the Chair, Trump's speeches and posts | at chance | s28, s29 `his_posts.py` |
| live headline wires (4 Telegram channels) | 0.48-0.88x the control in the 15 s before | s49 `his_headlines.py` |
| the top of the hour / the hourly candle | his hour is not a release; the hourly-candle rule wins 49-51% | s50 `his_hour.py` |
| his broker lagging the market | no lag (best shift 0 s); his fills neutral at entry, worse at exit | s34, s42 `his_fills.py` |
| his record built after the fact | no - live ticket counter | s53 `his_tickets.py` |
| his own chart differing from the market | no - 0.992 | s54 `his_chart_capfx.py` |

---

## 7. Mistakes found and fixed along the way

Every one of these pointed toward an explanation of him, and every one was the measurement:
- **the winter clock** - January-March read as "his broker's prices were not the market's"; the statement's clock was one
  hour different before the EU clock change (s35);
- **ticket numbers** read as opening order - they are closing-deal tickets (s39);
- **a 1-second artifact** read as "he banks more than the market moves" (s42);
- **a tie-ranking bug** that manufactured "bonds go quiet before his clicks" and a "thin queue on his side" (s44, s53);
- **a parser bug** that split prices wrongly (s21); an early "level fade" thesis and a "trigger" both retracted (s15, s20);
- **"VertexPro"** was the app, not the broker - both statements are CapitalFX (s53).

---

## 8. What this means for our own bot

**What we can take from him, and it is real:**
- **NASDAQ is where a short-horizon edge can live** - his works there and not on gold.
- **The trade shape**: a fixed ~7-point target, quick exits, sitting only when attentive, leaving each sitting green.
- **Size on the worst move, not the average one**: with no stop, the tail decides survival (s47 - one -31.75-point
  loser cost nine wins; at the other moments of his sittings the 99th-percentile adverse move is 149 points).

**What we cannot take:** his side. Every source a bot can read - prices, ticks, candles, levels, indicators, the CME tape
and book, options flow, other markets, news, headlines, his own chart - has been tested, and none carries it. The trade
shape without his side is a coin flip that pays the spread: every rule built from his habits lost about 2 points a
trade on 181 days of real prices (s52, s55).

**Measured facts about following him, for the record** (not a recommendation): a copy 5-10 seconds late keeps his
edge (s34, s47); sized so a 1-in-100 adverse move costs a quarter of $221, it would earn about $14 a month (s47).

---

**The final audit (s68).** ES leading NQ by 1-5 s, pulled ("spoof") liquidity before his clicks, and a sub-second
latency scanner were each tested and closed (`backtest/his_loopholes.py`, `his_cancel_proxy.py`). The mended version
- his +7 and pullback with a hard stop and an order-flow side - loses the 2.16-point spread at every stop
(`backtest/his_mended.py`). A side must win 63% at a -10 stop (72% at -15) for a Sharpe of 2; nothing measured is close.

## 9. What is still unknown

- **What tells him the side.** His entries and exits were both placed live (s53, s57), he is right ~95% of the time about
  the next minutes, and that accuracy is far beyond anything public data carries: everything tested here, including the
  CME order book, tops out around 55-60% at his moments (s56). So it is most likely a private live source - a caller, a
  room, someone's order flow - or a judgement no measurement has captured.
- **CapitalFX's ticks inside the minute.** Only its 1-minute candles have been seen (s54). VertexFX is not MetaTrader,
  so its ticks cannot be pulled the way Exness's were.

---

## 10. Files

| file | what |
|---|---|
| `strategy_analysis/his_strategy.md` | the full lab notebook, s1-s55 |
| `strategy_analysis/statement_trades.csv`, `his_statement_2026-10_trades.csv` | his trades (gitignored: name and account number) |
| `backtest/his_*.py`, `backtest/ustec_burst*.py` | every test, each with its predictions and RESULT in the docstring |
| `logs/his_*.txt` | each test's output |
| `strategy_analysis/data/` | Exness ticks, CME and options data (gitignored: licensed data) |

# 25 - The sentiment engine: design and build plan

*Written 2026-10-16. The user: "a top-tier sentiment analysis tool, with the weight each news item gets and how it
should impact markets - then we see how to integrate it into the bot for more control of our trades".*

---

## 1. The principle that makes it "top tier"

Most sentiment tools score text as positive / negative and stop. That number alone has not helped this book: Fear &
Greed as a size dial **lowered** the return per unit of risk on both halves (`sentiment_dial.py`), and macro headlines
are priced within about one second (`fx_news_seconds.py`). What makes a sentiment tool worth trading on is the second
half: **for each kind of news, from each source, how much did the price actually move afterwards, how fast, and how
reliably** - measured on history, with the last part of it held back. So in this engine:

- **The weight of a news item is not chosen by hand. It is learned** from thousands of past items and the price moves
  that followed them.
- **"How it should impact markets" is an expected move with a confidence**, per category, per horizon (1 minute to 3
  days) - and an honest note of how much of that move is gone before we could act.

## 2. The pipeline

```
 COLLECT            ENRICH                          SCORE                         LEARN (offline)          USE
 news, posts,  ->  which coin(s), what kind of  ->  tone -1..+1, weight     ->   event studies:          ->  dashboard,
 positioning       event, new or repeat,            = learned impact x           item -> price move          then (only if
                   how big the source               confidence x novelty         after it, by category,      it passes) veto /
                                                                                 source, horizon             size rules in the bot
```

### 2a. Collect (live and history, every item with its timestamp to the second)

| source | gives | history for learning | access |
|---|---|---|---|
| **Telegram public channels** - crypto headline wires (e.g. Watcher.Guru, Tree News, Wu Blockchain, CoinDesk, Cointelegraph, Binance / exchange announcement channels; probed for which exist) | the fastest headlines | **yes - back months / years** (`his_headlines.py` already reads them) | public pages, read through the VM |
| **Exchange announcements** (Binance, Bybit, OKX, Coinbase listings / delistings / monitoring tags) | the events that move single coins most | yes | public pages / feeds |
| **Reddit** (r/CryptoCurrency, r/Bitcoin, coin subreddits) | crowd mood, attention per coin | recent only (live from now) | official API, free app key (yours) |
| **Bluesky** | crowd mood (the crypto crowd that left X) | recent / live | open API (an app password from a free account, yours) |
| **X sentiment, legally** | social volume and mood per coin, aggregated | yes (theirs) | Santiment / LunarCrush free or cheap tiers (optional, yours) |
| **CryptoPanic, GDELT** | news volume and tone | GDELT yes (2017-) | free |
| **Positioning** | funding rates, open interest, long / short ratios, liquidations | yes (Binance archives) | public, no key |
| **Fear & Greed, FXSSI retail ratios** | market-wide mood | yes / recording | free (already used) |

### 2b. Enrich

- **Which coins** each item is about (tickers, names, $CASHTAGS, contract mentions), and "market-wide" if none.
- **What kind of event** - a fixed list, classified by rules first and a model second: exchange listing, delisting /
  monitoring tag, hack / exploit, regulation / lawsuit, ETF / institutional, macro data, Fed / rates, partnership, token
  unlock, whale / treasury transfer, liquidation cascade, rumour, price-only commentary.
- **New or repeat** - the same story re-posted by 20 channels is one event, not 20 (clustering by text similarity in a
  time window). The FIRST timestamp is the one that counts.
- **Source size and record** - followers / reach now; how often its past items preceded a real move (learned, 2c).

### 2c. Score and LEARN the weights

- **Tone**: a finance / crypto-tuned open model (FinBERT or a CryptoBERT variant from Hugging Face, run on the PC), plus
  rules for the event types where tone is obvious (a hack is negative for that coin).
- **The impact table** (the heart of it), from event studies on history: for every past item, the linked coin's move
  **against BTC** (abnormal return) at +1 / +5 / +15 / +60 minutes, +4 h, +24 h, +3 days, from Binance 1-minute data;
  averaged by **event type x source x tone**, with shrinkage toward zero for small groups, fit on the older 60% of
  history and checked on the newest 40%.
- **Each live item's weight** = its category's learned expected move x the category's reliability (how consistent the
  move was) x novelty (first report vs repeat) x source record.
- **Latency is measured, not assumed**: for each category, how much of the move is left after 10 s, 1 minute, 5
  minutes - the time a retail bot actually needs. A category whose whole move happens in the first second is shown as
  "priced before you can act".

## 3. What it can do for the bot ("more control of our trades")

Only categories that pass - a move after realistic delay that is bigger than fees, on both halves of history - become
inputs, and only as **controls**, tested through the harness like everything else (`mended_harness.py`, the out-of-sample
run, `oos1719.py`'s method):

| control | example | why this kind first |
|---|---|---|
| **veto** | no new long in a coin for 24 h after a hack, exploit or delisting / monitoring-tag announcement; capit2 does not buy a "capitulation" that is really a delisting | avoiding a known disaster is easier to prove than predicting a gain, and the repo's books do not know about these events at all |
| **exit early** | close a position in a coin after a credible negative event in that coin | cuts tail losses |
| **size tilt** | smaller new positions while market-wide panic is in its first hours | only if it beats betting smaller (the bar every brake here has failed) |
| **new entries** | trade a category's drift directly (e.g. post-listing moves) | the hardest bar: a stand-alone book; tested last |

## 4. What to expect, honestly (from this repo's own tests)

- Market-wide mood (Fear & Greed, attention) **predicts next week's direction a little but did not help as a size dial**
  (`sentiment.py`, `sentiment_dial.py`).
- Macro news is **priced in about a second** (`fx_news_seconds.py`), and its drift after the first minutes is ~0
  (`fx_surprises_1m.py`).
- So the most likely value is in **coin-specific events** (listings, delistings, hacks, unlocks) where moves continue
  for hours or days, and in **vetoes** that keep the books out of a coin that is about to collapse. That is where the
  engine's first test should look.

## 5. Build phases

| phase | what | needs from you |
|---|---|---|
| **A. History** | pull past headlines from public Telegram crypto channels and exchange announcements (through the VM, read-only, as `his_headlines.py` does); Binance 1-minute klines for the coins they mention | your OK for the downloads (below) |
| **B. Enrich + tone** | coin linking, event types, de-duplication, the tone model | OK to download the model (~0.5 GB) |
| **C. The impact table** | event studies, latency curves, the learned weights; registered predictions first; a report of which categories carry a move a bot can still catch | - |
| **D. Live engine** | collectors running on the PC (the VM has 66 MB free), scoring each new item as it arrives, storing to SQLite; feeds the dashboard (doc 24) | Reddit app key, Bluesky app password, optional Santiment / LunarCrush keys - all created by you, kept in environment variables, never in chat or the repo |
| **E. Into the bot** | each passing category tested as a veto / exit / tilt in the harness and out of sample; adopted only if it passes; the bot change is a code change you approve, like every other | your decision per rule |

## 6. Downloads phase A-B needs (asking before any of them)

| what | from | size (estimate) |
|---|---|---|
| past headlines, ~10-20 crypto news channels | t.me public pages, read through the VM | small (tens of MB of text) |
| exchange announcement archives | Binance / others' public announcement pages | small |
| Binance 1-minute klines for the coins mentioned, ~2 years | data.binance.vision (public, same archive as `spot_fetch.py`) | ~1-2 GB |
| a finance / crypto tone model | Hugging Face (FinBERT / CryptoBERT) | ~0.5 GB |

X itself is not scraped (its terms forbid it, and the working tools need logged-in accounts and get around its bot
protection); its mood comes in through Santiment / LunarCrush, which license it.

## 7. What the engine found, 2026-10-16 .. 2026-10-23 (the record; every number names its file)

The user, 2026-10-23: "we need to make better sentiment analysis tool ... add all the good stuff, also work on getting
news from X". Everything free was measured on history first. In one line: **coin-specific exchange news and the crowd's
positioning carry information; chatter, tone and general news do not.**

| source | file / log | verdict |
|---|---|---|
| Binance adds_products + monitoring tags | `news/impact.py`, `news/combo.py` | **the edge** - short the coin / long BTC, +267..+316bp a trade; running as the news book on the VM (paper) |
| the same notices, split by exchange | `news/impact_by_source.py`, `logs/news_impact_by_source.txt` | little new: Binance adds_products strongest (-952bp at 7d); new SPOT listings drift down on every venue (-350..-540bp at 7d, one usable: BWEnews) but only cover a thin coin's cost; delistings and unlocks nothing |
| general news by FinBERT tone | `news/tone.py`, `news/market_minutes.py` | dead - good and bad news barely differ; BTC does not move even in the headline's minute |
| crowd positioning (long / short accounts) | `news/positioning_hist.py`, `logs/positioning_hist.txt` | **a LEAD** - long the coins the crowd is most short, short the most long: +37% / +48%/yr (Monday / Thursday), t 1.8-2.0, under the bar; ~40% funding, the rest squeezes; mostly 2025-26; corr +0.19 with carry |
| top traders' accounts / positions, OI change | same | nothing that passes (top_acc rides the crowd's lead; top_pos and OI lose) |
| aggressive (taker) flow | same + `logs/positioning_taker_follow.txt` | real but small IC (+0.05..+0.06, momentum); no book either way (-10..+7%/yr) |
| Bluesky chatter and tone, 25 coins | `news/bsky_hist.py`, `logs/bsky_hist.txt` | dead - attention IC -0.007, tone flips between halves, crypto-wide attention vs BTC -0.03 |
| X / Twitter | - | no free legal feed: the official API is paid, LunarCrush's social data ~$90/month; scraping refused. Bluesky's null makes paying for X hard to justify |
| Fear & Greed, Wikipedia attention | `sentiment.py` era, doc 02 2026-10-05 | weekly momentum, but lowers Sharpe as a size dial |

**The live readout: `news/mood_now.py`** (read-only, public Binance endpoints, ~10 s; once a month ~30 s to rebuild the
universe). Per coin of the backtest's universe (the top 40 by the prior month's volume, listed >= 30 days - the crowd
book's own universe, `wide_book.eligibility`): crowd long %, its rank, funding annualised, taker buy / sell, OI 7d, and the
crowd book's quarters flagged (SQUEEZE WATCH = most short; crowd long = most long). Market line: Fear & Greed, the median
coin's long share, the share of coins paying shorts, BTC's crowd ratio. The live endpoints were checked against the
archive the backtest used (BTC crowd 1.0239 vs 1.0237 at 2026-10-21 23:50; SOL taker 1.0812 vs 1.0812).
`tests/test_mood_now.py`: 3 tests, 3 mutations caught. **Information, not a trade signal** - doc 22 freezes new books;
the crowd book needs its own paper record before it could be one.

**Not built, waiting on the user:** the AI headline reader (needs the user's own Anthropic key in an environment
variable and a model choice); the readout on the dashboard (a VM change: dashboard_push.py would call
`mood_now.snapshot()` hourly, not every minute - ~120 Binance calls a read).

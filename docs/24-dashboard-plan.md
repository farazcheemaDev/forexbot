# 24 - The live dashboard: implementation plan

> **Built since this was written (see CLAUDE.md s10, 2026-10-17 onward).** The design changed: instead of a PC-hosted page
> fed over ssh, `dashboard_push.py` runs on the VM (`forexbot-dash.timer`, every minute) and feeds a web app in
> `dashboard/`. What is running is in [`STATUS.md`](STATUS.md); the text below is the original plan.

*Written 2026-10-16. A plan, not built yet. What it is for: watching the bots work live - every trade, every book, every
day - plus a sentiment panel and a "how well is it doing against what we expected" scorecard.*

---

## 1. What you will see

One page, opened in the browser on your PC (and later on your phone):

| panel | what it shows | refresh |
|---|---|---|
| **Account** | equity of each paper book (final machine, combo, pair, crash bids, the seven blend books), today's P&L, all-time | 1 min |
| **Live trades** | every order as it happens: coin, book, side, size, price, slippage, why it was placed ("CAPIT2 BUY", "trend add", "MN rebalance") | 1 min |
| **Open positions** | each position with entry, live price, open P&L, its stop / target, how long it has been held | 1 min |
| **Risk** | gross leverage now against the 11.5x cap, the worst-hour estimate if the market fell like 2025-10-10, distance to liquidation | 1 min |
| **Calendar** | a heat-map of days (green / red) and months, with each day's P&L by book | daily |
| **Scorecard ("how well did it do")** | each book's live result against its backtest: the percentile it sits at, win rate, average trade, live vs expected - the honest "is it working" panel | daily |
| **Market mood** | BTC regime (above / below its 1000h and 42-day averages), breadth, Fear & Greed, funding, long/short ratios, retail positioning, crypto news / Reddit sentiment | 30 min |
| **Health** | each VM service up / down, restarts, last poll, poll errors, disk / memory | 1 min |
| **Alerts** | a list of everything notable: a fill, a stop, a book down X%, a service restarted | live |

Everything is **read-only**. The dashboard never sends an order and never holds an exchange key.

## 2. Where it runs, and why

**On your PC, not the VM.** The VM has 66 MB of free memory (`free -m`, 2026-10-16); a dashboard server would push the
bots into swap. So:

```
VM (bots, unchanged)  --- ssh, read-only, every 60 s --->  PC: sync folder  --->  PC: dashboard (browser)
```

- A small **sync job** on the PC copies the bots' state and log files from `/opt/forexbot/logs/` over the existing
  `ssh forexbot-vm` connection (read-only; it never writes to the VM).
- The **dashboard** reads that local copy and serves a page on `http://localhost:8501` - visible only on your PC.
- **Phone access later** (phase 5): Tailscale (a private network between your PC and phone, free for personal use) -
  never by opening a port to the internet.

## 3. The data is already there

The bots already write everything the dashboard needs. Nothing in the bots changes for phases 1-2.

| file on the VM (`/opt/forexbot/logs/`) | what it holds | panel |
|---|---|---|
| `combo_bot_dry_final/combo_exec.csv` | every order of the final machine (dry), with price and reason | Live trades |
| `combo_bot_dry_final/combo_final_trades.csv` | closed trades of the daily / capit2 / carry books | Live trades, Scorecard |
| `combo_bot_dry_final/combo_marks.csv`, `combo_mn.csv`, `combo_sleeve.csv` | daily marks per book | Account, Calendar |
| `combo_bot_dry_final/combo_paper.log` | the bot's own log lines (signals, refusals, stops) | Alerts |
| `combo_state.json`, `combo_marks.csv` | the combo paper book (machine v2) | Account |
| `blend_state*.json` + trade logs | the seven blend books | Account (via `rebuild_equity.py`'s CORRECTED equity, never the recorded one - CLAUDE.md s7b) |
| `pair_paper_state.json`, `pair_paper_trades.csv` | the pair + capit2 shadow book | Account, Live trades |
| wick paper ledgers | crash bids, Bitget and Binance | Account |
| `combo_bot_demo/` | the demo bot on Bitget's demo exchange (real order fills) | Live trades, Health |
| `systemctl`, `journalctl` | services, restarts, errors | Health |

The backtest side - what each book is *expected* to do - comes from the repo: `final_confidence.py`,
`combo_window.py`, `final_capit2_lev.py`, `oos1719.py` (their distributions are saved once as a small file the
scorecard reads).

## 4. "Learning from its outcomes" - what that should mean here

This needs to be said plainly, because it is where most bots lose their money.

**What it will NOT do: change its own rules automatically after wins or losses.** This repo measured that exact idea:
`backtest/doge_adapt.py` re-picked the best of 228 rules every 6 hours from the recent past and lost at every window;
`doge_focus.py` did it monthly on 134 strategies and lost; `month_regime.py` (2026-10-16) found a monthly signal that
helped on 2017-19 and hurt on 2020-26. A bot that tunes itself on its last few weeks is fitting noise, and it does it
with real money.

**What it WILL do - learning that is safe:**

1. **Record every outcome with its context.** Each closed trade is stored with what the market looked like when it was
   opened (BTC regime, breadth, volatility, Fear & Greed, funding, the signal's own reading). This becomes a growing
   live dataset nothing else can give us.
2. **Score itself against its own backtest every day.** For each book: where its live result sits in the backtest's
   distribution of same-length periods (the method of `combo_window.py`). Green = inside the normal range, amber =
   bottom 10%, red = bottom 5% for two checks in a row.
3. **Find what is working and what is not.** Weekly, automatically: live win rate and average trade per book and per
   market regime, against the backtest's numbers for the same regime. "capit2 is winning 9 of 10 as expected" or "the
   daily book has lost 6 in a row in chop - its backtest says that happens 1 time in 12".
4. **Propose, never apply.** When the live data suggests a change (for example: capit2 back to 1x - see `oos1719.py`),
   the dashboard shows it as a **proposal** with the evidence. It is tested through `backtest/mended_harness.py` /
   the out-of-sample run first, and a human applies it. The record of every proposal and its test result is kept.

That is how the bot gets better from its outcomes without quietly over-fitting to last week.

## 5. Sentiment: what is possible, and what it costs

| source | how | cost | notes |
|---|---|---|---|
| **X / Twitter** | official API | **Basic tier ~$200 / month** for read access; the free tier is effectively write-only | more than the whole trading account; scraping it breaks X's terms. **Not recommended.** |
| **Reddit** (r/CryptoCurrency, r/Bitcoin, coin subreddits) | official API, free tier (100 requests / min with an app key the user creates) | free | posts and comments per coin; scored for tone |
| **Crypto news** | CryptoPanic API (free tier) and GDELT (free, already used in `fx_news_tone.py`) | free | headline volume and tone per coin |
| **Fear & Greed** | alternative.me (already used, `sentiment.py`) | free | daily |
| **Funding rates, long / short ratios, open interest** | Binance / Bitget public endpoints (no key) | free | the market's actual positioning - usually more useful than tweets |
| **Retail positioning** | FXSSI (already recorded by `sentiment_rec.py`) | free | forex / indices / BTC; the recorder needs to be restarted to collect history |
| **Google Trends / Wikipedia views** | public | free | attention; Wikipedia already tested (`sentiment.py`) |

**Tone scoring**: a small open sentiment model on the PC (e.g. a finance-tuned model such as FinBERT, or a simple
crypto word list to start) scores each post / headline -1..+1; the panel shows per-coin and market-wide mood, volume of
talk, and changes against the last 7 days.

**What the repo already knows about sentiment as a trading signal**: Fear & Greed and attention predict the next week
a little, but as a size dial they **lowered** the return per unit of risk on both halves (`sentiment_dial.py`). So the
sentiment panel starts as **information on the screen**, recorded from day one. It becomes a trading input only if,
after months of recording, it passes the same test as everything else (the harness, both halves, out of sample).

## 6. Alerts to your phone

A Telegram bot (free; you create it with @BotFather and keep its token on the PC, in an environment variable - never
in the repo or in chat) sends: every fill, every stop, a book entering the bottom 10% of its backtest range, a service
restart, gross leverage over 10x, and a daily summary at a fixed time. Each alert type can be switched off.

## 7. Build phases

| phase | what | effort | depends on |
|---|---|---|---|
| **1** | sync job + dashboard skeleton: Account, Live trades, Open positions, Health | 1-2 sessions | nothing - files already exist |
| **2** | Calendar, Risk panel (gross leverage, worst-hour estimate from `liq_stress.py`'s method on the live positions), Scorecard against the backtest bands | 1-2 sessions | phase 1; one script to save the backtest distributions |
| **3** | the outcome recorder (context with every closed trade), the weekly "what is working" report, the proposals list | 1 session | phase 2 |
| **4** | sentiment recorders (Reddit, news, F&G, funding / long-short, FXSSI) on the PC + the Market mood panel | 2 sessions | a Reddit app key from you (free) |
| **5** | Telegram alerts; phone access through Tailscale | 1 session | a Telegram bot token and a Tailscale account, both yours |

**Tools**: Python on the PC; Streamlit for the page (quickest to build, auto-refreshes, good tables and charts) -
or FastAPI with a small HTML page if a lighter, faster page is wanted later. Data stays as the bots' own CSV / JSON plus
a local SQLite file for the sentiment and outcome history.

## 8. Rules the dashboard keeps

- Read-only towards the VM and the exchanges. No keys in the dashboard, ever.
- Books compared by CORRECTED equity (`rebuild_equity.py`), never by the blend books' recorded equity.
- Every number on the screen says where it comes from (file, or script) - rule 7 of CLAUDE.md, applied to the page.
- Nothing on the dashboard can change a bot's settings. Changes stay in the code, tested, committed, and deployed as
  they are today.

## 9. Decisions needed from you before building

1. **Twitter/X**: skip it (recommended - $200 / month), or pay for Basic access.
2. **Reddit**: create a free Reddit app key (you do it; I explain the steps) - or start without Reddit.
3. **Alerts**: Telegram yes / no.
4. **Phone access**: now (Tailscale) or later.

Phase 1 needs none of these and can start immediately.

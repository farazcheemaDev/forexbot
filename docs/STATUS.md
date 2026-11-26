# STATUS - what is true right now

**2026-11-26 - THE DAY-45 CHECKPOINT WAS READ AND IT IS A KILL** (doc 22 s3b; audit of 2026-11-26, read-only, nothing deployed or restarted). The main account's live equity at 2026-11-23 00:04 UTC was **$224.29** (`logs/dashboard/eq_main_h.csv` on the VM, nearest hourly point 2026-11-22 23:59:47) against the line **$261.30**: **$37 under it. No real money for this machine**; the paper bots keep running for the record and the funding question stays closed until a NEW pre-registered test reopens it (doc 22 s3b). Numbers at 2026-11-26 18:50 UTC (feed + `verify_status.sh`): **main $219.96 live (-26.7%, 1.7th percentile of the backtest band = "worse"), $198.29 booked (-33.9%)**, biggest booked fall 34.9%; **fresh $184.80 live (-38.4%, 1.2th percentile), $179.17 booked**, biggest fall 44.3% booked; **machine v2 (`combo_paper`) $120.17 (-45.6%)**; pair 8,197 PKR (-18.0%); crash bids Bitget +0.75% on 130 fills, +0.24% each (expected +0.8..+1.0). **Where main's -$80 went (booked + open):** market-neutral -$42.9, daily Bollinger -$35.1, bear sleeve -$9.2, trend -$3.8 (48 long trades 0 won, -60R; 66 shorts 30 won, +17.5R; open shorts +$22), NASDAQ dip -$2.6, bids -$0.4, fees -$5.0; carry +$9.9, news +$6.9, capit2 +$2.0. **The audit found no code or dashboard error behind it** (every dashboard number recomputed from the raw state and Binance; trend 106 of 114 live trades = the backtest rule's, daily / capit2 / MN rules reproduce; the 12 core bot / feed test suites run clean) - see CLAUDE.md s10, 2026-11-26. **Two real defects found:** (1) the **carry book has held nothing since 2026-11-13 on main (fresh: since 2026-11-07)** because `final_books.py:459` skips a whole equal-weight basket when `K_CARRY x equity x 0.5 / n` is under Bitget's $5 minimum - the one book making money switches itself off as the account shrinks, and the scorecard still reads "on track"; (2) `backtest/live_check.py`'s MN check builds its universe from today's 24h-volume pool, not the bot's monthly pool, so its "V3 MN WRONG" (40-78% overlap) is the check's artefact - the bot's own code on the bot's own November pool reproduces the logged baskets exactly. Fresh's own read is 2026-12-01 (does not decide).

**Verified 2026-11-22 10:58 UTC** (after the market breadth recorder went live, `3d0f49e`: every service and timer active incl. the new `breadth-rec.timer`, the VM's tracked files unmodified; main **$223.66 live - $37.64 under the day-45 line** (read 2026-11-23 00:04 UTC), fresh $183.98; the main bot's 'restart pending' the known one) with `bash deploy/verify_status.sh`. Before it: **Verified 2026-11-09 ~09:35 UTC** (after the forward ledger + Leads tab went live, `847b4bc`: main **$261.50 live - $0.20 over the day-45 line** (read 2026-11-23 00:04 UTC), every service file the same as local HEAD) with `bash deploy/verify_status.sh`. Before it: **Verified 2026-11-08 18:18 UTC** (after the RSI-80 momentum paper book went live, `c33bed7`: main $273.88 live - $12.58 over the day-45 line, read 2026-11-23 - fresh $247.11, every service and timer active incl. `rsi80-paper.timer`, the main bot's 'restart pending' the known one) with `bash deploy/verify_status.sh`
(read-only: the VM over ssh, plus local git) at 11:36 UTC, and an independent audit of the dashboard feed at 12:00 UTC (every headline number recomputed from the bot's raw state, the trade logs, the backtest bands and Binance: it reconciles).
**origin/main and local main are two commits ahead of the VM** (2026-11-22, both research only - nothing that runs, so the VM does not need them: at the user's word 'push', the four final forensic tests on the NASDAQ trader - his_strategy s105-s108, four study scripts in `backtest/`, their logs, the notebook, doc 23 s9b, this file's breadth note and CLAUDE.md; before it, at 'yes push it', the research backlog - study scripts, their tests, result logs, the picture book of his trades and the docs; rebuildable `logs/*.pkl` caches stay local by `.gitignore`). **The VM is at `3d0f49e`** (2026-11-22 ~10:52 UTC, at the user's word 'start recording the market breadth from now on vm': `breadth_rec.py` + its test + `deploy/breadth-rec.{service,timer}` + `verify_status.sh` listing the timer; the VM fast-forwarded from `e79dec5`, 14 bot / book files byte-identical, nothing restarted, the recorder's 7 tests pass there, the timer enabled - first daily run 2026-11-23 02:00 UTC - and a 29-day backfill by hand at 10:53-10:59 UTC: 20 trading days stored, 2026-10-26 .. 11-20, 100 stocks a day - EA and WBD no longer trade - 16 MB; Yahoo's 1-minute data has a hole on 2026-11-05 12:11-13:36 New York for every stock). Before it: `e79dec5` (2026-11-15 ~16:20 UTC, at the user's word 'yes, fix it' after asking "are you sure 'with market mood' means not good?": re-checked, the mood makes NO money difference on the replay (ideas with and against it reach the target equally often; the '+4 points' was the random baseline), so the Analyst tab grades on stop size and price position only ('Has room' / 'Skip'), the mood is a neutral context chip, the pick is the newest idea with room again, and analyst.py's amendment carries a same-day correction (docstring only); the VM pulled it, 12 bot files + the feed byte-identical, nothing restarted, desk tests 36 pass there). Before it: `258c764` ( 2026-11-15 ~13:50 UTC, at the user's word: the Analyst tab opens on ONE clear signal - the coin and direction, a grade (Best setup / Weaker setup / Skip from the stop size, whether the price is still between stop and target, and the market's mood) with its reasons, entry / stop / target / reward-to-risk, the order in four numbers; placing steps and the leverage table folded; every open idea graded in one table; the record in one line; the explanation moved into 'Full details'; the top tab bar now scrolls inside itself instead of widening the page - page + styles + `sizepanel.gradeCall` only, the VM not touched). Before it: `1a4f9d7` (2026-11-15 ~13:16 UTC, at the user's word 'deploy it': the Analyst desk records each call's market state (BTC label, fuel, the median alt's 30-day move from `logs/mood/mood.json`) and tags it with or against the market's mood, a dated amendment and a REGISTERED forward test (`lean_test`, calls from 2026-11-15 14:00 UTC, 30 bets of each lean), the feed carries both, the pick prefers 'against' (`backtest/analyst_states.py`: following the state made the desk's replay calls worse; against it +3.7 / +3.8 points of hit rate, post hoc, still losing); the VM fast-forwarded from `847b4bc`, 12 bot files byte-identical, no service restarted (the desk and the feed run on timers), tests 36 / 45 pass on the VM, a desk cycle in a temporary folder read BTC chop / fuel LOW / alts -33.5%; Vercel 'Deployment has completed'). Before it: `6c06925` ( 2026-11-15 ~11:02 UTC, at the user's word 'deploy it': the size panel shows the profit and loss as a % of the margin locked, on the ticket and on every row of the leverage guide - five dashboard / test files, page + styles + logic only, so the VM was not touched; Vercel 'Deployment has completed' 11:02 UTC). Before it: `847b4bc` (2026-11-09 ~09:27 UTC, at the user's word 'yes, deploy it': the forward ledger `backtest/forward_ledger.py` (PC only) with the three pinned study files it replays, and the dashboard's **Leads** tab (`dashboard_push.leads`, `Dashboard.js`, `globals.css`, `fmt.js`); the VM fast-forwarded from `f491caa`, all 13 bot files byte-identical and every service's start time unchanged, nothing restarted, feed tests 44 pass on the VM, the feed builds 11 Leads rows; `logs/leads/ledger.json` copied to the VM over ssh (sha256 equal); Vercel 'Deployment has completed' 09:27:07 UTC). Before it: `f491caa` (2026-11-08 ~21:16 UTC, at the user's word 'yes, check sooner': the RSI-80 paper book's timer moved from :05 to 30 seconds after each 4h close - nothing booked changes, only the logged 'seen' price; a dated amendment in `rsi80_paper.py`; the dashboard's next-check follows; the VM pulled it, the timer file reinstalled (next 00:00:30 UTC), 12 service files byte-identical, nothing restarted, the open JCT trade untouched). Before it: `ff4d621` (2026-11-08 ~18:29 UTC, at the user's word 'add it to the dashboard': a **Momentum book** tab for the RSI-80 paper book - `dashboard_push.momentum()` (balance with open trades at live prices, open and closed trades, the record against its registered lines, the curve) + the tab in `Dashboard.js` + `rsi80-paper.timer` in the page's health list; the VM pulled it (12 service files byte-identical, nothing restarted; the feed job picks it up each minute, 0 errors); Vercel 'Deployment has completed' 18:29:46 UTC. Before it: `c33bed7` (2026-11-08 ~18:17 UTC, at the user's word 'yes, record it': the RSI-80 momentum PAPER book - `rsi80_paper.py` + its test + `deploy/rsi80-paper.{service,timer}` + the doc 22 override (`7ac483c`), a Python 3.10 fix caught by the VM's own test run before anything was installed (`5f40d3e`), and `verify_status.sh` listing its timer (`c33bed7`); the VM fast-forwarded from `f921ca8`, 12 service files byte-identical, nothing restarted; the timer enabled after one run by hand at 18:16 UTC (the November universe ranked: top 100 of 516 perps; 100 coins checked, no signal). Before it: `f921ca8` (2026-11-08 ~16:11 UTC, at the user's word 'deploy it': the Analyst desk makes no XAUUSDT / QQQUSDT call while gold or the US stock market is shut - `analyst.py` `market_open` / `can_call` + the dashboard's 'coming' preview + their tests; a dated amendment in the desk's docstring. The VM fast-forwarded from `3cd87d8` (the range also brought the page-only commits below, which the VM does not serve); 12 service files byte-identical, no service restarted (the desk and the feed run on timers); tests 31 / 36 / 8 pass on the VM; a desk cycle run there in a temporary folder logged 'market shut, no calls: XAUUSDT QQQUSDT' and drew all 7 symbols' levels). Before it: origin/main was at `3b38602` (2026-11-08 11:24 UTC by the GitHub status clock, at the user's word: the Analyst tab in three blocks - what the desk is and its edge in plain words, 'Signal now' with the order and a five-step 'How to place it', and one closed 'Full details' button; page + styles only; the VM was not touched; Vercel redeployed). Before it: `c4231db` (2026-11-06 22:39 UTC, the leverage list with a 'Use Nx' button on each row), `cdf5440` (22:26 UTC, the order ticket with a suggested leverage), `c5030fd` (21:45 UTC, the panel opens on the bot's single pick in plain words), and `af5d6e7` (2026-11-06 17:55 UTC, the size panel itself; Vercel redeployed 17:57 UTC). The VM is at `3cd87d8` (deployed 2026-11-06 17:40 UTC at the user's word: the Analyst tab's sweet-spot card, a feed block and a dormant read-only wallet reader; before it `80e0ff1`, the display fix); neither deploy touched a service file (12 service files byte-identical before and after each, nothing restarted; Vercel redeployed; the VM's feed builds the new `analyst.sweet` block, 6 open calls tagged, the forward test reads 0 of 30 bets). **Section 1's account rows were refreshed today from the feed (11:36 UTC); the sections after
section 1 were NOT re-verified today** and may be stale (they were last verified on 2026-10-27).
**This is the one page that says what is running, on which code, with what result and under which gate. Where another
page disagrees with it, this one wins.** It goes stale the day something is deployed, started, stopped or a date below
passes: re-run the script (section 8) before trusting a number here that is more than a few days old.

**No real money is in anything.** `ALLOW_REAL = False` in all three bots that could place a real order
(`combo_bot.py:80`, `longtrend_bot.py:91`, `micro_bot.py:102`, checked). Only the user changes that. Every figure below
is labelled **BACKTEST** (what the rules did on history, never a forecast) or **PAPER** (a forward record, no orders).

---

## 1. Where it stands

### The machine being judged: the final machine (`combo_bot.py --mode dry --final`)

Trend (triple, 12 coins), market-neutral momentum/RSI, bear sleeve, funding carry, daily Bollinger, capit2 (2x), news,
NASDAQ dip-buy and a crash-bid ledger, netted on one virtual $300 account. No orders, no keys.

| | |
|---|---|
| **BACKTEST** (`backtest/final_machine.py`, DEPLOYABLE line) | A typical 12 months turns $300 into **$3,400** (6 years) / **$4,735** (last 2 years). **Worst month -30%, deepest fall 60% / 51%, about 4 months in 10 lose.** Trend gains are shrunk 3x for hindsight and its losses kept whole; the holdout is mined (CLAUDE.md s2); it earns little in sideways markets. The 2026-10-22 execution fixes add roughly +19% / +12% to the typical year (`machine_fixes.py`); the news and NASDAQ books came after this line was drawn and are not in it. |
| **PAPER, main account** (since 2026-10-09 00:04 UTC, **day 28**) | **$236.56 live (-21.1%, 4.7th percentile of the backtest range = "worse", under the 5th)**, $239.98 booked (-20.0%), biggest fall so far 22.7% (booked). Booked P&L: trend -$29.90, market-neutral -$30.07, carry +$11.63, daily -$15.71, crash-bid ledger +$1.12, NASDAQ dip +$5.87 (and -$11.50 open), fees -$2.97. Today (11-06) -$13.73: AIN fell 62% (held long in two books), QQQ -$11.50. **The machine alone - no crowd book** (kept so on purpose: the day-45 line was set for it). |
| **PAPER, fresh account** (since 2026-10-17 01:15 UTC, day 20) | **$210.11 live (-30.0%, 1.8th percentile = "worse")**, $271.94 booked (-9.4%), biggest fall 20.5% booked (35.6% from its $326 peak live). Booked P&L: trend -$25.12, market-neutral -$6.75, carry +$27.26, daily -$15.32, crowd -$6.52, crash bids +$1.14, fees -$2.77. Today (11-06) -$49.13: an AKE short bounced 130% from yesterday's close (-$20), AIN -62% (-$17), QQQ -$13. Carries the crowd-squeeze book at x1.0 since 2026-10-25; its scorecard leaves that book out. |
| **Gate that applies** | **READ 2026-11-23 00:04 UTC: $224.29 live, under the line = KILL (top of this page).** The paragraph below is the state of 2026-11-06, before the read. **Day-45 KILL line (doc 22 s3b): the main account's live equity under $261.30 at 2026-11-23 00:04 UTC.** On 2026-11-06 the live $236.56 is $24.74 under it (+10.5% needed in 17 days). Backtest windows that looked like main now (day 28, -21% +-3: 595 windows from 38 start blocks): 46% were over the line at day 45, 76% above their start by day 180, 99% by day 365 (backtest-conditional). Fresh's read is 2026-12-01. The fund decision is 2027-04-09 (section 4). |

"Live" is booked equity plus open P&L (the dashboard's number, and the one the day-45 rule reads); "booked" is what the
status command prints.

### The other books (all PAPER; none can be funded before its own date)

| Book | Since | Paper result today | What the BACKTEST says | Judged |
|---|---|---|---|---|
| **Machine v2** (`combo_paper.py`, $221) | 2026-09-24 | day 32: **$158.75 (-28.2%)**, biggest fall 28.5%; trend -$44.48, market-neutral -$17.23. Day 30: $154.22 (-30.2%) = **1.6th percentile of the backtest's BULL-start 30-day windows** (`logs/combo_window_30d.txt`; registered guess 1st-2nd, right) | typical 12 months $1,210 (6 yrs) / $1,125 (last 2) on $221, deepest fall 59% / 45% (`max_mix.py`, CLAUDE.md s6) | month-3 check about 2026-12-24 (the 5th-percentile kill line applies from then, and it is already under it); verdict 2027-03-24 |
| **Crash bids** (`wick_paper.py`, two $300 ledgers) | 2026-09-25 | Bitget +1.90%, 63 fills at +1.21% each (expected +0.8..+1.0); Binance +1.61% on 60 | +16%/yr alone (docs 16-17) | 6 months (2027-03-25) *and* 60+ Bitget fills: the fills are in, the time is not |
| **The pair + capit2 shadow** (`pair_live.py`, PKR) | 2026-10-08 | 8,775 of 10,000 PKR (-12.3% at 21:05 UTC on 10-26; 14:23: 8,426; 10-25: 8,639; 10-24: 8,835). Capitulation: 9 closed, 67% won, +2.58% avg. **Daily book: 6 closed, 0 won, -20.5% avg**, 5 open. capit2 shadow: no signal yet | +51%/yr median, falls 25-34% (`pair_books.py`) | capit2 shadow: 30 closed trades or 2027-10-08 |
| **Crowd-squeeze** (`news/crowd_paper.py`, $300) | 2026-10-23 | $299.24, its first week (21 legs) opened at the Mon 10-26 anchor, none closed yet (Thu 10-29 next) | +37% / +48%/yr, t 1.8-2.0: a lead, not a pass (`news/positioning_hist.py`); 26-week band p10 -6.5%, median +18.4% | KILL checkpoint 2027-01-25 (under -7.8%); verdict 2027-04-09 (dead under -6.6%, held up at +16.8% or more) |
| **Analyst desk** (`analyst.py`, $300) | 2026-10-26 22:45 UTC (the user: "deploy it") | $297.03 live / $296.77 booked at 2026-10-27 14:00 UTC: 8 calls, 6 resolved, 1 right (17% vs 37% for a random entry), and those 6 are only **2 bets** under the amended test; **its history replay says to expect about -3% a week** (`backtest/analyst_replay.py`: 10,580 calls over 4.7 years, 18% right vs 31% needed, -0.20R each; the desk's own 0.5%-risk book ends ~$0; the whole account at 10x / 20x / 30x is wiped out) | none expected: every chart-rule test in doc 02 is dead after fees; the desk is the user's idea measured forward | 100 resolved calls or 2027-01-31 (`analyst.py` docstring, doc 22 override); **since 2026-10-27 13:56 UTC its p counts same-day, same-direction calls as one bet**; **since 2026-11-08 ~16:11 UTC (`f921ca8`) no gold / QQQ call while their market is shut** (a post-hoc fix: those calls were about two-thirds of its live loss; `backtest/analyst_replay_cuts.py`) |
| **Seven trend books** (`blend_paper.py`, from $221) | 2026-09 | CORRECTED equity: main $383.75, tight $416.82, sized $363.50, short-boost $383.75, tstop $421.89, units $457.68, triple $463.48 (`rebuild_equity.py`, every self-check MATCH) | triple +10.43%/mo holdout with the 10x guard, hindsight-shrunk, on a mined holdout (CLAUDE.md s2) | research books, no verdict date. **Compare them only by CORRECTED equity** (s7) |

---

## 2. What is running where

**Azure VM** (`/opt/forexbot`, up 5 weeks 6 days, disk 9%, memory tight: ~160 MB available of 896 at 14:00 UTC on 10-26, ~76 MB free on 10-25). All checked active.

| Unit | What | Started (UTC) |
|---|---|---|
| `combo-bot-final` | main account, final machine, dry | 2026-10-22 21:53 (account clock from 10-09) - NOT restarted since, on purpose (section 3) |
| `combo-bot-fresh` | fresh $300 account, the current code **+ `--crowd`** (the crowd book inside) | **2026-10-25 16:59** (account from 10-17; state backed up to logs/backup_20261025-165930) |
| `combo-paper` | machine v2 | 2026-09-29 16:28 (account from 09-24) |
| `blend-paper` | the seven trend books | 2026-09-23 20:47 |
| `wick-paper` | crash bids, Bitget + Binance | 2026-09-25 05:17 |
| `pair-paper` | the pair + capit2 shadow, hourly | 2026-10-16 01:05 |
| `crowd-paper.timer` | crowd-squeeze book, hourly; since 2026-10-27 its mood snapshot also carries the trend-book FUEL gauge (`news/mood_now.fuel`, display only; the dashboard's mood card shows it) | deployed 2026-10-23 (book from 16:38) |
| `analyst-paper.timer` | the Analyst desk, hourly at :07 (paper only, public Binance candles, no keys; writes `logs/analyst/`; MemoryMax 120M) | 2026-10-26 22:45 UTC (first run by hand, then enabled; next 23:07) |
| `rsi80-paper.timer` | the RSI-80 momentum paper book, 30 seconds after every 4h close (00:00:30, 04:00:30 ... UTC; :05 until 2026-11-08 21:16 UTC) (paper only, public Binance futures candles and funding, no keys; writes `logs/rsi80/`; standard library, MemoryMax 120M) | 2026-11-08 18:16 UTC (first run by hand, then enabled; next 20:05) |
| `breadth-rec.timer` | the market breadth RECORDER, daily at 02:00 UTC (record only: the Nasdaq-100 stocks' 1-minute bars from public Yahoo chart data -> TICK / ADD / VOLD / TRIN-style breadth per minute, a proxy of the exchange indices; no keys; standard library, MemoryMax 150M; writes `strategy_analysis/data/breadth/`) | 2026-11-22 ~10:52 UTC (enabled; a 29-day backfill by hand: 20 trading days, 2026-10-26 .. 11-20; first daily run 2026-11-23 02:00 UTC) |
| `forexbot-dash.timer` | dashboard snapshot, every minute | 2026-10-17 |
| `status-server` | small HTTP status page | 2026-09-13 |

**The PC** runs one thing: `poly_forward.py`, the Polymarket snapshot collector (data only; the Polymarket ideas are
dead, docs 08 and 02).

**The forex bot** (`forex_bot.py`, NASDAQ noise momentum on Exness USTECm, demo-only) was BUILT 2026-11-03 and is **not running anywhere**: nothing has traded and no orders have been placed. Starting it (`--mode dry` first) is the user's call; it needs the MT5 terminal logged into the demo and the PC awake 19:30-02:00 Pakistan time. CLAUDE.md s4 / s10 and doc 02's last entry have its design, checks and expectations.

**Not running, and why:** `combo-bot-demo` (the Bitget DEMO order-path test) was stopped 2026-10-17 after 191 orders,
all filled and priced, 0 order or stop failures; its verdict stayed "not yet" only for two Bitget network blips.
`mn_paper.py` is dead (and carries the funding bug, CLAUDE.md s7b). The old PC runners (`longtrend_*`, `xs_paper`,
`crypto_*`) are gone. The DOGE live test, order-book recorders and TradingView session stopped 2026-10-09;
`sentiment_rec.py` and the meme collector are not running now.

**The dashboard**: the VM side is verified (the timer fires every minute and writes the equity feed). The web app on
Vercel lives outside this repo's runtime and was not checked.

---

## 3. Code identity

- **The VM is at `62ca3a2` since 2026-10-27 14:00 UTC** (fast-forward from `ae96a46`: `analyst.py`, its test, one dashboard line and docs only - the Analyst
  desk's verdict test now counts same-day, same-direction calls as one bet; tests 26 + 13 + 14 pass on the VM; no service restarted - the desk's timer and the
  feed's timer load the file at each run; Vercel "Deployment has completed" 14:00:48 UTC). The bullet below is the 10-26 deploy, kept as history.
- **The VM was at `ae96a46` from 2026-10-26 22:45 UTC** (fast-forward from `a100fa2`, no modified tracked files; tests 24 + 13 + 14 pass on the VM; the Analyst desk, its units, the dashboard tab and the two older commits below came with it; `blend_paper.py`, `combo_paper.py`, `combo_bot.py`, `final_books.py`, `wick_paper.py`, `wick_live.py`, `pair_live.py`, `news_books.py`, `news/crowd_paper.py` are byte-identical to the commit before; no service was restarted). **The paragraph below is the state at `a100fa2` and is kept as history:** (`9873966` changed only two dashboard files, the top-bar "Fuel" label, which run on Vercel; the commits
  after it are research, docs and logs, plus the two older ones below - none of them is a bot or paper-book file, so the VM needs nothing except the label fix). The VM pulled `a100fa2` 2026-10-27 02:01 Pakistan = 21:01 UTC on 10-26, no modified tracked files. That commit is the
  trend-book fuel gauge only (`news/mood_now.py`, `news/fuel_bands.json`, a line in `dashboard/app/Dashboard.js`, tests, `backtest/convexity.py`):
  every bot and paper-book file was byte-identical before and after (checked blob by blob), no service was restarted. Two OLDER commits (the Polymarket scan and
  the dashboard's short-exit label fix, the user's earlier "not yet") were pushed to GitHub on 2026-10-27 with everything else, but the VM was NOT pulled to
  them: it does not have `dashboard_push.py`'s label fix until the next `git pull` there (the user's call; nothing auto-pulls).
- **The paper-book files were byte-identical before and after that pull:** `blend_paper.py`, `combo_paper.py`,
  `wick_paper.py`, `pair_live.py`, `news_books.py`, `news/crowd_paper.py`. So the pre-registered books are unchanged.
- **The two final-machine bots now run DIFFERENT code, on purpose.** `combo-bot-fresh` was restarted on `a0da49c`: the
  crowd book (`crowd_book.py`, `--crowd`) and the 2026-10-24 real-order pieces (in dry mode only the coin map matters:
  1000PEPE / 1000SHIB / RAYSOL and the other renamed coins now enter its ledger as PEPE / SHIB / RAY). `combo-bot-final`
  (main) still runs the code it started with on 10-22 (`7148366`), so `verify_status.sh` prints "restart pending" for it
  - expected: main stays the machine the day-45 line was set for. If it restarts by itself (Restart=always) it loads
  the new files WITHOUT `--crowd`: same books, plus the coin map in its ledger.
- **Do not read that as "the execution improvements are not running".** The 2026-10-22 ones **are**, on both final-machine
  bots: capit2 filled as a resting limit against the 1-minute lows (`capit2_poll`) and the crash-bid ledger (`bids_poll`,
  a "BIDS ..." line every hour in the bot's log) since 2026-10-22 20:36 UTC, and Wilder ATR with the prior-month coin
  universe since 21:53 UTC. What does not exist on the VM is the *venue* path (`capit2_orders`, the real crash desk, the
  coin map): a paper bot has no use for it, a real account would. Checked on the VM, 2026-10-25.
- **Each long-running service is running the code now on disk** (the script asks git what the files it runs held at the
  service's start time and compares with now; file times lie after a `reset --hard`). The two timers start a fresh
  process on every run, so they always use the current files.
- **Configuration that matters in the final machine** (from its own status line): trend guard 6.25x, account cap 14.5x
  (paper only; reconsider before real money), capit2 at 2x.

---

## 4. The real-money gate

Doc 22 (written 2026-10-10, before the data; it cannot be moved after seeing a record) says money may go in only if
**all five** hold on the verdict date:

| # | Condition | State |
|---|---|---|
| 1 | Return at or above the 25th percentile of same-regime backtest windows | not judged (2027-04-09) |
| 2 | Beats "hold BTC only while above its 1000-hour average" over the same days | not judged |
| 3 | Tradable at the capital to be used: under 10% of orders below the venue minimum | not judged; Bitget's smaller coin list moves the machine -9% / +17% (tune / holdout), no consistent cost (`bitget_coverage.py`) |
| 4 | The PKR -> USDT -> exchange -> PKR path tested, its true cost written down | the real P2P and fee figures are not in doc 22 yet (the demo bot tested the order path, not this) |
| 5 | No open bug in CLAUDE.md s7b touches the book | judged at the verdict |

**Size is x1.0**, the user's decision of 2026-10-24. Plan on falls of 40-60% along the way (the backtest's deepest) and
a worst month near -30%. After a day-45 CONTINUE, a funded account also needs: withdrawals only above the starting
stake, and the month-3 kill line applied to the real account (doc 22 s3b).

---

## 5. Dates

| Date (UTC) | What | Source |
|---|---|---|
| 2026-10-26 (opened, 21 legs each), 10-29 | crowd book's first Monday / Thursday anchors - the standalone book and the one inside fresh | `news/crowd_paper.py`, `crowd_book.py` |
| **2026-11-23 00:04** | **main account day-45 KILL read: live equity under $261.30 = kill** | doc 22 s3b |
| 2026-12-01 01:15 | fresh account read beside it (does not decide) - read WITHOUT its crowd book (equity minus the book's P&L, open P&L and fees; the dashboard's scorecard figure) | doc 22 s3b |
| about 2026-12-24 / 2027-01-09 | month 3 of v2 / of the final machine (derived): 5th-percentile kill line starts | doc 22 s3 |
| 2026-12-31 | research stops (only the trader route stays open) | doc 22 s5 |
| 2027-01-25 | crowd book KILL checkpoint | doc 22 s4, `crowd_bands.json` |
| 2027-03-24 | v2 verdict | doc 22 s1 |
| 2027-03-25 | crash-bid 6-month mark | `wick_paper.py` |
| **2027-04-09** | **final machine verdict (fund / kill / extend); crowd verdict; code freeze ends** | doc 22 s1, s4 |
| 2027-10-08 | capit2 shadow deadline (or 30 closed trades) | doc 22 s1 |

Until 2027-04-09 the code is frozen: bug fixes and deployment fixes only, each logged in CLAUDE.md s10 (the crowd paper
book is the one logged override).

---

## 6. Waiting on the user

- **Real-order pieces on the VM.** In origin/main since 2026-10-24, not deployed. Deploying means restarting the two
  final-machine bots and putting the coin map into their dry ledgers, which is a code change during the freeze (doc 22
  s4), so it is the user's call. The paper record does not need it.
- **Which exchange**, Bitget or Binance, if it ever funds: deferred until the bot performs (Binance lists every coin the
  books use but has $20-$50 minimums on BTC, ETH, LINK, LTC and BCH; Bitget lists 91 fewer coins and has a $5 minimum).
- **The P2P / fee figures** for doc 22 condition 4, whenever the user wants that item closed.
- **The Analyst desk is LIVE on paper** (deployed 2026-10-26 22:45 UTC at the user's word: `analyst.py` + `desk.py`, `analyst-paper.timer`, the dashboard's "Analyst desk" tab, a leverage / capital what-if card). It is a separate $300 paper book outside main and fresh (doc 22 override 2026-10-27) and touches no bot. **Expect it to lose: its own replay over 4.7 years says -0.20R a call, about -3% a week, and the whole account at 10x / 20x / 30x wiped out** (doc 02, last entry). Its review is at 100 resolved calls (about two and a half weeks at the replay's call rate) or 2027-01-31; retired if the average result after fees is not above zero or the hit rate is no better than the random-entry baseline. **Amended 2026-10-27 13:56 UTC (6 calls resolved, before any verdict): the test counts calls made the same UTC day in the same direction as one bet** - the 7 markets move together, and one move stopped four of its shorts within 21 minutes; the old per-call p stays on the record. **Amended 2026-11-08 ~16:11 UTC (`f921ca8`, after looking at 95 resolved calls): no XAUUSDT / QQQUSDT call unless the real market is open at the run and at the start of the candle read** (gold Sunday 18:00 - Friday 17:00 New York less 17:00-18:00 daily; QQQ 09:30-16:00 New York; US holidays to 2027-12). Applied to the record it blocks 15 calls (1 win, -16.6R) and leaves 80 at -9.7R (about the fee): it stops a leak, it does not create an edge. Its 4.7-year replay also says the 'sweet spot' (stops >= 0.8%) loses -0.11 / -0.15R a call, so expect the registered forward test to fail. Check: `./.venv/bin/python analyst.py --status` on the VM, or the dashboard's Analyst desk tab.
- **The RSI-80 momentum book is LIVE on paper** (deployed 2026-11-08 18:16 UTC at the user's word 'yes, record it': `rsi80_paper.py`, `rsi80-paper.timer`). A separate $300 paper book outside main and fresh (doc 22 override 2026-11-08); touches no bot. Long the top-100 USDT perps (prior month's volume) when the 4h RSI(14) crosses up through 80; stop 4 ATR, target 4R, out after 24 bars; 1% of the booked equity at risk; real funding. **Backtest: a narrow no-pass on unseen data** (`backtest/rsi80_more.py`: +0.14R a trade, t 1.80; carried by a few burst weeks) and **not the trend book again** (`backtest/rsi80_overlap.py`). Registered lines in its docstring: KILL 2027-01-31 (30+ trades, mean under -0.24R); verdict 2027-04-09 (held up at +0.072R with the account above $300, dead under -0.107R, otherwise extended to 2027-10-09). A five-month record can only catch a clear failure. Check: the dashboard's **Momentum book** tab (since `ff4d621`), or `./.venv/bin/python rsi80_paper.py --status` on the VM.
- **The market breadth recorder is LIVE** (deployed 2026-11-22 ~10:52 UTC at the user's word 'start recording the market breadth from now on vm': `breadth_rec.py`, `breadth-rec.timer`, `3d0f49e`). It records; it does not trade. Why: 1-minute breadth (TICK / ADD / VOLD) is the one public scalper tool not properly tested on the NASDAQ trader (his_strategy s69 had Nasdaq TICK on 5-minute bars, 12 trades). The exchanges' breadth indices are vendor data, so it computes the same measures from the Nasdaq-100 stocks' own 1-minute bars - a PROXY, to be said wherever it is used. Use: score his next statement's trades against it in the regular session. **It cannot explain s74's 04:38-05:00 New York pre-market wins, so do not weight it for them** (his_strategy s108, `backtest/his_drift.py`): at those three clicks on 2026-11-12 only 10-20 of the ~100 stocks printed in a minute (median 14; regular session 98) and Yahoo's pre-market bars carry no volume (VOLD 0, TRIN empty) - before 09:30 New York the proxy has almost nothing to measure. Check: `./.venv/bin/python breadth_rec.py --status` on the VM; the log is `strategy_analysis/data/breadth/breadth_rec.log`.
- **The trend-book fuel gauge is LIVE** (deployed 2026-10-27 at the user's word: VM pulled to `a100fa2`, tests pass on the VM, one mood snapshot
  written and seen in the feed payload, Vercel reported "Deployment has completed" for the commit). Display only; no book reads it. It reads
  LOW (5% of the top-40 running, median coin -19% in 30 days). **Where to see it:** a "Fuel LOW" label in the top bar of EVERY tab (next to the BTC
  price; added in `9873966` after the first version showed it only on the Mood tab, which the user did not find) and the full line on the Mood tab.
  The trend book has no fuel for an explosive month, which the machine's backtest
  says is normal and lasts a while (doc 02, last entry). It does not change the day-45 line.
- **The forex bot is built, not started.** `python forex_bot.py --mode dry` (no orders, 10 trading days, check `--report`), then `--mode demo`. Real money has no path in release 1 and stays out of scope; expect about +$20 a year on $300 in the best honest case and read it by doc 22's rule, never by a good-looking month.
- **The forward ledger and the dashboard's Leads tab are LIVE** (deployed 2026-11-09 ~09:27 UTC, commit `847b4bc`, the user: "plan the farm" -> "yes, build it" -> "yes, deploy it"). Each PC run's `logs/leads/ledger.json` reaches the VM by ssh copy (`ssh forexbot-vm 'cat > /opt/forexbot/logs/leads/ledger.json' < logs/leads/ledger.json`; the user agreed to this route with the deploy). Built:
  `backtest/forward_ledger.py` (PC only: three leads re-run on data after 2026-11-09 00:00 UTC, pinned by hash; tests 10, 22 of 22 planted bugs; parity
  with all three studies in `logs/forward_ledger_check.txt`) and `dashboard_push.leads` + the Leads tab (every forward record in one list; tests 44,
  17 of 17 planted bugs; compiled with the VM's Python 3.10; previewed locally on the VM's real feed, desktop and 375 px). Deploying needs the user's
  word: commit and push, VM `git pull` (feed only, no restart), and a way for `logs/leads/ledger.json` to reach the VM after each PC run.
- Nothing else waits on the user until 2026-11-23.

---

## 7. Reading these numbers

- **Backtest is not paper is not real.** Backtest trend gains are shrunk 3x for hindsight with losses kept whole
  (CLAUDE.md s6); 12bp round-trip fees; a mined holdout. Paper has no real fills at all.
- **Equity has two bases.** "Live" = booked + open P&L; "booked" = what `--status` prints. The day-45 rule reads live.
- **The seven trend books' recorded equity is overstated** (by $85-$322 each on 2026-10-24). Use `rebuild_equity.py`'s CORRECTED column.
- **The VM's paper bots do not carry the 10-24 coin map**, so a few coins (`RAYSOL`, `1000PEPE`, `1000SHIB`, `BTR`, `SAGA`,
  `BULLA`) show as "unmapped" in the ledger: their P&L counts on paper, and a live Bitget account could not place them
  without the map.
- **`combo_paper` (v2) has no market-neutral short-leg exit**, by pre-registration; the final-machine bots do.
- **`blend_paper.py` uses a simple-mean ATR**; the final-machine bots use Wilder's, as the backtests do (CLAUDE.md s10,
  2026-10-22). The seven trend books keep the offset.

---

## 8. Keeping this page true, and where to read next

**Update this page in the same session as anything that changes it** (a deploy, restart, start, stop, a gate date
passing, a new paper book), and re-stamp the "Verified" line. To re-verify in about 30 seconds:

```bash
bash deploy/verify_status.sh
```

It reads only; it restarts nothing. For the corrected equity of the seven trend books, add
`ssh forexbot-vm 'cd /opt/forexbot && ./.venv/bin/python rebuild_equity.py'`.

**Reading order for a new session:** [`CLAUDE.md`](../CLAUDE.md) (rules, traps, safety gates; its s10 is the dated
log) -> this page -> [doc 22](22-decision-rule.md) (the gates) -> [doc 02](02-what-failed.md) and
[doc 21](21-graveyard-audit.md) before proposing anything. The full index is [`docs/README.md`](README.md).

**Dated snapshots - do not use them for current state:** [doc 00](00-current-state.md) (2026-09-23),
[doc 09](09-pick-up-here.md) (2026-10-09), [doc 24](24-dashboard-plan.md) (a plan; the dashboard is built since).

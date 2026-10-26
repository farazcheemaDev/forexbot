# STATUS - what is true right now

**Verified 2026-10-26 21:05 UTC** (2026-10-27 02:05 in Pakistan) with `bash deploy/verify_status.sh` (read-only: the VM over ssh,
plus local git), the day after the fresh account got the crowd book (section 2); section 1's account numbers were refreshed
from the dashboard feed (`dashboard_push.py --print`) at 14:23 UTC; at 21:05 UTC main was $248.77 live (-17.1%), fresh $272.31 (-9.2%). v2's percentile is from 2026-10-24
(`backtest/combo_window.py --days 30`).
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
| **PAPER, main account** (since 2026-10-09 00:04 UTC, **day 17**) | **$254.82 live (-15.1%, 8.4th percentile of the backtest range = "below")**, $253.20 booked (-15.6%), biggest fall so far 15.2% (booked). Booked P&L: trend -$25.91, market-neutral -$9.00, carry -$8.59, daily -$8.66, crash-bid ledger +$0.92, NASDAQ dip +$5.87 (one closed trade: QQQ 710.39 -> 726.15), fees -$1.44. The first 13 days ran the code from before the 10-22 fixes. **The machine alone - no crowd book** (kept so on purpose: the day-45 line was set for it). |
| **PAPER, fresh account** (since 2026-10-17 01:15 UTC, day 9) | **$279.97 live (-6.7%, 18.8th percentile = "below")**, $278.48 booked (-7.2%), biggest fall 12.3% (booked). **Since 2026-10-25 16:59 UTC it also carries the crowd-squeeze book at x1.0** (`crowd_book.py`, `--crowd`; the user: "add to fresh only"), its first week opened at the 10-26 00:00 anchor (21 legs, identical to the standalone book's; the 10-29 anchor is next). Its dashboard scorecard leaves that book out, so it still compares like-for-like with the machine's bands. |
| **Gate that applies** | **Day-45 KILL line (doc 22 s3b): the main account's live equity under $261.30 at 2026-11-23 00:04 UTC.** On 2026-10-26 the live $254.82 is $6.48 under it; the rule reads that one moment, 28 days from now, so today is not the verdict, and it is not above the line either. The fund decision is 2027-04-09 (section 4). |

"Live" is booked equity plus open P&L (the dashboard's number, and the one the day-45 rule reads); "booked" is what the
status command prints.

### The other books (all PAPER; none can be funded before its own date)

| Book | Since | Paper result today | What the BACKTEST says | Judged |
|---|---|---|---|---|
| **Machine v2** (`combo_paper.py`, $221) | 2026-09-24 | day 32: **$158.75 (-28.2%)**, biggest fall 28.5%; trend -$44.48, market-neutral -$17.23. Day 30: $154.22 (-30.2%) = **1.6th percentile of the backtest's BULL-start 30-day windows** (`logs/combo_window_30d.txt`; registered guess 1st-2nd, right) | typical 12 months $1,210 (6 yrs) / $1,125 (last 2) on $221, deepest fall 59% / 45% (`max_mix.py`, CLAUDE.md s6) | month-3 check about 2026-12-24 (the 5th-percentile kill line applies from then, and it is already under it); verdict 2027-03-24 |
| **Crash bids** (`wick_paper.py`, two $300 ledgers) | 2026-09-25 | Bitget +1.90%, 63 fills at +1.21% each (expected +0.8..+1.0); Binance +1.61% on 60 | +16%/yr alone (docs 16-17) | 6 months (2027-03-25) *and* 60+ Bitget fills: the fills are in, the time is not |
| **The pair + capit2 shadow** (`pair_live.py`, PKR) | 2026-10-08 | 8,775 of 10,000 PKR (-12.3% at 21:05 UTC on 10-26; 14:23: 8,426; 10-25: 8,639; 10-24: 8,835). Capitulation: 9 closed, 67% won, +2.58% avg. **Daily book: 6 closed, 0 won, -20.5% avg**, 5 open. capit2 shadow: no signal yet | +51%/yr median, falls 25-34% (`pair_books.py`) | capit2 shadow: 30 closed trades or 2027-10-08 |
| **Crowd-squeeze** (`news/crowd_paper.py`, $300) | 2026-10-23 | $299.24, its first week (21 legs) opened at the Mon 10-26 anchor, none closed yet (Thu 10-29 next) | +37% / +48%/yr, t 1.8-2.0: a lead, not a pass (`news/positioning_hist.py`); 26-week band p10 -6.5%, median +18.4% | KILL checkpoint 2027-01-25 (under -7.8%); verdict 2027-04-09 (dead under -6.6%, held up at +16.8% or more) |
| **Analyst desk** (`analyst.py`, $300) | built 2026-10-27, **NOT DEPLOYED** (waits for the user's go-ahead) | no calls yet | none expected: every chart-rule test in doc 02 is dead after fees; the desk is the user's idea measured forward | 100 resolved calls or 2027-01-31 (`analyst.py` docstring, doc 22 override) |
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
| `analyst-paper.timer` | **NOT INSTALLED YET** - the Analyst desk (hourly :07), units are in `deploy/`, waiting for the user's go-ahead | - |
| `forexbot-dash.timer` | dashboard snapshot, every minute | 2026-10-17 |
| `status-server` | small HTTP status page | 2026-09-13 |

**The PC** runs one thing: `poly_forward.py`, the Polymarket snapshot collector (data only; the Polymarket ideas are
dead, docs 08 and 02).

**Not running, and why:** `combo-bot-demo` (the Bitget DEMO order-path test) was stopped 2026-10-17 after 191 orders,
all filled and priced, 0 order or stop failures; its verdict stayed "not yet" only for two Bitget network blips.
`mn_paper.py` is dead (and carries the funding bug, CLAUDE.md s7b). The old PC runners (`longtrend_*`, `xs_paper`,
`crypto_*`) are gone. The DOGE live test, order-book recorders and TradingView session stopped 2026-10-09;
`sentiment_rec.py` and the meme collector are not running now.

**The dashboard**: the VM side is verified (the timer fires every minute and writes the equity feed). The web app on
Vercel lives outside this repo's runtime and was not checked.

---

## 3. Code identity

- **The VM is at `a100fa2`; origin/main is newer** (`9873966` changed only two dashboard files, the top-bar "Fuel" label, which run on Vercel; the commits
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
- **The trend-book fuel gauge is LIVE** (deployed 2026-10-27 at the user's word: VM pulled to `a100fa2`, tests pass on the VM, one mood snapshot
  written and seen in the feed payload, Vercel reported "Deployment has completed" for the commit). Display only; no book reads it. It reads
  LOW (5% of the top-40 running, median coin -19% in 30 days). **Where to see it:** a "Fuel LOW" label in the top bar of EVERY tab (next to the BTC
  price; added in `9873966` after the first version showed it only on the Mood tab, which the user did not find) and the full line on the Mood tab.
  The trend book has no fuel for an explosive month, which the machine's backtest
  says is normal and lasts a while (doc 02, last entry). It does not change the day-45 line.
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

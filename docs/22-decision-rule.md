# 22 - The decision rule: when real money goes in, and when the search stops

*Written 2026-10-10, BEFORE the verdict data, on the councils' advice. Changing it after a record comes in would make
the record worthless - the same rule as every pre-registered prediction in this repo. Only the user flips
`ALLOW_REAL`; nothing in this document or in any script does.*

## 1. What is being judged, and when

| Record (all paper, on the VM) | Started | Verdict | Its own hypotheses |
|---|---|---|---|
| `combo_paper.py` - machine v2 | 2026-09-24 | **2027-03-24** | H1-H3 in its docstring |
| `combo_bot.py --mode dry --final` - the final machine | 2026-10-09 00:04 UTC | **2027-04-09** | `final_books.py` docstring |
| capit2 shadow book in `pair_live.py` | 2026-10-08 | 30 closed trades or **2027-10-08** | H1-H3 in its docstring |
| `wick_paper.py` - crash bids | 2026-09-25 | 6 months with 60+ Bitget fills, else 12 | H1-H4 in its docstring |

**Added 2026-10-23: the final machine also has a day-45 KILL checkpoint on 2026-11-23 00:04 UTC (§3b).** Otherwise no
verdict earlier. A bad month is not a verdict (the books make their year in one or two months, and ~4 months in 10
lose); the monthly kill line below is the only early exit.

## 2. FUND - every condition must hold on the verdict date

1. **Same-regime position.** The record's return over its N days is at or above the **25th percentile** of the
   backtest's N-day windows that START in the same BTC regime (`python -m backtest.combo_window --days N --live R`;
   for the final machine, extend that script to its series first, before reading the record).
2. **Beats the simple benchmark.** Over the same days, in USDT, it beats holding BTC only while BTC is above its
   1000-hour average (`backtest/btc_timing.py`'s rule: Sharpe 1.12 vs 0.68 for buy-and-hold). If a four-book machine
   cannot beat a one-line rule forward, it is not worth its complexity.
3. **Tradable at the capital to be used.** Under 10% of its orders logged `BELOW VENUE MINIMUM` in the dry run at that
   capital (the final machine needs ~$300-550; the full point-in-time v3 ~100-150k PKR, `pair_min_capital.py`).
4. **The money path is tested.** ~$20 moved PKR -> USDT -> Bitget -> back to PKR, end to end, with the true round-trip
   cost written down (P2P spread, fees, days, any bank flag). That cost is subtracted from the book's expected return.
5. **No open bug** in CLAUDE.md s7b touches the book.

Then, if the user chooses: fund, and the user sets `ALLOW_REAL = True` by hand. **Size: x1.0 - the user's decision on
2026-10-24** ("0.65 will hurt gains"). x0.65 was the pre-set suggestion: backtest worst month -20% instead of -30%, at
about half the typical year ($1,806 vs $3,400 on $300, `final_books.py`'s docstring). At x1.0 plan on falls of 40-60%
along the way - the backtest's deepest - and a worst month near -30%.

## 3. KILL and EXTEND

- **Kill** a book at its verdict if it sits below the **5th percentile** of same-regime windows - or at any monthly
  check from month 3 on. Record it in doc 02. Kills are permanent unless the measurement was broken.
- **Extend** once, by 3 months, if it lands between the 5th and 25th percentiles.

## 3b. The day-45 checkpoint - the final machine (added 2026-10-23, BEFORE its day-45 data)

*Asked for by the user ("I want the verdict soon, can't wait 3 months"). Written on 2026-10-23, 14 days into the main
account's record and 22 days before its checkpoint. It ADDS an earlier kill and a pre-set small-stake option; it does
not loosen §2's FUND rule.*

**Why day 45.** `backtest/verdict_power.py` (`logs/verdict_power.txt`): how often the running final machine, as
backtested, looks like a machine with no edge (the same daily returns with their growth removed). Best-cut accuracy:
2 weeks 65%, 1 month 69%, **45 days 74%**, 3 months 74%, 6 months 73%. It stops improving after ~45 days, because the
machine's months cluster by regime and the year is made in one or two months. So day 45 says about as much as day 180.

**The line: the account down 12.9% at day 45** (the best cut at 45 days, taken from the backtest's two distributions -
not fitted to the live reading). A working machine ends under it 10% of the time, a dead one 58%.

| Account | Started (UTC) | Day 45 (UTC) | KILL if its equity is under |
|---|---|---|---|
| **main** (`combo-bot-final`) - decides | 2026-10-09 00:04 | **2026-11-23 00:04** | **$261.30** |
| fresh (`combo-bot-fresh`) - read beside it | 2026-10-17 01:15 | 2026-12-01 01:15 | $261.30, read WITHOUT its crowd book (below) |

*Added 2026-10-25, before either reading:* the fresh account carries the crowd-squeeze book inside it since 2026-10-25
16:59 UTC (`crowd_book.py`, the user's choice: "add to fresh only"). Its line is read on its equity MINUS that book's
booked P&L, open P&L and fees - the figure the dashboard's scorecard uses - so the comparison stays the machine's. The
main account has no crowd book and is read as written.

**What is read.** The dashboard's LIVE equity (booked + open) at that hour, from `logs/dashboard/eq_main_h.csv` on the VM;
the booked equity is written down beside it.

**The outcomes:**
- **Under $261.30: KILL.** About 6 times as likely from a machine with no edge as from the one backtested. No real money
  for this machine; record it in doc 02 with this paragraph's numbers. The paper bot may keep running for the record,
  but the funding question is closed until a NEW pre-registered test reopens it.
- **At or over $261.30: CONTINUE.** Only ~2 times as likely from a working machine - a weak yes. It does NOT meet §2;
  the month-3 check (below the 5th percentile of same-regime windows kills) and the verdict date stand.
- **If the user still chooses to fund after a day-45 CONTINUE** (pre-set now, so it is not decided in a good week): §2's
  conditions 3-5 must hold (tradable at the capital, the PKR money path tested, no open bug touching the book); size
  x1.0 (the user's decision, 2026-10-24 - see s2); a stake sized so a 40-60% fall, the backtest's deepest, can be sat
  through; withdrawals only above the starting stake; and the month-3 kill line applies to the real account as it does
  to paper. Only the user sets `ALLOW_REAL`. **The venue pieces are built (2026-10-24):** capit2's limit rests on the
  venue as a post-only order (`final_books.capit2_orders`), `--final --mode live` always runs the real crash desk
  (`combo_bot.wants_desk`), and the coin map converts names and units (`combo_bot.Venue.mapped`: 1000SHIB / 1000PEPE /
  1000FLOKI / 1000LUNC / 1000CHEEMS / RAYSOL; 651 more same-named; checked against live prices, none off by > 0.2%).
  Tested offline (`tests/test_live_orders.py`, 10 tests, 8 mutations caught); not yet seen on a real account - the
  demo lists only SBTC / SETH / SXRP.

**What this checkpoint cannot see.** The first 13 days ran the code before the 2026-10-22 fixes (capit2 as a poll, no
crash bids, the simple-mean ATR, the daily 24h-volume universe); their -13% counts in the reading as it is. The older
machine (`combo_paper.py`, v2) is a different set of books and is NOT judged by this line - its own month-3 check stands
(at day 28 it sat at the 4.1th percentile of BULL-start windows, `combo_window.py --days 28`).

## 4. Code freeze until 2027-04-09

No new books, no parameter changes, no new sweeps of the mined holdout. Allowed, each logged in CLAUDE.md s10:
- fixes that make a live book do what was tested - e.g. capit2's entry: the live 2-minute poll at market earns +1.76%
  a signal against the backtested resting limit's +2.15% (`backtest/capit2_exec.py`); a resting post-only limit
  (the crash desk's machinery) is the fix, applied only if the user agrees;
- bug fixes, deployment fixes, the demo restart that picks up the sub-step order fix (s7b).

**Override, 2026-10-23 (the user: "do 2 3"):** one new PAPER book, the crowd-squeeze book (`news/crowd_paper.py`, its
own $300, its own files, hourly timer on the VM). It is outside the final machine: combo_bot, final_books and every
running book are untouched, and s3b's checkpoint reads the machine alone. Its lines were written before its first
trade (crowd_paper.py's docstring, amended the same day after `news/crowd_fast.py`'s checks): a KILL checkpoint on
2027-01-25 (under -7.8%), and its verdict on **2027-04-09, the machine's own date**: dead under -6.6%, held up at +16.8%
or more - then it may join the machine. Real money in it would still need s2's conditions.

**Override, 2026-10-27 (the user: "show it on the dashboard ... the bot first predicts, then records how many times it was right ... a separate book"):** one more PAPER
book, the Analyst desk (`analyst.py`, its own $300, its own files, hourly timer). Outside the machine like the crowd book: no bot is touched and s3b reads the machine alone. Its
lines are in the file's docstring before its first call: no edge expected (A1-A4); review at 100 resolved calls or 2027-01-31; retired if the average result after fees is
not above zero or the hit rate does not beat the random-entry baseline (p < 0.05). It never trades real money and cannot qualify for s2.
**Amended 2026-10-27 13:56 UTC, with 6 of the 30 calls resolved (the user's word, before any verdict):** that p counts the calls MADE on the same UTC day in the
same direction as ONE bet (one market move stopped four shorts within 21 minutes that day), Student's t over the bets; the per-call figure stays on the record
as `p_calls`. Nothing else in the rule changed. The wording is in `analyst.py`'s docstring.

**Override, 2026-11-08 (the user: "yes, record it"):** one more PAPER book, the RSI-80 momentum book (`rsi80_paper.py`, its own $300, its own files, a timer every
4 hours on the VM): long the top-100 USDT perps when the 4h RSI(14) crosses up through 80, stop 4 ATR, target 4R, out after 24 bars, 1% of the booked equity at risk.
Found by `rsi_ratio.py`, a narrow no-pass on unseen data (`backtest/rsi80_more.py`: +0.14R a trade, t 1.80), not the trend book again (`backtest/rsi80_overlap.py`).
Outside the machine like the crowd book and the desk: no bot is touched and s3b reads the machine alone. Its lines are in the file's docstring before its first trade:
KILL on 2027-01-31 (30+ trades, mean under -0.24R); verdict on **2027-04-09**: held up at +0.072R a trade with the account above $300, dead under -0.107R, between
= cannot tell, extended to 2027-10-09. A held-up verdict makes it a candidate to join the machine; real money would still need s2's conditions.

**Override, 2026-11-09 (the user: "yes, build it"): the forward ledger** (`backtest/forward_ledger.py`, run on the PC; nothing on the VM trades or changes).
Three leads are re-run on data after **2026-11-09 00:00 UTC** with their study files' own code, pinned by hash before the window opened (2026-11-08 22:44 UTC):
the gold payrolls straddle (+11.1bp claimed), the NASDAQ inside-bar buy (+0.079R) and NASDAQ before the Fed (+0.25%). One rule for all three: dead when the forward
mean is more than 2 standard errors under the claim (5+ trades), confirmed only at t >= 2 after Holm across the three; otherwise keep recording. None can be
confirmed before ~6.5 / 10.7 / 23 years at the claimed size, so this is a record, not a route to money; s3b and s1 are unchanged. The dashboard's Leads tab
lists it beside every other forward record.

## 4c. The event account - a NEW pre-registered test (added 2026-11-27, BEFORE its first live day)

*Why it exists.* The final machine was killed at its day-45 check (s3b: main $224.29 live on 2026-11-23 00:04 UTC against the
$261.30 line). s3b says the funding question stays closed "until a NEW pre-registered test reopens it". This is that test. After
the KILL, the books that held up were the ones that wait for a forced trade or a payment (funding carry, capit2, crash bids, the
news shorts, the NASDAQ dip-buy: about +$16 on each paper account from roughly 13 trades - a small, post-hoc sample); everything
that lost was a ranking of pump coins plus trend longs. The account runs ONLY those five books.

*What runs.* `event_bot.py` (its docstring is the specification): the final machine's own code in a separate $300 PAPER account
(`combo_bot.py --mode dry --final --account events`, `combo-bot-events.service`), trend / market-neutral / bear sleeve / daily
breakout switched off in its own process, carry at x1.0 instead of x0.5 so Bitget's $5 minimum does not switch it off after a
fall (the machine's carry rebalance was empty on main from 2026-11-13 and on fresh from 2026-11-07). No orders, no keys, no real-money
path; `--mode dry` is fixed in the wrapper. No running bot's file is changed (the code freeze, s4, is respected).

*The claim, priced before any live day* (`backtest/event_account_registered.py` -> `logs/event_account_registered.txt`; the
bands `backtest/event_account_bands.py` -> `event_bands.json`, `logs/event_account_bands.txt`; 2020-02 .. 2026-09, 10 slot
orderings): full-period CAGR +134%, deepest fall 26%, 72% of months up; typical $300 year $580 (tune) / $911 (holdout), worst
month -10% / -16%. **It does NOT beat 'bet the machine smaller'** (the deployed machine scaled to the same fall makes $944 /
$1,830 a typical year): the claim is a steadier account, not a better one. Its last backtest year (2026 to September) is +8.6%
(news -25%). Stretches of 90 days: 5th percentile -7.8%, 25th +7.3%, median +19.2%; of 180 days: 5th +3.5%, 25th +25.4%, median +46.6%.
Predictions in the backtest file: V1 wrong by 4 points (+134% against 'up to +130%'), V2, V3, V4, V5 right.

*The lines (fixed now; they cannot move after the first live day).* Counted from START = the first poll after the service is
enabled (the date is written under this section the day it happens). The read is the dashboard's LIVE equity (booked + open) for
the 'Event books' account, placed in `event_bands.json` by the scorecard.
- **KILL** - from day 90 and at every 30 days after: live equity under the backtest's 5th percentile for that age (the page's
  'worse'): day 90 under -7.8% = **$276.6**, day 120 under -4.7% = $285.9, day 180 under +3.5% = $310.5. Kills are permanent
  (s3); record it in doc 02.
- **VERDICT at day 180:** at or over the 25th percentile of 180-day stretches (**+25.4% = $376.2**) AND s2's conditions 2-5
  hold (beats 'hold BTC only above its 1000h average' over the same days; tradable at the capital, floors included; the PKR money
  path tested; no open bug in CLAUDE.md s7b touching these books) = eligible for the funding question - the user's call, ALLOW_REAL
  untouched. Between the 5th and the 25th percentile: extend once by 3 months. Under the 5th: kill.
- **What does not count:** a good first 60 days (20% of the backtest's 60-day stretches are negative, so being up says little), one
  big news or capit2 trade, and any reading of the books' separate results as a verdict - only the account is judged.
- **What is NOT claimed:** that it beats the machine scaled down; that carry at x1.0 is right (it is the machine's x0.5 doubled; the
  backtest series are linear in the weight, the live fills are not); that 180 days is enough (capit2 is idle in 34% of 90-day
  stretches and the news book had 3 trades in the live record so far - the account can end the window with too few events to read,
  in which case 'extend' is the honest outcome, not a pass).
- **The floors are part of the record, not faults:** crash bids pause under $200 of equity (the $5 minimum) and on every BEAR day;
  carry under about $120; news under about $50. The dashboard shows each book's own result, so a book that switches itself off is
  visible there.
- **Changes:** none to the books' rules or weights before the verdict. A bug fix is logged here and in CLAUDE.md s10 with the date; it
  does not restart the clock unless it changes what a book trades.
- **STARTED 2026-11-26 19:26:04 UTC** (2026-11-27 in Pakistan; `combo-bot-events.service` on the VM, commit `263d2dc`; first poll 19:27 UTC
  opened the carry basket, 11 longs / 12 shorts at $12.50 each, and nothing else - the other books were off as specified). Reads: **day 90 =
  2027-02-24**, day 120 = 2027-03-26, day 150 = 2027-04-25, **day 180 verdict = 2027-05-25** (all about 19:26 UTC). The code freeze (s4) ends
  2027-04-09, before the verdict; it does not change this account's rules.
- **My prior, recorded before the data (rule 8):** about 25-30% that it reaches the 25th percentile at day 180, about 60% that it is not
  killed at day 90. Every forward record in this repo so far has come in under its backtest claim (the machine, the Analyst
  'sweet spot', crash bids at +0.24% a fill against +0.8%, the crowd book under its line); I expect this one to as well, by less,
  because it has no ranking of pump coins in it.

## 5. The research stops on 2026-12-31

What the 2026-10-10 councils asked to test is done:

| Candidate | Result | File |
|---|---|---|
| Polymarket weather markets vs a free forecast | market wins in all 22 cities - dead | `backtest/poly_weather.py` |
| Polymarket 80-90c favourites without early resolutions | +8 points, within 2 se of zero - killed by its rule | `backtest/poly_rescore.py` |
| The trader's copy, sized by its worst adverse move | passes: 0.37 lot ~ +$14/month on $221 (needs his signals) | `backtest/his_size.py` |
| Per-person-capped exchange rewards | premise fails: Launchpool rewards are pro-rata to stake | (Bitget Launchpool terms) |
| Maker execution for capit2 | resting limit +0.39 points a signal over the live poll | `backtest/capit2_exec.py` |

Until 2026-12-31 only the trader route stays open (below). If nothing new passes by then, the conclusion is written down
and the time goes to earning capital: at $221 a monthly deposit moves the account more than any strategy change found.

## 6. The trader

Decoding him from market data is exhausted (`strategy_analysis/his_strategy.md` s46-47): every market input was ruled out,
and his broker's feed cannot carry more about the real market than the real market's own data. The only routes left need
him: ask what is on his screen when he clicks (or a short screen recording), or a timestamped signal feed copied on an
Exness demo for a month. Kill: no reply within 2 weeks, or demo copies under +3 points a trade after the spread.

## 7. The yardstick for everything

Score every result against doing nothing clever: in PKR terms, holding USDT earns the rupee's fall plus a little, with no
strategy risk. A book or an idea that does not beat that, net of the hours it costs, is not worth running.

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

No verdict earlier. A bad month is not a verdict (the books make their year in one or two months, and ~4 months in 10
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

Then, if the user chooses: fund at **x0.65 size** (backtest worst month -20% instead of -30%), and the user sets
`ALLOW_REAL = True` by hand.

## 3. KILL and EXTEND

- **Kill** a book at its verdict if it sits below the **5th percentile** of same-regime windows - or at any monthly
  check from month 3 on. Record it in doc 02. Kills are permanent unless the measurement was broken.
- **Extend** once, by 3 months, if it lands between the 5th and 25th percentiles.

## 4. Code freeze until 2027-04-09

No new books, no parameter changes, no new sweeps of the mined holdout. Allowed, each logged in CLAUDE.md s10:
- fixes that make a live book do what was tested - e.g. capit2's entry: the live 2-minute poll at market earns +1.76%
  a signal against the backtested resting limit's +2.15% (`backtest/capit2_exec.py`); a resting post-only limit
  (the crash desk's machinery) is the fix, applied only if the user agrees;
- bug fixes, deployment fixes, the demo restart that picks up the sub-step order fix (s7b).

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

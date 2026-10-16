# 26 - The end goal: one bot that watches the world and uses everything that works

*Written 2026-10-16. The user: "a perfect bot looking at the world, trying everything we have tested and applying it -
one bot capable of making substantial gains. That's the end goal."*

"Perfect" here means a precise thing: **every edge that has passed its tests is in it, nothing that failed is, every
risk we can measure is measured live, and it gets better only through tested changes - never by guessing.** It does
not mean it never loses: every version measured here loses in about half its months and falls 30-50% at its worst.

---

## 1. The five layers

| layer | what it does | status |
|---|---|---|
| **1. Edges (the books)** | trend triple, market-neutral blend, funding carry, bear sleeve, crash bids, daily Bollinger, capit2 | **running on paper** (`combo_bot.py --final`, VM). Out of sample 2017-19: trend and daily hold, capit2's 2x does not (`oos1719.py`) |
| | the bad-news book: short coins after a monitoring tag / new-token launch, long BTC, stop 25% | **being measured** on the full news history (`news/news_book.py`) |
| **2. Eyes (the world)** | BTC regime and breadth; funding, open interest, long / short, liquidations; the news engine (event type, coins, learned impact); crowd mood (Reddit, Bluesky, Fear & Greed, Santiment / LunarCrush) | news engine **built** (`news/`), history collecting; crowd mood **planned** (doc 25 phase D) |
| **3. Risk** | account gross cap; the live worst-hour estimate on the positions actually held (`liq_stress.py`'s method); per-book drawdown alarms; liquidation-equivalent exits | cap and exits **running**; live worst-hour estimate **planned** (doc 24 phase 2) |
| **4. Hands (execution)** | one Bitget account, netted per coin, venue rules, disaster stops, crash desk | **proven** on Bitget's demo: 180 orders, 0 failures, 1.4bp slippage |
| **5. Learning loop** | record every outcome with its context -> score each book against its backtest daily -> propose changes -> test them (harness, both halves, out of sample) -> a human approves -> deploy | the tests exist (every `backtest/*.py`, `mended_harness.py`, `oos1719.py`); the automatic scorecard and proposals **planned** (doc 24 phase 3) |

Plus the **dashboard** to watch it all (doc 24) and **alerts** to the phone.

## 2. Why the learning loop never changes the bot by itself

Measured here, every time: a system that re-tunes itself on its recent results loses (`doge_adapt.py`, `doge_focus.py`);
a signal that looks good on one period flips on the next (`month_regime.py`: helped 2017-19, hurt 2020-26); and every
large improvement in this repo's history was a bug until proven otherwise (CLAUDE.md s9). So the bot watches, records,
scores and PROPOSES; changes go through the same tests as everything else and a person says yes.

## 3. What "substantial gains" honestly looks like

| source | figure | file |
|---|---|---|
| the final machine, backtest 2020-26 | typical year ~13x on $300 - inflated by hindsight and a mined holdout | `final_capit2_lev.py` |
| the same rules on unseen years 2017-19 | **+88% a year, worst fall 48%, about half the months losing** | `oos1719.py` |
| discounted for every known flatterer | profitable 12 months ~60-65%; a fall of 40-50% along the way ~50% | `final_confidence.py` |
| bad-news book (partial data) | ~+40-50% a year, fall ~20%, both halves | `news/news_book.py` - pending the full history |

A book that earns from a different source (bad news, against BTC) is worth more than its own return: it can earn in the
sideways months when the trend book does not. That is the main thing layer 2 can add.

## 4. The road from here

1. **Now**: the full news history -> the impact table and the bad-news book on it, with minute-level entry timing.
2. **If it holds**: the bad-news book as a paper book beside the final machine (same as every book: paper first).
3. **Decisions already open**: capit2 back to 1x / 1.5x (not supported out of sample at 2x).
4. **Dashboard phases 1-3** (live trades, risk, scorecard, proposals) - so you can watch it work.
5. **Crowd-mood collectors** (doc 25 phase D) - recorded from day one, used only once they pass.
6. **Real money** only by docs/22's rule: paper records inside their backtest ranges, out-of-sample checks passed,
   a tested money path - and `ALLOW_REAL` flipped by you, never by the code.

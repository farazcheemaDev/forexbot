# Profiting from crashes: resting bids under the wick (2026-09-24)

*Asked for: "how can we benefit from crashes then, there must be something". Every number names its
file. Status: **a candidate, NOT deployed, no paper book yet.***

> **Superseded in part by [doc 16](16-crash-buys-safe.md) (2026-09-25).** The book below, as written,
> hides a near-wipe-out. On 2025-10-10 21:00 its bids and the trend book together left **10% of the
> account** in one hour, a loss that the fill hour's close does not show. Doc 16's rule changes three
> things: it skips BEAR days, uses the top-40, and cancels the remaining bids after 10 fills per hour.
> Its $300 figures replace the ones below: typical year $1,812, not $1,937.

**Short version.**
- **You cannot short a crash; you can buy one.** Short a crash and you had to be short before it:
  every short-entry rule tested here was no better than random (doc 14 §14).
- **The other side of a crash is the forced seller.** Liquidations sell at any price for minutes.
- **The rule:** a buy order left **10% below the previous hour's close** on each of the top-20 coins,
  and whatever fills is **sold at the end of that same hour**.
- **Results:**
  - **+30.8%/yr** on its own, with 30bp of extra crash-hour slippage;
  - positive in every year 2020–2026 and on both halves;
  - it survives removing the biggest days and all of 2021;
  - it works on Bitget's own candles;
  - correlation with the final version is +0.09.
- **Added to the final version on $300:** the typical year goes $1,642 → **$1,937** (6 years) and
  $1,527 → **$1,629** (last 2 years), and the biggest fall goes 59% → 54%. The worst month gets
  worse (−29% → −36%).

---

## 1. Why this and not the taker version

`cascade_redux.py` (doc 11) killed buying AFTER a liquidation cascade at the bar close, on 4 years of
5-minute data: −3 to +2bp net. Its own docstring named the one route left: *"maker entry would be the
only route"*. A resting limit bid is placed in advance and is filled AT the wick, not after it.

## 2. The per-fill test — `backtest/crash_buy.py` (log `logs/crash_buy.txt`)

**Setup:**
- every hour, every PIT top-40 perp (364 coins over time, dead included);
- a bid k% under the previous close, filled only if the low goes **0.1% through it**, at
  min(bid, open);
- fees of 8bp (2bp maker in, 6bp taker out), and again at 12bp.

| k | fills / yr | sold at the fill hour's close: all / tune / holdout | held 24h: all / holdout | years positive (close exit) |
|---|---|---|---|---|
| 10% | 659 | **+2.24% / +2.79% / +1.22%** | +4.66% / +0.05% | 7 of 7 |
| 15% | 249 | **+4.75% / +6.11% / +2.11%** | +6.64% / −0.31% | 7 of 7 |
| 20% | 109 | **+7.12% / +9.41% / +2.51%** | +8.57% / −1.60% | 7 of 7 |

**Holding longer is what kills it.** Coins that keep falling do the damage: LUNA 2022-05-11
filled five times and went to −100% by +24h. As a portfolio, the 24h exit reaches 78–100% drawdowns.
**Sell at the end of the hour.**

**The mirror is dead.** Resting sells above the price, to fade squeezes, make ~0 at the close and
−8% to −19% with a take-profit.

**Glitch check.** The best fills are the 19 May 2021 Binance crash hour, and the raw bars show it
was real. SUSHI traded 17.54 → 5.83 → 23.15 → 14.84 across two hours; XLM 0.516 → 0.221 → 0.491.

## 3. Trying to break it — `backtest/crash_buy_check.py` (log `logs/crash_buy_check.txt`)

**1. Honest capacity.** A crash fills every resting bid at once, so there are bids on the top-N,
each 1/N of equity, and nothing is skipped:

| N | k | CAGR | tune | holdout | worst day | max DD |
|---|---|---|---|---|---|---|
| 20 | 10% | +37.5% | +48.4% | +15.8% | −17.3% | 22% |
| 20 | 15% | +29.2% | +37.9% | +12.0% | −11.3% | 14% |
| 40 | 10% | +40.1% | +48.8% | +22.7% | −12.1% | 13% |
| 40 | 15% | +32.4% | +41.6% | +14.4% | −7.5% | 9% |

**2. Exit slippage in the crash hour** (N 20):
- +60bp: k 10% still +24.4% (holdout +3.9); k 15% +24.6% (+7.6).
- +100bp: **k 10% holdout −3.4%**; k 15% +21.6% (+4.7); k 20% +15.8% (+4.7).

**3. Without the big days** (N 20):
- without the top-3 days: +30.3 / +21.7 / +12.3 %/yr for k 10 / 15 / 20;
- **without every 2021 fill: +16.2 / +14.3 / +11.0 %/yr.**

**4. The venue.** Bitget's history endpoint served 2025-10-24 → 2026-09-21 (after the 2025-10-10
crash), on 20 coins, compared with Binance on the same coins and dates:
- **k 10%: Bitget 34 fills at +5.42% each, Binance 46 fills at +4.79%.**
- k 15%: Bitget 0 fills, Binance 11.

Bitget's wicks are shallower, so on Bitget use **k ≈ 10%**.

Registered for this file:
- capacity positive at N 20/40: right;
- 60bp positive for k 15–20%: right;
- positive without the top days and without 2021: right;
- Bitget shallower with fewer fills: right, though its per-fill return was not smaller at 10%.

## 4. Added to the final version — `backtest/wick_combo.py` (log `logs/wick_combo.txt`)

This is the final version (doc 14 §8) plus the wick book (top-20, 10% below, 1/20 each, +30bp exit
slippage), on $300, over 10 orderings.

| $300, 12 months | typical year | bad year | fall | typical month | worst month | months up |
|---|---|---|---|---|---|---|
| final, 6 years | $1,642 | $666 | 59% | +$12 | −29% | 56% |
| **final + wicks, 6 years** | **$1,937** | **$744** | **54%** | **+$17** | **−36%** | **60%** |
| final, last 2 years | $1,527 | $1,004 | 45% | +$18 | −23% | 63% |
| **final + wicks, last 2 years** | **$1,629** | **$1,059** | 45% | +$19 | −25% | 65% |

Correlation with the final version is **+0.09**.

Registered: *"correlation ~0; typical year +10–25%; worst month a little better; fall unchanged."*
Outcomes:
- correlation: right;
- the typical year: +18% over 6 years (right), but only +7% over the last 2 years;
- **the worst month got WORSE (−29% → −36%): wrong.** In a crash month where the coins keep
  falling (May 2022) the wick book loses alongside the trend book;
- the fall improved over 6 years (59% → 54%).

## 5. Why it can work for a small account, and what is not settled

**The mechanism.** It is paid for providing liquidity to forced sellers at the extreme. Only a little
size trades at wick prices, so it is **capacity-limited**: an edge a fund cannot take and a $300
account can.

**Not settled:**
- **Decay.** Holdout returns are a third to a half of the tune half's.
- **The venue.** There is only 11 months of Bitget history, and it contains no big crash. Bitget
  fills are rarer.
- **Execution.** It needs 20 resting limit orders re-placed every hour, and a market sell at each
  hour's end. None of that exists in `combo_bot.py` yet. On a netted account, a wick fill on a coin
  the trend book holds changes that coin's net position for up to an hour.
- **The worst month is worse** with it.

**The next step would be a pre-registered paper book.** It can be computed exactly from hourly
candles after each hour closes. It must be separate from `combo_paper.py`, whose pre-registration
cannot change mid-test.

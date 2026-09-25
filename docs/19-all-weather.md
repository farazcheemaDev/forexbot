# 19 — All-weather: making the sideways months pay

*2026-09-26. Files: `backtest/all_weather.py`, `all_weather_check.py`, `all_weather_pick.py`,
`mn_stop.py`, `mn_scale.py`. Logs of the same names.*

**The goal, in the user's words:** *"an end result bot basically our product ... i just need an end
product that can give crazy gains in every time of market not just [bull]."*

---

## 1. What was actually wrong

The product earns in two of three markets and nothing in the third (`logs/machine.txt`):

| market | months | average | typical | up |
|---|---|---|---|---|
| RISING | 31 | +71.0% | +22.5% | 71% |
| **SIDEWAYS** | 26 | **+0.2%** | **−4.5%** | **32%** |
| FALLING | 23 | +7.6% | +4.7% | 64% |

The sideways month decomposes like this (`all_weather.py`, 26 months × 10 orderings):

| book | mean | median | % up |
|---|---|---|---|
| trend | −5.2% | **−6.5%** | **23%** |
| market-neutral | +4.3% | +0.2% | 50% |
| bear sleeve | −0.7% | +0.0% | 12% |
| crash bids | +1.4% | +1.1% | **88%** |

## 2. Three levers, and which one worked

**Cutting the trend book in chop — already dead.** `dd_fixes.py` measured every chop gate at
−0.46 to −4.48 %/mo with 0–2 wins of 10. The book has to be *in* the market during chop to catch
the turn into bull; its chop losses are the premium for the bull payoff.

**Making the MN book safer so it can be bigger — dead, twice.** A short-leg stop makes the worst
week *worse* (−26.3% against −24.2%) and fires on 0.3% of positions. A wider basket dilutes the
signal faster than it cuts the tail — at a common worst week, `frac 0.10` beats every wider
basket. Both are in [doc 02](02-what-failed.md); one of them also killed its own premise, because
the single-name blow-ups that motivated it belong to the *funding carry* book, not this one.

**Just weighting the MN book higher — this is the one.** It needs no change to any book.

## 3. The result

`max_mix.py` searched for the highest typical *year* at a bounded fall. That objective is
indifferent to *where* return comes from, which is why it produced a book with a dead sideways
cell. Ranking the same 54 mixes by their **worst regime cell** picks a different mix, and it
passes the control that matters:

| at the same 68% fall | BULL | **CHOP** | BEAR | typ yr |
|---|---|---|---|---|
| machine v2 **×1.3** (just bet more) | +95.5% | **+0.5%** | +9.7% | $1,989 |
| **all-weather** (trend 70%, MN 2×) | +55.2% | **+7.0%** | +12.3% | $1,474 |

**Betting more does nothing for chop** — it scales the trend book's chop *loss* too. So the weight
change is re-allocating risk, not adding leverage. It also holds where it has to:

| | v2 CHOP | all-weather CHOP |
|---|---|---|
| tune half | **−1.1%** | **+4.4%** |
| holdout | +2.8% | +11.7% |
| bar phases 0/1/2/3 | +0.3 / +0.3 / +0.8 / +0.6% | +7.0 / +7.0 / +7.3 / +7.2% |

The tune half goes from a *losing* chop cell to a positive one, and all four bar phases give the
same +6.5 to +6.7 gain. Four of four registered predictions held.

## 4. The menu, and the number that decides it

Every mix at MN ≥ 1.5× gains **both** chop and return — it is not a trade-off (`all_weather_pick.py`):

| mix | BULL | CHOP | BEAR | typ yr | DD | worst mo |
|---|---|---|---|---|---|---|
| machine v2 (today, on the VM) | +71.0% | +0.3% | +7.6% | $1,469 | 57% | −29% |
| MN 1.5×, trend 85%, sleeve 1.5× | +64.0% | +3.1% | +13.9% | $1,673 | 64% | −31% |
| MN 2×, trend 85%, sleeve 1.5× | +65.4% | +5.7% | +15.4% | $1,773 | 71% | −35% |
| MN 2×, trend 70%, sleeve 1× | +55.2% | +7.0% | +12.3% | $1,474 | 68% | −34% |

**But the drawdown column understates MN 2×, and `max_mix.py` says so** ("the falls here are
slightly too shallow for large MN shares"). The MN book settles weekly, so its whole week lands on
one day. Measured directly:

| mix | worst DAY | worst WEEK | account left |
|---|---|---|---|
| machine v2 (today) | −24.3% | −25.3% | 75% |
| **MN 1.5×**, trend 85%, sleeve 1.5× | −36.3% | −35.8% | **64%** |
| **MN 2×**, trend 85%, sleeve 1.5× | −48.4% | −47.9% | **52%** |

**MN 2× means losing half the account in a single settlement.** That is why the recommendation is
**MN 1.5×, trend 85%, sleeve 1.5×, bids 1×**: it takes +2.8 points of sideways return and +$204 of
typical year for 7 points of fall and a −36% worst week, instead of paying a −48% week for the
rest. MN 2× is the aggressive variant, not the default.

## 5. What is NOT achieved — read this before quoting section 3

**The sideways MEDIAN stays negative at every weight tested.** MN's own monthly median in chop is
**+0.2%**, so scaling it adds mean through a fat right tail and moves the median almost not at all:

| | chop mean | chop median | up |
|---|---|---|---|
| MN 1× | −0.2% | −3.8% | 34% |
| MN 2× | +4.0% | −3.7% | 39% |
| MN 4× | +12.5% | −5.3% | 43% |

So the honest claim is **positive on average in all three markets**, not "crazy gains in every
market". A typical sideways month still loses about 4%, and only ~37% of them are up. The only
book with all-weather *shape* is the crash bids (88% of sideways months up), and doc 16 caps those
because at 1× the worst hour already leaves 46% of the account.

**Status: candidate, nothing deployed.** `combo_paper.py` on the VM is pre-registered at the old
weights and must not be edited — a new paper book at the new weights is the next step.

# Why the account halves, and what actually fixes it (2026-09-24)

*Asked for: "see why it is happening if we have both long and short", then "test all three fixes,
test everything, I don't want any edge ignored." Every number names its file. Status: **a
candidate mix, NOT deployed.** Both extra books still need their forward paper evidence.*

**Short version.**
- **The cause.** The triple book falls about 50% after booms, in sideways or even rising
  markets. Hundreds of 1h alt breakouts fail, and big stacked positions give profit back.
- **The three fixes asked for:** smaller after a boom, pause after failures, get out of stacked
  adds sooner. 56 versions were tested. **Only one beats simply betting smaller** under the strict
  check (§3), and it wins by little: the equity anchor. The pause and the early exits all fail.
- **What works: running the two independent books beside a smaller trend book.** The
  market-neutral momentum book (doc 10) made **+22%, +55% and +52%** during the trend book's
  three worst falls. The bear breadth sleeve is doc 13.
- **The mix** is trend at 70% + sleeve + half-size market-neutral. For $221 it gives a typical year of
  **$710 against today's $584**. The biggest fall goes from **53% to 36%**, and **none of the six years
  ended below $221**. It passes on all four bar phases, both halves.
- **One of the 56 fixes survived the strict check: the equity anchor** (§3). It sizes the trend
  book from the lower of equity and its 21-day average, and adds a little more on top of the mix
  (§5b).
- **Final: trend at 70% with the anchor + sleeve + half-size market-neutral.** A typical year of
  **$736**, biggest fall **35%**, **worst year $241**, worst month −19%, 63 months up in 100.
- **§8 CORRECTS THE ABOVE UPWARD.** Those figures haircut the whole mix, including the two
  point-in-time books. Measured fairly (only the trend book's gains shrunk), the same mix is worth
  **$961**. **Keeping the trend book at 100%** + anchor + sleeve 1× + market-neutral 1× gives
  **$1,210 a year against today's $592 at the same risk**, and **$1,125 against $530 over the last
  2 years**, where no year ended below $221 and the biggest fall was 45% against 58%. Taking half
  of each month's profit gives ~$31–39 a month on $221, while the account grows to ~$450–475.

---

## 1. Why — `backtest/why_drawdown.py` (log `logs/why_drawdown.txt`)

See [doc 13 §10](13-bear-breadth.md) for the full breakdown.
- **When:** the falls come after booms (the account up ×2.4–×7.9 in the prior 4 months).
- **Where:** 42% of the falls' days are chop, 42% bull and only 16% bear. BTC rose **+51%** in the
  2020 fall and **+16%** in the worst one (2024-12 → 2025-07).
- **What lost:** 94–95% of 1h long breakouts lost, 55% of the losing dollars were full stop-outs,
  and the five biggest single losses were 3–7 unit longs at −11R to −24R.
- **Units 6–7 lose on 47–49% of positions** (worst about −12R each). CLAUDE.md said "almost no
  downside"; that is corrected.
- The shorts made money in two of three falls (+6%, +46%), but they are too small to matter.

## 2. The three fixes and everything near them — `backtest/dd_fixes.py` (log `logs/dd_fixes.txt`)

**The control.** Any rule that trades less falls less. So every fix is compared with **the same book at
a uniform smaller bet** with the same drawdown (baseline at 0.4–1.0× its risk). The number that
matters is **excess**: %/mo above that line, on each half.

**The baseline.** The triple + 10× guard, entry-sized, 10 orderings. The new simulator reproduces
`triple_capped.simulate` to the last digit.

| fix | versions | best excess tune / hold | verdict |
|---|---|---|---|
| **1a** smaller while equity is up ×G in L days | 12 | every tune excess negative (−0.19 to −1.85); holdout +0.30 to +0.73 | **fails**: the mined-holdout signature |
| **1b** size from min(equity, its k-day average) | 3 | k 30: **+0.13 / +0.71**; k 90/180 fail tune | marginal, see §3 |
| **1c** halve after a d% drawdown | 2 | −0.86 / −1.58, −0.17 / −2.14 | **fails** (as in doc 02) |
| **2a** skip or halve 1h / all longs after f of the last N signals lost | 24 | "1h N20 0.8 halve": **+0.51 / +0.26**; its neighbours straddle zero. Every "skip" version is disastrous: all-long skips go to **0%/mo, 70–82% DD** | marginal, see §3 |
| **2b** 1h or all longs cut in CHOP | 4 | best −0.03 / −0.26 | **fails** |
| **3a** tighter trail past +T R | 6 | **tune drawdown RISES to 57–72%**; holdout ≤ +0.49 | **fails** (the doc 02 identification problem, again) |
| **3b** each added unit gets its own stop X R below its entry | 3 | tune DD 52–54% and lower return; holdout −0.28 to −0.92 | **fails** |
| **3c** the gross guard at 6× / 8× | 2 | −0.31 / −0.94, −0.08 / −0.47 | **fails**: just the frontier |

Registered predictions:
- 1a/1c/2b/3a/3b/3c fail: **right**.
- "at most one passes": right in spirit. Two passed marginally; §3 settles them.
- 3b was predicted "~neutral at X = 6": it fails at every X.

**The mechanism behind the kills** is the one `vol_target.py` and `equity_filter.py` found. The book's
losing stretches come *just before* its trends. Anything that shrinks or pauses after losses is
small when the next trend starts. Anything that exits winners sooner sends the money back into the
queue of new entries, most of which lose.

## 3. The two marginal survivors, strictly — `backtest/dd_fix_check.py` (log `logs/dd_fix_check.txt`)

The check uses 20 orderings, excess measured per ordering against that ordering's own frontier,
every neighbouring setting, and all four bar phases.

| config | phase 0 tune / hold | phase 1 | phase 2 | phase 3 | verdict |
|---|---|---|---|---|---|
| **anchor 14d** | +0.24 (20/20) / +0.60 (20) | +0.31 / +0.61 | +0.39 / +0.70 | +0.40 / +0.65 | **PASS** |
| **anchor 21d** | +0.22 (19) / +0.73 (20) | +0.31 / +0.72 | +0.57 / +0.76 | +0.48 / +0.73 | **PASS** |
| **anchor 30d** | +0.14 (13) / +0.69 (20) | +0.28 / +0.65 | +0.64 / +0.63 | +0.46 / +0.67 | **PASS** |
| anchor 45d / 60d | −0.06 / −0.16 on phase 0 tune | positive elsewhere | | | fails one cell |
| streak, 12 settings | tune ≈ 0, **holdout −0.4 to −2.4** on phases 1–3 | | | | **fails every setting** |

(%/mo excess over the same ordering's frontier, standard errors 0.02–0.10; wins out of 20.)

- **The pause-after-failures idea is dead**, as predicted.
- **The equity anchor is not, and I predicted it would be.** Sizing the trend book from the lower
  of equity and its 14–30 day average beats the "bet smaller" line on every phase and both halves,
  winning 19–20 of 20 orderings in most cells. It has a clean plateau from 14 to 30 days.
- **Its mechanism** is the cause §1 found: after a boom, positions stop being sized from a balance
  that just jumped.
- **It is small**: +0.2 to +0.6 %/mo on the tune half and +0.6 to +0.8 on the holdout, above the
  frontier.
- **Why it is not the doc 02 equity-curve filter:** that one cut size *after losses*. The anchor
  delays size *after gains*, and it never cuts below the current balance.

## 4. Levers the user did not name — `backtest/dd_fix_more.py` (log `logs/dd_fix_more.txt`)

| lever | excess tune | excess hold | verdict |
|---|---|---|---|
| 1h longs ×0 / ×0.5 | −0.06 / +0.50 | **−2.49 / −0.41** | fails (the 1h sleeve's losses pay for its wins) |
| 12h longs ×0.5 | +0.05 ± 0.10 (5/10) | +0.46 (10/10) | tune inside noise: not a pass |
| shorts ×0 | drawdown 63% / 75% | | the shorts ARE a hedge; removing them is worse |
| shorts ×2 | drawdown above the frontier | +1.45 | not a pass |
| **+ 0.25× market-neutral book** | **+0.81 ± 0.04 (10/10)** | **+2.34 ± 0.09 (10/10)** | **passes** |
| **+ 0.5× market-neutral book** | **+1.42 ± 0.09 (9/10)** | **+4.21 ± 0.13 (10/10)** | **passes** |
| **+ 1× breadth sleeve (real $221)** | **+1.89 ± 0.06** | **+1.27 ± 0.07** | **passes** |
| **+ sleeve + 0.5× market-neutral** | **+3.38 ± 0.08 (10/10)** | **+4.92 ± 0.20 (10/10)** | **passes** |

**Why they work where the fixes failed.** They do not trade the trend book less; they add a
different earner whose best times are the trend book's worst. During the trend book's three worst
falls (log of this computation in §6):

| fall | trend book | market-neutral at 1× | at 0.5× | breadth sleeve (real $221) |
|---|---|---|---|---|
| 2020-08 → 2020-11 | −45% | **+22%** | +11% | 0% |
| 2024-12 → 2025-07 | −55% | **+55%** | +25% | +16% |
| 2025-10 → 2026-05 | −44% | **+52%** | +27% | +1% |

## 5. The mix — `backtest/final_mix.py` (log `logs/final_mix.txt`)

**All four bar phases, both halves, 10 orderings each: every mix passes.** Sleeve + 0.5 MN: tune
+3.38 to +3.73, holdout +4.53 to +4.92 %/mo above the frontier on the four phases.

**What $221 does in 12 months** (full history, 10 orderings):
- the typical and bad-year columns are haircut on the WHOLE book, which also shrinks the two
  point-in-time books, so they understate the mixes;
- the other columns are raw.

| trend size | plus | typical year | bad year (1 in 4) | years ending < $221 | worst year | biggest fall | worst month | months up |
|---|---|---|---|---|---|---|---|---|
| **100% (today's triple)** | nothing | **$584** | $318 | **8%** | $164 | **53%** | −23.6% | 49% |
| 100% | sleeve + 0.5 MN | $840 | $408 | 1% | $210 | 47% | −24.9% | 59% |
| 80% | sleeve + 0.5 MN | $770 | $401 | 0% | $225 | 40% | −21.0% | 62% |
| **70%** | **sleeve + 0.5 MN** | **$710** | **$395** | **0%** | **$232** | **36%** | **−19.1%** | **63%** |
| 60% | sleeve + 0.5 MN | $650 | $386 | 0% | $234 | 33% | −17.1% | 65% |
| 50% | sleeve + 0.5 MN | $589 | $372 | 0% | $236 | 30% | −15.2% | 66% |

**The recommended point is trend at 70% + sleeve + half-size market-neutral.** Against today's
triple alone it gives:
- **+$126 on the typical year** ($710 against $584);
- **a smaller biggest fall: 36% against 53%;**
- **no losing year in six**, with a worst year of $232;
- a better worst month (−19% against −24%);
- 63 months up in 100, against 49.

Taking the trend book down to 50% gives today's typical year ($589) with the biggest fall at 30%.

Registered for `final_mix.py`: *"the mix passes all four phases, both halves; trend 70% + sleeve +
0.5 MN gives about today's $584 at ~35% drawdown."* Outcomes:
- the four phases: right;
- the drawdown: right (36%);
- the return: **wrong**, it was $710, not $584.

## 5b. The anchor on top of the mix — `backtest/final_anchor.py` (log `logs/final_anchor.txt`)

The mix is trend 70% + sleeve + 0.5 MN; the anchor sizes the trend book from min(equity, its 21-day
average). Each cell is the excess over the trend-only frontier, 10 orderings, paired:

| phase | tune: plain → anchored (diff, wins) | holdout: plain → anchored (diff, wins) | biggest fall |
|---|---|---|---|
| 0 | +3.21 → +3.36 (**+0.15**, 8/10) | +4.80 → +5.34 (**+0.54**, 10/10) | 33 → 32%, 32 → 31% |
| 1 | +3.21 → +3.39 (**+0.18**, 9/10) | +3.86 → +4.42 (**+0.56**, 10/10) | 35 → 33%, 31 → 30% |
| 2 | +3.65 → +4.14 (**+0.49**, 10/10) | +4.04 → +4.62 (**+0.58**, 10/10) | 34 → 32%, 32 → 31% |
| 3 | +3.63 → +4.10 (**+0.47**, 10/10) | +4.58 → +5.08 (**+0.50**, 10/10) | 34 → 32%, 32 → 32% |

**The final menu**, for $221 over 12 months (full history, deployed grid, 10 orderings; upside
haircut on the whole book, downside raw):

| book | typical year | bad year | good year | years < $221 | worst year | biggest fall | worst month | months up |
|---|---|---|---|---|---|---|---|---|
| today: triple alone | $584 | $318 | $1,761 | 8% | $164 | 53% | −23.6% | 49% |
| triple alone + anchor | $609 | $326 | $1,853 | 6% | $167 | 51% | −22.5% | 49% |
| trend 70% + sleeve + 0.5 MN | $710 | $395 | $1,656 | 0% | $232 | 36% | −19.1% | 63% |
| **trend 70% + anchor + sleeve + 0.5 MN** | **$736** | **$411** | $1,691 | **0%** | **$241** | **35%** | **−19.1%** | **63%** |
| trend 80% + anchor + sleeve + 0.5 MN | $800 | $420 | $1,994 | 0% | $236 | 38% | −21.0% | 62% |
| trend 100% + anchor + sleeve + 0.5 MN | $881 | $430 | $2,408 | 0% | $224 | 45% | −24.9% | 60% |

Registered: *"the anchor adds +0.3 to +0.6 %/mo on both halves on all four phases and trims the
biggest fall by 2–4 points."* Outcomes:
- the holdout half: right;
- the tune half: **under** on phases 0–1 (+0.15, +0.18);
- the fall: trimmed 1–2 points, not 2–4.

## 6. What is not settled

- **Both extra books are unproven live.**
  - The market-neutral book has been on paper since 2026-09-23 (`mn_paper.py`, verdict at 26
    rebalances).
  - The sleeve has no paper book yet, and a bull regime runs today.
- **The market-neutral book's own risk.** Its worst week at 1× is −24% (`logs/carry_check.txt`).
  Here it is booked weekly, so its swings inside a week are invisible and the mix's drawdown is
  slightly understated.
- **Margin.** The bot's 10× guard sees only the trend book. The MN book adds 0.5× gross, so the
  live guard should be ~9.5× for the trend side.
- **Minimum orders.** The sleeve is modelled with the $5 minimum; the MN book is not. At 0.5× on
  $221 it holds 6 + 6 coins at ~$9 each: above the minimum, but thin.
- **The haircut** is applied to the whole mix, which understates the two books that need none.
- **The holdout is mined** (CLAUDE.md §2). What stands apart from it: the four-phase pass, the MN
  book's independent validation (doc 10), and the sleeve's out-of-sample 2018 replication (doc 13).

The three-fall table in §4 was computed inline from `bear_chop.fast_run` (MN, exact funding window)
and `logs/breadth_real_1x.pkl` (sleeve), over the fall windows in `logs/why_drawdown.txt`.

## 7. What can be withdrawn each month — `backtest/withdraw.py` (log `logs/withdraw.txt`)

**Method.** Monthly returns come from month-end equity, 10 orderings. "Safer" means up-months are
haircut (`expectations.haircut(x, 1)`) and down-months are raw. Each plan was run on every
12-month stretch, starting from $221.

| | bot alone, last 2 yrs | bot alone, 6 yrs | **final mix, last 2 yrs** | **final mix, 6 yrs** |
|---|---|---|---|---|
| typical month | −0.2% ($0) | −0.3% ($−1) | **+3.2% ($+7)** | **+2.4% ($+5)** |
| bad month (1 in 4) | −9.6% | −8.2% | −3.2% | −3.8% |
| good month (1 in 4) | +12.4% | +11.3% | +10.0% | +13.6% |
| months up | 50% | 49% | **67%** | **63%** |
| **Plan A**: take out everything above $221 monthly | $497/yr ($41/mo) | $553/yr ($46/mo) | $490/yr ($41/mo) | $552/yr ($46/mo) |
| Plan A: year ends with the $221 dented | 58% | 73% | 37% | 55% |
| **Plan B**: take out half of each month's profit | $326/yr ($27/mo) | $376/yr ($31/mo) | $321/yr ($27/mo) | $407/yr ($34/mo) |
| Plan B: balance left after 12 months | $389 | $434 | **$478** | **$503** |
| Plan B: balance below $221 | 13% | 23% | **8%** | 15% |

**The "average month" is not usable.** It reads +25% to +35%, because a few enormous months dominate
it; the typical month is +2–3% for the mix and ~0 for the bot alone. The withdrawals are lumpy,
because most of a year's money arrives in one or two months.

Registered: *"typical month for the mix +2% to +5%; Plan A ~$15–30/month; about a third of
stretches take out almost nothing for months."* Outcomes:
- the typical month: right;
- Plan A: **wrong**, it took out $41–46/month, more than predicted;
- the "almost nothing for months" part was not measured as stated.

## 8. Measured fairly, and scaled to today's risk — `backtest/max_mix.py` (logs `logs/max_mix.txt`, `logs/max_mix_pick.txt`)

The user said the combination's value was understated. **It was.** §5–§7 applied the 3× hindsight
haircut to the WHOLE mix, including the two point-in-time books that need none. §7 then haircut
every up-month again.

**The fair method: shrink the trend book's gains, keep its losses.** Every positive daily trend
return is multiplied by s = 0.733 (0.726–0.739 across orderings), solved so the deployed triple's
growth equals raw CAGR / 3. Losses stay whole, and the two point-in-time books stay raw.
- **Check:** today's triple reads $592 typical under this method, against $584 by the repo's
  haircut.
- **The price:** its fall reads 63% here against 53% raw, because shrinking the gains slows the
  recoveries. This is conservative.

**A first attempt was replaced before use.** It spread the haircut as a constant daily drag. It
matched the typical year ($560) but put today's triple at an 84% fall and a $69 worst year.
Hindsight inflates the winners, not the losers.

**Under the fair method, doc 14's own pick** (trend 70% + anchor + sleeve + 0.5 MN) is worth **$961
a year, not $736**, with a 43% fall and 4% of years below $221.

**The user's idea: keep the trend book at 100% and let the other books carry the bad times.** The
grid covered 105 mixes: trend 70–130% + anchor, sleeve 1–2×, and market-neutral 0.5–1× fixed or
sized by regime (small in bull, large in chop/bear). **79 of them fall no more than today's 63%.**

| $221, 12 months (fair) | typical year | bad year | years < $221 | worst year | fall | worst month | months up | typical month | take ½ profit: /month, balance left | take all above $221: /month |
|---|---|---|---|---|---|---|---|---|---|---|
| **today: triple alone** | $592 | $269 | 21% | $121 | 63% | −24.5% | 39% | −$7 | $22, $301 | $32 |
| trend 85% + anchor, sleeve 1×, MN 1× | $1,183 | $506 | 8% | $161 | 56% | −26.3% | 56% | +$10 | $37, $481 | $48 |
| **trend 100% + anchor, sleeve 1×, MN 1×** | **$1,210** | $491 | 9% | $151 | 59% | −29.0% | 56% | +$9 | **$39, $475** | **$51** |
| trend 100% + anchor, sleeve 1.5×, MN 1× | $1,261 | $516 | 7% | $155 | 61% | −29.0% | 57% | +$12 | $43, $487 | $53 |
| trend 100% + anchor, sleeve 2×, MN 1× (grid best) | $1,304 | $568 | 5% | $156 | 62% | −30.0% | 57% | +$12 | $45, $492 | $57 |

**The same mixes over the last 2 years only** (from 2024-08-29):

| | typical year | years < $221 | worst year | fall | months up | take ½ profit: /month, balance | take all above $221: /month |
|---|---|---|---|---|---|---|---|
| today: triple alone | $530 | 11% | $134 | 58% | 37% | $19, $284 | $28 |
| **trend 100% + anchor, sleeve 1×, MN 1×** | **$1,125** | **0%** | $312 | **45%** | **63%** | $31, $452 | $41 |
| trend 85% + anchor, sleeve 1×, MN 1× | $1,130 | 0% | $328 | 41% | 63% | $32, $459 | $42 |

**What the grid says.**
- **The user's regime idea ties** the fixed sizing: $1,299 against $1,304 at an equal fall. Keep
  the simpler fixed version.
- **The sleeve at 2× tops the grid, but it is not recommended.** Its out-of-sample 2018 fall was
  42% at 1× (doc 13 §7), so 2× could lose ~70% in a 2018-like bear on its own. It adds only
  $50–100 a year over 1×.
- **Trend 85% gives nearly the same** as 100% (−$27 a year) with a 3–4 point smaller fall.
- **The market-neutral book at 1× is the single largest lever**, and the least measured risk. It
  is booked weekly, so its swings inside a week (worst week −24% at 1×, `logs/carry_check.txt`)
  do not show in these falls.

Registered: *"today ≈ $584 at a ~60% fall; the best mix at today's risk $1,300–1,800; take-half
$60–90/month; the regime-sized MN beats the fixed one."* Outcomes:
- today: right;
- the best mix: right, at the bottom of the range ($1,304);
- **take-half: wrong**, $39–45/month;
- **the regime idea: wrong**, it ties.

**Why the monthly income stays modest on $221, and what changes it.** The mix roughly doubles the
typical year, and in dollars that is still ~$40–50 a month on $221. The percentage does not depend
on capital above ~$25 (CLAUDE.md §6), so dollars scale with capital. At the same mix:
- ~$1,000 would give ~$175–230 a month;
- ~$2,000 would give ~$350–460 a month.
This is arithmetic on these backtest rates, not a separate measurement.

## 9. The paper book — `combo_paper.py` (ON THE VM since 2026-09-24 12:40:12 UTC, `combo-paper.service`)

The mix from §8 runs forward as ONE $221 paper account. It places no orders anywhere.

**Frozen, pre-registered in the file's docstring:**
- **trend** is `blend_paper.cycle(triple=True)` itself, sized by the 21-day equity anchor, with a
  9× gross guard;
- **market-neutral** is `mn_paper.py`'s own functions at 1×;
- **bear sleeve** at 1× uses thresholds 0.100 / 0.288, a 7-day ladder, a 5-coin basket and the
  $5 minimum.

**Verdict at 6 months:**
- H1: beats the triple paper book's growth over the same days;
- H2: its biggest fall is smaller;
- H3: more of its months are up;
- H4: the three components' daily P&L are close to uncorrelated.

A window with no bear regime tests only trend + MN, and the verdict must say so.

**Safety.** It imports `blend_paper.py` and `mn_paper.py` and patches their trade and log paths
**in its own process only**. `tests/test_combo_paper.py` checks that, plus:
- the anchor never exceeds equity and lags a boom;
- the ladder holds each decision exactly 7 days, starting the day after;
- the $5 rule always allows a close;
- the live bear label equals `market_neutral.btc_regime` on 320 synthetic days covering all
  three regimes.

**First poll** (`logs/combo_paper.log`):
- the MN basket opened 12 names at $18.42 each;
- the sleeve was idle (BTC regime bull, breadth20 85%);
- the trend book took 3 LTC longs.

**One difference from `mn_paper.py`, on purpose.** Funding is counted from the previous daily
CLOSE + 1 ms. `mn_paper.py` counts from the previous bar's OPEN, which appears to count each
day's settlements about twice (flagged separately; that book is pre-registered, so it was not
edited here).

**Where it runs.** Locally, next to `mn_paper.py`, and `python health.py` reports it.
`deploy/combo-paper.service` is ready for the VM. Stop the local copy first, and carry
`logs/combo_state.json` + `logs/combo_*.csv` across, or the record restarts.

## 10. The final version by market type — `backtest/final_regimes.py` (log `logs/final_regimes.txt`)

The book is the trend book at 100% + anchor + sleeve 1× + MN 1×. Method as §8. Months are labelled
by the BTC regime most of their days carried, over 10 orderings.

| | rising: avg / typical / months up | sideways | falling |
|---|---|---|---|
| triple alone | +58.2% / +14.6% / 64% | −5.4% / −8.1% / 22% | −3.5% / −3.5% / 25% |
| **final** | **+67.4% / +19.1% / 69%** | **−1.3% / −6.4% / 33%** | **+7.6% / +4.7% / 64%** |
| typical month on $221 | +$32 → **+$42** | −$18 → **−$14** | −$8 → **+$10** |
| worst month | −30% → −35% | −25% → −30% | −16% → −18% |

What each part adds in an average month:

| | trend | market-neutral | bear sleeve |
|---|---|---|---|
| rising | +56.1% | +4.6% | 0 |
| sideways | −5.2% | **+4.3%** | −0.7% |
| falling | −3.4% | +4.5% | **+7.2%** |

Registered: *"the trend book earns in bull and is ~flat in chop and slightly negative in bear;
the MN book lifts chop to positive; the sleeve + MN turn bear positive; bull is almost
unchanged."* Outcomes:
- bear turns positive: right;
- **chop does NOT turn positive: wrong.** Under the fair method the trend book loses 5.2% a month
  in chop, and the MN book's +4.3% does not quite cover it;
- **bull is not unchanged: wrong.** The MN book adds ~4.6% a month there too;
- the worst month in each regime is a few points worse, because the extra books add exposure.

**VM install.** `deploy/install_combo.sh` does one paste after `pull_and_rebuild.sh`. It checks
combo_paper.py's sha256, compiles it, runs its tests, installs `combo-paper.service`, starts it
and prints the status and free memory. It has 51 lines, all under 44 characters, with no
backslashes. It was run whole against a fake target with stubbed `systemctl`, `sudo`, `chown`,
`journalctl` and `sleep`; the first run caught a 46-character line.

**Deployed 2026-09-24.** `pull_and_rebuild.sh` then `install_combo.sh` on the VM printed:
- HASH_OK, SYNTAX_OK, 7 passed, `active`, `clean`;
- memory 421 MB available of 896 MB;
- the first poll opened the MN basket (12 names at $18.42) and took 3 trend trades (LTC 4h and
  12h long, WLD 4h short);
- it read the triple paper book for H1 (x0.999 against x1.000 on day 0).

The local run (07:12–12:45 UTC) was stopped and its files archived in
`logs/combo_local_stopped_20260924/` (gitignored), so **the VM holds the only record**. The
verdict is due ~2027-03-24.

## 11. The live bot — `combo_bot.py` (demo from 2026-09-24, local), `tests/test_combo_bot.py`

**Why it was built.** The user did not want to wait until March, and chose: *build the live
version, test it 2 weeks on demo, then decide on real money*.

**Two findings changed the plan:**
- **Bitget's demo lists only 3 coins** (SBTC/SETH/SXRP). A demo cannot run the combination.
- **`longtrend_bot.py`'s live mode trades a 9-coin list that is not the validated 12-coin book.**

**How it is built.**
- **Decisions** are `combo_paper.py`'s own three books.
- **Execution nets them per coin.** One account in one-way mode holds one net position per coin,
  so the bot sends one order per coin for the difference.
- **The two-week proof has two parts:**
  - **demo** routes every coin onto the 3 demo contracts by dollar value, which stress-tests the
    order path;
  - **dry** runs every coin against Bitget's REAL market list with no orders.

**Safety:**
- `ALLOW_REAL = False`;
- it refuses to start beside `longtrend_bot.py` or another combo bot (checked by pid);
- **cross margin**: isolated 10× liquidates alts inside their own 4h/12h stops;
- a 30% disaster stop per net position;
- a price-sanity refusal when the venue and Binance differ by more than 3%;
- the $5 minimum, except that a full close always goes.

**Found by running it, not by the tests:**
1. **Intrabar trend stops.** The paper engine judges a stop at the bar close, which live would
   mean up to 12h late. The live price is now checked against every trend stop each poll, and the
   breach is sticky.
2. **Warm start.** The first dry run "entered" LTC 12h at a close from hours earlier: 62.04
   against a live 66.90, 8% away. Signals now come only from bars that close after the process
   starts.
3. **A fresh-state crash** (`KeyError: 'exec'`).
4. **Fills logged as 'assumed'.** Bitget's order response carries no fill price, so fills are
   now read back by order id.

**Tests.** 14 offline tests on a fake one-way exchange that rejects a reduce-only order growing a
position. Three mutations (no close-then-open split, price sanity off, non-sticky breach) are
each caught.

**First demo poll** (2026-09-24 13:02 UTC):
- it reduced and closed the old bot's 3 leftovers and flipped SETH as close + open;
- it placed 3 disaster stops, all accepted by Bitget;
- real fills read back from Bitget sit within ~1bp of the reference.

A restart sent no duplicate orders.

**The check, around 2026-10-08:**

```bash
python combo_bot.py --mode demo --report
```

```bash
python combo_bot.py --mode dry --report
```

**PASS** needs:
- no order failures;
- no stop-placement failures;
- no poll errors;
- every fill priced;
- slippage within a few bp;
- at least one open, add, reduce, close and flip.

After that, going live is the user's decision: they set `ALLOW_REAL = True` in `combo_bot.py`,
use a DEDICATED account of about $221 or more, and run `--mode live`.

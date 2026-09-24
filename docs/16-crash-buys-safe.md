# Crash buys made safe, the worst month, and coming back (2026-09-25)

*Asked for: "go deeper… make this better, reduce the worst month, and hypothetically if there is a
worse month can the capital go back up again on its own". Follows [doc 15](15-crash-wicks.md). Every
number names its file. Status: **a candidate, NOT deployed; the paper book `wick_paper.py` is
built and pre-registered (section 7).***

**Short version.**
- **Two changes make the crash buys better**, and they pass the "just bet smaller" test on both
  halves:
  - skip days the BTC label calls BEAR;
  - spread the bids over the top-40 coins instead of the top-20.
  The crash-buy book's own worst month goes from **−22% to −1% / −3%** (tune / holdout).
- **Doc 15's book hid a near-wipe-out.**
  - Five-minute bars show the price keeps falling after a bid fills.
  - On 2025-10-10 21:00 every bid filled and sank together: the book's paper loss inside that hour
    was **−52% of the account**.
  - Together with the trend book's losses that hour, **10% of the account was left** (ordering 0).
  - **Fix:** cancel the remaining bids once 10 have filled in an hour. That leaves 47% (trend alone:
    62%) and keeps +16%/yr.
- **Nothing shrinks the worst month better than betting smaller.** Sixteen monthly "brakes" (on
  the trend book, and on the whole account) all fail.
- **Coming back:**
  - Every 20%+ fall in six years recovered.
  - A made-up −50% month recovers within 24 months in 100% of starts at the backtest's growth, and
    in 52–62% if the bot only grows +25–50% a year.
  - **Withdrawing $20 a month through a loss** leaves most accounts near zero. Pausing withdrawals
    until the balance is back above its start removes that.

---

## 1. Better crash buys — `backtest/wick_better.py` (logs `wick_better.txt`, `wick_better_combos.txt`)

**Setup:** $300, Bitget's $5 minimum, 8bp fees plus 30bp of crash-hour slippage, dead coins
included. The baseline is doc 15's book: top-20, bids 10% under the last close, sold at the fill
hour's close.

| rule | TUNE | worst month | HOLDOUT | worst month | fall |
|---|---|---|---|---|---|
| doc 15 book (top-20) | +40.2% | −22.4% | +9.4% | −5.2% | 23% |
| top-40 | +40.8% | −13.9% | +16.1% | −4.6% | 15% |
| top-20, skip BEAR days | +37.8% | −2.2% | +15.5% | −4.2% | 8% |
| **top-40, skip BEAR days** | **+37.0%** | **−1.2%** | **+16.9%** | **−3.3%** | **9%** |

- **"Beats just betting smaller"** means the rule earns more than doc 15's book resized to the same
  worst month. Top-40 + skip BEAR earns **+34.9 points more on tune and +10.9 points more on
  holdout**: a PASS.
- **By year** (top-40 + skip BEAR): 2020 +20%, 2021 +124%, 2022 +6%, 2023 +20%, 2024 +38%, 2025 +13%,
  2026 +10%.
- **Months:** 74% up, 15% flat.

**Why skipping bear days works.** Per fill, after costs (top-20):
- bull days +2.98%;
- chop days +1.62%;
- **bear days +0.12%** (tune +0.82%, holdout −0.88%).

In a bear market a 10% wick is usually a coin that keeps falling, not a forced seller. LUNA's five
fills in May 2022 were all on bear days. The rule uses the same BTC label as the bear sleeve (doc
13), which is known at the start of each day. The two dovetail: the sleeve buys capitulation in
bears, and the crash bids buy wicks outside them.

**What did not help:**
- **Closer bids.**
  - 6%: holdout −4.3%/yr.
  - 8%: holdout +5.7%/yr.
- **Bids scaled to each coin's volatility.** 8× gives holdout +21.1% but tune only +25.8%: fails on
  tune.
- **Two bids per coin (a ladder):** about a size change.
- **Bids under the 3-hour high:** holdout −3.2%/yr (a slide is not a wick).
- **Selling at the next hour's close:** holdout −4.2%/yr.
- **Top-60:** $5 per bid on $300, which the minimum rejects.
- **No second fill on a coin within 24h,** and **skipping coins down >25% in 24h:** both pass alone,
  but add nothing on top of skipping BEAR.
- **A pump filter** (skip coins up >50% in 24h). It was picked from the worst-fills list of the same
  data, so it is listed and not adopted.

Registered predictions (in the file):
- right on the universe, closer bids, the reference and the exit;
- **wrong on skipping BEAR days.** I expected it to cost growth ("bear wicks bounce too"). They do
  not.

## 2. Inside the hour — `backtest/wick_5m.py` (logs `wick_5m.txt`, `wick_5m_caps.txt`)

Binance's 5-minute klines were fetched for the three hours from every fill: 4,345 fill hours on the
top-40, which include the top-20's, dead coins included.

**What the hourly model got right:**
- a 5-minute bar goes through the bid on **100%** of the hourly fills;
- the fill price is the same;
- half of the fills come after minute 30.

**What the hourly model could not see.** After the fill, the price kept falling before the hour
ended (top-40):
- median **−3.9%**;
- 1 in 4 fills −8.4%;
- 1 in 20 fills **−22.5%**.

I predicted −2% and 1 in 20 at −10%: **wrong, it is worse.**

Summed over the book, with every fill at its low at once, the **paper loss inside one hour** was
−52% of the account (top-40, 2025-10-10 21:00) and −50% for doc 15's top-20. That hour does not
appear in any daily or hourly-close test, because the hour ended with a profit.

**Exits (top-40 skip-BEAR, per fill after costs, tune / holdout):**
- **the hour's close: +2.83% / +1.32%.** Still the rule.
- the fill bar's close: −0.15% / +0.45%. The bounce takes minutes, not seconds.
- resting sell orders +2% to +8% above the fill: all lower on tune.
- stops 5% / 10% under the fill: lose.
- **+120 minutes after the fill: +4.29% / +1.65%**, better on both halves. This was found after the
  fact, so it is to be *recorded* by a forward test, not adopted.

**The cap: cancel the remaining bids after the first K fills in an hour** (a live bot can do this).

| top-40 skip-BEAR | CAGR | tune | holdout | worst in-hour paper loss |
|---|---|---|---|---|
| no cap | +30.0% | +36.1% | +17.3% | −51.7% |
| cancel after 20 | +23.6% | +27.7% | +15.0% | −30.6% |
| **cancel after 10** | **+16.3%** | **+18.5%** | **+11.4%** | **−15.8%** |
| cancel after 5 | +10.5% | +11.6% | +7.9% | −8.4% |

- **Cost:** the big waves carry most of the profit, so capping costs more than I predicted (I
  expected 10–15% of growth for cap 10; it cost ~46%).
- **Still better than betting smaller:** uniform sizing down to a −16% in-hour loss would earn about
  +8–10%.

## 3. The worst hour for the whole account — `backtest/joint_worst_hour.py` (log `joint_worst_hour.txt`)

The trend book and the crash bids lose in the **same** hour, on the same (cross-margin) account.
The table shows the account left, each part at its worst price of the hour:

| ordering | trend alone | + bids, no cap | cap 20 | **cap 10** | cap 5 |
|---|---|---|---|---|---|
| 0 | 62% | **10%** | 30% | **47%** | 54% |
| 1 | 88% | 49% | 69% | 86% | 88% |
| 2 | 89% | 43% | 63% | 80% | 86% |

- **The hour:** with the bids on, the worst hour is 2025-10-10 21:00 in every cell but one. The
  exception is ordering 1 at cap 5, where the trend book's own 2023-07-14 hour stays worst.
- **What the registered prediction said:** "~10–15% left with no cap, ~30% cap 20, ~45% cap 10".
  Right.
- **Why 10% left means liquidation:** open positions of about 2× the account's starting value would
  sit against 10% of it, which is ~20× leverage. That is where the exchange starts closing positions.
- **Scope:** this rules out doc 15's book as it was written, and any size above cap 10.

## 4. The worst month — `backtest/worst_month.py` (log `worst_month.txt`)

$300, 10 orderings, trend gains shrunk for hindsight and losses whole (max_mix.py's method).

**What made the worst months** (final + doc 15 bids, the mean month and each book's own return):

| month | account | trend | MN | sleeve | bids |
|---|---|---|---|---|---|
| 2022-05 | −35.5% | −0.4% | −2.6% | −13.1% | **−22.4%** |
| 2023-10 | −27.5% | −21.0% | −9.1% | +0.3% | +0.6% |
| 2026-04 | −25.1% | −11.2% | −11.4% | −0.7% | −4.4% |
| 2023-03 | −22.3% | −10.3% | −13.8% | 0.0% | +0.6% |

- **With the new capped bids, May 2022 falls to −16.7%.** The worst months are then trend + MN
  months (2023-10 −27.7%, 2026-04 −24.4%), the same as the final version without bids.
- I predicted "trend months after booms, the bids costing 5–7 points in May 2022": **wrong.** The
  bids cost 22 points and the sleeve 13.

**What shrinks it, judged against "everything smaller" at the same worst month, on both halves:**

| $300, typical year: 6 yrs / last 2 yrs | worst month: 6 yrs / last 2 yrs | vs smaller: tune / holdout | |
|---|---|---|---|
| final, no bids | $1,642 / $1,527 | −29.0% / −23.1% | +$154 / +$13 | pass |
| final + doc 15 bids | $1,937 / $1,629 | −35.5% / −25.4% | (the reference) | — |
| **final + new bids, cancel after 10** | **$1,812 / $1,625** | **−29.3% / −25.0%** | +$507 / +$14 | pass |
| final + new bids, cancel after 20 | $1,930 / $1,666 | −29.2% / −25.0% | +$700 / +$56 | pass |
| everything ×0.7 | $1,510 / $1,267 | −25.5% / −18.5% | (the frontier) | — |
| everything ×0.5 | $1,106 / $958 | −18.5% / −13.5% | (the frontier) | — |
| account brake, −20% this month → ×0.5 | $1,812 / $1,472 | −30.5% / −23.0% | +$163 / −$39 | fail |
| account brake, −10% → ×0 | $683 / $352 | −26.4% / −18.8% | −$1,048 / −$934 | fail |
| trend brake, −20% this month → ×0.25 | $1,780 / $1,551 | −35.5% / −25.4% | −$344 / −$78 | fail |

**All 16 brake variants fail.** That is 6 account brakes, 8 trend brakes (2 of them rolling), and 2
account brakes on top of the new bids. A bad month is usually followed by the
recovery. A brake sits out the recovery, and that costs more than it saves. This is the same answer
doc 14 got for 56 drawdown fixes.

**The only dial that shrinks the worst month is size.** Everything at ×0.7 gives a worst month of
−25.5% and a typical year of $1,510. At ×0.5 the figures are −18.5% and $1,106.

**The new bids earn little over no bids in the last 2 years:** +$98 on the typical year, with the
worst month −1.9 points worse. I predicted "within 1 point": wrong by 0.9.

## 5. Coming back — `backtest/worst_month.py` (C1, C2) and `--stress` (logs `worst_month_stress*.txt`)

**History** (final + new capped bids):
- 172 falls of 20%+ across 10 orderings, and **all 172 recovered**;
- from the low back to the old high: median 14 days, 3 in 4 within 28 days, longest 232 days.

The deepest in ordering 0:
- −55%, 2024-04 → 2024-11 (219 days down), back in 30 days;
- −44%, 2026-02 → 2026-05, back in 113 days;
- −43%, 2023-02 → 2023-05, back in 185 days.

With doc 15's bids the longest was 538 days (2022–23). I predicted a median of 3–6 months: **wrong,
the returns come back faster** (the book's up-months are very large).

**A shock that never happened.** $300 loses S at the start of a month, from every month 2020-01 to
2024-09, then lives through the real days that followed. The simulation includes the small-balance
penalties: the $5 minimum rejects trend units below ~$150, the MN book stops under $60, and the
bids shrink under $200.

Share of starts back at $300 within 12 / 24 months:

| shock | backtest growth | growth at +50%/yr | growth at +25%/yr |
|---|---|---|---|
| −30% ($210) | 91% / 100% | 65% / 75% | 61% / 67% |
| −50% ($150) | 80% / 100% (median 4.4 months) | 51% / 62% (11.7 months) | 45% / 52% (18.6 months) |
| −70% ($90) | 66% / 96% | 17% / 32% | 8% / 23% |

These figures assume no withdrawals. **Withdrawing $20 a month straight through the loss**, after a
−50% shock:
- backtest growth: 48% of starts back in 24 months, and the typical balance after 24 months is **$16**;
- at +25%/yr: 8% back.

**Pausing withdrawals while under $300** gives the same result as no withdrawals.

**How the stress was done** (the growth-rate columns): every up-day was shrunk by the factor that
makes the plan grow at that rate, which is the hindsight-haircut method. **A first version halved
every up-day instead,** and the account lost money even without a shock (12% back after −50%). That
does not mean "earns half". It removes the edge, because a volatile book's up-days only slightly
outweigh its down-days. It is kept in `logs/worst_month_stress_gains_halved.txt`, and the prediction
it was registered with ("~65%") is recorded as wrong because the question was wrong.

**So, in plain words:**
- The bot sizes every bet as a share of the balance. A loss makes the bets smaller; it does not
  stop the bot.
- It comes back **if the edge is real and you stop withdrawing while it is under water.**
- Below ~$150 the $5 minimum starts to bite.
- The one loss it cannot come back from is **liquidation inside one hour**. That is why the bids
  are capped.

## 6. The recommended crash-buy rule, and what is not settled

**The rule:**
1. Every hour, place a buy 10% under the last close on each of the PIT top-40 perps, 1/40 of
   equity each ($7.50 on $300).
2. Place no bids on days the BTC label calls BEAR.
3. Cancel the remaining bids once 10 have filled in the hour.
4. Sell everything at the end of the fill hour.

**Its numbers:**
- on its own: +16.3%/yr (tune +18.5%, holdout +11.4%), worst month −3.3%;
- with the final version, on $300: typical year $1,812 (6 years) and $1,625 (last 2 years), against
  $1,642 / $1,527 without it;
- the worst month is about unchanged.

**Not settled:**
- **The venue.** Bitget's wicks are shallower (doc 15). Its 1-minute history does reach 2025-10-10
  (section 7): that night 35 of the 40 bids filled on Bitget, against 38 on Binance.
- **Execution.**
  - 40 resting bids have to be re-placed every hour, and the bot must count fills in real time to
    cancel after 10.
  - On a netted account, a fill on a coin the trend book holds changes that coin's net position for
    up to an hour.
  - None of this exists in `combo_bot.py`.
- **Decay.** The holdout is about half of tune.
- **The mined split.** The holdout has been used heavily (CLAUDE.md §2). Skipping BEAR days and top-40
  were chosen on it among ~25 variants, so **the forward paper book decides** (section 7).
- **Recent weakness.** On Binance, per kept fill after costs: Jan–Jun 2026 **−0.37%**, Jul–Sep 2026
  +2.77%. The last 12 months average +0.79% (standard error 0.38). This is not a steady edge.

## 7. The paper book — `wick_paper.py` (pre-registered, 2026-09-25)

**The rule, run forward:** section 6's rule, computed after each hour closes from 1-minute candles,
on **two venues** with the same 40 coins:
- **Binance:** does the edge persist on the venue it was found on?
- **Bitget:** does it exist where the money would be?

Each venue has a $300 hour-close ledger. A second $300 ledger sells the same fills 120 minutes after
the fill, and is recorded, not adopted. The book places no orders and uses public data only.

**Registered in the file:**
- **H1 (Bitget)** and **H2 (Binance):** mean net return per kept fill above zero.
- **H3:** Bitget has fewer fills before the cap, and a mean per fill no more than 0.5 points below
  Binance's.
- **H4:** the in-hour paper loss never goes below −20%.
- **H5:** the +120-minute ledger beats the hour close.

**When it decides:**
- the verdict comes at 6 months if Bitget has 60+ kept fills, otherwise at 12;
- **H1 false at 12 months drops the crash bids;**
- H4 false at any time means stop and report.

**Expected, from the backtest on Binance:**
- +0.8% to +1.0% per kept fill, 35–52 kept fills a month;
- a 6-month read (~200–300 fills, standard error ~0.6%) can only fail a dead edge. It cannot prove
  a live one.

**Checked before it runs:**
- **13 offline tests** (`tests/test_wick_paper.py`). Six deliberate breaks each fail at least one:
  no cap, no slippage, a touch counts as a fill, bids on BEAR days, a fill at the bid through a gap,
  and a cap by name instead of time.
- **A replay on six past crash hours with both venues' real 1-minute data**
  (`backtest/wick_replay.py`, `logs/wick_replay.txt`):
  - Binance keeps the same 10 fills per hour as the backtest.
  - The hour's P&L has the same sign every time. It is within a fifth on 3 of 6 hours, because
    *which* ten the cap keeps depends on the fill order.
  - **2025-10-10 21:00:** Bitget 35 fills, Binance 38. The capped book lost $8.01 / $7.93 on $300.
    Its in-hour paper loss was −16.0% / −16.3%, deeper on 1-minute bars than the 5-minute
    backtest's −15.8%. That is why H4's limit is −20%, set before the start.
  - The next hour, 22:00, made +$6.55 / +$5.39.
- **The installer** (`deploy/install_wick.sh`, service `deploy/wick-paper.service`) was run whole
  against a fake VM with stubbed system commands. It aborts on a changed file (hash) and on a
  failing test.

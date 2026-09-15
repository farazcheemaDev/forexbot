# Reverse-Engineering the NASDAQ Scalping Strategy

Analysis of a screen recording (Vertex Trader Pro / cTrader) of a managed account
returning ~10%/month. Account: ~5 lakh PKR (~$1,800) in Jan 2026, later doubled.
Operated by a trader/**team** (per account owner) — so treat this as a *systematic*
process, not individual discretion.

Goal: extract enough rules to build a **signals system** (alerts), and possibly a bot.

---

## 1. What he trades
- **Primary: NASDAQ** (US Tech 100 index / front-month futures — "NASDAQ Sep/June/Mar").
- Secondary: **GOLD (XAUUSD)**, occasional **SILVER**.
- Ignore FX. It's an index/metals scalper.

## 2. Style (confirmed)
- **Scalping**: holds **30 seconds – 4 minutes**.
- **Small targets**: 5–18 points, typically 6–9 pts (~$60–270 on 0.10–0.20 lots).
- **Both directions** (buys bottoms, sells tops — flips around a range).
- **Small consistent lots** 0.05–0.20 (scales with account size, NOT martingale).
- **Cuts losers small** (saw −$24, −$35) → high win rate (~70–90%), real losses exist.

## 3. The cracked logic: LEVEL FADE
Fades price when it stretches INTO a level, then reverts:
- **25-POINT round levels** — the key discovery. 8 of 9 sampled entries sat within
  ~8 pts of a 25-level: 30300, 30000, 29750, 28325, 29825. He fades quarter-hundreds.
- **Prior-day / session high–low** (liquidity levels).
- Sells resistance (top of range / round level), buys support (bottom).
- Proof: on 08-07 he BOUGHT 29742.50 → sold exit 29751.25, then immediately
  SHORTED 29752.25 → covered 29745.25. Buying the bottom and selling the top of a
  tight 29742–29752 range.

## 4. Timing
Entry times (his server, ~GMT+3) cluster in the **US afternoon session**.
Converted to ET (≈ server − 7h): most entries fall **~13:00–15:00 ET** (US "power hour"
run-up), a few at the cash close (~16:00 ET) and premarket. A team could follow this
as a scheduled window.

## 5. Reconstructed trade log (from the recording)
| Date | Open time | Side | Open→Close | Pts | Hold |
|------|-----------|------|-----------|-----|------|
| 07-01 | 20:39:33 | SELL | 30305.75→30299.25 | 6.5 | 30s |
| 07-01 | 20:40:20 | SELL | 30305.25→30290.00 | 15.25 | 51s |
| 07-10 | 14:11:46 | BUY  | 29786.25→29790.50 | 4.25 | 1m39 |
| 07-10 | 21:18:29 | BUY  | 30005.00→30012.00 | 7 | 1m44 |
| 07-24 | 23:57:02 | SELL | 28323.75→28317.50 | 6.25 | 56s |
| 08-07 | 21:59:59 | BUY  | 29742.50→29751.25 | 8.75 | 2m29 |
| 08-07 | 22:03:15 | SELL | 29752.25→29745.25 | 7 | 84s |
| 08-11 | 03:30:21 | SELL | 29748.75→29730.00 | 18.75 | 3m44 |
(Earlier gold/silver trades Feb–Jun also present; losers seen: −$24, −$35.)

## 6. Tests run so far (all on NQ=F / our data, realistic costs)
| Approach | Win rate | Robust (in+out positive)? |
|----------|----------|---------------------------|
| Bollinger fade | 66–72% | NO |
| ADX-filtered fade | high | NO (0/48) |
| Momentum breakout scalp | 32–46% | NO (lost 34–56%/mo) |
| Level fade (25/50/100 + prior-day, RSI) | **70–75%** | NO (in-sample always negative) |

Pattern: every mechanical version reproduces his **win rate** but **not his profit**.

## 7. Systematic hypotheses — TESTED (team-followable)
| Rule | Win% (OOS) | OOS PF | Robust? |
|------|-----------|--------|---------|
| VWAP reversion (fade N-sigma from session VWAP) | 62–64% | ~1.0 | NO |
| Liquidity sweep (stop-hunt reversal) alone | 60–62% | ~0.9 | NO |
| **Liquidity sweep AT a 25-level** (his signature) | **70%** | **1.41** | NO (in-sample neg) |

- **Best candidate: liquidity-sweep-at-a-25-level, US afternoon.** Cleanest, most
  teachable rule; matches his behavior AND timing; best numbers found (70% / PF 1.41).
- **Timing confirmed**: his entries -> ET cluster at **13:00–15:00 ET** (US power hour).
- Still NOT robust (in-sample negative) on 60d data. The 25-level is clearly central —
  every test including it improves. Profit gap = which sweeps to take (discretion) +
  regime (only fade range days) + needs more data to validate.

## 8. Data limitation
Free NQ 5m history = only 60 days (yfinance). Robust validation needs months/years —
options: paid feed (Polygon/Databento) or collect forward from now.

## 9. THE VIABLE BUILD: a signals/alert system
Rule to alert on:
  price sweeps a 25-pt level (or prior-day H/L) and rejects back
  + RSI stretched + time is 13:00–15:00 ET  -> FADE alert.
~70% historical hit rate. Human applies final judgment. This is the realistic
near-term product (assistive signals), not a validated black-box bot.

## 10. DEEP VALIDATION (the definitive test) — done while away
Fetched deep data (BTC 5m 1yr = 106k bars via Binance; NQ 1h/4h 2yr via yfinance)
and walk-forwarded across MANY folds. This overrides the 60-day results.

FADE / mean-reversion (his style) — DECISIVELY NO EDGE:
| strategy        | BTC 5m PF | NQ 1h PF |
|-----------------|-----------|----------|
| liquidity_sweep | 0.53      | 0.79     |
| vwap_reversion  | 0.46      | 0.85     |
| level_fade      | 0.53      | 0.72     |
The 60-day "PF 1.4 / 70% win" was REGIME LUCK. On a full year+ every fade loses.
=> Do NOT build a bot OR signals on the fade logic. It is not a real edge.

TREND-following — REAL but MODEST and regime-dependent:
| market   | donchian PF | folds+ | note |
|----------|-------------|--------|------|
| NQ 1h 2yr| 1.05–1.09   | 43–57% | marginally positive |
| BTC 1h 1yr| ~1.0       | 33%    | ~breakeven (BTC chopped this year) |
So the earlier GOLD walk-forward (+114%/yr, PF 1.44) was INFLATED by gold's
exceptional 2022–26 bull run. Across other markets/periods trend is only
PF ~1.05–1.1. Realistic expectation = a small, real, regime-dependent edge —
good years (like gold's) and flat years — NOT a guaranteed 10%/month.

## 11. PAIRS HYPOTHESIS + deeper frame review (2026-09-10, round 2)
Prompted by "you're missing the pair he trades NASDAQ with". Read more frames:
- FOUND: SILVER SELL 0.05 and NASDAQ BUY 0.05 closed at the IDENTICAL second
  (2026-02-25 23:01:04). Looked like a risk-on/off pair trade.
- FOUND: holds are far shorter than first thought — GOLD SELL open 10:38:55 ->
  close 10:38:59 = **4 SECONDS**; a NASDAQ trade open 22:59:11 -> close 22:59:30
  = 19s. He fires rapid sequential trades during fast moves.
- FOUND: violent event conditions (2026-02-02 gold 4543 -> 4408 in ~32min, both
  directions traded, -35.43 and +23.43 within the window) => NEWS/EVENT scalping.

TESTED the pair hypothesis (yfinance NQ=F / GC=F / SI=F, shared timestamps):
- corr(NQ,GOLD) = +0.19 (1h) / +0.10 (1d); corr(NQ,SILVER) = +0.28 / +0.19.
  They are WEAKLY POSITIVELY correlated — NOT an inverse risk-on/off pair.
- Spread z-score mean-reversion (both pairs, 1h & 1d, z=1.5/2.0/2.5, hedge-ratio
  regression): PF 0.12–0.70 — LOSES decisively everywhere.
- LIKELY EXPLANATION for same-second closes: BATCH EXIT, not pairing. Proof: two
  GOLD BUY 0.05 positions closed at 10:39:14 at the SAME close price 4425.660 —
  he flattens multiple positions at once.
=> Pairs/spread is NOT his edge.

## 12. FULL SCREENSHOT REVIEW (round 3) — MAJOR CORRECTION
55 detailed screenshots (Strategy video/WhatsApp Unknown .../) contained the
LOSING trades the video scroll never showed. Reconstructed 2026-02-02 (~23 trades):
- 16 wins = +$322 (+1.13,1.63,3.33,3.48,7.93,7.93,9.08,9.83,16.48,19.38,21.78,
  23.43,34.98,35.98,37.73,88.08)
- 7 losses = -$270 (-10.23,-27.03,-35.43,-46.13,-49.58,-50.48,-50.78)
- NET ~ +$52 on a day gold swung 4408<->4571 (3.7% intraday range)

CORRECTIONS to earlier analysis:
| earlier claim        | actual                                   |
|----------------------|------------------------------------------|
| win rate 85-90%      | **~70%** (16/23)                         |
| holds 1-4 min        | **4-36 SECONDS** (e.g. 10:00:39->10:00:45)|
| wins ~= losses       | **avg win $20 vs avg loss $38.5 (2x)**   |

=> NEGATIVE-SKEW profile: many small wins, fewer big losses.
=> Expectancy ~ +$2.45/trade. Thin but real. ~2.9%/day on ~$1.8k on a good day;
   4-5 such days = the "10%/month".

### THE RECONCILIATION (why all our backtests were 'wrong' — they weren't)
His edge is ~$2.45/trade. That is SMALLER than the execution gap between a human
exiting in 4 seconds and a mechanical system paying spread+slippage on 5m bars.
Our tests landed at PF 0.9-1.4 (breakeven-ish) because the strategy genuinely IS
marginal. Nothing structural was missed: the SETUP is reproducible, the EDGE is
execution speed on a razor-thin margin.

### RISK NOTE for the capital provider
Negative skew = steady small gains until losses cluster. On 02-02 he took 7 losses
(three near -$50) and the day netted ~zero. Years of success do not remove that
tail risk; sizing should assume a bad cluster will eventually happen.

## CONCLUSION (honest, deep-data-backed)
1. His scalp does not automate (6 fade variants, now on deep data too — all lose).
2. Trend-following is the only real edge, and it's modest + regime-dependent.
3. Gold's big numbers were partly luck; don't size real money to them.
4. Best automatable approach: a DIVERSIFIED trend portfolio across many markets
   (so good regimes overlap), with realistic expectations (single-to-low-double
   digit %/yr on average), strict risk, demo-first.

## Files
- bot/strategies/level_fade.py, vwap_reversion.py, liquidity_sweep.py
- backtest/nq_fade.py, nq_levelfade.py, nq_systematic.py, validate_deep.py, trend_deep.py
- strategy_analysis/data/btc_5m_1y.json (106k bars, deep validation data)

## 8. Data limitation
Free NQ 5m history = only 60 days (yfinance). Robust validation needs months/years
of intraday data — a real blocker for any scalper backtest.

## 9. Notes for a SIGNALS system
Even if not fully profitable as a blind bot, a **signal/alert** version is viable:
detect "price stretched into a 25-level or prior-day H/L + RSI extreme in US session"
and alert — a human then applies the final judgment (which is where the edge lives).
This is the realistic near-term product: assistive signals, not full automation.

---

## 13. HIS ACTUAL TRADE RECORD — 55 trades transcribed (2026-09-15)

Until now this file reverse-engineered his method from a **recording**. The folder
`Strategy video/` held 55 screenshots of his broker history that had never been
transcribed. They span **2026-01-02 to 2026-09-15** across NASDAQ, GOLD and SILVER.
Extracted to `strategy_analysis/his_trades.csv`.

| | |
|---|---|
| Trades | **55** |
| Net | **+$1,875.39** |
| Win rate | **81.8%** (45/55) |
| Average win / loss | $59.44 / $79.95 |
| Loss ÷ win | **1.34×** |
| **Breakeven win rate needed** | **57.4%** |
| **Profit factor** | **3.35** |

**95% range for his true win rate: 70%–90%. The entire range sits above the 57.4%
breakeven. P(genuinely profitable) = 99.99%.**

He is profitable in both eras, and improved:

| Era | n | Win % | Net | PF |
|---|---|---|---|---|
| Jan–Feb (0.01–0.07 lots, no commission) | 39 | 76.9% | +$302.89 | 1.96 |
| Jul–Sep (0.10–0.25 lots, commission) | 16 | 93.8% | +$1,572.50 | 4.25 |

It survives removing his best trades: without the top 3 it is still **+$976.64**.

### The error this corrects

An earlier read of **8 trades** from one session concluded his loss/win ratio was 3.08×
and he needed **75.5%** to break even — leaving a 31% chance he was a losing trader. That
8-trade window happened to contain **his single worst trade in nine months** (−$483.75).
Across 55 trades the real ratio is **1.34×** and breakeven is **57.4%**.

**A tail event in a small sample inverted the conclusion.** Exactly the failure this
project documents everywhere else, committed here on someone else's data.

### What this means for our own testing

`backtest/forex.py` tested our *encoding* of his method — 25-point level fade plus RSI
stretch plus session — on years of NASDAQ and gold: **PF 0.77–0.84**. His actual record is
**PF 3.35**.

> **The encoding is wrong, not the edge.** The gap between PF 0.8 and PF 3.35 is the
> thing to close, and it is not closed by testing the same description again.

### The next job, now possible for the first time

His 55 entries are timestamped **to the second** with exact prices. `fx_fetch.py` now
supplies `USTECm` and `XAUUSDm` at M1/M5/M15. So instead of guessing his rules from a
video, **pull the actual bars around each of his 55 entries and measure what they have in
common** — position in the day's range, distance to round levels, preceding move size,
time of day, volatility state.

That is reverse-engineering from what he *did* rather than from what he *said*, and it is
the first approach here that could explain a PF of 3.35.

### Caveats that remain

- Transcribed from ~19 of 55 screenshots (list views, so not biased toward winners, but
  **incomplete**). More trades exist in the unread images.
- Screenshots are not a certified statement. The app has date filters and periods may be
  missing.
- 55 trades over 9 months is thin for someone who placed 8 in one hour on 2026-09-14 —
  these screenshots are a **sample of his activity, not all of it**.
- Gold prices in the record range 4305 → 5011 within weeks, which is worth querying.

## 14. Reverse-engineering from his ACTUAL entries — what it could and could not settle

`strategy_analysis/his_entries.csv` — his 26 NASDAQ entries with fill prices and
timestamps to the second, tested against `USTECm` 1m/5m bars from `fx_fetch.py`.

### What failed: aligning his clock to the bars

His broker stamps a timezone the screenshots never name. Three methods were tried and
**they disagree**, so the offset is unresolved:

| Method | Answer |
|---|---|
| Fill price inside the 5m bar range (basis removed) | UTC+4h, but 29.5 pts outside the bar |
| His move vs index move, 5m bars | UTC+4h (r=0.78) — **but slope 0.50** |
| Same, slope closest to 1.0 | UTC+3h (slope 1.09, r=0.69) |
| Same, 1m bars | UTC+5h (slope 0.95) or UTC+2h (slope 1.04) |

**The cause is his holding time.** Trades of 20 seconds to 4 minutes cannot be measured
against 1-minute bars, and the rolling futures basis across three contract months
(Mar/June/Sep) breaks absolute price matching.

**So every bar-derived feature — position in the day's range, size of the preceding move,
volatility state — is unavailable.** Not "weak"; unavailable. Reporting them off an
unresolved offset would be inventing a result.

### What the data CAN settle, needing no bars and no timezone

**The 25-point level claim: borderline, and it does not survive honest treatment.**
Null = his own prices with the last two digits randomised, which preserves the price level
and destroys only the round-number part.

| Level | Mean distance | Within 8 pts | Null | p |
|---|---|---|---|---|
| 10 | 2.38 | 100% | 2.50 | 0.340 |
| **25** | **5.08** | **81%** | 6.25 | **0.050** |
| 50 | 13.46 | 35% | 12.49 | 0.753 |
| 100 | 27.79 | 12% | 25.02 | 0.836 |

25 is the only level that shows anything, exactly as §3 claimed — but **four levels were
tested, so p=0.050 becomes p≈0.20 corrected**, and 26 entries is a thin sample. The
direction supports the original reverse-engineering; the significance does not.

**His timing does cluster.** 62% of entries fall in four hours of his broker clock
(18, 19, 21, 23), which is consistent with §4's US-session claim without confirming the
specific window.

**Fade vs follow: 8 usable cases. Not enough to say anything.**

### The honest conclusion

**26 entries cannot support reverse-engineering a rule.** The one testable claim came in
at the significance threshold and fails a multiple-comparison correction. That is not a
refutation of his edge — §13 establishes the edge at P(profitable)=100% — it means *this
dataset cannot explain it*.

### What would actually settle it, in order of value

1. **His broker's timezone.** One question to him. It unlocks every bar-derived feature
   and turns this from impossible into merely hard.
2. **A full statement export**, not screenshots. Hundreds of entries instead of 26.
3. **Tick or second-resolution index data** for his instrument, since his holds are
   shorter than the bars available here.

Without (1) and (2) this line of analysis is closed, and further effort on it is
speculation dressed as research.

## 15. TIMEZONE SOLVED — and the LEVEL FADE thesis is contradicted (2026-09-16)

### His platform clock is UTC+5

Not UTC, and not the GMT+3 assumed in §4. Established by **minimum basis variance**: a
real futures basis is near-constant within a contract month, so the true offset is the one
that makes `his_fill − index` a stable number rather than a random one.

| Offset | Basis std dev (26 entries, within contract month) |
|---|---|
| UTC+0 | 109.83 pts |
| UTC+3 | 41.41 pts |
| **UTC+5** | **13.10 pts** |
| UTC+7 | 73.62 pts |

**UTC+5 is Pakistan Standard Time.** The app renders the device's local clock, which is why
it looked like a broker setting. Every earlier time-of-day claim in this file was computed
against the wrong offset.

### With the offset resolved: he is a FOLLOWER, not a fader

| Measure | Result | Null |
|---|---|---|
| Entries going WITH the prior 15-min move | **17 of 26 (65%)** | 50% |
| Position in the day's range, BUY | 0.63 | 0.50 |
| Position in the day's range, SELL | 0.56 | 0.50 |
| **SELL minus BUY position** | **−0.07** | a fader needs this strongly POSITIVE |
| Prior 60-min move before a BUY | **+45.6 pts** | — |
| Prior 60-min move before a SELL | **+48.8 pts** | — |

**A fader sells high in the range and buys low. He does neither** — he enters in the *upper*
part of the day's range in both directions, and after the market has risen ~45–49 points in
the prior hour regardless of which way he trades.

**Timing** clusters in the US session and peaks at **14:00 ET** (6 of 26), broadly
consistent with §4's 13:00–15:00 window.

### What this means, and the caveat that limits it

§3 named "LEVEL FADE" as the cracked logic, and `backtest/forex.py` tested exactly that —
returning PF 0.77–0.84. **If he is actually a momentum follower, that test answered the
wrong question, which would explain the gap between PF 0.8 and his real PF 3.37.**

**But 26 entries cannot establish it.** The follow rate of 65% against a 50% null gives
p ≈ 0.17 — not significant. The range-position difference is the right sign for "not a
fader" and far too small to call.

> **Status: the fade thesis is contradicted in direction by every measure tested, and
> confirmed by none of them at this sample size.** That is a reason to stop testing fades,
> not yet a reason to test follows.

The blocker is unchanged and is now purely sample size: **a full statement export.** The
timezone question is closed.

## 16. THE OFFICIAL STATEMENT — it all checks out (2026-09-16)

A CapitalFX account statement for 01/01/2026–17/09/2026 replaced the screenshots.
**91 closed trades**, against 72 transcribed by hand. Parsed to
`strategy_analysis/statement_trades.csv` (gitignored — it carries a real name and
account number).

### First line of the statement: `GMT Offset : 5.0`

**§15 derived UTC+5 from price data alone, by minimum basis variance. The statement
confirms it exactly.** The method works and can be reused on any broker record whose
timezone is unstated.

### The reconstruction matches the broker to the cent

| | |
|---|---|
| Opening balance | **$1,635.89** |
| Trading profit (91 trades) | **+$3,328.09** *(statement: $3,301.06)* |
| Deposits | +$3,558.35 (two, each ≈5 lakh PKR) |
| Withdrawals | −$2,661.00 (monthly) |
| **Final equity** | **$5,861.33** — statement says **$5,861.33** |

### Monthly returns, on the capital held at the time

| Month | Trades | Trading P&L | Withdrawn | Return |
|---|---|---|---|---|
| Jan | 9 | $207 | −$178 | **12.7%** |
| Feb | 49 | $359 | −$180 | 21.6% |
| Mar | 4 | $139 | −$361 | 3.8% |
| Apr | 7 | $404 | −$350 | 11.9% |
| May | 3 | $271 | −$340 | 7.8% |
| Jun | 3 | $375 | −$355 | 11.1% |
| Jul | 5 | $463 | −$357 | 13.6% |
| Aug | 3 | $495 | −$540 | 9.4% |
| Sep | 8 | $615 | — | **11.7%** |

**Average ≈11.5%/month. Zero losing months in nine. Maximum drawdown 10.9%.**
Win rate 85.7% on 91 trades, profit factor 4.71.

### The test that matters most: who funded the payouts

| | |
|---|---|
| Trading profit | **$3,328** |
| Paid out | **$2,661** |
| **Coverage** | **125%** |

**The withdrawals came out of trading profit, with surplus left in the account.** The two
deposits are capital additions and are accounted for separately. This is the check that
distinguishes a real return from one funded by new money, and it passes.

### And "zero losing months in nine" is not a red flag

Tested rather than assumed. At his win rate (85.7%), average win ($54), average loss
($69) and ~10 trades/month, **P(any month is negative) = 1.6%**, so
**P(zero losing months in 9) = 86%.** It is the expected outcome, not an anomaly.

### Where the money is made — confirmed on the full record

| Instrument | Trades | Win % | Net |
|---|---|---|---|
| **NASDAQ** (Mar/June/Sep) | 46 | **95.7%** | **+$3,130** |
| GOLD | 41 | 73.2% | +$118 |

**94% of the profit is NASDAQ.** The 41 gold trades — the dense scalping this file spent
months reverse-engineering — produced **$118 in nine months.** §13's finding holds on the
complete data.

### What is now unblocked

**46 NASDAQ entries**, not 26, with exact times and a confirmed timezone. §15's
fade-vs-follow question needed ~85 for significance; 46 roughly halves the gap and makes
the direction testable with real power. That is the next analysis.

## 17. The entry analysis, run on the statement — one real finding (2026-09-16)

`backtest/his_entries_analysis.py`, on the 46 NASDAQ entries with the broker-confirmed
GMT+5 offset. 39 had enough prior bar history.

### My registered prediction failed

I predicted the follow rate would reach significance at n=46. **It did not.**

| Horizon | Follow rate | p |
|---|---|---|
| 5 min | 59% | 0.337 |
| 15 min | 62% | 0.200 |
| 30 min | 62% | 0.200 |
| 60 min | 59% | 0.337 |

Consistent in direction across all four horizons, significant at none. Day-range position
agrees: **SELL minus BUY = −0.096** (p=0.326), the wrong sign for a fader and too small to
claim.

> **The fade thesis stays contradicted in direction and unconfirmed in significance —
> exactly where §15 left it, on nearly twice the data.** Going from 26 to 46 entries did
> not move it. That is itself informative: if the effect were as large as 65% it should
> have firmed up. The honest reading is that **the preceding move does not explain his
> entries.**

### What IS significant: the hour

| | |
|---|---|
| Hours he trades across | 12 |
| Busiest hour | **11:00 ET — 12 of 46 entries** |
| Expected if spread evenly | 7.3 |
| **Permutation p** | **0.0032** |

| 11:00–13:00 ET | Rest of the day |
|---|---|
| 20 of 46 entries (43%) | 26 entries |
| **$1,598 — 51% of all NASDAQ profit** | $1,532 |
| **win rate 100%** | 92% |
| **$80 per trade** | $59 |

**He concentrates in a three-hour window, and that window carries half his profit at a
100% win rate.**

### And §4's timing claim was wrong

§4 said the cluster was **13:00–15:00 ET**. That was computed against an assumed GMT+3.
With the broker-confirmed GMT+5, the real cluster is **11:00–13:00 ET** — the US cash
open plus the first two hours, not the afternoon. **Every time-of-day statement in this
file written before §15 is off by two hours.**

### Why winners-vs-losers could not be tested

**38 winners, 1 loser** in the covered window. Nothing can separate them, and the reason
is the headline: on NASDAQ he is running at a **97% win rate**.

### Where this leaves the reverse-engineering

Two of the three original pillars are now gone. §3's **level fade** is contradicted, and
§4's **13:00–15:00 window** was an artifact of the wrong timezone. What survives is
narrower and better evidenced than either: **he trades NASDAQ, in a three-hour window
around the US open, roughly 5 times a month, and wins ~96% of the time.**

That is a description, not a rule. The rule — what he actually sees at 11:00 ET — remains
unexplained, and 46 entries spread over 12 hours is not enough to find it. **The next
thing that would help is not more analysis; it is asking him what he looks at.**

## 18. THE MECHANISM, FOUND — an event study rather than a hypothesis test (2026-09-16)

`backtest/his_event_study.py`. §17 tested pre-chosen hypotheses and every one came back
directionally consistent and statistically silent. A hypothesis test can only answer the
question you brought. So: align all 39 entries at t=0, sign-flip the sells so "up" always
means his way, express everything as points relative to the entry bar (which cancels the
futures basis exactly), and **look**.

| | −60m | −30m | −10m | **ENTRY** | +15m | +30m | +60m |
|---|---|---|---|---|---|---|---|
| **All 39** | **−23.5** | −6.6 | −3.4 | **0** | **+8.4** | +1.4 | **0.0** |
| 11:00–13:00 ET (20) | −28.3 | −2.0 | −4.7 | 0 | +4.5 | **−10.4** | −8.1 |
| Other hours (19) | −18.4 | −11.5 | −2.1 | 0 | +12.6 | +13.8 | +8.5 |

### He is a momentum entry with a 15-minute half-life

**Price moves ~23 points INTO his direction over the hour before he enters.** He buys
after a rise and sells after a fall. That settles §3's "LEVEL FADE" thesis definitively:
**it is backwards.** He is not fading anything; he is joining a move already underway.

**The edge lasts about fifteen minutes and then evaporates.** +8.4 points at +15min,
+1.4 at +30, **exactly 0.0 by +60.**

> **His 20-second-to-4-minute holding time is not a style preference. It is the whole
> strategy.** The move he enters gives back everything it gave within an hour. A trader
> doing the identical entries with a one-hour hold makes nothing.

### And his best window is the one that reverses hardest

The 11:00–13:00 ET cluster — 51% of his profit at a 100% win rate (§17) — is where the
move **reverses fastest**: +4.5 at 15 minutes, then **−10.4 by 30 minutes**. Outside that
window the move persists (+13.8 at 30min).

So in his most profitable hours he is scalping the opening thrust and getting out before
the snap-back. That is internally consistent with everything else: it explains the tiny
targets, the sub-4-minute holds, and why the single 48-minute hold in the record is also
the single worst loss (−$483).

### Why every previous encoding of him failed

`backtest/forex.py` tested **the fade direction with trailing exits** and returned
PF 0.77–0.84. On this evidence it had the direction backwards *and* the exit wrong — two
errors that each on their own would be fatal. His real PF is 4.71.

### What he actually does, stated as a rule for the first time

> **Join a NASDAQ move that has already run ~20+ points, preferably in the first two
> hours of the US cash session, and be out inside four minutes.**

He captures roughly 5 of the ~8 points available — consistent with exiting well before
the +15-minute peak rather than trying to time it.

### The honest limit

39 entries. The event-study shape is far more legible than anything in §17, but it is an
*average* over 39 paths with wide dispersion (see `logs/his_event_study.png` — the grey
lines are individual trades). **It explains his style; it does not yet give an entry
trigger.** What makes a given 20-point move worth joining, and the 20-point move an hour
earlier not worth joining, is still unexplained — and that is the part that is likely to
be judgment rather than rule.

## 19. THE TRIGGER, FOUND — he enters EARLY in moves, not late (2026-09-16)

`backtest/his_trigger.py`. §17 and §18 described his entries in isolation, which can never
say what he *skipped*. This builds the opportunity set: **46 entries he took against 3,910
comparable moments he did not**, same hours, same days, each control given the direction
of its own preceding move so the comparison is "which momentum moments does he pick",
not "does he trade with momentum" (settled in §18).

Ten features declared before looking, Holm-corrected across the family, and ranked on the
first two-thirds by date with the last third held out.

| Feature | His | Skipped | p | Holm p |
|---|---|---|---|---|
| **prior 60min move in ATR units** | **0.61** | **1.94** | **0.000** | **0.004** ✅ |
| prior 60min move (points) | 26.56 | 59.17 | 0.007 | 0.060 |
| prior 15min move (points) | 2.59 | 14.72 | 0.106 | 0.678 |
| position in session range | 0.54 | 0.64 | 0.076 | 0.606 |
| ATR expansion, new extreme, run length, distance from open, time since open | — | — | 0.35–0.93 | 1.000 |

**One feature survived Holm correction. It then held out of sample: held-out difference
−2.71, p = 0.000.**

### And the sign is the opposite of what §18 implied

| Prior 60-min move, in ATR | His 46 entries | The 3,910 he skipped |
|---|---|---|
| median | **0.29** | **1.44** |
| mean | 0.61 | 1.94 |
| share under 0.5 ATR | **52%** | 18% |
| share under 1.0 ATR | **70%** | 37% |

**It is a CEILING, not a floor.** He does not wait for a big move — he enters while the
move is still small relative to the market's own volatility, and skips the ones that have
already run.

### This corrects §18

§18 concluded "join a move that has already run ~20+ points". That was read off a **mean**
of sign-aligned paths. The mean is right — price does move ~25 points his way beforehand —
but the **median is 0.29 ATR**, near flat, and 25 points is *small* against the 59 points a
typical momentum moment has already run. Both facts are true and only together are they
meaningful:

> **There is a move in his direction, and it is a young one.** He enters roughly 3–5×
> earlier in the life of a move than a naive momentum trader would.

### It predicts his own results, not just his behaviour

| His entries | n | Average net |
|---|---|---|
| on moves below his median (0.29 ATR) | 23 | **$81.66** |
| on larger moves | 23 | $54.42 |

**50% better on the trades that satisfy the filter** — so this is not merely descriptive
of what he does, it tracks what works when he does it.

### Why this makes the whole picture consistent

§18 measured a **15-minute half-life**: the move gives everything back within an hour.
That is exactly what should happen if you enter late. **Entering at 0.3 ATR leaves room;
entering at 1.9 ATR is buying the exhaustion.** The trigger and the half-life are the same
fact seen from two sides, and together they explain the tiny targets and the sub-4-minute
holds.

### The rule, restated correctly

> **Join a NASDAQ move in the first two hours of the US session while it is still small
> relative to current volatility — under ~0.5 ATR over the prior hour — and be out inside
> four minutes.**

### Limits

46 entries; one feature out of ten. Holm correction and an out-of-sample holdout are the
right guards and it passed both at p=0.000, which is why this is stated as a finding
rather than a lead. But it is a **filter**, not a complete system: "move under 0.5 ATR"
still admits 18% of all moments, and he trades ~5 times a month. Something further
narrows it, and that something is not among the ten features tested.

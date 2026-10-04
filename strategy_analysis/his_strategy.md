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

## 20. §19 IS RETRACTED — the trigger was an artifact of my controls (2026-09-16)

Found while preparing to backtest the §19 rule. It does not survive.

### The bug

In `his_trigger.py`, each control bar was assigned **the direction of its own preceding
60-minute move**. That makes `move60` positive *by construction* for every control. His
entries were assigned **his actual trade direction**, which is sometimes against the prior
move. So the test compared **his signed move against the controls' absolute move**, and a
difference was guaranteed before any data was looked at.

### The corrected test

| | His 46 | Controls | p |
|---|---|---|---|
| **signed** move60 (ATR) — the rigged comparison | 0.07 | 1.94 | 0.000 |
| **absolute** move60 (ATR) — the fair one | **2.22** | **1.94** | **0.296** |

| Percentile of \|move\| | His | Controls |
|---|---|---|
| 25th | 0.70 | 0.68 |
| 50th | 1.29 | 1.44 |
| 75th | 2.99 | 2.68 |

**Indistinguishable.** The "he enters while the move is under 0.5 ATR" rule keeps 15% of
his trades and 18% of all moments — *worse* than chance.

It passed Holm correction and an out-of-sample holdout, and was still wrong, because
**both were computed against the same biased control set.** Neither guard can detect a bias
baked into the comparison itself.

### What the signed result actually showed

Only that **he trades in both directions relative to the prior move** while my controls
were all one direction by construction. That is a fact about my code, not about him.

### Corrected verdict on the trigger

**None of the ten features separates his entries from random moments once compared
fairly.** Not move size, speed, volatility expansion, session extreme, range position, run
length, distance from the open, or time since open.

> **His trigger is not a measurable property of the 5-minute chart at the moment he
> enters.** That is now the finding, and it is a real one.

### What survives all of this

| Established | Evidence |
|---|---|
| He is profitable | 91 trades, official statement, P = 100% |
| ~11.5%/month, 10.9% max drawdown, 0 losing months in 9 | broker statement, reconstructed to the cent |
| Payouts funded by trading, not deposits | $3,328 earned vs $2,661 paid = 125% |
| **NASDAQ, not gold** | 46 trades +$3,130 vs 41 trades +$118 |
| **Clusters at 11:00–13:00 ET** | p = 0.0032, 51% of profit, 100% win rate |
| **The edge has a ~15-minute half-life** | event study, sign-aligned, no control set involved |
| He is **not** a level-fader | contradicted by every measure tested |

**Dead:** the level-fade thesis (§3), the 13:00–15:00 window (§4, wrong timezone), and the
early-entry trigger (§19, this correction).

### The rule for this file, added the hard way

> **A control group must be built without reference to the outcome variable.** If controls
> are assigned a direction, positions, or a label derived from the same quantity being
> tested, no amount of multiple-comparison correction or holdout testing will save the
> result — both operate downstream of the bias.

## 21. THE EDGE IS THE EXIT — found by looking at the half I had ignored (2026-09-16)

§17–§20 spent everything on entries and found nothing. Entries are half a strategy. The
other half had never been examined.

**A parser bug had to be fixed first.** The price regex `(\d+\.\d{2,3})(\d+\.\d{2,3})`
greedily took 3 decimals from 2-decimal NASDAQ prices, stealing the leading digit of the
close: `25780.0025741.75` split as `25780.002` + `5741.75`. Exit points came out as ±30,000.
Fixed by requiring both prices to have the same decimal count **and** be within 5% of each
other — same instrument, minutes apart. Verified: points × lots × $100 now reproduces the
statement's profit column exactly. *Entry prices were nearly unaffected (off by 0.002), so
§15's timezone work stands; everything else used bar data, not his prices.*

### What his exits look like

| | |
|---|---|
| NASDAQ trades | 46 — **44 winners, 2 losers** |
| Points captured, median | **7.00** |
| Hold time, median | **1.3 minutes** |
| **Winners held** | **median 1.3 min** |
| **Losers held** | **median 24 min** |

### He exits on POINTS, not dollars

| Exit size | Times |
|---|---|
| **7.00 pts** | **5** |
| 6.25 pts | 3 |
| 8.75 pts | 3 |

Repeat-pairs observed **40** against **24.5** expected at random, **p = 0.032**. The same
test on *dollar* profit finds **4** repeat-pairs — nothing. **He is watching the chart, not
the P&L.** A fixed dollar target would show the opposite pattern.

### He does NOT cut losses short

| | |
|---|---|
| Average win | **10.48 pts** |
| Average loss | **19.62 pts** |
| Ratio | **1.87× — his losers are BIGGER** |

**His entire edge is the 95.7% win rate, not the payoff ratio.** That inverts the usual
advice and explains why the strategy is so fragile to a single held loser.

### The one time he broke his own rule

| The two losses | | |
|---|---|---|
| 2026-02-04 | −$24 | held **12 seconds** — cut instantly |
| 2026-09-15 | **−$483.75** | held **47.9 minutes** |

That single trade is **15% of his entire nine-month NASDAQ profit** and undoes **5.9
average wins**. Without it: 45 trades, **97.8% win rate, $3,614**.

> **His median winner is held 1.3 minutes. His one disaster was held 48 minutes.** The
> discipline is not a detail of the strategy — it *is* the strategy.

### Why this makes everything else cohere

§18 measured a **15-minute half-life**: the move gives everything back within an hour. If
that is the environment, then **taking ~7 points inside two minutes is not impatience, it
is the only correct response.** Entry timing barely matters when the move reverses that
fast; what matters is being gone before it does.

And it explains why every backtest of him failed. `backtest/forex.py` tested **trailing
exits and wide targets** — the exact opposite of a 7-point fixed target with a 2-minute
time stop. It was measuring a strategy he does not run.

### The rule, finally stated in the half that matters

> **Take ~7 NASDAQ points. Be out inside two minutes. Never let one run.**

The entry is not recoverable from price data (§20) and may not need to be: at a 15-minute
half-life and a 7-point target, a mediocre entry still works if the exit is disciplined.
**That is a testable proposition** — and it is the first one this file has produced that
was not contradicted within a day.

### Limits

Two losing trades is nothing to generalise from. The point-clustering p = 0.032 is
uncorrected and was tested after looking. What is *not* a marginal statistical claim is the
plain shape of the record: median 7 points, median 1.3 minutes, and the only long hold in
46 trades being the only large loss.

## 22. TESTED: the exit is necessary but NOT sufficient — §21's closing claim is wrong

`backtest/his_exit_test.py`. §21 ended by claiming "a mediocre entry still works if the
exit is disciplined." That is falsifiable, so it was falsified.

**Method:** 4,000 entries chosen **at random** inside his 11:00–13:00 ET window on
USTECm 1-minute bars, exited by his measured rule (7 points, 2 minutes, no stop). Costs
from his own statement: commission is **1.0 point round trip** ($10/side on 0.20 lots ÷
$100 per point per lot) plus ~1 point of spread = **2.0 points charged on every trade**.

| Entry direction | n | Win % | Avg points |
|---|---|---|---|
| random | 4,000 | 53% | **−3.13** |
| momentum | 4,000 | 53% | **−3.18** |
| fade | 4,000 | 54% | **−3.00** |

**Every one of 20 target × time combinations is negative.** The best cell anywhere in the
grid — 10 points, 1 minute — still loses **1.79 points per trade**.

| | His 46 NASDAQ trades | Random entry, identical exit |
|---|---|---|
| Win rate | **95.7%** | **53%** |
| Points per trade, gross | **+9.17** | −1.13 |
| Net of the same 2-pt cost | **+7.17** | **−3.13** |

### What this settles

**His entry selection is worth +10.4 points per trade** over a random entry in the same
window with the same exit. That is not a rounding difference — it is the entire strategy.

The exit rule is **necessary**: §21 showed the only long hold in 46 trades was the only
large loss, and the grid here confirms longer holds lose more at every target. But it is
**not sufficient**: applied to entries he did not choose, it loses money at every setting.

> **The edge is in the entry. §20 established that no measurable property of the chart
> distinguishes his entries from anyone else's. Both are true, and together they are the
> answer:** what he is doing is real, worth +10 points a trade, and **not recoverable from
> price data**.

### So the investigation closes here, and completely

Nine months of trades timestamped to the second, a broker statement reconciled to the
cent, a confirmed timezone, 1-minute bars, 3,910 control moments, ten entry features, eight
day-level features, an event study, and a 20-cell exit grid. The conclusion is not "we need
more data" — it is that **the thing he does happens somewhere other than the price series**:
order flow, the tape, or pattern recognition he could not write down if he tried.

That is consistent with everything observed: the 95.7% win rate, the 1.3-minute holds, the
single manual SL/TP order in 92 rows, and the fact that this project's most careful
encoding of him returned PF 0.80 against his real 4.71.

**This is a complete answer, not a failed search.** It tells you exactly where the value
sits — in him, not in a method — which is worth knowing before spending another month
trying to copy it.

## 23. Nothing in the material shows his chart (2026-09-25)

Re-checked for anything unread, because the question left by §22 is "what does he see before he
enters":
- **The video:** 94 s, 576×1248, sampled every 4 s. It is the History → Trades list scrolling:
  NASDAQ and GOLD rows with open/close times, prices and P&L.
- **The 55 screenshots:** all the same list. Every image has identical darkness (0.08 of pixels
  under 128), so none of them is a chart screen.

**No chart, indicator, order book or tick screen exists in the material.** The edge measured in
§22 (+10.4 points a trade from entry choice) cannot be traced further from these files. The only
two routes left are asking him what he watches, or a recording of his chart while he trades.

Forex strategies tested instead, the same day: doc 18. Nine calendar/session effects and the
Asian-range breakout are all dead after costs; 12-month trend on commodities + indices holds, but
only swap-free.

## 24. Reading his charts, testing news, and encoding what the charts show (2026-09-25)

The user: "don't you see the charts yourself by cross-checking dates and prices? Also, other than charts,
he relies on news." §15–22 aligned his trades to the bars and MEASURED them. This time they were
**drawn and read**.

**The charts** (`backtest/his_charts.py` → `logs/his_charts_01..08.png`). All 46 NASDAQ trades are drawn
on USTECm bars (1-minute from June, 5-minute before), with his fills pinned per trade. A per-contract
basis put the marks 100–200 points off, because a futures basis decays to expiry; per trade it lines
up. His exits then match what the chart did, which also confirms GMT+5 again. What they show:
- **He reads the 1-minute trend and joins it right after a small pause.**
  - 2026-09-14 is the clearest day: once the day made lower highs after its 13:57 top, he sold
    every small bounce. Four shorts in 16 minutes (#43–#46), 7–17 points each, size raised from
    0.20 to 0.25.
  - The same day's only disaster (#40, −$483.75) was a buy on a dip that he held **48 minutes**
    while the structure turned.
  - 2026-08-07 (#37–#38): he bought the first pullback of a V-bounce, then sold into the congestion.
- **Some entries follow news.**
  - 2026-02-11 and 2026-02-20 each have a huge 5-minute bar at exactly 08:30 ET, the US
    data-release time.
  - He trades 30–45 minutes later, in the aftermath: buying a pause near the high (#8, +14 points),
    and selling the retest of the level the news broke (#12, +19.5 points).
- **The 11:00–13:00 ET cluster holds** with a DST-aware conversion: 19 trades, every one a winner.
  11:00 ET is 16:00 London, the London close and the 4pm fix.

**News, tested** (`backtest/his_news.py`, `logs/his_news.txt`). Each entry was ranked against the SAME
ET minute on ~251 other days, so clock-time seasonality (08:30, 09:30) cancels:

| feature | mean rank (0.50 = ordinary) | in top 20% | p |
|---|---|---|---|
| largest bar, prior 60 min | 0.55 | 23% | 0.120 |
| volume, prior 30 min | 0.49 | 13% | 0.576 |
| move, prior 60 min | 0.49 | 21% | 0.580 |
| today's 08:30 bar | 0.55 | **34%** | 0.173 |
| recency of a shock bar | 0.56 | 28% | 0.083 |

- None survives Holm.
- **Fed decision days: 0 of his 39 entries**, against a 2.3% base rate.
- Entries with a news footprint earned $70 each against $60 for the rest.

Registered: "a moderate effect, significant on at least one". **Wrong.** News is at most a minor
part of how he picks moments.

**The chart pattern, encoded** (`backtest/his_micro.py`, `logs/his_micro.txt`). The rule: a 1-minute
trend (EMA20 slope and position), a pause of 1–3 bars against it, then entry on the resuming bar. It
exits at a 5/7/10-point target, a 20-point stop or 5 minutes, and runs 10:30–15:30 ET on June–September
1-minute data. 18 cells: **all lose.**
- Gross: −1.3 to −3.2 points a trade. Net of 2.2 points: −3.5 to −5.4.
- Wins: 53–66%, where a 7-point target against a 20-point stop needs ~74%. His record is 95.7%.

Registered: "within ±0.5 gross, 0 of 18". The count was right; the gross was worse than predicted.

**Where this leaves him.** The pattern he trades is now visible on his own charts, not only inferred.
- But *every* pause loses, and *his* pauses win 96% of the time.
- **What he adds is the choice of which pause**, most likely read from the order flow and the tape's
  speed at that moment. No 1-, 5- or 60-minute bar feature, and no news footprint, captures it.

This is the fourth independent angle to land on the same answer (§20 features, §22 random entries
with his exit, the news ranks, the 1-minute encoding).

## 25. Tick by tick: the pause he joins, his broker's prices, and what is left (2026-09-25)

Goal set by the user: "find which pause he joins... check the news too... something you are missing".
The missing piece was **tick data**. The Exness MT5 terminal serves USTECm bid/ask to the millisecond
back to 2026-01-02; until now only 1-minute bars had been used. Scripts: `his_ticks.py`,
`his_crossmarket.py`, `his_pullback_ticks.py`, `his_leadership_ticks.py`; the ad-hoc checks are
recorded in `logs/his_vs_market.csv` and `logs/his_after_activity.csv`.

### 1. His entry SECOND
- **17 of 46 NASDAQ entries fall 10–19 seconds into a minute**, against 7.7 expected (p ≈ 1e-4,
  ~6e-4 after six buckets).
- His gold entries and all his exits are uniform.
- The effect is stronger in January–March (45%) than April–September (31%).

### 2. The statement's clock is exact, but his January–March PRICES are not the market's
- **The clock.** Shifting the statement by −600…+600 s, the move between his entry and exit
  seconds matches his points best at a shift of **0 s**, and the error jumps at ±10 s.
- **The prices.** Holding the basis at that week's median:

  | | entries inside the real market's range (±2 min) | exits inside | basis scatter |
  |---|---|---|---|
  | **April–September, 26 trades** | **100%** | **100%** | 0.5 points |
  | January–March, 20 trades | 65% | 50% | 9.7 points |

- **The basis-free proof.** In ~10 of the 20 January–March trades he banked more points than the
  real market ever moved his way while the trade was open:
  - 2026-01-02: +38.25 against a best of +5.7;
  - 2026-02-11: +14 when the market never moved his way at all;
  - 2026-02-24: +7 against −5.
- **So much of his early small-lot record was earned on his broker's quotes, not the market's.**
  The April–September record, with bigger lots and most of the money, is fully consistent with the
  real market.

### 3. The pause he joins (the 26 clean trades, second by second, sign-aligned)

| window | what the market did |
|---|---|
| 5 min before | NASDAQ ~+5 points **his way** (62%), and **ahead of the S&P and the Dow** (S&P-minus-NASDAQ rank 0.37) |
| last 30 s | NASDAQ, the S&P and the Dow **all dipped against him together** (ranks 0.35–0.39), ~2 points |
| his entry | ~18 s into the minute, **during the dip**, inside the current candle |
| tape speed | ordinary (tick rate vs the same clock minute: 1.09) |
| next 60 s | **+6 points** median |
| first ±7 | **+7 before −7 in ~85–88%** (random: 50%) |
| next 5 min | **calmer than usual** (range rank 0.41) |

In words: **in a small NASDAQ-led move, he joins on a brief market-wide half-minute pullback,
mid-candle.**

### 4. Everything else that would pick THAT pause, tested

| what | result |
|---|---|
| that profile as a rule, every second of Apr–Sep, real bid/ask (9 cells) | −2.9 to −3.1 points a trade; **random entries −2.9** |
| plus NASDAQ leading the S&P (3 cells) | −3.0 to −3.5; no better than random |
| news before entry (§24, same clock time) | ordinary; 0 trades on Fed days |
| news AFTER entry (a burst he got ahead of) | **ordinary, and calmer than usual** over 5 min |
| the day's direction, VWAP, range position, opening range | ordinary (with the day's move 50%) |
| which days he trades (`his_day_choice.py`, earlier) | no feature separates them |

Registered predictions:
- "a price burst in the last 10–20 s, tape faster": **wrong**, he enters on a dip, at normal speed;
- "the S&P/Dow lead": **wrong in the way expected**. NASDAQ leads, then everything dips;
- "the rules lose after the spread": right.

### 5. How much of the 96% is skill

Random entries in his hours, taking +7, with his way of holding:
- no stop, up to 50 min: **83% win**, but −52 points on an average loser, −2.97 a trade;
- stop −35: 76%, −2.49 a trade.

**His clean record is 25 of 26** (96%), a win rate that is only borderline better than that
structure (p ≈ 0.05). **What is clearly skill is the first 7 points: +7 before −7 in ~85–88% of his
entries against 50% at random.**

### The answer to "which pause"

**The pause is now described exactly** (§3): a half-minute, market-wide dip inside a young
NASDAQ-led move, entered mid-candle. **He does not take every one.** A rule that takes every one is
no better than random, and no available data picks his out of the rest:
- NASDAQ's tick path;
- tape speed;
- the S&P, the Dow, gold, USDJPY;
- news before or after;
- the day's direction;
- VWAP;
- the opening range.

What he uses is outside all of these: most likely **the order book** (depth and the size behind
the quotes), which no free history records.

**Two things would crack it:** a recording of his screen while he trades, including any order
book / depth window, or simply asking him what he watches in that half-minute.

**What the statement itself says about him:**
- the **April–September** record is real skill on real prices;
- the January–March record leaned on his broker's quotes.

## 26. Looking for WHICH pause: every lead from his ticks, tested to the end (2026-09-26)

The user: "if we have identified the pause we can identify other things too". Everything below uses his
26 clean trades (April on) and USTECm ticks; logs are named per script.

### The feed has no order book
Exness USTECm's spread is fixed (1.12 points for an hour on 2026-09-14), and bid and ask move together on
100% of ticks: one price plus a markup. Real order flow exists only on Binance's QQQUSDT perp (from
2026-04-06; aggressor-tagged trades), whose API serves only recent days by time or by id (400 for older).
History is in the data.binance.vision archives, which is **a file download, not done without the
user's say-so**.

### What marks his moments

**Against the same clock second on other days:**
- `his_microstructure.py`: at the fill, the last 5 s still go against him (rank 0.39, p 0.046).
- `his_candles.py`: the 1-minute candle that just closed has a long wick AGAINST the move (0.61,
  p 0.048). Hammers make up 32% of his entries vs 16% of other days, on a quiet candle (0.71× usual).
- His entries sit near 25-point futures levels: 35% within 2.5 points vs 20% (p 0.039); exits show
  nothing.

**Against the other moments of the SAME 20 minutes, same direction** (`his_local.py`):
- the 30-s dip against him: 0.37 (p 0.029);
- the last 5 s against him: 0.37 (p 0.022);
- the rejection wick: 0.62 (p 0.036).

None of these survives Holm on 25 trades.

### What his moments are worth, measured properly
On mid prices, a 3-minute race to +7 / −7:

| entries | win rate |
|---|---|
| **his entries** | **87% (20/23)** |
| random, his direction, within 20 min | 54% |
| random, his direction, any time that day | 50.5% |
| random time, random direction | 50.5% |

- **The day, the hour and the direction add ~4 points. His exact moment adds ~33 (p = 0.001).**
- Net of the real spread, a symmetric −7 race puts his entries level with random (42% vs 42%), because
  they dip before they rise; he holds through that.
- This corrects §25's "88% vs 50%": the 50% was assumed there, not measured.

### Rules built from the markers, every trading day, real bid/ask

| rule | points a trade | random |
|---|---|---|
| resting limits at 25/50/100 futures levels vs half-step offsets vs random levels (`his_levels.py`) | −2.95 / −3.05 / −3.54 round, −2.91 / −3.26 / −3.24 offset | −2.83 |
| trend + quiet hammer, entry 15 s into the next minute (`his_setup.py`) | −2.67 | −2.56 |
| … + near a round 25 level / near an offset level | −2.41 / −2.34 | |
| rejection wick + not extended, net race (`his_predictors.py`) | 34.4% win, −2.19 | 33.9%, −2.25 |

### Do the local predictors hold on ALL days? (`his_predictors.py`, 8,606 moments)
- **The rejection wick is real but small:** +3.1 points of 3-minute win rate (+3.8 / +2.5 by half).
- Joining an extended move looked −11.5 near his trades, but is ~0 on all days. It was specific to
  his days.

### Where this leaves "which pause"
**The pause is described precisely:**
- a small NASDAQ-led move;
- a quiet 1-minute candle whose wick rejects the move against it, often near a round number;
- he buys while the next half-minute is still dipping.

**One ingredient, the rejection wick, is a genuine predictor on every day, worth ~3 of his ~33
points.** The remaining ~30 are not in:
- the price, the tick pace, or the step structure;
- the S&P, the Dow, gold or USDJPY;
- news before or after;
- the day's trend or VWAP;
- round numbers or candle patterns.

Every rule assembled from those loses the spread like random entries. The data that could still hold
the rest is order flow: Binance QQQ perp trade archives (needs the user's OK to download), or better, a
recording of his screen.

## 27. Order flow: the last free data source, and it is an echo (2026-09-26)

The user approved downloading Binance's QQQUSDT trade archives (data.binance.vision, 24 days, 19 MB, not
committed): his 10 clean trading days since the perp listed on 2026-04-06, plus 14 comparison days.
**22 of his entries** fall in that window. Every Binance trade is tagged buyer-aggressor or
seller-aggressor. It is Binance traders' flow, not the CME's. The perp is thin: 20–75 trades a
minute in US hours, and $5k–$135k traded a minute.

### Binance follows, it does not lead (`his_orderflow_check.py` part 1)
Correlation of 1-second returns, Binance QQQ vs Exness USTECm, 24 days:

| Binance vs Exness | 2 s earlier | 1 s earlier | same second | 1 s later |
|---|---|---|---|---|
| correlation | 0.095 | 0.255 | **0.567** | 0.015 |

Here "1 s earlier" means Binance's move a second before Exness's.

Read in plain words: Exness's NASDAQ price moves first, or in the same second. Binance's traders catch
up within a second. Nothing on Binance happens before the price the trader already sees. So its flow can
confirm a move, but it cannot hold anything the price did not already show. This also rules out look-ahead
in the tests below.

### What marks his moments (`his_orderflow_archive.py`, `logs/his_orderflow_archive.txt`)
Each of his entries is ranked against same-day moments within 20 minutes, same direction (0.50 = ordinary):

| feature | his rank | p |
|---|---|---|
| aggressive flow over the last 30 s, his way | **0.38** | 0.057 |
| largest single trade in the last 60 s | **0.38** | 0.044 |
| "absorption" (sellers hit, price barely moves) | 0.48 | 0.75 |
| flow in the 60 s AFTER his entry, his way | 0.59 | 0.13 |
| 10 s, 60 s and 5-minute flow, activity, move | 0.41–0.47 | ≥ 0.17 |

- Against the same clock second on the 14 other days, everything sits at 0.40–0.60, with p ≥ 0.09.
- Nothing survives Holm. The best result is 0.39.
- The two marks are §26's markers seen again through another window. **Takers were selling into his
  buys**, which is the 30-s dip against him. **Big trades were absent**, which is the quiet candle
  (0.71× usual).

**Prediction wrong in direction.** I registered absorption and his-way flow ≥ 0.6: that the dip would be
buyers pausing. In fact the dip is sellers pushing, and there is no absorption.

### Does the flow predict the next 3 minutes? No (`his_orderflow_check.py`)
- **The first run said yes, by a lot:** the 10-s imbalance split the 3-minute race by **+11.7 points**
  (+14.6 / +8.8 by half), 3–4× my registered +2 to +4.
- **The bug hunt says it was luck.**
  - 40 fresh random samples of the same 24 days give **+0.8** (sd 3.8, max +7.3). The first run was the
    most extreme of 41.
  - 150 moments a day give **+0.5**.
  - Inside terciles of the Exness price's own 10-s move, the flow adds −0.5 / −3.4 / −0.5.
- **Net of the spread**, no imbalance decile comes near break-even: 30.7–36.5% wins, against 34.0% for all
  moments and 50% needed.
- **"Sellers hit, then stopped"** (the flow turning, or the last 5 s going quiet): his ranks are 0.59
  (p 0.13) and 0.51 (p 0.89). As predictors: +2.2 and 0.0 points.

**The lesson for this repo:** a moment-sample has its own sampling noise, here ±3.8 points. One draw is
not a result. Draw it again before believing it.

Registered predictions:
- 1 right: no Binance lead.
- 2 wrong: I expected the flow to keep +3 to +6 points beyond the price. It keeps ~0.
- 3 right: no decile beats the spread.
- 4 wrong: no "sellers stopped" mark.

### Where "which pause" stands now
**Every free source has now been read:**
- his price;
- the tick pace and step structure;
- the S&P, the Dow, gold and USDJPY;
- the news calendar;
- round numbers and candle shapes;
- and now real order flow.

The order flow restates the dip and the quiet that the price already showed. The ~30 points his exact
moment adds (§26) are in none of them.

**Three things are left, and none is in this repo's reach:**
1. **CME's own NQ order flow**, the market that actually leads. It is paid data, and the user would have
   to open the vendor account. Expected value is low: book imbalance is known to predict the next few
   ticks, not a +7 point race over 3 minutes.
2. **His screen, or asking him.**
3. **That it is partly luck.** 20 of 23 on the mid race is p ≈ 0.001 against nearby moments. But this
   statement was picked because it looked good, and 23 trades cannot separate skill from a
   well-chosen record. Net of the spread his entries equal random (42% vs 42%, §26). The money came from
   the structure (a small target and holding through dips, §25) at least as much as from the pick.

Recommendation: stop the reverse-engineering here unless a recording of his screen exists. Nothing more
in the data can move it.

## 28. His trades against the real news calendar (2026-09-26)

The user: "he also does rely on news... some person who comes to speech and whatever the word he says
affects the market, and other economic stuff... cross check the dates". §24 read news only from its
footprint on the price (unusual bars), plus Fed decision days. It never used a calendar. This does.

**The calendar:** ForexFactory, the one retail news traders keep open (`backtest/ff_calendar.py`,
cached, not committed). It has 4,240 events from December 2025 to September 2026, each with its release
time to the second, its impact rating, actual vs forecast, and FF's notes on unscheduled events.
For the dollar it holds:
- 216 high-impact releases and decisions;
- 333 speeches, 74 of them by the President, the Fed Chair (Powell, then Warsh from May), Treasury
  Secretary Bessent, or FOMC press conferences;
- 15 events flagged as surprises.

**The test** (`backtest/his_calendar.py`, `logs/his_calendar.txt`): each entry against the SAME New York
clock time on the other 175 US trading days of his period, because releases and speeches sit at fixed
clock times. Predictions were registered first.

| NASDAQ | every entry (46) | | first entry of each day (30) | |
|---|---|---|---|---|
| | his / expected | p | his / expected | p |
| a high-impact release in the prior 60 min | 3 / 2.6 | 0.77 | 2 / 2.0 | 0.98 |
| … in the prior 3 hours | **13 / 8.2** | **0.044** (Holm 0.31) | 7 / 5.3 | 0.39 |
| a high-impact release due in the next 60 min | 3 / 1.7 | 0.27 | 2 / 1.5 | 0.65 |
| a speech started in the prior 60 min | 7 / 4.9 | 0.31 | 5 / 3.1 | 0.25 |
| President / Fed Chair / Treasury / press conference, prior 2 h | 2 / 2.0 | 0.98 | 2 / 1.0 | 0.32 |
| any medium/high event within 30 min | 2 / 3.3 | 0.40 | 2 / 2.7 | 0.62 |
| an unscheduled (surprise) event, prior 2 h | 0 / 0.7 | 0.40 | 0 / 0.4 | 0.50 |

**The days he chose:**

| the day has | his 29 NASDAQ days | the other 147 days |
|---|---|---|
| a high-impact release | 44.8% | 45.6% |
| a President / Chair / Treasury speech | 31.0% | 29.3% |
| CPI, payrolls or a Fed decision | 20.7% | 17.0% |
| a surprise-flagged event | 13.8% (4 days) | 4.8% |

On the 4 surprise-flagged days, none of his entries came within 2 hours after the event.

**What it says:**
- **The calendar does not pick his moments or his days.** Nothing survives Holm, and his days carry
  releases and big speeches at the base rate.
- **The only hint:** on mornings with a release he sometimes takes a second or third trade. 13 of 46
  entries fell within 3 hours after a release against 8.2 expected, but counted once per day it is 7
  against 5.3. Those 13 all won, averaging $92.69 against $58.33 for the rest. That is 13 trades, and
  the rest include his one −$483.75 loss.
- **His biggest days had no scheduled news at all:**
  - 2026-09-14 14:14–15:02 ET: 7 trades, a −$483.75 loss first, then 6 winners;
  - 2026-08-10 18:30 ET, after the close: +$273.75;
  - 2026-08-07 and 2026-07-24.

  Nothing was on the calendar in the 3 hours before or the hour after any of them.
- **Where news did come just before, it was a speech or a release 20–50 minutes earlier:**

  | date | news before his entry | his trade |
  |---|---|---|
  | 01-21 | Trump spoke 23 min before | BUY, +$41 |
  | 03-16 | Trump spoke 34 min before | BUY, +$63 |
  | 02-11 | payrolls 44 min before | BUY, +$40.50 |
  | 02-20 | PCE 32 min before | two trades |
  | 01-26 | durable goods 50 min before | +$10 |

  That matches §24's reading of the charts: he trades the aftermath, not the release.
- **Gold and silver** (9 entries, with the 2026-02-02 burst of 37 counted once): 3 came within 3 hours
  after a release against 1.1 expected (p 0.035, Holm 0.24). That is too few trades to separate from
  chance. The burst itself (23:51–00:39 ET) had no dollar event near it.

**Predictions:**
- Right: no feature survives Holm; his days carry releases at the base rate; speeches are not at 2×.
- Slightly outside the registered 0.7–1.5× band: releases in the prior 3 h (1.59×) and "a release due in the
  next 60 min" (1.76×, 3 against 1.7), which I had put at or below control.

**Still untested: unscheduled headlines**, meaning Trump's Truth Social posts, which move markets without
appearing on any calendar. CNN keeps a public archive (`truth_archive.csv`, 14 MB), which needs the user's
OK to download. One thing limits what posts could explain: §24 found the bars before his entries
ordinary against the same clock time (the largest 5-minute range in the prior hour). A post that moved
NASDAQ before he entered would have shown there.

## 29. His trades against Trump's posts (2026-09-26)

These are the unscheduled headlines §28 could not see. They come from CNN's public Truth Social archive,
downloaded with the user's OK (`truth_archive.csv`, 14 MB, not committed). His period has 5,709 posts,
22 a day at all hours.

**`backtest/his_posts.py`** (`logs/his_posts.txt`) sorts the posts three ways:
- **every post**;
- **market-topic posts**: tariffs, China, the Fed, rates, stocks, the economy, oil, Iran and so on, 1,299
  posts. The word list is crude: "deal" also catches "The Real Deal" and ballroom posts.
- **posts NASDAQ jumped on**: the 5-minute bar holding the post, or the next one, at 2× its clock slot's
  usual range. There are 761, defined from the price alone, so they catch any post that "affected the
  market" whatever its words.

As in §28, each entry was compared with the same New York clock time on the other trading days.

| NASDAQ | every entry (46) | | first entry of each day (30) | |
|---|---|---|---|---|
| | his / expected | p | his / expected | p |
| any post in the prior 15 min | 8 / 5.9 | 0.35 | 6 / 3.8 | 0.24 |
| any post in the prior 60 min | 22 / 16.1 | 0.066 | 15 / 10.3 | 0.069 |
| a market-topic post in the prior 30 min | 2 / 3.9 | 0.31 | 2 / 2.5 | 0.74 |
| a market-topic post in the prior 60 min | 7 / 7.2 | 0.95 | 4 / 4.5 | 0.80 |
| **a post NASDAQ jumped on, prior 60 min** | **5 / 3.7** | **0.50** | 3 / 2.4 | 0.70 |

**Nothing survives Holm. Posts that moved NASDAQ came before his entries at the chance rate.** His trades
with any post in the prior hour earned less ($33.58 against $99.64), mostly because the −$483.75 loss is
among them.

**Two posts are worth reading all the same:**
- **2026-06-05, 10:33 ET**, just after a strong jobs report: "With a great Jobs Report... stocks should go
  up, not down." Twenty-nine minutes later he bought twice and sold once, +$375 in all.
- **2026-09-14, 13:33 ET**: a post on AI regulation. Forty-one minutes later his biggest session began:
  a −$483.75 buy, then six sells that made it back and more.

Neither post made NASDAQ jump. Over all 46 entries, market-topic posts came before them exactly as often
as chance (7 against 7.2), so two striking cases are what 46 trades throw up. They are not a pattern.

**His biggest days in posts:**
- **2026-08-10 18:30 ET:** no post in the 2 hours before.
- **2026-08-07:** two posts, about endorsements and the courts.
- **2026-07-24:** one post, about the Senate.

**Predictions:**
- Right: nothing survives Holm, and posts that moved the market sit at chance.
- Outside the 0.7–1.5× band: "a market-topic post in the prior 30 min" (0.51×, 2 against 3.9) and, for
  first entries, "any post in the prior 15 min" (1.56×).

### Where the news question stands
Scheduled news (§28) and unscheduled posts (§29) were both checked minute by minute against the same clock
time on other days. **Neither picks his moments or his days.** What the news record does show is his
style: he sometimes trades 20–50 minutes after a release or a post, in the aftermath. The same entries
come just as often on days with nothing on the calendar and nothing posted, and those include his biggest
days.

## 30. His sessions, and the retail toolkit at his moments (2026-09-26)

The user: "day is not a restriction for him. Sometimes he is so busy, then when free he makes the whole
10 percent that day. There must be something you are missing, cross check his everything."

### The sessions (from the statement, NASDAQ)
| | |
|---|---|
| sittings (days with a NASDAQ trade) | 30 |
| sittings with a single trade | **20** |
| sittings that ended on a win / net positive | **29 of 30** / 29 of 30 |
| first entry of the sitting, New York time | anywhere from 05:00 to 18:00 |

| month | sittings | NASDAQ profit | best sitting's share |
|---|---|---|---|
| Jan / Feb / Mar | 6 / 7 / 5 | $156 / $236 / $207 | 31% / 42% / 33% |
| Apr / May / Jun | 3 / 2 / 1 | $330 / $271 / $375 | 43% / **89%** / **100%** |
| Jul / Aug / Sep | 3 / 2 / 1 | $463 / $495 / $598 | 45% / 55% / **100%** |

**The user's reading is right.**
- He sits down whenever he is free and takes one to three trades.
- He leaves on a win. On 2026-09-14 that meant trading on after the −$483.75 until he was back in profit.
- From May on, one sitting makes most or all of the month's ~10%. At 0.20–0.25 lots, 7 points is $140–175,
  about 3% of the account, so two or three wins are the month.
- **The comparison that fits this is his moment against the other moments while he is at the screen.** That
  is §26's same-day ±20-minute design, used again below, not "his days against other days". The calendar and
  post tests (§28–29) compared the same clock time on other days; they still show that news does not mark
  his moments. Their day-level rows mean less, for the user's reason.

### The retail toolkit (`backtest/his_ta.py`, `logs/his_ta.txt`)
This is the chart method most retail traders in Pakistan learn. It was never tested here:
- **smart-money concepts:** liquidity sweep, fair value gap, break of structure, premium/discount, on 1-
  and 5-minute candles;
- **the standard indicators:** price vs EMA 9/21 and EMA 20 on 5 minutes, RSI, Stochastic, MACD, Bollinger %B,
  the 1-hour trend.

All are rebuilt from ticks, sign-aligned to his direction, and use closed candles only.

**Stage A: his 25 clean entries against ~80 moments of the same day within 20 minutes, same direction.**
| | his entries | p |
|---|---|---|
| EMA, RSI, Stochastic, MACD, Bollinger (1 and 5 min), trend, discount | ranks 0.40–0.54 | ≥ 0.09 |
| fair value gap (1 min / 5 min) | 1.31× / 1.18× the nearby rate | 0.49 / 0.67 |
| liquidity sweep (1 min / 5 min) | 1.10× / 1.33× | 0.83 / 0.52 |
| break of structure | 0.95× | 0.78 |

**Nothing survives Holm. Nothing is even near it.**

*A first run required 60 one-minute candles of warm-up. The tick cache starts at 09:30, so that silently
dropped the whole 11:00–11:15 cluster (17 of 26 kept). On those 17, his entries leaned against the 1-hour
trend (rank 0.35, p 0.029), but that faded to 0.40 (p 0.09) with all 25.*

**Stage B: 7,788 random moments on 118 days.**
- These features describe NASDAQ's ordinary short-term reversal. Price above its EMAs, or high
  oscillators, win the 3-minute race 3–5 points LESS, on both halves.
- A fair value gap adds +3.1 points (+2.4 / +3.8).
- **Nothing gets near break-even after the spread:** the best net win rate is 37.6% (fair value gap)
  against 35.8% for all moments, with 50% needed.

**Predictions:**
- Wrong: the sweep came out ordinary (1.10×), where I expected ~1.5×.
- Right: the rest are ordinary, nothing survives Holm, and in Stage B nothing moves the net race more than
  3 points.

### What his "10% day" is made of, in plain terms
**The structure:**
- a ~7-point target;
- no stop;
- one to three trades a sitting;
- leave when green;
- about 3% of the account per win.

This makes the ~10% month from one good sitting, and a green sitting almost every time. **The hidden cost
is the day a position does not come back.** His one such day cost 10% of the account ($483.75), and he
traded back from it.

**The skill:** the first 7 points go his way in 87% of his entries, against 54% for the other moments
around them (§26). **What picks that moment is not in:**
- the price, ticks or other markets;
- order flow;
- the news calendar or the posts;
- any smart-money or indicator reading.

## 31. Every 1-minute candle pattern at his moments (2026-09-26)

The user: "he does [it] on 1 minute I guess". Most of §17–30 was already on 1-minute candles:
- the last closed candle vs other days (`his_candles.py`);
- the rejection wick vs the same 20 minutes (`his_local.py`);
- trend-pause-resume as a rule (`his_micro.py`);
- smart-money concepts and indicators (`his_ta.py`);
- all 46 trades drawn on 1-minute charts (§24).

**What was not yet tested:** the full candlestick set, and the candle that is **forming** when he clicks.

**The test** (`backtest/his_1m.py`, `logs/his_1m.txt`): 13 patterns, sign-aligned to his direction. His 24
clean entries were compared with ~80 moments of the same day within 20 minutes, same direction, **at the same
second of the minute**, so the forming candle is equally old.

| pattern | his | nearby | ratio | p |
|---|---|---|---|---|
| inside bar (last candle inside the one before) | 6 / 24 | 12.0% | 2.09× | 0.044 |
| pin bar (≥ 60% wick against him, small body, close his half) | 4 / 24 | 7.6% | 2.21× | 0.086 |
| three candles his way | 4 / 24 | 8.3% | 2.01× | 0.13 |
| forming candle against him at his click | 14 / 24 | 47.0% | 1.24× | 0.26 |
| first pullback candle / two-candle pullback | 4 / 2 of 24 | 14.2% / 7.3% | 1.18× / 1.13× | ≥ 0.72 |
| engulfing / outside bar / tweezer / break of the previous candle | 2 / 0 / 1 / 5 | | 0.00–0.74× | ≥ 0.22 |
| doji / morning-evening star / sweep inside the forming candle | 4 / 1 / 3 | | 0.92–3.33× | ≥ 0.19 |

**Nothing survives Holm over 13** (the best is 0.58).

The small signs agree with §26:
- a quiet, indecisive last candle (inside bar, pin bar);
- the forming candle dipping against him.

**On all 118 days** (8,672 random minutes, entered 18 s past the minute as he does):
- The forming candle being against you is a real small edge: +4.2 points of 3-minute win rate (+4.5 /
  +3.9). This is the seconds-scale reversal §26 found.
- Outside bars and stars go the other way (−7 to −9).
- **No pattern gets the net race above 37%** (base 35.2%, 50% needed).
- Inside bars and dojis have no direction of their own, so they cannot be scored this way.

**Predictions:**
- Right: pin bar at ~2× with p ~0.05–0.09; nothing survives Holm; no net race above 40%.
- Wrong: the first pullback candle came out ordinary (1.18×), where I expected ~1.5×.

**Reading the 1-minute chart the way a 1-minute trader does does not find his pick either.** His moments
look like a quiet candle and a dip inside the next one. So do half the moments around them, and those win
the first 7 points 54% of the time, not 87%.

## 32. The 87% attacked, not assumed, and the big stocks checked (2026-09-26)

The user: "there must be something that tells them apart - he sees what we don't". Every search since §26
rests on one number (+7 before −7: 87% against 54%), so it was attacked first. The crack to test: net of the
spread his entries equal random (42% against 42%, §26).

### It holds, and it is about direction over minutes (`backtest/his_race_curve.py`, `logs/his_race_curve.txt`)
Symmetric race, his 25 clean entries against ~80 same-day moments within 20 minutes, same direction:

| race to ±T (600 s) | 2 | 3 | 4 | 5 | 6 | **7** | 8 | 10 | 12 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|
| his entries | 52% | 68% | 68% | 64% | 68% | **88%** | 80% | 80% | 80% | 82% |
| nearby | 53% | 54% | 54% | 55% | 56% | 57% | 58% | 59% | 60% | 61% |

- **With a +7 target and any stop from 3 to 20 points**, his entries lead by +12 to +31.
- **Counted by day** (his 25 entries fall on 12 days, and same-day trades are not independent):

  | race | days above nearby | mean edge | t |
  |---|---|---|---|
  | ±7 | 10 of 12 | +32.5 | 5.8 |
  | ±10 | 8 of 12 | +23.6 | 3.7 |
  | ±4 | 7 of 12 | +8.9 | 0.7 |

- **The path.** One minute after his entry NASDAQ is a median +6.6 points his way, against 0.0 for the
  moments around him. His worst point in that minute is a median −1.9.

**So the user is right that something separates his moments.** It is real directional information about the
next one to five minutes. It is not about the next few ticks: at ±2–4 points he is ordinary.

**Predictions:**
- Registered: that the edge would prove fragile (≤ +10 at small races, gone with tight stops, a dip first).
  **All three were wrong.** The edge is broader than I expected.
- Right: no broker lag (next part).

### His broker's prices, second by second (parts D and F)
- **No lag.** The real market's move over his exact entry and exit seconds matches his points best at a shift
  of 0 to +1 second. His broker quotes the real market in real time.
- **His costs.** The real mid moved a median 3.24 points more than he banked, so his broker's prices cost him
  about 3–4 points a round trip. Exness USTECm's spread is 1.1–3.6.
- **Entries** come after a small drop against him in the previous 1–6 seconds (~0.7 points), with no
  immediate bounce.
- **Exits** land on a tiny peak: 1–6 seconds later the price is back below it about 70% of the time. That is
  hitting a target on an up-tick, not a signal.
- The statement's type code "L" marks every trade row, with "WD" for withdrawals. It is the row type, not
  the order type.

### The big stocks, the dollar and bitcoin (`backtest/his_generals.py`, `logs/his_generals.txt`)
**The idea:** something leads NASDAQ by minutes, so the most obvious untested candidate is the stocks that
make up the index.

**The data:** on 114 days, the eight largest (NVDA, MSFT, AAPL, AMZN, GOOGL, META, AVGO, TSLA; about half of
NASDAQ's weight) as MT5 tick CFDs, plus the dollar index and bitcoin, on 1-second prices. They are aligned to
the second: the correlation of 5-second returns peaks at 0 s (0.67). The stocks lead Exness's NASDAQ by up to
5 seconds (0.12), not minutes.

| his entries vs the same 20 minutes | rank | p |
|---|---|---|
| the eight stocks ahead of NASDAQ, 30 s / 2 min / 5 min | 0.43 / 0.57 / 0.58 | ≥ 0.19 |
| the eight stocks' move; how many moved his way | 0.47 / 0.48 | ≥ 0.63 |
| NVIDIA ahead of NASDAQ, 2 min | 0.58 | 0.16 |
| the dollar (inverted) / bitcoin, 2 min | 0.40 / 0.48 | 0.08 / 0.70 |

- **Nothing survives Holm.**
- On all 114 days, none moves the 7-point race by more than +3.1 points (the stocks' 30-second lead). None
  gets the net race above 35.3%, with 50% needed.
- Prediction right.

### Where "what he sees" now stands
**What we now know about it:**
- It is real, about ten days out of twelve, and it predicts NASDAQ's direction over the next one to five
  minutes.
- It is not in NASDAQ's price, ticks, candles, patterns, smart-money readings or indicators.
- It is not in the S&P, the Dow, the eight biggest NASDAQ stocks, the dollar, bitcoin, gold or USDJPY.
- It is not in Binance's order flow, the news calendar or Trump's posts.

**What is left is only what no archive holds:**
- CME's live order book;
- a paid news terminal or squawk;
- a person or group sending him calls;
- his own read of something on his screen.

**One question to him settles it:** what is on his screen in the half-minute before he clicks?

## 33. Every feature at once: can a model see what he sees? (2026-09-26)

The user: "that's on us to figure out". Sections 17–32 tested features one at a time. What that cannot see is a
**combination**, several things each ordinary alone.

**The model** (`backtest/his_model.py`, `logs/his_model.txt`) takes 75 features at once:
- NASDAQ's tick path;
- the candles;
- the smart-money readings and indicators;
- the 1-minute patterns;
- the eight biggest NASDAQ stocks, the dollar and bitcoin;
- new: the raw path of the last 60 s (5-s slices) and last 5 min (30-s slices), where the price sits in the last
  candle, the Fibonacci depth of the pullback, and the dip in points.

**The task:** tell his moment from the 40 moments of the same sitting at whole-minute offsets within 20 minutes.
They have the same second of the minute and the same direction, and none is within 60 s of another of his
entries. Two models (logistic and random forest) were scored **only on days they never saw**, with a
shuffle test for what luck gives.

| | his moment's percentile in its group | luck (shuffle), mean / 95th pct | p |
|---|---|---|---|
| logistic | **0.505** | 0.497 / 0.673 | 0.36 |
| random forest | **0.486** | 0.490 / 0.642 | 0.55 |

**On the 106 days he did not trade,** the moments the models rate most like his win the 7-point race 50.4% /
49.1% of the time (base 50.0%) and net 35.5% / 34.5% (50% needed).

**Could the test have found anything?** (`--power`, `logs/his_model_power.txt`). A hidden 2–3 feature rule plus
noise picked one moment per group as "his", and the same pipeline had to recover it:

| hidden rule | plant's rank on its rule | recovered: logistic / forest |
|---|---|---|
| wick + dip + low in the candle | 0.98 / 0.89 / 0.79 | 0.96 / 0.78 / 0.74 · 0.88 / 0.73 / 0.75 |
| 30-s move + NVIDIA ahead | 0.98 / 0.87 / 0.75 | 0.93 / 0.72 / 0.75 · 0.92 / 0.78 / 0.74 |

**It could.** A combination that made his moment stand out even at rank ~0.75 would have come back at ~0.74,
far above luck's 95th percentile. His real moments come back at 0.49–0.51.

**Prediction:** registered "no model finds him" — right.

### What this settles
Two facts now stand side by side, each tested hard:
1. **His moment carries real information** about NASDAQ's next one to five minutes: 10 of 12 days at ±7, t 5.8
   (§32).
2. **That information is not in anything we can record.** Here "anything" means:
   - NASDAQ's ticks and candles, and every pattern, indicator and smart-money reading of them;
   - the S&P, the Dow, the eight biggest NASDAQ stocks, the dollar, bitcoin, gold and USDJPY;
   - Binance's order flow, the news calendar and Trump's posts;
   - and, now, any combination of them strong enough to see.

Whatever he looks at, it is not the price history. The candidates left are ones no archive holds:
- CME's live order book;
- a paid news or audio feed;
- a person or group sending him calls;
- something shown only by his own platform.

**The one way to settle it from our side is going forward, not backward:** record what we can live, and
compare it with his next trades as they happen.

## 34. Looking at his charts the way he does, and copying instead of decoding (2026-09-26)

The user: "you are not looking correctly". §25–33 measured. This time his trades were **looked at**.

**The charts** (`backtest/his_look.py` → `logs/his_look/01..25.png`). Each clean trade is drawn on **his broker's
price scale**: his own fills give the exact offset from USTECm that day. There are two views:
- the 5-minute session up to his entry;
- 1-minute candles from 45 minutes before to 12 minutes after.

The levels are drawn in: yesterday's high, low and close, today's open, the first-15-minute range, the day's high
and low, and round 25/50/100s. 17 of the 25 were read by eye.

**What they show:** a discretionary scalper using ordinary setups.
- **Pullbacks in the last 30–60 minutes' direction:** 07-24 sold the top of a small range in a downtrend; 08-07
  bought a dip in a range.
- **Level bounces, even against the trend:** 06-05 bought 29,800 twice in a falling market, then sold the top of
  the bounce; 04-06 bought the open and yesterday's high as support (+12.5), then sold into 24,300.
- **A breakout:** 07-10 bought the break above 30,000 at the day's high.
- **Every chart shows two to four look-alike setups** around his click, and he takes the one that works.

**The eye's impression, tested** (`backtest/his_keylevels.py`, `logs/his_keylevels.txt`). Against the rest of his
sitting at the same second of the minute:
- **Distance to key levels:** his entries sit a median 37 points from the nearest one (rank 0.54, ordinary).
- **Trading off support:** only 1 of 25 was within 10 points of a supporting level, against 6% of the other moments.
- **Round 50s on his scale:** rank 0.38 (p 0.040, Holm 0.20).
- **On 106 other days** none moves the 7-point race.

**Prediction wrong:** I registered that his entries would sit closer to key levels (rank ≤ 0.40). **The level
trades that catch the eye are 4 or 5 of 25.** That is the trap of reading charts by eye.

### Is the record real-time? (`backtest/his_extremes.py`, `logs/his_extremes.txt`)
His entries carry information no recorded data holds. So the other explanation had to be tested: trades not
decided in real time. §25 had already found his broker's January–March fills earning moves the market never
offered. **The exit tells them apart:** with a fixed target, a real-time exit is the first touch, and the price
after it is luck.

| rank among the prices around it (1 = best) | his | random entries exiting at the first touch of his points | p |
|---|---|---|---|
| exit, ±60 s / ±300 s | 0.77 / 0.71 | 0.75 / 0.69 | 0.56 / 0.57 |
| entry, ±60 s / ±300 s | **0.65** / 0.58 | 0.52 / 0.51 | **0.003** / 0.12 |

- **His exits look exactly like a mechanical target. His record is real-time.**
- His entries fall in the better part of the minute: a dip buyer, never the exact low (0% at ≥ 0.95).
- Prediction right.

### If he cannot be decoded, can he be copied? (`backtest/his_copy_delay.py`, `logs/his_copy_delay.txt`)
Each of his 25 clean entries was entered d seconds late at Exness's quotes, against the same-sitting moments:

| delay | mid race ±7 | net race ±7 (50% = break-even) | +7 target, no stop, net points a trade (win %) |
|---|---|---|---|
| 0 s | 88% (nearby 56%) | 44% (42%) | +6.28 (96%) |
| **5 s** | 84% | **72%** (41%) | +6.26 (96%) |
| **10 s** | 76% | **64%** (41%) | **+7.00 (100%)** |
| 20 s | 72% | 48% | +0.98 (92%) |
| 30 s | 68% | 52% | +1.64 (96%) |
| 60 s / 120 s | 72% / 38% | 48% / 29% | +0.11 / +0.75 |

The nearby moments make +3.6 a trade with his exit, because they borrow his direction for the ±20 minutes around
his entry. They are not a tradable baseline.

**Why a 5–10 s copy beats his own second:** in 24% of his entries the price flushes 3–11 points against him in the
first 5 s, then turns (`median worst −1.46`). He clicks inside the dip and holds through it. A copier 5–10 s behind
often enters after the flush. **Exness's USTECm spread is fixed through the day** (1.12–3.60 by day), so no spread
spike explains it.

**The edge survives a copy delay of up to ~10 seconds and is gone by ~20.** At Exness, USTECm is $1 a point per
lot (0.05 lot minimum). His sizing (~$20–25 a point on ~$4,500) scales to ~1.5 lots on $300: about +$10 a winning
trade and −$48 on a −31.75-point day like 2026-09-14.

**This is 25 trades on 12 days, and the ±7 net race is sensitive to a point or two, so these are not planning
numbers.** Prediction: registered "≥ 75% mid race to 10 s, net ≥ 60%, ≥ +3 points a trade at 5–10 s". Right, except
that I expected a 0-s copy to be the best.

## 35. Was his January–March clock one hour off? A missed clue in our own table (2026-10-01)

Found by re-reading `logs/his_vs_market.csv` (46 NASDAQ trades with the real market's move during each hold) with no
new data. Split at the European clock change, **2026-03-29**, the record looks like two different traders:

| | before 29 Mar (19 trades) | after 29 Mar (27 trades) |
|---|---|---|
| real market moved his way | **37%**, −1.3 points | **96%**, +10.2 points |
| \|his points − market move\| (= his broker's basis jump inside the trade), median | 11.0 | 3.2 |
| his broker's basis at entry, across days | erratic, **−192 … +351** | smooth futures roll-down: 163 → 9 into the June expiry, 217 → −18 into September |
| his sitting time, Pakistan clock (no DST there) | 19:14 | 20:38 |

**§25 read the left column as "his January–March prices are not the market's".** A clock error produces the same
picture: compare his fill with the market at the wrong hour and the basis becomes the market's one-hour move (hundreds of
points, random sign), while "the market's move during his hold" becomes the move of some other few minutes (≈ 0 on
average). The break falls between his 03-16 trade (still erratic) and his 03-31 trade (clean) - after the US change
(03-08), at the European one (03-29), which is when many broker servers move their clocks.

**Why it was never caught.** Every script converts with one constant, `GMT = 5.0`. §14's three alignment methods split
between UTC+4 and UTC+5 on 26 entries, 11 of them from winter. §15 then tested only +0 / +3 / +5 / +7, pooled across all
months. §25's clock check searched only ±600 s, pooled. None could see a one-hour error confined to winter.

**The test** (`backtest/his_clock_check.py`, run on the PC with the MT5 terminal): for each offset and separately per
period, place his entry and exit at statement time − offset and read the real USTECm mid at both. With the right clock
his points equal the market's move minus his costs. `tests/test_his_clock_check.py` plants a one-hour winter error in a
synthetic market and the check finds it (UTC+4, error = the planted 2-point cost), and on a market with no error it finds
+5 everywhere.

**REGISTERED PREDICTION, before any run on his real data:**
- after 29 Mar: best offset UTC+5 - the control; if not, the method is broken;
- before 08 Mar: best offset **UTC+4**, median |pts − mv| ≤ 5 and the market his way in ≥ 80% of trades (against 11.0
  and 37% at UTC+5).

**If it is confirmed:**
- the "off-market prices" finding of §25 was the clock, not his broker - the strongest remaining doubt about the record
  goes away;
- ~19 January–March NASDAQ trades rejoin the clean sample (**25 → ~44**), nearly doubling the power of the copy-delay
  test in §34, which is the one that decides whether he can be copied;
- every §17–§34 result that used January–March times (the second-of-the-minute effect, which §25 found "stronger in
  January–March", news timing, the model in §33) has to be re-run at the corrected offset.

**A third sign, from the same table.** Under the one-offset clock, **10 of his 19 winter trades fall before the New York
cash open** (median 09:19 ET) against 1 of 27 in summer - odd for a NASDAQ scalper. With the winter hour corrected, 3 of 19
(median 10:19 ET), and his winter sitting moves to 20:01 Pakistan time against 20:38 in summer.

**Cross-checking his charts, as the user suggested (2026-10-01).** It was done for April on only: `his_look.py` (§34)
skipped January–March because its prices did not match, and `his_charts.py` (§24) drew those trades at UTC+5. So the
19 winter trades have never been seen at what may be their real hour. `his_look.py` now takes `--winter-gmt`, `--since`
and `--out` (defaults unchanged); after the clock check, on the PC:
`python -m backtest.his_look --winter-gmt 4 --since 2026-01-01 --out logs/his_look_all`.
`tests/test_his_look.py` runs it end to end on a fake cache: defaults reproduce the old output, the option draws a
winter trade at the corrected hour, and the old clock pushes it before the open where it cannot be drawn.

**If it is not confirmed** (best winter offset stays UTC+5), §25's reading stands and the January–March prices really
were not the market's.

### 35b. Which clock moved? MT5's own labels, checked against the US cash open (2026-10-01, local review)

`his_clock_check.py` measures the offset **between** his statement and MT5's USTECm data. It cannot tell which of the
two clocks carries the seasonal hour, and the two readings point at different re-runs:

- **(a)** his statement is UTC+4 in winter, MT5 is UTC → every result that compared his **winter** trades with an
  **outside** clock is suspect;
- **(b)** his statement is UTC+5 throughout, MT5 shifts in winter → those results stand, and the winter MT5 reads move.

**The anchor** (`backtest/mt5_clock_anchor.py`, `logs/mt5_clock_anchor.txt`): the US cash open at 09:30 New York time
is a jump no feed can hide, at 14:30 UTC under EST and 13:30 UTC under EDT; the EU change does not move it. MT5's
5-minute USTECm bars (the only cache reaching January) were scanned for the biggest step-up in range per period.
**Prediction registered first:** 14:30 / 13:30 / 13:30, i.e. MT5 is UTC.

| period | days | open bar | step-up vs prior hour | at 14:30 | at 13:30 |
|---|---|---|---|---|---|
| before 08 Mar | 46 | **14:30** | 4.37× | 4.37× | 1.89× |
| 08–29 Mar | 15 | **13:30** | 3.04× | 0.76× | 3.04× |
| after 29 Mar | 66 | **13:30** | 3.77× | 0.87× | 3.77× |

**Prediction right. MT5's labels are true UTC in all three periods** — they follow the US change on 08 Mar, ignore the
EU one on 29 Mar, and show one clean spike each. So **if the clock check confirms UTC+4 in winter, the hour is in the
timezone the statement's times are written in** - reading (a). That is a statement about the CLOCK, not about the
trades: a genuine statement written in a broker's server clock shifts by an hour in March even though Pakistan's
clock does not, and every script here read it as UTC+5 for all nine months.

**Provenance, from the user (2026-10-01):** the statement is genuine - the user downloaded it from **VertexPro**
themselves. That weighs for the clock reading over §25's. §25's alternative was that his January–March fills "were
not the market's" (about half his winter trades earning more than the market ever offered); on a statement taken
straight from the broker that is the harder thing to believe, while a clock mismatch needs nothing faked.

**How a genuine download produces exactly this (a hypothesis, not checked).** Most brokers run server time at GMT+2
in winter and GMT+3 in summer. If VertexPro does, and its statement converts server time to the viewer's Pakistan
time with ONE offset - the +2 h of the day it was downloaded, in summer - then summer rows land at UTC+5 and winter
rows at UTC+4, which is §35's pattern. VertexPro's own server clock could not be found online, so this stays a
hypothesis. **It adds one registered prediction, made before the clock check runs:** the statement's change follows
the broker's DST date. §35 already noted his 03-16 trade is still erratic at UTC+5, which points to the EU date
(29 Mar), not the US one (08 Mar). So: **the 08–29 Mar trades read best at UTC+4, like January–February.** If they
read at UTC+5, the change is on the US date and the mechanism is different.

**What that adds to the handoff (`docs/LOCAL_MT5_TASKS.md` step 4).** Its list is scripts that *excluded* winter and
would gain trades. Three scripts *included* his winter trades and compared them with outside UTC clocks, so under (a)
their winter results sat at the wrong hour — not under-powered, contaminated:

| script | section | winter trades in? | compared with |
|---|---|---|---|
| `his_calendar.py` | §28 | yes, from 2026-01-02 | ForexFactory release times |
| `his_posts.py` | §29 | yes, from 2026-01-02 | Trump's post times |
| `his_news.py` | §24 | yes, no date filter | news footprints at the same clock time |
| `his_orderflow.py` | §27 | no, from 2026-04-07 | unaffected |

If the clock check confirms, re-run these three at `--winter-gmt 4` alongside step 4's list, and report winter and
summer separately. **Not yet run: the clock check itself** — it needs the MT5 terminal open for January–March ticks,
and the terminal was closed when this was written. The 5-minute bars cannot stand in for it: his holds are 1–5
minutes, so they cannot measure his points against the market's move.

### 35c. The clock check, run: CONFIRMED (2026-10-02, local session, Exness MT5 ticks)

`python -m backtest.his_clock_check` (`logs/his_clock_check.txt`, per trade and offset in `logs/his_clock_check.csv`),
against the predictions registered in §35 and §35b before the run:

| period | trades | best offset | median \|pts − mv\| | market his way | at the old UTC+5 |
|---|---|---|---|---|---|
| before 08 Mar | 18 | **UTC+4** | **4.29** (registered: ≤ 5) | **94%** (registered: ≥ 80%) | 9.99, 39% |
| 08–29 Mar | 1 | UTC+3 (2.44); UTC+4 5.08 | — | — | 17.57, wrong way |
| after 29 Mar (control) | 27 | **UTC+5 — PASS** | 3.19 | 96% | — |

**Trade by trade.** Of the 19 winter trades, **12 are decisive** (the two clocks differ by more than 5 points) and
**all 12 favour UTC+4; none favour UTC+5.** The other 7 fall in quiet hours where both clocks fit within ~6 points.
One trade keeps a large error at UTC+4: **2026-01-02** (the first session of the year), market +50.2 his way, his
points +38.2 — right direction, he caught less of the move. Named, not averaged away.

**Against the predictions.** §35's three are all right: control UTC+5, winter UTC+4, error ≤ 5 and ≥ 80% his way.
§35b's added one was that the 08–29 Mar trade reads best at UTC+4. **Its literal form missed** — the best is UTC+3,
with UTC+4 second — but its substance held: on one trade UTC+5 is clearly wrong (17.6, wrong way), so the statement's
clock changed on the **EU date (29 Mar), not the US one (08 Mar)**, as the broker-server-time mechanism predicts.
One trade cannot separate +3 from +4.

**What it means.**
- **§25's "his January–March prices were not the market's" was the clock, not his broker.** At the right hour his
  winter trades match the market as closely as his summer ones (4.3 against 3.2 points; 94% against 96% his way).
  With the statement confirmed genuine by the user (VertexPro, §35b), the strongest doubt about his record is gone.
- **He was as good in winter as in summer** — 94% of winter trades had the market moving his way, not 39%.
- **The clean sample grows from 25 to ~44 trades** for the tests that decide whether he can be copied.
- **Three results are contaminated and must be re-run** with winter at UTC+4 (§35b): `his_calendar.py` (§28),
  `his_posts.py` (§29), `his_news.py` (§24) — each put his winter trades an hour early against an outside clock.

**Next (docs/LOCAL_MT5_TASKS.md steps 2–4):** add January–March to the tick cache, read the winter charts at the
corrected hour (prediction first), and re-run the deciding tests on ~44 trades, `his_copy_delay.py` first.

### 35d. The deciding tests on ~44 trades — PREDICTIONS, registered before any run (2026-10-02)

The January–March days are now in the tick cache (`his_tick_cache.py`: 63 days fetched, none missing; 181 days in
all). `his_copy_delay.py` takes `--winter-gmt / --since / --until / --out`; its defaults reproduce the committed
`logs/his_copy_delay.txt` byte for byte (checked before any new run).

1. **Copy test, winter trades alone** (`--winter-gmt 4 --since 2026-01-01 --until 2026-03-29`): the summer thresholds
   from §34 hold — a 5–10 s copy wins ≥ 60% of net ±7 races and makes ≥ +3 points a trade with his exit, while the
   same-sitting moments lose. Reason: §35c shows his winter entries as close to the market as his summer ones.
2. **Copy test, all ~44 trades:** within 10 points of the 25-trade result on every row.
3. **The 87% race (`his_local.py`) on ~44 trades:** his moment still beats the same-sitting moments, p < 0.01.
4. **The decoder (`his_model.py`) on ~44 trades:** STILL at chance (rank 0.45–0.55). More trades add power, but §33's
   planted-pattern test found 2–3-feature patterns at 0.72–0.96 on 25 trades, so if his pick were in these features
   it would already have shown. If it rises above 0.60 on both models, that is the first sign of a decodable rule.

### 35e. The ~44-trade re-runs: his edge replicates out of sample, and still cannot be decoded (2026-10-02)

Every script below took `--winter-gmt / --since / --until / --out`, and **each was first checked to reproduce its
committed log byte for byte with the defaults** (`his_copy_delay`, `his_local`, `his_race_curve`, `his_model`,
`his_calendar`, `his_posts`, `his_news`). Two fixes were needed along the way: `his_race_curve.py` reuses the name `a`
for its own results, which overwrote the options; and `his_model.py`'s OTHER DAYS check now uses the same window as
his trades, because the tick cache now reaches January. The cross-market cache was filled for January–March too
(`his_generals.load`: stocks 61/63 winter days — the two gaps are US stock holidays — dollar index and BTC 63/63).

**1. His edge replicates on trades never analysed at the right hour** (`logs/his_race_curve_{winter,all}.txt`):

| ±7-point race, mid, 600 s | his entries | same-day nearby moments | edge | binomial p |
|---|---|---|---|---|
| summer (the original sample) | 22/25 = 88% | 57% | +31 | 0.0009 |
| **winter alone** (out of sample) | **14/15 = 93%** | 55% | **+38** | **0.002** |
| **all** | **36/41 = 88%** | 55% | **+33** | **7e-6** |

At ±10 points his winter entries won 15 of 15. Prediction 3 (p < 0.01) right.

**2. Copying him** (`logs/his_copy_delay_{winter,all}.txt`, Exness quotes, his +7 target and no stop):

| all 46 entries | 0 s | 5 s | 10 s | 20 s | 30 s |
|---|---|---|---|---|---|
| net race (break-even 50%) | 56% | **66%** | 56% | 46% | 54% |
| his exit, points a trade | +6.57 | **+6.56** | **+7.00** | +0.68 | +1.06 |
| same exit at nearby moments | +2.85 | +2.68 | +2.51 | +2.42 | +2.22 |

A copy within 5–10 s keeps his edge (+4 points a trade over the same exit at random moments); by 20 s it is gone.
Prediction 1 (winter, ≥ 60% net races and ≥ +3 points at 5–10 s): half right — 60% at 5 s but 47% at 10 s, while his
exit made +7.00 at both. Prediction 2 (all within 10 points of the 25-trade result): 12 of 14 rows.
**Caution: the +7 target with no stop is profitable at RANDOM moments in this sample (+2.5 to +2.9)** — a 2026 NASDAQ
that mostly rose. Its losers are large and rare; 46 trades do not sample that tail.

**3. The markers, on 41 entries** (`logs/his_local_all.txt`): all 13 rank 0.44–0.56 against 0.50; nothing near Holm.
The three §26 markers (the 30-s dip, the rejection wick, the round-25 level) are 0.44, 0.53 and 0.44.

**4. The decoder** (`logs/his_model_all.txt`, 75 features, logistic and forest, scored on days the model never saw):

| | summer only (24 entries, 12 days) | all (33 entries, 20 days) | null |
|---|---|---|---|
| logistic | 0.505 (p 0.36) | **0.445 (p 0.78)** | 0.495 |
| forest | 0.486 (p 0.55) | **0.469 (p 0.68)** | 0.495 |

Still at chance with a third more entries and two thirds more days. Prediction 4 right. On days he did not trade, the
models' top 10% of moments win the race 50.4% / 49.0% against a 50.0% base.

**5. The three contaminated news tests, re-run at the corrected clock** (`logs/his_{calendar,posts}_fixed.txt`,
`logs/his_news_fixed.txt`): the numbers moved, the conclusions did not. Strongest features after Holm: a release within
3 h 0.27 (was 0.31), a market-topic post within 60 min 0.35, recency of a price shock 0.19. **News does not pick his
moments, at either clock.**

**WHERE THE REVERSE-ENGINEERING STANDS.**
- **What his trades DO — solved, and replicated out of sample.** He picks direction over the next 1–5 minutes on
  NASDAQ, right ~88% of the time at a ±7 race against ~55% for the same day's other moments, as strong in January–March
  as in April–September. His record is genuine (statement from VertexPro, §35b) and real-time (§34).
- **HOW he picks them — not recovered at all.** 13 named markers, 75 features in two models, 8 mega-cap stocks, the
  dollar, bitcoin, Binance order flow, the news calendar, Fed speakers and Trump's posts all rank his moments at chance.
  §33's power test showed a planted 2–3-feature rule would be found at 0.72–0.96 on fewer entries than this. Whatever
  he reads is not in any data recorded here: most likely the live order book / tape, or something off-screen.
- **The only route to his edge is to COPY him, not to decode him** — and the data say a copy within 5–10 s works.

**A footnote that supports §35b's mechanism.** The statement's own first line declares ONE offset for the whole file
(`GMT … : 5.0`, quoted in §16), and every script took it at its word. Its winter rows are UTC+4 (§35c). A single
declared offset over a server clock that changed in March is exactly the mechanism §35b proposed.

*Privacy check before this commit:* every staged file was searched for the statement header's name and account
tokens (read from the gitignored raw file, never printed). Two generic header words matched, both already in the
pushed doc; no name and no account number.

### 35f. His January–March charts at the corrected hour — PREDICTION, registered before drawing (2026-10-02)

The winter charts show the same ordinary setups as summer (§34): pullbacks in a 1-minute trend, level bounces, with
2–4 look-alikes per chart he did not take; nothing on the chart recurs at his clicks and not at the look-alikes.
Reason: the decoder found nothing on 33 entries including winter (§35e), and §34's eye impression of key levels
already failed its test.

**Result (2026-10-02).** `his_look.py --winter-gmt 4 --since 2026-01-01` drew 42 of 46 trades (`logs/his_look_all/`;
4 fall before 09:30 ET or on a day without ticks). The 15 winter charts read by eye, for the first time at their real
hour:
- **buys on a strong 1-minute push through the day's high or the opening-range high** (#4, #5, #6, #10);
- **fades of an exhausted spike at or just under the day's high** (#1, #2, #8, #9, #11 — #11 sold the same spike #10
  had bought a minute earlier, +19.5 against +1.25);
- **a sell into the day's low in a downtrend, and a buy bouncing off it** (#3, #7);
- **mid-range entries on a small pullback or V-turn** (#12–#15).
Every chart has look-alike candles within minutes that he did not take. **The prediction held: the same ordinary
setups as summer, nothing new.**

**One eye impression, tested before it was believed** (`backtest/his_day_extreme.py`, `logs/his_day_extreme.txt`).
By eye, 11 of 15 winter entries sat "at the day's high or low". Isolated against the same-sitting moments on 42
entries:

| distance to … | rank (low = his are closer) | his median | Holm |
|---|---|---|---|
| the nearer day extreme | 0.47 | 38.6 pts | 0.48 |
| the extreme behind his trade | 0.42 | 90.3 pts | 0.048 |
| the extreme ahead of his trade | 0.58 | 137.3 pts | 0.048 |

**The eye was wrong**: his median distance to the nearer extreme is 39 points and only 7% are within 10 — a 400-point
day chart makes 39 points look like "at the high". The two Holm-0.048 rows are one finding, not two (within a sitting
the day's range is fixed): he enters with somewhat more room ahead than the sitting's other moments, as
`his_keylevels.py`'s "room" also shows (0.59 on 42 entries, `logs/his_keylevels_all.txt`). **Stage B closes it: room
ahead does not win races at random moments** (far third 50.7% vs near third 49.2%; halves −0.8 / +3.6). A mild
preference of his with no edge in it. The registered prediction said "nothing near Holm"; two rows reached 0.048, so
it was partly wrong — and the finding is still empty.

## 36. How he chooses DIRECTION — not from the price, at any horizon (2026-10-02)

The user: *"I want to copy his strategy, not his trades."* Everything since §26 asked WHEN he enters. WHICH WAY was
flagged in §14 as "the next analysis" and never run. `backtest/his_direction.py` (`logs/his_direction.txt`, 42 entries
with ticks at the corrected hour), predictions registered in the file before the run.

**1. Fade or follow.** The market's move into each entry, signed by his side:

| horizon | 15 s | 30 s | 1 m | 2 m | 5 m | 15 m | 30 m |
|---|---|---|---|---|---|---|---|
| he follows it | 54% | 45% | 44% | 48% | 52% | 57% | 59% |
| binomial p | 0.76 | 0.64 | 0.53 | 0.88 | 0.88 | 0.44 | 0.34 |

**Nothing.** He follows and fades the prior move about equally at every horizon from 15 seconds to 30 minutes. Winter
and summer differ in places (30 s: 60% vs 36% followed) but neither is consistent.

**2. Give a mechanical rule his timing and let it pick the side.** At his own moments, "follow the last H" and "fade
the last H" for all seven horizons win the ±7 race **42–57%** (best: fade the last minute, 57%). **He wins 88%.**

**What that means — the most important structural fact about his method found so far:**

| | ±7 race won |
|---|---|
| his moment AND his side | **88%** |
| nearby moments (±20 min), his side | 55% |
| his moment, side chosen from price history (best of 14 rules) | 57% |

Neither half works alone. His timing with a price-based side is a coin flip; his side at other moments is barely
better. **At the moment he clicks, he knows which way the next 1–5 minutes will go, and that knowledge is not in the
price before it.** Predictions: (1) no horizon above 75% — right (max 59%); (2) 30 s faded more than followed overall
(45%) and 5 m followed slightly (52%), winter fading 5 m more — right in direction, all weak; (3) best rule under 70% —
right (57%).

**What can carry that.** Information that tells DIRECTION at a moment, and is not in price history:
1. **order flow on the real futures** — aggressive buying or selling hitting CME NQ before the price moves (tape
   reading). Never tested on the real futures: §27 used Binance's QQQ perp, a thin crypto proxy;
2. **the order book** — large resting orders, absorption, pulled liquidity, on the real futures;
3. **an unscheduled headline** — the scheduled calendar, Fed speakers and Trump's posts are tested and closed; the live
   headline wire (squawk) is not;
4. **someone else** — a signal service or a room.
Everything else free has been tested: price, ticks, candles, indicators, SMC, levels, the day's range, 8 mega-caps,
S&P, Dow, the dollar, gold, USDJPY, bitcoin, scheduled news, posts.

**The one decisive test left, and it may be free.** Hypotheses 1 and 2 need the real CME NQ futures — every trade with
its aggressor side, and the book. Databento serves both (Trades, MBP-10) and gives **$125 of free data credit to every
new account** (databento.com/pricing, checked 2026-10-02). Only ±20 minutes around each of his 42 entries is needed,
so the request is small; the plan is to price it with Databento's cost endpoint before downloading anything. The test
that would decide it: **does the sign of aggressive futures flow in the seconds before his click predict HIS side** at
his moments, and not at the nearby ones? If yes, he reads the tape and a bot can too. If no, what he sees is
off-screen. The user would have to open the account; the key goes in an environment variable, never in a chat or file.

## 37. The tape: real CME NQ order flow at his moments — RULED OUT (2026-10-02)

`backtest/his_tape.py` (`logs/his_tape.txt`), predictions registered and committed before any data was fetched.
Databento GLBX.MDP3 `trades` with the aggressor side, front-volume NQ, 22 min before to 20 min after each entry:
**801,045 trades in 31 windows, priced at $1.33** of the user's free credit before download. Raw CME data stays in the
git-ignored data folder; only these aggregates are committed. 42 entries, 1,553 same-sitting moments.

| test | result | registered |
|---|---|---|
| **A.** aggressor-flow sign agrees with HIS side at his click (5 s – 120 s) | **48–55%** all trades, 45–63% on 5+ lots, every p > 0.11 | 60–75% |
| **B.** his moment's flow, signed his way, ranked among the sitting's moments | **0.48–0.54**, every p > 0.38 | 0.55–0.65 |
| **C.** trade WITH top-decile flow at the sitting's moments | **46–52%** of ±7 races | 52–56% |

**All three predictions wrong, all toward less signal.** Aggressive buying and selling on the real futures in the two
minutes before his click carries neither his side nor his timing, and is not an edge at any moment either. §27's
Binance proxy said the same; this is the real market saying it. **He is not reading the trade tape.** What remains from
§36's list: the order book (resting size, not trades), a live unscheduled headline, or someone else.

**From the user (2026-10-02): he trades several accounts, with the same success rate on each.** That is the answer to
the one explanation no data could reach — that the statement is the lucky account out of several. If the other
accounts' records are real and show the same rate, selection across accounts cannot produce it: either they are the
same trades copied (one outcome, not a draw from many), or different trades that all win (independent evidence of a
real edge). **Not yet seen:** the other statements themselves. If they can be downloaded like this one, they decide two
things — whether the entries are the same moments across accounts, and, if not, they add trades for every test above.

**Selection across accounts, closed by arithmetic (2026-10-02).** The other accounts belong to his clients and cannot be
seen (the user). They are not needed. Counting by DAY, since trades in one sitting share the market: he won the
majority of his ±7 races on **22 of 23 trading days** (3 ties), against a 55% day for the sitting's other moments —
**p = 2.1e-5**. For one account this good to arise by luck and be the one shown, a manager would need **~47,000
accounts** trading at random (~350,000 against a 50% day). **His edge is real.** The question is only what he sees.

## 38. The order book: real CME NQ depth at his moments — RULED OUT (2026-10-04)

`backtest/his_book.py` (`logs/his_book.txt`), predictions committed before any data. Databento GLBX.MDP3 `mbp-10`
(10 levels a side), the same 31 windows, priced at $8.30 and reduced in chunks to **81,766 one-second book
snapshots**. 42 entries, 1,553 same-sitting moments. Features: top-of-book imbalance (q1) and its 30-s average, 5- and
10-level imbalance, and liquidity pulled over 30 s.

| test | result | registered |
|---|---|---|
| **A.** the book leans HIS way at his click | **38–56%**, every p > 0.26 | 50–60% |
| **B.** leans his way more at his moment than at the sitting's others | **0.49–0.52** on four features; top-of-book **0.39** (p 0.019, Holm over 5 ≈ 0.10) | 0.45–0.55 |
| **C.** trade WITH a top-decile lean at the sitting's moments | **43–51%** of ±7 races | 50–55% |

The one outlier points the other way — at his click the best level leans slightly AGAINST him — and does not survive
correction. **With §37, the real futures market is closed: neither its trades nor its book carry his side or his
timing.**

**Where his method stands after §36–§38.** At his click he knows which way the next 1–5 minutes go (§36), across 22 of
23 days (selection ruled out, p 2.1e-5). That knowledge is not in price, candles, indicators, levels, related markets,
scheduled news, posts, futures trade flow or the futures book. What remains cannot be recorded from market data: a live
headline (the Benzinga wire is testable — `his_headlines.py`, waiting on the user's free Alpaca keys — but a squawk is
not), a signal he follows, or something on his own VertexPro screen. **The way left to learn it is to see his screen or
ask him what he watches.**

## 39. A critical re-read of the lens (2026-10-04): limit orders, tickets, his broker's feed, higher timeframes

The user: *"I'm sure there is something we are missing, or not looking at through the right lens — how does a person
with 20 years of experience decide entry?"* Every test so far assumed the statement's entry second is the moment he
decided, and looked for what he saw then. Four ways that lens could be wrong were checked.

**1. Resting limit orders (the market chooses the moment, not him).** His NASDAQ fills are on a **quarter-point grid**
— the real NQ futures tick, confirming his instrument is futures-priced — spread evenly across .00 / .25 / .50 / .75;
multiples of 5 points 9% against 5% expected. No clustering on round prices, and §36 shows no strong fade into his fills
at 5–15 s, which a limit fill would force. **Mostly market orders.**

**2. The tickets (a clock independent of the timestamps).** His broker is small: its counter advances ~2,570 orders a
day across all clients. Four fills carry tickets older than earlier fills, and one evening (09-14) looked at first like a
trade recorded 35 minutes after its stamped open. **That reading was wrong, and so was the pending-order one.** Across the
whole record, in **all 8 overlapping pairs whose open order and close order disagree, the tickets follow the CLOSE
order** — the statement prints each trade's **closing-deal ticket**. The tickets say nothing about when a trade opened.

**3. A slow feed at his broker (latency against a B-book).** §34's test D matches the points he banked against the real
move over [open + d, close + d]: the best fit is **d = 0 s (summer) / +1 s (all)**. A lagging feed would put it at a
negative d. **His broker's prices do not lag the real market.**

**4. Direction from the higher timeframe** (`backtest/his_direction_htf.py`, `logs/his_direction_htf.txt`, predictions
committed first). His side against the trend over 1 h, 2 h, 4 h, 8 h, 1, 3, 5, 10 and 20 days: **43–63% agreement, none
significant**; against price vs EMA-50 / EMA-200 on 1-hour bars: 63% / 52%. Given his timing, "trade with the trend"
wins the ±7 race **32–66%** at every horizon. Prediction 1 (a 55–70% lean toward the 4-hour or daily trend) wrong — no
horizon leans significantly; prediction 2 (best rule under 70%) right.

**Also: decisions at higher-timeframe candle closes.** His entries do not cluster after 5-, 15- or 30-minute closes
(7, 5, 3 entries against 9.2, 3.1, 1.5 expected); they do sit 5–24 s into a minute (24 of 46, p 0.011) — a reaction a
few seconds after 1-minute candles, which §31 already tested pattern by pattern.

**Where that leaves the lens.** His side is not in the price at any horizon from 15 seconds to 20 days (§36, §39), and
his moment is not in the futures tape, book, news calendar, posts or related markets (§26–§38). The edge itself is
beyond doubt (25 of 26 days at ±10, §35e). Information that predicts the next minutes and leaves no trace in anything
recorded before them comes from outside the market's record: a feed (squawk or signal) — the Benzinga part is testable
with the user's Alpaca keys — or his own screen.

## 40. The futures–cash gap at his moments — ruled out; and a lead for US, not him (2026-10-04)

`backtest/his_basis.py` (`logs/his_basis.txt`), predictions committed first. Real NQ futures mid each second
(Databento bbo-1s, **$0.14**) against the Exness USTECm cash mid, around his 42 entries and 1,553 sitting moments.
- **The gap barely moves:** median within-window sd **0.48 pts** (0.24–1.30). Exness's cash CFD tracks the futures
  tightly — prediction 1 right.
- **Not his signal:** the gap's deviation points his way 50–60% (all p ≥ 0.28); ranks 0.49–0.52. Prediction 2 right
  for A and B.
- **C came out backwards:** betting on the gap snapping back won **38–44%** of ±7 races — so the opposite, *Exness
  follows the futures*, won **56–62%** (300 s window, n = 150). Prediction 2 for C (48–55%) wrong. This is not about
  him; it is a candidate lead-lag edge — the CME futures leading the Exness quote — measured on overlapping moments
  around his entries, which is not a valid sample for it. It needs its own test (doc 21).

## 41. A veteran's session rules against his side — nothing (2026-10-04)

`backtest/his_veteran.py` (`logs/his_veteran.txt`), predictions committed first; 42 entries with a full session.

| rule | agrees with his side | at his moments, the rule's side wins the ±7 race |
|---|---|---|
| fade the opening gap | 45% (p 0.64) | 49% |
| revert to session VWAP | 55% (p 0.64) | 68% |
| trade with VWAP | 45% | 32% |
| above the day's open = buy | 48% (p 0.88) | 34% |
| time of day | buys 52% before noon ET, 48% after | — |

Both predictions right: nothing outside 30–70%, best rule 68% against his 88%. **Behaviour:** within a sitting he keeps
his side 10 of 15 times (switches 33%, p 0.30), median 2.9 minutes between trades — not a two-sided range scalper.

**The lens, after §39–§41.** Every way an experienced trader reads a chart has now been put against his direction —
1-minute to 20-day trend, EMA filters, gap, VWAP, day open, key levels, the day's range, candle patterns, SMC,
indicators — and his timing against the real futures tape, book and futures-cash gap. Nothing recorded before his click
explains him, while what happens after it does, on 25 of 26 days. A veteran's edge of that kind is real-time judgment of
something we have no record of. The remaining recordable candidate is the news wire (`his_headlines.py`, waiting on the
user's Alpaca keys); after that, only his screen or his own account of what he watches.

## 42. Are his fills real? Yes — and his broker costs him, it does not favour him (2026-10-04)

The CLAUDE.md §9 question: what makes his record look this good? Test D (§34) showed he banked **+3.47 points more**
than the market moved over his holds at a zero offset — half a +7 trade, unexplained. `backtest/his_fills.py`
(`logs/his_fills.txt`), predictions committed first: every real print on his exact contracts (NQH6 / NQM6 / NQU6,
Databento `trades`, **$0.79**), 5 s before to 6 s after each of his entry and exit seconds; 45 of 46 trades.

| | result | registered |
|---|---|---|
| his price inside the real traded range of its second (±1 s) | **31%** entries / 31% exits; outside by a median **1.75 pts** | ≥ 90% |
| entries vs the real median print of that second | **+0.12** median (mean +0.37), better in 51% | −0.5 … +0.25 |
| exits vs the real market | **−2.50** median, better in 9% | −0.5 … +0.25 |
| banked vs the real contract's move between his two seconds | **+8.96 vs +10.97: he banked 2.0 pts LESS** | gap under +1 |

**Reading.** His broker quotes its own price around the real contract (outside the exchange's prints by ~1.75 points
— a CFD with its own spread, not the exchange book), fills his entries at a neutral price and his exits about 2.5
points worse. **The +3.47 of test D was the 1-second mid lagging fast seconds** (prediction 3 right). **His record is
not a pricing artifact: the real NQ futures moved +10.97 points his way between his entry and exit seconds, and his
broker took 2 of them.** Prediction 1 wrong (his quotes are not exchange prints), prediction 2 right at entry and
wrong at exit (worse, not neutral). **His edge is a genuine read of the next minutes.**

## 43. Non-dollar news — nothing (2026-10-04)

§28 tested the ForexFactory calendar for USD events only. An FX trader follows every currency, and his sittings fall in
the European afternoon. `backtest/his_fxnews.py` (`logs/his_fxnews.txt`, predictions committed first) reruns §28's exact
test on the **non-USD** rows of the same calendar (294 high-impact releases, 310 speeches incl. 102 by central-bank
governors, 614 medium/high events), and again on EUR + GBP alone. **Nothing survives Holm in either** (lowest Holm 0.43).
The only lean is AWAY: **0** entries during a live non-USD speech against 3.2 expected (p 0.06), 0 within 30 minutes of a
non-USD medium/high event against 2.6. Prediction 1 (nothing survives) right; prediction 2 (European speeches lean
toward his entries) wrong — they lean away, not significantly.

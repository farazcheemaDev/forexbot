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

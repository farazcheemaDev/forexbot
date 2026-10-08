# 21 — The graveyard audit: every "this doesn't work", how well it was backed, and what a re-test found

*Written 2026-10-08, the second half of the goal "test every combination of what worked, then re-test what we
claimed doesn't work with very little backing behind the claim". The first half is doc 02's entry "The combination
sweep". This document walks every kill in the repo — doc 02, doc 11, docs 12/13 and this session's — rates its
original backing, and records what was re-tested and what changed.*

## How each kill was rated

- **STRONG** — a large sample on a point-in-time universe (dead coins in) or a structural argument (costs,
  arithmetic), both halves, and nothing since that broke its measurement. Not re-tested.
- **MODERATE** — adequate, but one dimension is narrow (few settings, one venue, a small sample). Not re-tested,
  with the reason given.
- **THIN** — one of: survivor coins only where a point-in-time re-test is possible; measured on the engine before the
  2026-09-23 fixes and never re-scored (CLAUDE.md rule 9's legitimate exception); a single setting, phase, rebalance
  day or day of data; or killed by inspection, not by a test. **Every THIN kill that the data on disk allows was
  re-tested.**
- **DATA-LIMITED** — the data to re-test does not exist historically; only a forward log could.

## What changed (the short version)

| verdict now | kills |
|---|---|
| **reversed** | stops on the market-neutral short leg cost return (`mn_stop.py`): a +50% short-leg book exit is free on average across the 7 rebalance days and removes a wipe-out |
| **wrong as stated** | "volume is anti-useful in crypto"; "every reversal idea fails" |
| **stand, now properly backed** | indicators exhausted · funding carry · pairs · protecting the pyramid · stop width · entry limits · bb(20,2)/bb(50,1.5) on the engine · risk by sleeve · long BTC / short alts · MN basket width · crash bids up in chop · ICT sweep / prior-day fade · 1h capitulation · meme graduations on 7 more days |

Nothing in the graveyard came back as a book to trade. Two came close and died on the check that has killed
findings here before: the BTC/alts dispersion trade on a point-in-time basket (+0.55%/month, then 1 of 7 weekly
anchors) and risk by sleeve (cleared the paired bar on both halves, then failed matched risk).

## The full list

### A. Reversals and mean reversion
| claim | original backing | rating | re-test / why not | now |
|---|---|---|---|---|
| mean reversion / fading extremes (Bollinger + RSI, z-score), PF 0.46–0.85 | early, mixed markets | STRONG today | re-measured since: `bear_chop.py` #4 (daily PIT top-40, every regime, vs random), `rsi_only.py`, `rsi_factors.py`, `rsi_confluence.py` (~2,000 configs) | stands — except when keyed to forced selling (capitulation with breadth) |
| prior-day high/low fade; ICT liquidity sweep, PF ~1 / 0.53–0.79 | one line each, pre-fix, no universe, no control | THIN | `sweep_reclaim.py`: PIT top-40 hourly, ~60,000 trades, random control with the same stop | **stands as a trade**: real information (+0.03 to +0.12% over random, t 2.8–6.4) but −0.04 to −0.13% a trade after fees |
| VWAP reversion, PF 0.46–0.85 | early | MODERATE | the reversion family is re-measured above; a separate run would repeat it | stands |
| StochRSI | "no robust edge" | MODERATE | stochastic confirmations are inside `rsi_confluence.py`'s 2,000 configs | stands |
| pairs NASDAQ vs gold/silver | correlation +0.19 | MODERATE | forex; crypto pairs re-tested (§E) | stands |
| classic indicators on EURUSD | early | STRONG today | doc 18: 33 tests with Holm | stands |
| **"every reversal idea fails"** | the pattern of the early table | — | contradicted by evidence already in the repo | **too broad**: the capitulation book, crash bids and the bear sleeve are reversal buys that work, all keyed to forced selling |

### B. Costs, capital, venues
| claim | rating | note |
|---|---|---|
| Nasdaq momentum scalping; crypto 1/5/15-minute; market making | STRONG | fee toll; `scalp_1m.py` 572 tests, `scalp_15m.py` 980 |
| Exness lot minimums | answered | partly reopened (silver fundable at $25; Cent account) |
| options vol selling | STRONG, time-dependent | premium 0.00 in 2026 (re-checked 2026-09-23); a number to watch, not a kill |
| cheaper fees as a step change | STRONG | +0.67 %/mo, structural |
| diversification by risk on $5 | STRONG | arithmetic |
| launchpools | DATA-LIMITED | no history served; forward log only |

### C. Indicators and filters
| claim | original backing | rating | re-test | now |
|---|---|---|---|---|
| **"indicators are exhausted, they all detect the same thing"** | longs on 9 coins big today (hindsight), hourly | THIN | `daily_families.py`: 9 families + an ER filter on DAILY bars, PIT top-40, 3 day boundaries | **stands, now backed**: bb(30,1.5) first of 22 daily entries; Keltner closest (holdout-only) |
| cross-sectional versions of the 19 | Sharpe 0.49 vs 1.09 | MODERATE | superseded: price momentum became the MN book | stands |
| meta-labelling (ML filter on signals) | one early attempt | MODERATE | covered since by `entry_features.py` (9 features, Holm), `entry_runner.py`, `btc_doge.py` | stands |
| VSA / volume absorption | 199 virgin coins | STRONG | — | stands for hourly breakouts |
| **"volume is anti-useful in crypto"** | VSA, a surge filter, 1m setups | THIN as a general claim | `capit_volume.py` | **wrong as stated**: required in the base capitulation book, redundant once a 10% drop is required |
| crypto momentum + Kaufman ER | killed by correlation tax | MODERATE | ER filter on the daily book (`daily_families.py`) | stands |
| new-listing momentum (long) | 81% untakeable; capped negative | STRONG by implication | `bear_shorts.py`: listings fall (median +11.3% for a 30-day short) | stands |
| Fear & Greed as a size dial | 0/10 orderings | STRONG | also as filters today (daily, capitulation): fail | stands |
| the 14 BTC timing signals (doc 12) | both halves | STRONG | — | stands |

### D. The trend engine (exits, sizing, allocation)
| claim | original backing | rating | re-test | now |
|---|---|---|---|---|
| protecting the pyramid: scale_out / avg_be / ratchet | pre-fix engine, never re-scored | THIN | `engine_rescore2.py`, corrected engine, paired, MAIN and TRIPLE | **stands**: all lose (scale_out −3.56 / −0.34 %/mo vs main) |
| stop 1.5x / 3x ATR | pre-fix | THIN | same | **stands** |
| entry limit 0.25x / 1x ATR under | pre-fix | THIN | same | **stands** (1x is tune-only) |
| bb(20,2.0) / bb(50,1.5) entries | pre-fix | THIN | same | **stands** (bb(50,1.5) tune-only) |
| risk x1.5 / x1.0 / x0.5 by sleeve | pre-fix | THIN | same, then `sleeve_risk_control.py` | **stands**: clears the paired bar, fails matched risk (holdout-only) |
| max 1 / 2 positions per coin; correlation clusters | pre-fix | MODERATE | re-run on the causal allocator (`slot_ideas.py`); clusters unstable | stands |
| exits / sleeves / trails / 8 slots / risk dial / bb(30,1.25) / lean short | — | STRONG | re-scored 2026-09-23 (`graveyard_rescore.py`) | stand (tight exit and time stop came out of this) |
| take profit early, trade more | monotone over 5 targets | STRONG | — | stands |
| slot priority; slots by side; 16 slots | — | STRONG | re-run on the causal allocator 2026-10-06; priority again today | stand |
| equity-curve trading; funding-trail; nine entry features | corrected engine | STRONG | — | stand |
| breadth does not scale (hourly engine on PIT top-30/60/100) | old engine, not re-run | MODERATE | every fix lowers a long book, so none can close a +6 points/month gap in its favour; the daily book (a different timeframe) is today's counterexample | stands for the hourly engine |
| risk > 0.30%, low capital as an advantage, bar-phase blending | — | STRONG | — | stand |

### E. Bear, chop and market-neutral
| claim | original backing | rating | re-test | now |
|---|---|---|---|---|
| short-term reversal MN (18 cells) | PIT | STRONG | — | stands |
| crypto pairs stat-arb | 4 settings | MODERATE | `pairs_revisit.py`: 6 more (60/90-day formation, no stop, z 1.5, top-60) | **stands**: all negative on both halves |
| daily trend shorts in bears | t −3.8 vs random | STRONG | — | stands |
| mean reversion gated by regime; shorting BTC/ETH below 1000h | PIT | STRONG | — | stand |
| **funding carry MN** | one week (MYX −107%), one rebalance day | THIN | `carry_revisit.py`: 7 days, +50% short exit, a day's lag | **stands**: no wipe-out with the exit, but holdout Sharpe +0.28 |
| **long BTC / short alts in bears** | 11 SURVIVOR alts as the short leg, no funding | THIN | `bear_alpha_pit.py`: PIT top-20/40, funding, 7 weekly anchors, as an overlay | **stands**: +0.55 %/month on the original weekday, 1 of 7 anchors positive on both halves |
| funding_xs / cash_carry | 18 cells; same-coin carry | STRONG | — | stand |
| **MN short-leg stop costs return** (`mn_stop.py`) | one rebalance day | THIN | `mn_combos.py`: 7 days, a book exit at +50% | **REVERSED**: same average Sharpe, worst week −29% instead of −99% |
| **MN basket width** (`mn_scale.py`) | one rebalance day | THIN | `mn_width7.py`: 10–25% on 7 days, with and without the exit | **stands**: 10% stays (wider = better tune, worse holdout) |
| bear shorts on all 864 perps; every family short | PIT, controls | STRONG | — | stand |

### F. Crash bids
| claim | rating | re-test | now |
|---|---|---|---|
| funding filter, selling bear squeezes, 2h hold, longer after a wave | MODERATE–STRONG | — | stand |
| **sized up in sideways markets** — "dead on inspection" | THIN (no test) | `wick_chop_size.py`: alone and in the machine, vs uniform size | **stands** |
| wick_better's ~25 variants | STRONG | — | stand |

### G. Event, data and copy strategies
| claim | original backing | rating | re-test / why not | now |
|---|---|---|---|---|
| listing announcements | 122 Upbit + 2,263 Binance; the pump is gone in under a minute | STRONG | — | stands |
| **memecoin graduations** | ONE day, 631 graduates | THIN across days | `meme_days.py`: random graduates from later days (collector), first 13 hours from GeckoTerminal | **stands on other days**: 98 graduates from 7 later days, buy +1 min / sell +1h -66.9% [-81%, -50%], 0 of 7 days positive (`logs/meme_days.txt`) |
| copying Hyperliquid's best | 27 months, 3,000 accounts | MODERATE / DATA-LIMITED | needs a forward record | stands |
| funding spikes on small perps | 2.07M settlements | STRONG | — | stands |
| taker flow / crowd positioning | 5.99M rows, 13 symbols, Holm, then as a book | MODERATE | the archive covers 13 symbols only | stands |
| delisting announcements (doc 11 §2) | pre-registered confirmation failed | MODERATE / DATA-LIMITED | few events | stands |
| funding-settlement timing (doc 11 §1) | real, sub-second | STRONG for this setup | infrastructure | stands |
| grid bots; CME gaps; first-perp short; kimchi premium; HLP vault | 30 configs; 180 trades + placebo; ... | MODERATE | — | stand |
| TradFi perps | daily since 2005 | STRONG | — | stands |
| token unlocks | "not dead, not tradable" | — | — | unchanged |

### H. Forex and the NASDAQ trader
| claim | rating | note |
|---|---|---|
| 33 forex tests; currency strength; NQ lead-lag | STRONG | Holm, large samples |
| decoding the trader's picks | DATA-LIMITED | his information is not in any recorded data; copying live is the route (his_strategy.md) |

### I. This session's kills (2026-10-06 to 10-08)
All on multi-coin or PIT samples, both halves, predictions registered: `odds_now.py`, `scalp_1m.py`, `btc_doge.py`,
`one_shot.py`, `day_long.py`, `scalp_15m.py`, `rsi_only.py`, `rsi_factors.py`, `doge_focus.py`, the 1h capitulation
buy (re-tested today with the two capitulation fixes, `capit_1h.py`: still worse than the 4h book), euphoria shorts,
and today's combination sweep (doc 02). STRONG; not re-tested.

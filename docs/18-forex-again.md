# Back to forex: the trader's material, 33 new tests, and the one thing that holds (2026-09-25)

*Asked for: "go back to the roots for which we started this project, forexbot... try different
strategies for forex... you have the strategy video folder and his statement, I'm sure you can
decipher that". Every number names its file.*

## Short version

- **His material is used up.**
  - The video is 94 seconds of his trade-history list scrolling. All 55 screenshots are the same
    list (checked frame by frame). **None of them shows his chart**, so nothing in the material
    records what he looks at when he enters.
  - `strategy_analysis/his_strategy.md` §13–22 had already decoded the record fully:
    - 91 trades, reconciled to the cent;
    - +11.5%/month, 94% of it from NASDAQ;
    - 7-point wins held a median 1.3 minutes;
    - his entry choice is worth +10 points a trade over random entries with the same exit, and it
      is **not visible in price data**.
- **Two ways left to crack him:** ask him what he looks at, or get a screen recording of his
  **chart** (not his history) while he trades.
- **33 new forex tests.** Nine documented calendar and session effects, and the retail
  Asian-range breakout in 24 variants. **All 33 fail after Exness costs.**
- **One forex result holds** (`fx_tsmom.py`): 12-month trend on 16 markets, equal risk, monthly.
  - **+5.5%/yr at 10% volatility** from 2004 to 2026, on both halves (Sharpe 0.52 / 0.62);
    **only on a swap-free account**. With Exness's overnight swap it loses 1.6%/yr.
  - It comes from commodities and stock indices, not currencies.
  - At 20% volatility: +10.9%/yr with a 42% fall.
  - A $300 account can hold it only on a Cent account, and gold and silver are still too big there.

## 00. Update, later: tick data — the pause found, the broker's prices, and what is left

`strategy_analysis/his_strategy.md` §25. The Exness MT5 terminal has USTECm **tick** data back to
January.

**His broker's prices.** The statement's clock is exact to ±10 s. But in **January–March his fills
often sat where the real market never traded**: in ~10 of 20 trades he banked more than the market
ever offered during the trade. **April–September (26 trades, the big lots) is 100% consistent with
the real market.**

**The pause he joins** (the 26 real trades):
- a ~5-point NASDAQ-led move over 5 minutes;
- then all US indices dip ~2 points in 30 s;
- he enters during that dip, ~18 s into the minute;
- next: +6 points in 60 s median, and **+7 before −7 in ~85–88% (random: 50%)**.

**What does not pick his pauses out of the others:**
- the profile as a rule, on every second with real bid/ask: −3.0 a trade, **the same as random**;
- adding NASDAQ's lead over the S&P;
- news before or after entry (the 5 minutes after his entries are *calmer* than usual);
- the day's trend, VWAP, the opening range.

**His 96% win rate is partly the style.** Random entries taking 7 points with no stop win 83%, and
lose on average. The real skill is the first-7-points call.

**The rest is off the chart** (most likely the order book). Asking him, or a screen recording that
includes his order-book window, is the only way to crack it.

## 0. Update, same day: his charts read, news tested, the chart pattern encoded

Prompted by the user ("cross-check dates and prices... he also relies on news"), in
his_strategy.md §24:
- **The charts:** all 46 NASDAQ trades are drawn on real bars (`logs/his_charts_*.png`). **He reads
  the 1-minute trend and joins it after a small pause.** On 2026-09-14 that was four shorts in 16
  minutes, each on a bounce inside a downtrend. Some entries follow 08:30 ET data releases.
- **News, tested** against the same clock time on 251 other days: only slightly unusual, none of it
  significant; **0 trades on Fed decision days**.
- **The pattern, encoded as a rule:** 18 variants, **all lose** (−3.5 to −5.4 points a trade net;
  53–66% wins against the ~74% needed).

His skill is choosing WHICH pauses to join, which lives in the tape, not in the bars.

## 1. The trader's material — checked for anything unread

| source | what it contains | used? |
|---|---|---|
| `Strategy video/…1.20.43 AM.mp4` (94 s, 576×1248) | his History → Trades list scrolling, NASDAQ/GOLD entries | yes, §1–5, §11 |
| `Strategy video/WhatsApp Unknown …/` (55 images) | the same history list, every image (equal darkness 0.08 across all 55) | yes, §12–13 |
| broker statement (gitignored) | 91 trades, GMT+5, balance and withdrawals | yes, §16–22 |

**No chart, indicator, order book or tick screen appears anywhere.** The decisive question was
what he sees at 11:00 ET before he joins a NASDAQ move, and it cannot be answered from these files.
§22 already showed:
- his entries are worth +10.4 points a trade over random entries with the identical exit;
- ten chart features cannot tell his entries apart from any other moment (§20).

## 2. Nine documented effects — `backtest/fx_anomalies.py` (log `logs/fx_anomalies.txt`)

Each effect is published, with a stated cause. Costs are Exness's (forex.py). A result must be
positive on both halves, with Holm correction across the nine.

| effect | net per trade | tune / holdout | verdict |
|---|---|---|---|
| NASDAQ-100 overnight (close → open) | −0.3bp | −0.9 / +0.5 | fail: +3.4bp gross, eaten by 2.8bp spread + swap |
| S&P 500 overnight | −1.8bp | −3.2 / +0.2 | fail |
| NASDAQ-100 turn of month (days −1..+3) | +25.6bp | +26.0 / +24.9 | fail: any 4-day hold makes +20.9bp, so the effect is +5bp (t 1.43) |
| S&P 500 turn of month | +13.3bp | +12.5 / +14.6 | fail: any 4-day hold +12.9bp |
| gold 22–13 UTC (outside New York) | −0.4bp | −2.1 / +2.3 | fail: the right direction, +2.1bp gross |
| silver 22–13 UTC | −8.6bp | | fail on its 9.5bp spread |
| FX home-hours (Breedon-Ranaldo) | −2.1bp | −1.7 / −2.7 | fail: the wrong direction, and costs are bigger than the effect |
| month-end USD rebalancing (Melvin-Prins) | +4.1bp | +6.7 / +0.3 | fail: right in 128 of 234 months |
| NASDAQ-100 intraday (control) | +1.3bp | | fail |

Registered: "T3 and/or T5 survive". **Wrong: none do.** Published effects are a few basis points,
smaller than a retail CFD spread plus a night's swap.

## 3. The Asian-range breakout — `backtest/fx_breakout.py` (log `logs/fx_breakout.txt`)

**The rule:** trade the first break of the 00–07 UTC range at the London open. It was tested on
EURUSD, GBPUSD, USDJPY and gold, on 15-minute bars from 2022 to 2026, with pessimistic fills,
2 stop rules × 3 exit rules.

**0 of 24 cells pass.**
- The best is USDJPY with a stop at the other side and exit at 20:00 UTC: +0.062R a trade, t 1.50.
- Gold is holdout-only again (tune −0.02 to −0.14R, holdout +0.03 to +0.09R), which is its 2024–26
  bull market.

Registered: "zero of 24". Right.

## 4. Diversified trend — `backtest/fx_tsmom.py`, `backtest/fx_tsmom_check.py` (logs `fx_tsmom*.txt`)

**The rule** (Moskowitz-Ooi-Pedersen): each month, hold each market in the direction of its
12-month return, sized to equal risk. The whole book is scaled to ~10% volatility, with the scale
set on the tune half only.
- **Markets:** 7 FX pairs, gold, silver, WTI, S&P 500, Nasdaq-100, Dow, DAX, Nikkei, US 10-year.
- **Data:** Yahoo daily, 2004–2026.

| 12-month lookback | %/yr | Sharpe | max fall | tune (to 2017-09) | holdout |
|---|---|---|---|---|---|
| before costs | +5.6% | 0.57 | 23% | +5.4%, 0.54 | +5.9%, 0.63 |
| **after spread, swap-free** | **+5.5%** | **0.56** | **23%** | **+5.2%, 0.52** | **+5.8%, 0.62** |
| after spread + Exness swap | −1.6% | −0.16 | 54% | −1.5% | −1.7% |

**Trying to break it:**
- **By asset class.**
  - Commodities: +5.8%/yr, Sharpe 0.60 (0.58 / 0.63).
  - Indices: +5.5%/yr, 0.55 (0.60 / 0.48).
  - The bond: +1.8%/yr, 0.18.
  - **FX: +0.3%/yr, 0.03, nothing.**
- **Drop one market:** the range is +5.0% (without gold) to +6.1%/yr.
- **Without its best year (2013, +26%):** +4.7%/yr.
- **By year, swap-free:** positive in 15 of 23 years; worst −10% (2016), best +26% (2013).
- **Size, swap-free:**

  | volatility | %/yr | biggest fall |
  |---|---|---|
  | 15% | +8.2% | 33% |
  | 20% | +10.9% | 42% |
  | 30% | +16.4% | 58% |

- **Lookback:** 6 months fails on the holdout (−1.6% gross); 3 months is weaker (+3.3%). Only the
  registered 12 months holds on both halves.
- **$300.** At 10% volatility each market needs $12–$82 of position. Exness Standard's minimum is
  $567–$4,319 (FX 0.01 lot is 1,000 units; gold 0.01 lot is 1 oz). On a **Cent** account (100×
  smaller) FX and indices fit, but gold ($43 minimum against the $27 needed) and silver ($32 against
  $14) do not.

Registered predictions:
- "~0.5 Sharpe before 2016, ~0.1 after": **wrong**, the holdout is the better half;
- "negative with swap": right;
- "swap-free under 5%/yr": wrong by 0.5;
- "not worth running": this now depends on the account type.

## 5. What this means

**Forex majors are not where a small account makes money.** Every FX-only result in this project
is zero or negative after costs:
- trend on H1/H4 (forex.py);
- the nine effects;
- the breakout;
- FX inside the diversified trend book.

**What forex offers is slower and smaller: trend across commodities and indices.** It earns +5–6%
a year at 10% volatility, and 22 years says it is real. It needs:
1. **A swap-free Exness account.** With swaps it loses. *Whether the user's account is swap-free is
   the deciding fact, and only the account holder can check it* (Exness personal area → account
   settings).
2. **A Cent account** to size 16 positions on a few hundred dollars. Even then gold and silver need
   ~$500+.
3. **Leverage to make it matter.** At 20% volatility: +10.9%/yr and a 42% fall. That is far below
   the crypto machine's backtest, and with a much longer, cleaner history.

Everything else tried in forex is in the graveyard (doc 02, 2026-09-25 forex entry).

# VSA — asked and answered

**Verdict: dead. Settled 2026-09-13.** The absorption filter does not select
better trades; it selects *worse* ones, and the effect is significant.

## What it was

VSA = Volume Spread Analysis. Compare how far a bar moved against how much volume
traded in it. If huge volume trades and price barely moves, the theory says a
large player is soaking up the flow — "absorption" — and marks a turning point.

Mechanically: regress normalised range on normalised volume over a rolling
168-bar window; the indicator is the residual (`dev`). Very negative `dev` = lots
of volume, little movement = absorption. The filter was: only take a breakout
signal when `dev < −0.5`.

## Why it was unresolved

It gave contradictory results. It passed a shuffled-market test at **p = 0.0099**
but failed the cross-asset check (worked on only 16 of 28 assets). A
liquidity hypothesis was invented afterwards to explain that — the filter
supposedly works better on heavily traded coins — but that story was formed *after*
seeing the failure and had no mechanism.

So `vsa_forward.py` was set up: a pre-registered live test on 20 coins, 10 heavily
traded and 10 thin, taking every signal and *recording* whether absorption was
present instead of filtering on it. Timeline: **~4 months** to fill its cells.

## Why the 4-month wait was unnecessary

Two things had changed since that test was written.

**1. The old measurement used the broken exit rule.** `vsa.py` and
`vsa_forward.py` both close winners at a fixed target, capping every winner at
+1.5R — the exact bug that produced false negatives across 18 strategy families
([doc 03](03-mistakes.md)). So "VSA failed 16/28" was not a spent holdout, it was
a *contaminated measurement*. Re-measuring with a correct exit is new information.

**2. There are 199 delisted coins of genuinely virgin data.** They were
downloaded *after* every VSA hypothesis was formed, to fix survivorship bias.
Nothing about VSA — not the `dev` cut, not the liquidity split, not the breakout
parameters — was chosen with any knowledge of those series. That is the same
epistemic status as forward data, and it was already on disk.

Forward data arrives at ~3 trades per cell per day. The dead set contains
**238,000 trades across 199 independent assets**, right now.

The prediction was registered in `backtest/vsa_fast.py` before the first run,
including the stated expectation that it would fail.

## The result

199 delisted coins. Every breakout signal taken once; `dev` recorded at entry,
never used to gate. Filter cell vs everything else.

| Exit rule | filter meanR | filter win% | rest meanR | rest win% | coins improved | p |
|---|---|---|---|---|---|---|
| capped 3R *(the old rule)* | −0.066 | 38.5% | −0.035 | 40.0% | **68/171** | 0.0091 |
| trail 3× ATR | −0.025 | 32.5% | +0.055 | 33.6% | **73/174** | 0.04 |
| trail 5× ATR | −0.080 | 26.5% | +0.079 | 28.0% | **57/160** | 0.00034 |
| trail 10× ATR | −0.126 | 18.2% | +0.238 | 19.6% | **45/139** | 0.000039 |
| trail 20× ATR | −0.234 | 11.9% | *(outlier-driven)* | 13.1% | **22/96** | 0.000000094 |

Read the **coins improved** column. Under every exit rule the filter helped fewer
than half the coins, and at the trails we actually trade it is significant at
p < 0.001. The absorption filter is not neutral — it is **anti-predictive**.

Three more nails:

- **The liquidity hypothesis is backwards.** On virgin data the high-liquidity
  half is *worse* (24/77 coins improved, p = 0.0013) than the low-liquidity half
  (33/83, p = 0.078). The story that justified the entire forward test's design
  fails in the opposite direction.
- **The wider the trail, the worse it looks.** If the profit cap had been hiding
  an edge, removing it would reveal one. It reveals the opposite: the filter's
  deficit grows from −0.035R to −0.362R as winners are allowed to run.
- **On the 20 forward-test coins it is a literal coin flip** — 8 to 11 of 20 in
  every row, sign-test p between 0.48 and 1.0. The single mildly positive cell in
  the whole output (+0.041R, 11/20) is the capped exit on the non-virgin coins,
  which is exactly the original finding. That is what the original finding *was*:
  a pooled statistic on correlated coins, measured with a broken exit.

## Why the original p = 0.0099 was misleading

It pooled trades. Pooling treats 40,000 trades as 40,000 independent draws, but
crypto coins move together — one good market stretch inflates a pooled t
enormously. The honest unit of independence is the **coin**.

`vsa_fast.py` reports both. On the live coins the pooled figure is +2.02 while
the across-coin figure is +1.32 and the coin count is 11/20. When those two
disagree, the pooled one is measuring market direction.

## A note on mean R in that table

At a 20× ATR trail the "rest" cell shows mean R of +13.2, which is not a real
expectation. A delisted microcap that rose 1000× before dying posts an R in the
thousands, because R's denominator is the ATR from when the coin was worth a
fraction of a cent. One such trade moves a mean over 37,000 trades by whole R.

The returns are real — the trade did that — but a *mean* built from them measures
which cell caught the lottery ticket. That is why the sign test across coins is
the headline: a coin counts once whether its best trade made 1R or 5,000R.

## The forward test is stopped

`vsa_forward.py` was stopped on 2026-09-13 (PID 1728) at **5 trades** of the
~1,200 it needed — all five losses. Keeping it alive would have bought an
independent confirmation of a result that is already significant at p < 0.001 on
199 independent assets, for four more months of waiting.

Its data is kept: `logs/vsaf_trades.csv` and `logs/vsaf_state.json`. Its systemd
unit was deleted — `deploy/setup.sh` installs `deploy/*.service` by glob, so
leaving the file there would have quietly restarted the test on the Oracle box
with `Restart=always`.

## Rules this produced

1. **A "spent holdout" is not spent if the measurement was broken.** Re-measuring
   a contaminated result is new information, not post-hoc slicing.
2. **Delisted-asset data is virgin data.** Any dataset downloaded after a
   hypothesis was formed has the same epistemic status as forward data, and it is
   available immediately. Check for one before committing to a months-long wait.
3. **The unit of independence in crypto is the coin, not the trade.** Report a
   pooled statistic and an across-coin statistic side by side. If they disagree,
   believe the across-coin one.
4. **On heavy-tailed data, count assets rather than averaging returns.** A sign
   test across assets is immune to the single-trade outliers that make mean R
   unreadable.
5. **Shift the indicator one bar as a robustness check.** Here the pooled means
   flipped sign with a one-bar shift while the coin counts held — that gap tells
   you which statistic to trust.

## Files

| File | Role |
|---|---|
| `backtest/vsa.py` | the indicator, and the original (capped) test |
| `backtest/vsa_mcpt.py` | the shuffled-market test that gave p = 0.0099 |
| `backtest/vsa_crossasset.py` | the 16/28 cross-asset failure |
| `backtest/vsa_fast.py` | **the resolution** — virgin data, uncapped exits, sign test |
| `vsa_forward.py` | the pre-registered live test — stopped, kept for the record |
| `logs/vsa_fast.txt` | full output of the run above |

# The $5–10 Bitget account

*A deliberate lottery ticket. Measured 2026-09-14 in `backtest/microacct.py`.*

## The odds

6,000 bootstrapped paths per cell, hindsight-deflated edge, Bitget's real $5 order
minimum enforced.

| From | Target | Chance | **Ruin** | Time |
|---|---|---|---|---|
| **$10** | **$50 (5×)** | **29.7%** | **70.3%** | ~91 trades, 3–4 weeks |
| $10 | $100 (10×) | 22.7% | 77.3% | ~84 trades |
| $5 | $25 (5×) | 24.4% | 75.5% | ~49 trades |
| $5 | $50 (10×) | 17.8% | 82.2% | ~73 trades |

**The most likely single outcome is zero.** Roughly a 1-in-3 shot at 5× from $10.

**And 70.3% is optimistic.** The simulation runs trades one at a time. A real bot holds
several at once, they are correlated, and correlated simultaneous losses kill accounts
faster than a sequential draw. Real ruin is above 70%; the gap is unmeasured.

## The universe is not the problem

Bitget **real** lists 783 USDT perps and **742 accept a $5 order.** The 3-contract limit
is a **demo** restriction only.

Excluded by their own contract step: LINK ($11.35), BNB ($7.16), BTC ($7.68), SOL
($9.98), ETH ($24.83). A $10 account cannot place one of those.

Book used: XRP, ADA, DOGE, AVAX, DOT, SUI, LTC, SHIB, ARB, NEAR.

## Two predictions I got wrong

### I predicted a tighter stop would win. It lost.

With the $5 floor binding, dollar risk per trade is `$5 × stop width` — so halving the
stop halves forced risk. That looked like the obvious lever. But the edge shrinks faster
than the saving:

| Stop | Honest mean R | Forced risk on $10 |
|---|---|---|
| 0.5× ATR | **+0.035** | 0.32% |
| 1.0× ATR | +0.072 | 0.63% |
| **1.5× ATR** | **+0.086** | 0.95% |
| 2.0× ATR | +0.076 | 1.26% |

The noise cost beats the arithmetic saving. 2× and 3× tie within noise.

### I predicted adding risk would lower the odds. It raised them.

| Risk asked | P(reach $50) at 2× stop |
|---|---|
| 0.30% (floor-bound → 1.26%) | 25.3% |
| 2.00% | 28.4% |
| 4.00% | 28.2% |

The textbook result — timid play maximises your chance of reaching a goal when the edge
is positive — assumes you can bet arbitrarily small. **The $5 floor already forces ~1.26%
on $10, so timidity isn't available**, and inside a finite horizon more risk arrives
sooner.

## The configuration

`micro_bot.py`. Every choice traces to the sweep above:

| | | Why |
|---|---|---|
| Risk | **4% per trade** | best measured cell |
| Stop | 2× ATR | ties with 3×; consistent with everything else |
| Units | **1, no pyramid** | 5 units is $25 of notional on a $10 account |
| Slots | **3** | concurrency is unmeasured; keep the correlated exposure small |
| Regime gate | **OFF** | it cuts risk, and cutting risk lowers P(target) here |
| Target | stop opening at 5× | exactly what the simulation measures |

The regime gate being off is deliberate and counterintuitive: it is the single best
improvement for the $221 book, and here it would make the account **safer and less
likely to work** — the opposite of the stated goal.

The bot **stops opening positions at 5×**. A bot that compounds past the target has
worse odds of ever being up, and the 29.7% figure would no longer apply.

## Running it

```bash
python micro_bot.py --mode demo --dry-run
```

`--mode live` **refuses to start.** `ALLOW_REAL = False` is a hard gate in the file and
must be edited by a human. The refusal message prints the odds.

Note demo mode tests the **order plumbing only** — Bitget demo has 3 contracts, and the
strategy needs the 10-coin book. There is no way to forward-test this configuration on
Bitget without real money.

## How this differs from the $221 book

| | $221 blend | $10 micro |
|---|---|---|
| Goal | compound steadily | reach a multiple before dying |
| Risk | 0.30%/unit | **4%/trade** |
| Drawdown | 57% | ruin is the expected case |
| Regime gate | on | off |
| Timeframes | 1h + 4h + 12h | 1h only |
| Honest expectation | ~+8%/month | **70% chance of zero** |

They are not the same strategy with different sizing. One is an investment; the other is
a bet with a positive expected value and a majority chance of total loss.

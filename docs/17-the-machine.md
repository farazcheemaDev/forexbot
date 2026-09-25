# The machine, v2: four books, the evidence behind each, and every risk (2026-09-25)

*Asked for: "the perfect money making machine... every risk taken into account... crazy gains... solid
evidence... refine it if there is still some edge left or develop more". Every number names its file.
**This is a backtest plus a demo order-path test. It is not a promise of returns.** Status: the three
original books are on the Bitget demo (2-week check from 2026-09-24); the fourth, the crash desk, is
built into the same bot behind `--wick` and has its order path tested on the demo.*

## Short version

- **What it is.** One Bitget account running four books that earn at different times:

  | book | what it does | when it earns |
  |---|---|---|
  | TREND | the triple (tight exit, time stop, 7 units) at 100%, 21-day anchor | rising markets |
  | MARKET-NEUTRAL | long the 30-day winners, short the losers, 1× | sideways and falling |
  | BEAR SLEEVE | breadth long/short, only in bear markets, 1× | falling |
  | **CRASH BIDS** (new) | buys 10% under the price, sold at the hour's end; 10 fills an hour at most; none on bear days | crash hours in rising and sideways markets |

- **On $300, a typical 12 months** (`backtest/machine.py`, `logs/machine.txt`; trend gains shrunk for
  hindsight, losses whole):
  - **$1,812** over 6 years, **$1,625** over the last 2, against $1,642 / $1,527 without the crash
    bids;
  - the worst month is the same (−29% / −25%);
  - the biggest fall is 57% / 45%;
  - 57% / 64% of months up.
- **What changed today:**
  - the crash bids work on **Bitget's own prices**, 2022–2026: +1.01% a fill, identical to
    Binance's on the same hours;
  - four more ideas were tested and are dead;
  - the crash desk now exists in the live bot and has placed, filled, capped and sold on the demo.
- **More size does not buy much.** ×1.2 raises the typical year 8% and deepens the worst month to
  −34%, the fall to 65%, and the worst hour to 35% of the account left. **×1.0 is the setting;
  ×0.85 is the cautious one** (same typical year as the old final version, worst month −25%).

---

## 1. The numbers — `backtest/machine.py` (log `logs/machine.txt`)

$300, 10 orderings, 2020-01 to 2026-09. Trend gains are shrunk to a third of their raw growth
(hindsight), and trend losses are kept whole. The other books are raw.

**By market type** (months labelled by the BTC regime most of their days carried; average / typical
month, share of months up):

| | months | final, no crash bids | **machine v2** | what the crash bids added |
|---|---|---|---|---|
| RISING | 31 | +67.4% / +19.1%, 69% up | **+71.0% / +22.5%, 71%** | +2.08% a month |
| SIDEWAYS | 26 | −1.4% / −6.0%, 32% | **+0.2% / −4.5%, 32%** | +1.41% a month |
| FALLING | 23 | +7.6% / +4.7%, 64% | +7.6% / +4.7%, 64% | ~0 (no bids on bear days) |

The weak spot is still sideways markets: the typical sideways month loses 4.5%, but the average
sideways month is now slightly positive.

**The size dial** (every book × g; $300, 12 months):

| | typical | bad (1 in 4) | worst | years < $300 | worst month | biggest fall | worst hour, account left |
|---|---|---|---|---|---|---|---|
| final, no crash bids | $1,642 | $666 | $204 | 9% | −29.0% | 59% | 62% |
| machine ×0.7 | $1,435 | $671 | $250 | 6% | −21.3% | 44% | 62% |
| **machine ×0.85** | $1,646 | $691 | $236 | 8% | **−25.4%** | **51%** | 54% |
| **machine ×1.0** | **$1,812** | $725 | $222 | 9% | −29.3% | 57% | 46% |
| machine ×1.2 | $1,953 | $729 | $202 | 9% | −34.2% | 65% | 35% |
| machine ×1.4 | $2,082 | $714 | $182 | 10% | −38.2% | 71% | 25% |

Last 2 years: ×1.0 gives $1,625 typical, −25.0% worst month and a 45% fall, with no 12 months ending
under $300. Above ×1.0 the trend book's 9× leverage guard binds, so size buys little return and a
lot of risk.

**Monthly income** (×1.0, withdrawals paused while the balance is under $300):

| per month | typically taken out in a year | balance after 12 months: typical | bad (1 in 4) |
|---|---|---|---|
| $0 | $0 | $1,865 | $725 |
| $20 | $200 | $1,447 | $546 |
| $30 | $270 | $1,303 | $498 |
| $50 | $400 | $1,040 | $387 |

## 2. The evidence behind each book

| book | found | held on both halves | out of sample / forward | venue |
|---|---|---|---|---|
| TREND triple | docs 11, 12 | yes, all four bar phases, 79/80 orderings (tight exit) | 7 paper books on the VM since 2026-09-23/24 | the demo fills within ~5bp of Binance (`combo_bot.py --report`) |
| MARKET-NEUTRAL | doc 10 | yes | `mn_paper.py`, `combo_paper.py` forward | Binance funding; Bitget not separately tested |
| BEAR SLEEVE | doc 13 | yes; permutation p = 0.001 | **replicated on the 2018–19 bear with frozen parameters** (+21.7%/yr) | — |
| CRASH BIDS | docs 15, 16 | yes; passes "just bet smaller" on both halves | **Bitget's own 1-minute bars 2022–26: +1.01% a fill, same as Binance** (`wick_bitget.py`); `wick_paper.py` pre-registered for the VM | Bitget ≈ Binance |

Combined, `combo_paper.py` has run the first three forward on the VM since 2026-09-24 (verdict
~2027-03-24).

## 3. Tested this session and dead (doc 02, 2026-09-25 entry)

| idea | mechanism | result |
|---|---|---|
| crash bids only on crowded-long coins | liquidation wicks bounce more | tune yes, **holdout reverses** (−0.14% a fill) |
| selling squeeze spikes in bear markets | short-covering spikes fade | **−0.43% a fill**, worst −339% (LUNA) |
| holding crash fills 2 hours | post-cascade drift | +0.21 a fill, **not significant** (se 0.16) |
| hold longer only after a capped wave | same | worse than either |

The trend book's own last lead (tighten alts' trails on BTC's 4h break) was already adopted as the
tight exit. **No further trend-book refinement is available on this data without mining a used
holdout** (CLAUDE.md §2).

## 4. Every risk, measured where it can be

| risk | size | what is done about it | file |
|---|---|---|---|
| **The backtest is not the future** | The trend coins were picked with hindsight; the holdout is mined | Gains shrunk 3× for hindsight; losses whole; forward paper books | CLAUDE.md §2, §6 |
| **Liquidation inside one hour** | Worst hour in 6 years (2025-10-10 21:00): 46% of the account left at ×1.0; 10% if the crash bids were uncapped | 10-fill cap per hour, enforced by a 3-second watcher; 9× trend guard; 30% disaster stops | `joint_worst_hour.py` |
| **A bad month** | −29% (6 yrs), −25% (2 yrs); one month in ten below about −16% | Only size shrinks it; 16 "brakes" lose to betting smaller | `worst_month.py` |
| **A long fall** | 57% biggest fall; longest from the low back to a new high 232 days | Every one of 172 falls of 20%+ recovered in the backtest | `worst_month.py` C1 |
| **A worse-than-ever month** | After a made-up −50%: back to $300 within 24 months in 100% of starts at backtest growth, 62% at +50%/yr, 52% at +25%/yr | Keep trading through it; **pause withdrawals under water** ($20/month through it leaves a typical $16) | `worst_month.py` C2, `--stress` |
| **Edge decay** | Crash bids lost 0.4% a fill in Jan–Jun 2026, then made +2.7% since July | Forward paper book on both venues; H1 false at 12 months drops it | `wick_paper.py` |
| **Sideways markets** | The typical sideways month is −4.5% | None found in 21 signals (doc 13); crash bids lift the average to +0.2% | `machine.py` |
| **Small account** | Under ~$150 the $5 minimum rejects trend units; at $300, 8 of 40 crash-bid coins are under Bitget's minimum size | $300 recommended; the crash desk logs which coins it skips | `min_capital.py`, `wick_live.py` |
| **Execution** | Demo fills +1 to +17bp against the Binance reference | Price-sanity refusal at 3%; post-only crash bids | `combo_bot.py --report` |
| **The machine goes down** | Resting crash bids could fill with no cap and no exit while the bot is down | VM service restarts in 30 s; stale bids cancelled on restart; disaster stops on positions. **Not covered: a VM down for hours** | `wick_live.py` docstring |
| **The exchange** | Bitget halts, freezes or fails | Not modelled. Keep only the trading balance there | — |
| **One account, one bot** | A second bot doubles every order; manual trades get netted away | The bot refuses to start beside another; the account must be dedicated | `combo_bot.py` |
| **Real money** | — | `ALLOW_REAL = False`. Only a human changes it | `combo_bot.py` |

## 5. The crash desk in the live bot — `wick_live.py`, `combo_bot.py --wick`

- **What it does:** it only places post-only limit BUYS. Its fills are added to the bot's targets,
  so the netting keeps them. At the hour's close it releases them, and the bot sells them within
  seconds, through the same netting that runs the other books.
- **The cap is enforced by a watcher every 3 seconds.** The 2-minute poll would be far too slow:
  on 2025-10-10, 38 of 40 bids filled within minutes.
- **Offline:** `tests/test_wick_live.py`, 10 tests on a fake exchange with resting orders. Seven
  deliberate breaks are each caught: fills not held, no cap, not post-only, the wrong distance,
  hold kept past the close, bids on bear days, leftovers not cancelled. The bot's own 14 tests
  still pass.
- **Against Bitget's real market list, read-only:**
  - 38 of this month's 40 coins map. 1000PEPE and 1000SHIB don't (Bitget prices single coins),
    and are skipped.
  - At $7.50 a bid, 8 coins are under Bitget's minimum size (BTC, ETH, SOL, LINK, UNI, NEAR,
    AAVE, LIT), so about 30 get bids.
- **On the Bitget demo** (2026-09-24 22:52 UTC onward; test settings: 0.1% under, cap 2, $30 a
  bid):
  - bids placed on SBTC/SETH/SXRP;
  - an ETH fill got a disaster stop;
  - at 23:00:01 the hour closed, and at 23:00:03 the netting sold the ETH, +1.1bp from the
    reference;
  - new bids were placed for the next hour;
  - the second cycle sold an XRP fill at 00:00:06, +4.6bp from the reference.

  **Not yet seen on the exchange:** the cancel-at-cap, which needs 2 fills in one hour. It uses the
  same cancel call that cleared the leftover bids at both hour closes, and its trigger is tested
  offline.

  At 00:01 UTC the demo went back to the **real settings** (`--mode demo --wick`: 10%, cap 10,
  $5.5 a bid on the virtual $221). At that size only SXRP clears the demo's minimum, so it will
  rarely fill.

## 6. What to do, in order

1. **Now:** paste `deploy/install_wick.sh` on the VM, so the crash bids' forward record starts on
   both venues (doc 16 §7).
2. **~2026-10-08:** run `python combo_bot.py --mode demo --report`. PASS = no order failures, no
   stop failures, every fill priced, slippage within a few bp. The crash desk's lines appear in the
   same log.
3. **Going live is the user's decision:**
   - set `ALLOW_REAL = True` by hand;
   - fund a dedicated account with ~$300;
   - on the VM, run `combo_bot.py --mode live --wick`;
   - never trade that account by hand.
4. **Withdrawals:** take money out only while the balance is above where it started.
5. **Review at 6 months** against `combo_paper.py` and `wick_paper.py`, which are pre-registered.
   If the crash bids are still below zero on Bitget at 12 months, drop them.

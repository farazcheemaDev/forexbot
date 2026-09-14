# Pick up here

*Written 2026-09-14, end of a long day. Read this first when you come back.*

## Nothing is broken. Nothing is urgent.

The thing that matters is already running.

*State below verified 2026-09-14 with `python health.py` and on the VM directly.*

**The VM runs the 1000h gate and 12 slots as of 2026-09-14.** Verified on the box:
`REGIME_MA = 1000`, `klines_deep` returns 2000 bars against the 1002 needed, and
`btc_bear()` returns a real decision rather than its cached default. That last check is
the one that matters — with the old 300-bar fetch a 1000h average silently disables the
gate while every log line still reports it armed.

**It was patched in place, not pulled.** `git pull` on the VM fails with
`could not read Username for 'https://github.com'` — no cached credentials and no
interactive prompt through Azure Run command. Fix that before the next change: either a
fresh read-only PAT in the remote URL, or make the repo public (checked 2026-09-14:
312 tracked files, no `.env`, no `.pem`, no hardcoded keys). Also note Azure Run command
JSON-decodes the script, so **any `
` inside a pasted heredoc becomes a real newline** and
breaks Python — write patch scripts with no backslashes at all.

| What | Where | Status |
|---|---|---|
| **$221 blend — the validated strategy** | **Azure VM, `blend-paper`** | **running 24/7 on the 2026-09-14 config** ✅ |
| Status page | Azure VM, `status-server` | running ✅ |
| Polymarket forward collector | your PC, Startup launcher | running, **1,814 markets, 0 resolved** ✅ |
| Bitget demo order-path test | your PC | **DEAD since the ~05:00 reboot, 3 positions open** ⚠️ |
| $10 micro bot | built, `ALLOW_REAL = False` | yours to flip, or not |

**Your PC only restores one bot after a reboot.** The Polymarket collector has a Startup
launcher; nothing else does, which is why the demo bot sat down for ten hours unnoticed.
Restart it with `python longtrend_bot.py --mode demo`, or leave it — the thing that
matters is on the VM.

### First live read on the blend (24h, 2026-09-14)

`equity 219.76 (−0.56%)`, 11 entries, 7 closed, **0% win, −7.48R**. All of that is on
spec, and one line proves the machinery:

> 7.48R × 0.30%/unit × **0.25** = 0.561% → exactly the −0.56% reported.

**The BTC regime gate is live and quarter-sizing every trade**, so a −7.48R run cost
0.56% instead of 2.24%. Also confirmed: all 7 closed were *shorts* and all 4 open are
*longs* (5×ATR trail vs 20×ATR — shorts churn, longs sit), and losses clustered at
−1.05R to −1.09R, meaning live fills are paying the **0.07R/trade the pessimistic
backtest convention assumed**. 0% of 7 is a 1-in-5 event at the designed 20% win rate.

**Shorts are supposed to lose** — −0.036R/trade under honest fill. They are a drawdown
hedge (78.6% → 68.9%), not a profit source. See [doc 01](01-strategy.md).

## Check on it whenever

**On your PC — is anything wedged or dead:**

```bash
python health.py
```

Three signals per bot (process / heartbeat / progress), reported separately so a
silent-but-healthy bot is never mistaken for a dead one. Full explanation of the
verdicts in [doc 04](04-operations.md).

**On the VM — is the strategy actually making money:**

```bash
cd /opt/forexbot && ./.venv/bin/python blend_paper.py --status
```

Per-sleeve and per-side breakdown, which is how you tell "the strategy is losing"
from "half of it isn't running." Run it through Azure portal → your VM → **Run command**
→ `RunShellScript` if you don't want to set up SSH.

**Don't read anything into the first ~30 closed trades.** The book filled 8/8 on its
first cycle, which is a cold-start artifact — a bot that had been running would have
entered those over time. And you lose 4 trades in 5 by design.

## Three optional jobs, in the order I'd do them

### 1. Revoke the GitHub token (2 min)

GitHub → Settings → Developer settings → Personal access tokens → Fine-grained →
delete `forexbot-vm`. It's read-only and expires on its own, but it was pasted into a
chat transcript. The code is already on the VM; you don't need it until the next pull.

### 2. Move the Bitget demo bot to the VM (~15 min)

Full steps in [doc 06](06-deploy-221.md). The order matters:

1. **Stop the local bot first** — one account, one bot, or every order doubles
2. IP-whitelist your Bitget API key to the VM's public IP (and drop Withdraw
   permission while you're in there)
3. Write `/etc/forexbot.env`, chmod 600
4. Install `deploy/longtrend-demo.service`

Why bother: the demo bot exists to prove the order path works *unattended*, which it
can't do on a machine that gets switched off.

Expect the orphan guard to fire on XRP — there's an open position on the exchange with
no state on the VM. That's correct behaviour. Close it in the Bitget UI or let the bot
skip that symbol.

### 3. Nothing, on Polymarket — it already runs itself

The Startup launcher brings it back after a reboot, so there is no job here. Check it with
`python health.py`, or read the numbers with `python poly_forward.py --report`. Korea
Central returns 451 for Polymarket, so it can't live on the VM; it snapshots once a day
and markets stay open for weeks, so a day with the PC off costs very little.

**Do not deposit money into Polymarket yet.** 0 resolutions so far, the time to an answer
is **unknown** (the old "1–3 weeks" was computed from a field since caught lying by ten
months), and a fourth artifact turned up on 2026-09-14. $5 would buy one-180th of the
information the free collector is already gathering — full arithmetic in
[doc 08](08-polymarket.md).

## What to expect, so it isn't a surprise

**Probably a losing month, and that is not failure.** ~20% win rate, median month
flat-to-down, and 2021 alone made 40% of this strategy's lifetime profit while
2025–2026 made 2.5%. A month tests the machinery, not the returns.

The numbers start meaning something around 30 closed trades.

## If you want to go further, in order of value

1. **Earn the capital.** $221 runs the validated strategy; $1,122 runs the safer
   major-coin version. One freelance automation job covers either, and it's a far
   better bet than turning $10 into $200 — see [doc 07](07-micro-account.md).
2. **Wait for the Polymarket answer.** 4–8 weeks. Either the first genuinely new edge
   in this project, or a dead end closed properly — see [doc 08](08-polymarket.md).
3. **Stop searching for a better signal.** ~75 configurations were tested in one day
   across indicators, chart types, bar construction, timeframes, exits, stop widths,
   universe size and venue. The two things that survived a holdout were the breakeven
   stop and the timeframe blend, and both are already deployed. Further sweeps on the
   same six years of data are mining, not research.

# Pick up here

*Written 2026-09-14, end of a long day. Read this first when you come back.*

## Nothing is broken. Nothing is urgent.

The thing that matters is already running.

| What | Where | Status |
|---|---|---|
| **$221 blend — the validated strategy** | **Azure VM, `blend-paper`** | **running 24/7** ✅ |
| Status page | Azure VM, `status-server` | running ✅ |
| Bitget demo order-path test | your PC | runs while the PC is on |
| Polymarket calibration | your PC, manual | 978 markets snapshotted |
| $10 micro bot | built, `ALLOW_REAL = False` | yours to flip, or not |

## Check on it whenever

```bash
cd /opt/forexbot && ./.venv/bin/python blend_paper.py --status
```

Per-sleeve and per-side breakdown, which is how you tell "the strategy is losing"
from "half of it isn't running."

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

### 3. Run the Polymarket test when your PC is on

```bash
python poly_forward.py
```

Korea Central returns 451 for Polymarket, so it can't live on the VM. It snapshots once
a day and markets stay open for weeks, so gaps cost very little.

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

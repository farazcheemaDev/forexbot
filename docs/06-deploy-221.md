# Deploying the $221 configuration

*Written 2026-09-13. Target: one month of forward data on the validated config.*

## Read this first — two things that would invalidate the test

### Bitget demo cannot run this strategy

Bitget's demo lists **exactly three contracts**: SBTC, SETH, SXRP. The validated
strategy needs twelve coins, and three coins was measured at **+3.98%/month** against
the twelve-coin blend's ~+12%.

### $221 is a MEXC number, not a Bitget number

| Venue | Capital floor for this book |
|---|---|
| **MEXC** | **$221** (binding coin NEAR) |
| Bitget | **$585** (binding coin ENA, 12h stop 14.84% wide) |

Bitget charges a flat $5 minimum per order; MEXC's minimum is the contract step, which
for these coins is $0.005–$2.28. At $221 on Bitget most signals get rejected for size.

**So: run the strategy on paper with MEXC minimums. Run Bitget demo separately, for
the order plumbing only.**

## What to deploy

| Service | Money | Coins | Question it answers |
|---|---|---|---|
| **`blend-paper`** | $221 simulated | 12 × 3 timeframes | **Does the strategy work?** |
| **`poly-forward`** | none | — | **Is Polymarket's 50–65¢ band really mispriced?** |
| `status-server` | — | — | Lets you check it from your phone |
| `longtrend-paper`, `xs-paper` | optional | — | Older single-timeframe comparisons |

`poly-forward` records live prices on open Polymarket markets and checks them when
they resolve. **No keys, no funds, no orders** — it contains no code that could place
one. It exists because the historical version of that test produced a +25% edge that
survived four checks and which I still don't believe: three separate measurement
artifacts were found inside that same test, and the remaining suspect
(requiring 30 days of price history may select toward YES) cannot be ruled out from
history at all. See [doc 08](08-polymarket.md).

It needs **120 resolutions in the 50–65¢ band** and snapshots daily. First readable
answer in **4–8 weeks**.

```bash
python poly_forward.py --report
```

The blend runner needs **no API keys and places no orders** — it reads Binance public
klines and simulates fills. Nothing on the VPS can touch money.

The Bitget demo bot (`longtrend_bot.py`) stays on your own machine. It places real
demo orders, and running a second copy elsewhere would double-trade one account.

## The steps

### 1. Create the VM

**Azure for Students** ($100 credit, 12 months) or Oracle Cloud free tier. Azure is
the better choice in practice: Oracle's ARM free tier is frequently "out of capacity"
and can take days of retrying, while Azure provisions immediately.

**Azure settings that matter:**

| Setting | Value | Why |
|---|---|---|
| Image | **Ubuntu Server 22.04 LTS** | what `setup.sh` expects |
| Size | **B2ats v2** (2 vCPU, 1 GiB) | the current free-tier size. AMD/x86_64 — `B2pts v2` is the ARM equivalent and also works, but x86 has every Python wheel without question |
| **OS disk** | **Premium SSD, 64 GB (P6)** | the free allowance is 64 GB × 2 of **P6** specifically. A default of another size or tier bills against the credit |
| Region | **Central India**, else **West Europe** | see below — the region is a real constraint, not a preference |
| Authentication | **SSH public key** | never password |
| Inbound ports | SSH (22) only at first | add 8080 later, deliberately |

**750 hours per month covers exactly ONE VM running continuously** (a 31-day month is
744 hours). All three services run on the one box. A second VM would exceed the free
allowance immediately and start consuming the $100.

**Region is not cosmetic — exchanges geo-block.** The bots read Binance klines for
every signal, so a blocked region produces a bot that runs cleanly and never trades.

| | Region | |
|---|---|---|
| ✅ | **Central India** | closest to Pakistan; Binance operates there |
| ✅ | **West Europe**, **Germany West Central**, **France Central** | reliable, unrestricted |
| ❌ | **any US region** | Binance blocks US IP ranges outright |
| ⚠️ | **Southeast Asia (Singapore)** | Binance withdrew from Singapore and restricts access from it |
| ⚠️ | **UK South** | Binance has been subject to FCA restrictions on UK access |

Student subscriptions show a reduced region list, and it is often filtered by whatever
else is already selected — if the region you want is missing, clear the **Size** field,
pick the region first, then choose the size.

You find out immediately either way: `setup.sh` step 4 fetches 60 bars from Binance and
asserts they arrived. A blocked region fails there, not three weeks later with an empty
log. Deleting and recreating a VM in another region costs about five minutes and no
credit.

**Add swap — mandatory, not optional.** The free-tier sizes give 2 vCPU but only
**1 GiB of RAM**, and three Python processes with pandas come to roughly 450 MB on top
of ~200 MB of OS. It fits with no headroom; without swap one allocation spike kills a
process and systemd restarts it mid-cycle:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

**Cost.** The VM and its P6 disk are free for the first 12 months, and roughly $10–15
a month after, so the $100 credit covers the year that follows. Azure for Students has
a **spending cap on by default** — when the credit runs out, resources are
deprovisioned rather than billed to a card. Leave that cap on.

Nothing else on Azure's free-services page is needed: no Blob Storage, Azure Files, Key
Vault, MySQL or PostgreSQL. The bots write CSVs and JSON to the local disk.

### 2. Get the code on it

On the VM:

```bash
sudo mkdir -p /opt/forexbot && sudo chown $(whoami) /opt/forexbot
```

From your own machine (Azure's default Ubuntu user is `azureuser`, Oracle's is
`ubuntu`):

```bash
scp -r D:/forexbot/* azureuser@<VM-IP>:/opt/forexbot/
```

**Copy `logs/poly_snapshots.csv` too.** It already holds 978 snapshotted markets, and
that is a head start on a test that needs 120 resolutions in one band. Losing it costs
weeks.

**Do NOT copy any API keys.** Nothing on the VPS needs them — `blend_paper.py` and
`poly_forward.py` read public endpoints only and place no orders. The Bitget demo bot
stays on your own machine.

### 3. Run the setup script

```bash
cd /opt/forexbot && bash deploy/setup.sh
```

It sets the clock to **UTC** (the bots key off hourly bar boundaries — a VM on local
time decides bars at the wrong moment), builds a venv, installs pandas/numpy/ccxt, and
runs two smoke tests: a 60-bar fetch, then one full cycle of the blend runner. If
Binance is unreachable from the VM, it fails here rather than three weeks in.

### 4. Start it

```bash
sudo systemctl enable --now blend-paper poly-forward status-server
```

Setup step 4c checks whether Polymarket's endpoints are reachable from the VM before
you enable `poly-forward` — some regions and hosts block them. If that check fails,
leave it off: it would log an error every 24 hours and collect nothing.

### 5. Confirm it's alive

```bash
journalctl -u blend-paper -f
```

You want an `alive |` line roughly every hour. That heartbeat exists because "working
and quiet" and "dead" used to look identical in these logs, and that ambiguity once
caused two bots to run on one account.

### 6. Check it from anywhere (optional)

Set a token first:

```bash
sudo systemctl edit status-server
```

Add:

```
[Service]
Environment=STATUS_TOKEN=pick-something-long
```

Then open port 8080.

**On Azure:** VM → Networking → *Add inbound port rule* → TCP 8080. That is the only
step; Azure's Ubuntu images ship with `ufw` inactive, so there is no second firewall
to fight.

**On Oracle:** you must do it in **both** places — the VCN security list *and* the
instance's own iptables, which the image ships with blocking:

```bash
sudo iptables -I INPUT 6 -p tcp --dport 8080 -j ACCEPT
sudo netfilter-persistent save
```

Then visit `http://<VM-IP>:8080/?t=pick-something-long`.

Restrict the rule's source to your own IP if you can. The token is the real protection,
but there is no reason to let the whole internet knock on it.

The server is GET-only, never reads the environment into its output, and serves a fixed
allow-list of files under `logs/`.

## What to expect after a month

**Probably a loss, and that is not a failure.**

| | |
|---|---|
| Expected | ~+8%/month |
| Win rate | **~20% — you lose 4 trades in 5** |
| Median month | flat to slightly down |
| Drawdown to expect eventually | 57% |

The strategy makes its money in a handful of months. 2021 alone produced 40% of its
lifetime profit, and 2025–2026 produced 2.5%. **A single month is a test of the
machinery, not of the returns.**

### What would actually tell you something in a month

| Check | Good sign | Bad sign |
|---|---|---|
| Trades taken | 40+ | under 10 — signals aren't firing |
| `skipped(min order)` | a handful | more than trades taken — $221 is too small |
| Both sleeves active | longs and shorts both | one side silent — a bug |
| All three timeframes | 1h, 4h and 12h all trading | 12h silent — resampling broken |
| Heartbeat | hourly, no gaps | gaps — the VM or feed dropped |

Check with:

```bash
cd /opt/forexbot && ./.venv/bin/python blend_paper.py --status
```

That prints a per-sleeve and per-side breakdown, which is what you need to tell "the
strategy is losing" apart from "half of it isn't running."

## Files

| File | Role |
|---|---|
| `blend_paper.py` | the validated config, live on paper |
| `deploy/blend-paper.service` | systemd unit |
| `deploy/setup.sh` | one-shot VM setup |
| `status_server.py` | read-only JSON status |
| `logs/blend_state.json` | positions, survives restarts |
| `logs/trades_blend.csv` | every closed trade |

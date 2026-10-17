# Forexbot Live - the dashboard (docs/24)

A read-only web page showing the final machine's paper books live: equity, P&L by book, every open position, the news
the bot reads, orders, closed trades, the other paper books and the VM's health. It can not change anything on the bots.

```
VM bots (unchanged) -> dashboard_push.py every minute (read-only) -> Upstash Redis -> this Next.js app on Vercel -> you
```

## Setup (you do the account steps; no key ever goes through chat or into the repo)

1. **Upstash** (free): create a Redis database at upstash.com. From its page copy the **REST URL**, the **REST token**
   (read-write, for the VM) and the **read-only REST token** (for Vercel).
2. **The VM feed**: on the VM, as root, create `/etc/forexbot-dash.env` with mode 600 containing two lines,
   `UPSTASH_REDIS_REST_URL=...` and `UPSTASH_REDIS_REST_TOKEN=...` (the read-write token). Then tell Claude it exists:
   it installs `deploy/forexbot-dash.service` + `.timer` (read-only towards the bots) and checks the first push.
3. **Vercel** (free, Hobby): "Add New Project" -> import the GitHub repo -> **Root Directory: `dashboard`** -> add these
   Environment Variables, then Deploy:
   - `UPSTASH_REDIS_REST_URL` - the same URL
   - `UPSTASH_REDIS_REST_TOKEN` - the **read-only** token (the page only reads)
   - `DASHBOARD_PASSWORD` - your password for the page (8+ characters)
   - `DASHBOARD_SECRET` - any long random string (32+ characters); it signs the login cookie
4. Open the Vercel URL, sign in with your password. The page refreshes itself every 30 seconds.

## Local test (no accounts)

```
cd dashboard && npm install && npm run build
SNAPSHOT_FILE=.local/snapshot.json DASHBOARD_PASSWORD=... DASHBOARD_SECRET=... npx next start -p 3210
```
`.local/` is gitignored; a snapshot is made on the VM with `python dashboard_push.py --print`.

"""SENTIMENT ENGINE, phase A: the history of public crypto news channels on Telegram (2026-10-16, docs/25)

Pages each channel's public web preview (t.me/s/<channel>) from the newest message back to START, through the VM (this
PC cannot reach t.me; the VM only READS the public page and prints it back over ssh - nothing is written there). Every
message is kept with its id, its timestamp to the second, its full text (up to 2,000 characters) and its view count.
Resumable: each channel's file is append-only JSONL and a re-run continues below the oldest id already saved.
Channels found live on 2026-10-16 (scratchpad probe of 30 names): see CHANNELS.
OUT  strategy_analysis/data/news/tg/<channel>.jsonl   (gitignored - third-party text)

    python -m news.tg_history                 all channels, in order
    python -m news.tg_history WatcherGuru     one channel
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "strategy_analysis" / "data" / "news" / "tg"
START = "2019-01-01"
CHANNELS = ["binance_announcements", "BWEnews", "WatcherGuru", "WuBlockchainEnglish", "Bybit_Announcements",
            "OKXAnnouncements", "Bitget_Announcements", "CoinMarketCapAnnouncements", "unfolded", "TreeNewsFeed",
            "cointelegraph", "whale_alert_io"]

VM_SCRIPT = r'''
import json, re, sys, time, urllib.request, html
from datetime import datetime
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
CH, BEFORE, STOP = "%CH%", %BEFORE%, datetime.fromisoformat("%START%").timestamp()
def page(before):
    u = "https://t.me/s/%s" % CH + ("?before=%d" % before if before else "")
    for k in range(6):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25).read().decode("utf-8", "replace")
        except Exception:
            time.sleep(3 * (k + 1))
    return None
def views(s):
    s = s.strip().upper()
    m = {"K": 1e3, "M": 1e6}.get(s[-1:], 1)
    try:
        return int(float(s.rstrip("KM")) * m)
    except Exception:
        return None
before, empty = BEFORE, 0
while True:
    h = page(before)
    if h is None:
        print(json.dumps({"error": "fetch failed", "before": before}), flush=True); break
    rows = []
    for blk in re.split(r'<div class="tgme_widget_message_wrap', h)[1:]:
        m_id = re.search(r'data-post="[^/]+/(\d+)"', blk)
        m_t = re.search(r'<time datetime="([^"]+)"', blk)
        if not (m_id and m_t):
            continue
        txt = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>\s*(?:<div class="tgme_widget_message_footer|<div class="tgme_widget_message_reactions|$)', blk, re.S)
        if not txt:
            txt = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', blk, re.S)
        t = re.sub(r"<br\s*/?>", "\n", txt.group(1)) if txt else ""
        t = html.unescape(re.sub(r"<[^>]+>", "", t)).strip()
        v = re.search(r'<span class="tgme_widget_message_views">([^<]+)</span>', blk)
        rows.append({"id": int(m_id.group(1)), "ts": datetime.fromisoformat(m_t.group(1)).timestamp(),
                     "text": t[:2000], "views": views(v.group(1)) if v else None})
    if not rows:
        empty += 1
        if empty >= 3 or (before is not None and before <= 1):
            break
        before = (before or 10**9) - 20
        continue
    empty = 0
    for r in rows:
        print(json.dumps(r, ensure_ascii=False), flush=True)
    low = min(r["id"] for r in rows)
    if min(r["ts"] for r in rows) < STOP or low <= 1:
        break
    before = low
    time.sleep(0.25)
'''


def oldest(path: Path):
    lo, ts = None, None
    if path.exists():
        for line in path.open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if "id" in r and (lo is None or r["id"] < lo):
                lo, ts = r["id"], r["ts"]
    return lo, ts


def fetch(ch: str):
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"{ch}.jsonl"
    lo, ts = oldest(f)
    if ts is not None and ts < __import__("datetime").datetime.fromisoformat(START).timestamp():
        print(f"{ch}: complete (oldest {lo})", flush=True)
        return
    script = VM_SCRIPT.replace("%CH%", ch).replace("%BEFORE%", str(lo) if lo else "None").replace("%START%", START)
    p = subprocess.Popen(["ssh", "forexbot-vm", "python3 -"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
    p.stdin.write(script)
    p.stdin.close()
    n = 0
    with f.open("a", encoding="utf-8") as w:
        for line in p.stdout:
            if line.startswith("{"):
                w.write(line)
                n += 1
                if n % 2000 == 0:
                    print(f"  {ch}: {n:,} messages", flush=True)
    p.wait()
    print(f"{ch}: +{n:,} messages", flush=True)


def main():
    for ch in (sys.argv[1:] or CHANNELS):
        fetch(ch)


if __name__ == "__main__":
    main()

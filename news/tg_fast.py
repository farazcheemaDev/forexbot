"""SENTIMENT ENGINE, phase A (faster): the channel histories in parallel ID SEGMENTS (2026-10-16, docs/25)

news/tg_history.py walks each channel from its newest message back, one channel per lane: ~100 messages a minute a
lane, and one lane held 112k messages (Cointelegraph alone 73k) - ~7 hours. Here every channel's REMAINING history -
below the oldest message already saved by tg_history.py - is cut into segments of SEG message ids; LANES segments run at
once (each its own ssh reader on the VM, which only reads public t.me pages), each resumable from its own file.
A segment stops at its low id or at START, whichever comes first, so segments that lie before START end on their
first page.
FILES  strategy_analysis/data/news/tg/<channel>.jsonl (tg_history's, newest part) and <channel>__<lo>_<hi>.jsonl
       (segments). news/enrich.py reads them all as one channel, de-duplicated by message id.

    python -m news.tg_fast
"""
from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from news.tg_history import CHANNELS, OUT, START, VM_SCRIPT, oldest  # noqa: E402

SEG = 4000
LANES = 8
# newest message ids from the 2026-10-16 probe (+50), for channels tg_history.py had not started yet
LATEST = {"Bybit_Announcements": 9980, "Bitget_Announcements": 18190, "unfolded": 20490, "cointelegraph": 72750,
          "CoinMarketCapAnnouncements": 18990, "OKXAnnouncements": 7340, "BWEnews": 16600, "WatcherGuru": 15580,
          "WuBlockchainEnglish": 26500, "binance_announcements": 9110}
STOP_TS = datetime.fromisoformat(START).timestamp()

SEG_SCRIPT = VM_SCRIPT.replace("before, empty = BEFORE, 0", "before, empty = BEFORE, 0\nLOW = %LOW%") \
    .replace('if min(r["ts"] for r in rows) < STOP or low <= 1:', 'if min(r["ts"] for r in rows) < STOP or low <= max(LOW, 1):')


def plan():
    jobs = []
    for ch in CHANNELS:
        if ch == "whale_alert_io":
            continue
        lo_id, lo_ts = oldest(OUT / f"{ch}.jsonl")
        if lo_ts is not None and lo_ts < STOP_TS:
            continue
        hi = lo_id or LATEST.get(ch)
        if hi is None:
            print(f"  {ch}: no newest id known - skipped", flush=True)
            continue
        for a in range(hi, 1, -SEG):
            jobs.append((ch, max(a - SEG, 1), a))
    return jobs


def run(job):
    ch, lo, hi = job
    f = OUT / f"{ch}__{lo}_{hi}.jsonl"
    s_lo, s_ts = oldest(f)
    if s_ts is not None and (s_ts < STOP_TS or s_lo <= lo + 1):
        return ch, lo, hi, 0, "done"
    before = s_lo if s_lo else hi
    script = (SEG_SCRIPT.replace("%CH%", ch).replace("%BEFORE%", str(before)).replace("%START%", START)
              .replace("%LOW%", str(lo)))
    p = subprocess.Popen(["ssh", "forexbot-vm", "python3 -"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
    p.stdin.write(script)
    p.stdin.close()
    n, err = 0, ""
    with f.open("a", encoding="utf-8") as w:
        for line in p.stdout:
            if not line.startswith("{"):
                continue
            r = json.loads(line)
            if "error" in r:
                err = r["error"]
                continue
            if r["id"] < lo:
                continue
            w.write(line)
            n += 1
    p.wait()
    return ch, lo, hi, n, err or "ok"


def main():
    jobs = plan()
    print(f"{len(jobs)} segments of {SEG} ids, {LANES} at once", flush=True)
    with ThreadPoolExecutor(LANES) as ex:
        for ch, lo, hi, n, msg in ex.map(run, jobs):
            print(f"  {ch} {lo}-{hi}: +{n:,} ({msg})", flush=True)
    print("all segments finished", flush=True)


if __name__ == "__main__":
    main()

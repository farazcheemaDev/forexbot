"""PUBLIC SIGNAL CHANNELS - does any of them call his trades? (2026-10-20, his_strategy.md s72)

The user: "he is not a god, there is something we are unable to see" -> the best-fitting unseen source is a live signal
feed (his sittings, quick entries, +7 targets and monthly target look like following calls). Public NASDAQ / gold
signal channels on Telegram were found by probing ~350 likely usernames from the VM (71 public, these 18 active in 2026
with NASDAQ or gold calls). This pages each one's public web preview back to 2025-12-20 through the VM (this PC cannot
reach t.me; the VM only reads public pages), with news.tg_history's reader.
OUT  strategy_analysis/data/news/tg_signals/<channel>.jsonl (gitignored - third-party text)

    python -m news.signal_channels
"""
from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from news.tg_history import VM_SCRIPT, oldest  # noqa: E402

OUT = ROOT / "strategy_analysis" / "data" / "news" / "tg_signals"
START = "2025-12-20"
CHANNELS = ["GoldNAS100Signals", "US100_signals", "nas100us30official", "NASDAQ_FREE_SIGNALS", "Nas100trader",
            "NASDAQ100_SIGNALS", "anthonys_forex", "gold_signals", "royal_gold_signals", "GoldSignals_official",
            "GoldXAUUSDSignals", "goldpips", "ForexGold_Scalper", "MetatraderGoldSignals", "goldsignals", "forexsignals",
            "Fx_Canli", "forexgdp"]


def fetch(ch: str) -> str:
    f = OUT / f"{ch}.jsonl"
    lo, ts = oldest(f)
    from datetime import datetime
    if ts is not None and ts < datetime.fromisoformat(START).timestamp():
        return f"{ch}: complete"
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
    p.wait()
    return f"{ch}: +{n:,} messages"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(6) as ex:
        for msg in ex.map(fetch, CHANNELS):
            print(msg, flush=True)
    print("all channels done", flush=True)


if __name__ == "__main__":
    main()

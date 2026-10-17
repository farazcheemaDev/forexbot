"""SENTIMENT ENGINE: tone of every event headline with FinBERT (2026-10-17, docs/25 phase B)

The user: "you quoted Binance listings and all but not the other news". news/impact.py measured every TYPE of news
(ETF, hacks, regulation, macro, treasury buys ...) - all ~0 after the bot could act - but each type averages GOOD and
BAD news together ("ETF approved" with "ETF outflows"), which can cancel a real effect. This scores each event's
headline (first line, <= 128 tokens) with FinBERT (ProsusAI/finbert, local, CPU; safetensors weights in
strategy_analysis/data/models): tone = P(positive) - P(negative), in [-1, +1]. news/impact.py --tone then splits each
type by tone. Output: strategy_analysis/data/news/tone.parquet (event index -> tone), resumable in chunks.

    python -m news.tone
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "strategy_analysis" / "data" / "news" / "events.parquet"
OUT = ROOT / "strategy_analysis" / "data" / "news" / "tone.parquet"
MODEL = ROOT / "strategy_analysis" / "data" / "models" / "ProsusAI__finbert"
BATCH, CHUNK = 64, 4096
MAXLEN = 64                       # headlines are short; 128 tokens ran ~14 headlines a second, 64 about twice that
PRIORITY = {"etf", "regulation", "macro", "treasury_buy", "hack", "partnership", "unlock", "whale"}


def main():
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    torch.set_num_threads(max(1, (__import__("os").cpu_count() or 4) - 1))
    E = pd.read_parquet(EV)
    done = pd.read_parquet(OUT) if OUT.exists() else pd.DataFrame(columns=["tone"])
    todo = E.index[~E.index.isin(done.index)]
    # the general-news types first (they are what the tone split is for), the 88k 'other' bucket last
    first = E.loc[todo, "etype"].isin(PRIORITY).to_numpy()
    todo = todo[first].append(todo[~first])
    print(f"{len(E):,} events, {len(done):,} scored, {len(todo):,} to go", flush=True)
    tok = AutoTokenizer.from_pretrained(MODEL)
    m = AutoModelForSequenceClassification.from_pretrained(MODEL, use_safetensors=True).eval()
    lab = {v: k for k, v in m.config.id2label.items()}
    ip, ineg = lab["positive"], lab["negative"]
    heads = E.text.str.split("\n").str[0].str.slice(0, 300)
    for a in range(0, len(todo), CHUNK):
        ids = todo[a:a + CHUNK]
        ids = ids[np.argsort(heads.loc[ids].str.len().to_numpy(), kind="stable")]     # similar lengths batch together
        tones = []
        with torch.no_grad():
            for b in range(0, len(ids), BATCH):
                x = tok(list(heads.loc[ids[b:b + BATCH]]), padding=True, truncation=True, max_length=MAXLEN, return_tensors="pt")
                p = m(**x).logits.softmax(-1).numpy()
                tones += list(p[:, ip] - p[:, ineg])
        done = pd.concat([done, pd.DataFrame({"tone": np.array(tones, float)}, index=ids)])
        done.to_parquet(OUT)
        print(f"  {len(done):,} / {len(E):,}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()

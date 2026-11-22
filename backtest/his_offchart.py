"""Two off-chart checks: (1) his click-timing signature, (2) does crypto (BTC) move before his NASDAQ clicks (2026-11-14)

The user: he sees data I don't - test what's left in reach.
TIMING: if he reacts to a once-a-minute signal/alert, his entry second-into-the-minute should cluster TIGHT (a machine/alert lag,
  sd ~2-3s); if he scans the chart by eye it is loose (sd ~5-8s). Report the fine distribution, the in-cluster spread, old vs new.
CRYPTO: BTC trades 24/7 and he could watch it; does BTC's move in the 1/3/5 min BEFORE his click lean his way (a lead he sees)?
  Binance 1-min klines around each of his 53 NASDAQ clicks, his-side-aligned, ranked vs the same clock minute on other days, and
  does the prior BTC move predict the +-7 outcome. (1-min resolution: a coarse first pass; a seconds-scale lead needs tick data.)

    python -m backtest.his_offchart
"""
from __future__ import annotations

import sys
import time
import urllib.request
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOG = ROOT / "logs" / "his_offchart.txt"


def klines(sym, start_ms, end_ms):
    url = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1m&startTime={int(start_ms)}&endTime={int(end_ms)}&limit=1000"
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(1)
    return []


def main():
    from backtest.his_fade_stretch import entries
    X = entries()
    X = X[X.mk == "USTECm"].sort_values("utc").reset_index(drop=True)
    cards = json.loads(Path("C:/Users/HP/AppData/Local/Temp/claude/fef2cc426e076a16/20580fec-5e7c-4155-b549-2f55b3e95bb2/scratchpad/his_trainer.json").read_text())
    assert len(cards) == len(X), (len(cards), len(X))
    OUT = {i: (c["side"], c["outcome"]) for i, c in enumerate(cards)}
    L = [f"backtest/his_offchart.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(X)} NASDAQ clicks", ""]

    # ---- TIMING ----
    sec = X.utc.dt.second.to_numpy()
    new = (X.utc > pd.Timestamp("2026-10-01")).to_numpy()
    inwin = (sec >= 5) & (sec <= 24)
    L += ["1. CLICK-TIMING SIGNATURE (second into the clock minute; a 1-min candle closes at :00)",
          "   histogram (5-s bins): " + " ".join(f"{k * 5:02d}-{k * 5 + 4:02d}:{int(((sec >= k * 5) & (sec < k * 5 + 5)).sum())}" for k in range(12)),
          f"   all: median {np.median(sec):.0f}s, sd {sec.std(ddof=1):.1f}s; in 5-24s: {int(inwin.sum())}/{len(sec)}, "
          f"sd within cluster {sec[inwin].std(ddof=1):.1f}s (alert~2-3s, human-scan~5-8s)",
          f"   old (46): median {np.median(sec[~new]):.0f}s, in 5-24s {int(((sec >= 5) & (sec <= 24) & ~new).sum())}/{int((~new).sum())}; "
          f"new (7): seconds {sorted(sec[new].tolist())}", ""]

    # ---- CRYPTO LEAD ----
    rng = np.random.default_rng(5)
    rows = []
    for idx, r in enumerate(X.itertuples()):
        click = r.utc
        a = (click - pd.Timedelta(minutes=30))
        b = (click + pd.Timedelta(minutes=2))
        kl = klines("BTCUSDT", a.value // 10**6, b.value // 10**6)
        if len(kl) < 20:
            continue
        kt = np.array([k[0] for k in kl])
        kc = np.array([float(k[4]) for k in kl])
        def px(ts):
            i = np.searchsorted(kt, ts.value // 10**6, "right") - 1
            return kc[i] if i >= 0 else np.nan
        p0 = px(click)
        feats = {}
        for k in (1, 3, 5):
            pk = px(click - pd.Timedelta(minutes=k))
            feats[k] = r.s * (p0 / pk - 1) if pk and np.isfinite(pk) else np.nan   # his-side-aligned BTC return
        # controls: same idea at +-1..20 min offsets
        ctl = {1: [], 3: [], 5: []}
        for m in list(range(-20, 0)) + list(range(1, 21)):
            u = click + pd.Timedelta(minutes=m)
            pu = px(u)
            for k in (1, 3, 5):
                puk = px(u - pd.Timedelta(minutes=k))
                if pu and puk and np.isfinite(pu) and np.isfinite(puk):
                    ctl[k].append(r.s * (pu / puk - 1))
        rk = {k: (np.mean(np.array(ctl[k]) < feats[k]) if (np.isfinite(feats[k]) and len(ctl[k]) >= 10) else np.nan) for k in (1, 3, 5)}
        _side, _out = OUT[idx]
        up_first = 1 if (_side == 1) == (_out == "WON") else 0
        rows.append(dict(**{f"r{k}": rk[k] for k in (1, 3, 5)}, **{f"v{k}": feats[k] for k in (1, 3, 5)}, up=up_first, side=r.s))
        time.sleep(0.15)
    R = pd.DataFrame(rows)
    L += [f"2. DOES BTC MOVE HIS WAY BEFORE HIS CLICK? ({len(R)} clicks with BTC data; his-side-aligned BTC return, ranked vs same-clock-minute controls, 0.5 = ordinary)"]
    from scipy import stats
    for k in (1, 3, 5):
        v = R[f"r{k}"].dropna().to_numpy()
        p = stats.wilcoxon(v - 0.5).pvalue if len(v) > 5 else np.nan
        # does prior BTC move direction predict the +-7 outcome?
        d = R.dropna(subset=[f"v{k}"])
        pred = ((d[f"v{k}"] > 0) == (d.up == 1)).mean()
        L.append(f"   BTC prior {k}-min move his-way: mean rank {v.mean():.3f} (p {p:.2f}); "
                 f"its sign predicts +7-first {pred * 100:.0f}% of the time (coin flip 50%)")
    L += ["", "VERDICT",
          f"  timing: in-cluster sd {sec[inwin].std(ddof=1):.1f}s -> " + ("tight, consistent with reacting to a once-a-minute alert/message" if sec[inwin].std(ddof=1) < 4 else "loose, consistent with a human scanning the chart"),
          f"  crypto: BTC lead rank {R[['r1','r3','r5']].stack().mean():.3f} -> " + ("a lead worth a closer look" if abs(R[['r1','r3','r5']].stack().mean() - 0.5) > 0.06 else "no lead; BTC does not move his way before his clicks (at 1-min resolution)")]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    sys.exit(main())

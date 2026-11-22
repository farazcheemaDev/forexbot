"""Build a teaching set from his 53 real NASDAQ trades: the chart up to each entry + the hidden outcome (2026-11-14)

THE USER: "we have enough of his trades to teach ourselves". So turn his real entries into practice cards: for each trade, the 1-minute
chart for the hour BEFORE his click (what he saw), his side, and the forward path + the +-7 race outcome (hidden until you have guessed).
Prices are stored as POINTS from his entry (anonymous, comparable). Exness USTECm ticks via MT5. Writes scratchpad JSON for the HTML trainer.

    python -m backtest.his_trainer_data <out.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PRE_MIN, POST_MIN, K, RACE_S = 60, 15, 7.0, 15 * 60


def main():
    import MetaTrader5 as mt5
    from backtest.his_fade_stretch import entries
    assert mt5.initialize(), mt5.last_error()
    mt5.symbol_select("USTECm", True)
    X = entries()
    X = X[X.mk == "USTECm"].sort_values("utc").reset_index(drop=True)
    cards = []
    for n, r in enumerate(X.itertuples(), 1):
        a = r.utc - pd.Timedelta(minutes=PRE_MIN + 2)
        b = r.utc + pd.Timedelta(minutes=POST_MIN + 1)
        tk = mt5.copy_ticks_range("USTECm", a.tz_localize("UTC").to_pydatetime(), b.tz_localize("UTC").to_pydatetime(), mt5.COPY_TICKS_ALL)
        if tk is None or len(tk) < 100:
            continue
        s = pd.Series((tk["bid"] + tk["ask"]) / 2.0, index=pd.to_datetime(tk["time_msc"], unit="ms"))
        s = s[~s.index.duplicated(keep="last")].resample("1s").last().ffill()
        e = r.utc.floor("s")
        if e not in s.index:
            e = s.index[s.index.searchsorted(e) - 1]
        ep = float(s.loc[e])
        side = int(r.s)
        # 1-min candles in points from entry: pre (<= entry minute) and post
        pts = (s - ep).rename("p")
        mins = ((s.index - e) / pd.Timedelta(minutes=1)).to_numpy()
        df = pd.DataFrame({"p": pts.to_numpy(), "m": np.floor(mins).astype(int)})
        candles = []
        for m, g in df.groupby("m"):
            if -PRE_MIN <= m <= POST_MIN:
                candles.append([int(m), round(float(g.p.iloc[0]), 1), round(float(g.p.max()), 1),
                                round(float(g.p.min()), 1), round(float(g.p.iloc[-1]), 1)])
        # forward race from entry on the 1-s series
        seg = side * (s.loc[e:].to_numpy() - ep)
        up = np.flatnonzero(seg >= K)
        dn = np.flatnonzero(seg <= -K)
        if not len(up) and not len(dn):
            outcome, hit_s = "none", None
        elif len(up) and (not len(dn) or up[0] < dn[0]):
            outcome, hit_s = "WON", int(up[0])
        else:
            outcome, hit_s = "LOST", int(dn[0])
        cards.append(dict(n=n, date=str(r.utc.date()), side=side, candles=candles,
                          outcome=outcome, hit_s=hit_s, k=K))
    mt5.shutdown()
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "logs" / "his_trainer.json")
    out.write_text(json.dumps(cards), encoding="utf-8")
    won = sum(c["outcome"] == "WON" for c in cards)
    dec = sum(c["outcome"] in ("WON", "LOST") for c in cards)
    print(f"{len(cards)} cards -> {out}; his race {won}/{dec} = {won / dec * 100:.0f}% won")


if __name__ == "__main__":
    sys.exit(main())

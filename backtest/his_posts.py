"""HIS TRADES AGAINST TRUMP'S POSTS - the unscheduled news no calendar carries.

The user, 2026-09-26: "some person who comes to speech and whatever the word he says affects the market".
§28 (his_calendar.py) covered scheduled speeches and releases. Truth Social posts are the unscheduled
kind. CNN's public archive (strategy_analysis/data/truth_archive.csv, 14 MB, downloaded 2026-09-26 with the
user's OK, not committed): 5,685 posts in his period, ~22 a day at all hours.

Post classes:
  ANY     every post (a third are reposts or media with no text)
  MKT     text mentions a market topic: MARKET_RX below (tariffs, trade, China, the Fed, rates, stocks,
          the economy, inflation, oil, Iran/Israel/Russia/Ukraine, war, sanctions, the dollar, crypto)
  MOVE    NASDAQ reacted, whatever the text: the 5-minute bar containing the post or the next one has a
          range >= 2x the median range of its own clock slot (USTECm 5m bars, his_news.bars()) - defined
          from price alone, so it also catches posts whose words I would not have picked
Features of a moment m: post_15 / post_60 (ANY in the prior 15 / 60 min), mkt_30 / mkt_60 (MKT in the
prior 30 / 60 min), move_60 (a MOVE post in the prior 60 min). CONTROL as in his_calendar.py: the same New
York clock time on the other US trading days of his period; Poisson-binomial z; Holm over 5; repeated on
the first entry of each day. Plus the last market post before each of his entries, for reading.

REGISTERED PREDICTION (2026-09-26, before running): posts do not mark his entries. Every feature within
0.7-1.5x of control, nothing survives Holm. move_60 in particular sits at control, because §24 found the
bars in the hour before his entries ordinary, and a post that moved NASDAQ would be such a bar.

    python -m backtest.his_posts
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.his_calendar import HOLIDAYS, any_in, et_to_utc, holm, zp  # noqa: E402
from backtest.his_news import bars  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
POSTS = ROOT / "strategy_analysis" / "data" / "truth_archive.csv"
GMT = 5.0
MARKET_RX = (r"tariff|trade deal|trade war|\bchina\b|chinese|\bxi\b|federal reserve|\bthe fed\b|\bfed\b|powell|warsh|"
             r"interest rate|rate cut|\brates\b|stock market|\bstocks\b|\bdow\b|nasdaq|s&p|economy|inflation|\boil\b|"
             r"\biran\b|israel|russia|ukraine|\bwar\b|sanction|\bdollar\b|crypto|bitcoin|recession|jobs report|"
             r"treasury|\bbonds?\b|deficit|\bdeal\b")
FEATS = ("post_15", "post_60", "mkt_30", "mkt_60", "move_60")


def posts():
    t = pd.read_csv(POSTS)
    t["utc"] = pd.to_datetime(t.created_at, utc=True).dt.tz_localize(None)
    t = t[(t.utc >= "2025-12-31") & (t.utc < "2026-09-17")].sort_values("utc", kind="stable").reset_index(drop=True)
    t["text"] = t.content.fillna("").astype(str)
    t["mkt"] = t.text.str.contains(MARKET_RX, case=False, regex=True)
    return t


def mark_moves(t):
    b = bars()
    b = b[(b.index >= "2025-12-01") & (b.index < "2026-09-20")]
    med = b.groupby("slot").rng.median()
    b["rel"] = b.rng / b.slot.map(med)
    start = b.index.to_numpy("datetime64[ns]")
    rel = b.rel.to_numpy()
    k = np.searchsorted(start, t.utc.to_numpy("datetime64[ns]"), side="right") - 1
    ok = (k >= 0) & (k + 1 < len(start))
    k = np.clip(k, 0, len(start) - 2)
    inside = (t.utc.to_numpy("datetime64[ns]") - start[k]) < np.timedelta64(5, "m")
    r = np.fmax(rel[k], rel[k + 1])
    t["move"] = ok & inside & (r >= 2.0)
    return t


def feats(P, m):
    m = np.datetime64(m, "ns")
    mn = np.timedelta64(60, "s")
    return dict(post_15=any_in(P["ANY"], m - 15 * mn, m), post_60=any_in(P["ANY"], m - 60 * mn, m),
                mkt_30=any_in(P["MKT"], m - 30 * mn, m), mkt_60=any_in(P["MKT"], m - 60 * mn, m),
                move_60=any_in(P["MOVE"], m - 60 * mn, m))


def test(entries, P, days, title, out):
    obs = {k: 0 for k in FEATS}
    ps = {k: [] for k in FEATS}
    for r in entries.itertuples():
        mine = feats(P, r.utc)
        clock = r.et - r.et.normalize()
        ctrl = [feats(P, et_to_utc(d + clock)) for d in days if d != r.et.normalize()]
        for k in FEATS:
            obs[k] += mine[k]
            ps[k].append(np.mean([c[k] for c in ctrl]))
    res = {k: zp(obs[k], ps[k]) for k in FEATS}
    h = holm({k: v[2] for k, v in res.items()})
    out.append(f"\n{title}: {len(entries)} entries against the same ET clock time on {len(days)} trading days")
    out.append(f"  {'feature':<10}{'his':>6}{'expected':>10}{'ratio':>7}{'z':>7}{'p':>7}{'Holm':>7}")
    for k in FEATS:
        e, z, p = res[k]
        out.append(f"  {k:<10}{obs[k]:>6}{e:>10.1f}{obs[k] / e if e else np.nan:>7.2f}{z:>+7.2f}{p:>7.3f}{h[k]:>7.3f}")


def main():
    t = mark_moves(posts())
    P = {"ANY": np.sort(t.utc.to_numpy("datetime64[ns]")), "MKT": np.sort(t[t.mkt].utc.to_numpy("datetime64[ns]")),
         "MOVE": np.sort(t[t.move].utc.to_numpy("datetime64[ns]"))}
    x = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time"])
    x["utc"] = x.open_time - pd.Timedelta(hours=GMT)
    x["et"] = x.utc.dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
    x = x.sort_values("utc", kind="stable")
    days = [d for d in pd.bdate_range("2026-01-02", "2026-09-15") if f"{d:%Y-%m-%d}" not in HOLIDAYS]
    nq = x[x.symbol.str.startswith("NASDAQ")]
    out = [f"Truth Social, 2026-01-01..09-16: {len(t)} posts ({len(t)/258:.1f} a day), {int(t.mkt.sum())} on a market topic, "
           f"{int(t.move.sum())} followed by a NASDAQ bar >= 2x its clock slot's median range "
           f"({int((t.move & t.mkt).sum())} of them on a market topic)."]
    test(nq, P, days, "NASDAQ, every entry", out)
    test(nq.groupby(nq.et.dt.normalize()).head(1), P, days, "NASDAQ, first entry of each day", out)
    out.append("\nNASDAQ $ per trade (net), with vs without")
    rows = []
    for r in nq.itertuples():
        f = feats(P, r.utc)
        last = t[(t.utc <= r.utc) & t.mkt].tail(1)
        lp = last.iloc[0] if len(last) else None
        desc = (f"{(r.utc - lp.utc).total_seconds() / 60:.0f}m before{' [NASDAQ moved]' if lp.move else ''}: "
                f"{' '.join(lp.text.split())[:90]}") if lp is not None else "-"
        rows.append(f | {"et": r.et, "side": r.side, "net": r.net, "last": desc})
    T = pd.DataFrame(rows)
    for k in FEATS:
        a, b = T[T[k]].net, T[~T[k].astype(bool)].net
        out.append(f"  {k:<10} with: n {len(a):>2}  ${a.mean() if len(a) else np.nan:7.2f}   without: n {len(b):>2}  ${b.mean():7.2f}")
    out.append("\nEVERY NASDAQ ENTRY and the last market-topic post before it")
    for r in T.itertuples():
        out.append(f"  {r.et:%Y-%m-%d %H:%M} ET {r.side:<4} ${r.net:>7.2f} | {r.last}")
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_posts.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()

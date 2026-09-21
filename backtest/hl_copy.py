"""COPY THE BEST TRADERS ON HYPERLIQUID - does trader performance persist?

THE IDEA
    Hyperliquid is an on-chain perp exchange: every account's PnL history is public.
    "Copy the top wallets" is the popular trade. It only works if the traders who did best
    in one window KEEP doing best in the next. If winners are mostly lucky or over-levered,
    last quarter's leaderboard says nothing about next month, and copying it is noise with
    extra fees and a delay on every fill.

    So this tests the precondition, on the wallets' OWN returns. Copying can only be worse
    than the wallet itself (lag, slippage, sizing). If the wallet's own next-month return
    does not persist, copying is dead without further work.

THE SAMPLE, AND ITS ONE BIAS
    The public leaderboard: 46,621 accounts, 16,308 of them now worth under $10 - so
    accounts that blew up are still listed, which is what makes a persistence test honest.
    A random sample of accounts that traded at least $1M lifetime (people worth copying),
    and each one's full cumulative-PnL and account-value history from the portfolio API.

    Remaining bias: an account that blew up AND was later dropped from the leaderboard is
    missing. That can only flatter the winners, never hurt them.

THE TEST, POINT IN TIME
    At every month-end D from mid-2023: take accounts worth >= $10k at D with history back
    to D-90d. Rank by return over [D-90d, D] (PnL change / account value at D-90d, which
    ignores deposits - deposits do not change PnL). Then measure each account's return over
    [D, D+30d]. Report the top decile vs everyone vs the bottom decile, and the rank
    correlation between the two windows, month by month.

    python -m backtest.hl_copy
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

OUT = Path(__file__).resolve().parents[1] / "strategy_analysis" / "data" / "hyperliquid"
N_SAMPLE, MIN_VLM, MIN_EQ = 3000, 1e6, 10_000
FORM_D, HOLD_D = 90, 30


def leaderboard():
    f = OUT / "leaderboard.json"
    if f.exists():
        return json.load(open(f))
    OUT.mkdir(parents=True, exist_ok=True)
    raw = urllib.request.urlopen(urllib.request.Request(
        "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard",
        headers={"User-Agent": "Mozilla/5.0"}), timeout=180).read()
    rows = json.loads(raw)["leaderboardRows"]
    slim = []
    for r in rows:
        w = dict(r["windowPerformances"])
        slim.append(dict(addr=r["ethAddress"], av=float(r["accountValue"]),
                         vlm=float(w.get("allTime", {}).get("vlm", 0) or 0),
                         pnl=float(w.get("allTime", {}).get("pnl", 0) or 0)))
    json.dump(slim, open(f, "w"))
    return slim


def portfolio(addr):
    f = OUT / "portfolio" / f"{addr}.json"
    if f.exists():
        return json.load(open(f))
    f.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps({"type": "portfolio", "user": addr}).encode()
    for a in range(8):
        try:
            r = urllib.request.Request("https://api.hyperliquid.xyz/info", data=body,
                                       headers={"Content-Type": "application/json",
                                                "User-Agent": "Mozilla/5.0"})
            p = json.loads(urllib.request.urlopen(r, timeout=60).read())
            d = dict(p).get("allTime", {})
            out = {"pnl": d.get("pnlHistory", []), "av": d.get("accountValueHistory", [])}
            json.dump(out, open(f, "w"))
            time.sleep(1.0)
            return out
        except Exception as e:
            time.sleep(5 * (a + 1) if "429" in str(e) else 2)
    return None


def series(p):
    """Daily cumulative PnL and account value, interpolated from the sampled history."""
    if not p or len(p["pnl"]) < 3:
        return None
    pn = pd.Series({pd.Timestamp(int(t), unit="ms"): float(v) for t, v in p["pnl"]})
    av = pd.Series({pd.Timestamp(int(t), unit="ms"): float(v) for t, v in p["av"]})
    days = pd.date_range(pn.index.min().normalize(), pn.index.max().normalize(), freq="D")
    f = lambda s: s.sort_index().reindex(s.index.union(days)).interpolate("time").reindex(days)
    return pd.DataFrame({"pnl": f(pn), "av": f(av)})


def main():
    lb = leaderboard()
    pool = [r for r in lb if r["vlm"] >= MIN_VLM]
    rng = np.random.default_rng(0)
    pick = [pool[i] for i in rng.choice(len(pool), size=min(N_SAMPLE, len(pool)),
                                        replace=False)]
    print(f"leaderboard {len(lb):,} accounts; {len(pool):,} traded >= ${MIN_VLM/1e6:.0f}M "
          f"lifetime; sampling {len(pick):,} at random", flush=True)
    S = {}
    with ThreadPoolExecutor(2) as ex:
        for k, (r, p) in enumerate(zip(pick, ex.map(lambda r: portfolio(r["addr"]), pick))):
            s = series(p)
            if s is not None:
                S[r["addr"]] = s
            if (k + 1) % 250 == 0:
                print(f"  {k + 1}/{len(pick)} histories", flush=True)
    print(f"{len(S):,} accounts with usable history\n")

    start = min(s.index.min() for s in S.values()) + pd.Timedelta(days=FORM_D)
    end = max(s.index.max() for s in S.values()) - pd.Timedelta(days=HOLD_D)
    rows, rho = [], []
    for D in pd.date_range(start, end, freq="ME"):
        a0, b0 = D - pd.Timedelta(days=FORM_D), D + pd.Timedelta(days=HOLD_D)
        form, nxt = {}, {}
        for addr, s in S.items():
            if a0 < s.index[0] or b0 > s.index[-1]:
                continue
            base, eqD = s.at[a0, "av"], s.at[D, "av"]
            if base < MIN_EQ or eqD < MIN_EQ:
                continue
            form[addr] = (s.at[D, "pnl"] - s.at[a0, "pnl"]) / base
            nxt[addr] = max((s.at[b0, "pnl"] - s.at[D, "pnl"]) / eqD, -1.0)
        if len(form) < 50:
            continue
        f, n = pd.Series(form), pd.Series(nxt)
        q = f.rank(pct=True)
        top, bot = n[q >= 0.9], n[q <= 0.1]
        rows.append(dict(D=D, n=len(f), top=top.mean(), top_med=top.median(),
                         all=n.mean(), all_med=n.median(), bot=bot.mean(),
                         top_win=(top > 0).mean()))
        rho.append(f.rank().corr(n.rank()))
    R = pd.DataFrame(rows)
    R["rho"] = rho
    R.to_csv(OUT / "persistence.csv", index=False)
    print(f"{'month-end':<11}{'accts':>6}{'TOP10% next mo':>16}{'median':>9}{'win':>6}"
          f"{'EVERYONE':>10}{'median':>9}{'BOTTOM10%':>11}{'rank corr':>11}")
    for r in R.itertuples():
        print(f"{r.D:%Y-%m}    {r.n:>6}{r.top*100:>+15.1f}%{r.top_med*100:>+8.1f}%"
              f"{r.top_win*100:>5.0f}%{r.all*100:>+9.1f}%{r.all_med*100:>+8.1f}%"
              f"{r.bot*100:>+10.1f}%{r.rho:>+11.2f}")
    d = R.top - R["all"]
    t = d.mean() / (d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 2 else np.nan
    dm = R.top_med - R.all_med
    print(f"\nTOP decile minus EVERYONE, next month: mean {d.mean()*100:+.2f}%/mo "
          f"(t {t:+.2f}, {len(d)} months, positive in {(d > 0).mean()*100:.0f}%); "
          f"median-vs-median {dm.mean()*100:+.2f}%")
    print(f"mean rank correlation between formation and next month: {R.rho.mean():+.3f} "
          f"(positive in {(R.rho > 0).mean()*100:.0f}% of months)")
    print(f"top decile's own next-month return: mean {R.top.mean()*100:+.2f}%, "
          f"median of monthly medians {R.top_med.median()*100:+.2f}%, "
          f"months with a positive mean {(R.top > 0).mean()*100:.0f}%")


if __name__ == "__main__":
    main()

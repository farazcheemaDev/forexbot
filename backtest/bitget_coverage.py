"""DOES BITGET'S SMALLER LIST COST THE MACHINE? - the books' coins that Bitget does not list (2026-10-24)

THE USER (2026-10-24): "91 small Binance coins aren't listed on Bitget at all - this won't affect gains, right?" The books
choose coins from BINANCE's rankings; a coin Bitget does not list cannot be held on a real Bitget account (combo_bot
logs it and skips it), so that part of a book's return would not be earned - or lost.
MEASURED on the 2024-08-29 .. 2026-09 holdout (the closest to today's listings), with TODAY's Bitget list
(combo_bot.Venue.mapped - names and units converted): for each book, the share of its trades / basket slots in coins
Bitget does not list, and what those trades made. The trend book's 12 coins are all listed. Today's open positions of
the two paper accounts are read from the dashboard snapshot if one is given.
LIMITS  Bitget's list of 2024-25 is not on record; a coin it listed then and dropped since counts as unlisted here, so
        the shares are an upper bound for the past.

RESULT (2026-10-24, logs/bitget_coverage.txt; BACKTEST) - no consistent cost; the exchange can wait (the user: "the main
thing is that the bot performs, then we decide the exchange").
  Per book, 2024-26: trend 0% unlisted; daily 4.8% of trades (they LOST: skipping them helps +9%); capit2 5.4% (-5% of
  its sum); news shorts 32% (-25% of its sum); MN blend 15-21% of basket slots (TON, OM, GOAT, AI16Z, SAGA, REEF...).
  The whole machine on Bitget-listed coins only (the next listed coin takes an unlisted one's slot), $300 typical year,
  paired: 2020-24 $4,435 -> $4,036 (-8.8% +- 2.7, 2/10 better; worst month -19.2% -> -24.0%); 2024-26 $9,838 -> $11,019
  (+16.5% +- 9.5, 5/10). One half worse, one better, inside the orderings' noise on the second: Bitget's smaller list
  moves the machine by about +-10%, not one way. Today's paper positions: main 5 of 55 unlisted (BTR, SAGA, BULLA),
  fresh 0 of 54. On Binance nothing is unlisted, but its minimum order is $20 for ETH / LINK / LTC / BCH and $50 for BTC.

    python -m backtest.bitget_coverage [snapshot.json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "bitget_coverage.txt"
CUT = pd.Timestamp("2024-08-29")


def listed():
    import ccxt
    sys.argv = sys.argv[:1] + [a for a in sys.argv[1:] if a.endswith(".json")]
    import combo_bot as cb
    ex = ccxt.bitget({"options": {"defaultType": "swap"}})
    ex.load_markets()
    v = cb.Venue(ex, "dry")
    return lambda sym: v.mapped(sym)[0] is not None


def trades_share(name, T, ok, L):
    T = T[pd.to_datetime(T.t_in) >= CUT]
    u = ~T.coin.map(ok)
    n, net = len(T), T.net.sum()
    L.append(f"   {name:<34}{n:>7} trades | not on Bitget {u.sum():>4} ({u.mean() * 100:>4.1f}%) | their net "
             f"{T.net[u].sum() * 100:>+8.1f}% of {net * 100:>+8.1f}% summed ({(T.net[u].sum() / net * 100 if net else 0):+.1f}%)")
    return u.mean(), T.net[u].sum() / net if net else 0.0


def mn_legs(ok, L):
    """How often the MN blend's and carry's baskets name a coin Bitget does not list (slots, 2024-26)."""
    from backtest import mn_combos as m
    D = m.data()
    idx, X_, cols = D["idx"], D["X"], D["cols"]
    C = pd.DataFrame(X_)
    d = C.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()
    mom = X_ / np.r_[np.full((30, X_.shape[1]), np.nan), X_[:-30]] - 1
    for nm, score, frac in (("MN blend, momentum half", mom, 0.1), ("MN blend, RSI half", rsi, 0.1)):
        tot = bad = 0
        names = {}
        for i in range(31, len(idx) - 8, 7):
            if idx[i] < CUT:
                continue
            okm = (D["Em"][D["months"][i]] & ((idx[i].value - D["fv"]) // 86_400_000_000_000 >= m.MIN_AGE_D)
                   & np.isfinite(X_[i]) & np.isfinite(X_[i - 30]))
            if okm.sum() < 20:
                continue
            cand = np.flatnonzero(okm)
            k = max(int(len(cand) * frac), 3)
            order = cand[np.argsort(np.where(np.isnan(score[i, cand]), np.inf, score[i, cand]), kind="stable")]
            for x in list(order[:k]) + list(order[-k:]):
                tot += 1
                if not ok(cols[x]):
                    bad += 1
                    names[cols[x]] = names.get(cols[x], 0) + 1
        top = sorted(names.items(), key=lambda kv: -kv[1])[:8]
        L.append(f"   {nm:<34}{tot:>7} slots  | not on Bitget {bad:>4} ({bad / tot * 100:>4.1f}%) | most: "
                 + ", ".join(f"{s[:-4]} {n}" for s, n in top))


def scored_listed(score_mat, start, keep, short_stop=0.5):
    """moderate_retests.scored_run (stop="short_only") choosing only among coins with keep[col] True: an unlisted coin's
    slot goes to the next-ranked LISTED coin. With keep all True it reproduces scored_run (asserted in machine_effect)."""
    from backtest import mn_combos as m
    Dd = m.ohl()
    idx, X_, Fx, ff = Dd["idx"], Dd["X"], Dd["Fx"], Dd["ff"]
    hold, look, frac = 7, 30, 0.1
    rows, pl_, ps_ = [], set(), set()
    for i in range(look + 1 + start, len(idx) - hold - 1, hold):
        t0 = idx[i]
        ok = (Dd["Em"][Dd["months"][i]] & ((t0.value - Dd["fv"]) // 86_400_000_000_000 >= m.MIN_AGE_D)
              & np.isfinite(X_[i]) & np.isfinite(X_[i - look]) & keep)
        if ok.sum() < 20:
            continue
        cand = np.flatnonzero(ok)
        past = score_mat[i, cand]
        k = max(int(len(cand) * frac), 3)
        order = cand[np.argsort(np.where(np.isnan(past), np.inf, past), kind="stable")]
        sh, lo = order[:k], order[-k:]
        fwd = (ff[i + hold] / X_[i] - 1).copy()
        for x in sh:
            lvl = X_[i, x] * (1 + short_stop)
            for dd in range(i + 1, i + hold + 1):
                if np.isfinite(Dd["Hi"][dd, x]) and Dd["Hi"][dd, x] >= lvl:
                    fwd[x] = max(Dd["Op"][dd, x], lvl) / X_[i, x] - 1
                    break
        fnd = Fx[i + 1:i + hold + 1].sum(axis=0)
        gross = 0.5 * fwd[lo].mean() - 0.5 * fwd[sh].mean()
        carry = 0.5 * (-fnd[lo].mean()) + 0.5 * fnd[sh].mean()
        L_, S_ = {Dd["cols"][x] for x in lo}, {Dd["cols"][x] for x in sh}
        cost = m.FEE * min((len(L_ ^ pl_) + len(S_ ^ ps_)) / (4 * k), 1.0)
        pl_, ps_ = L_, S_
        rows.append((t0 + pd.Timedelta(days=hold), gross + carry - cost))
    return pd.Series([r for _, r in rows], index=pd.DatetimeIndex([t for t, _ in rows])).groupby(level=0).sum()


def machine_effect(ok, news_rows, L):
    """The deployed machine (machine_fixes.py F1+F2) with its coin-picking books restricted to Bitget-listed coins:
    MN blend (both halves), daily, capit2 and news; trend is all listed; carry has no per-coin hook and is left as is."""
    import pickle
    from backtest import capit_combos as cc
    from backtest import daily_combos as dc
    from backtest import machine_combos as mc
    from backtest import mn_combos as m
    import news.combo as NC
    from backtest.all_books import machine_books, ndx_dip, news_book
    from backtest.machine import summary
    from backtest.machine_fixes import CACHE as MCACHE
    M = pickle.loads(MCACHE.read_bytes()) if MCACHE.exists() else machine_books()
    news0, ndx = news_book(), ndx_dip()
    newsB = NC.daily([(r["t_in"].value, r["t_out"], r["net"]) for r in news_rows if ok(r["coin"])])
    D = m.data()
    keep = np.array([ok(c) for c in D["cols"]])
    C = pd.DataFrame(D["X"])
    d = C.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()
    mom = D["X"] / np.r_[np.full((30, D["X"].shape[1]), np.nan), D["X"][:-30]] - 1
    TD = {off: dc.gen(off, dict(dc.BASE, mean_n=20)) for off in dc.PHASES}
    TC = {off: cc.gen(off, dict(cc.BASE, **mc.CAPIT_BETTER)) for off in cc.PHASES}
    TDb = {off: T[T.coin.map(ok)].reset_index(drop=True) for off, T in TD.items()}
    TCb = {off: T[T.coin.map(ok)].reset_index(drop=True) for off, T in TC.items()}
    mnb, chk = {}, []
    base_xs, bit_xs = [], []
    for sd, x in zip(mc.SEEDS, M):
        r = lambda s: s.reindex(x.index).fillna(0.0)  # noqa: E731
        o = sd % 7
        if o not in mnb:
            mnb[o] = 0.5 * r(scored_listed(mom, o, keep)) + 0.5 * r(scored_listed(rsi, o, keep))
            if not chk:                                          # the rebuild with every coin = the deployed MN blend
                full = 0.5 * r(scored_listed(mom, o, np.ones_like(keep))) + 0.5 * r(scored_listed(rsi, o, np.ones_like(keep)))
                chk.append(float((full - x.mn_blend).abs().max()))
        off, coff = dc.PHASES[sd % 3], cc.PHASES[sd % 4]
        daily_b = 0.5 * r(dc.curve(TDb[off], dc.allocate(TDb[off], sd), off).pct_change())
        capit_b = r(cc.curve(TCb[coff], dc.allocate(TCb[coff].assign(units=None), sd, 2.0)).pct_change())
        base_xs.append(x.trend + x.sleeve + x.daily + r(news0) + r(ndx) + x.mn_blend + x.carry + x.capit2 + x.bids)
        bit_xs.append(x.trend + x.sleeve + daily_b + r(newsB) + r(ndx) + r(mnb[o]) + x.carry + capit_b + x.bids)
    assert chk[0] < 1e-9, f"the MN rebuild does not reproduce the deployed book ({chk[0]:.2e})"
    L += ["", "THE WHOLE MACHINE on Bitget-listed coins only (MN blend, daily, capit2, news restricted; an unlisted coin's",
          "slot goes to the next listed one), $300 typical 12 months, paired per ordering - BACKTEST, today's Bitget list:"]
    for lab, a, b in (("2020-2024-08 (tune)", None, CUT), ("2024-08..2026-09 (holdout)", CUT, None)):
        cut = lambda xs: [s[((s.index >= a) if a is not None else True) & ((s.index < b) if b is not None else True)] for s in xs]  # noqa: E731
        s0, s1 = summary(cut(base_xs)), summary(cut(bit_xs))
        p0 = np.array([summary([q])["typ"] for q in cut(base_xs)])
        p1 = np.array([summary([q])["typ"] for q in cut(bit_xs)])
        dd = (p1 / p0 - 1) * 100
        L.append(f"   {lab:<28} Binance coins ${s0['typ']:>7,.0f} (worst month {s0['wm']:+.1f}%) | Bitget-listed ${s1['typ']:>7,.0f} "
                 f"(worst month {s1['wm']:+.1f}%) | {dd.mean():+.1f}% +- {dd.std(ddof=1) / np.sqrt(len(dd)):.1f}, {int((dd > 0).sum())}/10 better")


def main():
    ok = listed()
    from backtest import capit_combos as cc
    from backtest import daily_combos as dc
    from backtest import machine_combos as mc
    import news.combo as NC
    L = [f"backtest/bitget_coverage.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; trades / slots from {CUT:%Y-%m-%d}, "
         f"against Bitget's market list of today", ""]
    L.append("BOOKS (backtest, holdout)")
    L.append("   trend book: its 12 coins are all on Bitget")
    sh = {}
    sh["daily"] = trades_share("daily breakout (signals)", dc.gen(dc.PHASES[0], dict(dc.BASE, mean_n=20)), ok, L)
    sh["capit2"] = trades_share("capit2 crash buys (signals)", cc.gen(cc.PHASES[0], dict(cc.BASE, **mc.CAPIT_BETTER)), ok, L)
    # news_trades() keeps no coin names: its own loop, as all_books.news_book runs it, with the coin kept
    NB = NC.NB
    NB.FEE = 0.0012
    E = pd.read_parquet(NB.EV)
    E = E[E.etype.isin(("adds_products", "monitoring_tag")) & (E.coins != "")]
    rows = []
    for r in E.itertuples():
        entry = (pd.Timestamp(r.t).floor("h") + pd.Timedelta(hours=1)).value
        for coin in r.coins.split(",")[:3]:
            if coin and coin != "BTCUSDT":
                x = NB.trade(coin, entry, 72, 0.25)
                if x is not None:
                    rows.append(dict(coin=coin, t_in=pd.Timestamp(entry), t_out=x[2], net=x[0]))
    sh["news"] = trades_share("news shorts", pd.DataFrame(rows), ok, L)
    mn_legs(ok, L)
    machine_effect(ok, rows, L)
    snap = next((a for a in sys.argv[1:] if a.endswith(".json")), None)
    if snap:
        d = json.loads(Path(snap).read_text(encoding="utf-8"))
        L += ["", "TODAY'S PAPER POSITIONS (dashboard snapshot)"]
        for acct, a in d["accounts"].items():
            pos = a.get("open", [])
            fix = {"SHIBUSDT": "1000SHIBUSDT", "PEPEUSDT": "1000PEPEUSDT"}
            miss = [r for r in pos if not ok(fix.get(r["sym"], r["sym"]))]
            L.append(f"   {acct}: {len(pos)} open positions, {len(miss)} not on Bitget: "
                     + ", ".join(f"{r['book']} {r['side']} {r['sym'][:-4]} ${r['size']:.2f} (P&L {r['upnl']:+.2f})" for r in miss))
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

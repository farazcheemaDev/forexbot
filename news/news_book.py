"""SENTIMENT ENGINE, phase E2: a BAD-NEWS BOOK - short the coin, long BTC, after a negative coin event (2026-10-16)

news/impact.py: after a Binance monitoring tag, a launchpool / HODLer-airdrop token, a seed-tag token, Binance adding a
token to Margin / Futures, or a delisting, the coin fell against BTC for days (partial data: monitoring tag -311bp at
72h, launchpool -1,819bp over 7 days). news/veto_test.py: as a VETO on the daily / capit2 books it does nothing (0.3-1.6%
of trades; the vetoed breakouts were winners). So, as its own book:
    TRADE  at the open of the first full hour after the event: SHORT the coin, LONG the same notional of BTC (a
           market-neutral pair, so the bet is the coin's move AGAINST BTC, not the market's)
    HOLD   24h / 72h / 7 days; optional STOP when the coin is up S vs entry (S = 25% / 50%) on an hourly HIGH
    COST   12bp a round trip on each leg, and funding on both legs (capitulation_wide.funding_cum: a short RECEIVES
           positive funding, the BTC long pays it)
    TYPES  fixed in advance from the impact table's TUNE half: monitoring_tag, launchpool, seed_tag, adds_products,
           delist, delist_futures, list_futures
    BOOK   1/10 of equity per trade (each leg), at most 10 open, entries skipped while full; booked at exit
REPORTED  per type and combined: trades, mean net, share won, the worst trade, the worst adverse move before the exit
          (the squeeze), tune / holdout means (the impact table's cut), and the book's CAGR / fall.

REGISTERED BEFORE THE RUN (2026-10-16)
    N1 monitoring_tag, 72h: mean net >= +150bp on both halves.
    N2 launchpool + seed_tag, 7 days, no stop: mean net >= +500bp, but the worst trade <= -50% (squeezes).
    N3 the combined book (72h, stop 50%) is positive on both halves, with a fall > 25% at 1/10 a trade.

RESULT (2026-10-16, logs/news_book.txt; FULL history, 180k messages, 11 channels) - THE NEWS CARRIES A REAL EDGE.
    Every trade has a CONTROL: the identical short-coin / long-BTC trade on the same coin at 4 ordinary hours within
    +-60 days (shorting an altcoin against BTC earns its drift without any news). EDGE = news trade - control.
    TUNE-CHOSEN (adds_products, monitoring_tag, list_spot, new_pairs - picked from the impact table's tune half):
      per trade edge +240..+544bp at every hold / stop, positive on both halves (72h stop 25%: +296 / +293bp;
      7d stop 25%: +421 / +612bp). Books at 1/10 a trade: news +12..+27%/yr (fall 17-27%) vs control -4..+6%/yr.
    monitoring_tag alone: edge +142..+376bp, both halves. adds_products: +154..+588bp, both halves.
    ALL (registered set, incl. launchpool / delist / list_futures): edge +97..+330bp, tune half weaker; its 7-day
    no-stop book is wiped out by one squeeze (-1752% on one trade, as on the partial data) - the stop is mandatory.
    Predictions: N1 right (+532 / +119 - the holdout weaker); N2 right (+633 / +544bp, worst -103% / -164%); N3 right.
    Partial-data CAGRs (+40-50%) did not survive the full history: +24-27% is the number to quote.

    python -m news.news_book
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest.capitulation_wide import funding_cum, hourly  # noqa: E402

EV = ROOT / "strategy_analysis" / "data" / "news" / "events.parquet"
LOG = ROOT / "logs" / "news_book.txt"
TYPES = ("monitoring_tag", "launchpool", "seed_tag", "adds_products", "delist", "delist_futures", "list_futures")
# chosen AFTER the full-history impact table, from its TUNE half only (excess 72h <= -100bp; logs/news_impact.txt):
# judge this group on the holdout columns, and against its control
TUNE_CHOSEN = ("adds_products", "monitoring_tag", "list_spot", "new_pairs")
HOLDS = {"24h": 24, "72h": 72, "7d": 168}
STOPS = (None, 0.25, 0.50)
FEE = 0.0012
STOP_SLIP = 0.03                  # 3% worse than the stop level on every stopped short (squeezes jump inside the hour)
_C: dict = {}


def load(sym):
    if sym not in _C:
        h = hourly(sym)
        if h is None:
            _C[sym] = None
        else:
            t = h.time.to_numpy("datetime64[ns]")
            _C[sym] = (t.astype("int64"), h.open.to_numpy(float), h.high.to_numpy(float), h.close.to_numpy(float),
                       funding_cum(sym, t, h))
    return _C[sym]


def trade(coin, entry_ns, hold, stop):
    """Net return of short coin + long BTC (per unit of one leg's notional), worst adverse coin move, exit index ok."""
    c, b = load(coin), load("BTCUSDT")
    if c is None or b is None:
        return None
    ic, ib = np.searchsorted(c[0], entry_ns), np.searchsorted(b[0], entry_ns)
    if ic >= len(c[0]) or c[0][ic] != entry_ns or ib >= len(b[0]) or b[0][ib] != entry_ns:
        return None
    jc = min(ic + hold - 1, len(c[0]) - 1)
    if c[0][jc] - entry_ns > (hold + 6) * 3600 * 10**9:                 # a gap: the coin stopped trading
        return None
    e = c[1][ic]
    hi = c[2][ic:jc + 1] / e - 1
    mae = float(hi.max())
    x_c, j_exit = c[3][jc], jc
    if stop is not None and (hi >= stop).any():
        k = int(np.argmax(hi >= stop))
        # a coin that OPENS the bar above the stop fills at that open, not at the stop (gap risk)
        j_exit, x_c = ic + k, max(e * (1 + stop), c[1][ic + k] if k > 0 else e * (1 + stop))
        x_c *= 1 + STOP_SLIP                                            # a stop in a squeeze fills worse than its level
    t_exit = c[0][j_exit]
    jb = min(np.searchsorted(b[0], t_exit), len(b[0]) - 1)
    r_coin = x_c / e - 1
    r_btc = b[3][jb] / b[1][ib] - 1
    f_coin = (c[4][j_exit] - c[4][ic]) / e                              # funding paid by a LONG coin holder
    f_btc = (b[4][jb] - b[4][ib]) / b[1][ib]
    net = (-r_coin + f_coin) + (r_btc - f_btc) - 2 * FEE
    return net, mae, int(t_exit)


def book(trades, slots=10, frac=0.10):
    trades = sorted(trades, key=lambda x: x[0])
    eq, open_, pts = 1.0, [], []
    for t_in, t_out, net in trades:
        for p in sorted([p for p in open_ if p[0] <= t_in]):
            eq += p[1]
            pts.append((p[0], eq))
        open_ = [p for p in open_ if p[0] > t_in]
        if len(open_) >= slots or eq <= 0:
            continue
        open_.append((t_out, eq * frac * net))
    for p in sorted(open_):
        eq += p[1]
        pts.append((p[0], eq))
    if not pts:
        return np.nan, np.nan
    s = pd.Series([e for _, e in pts], index=pd.to_datetime([t for t, _ in pts])).groupby(level=0).last()
    yrs = max((s.index[-1] - s.index[0]).days / 365.25, 0.25)
    cagr = s.iloc[-1] ** (1 / yrs) - 1 if s.iloc[-1] > 0 else -1.0
    return cagr, float((1 - s / s.cummax()).max())


def main():
    Eall = pd.read_parquet(EV)
    cut = Eall.t.sort_values().iloc[int(len(Eall) * 0.6)]
    E = Eall[Eall.etype.isin(TYPES) & (Eall.coins != "")]
    lines = [f"news/news_book.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(E):,} negative coin events; short coin / long "
             f"BTC at the next hour's open; 12bp a leg + funding; tune/holdout cut {cut:%Y-%m-%d}", "",
             f"  {'type':<15}{'hold':>5}{'stop':>6}{'n':>5}{'mean':>8}{'won':>6}{'worst':>8}{'squeeze p90':>12}{'tune':>8}{'hold':>8}"]
    lines[-1] += f"{'control':>9}{'EDGE':>7}{'edge tune':>10}{'edge hold':>10}"
    R, allt, ctlt = {}, {}, {}
    rng = np.random.default_rng(17)
    day = 86400 * 10**9
    groups = [(et, (et,)) for et in TYPES] + [("ALL (registered)", TYPES), ("TUNE-CHOSEN", TUNE_CHOSEN)]
    for et, kinds in groups:
        g = E[E.etype.isin(kinds)]
        for hk, hh in HOLDS.items():
            for st in STOPS:
                rows = []
                for r in g.itertuples():
                    entry = (pd.Timestamp(r.t).floor("h") + pd.Timedelta(hours=1)).value
                    for coin in r.coins.split(",")[:3]:
                        if not coin or coin == "BTCUSDT":
                            continue
                        x = trade(coin, entry, hh, st)
                        if x is None:
                            continue
                        # CONTROL: the identical trade on the same coin at 4 ordinary hours within +-60 days (not the
                        # week around the event) - shorting an altcoin against BTC earns its usual drift without news
                        cs = []
                        for _ in range(4):
                            off = int(rng.integers(7, 60)) * day * (1 if rng.random() < 0.5 else -1)
                            ce = entry + off - (entry + off) % (3600 * 10**9)
                            y = trade(coin, ce, hh, st)
                            if y is not None:
                                cs.append((ce, y[2], y[0]))
                        if not cs:
                            continue
                        rows.append((entry, x[2], x[0], x[1], pd.Timestamp(r.t) >= cut, np.mean([c[2] for c in cs]), cs[0]))
                if len(rows) < 8:
                    continue
                net = np.array([x[2] for x in rows])
                mae = np.array([x[3] for x in rows])
                ho = np.array([x[4] for x in rows])
                ctl = np.array([x[5] for x in rows])
                ed = net - ctl
                R[(et, hk, st)] = dict(n=len(rows), mean=net.mean(), won=(net > 0).mean(), worst=net.min(),
                                       sq=np.percentile(mae, 90), tune=net[~ho].mean() if (~ho).any() else np.nan,
                                       hold=net[ho].mean() if ho.any() else np.nan, ctl=ctl.mean(), edge=ed.mean(),
                                       etune=ed[~ho].mean() if (~ho).any() else np.nan, ehold=ed[ho].mean() if ho.any() else np.nan)
                if et in ("ALL (registered)", "TUNE-CHOSEN"):
                    allt[(et, hk, st)] = [(a, b, c) for a, b, c, *_ in rows]
                    ctlt[(et, hk, st)] = [x[6] for x in rows]
                r_ = R[(et, hk, st)]
                lines.append(f"  {et[:15]:<15}{hk:>5}{('-' if st is None else f'{st:.0%}'):>6}{r_['n']:>5}{r_['mean'] * 1e4:>+7.0f}b"
                             f"{r_['won'] * 100:>5.0f}%{r_['worst'] * 100:>+7.0f}%{r_['sq'] * 100:>+11.0f}%"
                             f"{r_['tune'] * 1e4:>+7.0f}b{r_['hold'] * 1e4:>+7.0f}b{r_['ctl'] * 1e4:>+8.0f}b{r_['edge'] * 1e4:>+6.0f}b"
                             f"{r_['etune'] * 1e4:>+9.0f}b{r_['ehold'] * 1e4:>+9.0f}b")
    lines += ["", "  THE BOOKS (1/10 of equity a trade, max 10 open) - news trades vs the SAME trades at ordinary times:"]
    for key, tr in allt.items():
        cg, dd = book(tr)
        cc_ = ctlt[key]
        cg2, dd2 = book(list(cc_)) if cc_ else (np.nan, np.nan)      # cs entries are already (t_in, t_out, net)
        et, hk, st = key
        lines.append(f"    {et:<17} hold {hk:>3}, stop {('none' if st is None else f'{st:.0%}'):>4}: news CAGR {cg * 100:+6.0f}% fall "
                     f"{dd * 100:4.0f}%  | control CAGR {cg2 * 100:+6.0f}% fall {dd2 * 100:4.0f}%")
    m = R.get(("monitoring_tag", "72h", None), {})
    lp = [R.get((k, "7d", None), {}) for k in ("launchpool", "seed_tag")]
    al = R.get(("ALL (registered)", "72h", 0.5), {})
    lines += ["", "REGISTERED PREDICTIONS",
              f"  N1 monitoring_tag 72h >= +150bp both halves: tune {m.get('tune', np.nan) * 1e4:+.0f} / hold {m.get('hold', np.nan) * 1e4:+.0f}",
              f"  N2 launchpool / seed_tag 7d >= +500bp, worst <= -50%: " + ", ".join(
                  f"{x.get('mean', np.nan) * 1e4:+.0f}bp worst {x.get('worst', np.nan) * 100:+.0f}%" for x in lp),
              f"  N3 combined 72h stop 50% positive both halves: tune {al.get('tune', np.nan) * 1e4:+.0f} / hold {al.get('hold', np.nan) * 1e4:+.0f}"]
    txt = "\n".join(lines)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

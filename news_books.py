"""TWO MORE BOOKS FOR THE FINAL MACHINE: the NEWS book and the NASDAQ dip-buy (2026-10-17, docs/26 step 1)

backtest/all_books.py: of every book we have, these two pay in the machine's worst months (news +1.9%, ndx_dip +1.0% on
average in its worst 20%), correlate ~0 with the rest, and lift the $300 typical year $3,774 / $5,494 -> $4,435 / $9,838
(tune / holdout) with the falls a little shallower. Both are CANDIDATES (the news types were chosen after looking); they
run here on paper, beside the final machine, as every book did before money.

NEWS BOOK (news/entry.py, news/score.py: +316 / +267bp a trade, 67% won, worst -36%)
    SOURCE   Binance's public announcement channel, t.me/s/binance_announcements, read every poll (the VM reaches t.me;
             this PC does not). The FIRST read only records the newest message id - nothing old is traded.
    EVENTS   news/enrich.py's rules: "adds_products" (Binance adds a token to Earn / Convert / Margin / Futures) and
             "monitoring_tag"; its first 3 coins that have a Binance USDT perp (BTC excluded).
    ENTRY    15 minutes after the headline: SHORT the coin, LONG the same notional of BTC, each leg 1/10 of equity
             (K_NEWS), at most 10 trades open, one per coin. A signal that cannot be filled within 60 minutes of its due
             time (no price) is dropped.
    EXIT     the coin at +25% from entry (stop), at -20% (take-profit), or 72 hours - whichever first, checked each poll
             on the live price (the backtest checked 1-minute bars; a poll every 2 minutes fills a little worse).
    COSTS    6bp a side on each leg (SIDE_FEE); funding on both legs at exit (a short receives what a long pays).
NDX DIP BOOK (backtest/ndx_capit.py: RSI(2) < 10, +0.95% a trade, 12 a year, both halves; all_books.py: +10%/yr, fall 5%)
    PRICE    Binance's QQQUSDT perp (tracks the NASDAQ close, corr 0.9993); the "daily close" is its price at 16:00
             New York on weekdays, from its 1h bars.
    RULE     RSI(2) of those closes under 10 -> BUY at the next poll (1x equity, K_NDX); out at the first close above the
             5-day average, or after 10 trading days. One position at a time.

    tests/test_news_books.py: offline, on a fake channel page and fake prices.
"""
from __future__ import annotations

import html
import re
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

K_NEWS, NEWS_SLOTS = 1.0, 10
NEWS_DELAY_MS, NEWS_STALE_MS, NEWS_HOLD_MS = 15 * 60_000, 60 * 60_000, 72 * 3_600_000
NEWS_STOP, NEWS_TP = 0.25, 0.20
NEWS_TYPES = ("adds_products", "monitoring_tag")
CHANNEL = "binance_announcements"
K_NDX, NDX_SYM, NDX_RSI, NDX_MAX_DAYS = 1.0, "QQQUSDT", 10.0, 10
NDX_LATE_MS = 3 * 3_600_000      # buy only within 3h of the US close (a restart must not buy a stale signal; exits always go)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
NY = ZoneInfo("America/New_York")


def fresh() -> dict:
    return dict(news=dict(last_id=None, pending={}, open={}, taken=0, dropped=0, seen=0),
                ndx=dict(open=None, last_close_day=None, taken=0))


def ensure(st: dict) -> dict:
    """A state saved before these books existed gets their keys (the VM's final machine has been running since 10-09)."""
    fin = st.setdefault("fin", {})
    for k, v in fresh().items():
        fin.setdefault(k, v)
    return fin


def log(m: str):
    import combo_paper as cp
    cp.log(m)


# ---------------------------------------------------------------- the channel (public page, no login)

def read_channel(channel: str = CHANNEL) -> list:
    """[(id, ts_seconds, text)] of the newest ~20 messages; [] if the page cannot be read."""
    try:
        h = urllib.request.urlopen(urllib.request.Request(f"https://t.me/s/{channel}", headers=UA), timeout=20) \
            .read().decode("utf-8", "replace")
    except Exception:
        return []
    out = []
    for blk in re.split(r'<div class="tgme_widget_message_wrap', h)[1:]:
        m_id = re.search(r'data-post="[^/]+/(\d+)"', blk)
        m_t = re.search(r'<time datetime="([^"]+)"', blk)
        if not (m_id and m_t):
            continue
        txt = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', blk, re.S)
        t = re.sub(r"<br\s*/?>", "\n", txt.group(1)) if txt else ""
        out.append((int(m_id.group(1)), datetime.fromisoformat(m_t.group(1)).timestamp(),
                    html.unescape(re.sub(r"<[^>]+>", "", t)).strip()))
    return out


def universe(symbols) -> dict:
    """Ticker -> Binance USDT perp symbol, as news/enrich.universe does from the archive (1000-prefixed perps too)."""
    out = {}
    for s in symbols:
        if not s.endswith("USDT"):
            continue
        base = s[:-4]
        for pre in ("1000000", "1000", "1M"):
            if base.startswith(pre) and len(base) > len(pre) + 1:
                out.setdefault(base[len(pre):], s)
        out.setdefault(base, s)
    return out


def classify(text: str, U: dict):
    """(event type, coins) by news/enrich.py's own rules - the ones the backtest was measured on."""
    from news.enrich import coins, etype
    et = etype(text)
    if et not in NEWS_TYPES:
        return et, []
    return et, [c for c in coins(text, CHANNEL, U) if c != "BTCUSDT"][:3]


# ---------------------------------------------------------------- the news book

def _pnl(p, px_c, px_b, fund, now_ms):
    fc = fund(p["coin"], p["t_ms"], now_ms)
    fb_ = fund("BTCUSDT", p["t_ms"], now_ms)
    pnl = p["q_coin"] * (px_c - p["e_coin"]) - p["q_coin"] * p["e_coin"] * fc \
        + p["q_btc"] * (px_b - p["e_btc"]) - p["q_btc"] * p["e_btc"] * fb_
    return pnl


def news_poll(st: dict, prices: dict, now_ms: int, rec=None, fund=None, read=read_channel, side_fee=6.0 / 1e4):
    fin = ensure(st)
    nb = fin["news"]
    fund = fund or (lambda s, a, b: 0.0)
    # 1. exits first, on the live price
    for key, p in list(nb["open"].items()):
        px_c, px_b = prices.get(p["coin"]), prices.get("BTCUSDT")
        if not px_c or not px_b:
            continue
        move = px_c / p["e_coin"] - 1
        eps = 1e-9                                 # 0.80 / 1.0 - 1 is -0.19999999999999996
        why = ("stop" if move >= NEWS_STOP - eps else "take_profit" if move <= -NEWS_TP + eps
               else "time" if now_ms - p["t_ms"] >= NEWS_HOLD_MS else None)
        if why is None:
            continue
        pnl = _pnl(p, px_c, px_b, fund, now_ms)
        fee = (abs(p["q_coin"]) * px_c + abs(p["q_btc"]) * px_b) * side_fee
        st["equity"] += pnl - fee
        cum = st.setdefault("cum", {})
        cum["news"] = cum.get("news", 0.0) + pnl
        cum["fees"] = cum.get("fees", 0.0) + fee
        nb["open"].pop(key)
        log(f"NEWS CLOSE {p['coin']} ({why}, {p['etype']}): coin {move:+.1%}, P&L {pnl - fee:+.2f} -> account {st['equity']:.2f}")
        if rec:
            rec(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}", book="news", symbol=p["coin"],
                     entry=f"{p['e_coin']:.8g}", exit=f"{px_c:.8g}", ret=f"{-move:.5f}", pnl=f"{pnl - fee:.4f}", why=why,
                     equity=f"{st['equity']:.4f}"))
    # 2. new messages -> pending signals
    msgs = read()
    if msgs:
        top = max(m[0] for m in msgs)
        if nb["last_id"] is None:
            nb["last_id"] = top                    # first read: remember where we are, trade nothing old
            log(f"NEWS: watching {CHANNEL} from message {top}")
        else:
            U = universe(prices)
            for mid, ts, text in sorted(msgs):
                if mid <= nb["last_id"]:
                    continue
                nb["seen"] += 1
                et, cs = classify(text, U)
                for c in cs:
                    nb["pending"][f"{mid}:{c}"] = dict(coin=c, etype=et, due_ms=int(ts * 1000) + NEWS_DELAY_MS,
                                                     headline=text.split("\n")[0][:120])
                    log(f"NEWS SIGNAL {c} ({et}): '{text.split(chr(10))[0][:80]}' - short vs BTC at "
                        f"{datetime.fromtimestamp(ts + NEWS_DELAY_MS / 1000, timezone.utc):%H:%M} UTC")
            nb["last_id"] = max(nb["last_id"], top)
    # 3. due signals -> trades
    for key, s in sorted(nb["pending"].items(), key=lambda kv: kv[1]["due_ms"]):
        if now_ms < s["due_ms"]:
            continue
        px_c, px_b = prices.get(s["coin"]), prices.get("BTCUSDT")
        held = any(p["coin"] == s["coin"] for p in nb["open"].values())
        if now_ms - s["due_ms"] > NEWS_STALE_MS or held:
            nb["pending"].pop(key)
            nb["dropped"] += 1
            continue
        if not px_c or not px_b or len(nb["open"]) >= NEWS_SLOTS:
            continue                              # wait (up to NEWS_STALE_MS) for a price or a free slot
        usd = K_NEWS * st["equity"] / NEWS_SLOTS
        nb["open"][key] = dict(coin=s["coin"], etype=s["etype"], t_ms=now_ms, e_coin=px_c, e_btc=px_b,
                               q_coin=-usd / px_c, q_btc=usd / px_b)
        fee = 2 * usd * side_fee
        st["equity"] -= fee
        st.setdefault("cum", {})["fees"] = st["cum"].get("fees", 0.0) + fee
        nb["pending"].pop(key)
        nb["taken"] += 1
        log(f"NEWS OPEN short {s['coin']} at {px_c:.6g} / long BTC at {px_b:.6g}, ${usd:.2f} a leg ({s['etype']})")


# ---------------------------------------------------------------- the NASDAQ dip book

def ny_closes(h1: pd.DataFrame) -> pd.Series:
    """Weekday closes at 16:00 New York from 1h bars (t = bar OPEN, ms; c = close) - the bar that ENDS at 16:00."""
    end = pd.to_datetime(h1.t + 3_600_000, unit="ms", utc=True).dt.tz_convert(NY)
    m = (end.dt.hour == 16) & (end.dt.minute == 0) & (end.dt.weekday < 5)
    return pd.Series(h1.c[m].to_numpy(float), index=end[m].dt.strftime("%Y-%m-%d").to_numpy())


def rsi2(c: np.ndarray) -> float:
    d = np.diff(np.asarray(c, float))
    if len(d) < 2:
        return 50.0
    up = pd.Series(np.where(d > 0, d, 0.0)).ewm(alpha=1 / 2, adjust=False).mean().iloc[-1]
    dn = pd.Series(np.where(d < 0, -d, 0.0)).ewm(alpha=1 / 2, adjust=False).mean().iloc[-1]
    return 100.0 if dn == 0 else float(100 - 100 / (1 + up / dn))


def bars1h(sym: str, limit: int = 600) -> "pd.DataFrame | None":
    try:
        import json
        with urllib.request.urlopen(f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}&interval=1h&limit={limit}",
                                    timeout=20) as r:
            k = json.loads(r.read().decode())
    except Exception:
        return None
    return pd.DataFrame([[int(x[0]), float(x[4])] for x in k], columns=["t", "c"])


def ndx_poll(st: dict, prices: dict, now_ms: int, rec=None, fund=None, get1h=bars1h, side_fee=6.0 / 1e4):
    fin = ensure(st)
    nd = fin["ndx"]
    fund = fund or (lambda s, a, b: 0.0)
    h1 = get1h(NDX_SYM)
    if h1 is None or not len(h1):
        return
    closed = h1[h1.t + 3_600_000 <= now_ms]
    cl = ny_closes(closed)
    if len(cl) < 10:
        return
    day = cl.index[-1]
    if nd["last_close_day"] == day:
        return                                    # act once per new US close
    nd["last_close_day"] = day
    c = cl.to_numpy()
    px = prices.get(NDX_SYM) or float(c[-1])
    p = nd["open"]
    if p is not None:
        p["days"] += 1
        sma5 = float(np.mean(c[-5:]))
        if c[-1] > sma5 or p["days"] >= NDX_MAX_DAYS:
            f = fund(NDX_SYM, p["t_ms"], now_ms)
            pnl = p["qty"] * (px - p["entry"]) - p["qty"] * p["entry"] * f
            fee = p["qty"] * px * side_fee
            st["equity"] += pnl - fee
            cum = st.setdefault("cum", {})
            cum["ndx"] = cum.get("ndx", 0.0) + pnl
            cum["fees"] = cum.get("fees", 0.0) + fee
            why = "above_sma5" if c[-1] > sma5 else "max_days"
            log(f"NDX CLOSE {NDX_SYM} at {px:.6g} ({why}): {px / p['entry'] - 1:+.2%}, P&L {pnl - fee:+.2f}")
            if rec:
                rec(dict(ts=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}", book="ndx", symbol=NDX_SYM,
                         entry=f"{p['entry']:.8g}", exit=f"{px:.8g}", ret=f"{px / p['entry'] - 1:.5f}",
                         pnl=f"{pnl - fee:.4f}", why=why, equity=f"{st['equity']:.4f}"))
            nd["open"] = None
        return
    r = rsi2(c[-30:])
    close_ms = int(pd.Timestamp(day + " 16:00", tz=NY).tz_convert("UTC").timestamp() * 1000)
    if r < NDX_RSI and now_ms - close_ms > NDX_LATE_MS:
        log(f"NDX: RSI(2) {r:.1f} at the {day} close, but {(now_ms - close_ms) / 3_600_000:.1f}h late - not bought "
            f"(the backtest buys AT the close)")
        return
    if r < NDX_RSI:
        usd = K_NDX * st["equity"]
        nd["open"] = dict(qty=usd / px, entry=px, t_ms=now_ms, days=0, rsi=r)
        fee = usd * side_fee
        st["equity"] -= fee
        st.setdefault("cum", {})["fees"] = st["cum"].get("fees", 0.0) + fee
        nd["taken"] += 1
        log(f"NDX BUY {NDX_SYM} at {px:.6g}: RSI(2) {r:.1f} at the {day} close, ${usd:.2f}")


# ---------------------------------------------------------------- what the books hold, and their status

def targets(st: dict) -> dict:
    fin, out = st.get("fin") or {}, {}
    for p in (fin.get("news") or {}).get("open", {}).values():
        out[p["coin"]] = out.get(p["coin"], 0.0) + p["q_coin"]
        out["BTCUSDT"] = out.get("BTCUSDT", 0.0) + p["q_btc"]
    p = (fin.get("ndx") or {}).get("open")
    if p:
        out[NDX_SYM] = out.get(NDX_SYM, 0.0) + p["qty"]
    return out


def status(st: dict):
    fin, c = st.get("fin") or {}, st.get("cum", {})
    nb, nd = fin.get("news"), fin.get("ndx")
    if nb:
        print(f"    news    ${c.get('news', 0):+.2f} | {len(nb['open'])} open ({', '.join(p['coin'][:-4] for p in nb['open'].values())}), "
              f"{len(nb['pending'])} pending, {nb['taken']} taken, {nb['dropped']} dropped, {nb['seen']} messages read since "
              f"id {nb['last_id']}")
    if nd:
        o = nd["open"]
        print(f"    ndx     ${c.get('ndx', 0):+.2f} | {'holding QQQ since ' + str(o['days']) + ' closes' if o else 'flat'}, "
              f"{nd['taken']} taken, last close {nd['last_close_day']}")

"""SENTIMENT ENGINE, phase B: what each message is about - event type, coins, first report (2026-10-16, docs/25)

Input: strategy_analysis/data/news/tg/*.jsonl (news/tg_history.py). Output: strategy_analysis/data/news/events.parquet,
one row per EVENT (the same story from several channels is one event, at its FIRST timestamp), with:
    t (UTC), channel, text, views, etype (event type), coins (Binance perp symbols, '' = market-wide), n_sources
EVENT TYPES are rules, checked in order (the first that matches wins) - the tone models cannot see them: FinBERT reads
"Binance will delist X" as 93% neutral and CryptoBERT as leaning bullish (sanity check 2026-10-16).
COINS: tickers written as (XXX), $XXX, XXX/USDT, XXXUSDT or XXX-USDT, and - in exchange titles - bare upper-case tickers
after list / delist verbs; kept only if Binance has (had) a USDT perp for them (strategy_analysis/data/perps), so common
words do not become coins. 1000-prefixed perps (1000PEPE) map from the plain ticker.
NOTE: written with the Write tool - a first version patched through a bash heredoc lost every regex word boundary
(CLAUDE.md s3 trap), so "apr" matched inside words and most events fell into noise.

    python -m news.enrich
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TG = ROOT / "strategy_analysis" / "data" / "news" / "tg"
PERPS = ROOT / "strategy_analysis" / "data" / "perps"
OUT = ROOT / "strategy_analysis" / "data" / "news" / "events.parquet"
EXCHANGE = {"binance_announcements", "Bybit_Announcements", "OKXAnnouncements", "Bitget_Announcements", "BWEnews"}
EXCH_TYPES = {"monitoring_tag", "delist_futures", "delist_pairs", "delist", "seed_tag", "launchpool", "new_pairs",
              "adds_products", "list_futures", "list_spot"}


def R(p):
    return re.compile(p, re.I)


RULES = [
    ("monitoring_tag", R(r"monitoring tag")),
    ("delist_futures", R(r"(futures|usd[sⓢ]?-?m|perpetual).{0,40}\bdelist|\bdelist.{0,60}(perpetual|futures contract|usd[sⓢ]?-?m)")),
    ("delist_pairs", R(r"remov\w* (of )?(spot |margin )?trading pairs|\bdelist.{0,40}(margin|isolated|cross|trading pairs?|/)")),
    ("delist", R(r"\bwill delist\b|\bdelisting\b|\bdelists?\b|\bcease trading\b|will remove .{0,30}token|discontinue .{0,30}support")),
    ("hack", R(r"\bhack(ed|er|ers|ing)?\b|\bexploit|\bdrained\b|\bstolen\b|\battack(ed)?\b|\bcompromised\b|security incident|rug ?pull")),
    ("seed_tag", R(r"\bseed tag\b")),
    ("launchpool", R(r"\blaunchpool\b|\blaunchpad\b|\bmegadrop\b|hodler airdrop")),
    ("noise", R(r"^\W*(binance )?(earn|pay|square|alpha points|wallet)\b|\bapr\b|\bapy\b|\bpromo|\bgiveaway|red packet|"
                r"\bcompetition\b|\btournament\b|\bvoucher|prize pool|\brewards?\b|\bcampaign\b|share \$|\bwin\b")),
    ("new_pairs", R(r"\badds? .{0,120}trading pairs|new trading pairs")),
    ("adds_products", R(r"\badd\w* .{0,60}\bon (earn|buy crypto|convert|margin|futures|cross margin)")),
    ("list_futures", R(r"\b(launch|list)\w*.{0,60}(usd[sⓢ]?-?m|perpetual)|(futures|perpetual).{0,30}(will launch|launch(es)?)")),
    ("list_spot", R(r"\bwill list\b|\blists?\b|\blisting\b|new listing|now available|opens trading")),
    ("etf", R(r"\betfs?\b")),
    ("regulation", R(r"\bsec\b|\blawsuit|\bsued?\b|\bregulat|\bcftc\b|\bdoj\b|\bindict|\bban(s|ned)?\b|\bsanction|\bsubpoena|\bcharges\b")),
    ("unlock", R(r"\bunlock")),
    ("macro", R(r"\bcpi\b|\bppi\b|\bpayrolls\b|\bnfp\b|\bfomc\b|\bfed\b|\brate (cut|hike)|\bjobless\b|\bgdp\b|\bpowell\b|treasury yields?")),
    ("whale", R(r"transferred from|transferred to|\bwhale\b|\bminted\b|burned at")),
    ("treasury_buy", R(r"\b(buys?|bought|acquir\w*|adds?) .{0,30}\b(btc|bitcoin|eth|ether)\b|microstrategy|\bsaylor\b|strategy (buys|bought)")),
    ("partnership", R(r"\bpartner|\bintegrat|\badopt|\bcollaborat")),
    ("noise", R(r"\bearn\b|\bstaking\b|simple earn|\bvip\b|\bmaintenance\b|network upgrade|hard fork|\bairdrop|\bwebinar\b|\bama\b|\bquiz\b|"
                r"\breferral|fee (discount|rebate)|zero.fee|\bloans?\b|\bcollateral\b|\bconvert\b|\bwallet\b|dual investment")),
]
STOP = {"USD", "USDT", "USDC", "BUSD", "FDUSD", "TUSD", "EUR", "TRY", "BRL", "BIDR", "AUD", "GBP", "UTC", "CEO", "SEC", "ETF",
        "NFT", "API", "AND", "THE", "FOR", "NEW", "WILL", "CPI", "PPI", "GDP", "FED", "USA", "US", "EU", "UK", "AI", "DEX", "CEX",
        "IPO", "OTC", "APY", "APR", "VIP", "KYC", "P2P", "ATH", "TVL", "DAO", "FOMC", "NFP", "BREAKING", "JUST", "IN", "UPDATE",
        "NOTICE", "ALERT", "LATEST", "BULLISH", "BEARISH", "SPOT", "MARGIN", "FUTURES", "PERP", "SEED", "TAG", "HODLER", "M"}
TICKER_RX = [re.compile(p) for p in (r"\(([A-Z0-9]{2,12})\)", r"\$([A-Z][A-Z0-9]{1,11})\b", r"\b([A-Z0-9]{2,12})[/-]?USDT\b",
                                     r"\b([A-Z0-9]{2,12})/(?:BUSD|USDC|FDUSD|BTC|ETH|TRY)\b")]
VERB_RX = re.compile(r"(?:delist|list|launch|adds?|remov\w*|monitoring tag (?:on|to|include))\s+(.{0,160})", re.I)
BARE_RX = re.compile(r"\b([A-Z][A-Z0-9]{1,11})\b")


def universe():
    out = {}
    for p in PERPS.glob("*_1h.csv.gz"):
        s = p.name.split("_")[0]
        if not s.endswith("USDT"):
            continue
        base = s[:-4]
        for pre in ("1000000", "1000", "1M"):
            if base.startswith(pre) and len(base) > len(pre) + 1:
                out.setdefault(base[len(pre):], s)
        out.setdefault(base, s)
    return out


def etype(text):
    head = text.split("\n")[0][:300]
    for name, rx in RULES:
        if rx.search(head):
            return name
    for name, rx in RULES:
        if name != "noise" and rx.search(text[:600]):
            return name
    return "other"


MAJORS = {"bitcoin": "BTC", "ethereum": "ETH", "ether": "ETH", "solana": "SOL", "ripple": "XRP", "dogecoin": "DOGE",
          "cardano": "ADA", "polkadot": "DOT", "avalanche": "AVAX", "chainlink": "LINK", "litecoin": "LTC", "polygon": "POL",
          "tron": "TRX", "shiba inu": "SHIB", "uniswap": "UNI", "aave": "AAVE", "arbitrum": "ARB", "optimism": "OP",
          "cosmos": "ATOM", "toncoin": "TON", "aptos": "APT", "filecoin": "FIL", "stellar": "XLM", "monero": "XMR",
          "tezos": "XTZ", "algorand": "ALGO", "hedera": "HBAR", "internet computer": "ICP", "worldcoin": "WLD",
          "celestia": "TIA", "injective": "INJ", "fantom": "FTM", "terra": "LUNA", "ftx token": "FTT", "curve finance": "CRV",
          "lido": "LDO", "pancakeswap": "CAKE", "sushiswap": "SUSHI", "bitcoin cash": "BCH", "ethereum classic": "ETC",
          "binance coin": "BNB", "eos": "EOS", "zcash": "ZEC", "dash": "DASH", "pepe": "PEPE", "bonk": "BONK"}
COMMON = {"bitcoin", "global", "world", "network", "protocol", "finance", "chain", "token", "coin", "smart", "digital",
          "games", "gaming", "labs", "capital", "union", "power", "energy", "fusion", "origin", "spell", "magic", "gold"}


LEAD = {"add", "adds", "about", "claim", "lists", "list", "listing", "bitget", "binance", "okx", "bybit", "kucoin", "gate",
        "introducing", "will", "the", "new", "trade", "earn", "buy", "sell", "support", "supports", "launch", "launches",
        "all", "on", "for", "and", "with", "of", "to", "in", "at", "by", "spot", "futures", "margin", "perpetual", "usdt"}


def learn_names(texts, U, corpus=()):
    """'Arbitrum (ARB)' in exchange announcements -> {'Arbitrum': 'ARBUSDT'} (case kept). Leading verbs / exchange names
    are stripped; a name that maps to two tickers is dropped; and a name written in lower case more often than
    capitalised across all headlines (`corpus`) is an ordinary word ('maker', 'crypto', 'stable') and is dropped."""
    seen = {}
    rx = re.compile(r"\b([A-Z][A-Za-z0-9]+(?: [A-Z][A-Za-z0-9]+){0,2}) \(([A-Z0-9]{2,12})\)")
    for t in texts:
        for name, tk in rx.findall(t[:400]):
            w = name.split()
            while w and w[0].lower() in LEAD:
                w = w[1:]
            name = " ".join(w)
            if len(name) < 5 or name.lower() in COMMON or tk not in U:
                continue
            seen.setdefault(name, set()).add(U[tk])
    names = {n: next(iter(v)) for n, v in seen.items() if len(v) == 1}
    if corpus:
        # one pass over every headline: counts of each 1-3 word phrase exactly as written (a per-name regex scan of
        # all headlines took tens of minutes)
        grams = Counter()
        wanted = {len(n.split()) for n in names}
        for h in corpus:
            w = re.findall(r"[A-Za-z0-9]+", h)
            for k in wanted:
                for i in range(len(w) - k + 1):
                    grams[" ".join(w[i:i + k])] += 1
        names = {n: s for n, s in names.items() if grams.get(n.lower(), 0) <= grams.get(n, 0)}
    learned = re.compile(r"\b(" + "|".join(sorted(map(re.escape, names), key=len, reverse=True)) + r")\b") if names else None
    majors = {n: U[tk] for n, tk in MAJORS.items() if tk in U}
    major_rx = re.compile(r"\b(" + "|".join(sorted(map(re.escape, majors), key=len, reverse=True)) + r")\b", re.I)
    return (names, learned, majors, major_rx)


def coins(text, channel, U, names=None):
    head = text.split("\n")[0][:400]
    found = []
    for rx in TICKER_RX:
        found += rx.findall(head)
    if channel in EXCHANGE:
        m = VERB_RX.search(head)
        if m:
            found += BARE_RX.findall(m.group(1))
    elif names is not None:                        # media headlines name coins by name, not ticker
        learned, l_rx, majors, m_rx = names
        if l_rx is not None:
            found += [learned[n][:-4] for n in l_rx.findall(head) if n in learned]          # case-sensitive
        found += [majors[n.lower()][:-4] for n in m_rx.findall(head) if n.lower() in majors]
    out = []
    for t in found:
        t = t.upper()
        if t in STOP or t.isdigit():
            continue
        s = U.get(t)
        if s and s not in out:
            out.append(s)
    return out


def norm(text):
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"https?://\S+", "", text.lower()))[:80]


def main():
    U = universe()
    rows, raw = [], []
    seen_by = {}
    for f in sorted(TG.glob("*.jsonl")):
        ch = f.stem.split("__")[0]                 # news/tg_fast.py's id segments are the same channel
        seen = seen_by.setdefault(ch, set())
        for line in f.open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if "id" not in r or r["id"] in seen or not r.get("text"):
                continue
            seen.add(r["id"])
            raw.append((ch, r))
    names = learn_names([r["text"] for ch, r in raw if ch in EXCHANGE], U,
                        corpus=[r["text"].split("\n")[0][:300] for ch, r in raw if ch not in EXCHANGE])
    for ch, r in raw:
        et = etype(r["text"])
        cs = coins(r["text"], ch, U, names) if et != "noise" else []
        rows.append(dict(t=pd.Timestamp(r["ts"], unit="s"), channel=ch, mid=r["id"], text=r["text"][:600],
                         views=r.get("views"), etype=et, coins=",".join(cs[:8]), key=norm(r["text"])))
    print(f"coin names learned: {len(names[0]):,}")
    D = pd.DataFrame(rows).sort_values("t", kind="stable").reset_index(drop=True)
    # one story, many channels: same event type + same coins within 6 h (coin events), or the same opening text
    # within 2 h (market-wide) -> one event at its FIRST timestamp
    first = [True] * len(D)
    nsrc = [1] * len(D)
    last = {}
    tt = D.t.astype("int64").to_numpy() // 10**9
    et_, co_, ke_ = D.etype.to_numpy(), D.coins.to_numpy(), D.key.to_numpy()
    for i in range(len(D)):
        if et_[i] == "noise":
            continue
        # merge by coin only for exchange events (one listing / delisting / tag reported by several channels); media
        # stories about the same coin are different stories - they merge only when their opening text is the same.
        # (Merging every coin-tagged story by coin for 6 h swallowed 51k of 143k messages once media got coin names.)
        by_coin = co_[i] and et_[i] in EXCH_TYPES
        k = (et_[i], co_[i]) if by_coin else ("text", ke_[i])
        win = 6 * 3600 if by_coin else 2 * 3600
        j = last.get(k)
        if j is not None and tt[i] - tt[j] <= win:
            first[i] = False
            nsrc[j] += 1
        else:
            last[k] = i
    D["first"], D["n_sources"] = first, nsrc
    E = D[D["first"] & (D.etype != "noise")].drop(columns=["first", "key"]).reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    E.to_parquet(OUT)
    print(f"{len(D):,} messages from {D.channel.nunique()} channels -> {len(E):,} events "
          f"({(D.etype == 'noise').sum():,} promo / noise dropped, {(~D['first']).sum():,} repeats merged)")
    print(E.groupby("etype").agg(events=("t", "size"), with_coin=("coins", lambda s: (s != "").sum())).sort_values("events", ascending=False))


if __name__ == "__main__":
    main()

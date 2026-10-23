"""SENTIMENT ENGINE: WHICH WORDS MOVE PRICES - a keyword table learned from history, instead of a paid AI reader (2026-10-23)

THE USER (2026-10-23): "we will do something about how to avoid api cost - we can check on previous years how each type
of news or keywords affect the market". An AI headline reader costs per headline; a table of words and the moves that
followed them costs nothing to run. This learns that table from the 150,789 headlines already measured
(news/impact.py -> impact_obs.parquet: each event's EXCESS move over the coin's own normal drift, from the first full
hour after the headline) and asks whether it predicts anything the event types (news/enrich.py) do not.

TWO SETS
  COIN    headlines naming altcoins (18,886 events, 2020-26): the coin's excess move vs BTC at 24h / 72h / 7d
  MARKET  headlines naming no altcoin (BTC itself): BTC's excess move at 1h / 4h / 24h, collapsed to ONE row per entry
          hour (an hour "has" a word if any headline in it does) - 107k headlines share ~40k hours
WORDS   lower-case words of 3+ letters and their two-word pairs, after dropping stop words, numbers, every perp's ticker
        and the major coin names; a word must appear in >= 40 coin events (>= 150 market hours) and no single coin may
        make up more than half its events (else it is the coin's name, not news)
PASS    t >= 2 on BOTH halves (first 60% / last 40% of the set's events by time), same sign, at some horizon
NULL    the same count after shifting the outcome series against the words by a random offset (circular, >= 10% of the
        set away; 20 shifts): it keeps the clustering of news and of overlapping returns, so the pass count is compared
        with what chance gives on these very words
USE     a SCORE learned on the tune half only (each word's mean move, shrunk to 0 by n / (n + 30); an event's score = the
        mean over its words), read on the holdout: rank IC, and the top / bottom 10% of scores traded at 12bp

REGISTERED BEFORE THE RUN (2026-10-23)
  K1 COIN: the words that pass number no more than twice the null's average.
  K2 COIN: the words that pass mostly re-find what the event types already know - at least half of their events are
     exchange listing / product / tag notices (list_spot, list_futures, adds_products, new_pairs, monitoring_tag,
     launchpool, seed_tag).
  K3 COIN: the tune-half score's holdout IC at 72h on events OUTSIDE those types is small: |IC| < 0.02.
  K4 MARKET: the pass count is inside the null's 95th percentile at every horizon.

RESULT (2026-10-23, logs/news_keywords.txt) - DEAD: words carry nothing beyond the event types. K1 K3 K4 RIGHT, K2 WRONG.
  COIN (18,886 events, 1,493 words): 3 / 10 / 27 words pass at 24h / 72h / 7d against 4.0 / 9.4 / 32.2 on shifted
  outcomes - chance. A score learned on 2020-24 reads holdout IC +0.025 (all) and -0.005 outside the known exchange
  types; trading its top / bottom tenth loses -63 / -156bp a trade net. MARKET (42,918 hours, 2,526 words): 4 / 5 / 3
  pass against 2.5 / 3.0 / 5.2 - chance. The one coherent cluster ('margin', 'convert', 'add') IS the adds_products
  type the news book already trades (-968bp at 7d when tagged); the untagged margin / convert / earn notices on exchange
  channels move -129bp at 72h (t -0.8), so the classifier misses nothing that pays. K2 WRONG only because most passing
  words are generic chance words ('while', 'within', 'both'), not exchange words.
  So the free rules in news/enrich.py already hold what headlines carry. A paid AI reader would have to find a NEW kind
  of event to earn its cost; three readings of the text (FinBERT tone, Bluesky words, this table) found none.

    python -m news.keywords
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from news.enrich import MAJORS, PERPS  # noqa: E402
from news.impact import EV, OUT  # noqa: E402

LOG = ROOT / "logs" / "news_keywords.txt"
KNOWN = {"list_spot", "list_futures", "adds_products", "new_pairs", "monitoring_tag", "launchpool", "seed_tag"}
SETS = {"COIN": dict(hz=("24h", "72h", "7d"), min_n=40), "MARKET": dict(hz=("1h", "4h", "24h"), min_n=150)}
TUNE, SHRINK, FEE_BP, SHIFTS = 0.60, 30.0, 12.0, 20
STOP = set("""the and for with from that this are was were has have had will its into over after amid about than more
than just new says said say who what when how why not but you your our their they his her she him them out off via per
all any can could would should may might also now yet still today week weeks day days year years month months time
first last next one two three top big high low back up down here there been being does did done get got make made
link read full update updates breaking news report reports reported according source sources""".split())


def tokens(text: str, drop: set) -> set:
    t = re.sub(r"https?://\S+", " ", text.lower())
    w = [x for x in re.findall(r"[a-z][a-z0-9]+", t) if len(x) >= 3 and x not in STOP and x not in drop
         and not x.isdigit()]
    return set(w) | {a + " " + b for a, b in zip(w, w[1:])}


def events():
    """One row per event (its coins averaged), split into the coin set and the market set (collapsed to hours)."""
    O = pd.read_parquet(OUT)
    E = pd.read_parquet(EV)
    hz = sorted({h for s in SETS.values() for h in s["hz"]})
    coin = O[~O.market].groupby("eid").agg(t=("t", "first"), top=("coin", "first"), **{h: (h, "mean") for h in hz})
    mk = O[O.market].groupby("eid").agg(t=("t", "first"), **{h: (h, "mean") for h in hz})
    coin = coin.join(E[["text", "etype"]]).sort_values("t", kind="stable")
    mk = mk.join(E[["text", "etype"]])
    mk["hour"] = mk.t.dt.floor("h")
    return coin, mk


def word_matrix(texts: list, drop: set, min_n: int, owner=None):
    """Sparse events x words (binary) for words in >= min_n events (and, with owner, no coin > half of them)."""
    from scipy import sparse
    toks = [tokens(t, drop) for t in texts]
    cnt = Counter(w for s in toks for w in s)
    keep = sorted(w for w, n in cnt.items() if n >= min_n)
    if owner is not None:
        by = {w: Counter() for w in keep}
        ks = set(keep)
        for s, o in zip(toks, owner):
            for w in s & ks:
                by[w][o] += 1
        keep = [w for w in keep if by[w].most_common(1)[0][1] <= 0.5 * cnt[w]]
    ix = {w: i for i, w in enumerate(keep)}
    r, c = [], []
    for i, s in enumerate(toks):
        for w in s:
            j = ix.get(w)
            if j is not None:
                r.append(i)
                c.append(j)
    X = sparse.csr_matrix((np.ones(len(r)), (r, c)), shape=(len(texts), len(keep)))
    return X, keep


def stats(X, y, half):
    """Per word: n, mean, t on the whole set and on each half (y may hold NaN)."""
    ok = np.isfinite(y)
    out = {}
    for name, m in (("all", ok), ("tune", ok & ~half), ("hold", ok & half)):
        yy = np.where(m, y, 0.0)
        n = np.asarray(X.T @ m.astype(float)).ravel()
        s1 = np.asarray(X.T @ yy).ravel()
        s2 = np.asarray(X.T @ (yy * yy)).ravel()
        mean = np.divide(s1, n, out=np.zeros_like(s1), where=n > 0)
        var = np.divide(s2 - n * mean ** 2, n - 1, out=np.zeros_like(s1), where=n > 1)
        t = np.divide(mean, np.sqrt(np.maximum(var, 1e-30) / np.maximum(n, 1)), out=np.zeros_like(s1), where=n > 2)
        out[name] = (n, mean, t)
    return out


def passes(st) -> np.ndarray:
    st_t, st_h = st["tune"], st["hold"]
    return (np.sign(st_t[1]) == np.sign(st_h[1])) & (np.abs(st_t[2]) >= 2) & (np.abs(st_h[2]) >= 2)


def null_counts(X, y, half, rng) -> list:
    n = len(y)
    out = []
    for _ in range(SHIFTS):
        k = int(rng.integers(int(0.1 * n), int(0.9 * n)))
        out.append(int(passes(stats(X, np.roll(y, k), half)).sum()))
    return out


def score_test(X, y, half, words, etypes, L):
    """A score learned on the tune half only, read on the holdout."""
    from scipy.stats import spearmanr
    tu = ~half & np.isfinite(y)
    n = np.asarray(X[tu].sum(axis=0)).ravel()
    s1 = np.asarray(X[tu].T @ y[tu]).ravel()
    w = s1 / (n + SHRINK)                                       # shrunk mean move per word
    k = np.asarray(X.sum(axis=1)).ravel()
    sc = np.divide(np.asarray(X @ w).ravel(), k, out=np.full(len(y), np.nan), where=k > 0)
    res = {}
    for name, m in (("all holdout", half), ("holdout, not a known type", half & ~np.isin(etypes, list(KNOWN)))):
        mm = m & np.isfinite(y) & np.isfinite(sc)
        ic = spearmanr(sc[mm], y[mm]).correlation if mm.sum() > 30 else np.nan
        lo, hi = np.nanpercentile(sc[mm], 10), np.nanpercentile(sc[mm], 90)
        sh, lg = y[mm & (sc <= lo)] * 1e4, y[mm & (sc >= hi)] * 1e4
        tr = np.r_[-sh, lg] - FEE_BP                            # short the bottom tenth, long the top tenth
        t = tr.mean() / (tr.std(ddof=1) / np.sqrt(len(tr))) if len(tr) > 2 else 0.0
        res[name] = ic
        L.append(f"      {name:<28} n {mm.sum():>6,}  IC {ic:+.3f} | top-10% long {lg.mean():+6.0f}bp, bottom-10% short "
                 f"{-sh.mean():+6.0f}bp, both net {tr.mean():+6.0f}bp (t {t:+.2f})")
    top = np.argsort(-np.abs(w) * (n >= SHRINK))[:12]
    L.append("      the tune half's strongest words (shrunk bp): " + ", ".join(f"'{words[i]}' {w[i] * 1e4:+.0f}" for i in top))
    return res


def main():
    rng = np.random.default_rng(23)
    coin, mk = events()
    drop = {p.name.split("_")[0].replace("USDT", "").lower() for p in PERPS.glob("*USDT_*")} | set(MAJORS) | {"usdt", "usd"}
    L = [f"news/keywords.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; impact_obs.parquet (news/impact.py), "
         f"{len(drop):,} tickers / coin names dropped as words; PASS = t >= 2 on both halves, same sign", ""]
    R = {}
    for name, cfg in SETS.items():
        if name == "COIN":
            D = coin.reset_index(drop=True)
            X, words = word_matrix(D.text.fillna("").tolist(), drop, cfg["min_n"], owner=D.top.tolist())
            et = D.etype.astype(str).to_numpy()
        else:
            # one row per entry hour: the hour's words (any headline), BTC's move from that hour
            g = mk.groupby("hour")
            D = g.agg(t=("t", "first"), **{h: (h, "first") for h in cfg["hz"]}).reset_index()
            D["text"] = g.text.apply(lambda s: " | ".join(s.fillna(""))).to_numpy()
            D["etype"] = g.etype.agg(lambda s: s.mode().iat[0]).to_numpy()
            D = D.sort_values("t", kind="stable").reset_index(drop=True)
            X, words = word_matrix(D.text.tolist(), drop, cfg["min_n"])
            et = D.etype.astype(str).to_numpy()
        half = np.arange(len(D)) >= int(len(D) * TUNE)
        L += [f"{name}: {len(D):,} {'events' if name == 'COIN' else 'hours'} {D.t.min():%Y-%m} .. {D.t.max():%Y-%m}, "
              f"{len(words):,} words / pairs tested, holdout from {D.t.iloc[int(len(D) * TUNE)]:%Y-%m-%d}"]
        R[name] = {}
        for h in cfg["hz"]:
            y = D[h].to_numpy(float)
            st = stats(X, y, half)
            p = passes(st)
            nul = null_counts(X, y, half, rng)
            known = []
            for j in np.where(p)[0]:
                rows = X[:, j].nonzero()[0]
                known.append(np.isin(et[rows], list(KNOWN)).mean())
            R[name][h] = dict(n=int(p.sum()), null=float(np.mean(nul)), p95=float(np.percentile(nul, 95)),
                              known=float(np.mean(known)) if known else np.nan)
            L.append(f"   {h:>4}: {p.sum():>4} words pass (chance: {np.mean(nul):.1f} on average, 95th pct "
                     f"{np.percentile(nul, 95):.0f})" + (f"; of their events {np.mean(known) * 100:.0f}% are known exchange types"
                                                        if known else ""))
            order = np.argsort(-np.minimum(np.abs(st['tune'][2]), np.abs(st['hold'][2])) * p)[:min(int(p.sum()), 15)]
            for j in order:
                L.append(f"         '{words[j]}' n {int(st['all'][0][j]):>5}  {st['all'][1][j] * 1e4:+7.0f}bp  tune "
                         f"{st['tune'][1][j] * 1e4:+6.0f} (t {st['tune'][2][j]:+.1f}) / hold {st['hold'][1][j] * 1e4:+6.0f} "
                         f"(t {st['hold'][2][j]:+.1f})")
            if name == "COIN" and h == "72h":
                L.append("   the word SCORE, learned on the tune half (72h):")
                R["score"] = score_test(X, y, half, words, et, L)
        L.append("")
    c72, m = R["COIN"], R["MARKET"]
    k1 = all(v["n"] <= 2 * max(v["null"], 0.5) for v in c72.values())
    kn = [v["known"] for v in c72.values() if np.isfinite(v["known"])]
    k2 = bool(kn) and np.mean(kn) >= 0.5
    k3 = abs(R["score"]["holdout, not a known type"]) < 0.02
    k4 = all(v["n"] <= v["p95"] for v in m.values())
    L += ["REGISTERED PREDICTIONS",
          f"  K1 COIN passes <= 2x chance at every horizon: {[(h, v['n'], round(v['null'], 1)) for h, v in c72.items()]} -> "
          f"{'RIGHT' if k1 else 'WRONG'}",
          f"  K2 COIN passing words mostly known exchange types (>= 50% of their events): "
          f"{[round(x * 100) for x in kn]}% -> {'RIGHT' if k2 else 'WRONG' if kn else 'n/a (nothing passed)'}",
          f"  K3 COIN score holdout IC outside the known types |IC| < 0.02: {R['score']['holdout, not a known type']:+.3f} -> "
          f"{'RIGHT' if k3 else 'WRONG'}",
          f"  K4 MARKET passes inside the null's 95th pct: {[(h, v['n'], v['p95']) for h, v in m.items()]} -> "
          f"{'RIGHT' if k4 else 'WRONG'}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

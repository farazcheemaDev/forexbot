"""CENTRAL-BANK SPEECH TONE AND FOREX: hawkish / dovish words in 30 years of central bankers' speeches (2026-10-12)

THE USER (2026-10-12): "run central bank speech tone next too". The BIS publishes every central banker's speech with its
full text (backtest/fx_macro_data.py --build_speeches, 1996-2026). Banks: the Fed (Board and the regional Reserve
Banks) for USD, the ECB and the Bundesbank for EUR, the Bank of England, Bank of Japan, Reserve Bank of Australia,
Reserve Bank of New Zealand, Bank of Canada and Swiss National Bank.

TONE  a word count, fixed BEFORE any result was seen: HAWK phrases (tightening, raising rates, inflation / price
      pressures, upside risks, overheating, restrictive, vigilance, normalisation, withdrawing accommodation, elevated
      or persistent inflation, strong demand) minus DOVE phrases (accommodation, easing, rate cuts, lower rates,
      stimulus, downside risks, slack, weakness, subdued, low inflation, deflation, support for the economy, patience,
      quantitative easing / asset purchases, high unemployment), per 1,000 words, pooled over each bank's speeches in
      the trailing 4 weeks (weekly) or the month (monthly). A currency's driver is its bank's tone MINUS the Fed's.
      A speech counts from its date; the trade starts at the next period's noon fix.
SANITY  the Fed's tone should rise and fall with the US 2-year yield if the word count measures hawkishness at all.

TESTS (fx_drivers machinery, Exness costs)
    A  MOVES WITH   the change in relative tone over the same week / month against the currency's move
    B  PREDICTS     last period's change, and its level, against the next period's move
    RULES  TONE SHIFT   follow last month's change in relative tone
           TONE LEVEL   long the currency whose bank sounds more hawkish than the Fed (z over 36 months), short if dovish

REGISTERED BEFORE THE RUN (2026-10-12)
    H0  SANITY: the Fed's monthly tone correlates >= +0.2 with the US 2-year yield level.
    H1  A: the same month's change in relative tone correlates positively (>= +0.05) with most of the 7 currencies.
    H2  B: every next-week and next-month |correlation| is under 0.10.
    H3  No rule passes on Exness.

RESULT (2026-10-12 08:25 UTC, logs/fx_speeches.txt; 8,850 speeches 1996-09 .. 2026-06: ECB/Bundesbank 3,622, Fed 1,856,
BoE 816, BoJ 779, BoC 610, RBA 579, SNB 383, RBNZ 205)
    - H0 RIGHT - the word count measures something real: the Fed's monthly tone tracks the US 2-year yield (+0.45, 263
      months). The BoJ is by far the most dovish voice (-3.0 a 1,000 words against -0.5..-1.0 for the rest).
    - H1 WRONG: relative tone does NOT move with the currency in the same month (-0.08..+0.12) or week (-0.09..+0.06).
    - H2 WRONG in the interesting direction: last month's change in a bank's tone relative to the Fed leans the right way
      for the next month on 5 of 7 (NZD +0.17, CHF +0.15, CAD +0.10, EUR +0.08, GBP +0.05) - 28 correlations, several
      from thin samples (RBNZ 205 speeches).
    - H3 RIGHT, and it settles H2: traded, the lean does not hold. TONE SHIFT +0.24%/yr at Exness, tune +0.136% a month
      (t +1.0) / holdout -0.155% (t -1.1) - it flips; TONE LEVEL -0.13%/yr. Holm 0.85, 0 of 2 pass.
    Reading: central bankers' words track where rates are going (the 2-year yield), and the 2-year yield is what moves
    the currency (fx_rates2y.py) - so by the time a speech's tone can be counted, its message is already in the price.

    python -m backtest.fx_speeches
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import fx_drivers as fd  # noqa: E402
from backtest import fx_macro_data as md  # noqa: E402

LOG = ROOT / "logs" / "fx_speeches.txt"
CACHE = md.OUT / "speech_counts.csv"
CCY = fd.CCY
BANK = [("USD", r"Board of Governors of the Federal Reserve System|Federal Reserve Bank of"),
        ("EUR", r"European Central Bank|Deutsche Bundesbank"), ("GBP", r"Bank of England"), ("JPY", r"Bank of Japan"),
        ("AUD", r"Reserve Bank of Australia"), ("NZD", r"Reserve Bank of New Zealand"), ("CAD", r"Bank of Canada"),
        ("CHF", r"Swiss National Bank")]
HAWK = [r"tighten\w*", r"rais\w* (?:interest |policy |the policy )?rates?", r"rate (?:increase|increases|hike|hikes)",
        r"inflation(?:ary)? pressures?", r"price pressures?", r"upside risks?", r"overheat\w*", r"restrictive",
        r"vigilan\w*", r"normali[sz]\w*", r"withdraw\w* (?:of )?(?:monetary )?(?:stimulus|accommodation)",
        r"elevated inflation", r"persistent inflation", r"strong demand", r"higher interest rates"]
DOVE = [r"accommodati\w*", r"eas(?:e|ing) (?:monetary )?polic\w*", r"monetary easing", r"rate cuts?",
        r"cut\w* (?:interest |policy )?rates", r"lower interest rates", r"stimul\w*", r"downside risks?", r"slack",
        r"weak\w*", r"subdued", r"low inflation", r"deflation\w*", r"support (?:the )?(?:economy|recovery|growth|demand)",
        r"patien\w*", r"quantitative easing", r"asset purchases?", r"unemployment (?:remains |is )?(?:high|elevated)"]
RH = re.compile(r"\b(?:" + "|".join(HAWK) + r")\b", re.I)
RD = re.compile(r"\b(?:" + "|".join(DOVE) + r")\b", re.I)


def counts() -> pd.DataFrame:
    if CACHE.exists():
        return pd.read_csv(CACHE, parse_dates=["date"])
    rows = []
    for zf in sorted((md.OUT / "speeches").glob("speeches-*.zip")):
        z = zipfile.ZipFile(zf)
        d = pd.read_csv(z.open(z.namelist()[0]))
        for r in d.itertuples():
            desc = str(r.description)
            bank = next((c for c, pat in BANK if re.search(pat, desc)), None)
            if bank is None or not isinstance(r.text, str):
                continue
            words = len(r.text.split())
            if words < 300:
                continue
            rows.append(dict(date=pd.Timestamp(str(r.date)[:10]), ccy=bank, words=words, hawk=len(RH.findall(r.text)),
                             dove=len(RD.findall(r.text))))
        print("speeches", zf.stem, len(rows), flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(CACHE, index=False)
    return out


def tone_at(S: pd.DataFrame, starts: pd.DatetimeIndex, days: int) -> pd.DataFrame:
    """per period start: (hawk - dove) per 1,000 words over each bank's speeches dated in the `days` before the start."""
    out = {}
    for c in ["USD"] + CCY:
        s = S[S.ccy == c].sort_values("date", kind="stable")
        cw, ch, cd = np.r_[0, np.cumsum(s.words)], np.r_[0, np.cumsum(s.hawk)], np.r_[0, np.cumsum(s.dove)]
        dts = s.date.to_numpy()
        a = np.searchsorted(dts, (starts.normalize() - pd.Timedelta(days=days)).to_numpy(), "left")
        b = np.searchsorted(dts, starts.normalize().to_numpy(), "left")
        w = cw[b] - cw[a]
        out[c] = np.where(w >= 2000, ((ch[b] - ch[a]) - (cd[b] - cd[a])) / np.maximum(w, 1) * 1000, np.nan)
    return pd.DataFrame(out, index=starts)


def main():
    S = counts()
    lines = [f"backtest/fx_speeches.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; BIS central bankers' speeches "
             f"{S.date.min():%Y-%m} .. {S.date.max():%Y-%m}: " + ", ".join(f"{c} {int((S.ccy == c).sum())}" for c in ["USD"] + CCY)
             + "; tone = hawk - dove phrases per 1,000 words (a period needs >= 2,000 words of speeches)", ""]
    res_corr = {}
    for fq, days, name in (("W", 28, "WEEK (4-week window)"), ("M", 31, "MONTH")):
        starts, ret, nights = fd.grid(fq)
        T = tone_at(S, starts, days)
        if fq == "M":
            us2 = fd.asof(md.load("ust_h15.csv")["2y"], starts)
            j = pd.concat([T["USD"], us2], axis=1).dropna()
            h0 = j.iloc[:, 0].corr(j.iloc[:, 1])
            lines.append(f"SANITY: the Fed's monthly tone vs the US 2-year yield level: corr {h0:+.2f} ({len(j)} months); "
                         f"tone averages " + ", ".join(f"{c} {T[c].mean():+.2f}" for c in ["USD"] + CCY))
            lines.append("")
        rel = pd.DataFrame({c: T[c] - T["USD"] for c in CCY})
        same, last = rel.shift(-1) - rel, rel - rel.shift(1)
        lines.append(f"{name}S ({len(starts)})")
        lines.append(f"  {'':40}" + "".join(f"{c:>7}" for c in CCY))
        for nm, x in (("A same period: tone change", same), ("B next period: last change", last),
                      ("B next period: tone level", rel)):
            row = f"  {nm:40}"
            for c in CCY:
                jj = pd.concat([x[c], ret[c]], axis=1).dropna()
                r = jj.iloc[:, 0].corr(jj.iloc[:, 1]) if len(jj) > 40 else np.nan
                res_corr[(fq, nm[0], nm, c)] = r
                row += f"{r:+7.2f}"
            lines.append(row)
        lines.append("")
        if fq == "M":
            m_starts, m_ret, m_n, m_rel, m_last = starts, ret, nights, rel, last
    z = (m_rel - m_rel.rolling(36, min_periods=24).mean()) / m_rel.rolling(36, min_periods=24).std()
    rules = {"TONE SHIFT (follow last month's change)": np.sign(m_last),
             "TONE LEVEL (hawkish vs the Fed, |z| > 1)": np.sign(z).where(z.abs() > 1, 0.0)}
    pol = fd.policy_gap(m_starts)[1]
    lines.append("RULES (monthly, % a month; EXNESS is the verdict)")
    res = {}
    for nm, pos in rules.items():
        s_spot, s_carry, s_ex = fd.run(pos.reindex(columns=CCY).fillna(0.0), m_ret, m_n, pol)
        a, e = fd.stat(s_spot, 12), fd.stat(s_ex, 12)
        res[nm] = e
        lines.append(f"  {nm:42} n {e['n']:4} | spot {a['mean'] * 100:+.3f} | EXNESS {e['mean'] * 100:+.3f} (tune {e['tu'] * 100:+.3f} "
                     f"t {e['t_tu']:+.1f} / holdout {e['ho'] * 100:+.3f} t {e['t_ho']:+.1f}) | {e['ann'] * 100:+.2f}%/yr")
    ps = sorted((res[n]["p"], n) for n in res)
    holm, run_max = {}, 0.0
    for r_, (p, n) in enumerate(ps):
        run_max = max(run_max, min(1.0, p * (len(ps) - r_)))
        holm[n] = run_max
    passes = [n for n in res if res[n]["tu"] > 0 and res[n]["ho"] > 0 and res[n]["t_tu"] >= 2 and res[n]["t_ho"] >= 2
              and holm[n] < 0.05]
    lines.append("  Holm p: " + ", ".join(f"{n.split(' (')[0]} {holm[n]:.2f}" for n in res) + f" | PASS: {passes or 'none'}")
    lines.append("")
    lines.append("REGISTERED PREDICTIONS")
    lines.append(f"  H0 Fed tone vs US 2y: {h0:+.2f} -> {'RIGHT' if h0 >= 0.2 else 'WRONG'}")
    a_ = [res_corr[("M", "A", "A same period: tone change", c)] for c in CCY]
    lines.append(f"  H1 same month: " + ", ".join(f"{c} {v:+.2f}" for c, v in zip(CCY, a_)) +
                 f" -> {'RIGHT' if np.mean(np.array(a_) >= 0.05) > 0.5 else 'WRONG'}")
    nx = max(abs(v) for k, v in res_corr.items() if k[1] == "B" and np.isfinite(v))
    lines.append(f"  H2 largest next-period |corr| {nx:.2f} -> {'RIGHT' if nx < 0.10 else 'WRONG'}")
    lines.append(f"  H3 passes: {passes or 'none'} -> {'RIGHT' if not passes else 'WRONG'}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

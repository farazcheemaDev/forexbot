"""NEWS MOOD AND FOREX: GDELT's tone of the world's news about each economy, 2017-2026 (2026-10-12)

THE USER (2026-10-12): "run gdelt news tone next". GDELT reads online news in 65 languages and scores each article's
TONE (negative to positive words); its DOC 2.0 API gives, per day, the average tone of all articles matching a query and
their VOLUME (share of all coverage), from 2017 (backtest/fx_macro_data.py --build_gdelt). One query per economy: its
economy and its central bank by name (fx_macro_data.GDELT_Q). For each currency the driver is RELATIVE: its economy's tone
minus the US economy's (good news about Europe vs good news about the US -> EURUSD), and its volume share.

TESTS (weekly, Monday noon fix to Monday noon fix; the tone of a day is complete at midnight UTC, so a week's tone is
known before the next Monday's fix; fx_drivers machinery, Exness costs)
    A  MOVES WITH   the same week's change in relative tone against the currency's move
    B  PREDICTS     last week's change against the next week's move; and last week's level
    RULES  TONE TREND   follow last week's change in relative tone
           TONE EXTREME fade the currency when its 52-week relative-tone z-score is beyond +-1.5 (the crowd's mood overdone)
           ATTENTION    sell a currency whose news volume jumped (z > 1.5 over 52 weeks: trouble makes news), buy when quiet

REGISTERED BEFORE THE RUN (2026-10-12)
    N1  A: the same week's change in relative tone correlates positively with the currency (>= +0.10) on most of the 7.
    N2  B: every next-week |correlation| is under 0.10.
    N3  No rule passes on Exness (t >= 2 on both halves, Holm across the three).

RESULT (2026-10-12 08:45 UTC, logs/fx_news_tone.txt; 507 weeks 2017-01 .. 2026-10)
    - N1 WRONG: the world's news tone about an economy does not move with its currency even in the same week (-0.06..
      +0.06). Tone levels differ (Canada +0.18, NZ -0.30 ... the euro area -1.45, the US -1.35) but their changes are noise
      for the exchange rate.
    - N2 RIGHT: nothing predicts the next week (|corr| <= 0.06), tone or volume.
    - N3 RIGHT: 0 of 3 rules pass. ATTENTION (sell a currency whose news volume spikes) +2.32%/yr at Exness, tune +0.110%
      (t +1.1) / holdout -0.053% (t -0.5) - flips; TONE TREND -1.68%/yr; TONE EXTREME -2.75%/yr.
    Reading: general news mood is not what moves currencies; the specific numbers (data, 2-year rates, risk) are, and they
    are priced within minutes (fx_surprises_1m.py, fx_rates2y.py).

    python -m backtest.fx_news_tone
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtest import fx_drivers as fd  # noqa: E402
from backtest import fx_macro_data as md  # noqa: E402

LOG = ROOT / "logs" / "fx_news_tone.txt"
CCY = fd.CCY


def weekly(daily: pd.DataFrame, starts: pd.DatetimeIndex) -> pd.DataFrame:
    """mean of the daily values over the 7 days before each period start (complete days only)."""
    out = {}
    for t in starts:
        w = daily[(daily.index < t.normalize()) & (daily.index >= t.normalize() - pd.Timedelta(days=7))]
        out[t] = w.mean()
    return pd.DataFrame(out).T


def main():
    g = md.load("gdelt_tone.csv")
    starts, ret, nights = fd.grid("W")
    keep = starts >= "2017-01-16"
    starts, ret, nights = starts[keep], ret[keep], nights[keep]
    pol = fd.policy_gap(starts)[1]
    tone = weekly(g[[f"tone_{c}" for c in ["USD"] + CCY if f"tone_{c}" in g.columns]], starts)
    vol = weekly(g[[f"vol_{c}" for c in ["USD"] + CCY if f"vol_{c}" in g.columns]], starts)
    rel = pd.DataFrame({c: tone[f"tone_{c}"] - tone["tone_USD"] for c in CCY if f"tone_{c}" in tone.columns})
    vz = pd.DataFrame({c: (vol[f"vol_{c}"] - vol[f"vol_{c}"].rolling(52, min_periods=26).mean()) /
                       vol[f"vol_{c}"].rolling(52, min_periods=26).std() for c in CCY if f"vol_{c}" in vol.columns})
    lines = [f"backtest/fx_news_tone.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; GDELT DOC API daily tone / volume "
             f"{g.index.min():%Y-%m-%d} .. {g.index.max():%Y-%m-%d}; {len(starts)} weeks; relative tone = the economy's minus the US's",
             f"average tone (more negative = gloomier): " + ", ".join(f"{c} {g[f'tone_{c}'].mean():+.2f}" for c in ["USD"] + CCY
                                                                       if f"tone_{c}" in g.columns), ""]
    lines.append(f"  {'':42}" + "".join(f"{c:>7}" for c in CCY))
    corr = {}
    same = rel.shift(-1) - rel                                     # the change over the week that starts at each date
    last = rel - rel.shift(1)
    for nm, x in (("A same week: tone change", same), ("B next week: last week's tone change", last),
                  ("B next week: last week's tone level", rel), ("B next week: last week's volume z", vz)):
        row = f"  {nm:42}"
        for c in CCY:
            if c not in x.columns:
                row += f"{'':>7}"
                continue
            j = pd.concat([x[c], ret[c]], axis=1).dropna()
            r = j.iloc[:, 0].corr(j.iloc[:, 1]) if len(j) > 50 else np.nan
            corr[(nm[0], nm, c)] = r
            row += f"{r:+7.2f}"
        lines.append(row)
    lines.append("")
    z = (rel - rel.rolling(52, min_periods=26).mean()) / rel.rolling(52, min_periods=26).std()
    rules = {"TONE TREND (follow last week's change)": np.sign(last),
             "TONE EXTREME (fade |z| > 1.5)": (-np.sign(z)).where(z.abs() > 1.5, 0.0),
             "ATTENTION (sell news spikes, buy quiet)": (-np.sign(vz)).where(vz.abs() > 1.5, 0.0)}
    lines.append("RULES (% a week; EXNESS is the verdict)")
    res = {}
    for nm, pos in rules.items():
        s_spot, s_carry, s_ex = fd.run(pos.reindex(columns=CCY).fillna(0.0), ret, nights, pol)
        a, e = fd.stat(s_spot, 52), fd.stat(s_ex, 52)
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
    a_ = [corr[("A", "A same week: tone change", c)] for c in CCY if ("A", "A same week: tone change", c) in corr]
    lines.append(f"  N1 same week: " + ", ".join(f"{c} {v:+.2f}" for c, v in zip(CCY, a_)) +
                 f" -> {'RIGHT' if np.mean(np.array(a_) >= 0.10) > 0.5 else 'WRONG'}")
    nx = max(abs(v) for k, v in corr.items() if k[0] == "B" and np.isfinite(v))
    lines.append(f"  N2 largest next-week |corr| {nx:.2f} -> {'RIGHT' if nx < 0.10 else 'WRONG'}")
    lines.append(f"  N3 passes: {passes or 'none'} -> {'RIGHT' if not passes else 'WRONG'}")
    txt = "\n".join(lines)
    print(txt)
    LOG.write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

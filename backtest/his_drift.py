"""s108 - BEHAVIOURAL AND TIMING DRIFT: January-September (46 NASDAQ trades) against October-November (7) (2026-11-22)

THE USER (2026-11-22): in January-September 24 of 46 clicks came 5-24 s after a 1-minute close (s73, p 0.006); in October-November only 1 of 7
(s83), 3 of the 7 at 04:38-05:00 New York (s74), and he still won 7 of 7. Is the disappearance of the timing cluster significant, what else
changed, and what does it say about his trigger?

DATA (on disk): his statement (strategy_analysis/statement_trades.csv, 46 NASDAQ trades; gitignored - it holds a name and account number,
  only aggregates are printed here), logs/his_new_trades.csv (the 7 new: 2026-10-08 x2 from the October statement, 10-13 x2 seen in the
  app's History, 11-12 x3 from the November statement), lots: October 8 from strategy_analysis/his_statement_2026-10_trades.csv (gitignored),
  November 12 from s74 (0.25 / 0.20 / 0.10, balance 6,655.58 before), October 13 not recorded; opening tickets: the 20 screenshot trades of
  his_open_tickets.py and the two of 10-13 (his_live_1013.py); the +-7 race on the Exness tick caches (his_race_curve.race2), the 11-12 races
  as scored by his_score_new.py at the time (logs/his_new_trades.csv); the breadth recorder's minute file for 2026-11-12, copied read-only
  from the VM (strategy_analysis/data/breadth/minute/2026-11-12.csv there; minute_ny / n_live / n_traded / tick / add / vold).
CLOCKS: his statement / app clock is UTC+4 before 2026-03-29 and UTC+5 after (s35c, s74); Pakistan time is UTC+5 all year; seconds are
  clock-free.

WHAT WAS ALREADY KNOWN (so these are measurements, not blind predictions): the seconds of all 53 entries (s73, s83), the 7 new trades' times,
  holds and points (logs/his_new_trades.csv), the Nov 12 lots and balance (s74), the old ticket gaps (s57).
REGISTERED BEFORE THE FIRST RUN for the parts not yet computed (2026-11-22)
  D1  The 5-24 s cluster: Fisher's exact (24/46 vs 1/7) one-sided p 0.02-0.08, two-sided 0.04-0.15; KS and a circular (Kuiper)
      permutation test on the 60 seconds both p > 0.05 - suggestive, not significant at n = 7.                                     (65%)
  D2  Pre-market (before 09:30 New York): the Jan-Sep share is under 15% and the Oct-Nov share (3 of 7) differs from it with Fisher
      one-sided p < 0.10.                                                                                                           (60%)
  D3  Hold time and banked points do not differ (Mann-Whitney p > 0.2 for both).                                                     (65%)
  D4  Size: the November % of the account per NASDAQ point sits inside the June-September monthly medians' range.                  (55%)
  D5  The ticket gaps of 10-13 (5 and 2 tickets) sit inside the old gap-vs-hold pattern (old median 6, range 1-52).                (75%)
  D6  At 04:38-05:00 New York on 2026-11-12 the breadth proxy is built from fewer than 30 of the ~100 stocks trading in a minute
      (the regular session: 90+), with no pre-market volume.                                                                        (70%)

RESULT (2026-11-22, logs/his_drift.txt) - THE CANDLE-CLOSE TIMING AND HIS HOURS CHANGED; HIS TRADING DID NOT. D1-D3, D5, D6 right;
  D4 WRONG (the third 11-12 trade, 0.10 lot, was smaller than any June-September median).
  Click second: 24 of 46 in 5-24 s -> 1 of 7 (Fisher one-sided p 0.069, two-sided 0.104; P(<= 1 of 7 at the old 52%) 0.049; KS 0.076; circular
  Kuiper 0.20) - suggestive, not significant. Hours: pre-market 4 of 46 (08:54, 08:32, 06:54, 05:11 New York - 11-12 was not his first) -> 3 of
  7 (Fisher one-sided 0.041); inside his two Pakistan-time windows 34 of 46 -> 2 of 7 (0.028).
  Unchanged: hold (median 78 s vs 84 s, p 0.82), banked points (+9.17 vs +9.18, p 0.95; 28% vs 29% within a point of +7), the race (36 of 41 vs
  7 of 7), ticket gaps (10-13: 5 and 2 tickets over 84 s and 72 s holds; Jan-Sep 1-52, median 6, NASDAQ holds of 50-100 s 1-7), size
  (11-12: 0.38 / 0.30 / 0.15% of the account a point, 106 / 85 / 43x notional; June-September medians 0.28-0.59%, 85-176x).
  Breadth at 04:38-05:00 New York on 11-12: 10-20 of the ~100 stocks printed in a minute (median 14; the regular session 98), no pre-market
  volume (VOLD 0, TRIN empty) - the recorder has almost nothing to measure there and cannot explain those three wins.
  Reading: the 5-24 s reaction was a habit of his usual evening cash-session sittings, not a component of the edge - the edge held without it.
  An alert firing at the 1-minute close that carried his information should have kept the cluster; on 7 trades it (weakly) did not.

    python -m backtest.his_drift [--breadth <copied 2026-11-12.csv>]
"""
from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "strategy_analysis" / "data"
LOG = ROOT / "logs" / "his_drift.txt"
LO, HI = 5, 24
NOV12_LOTS = {"14:38:38": 0.25, "14:44:57": 0.20, "15:00:57": 0.10}
NOV12_BALANCE = 6655.58
OCT13_TICKETS = [(84, 13990130, 13990135), (72, 13990144, 13990146)]      # (hold s, open ticket, close ticket), his_live_1013.py


def old_trades() -> pd.DataFrame:
    import backtest.his_tape as TP
    x = TP.entries()
    x["hold"] = (pd.to_datetime(x.close_time) - pd.to_datetime(x.open_time)).dt.total_seconds()
    x["banked"] = np.where(x.side.str.upper() == "BUY", x.close_price - x.open_price, x.open_price - x.close_price)
    x["sec"] = pd.to_datetime(x.open_time).dt.second
    x["ny_h"] = x.et.dt.hour + x.et.dt.minute / 60
    pk = x.utc + pd.Timedelta(hours=5)
    x["pk_h"] = pk.dt.hour + pk.dt.minute / 60
    x["month"] = x.utc.dt.month
    return x


def new_trades() -> pd.DataFrame:
    n = pd.read_csv(ROOT / "logs" / "his_new_trades.csv")
    o = pd.to_datetime(n.date + " " + n.open)
    c = pd.to_datetime(n.date + " " + n.close)
    utc = o - pd.Timedelta(hours=5)
    et = pd.to_datetime(n.date + " " + n.ny_time)
    out = pd.DataFrame({"utc": utc, "et": et, "s": np.where(n.side == "BUY", 1, -1), "hold": (c - o).dt.total_seconds(),
                        "banked": n.banked.astype(float), "sec": o.dt.second, "race": n.race, "open_px": n.open_px.astype(float),
                        "open": n.open, "date": n.date})
    out["ny_h"] = et.dt.hour + et.dt.minute / 60
    pk = utc + pd.Timedelta(hours=5)
    out["pk_h"] = pk.dt.hour + pk.dt.minute / 60
    oct_ = pd.read_csv(ROOT / "strategy_analysis" / "his_statement_2026-10_trades.csv")
    oct_ = oct_[oct_.symbol.str.contains("NASDAQ")]
    lots = {pd.to_datetime(r.open_time, format="%d-%m-%Y %H:%M:%S"): r.lots for r in oct_.itertuples()}
    out["lots"] = [lots.get(pd.Timestamp(f"{r.date} {r.open}"), NOV12_LOTS.get(r.open, np.nan)) for r in out.itertuples()]
    return out.sort_values("utc", kind="stable").reset_index(drop=True)


def kuiper_two_sample(a, b, n_perm=20000, rng=None):
    """Circular two-sample Kuiper statistic on seconds 0..59 and its permutation p."""
    grid = np.arange(60)

    def V(x, y):
        fx = np.searchsorted(np.sort(x), grid, side="right") / len(x)
        fy = np.searchsorted(np.sort(y), grid, side="right") / len(y)
        d = fx - fy
        return d.max() - d.min()
    obs = V(a, b)
    pool = np.concatenate([a, b])
    rng = rng or np.random.default_rng(108)
    cnt = 0
    for _ in range(n_perm):
        p = rng.permutation(pool)
        cnt += V(p[:len(a)], p[len(a):]) >= obs - 1e-12
    return obs, (cnt + 1) / (n_perm + 1)


def in_usual(pk_h):
    """His two Pakistan-time windows (s67): 19:45-21:00 and 23:00-00:30."""
    return ((pk_h >= 19.75) & (pk_h < 21.0)) | (pk_h >= 23.0) | (pk_h < 0.5)


def races_old(x):
    from backtest.his_race_curve import race2
    ticks = pickle.loads((DATA / "ustec_tick_days.pkl").read_bytes())
    out = []
    for r in x.itertuples():
        v = ticks.get(r.d)
        if v is None or r.t < 0:
            continue
        ts, mid, _ = v
        out.append(race2(ts, mid, r.t, r.s, 600, 7, 7))
    return [o for o in out if o is not None]


def races_new(n):
    from backtest.his_race_curve import race2
    fresh = pickle.loads((DATA / "fresh" / "ustec_tick_days_fresh.pkl").read_bytes())
    out = []
    for r in n.itertuples():
        d = r.et.normalize()
        t = (r.et - d - pd.Timedelta(hours=9, minutes=30)).total_seconds()
        v = fresh.get(d)
        if v is not None and 0 <= t <= 35000:
            ts, mid, _ = v
            out.append(("ticks", race2(ts, mid, t, r.s, 600, 7, 7)))
        else:
            out.append(("his_score_new (MT5 at the time)", 1 if r.race == "WON" else 0))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--breadth", default=None, help="the VM's strategy_analysis/data/breadth/minute/2026-11-12.csv, copied read-only")
    a = ap.parse_args(argv)
    rng = np.random.default_rng(108)
    x, n = old_trades(), new_trades()
    L = [f"backtest/his_drift.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC (s108); Jan-Sep {len(x)} NASDAQ trades (statement), Oct-Nov {len(n)}", ""]
    # 1. seconds
    so, sn = x.sec.to_numpy(), n.sec.to_numpy()
    ko, kn = int(((so >= LO) & (so <= HI)).sum()), int(((sn >= LO) & (sn <= HI)).sum())
    f2 = stats.fisher_exact([[ko, len(so) - ko], [kn, len(sn) - kn]])
    f1 = stats.fisher_exact([[ko, len(so) - ko], [kn, len(sn) - kn]], alternative="greater")
    binom = stats.binom.cdf(kn, len(sn), ko / len(so))
    ks = stats.ks_2samp(so, sn)
    kv, kp = kuiper_two_sample(so, sn, rng=rng)
    L += ["1. THE CLICK SECOND (seconds into the minute)",
          f"  Jan-Sep: {ko} of {len(so)} in {LO}-{HI} s ({ko / len(so):.0%}); median second {np.median(so):.0f}; Oct-Nov: {kn} of {len(sn)} "
          f"({kn / len(sn):.0%}), seconds {', '.join(f'{v:02d}' for v in sorted(sn))}",
          f"  Fisher's exact: two-sided p {f2.pvalue:.3f}, one-sided (fewer now) p {f1.pvalue:.3f}; P(<= {kn} of {len(sn)} | the old rate "
          f"{ko / len(so):.0%}) = {binom:.3f}",
          f"  KS two-sample p {ks.pvalue:.3f}; circular Kuiper V {kv:.3f}, permutation p {kp:.3f}",
          f"  the old cluster split by sitting (s73): follow-ups 10 of 15, first trades 14 of 31; the 7 new are 3 sittings: first trades "
          f"{', '.join(f'{v:02d}' for v in n.groupby(n.date).sec.first())}"]
    # 2. session hour
    pre_o, pre_n = int((x.ny_h < 9.5).sum()), int((n.ny_h < 9.5).sum())
    fp = stats.fisher_exact([[pre_n, len(n) - pre_n], [pre_o, len(x) - pre_o]], alternative="greater")
    uo, un = int(in_usual(x.pk_h).sum()), int(in_usual(n.pk_h).sum())
    fu = stats.fisher_exact([[uo, len(x) - uo], [un, len(n) - un]], alternative="greater")
    L += ["", "2. THE SESSION HOUR",
          f"  pre-market (before 09:30 New York): Jan-Sep {pre_o} of {len(x)} ({pre_o / len(x):.0%}) - "
          + ", ".join(f"{r.et:%m-%d %H:%M} NY / {(r.utc + pd.Timedelta(hours=5)):%H:%M} PKT" for r in x[x.ny_h < 9.5].itertuples())
          + f"; Oct-Nov {pre_n} of {len(n)} ({pre_n / len(n):.0%}); Fisher one-sided p {fp.pvalue:.3f}",
          f"  inside his two Pakistan-time windows (19:45-21:00, 23:00-00:30, s67): Jan-Sep {uo} of {len(x)} ({uo / len(x):.0%}), Oct-Nov {un} of "
          f"{len(n)}; Fisher one-sided p {fu.pvalue:.3f}",
          "  Oct-Nov, New York / Pakistan: " + ", ".join(f"{r.et:%m-%d %H:%M}/{(r.utc + pd.Timedelta(hours=5)):%H:%M}" for r in n.itertuples()),
          "  Jan-Sep New York hour histogram: " + " ".join(f"{h:02d}:{int((x.ny_h.astype(int) == h).sum())}" for h in range(4, 20)
                                                       if int((x.ny_h.astype(int) == h).sum()))]
    # 3. hold and exit points
    mh = stats.mannwhitneyu(x.hold, n.hold)
    mb = stats.mannwhitneyu(x.banked, n.banked)
    L += ["", "3. HOLD AND EXIT POINTS",
          f"  hold: Jan-Sep median {x.hold.median():.0f} s (middle half {x.hold.quantile(.25):.0f}-{x.hold.quantile(.75):.0f}), Oct-Nov median "
          f"{n.hold.median():.0f} s ({', '.join(f'{v:.0f}' for v in n.hold)}); Mann-Whitney p {mh.pvalue:.3f}",
          f"  banked points: Jan-Sep mean {x.banked.mean():+.2f}, median {x.banked.median():+.2f} (worst {x.banked.min():+.2f}, {int((x.banked > 0).sum())} of "
          f"{len(x)} green); Oct-Nov mean {n.banked.mean():+.2f}, median {n.banked.median():+.2f} ({int((n.banked > 0).sum())} of {len(n)} green); "
          f"Mann-Whitney p {mb.pvalue:.3f}",
          f"  share of exits within 1 point of +7: Jan-Sep {np.mean(np.abs(x.banked - 7) <= 1):.0%}, Oct-Nov {np.mean(np.abs(n.banked - 7) <= 1):.0%}; "
          f"above +10: {np.mean(x.banked > 10):.0%} vs {np.mean(n.banked > 10):.0%}"]
    # 4. size relative to the account
    from backtest.his_monthly_target import CAP
    x["pct_pt"] = x.lots * 100 / x.month.map(CAP) * 100
    x["notional_x"] = x.lots * 100 * x.open_price / x.month.map(CAP)
    med = x.groupby("month")[["lots", "pct_pt", "notional_x"]].median()
    js = med.loc[6:9]
    nov = n[n.date == "2026-11-12"]
    nov_pct = nov.lots * 100 / NOV12_BALANCE * 100
    nov_x = nov.lots * 100 * nov.open_px / NOV12_BALANCE
    octn = n[n.date == "2026-10-08"]
    lo_cap, hi_cap = CAP[9], NOV12_BALANCE
    L += ["", "4. SIZE RELATIVE TO THE ACCOUNT ($100 a point per lot; Jan-Sep capital from s16 by month, Nov 12 the statement's balance)",
          "  Jan-Sep monthly medians (lots / % of the account per point / notional x): "
          + "; ".join(f"{m:02d}: {r.lots:.2f} / {r.pct_pt:.2f}% / {r.notional_x:.0f}x" for m, r in med.iterrows()),
          f"  Nov 12: lots {', '.join(f'{v:.2f}' for v in nov.lots)} -> {', '.join(f'{v:.2f}%' for v in nov_pct)} a point, "
          f"{', '.join(f'{v:.0f}x' for v in nov_x)} notional (June-September medians {js.pct_pt.min():.2f}-{js.pct_pt.max():.2f}% / "
          f"{js.notional_x.min():.0f}-{js.notional_x.max():.0f}x)",
          f"  Oct 8: lots {', '.join(f'{v:.2f}' for v in octn.lots)} -> {octn.lots.iloc[0] * 100 / hi_cap * 100:.2f}-"
          f"{octn.lots.iloc[0] * 100 / lo_cap * 100:.2f}% a point (capital between September's ~${lo_cap:,.0f} and November's ${hi_cap:,.0f}); "
          "Oct 13: lots not recorded"]
    # 5. opening tickets
    from backtest.his_open_tickets import OPEN
    s = pd.read_csv(ROOT / "strategy_analysis" / "statement_trades.csv", parse_dates=["open_time", "close_time"])
    m = s[s.ticket.isin(OPEN)].copy()
    m["gap"] = m.ticket - m.ticket.map(OPEN)
    m["hold"] = (m.close_time - m.open_time).dt.total_seconds()
    nq = m[m.symbol.str.startswith("NASDAQ")]
    rho = stats.spearmanr(m.hold, m.gap)
    L += ["", "5. OPENING TICKETS (close ticket - open ticket = orders the broker took while he held)",
          f"  Jan-Sep: {len(m)} trades with an open ticket (NASDAQ {len(nq)}): gap median {m.gap.median():.0f}, range {m.gap.min()}-{m.gap.max()}; "
          f"gap vs hold Spearman {rho[0]:+.2f}; NASDAQ holds 50-100 s: gaps "
          + ", ".join(str(int(g)) for g, h in zip(nq.gap, nq.hold) if 50 <= h <= 100),
          f"  Oct 13: " + ", ".join(f"hold {h} s -> gap {c - o}" for h, o, c in OCT13_TICKETS) + " (both in counter order); Oct 8 and Nov 12: "
          "the statements print closing tickets only"]
    # 6. the race
    ro = races_old(x)
    rn = races_new(n)
    L += ["", "6. THE +-7 RACE ON THE EXNESS MID",
          f"  Jan-Sep (ticks inside 09:30-19:30 New York): {sum(ro)} of {len(ro)} ({np.mean(ro):.0%}); Oct-Nov: {sum(v for _, v in rn)} of {len(rn)} "
          f"({sum(1 for s_, _ in rn if s_ == 'ticks')} on the Exness tick cache, {sum(1 for s_, _ in rn if s_ != 'ticks')} pre-market as scored by "
          "his_score_new.py from MT5 at the time)"]
    # 7. breadth at the pre-market clicks
    if a.breadth and Path(a.breadth).exists():
        b = pd.read_csv(a.breadth)
        pre = b[(b.minute_ny >= "04:30") & (b.minute_ny <= "05:05")]
        reg = b[(b.minute_ny >= "09:30") & (b.minute_ny < "16:00")]
        at = b[b.minute_ny.isin([v[:5] for v in n[n.date == "2026-11-12"].et.dt.strftime("%H:%M:%S")])]
        L += ["", "7. THE BREADTH RECORDER AT THE PRE-MARKET CLICKS (2026-11-12; a Nasdaq-100 proxy from Yahoo 1-minute bars)",
              f"  stocks printing in a minute: 04:30-05:05 median {pre.n_traded.median():.0f} of 100 (range {pre.n_traded.min()}-{pre.n_traded.max()}), "
              f"with {pre.n_live.median():.0f} printed at all that morning; regular session median {reg.n_traded.median():.0f}",
              f"  pre-market VOLD all {pre.vold_day.abs().max():.0f} (Yahoo's pre-market minute bars carry no volume), TRIN empty: "
              f"{pre.trin.isna().all()}",
              "  at his minutes (minute, stocks printing, tick proxy, add): "
              + "; ".join(f"{r.minute_ny} {r.n_traded} {r.tick:+d} {r.add:+d}" for r in at.itertuples())
              + f"  - he sold all three; 04:30-05:05 add median {pre['add'].median():+.0f} (the whole sitting)"]
        d6 = pre.n_traded.max() < 30 and reg.n_traded.median() >= 90 and pre.vold_day.abs().max() == 0
    else:
        d6 = None
        L += ["", "7. BREADTH: pass --breadth <copied file> (not given)"]
    # predictions
    d1 = 0.02 <= f1.pvalue <= 0.08 and 0.04 <= f2.pvalue <= 0.15 and ks.pvalue > 0.05 and kp > 0.05
    d2 = pre_o / len(x) < 0.15 and fp.pvalue < 0.10
    d3 = mh.pvalue > 0.2 and mb.pvalue > 0.2
    d4 = all(js.pct_pt.min() <= v <= js.pct_pt.max() for v in nov_pct)
    d5 = all(1 <= c - o <= 52 for _, o, c in OCT13_TICKETS)
    L += ["", "PREDICTIONS",
          f"  D1 Fisher one-sided {f1.pvalue:.3f} (0.02-0.08), two-sided {f2.pvalue:.3f} (0.04-0.15), KS {ks.pvalue:.3f}, Kuiper {kp:.3f} (> 0.05) -> "
          f"{'RIGHT' if d1 else 'WRONG'}",
          f"  D2 Jan-Sep pre-market share {pre_o / len(x):.0%} (< 15%), Fisher one-sided {fp.pvalue:.3f} (< 0.10) -> {'RIGHT' if d2 else 'WRONG'}",
          f"  D3 hold p {mh.pvalue:.3f}, points p {mb.pvalue:.3f} (both > 0.2) -> {'RIGHT' if d3 else 'WRONG'}",
          f"  D4 Nov % a point {', '.join(f'{v:.2f}' for v in nov_pct)} inside June-Sep medians {js.pct_pt.min():.2f}-{js.pct_pt.max():.2f} -> "
          f"{'RIGHT' if d4 else 'WRONG'}",
          f"  D5 Oct 13 ticket gaps inside 1-52 -> {'RIGHT' if d5 else 'WRONG'}",
          f"  D6 breadth proxy pre-market < 30 stocks a minute, regular 90+, no volume -> {'n/a' if d6 is None else ('RIGHT' if d6 else 'WRONG')}"]
    txt = "\n".join(L)
    LOG.write_text(txt + "\n", encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    sys.exit(main())

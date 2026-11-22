"""THE ANALYST DESK'S "SWEET SPOT" SIGNALS, ANALYSED IN DEPTH (2026-11-15)

THE USER (2026-11-15): "I want a detailed analysis of sweet spot signals."
The sweet spot = a desk call whose stop is >= 0.8% from its entry (analyst_sweetspot.py, registered 2026-11-06 15:00 UTC after it was found by slicing the desk's first 86 calls).
This file puts every angle on one page, from the desk's LIVE call log (copied from the VM: logs/analyst_calls_20261114.csv), its 4.7-year replay (analyst_replay.py's cached calls) and
Binance's public 1-minute candles:
  A  the live record before / after the registration, with 95% ranges counted on independent bets (a bet = one UTC day + one side: one market move settles every same-direction call of a day)
  B  the NEW piece: a MATCHED RANDOM-ENTRY CONTROL IN R. For every resolved call, random entries on the same coin, same side, same stop %, target % and hours (every 15 minutes over the desk's live period,
     scored on 1-minute candles with the desk's own pessimistic rules and its 12bp fee) give the R a coin-flip entry earns on that exact bracket. The call's excess over it = what the TIMING is worth.
     The desk shows only the random HIT RATE; this puts the whole comparison in R and per independent bet.
  C  the registered forward test: where it stands, what the bar needs, the chance of passing at 30 bets given the 12 so far (a Monte Carlo over the true edge and two priors)
  D  slices (method, coin, side, stop band, reward:risk) - exploratory, 40 cells, so only a very large effect means anything
  E  dollars: the sweet-spot calls booked on $10 / $20 / $50 at 0.5 / 1 / 2% risk, with the desk's own booking rules (analyst_tiers.simulate)
  F  the 4.7-year replay: the sweet spot by half and year, with the R lost to the hit rate being below a random entry's

REGISTERED BEFORE THE FIRST RUN (2026-11-15)
  S1  The matched random-entry control earns about -0.05 to -0.12R a call on the sweet-spot geometry (the 12bp fee alone is ~0.1R at a 1.2% stop), and the sweet-spot calls' excess over it is within +-0.3R a bet
      with |t| < 2 in the forward sample, the discovery sample and the two together.
  S2  The chance of passing the registered bar at 30 bets is under 5% under a skeptical prior (centred on the replay's ~0R a bet) and under 15% under an enthusiast prior (centred on the +0.42R discovery).
  S3  No method / coin / side / stop-band slice of the forward sample reaches t >= 2 over bets (40 cells: about two would by chance at 5%).
  S4  $20 at 1% risk following ONLY the forward sweet-spot calls ends below its start.
  S5  The discovery sample's +0.71R a call is mostly selection: the same cut on the calls made since is no better than -0.1R a call.

    python -m backtest.sweetspot_deep [calls.csv]        writes logs/sweetspot_deep.txt          (the random-entry control needs Binance REST; candles are cached in strategy_analysis/data/sweetspot_1m/)
"""
from __future__ import annotations

import json
import math
import statistics as st
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from scipy import stats as sps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import analyst  # noqa: E402
import desk  # noqa: E402
from backtest import analyst_sweetspot as ss  # noqa: E402
from backtest import analyst_tiers as tiers  # noqa: E402

LOG = ROOT / "logs" / "sweetspot_deep.txt"
CACHE = ROOT / "strategy_analysis" / "data" / "sweetspot_1m"
REPLAY = ROOT / "strategy_analysis" / "data" / "analyst_replay" / "calls.json"
DEFAULT_CALLS = ROOT / "logs" / "analyst_calls_20261114.csv"
FEE = desk.FEE
SWEET, SCALP = ss.SWEET_STOP, ss.SCALP_STOP
STEP = 15                       # a random entry every 15 minutes, as desk.minute_baseline does
MIN_MS = 60_000
DONE = ("WIN", "LOSS", "EXPIRED")
SPLIT = "2024-12-07"            # analyst_replay_cuts.py's halves


# ------------------------------------------------------------------ the live log

def load_live(path) -> pd.DataFrame:
    d = pd.read_csv(path)
    d["t"] = pd.to_datetime(d.made_ms, unit="ms")
    d["day"] = d.made_utc.str[:10]
    d["hours"] = ((d.expires_ms - d.made_ms) / 3_600_000).round().astype(int)
    d["done"] = d.status.isin(DONE) & d.r_net.notna()
    d["win"] = (d.status == "WIN").astype(float)
    d["kind"] = np.where(d.stop_pct >= SWEET, "sweet", np.where(d.stop_pct >= SCALP, "middle", "scalp"))
    d["fwd"] = d.made_ms >= ss.REGISTERED_MS
    d["open_mkt"] = [analyst.market_open(s, int(m)) for s, m in zip(d.symbol, d.made_ms)]
    return d


def bets(x: pd.DataFrame, col: str = "r_net") -> pd.Series:
    """One independent bet per (UTC day, side): the mean of the column over that day's same-side calls."""
    return x.groupby(["day", "side"])[col].mean()


def ci95(b: pd.Series):
    n = len(b)
    if n < 3 or b.std(ddof=1) == 0:
        return float("nan"), float("nan"), float("nan")
    se = b.std(ddof=1) / math.sqrt(n)
    h = sps.t.ppf(0.975, n - 1) * se
    return b.mean(), b.mean() - h, b.mean() + h


def tstat(b: pd.Series) -> float:
    n = len(b)
    return float(b.mean() / (b.std(ddof=1) / math.sqrt(n))) if n >= 5 and b.std(ddof=1) > 0.02 else float("nan")


# ------------------------------------------------------------------ B: the matched random-entry control

def minute_bars(sym: str, start_ms: int, end_ms: int):
    """1-minute (h, l, c) arrays for a symbol, cached on disk and topped up from Binance (public, no keys)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{sym}.json"
    have = json.loads(f.read_text()) if f.exists() else []
    t0 = have[-1][0] + MIN_MS if have else start_ms
    if not have or t0 < end_ms - 2 * MIN_MS:
        new = desk.bars_between(sym, t0, end_ms)
        seen = {b[0] for b in have}
        have += [list(b) for b in new if b[0] not in seen]
        have.sort()
        f.write_text(json.dumps(have))
    a = np.array([b for b in have if start_ms <= b[0] <= end_ms], float)
    return a[:, 0], a[:, 2], a[:, 3], a[:, 4]               # t, high, low, close


def random_entry(h, l, c, side: str, sp: float, tp: float, hours: int):
    """Mean R (after the 12bp fee) of a random entry (every STEP minutes, at a bar's close) on this exact bracket, scored like desk.resolve: a bar touching both = a loss, a timeout exits at the
    horizon's close. Returns dict(r, win, n)."""
    H = hours * 60
    n = len(c)
    last = n - H - 2
    if last < 10:
        return dict(r=float("nan"), win=float("nan"), n=0)
    idx = np.arange(0, last, STEP)
    e = c[idx]
    wh, wl = sliding_window_view(h, H)[idx + 1], sliding_window_view(l, H)[idx + 1]
    if side == "long":
        hs, ht = wl <= (e * (1 - sp))[:, None], wh >= (e * (1 + tp))[:, None]
    else:
        hs, ht = wh >= (e * (1 + sp))[:, None], wl <= (e * (1 - tp))[:, None]
    fs = np.where(hs.any(1), hs.argmax(1), H)
    ft = np.where(ht.any(1), ht.argmax(1), H)
    lose, win = (fs <= ft) & (fs < H), ft < fs
    sgn = 1.0 if side == "long" else -1.0
    r_to = (sgn * (c[idx + H] / e - 1) - FEE) / sp
    r = np.where(win, (tp - FEE) / sp, np.where(lose, -(sp + FEE) / sp, r_to))
    return dict(r=float(r.mean()), win=float(win.mean()), n=len(idx))


def add_random_control(d: pd.DataFrame) -> pd.DataFrame:
    """rand_r / rand_win per resolved call, from the desk's live period (first call to now) on the call's own coin."""
    start = int(d.made_ms.min()) - 60 * MIN_MS
    end = int(d.made_ms.max()) + int(d.hours.max()) * 3_600_000
    end = min(end, desk.now_ms() - 3 * MIN_MS)
    bars = {s: minute_bars(s, start, end) for s in sorted(d[d.done].symbol.unique())}
    rr, rw = [], []
    for _, x in d.iterrows():
        if not x.done:
            rr.append(np.nan)
            rw.append(np.nan)
            continue
        _, h, l, c = bars[x.symbol]
        o = random_entry(h, l, c, x.side, float(x.stop_pct), float(x.target_pct), int(x.hours))
        rr.append(o["r"])
        rw.append(o["win"])
    d = d.copy()
    d["rand_r"], d["rand_win"] = rr, rw
    d["excess"] = d.r_net - d.rand_r
    return d


# ------------------------------------------------------------------ report pieces

def row(label: str, x: pd.DataFrame, control: bool = True) -> str:
    x = x[x.done]
    if len(x) == 0:
        return f"  {label:<46} none"
    b = bets(x)
    m, lo, hi = ci95(b)
    s = (f"  {label:<46} n {len(x):>3}  bets {len(b):>3}  won {int(x.win.sum()):>2} ({x.win.mean() * 100:4.0f}% vs random {x.base_p.mean() * 100:4.0f}%)  "
         f"R/call {x.r_net.mean():+.2f}  R/bet {m:+.2f} [{lo:+.2f}, {hi:+.2f}]  t {tstat(b):+.1f}")
    if control and "rand_r" in x:
        eb = bets(x, "excess")
        s += f"  | random entry {x.rand_r.mean():+.2f}R  excess {x.excess.mean():+.2f}R/call, {eb.mean():+.2f}/bet (t {tstat(eb):+.1f})"
    return s


def power_table(fwd_bets: list, prior_mean_skeptic: float, rng) -> list:
    """The registered bar at 30 bets (mean >= +0.15, t >= 2, first 15 / last 15 bets both positive; the hit-above-random clause is not modelled): P(pass) given the true edge mu per bet,
    with the bets already in hand fixed and the rest drawn Normal(mu, sd). sd = the sample sd of the bets so far."""
    n0 = len(fwd_bets)
    sd = float(np.std(fwd_bets, ddof=1)) if n0 > 2 else 1.0
    need = ss.MIN_BETS - n0
    out = []
    sims = 20000
    for mu in (-0.30, -0.15, 0.0, 0.10, 0.20, 0.30, 0.50, 0.80):
        pas = 0
        for _ in range(sims):
            x = np.r_[fwd_bets, rng.normal(mu, sd, max(need, 0))]
            m, s = x.mean(), x.std(ddof=1)
            t = m / (s / math.sqrt(len(x))) if s > 0 else 0.0
            if m >= ss.MIN_MEAN_R and t >= ss.MIN_T and x[: len(x) // 2].mean() > 0 and x[len(x) // 2:].mean() > 0:
                pas += 1
        out.append((mu, pas / sims))
    return out, sd


def posterior_pass(fwd_bets: list, prior_m: float, prior_s: float, rng, sd: float) -> float:
    """P(pass at 30 bets) averaging the table over a Normal posterior for mu (a conjugate update of the Normal prior with the bets so far)."""
    n0 = len(fwd_bets)
    m0 = float(np.mean(fwd_bets))
    prec = 1 / prior_s ** 2 + n0 / sd ** 2
    mu_post = (prior_m / prior_s ** 2 + n0 * m0 / sd ** 2) / prec
    s_post = math.sqrt(1 / prec)
    need = ss.MIN_BETS - n0
    pas = 0
    sims = 40000
    for mu in rng.normal(mu_post, s_post, sims):
        x = np.r_[fwd_bets, rng.normal(mu, sd, max(need, 0))]
        m, s = x.mean(), x.std(ddof=1)
        t = m / (s / math.sqrt(len(x))) if s > 0 else 0.0
        if m >= ss.MIN_MEAN_R and t >= ss.MIN_T and x[: len(x) // 2].mean() > 0 and x[len(x) // 2:].mean() > 0:
            pas += 1
    return pas / sims, mu_post, s_post


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CALLS
    out = []

    def say(s=""):
        print(s, flush=True)
        out.append(s)

    d = load_live(path)
    d = add_random_control(d)
    sw = d[d.kind == "sweet"]
    say(f"backtest/sweetspot_deep.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; live log {path.name}: {len(d)} calls ({int(d.done.sum())} resolved), made {d.made_utc.min()} .. {d.made_utc.max()} UTC;"
        f" sweet spot (stop >= {SWEET:.1%}) {len(sw)} calls ({int(sw.done.sum())} resolved); registered {ss.REGISTERED_UTC} UTC")

    say()
    say("A+B. THE LIVE RECORD, WITH THE MATCHED RANDOM-ENTRY CONTROL (R after the 12bp fee; bets = UTC day + side; [95% range over bets])")
    say(row("sweet spot, BEFORE the registration (discovery)", sw[~sw.fwd]))
    say(row("sweet spot, AFTER the registration (forward)", sw[sw.fwd]))
    say(row("  forward, market open at the call (no XAU / QQQ gap)", sw[sw.fwd & sw.open_mkt]))
    say(row("sweet spot, all live", sw))
    say(row("middle (stop 0.4-0.8%), all live", d[d.kind == "middle"]))
    say(row("scalp-sized (stop < 0.4%), all live", d[d.kind == "scalp"]))
    say(row("all calls", d))
    say(row("all calls, forward only", d[d.fwd]))
    f = sw[sw.fwd & sw.done]
    say(f"  (the discovery sample as first found: 13 of 28 won, +0.71R a call over 14 bets - read after slicing 19 ways; the same calls are the 'before' row above, now with later resolutions)")
    say(f"  forward outcomes: {int((f.status == 'WIN').sum())} WIN, {int((f.status == 'LOSS').sum())} LOSS, {int((f.status == 'EXPIRED').sum())} EXPIRED (timed out in profit: "
        f"{', '.join(f'#{int(i)} {r:+.2f}R' for i, r in zip(f[f.status == 'EXPIRED'].id, f[f.status == 'EXPIRED'].r_net))}); R of a LOSS {f[f.status == 'LOSS'].r_net.min():+.2f}..{f[f.status == 'LOSS'].r_net.max():+.2f}")
    say(f"  random-entry check: a coin-flip entry on the forward calls' own brackets wins {f.rand_win.mean() * 100:.0f}% of the time (the desk's own logged odds: {f.base_p.mean() * 100:.0f}%) and earns {f.rand_r.mean():+.2f}R a trade")
    say(f"  (the fee alone costs {np.mean(FEE / sw.stop_pct) :.2f}R on a sweet-spot call, against {np.mean(FEE / d[d.kind == 'scalp'].stop_pct):.2f}R on a scalp-sized one: most of the 'sweet spot' is that a wider stop shrinks the fee)")

    # ---- C: the registered forward test
    say()
    say("C. THE REGISTERED FORWARD TEST (stop >= 0.8%, calls made after the registration; bar: 30 independent bets, mean >= +0.15R a bet, t >= 2, hit above the random odds, both halves positive)")
    sc = ss.score(ss.load(path))
    fb = [v for _, v in ss.bets(ss.sweet(ss.resolved(ss.forward(ss.load(path)))))]
    say(f"  scorer: {sc['calls']} calls = {sc['bets']} bets | mean R per bet {sc['mean_r']:+.3f} | t {('%+.2f' % sc['t']) if sc['t'] is not None else 'n/a'} | hit {sc['hit'] * 100:.0f}% vs random-entry odds {sc['base'] * 100:.0f}% | halves {sc['h1']:+.2f} / {sc['h2']:+.2f} | {sc['verdict']}")
    first = pd.to_datetime(ss.REGISTERED_UTC)
    last = sw[sw.fwd & sw.done].t.max()
    days = (last - first).total_seconds() / 86400
    pace = len(fb) / days
    eta = last + pd.Timedelta(days=(ss.MIN_BETS - len(fb)) / pace + 1.0)
    say(f"  pace: {len(fb)} bets in {days:.1f} days = {pace:.2f} a day -> 30 bets about {eta:%Y-%m-%d} (a call takes up to 24-48h to resolve)")
    rng = np.random.default_rng(20261115)
    tbl, sd = power_table(fb, 0.0, rng)
    need_mean = ss.MIN_T * sd / math.sqrt(ss.MIN_BETS)
    say(f"  the bar in practice: bet sd so far {sd:.2f}R (a win is +1.4..+1.9R, a loss -1.1R), so t >= 2 at 30 bets needs a mean of about {need_mean:+.2f}R a bet - the +0.15R clause never binds")
    left = ss.MIN_BETS - len(fb)
    say(f"  the {left} remaining bets must average {(need_mean * ss.MIN_BETS - sum(fb)) / left:+.2f}R to reach that ({np.mean(fb):+.2f}R so far)")
    say("  chance of passing at 30 bets if the TRUE edge per bet were:  " + "   ".join(f"{mu:+.2f}R -> {p * 100:4.1f}%" for mu, p in tbl))
    for lab, pm, ps in (("skeptical prior N(-0.02, 0.15) (the replay's per-bet mean)", -0.02, 0.15), ("enthusiast prior N(+0.30, 0.30)", 0.30, 0.30)):
        p, mp, sp_ = posterior_pass(fb, pm, ps, rng, sd)
        say(f"  {lab}: posterior edge {mp:+.2f}R +- {sp_:.2f}, P(pass at 30 bets) = {p * 100:.1f}%")

    # ---- D: slices
    say()
    say("D. SLICES (exploratory: ~40 cells, found AFTER looking, so a cell needs |t| >= 3 to mean anything; small n)")
    slice_t = {}
    for title, x in (("forward sweet spot", sw[sw.fwd]), ("all live sweet spot", sw)):
        say(f"  -- {title}")
        x = x[x.done]
        cuts = [(f"{col} = {v}", x[x[col] == v]) for col, labels in (("method", sorted(x.method.unique())), ("symbol", sorted(x.symbol.unique())), ("side", ["long", "short"])) for v in labels]
        cuts += [(lab, x[m]) for lab, m in (("stop 0.8-1.0%", (x.stop_pct >= 0.008) & (x.stop_pct < 0.010)), ("stop 1.0-1.5%", (x.stop_pct >= 0.010) & (x.stop_pct < 0.015)), ("stop >= 1.5%", x.stop_pct >= 0.015),
                                            ("reward:risk <= 2.5", x.rr <= 2.5), ("reward:risk 2.5-4", (x.rr > 2.5) & (x.rr <= 4)), ("reward:risk > 4", x.rr > 4),
                                            ("held 24h (SR, SMC)", x.hours == 24), ("held 48h (FIB)", x.hours == 48))]
        for lab, xx in cuts:
            say(row(lab, xx))
            b_ = bets(xx[xx.done])
            e_ = bets(xx[xx.done], "excess")
            slice_t[title, lab] = (tstat(b_), tstat(e_), len(b_))
    xs = sw[sw.done].sort_values("r_net", ascending=False)
    say(f"  concentration, all live sweet spot ({len(xs)} resolved, sum {xs.r_net.sum():+.1f}R): the best 3 calls are {xs.r_net.head(3).sum():+.1f}R; without them {xs.r_net.iloc[3:].sum():+.1f}R "
        f"over {len(xs) - 3} calls = {xs.r_net.iloc[3:].mean():+.2f}R a call")

    # ---- E: dollars
    say()
    say("E. DOLLARS: the sweet-spot calls booked with the desk's own rules (risk on booked equity, notional = risk / stop, 3x cap, $5 minimum order; no slippage / funding / lot steps)")
    rows = tiers.load(path)
    rows = [r for r in rows if r["status"] in DONE and r["r"] is not None]
    reg = ss.REGISTERED_MS
    for lab, pick in (("forward sweet spot only", lambda r: r["stop_pct"] >= SWEET and r["made_ms"] >= reg), ("all live sweet spot", lambda r: r["stop_pct"] >= SWEET)):
        say(f"  -- {lab}")
        for cap in tiers.TIERS:
            cells = []
            for rk in tiers.RISKS:
                o = tiers.simulate(rows, cap, rk, pick=pick)
                cells.append(f"{rk:.1f}% risk: ${o['equity']:.2f} ({o['ret'] * 100:+.1f}%, fall {o['maxdd'] * 100:.0f}%, {o['taken']} taken / {o['small']} under $5)")
            say(f"    ${cap:.0f}: " + " | ".join(cells))

    # ---- F: the replay
    say()
    say("F. THE 4.7-YEAR REPLAY (analyst_replay.py's cached calls, 1h bars, a bar touching both = a loss, 12bp): the sweet spot against what a random entry on the same bracket does")
    r = pd.DataFrame(json.loads(REPLAY.read_text()))
    r["t"] = pd.to_datetime(r.made_ms, unit="ms")
    r["day"] = r.t.dt.strftime("%Y-%m-%d")
    r["win"] = (r.status == "WIN").astype(float)
    r["rr"] = (r.target - r.entry).abs() / (r.entry - r.stop).abs()
    r["fee_r"] = FEE / r.stop_pct
    r["lose_r"] = 1 + r.fee_r
    r["win_r"] = r.rr - r.fee_r
    r["shortfall"] = (r.win - r.base_p) * (r.win_r + r.lose_r)
    r["half"] = np.where(r.t < SPLIT, "tune (to 2024-12)", "holdout (2024-12 on)")
    rs = r[r.stop_pct >= SWEET]
    for lab, x in [("all sweet-spot calls", rs)] + [(h, rs[rs.half == h]) for h in sorted(rs.half.unique())] + [(f"year {y}", rs[rs.t.dt.year == y]) for y in sorted(rs.t.dt.year.unique())]:
        b = x.groupby(["day", "side"]).r_net.mean()
        say(f"  {lab:<24} n {len(x):>5}  bets {len(b):>4}  hit {x.win.mean() * 100:4.1f}% vs random {x.base_p.mean() * 100:4.1f}%  R/call {x.r_net.mean():+.3f}  R/bet {b.mean():+.3f} (t {tstat(b):+.1f})  "
            f"R lost to the hit-rate shortfall {x.shortfall.mean():+.3f}/call  fee {x.fee_r.mean():.2f}R")
    for m in ("SMC", "SR", "FIB"):
        x = rs[rs.method == m]
        b = x.groupby(["day", "side"]).r_net.mean()
        say(f"  method {m:<17} n {len(x):>5}  bets {len(b):>4}  hit {x.win.mean() * 100:4.1f}% vs random {x.base_p.mean() * 100:4.1f}%  R/call {x.r_net.mean():+.3f}  R/bet {b.mean():+.3f} (t {tstat(b):+.1f})")
    # where would the sweet spot's 'live' record sit in the replay? every stretch of the same number of consecutive sweet-spot calls
    n_live = int(sw.done.sum())
    rr_ = rs.sort_values("made_ms").r_net.to_numpy()
    if len(rr_) > n_live:
        means = np.convolve(rr_, np.ones(n_live) / n_live, mode="valid")
        say(f"  every stretch of {n_live} consecutive sweet-spot calls in the replay: median {np.median(means):+.2f}R a call, 90th percentile {np.percentile(means, 90):+.2f}, 99th {np.percentile(means, 99):+.2f}; "
            f"the live all-time {sw[sw.done].r_net.mean():+.2f}R a call sits at the {np.mean(means < sw[sw.done].r_net.mean()) * 100:.0f}th percentile; the discovery sample's +0.71R a call (28 calls) would be the "
            f"{np.mean(sliding_window_view(rr_, 28).mean(1) < 0.71) * 100:.1f}th percentile of 28-call stretches")

    # ---- the registered predictions
    say()
    say("PREDICTIONS (registered in the docstring before the run)")
    a_f, a_d = bets(sw[sw.fwd & sw.done], "excess"), bets(sw[~sw.fwd & sw.done], "excess")
    a_all = bets(sw[sw.done], "excess")
    say(f"  S1 random-entry R on the sweet-spot geometry {sw[sw.done].rand_r.mean():+.3f}R a call; excess per bet forward {a_f.mean():+.2f} (t {tstat(a_f):+.1f}), discovery {a_d.mean():+.2f} (t {tstat(a_d):+.1f}), all {a_all.mean():+.2f} (t {tstat(a_all):+.1f})")
    say(f"  S2 P(pass) at 30 bets: see C (skeptical / enthusiast posterior)")
    fw_t = {k[1]: v for k, v in slice_t.items() if k[0] == "forward sweet spot" and not math.isnan(v[0])}
    best, worst = max(fw_t.items(), key=lambda kv: kv[1][0]), min(fw_t.items(), key=lambda kv: kv[1][0])
    best_e, worst_e = max(fw_t.items(), key=lambda kv: kv[1][1] if not math.isnan(kv[1][1]) else -99), min(fw_t.items(), key=lambda kv: kv[1][1] if not math.isnan(kv[1][1]) else 99)
    say(f"  S3 forward slices with >= 5 bets ({len(fw_t)}): best t over bets {best[1][0]:+.1f} ({best[0]}, {best[1][2]} bets), worst {worst[1][0]:+.1f} ({worst[0]}, {worst[1][2]} bets); "
        f"best excess-over-random t {best_e[1][1]:+.1f} ({best_e[0]}), worst {worst_e[1][1]:+.1f} ({worst_e[0]})")
    o = tiers.simulate(rows, 20.0, 1.0, pick=lambda r: r["stop_pct"] >= SWEET and r["made_ms"] >= reg)
    say(f"  S4 $20 at 1% risk, forward sweet spot only: ${o['equity']:.2f} ({o['ret'] * 100:+.1f}%)")
    pre = sw[(~sw.fwd) & sw.done]
    say(f"  S5 the discovery cut on the calls MADE SINCE: {sw[sw.fwd & sw.done].r_net.mean():+.2f}R a call over {int((sw.fwd & sw.done).sum())} calls (before: {pre.r_net.mean():+.2f}R over {len(pre)})")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

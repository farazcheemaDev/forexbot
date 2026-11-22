"""THE COMBINATION TEST: every signal the repo can see at the moment of a desk call, in one walk-forward model, scored on 4.7 years and then on the desk's LIVE forward calls (2026-11-15)

THE USER (2026-11-15, /goal): "find an edge that gives good signals - a perfect combination of every signal, or everything you have so far, including the forward data from the Analyst desk."
The Analyst desk logs a call whenever one of its three rules fires (SR bounce, FIB pullback, SMC sweep). Each call is a candidate trade with a fixed bracket (stop / target / hours) and a known outcome in R after the 12bp fee.
THE QUESTION: can a model that sees EVERYTHING available at that moment tell the winners from the losers well enough to trade only the best calls? (This is meta-labelling: the repo's older meta-labelling test, moderate_retests.py, used the daily grid
and one model; this one uses the desk's own calls, ~45 candle features, the panel's 60+ daily signals - funding, positioning, taker flow, open interest, news, tone, unlocks, size / age, fuel, breadth, fear & greed - and the live forward calls.)

DATA   The desk's replay calls (strategy_analysis/data/analyst_replay/calls.json: 2022-02 .. 2026-10-25, the desk's rules unchanged, scored on 1h bars with a bar touching both = a loss, 12bp) for the five crypto markets (XAU / QQQ dropped:
       their calls on a shut market gap through stops, a known fault, and the panel has no coin features for them); the LIVE log (logs/analyst_calls_20261114.csv: 129 resolved calls, 2026-10-27 .. 2026-11-14, never seen by any model fit);
       the panel (strategy_analysis/data/all_sources_panel.npz, daily, 364 coins, to 2026-09-30; positioning / OI to 2026-09-09).
FEATURES (all computed from data up to the call, nothing later)
  geometry   method, side, stop %, target %, reward:risk, hours; the same calls' direction-aligned (x side) context
  P set      candles only (computable for any call, live included): returns 1h .. 30d, ATR % and its ratio, RSI 1h / 1d, Bollinger z and width, position in the 24h range and distance to its edges in ATRs, distance to the 1000h and daily 20 / 50-day
             means, BTC's state, relative strength vs BTC, breadth of the five coins, hour of day, weekday
  E set      P + the panel's coin-day signals at the PREVIOUS day (60+) and its market block
MODELS Ridge (a linear combination of everything, winsorised and standardised on the training fold) and a regularised gradient-boosted tree (depth 3, 150 trees, 150 calls a leaf), each on the P set and on the P + E set = 4 models.
       Target: r_net clipped to [-2, +4] for fitting (heavy right tail); every result is in the RAW r_net.
WALK-FORWARD  quarterly folds from 2023-01-01; a fold trains only on calls made at least 72 hours before it starts (their outcomes are known) and predicts the fold's calls; 2023-01 .. 2026-10 is out of sample for every call.
SELECTION in each fold the top 10% / 20% / 33% of calls by predicted R are 'taken'; 12 cells (4 models x 3 fractions).
UNIT   a bet = one UTC day + one side (one market move settles every same-direction call of the day); uplift per bet = the mean R of the selected calls in the bet minus the mean R of ALL calls of that bet, so the market's drift cancels.
GATE   a cell PASSES when (all): uplift per bet > 0 with t >= 2 over bets; the selected calls' mean R per bet >= +0.05; uplift > 0 in BOTH halves (2023-24, 2025-26); the selected calls' hit rate above the calls' random-entry odds in both halves;
       >= 150 selected bets; Holm-adjusted p < 0.05 over the 12 cells. Then, separately, the live forward calls are read (descriptive: ~40 selected calls cannot confirm anything).

REGISTERED BEFORE THE FIRST RUN (2026-11-15; prior that at least one cell passes: 4%)
  M1  No cell passes.
  M2  Out-of-sample rank IC between predicted and realised R is within +-0.03 for the P models and at most +0.05 for the E models; no model has day-block t >= 2 in both halves.
  M3  Adding the E set (funding, positioning, news ...) to the P set lifts the IC by under 0.01.
  M4  The best cell's uplift per bet is under +0.15R out of sample, while the same cell on its own TRAINING data (in-sample) looks far better (> +0.30R): the model fits noise.
  M5  On the live forward calls the model's top third beats the rest by less than 0.4R a bet with |t| < 2.
  M6  A planted skill (+0.25R x the rank-normal direction-aligned 24h return) IS recovered by the same pipeline (uplift >= +0.15R, t >= 2): the test can see a real signal. A label-shuffled placebo does not pass.

RESULT (2026-11-15; logs/combo_meta.txt; first run under the registered within-bet measure kept in logs/combo_meta_first_run_within_bet_gate.txt) - 0 of 12 cells pass, under BOTH measures.
    10,081 replay calls, 8,220 out of sample (2023-01 on): all calls -0.195R a call, hit 18.1% vs random 19.6%, -0.040 / -0.063R a bet in 2023-24 / 2025-26. Rank IC against R +0.20..+0.25 (day-block range +0.17..+0.27) - but against FEE-FREE R only +0.05..+0.07,
    and the predictions correlate +0.34..+0.43 with stop width: most of that IC is 'prefer wide stops' (a loser's R is -(1 + 0.12% / stop)), not skill. Selected top 10 / 20 / 33% earn -0.05 .. -0.15R a bet against all calls' -0.05: differences -0.097 .. +0.003,
    Welch t -1.7 .. +0.1; the models that also see the panel's 91 daily signals (E) do WORSE (ridge P+E top 10%: -0.097R, t -1.7, 2025-26 selected -0.19R); the E set adds -0.048 (ridge) and +0.005 (trees) of IC. The same model on its OWN training calls: selected +0.068 vs all -0.057
    (t +2.2; under the registered within-bet measure the best tree's in-sample uplift was +0.454R, t +15.5, against +0.026R out of sample): it fits noise. LIVE forward calls (92 resolved crypto calls, never seen by any fit): the models' top half earns +0.16 .. +0.33R a bet against all -0.04
    (Welch t +0.6 .. +1.1, 24 bets); their fee-free IC is +0.22 / +0.23 and 74-80% of what they pick are sweet-spot calls (stop >= 0.8%): they re-learned the stop-width rule, which on the same live calls is +0.28R a bet (t +0.8) and over the replay's out-of-sample years +0.036R (still -0.015R absolute).
    POWER CHECK: a planted +0.25R-per-sd skill is recovered only at selected +0.080R above all (Welch t +1.8) with the rank-normal plant (the first run's raw-z plant: -0.052R within-bet, t -2.2); the shuffled placebo does not pass. The pipeline's reach on the desk's calls is limited to large skills.
    Predictions: M1 right; M2 WRONG on the raw IC (+0.20..+0.25), within +-0.03 only never (fee-free +0.05..+0.07); M3 right; M4 right; M5 right (top third +0.07..+0.15R, t 0.2..0.4; top half +0.37R, t +1.1); M6 WRONG (not recovered at the registered size; the registered measure could not see a market-level skill at all - amended above).
    Tests 20 (tests/test_combo_meta.py); planted bugs 40 of 40 in the full round and the mutants added later (the constant-column fix, the rank-normal plant) all caught; the no-op control survived every round.

AMENDMENT (2026-11-15, AFTER the first run; the first run's log is kept as logs/combo_meta_first_run_within_bet_gate.txt)
  The first run's POWER CHECK failed (M6): a planted +0.25R-per-sd skill on the direction-aligned 24h return was NOT recovered (uplift -0.05R). Cause: the registered 'uplift per bet' compares the selected calls with the other calls of the SAME day + side, which cancels
  any skill that works at the level of the market (the planted 24h return is mostly a market-wide feature; 'be short when the market is falling' is a real kind of edge). A gate that cannot see planted skill is not a gate. The PRIMARY measure is now the selected bets'
  mean R minus the mean R of ALL bets in the same period (Welch t over bets, conservative because the selected bets are a subset of all), with the same other clauses plus 'selected R/bet > 0 in BOTH halves'; the within-bet uplift stays as a diagnostic.
  Also added: the rank IC against FEE-FREE R and against the win flag, because every losing call ends near -1.1R and the tiny differences between them are the fee / stop width: a model that merely prefers wide stops gets a high rank IC with no skill.
  What the first run showed under the registered measure (no cell passes; every within-bet uplift inside +-0.03R; the best cell's in-sample uplift +0.454R against +0.026R out of sample; the IC +0.20..+0.25) is in that log.

    python -m backtest.combo_meta        writes logs/combo_meta.txt          tests: python tests/test_combo_meta.py
"""
from __future__ import annotations

import json
import math
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOG = ROOT / "logs" / "combo_meta.txt"
REPLAY = ROOT / "strategy_analysis" / "data" / "analyst_replay"
PANEL = ROOT / "strategy_analysis" / "data" / "all_sources_panel.npz"
EXT = ROOT / "strategy_analysis" / "data" / "combo_meta"
LIVE = ROOT / "logs" / "analyst_calls_20261114.csv"
SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]
H1 = 3_600_000
D1 = 86_400_000
FIRST_OOS = pd.Timestamp("2023-01-01")
HALF_SPLIT = pd.Timestamp("2025-01-01")
PANEL_CALLS_UNTIL = pd.Timestamp("2026-09-10")        # the panel's positioning / OI features end 2026-09-09
EMBARGO_MS = 72 * H1
CLIP_LO, CLIP_HI = -2.0, 4.0
FRACS = (0.10, 0.20, 0.33)
MIN_TRAIN = 1500
MIN_BETS = 150
SCREEN_K = 8                                           # the screened ridge keeps the K features most correlated with the (clipped) outcome ON THE TRAINING FOLD
MIN_SEL_R = 0.05
METHODS = ("SR", "FIB", "SMC")


# ------------------------------------------------------------------ candles -> per-symbol feature frames

def load_bars(sym: str, extend: bool = False) -> pd.DataFrame:
    """1h candles indexed by open time (ms): o h l c. extend=True appends fresh public candles (cached in EXT) so live calls have their history."""
    b = np.array(json.loads((REPLAY / f"{sym}_1h.json").read_text()), float)[:, :5]
    if extend:
        f = EXT / f"{sym}_ext.json"
        have = json.loads(f.read_text()) if f.exists() else []
        last = max(int(b[-1, 0]), int(have[-1][0]) if have else 0)
        import desk
        now = desk.now_ms()
        if last < now - 2 * H1:
            new = desk.klines(sym, "1h", last + H1, None, 1500)
            have += [list(x) for x in new if x[0] > last]
            EXT.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(have))
        if have:
            b = np.vstack([b, np.array(have, float)])
        _, keep = np.unique(b[:, 0], return_index=True)
        b = b[np.sort(keep)]
    df = pd.DataFrame(b[:, 1:], index=b[:, 0].astype("int64"), columns=["o", "h", "l", "c"])
    return df[~df.index.duplicated()].sort_index()


def wilder_rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def symbol_features(b: pd.DataFrame) -> pd.DataFrame:
    """Candle features at every hourly bar, each a function of bars up to and including that bar. Indexed by the bar's open time."""
    c, h, l = b.c, b.h, b.l
    lr = np.log(c)
    f = pd.DataFrame(index=b.index)
    for k in (1, 4, 24, 72, 168, 720):
        f[f"ret{k}"] = lr - lr.shift(k)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    f["atr_pct"] = atr / c
    f["atr_ratio"] = atr / atr.rolling(720).mean()
    f["rsi1h"] = wilder_rsi(c)
    sma, sd = c.rolling(20).mean(), c.rolling(20).std()
    f["bb_z"] = (c - sma) / sd
    f["bb_w"] = 4 * sd / sma
    hi24, lo24 = h.rolling(24).max(), l.rolling(24).min()
    f["rng_pos24"] = (c - lo24) / (hi24 - lo24).replace(0, np.nan)
    f["d_hi24_atr"] = (hi24 - c) / atr
    f["d_lo24_atr"] = (c - lo24) / atr
    f["d_ma1000"] = c / c.rolling(1000).mean() - 1
    hv = lr.diff().rolling(720).std()
    f["z_ret24"] = f["ret24"] / (hv * math.sqrt(24))
    # daily context from the previous COMPLETE UTC day, carried to every hour of the next day
    day = (b.index.to_numpy() // D1)
    dc = c.groupby(day).last()
    dd = pd.DataFrame(index=dc.index)
    dd["d_ret1"] = np.log(dc).diff(1)
    dd["d_ret7"] = np.log(dc).diff(7)
    dd["d_ret30"] = np.log(dc).diff(30)
    dd["d_rsi"] = wilder_rsi(dc)
    dd["d_sma20"] = dc / dc.rolling(20).mean() - 1
    dd["d_sma50"] = dc / dc.rolling(50).mean() - 1
    dd = dd.shift(1)                                                        # known from 00:00 UTC of the NEXT day
    for k in dd.columns:
        f[k] = dd[k].reindex(day).to_numpy()
    return f


def market_frame(feats: dict) -> pd.DataFrame:
    """BTC's state and the breadth of the five coins at each hour (same index for all crypto symbols)."""
    btc = feats["BTCUSDT"]
    m = pd.DataFrame(index=btc.index)
    m["btc_ret24"] = btc.ret24
    m["btc_ret168"] = btc.ret168
    m["btc_d_ma1000"] = btc.d_ma1000
    m["btc_atr_ratio"] = btc.atr_ratio
    r24 = pd.concat([feats[s].ret24.reindex(btc.index) for s in SYMS], axis=1)
    m["breadth24"] = (r24 > 0).mean(axis=1)
    m["mkt_ret24"] = r24.mean(axis=1)
    return m


# ------------------------------------------------------------------ calls -> features

ALIGN_P = ["ret24", "ret168", "d_ma1000", "bb_z", "rng_pos24", "d_sma50", "d_ret7", "rel_btc24", "rel_btc168", "btc_ret24", "mkt_ret24"]
ALIGN_E = ["f_fund1", "f_fund7", "f_crowd", "f_top_acc", "f_top_pos", "f_taker1", "f_taker7", "f_oi_chg1", "f_oi_chg7", "f_crowd_chg7", "f_ret1", "f_ret7", "f_ret30", "f_rel_btc7", "f_ema_d20", "f_ema_d50",
           "f_close_loc", "m_btc_ret7"]


def call_features(calls: pd.DataFrame, feats: dict, mkt: pd.DataFrame) -> pd.DataFrame:
    """P-set features per call. The call reads the last CLOSED hourly bar: the bar that opened one hour before the hour the call was made in."""
    out = []
    for sym, g in calls.groupby("symbol"):
        f, i_open = feats[sym], (g.made_ms.to_numpy() // H1) * H1 - H1
        x = f.reindex(i_open)
        mm = mkt.reindex(i_open)
        x.index, mm.index = g.index, g.index
        x = pd.concat([x, mm], axis=1)
        x["rel_btc24"] = x.ret24 - x.btc_ret24
        x["rel_btc168"] = x.ret168 - x.btc_ret168
        out.append(x)
    x = pd.concat(out).loc[calls.index]
    side = np.where(calls.side == "long", 1.0, -1.0)
    x["side"] = side
    x["stop_pct"], x["target_pct"], x["rr"], x["hours"] = calls.stop_pct, calls.target_pct, calls.rr, calls.hours
    x["log_stop"] = np.log(calls.stop_pct)
    for m in METHODS:
        x[f"m_{m}"] = (calls.method == m).astype(float)
    ts = pd.to_datetime(calls.made_ms, unit="ms")
    x["hour_sin"], x["hour_cos"] = np.sin(2 * np.pi * ts.dt.hour / 24), np.cos(2 * np.pi * ts.dt.hour / 24)
    x["dow"] = ts.dt.dayofweek.astype(float)
    x["rsi_aligned"] = (x.rsi1h - 50) * side
    x["d_rsi_aligned"] = (x.d_rsi - 50) * side
    for k in ALIGN_P:
        x[f"a_{k}"] = x[k] * side
    return x


def panel_features(calls: pd.DataFrame) -> pd.DataFrame:
    """E-set features: the panel's coin-day and market signals at the day BEFORE the call (row d-1), plus the direction-aligned versions."""
    z = np.load(PANEL, allow_pickle=True)
    dates, coins = z["dates"], list(z["coins"])
    day = pd.to_datetime(calls.made_ms // D1 * D1, unit="ms").to_numpy().astype("datetime64[D]") - np.timedelta64(1, "D")
    row = np.searchsorted(dates, day)
    ok = (row < len(dates)) & (dates[np.clip(row, 0, len(dates) - 1)] == day)
    ci = np.array([coins.index(s) for s in calls.symbol])
    cols = {}
    side = np.where(calls.side == "long", 1.0, -1.0)
    for k in z.files:
        if k.startswith("f_"):
            a = z[k][np.clip(row, 0, len(dates) - 1), ci].astype(float)
            cols[k] = np.where(ok, a, np.nan)
        elif k.startswith("m_"):
            a = z[k]
            a = (a[np.clip(row, 0, len(dates) - 1)] if a.ndim == 1 else a[np.clip(row, 0, len(dates) - 1), 0]).astype(float)
            cols[k] = np.where(ok, a, np.nan)
    e = pd.DataFrame(cols, index=calls.index)
    for k in ALIGN_E:
        if k in e:
            e[f"a_{k}"] = e[k] * side
    return e


def load_replay_calls() -> pd.DataFrame:
    c = pd.DataFrame(json.loads((REPLAY / "calls.json").read_text()))
    c = c[c.symbol.isin(SYMS)].copy()
    c["target_pct"] = (c.target - c.entry).abs() / c.entry
    c["rr"] = c.target_pct / c.stop_pct
    c["hours"] = np.where(c.method == "FIB", 48, 24)
    return finish_calls(c.sort_values("made_ms").reset_index(drop=True))


def load_live_calls(path=LIVE) -> pd.DataFrame:
    c = pd.read_csv(path)
    c = c[c.symbol.isin(SYMS) & c.status.isin(["WIN", "LOSS", "EXPIRED"]) & c.r_net.notna()].copy()
    c["hours"] = ((c.expires_ms - c.made_ms) / H1).round().astype(int)
    c["exit_ms"] = c.exit_ms.astype(float)
    return finish_calls(c.sort_values("made_ms").reset_index(drop=True))


def finish_calls(c: pd.DataFrame) -> pd.DataFrame:
    c["t"] = pd.to_datetime(c.made_ms, unit="ms")
    c["day"] = c.t.dt.strftime("%Y-%m-%d")
    c["win"] = (c.status == "WIN").astype(float)
    return c


def build_table(calls: pd.DataFrame, extend: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    bars = {s: load_bars(s, extend) for s in SYMS}
    feats = {s: symbol_features(bars[s]) for s in SYMS}
    mkt = market_frame(feats)
    return call_features(calls, feats, mkt), panel_features(calls)


# ------------------------------------------------------------------ models

class Prep:
    """Median-impute, winsorise at the 1st / 99th percentile and standardise, all learned on the training fold only (for the linear model)."""

    def fit(self, X: np.ndarray):
        self.med = np.nanmedian(X, axis=0)
        self.med = np.where(np.isfinite(self.med), self.med, 0.0)
        Xf = np.where(np.isfinite(X), X, self.med)
        self.lo, self.hi = np.percentile(Xf, 1, axis=0), np.percentile(Xf, 99, axis=0)
        Xc = np.clip(Xf, self.lo, self.hi)
        self.mu, self.sd = Xc.mean(0), Xc.std(0)
        self.sd = np.where(self.sd > 1e-12, self.sd, 1.0)
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        Xf = np.where(np.isfinite(X), X, self.med)
        return (np.clip(Xf, self.lo, self.hi) - self.mu) / self.sd


def usable_columns(X: np.ndarray) -> np.ndarray:
    """Columns with at least two distinct finite values in this training fold (a constant or all-missing signal cannot be binned, and carries nothing)."""
    return pd.DataFrame(X).nunique(dropna=True).to_numpy() >= 2


def screen_top(Z: np.ndarray, y: np.ndarray, k: int) -> np.ndarray:
    """Indices of the k standardised features with the largest |correlation| with the outcome (training fold only)."""
    ys = (y - y.mean()) / (y.std() if y.std() > 1e-12 else 1.0)
    corr = np.abs(Z.T @ ys) / len(Z)
    return np.argsort(-corr, kind="stable")[:k]


def fit_model(kind: str, Xtr: np.ndarray, ytr: np.ndarray, seed: int = 0):
    """Fit once, return a predict function. Target clipped for fitting only; unusable columns dropped on the training fold."""
    y = np.clip(ytr, CLIP_LO, CLIP_HI)
    keep = usable_columns(Xtr)
    Xk = Xtr[:, keep]
    if kind == "ridge":
        p = Prep().fit(Xk)
        m = Ridge(alpha=300.0).fit(p.transform(Xk), y)
        return lambda X: m.predict(p.transform(X[:, keep]))
    if kind == "sridge":
        p = Prep().fit(Xk)
        Z = p.transform(Xk)
        top = screen_top(Z, y, SCREEN_K)
        m = Ridge(alpha=10.0).fit(Z[:, top], y)
        return lambda X: m.predict(p.transform(X[:, keep])[:, top])
    m = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=150, l2_regularization=10.0, random_state=seed).fit(Xk, y)
    return lambda X: m.predict(X[:, keep])


def fit_predict(kind: str, Xtr: np.ndarray, ytr: np.ndarray, Xte: np.ndarray, seed: int = 0) -> np.ndarray:
    return fit_model(kind, Xtr, ytr, seed)(Xte)


def fold_starts(t: pd.Series, first=FIRST_OOS) -> list:
    qs = list(pd.date_range(first, t.max(), freq="QS"))
    return qs + [t.max() + pd.Timedelta(days=2)]


def walk_forward(calls: pd.DataFrame, X: pd.DataFrame, kind: str, first=FIRST_OOS, y: np.ndarray | None = None) -> pd.DataFrame:
    """Out-of-sample prediction for every call from `first` on. Returns a frame with pred, fold (fold start), in-sample prediction of the same call set trained on (for the overfit check)."""
    y = calls.r_net.to_numpy() if y is None else y
    t_ms = calls.made_ms.to_numpy()
    starts = fold_starts(calls.t, first)
    pred = np.full(len(calls), np.nan)
    fold = np.full(len(calls), np.datetime64("NaT"), dtype="datetime64[ns]")
    ins = np.full(len(calls), np.nan)
    Xv = X.to_numpy(float)
    for a, b in zip(starts[:-1], starts[1:]):
        te = ((calls.t >= a) & (calls.t < b)).to_numpy()
        tr = t_ms + EMBARGO_MS < int(a.timestamp() * 1000)
        if te.sum() == 0 or tr.sum() < MIN_TRAIN:
            continue
        model = fit_model(kind, Xv[tr], y[tr])
        pred[te] = model(Xv[te])
        fold[te] = np.datetime64(a)
        idx = np.flatnonzero(tr)[-max(300, int(tr.sum()) // 4):]          # the last quarter of the model's OWN training calls, for the in-sample comparison
        ins[idx] = model(Xv[idx])
    return pd.DataFrame({"pred": pred, "fold": fold, "ins": ins}, index=calls.index)


# ------------------------------------------------------------------ evaluation

def bet_table(x: pd.DataFrame) -> pd.DataFrame:
    return x.groupby(["day", "side"]).agg(R=("r_net", "mean"))


def tstat(v) -> float:
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    return float(v.mean() / (v.std(ddof=1) / math.sqrt(len(v)))) if len(v) >= 5 and v.std(ddof=1) > 1e-9 else float("nan")


def p_up(t: float) -> float:
    return 1.0 if not np.isfinite(t) else float(0.5 * math.erfc(t / math.sqrt(2)))


def holm(ps) -> np.ndarray:
    ps = np.asarray(ps, float)
    order = np.argsort(ps)
    m = len(ps)
    adj, run = np.empty(m), 0.0
    for rank, k in enumerate(order):
        run = max(run, (m - rank) * ps[k])
        adj[k] = min(1.0, run)
    return adj


def select(df: pd.DataFrame, pred_col: str, frac: float) -> pd.Series:
    """True for the top `frac` of calls by prediction within each fold."""
    rk = df.groupby("fold")[pred_col].rank(pct=True, method="first")
    return rk > 1.0 - frac


def half_stats(df: pd.DataFrame, sel: pd.Series) -> dict:
    """Selected calls against ALL calls, per independent bet (UTC day + side). PRIMARY: the mean R of the bets that contain a selected call (each bet = its selected calls' mean R) minus the mean R of ALL bets in the same
    period, Welch t over bets (conservative: the selected bets are a subset of all bets). DIAGNOSTIC: the within-bet uplift (selected minus all calls of the SAME bet), which cancels any skill at the level of the market."""
    s = df[sel]
    nan = float("nan")
    if len(s) == 0:
        return dict(n=0, bets=0, all_bets=0, sel_r=nan, all_r=nan, diff=nan, t=nan, uplift=nan, t_within=nan, hit=nan, base=nan)
    b_all = df.groupby(["day", "side"]).r_net.mean()
    b_sel = s.groupby(["day", "side"]).r_net.mean()
    up = (b_sel - b_all.reindex(b_sel.index)).to_numpy()
    ns, na = len(b_sel), len(b_all)
    diff = float(b_sel.mean() - b_all.mean())
    se = math.sqrt(b_sel.var(ddof=1) / ns + b_all.var(ddof=1) / na) if ns >= 5 and na >= 5 else nan
    return dict(n=len(s), bets=ns, all_bets=na, sel_r=float(b_sel.mean()), all_r=float(b_all.mean()), diff=diff, t=(diff / se if se and se > 1e-12 else nan),
                uplift=float(up.mean()), t_within=tstat(up), hit=float(s.win.mean()), base=float(s.base_p.mean()))


def cell(df: pd.DataFrame, pred_col: str, frac: float) -> dict:
    d = df[df[pred_col].notna()].copy()
    sel = select(d, pred_col, frac)
    a, b = d.t < HALF_SPLIT, d.t >= HALF_SPLIT
    full = half_stats(d, sel)
    h1, h2 = half_stats(d[a], sel[a]), half_stats(d[b], sel[b])
    return dict(full=full, h1=h1, h2=h2, p=p_up(full["t"]))


def passes(c: dict, adj_p: float) -> bool:
    f, h1, h2 = c["full"], c["h1"], c["h2"]
    return bool(f["bets"] >= MIN_BETS and f["t"] >= 2.0 and f["diff"] > 0 and f["sel_r"] >= MIN_SEL_R and h1["diff"] > 0 and h2["diff"] > 0 and h1["sel_r"] > 0 and h2["sel_r"] > 0
                and h1["hit"] > h1["base"] and h2["hit"] > h2["base"] and adj_p < 0.05)


def rank_ic(df: pd.DataFrame, pred_col: str, rng, boots: int = 400) -> tuple:
    """Spearman IC over all calls, with a day-block bootstrap range (resample whole days; pooled Pearson of the global ranks from per-day sums)."""
    d = df[df[pred_col].notna()]
    ic = float(sps.spearmanr(d[pred_col], d.r_net)[0])
    x, y = d[pred_col].rank().to_numpy(), d.r_net.rank().to_numpy()
    codes, _ = pd.factorize(d.day)
    k = codes.max() + 1
    S = np.zeros((k, 6))
    for j, v in enumerate((np.ones(len(d)), x, y, x * x, y * y, x * y)):
        S[:, j] = np.bincount(codes, weights=v, minlength=k)
    ics = []
    for _ in range(boots):
        w = rng.multinomial(k, np.full(k, 1.0 / k)).astype(float)
        n, sx, sy, sxx, syy, sxy = w @ S
        den = math.sqrt(max(n * sxx - sx * sx, 1e-12) * max(n * syy - sy * sy, 1e-12))
        ics.append((n * sxy - sx * sy) / den)
    lo, hi = np.percentile(ics, [2.5, 97.5])
    return ic, float(lo), float(hi)


def plant(calls: pd.DataFrame, X: pd.DataFrame, strength: float) -> np.ndarray:
    """Labels with a KNOWN skill added: +strength R per standard deviation of the direction-aligned 24h return, taken as a RANK-NORMAL score (a heavy-tailed return z-scored by its raw sd would barely move most calls)."""
    a = X["a_ret24"].to_numpy(float)
    ok = np.isfinite(a)
    z = np.zeros(len(a))
    z[ok] = sps.norm.ppf((sps.rankdata(a[ok]) - 0.5) / ok.sum())
    return calls.r_net.to_numpy() + strength * z


# ------------------------------------------------------------------ the run

def feature_sets(Xp: pd.DataFrame, Xe: pd.DataFrame) -> dict:
    return {"P": Xp, "P+E": pd.concat([Xp, Xe], axis=1)}


def run_models(calls: pd.DataFrame, sets: dict, y: np.ndarray | None = None, kinds=("ridge", "hgb")) -> dict:
    out = {}
    for name, X in sets.items():
        sub = calls if name == "P" else calls[calls.t < PANEL_CALLS_UNTIL]
        Xs = X.loc[sub.index]
        for kind in kinds:
            yy = None if y is None else pd.Series(y, index=calls.index).loc[sub.index].to_numpy()
            wf = walk_forward(sub, Xs, kind, y=yy)
            out[f"{kind} {name}"] = (sub, wf)
    return out


def table(calls: pd.DataFrame, models: dict, fracs=FRACS) -> list:
    rows = []
    for mname, (sub, wf) in models.items():
        d = sub.join(wf)
        for fr in fracs:
            rows.append((mname, fr, cell(d, "pred", fr)))
    adj = holm([r[2]["p"] for r in rows])
    return [(m, fr, c, float(a)) for (m, fr, c), a in zip(rows, adj)]


def fmt_cell(m: str, fr: float, c: dict, adj: float) -> str:
    f, h1, h2 = c["full"], c["h1"], c["h2"]
    return (f"  {m:<11} top {int(fr * 100):>2}%  n {f['n']:>5} bets {f['bets']:>4}/{f['all_bets']}  selected R/bet {f['sel_r']:+.3f} vs all {f['all_r']:+.3f} = {f['diff']:+.3f} (Welch t {f['t']:+.1f})  "
            f"hit {f['hit'] * 100:4.1f}% vs random {f['base'] * 100:4.1f}%  halves: diff {h1['diff']:+.3f} / {h2['diff']:+.3f}, selected {h1['sel_r']:+.3f} / {h2['sel_r']:+.3f}  "
            f"[within-bet uplift {f['uplift']:+.3f} (t {f['t_within']:+.1f})]  Holm p {adj:.3f}  {'PASS' if passes(c, adj) else 'no'}")


def main():
    out = []

    def say(s=""):
        print(s, flush=True)
        out.append(s)

    rng = np.random.default_rng(20261115)
    calls = load_replay_calls()
    Xp, Xe = build_table(calls, extend=False)
    sets = feature_sets(Xp, Xe)
    say(f"backtest/combo_meta.py, {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC; {len(calls):,} replay calls ({calls.t.min():%Y-%m-%d} .. {calls.t.max():%Y-%m-%d}), 5 crypto markets; "
        f"{Xp.shape[1]} candle features (P), {Xe.shape[1]} panel features (E); walk-forward quarterly folds from {FIRST_OOS:%Y-%m-%d}, embargo 72h")
    say(f"all calls out of sample: {int((calls.t >= FIRST_OOS).sum()):,} calls, mean R {calls[calls.t >= FIRST_OOS].r_net.mean():+.3f} a call, hit {calls[calls.t >= FIRST_OOS].win.mean() * 100:.1f}% vs random {calls[calls.t >= FIRST_OOS].base_p.mean() * 100:.1f}%")
    models = run_models(calls, sets)
    say()
    say("OUT-OF-SAMPLE RANK IC (day-block bootstrap 95% range) against: realised R / FEE-FREE R (R + 0.12% / stop: removes the stop-width tie-break among losers) / the win flag; plus the in-sample IC and the prediction's correlation with stop width")
    for m, (sub, wf) in models.items():
        d = sub.join(wf)
        d["r_gross"] = d.r_net + 0.0012 / d.stop_pct
        ic, lo, hi = rank_ic(d, "pred", rng)
        dd = d[d.pred.notna()]
        ic_g = float(sps.spearmanr(dd.pred, dd.r_gross)[0])
        ic_w = float(sps.spearmanr(dd.pred, dd.win)[0])
        ic_sp = float(sps.spearmanr(dd.pred, dd.stop_pct)[0])
        i2 = d[d.ins.notna()]
        ic_in = float(sps.spearmanr(i2.ins, i2.r_net)[0]) if len(i2) > 10 else float("nan")
        say(f"  {m:<11} R {ic:+.3f} [{lo:+.3f}, {hi:+.3f}] | fee-free R {ic_g:+.3f} | win flag {ic_w:+.3f} | in-sample {ic_in:+.3f} | corr with stop width {ic_sp:+.3f}")
    oos = calls[calls.t >= FIRST_OOS]
    for lab, x in (("2023-24", oos[oos.t < HALF_SPLIT]), ("2025-26", oos[oos.t >= HALF_SPLIT])):
        b_ = bet_table(x)
        say(f"  reference, ALL calls {lab}: {len(x):,} calls, {len(b_):,} bets, {x.r_net.mean():+.3f}R a call, {b_.R.mean():+.3f}R a bet")
    say()
    say("THE 12 CELLS (selected = the top fraction by predicted R in each fold; uplift per bet = selected minus all calls of the same day + side)")
    tb = table(calls, models)
    for m, fr, c, adj in tb:
        say(fmt_cell(m, fr, c, adj))
    npass = sum(passes(c, a) for _, _, c, a in tb)
    say(f"  cells passing: {npass} of {len(tb)}")
    best = max(tb, key=lambda r: r[2]["full"]["diff"] if np.isfinite(r[2]["full"]["diff"]) else -9)
    m, fr, c, adj = best
    sub, wf = models[m]
    d = sub.join(wf)
    d_in = d[d.ins.notna()].copy()
    d_in["fold"] = 0
    ins_sel = select(d_in, "ins", fr)
    ins = half_stats(d_in, ins_sel)
    say(f"  best cell by difference: {m} top {int(fr * 100)}%: out-of-sample selected {c['full']['sel_r']:+.3f} vs all {c['full']['all_r']:+.3f} R a bet; the SAME model on its own training calls (in-sample): selected {ins['sel_r']:+.3f} vs all {ins['all_r']:+.3f} (t {ins['t']:+.1f})")

    # ---- what the E set adds
    say()
    say("WHAT THE RICH SIGNALS ADD (IC of P+E minus P, same calls)")
    for kind in ("ridge", "hgb"):
        sp, wp = models[f"{kind} P"]
        se, we = models[f"{kind} P+E"]
        dp, de = sp.join(wp), se.join(we)
        dp = dp[dp.index.isin(de.index) & dp.pred.notna()]
        de = de.loc[dp.index]
        say(f"  {kind}: P {sps.spearmanr(dp.pred, dp.r_net)[0]:+.3f}  P+E {sps.spearmanr(de.pred, de.r_net)[0]:+.3f}  (on the {len(dp):,} calls the panel covers)")

    # ---- the planted-skill power check and the shuffled placebo
    say()
    say("POWER CHECK: the same pipeline on labels with a KNOWN skill planted (+0.25R per sd of the direction-aligned 24h return) and on a label-shuffled placebo (ridge P, top 20%)")
    yp = plant(calls, Xp, 0.25)
    ysh = calls.r_net.to_numpy().copy()
    rng.shuffle(ysh)
    for lab, y in (("planted", yp), ("placebo (shuffled labels)", ysh)):
        c2 = calls.copy()
        c2["r_net"] = y
        wf = walk_forward(c2, Xp, "ridge", y=y)
        d = c2.join(wf)
        cc = cell(d, "pred", 0.20)
        say(f"  {lab:<26} selected {cc['full']['sel_r']:+.3f} vs all {cc['full']['all_r']:+.3f} R a bet = {cc['full']['diff']:+.3f} (Welch t {cc['full']['t']:+.1f}), halves {cc['h1']['diff']:+.3f} / {cc['h2']['diff']:+.3f}; within-bet uplift {cc['full']['uplift']:+.3f}")

    # ---- the live forward calls
    say()
    say("THE LIVE FORWARD CALLS (never seen by any fit; the P-set models trained on ALL replay calls up to 2026-10-25; candles to now)")
    live = load_live_calls()
    Xl, _ = build_table(live, extend=True)
    Xtr = Xp.to_numpy(float)
    ytr = calls.r_net.to_numpy()
    live = live.copy()
    say(f"  {len(live)} resolved live crypto calls, {live.day.nunique()} days; all calls: {live.r_net.mean():+.3f}R a call, hit {live.win.mean() * 100:.0f}% vs random {live.base_p.mean() * 100:.0f}%")
    for kind in ("ridge", "hgb"):
        live[f"pred_{kind}"] = fit_predict(kind, Xtr, ytr, Xl.reindex(columns=Xp.columns).to_numpy(float))
        ic = sps.spearmanr(live[f"pred_{kind}"], live.r_net)[0]
        live["fold"] = 0
        for fr in (0.33, 0.50):
            sel = select(live, f"pred_{kind}", fr)
            st_ = half_stats(live, sel)
            say(f"  {kind} P: IC {ic:+.3f};  top {int(fr * 100)}%: n {st_['n']} bets {st_['bets']}  selected R/bet {st_['sel_r']:+.2f} vs all {st_['all_r']:+.2f} = {st_['diff']:+.2f} (Welch t {st_['t']:+.1f})  hit {st_['hit'] * 100:.0f}% vs random {st_['base'] * 100:.0f}%")
    live["r_gross"] = live.r_net + 0.0012 / live.stop_pct
    for kind in ("ridge", "hgb"):
        sel = select(live, f"pred_{kind}", 0.50)
        say(f"  {kind} P: fee-free IC {sps.spearmanr(live[f'pred_{kind}'], live.r_gross)[0]:+.3f}; corr of the prediction with stop width {sps.spearmanr(live[f'pred_{kind}'], live.stop_pct)[0]:+.3f}; "
            f"{(live[sel].stop_pct >= 0.008).mean() * 100:.0f}% of the top-50% calls are sweet-spot calls (stop >= 0.8%) against {(live.stop_pct >= 0.008).mean() * 100:.0f}% of all")
    sw = live[live.stop_pct >= 0.008]
    live["fold"] = 0
    plain_live = half_stats(live, live.stop_pct >= 0.008)
    say(f"  the plain rule 'stop >= 0.8%' on the same live calls: {plain_live['n']} calls, selected {plain_live['sel_r']:+.2f} vs all {plain_live['all_r']:+.2f} R a bet = {plain_live['diff']:+.2f} (Welch t {plain_live['t']:+.1f}); live sweet-spot calls {sw.r_net.mean():+.3f}R a call")
    oosr = calls[calls.t >= FIRST_OOS].copy()
    oosr["fold"] = 0
    plain = half_stats(oosr, oosr.stop_pct >= 0.008)
    say(f"  the same plain rule over the replay's out-of-sample years: {plain['n']:,} calls, selected {plain['sel_r']:+.3f} vs all {plain['all_r']:+.3f} R a bet = {plain['diff']:+.3f} (Welch t {plain['t']:+.1f}): the stop-width effect alone"
        f" (a wider stop shrinks the fee), still negative in absolute R")

    say()
    say("PREDICTIONS (registered before the run)")
    say(f"  M1 cells passing: {npass} of {len(tb)}")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

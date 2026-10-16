"""Episode check for ndx_aplus_ticks.py top 0.1% (2026-10-13): are the 396 calls independent? RESULT (logs/ndx_aplus_ticks_check.txt):
396 calls = 7 episodes (>10 min apart) on 6 days (two on 2026-09-07, US Labor Day); 6 of 7 episodes won (binomial p ~0.06
for 7 coin flips) - the 70% is a handful of events counted ~57 times each, not a setup.

    python -m backtest.ndx_aplus_ticks_check
"""
import pickle, sys, numpy as np, pandas as pd
from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest.ndx_aplus_ticks as A
from sklearn.ensemble import HistGradientBoostingClassifier
cache = pickle.loads(open(str(Path(__file__).resolve().parents[1]) + "/strategy_analysis/data/ustec_tick_days.pkl","rb").read())
days = sorted(d for d, v in cache.items() if v is not None); cut = days[int(len(days)*0.6)]
fr = []
for d in days:
    F, (g, gm, gsp) = A.day_frame(*cache[d]); F = A.extra(F, gm)
    idx = np.arange(900, len(F)-1, A.STEP); y, pu, pdn = A.races(gm, gsp, idx)
    s = F.iloc[idx][A.FEATS].copy(); s["y"], s["pu"], s["pd"], s["day"], s["sec"] = y, pu, pdn, d, g[idx]; fr.append(s)
D = pd.concat(fr, ignore_index=True); D = D[D.y.notna()]
tr, te = D[D.day < cut], D[D.day >= cut]
m = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_leaf_nodes=63, min_samples_leaf=200, l2_regularization=1.0, random_state=0).fit(tr[A.FEATS], tr.y)
te = te.copy(); te["p"] = m.predict_proba(te[A.FEATS])[:,1]; te["conf"] = (te.p-0.5).abs()
top = te.nlargest(int(len(te)*0.001), "conf").copy()
top["won"] = ((top.y==1)==(top.p>0.5)); top["net"] = np.where(top.p>0.5, top.pu, top.pd)
top = top.sort_values(["day","sec"])
top["ep"] = ((top.day != top.day.shift()) | (top.sec.diff() > 600)).cumsum()
e = top.groupby("ep").agg(day=("day","first"), n=("won","size"), won=("won","mean"), net=("net","mean"), up=("p", lambda v: (v>0.5).mean()))
print("calls", len(top), "days", top.day.nunique(), "episodes (>10 min apart)", len(e))
print(e.sort_values("n", ascending=False).head(12).to_string())
print("episode-weighted: won", round(e.won.mean()*100,1), "% net", round(e.net.mean(),2), "| episodes won majority", (e.won>0.5).sum(), "of", len(e))
print("first call of each episode: won", round(top.groupby('ep').won.first().mean()*100,1), "% net", round(top.groupby('ep').net.first().mean(),2))

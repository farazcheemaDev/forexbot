"""HIS FIRST TRADE OF EACH SITTING vs HIS LATER TICKETS (2026-11-03)

Origin: the LLM council on "what could the secret of the NASDAQ trader's edge be" (2026-11-02/03). Its top 'the record is built, not foreseen' hypothesis (Expansionist, ~40%; also the First Principles and Outsider
advisors): averaging down, hedging and re-entering after a pullback inflate a race that is ordinary at the first click, so the FIRST ticket of a sitting should look ordinary and the later tickets carry the wins.
This splits the 46 NASDAQ trades of logs/his_vs_market.csv (his result in points, the market's best and worst excursion during the hold, the hold in seconds) into sittings (a new sitting after a gap of more than
30 minutes) and compares the first ticket with the later ones.

STATED BEFORE THE RUN (2026-11-03, in chat): S1 - if the record were built by add-ons, first tickets would look ordinary (lower win rate, deeper worst excursion than the later ones). Not stated beforehand:
how many sittings are single trades (the table shows it).

RESULT (logs/his_sittings.txt): 22 of 31 sittings are ONE trade. First tickets: 29 of 31 closed in profit (93.5%), mean +9.22 points, median worst excursion -4.76; later tickets: 15 of 15, +9.07, -4.75. Only 1
sitting began with a loss and finished green. S1 is refuted: nothing is built by later tickets. Caveats: 46 trades; 'closed in profit' is partly structure (a 7-point target with no stop wins ~83% even at random
entries - his_strategy s25); the measure that separates him from chance is the +7/-7 race (88% vs 55%), which this table does not hold.

    python -m backtest.his_sittings        writes logs/his_sittings.txt          tests: python tests/test_his_sittings.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SITTING_GAP_S = 30 * 60


def sittings(d: pd.DataFrame, gap_s: int = SITTING_GAP_S) -> pd.DataFrame:
    """Add `sit` (sitting number) and `k` (0 = first ticket of its sitting). A new sitting starts when more than gap_s seconds passed since the previous trade."""
    d = d.sort_values("o", kind="stable").reset_index(drop=True)
    gap = d.o.diff().dt.total_seconds().fillna(float("inf"))
    d["sit"] = (gap > gap_s).cumsum() - 1                      # 0-based; the first trade always opens sitting 0
    d["k"] = d.groupby("sit").cumcount()
    return d


def row(name: str, g: pd.DataFrame) -> str:
    return (f"{name:<18} n {len(g):>3}  closed in profit {(g.pts > 0).mean() * 100:5.1f}%  mean pts {g.pts.mean():+6.2f}  median pts {g.pts.median():+5.2f}  "
            f"median worst excursion {g.mae.median():+6.2f}  worse than -10: {(g.mae <= -10).mean() * 100:4.1f}%  median hold {g.hold.median():5.0f}s")


def main():
    d = sittings(pd.read_csv(ROOT / "logs" / "his_vs_market.csv", parse_dates=["o"]))
    first = d[d.k == 0]
    later = d[d.k > 0]
    s = d.groupby("sit").agg(n=("pts", "size"), total=("pts", "sum"), first_pts=("pts", "first"))
    out = [f"backtest/his_sittings.py - {len(d)} NASDAQ trades in {d.sit.nunique()} sittings (a new sitting after a gap of more than {SITTING_GAP_S // 60} minutes); sitting sizes {s.n.value_counts().sort_index().to_dict()}",
           row("all", d), row("first of sitting", first), row("later tickets", later), row("2nd ticket", d[d.k == 1]), row("3rd and later", d[d.k >= 2]),
           f"sittings that finished green: {(s.total > 0).mean() * 100:.0f}% of {len(s)}; first ticket alone green: {(s.first_pts > 0).mean() * 100:.0f}%; "
           f"began with a loss and finished green: {int(((s.first_pts <= 0) & (s.total > 0)).sum())}"]
    txt = "\n".join(out)
    print(txt)
    (ROOT / "logs" / "his_sittings.txt").write_text(txt + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

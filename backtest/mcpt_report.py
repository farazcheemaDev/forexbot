"""Summarise every MCPT run and plot the null distributions.

    python -m backtest.mcpt_report
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

LOGS = Path(__file__).resolve().parents[1] / "logs"


def verdict(p: float) -> str:
    if p <= 0.01:
        return "STRONG edge"
    if p <= 0.05:
        return "passes 5%"
    if p <= 0.10:
        return "borderline"
    return "DATA MINING"


def main():
    files = sorted(LOGS.glob("mcpt_*.json"))
    if not files:
        print("no MCPT results yet")
        return

    runs, calibs = [], []
    for f in files:
        try:
            r = json.load(open(f))
        except Exception:
            continue
        (calibs if r.get("test") == "calibration" else runs).append((f.stem, r))

    if calibs:
        print("=" * 78)
        print("TEST CALIBRATION — is the p-value machinery itself unbiased?")
        print("=" * 78)
        for name, r in calibs:
            ps = np.array(r["pvals"])
            print(f"  {r['n_trials']} trials on data with NO edge (permutations), "
                  f"{r['n_perm']} perms each")
            print(f"  mean p = {ps.mean():.3f}   (unbiased test -> ~0.50)")
            print(f"  p < 0.05 in {np.mean(ps < 0.05)*100:.0f}% of trials "
                  f"(unbiased test -> ~5%)")
            print(f"  p-values: {', '.join(f'{x:.2f}' for x in ps)}")
            ok = 0.30 < ps.mean() < 0.70
            print(f"  -> {'CALIBRATED: p-values are trustworthy' if ok else 'BIASED: do not trust these p-values'}\n")

    if runs:
        print("=" * 78)
        print("MCPT RESULTS")
        print("=" * 78)
        print(f"{'run':34} {'real PF':>8} {'perm med':>9} {'perm p95':>9} "
              f"{'p-val':>7}  verdict")
        print("-" * 78)
        for name, r in sorted(runs, key=lambda x: x[1].get("pval", 9)):
            if "pval" not in r:
                print(f"{name[:34]:34} {r.get('error','incomplete')}")
                continue
            tag = name.replace("mcpt_", "").replace("_mcpt", "")
            print(f"{tag[:34]:34} {r['real_pf']:>8.3f} {r['perm_pf_median']:>9.3f} "
                  f"{r['perm_pf_p95']:>9.3f} {r['pval']:>7.3f}  {verdict(r['pval'])}")

        print("\nKEY COMPARISON — our headline claim vs the noise floor:")
        for name, r in runs:
            if "pval" not in r or r["test"] != "insample_mcpt":
                continue
            med = r["perm_pf_median"]
            print(f"  {r['label']:22} best-of-{r['grid_size']} search on RANDOM data "
                  f"typically reaches PF {med:.3f}; real reached {r['real_pf']:.3f}")

    # histograms
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plot = [(n, r) for n, r in runs if r.get("perm_pfs")]
        if plot:
            k = len(plot)
            fig, axes = plt.subplots(1, k, figsize=(5 * k, 4), squeeze=False)
            for ax, (name, r) in zip(axes[0], plot):
                ax.hist(r["perm_pfs"], bins=30, color="#4472c4",
                        label=f"{r['n_perm']} permutations\n(no edge exists)")
                ax.axvline(r["real_pf"], color="red", lw=2,
                           label=f"real = {r['real_pf']:.3f}")
                ax.axvline(np.median(r["perm_pfs"]), color="orange", ls="--", lw=1.5,
                           label=f"perm median = {np.median(r['perm_pfs']):.3f}")
                ax.set_title(f"{r['label']} {r['test'].replace('_mcpt','')}\n"
                             f"p = {r['pval']:.3f} — {verdict(r['pval'])}", fontsize=10)
                ax.set_xlabel("best profit factor found by the search")
                ax.legend(fontsize=7)
            plt.tight_layout()
            out = LOGS / "mcpt_distributions.png"
            plt.savefig(out, dpi=110)
            print(f"\nplot -> {out}")
    except Exception as e:
        print(f"(plot skipped: {e})")


if __name__ == "__main__":
    main()

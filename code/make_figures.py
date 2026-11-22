"""Make the paper's figures from the experiment output (no numbers are typed in by hand).
Run from code/ :   python3 make_figures.py
Options:  --runs8 runs.jsonl  --runs16 runs_b16000.jsonl  --exclude excluded_tasks.txt
          --tables8 ../paper/results_excl/tables.tex  --tables16 ../paper/results_b16000_excl/tables.tex  --out ../paper/figures
Writes: fig_recovery.pdf  fig_forest.pdf  fig_perfunction.pdf  fig_tokens_quality.pdf
Needs: pip install matplotlib pandas numpy"""
import argparse, json, math, os, re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPAIR, REGEN = "#E69F00", "#0072B2"          # colour-blind-safe pair, used for the two policies everywhere
GOOD, BUDGET_C, CAP_C = "#009E73", "#D55E00", "#999999"
plt.rcParams.update({"font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8, "legend.fontsize": 7.5,
                     "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "axes.spines.top": False, "axes.spines.right": False,
                     "pdf.fonttype": 42})

def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)

def load_runs(path, exclude):
    df = pd.DataFrame(json.loads(l) for l in open(path))
    if exclude and os.path.exists(exclude):
        ex = {l.strip() for l in open(exclude) if l.strip()}
        df = df[~df.task.isin(ex)].copy()
    df["ms_all"] = df["ms"].fillna(0.0)
    return df

def counts_from_runs(dfs):
    out = {}
    for df in dfs:
        b = int(df.budget.iloc[0])
        f = df[~df.init_valid]
        for pol in ("repair", "regenerate"):
            g = f[f.policy == pol]
            out[(b, pol)] = dict(n=len(g), valid=int((g.stop == "pass").sum()), budget=int((g.stop == "budget").sum()),
                                 cap=int((g.stop == "max_calls").sum()))
    return out

# ---------------------------------------------------------------- Figure 1
def fig_recovery(counts, out):
    budgets = sorted({b for b, _ in counts})
    fig, (a, b2) = plt.subplots(1, 2, figsize=(6.5, 2.7))
    w = 0.34; xs = np.arange(len(budgets))
    for j, (pol, col, lab) in enumerate([("repair", REPAIR, "Repair"), ("regenerate", REGEN, "Regeneration")]):
        off = (-0.5 + j) * w * 1.05
        for i, bud in enumerate(budgets):
            c = counts[(bud, pol)]; p = c["valid"] / c["n"]; lo, hi = wilson(c["valid"], c["n"])
            a.bar(xs[i] + off, p, w, color=col, label=lab if i == 0 else None)
            a.errorbar(xs[i] + off, p, yerr=[[p - lo], [hi - p]], color="black", capsize=2, lw=0.8)
            a.text(xs[i] + off, 0.03, f"{c['valid']}/{c['n']}", ha="center", va="bottom", fontsize=6.5, color="white", fontweight="bold")
    a.set_xticks(xs); a.set_xticklabels([f"{b:,} tokens" for b in budgets])
    a.set_ylim(0, 1.05); a.set_ylabel("Share of failed starts\nthat ended with a valid suite")
    a.set_title("(a) Recovery after a failed start"); a.legend(frameon=False, loc="upper left")
    # (b) stacked outcomes
    for j, (pol, short) in enumerate([("repair", "Repair"), ("regenerate", "Regen.")]):
        off = (-0.5 + j) * w * 1.05
        for i, bud in enumerate(budgets):
            c = counts[(bud, pol)]; bottom = 0
            for key, col in (("valid", GOOD), ("budget", BUDGET_C), ("cap", CAP_C)):
                h = c[key] / c["n"]
                b2.bar(xs[i] + off, h, w, bottom=bottom, color=col)
                if h >= 0.08: b2.text(xs[i] + off, bottom + h / 2, str(c[key]), ha="center", va="center", fontsize=6.5, color="white", fontweight="bold")
                bottom += h
            b2.text(xs[i] + off, -0.06, short, ha="center", va="top", fontsize=6.5)
    b2.set_xticks(xs); b2.set_xticklabels([f"{b:,} tokens" for b in budgets]); b2.tick_params(axis="x", pad=14)
    b2.set_ylim(0, 1.0); b2.set_ylabel("Share of failed starts")
    b2.set_title("(b) How failed-start trajectories ended")
    from matplotlib.patches import Patch
    b2.legend(handles=[Patch(color=GOOD, label="valid suite"), Patch(color=BUDGET_C, label="stopped: token budget"),
                       Patch(color=CAP_C, label="stopped: 10-call cap")], frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.30), ncol=3, fontsize=6.8, handlelength=1.2, columnspacing=1.0)
    fig.tight_layout(); fig.savefig(out, bbox_inches="tight"); plt.close(fig)

# ---------------------------------------------------------------- Figure 2
def parse_tables(path, budget):
    """Reads the analysis tables written by analyze.py (tab:main-original / tab:main-renamed)."""
    res = {}
    for chunk in open(path).read().split("\\begin{table}")[1:]:
        m = re.search(r"\\label\{tab:main-(original|renamed)\}", chunk)
        if not m: continue
        cond = m.group(1)
        for line in chunk.splitlines():
            if "&" not in line or line.strip().startswith("Measure"): continue
            parts = [p.strip().rstrip("\\").strip() for p in line.split("&")]
            if len(parts) < 6: continue
            ci = re.findall(r"[-+]?\d+\.\d+", parts[4])
            try: res[(budget, cond, parts[0])] = (float(parts[1]), float(parts[2]), float(parts[3]), float(ci[0]), float(ci[1]))
            except (ValueError, IndexError): pass
    return res

def fig_forest(tab, budgets, out):
    measures = [("Mutation score (all attempts)", "Mutation score\n(all attempts)"), ("Validity rate", "Validity rate"),
                ("Branch coverage (all attempts)", "Branch coverage\n(all attempts)")]
    rows = [(b, c) for b in budgets for c in ("original", "renamed")]
    fig, axes = plt.subplots(1, 3, figsize=(6.5, 2.5), sharey=True)
    colors = {budgets[0]: "#333333", budgets[-1]: "#56B4E9"}
    for ax, (key, title) in zip(axes, measures):
        for yi, (b, c) in enumerate(rows):
            v = tab.get((b, c, key))
            if not v: continue
            _, _, d, lo, hi = v
            ax.errorbar(d, yi, xerr=[[d - lo], [hi - d]], fmt="o" if c == "original" else "s", color=colors[b], capsize=2, ms=4.5, lw=1)
        ax.axvline(0, color="black", lw=0.8, ls="--"); ax.set_title(title)
        ax.set_yticks(range(len(rows))); ax.set_ylim(len(rows) - 0.5, -0.5)
        lo, hi = ax.get_xlim(); m = max(abs(lo), abs(hi)); ax.set_xlim(-m, m)
        ax.set_xlabel("repair \u2212 regeneration\n\u2190 regen. better    repair better \u2192", fontsize=6.8)
    axes[0].set_yticklabels([f"{b:,} tokens, {c}" for b, c in rows])
    fig.tight_layout(); fig.savefig(out, bbox_inches="tight"); plt.close(fig)

# ---------------------------------------------------------------- Figure 3
def fig_perfunction(dfs, out):
    fig, axes = plt.subplots(1, len(dfs), figsize=(6.5, 2.5), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, df in zip(axes, dfs):
        g = df.groupby(["task", "policy"])["ms_all"].mean().unstack().dropna()
        d = (g["repair"] - g["regenerate"]).sort_values()
        x = np.arange(len(d)); col = np.where(d.values > 0, REPAIR, np.where(d.values < 0, REGEN, "#BBBBBB"))
        ax.vlines(x, 0, d.values, colors=col, lw=1.4); ax.scatter(x, d.values, c=col, s=10, zorder=3)
        ax.axhline(0, color="black", lw=0.8); ax.axhline(d.mean(), color="#555555", ls="--", lw=0.8)
        ax.set_xlabel("functions, sorted by difference"); ax.set_xticks([])
        ax.set_title(f"{int(df.budget.iloc[0]):,} tokens: {int((d != 0).sum())} of {len(d)} functions differ\n(mean {d.mean():+.3f}, dashed)")
    axes[0].set_ylabel("Mutation score, repair \u2212 regeneration\n(all attempts, per function)")
    fig.tight_layout(); fig.savefig(out, bbox_inches="tight"); plt.close(fig)

# ---------------------------------------------------------------- Figure 4
def fig_tokens_quality(dfs, out):
    fig, (a, b2) = plt.subplots(1, 2, figsize=(6.5, 2.7))
    pos, labels = [], []; rng = np.random.default_rng(1)
    for i, df in enumerate(dfs):
        bud = int(df.budget.iloc[0])
        for j, (pol, col) in enumerate([("repair", REPAIR), ("regenerate", REGEN)]):
            x = i * 3 + j; f = df[(~df.init_valid) & (df.policy == pol)]
            v = (f.tokens / bud).values
            a.boxplot(v, positions=[x], widths=0.55, showfliers=False, patch_artist=True, boxprops=dict(facecolor="white", color=col),
                      medianprops=dict(color=col), whiskerprops=dict(color=col), capprops=dict(color=col))
            a.scatter(x + rng.uniform(-0.18, 0.18, len(v)), v, s=6, color=col, alpha=0.6, zorder=3)
            pos.append(x); labels.append("Repair" if pol == "repair" else "Regen.")
        a.text(i * 3 + 0.5, -0.19, f"{bud:,} tokens", ha="center", va="top", fontsize=7.5, transform=a.get_xaxis_transform())
    a.axhline(1.0, color="black", ls="--", lw=0.8); a.text(a.get_xlim()[1], 1.0, " allowance", fontsize=6.5, va="center")
    a.set_xticks(pos); a.set_xticklabels(labels); a.set_ylabel("Tokens used / allowance\n(failed starts only)"); a.set_title("(a) Token use after a failed start")
    for i, df in enumerate(dfs):
        for j, (pol, col) in enumerate([("repair", REPAIR), ("regenerate", REGEN)]):
            x = i * 3 + j; v = df[(df.policy == pol) & df.ms.notna()].ms.values
            b2.boxplot(v, positions=[x], widths=0.55, showfliers=False, patch_artist=True, boxprops=dict(facecolor="white", color=col),
                       medianprops=dict(color=col), whiskerprops=dict(color=col), capprops=dict(color=col))
            b2.scatter(x + rng.uniform(-0.18, 0.18, len(v)), v, s=5, color=col, alpha=0.45, zorder=3)
        b2.text(i * 3 + 0.5, -0.19, f"{int(df.budget.iloc[0]):,} tokens", ha="center", va="top", fontsize=7.5, transform=b2.get_xaxis_transform())
    b2.set_xticks(pos); b2.set_xticklabels(labels); b2.set_ylabel("Mutation score of valid suites"); b2.set_title("(b) Quality of valid suites")
    b2.set_ylim(0, 1.05)
    fig.tight_layout(); fig.subplots_adjust(bottom=0.2); fig.savefig(out, bbox_inches="tight"); plt.close(fig)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--runs8", default="runs.jsonl"); p.add_argument("--runs16", default="runs_b16000.jsonl")
    p.add_argument("--exclude", default="excluded_tasks.txt")
    p.add_argument("--tables8", default="../paper/results_excl/tables.tex"); p.add_argument("--tables16", default="../paper/results_b16000_excl/tables.tex")
    p.add_argument("--out", default="../paper/figures")
    a = p.parse_args(); os.makedirs(a.out, exist_ok=True)
    d8, d16 = load_runs(a.runs8, a.exclude), load_runs(a.runs16, a.exclude)
    dfs = sorted([d8, d16], key=lambda d: int(d.budget.iloc[0]))
    print("functions per run:", [d.task.nunique() for d in dfs])
    fig_recovery(counts_from_runs(dfs), os.path.join(a.out, "fig_recovery.pdf"))
    tab = {}; tab.update(parse_tables(a.tables8, int(d8.budget.iloc[0]))); tab.update(parse_tables(a.tables16, int(d16.budget.iloc[0])))
    fig_forest(tab, [int(d.budget.iloc[0]) for d in dfs], os.path.join(a.out, "fig_forest.pdf"))
    fig_perfunction(dfs, os.path.join(a.out, "fig_perfunction.pdf"))
    fig_tokens_quality(dfs, os.path.join(a.out, "fig_tokens_quality.pdf"))
    print("wrote 4 figures to", a.out)

if __name__ == "__main__":
    main()
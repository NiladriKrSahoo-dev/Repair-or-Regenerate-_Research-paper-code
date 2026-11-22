"""Usage: python analyze.py runs.jsonl [--latex DIR]. Writes DIR/tables.tex and DIR/numbers.tex for the paper."""
import json, sys, os, numpy as np, pandas as pd
from scipy.stats import wilcoxon

path = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "runs.jsonl"
outdir = sys.argv[sys.argv.index("--latex") + 1] if "--latex" in sys.argv else None
df = pd.DataFrame(json.loads(l) for l in open(path))
if "--exclude" in sys.argv:   # drop tasks listed (one id per line) in the given file
    _ex = {l.strip() for l in open(sys.argv[sys.argv.index("--exclude") + 1]) if l.strip()}
    df = df[~df.task.isin(_ex)].copy()
df["ms_all"] = df["ms"].fillna(0.0)           # unusable suite counts as 0 in all-attempt analysis
df["cov_all"] = df["branch_cov"].fillna(0.0)
df["valid"] = df["valid"].astype(float); df["executable"] = df["executable"].astype(float)
rng = np.random.default_rng(0)

def stats(diff):
    diff = np.asarray(diff, float)
    if len(diff) < 2: return None
    b = [rng.choice(diff, len(diff)).mean() for _ in range(10000)]
    lo, hi = np.percentile(b, [2.5, 97.5])
    try: p = wilcoxon(diff).pvalue if np.any(diff != 0) else 1.0
    except ValueError: p = float("nan")
    sd = diff.std(ddof=1)
    need = int(np.ceil(((1.96 + 0.84) * sd / abs(diff.mean())) ** 2)) if diff.mean() != 0 and sd > 0 else None
    return dict(n=len(diff), mean=diff.mean(), lo=lo, hi=hi, p=p, sd=sd, need=need)

def pol_means(d, col):
    return d.groupby(["task", "policy"])[col].mean().unstack().dropna()

def row(d, col, label):
    g = pol_means(d, col)
    s = stats((g["repair"] - g["regenerate"]).values) if len(g) else None
    return (label, g["repair"].mean() if len(g) else np.nan, g["regenerate"].mean() if len(g) else np.nan, s)

METRICS = [("ms_all", "Mutation score (all attempts)"), ("cov_all", "Branch coverage (all attempts)"),
           ("valid", "Validity rate"), ("executable", "Executability rate"), ("tokens", "Tokens used"), ("calls", "Model calls")]
tex_esc = lambda s: s.replace("_", r"\_").replace("%", r"\%")
def fmt_p(p): return "n/a" if p != p else ("<0.001" if p < 0.001 else f"{p:.3f}")

def table(rows, caption, label):
    L = [r"\begin{table}[t]", r"\centering\small", rf"\caption{{{caption}}}", rf"\label{{{label}}}",
         r"\begin{tabular}{lrrrrr}", r"\toprule", r"Measure & Repair & Regen. & $\Delta$ (R$-$G) & 95\% CI & $p$ \\", r"\midrule"]
    for lab, a, b, s in rows:
        if s is None: L.append(rf"{tex_esc(lab)} & {a:.3f} & {b:.3f} & \multicolumn{{3}}{{c}}{{too few functions}} \\"); continue
        L.append(rf"{tex_esc(lab)} & {a:.3f} & {b:.3f} & {s['mean']:+.3f} & [{s['lo']:+.3f}, {s['hi']:+.3f}] & {fmt_p(s['p'])} \\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(L)

tables, nums = [], []
def macro(name, val): nums.append(rf"\newcommand{{\{name}}}{{{val}}}")
macro("nTasks", df.task.nunique()); macro("nRunsPerPolicy", len(df[df.policy == "repair"]))
macro("budgetTokens", int(df.budget.iloc[0])); macro("modelId", tex_esc(str(df.model.iloc[0])))
base = df[df.policy == "repair"]
macro("initPassRate", f"{100 * base.init_valid.mean():.1f}")

for cond in sorted(df.cond.unique()):
    d = df[df.cond == cond]; c = {"original": "Orig", "renamed": "Ren"}.get(cond, cond.capitalize())
    rows = [row(d, col, lab) for col, lab in METRICS]
    tables.append(table(rows, f"Repair vs.\\ fresh regeneration on {cond} code, all runs (paired by function; CI by bootstrap over functions; Wilcoxon signed-rank).", f"tab:main-{cond}"))
    f = d[~d.init_valid]
    n_f = f.groupby(["task", "rep"]).ngroups
    macro(f"nInitFail{c}", n_f)
    rows = [row(f, col, lab) for col, lab in METRICS[:3]]
    tables.append(table(rows, f"As above, restricted to runs whose shared initial candidate failed validation ({cond} code; {n_f} runs).", f"tab:fail-{cond}"))
    r0 = rows[0][3] if rows else None
    m = row(d, "ms_all", "")
    if m[3]:
        macro(f"msRepair{c}", f"{m[1]:.3f}"); macro(f"msRegen{c}", f"{m[2]:.3f}")
        macro(f"msDiff{c}", f"{m[3]['mean']:+.3f}"); macro(f"msCI{c}", f"[{m[3]['lo']:+.3f}, {m[3]['hi']:+.3f}]"); macro(f"msP{c}", fmt_p(m[3]['p']))
        macro(f"nNeeded{c}", m[3]['need'] if m[3]['need'] else "undetermined")

if {"original", "renamed"} <= set(df.cond):
    L = [r"\begin{table}[t]", r"\centering\small", r"\caption{Effect of local-variable renaming on all-attempt mutation score (original $-$ renamed; paired by function).}", r"\label{tab:rename}",
         r"\begin{tabular}{lrrrr}", r"\toprule", r"Policy & Original & Renamed & $\Delta$ & 95\% CI \\", r"\midrule"]
    for pol in ("repair", "regenerate"):
        g = df[df.policy == pol].groupby(["task", "cond"])["ms_all"].mean().unstack().dropna()
        s = stats((g["original"] - g["renamed"]).values) if len(g) else None
        if s: L.append(rf"{pol} & {g['original'].mean():.3f} & {g['renamed'].mean():.3f} & {s['mean']:+.3f} & [{s['lo']:+.3f}, {s['hi']:+.3f}] \\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    tables.append("\n".join(L))

st = df.groupby(["cond", "policy", "stop"]).size().reset_index(name="n")
L = [r"\begin{table}[t]", r"\centering\small", r"\caption{Stopping reasons per trajectory.}", r"\label{tab:stops}", r"\begin{tabular}{lllr}", r"\toprule", r"Code & Policy & Stop reason & Runs \\", r"\midrule"]
for _, r in st.iterrows(): L.append(rf"{r.cond} & {r.policy} & {tex_esc(r.stop)} & {r.n} \\")
L += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
tables.append("\n".join(L))

print("\n".join(tables).replace(r"\\", "") if not outdir else f"wrote {outdir}")
print("\n".join(nums))
if outdir:
    os.makedirs(outdir, exist_ok=True)
    open(os.path.join(outdir, "tables.tex"), "w").write("\n".join(tables))
    open(os.path.join(outdir, "numbers.tex"), "w").write("\n".join(nums) + "\n")

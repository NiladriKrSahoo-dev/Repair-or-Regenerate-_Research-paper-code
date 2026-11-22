"""Offline re-score of pilot final tests with the CURRENT mutant operators (no API calls).
Usage: python3 reeval_pilot.py pilot.jsonl tasks/tasks_pilot.jsonl"""
import json, sys, statistics as st
from execute import run_tests
from mutants import generate
from rename import rename_locals

runs = [json.loads(l) for l in open(sys.argv[1])]
tasks = {}
for l in open(sys.argv[2]):
    t = json.loads(l); tasks[t["id"]] = t
cache = {}

def score(src, test):
    if src not in cache: cache[src] = generate(src)
    killed = elig = 0
    for m in cache[src]:
        try: compile(m["code"], "m", "exec")
        except Exception: continue
        r = run_tests(m["code"], test, timeout=5)
        if r["timeout"]: continue
        if r["passed"]: elig += 1
        elif r["executable"]: elig += 1; killed += 1
    return (killed / elig if elig else None), len(cache[src])

rows = []
for r in runs:
    if not r.get("valid") or "final_test" not in r: continue
    t = tasks[r["task"]]
    src = t["source"] if r["cond"] == "original" else rename_locals(t["source"], t["fn"])[0]
    new, n = score(src, r["final_test"])
    rows.append((r["policy"], r["cond"], r["ms"], new, n))
print(f"re-scored {len(rows)} valid suites; mean mutants per function: {st.mean(x[4] for x in rows):.1f}")
for pol in ("repair", "regenerate"):
    for cond in ("original", "renamed"):
        sel = [x for x in rows if x[0] == pol and x[1] == cond and x[3] is not None]
        if not sel: continue
        old = [x[2] for x in sel if x[2] is not None]; new = [x[3] for x in sel]
        print(f"{pol:10s} {cond:9s} n={len(sel):2d} old_mean={st.mean(old):.3f} new_mean={st.mean(new):.3f} "
              f"new_min={min(new):.3f} new_median={st.median(new):.3f} share_below_0.9={sum(v < 0.9 for v in new) / len(new):.2f}")

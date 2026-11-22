"""Offline diagnostics (no API calls). Usage: python3 diagnose.py runs.jsonl tasks/tasks.jsonl
1) why were final suites non-executable?  2) how much budget was left unused when trajectories stopped on 'budget'?"""
import json, re, sys, collections, statistics as st
from execute import run_tests
from rename import rename_locals

rows = [json.loads(l) for l in open(sys.argv[1])]
tasks = {}
for l in open(sys.argv[2]):
    t = json.loads(l); tasks[t["id"]] = t

print("== Non-executable final suites ==")
kinds = collections.Counter(); examples = {}
for r in rows:
    if r["executable"]: continue
    t = tasks[r["task"]]
    src = t["source"] if r["cond"] == "original" else rename_locals(t["source"], t["fn"])[0]
    out = run_tests(src, r["final_test"])["output"]
    if "unsupported operand type(s) for |" in out: k = "py3.10+ type-union syntax (| in annotation)"
    elif "IndentationError" in out: k = "IndentationError"
    elif "SyntaxError" in out: k = "SyntaxError"
    elif re.search(r"ModuleNotFoundError|ImportError", out): k = "ImportError"
    elif "NameError" in out: k = "NameError"
    elif "TypeError" in out: k = "TypeError at import/collection"
    elif r.get("timeout") or "TIMEOUT" in out: k = "timeout"
    else: k = "other"
    kinds[k] += 1; examples.setdefault(k, "\n".join(out.strip().splitlines()[-3:]))
print(f"total non-executable: {sum(kinds.values())} of {len(rows)}")
for k, n in kinds.most_common(): print(f"  {n:3d}  {k}\n       e.g. {examples[k][:200]!r}")

print("\n== Budget slack at stop == 'budget' ==")
for pol in ("repair", "regenerate"):
    s = [r["budget"] - r["tokens"] for r in rows if r["policy"] == pol and r["stop"] == "budget"]
    if s: print(f"{pol:10s} n={len(s):3d} mean unused tokens={st.mean(s):.0f} min={min(s)} max={max(s)}")
print("\n== Stop reasons by init_valid ==")
c = collections.Counter((r["policy"], r["init_valid"], r["stop"]) for r in rows)
for k, n in sorted(c.items(), key=str): print(" ", k, n)

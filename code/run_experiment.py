import argparse, json, os, time
from policies import trajectory, extract
from prompts import GEN
from execute import run_tests
from mutants import frozen
from rename import rename_locals

def evaluate(task_id, cond, src, test):
    v = run_tests(src, test, cov=True)
    out = dict(executable=v["executable"], valid=v["passed"], branch_cov=v["branch_cov"], ms=None, killed=0, eligible=0, invalid=0, timeouts=0)
    if not v["passed"]: return out
    for m in frozen(f"{task_id}_{cond}", src):
        try: compile(m["code"], "m", "exec")
        except Exception: out["invalid"] += 1; continue
        r = run_tests(m["code"], test, timeout=5)
        if r["timeout"]: out["timeouts"] += 1
        elif r["passed"]: out["eligible"] += 1
        elif r["executable"]: out["eligible"] += 1; out["killed"] += 1
        else: out["invalid"] += 1
    out["ms"] = out["killed"] / out["eligible"] if out["eligible"] else None
    return out

def main():
    a = argparse.ArgumentParser()
    a.add_argument("--tasks", required=True); a.add_argument("--out", default="runs.jsonl")
    a.add_argument("--provider", choices=["anthropic", "gemini", "openai"], default="anthropic"); a.add_argument("--thinking-budget", type=int, default=None); a.add_argument("--max-output", type=int, default=1500); a.add_argument("--extra-body"); a.add_argument("--system"); a.add_argument("--base-url"); a.add_argument("--api-key-env", default="NVIDIA_API_KEY"); a.add_argument("--model"); a.add_argument("--budget", type=int, default=8000)
    a.add_argument("--reps", type=int, default=3); a.add_argument("--mock", action="store_true")
    a.add_argument("--conds", default="original,renamed"); a.add_argument("--temperature", type=float, default=1.0)
    a = a.parse_args()
    if a.mock:
        from llm import MockBackend; mk = lambda s: MockBackend(seed=s)
    elif a.provider == "openai":
        from llm import OpenAICompatBackend; mk = lambda s: OpenAICompatBackend(a.model, a.base_url or "https://integrate.api.nvidia.com/v1", a.api_key_env, a.temperature, a.max_output, json.loads(a.extra_body) if a.extra_body else None, a.system)
    elif a.provider == "gemini":
        from llm import GeminiBackend; mk = lambda s: GeminiBackend(a.model, a.temperature, thinking_budget=a.thinking_budget)
    else:
        from llm import AnthropicBackend; mk = lambda s: AnthropicBackend(a.model, a.temperature)
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out): r = json.loads(l); done.add((r["task"], r["cond"], r["rep"], r["policy"]))
    for line in open(a.tasks):
        t = json.loads(line)
        for cond in a.conds.split(","):
            src = t["source"] if cond == "original" else rename_locals(t["source"], t["fn"])[0]
            for rep in range(a.reps):
                if all((t["id"], cond, rep, p) in done for p in ("repair", "regenerate")): continue
                be = mk(hash((t["id"], cond, rep)) % 10**6)
                text, ti, to = be.call(GEN.format(fn=t["fn"], src=src))
                init = dict(test=extract(text), tokens=ti + to)   # shared, charged to both
                recs = []   # written together AFTER both policies finish
                for pol in ("repair", "regenerate"):
                    tr = trajectory(pol, t["fn"], src, init, be, a.budget)
                    ev = evaluate(t["id"], cond, src, tr["test"])
                    rec = dict(task=t["id"], cond=cond, rep=rep, policy=pol, budget=a.budget, tokens=tr["tokens"], calls=tr["calls"],
                               stop=tr["stop"], init_valid=tr["trail"][0]["passed"], model=a.model or "mock", provider="mock" if a.mock else a.provider, ts=time.time(),
                               initial_test=init["test"], final_test=tr["test"], trail=tr["trail"], **ev)
                    recs.append(rec)
                with open(a.out, "a") as fh:
                    for rec in recs: fh.write(json.dumps(rec) + "\n")
                print(t["id"], cond, rep, flush=True)
main()

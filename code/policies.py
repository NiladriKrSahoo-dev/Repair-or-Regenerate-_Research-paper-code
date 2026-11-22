import re
from prompts import GEN, REPAIR
from execute import run_tests

def extract(text):
    m = re.findall(r"```(?:python)?\n(.*?)```", text, re.S)
    return (m[0] if m else text).strip() + "\n"

def trajectory(policy, fn, src, init, backend, budget, max_calls=10):
    """init = dict(test, tokens). Same rule for both policies: a call is made only if
    used + estimated_input + max_output <= budget. Stopping uses ONLY visible pass/fail,
    never coverage or mutation (hidden outcomes)."""
    used, calls, cand = init["tokens"], 1, init["test"]
    res = run_tests(src, cand)
    trail = [dict(call=1, passed=res["passed"], tokens=used)]
    stop = "initial_pass" if res["passed"] else None
    while not res["passed"]:
        prompt = REPAIR.format(fn=fn, src=src, prev=cand, diag=res["output"]) if policy == "repair" else GEN.format(fn=fn, src=src)
        if used + len(prompt) // 3 + backend.max_output > budget: stop = "budget"; break
        if calls >= max_calls: stop = "max_calls"; break
        text, ti, to = backend.call(prompt)
        used += ti + to; calls += 1
        cand = extract(text)
        res = run_tests(src, cand)
        trail.append(dict(call=calls, passed=res["passed"], tokens=used))
        if res["passed"]: stop = "pass"
    return dict(test=cand, tokens=used, calls=calls, stop=stop or "end", trail=trail, visible=res)

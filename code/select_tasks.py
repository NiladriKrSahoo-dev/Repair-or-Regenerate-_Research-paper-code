"""Deterministic, outcome-blind task selection. Run BEFORE any model call.
Input: JSONL with the fields given by --id-key/--fn-key/--src-key (map your ULT export). Output: tasks.jsonl + selection_log.json.
Eligibility (frozen): parses; exactly one top-level function (plus optional imports) named fn; stdlib-only imports;
no I/O, network, randomness, time, os/sys/subprocess, global state; >=1 local variable; renamer passes alpha-equivalence;
>=1 branch construct; >=6 mutants. Then a seeded random sample of N. Nothing here looks at model output."""
import argparse, ast, builtins, json, random, sys
from mutants import generate
from rename import rename_locals

def _stdlib():
    n = getattr(sys, "stdlib_module_names", None)   # Python 3.10+
    if n: return set(n)
    import sysconfig, pkgutil, os                  # Python 3.9: build the list from the stdlib directory
    d = sysconfig.get_paths()["stdlib"]
    names = {m.name for m in pkgutil.iter_modules([d])} | set(sys.builtin_module_names) | {"__future__"}
    names |= {m.name for m in pkgutil.iter_modules([os.path.join(d, "lib-dynload")])}
    return names
STDLIB = _stdlib()
MIN_MUT = 6
BANNED = {"os", "sys", "subprocess", "socket", "requests", "urllib", "random", "time", "datetime", "shutil", "pathlib", "threading", "multiprocessing", "numpy", "pandas"}
BANNED_CALLS = {"open", "input", "eval", "exec", "print", "__import__"}

def free_names(t, fn):
    """Names read inside the function that are not args, locals, builtins, or imported at module level."""
    f = next(n for n in t.body if isinstance(n, ast.FunctionDef) and n.name == fn)
    a = f.args
    known = {x.arg for x in a.args + a.kwonlyargs + a.posonlyargs} | set(dir(builtins)) | {fn}
    if a.vararg: known.add(a.vararg.arg)
    if a.kwarg: known.add(a.kwarg.arg)
    for n in ast.walk(t):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for x in n.names: known.add((x.asname or x.name).split(".")[0])
    for n in ast.walk(f):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store): known.add(n.id)
        if isinstance(n, ast.arg): known.add(n.arg)
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n is not f: known.add(n.name)
        if isinstance(n, ast.ExceptHandler) and n.name: known.add(n.name)
    return {n.id for n in ast.walk(f) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in known}

def eligible(src, fn):
    try: t = ast.parse(src)
    except SyntaxError: return "syntax"
    fns = [n for n in t.body if isinstance(n, ast.FunctionDef)]
    if len(fns) != 1 or fns[0].name != fn: return "not_single_function"
    for n in ast.walk(t):
        mods = [a.name.split(".")[0] for a in n.names] if isinstance(n, ast.Import) else ([n.module.split(".")[0]] if isinstance(n, ast.ImportFrom) and n.module else [])
        if any(m in BANNED or m not in STDLIB for m in mods): return "non_stdlib_or_banned_import"
        if isinstance(n, (ast.Global, ast.Nonlocal, ast.AsyncFunctionDef, ast.Await)): return "global_or_async"
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in BANNED_CALLS: return "banned_call"
    if free_names(t, fn): return "not_self_contained"
    try: _, m = rename_locals(src, fn)
    except Exception: return "rename_failed"
    if not m: return "no_locals"
    if not any(isinstance(n, (ast.If, ast.For, ast.While, ast.IfExp)) for n in ast.walk(t)): return "no_branches"
    if len(generate(src)) < MIN_MUT: return "too_few_mutants"
    return None

if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--inp", required=True); a.add_argument("--out", default="tasks/tasks.jsonl")
    a.add_argument("--n", type=int, default=20); a.add_argument("--seed", type=int, default=2026)
    a.add_argument("--id-key", default="id"); a.add_argument("--fn-key", default="fn"); a.add_argument("--src-key", default="source")
    a = a.parse_args()
    ok, why = [], {}
    for l in open(a.inp):
        r = json.loads(l); s, f = r[a.src_key], r[a.fn_key]
        reason = eligible(s, f)
        if reason: why[reason] = why.get(reason, 0) + 1
        else: ok.append(dict(id=str(r[a.id_key]), fn=f, source=s))
    random.Random(a.seed).shuffle(ok)
    pick = ok[:a.n]
    with open(a.out, "w") as o:
        for t in pick: o.write(json.dumps(t) + "\n")
    json.dump(dict(seed=a.seed, n_input=sum(why.values()) + len(ok), n_eligible=len(ok), exclusions=why, selected=[t["id"] for t in pick]), open("selection_log.json", "w"), indent=1)
    print(f"eligible={len(ok)} selected={len(pick)} exclusions={why}")

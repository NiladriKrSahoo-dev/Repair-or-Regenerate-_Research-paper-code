"""Deterministic local-variable renaming with a formal check.
Arguments, globals, nonlocals, attributes and called names are untouched. After renaming we verify
alpha-equivalence: canonically renaming locals in first-store order in BOTH versions must yield identical ASTs.
This shows the transformation is a pure bijective renaming of locals (no name capture), not just that it compiles."""
import ast

def _fn(tree, fn):
    return next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == fn)

def _locals(target):
    a = target.args
    blocked = {x.arg for x in a.args + a.kwonlyargs + a.posonlyargs}
    if a.vararg: blocked.add(a.vararg.arg)
    if a.kwarg: blocked.add(a.kwarg.arg)
    for n in ast.walk(target):
        if isinstance(n, (ast.Global, ast.Nonlocal)): blocked |= set(n.names)
    out = []
    for n in ast.walk(target):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id not in blocked and n.id not in out:
            out.append(n.id)
    return out

def _apply(tree, fn, mapping):
    for n in ast.walk(_fn(tree, fn)):
        if isinstance(n, ast.Name) and n.id in mapping: n.id = mapping[n.id]

def _canon(src, fn):
    t = ast.parse(src); names = _locals(_fn(t, fn))
    _apply(t, fn, {o: f"__c{i}" for i, o in enumerate(names)})
    return ast.dump(t)

def rename_locals(src, fn):
    tree = ast.parse(src)
    names = _locals(_fn(tree, fn))
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.arg for n in ast.walk(tree) if isinstance(n, ast.arg)}
    mapping = {old: f"v{i+1}_" for i, old in enumerate(names)}
    if set(mapping.values()) & used: raise ValueError("name collision; task ineligible")
    _apply(tree, fn, mapping)
    out = ast.unparse(tree)
    compile(out, "<renamed>", "exec")
    if _canon(src, fn) != _canon(out, fn): raise ValueError("alpha-equivalence check failed; task ineligible")
    return out, mapping

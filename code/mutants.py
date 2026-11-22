"""Frozen mutant pool (operator set v2). Own AST operators (documented in the paper); swap in Cosmic Ray/mutmut if preferred."""
import ast, copy, hashlib, json, os, re

VERSION = "v2"
CMP = {ast.Lt: ast.GtE, ast.LtE: ast.Gt, ast.Gt: ast.LtE, ast.GtE: ast.Lt, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
       ast.In: ast.NotIn, ast.NotIn: ast.In, ast.Is: ast.IsNot, ast.IsNot: ast.Is}
BND = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt}      # boundary (off-by-one) comparison changes
ARI = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.FloorDiv, ast.FloorDiv: ast.Mult, ast.Div: ast.Mult, ast.Mod: ast.Mult}
BOOL = {ast.And: ast.Or, ast.Or: ast.And}

def _num(n):
    return isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)

def _sites(tree):
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Compare):
            if type(n.ops[0]) in CMP: out.append(("cmp", n))
            if type(n.ops[0]) in BND: out.append(("bnd", n))
        elif isinstance(n, ast.BinOp) and type(n.op) in ARI: out.append(("ari", n))
        elif isinstance(n, ast.AugAssign) and type(n.op) in ARI: out.append(("aug", n))
        elif isinstance(n, ast.BoolOp) and type(n.op) in BOOL: out.append(("bool", n))
        elif _num(n): out.append(("const", n)); out.append(("dec", n))
        elif isinstance(n, ast.If): out.append(("neg", n))
        elif isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not): out.append(("not", n))
        elif isinstance(n, ast.Return) and n.value is not None: out.append(("ret", n))
    return out

def _replace(tree, target, new):
    for parent in ast.walk(tree):
        for field, value in ast.iter_fields(parent):
            if value is target: setattr(parent, field, new); return
            if isinstance(value, list):
                for i, v in enumerate(value):
                    if v is target: value[i] = new; return

def generate(src):
    base = ast.parse(src); base_code = ast.unparse(base).strip()
    muts, seen = [], set()
    for i, (kind, _) in enumerate(_sites(base)):
        t = copy.deepcopy(base); _, node = _sites(t)[i]
        if kind == "cmp": node.ops[0] = CMP[type(node.ops[0])]()
        elif kind == "bnd": node.ops[0] = BND[type(node.ops[0])]()
        elif kind in ("ari", "aug"): node.op = ARI[type(node.op)]()
        elif kind == "bool": node.op = BOOL[type(node.op)]()
        elif kind == "const": node.value = node.value + 1
        elif kind == "dec": node.value = node.value - 1
        elif kind == "neg": node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
        elif kind == "not": _replace(t, node, node.operand)
        elif kind == "ret": node.value = ast.Constant(value=None)
        ast.fix_missing_locations(t)
        code = ast.unparse(t)
        if code.strip() != base_code and code not in seen:
            seen.add(code); muts.append(dict(id=f"{kind}{i}", kind=kind, code=code))
    return muts

def frozen(task_id, src, cache_dir="mutant_cache"):
    os.makedirs(cache_dir, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(task_id))[:80]           # task ids contain / and :: -> flat, portable file name
    tid = hashlib.sha256(str(task_id).encode()).hexdigest()[:8]          # keeps names unique after sanitising
    key = hashlib.sha256((VERSION + src).encode()).hexdigest()[:12]
    p = os.path.join(cache_dir, f"{safe}_{tid}_{key}.json")
    if os.path.exists(p): return json.load(open(p))
    m = generate(src); json.dump(m, open(p, "w")); return m

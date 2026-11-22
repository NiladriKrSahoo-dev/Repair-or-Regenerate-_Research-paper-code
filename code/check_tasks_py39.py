"""List tasks whose SOURCE cannot be imported under the Python that runs this script (e.g. `x: int | None`
annotations on Python 3.9). Usage: python3 check_tasks_py39.py tasks/tasks.jsonl > excluded_tasks.txt
Task ids go to stdout (one per line); reasons go to stderr."""
import ast, json, sys
flagged = []
for line in open(sys.argv[1]):
    t = json.loads(line); why = None
    tree = ast.parse(t["source"])
    future = any(isinstance(n, ast.ImportFrom) and n.module == "__future__" and any(a.name == "annotations" for a in n.names) for n in ast.walk(tree))
    anns = []
    for n in ast.walk(tree):
        if isinstance(n, ast.arg) and n.annotation is not None: anns.append(n.annotation)
        elif isinstance(n, ast.FunctionDef) and n.returns is not None: anns.append(n.returns)
        elif isinstance(n, ast.AnnAssign): anns.append(n.annotation)
    if not future and any(isinstance(m, ast.BinOp) and isinstance(m.op, ast.BitOr) for a in anns for m in ast.walk(a)):
        why = "X | Y in an annotation (needs Python 3.10+)"
    if why is None:
        try: exec(compile(t["source"], "<task>", "exec"), {"__name__": "target"})
        except Exception as e: why = f"import fails: {type(e).__name__}: {e}"
    if why: flagged.append(t["id"]); print(t["id"]); print(f"FLAGGED {t['id']}: {why}", file=sys.stderr)
print(f"{len(flagged)} of {sum(1 for _ in open(sys.argv[1]))} tasks flagged", file=sys.stderr)


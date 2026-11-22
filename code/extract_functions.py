"""Build a candidate pool from Python source files (e.g. a ULT export is NOT needed for this path).
Writes JSONL {id, fn, source}: each top-level function with the module's imports prepended.
Then run select_tasks.py on the output, which keeps only self-contained, stdlib-only, branchy, deterministic functions.
Usage: python extract_functions.py --root /path/to/python/files --out pool.jsonl [--max-lines 40]"""
import argparse, ast, json, os

def main():
    a = argparse.ArgumentParser(); a.add_argument("--root", required=True); a.add_argument("--out", default="pool.jsonl")
    a.add_argument("--max-lines", type=int, default=40); a.add_argument("--min-lines", type=int, default=5)
    a = a.parse_args(); n = 0
    with open(a.out, "w") as o:
        for dp, _, fs in os.walk(a.root):
            for f in sorted(fs):
                if not f.endswith(".py") or f.startswith("test"): continue
                p = os.path.join(dp, f)
                try: text = open(p, encoding="utf-8").read(); t = ast.parse(text)
                except Exception: continue
                imports = [ast.get_source_segment(text, x) for x in t.body if isinstance(x, (ast.Import, ast.ImportFrom))]
                for x in t.body:
                    if isinstance(x, ast.FunctionDef) and not x.name.startswith("_") and not x.decorator_list:
                        seg = ast.get_source_segment(text, x)
                        if seg and a.min_lines <= seg.count("\n") + 1 <= a.max_lines:
                            src = "\n".join(i for i in imports if i) + ("\n\n" if imports else "") + seg + "\n"
                            o.write(json.dumps(dict(id=f"{os.path.relpath(p, a.root)}::{x.name}", fn=x.name, source=src)) + "\n"); n += 1
    print(f"wrote {n} candidate functions to {a.out}")
main()

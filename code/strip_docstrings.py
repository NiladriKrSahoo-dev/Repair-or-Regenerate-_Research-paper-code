import ast, json
out = open('pool_nodoc.jsonl', 'w'); k = 0
for l in open('pool.jsonl'):
    r = json.loads(l)
    try: t = ast.parse(r['source'])
    except Exception: continue
    for n in ast.walk(t):
        if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Module)) and n.body and isinstance(n.body[0], ast.Expr) \
           and isinstance(n.body[0].value, ast.Constant) and isinstance(n.body[0].value.value, str):
            n.body = n.body[1:] or [ast.Pass()]
    r['source'] = ast.unparse(t) + '\n'; out.write(json.dumps(r) + '\n'); k += 1
print('wrote', k)


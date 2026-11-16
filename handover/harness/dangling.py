"""Every `module.name` and `from module import name` that points into src/council must name something the
module defines at its top level. Prints the ones that do not."""
import ast, sys
from pathlib import Path
root = Path(sys.argv[1]); src = root / "src"
def module_file(name):
    p = src / Path(*name.split("."))
    return p.with_suffix(".py") if p.with_suffix(".py").is_file() else (p / "__init__.py" if (p / "__init__.py").is_file() else None)
def top_names(path, seen={}):
    if path in seen: return seen[path]
    names = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree) if False else tree.body:
        for sub in ast.walk(node) if isinstance(node, (ast.If, ast.Try, ast.With, ast.For)) else [node]:
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)): names.add(sub.name)
            elif isinstance(sub, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                for t in (sub.targets if isinstance(sub, ast.Assign) else [sub.target]):
                    for n in ast.walk(t):
                        if isinstance(n, ast.Name): names.add(n.id)
            elif isinstance(sub, (ast.Import, ast.ImportFrom)):
                for a in sub.names: names.add((a.asname or a.name).split(".")[0])
    if path.name == "__init__.py":
        names |= {p.stem for p in path.parent.glob("*.py")} | {p.name for p in path.parent.iterdir() if p.is_dir()}
    seen[path] = names
    return names
bad = 0; checked = 0
files = [p for d in ("src", "evals", "tests", "scripts", "hooks") for p in (root / d).rglob("*.py")]
for f in files:
    try: tree = ast.parse(f.read_text(encoding="utf-8"))
    except SyntaxError as e: print("SYNTAX", f, e); bad += 1; continue
    alias = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "council" and not node.level:
            mf = module_file(node.module)
            for a in node.names:
                sub = module_file(node.module + "." + a.name)
                if sub: alias[a.asname or a.name] = sub
                elif mf and a.name != "*" and a.name not in top_names(mf):
                    print("%s:%d from %s import %s" % (f.relative_to(root), node.lineno, node.module, a.name)); bad += 1
                elif not mf:
                    print("%s:%d no module %s" % (f.relative_to(root), node.lineno, node.module)); bad += 1
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] == "council" and a.asname and module_file(a.name): alias[a.asname] = module_file(a.name)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in alias:
            checked += 1
            if node.attr not in top_names(alias[node.value.id]) and not node.attr.startswith("__"):
                print("%s:%d %s.%s (not in %s)" % (f.relative_to(root), node.lineno, node.value.id, node.attr, alias[node.value.id].relative_to(root))); bad += 1
print("files", len(files), "module attributes checked", checked, "dangling", bad)

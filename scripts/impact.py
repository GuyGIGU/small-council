#!/usr/bin/env python3
"""Optional, bounded impact provider for a Small Council run.

The Git delta is authoritative. Python AST and literal relative JS/TS imports add direct
relationships, not a complete call graph. Everything emitted is evidence-labelled TSV.
"""

import argparse
import ast
import difflib
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile


HEADER = "kind\tsource\ttarget\trelation\tevidence\tconfidence"
MAX_FILES = 2000
MAX_BYTES = 64 * 1024 * 1024
MAX_FILE_BYTES = 512 * 1024
MAX_CHANGED_DETAIL = 200
JS_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")
JS_IMPORT = re.compile(
    r"(?:\b(?:import|export)\s+(?:[^;'\"]*?\s+from\s+)?|\brequire\s*\(\s*|\bimport\s*\(\s*)"
    r"[\"'](\.{1,2}/[^\"']+)[\"']"
)
JS_SYMBOL = re.compile(
    r"\b(?:function|class|interface|type|enum)\s+([A-Za-z_$][\w$]*)\b|"
    r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*="
)


def git(root, *args, allow_error=False):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if result.returncode and not allow_error:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip() or "git failed")
    return result.stdout


def paths(blob):
    return [item.decode("utf-8", "surrogateescape") for item in blob.split(b"\0") if item]


def change_rows(root, base):
    fields = paths(git(root, "-c", "core.quotePath=false", "diff", "-M", "--name-status", "-z", base, "--"))
    changes = {}
    index = 0
    while index < len(fields):
        status = fields[index]
        index += 1
        if status[:1] in ("R", "C"):
            old, path = fields[index:index + 2]
            index += 2
        else:
            path = fields[index]
            old = "-"
            index += 1
        if path.startswith(".council/"):
            continue
        changes[path] = (status[:1], old)
    for path in paths(git(root, "ls-files", "--others", "--exclude-standard", "-z")):
        if not path.startswith(".council/") and (root / path).is_file():
            changes.setdefault(path, ("?", "-"))
    return changes


def provenance(root, base, changes):
    committed = set(paths(git(root, "diff", "--name-only", "-z", base, "HEAD", "--")))
    staged = set(paths(git(root, "diff", "--cached", "--name-only", "-z", "HEAD", "--")))
    unstaged = set(paths(git(root, "diff", "--name-only", "-z", "--")))
    result = {}
    for path, (status, old) in changes.items():
        labels = [label for label, names in (("committed", committed), ("staged", staged), ("unstaged", unstaged))
                  if path in names or old in names]
        if status == "?":
            labels.append("untracked")
        result[path] = "+".join(labels) or "unknown"
    return result


def source_paths(root, changed):
    tracked = paths(git(root, "ls-files", "-z"))
    untracked = paths(git(root, "ls-files", "--others", "--exclude-standard", "-z"))
    candidates = set(tracked + untracked)
    candidates.update(changed)
    accepted = []
    for path in sorted(candidates):
        if path.startswith(".council/") or any(part in ("node_modules", "vendor", "dist", "build", ".git")
                                                     for part in PurePosixPath(path).parts):
            continue
        if path.endswith((".py",) + JS_EXTENSIONS) and not (root / path).is_symlink() and (root / path).is_file():
            accepted.append(path)
    priority = [path for path in sorted(changed) if path in accepted]
    ordered = priority + [path for path in accepted if path not in changed]
    return ordered[:MAX_FILES], max(0, len(ordered) - MAX_FILES)


def read_worktree(root, path):
    file = root / path
    if file.is_symlink():
        return None  # Never follow a repository symlink into files outside the code root.
    if file.stat().st_size > MAX_FILE_BYTES:
        return None
    raw = file.read_bytes()
    if b"\0" in raw:
        return None
    return raw.decode("utf-8", "replace")


def read_base(root, base, path):
    blob = git(root, "show", f"{base}:{path}", allow_error=True)
    if len(blob) > MAX_FILE_BYTES or b"\0" in blob:
        return None
    return blob.decode("utf-8", "replace")


def python_module(path):
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def python_module_names(path):
    canonical = python_module(path)
    names = [canonical] if canonical else []
    if canonical.startswith("src."):
        names.append(canonical[4:])  # common src-layout absolute imports
    return names


def python_imports(path, content, modules):
    try:
        tree = ast.parse(content, filename=path)
    except SyntaxError:
        return None
    current = python_module(path)
    package = current if path.endswith("/__init__.py") else current.rpartition(".")[0]
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in modules:
                    found.add((modules[alias.name], f"import {alias.name}", node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".") if package else []
                parts = parts[:max(0, len(parts) - node.level + 1)]
                prefix = ".".join(parts)
                name = ".".join(filter(None, (prefix, node.module or "")))
            else:
                name = node.module or ""
            candidates = [name] if name else []
            candidates.extend(".".join(filter(None, (name, alias.name))) for alias in node.names if alias.name != "*")
            resolved = [candidate for candidate in candidates if candidate in modules]
            # A submodule is more specific than its package; a symbol import resolves to the package file.
            for candidate in resolved:
                if candidate != name or not any(other.startswith(name + ".") for other in resolved):
                    found.add((modules[candidate], f"from {name or '.'} import", node.lineno))
    return found


def js_imports(path, content, universe):
    found = set()
    for match in JS_IMPORT.finditer(content):
        spec = match.group(1)
        stem = str(PurePosixPath(path).parent.joinpath(spec))
        normalized = os.path.normpath(stem).replace("\\", "/")
        if normalized.startswith("../") or normalized == "..":
            continue
        candidates = [normalized]
        candidates.extend(normalized + ext for ext in JS_EXTENSIONS)
        candidates.extend(normalized + "/index" + ext for ext in JS_EXTENSIONS)
        for candidate in candidates:
            if candidate in universe:
                line = content.count("\n", 0, match.start()) + 1
                found.add((candidate, f"literal relative import {spec}", line))
                break
    return found


def python_definitions(content):
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None
    definitions = []

    def walk(body, prefix=""):
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + node.name
                definitions.append((name, node.lineno, getattr(node, "end_lineno", node.lineno)))
                walk(node.body, name + ".")

    walk(tree.body)
    return definitions


def changed_lines(old, new):
    left, right = set(), set()
    matcher = difflib.SequenceMatcher(None, old.splitlines(), new.splitlines())
    for tag, a0, a1, b0, b1 in matcher.get_opcodes():
        if tag != "equal":
            left.update(range(a0 + 1, a1 + 1))
            right.update(range(b0 + 1, b1 + 1))
    return left, right


def changed_symbols(path, old, new):
    old_lines, new_lines = changed_lines(old or "", new or "")
    if path.endswith(".py"):
        before = python_definitions(old or "") if old is not None else []
        after = python_definitions(new or "") if new is not None else []
        if before is None or after is None:
            return [], "Python syntax could not be parsed"
        names = {name for name, start, end in before if any(start <= n <= end for n in old_lines)}
        names.update(name for name, start, end in after if any(start <= n <= end for n in new_lines))
        return sorted(names), None
    if path.endswith(JS_EXTENSIONS):
        names = set()
        for content, line_numbers in ((old, old_lines), (new, new_lines)):
            if content is None:
                continue
            lines = content.splitlines()
            for number in line_numbers:
                for index in range(min(number, len(lines)) - 1, max(0, number - 81) - 1, -1):
                    match = JS_SYMBOL.search(lines[index])
                    if match:
                        names.add(match.group(1) or match.group(2))
                        break
        return sorted(names), None
    return [], None


def is_test(path):
    name = PurePosixPath(path).name
    parts = PurePosixPath(path).parts
    return (any(part in ("test", "tests", "spec", "__tests__") for part in parts[:-1]) or
            name.startswith("test_") or name.endswith(("_test.py", ".test.js", ".test.jsx", ".test.ts",
                                                      ".test.tsx", ".spec.js", ".spec.jsx", ".spec.ts", ".spec.tsx")))


def surfaces(path):
    lower = path.lower()
    parts = set(PurePosixPath(lower).parts)
    result = set()
    if lower.endswith((".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env")) or "config" in parts:
        result.add("configuration")
    if parts & {"migration", "migrations", "schema", "schemas", "db", "database"} or lower.endswith(".sql"):
        result.add("persistent-data")
    if parts & {"auth", "security", "permissions", "crypto"}:
        result.add("security")
    if parts & {"ui", "frontend", "components", "pages"} or lower.endswith((".jsx", ".tsx", ".css", ".scss")):
        result.add("frontend")
    if lower.endswith((".proto", ".graphql", ".openapi.json")) or "api" in parts:
        result.add("public-interface")
    return sorted(result)


def cell(value):
    escaped = []
    for char in str(value):
        if char == "\\":
            escaped.append("\\\\")
        elif char == "\t":
            escaped.append("\\t")
        elif char == "\r":
            escaped.append("\\r")
        elif char == "\n":
            escaped.append("\\n")
        elif ord(char) < 32 or ord(char) == 127:
            escaped.append(f"\\x{ord(char):02x}")
        elif 0xDC80 <= ord(char) <= 0xDCFF:
            escaped.append(f"\\x{ord(char) - 0xDC00:02x}")
        else:
            escaped.append(char)
    return "".join(escaped) or "-"


def emit(rows, kind, source, target, relation, evidence, confidence):
    rows.add(tuple(map(cell, (kind, source, target, relation, evidence, confidence))))


def build(root, base):
    changes = change_rows(root, base)
    origins = provenance(root, base, changes)
    rows = set()
    emit(rows, "schema", "impact", "1", "version", "direct, bounded impact graph", "high")
    for path, (status, old) in changes.items():
        emit(rows, "change", path, old, status, origins[path], "high")
        for surface in surfaces(path):
            emit(rows, "surface", path, surface, "path-heuristic", "path words or extension", "low")

    ordered, omitted = source_paths(root, changes)
    if omitted:
        emit(rows, "limit", "scan", str(omitted), "files-omitted", f"first {MAX_FILES} source files scanned", "high")
    former_paths = {old: path for path, (status, old) in changes.items() if status == "R" and old != "-"}
    removed_paths = {path for path, (status, _) in changes.items() if status == "D"}
    affected_targets = set(changes) | set(former_paths)
    universe = set(ordered) | set(former_paths) | removed_paths
    module_paths = ordered + sorted((set(former_paths) | removed_paths) - set(ordered))
    modules = {}
    for path in module_paths:
        if path.endswith(".py"):
            name = python_module(path)
            if name:
                modules.setdefault(name, path)
    for path in module_paths:
        if path.endswith(".py"):
            for alias in python_module_names(path)[1:]:
                modules.setdefault(alias, path)  # exact package paths always take precedence
    imports = set()
    consumed = 0
    for path in ordered:
        if consumed >= MAX_BYTES:
            emit(rows, "limit", "scan", str(len(ordered) - ordered.index(path)), "bytes-exhausted",
                 f"at most {MAX_BYTES} bytes scanned", "high")
            break
        content = read_worktree(root, path)
        if content is None:
            emit(rows, "limit", path, "-", "unreadable-or-large", f"per-file limit {MAX_FILE_BYTES} bytes", "high")
            continue
        consumed += len(content.encode("utf-8", "replace"))
        if path.endswith(".py"):
            found = python_imports(path, content, modules)
            if found is None:
                emit(rows, "limit", path, "-", "syntax-error", "Python AST provider skipped this file", "high")
                continue
            provider = "python-ast"
        else:
            found = js_imports(path, content, universe)
            provider = "js-literal-import"
        for target, text, line in found:
            if target != path:
                imports.add((path, target, text, line, provider))

    test_links = set()
    impacted = set()
    for source, target, text, line, provider in imports:
        confidence = "high" if provider == "python-ast" else "medium"
        if source in changes or target in affected_targets:
            emit(rows, "dependency", source, target, "imports", f"{provider}:{source}:{line}:{text}", confidence)
        if target in affected_targets and source not in changes:
            impacted.add(source)
            relation = "former-path-importer" if target in former_paths else "direct-importer"
            evidence = f"{provider}:{source}:{line}"
            if target in former_paths:
                evidence += f":renamed-to {former_paths[target]}"
            emit(rows, "impact", target, source, relation, evidence, confidence)
            if is_test(source):
                test_links.add((target, source))
                emit(rows, "test", target, source, "direct-import", f"{provider}:{source}:{line}", confidence)

    tests = [path for path in ordered if is_test(path)]
    hinted = sorted(changes)[:MAX_CHANGED_DETAIL]
    if len(changes) > MAX_CHANGED_DETAIL:
        emit(rows, "limit", "name-hints", str(len(changes) - MAX_CHANGED_DETAIL), "changes-omitted",
             f"first {MAX_CHANGED_DETAIL} changed paths considered", "high")
    for path in hinted:
        stem = PurePosixPath(path).stem
        if len(stem) < 3:
            continue
        for test in tests:
            if test == path or (path, test) in test_links:
                continue
            if stem.lower() in PurePosixPath(test).stem.lower():
                test_links.add((path, test))
                emit(rows, "test", path, test, "name-match", "filename only; inspect before relying on it", "low")

    detail_paths = [path for path in sorted(changes) if path.endswith((".py",) + JS_EXTENSIONS)]
    if len(detail_paths) > MAX_CHANGED_DETAIL:
        emit(rows, "limit", "symbols", str(len(detail_paths) - MAX_CHANGED_DETAIL), "changes-omitted",
             f"first {MAX_CHANGED_DETAIL} changed source files considered", "high")
    for path in detail_paths[:MAX_CHANGED_DETAIL]:
        status, old = changes[path]
        before = read_base(root, base, old if status in ("R", "C") else path) if status != "?" else None
        after = None if status == "D" else read_worktree(root, path)
        if (before is None and status not in ("A", "?")) or (after is None and status != "D"):
            emit(rows, "limit", path, "-", "symbol-source-unavailable", "large, binary or missing source", "high")
            continue
        names, warning = changed_symbols(path, before, after)
        if warning:
            emit(rows, "limit", path, "-", "symbol-provider-skipped", warning, "high")
        for name in names:
            provider = "python-ast" if path.endswith(".py") else "js-diff-definition"
            emit(rows, "symbol", path, name, "changed-definition", provider, "high" if path.endswith(".py") else "medium")
    return rows, len(changes), len(impacted), len(test_links)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--base", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    rows, changes, impacted, tests = build(root, args.base)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=args.output.parent,
                                     prefix=".impact-", delete=False) as stream:
        temp = Path(stream.name)
        stream.write(HEADER + "\n")
        for row in sorted(rows, key=lambda row: (row[0] != "schema", row)):
            stream.write("\t".join(row) + "\n")
    os.replace(temp, args.output)
    print(f"impact: {changes} changed, {impacted} direct importer(s), {tests} linked test(s) -> impact.tsv")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"impact: {exc}", file=sys.stderr)
        sys.exit(2)

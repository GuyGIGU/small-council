"""council init's check detection: the project's candidate check commands, read from its own manifests and scripts at
the code root (package.json scripts, Python tool config, Cargo.toml, go.mod, a Makefile's targets, CMake with tests,
Gradle, Maven, .NET, RSpec and RuboCop, and build or test scripts in the root, scripts/ or tools/). Each comes with a
fast form to probe, a broken twin that must fail, and what it is. Nothing here runs a command: the Chair probes each
one with `council gate probe-<name> -- '<fast form>'`. A tool the project doesn't show is never offered."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Callable, NamedTuple


class Check(NamedTuple):
    """One candidate check: its gate name, kind (test, lint, type check, build, format, check), the command the Gates
    row runs, the fast form to probe, its broken twin, where the project shows it, what it needs, its side effects."""

    name: str
    kind: str
    command: str
    probe: str
    broken: str
    source: str
    needs: str
    side: str = "none"


SCRIPT_DIRS = ("", "scripts/", "tools/")
SCRIPT_EXT = ("sh", "ps1", "cmd", "bat")
KINDS = {"typecheck": "type check", "types": "type check", "tsc": "type check", "test": "test", "tests": "test",
         "e2e": "test", "unit": "test", "lint": "lint", "build": "build", "format": "format", "fmt": "format",
         "check": "check"}
NOT_A_CHECK = {"fix", "write", "watch", "dev", "serve", "start", "deploy", "publish", "release", "clean", "install"}
NPM_PLACEHOLDER = 'echo "Error: no test specified"'
PY_TOOLS = ("pytest", "ruff", "mypy", "black", "flake8")


def _read(root: Path, name: str) -> str:
    try:
        return (root / name).read_bytes().decode("utf-8", "replace")
    except OSError:
        return ""


def _kind(word: str) -> str:
    """The kind a script or target name says, by its first token that names one; '' for none, and for a name that
    also says it changes files or keeps running (lint:fix, test:watch, build-and-deploy)."""
    folded = re.sub(r"type-?check|check-?types", "typecheck", word.lower())
    tokens = re.split(r"[^a-z0-9]+", folded)
    if NOT_A_CHECK & set(tokens):
        return ""
    return next((KINDS[token] for token in tokens if token in KINDS), "")


def _side(kind: str, name: str) -> str:
    """A build writes the tree, and so does a format step that doesn't say it only checks."""
    if kind == "build" or (kind == "format" and "check" not in name.lower()):
        return "writes the tree"
    return "none"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _safe(word: str) -> bool:
    """A name that goes into a command as it is: no quote, space or shell character."""
    return re.fullmatch(r"[A-Za-z0-9_.:/-]+", word) is not None


def node(root: Path, files: set[str]) -> list[Check]:
    """package.json's scripts that name a test, lint, type check, build or format step, run by the project's package
    manager (its lockfile says which); tsc and eslint only when the project has their config and no such script."""
    text = _read(root, "package.json")
    if not text:
        return []
    try:
        scripts = json.loads(text).get("scripts", {})
    except (ValueError, AttributeError):
        return []
    scripts = scripts if isinstance(scripts, dict) else {}
    runner = next((tool for lock, tool in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"),
                                           ("bun.lock", "bun")) if lock in files), "npm")
    found = []
    for script, body in sorted(scripts.items()):
        kind = _kind(script)
        if not kind or not _safe(script) or not isinstance(body, str) or NPM_PLACEHOLDER in body:
            continue
        command = "%s run %s" % (runner, script)
        found.append(Check(_slug("%s-%s" % (runner, script)), kind, command, command,
                           "%s run %s-not-a-script" % (runner, script),
                           "package.json script %s: %s" % (script, body[:80]), "node, " + runner,
                           _side(kind, script)))
    kinds = {check.kind for check in found}
    if "tsconfig.json" in files and "type check" not in kinds:
        found.append(Check("tsc", "type check", "npx --no-install tsc --noEmit", "npx --no-install tsc --version",
                           "npx --no-install tsc-not-installed --version", "tsconfig.json", "node, typescript"))
    eslint = sorted(f for f in files if "/" not in f and re.match(r"(\.eslintrc(\..+)?|eslint\.config\.[a-z]+)\Z", f))
    if eslint and "lint" not in kinds:
        found.append(Check("eslint", "lint", "npx --no-install eslint .", "npx --no-install eslint --version",
                           "npx --no-install eslint-not-installed --version", eslint[0], "node, eslint"))
    return found


def _python_shows(root: Path, files: set[str]) -> dict[str, str]:
    """Each Python tool the project shows, with where: its own config file or section, or a dependency line."""
    shown: dict[str, str] = {}
    for name, tool in (("pytest.ini", "pytest"), ("conftest.py", "pytest"), ("ruff.toml", "ruff"),
                       (".ruff.toml", "ruff"), ("mypy.ini", "mypy"), (".mypy.ini", "mypy"), (".flake8", "flake8")):
        if name in files:
            shown.setdefault(tool, name)
    for name in ("pyproject.toml", "setup.cfg", "tox.ini"):
        for head in re.findall(r"(?m)^\[([a-z_:.-]+)", _read(root, name) if name in files else ""):
            tool = head.replace("tool:", "tool.").split(".")
            word = tool[1] if tool[0] == "tool" and len(tool) > 1 else tool[0]
            if word in PY_TOOLS:
                shown.setdefault(word, "%s [%s]" % (name, head))
    for name in sorted(f for f in files if "/" not in f and (re.fullmatch(r"requirements[\w.-]*\.txt", f)
                                                            or f in ("pyproject.toml", "setup.cfg", "Pipfile"))):
        for tool in PY_TOOLS:
            if tool not in shown and re.search(r"(?<![\w-])%s(?![\w-])" % tool, _read(root, name)):
                shown[tool] = "%s names %s" % (name, tool)
    return shown


PYTHON = {
    "pytest": ("test", "python -m pytest -q", "python -m pytest --collect-only -q",
               "python -m pytest_not_installed --collect-only -q"),
    "ruff": ("lint", "ruff check .", "ruff check .", "ruff-not-installed check ."),
    "mypy": ("type check", "python -m mypy .", "python -m mypy --version", "python -m mypy_not_installed --version"),
    "black": ("format", "python -m black --check .", "python -m black --version",
              "python -m black_not_installed --version"),
    "flake8": ("lint", "python -m flake8", "python -m flake8 --version", "python -m flake8_not_installed --version"),
}


def python(root: Path, files: set[str]) -> list[Check]:
    shown = _python_shows(root, files)
    return [Check(tool, *PYTHON[tool], source=shown[tool], needs="python, " + tool) for tool in PY_TOOLS
            if tool in shown]


def rust(root: Path, files: set[str]) -> list[Check]:
    if "Cargo.toml" not in files:
        return []
    cargo = _read(root, "Cargo.toml")
    found = [Check("cargo-test", "test", "cargo test", "cargo test --no-run",
                   "cargo test --no-run --manifest-path no-such-dir/Cargo.toml", "Cargo.toml", "cargo",
                   "writes the tree")]
    if {"clippy.toml", ".clippy.toml"} & files or re.search(r"(?m)^\[(workspace\.)?lints\.clippy\]", cargo):
        found.append(Check("cargo-clippy", "lint", "cargo clippy -- -D warnings", "cargo clippy --version",
                           "cargo clippy-not-installed --version", "clippy config", "cargo, clippy"))
    if {"rustfmt.toml", ".rustfmt.toml"} & files:
        found.append(Check("cargo-fmt", "format", "cargo fmt --check", "cargo fmt --version",
                           "cargo fmt-not-installed --version", "rustfmt.toml", "cargo, rustfmt"))
    return found


def go(root: Path, files: set[str]) -> list[Check]:
    if "go.mod" not in files:
        return []
    found = [Check("go-test", "test", "go test ./...", "go test -count=1 -run NO_TEST_MATCHES ./...",
                   "go test -count=1 -run NO_TEST_MATCHES ./no-such-package/...", "go.mod", "go"),
             Check("go-vet", "lint", "go vet ./...", "go vet ./...", "go vet ./no-such-package/...", "go.mod", "go")]
    linter = sorted(f for f in files if re.fullmatch(r"\.golangci\.(ya?ml|toml|json)", f))
    if linter:
        found.append(Check("golangci-lint", "lint", "golangci-lint run", "golangci-lint --version",
                           "golangci-lint-not-installed --version", linter[0], "golangci-lint"))
    return found


def make(root: Path, files: set[str]) -> list[Check]:
    name = next((f for f in ("GNUmakefile", "makefile", "Makefile") if f in files), "")
    targets = re.findall(r"(?m)^([A-Za-z0-9][A-Za-z0-9_.-]*)[ \t]*:(?!=)", _read(root, name) if name else "")
    found = []
    for target in sorted(set(targets)):
        kind = _kind(target)
        if kind:
            found.append(Check(_slug("make-" + target), kind, "make " + target, "make -n " + target,
                               "make -n %s-not-a-target" % target, "%s target %s" % (name, target), "make",
                               _side(kind, target)))
    return found


def cmake(root: Path, files: set[str]) -> list[Check]:
    if "CMakeLists.txt" not in files:
        return []
    found = [Check("cmake-build", "build", "cmake -S . -B build && cmake --build build", "cmake -S . -B build",
                   "cmake -S no-such-dir -B build", "CMakeLists.txt (build folder: build/)", "cmake, a C/C++ compiler",
                   "writes the tree")]
    if re.search(r"(?i)\b(enable_testing|add_test|include\s*\(\s*CTest)", _read(root, "CMakeLists.txt")):
        found.append(Check("ctest", "test", "ctest --test-dir build --output-on-failure", "ctest --test-dir build -N",
                           "ctest-not-installed --test-dir build -N",
                           "CMakeLists.txt enables tests (after cmake-build)",
                           "cmake, a built tree in build/"))
    return found


def jvm_dotnet_ruby(root: Path, files: set[str]) -> list[Check]:
    found = []
    gradle = next((f for f in ("build.gradle", "build.gradle.kts") if f in files), "")
    if gradle:
        tool = "./gradlew" if "gradlew" in files else "gradle"
        found += [Check("gradle-test", "test", tool + " test", tool + " --version", tool + " no-such-task",
                        gradle, "a JDK" + ("" if tool == "./gradlew" else ", gradle"), "writes the tree")]
    if "pom.xml" in files:
        found.append(Check("maven-test", "test", "mvn -q test", "mvn -v", "mvn-not-installed -v", "pom.xml",
                           "a JDK, maven", "writes the tree"))
    solution = sorted(f for f in files if "/" not in f and re.search(r"\.(sln|csproj|fsproj)\Z", f))
    if solution:
        found.append(Check("dotnet-test", "test", "dotnet test", "dotnet --version", "dotnet-not-installed --version",
                           solution[0], "the .NET SDK", "writes the tree"))
    if "Gemfile" in files and (".rspec" in files or any(f.startswith("spec/") for f in files)):
        found.append(Check("rspec", "test", "bundle exec rspec", "bundle exec rspec --dry-run",
                           "bundle exec rspec-not-installed --dry-run", ".rspec" if ".rspec" in files else "spec/",
                           "ruby, bundler"))
    if "Gemfile" in files and ".rubocop.yml" in files:
        found.append(Check("rubocop", "lint", "bundle exec rubocop", "bundle exec rubocop --version",
                           "bundle exec rubocop-not-installed --version", ".rubocop.yml", "ruby, bundler"))
    return found


def scripts(root: Path, files: set[str]) -> list[Check]:
    """A build or test script (.sh, .ps1, .cmd, .bat) in the root, scripts/ or tools/ whose name says its kind."""
    found = []
    for path in sorted(files):
        folder, _, name = path.rpartition("/")
        stem, _, ext = name.rpartition(".")
        kind = _kind(stem) if stem else ""
        if not kind or ext.lower() not in SCRIPT_EXT or (folder + "/" if folder else "") not in SCRIPT_DIRS:
            continue
        if not _safe(path):
            continue
        missing = (folder + "/" if folder else "") + "no-such-" + name
        command, broken, needs = _script_call(path, missing, ext.lower())
        found.append(Check(_slug(path.replace("/", "-")), kind, command, command, broken, path, needs,
                           _side(kind, stem)))
    return found


def _script_call(path: str, missing: str, ext: str) -> tuple[str, str, str]:
    if ext == "sh":
        return "bash " + path, "bash " + missing, "bash"
    if ext == "ps1":
        shell = "powershell" if os.name == "nt" else "pwsh"
        return ("%s -NoProfile -File %s" % (shell, path), "%s -NoProfile -File %s" % (shell, missing),
                "PowerShell (%s)" % shell)
    return 'cmd //c "%s"' % path.replace("/", "\\"), 'cmd //c "%s"' % missing.replace("/", "\\"), "Windows (cmd)"


FINDERS: tuple[Callable[[Path, set[str]], list[Check]], ...] = (node, python, rust, go, make, cmake, jvm_dotnet_ruby,
                                                                scripts)
LOOKED_AT = ("package.json scripts", "Python tool config (pyproject.toml, setup.cfg, tox.ini, pytest.ini, ruff, mypy, "
             "flake8, requirements)", "Cargo.toml", "go.mod", "Makefile targets", "CMakeLists.txt", "Gradle", "Maven",
             ".NET", "RSpec and RuboCop", "build and test scripts in the root, scripts/ and tools/")


def found(root: Path, files: list[str]) -> list[Check]:
    """Every candidate check the project shows, finder by finder; a name taken twice keeps its first."""
    listed, seen, out = set(files), set(), []
    for finder in FINDERS:
        for check in finder(root, listed):
            if check.name and check.name not in seen:
                seen.add(check.name)
                out.append(check)
    return out

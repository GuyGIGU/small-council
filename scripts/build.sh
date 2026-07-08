#!/usr/bin/env bash
# Build Council .skill packages from skills/*/ + the shared references/ directory.
# Each .skill is a zip of {SKILL.md, manifest.json, references/<declared refs>}.
# Reference bundling lives in package_skill.py (pure Python) so it is robust across filesystems and
# line endings — do NOT move it back into a shell copy loop (CRLF drops all but the last ref).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REF_DIR="references"
OUT="dist"
mkdir -p "$OUT"

# Prefer python3, fall back to python (Windows / Git-Bash often only ships `python`).
PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then echo "ERROR: no python3/python on PATH" >&2; exit 1; fi

# Validate first (hard errors abort the build; missing refs are soft warnings from the packager).
"$PY" scripts/quick_validate.py

for skill_dir in skills/*/; do
  name="$(basename "$skill_dir")"
  "$PY" scripts/package_skill.py "$skill_dir" "$REF_DIR" "$OUT/$name.skill"
done

echo "Done. Packages in $OUT/:"
ls -1 "$OUT"

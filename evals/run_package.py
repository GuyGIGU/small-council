#!/usr/bin/env python3
"""Package evals for Ultra Council — runnable without an LLM or the network.

Builds every skill under skills/*/ into a .skill with scripts/package_skill.py and asserts the
package is a valid, portable, path-safe artifact: it is a real zip; it carries SKILL.md +
manifest.json; every reference the manifest declares is bundled under references/; no member ships
CRLF (a past bug dropped refs on Windows when a shell copy loop hit CRLF); no member arcname escapes
the archive (absolute or "..") ; and the manifest name matches the folder name.

It also builds a hostile fixture whose manifest declares a "../etc/passwd" reference and asserts the
packager REFUSES it — the traversal entry is never written into the zip.

Companion to run_structural.py (the framework-invariants eval); this one guards the build output.
"""
import json
import os
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
REFS = os.path.join(ROOT, "references")
PACKAGER = os.path.join(ROOT, "scripts", "package_skill.py")

results = []


def check(name, ok, detail=""):
    results.append((ok, name, detail))


def package(skill_dir, refs_dir, out_path):
    """Build one .skill via package_skill.py; return (ok, stderr)."""
    proc = subprocess.run(
        [sys.executable, PACKAGER, skill_dir, refs_dir, out_path],
        capture_output=True, text=True,
    )
    return proc.returncode == 0 and os.path.isfile(out_path), proc.stderr


def escapes(arcname):
    """True if a zip member name is absolute or walks out of the archive."""
    norm = arcname.replace("\\", "/")
    return os.path.isabs(arcname) or norm.startswith("/") or ".." in norm.split("/") \
        or (len(norm) > 1 and norm[1] == ":")


with tempfile.TemporaryDirectory() as tmp:
    # 1. Every real skill packages into a valid, portable, path-safe .skill.
    for name in sorted(os.listdir(SKILLS)):
        sdir = os.path.join(SKILLS, name)
        if not os.path.isdir(sdir):
            continue
        out = os.path.join(tmp, name + ".skill")
        ok, err = package(sdir, REFS, out)
        check(f"{name}: packages without error", ok, err.strip())
        if not ok:
            continue

        check(f"{name}: is a valid zip", zipfile.is_zipfile(out))
        with zipfile.ZipFile(out) as z:
            members = z.namelist()
            check(f"{name}: contains SKILL.md", "SKILL.md" in members)
            check(f"{name}: contains manifest.json", "manifest.json" in members)

            manifest = json.loads(z.read("manifest.json"))
            check(f"{name}: manifest name matches folder",
                  manifest.get("name") == name, manifest.get("name", ""))

            declared = [r.strip() for r in manifest.get("references", []) if r.strip()]
            missing = [r for r in declared if "references/" + r not in members]
            check(f"{name}: all declared references bundled",
                  not missing, ", ".join(missing))

            crlf = [m for m in members if b"\r\n" in z.read(m)]
            check(f"{name}: no member ships CRLF", not crlf, ", ".join(crlf))

            bad = [m for m in members if escapes(m)]
            check(f"{name}: no member escapes the archive", not bad, ", ".join(bad))

    # 2. Hostile fixture: a "../etc/passwd" reference must be refused, never written into the zip.
    evil = os.path.join(tmp, "evil-skill")
    os.makedirs(evil)
    with open(os.path.join(evil, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("---\nname: evil-skill\ndescription: traversal fixture\n---\nbody\n")
    with open(os.path.join(evil, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"name": "evil-skill", "references": ["../etc/passwd"]}, f)

    evil_out = os.path.join(tmp, "evil-skill.skill")
    ok, _ = package(evil, REFS, evil_out)
    check("traversal fixture: packages (with the bad ref refused)", ok)
    if ok:
        with zipfile.ZipFile(evil_out) as z:
            members = z.namelist()
            leaked = [m for m in members if escapes(m) or "passwd" in m]
            check("traversal fixture: no traversal member written", not leaked, ", ".join(leaked))
            check("traversal fixture: only SKILL.md + manifest.json written",
                  set(members) == {"SKILL.md", "manifest.json"}, ", ".join(sorted(members)))

# Report (matches run_structural.py's format)
passed = sum(1 for ok, *_ in results if ok)
for ok, name, detail in results:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f"  ({detail})" if detail and not ok else ""))
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)

"""Show, for each differing call in an oldnew diffs.txt, only the lines that changed.

Usage: difflook.py <diffs.txt> [skip-substring ...]   (a stream whose label holds a skip-substring is left out)
"""
import ast
import collections
import difflib
import io
import re
import sys

RUN = re.compile(r"\d{4}-\d{2}-\d{2}-\d{6}")


def value(line):
    text = line.split("=", 1)[1]
    try:
        got = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text
    return "" if got is None else str(got)


def changed(old, new):
    out = []
    for line in difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0):
        if line.startswith(("---", "+++", "@@")):
            continue
        out.append(RUN.sub("<RUN>", line)[:230])
    return out


def main():
    path, skips = sys.argv[1], sys.argv[2:]
    blocks = io.open(path, encoding="utf-8", errors="replace").read().split("\n== ")
    seen = collections.Counter()
    for block in blocks:
        lines = block.split("\n")
        head = lines[0].lstrip("= ")
        shown = []
        i = 1
        while i < len(lines):
            label = lines[i]
            if i + 2 < len(lines) and lines[i + 1].startswith("  old=") and lines[i + 2].startswith("  new="):
                if not any(s in label for s in skips):
                    delta = changed(value(lines[i + 1]), value(lines[i + 2]))
                    key = (RUN.sub("<RUN>", label), tuple(delta))
                    seen[key] += 1
                    if seen[key] == 1:
                        shown.append("  " + RUN.sub("<RUN>", label))
                        shown.extend("    " + d for d in delta[:14])
                        if len(delta) > 14:
                            shown.append("    … %d more changed lines" % (len(delta) - 14))
                    else:
                        shown.append("  %s (same change as an earlier call)" % RUN.sub("<RUN>", label))
                i += 3
            else:
                i += 1
        if shown:
            print("== " + RUN.sub("<RUN>", head)[:150])
            print("\n".join(shown))


main()

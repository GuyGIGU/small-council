#!/usr/bin/env python3
"""Build a bounded, seat-specific context pack from one Small Council run.

This is a read-only selector, not a seat router. The brief's slice decides scope;
the optional impact graph supplies direct relationships. No project code is run.
"""

import argparse
import fnmatch
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile


LEVELS = {
    "minimal": (8, 16, 4096),
    "focused": (24, 64, 12288),
    "full": (80, 200, 32768),
}
IMPACT_HEADER = "kind\tsource\ttarget\trelation\tevidence\tconfidence"
SECTION = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
INDEX_ENTRY = re.compile(r"^## (.+?)  \(", re.MULTILINE)
SEAT_HEADING = re.compile(r"^### ([A-Za-z0-9][A-Za-z0-9._-]*)(?=\s|$)")
SLICE_LINE = re.compile(r"^\s*-\s*slice\s*:\s*(.*)$", re.IGNORECASE | re.MULTILINE)
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
MAX_EXPAND_BYTES = 512 * 1024


class ContextError(Exception):
    """A user-facing input or scope error."""


def within(parent, path):
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def rebase(path, given, root):
    """Spell an absolute path under the resolved root when it arrives under the root as given.

    The root is resolved, but the paths beside it arrive as spelled: on macOS /var is a link to
    /private/var, and a Windows temp folder can be an 8.3 name (RUNNER~1). Links below the root
    are still refused by safe_path."""
    if not path.is_absolute():
        return path
    path = Path(os.path.abspath(str(path)))
    if within(given, path) and not within(root, path):
        return root / path.relative_to(given)
    return path


def safe_path(parent, candidate, *, must_exist=True, regular=False):
    """Reject traversal and symlink components before any file read or write."""
    parent = parent.absolute()
    path = candidate if candidate.is_absolute() else parent / candidate
    path = Path(os.path.abspath(str(path)))
    if not within(parent, path):
        raise ContextError("path is outside the allowed directory: " + str(candidate))
    cursor = parent
    if cursor.is_symlink():
        raise ContextError("symlink directory is not allowed: " + str(cursor))
    for part in path.relative_to(parent).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ContextError("symlink path is not allowed: " + str(candidate))
    if must_exist and not path.exists():
        raise ContextError("path does not exist: " + str(candidate))
    if regular and not path.is_file():
        raise ContextError("not a regular file: " + str(candidate))
    return path


def read_artifact(run, name, *, optional=False):
    path = safe_path(run, Path(name), must_exist=not optional)
    if optional and not path.exists():
        return "", 0
    if not path.is_file():
        raise ContextError("not a regular run file: " + str(path))
    size = path.stat().st_size
    if size > MAX_ARTIFACT_BYTES:
        raise ContextError("run file exceeds the context input limit: " + str(path))
    blob = path.read_bytes()
    return blob.decode("utf-8", "replace"), len(blob)


def sections(markdown):
    headings = list(SECTION.finditer(markdown))
    result = [("header", markdown[:headings[0].start()] if headings else markdown)]
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(markdown)
        result.append((match.group(1).strip(), markdown[match.start():end]))
    return result


def seat_block(brief, slug):
    seat_sections = [body for title, body in sections(brief) if title == "Seats"]
    if not seat_sections:
        raise ContextError("brief.md has no '## Seats' section")
    section = seat_sections[0]
    matches = list(re.finditer(r"^### .+$", section, re.MULTILINE))
    for index, match in enumerate(matches):
        heading = SEAT_HEADING.match(match.group())
        if heading and heading.group(1) == slug:
            end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
            return section[match.start():end].strip() + "\n"
    raise ContextError("seat is not present in brief.md: " + slug)


def slice_patterns(block, root):
    lines = SLICE_LINE.findall(block)
    if not lines:
        raise ContextError("seat block has no '- slice:' line")
    patterns = []
    for line in lines:
        quoted = re.findall(r"`([^`]+)`", line)
        remainder = re.sub(r"`[^`]+`", " ", line)
        tokens = quoted + re.split(r"[,;\s]+", remainder)
        for token in tokens:
            token = token.strip(" \t.,:()[]{}\"'").replace("\\", "/")
            if not token or token.lower() in {"none", "and", "or", "only"}:
                continue
            if Path(token).is_absolute():
                try:
                    token = Path(token).relative_to(root).as_posix()
                except ValueError:
                    continue
            if token.startswith("./"):
                token = token[2:]
            parts = PurePosixPath(token).parts
            if not parts or ".." in parts or token.startswith("/"):
                continue
            if "/" in token or any(char in token for char in "*?[") or "." in token or len(token) > 1:
                patterns.append(token)
    if not patterns:
        raise ContextError("seat slice has no usable in-root path or glob")
    return list(dict.fromkeys(patterns))


def matches_slice(path, patterns):
    for pattern in patterns:
        if fnmatch.fnmatchcase(path, pattern):
            return True
        if pattern.endswith("/") and path.startswith(pattern):
            return True
        if not any(char in pattern for char in "*?[") and path.startswith(pattern.rstrip("/") + "/"):
            return True
    return False


def path_cell(value):
    """Validate a graph/index path lexically; it is never opened implicitly."""
    if not value or value == "-" or value.startswith("/") or "\\" in value:
        return ""
    parts = PurePosixPath(value).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        return ""
    return value


def index_entries(index):
    matches = list(INDEX_ENTRY.finditer(index))
    entries = {}
    for number, match in enumerate(matches):
        path = path_cell(match.group(1))
        if not path:
            continue
        end = matches[number + 1].start() if number + 1 < len(matches) else len(index)
        body = index[match.start():end]
        # The earlier-work appendix and overflow summary are not a file entry.
        for marker in ("\n## Earlier council work", "\n## Past the "):
            if marker in body:
                body = body.split(marker, 1)[0]
        entries[path] = body.strip()
    return entries


def unescape_cell(cell):
    pieces = []
    position = 0
    while position < len(cell):
        if cell[position] == "\\" and position + 1 < len(cell):
            next_char = cell[position + 1]
            if next_char in {"t", "n", "r", "\\"}:
                pieces.append({"t": "\t", "n": "\n", "r": "\r", "\\": "\\"}[next_char])
                position += 2
                continue
            if next_char == "x" and re.match(r"[0-9a-fA-F]{2}", cell[position + 2:position + 4]):
                pieces.append(chr(int(cell[position + 2:position + 4], 16)))
                position += 4
                continue
        pieces.append(cell[position])
        position += 1
    return "".join(pieces)


def impact_rows(graph):
    if not graph:
        return []
    lines = graph.splitlines()
    if not lines or lines[0] != IMPACT_HEADER:
        raise ContextError("impact.tsv has an unsupported header")
    rows = []
    for number, line in enumerate(lines[1:], 2):
        cells = line.split("\t")
        if len(cells) != 6:
            raise ContextError("impact.tsv has an invalid row at line " + str(number))
        row = tuple(unescape_cell(cell) for cell in cells)
        if row[0] != "schema":
            rows.append(row)
    return rows


def related_paths(seeds, rows):
    related = set(seeds)
    for kind, source, target, relation, evidence, confidence in rows:
        if kind in {"impact", "test", "dependency"} and path_cell(source) and path_cell(target):
            if source in seeds:
                related.add(target)
            if target in seeds:
                related.add(source)
    return related


def selected_rows(rows, seeds, related):
    chosen = []
    for row in rows:
        kind, source, target, relation, evidence, confidence = row
        if kind in {"change", "symbol", "surface", "limit"}:
            take = source in related or (kind == "limit" and source == "scan")
        elif kind in {"impact", "test", "dependency"}:
            take = (source in seeds and target in related) or (target in seeds and source in related)
        else:
            take = False
        if take:
            chosen.append(row)
    confidence_rank = {"high": 0, "medium": 1, "low": 2}
    kind_rank = {"change": 0, "impact": 1, "test": 2, "dependency": 3,
                 "symbol": 4, "surface": 5, "limit": 6}
    return sorted(set(chosen), key=lambda row: (confidence_rank.get(row[5], 3),
                                                 kind_rank.get(row[0], 7), row))


def short_entry(body):
    lines = body.splitlines()
    keep = [lines[0]]
    for line in lines[1:]:
        if line.startswith(("- hunks:", "- symbols:", "- tests:", "- note:")):
            keep.append(line)
    return "\n".join(keep)


def markdown_cell(value):
    return value.replace("|", "\\|").replace("\n", " ").replace("\r", " ").replace("`", "\\`")


def fence_for(content):
    longest = max((len(match.group()) for match in re.finditer(r"`+", content)), default=0)
    return "`" * max(3, longest + 1)


def expanded_file(root, raw_path, byte_cap):
    source = safe_path(root, Path(raw_path), regular=True)
    if source.stat().st_size > MAX_EXPAND_BYTES:
        raise ContextError("expanded file exceeds the 512 KiB safety limit: " + str(raw_path))
    blob = source.read_bytes()
    if b"\0" in blob:
        raise ContextError("expanded file is binary: " + str(raw_path))
    relative = source.relative_to(root).as_posix()
    excerpt = blob[:byte_cap].decode("utf-8", "replace")
    omitted = max(0, len(blob) - byte_cap)
    return relative, excerpt, omitted


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".context-", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def build(root, run, seat, level, output, expansions):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", seat):
        raise ContextError("seat must be a safe plan slug")
    max_index, max_impact, expand_cap = LEVELS[level]
    brief, brief_size = read_artifact(run, "brief.md")
    index, index_size = read_artifact(run, "index.md", optional=True)
    graph, graph_size = read_artifact(run, "impact.tsv", optional=True)
    baseline = brief_size + index_size + graph_size
    block = seat_block(brief, seat)
    patterns = slice_patterns(block, root)
    entries = index_entries(index)
    rows = impact_rows(graph)
    graph_paths = set()
    for kind, source, target, _, _, _ in rows:
        if kind in {"change", "symbol", "surface", "impact", "test", "dependency"} and path_cell(source):
            graph_paths.add(source)
        if kind in {"impact", "test", "dependency"} and path_cell(target):
            graph_paths.add(target)
    seeds = {path for path in set(entries) | graph_paths if matches_slice(path, patterns)}
    # A rename's former path is the same changed file for selection purposes. Importers
    # that still name it must remain visible to a seat owning the new path.
    for kind, source, target, relation, _, _ in rows:
        if kind == "change" and relation in {"R", "C"} and path_cell(source) and path_cell(target):
            if source in seeds:
                seeds.add(target)
            elif target in seeds:
                seeds.add(source)
    related = related_paths(seeds, rows)
    ranked_paths = sorted(related, key=lambda path: (path not in seeds, path))
    entry_candidates = [path for path in ranked_paths if path in entries]
    selected_entries = entry_candidates[:max_index]
    omitted_entries = entry_candidates[max_index:]
    row_candidates = selected_rows(rows, seeds, related)
    selected_impact = row_candidates[:max_impact]
    omitted_impact = row_candidates[max_impact:]

    brief_parts = sections(brief)
    shared = [body.strip() for title, body in brief_parts
              if title in {"header", "Landscape"} and body.strip()]
    hard = [body.strip() for title, body in brief_parts if title.startswith("Hard constraints")]
    if not hard:
        raise ContextError("brief.md has no Hard constraints section")
    sources = ["brief.md"] + (["index.md"] if index else []) + (["impact.tsv"] if graph else [])
    fallback = (" · impact.tsv absent (index-only fallback)" if index and not graph else
                " · no index or impact graph (brief-only fallback)" if not index and not graph else "")
    parts = ["# Context pack — " + seat,
             "Level: " + level + " · Source: " + ", ".join(sources) + fallback,
             "Scope: seat slice " + ", ".join("`" + pattern + "`" for pattern in patterns)]
    if level == "full":
        parts.append("Full depth retains index provenance when available; project files still require explicit expansion.")
    parts.extend(shared)
    parts.append("## Seat orders\n" + block.strip())
    if level == "full":
        first_entry = INDEX_ENTRY.search(index)
        provenance = index[:first_entry.start() if first_entry else len(index)].strip()
        if provenance:
            parts.append("## Change index provenance\n" + provenance)
    parts.append("## Relevant change index")
    if selected_entries:
        for path in selected_entries:
            parts.append(short_entry(entries[path]) if level == "minimal" else entries[path])
    else:
        parts.append("No indexed file matches this seat slice. This is not proof of no impact."
                     if index else "Change index unavailable; retain the brief slice and inspect code directly.")
    parts.append("## Direct impact relationships")
    if graph:
        if selected_impact:
            table = ["| Kind | Source | Target | Relation | Evidence | Confidence |",
                     "|---|---|---|---|---|---|"]
            table.extend("| " + " | ".join(markdown_cell(cell) for cell in row) + " |"
                         for row in selected_impact)
            parts.append("\n".join(table))
        else:
            parts.append("No graph row matches this seat slice. Absence is not proof of no impact.")
    else:
        parts.append("Impact graph unavailable; use the change index and inspect code directly.")

    seen_expansions = set()
    if expansions:
        parts.append("## Requested expansion")
    for request in expansions:
        relative, content, omitted = expanded_file(root, request, expand_cap)
        if relative in seen_expansions:
            continue
        seen_expansions.add(relative)
        fence = fence_for(content)
        parts.append("### " + relative + "\nRequested explicitly with --expand; "
                     + (str(omitted) + " source bytes omitted at this level.\n" if omitted else "complete file.\n")
                     + fence + "\n" + content + ("\n" if not content.endswith("\n") else "") + fence)

    selected_paths = set(selected_entries) | seen_expansions
    for row in selected_impact:
        kind, source, target, _, _, _ = row
        if path_cell(source) and source != "scan":
            selected_paths.add(source)
        if kind in {"change", "impact", "test", "dependency"} and path_cell(target):
            selected_paths.add(target)
    candidate_paths = set(entry_candidates)
    for row in row_candidates:
        kind, source, target, _, _, _ = row
        if path_cell(source) and source != "scan":
            candidate_paths.add(source)
        if kind in {"change", "impact", "test", "dependency"} and path_cell(target):
            candidate_paths.add(target)
    omitted_paths = sorted(candidate_paths - selected_paths)
    parts.append("## Selection limits\n"
                 + "Index entries included: " + str(len(selected_entries)) + "; omitted: " + str(len(omitted_entries))
                 + ". Impact rows included: " + str(len(selected_impact)) + "; omitted: " + str(len(omitted_impact))
                 + ". Source files are not opened unless explicitly requested with --expand.")
    if omitted_paths:
        parts.append("Omitted relevant paths: " + ", ".join("`" + path + "`" for path in omitted_paths))
    parts.extend(hard)  # The non-negotiable brief constraints stay at the bottom edge.
    output_text = "\n\n".join(parts).rstrip() + "\n"
    included = len(output_text.encode("utf-8"))
    # Baseline is the exact bytes of the unfiltered brief + index + optional graph.
    # Included is the UTF-8 pack byte count. A requested expansion may make reduction negative.
    reduction = 100 * (baseline - included) / baseline if baseline else 0.0
    metrics = ["metric\tvalue", "baseline_bytes\t" + str(baseline),
               "included_bytes\t" + str(included), "reduction_percent\t" + f"{reduction:.2f}",
               "selected_paths\t" + str(len(selected_paths)), "omitted_paths\t" + str(len(omitted_paths)),
               "index_entries_included\t" + str(len(selected_entries)),
               "index_entries_omitted\t" + str(len(omitted_entries)),
               "impact_rows_included\t" + str(len(selected_impact)),
               "impact_rows_omitted\t" + str(len(omitted_impact))]
    metrics.extend("selected_path\t" + path.replace("\t", "\\t").replace("\n", "\\n")
                   for path in sorted(selected_paths))
    metrics.extend("omitted_path\t" + path.replace("\t", "\\t").replace("\n", "\\n")
                   for path in omitted_paths)
    metrics_text = "\n".join(metrics) + "\n"
    sidecar = safe_path(run, Path(str(output) + ".metrics.tsv"), must_exist=False)
    if output in {run / "brief.md", run / "index.md", run / "impact.tsv"} or sidecar in {
            run / "brief.md", run / "index.md", run / "impact.tsv"}:
        raise ContextError("output would overwrite a source run file")
    if any(output == safe_path(root, Path(request), regular=True) for request in expansions):
        raise ContextError("output would overwrite a requested source file")
    atomic_write(output, output_text)
    atomic_write(sidecar, metrics_text)
    print(str(output))
    print(str(sidecar))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path, help="repository code root")
    parser.add_argument("--run", required=True, type=Path, help="run directory under the code root")
    parser.add_argument("--seat", required=True, help="seat slug from brief.md")
    parser.add_argument("--level", choices=tuple(LEVELS), required=True)
    parser.add_argument("--output", required=True, type=Path, help="Markdown output inside the run's contexts directory")
    parser.add_argument("--expand", action="append", default=[], metavar="PATH",
                        help="explicit regular source file under the code root (repeatable)")
    args = parser.parse_args()
    try:
        given = Path(os.path.abspath(str(args.root)))
        root = args.root.resolve(strict=True)
        if not root.is_dir():
            raise ContextError("root is not a directory")
        run = safe_path(root, rebase(args.run, given, root), regular=False)
        if not run.is_dir():
            raise ContextError("run is not a directory")
        contexts = safe_path(run, Path("contexts"), must_exist=False)
        output = safe_path(contexts, rebase(args.output, given, root), must_exist=False)
        expansions = [str(rebase(Path(request), given, root)) if Path(request).is_absolute() else request
                      for request in args.expand]
        build(root, run, args.seat, args.level, output, expansions)
    except (ContextError, OSError) as error:
        print("context: " + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

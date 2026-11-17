#!/usr/bin/env bash
# PreToolUse hook (Bash and PowerShell: both hand it tool_input.command) — the Small Council's pipe stop and push freeze.
#
# A pipe hides the helper's exit status, and head, tail or grep cut off its refusals ("never pipe it" lived in prose and
# was broken 133 times). So a command whose own unquoted text runs the plugin's helper (a bare `council`, an absolute or
# $VAR-rooted path ending in bin/council, `bash` with one, or a variable set to one — not a project's ./council or
# bin/council) and pipes its output into head, tail or grep (`|`, `2>&1 |`, `|&`, through other commands, or a loop or
# group piped whole) is refused: exit 2, one line on stderr, which Claude Code hands to Claude.
# The push freeze (issue 49): `git push` or `gh pr create` in the command's own unquoted text (alone, compound, grouped,
# looped or substituted, after git -C <dir>, or quoted whole after bash -c, sh -c or eval), without --dry-run, is put to
# `council pushes check` from the call's folder (and git -C's), which refuses (exit 2, its reason on stderr) while
# `- pushes: off`, or `off until` a later date, holds. A stage with COUNCIL_ALLOW_PUSH=1 (its prefix, or exported earlier
# in the command) never is. An alias, or a push spelled through a variable, can't be seen: the freeze guards accidents.
# Everything else passes, silently: a redirect, `| tee`, grep or head over other commands, council or git push in quoted
# text, a comment, a heredoc or a case pattern, a command over 100 KB (macOS awk re-measures the string at each
# character), anything it can't parse, and any fault of the helper's. Nothing goes to stdout. Before a call that names
# council it touches this session's mark (session-mark.sh). Fast: shell patterns over the command (not its cwd) let
# through each one that can't match; the rest get one awk pass that walks it as the shell would. Only a push or a PR
# starts the helper (Python). bash 3.2 (macOS), Git Bash, Linux — no jq.

input="$(tr -d '\000' 2>/dev/null)" || exit 0   # NUL bytes, which JSON can't hold: bash 4.4+ would warn about them
c="${input:0:1000}"; c="${c%%\"command\"*}"; c="${input:${#c}}"   # tool_input.command on: the cwd can say push
walk=""; case "$c" in *push*) walk=1 ;; *create*) walk=1 ;; esac   # one pattern each: more stars can backtrack
case "$input" in *council*) sid="${input:0:1000}" ;; *) [ -n "$walk" ] || exit 0; sid="" ;; esac
# The session's mark, from the id near the start of the input (a pattern over all of it could take seconds).
case "$sid" in *'"session_id"'*) sid="${sid#*\"session_id\"}" ;; *) sid="" ;; esac
case "$sid" in :\"*) sid="${sid#:\"}" ;; ': "'*) sid="${sid#: \"}" ;; *) sid="" ;; esac
sid="${sid%%\"*}"
. "${BASH_SOURCE[0]%[/\\\\]*}/session-mark.sh" 2>/dev/null && mark_session "$sid" bash-gate

[ "${#input}" -le 100000 ] || exit 0
case "$c" in *'|'*) ;; *) [ -n "$walk" ] || exit 0 ;; esac

verdict="$(printf '%s' "$input" | LC_ALL=C awk '
  # --- the JSON: tool_input.command, its escapes undone ------------------------------------------
  # Escapes undone with gsub, one pass each: a loop over them copies the rest of a long command every time.
  # \\ and \" were set aside as \001 and \002, so every backslash left starts an escape.
  function unjson(v,   out, i, x) {
    gsub(/\\n/, "\n", v); gsub(/\\t/, "\t", v); gsub(/\\[rbf]/, " ", v); gsub(/\\\//, "/", v); out = ""
    while ((i = index(v, "\\u")) > 0) {        # \u0041 and the like: rare, so a loop is fine
      x = hexval(substr(v, i + 2, 4)); out = out substr(v, 1, i - 1) ((x > 0 && x < 128) ? sprintf("%c", x) : "_"); v = substr(v, i + 6)
    }
    v = out v; gsub("\002", "\"", v); gsub("\001", "\\", v)
    return v
  }
  function hexval(h,   i, d, v) {
    v = 0; h = tolower(h)
    for (i = 1; i <= 4; i++) { d = index("0123456789abcdef", substr(h, i, 1)); if (!d) return -1; v = v * 16 + d - 1 }
    return v
  }
  # --- what the commands do: stages, pipes, groups ------------------------------------------------
  # pos: 0 = before the command word · 1 = its arguments · 2 = bash/sh before its script · 3 = timeout before its
  # duration · 4 = export and the like · 5 = git before its subcommand · 6 = gh before pr · 7 = gh pr before create ·
  # 8 = the string after bash -c. opt: a git or gh option waits for its value (2: the dir of git -C, joined into cdir). pal: this
  # stage carries COUNCIL_ALLOW_PUSH=1; gal: the command exported it. pend: the push or PR of this stage ("dry" after
  # --dry-run); pk and pdir: the first one a stage ended with, and its git -C. stc: this stage runs the helper. taint:
  # an earlier stage of this pipeline runs it. sout: its stdout goes to a file. rp: a redirect waits for its target.
  # Frames: ( { if loop case, and $ for a substitution, which keeps the outer stage apart. cpat, for a case frame: 0 = its
  # word, before "in" · 1 = a pattern, before its ")" · 2 = a branch, its commands. In 0 and 1, words and | are pattern text.
  function reset() { pos = 0; stc = 0; rp = 0; sout = 0; pre = ""; opt = 0; pal = 0; pend = ""; cdir = "" }
  function endstage() { if (stc && !sout && fd > 0) fcn[fd] = 1; if (pk == "" && pend != "" && pend != "dry") { pk = pend; pdir = cdir } }
  function sep() { endstage(); taint = 0; reset() }
  function pipe(both) { endstage(); taint = taint || (stc && (both || !sout)); reset() }
  function push(k) {
    fd++; fk[fd] = k; fcn[fd] = 0
    sp[fd] = pos; ss[fd] = stc; st[fd] = taint; sr[fd] = rp; so[fd] = sout; spr[fd] = pre; sop[fd] = opt; spa[fd] = pal; spe[fd] = pend; scd[fd] = cdir
    reset(); if (k == "$") taint = 0            # a pipe into a group reaches its first command
    if (k == "case") cpat[fd] = 0
  }
  function inpat() { return fd > 0 && fk[fd] == "case" && cpat[fd] < 2 }
  function pop(k,   c) {
    if (fd < 1 || fk[fd] != k) { bad = 1; return }
    endstage(); c = fcn[fd]
    if (k == "$") { pos = sp[fd]; stc = ss[fd]; taint = st[fd]; rp = sr[fd]; sout = so[fd]; pre = spr[fd]; opt = sop[fd]; pal = spa[fd]; pend = spe[fd]; cdir = scd[fd]; fd--; return }
    taint = st[fd]; fd--; reset(); pos = 1; stc = c   # the group is one stage of the pipeline around it
  }
  function base(x) { sub(/.*[\/\\]/, "", x); return x }
  function iscouncil(x) {                       # the helper of the plugin: a bare council, or an absolute or $-rooted bin/council
    if (x ~ /^\$\{?[A-Za-z_][A-Za-z0-9_]*\}?$/) { gsub(/[${}]/, "", x); return (x in cvar) }
    return x == "council" || x ~ /^([\/~$]|[A-Za-z]:).*[\/\\]bin[\/\\]council$/
  }
  function assign(x,   nm, v) {
    nm = x; sub(/\+?=.*$/, "", nm); v = x; sub(/^[^=]*=/, "", v)
    sub(/^[ \t]*(bash|sh)[ \t]+/, "", v); sub(/[ \t].*$/, "", v)
    if (iscouncil(v)) cvar[nm] = 1; else if (nm in cvar) delete cvar[nm]
  }
  function inner(x) {                            # a whole command quoted after bash -c, sh -c or eval
    if (pend != "" || pal || gal || x ~ /COUNCIL_ALLOW_PUSH=1|--dry-run/) return
    if (x ~ /(^|[;&|({ \t\n])git[ \t]+(-C[ \t]+[^ \t;&|]+[ \t]+)*push([ \t;&|)]|$)/) pend = "git push"
    else if (x ~ /(^|[;&|({ \t\n])gh[ \t]+pr[ \t]+create([ \t;&|)]|$)/) pend = "gh pr create"
  }
  function onword(x,   b) {
    if (inpat()) { if (cpat[fd] == 0) { if (x == "in") cpat[fd] = 1 } else if (x == "esac") pop("case"); return }
    if (rp) { rp = 0; return }
    if (pos == 0) {
      if (x ~ /^[A-Za-z_][A-Za-z0-9_]*\+?=/) { if (x == "COUNCIL_ALLOW_PUSH=1") pal = 1; assign(x); return }
      if (x ~ /^-/) { if (pre == "command" && (x == "-v" || x == "-V")) pos = 1; return }
      if (pre == "eval" && x ~ /[ \t\n;&|]/) { inner(x); pos = 1; return }
      if (x == "!" || x == "time" || x == "then" || x == "else" || x == "elif" || x == "do" || x == "env" || x == "eval" \
          || x == "command" || x == "builtin" || x == "exec" || x == "nohup" || x == "nice") { pre = x; return }
      if (x == "timeout" || x == "gtimeout") { pos = 3; return }
      if (x == "{" || x == "if" || x == "case") { push(x); return }
      if (x == "for" || x == "while" || x == "until" || x == "select") { push("loop"); if (x == "for" || x == "select") pos = 1; return }   # its name is no command
      if (x == "}") { pop("{"); return }
      if (x == "fi") { pop("if"); return }
      if (x == "done") { pop("loop"); return }
      if (x == "esac") { pop("case"); return }
      b = base(x)
      if (taint && (b == "head" || b == "tail" || b == "grep" || b == "egrep" || b == "fgrep")) hit = 1
      if (iscouncil(x)) stc = 1
      pos = (b == "git") ? 5 : (b == "gh") ? 6 : 1
      if (b == "bash" || b == "sh") pos = 2
      if (b == "export" || b == "declare" || b == "typeset" || b == "local" || b == "readonly") pos = 4
      return
    }
    if (pos == 8) { inner(x); pos = 1; return }
    if (pos >= 5) {                                   # git -C dir push · gh -R o/r pr create
      if (opt == 2) cdir = (cdir == "" || x ~ /^([\/~]|[A-Za-z]:)/) ? x : cdir "/" x
      if (opt || x ~ /^-/) { opt = opt ? 0 : (pos == 5 && x == "-C") ? 2 : x ~ /^(-c|-R|--git-dir|--work-tree|--namespace|--repo)$/; return }
      if (pend == "" && !pal && !gal && (pos == 5 && x == "push" || pos == 7 && x == "create")) pend = (pos == 5) ? "git push" : "gh pr create"
      pos = (pos == 6 && x == "pr") ? 7 : 1; return
    }
    if (pos == 1 && pend != "dry" && pend != "" && (x == "--dry-run" || x == "-n" && pend == "git push")) pend = "dry"
    if (pos == 2) {
      if (x ~ /^-/) { if (x ~ /^-[a-z]*c[a-z]*$/) pos = 8; else if (x == "-n") pos = 1; return }   # a command string, or a syntax check
      if (iscouncil(x)) stc = 1
      pos = 1; return
    }
    if (pos == 3) { if (x !~ /^-/) pos = 0; return }
    if (pos == 4 && x ~ /^[A-Za-z_][A-Za-z0-9_]*=/) { if (x == "COUNCIL_ALLOW_PUSH=1") gal = 1; assign(x) }
  }
  # --- the characters: words, quotes, operators ---------------------------------------------------
  function endword() { if (inw) onword(w); w = ""; inw = 0 }
  function opensub(k) { cd++; ck[cd] = k; cp[cd] = 0; cw[cd] = w; ci[cd] = inw; w = ""; inw = 0; push("$") }
  function closesub() { endword(); pop("$"); w = cw[cd]; inw = 1; cd-- }
  function skipto(s, i, q, esc,   L) {          # the index of the closing q (0: none); esc: \ escapes
    L = length(s); while (i <= L && substr(s, i, 1) != q) { if (esc && substr(s, i, 1) == "\\") i++; i++ }
    return (i <= L) ? i : 0
  }
  function closer(s, i, o, e,   L, n, c) {     # the index just past the e that balances the o already open
    L = length(s); n = 1
    for (; i <= L; i++) { c = substr(s, i, 1); if (c == "\\") { i++; continue } if (c == o) n++; else if (c == e && !--n) return i + 1 }
    return 0
  }
  function redir(fdn, isout, target) { if (isout && (fdn == "" || fdn == "1")) sout = 1; if (target) rp = 1 }
  function heredocs(s, i,   rest, n, ln, h, j, line) {
    rest = substr(s, i); n = split(rest, ln, "\n"); j = 1
    for (h = 1; h <= nhd; h++) {
      for (; j <= n; j++) {
        line = ln[j]; i += length(line) + 1
        if (hdash[h]) sub(/^\t+/, "", line)
        if (line == hd[h]) { j++; break }
      }
    }
    nhd = 0; return i
  }
  function scan(s,   L, i, c, c2, j, k, fdn, dl, dash) {
    L = length(s); i = 1; cd = 1; ck[1] = "T"; cp[1] = 0; w = ""; inw = 0; nhd = 0; fd = 0; taint = 0; reset()
    while (i <= L && !bad) {
      c = substr(s, i, 1); k = ck[cd]
      if (k == "D") {                                              # inside "…": only $( ), ` ` and \ matter
        if (c == "\"") { cd--; i++; continue }
        if (c == "\\") { c2 = substr(s, i + 1, 1); w = w (index("$`\"\\\n", c2) ? c2 : c c2); i += 2; continue }
        if (c == "$" && substr(s, i + 1, 2) == "((") { j = closer(s, i + 3, "(", ")"); if (!j) { bad = 1; break } w = w "0"; i = j + 1; continue }
        if (c == "$" && substr(s, i + 1, 1) == "(") { opensub("C"); i += 2; continue }
        if (c == "$" && substr(s, i + 1, 1) == "{") { j = closer(s, i + 2, "{", "}"); if (!j) { bad = 1; break } w = w substr(s, i, j - i); i = j; continue }
        if (c == "`") { opensub("B"); i++; continue }
        j = i + 1; while (j <= L && !index("\"\\$`", substr(s, j, 1))) j++
        w = w substr(s, i, j - i); i = j; continue
      }
      if (c == "\\") { if (substr(s, i + 1, 1) != "\n") { w = w substr(s, i + 1, 1); inw = 1 } i += 2; continue }
      if (c == "\047") { j = skipto(s, i + 1, "\047", 0); if (!j) { bad = 1; break } w = w substr(s, i + 1, j - i - 1); inw = 1; i = j + 1; continue }
      if (c == "\"") { cd++; ck[cd] = "D"; inw = 1; i++; continue }
      if (c == "`") { if (k == "B") closesub(); else { inw = 1; opensub("B") } i++; continue }
      if (c == "$") {
        c2 = substr(s, i + 1, 1); inw = 1
        if (c2 == "\047") { j = skipto(s, i + 2, "\047", 1); if (!j) { bad = 1; break } w = w "_"; i = j + 1; continue }
        if (c2 == "(" && substr(s, i + 2, 1) == "(") { j = closer(s, i + 3, "(", ")"); if (!j) { bad = 1; break } w = w "0"; i = j + 1; continue }
        if (c2 == "(") { opensub("C"); i += 2; continue }
        if (c2 == "{") { j = closer(s, i + 2, "{", "}"); if (!j) { bad = 1; break } w = w substr(s, i, j - i); i = j; continue }
        w = w c; i++; continue
      }
      if (c == "#" && !inw) { while (i <= L && substr(s, i, 1) != "\n") i++; continue }
      if (c == " " || c == "\t" || c == "\r") { endword(); i++; continue }
      if (c == "\n") { endword(); sep(); i++; if (nhd) i = heredocs(s, i); continue }
      if (c == ";") {
        endword(); sep(); i++; c2 = substr(s, i, 1)
        if (c2 == ";" || c2 == "&") { i++; if (fd > 0 && fk[fd] == "case") cpat[fd] = 1 }   # ;; ;& — the next pattern
        continue
      }
      if (c == "|") {
        endword(); if (inpat()) { i++; continue }                         # a|b) — one pattern or another
        c2 = substr(s, i + 1, 1)
        if (c2 == "|") { sep(); i += 2 } else if (c2 == "&") { pipe(1); i += 2 } else { pipe(0); i++ }
        continue
      }
      if (c == "&") {
        endword(); c2 = substr(s, i + 1, 1)
        if (c2 == "&") { sep(); i += 2; continue }
        if (c2 == ">") { i += 2; if (substr(s, i, 1) == ">") i++; redir("", 1, 1); continue }
        sep(); i++; continue
      }
      if (c == "<" || c == ">") {
        fdn = ""
        if (inw && w ~ /^[0-9]+$/) { fdn = w; w = ""; inw = 0 } else endword()
        c2 = substr(s, i + 1, 1)
        if (c2 == "(") { inw = 1; opensub("C"); i += 2; continue }          # <( ) and >( ): commands
        if (c == "<" && c2 == "<" && substr(s, i + 2, 1) == "<") { i += 3; redir(fdn, 0, 1); continue }
        if (c == "<" && c2 == "<") {                                       # a heredoc: its body is no command
          i += 2; dash = 0; dl = ""
          if (substr(s, i, 1) == "-") { dash = 1; i++ }
          while (substr(s, i, 1) == " " || substr(s, i, 1) == "\t") i++
          while (i <= L) {
            c2 = substr(s, i, 1)
            if (index(" \t\n;&|<>()", c2)) break
            if (c2 == "\047" || c2 == "\"") { j = skipto(s, i + 1, c2, c2 == "\""); if (!j) { bad = 1; break } dl = dl substr(s, i + 1, j - i - 1); i = j + 1; continue }
            if (c2 == "\\") { dl = dl substr(s, i + 1, 1); i += 2; continue }
            dl = dl c2; i++
          }
          if (dl == "") bad = 1
          nhd++; hd[nhd] = dl; hdash[nhd] = dash; continue
        }
        if (c2 == "&") {                                                   # >&2, 2>&1, <&0, >&-: no target
          i += 2; j = i
          while (substr(s, i, 1) ~ /[0-9]/) i++
          if (i == j && substr(s, i, 1) == "-") i++
          if (i > j) { redir(fdn, c == ">" && substr(s, j, i - j) != "1", 0); continue }
          redir(fdn, c == ">", 1); continue                                 # >& file
        }
        if (c2 == ">" || c2 == "|" || (c == "<" && c2 == ">")) i++
        redir(fdn, c == ">", 1); i++; continue
      }
      if (c == "(") { endword(); if (!inpat()) { cp[cd]++; push("(") } i++; continue }   # (a|b): pattern text
      if (c == ")") {
        endword()
        if (inpat()) { sep(); cpat[fd] = 2 }                               # a case pattern ends
        else if (cp[cd] > 0) { cp[cd]--; pop("(") }
        else if (k == "C") closesub()
        else bad = 1
        i++; continue
      }
      w = w c; inw = 1; i++
    }
    if (!bad) { endword(); endstage() }
    if (cd != 1 || fd != 0 || rp) bad = 1
  }
  { s = s $0 "\n" }
  END {
    gsub(/\\\\/, "\001", s); gsub(/\\"/, "\002", s)
    n = split(s, p, /"/)
    for (i = 1; i + 3 <= n; i += 2) {
      t = p[i]; depth += gsub(/[[{]/, "", t) - gsub(/[\]}]/, "", t)   # how deep the next key is
      k = p[i + 1]
      if (depth == 1 && p[i + 2] ~ /^[ \t\r\n]*:/) top = k
      if (depth == 1 && k == "cwd" && p[i + 2] ~ /^[ \t\r\n]*:[ \t\r\n]*$/) cwd = unjson(p[i + 3])   # before tool_input
      if (depth == 2 && top == "tool_input" && k == "command" && p[i + 2] ~ /^[ \t\r\n]*:[ \t\r\n]*$/) { cmd = unjson(p[i + 3]); found = 1; break }
    }
    if (!found) exit
    scan(cmd)
    if (!bad) { gsub(/[\t\n]/, " ", cwd); print (hit ? "refuse" : "-") "\t" (pk == "" ? "-" : pk) "\t" (pdir == "" ? "." : pdir) "\t" cwd }
  }' 2>/dev/null)"
IFS=$'\t' read -r verdict pushed pdir cwd <<<"$verdict"
if [ "$verdict" = refuse ]; then
  printf '%s\n' "Small Council: run council plain — a pipe into head, tail or grep hides its exit status and its refusals. To shorten its output, redirect it to a file (council … > out.txt) and read that." >&2
  exit 2
fi
case "$pushed" in 'git push'|'gh pr create') ;; *) exit 0 ;; esac
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)" || exit 0
case "$cwd$pdir" in *\\*) cwd="$(printf '%s' "$cwd" | tr '\\' '/')"; pdir="$(printf '%s' "$pdir" | tr '\\' '/')" ;; esac   # C:\Users\…
out="$(cd "$cwd" 2>/dev/null || true; cd "$pdir" 2>/dev/null || true; "${BASH:-bash}" "$ROOT/bin/council" pushes check "$pushed" 2>/dev/null)"
[ $? -eq 2 ] && case "$out" in "Small Council:"*) printf '%s\n' "$out" >&2; exit 2 ;; esac
exit 0

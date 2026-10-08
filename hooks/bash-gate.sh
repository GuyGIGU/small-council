#!/usr/bin/env bash
# PreToolUse hook (Bash) — the Small Council's pipe stop.
#
# A pipe hides the helper's exit status, and head, tail or grep cut off its refusals and reminders. The
# rule "never pipe it" lived in prose and was broken 133 times across three sessions, again after every
# warning. So a Bash command whose own unquoted text runs the helper — `council <cmd>`, a path ending in
# /council, `bash …/bin/council <cmd>`, or a variable the same command set to one of those — and pipes
# that output into head, tail or grep (`|`, `2>&1 |`, `|&`, through other commands, or a loop or group
# piped whole) is refused: exit 2, one line on stderr, which Claude Code hands to Claude.
#
# Everything else passes, silently: a redirect to a file, `| tee`, grep or head over files or over other
# commands, the word council in a quoted string, a comment or a heredoc (commit messages, echo), and
# anything it can't parse. Nothing goes to stdout. It never reads a council home, so it costs the same
# in every project.
#
# Fast, as it runs before every Bash call: one cat, then shell patterns let through every command that
# can't match (no "council", or no pipe); only the rest reach one awk pass, linear in the command's size,
# which reads tool_input.command from the JSON and walks it once as the shell would: quotes, escapes,
# $( ), backticks, heredocs, comments, redirects, groups and loops.
#
# Portability: bash 3.2 (macOS), Git Bash on Windows, Linux — no jq, no Python.

input="$(cat 2>/dev/null)" || exit 0
case "$input" in *council*) ;; *) exit 0 ;; esac   # one pattern each: several stars in one can backtrack
case "$input" in *'|'*) ;; *) exit 0 ;; esac

verdict="$(printf '%s' "$input" | LC_ALL=C awk '
  # --- the JSON: tool_input.command, its escapes undone ------------------------------------------
  # Escapes undone with gsub, one pass each: a loop over them copies the rest of a long command every time.
  # \\ and \" were set aside as \001 and \002, so every backslash left starts an escape.
  function unjson(v,   out, i, x) {
    gsub(/\\n/, "\n", v); gsub(/\\t/, "\t", v); gsub(/\\[rbf]/, " ", v); gsub(/\\\//, "/", v)
    out = ""
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
  # pos: 0 = before the command word · 1 = its arguments · 2 = bash/sh before its script · 3 = timeout
  # before its duration · 4 = export and friends (assignments). stc: this stage runs the helper. sout:
  # its stdout goes to a file. taint: an earlier stage of this pipeline runs it. rp: a redirect waits for
  # its target. Frames: ( { if loop case, and $ for a substitution, which keeps the outer stage apart.
  function reset() { pos = 0; stc = 0; rp = 0; sout = 0; pre = "" }
  function endstage() { if (stc && !sout && fd > 0) fcn[fd] = 1 }
  function sep() { endstage(); taint = 0; reset() }
  function pipe(both) { endstage(); taint = taint || (stc && (both || !sout)); reset() }
  function push(k) {
    fd++; fk[fd] = k; fcn[fd] = 0
    sp[fd] = pos; ss[fd] = stc; st[fd] = taint; sr[fd] = rp; so[fd] = sout; spr[fd] = pre
    reset(); if (k == "$") taint = 0            # a pipe into a group reaches its first command
  }
  function pop(k,   c) {
    if (fd < 1 || fk[fd] != k) { bad = 1; return }
    endstage(); c = fcn[fd]
    if (k == "$") { pos = sp[fd]; stc = ss[fd]; taint = st[fd]; rp = sr[fd]; sout = so[fd]; pre = spr[fd]; fd--; return }
    taint = st[fd]; fd--; reset(); pos = 1; stc = c   # the group is one stage of the pipeline around it
  }
  function base(x) { sub(/.*[\/\\]/, "", x); return x }
  function iscouncil(x) {
    if (x ~ /^\$\{?[A-Za-z_][A-Za-z0-9_]*\}?$/) { gsub(/[${}]/, "", x); return (x in cvar) }
    return base(x) == "council"
  }
  function assign(x,   nm, v) {
    nm = x; sub(/\+?=.*$/, "", nm); v = x; sub(/^[^=]*=/, "", v)
    sub(/^[ \t]*(bash|sh)[ \t]+/, "", v); sub(/[ \t].*$/, "", v)
    if (base(v) == "council") cvar[nm] = 1; else if (nm in cvar) delete cvar[nm]
  }
  function onword(x,   b) {
    if (rp) { rp = 0; return }
    if (pos == 0) {
      if (x ~ /^[A-Za-z_][A-Za-z0-9_]*\+?=/) { assign(x); return }
      if (x ~ /^-/) { if (pre == "command" && (x == "-v" || x == "-V")) pos = 1; return }
      if (x == "!" || x == "time" || x == "then" || x == "else" || x == "elif" || x == "do" || x == "env" \
          || x == "command" || x == "builtin" || x == "exec" || x == "nohup" || x == "nice") { pre = x; return }
      if (x == "timeout" || x == "gtimeout") { pos = 3; return }
      if (x == "{" || x == "if" || x == "case") { push(x); return }
      if (x == "for" || x == "while" || x == "until" || x == "select") { push("loop"); return }
      if (x == "}") { pop("{"); return }
      if (x == "fi") { pop("if"); return }
      if (x == "done") { pop("loop"); return }
      if (x == "esac") { pop("case"); return }
      b = base(x)
      if (taint && (b == "head" || b == "tail" || b == "grep" || b == "egrep" || b == "fgrep")) hit = 1
      if (iscouncil(x)) stc = 1
      pos = 1
      if (b == "bash" || b == "sh") pos = 2
      if (b == "export" || b == "declare" || b == "typeset" || b == "local" || b == "readonly") pos = 4
      return
    }
    if (pos == 2) {
      if (x ~ /^-/) { if (x == "-c" || x == "-n") pos = 1; return }   # a command string, or a syntax check
      if (iscouncil(x)) stc = 1
      pos = 1; return
    }
    if (pos == 3) { if (x !~ /^-/) pos = 0; return }
    if (pos == 4 && x ~ /^[A-Za-z_][A-Za-z0-9_]*=/) assign(x)
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
      if (c == ";") { endword(); sep(); i++; c2 = substr(s, i, 1); if (c2 == ";" || c2 == "&") i++; continue }
      if (c == "|") {
        endword(); c2 = substr(s, i + 1, 1)
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
      if (c == "(") { endword(); cp[cd]++; push("("); i++; continue }
      if (c == ")") {
        endword()
        if (fd > 0 && fk[fd] == "case") sep()                              # a case pattern ends
        else if (cp[cd] > 0) { cp[cd]--; pop("(") }
        else if (k == "C") closesub()
        else bad = 1
        i++; continue
      }
      w = w c; inw = 1; i++
    }
    if (!bad) endword()
    if (cd != 1 || fd != 0 || rp) bad = 1
  }

  { s = s $0 "\n" }
  END {
    gsub(/\\\\/, "\001", s); gsub(/\\"/, "\002", s)
    n = split(s, p, /"/)
    for (i = 1; i + 3 <= n; i += 2) {
      t = p[i]
      for (c = 1; c <= length(t); c++) {
        ch = substr(t, c, 1)
        if (ch == "{" || ch == "[") depth++
        else if (ch == "}" || ch == "]") depth--
      }
      k = p[i + 1]
      if (depth == 1 && p[i + 2] ~ /^[ \t\r\n]*:/) top = k
      if (depth == 2 && top == "tool_input" && k == "command" && p[i + 2] ~ /^[ \t\r\n]*:[ \t\r\n]*$/) { cmd = unjson(p[i + 3]); found = 1; break }
    }
    if (!found) exit
    scan(cmd)
    if (hit && !bad) print "refuse"
  }' 2>/dev/null)"

if [ "$verdict" = refuse ]; then
  printf '%s\n' "Small Council: run council plain — a pipe into head, tail or grep hides its exit status and its refusals. To shorten its output, redirect it to a file (council … > out.txt) and read that." >&2
  exit 2
fi
exit 0

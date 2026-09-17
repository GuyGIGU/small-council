#!/usr/bin/env bash
# Small Council — SubagentStop hook for council-worker and council-verifier.
#
# A council agent may not finish without the file its contract requires. When that file is missing or
# malformed, the hook blocks the stop once: exit 2, and the reason on stderr goes back to the agent so
# it can fix the file. The next stop always passes (stop_hook_active), so it can never loop. Anything
# it can't read, it lets through — this hook must never trap an agent on a guess.

set -u

input="$(cat 2>/dev/null || true)"

# The string value of a top-level JSON field (first occurrence), unescaped enough for these checks.
json_str() {
  printf '%s' "$input" | K="$1" awk '
    BEGIN { RS = "\001" }
    {
      pat = "\"" ENVIRON["K"] "\"[ \t\r\n]*:[ \t\r\n]*\""
      if (!match($0, pat)) exit
      i = RSTART + RLENGTH; out = ""; L = length($0)
      while (i <= L) {
        c = substr($0, i, 1)
        if (c == "\\") {
          e = substr($0, i + 1, 1)
          if (e == "n") out = out "\n"; else if (e == "t") out = out "\t"; else if (e == "r") out = out ""
          else if (e == "u") { out = out "?"; i += 4 } else out = out e
          i += 2; continue
        }
        if (c == "\"") break
        out = out c; i++
      }
      printf "%s", out
    }'
}

block() {
  printf 'Small Council seat check: %s\n' "$1" >&2
  exit 2
}

# Any spacing JSON allows ("stop_hook_active" : true, a line break) — whitespace inside the reply's own
# text can't fake it, because a quote in a JSON string is escaped (\").
case "$(printf '%s' "$input" | tr -d ' \t\r\n')" in *'"stop_hook_active":true'*) exit 0 ;; esac

case "$(json_str agent_type)" in
  *council-worker) kind=worker ;;
  *council-verifier) kind=verifier ;;
  *) exit 0 ;;
esac

msg="$(json_str last_assistant_message)"
[ -n "$msg" ] || exit 0
# BLOCKED at a line's start, after spaces, a quote mark or markdown (**BLOCKED:**): in capitals on any line,
# or "Blocked:" in any case as the reply's first line — so a finding like "* Blocked users can …" is no reply.
if printf '%s\n' "$msg" | grep -q -E '^[[:space:]>*_]*BLOCKED([^[:alpha:]]|$)'; then exit 0; fi
if printf '%s\n' "$msg" | awk 'NF { print; exit }' | grep -q -i -E '^[[:space:]>*_]*blocked[*_]*[[:space:]]*:'; then exit 0; fi

if [ "$kind" = worker ]; then
  finish="finish by writing your output file, then reply with exactly one line: Wrote <output path> — <N> items (<counts>). If you couldn't do the work, reply BLOCKED: <reason> instead."
else
  finish="finish by writing your verdicts to the file your dispatch named (<run>/verify-<n>.md), then reply with exactly one line: Wrote <path> — <count of each verdict>. If you couldn't do the check, reply BLOCKED: <reason> instead."
fi

# The line that names the file: "Wrote <path>" anywhere, or at a line's start "Wrote:", "**Wrote**", "wrote".
line="$(printf '%s\n' "$msg" | grep -m 1 -i -E '^[[:space:]>*_]*wrote[*_:]*[[:space:]].*\.md' || true)"
[ -n "$line" ] || line="$(printf '%s\n' "$msg" | grep -m 1 'Wrote ' || true)"
[ -n "$line" ] || block "$finish"

# For each "….md" after the word (a full stop may follow; a markdown link gives its target): the whole text
# before it, then the text from each space, quote or mark on — so "my findings to /abs/x.md" yields /abs/x.md.
cands="$(printf '%s\n' "$line" | LC_ALL=C awk '
  NR == 1 {
    t = " " tolower($0)
    if (!match(t, /[^a-z]wrote[*_:]*[ \t]+/)) exit
    s = substr($0, RSTART + RLENGTH - 1)
    pathch = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_./\\-"
    marks = "[]`\"'"'"'*_(< \t"
    off = 0; rest = s
    while ((i = index(rest, ".md")) > 0) {
      end = off + i + 2
      nxt = substr(s, end + 1, 1)
      if (nxt == ".") nxt = substr(s, end + 2, 1)
      if ((nxt == "" || index(pathch, nxt) == 0) && substr(s, end + 1, 2) != "](") {
        c = substr(s, 1, end)
        while ((k = index(c, "](")) > 0) c = substr(c, k + 2)
        n = length(c)
        for (j = 1; j <= n; j++) {
          if (j > 1 && index(marks, substr(c, j - 1, 1)) == 0) continue
          d = substr(c, j)
          while (d != "" && index(marks, substr(d, 1, 1))) d = substr(d, 2)
          if (d != "" && !(d in seen)) { seen[d] = 1; print d }
        }
        print ""
      }
      rest = substr(rest, i + 3); off = end
    }
  }')"
[ -n "$cands" ] || exit 0
cwd="$(json_str cwd)"
path=""; named=""
while IFS= read -r c; do
  if [ -z "$c" ]; then                     # the end of one .md's candidates: an absolute one that isn't there
    [ -z "$named" ] || break               # is the file the agent named
    continue
  fi
  case "$c" in
    /* | [A-Za-z]:[\\/]*) p="$c"; [ -n "$named" ] || named="$c" ;;
    *) p="${cwd:+$cwd/}$c" ;;
  esac
  if [ -s "$p" ]; then path="$p"; break; fi
done <<EOF
$cands
EOF
if [ -z "$path" ]; then
  # Only relative names, joined to the folder Claude Code sends — which may not be the run's: can't tell.
  [ -n "$named" ] || exit 0
  path="$named"
fi

problems=""
add() { problems="${problems}${problems:+; }$1"; }

if [ ! -s "$path" ]; then
  add "the file you named ($path) doesn't exist or is empty"
else
  l1="$(sed -n '1p' "$path" | tr -d '\r')"
  bom="$(printf '\357\273\277')"; l1="${l1#"$bom"}"                 # an editor's byte-order mark
  l2="$(sed -n '2p' "$path" | tr -d '\r')"
  if [ "$kind" = worker ]; then
    case "$l1" in '# '*) ;; *) add "line 1 must be '# <Seat> — <lane> (<mode>)'" ;; esac
    case "$l2" in 'ref:'*) ;; *) add "line 2 must be 'ref: <the first heading of your reference document, copied exactly>' — one ref: line per document — or 'ref: none'" ;; esac
    if ! grep -q '^## Index' "$path"; then
      add "add an '## Index' section with one line per item: '<n> · <severity> · <principle> · <path:line> · <title>' (write '(none) — <why>' for an empty lane)"
    else
      # The same rule as index_shape in bin/council: change both together.
      shape="$(awk '
        /^## / { h = tolower($0); sub(/^## +/, "", h); ins = (h ~ /^index([ \t\r]|$)/); next }
        !ins { next }
        {
          l = $0; gsub(/\r/, "", l); gsub(/\t/, " ", l)
          if (l ~ /^###/) {                          # a "### P1" group heading is skipped; an item body ends the Index
            if (l ~ /^#+ *[*_]*C?[0-9]+[a-z]?[*_]* +(·|\|) /) bad++
            else if (tolower(l) !~ /^#+ *[*_]*(p[0-4]|must|should|could|strong|moderate|weak|critical|high|medium|low|major|minor|blocker|severity)([^a-z0-9]|$)/) ins = 0
            next
          }
          if (l ~ /^ *$/) next
          if (l ~ /^ *\(none\)/) { none = 1; next }
          if (l ~ /^[-*+]? *[*_]*C?[0-9]+[a-z]?[*_]*\.? +(·|\|) /) {   # an item needs four fields: no citation, no item
            if ((index(l, "·") ? split(l, f, / +· +/) : split(l, f, / +\| +/)) >= 4) ok++; else bad++
            next
          }
          if (l ~ /^ *([-*+] +)?[*_]*C?[0-9]+/ || l ~ / · / || l ~ /^ *\| *[*_]*C?[0-9]+[a-z]?[*_]* *\|/) bad++
        }
        END { printf "%d %d %d", ok, bad, none }' "$path")"
      ok="${shape%% *}"; rest="${shape#* }"; bad="${rest%% *}"; none="${rest#* }"
      [ "${bad:-0}" -eq 0 ] || add "$bad line(s) under '## Index' aren't in the index format — write each item as '<n> · <severity> · <principle> · <path:line> · <title>'"
      if [ "${ok:-0}" -eq 0 ] && [ "${none:-0}" -eq 0 ]; then add "the Index is empty — list your items, or write '(none) — <why>' if your lane had nothing"; fi
    fi
  else
    case "$l1" in '# Verification'*) ;; *) add "line 1 must be '# Verification — <run title>'" ;; esac
    grep -q '^|' "$path" || add "add the verdict table: | # | Item | Verdict | Evidence |"
  fi
  size="$(wc -c < "$path" | tr -d ' ')"
  if [ "$size" -gt 16384 ]; then
    kb=$(( (size * 10 + 1023) / 1024 )); kb="$((kb / 10)).$((kb % 10))"     # rounded up: 16.0 would read as fine
    if [ "$kind" = worker ]; then
      add "the file is $kb KB (limit 16 KB) — cut it to your item cap and keep items short"
    else
      add "the file is $kb KB (limit 16 KB) — shorten the paragraphs, and keep every row of the verdict table"
    fi
  fi
fi

[ -z "$problems" ] && exit 0
block "$path — $problems. Fix the file, then reply again with your one line."

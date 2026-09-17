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

case "$input" in *'"stop_hook_active":true'* | *'"stop_hook_active": true'*) exit 0 ;; esac

case "$(json_str agent_type)" in
  *council-worker) kind=worker ;;
  *council-verifier) kind=verifier ;;
  *) exit 0 ;;
esac

msg="$(json_str last_assistant_message)"
[ -n "$msg" ] || exit 0
if printf '%s\n' "$msg" | grep -q '^BLOCKED'; then exit 0; fi        # a line that starts with BLOCKED

line="$(printf '%s\n' "$msg" | grep -m 1 'Wrote ' || true)"
[ -n "$line" ] || block "finish by writing your output file, then reply with exactly one line: Wrote <output path> — <N> items (<counts>)."

path="$(printf '%s' "$line" | sed -n 's/^.*Wrote[[:space:]][[:space:]]*\(.*\.md\).*$/\1/p' | tr -d '`"')"
[ -n "$path" ] || exit 0
case "$path" in
  /* | [A-Za-z]:*) ;;
  *) cwd="$(json_str cwd)"; [ -z "$cwd" ] || path="$cwd/$path" ;;
esac

problems=""
add() { problems="${problems}${problems:+; }$1"; }

if [ ! -s "$path" ]; then
  add "the file you named ($path) doesn't exist or is empty"
else
  l1="$(sed -n '1p' "$path" | tr -d '\r')"
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
  [ "$size" -le 16384 ] || add "the file is $(( size / 1024 )) KB — cut it to your item cap and keep items short (limit 16 KB)"
fi

[ -z "$problems" ] && exit 0
block "$path — $problems. Fix the file, then reply again with your one line."

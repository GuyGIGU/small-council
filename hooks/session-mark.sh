#!/usr/bin/env bash
# Small Council — sourced by the bash hooks. Builtins only, so no process starts; a failure is silent and changes nothing.
# records/hook_marks.py leaves the same marks from Python, and trims the folders. Ids are spelled out: bash 3.2's [a-z] follows the locale.
mark_session() {   # <session id> <hook>: an empty <id> and <id>.<hook> in $XDG_CACHE_HOME's mark folder, and ~/.cache's unless the same
  case "$1" in ''|.*|*[!0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ._-]*) return 0 ;; esac; [ -z "${XDG_CACHE_HOME:-}" ] || mark_in "$XDG_CACHE_HOME/small-council/sessions" "$1" "$2"
  [ -z "${HOME:-}" ] || [ "${XDG_CACHE_HOME:-}" = "$HOME/.cache" ] || mark_in "$HOME/.cache/small-council/sessions" "$1" "$2"; return 0
}
mark_in() { { [ -d "$1" ] || mkdir -p "$1"; } 2>/dev/null && { : > "$1/$2"; : > "$1/$2.$3"; } 2>/dev/null; }
no_council() {   # [folder]: true only when no council home can be there (records/home.py's council_home); when unsure, false
  local d="${1:-$PWD}" g=""; case "$d" in [A-Za-z]:\\*) d="${d//\\//}" ;; esac; [ -d "$d" ] || return 1; [ -z "${GIT_DIR:-}${GIT_WORK_TREE:-}" ] || return 1
  while [ -n "$d" ]; do [ ! -e "$d/.council" ] || return 1; [ ! -d "$d/.git" ] || return 0; if [ -f "$d/.git" ]; then IFS= read -r g 2>/dev/null < "$d/.git"; g="${g#gitdir: }"; g="${g:-?}"; break; fi; case "$d" in */*) d="${d%/*}" ;; *) d="" ;; esac; done
  case "$g" in ''|*/.git/modules/*) return 0 ;; */.git/worktrees/*) g="${g%/.git/worktrees/*}"; case "$g" in /*|[A-Za-z]:*) ;; *) g="$d/$g" ;; esac; [ ! -e "$g/.council" ] ;; *) return 1 ;; esac
}

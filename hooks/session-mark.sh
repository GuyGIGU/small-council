#!/usr/bin/env bash
# Small Council — the session mark of the hooks that stay bash, sourced by bash-gate.sh and seat-gate.sh. The
# Python hooks leave the same files through src/council/records/hook_marks.py, which also clears marks older than
# 30 days. An empty <id> and <id>.<hook> go in each mark folder: $XDG_CACHE_HOME's, and ~/.cache's unless that is
# the same one. The id must be safe as a file name (letters spelled out, as bash 3.2's [a-z] follows the locale).
# Builtins only, so no process starts once the folder is there; a failure is silent and changes nothing.
mark_session() {   # <session id> <hook>
  case "$1" in ''|.*|*[!0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ._-]*) return 0 ;; esac
  [ -z "${XDG_CACHE_HOME:-}" ] || mark_in "$XDG_CACHE_HOME/small-council/sessions" "$1" "$2"
  [ -z "${HOME:-}" ] || [ "${XDG_CACHE_HOME:-}" = "$HOME/.cache" ] || mark_in "$HOME/.cache/small-council/sessions" "$1" "$2"
  return 0
}
mark_in() { { [ -d "$1" ] || mkdir -p "$1"; } 2>/dev/null && { : > "$1/$2"; : > "$1/$2.$3"; } 2>/dev/null; }

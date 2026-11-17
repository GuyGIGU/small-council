"""How the helper was called in a Bash or PowerShell command, read from the command's text: council run audit's
reading of a session transcript (and hooks/bash-gate.sh's twin, in awk)."""
from __future__ import annotations

import re
import shlex
from typing import Any, Dict

Call = Dict[str, Any]

HELPER_WORDS = {"home", "run", "state", "seat", "cap", "correct", "index", "evidence", "repair",
                "gate", "gates", "changed", "collect", "check", "map", "fingerprint", "memory", "prior", "ask",
                "ledger", "route", "status", "doctor", "help",
                "sharing", "version"}
TWO_WORD = {"run", "cap", "memory", "evidence", "repair", "route"}


def heredoc_free(command: str) -> str:
    """The command without here-document bodies (their lines are data, not commands)."""
    out, ends = [], []
    for line in command.split("\n"):
        if ends:
            if line.strip() == ends[0]:
                ends.pop(0)
            continue
        out.append(line)
        ends += [tag for _, tag in re.findall(r"<<-?\s*(['\"]?)([A-Za-z_]\w*)\1", line)]
    return "\n".join(out)


def pipelines(command: str) -> list[list[str]]:
    """Each simple command of a shell line as its list of pipe stages. Splits on ; && || & newline and
    backquotes outside quotes, then on single | (and |&); enough to see how the helper was called. A ( or $(
    opens a group and its ) closes it, each as a line of its own; a pipe right after the ) stays on the ) line,
    so `(...) | tail` is seen as the group's output cut."""
    lines, stages, cur, quote, n = [], [], [], None, 0

    def end() -> None:
        stages.append("".join(cur))
        lines.append(list(stages))
        del stages[:], cur[:]
    while n < len(command):
        ch, two = command[n], command[n:n + 2]
        if quote:
            cur.append(ch)
            if ch == "\\" and quote == '"' and n + 1 < len(command):
                cur.append(command[n + 1])
                n += 1
            elif ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            cur.append(ch)
        elif ch == "\\" and n + 1 < len(command):
            cur.append(two)
            n += 1
        elif ch == "&" and (command[n - 1:n] in "<>" and n > 0 or command[n + 1:n + 2] == ">"):
            cur.append(ch)                                       # 2>&1, &>file: a redirection, not a separator
        elif two == "|&":
            stages.append("".join(cur))
            del cur[:]
            n += 1
        elif two in ("&&", "||"):
            end()
            n += 1
        elif two == "$(" or ch == "(":
            end()
            lines.append(["("])
            n += 1 if two == "$(" else 0
        elif ch == ")":
            end()
            if re.match(r"(?:\s*(?:[0-9]*>&[0-9-]+|&>\s*\S+|[0-9]*>>?\s*[^\s|;&]+))*\s*\|(?!\|)", command[n + 1:]):
                cur.append(")")                                  # the group's own pipe stages follow
            else:
                lines.append([")"])
        elif ch in ";\n&`":
            end()
        elif ch == "|":
            stages.append("".join(cur))
            del cur[:]
        else:
            cur.append(ch)
        n += 1
    end()
    return [[s.strip() for s in line] for line in lines if line and line[0].strip()]


def words_of(stage: str) -> list[str]:
    try:
        return shlex.split(stage, posix=True)
    except ValueError:
        return stage.split()


# Shell groups whose output one pipe after their end cuts as a whole: `for ...; do council ...; done | tail`.
OPENERS = {"(": ")", "{": "}", "for": "done", "select": "done", "while": "done", "until": "done", "if": "fi",
           "case": "esac"}
LEADS = ("!", "&", "time", "command", "exec", "nohup", "env", "do", "then", "else", "elif")


def cut_of(stages: list[str]) -> str | None:
    return next((s for s in stages[1:] if words_of(s)[:1] and words_of(s)[0] in ("tail", "head")), None)


def invocations(command: str) -> list[Call]:
    """The helper calls in a Bash or PowerShell command: how each was called (plain, path or variable),
    its subcommand, and the tail/head stage that cut its output, if any — its own, or one on a loop, if,
    { } or ( ) group around it. Calls inside a loop body count, and so does `bash "$C" …` once C was set to
    the helper earlier in the same command. "last": the call is the command's last, unpiped, so the
    command's exit is its own."""
    command = heredoc_free(command or "")
    variables = {"C", "COUNCIL"} | set(name for name, value in re.findall(
        r"(?:^|[\s;&(|])([A-Za-z_]\w*)=(\"[^\"]*\"|'[^']*'|\S*)", command) if re.search(r"[/\\]council\b", value))
    variables |= set(re.findall(r"(?:^|[\s;&(|])([A-Za-z_]\w*)=[\"']?\$\((?:command -v|which) council\)", command))
    found, groups = [], []                       # groups: (the word that closes it, where its calls start)
    lines = pipelines(command)
    for index, stages in enumerate(lines):
        words = words_of(stages[0])
        if words and words[0] in (")", "}", "done", "fi", "esac"):
            if groups and groups[-1][0] == words[0]:
                begin = groups.pop()[1]
                cut = cut_of(stages)
                for call in found[begin:] if cut else []:
                    call["cut"] = call["cut"] or cut
            continue
        while words:
            if words[0] in OPENERS:
                groups.append((OPENERS[words[0]], len(found)))
                if words[0] in ("for", "select", "case"):
                    words = []                     # its word list or subject, not a command
                    break
            elif not (re.match(r"^[A-Za-z_]\w*=", words[0]) or words[0] in LEADS):
                break
            words = words[1:]
        if not words:
            continue
        first = words[0].replace("\\", "/")
        form, rest = None, []
        if first == "council":
            form, rest = "plain", words[1:]
        elif re.search(r"(^|/)(ba)?sh(\.exe)?$", first) and len(words) > 1:
            second = words[1].replace("\\", "/")
            match = re.match(r"^\$\{?([A-Za-z_]\w*)\}?$", second)
            if second.endswith("/council"):
                form, rest = "path", words[2:]
            elif match and match.group(1) in variables:
                form, rest = "variable", words[2:]
        elif first.endswith("/council"):
            form, rest = "path", words[1:]
        else:
            match = re.match(r"^\$\{?([A-Za-z_]\w*)\}?$", first)
            if match and match.group(1) in variables:
                form, rest = "variable", words[1:]
        if not form or not rest or rest[0] not in HELPER_WORDS:
            continue
        sub = rest[0]
        if sub in TWO_WORD and len(rest) > 1 and re.match(r"^[a-z]+$", rest[1]):
            sub += " " + rest[1]
        found.append({"form": form, "sub": sub, "flags": [w for w in rest if w.startswith("--")], "cut": cut_of(stages),
                      "text": stages[0][:120], "last": index == len(lines) - 1 and len(stages) == 1})
    return found

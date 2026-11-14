"""Secret-looking strings taken out of the user's words before they are filed: `council ask save`, `council check`'s
quotes, `council memory`'s drafts and answers. It knows common shapes, not every secret, and the caller says so.

Bytes in, bytes out, line by line, as the sed script it was ported from read them in the C locale: a carriage return
is part of its line, a byte past ASCII is one character, and a last line with no newline is written back without
one. In this order:
 - private-key blocks, at any indent: the BEGIN line becomes [redacted private key]; the key lines under it go until
   the END line or the first line that isn't key-shaped, so the text after a snipped key stays. A short key-shaped
   line waits (PENDING) and goes only if the END line follows it. An armour header (Comment:, Version: …) stays; a
   line with one key's END and the next one's BEGIN goes on;
 - tokens by their prefix (sk-, sk_live_, whsec_, ghp_, glpat-, npm_, hf_, pypi-, GOCSPX-, AKIA/ASIA, AIza,
   xoxb-/xapp-, SG., bot tokens, JWTs, Slack webhook paths, a URL's password); a lowercase word-list such as
   sk-learn-compat-… is shielded first (SHIELD), only when every part of it is a word;
 - values named by what's around them (Authorization, Bearer/Basic, "password is", key = value for password-,
   token-, secret- and …key-names) are marked (WORD for passwords, MARK for the rest), then unmarked when they read
   as ordinary text: a date, an ${ENV} name, a path made of words, code such as a.b.get( or getpass() — for a
   password also a short plain word; for the rest also a count of up to 10 digits, a call, a dotted name, words
   joined by - _ . or /, a CamelCase name, or a value with no digit. What stays marked becomes [redacted].

bin/council keeps its sed copy (redact_copy) for the bash that has not moved (state, cap allow, tune, repair) until
S8b; tests/py/test_redact.py holds the two to the same output."""
from __future__ import annotations

import re
from typing import Callable

MARK, WORD, SHIELD = b"\x02", b"\x04", b"\x05"
REDACTED = b"[redacted"
_S = b" \t\n\x0b\x0c\r"                                  # [[:space:]] in the C locale


def ci(word: str) -> bytes:
    """A word in either case, letter by letter: token -> [tT][oO][kK][eE][nN]."""
    return b"".join(b"[%s%s]" % (c.lower().encode(), c.upper().encode()) if c.isalpha() else re.escape(c).encode()
                    for c in word)


def _any(*words: str) -> bytes:
    return b"|".join(ci(word) for word in words)


_PW = b"[A-Za-z0-9_]*(" + _any("passwd", "password", "passphrase", "passcode") + b"|[_-]" + ci("pass") + b"|[_-]" \
    + ci("pwd") + b")"
_TK = b"[A-Za-z0-9_]*(" + _any("secret", "token", "credentials", "credential") + b"|(" \
    + _any("api", "access", "account", "encryption", "private", "signing", "master", "client", "app", "auth",
           "session", "shared", "license", "secret") + b")[_-]?" + ci("key") + b")"
_Q = b"[\"'`]"
_V = b"[^" + _S + b"\"'`,;}" + MARK + WORD + b"]"           # one character of an unquoted value …
_VE = b"[^" + _S + b"\"'`,;}." + MARK + WORD + b"]"         # … and its last: a full stop after it ends the sentence
_KEY = b"-----BEGIN [A-Z0-9 ]*PRIVATE KEY( BLOCK)?-----"
_END = b"-----END [A-Z0-9 ]*PRIVATE KEY( BLOCK)?-----"
_B64 = b"[A-Za-z0-9+/]"
_SP = b"[" + _S + b"]"
_MARKS = b"[" + MARK + WORD + b"]"

# What a marked value may be and still read as ordinary text.
_ID = b"[A-Za-z_][A-Za-z0-9_]*"
_WP = b"(_*[a-z]+[0-9]*(_+[a-z]*[0-9]*)*|_*[A-Z]+[0-9]*(_+[A-Z]*[0-9]*)*|[A-Z]?[a-z]+([A-Z][a-z]+)*[0-9]*)"
_ARG = b"(\\\\([A-Za-z0-9_.]*\\\\))?"                     # as the sed has it: a backslash-wrapped (x), or nothing
_DCALL = _ID + b"(\\." + _ID + b")+\\(([A-Za-z0-9_.]*\\))?(\\." + _ID + _ARG + b")*"
_CALL = _ID + b"\\(([A-Za-z0-9_.]*\\))?(\\." + _ID + _ARG + b")*|" + _DCALL
_PCALL = _ID + b"\\((\\)|_*[A-Z]+[0-9]*(_+[A-Z]*[0-9]*)*\\))?"
_PS = b"(([A-Z]?[a-z_.-]+[0-9]*)+|[A-Z0-9_.-]+)"
_PATH = (b"(/" + _PS + b"){2,}/?|(\\.{1,2}|~)(/" + _PS + b")+/?|[A-Za-z]:[\\\\/][^" + MARK + WORD
         + b"]*|([A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\\.[A-Za-z0-9]{1,5}")
_W = b"(([A-Z]?[a-z]+|[A-Z]+)[0-9]*|[0-9]+)"
_L = b"([A-Z]?[a-z]{2,}|[A-Z]{3,})[0-9]*"
_SEP = b"[-_./]"
_JOINED = b"(" + _W + _SEP + b")*" + _L + _SEP + b"(" + _W + _SEP + b")*" + _L + b"(" + _SEP + _W + b")*"
_CAMEL = b"([A-Z][a-z]+){2,}[0-9]{0,2}|[a-z]+([A-Z][a-z]+)+[0-9]{0,2}"
# A password described in hyphenated words: two small joining words make it prose. A passphrase of random words
# ("correct-horse-battery-staple") has none, so it stays redacted.
_FW = b"(" + b"|".join(b"the a an to of in on at by for with before after from into we our us it its is are be and or "
                       b"not as same every each all".split()) + b")"
_PROSE = b"([a-z]+-)*" + _FW + b"-([a-z]+-)*" + _FW + b"(-[a-z]+)+"

_KEY_ID = re.compile(b"(^|[^A-Za-z0-9])((AKIA|ASIA)[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35})")


def _rule(pattern: bytes, replacement: bytes) -> Callable[[bytes], bytes]:
    compiled = re.compile(pattern, re.S)
    return lambda line: compiled.sub(replacement, line)


def _value_rules() -> list[Callable[[bytes], bytes]]:
    """The values named by what's around them, marked; then the ordinary text among them unmarked."""
    return [
        _rule(b"(" + ci("authorization") + _Q + b"?" + _SP + b"*[:=]" + _SP + b"*" + _Q + b"?[A-Za-z][A-Za-z0-9_-]*"
              + _SP + b"+)(" + _V + b"{7,}" + _VE + b")", b"\\1" + MARK + b"\\2" + MARK),
        _rule(b"([Bb]earer" + _SP + b"+|[Bb]asic" + _SP + b"+)([A-Za-z0-9._~+/=-]{15,}[A-Za-z0-9_~+/=-])",
              b"\\1" + MARK + b"\\2" + MARK),
        _rule(b"((" + _any("password", "passwd", "passphrase") + b")" + _SP + b"+(" + _any("is", "was") + b")" + _SP
              + b"*:?" + _SP + b"+)(" + _V + b"{5,}" + _VE + b")", b"\\1" + WORD + b"\\4" + WORD),
        _rule(b"((" + ci("secret") + b"[" + _S + b"A-Za-z]{0,12}|" + ci("token") + b"|(" + _any("api", "access")
              + b")[" + _S + b"_-]?" + ci("key") + b")" + _SP + b"+(" + _any("is", "was") + b")" + _SP + b"*:?" + _SP
              + b"+)(" + _V + b"{7,}" + _VE + b")", b"\\1" + MARK + b"\\5" + MARK),
        _rule(b"(" + _PW + _Q + b"?" + _SP + b"*[:=]" + _SP + b"*)\"([^\"" + MARK + WORD + b"]{6,})\"",
              b"\\1\"" + WORD + b"\\3" + WORD + b"\""),
        _rule(b"(" + _PW + _Q + b"?" + _SP + b"*[:=]" + _SP + b"*)'([^'" + MARK + WORD + b"]{6,})'",
              b"\\1'" + WORD + b"\\3" + WORD + b"'"),
        _rule(b"(" + _PW + _Q + b"?" + _SP + b"*[:=]" + _SP + b"*" + _Q + b"?)(" + _V + b"{5,}" + _VE + b")",
              b"\\1" + WORD + b"\\3" + WORD),
        _rule(b"(" + _TK + _Q + b"?" + _SP + b"*[:=]" + _SP + b"*)\"([^\"" + MARK + WORD + b"]{8,})\"",
              b"\\1\"" + MARK + b"\\4" + MARK + b"\""),
        _rule(b"(" + _TK + _Q + b"?" + _SP + b"*[:=]" + _SP + b"*)'([^'" + MARK + WORD + b"]{8,})'",
              b"\\1'" + MARK + b"\\4" + MARK + b"'"),
        _rule(b"(" + _TK + _Q + b"?" + _SP + b"*[:=]" + _SP + b"*" + _Q + b"?)(" + _V + b"{7,}" + _VE + b")",
              b"\\1" + MARK + b"\\4" + MARK),
        _rule(_MARKS + b"([0-9]{4}-[0-9]{2}-[0-9]{2}[T0-9:.Z+-]*|\\$\\{?[A-Za-z_][A-Za-z0-9_]*\\}?|"
                       b"%[A-Za-z_][A-Za-z0-9_]*%)" + _MARKS, b"\\1"),
        _rule(WORD + b"([A-Za-z._-]{1,19}|" + _DCALL + b"|" + _PCALL + b"|" + _PATH + b"|" + _PROSE + b")" + WORD,
              b"\\1"),
        _rule(MARK + b"([0-9]{1,10}|" + _CALL + b"|" + _PATH + b"|" + _WP + b"(\\." + _WP + b")+|" + _JOINED + b"|"
              + _CAMEL + b")" + MARK, b"\\1"),
        _rule(MARK + b"([^0-9A-Z+=" + MARK + b"]+|[^0-9a-z+=" + MARK + b"]+|[^0-9+=" + MARK + b"]{1,19})" + MARK,
              b"\\1"),
        _rule(_MARKS + b"[^" + MARK + WORD + b"]*" + _MARKS, b"[redacted]"),
        _rule(SHIELD, b""),
    ]


def _token_rules() -> list[Callable[[bytes], bytes]]:
    """The tokens known by their prefix, after a lowercase word-list such as sk-learn-compat-… is shielded."""
    return [
        _rule(b"(^|[^A-Za-z0-9_-])(sk|rk)(-[a-z]{1,16}[0-9]{0,4}(-[a-z]{1,16}[0-9]{0,4}){2,})([^A-Za-z0-9_-]|$)",
              b"\\1\\2" + SHIELD + b"\\3\\5"),
        _rule(b"(^|[^A-Za-z0-9_-])((sk|rk)(-|_live_|_test_)|whsec_)[A-Za-z0-9_-]{20,}", b"\\1[redacted]"),
        _rule(b"(^|[^A-Za-z0-9_])(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{22,}|gl(pat|dt|rt|ptt|cbt|soat)-"
              b"[A-Za-z0-9_-]{20,}|npm_[A-Za-z0-9]{30,}|hf_[A-Za-z0-9]{30,}|pypi-[A-Za-z0-9_-]{40,}|GOCSPX-"
              b"[A-Za-z0-9_-]{20,})", b"\\1[redacted]"),
        _rule(b"(AKIA|ASIA)[0-9A-Z]{16}([,;" + _S + b"]+)[A-Za-z0-9+/]{40}([^A-Za-z0-9+/]|$)",
              b"[redacted]\\2[redacted]\\3"),
        lambda line: _KEY_ID.sub(b"\\1[redacted]", line),
        _rule(b"(^|[^A-Za-z0-9_-])(xox[abeoprs]|xapp)-[A-Za-z0-9-]{10,}", b"\\1[redacted]"),
        _rule(b"(^|[^A-Za-z0-9_-])SG\\.[A-Za-z0-9_-]{16,}\\.[A-Za-z0-9_-]{16,}", b"\\1[redacted]"),
        _rule(b"(^|[^A-Za-z0-9])[0-9]{8,10}:AA[A-Za-z0-9_-]{30,}", b"\\1[redacted]"),
        _rule(b"eyJ[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}", b"[redacted]"),
        _rule(b"(hooks\\.slack\\.com/(services|workflows|triggers)/)[A-Za-z0-9_/-]{16,}", b"\\1[redacted]"),
        _rule(b"(://[^/:@" + _S + b"]*:)[^/@" + _S + b"]+@", b"\\1[redacted]@"),
    ]


_WHOLE_KEY = re.compile(_KEY + b".*" + _END, re.S)
_OPEN_KEY = re.compile(_KEY)
_OPEN_KEY_BODY = re.compile(_KEY + b"[A-Za-z0-9+/=\\\\]*")
_END_KEY = re.compile(_END)
_END_THEN_KEY = re.compile(_END + b".*" + _KEY, re.S)
_CHECKSUM = re.compile(b"^[" + _S + b">]*=" + _B64 + b"{4}" + _SP + b"*$")
_PADDED = re.compile(b"^[" + _S + b">]*" + _B64 + b"*={1,2}" + _SP + b"*$")
_LONG = re.compile(b"^[" + _S + b">]*" + _B64 + b"{40,}" + _SP + b"*$")
_SHORT = re.compile(b"^[" + _S + b">]*" + _B64 + b"{1,39}" + _SP + b"*$")
_BLANK = re.compile(_SP + b"*$")
_ARMOUR = re.compile(b"[" + _S + b">]*(Proc-Type|DEK-Info|Version|Comment|Hash|Charset):")
_TOKENS, _VALUES = _token_rules(), _value_rules()

NORMAL, IN_KEY, PENDING = "normal", "key", "pending"


def _shapes(line: bytes) -> tuple[bytes, bool]:
    """Every rule after the key lines; True when the line opens a key that runs on below it."""
    line = _WHOLE_KEY.sub(b"[redacted private key]", line)
    opened = bool(_OPEN_KEY.search(line))
    if opened:
        line = _OPEN_KEY_BODY.sub(b"[redacted private key]", line, count=1)
    for rule in _TOKENS + _VALUES:
        line = rule(line)
    return line, opened


def _in_key(line: bytes, last: bool) -> tuple[str, bytes | None, bool]:
    """A line inside a key block: (what comes next, the line still to be shaped or None when it goes, whether the
    block goes on). Bare: printed as it is."""
    if _END_KEY.search(line):
        if not _END_THEN_KEY.search(line):
            return "drop", None, False
        return "shape", line[_END_KEY.search(line).end():], False      # type: ignore[union-attr]
    if _BLANK.match(line):
        return "bare", line, True
    if _ARMOUR.match(line):
        return "shape", line, True
    if _CHECKSUM.match(line) or _PADDED.match(line):
        return "drop", None, True
    if _LONG.match(line) and re.search(b"[A-Z]", line) and re.search(b"[a-z]", line) and re.search(b"[0-9]", line):
        return "drop", None, True
    if _SHORT.match(line) and not last:
        return "pending", line, False
    return "shape", line, False


def redact(data: bytes) -> tuple[bytes, int]:
    """data with its secret-looking strings redacted, and how many were (the [redacted marks it gained)."""
    lines = data.split(b"\n")
    newline_at_end = lines[-1] == b""
    if newline_at_end:
        lines.pop()
    out: list[bytes] = []
    state, pending = NORMAL, b""
    printed_last = False
    for at, line in enumerate(lines):
        last = at == len(lines) - 1
        if state == PENDING:
            if _END_KEY.search(line):
                state = IN_KEY                                    # the short line was the key's tail: it goes too
            elif _CHECKSUM.match(line):
                continue
            else:
                out.append(_KEY_ID.sub(b"\\1[redacted]", pending) + b"\n")
                state = NORMAL
        if state == IN_KEY:
            step, line_or_none, state_on = _in_key(line, last)
            if step == "drop":
                state = IN_KEY if state_on else NORMAL
                continue
            if step == "pending":
                state, pending = PENDING, line
                continue
            state = IN_KEY if state_on else NORMAL
            if step == "bare":
                out.append(line + b"\n")
                printed_last = last
                continue
            line = line_or_none                                   # type: ignore[assignment]
        shaped, opened = _shapes(line)
        if opened:
            state = IN_KEY
        out.append(shaped + b"\n")
        printed_last = last
    result = b"".join(out)
    if printed_last and not newline_at_end:                      # a last line with no newline is written without one
        result = result[:-1]
    return result, result.count(REDACTED) - data.count(REDACTED)

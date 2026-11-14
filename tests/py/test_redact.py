"""Redaction of the user's words (records/redact.py) against bin/council's redact_copy, which stays for the bash that
has not moved (state, cap allow, tune, repair): the same bytes out and the same count."""
from __future__ import annotations

import unittest

import support

from council.records import redact

LINES = [
    "We need CSV export, filterable by `date` and $OWNER — \"admins\" only.",
    "Key: sk-abcdefghijklmnopqrstuvwx · token=ghp_abcdefghijklmnopqrstuvwxyz1234 · café",
    "password: hunter2hunter2 and PASSWORD=\"Zq8vT3xKp2Lm\"",
    "my db password is Zq8vT3xKp2Lm",
    "api_key = 'AKIAIOSFODNN7EXAMPLE'",
    "set the password to the same-as-before-for-every-user",
    "the password is hashed-with-bcrypt-before-storage",
    "the password field uses getPassword() and config.secret_key",
    "a passphrase: correct-horse-battery-staple",
    "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcDEF123_-xyz",
    "-----BEGIN RSA PRIVATE KEY-----",
    "MIIEowIBAAKCAQEA0Zt3exampleexampleexampleexampleexample",
    "-----END RSA PRIVATE KEY-----",
    "secret path: /etc/app/secrets/prod.env and C:\\Users\\me\\token.txt",
    "nothing secret here, just ü and 日本語",
    "AWS: aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
]


class SameAsTheHelperTest(support.Scratch):
    def helper(self, data: bytes) -> tuple[bytes, int]:
        src = self.write("said.raw", data, binary=True).as_posix()
        dst = (self.tmp / "said").as_posix()
        code, out = support.helper_bash(self, 'redact_copy "$1" "$2"', src, dst)
        self.assertEqual(code, 0)
        return (self.tmp / "said").read_bytes(), int(out or b"0")

    def assert_same(self, data: bytes) -> tuple[bytes, int]:
        python = redact.redact(data)
        self.assertEqual(self.helper(data), python)
        return python

    def test_the_whole_text_with_crlf_and_no_final_newline(self) -> None:
        """Redaction goes line by line, so one text holds every shape."""
        text = "\n".join(LINES).encode("utf-8") + b"\ncaf\xe9 (a stray byte) token=ghp_abcdefghijklmnopqrstuvwxyz1234"
        out, count = self.assert_same(text + b"\n")
        self.assertGreaterEqual(count, 6)
        self.assertIn(b"caf\xe9 (a stray byte)", out)
        self.assert_same(text.replace(b"\n", b"\r\n") + b"\r\n")
        self.assert_same(text)


class RedactTest(unittest.TestCase):
    def test_secrets_are_marked_and_counted(self) -> None:
        out, count = redact.redact(b"Key: sk-abcdefghijklmnopqrstuvwx and token=ghp_abcdefghijklmnopqrstuvwxyz1234\n")
        self.assertEqual(count, 2)
        self.assertNotIn(b"sk-abc", out)
        self.assertNotIn(b"ghp_", out)
        self.assertEqual(out.count(b"[redacted"), 2)

    def test_prose_and_code_stay(self) -> None:
        for line in (b"the password is hashed-with-bcrypt-before-storage\n",
                     b"the password field uses getPassword() and config.secret_key\n",
                     "nothing secret here, just ü\n".encode("utf-8")):
            self.assertEqual(redact.redact(line), (line, 0))

    def test_ci_matches_either_case(self) -> None:
        self.assertEqual(redact.ci("tok"), b"[tT][oO][kK]")


if __name__ == "__main__":
    unittest.main()

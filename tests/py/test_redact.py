"""Redaction of the user's words (records/redact.py): the bytes and the count bin/council's redact_copy gave,
written out."""
from __future__ import annotations

import unittest

import support  # noqa: F401  (puts src/ on the path)

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


SAID = [LINES[0], "Key: [redacted] · token=[redacted] · café", 'password: [redacted] and PASSWORD="[redacted]"',
        "my db password is [redacted]", "api_key = '[redacted]'", *LINES[5:8], "a passphrase: [redacted]",
        "Authorization: Bearer [redacted]", "[redacted private key]", *LINES[13:15],
        "AWS: aws_secret_access_key=[redacted]"]


class SameAsTheHelperTest(unittest.TestCase):
    def test_the_whole_text_with_crlf_and_no_final_newline(self) -> None:
        """Redaction goes line by line, so one text holds every shape: what bin/council's redact_copy wrote, and
        its count, for the text with LF, with CR LF and with no final newline."""
        text = "\n".join(LINES).encode("utf-8") + b"\ncaf\xe9 (a stray byte) token=ghp_abcdefghijklmnopqrstuvwxyz1234"
        said = "\n".join(SAID).encode("utf-8") + b"\ncaf\xe9 (a stray byte) token=[redacted]"
        self.assertEqual(redact.redact(text + b"\n"), (said + b"\n", 11))
        crlf = text.replace(b"\n", b"\r\n") + b"\r\n"
        self.assertEqual(redact.redact(crlf), (said.replace(b"\n", b"\r\n") + b"\r\n", 11))
        self.assertEqual(redact.redact(text), (said, 11))


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

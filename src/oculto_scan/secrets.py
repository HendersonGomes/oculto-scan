"""Small curated secret rules.

Token-shaped patterns are copied from gitleaks (MIT). See NOTICE.
The password/assignment rule is original and includes the Portuguese
label ``senha``. Entropy is a separate, opt-in pass.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

# Copied from gitleaks config (MIT). See NOTICE for attribution.
_GITLEAKS_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "aws-access-token",
        re.compile(r"(?:A3T[A-Z0-9]|AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}"),
    ),
    (
        "github-pat",
        re.compile(r"ghp_[0-9a-zA-Z]{36}"),
    ),
    (
        "gcp-api-key",
        re.compile(r"(?i)\b(AIza[0-9A-Za-z\-_]{35})(?:['\"\s]|$)"),
    ),
    (
        "slack-bot-token",
        re.compile(r"(xoxb-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*)"),
    ),
    (
        "private-key",
        # Header only. The gitleaks rule also spans the body; we stop at the
        # banner so a single spreadsheet cell cannot trigger a large match.
        re.compile(r"(?i)-----BEGIN[ A-Z0-9_-]{0,100}PRIVATE KEY(?: BLOCK)?-----"),
    ),
)

# Original assignment rule. Inspired by the idea of gitleaks' generic-api-key,
# rewritten for cell text and for the Portuguese word "senha". Entropy is not
# required: that pass is off unless the operator asks for it.
# ``aws_secret_access_key`` is matched as a whole token. ``Senha do portal: ...``
# allows a few words between the label and the separator.
_ASSIGNMENT = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:aws_secret_access_key|password|passwd|senha|api[_-]?key|token|secret|client[_-]?secret)\b"
    r"(?:\s+\w+){0,6}\s*[:=]\s*['\"]?([^\s'\"]{8,80})"
)
_PLACEHOLDERS = {
    "password",
    "changeme",
    "secret",
    "senha",
    "exemplo",
    "example",
    "xxxxxxxx",
    "12345678",
    "********",
}


@dataclass(frozen=True)
class SecretHit:
    rule: str
    value: str


def find_secrets(text: str) -> list[SecretHit]:
    if not text:
        return []
    hits: list[SecretHit] = []
    seen: set[str] = set()
    for rule_id, pattern in _GITLEAKS_RULES:
        for match in pattern.finditer(text):
            value = match.group(1) if match.lastindex else match.group(0)
            key = value.strip()
            if key and key not in seen:
                seen.add(key)
                hits.append(SecretHit(rule_id, key))
    for match in _ASSIGNMENT.finditer(text):
        value = match.group(1).strip().strip("'\"")
        folded = value.casefold()
        if folded in _PLACEHOLDERS or len(set(folded)) < 3:
            continue
        if value not in seen:
            seen.add(value)
            hits.append(SecretHit("senha-ou-token", value))
    return hits


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = Counter(value)
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


_ENTROPY_TOKEN = re.compile(r"[A-Za-z0-9+/_=-]{20,}")


def find_high_entropy(text: str, threshold: float = 4.2) -> list[str]:
    found: list[str] = []
    for match in _ENTROPY_TOKEN.finditer(text or ""):
        token = match.group(0)
        if token.isdigit() or token.isalpha():
            continue
        if shannon_entropy(token) >= threshold:
            found.append(token)
    return found

"""Mask values before they reach a terminal, a log or a JSON report."""

from __future__ import annotations

import re

_NON_ALNUM = re.compile(r"[^0-9A-Za-z]")
_USER_DIR = re.compile(r"(?i)([\\/](?:Users|home|usuarios)[\\/])([^\\/]+)")


def mask_cpf(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) != 11:
        return "***"
    return f"***.{digits[3:6]}.{digits[6:9]}-**"


def mask_cnpj(value: str) -> str:
    compact = _NON_ALNUM.sub("", value).upper()
    if len(compact) != 14:
        return "**.***.***/****-**"
    body = compact[:12]
    return f"**.{body[2:5]}.{body[5:8]}/{body[8:12]}-**"


def mask_pis(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) != 11:
        return "***"
    return f"***.{digits[3:8]}.**-*"


def mask_secret(value: str) -> str:
    stripped = value.strip()
    if stripped.upper().startswith("-----BEGIN"):
        prefix = "-----"
    else:
        prefix = stripped[:4]
    return f"{prefix}… ({len(stripped)} caracteres)"


def mask_account(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 2:
        return "***"
    return f"{'*' * max(len(digits) - 2, 2)}{digits[-2:]} ({len(digits)} dígitos)"


def mask_text(value: str) -> str:
    parts: list[str] = []
    for word in value.split():
        if len(word) <= 2:
            parts.append("*" * len(word))
        else:
            parts.append(word[:2] + "*" * (len(word) - 2))
    return " ".join(parts) if parts else "***"


def mask_path(value: str) -> str:
    def _repl(match: re.Match[str]) -> str:
        name = match.group(2)
        masked = (name[:1] + "***") if name else "***"
        return match.group(1) + masked

    return _USER_DIR.sub(_repl, value)


_CELL_REF = re.compile(r"(?<![A-Za-z])\$?[A-Z]{1,3}\$?\d+")
_BARE_NUMBER = re.compile(r"\d+(?:\.\d+)?%?")


def _ref_token(index: int) -> str:
    """Letter-only placeholder so the number mask cannot eat the marker."""
    chars: list[str] = []
    number = index + 1
    while number:
        number, rem = divmod(number - 1, 26)
        chars.append(chr(65 + rem))
    return "⟦" + "".join(reversed(chars)) + "⟧"


def mask_formula(formula: str) -> str:
    """Hide bare numeric literals and keep cell references readable."""
    held: dict[str, str] = {}

    def _hold(match: re.Match[str]) -> str:
        token = _ref_token(len(held))
        held[token] = match.group(0)
        return token

    masked = _BARE_NUMBER.sub("[n]", _CELL_REF.sub(_hold, formula))
    for token, original in held.items():
        masked = masked.replace(token, original)
    return masked

"""Mask values before they reach a terminal, a log or a JSON report."""

from __future__ import annotations

import re
from urllib.parse import urlparse

_NON_ALNUM = re.compile(r"[^0-9A-Za-z]")
_USER_DIR = re.compile(r"(?i)([\\/](?:Users|home|usuarios)[\\/])([^\\/]+)")
_QUOTED = re.compile(r'"(?:[^"]|"")*"')
_ABSOLUTE = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/]{2}|[\\/])")


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
    """Length only. The first characters of a token are still a secret."""
    stripped = value.strip()
    return f"({len(stripped)} caracteres)"


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


def _basename(value: str) -> str:
    normalized = value.replace("\\", "/").rstrip("/")
    name = normalized.split("/")[-1] if normalized else ""
    return name or "***"


def mask_url(value: str) -> str:
    """Scheme and host only. A file URL keeps just the file name."""
    parsed = urlparse(value.strip())
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    if parsed.scheme == "file":
        return _basename(parsed.path)
    return _basename(value)


def mask_path(value: str) -> str:
    """Absolute paths become the file name. Relative paths hide the user folder."""
    text = value.strip()
    if "://" in text or text.lower().startswith("file:"):
        return mask_url(text)
    normalized = text.replace("\\", "/")
    if _ABSOLUTE.match(text) or normalized.startswith("//"):
        return _basename(text)

    def _repl(match: re.Match[str]) -> str:
        name = match.group(2)
        masked = (name[:1] + "***") if name else "***"
        return match.group(1) + masked

    return _USER_DIR.sub(_repl, text)


def mask_link(value: str) -> str:
    """External link or hyperlink: URL host, or the file name of a path."""
    text = value.strip()
    if "://" in text or text.lower().startswith("file:"):
        return mask_url(text)
    return mask_path(text)


_CELL_REF = re.compile(r"(?<![A-Za-z0-9_])(\$?[A-Z]{1,3}\$?\d+)(?![A-Za-z0-9_(])")
_BARE_NUMBER = re.compile(r"\d+(?:\.\d+)?%?")


def _ref_token(index: int) -> str:
    """Letter-only placeholder so the number mask cannot eat the marker."""
    chars: list[str] = []
    number = index + 1
    while number:
        number, rem = divmod(number - 1, 26)
        chars.append(chr(65 + rem))
    return "⟦" + "".join(reversed(chars)) + "⟧"


def mask_sensitive(value: str) -> str:
    """Apply the same CPF and secret masks the scan uses, then the generic mask."""
    import tarja

    from oculto_scan.secrets import find_secrets

    text = value
    for hit in find_secrets(text):
        text = text.replace(hit.value, mask_secret(hit.value))
    try:
        matches = tarja.find(text[:100_000], entities=("BR_CPF", "BR_CNPJ", "BR_NIS"))
    except Exception:
        matches = []
    for match in matches:
        if not getattr(match, "valid_dv", False):
            continue
        if match.entity == "BR_CPF":
            replacement = mask_cpf(match.value)
        elif match.entity == "BR_CNPJ":
            replacement = mask_cnpj(match.value)
        elif match.entity == "BR_NIS":
            replacement = mask_pis(match.value)
        else:
            continue
        text = text.replace(match.value, replacement)
    return text


def mask_formula(formula: str) -> str:
    """Hide numeric literals and quoted text. Cell references stay readable."""
    held: dict[str, str] = {}

    def _hold(replacement: str) -> str:
        token = _ref_token(len(held))
        held[token] = replacement
        return token

    def _hold_string(match: re.Match[str]) -> str:
        return _hold("«texto»")

    def _hold_ref(match: re.Match[str]) -> str:
        return _hold(match.group(0))

    without_strings = _QUOTED.sub(_hold_string, formula)
    masked = _BARE_NUMBER.sub("[n]", _CELL_REF.sub(_hold_ref, without_strings))
    for token, original in held.items():
        masked = masked.replace(token, original)
    return masked

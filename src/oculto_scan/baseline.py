"""Baseline file: HMAC of finding fingerprints, never the raw value.

The salt lives next to the HMACs and is created locally. The fingerprint is
rule + path + sheet + cell, so the file does not contain personal data or
secrets. It suppresses a known location; a new cell still alerts.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from pathlib import Path

from oculto_scan.models import Finding


class BaselineError(Exception):
    pass


def _load(path: Path) -> tuple[bytes, set[str]]:
    if not path.exists():
        raise BaselineError(f"linha de base não encontrada: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BaselineError("linha de base inválida") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise BaselineError("versão de linha de base não suportada")
    salt_hex = payload.get("salt")
    entries = payload.get("entries")
    if not isinstance(salt_hex, str) or not isinstance(entries, list):
        raise BaselineError("linha de base inválida")
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError as exc:
        raise BaselineError("sal da linha de base inválido") from exc
    if len(salt) < 16:
        raise BaselineError("sal da linha de base curto demais")
    return salt, {item for item in entries if isinstance(item, str)}


def _digest(salt: bytes, finding: Finding) -> str:
    message = finding.fingerprint().encode("utf-8")
    return hmac.new(salt, message, hashlib.sha256).hexdigest()


def filter_findings(findings: list[Finding], path: Path) -> tuple[list[Finding], int]:
    salt, entries = _load(path)
    kept: list[Finding] = []
    ignored = 0
    for finding in findings:
        if _digest(salt, finding) in entries:
            ignored += 1
            continue
        kept.append(finding)
    return kept, ignored


def update_baseline(findings: list[Finding], path: Path) -> int:
    """Add fingerprints for ``findings``. Returns how many entries were written."""
    if path.exists():
        salt, entries = _load(path)
    else:
        salt = secrets.token_bytes(32)
        entries = set()
    for finding in findings:
        entries.add(_digest(salt, finding))
    payload = {
        "version": 1,
        "salt": salt.hex(),
        "entries": sorted(entries),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return len(entries)

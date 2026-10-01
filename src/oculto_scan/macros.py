"""Static VBA reading. The macro is never executed and no password is tried.

oletools is an optional extra (``pip install oculto-scan[macro]``). Without
it, a workbook that contains vbaProject.bin is reported as not analyzed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_ALTO = (
    "URLDownloadToFile",
    "ShellExecute",
    "Workbook_Open",
    "Document_Open",
    "Auto_Open",
    "AutoOpen",
    "AutoExec",
    "WScript",
    "PowerShell",
    "CreateObject",
    "GetObject",
    "Shell",
)
_MEDIO = ("Environ", "CallByName", "ADODB.Stream", "MSXML2.XMLHTTP", "WinHttp")
_URL = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_IP = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
_PATH = re.compile(r"(?:[A-Za-z]:\\|\\\\)[^\s\"']{3,180}")
_SKIP_HOST = ("schemas.microsoft.com", "schemas.openxmlformats.org", "www.w3.org")


@dataclass
class MacroRead:
    status: str  # ok, missing, unreadable
    modules: list[tuple[str, str]] = field(default_factory=list)
    keywords: list[tuple[str, str, str]] = field(default_factory=list)
    iocs: list[tuple[str, str, str]] = field(default_factory=list)


def _keywords(source: str) -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for line in source.splitlines():
        for word, risk in [(item, "alto") for item in _ALTO] + [(item, "medio") for item in _MEDIO]:
            if word.casefold() in seen:
                continue
            if re.search(rf"(?i)(?<![A-Za-z0-9_]){re.escape(word)}(?![A-Za-z0-9_])", line):
                seen.add(word.casefold())
                found.append((word, risk, line.strip()))
    return found


def _iocs(source: str) -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    def add(kind: str, raw: str, risk: str) -> None:
        key = raw.casefold()
        if key in seen:
            return
        seen.add(key)
        found.append((kind, raw, risk))

    for match in _URL.finditer(source):
        raw = match.group(0).rstrip(").,;")
        if any(host in raw.casefold() for host in _SKIP_HOST):
            continue
        add("url", raw, "alto")
    for match in _IP.finditer(source):
        raw = match.group(0)
        if raw.startswith("0.") or raw == "127.0.0.1":
            continue
        add("ip", raw, "medio")
    for match in _PATH.finditer(source):
        add("caminho", match.group(0), "medio")
    return found


def inspect_vba(data: bytes) -> MacroRead:
    """Read VBA source if oletools is installed. Never runs the macro."""
    if not data:
        return MacroRead(status="unreadable")
    try:
        from oletools.olevba import VBA_Parser
    except ImportError:
        return MacroRead(status="missing")
    try:
        parser = VBA_Parser("vbaProject.bin", data=data)
    except Exception:
        return MacroRead(status="unreadable")
    try:
        modules: list[tuple[str, str]] = []
        try:
            extracted = list(parser.extract_macros())
        except Exception:
            return MacroRead(status="unreadable")
        for _filename, _stream, vba_filename, vba_code in extracted:
            if not isinstance(vba_code, str) or not vba_code.strip():
                continue
            name = vba_filename or "modulo"
            modules.append((name, vba_code))
        if not modules:
            return MacroRead(status="unreadable")
        keywords: list[tuple[str, str, str]] = []
        iocs: list[tuple[str, str, str]] = []
        for _name, source in modules:
            keywords.extend(_keywords(source))
            for kind, raw, risk in _iocs(source):
                iocs.append((kind, raw, risk))
        return MacroRead(status="ok", modules=modules, keywords=keywords, iocs=iocs)
    finally:
        try:
            parser.close()
        except Exception:
            pass

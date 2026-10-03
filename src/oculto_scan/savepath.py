"""Where Excel last saved the workbook, and other path traces.

Nothing here is opened, resolved, or executed. Power Query is detected from
the package text; a DataMashup blob is only scanned for a readable path.
"""

from __future__ import annotations

import base64
import re

from defusedxml import ElementTree as DefusedET
from defusedxml.common import DefusedXmlException

from oculto_scan.models import Finding, NetworkHint, SaveTrace

# Spaces stay inside the path (OneDrive - Empresa). Stop at a quote, semicolon or newline.
_DRIVE = re.compile(r"(?i)[A-Za-z]:[/\\][^\"'<>|\r\n;]+")
_UNC = re.compile(r"\\\\[A-Za-z0-9._-]{1,63}(?:\\[^\"'<>|\r\n;]+)+")
_UNC_SLASH = re.compile(r"(?<![:\w])//[A-Za-z0-9._-]{1,63}(?:/[^\"'<>|\r\n;]+)+")
_FILE_URL = re.compile(r"(?i)file://+[^\s\"'<>]+")
_SHAREPOINT = re.compile(r"(?i)https?://([a-z0-9-]+)\.sharepoint\.com[^\s\"'<>]*")
_ONEDRIVE_DIR = re.compile(r"(?i)^onedrive\s*-\s*(.+)$")
_USER_DIR = re.compile(r"(?i)^(?:users|usuarios|usuários)$")
_KNOWN = {
    "users",
    "usuarios",
    "usuários",
    "desktop",
    "documents",
    "documentos",
    "downloads",
    "public",
    "onedrive",
}
_SKIP_USER = {"public", "default", "default user", "all users", "todos"}
_MAX_MASHUP = 1_500_000

_MESSAGE = {
    "absPath": (
        "Pasta onde o Excel gravou o arquivo pela última vez. "
        "Pode mostrar o usuário do Windows, o OneDrive da empresa ou um servidor. "
        "É indício de onde o arquivo foi montado, não prova de autoria."
    ),
    "HyperlinkBase": (
        "Pasta base dos hiperlinks (HyperlinkBase). "
        "Mostra onde o arquivo esperava achar os links. É indício, não prova."
    ),
    "Template": (
        "Modelo usado pelo arquivo (Template). "
        "O caminho pode identificar a máquina ou a pasta da empresa. É indício, não prova."
    ),
    "custom": (
        "Propriedade personalizada com caminho de pasta ou arquivo. "
        "É indício de onde o arquivo foi montado, não prova."
    ),
    "definedName": (
        "Nome definido com caminho de arquivo. O destino não foi aberto. É indício, não prova."
    ),
    "connection": (
        "Conexão de dados com caminho de arquivo, ODBC ou fonte. O caminho não foi aberto."
    ),
    "queryTable": (
        "Consulta da planilha (queryTable) com caminho de arquivo. O caminho não foi aberto."
    ),
    "powerQuery": (
        "Consulta Power Query (DataMashup) com caminho legível. A consulta não foi executada."
    ),
    "powerQuery-presente": (
        "Há uma consulta Power Query (DataMashup). Nenhum caminho ficou legível. "
        "A consulta não foi executada."
    ),
    "pivotCache": (
        "Tabela dinâmica aponta para outra planilha (pivotCache). O arquivo externo não foi aberto."
    ),
}


def text_has_path(value: str) -> bool:
    if not value:
        return False
    return bool(
        _DRIVE.search(value)
        or _UNC.search(value)
        or _UNC_SLASH.search(value)
        or _FILE_URL.search(value)
        or _SHAREPOINT.search(value)
    )


def _drop_paths(value: str) -> str:
    updated = _UNC.sub("", value)
    updated = _UNC_SLASH.sub("", updated)
    updated = _DRIVE.sub("", updated)
    updated = _FILE_URL.sub("", updated)
    return _SHAREPOINT.sub("", updated)


def scrub_path_text(value: str) -> tuple[str, bool]:
    """Drop path-shaped pieces. The rest of the text stays."""
    updated = _drop_paths(value)
    updated = re.sub(r"\s+", " ", updated).strip(" -;,")
    return updated, updated != value.strip()


def scrub_path_xml(value: str) -> tuple[str, bool]:
    """Drop paths in an XML part. Tags and other whitespace stay put."""
    updated = _drop_paths(value)
    return updated, updated != value


def mask_name(value: str) -> str:
    text = value.strip()
    if not text:
        return "*"
    if len(text) <= 2:
        return text[:1] + "*"
    return text[:2] + ("*" * min(len(text) - 2, 6))


def _local(tag: str) -> str:
    if tag.startswith("{"):
        return tag.rsplit("}", 1)[-1]
    return tag


def _attr(node, name: str) -> str:
    for key, value in node.attrib.items():
        if key == name or key.endswith("}" + name):
            if value and str(value).strip():
                return str(value).strip()
    return ""


def _parse(payload: bytes):
    try:
        return DefusedET.fromstring(payload)
    except (DefusedXmlException, SyntaxError):
        return None


def _split_path(path: str) -> tuple[str, list[str]]:
    text = path.strip().strip("\"'")
    lower = text.casefold()
    if lower.startswith("file:"):
        text = re.sub(r"(?i)^file:/+", "", text)
        if len(text) >= 3 and text[0] == "/" and text[2] == ":":
            text = text[1:]
    text = text.replace("\\", "/")
    if text.startswith("//"):
        return "//", [part for part in text.split("/") if part]
    if len(text) >= 2 and text[1] == ":":
        rest = text[2:].lstrip("/")
        return text[:2], [part for part in rest.split("/") if part]
    return "", [part for part in text.split("/") if part]


def _mask_part(part: str) -> str:
    match = _ONEDRIVE_DIR.match(part.strip())
    if match:
        return "OneDrive - " + mask_name(match.group(1).strip())
    if part.casefold() in _KNOWN:
        return part
    return mask_name(part)


def mask_save_path(path: str) -> str:
    """Keep the shape. Hide the user, the company and the deep folders."""
    prefix, parts = _split_path(path)
    if not parts and not prefix:
        return mask_name(path)
    shown = [_mask_part(part) for part in parts[:4]]
    if len(parts) > 4:
        shown.append("...")
    body = "/".join(shown)
    if prefix == "//":
        return "//" + body if body else "//*"
    if prefix:
        return prefix + "/" + body if body else prefix
    return body


def _windows_user(parts: list[str]) -> str:
    for index, part in enumerate(parts[:-1]):
        if not _USER_DIR.match(part):
            continue
        user = parts[index + 1].strip()
        if user.casefold() in _SKIP_USER or len(user) < 2:
            continue
        if _ONEDRIVE_DIR.match(user) or user.casefold() == "onedrive":
            continue
        return user
    return ""


def _company(path: str, parts: list[str]) -> str:
    for part in parts:
        match = _ONEDRIVE_DIR.match(part.strip())
        if match:
            name = match.group(1).strip()
            if name:
                return name
    found = _SHAREPOINT.search(path)
    if found:
        return found.group(1)
    return ""


def _risk(path: str, user: str, company: str) -> str:
    folded = path.casefold()
    if user or company or path.startswith("\\\\") or path.startswith("//") or "sharepoint" in folded:
        return "alto"
    if "onedrive" in folded:
        return "alto"
    return "medio"


def _trace(raw: str, source: str) -> SaveTrace | None:
    cleaned = raw.strip().strip("\"'")
    if not cleaned or not text_has_path(cleaned):
        return None
    _prefix, parts = _split_path(cleaned)
    user = _windows_user(parts)
    company = _company(cleaned, parts)
    return SaveTrace(raw=cleaned, source=source, user=user, company=company, risk=_risk(cleaned, user, company))


def _add(found: list[SaveTrace], seen: set[tuple[str, str]], raw: str, source: str) -> None:
    trace = _trace(raw, source)
    if trace is None:
        return
    key = (source, trace.raw.casefold())
    if key in seen:
        return
    seen.add(key)
    found.append(trace)


def _trim_path(value: str) -> str:
    text = value.strip().rstrip(" .,)'\"")
    bang = text.find("!")
    if bang > 2:
        text = text[:bang].rstrip(" .,)'\"")
    return text.rstrip(" \\/")


def _paths_in(text: str) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for pattern in (_UNC, _UNC_SLASH, _DRIVE):
        found.extend(_trim_path(match.group(0)) for match in pattern.finditer(text))
    for pattern in (_FILE_URL, _SHAREPOINT):
        found.extend(match.group(0).rstrip(".,)") for match in pattern.finditer(text))
    return [item for item in found if item]


def _from_xml_values(payload: bytes, source: str, found: list[SaveTrace], seen: set[tuple[str, str]]) -> None:
    root = _parse(payload)
    if root is None:
        return
    for node in root.iter():
        if node.text:
            for path in _paths_in(node.text):
                _add(found, seen, path, source)
        for value in node.attrib.values():
            for path in _paths_in(str(value)):
                _add(found, seen, path, source)


def _mashup_strings(payload: bytes) -> list[str]:
    root = _parse(payload)
    if root is None or "datamashup" not in DefusedET.tostring(root, encoding="unicode").casefold():
        return []
    texts = [DefusedET.tostring(root, encoding="unicode")]
    for node in root.iter():
        if _local(node.tag).casefold() != "datamashup":
            continue
        blob = (node.text or "").strip()
        if len(blob) < 16 or len(blob) > _MAX_MASHUP:
            continue
        try:
            decoded = base64.b64decode(blob, validate=False)
        except (ValueError, TypeError):
            continue
        if len(decoded) > _MAX_MASHUP:
            decoded = decoded[:_MAX_MASHUP]
        texts.append(decoded.decode("utf-8", errors="ignore"))
        texts.append(decoded.decode("utf-16-le", errors="ignore"))
    return texts


def collect_save_traces(parts: dict[str, bytes]) -> list[SaveTrace]:
    found: list[SaveTrace] = []
    seen: set[tuple[str, str]] = set()
    workbook = parts.get("xl/workbook.xml")
    if workbook:
        root = _parse(workbook)
        if root is not None:
            for node in root.iter():
                if _local(node.tag) == "absPath":
                    _add(found, seen, _attr(node, "url"), "absPath")
                elif _local(node.tag) == "definedName" and node.text:
                    for path in _paths_in(node.text):
                        _add(found, seen, path, "definedName")
    app = parts.get("docProps/app.xml")
    if app:
        root = _parse(app)
        if root is not None:
            for node in root.iter():
                local = _local(node.tag)
                text = (node.text or "").strip()
                if local.casefold() == "hyperlinkbase" and text:
                    _add(found, seen, text, "HyperlinkBase")
                elif local.casefold() == "template" and text:
                    _add(found, seen, text, "Template")
    custom = parts.get("docProps/custom.xml")
    if custom:
        _from_xml_values(custom, "custom", found, seen)
    for name, payload in parts.items():
        folded = name.casefold()
        if folded.endswith("connections.xml"):
            _from_xml_values(payload, "connection", found, seen)
        elif "querytable" in folded and folded.endswith(".xml"):
            _from_xml_values(payload, "queryTable", found, seen)
        elif "pivotcache" in folded and folded.endswith(".xml"):
            _from_xml_values(payload, "pivotCache", found, seen)
        elif "pivotcache" in folded and folded.endswith(".rels"):
            _from_xml_values(payload, "pivotCache", found, seen)
        elif folded.startswith("customxml/") and folded.endswith(".xml"):
            strings = _mashup_strings(payload)
            if not strings:
                continue
            readable = False
            for text in strings:
                for path in _paths_in(text):
                    readable = True
                    _add(found, seen, path, "powerQuery")
            if not readable:
                key = ("powerQuery-presente", "datamashup")
                if key not in seen:
                    seen.add(key)
                    found.append(
                        SaveTrace(
                            raw="DataMashup",
                            source="powerQuery-presente",
                            user="",
                            company="",
                            risk="info",
                        )
                    )
    return found


def evidence_text(trace: SaveTrace, *, show: bool) -> str:
    if trace.source == "powerQuery-presente":
        return "Power Query (DataMashup)"
    path = trace.raw if show else mask_save_path(trace.raw)
    lines = [path]
    if trace.user:
        lines.append("usuário: " + (trace.user if show else mask_name(trace.user)))
    if trace.company:
        lines.append("OneDrive/empresa: " + (trace.company if show else mask_name(trace.company)))
    return "\n".join(lines)


def save_findings(traces: list[SaveTrace], file_label: str) -> list[Finding]:
    findings: list[Finding] = []
    for trace in traces:
        findings.append(
            Finding(
                file=file_label,
                sheet="",
                cell=trace.source,
                rule="pasta-salva",
                type_label="Pasta onde foi salvo",
                risk=trace.risk,
                message=_MESSAGE.get(trace.source, _MESSAGE["absPath"]),
                evidence_masked=evidence_text(trace, show=False),
                evidence_raw=evidence_text(trace, show=True),
            )
        )
    return findings


def save_hints(traces: list[SaveTrace], file_label: str) -> list[NetworkHint]:
    hints: list[NetworkHint] = []
    for trace in traces:
        raw = trace.raw if trace.source != "powerQuery-presente" else "DataMashup"
        hints.append(
            NetworkHint(
                file=file_label,
                sheet="",
                cell=trace.source,
                kind="pasta",
                type_label="Pasta onde foi salvo",
                risk=trace.risk,
                message=_MESSAGE.get(trace.source, _MESSAGE["absPath"]),
                evidence_masked=evidence_text(trace, show=False),
                evidence_raw=evidence_text(trace, show=True) if trace.source != "powerQuery-presente" else raw,
                source=trace.source,
            )
        )
    return hints


def root_key(trace: SaveTrace) -> str:
    """A stable folder identity: user, company, UNC host, or the first folder."""
    if trace.source == "powerQuery-presente":
        return ""
    _prefix, parts = _split_path(trace.raw)
    if trace.user:
        return "user:" + trace.user.casefold()
    if trace.company:
        return "company:" + trace.company.casefold()
    if _prefix == "//" and parts:
        return "unc:" + parts[0].casefold()
    if parts:
        return "dir:" + parts[0].casefold()
    return ""


def primary_trace(traces: list[SaveTrace]) -> SaveTrace | None:
    for source in ("absPath", "HyperlinkBase", "Template", "connection", "pivotCache", "powerQuery"):
        for trace in traces:
            if trace.source == source:
                return trace
    for trace in traces:
        if trace.source != "powerQuery-presente":
            return trace
    return None

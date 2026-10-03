"""Internal-network map: users, UNC paths, SharePoint, printers, servers.

Signals are collected from text the workbook already exposes. Nothing is
resolved or contacted. A signal that an existing finding already covers at
the same or higher risk is shown in the map and is not added again.
"""

from __future__ import annotations

import re

from oculto_scan.masking import mask_ip, mask_piece, mask_unc, mask_url
from oculto_scan.models import RISK_RANK, Finding, NetworkHint, Workbook

_UNC = re.compile(r"\\\\[A-Za-z0-9._-]{1,63}(?:\\[^\s\"'<>\\|]{1,80})+")
_DRIVE = re.compile(r"[A-Za-z]:\\[^\s\"'<>|]{1,180}")
_USER_DIR = re.compile(r"(?i)(?:Users|Usuarios|Usuários)\\([^\\/\s\"']+)")
# The domain must not continue a path. A letter, digit, hyphen, dot or backslash
# before it means the pair is a segment, not DOMINIO\usuario.
_DOMAIN_USER = re.compile(
    r"(?<![A-Za-z0-9.\\-])([A-Za-z][A-Za-z0-9_-]{1,15})\\([A-Za-z][A-Za-z0-9._-]{1,32})\b"
)
_SHAREPOINT = re.compile(r"https?://[a-z0-9.-]*sharepoint\.com[^\s<>'\"]*", re.IGNORECASE)
_ONEDRIVE = re.compile(r"https?://[a-z0-9.-]*onedrive\.live\.com[^\s<>'\"]*", re.IGNORECASE)
_SERVER = re.compile(r"(?i)\b(?:data\s*source|server|servidor)\s*=\s*([^;\s,]+)")
_PRINTER_WORD = re.compile(r"(?i)impressora|printer")
_IP = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
_SKIP_USER = {"public", "default", "default user", "all users", "todos"}
_SKIP_DOMAIN = {
    "users",
    "usuarios",
    "windows",
    "program",
    "system",
    "appdata",
    "programdata",
    "arquivos",
    "desktop",
    "documents",
    "documentos",
    "downloads",
    "temp",
    "tmp",
    "onedrive",
}
_SKIP_HOST = {"localhost", "schemas", "www", "office", "microsoft"}

_LABEL = {
    "unc": "caminho UNC",
    "caminho": "caminho local",
    "usuario": "usuário",
    "sharepoint": "SharePoint/OneDrive",
    "impressora": "impressora",
    "maquina": "máquina",
}
_MESSAGE = {
    "unc": "Caminho de rede (\\\\servidor\\pasta). Mostra servidor e pasta internos.",
    "caminho": "Caminho de arquivo neste computador. A pasta pode identificar a máquina de quem montou o arquivo.",
    "usuario": "Usuário do Windows, em caminho pessoal ou no formato DOMINIO\\usuario.",
    "sharepoint": "Endereço de SharePoint ou OneDrive. O caminho interno fica oculto; o site (tenant) aparece no host.",
    "impressora": "Impressora ou fila de impressão da rede interna.",
    "maquina": "Nome de máquina ou servidor citado na planilha.",
}
_RISK = {
    "unc": "alto",
    "caminho": "medio",
    "usuario": "medio",
    "sharepoint": "medio",
    "impressora": "medio",
    "maquina": "medio",
}


def _hint(
    *,
    file_label: str,
    sheet: str,
    cell: str,
    source: str,
    kind: str,
    raw: str,
    masked: str,
    risk: str | None = None,
) -> NetworkHint:
    return NetworkHint(
        file=file_label,
        sheet=sheet,
        cell=cell,
        kind=kind,
        type_label=_LABEL[kind],
        risk=risk or _RISK[kind],
        message=_MESSAGE[kind],
        evidence_masked=masked,
        evidence_raw=raw,
        source=source,
    )


def _inside(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    """True when ``span`` sits inside a path already recorded."""
    start, end = span
    return any(left <= start and end <= right for left, right in spans)


def _host_of(unc: str) -> str:
    parts = [part for part in unc.replace("/", "\\").split("\\") if part]
    return parts[0] if parts else ""


def _skip_host(host: str) -> bool:
    folded = host.casefold().strip(".")
    if len(folded) < 3 or folded in _SKIP_HOST:
        return True
    if folded.endswith(".sharepoint.com") or folded.endswith(".live.com"):
        return True
    return False


def _from_text(text: str, *, file_label: str, sheet: str, cell: str, source: str) -> list[NetworkHint]:
    found: list[NetworkHint] = []
    if not text or not text.strip():
        return found

    def add(kind: str, raw: str, masked: str, *, risk: str | None = None) -> None:
        cleaned = raw.strip().strip("\"'")
        if not cleaned:
            return
        found.append(
            _hint(
                file_label=file_label,
                sheet=sheet,
                cell=cell,
                source=source,
                kind=kind,
                raw=cleaned,
                masked=masked,
                risk=risk,
            )
        )

    unc_spans: list[tuple[int, int]] = []
    for match in _UNC.finditer(text):
        unc_spans.append(match.span())
        raw = match.group(0)
        kind = "impressora" if _PRINTER_WORD.search(raw) else "unc"
        add(kind, raw, mask_unc(raw))
        host = _host_of(raw)
        if not _skip_host(host) and not _IP.fullmatch(host):
            add("maquina", host, mask_piece(host))
    for match in _DRIVE.finditer(text):
        raw = match.group(0)
        add("caminho", raw, mask_unc(raw))
    for match in _USER_DIR.finditer(text):
        user = match.group(1).strip()
        if user.casefold() in _SKIP_USER or len(user) < 2:
            continue
        add("usuario", user, mask_piece(user))
    for match in _DOMAIN_USER.finditer(text):
        if _inside(match.span(), unc_spans):
            continue
        domain, user = match.group(1), match.group(2)
        if domain.casefold() in _SKIP_DOMAIN:
            continue
        raw = f"{domain}\\{user}"
        add("usuario", raw, f"{mask_piece(domain)}\\{mask_piece(user)}")
    for pattern in (_SHAREPOINT, _ONEDRIVE):
        for match in pattern.finditer(text):
            raw = match.group(0).rstrip(").,;")
            # A path after the host names an internal site. The host alone is the tenant.
            risk = "alto" if raw.split("://", 1)[-1].find("/") > 0 else "medio"
            add("sharepoint", raw, mask_url(raw), risk=risk)
    for match in _SERVER.finditer(text):
        raw = match.group(1).strip().strip("\"'")
        if not raw or raw.startswith("\\") or "://" in raw:
            continue
        if _IP.fullmatch(raw):
            add("maquina", raw, mask_ip(raw))
        elif not _skip_host(raw):
            add("maquina", raw, mask_piece(raw))
    for match in _IP.finditer(text):
        raw = match.group(0)
        if raw.startswith("0.") or raw == "127.0.0.1":
            continue
        add("maquina", raw, mask_ip(raw))
    return found


def _spots_before(workbook: Workbook) -> list[tuple[str, str, str, str]]:
    spots: list[tuple[str, str, str, str]] = []
    for key, value in workbook.metadata.items():
        spots.append(("metadado", "", key, value))
    for link in workbook.external_links:
        spots.append(("vínculo", "", "", link))
    for name in workbook.defined_names:
        spots.append(("nome", name.local_sheet or "", name.name, name.formula))
    return spots


def _spots_sheet(sheet) -> list[tuple[str, str, str, str]]:
    spots: list[tuple[str, str, str, str]] = []
    for cell in sheet.cells:
        text = "\n".join(piece for piece in (cell.value, cell.formula) if piece)
        if text:
            spots.append(("célula", sheet.name, cell.ref, text))
    for comment in sheet.comments:
        if comment.text:
            spots.append(("comentário", sheet.name, comment.ref, comment.text))
    return spots


def _spots_after(workbook: Workbook, extra: list[tuple[str, str, str, str]]) -> list[tuple[str, str, str, str]]:
    spots: list[tuple[str, str, str, str]] = []
    for label, cell in workbook.external_cache:
        text = "\n".join(piece for piece in (cell.value, cell.formula) if piece)
        if text:
            spots.append(("vínculo", label, cell.ref, text))
    for text in workbook.connections:
        spots.append(("conexão", "", "", text))
    for text in workbook.printer_texts:
        spots.append(("impressora", "", "", text))
    for text in workbook.person_texts:
        spots.append(("pessoa", "", "", text))
    spots.extend(extra)
    return spots


def _spots(workbook: Workbook, extra: list[tuple[str, str, str, str]]) -> list[tuple[str, str, str, str]]:
    spots = _spots_before(workbook)
    for sheet in workbook.sheets:
        spots.extend(_spots_sheet(sheet))
    spots.extend(_spots_after(workbook, extra))
    return spots


def absorb_hints(
    spots: list[tuple[str, str, str, str]],
    *,
    file_label: str,
    hints: list[NetworkHint],
    seen: set[tuple[str, str, str, str]],
) -> None:
    for source, sheet, cell, text in spots:
        for hint in _from_text(text, file_label=file_label, sheet=sheet, cell=cell, source=source):
            key = (hint.kind, hint.evidence_raw.casefold(), hint.sheet, hint.cell)
            if key in seen:
                continue
            seen.add(key)
            hints.append(hint)


def collect_network(
    workbook: Workbook,
    file_label: str,
    extra: list[tuple[str, str, str, str]] | None = None,
) -> list[NetworkHint]:
    hints: list[NetworkHint] = []
    seen: set[tuple[str, str, str, str]] = set()
    absorb_hints(_spots(workbook, extra or []), file_label=file_label, hints=hints, seen=seen)
    return hints


def _contains(evidence: str, raw: str) -> bool:
    if evidence.casefold() == raw.casefold():
        return True
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(raw)}(?![A-Za-z0-9])", evidence, re.IGNORECASE) is not None


def promote_network(hints: list[NetworkHint], findings: list[Finding]) -> list[Finding]:
    """Add a finding only when no earlier finding already covers this value."""
    promoted: list[Finding] = []
    for hint in hints:
        covered = False
        for finding in [*findings, *promoted]:
            evidence = finding.evidence_raw or ""
            if not evidence or not _contains(evidence, hint.evidence_raw):
                continue
            same_cell = finding.cell == hint.cell or not finding.cell or not hint.cell
            same_place = finding.sheet == hint.sheet and same_cell
            if not same_place:
                continue
            if RISK_RANK.get(finding.risk, 0) >= RISK_RANK.get(hint.risk, 0):
                covered = True
                break
        hint.counted = not covered
        if covered:
            continue
        promoted.append(
            Finding(
                file=hint.file,
                sheet=hint.sheet,
                cell=hint.cell,
                rule="mapa-rede",
                type_label=hint.type_label,
                risk=hint.risk,
                message=hint.message,
                evidence_masked=hint.evidence_masked,
                evidence_raw=hint.evidence_raw,
            )
        )
    return promoted

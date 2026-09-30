"""Personal-data rules for construction workbooks.

CPF detection is delegated to tarja (check digit + Portuguese context).
A valid CPF without context is dropped: about one percent of random
11-digit numbers satisfy the check digit. Several contextual CPFs on the
same sheet are high risk (an employee list). CNPJ is informational.
Bank data is contextual only; there is no generic check digit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import tarja

from oculto_scan.masking import mask_account, mask_cnpj, mask_cpf, mask_pis, mask_text
from oculto_scan.models import Finding, Workbook

_CPF_CONTEXT = re.compile(
    r"(?i)(?:"
    r"\bcpf\b|c\.p\.f|"
    r"funcion[aá]ri[oa]s?|empregad[oa]s?|colaborador(?:es|a|as)?|"
    r"\bpis\b|\bpasep\b|\bnis\b|"
    r"sal[aá]rio|folha(?:\s+de\s+pagamento)?|trabalhador(?:es|a|as)?"
    r")"
)
_PIS_CONTEXT = re.compile(
    r"(?i)(?:\bpis\b|\bpasep\b|\bnis\b|funcion[aá]ri[oa]s?|empregad[oa]s?|sal[aá]rio|folha)"
)
_BANCO = re.compile(r"(?i)\bbanco\b")
_AGENCIA = re.compile(r"(?i)\bag[eê]ncia\b")
_CONTA = re.compile(r"(?i)\bcontas?(?:\s+corrente)?\b|\bc/c\b")
_AGENCIA_INLINE = re.compile(r"(?i)\bag[eê]ncia\b\s*[:\-]?\s*(\d{3,6})\b")
_CONTA_INLINE = re.compile(
    r"(?i)\bcontas?(?:\s+corrente)?\b\s*[:\-]?\s*(\d[\d.\-]{2,18})"
)
_ACCOUNT_VALUE = re.compile(r"^\d{3,14}(?:-\d)?$")
_BANK_CODE = re.compile(r"^\d{1,4}$")

_ENTITIES = ("BR_CPF", "BR_CNPJ", "BR_NIS")


@dataclass
class _Spot:
    sheet: str
    cell: str
    row: int | None
    col: int | None
    text: str
    context: str


@dataclass
class _IdHit:
    spot: _Spot
    entity: str
    raw: str
    contextual: bool


def _spots(workbook: Workbook) -> list[_Spot]:
    spots: list[_Spot] = []
    for sheet in workbook.sheets:
        headers: dict[int, list[str]] = {}
        left_label: dict[int, str] = {}
        for cell in sheet.cells:
            if cell.value and cell.row <= 3 and not _looks_numeric(cell.value):
                headers.setdefault(cell.col, []).append(cell.value)
            if cell.value and cell.col == 1 and not _looks_numeric(cell.value):
                left_label[cell.row] = cell.value
        for cell in sheet.cells:
            chunks = [piece for piece in (cell.value, cell.formula) if piece]
            if not chunks:
                continue
            header = " ".join(headers.get(cell.col, []))
            label = left_label.get(cell.row, "")
            spots.append(
                _Spot(
                    sheet=sheet.name,
                    cell=cell.ref,
                    row=cell.row,
                    col=cell.col,
                    text="\n".join(chunks),
                    context=" ".join((header, label, sheet.name)),
                )
            )
        for comment in sheet.comments:
            spots.append(
                _Spot(
                    sheet=sheet.name,
                    cell=comment.ref,
                    row=None,
                    col=None,
                    text=comment.text,
                    context=" ".join((comment.text, comment.author or "", sheet.name)),
                )
            )
    for key, value in workbook.metadata.items():
        spots.append(_Spot(sheet="", cell=key, row=None, col=None, text=value, context=key))
    return spots


def _looks_numeric(value: str) -> bool:
    compact = value.replace(".", "").replace(",", "").replace("-", "").strip()
    return compact.isdigit()


def _contextual(pattern: re.Pattern[str], spot: _Spot, tarja_context: bool) -> bool:
    return tarja_context or bool(pattern.search(spot.context)) or bool(pattern.search(spot.text))


def _collect(workbook: Workbook) -> list[_IdHit]:
    hits: list[_IdHit] = []
    for spot in _spots(workbook):
        if not spot.text or not spot.text.strip():
            continue
        matches = tarja.find(spot.text[:100_000], entities=_ENTITIES)
        for match in matches:
            if not match.valid_dv:
                continue
            entity = {"BR_CPF": "cpf", "BR_CNPJ": "cnpj", "BR_NIS": "pis"}.get(match.entity)
            if entity is None:
                continue
            if entity == "cpf":
                contextual = _contextual(_CPF_CONTEXT, spot, bool(match.has_context))
            elif entity == "pis":
                contextual = _contextual(_PIS_CONTEXT, spot, bool(match.has_context))
            else:
                contextual = True
            hits.append(_IdHit(spot=spot, entity=entity, raw=match.value, contextual=contextual))
    return hits


def _risk_for_group(entity: str, count: int) -> str:
    if entity == "cnpj":
        return "info"
    if count >= 2:
        return "alto"
    return "medio"


def personal_findings(workbook: Workbook, file_label: str) -> list[Finding]:
    hits = [hit for hit in _collect(workbook) if hit.contextual or hit.entity == "cnpj"]
    counts_sheet: dict[tuple[str, str], int] = {}
    counts_col: dict[tuple[str, str, int | None], int] = {}
    for hit in hits:
        if hit.entity == "cnpj":
            continue
        counts_sheet[(hit.spot.sheet, hit.entity)] = counts_sheet.get((hit.spot.sheet, hit.entity), 0) + 1
        counts_col[(hit.spot.sheet, hit.entity, hit.spot.col)] = (
            counts_col.get((hit.spot.sheet, hit.entity, hit.spot.col), 0) + 1
        )

    findings: list[Finding] = []
    seen: set[tuple[str, str, str, str]] = set()
    for hit in hits:
        key = (hit.entity, hit.spot.sheet, hit.spot.cell, hit.raw)
        if key in seen:
            continue
        seen.add(key)
        sheet_count = counts_sheet.get((hit.spot.sheet, hit.entity), 1)
        col_count = counts_col.get((hit.spot.sheet, hit.entity, hit.spot.col), 1)
        count = max(sheet_count, col_count)
        risk = _risk_for_group(hit.entity, count)
        findings.append(_finding(file_label, hit, risk, count))
    findings.extend(_bank_findings(workbook, file_label))
    return findings


def _finding(file_label: str, hit: _IdHit, risk: str, count: int) -> Finding:
    if hit.entity == "cpf":
        masked = mask_cpf(hit.raw)
        if count >= 2:
            message = (
                "Lista de CPFs com dígito verificador válido e contexto de pessoa "
                "(cabeçalho, rótulo ou texto como funcionário, PIS ou salário). "
                "Vários CPFs no mesmo lugar indicam relação de empregados."
            )
        else:
            message = (
                "CPF com dígito verificador válido e contexto de pessoa. "
                "Um número de 11 dígitos sem esse contexto é ignorado: "
                "cerca de 1% deles passa no dígito por acaso."
            )
        label = "CPF"
        rule = "cpf"
    elif hit.entity == "pis":
        masked = mask_pis(hit.raw)
        message = (
            "PIS/NIS/PASEP com dígito verificador válido e contexto de trabalhador. "
            "Pode fazer parte de folha ou medição com relação de empregados."
        )
        label = "PIS"
        rule = "pis"
    else:
        masked = mask_cnpj(hit.raw)
        message = (
            "CNPJ válido (numérico ou alfanumérico). Informativo: em proposta, "
            "medição e documento fiscal o CNPJ costuma ser obrigatório. "
            "O formato alfanumérico segue a IN RFB nº 2.229/2024; confira a norma antes de confiar no achado."
        )
        label = "CNPJ"
        rule = "cnpj"
    return Finding(
        file=file_label,
        sheet=hit.spot.sheet,
        cell=hit.spot.cell,
        rule=rule,
        type_label=label,
        risk=risk,
        message=message,
        evidence_masked=masked,
        evidence_raw=hit.raw,
    )


def _header_map(workbook: Workbook) -> dict[tuple[str, int], str]:
    headers: dict[tuple[str, int], str] = {}
    for sheet in workbook.sheets:
        buckets: dict[int, list[str]] = {}
        for cell in sheet.cells:
            if cell.row <= 3 and cell.value and not _looks_numeric(cell.value):
                buckets.setdefault(cell.col, []).append(cell.value)
        for col, parts in buckets.items():
            headers[(sheet.name, col)] = " ".join(parts)
    return headers


def _bank_findings(workbook: Workbook, file_label: str) -> list[Finding]:
    findings: list[Finding] = []
    headers = _header_map(workbook)
    seen: set[tuple[str, str, str]] = set()
    covered: set[tuple[str, str]] = set()
    for sheet in workbook.sheets:
        for cell in sheet.cells:
            if not cell.value:
                continue
            header = headers.get((sheet.name, cell.col), "")
            value = cell.value.strip()
            kind = _bank_kind(header, value)
            if kind is None:
                continue
            key = (sheet.name, cell.ref, kind)
            if key in seen:
                continue
            seen.add(key)
            covered.add((sheet.name, cell.ref))
            findings.append(_bank_finding(file_label, sheet.name, cell.ref, value, kind))
        inline_spots: list[tuple[str, str, str]] = [
            (sheet.name, comment.ref, comment.text) for comment in sheet.comments
        ]
        inline_spots.extend((sheet.name, cell.ref, cell.value or "") for cell in sheet.cells)
        for sheet_name, ref, text in inline_spots:
            if (sheet_name, ref) in covered:
                continue
            for kind, raw in _inline_bank(text):
                key = (sheet_name, ref, kind)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(_bank_finding(file_label, sheet_name, ref, raw, kind))
    return findings


def _bank_kind(header: str, value: str) -> str | None:
    if _CONTA.search(header) and _ACCOUNT_VALUE.match(value.replace(" ", "")):
        return "conta"
    if _AGENCIA.search(header) and _ACCOUNT_VALUE.match(value.replace(" ", "")):
        return "agencia"
    if _BANCO.search(header) and value and not _BANCO.search(value):
        if _BANK_CODE.match(value) or (not value.isdigit() and len(value) >= 3):
            return "banco"
    return None


def _inline_bank(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for match in _AGENCIA_INLINE.finditer(text or ""):
        found.append(("agencia", match.group(1)))
    for match in _CONTA_INLINE.finditer(text or ""):
        found.append(("conta", match.group(1)))
    return found


def _bank_finding(file_label: str, sheet: str, cell: str, raw: str, kind: str) -> Finding:
    risk = "medio" if kind == "banco" else "alto"
    label = {"banco": "banco", "agencia": "agência", "conta": "conta"}[kind]
    return Finding(
        file=file_label,
        sheet=sheet,
        cell=cell,
        rule="conta-bancaria",
        type_label="dado bancário",
        risk=risk,
        message=(
            f"Dado bancário identificado pelo rótulo «{label}». "
            "Não há validação genérica de dígito: cada banco usa a sua."
        ),
        evidence_masked=mask_account(raw) if kind != "banco" or raw.isdigit() else mask_text_bank(raw),
        evidence_raw=raw,
    )


def mask_text_bank(value: str) -> str:
    return mask_text(value)

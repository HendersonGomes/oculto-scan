"""Personal-data rules for construction workbooks.

CPF detection is delegated to tarja (check digit + Portuguese context).
A valid CPF without context is dropped: about one percent of random
11-digit numbers satisfy the check digit. Several contextual CPFs on the
same sheet are high risk (an employee list). CNPJ is informational.
Bank data is contextual only; there is no generic check digit.
"""

from __future__ import annotations

import bisect
import re
import time
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
# A column headed with one of these is not a CPF column, even if the sheet
# name or a label on the row would suggest it. Phone is not inferred from a
# leading 9: a valid CPF can look like that.
_CPF_CANCEL = re.compile(
    r"(?i)\b(?:tel|telefone|fone|celular|contato|whatsapp|c[oó]digos?|c[oó]d\.?|quantidades?)\b"
)
_LOOSE_DIGITS = re.compile(r"(?<!\d)(\d{10,11})(?!\d)")


@dataclass
class _Spot:
    sheet: str
    cell: str
    row: int | None
    col: int | None
    text: str
    context: str
    header: str | None = None
    cpf_blocked: bool = False


@dataclass
class _IdHit:
    spot: _Spot
    entity: str
    raw: str
    contextual: bool


def _text_cells(sheet_cells: list) -> list:
    return [cell for cell in sheet_cells if cell.value and not _looks_numeric(cell.value)]


class _LabelIndex:
    """Nearest text above or to the left, without scanning the whole sheet per cell.

    ``max()`` keeps the first cell when several share the winning row or column.
    The lists are sorted by coordinate, then by the original order, so the
    binary search can walk back to that first cell.
    """

    def __init__(self, cells: list) -> None:
        by_col: dict[int, list[tuple[int, int, str]]] = {}
        by_row: dict[int, list[tuple[int, int, str]]] = {}
        for index, cell in enumerate(cells):
            by_col.setdefault(cell.col, []).append((cell.row, index, cell.value))
            by_row.setdefault(cell.row, []).append((cell.col, index, cell.value))
        self._by_col = {key: sorted(items) for key, items in by_col.items()}
        self._by_row = {key: sorted(items) for key, items in by_row.items()}

    def header(self, col: int, row: int) -> str | None:
        column = self._by_col.get(col)
        if not column:
            return None
        pos = bisect.bisect_left(column, (row, -1, ""))
        if pos == 0:
            return None
        winner = column[pos - 1][0]
        start = pos - 1
        while start > 0 and column[start - 1][0] == winner:
            start -= 1
        return column[start][2]

    def left(self, col: int, row: int) -> str:
        line = self._by_row.get(row)
        if not line:
            return ""
        pos = bisect.bisect_left(line, (col, -1, ""))
        if pos == 0:
            return ""
        winner = line[pos - 1][0]
        start = pos - 1
        while start > 0 and line[start - 1][0] == winner:
            start -= 1
        return line[start][2]


def _pace(step: int, cancel) -> None:
    if step % 2000:
        return
    if cancel is not None and cancel():
        from oculto_scan.workbook import ScanCancelled

        raise ScanCancelled()
    time.sleep(0)


def _spots(
    workbook: Workbook,
    *,
    only_sheet=None,
    include_sheets: bool = True,
    include_meta: bool = True,
    cancel=None,
) -> list[_Spot]:
    spots: list[_Spot] = []
    sheets: list = []
    if include_sheets:
        sheets = [only_sheet] if only_sheet is not None else list(workbook.sheets)
    if include_meta and workbook.external_cache and only_sheet is None:
        from oculto_scan.models import Sheet

        sheets.append(
            Sheet(
                name="vínculo externo",
                state="visible",
                cells=[cell for _label, cell in workbook.external_cache],
            )
        )
    step = 0
    for sheet in sheets:
        labels = _LabelIndex(_text_cells(sheet.cells))
        for cell in sheet.cells:
            step += 1
            _pace(step, cancel)
            chunks = [piece for piece in (cell.value, cell.formula) if piece]
            if not chunks:
                continue
            header = labels.header(cell.col, cell.row) if cell.row else None
            if header:
                context = header
                blocked = bool(_CPF_CANCEL.search(header))
            else:
                label = labels.left(cell.col, cell.row) if cell.row else ""
                context = " ".join(piece for piece in (label, sheet.name) if piece)
                blocked = False
            spots.append(
                _Spot(
                    sheet=sheet.name,
                    cell=cell.ref,
                    row=cell.row,
                    col=cell.col,
                    text="\n".join(chunks),
                    context=context,
                    header=header,
                    cpf_blocked=blocked,
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
    if include_meta:
        for key, value in workbook.metadata.items():
            spots.append(_Spot(sheet="", cell=key, row=None, col=None, text=value, context=key))
    return spots


def _looks_numeric(value: str) -> bool:
    compact = value.replace(".", "").replace(",", "").replace("-", "").strip()
    return compact.isdigit()


def _contextual(pattern: re.Pattern[str], spot: _Spot, tarja_context: bool) -> bool:
    return tarja_context or bool(pattern.search(spot.context)) or bool(pattern.search(spot.text))


def _cpf_digits_ok(digits: str) -> bool:
    if len(digits) != 11 or not digits.isdigit() or digits == digits[0] * 11:
        return False

    def _dv(base: str) -> int:
        total = sum(int(char) * weight for char, weight in zip(base, range(len(base) + 1, 1, -1)))
        rest = total % 11
        return 0 if rest < 2 else 11 - rest

    return _dv(digits[:9]) == int(digits[9]) and _dv(digits[:10]) == int(digits[10])


def _collect(
    workbook: Workbook,
    *,
    only_sheet=None,
    include_sheets: bool = True,
    include_meta: bool = True,
    cancel=None,
) -> list[_IdHit]:
    hits: list[_IdHit] = []
    for spot in _spots(
        workbook,
        only_sheet=only_sheet,
        include_sheets=include_sheets,
        include_meta=include_meta,
        cancel=cancel,
    ):
        if not spot.text or not spot.text.strip():
            continue
        seen_digits: set[str] = set()
        matches = tarja.find(spot.text[:100_000], entities=_ENTITIES)
        for match in matches:
            if not match.valid_dv:
                continue
            entity = {"BR_CPF": "cpf", "BR_CNPJ": "cnpj", "BR_NIS": "pis"}.get(match.entity)
            if entity is None:
                continue
            if entity == "cpf":
                seen_digits.add(re.sub(r"\D", "", match.value))
                contextual = False if spot.cpf_blocked else _contextual(_CPF_CONTEXT, spot, bool(match.has_context))
            elif entity == "pis":
                contextual = _contextual(_PIS_CONTEXT, spot, bool(match.has_context))
            else:
                contextual = True
            hits.append(_IdHit(spot=spot, entity=entity, raw=match.value, contextual=contextual))
        if spot.cpf_blocked:
            continue
        contextual = _contextual(_CPF_CONTEXT, spot, False)
        if not contextual:
            continue
        for match in _LOOSE_DIGITS.finditer(spot.text):
            raw_digits = match.group(1)
            candidate = raw_digits if len(raw_digits) == 11 else "0" + raw_digits
            if candidate in seen_digits or not _cpf_digits_ok(candidate):
                continue
            seen_digits.add(candidate)
            shown = candidate if len(raw_digits) == 11 else raw_digits
            hits.append(_IdHit(spot=spot, entity="cpf", raw=shown, contextual=True))
    return hits


def _risk_for_group(entity: str, count: int) -> str:
    if entity == "cnpj":
        return "info"
    if count >= 2:
        return "alto"
    return "medio"


def personal_findings(
    workbook: Workbook,
    file_label: str,
    *,
    only_sheet=None,
    include_sheets: bool = True,
    include_meta: bool = True,
    cancel=None,
) -> list[Finding]:
    hits = [
        hit
        for hit in _collect(
            workbook,
            only_sheet=only_sheet,
            include_sheets=include_sheets,
            include_meta=include_meta,
            cancel=cancel,
        )
        if hit.contextual or hit.entity == "cnpj"
    ]
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
    if include_sheets:
        findings.extend(_bank_findings(workbook, file_label, only_sheet=only_sheet))
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


def _header_map(workbook: Workbook, *, only_sheet=None) -> dict[tuple[str, int, int], str]:
    """Nearest text above each content cell, keyed by sheet, column and row."""
    headers: dict[tuple[str, int, int], str] = {}
    sheets = [only_sheet] if only_sheet is not None else workbook.sheets
    for sheet in sheets:
        labels = _LabelIndex(_text_cells(sheet.cells))
        for cell in sheet.cells:
            header = labels.header(cell.col, cell.row)
            if header:
                headers[(sheet.name, cell.col, cell.row)] = header
    return headers


def _bank_findings(workbook: Workbook, file_label: str, *, only_sheet=None) -> list[Finding]:
    findings: list[Finding] = []
    headers = _header_map(workbook, only_sheet=only_sheet)
    seen: set[tuple[str, str, str]] = set()
    covered: set[tuple[str, str]] = set()
    sheets = [only_sheet] if only_sheet is not None else workbook.sheets
    for sheet in sheets:
        for cell in sheet.cells:
            if not cell.value:
                continue
            header = headers.get((sheet.name, cell.col, cell.row), "")
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

"""Turn a parsed workbook into findings. No I/O and no network."""

from __future__ import annotations

import re
import time
from pathlib import Path

from oculto_scan.formulas import (
    cell_is_visible,
    name_points_hidden,
    parse_formula,
    reference_is_hidden,
)
from oculto_scan.macros import inspect_vba
from oculto_scan.masking import mask_formula, mask_ip, mask_link, mask_secret, mask_text, mask_unc, mask_url
from oculto_scan.models import Finding, Workbook
from oculto_scan.network import (
    _spots_after,
    _spots_before,
    _spots_sheet,
    absorb_hints,
    collect_network,
    promote_network,
)
from oculto_scan.personal import personal_findings
from oculto_scan.refs import contiguous_groups, format_group, index_to_col, reference_axes
from oculto_scan.secrets import find_high_entropy, find_secrets
from oculto_scan.workbook import ScanCancelled, open_scan_session


def _pace(step: int, cancel) -> None:
    if step % 2000:
        return
    if cancel is not None and cancel():
        raise ScanCancelled()
    time.sleep(0)


_GUID = re.compile(r"^\{?[0-9a-fA-F-]{32,}\}?$")
# Excel stores the threaded-comment author as ``tc={GUID}`` on the legacy note.
_TC_AUTHOR = re.compile(r"(?i)^tc\s*=")
# Localized first line of that compatibility note. The rest of the wording varies.
_PLACEHOLDER_PREFIXES = (
    "[threaded comment]",
    "[comentário encadeado]",
    "[comentário em thread]",
    "[comentario encadenado]",
)

_IDENTITY = {"creator", "lastmodifiedby", "company", "manager"}
_CUSTOM_IDENTITY = ("empresa", "autor", "respons", "engenheir", "contato", "e-mail", "email")


def analyze(
    workbook: Workbook,
    file_label: str,
    *,
    entropy: bool = False,
    progress=None,
    cancel=None,
) -> list[Finding]:
    _drop_legacy_thread_placeholders(workbook)
    if progress is not None:
        progress("Analisando a planilha")
    findings: list[Finding] = []
    findings.extend(_structure(workbook, file_label))
    macro_findings, macro_texts = _macros(workbook, file_label)
    findings.extend(macro_findings)
    findings.extend(_formulas(workbook, file_label, cancel=cancel))
    findings.extend(personal_findings(workbook, file_label, cancel=cancel))
    findings.extend(_secrets(workbook, file_label, entropy=entropy, cancel=cancel))
    hints = collect_network(workbook, file_label, macro_texts)
    workbook.network_hints = hints
    findings.extend(promote_network(hints, findings))
    return _dedupe(findings)


def analyze_releasing(workbook: Workbook, fill, file_label: str, *, entropy: bool = False, progress=None, cancel=None):
    """Same rules as :func:`analyze`, dropping each sheet's cells after it is read.

    Hidden rows and columns of every sheet are already known. A formula on
    sheet 1 can still point at a hidden row on sheet 2.
    """
    _drop_legacy_thread_placeholders(workbook)
    findings: list[Finding] = []
    findings.extend(_structure(workbook, file_label, with_concealment=False))
    macro_findings, macro_texts = _macros(workbook, file_label)
    concealment: list[Finding] = []
    formulas: list[Finding] = []
    personal: list[Finding] = []
    banks: list[Finding] = []
    secrets: list[tuple[str, str, str]] = []
    hints: list = []
    seen: set[tuple[str, str, str, str]] = set()
    absorb_hints(_spots_before(workbook), file_label=file_label, hints=hints, seen=seen)
    total = len(workbook.sheets)
    for index, sheet in enumerate(workbook.sheets, start=1):
        if cancel is not None and cancel():
            raise ScanCancelled()
        if progress is not None:
            progress(f"Lendo aba {index} de {total} ({sheet.name})")
        fill(sheet)
        if progress is not None:
            progress(f"Analisando aba {index} de {total} ({sheet.name})")
        concealment.extend(_concealment_sheet(workbook, sheet, file_label))
        formulas.extend(_formulas_sheet(workbook, sheet, file_label, cancel=cancel))
        for finding in personal_findings(
            workbook,
            file_label,
            only_sheet=sheet,
            include_meta=False,
            cancel=cancel,
        ):
            if finding.rule == "conta-bancaria":
                banks.append(finding)
            else:
                personal.append(finding)
        secrets.extend(_secret_blobs_sheet(sheet))
        absorb_hints(_spots_sheet(sheet), file_label=file_label, hints=hints, seen=seen)
        sheet.cells.clear()
    findings.extend(concealment)
    findings.extend(macro_findings)
    findings.extend(formulas)
    findings.extend(personal)
    findings.extend(
        personal_findings(
            workbook,
            file_label,
            include_sheets=False,
            include_meta=True,
            cancel=cancel,
        )
    )
    findings.extend(banks)
    findings.extend(_secrets_from_blobs(secrets, file_label, entropy=entropy, cancel=cancel))
    findings.extend(_secrets_from_blobs(_secret_blobs_meta(workbook), file_label, entropy=entropy, cancel=cancel))
    absorb_hints(_spots_after(workbook, macro_texts), file_label=file_label, hints=hints, seen=seen)
    workbook.network_hints = hints
    findings.extend(promote_network(hints, findings))
    return _dedupe(findings)


def scan_path(
    path: Path,
    file_label: str,
    *,
    max_mb: int | None = None,
    entropy: bool = False,
    progress=None,
    cancel=None,
):
    """Scan one workbook from disk without keeping every sheet's cells at once."""
    session = open_scan_session(path, max_mb=max_mb, progress=progress, cancel=cancel)
    try:
        findings = analyze_releasing(
            session.workbook,
            session.fill,
            file_label,
            entropy=entropy,
            progress=progress,
            cancel=cancel,
        )
        return findings, list(session.workbook.network_hints)
    finally:
        session.close()


def _author_label(author: str | None) -> str:
    if not author:
        return ""
    stripped = author.strip()
    if _GUID.match(stripped) or _is_tc_author(stripped):
        return ""
    return mask_text(stripped)


def _cell_key(ref: str) -> str:
    return ref.replace("$", "").casefold()


def _is_tc_author(author: str | None) -> bool:
    return bool(author and _TC_AUTHOR.match(author.strip()))


def _is_thread_placeholder(text: str) -> bool:
    folded = (text or "").lstrip().casefold()
    return any(folded.startswith(prefix) for prefix in _PLACEHOLDER_PREFIXES)


def _drop_legacy_thread_placeholders(workbook: Workbook) -> None:
    """Drop Excel's legacy compatibility note when a real thread exists.

    A threaded comment is stored twice: the thread, and a legacy note whose
    author is ``tc={GUID}``. The note text starts with ``[Threaded comment]``
    in English, ``[Comentário encadeado]`` in pt-BR, ``[Comentário em thread]``
    in pt-PT, or ``[Comentario encadenado]`` in Spanish. The author plus a
    thread on the same cell is enough to treat it as that duplicate. A legacy
    note with its own author and its own text stays.
    """
    for sheet in workbook.sheets:
        thread_cells = {_cell_key(item.ref) for item in sheet.comments if item.kind == "thread" and item.ref}
        if not thread_cells:
            continue
        sheet.comments = [
            item
            for item in sheet.comments
            if not (
                item.kind == "nota"
                and item.ref
                and _cell_key(item.ref) in thread_cells
                and (_is_tc_author(item.author) or _is_thread_placeholder(item.text))
            )
        ]


def _macros(workbook: Workbook, file_label: str) -> tuple[list[Finding], list[tuple[str, str, str, str]]]:
    """Read VBA without running it. Returns findings and texts for the network map."""
    if not workbook.has_vba:
        return [], []
    report = inspect_vba(workbook.vba_bytes or b"")
    findings: list[Finding] = []
    texts: list[tuple[str, str, str, str]] = []
    if report.status == "missing":
        findings.append(
            Finding(
                file=file_label,
                sheet="",
                cell="",
                rule="macro",
                type_label="macro",
                risk="medio",
                message=(
                    "A pasta contém macro (vbaProject.bin). "
                    "O código não foi analisado porque o extra oletools não está instalado. "
                    "Nada foi executado."
                ),
                evidence_masked="vbaProject.bin",
                evidence_raw=None,
            )
        )
        findings.append(
            Finding(
                file=file_label,
                sheet="",
                cell="",
                rule="nao-analisado",
                type_label="não analisado",
                risk="info",
                message=(
                    "Não analisado: macro presente e o extra de leitura não está instalado. "
                    "Instale com: pip install oculto-scan[macro]. "
                    "A macro não foi executada e nenhuma senha foi testada."
                ),
                evidence_masked="vbaProject.bin",
                evidence_raw=None,
            )
        )
        return findings, texts
    if report.status != "ok":
        findings.append(
            Finding(
                file=file_label,
                sheet="",
                cell="",
                rule="macro",
                type_label="macro",
                risk="medio",
                message=(
                    "A pasta contém macro (vbaProject.bin), mas o projeto VBA não pôde ser lido. "
                    "Nada foi executado e nenhuma senha foi testada."
                ),
                evidence_masked="vbaProject.bin",
                evidence_raw=None,
            )
        )
        findings.append(
            Finding(
                file=file_label,
                sheet="",
                cell="",
                rule="nao-analisado",
                type_label="não analisado",
                risk="info",
                message=(
                    "Não analisado: projeto VBA ilegível. "
                    "A senha do editor não foi testada e a macro não foi executada."
                ),
                evidence_masked="vbaProject.bin",
                evidence_raw=None,
            )
        )
        return findings, texts

    names = ", ".join(name for name, _source in report.modules)
    findings.append(
        Finding(
            file=file_label,
            sheet="",
            cell="",
            rule="macro",
            type_label="macro",
            risk="medio",
            message=(
                f"Macro lida sem executar. Módulos: {names}. "
                "A senha do editor VBA não foi testada."
            ),
            evidence_masked=names,
            evidence_raw=names,
        )
    )
    for word, risk, line in report.keywords:
        findings.append(
            Finding(
                file=file_label,
                sheet="",
                cell="",
                rule="macro-suspeita",
                type_label="macro suspeita",
                risk=risk,
                message=(
                    f"A macro cita {word}. Isso pode abrir outro programa ou baixar arquivo. "
                    "O oculto-scan não executou a macro."
                ),
                evidence_masked=word,
                evidence_raw=line,
            )
        )
    for kind, raw, risk in report.iocs:
        if kind == "url":
            masked = mask_url(raw)
            label = "endereço na macro"
        elif kind == "ip":
            masked = mask_ip(raw)
            label = "IP na macro"
        else:
            masked = mask_unc(raw)
            label = "caminho na macro"
        findings.append(
            Finding(
                file=file_label,
                sheet="",
                cell="",
                rule="macro-ioc",
                type_label=label,
                risk=risk,
                message="Indicador na macro (endereço, IP ou caminho). Nada foi acessado nem executado.",
                evidence_masked=masked,
                evidence_raw=raw,
            )
        )
    for name, source in report.modules:
        texts.append(("macro", "", name, source))
    return findings, texts


def _dedupe(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, str, str, str, str]] = set()
    unique: list[Finding] = []
    for finding in findings:
        key = (
            finding.rule,
            finding.sheet,
            finding.cell,
            finding.evidence_raw or "",
            finding.message,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


def _structure(workbook: Workbook, file_label: str, *, with_concealment: bool = True) -> list[Finding]:
    findings: list[Finding] = []
    for sheet in workbook.sheets:
        if sheet.state == "hidden":
            findings.append(
                Finding(
                    file=file_label,
                    sheet=sheet.name,
                    cell="",
                    rule="aba-oculta",
                    type_label="aba oculta",
                    risk="alto",
                    message=(
                        "Aba oculta. Em proposta, orçamento ou edital isso costuma "
                        "esconder custo, margem ou memória de cálculo, e o destinatário "
                        "revela a aba com um clique."
                    ),
                )
            )
        elif sheet.state == "veryHidden":
            findings.append(
                Finding(
                    file=file_label,
                    sheet=sheet.name,
                    cell="",
                    rule="aba-muito-oculta",
                    type_label="aba muito oculta",
                    risk="alto",
                    message=(
                        "Aba muito oculta (very hidden). Não aparece na lista de abas; "
                        "só sai desse estado por VBA ou pelo editor de XML. "
                        "Sinal forte de conteúdo que não deveria seguir com o arquivo."
                    ),
                )
            )
        for start, end in contiguous_groups(sheet.hidden_rows) + list(sheet.hidden_row_spans):
            findings.append(
                Finding(
                    file=file_label,
                    sheet=sheet.name,
                    cell=format_group(start, end),
                    rule="linha-oculta",
                    type_label="linha oculta",
                    risk="medio",
                    message=(
                        "Linha ou faixa de linhas oculta. Pode guardar quantidade, "
                        "custo unitário ou margem fora da área impressa."
                    ),
                )
            )
        for start, end in contiguous_groups(sheet.hidden_cols) + list(sheet.hidden_col_spans):
            findings.append(
                Finding(
                    file=file_label,
                    sheet=sheet.name,
                    cell=f"{index_to_col(start)}:{index_to_col(end)}",
                    rule="coluna-oculta",
                    type_label="coluna oculta",
                    risk="medio",
                    message=(
                        "Coluna ou faixa de colunas oculta. Em planilha de preço "
                        "isso é um lugar típico de custo e BDI."
                    ),
                )
            )
        for comment in sheet.comments:
            kind = "nota antiga" if comment.kind == "nota" else "comentário em thread"
            author = _author_label(comment.author)
            author_bit = f" Autor: {author}." if author else ""
            findings.append(
                Finding(
                    file=file_label,
                    sheet=sheet.name,
                    cell=comment.ref,
                    rule="comentario" if comment.kind == "nota" else "comentario-thread",
                    type_label="comentário",
                    risk="medio",
                    message=(
                        f"Há {kind} nesta célula.{author_bit} "
                        "Comentário interno muitas vezes descreve margem, premissa ou ressalva "
                        "que não está na célula visível."
                    ),
                    evidence_masked=f"texto mascarado ({len(comment.text)} caracteres)",
                    evidence_raw=comment.text,
                )
            )

    known_names = {item.name for item in workbook.defined_names}
    for defined in workbook.defined_names:
        info = parse_formula(defined.formula, known_names)
        target = name_points_hidden(workbook, defined.name)
        external = bool(info.external) or bool(target and ("\\" in target or target.startswith("[")))
        points_hidden = bool(target) and not external
        if points_hidden or external:
            shown = target or (info.external[0] if info.external else defined.formula)
            findings.append(
                Finding(
                    file=file_label,
                    sheet=defined.local_sheet or "",
                    cell=defined.name,
                    rule="nome-definido-oculto",
                    type_label="nome definido",
                    risk="alto",
                    message=(
                        "Nome definido aponta para área oculta ou para outra pasta. "
                        "Uma célula visível pode usar esse nome sem mostrar a origem."
                    ),
                    evidence_masked=mask_link(mask_formula(shown)),
                    evidence_raw=defined.formula,
                )
            )
        elif defined.hidden:
            findings.append(
                Finding(
                    file=file_label,
                    sheet=defined.local_sheet or "",
                    cell=defined.name,
                    rule="nome-definido",
                    type_label="nome definido",
                    risk="medio",
                    message="Nome definido oculto. O nome não aparece no gerenciador de nomes.",
                    evidence_masked=mask_formula(defined.formula),
                    evidence_raw=defined.formula,
                )
            )
        else:
            findings.append(
                Finding(
                    file=file_label,
                    sheet=defined.local_sheet or "",
                    cell=defined.name,
                    rule="nome-definido",
                    type_label="nome definido",
                    risk="info",
                    message="Nome definido na pasta. Confira se o destino pode ser enviado.",
                    evidence_masked=mask_formula(defined.formula),
                    evidence_raw=defined.formula,
                )
            )

    for link in workbook.external_links:
        findings.append(
            Finding(
                file=file_label,
                sheet="",
                cell="",
                rule="vinculo-externo",
                type_label="vínculo externo",
                risk="alto",
                message=(
                    "Vínculo externo ou hiperlink para outro arquivo. "
                    "Caminhos locais (C:\\Users\\...) identificam a máquina e podem "
                    "apontar para uma planilha de custo que não deveria sair."
                ),
                evidence_masked=mask_link(link),
                evidence_raw=link,
            )
        )

    for key, value in workbook.metadata.items():
        folded = key.casefold()
        base = folded.split(":", 1)[-1]
        identity = folded in _IDENTITY or any(token in folded or token in base for token in _CUSTOM_IDENTITY)
        email = "@" in value and "email" in folded
        findings.append(
            Finding(
                file=file_label,
                sheet="",
                cell=key,
                rule="metadado",
                type_label="metadado",
                risk="medio" if identity else "info",
                message=(
                    "E-mail de quem comentou, lido de persons.xml. "
                    "Identifica a pessoa mesmo quando o comentário não mostra o endereço."
                    if email
                    else (
                        "Metadado do arquivo. Autor, empresa e último editor identificam "
                        "quem preparou a proposta e, entre licitantes, são indício de "
                        "autoria compartilhada — não prova de conluio."
                        if identity
                        else "Metadado descritivo do arquivo (título, assunto ou semelhante)."
                    )
                ),
                evidence_masked=f"e-mail ({len(value)} caracteres)" if email else mask_text(value),
                evidence_raw=value,
            )
        )
    if with_concealment:
        findings.extend(_concealment(workbook, file_label))
    return findings


_HIDDEN_FORMATS = {";;;", ";;;@"}


def _format_hides(code: str | None) -> bool:
    if not code:
        return False
    return code.replace(" ", "").replace("\\", "") in _HIDDEN_FORMATS


def _inside_print(areas: list[tuple[int, int, int, int]], row: int, col: int) -> bool:
    return any(r1 <= row <= r2 and c1 <= col <= c2 for r1, c1, r2, c2 in areas)


def _ref_outside(ref: str, areas: list[tuple[int, int, int, int]]) -> bool:
    axes = reference_axes(ref)
    if axes is None:
        return False
    rows, cols = axes
    if rows is None or cols is None:
        return True
    r1, r2 = rows
    c1, c2 = cols

    def covered(row: int, col: int) -> bool:
        return _inside_print(areas, row, col)

    return not (covered(r1, c1) and covered(r2, c2) and covered(r1, c2) and covered(r2, c1))


def _concealment(workbook: Workbook, file_label: str) -> list[Finding]:
    """Content hidden without the Hide command: format, size, or print area."""
    findings: list[Finding] = []
    for sheet in workbook.sheets:
        findings.extend(_concealment_sheet(workbook, sheet, file_label))
    return findings


def _concealment_sheet(workbook: Workbook, sheet, file_label: str) -> list[Finding]:
    findings: list[Finding] = []
    areas = sheet.print_areas
    for cell in sheet.cells:
        has_content = bool((cell.value and str(cell.value).strip()) or cell.formula)
        if not has_content:
            continue
        if _format_hides(cell.number_format):
            findings.append(
                Finding(
                    file=file_label,
                    sheet=sheet.name,
                    cell=cell.ref,
                    rule="formato-oculto",
                    type_label="formato oculto",
                    risk="alto",
                    message=(
                        "Formato numérico com as seções vazias (;;; ou ;;;@). "
                        "A célula tem conteúdo, mas a tela e a impressão ficam em branco."
                    ),
                    evidence_masked=cell.number_format,
                    evidence_raw=cell.value or cell.formula,
                )
            )
        if cell.col in sheet.narrow_cols:
            findings.append(
                Finding(
                    file=file_label,
                    sheet=sheet.name,
                    cell=cell.ref,
                    rule="largura-minima",
                    type_label="coluna estreita",
                    risk="medio",
                    message=(
                        "Coluna com largura perto de zero e com conteúdo. "
                        "Não usa o comando Ocultar, mas some na tela."
                    ),
                )
            )
        if cell.row in sheet.short_rows:
            findings.append(
                Finding(
                    file=file_label,
                    sheet=sheet.name,
                    cell=cell.ref,
                    rule="altura-minima",
                    type_label="linha baixa",
                    risk="medio",
                    message=(
                        "Linha com altura perto de zero e com conteúdo. "
                        "Não usa o comando Ocultar, mas some na tela."
                    ),
                )
            )
        if areas is not None and cell.row and cell.col and not _inside_print(areas, cell.row, cell.col):
            findings.append(
                Finding(
                    file=file_label,
                    sheet=sheet.name,
                    cell=cell.ref,
                    rule="fora-impressao",
                    type_label="fora da impressão",
                    risk="medio",
                    message=(
                        "Célula com conteúdo fora da área de impressão. "
                        "Quem imprime ou exporta PDF não vê esse valor."
                    ),
                )
            )
        if cell.formula and cell_is_visible(sheet, cell.row, cell.col):
            info = parse_formula(cell.formula, {item.name for item in workbook.defined_names})
            outside = False
            for target_name, ref in info.sheet_refs:
                target = workbook.sheet_by_name(target_name)
                if (
                    target is not None
                    and target.print_areas is not None
                    and ref
                    and _ref_outside(ref, target.print_areas)
                ):
                    outside = True
            if sheet.print_areas is not None:
                for ref in info.local_refs:
                    if _ref_outside(ref, sheet.print_areas):
                        outside = True
            if outside:
                findings.append(
                    Finding(
                        file=file_label,
                        sheet=sheet.name,
                        cell=cell.ref,
                        rule="formula-fora-impressao",
                        type_label="fórmula fora da impressão",
                        risk="alto",
                        message=(
                            "Fórmula visível que puxa valor de fora da área de impressão. "
                            "O número aparece, mas a origem não sai na impressão."
                        ),
                        evidence_masked=mask_formula(cell.formula),
                        evidence_raw=cell.formula,
                    )
                )
    return findings


def _formulas(workbook: Workbook, file_label: str, *, cancel=None) -> list[Finding]:
    findings: list[Finding] = []
    for sheet in workbook.sheets:
        findings.extend(_formulas_sheet(workbook, sheet, file_label, cancel=cancel))
    return findings


def _formulas_sheet(workbook: Workbook, sheet, file_label: str, *, cancel=None) -> list[Finding]:
    names = {item.name for item in workbook.defined_names}
    findings: list[Finding] = []
    for step, cell in enumerate(sheet.cells, start=1):
        _pace(step, cancel)
        if not cell.formula or not cell_is_visible(sheet, cell.row, cell.col):
            continue
        info = parse_formula(cell.formula, names)
        if info.external:
            findings.append(
                Finding(
                    file=file_label,
                    sheet=sheet.name,
                    cell=cell.ref,
                    rule="formula-vinculo-externo",
                    type_label="fórmula externa",
                    risk="alto",
                    message=(
                        "Célula visível com fórmula que referencia outra pasta de trabalho. "
                        "O valor pode depender de um arquivo que não será enviado, "
                        "ou o caminho pode identificar o autor."
                    ),
                    evidence_masked=mask_link(mask_formula(cell.formula)),
                    evidence_raw=cell.formula,
                )
            )
        hidden: list[str] = []
        for target_sheet, ref in info.sheet_refs:
            if reference_is_hidden(workbook, target_sheet, ref):
                hidden.append(f"{target_sheet}!{ref}" if ref else target_sheet)
        for ref in info.local_refs:
            if reference_is_hidden(workbook, sheet.name, ref):
                hidden.append(f"{sheet.name}!{ref}")
        for name in info.names:
            target = name_points_hidden(workbook, name)
            if target and "\\" not in target and not target.startswith("["):
                hidden.append(f"{name} → {target}")
        for literal in info.string_literals:
            for other in workbook.sheets:
                if other.visible:
                    continue
                if other.name and other.name.casefold() in literal.casefold():
                    hidden.append(f"texto:{other.name}")
        if hidden:
            findings.append(
                Finding(
                    file=file_label,
                    sheet=sheet.name,
                    cell=cell.ref,
                    rule="formula-referencia-oculta",
                    type_label="fórmula oculta",
                    risk="alto",
                    message=(
                        "Célula visível cuja fórmula referencia aba, linha ou coluna oculta "
                        f"({', '.join(hidden[:4])}). O número mostrado pode depender de "
                        "custo ou margem que não aparece na impressão."
                    ),
                    evidence_masked=mask_formula(cell.formula),
                    evidence_raw=cell.formula,
                )
            )
        if info.constants:
            shown = ", ".join(info.constants[:6])
            findings.append(
                Finding(
                    file=file_label,
                    sheet=sheet.name,
                    cell=cell.ref,
                    rule="formula-constante",
                    type_label="constante",
                    risk="info",
                    message=(
                        "Fórmula com constante numérica. Pode revelar o método de margem "
                        "ou BDI (por exemplo um fator multiplicando o custo). "
                        "É informativo: constante sozinha não prova vazamento."
                    ),
                    evidence_masked=mask_formula(cell.formula),
                    evidence_raw=cell.formula if shown else None,
                )
            )
    return findings


def _secret_blobs_sheet(sheet) -> list[tuple[str, str, str]]:
    blobs: list[tuple[str, str, str]] = []
    for cell in sheet.cells:
        text = "\n".join(piece for piece in (cell.value, cell.formula) if piece)
        if text:
            blobs.append((sheet.name, cell.ref, text))
    for comment in sheet.comments:
        if comment.text:
            blobs.append((sheet.name, comment.ref, comment.text))
    return blobs


def _secret_blobs_meta(workbook: Workbook) -> list[tuple[str, str, str]]:
    blobs: list[tuple[str, str, str]] = []
    for label, cell in workbook.external_cache:
        text = "\n".join(piece for piece in (cell.value, cell.formula) if piece)
        if text:
            blobs.append((label, cell.ref, text))
    for key, value in workbook.metadata.items():
        blobs.append(("", key, value))
    return blobs


def _secrets(workbook: Workbook, file_label: str, *, entropy: bool, cancel=None) -> list[Finding]:
    blobs: list[tuple[str, str, str]] = []
    for sheet in workbook.sheets:
        blobs.extend(_secret_blobs_sheet(sheet))
    blobs.extend(_secret_blobs_meta(workbook))
    return _secrets_from_blobs(blobs, file_label, entropy=entropy, cancel=cancel)


def _secrets_from_blobs(
    blobs: list[tuple[str, str, str]],
    file_label: str,
    *,
    entropy: bool,
    cancel=None,
) -> list[Finding]:
    findings: list[Finding] = []
    for step, (sheet, cell, text) in enumerate(blobs, start=1):
        _pace(step, cancel)
        for hit in find_secrets(text):
            findings.append(
                Finding(
                    file=file_label,
                    sheet=sheet,
                    cell=cell,
                    rule="segredo",
                    type_label="segredo",
                    risk="alto",
                    message=(
                        f"Possível segredo ({hit.rule}). Chave, token ou senha não devem "
                        "viajar dentro de proposta, medição ou laudo."
                    ),
                    evidence_masked=mask_secret(hit.value),
                    evidence_raw=hit.value,
                )
            )
        if entropy:
            known = {hit.value for hit in find_secrets(text)}
            for token in find_high_entropy(text):
                if token in known:
                    continue
                findings.append(
                    Finding(
                        file=file_label,
                        sheet=sheet,
                        cell=cell,
                        rule="entropia",
                        type_label="entropia",
                        risk="info",
                        message=(
                            "Trecho de entropia alta. A detecção por entropia está desligada "
                            "por padrão e gera falso positivo; este achado só aparece com --entropy."
                        ),
                        evidence_masked=mask_secret(token),
                        evidence_raw=token,
                    )
                )
    return findings

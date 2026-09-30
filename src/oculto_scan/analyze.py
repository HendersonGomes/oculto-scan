"""Turn a parsed workbook into findings. No I/O and no network."""

from __future__ import annotations

import re

from oculto_scan.formulas import (
    cell_is_visible,
    name_points_hidden,
    parse_formula,
    reference_is_hidden,
)
from oculto_scan.masking import mask_formula, mask_path, mask_secret, mask_text
from oculto_scan.models import Finding, Workbook
from oculto_scan.personal import personal_findings
from oculto_scan.refs import contiguous_groups, format_group, index_to_col
from oculto_scan.secrets import find_high_entropy, find_secrets

_GUID = re.compile(r"^\{?[0-9a-fA-F-]{32,}\}?$")

_IDENTITY = {"creator", "lastmodifiedby", "company", "manager"}
_CUSTOM_IDENTITY = ("empresa", "autor", "respons", "engenheir", "contato", "e-mail", "email")


def analyze(workbook: Workbook, file_label: str, *, entropy: bool = False) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(_structure(workbook, file_label))
    findings.extend(_formulas(workbook, file_label))
    findings.extend(personal_findings(workbook, file_label))
    findings.extend(_secrets(workbook, file_label, entropy=entropy))
    return _dedupe(findings)


def _author_label(author: str | None) -> str:
    if not author or _GUID.match(author.strip()):
        return ""
    return mask_text(author)


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


def _structure(workbook: Workbook, file_label: str) -> list[Finding]:
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
        for start, end in contiguous_groups(sheet.hidden_rows):
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
        for start, end in contiguous_groups(sheet.hidden_cols):
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
                    evidence_masked=mask_path(mask_formula(shown)),
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
                evidence_masked=mask_path(link),
                evidence_raw=link,
            )
        )

    if workbook.has_vba:
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
                    "O oculto-scan não executa e não descompila macro; só registra a presença."
                ),
                evidence_masked="vbaProject.bin",
                evidence_raw=None,
            )
        )

    for key, value in workbook.metadata.items():
        folded = key.casefold()
        base = folded.split(":", 1)[-1]
        identity = folded in _IDENTITY or any(token in base for token in _CUSTOM_IDENTITY)
        findings.append(
            Finding(
                file=file_label,
                sheet="",
                cell=key,
                rule="metadado",
                type_label="metadado",
                risk="medio" if identity else "info",
                message=(
                    "Metadado do arquivo. Autor, empresa e último editor identificam "
                    "quem preparou a proposta e, entre licitantes, são indício de "
                    "autoria compartilhada — não prova de conluio."
                    if identity
                    else "Metadado descritivo do arquivo (título, assunto ou semelhante)."
                ),
                evidence_masked=mask_text(value),
                evidence_raw=value,
            )
        )
    return findings


def _formulas(workbook: Workbook, file_label: str) -> list[Finding]:
    names = {item.name for item in workbook.defined_names}
    findings: list[Finding] = []
    for sheet in workbook.sheets:
        for cell in sheet.cells:
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
                        evidence_masked=mask_path(mask_formula(cell.formula)),
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


def _secrets(workbook: Workbook, file_label: str, *, entropy: bool) -> list[Finding]:
    findings: list[Finding] = []
    blobs: list[tuple[str, str, str]] = []
    for sheet in workbook.sheets:
        for cell in sheet.cells:
            text = "\n".join(piece for piece in (cell.value, cell.formula) if piece)
            if text:
                blobs.append((sheet.name, cell.ref, text))
        for comment in sheet.comments:
            if comment.text:
                blobs.append((sheet.name, comment.ref, comment.text))
    for key, value in workbook.metadata.items():
        blobs.append(("", key, value))

    for sheet, cell, text in blobs:
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

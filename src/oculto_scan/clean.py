"""Write a cleaned copy of an .xlsx or .xlsm package.

The source bytes are only read. Comments, identity metadata, personal
custom properties, and external links come out by default. Hidden sheets,
rows, and columns stay unless the caller asks: deleting them can break a
formula that still points there. Cell values that look like CPF, CNPJ, or
a secret are never rewritten.
"""

from __future__ import annotations

import hashlib
import html
import io
import json
import os
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import tarja

from oculto_scan.formulas import parse_formula, reference_is_hidden
from oculto_scan.models import DefinedName, Finding, Workbook
from oculto_scan.refs import split_cell
from oculto_scan.report import summary
from oculto_scan.workbook import (
    WorkbookParseError,
    _attr,
    _local,
    _parse_rels,
    _parse_xml,
    _resolve,
    _truthy,
    load_workbook_bytes,
)
from oculto_scan.zipsafe import open_office_bytes, read_member

_XLSX_MAIN = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"

_PREFERRED = {
    "http://schemas.openxmlformats.org/spreadsheetml/2006/main": "",
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships": "r",
    "http://schemas.openxmlformats.org/package/2006/relationships": "",
    "http://schemas.openxmlformats.org/package/2006/content-types": "",
    "http://schemas.openxmlformats.org/package/2006/metadata/core-properties": "cp",
    "http://purl.org/dc/elements/1.1/": "dc",
    "http://purl.org/dc/terms/": "dcterms",
    "http://www.w3.org/2001/XMLSchema-instance": "xsi",
    "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties": "",
    "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties": "",
    "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes": "vt",
    "http://schemas.microsoft.com/office/spreadsheetml/2018/threadedcomments": "",
}
_XML_NS = "http://www.w3.org/XML/1998/namespace"
_CLEAR_META = {
    "creator",
    "lastmodifiedby",
    "lastprinted",
    "revision",
    "created",
    "modified",
    "company",
    "manager",
    "hyperlinkbase",
}
_UNC = re.compile(r"\\\\[^\s\"'<>]+")
_DRIVE = re.compile(r"(?i)[A-Za-z]:\\[^\s\"'<>]*")
_DOMAIN_USER = re.compile(
    r"(?i)(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9._-]{0,30}\\[A-Za-z][A-Za-z0-9._-]{1,40}"
)
_EMAIL = re.compile(r"(?i)[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}")
_PERSONAL_NAME = re.compile(
    r"(?i)(?:autor|author|empresa|company|usu[aá]rio|user|e-?mail|cpf|cnpj|\bpis\b|gerente|manager|respons[aá]vel)"
)
_NOTE = (
    "O original não foi alterado. Fórmula local permanece. "
    "Fórmula que depende de vínculo externo passa a ser o valor em cache; sem cache, a célula fica vazia. "
    "CPF, CNPJ e segredo em célula não são alterados: ficam para revisão humana. "
    "Aba, linha e coluna ocultas só saem com --remover-ocultas, porque apagar pode quebrar fórmula. "
    "Nesse caso a fórmula dependente vira o valor em cache, a linha oculta fica vazia e visível, "
    "e as demais linhas não são renumeradas."
)

_WHY = {
    "cpf": "CPF na célula: o valor não foi alterado. Ficou para revisão humana.",
    "cnpj": "CNPJ na célula: o valor não foi alterado. Ficou para revisão humana.",
    "pis": "PIS na célula: o valor não foi alterado. Ficou para revisão humana.",
    "conta-bancaria": "Dado bancário na célula: o valor não foi alterado. Ficou para revisão humana.",
    "segredo": "Possível segredo na célula: o valor não foi alterado. Ficou para revisão humana.",
    "entropia": "Trecho de alta entropia na célula: o valor não foi alterado. Ficou para revisão humana.",
    "aba-oculta": (
        "Aba oculta foi mantida. Apagar pode quebrar fórmula. "
        "Use --remover-ocultas para apagar e trocar a fórmula dependente pelo valor em cache."
    ),
    "aba-muito-oculta": (
        "Aba muito oculta foi mantida. Apagar pode quebrar fórmula. Use --remover-ocultas."
    ),
    "linha-oculta": "Linha oculta foi mantida. Apagar pode quebrar fórmula. Use --remover-ocultas.",
    "coluna-oculta": "Coluna oculta foi mantida. Apagar pode quebrar fórmula. Use --remover-ocultas.",
    "formula-referencia-oculta": (
        "Fórmula que aponta para área oculta foi mantida. Use --remover-ocultas para trocar pelo valor em cache."
    ),
    "macro": "A macro foi mantida. Use --remover-macros para gerar um .xlsx sem vbaProject.",
    "macro-suspeita": "A macro foi mantida. Use --remover-macros para gerar um .xlsx sem vbaProject.",
    "macro-ioc": "A macro foi mantida. Use --remover-macros para gerar um .xlsx sem vbaProject.",
    "nao-analisado": "Uma parte da cópia não foi lida. Veja a mensagem da varredura.",
    "vinculo-externo": (
        "Ainda há vínculo ou hiperlink. externalLinks sai por padrão; hiperlink de célula fica para revisão humana."
    ),
    "formula-vinculo-externo": (
        "Ainda há fórmula com vínculo. Sem valor em cache a célula fica vazia; fórmula local é preservada."
    ),
    "metadado": (
        "Metadado descritivo (título, assunto ou semelhante) foi mantido. "
        "Autor, empresa e última modificação saem por padrão."
    ),
    "formula-constante": "Número fixo dentro de fórmula local foi preservado.",
    "nome-definido": "Nome definido visível foi mantido.",
    "nome-definido-oculto": "Nome definido oculto foi mantido. Confira o destino no relatório.",
    "formato-oculto": "Formato que esconde o valor foi mantido. A limpeza não mexe no formato da célula.",
    "largura-minima": "Coluna muito estreita foi mantida. Isso é diferente de coluna marcada como oculta.",
    "altura-minima": "Linha muito baixa foi mantida. Isso é diferente de linha marcada como oculta.",
    "fora-impressao": "Conteúdo fora da área de impressão foi mantido.",
    "formula-fora-impressao": "Fórmula fora da área de impressão foi mantida.",
    "comentario": "Ainda há comentário. A parte não foi alcançada pela limpeza.",
    "comentario-thread": "Ainda há comentário em thread. A parte não foi alcançada pela limpeza.",
}


class CleanError(Exception):
    """The copy was not written. The original is unchanged."""


@dataclass
class CleanResult:
    data: bytes
    removed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    had_vba: bool = False
    stripped_vba: bool = False


@dataclass
class _SheetEntry:
    name: str
    state: str
    part: str
    index: int


@dataclass
class _FormulaStats:
    external_converted: int = 0
    external_empty: int = 0
    hidden_converted: int = 0
    hidden_empty: int = 0


def default_output_path(source: Path, *, remove_macros: bool) -> Path:
    """``proposta.xlsx`` becomes ``proposta-limpa.xlsx`` beside the original."""
    suffix = ".xlsx" if remove_macros else source.suffix.lower()
    if suffix not in {".xlsx", ".xlsm"}:
        suffix = ".xlsx"
    return source.with_name(f"{source.stem}-limpa{suffix}")


def clean_bytes(
    data: bytes,
    nome: str,
    *,
    remove_hidden: bool = False,
    remove_macros: bool = False,
    max_mb: int | None = None,
) -> CleanResult:
    """Return cleaned package bytes. Does not touch the filesystem."""
    parts = _read_parts(data, max_mb=max_mb)
    workbook = load_workbook_bytes(data, nome, max_mb=max_mb, keep_cells=False)
    entries = _sheet_entries(parts)
    if not entries:
        raise WorkbookParseError("a pasta não tem abas")
    hidden_entries = [item for item in entries if item.state in {"hidden", "veryHidden"}]
    if remove_hidden and len(hidden_entries) == len(entries):
        raise CleanError(
            "Todas as abas estão ocultas. Removê-las deixaria o arquivo sem aba. Nada foi gravado."
        )

    removed_sheets = {item.name.casefold() for item in hidden_entries} if remove_hidden else set()
    removed_indexes = {item.index for item in hidden_entries} if remove_hidden else set()
    dropped: set[str] = set()
    removed: list[str] = []
    warnings: list[str] = []
    stats = _FormulaStats()

    _mark_comment_parts(parts, dropped)
    _mark_external_parts(parts, dropped)
    had_vba = _has_vba(parts)
    stripped_vba = False
    if remove_macros and had_vba:
        _mark_vba_parts(parts, dropped)
        stripped_vba = True
    if remove_hidden:
        for item in hidden_entries:
            dropped.add(item.part.casefold())
            rels = _rels_name(item.part)
            if rels:
                dropped.add(rels.casefold())

    names = {item.name for item in workbook.defined_names}
    vml_targets: list[str] = []
    for item in entries:
        if item.name.casefold() in removed_sheets:
            continue
        payload = _lookup(parts, item.part)
        if payload is None:
            continue
        edited, ids, sheet_stats = _edit_sheet(
            payload,
            item.name,
            workbook,
            names=names,
            remove_hidden=remove_hidden,
            removed_sheets=removed_sheets,
        )
        _add_stats(stats, sheet_stats)
        if edited is not None:
            _store(parts, item.part, edited)
        if ids:
            vml_targets.extend(_vml_targets(parts, item.part, ids))

    for target in vml_targets:
        dropped.add(target.casefold())
    _mark_drawing_targets(parts, dropped)

    names_removed, workbook_xml = _edit_workbook(
        parts,
        removed_sheets=removed_sheets,
        removed_indexes=removed_indexes,
        remove_hidden=remove_hidden,
    )
    if workbook_xml is not None:
        _store(parts, "xl/workbook.xml", workbook_xml)

    if stats.external_converted or stats.external_empty or stats.hidden_converted or names_removed or removed_sheets:
        _mark_calc_chain(parts, dropped)

    identity, paths, personal_props = _scrub_properties(parts, dropped)
    for target in list(dropped):
        _drop_key(parts, target)

    _rewrite_rels(parts, dropped)
    _rewrite_content_types(parts, dropped, xlsx_main=stripped_vba)
    packed = _pack(parts, max_mb=max_mb)

    if _dropped_any(dropped, ("xl/comments", "xl/threadedcomments/", "xl/persons/")):
        removed.append("Comentários e notas removidos.")
    if identity:
        removed.append("Metadados de autor, empresa e última modificação removidos.")
    if paths:
        removed.append("Caminho de rede ou de usuário removido dos metadados.")
    if personal_props:
        removed.append(
            "Propriedades personalizadas com dado pessoal removidas: " + ", ".join(personal_props) + "."
        )
    if _dropped_any(dropped, ("xl/externallinks/",)) or stats.external_converted or stats.external_empty:
        line = "Vínculo externo (externalLinks) removido. Fórmulas que dependiam dele ficaram com o valor em cache."
        if stats.external_empty:
            line += " Houve fórmula externa sem valor em cache: a célula ficou vazia."
        removed.append(line)
    if names_removed:
        removed.append("Nome definido que apontava para vínculo externo ou para aba removida foi retirado.")
    for item in hidden_entries if remove_hidden else []:
        removed.append(
            f"Aba oculta removida: {_safe_label(item.name)}. "
            "Fórmulas que dependiam dela passaram ao valor em cache."
        )
    if stats.hidden_empty:
        warnings.append("Houve fórmula dependente de área oculta sem valor em cache: a célula ficou vazia.")
    if remove_hidden and _workbook_had_hidden_rows_or_cols(workbook, removed_sheets):
        removed.append(
            "Linhas e colunas ocultas foram esvaziadas e reexibidas. "
            "As outras linhas mantêm o mesmo número e as outras colunas a mesma letra."
        )
    if stripped_vba:
        removed.append("Macro removida (vbaProject). A cópia é .xlsx.")
    if not removed:
        removed.append("Nenhum comentário, metadado de autor ou vínculo externo precisou sair.")

    if not remove_hidden and (hidden_entries or _workbook_had_hidden_rows_or_cols(workbook, set())):
        warnings.append(
            "Abas, linhas ou colunas ocultas foram mantidas. Apagar pode quebrar fórmula. "
            "Use --remover-ocultas para apagar e trocar a fórmula dependente pelo valor em cache. "
            "Linhas e colunas ocultas, quando removidas, ficam vazias e visíveis; o restante não é renumerado."
        )
    if had_vba and not remove_macros:
        warnings.append("A macro foi mantida. Use --remover-macros para gerar um .xlsx sem vbaProject.")
    if _has_hyperlink(parts):
        warnings.append("Hiperlink de célula foi mantido. O endereço fica para revisão humana.")
    if _has_part(parts, "connections.xml"):
        warnings.append("Conexão de dados foi mantida. Revise manualmente.")
    if _has_part(parts, "printersettings"):
        warnings.append("Configuração de impressora foi mantida. Ela pode guardar um nome de máquina.")

    return CleanResult(
        data=packed,
        removed=removed,
        warnings=warnings,
        had_vba=had_vba,
        stripped_vba=stripped_vba,
    )


def write_clean_copy(
    source: Path,
    destination: Path | None = None,
    *,
    remove_hidden: bool = False,
    remove_macros: bool = False,
    force: bool = False,
    max_mb: int | None = None,
) -> tuple[Path, CleanResult]:
    """Write the copy beside ``source`` or at ``destination``. Never replaces ``source``."""
    if not source.is_file():
        raise CleanError("Arquivo não encontrado.")
    if source.suffix.lower() not in {".xlsx", ".xlsm"}:
        raise CleanError("A limpeza aceita .xlsx e .xlsm.")
    original = source.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    result = clean_bytes(
        original,
        source.name,
        remove_hidden=remove_hidden,
        remove_macros=remove_macros,
        max_mb=max_mb,
    )
    dest = destination if destination is not None else default_output_path(source, remove_macros=remove_macros)
    if dest.exists() and dest.is_dir():
        raise CleanError("Informe um arquivo em --saida, não uma pasta.")
    if remove_macros and dest.suffix.lower() == ".xlsm":
        dest = dest.with_suffix(".xlsx")
        result.warnings.append("A saída foi gravada como .xlsx porque a macro foi removida.")
    if _same_path(source, dest):
        raise CleanError("A cópia não pode substituir o arquivo original, nem com --forcar.")
    if dest.exists() and not force:
        raise CleanError(
            f"A cópia já existe ({dest.name}). Use --forcar para substituir. O original não foi alterado."
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_name(f".{dest.name}.oculto-tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        view = memoryview(result.data)
        while view:
            written = os.write(fd, view)
            view = view[written:]
    except Exception:
        os.close(fd)
        temporary.unlink(missing_ok=True)
        raise
    else:
        os.close(fd)
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    try:
        os.replace(temporary, dest)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
        raise CleanError("O original mudou durante a limpeza. Isso não deveria acontecer.")
    return dest, result


def explain_leftovers(findings: list[Finding]) -> list[str]:
    """One safe line per rule that the copy still has, and why it is still there."""
    seen: list[str] = []
    known: set[str] = set()
    for finding in findings:
        if finding.rule in known:
            continue
        known.add(finding.rule)
        if finding.rule == "mapa-rede":
            continue
        seen.append(_WHY.get(finding.rule, "Este achado foi mantido. Veja o detalhe na varredura da cópia."))
    return seen


def render_clean_text(
    *,
    source_name: str,
    dest_name: str,
    result: CleanResult,
    before: list[Finding],
    after: list[Finding],
    after_text: str,
) -> str:
    lines = [
        "Limpeza",
        f"Original: {source_name}",
        f"Cópia: {dest_name}",
        "",
        _NOTE,
        "",
        "Removido:",
        *[f"- {item}" for item in result.removed],
    ]
    if result.warnings:
        lines.extend(["", "Avisos:", *[f"- {item}" for item in result.warnings]])
    leftovers = explain_leftovers(after)
    lines.extend(["", "Ainda na cópia:"])
    if leftovers:
        lines.extend(f"- {item}" for item in leftovers)
    else:
        lines.append("- A varredura da cópia não apontou achado restante.")
    lines.extend(
        [
            "",
            f"Antes: {_count_line(before)}",
            f"Depois: {_count_line(after)}",
            "",
            "Varredura da cópia:",
            after_text.rstrip(),
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def render_clean_json(
    *,
    source_name: str,
    dest_name: str,
    result: CleanResult,
    before_json: str,
    after_json: str,
    after: list[Finding],
) -> str:
    payload = {
        "modo": "limpar",
        "original": source_name,
        "copia": dest_name,
        "nota": _NOTE,
        "removido": list(result.removed),
        "avisos": list(result.warnings),
        "ainda": explain_leftovers(after),
        "antes": json.loads(before_json),
        "depois": json.loads(after_json),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def inject_clean_html(page: str, *, source_name: str, dest_name: str, result: CleanResult, after: list[Finding]) -> str:
    """Insert the clean summary into an already escaped scan page."""
    items = "".join(f"<li>{html.escape(item)}</li>" for item in result.removed)
    warns = "".join(f"<li>{html.escape(item)}</li>" for item in result.warnings)
    left = "".join(f"<li>{html.escape(item)}</li>" for item in explain_leftovers(after))
    block = (
        "<section><h2>Limpeza</h2>"
        f"<p>Original: {html.escape(source_name)}. Cópia: {html.escape(dest_name)}.</p>"
        f"<p>{html.escape(_NOTE)}</p>"
        f"<h3>Removido</h3><ul>{items}</ul>"
        f"<h3>Avisos</h3><ul>{warns or '<li>Nenhum.</li>'}</ul>"
        f"<h3>Ainda na cópia</h3><ul>{left or '<li>Nenhum achado restante.</li>'}</ul>"
        "<p>A varredura abaixo é a da cópia.</p></section>"
    )
    return page.replace("</body>", block + "</body>", 1)


def _count_line(findings: list[Finding]) -> str:
    counts = summary(findings)
    return f"{counts['alto']} alto, {counts['medio']} médio, {counts['info']} info ({counts['total']} no total)"


def _read_parts(data: bytes, *, max_mb: int | None) -> dict[str, bytes]:
    archive = open_office_bytes(data, max_mb=max_mb)
    try:
        parts: dict[str, bytes] = {}
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            if name.endswith("/") or info.is_dir():
                continue
            parts[name] = read_member(archive, info, max_mb=max_mb)
        return parts
    finally:
        archive.close()


def _lookup(parts: dict[str, bytes], name: str) -> bytes | None:
    if name in parts:
        return parts[name]
    folded = name.casefold()
    for key, payload in parts.items():
        if key.casefold() == folded:
            return payload
    return None


def _store(parts: dict[str, bytes], name: str, payload: bytes) -> None:
    folded = name.casefold()
    for key in list(parts):
        if key.casefold() == folded:
            parts[key] = payload
            return
    parts[name] = payload


def _drop_key(parts: dict[str, bytes], folded_name: str) -> None:
    for key in list(parts):
        if key.casefold() == folded_name:
            del parts[key]


def _key_for(parts: dict[str, bytes], name: str) -> str | None:
    folded = name.casefold()
    for key in parts:
        if key.casefold() == folded:
            return key
    return None


def _sheet_entries(parts: dict[str, bytes]) -> list[_SheetEntry]:
    payload = _lookup(parts, "xl/workbook.xml")
    if payload is None:
        raise WorkbookParseError("xl/workbook.xml ausente")
    root = _parse_xml(payload)
    rels_payload = _lookup(parts, "xl/_rels/workbook.xml.rels")
    rels = _parse_rels(rels_payload) if rels_payload else []
    by_id = {rel_id: target for rel_id, _rel_type, target, _mode in rels}
    entries: list[_SheetEntry] = []
    index = 0
    for node in root.iter():
        if _local(node.tag) != "sheet":
            continue
        name = _attr(node, "name") or "Sem nome"
        state = _attr(node, "state") or "visible"
        if state not in {"visible", "hidden", "veryHidden"}:
            state = "visible"
        rel_id = _attr(node, "id") or ""
        target = by_id.get(rel_id, "")
        part = _resolve("xl/workbook.xml", target) if target else ""
        entries.append(_SheetEntry(name=name, state=state, part=part, index=index))
        index += 1
    return entries


def _rels_name(part: str) -> str:
    directory, _, filename = part.rpartition("/")
    return f"{directory}/_rels/{filename}.rels" if directory else f"_rels/{filename}.rels"


def _owner_part(rels_name: str) -> str:
    folded = rels_name.replace("\\", "/")
    if folded.casefold() == "_rels/.rels":
        return ""
    marker = "/_rels/"
    index = folded.casefold().rfind(marker)
    if index == -1:
        return folded
    parent = folded[:index]
    filename = folded[index + len(marker) :]
    if filename.casefold().endswith(".rels"):
        filename = filename[:-5]
    return f"{parent}/{filename}" if parent else filename


def _mark_comment_parts(parts: dict[str, bytes], dropped: set[str]) -> None:
    for name in parts:
        folded = name.casefold()
        if folded.startswith("xl/comments") and folded.endswith(".xml"):
            dropped.add(folded)
        elif folded.startswith("xl/threadedcomments/"):
            dropped.add(folded)
        elif folded.startswith("xl/persons/"):
            dropped.add(folded)


def _mark_external_parts(parts: dict[str, bytes], dropped: set[str]) -> None:
    for name in parts:
        folded = name.casefold()
        if folded.startswith("xl/externallinks/"):
            dropped.add(folded)


def _mark_drawing_targets(parts: dict[str, bytes], dropped: set[str]) -> None:
    for name, payload in list(parts.items()):
        if not name.casefold().endswith(".rels"):
            continue
        try:
            rels = _parse_rels(payload)
        except WorkbookParseError:
            continue
        owner = _owner_part(name)
        for _rel_id, rel_type, target, mode in rels:
            if mode.casefold() == "external" or not target:
                continue
            if "vmldrawing" in rel_type.casefold():
                dropped.add(_resolve(owner, target).casefold())


def _mark_vba_parts(parts: dict[str, bytes], dropped: set[str]) -> None:
    for name in parts:
        folded = name.casefold()
        if folded.endswith("vbaproject.bin") or "vbaprojectsignature" in folded or folded.endswith("/vbadata.xml"):
            dropped.add(folded)


def _mark_calc_chain(parts: dict[str, bytes], dropped: set[str]) -> None:
    for name in parts:
        if name.casefold().endswith("calcchain.xml"):
            dropped.add(name.casefold())


def _has_vba(parts: dict[str, bytes]) -> bool:
    return any(name.casefold().endswith("vbaproject.bin") for name in parts)


def _has_part(parts: dict[str, bytes], token: str) -> bool:
    return any(token in name.casefold() for name in parts)


def _has_hyperlink(parts: dict[str, bytes]) -> bool:
    for name, payload in parts.items():
        if not name.casefold().endswith(".rels"):
            continue
        try:
            rels = _parse_rels(payload)
        except WorkbookParseError:
            continue
        for _rid, rel_type, _target, _mode in rels:
            if rel_type.casefold().endswith("/hyperlink"):
                return True
    return False


def _dropped_any(dropped: set[str], prefixes: tuple[str, ...]) -> bool:
    return any(name.startswith(prefix) or prefix in name for name in dropped for prefix in prefixes)


def _workbook_had_hidden_rows_or_cols(workbook: Workbook, removed_sheets: set[str]) -> bool:
    for sheet in workbook.sheets:
        if sheet.name.casefold() in removed_sheets:
            continue
        if sheet.hidden_rows or sheet.hidden_cols or sheet.hidden_row_spans or sheet.hidden_col_spans:
            return True
    return False


def _add_stats(total: _FormulaStats, extra: _FormulaStats) -> None:
    total.external_converted += extra.external_converted
    total.external_empty += extra.external_empty
    total.hidden_converted += extra.hidden_converted
    total.hidden_empty += extra.hidden_empty


def _edit_sheet(
    payload: bytes,
    sheet_name: str,
    workbook: Workbook,
    *,
    names: set[str],
    remove_hidden: bool,
    removed_sheets: set[str],
) -> tuple[bytes | None, list[str], _FormulaStats]:
    root = _parse_xml(payload)
    stats = _FormulaStats()
    dirty = False
    hidden_cols = _hidden_columns(root) if remove_hidden else set()
    masters = _shared_masters(root)
    seen_si: dict[str, str] = {}
    for row in root.iter():
        if _local(row.tag) != "row":
            continue
        for cell in list(row):
            if _local(cell.tag) != "c":
                continue
            if _cell_will_go(row, cell, hidden_cols, remove_hidden=remove_hidden):
                continue
            formula = _effective_formula(cell, masters)
            if not formula:
                continue
            shared_id = _shared_id(cell)
            kind = seen_si.get(shared_id) if shared_id and shared_id in seen_si else None
            if kind is None:
                kind = _formula_kind(
                    formula,
                    sheet_name,
                    workbook,
                    names=names,
                    remove_hidden=remove_hidden,
                    removed_sheets=removed_sheets,
                    seen=set(),
                )
                if shared_id and kind:
                    seen_si[shared_id] = kind
            if not kind:
                continue
            cached = _has_cache(cell)
            _remove_formula(cell)
            dirty = True
            if kind == "externo":
                if cached:
                    stats.external_converted += 1
                else:
                    stats.external_empty += 1
            elif cached:
                stats.hidden_converted += 1
            else:
                stats.hidden_empty += 1

    if remove_hidden and (_clear_hidden(root, hidden_cols)):
        dirty = True
    drawing_ids = _strip_comment_drawings(root)
    if drawing_ids:
        dirty = True
    if not dirty:
        return None, drawing_ids, stats
    return _serialize(root), drawing_ids, stats


def _hidden_columns(root) -> set[int]:
    found: set[int] = set()
    for node in root.iter():
        if _local(node.tag) != "col" or not _truthy(_attr(node, "hidden")):
            continue
        try:
            start = int(_attr(node, "min") or "0")
            end = int(_attr(node, "max") or str(start))
        except ValueError:
            continue
        if start >= 1 and end >= start:
            found.update(range(start, end + 1))
    return found


def _shared_masters(root) -> dict[str, str]:
    masters: dict[str, str] = {}
    for node in root.iter():
        if _local(node.tag) != "f":
            continue
        text = (node.text or "").strip()
        shared_id = _attr(node, "si")
        if text and shared_id is not None:
            masters[shared_id] = text
    return masters


def _shared_id(cell) -> str | None:
    for child in cell:
        if _local(child.tag) == "f":
            return _attr(child, "si")
    return None


def _effective_formula(cell, masters: dict[str, str]) -> str:
    for child in cell:
        if _local(child.tag) != "f":
            continue
        text = (child.text or "").strip()
        if text:
            return text[1:] if text.startswith("=") else text
        shared_id = _attr(child, "si")
        if shared_id is not None:
            return masters.get(shared_id, "")
    return ""


def _cell_will_go(row, cell, hidden_cols: set[int], *, remove_hidden: bool) -> bool:
    if not remove_hidden:
        return False
    if _truthy(_attr(row, "hidden")):
        return True
    parsed = split_cell(_attr(cell, "r") or "")
    return bool(parsed and parsed[1] in hidden_cols)


def _has_cache(cell) -> bool:
    for child in cell:
        local = _local(child.tag)
        if local == "v" and (child.text or "").strip():
            return True
        if local == "is" and "".join(child.itertext()).strip():
            return True
    return False


def _remove_formula(cell) -> None:
    for child in list(cell):
        if _local(child.tag) == "f":
            cell.remove(child)


def _formula_kind(
    formula: str,
    sheet_name: str,
    workbook: Workbook,
    *,
    names: set[str],
    remove_hidden: bool,
    removed_sheets: set[str],
    seen: set[str],
) -> str | None:
    info = parse_formula(formula, names)
    if info.external:
        return "externo"
    hidden_hit = False
    if remove_hidden:
        for sheet, ref in info.sheet_refs:
            if sheet.casefold() in removed_sheets or reference_is_hidden(workbook, sheet, ref):
                hidden_hit = True
                break
        if not hidden_hit:
            for ref in info.local_refs:
                if reference_is_hidden(workbook, sheet_name, ref):
                    hidden_hit = True
                    break
    for name in info.names:
        key = name.casefold()
        if key in seen:
            continue
        defined = _defined(workbook, key)
        if defined is None:
            continue
        seen.add(key)
        nested = _formula_kind(
            defined.formula,
            defined.local_sheet or sheet_name,
            workbook,
            names=names,
            remove_hidden=remove_hidden,
            removed_sheets=removed_sheets,
            seen=seen,
        )
        if nested == "externo":
            return "externo"
        if nested == "oculta":
            hidden_hit = True
    if hidden_hit:
        return "oculta"
    return None


def _defined(workbook: Workbook, folded: str) -> DefinedName | None:
    for item in workbook.defined_names:
        if item.name.casefold() == folded:
            return item
    return None


def _clear_hidden(root, hidden_cols: set[int]) -> bool:
    dirty = False
    for parent, child in _pairs(root):
        if _local(child.tag) != "col" or not _truthy(_attr(child, "hidden")):
            continue
        if child in list(parent):
            parent.remove(child)
            dirty = True
    for parent, child in _pairs(root):
        if _local(child.tag) == "cols" and len(list(child)) == 0 and child in list(parent):
            parent.remove(child)
            dirty = True
    for row in list(root.iter()):
        if _local(row.tag) != "row":
            continue
        if _truthy(_attr(row, "hidden")):
            for cell in list(row):
                if _local(cell.tag) == "c":
                    row.remove(cell)
            _delete_attr(row, "hidden")
            dirty = True
            continue
        if not hidden_cols:
            continue
        for cell in list(row):
            if _local(cell.tag) != "c":
                continue
            parsed = split_cell(_attr(cell, "r") or "")
            if parsed and parsed[1] in hidden_cols:
                row.remove(cell)
                dirty = True
    return dirty


def _strip_comment_drawings(root) -> list[str]:
    found: list[str] = []
    for parent, child in _pairs(root):
        local = _local(child.tag)
        if local == "legacyDrawing":
            rid = _attr(child, "id")
            if rid:
                found.append(rid)
            if child in list(parent):
                parent.remove(child)
        elif local in {"threadedComment", "threadedComments"} and child in list(parent):
            parent.remove(child)
    _prune_empty(root, {"ext", "extLst"})
    return found


def _prune_empty(root, names: set[str]) -> None:
    changed = True
    while changed:
        changed = False
        for parent, child in _pairs(root):
            if _local(child.tag) not in names:
                continue
            if list(child) or (child.text or "").strip():
                continue
            if child in list(parent):
                parent.remove(child)
                changed = True
                break


def _pairs(root) -> list[tuple]:
    found = []
    for parent in root.iter():
        for child in list(parent):
            found.append((parent, child))
    return found


def _delete_attr(element, name: str) -> None:
    for key in list(element.attrib):
        if key == name or key.endswith("}" + name):
            del element.attrib[key]


def _vml_targets(parts: dict[str, bytes], sheet_part: str, rel_ids: list[str]) -> list[str]:
    payload = _lookup(parts, _rels_name(sheet_part))
    if payload is None:
        return []
    wanted = set(rel_ids)
    targets: list[str] = []
    for rel_id, rel_type, target, mode in _parse_rels(payload):
        if mode.casefold() == "external":
            continue
        if rel_id in wanted or "vmldrawing" in rel_type.casefold():
            targets.append(_resolve(sheet_part, target))
    return targets


def _edit_workbook(
    parts: dict[str, bytes],
    *,
    removed_sheets: set[str],
    removed_indexes: set[int],
    remove_hidden: bool,
) -> tuple[int, bytes | None]:
    payload = _lookup(parts, "xl/workbook.xml")
    if payload is None:
        return 0, None
    root = _parse_xml(payload)
    dirty = False
    removed_names = 0
    for parent, child in _pairs(root):
        local = _local(child.tag)
        if local in {"externalReferences", "externalReference"} and child in list(parent):
            parent.remove(child)
            dirty = True
            continue
        if local != "sheet":
            continue
        state = _attr(child, "state") or "visible"
        name = (_attr(child, "name") or "").casefold()
        if remove_hidden and (name in removed_sheets or state in {"hidden", "veryHidden"}):
            if child in list(parent):
                parent.remove(child)
                dirty = True
    for parent, child in _pairs(root):
        if _local(child.tag) != "definedName":
            continue
        formula = (child.text or "").strip()
        local_id = _attr(child, "localSheetId")
        drop_name = _name_is_external(formula)
        if local_id is not None and local_id.isdigit() and int(local_id) in removed_indexes:
            drop_name = True
        elif remove_hidden and _formula_mentions_sheet(formula, removed_sheets):
            drop_name = True
        if drop_name and child in list(parent):
            parent.remove(child)
            removed_names += 1
            dirty = True
            continue
        if local_id is not None and local_id.isdigit() and removed_indexes:
            current = int(local_id)
            shift = sum(1 for index in removed_indexes if index < current)
            if shift:
                _set_attr(child, "localSheetId", str(current - shift))
                dirty = True
    for parent, child in _pairs(root):
        if _local(child.tag) == "definedNames" and len(list(child)) == 0 and child in list(parent):
            parent.remove(child)
            dirty = True
    if not dirty:
        return removed_names, None
    return removed_names, _serialize(root)


def _name_is_external(formula: str) -> bool:
    return bool(parse_formula(formula).external)


def _formula_mentions_sheet(formula: str, sheets: set[str]) -> bool:
    info = parse_formula(formula)
    return any(sheet.casefold() in sheets for sheet, _ref in info.sheet_refs)


def _set_attr(element, name: str, value: str) -> None:
    for key in list(element.attrib):
        if key == name or key.endswith("}" + name):
            element.attrib[key] = value
            return
    element.attrib[name] = value


def _scrub_properties(parts: dict[str, bytes], dropped: set[str]) -> tuple[bool, bool, list[str]]:
    identity = False
    paths = False
    for part in ("docProps/core.xml", "docProps/app.xml"):
        payload = _lookup(parts, part)
        if payload is None:
            continue
        root = _parse_xml(payload)
        changed, cleared, scrubbed = _scrub_tree(root)
        identity = identity or cleared
        paths = paths or scrubbed
        if changed:
            _store(parts, part, _serialize(root))
    personal: list[str] = []
    custom = _lookup(parts, "docProps/custom.xml")
    if custom is None:
        return identity, paths, personal
    root = _parse_xml(custom)
    for parent, child in _pairs(root):
        if _local(child.tag) != "property":
            continue
        prop_name = _attr(child, "name") or "propriedade"
        value = "".join(child.itertext())
        if _property_is_personal(prop_name, value) and child in list(parent):
            parent.remove(child)
            personal.append(_safe_label(prop_name))
    if personal:
        if any(_local(child.tag) == "property" for child in root.iter()):
            _store(parts, "docProps/custom.xml", _serialize(root))
        else:
            dropped.add("docprops/custom.xml")
    return identity, paths, personal


def _scrub_tree(root) -> tuple[bool, bool, bool]:
    changed = False
    cleared = False
    scrubbed = False
    for node in root.iter():
        local = _local(node.tag).casefold()
        text = node.text or ""
        if local in _CLEAR_META and text.strip():
            if _has_path(text) or _EMAIL.search(text):
                scrubbed = True
            node.text = ""
            changed = True
            cleared = True
            continue
        if not text.strip():
            continue
        updated, did = _scrub_text(text)
        if did:
            node.text = updated
            changed = True
            scrubbed = True
    return changed, cleared, scrubbed


def _scrub_text(text: str) -> tuple[str, bool]:
    updated = _UNC.sub("", text)
    updated = _DRIVE.sub("", updated)
    updated = _DOMAIN_USER.sub("", updated)
    updated = _EMAIL.sub("", updated)
    updated = re.sub(r"\s+", " ", updated).strip(" -;,")
    return updated, updated != text.strip()


def _has_path(text: str) -> bool:
    return bool(_UNC.search(text) or _DRIVE.search(text) or _DOMAIN_USER.search(text))


def _property_is_personal(name: str, value: str) -> bool:
    if _PERSONAL_NAME.search(name):
        return True
    if _has_path(value) or _EMAIL.search(value):
        return True
    try:
        return bool(tarja.find(value[:10_000], entities=("BR_CPF", "BR_CNPJ", "BR_NIS")))
    except Exception:
        return False


def _safe_label(name: str) -> str:
    if "@" in name or "\\" in name or _DRIVE.search(name) or _EMAIL.search(name):
        return "item com dado pessoal"
    return name


def _rewrite_rels(parts: dict[str, bytes], dropped: set[str]) -> None:
    for name in list(parts):
        if not name.casefold().endswith(".rels"):
            continue
        payload = parts[name]
        try:
            root = _parse_xml(payload)
        except WorkbookParseError:
            continue
        owner = _owner_part(name)
        dirty = False
        for parent, child in _pairs(root):
            if _local(child.tag) != "Relationship":
                continue
            rel_type = _attr(child, "Type") or ""
            target = _attr(child, "Target") or ""
            mode = _attr(child, "TargetMode") or ""
            if _rel_dropped(rel_type, target, mode, owner, dropped) and child in list(parent):
                parent.remove(child)
                dirty = True
        if dirty:
            parts[name] = _serialize(root)


def _rel_dropped(rel_type: str, target: str, mode: str, owner: str, dropped: set[str]) -> bool:
    folded = rel_type.casefold()
    if folded.endswith("/comments") or folded.endswith("/externallink") or folded.endswith("/person"):
        return True
    if "threadedcomment" in folded or "vbaproject" in folded:
        return True
    if folded.endswith("/calcchain") and any(name.endswith("calcchain.xml") for name in dropped):
        return True
    if "vmldrawing" in folded:
        return True
    if mode.casefold() == "external":
        return False
    resolved = _resolve(owner, target).casefold() if target else ""
    return resolved in dropped


def _rewrite_content_types(parts: dict[str, bytes], dropped: set[str], *, xlsx_main: bool) -> None:
    key = _key_for(parts, "[Content_Types].xml")
    if key is None:
        return
    root = _parse_xml(parts[key])
    dirty = False
    for parent, child in _pairs(root):
        if _local(child.tag) != "Override":
            continue
        part_name = (_attr(child, "PartName") or "").lstrip("/").casefold()
        content = _attr(child, "ContentType") or ""
        if part_name in dropped and child in list(parent):
            parent.remove(child)
            dirty = True
            continue
        if xlsx_main and "macroenabled" in content.casefold():
            _set_attr(child, "ContentType", _XLSX_MAIN)
            dirty = True
    if dirty:
        parts[key] = _serialize(root)


def _pack(parts: dict[str, bytes], *, max_mb: int | None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(parts, key=_zip_order):
            if name.startswith("/") or ".." in name.split("/"):
                raise WorkbookParseError("parte com caminho recusado")
            archive.writestr(name, parts[name])
    data = buffer.getvalue()
    archive = open_office_bytes(data, max_mb=max_mb)
    archive.close()
    return data


def _zip_order(name: str) -> tuple[int, str]:
    if name == "[Content_Types].xml":
        return (0, name)
    if name == "_rels/.rels":
        return (1, name)
    return (2, name)


def _same_path(source: Path, dest: Path) -> bool:
    try:
        if dest.exists() and source.exists() and dest.samefile(source):
            return True
    except OSError:
        pass
    return dest.resolve() == source.resolve()


def _clark(tag: str) -> tuple[str, str]:
    if tag.startswith("{"):
        uri, _, local = tag[1:].partition("}")
        return uri, local
    return "", tag


def _collect_uris(element) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    def add(uri: str) -> None:
        if uri and uri != _XML_NS and uri not in seen:
            seen.add(uri)
            found.append(uri)

    def walk(node) -> None:
        uri, _local_name = _clark(node.tag)
        add(uri)
        for key in node.attrib:
            attr_uri, _name = _clark(key)
            add(attr_uri)
        for child in node:
            walk(child)

    walk(element)
    return found


def _prefix_map(element) -> dict[str, str]:
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for uri in _collect_uris(element):
        preferred = _PREFERRED.get(uri, "ns")
        if preferred in used:
            number = 2
            base = preferred or "ns"
            preferred = f"{base}{number}"
            while preferred in used:
                number += 1
                preferred = f"{base}{number}"
        mapping[uri] = preferred
        used.add(preferred)
    return mapping


def _qname(tag: str, mapping: dict[str, str]) -> str:
    uri, local = _clark(tag)
    if not uri or uri == _XML_NS:
        if uri == _XML_NS:
            return f"xml:{local}"
        return local
    prefix = mapping.get(uri, "")
    if not prefix:
        return local
    return f"{prefix}:{local}"


def _escape_text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_attr(value: str) -> str:
    return _escape_text(value).replace('"', "&quot;")


def _serialize(element) -> bytes:
    mapping = _prefix_map(element)
    declarations = []
    for uri, prefix in mapping.items():
        if prefix:
            declarations.append(f'xmlns:{prefix}="{uri}"')
        else:
            declarations.append(f'xmlns="{uri}"')
    body = _write_xml(element, mapping, declarations)
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + body).encode("utf-8")


def _write_xml(element, mapping: dict[str, str], declarations: list[str] | None = None) -> str:
    name = _qname(element.tag, mapping)
    attrs: list[str] = []
    if declarations:
        attrs.extend(declarations)
    for key, value in element.attrib.items():
        attrs.append(f'{_qname(key, mapping)}="{_escape_attr(value)}"')
    attr_text = (" " + " ".join(attrs)) if attrs else ""
    children = list(element)
    if not children and not element.text:
        return f"<{name}{attr_text}/>"
    chunks = [f"<{name}{attr_text}>"]
    if element.text:
        chunks.append(_escape_text(element.text))
    for child in children:
        chunks.append(_write_xml(child, mapping))
        if child.tail:
            chunks.append(_escape_text(child.tail))
    chunks.append(f"</{name}>")
    return "".join(chunks)

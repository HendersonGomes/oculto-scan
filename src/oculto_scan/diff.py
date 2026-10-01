"""Compare two workbooks: what changed, and who saved last.

The file does not record an IP address or a per-person edit history.
``lastModifiedBy`` is only the last person who saved, and it can be edited.
Opening a file without saving leaves no trace.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from oculto_scan import __version__
from oculto_scan.analyze import _author_label, _drop_legacy_thread_placeholders
from oculto_scan.masking import mask_formula, mask_path, mask_text
from oculto_scan.models import Cell, Comment, DefinedName, Sheet, Workbook
from oculto_scan.refs import contiguous_groups, format_group, index_to_col
from oculto_scan.report import DISCLAIMER, stdout_wants_color
from oculto_scan.workbook import WorkbookParseError, load_workbook, read_document_properties
from oculto_scan.zipsafe import ZipSafetyError

LIMITS = (
    "O arquivo não guarda IP nem o histórico de quem editou cada célula. "
    "lastModifiedBy é só quem salvou por último e pode ser editado. "
    "Abrir sem salvar não deixa rastro. "
    "Para histórico real, use o Histórico de Versões ou Mostrar Alterações no OneDrive/SharePoint, "
    "e os logs de auditoria do Microsoft 365 para endereço IP."
)
IDENTICAL = "arquivo não foi salvo novamente"
METADATA_ONLY = "salvo de novo sem alteração de conteúdo detectada"
REVEALED_BANNER = "Este relatório contém os dados revelados (--show). Não envie este arquivo a terceiros."

_STATE = {"visible": "visível", "hidden": "oculta", "veryHidden": "muito oculta"}
_META_FIELDS = (
    ("creator", "Criador"),
    ("lastModifiedBy", "Salvo por"),
    ("created", "Criado em"),
    ("modified", "Modificado em"),
    ("lastPrinted", "Última impressão"),
    ("revision", "Revisão"),
    ("Application", "Aplicativo"),
    ("AppVersion", "Versão do aplicativo"),
    ("Company", "Empresa"),
    ("Manager", "Gerente"),
)
_CATEGORY_RANK = {"conteudo": 0, "estrutura": 1, "metadado": 2}
_CATEGORY_COLOR = {"conteudo": "\033[31m", "estrutura": "\033[33m", "metadado": "\033[36m"}
_BOLD = "\033[1m"
_RESET = "\033[0m"
_SUFFIXES = {".xlsx", ".xlsm"}


@dataclass(frozen=True)
class DiffChange:
    sheet: str
    cell: str
    type_label: str
    category: str
    message: str
    before_masked: str
    after_masked: str
    before_raw: str
    after_raw: str


@dataclass(frozen=True)
class MetaRow:
    key: str
    label: str
    before_masked: str
    after_masked: str
    before_raw: str
    after_raw: str
    changed: bool


@dataclass
class DiffReport:
    original: str
    received: str
    changes: list[DiffChange]
    metadata: list[MetaRow]
    identical: bool
    headline: str | None
    exit_code: int


def _blank(value: str | None) -> str:
    return value if value else "—"


def _mask_scalar(value: str | None) -> str:
    if value is None or value == "":
        return "—"
    stripped = value.strip()
    if stripped.replace(".", "", 1).replace(",", "", 1).replace("-", "", 1).isdigit():
        return "[n]"
    return mask_text(stripped)


def _mask_formula_or_blank(value: str | None) -> str:
    if not value:
        return "—"
    return mask_formula(value)


def _format_stamp(when: datetime) -> str:
    if when.tzinfo is None:
        when = when.astimezone()
    offset = when.utcoffset() or timedelta(0)
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"{when.strftime('%d/%m/%Y %H:%M')} (UTC{sign}{hours:02d}:{minutes:02d})"


def _cell_map(sheet: Sheet) -> dict[str, Cell]:
    found: dict[str, Cell] = {}
    for cell in sheet.cells:
        if not cell.ref:
            continue
        if not cell.formula and not (cell.value and str(cell.value).strip()):
            continue
        found[cell.ref.replace("$", "").upper()] = cell
    return found


def _sheet_signature(sheet: Sheet) -> frozenset[tuple[str, str, str]]:
    signature: set[tuple[str, str, str]] = set()
    for ref, cell in _cell_map(sheet).items():
        signature.add((ref, cell.formula or "", str(cell.value or "")))
    return frozenset(signature)


def _jaccard(left: frozenset, right: frozenset) -> float:
    if not left and not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _match_renames(
    removed: list[Sheet], added: list[Sheet]
) -> tuple[list[tuple[Sheet, Sheet, bool]], list[Sheet], list[Sheet]]:
    """Pair a removed sheet with an added one when the cells mostly match."""
    pairs: list[tuple[Sheet, Sheet, bool]] = []
    unused_added = set(range(len(added)))
    still_removed: list[Sheet] = []
    for old in removed:
        best_index = None
        best_score = 0.0
        old_sig = _sheet_signature(old)
        for index in unused_added:
            score = _jaccard(old_sig, _sheet_signature(added[index]))
            if score > best_score:
                best_score = score
                best_index = index
        if best_index is not None and best_score >= 0.5:
            pairs.append((old, added[best_index], True))
            unused_added.remove(best_index)
        else:
            still_removed.append(old)
    still_added = [added[index] for index in sorted(unused_added)]
    return pairs, still_removed, still_added


def _comment_key(comment: Comment) -> str:
    return comment.ref.replace("$", "").upper()


def _comment_payload(comment: Comment, *, show: bool) -> tuple[str, str]:
    label = _author_label(comment.author)
    author = ""
    if label:
        author = comment.author.strip() if show else label
    text = comment.text if show else f"texto mascarado ({len(comment.text)} caracteres)"
    prefix = f"autor: {author}; " if author else ""
    raw_prefix = f"autor: {comment.author.strip()}; " if label and comment.author else ""
    return prefix + text, raw_prefix + comment.text


def _add(
    changes: list[DiffChange],
    *,
    sheet: str,
    cell: str,
    type_label: str,
    category: str,
    message: str,
    before_raw: str = "",
    after_raw: str = "",
    before_masked: str | None = None,
    after_masked: str | None = None,
) -> None:
    changes.append(
        DiffChange(
            sheet=sheet,
            cell=cell,
            type_label=type_label,
            category=category,
            message=message,
            before_masked=_blank(before_masked if before_masked is not None else _mask_scalar(before_raw)),
            after_masked=_blank(after_masked if after_masked is not None else _mask_scalar(after_raw)),
            before_raw=_blank(before_raw),
            after_raw=_blank(after_raw),
        )
    )


def _compare_cells(old: Sheet, new: Sheet, changes: list[DiffChange]) -> None:
    before = _cell_map(old)
    after = _cell_map(new)
    for ref in sorted(set(before) | set(after)):
        left = before.get(ref)
        right = after.get(ref)
        if left is None and right is not None:
            shown = right.formula or str(right.value or "")
            _add(
                changes,
                sheet=new.name,
                cell=ref,
                type_label="célula criada",
                category="conteudo",
                message="Célula presente só na planilha recebida.",
                after_raw=shown,
                after_masked=_mask_formula_or_blank(right.formula) if right.formula else _mask_scalar(shown),
            )
            continue
        if right is None and left is not None:
            shown = left.formula or str(left.value or "")
            _add(
                changes,
                sheet=new.name,
                cell=ref,
                type_label="célula apagada",
                category="conteudo",
                message="Célula presente só na planilha original.",
                before_raw=shown,
                before_masked=_mask_formula_or_blank(left.formula) if left.formula else _mask_scalar(shown),
            )
            continue
        assert left is not None and right is not None
        if (left.formula or "") != (right.formula or ""):
            _add(
                changes,
                sheet=new.name,
                cell=ref,
                type_label="fórmula alterada",
                category="conteudo",
                message="A fórmula da célula mudou.",
                before_raw=left.formula or "",
                after_raw=right.formula or "",
                before_masked=_mask_formula_or_blank(left.formula),
                after_masked=_mask_formula_or_blank(right.formula),
            )
        left_value = str(left.value or "")
        right_value = str(right.value or "")
        if left_value != right_value:
            same_formula = (left.formula or "") == (right.formula or "") and bool(left.formula or right.formula)
            _add(
                changes,
                sheet=new.name,
                cell=ref,
                type_label="valor em cache" if same_formula else "valor alterado",
                category="conteudo",
                message=(
                    "A fórmula é a mesma e o valor em cache mudou. "
                    "Em geral uma célula de origem foi alterada e o arquivo foi salvo de novo."
                    if same_formula
                    else "O valor armazenado na célula mudou."
                ),
                before_raw=left_value,
                after_raw=right_value,
            )


def _compare_hidden(old: Sheet, new: Sheet, changes: list[DiffChange], *, columns: bool) -> None:
    before = old.hidden_cols if columns else old.hidden_rows
    after = new.hidden_cols if columns else new.hidden_rows
    hidden_now = after - before
    shown_again = before - after
    noun = "Coluna" if columns else "Linha"
    for start, end in contiguous_groups(hidden_now):
        label = f"{index_to_col(start)}:{index_to_col(end)}" if columns else format_group(start, end)
        if columns and start == end:
            label = index_to_col(start)
        _add(
            changes,
            sheet=new.name,
            cell=label,
            type_label="coluna ocultada" if columns else "linha ocultada",
            category="estrutura",
            message=f"{noun} que estava visível passou a ficar oculta.",
        )
    for start, end in contiguous_groups(shown_again):
        label = f"{index_to_col(start)}:{index_to_col(end)}" if columns else format_group(start, end)
        if columns and start == end:
            label = index_to_col(start)
        _add(
            changes,
            sheet=new.name,
            cell=label,
            type_label="coluna reexibida" if columns else "linha reexibida",
            category="estrutura",
            message=f"{noun} que estava oculta voltou a aparecer.",
        )


def _compare_comments(old: Sheet, new: Sheet, changes: list[DiffChange]) -> None:
    def keyed(sheet: Sheet) -> dict[tuple[str, str], Comment]:
        return {(_comment_key(item), item.kind): item for item in sheet.comments}

    before = keyed(old)
    after = keyed(new)
    for key in sorted(set(before) | set(after)):
        left = before.get(key)
        right = after.get(key)
        kind = "comentário em thread" if key[1] == "thread" else "nota"
        if left is None and right is not None:
            masked, _raw = _comment_payload(right, show=False)
            _, raw_full = _comment_payload(right, show=True)
            _add(
                changes,
                sheet=new.name,
                cell=key[0],
                type_label="comentário novo",
                category="conteudo",
                message=f"Há {kind} novo nesta célula.",
                after_raw=raw_full,
                after_masked=masked,
            )
        elif right is None and left is not None:
            masked, _raw = _comment_payload(left, show=False)
            _, raw_full = _comment_payload(left, show=True)
            _add(
                changes,
                sheet=new.name,
                cell=key[0],
                type_label="comentário removido",
                category="conteudo",
                message=f"{kind.capitalize()} removido desta célula.",
                before_raw=raw_full,
                before_masked=masked,
            )
        elif left is not None and right is not None and (
            left.text != right.text or (left.author or "") != (right.author or "")
        ):
            before_masked, _ = _comment_payload(left, show=False)
            after_masked, _ = _comment_payload(right, show=False)
            _, before_raw = _comment_payload(left, show=True)
            _, after_raw = _comment_payload(right, show=True)
            _add(
                changes,
                sheet=new.name,
                cell=key[0],
                type_label="comentário editado",
                category="conteudo",
                message=f"{kind.capitalize()} alterado nesta célula.",
                before_raw=before_raw,
                after_raw=after_raw,
                before_masked=before_masked,
                after_masked=after_masked,
            )


def _compare_sheet_pair(old: Sheet, new: Sheet, changes: list[DiffChange], *, renamed: bool) -> None:
    if renamed:
        _add(
            changes,
            sheet=new.name,
            cell="",
            type_label="aba renomeada",
            category="estrutura",
            message=f"Aba «{old.name}» passou a se chamar «{new.name}».",
            before_raw=old.name,
            after_raw=new.name,
            before_masked=old.name,
            after_masked=new.name,
        )
    if old.state != new.state:
        _add(
            changes,
            sheet=new.name,
            cell="",
            type_label="visibilidade da aba",
            category="estrutura",
            message="O estado da aba mudou (visível, oculta ou muito oculta).",
            before_raw=_STATE.get(old.state, old.state),
            after_raw=_STATE.get(new.state, new.state),
            before_masked=_STATE.get(old.state, old.state),
            after_masked=_STATE.get(new.state, new.state),
        )
    _compare_cells(old, new, changes)
    _compare_hidden(old, new, changes, columns=False)
    _compare_hidden(old, new, changes, columns=True)
    _compare_comments(old, new, changes)


def _name_key(item: DefinedName) -> tuple[str, str]:
    return (item.name.casefold(), (item.local_sheet or "").casefold())


def _compare_names(original: Workbook, received: Workbook, changes: list[DiffChange]) -> None:
    before = {_name_key(item): item for item in original.defined_names}
    after = {_name_key(item): item for item in received.defined_names}
    for key in sorted(set(before) | set(after)):
        left = before.get(key)
        right = after.get(key)
        label = (right or left).name if (right or left) else key[0]
        sheet = (right or left).local_sheet or "" if (right or left) else ""
        if left is None and right is not None:
            _add(
                changes,
                sheet=sheet,
                cell=label,
                type_label="nome definido",
                category="estrutura",
                message="Nome definido presente só na planilha recebida.",
                after_raw=right.formula,
                after_masked=mask_path(mask_formula(right.formula)),
            )
        elif right is None and left is not None:
            _add(
                changes,
                sheet=sheet,
                cell=label,
                type_label="nome definido",
                category="estrutura",
                message="Nome definido presente só na planilha original.",
                before_raw=left.formula,
                before_masked=mask_path(mask_formula(left.formula)),
            )
        elif left is not None and right is not None and (
            left.formula != right.formula or left.hidden != right.hidden
        ):
            _add(
                changes,
                sheet=sheet,
                cell=label,
                type_label="nome definido",
                category="estrutura",
                message="Nome definido alterado (fórmula ou visibilidade).",
                before_raw=left.formula,
                after_raw=right.formula,
                before_masked=mask_path(mask_formula(left.formula)),
                after_masked=mask_path(mask_formula(right.formula)),
            )


def _compare_links(original: Workbook, received: Workbook, changes: list[DiffChange]) -> None:
    before = set(original.external_links)
    after = set(received.external_links)
    removed = sorted(before - after)
    added = sorted(after - before)
    if len(removed) == 1 and len(added) == 1:
        _add(
            changes,
            sheet="",
            cell="",
            type_label="vínculo externo",
            category="estrutura",
            message="Vínculo externo alterado.",
            before_raw=removed[0],
            after_raw=added[0],
            before_masked=mask_path(removed[0]),
            after_masked=mask_path(added[0]),
        )
        return
    for link in removed:
        _add(
            changes,
            sheet="",
            cell="",
            type_label="vínculo externo",
            category="estrutura",
            message="Vínculo externo presente só na planilha original.",
            before_raw=link,
            before_masked=mask_path(link),
        )
    for link in added:
        _add(
            changes,
            sheet="",
            cell="",
            type_label="vínculo externo",
            category="estrutura",
            message="Vínculo externo presente só na planilha recebida.",
            after_raw=link,
            after_masked=mask_path(link),
        )


def _meta_lookup(props: dict[str, str]) -> dict[str, tuple[str, str]]:
    return {key.casefold(): (key, value) for key, value in props.items()}


def _compare_metadata(
    original: dict[str, str], received: dict[str, str]
) -> tuple[list[MetaRow], list[DiffChange]]:
    left = _meta_lookup(original)
    right = _meta_lookup(received)
    rows: list[MetaRow] = []
    changes: list[DiffChange] = []
    for key, label in _META_FIELDS:
        before = left.get(key.casefold(), ("", ""))[1]
        after = right.get(key.casefold(), ("", ""))[1]
        changed = before != after
        rows.append(
            MetaRow(
                key=key,
                label=label,
                before_masked=_mask_scalar(before),
                after_masked=_mask_scalar(after),
                before_raw=_blank(before),
                after_raw=_blank(after),
                changed=changed,
            )
        )
        if changed:
            _add(
                changes,
                sheet="",
                cell=key,
                type_label="metadado",
                category="metadado",
                message=f"{label} mudou. É quem salvou por último, ou uma propriedade do arquivo, e pode ser editado.",
                before_raw=before,
                after_raw=after,
            )
    return rows, changes


def compare_workbooks(
    original: Workbook,
    received: Workbook,
    *,
    original_label: str,
    received_label: str,
    original_props: dict[str, str],
    received_props: dict[str, str],
    identical: bool,
) -> DiffReport:
    _drop_legacy_thread_placeholders(original)
    _drop_legacy_thread_placeholders(received)
    changes: list[DiffChange] = []
    old_by = {sheet.name.casefold(): sheet for sheet in original.sheets}
    new_by = {sheet.name.casefold(): sheet for sheet in received.sheets}
    common = set(old_by) & set(new_by)
    removed = [old_by[key] for key in old_by if key not in common]
    added = [new_by[key] for key in new_by if key not in common]
    renamed, removed, added = _match_renames(removed, added)
    for key in sorted(common):
        _compare_sheet_pair(old_by[key], new_by[key], changes, renamed=False)
    for old, new, _flag in renamed:
        _compare_sheet_pair(old, new, changes, renamed=True)
    for sheet in removed:
        _add(
            changes,
            sheet=sheet.name,
            cell="",
            type_label="aba apagada",
            category="estrutura",
            message="Aba presente só na planilha original.",
            before_raw=sheet.name,
            before_masked=sheet.name,
        )
    for sheet in added:
        _add(
            changes,
            sheet=sheet.name,
            cell="",
            type_label="aba criada",
            category="estrutura",
            message="Aba presente só na planilha recebida.",
            after_raw=sheet.name,
            after_masked=sheet.name,
        )
    _compare_names(original, received, changes)
    _compare_links(original, received, changes)
    metadata, meta_changes = _compare_metadata(original_props, received_props)
    changes.extend(meta_changes)
    changes.sort(key=lambda item: (_CATEGORY_RANK.get(item.category, 9), item.sheet, item.cell, item.type_label))
    if identical:
        headline: str | None = IDENTICAL
        code = 0
        changes = []
    elif changes and all(item.category == "metadado" for item in changes):
        headline = METADATA_ONLY
        code = 1
    elif changes:
        headline = None
        code = 1
    else:
        headline = None
        code = 0
    return DiffReport(
        original=original_label,
        received=received_label,
        changes=changes,
        metadata=metadata,
        identical=identical,
        headline=headline,
        exit_code=code,
    )


def _side(change: DiffChange, *, show: bool, before: bool) -> str:
    if show:
        return change.before_raw if before else change.after_raw
    return change.before_masked if before else change.after_masked


def render_diff_text(report: DiffReport, *, show: bool, color: bool) -> str:
    lines = [f"{report.original} → {report.received}"]
    if report.headline:
        lines.append(_paint(report.headline, _BOLD, color=color))
    if report.identical:
        lines.append(LIMITS)
        lines.append(DISCLAIMER)
        return "\n".join(lines) + "\n"
    for change in report.changes:
        label = _paint(change.type_label, _CATEGORY_COLOR.get(change.category, ""), color=color)
        sheet = change.sheet or "—"
        cell = change.cell or "—"
        lines.append(f"  {sheet} › {cell} › {label}")
        lines.append(f"    {change.message}")
        lines.append(f"    antes: {_side(change, show=show, before=True)}")
        lines.append(f"    depois: {_side(change, show=show, before=False)}")
    counts = _summary(report)
    lines.append("---")
    lines.append(
        "Resumo: "
        f"{counts['conteudo']} conteúdo, {counts['estrutura']} estrutura, "
        f"{counts['metadado']} metadado ({counts['total']} no total)."
    )
    lines.append(LIMITS)
    lines.append(DISCLAIMER)
    return "\n".join(lines) + "\n"


def _summary(report: DiffReport) -> dict[str, int]:
    counts = {"conteudo": 0, "estrutura": 0, "metadado": 0, "total": len(report.changes)}
    for change in report.changes:
        if change.category in counts:
            counts[change.category] += 1
    return counts


def _paint(text: str, code: str, *, color: bool) -> str:
    if not color or not code:
        return text
    return f"{code}{text}{_RESET}"


def render_diff_json(report: DiffReport) -> str:
    counts = _summary(report)
    payload = {
        "tool": "oculto-scan",
        "command": "diff",
        "version": __version__,
        "disclaimer": DISCLAIMER,
        "limits": LIMITS,
        "original": report.original,
        "received": report.received,
        "identical": report.identical,
        "headline": report.headline,
        "summary": counts,
        "metadata": [
            {
                "key": row.key,
                "label": row.label,
                "before": row.before_masked,
                "after": row.after_masked,
                "changed": row.changed,
            }
            for row in report.metadata
        ],
        "changes": [
            {
                "sheet": change.sheet,
                "cell": change.cell,
                "type": change.type_label,
                "category": change.category,
                "message": change.message,
                "before": change.before_masked,
                "after": change.after_masked,
            }
            for change in report.changes
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def render_diff_html(report: DiffReport, *, show: bool, generated_at: datetime | None = None) -> str:
    when = generated_at if generated_at is not None else datetime.now().astimezone()
    counts = _summary(report)
    banner = f'<p class="revelado">{_esc(REVEALED_BANNER)}</p>' if show else ""
    rows: list[str] = []
    for change in report.changes:
        rows.append(
            "<tr class=\"cat-{category}\">"
            "<td>{sheet}</td><td>{cell}</td><td>{kind}</td>"
            "<td class=\"value\">{before}</td><td class=\"value\">{after}</td><td>{message}</td>"
            "</tr>".format(
                category=_esc(change.category),
                sheet=_esc(change.sheet or "—"),
                cell=_esc(change.cell or "—"),
                kind=_esc(change.type_label),
                before=_esc(_side(change, show=show, before=True)),
                after=_esc(_side(change, show=show, before=False)),
                message=_esc(change.message),
            )
        )
    meta_rows: list[str] = []
    for row in report.metadata:
        before = row.before_raw if show else row.before_masked
        after = row.after_raw if show else row.after_masked
        mark = " mudou" if row.changed else ""
        meta_rows.append(
            f"<tr class=\"{'changed' if row.changed else 'same'}\">"
            f"<td>{_esc(row.label)}</td><td class=\"value\">{_esc(before)}</td>"
            f"<td class=\"value\">{_esc(after)}</td><td>{_esc(mark.strip() or 'igual')}</td></tr>"
        )
    headline = f"<p class=\"headline\">{_esc(report.headline)}</p>" if report.headline else ""
    table = (
        "<table><thead><tr><th>Aba</th><th>Célula</th><th>Mudança</th>"
        "<th>Antes</th><th>Depois</th><th>Explicação</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
        if rows
        else "<p class=\"empty\">Nenhuma diferença de célula, aba, comentário ou vínculo.</p>"
    )
    return _HTML.format(
        banner=banner,
        stamp=_esc(_format_stamp(when)),
        version=_esc(__version__),
        original=_esc(report.original),
        received=_esc(report.received),
        headline=headline,
        conteudo=_esc(counts["conteudo"]),
        estrutura=_esc(counts["estrutura"]),
        metadado=_esc(counts["metadado"]),
        total=_esc(counts["total"]),
        table=table,
        meta="".join(meta_rows),
        limits=_esc(LIMITS),
        disclaimer=_esc(DISCLAIMER),
    )


def load_diff(original: Path, received: Path) -> DiffReport:
    identical = original.resolve() != received.resolve() and original.read_bytes() == received.read_bytes()
    if original.resolve() == received.resolve():
        identical = True
    if identical:
        return DiffReport(
            original=str(original),
            received=str(received),
            changes=[],
            metadata=[],
            identical=True,
            headline=IDENTICAL,
            exit_code=0,
        )
    left = load_workbook(original)
    right = load_workbook(received)
    return compare_workbooks(
        left,
        right,
        original_label=str(original),
        received_label=str(received),
        original_props=read_document_properties(original),
        received_props=read_document_properties(received),
        identical=False,
    )


def run_diff(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="oculto-scan diff",
        description=(
            "Compara a planilha enviada com a que voltou. Mostra o que mudou e quem salvou por último. "
            "Não mostra IP nem histórico por pessoa."
        ),
    )
    parser.add_argument("original", type=Path, help="planilha enviada")
    parser.add_argument("recebido", type=Path, help="planilha que voltou")
    parser.add_argument("--format", dest="formato", choices=("texto", "json", "html"), default="texto")
    parser.add_argument(
        "--output",
        type=Path,
        help="arquivo HTML (padrão: oculto-scan-diff.html, ou oculto-scan-diff-revelado.html com --show)",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="mostra os valores no terminal e no HTML; o JSON continua mascarado",
    )
    parser.add_argument("--no-color", action="store_true", help="desliga cores ANSI no texto")
    args = parser.parse_args(argv)
    if args.output is not None and args.formato != "html":
        print("--output é o caminho do relatório HTML; use junto com --format html.", file=sys.stderr)
        return 2
    for path in (args.original, args.recebido):
        if not path.exists():
            print(f"Caminho não encontrado: {path}", file=sys.stderr)
            return 2
        if not path.is_file() or path.suffix.lower() not in _SUFFIXES:
            print(f"Informe um arquivo .xlsx ou .xlsm: {path}", file=sys.stderr)
            return 2
    try:
        report = load_diff(args.original, args.recebido)
    except (ZipSafetyError, WorkbookParseError, OSError) as exc:
        print(f"Não foi possível comparar ({exc}).", file=sys.stderr)
        return 2
    if args.formato == "json":
        sys.stdout.write(render_diff_json(report))
    elif args.formato == "html":
        if args.output is not None:
            target = args.output
        elif args.show:
            target = Path("oculto-scan-diff-revelado.html")
        else:
            target = Path("oculto-scan-diff.html")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_diff_html(report, show=args.show), encoding="utf-8")
        print(f"Relatório salvo em {target}")
    else:
        sys.stdout.write(
            render_diff_text(report, show=args.show, color=stdout_wants_color(no_color=args.no_color))
        )
    return report.exit_code


_HTML = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>oculto-scan — diferenças</title>
<style>
  :root {{
    --ink: #1c1915; --muted: #5c564c; --line: #e4ddd2; --paper: #f7f4ef; --card: #fffdf9;
    --alto: #9f2d2d; --alto-bg: #f8e4e1; --medio: #8a5a12; --medio-bg: #f8efd4;
    --info: #1f5f6b; --info-bg: #e3f0f2;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; color: var(--ink); background: var(--paper);
    font: 15px/1.45 "Segoe UI", Calibri, "Liberation Sans", sans-serif; }}
  .revelado {{ margin: 0; padding: 0.9rem 1.25rem; background: #9b1c1c; color: #fff;
    font-weight: 700; text-align: center; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 2rem 1.25rem 3rem; }}
  h1 {{ font-size: 1.8rem; margin: 0 0 0.2rem; }}
  h2 {{ font-size: 1.05rem; margin: 1.6rem 0 0.6rem; }}
  .meta {{ display: flex; flex-wrap: wrap; gap: 1.25rem; margin: 1rem 0 0; }}
  .meta dt {{ font-size: 0.75rem; text-transform: uppercase; color: var(--muted); }}
  .meta dd {{ margin: 0.15rem 0 0; font-weight: 650; word-break: break-word; }}
  .headline {{ background: #fff6d8; border: 1px solid var(--line); padding: 0.8rem 1rem; font-weight: 700; }}
  .resumo {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.75rem; margin: 1.5rem 0; }}
  .resumo article {{ background: var(--card); border: 1px solid var(--line);
    border-radius: 10px; padding: 0.85rem 1rem; }}
  .resumo strong {{ display: block; font-size: 1.6rem; }}
  table {{ width: 100%; border-collapse: collapse; background: var(--card); }}
  th, td {{ text-align: left; vertical-align: top; padding: 0.55rem 0.65rem; border-bottom: 1px solid var(--line); }}
  th {{ font-size: 0.75rem; text-transform: uppercase; color: var(--muted); }}
  tr.cat-conteudo td {{ background: var(--alto-bg); }}
  tr.cat-estrutura td {{ background: var(--medio-bg); }}
  tr.cat-metadado td {{ background: var(--info-bg); }}
  tr.changed td {{ background: var(--info-bg); }}
  td.value {{ font-family: Consolas, "Courier New", monospace; font-size: 0.86rem; word-break: break-word; }}
  footer {{ margin-top: 2rem; padding-top: 0.8rem; border-top: 1px solid var(--line); color: var(--muted); }}
  @media print {{
    body {{ background: #fff; }} main {{ max-width: none; padding: 0; }}
    tr, .resumo article {{ break-inside: avoid; }}
    * {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  }}
</style>
</head>
<body>
{banner}
<main>
  <header>
    <h1>oculto-scan diff</h1>
    <p>O que mudou entre a planilha enviada e a que voltou, e quem salvou por último.</p>
    <dl class="meta">
      <div><dt>Data</dt><dd>{stamp}</dd></div>
      <div><dt>Versão</dt><dd>{version}</dd></div>
      <div><dt>Original</dt><dd>{original}</dd></div>
      <div><dt>Recebido</dt><dd>{received}</dd></div>
    </dl>
  </header>
  {headline}
  <section class="resumo" aria-label="Quadro-resumo">
    <article><strong>{conteudo}</strong><span>conteúdo</span></article>
    <article><strong>{estrutura}</strong><span>estrutura</span></article>
    <article><strong>{metadado}</strong><span>metadado</span></article>
    <article><strong>{total}</strong><span>no total</span></article>
  </section>
  {table}
  <h2>Quem salvou</h2>
  <table><thead><tr><th>Propriedade</th><th>Antes</th><th>Depois</th><th></th></tr></thead>
  <tbody>{meta}</tbody></table>
  <footer><p>{limits}</p><p>{disclaimer}</p></footer>
</main>
</body>
</html>
"""

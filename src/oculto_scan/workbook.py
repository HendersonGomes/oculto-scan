"""Read an .xlsx/.xlsm package with zipfile and defusedxml.

Macros are never executed. External link targets are recorded as text and
never opened. Shared formulas are expanded with a relative shift so a
copied margin formula is still visible to the rules.
"""

from __future__ import annotations

import posixpath
import re
import zipfile
from pathlib import Path

from defusedxml import ElementTree as DefusedET
from defusedxml.common import DefusedXmlException

from oculto_scan.models import Cell, Comment, DefinedName, Sheet, Workbook
from oculto_scan.refs import col_to_index, index_to_col, split_cell
from oculto_scan.zipsafe import ZipSafetyError, open_office_bytes, open_office_package, read_member

# A cell token, not a function (``LOG10(``) and not glued to a name (``ATAN2``, ``Total10``).
_CELL_TOKEN = re.compile(r"(?<![A-Za-z0-9_])(\$?)([A-Z]{1,3})(\$?)(\d+)(?![A-Za-z0-9_(])")
_QUOTED = re.compile(r'"(?:[^"]|"")*"')
_BUILTIN_NAME = re.compile(r"^_xlnm\.", re.IGNORECASE)
_PRINT_AREA = re.compile(r"(?i)^_xlnm\.print_area$")
_AREA_REF = re.compile(
    r"(?:(?:'((?:[^']|'')*)'|([A-Za-z0-9_\-. \u00C0-\u024F]+))!)?"
    r"(\$?[A-Z]{1,3}\$?\d+):(\$?[A-Z]{1,3}\$?\d+)"
)
_SPAN_LIMIT = 4096
_NARROW_WIDTH = 0.5
_SHORT_HEIGHT = 0.5

_IDENTITY_META = {
    "creator",
    "lastmodifiedby",
    "company",
    "manager",
}
_TEXT_META = _IDENTITY_META | {
    "title",
    "subject",
    "description",
    "keywords",
    "category",
    "template",
}


class WorkbookParseError(Exception):
    """The package is a zip but not a readable workbook."""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _attr(element: DefusedET.Element, name: str) -> str | None:  # type: ignore[name-defined]
    if name in element.attrib:
        return element.attrib[name]
    suffix = "}" + name
    for key, value in element.attrib.items():
        if key == name or key.endswith(suffix):
            return value
    return None


def _parse_xml(payload: bytes) -> DefusedET.Element:  # type: ignore[name-defined]
    try:
        return DefusedET.fromstring(payload)
    except DefusedXmlException as exc:
        raise ZipSafetyError("xml recusou entidade, DTD ou expansão") from exc
    except Exception as exc:  # ElementTree.ParseError and friends
        raise WorkbookParseError("xml malformado") from exc


def _text_content(element: DefusedET.Element) -> str:  # type: ignore[name-defined]
    """Collect spreadsheet text nodes.

    Legacy comments and shared strings use ``<t>``. Threaded comments use
    ``<text>``. A ``<text>`` parent of ``<t>`` has no direct text, so both
    can be read without duplicating the string.
    """
    chunks: list[str] = []
    for node in element.iter():
        local = _local(node.tag)
        if local in {"t", "text"} and node.text:
            chunks.append(node.text)
    return "".join(chunks)


def _resolve(base_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    base_dir = posixpath.dirname(base_part)
    return posixpath.normpath(posixpath.join(base_dir, target))


def _parse_rels(payload: bytes) -> list[tuple[str, str, str, str]]:
    root = _parse_xml(payload)
    rels: list[tuple[str, str, str, str]] = []
    for node in root:
        if _local(node.tag) != "Relationship":
            continue
        rels.append(
            (
                _attr(node, "Id") or "",
                _attr(node, "Type") or "",
                _attr(node, "Target") or "",
                _attr(node, "TargetMode") or "",
            )
        )
    return rels


def _shift_outside(formula: str, delta_row: int, delta_col: int) -> str:
    def _repl(match: re.Match[str]) -> str:
        abs_col, letters, abs_row, row_text = match.groups()
        column = col_to_index(letters)
        row = int(row_text)
        if not abs_col:
            column += delta_col
        if not abs_row:
            row += delta_row
        if column < 1 or row < 1:
            return match.group(0)
        return f"{abs_col}{index_to_col(column)}{abs_row}{row}"

    return _CELL_TOKEN.sub(_repl, formula)


def _shift_formula(formula: str, delta_row: int, delta_col: int) -> str:
    """Shift cell references. Quoted text and names like ``LOG10`` stay put."""
    if not delta_row and not delta_col:
        return formula
    parts: list[str] = []
    cursor = 0
    for match in _QUOTED.finditer(formula):
        parts.append(_shift_outside(formula[cursor : match.start()], delta_row, delta_col))
        parts.append(match.group(0))
        cursor = match.end()
    parts.append(_shift_outside(formula[cursor:], delta_row, delta_col))
    return "".join(parts)


def _remember_span(target: set[int], spans: list[tuple[int, int]], start: int, end: int) -> None:
    if end < start:
        return
    if end - start + 1 <= _SPAN_LIMIT:
        target.update(range(start, end + 1))
    else:
        spans.append((start, end))


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "on"}


def _cell_value(cell_el: DefusedET.Element, shared: list[str]) -> str | None:  # type: ignore[name-defined]
    kind = _attr(cell_el, "t") or ""
    if kind == "inlineStr":
        for child in cell_el:
            if _local(child.tag) == "is":
                return _text_content(child)
        return _text_content(cell_el)
    value_node = None
    for child in cell_el:
        if _local(child.tag) == "v":
            value_node = child
            break
    if value_node is None or value_node.text is None:
        return None
    raw = value_node.text
    if kind == "s":
        try:
            return shared[int(raw)]
        except (ValueError, IndexError):
            return raw
    return raw


def _load_shared_strings(parts: dict[str, bytes]) -> list[str]:
    payload = parts.get("xl/sharedstrings.xml")
    if payload is None:
        return []
    root = _parse_xml(payload)
    values: list[str] = []
    for node in root:
        if _local(node.tag) == "si":
            values.append(_text_content(node))
    return values


def _style_formats(parts: dict[str, bytes]) -> dict[int, str]:
    payload = parts.get("xl/styles.xml")
    if payload is None:
        return {}
    root = _parse_xml(payload)
    formats: dict[str, str] = {}
    cell_xfs: list[str] = []
    for node in root.iter():
        local = _local(node.tag)
        if local == "numFmt":
            formats[_attr(node, "numFmtId") or ""] = _attr(node, "formatCode") or ""
        elif local == "cellXfs":
            for child in list(node):
                if _local(child.tag) != "xf":
                    continue
                cell_xfs.append(formats.get(_attr(child, "numFmtId") or "", ""))
    return {index: code for index, code in enumerate(cell_xfs) if code}


def _sheet_cells(  # type: ignore[name-defined]
    root: DefusedET.Element,
    shared: list[str],
    xf_formats: dict[int, str],
) -> tuple[list[Cell], set[int], set[int], list[tuple[int, int]], list[tuple[int, int]], set[int], set[int]]:
    hidden_rows: set[int] = set()
    hidden_cols: set[int] = set()
    hidden_row_spans: list[tuple[int, int]] = []
    hidden_col_spans: list[tuple[int, int]] = []
    narrow_cols: set[int] = set()
    short_rows: set[int] = set()
    for node in root.iter():
        if _local(node.tag) != "col":
            continue
        try:
            start = int(_attr(node, "min") or "0")
            end = int(_attr(node, "max") or "0")
        except ValueError:
            continue
        if start < 1 or end < start:
            continue
        hidden = _truthy(_attr(node, "hidden"))
        if hidden:
            _remember_span(hidden_cols, hidden_col_spans, start, end)
            continue
        try:
            width = float(_attr(node, "width") or "999")
        except ValueError:
            width = 999
        if 0 <= width <= _NARROW_WIDTH:
            _remember_span(narrow_cols, [], start, end)

    masters: dict[str, tuple[str, int, int]] = {}
    pending: list[tuple[Cell, str]] = []
    cells: list[Cell] = []

    for row_el in root.iter():
        if _local(row_el.tag) != "row":
            continue
        try:
            row_index = int(_attr(row_el, "r") or "0")
        except ValueError:
            row_index = 0
        if _truthy(_attr(row_el, "hidden")) and row_index:
            hidden_rows.add(row_index)
        elif row_index:
            height_text = _attr(row_el, "ht")
            if height_text:
                try:
                    if float(height_text) <= _SHORT_HEIGHT:
                        short_rows.add(row_index)
                except ValueError:
                    pass
        for cell_el in row_el:
            if _local(cell_el.tag) != "c":
                continue
            ref = _attr(cell_el, "r") or ""
            parsed = split_cell(ref) if ref else None
            if parsed:
                row, col = parsed
            else:
                row, col = row_index, 0
            formula = None
            shared_id = None
            for child in cell_el:
                if _local(child.tag) != "f":
                    continue
                shared_id = _attr(child, "si")
                body = (child.text or "").strip()
                if body:
                    formula = body
                break
            style_index = _attr(cell_el, "s")
            number_format = None
            if style_index and style_index.isdigit():
                number_format = xf_formats.get(int(style_index)) or None
            cell = Cell(
                ref=ref or f"R{row}",
                row=row,
                col=col,
                formula=formula,
                value=_cell_value(cell_el, shared),
                number_format=number_format,
            )
            if formula and shared_id:
                masters[shared_id] = (formula, row, col)
                cells.append(cell)
            elif shared_id and not formula:
                pending.append((cell, shared_id))
                cells.append(cell)
            else:
                cells.append(cell)

    for cell, shared_id in pending:
        master = masters.get(shared_id)
        if not master:
            continue
        formula, master_row, master_col = master
        cell.formula = _shift_formula(formula, cell.row - master_row, cell.col - master_col)
    return cells, hidden_rows, hidden_cols, hidden_row_spans, hidden_col_spans, narrow_cols, short_rows


def _comments_from(payload: bytes, kind: str) -> list[Comment]:
    root = _parse_xml(payload)
    authors: list[str] = []
    for node in root.iter():
        if _local(node.tag) == "author" and node.text:
            authors.append(node.text)
    comments: list[Comment] = []
    for node in root.iter():
        local = _local(node.tag)
        if local not in {"comment", "threadedComment"}:
            continue
        ref = _attr(node, "ref") or ""
        author = _attr(node, "author") or _attr(node, "personId")
        author_id = _attr(node, "authorId")
        if author_id and author_id.isdigit():
            index = int(author_id)
            if 0 <= index < len(authors):
                author = authors[index]
        text = _text_content(node)
        if ref or text:
            comments.append(Comment(ref=ref, text=text, author=author, kind=kind))
    return comments


# Properties compared by ``diff``. Kept out of the scan findings on purpose.
_DIFF_META_KEYS = {
    "creator",
    "lastmodifiedby",
    "created",
    "modified",
    "lastprinted",
    "revision",
    "application",
    "appversion",
    "company",
    "manager",
}


def _metadata(parts: dict[str, bytes], keys: set[str] | None = None) -> dict[str, str]:
    allowed = _TEXT_META if keys is None else keys
    found: dict[str, str] = {}
    core = parts.get("docprops/core.xml")
    if core:
        root = _parse_xml(core)
        for node in root.iter():
            name = _local(node.tag)
            if name.casefold() in allowed and node.text and node.text.strip():
                found[name] = node.text.strip()
    app = parts.get("docprops/app.xml")
    if app:
        root = _parse_xml(app)
        for node in root:
            name = _local(node.tag)
            if name.casefold() in allowed and node.text and node.text.strip():
                found[name] = node.text.strip()
    custom = parts.get("docprops/custom.xml")
    if custom:
        root = _parse_xml(custom)
        for node in root.iter():
            if _local(node.tag) != "property":
                continue
            name = _attr(node, "name") or "custom"
            text = _text_content(node) or (node.text or "")
            if text.strip():
                found[f"custom:{name}"] = text.strip()
    return found


def _local_sheet_name(sheets: list[Sheet], local: str | None) -> str | None:
    if local and local.isdigit():
        index = int(local)
        if 0 <= index < len(sheets):
            return sheets[index].name
    return None


def _print_rects(formula: str, fallback_sheet: str | None) -> list[tuple[str, tuple[int, int, int, int]]]:
    found: list[tuple[str, tuple[int, int, int, int]]] = []
    for match in _AREA_REF.finditer(formula or ""):
        quoted, plain, left, right = match.groups()
        sheet_name = _unescape_sheet(quoted) if quoted else (plain or fallback_sheet or "")
        start = split_cell(left)
        end = split_cell(right)
        if not sheet_name or not start or not end:
            continue
        r1, c1 = start
        r2, c2 = end
        if r1 > r2:
            r1, r2 = r2, r1
        if c1 > c2:
            c1, c2 = c2, c1
        found.append((sheet_name, (r1, c1, r2, c2)))
    return found


def _unescape_sheet(token: str) -> str:
    return token.replace("''", "'")


def _defined_names(  # type: ignore[name-defined]
    root: DefusedET.Element, sheets: list[Sheet]
) -> tuple[list[DefinedName], dict[str, list[tuple[int, int, int, int]]]]:
    names: list[DefinedName] = []
    areas: dict[str, list[tuple[int, int, int, int]]] = {}
    for node in root.iter():
        if _local(node.tag) != "definedName":
            continue
        name = _attr(node, "name") or ""
        if not name:
            continue
        formula = (node.text or "").strip()
        local_sheet = _local_sheet_name(sheets, _attr(node, "localSheetId"))
        if _PRINT_AREA.match(name):
            for sheet_name, rect in _print_rects(formula, local_sheet):
                areas.setdefault(sheet_name, []).append(rect)
            continue
        if _BUILTIN_NAME.match(name):
            continue
        names.append(
            DefinedName(
                name=name,
                formula=formula,
                hidden=_truthy(_attr(node, "hidden")),
                local_sheet=local_sheet,
            )
        )
    return names, areas


def _person_emails(parts: dict[str, bytes]) -> dict[str, str]:
    found: dict[str, str] = {}
    for part_name, payload in parts.items():
        folded = part_name.casefold()
        if not folded.endswith(".xml") or "person" not in folded:
            continue
        try:
            root = _parse_xml(payload)
        except (ZipSafetyError, WorkbookParseError):
            continue
        for node in root.iter():
            if _local(node.tag) != "person":
                continue
            email = (_attr(node, "userId") or "").strip()
            if "@" not in email:
                continue
            found[f"email-{len(found) + 1}"] = email
    return found


def _person_texts(parts: dict[str, bytes]) -> list[str]:
    """Names and ids from persons.xml. E-mails stay in the metadata findings."""
    texts: list[str] = []
    seen: set[str] = set()
    for part_name, payload in parts.items():
        folded = part_name.casefold()
        if not folded.endswith(".xml") or "person" not in folded:
            continue
        try:
            root = _parse_xml(payload)
        except (ZipSafetyError, WorkbookParseError):
            continue
        for node in root.iter():
            if _local(node.tag) != "person":
                continue
            for key in ("displayName", "userId", "providerId"):
                value = (_attr(node, key) or "").strip()
                if not value or "@" in value or value.casefold() in seen:
                    continue
                seen.add(value.casefold())
                texts.append(value)
    return texts


def _external_cache(parts: dict[str, bytes]) -> list[tuple[str, Cell]]:
    cached: list[tuple[str, Cell]] = []
    for part_name, payload in parts.items():
        folded = part_name.casefold()
        if "externallink" not in folded or not folded.endswith(".xml") or folded.endswith(".rels"):
            continue
        try:
            root = _parse_xml(payload)
        except (ZipSafetyError, WorkbookParseError):
            continue
        for node in root.iter():
            if _local(node.tag) != "cell":
                continue
            ref = _attr(node, "r") or ""
            value = None
            for child in node:
                if _local(child.tag) == "v" and child.text:
                    value = child.text
                    break
            if not value:
                continue
            parsed = split_cell(ref) if ref else None
            row, col = parsed if parsed else (0, 0)
            cached.append(("vínculo externo", Cell(ref=ref, row=row, col=col, value=value)))
    return cached


def _read_parts(archive: zipfile.ZipFile, *, max_mb: int | None) -> dict[str, bytes]:
    parts: dict[str, bytes] = {}
    for info in archive.infolist():
        if info.is_dir():
            continue
        name = info.filename.replace("\\", "/").lstrip("/")
        parts[name] = read_member(archive, info, max_mb=max_mb)
        parts[name.casefold()] = parts[name]
    return parts


def read_document_properties(path: Path, *, max_mb: int | None = None) -> dict[str, str]:
    """Core and app properties for ``diff``. Scan findings stay on the smaller set."""
    archive = open_office_package(path, max_mb=max_mb)
    try:
        parts: dict[str, bytes] = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/").lstrip("/").casefold()
            if name in {"docprops/core.xml", "docprops/app.xml"}:
                parts[name] = read_member(archive, info, max_mb=max_mb)
    finally:
        archive.close()
    return _metadata(parts, _DIFF_META_KEYS)


def read_document_properties_bytes(data: bytes, *, max_mb: int | None = None) -> dict[str, str]:
    archive = open_office_bytes(data, max_mb=max_mb)
    try:
        parts: dict[str, bytes] = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/").lstrip("/").casefold()
            if name in {"docprops/core.xml", "docprops/app.xml"}:
                parts[name] = read_member(archive, info, max_mb=max_mb)
    finally:
        archive.close()
    return _metadata(parts, _DIFF_META_KEYS)


def load_workbook(path: Path, *, max_mb: int | None = None) -> Workbook:
    """Load workbook structure. Raises ZipSafetyError, FileTooLargeError or WorkbookParseError."""
    archive = open_office_package(path, max_mb=max_mb)
    try:
        parts = _read_parts(archive, max_mb=max_mb)
    finally:
        archive.close()
    return _workbook_from_parts(parts, label=str(path))


def load_workbook_bytes(data: bytes, nome: str, *, max_mb: int | None = None) -> Workbook:
    """Same as :func:`load_workbook` for an in-memory package. Does not touch the disk."""
    archive = open_office_bytes(data, max_mb=max_mb)
    try:
        parts = _read_parts(archive, max_mb=max_mb)
    finally:
        archive.close()
    return _workbook_from_parts(parts, label=nome)


def _connection_strings(parts: dict[str, bytes]) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()
    for name, payload in parts.items():
        folded = name.casefold()
        if not folded.endswith("connections.xml") or folded in seen:
            continue
        seen.add(folded)
        try:
            root = _parse_xml(payload)
        except (ZipSafetyError, WorkbookParseError):
            continue
        for node in root.iter():
            if node.text and node.text.strip():
                texts.append(node.text.strip())
            for value in node.attrib.values():
                if value and str(value).strip():
                    texts.append(str(value).strip())
    return texts


def _binary_strings(payload: bytes) -> list[str]:
    found: list[str] = []

    def take(chars: list[str]) -> None:
        if len(chars) < 4:
            return
        text = "".join(chars)
        folded = text.casefold()
        if "\\" in text or "impressora" in folded or "printer" in folded:
            found.append(text)

    chars: list[str] = []
    for byte in payload:
        if 32 <= byte < 127:
            chars.append(chr(byte))
        else:
            take(chars)
            chars = []
    take(chars)
    chars = []
    index = 0
    while index + 1 < len(payload):
        code = payload[index] | (payload[index + 1] << 8)
        index += 2
        if 32 <= code < 127:
            chars.append(chr(code))
        else:
            take(chars)
            chars = []
    take(chars)
    return found


def _printer_texts(parts: dict[str, bytes]) -> list[str]:
    texts: list[str] = []
    seen: set[str] = set()
    for name, payload in parts.items():
        folded = name.casefold()
        if "printersettings" not in folded or folded in seen:
            continue
        seen.add(folded)
        texts.extend(_binary_strings(payload))
    return texts


def _vba_bytes(parts: dict[str, bytes]) -> bytes | None:
    for name, payload in parts.items():
        if name.casefold() == "xl/vbaproject.bin":
            return payload
    return None


def _workbook_from_parts(parts: dict[str, bytes], *, label: str) -> Workbook:

    has_vba = any(name.casefold() == "xl/vbaproject.bin" for name in parts)
    workbook_xml = parts.get("xl/workbook.xml")
    if workbook_xml is None:
        raise WorkbookParseError("xl/workbook.xml ausente")

    root = _parse_xml(workbook_xml)
    rels_payload = parts.get("xl/_rels/workbook.xml.rels")
    rels = _parse_rels(rels_payload) if rels_payload else []
    rel_by_id = {rel_id: (rel_type, target, mode) for rel_id, rel_type, target, mode in rels}

    shared = _load_shared_strings(parts)
    xf_formats = _style_formats(parts)
    sheets: list[Sheet] = []
    external: list[str] = []

    for _rel_id, rel_type, target, mode in rels:
        # The link to xl/externalLinks/externalLink1.xml is internal.
        # The user-visible path is TargetMode=External or externalLinkPath.
        type_name = rel_type.rsplit("/", 1)[-1].lower()
        if target and (mode.lower() == "external" or type_name == "externallinkpath"):
            external.append(target)

    for node in root.iter():
        if _local(node.tag) != "sheet":
            continue
        name = _attr(node, "name") or "Sem nome"
        state = _attr(node, "state") or "visible"
        if state not in {"visible", "hidden", "veryHidden"}:
            state = "visible"
        rel_id = _attr(node, "id") or ""
        target = ""
        if rel_id in rel_by_id:
            target = _resolve("xl/workbook.xml", rel_by_id[rel_id][1])
        sheet_xml = parts.get(target) or parts.get(target.casefold())
        cells: list[Cell] = []
        hidden_rows: set[int] = set()
        hidden_cols: set[int] = set()
        hidden_row_spans: list[tuple[int, int]] = []
        hidden_col_spans: list[tuple[int, int]] = []
        narrow_cols: set[int] = set()
        short_rows: set[int] = set()
        comments: list[Comment] = []
        if sheet_xml:
            sheet_root = _parse_xml(sheet_xml)
            (
                cells,
                hidden_rows,
                hidden_cols,
                hidden_row_spans,
                hidden_col_spans,
                narrow_cols,
                short_rows,
            ) = _sheet_cells(sheet_root, shared, xf_formats)
            rels_name = posixpath.join(posixpath.dirname(target), "_rels", posixpath.basename(target) + ".rels")
            sheet_rels = parts.get(rels_name) or parts.get(rels_name.casefold())
            if sheet_rels:
                for _rid, rel_type, rel_target, mode in _parse_rels(sheet_rels):
                    if mode.lower() == "external":
                        if rel_target:
                            external.append(rel_target)
                        continue
                    resolved = _resolve(target, rel_target)
                    payload = parts.get(resolved) or parts.get(resolved.casefold())
                    if payload is None:
                        continue
                    rel_type_l = rel_type.lower()
                    if rel_type_l.endswith("/comments"):
                        comments.extend(_comments_from(payload, "nota"))
                    elif "threadedcomment" in rel_type_l:
                        comments.extend(_comments_from(payload, "thread"))
        sheets.append(
            Sheet(
                name=name,
                state=state,
                cells=cells,
                hidden_rows=hidden_rows,
                hidden_cols=hidden_cols,
                comments=comments,
                hidden_row_spans=hidden_row_spans,
                hidden_col_spans=hidden_col_spans,
                narrow_cols=narrow_cols,
                short_rows=short_rows,
            )
        )

    # Comments that live in well-known parts even if a relationship was missed.
    attached_refs = {(comment.ref, comment.kind, comment.text) for sheet in sheets for comment in sheet.comments}
    for part_name, payload in parts.items():
        folded = part_name.casefold()
        if folded.startswith("xl/comments") and folded.endswith(".xml"):
            for comment in _comments_from(payload, "nota"):
                key = (comment.ref, comment.kind, comment.text)
                if key not in attached_refs and sheets:
                    sheets[0].comments.append(comment)
                    attached_refs.add(key)
        elif "/threadedcomments/" in folded and folded.endswith(".xml"):
            for comment in _comments_from(payload, "thread"):
                key = (comment.ref, comment.kind, comment.text)
                if key not in attached_refs and sheets:
                    sheets[0].comments.append(comment)
                    attached_refs.add(key)

    for part_name in list(parts):
        if "externallink" in part_name.casefold() and part_name.casefold().endswith(".rels"):
            try:
                for _rid, _rel_type, target, mode in _parse_rels(parts[part_name]):
                    if target and (mode.lower() == "external" or "externalLinkPath" in _rel_type):
                        external.append(target)
            except (ZipSafetyError, WorkbookParseError):
                continue

    deduped: list[str] = []
    seen: set[str] = set()
    for item in external:
        if item not in seen:
            seen.add(item)
            deduped.append(item)

    defined_names, print_areas = _defined_names(root, sheets)
    for sheet in sheets:
        if sheet.name in print_areas:
            sheet.print_areas = print_areas[sheet.name]
    metadata = _metadata(parts)
    metadata.update(_person_emails(parts))
    workbook = Workbook(
        path=label,
        sheets=sheets,
        defined_names=defined_names,
        external_links=deduped,
        has_vba=has_vba,
        metadata=metadata,
        external_cache=_external_cache(parts),
        connections=_connection_strings(parts),
        printer_texts=_printer_texts(parts),
        person_texts=_person_texts(parts),
        vba_bytes=_vba_bytes(parts) if has_vba else None,
    )
    return workbook

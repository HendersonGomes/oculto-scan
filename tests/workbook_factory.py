"""Build synthetic .xlsx/.xlsm packages for tests.

No real personal data. CPF and PIS numbers are generated from the check
digit algorithms; company and person names are obviously fictional.
"""

from __future__ import annotations

import zipfile
from pathlib import Path


def make_cpf(base9: str) -> str:
    digits = [int(char) for char in base9]
    if len(digits) != 9:
        raise ValueError("CPF base must have 9 digits")

    def _dv(series: list[int]) -> int:
        total = sum(number * weight for number, weight in zip(series, range(len(series) + 1, 1, -1)))
        rest = total % 11
        return 0 if rest < 2 else 11 - rest

    first = _dv(digits)
    second = _dv(digits + [first])
    raw = base9 + f"{first}{second}"
    return f"{raw[:3]}.{raw[3:6]}.{raw[6:9]}-{raw[9:]}"


def make_pis(base10: str) -> str:
    weights = [3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    digits = [int(char) for char in base10]
    total = sum(number * weight for number, weight in zip(digits, weights))
    rest = total % 11
    check = 0 if rest < 2 else 11 - rest
    raw = base10 + str(check)
    return f"{raw[0:3]}.{raw[3:8]}.{raw[8:10]}-{raw[10]}"


def _meta_value(metadata: dict, *keys: str) -> str:
    folded = {str(key).casefold(): value for key, value in metadata.items()}
    for key in keys:
        value = folded.get(key.casefold())
        if value:
            return str(value)
    return ""


def _meta_tag(tag: str, value: str | None, *, xsi: bool = False) -> str:
    if not value:
        return ""
    attrs = ' xsi:type="dcterms:W3CDTF"' if xsi else ""
    return f"<{tag}{attrs}>{xml_escape(value)}</{tag}>"


def xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_zip(path: Path, parts: dict[str, bytes | str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in parts.items():
            data = payload.encode("utf-8") if isinstance(payload, str) else payload
            archive.writestr(name, data)


def _ref_row(ref: str) -> int:
    digits = "".join(char for char in ref if char.isdigit())
    return int(digits or "1")


def _cell_xml(cell: dict, shared: list[str] | None = None) -> str:
    ref = cell["ref"]
    shared = cell.get("shared")
    formula = cell.get("formula")
    value = cell.get("value")
    pieces: list[str] = []
    if shared is not None or formula is not None:
        attrs = ""
        if shared is not None:
            attrs = f' t="shared" si="{shared}"'
            if cell.get("shared_ref"):
                attrs += f' ref="{cell["shared_ref"]}"'
        body = xml_escape(formula) if formula else ""
        pieces.append(f"<f{attrs}>{body}</f>")
    if isinstance(value, (int, float)):
        pieces.append(f"<v>{value}</v>")
        return f'<c r="{ref}">{"".join(pieces)}</c>'
    if value is None:
        return f'<c r="{ref}">{"".join(pieces)}</c>'
    if cell.get("number"):
        pieces.append(f"<v>{xml_escape(str(value))}</v>")
        return f'<c r="{ref}">{"".join(pieces)}</c>'
    if shared is not None and formula is None:
        index = len(shared)
        shared.append(str(value))
        return f'<c r="{ref}" t="s"><v>{index}</v></c>'
    pieces.append(f'<is><t xml:space="preserve">{xml_escape(str(value))}</t></is>')
    return f'<c r="{ref}" t="inlineStr">{"".join(pieces)}</c>'


def _sheet_xml(sheet: dict, shared: list[str] | None = None) -> str:
    hidden_rows = set(sheet.get("hidden_rows") or [])
    hidden_cols = sheet.get("hidden_cols") or []
    cells = sheet.get("cells") or []
    rows: dict[int, list[dict]] = {}
    for cell in cells:
        rows.setdefault(_ref_row(cell["ref"]), []).append(cell)
    for row in hidden_rows:
        rows.setdefault(row, [])
    col_xml = ""
    if hidden_cols:
        cols = []
        for index in hidden_cols:
            cols.append(f'<col min="{index}" max="{index}" hidden="1" width="0"/>')
        col_xml = "<cols>" + "".join(cols) + "</cols>"
    row_xml = []
    for row in sorted(rows):
        hidden = ' hidden="1"' if row in hidden_rows else ""
        body = "".join(_cell_xml(cell, shared) for cell in rows[row])
        row_xml.append(f'<row r="{row}"{hidden}>{body}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"{col_xml}<sheetData>{''.join(row_xml)}</sheetData></worksheet>"
    )


def _comments_xml(comments: list[dict]) -> str:
    authors = []
    for comment in comments:
        author = comment.get("author") or "Autor Sintetico"
        if author not in authors:
            authors.append(author)
    author_xml = "".join(f"<author>{xml_escape(author)}</author>" for author in authors)
    items = []
    for comment in comments:
        author = comment.get("author") or "Autor Sintetico"
        items.append(
            f'<comment ref="{comment["ref"]}" authorId="{authors.index(author)}">'
            f"<text><t>{xml_escape(comment['text'])}</t></text></comment>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<comments xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<authors>{author_xml}</authors><commentList>{''.join(items)}</commentList></comments>"
    )


def _threads_xml(threads: list[dict]) -> str:
    items = []
    for index, thread in enumerate(threads):
        items.append(
            f'<threadedComment ref="{thread["ref"]}" dT="2026-01-15T12:00:00.00" '
            f'personId="{{00000000-0000-0000-0000-0000000000{index:02d}}}" '
            f'id="{{10000000-0000-0000-0000-0000000000{index:02d}}}">'
            f"<text>{xml_escape(thread['text'])}</text></threadedComment>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<ThreadedComments xmlns="http://schemas.microsoft.com/office/spreadsheetml/2018/threadedcomments">'
        f"{''.join(items)}</ThreadedComments>"
    )


def build_workbook(
    path: Path,
    sheets: list[dict],
    *,
    defined_names: list[dict] | None = None,
    metadata: dict | None = None,
    external_target: str | None = None,
    hyperlink: dict | None = None,
    vba_blob: bytes | None = None,
    use_shared_strings: bool = False,
) -> Path:
    """Write a minimal OOXML workbook. ``sheets`` entries accept cells, comments, threads."""
    metadata = metadata or {}
    parts: dict[str, bytes | str] = {}
    overrides = [
        (
            "/xl/workbook.xml",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
        ),
        (
            "/docProps/core.xml",
            "application/vnd.openxmlformats-package.core-properties+xml",
        ),
        (
            "/docProps/app.xml",
            "application/vnd.openxmlformats-officedocument.extended-properties+xml",
        ),
    ]
    workbook_rels = []
    sheet_nodes = []
    next_rel = 1
    shared: list[str] | None = [] if use_shared_strings else None

    for index, sheet in enumerate(sheets, start=1):
        part = f"xl/worksheets/sheet{index}.xml"
        parts[part] = _sheet_xml(sheet, shared)
        overrides.append(
            (
                f"/{part}",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
            )
        )
        rel_id = f"rId{next_rel}"
        next_rel += 1
        workbook_rels.append(
            f'<Relationship Id="{rel_id}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
        )
        state = sheet.get("state") or "visible"
        state_attr = "" if state == "visible" else f' state="{state}"'
        sheet_nodes.append(
            f'<sheet name="{xml_escape(sheet["name"])}" sheetId="{index}"{state_attr} r:id="{rel_id}"/>'
        )
        sheet_rels = []
        comments = sheet.get("comments") or []
        if comments:
            comment_part = f"xl/comments{index}.xml"
            parts[comment_part] = _comments_xml(comments)
            overrides.append(
                (
                    "/" + comment_part,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.comments+xml",
                )
            )
            sheet_rels.append(
                '<Relationship Id="rIdComment" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" '
                f'Target="../comments{index}.xml"/>'
            )
        threads = sheet.get("threads") or []
        if threads:
            thread_part = f"xl/threadedComments/threadedComment{index}.xml"
            parts[thread_part] = _threads_xml(threads)
            overrides.append(
                (
                    "/" + thread_part,
                    "application/vnd.ms-excel.threadedcomments+xml",
                )
            )
            sheet_rels.append(
                '<Relationship Id="rIdThread" '
                'Type="http://schemas.microsoft.com/office/2017/10/relationships/threadedComment" '
                f'Target="../threadedComments/threadedComment{index}.xml"/>'
            )
        if hyperlink and hyperlink.get("sheet") == sheet["name"]:
            sheet_rels.append(
                '<Relationship Id="rIdLink" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
                f'Target="{xml_escape(hyperlink["target"])}" TargetMode="External"/>'
            )
        if sheet_rels:
            parts[f"xl/worksheets/_rels/sheet{index}.xml.rels"] = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                + "".join(sheet_rels)
                + "</Relationships>"
            )

    if external_target:
        rel_id = f"rId{next_rel}"
        next_rel += 1
        parts["xl/externalLinks/externalLink1.xml"] = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<externalLink xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<externalBook r:id="rId1"><sheetNames><sheetName val="Custos"/></sheetNames></externalBook>'
            "</externalLink>"
        )
        parts["xl/externalLinks/_rels/externalLink1.xml.rels"] = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/externalLinkPath" '
            f'Target="{xml_escape(external_target)}" TargetMode="External"/>'
            "</Relationships>"
        )
        workbook_rels.append(
            f'<Relationship Id="{rel_id}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/externalLink" '
            'Target="externalLinks/externalLink1.xml"/>'
        )
        overrides.append(
            (
                "/xl/externalLinks/externalLink1.xml",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.externalLink+xml",
            )
        )

    if shared is not None:
        items = "".join(f"<si><t>{xml_escape(value)}</t></si>" for value in shared)
        parts["xl/sharedStrings.xml"] = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            f'count="{len(shared)}" uniqueCount="{len(shared)}">{items}</sst>'
        )
        rel_id = f"rId{next_rel}"
        next_rel += 1
        workbook_rels.append(
            f'<Relationship Id="{rel_id}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" '
            'Target="sharedStrings.xml"/>'
        )
        overrides.append(
            (
                "/xl/sharedStrings.xml",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml",
            )
        )

    if vba_blob is not None:
        parts["xl/vbaProject.bin"] = vba_blob
        rel_id = f"rId{next_rel}"
        next_rel += 1
        workbook_rels.append(
            f'<Relationship Id="{rel_id}" '
            'Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject" '
            'Target="vbaProject.bin"/>'
        )
        overrides.append(("/xl/vbaProject.bin", "application/vnd.ms-office.vbaProject"))

    names_xml = ""
    if defined_names:
        chunks = []
        for item in defined_names:
            hidden = ' hidden="1"' if item.get("hidden") else ""
            chunks.append(
                f'<definedName name="{xml_escape(item["name"])}"{hidden}>'
                f"{xml_escape(item['formula'])}</definedName>"
            )
        names_xml = "<definedNames>" + "".join(chunks) + "</definedNames>"

    parts["xl/workbook.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{''.join(sheet_nodes)}</sheets>{names_xml}</workbook>"
    )
    parts["xl/_rels/workbook.xml.rels"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(workbook_rels)
        + "</Relationships>"
    )
    creator = xml_escape(_meta_value(metadata, "creator"))
    last = xml_escape(_meta_value(metadata, "lastModifiedBy"))
    title = xml_escape(_meta_value(metadata, "title"))
    subject = xml_escape(_meta_value(metadata, "subject"))
    parts["docProps/core.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:creator>{creator}</dc:creator>"
        f"<cp:lastModifiedBy>{last}</cp:lastModifiedBy>"
        f"<dc:title>{title}</dc:title>"
        f"<dc:subject>{subject}</dc:subject>"
        + _meta_tag("cp:lastPrinted", _meta_value(metadata, "lastPrinted"))
        + _meta_tag("cp:revision", _meta_value(metadata, "revision"))
        + _meta_tag("dcterms:created", _meta_value(metadata, "created"), xsi=True)
        + _meta_tag("dcterms:modified", _meta_value(metadata, "modified"), xsi=True)
        + "</cp:coreProperties>"
    )
    company = xml_escape(_meta_value(metadata, "company", "Company"))
    manager = xml_escape(_meta_value(metadata, "manager", "Manager"))
    parts["docProps/app.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
        f"<Company>{company}</Company><Manager>{manager}</Manager>"
        + _meta_tag("Application", _meta_value(metadata, "Application"))
        + _meta_tag("AppVersion", _meta_value(metadata, "AppVersion"))
        + "</Properties>"
    )
    def _rel(rel_id: str, rel_type: str, target: str) -> str:
        return f'<Relationship Id="{rel_id}" Type="{rel_type}" Target="{target}"/>'

    parts["_rels/.rels"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + _rel(
            "rId1",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
            "xl/workbook.xml",
        )
        + _rel(
            "rId2",
            "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties",
            "docProps/core.xml",
        )
        + _rel(
            "rId3",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties",
            "docProps/app.xml",
        )
        + "</Relationships>"
    )
    override_xml = "".join(
        f'<Override PartName="{part}" ContentType="{content}"/>' for part, content in overrides
    )
    parts["[Content_Types].xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f"{override_xml}</Types>"
    )
    write_zip(path, parts)
    return path

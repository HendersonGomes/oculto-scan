"""Inspect formula text without evaluating it.

References to hidden sheets, hidden rows or columns, and other workbooks
are the high-value rule. A bare numeric literal is informational: it can
expose a margin or BDI factor, but it is not proof of a leak.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from oculto_scan.models import DefinedName, Sheet, Workbook
from oculto_scan.refs import reference_axes, span_hits

_STRING = re.compile(r'"(?:[^"]|"")*"')
_QUOTED_SHEET = re.compile(r"'((?:[^']|'')*)'!")
# Letters include accents, so ``Orçamento!B5`` is a sheet reference.
_UNQUOTED_SHEET = re.compile(r"(?<![\w.'])([^\W\d_][\w.]*)!", re.UNICODE)
_CELL_BODY = (
    r"(?:\$?[A-Z]{1,3}:\$?[A-Z]{1,3}|\$?\d+:\$?\d+|\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?)"
)
# A cell is not a function: ``LOG10(`` must not match. No identifier glued on either side.
_CELL_AT = re.compile(rf"^({_CELL_BODY})(?![A-Za-z0-9_(])")
_LOCAL_CELL = re.compile(rf"(?<![A-Za-z0-9_])({_CELL_BODY})(?![A-Za-z0-9_(])")
_NUMBER = re.compile(r"(?<![A-Za-z0-9_.])(\d+(?:\.\d+)?|\.\d+)(%)?(?![A-Za-z0-9_])")
_EXTERNAL_BOOK = re.compile(r"\[[^\[\]\r\n]+\]")
_WORKBOOK_IN_BRACKETS = re.compile(r"(?i)(?:\.xls|\.xlt|\\|/)|^\d+$")
_WIN_PATH = re.compile(r"(?i)[A-Z]:\\[^\s\"']+")
_UNC = re.compile(r"\\\\[^\s\"']+")
_IDENT = re.compile(r"(?<![A-Za-z0-9_.])([A-Za-z_][A-Za-z0-9_.]*)(?![A-Za-z0-9_.])")

_FUNCTIONS = {
    "SUM", "AVERAGE", "IF", "ROUND", "SUMIF", "SUMIFS", "COUNT", "COUNTA", "COUNTIF",
    "COUNTIFS", "VLOOKUP", "HLOOKUP", "INDEX", "MATCH", "AND", "OR", "NOT", "MIN",
    "MAX", "ABS", "INT", "MOD", "ROUNDUP", "ROUNDDOWN", "SUMPRODUCT", "IFERROR",
    "CONCATENATE", "LEFT", "RIGHT", "MID", "LEN", "TRIM", "UPPER", "LOWER", "TEXT",
    "VALUE", "DATE", "TODAY", "NOW", "YEAR", "MONTH", "DAY", "OFFSET", "INDIRECT",
    "SUBSTITUTE", "FIND", "SEARCH", "ISBLANK", "ISNUMBER", "TRUE", "FALSE", "NA",
    "PI", "SQRT", "POWER", "LOG", "LN", "EXP", "AVERAGEIF", "AVERAGEIFS", "COUNTBLANK",
    "LARGE", "SMALL", "RANK", "SUBTOTAL", "AGGREGATE", "CHOOSE", "SWITCH", "IFS",
    "XOR", "LET", "LAMBDA", "FILTER", "UNIQUE", "SORT", "XLOOKUP", "XMATCH",
    "TEXTJOIN", "CONCAT", "NUMBERVALUE", "FIXED", "PROPER", "REPT", "REPLACE",
    "EXACT", "HYPERLINK", "IFNA", "MEDIAN", "STDEV", "VAR", "PRODUCT", "QUOTIENT",
    "CEILING", "FLOOR", "TRUNC", "SIGN", "RAND", "RANDBETWEEN", "ROW", "COLUMN",
    "ROWS", "COLUMNS", "ADDRESS", "CELL", "TYPE", "N", "T", "INFO", "SHEET",
    "SHEETS", "SUMX", "LOOKUP", "TIME", "HOUR", "MINUTE", "SECOND", "EOMONTH",
    "EDATE", "NETWORKDAYS", "WORKDAY", "PMT", "PV", "FV", "NPV", "IRR", "RATE",
}


@dataclass
class FormulaInfo:
    external: list[str] = field(default_factory=list)
    sheet_refs: list[tuple[str, str]] = field(default_factory=list)
    local_refs: list[str] = field(default_factory=list)
    constants: list[str] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    string_literals: list[str] = field(default_factory=list)


def _unescape_sheet(token: str) -> str:
    return token.replace("''", "'")


def _take_ref(text: str, start: int) -> tuple[str, int] | None:
    match = _CELL_AT.match(text[start:])
    if not match:
        return None
    return match.group(1), start + match.end()


def _interesting_number(literal: str, percent: bool) -> bool:
    if percent:
        return literal not in {"0", "0.0", "0.00"}
    try:
        value = float(literal)
    except ValueError:
        return False
    return value not in (0.0, 1.0)


def parse_formula(formula: str, defined_names: set[str] | None = None) -> FormulaInfo:
    """Parse references out of a formula. The formula is not evaluated."""
    info = FormulaInfo()
    if not formula:
        return info
    text = formula[1:] if formula.startswith("=") else formula
    info.string_literals = [item[1:-1].replace('""', '"') for item in _STRING.findall(text)]
    stripped = _STRING.sub('""', text)

    for match in _EXTERNAL_BOOK.finditer(stripped):
        inner = match.group(0)[1:-1]
        # ``Tabela1[Valor]`` is a structured reference, not another workbook.
        if _WORKBOOK_IN_BRACKETS.search(inner):
            info.external.append(match.group(0))
    for match in _WIN_PATH.finditer(stripped):
        info.external.append(match.group(0))
    for match in _UNC.finditer(stripped):
        info.external.append(match.group(0))

    consumed = [False] * len(stripped)

    def _mark(start: int, end: int) -> None:
        for index in range(start, min(end, len(consumed))):
            consumed[index] = True

    def _consider_sheet(token: str, bang: int) -> None:
        sheet = _unescape_sheet(token)
        external = bool(
            _EXTERNAL_BOOK.search(sheet) or _WIN_PATH.search(sheet) or _UNC.search(sheet) or "\\" in sheet
        )
        if external:
            info.external.append(sheet)
        taken = _take_ref(stripped, bang)
        if taken:
            ref, end = taken
            _mark(bang - 1, end)  # include the bang; sheet body marked by caller
            if not external:
                info.sheet_refs.append((sheet, ref))
        elif not external:
            info.sheet_refs.append((sheet, ""))

    for match in _QUOTED_SHEET.finditer(stripped):
        _mark(match.start(), match.end())
        _consider_sheet(match.group(1), match.end())

    for match in _UNQUOTED_SHEET.finditer(stripped):
        if consumed[match.start()]:
            continue
        _mark(match.start(), match.end())
        _consider_sheet(match.group(1), match.end())

    blanked = "".join(" " if flag else char for char, flag in zip(stripped, consumed))
    for match in _LOCAL_CELL.finditer(blanked):
        info.local_refs.append(match.group(1))
        _mark(match.start(), match.end())

    blanked = "".join(" " if flag else char for char, flag in zip(stripped, consumed))
    for match in _NUMBER.finditer(blanked):
        literal, percent = match.group(1), match.group(2)
        if _interesting_number(literal, bool(percent)):
            shown = literal + (percent or "")
            info.constants.append(shown)

    if defined_names:
        folded = {name.casefold(): name for name in defined_names}
        for match in _IDENT.finditer(blanked):
            token = match.group(1)
            if token.upper() in _FUNCTIONS:
                continue
            canonical = folded.get(token.casefold())
            if canonical:
                info.names.append(canonical)
    return info


def reference_is_hidden(workbook: Workbook, sheet_name: str | None, ref: str) -> bool:
    if not sheet_name:
        return False
    sheet = workbook.sheet_by_name(sheet_name)
    if sheet is None:
        return False
    if not sheet.visible:
        return True
    if not ref:
        return False
    axes = reference_axes(ref)
    if axes is None:
        return False
    rows, cols = axes
    row_hit = span_hits(rows, sheet.hidden_rows, sheet.hidden_row_spans)
    col_hit = span_hits(cols, sheet.hidden_cols, sheet.hidden_col_spans)
    return row_hit or col_hit


def _name_map(workbook: Workbook) -> dict[str, DefinedName]:
    return {item.name.casefold(): item for item in workbook.defined_names}


def name_points_hidden(workbook: Workbook, name: str, seen: set[str] | None = None) -> str | None:
    """Return a short description if ``name`` resolves into a hidden area."""
    mapping = _name_map(workbook)
    defined = mapping.get(name.casefold())
    if defined is None:
        return None
    chain = seen if seen is not None else set()
    key = defined.name.casefold()
    if key in chain:
        return None
    chain.add(key)
    info = parse_formula(defined.formula, set(mapping))
    for sheet, ref in info.sheet_refs:
        if reference_is_hidden(workbook, sheet, ref):
            target = f"{sheet}!{ref}" if ref else sheet
            return target
    for local in info.local_refs:
        sheet_name = defined.local_sheet
        if sheet_name and reference_is_hidden(workbook, sheet_name, local):
            return f"{sheet_name}!{local}"
    for nested in info.names:
        found = name_points_hidden(workbook, nested, chain)
        if found:
            return found
    if info.external:
        return info.external[0]
    return None


def cell_is_visible(sheet: Sheet, row: int, col: int) -> bool:
    return sheet.visible and not sheet.row_is_hidden(row) and not sheet.col_is_hidden(col)

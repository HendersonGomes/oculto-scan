"""Finding and workbook models shared by the parser and the rules."""

from __future__ import annotations

from dataclasses import dataclass, field

RISK_RANK = {"info": 1, "medio": 2, "alto": 3}
RISK_LABEL = {"alto": "alto", "medio": "médio", "info": "info"}


@dataclass(frozen=True)
class Finding:
    """One leak signal.

    ``message`` is always safe to print. ``evidence_raw`` may hold the
    original snippet and is shown only with ``--show`` (terminal and HTML).
    ``evidence_masked`` is what JSON and the default terminal report use.
    """

    file: str
    sheet: str
    cell: str
    rule: str
    type_label: str
    risk: str
    message: str
    evidence_masked: str | None = None
    evidence_raw: str | None = None

    def fingerprint(self) -> str:
        return "|".join((self.rule, self.file, self.sheet, self.cell))


@dataclass
class Cell:
    ref: str
    row: int
    col: int
    formula: str | None = None
    value: str | None = None
    number_format: str | None = None


@dataclass
class Comment:
    ref: str
    text: str
    author: str | None
    kind: str  # "nota" (legacy) or "thread"


@dataclass
class DefinedName:
    name: str
    formula: str
    hidden: bool = False
    local_sheet: str | None = None


@dataclass
class Sheet:
    name: str
    state: str  # visible, hidden, veryHidden
    cells: list[Cell] = field(default_factory=list)
    hidden_rows: set[int] = field(default_factory=set)
    hidden_cols: set[int] = field(default_factory=set)
    comments: list[Comment] = field(default_factory=list)
    # Spans too large to store as a set. Membership checks consult both.
    hidden_row_spans: list[tuple[int, int]] = field(default_factory=list)
    hidden_col_spans: list[tuple[int, int]] = field(default_factory=list)
    narrow_cols: set[int] = field(default_factory=set)
    short_rows: set[int] = field(default_factory=set)
    # None: the sheet has no print area. A list means one was defined.
    print_areas: list[tuple[int, int, int, int]] | None = None

    @property
    def visible(self) -> bool:
        return self.state == "visible"

    def row_is_hidden(self, row: int) -> bool:
        if row in self.hidden_rows:
            return True
        return any(start <= row <= end for start, end in self.hidden_row_spans)

    def col_is_hidden(self, col: int) -> bool:
        if col in self.hidden_cols:
            return True
        return any(start <= col <= end for start, end in self.hidden_col_spans)


@dataclass
class Workbook:
    path: str
    sheets: list[Sheet] = field(default_factory=list)
    defined_names: list[DefinedName] = field(default_factory=list)
    external_links: list[str] = field(default_factory=list)
    has_vba: bool = False
    metadata: dict[str, str] = field(default_factory=dict)
    # Cached values from externalLinks sheetDataSet. Not real sheets.
    external_cache: list[tuple[str, Cell]] = field(default_factory=list)

    def sheet_by_name(self, name: str) -> Sheet | None:
        folded = name.casefold()
        for sheet in self.sheets:
            if sheet.name.casefold() == folded:
                return sheet
        return None

    def sheet_index(self, index: int) -> Sheet | None:
        if 0 <= index < len(self.sheets):
            return self.sheets[index]
        return None

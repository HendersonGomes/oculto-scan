"""Cell-reference helpers. Columns are 1-based, matching OOXML."""

from __future__ import annotations

import re

_CELL = re.compile(r"^(\$?)([A-Z]{1,3})(\$?)(\d+)$")
_COL_RANGE = re.compile(r"^(\$?)([A-Z]{1,3}):(\$?)([A-Z]{1,3})$")
_ROW_RANGE = re.compile(r"^(\$?)(\d+):(\$?)(\d+)$")


def col_to_index(letters: str) -> int:
    value = 0
    for char in letters.upper():
        value = value * 26 + (ord(char) - 64)
    return value


def index_to_col(index: int) -> str:
    letters = []
    while index:
        index, rem = divmod(index - 1, 26)
        letters.append(chr(65 + rem))
    return "".join(reversed(letters))


def split_cell(ref: str) -> tuple[int, int] | None:
    match = _CELL.match(ref.replace("$", ""))
    if not match:
        return None
    return int(match.group(4)), col_to_index(match.group(2))


def reference_axes(ref: str) -> tuple[tuple[int, int] | None, tuple[int, int] | None] | None:
    """Return ``(row_span, col_span)`` without listing every cell.

    ``None`` on an axis means that axis is unbounded (a whole column or row).
    ``None`` as the result means the reference could not be parsed.
    """
    clean = ref.replace("$", "")
    if not clean:
        return None
    if ":" not in clean:
        parsed = split_cell(clean)
        if not parsed:
            return None
        row, col = parsed
        return (row, row), (col, col)

    left, right = clean.split(":", 1)
    col_match = _COL_RANGE.match(clean)
    if col_match:
        start = col_to_index(col_match.group(2))
        end = col_to_index(col_match.group(4))
        if start > end:
            start, end = end, start
        return None, (start, end)
    row_match = _ROW_RANGE.match(clean)
    if row_match:
        start = int(row_match.group(2))
        end = int(row_match.group(4))
        if start > end:
            start, end = end, start
        return (start, end), None

    left_cell = split_cell(left)
    right_cell = split_cell(right)
    if not left_cell or not right_cell:
        return None
    r1, c1 = left_cell
    r2, c2 = right_cell
    if r1 > r2:
        r1, r2 = r2, r1
    if c1 > c2:
        c1, c2 = c2, c1
    return (r1, r2), (c1, c2)


def span_hits(span: tuple[int, int] | None, hidden: set[int], extra: list[tuple[int, int]]) -> bool:
    """True when an axis meets a hidden index. ``span is None`` means unbounded."""
    if span is None:
        return bool(hidden or extra)
    start, end = span
    if start > end:
        start, end = end, start
    if any(start <= item <= end for item in hidden):
        return True
    return any(not (end < left or start > right) for left, right in extra)


def rows_and_cols(ref: str) -> tuple[set[int] | None, set[int] | None]:
    """Materialize a reference only when the caller really needs the indexes.

    Prefer :func:`reference_axes` plus :func:`span_hits` for hidden-area checks.
    """
    axes = reference_axes(ref)
    if axes is None:
        return set(), set()
    rows, cols = axes

    def _set(span: tuple[int, int] | None) -> set[int] | None:
        if span is None:
            return None
        start, end = span
        return {start, end} if end != start else {start}

    return _set(rows), _set(cols)


def contiguous_groups(values: set[int]) -> list[tuple[int, int]]:
    if not values:
        return []
    ordered = sorted(values)
    groups: list[tuple[int, int]] = []
    start = previous = ordered[0]
    for number in ordered[1:]:
        if number == previous + 1:
            previous = number
            continue
        groups.append((start, previous))
        start = previous = number
    groups.append((start, previous))
    return groups


def format_group(start: int, end: int) -> str:
    if start == end:
        return str(start)
    return f"{start}:{end}"

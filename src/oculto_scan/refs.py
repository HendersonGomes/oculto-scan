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


def rows_and_cols(ref: str) -> tuple[set[int] | None, set[int] | None]:
    """Return row and column indexes touched by ``ref``.

    ``None`` means the axis is unbounded (a full column or full row range).
    An empty set means the reference could not be parsed.
    """
    clean = ref.replace("$", "")
    if ":" not in clean:
        parsed = split_cell(clean)
        if not parsed:
            return set(), set()
        row, col = parsed
        return {row}, {col}

    left, right = clean.split(":", 1)
    col_match = _COL_RANGE.match(clean)
    if col_match:
        start = col_to_index(col_match.group(2))
        end = col_to_index(col_match.group(4))
        if start > end:
            start, end = end, start
        return None, set(range(start, end + 1))
    row_match = _ROW_RANGE.match(clean)
    if row_match:
        start = int(row_match.group(2))
        end = int(row_match.group(4))
        if start > end:
            start, end = end, start
        return set(range(start, end + 1)), None

    left_cell = split_cell(left)
    right_cell = split_cell(right)
    if not left_cell or not right_cell:
        return set(), set()
    r1, c1 = left_cell
    r2, c2 = right_cell
    if r1 > r2:
        r1, r2 = r2, r1
    if c1 > c2:
        c1, c2 = c2, c1
    # Cap expansion so a pathological A1:XFD1048576 cannot exhaust memory.
    if (r2 - r1) > 2000 or (c2 - c1) > 256:
        rows = set(range(r1, r1 + 2000))
        cols = set(range(c1, min(c2, c1 + 256) + 1))
        return rows, cols
    return set(range(r1, r2 + 1)), set(range(c1, c2 + 1))


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

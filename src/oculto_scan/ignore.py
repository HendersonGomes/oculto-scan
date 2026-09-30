"""Plain-text ignore list by rule or location.

A line is one of ``rule:``, ``file:``, ``sheet:`` or ``cell:``.
``#`` starts a comment. Values are matched without the raw cell content.
"""

from __future__ import annotations

from pathlib import Path

from oculto_scan.models import Finding


class IgnoreError(Exception):
    pass


def load_ignore(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        raise IgnoreError(f"arquivo de ignore não encontrado: {path}")
    rules: list[tuple[str, str]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise IgnoreError(f"linha {line_no} sem tipo (rule, file, sheet ou cell)")
        kind, value = line.split(":", 1)
        kind = kind.strip().lower()
        value = value.strip()
        if kind not in {"rule", "file", "sheet", "cell"} or not value:
            raise IgnoreError(f"linha {line_no} inválida")
        rules.append((kind, value))
    return rules


def _file_match(pattern: str, file_label: str) -> bool:
    if file_label == pattern:
        return True
    name = file_label.rsplit("/", 1)[-1]
    return name == pattern or file_label.endswith("/" + pattern)


def matches(finding: Finding, rules: list[tuple[str, str]]) -> bool:
    for kind, value in rules:
        if kind == "rule" and finding.rule == value:
            return True
        if kind == "file" and _file_match(value, finding.file):
            return True
        if kind == "sheet":
            if "/" in value:
                file_part, sheet = value.rsplit("/", 1)
                if finding.sheet.casefold() == sheet.casefold() and _file_match(file_part, finding.file):
                    return True
            elif finding.sheet.casefold() == value.casefold():
                return True
        if kind == "cell" and _cell_match(value, finding):
            return True
    return False


def _cell_match(pattern: str, finding: Finding) -> bool:
    if "!" in pattern and "/" not in pattern:
        sheet, cell = pattern.split("!", 1)
        return finding.sheet.casefold() == sheet.casefold() and finding.cell == cell
    parts = pattern.split("/")
    if len(parts) == 3:
        file_part, sheet, cell = parts
        return (
            _file_match(file_part, finding.file)
            and finding.sheet.casefold() == sheet.casefold()
            and finding.cell == cell
        )
    if len(parts) == 2:
        sheet, cell = parts
        return finding.sheet.casefold() == sheet.casefold() and finding.cell == cell
    return False


def apply_ignore(findings: list[Finding], rules: list[tuple[str, str]]) -> tuple[list[Finding], int]:
    kept: list[Finding] = []
    ignored = 0
    for finding in findings:
        if matches(finding, rules):
            ignored += 1
            continue
        kept.append(finding)
    return kept, ignored

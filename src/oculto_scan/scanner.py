"""Scan paths, apply ignore and baseline, decide the exit code."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from oculto_scan.analyze import analyze
from oculto_scan.baseline import BaselineError, filter_findings, update_baseline
from oculto_scan.ignore import IgnoreError, apply_ignore, load_ignore
from oculto_scan.models import RISK_RANK, Finding
from oculto_scan.workbook import WorkbookParseError, load_workbook
from oculto_scan.zipsafe import ZipSafetyError

_SUFFIXES = {".xlsx", ".xlsm"}


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)
    ignored: int = 0
    scanned: int = 0
    exit_code: int = 0
    messages: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def iter_workbooks(paths: list[Path]) -> list[Path]:
    found: list[Path] = []
    for path in paths:
        if path.is_file():
            if path.suffix.lower() in _SUFFIXES and not path.name.startswith("~$"):
                found.append(path)
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if not child.is_file():
                    continue
                if child.suffix.lower() not in _SUFFIXES:
                    continue
                if child.name.startswith("~$"):
                    continue
                found.append(child)
    return found


def _error_finding(file_label: str, rule: str, risk: str, message: str) -> Finding:
    return Finding(
        file=file_label,
        sheet="",
        cell="",
        rule=rule,
        type_label="arquivo hostil" if rule == "arquivo-hostil" else "arquivo ilegível",
        risk=risk,
        message=message,
    )


def scan_files(
    paths: list[Path],
    *,
    fail_on: str = "alto",
    ignore_path: Path | None = None,
    baseline_path: Path | None = None,
    update: bool = False,
    entropy: bool = False,
) -> ScanResult:
    result = ScanResult()
    missing = [path for path in paths if not path.exists()]
    if missing:
        result.exit_code = 2
        result.messages.append("Caminho não encontrado: " + ", ".join(str(path) for path in missing))
        return result

    ignore_rules: list[tuple[str, str]] = []
    if ignore_path is not None:
        try:
            ignore_rules = load_ignore(ignore_path)
        except IgnoreError as exc:
            result.exit_code = 2
            result.messages.append(str(exc))
            return result

    workbooks = iter_workbooks(paths)
    result.scanned = len(workbooks)
    result.files = [display_path(path) for path in workbooks]
    findings: list[Finding] = []
    for path in workbooks:
        label = display_path(path)
        try:
            workbook = load_workbook(path)
        except ZipSafetyError as exc:
            findings.append(
                _error_finding(
                    label,
                    "arquivo-hostil",
                    "alto",
                    f"Arquivo recusado por limite de segurança ({exc}). Nada foi executado.",
                )
            )
            continue
        except WorkbookParseError as exc:
            findings.append(
                _error_finding(
                    label,
                    "arquivo-ilegivel",
                    "medio",
                    f"Planilha ilegível ({exc}).",
                )
            )
            continue
        except OSError as exc:
            findings.append(
                _error_finding(label, "arquivo-ilegivel", "medio", f"Não foi possível ler o arquivo ({exc}).")
            )
            continue
        findings.extend(analyze(workbook, label, entropy=entropy))

    ignored = 0
    if ignore_rules:
        findings, ignored_now = apply_ignore(findings, ignore_rules)
        ignored += ignored_now

    if update:
        if baseline_path is None:
            result.exit_code = 2
            result.messages.append("informe o arquivo de linha de base com --baseline ou --update-baseline")
            return result
        try:
            # Baseline the pre-filter set so a later scan with the same file stays quiet.
            written = update_baseline(findings, baseline_path)
        except BaselineError as exc:
            result.exit_code = 2
            result.messages.append(str(exc))
            return result
        result.messages.append(f"Linha de base atualizada ({written} impressão(ões) em {baseline_path}).")
        result.findings = []
        result.ignored = ignored + len(findings)
        result.exit_code = 0
        return result

    if baseline_path is not None:
        try:
            findings, ignored_now = filter_findings(findings, baseline_path)
        except BaselineError as exc:
            result.exit_code = 2
            result.messages.append(str(exc))
            return result
        ignored += ignored_now

    result.findings = findings
    result.ignored = ignored
    result.exit_code = _exit_code(findings, fail_on)
    return result


def _exit_code(findings: list[Finding], fail_on: str) -> int:
    if fail_on == "nenhum":
        return 0
    threshold = RISK_RANK[fail_on]
    if any(RISK_RANK.get(finding.risk, 0) >= threshold for finding in findings):
        return 1
    return 0

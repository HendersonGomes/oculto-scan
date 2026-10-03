"""Scan paths, apply ignore and baseline, decide the exit code."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from oculto_scan.analyze import scan_path
from oculto_scan.baseline import BaselineError, filter_findings, update_baseline
from oculto_scan.ignore import IgnoreError, apply_ignore, load_ignore
from oculto_scan.models import RISK_RANK, Finding, NetworkHint
from oculto_scan.workbook import ScanCancelled, WorkbookParseError
from oculto_scan.zipsafe import FileTooLargeError, ZipSafetyError

_SUFFIXES = {".xlsx", ".xlsm"}
_EXPLICIT_OTHER = {".xls", ".csv"}
_OLE = b"\xd0\xcf\x11\xe0"
_UNANALYZED = "nao-analisado"


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)
    ignored: int = 0
    scanned: int = 0
    exit_code: int = 0
    messages: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    network: list[NetworkHint] = field(default_factory=list)


def display_path(path: Path) -> str:
    """Relative path when the file sits under the current folder, otherwise the name."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.name


def iter_workbooks(paths: list[Path]) -> list[Path]:
    found, _explicit = partition_inputs(paths)
    return found


def partition_inputs(paths: list[Path]) -> tuple[list[Path], list[Path]]:
    """Workbooks to open, and .xls/.csv files the user named explicitly.

    A directory walk still skips .xls and .csv. Naming one of them on the
    command line is not silent: the caller reports it as not analyzed.
    """
    found: list[Path] = []
    explicit: list[Path] = []
    for path in paths:
        if path.is_file():
            suffix = path.suffix.lower()
            if path.name.startswith("~$"):
                continue
            if suffix in _SUFFIXES:
                found.append(path)
            elif suffix in _EXPLICIT_OTHER:
                explicit.append(path)
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if not child.is_file():
                    continue
                if child.suffix.lower() not in _SUFFIXES:
                    continue
                if child.name.startswith("~$"):
                    continue
                found.append(child)
    return found, explicit


def _unanalyzed(file_label: str, message: str) -> Finding:
    return Finding(
        file=file_label,
        sheet="",
        cell="",
        rule=_UNANALYZED,
        type_label="não analisado",
        risk="info",
        message=message,
    )


def _ole_encrypted(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(8).startswith(_OLE)
    except OSError:
        return False


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
    max_mb: int | None = None,
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

    workbooks, explicit = partition_inputs(paths)
    result.scanned = len(workbooks)
    result.files = [display_path(path) for path in workbooks]
    findings: list[Finding] = []
    network: list[NetworkHint] = []
    for path in explicit:
        label = display_path(path)
        findings.append(
            _unanalyzed(
                label,
                "Não analisado: .xls e .csv não são lidos. Salve como .xlsx e rode de novo.",
            )
        )
        result.messages.append(f"Não analisado ({label}): formato .xls/.csv não é lido.")
    for path in workbooks:
        label = display_path(path)
        try:
            found, hints = scan_path(path, label, max_mb=max_mb, entropy=entropy)
        except ScanCancelled:
            result.exit_code = 2
            result.messages.append("Análise cancelada.")
            return result
        except FileTooLargeError as exc:
            findings.append(_unanalyzed(label, f"Não analisado: {exc}"))
            result.messages.append(f"Não analisado ({label}): {exc}")
            continue
        except ZipSafetyError as exc:
            if "não é um pacote zip válido" in str(exc) and _ole_encrypted(path):
                message = (
                    "Não analisado: arquivo protegido por senha (assinatura OLE D0CF11E0). "
                    "O oculto-scan não pede senha e não abre o conteúdo."
                )
                findings.append(_unanalyzed(label, message))
                result.messages.append(f"Não analisado ({label}): protegido por senha.")
                continue
            if "não é um pacote zip válido" in str(exc):
                message = "Não analisado: arquivo corrompido ou não é um pacote .xlsx/.xlsm válido."
                findings.append(_unanalyzed(label, message))
                result.messages.append(f"Não analisado ({label}): corrompido.")
                continue
            findings.append(
                _error_finding(
                    label,
                    "arquivo-hostil",
                    "alto",
                    f"Arquivo recusado por limite de segurança ({exc}). Nada foi executado.",
                )
            )
            continue
        except zipfile.BadZipFile:
            message = "Não analisado: arquivo corrompido ou não é um pacote .xlsx/.xlsm válido."
            findings.append(_unanalyzed(label, message))
            result.messages.append(f"Não analisado ({label}): corrompido.")
            continue
        except WorkbookParseError as exc:
            message = f"Não analisado: planilha ilegível ({exc})."
            findings.append(_unanalyzed(label, message))
            result.messages.append(f"Não analisado ({label}): ilegível.")
            continue
        except OSError as exc:
            message = f"Não analisado: não foi possível ler o arquivo ({exc})."
            findings.append(_unanalyzed(label, message))
            result.messages.append(f"Não analisado ({label}): ilegível.")
            continue
        findings.extend(found)
        network.extend(hints)

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
    result.network = _kept_network(network, findings)
    result.ignored = ignored
    result.exit_code = _exit_code(findings, fail_on)
    return result


def _kept_network(hints: list[NetworkHint], findings: list[Finding]) -> list[NetworkHint]:
    """Drop map rows whose finding was ignored or baselined away."""
    alive = {(item.file, item.sheet, item.cell, item.evidence_raw) for item in findings if item.rule == "mapa-rede"}
    kept: list[NetworkHint] = []
    for hint in hints:
        if hint.counted and (hint.file, hint.sheet, hint.cell, hint.evidence_raw) not in alive:
            continue
        kept.append(hint)
    return kept


def _exit_code(findings: list[Finding], fail_on: str) -> int:
    if any(finding.rule == _UNANALYZED for finding in findings):
        return 3
    analyzed = findings
    if fail_on == "nenhum":
        return 0
    threshold = RISK_RANK[fail_on]
    if any(RISK_RANK.get(finding.risk, 0) >= threshold for finding in analyzed):
        return 1
    return 0

"""In-memory entry points. Nothing here writes a workbook or a report to disk."""

from __future__ import annotations

from oculto_scan.analyze import analyze
from oculto_scan.diff import IDENTICAL, DiffReport, compare_workbooks, render_diff_html
from oculto_scan.report import render_html
from oculto_scan.scanner import _error_finding, _unanalyzed
from oculto_scan.workbook import (
    WorkbookParseError,
    load_workbook_bytes,
    read_document_properties_bytes,
)
from oculto_scan.zipsafe import FileTooLargeError, ZipSafetyError

_OLE = b"\xd0\xcf\x11\xe0"


def _load_finding(nome: str, dados: bytes, exc: Exception):
    if isinstance(exc, FileTooLargeError):
        return _unanalyzed(nome, f"Não analisado: {exc}")
    if isinstance(exc, ZipSafetyError) and "não é um pacote zip válido" in str(exc):
        if dados[:8].startswith(_OLE):
            message = (
                "Não analisado: arquivo protegido por senha (assinatura OLE D0CF11E0). "
                "O oculto-scan não pede senha e não abre o conteúdo."
            )
        else:
            message = "Não analisado: arquivo corrompido ou não é um pacote .xlsx/.xlsm válido."
        return _unanalyzed(nome, message)
    if isinstance(exc, ZipSafetyError):
        return _error_finding(
            nome,
            "arquivo-hostil",
            "alto",
            f"Arquivo recusado por limite de segurança ({exc}). Nada foi executado.",
        )
    return _unanalyzed(nome, f"Não analisado: planilha ilegível ({exc}).")


def scan_bytes(nome: str, dados: bytes, show: bool = False) -> str:
    """Scan one workbook held in memory and return the HTML report."""
    try:
        workbook = load_workbook_bytes(dados, nome)
    except (FileTooLargeError, ZipSafetyError, WorkbookParseError) as exc:
        finding = _load_finding(nome, dados, exc)
        return render_html([finding], ignored=0, scanned=0, files=[nome], show=False)
    findings = analyze(workbook, nome)
    return render_html(findings, ignored=0, scanned=1, files=[nome], show=show)


def diff_bytes(
    nome_original: str,
    original: bytes,
    nome_recebido: str,
    recebido: bytes,
    show: bool = False,
) -> str:
    """Compare two workbooks held in memory and return the HTML diff."""
    if original == recebido:
        report = DiffReport(
            original=nome_original,
            received=nome_recebido,
            changes=[],
            metadata=[],
            identical=True,
            headline=IDENTICAL,
            exit_code=0,
        )
        return render_diff_html(report, show=show)
    try:
        left = load_workbook_bytes(original, nome_original)
        right = load_workbook_bytes(recebido, nome_recebido)
        props_left = read_document_properties_bytes(original)
        props_right = read_document_properties_bytes(recebido)
    except (FileTooLargeError, ZipSafetyError, WorkbookParseError) as exc:
        hostile = isinstance(exc, ZipSafetyError) and "não é um pacote zip válido" not in str(exc)
        report = DiffReport(
            original=nome_original,
            received=nome_recebido,
            changes=[],
            metadata=[],
            identical=False,
            headline=(
                f"Arquivo recusado por limite de segurança ({exc})."
                if hostile
                else f"Não analisado: {exc}"
            ),
            exit_code=1 if hostile else 3,
        )
        return render_diff_html(report, show=False)
    report = compare_workbooks(
        left,
        right,
        original_label=nome_original,
        received_label=nome_recebido,
        original_props=props_left,
        received_props=props_right,
        identical=False,
    )
    return render_diff_html(report, show=show)

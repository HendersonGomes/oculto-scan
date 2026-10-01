"""Window behavior without widgets. Safe to import where there is no display."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from oculto_scan.diff import DiffReport, render_diff_html
from oculto_scan.models import RISK_LABEL, Finding, NetworkHint
from oculto_scan.public import inspect_bytes, inspect_diff_bytes
from oculto_scan.report import DISCLAIMER, render_html, sorted_findings, summary

ACCEPTED_SUFFIXES = {".xlsx", ".xlsm"}


@dataclass
class Session:
    """One scan or one comparison, already parsed. Reveal only changes the text."""

    mode: str = ""
    findings: list[Finding] = field(default_factory=list)
    network: list[NetworkHint] = field(default_factory=list)
    diff: DiffReport | None = None
    scanned: int = 0
    names: tuple[str, ...] = ()
    error: str = ""

    @property
    def ready(self) -> bool:
        return not self.error and self.mode in {"scan", "diff"}


def validate_workbook(path: Path) -> str | None:
    """Return a short message when the path cannot be opened, otherwise None."""
    if not path.is_file():
        return "Arquivo não encontrado."
    if path.suffix.lower() not in ACCEPTED_SUFFIXES:
        return "Escolha um arquivo .xlsx ou .xlsm."
    return None


def scan_file(path: Path) -> Session:
    problem = validate_workbook(path)
    if problem:
        return Session(error=problem)
    result = inspect_bytes(path.name, path.read_bytes(), show=False)
    return Session(
        mode="scan",
        findings=list(result.findings),
        network=list(result.network),
        scanned=result.scanned,
        names=(path.name,),
    )


def compare_files(original: Path, received: Path) -> Session:
    for path in (original, received):
        problem = validate_workbook(path)
        if problem:
            return Session(error=f"{path.name}: {problem}")
    report, _html = inspect_diff_bytes(
        original.name,
        original.read_bytes(),
        received.name,
        received.read_bytes(),
        show=False,
    )
    return Session(mode="diff", diff=report, names=(original.name, received.name))


def summary_line(session: Session) -> str:
    if session.error:
        return session.error
    if session.mode == "diff" and session.diff is not None:
        if session.diff.headline:
            return session.diff.headline
        count = len(session.diff.changes)
        return f"{count} mudança(s) entre os dois arquivos."
    counts = summary(session.findings)
    return (
        f"Resumo: {counts['alto']} alto, {counts['medio']} médio, "
        f"{counts['info']} info ({counts['total']} no total)."
    )


def _value(masked: str | None, raw: str | None, *, show: bool) -> str:
    if show and raw:
        return raw
    if masked:
        return masked
    return "—"


def result_text(session: Session, *, show: bool) -> str:
    if session.error:
        return session.error + "\n"
    lines: list[str] = []
    if session.mode == "scan":
        visible = [item for item in sorted_findings(session.findings) if item.rule != "mapa-rede"]
        if not visible and not session.findings:
            lines.append("Nenhum achado.")
        for finding in visible:
            risk = RISK_LABEL.get(finding.risk, finding.risk)
            where = " › ".join(piece for piece in (finding.sheet, finding.cell) if piece) or "—"
            lines.append(f"{risk} · {finding.type_label} · {where}")
            lines.append(f"  {finding.message}")
            lines.append(f"  valor: {_value(finding.evidence_masked, finding.evidence_raw, show=show)}")
        lines.append("")
        lines.append("Mapa da rede")
        if not session.network:
            lines.append("  Nenhum indício de rede interna.")
        for hint in session.network:
            risk = RISK_LABEL.get(hint.risk, hint.risk)
            where = " › ".join(piece for piece in (hint.sheet, hint.cell, hint.source) if piece) or "—"
            lines.append(f"{risk} · {hint.type_label} · {where}")
            lines.append(f"  valor: {_value(hint.evidence_masked, hint.evidence_raw, show=show)}")
    elif session.diff is not None:
        report = session.diff
        if report.headline:
            lines.append(report.headline)
        if not report.changes and not report.headline:
            lines.append("Nenhuma mudança de conteúdo.")
        for change in report.changes:
            where = " › ".join(piece for piece in (change.sheet, change.cell) if piece) or "—"
            before = _value(change.before_masked, change.before_raw, show=show)
            after = _value(change.after_masked, change.after_raw, show=show)
            lines.append(f"{change.type_label} · {where}")
            lines.append(f"  {change.message}")
            lines.append(f"  antes: {before}")
            lines.append(f"  depois: {after}")
    lines.append("")
    lines.append(DISCLAIMER)
    if show:
        lines.append("Os valores acima estão revelados. Não envie este relatório a terceiros.")
    else:
        lines.append("Valores mascarados. Marque a opção para revelar só neste computador.")
    return "\n".join(lines) + "\n"


def result_html(session: Session, *, show: bool) -> str:
    if not session.ready:
        return ""
    if session.mode == "diff" and session.diff is not None:
        return render_diff_html(session.diff, show=show)
    return render_html(
        session.findings,
        ignored=0,
        scanned=session.scanned,
        files=list(session.names),
        show=show,
        network=session.network,
    )


def suggested_html_name(*, show: bool, mode: str) -> str:
    if mode == "diff":
        return "oculto-scan-diff-revelado.html" if show else "oculto-scan-diff.html"
    return "oculto-scan-relatorio-revelado.html" if show else "oculto-scan-relatorio.html"

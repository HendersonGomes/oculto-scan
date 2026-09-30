"""Terminal and JSON reports. JSON never includes raw values."""

from __future__ import annotations

import json

from oculto_scan import __version__
from oculto_scan.models import RISK_LABEL, RISK_RANK, Finding

DISCLAIMER = "nenhum achado não significa arquivo limpo."


def _sort_key(finding: Finding) -> tuple[int, str, str, str, str]:
    return (
        -RISK_RANK.get(finding.risk, 0),
        finding.file,
        finding.sheet,
        finding.cell,
        finding.rule,
    )


def sorted_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=_sort_key)


def summary(findings: list[Finding]) -> dict[str, int]:
    counts = {"alto": 0, "medio": 0, "info": 0, "total": len(findings)}
    for finding in findings:
        if finding.risk in counts:
            counts[finding.risk] += 1
    return counts


def _place(finding: Finding) -> str:
    sheet = finding.sheet or "—"
    cell = finding.cell or "—"
    risk = RISK_LABEL.get(finding.risk, finding.risk)
    return f"{finding.file} › {sheet} › {cell} › {finding.type_label} › {risk}"


def render_text(findings: list[Finding], *, show: bool, ignored: int, scanned: int) -> str:
    lines: list[str] = []
    ordered = sorted_findings(findings)
    if not ordered:
        if scanned == 0:
            lines.append("Nenhuma planilha .xlsx ou .xlsm encontrada.")
        else:
            lines.append(f"Nenhum achado em {scanned} planilha(s).")
    for finding in ordered:
        lines.append(_place(finding))
        lines.append(f"  {finding.message}")
        if show and finding.evidence_raw:
            lines.append(f"  valor: {finding.evidence_raw}")
        elif finding.evidence_masked:
            lines.append(f"  valor: {finding.evidence_masked}")
    counts = summary(ordered)
    lines.append("---")
    lines.append(
        "Resumo: "
        f"{counts['alto']} alto, {counts['medio']} médio, {counts['info']} info "
        f"({counts['total']} no total). {ignored} ignorado(s)."
    )
    lines.append(DISCLAIMER)
    return "\n".join(lines) + "\n"


def render_json(findings: list[Finding], *, ignored: int, scanned: int) -> str:
    ordered = sorted_findings(findings)
    counts = summary(ordered)
    payload = {
        "tool": "oculto-scan",
        "version": __version__,
        "disclaimer": DISCLAIMER,
        "scanned": scanned,
        "summary": {
            "alto": counts["alto"],
            "medio": counts["medio"],
            "info": counts["info"],
            "total": counts["total"],
            "ignorados": ignored,
        },
        "findings": [
            {
                "file": finding.file,
                "sheet": finding.sheet,
                "cell": finding.cell,
                "rule": finding.rule,
                "type": finding.type_label,
                "risk": finding.risk,
                "message": finding.message,
                "value": finding.evidence_masked,
            }
            for finding in ordered
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

"""Window behavior without widgets. Safe to import where there is no display."""

from __future__ import annotations

import re
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


VAZIO = "vazio"
ERRO = "erro"
LIMPO = "limpo"
ACHADOS = "achados"

_SCAN_CARDS = (("alto", "alto"), ("medio", "médio"), ("info", "info"), ("total", "total"))
_DIFF_CARDS = (
    ("conteudo", "conteúdo"),
    ("estrutura", "estrutura"),
    ("metadado", "metadado"),
    ("total", "total"),
)


def view_state(session: Session) -> str:
    """Visual state of a finished session. The window adds «analisando» itself."""
    if session.error:
        return ERRO
    if session.mode == "scan":
        if session.findings or session.network:
            return ACHADOS
        return LIMPO
    if session.mode == "diff" and session.diff is not None:
        if session.diff.changes:
            return ACHADOS
        return LIMPO
    return VAZIO


def card_counts(session: Session) -> list[tuple[str, str, int]]:
    """Severity or diff-category cards: (key, label, count). Empty before a result."""
    state = view_state(session)
    if state not in {LIMPO, ACHADOS}:
        return []
    if session.mode == "diff" and session.diff is not None:
        counts = {"conteudo": 0, "estrutura": 0, "metadado": 0, "total": len(session.diff.changes)}
        for change in session.diff.changes:
            if change.category in counts:
                counts[change.category] += 1
        return [(key, label, counts[key]) for key, label in _DIFF_CARDS]
    counts = summary(session.findings)
    return [(key, label, counts[key]) for key, label in _SCAN_CARDS]


def type_counts(session: Session) -> list[tuple[str, int]]:
    """How many lines of each type the report lists. Order is count, then name."""
    counts: dict[str, int] = {}
    labels: list[str] = []
    if session.mode == "scan":
        labels = [finding.type_label for finding in session.findings if finding.rule != "mapa-rede"]
    elif session.diff is not None:
        labels = [change.type_label for change in session.diff.changes]
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


# Four or more info-only signals raise the grade to médio. Médio never becomes alto by count.
_INFO_TO_MEDIO = 4
_AUTHOR = re.compile(r"Autor: ([^.]+)\.")
_DIFF_RISK = {"conteudo": "alto", "estrutura": "medio", "metadado": "info"}
_SEVERITY_LABEL = {"alto": "ALTO", "medio": "MÉDIO", "info": "INFO"}

# Short window copy. The long finding.message stays in the HTML and terminal reports.
_SCAN_COPY: dict[str, tuple[str, str]] = {
    "macro": ("Macro no arquivo", "Uma macro pode mudar a planilha ao abrir. O detalhe está no relatório HTML."),
    "não analisado": ("Parte não lida", "O programa não conseguiu ler essa parte. Veja o detalhe no relatório HTML."),
    "macro suspeita": ("Macro suspeita", "A macro tem um sinal de risco. Não abra se você não confia na origem."),
    "aba oculta": (
        "Aba escondida",
        "Revele a aba ou tire-a do arquivo. Quem recebe mostra {sheet} com um clique.",
    ),
    "aba muito oculta": (
        "Aba bem escondida",
        "A aba {sheet} não aparece no menu normal. Revele ou apague antes de enviar.",
    ),
    "linha oculta": ("Linha escondida", "Mostre a linha ou confira se ela guarda custo ou margem."),
    "coluna oculta": ("Coluna escondida", "Mostre a coluna ou confira se ela guarda custo ou margem."),
    "comentário": ("Comentário interno", "{evidence}. Apague a nota se for margem ou ressalva."),
    "nome definido": ("Nome definido", "Um nome pode apontar para uma aba ou célula escondida. Confira no HTML."),
    "vínculo externo": (
        "Ligação com outro arquivo",
        "A planilha puxa dado de fora. Quem recebe pode não ter esse arquivo.",
    ),
    "metadado": ("Dado do arquivo", "Autor, empresa ou caminho pode identificar quem montou. Veja no HTML."),
    "formato oculto": (
        "Texto com formato escondido",
        "A célula tem conteúdo, mas a tela fica em branco. Confira no HTML.",
    ),
    "coluna estreita": ("Coluna estreita demais", "A coluna está tão fina que o conteúdo some. Alargue ou apague."),
    "linha baixa": ("Linha baixa demais", "A linha está tão baixa que o conteúdo some. Aumente ou apague."),
    "fora da impressão": ("Fora da área de impressão", "Quem imprime não vê, mas quem abre a planilha ainda vê."),
    "fórmula fora da impressão": (
        "Fórmula fora da impressão",
        "A fórmula puxa um valor que não sai na impressão. Confira a origem no HTML.",
    ),
    "fórmula externa": ("Fórmula de outro arquivo", "A fórmula busca valor em outro arquivo. O vínculo pode ir junto."),
    "fórmula oculta": (
        "Preço ligado a custo oculto",
        "A fórmula usa {evidence}. Confira se esse custo pode sair junto.",
    ),
    "constante": ("Número fixo na fórmula", "Fator mascarado como [n]. Sozinho, não prova vazamento."),
    "segredo": ("Possível senha ou chave", "Tire o segredo do arquivo antes de enviar."),
    "entropia": ("Trecho incomum", "Pode ser falso alarme. O detalhe está no HTML."),
    "CPF": ("CPF na planilha", "Há um CPF. Tire se a planilha for para fora da empresa."),
    "PIS": ("PIS na planilha", "Há um número de trabalhador. Confira se pode sair."),
    "CNPJ": ("CNPJ na planilha", "CNPJ é comum em proposta. Confira no HTML se é o caso."),
    "dado bancário": ("Dado bancário", "Há conta ou agência. Não envie se não for necessário."),
    "arquivo hostil": ("Arquivo recusado", "O arquivo parece perigoso. Não abra no Excel."),
    "arquivo ilegível": ("Arquivo ilegível", "Não foi possível ler este arquivo como planilha."),
    "caminho UNC": ("Caminho de rede", "Há um caminho de servidor. Tire-o antes de enviar."),
    "caminho local": ("Caminho neste computador", "A pasta pode identificar a máquina. Veja o detalhe no HTML."),
    "usuário": ("Nome de usuário", "O arquivo cita um usuário do Windows. Confira se pode sair."),
    "SharePoint/OneDrive": ("Link de nuvem interna", "O endereço mostra o site interno. Confira no HTML."),
    "impressora": ("Impressora da rede", "O arquivo cita uma impressora interna. Veja no HTML."),
    "máquina": ("Nome de máquina", "O arquivo cita um computador da rede. Veja no HTML."),
}
_DIFF_COPY: dict[str, tuple[str, str]] = {
    "célula criada": ("Célula nova", "Apareceu conteúdo que não estava no arquivo original."),
    "célula apagada": ("Célula apagada", "Sumiu conteúdo que estava no arquivo original."),
    "fórmula alterada": ("Fórmula mudou", "A conta desta célula não é a mesma."),
    "valor em cache": ("Valor em cache mudou", "A fórmula é a mesma, mas o número guardado mudou."),
    "valor alterado": ("Valor mudou", "O número ou o texto desta célula mudou."),
    "coluna ocultada": ("Coluna foi escondida", "Uma coluna visível passou a ficar oculta."),
    "linha ocultada": ("Linha foi escondida", "Uma linha visível passou a ficar oculta."),
    "coluna reexibida": ("Coluna voltou a aparecer", "Uma coluna oculta ficou visível."),
    "linha reexibida": ("Linha voltou a aparecer", "Uma linha oculta ficou visível."),
    "comentário novo": ("Comentário novo", "Entrou uma nota que não estava no original."),
    "comentário removido": ("Comentário saiu", "Uma nota do original não está mais no arquivo."),
    "comentário editado": ("Comentário mudou", "O texto da nota não é o mesmo."),
    "aba renomeada": ("Aba renomeada", "O nome da aba mudou entre os dois arquivos."),
    "visibilidade da aba": ("Visibilidade da aba", "A aba mudou de visível para oculta, ou o contrário."),
    "nome definido": ("Nome definido mudou", "Um nome da planilha foi criado, apagado ou alterado."),
    "vínculo externo": ("Vínculo externo mudou", "A ligação com outro arquivo não é a mesma."),
    "metadado": ("Dado do arquivo mudou", "Autor, data ou outro dado do arquivo mudou."),
    "aba apagada": ("Aba apagada", "Uma aba do original não está no arquivo recebido."),
    "aba criada": ("Aba nova", "Entrou uma aba que não estava no original."),
    "macro": ("Macro mudou", "O arquivo de macro não é o mesmo. Veja o HTML."),
}
_DIFF_WITH_VALUES = {
    "célula criada",
    "célula apagada",
    "fórmula alterada",
    "valor em cache",
    "valor alterado",
    "comentário novo",
    "comentário editado",
}


@dataclass(frozen=True)
class WindowCard:
    """One short card. The long explanation stays in the HTML report."""

    severity: str
    title: str
    where: str
    action: str

    @property
    def severity_label(self) -> str:
        return _SEVERITY_LABEL.get(self.severity, self.severity.upper())


def risk_grade(session: Session) -> tuple[str, str]:
    """Grade and the line under it.

    The grade is the worst severity. Info-only results become médio at four
    or more. Count never lifts médio to alto. Empty before a scan.
    """
    if session.error:
        return "erro", session.error
    if session.mode not in {"scan", "diff"}:
        return "", ""
    altos, medios, infos = _severity_counts(session)
    if altos + medios + infos == 0:
        return "limpo", "nota geral · nenhum achado"
    if altos:
        return "alto", f"nota geral · {_phrase(altos, 'alto', 'altos')}"
    if medios:
        return "medio", f"nota geral · {_phrase(medios, 'médio', 'médios')}"
    if infos >= _INFO_TO_MEDIO:
        return "medio", f"nota geral · {_phrase(infos, 'info', 'infos')}"
    return "baixo", f"nota geral · {_phrase(infos, 'info', 'infos')}"


def window_cards(session: Session, *, show: bool) -> list[WindowCard]:
    """Short cards for the window. ``show`` reveals a short snippet, not the long message."""
    if session.error or session.mode not in {"scan", "diff"}:
        return []
    if session.mode == "diff" and session.diff is not None:
        return [_diff_card(change, show=show) for change in session.diff.changes]
    cards = [_scan_card(item, show=show) for item in _visible_findings(session)]
    cards.extend(_scan_card(hint, show=show) for hint in session.network)
    return cards


def _phrase(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def _severity_counts(session: Session) -> tuple[int, int, int]:
    altos = medios = infos = 0
    for severity in _severities(session):
        if severity == "alto":
            altos += 1
        elif severity == "medio":
            medios += 1
        else:
            infos += 1
    return altos, medios, infos


def _severities(session: Session) -> list[str]:
    if session.mode == "diff" and session.diff is not None:
        return [_DIFF_RISK.get(change.category, "info") for change in session.diff.changes]
    ranks: list[str] = []
    for finding in _visible_findings(session):
        ranks.append(finding.risk if finding.risk in _SEVERITY_LABEL else "info")
    for hint in session.network:
        ranks.append(hint.risk if hint.risk in _SEVERITY_LABEL else "info")
    return ranks


def _visible_findings(session: Session) -> list[Finding]:
    """Same skip as the text report: mapa-rede is the network section, unless it is the only signal."""
    ordered = sorted_findings(session.findings)
    visible = [item for item in ordered if item.rule != "mapa-rede"]
    if visible or session.network:
        return visible
    return ordered


def _clip(text: str, limit: int = 72) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _snippet(masked: str | None, raw: str | None, *, show: bool) -> str:
    if show and raw:
        return _clip(raw)
    if masked:
        return _clip(masked)
    return ""


def _place(sheet: str, cell: str, message: str = "") -> str:
    if sheet and not cell:
        place = f"Aba {sheet}"
    else:
        bits = [piece for piece in (sheet, cell) if piece]
        place = " › ".join(bits) if bits else "Arquivo"
    match = _AUTHOR.search(message)
    if match:
        place = f"{place} · autor {match.group(1).strip()}"
    return place


def _plain_title(label: str) -> str:
    if not label:
        return "Achado"
    if label[:1].isupper():
        return label
    return label[:1].upper() + label[1:]


def _fill(template: str, *, sheet: str, evidence: str) -> str:
    if "{evidence}" in template and not evidence:
        return "Veja o detalhe no relatório HTML."
    shown = evidence
    if template.startswith("{evidence}") and shown[:1].islower():
        shown = shown[0].upper() + shown[1:]
    return template.format(sheet=sheet or "a aba", evidence=shown)


def _scan_card(item: Finding | NetworkHint, *, show: bool) -> WindowCard:
    label = item.type_label
    evidence = _snippet(item.evidence_masked, item.evidence_raw, show=show)
    title, template = _SCAN_COPY.get(label, (_plain_title(label), "Veja o detalhe no relatório HTML."))
    if label == "constante":
        if show and item.evidence_raw:
            action = f"A fórmula mostra {_clip(item.evidence_raw)}. Sozinho, não prova vazamento."
        elif evidence and "[n]" not in evidence:
            action = f"Número fixo: {evidence}. Sozinho, não prova vazamento."
        else:
            action = template
    else:
        action = _fill(template, sheet=item.sheet, evidence=evidence)
    severity = item.risk if item.risk in _SEVERITY_LABEL else "info"
    return WindowCard(severity=severity, title=title, where=_place(item.sheet, item.cell, item.message), action=action)


def _diff_card(change, *, show: bool) -> WindowCard:
    fallback = (_plain_title(change.type_label), "Veja o detalhe no relatório HTML.")
    title, action = _DIFF_COPY.get(change.type_label, fallback)
    if change.type_label in _DIFF_WITH_VALUES:
        before = _snippet(change.before_masked, change.before_raw, show=show)
        after = _snippet(change.after_masked, change.after_raw, show=show)
        if before and after and before != "—" and after != "—":
            action = f"{action} De {before} para {after}."
    severity = _DIFF_RISK.get(change.category, "info")
    return WindowCard(
        severity=severity,
        title=title,
        where=_place(change.sheet, change.cell, change.message),
        action=action,
    )

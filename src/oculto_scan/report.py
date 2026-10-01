"""Terminal, JSON and HTML reports. JSON and HTML never include raw values."""

from __future__ import annotations

import html
import json
import os
import sys
from datetime import datetime

from oculto_scan import __version__
from oculto_scan.models import RISK_LABEL, RISK_RANK, Finding

DISCLAIMER = "nenhum achado não significa arquivo limpo."

_RESET = "\033[0m"
_BOLD = "\033[1m"
_RISK_COLOR = {
    "alto": "\033[31m",
    "medio": "\033[33m",
    "info": "\033[36m",
}

# STD_OUTPUT_HANDLE / ENABLE_VIRTUAL_TERMINAL_PROCESSING
_STD_OUTPUT_HANDLE = -11
_ENABLE_VT = 0x0004


def enable_windows_vt() -> bool:
    """Turn on ANSI processing in the Windows console. No-op elsewhere."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.GetStdHandle.restype = ctypes.c_void_p
        kernel32.GetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel32.GetConsoleMode.restype = ctypes.c_int
        kernel32.SetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel32.SetConsoleMode.restype = ctypes.c_int
        handle = kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)
        if not handle or handle == ctypes.c_void_p(-1).value:
            return False
        mode = ctypes.c_ulong()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | _ENABLE_VT))
    except (AttributeError, OSError):
        return False


def stdout_wants_color(*, no_color: bool) -> bool:
    """Color only on a TTY, unless NO_COLOR or --no-color says otherwise."""
    if no_color or os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    enable_windows_vt()
    return True


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


def _by_file(findings: list[Finding]) -> list[tuple[str, list[Finding]]]:
    ordered = sorted_findings(findings)
    groups: dict[str, list[Finding]] = {}
    for finding in ordered:
        groups.setdefault(finding.file, []).append(finding)

    def _file_key(name: str) -> tuple[int, str]:
        worst = max(RISK_RANK.get(item.risk, 0) for item in groups[name])
        return (-worst, name)

    return [(name, groups[name]) for name in sorted(groups, key=_file_key)]


def _paint(text: str, code: str, *, color: bool) -> str:
    if not color or not code:
        return text
    return f"{code}{text}{_RESET}"


def _summary_line(counts: dict[str, int], ignored: int, *, color: bool) -> str:
    if not color:
        return (
            "Resumo: "
            f"{counts['alto']} alto, {counts['medio']} médio, {counts['info']} info "
            f"({counts['total']} no total). {ignored} ignorado(s)."
        )
    alto = _paint(f"{counts['alto']} alto", _RISK_COLOR["alto"], color=True)
    medio = _paint(f"{counts['medio']} médio", _RISK_COLOR["medio"], color=True)
    info = _paint(f"{counts['info']} info", _RISK_COLOR["info"], color=True)
    return (
        f"{_BOLD}Resumo:{_RESET} {alto}, {medio}, {info} "
        f"({counts['total']} no total). {ignored} ignorado(s)."
    )


def render_text(
    findings: list[Finding],
    *,
    show: bool,
    ignored: int,
    scanned: int,
    color: bool = False,
) -> str:
    lines: list[str] = []
    groups = _by_file(findings)
    if not groups:
        if scanned == 0:
            lines.append("Nenhuma planilha .xlsx ou .xlsm encontrada.")
        else:
            lines.append(f"Nenhum achado em {scanned} planilha(s).")
    for index, (name, items) in enumerate(groups):
        if index:
            lines.append("")
        lines.append(_paint(name, _BOLD, color=color))
        for finding in items:
            sheet = finding.sheet or "—"
            cell = finding.cell or "—"
            risk = RISK_LABEL.get(finding.risk, finding.risk)
            risk_shown = _paint(risk, _RISK_COLOR.get(finding.risk, ""), color=color)
            lines.append(f"  {sheet} › {cell} › {finding.type_label} › {risk_shown}")
            lines.append(f"    {finding.message}")
            if show and finding.evidence_raw:
                lines.append(f"    valor: {finding.evidence_raw}")
            elif finding.evidence_masked:
                lines.append(f"    valor: {finding.evidence_masked}")
    counts = summary(findings)
    lines.append("---")
    lines.append(_summary_line(counts, ignored, color=color))
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


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def render_html(
    findings: list[Finding],
    *,
    ignored: int,
    scanned: int,
    files: list[str],
    generated_at: datetime | None = None,
) -> str:
    """Self-contained HTML. Spreadsheet text is escaped. Values stay masked."""
    when = generated_at or datetime.now().astimezone()
    stamp = when.strftime("%d/%m/%Y %H:%M:%S %z").strip()
    counts = summary(findings)
    groups = _by_file(findings)
    scanned_files = files or [name for name, _items in groups]
    file_items = "".join(f"<li>{_esc(name)}</li>" for name in scanned_files) or "<li>Nenhuma planilha.</li>"

    sections: list[str] = []
    if not groups:
        empty = (
            "Nenhuma planilha .xlsx ou .xlsm encontrada."
            if scanned == 0
            else f"Nenhum achado em {scanned} planilha(s)."
        )
        sections.append(f'<p class="empty">{_esc(empty)}</p>')
    for name, items in groups:
        rows: list[str] = []
        for finding in items:
            value = finding.evidence_masked or "—"
            risk = RISK_LABEL.get(finding.risk, finding.risk)
            rows.append(
                "<tr class=\"risk-{risk}\">"
                "<td>{sheet}</td><td>{cell}</td><td>{kind}</td>"
                "<td><span class=\"badge badge-{risk}\">{risk_label}</span></td>"
                "<td>{message}</td><td class=\"value\">{value}</td>"
                "</tr>".format(
                    risk=_esc(finding.risk),
                    sheet=_esc(finding.sheet or "—"),
                    cell=_esc(finding.cell or "—"),
                    kind=_esc(finding.type_label),
                    risk_label=_esc(risk),
                    message=_esc(finding.message),
                    value=_esc(value),
                )
            )
        sections.append(
            "<section class=\"file\">"
            f"<h2>{_esc(name)}</h2>"
            "<table><thead><tr>"
            "<th>Aba</th><th>Célula</th><th>Tipo</th><th>Risco</th>"
            "<th>Explicação</th><th>Valor mascarado</th>"
            "</tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table></section>"
        )

    return _HTML.format(
        version=_esc(__version__),
        stamp=_esc(stamp),
        scanned=_esc(scanned),
        ignored=_esc(ignored),
        alto=_esc(counts["alto"]),
        medio=_esc(counts["medio"]),
        info=_esc(counts["info"]),
        total=_esc(counts["total"]),
        files=file_items,
        sections="".join(sections),
        disclaimer=_esc(DISCLAIMER),
    )


_HTML = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>oculto-scan — relatório</title>
<style>
  :root {{
    --ink: #1c1915;
    --muted: #5c564c;
    --line: #e4ddd2;
    --paper: #f7f4ef;
    --card: #fffdf9;
    --alto: #9f2d2d;
    --alto-bg: #f8e4e1;
    --medio: #8a5a12;
    --medio-bg: #f8efd4;
    --info: #1f5f6b;
    --info-bg: #e3f0f2;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    color: var(--ink);
    background: var(--paper);
    font: 15px/1.45 "Segoe UI", Calibri, "Liberation Sans", sans-serif;
  }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 2rem 1.25rem 3rem; }}
  header h1 {{ font-size: 1.8rem; margin: 0 0 0.2rem; letter-spacing: -0.02em; }}
  header p {{ margin: 0; color: var(--muted); }}
  .meta {{ display: flex; flex-wrap: wrap; gap: 1.25rem; margin: 1rem 0 0; padding: 0; }}
  .meta div {{ min-width: 8rem; }}
  .meta dt {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); }}
  .meta dd {{ margin: 0.15rem 0 0; font-weight: 650; }}
  .resumo {{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.75rem;
    margin: 1.5rem 0;
  }}
  .resumo article {{
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 0.85rem 1rem;
  }}
  .resumo strong {{ display: block; font-size: 1.6rem; line-height: 1; }}
  .resumo span {{ color: var(--muted); font-size: 0.85rem; }}
  .resumo .alto strong {{ color: var(--alto); }}
  .resumo .medio strong {{ color: var(--medio); }}
  .resumo .info strong {{ color: var(--info); }}
  h2 {{ font-size: 1.05rem; margin: 1.6rem 0 0.6rem; word-break: break-word; }}
  .files {{ margin: 0.4rem 0 0; padding-left: 1.1rem; }}
  .files li {{ word-break: break-word; }}
  table {{ width: 100%; border-collapse: collapse; background: var(--card); }}
  th, td {{
    text-align: left;
    vertical-align: top;
    padding: 0.55rem 0.65rem;
    border-bottom: 1px solid var(--line);
  }}
  th {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.03em; color: var(--muted); }}
  tr.risk-alto td {{ background: var(--alto-bg); }}
  tr.risk-medio td {{ background: var(--medio-bg); }}
  tr.risk-info td {{ background: var(--info-bg); }}
  .badge {{
    display: inline-block;
    font-weight: 700;
    font-size: 0.8rem;
    padding: 0.1rem 0.45rem;
    border-radius: 999px;
  }}
  .badge-alto {{ color: var(--alto); background: #fff; }}
  .badge-medio {{ color: var(--medio); background: #fff; }}
  .badge-info {{ color: var(--info); background: #fff; }}
  td.value {{ font-family: Consolas, "Courier New", monospace; font-size: 0.86rem; word-break: break-word; }}
  .empty {{ color: var(--muted); }}
  footer {{
    margin-top: 2rem;
    padding-top: 0.8rem;
    border-top: 1px solid var(--line);
    color: var(--muted);
    font-size: 0.92rem;
  }}
  @media (max-width: 800px) {{
    .resumo {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    table {{ display: block; overflow-x: auto; }}
  }}
  @media print {{
    body {{ background: #fff; }}
    main {{ max-width: none; padding: 0; }}
    .resumo article, table {{ border-color: #ccc; }}
    tr, .resumo article, header, footer {{ break-inside: avoid; }}
    h2 {{ break-after: avoid; }}
    * {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  }}
</style>
</head>
<body>
<main>
  <header>
    <h1>oculto-scan</h1>
    <p>Relatório de vazamento em planilha de obra. Valores mascarados; nada aqui é o conteúdo original.</p>
    <dl class="meta">
      <div><dt>Data</dt><dd>{stamp}</dd></div>
      <div><dt>Versão</dt><dd>{version}</dd></div>
      <div><dt>Planilhas</dt><dd>{scanned}</dd></div>
      <div><dt>Ignorados</dt><dd>{ignored}</dd></div>
    </dl>
    <h2>Arquivos analisados</h2>
    <ul class="files">{files}</ul>
  </header>
  <section class="resumo" aria-label="Quadro-resumo">
    <article class="alto"><strong>{alto}</strong><span>alto</span></article>
    <article class="medio"><strong>{medio}</strong><span>médio</span></article>
    <article class="info"><strong>{info}</strong><span>info</span></article>
    <article><strong>{total}</strong><span>no total</span></article>
  </section>
  {sections}
  <footer>{disclaimer}</footer>
</main>
</body>
</html>
"""

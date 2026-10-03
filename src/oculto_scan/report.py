"""Terminal, JSON and HTML reports. JSON and HTML never include raw values."""

from __future__ import annotations

import html
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from oculto_scan import __version__
from oculto_scan.models import RISK_LABEL, RISK_RANK, Finding, NetworkHint

DISCLAIMER = "nenhum achado não significa arquivo limpo."
HTML_CELL_EXAMPLES = 20
HTML_ROWS_PER_TYPE = 500
_JSON_NOTE = "A lista de cada célula sai com --format json."

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


def ensure_stdio() -> None:
    """Replace a missing stdout or stderr.

    ``pythonw`` and a windowed PyInstaller exe leave both as ``None``.
    ``print`` and ``isatty`` would then raise. A discarded stream keeps the
    window alive and leaves the console program unchanged when a stream exists.
    """
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="replace")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")


def stdout_wants_color(*, no_color: bool) -> bool:
    """Color only on a TTY, unless NO_COLOR or --no-color says otherwise."""
    ensure_stdio()
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


def _without_map(findings: list[Finding]) -> list[Finding]:
    return [finding for finding in findings if finding.rule != "mapa-rede"]


def _network_lines(hints: list[NetworkHint], *, show: bool, color: bool) -> list[str]:
    lines = ["", "Mapa da rede"]
    if not hints:
        lines.append("  Nenhum indício de rede interna.")
        return lines
    for hint in hints:
        risk = RISK_LABEL.get(hint.risk, hint.risk)
        risk_shown = _paint(risk, _RISK_COLOR.get(hint.risk, ""), color=color)
        where = " › ".join(piece for piece in (hint.sheet, hint.cell, hint.source) if piece)
        lines.append(f"  {hint.type_label} › {risk_shown} › {where or '—'}")
        lines.append(f"    {hint.message}")
        value = hint.evidence_raw if show and hint.evidence_raw else hint.evidence_masked
        lines.append(f"    valor: {value}")
    return lines


def render_text(
    findings: list[Finding],
    *,
    show: bool,
    ignored: int,
    scanned: int,
    color: bool = False,
    network: list[NetworkHint] | None = None,
) -> str:
    lines: list[str] = []
    groups = _by_file(_without_map(findings))
    if not groups:
        if scanned == 0:
            lines.append("Nenhuma planilha .xlsx ou .xlsm encontrada.")
        elif not findings:
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
    if network is not None:
        lines.extend(_network_lines(network, show=show, color=color))
    counts = summary(findings)
    lines.append("---")
    lines.append(_summary_line(counts, ignored, color=color))
    lines.append(DISCLAIMER)
    return "\n".join(lines) + "\n"


def _network_json(hints: list[NetworkHint]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for hint in hints:
        rows.append(
            {
                "file": hint.file,
                "sheet": hint.sheet,
                "cell": hint.cell,
                "tipo": hint.type_label,
                "risco": hint.risk,
                "origem": hint.source,
                "valor": hint.evidence_masked,
            }
        )
    return rows


def render_json(
    findings: list[Finding],
    *,
    ignored: int,
    scanned: int,
    network: list[NetworkHint] | None = None,
) -> str:
    ordered = sorted_findings(findings)
    counts = summary(ordered)
    visible = _without_map(ordered)
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
            for finding in visible
        ],
        "mapa_da_rede": _network_json(network or []),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def fill_template(template: str, **values: str) -> str:
    """Fill ``{name}`` placeholders without calling ``str.format`` on user text.

    CSS in the template keeps doubled braces. Values are inserted afterwards,
    so a file name like ``a{x}.xlsx`` cannot break the page or run as a key.
    """
    text = template
    tokens: dict[str, str] = {}
    for index, key in enumerate(values):
        token = f"@@PH{index}@@"
        text = text.replace("{" + key + "}", token)
        tokens[token] = values[key]
    text = text.replace("{{", "\x00").replace("}}", "\x01").replace("\x00", "{").replace("\x01", "}")
    for token, value in tokens.items():
        text = text.replace(token, value)
    return text


def force_utf8_stdio() -> None:
    """Keep ``→`` readable when Windows redirects stdout as cp1252."""
    ensure_stdio()
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue


def write_private_text(path: Path, text: str) -> None:
    """Write a report that other users on the machine cannot read, when the OS allows it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            fd = -1
    finally:
        if fd >= 0:
            os.close(fd)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _format_stamp(when: datetime) -> str:
    """Local wall time plus an explicit UTC offset, e.g. ``30/09/2026 21:55 (UTC-03:00)``."""
    if when.tzinfo is None:
        when = when.astimezone()
    offset = when.utcoffset() or timedelta(0)
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"{when.strftime('%d/%m/%Y %H:%M')} (UTC{sign}{hours:02d}:{minutes:02d})"


_REVEALED_BANNER = (
    "Este relatório contém os dados revelados (--show). Não envie este arquivo a terceiros."
)


def _network_html(hints: list[NetworkHint], *, show: bool) -> str:
    if not hints:
        body = '<p class="empty">Nenhum indício de rede interna.</p>'
    else:
        rows: list[str] = []
        for hint in hints:
            value = hint.evidence_raw if show and hint.evidence_raw else hint.evidence_masked
            risk = RISK_LABEL.get(hint.risk, hint.risk)
            where = " › ".join(piece for piece in (hint.sheet, hint.cell, hint.source) if piece)
            rows.append(
                f'<tr class="risk-{_esc(hint.risk)}">'
                f"<td>{_esc(hint.type_label)}</td>"
                f'<td><span class="badge badge-{_esc(hint.risk)}">{_esc(risk)}</span></td>'
                f"<td>{_esc(where or '—')}</td>"
                f"<td>{_esc(hint.message)}</td>"
                f'<td class="value">{_esc(value)}</td>'
                "</tr>"
            )
        header = "Valor revelado" if show else "Valor mascarado"
        body = (
            "<table><thead><tr>"
            f"<th>Tipo</th><th>Risco</th><th>Onde</th><th>Explicação</th><th>{_esc(header)}</th>"
            "</tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )
    return f'<section class="mapa"><h2>Mapa da rede</h2>{body}</section>'


def _pt(number: int) -> str:
    return f"{number:,}".replace(",", ".")


class _HtmlGroup:
    __slots__ = ("file", "rule", "type_label", "risk", "message", "count", "samples")

    def __init__(self, finding: Finding) -> None:
        self.file = finding.file
        self.rule = finding.rule
        self.type_label = finding.type_label
        self.risk = finding.risk
        self.message = finding.message
        self.count = 0
        self.samples: list[tuple[str, str, str, str]] = []

    def add(self, finding: Finding) -> None:
        self.count += 1
        if len(self.samples) < HTML_CELL_EXAMPLES:
            self.samples.append(
                (
                    finding.sheet,
                    finding.cell,
                    finding.evidence_masked or "",
                    finding.evidence_raw or "",
                )
            )


def _html_groups(findings: list[Finding]) -> list[_HtmlGroup]:
    """Collapse repeats of the same type, rule, risk and explanation.

    Examples keep the first cells in scan order. The groups themselves stay
    ordered by severity, like the old row-by-row report.
    """
    groups: dict[tuple[str, str, str, str, str], _HtmlGroup] = {}
    for finding in _without_map(findings):
        key = (finding.file, finding.rule, finding.type_label, finding.risk, finding.message)
        group = groups.get(key)
        if group is None:
            group = _HtmlGroup(finding)
            groups[key] = group
        group.add(finding)

    def _rank(group: _HtmlGroup) -> tuple[int, str, str, str, str]:
        sheet, cell = ("", "")
        if group.samples:
            sheet, cell = group.samples[0][0], group.samples[0][1]
        return (-RISK_RANK.get(group.risk, 0), group.file, sheet, cell, group.rule)

    return sorted(groups.values(), key=_rank)


def _spot(sheet: str, cell: str) -> str:
    if sheet and cell:
        return f"{sheet}!{cell}"
    return sheet or cell or "—"


def _example_cells(group: _HtmlGroup) -> str:
    shown = ", ".join(_spot(sheet, cell) for sheet, cell, _masked, _raw in group.samples)
    extra = group.count - len(group.samples)
    if extra > 0:
        tail = f" e mais {_pt(extra)} células"
        return (shown + tail) if shown else tail.strip()
    return shown or "—"


def _example_values(group: _HtmlGroup, *, show: bool) -> str:
    values: list[str] = []
    for _sheet, _cell, masked, raw in group.samples:
        value = raw if show and raw else masked
        if value and value not in values:
            values.append(value)
    return " · ".join(values) if values else "—"


def _type_summary(groups: list[_HtmlGroup]) -> str:
    if not groups:
        return ""
    totals: dict[tuple[str, str], int] = {}
    for group in groups:
        key = (group.type_label, group.risk)
        totals[key] = totals.get(key, 0) + group.count
    rows = sorted(totals.items(), key=lambda item: (-RISK_RANK.get(item[0][1], 0), -item[1], item[0][0]))
    body = []
    for (label, risk), count in rows:
        risk_name = RISK_LABEL.get(risk, risk)
        body.append(
            f'<tr class="risk-{_esc(risk)}">'
            f"<td>{_esc(label)}</td>"
            f'<td><span class="badge badge-{_esc(risk)}">{_esc(risk_name)}</span></td>'
            f"<td>{_esc(_pt(count))}</td>"
            "</tr>"
        )
    table = (
        "<table><thead><tr><th>Tipo</th><th>Risco</th><th>Quantidade</th></tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )
    return (
        '<details class="tipos" open><summary>Por gravidade e tipo</summary>'
        f"{table}</details>"
    )


def _files_html(groups: list[_HtmlGroup], *, show: bool) -> str:
    if not groups:
        return ""
    by_file: dict[str, list[_HtmlGroup]] = {}
    for group in groups:
        by_file.setdefault(group.file, []).append(group)

    def _file_rank(name: str) -> tuple[int, str]:
        worst = max(RISK_RANK.get(item.risk, 0) for item in by_file[name])
        return (-worst, name)

    sections: list[str] = []
    value_header = "Valor revelado" if show else "Valor mascarado"
    for name in sorted(by_file, key=_file_rank):
        file_groups = by_file[name]
        buckets: dict[tuple[str, str], list[_HtmlGroup]] = {}
        bucket_order: list[tuple[str, str]] = []
        for group in file_groups:
            key = (group.risk, group.type_label)
            if key not in buckets:
                bucket_order.append(key)
                buckets[key] = []
            buckets[key].append(group)
        blocks: list[str] = []
        total = sum(item.count for item in file_groups)
        noun = "achado" if total == 1 else "achados"
        for risk, label in bucket_order:
            bucket = buckets[(risk, label)]
            shown = bucket[:HTML_ROWS_PER_TYPE]
            omitted = sum(item.count for item in bucket[HTML_ROWS_PER_TYPE:])
            rows: list[str] = []
            for group in shown:
                risk_name = RISK_LABEL.get(group.risk, group.risk)
                rows.append(
                    f'<tr class="risk-{_esc(group.risk)}">'
                    f"<td>{_esc(_pt(group.count))}</td>"
                    f"<td>{_esc(_example_cells(group))}</td>"
                    f'<td><span class="badge badge-{_esc(group.risk)}">{_esc(risk_name)}</span></td>'
                    f"<td>{_esc(group.message)}</td>"
                    f'<td class="value">{_esc(_example_values(group, show=show))}</td>'
                    "</tr>"
                )
            warning = ""
            if omitted:
                warning = (
                    f'<p class="omit">Mais {_esc(_pt(omitted))} achados deste tipo ficaram de fora '
                    "desta página. A lista completa sai com --format json.</p>"
                )
            kind_total = sum(item.count for item in bucket)
            opened = " open" if risk != "info" or len(shown) <= 40 else ""
            blocks.append(
                f"<details{opened}>"
                f"<summary>{_esc(label)} · {_esc(_pt(kind_total))}</summary>"
                "<table><thead><tr>"
                "<th>Quantidade</th><th>Exemplos de células</th><th>Risco</th>"
                f"<th>Explicação</th><th>{_esc(value_header)}</th>"
                "</tr></thead><tbody>"
                + "".join(rows)
                + "</tbody></table>"
                + warning
                + "</details>"
            )
        sections.append(
            '<section class="arquivo"><details open>'
            f"<summary>{_esc(name)} · {_esc(_pt(total))} {_esc(noun)}</summary>"
            + "".join(blocks)
            + "</details></section>"
        )
    return "".join(sections)


def render_html(
    findings: list[Finding],
    *,
    ignored: int,
    scanned: int,
    files: list[str],
    show: bool = False,
    generated_at: datetime | None = None,
    network: list[NetworkHint] | None = None,
) -> str:
    """Self-contained HTML. Spreadsheet text is escaped. Values stay masked unless ``show``."""
    when = generated_at if generated_at is not None else datetime.now().astimezone()
    stamp = _format_stamp(when)
    counts = summary(findings)
    grouped = _html_groups(findings)
    scanned_files = files or list(dict.fromkeys(group.file for group in grouped))
    file_items = "".join(f"<li>{_esc(name)}</li>" for name in scanned_files) or "<li>Nenhuma planilha.</li>"

    sections: list[str] = []
    if not grouped:
        if scanned == 0:
            empty = "Nenhuma planilha .xlsx ou .xlsm encontrada."
        elif not findings:
            empty = f"Nenhum achado em {scanned} planilha(s)."
        else:
            empty = ""
        if empty:
            sections.append(f'<p class="empty">{_esc(empty)}</p>')
    sections.append(_files_html(grouped, show=show))

    banner = f'<p class="revelado">{_esc(_REVEALED_BANNER)}</p>' if show else ""
    lead = (
        "Relatório de vazamento em planilha de obra. Os valores abaixo estão revelados."
        if show
        else "Relatório de vazamento em planilha de obra. Valores mascarados; nada aqui é o conteúdo original."
    )
    return fill_template(
        _HTML,
        banner=banner,
        lead=_esc(lead),
        version=_esc(__version__),
        stamp=_esc(stamp),
        scanned=_esc(scanned),
        ignored=_esc(ignored),
        alto=_esc(_pt(counts["alto"])),
        medio=_esc(_pt(counts["medio"])),
        info=_esc(_pt(counts["info"])),
        total=_esc(_pt(counts["total"])),
        files=file_items,
        tipos=_type_summary(grouped),
        sections="".join(sections),
        network=_network_html(network, show=show) if network is not None else "",
        disclaimer=_esc(DISCLAIMER),
        nota=_esc(_JSON_NOTE),
    )


_HTML = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy"
 content="default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; base-uri 'none'; form-action 'none'">
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
  .revelado {{
    margin: 0;
    padding: 0.9rem 1.25rem;
    background: #9b1c1c;
    color: #fff;
    font-weight: 700;
    text-align: center;
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
  details {{
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 10px;
    margin: 0.75rem 0;
    padding: 0.35rem 0.85rem 0.85rem;
  }}
  summary {{ cursor: pointer; font-weight: 650; padding: 0.45rem 0; }}
  summary .qtd, .qtd {{ color: var(--muted); font-weight: 650; }}
  .omit {{ color: var(--muted); margin: 0.7rem 0 0; }}
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
    tr, .resumo article, header, footer, details {{ break-inside: avoid; }}
    details, details > * {{ display: block; }}
    h2 {{ break-after: avoid; }}
    * {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  }}
</style>
</head>
<body>
{banner}
<main>
  <header>
    <h1>oculto-scan</h1>
    <p>{lead}</p>
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
  {tipos}
  {sections}
  {network}
  <footer><p>{disclaimer}</p><p>{nota}</p></footer>
</main>
</body>
</html>
"""

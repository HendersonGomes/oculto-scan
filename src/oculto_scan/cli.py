"""Command-line entry point. User-facing text is Brazilian Portuguese."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from oculto_scan import __version__
from oculto_scan.report import (
    force_utf8_stdio,
    render_html,
    render_json,
    render_text,
    stdout_wants_color,
    write_private_text,
)
from oculto_scan.scanner import scan_files

_EPILOG = """\
exemplos:
  oculto-scan proposta.xlsx
  oculto-scan pasta-de-licitacao/ --format json
  oculto-scan proposta.xlsx --format html
  oculto-scan proposta.xlsx --format html --show
  oculto-scan proposta.xlsx --format html --output relatorio.html
  oculto-scan medicao.xlsm --fail-on medio
  oculto-scan proposta.xlsx --no-color
  oculto-scan proposta.xlsx --no-hints
  oculto-scan orcamento.xlsx --ignore .oculto-ignore
  oculto-scan orcamento.xlsx --baseline .oculto-baseline.json
  oculto-scan orcamento.xlsx --update-baseline .oculto-baseline.json
  oculto-scan diff enviada.xlsx recebida.xlsx
  oculto-scan diff enviada.xlsx recebida.xlsx --format html
  oculto-scan gui

códigos de saída:
  0  nenhum achado no nível de --fail-on (padrão: alto)
  1  há achado nesse nível ou acima
  2  caminho ausente, ignore/linha de base inválidos, ou --show recusado no CI
  3  não analisado (ilegível, senha, corrompido, .xls/.csv, acima do limite,
     ou macro sem o extra oletools)

Macro em .xlsm só é lida com: pip install "oculto-scan[macro]". Sem o extra, a saída é 3.

nenhum achado não significa arquivo limpo.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oculto-scan",
        description=(
            "Procura vazamento de dados em planilhas de obra (.xlsx/.xlsm) "
            "antes do envio ou da publicação. Funciona 100% offline."
        ),
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "caminhos",
        nargs="*",
        help="arquivo ou pasta. Sem caminho, nada é varrido (a ajuda é mostrada)",
    )
    parser.add_argument(
        "--format",
        dest="formato",
        choices=("texto", "json", "html"),
        default="texto",
        help="texto no terminal (padrão), JSON mascarado ou relatório HTML",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "arquivo do relatório HTML (padrão: oculto-scan-relatorio.html, "
            "ou oculto-scan-relatorio-revelado.html com --show)"
        ),
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="desliga cores ANSI no texto do terminal",
    )
    parser.add_argument(
        "--no-hints",
        action="store_true",
        help="não mostra o bloco de próximos passos no fim do texto",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help=(
            "mostra os valores no terminal e no HTML; o JSON continua mascarado. "
            "O HTML revelado não deve ser enviado a terceiros"
        ),
    )
    parser.add_argument(
        "--fail-on",
        choices=("alto", "medio", "info", "nenhum"),
        default="alto",
        help="nível que faz o processo sair com código 1 (padrão: alto)",
    )
    parser.add_argument("--baseline", type=Path, help="arquivo de linha de base (HMAC, sem valores)")
    parser.add_argument(
        "--update-baseline",
        nargs="?",
        const="__USE_DEFAULT_OR_BASELINE__",
        default=None,
        help="grava a linha de base com os achados atuais e sai 0",
    )
    parser.add_argument("--ignore", type=Path, help="arquivo de ignore por regra ou localização")
    parser.add_argument(
        "--entropy",
        action="store_true",
        help="liga detecção por entropia (desligada por padrão; muitos falso-positivos)",
    )
    parser.add_argument(
        "--max-mb",
        type=int,
        default=None,
        metavar="N",
        help="analisa de propósito um arquivo maior que o limite padrão (64 MiB no total, 32 MiB por parte)",
    )
    parser.add_argument("--version", action="version", version=f"oculto-scan {__version__}")
    return parser


def running_in_ci() -> bool:
    """True when CI or GITHUB_ACTIONS is set. Same check that refuses --show."""
    return bool(os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"))


def show_is_blocked() -> str | None:
    """Refuse --show on a CI runner, where the log would keep the raw values."""
    if running_in_ci():
        return (
            "O --show foi recusado porque CI ou GITHUB_ACTIONS está definido. "
            "Neste ambiente o relatório não revela CPF, senha nem outros valores."
        )
    return None


def _ps_quote(value: str) -> str:
    """Double quotes for PowerShell. An embedded quote is escaped with a backtick."""
    return '"' + value.replace("`", "``").replace('"', '`"') + '"'


def _macro_extra_installed() -> bool:
    try:
        from oletools import olevba
    except ImportError:
        return False
    return olevba is not None


def _example_path(argv_paths: list[str], scanned: list[str]) -> str:
    if len(argv_paths) == 1:
        candidate = Path(argv_paths[0])
        if candidate.suffix.lower() in {".xlsx", ".xlsm", ".xls", ".csv"} or candidate.is_file():
            return str(candidate)
    if scanned:
        return scanned[0]
    if argv_paths:
        return argv_paths[0]
    return "arquivo.xlsx"


def _needs_macro_hint(argv_paths: list[str], scanned: list[str]) -> bool:
    names = [*argv_paths, *scanned]
    if not any(Path(name).suffix.lower() == ".xlsm" for name in names):
        return False
    return not _macro_extra_installed()


def next_steps_text(path: str, *, show: bool, needs_macro: bool) -> str:
    """Up to four commands under one heading. Text output only."""
    quoted = _ps_quote(path)
    other_name = "original.xlsx" if Path(path).name.casefold() == "recebido.xlsx" else "recebido.xlsx"
    commands: list[str] = []
    if needs_macro:
        commands.append('python -m pip install "oculto-scan[macro]"')
    if not show:
        commands.append(f"oculto-scan {quoted} --show")
    commands.append(f"oculto-scan {quoted} --format html")
    commands.append(f'oculto-scan diff {quoted} {_ps_quote(other_name)}')
    commands.append(f"oculto-scan {quoted} --format json")
    picked = commands[:3]
    picked.append("oculto-scan --help")
    lines = ["Próximos passos:", *[f"  {command}" for command in picked]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    force_utf8_stdio()
    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0] == "diff":
        from oculto_scan.diff import run_diff

        return run_diff(args_list[1:])
    if args_list and args_list[0] == "gui":
        from oculto_scan.gui import main as gui_main

        return gui_main(args_list[1:])
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.caminhos:
        parser.print_help(sys.stderr)
        print(
            "Informe o arquivo ou a pasta. Sem caminho, a pasta atual não é varrida.",
            file=sys.stderr,
        )
        return 2
    if args.show:
        blocked = show_is_blocked()
        if blocked:
            print(blocked, file=sys.stderr)
            return 2
    baseline: Path | None = args.baseline
    update = False
    if args.update_baseline is not None:
        update = True
        if args.update_baseline != "__USE_DEFAULT_OR_BASELINE__":
            baseline = Path(args.update_baseline)
        elif baseline is None:
            baseline = Path(".oculto-baseline.json")

    if args.output is not None and args.formato != "html":
        print("--output é o caminho do relatório HTML; use junto com --format html.", file=sys.stderr)
        return 2

    result = scan_files(
        [Path(item) for item in args.caminhos],
        fail_on=args.fail_on,
        ignore_path=args.ignore,
        baseline_path=baseline,
        update=update,
        entropy=args.entropy,
        max_mb=args.max_mb,
    )
    for message in result.messages:
        print(message, file=sys.stderr)
    if result.exit_code == 2 and not result.findings and result.messages:
        return 2
    if args.formato == "json":
        sys.stdout.write(
            render_json(
                result.findings,
                ignored=result.ignored,
                scanned=result.scanned,
                network=result.network,
            )
        )
    elif args.formato == "html":
        if args.output is not None:
            target = args.output
        elif args.show:
            target = Path("oculto-scan-relatorio-revelado.html")
        else:
            target = Path("oculto-scan-relatorio.html")
        write_private_text(
            target,
            render_html(
                result.findings,
                ignored=result.ignored,
                scanned=result.scanned,
                files=result.files,
                show=args.show,
                network=result.network,
            ),
        )
        print(f"Relatório salvo em {target}")
    else:
        sys.stdout.write(
            render_text(
                result.findings,
                show=args.show,
                ignored=result.ignored,
                scanned=result.scanned,
                color=stdout_wants_color(no_color=args.no_color),
                network=result.network,
            )
        )
        if not args.no_hints and not running_in_ci():
            example = _example_path(list(args.caminhos), result.files)
            sys.stdout.write(
                "\n"
                + next_steps_text(
                    example,
                    show=args.show,
                    needs_macro=_needs_macro_hint(list(args.caminhos), result.files),
                )
            )
    return result.exit_code


def console_main() -> None:
    sys.exit(main())

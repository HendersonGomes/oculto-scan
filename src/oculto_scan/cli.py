"""Command-line entry point. User-facing text is Brazilian Portuguese."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from oculto_scan import __version__
from oculto_scan.report import render_html, render_json, render_text, stdout_wants_color
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
  oculto-scan orcamento.xlsx --ignore .oculto-ignore
  oculto-scan orcamento.xlsx --baseline .oculto-baseline.json
  oculto-scan orcamento.xlsx --update-baseline .oculto-baseline.json
  oculto-scan diff enviada.xlsx recebida.xlsx
  oculto-scan diff enviada.xlsx recebida.xlsx --format html

códigos de saída:
  0  nenhum achado no nível de --fail-on (padrão: alto)
  1  há achado nesse nível ou acima
  2  caminho ausente, ignore/linha de base inválidos

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
    parser.add_argument("caminhos", nargs="*", default=["."], help="arquivo ou pasta (varredura recursiva)")
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
    parser.add_argument("--version", action="version", version=f"oculto-scan {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0] == "diff":
        from oculto_scan.diff import run_diff

        return run_diff(args_list[1:])
    parser = build_parser()
    args = parser.parse_args(argv)
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
    )
    for message in result.messages:
        print(message, file=sys.stderr)
    if result.exit_code == 2 and not result.findings and result.messages:
        return 2
    if args.formato == "json":
        sys.stdout.write(
            render_json(result.findings, ignored=result.ignored, scanned=result.scanned)
        )
    elif args.formato == "html":
        if args.output is not None:
            target = args.output
        elif args.show:
            target = Path("oculto-scan-relatorio-revelado.html")
        else:
            target = Path("oculto-scan-relatorio.html")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            render_html(
                result.findings,
                ignored=result.ignored,
                scanned=result.scanned,
                files=result.files,
                show=args.show,
            ),
            encoding="utf-8",
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
            )
        )
    return result.exit_code


def console_main() -> None:
    sys.exit(main())

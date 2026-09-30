"""Command-line entry point. User-facing text is Brazilian Portuguese."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from oculto_scan import __version__
from oculto_scan.report import render_json, render_text
from oculto_scan.scanner import scan_files

_EPILOG = """\
exemplos:
  oculto-scan proposta.xlsx
  oculto-scan pasta-de-licitacao/ --format json
  oculto-scan medicao.xlsm --fail-on medio
  oculto-scan orcamento.xlsx --ignore .oculto-ignore
  oculto-scan orcamento.xlsx --baseline .oculto-baseline.json
  oculto-scan orcamento.xlsx --update-baseline .oculto-baseline.json

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
        choices=("texto", "json"),
        default="texto",
        help="saída no terminal (padrão: texto) ou JSON mascarado",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="mostra valores crus no texto do terminal; o JSON continua mascarado",
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
    else:
        sys.stdout.write(
            render_text(
                result.findings,
                show=args.show,
                ignored=result.ignored,
                scanned=result.scanned,
            )
        )
    return result.exit_code


def console_main() -> None:
    sys.exit(main())

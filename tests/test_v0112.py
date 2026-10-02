"""Window layout data, missing stdio, and the two Windows executables. No display."""

import importlib.util
import sys
from pathlib import Path

from oculto_scan.cli import main as cli_main
from oculto_scan.diff import DiffChange, DiffReport
from oculto_scan.gui import main as gui_main
from oculto_scan.gui_logic import (
    ACHADOS,
    ERRO,
    LIMPO,
    VAZIO,
    Session,
    card_counts,
    compare_files,
    result_text,
    risk_grade,
    scan_file,
    type_counts,
    view_state,
    window_cards,
)
from oculto_scan.gui_theme import (
    ALTO,
    AMBER,
    CARD,
    CREAM,
    GAUGE_ALTO_TEXT,
    GAUGE_BG,
    GAUGE_CARD,
    GAUGE_CREAM,
    GAUGE_INFO,
    GAUGE_INK,
    GAUGE_MEDIO,
    GAUGE_MUTED,
    INFO,
    INK,
    MEDIO,
    MUTED,
    NAVY,
    contrast_ratio,
)
from oculto_scan.models import Finding
from oculto_scan.report import ensure_stdio, stdout_wants_color
from tests.workbook_factory import build_workbook

ROOT = Path(__file__).resolve().parents[1]


def test_text_on_the_dark_theme_stays_readable():
    assert contrast_ratio(CREAM, NAVY) >= 4.5
    assert contrast_ratio(MUTED, NAVY) >= 4.5
    assert contrast_ratio(ALTO, CARD) >= 4.5
    assert contrast_ratio(MEDIO, CARD) >= 4.5
    assert contrast_ratio(INFO, CARD) >= 4.5
    assert contrast_ratio(INK, AMBER) >= 4.5
    assert contrast_ratio(GAUGE_CREAM, GAUGE_BG) >= 4.5
    assert contrast_ratio(GAUGE_MUTED, GAUGE_BG) >= 4.5
    assert contrast_ratio(GAUGE_ALTO_TEXT, GAUGE_CARD) >= 4.5
    assert contrast_ratio(GAUGE_MEDIO, GAUGE_CARD) >= 4.5
    assert contrast_ratio(GAUGE_INFO, GAUGE_CARD) >= 4.5
    assert contrast_ratio(GAUGE_INK, AMBER) >= 4.5


def test_cards_follow_the_same_counts_as_the_report(tmp_path):
    empty = Session()
    assert view_state(empty) == VAZIO
    assert card_counts(empty) == []
    refused = scan_file(tmp_path / "nota.txt")
    assert view_state(refused) == ERRO
    assert card_counts(refused) == []

    clean = tmp_path / "medicao.xlsx"
    build_workbook(
        clean,
        [{"name": "Medicao", "cells": [{"ref": "A1", "value": "Item"}, {"ref": "B2", "value": 12}]}],
    )
    clean_session = scan_file(clean)
    assert view_state(clean_session) == LIMPO
    assert card_counts(clean_session) == [
        ("alto", "alto", 0),
        ("medio", "médio", 0),
        ("info", "info", 0),
        ("total", "total", 0),
    ]

    demo = tmp_path / "proposta.xlsx"
    build_workbook(
        demo,
        [
            {
                "name": "Proposta",
                "cells": [{"ref": "C2", "formula": "Custos!B2*1.35", "value": 1350}],
                "comments": [{"ref": "C2", "author": "Ana", "text": "conferir margem"}],
            },
            {"name": "Custos", "state": "hidden", "cells": [{"ref": "B2", "value": 1000}]},
        ],
    )
    session = scan_file(demo)
    assert view_state(session) == ACHADOS
    counts = {key: count for key, _label, count in card_counts(session)}
    assert counts["alto"] == 2
    assert counts["medio"] == 1
    assert counts["info"] == 1
    assert counts["total"] == 4
    kinds = dict(type_counts(session))
    assert kinds["aba oculta"] == 1
    assert kinds["fórmula oculta"] == 1

    original = tmp_path / "original.xlsx"
    received = tmp_path / "recebido.xlsx"
    build_workbook(original, [{"name": "Proposta", "cells": [{"ref": "A1", "value": "quantidade 12"}]}])
    build_workbook(received, [{"name": "Proposta", "cells": [{"ref": "A1", "value": "quantidade 40"}]}])
    diff = compare_files(original, received)
    assert view_state(diff) == ACHADOS
    diff_cards = {key: count for key, _label, count in card_counts(diff)}
    assert diff_cards["total"] >= 1


def _info(count: int) -> Session:
    findings = [
        Finding(
            file="a.xlsx",
            sheet="P",
            cell=f"A{index}",
            rule="formula-constante",
            type_label="constante",
            risk="info",
            message="Fórmula com constante numérica.",
        )
        for index in range(1, count + 1)
    ]
    return Session(mode="scan", findings=findings, names=("a.xlsx",))


def test_risk_grade_follows_the_worst_finding_and_the_count():
    assert risk_grade(Session()) == ("", "")
    assert risk_grade(Session(error="Arquivo não encontrado.")) == ("erro", "Arquivo não encontrado.")
    assert risk_grade(_info(0)) == ("limpo", "nota geral · nenhum achado")
    assert risk_grade(_info(1)) == ("baixo", "nota geral · 1 info")
    assert risk_grade(_info(3)) == ("baixo", "nota geral · 3 infos")
    assert risk_grade(_info(4)) == ("medio", "nota geral · 4 infos")
    medium = _info(1)
    medium.findings[0] = Finding(
        file="a.xlsx",
        sheet="P",
        cell="A1",
        rule="comentario",
        type_label="comentário",
        risk="medio",
        message="nota",
    )
    assert risk_grade(medium)[0] == "medio"
    many_medium = Session(
        mode="scan",
        findings=[
            Finding(
                file="a.xlsx",
                sheet="P",
                cell=f"A{index}",
                rule="comentario",
                type_label="comentário",
                risk="medio",
                message="nota",
            )
            for index in range(8)
        ],
    )
    assert risk_grade(many_medium)[0] == "medio"


def test_window_cards_stay_short_and_masked(tmp_path):
    demo = tmp_path / "proposta.xlsx"
    build_workbook(
        demo,
        [
            {
                "name": "Proposta",
                "cells": [{"ref": "C2", "formula": "Custos!B2*1.35", "value": 1350}],
                "comments": [{"ref": "C2", "author": "Ana", "text": "conferir margem"}],
            },
            {"name": "Custos", "state": "hidden", "cells": [{"ref": "B2", "value": 1000}]},
        ],
    )
    session = scan_file(demo)
    assert risk_grade(session) == ("alto", "nota geral · 2 altos")
    cards = window_cards(session, show=False)
    titles = [card.title for card in cards]
    assert titles[:2] == ["Aba escondida", "Preço ligado a custo oculto"]
    assert "Comentário interno" in titles
    assert "Número fixo na fórmula" in titles
    hidden = cards[0]
    assert hidden.where == "Aba Custos"
    assert "Custos" in hidden.action
    assert "Em proposta" not in hidden.action
    formula = next(card for card in cards if card.title == "Preço ligado a custo oculto")
    assert "Custos!B2*[n]" in formula.action
    assert "1.35" not in formula.action
    comment = next(card for card in cards if card.title == "Comentário interno")
    assert comment.where.endswith("autor An*")
    assert "Texto mascarado" in comment.action
    assert "conferir margem" not in comment.action
    number = next(card for card in cards if card.title == "Número fixo na fórmula")
    assert "[n]" in number.action
    blob = " ".join(f"{card.title} {card.where} {card.action}" for card in cards)
    assert "1.35" not in blob
    assert "conferir margem" not in blob
    revealed = " ".join(card.action for card in window_cards(session, show=True)).casefold()
    assert "1.35" in revealed
    assert "conferir margem" in revealed
    report = result_text(session, show=False)
    assert "Aba oculta. Em proposta" in report
    assert "conferir margem" not in report

    unknown = window_cards(
        Session(
            mode="scan",
            findings=[
                Finding(
                    file="a.xlsx",
                    sheet="P",
                    cell="B2",
                    rule="novo",
                    type_label="sinal novo",
                    risk="info",
                    message="texto longo que não entra no cartão",
                    evidence_raw="segredo-cru",
                )
            ],
        ),
        show=False,
    )[0]
    assert unknown.title == "Sinal novo"
    assert unknown.action == "Veja o detalhe no relatório HTML."
    assert "segredo-cru" not in unknown.action

    original = tmp_path / "original.xlsx"
    received = tmp_path / "recebido.xlsx"
    build_workbook(original, [{"name": "Proposta", "cells": [{"ref": "A1", "value": "quantidade 12"}]}])
    build_workbook(received, [{"name": "Proposta", "cells": [{"ref": "A1", "value": "quantidade 40"}]}])
    diff = compare_files(original, received)
    assert risk_grade(diff)[0] == "alto"
    masked = window_cards(diff, show=False)
    assert masked
    assert all("quantidade 40" not in card.action for card in masked)
    shown = window_cards(diff, show=True)
    assert any("quantidade 40" in card.action for card in shown)

    quiet = DiffReport(
        original="a.xlsx",
        received="b.xlsx",
        changes=[],
        metadata=[],
        identical=True,
        headline="Os arquivos coincidem.",
        exit_code=0,
    )
    assert risk_grade(Session(mode="diff", diff=quiet))[0] == "limpo"
    assert window_cards(Session(mode="diff", diff=quiet), show=False) == []
    meta = [
        DiffChange(
            sheet="",
            cell="Autor",
            type_label="metadado",
            category="metadado",
            message="mudou",
            before_masked="An*",
            after_masked="Be*",
            before_raw="Ana",
            after_raw="Beto",
        )
        for _index in range(4)
    ]
    lifted = DiffReport("a.xlsx", "b.xlsx", meta, [], False, None, 1)
    assert risk_grade(Session(mode="diff", diff=lifted))[0] == "medio"


def test_window_source_keeps_cards_and_the_html_buttons():
    source = (ROOT / "src" / "oculto_scan" / "gui_window.py").read_text(encoding="utf-8")
    assert "result_text(" not in source
    assert "tk.Canvas" in source
    assert "Salvar relatório HTML" in source
    assert "Abrir relatório HTML" in source
    assert "Escolher..." in source
    assert "Comparar dois arquivos" in source


def test_missing_stdio_does_not_crash(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    ensure_stdio()
    assert stdout_wants_color(no_color=False) is False
    print("janela")
    print("erro", file=sys.stderr)

    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    assert gui_main(["--version"]) == 0

    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    assert cli_main([]) == 2


def test_windows_split_keeps_a_window_and_a_console():
    spec = (ROOT / "packaging" / "oculto-scan.spec").read_text(encoding="utf-8")
    assert '"oculto-scan",\n    console=False' in spec
    assert '"oculto-scan-cli",\n    console=True' in spec
    assert "upx=False" in spec
    script = (ROOT / "packaging" / "oculto-scan.iss").read_text(encoding="utf-8-sig")
    assert "oculto-scan-cli.exe" in script
    assert 'Filename: "{app}\\{#MyAppExeName}"' in script
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    scripts, _, rest = pyproject.partition("[project.scripts]")
    assert scripts is not None
    block, _, _after = rest.partition("[project.gui-scripts]")
    assert "oculto-scan-gui" not in block
    assert 'oculto-scan = "oculto_scan.cli:console_main"' in block
    assert 'oculto-scan-gui = "oculto_scan.gui:console_main"' in pyproject
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "pythonw" in readme
    assert "oculto-scan-cli.exe" in readme
    assert "sem a janela preta" in readme


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_pe_subsystem_reads_the_optional_header(tmp_path):
    module = _load(ROOT / "packaging" / "pe_subsystem.py", "oculto_scan_pe_subsystem")
    blob = bytearray(256)
    blob[0:2] = b"MZ"
    blob[0x3C:0x40] = (64).to_bytes(4, "little")
    blob[64:68] = b"PE\0\0"
    blob[64 + 24 + 68 : 64 + 24 + 70] = (2).to_bytes(2, "little")
    path = tmp_path / "janela.exe"
    path.write_bytes(blob)
    assert module.pe_subsystem(path) == module.WINDOWS_GUI
    blob[64 + 24 + 68 : 64 + 24 + 70] = (3).to_bytes(2, "little")
    path.write_bytes(blob)
    assert module.pe_subsystem(path) == module.WINDOWS_CUI
    assert module.main([str(path), "3"]) == 0

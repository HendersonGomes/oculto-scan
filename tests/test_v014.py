"""Regression tests for the 0.1.4 review fixes.

Each behavior has a case that must fire and a case that must not.
"""

import os
import stat

from oculto_scan.cli import main
from oculto_scan.formulas import parse_formula
from oculto_scan.masking import mask_formula, mask_link, mask_secret, mask_url
from oculto_scan.public import diff_bytes, scan_bytes
from oculto_scan.refs import index_to_col
from oculto_scan.report import force_utf8_stdio, render_html
from oculto_scan.secrets import find_secrets
from oculto_scan.workbook import _shift_formula
from tests.workbook_factory import build_workbook, make_cpf


def _rules(findings, rule):
    return [item for item in findings if item.rule == rule]


def test_html_filename_with_braces_and_script_is_escaped(tmp_path):
    from oculto_scan.analyze import analyze
    from oculto_scan.models import Finding
    from oculto_scan.workbook import load_workbook

    braced = tmp_path / "a{x}.xlsx"
    build_workbook(braced, [{"name": "Proposta", "cells": [{"ref": "A1", "value": "ok"}]}])
    page = render_html(
        analyze(load_workbook(braced), braced.name),
        ignored=0,
        scanned=1,
        files=[braced.name],
    )
    assert "a{x}.xlsx" in page
    assert "KeyError" not in page
    assert "Content-Security-Policy" in page
    assert "default-src 'none'" in page

    hostile = Finding(
        file="<script>alert(1)</script>.xlsx",
        sheet="Aba",
        cell="A1",
        rule="comentario",
        type_label="comentário",
        risk="medio",
        message="Há nota",
        evidence_masked="texto",
    )
    attacked = render_html([hostile], ignored=0, scanned=1, files=[hostile.file])
    assert "<script" not in attacked.lower()
    assert "&lt;script&gt;" in attacked
    plain = Finding(
        file="proposta.xlsx",
        sheet="Aba",
        cell="A1",
        rule="comentario",
        type_label="comentário",
        risk="medio",
        message="Há nota",
        evidence_masked="texto",
    )
    quiet = render_html([plain], ignored=0, scanned=1, files=["proposta.xlsx"])
    assert "proposta.xlsx" in quiet
    assert "&lt;script&gt;" not in quiet


def test_link_mask_keeps_only_host_and_formula_hides_quotes():
    url = "https://sharepoint.example/sites/obra/custos.xlsx"
    assert mask_url(url) == "https://sharepoint.example"
    assert "sites/obra" not in mask_link(url)
    assert mask_link(r"C:\Users\ana.sintetica\notas\laudo.pdf") == "laudo.pdf"
    assert mask_link("custos.xlsx") == "custos.xlsx"
    masked = mask_formula('=A1&"senha-interna"&1.35')
    assert "senha-interna" not in masked
    assert "«texto»" in masked
    assert "1.35" not in masked
    assert mask_secret("AKIAIOSFODNN7EXAMPLE") == "(20 caracteres)"


def test_show_is_refused_on_ci_and_allowed_outside(tmp_path, monkeypatch, capsys):
    path = tmp_path / "proposta.xlsx"
    cpf = make_cpf("529982247")
    build_workbook(
        path,
        [{"name": "Funcionários", "cells": [{"ref": "A1", "value": "CPF"}, {"ref": "A2", "value": cpf}]}],
    )
    monkeypatch.setenv("CI", "true")
    code = main([str(path), "--show"])
    captured = capsys.readouterr()
    assert code == 2
    assert "recusado" in captured.err
    assert cpf not in captured.out
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    code = main([str(path), "--show", "--fail-on", "info"])
    revealed = capsys.readouterr().out
    assert code == 1
    assert cpf in revealed


def test_corrupt_file_does_not_abort_the_folder_and_csv_is_explicit(tmp_path, capsys):
    folder = tmp_path / "lote"
    folder.mkdir()
    (folder / "quebrado.xlsx").write_bytes(b"nao e zip")
    build_workbook(
        folder / "ok.xlsx",
        [{"name": "Custos", "state": "hidden", "cells": [{"ref": "A1", "value": "10"}]}],
    )
    (folder / "antigo.csv").write_text("a,b\n", encoding="utf-8")
    code = main([str(folder), "--format", "json"])
    out = capsys.readouterr().out
    assert code == 3
    assert "corrompido" in out
    assert "aba oculta" in out or "aba-oculta" in out
    assert "csv" not in out.lower() or "nao-analisado" not in out.split("antigo")[0]

    code = main([str(folder / "antigo.csv")])
    text = capsys.readouterr()
    assert code == 3
    assert ".xls" in text.out or ".csv" in text.err or "csv" in (text.out + text.err).lower()
    plain = tmp_path / "nota.txt"
    plain.write_text("oi", encoding="utf-8")
    code = main([str(plain)])
    assert code == 0 or code == 2


def test_size_limit_is_not_hostile_and_max_mb_raises_it(tmp_path, monkeypatch, capsys):
    path = tmp_path / "grande.xlsx"
    build_workbook(path, [{"name": "Proposta", "cells": [{"ref": "A1", "value": "ok"}]}])
    monkeypatch.setattr("oculto_scan.zipsafe.MAX_MEMBER_UNCOMPRESSED", 20)
    monkeypatch.setattr("oculto_scan.zipsafe.MAX_TOTAL_UNCOMPRESSED", 20)
    monkeypatch.setattr("oculto_scan.zipsafe.MAX_FILE_BYTES", 20)
    code = main([str(path)])
    captured = capsys.readouterr()
    blob = captured.out + captured.err
    assert code == 3
    assert "acima do limite" in blob
    assert "arquivo hostil" not in blob
    assert "arquivo-hostil" not in blob
    code = main([str(path), "--max-mb", "64"])
    captured = capsys.readouterr()
    assert code == 0
    assert "acima do limite" not in captured.out + captured.err


def test_utf8_stdio_and_private_html(tmp_path, monkeypatch, capsys):
    calls = []

    class _Stream:
        def reconfigure(self, **kwargs):
            calls.append(kwargs)

        def isatty(self):
            return False

    monkeypatch.setattr("sys.stdout", _Stream())
    monkeypatch.setattr("sys.stderr", _Stream())
    force_utf8_stdio()
    assert calls[0]["encoding"] == "utf-8"
    assert calls[0]["errors"] == "replace"

    monkeypatch.undo()
    path = tmp_path / "proposta.xlsx"
    build_workbook(path, [{"name": "Proposta", "cells": [{"ref": "A1", "value": "ok"}]}])
    monkeypatch.chdir(tmp_path)
    code = main([str(path), "--format", "html", "--output", "relatorio.html"])
    assert code == 0
    report = tmp_path / "relatorio.html"
    mode = stat.S_IMODE(report.stat().st_mode)
    assert mode == 0o600


def test_accented_sheet_structured_ref_and_log10(tmp_path):
    info = parse_formula("=Orçamento!B5")
    assert ("Orçamento", "B5") in info.sheet_refs
    missed = parse_formula("=Orcamento!B5")
    assert ("Orçamento", "B5") not in missed.sheet_refs

    structured = parse_formula("=Tabela1[Valor]")
    assert structured.external == []
    external = parse_formula("=[precos.xlsx]Custos!A1")
    assert external.external

    assert _shift_formula("LOG10(A1)", 1, 0) == "LOG10(A2)"
    assert _shift_formula('="A1"&A1', 1, 0) == '="A1"&A2'
    assert _shift_formula("ATAN2(B2)", 0, 1) == "ATAN2(C2)"

    path = tmp_path / "log.xlsx"
    build_workbook(
        path,
        [
            {
                "name": "Proposta",
                "cells": [
                    {"ref": "A1", "formula": "LOG10(B1)", "value": 1, "shared": "0", "shared_ref": "A1:A2"},
                    {"ref": "A2", "shared": "0", "value": 2},
                ],
            }
        ],
    )
    from oculto_scan.workbook import load_workbook

    formulas = {cell.ref: cell.formula for cell in load_workbook(path).sheets[0].cells}
    assert formulas["A2"] == "LOG10(B2)"

    hidden_col = index_to_col(300)
    wide = tmp_path / "largo.xlsx"
    build_workbook(
        wide,
        [
            {"name": "Custos", "hidden_cols": [300], "cells": [{"ref": f"{hidden_col}1", "value": 1}]},
            {"name": "Proposta", "cells": [{"ref": "B2", "formula": f"Custos!{hidden_col}1"}]},
        ],
    )
    from oculto_scan.analyze import analyze

    findings = analyze(load_workbook(wide), "largo.xlsx")
    assert any(item.rule == "formula-referencia-oculta" for item in findings)
    near = tmp_path / "perto.xlsx"
    build_workbook(
        near,
        [
            {"name": "Custos", "hidden_rows": [2500], "cells": [{"ref": "A1", "value": 1}]},
            {"name": "Proposta", "cells": [{"ref": "B2", "formula": "Custos!A1:A10"}]},
        ],
    )
    quiet = analyze(load_workbook(near), "perto.xlsx")
    assert not any(item.rule == "formula-referencia-oculta" and item.cell == "B2" for item in quiet)
    far = tmp_path / "longe.xlsx"
    build_workbook(
        far,
        [
            {"name": "Custos", "hidden_rows": [2500], "cells": [{"ref": "A1", "value": 1}]},
            {"name": "Proposta", "cells": [{"ref": "B2", "formula": "Custos!A1:A3000"}]},
        ],
    )
    loud = analyze(load_workbook(far), "longe.xlsx")
    assert any(item.rule == "formula-referencia-oculta" and item.cell == "B2" for item in loud)


def test_cpf_header_blocks_phone_column_and_accepts_short_cpf(tmp_path):
    from oculto_scan.analyze import analyze
    from oculto_scan.workbook import load_workbook

    full = make_cpf("529982247")
    short_source = make_cpf("012345678")
    raw_digits = short_source.replace(".", "").replace("-", "")
    assert raw_digits.startswith("0") and len(raw_digits) == 11
    short = raw_digits[1:]
    path = tmp_path / "folha.xlsx"
    build_workbook(
        path,
        [
            {
                "name": "Funcionários",
                "cells": [
                    {"ref": "A1", "value": "Quadro de pessoal"},
                    {"ref": "A7", "value": "CPF"},
                    {"ref": "B7", "value": "Telefone"},
                    {"ref": "A8", "value": full},
                    {"ref": "B8", "value": full},
                    {"ref": "C7", "value": "CPF"},
                    {"ref": "C8", "value": short},
                    {"ref": "D7", "value": "Quantidade"},
                    {"ref": "D8", "value": short},
                ],
            }
        ],
    )
    findings = analyze(load_workbook(path), "folha.xlsx")
    cpfs = [item for item in findings if item.rule == "cpf"]
    cells = {item.cell for item in cpfs}
    assert "A8" in cells
    assert "C8" in cells
    assert "B8" not in cells
    assert "D8" not in cells

    labeled = tmp_path / "rotulo.xlsx"
    build_workbook(
        labeled,
        [
            {
                "name": "Proposta",
                "cells": [
                    {"ref": "C5", "value": "CPF"},
                    {"ref": "D5", "value": full},
                    {"ref": "C6", "value": "Item"},
                    {"ref": "D6", "value": full},
                ],
            }
        ],
    )
    labeled_hits = analyze(load_workbook(labeled), "rotulo.xlsx")
    labeled_cells = {item.cell for item in labeled_hits if item.rule == "cpf"}
    assert "D5" in labeled_cells
    assert "D6" not in labeled_cells


def test_portuguese_secret_labels_and_plain_sentence():
    hits = find_secrets("aws_secret_access_key: wJalrXUtnFEMIexample")
    assert any(hit.rule == "senha-ou-token" for hit in hits)
    portal = find_secrets("Senha do portal: s3gr3d0-sintetico")
    assert any(hit.value == "s3gr3d0-sintetico" for hit in portal)
    assert find_secrets("A senha do portal é forte demais") == []
    assert find_secrets("senha: exemplo") == []


def test_hidden_without_the_hide_command(tmp_path):
    from oculto_scan.analyze import analyze
    from oculto_scan.workbook import load_workbook

    path = tmp_path / "some.xlsx"
    build_workbook(
        path,
        [
            {
                "name": "Proposta",
                "col_widths": {2: 0},
                "row_heights": {3: 0},
                "cells": [
                    {"ref": "A1", "value": "visível", "num_fmt": ";;;"},
                    {"ref": "B2", "value": "sumiu na largura"},
                    {"ref": "A3", "value": "sumiu na altura"},
                    {"ref": "C2", "formula": "Z9"},
                    {"ref": "A2", "value": "dentro"},
                ],
            }
        ],
        defined_names=[{"name": "_xlnm.Print_Area", "formula": "Proposta!$A$1:$A$2"}],
        persons=[{"name": "Autora Sintetica", "userId": "autora@exemplo.test"}],
        external_cache=[{"ref": "A1", "value": "Senha do portal: s3gr3d0-sintetico"}],
    )
    findings = analyze(load_workbook(path), "some.xlsx")
    rules = {item.rule for item in findings}
    assert "formato-oculto" in rules
    assert "largura-minima" in rules
    assert "altura-minima" in rules
    assert "fora-impressao" in rules
    assert "formula-fora-impressao" in rules
    assert any(item.rule == "metadado" and "autora@exemplo.test" == item.evidence_raw for item in findings)
    assert any(item.rule == "segredo" and item.sheet == "vínculo externo" for item in findings)
    assert all("autora@exemplo.test" not in (item.evidence_masked or "") for item in findings)

    plain = tmp_path / "normal.xlsx"
    build_workbook(
        plain,
        [{"name": "Proposta", "cells": [{"ref": "A1", "value": "só um título"}, {"ref": "B2", "formula": "A1"}]}],
    )
    quiet = {item.rule for item in analyze(load_workbook(plain), "normal.xlsx")}
    assert "formato-oculto" not in quiet
    assert "fora-impressao" not in quiet
    assert "formula-fora-impressao" not in quiet
    assert "largura-minima" not in quiet


def test_diff_hidden_new_sheet_and_useful_number_mask(tmp_path):
    from oculto_scan.diff import load_diff

    original = tmp_path / "original.xlsx"
    received = tmp_path / "recebido.xlsx"
    build_workbook(original, [{"name": "Proposta", "cells": [{"ref": "A1", "value": 1000}]}])
    build_workbook(
        received,
        [
            {"name": "Proposta", "cells": [{"ref": "A1", "value": 2000}]},
            {"name": "Custos", "state": "hidden", "cells": [{"ref": "B2", "value": 10}]},
        ],
    )
    report = load_diff(original, received)
    labels = {(item.sheet, item.type_label) for item in report.changes}
    assert ("Custos", "aba criada") in labels
    assert ("Custos", "visibilidade da aba") in labels
    value = next(item for item in report.changes if item.cell == "A1")
    assert value.before_masked != "[n]" or value.after_masked != "[n]"
    assert "[n]" not in value.before_masked
    assert "1000" not in value.before_masked
    visible = tmp_path / "visivel.xlsx"
    build_workbook(
        visible,
        [{"name": "Proposta", "cells": [{"ref": "A1", "value": 1000}]}, {"name": "Extra", "cells": []}],
    )
    same = load_diff(original, visible)
    assert not any(item.type_label == "visibilidade da aba" and item.sheet == "Extra" for item in same.changes)


def test_no_arguments_do_not_scan_and_bytes_api_stays_in_memory(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    build_workbook(
        tmp_path / "proposta.xlsx",
        [{"name": "Custos", "state": "hidden", "cells": [{"ref": "A1", "value": "1"}]}],
    )
    code = main([])
    captured = capsys.readouterr()
    assert code == 2
    assert "aba oculta" not in captured.out
    assert "Informe o arquivo" in captured.err
    data = (tmp_path / "proposta.xlsx").read_bytes()
    before = set(os.listdir(tmp_path))
    page = scan_bytes("proposta.xlsx", data)
    diff_page = diff_bytes("original.xlsx", data, "recebido.xlsx", data)
    assert "aba oculta" in page or "Custos" in page
    assert "arquivo não foi salvo novamente" in diff_page
    assert set(os.listdir(tmp_path)) == before

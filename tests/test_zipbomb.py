import zipfile

from tests.workbook_factory import write_zip

from oculto_scan.cli import main


def test_zip_bomb_is_rejected(tmp_path, capsys):
    path = tmp_path / "bomba.xlsx"
    payload = b"\0" * (4 * 1024 * 1024)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", payload)
        archive.writestr("[Content_Types].xml", "<Types></Types>")
    code = main([str(path), "--format", "json"])
    out = capsys.readouterr().out
    assert code == 1
    assert "arquivo-hostil" in out
    assert "bomba" in out


def test_not_a_zip_and_malformed_xml(tmp_path, capsys):
    broken = tmp_path / "quebrado.xlsx"
    broken.write_bytes(b"isto nao e uma planilha")
    code = main([str(broken), "--format", "json"])
    assert code == 1
    assert "arquivo-hostil" in capsys.readouterr().out

    hostile_xml = tmp_path / "entidades.xlsx"
    write_zip(
        hostile_xml,
        {
            "xl/workbook.xml": (
                '<?xml version="1.0"?>'
                '<!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;">]>'
                "<workbook>&lol2;</workbook>"
            )
        },
    )
    code = main([str(hostile_xml), "--format", "json"])
    out = capsys.readouterr().out
    assert code == 1
    assert "arquivo-hostil" in out

    malformed = tmp_path / "xml-ruim.xlsx"
    write_zip(malformed, {"xl/workbook.xml": "<workbook><sheets></workbook>"})
    code = main([str(malformed), "--format", "json", "--fail-on", "medio"])
    out = capsys.readouterr().out
    assert code == 1
    assert "arquivo-ilegivel" in out

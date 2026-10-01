"""Contact line in the window. No display and no network."""

from pathlib import Path

from oculto_scan import __version__
from oculto_scan.gui_help import CONTACT_EMAIL, MAILTO_URL, about_text, contact_text, open_contact_mail

_README = Path(__file__).resolve().parents[1] / "README.md"


def test_contact_text_is_the_support_line():
    text = contact_text()
    assert text == (
        "Dúvidas, sugestões ou checagem de arquivos antes de licitação: "
        f"{CONTACT_EMAIL}"
    )
    assert CONTACT_EMAIL in about_text(__version__)
    assert text in about_text(__version__)


def test_mailto_is_handed_to_the_mail_program(monkeypatch):
    opened: list[str] = []

    def _open(url: str) -> bool:
        opened.append(url)
        return True

    monkeypatch.setattr("webbrowser.open", _open)
    assert open_contact_mail() is True
    assert opened == [MAILTO_URL]
    assert MAILTO_URL == f"mailto:{CONTACT_EMAIL}"


def test_readme_points_to_the_window_and_hides_the_address():
    readme = _README.read_text(encoding="utf-8")
    assert CONTACT_EMAIL not in readme
    assert "mailto:" not in readme
    assert "Dúvidas: use o menu Ajuda > Contato da janela ou" in readme
    assert "https://github.com/HendersonGomes/oculto-scan/issues" in readme

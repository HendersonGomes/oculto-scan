"""Update help text. No window and no network."""

from oculto_scan import __version__
from oculto_scan.gui_help import DOWNLOAD_URL, REPO_URL, about_text, open_download_page, update_help_text


def test_update_help_lists_both_paths():
    text = update_help_text()
    assert "não procura versão nova" in text
    assert DOWNLOAD_URL in text
    assert "Get-FileHash -Algorithm SHA256" in text
    assert "git pull" in text
    assert 'python -m pip install -e ".[macro]"' in text
    assert "oculto-scan --version" in text
    assert "Watch > Custom > Releases" in text


def test_about_shows_installed_version_and_license():
    text = about_text(__version__)
    assert text.startswith(f"oculto-scan {__version__}")
    assert "Apache-2.0" in text
    assert REPO_URL in text
    assert "0.1.9" in text


def test_download_page_is_handed_to_the_browser(monkeypatch):
    opened: list[str] = []

    def _open(url: str) -> bool:
        opened.append(url)
        return True

    monkeypatch.setattr("webbrowser.open", _open)
    assert open_download_page() is True
    assert opened == [DOWNLOAD_URL]

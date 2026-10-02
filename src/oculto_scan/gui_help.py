"""Help texts for the window. No widgets, and this module does not fetch anything."""

from __future__ import annotations

from pathlib import Path

DOWNLOAD_URL = "https://github.com/HendersonGomes/oculto-scan/releases/latest"
SETUP_URL = f"{DOWNLOAD_URL}/download/oculto-scan-setup.exe"
PORTABLE_URL = f"{DOWNLOAD_URL}/download/oculto-scan.exe"
CLI_URL = f"{DOWNLOAD_URL}/download/oculto-scan-cli.exe"
REPO_URL = "https://github.com/HendersonGomes/oculto-scan"

MENU_HELP = "Ajuda"
MENU_UPDATE = "Como atualizar"
MENU_DOWNLOAD = "Abrir página de download"
MENU_CONTACT = "Contato / suporte"
MENU_ABOUT = "Sobre"
CONTACT_EMAIL = "henderson.gomes11@gmail.com"
MAILTO_URL = f"mailto:{CONTACT_EMAIL}"


def icon_paths() -> tuple[Path, Path]:
    """PNG for the window and ICO for Windows. Both ship inside the package."""
    base = Path(__file__).resolve().parent
    return base / "oculto-scan.png", base / "oculto-scan.ico"


def update_help_text() -> str:
    """Short update steps. The program does not look for a new version by itself."""
    return (
        "O programa não procura versão nova sozinho.\n"
        "\n"
        "Instalador\n"
        "Baixe o setup novo e instale por cima. A versão antiga é substituída.\n"
        f"{SETUP_URL}\n"
        "No PowerShell, na pasta do arquivo:\n"
        "Get-FileHash -Algorithm SHA256 .\\oculto-scan-setup.exe\n"
        "\n"
        "Arquivo .exe portátil\n"
        "Baixe de novo e apague o arquivo antigo. oculto-scan.exe abre só a janela.\n"
        f"{PORTABLE_URL}\n"
        "Get-FileHash -Algorithm SHA256 .\\oculto-scan.exe\n"
        "O terminal no Windows é o oculto-scan-cli.exe:\n"
        f"{CLI_URL}\n"
        "Get-FileHash -Algorithm SHA256 .\\oculto-scan-cli.exe\n"
        "\n"
        "Instalação pelo código, na pasta do clone:\n"
        "git pull\n"
        'python -m pip install -e ".[macro]"\n'
        "oculto-scan --version\n"
        "\n"
        "No GitHub: Watch > Custom > Releases para receber e-mail a cada versão nova."
    )


def contact_text() -> str:
    """Support line shown in the window. The README does not repeat the address."""
    return (
        "Dúvidas, sugestões ou checagem de arquivos antes de licitação: "
        f"{CONTACT_EMAIL}"
    )


def about_text(version: str) -> str:
    """Version, license, repository and the same contact line as the support box."""
    return f"oculto-scan {version}\nLicença Apache-2.0\n{REPO_URL}\n\n{contact_text()}"


def open_download_page() -> bool:
    """Hand the download page to the default browser.

    This process does not request the page. The browser, if the person confirms
    by choosing the menu item, is what opens the address.
    """
    import webbrowser

    return bool(webbrowser.open(DOWNLOAD_URL))


def open_contact_mail() -> bool:
    """Hand a mailto address to the default mail program.

    This process does not send a message and does not contact a server.
    """
    import webbrowser

    return bool(webbrowser.open(MAILTO_URL))

"""Entry point for the window. ``--version`` does not open a display."""

from __future__ import annotations

import sys

from oculto_scan import __version__


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--version" in args or "-V" in args:
        print(f"oculto-scan {__version__}")
        return 0
    if "--self-check" in args:
        return _self_check()
    try:
        from oculto_scan.gui_window import run
    except ImportError as exc:
        if "tkinter" not in str(exc).casefold():
            raise
        print(
            "Não foi possível abrir a janela. No Windows, instale o Python em python.org "
            "com a opção Tcl/Tk. Nada foi enviado para a internet.",
            file=sys.stderr,
        )
        return 1
    run()
    return 0


def _self_check() -> int:
    """Headless check used by the Windows build. Does not open a window or the network."""
    import tkinter

    from oletools.olevba import VBA_Parser

    if tkinter.Tk is None or VBA_Parser is None:
        print("falhou", file=sys.stderr)
        return 1
    print(f"oculto-scan {__version__}")
    print("ok")
    return 0


def console_main() -> None:
    sys.exit(main())


def hide_console_window() -> None:
    """Hide the extra console when the window is open. ``--version`` keeps it."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except (AttributeError, OSError):
        return

"""Tk window. Widgets only: the scan itself lives in gui_logic."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from oculto_scan import __version__
from oculto_scan.gui import hide_console_window
from oculto_scan.gui_help import (
    MENU_ABOUT,
    MENU_CONTACT,
    MENU_DOWNLOAD,
    MENU_HELP,
    MENU_UPDATE,
    about_text,
    contact_text,
    open_contact_mail,
    open_download_page,
    update_help_text,
)
from oculto_scan.gui_logic import (
    Session,
    compare_files,
    result_html,
    result_text,
    scan_file,
    suggested_html_name,
    summary_line,
)
from oculto_scan.report import write_private_text

_BG = "#f7f4ef"
_INK = "#1c1915"
_MUTED = "#5c564c"
_CARD = "#fffdf9"
_ALTO = "#9f2d2d"
_MEDIO = "#8a5a12"
_INFO = "#1f5f6b"


def open_document(path: Path) -> None:
    """Open a local HTML file. This does not contact a website."""
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
        return
    command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
    subprocess.run(command, check=False)


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.session = Session()
        self.saved: Path | None = None
        root.title(f"oculto-scan {__version__}")
        root.configure(bg=_BG)
        root.minsize(720, 560)
        self._mode = tk.StringVar(value="scan")
        self._left = tk.StringVar()
        self._right = tk.StringVar()
        self._show = tk.BooleanVar(value=False)
        self._status = tk.StringVar(value="Nada é enviado para a internet. O arquivo fica neste computador.")
        self._build_menu()
        self._build()
        self._apply_mode()

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)
        help_menu = tk.Menu(menu, tearoff=0)
        help_menu.add_command(label=MENU_UPDATE, command=self._show_update_help)
        help_menu.add_command(label=MENU_DOWNLOAD, command=open_download_page)
        help_menu.add_command(label=MENU_CONTACT, command=self._show_contact)
        help_menu.add_command(label=MENU_ABOUT, command=self._show_about)
        menu.add_cascade(label=MENU_HELP, menu=help_menu)
        self.root.config(menu=menu)

    def _show_update_help(self) -> None:
        messagebox.showinfo(MENU_UPDATE, update_help_text(), parent=self.root)

    def _show_about(self) -> None:
        messagebox.showinfo(MENU_ABOUT, about_text(__version__), parent=self.root)

    def _show_contact(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(MENU_CONTACT)
        dialog.transient(self.root)
        dialog.configure(bg=_BG)
        dialog.resizable(False, False)
        tk.Label(
            dialog,
            text=contact_text(),
            wraplength=420,
            justify="left",
            bg=_BG,
            fg=_INK,
            font=("Segoe UI", 11),
        ).pack(padx=16, pady=(16, 8))
        buttons = tk.Frame(dialog, bg=_BG)
        buttons.pack(padx=16, pady=(0, 16))
        ttk.Button(buttons, text="Escrever e-mail", command=open_contact_mail).pack(side="left")
        ttk.Button(buttons, text="Fechar", command=dialog.destroy).pack(side="left", padx=8)

    def _build(self) -> None:
        pad = {"padx": 16, "pady": 4}
        frame = tk.Frame(self.root, bg=_BG)
        frame.pack(fill="both", expand=True)
        tk.Label(
            frame,
            text="oculto-scan",
            bg=_BG,
            fg=_INK,
            font=("Segoe UI", 20, "bold"),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(16, 0))
        tk.Label(
            frame,
            text="Verifica se a planilha pode vazar dados antes de você enviar.",
            bg=_BG,
            fg=_MUTED,
            font=("Segoe UI", 11),
            anchor="w",
        ).pack(fill="x", padx=16)
        modes = tk.Frame(frame, bg=_BG)
        modes.pack(fill="x", **pad)
        ttk.Radiobutton(modes, text="Um arquivo", value="scan", variable=self._mode, command=self._apply_mode).pack(
            side="left"
        )
        ttk.Radiobutton(
            modes,
            text="Comparar dois arquivos",
            value="diff",
            variable=self._mode,
            command=self._apply_mode,
        ).pack(side="left", padx=12)

        self._files = tk.Frame(frame, bg=_BG)
        self._files.pack(fill="x")
        self._left_row = self._file_row(self._files, "Arquivo", self._left)
        self._right_row = self._file_row(self._files, "Outro arquivo", self._right)
        ttk.Checkbutton(
            frame,
            text="Mostrar os valores reais (não envie o relatório a outras pessoas)",
            variable=self._show,
            command=self._refresh,
        ).pack(anchor="w", padx=16, pady=8)
        actions = tk.Frame(frame, bg=_BG)
        actions.pack(fill="x", padx=16, pady=4)
        self._go = ttk.Button(actions, text="Escanear", command=self._run)
        self._go.pack(side="left")
        self._summary = tk.Label(actions, text="", bg=_BG, fg=_INK, font=("Segoe UI", 11, "bold"))
        self._summary.pack(side="left", padx=12)
        self._text = tk.Text(
            frame,
            height=16,
            wrap="word",
            bg=_CARD,
            fg=_INK,
            font=("Segoe UI", 11),
            relief="flat",
            padx=10,
            pady=8,
        )
        self._text.pack(fill="both", expand=True, padx=16, pady=8)
        self._text.tag_configure("alto", foreground=_ALTO)
        self._text.tag_configure("médio", foreground=_MEDIO)
        self._text.tag_configure("info", foreground=_INFO)
        self._text.configure(state="disabled")
        buttons = tk.Frame(frame, bg=_BG)
        buttons.pack(fill="x", padx=16, pady=(0, 4))
        ttk.Button(buttons, text="Salvar relatório HTML", command=self._save).pack(side="left")
        ttk.Button(buttons, text="Abrir relatório HTML", command=self._open).pack(side="left", padx=8)
        tk.Label(frame, textvariable=self._status, bg=_BG, fg=_MUTED, font=("Segoe UI", 9), anchor="w").pack(
            fill="x", padx=16, pady=(0, 12)
        )

    def _file_row(self, parent: tk.Misc, label: str, variable: tk.StringVar) -> tk.Frame:
        row = tk.Frame(parent, bg=_BG)
        tk.Label(row, text=label, width=14, anchor="w", bg=_BG, fg=_INK, font=("Segoe UI", 10)).pack(side="left")
        entry = ttk.Entry(row, textvariable=variable)
        entry.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row, text="Escolher...", command=lambda: self._pick(variable)).pack(side="left")
        return row

    def _pick(self, variable: tk.StringVar) -> None:
        chosen = filedialog.askopenfilename(
            title="Escolher planilha",
            filetypes=[("Planilhas Excel", "*.xlsx *.xlsm"), ("Todos os arquivos", "*.*")],
        )
        if chosen:
            variable.set(chosen)

    def _apply_mode(self) -> None:
        self._left_row.pack(fill="x", padx=16, pady=2)
        if self._mode.get() == "diff":
            self._right_row.pack(fill="x", padx=16, pady=2)
            self._go.configure(text="Comparar")
        else:
            self._right_row.pack_forget()
            self._go.configure(text="Escanear")

    def _run(self) -> None:
        self.saved = None
        try:
            if self._mode.get() == "diff":
                self.session = compare_files(Path(self._left.get()), Path(self._right.get()))
            else:
                self.session = scan_file(Path(self._left.get()))
        except OSError as exc:
            self.session = Session(error=f"Não foi possível ler o arquivo ({exc}).")
        self._refresh()

    def _refresh(self) -> None:
        show = bool(self._show.get())
        text = result_text(self.session, show=show) if self.session.mode or self.session.error else ""
        self._summary.configure(text=summary_line(self.session) if self.session.mode or self.session.error else "")
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        if text:
            self._insert_colored(text)
        self._text.configure(state="disabled")

    def _insert_colored(self, text: str) -> None:
        for line in text.splitlines(keepends=True):
            tag = ""
            for name in ("alto", "médio", "info"):
                if line.startswith(name + " "):
                    tag = name
            self._text.insert("end", line, tag)

    def _html(self) -> str:
        if not self.session.ready:
            return ""
        return result_html(self.session, show=bool(self._show.get()))

    def _save(self) -> None:
        html = self._html()
        if not html:
            messagebox.showinfo("oculto-scan", "Escaneie um arquivo antes de salvar o relatório.")
            return
        name = suggested_html_name(show=bool(self._show.get()), mode=self.session.mode)
        chosen = filedialog.asksaveasfilename(
            title="Salvar relatório",
            defaultextension=".html",
            initialfile=name,
            filetypes=[("Página HTML", "*.html")],
        )
        if not chosen:
            return
        path = Path(chosen)
        write_private_text(path, html)
        self.saved = path
        self._status.set(f"Relatório salvo em {path}. Nada foi enviado para a internet.")

    def _open(self) -> None:
        html = self._html()
        if not html:
            messagebox.showinfo("oculto-scan", "Escaneie um arquivo antes de abrir o relatório.")
            return
        path = self.saved
        if path is None or not path.is_file():
            handle = tempfile.NamedTemporaryFile(prefix="oculto-scan-", suffix=".html", delete=False)
            handle.close()
            path = Path(handle.name)
            write_private_text(path, html)
            self.saved = path
            self._status.set("Relatório aberto de um arquivo temporário. Use Salvar para guardar uma cópia.")
        open_document(path)


def run() -> None:
    hide_console_window()
    root = tk.Tk()
    App(root)
    root.mainloop()

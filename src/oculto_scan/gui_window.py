"""Tk window. Widgets only: the scan itself lives in gui_logic.

The report text is still ``result_text``. This module only changes layout and color.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, ttk

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
    icon_paths,
    open_contact_mail,
    open_download_page,
    update_help_text,
)
from oculto_scan.gui_logic import (
    ACHADOS,
    ERRO,
    LIMPO,
    Session,
    card_counts,
    compare_files,
    result_html,
    result_text,
    scan_file,
    suggested_html_name,
    summary_line,
    type_counts,
    view_state,
)
from oculto_scan.gui_theme import (
    ALTO,
    AMBER,
    AMBER_HOT,
    CARD,
    CARD_RAISED,
    CREAM,
    ERROR_BG,
    INFO,
    INK,
    LINE,
    MEDIO,
    MONO_FONTS,
    MUTED,
    NAVY,
    NAVY_DEEP,
    OK,
    OK_BG,
    PANEL,
    UI_FONTS,
)
from oculto_scan.report import write_private_text

_PLACEHOLDER = "O relatório aparece aqui, com os mesmos textos de sempre."
_BUSY = "Analisando a planilha neste computador."
_OFFLINE = "Nada é enviado para a internet. O arquivo fica neste computador."
_SHOW = "Mostrar os valores reais (não envie o relatório a outras pessoas)"
_EMPTY_FILE = "Nenhum arquivo escolhido"
_FILE_HINT = ".xlsx ou .xlsm · o arquivo fica neste computador"


def _first_font(root: tk.Misc, names: tuple[str, ...]) -> str:
    families = set(tkfont.families(root))
    for name in names:
        if name in families:
            return name
    return "TkDefaultFont"


def apply_window_icon(root: tk.Tk) -> tk.PhotoImage | None:
    """Set the window icon. A missing file keeps the usual Tk icon."""
    png, ico = icon_paths()
    image = None
    if png.is_file():
        try:
            image = tk.PhotoImage(file=str(png))
            root.iconphoto(True, image)
        except tk.TclError:
            image = None
    if sys.platform == "win32" and ico.is_file():
        try:
            root.iconbitmap(default=str(ico))
        except tk.TclError:
            pass
    return image


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
        self._busy = False
        root.title(f"oculto-scan {__version__}")
        root.configure(bg=NAVY)
        root.minsize(880, 640)
        root.geometry("1080x780")
        self._ui = _first_font(root, UI_FONTS)
        self._mono = _first_font(root, MONO_FONTS)
        self._icon_image = apply_window_icon(root)
        self._header_icon = self._scaled_icon()
        self._mode = tk.StringVar(value="scan")
        self._left = tk.StringVar()
        self._right = tk.StringVar()
        self._show = tk.BooleanVar(value=False)
        self._status = tk.StringVar(value=_OFFLINE)
        self._apply_theme()
        self._build_menu()
        self._build()
        self._apply_mode()
        self._refresh()

    def _scaled_icon(self) -> tk.PhotoImage | None:
        png, _ico = icon_paths()
        if not png.is_file():
            return None
        try:
            image = tk.PhotoImage(file=str(png))
        except tk.TclError:
            return None
        factor = max(1, image.width() // 56)
        if factor > 1:
            image = image.subsample(factor, factor)
        return image

    def _apply_theme(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        ui = (self._ui, 12)
        style.configure(".", background=NAVY, foreground=CREAM, font=ui)
        style.configure("TButton", background=CARD, foreground=CREAM, bordercolor=LINE, padding=(14, 8), font=ui)
        style.map(
            "TButton",
            background=[("active", CARD_RAISED), ("pressed", CARD_RAISED), ("disabled", PANEL)],
            foreground=[("disabled", MUTED)],
        )
        style.configure(
            "Accent.TButton",
            background=AMBER,
            foreground=INK,
            bordercolor=AMBER,
            padding=(18, 10),
            font=(self._ui, 13, "bold"),
        )
        style.map(
            "Accent.TButton",
            background=[("active", AMBER_HOT), ("pressed", AMBER_HOT), ("disabled", PANEL)],
            foreground=[("disabled", MUTED), ("!disabled", INK)],
        )
        style.configure("TRadiobutton", background=NAVY, foreground=CREAM, font=ui)
        style.map(
            "TRadiobutton",
            background=[("active", NAVY), ("selected", NAVY)],
            foreground=[("selected", AMBER_HOT)],
            indicatorcolor=[("selected", AMBER), ("!selected", CARD)],
        )
        style.configure("TCheckbutton", background=NAVY, foreground=CREAM, font=ui)
        style.map(
            "TCheckbutton",
            background=[("active", NAVY)],
            indicatorcolor=[("selected", AMBER), ("!selected", CARD)],
        )
        style.configure(
            "Amber.Horizontal.TProgressbar",
            troughcolor=PANEL,
            background=AMBER,
            bordercolor=PANEL,
            lightcolor=AMBER,
            darkcolor=AMBER,
        )
        style.configure(
            "Vertical.TScrollbar",
            background=PANEL,
            troughcolor=NAVY,
            bordercolor=NAVY,
            arrowcolor=CREAM,
        )

    def _build_menu(self) -> None:
        menu = tk.Menu(
            self.root,
            bg=PANEL,
            fg=CREAM,
            activebackground=AMBER,
            activeforeground=INK,
            font=(self._ui, 12),
            bd=0,
            relief="flat",
        )
        help_menu = tk.Menu(
            menu,
            tearoff=0,
            bg=PANEL,
            fg=CREAM,
            activebackground=AMBER,
            activeforeground=INK,
            font=(self._ui, 12),
        )
        help_menu.add_command(label=MENU_UPDATE, command=self._show_update_help)
        help_menu.add_command(label=MENU_DOWNLOAD, command=open_download_page)
        help_menu.add_command(label=MENU_CONTACT, command=self._show_contact)
        help_menu.add_command(label=MENU_ABOUT, command=self._show_about)
        menu.add_cascade(label=MENU_HELP, menu=help_menu)
        self.root.config(menu=menu)

    def _show_update_help(self) -> None:
        self._dialog(MENU_UPDATE, update_help_text())

    def _show_about(self) -> None:
        self._dialog(MENU_ABOUT, about_text(__version__))

    def _show_contact(self) -> None:
        self._dialog(MENU_CONTACT, contact_text(), mail=True)

    def _dialog(self, title: str, body: str, *, mail: bool = False) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.configure(bg=NAVY)
        dialog.minsize(460, 220)
        dialog.geometry("560x420")
        text = tk.Text(
            dialog,
            wrap="word",
            bg=CARD,
            fg=CREAM,
            font=(self._ui, 12),
            relief="flat",
            padx=14,
            pady=12,
            highlightthickness=0,
        )
        text.insert("1.0", body)
        text.configure(state="disabled")
        text.pack(fill="both", expand=True, padx=16, pady=(16, 8))
        buttons = tk.Frame(dialog, bg=NAVY)
        buttons.pack(padx=16, pady=(0, 16))
        if mail:
            ttk.Button(buttons, text="Escrever e-mail", command=open_contact_mail).pack(side="left")
        ttk.Button(buttons, text="Fechar", command=dialog.destroy).pack(side="left", padx=(8, 0))

    def _build(self) -> None:
        header = tk.Frame(self.root, bg=NAVY_DEEP)
        header.pack(fill="x")
        if self._header_icon is not None:
            tk.Label(header, image=self._header_icon, bg=NAVY_DEEP).pack(side="left", padx=(18, 10), pady=14)
        titles = tk.Frame(header, bg=NAVY_DEEP)
        titles.pack(side="left", fill="x", expand=True, pady=14)
        tk.Label(
            titles,
            text="oculto-scan",
            bg=NAVY_DEEP,
            fg=CREAM,
            font=(self._ui, 22, "bold"),
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            titles,
            text=f"versão {__version__}",
            bg=NAVY_DEEP,
            fg=MUTED,
            font=(self._ui, 12),
            anchor="w",
        ).pack(anchor="w")
        badge = tk.Label(
            header,
            text="  100% offline  ",
            bg=NAVY,
            fg=AMBER_HOT,
            font=(self._ui, 12, "bold"),
            highlightthickness=1,
            highlightbackground=AMBER,
        )
        badge.pack(side="right", padx=18, pady=18)
        tk.Frame(self.root, bg=AMBER, height=2).pack(fill="x")

        body = tk.Frame(self.root, bg=NAVY)
        body.pack(fill="both", expand=True)
        tk.Label(
            body,
            text="Verifica se a planilha pode vazar dados antes de você enviar.",
            bg=NAVY,
            fg=MUTED,
            font=(self._ui, 12),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(12, 4))

        modes = tk.Frame(body, bg=NAVY)
        modes.pack(fill="x", padx=20, pady=4)
        ttk.Radiobutton(modes, text="Um arquivo", value="scan", variable=self._mode, command=self._apply_mode).pack(
            side="left"
        )
        ttk.Radiobutton(
            modes,
            text="Comparar dois arquivos",
            value="diff",
            variable=self._mode,
            command=self._apply_mode,
        ).pack(side="left", padx=16)

        self._files = tk.Frame(body, bg=NAVY)
        self._files.pack(fill="x", padx=20, pady=6)
        self._files.grid_columnconfigure(0, weight=1)
        self._files.grid_columnconfigure(1, weight=1)
        self._left_zone, self._left_name = self._zone(self._files, "Arquivo", self._left)
        self._right_zone, self._right_name = self._zone(self._files, "Outro arquivo", self._right)

        ttk.Checkbutton(body, text=_SHOW, variable=self._show, command=self._refresh).pack(anchor="w", padx=20, pady=8)

        actions = tk.Frame(body, bg=NAVY)
        actions.pack(fill="x", padx=20, pady=4)
        self._go = ttk.Button(actions, text="Escanear", style="Accent.TButton", command=self._run)
        self._go.pack(side="left")
        ttk.Button(actions, text="Salvar relatório HTML", command=self._save).pack(side="left", padx=8)
        ttk.Button(actions, text="Abrir relatório HTML", command=self._open).pack(side="left")

        tk.Label(body, textvariable=self._status, bg=NAVY, fg=MUTED, font=(self._ui, 11), anchor="w").pack(
            fill="x", padx=20, pady=(6, 2)
        )

        self._results = tk.Frame(body, bg=NAVY)
        self._results.pack(fill="x")
        self._banner = tk.Frame(self._results, bg=PANEL)
        self._banner_accent = tk.Frame(self._banner, bg=AMBER, width=4)
        self._banner_accent.pack(side="left", fill="y")
        self._banner_text = tk.Label(
            self._banner,
            text="",
            bg=PANEL,
            fg=CREAM,
            font=(self._ui, 13, "bold"),
            anchor="w",
            justify="left",
            wraplength=860,
        )
        self._banner_text.pack(side="left", fill="x", expand=True, padx=12, pady=10)
        self._progress = ttk.Progressbar(self._results, mode="indeterminate", style="Amber.Horizontal.TProgressbar")
        self._cards = tk.Frame(self._results, bg=NAVY)
        self._chips = tk.Frame(self._results, bg=NAVY)
        self._summary = tk.Label(
            self._results, text="", bg=NAVY, fg=CREAM, font=(self._ui, 12), anchor="w", justify="left"
        )
        self._banner_on = False

        report_head = tk.Frame(body, bg=NAVY)
        report_head.pack(fill="x", padx=20, pady=(10, 0))
        tk.Label(report_head, text="Relatório", bg=NAVY, fg=MUTED, font=(self._ui, 11), anchor="w").pack(side="left")

        report = tk.Frame(body, bg=NAVY)
        report.pack(fill="both", expand=True, padx=20, pady=(4, 16))
        self._text = tk.Text(
            report,
            wrap="word",
            bg=CARD,
            fg=CREAM,
            font=(self._mono, 12),
            relief="flat",
            padx=12,
            pady=10,
            highlightthickness=1,
            highlightbackground=LINE,
            insertbackground=CREAM,
        )
        scroll = ttk.Scrollbar(report, command=self._text.yview)
        self._text.configure(yscrollcommand=scroll.set)
        self._text.tag_configure("alto", foreground=ALTO)
        self._text.tag_configure("médio", foreground=MEDIO)
        self._text.tag_configure("info", foreground=INFO)
        self._text.tag_configure("placeholder", foreground=MUTED)
        self._text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self._text.configure(state="disabled")

    def _zone(self, parent: tk.Misc, caption: str, variable: tk.StringVar) -> tuple[tk.Frame, tk.Label]:
        zone = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=AMBER, cursor="hand2")
        tk.Label(zone, text=caption.upper(), bg=CARD, fg=MUTED, font=(self._ui, 10)).pack(pady=(16, 2))
        ttk.Button(zone, text="Escolher...", command=lambda: self._pick(variable)).pack(pady=4)
        name = tk.Label(zone, text=_EMPTY_FILE, bg=CARD, fg=MUTED, font=(self._ui, 12, "bold"), wraplength=420)
        name.pack(pady=(6, 0))
        tk.Label(zone, text=_FILE_HINT, bg=CARD, fg=MUTED, font=(self._ui, 11)).pack(pady=(2, 16))

        def choose(_event: tk.Event | None = None) -> None:
            self._pick(variable)

        zone.bind("<Button-1>", choose)
        for child in zone.winfo_children():
            if not isinstance(child, ttk.Button):
                child.bind("<Button-1>", choose)
        variable.trace_add("write", lambda *_args: self._paint_name(name, variable))
        return zone, name

    def _paint_name(self, label: tk.Label, variable: tk.StringVar) -> None:
        raw = variable.get().strip()
        if not raw:
            label.configure(text=_EMPTY_FILE, fg=MUTED)
            return
        path = Path(raw)
        label.configure(text=path.name, fg=CREAM)

    def _pick(self, variable: tk.StringVar) -> None:
        chosen = filedialog.askopenfilename(
            title="Escolher planilha",
            filetypes=[("Planilhas Excel", "*.xlsx *.xlsm"), ("Todos os arquivos", "*.*")],
        )
        if chosen:
            variable.set(chosen)

    def _apply_mode(self) -> None:
        scanning = self._mode.get() != "diff"
        span = 2 if scanning else 1
        pad = 0 if scanning else 6
        self._left_zone.grid(row=0, column=0, columnspan=span, sticky="nsew", padx=(0, pad))
        if scanning:
            self._right_zone.grid_remove()
            self._go.configure(text="Escanear")
        else:
            self._right_zone.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
            self._go.configure(text="Comparar")

    def _run(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.saved = None
        self._go.state(["disabled"])
        self._status.set(_BUSY)
        self._show_banner("analisando", _BUSY)
        self._layout_results()
        self._progress.start(12)
        self.root.update_idletasks()
        self.root.after(40, self._finish_run)

    def _finish_run(self) -> None:
        try:
            if self._mode.get() == "diff":
                self.session = compare_files(Path(self._left.get()), Path(self._right.get()))
            else:
                self.session = scan_file(Path(self._left.get()))
        except OSError as exc:
            self.session = Session(error=f"Não foi possível ler o arquivo ({exc}).")
        finally:
            self._progress.stop()
            self._progress.pack_forget()
            self._busy = False
            self._go.state(["!disabled"])
            self._apply_mode()
            self._status.set(_OFFLINE)
            self._refresh()

    def _show_banner(self, kind: str, text: str) -> None:
        colors = {
            "analisando": (PANEL, AMBER),
            "limpo": (OK_BG, OK),
            "erro": (ERROR_BG, ALTO),
        }
        background, accent = colors.get(kind, (PANEL, AMBER))
        self._banner.configure(bg=background)
        self._banner_accent.configure(bg=accent)
        self._banner_text.configure(bg=background, fg=CREAM, text=text)
        self._banner_on = True

    def _hide_banner(self) -> None:
        self._banner_on = False

    def _layout_results(self) -> None:
        for widget in (self._banner, self._progress, self._cards, self._chips, self._summary):
            if widget.winfo_ismapped():
                widget.pack_forget()
        if self._banner_on:
            self._banner.pack(fill="x", padx=20, pady=(8, 0))
        if self._busy:
            self._progress.pack(fill="x", padx=20, pady=(4, 0))
        if self._cards.winfo_children():
            self._cards.pack(fill="x", padx=16, pady=(10, 0))
        if self._chips.winfo_children():
            self._chips.pack(fill="x", padx=20, pady=(8, 0))
        if str(self._summary.cget("text")):
            self._summary.pack(fill="x", padx=20, pady=(8, 0))

    def _refresh(self) -> None:
        if self._busy:
            return
        state = view_state(self.session)
        if state == ERRO:
            self._show_banner("erro", self.session.error)
        elif state == LIMPO:
            self._show_banner("limpo", "Nenhum achado.")
        else:
            self._hide_banner()
        self._fill_cards(card_counts(self.session))
        self._fill_chips(type_counts(self.session) if state == ACHADOS else [])
        summary = summary_line(self.session) if self.session.mode or self.session.error else ""
        self._summary.configure(text=summary)
        self._layout_results()
        show = bool(self._show.get())
        text = result_text(self.session, show=show) if self.session.mode or self.session.error else ""
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        if text:
            self._insert_colored(text)
        else:
            self._text.insert("end", _PLACEHOLDER, "placeholder")
        self._text.configure(state="disabled")

    def _fill_cards(self, cards: list[tuple[str, str, int]]) -> None:
        for child in self._cards.winfo_children():
            child.destroy()
        if not cards:
            return
        tones = {
            "alto": ALTO,
            "medio": MEDIO,
            "info": INFO,
            "conteudo": ALTO,
            "estrutura": MEDIO,
            "metadado": INFO,
            "total": CREAM,
        }
        for key, label, count in cards:
            color = tones.get(key, CREAM)
            card = tk.Frame(self._cards, bg=CARD)
            tk.Frame(card, bg=color, width=4).pack(side="left", fill="y")
            inner = tk.Frame(card, bg=CARD)
            inner.pack(side="left", fill="both", expand=True, padx=12, pady=8)
            tk.Label(inner, text=str(count), bg=CARD, fg=color, font=(self._ui, 20, "bold")).pack(anchor="w")
            tk.Label(inner, text=label, bg=CARD, fg=MUTED, font=(self._ui, 12)).pack(anchor="w")
            card.pack(side="left", fill="x", expand=True, padx=4)

    def _fill_chips(self, chips: list[tuple[str, int]]) -> None:
        for child in self._chips.winfo_children():
            child.destroy()
        if not chips:
            return
        for label, count in chips:
            tk.Label(
                self._chips,
                text=f"  {label}  {count}  ",
                bg=CARD_RAISED,
                fg=CREAM,
                font=(self._ui, 11),
                padx=4,
                pady=3,
            ).pack(side="left", padx=4, pady=2)

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

    def _notice(self, text: str) -> None:
        self._dialog("oculto-scan", text)

    def _save(self) -> None:
        html = self._html()
        if not html:
            self._notice("Escaneie um arquivo antes de salvar o relatório.")
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
            self._notice("Escaneie um arquivo antes de abrir o relatório.")
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

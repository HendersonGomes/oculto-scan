"""Tk window. Widgets only: the scan itself lives in gui_logic.

The in-window report is a gauge plus short cards. The long text stays in
``result_html`` (and in ``result_text`` for the terminal).
"""

from __future__ import annotations

import math
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
    Session,
    compare_files,
    result_html,
    risk_grade,
    scan_file,
    suggested_html_name,
    window_cards,
)
from oculto_scan.gui_theme import (
    AMBER,
    AMBER_HOT,
    GAUGE_ALTO,
    GAUGE_ALTO_TEXT,
    GAUGE_BG,
    GAUGE_CARD,
    GAUGE_CREAM,
    GAUGE_INFO,
    GAUGE_INK,
    GAUGE_LINE,
    GAUGE_MEDIO,
    GAUGE_MUTED,
    GAUGE_TRACK,
    OK,
    UI_FONTS,
)
from oculto_scan.report import write_private_text

_BUSY = "Analisando a planilha neste computador."
_OFFLINE = "Nada é enviado para a internet. O arquivo fica neste computador."
_SHOW = "Mostrar os valores reais (não envie o relatório a outras pessoas)"
_EMPTY_FILE = "Nenhum arquivo escolhido"
_FILE_HINT = "Escolha um .xlsx ou .xlsm"
_FILE_READY = "Escolha outro arquivo quando quiser"
_LEAD = "A nota segue o pior achado e a quantidade. Não é uma porcentagem."
_INVITE = "Escolha um arquivo para ver os achados aqui, em linguagem simples."
_CLEAN = "Nenhum achado. O texto completo continua no relatório HTML."

_WORD = {
    "limpo": "Limpo",
    "baixo": "Baixo",
    "medio": "Médio",
    "alto": "Alto",
    "erro": "Erro",
    "analisando": "Aguarde",
}
_WORD_COLOR = {
    "limpo": OK,
    "baixo": GAUGE_INFO,
    "medio": GAUGE_MEDIO,
    "alto": GAUGE_ALTO_TEXT,
    "erro": GAUGE_ALTO_TEXT,
    "analisando": GAUGE_MUTED,
    "": GAUGE_MUTED,
}
_NEEDLE = {"limpo": 168, "baixo": 150, "medio": 90, "alto": 22}
_CARD_COLOR = {"alto": GAUGE_ALTO, "medio": GAUGE_MEDIO, "info": GAUGE_INFO}


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
        self._meter = ("", "Escolha um arquivo", "")
        root.title(f"oculto-scan {__version__}")
        root.configure(bg=GAUGE_BG)
        root.minsize(960, 680)
        root.geometry("1180x820")
        self._ui = _first_font(root, UI_FONTS)
        self._icon_image = apply_window_icon(root)
        self._mark = self._scaled_icon()
        self._mode = tk.StringVar(value="scan")
        self._left = tk.StringVar()
        self._right = tk.StringVar()
        self._show = tk.BooleanVar(value=False)
        self._status = tk.StringVar(value=_OFFLINE)
        self._title = tk.StringVar(value="Risco da planilha")
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
        factor = max(1, image.width() // 36)
        if factor > 1:
            image = image.subsample(factor, factor)
        return image

    def _apply_theme(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        ui = (self._ui, 12)
        style.configure(".", background=GAUGE_BG, foreground=GAUGE_CREAM, font=ui)
        style.configure(
            "TButton",
            background=GAUGE_CARD,
            foreground=GAUGE_CREAM,
            bordercolor=GAUGE_LINE,
            padding=(14, 8),
            font=ui,
        )
        style.map(
            "TButton",
            background=[("active", GAUGE_TRACK), ("pressed", GAUGE_TRACK), ("disabled", GAUGE_BG)],
            foreground=[("disabled", GAUGE_MUTED)],
        )
        style.configure(
            "Accent.TButton",
            background=AMBER,
            foreground=GAUGE_INK,
            bordercolor=AMBER,
            padding=(16, 10),
            font=(self._ui, 12, "bold"),
        )
        style.map(
            "Accent.TButton",
            background=[("active", AMBER_HOT), ("pressed", AMBER_HOT), ("disabled", GAUGE_TRACK)],
            foreground=[("disabled", GAUGE_MUTED), ("!disabled", GAUGE_INK)],
        )
        style.configure("TRadiobutton", background=GAUGE_BG, foreground=GAUGE_CREAM, font=ui)
        style.map(
            "TRadiobutton",
            background=[("active", GAUGE_BG), ("selected", GAUGE_BG)],
            foreground=[("selected", AMBER_HOT)],
            indicatorcolor=[("selected", AMBER), ("!selected", GAUGE_CARD)],
        )
        style.configure("TCheckbutton", background=GAUGE_BG, foreground=GAUGE_CREAM, font=ui)
        style.map(
            "TCheckbutton",
            background=[("active", GAUGE_BG)],
            indicatorcolor=[("selected", AMBER), ("!selected", GAUGE_CARD)],
        )
        style.configure(
            "Amber.Horizontal.TProgressbar",
            troughcolor=GAUGE_TRACK,
            background=AMBER,
            bordercolor=GAUGE_TRACK,
            lightcolor=AMBER,
            darkcolor=AMBER,
        )
        style.configure(
            "Vertical.TScrollbar",
            background=GAUGE_LINE,
            troughcolor=GAUGE_BG,
            bordercolor=GAUGE_BG,
            arrowcolor=GAUGE_CREAM,
        )

    def _build_menu(self) -> None:
        menu = tk.Menu(
            self.root,
            bg=GAUGE_CARD,
            fg=GAUGE_CREAM,
            activebackground=AMBER,
            activeforeground=GAUGE_INK,
            font=(self._ui, 12),
            bd=0,
            relief="flat",
        )
        help_menu = tk.Menu(
            menu,
            tearoff=0,
            bg=GAUGE_CARD,
            fg=GAUGE_CREAM,
            activebackground=AMBER,
            activeforeground=GAUGE_INK,
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
        dialog.configure(bg=GAUGE_BG)
        dialog.minsize(460, 220)
        dialog.geometry("560x420")
        text = tk.Text(
            dialog,
            wrap="word",
            bg=GAUGE_CARD,
            fg=GAUGE_CREAM,
            font=(self._ui, 12),
            relief="flat",
            padx=14,
            pady=12,
            highlightthickness=0,
        )
        text.insert("1.0", body)
        text.configure(state="disabled")
        text.pack(fill="both", expand=True, padx=16, pady=(16, 8))
        buttons = tk.Frame(dialog, bg=GAUGE_BG)
        buttons.pack(padx=16, pady=(0, 16))
        if mail:
            ttk.Button(buttons, text="Escrever e-mail", command=open_contact_mail).pack(side="left")
        ttk.Button(buttons, text="Fechar", command=dialog.destroy).pack(side="left", padx=(8, 0))

    def _build(self) -> None:
        brand = tk.Frame(self.root, bg=GAUGE_BG)
        brand.pack(fill="x", padx=20, pady=(10, 0))
        if self._mark is not None:
            tk.Label(brand, image=self._mark, bg=GAUGE_BG).pack(side="left", padx=(0, 8))
        tk.Label(brand, text="oculto-scan", bg=GAUGE_BG, fg=GAUGE_CREAM, font=(self._ui, 16, "bold")).pack(
            side="left"
        )
        tk.Label(brand, text=f"  {__version__}", bg=GAUGE_BG, fg=GAUGE_MUTED, font=(self._ui, 12)).pack(side="left")
        tk.Label(brand, text="100% offline", bg=GAUGE_BG, fg=AMBER_HOT, font=(self._ui, 12, "bold")).pack(
            side="right"
        )

        top = tk.Frame(self.root, bg=GAUGE_BG)
        top.pack(fill="x", padx=12, pady=(4, 0))
        self._gauge = tk.Canvas(top, width=500, height=280, bg=GAUGE_BG, highlightthickness=0)
        self._gauge.pack(side="left", anchor="n")
        self._gauge.bind("<Configure>", lambda _event: self._draw_meter())

        side = tk.Frame(top, bg=GAUGE_BG)
        side.pack(side="left", fill="both", expand=True, padx=(8, 12), pady=(18, 0))
        tk.Label(
            side,
            textvariable=self._title,
            bg=GAUGE_BG,
            fg=GAUGE_CREAM,
            font=(self._ui, 26, "bold"),
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            side,
            text=_LEAD,
            bg=GAUGE_BG,
            fg=GAUGE_MUTED,
            font=(self._ui, 13),
            anchor="w",
            justify="left",
            wraplength=520,
        ).pack(anchor="w", pady=(4, 10))

        modes = tk.Frame(side, bg=GAUGE_BG)
        modes.pack(anchor="w", pady=(0, 8))
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

        self._files = tk.Frame(side, bg=GAUGE_BG)
        self._files.pack(fill="x")
        self._left_zone, self._left_name = self._bar(self._files, "Arquivo", self._left)
        self._right_zone, self._right_name = self._bar(self._files, "Outro arquivo", self._right)

        actions = tk.Frame(side, bg=GAUGE_BG)
        actions.pack(fill="x", pady=(10, 0))
        self._go = ttk.Button(actions, text="Escanear", style="Accent.TButton", command=self._run)
        self._go.pack(side="left")
        ttk.Button(actions, text="Salvar relatório HTML", command=self._save).pack(side="left", padx=8)
        ttk.Button(actions, text="Abrir relatório HTML", command=self._open).pack(side="left")

        ttk.Checkbutton(side, text=_SHOW, variable=self._show, command=self._refresh).pack(anchor="w", pady=(10, 0))
        tk.Label(side, textvariable=self._status, bg=GAUGE_BG, fg=GAUGE_MUTED, font=(self._ui, 11), anchor="w").pack(
            anchor="w", pady=(6, 0)
        )
        self._progress = ttk.Progressbar(side, mode="indeterminate", style="Amber.Horizontal.TProgressbar")

        board = tk.Frame(self.root, bg=GAUGE_BG)
        board.pack(fill="both", expand=True, padx=20, pady=(8, 16))
        self._scroll = ttk.Scrollbar(board, orient="vertical")
        self._cards_canvas = tk.Canvas(board, bg=GAUGE_BG, highlightthickness=0, yscrollcommand=self._scroll.set)
        self._scroll.configure(command=self._cards_canvas.yview)
        self._cards_canvas.pack(side="left", fill="both", expand=True)
        self._card_frame = tk.Frame(self._cards_canvas, bg=GAUGE_BG)
        self._cards_window = self._cards_canvas.create_window((0, 0), window=self._card_frame, anchor="nw")
        self._card_frame.bind("<Configure>", self._on_cards_configure)
        self._cards_canvas.bind("<Configure>", self._on_cards_configure)
        self._cards_canvas.bind("<Enter>", lambda _event: self._bind_wheel())
        self._cards_canvas.bind("<Leave>", lambda _event: self._unbind_wheel())

    def _bind_wheel(self) -> None:
        self.root.bind_all("<Button-4>", self._on_wheel)
        self.root.bind_all("<Button-5>", self._on_wheel)
        self.root.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self) -> None:
        self.root.unbind_all("<Button-4>")
        self.root.unbind_all("<Button-5>")
        self.root.unbind_all("<MouseWheel>")

    def _on_wheel(self, event: tk.Event) -> None:
        if getattr(event, "num", None) == 4:
            self._cards_canvas.yview_scroll(-3, "units")
        elif getattr(event, "num", None) == 5:
            self._cards_canvas.yview_scroll(3, "units")
        else:
            self._cards_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _on_cards_configure(self, _event: tk.Event | None = None) -> None:
        width = self._cards_canvas.winfo_width()
        if width > 1:
            self._cards_canvas.itemconfigure(self._cards_window, width=width)
        self._cards_canvas.configure(scrollregion=self._cards_canvas.bbox("all"))
        self._toggle_scrollbar()

    def _toggle_scrollbar(self) -> None:
        bbox = self._cards_canvas.bbox("all")
        height = self._cards_canvas.winfo_height()
        needed = bool(bbox and height > 1 and bbox[3] > height + 4)
        mapped = bool(self._scroll.winfo_ismapped())
        if needed and not mapped:
            self._scroll.pack(side="right", fill="y")
        elif mapped and not needed:
            self._scroll.pack_forget()

    def _bar(self, parent: tk.Misc, caption: str, variable: tk.StringVar) -> tuple[tk.Frame, tk.Label]:
        zone = tk.Frame(parent, bg=GAUGE_CARD, highlightthickness=1, highlightbackground=GAUGE_LINE)
        text = tk.Frame(zone, bg=GAUGE_CARD)
        text.pack(side="left", fill="both", expand=True, padx=14, pady=8)
        tk.Label(text, text=caption, bg=GAUGE_CARD, fg=GAUGE_MUTED, font=(self._ui, 10)).pack(anchor="w")
        name = tk.Label(text, text=_EMPTY_FILE, bg=GAUGE_CARD, fg=GAUGE_MUTED, font=(self._ui, 13, "bold"), anchor="w")
        name.pack(anchor="w")
        hint = tk.Label(text, text=_FILE_HINT, bg=GAUGE_CARD, fg=GAUGE_MUTED, font=(self._ui, 11), anchor="w")
        hint.pack(anchor="w")
        ttk.Button(zone, text="Escolher...", style="Accent.TButton", command=lambda: self._pick(variable)).pack(
            side="right", padx=10, pady=10
        )
        variable.trace_add("write", lambda *_args: self._paint_name(name, hint, variable))
        return zone, name

    def _paint_name(self, name: tk.Label, hint: tk.Label, variable: tk.StringVar) -> None:
        raw = variable.get().strip()
        if not raw:
            name.configure(text=_EMPTY_FILE, fg=GAUGE_MUTED)
            hint.configure(text=_FILE_HINT)
            return
        name.configure(text=Path(raw).name, fg=GAUGE_CREAM)
        hint.configure(text=_FILE_READY)

    def _pick(self, variable: tk.StringVar) -> None:
        chosen = filedialog.askopenfilename(
            title="Escolher planilha",
            filetypes=[("Planilhas Excel", "*.xlsx *.xlsm"), ("Todos os arquivos", "*.*")],
        )
        if chosen:
            variable.set(chosen)

    def _apply_mode(self) -> None:
        scanning = self._mode.get() != "diff"
        self._left_zone.pack_forget()
        self._right_zone.pack_forget()
        self._left_zone.pack(fill="x", pady=(0, 0 if scanning else 8))
        if scanning:
            self._go.configure(text="Escanear")
            self._title.set("Risco da planilha")
        else:
            self._right_zone.pack(fill="x")
            self._go.configure(text="Comparar")
            self._title.set("Risco da comparação")

    def _run(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.saved = None
        self._go.state(["disabled"])
        self._status.set(_BUSY)
        self._meter = ("analisando", "Aguarde", "")
        self._draw_meter()
        self._show_note(_BUSY)
        self._progress.pack(fill="x", pady=(6, 0))
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

    def _draw_meter(self) -> None:
        grade, detail = self._meter[0], self._meter[2]
        word = self._meter[1]
        canvas = self._gauge
        canvas.delete("all")
        width = max(canvas.winfo_width(), 500)
        height = max(canvas.winfo_height(), 280)
        radius = min(width * 0.40, height * 0.62)
        cx = width / 2
        cy = height * 0.70
        box = (cx - radius, cy - radius, cx + radius, cy + radius)
        stroke = 22
        if grade == "limpo":
            canvas.create_arc(*box, start=0, extent=180, style="arc", outline=GAUGE_TRACK, width=stroke)
            canvas.create_arc(*box, start=135, extent=45, style="arc", outline=OK, width=stroke)
        elif grade in _NEEDLE:
            canvas.create_arc(*box, start=120, extent=60, style="arc", outline=GAUGE_INFO, width=stroke)
            canvas.create_arc(*box, start=60, extent=60, style="arc", outline=GAUGE_MEDIO, width=stroke)
            canvas.create_arc(*box, start=0, extent=60, style="arc", outline=GAUGE_ALTO, width=stroke)
        else:
            canvas.create_arc(*box, start=0, extent=180, style="arc", outline=GAUGE_TRACK, width=stroke)
        if grade in _NEEDLE:
            angle = math.radians(_NEEDLE[grade])
            length = radius * 0.78
            canvas.create_line(
                cx,
                cy,
                cx + math.cos(angle) * length,
                cy - math.sin(angle) * length,
                fill=GAUGE_CREAM,
                width=5,
                capstyle="round",
            )
            canvas.create_oval(cx - 7, cy - 7, cx + 7, cy + 7, fill=GAUGE_CREAM, outline=GAUGE_CREAM)
        color = _WORD_COLOR.get(grade, GAUGE_MUTED)
        size = 16 if grade == "" else 32
        canvas.create_text(cx, cy - 62, text=word, fill=color, font=(self._ui, size, "bold"))
        if detail:
            canvas.create_text(cx, cy - 28, text=detail, fill=GAUGE_MUTED, font=(self._ui, 12))

    def _refresh(self) -> None:
        if self._busy:
            return
        grade, detail = risk_grade(self.session)
        word = _WORD.get(grade, "Escolha um arquivo")
        if grade == "":
            detail = ""
            word = "Escolha um arquivo"
        self._meter = (grade, word, detail)
        self._draw_meter()
        cards = window_cards(self.session, show=bool(self._show.get()))
        if cards:
            self._show_cards(cards)
        elif grade == "erro":
            self._show_note(self.session.error)
        elif grade == "limpo":
            self._show_note(_CLEAN)
        else:
            self._show_note(_INVITE)
        self.root.update_idletasks()
        self._on_cards_configure()

    def _clear_cards(self) -> None:
        for child in self._card_frame.winfo_children():
            child.destroy()

    def _show_note(self, text: str) -> None:
        self._clear_cards()
        tk.Label(
            self._card_frame,
            text=text,
            bg=GAUGE_BG,
            fg=GAUGE_MUTED,
            font=(self._ui, 13),
            anchor="w",
            justify="left",
            wraplength=760,
        ).pack(anchor="w", padx=8, pady=8)

    def _show_cards(self, cards) -> None:
        self._clear_cards()
        width = max(self._cards_canvas.winfo_width() - 36, 640)
        for card in cards:
            color = _CARD_COLOR.get(card.severity, GAUGE_INFO)
            block = tk.Frame(self._card_frame, bg=GAUGE_CARD, highlightthickness=1, highlightbackground=GAUGE_LINE)
            tk.Frame(block, bg=color, height=6).pack(fill="x")
            inner = tk.Frame(block, bg=GAUGE_CARD)
            inner.pack(fill="x", padx=14, pady=10)
            tk.Label(
                inner,
                text=card.severity_label,
                bg=GAUGE_CARD,
                fg=color if card.severity != "alto" else GAUGE_ALTO_TEXT,
                font=(self._ui, 11, "bold"),
                anchor="w",
            ).pack(anchor="w")
            tk.Label(
                inner,
                text=card.title,
                bg=GAUGE_CARD,
                fg=GAUGE_CREAM,
                font=(self._ui, 16, "bold"),
                anchor="w",
                justify="left",
                wraplength=width,
            ).pack(anchor="w", pady=(2, 0))
            tk.Label(
                inner,
                text=card.where,
                bg=GAUGE_CARD,
                fg=GAUGE_MUTED,
                font=(self._ui, 12),
                anchor="w",
            ).pack(anchor="w")
            tk.Label(
                inner,
                text=card.action,
                bg=GAUGE_CARD,
                fg=GAUGE_CREAM,
                font=(self._ui, 12),
                anchor="w",
                justify="left",
                wraplength=width,
            ).pack(anchor="w", pady=(6, 0))
            block.pack(fill="x", pady=5)

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

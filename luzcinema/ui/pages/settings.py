"""Página Ajustes: aparência, integração com o Windows, dados e sobre."""
from __future__ import annotations

from tkinter import ttk
import webbrowser

from ... import __version__
from ...windows import DATA_DIR, open_folder
from ..labels import GITHUB_URL, HOW_IT_WORKS, TINYTUYA_KEYS_URL
from ..widgets import ScrollPage, card, section_header


class SettingsPage(ScrollPage):
    def __init__(self, app, parent):
        super().__init__(parent, app.theme)
        self.app = app
        body = self.body
        ttk.Label(body, text="Ajustes", style="H1.TLabel").pack(anchor="w", pady=(0, 18))

        system = card(body)
        system.outer.pack(fill="x")
        section_header(system, "Windows", style_prefix="Card").pack(anchor="w")
        ttk.Checkbutton(system, text="Ao fechar a janela, continuar na bandeja (ao lado do relógio)",
                        variable=app.minimize_to_tray, style="Card.TCheckbutton").pack(anchor="w", pady=(10, 3))
        ttk.Checkbutton(system, text="Iniciar com o Windows (abre discretamente na bandeja)",
                        variable=app.start_with_windows, style="Card.TCheckbutton",
                        command=lambda: app.set_autostart(app.start_with_windows.get())).pack(anchor="w", pady=3)

        look = card(body)
        look.outer.pack(fill="x", pady=(16, 0))
        section_header(look, "Aparência", style_prefix="Card").pack(anchor="w")
        row = ttk.Frame(look, style="Card.TFrame")
        row.pack(anchor="w", pady=(10, 0))
        self.theme_buttons = {}
        for mode, label in (("dark", "🌙  Escuro"), ("light", "☀  Claro")):
            button = ttk.Button(row, text=label, command=lambda m=mode: self._set_theme(m))
            button.pack(side="left", padx=(0, 6))
            self.theme_buttons[mode] = button
        app.theme.bind(lambda t: [b.configure(style="ChipActive.TButton" if m == t["name"] else "Chip.TButton")
                                  for m, b in self.theme_buttons.items()])

        data = card(body)
        data.outer.pack(fill="x", pady=(16, 0))
        section_header(data, "Seus dados", (
            "Preferências e a sessão Tuya ficam na pasta “dados” ao lado do programa. Chaves locais e tokens "
            "são criptografados pelo Windows (DPAPI) e só abrem na sua conta deste PC."), style_prefix="Card").pack(anchor="w", fill="x")
        ttk.Button(data, text="Abrir pasta de dados", command=lambda: open_folder(DATA_DIR)).pack(anchor="w", pady=(12, 0))

        about = card(body)
        about.outer.pack(fill="x", pady=(16, 0))
        section_header(about, f"{app.edition.title}  ·  versão {__version__}", app.edition.subtitle,
                       style_prefix="Card").pack(anchor="w", fill="x")
        ttk.Label(about, text=HOW_IT_WORKS, style="CardMuted.TLabel", wraplength=620, justify="left").pack(anchor="w", pady=(12, 0))
        links = ttk.Frame(about, style="Card.TFrame")
        links.pack(anchor="w", pady=(12, 0))
        ttk.Button(links, text="Projeto no GitHub ↗", command=lambda: webbrowser.open(GITHUB_URL)).pack(side="left")
        ttk.Button(links, text="Como obter a chave local ↗",
                   command=lambda: webbrowser.open(TINYTUYA_KEYS_URL)).pack(side="left", padx=8)

    def _set_theme(self, mode):
        if mode != self.app.theme.mode:
            self.app.toggle_theme()

"""Página Cenários: ambientes prontos com um clique e cenários salvos pelo usuário."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..widgets import ScrollPage, Tile, card, section_header


class ScenesPage(ScrollPage):
    def __init__(self, app, parent):
        super().__init__(parent, app.theme)
        self.app = app
        body = self.body
        ttk.Label(body, text="Cenários", style="H1.TLabel").pack(anchor="w")
        ttk.Label(body, style="Muted.TLabel", wraplength=640, justify="left", text=(
            "Ambientes prontos com um clique. Com várias lâmpadas, cada zona recebe sua própria cor."
            if app.edition.multi else "Ambientes prontos com um clique.")).pack(anchor="w", pady=(2, 18))

        self.grid = ttk.Frame(body)
        self.grid.pack(fill="x")
        self.grid.columnconfigure(0, weight=1, uniform="s")
        self.grid.columnconfigure(1, weight=1, uniform="s")

        save = card(body)
        save.outer.pack(fill="x", pady=(18, 0))
        section_header(save, "Salvar meu cenário",
                       "Guarda a cor e o brilho escolhidos na página Cores como um cenário.",
                       style_prefix="Card").pack(anchor="w", fill="x")
        row = ttk.Frame(save, style="Card.TFrame")
        row.pack(fill="x", pady=(12, 0))
        self.name = ttk.Entry(row)
        self.name.pack(side="left", fill="x", expand=True)
        self.name.bind("<Return>", lambda _: self._save())
        ttk.Button(row, text="Salvar cenário", command=self._save).pack(side="left", padx=(8, 0))
        self.render()

    def render(self):
        for child in self.grid.winfo_children():
            child.destroy()
        for i, scenario in enumerate(self.app.scenarios):
            on_delete = (lambda s=scenario: (self.app.delete_scenario(s.id), self.render())) if scenario.is_custom else None
            Tile(self.grid, self.app.theme, scenario.name, scenario.description, scenario.preview_hex,
                 icon=scenario.icon, command=lambda s=scenario: self.app.activate_scenario(s),
                 on_delete=on_delete).grid(row=i // 2, column=i % 2, sticky="nsew", padx=4, pady=4)

    def _save(self):
        self.app.save_scenario(self.name.get().strip())
        self.name.delete(0, tk.END)
        self.render()

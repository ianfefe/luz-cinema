"""Página Cores: roda de cores, branco ajustável e presets."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ...core import rgb_to_hex
from ...presets import DEFAULT_PRESETS, preset_color_hex
from ..widgets import ColorWheel, ScrollPage, Slider, Swatch, Tile, card, section_header

WHEEL_SIZE = 210
ALL_LAMPS = "Todas as lâmpadas"


class ColorsPage(ScrollPage):
    def __init__(self, app, parent):
        super().__init__(parent, app.theme)
        self.app = app
        self._syncing = False
        body = self.body

        ttk.Label(body, text="Cores", style="H1.TLabel").pack(anchor="w")
        ttk.Label(body, text="Escolha uma cor ou um tom de branco e aplique direto do PC.",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 18))

        columns = ttk.Frame(body)
        columns.pack(fill="both", expand=True)
        columns.columnconfigure(0, weight=5, uniform="cols")
        columns.columnconfigure(1, weight=6, uniform="cols")

        # ---------------------------------------------------------- cor manual
        left = card(columns)
        left.outer.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        if app.edition.multi:
            ttk.Label(left, text="Aplicar em", style="CardMuted.TLabel").pack(anchor="w")
            self.target_combo = ttk.Combobox(left, state="readonly")
            self.target_combo.pack(fill="x", pady=(4, 14))
            self.target_combo.bind("<<ComboboxSelected>>", lambda _: self._on_target())
            self.on_devices_changed()

        modes = ttk.Frame(left, style="Card.TFrame")
        modes.pack(fill="x")
        self.mode_buttons = {
            "colour": ttk.Button(modes, text="🎨  Colorida", command=lambda: self._set_mode("colour")),
            "white": ttk.Button(modes, text="☀  Branca", command=lambda: self._set_mode("white")),
        }
        for i, button in enumerate(self.mode_buttons.values()):
            button.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 4, 0))
            modes.columnconfigure(i, weight=1)

        self.wheel_box = ttk.Frame(left, style="Card.TFrame")
        self.wheel_canvas = tk.Canvas(self.wheel_box, width=WHEEL_SIZE, height=WHEEL_SIZE, highlightthickness=0)
        self.wheel_canvas.pack(pady=14)
        app.theme.bind(lambda t: self.wheel_canvas.configure(bg=t["CARD"]))
        self.wheel = ColorWheel(self.wheel_canvas, WHEEL_SIZE, self._on_wheel)
        self.temp_box = ttk.Frame(left, style="Card.TFrame")
        Slider(self.temp_box, "Temperatura", app.manual_temp, 0, 100,
               lambda v: "Quente" if v < 34 else ("Neutra" if v < 67 else "Fria"),
               hint="Da luz amarelada de abajur (2700K) ao branco frio de escritório (6500K).").pack(fill="x", pady=(14, 6))
        self.mode_anchor = ttk.Frame(left, style="Card.TFrame")
        self.mode_anchor.pack(fill="x")
        Slider(left, "Brilho", app.manual_brightness, 1, 100, lambda v: f"{v:.0f}%").pack(fill="x", pady=(6, 10))

        result = ttk.Frame(left, style="Card.TFrame")
        result.pack(fill="x", pady=(4, 0))
        self.swatch = Swatch(result, app.theme, size=40)
        self.swatch.pack(side="left")
        self.swatch_label = ttk.Label(result, style="CardStrong.TLabel")
        self.swatch_label.pack(side="left", padx=12)

        buttons = ttk.Frame(left, style="Card.TFrame")
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text="Aplicar", style="Accent.TButton", command=app.apply_manual).pack(side="left")
        ttk.Button(buttons, text="⏻  Apagar", command=lambda: app.set_power(False, app.target_ids())).pack(side="left", padx=8)
        ttk.Checkbutton(left, text="Aplicar enquanto ajusto", variable=app.live_manual,
                        style="Card.TCheckbutton").pack(anchor="w", pady=(12, 0))

        save = ttk.Frame(left, style="Card.TFrame")
        save.pack(fill="x", pady=(14, 0))
        self.preset_name = ttk.Entry(save)
        self.preset_name.pack(side="left", fill="x", expand=True)
        self.preset_name.insert(0, "")
        self.preset_name.bind("<Return>", lambda _: self._save_preset())
        ttk.Button(save, text="Salvar cor", command=self._save_preset).pack(side="left", padx=(8, 0))
        ttk.Label(left, text="Dê um nome e salve para usar de novo (também aparece na bandeja).",
                  style="CardMuted.TLabel", wraplength=300, justify="left").pack(anchor="w", pady=(4, 0))

        # ---------------------------------------------------------- presets
        right = card(columns)
        right.outer.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        section_header(right, "Cores prontas", style_prefix="Card").pack(anchor="w")
        grid = ttk.Frame(right, style="Card.TFrame")
        grid.pack(fill="x", pady=(10, 0))
        for i, preset in enumerate(DEFAULT_PRESETS):
            Tile(grid, app.theme, preset["name"], color=preset["color_hex"],
                 command=lambda p=preset: app.apply_preset(p)).grid(row=i // 2, column=i % 2, sticky="ew", padx=3, pady=3)
        grid.columnconfigure(0, weight=1, uniform="p")
        grid.columnconfigure(1, weight=1, uniform="p")
        section_header(right, "Minhas cores", style_prefix="Card").pack(anchor="w", pady=(18, 0))
        self.custom_grid = ttk.Frame(right, style="Card.TFrame")
        self.custom_grid.pack(fill="x", pady=(10, 0))
        self._render_custom()

        for var in (app.manual_brightness, app.manual_temp):
            var.trace_add("write", lambda *_: self._changed())
        self.sync_from_app()

    # ------------------------------------------------------------------ interação
    def _set_mode(self, mode):
        self.app.manual_mode.set(mode)
        self._refresh_mode()
        self._changed()

    def _refresh_mode(self):
        white = self.app.manual_mode.get() == "white"
        self.wheel_box.pack_forget()
        self.temp_box.pack_forget()
        (self.temp_box if white else self.wheel_box).pack(fill="x", before=self.mode_anchor)
        self.mode_buttons["white"].configure(style="ChipActive.TButton" if white else "Chip.TButton")
        self.mode_buttons["colour"].configure(style="Chip.TButton" if white else "ChipActive.TButton")

    def _on_wheel(self, hue, sat):
        self.app.manual_hue, self.app.manual_sat = hue, sat
        if self.app.manual_mode.get() != "colour":
            self.app.manual_mode.set("colour")
            self._refresh_mode()
        self._changed()

    def _changed(self):
        rgb = self.app.manual_rgb()
        self.swatch.set(rgb_to_hex(rgb))
        mode = "Branco" if self.app.manual_mode.get() == "white" else rgb_to_hex(rgb).upper()
        self.swatch_label.configure(text=f"{mode}  ·  {self.app.manual_brightness.get():.0f}%")
        if not self._syncing:
            self.app.schedule_live_apply()

    def sync_from_app(self):
        """Reflete na tela a cor atual do app (ex.: depois de escolher um preset) sem reenviar."""
        self._syncing = True
        try:
            self.wheel.set_color_hsv(self.app.manual_hue, self.app.manual_sat)
            self._refresh_mode()
            self._changed()
        finally:
            self._syncing = False

    def _save_preset(self):
        self.app.save_preset(self.preset_name.get().strip())
        self.preset_name.delete(0, tk.END)
        self._render_custom()

    def _render_custom(self):
        for child in self.custom_grid.winfo_children():
            child.destroy()
        if not self.app.custom_presets:
            ttk.Label(self.custom_grid, text="Nenhuma cor salva ainda.", style="CardMuted.TLabel").grid(row=0, column=0, sticky="w")
            return
        for i, preset in enumerate(self.app.custom_presets):
            Tile(self.custom_grid, self.app.theme, preset.get("name", "Cor"), color=preset_color_hex(preset),
                 command=lambda p=preset: self.app.apply_preset(p),
                 on_delete=lambda idx=i: (self.app.delete_preset(idx), self._render_custom())
                 ).grid(row=i // 2, column=i % 2, sticky="ew", padx=3, pady=3)
        self.custom_grid.columnconfigure(0, weight=1, uniform="p")
        self.custom_grid.columnconfigure(1, weight=1, uniform="p")

    # ------------------------------------------------------------------ lâmpada alvo (Multi)
    def _target_options(self):
        return [(None, ALL_LAMPS)] + [(d.id, d.name) for d in self.app.controller.device_list()]

    def _on_target(self):
        options = self._target_options()
        index = self.target_combo.current()
        self.app.manual_target.set(options[index][0] or "" if 0 <= index < len(options) else "")
        self.app.schedule_save()

    def on_devices_changed(self):
        if not self.app.edition.multi:
            return
        options = self._target_options()
        self.target_combo.configure(values=[label for _, label in options])
        ids = [bid for bid, _ in options]
        current = self.app.manual_target.get() or None
        if current not in ids:
            current = None
            self.app.manual_target.set("")
        self.target_combo.current(ids.index(current))

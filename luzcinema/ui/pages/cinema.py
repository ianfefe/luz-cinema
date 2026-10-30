"""Página Cinema: prévia ao vivo, iniciar/parar, perfis prontos e ajustes finos."""
from __future__ import annotations

from tkinter import ttk

from ...presets import CINEMA_PROFILES
from ..labels import ZONE_LABELS
from ..widgets import ScreenPreview, ScrollPage, Slider, Swatch, card, section_header


def _percent(v):
    return f"{v:.0f}%"


def _smoothing(v):
    return "Instantânea" if v <= 0.01 else f"{v:.2f} s"


def _fps(v):
    return f"{1 / max(v, 0.01):.0f} quadros/s"


def _dark(v):
    return "Desligado" if v < 0.5 else f"{v:.0f}%"


class CinemaPage(ScrollPage):
    def __init__(self, app, parent):
        super().__init__(parent, app.theme)
        self.app = app
        multi = app.edition.multi
        body = self.body

        ttk.Label(body, text="Modo cinema", style="H1.TLabel").pack(anchor="w")
        ttk.Label(body, style="Muted.TLabel", text=(
            "Cada lâmpada acompanha a sua zona da tela em tempo real." if multi
            else "Sua lâmpada acompanha as cores da tela em tempo real.")).pack(anchor="w", pady=(2, 18))

        # Prévia + controles principais
        hero = card(body, padding=0)
        hero.outer.pack(fill="x")
        self.preview = ScreenPreview(hero, app.theme, show_zones=multi)
        self.preview.pack(fill="x")
        controls = ttk.Frame(hero, style="Card.TFrame", padding=(18, 4, 18, 18))
        controls.pack(fill="x")
        self.toggle_button = ttk.Button(controls, style="Big.Accent.TButton", command=app.toggle_cinema)
        self.toggle_button.pack(side="left")
        self.preview_button = ttk.Button(controls, text="Só prévia", command=lambda: app.start_cinema(preview=True))
        self.preview_button.pack(side="left", padx=(10, 0))
        monitor_box = ttk.Frame(controls, style="Card.TFrame")
        monitor_box.pack(side="right")
        ttk.Label(monitor_box, text="Tela", style="CardMuted.TLabel").pack(anchor="w")
        self.monitor_combo = ttk.Combobox(monitor_box, state="readonly", width=26, values=app.monitor_labels())
        self.monitor_combo.pack(anchor="w")
        if app.monitors:
            self.monitor_combo.current(app.monitor_index)
        self.monitor_combo.bind("<<ComboboxSelected>>", lambda _: app.set_monitor(self.monitor_combo.current()))

        self.lamps_row = None
        if multi:
            self.lamps_row = ttk.Frame(hero, style="Card.TFrame", padding=(18, 0, 18, 16))
            self.lamps_row.pack(fill="x")
            self.lamp_swatches: dict[str, Swatch] = {}
            self.on_devices_changed()

        # Perfis prontos
        profiles = card(body)
        profiles.outer.pack(fill="x", pady=(16, 0))
        section_header(profiles, "Perfis prontos", "Ajusta tudo de uma vez para o que você vai assistir ou jogar.",
                       style_prefix="Card").pack(anchor="w", fill="x")
        grid = ttk.Frame(profiles, style="Card.TFrame")
        grid.pack(fill="x", pady=(12, 0))
        self.profile_buttons = {}
        for i, profile in enumerate(CINEMA_PROFILES):
            button = ttk.Button(grid, text=profile["short_name"], style="Chip.TButton",
                                command=lambda p=profile: app.apply_profile(p))
            button.grid(row=i // 3, column=i % 3, sticky="ew", padx=3, pady=3)
            self.profile_buttons[profile["id"]] = button
        for col in range(3):
            grid.columnconfigure(col, weight=1)
        self.profile_hint = ttk.Label(profiles, style="CardMuted.TLabel", wraplength=600, justify="left")
        self.profile_hint.pack(anchor="w", pady=(8, 0))
        app.profile.trace_add("write", lambda *_: self._refresh_profile())
        self._refresh_profile()

        # Ajustes
        adjust = card(body)
        adjust.outer.pack(fill="x", pady=(16, 0))
        section_header(adjust, "Ajustes", "Mudanças valem na hora, inclusive durante o cinema, e são salvas sozinhas.",
                       style_prefix="Card").pack(anchor="w", fill="x", pady=(0, 10))
        v = app.vars
        Slider(adjust, "Brilho máximo", v["brightness"], 5, 100, _percent).pack(fill="x", pady=6)
        Slider(adjust, "Intensidade das cores", v["saturation"], 50, 250, _percent,
               hint="Acima de 100% deixa as cores mais vivas que na tela.").pack(fill="x", pady=6)
        Slider(adjust, "Foco na cor de destaque", v["standout"], 0, 100, _percent,
               hint="0% usa a média da tela; 100% persegue a cor que mais chama atenção.").pack(fill="x", pady=6)

        self.advanced = ttk.Frame(adjust, style="Card.TFrame")
        self.advanced_button = ttk.Button(adjust, style="Ghost.TButton", command=self._toggle_advanced)
        self.advanced_button.pack(anchor="w", pady=(6, 0))
        Slider(self.advanced, "Suavidade da transição", v["smoothing"], 0.0, 2.0, _smoothing, resolution=0.01,
               hint="Transições mais lentas evitam piscadas; instantânea é melhor para jogos.").pack(fill="x", pady=6)
        Slider(self.advanced, "Velocidade de captura", v["interval"], 0.03, 0.5, _fps, resolution=0.01,
               hint="Mais quadros por segundo = resposta mais rápida, porém mais uso de CPU e rede.").pack(fill="x", pady=6)
        Slider(self.advanced, "Ignorar faixas em cima e embaixo", v["crop"], 0, 30, _percent, resolution=1,
               hint="Remove barras pretas de filmes e legendas do cálculo.").pack(fill="x", pady=6)
        Slider(self.advanced, "Apagar em cenas escuras abaixo de", v["dark_percent"], 0, 15, _dark, resolution=0.5).pack(fill="x", pady=6)
        options = ttk.Frame(self.advanced, style="Card.TFrame")
        options.pack(fill="x", pady=(8, 0))
        for key, text in (("off_on_neutral", "Apagar em cenas cinzas ou preto e branco"),
                          ("flash_boost", "Clarão: explosões e flashes brancos acendem a 100%"),
                          ("light_mode", "Modo claro: páginas brancas viram luz branca (ótimo para navegar)")):
            ttk.Checkbutton(options, text=text, variable=v[key], style="Card.TCheckbutton").pack(anchor="w", pady=3)
        self._advanced_open = False
        self._toggle_advanced(initial=True)
        self.on_running_changed()

    def _toggle_advanced(self, initial=False):
        if not initial:
            self._advanced_open = not self._advanced_open
        if self._advanced_open:
            self.advanced.pack(fill="x", pady=(4, 0))
            self.advanced_button.configure(text="▴  Ocultar ajustes avançados")
        else:
            self.advanced.pack_forget()
            self.advanced_button.configure(text="▾  Mostrar ajustes avançados")

    def _refresh_profile(self):
        current = self.app.profile.get()
        for pid, button in self.profile_buttons.items():
            button.configure(style="ChipActive.TButton" if pid == current else "Chip.TButton")
        profile = next((p for p in CINEMA_PROFILES if p["id"] == current), None)
        self.profile_hint.configure(text=profile["description"] if profile else
                                    "Ajustes personalizados. Escolha um perfil para recomeçar de um ponto conhecido.")

    # ------------------------------------------------------------------ eventos do app
    def on_running_changed(self):
        app = self.app
        if app.running:
            self.toggle_button.configure(text="■  Parar", style="Big.Danger.TButton")
            self.preview_button.state(["disabled"])
            self.monitor_combo.state(["disabled"])
        else:
            self.toggle_button.configure(text="▶  Iniciar sincronização", style="Big.Accent.TButton")
            self.preview_button.state(["!disabled"])
            self.monitor_combo.state(["!disabled", "readonly"])

    def on_frame(self, colors, lamp_colors):
        self.preview.set_colors(colors or None)
        if self.lamps_row is not None:
            for bid, swatch in self.lamp_swatches.items():
                rgb = lamp_colors.get(bid)
                swatch.set("#%02x%02x%02x" % rgb if rgb else self.app.theme["CARD_HOVER"])

    def on_devices_changed(self):
        if self.lamps_row is None:
            return
        for child in self.lamps_row.winfo_children():
            child.destroy()
        self.lamp_swatches = {}
        devices = self.app.controller.active_devices()
        if not devices:
            ttk.Label(self.lamps_row, text="Nenhuma lâmpada ativa no cinema. Configure na página Lâmpadas.",
                      style="CardMuted.TLabel").pack(anchor="w")
            return
        for device in devices:
            chip = ttk.Frame(self.lamps_row, style="Card.TFrame")
            chip.pack(side="left", padx=(0, 16))
            swatch = Swatch(chip, self.app.theme, self.app.theme["CARD_HOVER"], size=14)
            swatch.pack(side="left", padx=(0, 6))
            self.lamp_swatches[device.id] = swatch
            ttk.Label(chip, text=device.name, style="CardStrong.TLabel").pack(side="left")
            ttk.Label(chip, text=f"  {ZONE_LABELS.get(device.zone, '')}", style="CardMuted.TLabel").pack(side="left")

"""Construção das abas visuais do Luz Cinema v2: Cinema Multi-Lâmpadas, Cenários, Presets e Conectar."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import webbrowser

from color_wheel import ColorWheel
from presets_data import DEFAULT_PRESETS, CINEMA_PROFILES
from scenarios import DEFAULT_SCENARIOS, Scenario
from multi_bulb import BulbDevice
from win_platform import APP_DIR
from ui_theme import THEMES

HELP = """LUZ CINEMA v2 — NOVIDADES E GUIA COMPLETO

1. MULTI-LÂMPADAS COM AMBILIGHT ESPACIAL
Agora você pode ter várias lâmpadas sincronizadas com a tela ao mesmo tempo!
Cada lâmpada pode ser configurada para uma zona da tela:
- Lado Esquerdo (left): acompanha a metade esquerda da tela.
- Lado Direito (right): acompanha a metade direita da tela.
- Topo / Teto (top): acompanha o céu e a iluminação superior.
- Tela Inteira (all): faz a média do ambiente geral da tela.

2. CENÁRIOS DE ILUMINAÇÃO
Na aba 'Cenários & Lâmpadas', ative cenários temáticos com 1 clique:
- Setup Cinema: ambientação azul e roxa perfeita para filmes.
- Cyberpunk Neon: azul neon na esquerda e rosa choque na direita.
- Pôr do Sol Dourado: aconchego de luz alaranjada.
- Leitura Relaxante: luz quente aveludada sem cansar a vista.
- Trabalho Focado: branco frio puro no brilho máximo.

3. BANDEJA DO SISTEMA (SYSTEM TRAY)
Clique com o botão direito no ícone da lâmpada ao lado do relógio do Windows para
ativar qualquer Cenário instantaneamente ou controlar lâmpadas individuais!
"""

ZONE_LABELS = {
    "all": "Tela Inteira (all)",
    "left": "Lado Esquerdo (left)",
    "right": "Lado Direito (right)",
    "top": "Topo / Teto (top)",
    "bottom": "Base (bottom)",
    "center": "Centro (center)",
    "none": "Desativada (none)",
}
ZONE_KEYS = list(ZONE_LABELS.keys())


class TabViewsMixin:
    """Mixin responsável pela interface de usuário do Luz Cinema v2."""

    def locked(self, widget, normal="normal"):
        self.lockables.append((widget, normal))
        return widget

    def slider(self, page, label, variable, low, high, unit):
        row = ttk.Frame(page)
        row.pack(fill="x", pady=4)
        row.columnconfigure(1, weight=1)
        ttk.Label(row, text=label, width=28).grid(row=0, column=0, sticky="w")
        value_label = ttk.Label(row, width=18)
        value_label.grid(row=0, column=2, padx=(8, 0))

        def display(*_):
            try:
                n = float(variable.get())
            except (ValueError, TypeError):
                n = 0.0
            if unit == " s":
                if n <= 0.01:
                    value_label.configure(text="0.00 s (Instantâneo)")
                elif n <= 0.25:
                    fps = round(1.0 / n) if n > 0 else 0
                    value_label.configure(text=f"{n:.2f} s ({fps} FPS)")
                else:
                    value_label.configure(text=f"{n:.2f} s")
            else:
                value_label.configure(text=f"{n:.0f}{unit}")

        display()
        variable.trace_add("write", display)
        self.locked(ttk.Scale(row, from_=low, to=high, variable=variable)).grid(row=0, column=1, sticky="ew")

    # =========================================================
    # ABA 1: CINEMA MULTI-LÂMPADAS
    # =========================================================
    def build_cinema(self, page):
        t = self.current_theme

        # Monitor e Modo
        top_row = ttk.Frame(page)
        top_row.pack(fill="x", pady=(0, 10))
        ttk.Label(top_row, text="Tela do filme:").pack(side="left", padx=(0, 8))
        self.monitor_box = self.locked(ttk.Combobox(top_row, textvariable=self.monitor, state="readonly", width=34), "readonly")
        self.monitor_box.pack(side="left", fill="x", expand=True)

        self.monitors = []
        try:
            from mss import MSS
            with MSS() as capture:
                self.monitors = [dict(m) for m in capture.monitors[1:]]
            choices = [f"Monitor {i+1} · {m['width']} × {m['height']}" for i, m in enumerate(self.monitors)]
            self.monitor_box["values"] = choices
            if choices:
                self.monitor_box.current(min(self.saved_monitor, len(choices) - 1))
        except Exception:
            self.status.set("Não foi possível listar as telas. Verifique a sessão do Windows.")

        # Ambilight Multi-Zona Visual Preview (Canvas simulando tela com Lado Esquerdo, Centro e Lado Direito)
        preview_box = ttk.LabelFrame(page, text=" Prévia Ambilight Multi-Zona ", padding=8)
        preview_box.pack(fill="x", pady=(0, 10))

        zones_container = ttk.Frame(preview_box)
        zones_container.pack(fill="x")
        zones_container.columnconfigure(0, weight=1)
        zones_container.columnconfigure(1, weight=1)
        zones_container.columnconfigure(2, weight=1)

        self.zone_swatches = {}

        # Zona Esquerda
        f_left = ttk.Frame(zones_container)
        f_left.grid(row=0, column=0, sticky="nsew", padx=2)
        ttk.Label(f_left, text="◀ Esquerda", style="Muted.TLabel").pack()
        sw_left = tk.Canvas(f_left, height=48, bg="#1a1f33", highlightthickness=1, highlightbackground=t["BORDER"])
        sw_left.pack(fill="x")
        self.zone_swatches["left"] = sw_left

        # Zona Centro / Geral
        f_all = ttk.Frame(zones_container)
        f_all.grid(row=0, column=1, sticky="nsew", padx=2)
        ttk.Label(f_all, text="⬛ Geral / Centro", style="Muted.TLabel").pack()
        sw_all = tk.Canvas(f_all, height=48, bg="#1a1f33", highlightthickness=1, highlightbackground=t["BORDER"])
        sw_all.pack(fill="x")
        self.zone_swatches["all"] = sw_all

        # Zona Direita
        f_right = ttk.Frame(zones_container)
        f_right.grid(row=0, column=2, sticky="nsew", padx=2)
        ttk.Label(f_right, text="Direita ▶", style="Muted.TLabel").pack()
        sw_right = tk.Canvas(f_right, height=48, bg="#1a1f33", highlightthickness=1, highlightbackground=t["BORDER"])
        sw_right.pack(fill="x")
        self.zone_swatches["right"] = sw_right

        # Mapeamento Espacial de Lâmpadas no Cinema
        lamps_frame = ttk.LabelFrame(page, text=" Distribuição das Lâmpadas na Sala / Tela ", padding=8)
        lamps_frame.pack(fill="x", pady=(0, 10))

        self.cinema_lamps_container = ttk.Frame(lamps_frame)
        self.cinema_lamps_container.pack(fill="x")
        self.refresh_cinema_lamps_ui()

        # Perfis Rápidos de Calibração (1 Clique)
        profiles_frame = ttk.LabelFrame(page, text=" ⚡ Perfis Prontos de Calibração (1 Clique) ", padding=(6, 6))
        profiles_frame.pack(fill="x", pady=(0, 10))

        prof_row = ttk.Frame(profiles_frame)
        prof_row.pack(fill="x")
        for i in range(len(CINEMA_PROFILES)):
            prof_row.columnconfigure(i, weight=1)

        for idx, prof in enumerate(CINEMA_PROFILES):
            btn = ttk.Button(
                prof_row,
                text=prof["short_name"],
                command=lambda p=prof: self.apply_cinema_profile(p),
            )
            btn.grid(row=0, column=idx, padx=2, pady=2, sticky="ew")

        # Sliders de Calibração
        self.slider(page, "Brilho máximo", self.brightness, 5, 100, "%")
        self.slider(page, "Vibração das cores", self.saturation, 50, 250, "%")
        self.slider(page, "Foco no destaque da tela", self.standout, 0, 100, "%")
        self.slider(page, "Suavidade da transição", self.smoothing, 0.0, 2.0, " s")
        self.slider(page, "Velocidade de captura (FPS)", self.interval, 0.03, 0.50, " s")
        self.slider(page, "Recorte em cima e embaixo", self.crop, 0, 30, "%")
        self.slider(page, "Apagar cenas abaixo de", self.dark_percent, 0, 15, "%")

        # Opções Dinâmicas
        checks_row = ttk.Frame(page)
        checks_row.pack(fill="x", pady=(2, 8))
        self.locked(ttk.Checkbutton(checks_row, text="Apagar lâmpadas em cenas pretas / cinzas", variable=self.off_on_neutral)).pack(anchor="w")
        self.locked(ttk.Checkbutton(checks_row, text="Clarão dinâmico Flashbang (explosões brancas a 100%)", variable=self.flash_boost)).pack(anchor="w", pady=(2, 0))
        self.locked(ttk.Checkbutton(checks_row, text="Modo claro (iluminar páginas brancas e quentes)", variable=self.light_mode)).pack(anchor="w", pady=(2, 0))

        # Botões de Ação
        buttons = ttk.Frame(page)
        buttons.pack(fill="x", pady=(6, 0))
        self.preview_button = self.locked(ttk.Button(buttons, text="Prévia na tela", command=lambda: self.start(False)))
        self.preview_button.pack(side="left")
        self.start_button = self.locked(ttk.Button(buttons, text="Sincronizar Todas as Lâmpadas", style="Accent.TButton", command=lambda: self.start(True)))
        self.start_button.pack(side="left", padx=10)
        self.stop_button = ttk.Button(buttons, text="Parar", state="disabled", command=self.stop)
        self.stop_button.pack(side="left")
        self.cinema_off_btn = ttk.Button(buttons, text="⏻ Apagar Lâmpadas", style="Danger.TButton", command=self.turn_off_all_lights)
        self.cinema_off_btn.pack(side="left", padx=10)
        ttk.Button(buttons, text="Salvar ajustes", command=self.save_settings).pack(side="right")

    def refresh_cinema_lamps_ui(self):
        """Atualiza a grade de lâmpadas ativas e seleção de zona espacial na aba Cinema."""
        if not hasattr(self, "cinema_lamps_container"):
            return
        for child in self.cinema_lamps_container.winfo_children():
            child.destroy()

        devices = list(self.bulb_controller.devices.values())
        if not devices:
            ttk.Label(self.cinema_lamps_container, text="Nenhuma lâmpada adicionada ainda. Adicione na aba 'Cenários & Lâmpadas'.", style="Muted.TLabel").pack(anchor="w", pady=4)
            return

        for dev in devices:
            row = ttk.Frame(self.cinema_lamps_container)
            row.pack(fill="x", pady=2)

            # Checkbox de ativação
            enable_var = tk.BooleanVar(value=dev.enabled)

            def _on_toggle(d=dev, v=enable_var):
                d.enabled = v.get()
                self.save_settings()
                self.update_tray_menu()

            cb = ttk.Checkbutton(row, text=f"{dev.name} ({dev.connection_type.upper()})", variable=enable_var, command=_on_toggle)
            cb.pack(side="left")

            # Combobox de Zona
            zone_var = tk.StringVar(value=ZONE_LABELS.get(dev.zone, "Tela Inteira (all)"))

            def _on_zone_change(evt, d=dev, zv=zone_var):
                txt = zv.get()
                # Extrai o código da zona entre parênteses
                for k, v in ZONE_LABELS.items():
                    if v == txt:
                        d.zone = k
                        break
                self.save_settings()
                self.update_tray_menu()

            combo = ttk.Combobox(row, textvariable=zone_var, values=list(ZONE_LABELS.values()), state="readonly", width=22)
            combo.pack(side="right")
            combo.bind("<<ComboboxSelected>>", _on_zone_change)
            ttk.Label(row, text="Acompanhar: ", style="Muted.TLabel").pack(side="right", padx=(0, 6))

    # =========================================================
    # ABA 2: CENÁRIOS & LÂMPADAS
    # =========================================================
    def build_scenarios(self, page):
        t = self.current_theme
        ttk.Label(page, text="Cenários e Lâmpadas Conectadas", font=("Segoe UI Semibold", 16)).pack(anchor="w")
        ttk.Label(page, text="Crie ambientes de luz personalizados ou controle lâmpadas individualmente.", style="Muted.TLabel").pack(anchor="w", pady=(2, 10))

        content = ttk.Frame(page)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)

        # Coluna Esquerda: Cenários de Iluminação
        left_col = ttk.Frame(content)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        ttk.Label(left_col, text="Cenários Prontos", font=("Segoe UI Semibold", 12)).pack(anchor="w", pady=(0, 6))
        self.scenarios_grid = ttk.Frame(left_col)
        self.scenarios_grid.pack(fill="x", pady=(0, 10))
        self.refresh_scenarios_grid_ui()

        # Salvar Cenário Personalizado
        ttk.Separator(left_col, orient="horizontal").pack(fill="x", pady=8)
        ttk.Label(left_col, text="Salvar Estado Atual como Cenário", font=("Segoe UI Semibold", 12)).pack(anchor="w", pady=(0, 4))
        save_box = ttk.Frame(left_col)
        save_box.pack(fill="x", pady=(0, 8))
        self.new_scenario_entry = ttk.Entry(save_box)
        self.new_scenario_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(save_box, text="Salvar Cenário", command=self.save_current_as_scenario).pack(side="left")

        self.custom_scenarios_frame = ttk.Frame(left_col)
        self.custom_scenarios_frame.pack(fill="both", expand=True)
        self.refresh_custom_scenarios_ui()

        # Coluna Direita: Gerenciamento de Lâmpadas
        right_col = ttk.Frame(content)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(12, 0))

        ttk.Label(right_col, text="Minhas Lâmpadas", font=("Segoe UI Semibold", 12)).pack(anchor="w", pady=(0, 6))

        lamps_box = ttk.Frame(right_col)
        lamps_box.pack(fill="both", expand=True)

        self.lamps_listbox = tk.Listbox(lamps_box, height=8, bg=t["ENTRY_BG"], fg=t["FG"], selectbackground=t["ACCENT"], selectforeground="#ffffff", borderwidth=0, highlightthickness=1, highlightbackground=t["BORDER"])
        self.lamps_listbox.pack(fill="both", expand=True, pady=(0, 8))

        # Botões de Gerenciamento de Lâmpadas
        btn_bar = ttk.Frame(right_col)
        btn_bar.pack(fill="x", pady=(0, 6))
        ttk.Button(btn_bar, text="+ Local (IP/Chave)", command=self.open_add_local_bulb_popup).pack(side="left", padx=(0, 6))
        ttk.Button(btn_bar, text="+ Da Conta Tuya", command=self.import_tuya_account_bulbs).pack(side="left", padx=(0, 6))
        ttk.Button(btn_bar, text="Remover", command=self.delete_selected_bulb).pack(side="left")

        # Ações Rápidas por Lâmpada Selecionada
        quick_frame = ttk.LabelFrame(right_col, text=" Ação Rápida na Lâmpada Selecionada ", padding=8)
        quick_frame.pack(fill="x", pady=(8, 0))
        q_row = ttk.Frame(quick_frame)
        q_row.pack(fill="x")
        ttk.Button(q_row, text="Acender", command=lambda: self.toggle_selected_bulb_power(True)).pack(side="left", padx=(0, 6))
        ttk.Button(q_row, text="Apagar", command=lambda: self.toggle_selected_bulb_power(False)).pack(side="left", padx=(0, 6))
        ttk.Button(q_row, text="Testar Conexão", command=self.test_selected_bulb).pack(side="left")

        self.refresh_lamps_listbox_ui()

    def refresh_scenarios_grid_ui(self):
        for child in self.scenarios_grid.winfo_children():
            child.destroy()
        for i, sc in enumerate(DEFAULT_SCENARIOS):
            card = ttk.Frame(self.scenarios_grid)
            card.grid(row=i // 2, column=i % 2, sticky="ew", padx=3, pady=3)
            btn = ttk.Button(card, text=f"{sc.icon} {sc.name}", style="Preset.TButton", command=lambda s=sc: self.activate_scenario(s))
            btn.pack(fill="x", expand=True)
        self.scenarios_grid.columnconfigure(0, weight=1)
        self.scenarios_grid.columnconfigure(1, weight=1)

    def refresh_custom_scenarios_ui(self):
        for child in self.custom_scenarios_frame.winfo_children():
            child.destroy()
        customs = [s for s in getattr(self, "scenarios", []) if s.is_custom]
        if not customs:
            return
        ttk.Label(self.custom_scenarios_frame, text="Cenários Personalizados Salvos:", style="Muted.TLabel").pack(anchor="w", pady=(4, 2))
        for i, sc in enumerate(customs):
            row = ttk.Frame(self.custom_scenarios_frame)
            row.pack(fill="x", pady=2)
            btn = ttk.Button(row, text=f"{sc.icon} {sc.name}", style="Preset.TButton", command=lambda s=sc: self.activate_scenario(s))
            btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
            del_btn = ttk.Button(row, text="✕", width=3, command=lambda s=sc: self.delete_custom_scenario(s.id))
            del_btn.pack(side="left")

    def refresh_lamps_listbox_ui(self):
        if not hasattr(self, "lamps_listbox"):
            return
        self.lamps_listbox.delete(0, tk.END)
        for dev in self.bulb_controller.devices.values():
            status_dot = "●" if dev.enabled else "○"
            status_text = "LIGADA" if dev.is_on else "APAGADA"
            self.lamps_listbox.insert(tk.END, f"{status_dot} {dev.name}  [{dev.connection_type.upper()}]  ·  Zona: {dev.zone}  ({status_text})")

    # =========================================================
    # ABA 3: PRESETS & CORES (CONTROLE MANUAL)
    # =========================================================
    def build_presets(self, page):
        t = self.current_theme
        ttk.Label(page, text="Controle de Cores e Brilho", font=("Segoe UI Semibold", 16)).pack(anchor="w")
        ttk.Label(page, text="Escolha a cor ou branco desejado pelo PC sem precisar do celular.", style="Muted.TLabel").pack(anchor="w", pady=(2, 10))

        content = ttk.Frame(page)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)

        # Coluna Esquerda: Roda de cores e controle
        left_col = ttk.Frame(content)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 15))

        # Seletor de lâmpada alvo para controle manual
        target_row = ttk.Frame(left_col)
        target_row.pack(fill="x", pady=(0, 8))
        ttk.Label(target_row, text="Aplicar em:").pack(side="left", padx=(0, 6))
        self.manual_target_var = tk.StringVar(value="Todas as Lâmpadas")
        self.manual_target_combo = ttk.Combobox(target_row, textvariable=self.manual_target_var, state="readonly")
        self.manual_target_combo.pack(side="left", fill="x", expand=True)
        self.update_manual_target_choices()

        # Modo de luz (RGB vs CCT)
        mode_frame = ttk.Frame(left_col)
        mode_frame.pack(fill="x", pady=(0, 8))
        ttk.Radiobutton(mode_frame, text="Cor RGB", variable=self.manual_mode, value="colour", command=self.update_manual_preview).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(mode_frame, text="Branco CCT", variable=self.manual_mode, value="white", command=self.update_manual_preview).pack(side="left")

        # Roda de Cores
        wheel_container = ttk.Frame(left_col)
        wheel_container.pack(pady=4)
        self.wheel_canvas = tk.Canvas(wheel_container, width=180, height=180, bg=t["BG"], highlightthickness=0)
        self.wheel_canvas.pack()
        self.color_wheel = ColorWheel(self.wheel_canvas, 180, self.on_wheel_pick)

        # Sliders
        self.slider(left_col, "Brilho", self.manual_brightness, 1, 100, "%")
        self.slider(left_col, "Temperatura Branca", self.manual_temp, 0, 100, "%")
        self.manual_brightness.trace_add("write", lambda *_: self.on_manual_control_change())
        self.manual_temp.trace_add("write", lambda *_: self.on_manual_control_change())

        # Amostra de Cor
        preview_row = ttk.Frame(left_col)
        preview_row.pack(fill="x", pady=6)
        self.manual_swatch = tk.Canvas(preview_row, width=38, height=38, bg="#ff0000", highlightthickness=1, highlightbackground=t["BORDER"])
        self.manual_swatch.pack(side="left", padx=(0, 10))
        self.manual_swatch_label = ttk.Label(preview_row, text="#FF0000 (100%)", font=("Segoe UI Semibold", 10))
        self.manual_swatch_label.pack(side="left")

        # Botões de Ação
        btn_row = ttk.Frame(left_col)
        btn_row.pack(fill="x", pady=6)
        self.apply_btn = ttk.Button(btn_row, text="Aplicar à Lâmpada", style="Accent.TButton", command=self.apply_current_manual)
        self.apply_btn.pack(side="left", padx=(0, 8))
        self.off_btn = ttk.Button(btn_row, text="⏻ Apagar Lâmpada", style="Danger.TButton", command=self.turn_off_selected_or_all)
        self.off_btn.pack(side="left", padx=(0, 8))
        ttk.Checkbutton(left_col, text="Aplicar em tempo real enquanto ajusta", variable=self.live_manual).pack(anchor="w", pady=(2, 0))

        # Coluna Direita: Presets Rápidos
        right_col = ttk.Frame(content)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(15, 0))

        ttk.Label(right_col, text="Presets Rápidos", font=("Segoe UI Semibold", 12)).pack(anchor="w", pady=(0, 6))
        presets_grid = ttk.Frame(right_col)
        presets_grid.pack(fill="x", pady=(0, 10))
        self.default_preset_swatches = []
        for i, preset in enumerate(DEFAULT_PRESETS):
            card = ttk.Frame(presets_grid)
            card.grid(row=i // 2, column=i % 2, sticky="ew", padx=3, pady=3)
            swatch = tk.Canvas(card, width=16, height=16, bg=preset["color_hex"], highlightthickness=1, highlightbackground=t["BORDER"])
            swatch.pack(side="left", padx=(2, 6))
            swatch.bind("<Button-1>", lambda _, p=preset: self.activate_preset(p))
            self.default_preset_swatches.append(swatch)
            btn = ttk.Button(card, text=preset["name"], style="Preset.TButton", command=lambda p=preset: self.activate_preset(p))
            btn.pack(side="left", fill="x", expand=True)
        presets_grid.columnconfigure(0, weight=1)
        presets_grid.columnconfigure(1, weight=1)

        # Salvar Preset Personalizado
        ttk.Separator(right_col, orient="horizontal").pack(fill="x", pady=8)
        ttk.Label(right_col, text="Salvar Cor Personalizada", font=("Segoe UI Semibold", 12)).pack(anchor="w", pady=(0, 6))
        save_row = ttk.Frame(right_col)
        save_row.pack(fill="x", pady=(0, 6))
        self.new_preset_entry = ttk.Entry(save_row)
        self.new_preset_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(save_row, text="Salvar", command=self.save_custom_preset).pack(side="left")

        self.custom_presets_frame = ttk.Frame(right_col)
        self.custom_presets_frame.pack(fill="both", expand=True)
        self.refresh_custom_presets_ui()

        # Opções do Sistema
        tray_box = ttk.LabelFrame(page, text=" Opções do Sistema ", padding=10)
        tray_box.pack(fill="x", pady=(10, 0))
        ttk.Checkbutton(tray_box, text="Minimizar para a bandeja do sistema (System Tray) ao fechar a janela", variable=self.minimize_to_tray).pack(anchor="w", pady=2)
        ttk.Checkbutton(tray_box, text="Iniciar automaticamente com o Windows (inicia minimizado na bandeja)", variable=self.start_with_windows, command=self.toggle_autostart).pack(anchor="w", pady=2)

        self.update_manual_preview()

    def update_manual_target_choices(self):
        if not hasattr(self, "manual_target_combo"):
            return
        choices = ["Todas as Lâmpadas"]
        for d in self.bulb_controller.devices.values():
            choices.append(f"{d.name} ({d.zone})")
        self.manual_target_combo["values"] = choices
        if self.manual_target_var.get() not in choices:
            self.manual_target_var.set("Todas as Lâmpadas")

    # =========================================================
    # ABA 4: CONECTAR
    # =========================================================
    def build_connection(self, page):
        ttk.Label(page, text="Conexão com a Nuvem e Rede Local", font=("Segoe UI Semibold", 16)).pack(anchor="w")
        ttk.Label(page, text="Conecte sua conta Tuya pelo celular ou escaneie lâmpadas na rede local.", style="Muted.TLabel").pack(anchor="w", pady=(2, 12))

        # Conta Tuya
        cloud_frame = ttk.LabelFrame(page, text=" Conta Tuya (Recomendado — Controle via Internet) ", padding=12)
        cloud_frame.pack(fill="x", pady=(0, 12))

        self.cloud_state = tk.StringVar(value="Autorização salva neste Windows." if (APP_DIR / "dados" / "tuya.enc").exists() else "Conta ainda não vinculada.")
        ttk.Label(cloud_frame, textvariable=self.cloud_state, style="Muted.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Label(cloud_frame, text="1. Clique em 'Vincular por QR code' e autorize no app Tuya Smart ou Elgin Smart.\n2. Em seguida clique em 'Importar Lâmpadas da Conta' para adicioná-las automaticamente ao sistema.", wraplength=680).pack(anchor="w", pady=(0, 8))

        row_c = ttk.Frame(cloud_frame)
        row_c.pack(fill="x", pady=4)
        ttk.Button(row_c, text="Vincular por QR code", command=self.open_tuya_link).pack(side="left")
        ttk.Button(row_c, text="Testar acesso", command=self.test_cloud).pack(side="left", padx=10)
        ttk.Button(row_c, text="Importar Lâmpadas da Conta", command=self.import_tuya_account_bulbs).pack(side="left")

        # Rede Local
        local_frame = ttk.LabelFrame(page, text=" Rede Local (Controle direto sem Internet) ", padding=12)
        local_frame.pack(fill="x")
        ttk.Label(local_frame, text="Busque lâmpadas Wi-Fi compatíveis ou adicione manualmente por IP e Chave Local.", style="Muted.TLabel").pack(anchor="w", pady=(0, 8))

        row_l = ttk.Frame(local_frame)
        row_l.pack(fill="x", pady=4)
        ttk.Button(row_l, text="Buscar na rede local", command=self.scan_local_network).pack(side="left")
        ttk.Button(row_l, text="+ Adicionar Lâmpada Manual", command=self.open_add_local_bulb_popup).pack(side="left", padx=10)

    # =========================================================
    # DIÁLOGOS E POPUPS
    # =========================================================
    def open_add_local_bulb_popup(self):
        t = self.current_theme
        top = tk.Toplevel(self.root)
        top.title("Adicionar Lâmpada Local")
        top.geometry("460x340")
        top.configure(bg=t["BG"])

        ttk.Label(top, text="Adicionar Lâmpada na Rede Local", font=("Segoe UI Semibold", 13)).pack(anchor="w", padx=16, pady=(16, 8))

        form = ttk.Frame(top, padding=16)
        form.pack(fill="both", expand=True)
        form.columnconfigure(1, weight=1)

        name_var = tk.StringVar(value=f"Lâmpada {len(self.bulb_controller.devices) + 1}")
        ip_var = tk.StringVar()
        id_var = tk.StringVar()
        key_var = tk.StringVar()
        version_var = tk.StringVar(value="3.5")
        zone_var = tk.StringVar(value="all")

        fields = [
            ("Nome amigável:", name_var),
            ("IP da lâmpada:", ip_var),
            ("ID virtual:", id_var),
            ("Chave local (Key):", key_var),
        ]
        for idx, (label, var) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=idx, column=0, sticky="w", pady=4)
            ttk.Entry(form, textvariable=var).grid(row=idx, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="Versão protocolo:").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Combobox(form, textvariable=version_var, values=["3.5", "3.4", "3.3", "3.1"], state="readonly", width=8).grid(row=4, column=1, sticky="w", pady=4)

        ttk.Label(form, text="Zona no Cinema:").grid(row=5, column=0, sticky="w", pady=4)
        ttk.Combobox(form, textvariable=zone_var, values=ZONE_KEYS, state="readonly", width=14).grid(row=5, column=1, sticky="w", pady=4)

        def _save():
            if not ip_var.get().strip() or not id_var.get().strip():
                messagebox.showerror("Erro", "Preencha ao menos o IP e o ID da lâmpada.", parent=top)
                return
            dev = BulbDevice(
                id=id_var.get().strip(),
                name=name_var.get().strip() or "Lâmpada Local",
                connection_type="local",
                ip=ip_var.get().strip(),
                key=key_var.get().strip(),
                version=version_var.get().strip() or "3.5",
                zone=zone_var.get(),
            )
            self.bulb_controller.devices[dev.id] = dev
            self.save_settings()
            self.refresh_lamps_listbox_ui()
            self.refresh_cinema_lamps_ui()
            self.update_manual_target_choices()
            self.update_tray_menu()
            top.destroy()

        btn_row = ttk.Frame(top, padding=16)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="Cancelar", command=top.destroy).pack(side="right")
        ttk.Button(btn_row, text="Salvar Lâmpada", style="Accent.TButton", command=_save).pack(side="right", padx=8)

    def open_help_popup(self):
        t = getattr(self, "current_theme", THEMES["dark"])
        popup = tk.Toplevel(self.root)
        popup.title("Guia do Usuário — Luz Cinema v2")
        popup.geometry("740x700")
        popup.minsize(580, 480)
        popup.configure(bg=t["BG"])

        header = ttk.Frame(popup, padding=(20, 16, 20, 10))
        header.pack(fill="x")
        ttk.Label(header, text="Guia de Uso Multi-Lâmpadas & Cenários", font=("Segoe UI Semibold", 16)).pack(side="left")
        ttk.Button(header, text="Guia oficial de chaves Tuya", command=lambda: webbrowser.open("https://github.com/jasonacox/tinytuya#setup-wizard---getting-local-keys")).pack(side="right")

        body = ttk.Frame(popup, padding=(20, 0, 20, 16))
        body.pack(fill="both", expand=True)
        text = tk.Text(body, bg=t["PANEL"], fg=t["FG"], font=("Segoe UI", 10), wrap="word", padx=15, pady=12, borderwidth=0)
        scroll = ttk.Scrollbar(body, command=text.yview)
        scroll.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        text.configure(yscrollcommand=scroll.set)
        help_text = (
            "LUZ CINEMA v2 — NOVIDADES E GUIA COMPLETO\n\n"
            "1. MULTI-LÂMPADAS COM AMBILIGHT ESPACIAL\n"
            "Agora você pode ter várias lâmpadas sincronizadas com a tela ao mesmo tempo!\n"
            "Cada lâmpada pode ser configurada para uma zona da tela:\n"
            "- Lado Esquerdo (left): acompanha explosões, clima e cores da metade esquerda da tela.\n"
            "- Lado Direito (right): acompanha os acontecimentos da metade direita da tela.\n"
            "- Topo / Teto (top): acompanha o céu e a iluminação superior da cena.\n"
            "- Tela Inteira (all): faz a média do ambiente geral da tela.\n\n"
            "2. CENÁRIOS DE ILUMINAÇÃO\n"
            "Na aba 'Cenários & Lâmpadas', ative cenários temáticos com 1 clique:\n"
            "- Setup Cinema: ambientação azul e roxa perfeita para filmes.\n"
            "- Cyberpunk Neon: azul neon na esquerda e rosa choque na direita.\n"
            "- Pôr do Sol Dourado: aconchego de luz alaranjada.\n"
            "- Leitura Relaxante: luz quente aveludada sem cansar a vista.\n"
            "- Trabalho Focado: branco frio puro no brilho máximo.\n"
            "Você também pode salvar suas próprias combinações personalizadas!\n\n"
            "3. BANDEJA DO SISTEMA (SYSTEM TRAY)\n"
            "Clique com o botão direito no ícone da lâmpada ao lado do relógio do Windows para:\n"
            "- Ativar qualquer Cenário instantaneamente sem precisar abrir o app.\n"
            "- Acender ou apagar lâmpadas individuais ou todas juntas.\n"
            "- Iniciar o cinema na tela desejada.\n"
        )
        text.insert("1.0", help_text)
        text.configure(state="disabled")
        btn_frame = ttk.Frame(popup, padding=(20, 0, 20, 16))
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="Fechar", command=popup.destroy).pack(side="right")

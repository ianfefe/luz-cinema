"""Luz Cinema v2 — Controle Multi-Lâmpadas com Ambilight Espacial e Sistema de Cenários."""
from __future__ import annotations

import colorsys
import ctypes
from dataclasses import replace
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from PIL import Image, ImageTk
from core import (
    Settings,
    Smoother,
    LocalBulb,
    BulbError,
    screen_color,
    should_send,
    cct_to_rgb,
    rgb_to_hex,
    hex_to_rgb,
    crop_zone,
    compute_zones_colors,
)

# Módulos especializados da v2
from win_platform import (
    APP_DIR,
    CONFIG,
    APP_REG_NAME,
    REG_RUN_KEY,
    REG_APPROVED_KEY,
    WAKE_EVENT_NAME,
    _WAKE_EVENT,
    check_single_instance,
    get_wake_event,
    get_target_app_cmd,
    is_autostart_enabled,
    set_autostart,
    protect,
    setup_windows_dpi_and_app_id,
)
from presets_data import DEFAULT_PRESETS, preset_color_hex
from scenarios import DEFAULT_SCENARIOS, Scenario
from multi_bulb import BulbDevice, MultiBulbController
from icon_utils import (
    render_icon,
    create_tray_icon_image,
    create_color_wheel_image,
    export_ico,
    get_icon_file,
)
from color_wheel import ColorWheel
from ui_theme import (
    THEMES,
    BG,
    PANEL,
    PANEL_ALT,
    FG,
    MUTED,
    ACCENT,
    ACCENT_HOVER,
    DANGER,
    BORDER,
    ENTRY_BG,
    ThemeMixin,
)
from tray_manager import TrayMixin
from tab_views import TabViewsMixin, HELP


class App(TabViewsMixin, TrayMixin, ThemeMixin):
    """Controlador principal do Luz Cinema v2 (Multi-Lâmpadas e Cenários)."""

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Luz Cinema v2 · Multi-Lâmpadas & Cenários")
        root.geometry("880x960")
        root.minsize(820, 840)

        # Estado visual e de temas
        self.theme_mode = tk.StringVar(value="dark")
        self.current_theme = THEMES["dark"]
        self._element_images = {}

        # Fila de eventos e controle de threads
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None
        self.closing = False
        self.alive = True
        self.running = False
        self.lockables = []
        self.default_preset_swatches = []

        # Gerenciadores de Multi-Lâmpadas e Cenários
        self.bulb_controller = MultiBulbController()
        self.scenarios = list(DEFAULT_SCENARIOS)

        # Variáveis reativas de Cinema
        self.status = tk.StringVar(value="Luz Cinema v2 pronto. Configure suas lâmpadas ou escolha um Cenário.")
        self.monitor = tk.StringVar()
        self.brightness = tk.DoubleVar(value=45)
        self.saturation = tk.DoubleVar(value=140)
        self.standout = tk.DoubleVar(value=100)
        self.smoothing = tk.DoubleVar(value=0.0)
        self.interval = tk.DoubleVar(value=0.05)
        self.crop = tk.DoubleVar(value=10)
        self.dark_percent = tk.DoubleVar(value=5)
        self.off_on_neutral = tk.BooleanVar(value=True)
        self.flash_boost = tk.BooleanVar(value=True)
        self.light_mode = tk.BooleanVar(value=False)
        self.saved_monitor = 0

        # Variáveis reativas de Modo Manual e Presets
        self.manual_mode = tk.StringVar(value="colour")
        self.manual_hue = 0.0
        self.manual_sat = 1.0
        self.manual_brightness = tk.DoubleVar(value=100)
        self.manual_temp = tk.DoubleVar(value=100)
        self.live_manual = tk.BooleanVar(value=False)
        self.custom_presets = []

        # Bandeja do sistema e Início Automático
        self.minimize_to_tray = tk.BooleanVar(value=True)
        self.start_with_windows = tk.BooleanVar(value=is_autostart_enabled())
        self.tray_icon = None
        self._exiting_completely = False

        # Conexão manual e persistência
        self.manual_queue = queue.Queue(maxsize=1)
        self.manual_thread = None
        self.manual_worker_stop = threading.Event()

        # Carrega preferências e temas
        self.load_settings()
        self.apply_theme()

        # Ícones da janela
        ico_file = get_icon_file()
        if ico_file:
            try:
                root.iconbitmap(str(ico_file))
                with Image.open(ico_file) as img_f:
                    base_ico = img_f.copy()
                self.app_icons = [ImageTk.PhotoImage(base_ico.resize((n, n), Image.LANCZOS), master=root) for n in (256, 64, 48, 32, 16)]
                root.iconphoto(True, *self.app_icons)
            except Exception:
                self.app_icons = [ImageTk.PhotoImage(render_icon(size=n), master=root) for n in (256, 64, 48, 32, 16)]
                root.iconphoto(True, *self.app_icons)
        else:
            self.app_icons = [ImageTk.PhotoImage(render_icon(size=n), master=root) for n in (256, 64, 48, 32, 16)]
            root.iconphoto(True, *self.app_icons)

        # Cabeçalho
        header = ttk.Frame(root, padding=(28, 20, 28, 12))
        header.pack(fill="x")
        header_left = ttk.Frame(header)
        header_left.pack(side="left", fill="both", expand=True)

        if ico_file:
            try:
                self.header_logo = ImageTk.PhotoImage(base_ico.resize((48, 48), Image.LANCZOS), master=root)
            except Exception:
                self.header_logo = ImageTk.PhotoImage(render_icon(size=52), master=root)
        else:
            self.header_logo = ImageTk.PhotoImage(render_icon(size=52), master=root)
        ttk.Label(header_left, image=self.header_logo).pack(side="left", padx=(0, 14))

        header_text = ttk.Frame(header_left)
        header_text.pack(side="left", fill="y")
        ttk.Label(header_text, text="Luz Cinema v2", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header_text, text="Ambilight Multi-Lâmpadas com Zonas Espaciais e Cenários.", style="Muted.TLabel").pack(anchor="w")

        header_right = ttk.Frame(header)
        header_right.pack(side="right", anchor="e", pady=(4, 0))
        toggle_label = self.current_theme["toggle_label"]
        self.theme_toggle_btn = ttk.Button(header_right, text=toggle_label, style="ThemeToggle.TButton", command=self.toggle_theme)
        self.theme_toggle_btn.pack(side="right")

        # Abas da v2
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=26)

        tab_cinema = ttk.Frame(self.tabs, padding=20)
        tab_scenarios = ttk.Frame(self.tabs, padding=20)
        tab_presets = ttk.Frame(self.tabs, padding=20)
        tab_connect = ttk.Frame(self.tabs, padding=20)

        self.tabs.add(tab_cinema, text="  🎬 Cinema Multi-Lâmpadas  ")
        self.tabs.add(tab_scenarios, text="  ✨ Cenários & Lâmpadas  ")
        self.tabs.add(tab_presets, text="  🎨 Presets & Cores  ")
        self.tabs.add(tab_connect, text="  🔌 Conectar  ")

        self.build_cinema(tab_cinema)
        self.build_scenarios(tab_scenarios)
        self.build_presets(tab_presets)
        self.build_connection(tab_connect)
        self.setup_tray()

        # Barra inferior de status
        bottom_bar = ttk.Frame(root, style="Status.TFrame")
        bottom_bar.pack(side="bottom", fill="x", before=self.tabs)
        self.status_label = ttk.Label(bottom_bar, textvariable=self.status, wraplength=640, style="Status.TLabel", padding=(26, 12))
        self.status_label.pack(side="left", fill="x", expand=True)

        t = self.current_theme
        self.help_link = tk.Label(bottom_bar, text="Guia v2 ↗", bg=t["STATUS_BG"], fg=t["MUTED"], font=("Segoe UI", 9, "underline"), cursor="hand2")
        self.help_link.pack(side="right", padx=(10, 26))
        self.help_link.bind("<Button-1>", lambda _: self.open_help_popup())
        self.help_link.bind("<Enter>", lambda _: self.help_link.configure(fg=self.current_theme["FG"]))
        self.help_link.bind("<Leave>", lambda _: self.help_link.configure(fg=self.current_theme["MUTED"]))

        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)
        self.timer = self.root.after(100, self.drain)

    # ---------------------------------------------------------
    # Perfis de Calibração Rápida de Cinema & Jogos
    # ---------------------------------------------------------
    def apply_cinema_profile(self, profile: dict):
        """Aplica instantaneamente um perfil de calibração para o Modo Cinema."""
        self.brightness.set(float(profile.get("brightness", 75.0)))
        self.saturation.set(float(profile.get("saturation", 185.0)))
        self.standout.set(float(profile.get("standout", 90.0)))
        self.smoothing.set(float(profile.get("smoothing", 0.04)))
        self.interval.set(float(profile.get("interval", 0.05)))
        self.crop.set(int(profile.get("crop", 12)))
        self.dark_percent.set(float(profile.get("dark_percent", 5.0)))
        self.off_on_neutral.set(bool(profile.get("off_on_neutral", True)))
        self.flash_boost.set(bool(profile.get("flash_boost", True)))
        self.light_mode.set(bool(profile.get("light_mode", False)))

        self.save_settings()
        self.status.set(f"Perfil de calibração '{profile.get('name')}' aplicado com sucesso!")

    # ---------------------------------------------------------
    # Controle de Cenários e Múltiplas Lâmpadas
    # ---------------------------------------------------------
    def activate_scenario(self, scenario: Scenario):
        """Ativa um cenário de luz em todas as lâmpadas configuradas."""
        if self.running:
            self.stop(restore=False)
            if self.worker and self.worker.is_alive():
                self.worker.join(timeout=0.3)

        self.bulb_controller.apply_scenario(scenario)
        self.status.set(f"Cenário '{scenario.name}' ativado!")
        color_hex = rgb_to_hex(scenario.default_rgb)
        self.set_tray_icon_visual(color_hex=color_hex, cinema_mode=False, is_off=False)
        self.refresh_lamps_listbox_ui()

    def save_current_as_scenario(self):
        """Captura o estado de cor atual e salva como novo cenário personalizado."""
        name = self.new_scenario_entry.get().strip()
        if not name:
            name = f"Cenário {len(self.scenarios) + 1}"

        mode = self.manual_mode.get()
        rgb = self.get_current_manual_rgb()
        bright = round(self.manual_brightness.get())
        temp = round(self.manual_temp.get())

        sc = Scenario(
            id=f"custom_{int(time.time())}",
            name=name,
            description="Cenário personalizado criado pelo usuário.",
            icon="🌟",
            default_mode=mode,
            default_rgb=rgb,
            default_brightness=bright,
            default_temp=temp,
            is_custom=True,
        )
        self.scenarios.append(sc)
        self.new_scenario_entry.delete(0, tk.END)
        self.save_settings()
        self.refresh_custom_scenarios_ui()
        self.update_tray_menu()
        self.status.set(f"Cenário personalizado '{name}' salvo!")

    def delete_custom_scenario(self, scenario_id: str):
        self.scenarios = [s for s in self.scenarios if s.id != scenario_id]
        self.save_settings()
        self.refresh_custom_scenarios_ui()
        self.update_tray_menu()
        self.status.set("Cenário excluído.")

    def toggle_single_bulb(self, bulb_id: str, is_on: bool):
        mode = "colour" if is_on else "off"
        rgb = self.get_current_manual_rgb() if is_on else None
        self.bulb_controller.apply_manual_to_bulbs([bulb_id], mode=mode, rgb=rgb)
        dev = self.bulb_controller.devices.get(bulb_id)
        if dev:
            dev.is_on = is_on
        self.refresh_lamps_listbox_ui()
        self.status.set(f"{'Lâmpada ligada' if is_on else 'Lâmpada apagada'}.")

    def toggle_selected_bulb_power(self, is_on: bool):
        sel = self.lamps_listbox.curselection()
        if not sel:
            messagebox.showinfo("Aviso", "Selecione uma lâmpada na lista primeiro.")
            return
        keys = list(self.bulb_controller.devices.keys())
        if 0 <= sel[0] < len(keys):
            self.toggle_single_bulb(keys[sel[0]], is_on)

    def delete_selected_bulb(self):
        sel = self.lamps_listbox.curselection()
        if not sel:
            return
        keys = list(self.bulb_controller.devices.keys())
        if 0 <= sel[0] < len(keys):
            bid = keys[sel[0]]
            del self.bulb_controller.devices[bid]
            self.save_settings()
            self.refresh_lamps_listbox_ui()
            self.refresh_cinema_lamps_ui()
            self.update_manual_target_choices()
            self.update_tray_menu()
            self.status.set("Lâmpada removida.")

    def test_selected_bulb(self):
        sel = self.lamps_listbox.curselection()
        if not sel:
            messagebox.showinfo("Aviso", "Selecione uma lâmpada na lista para testar.")
            return
        keys = list(self.bulb_controller.devices.keys())
        if 0 <= sel[0] < len(keys):
            dev = self.bulb_controller.devices[keys[sel[0]]]
            self.status.set(f"Testando conexão com {dev.name}…")

            def test():
                conn = self.bulb_controller.get_bulb_instance(dev)
                if conn:
                    self.events.put(("status", f"Conexão com '{dev.name}' confirmada com sucesso!"))
                else:
                    self.events.put(("error", f"Falha ao conectar com '{dev.name}'. Verifique os dados."))

            threading.Thread(target=test, daemon=True).start()

    def import_tuya_account_bulbs(self):
        """Consulta as lâmpadas da conta Tuya vinculada e adiciona automaticamente à lista."""
        self.status.set("Buscando lâmpadas na conta Tuya vinculada…")

        def _task():
            try:
                from tuya_cloud import query_account_devices
                devs = query_account_devices()
                if not devs:
                    self.events.put(("status", "Nenhuma lâmpada localizada na conta. Vincule a conta Tuya primeiro."))
                    return

                added = 0
                for d in devs:
                    did = d["id"]
                    if did not in self.bulb_controller.devices:
                        name = d.get("name") or f"Lâmpada {did[-4:]}"
                        # Distribuição inteligente de zonas espaciais se for a primeira/segunda lâmpada
                        current_count = len(self.bulb_controller.devices)
                        suggested_zone = "left" if current_count == 0 else "right" if current_count == 1 else "all"
                        self.bulb_controller.devices[did] = BulbDevice(
                            id=did,
                            name=name,
                            connection_type="cloud",
                            zone=suggested_zone,
                        )
                        added += 1

                self.events.put(("bulbs_imported", added))
            except Exception as exc:
                self.events.put(("error", f"Erro ao consultar conta Tuya: {exc}"))

        threading.Thread(target=_task, daemon=True).start()

    def scan_local_network(self):
        self.status.set("Escaneando anúncios locais por cerca de 12 segundos…")

        def search():
            try:
                import tinytuya
                devices = tinytuya.deviceScan(verbose=False, maxretry=12, poll=False, forcescan=False)
                count = 0
                for ip, device in devices.items():
                    did = device.get("gwId") or device.get("id")
                    if did and did not in self.bulb_controller.devices:
                        self.bulb_controller.devices[did] = BulbDevice(
                            id=did,
                            name=f"Lâmpada {ip}",
                            connection_type="local",
                            ip=ip,
                            version=str(device.get("version", "3.3")),
                        )
                        count += 1
                self.events.put(("bulbs_imported", count))
            except Exception as e:
                self.events.put(("error", f"Falha na busca local: {e}"))

        threading.Thread(target=search, daemon=True).start()

    # ---------------------------------------------------------
    # Controle Manual e Presets
    # ---------------------------------------------------------
    def on_wheel_pick(self, hue: float, sat: float):
        self.manual_mode.set("colour")
        self.manual_hue = hue
        self.manual_sat = sat
        self.update_manual_preview()
        if self.live_manual.get():
            self.debounced_apply_manual()

    def on_manual_control_change(self):
        self.update_manual_preview()
        if self.live_manual.get():
            self.debounced_apply_manual()

    def debounced_apply_manual(self):
        if self.running:
            self.stop(restore=False)
        if hasattr(self, "_live_timer") and self._live_timer:
            self.root.after_cancel(self._live_timer)
        self._live_timer = self.root.after(60, self.apply_current_manual)

    def get_current_manual_rgb(self) -> tuple[int, int, int]:
        if self.manual_mode.get() == "white":
            return cct_to_rgb(self.manual_temp.get(), self.manual_brightness.get())
        bright = max(0.01, self.manual_brightness.get() / 100.0)
        r, g, b = colorsys.hsv_to_rgb(self.manual_hue, self.manual_sat, bright)
        return (round(r * 255), round(g * 255), round(b * 255))

    def update_manual_preview(self):
        if not hasattr(self, "manual_swatch"):
            return
        rgb = self.get_current_manual_rgb()
        color_hex = rgb_to_hex(rgb)
        self.manual_swatch.configure(bg=color_hex)
        mode_str = "Branco" if self.manual_mode.get() == "white" else "RGB"
        bright_val = round(self.manual_brightness.get())
        self.manual_swatch_label.configure(text=f"{color_hex.upper()} ({mode_str} {bright_val}%)")

    def _get_target_bulb_ids(self) -> list[str] | None:
        target_txt = getattr(self, "manual_target_var", None)
        if not target_txt or target_txt.get() == "Todas as Lâmpadas":
            return None
        selected_name = target_txt.get().split(" (")[0]
        for bid, d in self.bulb_controller.devices.items():
            if d.name == selected_name:
                return [bid]
        return None

    def apply_current_manual(self):
        if self.running:
            self.stop(restore=False)
            if self.worker and self.worker.is_alive():
                self.worker.join(timeout=0.3)
        target_ids = self._get_target_bulb_ids()
        mode = self.manual_mode.get()
        rgb = self.get_current_manual_rgb()
        brightness = round(self.manual_brightness.get())
        temp = round(self.manual_temp.get())
        self.bulb_controller.apply_manual_to_bulbs(target_ids, mode=mode, rgb=rgb, brightness=brightness, temp=temp)
        color_hex = rgb_to_hex(rgb)
        self.set_tray_icon_visual(color_hex=color_hex, cinema_mode=False, is_off=False)
        self.status.set("Cor aplicada às lâmpadas selecionadas.")
        self.refresh_lamps_listbox_ui()

    def turn_off_all_lights(self):
        if self.running:
            self.stop(restore=False)
            if self.worker and self.worker.is_alive():
                self.worker.join(timeout=0.3)
        self.bulb_controller.turn_off_all()
        self.set_tray_icon_visual(is_off=True)
        self.status.set("Todas as lâmpadas foram apagadas.")
        self.refresh_lamps_listbox_ui()

    def turn_off_selected_or_all(self):
        target_ids = self._get_target_bulb_ids()
        if not target_ids:
            self.turn_off_all_lights()
        else:
            self.bulb_controller.apply_manual_to_bulbs(target_ids, mode="off")
            self.status.set("Lâmpada selecionada apagada.")
            self.refresh_lamps_listbox_ui()

    def activate_preset(self, preset: dict):
        if self.running:
            self.stop(restore=False)
            if self.worker and self.worker.is_alive():
                self.worker.join(timeout=0.3)
        target_ids = self._get_target_bulb_ids()
        mode = preset.get("mode", "colour")
        self.manual_mode.set(mode)
        brightness = preset.get("brightness", 100)
        self.manual_brightness.set(brightness)
        if mode == "white":
            temp = preset.get("temp", 100)
            self.manual_temp.set(temp)
            rgb = None
        else:
            rgb = tuple(preset.get("rgb", (255, 255, 255)))
            temp = 100
            h, s, _ = colorsys.rgb_to_hsv(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
            self.manual_hue = h
            self.manual_sat = s
            self.color_wheel.set_color_hsv(h, s)
        self.update_manual_preview()
        self.bulb_controller.apply_manual_to_bulbs(target_ids, mode=mode, rgb=rgb, brightness=brightness, temp=temp)
        color_hex = preset_color_hex(preset)
        self.set_tray_icon_visual(color_hex=color_hex, cinema_mode=False, is_off=False)
        self.status.set(f"Preset '{preset.get('name')}' aplicado.")
        self.refresh_lamps_listbox_ui()

    def save_custom_preset(self):
        name = self.new_preset_entry.get().strip()
        if not name:
            name = f"Cor {len(self.custom_presets) + 1}"
        if self.manual_mode.get() == "white":
            preset = {"name": name, "mode": "white", "temp": round(self.manual_temp.get()), "brightness": round(self.manual_brightness.get())}
        else:
            preset = {"name": name, "mode": "colour", "rgb": list(self.get_current_manual_rgb()), "brightness": round(self.manual_brightness.get())}
        self.custom_presets.append(preset)
        self.new_preset_entry.delete(0, tk.END)
        self.save_settings()
        self.refresh_custom_presets_ui()
        self.status.set(f"Cor '{name}' salva nos presets.")

    def delete_custom_preset(self, index: int):
        if 0 <= index < len(self.custom_presets):
            removed = self.custom_presets.pop(index)
            self.save_settings()
            self.refresh_custom_presets_ui()
            self.status.set(f"Preset '{removed.get('name', '')}' excluído.")

    def refresh_custom_presets_ui(self):
        t = getattr(self, "current_theme", THEMES["dark"])
        if not hasattr(self, "custom_presets_frame"):
            return
        for child in self.custom_presets_frame.winfo_children():
            child.destroy()
        if not self.custom_presets:
            ttk.Label(self.custom_presets_frame, text="Nenhuma cor personalizada salva ainda.", style="Muted.TLabel").pack(anchor="w", pady=4)
            return
        for i, preset in enumerate(self.custom_presets):
            row = ttk.Frame(self.custom_presets_frame)
            row.pack(fill="x", pady=2)
            color_hex = preset_color_hex(preset)
            swatch = tk.Canvas(row, width=16, height=16, bg=color_hex, highlightthickness=1, highlightbackground=t["BORDER"])
            swatch.pack(side="left", padx=(2, 6))
            swatch.bind("<Button-1>", lambda _, p=preset: self.activate_preset(p))
            btn = ttk.Button(row, text=preset["name"], style="Preset.TButton", command=lambda p=preset: self.activate_preset(p))
            btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
            del_btn = ttk.Button(row, text="✕", width=3, command=lambda idx=i: self.delete_custom_preset(idx))
            del_btn.pack(side="left")

    def toggle_autostart(self):
        enabled = self.start_with_windows.get()
        set_autostart(enabled)
        self.save_settings()
        self.status.set("Inicialização com o Windows " + ("ativada." if enabled else "desativada."))

    def close_manual_bulb(self):
        self.bulb_controller.close_all()

    # ---------------------------------------------------------
    # Ciclo de Vida do Cinema Multi-Lâmpada
    # ---------------------------------------------------------
    def settings(self) -> Settings:
        return Settings(
            brightness=self.brightness.get() / 100,
            saturation=self.saturation.get() / 100,
            standout=self.standout.get() / 100,
            smoothing=self.smoothing.get(),
            interval=float(self.interval.get()),
            crop_percent=round(self.crop.get()),
            dark_percent=self.dark_percent.get(),
            off_on_neutral=self.off_on_neutral.get(),
            flash_boost=self.flash_boost.get(),
            light_mode=self.light_mode.get(),
        )

    def set_busy(self, value: bool, can_stop: bool = False):
        self.running = value
        for widget, normal in self.lockables:
            widget.configure(state="disabled" if value else normal)
        self.stop_button.configure(state="normal" if value and can_stop else "disabled")

    def launch(self, function, can_stop: bool = False) -> bool:
        if self.worker and self.worker.is_alive():
            return False
        self.stop_event.clear()
        self.set_busy(True, can_stop)

        def run():
            try:
                function()
            except BulbError as exc:
                self.events.put(("error", str(exc)))
            except Exception as e:
                self.events.put(("error", f"Falha na sincronização: {e}"))
            finally:
                self.events.put(("done", None))

        self.worker = threading.Thread(target=run, daemon=True)
        self.worker.start()
        return True

    def start(self, real: bool):
        if self.running:
            return
        if real:
            self.bulb_controller.skip_restore_on_stop = False
            self.set_tray_icon_visual(cinema_mode=True)

        try:
            settings = self.settings()
            index = self.monitor_box.current()
            if not 0 <= index < len(self.monitors):
                raise ValueError("Selecione uma tela disponível.")
            monitor = self.monitors[index].copy()
        except ValueError as exc:
            messagebox.showinfo("Antes de começar", str(exc))
            return

        self.status.set("Conectando às lâmpadas e iniciando Cinema Multi-Zona…" if real else "Iniciando prévia multi-zona…")

        def synchronize():
            from mss import MSS

            if real:
                successes = self.bulb_controller.connect_all_active()
                if not successes:
                    self.events.put(("status", "Aviso: Nenhuma lâmpada respondeu. Verifique na aba Cenários & Lâmpadas."))
                else:
                    self.events.put(("status", f"Cinema v2 ativo! Sincronizando {len(successes)} lâmpada(s) por zona. Minimize para assistir."))
            else:
                self.events.put(("status", "Prévia multi-zona ativa na tela. Nenhum comando enviado."))

            was_dark_map = {}
            required_zones = self.bulb_controller.get_required_zones() | {"left", "right", "top", "bottom", "center", "all"}
            previous = time.monotonic()

            with MSS() as capture:
                while not self.stop_event.is_set():
                    started = time.monotonic()
                    current_settings = self.settings()
                    shot = capture.grab(monitor)
                    frame = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

                    # Extrai e calcula a cor de cada setor da tela de forma ultrarrápida
                    zone_colors = compute_zones_colors(frame, current_settings, required_zones, was_dark_map)
                    for z, col in zone_colors.items():
                        was_dark_map[z] = max(col) == 0

                    if self.stop_event.is_set():
                        break

                    dt = started - previous
                    previous = started

                    if real:
                        self.bulb_controller.dispatch_cinema_frame(zone_colors, light_mode=current_settings.light_mode, dt=dt, smoothing=current_settings.smoothing)

                    self.events.put(("zones_colors", zone_colors))
                    self.stop_event.wait(max(0, current_settings.interval - (time.monotonic() - started)))

            if real:
                self.bulb_controller.restore_all()
                self.events.put(("status", "Sincronização de cinema encerrada. Lâmpadas restauradas."))
            else:
                self.events.put(("status", "Prévia encerrada."))

        self.launch(synchronize, can_stop=True)

    def stop(self, restore: bool = True):
        self.bulb_controller.skip_restore_on_stop = not restore
        self.stop_event.set()
        self.stop_button.configure(state="disabled")
        self.bulb_controller.stop_cinema()
        self.status.set("Parando e restaurando lâmpadas…" if restore else "Parando sincronização…")
        if not restore:
            self.running = False
        self.set_tray_icon_visual(color_hex="#9c8aff", cinema_mode=False, is_off=False)
        self.reset_zone_swatches()

    def reset_zone_swatches(self):
        t = getattr(self, "current_theme", THEMES["dark"])
        if hasattr(self, "zone_swatches"):
            for sw in self.zone_swatches.values():
                sw.configure(bg=t["PANEL"])

    def open_tuya_link(self):
        from vincular_tuya import LinkWindow
        popup = tk.Toplevel(self.root)
        LinkWindow(popup, "", "")

    def test_cloud(self):
        self.status.set("Testando sessão com a Tuya Cloud…")

        def _task():
            try:
                from tuya_cloud import CloudBulb
                b = CloudBulb()
                name = b.device.name
                b.close()
                self.events.put(("status", f"Conta autorizada com sucesso na Tuya! Lâmpada principal: {name}."))
            except Exception as e:
                self.events.put(("error", f"Falha no teste Tuya: {e}"))

        threading.Thread(target=_task, daemon=True).start()

    # ---------------------------------------------------------
    # Persistência de Dados (preferencias_v2.json)
    # ---------------------------------------------------------
    def save_settings(self):
        try:
            set_autostart(self.start_with_windows.get())
            settings = self.settings()
            devices_data = [d.to_dict() for d in self.bulb_controller.devices.values()]
            custom_scenarios = [s.to_dict() for s in self.scenarios if s.is_custom]

            data = {
                "version_app": "2.0",
                "devices": devices_data,
                "custom_scenarios": custom_scenarios,
                "brightness": settings.brightness * 100,
                "saturation": settings.saturation * 100,
                "standout": settings.standout * 100,
                "smoothing": settings.smoothing,
                "interval": float(settings.interval),
                "crop": settings.crop_percent,
                "dark_percent": settings.dark_percent,
                "off_on_neutral": settings.off_on_neutral,
                "flash_boost": settings.flash_boost,
                "light_mode": settings.light_mode,
                "monitor_index": self.monitor_box.current() if hasattr(self, "monitor_box") else 0,
                "custom_presets": self.custom_presets,
                "minimize_to_tray": self.minimize_to_tray.get(),
                "start_with_windows": self.start_with_windows.get(),
                "theme_mode": self.theme_mode.get(),
            }

            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            temporary = CONFIG.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(CONFIG)
            self.status.set("Preferências do Luz Cinema v2 salvas com sucesso.")
        except Exception as e:
            messagebox.showerror("Salvar", f"Não foi possível salvar as preferências: {e}")

    def load_settings(self):
        # Garante migração de tuya.enc da v1 se ainda não existir na v2
        v2_tuya = APP_DIR / "dados" / "tuya.enc"
        if not v2_tuya.exists():
            for cand in (APP_DIR.parent / "LuzCinema" / "dados" / "tuya.enc", APP_DIR / "tuya.enc"):
                if cand.exists():
                    import shutil
                    v2_tuya.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(cand, v2_tuya)
                    break

        # 1. Tenta carregar preferencias_v2.json
        if not CONFIG.exists():
            v1_config = APP_DIR.parent / "LuzCinema" / "dados" / "preferencias.json"
            if not v1_config.exists():
                v1_config = APP_DIR / "dados" / "preferencias.json"
            if v1_config.exists():
                self._migrate_v1_config(v1_config)
            return

        try:
            data = json.loads(CONFIG.read_text(encoding="utf-8"))
            raw_devs = data.get("devices", [])
            devs = [BulbDevice.from_dict(d) for d in raw_devs]
            # Se não houver lâmpadas salvas ainda mas tuya.enc existir, carrega do tuya.enc
            if not devs and v2_tuya.exists():
                try:
                    sess_raw = v2_tuya.read_text(encoding="ascii")
                    sess = json.loads(protect(sess_raw, decrypt=True))
                    did = sess.get("device_id", "")
                    binfo = sess.get("bulb", {})
                    if did:
                        devs.append(BulbDevice(
                            id=did,
                            name=binfo.get("name") or "Smart Color",
                            connection_type="cloud",
                            ip=binfo.get("ip", ""),
                            key=binfo.get("local_key", ""),
                            zone="all",
                        ))
                except Exception:
                    pass
            self.bulb_controller.update_devices(devs)

            raw_scs = data.get("custom_scenarios", [])
            custom_scs = [Scenario.from_dict(s) for s in raw_scs]
            self.scenarios = list(DEFAULT_SCENARIOS) + custom_scs

            self.brightness.set(float(data.get("brightness", 45)))
            self.saturation.set(float(data.get("saturation", 140)))
            self.standout.set(float(data.get("standout", 100)))
            self.smoothing.set(float(data.get("smoothing", 0.0)))
            self.interval.set(float(data.get("interval", 0.05)))
            self.crop.set(int(data.get("crop", 10)))
            self.dark_percent.set(float(data.get("dark_percent", 5)))
            self.off_on_neutral.set(bool(data.get("off_on_neutral", True)))
            self.flash_boost.set(bool(data.get("flash_boost", True)))
            self.light_mode.set(bool(data.get("light_mode", False)))
            self.saved_monitor = max(0, int(data.get("monitor_index", 0)))
            self.custom_presets = data.get("custom_presets", [])
            if "minimize_to_tray" in data:
                self.minimize_to_tray.set(bool(data["minimize_to_tray"]))
            if "start_with_windows" in data:
                self.start_with_windows.set(bool(data["start_with_windows"]))
            if "theme_mode" in data and data["theme_mode"] in THEMES:
                self.theme_mode.set(data["theme_mode"])
        except Exception as e:
            self.status.set(f"Aviso ao ler preferências: {e}")

    def _migrate_v1_config(self, v1_path: Path):
        """Importa lâmpada e configurações da v1 de forma transparente."""
        try:
            d = json.loads(v1_path.read_text(encoding="utf-8"))
            did = d.get("id", "")
            v2_tuya = APP_DIR / "dados" / "tuya.enc"
            if not did and v2_tuya.exists():
                try:
                    sess_raw = v2_tuya.read_text(encoding="ascii")
                    sess = json.loads(protect(sess_raw, decrypt=True))
                    did = sess.get("device_id", "")
                    binfo = sess.get("bulb", {})
                    name = binfo.get("name") or "Smart Color"
                    if did:
                        dev = BulbDevice(
                            id=did,
                            name=name,
                            connection_type="cloud",
                            ip=binfo.get("ip", ""),
                            key=binfo.get("local_key", ""),
                            zone="all",
                        )
                        self.bulb_controller.devices[did] = dev
                except Exception:
                    pass
            elif did:
                key = ""
                if d.get("protected_key"):
                    try:
                        key = protect(d["protected_key"], decrypt=True)
                    except Exception:
                        pass
                dev = BulbDevice(
                    id=did,
                    name="Lâmpada Principal",
                    connection_type="local" if d.get("ip") else "cloud",
                    ip=d.get("ip", ""),
                    key=key,
                    zone="all",
                )
                self.bulb_controller.devices[did] = dev
            self.brightness.set(float(d.get("brightness", 45)))
            self.saturation.set(float(d.get("saturation", 140)))
            self.save_settings()
        except Exception:
            pass

    # ---------------------------------------------------------
    # Processamento de Eventos (drain)
    # ---------------------------------------------------------
    def drain(self):
        if not self.alive:
            return
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind in ("status", "error"):
                self.status.set(value)
            elif kind == "zones_colors":
                # Atualiza as cores das mini-zonas de prévia
                if hasattr(self, "zone_swatches"):
                    for z, col in value.items():
                        if z in self.zone_swatches:
                            self.zone_swatches[z].configure(bg=rgb_to_hex(col))
            elif kind == "bulbs_imported":
                self.status.set(f"{value} lâmpada(s) adicionada(s) com sucesso!")
                self.save_settings()
                self.refresh_lamps_listbox_ui()
                self.refresh_cinema_lamps_ui()
                self.update_manual_target_choices()
                self.update_tray_menu()
            elif kind == "done":
                self.set_busy(False)
                if self.closing:
                    self.alive = False
                    self.root.destroy()
                    return

        wake_evt = get_wake_event()
        if wake_evt and os.name == "nt":
            try:
                if ctypes.windll.kernel32.WaitForSingleObject(wake_evt, 0) == 0:
                    self._show_window()
            except Exception:
                pass

        if self.closing and (not self.worker or not self.worker.is_alive()):
            self.alive = False
            try:
                self.root.update_idletasks()
            except Exception:
                pass
            try:
                self.root.destroy()
            except Exception:
                pass
            return

        self.timer = self.root.after(100, self.drain)

    def close(self):
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.bulb_controller.close_all()
        if self.worker and self.worker.is_alive():
            self.closing = True
            self.stop()
        else:
            self.alive = False
            try:
                self.root.after_cancel(self.timer)
            except Exception:
                pass
            try:
                self.root.update_idletasks()
            except Exception:
                pass
            try:
                self.root.destroy()
            except Exception:
                pass


def main():
    os.chdir(APP_DIR)
    if not check_single_instance():
        sys.exit(0)
    setup_windows_dpi_and_app_id()
    if "--export-icon" in sys.argv:
        export_ico(APP_DIR / "luzcinema.ico")
        return
    root = tk.Tk()
    is_minimized = "--tray" in sys.argv or "--minimized" in sys.argv
    if is_minimized:
        root.withdraw()
    app = App(root)
    if is_minimized:
        if app.tray_icon:
            def _notify():
                try:
                    if getattr(app.tray_icon, "HAS_NOTIFICATION", False):
                        app.tray_icon.notify("Luz Cinema v2 está ativo na bandeja do sistema.", "Luz Cinema v2")
                except Exception:
                    pass
            root.after(600, _notify)
        else:
            root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()

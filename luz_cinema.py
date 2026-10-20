"""Luz Cinema — Interface gráfica para sincronização de tela com lâmpadas inteligentes Tuya."""
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
)

# Módulos especializados
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
    """Controlador principal do aplicativo Luz Cinema."""

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Luz Cinema")
        root.geometry("860x940")
        root.minsize(800, 840)

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
        self.found = []
        self.lockables = []
        self.default_preset_swatches = []

        # Variáveis reativas de Cinema
        self.status = tk.StringVar(value="Pronto para testar a prévia. Lâmpada ainda não conectada.")
        self.monitor = tk.StringVar()
        self.brightness = tk.DoubleVar(value=45)
        self.saturation = tk.DoubleVar(value=140)
        self.standout = tk.DoubleVar(value=100)
        self.smoothing = tk.DoubleVar(value=0.1)
        self.interval = tk.StringVar(value="0.25")
        self.crop = tk.DoubleVar(value=10)
        self.dark_percent = tk.DoubleVar(value=5)
        self.off_on_neutral = tk.BooleanVar(value=True)
        self.flash_boost = tk.BooleanVar(value=True)
        self.light_mode = tk.BooleanVar(value=False)
        self.saved_monitor = 0

        # Variáveis reativas de Conexão
        self.device_id = tk.StringVar()
        self.ip = tk.StringVar()
        self.key = tk.StringVar()
        self.version = tk.StringVar(value="3.3")
        self.connection_mode = tk.StringVar(value="Conta Tuya" if (APP_DIR / "dados" / "tuya.enc").exists() else "Rede local")
        self.remember = tk.BooleanVar(value=False)

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

        # Fila de comandos manuais para conexão persistente
        self.manual_queue = queue.Queue(maxsize=1)
        self.manual_thread = None
        self.manual_worker_stop = threading.Event()
        self.cached_manual_bulb = None
        self.cached_bulb_key = None

        # Carrega configurações e inicializa tema
        self.load_settings()
        self.apply_theme()

        # Configuração do ícone da janela
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
        ttk.Label(header_text, text="Luz Cinema", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header_text, text="As cores do filme iluminam o seu quarto.", style="Muted.TLabel").pack(anchor="w")

        header_right = ttk.Frame(header)
        header_right.pack(side="right", anchor="e", pady=(4, 0))
        toggle_label = self.current_theme["toggle_label"]
        self.theme_toggle_btn = ttk.Button(header_right, text=toggle_label, style="ThemeToggle.TButton", command=self.toggle_theme)
        self.theme_toggle_btn.pack(side="right")

        # Abas
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=26)
        cinema = ttk.Frame(self.tabs, padding=20)
        presets_tab = ttk.Frame(self.tabs, padding=20)
        connect_tab = ttk.Frame(self.tabs, padding=20)
        self.tabs.add(cinema, text="  Cinema  ")
        self.tabs.add(presets_tab, text="  Presets & Cores  ")
        self.tabs.add(connect_tab, text="  Conectar  ")

        self.build_cinema(cinema)
        self.build_presets(presets_tab)
        self.build_connection(connect_tab)
        self.setup_tray()

        # Barra inferior de status
        bottom_bar = ttk.Frame(root, style="Status.TFrame")
        bottom_bar.pack(side="bottom", fill="x", before=self.tabs)
        self.status_label = ttk.Label(bottom_bar, textvariable=self.status, wraplength=620, style="Status.TLabel", padding=(26, 12))
        self.status_label.pack(side="left", fill="x", expand=True)

        t = self.current_theme
        self.help_link = tk.Label(bottom_bar, text="Como conectar ↗", bg=t["STATUS_BG"], fg=t["MUTED"], font=("Segoe UI", 9, "underline"), cursor="hand2")
        self.help_link.pack(side="right", padx=(10, 26))
        self.help_link.bind("<Button-1>", lambda _: self.open_help_popup())
        self.help_link.bind("<Enter>", lambda _: self.help_link.configure(fg=self.current_theme["FG"]))
        self.help_link.bind("<Leave>", lambda _: self.help_link.configure(fg=self.current_theme["MUTED"]))

        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)
        self.timer = self.root.after(100, self.drain)

    # ---------------------------------------------------------
    # Manipulação de Cor Manual e Presets
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

    def apply_current_manual(self):
        mode = self.manual_mode.get()
        rgb = self.get_current_manual_rgb()
        brightness = round(self.manual_brightness.get())
        temp = round(self.manual_temp.get())
        self.apply_manual_light(mode, rgb=rgb, brightness=brightness, temp=temp)
        color_hex = rgb_to_hex(rgb)
        self.set_tray_icon_visual(color_hex=color_hex, cinema_mode=False, is_off=False)

    def turn_off_light(self):
        if self.running:
            self.stop(restore=False)
            if self.worker and self.worker.is_alive():
                self.worker.join(timeout=0.3)
        self.apply_manual_light("off")
        self.set_tray_icon_visual(is_off=True)
        if hasattr(self, "manual_swatch"):
            self.manual_swatch.configure(bg="#111827")
            self.manual_swatch_label.configure(text="LÂMPADA APAGADA")
        self.status.set("Lâmpada apagada.")

    def activate_preset(self, preset: dict):
        if self.running:
            self.stop(restore=False)
            if self.worker and self.worker.is_alive():
                self.worker.join(timeout=0.3)
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
        self.apply_manual_light(mode, rgb=rgb, brightness=brightness, temp=temp)
        color_hex = preset_color_hex(preset)
        self.set_tray_icon_visual(color_hex=color_hex, cinema_mode=False, is_off=False)

    def apply_manual_light(self, mode: str, rgb=None, brightness=100, temp=100):
        if self.running:
            self.status.set("Sincronização de cinema em andamento. Pare antes de aplicar manualmente.")
            return

        cloud = self.connection_mode.get() == "Conta Tuya"
        credentials = self.credentials()
        key = ("cloud",) if cloud else ("local", credentials)

        try:
            self.manual_queue.get_nowait()
        except queue.Empty:
            pass

        self.manual_queue.put((key, mode, rgb, brightness, temp))

        if self.manual_thread is None or not self.manual_thread.is_alive():
            self.manual_worker_stop.clear()
            self.manual_thread = threading.Thread(target=self._manual_worker_loop, daemon=True)
            self.manual_thread.start()

    def _manual_worker_loop(self):
        while not self.manual_worker_stop.is_set():
            try:
                item = self.manual_queue.get(timeout=25.0)
            except queue.Empty:
                self.close_manual_bulb()
                break

            key, mode, rgb, brightness, temp = item
            if self.cached_manual_bulb is None or self.cached_bulb_key != key:
                self.close_manual_bulb()
                try:
                    if key[0] == "cloud":
                        from tuya_cloud import CloudBulb
                        self.cached_manual_bulb = CloudBulb()
                    else:
                        self.cached_manual_bulb = LocalBulb(*key[1])
                    self.cached_bulb_key = key
                except Exception as exc:
                    self.events.put(("status", f"Não foi possível conectar: {exc}"))
                    self.close_manual_bulb()
                    continue

            try:
                self.cached_manual_bulb.set_manual(mode, rgb=rgb, brightness=brightness, temp=temp)
                self.events.put(("status", "Cor aplicada à lâmpada."))
            except Exception as exc:
                self.events.put(("status", f"Falha ao enviar comando: {exc}"))
                self.close_manual_bulb()

    def close_manual_bulb(self):
        if self.cached_manual_bulb:
            try:
                self.cached_manual_bulb.close()
            except Exception:
                pass
            self.cached_manual_bulb = None
            self.cached_bulb_key = None

    def save_custom_preset(self):
        name = self.new_preset_entry.get().strip()
        if not name:
            name = f"Preset {len(self.custom_presets) + 1}"
        if self.manual_mode.get() == "white":
            preset = {
                "name": name,
                "mode": "white",
                "temp": round(self.manual_temp.get()),
                "brightness": round(self.manual_brightness.get()),
            }
        else:
            preset = {
                "name": name,
                "mode": "colour",
                "rgb": list(self.get_current_manual_rgb()),
                "brightness": round(self.manual_brightness.get()),
            }
        self.custom_presets.append(preset)
        self.new_preset_entry.delete(0, tk.END)
        self.save_settings()
        self.refresh_custom_presets_ui()
        self.status.set(f"Preset '{name}' salvo.")

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
            ttk.Label(self.custom_presets_frame, text="Nenhum preset personalizado salvo ainda.", style="Muted.TLabel").pack(anchor="w", pady=4)
            self.update_tray_menu()
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
        self.update_tray_menu()

    def toggle_autostart(self):
        enabled = self.start_with_windows.get()
        set_autostart(enabled)
        self.save_settings()
        self.status.set("Inicialização com o Windows " + ("ativada." if enabled else "desativada."))

    # ---------------------------------------------------------
    # Parâmetros e Credenciais
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

    def credentials(self) -> tuple[str, str, str, str]:
        return self.device_id.get(), self.ip.get(), self.key.get(), self.version.get()

    def set_busy(self, value: bool, can_stop: bool = False):
        self.running = value
        for widget, normal in self.lockables:
            widget.configure(state="disabled" if value else normal)
        self.stop_button.configure(state="normal" if value and can_stop else "disabled")

    # ---------------------------------------------------------
    # Ciclo de Vida da Thread de Sincronização
    # ---------------------------------------------------------
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
            except Exception:
                self.events.put(("error", "Não foi possível concluir. Confira a rede, o IP, a chave e o protocolo. Se for a prévia, verifique a tela selecionada."))
            finally:
                self.events.put(("done", None))

        self.worker = threading.Thread(target=run, daemon=True)
        self.worker.start()
        return True

    def start(self, real: bool):
        if self.running:
            return
        if real:
            self.skip_restore_on_stop = False
            self.close_manual_bulb()
            self.manual_worker_stop.set()
            self.set_tray_icon_visual(cinema_mode=True)
        try:
            settings = self.settings()
            index = self.monitor_box.current()
            if not 0 <= index < len(self.monitors):
                raise ValueError("Selecione uma tela disponível.")
            monitor = self.monitors[index].copy()
            credentials = self.credentials()
            cloud = real and self.connection_mode.get() == "Conta Tuya"
            if cloud:
                settings = replace(settings, interval=max(0.25, settings.interval))
            if real and not cloud and not all(credentials):
                self.tabs.select(2)
                raise ValueError("Preencha os dados na aba Conectar e teste a conexão primeiro.")
        except ValueError as exc:
            messagebox.showinfo("Antes de começar", str(exc))
            return

        self.status.set("Conectando à lâmpada…" if real else "Iniciando prévia…")

        def synchronize():
            from mss import MSS

            bulb = None
            failed = False
            try:
                if real:
                    if cloud:
                        from tuya_cloud import CloudBulb
                        bulb = CloudBulb()
                    else:
                        bulb = LocalBulb(*credentials)
                self.events.put(("status", (f"Sincronizando pela Tuya · intervalo {settings.interval:g} s. Minimize para assistir." if cloud else "Sincronizando a lâmpada. Minimize a janela para assistir.") if real else "Prévia ativa. Nenhum comando enviado à lâmpada."))
                smoother = Smoother()
                was_dark = False
                last_rgb, last_send = None, 0
                previous = time.monotonic()
                with MSS() as capture:
                    while not self.stop_event.is_set():
                        started = time.monotonic()
                        shot = capture.grab(monitor)
                        frame = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                        target = screen_color(frame, settings, was_dark=was_dark)
                        was_dark = max(target) == 0
                        rgb = smoother.update(target, started - previous, settings.smoothing)
                        previous = started
                        if self.stop_event.is_set():
                            break
                        if bulb and should_send(last_rgb, rgb, started - last_send):
                            bulb.color(rgb, light_mode=settings.light_mode)
                            last_rgb, last_send = rgb, started
                            if cloud:
                                ack = f"{bulb.last_ack_ms} ms" if bulb.last_ack_ms is not None else "aguardando comando"
                                self.events.put(("status", f"Sincronizando · intervalo {settings.interval:g} s · última confirmação Tuya: {ack} · " + ("luz apagada" if max(rgb) <= 2 else "cor ativa")))
                        self.events.put(("color", rgb))
                        self.stop_event.wait(max(0, settings.interval - (time.monotonic() - started)))
            except Exception:
                failed = True
                raise
            finally:
                restored = True
                if bulb:
                    try:
                        if not getattr(self, "skip_restore_on_stop", False):
                            bulb.restore()
                    except Exception:
                        restored = False
                    finally:
                        bulb.close()
                if not restored:
                    raise BulbError("A conexão falhou ao restaurar a luz. Ajuste a lâmpada pelo Elgin Smart.")
                elif not failed:
                    msg = "Parado. Estado anterior da lâmpada restaurado." if bulb and not getattr(self, "skip_restore_on_stop", False) else "Sincronização encerrada." if bulb else "Prévia encerrada."
                    self.events.put(("status", msg))

        self.launch(synchronize, can_stop=True)

    def stop(self, restore: bool = True):
        self.skip_restore_on_stop = not restore
        self.stop_event.set()
        self.stop_button.configure(state="disabled")
        self.status.set("Parando e, se conectada, restaurando a lâmpada…" if restore else "Parando sincronização…")
        if not restore:
            self.running = False
        self.set_tray_icon_visual(color_hex="#9c8aff", cinema_mode=False, is_off=False)
        t = getattr(self, "current_theme", THEMES["dark"])
        if hasattr(self, "swatch"):
            self.swatch.configure(bg=t["PANEL"])
            self.swatch.itemconfigure(self.swatch_label, text="Sua prévia de cor aparece aqui", fill=t["FG"])

    def test_connection(self):
        credentials = self.credentials()
        self.status.set("Testando leitura da lâmpada, sem mudar a cor…")

        def test():
            bulb = LocalBulb(*credentials)
            bulb.close()
            self.events.put(("status", "Conexão RGB local confirmada. Volte a Cinema e clique Sincronizar lâmpada."))

        self.launch(test)

    def scan(self):
        self.status.set("Buscando anúncios locais de dispositivos por cerca de 12 segundos…")

        def search():
            import tinytuya
            devices = tinytuya.deviceScan(verbose=False, maxretry=12, poll=False, forcescan=False)
            items = []
            for ip, device in devices.items():
                device_id = device.get("gwId") or device.get("id")
                if device_id:
                    items.append({"ip": device.get("ip", ip), "id": device_id,
                                  "version": str(device.get("version", "3.3")), "name": "Dispositivo local"})
            self.events.put(("devices", items))
            self.events.put(("status", f"{len(items)} dispositivo(s) encontrado(s). Selecione sua lâmpada." if items else "Nenhum anúncio encontrado. Confira se PC e lâmpada estão na mesma rede; você também pode preencher o IP manualmente."))

        self.launch(search)

    def import_devices(self):
        filename = filedialog.askopenfilename(title="Importar devices.json do TinyTuya", filetypes=[("Arquivo JSON", "*.json")])
        if not filename:
            return
        try:
            if Path(filename).stat().st_size > 2_000_000:
                raise ValueError()
            devices = json.loads(Path(filename).read_text(encoding="utf-8-sig"))
            if not isinstance(devices, list):
                raise ValueError()
            self.found = [{k: str(d.get(k, "")) for k in ("id", "ip", "key", "name", "version")}
                          for d in devices if isinstance(d, dict) and d.get("id")]
            self.show_devices()
            self.status.set("Importado. Selecione sua lâmpada na lista; preencha o IP se estiver vazio.")
        except (ValueError, OSError, TypeError):
            messagebox.showerror("Importação", "Escolha um devices.json válido gerado pelo TinyTuya.")

    def show_devices(self):
        self.device_list.delete(0, "end")
        for item in self.found:
            self.device_list.insert("end", f"{item.get('name') or 'Dispositivo'}   ·   {item.get('ip') or 'IP não informado'}   ·   {item['id']}")

    def select_device(self, _):
        if self.running:
            return
        selection = self.device_list.curselection()
        if not selection:
            return
        item = self.found[selection[0]]
        same_device = item["id"] == self.device_id.get()
        previous_ip, previous_key = self.ip.get(), self.key.get()
        self.device_id.set(item["id"])
        self.ip.set(item.get("ip") or (previous_ip if same_device else ""))
        self.key.set(item.get("key") or (previous_key if same_device else ""))
        if item.get("version") in ("3.1", "3.2", "3.3", "3.4", "3.5"):
            self.version.set(item["version"])

    def save_settings(self):
        try:
            set_autostart(self.start_with_windows.get())
            settings = self.settings()
            data = {
                "ip": self.ip.get(),
                "id": self.device_id.get(),
                "version": self.version.get(),
                "brightness": settings.brightness * 100,
                "saturation": settings.saturation * 100,
                "standout": settings.standout * 100,
                "smoothing": settings.smoothing,
                "interval": str(settings.interval),
                "crop": settings.crop_percent,
                "dark_percent": settings.dark_percent,
                "off_on_neutral": settings.off_on_neutral,
                "flash_boost": settings.flash_boost,
                "light_mode": settings.light_mode,
                "monitor_index": self.monitor_box.current(),
                "custom_presets": self.custom_presets,
                "minimize_to_tray": self.minimize_to_tray.get(),
                "start_with_windows": self.start_with_windows.get(),
                "theme_mode": self.theme_mode.get(),
            }
            if self.remember.get() and self.key.get():
                data["protected_key"] = protect(self.key.get())
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            temporary = CONFIG.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(CONFIG)
            self.status.set("Preferências salvas. A chave foi protegida neste Windows." if "protected_key" in data else "Preferências salvas sem guardar a chave local.")
        except Exception:
            messagebox.showerror("Salvar", "Não foi possível salvar as preferências nesta pasta.")

    def load_settings(self):
        if not CONFIG.exists():
            return
        try:
            data = json.loads(CONFIG.read_text(encoding="utf-8"))
            checked = Settings(
                brightness=float(data.get("brightness", 45)) / 100,
                saturation=float(data.get("saturation", 140)) / 100,
                standout=float(data.get("standout", 100)) / 100,
                smoothing=float(data.get("smoothing", 0.1)),
                interval=float(data.get("interval", 0.25)),
                crop_percent=int(data.get("crop", 10)),
                dark_percent=float(data.get("dark_percent", 5)),
                off_on_neutral=bool(data.get("off_on_neutral", True)),
                flash_boost=bool(data.get("flash_boost", True)),
                light_mode=bool(data.get("light_mode", False)),
            )
            self.ip.set(data.get("ip", ""))
            self.device_id.set(data.get("id", ""))
            self.version.set(data.get("version", "3.3"))
            self.brightness.set(checked.brightness * 100)
            self.saturation.set(checked.saturation * 100)
            self.standout.set(checked.standout * 100)
            self.smoothing.set(checked.smoothing)
            self.interval.set(str(checked.interval))
            self.crop.set(checked.crop_percent)
            self.dark_percent.set(checked.dark_percent)
            self.off_on_neutral.set(checked.off_on_neutral)
            self.flash_boost.set(checked.flash_boost)
            self.light_mode.set(checked.light_mode)
            self.saved_monitor = max(0, int(data.get("monitor_index", 0)))
            self.custom_presets = data.get("custom_presets", [])
            if "minimize_to_tray" in data:
                self.minimize_to_tray.set(bool(data["minimize_to_tray"]))
            if "start_with_windows" in data:
                should_autostart = bool(data["start_with_windows"])
                self.start_with_windows.set(should_autostart)
                set_autostart(should_autostart)
            else:
                self.start_with_windows.set(is_autostart_enabled())
            if "theme_mode" in data and data["theme_mode"] in THEMES:
                self.theme_mode.set(data["theme_mode"])
            if data.get("protected_key"):
                self.key.set(protect(data["protected_key"], decrypt=True))
                self.remember.set(True)
        except Exception:
            self.status.set("Preferências antigas não puderam ser lidas. Preencha os dados novamente.")

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
            elif kind == "color":
                color = "#%02x%02x%02x" % value
                self.swatch.configure(bg=color)
                self.swatch.itemconfigure(self.swatch_label, text=color.upper(), fill="#111111" if sum(value) > 420 else "#ffffff")
            elif kind == "devices":
                self.found = value
                self.show_devices()
            elif kind == "cloud_status":
                self.cloud_state.set(value)
            elif kind == "done":
                self.set_busy(False)
                if self.closing:
                    if "restaurar" in self.status.get() and "falhou" in self.status.get():
                        messagebox.showwarning("Lâmpada", self.status.get())
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
                        app.tray_icon.notify("Luz Cinema está em execução na bandeja do sistema.", "Luz Cinema")
                except Exception:
                    pass
            root.after(600, _notify)
        else:
            root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()

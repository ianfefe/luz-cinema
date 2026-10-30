"""Janela principal do Luz Cinema.

Com uma lâmpada a interface fica enxuta; zonas, alvo do controle manual e chips por
lâmpada só aparecem quando há duas ou mais configuradas.
"""
from __future__ import annotations

import colorsys
import logging
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from .. import __version__
from .. import storage
from ..core import (BulbError, Settings, cct_to_rgb, compute_zones_colors, downscale_frame, rgb_to_hex)
from ..devices import BulbController, BulbDevice, friendly_error
from ..presets import preset_color_hex
from ..scenarios import DEFAULT_SCENARIOS, Scenario
from ..windows import (is_autostart_enabled, set_autostart, take_over_legacy_autostart, wake_requested)
from .icons import get_icon_file, render_icon
from .theme import Theme
from .tray import Tray

log = logging.getLogger(__name__)

CINEMA_FIELDS = ("brightness", "saturation", "standout", "smoothing", "interval", "crop",
                 "dark_percent", "off_on_neutral", "flash_boost", "light_mode")
FRAME_UI_INTERVAL = 0.06  # atualiza a prévia na janela no máximo ~16x por segundo
ALL_ZONES = {"all", "left", "right", "top", "bottom", "center"}


class App:
    def __init__(self, root: tk.Tk, data_dir=None):
        self.root = root
        self.data_dir = data_dir
        self.events: queue.Queue = queue.Queue()
        self.alive = True
        self.closing = False
        self.worker: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.running = False          # sincronização (ou prévia) em andamento
        self.previewing = False       # prévia: captura sem enviar às lâmpadas
        self._restore_on_stop = True
        self._after_stop: list = []
        self._save_job = None
        self._live_job = None
        self._applying_profile = False
        self._error_shown: dict[str, float] = {}
        self.lamp_colors: dict[str, tuple[int, int, int]] = {}
        self.monitors: list[dict] = []

        config, migrated = storage.load(data_dir)
        self.theme = Theme(root, config["theme_mode"])
        self.controller = BulbController(config["devices"], on_event=lambda k, p: self.events.put(("bulb", (k, p))))
        self.custom_presets: list[dict] = config["custom_presets"]
        self.scenarios: list[Scenario] = list(DEFAULT_SCENARIOS) + [
            Scenario.from_dict(s) for s in config["custom_scenarios"] if isinstance(s, dict)]

        # Variáveis do modo cinema
        self.vars = {
            "brightness": tk.DoubleVar(value=config["brightness"]),
            "saturation": tk.DoubleVar(value=config["saturation"]),
            "standout": tk.DoubleVar(value=config["standout"]),
            "smoothing": tk.DoubleVar(value=config["smoothing"]),
            "interval": tk.DoubleVar(value=config["interval"]),
            "crop": tk.DoubleVar(value=config["crop"]),
            "dark_percent": tk.DoubleVar(value=config["dark_percent"]),
            "off_on_neutral": tk.BooleanVar(value=config["off_on_neutral"]),
            "flash_boost": tk.BooleanVar(value=config["flash_boost"]),
            "light_mode": tk.BooleanVar(value=config["light_mode"]),
        }
        self.profile = tk.StringVar(value=config["profile"])
        self.monitor_index = int(config["monitor_index"]) if str(config["monitor_index"]).lstrip("-").isdigit() else 0
        self.settings_snapshot = self._read_settings()

        # Controle manual
        self.manual_mode = tk.StringVar(value="colour")
        self.manual_hue, self.manual_sat = 0.75, 0.85
        self.manual_brightness = tk.DoubleVar(value=100)
        self.manual_temp = tk.DoubleVar(value=50)
        self.live_manual = tk.BooleanVar(value=config["live_manual"])
        self.manual_target = tk.StringVar(value=config["manual_target"])

        # Sistema
        self.minimize_to_tray = tk.BooleanVar(value=config["minimize_to_tray"])
        if migrated:
            take_over_legacy_autostart()
        self.start_with_windows = tk.BooleanVar(value=is_autostart_enabled())
        self.status_text = tk.StringVar()
        self.cinema_state = tk.StringVar()

        self._setup_window()
        self.theme.apply()
        self._detect_monitors()
        self._build_layout()
        self.tray = Tray(self)
        self.tray.start()

        for name, var in self.vars.items():
            var.trace_add("write", lambda *_: self._on_cinema_setting_changed())
        self.live_manual.trace_add("write", lambda *_: self.schedule_save())
        self.minimize_to_tray.trace_add("write", lambda *_: self.schedule_save())

        if migrated:
            self.schedule_save()
            self.set_status("Preferências da versão anterior importadas. Sua chave local agora fica protegida pelo Windows.", "ok")
        elif not self.controller.device_list():
            self.set_status("Bem-vindo! Comece conectando sua lâmpada.")
            self.show_page("lamps")
        else:
            self.set_status("Pronto. Escolha uma cor, um cenário ou inicie o modo cinema.")
        self._update_cinema_state()
        root.protocol("WM_DELETE_WINDOW", self.on_window_close)
        self._timer = root.after(50, self.drain)

    # ================================================================== janela e layout
    def _setup_window(self):
        root = self.root
        root.title("Luz Cinema")
        scale = max(1.0, root.winfo_fpixels("1i") / 96.0)
        w, h = round(1000 * scale), round(720 * scale)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = min(w, sw - 40), min(h, sh - 80)
        root.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 3)}")
        root.minsize(min(round(820 * scale), w), min(round(560 * scale), h))

        ico = get_icon_file()
        base = render_icon(size=256)
        if ico:
            try:
                with Image.open(ico) as image:
                    base = image.copy()
            except OSError:
                pass
        self.app_icons = [ImageTk.PhotoImage(base.resize((n, n), Image.LANCZOS), master=root) for n in (256, 64, 48, 32, 16)]
        root.iconphoto(True, *self.app_icons)
        if ico:
            try:
                root.iconbitmap(str(ico))
            except tk.TclError:
                pass
        self.logo = ImageTk.PhotoImage(base.resize((34, 34), Image.LANCZOS), master=root)
        for i, page in enumerate(("cinema", "colors", "scenes", "lamps", "settings"), start=1):
            root.bind_all(f"<Control-Key-{i}>", lambda _, p=page: self.show_page(p))
        root.bind_all("<F5>", lambda _: self.toggle_cinema())
        root.bind_all("<MouseWheel>", self._on_mousewheel)

    def _build_layout(self):
        from .pages import PAGES

        self.sidebar = ttk.Frame(self.root, style="Sidebar.TFrame", padding=(14, 18, 14, 14))
        self.sidebar.pack(side="left", fill="y")
        brand = ttk.Frame(self.sidebar, style="Sidebar.TFrame")
        brand.pack(fill="x", pady=(0, 22))
        tk_logo = tk.Label(brand, image=self.logo, borderwidth=0)
        tk_logo.pack(side="left", padx=(2, 10))
        self.theme.bind(lambda t: tk_logo.configure(bg=t["SURFACE"]))
        ttk.Label(brand, text="Luz Cinema", style="Brand.TLabel").pack(side="left")

        self.nav_buttons: dict[str, ttk.Button] = {}
        self.pages = {}
        self.content = ttk.Frame(self.root)
        self.status_bar = ttk.Frame(self.root, style="Sidebar.TFrame", padding=(20, 8))
        self.status_bar.pack(side="bottom", fill="x")
        self.status_label = ttk.Label(self.status_bar, textvariable=self.status_text, style="Status.TLabel")
        self.status_label.pack(side="left", fill="x", expand=True)
        ttk.Label(self.status_bar, textvariable=self.cinema_state, style="Status.TLabel").pack(side="right")
        self.content.pack(side="left", fill="both", expand=True)

        for key, label, page_cls in PAGES:
            button = ttk.Button(self.sidebar, text=label, style="Nav.TButton", command=lambda k=key: self.show_page(k))
            button.pack(fill="x", pady=2)
            self.nav_buttons[key] = button
            self.pages[key] = page_cls(self, self.content)

        bottom = ttk.Frame(self.sidebar, style="Sidebar.TFrame")
        bottom.pack(side="bottom", fill="x")
        ttk.Label(bottom, text=f"v{__version__}", style="SidebarMuted.TLabel").pack(side="bottom", anchor="w", pady=(10, 0))
        ttk.Button(bottom, text="⏻  Apagar tudo", style="Sidebar.TButton", command=self.turn_off_all).pack(fill="x", pady=1)
        self.theme_button = ttk.Button(bottom, style="Sidebar.TButton", command=self.toggle_theme)
        self.theme_button.pack(fill="x", pady=1)
        self.theme.bind(lambda t: self.theme_button.configure(text="☀  Tema claro" if t["name"] == "dark" else "🌙  Tema escuro"))

        self.current_page = None
        self.show_page("cinema")

    def show_page(self, key: str):
        if key not in self.pages or key == self.current_page:
            return
        if self.current_page:
            self.pages[self.current_page].pack_forget()
            self.nav_buttons[self.current_page].configure(style="Nav.TButton")
        self.current_page = key
        self.pages[key].pack(fill="both", expand=True)
        self.nav_buttons[key].configure(style="NavActive.TButton")
        if hasattr(self.pages[key], "on_show"):
            self.pages[key].on_show()

    def _on_mousewheel(self, event):
        page = self.pages.get(self.current_page)
        try:
            if page is not None and str(event.widget).startswith(str(page)):
                page.scroll(event)
        except (tk.TclError, AttributeError):
            pass

    def toggle_theme(self):
        self.theme.set_mode("light" if self.theme.mode == "dark" else "dark")
        self.schedule_save()

    def set_status(self, text: str, level: str = "info"):
        self.status_text.set(text)
        style = {"error": "StatusError.TLabel", "ok": "StatusOk.TLabel"}.get(level, "Status.TLabel")
        if hasattr(self, "status_label"):
            self.status_label.configure(style=style)

    def _update_cinema_state(self):
        if self.running:
            text = "● Prévia na janela" if self.previewing else "● Sincronizando com a tela"
        else:
            active = self.controller.active_devices()
            if not active:
                text = "Nenhuma lâmpada configurada"
            elif len(active) == 1:
                text = f"Lâmpada: {active[0].name}"
            else:
                text = f"{len(active)} lâmpadas ativas"
        self.cinema_state.set(text)
        for page in self.pages.values():
            if hasattr(page, "on_running_changed"):
                page.on_running_changed()

    # ================================================================== monitores
    def _detect_monitors(self):
        try:
            from mss import MSS
            with MSS() as capture:
                self.monitors = [dict(m) for m in capture.monitors[1:]]
        except Exception:
            self.monitors = []
        if not 0 <= self.monitor_index < len(self.monitors):
            self.monitor_index = 0

    def monitor_labels(self) -> list[str]:
        return [f"Monitor {i + 1}  ·  {m['width']} × {m['height']}" for i, m in enumerate(self.monitors)]

    def set_monitor(self, index: int):
        if 0 <= index < len(self.monitors) and index != self.monitor_index:
            self.monitor_index = index
            self.schedule_save()

    # ================================================================== ajustes do cinema
    def _read_settings(self) -> Settings:
        v = {k: var.get() for k, var in self.vars.items()}
        return Settings.clamped(
            brightness=v["brightness"] / 100, saturation=v["saturation"] / 100, standout=v["standout"] / 100,
            smoothing=v["smoothing"], interval=v["interval"], crop_percent=v["crop"],
            dark_percent=v["dark_percent"], off_on_neutral=bool(v["off_on_neutral"]),
            flash_boost=bool(v["flash_boost"]), light_mode=bool(v["light_mode"]))

    def _on_cinema_setting_changed(self):
        try:
            self.settings_snapshot = self._read_settings()
        except (tk.TclError, ValueError):
            return
        if not self._applying_profile and self.profile.get():
            self.profile.set("")
        self.schedule_save()

    def apply_profile(self, profile: dict):
        self._applying_profile = True
        try:
            for field in CINEMA_FIELDS:
                if field in profile:
                    self.vars[field].set(profile[field])
        finally:
            self._applying_profile = False
        self.profile.set(profile["id"])
        self.settings_snapshot = self._read_settings()
        self.schedule_save()
        self.set_status(f"Perfil “{profile['short_name']}” aplicado.", "ok")

    # ================================================================== modo cinema
    def toggle_cinema(self):
        if self.running:
            self.stop_cinema()
        else:
            self.start_cinema()

    def start_cinema(self, preview: bool = False, monitor_index: int | None = None):
        if self.running or (self.worker and self.worker.is_alive()):
            return
        if monitor_index is not None:
            self.set_monitor(monitor_index)
        if not self.monitors:
            self._detect_monitors()
        if not self.monitors:
            self.set_status("Não foi possível listar as telas deste computador.", "error")
            return
        if not preview and not self.controller.active_devices():
            self.set_status("Adicione uma lâmpada antes de iniciar o modo cinema.", "error")
            self.show_page("lamps")
            return
        monitor = self.monitors[self.monitor_index].copy()
        self.stop_event.clear()
        self.running, self.previewing, self._restore_on_stop = True, preview, True
        self._update_cinema_state()
        self.tray.set_icon(cinema=not preview)
        self.set_status("Prévia ativa: mostrando as cores só na janela." if preview
                        else "Conectando às lâmpadas…")
        self.worker = threading.Thread(target=self._cinema_loop, args=(monitor, preview), daemon=True, name="Cinema")
        self.worker.start()

    def _cinema_loop(self, monitor: dict, preview: bool):
        try:
            if not preview:
                results = self.controller.start_cinema()
                ok = [d for d, err in results if err is None]
                failed = [(d, err) for d, err in results if err is not None]
                self.events.put(("cinema_started", (ok, failed)))
                if not ok:
                    return
            from mss import MSS

            dark_map: dict[str, bool] = {}
            zones = ALL_ZONES if self.multi else {"all"}
            previous = last_ui = time.monotonic()
            with MSS() as capture:
                while not self.stop_event.is_set():
                    started = time.monotonic()
                    settings = self.settings_snapshot
                    shot = capture.grab(monitor)
                    frame = downscale_frame(Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX"))
                    colors = compute_zones_colors(frame, settings, zones, dark_map)
                    for zone, color in colors.items():
                        dark_map[zone] = max(color) == 0
                    if self.stop_event.is_set():
                        break
                    dt, previous = started - previous, started
                    lamp_colors = {}
                    if not preview:
                        lamp_colors = self.controller.dispatch_frame(
                            colors, light_mode=settings.light_mode, dt=dt, smoothing=settings.smoothing)
                    if started - last_ui >= FRAME_UI_INTERVAL:
                        last_ui = started
                        self.events.put(("frame", (colors, lamp_colors)))
                    self.stop_event.wait(max(0.0, settings.interval - (time.monotonic() - started)))
        except Exception as exc:
            log.exception("Falha no modo cinema")
            self.events.put(("status", (f"O modo cinema parou: {friendly_error(exc) if isinstance(exc, BulbError) else exc}", "error")))
        finally:
            if not preview:
                self.controller.stop_cinema(restore=self._restore_on_stop)
            self.events.put(("cinema_done", preview))

    def stop_cinema(self, restore: bool = True):
        if not self.running:
            return
        self._restore_on_stop = restore
        self.stop_event.set()
        self.set_status("Parando e devolvendo as lâmpadas ao estado anterior…" if restore and not self.previewing
                        else "Parando…")

    def after_cinema(self, action):
        """Executa ``action`` agora ou, se o cinema estiver rodando, assim que ele parar (sem restaurar)."""
        if self.running or (self.worker and self.worker.is_alive()):
            self._after_stop.append(action)
            self.stop_cinema(restore=False)
        else:
            action()

    # ================================================================== controle manual
    def manual_rgb(self) -> tuple[int, int, int]:
        if self.manual_mode.get() == "white":
            return cct_to_rgb(self.manual_temp.get(), self.manual_brightness.get())
        value = max(0.01, self.manual_brightness.get() / 100.0)
        return tuple(round(c * 255) for c in colorsys.hsv_to_rgb(self.manual_hue, self.manual_sat, value))

    def manual_command(self) -> dict:
        return {"mode": self.manual_mode.get(), "rgb": self.manual_rgb(),
                "brightness": round(self.manual_brightness.get()), "temp": round(self.manual_temp.get())}

    def target_ids(self) -> list[str] | None:
        """Lâmpadas que recebem o controle manual (None = todas)."""
        target = self.manual_target.get()
        if self.multi and target and target in self.controller.devices:
            return [target]
        return None

    def apply_manual(self, quiet: bool = False):
        command = self.manual_command()

        def run():
            self.controller.apply(self.target_ids(), command)
            self.tray.set_icon(color=rgb_to_hex(command["rgb"]))
            if not quiet:
                self.set_status("Aplicando cor…")
        self.after_cinema(run)

    def schedule_live_apply(self):
        """Aplica em tempo real (com atraso curto) enquanto o usuário mexe na roda/sliders."""
        if not self.live_manual.get():
            return
        if self._live_job:
            self.root.after_cancel(self._live_job)
        self._live_job = self.root.after(120, lambda: self.apply_manual(quiet=True))

    def apply_preset(self, preset: dict):
        mode = preset.get("mode", "colour")
        self.manual_mode.set(mode)
        self.manual_brightness.set(preset.get("brightness", 100))
        if mode == "white":
            self.manual_temp.set(preset.get("temp", 100))
        else:
            r, g, b = preset.get("rgb", (255, 255, 255))
            self.manual_hue, self.manual_sat, _ = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        self.pages["colors"].sync_from_app()
        command = self.manual_command()
        if mode != "white":
            command["rgb"] = tuple(preset.get("rgb", command["rgb"]))

        def run():
            self.controller.apply(self.target_ids(), command)
            self.tray.set_icon(color=preset_color_hex(preset))
            self.set_status(f"Preset “{preset.get('name', '')}” aplicado.", "ok")
        self.after_cinema(run)

    def save_preset(self, name: str):
        command = self.manual_command()
        preset = {"name": name or f"Minha cor {len(self.custom_presets) + 1}", "mode": command["mode"],
                  "brightness": command["brightness"]}
        if command["mode"] == "white":
            preset["temp"] = command["temp"]
        else:
            preset["rgb"] = list(command["rgb"])
        self.custom_presets.append(preset)
        self.schedule_save()
        self.tray.rebuild()
        self.set_status(f"Cor “{preset['name']}” salva.", "ok")

    def delete_preset(self, index: int):
        if 0 <= index < len(self.custom_presets):
            removed = self.custom_presets.pop(index)
            self.schedule_save()
            self.tray.rebuild()
            self.set_status(f"Cor “{removed.get('name', '')}” excluída.")

    def activate_scenario(self, scenario: Scenario):
        def run():
            self.controller.apply(None, lambda device: scenario.get_color_for_bulb(device.id, device.zone))
            self.tray.set_icon(color=scenario.preview_hex)
            self.set_status(f"Cenário “{scenario.name}” ativado.", "ok")
        self.after_cinema(run)

    def save_scenario(self, name: str):
        command = self.manual_command()
        scenario = Scenario(
            id=f"custom_{int(time.time() * 1000)}", name=name or f"Meu cenário {len(self.scenarios) + 1}",
            description="Cenário personalizado.", icon="⭐", default_mode=command["mode"],
            default_rgb=tuple(command["rgb"]), default_brightness=command["brightness"],
            default_temp=command["temp"], is_custom=True)
        self.scenarios.append(scenario)
        self.schedule_save()
        self.tray.rebuild()
        self.set_status(f"Cenário “{scenario.name}” salvo.", "ok")

    def delete_scenario(self, scenario_id: str):
        self.scenarios = [s for s in self.scenarios if s.id != scenario_id]
        self.schedule_save()
        self.tray.rebuild()
        self.set_status("Cenário excluído.")

    def set_power(self, on: bool, bulb_ids: list[str] | None = None):
        def run():
            if on:
                command = self.manual_command()
                self.controller.apply(bulb_ids, command)
                self.tray.set_icon(color=rgb_to_hex(command["rgb"]))
            else:
                self.controller.turn_off(bulb_ids)
                if bulb_ids is None:
                    self.tray.set_icon(off=True)
            self.set_status("Acendendo…" if on else "Apagando…")
        self.after_cinema(run)

    def turn_off_all(self):
        self.set_power(False)

    # ================================================================== lâmpadas
    @property
    def multi(self) -> bool:
        """True quando há mais de uma lâmpada: libera zonas e controle por lâmpada."""
        return len(self.controller.device_list()) > 1

    def save_device(self, device: BulbDevice):
        if not self.controller.device_list():
            device.zone, device.enabled = "all", True
        self.controller.add_device(device)
        self.devices_changed()
        self.set_status(f"Lâmpada “{device.name}” salva. Testando conexão…")
        self.controller.test(device)

    def remove_device(self, device: BulbDevice):
        if not messagebox.askyesno("Remover lâmpada", f"Remover “{device.name}” do Luz Cinema?", parent=self.root):
            return

        def run():
            self.controller.remove_device(device.id)
            remaining = self.controller.device_list()
            if len(remaining) == 1:
                # Sozinha, a lâmpada volta a acompanhar a tela inteira (as zonas ficam ocultas).
                remaining[0].zone, remaining[0].enabled = "all", True
            self.devices_changed()
            self.set_status(f"“{device.name}” removida.")
        self.after_cinema(run)

    def devices_changed(self):
        self.schedule_save()
        self.tray.rebuild()
        self._update_cinema_state()
        for page in self.pages.values():
            if hasattr(page, "on_devices_changed"):
                page.on_devices_changed()

    def test_device(self, device: BulbDevice):
        self.set_status(f"Testando “{device.name}”…")
        self.controller.test(device)

    def fetch_cloud_devices(self, callback):
        """Busca as lâmpadas da conta Tuya em segundo plano e chama ``callback(lista)`` na interface."""
        self.set_status("Buscando lâmpadas na sua conta Tuya…")

        def task():
            try:
                from ..tuya_cloud import query_account_devices
                devices = query_account_devices()
                self.events.put(("call", lambda: callback(devices)))
            except Exception as exc:
                self.events.put(("status", (friendly_error(exc), "error")))
        threading.Thread(target=task, daemon=True).start()

    def scan_local(self, callback):
        """Procura lâmpadas Tuya na rede local (~10 s) e chama ``callback(lista)`` na interface."""
        self.set_status("Procurando lâmpadas na rede local (leva cerca de 10 segundos)…")

        def task():
            try:
                import tinytuya
                found = tinytuya.deviceScan(verbose=False, maxretry=10, poll=False, forcescan=False)
                devices = [{"id": d.get("gwId") or d.get("id"), "ip": ip, "version": str(d.get("version", "3.3"))}
                           for ip, d in found.items() if d.get("gwId") or d.get("id")]
                self.events.put(("call", lambda: callback(devices)))
            except Exception:
                self.events.put(("status", ("A busca na rede local falhou. Confira se o PC está no mesmo Wi-Fi.", "error")))
        threading.Thread(target=task, daemon=True).start()

    def open_tuya_link(self, on_linked=None):
        from ..tuya_link import LinkWindow
        top = tk.Toplevel(self.root)
        top.transient(self.root)
        LinkWindow(top, self.theme.t, on_linked=on_linked)

    # ================================================================== sistema
    def set_autostart(self, enabled: bool):
        if set_autostart(enabled):
            self.set_status("Vai iniciar junto com o Windows (na bandeja)." if enabled
                            else "Não vai mais iniciar com o Windows.", "ok")
        else:
            self.set_status("Não foi possível alterar o início automático.", "error")
        self.start_with_windows.set(is_autostart_enabled())

    def collect_config(self) -> dict:
        data = {k: var.get() for k, var in self.vars.items()}
        data["crop"] = round(data["crop"])
        data.update(
            profile=self.profile.get(), monitor_index=self.monitor_index, theme_mode=self.theme.mode,
            minimize_to_tray=self.minimize_to_tray.get(), live_manual=self.live_manual.get(),
            manual_target=self.manual_target.get(), custom_presets=self.custom_presets,
            custom_scenarios=[s.to_dict() for s in self.scenarios if s.is_custom],
            devices=self.controller.device_list())
        return data

    def schedule_save(self):
        if self.closing:
            return
        if self._save_job:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(500, self.save_now)

    def save_now(self):
        self._save_job = None
        try:
            storage.save(self.collect_config(), self.data_dir)
        except Exception as exc:
            log.exception("Falha ao salvar preferências")
            self.set_status(f"Não foi possível salvar as preferências: {exc}", "error")

    # ================================================================== eventos
    def drain(self):
        if not self.alive:
            return
        try:
            while True:
                kind, value = self.events.get_nowait()
                self._handle_event(kind, value)
                if not self.alive:
                    return
        except queue.Empty:
            pass
        if wake_requested():
            self.show_window()
        self._timer = self.root.after(40, self.drain)

    def _handle_event(self, kind, value):
        if kind == "status":
            self.set_status(*value)
        elif kind == "call":
            value()
        elif kind == "frame":
            colors, lamp_colors = value
            self.lamp_colors.update(lamp_colors)
            for page in self.pages.values():
                if hasattr(page, "on_frame"):
                    page.on_frame(colors, lamp_colors)
            self.tray.set_frame_color(colors.get("all"))
        elif kind == "cinema_started":
            ok, failed = value
            if not ok:
                reason = failed[0][1] if failed else "Nenhuma lâmpada ativa."
                self.set_status(f"Nenhuma lâmpada respondeu. {reason}", "error")
            elif failed:
                names = ", ".join(d.name for d, _ in failed)
                self.set_status(f"Sincronizando {len(ok)} lâmpada(s). Sem resposta: {names}.", "error")
            else:
                self.set_status("Sincronizando! Pode minimizar e dar play no seu filme ou jogo.", "ok")
        elif kind == "cinema_done":
            self._on_cinema_done(value)
        elif kind == "bulb":
            self._handle_bulb_event(*value)

    def _handle_bulb_event(self, kind, payload):
        if kind == "test":
            device, error = payload
            if error:
                self.set_status(f"“{device.name}”: {error}", "error")
            else:
                self.set_status(f"Conexão com “{device.name}” funcionando!", "ok")
        elif kind == "applied":
            if self.status_text.get().endswith("…"):
                self.set_status("Pronto.", "ok")
        elif kind == "bulb_error":
            device, error = payload
            now = time.monotonic()
            if now - self._error_shown.get(device.id, 0) > 8:
                self._error_shown[device.id] = now
                self.set_status(f"“{device.name}”: {error}", "error")
        elif kind == "reconnected":
            self.set_status(f"“{payload.name}” reconectada.", "ok")
        elif kind == "no_bulbs":
            self.set_status("Nenhuma lâmpada configurada.", "error")
        for page in self.pages.values():
            if hasattr(page, "on_bulb_event"):
                page.on_bulb_event(kind, payload)

    def _on_cinema_done(self, preview: bool):
        self.running = self.previewing = False
        self.worker = None
        self.lamp_colors.clear()
        self._update_cinema_state()
        for page in self.pages.values():
            if hasattr(page, "on_frame"):
                page.on_frame({}, {})
        pending, self._after_stop = self._after_stop, []
        if self.closing:
            self._destroy()
            return
        if pending:
            for action in pending:
                action()
        else:
            self.tray.set_icon()
            self.set_status("Prévia encerrada." if preview else
                            ("Sincronização encerrada. Lâmpadas restauradas." if self._restore_on_stop
                             else "Sincronização encerrada."))

    # ================================================================== janela / saída
    def show_window(self):
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.focus_force()

    def on_window_close(self):
        if self.minimize_to_tray.get() and self.tray.available:
            self.root.withdraw()
            self.tray.notify_once("O Luz Cinema continua rodando aqui na bandeja. Clique com o botão direito para sair.")
        else:
            self.quit()

    def quit(self):
        if self.closing:
            return
        self.closing = True
        if self._save_job:
            self.root.after_cancel(self._save_job)
            self.save_now()
        self.tray.stop()
        if self.worker and self.worker.is_alive():
            self.root.withdraw()
            self.stop_cinema(restore=True)
            self.root.after(8000, self._destroy)  # garantia caso alguma lâmpada não responda
        else:
            self._destroy()

    def _destroy(self):
        if not self.alive:
            return
        self.alive = False
        self.controller.close()
        for job in (self._timer, self._save_job, self._live_job):
            if job:
                try:
                    self.root.after_cancel(job)
                except tk.TclError:
                    pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def run():
    """Ponto de entrada do app."""
    import os
    import sys

    from ..windows import APP_DIR, check_single_instance, setup_process

    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    os.chdir(APP_DIR)
    if "--export-icon" in sys.argv:
        from .icons import export_ico
        from .icons import ASSETS_DIR
        export_ico(ASSETS_DIR / "luzcinema.ico")
        return
    if not check_single_instance():
        return
    setup_process()
    root = tk.Tk()
    minimized = "--tray" in sys.argv or "--minimized" in sys.argv
    if minimized:
        root.withdraw()
    app = App(root)
    if minimized and not app.tray.available:
        root.deiconify()
    root.mainloop()

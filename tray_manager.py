"""Gerenciamento do ícone, menus e eventos na bandeja do sistema (System Tray)."""
from __future__ import annotations

import threading
from icon_utils import create_tray_icon_image
from presets_data import DEFAULT_PRESETS


class TrayMixin:
    """Mixin que fornece integração com a área de notificação do Windows via Pystray."""

    def setup_tray(self):
        try:
            import pystray
            image = create_tray_icon_image()
            menu = self._build_tray_menu()
            self.tray_icon = pystray.Icon("LuzCinema", image, "Luz Cinema", menu=menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception:
            self.tray_icon = None

    def set_tray_icon_visual(self, color_hex="#9c8aff", cinema_mode=False, is_off=False):
        if not self.tray_icon:
            return
        try:
            self.tray_icon.icon = create_tray_icon_image(color_hex=color_hex, cinema_mode=cinema_mode, is_off=is_off)
        except Exception:
            pass

    def _build_tray_menu(self):
        import logging
        try:
            import pystray

            def make_cinema_action(idx):
                return lambda icon, item: self.start_cinema_from_tray(idx)

            def make_preset_action(preset):
                return lambda icon, item: self.activate_preset_from_tray(preset)

            monitor_items = []
            try:
                if hasattr(self, "monitors") and self.monitors:
                    for i, m in enumerate(self.monitors):
                        w = m.get("width") if isinstance(m, dict) else getattr(m, "width", None)
                        h = m.get("height") if isinstance(m, dict) else getattr(m, "height", None)
                        label = f"Monitor {i+1} ({w}x{h})" if w and h else f"Monitor {i+1}"
                        monitor_items.append(pystray.MenuItem(label, make_cinema_action(i)))
                else:
                    monitor_items.append(pystray.MenuItem("Sincronizar (Padrão)", make_cinema_action(0)))
            except Exception as e:
                logging.warning("Erro ao criar submenu de monitores (v1): %s", e)
                monitor_items = [pystray.MenuItem("Sincronizar (Padrão)", make_cinema_action(0))]
            cinema_submenu = pystray.Menu(*monitor_items)

            preset_items = []
            try:
                for p in DEFAULT_PRESETS:
                    p_name = p.get("name") if isinstance(p, dict) else getattr(p, "name", "Preset")
                    preset_items.append(pystray.MenuItem(p_name, make_preset_action(p)))
                if getattr(self, "custom_presets", None):
                    preset_items.append(pystray.Menu.SEPARATOR)
                    for cp in self.custom_presets:
                        cp_name = cp.get("name") if isinstance(cp, dict) else getattr(cp, "name", "Preset")
                        preset_items.append(pystray.MenuItem(cp_name, make_preset_action(cp)))
            except Exception as e:
                logging.warning("Erro ao criar submenu de presets (v1): %s", e)
            presets_submenu = pystray.Menu(*preset_items) if preset_items else None

            menu_items = [
                pystray.MenuItem("Abrir Luz Cinema", self.restore_from_tray, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Sincronizar Cinema", cinema_submenu),
            ]
            if presets_submenu:
                menu_items.append(pystray.MenuItem("Presets", presets_submenu))
            menu_items.extend([
                pystray.MenuItem("Apagar Lâmpada", lambda icon, item: self.root.after(0, self.turn_off_light)),
                pystray.MenuItem("Parar Iluminação", lambda icon, item: self.root.after(0, self.stop)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Sair", self.quit_app),
            ])
            return pystray.Menu(*menu_items)
        except Exception as err:
            logging.warning("Erro inesperado ao gerar menu completo da bandeja (v1): %s", err, exc_info=True)
            try:
                import pystray
                return pystray.Menu(
                    pystray.MenuItem("Abrir Luz Cinema", self.restore_from_tray, default=True),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("Parar Iluminação", lambda icon, item: self.root.after(0, self.stop)),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("Sair", self.quit_app),
                )
            except Exception:
                return None

    def update_tray_menu(self):
        if not self.tray_icon:
            return
        try:
            menu = self._build_tray_menu()
            if menu:
                self.tray_icon.menu = menu
        except Exception:
            pass

    def start_cinema_from_tray(self, monitor_idx: int):
        def task():
            if self.running:
                self.stop(restore=False)
                if self.worker and self.worker.is_alive():
                    self.worker.join(timeout=0.3)
            if hasattr(self, "monitor_box") and hasattr(self, "monitors") and 0 <= monitor_idx < len(self.monitors):
                self.monitor_box.current(monitor_idx)
            self.start(real=True)
        self.root.after(0, task)

    def activate_preset_from_tray(self, preset: dict):
        self.root.after(0, lambda: self.activate_preset(preset))

    def restore_from_tray(self, *args):
        self.root.after(0, self._show_window)

    def _show_window(self):
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.focus_force()

    def quit_app(self, *args):
        self._exiting_completely = True
        self.close_manual_bulb()
        self.manual_worker_stop.set()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.root.after(0, self.close)

    def on_window_close(self):
        if self.minimize_to_tray.get() and self.tray_icon and not getattr(self, "_exiting_completely", False):
            self.root.withdraw()
        else:
            self.quit_app()

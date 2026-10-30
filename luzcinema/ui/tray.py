"""Ícone e menu na bandeja do Windows (ao lado do relógio)."""
from __future__ import annotations

import logging
import threading
import time

from ..core import rgb_to_hex
from ..presets import CINEMA_PROFILES, DEFAULT_PRESETS
from ..windows import APP_REG_NAME
from .icons import create_tray_icon_image

log = logging.getLogger(__name__)


class Tray:
    """Os cliques do menu rodam na thread do pystray; por isso tudo vai para a fila de eventos da janela."""

    def __init__(self, app):
        self.app = app
        self.icon = None
        self._notified = False
        self._last_frame_update = 0.0
        self._cinema = False

    @property
    def available(self) -> bool:
        return self.icon is not None

    def start(self):
        try:
            import pystray
            self.icon = pystray.Icon(APP_REG_NAME, create_tray_icon_image(),
                                     "Luz Cinema", menu=self._menu())
            threading.Thread(target=self.icon.run, daemon=True, name="Bandeja").start()
        except Exception:
            log.warning("Bandeja do sistema indisponível", exc_info=True)
            self.icon = None

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass

    def rebuild(self):
        if self.icon:
            try:
                self.icon.menu = self._menu()
                self.icon.update_menu()
            except Exception:
                log.warning("Falha ao atualizar o menu da bandeja", exc_info=True)

    def notify_once(self, message: str):
        if self.icon and not self._notified and getattr(self.icon, "HAS_NOTIFICATION", False):
            self._notified = True
            try:
                self.icon.notify(message, "Luz Cinema")
            except Exception:
                pass

    def set_icon(self, color: str = "#8b7bff", cinema: bool = False, off: bool = False):
        self._cinema = cinema
        if self.icon:
            try:
                self.icon.icon = create_tray_icon_image(color_hex=color, cinema_mode=cinema, is_off=off)
            except Exception:
                pass

    def set_frame_color(self, rgb):
        """Durante a prévia, o ícone acompanha a cor da tela (no máximo 1x por segundo)."""
        now = time.monotonic()
        if rgb is None or self._cinema or now - self._last_frame_update < 1.0 or not self.app.previewing:
            return
        self._last_frame_update = now
        if max(rgb) > 6:
            self.set_icon(color=rgb_to_hex(rgb))

    # ------------------------------------------------------------------ menu
    def _ui(self, fn, *args):
        """Cria um callback de menu que executa ``fn(*args)`` na thread da interface."""
        return lambda icon=None, item=None: self.app.events.put(("call", lambda: fn(*args)))

    def _menu(self):
        import pystray
        Item, Menu = pystray.MenuItem, pystray.Menu
        app = self.app

        monitors = app.monitor_labels() or ["Tela principal"]
        cinema_menu = Menu(*[Item(label, self._ui(app.start_cinema, False, i)) for i, label in enumerate(monitors)])
        profiles = Menu(*[Item(p["name"], self._ui(app.apply_profile, p)) for p in CINEMA_PROFILES])
        scenarios = Menu(*[Item(f"{s.icon} {s.name}", self._ui(app.activate_scenario, s)) for s in app.scenarios])
        preset_items = [Item(p["name"], self._ui(app.apply_preset, p)) for p in DEFAULT_PRESETS]
        if app.custom_presets:
            preset_items.append(Menu.SEPARATOR)
            preset_items += [Item(p.get("name", "Cor"), self._ui(app.apply_preset, p)) for p in app.custom_presets]

        items = [
            Item("Abrir Luz Cinema", self._ui(app.show_window), default=True),
            Menu.SEPARATOR,
            Item("▶ Iniciar modo cinema", cinema_menu),
            Item("■ Parar modo cinema", self._ui(app.stop_cinema), enabled=lambda _: app.running),
            Item("Perfis de calibração", profiles),
            Menu.SEPARATOR,
            Item("Cenários", scenarios),
            Item("Cores", Menu(*preset_items)),
        ]
        devices = app.controller.device_list()
        if len(devices) > 1:
            items.append(Item("Lâmpadas", Menu(*[
                Item(d.name, Menu(Item("Acender", self._ui(app.set_power, True, [d.id])),
                                  Item("Apagar", self._ui(app.set_power, False, [d.id]))))
                for d in devices])))
        items += [
            Item("💡 Acender", self._ui(app.set_power, True)),
            Item("⏻ Apagar", self._ui(app.turn_off_all)),
            Menu.SEPARATOR,
            Item("Sair", self._ui(app.quit)),
        ]
        return Menu(*items)

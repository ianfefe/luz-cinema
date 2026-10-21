"""Gerenciador e despachante multi-lâmpadas com suporte a zonas espaciais para o Luz Cinema v2."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
import logging
import threading
import time
from typing import Any

from core import LocalBulb, BulbError, Smoother, should_send


@dataclass
class BulbDevice:
    """Representa uma lâmpada configurada no sistema."""
    id: str
    name: str
    connection_type: str = "cloud"  # 'cloud' ou 'local'
    ip: str = ""
    key: str = ""
    version: str = "3.5"
    zone: str = "all"  # 'all', 'left', 'right', 'top', 'bottom', 'center', 'none'
    enabled: bool = True
    last_color_hex: str = "#8b7bff"
    is_on: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> BulbDevice:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", "Lâmpada"),
            connection_type=data.get("connection_type", "cloud"),
            ip=data.get("ip", ""),
            key=data.get("key", ""),
            version=data.get("version", "3.5"),
            zone=data.get("zone", "all"),
            enabled=bool(data.get("enabled", True)),
            last_color_hex=data.get("last_color_hex", "#8b7bff"),
            is_on=bool(data.get("is_on", True)),
        )


class MultiBulbController:
    """Gerencia conexões, despacho simultâneo de cores por zona e cenários para múltiplas lâmpadas."""

    def __init__(self, devices: list[BulbDevice] | None = None):
        self.devices: dict[str, BulbDevice] = {d.id: d for d in (devices or [])}
        self.active_connections: dict[str, Any] = {}
        self.smoothers: dict[str, Smoother] = {}
        self.last_sent: dict[str, tuple[tuple[int, int, int] | None, float]] = {}
        self.skip_restore_on_stop = False
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="BulbWorker")

    def update_devices(self, devices: list[BulbDevice]):
        with self._lock:
            new_ids = {d.id for d in devices}
            # Fecha conexões de lâmpadas removidas
            for bid in list(self.active_connections.keys()):
                if bid not in new_ids:
                    self._close_one(bid)
            self.devices = {d.id: d for d in devices}

    def get_required_zones(self) -> set[str]:
        """Retorna o conjunto de zonas espaciais que possuem lâmpadas ativas vinculadas."""
        with self._lock:
            zones = set()
            for d in self.devices.values():
                if d.enabled and d.zone != "none":
                    zones.add(d.zone)
            return zones or {"all"}

    def get_bulb_instance(self, device: BulbDevice):
        """Retorna ou cria uma conexão para a lâmpada especificada."""
        bid = device.id
        if bid in self.active_connections:
            return self.active_connections[bid]

        try:
            if device.connection_type == "cloud":
                from tuya_cloud import CloudBulb
                conn = CloudBulb(device_id=device.id)
            else:
                conn = LocalBulb(device.id, device.ip, device.key, device.version)
            self.active_connections[bid] = conn
            if bid not in self.smoothers:
                self.smoothers[bid] = Smoother()
            if bid not in self.last_sent:
                self.last_sent[bid] = (None, 0.0)
            return conn
        except Exception as exc:
            logging.warning(f"Falha ao conectar à lâmpada {device.name} ({device.id}): {exc}")
            return None

    def connect_all_active(self) -> list[str]:
        """Conecta a todas as lâmpadas habilitadas. Retorna lista de nomes com sucesso."""
        successes = []
        with self._lock:
            for dev in self.devices.values():
                if dev.enabled and dev.zone != "none":
                    conn = self.get_bulb_instance(dev)
                    if conn:
                        successes.append(dev.name)
        return successes

    def dispatch_cinema_frame(
        self,
        zone_colors: dict[str, tuple[int, int, int]],
        light_mode: bool = False,
        dt: float = 0.25,
        smoothing: float = 0.1,
    ) -> dict[str, tuple[int, int, int]]:
        """
        Aplica a cor de cada zona à sua respectiva lâmpada de forma paralela.
        Retorna dicionário {device_id: rgb_suavizado}.
        """
        tasks = []
        results = {}
        now = time.monotonic()

        with self._lock:
            for bid, dev in self.devices.items():
                if not dev.enabled or dev.zone == "none":
                    continue
                target_rgb = zone_colors.get(dev.zone, zone_colors.get("all", (0, 0, 0)))
                smoother = self.smoothers.setdefault(bid, Smoother())
                smoothed_rgb = smoother.update(target_rgb, dt, smoothing)
                results[bid] = smoothed_rgb

                conn = self.get_bulb_instance(dev)
                if not conn:
                    continue

                last_rgb, last_time = self.last_sent.get(bid, (None, 0.0))
                if should_send(last_rgb, smoothed_rgb, now - last_time):
                    self.last_sent[bid] = (smoothed_rgb, now)
                    # Dispara em paralelo para não acumular latência entre múltiplas lâmpadas
                    tasks.append((conn, smoothed_rgb, light_mode))

        def _send(c, rgb, mode):
            try:
                c.color(rgb, light_mode=mode)
            except Exception:
                pass

        for c, rgb, mode in tasks:
            self._executor.submit(_send, c, rgb, mode)

        return results

    def apply_manual_to_bulbs(
        self,
        bulb_ids: list[str] | None,
        mode: str,
        rgb: tuple[int, int, int] | None = None,
        brightness: int = 100,
        temp: int = 100,
    ):
        """Aplica comando manual (cor, branco ou off) a uma ou todas as lâmpadas."""
        targets = []
        with self._lock:
            for bid, dev in self.devices.items():
                if bulb_ids is None or bid in bulb_ids:
                    conn = self.get_bulb_instance(dev)
                    if conn:
                        targets.append((dev, conn))

        def _send(dev, conn):
            try:
                conn.set_manual(mode, rgb=rgb, brightness=brightness, temp=temp)
                dev.is_on = (mode != "off")
            except Exception as e:
                logging.warning(f"Erro ao enviar comando manual para {dev.name}: {e}")

        for dev, conn in targets:
            self._executor.submit(_send, dev, conn)

    def apply_scenario(self, scenario, bulb_ids: list[str] | None = None):
        """Aplica um cenário de iluminação distribuindo cores individuais ou coletivas."""
        targets = []
        with self._lock:
            for bid, dev in self.devices.items():
                if bulb_ids is None or bid in bulb_ids:
                    conn = self.get_bulb_instance(dev)
                    if conn:
                        cmd = scenario.get_color_for_bulb(dev.id, dev.zone)
                        targets.append((dev, conn, cmd))

        def _send(dev, conn, cmd):
            try:
                mode = cmd.get("mode", "colour")
                rgb = tuple(cmd["rgb"]) if cmd.get("rgb") else None
                bright = int(cmd.get("brightness", 100))
                temp = int(cmd.get("temp", 100))
                conn.set_manual(mode, rgb=rgb, brightness=bright, temp=temp)
                dev.is_on = (mode != "off")
            except Exception as e:
                logging.warning(f"Erro ao aplicar cenário {scenario.name} em {dev.name}: {e}")

        for dev, conn, cmd in targets:
            self._executor.submit(_send, dev, conn, cmd)

    def turn_off_all(self):
        """Apaga todas as lâmpadas configuradas."""
        self.apply_manual_to_bulbs(None, mode="off")

    def restore_all(self):
        """Restaura o estado anterior de todas as lâmpadas."""
        if getattr(self, "skip_restore_on_stop", False):
            return
        with self._lock:
            conns = list(self.active_connections.values())
        for c in conns:
            try:
                c.restore()
            except Exception:
                pass

    def _close_one(self, bid: str):
        conn = self.active_connections.pop(bid, None)
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    def close_all(self):
        """Encerra todas as conexões abertas."""
        with self._lock:
            for bid in list(self.active_connections.keys()):
                self._close_one(bid)
            self.smoothers.clear()
            self.last_sent.clear()
            try:
                self._executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass

"""Cadastro de lâmpadas e despacho paralelo de cores (local ou nuvem Tuya).

Com uma lâmpada ela fica na zona "all"; com várias, cada uma acompanha a sua zona da tela.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
import logging
import threading
import time
from typing import Any, Callable

from .core import LocalBulb, Smoother, should_send, ZONES

log = logging.getLogger(__name__)

RETRY_DELAY = 5.0  # segundos entre tentativas de reconexão durante o cinema


@dataclass
class BulbDevice:
    """Uma lâmpada cadastrada. A chave local só existe em memória; no disco ela vai protegida."""
    id: str
    name: str
    connection_type: str = "cloud"  # "cloud" ou "local"
    ip: str = ""
    key: str = ""
    version: str = "3.5"
    zone: str = "all"  # uma de ZONES ou "none"
    enabled: bool = True

    @property
    def is_local(self) -> bool:
        return self.connection_type == "local"

    @property
    def kind_label(self) -> str:
        return "Rede local" if self.is_local else "Conta Tuya"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "BulbDevice":
        zone = data.get("zone", "all")
        return cls(
            id=str(data.get("id", "")).strip(),
            name=str(data.get("name") or "Lâmpada"),
            connection_type="local" if data.get("connection_type") == "local" else "cloud",
            ip=str(data.get("ip", "")),
            key=str(data.get("key", "")),
            version=str(data.get("version", "3.5")),
            zone=zone if zone in ZONES or zone == "none" else "all",
            enabled=bool(data.get("enabled", True)),
        )


def default_connector(device: BulbDevice):
    if device.is_local:
        return LocalBulb(device.id, device.ip, device.key, device.version)
    from .tuya_cloud import CloudBulb
    return CloudBulb(device_id=device.id)


class BulbController:
    """Gerencia conexões e envia comandos às lâmpadas sem travar a interface.

    - Cada lâmpada tem um lock próprio: comandos manuais e quadros do cinema nunca se misturam.
    - Durante o cinema, quadros são descartados enquanto a lâmpada ainda envia o anterior.
    - Conexões perdidas são refeitas em segundo plano, com espera entre tentativas.
    """

    def __init__(self, devices: list[BulbDevice] | None = None,
                 connector: Callable[[BulbDevice], Any] = default_connector,
                 on_event: Callable[[str, Any], None] | None = None):
        self.devices: dict[str, BulbDevice] = {d.id: d for d in (devices or [])}
        self.connector = connector
        self.on_event = on_event or (lambda kind, payload: None)
        self.connections: dict[str, Any] = {}
        self.power: dict[str, bool | None] = {}
        self._smoothers: dict[str, Smoother] = {}
        self._last_sent: dict[str, tuple[tuple[int, int, int] | None, float]] = {}
        self._in_flight: set[str] = set()
        self._connecting: set[str] = set()
        self._retry_at: dict[str, float] = {}
        self._bulb_locks: dict[str, threading.Lock] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="Lampada")
        self._closed = False

    # ------------------------------------------------------------------ cadastro
    def set_devices(self, devices: list[BulbDevice]):
        with self._lock:
            keep = {d.id for d in devices}
            for bid in list(self.connections):
                if bid not in keep:
                    self._close_unlocked(bid)
            self.devices = {d.id: d for d in devices}

    def add_device(self, device: BulbDevice):
        with self._lock:
            self._close_unlocked(device.id)  # dados podem ter mudado (IP, chave)
            self.devices[device.id] = device

    def remove_device(self, bulb_id: str):
        with self._lock:
            self._close_unlocked(bulb_id)
            self.devices.pop(bulb_id, None)
            self.power.pop(bulb_id, None)

    def device_list(self) -> list[BulbDevice]:
        with self._lock:
            return list(self.devices.values())

    def active_devices(self) -> list[BulbDevice]:
        return [d for d in self.device_list() if d.enabled and d.zone != "none"]

    def required_zones(self) -> set[str]:
        return {d.zone for d in self.active_devices()} or {"all"}

    # ------------------------------------------------------------------ conexões
    def _bulb_lock(self, bulb_id: str) -> threading.Lock:
        with self._lock:
            return self._bulb_locks.setdefault(bulb_id, threading.Lock())

    def connect(self, device: BulbDevice):
        """Retorna a conexão da lâmpada, conectando se preciso (bloqueante). Lança BulbError em falha."""
        with self._bulb_lock(device.id):
            return self._connect_locked(device)

    def _connect_locked(self, device: BulbDevice):
        with self._lock:
            conn = self.connections.get(device.id)
        if conn is not None:
            return conn
        conn = self.connector(device)
        with self._lock:
            if device.id not in self.devices or self._closed:
                stale = True
            else:
                self.connections[device.id] = conn
                self._smoothers.setdefault(device.id, Smoother())
                stale = False
        if stale:
            try:
                conn.close()
            except Exception:
                pass
        return conn

    def _drop(self, bulb_id: str):
        with self._lock:
            self._close_unlocked(bulb_id)

    def _close_unlocked(self, bulb_id: str):
        conn = self.connections.pop(bulb_id, None)
        self._last_sent.pop(bulb_id, None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    def _submit(self, fn, *args):
        if self._closed:
            return None
        try:
            return self._executor.submit(fn, *args)
        except RuntimeError:  # executor encerrado durante o fechamento
            return None

    def test(self, device: BulbDevice):
        """Testa a conexão em segundo plano e avisa o resultado por on_event('test', ...)."""
        def task():
            try:
                self._drop(device.id)
                self.connect(device)
                self.on_event("test", (device, None))
            except Exception as exc:
                self.on_event("test", (device, friendly_error(exc)))
        self._submit(task)

    # ------------------------------------------------------------------ cinema
    def start_cinema(self) -> list[tuple[BulbDevice, str | None]]:
        """Conecta (em paralelo) às lâmpadas ativas e guarda o estado atual para restaurar no fim."""
        with self._lock:
            self._in_flight.clear()
            self._last_sent.clear()
            self._retry_at.clear()
            self._smoothers.clear()

        def prepare(device):
            try:
                with self._bulb_lock(device.id):
                    conn = self._connect_locked(device)
                    if hasattr(conn, "capture_state"):
                        conn.capture_state()
                return device, None
            except Exception as exc:
                self._drop(device.id)
                return device, friendly_error(exc)

        futures = [self._submit(prepare, d) for d in self.active_devices()]
        return [f.result() for f in futures if f is not None]

    def dispatch_frame(self, zone_colors: dict[str, tuple[int, int, int]], light_mode: bool = False,
                       dt: float = 0.05, smoothing: float = 0.0) -> dict[str, tuple[int, int, int]]:
        """Envia a cor de cada zona para as lâmpadas dela. Retorna {id: cor suavizada}."""
        now = time.monotonic()
        results = {}
        for device in self.active_devices():
            bid = device.id
            target = zone_colors.get(device.zone, zone_colors.get("all", (0, 0, 0)))
            with self._lock:
                smoothed = self._smoothers.setdefault(bid, Smoother()).update(target, dt, smoothing)
                results[bid] = smoothed
                conn = self.connections.get(bid)
                if bid in self._in_flight:
                    continue
                if conn is None:
                    if bid not in self._connecting and now >= self._retry_at.get(bid, 0.0):
                        self._connecting.add(bid)
                        self._submit(self._reconnect_task, device)
                    continue
                last_rgb, last_time = self._last_sent.get(bid, (None, 0.0))
                if not should_send(last_rgb, smoothed, now - last_time):
                    continue
                self._last_sent[bid] = (smoothed, now)
                self._in_flight.add(bid)
            if self._submit(self._send_frame_task, device, conn, smoothed, light_mode) is None:
                with self._lock:
                    self._in_flight.discard(bid)
        return results

    def _reconnect_task(self, device: BulbDevice):
        try:
            self.connect(device)
            self.on_event("reconnected", device)
        except Exception as exc:
            with self._lock:
                self._retry_at[device.id] = time.monotonic() + RETRY_DELAY
            self.on_event("bulb_error", (device, friendly_error(exc)))
        finally:
            with self._lock:
                self._connecting.discard(device.id)

    def _send_frame_task(self, device: BulbDevice, conn, rgb, light_mode):
        try:
            with self._bulb_lock(device.id):
                conn.color(rgb, light_mode=light_mode)
            self.power[device.id] = max(rgb) > 2
        except Exception as exc:
            log.warning("Falha ao enviar cor para %s: %s", device.name, exc)
            self._drop(device.id)
            with self._lock:
                self._retry_at[device.id] = time.monotonic() + 1.0
            self.on_event("bulb_error", (device, friendly_error(exc)))
        finally:
            with self._lock:
                self._in_flight.discard(device.id)

    def stop_cinema(self, restore: bool, timeout: float = 4.0):
        """Aguarda envios pendentes e, se pedido, devolve as lâmpadas ao estado de antes do cinema."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if not self._in_flight:
                    break
            time.sleep(0.02)
        if not restore:
            return
        with self._lock:
            targets = [(self.devices[b], c) for b, c in self.connections.items() if b in self.devices]
        futures = [self._submit(self._restore_task, d, c) for d, c in targets]
        for future in futures:
            if future is not None:
                try:
                    future.result(timeout=max(0.1, deadline + 4.0 - time.monotonic()))
                except Exception:
                    pass

    def _restore_task(self, device, conn):
        with self._bulb_lock(device.id):
            conn.restore()
        self.power[device.id] = None

    # ------------------------------------------------------------------ comandos manuais
    def apply(self, bulb_ids: list[str] | None, command: dict | Callable[[BulbDevice], dict]):
        """Aplica um comando {mode, rgb, brightness, temp} às lâmpadas (None = todas).

        ``command`` também pode ser uma função que recebe a lâmpada e devolve o comando,
        usada pelos cenários para dar cores diferentes a cada zona.
        """
        targets = [d for d in self.device_list() if bulb_ids is None or d.id in bulb_ids]
        if not targets:
            self.on_event("no_bulbs", None)
        for device in targets:
            cmd = command(device) if callable(command) else command
            self._submit(self._manual_task, device, cmd)

    def _manual_task(self, device: BulbDevice, cmd: dict):
        mode = cmd.get("mode", "colour")
        rgb = tuple(cmd["rgb"]) if cmd.get("rgb") else None
        kwargs = dict(rgb=rgb, brightness=int(cmd.get("brightness", 100)), temp=int(cmd.get("temp", 100)))
        for attempt in (1, 2):
            try:
                with self._bulb_lock(device.id):
                    conn = self._connect_locked(device)
                    conn.set_manual(mode, **kwargs)
                self.power[device.id] = mode != "off"
                self.on_event("applied", device)
                return
            except Exception as exc:
                self._drop(device.id)
                if attempt == 2:
                    self.on_event("bulb_error", (device, friendly_error(exc)))

    def turn_off(self, bulb_ids: list[str] | None = None):
        self.apply(bulb_ids, {"mode": "off"})

    # ------------------------------------------------------------------ encerramento
    def close(self):
        with self._lock:
            self._closed = True
            for bid in list(self.connections):
                self._close_unlocked(bid)
        self._executor.shutdown(wait=False, cancel_futures=True)


def friendly_error(exc: Exception) -> str:
    """Mensagem curta e segura para o usuário (sem detalhes internos da biblioteca)."""
    from .core import BulbError
    if isinstance(exc, BulbError):
        return str(exc)
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return "A lâmpada não respondeu na rede. Confira se ela está ligada na tomada e no Wi-Fi."
    return "Não foi possível falar com a lâmpada."

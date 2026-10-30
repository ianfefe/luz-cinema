"""Leitura e gravação das preferências, com migração das versões anteriores.

Tudo fica em ``dados/preferencias_v3.json``. As chaves locais das lâmpadas
são gravadas protegidas pela DPAPI do Windows (campo ``protected_key``), nunca em texto puro.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .devices import BulbDevice
from .windows import DATA_DIR, protect

log = logging.getLogger(__name__)

SCHEMA = 3
CONFIG_NAME = "preferencias_v3.json"
# Arquivos das edições Simples/Multi (3.0), em ordem de preferência na migração.
LEGACY_EDITIONS = ("preferencias_simples.json", "preferencias_multi.json")
LEGACY_V2 = "preferencias_v2.json"
LEGACY_V1 = "preferencias.json"

DEFAULTS = {
    "brightness": 45.0,
    "saturation": 140.0,
    "standout": 100.0,
    "smoothing": 0.0,
    "interval": 0.05,
    "crop": 10,
    "dark_percent": 5.0,
    "off_on_neutral": True,
    "flash_boost": True,
    "light_mode": False,
    "profile": "",
    "monitor_index": 0,
    "minimize_to_tray": True,
    "theme_mode": "dark",
    "live_manual": True,
    "manual_target": "",
    "custom_presets": [],
    "custom_scenarios": [],
    "devices": [],
}


def config_path(data_dir: Path | None = None) -> Path:
    return (data_dir or DATA_DIR) / CONFIG_NAME


def _encode_device(device: BulbDevice) -> dict:
    data = device.to_dict()
    key = data.pop("key", "")
    if key:
        try:
            data["protected_key"] = protect(key)
        except Exception:
            log.warning("Não foi possível proteger a chave de %s; ela não será salva.", device.name)
    return data


def _decode_device(raw: dict) -> BulbDevice | None:
    if not isinstance(raw, dict) or not str(raw.get("id", "")).strip():
        return None
    data = dict(raw)
    if data.get("protected_key"):
        try:
            data["key"] = protect(data["protected_key"], decrypt=True)
        except Exception:
            data["key"] = ""
    return BulbDevice.from_dict(data)


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except FileNotFoundError:
        return None
    except Exception as exc:
        log.warning("Preferências ilegíveis em %s: %s", path, exc)
        return None


def _normalize(data: dict) -> dict:
    result = dict(DEFAULTS)
    result.update({k: v for k, v in data.items() if k in DEFAULTS})
    devices: dict[str, BulbDevice] = {}
    for device in (_decode_device(x) for x in data.get("devices", [])):
        if device and device.id not in devices:
            devices[device.id] = device
    result["devices"] = list(devices.values())
    if len(devices) == 1:
        # Sozinha, a lâmpada acompanha a tela inteira (zonas só aparecem com duas ou mais).
        only = result["devices"][0]
        only.zone, only.enabled = "all", True
    for key in ("custom_presets", "custom_scenarios"):
        if not isinstance(result[key], list):
            result[key] = []
    return result


def _from_legacy_v1(data: dict) -> dict:
    """Converte o formato da v1 (uma lâmpada, chave protegida na raiz)."""
    migrated = {k: data[k] for k in ("brightness", "saturation", "custom_presets", "theme_mode") if k in data}
    if data.get("id"):
        migrated["devices"] = [{
            "id": data["id"],
            "name": "Lâmpada Principal",
            "connection_type": "local" if data.get("ip") else "cloud",
            "ip": data.get("ip", ""),
            "protected_key": data.get("protected_key", ""),
            "version": str(data.get("version", "3.5")),
        }]
    return migrated


def _device_from_tuya_session() -> list[dict]:
    """Versões antigas guardavam a lâmpada da nuvem só dentro da sessão Tuya."""
    from .tuya_link import SESSION_FILE
    try:
        session = json.loads(protect(SESSION_FILE.read_text(encoding="ascii"), decrypt=True))
    except Exception:
        return []
    device_id = session.get("device_id")
    if not device_id:
        return []
    bulb = session.get("bulb") or {}
    return [{"id": device_id, "name": bulb.get("name") or "Lâmpada Tuya", "connection_type": "cloud"}]


def _read_legacy(base: Path) -> dict | None:
    for name in (*LEGACY_EDITIONS, LEGACY_V2):
        data = _read_json(base / name)
        if data is not None:
            return data
    v1 = _read_json(base / LEGACY_V1)
    return _from_legacy_v1(v1) if v1 else None


def load(data_dir: Path | None = None) -> tuple[dict, bool]:
    """Carrega as preferências. Retorna (dados, migrado_de_versao_antiga)."""
    base = data_dir or DATA_DIR
    data = _read_json(config_path(base))
    migrated = False
    if data is None:
        legacy = _read_legacy(base)
        data = legacy or {}
        migrated = legacy is not None
        if not data.get("devices"):
            data["devices"] = _device_from_tuya_session()
    return _normalize(data), migrated


def save(data: dict, data_dir: Path | None = None):
    """Grava as preferências de forma atômica (arquivo temporário + troca)."""
    path = config_path(data_dir)
    payload = {k: data.get(k, DEFAULTS[k]) for k in DEFAULTS}
    payload["schema"] = SCHEMA
    payload["devices"] = [_encode_device(d) for d in data.get("devices", [])]
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)

"""Presets de cores de fábrica e utilitários de cores do Luz Cinema."""
from __future__ import annotations

from core import cct_to_rgb, rgb_to_hex

DEFAULT_PRESETS = [
    {"name": "Branco Frio", "mode": "white", "temp": 100, "brightness": 100, "color_hex": "#e0f2fe"},
    {"name": "Branco Neutro", "mode": "white", "temp": 50, "brightness": 100, "color_hex": "#fef3c7"},
    {"name": "Branco Quente", "mode": "white", "temp": 0, "brightness": 100, "color_hex": "#fed7aa"},
    {"name": "Luz Noturna", "mode": "white", "temp": 0, "brightness": 15, "color_hex": "#f97316"},
    {"name": "Ciano Neon", "mode": "colour", "rgb": (0, 229, 255), "brightness": 100, "color_hex": "#00e5ff"},
    {"name": "Vermelho Cinema", "mode": "colour", "rgb": (255, 17, 51), "brightness": 45, "color_hex": "#ff1133"},
    {"name": "Roxo Synthwave", "mode": "colour", "rgb": (153, 0, 255), "brightness": 100, "color_hex": "#9900ff"},
    {"name": "Verde Matrix", "mode": "colour", "rgb": (0, 255, 68), "brightness": 80, "color_hex": "#00ff44"},
    {"name": "Pôr do Sol", "mode": "colour", "rgb": (255, 102, 0), "brightness": 100, "color_hex": "#ff6600"},
    {"name": "Rosa Choque", "mode": "colour", "rgb": (255, 0, 128), "brightness": 100, "color_hex": "#ff0080"},
]


def preset_color_hex(preset: dict) -> str:
    """Retorna a cor hexadecimal representativa de qualquer preset (branco ou colorido)."""
    if preset.get("color_hex"):
        return preset["color_hex"]
    if preset.get("mode") == "white":
        return rgb_to_hex(cct_to_rgb(preset.get("temp", 100), preset.get("brightness", 100)))
    rgb = preset.get("rgb", (255, 255, 255))
    return rgb_to_hex((int(rgb[0]), int(rgb[1]), int(rgb[2])))

"""Presets de cor e perfis de calibração do modo cinema."""
from __future__ import annotations

from .core import cct_to_rgb, rgb_to_hex

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

CINEMA_PROFILES = [
    {
        "id": "marvel",
        "name": "🦸 Cinema Marvel / Ação",
        "short_name": "🦸 Marvel/Ação",
        "icon": "🦸",
        "brightness": 75.0,
        "saturation": 185.0,
        "standout": 90.0,
        "smoothing": 0.04,
        "interval": 0.05,
        "crop": 12,
        "dark_percent": 5.0,
        "off_on_neutral": True,
        "flash_boost": True,
        "light_mode": False,
        "description": "Cores ultra-vivas para blockbusters, trajes de heróis e efeitos de luz sem estroboscópio.",
    },
    {
        "id": "noir",
        "name": "🦇 Cinema Escuro / Noir",
        "short_name": "🦇 Escuro/Noir",
        "icon": "🦇",
        "brightness": 45.0,
        "saturation": 175.0,
        "standout": 100.0,
        "smoothing": 0.04,
        "interval": 0.05,
        "crop": 15,
        "dark_percent": 8.0,
        "off_on_neutral": True,
        "flash_boost": True,
        "light_mode": False,
        "description": "Para The Batman, suspense e terror. Quarto no breu total até surgir uma fonte de luz.",
    },
    {
        "id": "competitive",
        "name": "🎯 Jogo Competitivo (FPS)",
        "short_name": "🎯 Jogo FPS",
        "icon": "🎯",
        "brightness": 35.0,
        "saturation": 125.0,
        "standout": 70.0,
        "smoothing": 0.00,
        "interval": 0.04,
        "crop": 0,
        "dark_percent": 3.0,
        "off_on_neutral": False,
        "flash_boost": True,
        "light_mode": False,
        "description": "Zero lag instantâneo (~25 FPS), luz confortável que não ofusca a mira e flashbang 100%.",
    },
    {
        "id": "campaign",
        "name": "🎮 Jogo Campanha (RPG)",
        "short_name": "🎮 Jogo RPG",
        "icon": "🎮",
        "brightness": 70.0,
        "saturation": 180.0,
        "standout": 95.0,
        "smoothing": 0.06,
        "interval": 0.05,
        "crop": 5,
        "dark_percent": 5.0,
        "off_on_neutral": True,
        "flash_boost": True,
        "light_mode": False,
        "description": "Para Cyberpunk 2077, RDR2 e Elden Ring. Néons vivos, transições ricas e imersão pura.",
    },
    {
        "id": "web",
        "name": "🌐 Navegação Web / Trabalho",
        "short_name": "🌐 Web/Trabalho",
        "icon": "🌐",
        "brightness": 85.0,
        "saturation": 100.0,
        "standout": 30.0,
        "smoothing": 0.40,
        "interval": 0.25,
        "crop": 10,
        "dark_percent": 5.0,
        "off_on_neutral": False,
        "flash_boost": False,
        "light_mode": True,
        "description": "Modo claro CCT inteligente. Emite luz branca relaxante (2700K a 6500K) sem piscar.",
    },
    {
        "id": "youtube",
        "name": "📺 YouTube & Vídeos",
        "short_name": "📺 YouTube",
        "icon": "📺",
        "brightness": 55.0,
        "saturation": 145.0,
        "standout": 80.0,
        "smoothing": 0.10,
        "interval": 0.10,
        "crop": 6,
        "dark_percent": 5.0,
        "off_on_neutral": True,
        "flash_boost": False,
        "light_mode": False,
        "description": "Equilíbrio ideal para vídeos diversos, trailers, podcasts e gameplays.",
    },
]


def preset_color_hex(preset: dict) -> str:
    """Retorna a cor hexadecimal representativa de qualquer preset (branco ou colorido)."""
    if preset.get("color_hex"):
        return preset["color_hex"]
    if preset.get("mode") == "white":
        return rgb_to_hex(cct_to_rgb(preset.get("temp", 100), preset.get("brightness", 100)))
    rgb = preset.get("rgb", (255, 255, 255))
    return rgb_to_hex((int(rgb[0]), int(rgb[1]), int(rgb[2])))

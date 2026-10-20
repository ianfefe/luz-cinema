"""Sistema de Cenários de Iluminação para o Luz Cinema v2."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any
from core import rgb_to_hex, hex_to_rgb


@dataclass
class Scenario:
    id: str
    name: str
    description: str
    icon: str = "💡"
    default_mode: str = "colour"
    default_rgb: tuple[int, int, int] = (255, 255, 255)
    default_brightness: int = 100
    default_temp: int = 100
    # Mapeamento por zona ou ID de lâmpada: 'left', 'right', 'top', ou ID específico
    zone_colors: dict[str, dict[str, Any]] = field(default_factory=dict)
    is_custom: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Scenario:
        rgb = data.get("default_rgb", (255, 255, 255))
        if isinstance(rgb, list):
            rgb = tuple(rgb)
        return cls(
            id=data.get("id", ""),
            name=data.get("name", "Cenário"),
            description=data.get("description", ""),
            icon=data.get("icon", "💡"),
            default_mode=data.get("default_mode", "colour"),
            default_rgb=rgb,
            default_brightness=int(data.get("default_brightness", 100)),
            default_temp=int(data.get("default_temp", 100)),
            zone_colors=data.get("zone_colors", {}),
            is_custom=bool(data.get("is_custom", False)),
        )

    def get_color_for_bulb(self, bulb_id: str, zone: str = "all") -> dict[str, Any]:
        """Retorna o comando de luz (modo, rgb, brilho, temp) para uma lâmpada específica."""
        # 1. Verifica se há comando específico para este ID de lâmpada
        if bulb_id in self.zone_colors:
            return self.zone_colors[bulb_id]
        # 2. Verifica se há comando para a zona da lâmpada (ex: 'left', 'right', 'top')
        if zone in self.zone_colors:
            return self.zone_colors[zone]
        # 3. Fallback para as configurações padrão do cenário
        return {
            "mode": self.default_mode,
            "rgb": self.default_rgb,
            "brightness": self.default_brightness,
            "temp": self.default_temp,
        }


DEFAULT_SCENARIOS = [
    Scenario(
        id="cinema_setup",
        name="Setup Cinema",
        description="Azul profundo e roxo suave nas laterais, iluminação de sala de cinema.",
        icon="🎬",
        default_mode="colour",
        default_rgb=(10, 28, 80),
        default_brightness=40,
        zone_colors={
            "left": {"mode": "colour", "rgb": (15, 80, 255), "brightness": 45, "temp": 100},
            "right": {"mode": "colour", "rgb": (153, 0, 255), "brightness": 45, "temp": 100},
            "top": {"mode": "colour", "rgb": (80, 20, 180), "brightness": 35, "temp": 100},
            "all": {"mode": "colour", "rgb": (15, 60, 200), "brightness": 40, "temp": 100},
        },
    ),
    Scenario(
        id="cyberpunk",
        name="Cyberpunk Neon",
        description="Contraste sci-fi marcante entre Ciano Neon à esquerda e Magenta Choque à direita.",
        icon="👾",
        default_mode="colour",
        default_rgb=(170, 40, 255),
        default_brightness=90,
        zone_colors={
            "left": {"mode": "colour", "rgb": (0, 229, 255), "brightness": 100, "temp": 100},
            "right": {"mode": "colour", "rgb": (255, 0, 128), "brightness": 100, "temp": 100},
            "top": {"mode": "colour", "rgb": (140, 20, 255), "brightness": 80, "temp": 100},
        },
    ),
    Scenario(
        id="sunset",
        name="Pôr do Sol Dourado",
        description="Tons quentes e aconchegantes de laranja, âmbar e vermelho pôr do sol.",
        icon="🌆",
        default_mode="colour",
        default_rgb=(255, 120, 0),
        default_brightness=80,
        zone_colors={
            "left": {"mode": "colour", "rgb": (255, 70, 0), "brightness": 85, "temp": 100},
            "right": {"mode": "colour", "rgb": (255, 170, 0), "brightness": 85, "temp": 100},
            "top": {"mode": "colour", "rgb": (255, 130, 20), "brightness": 80, "temp": 100},
        },
    ),
    Scenario(
        id="reading",
        name="Leitura Relaxante",
        description="Luz branca quente aveludada (2700K) a 50% de brilho para descanso e leitura.",
        icon="📖",
        default_mode="white",
        default_rgb=(255, 180, 107),
        default_brightness=50,
        default_temp=0,
    ),
    Scenario(
        id="focus_work",
        name="Trabalho Focado",
        description="Branco frio vivo e nítido (6500K) com brilho total para máxima produtividade.",
        icon="💻",
        default_mode="white",
        default_rgb=(210, 230, 255),
        default_brightness=100,
        default_temp=100,
    ),
    Scenario(
        id="night_light",
        name="Luz Noturna",
        description="Luz âmbar ultra suave no brilho mínimo (10%) para a noite sem ofuscar.",
        icon="🌙",
        default_mode="white",
        default_rgb=(255, 150, 60),
        default_brightness=10,
        default_temp=0,
    ),
    Scenario(
        id="emerald_forest",
        name="Floresta Esmeralda",
        description="Verde esmeralda e menta suave para relaxamento e conexão com a natureza.",
        icon="🌲",
        default_mode="colour",
        default_rgb=(0, 220, 110),
        default_brightness=75,
        zone_colors={
            "left": {"mode": "colour", "rgb": (0, 240, 120), "brightness": 80, "temp": 100},
            "right": {"mode": "colour", "rgb": (0, 180, 180), "brightness": 80, "temp": 100},
        },
    ),
]

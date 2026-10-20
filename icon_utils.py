"""Utilitários de geração e renderização de ícones para janela, bandeja e roda de cores."""
from __future__ import annotations

import colorsys
import math
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFilter
from core import hex_to_rgb
from win_platform import APP_DIR


def create_color_wheel_image(size: int) -> Image.Image:
    """Gera a imagem de uma roda de cores HSV circular com transparência nos cantos."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    radius = size / 2.0
    pixels = img.load()
    for y in range(size):
        dy = y - radius
        for x in range(size):
            dx = x - radius
            dist = math.sqrt(dx * dx + dy * dy)
            if dist <= radius:
                alpha = 255
                if dist > radius - 1.0:
                    alpha = int(255 * (radius - dist))
                angle = math.atan2(dy, dx)
                hue = (angle / (2.0 * math.pi)) % 1.0
                sat = min(1.0, dist / radius)
                r, g, b = colorsys.hsv_to_rgb(hue, sat, 1.0)
                pixels[x, y] = (int(r * 255), int(g * 255), int(b * 255), alpha)
            else:
                pixels[x, y] = (0, 0, 0, 0)
    return img


def _gradient_badge(size: int, top_hex: str, bottom_hex: str, radius: int) -> Image.Image:
    """Cria um quadrado arredondado preenchido com gradiente vertical."""
    top, bottom = hex_to_rgb(top_hex), hex_to_rgb(bottom_hex)
    grad = Image.new("RGBA", (1, size))
    for y in range(size):
        k = y / (size - 1)
        grad.putpixel((0, y), tuple(round(a + (b - a) * k) for a, b in zip(top, bottom)) + (255,))
    grad = grad.resize((size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    badge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    badge.paste(grad, (0, 0), mask)
    return badge


def _draw_bulb(draw: ImageDraw.ImageDraw, color, outline=None, width=0):
    """Desenha a silhueta da lâmpada (bulbo e base metálica com rosca)."""
    # Bulbo: círculo grande para boa legibilidade mesmo em 16 px
    draw.ellipse((44, 22, 212, 190), fill=color, outline=outline, width=width)
    # Gargalo e base metálica
    draw.polygon([(92, 168), (164, 168), (152, 200), (104, 200)], fill=color, outline=outline)
    draw.rounded_rectangle((96, 198, 160, 236), radius=10, fill="#e2e8f0")
    draw.line((98, 211, 158, 211), fill="#64748b", width=6)
    draw.line((98, 224, 158, 224), fill="#64748b", width=6)


def render_icon(color_hex="#8b7bff", cinema_mode=False, is_off=False, size=64) -> Image.Image:
    """Renderiza o ícone do aplicativo/bandeja a 256 px e reduz para antialiasing nítido."""
    S = 256
    if cinema_mode:
        img = _gradient_badge(S, "#a855f7", "#e11d48", 58)
        d = ImageDraw.Draw(img)
        # Claquete de cinema inclinada com listras
        clap = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        cd = ImageDraw.Draw(clap)
        cd.rounded_rectangle((30, 46, 226, 102), radius=12, fill="#ffffff")
        for x in (70, 150):
            cd.polygon([(x, 46), (x + 40, 46), (x + 12, 102), (x - 28, 102)], fill="#3b0764")
        clap = clap.rotate(10, center=(34, 104), resample=Image.BICUBIC)
        img.alpha_composite(clap)
        # Corpo da claquete com triângulo de play
        d.rounded_rectangle((30, 112, 226, 226), radius=18, fill="#ffffff")
        d.polygon([(100, 132), (100, 206), (168, 169)], fill="#be185d")
    elif is_off:
        img = _gradient_badge(S, "#334155", "#1e293b", 58)
        d = ImageDraw.Draw(img)
        _draw_bulb(d, "#475569")
        d.line((52, 40, 204, 206), fill="#0f172a", width=30)
        d.line((52, 40, 204, 206), fill="#f87171", width=18)
    else:
        img = _gradient_badge(S, "#272f52", "#11141f", 58)
        r, g, b = hex_to_rgb(color_hex)
        # Brilho suave (halo) na cor da lâmpada
        halo = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        ImageDraw.Draw(halo).ellipse((22, 0, 234, 212), fill=(r, g, b, 110))
        img.alpha_composite(halo.filter(ImageFilter.GaussianBlur(18)))
        d = ImageDraw.Draw(img, "RGBA")
        _draw_bulb(d, (r, g, b))
        d.ellipse((78, 52, 122, 96), fill=(255, 255, 255, 150))
    return img.resize((size, size), Image.LANCZOS) if size != S else img


def create_tray_icon_image(color_hex="#8b7bff", cinema_mode=False, is_off=False) -> Image.Image:
    """Gera a imagem para exibição na bandeja do Windows."""
    return render_icon(color_hex, cinema_mode, is_off, size=64)


def export_ico(path: Path):
    """Exporta arquivo .ico multi-resolução para compilação do executável e atalhos."""
    big = render_icon(size=256)
    big.save(path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def get_icon_file() -> Path | None:
    """Localiza o arquivo luzcinema.ico no executável empacotado ou no diretório do projeto."""
    for base in (getattr(sys, "_MEIPASS", None), APP_DIR, Path(__file__).parent):
        if base:
            p = Path(base) / "luzcinema.ico"
            if p.exists():
                return p
    return None

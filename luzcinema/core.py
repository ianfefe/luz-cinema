"""Processamento de cor da tela e controle local de lâmpadas. Sem nuvem e sem salvar imagens."""
from __future__ import annotations

import colorsys
import ipaddress
import math
import threading
from dataclasses import dataclass, replace

from PIL import Image

SUPPORTED_VERSIONS = (3.1, 3.2, 3.3, 3.4, 3.5)
ZONES = ("all", "left", "right", "top", "bottom", "center")


@dataclass(frozen=True)
class Settings:
    brightness: float = 0.45
    saturation: float = 1.4
    standout: float = 1.0  # 0.0 (overall average) to 1.0 (focus on standout color)
    smoothing: float = 0.1  # seconds, time constant
    interval: float = 0.25
    crop_percent: int = 10
    dark_percent: float = 5.0  # perceptual source luminance, independent of bulb brightness
    off_on_neutral: bool = False  # Apagar lâmpada em cenas neutras / cinzas / P&B
    flash_boost: bool = False     # Clarão dinâmico (100% branco) em cenas super claras (flashbang)
    light_mode: bool = False      # Modo claro: iluminar telas/páginas brancas e quentes usando LEDs brancos de alta potência

    LIMITS = {"brightness": (0.05, 1), "saturation": (0, 3), "standout": (0, 1),
              "smoothing": (0.0, 4), "interval": (0.02, 2),
              "crop_percent": (0, 35), "dark_percent": (0, 20)}

    def __post_init__(self):
        for field, (low, high) in self.LIMITS.items():
            value = getattr(self, field)
            if not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"Ajuste inválido: {field}")

    @classmethod
    def clamped(cls, **values) -> "Settings":
        """Cria ajustes a partir de valores da interface/arquivo, limitando-os à faixa válida."""
        for field, (low, high) in cls.LIMITS.items():
            if field in values:
                value = float(values[field])
                value = low if not math.isfinite(value) else min(high, max(low, value))
                values[field] = round(value) if field == "crop_percent" else value
        return cls(**values)


def srgb_to_linear(x: float) -> float:
    return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4


def linear_to_srgb(x: float) -> float:
    return 12.92 * x if x <= 0.0031308 else 1.055 * (max(0.0, x) ** (1 / 2.4)) - 0.055


LINEAR_LUT = [srgb_to_linear(i / 255.0) for i in range(256)]
LUM_R_LUT = [0.2126 * i for i in range(256)]
LUM_G_LUT = [0.7152 * i for i in range(256)]
LUM_B_LUT = [0.0722 * i for i in range(256)]


def cct_to_rgb(temp_pct: float, brightness_pct: float = 100.0) -> tuple[int, int, int]:
    """Convert CCT temperature percentage (0=warm, 100=cold) and brightness to approximate RGB."""
    temp_ratio = max(0.0, min(1.0, temp_pct / 100.0))
    r = int(255 - temp_ratio * 45)
    g = int(180 + temp_ratio * 50)
    b = int(107 + temp_ratio * 148)
    br = max(0.01, min(1.0, brightness_pct / 100.0))
    return (round(r * br), round(g * br), round(b * br))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """Format RGB tuple as #RRGGBB."""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def hex_to_rgb(color_hex: str) -> tuple[int, int, int]:
    """Parse #RRGGBB hex string to (R, G, B) tuple."""
    color_hex = color_hex.lstrip("#")
    return tuple(int(color_hex[i:i + 2], 16) for i in (0, 2, 4))


def interpolate_hue(h1: float, h2: float, t: float) -> float:
    """Interpolate between two hues taking the shortest path on the circle [0, 1)."""
    diff = (h2 - h1 + 0.5) % 1.0 - 0.5
    return (h1 + diff * t) % 1.0


def is_white_cct_candidate(rgb: tuple[int, int, int]) -> bool:
    """Determine whether an RGB color should be treated as white/warm CCT."""
    h, s, v = colorsys.rgb_to_hsv(*(c / 255.0 for c in rgb))
    h_deg = h * 360.0
    return (v >= 0.25) and (s <= 0.38) and (h_deg <= 70.0 or h_deg >= 330.0 or s <= 0.12)


def calc_cct_values(rgb: tuple[int, int, int], bmax: int = 100, tmax: int = 100) -> tuple[int, int]:
    """Calculate brightness and temperature values for white CCT LEDs."""
    h, s, v = colorsys.rgb_to_hsv(*(c / 255.0 for c in rgb))
    if s <= 0.08:
        temp = tmax
    else:
        t_factor = max(0.0, min(1.0, 1.0 - (s - 0.08) / 0.28))
        temp = round(t_factor * tmax)
    bright = round(max(round(bmax * 0.1), min(bmax, v * bmax)))
    return bright, temp


def screen_color(frame: Image.Image, settings: Settings, was_dark: bool = False) -> tuple[int, int, int]:
    """Extract screen color focusing on the standout vibrant hue (AuraSync-style).

    - Identifies the most salient/vibrant color that stands out against neutral backgrounds.
    - Preserves dark scene dimming/cutoff without black frame purple glow.
    - Turns off on desaturated/grey/black-and-white scenes if off_on_neutral is enabled.
    - Surges to maximum bright white for flashbangs/light explosions if flash_boost is enabled.
    - Top/bottom crop removes common letterbox bars and subtitle overlays.
    """
    if frame.mode != "RGB":
        frame = frame.convert("RGB")
    w, h = frame.size
    trim = int(h * settings.crop_percent / 100)
    if trim > 0:
        frame = frame.crop((0, trim, w, h - trim))
    resample_filter = getattr(Image, "BOX", Image.BILINEAR)
    frame = frame.resize((80, 45), resample=resample_filter)

    pixels = frame.get_flattened_data() if hasattr(frame, "get_flattened_data") else frame.getdata()

    total_luminance = 0.0
    count = 0

    NUM_BINS = 16
    bin_weights = [0.0] * NUM_BINS
    bin_r = [0.0] * NUM_BINS
    bin_g = [0.0] * NUM_BINS
    bin_b = [0.0] * NUM_BINS

    scene_r = 0.0
    scene_g = 0.0
    scene_b = 0.0
    scene_w = 0.0

    for r, g, b in pixels:
        lum = LUM_R_LUT[r] + LUM_G_LUT[g] + LUM_B_LUT[b]
        total_luminance += lum
        count += 1

        lin_r = LINEAR_LUT[r]
        lin_g = LINEAR_LUT[g]
        lin_b = LINEAR_LUT[b]

        high = max(r, g, b)
        low = min(r, g, b)
        chroma = high - low

        # General scene average in linear light
        sat = chroma / high if high > 0 else 0.0
        base_w = 1.0 + 0.6 * sat
        scene_r += lin_r * base_w
        scene_g += lin_g * base_w
        scene_b += lin_b * base_w
        scene_w += base_w

        # Chromatic salience for standout color detection
        if high > 10 and chroma > 5:
            val = high / 255.0
            # Strongly prioritize high saturation to capture the standout accent
            salience = (sat ** 2.4) * (val ** 0.8)

            if chroma == 0:
                h_deg = 0.0
            elif high == r:
                h_deg = (60.0 * ((g - b) / chroma)) % 360.0
            elif high == g:
                h_deg = (60.0 * ((b - r) / chroma) + 120.0) % 360.0
            else:
                h_deg = (60.0 * ((r - g) / chroma) + 240.0) % 360.0

            bin_idx = int(h_deg / (360.0 / NUM_BINS)) % NUM_BINS
            bin_weights[bin_idx] += salience
            bin_r[bin_idx] += lin_r * salience
            bin_g[bin_idx] += lin_g * salience
            bin_b[bin_idx] += lin_b * salience

    # Dark cutoff check with hysteresis
    avg_lum_ratio = total_luminance / (count * 255.0)
    if settings.dark_percent > 0:
        threshold = settings.dark_percent + (1.5 if was_dark else 0.0)
        if avg_lum_ratio * 100.0 < threshold:
            return (0, 0, 0)

    # Calculate overall scene average RGB
    avg_scene_lin = [scene_r / max(scene_w, 1e-6), scene_g / max(scene_w, 1e-6), scene_b / max(scene_w, 1e-6)]
    avg_scene_rgb = [linear_to_srgb(c) for c in avg_scene_lin]
    scene_h, scene_s, scene_v = colorsys.rgb_to_hsv(*[max(0.0, min(1.0, c)) for c in avg_scene_rgb])

    # Smooth bin energy with circular wrapping across the hue circle
    smoothed = [0.0] * NUM_BINS
    for i in range(NUM_BINS):
        prev_i = (i - 1) % NUM_BINS
        next_i = (i + 1) % NUM_BINS
        smoothed[i] = 0.25 * bin_weights[prev_i] + 0.5 * bin_weights[i] + 0.25 * bin_weights[next_i]

    best_bin = 0
    best_energy = smoothed[0]
    for i in range(1, NUM_BINS):
        if smoothed[i] > best_energy:
            best_energy = smoothed[i]
            best_bin = i

    total_salience = sum(bin_weights)
    has_standout = (settings.standout > 0.01) and (total_salience > 1.2) and (best_energy > 0.4)

    if has_standout:
        cluster_w = 0.0
        cluster_r = 0.0
        cluster_g = 0.0
        cluster_b = 0.0
        for offset in (-1, 0, 1):
            idx = (best_bin + offset) % NUM_BINS
            w_bin = bin_weights[idx]
            cluster_w += w_bin
            cluster_r += bin_r[idx]
            cluster_g += bin_g[idx]
            cluster_b += bin_b[idx]

        if cluster_w > 0:
            cluster_lin = [cluster_r / cluster_w, cluster_g / cluster_w, cluster_b / cluster_w]
            cluster_srgb = [linear_to_srgb(c) for c in cluster_lin]
            cand_h, cand_s, cand_v = colorsys.rgb_to_hsv(*[max(0.0, min(1.0, c)) for c in cluster_srgb])
        else:
            cand_h, cand_s, cand_v = scene_h, scene_s, scene_v
            has_standout = False
    else:
        cand_h, cand_s, cand_v = scene_h, scene_s, scene_v

    # Check for Flashbang / Clarão (very bright screen / white explosion)
    is_flash = settings.flash_boost and (avg_lum_ratio >= 0.70 or scene_v >= 0.85)

    # Check for neutral / grey / black & white scene
    is_neutral = (not has_standout) and (scene_s < 0.18)

    # If the scene is grey/black-and-white and NOT a flashbang, turn OFF as requested
    # Em modo claro, páginas e telas claras (sites, documentos) permanecem acesas
    if is_neutral and settings.off_on_neutral and not is_flash:
        if not (settings.light_mode and scene_v >= 0.28):
            return (0, 0, 0)

    # Dynamic Flashbang Clarão Burst:
    # If the scene is an intense flash, scale brightness towards 100% (true clarão)
    if is_flash:
        surge = max(0.0, min(1.0, (avg_lum_ratio - 0.65) / 0.25))
        effective_brightness = (1.0 - surge) * settings.brightness + surge * 1.0
    elif settings.light_mode and scene_s <= 0.35 and scene_v >= 0.35:
        # Modo claro: telas e páginas brancas/quentes iluminam o quarto adequadamente
        effective_brightness = min(1.0, settings.brightness * 1.35)
    else:
        effective_brightness = settings.brightness

    # Blend between scene average and standout candidate
    t_standout = settings.standout if has_standout else 0.0

    if t_standout > 0.0:
        base_h = interpolate_hue(scene_h, cand_h, t_standout)
        base_s = (1.0 - t_standout) * scene_s + t_standout * cand_s

        # Standout vibrancy boost on saturation:
        # Pushes moderate saturation up to achieve rich, vivid ambilight lighting on the bulb
        boosted_s = min(1.0, (base_s ** 0.75) * settings.saturation)
        final_s = max(base_s, boosted_s)

        standout_factor = min(1.0, total_salience / 40.0)
        target_v = max(scene_v * 0.7, min(cand_v, scene_v * (1.0 + 0.6 * standout_factor)))
        final_v = (1.0 - t_standout) * scene_v + t_standout * target_v
        final_h = base_h
    else:
        final_h = scene_h
        final_s = min(1.0, scene_s * settings.saturation)
        final_v = scene_v

    out_rgb = colorsys.hsv_to_rgb(final_h, final_s, final_v * effective_brightness)
    return tuple(max(0, min(255, round(c * 255))) for c in out_rgb)


class Smoother:
    def __init__(self):
        self.value = None

    def update(self, target, dt, tau):
        if max(target) == 0:
            self.value = (0.0, 0.0, 0.0)
            return (0, 0, 0)
        # Intense white flash (flashbang) bursts instantly without lag, or zero smoothing
        if min(target) >= 245 or tau <= 0.01:
            self.value = tuple(float(v) for v in target)
            return target
        alpha = 1 - math.exp(-min(max(dt, 0), 1) / tau)
        if self.value is None:
            self.value = tuple(float(v) for v in target)
        else:
            self.value = tuple(a + alpha * (b - a) for a, b in zip(self.value, target))
        return tuple(round(v) for v in self.value)


def should_send(previous, current, elapsed):
    """Always transmit off/on edges, even when their RGB delta is tiny."""
    if previous is None:
        return True
    if (max(previous) <= 2) != (max(current) <= 2):
        return True
    return max(abs(a-b) for a,b in zip(previous,current)) >= 3 or elapsed >= 8


class BulbError(Exception):
    pass


class LocalBulb:
    """Controle local (LAN) de uma lâmpada Tuya: thread-safe, com reconexão e restauração do estado."""

    RESTORE_FIELDS = ("switch", "mode", "brightness", "colourtemp", "colour", "scene", "scene_data")

    def __init__(self, device_id, ip, key, version, factory=None):
        if not str(device_id).strip() or len(str(key).encode("utf-8")) != 16:
            raise BulbError("Preencha o ID e a chave local de 16 caracteres da lâmpada.")
        try:
            address = ipaddress.ip_address(str(ip).strip())
            if (address.version != 4 or not address.is_private or address.is_loopback
                    or address.is_unspecified or address.is_multicast or address.is_link_local):
                raise ValueError()
        except ValueError:
            raise BulbError("Informe o endereço IPv4 da lâmpada na sua rede local.") from None
        try:
            parsed_version = float(version)
        except (TypeError, ValueError):
            parsed_version = 0.0
        if parsed_version not in SUPPORTED_VERSIONS:
            raise BulbError("Versão de protocolo inválida.")
        if factory is None:
            import tinytuya
            factory = tinytuya.BulbDevice

        self.device_id = str(device_id).strip()
        self.ip = str(address)
        self.key = key
        self.version = parsed_version
        self.factory = factory
        self._lock = threading.Lock()
        self.original = {}
        self.switch_dp = None
        self.off = False
        self.device = None
        try:
            self._open()
            self._capture_unlocked(require_rgb=True)
        except Exception:
            self.close()
            raise

    def _open(self):
        self.device = self.factory(self.device_id, self.ip, self.key)
        self.device.set_socketTimeout(1.5)
        self.device.set_socketRetryLimit(1)
        self.device.set_socketRetryDelay(0.1)
        self.device.set_socketPersistent(True)
        self.device.set_version(self.version)

    def _capture_unlocked(self, require_rgb=False):
        status = self.device.status()
        self.check(status)
        if not isinstance(status.get("dps"), dict):
            raise BulbError("A lâmpada não respondeu com um estado válido.")
        if require_rgb and (not self.device.has_colour or self.device.bulb_type not in ("A", "B")):
            raise BulbError("Este dispositivo não apresentou controle RGB local compatível.")
        dps = status["dps"]
        mapping = self.device.dpset
        self.switch_dp = str(mapping["switch"])
        original = {str(mapping[k]): dps[str(mapping[k])] for k in self.RESTORE_FIELDS
                    if mapping.get(k) and str(mapping[k]) in dps}
        if self.switch_dp not in original or str(mapping["mode"]) not in original:
            raise BulbError("Não foi possível ler o estado necessário para restaurar a lâmpada.")
        self.original = original
        self.off = not bool(dps.get(self.switch_dp, True))

    def capture_state(self):
        """Relê o estado atual da lâmpada para restaurá-lo depois (ex.: ao iniciar o cinema)."""
        with self._lock:
            self._with_reconnect(self._capture_unlocked)

    def reconnect(self) -> bool:
        with self._lock:
            return self._reconnect_unlocked()

    def _reconnect_unlocked(self) -> bool:
        try:
            if self.device:
                self.device.close()
        except Exception:
            pass
        try:
            self._open()
            status = self.device.status()
            return isinstance(status, dict) and "dps" in status
        except Exception:
            return False

    def _with_reconnect(self, action, *args, **kwargs):
        try:
            return action(*args, **kwargs)
        except Exception:
            # Socket caído ou corrompido: tenta recuperar uma única vez.
            if self._reconnect_unlocked():
                return action(*args, **kwargs)
            raise

    @staticmethod
    def check(result):
        if not isinstance(result, dict) or "Error" in result or "Err" in result:
            # Não exibe a resposta crua da biblioteca: ela pode conter segredos do dispositivo.
            raise BulbError("Sem resposta válida da lâmpada. Confira IP, chave e protocolo; feche o app do fabricante e tente novamente.")

    def _white(self, brightness_pct, temp_pct):
        if hasattr(self.device, "set_white_percentage"):
            self.check(self.device.set_white_percentage(int(brightness_pct), int(temp_pct)))
        else:
            self.check(self.device.set_mode("white"))
            self.check(self.device.set_brightness_percentage(int(brightness_pct)))
        self.off = False

    def _colour(self, rgb):
        self.check(self.device.set_colour(*rgb))
        self.off = False

    def _turn_off(self):
        if not self.off:
            self.check(self.device.turn_off())
            self.off = True

    def color(self, rgb, light_mode=False):
        """Envia uma cor do modo cinema (preto apaga; clarão e páginas claras usam LEDs brancos)."""
        with self._lock:
            self._with_reconnect(self._send_frame, rgb, light_mode)

    def _send_frame(self, rgb, light_mode):
        if max(rgb) <= 2:
            self._turn_off()
        elif min(rgb) >= 245:
            self._white(100, 100)
        elif light_mode and is_white_cct_candidate(rgb):
            self._white(*calc_cct_values(rgb, 100, 100))
        else:
            self._colour(rgb)

    def set_manual(self, mode, rgb=None, brightness=100, temp=100):
        with self._lock:
            self._with_reconnect(self._send_manual, mode, rgb, brightness, temp)

    def _send_manual(self, mode, rgb, brightness, temp):
        if mode == "off":
            self.check(self.device.turn_off())
            self.off = True
        elif mode == "white":
            self._white(brightness, temp)
        elif rgb:
            self._colour(rgb)

    def restore(self):
        with self._lock:
            if self.original:
                try:
                    self._with_reconnect(lambda: self.check(self.device.set_multiple_values(self.original)))
                except Exception:
                    pass

    def close(self):
        with self._lock:
            try:
                if self.device:
                    self.device.close()
            except Exception:
                pass


def downscale_frame(frame: Image.Image, width: int = 320) -> Image.Image:
    """Reduz a captura uma única vez antes de recortar as zonas (bem mais rápido em telas 4K)."""
    if frame.mode != "RGB":
        frame = frame.convert("RGB")
    w, h = frame.size
    if w <= width:
        return frame
    height = max(1, round(h * width / w))
    return frame.resize((width, height), resample=getattr(Image, "BOX", Image.BILINEAR))


def crop_zone(frame: Image.Image, zone: str, crop_percent: int = 10) -> Image.Image:
    """
    Recorta a zona espacial desejada do frame da tela:
    - 'all': tela inteira (com corte de margem/letterbox no topo e na base)
    - 'left': metade esquerda (0% a 55% da largura, com leve sobreposição central)
    - 'right': metade direita (45% a 100% da largura)
    - 'top': metade superior da tela útil
    - 'bottom': metade inferior da tela útil
    - 'center': região central (25% a 75% da largura e altura)
    """
    w, h = frame.size
    margin = round(h * (crop_percent / 100.0)) if crop_percent else 0
    y0 = margin
    y1 = max(y0 + 1, h - margin)

    if zone == "left":
        x0 = 0
        x1 = max(1, round(w * 0.55))
    elif zone == "right":
        x0 = min(w - 1, round(w * 0.45))
        x1 = w
    elif zone == "top":
        x0 = 0
        x1 = w
        y1 = max(y0 + 1, round(y0 + (y1 - y0) * 0.50))
    elif zone == "bottom":
        x0 = 0
        x1 = w
        y0 = min(y1 - 1, round(y0 + (y1 - y0) * 0.50))
    elif zone == "center":
        x0 = round(w * 0.25)
        x1 = max(x0 + 1, round(w * 0.75))
        y_mid0 = round(y0 + (y1 - y0) * 0.25)
        y_mid1 = max(y_mid0 + 1, round(y0 + (y1 - y0) * 0.75))
        return frame.crop((x0, y_mid0, x1, y_mid1))
    else:  # "all" ou padrão
        x0 = 0
        x1 = w

    return frame.crop((x0, y0, x1, y1))


def compute_zones_colors(
    frame: Image.Image,
    settings: Settings,
    zones: set[str],
    was_dark_map: dict[str, bool] | None = None,
) -> dict[str, tuple[int, int, int]]:
    """Calcula a cor representativa para cada uma das zonas espaciais solicitadas."""
    results: dict[str, tuple[int, int, int]] = {}
    for z in zones:
        sub_frame = crop_zone(frame, z, settings.crop_percent)
        sub_settings = replace(settings, crop_percent=0)
        is_dark_prev = was_dark_map.get(z, False) if was_dark_map else False
        results[z] = screen_color(sub_frame, sub_settings, was_dark=is_dark_prev)
    return results


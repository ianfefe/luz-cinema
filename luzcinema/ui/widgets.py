"""Componentes visuais reutilizáveis: página rolável, cartões, sliders, roda de cores e prévia da tela."""
from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

from ..core import hex_to_rgb, rgb_to_hex
from .icons import create_color_wheel_image
from .theme import FONT, FONT_SEMIBOLD, Theme


def mix(color_a: str, color_b: str, t: float) -> str:
    """Interpola duas cores #rrggbb (t=0 → a, t=1 → b)."""
    a, b = hex_to_rgb(color_a), hex_to_rgb(color_b)
    return rgb_to_hex(tuple(round(x + (y - x) * t) for x, y in zip(a, b)))


class ScrollPage(ttk.Frame):
    """Página com rolagem vertical; o conteúdo vai em ``self.body``."""

    def __init__(self, parent, theme: Theme, padding=(28, 24, 28, 28)):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.body = ttk.Frame(self.canvas, padding=padding)
        self._window = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body.bind("<Configure>", lambda _: self._update_region())
        self.canvas.bind("<Configure>", self._on_resize)
        theme.bind(lambda t: self.canvas.configure(bg=t["BG"]))

    def _on_resize(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)
        self._update_region()

    def _update_region(self):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_scroll(self, first, last):
        self.scrollbar.set(first, last)
        needed = float(first) > 0 or float(last) < 1
        if needed and not self.scrollbar.winfo_ismapped():
            self.scrollbar.pack(side="right", fill="y")
        elif not needed and self.scrollbar.winfo_ismapped():
            self.scrollbar.pack_forget()

    def scroll(self, event):
        """Chamado pela janela principal para a roda do mouse na página visível."""
        if self.scrollbar.winfo_ismapped():
            widget = event.widget
            # Não rola a página quando o usuário gira a roda dentro de uma lista suspensa.
            if isinstance(widget, str) or widget.winfo_class() in ("TCombobox", "Listbox"):
                return
            self.canvas.yview_scroll(int(-event.delta / 120), "units")


def card(parent, padding=18) -> ttk.Frame:
    """Cartão com borda de 1 px. Retorna o frame interno onde o conteúdo deve ser colocado."""
    border = ttk.Frame(parent, style="CardBorder.TFrame", padding=1)
    inner = ttk.Frame(border, style="Card.TFrame", padding=padding)
    inner.pack(fill="both", expand=True)
    inner.outer = border
    return inner


def section_header(parent, title: str, subtitle: str = "", style_prefix: str = "") -> ttk.Frame:
    box = ttk.Frame(parent, style="Card.TFrame" if style_prefix else "TFrame")
    ttk.Label(box, text=title, style=f"{style_prefix}H2.TLabel").pack(anchor="w")
    if subtitle:
        ttk.Label(box, text=subtitle, style="CardMuted.TLabel" if style_prefix else "Muted.TLabel",
                  wraplength=560, justify="left").pack(anchor="w", pady=(2, 0))
    return box


class Slider(ttk.Frame):
    """Linha de ajuste com rótulo, valor formatado e dica opcional, dentro de um cartão."""

    def __init__(self, parent, label: str, variable: tk.Variable, low: float, high: float,
                 fmt=lambda v: f"{v:.0f}%", hint: str = "", resolution: float | None = None):
        super().__init__(parent, style="Card.TFrame")
        self.variable = variable
        self.fmt = fmt
        self.resolution = resolution
        top = ttk.Frame(self, style="Card.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text=label, style="CardStrong.TLabel").pack(side="left")
        self.value_label = ttk.Label(top, style="CardValue.TLabel")
        self.value_label.pack(side="right")
        self.scale = ttk.Scale(self, from_=low, to=high, variable=variable, style="Card.Horizontal.TScale",
                               command=self._snap)
        self.scale.pack(fill="x", pady=(4, 0))
        if hint:
            ttk.Label(self, text=hint, style="CardMuted.TLabel", wraplength=520, justify="left").pack(anchor="w")
        variable.trace_add("write", lambda *_: self._display())
        self._display()

    def _snap(self, _value):
        if self.resolution:
            value = round(float(self.variable.get()) / self.resolution) * self.resolution
            if abs(value - float(self.variable.get())) > 1e-9:
                self.variable.set(round(value, 4))

    def _display(self):
        try:
            self.value_label.configure(text=self.fmt(float(self.variable.get())))
        except (tk.TclError, ValueError):
            pass

    def state(self, statespec=None):
        return self.scale.state(statespec)


class Swatch(tk.Canvas):
    """Círculo de cor (com anel), usado em presets, lâmpadas e cenários."""

    def __init__(self, parent, theme: Theme, color="#000000", size=18, bg_token="CARD"):
        super().__init__(parent, width=size, height=size, highlightthickness=0, borderwidth=0)
        self.size = size
        self.color = color
        self._oval = self.create_oval(1, 1, size - 1, size - 1, fill=color, width=1)
        theme.bind(lambda t: (self.configure(bg=t[bg_token]), self.itemconfigure(self._oval, outline=t["BORDER"])))

    def set(self, color: str):
        if color != self.color:
            self.color = color
            self.itemconfigure(self._oval, fill=color)


class Tile(tk.Frame):
    """Cartão clicável (cenários e presets) com amostra de cor, título e descrição."""

    def __init__(self, parent, theme: Theme, title: str, subtitle: str = "", color: str = "#888888",
                 icon: str = "", command=None, on_delete=None):
        super().__init__(parent, highlightthickness=1, borderwidth=0, cursor="hand2")
        self.theme = theme
        self.command = command
        self._hover = False
        self.swatch = Swatch(self, theme, color, size=28)
        self.swatch.grid(row=0, column=0, rowspan=2, padx=(14, 12), pady=12, sticky="w")
        self.title = tk.Label(self, text=f"{icon}  {title}".strip(), font=(FONT_SEMIBOLD, 10), anchor="w")
        self.title.grid(row=0, column=1, sticky="sw", pady=(12 if subtitle else 0, 0))
        self.subtitle = tk.Label(self, text=subtitle, font=(FONT, 9), anchor="w", justify="left", wraplength=240)
        if subtitle:
            self.subtitle.grid(row=1, column=1, sticky="nw", pady=(0, 12), padx=(0, 10))
        else:
            self.title.grid_configure(rowspan=2, sticky="w")
        self.columnconfigure(1, weight=1)
        self.delete_button = None
        if on_delete:
            self.delete_button = tk.Label(self, text="✕", font=(FONT, 10), cursor="hand2", padx=10)
            self.delete_button.grid(row=0, column=2, rowspan=2, sticky="ns")
            self.delete_button.bind("<Button-1>", lambda _: on_delete())
        for widget in (self, self.title, self.subtitle, self.swatch):
            widget.bind("<Button-1>", self._click)
            widget.bind("<Enter>", lambda _: self._set_hover(True))
            widget.bind("<Leave>", lambda _: self._set_hover(False))
        theme.bind(self._paint)

    def _click(self, _event):
        if self.command:
            self.command()

    def _set_hover(self, value):
        self._hover = value
        self._paint(self.theme.t)

    def _paint(self, t):
        bg = t["CARD_HOVER"] if self._hover else t["CARD"]
        self.configure(bg=bg, highlightbackground=t["ACCENT"] if self._hover else t["BORDER"], highlightcolor=t["ACCENT"])
        self.title.configure(bg=bg, fg=t["FG"])
        self.subtitle.configure(bg=bg, fg=t["MUTED"])
        self.swatch.configure(bg=bg)
        if self.delete_button:
            self.delete_button.configure(bg=bg, fg=t["MUTED"])


class ColorWheel:
    """Roda de matiz/saturação clicável e arrastável."""

    def __init__(self, canvas: tk.Canvas, size: int, on_color_change):
        self.canvas = canvas
        self.size = size
        self.radius = size / 2.0
        self.on_color_change = on_color_change
        self.photo = ImageTk.PhotoImage(create_color_wheel_image(size), master=canvas)
        canvas.create_image(self.radius, self.radius, image=self.photo)
        self.cursor_outer = canvas.create_oval(0, 0, 16, 16, outline="#000000", width=2)
        self.cursor = canvas.create_oval(0, 0, 14, 14, outline="#ffffff", width=2)
        canvas.bind("<Button-1>", self._pick)
        canvas.bind("<B1-Motion>", self._pick)
        self.set_color_hsv(0.0, 1.0)

    def _pick(self, event):
        dx, dy = event.x - self.radius, event.y - self.radius
        sat = min(1.0, math.hypot(dx, dy) / self.radius)
        hue = (math.atan2(dy, dx) / (2.0 * math.pi)) % 1.0
        self.set_color_hsv(hue, sat)
        self.on_color_change(hue, sat)

    def set_color_hsv(self, hue: float, sat: float):
        angle = hue * 2.0 * math.pi
        dist = max(0.0, min(1.0, sat)) * (self.radius - 2)
        cx = self.radius + math.cos(angle) * dist
        cy = self.radius + math.sin(angle) * dist
        self.canvas.coords(self.cursor_outer, cx - 8, cy - 8, cx + 8, cy + 8)
        self.canvas.coords(self.cursor, cx - 7, cy - 7, cx + 7, cy + 7)


class ScreenPreview(tk.Canvas):
    """Ilustração do monitor com o brilho ambiente ao redor, atualizada em tempo real.

    O brilho é desenhado com Pillow em baixa resolução e desfocado, o que dá um degradê suave.
    Na edição Multi cada lado brilha com a cor da sua zona e as zonas aparecem dentro da tela.
    """

    DOWNSCALE = 4

    def __init__(self, parent, theme: Theme, show_zones: bool, height=230):
        super().__init__(parent, height=height, highlightthickness=0, borderwidth=0)
        self.theme = theme
        self.show_zones = show_zones
        self.colors: dict[str, str] = {}
        self._items: dict[str, int] = {}
        self._geometry = None
        self._glow_photo = None
        self._glow_key = None
        self.bind("<Configure>", lambda _: self._draw())
        theme.bind(lambda t: self._draw())

    def set_colors(self, zone_colors: dict[str, tuple[int, int, int]] | None):
        """Atualiza as cores (None = parado)."""
        self.colors = {z: rgb_to_hex(c) for z, c in (zone_colors or {}).items()}
        self._paint()

    def _draw(self):
        self.delete("all")
        self._items.clear()
        self._glow_key = None
        t = self.theme.t
        w, h = max(self.winfo_width(), 200), max(self.winfo_height(), 120)
        self.configure(bg=t["CARD"])
        sh = h * 0.6
        sw = min(w * 0.6, sh * 16 / 9)
        x0, y0 = (w - sw) / 2, (h - sh) / 2 - 8
        x1, y1 = x0 + sw, y0 + sh
        self._geometry = (w, h, x0, y0, x1, y1)
        self._items["glow"] = self.create_image(0, 0, anchor="nw")
        self.create_rectangle(x0 - 6, y0 - 6, x1 + 6, y1 + 6, fill="#0b0c10", outline="#2b2f3a", width=2)
        self.create_rectangle(x0, y0, x1, y1, fill=t["SCREEN"], width=0)
        if self.show_zones:
            zx, zy = sw * 0.2, sh * 0.24
            boxes = {
                "top": (x0 + zx, y0, x1 - zx, y0 + zy),
                "bottom": (x0 + zx, y1 - zy, x1 - zx, y1),
                "left": (x0, y0, x0 + zx, y1),
                "right": (x1 - zx, y0, x1, y1),
                "center": (x0 + sw * 0.36, y0 + sh * 0.36, x1 - sw * 0.36, y1 - sh * 0.36),
            }
            for zone, box in boxes.items():
                self._items[zone] = self.create_rectangle(*box, width=0)
        cx = (x0 + x1) / 2
        self.create_rectangle(cx - 6, y1 + 6, cx + 6, y1 + 18, fill="#2b2f3a", width=0)
        self.create_rectangle(cx - 34, y1 + 18, cx + 34, y1 + 23, fill="#2b2f3a", width=0)
        self._items["label"] = self.create_text(cx, (y0 + y1) / 2, fill="#cfd3dc", font=(FONT_SEMIBOLD, 10))
        self._paint()

    def _render_glow(self):
        from PIL import Image, ImageDraw, ImageFilter

        t = self.theme.t
        w, h, x0, y0, x1, y1 = self._geometry
        k = self.DOWNSCALE
        img = Image.new("RGB", (max(1, round(w / k)), max(1, round(h / k))), hex_to_rgb(t["CARD"]))
        draw = ImageDraw.Draw(img)
        x0, y0, x1, y1 = x0 / k, y0 / k, x1 / k, y1 / k
        spread = min(w, h) * 0.22 / k

        def glow(color, box):
            if color and max(hex_to_rgb(color)) > 6:
                draw.rectangle(box, fill=mix(t["CARD"], color, 0.9))

        glow(self.colors.get("all"), (x0 - spread, y0 - spread * 0.4, x1 + spread, y1 + spread * 0.4))
        if self.show_zones:
            mid_x, mid_y = (x0 + x1) / 2, (y0 + y1) / 2
            glow(self.colors.get("top"), (x0 + spread, y0 - spread * 0.6, x1 - spread, mid_y))
            glow(self.colors.get("bottom"), (x0 + spread, mid_y, x1 - spread, y1 + spread * 0.6))
            glow(self.colors.get("left"), (x0 - spread * 1.3, y0 - spread * 0.4, mid_x - spread, y1 + spread * 0.4))
            glow(self.colors.get("right"), (mid_x + spread, y0 - spread * 0.4, x1 + spread * 1.3, y1 + spread * 0.4))
        img = img.filter(ImageFilter.GaussianBlur(spread * 0.75)).resize((w, h), Image.BILINEAR)
        self._glow_photo = ImageTk.PhotoImage(img, master=self)
        self.itemconfigure(self._items["glow"], image=self._glow_photo)

    def _paint(self):
        if not self._geometry or "glow" not in self._items:
            return
        t = self.theme.t
        key = tuple(sorted(self.colors.items()))
        if key != self._glow_key:
            self._glow_key = key
            self._render_glow()
        for zone in ("top", "bottom", "left", "right", "center"):
            if zone in self._items:
                color = self.colors.get(zone)
                self.itemconfigure(self._items[zone], fill=mix(t["SCREEN"], color, 0.75) if color else t["SCREEN"])
        main = self.colors.get("all")
        label = (main.upper() if max(hex_to_rgb(main)) > 6 else "apagada") if main else ""
        if self.show_zones and main:
            label = ""
        self.itemconfigure(self._items["label"], text=label)

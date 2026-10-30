"""Temas claro/escuro e estilos ttk do Luz Cinema.

Todas as cores vêm dos tokens de ``THEMES``. Widgets Tk puros (Canvas, Label, Listbox)
se registram com ``Theme.bind`` para serem recoloridos quando o tema muda.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

FONT = "Segoe UI"
FONT_SEMIBOLD = "Segoe UI Semibold"

THEMES = {
    "dark": {
        "name": "dark",
        "label": "Escuro",
        "BG": "#0f1117",
        "SURFACE": "#141722",
        "CARD": "#1a1e2b",
        "CARD_HOVER": "#232838",
        "BORDER": "#2a3042",
        "FG": "#eef1f8",
        "MUTED": "#8b93a7",
        "ACCENT": "#8b5cf6",
        "ACCENT_HOVER": "#7c3aed",
        "ACCENT_SOFT": "#2a2346",
        "ACCENT_FG": "#ffffff",
        "SUCCESS": "#22c55e",
        "WARNING": "#f59e0b",
        "DANGER": "#ef4444",
        "DANGER_HOVER": "#dc2626",
        "ENTRY_BG": "#12151f",
        "TROUGH": "#2a3042",
        "SCREEN": "#05060a",
    },
    "light": {
        "name": "light",
        "label": "Claro",
        "BG": "#f4f5fa",
        "SURFACE": "#ffffff",
        "CARD": "#ffffff",
        "CARD_HOVER": "#eef0f7",
        "BORDER": "#e1e4ee",
        "FG": "#151925",
        "MUTED": "#5d667a",
        "ACCENT": "#7c3aed",
        "ACCENT_HOVER": "#6d28d9",
        "ACCENT_SOFT": "#ede9fe",
        "ACCENT_FG": "#ffffff",
        "SUCCESS": "#16a34a",
        "WARNING": "#d97706",
        "DANGER": "#dc2626",
        "DANGER_HOVER": "#b91c1c",
        "ENTRY_BG": "#ffffff",
        "TROUGH": "#dfe2ec",
        "SCREEN": "#1b1e29",
    },
}


class Theme:
    """Aplica o tema ao ttk e avisa os widgets registrados quando ele muda."""

    def __init__(self, root: tk.Tk, mode: str = "dark"):
        self.root = root
        self.mode = mode if mode in THEMES else "dark"
        self._listeners = []
        self._images = {}
        self.style = ttk.Style(root)
        self.style.theme_use("clam")

    @property
    def t(self) -> dict:
        return THEMES[self.mode]

    def __getitem__(self, token: str) -> str:
        return self.t[token]

    def bind(self, callback):
        """Registra ``callback(tokens)``; é chamado agora e a cada troca de tema."""
        self._listeners.append(callback)
        callback(self.t)
        return callback

    def set_mode(self, mode: str):
        self.mode = mode if mode in THEMES else "dark"
        self.apply()

    def apply(self):
        t = self.t
        self._configure_styles(t)
        alive = []
        for callback in self._listeners:
            try:
                callback(t)
                alive.append(callback)
            except tk.TclError:
                pass  # widget já destruído
        self._listeners = alive

    # ------------------------------------------------------------------ estilos
    def _configure_styles(self, t: dict):
        s = self.style
        self.root.configure(bg=t["BG"])
        s.configure(".", font=(FONT, 10), background=t["BG"], foreground=t["FG"], bordercolor=t["BORDER"],
                    lightcolor=t["BG"], darkcolor=t["BG"], focuscolor=t["ACCENT"], troughcolor=t["TROUGH"],
                    selectbackground=t["ACCENT"], selectforeground=t["ACCENT_FG"], relief="flat")

        for name, bg in (("TFrame", t["BG"]), ("Card.TFrame", t["CARD"]), ("Sidebar.TFrame", t["SURFACE"])):
            s.configure(name, background=bg)
        s.configure("CardBorder.TFrame", background=t["BORDER"])

        labels = {
            "TLabel": (t["BG"], t["FG"], (FONT, 10)),
            "Muted.TLabel": (t["BG"], t["MUTED"], (FONT, 10)),
            "Small.TLabel": (t["BG"], t["MUTED"], (FONT, 9)),
            "H1.TLabel": (t["BG"], t["FG"], (FONT_SEMIBOLD, 18)),
            "H2.TLabel": (t["BG"], t["FG"], (FONT_SEMIBOLD, 12)),
            "Card.TLabel": (t["CARD"], t["FG"], (FONT, 10)),
            "CardMuted.TLabel": (t["CARD"], t["MUTED"], (FONT, 9)),
            "CardH2.TLabel": (t["CARD"], t["FG"], (FONT_SEMIBOLD, 12)),
            "CardStrong.TLabel": (t["CARD"], t["FG"], (FONT_SEMIBOLD, 10)),
            "CardValue.TLabel": (t["CARD"], t["ACCENT"], (FONT_SEMIBOLD, 10)),
            "Brand.TLabel": (t["SURFACE"], t["FG"], (FONT_SEMIBOLD, 14)),
            "SidebarMuted.TLabel": (t["SURFACE"], t["MUTED"], (FONT, 9)),
            "Badge.TLabel": (t["ACCENT_SOFT"], t["ACCENT"], (FONT_SEMIBOLD, 8)),
            "Status.TLabel": (t["SURFACE"], t["MUTED"], (FONT, 9)),
            "StatusError.TLabel": (t["SURFACE"], t["DANGER"], (FONT, 9)),
            "StatusOk.TLabel": (t["SURFACE"], t["SUCCESS"], (FONT, 9)),
        }
        for name, (bg, fg, font) in labels.items():
            s.configure(name, background=bg, foreground=fg, font=font)

        def button(name, bg, fg, hover, font=(FONT_SEMIBOLD, 10), padding=(14, 8), anchor="center", pressed=None):
            s.configure(name, font=font, padding=padding, background=bg, foreground=fg, borderwidth=0,
                        lightcolor=bg, darkcolor=bg, bordercolor=bg, focuscolor=bg, anchor=anchor)
            s.map(name,
                  background=[("disabled", t["CARD"]), ("pressed", pressed or hover), ("active", hover)],
                  foreground=[("disabled", t["MUTED"])],
                  lightcolor=[("active", hover)], darkcolor=[("active", hover)], bordercolor=[("active", hover)])

        button("TButton", t["CARD_HOVER"], t["FG"], t["BORDER"])
        button("Accent.TButton", t["ACCENT"], t["ACCENT_FG"], t["ACCENT_HOVER"])
        button("Big.Accent.TButton", t["ACCENT"], t["ACCENT_FG"], t["ACCENT_HOVER"], font=(FONT_SEMIBOLD, 11), padding=(22, 12))
        button("Big.Danger.TButton", t["DANGER"], "#ffffff", t["DANGER_HOVER"], font=(FONT_SEMIBOLD, 11), padding=(22, 12))
        button("Danger.TButton", t["DANGER"], "#ffffff", t["DANGER_HOVER"])
        button("Ghost.TButton", t["CARD"], t["MUTED"], t["CARD_HOVER"], font=(FONT, 9), padding=(8, 4))
        button("Nav.TButton", t["SURFACE"], t["MUTED"], t["CARD_HOVER"], font=(FONT_SEMIBOLD, 10), padding=(14, 10), anchor="w")
        button("NavActive.TButton", t["ACCENT_SOFT"], t["ACCENT"], t["ACCENT_SOFT"], font=(FONT_SEMIBOLD, 10), padding=(14, 10), anchor="w")
        button("Chip.TButton", t["CARD_HOVER"], t["FG"], t["BORDER"], font=(FONT, 9), padding=(12, 6))
        button("ChipActive.TButton", t["ACCENT"], t["ACCENT_FG"], t["ACCENT_HOVER"], font=(FONT_SEMIBOLD, 9), padding=(12, 6))
        button("Sidebar.TButton", t["SURFACE"], t["MUTED"], t["CARD_HOVER"], font=(FONT, 9), padding=(10, 6))

        s.configure("TEntry", fieldbackground=t["ENTRY_BG"], foreground=t["FG"], insertcolor=t["FG"], padding=7,
                    bordercolor=t["BORDER"], lightcolor=t["BORDER"], darkcolor=t["BORDER"])
        s.map("TEntry", bordercolor=[("focus", t["ACCENT"])], lightcolor=[("focus", t["ACCENT"])],
              fieldbackground=[("disabled", t["CARD"])])
        s.configure("TCombobox", fieldbackground=t["ENTRY_BG"], background=t["CARD_HOVER"], foreground=t["FG"],
                    arrowcolor=t["MUTED"], padding=6, bordercolor=t["BORDER"], lightcolor=t["BORDER"],
                    darkcolor=t["BORDER"], arrowsize=14)
        s.map("TCombobox", fieldbackground=[("readonly", t["ENTRY_BG"]), ("disabled", t["CARD"])],
              selectbackground=[("readonly", t["ENTRY_BG"])], selectforeground=[("readonly", t["FG"])],
              foreground=[("readonly", t["FG"]), ("disabled", t["MUTED"])],
              bordercolor=[("focus", t["ACCENT"])])
        self.root.option_add("*TCombobox*Listbox.background", t["CARD"])
        self.root.option_add("*TCombobox*Listbox.foreground", t["FG"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", t["ACCENT"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", t["ACCENT_FG"])
        self.root.option_add("*TCombobox*Listbox.font", (FONT, 10))

        for base in ("TCheckbutton", "TRadiobutton"):
            for prefix, bg in (("", t["BG"]), ("Card.", t["CARD"])):
                s.configure(prefix + base, background=bg, foreground=t["FG"], focuscolor=bg)
                s.map(prefix + base, background=[("active", bg)], foreground=[("disabled", t["MUTED"]), ("active", t["FG"])])

        s.configure("Horizontal.TScale", background=t["BG"])
        s.configure("Card.Horizontal.TScale", background=t["CARD"])
        s.configure("TSeparator", background=t["BORDER"])
        s.configure("Vertical.TScrollbar", background=t["CARD_HOVER"], troughcolor=t["BG"], borderwidth=0,
                    arrowcolor=t["MUTED"], lightcolor=t["CARD_HOVER"], darkcolor=t["CARD_HOVER"], bordercolor=t["BG"])
        s.map("Vertical.TScrollbar", background=[("active", t["BORDER"])])
        try:
            self._install_elements(t)
        except tk.TclError:
            pass

    def _install_elements(self, t: dict):
        """Desenha sliders, caixas e rádios suavizados com Pillow (o 'clam' padrão é serrilhado)."""
        mode = self.mode
        s = self.style
        scale = max(1.0, self.root.winfo_fpixels("1i") / 96.0)
        n = round(18 * scale)
        gap = round(8 * scale)
        k = 4  # superamostragem

        def photo(key, draw_fn, width=None):
            w = width or n
            big = Image.new("RGBA", (w * k, n * k), (0, 0, 0, 0))
            draw_fn(ImageDraw.Draw(big), w * k, n * k)
            img = ImageTk.PhotoImage(big.resize((w, n), Image.LANCZOS), master=self.root)
            self._images[(mode, key)] = img
            return img

        def thumb(fill):
            def fn(d, w, h):
                d.ellipse((k, k, h - k, h - k), fill=fill)
                d.ellipse((h * 0.32, h * 0.32, h * 0.68, h * 0.68), fill="#ffffff")
            return fn

        def trough(d, w, h):
            th = h * 0.22
            d.rounded_rectangle((0, (h - th) / 2, w - 1, (h + th) / 2), radius=th / 2, fill=t["TROUGH"])

        def box(checked, fill):
            def fn(d, w, h):
                r = (k, k, h - k, h - k)
                if checked:
                    d.rounded_rectangle(r, radius=h * 0.24, fill=fill)
                    d.line([(h * 0.28, h * 0.52), (h * 0.44, h * 0.68), (h * 0.74, h * 0.34)],
                           fill="#ffffff", width=round(h * 0.11), joint="curve")
                else:
                    d.rounded_rectangle(r, radius=h * 0.24, fill=t["ENTRY_BG"], outline=fill, width=round(h * 0.08))
            return fn

        def dot(checked, fill):
            def fn(d, w, h):
                r = (k, k, h - k, h - k)
                if checked:
                    d.ellipse(r, fill=fill)
                    d.ellipse((h * 0.33, h * 0.33, h * 0.67, h * 0.67), fill="#ffffff")
                else:
                    d.ellipse(r, fill=t["ENTRY_BG"], outline=fill, width=round(h * 0.08))
            return fn

        if (mode, "thumb") not in self._images:
            th = photo("thumb", thumb(t["ACCENT"]))
            th_a = photo("thumb_a", thumb(t["ACCENT_HOVER"]))
            th_d = photo("thumb_d", thumb(t["BORDER"]))
            tr = photo("trough", trough, width=n * 3)
            s.element_create(f"{mode}Scale.trough", "image", tr, border=(n, 0), sticky="ew")
            s.element_create(f"{mode}Scale.slider", "image", th, ("disabled", th_d), ("active", th_a),
                             ("pressed", th_a), sticky="")
            cb = [photo(key, box(c, f), width=n + gap) for key, c, f in
                  (("cb_off", False, t["MUTED"]), ("cb_on", True, t["ACCENT"]),
                   ("cb_off_d", False, t["BORDER"]), ("cb_on_d", True, t["BORDER"]))]
            s.element_create(f"{mode}Check.indicator", "image", cb[0],
                             ("disabled", "selected", cb[3]), ("disabled", cb[2]), ("selected", cb[1]), sticky="")
            rb = [photo(key, dot(c, f), width=n + gap) for key, c, f in
                  (("rb_off", False, t["MUTED"]), ("rb_on", True, t["ACCENT"]),
                   ("rb_off_d", False, t["BORDER"]), ("rb_on_d", True, t["BORDER"]))]
            s.element_create(f"{mode}Radio.indicator", "image", rb[0],
                             ("disabled", "selected", rb[3]), ("disabled", rb[2]), ("selected", rb[1]), sticky="")

        for scale_style in ("Horizontal.TScale", "Card.Horizontal.TScale"):
            s.layout(scale_style, [(f"{mode}Scale.trough", {"sticky": "ew", "children": [
                (f"{mode}Scale.slider", {"side": "left", "sticky": ""})]})])
        for prefix in ("", "Card."):
            for cls, indicator in (("TCheckbutton", f"{mode}Check.indicator"), ("TRadiobutton", f"{mode}Radio.indicator")):
                s.layout(prefix + cls, [("Checkbutton.padding", {"sticky": "nswe", "children": [
                    (indicator, {"side": "left", "sticky": ""}),
                    ("Checkbutton.label", {"side": "left", "sticky": "nswe"})]})])

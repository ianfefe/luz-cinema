"""Definição de temas (Claro e Escuro) e estilos visuais antialiased para o Luz Cinema."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk

THEMES = {
    "dark": {
        "name": "dark",
        "title": "Modo Escuro",
        "toggle_label": "☀️ Modo Claro",
        "BG": "#0d1018",
        "PANEL": "#171b27",
        "PANEL_ALT": "#20263a",
        "FG": "#eef1f8",
        "MUTED": "#8a93ab",
        "ACCENT": "#8b5cf6",
        "ACCENT_HOVER": "#7c3aed",
        "ACCENT_FG": "#ffffff",
        "DANGER": "#e11d48",
        "DANGER_HOVER": "#be123c",
        "BORDER": "#262c40",
        "ENTRY_BG": "#11141e",
        "TAB_SELECTED": "#8b5cf6",
        "TROUGH": "#232a3e",
        "STATUS_BG": "#11141e",
        "STATUS_FG": "#c7cde0",
    },
    "light": {
        "name": "light",
        "title": "Modo Claro",
        "toggle_label": "🌙 Modo Escuro",
        "BG": "#f5f6fb",
        "PANEL": "#ffffff",
        "PANEL_ALT": "#eceefa",
        "FG": "#141827",
        "MUTED": "#5b6478",
        "ACCENT": "#7c3aed",
        "ACCENT_HOVER": "#6d28d9",
        "ACCENT_FG": "#ffffff",
        "DANGER": "#e11d48",
        "DANGER_HOVER": "#be123c",
        "BORDER": "#dde1ee",
        "ENTRY_BG": "#ffffff",
        "TAB_SELECTED": "#7c3aed",
        "TROUGH": "#dde1ee",
        "STATUS_BG": "#ffffff",
        "STATUS_FG": "#2a3045",
    },
}

# Constantes de cor padrão (tema escuro) para compatibilidade reversa
BG = THEMES["dark"]["BG"]
PANEL = THEMES["dark"]["PANEL"]
PANEL_ALT = THEMES["dark"]["PANEL_ALT"]
FG = THEMES["dark"]["FG"]
MUTED = THEMES["dark"]["MUTED"]
ACCENT = THEMES["dark"]["ACCENT"]
ACCENT_HOVER = THEMES["dark"]["ACCENT_HOVER"]
DANGER = THEMES["dark"]["DANGER"]
BORDER = THEMES["dark"]["BORDER"]
ENTRY_BG = THEMES["dark"]["ENTRY_BG"]


class ThemeMixin:
    """Mixin que fornece gerenciamento de temas e estilos visuais para a janela principal."""

    def toggle_theme(self):
        new_mode = "light" if self.theme_mode.get() == "dark" else "dark"
        self.theme_mode.set(new_mode)
        self.apply_theme()
        self.save_settings()
        self.status.set(f"Tema alterado para {THEMES[new_mode]['title']}.")

    def configure_theme(self):
        self.apply_theme()

    def install_custom_elements(self, style: ttk.Style, mode: str, t: dict):
        """Desenha sliders, checkboxes e radio buttons antialiased com Pillow."""
        if not hasattr(self, "_element_images"):
            self._element_images = {}
        scale = max(1.0, self.root.winfo_fpixels("1i") / 96.0)
        n = round(18 * scale)
        gap = round(8 * scale)
        S = 4

        def photo(key, draw_fn, width=None):
            w = width or n
            big = Image.new("RGBA", (w * S, n * S), (0, 0, 0, 0))
            draw_fn(ImageDraw.Draw(big), w * S, n * S)
            img = ImageTk.PhotoImage(big.resize((w, n), Image.LANCZOS), master=self.root)
            self._element_images[(mode, key)] = img
            return img

        def thumb(fill):
            def fn(d, w, h):
                d.ellipse((S, S, h - S, h - S), fill=fill)
                d.ellipse((h * 0.3, h * 0.3, h * 0.7, h * 0.7), fill="#ffffff")
            return fn

        def trough(d, w, h):
            th = h * 0.24
            d.rounded_rectangle((0, (h - th) / 2, w - 1, (h + th) / 2), radius=th / 2, fill=t["TROUGH"])

        def box(checked, fill):
            def fn(d, w, h):
                r = (S, S, h - S, h - S)
                if checked:
                    d.rounded_rectangle(r, radius=h * 0.22, fill=fill)
                    d.line([(h * 0.28, h * 0.52), (h * 0.44, h * 0.68), (h * 0.74, h * 0.34)], fill="#ffffff", width=round(h * 0.11), joint="curve")
                else:
                    d.rounded_rectangle(r, radius=h * 0.22, fill=t["ENTRY_BG"], outline=fill, width=round(h * 0.08))
            return fn

        def dot(checked, fill):
            def fn(d, w, h):
                r = (S, S, h - S, h - S)
                if checked:
                    d.ellipse(r, fill=fill)
                    d.ellipse((h * 0.33, h * 0.33, h * 0.67, h * 0.67), fill="#ffffff")
                else:
                    d.ellipse(r, fill=t["ENTRY_BG"], outline=fill, width=round(h * 0.08))
            return fn

        if (mode, "thumb") not in self._element_images:
            muted_line = t["MUTED"]
            th = photo("thumb", thumb(t["ACCENT"]))
            th_a = photo("thumb_a", thumb(t["ACCENT_HOVER"]))
            th_d = photo("thumb_d", thumb(t["BORDER"]))
            tr = photo("trough", trough, width=n * 3)
            style.element_create(f"{mode}Scale.trough", "image", tr, border=(n, 0), sticky="ew")
            style.element_create(f"{mode}Scale.slider", "image", th, ("disabled", th_d), ("active", th_a), ("pressed", th_a), sticky="")
            cb = [photo(k, box(c, f), width=n + gap) for k, c, f in
                  (("cb_off", False, muted_line), ("cb_on", True, t["ACCENT"]), ("cb_off_d", False, t["BORDER"]), ("cb_on_d", True, t["BORDER"]))]
            style.element_create(f"{mode}Check.indicator", "image", cb[0],
                                 ("disabled", "selected", cb[3]), ("disabled", cb[2]), ("selected", cb[1]), sticky="")
            rb = [photo(k, dot(c, f), width=n + gap) for k, c, f in
                  (("rb_off", False, muted_line), ("rb_on", True, t["ACCENT"]), ("rb_off_d", False, t["BORDER"]), ("rb_on_d", True, t["BORDER"]))]
            style.element_create(f"{mode}Radio.indicator", "image", rb[0],
                                 ("disabled", "selected", rb[3]), ("disabled", rb[2]), ("selected", rb[1]), sticky="")

        style.layout("Horizontal.TScale", [(f"{mode}Scale.trough", {"sticky": "ew", "children": [
            (f"{mode}Scale.slider", {"side": "left", "sticky": ""})]})])
        for cls, ind in (("TCheckbutton", f"{mode}Check.indicator"), ("TRadiobutton", f"{mode}Radio.indicator")):
            style.layout(cls, [("Checkbutton.padding", {"sticky": "nswe", "children": [
                (ind, {"side": "left", "sticky": ""}),
                ("Checkbutton.label", {"side": "left", "sticky": "nswe"})]})])

    def apply_theme(self, theme_name: str | None = None):
        """Aplica cores, fontes e estilos ttk ao aplicativo com base no tema ativo."""
        if theme_name:
            self.theme_mode.set(theme_name)
        mode = self.theme_mode.get()
        if mode not in THEMES:
            mode = "dark"
            self.theme_mode.set(mode)
        t = THEMES[mode]
        self.current_theme = t

        style = ttk.Style()
        style.theme_use("clam")

        self.root.configure(bg=t["BG"])

        # Tipografia e estilos de containers
        style.configure(".", font=("Segoe UI", 10), background=t["BG"], foreground=t["FG"],
                        bordercolor=t["BORDER"], lightcolor=t["BG"], darkcolor=t["BG"],
                        focuscolor=t["ACCENT"], troughcolor=t["TROUGH"], relief="flat")
        style.configure("TFrame", background=t["BG"])
        style.configure("Panel.TFrame", background=t["PANEL"])
        style.configure("Status.TFrame", background=t["STATUS_BG"])
        style.configure("TLabel", background=t["BG"], foreground=t["FG"])
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 22), background=t["BG"], foreground=t["FG"])
        style.configure("Section.TLabel", font=("Segoe UI Semibold", 13), background=t["BG"], foreground=t["FG"])
        style.configure("Muted.TLabel", font=("Segoe UI", 10), background=t["BG"], foreground=t["MUTED"])
        style.configure("Status.TLabel", font=("Segoe UI", 10), background=t["STATUS_BG"], foreground=t["STATUS_FG"])

        # Botões
        style.configure("TButton", font=("Segoe UI Semibold", 10), padding=(14, 8), background=t["PANEL_ALT"], foreground=t["FG"],
                        borderwidth=0, lightcolor=t["PANEL_ALT"], darkcolor=t["PANEL_ALT"])
        style.map("TButton",
            background=[("pressed", t["BORDER"]), ("active", t["BORDER"]), ("disabled", t["PANEL_ALT"])],
            foreground=[("disabled", t["MUTED"])])

        style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=(16, 8), background=t["ACCENT"], foreground=t["ACCENT_FG"],
                        borderwidth=0, lightcolor=t["ACCENT"], darkcolor=t["ACCENT"])
        style.map("Accent.TButton",
            background=[("pressed", t["ACCENT_HOVER"]), ("active", t["ACCENT_HOVER"]), ("disabled", t["PANEL"])],
            foreground=[("disabled", t["MUTED"])])

        style.configure("Danger.TButton", font=("Segoe UI Semibold", 10), padding=(14, 8), background=t["DANGER"], foreground="#ffffff",
                        borderwidth=0, lightcolor=t["DANGER"], darkcolor=t["DANGER"])
        style.map("Danger.TButton",
            background=[("pressed", t["DANGER_HOVER"]), ("active", t["DANGER_HOVER"]), ("disabled", t["PANEL"])],
            foreground=[("disabled", t["MUTED"])])

        style.configure("Preset.TButton", font=("Segoe UI", 10), padding=(10, 7), anchor="w", background=t["PANEL_ALT"], foreground=t["FG"], borderwidth=0)
        style.map("Preset.TButton", background=[("pressed", t["ACCENT"]), ("active", t["BORDER"])], foreground=[("pressed", "#ffffff")])
        style.configure("ThemeToggle.TButton", font=("Segoe UI", 10), padding=(12, 6), background=t["PANEL_ALT"], foreground=t["FG"], borderwidth=0)
        style.map("ThemeToggle.TButton",
            background=[("pressed", t["BORDER"]), ("active", t["PANEL_ALT"])])

        # Campos de formulário
        style.configure("TEntry", fieldbackground=t["ENTRY_BG"], foreground=t["FG"], insertcolor=t["FG"], padding=7,
                        bordercolor=t["BORDER"], lightcolor=t["ENTRY_BG"], darkcolor=t["ENTRY_BG"])
        style.map("TEntry", bordercolor=[("focus", t["ACCENT"])], lightcolor=[("focus", t["ACCENT"])])
        style.configure("TCombobox", fieldbackground=t["ENTRY_BG"], background=t["PANEL_ALT"], foreground=t["FG"], arrowcolor=t["MUTED"], padding=6,
                        bordercolor=t["BORDER"], lightcolor=t["ENTRY_BG"], darkcolor=t["ENTRY_BG"], arrowsize=14)
        self.root.option_add("*TCombobox*Listbox.background", t["PANEL"])
        self.root.option_add("*TCombobox*Listbox.foreground", t["FG"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", t["ACCENT"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        style.map("TCombobox",
            fieldbackground=[("readonly", t["ENTRY_BG"])],
            selectbackground=[("readonly", t["ENTRY_BG"])],
            selectforeground=[("readonly", t["FG"])],
            foreground=[("readonly", t["FG"])])

        # Abas do Notebook
        style.configure("TNotebook", background=t["BG"], borderwidth=0, tabmargins=(0, 0, 0, 10))
        style.configure("TNotebook.Tab", font=("Segoe UI Semibold", 10), padding=(16, 8), background=t["BG"], foreground=t["MUTED"],
                        borderwidth=0, lightcolor=t["BG"], bordercolor=t["BG"])
        style.map("TNotebook.Tab",
            background=[("selected", t["TAB_SELECTED"]), ("active", t["PANEL_ALT"])],
            foreground=[("selected", "#ffffff"), ("active", t["FG"])],
            lightcolor=[("selected", t["TAB_SELECTED"])],
            expand=[("selected", (0, 0, 0, 0))])

        # Caixas de seleção e opções
        style.configure("TCheckbutton", background=t["BG"], foreground=t["FG"])
        style.map("TCheckbutton", foreground=[("active", t["FG"])], background=[("active", t["BG"])])
        style.configure("TRadiobutton", background=t["BG"], foreground=t["FG"])
        style.map("TRadiobutton", foreground=[("active", t["FG"])], background=[("active", t["BG"])])

        # Sliders e Agrupadores
        try:
            self.install_custom_elements(style, mode, t)
        except Exception:
            pass
        style.configure("Horizontal.TScale", background=t["BG"])
        style.configure("TSeparator", background=t["BORDER"])
        style.configure("Vertical.TScrollbar", background=t["PANEL_ALT"], troughcolor=t["BG"], borderwidth=0, arrowcolor=t["MUTED"])
        style.configure("TLabelframe", background=t["BG"], bordercolor=t["BORDER"], lightcolor=t["BORDER"], darkcolor=t["BORDER"])
        style.configure("TLabelframe.Label", font=("Segoe UI Semibold", 10), background=t["BG"], foreground=t["FG"])

        # Atualização de widgets Tkinter diretos (Canvases, Labels específicos)
        if hasattr(self, "theme_toggle_btn"):
            self.theme_toggle_btn.configure(text=t["toggle_label"])

        if hasattr(self, "wheel_canvas"):
            self.wheel_canvas.configure(bg=t["BG"])

        if hasattr(self, "help_link"):
            self.help_link.configure(bg=t["STATUS_BG"], fg=t["MUTED"])

        if hasattr(self, "device_list"):
            self.device_list.configure(bg=t["ENTRY_BG"], fg=t["FG"], selectbackground=t["ACCENT"], selectforeground="#ffffff", highlightthickness=1, highlightbackground=t["BORDER"])

        if hasattr(self, "swatch") and not getattr(self, "running", False):
            self.swatch.configure(bg=t["PANEL"], highlightbackground=t["BORDER"])
            if hasattr(self, "swatch_label"):
                self.swatch.itemconfigure(self.swatch_label, fill=t["FG"])

        if hasattr(self, "manual_swatch"):
            self.manual_swatch.configure(highlightbackground=t["BORDER"])

        if hasattr(self, "default_preset_swatches"):
            for s in self.default_preset_swatches:
                try:
                    s.configure(highlightbackground=t["BORDER"])
                except Exception:
                    pass

        if hasattr(self, "custom_presets_frame") and hasattr(self, "refresh_custom_presets_ui"):
            self.refresh_custom_presets_ui()

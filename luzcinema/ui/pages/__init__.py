"""Páginas da janela principal, na ordem da barra lateral."""
from .cinema import CinemaPage
from .colors import ColorsPage
from .lamps import LampsPage
from .scenes import ScenesPage
from .settings import SettingsPage

PAGES = [
    ("cinema", "🎬  Cinema", CinemaPage),
    ("colors", "🎨  Cores", ColorsPage),
    ("scenes", "✨  Cenários", ScenesPage),
    ("lamps", "💡  Lâmpadas", LampsPage),
    ("settings", "⚙  Ajustes", SettingsPage),
]

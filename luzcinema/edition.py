"""Definição das duas edições oficiais do Luz Cinema.

As edições compartilham todo o código; só mudam a identidade no Windows
(registro, instância única, arquivo de preferências) e o que a interface mostra.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Edition:
    key: str
    title: str
    subtitle: str
    multi: bool
    config_name: str
    reg_name: str
    wake_event: str
    app_id: str
    script: str
    exe_name: str


SIMPLE = Edition(
    key="simples",
    title="Luz Cinema",
    subtitle="Sua lâmpada acompanhando a tela",
    multi=False,
    config_name="preferencias_simples.json",
    reg_name="LuzCinema",
    wake_event="LuzCinema_Simples_WakeEvent",
    app_id="LuzCinema.App.Simples",
    script="luz_cinema.py",
    exe_name="LuzCinema.exe",
)

MULTI = Edition(
    key="multi",
    title="Luz Cinema Multi",
    subtitle="Várias lâmpadas, cada uma em uma zona da tela",
    multi=True,
    config_name="preferencias_multi.json",
    reg_name="LuzCinemaMulti",
    wake_event="LuzCinema_Multi_WakeEvent",
    app_id="LuzCinema.App.Multi",
    script="luz_cinema_multi.py",
    exe_name="LuzCinemaMulti.exe",
)

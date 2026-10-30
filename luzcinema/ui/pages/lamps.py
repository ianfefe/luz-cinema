"""Página Lâmpadas: ver, testar, adicionar e organizar as lâmpadas."""
from __future__ import annotations

from tkinter import ttk

from ...core import rgb_to_hex
from ...devices import BulbDevice
from ..dialogs import ChooseDevicesDialog, LocalBulbDialog
from ..labels import ZONE_LABELS
from ..widgets import ScrollPage, Swatch, card

SUGGESTED_ZONES = ("left", "right", "top", "all")


class LampsPage(ScrollPage):
    def __init__(self, app, parent):
        super().__init__(parent, app.theme)
        self.app = app
        self.swatches: dict[str, Swatch] = {}
        self.status_labels: dict[str, ttk.Label] = {}
        body = self.body

        ttk.Label(body, text="Lâmpadas", style="H1.TLabel").pack(anchor="w")
        ttk.Label(body, style="Muted.TLabel", wraplength=640, justify="left", text=(
            "Conecte sua lâmpada. Com duas ou mais, você escolhe qual parte da tela cada uma acompanha."
        )).pack(anchor="w", pady=(2, 18))

        self.devices_area = ttk.Frame(body)
        self.devices_area.pack(fill="x")

        add = card(body)
        add.outer.pack(fill="x", pady=(18, 0))
        self.add_title = ttk.Label(add, style="CardH2.TLabel")
        self.add_title.pack(anchor="w")
        options = ttk.Frame(add, style="Card.TFrame")
        options.pack(fill="x", pady=(12, 0))
        options.columnconfigure(0, weight=1, uniform="o")
        options.columnconfigure(1, weight=1, uniform="o")
        self._option(options, 0, "☁  Pela conta Tuya", "Recomendado. Vincule o app do celular por QR code e escolha a lâmpada.",
                     [("Vincular conta (QR code)", "Accent.TButton", self.link_account),
                      ("Escolher da conta", "TButton", self.choose_from_account)])
        self._option(options, 1, "📶  Pela rede local", "Sem internet: precisa do IP, do ID e da chave local da lâmpada.",
                     [("Procurar na rede", "TButton", self.scan),
                      ("Digitar dados", "TButton", lambda: LocalBulbDialog(self.app))])
        self.on_devices_changed()

    def _option(self, parent, column, title, text, buttons):
        box = ttk.Frame(parent, style="Card.TFrame")
        box.grid(row=0, column=column, sticky="nsew", padx=(0, 12) if column == 0 else (12, 0))
        ttk.Label(box, text=title, style="CardStrong.TLabel").pack(anchor="w")
        ttk.Label(box, text=text, style="CardMuted.TLabel", wraplength=280, justify="left").pack(anchor="w", pady=(2, 10))
        for label, style, command in buttons:
            ttk.Button(box, text=label, style=style, command=command).pack(anchor="w", pady=2, fill="x")

    # ------------------------------------------------------------------ lista
    def on_devices_changed(self):
        for child in self.devices_area.winfo_children():
            child.destroy()
        self.swatches.clear()
        self.status_labels.clear()
        devices = self.app.controller.device_list()
        self.add_title.configure(text="Adicionar outra lâmpada" if devices else "Conectar sua lâmpada")
        if not devices:
            empty = card(self.devices_area, padding=24)
            empty.outer.pack(fill="x")
            ttk.Label(empty, text="💡  Nenhuma lâmpada conectada ainda", style="CardH2.TLabel").pack(anchor="w")
            ttk.Label(empty, style="CardMuted.TLabel", text="Use uma das opções abaixo para começar.").pack(anchor="w", pady=(4, 0))
            return
        for device in devices:
            self._device_card(device)

    def _device_card(self, device: BulbDevice):
        app = self.app
        multi = app.multi
        box = card(self.devices_area)
        box.outer.pack(fill="x", pady=(0, 10))
        top = ttk.Frame(box, style="Card.TFrame")
        top.pack(fill="x")
        swatch = Swatch(top, app.theme, self._power_color(device), size=26 if multi else 34)
        swatch.pack(side="left", padx=(0, 14))
        self.swatches[device.id] = swatch
        info = ttk.Frame(top, style="Card.TFrame")
        info.pack(side="left", fill="x", expand=True)
        ttk.Label(info, text=device.name, style="CardH2.TLabel").pack(anchor="w")
        details = device.kind_label + (f"  ·  {device.ip}" if device.is_local and device.ip else "")
        ttk.Label(info, text=details, style="CardMuted.TLabel").pack(anchor="w")

        if multi:
            zone_box = ttk.Frame(top, style="Card.TFrame")
            zone_box.pack(side="right")
            ttk.Label(zone_box, text="Acompanha", style="CardMuted.TLabel").pack(anchor="w")
            zone = ttk.Combobox(zone_box, state="readonly", width=16, values=list(ZONE_LABELS.values()))
            zone.set(ZONE_LABELS.get(device.zone if device.enabled else "none", ZONE_LABELS["all"]))
            zone.pack(anchor="w")
            zone.bind("<<ComboboxSelected>>", lambda _, d=device, z=zone: self._set_zone(d, z.get()))

        actions = ttk.Frame(box, style="Card.TFrame")
        actions.pack(fill="x", pady=(12, 0))
        buttons = [("Acender", lambda: app.set_power(True, [device.id])),
                   ("Apagar", lambda: app.set_power(False, [device.id])),
                   ("Testar conexão", lambda: app.test_device(device))]
        if device.is_local:
            buttons.append(("Editar", lambda: LocalBulbDialog(app, device)))
        for label, command in buttons:
            ttk.Button(actions, text=label, command=command).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Remover", style="Ghost.TButton",
                   command=lambda: app.remove_device(device)).pack(side="right")
        status = ttk.Label(box, style="CardMuted.TLabel", text="Use “Testar conexão” para verificar se ela responde.")
        status.pack(anchor="w", pady=(10, 0))
        self.status_labels[device.id] = status

    def _power_color(self, device):
        on = self.app.controller.power.get(device.id)
        if on is None:
            return self.app.theme["CARD_HOVER"]
        return self.app.theme["SUCCESS"] if on else "#3a3f4d"

    def _set_zone(self, device: BulbDevice, label: str):
        zone = next((k for k, v in ZONE_LABELS.items() if v == label), "all")
        device.enabled = zone != "none"
        if zone != "none":
            device.zone = zone
        self.app.devices_changed()

    # ------------------------------------------------------------------ eventos
    def on_bulb_event(self, kind, payload):
        device = payload[0] if isinstance(payload, tuple) else payload
        if not isinstance(device, BulbDevice) or device.id not in self.status_labels:
            return
        label = self.status_labels[device.id]
        if kind == "test":
            label.configure(text=f"✖  {payload[1]}" if payload[1] else "✔  Conexão funcionando")
        elif kind == "bulb_error":
            label.configure(text=f"✖  {payload[1]}")
        elif kind in ("applied", "reconnected"):
            label.configure(text="✔  Respondendo")
        if device.id in self.swatches and not self.app.running:
            self.swatches[device.id].set(self._power_color(device))

    def on_frame(self, colors, lamp_colors):
        for bid, swatch in self.swatches.items():
            rgb = lamp_colors.get(bid)
            if rgb:
                swatch.set(rgb_to_hex(rgb))
            elif not colors:
                device = self.app.controller.devices.get(bid)
                if device:
                    swatch.set(self._power_color(device))

    # ------------------------------------------------------------------ adicionar
    def link_account(self):
        self.app.open_tuya_link(on_linked=self.choose_from_account)

    def choose_from_account(self):
        from ...tuya_cloud import has_session
        if not has_session():
            self.app.set_status("Primeiro vincule sua conta Tuya pelo QR code.", "error")
            self.link_account()
            return
        self.app.fetch_cloud_devices(self._show_cloud_devices)

    def _show_cloud_devices(self, devices):
        if not devices:
            self.app.set_status("Nenhuma lâmpada encontrada na conta Tuya vinculada.", "error")
            return
        self.app.set_status(f"{len(devices)} lâmpada(s) encontrada(s) na conta.")
        ChooseDevicesDialog(
            self.app, "Lâmpadas da sua conta",
            "Escolha as lâmpadas que o Luz Cinema deve controlar.",
            devices, self._add_cloud_devices,
            describe=lambda d: d["name"] + ("" if d.get("online", True) else "  (offline)"))

    def _add_cloud_devices(self, chosen):
        count = len(self.app.controller.device_list())
        several = count + len(chosen) > 1
        for i, item in enumerate(chosen):
            zone = SUGGESTED_ZONES[min(count + i, len(SUGGESTED_ZONES) - 1)] if several else "all"
            self.app.save_device(BulbDevice(id=item["id"], name=item["name"], connection_type="cloud", zone=zone))

    def scan(self):
        self.app.scan_local(self._show_scan)

    def _show_scan(self, found):
        if not found:
            self.app.set_status("Nenhuma lâmpada respondeu na rede local. Você ainda pode digitar os dados.", "error")
            return
        self.app.set_status(f"{len(found)} dispositivo(s) encontrado(s) na rede.")
        ChooseDevicesDialog(
            self.app, "Encontradas na rede",
            "Escolha a lâmpada. Em seguida, informe a chave local dela.",
            found, lambda chosen: LocalBulbDialog(self.app, prefill=chosen[0]),
            describe=lambda d: f"{d['ip']}   ·   {d['id']}", single=True)

"""Diálogos: lâmpada na rede local e escolha de lâmpadas (conta Tuya ou busca na rede)."""
from __future__ import annotations

import ipaddress
import tkinter as tk
from tkinter import ttk

from ..core import SUPPORTED_VERSIONS
from ..devices import BulbDevice
from .labels import ZONE_LABELS


class Dialog:
    """Janela modal simples, centralizada sobre a principal e com o tema atual."""

    def __init__(self, app, title: str, width=460):
        self.app = app
        self.top = tk.Toplevel(app.root)
        self.top.title(title)
        self.top.transient(app.root)
        self.top.resizable(False, False)
        self.top.configure(bg=app.theme["BG"])
        self.body = ttk.Frame(self.top, padding=24)
        self.body.pack(fill="both", expand=True)
        self.width = width
        self.top.bind("<Escape>", lambda _: self.close())

    def finish(self):
        """Posiciona a janela e torna-a modal depois de montado o conteúdo."""
        self.top.update_idletasks()
        root = self.app.root
        w = max(self.width, self.top.winfo_reqwidth())
        h = self.top.winfo_reqheight()
        x = root.winfo_rootx() + (root.winfo_width() - w) // 2
        y = root.winfo_rooty() + max(20, (root.winfo_height() - h) // 3)
        self.top.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        self.top.grab_set()
        self.top.focus_set()

    def close(self):
        try:
            self.top.grab_release()
        except tk.TclError:
            pass
        self.top.destroy()


class LocalBulbDialog(Dialog):
    """Cadastro/edição de uma lâmpada controlada direto pela rede local (IP + ID + chave)."""

    def __init__(self, app, device: BulbDevice | None = None, prefill: dict | None = None):
        super().__init__(app, "Lâmpada na rede local")
        editing = device is not None
        prefill = prefill or {}
        source = device.to_dict() if device else {}
        default_name = "Lâmpada" if not app.edition.multi else f"Lâmpada {len(app.controller.device_list()) + 1}"
        self.original_id = device.id if device else None
        self.vars = {
            "name": tk.StringVar(value=source.get("name") or default_name),
            "ip": tk.StringVar(value=source.get("ip") or prefill.get("ip", "")),
            "id": tk.StringVar(value=source.get("id") or prefill.get("id", "")),
            "key": tk.StringVar(value=source.get("key", "")),
            "version": tk.StringVar(value=str(source.get("version") or prefill.get("version") or "3.5")),
            "zone": tk.StringVar(value=ZONE_LABELS.get(source.get("zone", "all"), ZONE_LABELS["all"])),
        }
        self.error = tk.StringVar()

        ttk.Label(self.body, text="Editar lâmpada" if editing else "Adicionar pela rede local", style="H1.TLabel").pack(anchor="w")
        ttk.Label(self.body, style="Muted.TLabel", wraplength=410, justify="left", text=(
            "Controle direto pelo Wi-Fi, sem passar pela internet. O ID e a chave local (16 caracteres) "
            "podem ser obtidos com o assistente do tinytuya ou na plataforma Tuya IoT.")).pack(anchor="w", pady=(4, 16))

        form = ttk.Frame(self.body)
        form.pack(fill="x")
        form.columnconfigure(0, weight=1)
        self._field(form, "Nome", "name")
        self._field(form, "Endereço IP", "ip", hint="Ex.: 192.168.0.42 — veja no app do celular ou no roteador.")
        self._field(form, "ID do dispositivo", "id")
        key_entry = self._field(form, "Chave local", "key", show="•")
        self.show_key = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Mostrar chave", variable=self.show_key,
                        command=lambda: key_entry.configure(show="" if self.show_key.get() else "•")).pack(anchor="w", pady=(0, 10))

        row = ttk.Frame(form)
        row.pack(fill="x", pady=(0, 10))
        col = ttk.Frame(row)
        col.pack(side="left")
        ttk.Label(col, text="Versão do protocolo").pack(anchor="w")
        ttk.Combobox(col, textvariable=self.vars["version"], state="readonly", width=8,
                     values=[str(v) for v in reversed(SUPPORTED_VERSIONS)]).pack(anchor="w", pady=(4, 0))
        if app.edition.multi:
            col = ttk.Frame(row)
            col.pack(side="left", padx=(16, 0), fill="x", expand=True)
            ttk.Label(col, text="Zona da tela").pack(anchor="w")
            ttk.Combobox(col, textvariable=self.vars["zone"], state="readonly",
                         values=list(ZONE_LABELS.values())).pack(fill="x", pady=(4, 0))

        ttk.Label(self.body, textvariable=self.error, foreground=app.theme["DANGER"], wraplength=410).pack(anchor="w")
        buttons = ttk.Frame(self.body)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Salvar e testar", style="Accent.TButton", command=self.save).pack(side="right")
        ttk.Button(buttons, text="Cancelar", command=self.close).pack(side="right", padx=8)
        self.top.bind("<Return>", lambda _: self.save())
        self.finish()

    def _field(self, parent, label, key, hint="", show=None):
        ttk.Label(parent, text=label).pack(anchor="w")
        entry = ttk.Entry(parent, textvariable=self.vars[key], show=show or "")
        entry.pack(fill="x", pady=(4, 2 if hint else 10))
        if hint:
            ttk.Label(parent, text=hint, style="Small.TLabel").pack(anchor="w", pady=(0, 10))
        return entry

    def save(self):
        values = {k: v.get().strip() for k, v in self.vars.items()}
        try:
            address = ipaddress.ip_address(values["ip"])
            if address.version != 4 or not address.is_private:
                raise ValueError
        except ValueError:
            self.error.set("Informe o IPv4 da lâmpada na sua rede (ex.: 192.168.0.42).")
            return
        if not values["id"]:
            self.error.set("Informe o ID do dispositivo.")
            return
        if len(values["key"].encode("utf-8")) != 16:
            self.error.set("A chave local precisa ter exatamente 16 caracteres.")
            return
        zone = next((k for k, label in ZONE_LABELS.items() if label == values["zone"]), "all")
        if self.original_id and self.original_id != values["id"]:
            self.app.controller.remove_device(self.original_id)
        device = BulbDevice(id=values["id"], name=values["name"] or "Lâmpada", connection_type="local",
                            ip=str(ipaddress.ip_address(values["ip"])), key=values["key"],
                            version=values["version"] or "3.5", zone=zone)
        self.close()
        self.app.save_device(device)


class ChooseDevicesDialog(Dialog):
    """Lista lâmpadas encontradas para o usuário escolher (uma na Simples, várias na Multi)."""

    def __init__(self, app, title: str, subtitle: str, devices: list[dict], on_choose, describe, single=False):
        super().__init__(app, title)
        self.on_choose = on_choose
        self.devices = devices
        self.multi = multi = app.edition.multi and not single
        known = set(app.controller.devices)

        ttk.Label(self.body, text=title, style="H1.TLabel").pack(anchor="w")
        ttk.Label(self.body, text=subtitle, style="Muted.TLabel", wraplength=410, justify="left").pack(anchor="w", pady=(4, 14))

        box = ttk.Frame(self.body)
        box.pack(fill="x")
        self.choice = tk.StringVar(value="")
        self.checks: dict[str, tk.BooleanVar] = {}
        for device in devices:
            label = describe(device)
            if device["id"] in known:
                label += "   (já adicionada)"
            if multi:
                var = tk.BooleanVar(value=device["id"] not in known)
                self.checks[device["id"]] = var
                ttk.Checkbutton(box, text=label, variable=var).pack(anchor="w", pady=3)
            else:
                ttk.Radiobutton(box, text=label, variable=self.choice, value=device["id"]).pack(anchor="w", pady=3)
        if not multi and devices:
            self.choice.set(devices[0]["id"])

        buttons = ttk.Frame(self.body)
        buttons.pack(fill="x", pady=(18, 0))
        ttk.Button(buttons, text="Adicionar" if multi else "Usar esta lâmpada", style="Accent.TButton",
                   command=self.confirm).pack(side="right")
        ttk.Button(buttons, text="Cancelar", command=self.close).pack(side="right", padx=8)
        self.finish()

    def confirm(self):
        if self.multi:
            ids = {i for i, var in self.checks.items() if var.get()}
        else:
            ids = {self.choice.get()} if self.choice.get() else set()
        chosen = [d for d in self.devices if d["id"] in ids]
        self.close()
        if chosen:
            self.on_choose(chosen)

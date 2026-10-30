"""Vinculação da conta Tuya por QR code (fluxo público de compartilhamento Tuya / Home Assistant).

O registro público usado pela Tuya identifica este login como "Home Assistant";
a janela informa isso antes da autorização. Nenhuma senha é pedida e os tokens
ficam só neste computador, protegidos pela DPAPI do Windows.
"""
from __future__ import annotations

from functools import partial
import json
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from urllib.parse import urlsplit

from .windows import DATA_DIR, protect

CLIENT_ID = "HA_3y9q4ak7g4ephrvke"
SCHEMA = "haauthorize"
SESSION_FILE = DATA_DIR / "tuya.enc"
QR_TIMEOUT = 180
TUYA_HOSTS = ("iotbing.com", "tuyaus.com", "tuyaeu.com", "tuyacn.com", "tuya.com", "tuyain.com")


def check_endpoint(endpoint):
    parsed = urlsplit(endpoint)
    host = parsed.hostname or ""
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Destino de autenticação inválido.")
    if not any(host == base or host.endswith("." + base) for base in TUYA_HOSTS):
        raise ValueError("Destino não reconhecido como serviço Tuya.")
    return endpoint.rstrip("/")


def session_from_result(info, user_code):
    endpoint = check_endpoint(info.get("endpoint") or info.get("end_point") or "")
    fields = ("t", "uid", "expire_time", "access_token", "refresh_token")
    if not all(info.get(k) is not None for k in fields) or not info.get("terminal_id"):
        raise ValueError("Autorização retornou dados incompletos.")
    return {"client_id": CLIENT_ID, "user_code": user_code, "terminal_id": info["terminal_id"],
            "endpoint": endpoint, "token_info": {k: info[k] for k in fields}}


def save_session(session):
    encoded = protect(json.dumps(session))
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = SESSION_FILE.with_suffix(".tmp")
    temporary.write_text(encoded, encoding="ascii")
    temporary.replace(SESSION_FILE)


class LinkWindow:
    """Janela que gera o QR code e aguarda a confirmação no app Tuya Smart / Smart Life."""

    def __init__(self, top: tk.Toplevel, theme: dict, on_linked=None, user_code: str = ""):
        self.top = top
        self.theme = theme
        self.on_linked = on_linked
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.thread = None
        self.photo = None
        self.code = tk.StringVar(value=user_code)
        self.status = tk.StringVar(value="Digite o código de usuário e gere o QR code.")

        t = theme
        top.title("Vincular conta Tuya")
        top.configure(bg=t["BG"])
        top.resizable(False, False)

        body = ttk.Frame(top, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Vincular conta Tuya", style="H1.TLabel").pack(anchor="w")
        ttk.Label(body, style="Muted.TLabel", wraplength=440, justify="left", text=(
            "Funciona com Tuya Smart, Smart Life e apps compatíveis (ex.: Elgin Smart). "
            "O pedido de autorização aparece no celular como \"Home Assistant\" — é o "
            "registro público da Tuya usado por este app. Nenhuma senha é pedida.")).pack(anchor="w", pady=(4, 16))

        steps = ttk.Frame(body, style="Card.TFrame", padding=16)
        steps.pack(fill="x")
        ttk.Label(steps, style="CardMuted.TLabel", justify="left", wraplength=420, text=(
            "1. No app do celular: Eu (Perfil) → ⚙ Configurações → Conta e segurança → Código de usuário.\n"
            "2. Cole o código abaixo e clique em Gerar QR code.\n"
            "3. No app: toque em + → Escanear e confirme a autorização.")).pack(anchor="w")

        row = ttk.Frame(body)
        row.pack(fill="x", pady=(16, 8))
        ttk.Label(row, text="Código de usuário").pack(anchor="w")
        entry_row = ttk.Frame(row)
        entry_row.pack(fill="x", pady=(4, 0))
        self.entry = ttk.Entry(entry_row, textvariable=self.code)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", lambda _: self.start())
        self.button = ttk.Button(entry_row, text="Gerar QR code", style="Accent.TButton", command=self.start)
        self.button.pack(side="left", padx=(8, 0))

        self.qr_holder = tk.Label(body, bg=t["BG"], width=1, height=1)
        self.qr_holder.pack(pady=8)
        ttk.Label(body, textvariable=self.status, style="Muted.TLabel", wraplength=440, justify="center").pack(pady=(0, 12))
        ttk.Button(body, text="Fechar", command=self.close).pack(anchor="e")

        top.protocol("WM_DELETE_WINDOW", self.close)
        self.entry.focus_set()
        self.timer = top.after(100, self.drain)

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        code = self.code.get().strip()
        if not code or not code.isalnum() or len(code) > 64:
            self.status.set("Confira o código de usuário (só letras e números).")
            return
        self.cancel.clear()
        self.button.configure(state="disabled")
        self.entry.configure(state="disabled")
        self.status.set("Solicitando QR code à Tuya…")
        self.thread = threading.Thread(target=self._run, args=(code,), daemon=True)
        self.thread.start()

    def _run(self, code):
        import qrcode
        from tuya_sharing import LoginControl

        login = None
        try:
            login = LoginControl()
            login.session.request = partial(login.session.request, timeout=(5, 12))
            response = login.qr_code(CLIENT_ID, SCHEMA, code)
            if not response.get("success"):
                self.events.put(("status", "A Tuya recusou a solicitação. Confira o código e tente novamente."))
                return
            token = response.get("result", {}).get("qrcode")
            if not isinstance(token, str) or not token:
                raise ValueError()
            qr = qrcode.QRCode(box_size=8, border=3)
            qr.add_data(f"tuyaSmart--qrLogin?token={token}")
            qr.make(fit=True)
            self.events.put(("qr", qr.make_image(fill_color="black", back_color="white").convert("RGB")))
            self.events.put(("status", "Escaneie com o app e confirme. O QR code expira em 3 minutos."))
            end = time.monotonic() + QR_TIMEOUT
            while time.monotonic() < end and not self.cancel.wait(3):
                ok, info = login.login_result(token, CLIENT_ID, code)
                if ok:
                    save_session(session_from_result(info, code))
                    self.events.put(("linked", None))
                    return
            if not self.cancel.is_set():
                self.events.put(("status", "O QR code expirou. Clique em Gerar QR code para tentar de novo."))
        except Exception:
            self.events.put(("status", "Não foi possível falar com a Tuya. Verifique a internet e gere outro QR code."))
        finally:
            if login:
                login.session.close()
            self.events.put(("done", None))

    def drain(self):
        from PIL import ImageTk

        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "status":
                self.status.set(value)
            elif kind == "qr":
                self.photo = ImageTk.PhotoImage(value.resize((260, 260)), master=self.top)
                self.qr_holder.configure(image=self.photo, width=260, height=260)
            elif kind == "linked":
                self.status.set("Conta vinculada e protegida neste Windows!")
                if self.on_linked:
                    self.on_linked()
                self.close()
                return
            elif kind == "done":
                self.button.configure(state="normal")
                self.entry.configure(state="normal")
        self.timer = self.top.after(100, self.drain)

    def close(self):
        self.cancel.set()
        try:
            self.top.after_cancel(self.timer)
        except Exception:
            pass
        self.top.destroy()

"""Integração com o Windows: registro de autostart, instância única e proteção DPAPI."""
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import sys
import winreg

APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
CONFIG = APP_DIR / "dados" / "preferencias.json"

APP_REG_NAME = "LuzCinema"
REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_APPROVED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
WAKE_EVENT_NAME = "LuzCinema_SingleInstance_WakeEvent"

_WAKE_EVENT = None


def check_single_instance() -> bool:
    """Garante que apenas uma instância execute. Se uma segunda for aberta, acorda a primeira."""
    global _WAKE_EVENT
    if os.name != "nt":
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateEventW.restype = wintypes.HANDLE
        kernel32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.SetEvent.restype = wintypes.BOOL
        kernel32.SetEvent.argtypes = [wintypes.HANDLE]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]

        _WAKE_EVENT = kernel32.CreateEventW(None, False, False, WAKE_EVENT_NAME)
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            if "--tray" not in sys.argv and "--minimized" not in sys.argv:
                kernel32.SetEvent(_WAKE_EVENT)
            return False
        return True
    except Exception:
        return True


def get_wake_event():
    """Retorna o handle do evento de ativação de instância única."""
    return _WAKE_EVENT


def get_target_app_cmd() -> str:
    """Retorna a linha de comando entre aspas para iniciar o Luz Cinema na bandeja do Windows."""
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable).resolve()
        return f'"{exe_path}" --tray'

    exe_candidate = (APP_DIR / "LuzCinema.exe").resolve()
    if exe_candidate.exists():
        return f'"{exe_candidate}" --tray'

    py_exe = sys.executable
    pyw = Path(py_exe).with_name("pythonw.exe")
    used_py = pyw if pyw.exists() else py_exe
    script = (APP_DIR / "luz_cinema.py").resolve()
    return f'"{used_py}" "{script}" --tray'


def is_autostart_enabled() -> bool:
    """Verifica se o início automático com o Windows está ativo e não bloqueado pelo Gerenciador de Tarefas."""
    if os.name != "nt":
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, APP_REG_NAME)
            if not val or not isinstance(val, str):
                return False
            # Verifica se o arquivo executável apontado realmente existe no disco
            raw = val.strip()
            exe_part = raw[1:].split('"')[0] if raw.startswith('"') else raw.split()[0]
            if not exe_part or not Path(exe_part).exists():
                return False

            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_APPROVED_KEY, 0, winreg.KEY_READ) as app_key:
                    approved_val, _ = winreg.QueryValueEx(app_key, APP_REG_NAME)
                    if isinstance(approved_val, (bytes, bytearray)) and len(approved_val) > 0:
                        # Valores ímpares (ex.: 0x01 ou 0x03) indicam desabilitado no Gerenciador de Tarefas
                        if (approved_val[0] & 1) != 0:
                            return False
            except Exception:
                pass
            return True
    except Exception:
        return False


def set_autostart(enable: bool):
    """Ativa ou desativa a inicialização automática no Registro do Windows."""
    if os.name != "nt":
        return
    try:
        cmd = get_target_app_cmd()
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, cmd)
                try:
                    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_APPROVED_KEY, 0, winreg.KEY_SET_VALUE) as app_key:
                        winreg.SetValueEx(app_key, APP_REG_NAME, 0, winreg.REG_BINARY, b"\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
                except Exception:
                    pass
            else:
                try:
                    winreg.DeleteValue(key, APP_REG_NAME)
                except FileNotFoundError:
                    pass
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_APPROVED_KEY, 0, winreg.KEY_SET_VALUE) as app_key:
                        winreg.DeleteValue(app_key, APP_REG_NAME)
                except Exception:
                    pass
    except Exception:
        pass


def protect(text: str, decrypt: bool = False) -> str:
    """Criptografa ou descriptografa dados vinculados ao usuário atual do Windows via DPAPI."""
    if os.name != "nt":
        raise ValueError("Armazenamento protegido disponível somente no Windows.")

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    raw = base64.b64decode(text) if decrypt else text.encode("utf-8")
    buf = ctypes.create_string_buffer(raw)
    incoming = Blob(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    outgoing = Blob()
    crypt = ctypes.windll.crypt32
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    if not fn(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)):
        raise ValueError("O Windows não conseguiu proteger ou ler a chave salva.")
    try:
        result = ctypes.string_at(outgoing.pbData, outgoing.cbData)
        return result.decode("utf-8") if decrypt else base64.b64encode(result).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(outgoing.pbData)


def setup_windows_dpi_and_app_id():
    """Configura percepção de DPI e AppUserModelID para ícone na barra de tarefas."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LuzCinema.App")
    except (AttributeError, OSError):
        pass

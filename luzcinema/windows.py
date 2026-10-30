"""Integração com o Windows: pastas, início automático, instância única e DPAPI."""
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import sys

if os.name == "nt":
    import winreg
else:  # pragma: no cover - o app é exclusivo para Windows; mantém import possível em testes
    winreg = None

APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "dados"

APP_REG_NAME = "LuzCinema"
WAKE_EVENT_NAME = "LuzCinema_WakeEvent"
APP_USER_MODEL_ID = "LuzCinema.App"
ENTRY_SCRIPT = "luz_cinema.py"
EXE_NAME = "LuzCinema.exe"
# Nomes usados pelas versões anteriores (v2 e edição Multi) no início automático.
LEGACY_REG_NAMES = ("LuzCinemaV2", "LuzCinemaMulti")

REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_APPROVED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
ERROR_ALREADY_EXISTS = 183

_wake_event = None


def check_single_instance() -> bool:
    """Garante uma única instância. Uma segunda abertura acorda a janela existente."""
    global _wake_event
    if os.name != "nt":
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateEventW.restype = wintypes.HANDLE
        kernel32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.SetEvent.argtypes = [wintypes.HANDLE]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]

        _wake_event = kernel32.CreateEventW(None, False, False, WAKE_EVENT_NAME)
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            if "--tray" not in sys.argv and "--minimized" not in sys.argv:
                kernel32.SetEvent(_wake_event)
            return False
        return True
    except Exception:
        return True


def wake_requested() -> bool:
    """Retorna True quando outra instância pediu para mostrar a janela."""
    if os.name != "nt" or not _wake_event:
        return False
    try:
        return ctypes.windll.kernel32.WaitForSingleObject(_wake_event, 0) == 0
    except Exception:
        return False


def launch_command() -> str:
    """Linha de comando usada pelo Windows para abrir o app minimizado na bandeja."""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}" --tray'

    exe_candidate = APP_DIR / EXE_NAME
    if exe_candidate.exists():
        return f'"{exe_candidate.resolve()}" --tray'

    pythonw = Path(sys.executable).with_name("pythonw.exe")
    interpreter = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{interpreter}" "{(APP_DIR / ENTRY_SCRIPT).resolve()}" --tray'


def is_autostart_enabled() -> bool:
    """Verifica se o início automático está registrado, aponta para algo existente e não foi bloqueado."""
    if os.name != "nt":
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, APP_REG_NAME)
    except OSError:
        return False
    if not isinstance(value, str) or not value.strip():
        return False
    raw = value.strip()
    exe_part = raw[1:].split('"')[0] if raw.startswith('"') else raw.split()[0]
    if not exe_part or not Path(exe_part).exists():
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_APPROVED_KEY, 0, winreg.KEY_READ) as key:
            approved, _ = winreg.QueryValueEx(key, APP_REG_NAME)
        # Bit 0 ligado = desativado pelo usuário no Gerenciador de Tarefas.
        if isinstance(approved, (bytes, bytearray)) and approved and approved[0] & 1:
            return False
    except OSError:
        pass
    return True


def set_autostart(enable: bool) -> bool:
    """Ativa ou desativa o início com o Windows. Retorna True se o registro foi alterado com sucesso."""
    if os.name != "nt":
        return False
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, launch_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_REG_NAME)
                except FileNotFoundError:
                    pass
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_APPROVED_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_BINARY, b"\x02" + b"\x00" * 11)
            else:
                try:
                    winreg.DeleteValue(key, APP_REG_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def take_over_legacy_autostart() -> bool:
    """Se uma versão anterior iniciava com o Windows, passa esse início para o app atual (evita abrir duas)."""
    if os.name != "nt":
        return False
    found = False
    for name in LEGACY_REG_NAMES:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, name)
        except OSError:
            continue
        found = found or (isinstance(value, str) and bool(value.strip()))
        for path in (REG_RUN_KEY, REG_APPROVED_KEY):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key, name)
            except OSError:
                pass
    return set_autostart(True) if found else False


def protect(text: str, decrypt: bool = False) -> str:
    """Criptografa (ou descriptografa) texto com a DPAPI, vinculada à conta do Windows."""
    if os.name != "nt":
        raise ValueError("Armazenamento protegido disponível somente no Windows.")

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    raw = base64.b64decode(text) if decrypt else text.encode("utf-8")
    buffer = ctypes.create_string_buffer(raw, len(raw))
    incoming = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    outgoing = Blob()
    crypt32 = ctypes.windll.crypt32
    function = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    if not function(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)):
        raise ValueError("O Windows não conseguiu proteger ou ler a chave salva.")
    try:
        result = ctypes.string_at(outgoing.pbData, outgoing.cbData)
        return result.decode("utf-8") if decrypt else base64.b64encode(result).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(outgoing.pbData)


def setup_process():
    """Ativa DPI nítido e define a identidade do app na barra de tarefas."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        pass


def open_folder(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(path))

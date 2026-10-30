"""Integração com o Windows: pastas, início automático, instância única e DPAPI."""
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import sys

from .edition import Edition

if os.name == "nt":
    import winreg
else:  # pragma: no cover - o app é exclusivo para Windows; mantém import possível em testes
    winreg = None

APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "dados"

REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_APPROVED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
ERROR_ALREADY_EXISTS = 183

_wake_event = None


def check_single_instance(edition: Edition) -> bool:
    """Garante uma instância por edição. Uma segunda abertura acorda a janela existente."""
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

        _wake_event = kernel32.CreateEventW(None, False, False, edition.wake_event)
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


def launch_command(edition: Edition) -> str:
    """Linha de comando usada pelo Windows para abrir o app minimizado na bandeja."""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}" --tray'

    exe_candidate = APP_DIR / edition.exe_name
    if exe_candidate.exists():
        return f'"{exe_candidate.resolve()}" --tray'

    pythonw = Path(sys.executable).with_name("pythonw.exe")
    interpreter = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{interpreter}" "{(APP_DIR / edition.script).resolve()}" --tray'


def is_autostart_enabled(edition: Edition) -> bool:
    """Verifica se o início automático está registrado, aponta para algo existente e não foi bloqueado."""
    if os.name != "nt":
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, edition.reg_name)
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
            approved, _ = winreg.QueryValueEx(key, edition.reg_name)
        # Bit 0 ligado = desativado pelo usuário no Gerenciador de Tarefas.
        if isinstance(approved, (bytes, bytearray)) and approved and approved[0] & 1:
            return False
    except OSError:
        pass
    return True


def set_autostart(edition: Edition, enable: bool) -> bool:
    """Ativa ou desativa o início com o Windows. Retorna True se o registro foi alterado com sucesso."""
    if os.name != "nt":
        return False
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, edition.reg_name, 0, winreg.REG_SZ, launch_command(edition))
            else:
                try:
                    winreg.DeleteValue(key, edition.reg_name)
                except FileNotFoundError:
                    pass
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_APPROVED_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, edition.reg_name, 0, winreg.REG_BINARY, b"\x02" + b"\x00" * 11)
            else:
                try:
                    winreg.DeleteValue(key, edition.reg_name)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def take_over_legacy_autostart(edition: Edition, legacy_name: str = "LuzCinemaV2") -> bool:
    """Se a v2 antiga iniciava com o Windows, passa esse início para esta edição (evita abrir as duas)."""
    if os.name != "nt":
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, legacy_name)
    except OSError:
        return False
    for path in (REG_RUN_KEY, REG_APPROVED_KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, legacy_name)
        except OSError:
            pass
    return set_autostart(edition, True)


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


def setup_process(edition: Edition):
    """Ativa DPI nítido e separa o ícone da barra de tarefas por edição."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(edition.app_id)
    except (AttributeError, OSError):
        pass


def open_folder(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(path))

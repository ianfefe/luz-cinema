"""Dublês de teste compartilhados (lâmpadas falsas sem rede)."""
import threading
import time


class FakeTinyTuya:
    """Imita tinytuya.BulbDevice o suficiente para o LocalBulb."""

    instances = []

    def __init__(self, device_id, ip, key, fail_status=False):
        self.calls = []
        self.dps = {"20": True, "21": "white", "22": 500, "23": 300, "24": "000003e803e8"}
        self.has_colour = True
        self.bulb_type = "B"
        self.dpset = {"switch": 20, "mode": 21, "brightness": 22, "colourtemp": 23, "colour": 24}
        self.fail_next = 0
        FakeTinyTuya.instances.append(self)

    def __getattr__(self, name):
        if name.startswith("set_socket") or name == "set_version":
            return lambda *a: None
        raise AttributeError(name)

    def _ok(self, *call):
        self.calls.append(call)
        if self.fail_next:
            self.fail_next -= 1
            raise ConnectionError("socket caiu")
        return {"dps": {}}

    def status(self):
        return {"dps": dict(self.dps)}

    def set_colour(self, r, g, b):
        return self._ok("colour", (r, g, b))

    def set_white_percentage(self, brightness, temp):
        return self._ok("white", brightness, temp)

    def turn_off(self):
        return self._ok("off")

    def set_multiple_values(self, values):
        return self._ok("restore", dict(values))

    def close(self):
        self.calls.append(("close",))


class FakeBulb:
    """Conexão falsa usada pelo BulbController."""

    def __init__(self, device=None, delay=0.0, fail=False):
        self.device = device
        self.delay = delay
        self.fail = fail
        self.calls = []
        self.lock = threading.Lock()

    def _record(self, *call):
        if self.delay:
            time.sleep(self.delay)
        if self.fail:
            raise ConnectionError("sem resposta")
        with self.lock:
            self.calls.append(call)

    def color(self, rgb, light_mode=False):
        self._record("color", tuple(rgb), light_mode)

    def set_manual(self, mode, rgb=None, brightness=100, temp=100):
        self._record("manual", mode, rgb, brightness, temp)

    def capture_state(self):
        self._record("capture")

    def restore(self):
        self._record("restore")

    def close(self):
        self.calls.append(("close",))


def wait_until(condition, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.01)
    return condition()

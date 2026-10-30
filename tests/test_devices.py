import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fakes import FakeBulb, wait_until  # noqa: E402
from luzcinema import devices as devices_module  # noqa: E402
from luzcinema.core import BulbError  # noqa: E402
from luzcinema.devices import BulbController, BulbDevice  # noqa: E402
from luzcinema.scenarios import DEFAULT_SCENARIOS  # noqa: E402


def make_controller(devices, **bulb_kwargs):
    bulbs, events = {}, []

    def connector(device):
        bulb = bulbs.setdefault(device.id, FakeBulb(device, **bulb_kwargs))
        return bulb

    controller = BulbController(devices, connector=connector, on_event=lambda k, p: events.append((k, p)))
    return controller, bulbs, events


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.left = BulbDevice("L", "Esquerda", zone="left")
        self.right = BulbDevice("R", "Direita", zone="right")
        self.off = BulbDevice("X", "Fora", zone="all", enabled=False)

    def test_zones_and_active_devices(self):
        controller, _, _ = make_controller([self.left, self.right, self.off])
        self.assertEqual(controller.required_zones(), {"left", "right"})
        self.assertEqual([d.id for d in controller.active_devices()], ["L", "R"])
        controller.close()

    def test_start_dispatch_and_restore(self):
        controller, bulbs, _ = make_controller([self.left, self.right])
        results = controller.start_cinema()
        self.assertEqual([err for _, err in results], [None, None])
        controller.dispatch_frame({"left": (255, 0, 0), "right": (0, 0, 255)}, dt=0.1, smoothing=0)
        self.assertTrue(wait_until(lambda: all(any(c[0] == "color" for c in b.calls) for b in bulbs.values())))
        self.assertEqual(next(c for c in bulbs["L"].calls if c[0] == "color")[1], (255, 0, 0))
        self.assertEqual(next(c for c in bulbs["R"].calls if c[0] == "color")[1], (0, 0, 255))
        controller.stop_cinema(restore=True)
        for bulb in bulbs.values():
            self.assertEqual(bulb.calls[0], ("capture",))
            self.assertEqual(bulb.calls[-1], ("restore",))
        controller.close()

    def test_busy_bulb_drops_frames_instead_of_queueing(self):
        controller, bulbs, _ = make_controller([self.left], delay=0.05)
        controller.start_cinema()
        for i in range(6):
            controller.dispatch_frame({"left": (i * 40, 10, 10)}, dt=0.01, smoothing=0)
        controller.stop_cinema(restore=False)
        sent = [c for c in bulbs["L"].calls if c[0] == "color"]
        self.assertLess(len(sent), 6)
        self.assertEqual(controller._in_flight, set())
        controller.close()

    def test_failed_bulb_reconnects_in_background_without_blocking(self):
        attempts = []

        def connector(device):
            attempts.append(time.monotonic())
            raise BulbError("offline")

        events = []
        controller = BulbController([self.left], connector=connector, on_event=lambda k, p: events.append(k))
        self.assertEqual(controller.start_cinema()[0][1], "offline")
        started = time.monotonic()
        controller.dispatch_frame({"left": (9, 9, 9)})
        self.assertLess(time.monotonic() - started, 0.05)
        self.assertTrue(wait_until(lambda: "bulb_error" in events))
        controller.dispatch_frame({"left": (9, 9, 9)})  # dentro do intervalo de espera: não tenta de novo
        time.sleep(0.05)
        self.assertEqual(len(attempts), 2)
        controller.close()

    def test_manual_command_and_scenario_per_zone(self):
        controller, bulbs, events = make_controller([self.left, self.right])
        controller.apply(["L"], {"mode": "colour", "rgb": (1, 2, 3), "brightness": 50})
        self.assertTrue(wait_until(lambda: bulbs.get("L") and bulbs["L"].calls))
        self.assertEqual(bulbs["L"].calls[-1], ("manual", "colour", (1, 2, 3), 50, 100))
        self.assertNotIn("R", bulbs)
        cyber = next(s for s in DEFAULT_SCENARIOS if s.id == "cyberpunk")
        controller.apply(None, lambda d: cyber.get_color_for_bulb(d.id, d.zone))
        self.assertTrue(wait_until(lambda: len(bulbs["L"].calls) == 2 and "R" in bulbs and bulbs["R"].calls))
        self.assertEqual(bulbs["L"].calls[-1][2], (0, 229, 255))
        self.assertEqual(bulbs["R"].calls[-1][2], (255, 0, 128))
        self.assertTrue(controller.power["L"])
        controller.close()

    def test_manual_failure_is_reported(self):
        controller, _, events = make_controller([self.left], fail=True)
        controller.turn_off()
        self.assertTrue(wait_until(lambda: any(k == "bulb_error" for k, _ in events)))
        controller.close()

    def test_remove_closes_connection_and_close_is_safe(self):
        controller, bulbs, _ = make_controller([self.left])
        controller.connect(self.left)
        controller.remove_device("L")
        self.assertEqual(bulbs["L"].calls[-1], ("close",))
        controller.close()
        controller.apply(None, {"mode": "off"})  # depois de fechado não deve lançar erro

    def test_device_from_dict_sanitizes(self):
        d = BulbDevice.from_dict({"id": " x ", "zone": "teto", "connection_type": "weird"})
        self.assertEqual((d.id, d.zone, d.connection_type), ("x", "all", "cloud"))

    def test_friendly_error_hides_internal_details(self):
        self.assertIn("rede", devices_module.friendly_error(TimeoutError("raw socket 0x1")))
        self.assertEqual(devices_module.friendly_error(BulbError("msg")), "msg")


if __name__ == "__main__":
    unittest.main()

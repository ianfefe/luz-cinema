import json
import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fakes import FakeBulb  # noqa: E402
from luzcinema.edition import MULTI, SIMPLE  # noqa: E402
from luzcinema.presets import CINEMA_PROFILES  # noqa: E402
from luzcinema.ui import app as app_module  # noqa: E402
from luzcinema.ui.tray import Tray  # noqa: E402


class AppTests(unittest.TestCase):
    def build(self, edition, devices=()):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / edition.config_name).write_text(json.dumps({"devices": list(devices)}), encoding="utf-8")
        self.bulbs = {}
        patches = [
            patch.object(Tray, "start", lambda self: None),
            patch.object(app_module, "is_autostart_enabled", lambda edition: False),
            patch("luzcinema.devices.default_connector",
                  lambda d: self.bulbs.setdefault(d.id, FakeBulb(d))),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.root = tk.Tk()
        self.root.withdraw()
        app = app_module.App(self.root, edition, data_dir=self.dir)
        app.controller.connector = lambda d: self.bulbs.setdefault(d.id, FakeBulb(d))
        self.addCleanup(self._close, app)
        return app

    def _close(self, app):
        app.quit()
        self.pump(app, 1.0, lambda: not app.alive)

    def pump(self, app, seconds, until=lambda: False):
        end = time.monotonic() + seconds
        while time.monotonic() < end and not until():
            try:
                self.root.update()
            except tk.TclError:
                return
            time.sleep(0.01)

    def test_simple_edition_pages_and_single_lamp(self):
        app = self.build(SIMPLE, [{"id": "a", "name": "Abajur", "zone": "left"}, {"id": "b", "name": "Outra"}])
        self.assertEqual(set(app.pages), {"cinema", "colors", "scenes", "lamps", "settings"})
        devices = app.controller.device_list()
        self.assertEqual([(d.id, d.zone) for d in devices], [("a", "all")])
        self.assertIsNone(app.target_ids())

    def test_profile_selection_and_manual_change(self):
        app = self.build(MULTI)
        profile = CINEMA_PROFILES[2]
        app.apply_profile(profile)
        self.assertEqual(app.profile.get(), profile["id"])
        self.assertAlmostEqual(app.settings_snapshot.brightness, profile["brightness"] / 100)
        app.vars["brightness"].set(80)
        self.assertEqual(app.profile.get(), "")
        self.assertAlmostEqual(app.settings_snapshot.brightness, 0.8)
        app.save_now()
        saved = json.loads((self.dir / MULTI.config_name).read_text(encoding="utf-8"))
        self.assertEqual(saved["brightness"], 80)
        self.assertEqual(saved["edition"], "multi")

    def test_preset_and_scenario_reach_the_lamp(self):
        app = self.build(SIMPLE, [{"id": "a", "name": "Abajur"}])
        app.apply_preset({"name": "Ciano", "mode": "colour", "rgb": (0, 229, 255), "brightness": 100})
        self.pump(app, 1.0, lambda: "a" in self.bulbs and self.bulbs["a"].calls)
        self.assertEqual(self.bulbs["a"].calls[-1][:3], ("manual", "colour", (0, 229, 255)))
        app.activate_scenario(app.scenarios[0])
        self.pump(app, 1.0, lambda: len(self.bulbs["a"].calls) >= 2)
        self.assertEqual(self.bulbs["a"].calls[-1][0], "manual")

    def test_cinema_runs_and_restores_and_manual_waits_for_stop(self):
        app = self.build(MULTI, [{"id": "a", "name": "Esq", "zone": "left"}])
        if not app.monitors:
            self.skipTest("sem monitor disponível")
        app.vars["interval"].set(0.05)
        app.start_cinema()
        self.pump(app, 3.0, lambda: any(c[0] == "color" for c in self.bulbs.get("a", FakeBulb()).calls))
        self.assertTrue(app.running)
        self.assertTrue(any(c[0] == "color" for c in self.bulbs["a"].calls))
        app.apply_manual()  # deve parar o cinema (sem restaurar) e só então aplicar
        self.pump(app, 3.0, lambda: not app.running and self.bulbs["a"].calls[-1][0] == "manual")
        self.assertFalse(app.running)
        kinds = [c[0] for c in self.bulbs["a"].calls]
        self.assertEqual(kinds[-1], "manual")
        self.assertNotIn("restore", kinds)

        app.start_cinema()
        self.pump(app, 2.0, lambda: kinds.count("capture") < [c[0] for c in self.bulbs["a"].calls].count("capture"))
        app.stop_cinema()
        self.pump(app, 3.0, lambda: not app.running)
        self.assertEqual(self.bulbs["a"].calls[-1][0], "restore")

    def test_start_without_lamps_goes_to_lamps_page(self):
        app = self.build(SIMPLE)
        app.start_cinema()
        self.assertFalse(app.running)
        self.assertEqual(app.current_page, "lamps")

    def test_theme_toggle_repaints(self):
        app = self.build(MULTI)
        app.toggle_theme()
        self.assertEqual(app.theme.mode, "light")
        self.root.update()
        self.assertEqual(app.pages["cinema"].canvas.cget("bg"), app.theme["BG"])


if __name__ == "__main__":
    unittest.main()

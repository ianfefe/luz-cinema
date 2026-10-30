import sys
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fakes import FakeTinyTuya  # noqa: E402
from luzcinema.core import (BulbError, LocalBulb, Settings, Smoother, compute_zones_colors, crop_zone,  # noqa: E402
                            downscale_frame, screen_color, should_send)


def solid(rgb, size=(160, 90)):
    return Image.new("RGB", size, rgb)


class ScreenColorTests(unittest.TestCase):
    def test_primary_colors_keep_their_hue(self):
        settings = Settings(brightness=1.0, crop_percent=0, dark_percent=0)
        r, g, b = screen_color(solid((255, 0, 0)), settings)
        self.assertGreater(r, 200)
        self.assertLess(max(g, b), 30)
        r, g, b = screen_color(solid((0, 0, 255)), settings)
        self.assertGreater(b, 200)

    def test_brightness_scales_output(self):
        full = screen_color(solid((0, 255, 0)), Settings(brightness=1.0, dark_percent=0))
        half = screen_color(solid((0, 255, 0)), Settings(brightness=0.5, dark_percent=0))
        self.assertLess(max(half), max(full))

    def test_dark_scene_turns_off_and_letterbox_is_ignored(self):
        self.assertEqual(screen_color(solid((3, 3, 3)), Settings(dark_percent=5)), (0, 0, 0))
        frame = solid((0, 0, 0))
        frame.paste((255, 120, 0), (0, 20, 160, 70))
        self.assertGreater(max(screen_color(frame, Settings(crop_percent=20, dark_percent=5))), 50)

    def test_neutral_scene_can_turn_off(self):
        settings = Settings(off_on_neutral=True, flash_boost=False, dark_percent=0)
        self.assertEqual(screen_color(solid((128, 128, 128)), settings), (0, 0, 0))

    def test_flashbang_surges_to_white(self):
        rgb = screen_color(solid((255, 255, 255)), Settings(flash_boost=True, brightness=0.3))
        self.assertGreaterEqual(min(rgb), 245)


class SettingsTests(unittest.TestCase):
    def test_invalid_values_raise_and_clamped_fixes_them(self):
        with self.assertRaises(ValueError):
            Settings(brightness=2)
        s = Settings.clamped(brightness=9, interval=0, crop_percent=12.6, smoothing=float("nan"))
        self.assertEqual((s.brightness, s.interval, s.crop_percent, s.smoothing), (1, 0.02, 13, 0.0))


class SmoothingAndSendTests(unittest.TestCase):
    def test_smoother_moves_gradually_and_black_is_instant(self):
        sm = Smoother()
        self.assertEqual(sm.update((0, 0, 200), 0.05, 0.5), (0, 0, 200))
        mid = sm.update((200, 0, 0), 0.05, 0.5)
        self.assertTrue(0 < mid[0] < 200)
        self.assertEqual(sm.update((0, 0, 0), 0.05, 0.5), (0, 0, 0))

    def test_should_send_on_power_edges_and_big_changes(self):
        self.assertTrue(should_send(None, (1, 1, 1), 0))
        self.assertTrue(should_send((0, 0, 0), (3, 3, 3), 0))
        self.assertFalse(should_send((100, 100, 100), (101, 100, 100), 1))
        self.assertTrue(should_send((100, 100, 100), (101, 100, 100), 9))


class ZoneTests(unittest.TestCase):
    def test_left_and_right_zones_follow_their_side(self):
        img = Image.new("RGB", (200, 100))
        img.paste((255, 0, 0), (0, 0, 100, 100))
        img.paste((0, 0, 255), (100, 0, 200, 100))
        colors = compute_zones_colors(img, Settings(brightness=1.0, crop_percent=0), {"left", "right", "all"})
        self.assertGreater(colors["left"][0], 200)
        self.assertGreater(colors["right"][2], 200)
        self.assertEqual(crop_zone(img, "center", 0).size, (100, 50))

    def test_downscale_keeps_aspect(self):
        self.assertEqual(downscale_frame(Image.new("RGB", (3840, 2160))).size, (320, 180))
        self.assertEqual(downscale_frame(Image.new("RGB", (100, 50))).size, (100, 50))


class LocalBulbTests(unittest.TestCase):
    def make(self):
        return LocalBulb("abc", "192.168.0.10", "0123456789abcdef", "3.5", factory=FakeTinyTuya)

    def test_rejects_bad_credentials(self):
        for args in (("", "192.168.0.10", "0123456789abcdef", "3.3"),
                     ("abc", "8.8.8.8", "0123456789abcdef", "3.3"),
                     ("abc", "192.168.0.10", "curta", "3.3"),
                     ("abc", "192.168.0.10", "0123456789abcdef", "9")):
            with self.assertRaises(BulbError):
                LocalBulb(*args, factory=FakeTinyTuya)

    def test_frames_map_to_commands(self):
        bulb = self.make()
        dev = bulb.device
        bulb.color((10, 20, 200))
        bulb.color((255, 255, 255))
        bulb.color((240, 230, 220), light_mode=True)
        bulb.color((0, 0, 0))
        bulb.color((0, 0, 0))  # já apagada: não repete
        kinds = [c[0] for c in dev.calls]
        self.assertEqual(kinds, ["colour", "white", "white", "off"])
        self.assertEqual(dev.calls[1], ("white", 100, 100))

    def test_reconnects_once_after_socket_failure(self):
        bulb = self.make()
        bulb.device.fail_next = 1
        bulb.color((0, 255, 0))
        self.assertIsNot(bulb.device, FakeTinyTuya.instances[-2])
        self.assertEqual(bulb.device.calls[-1], ("colour", (0, 255, 0)))

    def test_capture_state_then_restore_uses_latest_state(self):
        bulb = self.make()
        bulb.device.dps.update({"20": True, "21": "colour", "24": "00f003e803e8"})
        bulb.capture_state()
        bulb.color((5, 5, 200))
        bulb.restore()
        restored = bulb.device.calls[-1]
        self.assertEqual(restored[0], "restore")
        self.assertEqual(restored[1]["21"], "colour")


if __name__ == "__main__":
    unittest.main()

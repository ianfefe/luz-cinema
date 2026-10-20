import sys
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile
import time
import tkinter as tk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'outputs' / 'LuzCinema'))
from PIL import Image
from core import screen_color, Settings, Smoother, LocalBulb, BulbError
import luz_cinema as gui


class FakeBulb:
    def __init__(self, *args):
        self.has_colour = True
        self.bulb_type = 'B'
        self.dpset = {'switch':'20', 'mode':'21', 'brightness':'22', 'colourtemp':'23', 'colour':'24', 'scene':'25'}
        self.calls = []
    def __getattr__(self, name):
        if name.startswith('set_socket') or name == 'set_version':
            return lambda *args: None
        raise AttributeError(name)
    def status(self):
        return {'dps':{'20':False,'21':'white','22':400,'23':200,'24':'000003e803e8','26':4000}}
    def set_colour(self, *rgb):
        self.calls.append(('color',rgb)); return {}
    def set_white_percentage(self, bright, temp):
        self.calls.append(('white_pct', bright, temp)); return {}
    def turn_off(self):
        self.calls.append(('off',)); return {}
    def set_multiple_values(self, dps):
        self.calls.append(('restore',dps)); return {}
    def close(self):
        self.calls.append(('close',))


class Tests(unittest.TestCase):
    def test_primary_colors_and_brightness(self):
        for rgb in [(255,0,0),(0,255,0),(0,0,255),(255,255,255)]:
            value = screen_color(Image.new('RGB',(320,180),rgb), Settings(brightness=.5))
            self.assertTrue(all(abs(a-round(b*.5))<=1 for a,b in zip(value,rgb)))

    def test_dark_scene_dims_and_letterbox_is_removed(self):
        self.assertEqual(screen_color(Image.new('RGB',(320,180),'black'),Settings()),(0,0,0))
        image = Image.new('RGB',(100,100),'black')
        image.paste((255,0,0),(0,10,100,90))
        self.assertEqual(screen_color(image,Settings(brightness=1,crop_percent=10)),(255,0,0))
        untrimmed = screen_color(image,Settings(brightness=1,crop_percent=0))
        self.assertLess(untrimmed[0],255)

    def test_smoothing_monotonic_no_hue_wrap_artifact(self):
        s = Smoother()
        s.update((255,0,0),1,.8)
        a=s.update((0,0,255),.5,.8)
        b=s.update((0,0,255),.5,.8)
        self.assertLess(b[0],a[0]); self.assertGreater(b[2],a[2]); self.assertEqual(b[1],0)

    def test_controller_restore_only_known_fields(self):
        bulb=LocalBulb('test','192.168.1.12','1234567890123456','3.3',factory=FakeBulb)
        bulb.color((100,40,0)); bulb.color((0,0,0)); bulb.color((0,0,0)); bulb.color((20,30,40))
        bulb.restore(); bulb.close()
        calls=bulb.device.calls
        self.assertEqual(sum(c[0]=='off' for c in calls),1)
        restore=next(c[1] for c in calls if c[0]=='restore')
        self.assertIs(restore['20'],False)
        self.assertEqual(restore['21'],'white')
        self.assertNotIn('26',restore)
        self.assertEqual(calls[-1],('close',))

    def test_invalid_endpoints_and_errors_are_rejected(self):
        for address in ('8.8.8.8','localhost','127.0.0.1','0.0.0.0','224.0.0.1'):
            with self.assertRaises(BulbError):
                LocalBulb('test',address,'1234567890123456','3.3',factory=FakeBulb)
        for response in (None,{'Error':'key secret'},'bad'):
            with self.assertRaises(BulbError) as failure:
                LocalBulb.check(response)
            self.assertNotIn('secret',str(failure.exception))

    def test_dpapi_roundtrip(self):
        encrypted=gui.protect('sample-local-key')
        self.assertNotIn('sample-local-key',encrypted)
        self.assertEqual(gui.protect(encrypted,decrypt=True),'sample-local-key')

    def test_standout_color_detection_and_vibrancy(self):
        import colorsys
        # Dark muddy background with 16% bright cyan neon element
        frame = Image.new('RGB', (100, 100), (60, 55, 50))
        frame.paste((0, 220, 255), (30, 30, 70, 70))
        standout_color = screen_color(frame, Settings(brightness=1.0, standout=1.0, saturation=1.4))
        h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in standout_color))
        # Hue should be cyan (around 180-200 degrees), not muddy brown (around 30 degrees)
        self.assertGreater(h * 360, 160)
        self.assertLess(h * 360, 210)
        self.assertGreater(s, 0.9)  # High vibrancy saturation

        # Classic average mode (standout=0) should yield duller muddy color
        avg_color = screen_color(frame, Settings(brightness=1.0, standout=0.0, saturation=1.0))
        h_avg, s_avg, v_avg = colorsys.rgb_to_hsv(*(c / 255 for c in avg_color))
        self.assertLess(s_avg, s)

    def test_flashbang_burst_and_grey_scene_cutoff(self):
        # Flashbang (pure white) with flash_boost should output (255, 255, 255) even at lower base brightness
        flash_frame = Image.new('RGB', (100, 100), (255, 255, 255))
        flash_res = screen_color(flash_frame, Settings(brightness=0.45, flash_boost=True))
        self.assertEqual(flash_res, (255, 255, 255))

        # Flashbang should bypass long smoother lag
        smooth = Smoother()
        smooth.update((10, 10, 10), 0.25, 2.0)
        instant_flash = smooth.update(flash_res, 0.05, 2.0)
        self.assertEqual(instant_flash, (255, 255, 255))

        # Grey / Black and White scene with off_on_neutral=True should turn off (0, 0, 0)
        grey_frame = Image.new('RGB', (100, 100), (128, 128, 128))
        grey_res = screen_color(grey_frame, Settings(off_on_neutral=True))
        self.assertEqual(grey_res, (0, 0, 0))

        # But a grey frame with a vibrant accent should NOT turn off
        grey_frame.paste((255, 0, 0), (40, 20, 60, 80))
        accent_res = screen_color(grey_frame, Settings(off_on_neutral=True))
        self.assertNotEqual(accent_res, (0, 0, 0))

    def test_real_capture_preview_worker_and_stop(self):
        root=tk.Tk(); root.withdraw()
        app=gui.App(root)
        self.assertTrue(app.monitors)
        try:
            from mss import MSS
            with MSS() as c:
                c.grab(app.monitors[0])
        except Exception:
            self.skipTest("Captura de monitor indisponível na sessão de console atual.")
        app.start(False)
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            root.update(); time.sleep(.02)
        self.assertNotEqual(app.swatch['background'],gui.PANEL)
        app.stop()
        app.worker.join(timeout=4)
        self.assertFalse(app.worker.is_alive())
        app.close()

    def test_key_is_opt_in_and_protected(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(gui,'CONFIG',Path(folder)/'prefs.json'):
            root=tk.Tk(); root.withdraw()
            app=gui.App(root)
            app.key.set('1234567890123456')
            app.save_settings()
            raw=gui.CONFIG.read_text()
            self.assertNotIn('protected_key',raw)
            self.assertNotIn('1234567890123456',raw)
            app.remember.set(True); app.save_settings()
            raw=gui.CONFIG.read_text()
            self.assertIn('protected_key',raw)
            self.assertNotIn('1234567890123456',raw)
            root.update(); app.close()

    def test_presets_and_color_wheel(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(gui, 'CONFIG', Path(folder) / 'prefs.json'):
            root = tk.Tk()
            root.withdraw()
            app = gui.App(root)
            self.assertIsNotNone(app.color_wheel)
            # Test color wheel coords
            app.color_wheel.set_color_hsv(0.5, 0.8)
            self.assertEqual(app.manual_mode.get(), "colour")

            # Activate a factory preset
            app.activate_preset(gui.DEFAULT_PRESETS[0])  # Branco Frio
            self.assertEqual(app.manual_mode.get(), "white")
            self.assertEqual(app.manual_temp.get(), 100)

            # Save a custom preset
            app.manual_mode.set("colour")
            app.manual_hue = 0.33  # green
            app.manual_sat = 1.0
            app.manual_brightness.set(90)
            app.new_preset_entry.insert(0, "Meu Verde Neon")
            app.save_custom_preset()
            self.assertEqual(len(app.custom_presets), 1)
            self.assertEqual(app.custom_presets[0]["name"], "Meu Verde Neon")

            # Verify persisted in config
            raw = gui.CONFIG.read_text(encoding="utf-8")
            self.assertIn("Meu Verde Neon", raw)

            # Delete preset
            app.delete_custom_preset(0)
            self.assertEqual(len(app.custom_presets), 0)

            root.update()
            app.close()

    def test_local_bulb_set_manual(self):
        bulb = LocalBulb('test', '192.168.1.12', '1234567890123456', '3.3', factory=FakeBulb)
        bulb.set_manual('colour', rgb=(255, 0, 128), brightness=100)
        self.assertEqual(bulb.device.calls[-1], ('color', (255, 0, 128)))
        bulb.set_manual('white', brightness=80, temp=50)
        self.assertEqual(bulb.device.calls[-1], ('white_pct', 80, 50))
        bulb.close()

    def test_tray_and_window_close(self):
        root = tk.Tk()
        root.withdraw()
        app = gui.App(root)
        app.minimize_to_tray.set(True)
        # Mock tray icon existence
        class FakeIcon:
            def __init__(self):
                self.stopped = False
            def stop(self):
                self.stopped = True
        fake_icon = FakeIcon()
        app.tray_icon = fake_icon

        # on_window_close with minimize_to_tray=True should withdraw, not destroy
        with patch.object(root, 'withdraw') as mock_withdraw:
            app.on_window_close()
            mock_withdraw.assert_called_once()

        # Quit app completely
        app.quit_app()
        self.assertTrue(fake_icon.stopped)

    def test_three_tabs_and_connection_view(self):
        root = tk.Tk()
        root.withdraw()
        app = gui.App(root)
        self.assertEqual(len(app.tabs.tabs()), 3)
        tab_names = [app.tabs.tab(t, "text").strip() for t in app.tabs.tabs()]
        self.assertEqual(tab_names, ["Cinema", "Presets & Cores", "Conectar"])

        # Check connection view toggle
        app.connection_mode.set("Conta Tuya")
        app.update_connection_view()
        self.assertEqual(app.cloud_container.winfo_manager(), "pack")
        self.assertEqual(app.local_container.winfo_manager(), "")

        app.connection_mode.set("Rede local")
        app.update_connection_view()
        self.assertEqual(app.local_container.winfo_manager(), "pack")
        self.assertEqual(app.cloud_container.winfo_manager(), "")

        # Check help link opens popup
        self.assertIsNotNone(app.help_link)
        with patch.object(tk, "Toplevel") as mock_top:
            app.open_help_popup()
            mock_top.assert_called_once()

        app.close()

    def test_tray_submenus_monitors_and_presets(self):
        root = tk.Tk()
        root.withdraw()
        app = gui.App(root)
        app.monitors = [{"width": 1920, "height": 1080}, {"width": 2560, "height": 1440}]
        app.custom_presets = [{"name": "Custom 1", "mode": "white", "temp": 50, "brightness": 100}]
        app.update_tray_menu()

        menu = app.tray_icon.menu
        menu_titles = [item.text for item in menu.items if hasattr(item, "text")]
        self.assertIn("Sincronizar Cinema", menu_titles)
        self.assertIn("Presets", menu_titles)

        # Cinema submenu
        cinema_item = next(item for item in menu.items if getattr(item, "text", "") == "Sincronizar Cinema")
        sub_cinema_titles = [item.text for item in cinema_item.submenu.items]
        self.assertIn("Monitor 1 (1920x1080)", sub_cinema_titles)
        self.assertIn("Monitor 2 (2560x1440)", sub_cinema_titles)

        # Presets submenu
        presets_item = next(item for item in menu.items if getattr(item, "text", "") == "Presets")
        sub_preset_titles = [item.text for item in presets_item.submenu.items if hasattr(item, "text")]
        self.assertIn("Branco Frio", sub_preset_titles)
        self.assertIn("Custom 1", sub_preset_titles)

        # Test clicking tray items (pystray passes (icon, item))
        custom1_item = next(item for item in presets_item.submenu.items if getattr(item, "text", "") == "Custom 1")
        custom1_item(app.tray_icon)
        root.update()
        self.assertEqual(app.manual_mode.get(), "white")

        cinema_m2 = next(item for item in cinema_item.submenu.items if getattr(item, "text", "") == "Monitor 2 (2560x1440)")
        with patch.object(app, "start") as mock_start:
            cinema_m2(app.tray_icon)
            root.update()
            mock_start.assert_called_with(real=True)
            self.assertEqual(app.monitor_box.current(), 1)

        stop_item = next(item for item in menu.items if getattr(item, "text", "") == "Parar Iluminação")
        with patch.object(app, "stop") as mock_stop:
            stop_item(app.tray_icon)
            root.update()
            mock_stop.assert_called_once()

        off_item = next(item for item in menu.items if getattr(item, "text", "") == "Apagar Lâmpada")
        with patch.object(app, "turn_off_light") as mock_off:
            off_item(app.tray_icon)
            root.update()
            mock_off.assert_called_once()

        # Test tray icon visual changes
        app.set_tray_icon_visual(cinema_mode=True)
        self.assertIsNotNone(app.tray_icon.icon)

        app.set_tray_icon_visual(color_hex="#00e5ff", cinema_mode=False)
        self.assertIsNotNone(app.tray_icon.icon)

        app.set_tray_icon_visual(is_off=True)
        self.assertIsNotNone(app.tray_icon.icon)

        # Test preset click while cinema mode is running stops cinema without restoring old state
        app.running = True
        fake_bulb = FakeBulb()
        app.cached_manual_bulb = fake_bulb
        app.activate_preset(gui.DEFAULT_PRESETS[4])  # Ciano Neon
        self.assertTrue(getattr(app, "skip_restore_on_stop", False))
        self.assertEqual(app.manual_mode.get(), "colour")

        app.close()

    def test_theme_toggle_and_light_off(self):
        root = tk.Tk()
        root.withdraw()
        app = gui.App(root)
        app.theme_mode.set("dark")
        app.apply_theme()
        self.assertEqual(app.theme_mode.get(), "dark")
        self.assertEqual(app.current_theme["name"], "dark")
        self.assertEqual(app.theme_toggle_btn.cget("text"), "☀️ Modo Claro")

        # Toggle to light theme
        app.toggle_theme()
        root.update()
        self.assertEqual(app.theme_mode.get(), "light")
        self.assertEqual(app.current_theme["name"], "light")
        self.assertEqual(app.theme_toggle_btn.cget("text"), "🌙 Modo Escuro")

        # Toggle back to dark theme
        app.toggle_theme()
        root.update()
        self.assertEqual(app.theme_mode.get(), "dark")
        self.assertEqual(app.current_theme["name"], "dark")
        self.assertEqual(app.theme_toggle_btn.cget("text"), "☀️ Modo Claro")

        # Test turn off light
        app.running = True
        with patch.object(app, "apply_manual_light") as mock_manual:
            app.turn_off_light()
            root.update()
            self.assertFalse(app.running)
            self.assertTrue(getattr(app, "skip_restore_on_stop", False))
            mock_manual.assert_called_with("off")
            self.assertEqual(app.status.get(), "Lâmpada apagada.")

        # Test LocalBulb set_manual with mode="off"
        fake_bulb = FakeBulb()
        bulb = LocalBulb("test", "192.168.1.50", "1234567890123456", "3.3", factory=lambda *a: fake_bulb)
        bulb.set_manual("off")
        bulb.close()
        self.assertIn(("off",), fake_bulb.calls)

        app.close()

    def test_cct_and_hex_helpers(self):
        cold_rgb = gui.cct_to_rgb(100, 100)
        self.assertEqual(cold_rgb, (210, 230, 255))
        warm_rgb = gui.cct_to_rgb(0, 100)
        self.assertEqual(warm_rgb, (255, 180, 107))
        self.assertEqual(gui.rgb_to_hex((255, 0, 128)), "#ff0080")

    def test_autostart_sync_and_registry(self):
        with patch.object(gui, "set_autostart") as mock_set_auto, patch.object(gui, "is_autostart_enabled", return_value=True):
            with tempfile.TemporaryDirectory() as folder, patch.object(gui, 'CONFIG', Path(folder) / 'prefs.json'):
                # When preferences has start_with_windows=True, load_settings must call set_autostart(True)
                prefs_path = Path(folder) / 'prefs.json'
                prefs_path.write_text('{"start_with_windows": true}', encoding="utf-8")
                root = tk.Tk(); root.withdraw()
                app = gui.App(root)
                self.assertTrue(app.start_with_windows.get())
                mock_set_auto.assert_called_with(True)

                # When save_settings is called, set_autostart must also be called with current state
                mock_set_auto.reset_mock()
                app.start_with_windows.set(False)
                app.save_settings()
                mock_set_auto.assert_called_with(False)
                app.close()

    def test_single_instance_check(self):
        # First call should succeed (return True or bool)
        res = gui.check_single_instance()
        self.assertIsInstance(res, bool)

    def test_preset_color_hex_and_hex_to_rgb(self):
        from core import hex_to_rgb
        self.assertEqual(hex_to_rgb("#ff0080"), (255, 0, 128))
        self.assertEqual(hex_to_rgb("00e5ff"), (0, 229, 255))
        # Custom preset with explicit color_hex
        p1 = {"name": "Test1", "color_hex": "#123456"}
        self.assertEqual(gui.preset_color_hex(p1), "#123456")
        # White preset
        p2 = {"name": "Test2", "mode": "white", "temp": 100, "brightness": 100}
        self.assertEqual(gui.preset_color_hex(p2), "#d2e6ff")
        # Color preset without color_hex
        p3 = {"name": "Test3", "mode": "colour", "rgb": (255, 0, 0)}
        self.assertEqual(gui.preset_color_hex(p3), "#ff0000")

    def test_is_autostart_enabled_edge_cases(self):
        import winreg
        # Test 1: When registry entry does not exist
        with patch.object(winreg, "OpenKey", side_effect=FileNotFoundError):
            self.assertFalse(gui.is_autostart_enabled())

        # Test 2: When registry entry points to non-existent executable
        with patch.object(winreg, "OpenKey"), patch.object(winreg, "QueryValueEx", return_value=(r'"C:\NonExistent\FakeApp.exe" --tray', winreg.REG_SZ)):
            self.assertFalse(gui.is_autostart_enabled())

        # Test 3: When target executable exists, but StartupApproved has disabled flag (0x03)
        with patch.object(winreg, "OpenKey"), patch.object(Path, "exists", return_value=True):
            def mock_query(key, name):
                if name == gui.APP_REG_NAME:
                    return (b"\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00", winreg.REG_BINARY)
                return (r'"C:\Existing\App.exe" --tray', winreg.REG_SZ)
            with patch.object(winreg, "QueryValueEx", side_effect=mock_query):
                self.assertFalse(gui.is_autostart_enabled())


if __name__=='__main__':
    unittest.main(verbosity=2)

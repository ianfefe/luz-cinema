"""Suíte de testes automatizados para o Luz Cinema v2 (Multi-Lâmpadas, Zonas e Cenários)."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import tempfile
import tkinter as tk

from PIL import Image

# Configura importação explícita da v2 sem conflito com v1
V2_DIR = str(Path(__file__).resolve().parents[1] / "outputs" / "LuzCinema_v2")
if V2_DIR in sys.path:
    sys.path.remove(V2_DIR)
sys.path.insert(0, V2_DIR)

for mod_name in ["luz_cinema", "tab_views", "tray_manager", "win_platform", "multi_bulb", "scenarios"]:
    sys.modules.pop(mod_name, None)

import core
from multi_bulb import BulbDevice, MultiBulbController
from scenarios import DEFAULT_SCENARIOS, Scenario
import luz_cinema as gui_v2


class FakeBulb:
    def __init__(self, name="fake", *args):
        self.name = name
        self.calls = []
        self.original = [{"switch_led": True}]

    def color(self, rgb, light_mode=False):
        self.calls.append(("color", rgb, light_mode))

    def set_manual(self, mode, rgb=None, brightness=100, temp=100):
        self.calls.append(("manual", mode, rgb, brightness, temp))

    def turn_off(self):
        self.calls.append(("off",))

    def restore(self):
        self.calls.append(("restore",))

    def close(self):
        self.calls.append(("close",))


class TestLuzCinemaV2(unittest.TestCase):
    def setUp(self):
        # Garante que as chamadas utilizem o código da v2
        if V2_DIR in sys.path:
            sys.path.remove(V2_DIR)
        sys.path.insert(0, V2_DIR)

    def test_spatial_zone_cropping_and_colors(self):
        # Cria imagem com lado esquerdo vermelho puro e lado direito azul puro
        img = Image.new("RGB", (200, 100), (0, 0, 0))
        img.paste((255, 0, 0), (0, 0, 100, 100))      # Esquerda = Vermelho
        img.paste((0, 0, 255), (100, 0, 200, 100))    # Direita = Azul

        settings = core.Settings(brightness=1.0, crop_percent=0)

        # Recorta zonas
        left_crop = core.crop_zone(img, "left", crop_percent=0)
        right_crop = core.crop_zone(img, "right", crop_percent=0)
        all_crop = core.crop_zone(img, "all", crop_percent=0)

        # Calcula cores das zonas
        zones_colors = core.compute_zones_colors(img, settings, {"left", "right", "all"})

        # Lado esquerdo deve ser predominantemente vermelho
        self.assertGreater(zones_colors["left"][0], 200)
        self.assertLess(zones_colors["left"][2], 50)

        # Lado direito deve ser predominantemente azul
        self.assertGreater(zones_colors["right"][2], 200)
        self.assertLess(zones_colors["right"][0], 50)

    def test_multi_bulb_controller_and_zone_dispatch(self):
        bulb1 = BulbDevice(id="b1", name="Abajur Esquerdo", connection_type="local", zone="left")
        bulb2 = BulbDevice(id="b2", name="Abajur Direito", connection_type="local", zone="right")
        bulb3 = BulbDevice(id="b3", name="Luz Teto", connection_type="local", zone="all")

        controller = MultiBulbController([bulb1, bulb2, bulb3])
        self.assertEqual(controller.get_required_zones(), {"left", "right", "all"})

        # Injeta fakes
        fake1, fake2, fake3 = FakeBulb("b1"), FakeBulb("b2"), FakeBulb("b3")
        controller.active_connections["b1"] = fake1
        controller.active_connections["b2"] = fake2
        controller.active_connections["b3"] = fake3

        # Despacha frame cinema com zonas distintas
        zone_colors = {
            "left": (255, 0, 0),
            "right": (0, 0, 255),
            "all": (128, 0, 128),
        }
        controller.dispatch_cinema_frame(zone_colors, dt=0.5, smoothing=0.05)

        import time
        time.sleep(0.08)

        # fake1 (esquerda) deve receber comando com vermelho dominante
        self.assertTrue(any(c[0] == "color" and c[1][0] > 100 for c in fake1.calls))
        # fake2 (direita) deve receber comando com azul dominante
        self.assertTrue(any(c[0] == "color" and c[1][2] > 100 for c in fake2.calls))

    def test_scenarios_and_spatial_mapping(self):
        cinema_sc = next(s for s in DEFAULT_SCENARIOS if s.id == "cinema_setup")
        cyber_sc = next(s for s in DEFAULT_SCENARIOS if s.id == "cyberpunk")

        # Verifica mapeamento de zona do Cyberpunk: left=ciano neon (0,229,255), right=rosa (255,0,128)
        left_color = cyber_sc.get_color_for_bulb("lamp_left", zone="left")
        right_color = cyber_sc.get_color_for_bulb("lamp_right", zone="right")
        self.assertEqual(left_color["rgb"], (0, 229, 255))
        self.assertEqual(right_color["rgb"], (255, 0, 128))

        # Teste de aplicação do cenário através do MultiBulbController
        bulb1 = BulbDevice(id="b_left", name="Esq", zone="left")
        bulb2 = BulbDevice(id="b_right", name="Dir", zone="right")
        controller = MultiBulbController([bulb1, bulb2])

        fake1, fake2 = FakeBulb("Esq"), FakeBulb("Dir")
        controller.active_connections["b_left"] = fake1
        controller.active_connections["b_right"] = fake2

        controller.apply_scenario(cyber_sc)
        import time
        time.sleep(0.05)

        self.assertTrue(any(c[0] == "manual" and c[2] == (0, 229, 255) for c in fake1.calls))
        self.assertTrue(any(c[0] == "manual" and c[2] == (255, 0, 128) for c in fake2.calls))

    def test_v2_app_interface_and_tabs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_cfg = Path(tmp_dir) / "prefs_v2.json"
            with patch.object(gui_v2, "CONFIG", tmp_cfg):
                root = tk.Tk()
                root.withdraw()
                app = gui_v2.App(root)

                # Verifica 4 abas da v2
                self.assertEqual(len(app.tabs.tabs()), 4)
                tab_texts = [app.tabs.tab(t, "text").strip() for t in app.tabs.tabs()]
                self.assertIn("Cinema Multi-Lâmpadas", tab_texts[0])
                self.assertIn("Cenários & Lâmpadas", tab_texts[1])
                self.assertIn("Presets & Cores", tab_texts[2])
                self.assertIn("Conectar", tab_texts[3])

                # Adiciona lâmpada de teste
                dev = BulbDevice(id="test_lamp", name="Abajur Quarto", connection_type="local", zone="left")
                app.bulb_controller.devices[dev.id] = dev
                app.refresh_lamps_listbox_ui()
                app.refresh_cinema_lamps_ui()

                # Verifica se apareceu na listbox
                self.assertGreaterEqual(app.lamps_listbox.size(), 1)

                # Testa ativação de cenário pela interface
                with patch.object(app.bulb_controller, "apply_scenario"):
                    app.activate_scenario(DEFAULT_SCENARIOS[0])
                self.assertIn("Setup Cinema", app.status.get())

                # Salva cenário personalizado
                app.new_scenario_entry.insert(0, "Meu Cenário V2")
                app.save_current_as_scenario()
                self.assertTrue(any(s.name == "Meu Cenário V2" for s in app.scenarios))

                root.update()
                app.close()

    def test_system_tray_menu_initialization_and_actions(self):
        import inspect
        import pystray
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_cfg = Path(tmp_dir) / "prefs_v2.json"
            with patch.object(gui_v2, "CONFIG", tmp_cfg):
                root = tk.Tk()
                root.withdraw()
                app = gui_v2.App(root)

                self.assertIsNotNone(app.tray_icon, "Tray icon should be initialized")
                self.assertIsNotNone(app.tray_icon.menu, "Tray menu should be initialized")

                # Verifica itens principais da bandeja
                items = list(app.tray_icon.menu)
                item_names = [it.text for it in items]
                self.assertIn("Abrir Luz Cinema v2", item_names)
                self.assertIn("Sincronizar Cinema Multi-Lâmpadas", item_names)
                self.assertIn("Cenários", item_names)
                self.assertIn("Presets de Cores", item_names)
                self.assertIn("Sair", item_names)

                # Adiciona lâmpada e atualiza menu dinamicamente
                dev = BulbDevice(id="lamp_tray", name="Abajur Tray", zone="right")
                app.bulb_controller.devices[dev.id] = dev
                app.update_tray_menu()

                updated_items = list(app.tray_icon.menu)
                updated_names = [it.text for it in updated_items]
                self.assertIn("Lâmpadas Individuais", updated_names)

                # Validação exaustiva da árvore de menus e conformidade de argcount com pystray
                def validate_menu_items(menu):
                    found_actions = 0
                    for item in menu:
                        if item is pystray.Menu.SEPARATOR:
                            continue
                        self.assertTrue(hasattr(item, "text"))
                        if item.submenu:
                            found_actions += validate_menu_items(item.submenu)
                        else:
                            self.assertTrue(callable(item._action))
                            if hasattr(item._action, "__code__"):
                                argcount = item._action.__code__.co_argcount - (
                                    1 if inspect.ismethod(item._action) else 0
                                )
                                self.assertLessEqual(
                                    argcount, 2,
                                    f"Callback para '{item.text}' tem {argcount} argumentos, pystray exige <= 2"
                                )
                            found_actions += 1
                    return found_actions

                total_actions = validate_menu_items(app.tray_icon.menu)
                self.assertGreater(total_actions, 10, "Deveria haver múltiplos itens acionáveis no menu")

                # Testa restauração de janela e garantia de state('normal')
                root.iconify()
                self.assertEqual(root.state(), "iconic")
                app._show_window()
                self.assertEqual(root.state(), "normal")

                # Testa ações do menu via mock sem IO/rede
                with patch.object(app, "start") as mock_start:
                    app.start_cinema_from_tray(0)
                    root.update()
                    mock_start.assert_called_with(real=True)

                with patch.object(app, "activate_preset") as mock_preset:
                    app.activate_preset_from_tray({"name": "Teste", "mode": "white"})
                    root.update()
                    mock_preset.assert_called_once()

                with patch.object(app, "activate_scenario") as mock_sc:
                    app.activate_scenario(app.scenarios[0])
                    root.update()
                    mock_sc.assert_called_with(app.scenarios[0])

                with patch.object(app, "stop") as mock_stop:
                    app.stop()
                    mock_stop.assert_called_once()

                # Testa robustez do fallback se dados de monitores/cenários estiverem corrompidos
                app.monitors = [{"invalid_key": 123}]
                app.scenarios = [{"invalid": True}]
                app.update_tray_menu()
                self.assertIsNotNone(app.tray_icon.menu, "Menu deve ser gerado mesmo com dados incompletos/inválidos")

                # Testa criação de HMENU nativo do Win32 pelo backend do pystray
                callbacks = []
                hmenu = app.tray_icon._create_menu(app.tray_icon.menu, callbacks)
                self.assertIsNotNone(hmenu, "HMENU nativo deve ser alocado pelo Windows")
                self.assertGreater(hmenu, 0, "Handle HMENU deve ser válido (>0)")
                self.assertGreater(len(callbacks), 0, "Lista de callbacks do menu deve ser populada")

                root.update()
                app.close()

    def test_cinema_calibration_profiles(self):
        from presets_data import CINEMA_PROFILES
        self.assertEqual(len(CINEMA_PROFILES), 6)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_cfg = Path(tmp_dir) / "prefs_v2.json"
            with patch.object(gui_v2, "CONFIG", tmp_cfg):
                root = tk.Tk()
                root.withdraw()
                app = gui_v2.App(root)

                for prof in CINEMA_PROFILES:
                    app.apply_cinema_profile(prof)
                    self.assertAlmostEqual(app.brightness.get(), prof["brightness"])
                    self.assertAlmostEqual(app.saturation.get(), prof["saturation"])
                    self.assertAlmostEqual(app.standout.get(), prof["standout"])
                    self.assertAlmostEqual(app.smoothing.get(), prof["smoothing"])
                    self.assertAlmostEqual(app.interval.get(), prof["interval"])
                    self.assertEqual(app.crop.get(), prof["crop"])
                    self.assertAlmostEqual(app.dark_percent.get(), prof["dark_percent"])
                    self.assertEqual(app.off_on_neutral.get(), prof["off_on_neutral"])
                    self.assertEqual(app.flash_boost.get(), prof["flash_boost"])
                    self.assertEqual(app.light_mode.get(), prof["light_mode"])
                    self.assertIn(prof["name"], app.status.get())

                root.update()
                app.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)

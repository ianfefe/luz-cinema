import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from luzcinema import storage  # noqa: E402
from luzcinema.devices import BulbDevice  # noqa: E402

KEY = "gdHiGO{Xuy&}a#C4"


@unittest.skipUnless(os.name == "nt", "DPAPI só existe no Windows")
class StorageTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def test_roundtrip_never_writes_plain_key(self):
        data = dict(storage.DEFAULTS, devices=[BulbDevice("id1", "Abajur", "local", "192.168.0.9", KEY, zone="left"),
                                               BulbDevice("id2", "Teto", zone="top")])
        storage.save(data, self.dir)
        raw = (self.dir / storage.CONFIG_NAME).read_text(encoding="utf-8")
        self.assertNotIn(KEY, raw)
        self.assertIn("protected_key", raw)
        loaded, migrated = storage.load(self.dir)
        self.assertFalse(migrated)
        self.assertEqual(loaded["devices"][0].key, KEY)
        self.assertEqual([d.zone for d in loaded["devices"]], ["left", "top"])

    def test_single_lamp_always_follows_whole_screen(self):
        (self.dir / storage.CONFIG_NAME).write_text(json.dumps(
            {"devices": [{"id": "a", "zone": "left", "enabled": False}]}), encoding="utf-8")
        data, _ = storage.load(self.dir)
        self.assertEqual([(d.zone, d.enabled) for d in data["devices"]], [("all", True)])

    def test_migrates_v2_preferences(self):
        legacy = {"devices": [
            {"id": "a", "name": "Desligada", "enabled": False, "zone": "left"},
            {"id": "b", "name": "Principal", "connection_type": "local", "ip": "192.168.0.5", "key": KEY,
             "zone": "right", "enabled": True}],
            "brightness": 35.0, "theme_mode": "light", "interval": 0.04}
        (self.dir / storage.LEGACY_V2).write_text(json.dumps(legacy), encoding="utf-8")
        data, migrated = storage.load(self.dir)
        self.assertTrue(migrated)
        self.assertEqual([(d.id, d.zone, d.enabled) for d in data["devices"]],
                         [("a", "left", False), ("b", "right", True)])
        self.assertEqual(data["devices"][1].key, KEY)
        self.assertEqual((data["brightness"], data["theme_mode"]), (35.0, "light"))

    def test_migrates_3_0_editions_preferring_simple(self):
        (self.dir / "preferencias_multi.json").write_text(json.dumps(
            {"devices": [{"id": "m1"}, {"id": "m2"}], "brightness": 80.0}), encoding="utf-8")
        (self.dir / "preferencias_simples.json").write_text(json.dumps(
            {"devices": [{"id": "s1"}], "brightness": 60.0}), encoding="utf-8")
        (self.dir / storage.LEGACY_V2).write_text(json.dumps({"brightness": 10.0}), encoding="utf-8")
        data, migrated = storage.load(self.dir)
        self.assertTrue(migrated)
        self.assertEqual(([d.id for d in data["devices"]], data["brightness"]), (["s1"], 60.0))
        (self.dir / "preferencias_simples.json").unlink()
        data, _ = storage.load(self.dir)
        self.assertEqual([d.id for d in data["devices"]], ["m1", "m2"])

    def test_corrupt_file_falls_back_to_defaults(self):
        (self.dir / storage.CONFIG_NAME).write_text("{oops", encoding="utf-8")
        data, _ = storage.load(self.dir)
        self.assertEqual(data["brightness"], storage.DEFAULTS["brightness"])


if __name__ == "__main__":
    unittest.main()

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from luzcinema import storage  # noqa: E402
from luzcinema.devices import BulbDevice  # noqa: E402
from luzcinema.edition import MULTI, SIMPLE  # noqa: E402

KEY = "gdHiGO{Xuy&}a#C4"


@unittest.skipUnless(os.name == "nt", "DPAPI só existe no Windows")
class StorageTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def test_roundtrip_never_writes_plain_key(self):
        data = dict(storage.DEFAULTS, devices=[BulbDevice("id1", "Abajur", "local", "192.168.0.9", KEY, zone="left")])
        storage.save(MULTI, data, self.dir)
        raw = (self.dir / MULTI.config_name).read_text(encoding="utf-8")
        self.assertNotIn(KEY, raw)
        self.assertIn("protected_key", raw)
        loaded, migrated = storage.load(MULTI, self.dir)
        self.assertFalse(migrated)
        self.assertEqual(loaded["devices"][0].key, KEY)
        self.assertEqual(loaded["devices"][0].zone, "left")

    def test_migrates_v2_preferences(self):
        legacy = {"devices": [
            {"id": "a", "name": "Desligada", "enabled": False, "zone": "left"},
            {"id": "b", "name": "Principal", "connection_type": "local", "ip": "192.168.0.5", "key": KEY,
             "zone": "right", "enabled": True}],
            "brightness": 35.0, "theme_mode": "light", "interval": 0.04}
        (self.dir / storage.LEGACY_V2).write_text(json.dumps(legacy), encoding="utf-8")
        simple, migrated = storage.load(SIMPLE, self.dir)
        self.assertTrue(migrated)
        self.assertEqual([d.id for d in simple["devices"]], ["b"])  # só uma, priorizando a ativa
        self.assertEqual(simple["devices"][0].zone, "all")
        self.assertEqual(simple["devices"][0].key, KEY)
        self.assertEqual((simple["brightness"], simple["theme_mode"]), (35.0, "light"))
        multi, _ = storage.load(MULTI, self.dir)
        self.assertEqual(len(multi["devices"]), 2)

    def test_corrupt_file_falls_back_to_defaults(self):
        (self.dir / SIMPLE.config_name).write_text("{oops", encoding="utf-8")
        data, _ = storage.load(SIMPLE, self.dir)
        self.assertEqual(data["brightness"], storage.DEFAULTS["brightness"])


if __name__ == "__main__":
    unittest.main()

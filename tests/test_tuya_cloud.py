import unittest
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'outputs'/'LuzCinema'))
from tuya_cloud import CloudBulb
from core import BulbError

class CloudTests(unittest.TestCase):
    def setup_bulb(self,mode='white',online=True):
        self.sent=[]
        self.fail=False
        functions={k:SimpleNamespace(values='{}') for k in ('switch_led','work_mode','bright_value_v2','temp_value_v2','colour_data_v2','scene_data_v2')}
        functions['colour_data_v2'].values='{"h":{"max":360},"s":{"max":1000},"v":{"max":1000}}'
        device=SimpleNamespace(id='lamp',online=online,function=functions,status={'switch_led':False,'work_mode':mode,'bright_value_v2':500,'temp_value_v2':300,'colour_data_v2':'{"h":120,"s":1000,"v":500}','countdown_1':300,'scene_data_v2':'scene-original'})
        def post(path,params,body):
            self.sent.append(body['commands'])
            return {'success':not self.fail,'result':not self.fail}
        manager=SimpleNamespace(device_repository=SimpleNamespace(query_devices_by_ids=lambda ids:[device]),customer_api=SimpleNamespace(post=post,session=SimpleNamespace(close=lambda:None)))
        return CloudBulb(session={'device_id':'lamp'},manager=manager)

    def test_rgb_encoding_and_white_restore(self):
        import json
        bulb=self.setup_bulb()
        bulb.color((0,0,128))
        cmd={c['code']:c['value'] for c in self.sent[0]}
        rgb=json.loads(cmd['colour_data_v2'])
        self.assertEqual(rgb,{'h':240,'s':1000,'v':502})
        self.assertTrue(cmd['switch_led']); self.assertEqual(cmd['work_mode'],'colour')
        bulb.restore()
        restored={c['code']:c['value'] for c in self.sent[-1]}
        self.assertFalse(restored['switch_led']); self.assertEqual(restored['work_mode'],'white')
        self.assertNotIn('countdown_1',restored); self.assertNotIn('scene_data_v2',restored)

    def test_failed_send_still_attempts_restore(self):
        bulb=self.setup_bulb()
        self.fail=True
        with self.assertRaises(BulbError):bulb.color((100,0,0))
        self.assertTrue(bulb.changed)
        self.fail=False
        bulb.restore(); self.assertFalse(bulb.changed)

    def test_offline_and_music_rejected(self):
        with self.assertRaises(BulbError):self.setup_bulb(online=False)
        with self.assertRaises(BulbError):self.setup_bulb(mode='music')

    def test_read_only_test_sends_nothing_and_black_turns_off(self):
        bulb=self.setup_bulb(); bulb.restore()
        self.assertEqual(self.sent,[])
        bulb.color((0,0,0))
        self.assertEqual(self.sent,[])
        bulb.color((60,20,100));bulb.color((0,0,0))
        self.assertEqual(self.sent[-1],[{'code':'switch_led','value':False}])

    def test_subsequent_color_only_sends_new_color(self):
        bulb=self.setup_bulb();bulb.color((128,0,0));bulb.color((0,128,0))
        self.assertEqual([c['code'] for c in self.sent[-1]],['colour_data_v2'])
        bulb.color((0,0,0));bulb.color((0,128,0))
        self.assertEqual({c['code'] for c in self.sent[-1]},{'colour_data_v2','switch_led'})

    def test_flashbang_triggers_cold_white_mode(self):
        bulb=self.setup_bulb()
        bulb.color((255,255,255))
        cmd={c['code']:c['value'] for c in self.sent[-1]}
        self.assertEqual(cmd['work_mode'],'white')
        self.assertEqual(cmd['bright_value_v2'],1000)
        self.assertEqual(cmd['temp_value_v2'],1000)

    def test_light_mode_triggers_cct_white_and_warm(self):
        bulb=self.setup_bulb()
        # White webpage -> white mode cold white
        bulb.color((245,245,245), light_mode=True)
        cmd={c['code']:c['value'] for c in self.sent[-1]}
        self.assertEqual(cmd['work_mode'],'white')
        self.assertEqual(cmd['temp_value_v2'],1000)

        # Warm white / meio laranja webpage -> white mode warm white (lower temp_value)
        bulb.color((255,215,170), light_mode=True)
        cmd={c['code']:c['value'] for c in self.sent[-1]}
        self.assertEqual(cmd['work_mode'],'white')
        self.assertLess(cmd['temp_value_v2'],300)

        # Saturated color -> should return to colour mode
        bulb.color((0,150,255), light_mode=True)
        cmd={c['code']:c['value'] for c in self.sent[-1]}
        self.assertEqual(cmd['work_mode'],'colour')
        self.assertIn('colour_data_v2',cmd)

    def test_authorization_endpoint_validation(self):
        from vincular_tuya import check_endpoint
        for value in ('http://apigw.tuyaus.com','https://tuyaus.com.attacker.invalid','https://user:pass@tuyaus.com','https://tuyaus.com:4433'):
            with self.assertRaises(ValueError):check_endpoint(value)
        self.assertEqual(check_endpoint('https://apigw.tuyaus.com/'),'https://apigw.tuyaus.com')

if __name__=='__main__':unittest.main(verbosity=2)

"""Account-authorized control of the one selected bulb via Tuya sharing SDK."""
from __future__ import annotations

import colorsys
from functools import partial
import json
import logging
import threading
import time
from copy import deepcopy

from core import BulbError, is_white_cct_candidate, calc_cct_values

SESSION_LOCK = threading.Lock()


def load_session():
    from vincular_tuya import SESSION_FILE
    from luz_cinema import protect
    try:
        with SESSION_LOCK:
            return json.loads(protect(SESSION_FILE.read_text(encoding='ascii'),decrypt=True))
    except Exception:
        raise BulbError('Vincule sua conta primeiro na aba Conta Tuya.') from None


def update_session(data):
    from vincular_tuya import save_session
    with SESSION_LOCK:
        save_session(data)


class TokenListener:
    def __init__(self, session):
        self.session=session

    def update_token(self, info):
        self.session['token_info']=info
        update_session(self.session)


def make_manager(session):
    from tuya_sharing import Manager
    from vincular_tuya import CLIENT_ID, check_endpoint
    logging.getLogger('tuya_sharing').setLevel(logging.CRITICAL)
    if session.get('client_id')!=CLIENT_ID:
        raise BulbError('Registro da autorização não reconhecido. Vincule a conta novamente.')
    endpoint=check_endpoint(session['endpoint'])
    manager=Manager(CLIENT_ID,session['user_code'],session['terminal_id'],endpoint,
                    session['token_info'],TokenListener(session))
    manager.customer_api.session.request=partial(manager.customer_api.session.request,timeout=(4,8))
    return manager


class CloudBulb:
    min_interval = 0.25

    def __init__(self, session=None, manager=None, device_id=None):
        self.session = deepcopy(session) if session else load_session()
        self.device_id = device_id or self.session.get('device_id')
        if not self.device_id:
            raise BulbError('Informe o ID virtual da sua lâmpada ao vincular a conta.')
        self.manager = manager or make_manager(self.session)
        self.changed=False
        self.last_rgb=None
        self.last_ack_ms=None
        self.last_request=0.0
        self.off=False
        self.color_mode=False
        try:
            self.device=self.read_device()
            if not self.device.online:
                raise BulbError('A lâmpada está offline na Tuya. Confira no aplicativo.')
            self.functions=self.device.function
            self.switch=next((k for k in ('switch_led','switch') if k in self.functions),None)
            self.colour=next((k for k in ('colour_data_v2','colour_data','color_data_v2') if k in self.functions),None)
            self.bright=next((k for k in ('bright_value_v2','bright_value') if k in self.functions),None)
            self.temp=next((k for k in ('temp_value_v2','temp_value') if k in self.functions),None)
            if not self.switch or not self.colour or 'work_mode' not in self.functions:
                raise BulbError('A Tuya não disponibilizou os controles RGB necessários para esta lâmpada.')
            self.off=not self.device.status.get(self.switch,False)
            self.color_mode=self.device.status.get('work_mode')=='colour'
            self.white_mode=self.device.status.get('work_mode')=='white'
            self.original=self.restore_commands(self.device.status,self.functions,self.switch,self.colour)
            if not self.original:
                raise BulbError('Não foi possível ler o estado necessário para restaurar a luz.')
            spec=self.functions[self.colour].values
            spec=json.loads(spec) if isinstance(spec,str) else spec
            self.hmax=spec.get('h',{}).get('max',360)
            self.smax=spec.get('s',{}).get('max',1000)
            self.vmax=spec.get('v',{}).get('max',1000)
            self.bmax=1000
            if self.bright and hasattr(self.functions[self.bright],'values'):
                bspec=self.functions[self.bright].values
                bspec=json.loads(bspec) if isinstance(bspec,str) else bspec
                self.bmax=bspec.get('max',1000) if isinstance(bspec,dict) else 1000
            self.tmax=1000
            if self.temp and hasattr(self.functions[self.temp],'values'):
                tspec=self.functions[self.temp].values
                tspec=json.loads(tspec) if isinstance(tspec,str) else tspec
                self.tmax=tspec.get('max',1000) if isinstance(tspec,dict) else 1000
            if self.hmax!=360 or self.smax not in (255,1000) or self.vmax not in (255,1000):
                raise BulbError('A escala de cores desta lâmpada ainda não é compatível.')
        except Exception:
            self.close()
            raise

    @staticmethod
    def restore_commands(status,functions,switch,colour):
        if switch not in status or 'work_mode' not in status:
            return []
        allowed=(colour,'bright_value_v2','bright_value','temp_value_v2','temp_value')
        commands=[{'code':k,'value':status[k]} for k in allowed if k in status and k in functions]
        # Restore a scene only when it was actually active. Timers and automation stay untouched.
        if status['work_mode']=='scene':
            scene=next((k for k in ('scene_data_v2','scene_data') if k in status and k in functions),None)
            if scene:
                commands.append({'code':scene,'value':status[scene]})
        if status['work_mode']=='music':
            raise BulbError('Desative o modo música no Tuya antes de sincronizar; o fluxo de música anterior não pode ser restaurado.')
        commands.extend([{'code':'work_mode','value':status['work_mode']}, {'code':switch,'value':status[switch]}])
        return commands

    def read_device(self):
        try:
            devices=self.manager.device_repository.query_devices_by_ids([self.device_id])
            device=next((d for d in devices if d.id==self.device_id),None)
            if device is None:
                raise BulbError('A lâmpada não foi localizada na conta autorizada. Confira o ID virtual.')
            return device
        except BulbError:
            raise
        except Exception:
            raise BulbError('Falha ao consultar a Tuya. Verifique a internet ou vincule a conta novamente.') from None

    def send(self, commands):
        try:
            # Bound request rate without accumulating stale frames or parallel requests.
            delay=self.min_interval-(time.monotonic()-self.last_request)
            if delay>0:
                time.sleep(delay)
            self.last_request=time.monotonic()
            started=self.last_request
            response=self.manager.customer_api.post(f'/v1.1/m/thing/{self.device_id}/commands',None,{'commands':commands})
            if not isinstance(response,dict) or not response.get('success') or response.get('result') is False:
                raise ValueError()
            self.last_ack_ms=round((time.monotonic()-started)*1000)
        except Exception:
            raise BulbError('A Tuya não confirmou o comando. A sincronização foi interrompida; confira sua conexão.') from None

    def is_white_cct_candidate(self, rgb):
        return is_white_cct_candidate(rgb)

    def calc_cct(self, rgb):
        return calc_cct_values(rgb, self.bmax, self.tmax)

    def _build_white_commands(self, bright_val, temp_val):
        commands = [{'code': 'work_mode', 'value': 'white'}, {'code': self.bright, 'value': bright_val}]
        if self.temp:
            commands.append({'code': self.temp, 'value': temp_val})
        if self.off or not getattr(self, 'white_mode', False):
            commands.append({'code': self.switch, 'value': True})
        return commands

    def color(self, rgb, light_mode=False):
        if max(rgb) <= 2:
            if self.off:
                return
            commands = [{'code': self.switch, 'value': False}]
        elif min(rgb) >= 245 and self.bright:
            # Flashbang: dispara LEDs brancos de alta potência (Branco Frio / 100%)
            commands = self._build_white_commands(self.bmax, self.tmax)
            self.color_mode = False
            self.white_mode = True
        elif light_mode and self.bright and self.is_white_cct_candidate(rgb):
            # Modo Claro: páginas e telas claras usam LEDs brancos CCT de alta potência
            bright_val, temp_val = self.calc_cct(rgb)
            commands = self._build_white_commands(bright_val, temp_val)
            self.color_mode = False
            self.white_mode = True
        else:
            h, s, v = colorsys.rgb_to_hsv(*(value / 255 for value in rgb))
            value = json.dumps({'h': round(h * self.hmax), 's': round(s * self.smax), 'v': round(v * self.vmax)}, separators=(',', ':'))
            commands = [{'code': self.colour, 'value': value}]
            if not self.color_mode:
                commands.append({'code': 'work_mode', 'value': 'colour'})
            if self.off or not self.color_mode:
                commands.append({'code': self.switch, 'value': True})
            self.color_mode = True
            self.white_mode = False
        # An unknown result may have changed the lamp, so restoration is still attempted.
        self.changed=True
        self.send(commands)
        self.last_rgb=rgb
        self.off=max(rgb)<=2
        if not self.off and not getattr(self,'white_mode',False):
            self.color_mode=True

    def set_manual(self, mode, rgb=None, brightness=100, temp=100):
        if mode == "off":
            commands = [{'code': self.switch, 'value': False}]
            self.send(commands)
            self.off = True
        elif mode == "white" and self.bright:
            bright_val = round(max(10, min(self.bmax, (brightness / 100.0) * self.bmax)))
            temp_val = round(max(0, min(self.tmax, (temp / 100.0) * self.tmax)))
            commands = self._build_white_commands(bright_val, temp_val)
            self.send(commands)
            self.color_mode = False
            self.white_mode = True
            self.off = False
        elif rgb:
            h, s, v = colorsys.rgb_to_hsv(*(val / 255.0 for val in rgb))
            val_str = json.dumps({'h': round(h * self.hmax), 's': round(s * self.smax), 'v': round(v * self.vmax)}, separators=(',', ':'))
            commands = [{'code': self.colour, 'value': val_str}, {'code': 'work_mode', 'value': 'colour'}, {'code': self.switch, 'value': True}]
            self.send(commands)
            self.color_mode = True
            self.white_mode = False
            self.off = False

    def restore(self):
        if self.changed:
            self.send(self.original)
            self.changed=False

    def close(self):
        if getattr(self,'manager',None):
            self.manager.customer_api.session.close()

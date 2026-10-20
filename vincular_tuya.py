"""Interactive Tuya account link using the published HA device-sharing flow.

The public application registration identifies this login as Home Assistant.
This independent helper clearly discloses that identity before authorization.
No password is requested. Tokens remain local, protected by Windows DPAPI.
"""
from __future__ import annotations

import argparse
from functools import partial
import json
import logging
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from urllib.parse import urlsplit

from PIL import ImageTk
import qrcode
from tuya_sharing import LoginControl, Manager
from luz_cinema import protect, APP_DIR

CLIENT_ID = "HA_3y9q4ak7g4ephrvke"
SCHEMA = "haauthorize"
SESSION_FILE = APP_DIR / "dados" / "tuya.enc"


def check_endpoint(endpoint):
    parsed = urlsplit(endpoint)
    host = parsed.hostname or ""
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Destino de autenticação inválido.")
    if not any(host == base or host.endswith('.'+base) for base in ('iotbing.com','tuyaus.com','tuyaeu.com','tuyacn.com','tuya.com','tuyain.com')):
        raise ValueError("Destino não reconhecido como serviço Tuya.")
    return endpoint.rstrip('/')


def session_from_result(info, user_code, device_id):
    endpoint = check_endpoint(info.get('endpoint') or info.get('end_point') or '')
    fields = ('t','uid','expire_time','access_token','refresh_token')
    if not all(info.get(k) is not None for k in fields) or not info.get('terminal_id'):
        raise ValueError("Autorização retornou dados incompletos.")
    return {'client_id': CLIENT_ID, 'user_code': user_code, 'terminal_id':info['terminal_id'],
            'endpoint':endpoint, 'token_info':{k:info[k] for k in fields}, 'device_id':device_id}


def save_session(session):
    encoded = protect(json.dumps(session))
    SESSION_FILE.parent.mkdir(parents=True,exist_ok=True)
    temporary = SESSION_FILE.with_suffix('.tmp')
    temporary.write_text(encoded,encoding='ascii')
    temporary.replace(SESSION_FILE)


class LinkWindow:
    def __init__(self, root, user_code='', device_id=''):
        self.root = root
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.thread = None
        self.photo = None
        self.timer = None
        self.target = tk.StringVar(value=device_id)
        root.title('Luz Cinema · Autorizar Tuya')
        root.geometry('660x820')
        root.configure(bg='#10121c')
        self.status = tk.StringVar(value='Pronto para gerar o QR code.')
        self.code = tk.StringVar(value=user_code)
        self.label(root,'Conectar a conta Tuya',18).pack(pady=(20,10))
        self.label(root,'Usa o fluxo público Tuya / Home Assistant.\nEsse nome pode aparecer na autorização no celular.',11).pack(pady=6)
        self.label(root,'A autorização permite acesso aos dispositivos compartilhados\ncom a integração. Este programa usará a lâmpada indicada.\nNenhuma senha é solicitada e nenhuma cor será alterada nesta etapa.',10).pack(pady=8)
        row = ttk.Frame(root)
        row.pack(pady=6)
        ttk.Label(row,text='Código de usuário:').pack(side='left')
        self.entry=ttk.Entry(row,textvariable=self.code,width=18)
        self.entry.pack(side='left',padx=8)
        self.button=ttk.Button(row,text='Gerar QR code',command=self.start)
        self.button.pack(side='left')
        target_row=ttk.Frame(root)
        target_row.pack(pady=5)
        ttk.Label(target_row,text='ID virtual da lâmpada:').pack(side='left')
        self.target_entry=ttk.Entry(target_row,textvariable=self.target,width=32)
        self.target_entry.pack(side='left',padx=8)
        self.qr_label=tk.Label(root,bg='#10121c',height=1)
        self.qr_label.pack(pady=10)
        self.label(root,'No Tuya Smart: + → Escanear.\nLeia o QR e confirme a autorização no próprio aplicativo.',11).pack(pady=8)
        self.label(root,'A sessão autorizada será salva neste computador com\nproteção do Windows para conectar o Luz Cinema.',10).pack(pady=5)
        tk.Label(root,textvariable=self.status,fg='#b6ffc7',bg='#10121c',wraplength=610,font=('Segoe UI',11)).pack(padx=20,pady=10)
        ttk.Button(root,text='Fechar',command=self.close).pack(pady=6)
        root.protocol('WM_DELETE_WINDOW',self.close)
        self.timer=root.after(100,self.drain)

    @staticmethod
    def label(parent,text,size):
        return tk.Label(parent,text=text,bg='#10121c',fg='#f1f2fc',font=('Segoe UI',size),justify='center')

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        code=self.code.get().strip()
        target_id=self.target.get().strip()
        if not code or not code.isalnum() or len(code)>64:
            self.status.set('Confira o código de usuário no Tuya Smart.')
            return
        if not target_id or not target_id.isalnum() or len(target_id)>100:
            self.status.set('Informe o ID virtual da sua lâmpada, exibido no Tuya Smart.')
            return
        self.cancel.clear()
        self.button.configure(state='disabled')
        self.entry.configure(state='disabled')
        self.target_entry.configure(state='disabled')
        self.status.set('Solicitando QR code à Tuya…')
        def run():
            login=None
            try:
                login=LoginControl()
                login.session.request=partial(login.session.request,timeout=(5,12))
                response=login.qr_code(CLIENT_ID,SCHEMA,code)
                if not response.get('success'):
                    self.events.put(('status','A Tuya recusou a solicitação. Confira o código e tente novamente.'))
                    return
                token=response.get('result',{}).get('qrcode')
                if not isinstance(token,str) or not token:
                    raise ValueError()
                qr=qrcode.QRCode(box_size=8,border=4)
                qr.add_data(f'tuyaSmart--qrLogin?token={token}')
                qr.make(fit=True)
                image=qr.make_image(fill_color='black',back_color='white').convert('RGB')
                self.events.put(('qr',image))
                self.events.put(('status','Aguardando sua confirmação no celular. O QR expira em poucos minutos.'))
                end=time.monotonic()+180
                while time.monotonic()<end and not self.cancel.wait(3):
                    ok,info=login.login_result(token,CLIENT_ID,code)
                    if not ok:
                        continue
                    session=session_from_result(info,code,target_id)
                    save_session(session)
                    self.events.put(('status','Autorização recebida e protegida no Windows. Pode voltar ao chat para continuarmos a conexão.'))
                    # No device command is sent here; inspect only the requested bulb.
                    manager=Manager(CLIENT_ID,code,session['terminal_id'],session['endpoint'],session['token_info'])
                    manager.customer_api.session.request=partial(manager.customer_api.session.request,timeout=(5,12))
                    try:
                        if target_id:
                            devices=manager.device_repository.query_devices_by_ids([target_id])
                            target=next((d for d in devices if d.id==target_id),None)
                            if target:
                                # Save only the target bulb's metadata, encrypted together with auth.
                                session['bulb']={k:getattr(target,k,None) for k in ('id','name','online','category','local_key','ip','status')}
                                session['bulb']['functions']={k:{'type':getattr(v,'type',None),'values':getattr(v,'values',None)} for k,v in target.function.items()}
                                save_session(session)
                                self.events.put(('status','Autorização concluída. A lâmpada foi localizada na sua conta; nenhuma cor foi alterada. Volte ao chat para continuar.'))
                            else:
                                self.events.put(('status','Conta autorizada, mas o ID informado não apareceu. O ID pode ter mudado ao cadastrar no Tuya.'))
                    except Exception:
                        self.events.put(('status','Autorização salva. A leitura da lâmpada ainda precisa ser concluída; volte ao chat.'))
                    finally:
                        manager.customer_api.session.close()
                    return
                if not self.cancel.is_set():
                    self.events.put(('status','QR expirou. Clique em Gerar QR code para tentar novamente.'))
            except Exception:
                self.events.put(('status','Não foi possível concluir a comunicação com a Tuya. Tente gerar outro QR code.'))
            finally:
                if login:
                    login.session.close()
                self.events.put(('done',None))
        self.thread=threading.Thread(target=run,daemon=True)
        self.thread.start()

    def drain(self):
        while True:
            try:
                kind,value=self.events.get_nowait()
            except queue.Empty:
                break
            if kind=='status':
                self.status.set(value)
            elif kind=='qr':
                self.photo=ImageTk.PhotoImage(value.resize((300,300)))
                self.qr_label.configure(image=self.photo,height=300)
            elif kind=='done':
                self.button.configure(state='normal')
                self.entry.configure(state='normal')
                self.target_entry.configure(state='normal')
        self.timer=self.root.after(100,self.drain)

    def close(self):
        self.cancel.set()
        if self.timer:
            self.root.after_cancel(self.timer)
        self.root.destroy()


def main():
    logging.getLogger('tuya_sharing').setLevel(logging.CRITICAL)
    parser=argparse.ArgumentParser()
    parser.add_argument('--user-code',default='')
    parser.add_argument('--device-id',default='')
    parser.add_argument('--generate',action='store_true')
    args=parser.parse_args()
    root=tk.Tk()
    app=LinkWindow(root,args.user_code,args.device_id)
    if args.generate:
        root.after(300,app.start)
    root.mainloop()


if __name__=='__main__':
    main()

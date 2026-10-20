"""Construção das abas visuais da interface: Cinema, Presets e Conectar."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

from color_wheel import ColorWheel
from presets_data import DEFAULT_PRESETS
from win_platform import APP_DIR
from ui_theme import THEMES

HELP = """PRIMEIRO TESTE
1. Em Cinema, escolha o monitor e clique em Prévia da tela.
2. Minimize esta janela e coloque o filme em tela cheia no Stremio.
3. A prévia funciona mesmo antes de conectar a lâmpada.

CONTA TUYA (CONEXÃO PELA INTERNET)
Se a conta já foi autorizada, escolha Conta Tuya na aba Cinema
e clique Sincronizar lâmpada. Não é necessário preencher o IP
ou a chave local para este modo. Em Conta Tuya, Testar acesso
confere a leitura sem mudar as cores. Para vincular outra vez,
use Vincular por QR code e confirme no celular.
O intervalo mínimo pela conta é de 0,25 segundo. As imagens ficam
no computador; somente comandos de luz são enviados à Tuya.
Essa conexão usa o fluxo público Tuya / Home Assistant e pode
aparecer com esse nome na autorização. A sessão fica protegida
pelo Windows em dados/tuya.enc. O programa consulta e comanda
somente o ID da lâmpada informado, embora a autorização da
plataforma possa abranger outros dispositivos da conta.

CONECTAR A LÂMPADA
O modo Rede local implementa controle local Tuya RGB. Usar o Elgin Smart
não garante que todo modelo permita esse acesso. A conexão só será
confirmada depois de um teste com sua lâmpada.

PC e lâmpada devem estar na mesma rede. Em Lâmpada, use Buscar
na rede para localizar IP, ID e protocolo de dispositivos compatíveis.
A busca não fornece a chave local e não identifica sozinha qual é
a lâmpada do quarto: selecione o dispositivo correto.

CHAVE LOCAL
É a chave de controle do dispositivo, não a senha do Wi-Fi nem a
senha do Elgin Smart. Não é necessário colar senhas neste programa.
Se você já tem um devices.json gerado pelo TinyTuya, importe-o.
Caso não tenha, consulte o guia oficial no botão abaixo. Ele descreve
obter a chave pela plataforma Tuya usando uma conta compatível.
A vinculação direta do Elgin Smart pode variar; não resete nem
remova a lâmpada do aplicativo para experimentar sem orientação.

Após preencher IP, ID, chave e protocolo, clique Testar conexão.
Esse teste apenas lê o estado e verifica suporte a cor.
Depois volte a Cinema e clique Sincronizar lâmpada.

DURANTE O FILME
Comece com suavidade de 0,1 segundo e atualização a cada 0,25 segundo.
Vibração das cores (140% inicialmente) intensifica a saturação para
lâmpadas RGB, garantindo cores vivas estilo AuraSync.
Foco no destaque da tela (100% inicialmente) prioriza a cor marcante
da cena (néon, explosões, sabres de luz, elementos vívidos) em vez
de diluí-la no fundo neutro ou escuro. Em 0%, calcula a média tradicional.
Modo claro ativa os LEDs brancos de alta potência para telas de navegação,
documentos e páginas brancas ou quentes (meio laranja), garantindo
iluminação real do quarto em vez de um cinza fraco.
Ajuste Apagar cenas abaixo de (5% inicialmente) para eliminar a
luz residual de cenas quase pretas. O preto apaga imediatamente;
uma pequena margem de retorno evita piscar no limiar.
A suavidade evita mudanças bruscas. A faixa superior e inferior da
imagem é recortada para reduzir barras pretas e legendas.
Minimize o programa para que ele não influencie as cores capturadas.

PARAR
Parar ou fechar interrompe a captura e tenta restaurar o estado lido
antes de iniciar. Se a conexão cair, a restauração pode falhar;
nesse caso ajuste a lâmpada pelo Elgin Smart. Em uma queda de
energia ou encerramento forçado do programa não há restauração.

LIMITES
Uma lâmpada Wi-Fi pode responder mais devagar que fitas dedicadas.
Vídeos com proteção de captura podem aparecer pretos, e HDR pode
alterar as cores capturadas. O programa não contorna essas proteções.
Se a rede oscilar, aumente o intervalo para 1 segundo.

PRIVACIDADE
As imagens são analisadas na memória e não são gravadas nem
enviadas à internet. Somente comandos de cor vão ao IP configurado.
A busca escuta anúncios locais de dispositivos Tuya.
A chave só é salva se você marcar Lembrar chave neste Windows;
nesse caso usa a proteção DPAPI do Windows. Não compartilhe
devices.json ou a pasta dados. Programa independente, sem vínculo
oficial com a Elgin, a Tuya ou o Stremio.
"""


class TabViewsMixin:
    """Mixin responsável por instanciar os elementos e layouts das abas."""

    def locked(self, widget, normal="normal"):
        self.lockables.append((widget, normal))
        return widget

    def slider(self, page, label, variable, low, high, unit):
        row = ttk.Frame(page)
        row.pack(fill="x", pady=5)
        row.columnconfigure(1, weight=1)
        ttk.Label(row, text=label, width=28).grid(row=0, column=0, sticky="w")
        value_label = ttk.Label(row, width=8)
        value_label.grid(row=0, column=2, padx=(8, 0))

        def display(*_):
            n = variable.get()
            value_label.configure(text=(f"{n:.1f}" if unit == " s" else f"{n:.0f}") + unit)

        display()
        variable.trace_add("write", display)
        self.locked(ttk.Scale(row, from_=low, to=high, variable=variable)).grid(row=0, column=1, sticky="ew")

    def build_cinema(self, page):
        t = self.current_theme
        connection_row = ttk.Frame(page)
        connection_row.pack(fill="x", pady=(0, 12))
        ttk.Label(connection_row, text="Conexão da lâmpada").pack(side="left", padx=(0, 14))
        self.locked(ttk.Combobox(connection_row, textvariable=self.connection_mode, values=("Conta Tuya", "Rede local"), state="readonly", width=18), "readonly").pack(side="left")

        ttk.Label(page, text="Tela do filme").pack(anchor="w")
        self.monitor_box = self.locked(ttk.Combobox(page, textvariable=self.monitor, state="readonly"), "readonly")
        self.monitor_box.pack(fill="x", pady=(5, 18))
        self.monitors = []
        try:
            from mss import MSS
            with MSS() as capture:
                self.monitors = [dict(m) for m in capture.monitors[1:]]
            choices = [f"Monitor {i+1} · {m['width']} × {m['height']}" for i, m in enumerate(self.monitors)]
            self.monitor_box["values"] = choices
            if choices:
                self.monitor_box.current(min(self.saved_monitor, len(choices) - 1))
        except Exception:
            self.status.set("Não foi possível listar as telas. Verifique a sessão do Windows.")

        self.swatch = tk.Canvas(page, height=95, bg=t["PANEL"], highlightthickness=1, highlightbackground=t["BORDER"])
        self.swatch.pack(fill="x")
        self.swatch_label = self.swatch.create_text(20, 48, anchor="w", text="Sua prévia de cor aparece aqui", fill=t["FG"], font=("Segoe UI", 15))
        ttk.Label(page, text="Prévia local · minimize esta janela durante o filme", style="Muted.TLabel").pack(anchor="w", pady=(6, 15))

        self.slider(page, "Brilho máximo", self.brightness, 5, 100, "%")
        self.slider(page, "Vibração das cores", self.saturation, 50, 250, "%")
        self.slider(page, "Foco no destaque da tela", self.standout, 0, 100, "%")
        self.slider(page, "Suavidade da transição", self.smoothing, 0.1, 3, " s")
        self.slider(page, "Recorte em cima e embaixo", self.crop, 0, 30, "%")
        self.slider(page, "Apagar cenas abaixo de", self.dark_percent, 0, 15, "%")

        checks_row = ttk.Frame(page)
        checks_row.pack(fill="x", pady=(4, 10))
        self.locked(ttk.Checkbutton(checks_row, text="Apagar lâmpada em cenas cinzas / preto e branco", variable=self.off_on_neutral)).pack(anchor="w")
        self.locked(ttk.Checkbutton(checks_row, text="Clarão dinâmico em cenas muito claras (efeito Flashbang)", variable=self.flash_boost)).pack(anchor="w", pady=(3, 0))
        self.locked(ttk.Checkbutton(checks_row, text="Modo claro (iluminar páginas e telas brancas/quentes)", variable=self.light_mode)).pack(anchor="w", pady=(3, 0))

        row = ttk.Frame(page)
        row.pack(fill="x", pady=(5, 16))
        ttk.Label(row, text="Atualizar a cada").pack(side="left")
        self.locked(ttk.Combobox(row, textvariable=self.interval, values=("0.25", "0.5", "1.0", "2.0"), width=8, state="readonly"), "readonly").pack(side="left", padx=8)
        ttk.Label(row, text="segundo(s)", style="Muted.TLabel").pack(side="left")

        buttons = ttk.Frame(page)
        buttons.pack(fill="x")
        self.preview_button = self.locked(ttk.Button(buttons, text="Prévia da tela", command=lambda: self.start(False)))
        self.preview_button.pack(side="left")
        self.start_button = self.locked(ttk.Button(buttons, text="Sincronizar lâmpada", style="Accent.TButton", command=lambda: self.start(True)))
        self.start_button.pack(side="left", padx=10)
        self.stop_button = ttk.Button(buttons, text="Parar", state="disabled", command=self.stop)
        self.stop_button.pack(side="left")
        self.cinema_off_btn = ttk.Button(buttons, text="⏻ Apagar Lâmpada", style="Danger.TButton", command=self.turn_off_light)
        self.cinema_off_btn.pack(side="left", padx=10)

        bottom_buttons = ttk.Frame(page)
        bottom_buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(bottom_buttons, text="Minimizar para assistir", command=self.root.iconify).pack(side="left")
        self.locked(ttk.Button(bottom_buttons, text="Salvar ajustes", command=self.save_settings)).pack(side="left", padx=10)

    def build_connection(self, page):
        ttk.Label(page, text="Conexão da Lâmpada", font=("Segoe UI Semibold", 16)).pack(anchor="w")
        ttk.Label(page, text="Escolha entre a conexão pela internet (Conta Tuya) ou conexão direta na rede local.", style="Muted.TLabel").pack(anchor="w", pady=(2, 12))

        mode_frame = ttk.Frame(page)
        mode_frame.pack(fill="x", pady=(0, 14))
        ttk.Radiobutton(mode_frame, text="Conta Tuya (Internet / QR Code) — Recomendado", variable=self.connection_mode, value="Conta Tuya", command=self.update_connection_view).pack(side="left", padx=(0, 18))
        ttk.Radiobutton(mode_frame, text="Rede Local (IP e Chave)", variable=self.connection_mode, value="Rede local", command=self.update_connection_view).pack(side="left")

        # Container para Nuvem Tuya
        self.cloud_container = ttk.Frame(page)
        self.cloud_state = tk.StringVar(value="Autorização salva neste Windows." if (APP_DIR / "dados" / "tuya.enc").exists() else "Conta ainda não vinculada.")
        ttk.Label(self.cloud_container, textvariable=self.cloud_state, wraplength=690, style="Muted.TLabel").pack(anchor="w", pady=(4, 12))
        ttk.Label(self.cloud_container, text="1. Vincule a conta pelo QR code e confirme no celular no Tuya Smart / Elgin Smart.\n2. Clique em Testar acesso para verificar a lâmpada.\n3. Em Cinema, sincronize e aproveite!", wraplength=680).pack(anchor="w", pady=8)
        row = ttk.Frame(self.cloud_container)
        row.pack(fill="x", pady=10)
        self.locked(ttk.Button(row, text="Vincular por QR code", command=self.open_tuya_link)).pack(side="left")
        self.locked(ttk.Button(row, text="Testar acesso", command=self.test_cloud)).pack(side="left", padx=10)
        ttk.Label(self.cloud_container, text="A conta usa o fluxo público Tuya / Home Assistant. A sessão fica protegida por DPAPI no Windows.\nO aplicativo consulta e comanda somente a lâmpada especificada. Nenhuma imagem da tela sai do computador.", wraplength=680, style="Muted.TLabel").pack(anchor="w", pady=12)

        # Container para Rede Local
        self.local_container = ttk.Frame(page)
        ttk.Label(self.local_container, text="Compatibilidade será confirmada no teste com a lâmpada.", style="Muted.TLabel").pack(anchor="w", pady=(0, 10))
        form = ttk.Frame(self.local_container)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        for i, (label, var) in enumerate((("IP da lâmpada", self.ip), ("ID do dispositivo", self.device_id), ("Chave local", self.key))):
            ttk.Label(form, text=label, width=20).grid(row=i, column=0, sticky="w", pady=5)
            entry = self.locked(ttk.Entry(form, textvariable=var, show="•" if var is self.key else ""))
            entry.grid(row=i, column=1, sticky="ew", pady=5)
        ttk.Label(form, text="Protocolo").grid(row=3, column=0, sticky="w", pady=5)
        self.locked(ttk.Combobox(form, textvariable=self.version, values=("3.1", "3.2", "3.3", "3.4", "3.5"), state="readonly", width=10), "readonly").grid(row=3, column=1, sticky="w", pady=5)
        self.locked(ttk.Checkbutton(self.local_container, text="Lembrar chave neste Windows (proteção do Windows)", variable=self.remember)).pack(anchor="w", pady=8)
        row_local = ttk.Frame(self.local_container)
        row_local.pack(fill="x", pady=7)
        self.locked(ttk.Button(row_local, text="Buscar na rede", command=self.scan)).pack(side="left")
        self.locked(ttk.Button(row_local, text="Importar devices.json", command=self.import_devices)).pack(side="left", padx=8)
        self.locked(ttk.Button(row_local, text="Testar conexão", command=self.test_connection)).pack(side="left")

        t = self.current_theme
        self.device_list = self.locked(tk.Listbox(self.local_container, height=4, bg=t["ENTRY_BG"], fg=t["FG"], selectbackground=t["ACCENT"], selectforeground="#ffffff", borderwidth=0, highlightthickness=1, highlightbackground=t["BORDER"]))
        self.device_list.pack(fill="x", pady=8)
        self.device_list.bind("<<ListboxSelect>>", self.select_device)
        self.locked(ttk.Button(self.local_container, text="Salvar preferências", command=self.save_settings)).pack(anchor="w", pady=8)

        self.update_connection_view()
        self.connection_mode.trace_add("write", lambda *_: self.update_connection_view())

    def update_connection_view(self):
        if not hasattr(self, "cloud_container") or not hasattr(self, "local_container"):
            return
        if self.connection_mode.get() == "Conta Tuya":
            self.local_container.pack_forget()
            self.cloud_container.pack(fill="both", expand=True)
        else:
            self.cloud_container.pack_forget()
            self.local_container.pack(fill="both", expand=True)

    def open_tuya_link(self):
        from vincular_tuya import LinkWindow
        code, target = "", ""
        try:
            from tuya_cloud import load_session
            from core import BulbError
            session = load_session()
            code, target = session["user_code"], session.get("device_id", "")
        except Exception:
            target = self.device_id.get()
        popup = tk.Toplevel(self.root)
        LinkWindow(popup, code, target)

    def test_cloud(self):
        self.status.set("Consultando a lâmpada autorizada na Tuya…")

        def test():
            from tuya_cloud import CloudBulb
            bulb = CloudBulb()
            name = bulb.device.name
            bulb.close()
            self.events.put(("status", f"Acesso confirmado: {name}. Nenhuma cor foi alterada neste teste."))
            self.events.put(("cloud_status", "Conta autorizada e lâmpada online. Pronta para sincronizar."))

        self.launch(test)

    def build_presets(self, page):
        t = self.current_theme
        ttk.Label(page, text="Controle Manual e Presets", font=("Segoe UI Semibold", 16)).pack(anchor="w")
        ttk.Label(page, text="Escolha a cor ou branco desejado pelo PC sem precisar do celular.", style="Muted.TLabel").pack(anchor="w", pady=(2, 10))

        content = ttk.Frame(page)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)

        # Coluna da Esquerda: Roda de Cores e Sliders
        left_col = ttk.Frame(content)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 15))

        # Seletor de Modo
        mode_frame = ttk.Frame(left_col)
        mode_frame.pack(fill="x", pady=(0, 8))
        ttk.Radiobutton(mode_frame, text="Cor RGB", variable=self.manual_mode, value="colour", command=self.update_manual_preview).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(mode_frame, text="Branco CCT", variable=self.manual_mode, value="white", command=self.update_manual_preview).pack(side="left")

        # Roda de Cores
        wheel_container = ttk.Frame(left_col)
        wheel_container.pack(pady=4)
        self.wheel_canvas = tk.Canvas(wheel_container, width=180, height=180, bg=t["BG"], highlightthickness=0)
        self.wheel_canvas.pack()
        self.color_wheel = ColorWheel(self.wheel_canvas, 180, self.on_wheel_pick)

        # Sliders
        self.slider(left_col, "Brilho", self.manual_brightness, 1, 100, "%")
        self.slider(left_col, "Temperatura Branca", self.manual_temp, 0, 100, "%")
        self.manual_brightness.trace_add("write", lambda *_: self.on_manual_control_change())
        self.manual_temp.trace_add("write", lambda *_: self.on_manual_control_change())

        # Amostra de Cor Atual
        preview_row = ttk.Frame(left_col)
        preview_row.pack(fill="x", pady=6)
        self.manual_swatch = tk.Canvas(preview_row, width=38, height=38, bg="#ff0000", highlightthickness=1, highlightbackground=t["BORDER"])
        self.manual_swatch.pack(side="left", padx=(0, 10))
        self.manual_swatch_label = ttk.Label(preview_row, text="#FF0000 (100%)", font=("Segoe UI Semibold", 10))
        self.manual_swatch_label.pack(side="left")

        # Botões de Ação
        btn_row = ttk.Frame(left_col)
        btn_row.pack(fill="x", pady=6)
        self.apply_btn = ttk.Button(btn_row, text="Aplicar à Lâmpada", style="Accent.TButton", command=self.apply_current_manual)
        self.apply_btn.pack(side="left", padx=(0, 8))
        self.off_btn = ttk.Button(btn_row, text="⏻ Apagar Lâmpada", style="Danger.TButton", command=self.turn_off_light)
        self.off_btn.pack(side="left", padx=(0, 8))
        ttk.Checkbutton(left_col, text="Aplicar em tempo real enquanto ajusta", variable=self.live_manual).pack(anchor="w", pady=(2, 0))

        # Coluna da Direita: Presets Rápidos e Personalizados
        right_col = ttk.Frame(content)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(15, 0))

        ttk.Label(right_col, text="Presets Rápidos", font=("Segoe UI Semibold", 12)).pack(anchor="w", pady=(0, 6))
        presets_grid = ttk.Frame(right_col)
        presets_grid.pack(fill="x", pady=(0, 10))
        self.default_preset_swatches = []
        for i, preset in enumerate(DEFAULT_PRESETS):
            card = ttk.Frame(presets_grid)
            card.grid(row=i // 2, column=i % 2, sticky="ew", padx=3, pady=3)
            swatch = tk.Canvas(card, width=16, height=16, bg=preset["color_hex"], highlightthickness=1, highlightbackground=t["BORDER"])
            swatch.pack(side="left", padx=(2, 6))
            swatch.bind("<Button-1>", lambda _, p=preset: self.activate_preset(p))
            self.default_preset_swatches.append(swatch)
            btn = ttk.Button(card, text=preset["name"], style="Preset.TButton", command=lambda p=preset: self.activate_preset(p))
            btn.pack(side="left", fill="x", expand=True)
        presets_grid.columnconfigure(0, weight=1)
        presets_grid.columnconfigure(1, weight=1)

        # Seção de Presets Personalizados
        ttk.Separator(right_col, orient="horizontal").pack(fill="x", pady=8)
        ttk.Label(right_col, text="Salvar Preset Personalizado", font=("Segoe UI Semibold", 12)).pack(anchor="w", pady=(0, 6))
        save_row = ttk.Frame(right_col)
        save_row.pack(fill="x", pady=(0, 6))
        self.new_preset_entry = ttk.Entry(save_row)
        self.new_preset_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(save_row, text="Salvar", command=self.save_custom_preset).pack(side="left")

        self.custom_presets_frame = ttk.Frame(right_col)
        self.custom_presets_frame.pack(fill="both", expand=True)
        self.refresh_custom_presets_ui()

        # Seção de Sistema e Inicialização
        tray_box = ttk.LabelFrame(page, text=" Opções do Sistema ", padding=10)
        tray_box.pack(fill="x", pady=(10, 0))
        ttk.Checkbutton(tray_box, text="Minimizar para a bandeja do sistema (System Tray) ao fechar a janela", variable=self.minimize_to_tray).pack(anchor="w", pady=2)
        ttk.Checkbutton(tray_box, text="Iniciar automaticamente com o Windows (inicia minimizado na bandeja)", variable=self.start_with_windows, command=self.toggle_autostart).pack(anchor="w", pady=2)

        self.update_manual_preview()

    def open_help_popup(self):
        t = getattr(self, "current_theme", THEMES["dark"])
        popup = tk.Toplevel(self.root)
        popup.title("Como conectar — Guia")
        popup.geometry("720x680")
        popup.minsize(580, 480)
        popup.configure(bg=t["BG"])
        header = ttk.Frame(popup, padding=(20, 16, 20, 10))
        header.pack(fill="x")
        ttk.Label(header, text="Guia de Conexão", font=("Segoe UI Semibold", 16)).pack(side="left")
        ttk.Button(header, text="Guia oficial de conexão local", command=lambda: webbrowser.open("https://github.com/jasonacox/tinytuya#setup-wizard---getting-local-keys")).pack(side="right")
        body = ttk.Frame(popup, padding=(20, 0, 20, 16))
        body.pack(fill="both", expand=True)
        text = tk.Text(body, bg=t["PANEL"], fg=t["FG"], font=("Segoe UI", 10), wrap="word", padx=15, pady=12, borderwidth=0, selectbackground=t["ACCENT"], selectforeground="#ffffff")
        scroll = ttk.Scrollbar(body, command=text.yview)
        scroll.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        text.configure(yscrollcommand=scroll.set)
        text.insert("1.0", HELP)
        text.configure(state="disabled")
        btn_frame = ttk.Frame(popup, padding=(20, 0, 20, 16))
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="Fechar", command=popup.destroy).pack(side="right")

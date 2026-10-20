# 🎬 Luz Cinema (v1.0.0)

<p align="center">
  <b>Sistema de Ambilight Dinâmico em Tempo Real para Lâmpadas Inteligentes no Windows</b><br>
  <i>Sincronize as cores do seu monitor com sua lâmpada Tuya / Smart Life com baixa latência e alta fidelidade visual.</i>
</p>

---

## 🌟 Recursos Principais

- ⚡ **Ambilight Dinâmico de Alta Performance:** Captura a tela e reflete a iluminação das cenas em tempo real no seu quarto com suavização visual ultra-fluida.
- 🎯 **Filtro de Destaque Espectral (AuraSync-style):** Destaca cores salientes (explosões, sabres de luz, feixes de néon) mesmo quando ocupam pequenos detalhes da tela, sem virar média acinzentada.
- 💥 **Detecção de Clarão (Flashbang Burst):** Transição instantânea para os LEDs brancos dedicados (1000 lúmens) em explosões de luz branca.
- 🌙 **Desligamento Inteligente em Telas Escuras/Pretas:** Economiza energia e preserva a imersão total apagando a luz em cenas de cinema escuras ou créditos.
- 🎨 **Roda de Cores HSV e Modo Manual:** Ajuste de matiz, saturação, brilho e temperatura de cor (Branco Quente 2700K a Branco Frio 6500K) direto pelo PC.
- 📌 **Bandeja do Sistema (System Tray):** Fica discretamente ao lado do relógio do Windows, permitindo sincronizar, trocar cores ou apagar a lâmpada pelo menu de contexto.
- 🚀 **Início com o Windows:** Inicialização automática silenciosa em segundo plano no login do sistema.
- 🌓 **Temas Modernos:** Interface gráfica com suporte completo a Modo Escuro e Modo Claro.

---

## 🚀 Como Usar

### Executável Pronto (Recomendado)
1. Baixe o executável `LuzCinema.exe` na aba [Releases](https://github.com/ianfefe/luz-cinema/releases).
2. Execute o aplicativo.
3. Na aba **Conectar**, vincule sua lâmpada via QR code (Tuya Smart / Smart Life / Elgin) ou configure via Rede Local (IP e Chave).
4. Na aba **Cinema**, selecione o monitor desejado e clique em **Sincronizar lâmpada**.
5. Abra seu filme, jogo ou série em tela cheia!

---

## 🛠️ Executando a partir do Código-Fonte

### Pré-requisitos
- Python 3.10+ no Windows
- Dependências listadas em `requirements.txt`

### Instalação
```bash
git clone https://github.com/ianfefe/luz-cinema.git
cd luz-cinema
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Iniciar o aplicativo
```bash
python luz_cinema.py
```

### Compilar para Executável (.exe)
```bash
pip install pyinstaller
pyinstaller -y LuzCinema.spec
```

---

## 📄 Licença e Componentes de Terceiros
Este projeto é distribuído sob os termos e licenças das bibliotecas de terceiros contidas na pasta `licencas/`.

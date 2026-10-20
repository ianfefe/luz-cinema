# 🎬 Luz Cinema v2

<p align="center">
  <img src="luzcinema.ico" width="80" height="80" alt="Luz Cinema Logo"><br>
  <b>Ambilight Espacial Multi-Lâmpadas & Sistema de Cenários para Windows</b><br>
  <i>Transforme seu quarto em uma verdadeira sala de cinema com iluminação dinâmica sincronizada à tela em tempo real.</i>
</p>

<p align="center">
  <a href="https://github.com/ianfefe/luz-cinema/releases"><img src="https://img.shields.io/github/v/release/ianfefe/luz-cinema?color=8b7bff&label=Vers%C3%A3o" alt="GitHub Release"></a>
  <img src="https://img.shields.io/badge/Plataforma-Windows%2010%20%7C%2011-blue" alt="Windows 10/11">
  <img src="https://img.shields.io/badge/Python-3.10%2B-green" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Licen%C3%A7a-Open%20Source-purple" alt="Open Source">
</p>

---

## 🌟 O Que Há de Novo no Luz Cinema v2?

O **Luz Cinema v2** evolui o projeto de um sincronizador de lâmpada única para uma central completa de **Ambilight Multi-Canal com Zonas Espaciais e Cenários Temáticos**:

### 1. 🌌 Ambilight Espacial por Zonas da Tela
Distribua suas lâmpadas pelo cômodo e mapeie cada uma para acompanhar uma região específica do monitor:
- **Lado Esquerdo:** A lâmpada à sua esquerda reage somente ao lado esquerdo da tela (ex: sabre de luz verde, explosões ou feixes desse lado).
- **Lado Direito:** A lâmpada à sua direita acompanha as cores da margem direita (ex: sabre de luz vermelho ou fogo).
- **Topo / Teto:** Ilumina o quarto com o céu ou teto da cena.
- **Tela Inteira:** Realiza a média cinematográfica harmônica do quadro.

```
       ┌──────────────────────────────┐
       │         ZONA DO TOPO         │
       ├──────────┬────────┬──────────┤
       │          │        │          │
       │ ESQUERDA │ CENTRO │ DIREITA  │
       │          │        │          │
       └──────────┴────────┴──────────┘
```

### 2. ✨ Sistema de Cenários de Iluminação (1 Clique)
Alterne instantaneamente a atmosfera de todo o seu quarto com cenários pré-configurados:
- 🎬 **Setup Cinema:** tons profundos de azul e roxo que não cansam a visão.
- 👾 **Cyberpunk Neon:** Ciano Neon à esquerda e Magenta Vibrante à direita.
- 🌆 **Pôr do Sol Dourado:** tons aconchegantes de laranja, âmbar e dourado.
- 📖 **Leitura Relaxante:** luz quente aveludada (2700K) no brilho ideal para descanso.
- 💻 **Trabalho Focado:** branco frio nítido (6500K) para concentração e produtividade.
- 🌙 **Luz Noturna:** iluminação âmbar ultraleve (10% de brilho) para antes de dormir.
- 🌲 **Floresta Esmeralda:** tons de verde esmeralda e menta refrescante.
- ➕ **Crie seus Próprios Cenários:** regule suas lâmpadas, salve com um clique e acesse quando quiser.

### 3. 🚀 Despacho Paralelo Assíncrono
Envio de comandos simultâneo em canais independentes (`ThreadPoolExecutor`). Se uma lâmpada for desligada da tomada, as demais continuam sincronizando perfeitamente sem congelar o aplicativo.

### 4. 🎨 Controle Individual ou Coletivo
Na aba *Presets & Cores*, escolha controlar **Todas as Lâmpadas** juntas ou regular uma lâmpada específica (ex: apenas a luminária de mesa ou a fita LED da TV).

### 5. 📌 Menu Completo na Bandeja do Windows (System Tray)
Clique com o botão direito no ícone ao lado do relógio do Windows para:
- Ativar qualquer **Cenário** com 1 clique.
- Ligar ou apagar lâmpadas individuais ou todas juntas.
- Iniciar a sincronização de cinema no monitor selecionado.
- Escolher presets de fábrica e favoritos.

---

## 📊 Comparativo: v1.0.0 vs v2.0.0

| Recurso | Luz Cinema v1.0.0 | Luz Cinema v2.0.0 |
| :--- | :---: | :---: |
| **Capacidade de Lâmpadas** | 1 lâmpada | **Múltiplas lâmpadas simultâneas** |
| **Ambilight Espacial** | Tela inteira | **Zonas (Esquerda, Direita, Topo, Inteira)** |
| **Comunicação Concorrente** | Serial | **Assíncrona em Paralelo (Thread Pool)** |
| **Sistema de Cenários** | Não | **7 cenários inclusos + Cenários Customizados** |
| **Seleção de Alvo Manual** | Lâmpada única | **Individual ou Coletivo (Todas)** |
| **Bandeja do Sistema** | Monitores & Presets | **Monitores, Cenários, Lâmpadas & Presets** |
| **Detecção de Clarão (Flashbang)** | ✅ | ✅ |
| **Filtro de Destaque Espectral** | ✅ | ✅ |
| **Desligamento em Telas Pretas** | ✅ | ✅ |
| **Início com o Windows** | ✅ | ✅ |
| **Temas Escuro e Claro** | ✅ | ✅ |

---

## 🚀 Como Usar

### Opção 1: Executável Portátil Pronto (Recomendado)
1. Acesse a aba de [Releases](https://github.com/ianfefe/luz-cinema/releases) e baixe o `LuzCinema-v2.0.0.exe` ou o arquivo compacto `LuzCinema-v2.0.0-Portable.zip`.
2. Extraia (caso tenha baixado o zip) e abra o **`LuzCinema.exe`**.
3. Na aba **Conectar**, vincule suas lâmpadas via QR code da Tuya (Tuya Smart, Smart Life ou Elgin) ou por Rede Local.
4. Na aba **Cenários & Lâmpadas**, defina a zona da tela para cada lâmpada.
5. Na aba **Cinema Multi-Lâmpadas**, clique em **Sincronizar Todas as Lâmpadas** e aproveite!

### Opção 2: A Partir do Código-Fonte (Desenvolvedores)

```bash
# 1. Clone o repositório
git clone https://github.com/ianfefe/luz-cinema.git
cd luz-cinema

# 2. Crie e ative o ambiente virtual
python -m venv venv
.\venv\Scripts\activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Inicie o Luz Cinema v2
python luz_cinema.py
```

### Compilar seu Próprio Executável (.exe)
```bash
pip install pyinstaller
.\compilar.bat
```

---

## 🔒 Segurança e Privacidade

- **Criptografia Local Segura (DPAPI):** Todas as credenciais locais ou tokens são protegidos usando criptografia da API de Proteção de Dados do Windows (`CryptProtectData`), vinculada exclusivamente à sua conta do usuário no Windows.
- **Zero Vazamento de Dados:** Nenhuma informação pessoal, credencial, chave ou histórico é enviado para servidores externos além dos endpoints oficiais da Tuya Cloud requisitados pelo protocolo padrão.
- **Código 100% Aberto e Auditável:** Todos os scripts de captura de tela, cálculo espectral e despacho de cores estão disponíveis neste repositório.

---

## 🧪 Testes Automatizados

O projeto conta com suíte completa de testes unitários para o pipeline de Ambilight, algoritmos de cor e despacho multi-lâmpadas:

```bash
python -m unittest tests/test_luz_cinema.py tests/test_luz_cinema_v2.py
```

---

## 📄 Licenças
Consulte a pasta `licencas/` para as licenças das bibliotecas de código aberto utilizadas.

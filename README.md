# 🎬 Luz Cinema

<p align="center">
  <img src="luzcinema/assets/luzcinema.ico" width="80" height="80" alt="Luz Cinema"><br>
  <b>Suas lâmpadas inteligentes acompanhando as cores da tela do PC, em tempo real.</b><br>
  <i>Filmes, jogos e vídeos com iluminação ambiente — sem hardware extra.</i>
</p>

<p align="center">
  <a href="https://github.com/ianfefe/luz-cinema/releases"><img src="https://img.shields.io/github/v/release/ianfefe/luz-cinema?color=8b5cf6&label=Vers%C3%A3o" alt="Versão"></a>
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-blue" alt="Windows 10/11">
  <img src="https://img.shields.io/badge/Python-3.10%2B-green" alt="Python 3.10+">
</p>

---

## Uma lâmpada ou várias

É um app só, que se adapta ao que você tem:

- **Uma lâmpada**: interface enxuta — a lâmpada acompanha a tela inteira.
- **Duas ou mais**: aparecem as **zonas da tela** (esquerda, direita, topo, base, centro ou inteira),
  a cor de cada lâmpada na prévia, o seletor “Aplicar em” nas cores e um submenu por lâmpada na bandeja.
  Os cenários dão uma cor diferente para cada zona.

## Recursos

- **Modo cinema** com prévia ao vivo do brilho em volta do monitor, botão único de iniciar/parar (ou **F5**)
  e restauração automática da lâmpada ao estado anterior quando você para.
- **Perfis prontos** (Ação, Escuro/Noir, Jogo FPS, Jogo RPG, Web, YouTube) e ajustes finos salvos automaticamente.
- **Clarão** (flashes brancos a 100%), **apagar em cenas escuras/cinzas** e **modo claro** para navegar.
- **Cores**: roda de cores, branco quente→frio, presets e cores salvas.
- **Cenários** prontos com um clique e cenários personalizados.
- **Bandeja do Windows**: cinema, perfis, cenários, cores, acender/apagar e sair, sem abrir a janela.
- **Conexão** pela conta Tuya (QR code — Tuya Smart, Smart Life, Elgin Smart…) ou direto pela rede local (IP + chave).
- Tema **escuro e claro**, interface rolável que cabe em telas de notebook.

## Como usar

### Executável pronto
1. Baixe em [Releases](https://github.com/ianfefe/luz-cinema/releases) e abra `LuzCinema.exe`.
2. Na página **Lâmpadas**, vincule a conta Tuya por QR code e escolha a lâmpada — ou adicione pela rede local.
3. Na página **Cinema**, clique em **Iniciar sincronização** e dê play no filme. Pode minimizar.

### A partir do código-fonte

```bash
git clone https://github.com/ianfefe/luz-cinema.git
cd luz-cinema
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python luz_cinema.py
```

### Gerar o executável

```bash
pip install pyinstaller
.\ferramentas\compilar.bat
```

O arquivo sai em `dist\LuzCinema.exe`. Coloque o `.exe` na mesma pasta onde ficava a versão anterior para que as
preferências (`dados\`) sejam importadas automaticamente.

## Vindo de uma versão anterior?

Na primeira execução, o app importa as preferências antigas da pasta `dados/` — das edições Simples/Multi
de testes da 3.0 (`preferencias_simples.json`, depois `preferencias_multi.json`), da v2 (`preferencias_v2.json`) ou da v1:
lâmpadas, ajustes, cores e cenários. Tudo passa a ficar em `dados/preferencias_v3.json`. Se a v2 ou a edição
Multi iniciava com o Windows, esse início passa para o `LuzCinema.exe`. A chave local, que a v2 gravava em texto
puro, passa a ser salva criptografada — depois de confirmar que tudo funciona, você pode apagar os arquivos antigos.

## Estrutura do repositório

```
luz-cinema/
├── luz_cinema.py           ▶ abre o app
├── requirements.txt
├── luzcinema/              código do app
│   ├── core.py             análise de cor da tela, suavização e controle local (tinytuya)
│   ├── devices.py          cadastro de lâmpadas e envio paralelo com reconexão
│   ├── tuya_cloud.py       controle pela nuvem Tuya
│   ├── tuya_link.py        vinculação da conta por QR code
│   ├── storage.py          preferências (migração e chaves protegidas por DPAPI)
│   ├── windows.py          início com o Windows, instância única, DPAPI
│   ├── assets/             ícone do app
│   └── ui/                 janela, tema, componentes, bandeja, diálogos e páginas
├── tests/                  testes automatizados
└── ferramentas/            compilação e manutenção
    ├── compilar.bat / compilar.ps1 / LuzCinema.spec
    ├── gerar_icone.py      recria o ícone
    ├── coletar_licencas.py atualiza a pasta licencas/
    └── licencas/           licenças das bibliotecas incluídas no .exe
```

Pastas geradas localmente e ignoradas pelo Git: `venv/`, `build/`, `dist/` e `dados/`.

## Segurança e privacidade

- Chaves locais e tokens da Tuya ficam criptografados com a **DPAPI do Windows**, só legíveis na sua conta.
- Nenhuma imagem da tela é salva ou enviada: a análise acontece na memória, em baixa resolução.
- Comunicação externa apenas com os servidores oficiais da Tuya quando você usa a conexão pela conta.

## Testes

```bash
python -m unittest discover -s tests
```

## Licenças

As licenças das bibliotecas usadas estão em `ferramentas/licencas/` (atualize com `python ferramentas/coletar_licencas.py`).

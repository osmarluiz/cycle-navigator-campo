# CLAUDE.md — contexto para quem trabalha neste repositório

Este arquivo existe porque o projeto foi construído em sessões de Claude Code num PC Windows do
LSIE/UnB, e a memória dessas sessões é local àquela máquina. Quem abre o repositório noutro
computador (o MacBook Air do Osmar, por exemplo) precisa do que está aqui: o que é a ferramenta,
como rodá-la a partir do código, como ela é montada, quais decisões não devem ser revertidas e
onde estão as armadilhas já pagas. O `README.md` descreve o produto para o público; este arquivo
descreve o trabalho para quem o continua. Atualizado em 2026-11-17.

## 1. O que é, para quem

Ferramenta de **levantamento de campo de sistemas de cultivo**. Alunos e funcionários visitam
produtores na RIDE-DF e registram, por talhão, o que foi plantado em cada parte do ano-safra
("soja out→fev, milho safrinha mar→jul") e de quem é a terra. A base é uma série mensal de mosaicos
PlanetScope (4,8 m) de set/2020 a fev/2025 (54 meses), recortada a um retângulo de 137 × 145 km.

Quem manda é **Osmar L. F. de Carvalho** (professor, UnB/LSIE; GitHub `osmarluiz`). Ele responde
em português, direto, prefere ver o programa aberto a ler descrição, e tem três regras firmes:

- **não apagar nada** (dados, histórico, arquivos) sem ele pedir;
- **perguntar antes** de qualquer ação em repositório que não seja commit/push neste repositório
  (criar repositório, mudar remoto, empurrar para outro repositório, apagar branch);
- **nunca empurrar** para `osmarluiz/cycle-navigator` (o original) nem para
  `osmarluiz/ts-annotator`. Este repositório, `osmarluiz/cycle-navigator-campo`, é o lugar.

## 2. Onde está o quê

| coisa | onde |
|---|---|
| código | este repositório (`campo` = `osmarluiz/cycle-navigator-campo`, público) |
| motor fenométrico | `pheno-engine` v0.1.0, dependência pinada por tag; **não mora aqui** (ver §5) |
| widgets de mapa e I/O de raster | `ts-annotator` `main` público (TiledMapView, RasterSource, TimeSeriesSource, render, AnnotationStore) |
| dados (287 GB) | **não estão no git.** PC do LSIE: `F:\sits_aoi_crop`. HD de campo Seagate 5 TB (exFAT): `CycleNavigator\dados`. Plano: copiar a pasta inteira para `~/CycleNavigator` no Air |
| executáveis | GitHub Actions → artefatos (expiram em 90 dias). `build/artefatos/` no PC do LSIE (ignorado pelo git). Release por tag ainda não foi criada |
| configuração | `cycle-navigator.toml` ao lado do executável ou da pasta de trabalho (ignorado pelo git; `cycle-navigator.example.toml` é o modelo) |
| scripts de preparo (CAR, SAM) | `tools/` — rodam uma vez, em ambientes próprios, e não no Mac (SAM precisa de CUDA) |

Layout dos dados (o programa confere tudo isso ao abrir):

```
dados/cube/ride_{YYYYMM}_aoi.tif       4 bandas (B,G,R,NIR) uint16, tiled ZSTD, com overviews — 1 por mês
dados/input/basemap_{ndvitemporal,pheno,mnf}_aoi.tif   obrigatórios; rgb_chuvoso, rgb_seco opcionais
dados/products/basemap_class_aoi.tif   define a grade de referência (hoje é todo nodata, e não importa)
dados/car/car_aoi.gpkg                 29.640 imóveis do CAR (DF, GO, MG) recortados ao AOI — opcional
dados/sam/sam_aoi.gpkg                 52.423 talhões pré-segmentados com SAM 2.1 — opcional
dados/pontos/                          o que o programa grava: pontos_{safra}.json, fazendas.json, _levantador.txt
```

## 3. Rodar a partir do código

### macOS (Apple Silicon) — primeira vez

```bash
# Python 3.12 do python.org ou do Homebrew (brew install python@3.12). Não use o Python do sistema.
cd ~
git clone https://github.com/osmarluiz/cycle-navigator-campo.git NAVIGATOR
python3.12 -m venv ~/ENV/navigator          # ⚠️ o venv FORA do repositório (ver §6)
source ~/ENV/navigator/bin/activate
pip install --upgrade pip
pip install "PyQt6==6.7.1" "PyQt6-Qt6==6.7.3" "PyQt6-sip==13.8.0"
cd ~/NAVIGATOR && pip install -e ".[pivots,dev]"
python -m pytest -q                          # 4 testes do motor + 2 de fluxo (os de fluxo pulam sem dados)
cycle-navigator --config ~/CycleNavigator/cycle-navigator.toml
```

O `.toml` do pacote de campo tem `aoi = "dados"`, relativo à pasta do próprio `.toml`: funciona onde
a pasta `CycleNavigator` estiver. Se o programa não achar os dados, a mensagem diz qual arquivo
faltou; não chuta.

O pin do PyQt6 veio de um problema no **Windows** (6.11 não carregava QtCore). No Mac ele não é
sabidamente necessário, mas mantém o mesmo Qt que o executável usa; se um dia atrapalhar no Mac,
teste sem o pin e anote aqui o resultado.

### Windows (PC do LSIE)

Ambiente de desenvolvimento: `D:\ENV\navigator` (Anaconda). Ambiente **só para PyInstaller**:
`D:\ENV\build` (python.org 3.12, limpo). Repositório: `D:\NAVIGATOR`. Config: `D:\NAVIGATOR\cycle-navigator.toml`
com `aoi = "F:/sits_aoi_crop"`.

### Testes

- `tests/test_motor_compartilhado.py`: falha se alguém copiar o motor para dentro deste repositório.
  **Precisa do venv fora da árvore do repositório**, senão acha o `pheno_engine` "dentro" e falha.
- `tests/test_fluxo_real.py` + `tests/fluxo/`: abre o programa de verdade num subprocesso (offscreen),
  faz o fluxo clicar → faixas → gravar → fechar, e um teste de estresse de troca rápida de mês.
  Um abort do Qt vira código de saída. Pulam quando não há dados (`CN_CONFIG` aponta o `.toml`).

## 4. Arquitetura

`src/cycle_navigator/`, ~3.200 linhas, tudo em português. Um módulo por responsabilidade:

| módulo | faz |
|---|---|
| `config.py` | lê o `.toml` (tolera BOM), resolve caminhos relativos à pasta do `.toml`, agrupa meses em **safras completas** (out→set), auto-detecta `car/` e `sam/`, lista de classes padrão |
| `app.py` | só a partida: `monta_app(cfg, app)` cria o `ctx` e instala as peças de `montagem/` em ordem (ver §10); `main()`, `--autoteste`, tela acordada no Mac |
| `janela.py` | `BarraTopo` (Safra, Data ◀ ▶, Ver como, Levantador; modos Identificar/Desenhar/Editar; Tabelas, Exportar; botões CAR e SAM) e `JanelaCampo` (mapa em cima, curva embaixo, atalhos, `para_threads()`) |
| `ciclos.py` | `PainelCiclo`: curva NDVI do ano, faixa de contexto da série toda, faixas (bandas) com bordas que grudam no mês, detecção pelo motor por safra, chips, cultura em texto livre com autocompletar, confiança |
| `pontos.py` | camada de pontos, `PainelPontos`, `abre_store()` → `pontos_{safra}.json` (formato do AnnotationStore do ts-annotator, um arquivo por safra) |
| `fazendas.py` | `CadastroFazendas` (JSON atômico, ponto-em-polígono), `DesenhoPoligono` (vértice a vértice, duplo clique fecha, Esc cancela, botão direito desfaz), `CamadaFazendas`, `DialogoFazenda` |
| `car.py` | `CamadaCAR` genérica para CAR **e** SAM: gpkg → polígonos em pixel + STRtree, LOD quando há vértices demais, seleção com cartão de dados; tradução dos campos do CAR |
| `tabelas.py` | janela com duas tabelas (Fazendas, Pontos rotulados); duplo clique centra o mapa |
| `exporta.py` | GPKG/SHP/CSV, uma feição por faixa; nomes curtos para SHP |
| `estilo.py` | tokens de design (cores, fonte Segoe UI Variable, ícones mdi6 via qtawesome) e o QSS inteiro; `objectName` é o que liga widget a estilo |

Fluxo: `.toml` → `Config` → `monta_app` abre a série da safra (`TimeSeriesSource`) e os basemaps,
cria mapa, barra, painéis e camadas → clique no mapa em modo Identificar lê a curva dos 54 meses,
mostra 12 (a safra), o motor sugere faixas **com cultura vazia**, o usuário nomeia e grava →
JSON por safra. Fazendas são desenhadas, ou adotadas de um polígono do CAR/SAM (modo Editar), ou
semeadas a partir dele e ajustadas (modo Desenhar). Ponto dentro de fazenda herda produtor e contato.

Empacotamento: `build/launcher.py` (acha o `.toml` ao lado do executável; no Mac, **ao lado do
`.app`**, não dentro dele; log em `cycle-navigator.log` ao lado) → `build/cycle-navigator.spec`
(PyInstaller onedir, sem console; `BUNDLE` só no Darwin) → `.github/workflows/build.yml` (Windows x64,
macOS arm64 em `macos-latest`, macOS x64 em `macos-15-intel`) → `build/monta_ssd.ps1` monta o disco de campo.

## 5. Decisões que não devem ser revertidas (e por quê)

- **O motor não mora aqui.** `pheno-engine` é dependência pinada. O que o aluno confirma em campo
  tem de ser a mesma leitura que as análises usam; copiar `pheno.py` para cá quebraria isso em
  silêncio. Há teste para impedir.
- **Faixas sugeridas pelo motor, cultura vazia.** Ninguém desenha duas bordas por talhão com o
  produtor esperando; e "Soja" pré-preenchida seria aceita sem ler.
- **Detecção sempre por safra (12 meses de outubro), nunca na série toda.** O motor assume isso
  (índices de seca 8..12). A faixa de contexto mostra os 54 meses, a detecção roda na janela.
- **Bordas grudam no mês.** O dado é mensal; borda no meio do mês é ruído.
- **Uma faixa em foco por vez**, ✕ no chip, clicar na curva seleciona, arrastar no vazio cria.
- **Sem overlay colorido no mapa.** Só o que o usuário desenhou. O continuum do navigator original saiu.
- **Barra de cima + mapa inteiro + curva embaixo; tabelas em janela própria.** Painel lateral e doca
  foram rejeitados ("inútil a maior parte do tempo", "esmagou o layout").
- **Data e "Ver como" são campos separados.** Composição mensal (RGB natural, falsa-cor, NDVI do mês)
  e composições do ano (NDVI-temporal, fenologia, MNF, RGB chuva/seca, classificação) no mesmo combo.
- **CAR e SAM são ferramentas de contorno, não camadas decorativas.** Ligáveis; CAR nasce desligado;
  visíveis em todos os modos quando ligados; clique seleciona e mostra cartão; Editar adota; Desenhar semeia.
- **Dados do CAR no cadastro** como bloco só-leitura (código, município, área, módulos fiscais,
  status, tipo). O CAR não tem nome de dono nem contato: isso vem da conversa.
- **Um JSON por safra para pontos** (`pontos_2023_24.json`), no formato do ts-annotator; um
  `fazendas.json`. Exportação SHP/GPKG/CSV com uma feição por faixa.
- **Mac em `.tar.gz`, nunca zip** (o zip do upload-artifact perde symlinks e bit de execução).
- **Disco de campo em exFAT** (NTFS é só-leitura no Mac; o programa não gravaria pontos).
- **`robocopy` sem `/J` nem `/MT` para o HD externo**: com eles, 8 arquivos ficaram com tamanho
  arredondado ao setor e o robocopy travou em tentativas infinitas, em silêncio.

## 6. Armadilhas já pagas

- **PyQt6 6.11 + Qt6 6.11.2 não carregou QtCore no Windows.** Pin 6.7.1 / 6.7.3 / sip 13.8.0.
- **PyInstaller só a partir de Python limpo** (python.org). Do venv do Anaconda o exe falha com `_ctypes`.
- **venv dentro do repositório** faz `test_motor_compartilhado` falhar. Venv sempre fora.
- **Fechar o programa depois de trocar muitos meses abortava (`0xC0000409`)**: Qt não destrói
  `QThread` rodando. `JanelaCampo.para_threads()` espera as threads do mapa, ligado também em
  `app.aboutToQuit`. Reproduzido e validado com `tests/fluxo/estresse.py`.
- **`rasterio`/GDAL 3.12 não lê o mosaico ENVI `.dat` de 82 GB** ("Int overflow"). Os recortes
  foram feitos com o GDAL 3.8 do QGIS. Os GeoTIFFs **precisam de overviews** (`gdaladdo 2 4 8 16 32`),
  senão cada pan lê em resolução cheia e a ferramenta engasga.
- **STRtree**: o predicado para "ponto dentro de polígono" é `within` com o ponto como consulta; com
  `contains` nada era encontrado e o CAR parecia invisível.
- **`.toml` com BOM** (PowerShell `Set-Content -Encoding utf8` escreve BOM). O config lê `utf-8-sig`;
  ao escrever, use `UTF8Encoding($false)`.
- **Launcher no Mac**: `sys.executable` está em `CycleNavigator.app/Contents/MacOS/`; o `.toml` e os
  dados ficam ao lado do `.app`. O launcher sobe três níveis quando reconhece a estrutura.
- **Runner `macos-13` foi aposentado (2025-12-04)** e fica na fila para sempre. Intel compila em `macos-15-intel`.
- **Gatekeeper no macOS 15+**: botão direito → Abrir já não libera app sem assinatura. É Ajustes →
  Privacidade e Segurança → "Abrir Mesmo Assim", ou `xattr -dr com.apple.quarantine CycleNavigator.app`.
- **As portas USB 9 e 10 do PC do LSIE não fornecem corrente para girar HD externo** (quatro discos
  falharam ali em 17/11/2026; a porta 22 funciona). Não é problema de disco.
- **Abrir leva ~40 s** (CAR e SAM carregam na partida). Carregar sob demanda é melhoria conhecida, não feita.

## 7. Build e distribuição

- Actions → "build" → *Run workflow* compila as três plataformas (~20 min; os runners de Mac podem
  esperar muito na fila) e publica artefatos. Baixe com `gh run download <id> -D build/artefatos`.
- Verificação de um `.tar.gz` do Mac: contar symlinks (`tar -tvf | grep -c '^l'`, ~577), bit de
  execução no binário `Contents/MacOS/cycle-navigator`, cabeçalho Mach-O `cffa edfe 0c00 0001` (arm64)
  ou `0700 0001` (x86_64).
- Disco de campo: `.\build\monta_ssd.ps1 -Destino "H:\CycleNavigator" -Dist build\artefatos\CycleNavigator-windows-x64`
  (ou `-Safras "2023/24"` para um pacote de uma safra, ~75 GB). Exige exFAT, confere tamanhos ao fim,
  escreve `LEIA-ME_MAC.txt`.
- **Pendente**: release por tag (`v1.0.0`) com os três pacotes anexados, para link público permanente.
  O workflow já dispara em tags `v*`; falta o passo que anexa à release. Notarização da Apple também não foi feita.

## 8. Convenções

- Código, comentários, commits e interface em **português** (sem acento nos identificadores; nos
  comentários o acento é opcional, o repositório mistura). Comentários que explicam uma armadilha
  começam com `⚠️`; os que explicam uma garantia de projeto, com `⚠️⚠️`.
- Commits pequenos, mensagem em português dizendo o quê e por quê, terminando com
  `Co-Authored-By: Claude <modelo da sessão> <noreply@anthropic.com>` (o modelo que de fato escreveu). Identidade git: Osmar L. F. de Carvalho.
- Testes offscreen antes de mudar interface (`QT_QPA_PLATFORM=offscreen`); use `isHidden()`, não
  `isVisible()`, porque offscreen nada é "visível".
- Interface: tokens em `estilo.py`, nunca cor solta no widget; `objectName` liga ao QSS; sem negrito
  em botão marcado (corta o texto); fonte do sistema; hover em tudo que é clicável.
- Captura de tela só da janela do programa, nunca do desktop (há WhatsApp e planilhas abertas).

## 9. Estado em 2026-11-17 e o que vem

Feito e validado: a ferramenta inteira (93+ verificações offscreen, 4 testes do motor, 2 de fluxo),
executável Windows, `.app` arm64 e x64 compilados hoje e conferidos, CAR de 3 estados, SAM do AOI,
disco de campo montado (287 GB, tamanhos conferidos, programa abriu direto do disco no Windows).

**Nunca testado**: o `.app` num Mac de verdade. O primeiro teste é no MacBook Air do Osmar (M-series,
1 TB). Se falhar, o `cycle-navigator.log` ao lado do `.app` diz onde; se nem o log aparecer, rode
`./CycleNavigator.app/Contents/MacOS/cycle-navigator` no Terminal e leia o erro.

Próximos passos prováveis, por ordem: (1) rodar do código no Air e corrigir o que for específico de
macOS; (2) release `v1.0.0`; (3) carregar CAR/SAM sob demanda; (4) notarização, se os alunos usarem
Mac em número.

## 10. O que entrou no MacBook Air em 2026-11-18

O programa rodou pela primeira vez num Mac de verdade (Air M5, 24 GB, tela de 1470 × 956 pontos),
do código e empacotado. O que mudou nesse dia, e que as seções acima ainda não contam:

**Módulos novos** (`src/cycle_navigator/`, agora ~6.000 linhas):

| módulo | faz |
|---|---|
| `montagem/` | o antigo `monta_app` de 1.200 linhas, cortado em 16 peças. Cada uma tem `instala(ctx)`: lê do `ctx` o que as anteriores deixaram, escreve o que cria. A ordem está em `montagem/__init__.py` (`ORDEM`) e **importa**. `fontes.py` abre os rasters |
| `recorte.py` | `RecorteVivo`: SAM 2.1 no clique (torch + MPS). Bloco de 1024 px em cache, escalas 1/2/4 quando a máscara encosta na borda. **Opcional de ponta a ponta**: sem `torch`, `sam2` ou o modelo em `~/CycleNavigator/modelos/`, o botão "Recortar" some e o resto funciona |
| `analise.py` | painel de análise: `resume()` e `pendencias()` puras (testadas) e `JanelaAnalise` (números, sistemas, calendário, vigor, o que conferir) |
| `sugestoes.py`, `janela_sugestoes.py` | caixa de sugestões: uma fila de `dados/sugestoes/<id>.json` (+ `.png` da tela). Quem responde é uma sessão de Claude Code: `tools/vigia_sugestoes.py` avisa, `tools/sugestoes.py` lê e responde, a skill `.claude/skills/responder-sugestoes` diz como |
| `arquivos.py` | arquivo ilegível é **posto de lado** com outro nome (`.danificado-<data>`), nunca apagado nem sobrescrito |
| `busca.py`, `posicao.py` | busca por município, CAR ou coordenada; "Onde estou" (QtPositioning) |

**Como se usa agora**: a origem da curva é uma escolha de três, `Talhão | Recortar | Ponto`. Clicar
onde não há talhão pronto aciona o recorte sozinho (recusado acima de 400 ha ou com nota < 0,75;
nota < 0,8 mostra "contorno incerto — confira"). ⇧-clique soma um ponto ao recorte aberto, ⌥-clique
tira. O ponto gravado guarda `fonte_curva`, `contorno`, `recorte_pontos`, `recorte_nota`, `talhao_ha`.
A exportação leva uma segunda camada, `talhoes`, com um polígono por talhão.

**Regras novas**:

- **Sugestão nunca é implementada sem o ok explícito do Osmar.** Pergunta de informação pode ser
  respondida direto; mudança no programa, só depois de ele aprovar.
- **Tamanho de arquivo é teste** (`tests/test_padrao_do_codigo.py`): peça de `montagem/` até 300
  linhas; os grandes antigos têm teto próprio que só pode descer. Dívida conhecida: `ciclos.py` (897),
  `janela.py` (489), `analise.py` (437), `fazendas.py` (360), `car.py` (318) e a função `ao_clicar`
  (~130 linhas, em `montagem/clique.py`). Cortar é **mover**, não reescrever.
- **Testes nunca tocam `~/CycleNavigator/dados/pontos`.** Use uma pasta de trabalho com links para
  `cube`, `input`, `products`, `car`, `sam` e uma `pontos` própria, apontada por `CN_CONFIG`.

**Armadilhas pagas neste dia**:

- ⚠️ **`pyproj` e `rasterio` trazem cada um uma `libproj` com o mesmo nome**; o PyInstaller guarda uma
  só e a exportação saía sem CRS, só no `.app`. `build/corrige_dylibs_mac.py` religa.
- ⚠️ **O caminho religado não pode ser mais comprido que o da wheel**: nas wheels x86_64 o cabeçalho
  Mach-O não tem folga e o `install_name_tool` recusava; o build de Mac Intel quebrou assim. Cada
  pacote ganha um link curto `dl -> __dot__dylibs`. Conferido aqui com as wheels x86_64 baixadas.
- ⚠️ **Teste offscreen que gira `processEvents()` à mão não entrega `deleteLater`**: parece vazamento
  de memória e não é. Chame `QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)`.
- ⚠️ **`torchvision` precisa de `collect_all` no spec**, senão o modelo morre em
  "operator torchvision::nms does not exist", só no pacote.
- ⚠️ **`cycle-navigator --autoteste`** existe para isso: roda o que só quebra depois de empacotar
  (pyproj, clique, recorte, análise, sugestões), sem gravar nada; sai 0 ou 1. Rode após cada build.
- ⚠️ **Trocar de safra com um talhão aberto** gravava faixas do ano errado; agora o talhão reabre na
  safra nova. **Clique perto de um ponto gravado** reabria o vizinho; só gruda se o clique não cair
  dentro de outro talhão.
- ⚠️ **`deleteLater()` ao refazer uma lista** deixa o widget velho por cima do novo por um instante;
  `setParent(None)` antes.
- ⚠️ **A barra de cima tinha largura mínima de 1601 px**, maior que a tela do Air; o mapa abria com
  faixas pretas. Hoje são 1347, e `enquadra_largura` ajusta o mapa ao abrir.
- A tela do Mac apagava no meio da conversa: o programa chama `caffeinate` enquanto está aberto.
- Abrir leva ~11 s no Air (não os ~40 s do PC), ainda com CAR e SAM na partida.

**Ambientes no Air**: `~/ENV/navigator` (desenvolvimento, com torch/sam2), `~/ENV/build` (só
PyInstaller; `pip install .` antes de cada build). Build local:
`pyinstaller --noconfirm --distpath build/dist --workpath build/work build/cycle-navigator.spec`.
O build do GitHub Actions **não** instala torch/sam2: os pacotes de lá saem sem o recorte na hora.

**Sem teste até aqui**: "Onde estou" (depende da permissão do macOS), e tudo o que é novo neste
dia em Windows e em Mac Intel.

## 11. Depois da reunião com a cooperativa (2026-11-18, tarde)

O Osmar usou o programa com a cooperativa e voltou com um reparo de fundo: **estávamos misturando
coisas**. O que ficou decidido, e não deve ser desfeito:

- **Há duas informações distintas: a do PIXEL e a da FAZENDA.** Identificar só **lê**: a série do
  pixel (ou, se pedida, a média do talhão pronto) e a fazenda do lugar, em linhas separadas do
  cabeçalho. Identificar **não recorta**; a origem da curva é `Pixel | Média do talhão`, padrão Pixel.
- **O SAM é ferramenta de desenho**, não fonte de informação. Mora no modo Desenhar, na barra de
  ferramentas (`barra_desenho.py`): `Polígono | Automático | Copiar contorno`, com Desfazer,
  Concluir e Cancelar e a dica do próximo clique. ⇧ soma e ⌥ tira valem só no Automático.
- **O contorno do CAR/talhão só é copiado pela ferramenta Copiar**: antes, começar um polígono à
  mão dentro de um imóvel com a camada ligada copiava o contorno sem ninguém pedir.
- **As faixas são uma lista ao lado da curva** (`lista_faixas.py`), uma linha por faixa com número,
  período, cultura e confiança. A fila de chips não aguentava cinco faixas.
- Bordas das faixas com cursor ↔.

**Armadilhas desse dia**:

- ⚠️ **O atalho de Enter da janela chega antes do campo de texto**: a busca só funcionava pelo que
  se escolhia na lista de sugestões. `JanelaCampo._enter` entrega o Enter ao campo em foco. Teste
  de busca tem de apertar Enter de verdade (`QTest.keyClick`), não chamar `procura()`.
- ⚠️ **A aba Fazendas ficava desabilitada no modo Desenhar** (onde se fica depois de desenhar).
- ⚠️ **O autoteste apagava o log do programa aberto ao lado** (mesmo arquivo, `filemode="w"`).
  Agora escreve em `cycle-navigator-autoteste.log`.
- ⚠️ **A tabela passou a abrir em "Talhões levantados"**; no mesmo dia os dois talhões da safra
  sumiram às 15:38 e não se sabe se foi exclusão por engano. A exclusão de talhão ainda não diz o
  nome do que vai excluir (a de fazenda diz). Fazer.

**Depois, no mesmo dia, com o ok dele ("sim")**:

- **O painel de baixo tem duas abas, `Pixel | Fazenda`** (`painel_lugar.py`). A aba Fazenda é o
  cadastro inteiro do lugar clicado, editável ali, com "Editar contorno" e "Excluir fazenda". A aba
  não muda sozinha ao clicar noutro lugar. Concluir um desenho grava o contorno e abre a aba Fazenda
  com o foco no nome — **sem diálogo por cima do mapa**. Texto de cadastro digitado e não salvo é
  gravado ao sair do lugar.
- **Só dois modos: Identificar e Desenhar.** O modo Editar acabou.
- **Sair de um ponto com cultura nomeada e não gravada pergunta** Gravar / Descartar / Voltar
  (`pode_sair` em `montagem/clique.py`). Vale para clique no mapa e troca de modo.
- **"Ponto" é o que se levanta; "fazenda" é o polígono; "talhão" só a camada de contornos prontos.**
- **As cores das culturas foram medidas** (`config.py`): busca que maximiza a diferença entre todos
  os pares em OKLab, em visão normal e simulando deuteranopia e protanopia. Antes de trocar uma cor,
  meça de novo; o nome da cultura fica sempre escrito ao lado, porque 16 classes não se distinguem
  só por cor.
- Faixa na curva é um véu (alfa 62/40/22), não um bloco; `TEXT_3` tem contraste ≥ 4,5:1.
- `texto.py`: `plural()` e `data_br()`. Nada de "(s)", "(ões)" nem data ISO na tela.

**Ainda por fazer do que ele pediu**: os comandos de edição de vértice continuam os do
`PolyLineROI` (arrastar, clicar na linha, botão direito apaga) — falta desfazer no ajuste e snap;
editar atributos direto na tabela; todas as safras numa tabela só.

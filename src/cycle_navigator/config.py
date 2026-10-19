# -*- coding: utf-8 -*-
"""ONDE ESTAO OS DADOS -- lido de fora, nunca escrito aqui.

⚠️⚠️ POR QUE ISTO EXISTE. O lancador original (`examples/run_cycle_inspect.py` no ts-annotator) trazia
os caminhos embutidos: `E:\\sits_aoi_crop`, `D:\\PROJECTS\\sits\\data\\external\\...`. Numa maquina que
nao seja a do autor, a ferramenta nao abre, e um artigo que cita a ferramenta como resultado nao pode
depender de um caminho que so' existe num disco. Aqui os caminhos vem de um arquivo de configuracao ou
de variaveis de ambiente, e a falta de cada um da' uma mensagem que diz o que fazer.

Ordem de procura, a primeira que existir vence:
  1. o caminho passado em `--config`
  2. `$CYCLE_NAVIGATOR_CONFIG`
  3. `./cycle-navigator.toml`
  4. `~/.config/cycle-navigator/config.toml`

Exemplo minimo:

    aoi        = "E:/sits_aoi_crop"
    meses      = [202210, 202211, 202212, 202301, 202302, 202303,
                  202304, 202305, 202306, 202307, 202308, 202309]
    # opcionais
    pivos      = "D:/PROJECTS/sits/data/external/ana_pivos_RIDE_2022.gpkg"
    predicao   = "E:/sits_aoi_crop/predictions/pred_it_v2.tif"
"""
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

NOME = "cycle-navigator.toml"
PADROES = ("CYCLE_NAVIGATOR_CONFIG",)

# Classes do trabalho de campo. Quem vai a campo pergunta ao produtor o que foi plantado, entao a
# lista fala de CULTURA, nao de numero de ciclos -- o numero de ciclos o motor fenometrico ja' le'
# sozinho da curva, e e' justamente o que o rotulo de campo serve para conferir.
# ⚠️ `nao_sei` existe de proposito e fica por ultimo: sem ele, quem esta' em duvida chuta, e um chute
# entra no arquivo com a mesma cara de uma informacao obtida com o produtor.
CLASSES_PADRAO = {
    "Soja":                "#f67825",
    "Milho":               "#ffd400",
    "Milho safrinha":      "#c9a227",
    "Algodao":             "#f2f0e6",
    "Feijao":              "#8d6e63",
    "Trigo":               "#d9b382",
    "Sorgo":               "#b5651d",
    "Cafe":                "#5b2d8c",
    "Cana":                "#7cb342",
    "Hortalicas":          "#26c6da",
    "Pastagem":            "#33c16f",
    "Silvicultura":        "#33691e",
    "Vegetacao natural":   "#9acd32",
    "Agua":                "#1f5fbf",
    "Urbana/solo exposto": "#976c5e",
    "nao_sei":             "#7a7a7a",
}


class ConfiguracaoAusente(RuntimeError):
    """Erro de configuracao com instrucao, nao stack trace."""


def _acha(explicito=None):
    if explicito:
        return Path(explicito)
    for var in PADROES:
        if os.environ.get(var):
            return Path(os.environ[var])
    for c in (Path.cwd() / NOME, Path.home() / ".config" / "cycle-navigator" / "config.toml"):
        if c.exists():
            return c
    raise ConfiguracaoAusente(
        f"nenhuma configuracao encontrada.\n"
        f"Crie um {NOME} no diretorio atual, ou aponte $CYCLE_NAVIGATOR_CONFIG para ele.\n"
        f"O minimo e':\n\n"
        f'    aoi   = "/caminho/para/o/recorte"\n'
        f"    meses = [202210, 202211, 202212, 202301, 202302, 202303,\n"
        f"             202304, 202305, 202306, 202307, 202308, 202309]\n")


@dataclass
class Config:
    aoi: Path
    meses: list
    pivos: Path = None
    predicao: Path = None
    car: Path = None          # perimetros do CAR recortados ao AOI (opcional)
    origem: Path = None
    classes: dict = field(default_factory=lambda: dict(CLASSES_PADRAO))
    _faltando: list = field(default_factory=list)

    @property
    def cubo(self):
        return [self.aoi / "cube" / f"ride_{m}_aoi.tif" for m in self.meses]

    def meses_de(self, safra):
        return self.safras[safra]

    @property
    def safras(self):
        """{'2022/23': [202210, ..., 202309]} -- so' os anos-safra COMPLETOS que ha' nos meses.

        ⚠️ Agrupa por outubro, nao em blocos de 12 a partir do primeiro mes da lista. A serie real
        comeca em setembro/2020 e termina em fevereiro/2025, ou seja, tem sobra nas duas pontas;
        fatiar de 12 em 12 a partir do inicio produziria "safras" deslocadas, de setembro a agosto,
        que nao correspondem a nenhum calendario agricola -- e o erro so' apareceria la' na frente,
        como uma fenologia que nao fecha.
        """
        ordenados = sorted(self.meses)
        existe = set(ordenados)
        out = {}
        for m in ordenados:
            if m % 100 != 10:                     # safra comeca em outubro
                continue
            ano = m // 100
            janela = ([ano * 100 + mm for mm in (10, 11, 12)] +
                      [(ano + 1) * 100 + mm for mm in range(1, 10)])
            if all(x in existe for x in janela):
                out[f"{ano}/{str(ano + 1)[2:]}"] = janela
        return out

    @property
    def pasta_pontos(self):
        return self.aoi / "pontos"

    @property
    def basemaps(self):
        b = self.aoi / "input"
        return {"ndvi": b / "basemap_ndvitemporal_aoi.tif",
                "pheno": b / "basemap_pheno_aoi.tif",
                "mnf": b / "basemap_mnf_aoi.tif",
                "classe": self.aoi / "products" / "basemap_class_aoi.tif"}

    @property
    def basemaps_extra(self):
        """Visualizacoes que ENRIQUECEM, mas sem as quais a ferramenta abre.

        ⚠️ Opcionais de proposito: sao uteis (um RGB natural da chuva e outro da seca ajudam a
        reconhecer a lavoura a olho antes de perguntar ao produtor), mas exigir cada uma delas faria
        a ferramenta recusar a abrir por causa de um arquivo acessorio. O que falta e' avisado, nao
        fatal.
        """
        b = self.aoi / "input"
        return {"rgb_chuvoso": b / "basemap_rgb_chuvoso_aoi.tif",
                "rgb_seco": b / "basemap_rgb_seco_aoi.tif"}


def carrega(explicito=None):
    p = _acha(explicito)
    if not p.exists():
        raise ConfiguracaoAusente(f"configuracao apontada nao existe: {p}")
    # ⚠️ tolera BOM. `tomllib.load` recusa um arquivo que comece com o BOM de UTF-8 e o erro que ele
    # da' e' "Invalid statement (at line 1, column 1)" -- que aponta para a primeira linha do
    # arquivo, onde nao ha' nada de errado, e manda o usuario cacar um defeito que nao existe.
    # No Windows isso nao e' caso raro: PowerShell (`Set-Content -Encoding utf8`) e o "UTF-8 com
    # BOM" do Bloco de Notas gravam assim.
    bruto = p.read_bytes().decode("utf-8-sig")
    try:
        d = tomllib.loads(bruto)
    except tomllib.TOMLDecodeError as e:
        raise ConfiguracaoAusente(f"{p}: o arquivo nao e' TOML valido -- {e}") from None
    if "aoi" not in d:
        raise ConfiguracaoAusente(f"{p}: falta a chave obrigatoria `aoi`")
    if "meses" not in d or len(d["meses"]) < 12:
        raise ConfiguracaoAusente(
            f"{p}: `meses` precisa listar os meses disponiveis (no minimo um ano-safra inteiro).\n"
            f"Pode listar TODOS os meses que voce tem; a ferramenta agrupa em safras sozinha.")
    # ⚠️ caminho relativo e' relativo ao PROPRIO .toml, nao ao diretorio de onde se abriu o programa.
    # No notebook de campo os dados ficam numa pasta ao lado do executavel ("aoi = 'dados'"), e um
    # atalho na area de trabalho abre o programa com outro diretorio corrente.
    def _cam(chave):
        v = d.get(chave)
        if not v:
            return None
        c = Path(v)
        return c if c.is_absolute() else (p.parent / c).resolve()

    cfg = Config(aoi=_cam("aoi"), meses=list(d["meses"]),
                 pivos=_cam("pivos"), predicao=_cam("predicao"), car=_cam("car"),
                 classes=dict(d["classes"]) if d.get("classes") else dict(CLASSES_PADRAO),
                 origem=p)
    # ⚠️ um ano-safra INCOMPLETO nao serve: a leitura fenometrica compara o ciclo com o ano inteiro,
    # e doze meses faltando um sao onze meses que mentem sobre o fim do ciclo.
    if not cfg.safras:
        raise ConfiguracaoAusente(
            f"{p}: nenhum ano-safra completo (outubro a setembro) nos `meses` listados.\n"
            f"Meses vistos: {min(cfg.meses)} a {max(cfg.meses)}.")
    # ⚠️ conferir AGORA, nao no meio do desenho da janela. Um caminho errado que so' aparece depois de
    # trinta segundos de carregamento e' pior que um erro imediato.
    cfg._faltando = [str(x) for x in list(cfg.cubo) + list(cfg.basemaps.values()) if not x.exists()]
    # CAR: se nao foi declarado, usa o padrao do recorte quando ele existir; nunca e' obrigatorio
    if cfg.car is None and (cfg.aoi / "car" / "car_aoi.gpkg").exists():
        cfg.car = cfg.aoi / "car" / "car_aoi.gpkg"
    if cfg._faltando:
        raise ConfiguracaoAusente(
            f"{p}: {len(cfg._faltando)} arquivo(s) declarado(s) nao existem, a comecar por\n"
            f"  {cfg._faltando[0]}\n"
            f"Confira `aoi` e `meses`.")
    return cfg

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
    origem: Path = None
    _faltando: list = field(default_factory=list)

    @property
    def cubo(self):
        return [self.aoi / "cube" / f"ride_{m}_aoi.tif" for m in self.meses]

    @property
    def basemaps(self):
        b = self.aoi / "input"
        return {"ndvi": b / "basemap_ndvitemporal_aoi.tif",
                "pheno": b / "basemap_pheno_aoi.tif",
                "mnf": b / "basemap_mnf_aoi.tif",
                "classe": self.aoi / "products" / "basemap_class_aoi.tif"}


def carrega(explicito=None):
    p = _acha(explicito)
    if not p.exists():
        raise ConfiguracaoAusente(f"configuracao apontada nao existe: {p}")
    with open(p, "rb") as f:
        d = tomllib.load(f)
    if "aoi" not in d:
        raise ConfiguracaoAusente(f"{p}: falta a chave obrigatoria `aoi`")
    if "meses" not in d or len(d["meses"]) != 12:
        raise ConfiguracaoAusente(f"{p}: `meses` precisa listar os 12 meses do ano-safra, em ordem")
    cfg = Config(aoi=Path(d["aoi"]), meses=list(d["meses"]),
                 pivos=Path(d["pivos"]) if d.get("pivos") else None,
                 predicao=Path(d["predicao"]) if d.get("predicao") else None,
                 origem=p)
    # ⚠️ conferir AGORA, nao no meio do desenho da janela. Um caminho errado que so' aparece depois de
    # trinta segundos de carregamento e' pior que um erro imediato.
    cfg._faltando = [str(x) for x in list(cfg.cubo) + list(cfg.basemaps.values()) if not x.exists()]
    if cfg._faltando:
        raise ConfiguracaoAusente(
            f"{p}: {len(cfg._faltando)} arquivo(s) declarado(s) nao existem, a comecar por\n"
            f"  {cfg._faltando[0]}\n"
            f"Confira `aoi` e `meses`.")
    return cfg

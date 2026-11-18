# -*- coding: utf-8 -*-
"""MONTAGEM · fontes: as constantes das camadas e a abertura dos rasters e da serie mensal."""
import logging
from ts_annotator.core.raster_source import RasterSource
from ts_annotator.core.timeseries import TimeSeriesSource
from ts_annotator.render import CLASS_COLORS
from ts_annotator.render import make_class_colorizer
from ts_annotator.render import make_rgb_colorizer
import numpy as np
import pyqtgraph as pg
import rasterio

log = logging.getLogger(__name__)


def cinza(nodata=0, escurece=0.55):
    """RGB medio -> cinza escurecido: base neutra para o eixo colorido saltar."""
    def fn(arr):
        g = arr[:3].astype(np.float32).mean(0)
        gv = np.clip(g * escurece, 0, 255).astype(np.uint8)
        rgba = np.dstack([gv, gv, gv, np.full(gv.shape, 255, np.uint8)])
        rgba[(arr[:3].sum(0) == nodata * 3), 3] = 0
        return rgba
    return fn


def _tabela_de_ciclos(pred_tif):
    """idx da predicao -> numero de ciclos, lido do sidecar .json do proprio raster.

    ⚠️ le' os rotulos do arquivo em vez de assumir a ordem das classes. A ordem muda entre modelos, e
    uma tabela escrita a mao aponta para a classe errada sem avisar.
    """
    import json
    import re
    labs = json.load(open(str(pred_tif).replace(".tif", ".json"), encoding="utf-8"))["labs"]
    lut = np.zeros(256, np.float32)
    for i, l in enumerate(labs):
        if l.startswith("Cultivo") and "perene" not in l.lower():
            m = re.search(r"(\d)", l)
            if m:
                lut[i] = int(m.group(1))
    return lut


def serie(cfg, safra_ou_meses, T):
    """A serie temporal de um ano-safra (nome) ou de uma lista de meses, na grade da base.

    ⚠️ Carregar a serie inteira aqui e' seguro -- o que NAO pode e' entregar 54 meses de uma vez ao
    motor fenometrico, que pressupoe doze meses a partir de outubro (`derive_feat` tem os meses da
    seca fixos nos indices 8..12). Quem cuida disso e' `ciclos.deteccao`, que fatia por ano-safra
    antes de chamar o motor. Entregar a serie toda nao daria erro -- daria numero, e errado.
    """
    meses = (cfg.meses_de(safra_ou_meses) if isinstance(safra_ou_meses, str)
             else list(safra_ou_meses))
    arquivos = [str(cfg.aoi / "cube" / f"ride_{m}_aoi.tif") for m in meses]
    # cada mes pode estar deslocado em relacao a' base; o deslocamento sai do proprio geotransform
    offs = [round((rasterio.open(f).transform.f - T.f) / T.a) for f in arquivos]
    ts = TimeSeriesSource(arquivos, bands=(1, 2, 3, 4), row_offsets=offs, nodata=65535, scale=10000)
    if not ts.has_overviews:
        log.warning("⚠️ %d mes(es) sem overviews: a navegacao vai ler em resolucao cheia e travar "
                    "em area grande. Gere com: gdaladdo -r average <mes>.tif 2 4 8 16 32",
                    len(arquivos))
    return ts


# Esticamento FIXO do RGB dos meses (bandas do cubo: 1=B 2=G 3=R 4=NIR -> indices 0..3).
# ⚠️ FIXO, nao por-viewport: o ponto de ver mes a mes e' COMPARAR os meses entre si. Um esticamento
# recalculado a cada vista deixa todo mes com a mesma cara e some com a diferenca que se queria ver.
# Os valores do RGB natural vem do projeto ride_review, ajustados nesta cena.
RGB_NAT = {"idx": [2, 1, 0], "lo": [260, 375, 171], "hi": [1879, 1247, 795]}
RGB_FC = {"idx": [3, 2, 1], "lo": [900, 260, 375], "hi": [4200, 1879, 1247]}

# As camadas que dependem da DATA, e as que resumem o ano inteiro.
CAMADAS_MES = ["RGB natural", "Falsa-cor (infravermelho)", "NDVI do mês"]
CAMADAS_ANO = ["NDVI-temporal (ano)", "Fenologia (ano)", "MNF (ano)",
               "RGB da chuva (jan)", "RGB da seca (ago)", "Classificação"]


def cor_ndvi(nodata=65535):
    """NDVI de um mes cru -> rampa de cor. ⚠️ So' visualizacao: a fenometria vem do pheno_engine."""
    import pyqtgraph as pg
    lut = pg.colormap.get("RdYlGn", source="matplotlib").getLookupTable(0.0, 1.0, 256)

    def fn(arr):
        a = arr.astype(np.float32)
        red, nir = a[2], a[3]
        mau = (~np.isfinite(red)) | (~np.isfinite(nir)) | (red == nodata) | (nir == nodata)
        nd = (nir - red) / (nir + red + 1e-6)
        i = np.clip(((np.nan_to_num(nd) + 0.2) / 1.2 * 255), 0, 255).astype(np.uint8)
        rgba = np.dstack([lut[i], np.full(i.shape, 255, np.uint8)])
        rgba[mau, 3] = 0
        return rgba
    return fn


def _tem_dado(tif):
    """Ha' algum pixel diferente de nodata? Lido numa amostra 1/32, que e' o que basta."""
    try:
        with rasterio.open(str(tif)) as d:
            a = d.read(1, out_shape=(1, max(1, d.height // 32), max(1, d.width // 32)))
            return bool((a != (255 if d.nodata is None else d.nodata)).any())
    except Exception:
        return False


def monta(cfg):

    """Abre as fontes e devolve o que a janela precisa."""
    bm = cfg.basemaps
    classe = RasterSource(str(bm["classe"]))

    rgb, cinz = make_rgb_colorizer(nodata=0), cinza(nodata=0)
    ndvi = RasterSource(str(bm["ndvi"]))
    # ⚠️⚠️ AS CHAVES SAO OS NOMES DE `CAMADAS_ANO`, LETRA POR LETRA. `usa_camada` faz
    # `bases.get(nome)` e nao reclama quando nao acha -- so' nao troca o mapa. Durante um tempo as
    # chaves daqui eram "Imagem · NDVI-temporal" e o combo oferecia "NDVI-temporal (ano)": cinco das
    # seis visoes do ano nao faziam NADA ao serem escolhidas, e ninguem viu porque nao dava erro.
    # O combo agora so' oferece o que existe neste dicionario (ver `monta_app`).
    bases = {"NDVI-temporal (ano)": (ndvi, rgb),
             "Fenologia (ano)": (RasterSource(str(bm["pheno"])), rgb),
             "MNF (ano)": (RasterSource(str(bm["mnf"])), rgb)}
    for chave, rotulo in (("rgb_chuvoso", "RGB da chuva (jan)"),
                          ("rgb_seco", "RGB da seca (ago)")):
        p = cfg.basemaps_extra[chave]
        if p.exists():
            bases[rotulo] = (RasterSource(str(p)), rgb)
        else:
            log.info("visualizacao opcional ausente (segue sem ela): %s", p.name)
    # ⚠️ a classificacao so' entra na lista se tiver algum pixel classificado: o raster do pacote
    # de campo e' todo nodata (existe para definir a grade), e oferece-lo era oferecer um mapa preto.
    if _tem_dado(bm["classe"]):
        bases["Classificação"] = (classe, make_class_colorizer(CLASS_COLORS, 255))
    assert set(bases) <= set(CAMADAS_ANO), set(bases) - set(CAMADAS_ANO)

    pivos = []
    if cfg.pivos:
        try:
            import geopandas as gpd
            pivos = list(gpd.read_file(str(cfg.pivos)).geometry)
            log.info("pivot register: %d polygons", len(pivos))
        except Exception as e:                      # opcional: a ferramenta abre sem isso
            log.warning("pivot register unavailable (%s): %s", type(e).__name__, e)

    cult, lut = None, None
    if cfg.predicao:
        try:
            cult = RasterSource(str(cfg.predicao))
            lut = _tabela_de_ciclos(cfg.predicao)
        except Exception as e:
            log.warning("cropland prediction unavailable (%s): %s; "
                        "falling back to the phenological detector", type(e).__name__, e)
            cult, lut = None, None
    return classe, bases, ndvi, cinz, pivos, cult, lut

# -*- coding: utf-8 -*-
"""O NAVEGADOR: le' o continuo de sistemas de cultivo em vez de consultar uma legenda.

O motor fenometrico e a interface vem do pacote `ts-annotator`, declarado como dependencia. Este
pacote e' a APLICACAO: configuracao, montagem e ponto de entrada. Ele nao reimplementa nada do motor,
e ha' um teste que falha se alguem tentar (`tests/test_motor_compartilhado.py`).

Uso:  cycle-navigator [--config caminho.toml]
"""
import argparse
import logging
import sys

import numpy as np
import rasterio
from PyQt6.QtWidgets import QApplication

from ts_annotator.core.raster_source import RasterSource
from ts_annotator.core.timeseries import TimeSeriesSource
from ts_annotator.render import CLASS_COLORS, make_class_colorizer, make_rgb_colorizer
from ts_annotator.ui.cycle_inspect_window import CycleInspectWindow
from ts_annotator.ui.tiled_map_view import TiledMapView

from .config import ConfiguracaoAusente, carrega
from .estilo import QSS

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


def monta(cfg):
    """Abre as fontes e devolve o que a janela precisa."""
    bm = cfg.basemaps
    classe = RasterSource(str(bm["classe"]))
    T = classe.transform
    arquivos = [str(p) for p in cfg.cubo]
    # cada mes pode estar deslocado em relacao a' base; o deslocamento sai do proprio geotransform
    offs = [round((rasterio.open(f).transform.f - T.f) / T.a) for f in arquivos]
    ts = TimeSeriesSource(arquivos, bands=(1, 2, 3, 4), row_offsets=offs, nodata=65535, scale=10000)

    rgb, cinz = make_rgb_colorizer(nodata=0), cinza(nodata=0)
    ndvi = RasterSource(str(bm["ndvi"]))
    bases = {"Image · Gray": (ndvi, cinz),
             "Image · NDVI-temporal": (ndvi, rgb),
             "Image · Phenology": (RasterSource(str(bm["pheno"])), rgb),
             "Image · MNF": (RasterSource(str(bm["mnf"])), rgb),
             "Classification": (classe, make_class_colorizer(CLASS_COLORS, 255))}

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
    return classe, ts, bases, ndvi, cinz, pivos, cult, lut


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(prog="cycle-navigator", description=__doc__.splitlines()[0])
    ap.add_argument("--config", help="caminho do .toml; se omitido, procura os lugares de sempre")
    args = ap.parse_args(argv)
    try:
        cfg = carrega(args.config)
    except ConfiguracaoAusente as e:                # erro de uso, nao defeito: sem stack trace
        print(f"\n{e}\n", file=sys.stderr)
        return 2
    log.info("configuration: %s", cfg.origem)

    app = QApplication(sys.argv[:1])
    app.setStyleSheet(QSS)
    classe, ts, bases, ndvi, cinz, pivos, cult, lut = monta(cfg)
    view = TiledMapView(ndvi, cinz)
    view.vb.setLimits(xMin=-ndvi.width, xMax=2 * ndvi.width,
                      yMin=-ndvi.height, yMax=2 * ndvi.height)
    win = CycleInspectWindow(view, ts, classe, bases, pivos, crop_src=cult, count_lut=lut)
    win.resize(1520, 920)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

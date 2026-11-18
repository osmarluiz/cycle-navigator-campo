# -*- coding: utf-8 -*-
"""MONTAGEM · geografia: pixel <-> latitude/longitude.

Uma peca de `monta_app` (ver `app.py`). Recebe o contexto `ctx`, usa o que as pecas anteriores
puseram nele e deixa nele o que define. Nome de peca POSTERIOR aparece como `ctx.nome`: so' e'
lido quando a funcao roda, com tudo ja' montado.
"""
import logging

log = logging.getLogger(__name__)


def instala(ctx):
    classe = ctx.classe
    p_pontos = ctx.p_pontos
    win = ctx.win

    # ---------------- geografia ----------------
    try:
        from pyproj import Transformer
        _para_geo = Transformer.from_crs(classe.crs, "EPSG:4326", always_xy=True)
        _de_geo = Transformer.from_crs("EPSG:4326", classe.crs, always_xy=True)
    except Exception as e:                          # sem pyproj: segue sem lat/lon
        log.warning("sem conversao de coordenadas (%s): %s", type(e).__name__, e)
        _para_geo = _de_geo = None

    def latlon(row, col):
        if _para_geo is None:
            return None
        x, y = classe.transform * (col + 0.5, row + 0.5)
        lon, lat = _para_geo.transform(x, y)
        return lat, lon

    def pixel_de(lat, lon):
        """(row, col) da coordenada, ou None se cair fora do recorte."""
        if _de_geo is None:
            return None
        x, y = _de_geo.transform(lon, lat)
        col, row = ~classe.transform * (x, y)
        if 0 <= row < classe.height and 0 <= col < classe.width:
            return int(row), int(col)
        return None
    win.barra.ed_levantador.setText(p_pontos.levantador)
    win.barra.ed_levantador.editingFinished.connect(
        lambda: (p_pontos.ed_levantador.setText(win.barra.ed_levantador.text()),
                 p_pontos._salva_levantador()))

    # o que esta peca deixa para as outras
    ctx.Transformer = Transformer
    ctx._de_geo = _de_geo
    ctx._para_geo = _para_geo
    ctx.latlon = latlon
    ctx.pixel_de = pixel_de

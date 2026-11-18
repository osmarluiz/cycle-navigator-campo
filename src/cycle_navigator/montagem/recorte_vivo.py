# -*- coding: utf-8 -*-
"""MONTAGEM · recorte_vivo: o recorte do talhao na hora (SAM): pedir, desenhar, reabrir o gravado.

Uma peca de `monta_app` (ver `app.py`). Recebe o contexto `ctx`, usa o que as pecas anteriores
puseram nele e deixa nele o que define. Nome de peca POSTERIOR aparece como `ctx.nome`: so' e'
lido quando a funcao roda, com tudo ja' montado.
"""
import logging
from PyQt6.QtCore import Qt
import numpy as np
import pyqtgraph as pg
from ..recorte import RecorteVivo

log = logging.getLogger(__name__)


def instala(ctx):
    app = ctx.app
    cfg = ctx.cfg
    classe = ctx.classe
    view = ctx.view

    # ---------------- recorte na hora (SAM) ----------------
    recorte = RecorteVivo(cfg.aoi / "input" / "basemap_ndvitemporal_aoi.tif",
                          [cfg.aoi.parent / "modelos", cfg.aoi / "modelos", cfg.aoi / "sam"],
                          forma=(classe.height, classe.width))
    log.info("recorte na hora: %s", "disponivel" if recorte.ok else "desligado — " + recorte.motivo)
    PX_HA = abs(classe.transform.a * classe.transform.e) / 1e4
    linha_rec = pg.PlotCurveItem(pen=pg.mkPen("#7fe7ff", width=2.5))
    linha_rec.setZValue(26)
    view.vb.addItem(linha_rec)
    marcas_rec = pg.ScatterPlotItem(pxMode=True)       # as correcoes: + isto tambem, - isto nao
    marcas_rec.setZValue(31)
    view.vb.addItem(marcas_rec)

    def desenha_recorte(rec):
        if not rec:
            linha_rec.clear(); marcas_rec.clear()
            return
        xs, ys = rec["poli"].exterior.xy
        linha_rec.setData(np.asarray(xs), np.asarray(ys))
        marcas_rec.setData([{"pos": (c + 0.5, r + 0.5), "size": 11, "symbol": "o",
                             "pen": pg.mkPen("#000000", width=1.5),
                             "brush": pg.mkBrush("#7fe7ff" if lig else "#ff5a4f")}
                            for r, c, lig in rec["pontos"][1:]])

    def pede_recorte(pontos):
        """-> {"poli", "pontos", "nota"} ou None. Menos de um segundo, na thread da interface."""
        app.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            poli, nota = recorte.contorno(pontos)
        finally:
            app.restoreOverrideCursor()
        if poli is None:
            return None
        return {"poli": poli, "pontos": list(pontos), "nota": nota}

    def recorte_gravado(pt):
        """O contorno que foi gravado com o ponto, de volta como recorte (sem chamar o modelo)."""
        from shapely.geometry import Polygon
        cont = (pt or {}).get("contorno")
        if not cont or len(cont) < 3:
            return None
        try:
            return {"poli": Polygon(cont), "nota": float(pt.get("recorte_nota") or 0),
                    "pontos": [tuple(q) for q in (pt.get("recorte_pontos") or
                                                  [(pt["row"], pt["col"], 1)])]}
        except Exception:
            return None

    # o que esta peca deixa para as outras
    ctx.PX_HA = PX_HA
    ctx.desenha_recorte = desenha_recorte
    ctx.linha_rec = linha_rec
    ctx.marcas_rec = marcas_rec
    ctx.pede_recorte = pede_recorte
    ctx.recorte = recorte
    ctx.recorte_gravado = recorte_gravado

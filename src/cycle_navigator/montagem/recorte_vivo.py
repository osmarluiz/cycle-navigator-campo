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
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window
from ..recorte import RecorteVivo

log = logging.getLogger(__name__)


def instala(ctx):
    app = ctx.app
    cfg = ctx.cfg
    classe = ctx.classe
    view = ctx.view

    # ---------------- recorte na hora (SAM) ----------------
    _abertos = {}

    def leitor(r0, c0, lado, n):
        """⚠️⚠️ O bloco como esta' NA TELA: a fonte e o realce do mapa neste momento (ver recorte.py).
        Handle proprio por arquivo: o do mapa e' lido por outra thread."""
        src = view.source
        ds = _abertos.get(src.path)
        if ds is None:
            ds = _abertos[src.path] = rasterio.open(src.path)
        arr = ds.read(window=Window(c0, r0, lado, lado), boundless=True,
                      out_shape=(ds.count, n, n), resampling=Resampling.bilinear,
                      fill_value=ds.nodata if ds.nodata is not None else 0)
        return view.colorize(arr)[:, :, :3]

    recorte = RecorteVivo(leitor, [cfg.aoi.parent / "modelos", cfg.aoi / "modelos", cfg.aoi / "sam"],
                          versao=lambda: (view.source.path, ctx.estado.get("camada"),
                                          ctx.estado.get("mes")))
    log.info("recorte na hora: %s", "disponivel" if recorte.ok else "desligado — " + recorte.motivo)
    PX_HA = abs(classe.transform.a * classe.transform.e) / 1e4
    linha_rec = pg.PlotCurveItem(pen=pg.mkPen("#7fe7ff", width=2.5))
    linha_rec.setZValue(26)
    view.vb.addItem(linha_rec)
    marcas_rec = pg.ScatterPlotItem(pxMode=True)       # as correcoes: + isto tambem, - isto nao
    marcas_rec.setZValue(31)
    view.vb.addItem(marcas_rec)
    # a AREA que o modelo ve^ (tracejado) e, quando houve, o recorte da segunda passada (pontilhado)
    quadros = []
    for estilo_linha in (Qt.PenStyle.DashLine, Qt.PenStyle.DotLine, Qt.PenStyle.SolidLine):
        q = pg.PlotCurveItem(pen=pg.mkPen("#ffffff", width=1.2, style=estilo_linha))
        q.setZValue(25)
        view.vb.addItem(q)
        quadros.append(q)

    def _ret(item, r0, c0, r1, c1):
        item.setData(np.array([c0, c1, c1, c0, c0], float), np.array([r0, r0, r1, r1, r0], float))

    def desenha_quadro(bloco=None, fino=None, caixa=None):
        """O que o modelo esta' (ou estaria) vendo; sem argumentos, apaga."""
        for item, b in zip(quadros[:2], (bloco, fino)):
            if b is None:
                item.clear()
            else:
                _ret(item, b[0], b[1], b[0] + b[2], b[1] + b[2])
        if caixa is None:
            quadros[2].clear()
        else:
            _ret(quadros[2], *caixa)

    def desenha_recorte(rec):
        if not rec:
            linha_rec.clear(); marcas_rec.clear()
            desenha_quadro()
            return
        xs, ys = rec["poli"].exterior.xy
        linha_rec.setData(np.asarray(xs), np.asarray(ys))
        cx = rec.get("caixa")
        marcas_rec.setData([{"pos": (c + 0.5, r + 0.5), "size": 11, "symbol": "o",
                             "pen": pg.mkPen("#000000", width=1.5),
                             "brush": pg.mkBrush("#7fe7ff" if lig else "#ff5a4f")}
                            for r, c, lig in (rec["pontos"] if cx else rec["pontos"][1:])])
        desenha_quadro(rec.get("quadro"), rec.get("fino"), cx)

    def pede_recorte(pontos, caixa=None):
        """-> {"poli", "pontos", "nota", "caixa", "quadro", "fino"} ou None. Na thread da interface."""
        app.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            poli, nota = recorte.contorno(pontos, caixa)
        finally:
            app.restoreOverrideCursor()
        if poli is None:
            return None
        return {"poli": poli, "pontos": list(pontos), "nota": nota, "caixa": caixa,
                "quadro": recorte.quadro, "fino": recorte.fino}

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
    ctx.desenha_quadro = desenha_quadro
    ctx.linha_rec = linha_rec
    ctx.marcas_rec = marcas_rec
    ctx.pede_recorte = pede_recorte
    ctx.recorte = recorte
    ctx.recorte_gravado = recorte_gravado

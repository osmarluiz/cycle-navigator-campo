# -*- coding: utf-8 -*-
"""MONTAGEM · busca_posicao: a busca (lugar, CAR, coordenada) e o 'onde estou'.

Uma peca de `monta_app` (ver `app.py`). Recebe o contexto `ctx`, usa o que as pecas anteriores
puseram nele e deixa nele o que define. Nome de peca POSTERIOR aparece como `ctx.nome`: so' e'
lido quando a funcao roda, com tudo ja' montado.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCompleter
import numpy as np
import pyqtgraph as pg
from ..busca import Indice
from ..posicao import OndeEstou


def instala(ctx):
    aqui = ctx.aqui
    cadastro = ctx.cadastro
    cam_car = ctx.cam_car
    camadas = ctx.camadas
    centra = ctx.centra
    centra_fazenda = ctx.centra_fazenda
    pixel_de = ctx.pixel_de
    poe_alfinete = ctx.poe_alfinete
    view = ctx.view
    win = ctx.win

    # ---------------- busca e posicao ----------------
    indice = Indice(cam_car, cadastro)

    def atualiza_busca():
        comp = QCompleter(indice.sugestoes(), win.barra.ed_busca)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        comp.activated.connect(procura)
        win.barra.ed_busca.setCompleter(comp)

    def vai_a_coordenada(a, b, zoom=350):
        """Aceita lat,lon e lon,lat: fica com a ordem que cai dentro do recorte."""
        rc = pixel_de(a, b) or pixel_de(b, a)
        if rc is None:
            win.avisa("Essa coordenada fica fora da área das imagens", "erro", 4000)
            return None
        centra(rc[1], rc[0], zoom)
        return rc

    def procura(txt):
        if not str(txt or "").strip():
            return
        r = indice.procura(txt)
        if r is None:
            win.avisa(f"Nada encontrado para “{txt}”", "erro")
            return
        for c in camadas:                   # o cartao do contorno anterior nao segue viagem
            c.limpa_selecao()
        if r[0] == "coord":
            rc = vai_a_coordenada(r[1], r[2])
            if rc:
                poe_alfinete(*rc)
                win.avisa("Coordenada localizada — clique no talhão para abrir", "info")
        elif r[0] == "fazenda":
            centra_fazenda(r[1])
        elif r[0] == "municipio":
            b = np.array([cam_car.polys[i].bounds for i in r[2]])
            view.vb.setRange(xRange=(b[:, 0].min(), b[:, 2].max()),
                             yRange=(b[:, 1].min(), b[:, 3].max()), padding=0.03)
            win.avisa(f"{r[1]} · {len(r[2])} imóveis no CAR".replace(",", "."), "info")
        elif r[0] == "car":
            i = r[1]
            win.barra.bt_car.setChecked(True)
            c0, r0, c1, r1 = cam_car.polys[i].bounds
            meia = max(c1 - c0, r1 - r0) * 0.8 + 60
            centra((c0 + c1) / 2, (r0 + r1) / 2, meia)
            cam_car.seleciona(i)

    gps = OndeEstou(win)

    def estou_em(lat, lon, prec):
        rc = vai_a_coordenada(lat, lon)
        if rc is None:
            return
        pos = (rc[1] + 0.5, rc[0] + 0.5)
        aqui.setData([{"pos": pos, "size": 30, "pen": None, "brush": pg.mkBrush(66, 133, 244, 70)},
                      {"pos": pos, "size": 14, "pen": pg.mkPen("#ffffff", width=2.5),
                       "brush": pg.mkBrush(66, 133, 244)}])
        win.avisa("Você está aqui" + (f" (± {prec:.0f} m)" if prec > 0 else ""), "info")

    # o que esta peca deixa para as outras
    ctx.atualiza_busca = atualiza_busca
    ctx.estou_em = estou_em
    ctx.gps = gps
    ctx.indice = indice
    ctx.procura = procura
    ctx.vai_a_coordenada = vai_a_coordenada

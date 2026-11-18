# -*- coding: utf-8 -*-
"""MONTAGEM · contornos: as camadas sobre o mapa (pontos, fazendas, CAR, talhoes) e o estado.

Uma peca de `monta_app` (ver `app.py`). Recebe o contexto `ctx`, usa o que as pecas anteriores
puseram nele e deixa nele o que define. Nome de peca POSTERIOR aparece como `ctx.nome`: so' e'
lido quando a funcao roda, com tudo ja' montado.
"""
import logging
from ..car import COR_SAM
from ..car import CamadaCAR
from ..car import dados_do_sam
from ..car import html_sam
from ..fazendas import CamadaFazendas
from ..janela import IDENTIFICAR
from ..pontos import CamadaPontos
from .fontes import CAMADAS_MES

log = logging.getLogger(__name__)


def instala(ctx):
    cadastro = ctx.cadastro
    cfg = ctx.cfg
    classe = ctx.classe
    safra = ctx.safra
    tabs = ctx.tabs
    view = ctx.view
    win = ctx.win

    cam_pontos = CamadaPontos(view, cfg.classes)
    cam_faz = CamadaFazendas(view)
    cam_faz.usar(cadastro)
    cam_car = CamadaCAR(view, cfg.car, classe.transform, classe.crs) if cfg.car else None
    if cam_car is not None and cam_car.ok:
        win.barra.bt_car.show()
        # ⚠️ visivel em QUALQUER modo enquanto o botao estiver ligado. A versao anterior so' mostrava
        # no modo Desenhar: quem abria o programa nao via o CAR e nao tinha como clicar em cima.
        win.barra.carToggled.connect(cam_car.visivel)
        view.vb.sigRangeChanged.connect(cam_car.redesenha)
        view.vb.sigRangeChanged.connect(lambda *_: ctx.aviso_car())
        log.info("CAR: %d imoveis como referencia", cam_car.n)
    else:
        cam_car = None
    cam_sam = (CamadaCAR(view, cfg.sam, classe.transform, classe.crs, cor=COR_SAM,
                         cor_sel="#9fe0ff", titulo="Talhão (SAM)", html=html_sam,
                         dados=dados_do_sam) if cfg.sam else None)
    if cam_sam is not None and cam_sam.ok:
        win.barra.bt_sam.show()
        win.barra.samToggled.connect(cam_sam.visivel)
        view.vb.sigRangeChanged.connect(cam_sam.redesenha)
        log.info("SAM: %d talhoes como referencia", cam_sam.n)
    else:
        cam_sam = None
    # as camadas de contorno, na ordem de prioridade do clique: CAR primeiro, depois SAM
    camadas = [c for c in (cam_car, cam_sam) if c is not None]

    def sob_o_clique(row, col):
        """(camada, indice) do poligono visivel sob o pixel, ou (None, None)."""
        for cam in camadas:
            if cam._visivel:
                i = cam.em_idx(row, col)
                if i is not None:
                    return cam, i
        return None, None
    tabs.fazendas.lista(cadastro)
    estado = {"safra": safra, "modo": IDENTIFICAR, "mes": None, "camada": CAMADAS_MES[0],
              "car_semente": "", "semente_dados": {}, "fonte": "pixel", "sam": None,
              "recorte": None}       # {"poli": Polygon, "pontos": [(row, col, 1|0)], "nota": float}
    _curvas = {}

    # o que esta peca deixa para as outras
    ctx._curvas = _curvas
    ctx.cam_car = cam_car
    ctx.cam_faz = cam_faz
    ctx.cam_pontos = cam_pontos
    ctx.cam_sam = cam_sam
    ctx.camadas = camadas
    ctx.estado = estado
    ctx.sob_o_clique = sob_o_clique

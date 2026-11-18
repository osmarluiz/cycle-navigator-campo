# -*- coding: utf-8 -*-
"""MONTAGEM · camadas: o que o mapa mostra: camada, mes, safra.

Uma peca de `monta_app` (ver `app.py`). Recebe o contexto `ctx`, usa o que as pecas anteriores
puseram nele e deixa nele o que define. Nome de peca POSTERIOR aparece como `ctx.nome`: so' e'
lido quando a funcao roda, com tudo ja' montado.
"""
import logging
from ts_annotator.core.raster_source import RasterSource
from ts_annotator.render import make_bands_rgb_colorizer
from ..janela import IDENTIFICAR
from ..pontos import abre_store
from .fontes import CAMADAS_MES, RGB_FC, RGB_NAT, cor_ndvi

log = logging.getLogger(__name__)


def instala(ctx):
    _fontes = ctx._fontes
    bases = ctx.bases
    cam_pontos = ctx.cam_pontos
    cfg = ctx.cfg
    classe = ctx.classe
    conta = ctx.conta
    estado = ctx.estado
    p_ciclo = ctx.p_ciclo
    p_pontos = ctx.p_pontos
    refresca_analise = ctx.refresca_analise
    tabs = ctx.tabs
    view = ctx.view
    win = ctx.win

    # ---------------- camadas ----------------
    def fonte_mes(m):
        if m not in _fontes:
            _fontes[m] = RasterSource(str(cfg.aoi / "cube" / f"ride_{m}_aoi.tif"))
        return _fontes[m]

    def pinta_mapa():
        cam, m = estado["camada"], estado["mes"]
        if cam in CAMADAS_MES and m:
            src = fonte_mes(m)
            if cam == "RGB natural":
                col = make_bands_rgb_colorizer(RGB_NAT["idx"], RGB_NAT["lo"], RGB_NAT["hi"], 65535)
            elif cam == "Falsa-cor (infravermelho)":
                col = make_bands_rgb_colorizer(RGB_FC["idx"], RGB_FC["lo"], RGB_FC["hi"], 65535)
            else:
                col = cor_ndvi()
            view.set_source(src, col)
        else:
            par = bases.get(cam)
            if par is not None:
                view.set_source(*par)

    def usa_camada(nome):
        estado["camada"] = nome
        win.barra.data_ativa(nome in CAMADAS_MES)
        pinta_mapa()

    def usa_data(m):
        estado["mes"] = int(m)
        p_ciclo.marca_mes(estado["mes"])
        if estado["camada"] in CAMADAS_MES:
            pinta_mapa()

    def mes_da_curva(m):
        """Clicaram num mes da curva: o mapa vai ate' ele."""
        if m not in cfg.meses_de(estado["safra"]):
            win.avisa("Esse mês é de outra safra — troque a safra lá em cima para vê-lo no mapa",
                      "info")
            return
        if estado["camada"] not in CAMADAS_MES:
            win.barra.cb_camada.setCurrentText(CAMADAS_MES[0])
        win.barra.mostra_data(m)

    def usa_safra(s):
        estado["safra"] = s
        store = abre_store(cfg, s, classe.transform, classe.crs)
        if getattr(store, "danificado", None):
            win.avisa(f"O arquivo de pontos da safra {s} estava danificado e foi guardado como "
                      f"{store.danificado.name} — a safra abriu vazia. Avise o Osmar.", "erro", 20000)
        p_pontos.usar(store)
        cam_pontos.usar(store)
        meses = cfg.meses_de(s)
        estado["mes"] = meses[0] if estado["mes"] not in meses else estado["mes"]
        win.barra.lista_datas(meses, atual=estado["mes"])
        p_ciclo.marca_mes(estado["mes"])
        pinta_mapa()
        tabs.pontos.lista(store)
        conta()
        log.info("safra %s: %d talhao(oes)", s, len(store))
        # ⚠️⚠️ O TALHAO ABERTO E' REABERTO NA SAFRA NOVA. Sem isto o painel continuava com as faixas
        # e os meses da safra anterior, e "Gravar" punha no arquivo de 2022/23 uma soja de
        # fev/2024: dado errado, gravado sem aviso. O que estava nomeado e nao gravado se perde de
        # proposito -- era sobre outro ano.
        if p_ciclo.rc is not None and estado["modo"] == IDENTIFICAR:
            ctx.ao_clicar(*p_ciclo.rc)
        refresca_analise()

    # o que esta peca deixa para as outras
    ctx.fonte_mes = fonte_mes
    ctx.mes_da_curva = mes_da_curva
    ctx.pinta_mapa = pinta_mapa
    ctx.usa_camada = usa_camada
    ctx.usa_data = usa_data
    ctx.usa_safra = usa_safra

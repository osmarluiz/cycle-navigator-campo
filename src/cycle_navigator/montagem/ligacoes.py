# -*- coding: utf-8 -*-
"""MONTAGEM · ligacoes: os sinais da barra, dos paineis e das tabelas; a analise.

Uma peca de `monta_app` (ver `app.py`). Recebe o contexto `ctx`, usa o que as pecas anteriores
puseram nele e deixa nele o que define. Nome de peca POSTERIOR aparece como `ctx.nome`: so' e'
lido quando a funcao roda, com tudo ja' montado.
"""


def instala(ctx):
    analise = ctx.analise
    atualiza_busca = ctx.atualiza_busca
    cam_car = ctx.cam_car
    cam_sam = ctx.cam_sam
    cfg = ctx.cfg
    estado = ctx.estado
    estou_em = ctx.estou_em
    gps = ctx.gps
    mes_da_curva = ctx.mes_da_curva
    p_ciclo = ctx.p_ciclo
    p_pontos = ctx.p_pontos
    procura = ctx.procura
    recado_camada = ctx.recado_camada
    tabs = ctx.tabs
    troca_fonte = ctx.troca_fonte
    usa_camada = ctx.usa_camada
    usa_data = ctx.usa_data
    usa_modo = ctx.usa_modo
    usa_safra = ctx.usa_safra
    ve_levantados = ctx.ve_levantados
    win = ctx.win

    win.barra.safraMudou.connect(usa_safra)
    win.barra.camadaMudou.connect(usa_camada)
    win.barra.dataMudou.connect(usa_data)
    win.barra.modoMudou.connect(usa_modo)
    win.barra.buscou.connect(procura)
    win.barra.verLevantados.connect(ve_levantados)
    if cam_car is not None:
        win.barra.carToggled.connect(lambda on: recado_camada(cam_car, "CAR", on))
    if cam_sam is not None:
        win.barra.samToggled.connect(lambda on: recado_camada(cam_sam, "Talhões", on))
    win.barra.ondeEstou.connect(lambda: (win.avisa("Procurando a sua posição…", "info", 15000),
                                         gps.pede()))
    gps.achou.connect(estou_em)
    gps.falhou.connect(lambda t: win.avisa(t, "erro", 6000))
    p_ciclo.mesEscolhido.connect(mes_da_curva)
    p_ciclo.fonteMudou.connect(troca_fonte)
    p_ciclo.recado.connect(lambda t, tipo: win.avisa(t, tipo))
    p_ciclo.abriu.connect(win.abre_painel)
    win.gravarAtalho.connect(p_ciclo._emite)
    atualiza_busca()
    win.barra.abrirTabela.connect(lambda: tabs.mostra())

    def abre_analise():
        analise.atualiza(p_pontos.store, estado["safra"], cfg.meses_de(estado["safra"]))
        analise.mostra()
    win.barra.abrirAnalise.connect(abre_analise)

    # o que esta peca deixa para as outras
    ctx.abre_analise = abre_analise

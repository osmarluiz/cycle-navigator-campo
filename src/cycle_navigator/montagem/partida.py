# -*- coding: utf-8 -*-
"""MONTAGEM · partida: as ultimas ligacoes e o estado inicial (safra, camada).

Uma peca de `monta_app` (ver `app.py`). Recebe o contexto `ctx`, usa o que as pecas anteriores
puseram nele e deixa nele o que define. Nome de peca POSTERIOR aparece como `ctx.nome`: so' e'
lido quando a funcao roda, com tudo ja' montado.
"""
from ..janela import DESENHAR
from .fontes import CAMADAS_MES


def instala(ctx):
    cadastro = ctx.cadastro
    analise = ctx.analise
    ao_gravar = ctx.ao_gravar
    app = ctx.app
    cam_car = ctx.cam_car
    cam_pontos = ctx.cam_pontos
    cancela = ctx.cancela
    centra_fazenda = ctx.centra_fazenda
    clique_do_mapa = ctx.clique_do_mapa
    confirma = ctx.confirma
    desenho = ctx.desenho
    exclui = ctx.exclui
    exclui_ponto = ctx.exclui_ponto
    exporta_camada = ctx.exporta_camada
    p_ciclo = ctx.p_ciclo
    preenche = ctx.preenche
    safra = ctx.safra
    tabs = ctx.tabs
    usa_camada = ctx.usa_camada
    usa_modo = ctx.usa_modo
    usa_safra = ctx.usa_safra
    vai_ao_ponto = ctx.vai_ao_ponto
    view = ctx.view
    win = ctx.win

    analise.irPara.connect(vai_ao_ponto)
    analise.exportar.connect(lambda: exporta_camada('pontos'))
    win.barra.exportar.connect(lambda: exporta_camada('pontos'))
    win.confirmou.connect(confirma)
    win.cancelou.connect(cancela)
    win.desfezVertice.connect(desenho.desfaz_vertice)
    view.pixelClicked.connect(clique_do_mapa)
    p_ciclo.gravar.connect(ao_gravar)
    def redesenha_contorno(fid):
        fid = ctx.qual_fazenda(fid)
        if fid is not None:
            usa_modo(DESENHAR, fid)
            win.raise_(); win.activateWindow()      # o contorno se edita no mapa, nao na tabela
    tabs.fazendas.editarContorno.connect(redesenha_contorno)
    tabs.fazendas.editarDados.connect(preenche)
    tabs.fazendas.excluir.connect(exclui)
    tabs.fazendas.irPara.connect(centra_fazenda)
    tabs.fazendas.exportar.connect(lambda: exporta_camada('fazendas'))
    tabs.pontos.irPara.connect(vai_ao_ponto)
    tabs.pontos.excluir.connect(exclui_ponto)
    tabs.pontos.desfazer.connect(ctx.desfaz_exclusao)
    from PyQt6.QtGui import QKeySequence, QShortcut
    QShortcut(QKeySequence(QKeySequence.StandardKey.Undo), win).activated.connect(ctx.desfaz_exclusao)
    tabs.pontos.exportar.connect(lambda: exporta_camada('pontos'))
    view.vb.sigRangeChanged.connect(cam_pontos.redesenha)

    win.barra.cb_safra.blockSignals(True)
    win.barra.cb_safra.setCurrentText(safra)
    win.barra.cb_safra.blockSignals(False)
    usa_safra(safra)
    usa_camada(CAMADAS_MES[0])
    if cam_car is not None:
        cam_car.visivel(win.barra.bt_car.isChecked())     # aparece desde a abertura
    # rede de seguranca: se o processo for encerrado por outro caminho que nao o X da janela
    # (sys.exit, excecao no event loop), as threads do mapa ainda sao paradas antes do teardown.
    app.aboutToQuit.connect(win.para_threads)
    if getattr(cadastro, "danificado", None):
        win.avisa(f"O cadastro de fazendas estava danificado e foi guardado como "
                  f"{cadastro.danificado.name} — abriu vazio. Avise o Osmar.", "erro", 20000)


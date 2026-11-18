# -*- coding: utf-8 -*-
"""MONTAGEM · navegacao: ir ate' um ponto ou fazenda; excluir um ponto.

Uma peca de `monta_app` (ver `app.py`). Recebe o contexto `ctx`, usa o que as pecas anteriores
puseram nele e deixa nele o que define. Nome de peca POSTERIOR aparece como `ctx.nome`: so' e'
lido quando a funcao roda, com tudo ja' montado.
"""
from PyQt6.QtWidgets import QMessageBox
from ..janela import IDENTIFICAR


def instala(ctx):
    ao_clicar = ctx.ao_clicar
    cadastro = ctx.cadastro
    cam_pontos = ctx.cam_pontos
    conta = ctx.conta
    estado = ctx.estado
    p_ciclo = ctx.p_ciclo
    p_pontos = ctx.p_pontos
    refresca_analise = ctx.refresca_analise
    tabs = ctx.tabs
    usa_modo = ctx.usa_modo
    view = ctx.view
    win = ctx.win

    # ---------------- tabela ----------------
    def centra(col, row, meia=600):
        """Enquadra o mapa num ponto (col/row em pixel) com uma margem."""
        view.vb.setRange(xRange=(col - meia, col + meia), yRange=(row - meia, row + meia),
                         padding=0)

    def vai_ao_ponto(row, col):
        """Da linha da tabela ao mapa E a' curva: e' assim que se confere um rotulo."""
        usa_modo(IDENTIFICAR)
        centra(col, row)
        ao_clicar(row, col)
        win.raise_(); win.activateWindow()

    def centra_fazenda(fid):
        f = cadastro.por_id(fid)
        poli = (f or {}).get("poligono") or []
        if not poli:
            return
        xs = [q[0] for q in poli]; ys = [q[1] for q in poli]
        meia = max(max(xs) - min(xs), max(ys) - min(ys)) * 0.7 + 50
        centra((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, meia)
        win.raise_(); win.activateWindow()

    def exclui_ponto(row, col):
        if p_pontos.store is None:
            return
        if QMessageBox.question(tabs, "Excluir", "Excluir este ponto rotulado?"
                                ) != QMessageBox.StandardButton.Yes:
            return
        p_pontos.store.remove_at(row, col)
        p_pontos.atualiza_info()
        cam_pontos.redesenha()
        tabs.pontos.lista(p_pontos.store)
        conta()
        refresca_analise()
        if p_ciclo.rc == (row, col) and estado["modo"] == IDENTIFICAR:
            ao_clicar(row, col)                 # o painel aberto deixa de dizer "ja' levantado"
        win.avisa("Talhão excluído", "info")

    # o que esta peca deixa para as outras
    ctx.centra = centra
    ctx.centra_fazenda = centra_fazenda
    ctx.exclui_ponto = exclui_ponto
    ctx.vai_ao_ponto = vai_ao_ponto

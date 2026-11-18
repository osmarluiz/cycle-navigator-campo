# -*- coding: utf-8 -*-
"""MONTAGEM · modos: Identificar / Desenhar / Editar e o desenho de fazendas.

Uma peca de `monta_app` (ver `app.py`). Recebe o contexto `ctx`, usa o que as pecas anteriores
puseram nele e deixa nele o que define. Nome de peca POSTERIOR aparece como `ctx.nome`: so' e'
lido quando a funcao roda, com tudo ja' montado.
"""
import logging
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog
from ..fazendas import DesenhoPoligono
from ..fazendas import DialogoFazenda
from ..janela import DESENHAR
from ..janela import EDITAR
from ..janela import IDENTIFICAR

log = logging.getLogger(__name__)


def instala(ctx):
    cadastro = ctx.cadastro
    cam_car = ctx.cam_car
    cam_faz = ctx.cam_faz
    camadas = ctx.camadas
    estado = ctx.estado
    sob_o_clique = ctx.sob_o_clique
    status = ctx.status
    tabs = ctx.tabs
    view = ctx.view
    win = ctx.win

    # ---------------- modos ----------------
    desenho = DesenhoPoligono(view, None)

    def usa_modo(m, fid=None, semente=None):
        """`semente` = (pontos, cod_car): abre o modo Desenhar ja' com esse contorno editavel."""
        if estado["modo"] == DESENHAR and m != DESENHAR:
            desenho.cancela(); cam_faz.oculto = None; cam_faz.redesenha()
        estado["modo"] = m
        estado["semente_dados"] = dict(semente[1]) if semente else {}
        win.barra.mostra_modo(m)
        win._posiciona()
        if cam_car is not None:
            ctx.aviso_car()
        if m == DESENHAR:
            cam_faz.oculto = fid
            cam_faz.redesenha()
            if semente:
                desenho.comeca(None, semente[0])
            else:
                desenho.comeca(fid, (cadastro.por_id(fid) or {}).get("poligono") if fid else None)
        view.setCursor(Qt.CursorShape.CrossCursor if m == DESENHAR
                       else Qt.CursorShape.ArrowCursor)

    def confirma():
        """Enter / duplo-clique: fecha o contorno e abre o cadastro."""
        if estado["modo"] != DESENHAR:
            return
        pts = desenho.pontos()
        if len(pts) < 3:
            return
        fid = desenho.editando
        extra = dict(estado.get("semente_dados") or {})
        desenho.cancela()
        cam_faz.oculto = None
        f = cadastro.salva(fid, pts, extra or None)
        dlg = DialogoFazenda(f, win)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            dados = dlg.dados()
            dados.update(extra)          # os dados do CAR nao se editam no formulario
            f = cadastro.salva(f["id"], None, dados)
        cam_faz.redesenha()
        tabs.fazendas.lista(cadastro, selecionar=f["id"])
        ctx.atualiza_busca()
        win.avisa(f"Fazenda gravada · {f.get('nome') or 'sem nome'}")
        log.info("fazenda #%d: %s (%.1f ha)", f["id"], f.get("nome") or "-", f.get("area_ha") or 0)
        usa_modo(IDENTIFICAR)

    def cancela():
        for c in camadas:
            c.limpa_selecao()
        if estado["modo"] in (DESENHAR, EDITAR):
            usa_modo(IDENTIFICAR)

    def no_clique(ev):
        """⚠️ Roda ANTES do pixelClicked: no modo desenho o clique poe vertice, nao abre talhao."""
        if estado["modo"] == DESENHAR and desenho.ativo:
            # ⚠️ CAR como PONTO DE PARTIDA: sem vertice ainda, um clique dentro de um imovel carrega
            # o contorno dele ja' editavel. A pessoa ajusta ou so' da' Enter e nomeia.
            if (not desenho.pts and camadas
                    and ev.button() == Qt.MouseButton.LeftButton and not ev.double()):
                p = view.vb.mapSceneToView(ev.scenePos())
                cam, i = sob_o_clique(int(p.y()), int(p.x()))
                if cam is not None:
                    cs, rs = cam.aneis[i]
                    pts = [(float(c), float(r)) for c, r in zip(cs, rs)]
                    if len(pts) > 2 and pts[0] == pts[-1]:
                        pts = pts[:-1]
                    desenho.comeca(None, pts)
                    estado["semente_dados"] = cam.dados(cam.attr[i])
                    status(f"Contorno carregado de {cam.titulo} — ajuste os vértices ou dê Enter")
                    return
            if desenho.clique(ev) and not desenho.ativo:
                confirma()                      # duplo-clique fechou
            return
        if estado["modo"] == EDITAR and ev.double():
            p = view.vb.mapSceneToView(ev.scenePos())
            f = cadastro.em(int(p.y()), int(p.x()))
            if f:
                dlg = DialogoFazenda(f, win)
                if dlg.exec() == QDialog.DialogCode.Accepted:
                    cadastro.salva(f["id"], None, dlg.dados())
                    cam_faz.redesenha()
                    tabs.fazendas.lista(cadastro, selecionar=f["id"])

    view.glw.scene().sigMouseClicked.connect(no_clique)

    # o que esta peca deixa para as outras
    ctx.cancela = cancela
    ctx.confirma = confirma
    ctx.desenho = desenho
    ctx.no_clique = no_clique
    ctx.usa_modo = usa_modo
